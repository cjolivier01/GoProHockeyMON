"""Generate a full-scale, modular, 3D-printable hockey goalie mannequin.

The generator creates four independently hideable groups:

* a PETG/ABS skeleton with M8 friction-pivot joints,
* TPU body sleeves and dressing surfaces for fitting real goalie equipment,
* optional, simplified TPU goalie-equipment shells for display/costume use, and
* a PETG/ABS floor stand and rear backstay.

Every exported object is checked against a 250 x 250 x 200 mm build volume.
Parts are modeled locally, posed only with object transforms, and exported in a
compact print orientation at the origin.  Dimensions and print/assembly notes
are also written to a CSV manifest and stored as Blender custom properties.

This is a display and equipment-fit mannequin, not protective equipment and
not a person-supporting device.  Printed mask, pad, blocker, catcher, and chest
parts must never be used as sports safety equipment.

Run with Blender 4.4 or newer, for example:

    blender --background --factory-startup \
      --python hockey_goalie_mannequin_blender.py -- \
      --output-dir goalie_output

Useful options after ``--`` include ``--no-export``, ``--no-gear``,
``--no-body-shell``, ``--no-stand``, ``--no-save-blend``, and
``--stature-mm 1880``.
"""

from __future__ import annotations

import argparse
import csv
import math
import struct
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


# ---------------------------------------------------------------------------
# CONFIGURATION (millimeters)


@dataclass
class Config:
    # Nominal adult mannequin.  Pose height is lower because the goalie is in
    # a crouch; stature controls the proportional scale of the body.
    stature_mm: float = 1880.0
    reference_stature_mm: float = 1880.0

    shoulder_width_mm: float = 570.0
    chest_width_mm: float = 440.0
    chest_depth_mm: float = 190.0
    waist_width_mm: float = 360.0
    waist_depth_mm: float = 170.0
    head_width_mm: float = 164.0
    head_depth_mm: float = 190.0
    thigh_circumference_mm: float = 450.0
    calf_circumference_mm: float = 345.0
    upper_arm_circumference_mm: float = 365.0
    forearm_circumference_mm: float = 295.0
    hand_width_mm: float = 92.0
    foot_width_mm: float = 105.0
    gear_clearance_mm: float = 8.0

    build_x: float = 250.0
    build_y: float = 250.0
    build_z: float = 200.0
    build_margin: float = 5.0
    max_link_span: float = 170.0

    rigid_material: str = "PETG_or_ABS_ASA"
    flexible_material: str = "TPU_95A"
    pivot_bolt: str = "M8 x 40 mm class 8.8 bolt, two washers, nyloc nut"
    panel_fastener: str = "M5 bolt or 4.8 mm reusable zip tie"

    pivot_hole_diameter: float = 8.6
    straight_lock_hole_diameter: float = 5.4
    straight_lock_radius: float = 14.0
    male_lug_width: float = 8.0
    clevis_plate_width: float = 5.5
    clevis_gap: float = 10.5
    lug_radius: float = 22.0
    link_radius: float = 16.0
    terminal_neck_length: float = 29.0
    anchor_base_center: float = 34.0
    anchor_base_thickness: float = 12.0
    boolean_cleanup_distance: float = 0.0001

    generate_body_shell: bool = True
    generate_gear: bool = True
    generate_stand: bool = True
    export_stl: bool = True
    save_blend: bool = True
    output_dir: Path = Path("goalie_output")

    @property
    def body_scale(self) -> float:
        return self.stature_mm / self.reference_stature_mm


CFG = Config()


@dataclass
class PartRecord:
    part_id: str
    obj: bpy.types.Object
    category: str
    material: str
    print_notes: str
    assembly_notes: str
    fasteners: str = "None"
    safety: str = "Display mannequin component; inspect before every use."
    local_dimensions: tuple[float, float, float] = field(init=False)

    def __post_init__(self) -> None:
        self.local_dimensions = local_mesh_dimensions(self.obj)


@dataclass
class ConnectionRecord:
    connection_id: str
    mate_a: str
    mate_b: str
    hardware: tuple[tuple[str, int], ...]
    assembly_notes: str
    point_a: Vector | None = None
    point_b: Vector | None = None
    axis_a: Vector | None = None
    axis_b: Vector | None = None
    terminal_a: str | None = None
    terminal_b: str | None = None


PARTS: list[PartRecord] = []
CONNECTIONS: list[ConnectionRecord] = []
COLLECTIONS: dict[str, bpy.types.Collection] = {}
MATERIALS: dict[str, bpy.types.Material] = {}
MOUNT_PATTERN_CHECKS: list[
    tuple[
        bpy.types.Object,
        bpy.types.Object,
        tuple[tuple[float, float, float], ...],
        float,
    ]
] = []
CLAMSHELL_PAIR_CHECKS: list[tuple[bpy.types.Object, bpy.types.Object]] = []
CLEARANCE_CHECKS: list[
    tuple[bpy.types.Object, bpy.types.Object, Vector, str]
] = []
WEDGE_PANEL_CHECKS: list[
    tuple[bpy.types.Object, bpy.types.Object, tuple[Vector, ...], str]
] = []
WEDGE_BORE_CHECKS: list[
    tuple[bpy.types.Object, bpy.types.Object, tuple[Vector, ...], str]
] = []
BORE_FACE_CHECKS: list[
    tuple[bpy.types.Object, tuple[Vector, ...], float, float, str]
] = []
FRONT_GEAR_CHECKS: list[
    tuple[bpy.types.Object, bpy.types.Object, Vector, float, str]
] = []
PAD_SADDLE_CONTACT_CHECKS: list[
    tuple[
        bpy.types.Object,
        bpy.types.Object,
        tuple[Vector, ...],
        float,
        str,
    ]
] = []
PAD_HARDWARE_CLEARANCE_CHECKS: list[tuple[float, str]] = []
PAD_SADDLE_LATERAL_CLEARANCE_CHECKS: list[
    tuple[float, float, str]
] = []
DISPLAY_GEAR_STRAP_CUT_LENGTHS_MM: list[int] = []


def register_connection(
    connection_id: str,
    mate_a: str,
    mate_b: str,
    hardware: Sequence[tuple[str, int]],
    assembly_notes: str,
    *,
    point_a: Vector | None = None,
    point_b: Vector | None = None,
    axis_a: Vector | None = None,
    axis_b: Vector | None = None,
    terminal_a: str | None = None,
    terminal_b: str | None = None,
) -> None:
    CONNECTIONS.append(
        ConnectionRecord(
            connection_id,
            mate_a,
            mate_b,
            tuple(hardware),
            assembly_notes,
            point_a,
            point_b,
            axis_a.normalized() if axis_a is not None else None,
            axis_b.normalized() if axis_b is not None else None,
            terminal_a,
            terminal_b,
        )
    )


def frame_x_axis(matrix: Matrix) -> Vector:
    return Vector((matrix[0][0], matrix[1][0], matrix[2][0])).normalized()


# ---------------------------------------------------------------------------
# BLENDER AND MESH HELPERS


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        if collection.name != bpy.context.scene.collection.name:
            bpy.data.collections.remove(collection)


def set_units() -> None:
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 0.001


def ensure_collection(name: str) -> bpy.types.Collection:
    if name in COLLECTIONS:
        return COLLECTIONS[name]
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    COLLECTIONS[name] = collection
    return collection


def create_material(name: str, rgba: tuple[float, float, float, float]):
    material = bpy.data.materials.new(name)
    material.diffuse_color = rgba
    material.metallic = 0.05
    material.roughness = 0.48
    MATERIALS[name] = material
    return material


def setup_materials() -> None:
    create_material(CFG.rigid_material, (0.10, 0.22, 0.36, 1.0))
    create_material(CFG.flexible_material, (0.10, 0.55, 0.24, 1.0))
    create_material("TPU_95A_DISPLAY_GEAR", (0.70, 0.08, 0.06, 1.0))
    create_material("REFERENCE_ONLY", (0.65, 0.68, 0.72, 0.35))


def select_only(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def apply_object_transform(
    obj: bpy.types.Object,
    *,
    location: bool = False,
    rotation: bool = True,
    scale: bool = True,
) -> None:
    select_only(obj)
    bpy.ops.object.transform_apply(
        location=location,
        rotation=rotation,
        scale=scale,
    )


def recalc_normals(obj: bpy.types.Object) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def cleanup_mesh(obj: bpy.types.Object) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(
        bm,
        verts=list(bm.verts),
        dist=CFG.boolean_cleanup_distance,
    )
    bmesh.ops.dissolve_degenerate(
        bm,
        edges=list(bm.edges),
        dist=CFG.boolean_cleanup_distance,
    )
    bm.to_mesh(obj.data)
    bm.free()
    recalc_normals(obj)


def delete_object(obj: bpy.types.Object) -> None:
    bpy.data.objects.remove(obj, do_unlink=True)


def boolean_apply(
    base: bpy.types.Object,
    operand: bpy.types.Object,
    operation: str,
    label: str,
) -> bpy.types.Object:
    modifier = base.modifiers.new(label, "BOOLEAN")
    modifier.operation = operation
    modifier.solver = "EXACT"
    modifier.object = operand
    select_only(base)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    delete_object(operand)
    cleanup_mesh(base)
    return base


def union_many(
    base: bpy.types.Object,
    additions: Iterable[bpy.types.Object],
    label: str,
) -> bpy.types.Object:
    for index, addition in enumerate(additions, start=1):
        boolean_apply(base, addition, "UNION", f"{label}_{index}")
    return base


def add_box(
    name: str,
    dimensions: Sequence[float],
    location: Sequence[float] = (0.0, 0.0, 0.0),
    bevel: float = 0.0,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    obj.dimensions = dimensions
    apply_object_transform(obj, rotation=False, scale=True)
    if bevel > 0.0:
        modifier = obj.modifiers.new(name + "_Edge_Rounds", "BEVEL")
        modifier.width = min(bevel, min(dimensions) / 2.1)
        modifier.segments = 4
        select_only(obj)
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        cleanup_mesh(obj)
    return obj


def add_cylinder(
    name: str,
    radius: float,
    depth: float,
    location: Sequence[float] = (0.0, 0.0, 0.0),
    axis: str = "Z",
    vertices: int = 48,
) -> bpy.types.Object:
    rotations = {
        "X": (0.0, math.pi / 2.0, 0.0),
        "Y": (math.pi / 2.0, 0.0, 0.0),
        "Z": (0.0, 0.0, 0.0),
    }
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=depth,
        location=location,
        rotation=rotations[axis],
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    apply_object_transform(obj)
    recalc_normals(obj)
    return obj


def add_cylinder_along_vector(
    name: str,
    radius: float,
    depth: float,
    location: Sequence[float],
    direction: Sequence[float],
    vertices: int = 48,
) -> bpy.types.Object:
    direction_vector = Vector(direction).normalized()
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=depth,
        location=location,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    obj.rotation_euler = direction_vector.to_track_quat("Z", "Y").to_euler()
    apply_object_transform(obj)
    recalc_normals(obj)
    return obj


def add_sphere(name: str, radius: float) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=64,
        ring_count=32,
        radius=radius,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    recalc_normals(obj)
    return obj


def add_scaled_cone(
    name: str,
    radius_bottom: tuple[float, float],
    radius_top: tuple[float, float],
    depth: float,
) -> bpy.types.Object:
    # Blender's cone operator exposes only circular radii.  Construct the two
    # elliptical loops directly so thigh/calf/head taper can change aspect.
    segment_count = 64
    vertices: list[tuple[float, float, float]] = []
    for z, radii in ((-depth * 0.5, radius_bottom), (depth * 0.5, radius_top)):
        for index in range(segment_count):
            angle = math.tau * index / segment_count
            vertices.append(
                (radii[0] * math.cos(angle), radii[1] * math.sin(angle), z)
            )
    faces: list[tuple[int, ...]] = []
    for index in range(segment_count):
        next_index = (index + 1) % segment_count
        faces.append((index, next_index, segment_count + next_index, segment_count + index))
    faces.append(tuple(reversed(range(segment_count))))
    faces.append(tuple(range(segment_count, segment_count * 2)))
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(clean_customdata=True)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    recalc_normals(obj)
    return obj


def add_open_elliptical_sleeve(
    name: str,
    outer_bottom: tuple[float, float],
    outer_top: tuple[float, float],
    depth: float,
    wall: float,
) -> bpy.types.Object:
    outer = add_scaled_cone(name, outer_bottom, outer_top, depth)
    inner_bottom = (
        max(outer_bottom[0] - wall, 1.0),
        max(outer_bottom[1] - wall, 1.0),
    )
    inner_top = (
        max(outer_top[0] - wall, 1.0),
        max(outer_top[1] - wall, 1.0),
    )
    inner = add_scaled_cone(
        name + "_Inner_Cutter",
        inner_bottom,
        inner_top,
        depth + 2.0,
    )
    boolean_apply(outer, inner, "DIFFERENCE", name + "_Hollow")
    return outer


def add_tapered_sleeve_mount_web(
    name: str,
    bottom_radius_y: float,
    top_radius_y: float,
    height: float,
    side_sign: float,
    inner_face_y: float,
) -> bpy.types.Object:
    """Create a vertical TPU web from an inner mount land to a tapered shell."""
    half_width = 10.0
    bottom_outer_y = side_sign * bottom_radius_y
    top_outer_y = side_sign * top_radius_y
    inner_y = side_sign * inner_face_y
    vertices = (
        (-half_width, inner_y, -height * 0.5),
        (half_width, inner_y, -height * 0.5),
        (half_width, bottom_outer_y, -height * 0.5),
        (-half_width, bottom_outer_y, -height * 0.5),
        (-half_width, inner_y, height * 0.5),
        (half_width, inner_y, height * 0.5),
        (half_width, top_outer_y, height * 0.5),
        (-half_width, top_outer_y, height * 0.5),
    )
    faces = (
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    )
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(clean_customdata=True)
    mesh.update()
    web = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(web)
    recalc_normals(web)
    return web


def add_open_elliptical_sleeve_half(
    name: str,
    bottom: tuple[float, float],
    top: tuple[float, float],
    height: float,
    wall: float,
    side_sign: float,
    mount_face_y: float,
) -> bpy.types.Object:
    """Build one laced TPU half-shell with a rigid-link mounting web."""
    shell = add_open_elliptical_sleeve(name, bottom, top, height, wall)
    clip_extent = max(bottom + top) * 2.0 + 20.0
    clip = add_box(
        name + "_Half_Clip",
        (clip_extent, clip_extent, height + 10.0),
        (0.0, side_sign * clip_extent * 0.25, 0.0),
    )
    # The clip spans from the center plane to the selected front/rear side.
    clip.dimensions.y = clip_extent * 0.5
    apply_object_transform(clip, location=False, rotation=False, scale=True)
    boolean_apply(shell, clip, "INTERSECT", name + "_Half")

    web = add_tapered_sleeve_mount_web(
        name + "_Mount_Web",
        bottom[1],
        top[1],
        height,
        side_sign,
        mount_face_y,
    )
    union_many(shell, (web,), name + "_Mount_Web_Union")

    link_clearance = add_cylinder(
        name + "_Rigid_Link_Clearance",
        CFG.link_radius + 0.4,
        height + 4.0,
    )
    boolean_apply(
        shell,
        link_clearance,
        "DIFFERENCE",
        name + "_Rigid_Link_Saddle",
    )

    maximum_depth = max(bottom[1], top[1]) * 2.0 + 8.0
    mount_bore = add_cylinder(
        name + "_Mount_Hole",
        2.8,
        maximum_depth,
        (0.0, 0.0, 0.0),
        axis="Y",
        vertices=48,
    )
    boolean_apply(shell, mount_bore, "DIFFERENCE", name + "_Mount_Bore")

    # Three paired holes on each longitudinal edge close the two halves with
    # shock cord or reusable ties.  Their X location follows the local taper.
    for row, z in enumerate(
        (-height * 0.5 + 10.0, 0.0, height * 0.5 - 10.0),
        start=1,
    ):
        interpolation = z / height + 0.5
        radius_x = bottom[0] + (top[0] - bottom[0]) * interpolation
        edge_x = max(6.0, radius_x - 6.0)
        for edge_sign in (-1.0, 1.0):
            lace_bore = add_cylinder(
                f"{name}_Lace_Hole_{edge_sign}_{row}",
                SLEEVE_LACE_BORE_RADIUS_MM,
                maximum_depth,
                (edge_sign * edge_x, 0.0, z),
                axis="Y",
                vertices=32,
            )
            boolean_apply(
                shell,
                lace_bore,
                "DIFFERENCE",
                f"{name}_Lace_Bore_{edge_sign}_{row}",
            )
    shell["print_rotation_euler"] = [0.0, 0.0, 0.0]
    return shell


def add_open_box_half(
    name: str,
    outer_dimensions: tuple[float, float, float],
    wall: float,
    side_sign: float,
    *,
    open_negative_z: bool = False,
) -> bpy.types.Object:
    """Build one hollow front/back tray half around a local-Z link."""
    width, full_depth, height = outer_dimensions
    half_depth = full_depth * 0.5
    outer = add_box(
        name,
        (width, half_depth, height),
        (0.0, side_sign * full_depth * 0.25, 0.0),
        bevel=min(10.0, wall * 2.0),
    )
    cavity_depth = half_depth - wall + 1.0
    cavity_outer_edge = full_depth * 0.5 - wall
    cavity_open_edge = -1.0
    cavity_center_y = side_sign * (cavity_outer_edge + cavity_open_edge) * 0.5
    cavity_low_z = -height * 0.5 + wall
    if open_negative_z:
        cavity_low_z = -height * 0.5 - 1.0
    cavity_high_z = height * 0.5 - wall
    cavity_height = cavity_high_z - cavity_low_z
    cavity_center_z = (cavity_low_z + cavity_high_z) * 0.5
    cavity = add_box(
        name + "_Cavity",
        (width - wall * 2.0, cavity_depth, cavity_height),
        (0.0, cavity_center_y, cavity_center_z),
        bevel=max(1.0, wall),
    )
    boolean_apply(outer, cavity, "DIFFERENCE", name + "_Hollow")
    # Bake the front/rear offset into the mesh.  Callers subsequently replace
    # matrix_world with the limb pose; leaving this as an object translation
    # would collapse both halves onto the same center plane.
    apply_object_transform(
        outer,
        location=True,
        rotation=False,
        scale=False,
    )
    # Rotate the mating opening upward in the exported STL.
    outer["print_rotation_euler"] = [
        -math.pi * 0.5 if side_sign > 0.0 else math.pi * 0.5,
        0.0,
        0.0,
    ]
    return outer


def add_edge_lace_holes(
    panel: bpy.types.Object,
    name: str,
    span: float,
    height: float,
    thickness: float,
    through_axis: str,
    rows: int = 4,
) -> None:
    edge = span * 0.5 - 10.0
    for side_sign in (-1.0, 1.0):
        for row in range(rows):
            z = -height * 0.5 + 14.0 + row * (height - 28.0) / max(rows - 1, 1)
            if through_axis == "Y":
                location = (side_sign * edge, 0.0, z)
            elif through_axis == "X":
                location = (0.0, side_sign * edge, z)
            else:
                raise ValueError("Lace-hole axis must be X or Y")
            cutter = add_cylinder(
                f"{name}_Lace_Hole_{side_sign}_{row}",
                2.6,
                thickness + 6.0,
                location,
                axis=through_axis,
                vertices=32,
            )
            boolean_apply(panel, cutter, "DIFFERENCE", f"{name}_Lace_Bore")


def add_head_seam_holes(
    shell: bpy.types.Object,
    name: str,
    width: float,
    depth: float,
    height: float,
) -> None:
    for x in (-width * 0.28, width * 0.28):
        for z in (-height * 0.5 + 10.0, height * 0.5 - 10.0):
            cutter = add_cylinder(
                name + "_Seam_Hole",
                2.6,
                depth + 6.0,
                (x, 0.0, z),
                axis="Y",
                vertices=32,
            )
            boolean_apply(shell, cutter, "DIFFERENCE", name + "_Seam_Bore")


def local_mesh_bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    coordinates = [vertex.co for vertex in obj.data.vertices]
    if not coordinates:
        return Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.0, 0.0))
    low = Vector(
        tuple(min(coordinate[axis] for coordinate in coordinates) for axis in range(3))
    )
    high = Vector(
        tuple(max(coordinate[axis] for coordinate in coordinates) for axis in range(3))
    )
    return low, high


def local_mesh_dimensions(obj: bpy.types.Object) -> tuple[float, float, float]:
    low, high = local_mesh_bounds(obj)
    dimensions = high - low
    return tuple(float(value) for value in dimensions)


def frame_between(
    point_a: Sequence[float],
    point_b: Sequence[float],
    preferred_x: Sequence[float],
) -> Matrix:
    start = Vector(point_a)
    end = Vector(point_b)
    z_axis = (end - start).normalized()
    x_hint = Vector(preferred_x).normalized()
    x_axis = x_hint - z_axis * x_hint.dot(z_axis)
    if x_axis.length < 0.001:
        fallback = Vector((0.0, 1.0, 0.0))
        x_axis = fallback - z_axis * fallback.dot(z_axis)
    x_axis.normalize()
    y_axis = z_axis.cross(x_axis).normalized()
    midpoint = (start + end) * 0.5
    return Matrix(
        (
            (x_axis.x, y_axis.x, z_axis.x, midpoint.x),
            (x_axis.y, y_axis.y, z_axis.y, midpoint.y),
            (x_axis.z, y_axis.z, z_axis.z, midpoint.z),
            (0.0, 0.0, 0.0, 1.0),
        )
    )


def move_to_collection(obj: bpy.types.Object, collection_name: str) -> None:
    destination = ensure_collection(collection_name)
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    destination.objects.link(obj)


def register_part(
    part_id: str,
    obj: bpy.types.Object,
    category: str,
    material: str,
    print_notes: str,
    assembly_notes: str,
    fasteners: str = "None",
    safety: str = "Display mannequin component; inspect before every use.",
) -> PartRecord:
    obj.name = part_id
    obj.data.name = part_id + "_Mesh"
    if material in MATERIALS:
        obj.data.materials.clear()
        obj.data.materials.append(MATERIALS[material])
    move_to_collection(obj, category)
    record = PartRecord(
        part_id=part_id,
        obj=obj,
        category=category,
        material=material,
        print_notes=print_notes,
        assembly_notes=assembly_notes,
        fasteners=fasteners,
        safety=safety,
    )
    obj["part_id"] = part_id
    obj["category"] = category
    obj["recommended_material"] = material
    obj["print_notes"] = print_notes
    obj["assembly_notes"] = assembly_notes
    obj["fasteners"] = fasteners
    obj["safety"] = safety
    obj["local_dimensions_mm"] = [round(value, 3) for value in record.local_dimensions]
    PARTS.append(record)
    return record


# ---------------------------------------------------------------------------
# PRINTABLE JOINTS AND STRUCTURAL PARTS


def add_terminal_geometry(
    name: str,
    end_z: float,
    inward_sign: float,
    terminal_type: str,
) -> tuple[list[bpy.types.Object], list[bpy.types.Object]]:
    neck_length = CFG.terminal_neck_length
    neck_center_z = end_z + inward_sign * neck_length * 0.5
    components: list[bpy.types.Object] = []
    if terminal_type == "MALE":
        lane_centers = (0.0,)
        plate_width = CFG.male_lug_width
    elif terminal_type == "FEMALE":
        lane = CFG.clevis_gap * 0.5 + CFG.clevis_plate_width * 0.5
        lane_centers = (-lane, lane)
        plate_width = CFG.clevis_plate_width
    else:
        raise ValueError(f"Unknown terminal type: {terminal_type}")

    for lane_index, x_center in enumerate(lane_centers, start=1):
        disk = add_cylinder(
            f"{name}_{terminal_type}_Disk_{lane_index}",
            CFG.lug_radius,
            plate_width,
            (x_center, 0.0, end_z),
            axis="X",
        )
        neck = add_box(
            f"{name}_{terminal_type}_Neck_{lane_index}",
            (plate_width, CFG.lug_radius * 1.05, neck_length),
            (x_center, 0.0, neck_center_z),
            bevel=2.0,
        )
        components.extend((disk, neck))
    hole = add_cylinder(
        f"{name}_{terminal_type}_Pivot_Hole",
        CFG.pivot_hole_diameter * 0.5,
        CFG.clevis_gap + CFG.clevis_plate_width * 2.0 + 8.0,
        (0.0, 0.0, end_z),
        axis="X",
    )
    straight_lock_hole = add_cylinder(
        f"{name}_{terminal_type}_Straight_Lock_Hole",
        CFG.straight_lock_hole_diameter * 0.5,
        CFG.clevis_gap + CFG.clevis_plate_width * 2.0 + 8.0,
        (0.0, CFG.straight_lock_radius, end_z),
        axis="X",
    )
    return components, [hole, straight_lock_hole]


def build_pivot_link(
    name: str,
    length: float,
    start_type: str = "MALE",
    end_type: str = "FEMALE",
    radius: float | None = None,
) -> bpy.types.Object:
    if length < CFG.terminal_neck_length * 2.0 + 8.0:
        raise ValueError(f"{name} is too short for two printable terminals: {length:.1f}")
    radius = radius or CFG.link_radius
    body_length = length - CFG.terminal_neck_length * 2.0 + 5.0
    body = add_cylinder(name + "_Body", radius, body_length)
    start_components, start_holes = add_terminal_geometry(
        name + "_Start",
        -length * 0.5,
        +1.0,
        start_type,
    )
    end_components, end_holes = add_terminal_geometry(
        name + "_End",
        +length * 0.5,
        -1.0,
        end_type,
    )
    union_many(body, start_components + end_components, name + "_Terminal_Union")
    for index, cutter in enumerate(start_holes, start=1):
        boolean_apply(body, cutter, "DIFFERENCE", f"{name}_Start_Bore_{index}")
    for index, cutter in enumerate(end_holes, start=1):
        boolean_apply(body, cutter, "DIFFERENCE", f"{name}_End_Bore_{index}")
    body.name = name
    body.data.name = name + "_Mesh"
    return body


def build_anchor_bracket(
    name: str,
    terminal_type: str = "FEMALE",
    base_side: float = -1.0,
) -> bpy.types.Object:
    # A start anchor uses a FEMALE clevis and a base on local -Z.  An end
    # anchor reverses that arrangement: its MALE lug enters the final FEMALE
    # link and its base lands on local +Z.
    if terminal_type not in {"MALE", "FEMALE"}:
        raise ValueError("Anchor terminal_type must be MALE or FEMALE")
    if base_side not in {-1.0, 1.0}:
        raise ValueError("Anchor base_side must be -1.0 or +1.0")
    components, terminal_holes = add_terminal_geometry(
        name + "_Terminal",
        0.0,
        base_side,
        terminal_type,
    )
    base_z = base_side * CFG.anchor_base_center
    base = add_box(
        name + "_Base",
        (68.0, 54.0, CFG.anchor_base_thickness),
        (0.0, 0.0, base_z),
        4.0,
    )
    union_many(base, components, name + "_Terminal_Union")
    for index, cutter in enumerate(terminal_holes, start=1):
        boolean_apply(base, cutter, "DIFFERENCE", f"{name}_Terminal_Bore_{index}")
    for x, y in ((-22.0, -16.0), (-22.0, 16.0), (22.0, -16.0), (22.0, 16.0)):
        cutter = add_cylinder(name + "_Mount_Hole", 2.7, 18.0, (x, y, base_z))
        boolean_apply(base, cutter, "DIFFERENCE", name + "_Mount_Bore")
    # Boolean operations preserve the base object's creation translation.
    # Bake it so local (0, 0, 0) is the actual terminal pivot used by every
    # joint transform and by the mount-pattern projection below.
    apply_object_transform(
        base,
        location=True,
        rotation=False,
        scale=False,
    )
    base["anchor_base_side"] = base_side
    base["anchor_terminal_type"] = terminal_type
    base["terminal_center_local"] = [0.0, 0.0, 0.0]
    base["terminal_axis_local"] = [1.0, 0.0, 0.0]
    base["mount_holes_local"] = [
        [-22.0, -16.0, base_z],
        [-22.0, 16.0, base_z],
        [22.0, -16.0, base_z],
        [22.0, 16.0, base_z],
    ]
    base["print_rotation_euler"] = [
        math.pi if base_side > 0.0 else 0.0,
        0.0,
        0.0,
    ]
    return base


def build_bolted_panel(
    name: str,
    dimensions: tuple[float, float, float],
    hole_points_xy: Sequence[tuple[float, float]],
    hole_diameter: float = 6.4,
    bevel: float = 5.0,
) -> bpy.types.Object:
    panel = add_box(name, dimensions, bevel=bevel)
    for index, (x, y) in enumerate(hole_points_xy, start=1):
        cutter = add_cylinder(
            f"{name}_Hole_{index}",
            hole_diameter * 0.5,
            dimensions[2] + 4.0,
            (x, y, 0.0),
        )
        boolean_apply(panel, cutter, "DIFFERENCE", f"{name}_Bore_{index}")
    return panel


def cut_bracket_mount_pattern(
    target: bpy.types.Object,
    bracket: bpy.types.Object,
    base_side: float,
    cutter_depth: float,
    *,
    register_contact_check: bool = True,
    target_hole_radius: float = 3.0,
) -> None:
    """Cut 6 mm mating clearances coaxial with the bracket's 5.4 mm bores."""
    direction = bracket.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))
    world_holes: list[tuple[float, float, float]] = []
    local_holes = bracket["mount_holes_local"]
    for index, coordinates in enumerate(local_holes, start=1):
        location = bracket.matrix_world @ Vector(coordinates)
        world_holes.append(tuple(float(value) for value in location))
        cutter = add_cylinder_along_vector(
            f"{target.name}_{bracket.name}_Mate_Hole_{index}",
            target_hole_radius,
            cutter_depth,
            location,
            direction,
        )
        boolean_apply(
            target,
            cutter,
            "DIFFERENCE",
            f"{target.name}_{bracket.name}_Mate_Bore_{index}",
        )
    if register_contact_check:
        MOUNT_PATTERN_CHECKS.append((target, bracket, tuple(world_holes), base_side))


def register_horizontal_bore_face_checks(
    target: bpy.types.Object,
    world_holes: Sequence[Vector],
    *,
    minimum_radius: float,
    maximum_radius: float,
    label: str,
) -> None:
    """Require each in-bounds vertical bore to open on both panel faces."""
    low, high = world_aabb(target)
    centers: list[Vector] = []
    for hole in world_holes:
        if not (
            low.x - 0.01 <= hole.x <= high.x + 0.01
            and low.y - 0.01 <= hole.y <= high.y + 0.01
        ):
            continue
        centers.extend(
            (
                Vector((hole.x, hole.y, low.z)),
                Vector((hole.x, hole.y, high.z)),
            )
        )
    if not centers:
        raise ValueError(f"{label}: no mount bores fall within the target panel")
    BORE_FACE_CHECKS.append(
        (target, tuple(centers), minimum_radius, maximum_radius, label)
    )


def add_mount_hole_id_dimples(
    bracket: bpy.types.Object,
    base_side: float,
) -> None:
    """Recess one through four dots beside wedge-bracket mount holes.

    Angled wedges can require a different bolt length at every corner.  The
    dots make the generated connection-table map usable on the physical print
    without relying on Blender-local axes or an arbitrary bracket rotation.
    """
    if bracket.get("mount_hole_id_dimples"):
        return
    face_z = base_side * (
        CFG.anchor_base_center - CFG.anchor_base_thickness * 0.5
    )
    local_axis = bracket.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))
    for hole_index, coordinates in enumerate(
        bracket["mount_holes_local"],
        start=1,
    ):
        hole_x = float(coordinates[0])
        hole_y = float(coordinates[1])
        mark_y = math.copysign(23.2, hole_y)
        for dot_index in range(hole_index):
            mark_x = hole_x + (dot_index - (hole_index - 1) * 0.5) * 3.0
            local_center = Vector(
                (mark_x, mark_y, face_z + base_side * 0.35)
            )
            cutter = add_cylinder_along_vector(
                f"{bracket.name}_HOLE_{hole_index}_ID_DOT_{dot_index + 1}",
                0.9,
                1.4,
                bracket.matrix_world @ local_center,
                local_axis,
            )
            boolean_apply(
                bracket,
                cutter,
                "DIFFERENCE",
                f"{bracket.name}_HOLE_{hole_index}_ID_MARK",
            )
    bracket["mount_hole_id_dimples"] = [1, 2, 3, 4]


def build_mating_wedge_and_mount_pattern(
    name: str,
    target: bpy.types.Object,
    bracket: bpy.types.Object,
    base_side: float,
    *,
    cutter_depth: float,
    target_surface_z: float,
    target_panel_thickness: float,
    wedge_world_z_sign: float,
) -> tuple[
    bpy.types.Object,
    tuple[tuple[str, int], ...],
    str,
]:
    """Build a separate angled bracket wedge and drill the shared bores.

    The bracket plate's face farthest from its terminal is the contact face.
    The wedge continues from that face to a horizontal panel surface, avoiding
    point contact without making the broad target panel unstable on the print
    bed.  ``wedge_world_z_sign`` is -1 for a wedge below the panel and +1 for a
    wedge above it.
    """
    if wedge_world_z_sign not in {-1.0, 1.0}:
        raise ValueError("wedge_world_z_sign must be -1.0 or +1.0")
    add_mount_hole_id_dimples(bracket, base_side)
    contact_z = base_side * (
        CFG.anchor_base_center + CFG.anchor_base_thickness * 0.5
    )
    bracket_axis = (
        bracket.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))
    ).normalized()
    target_direction = bracket_axis * base_side
    if abs(target_direction.z) < 0.1:
        raise ValueError(f"{name}: bracket mount axis is too horizontal")
    target_axial_grip = target_panel_thickness / abs(target_direction.z)

    def gap_at(x: float, y: float) -> float:
        contact_point = bracket.matrix_world @ Vector((x, y, contact_z))
        gap = (target_surface_z - contact_point.z) / target_direction.z
        if gap < 3.5:
            raise ValueError(
                f"{name}: horizontal wedge is too thin at ({x:g}, {y:g}): "
                f"{gap:.3f} mm"
            )
        return gap

    # Size from the complete 68 x 54 mm bearing face, not merely from the
    # nominal center or bolt locations.  Two extra millimeters ensure the
    # pre-clip box reaches beyond the horizontal target plane everywhere.
    bearing_corners = tuple(
        (x, y) for x in (-34.0, 34.0) for y in (-27.0, 27.0)
    )
    wedge_depth = max(gap_at(x, y) for x, y in bearing_corners) + 2.0
    wedge_center_z = contact_z + base_side * wedge_depth * 0.5
    wedge = add_box(
        name,
        (68.0, 54.0, wedge_depth),
        bevel=0.0,
    )
    wedge.matrix_world = bracket.matrix_world @ Matrix.Translation(
        (0.0, 0.0, wedge_center_z)
    )

    # Keep only the gap-side half-space up to the panel face.  The oversized
    # slab is merely a deterministic Boolean cutter; it is deleted afterward.
    clip_depth = 1000.0
    clip = add_box(
        name + "_Horizontal_Clip",
        (1000.0, 1000.0, clip_depth),
        (0.0, 0.0, target_surface_z + wedge_world_z_sign * clip_depth * 0.5),
    )
    boolean_apply(
        wedge,
        clip,
        "INTERSECT",
        name + "_Horizontal_Land_Clip",
    )
    # The complete bracket face is local +Z for the current base-side -1
    # mounts.  Flip it onto the bed; retain the generalized base-side behavior
    # for any future +1 wedge.
    wedge["print_rotation_euler"] = [
        math.pi if base_side < 0.0 else 0.0,
        0.0,
        0.0,
    ]
    effective_cutter_depth = max(
        cutter_depth,
        2.0
        * (
            CFG.anchor_base_thickness * 0.5
            + wedge_depth
            + target_axial_grip
            + 5.0
        ),
    )
    cut_bracket_mount_pattern(
        wedge,
        bracket,
        base_side,
        effective_cutter_depth,
    )
    cut_bracket_mount_pattern(
        target,
        bracket,
        base_side,
        effective_cutter_depth,
        register_contact_check=False,
    )

    hole_gaps: list[float] = []
    bolt_lengths: list[int] = []
    panel_samples: list[Vector] = []
    bore_centers: list[Vector] = []
    for coordinates in bracket["mount_holes_local"]:
        x, y = float(coordinates[0]), float(coordinates[1])
        hole_gap = gap_at(x, y)
        hole_gaps.append(hole_gap)
        total_grip = (
            CFG.anchor_base_thickness + hole_gap + target_axial_grip
        )
        # Allow two washers, a full nyloc nut, at least two exposed threads,
        # and 2 mm of print/assembly tolerance, then round up to a common
        # 10 mm metric length.  Different corners can legitimately differ.
        bolt_lengths.append(int(math.ceil((total_grip + 12.0) / 10.0) * 10))
        hole_contact = bracket.matrix_world @ Vector((x, y, contact_z))
        bore_centers.append(hole_contact + target_direction * hole_gap)
        for dx, dy in ((-5.0, 0.0), (5.0, 0.0), (0.0, -5.0), (0.0, 5.0)):
            sample_contact = bracket.matrix_world @ Vector(
                (x + dx, y + dy, contact_z)
            )
            sample_gap = (
                target_surface_z - sample_contact.z
            ) / target_direction.z
            panel_samples.append(
                sample_contact + target_direction * sample_gap
            )

    bolt_counts = Counter(bolt_lengths)
    bolt_hardware = tuple(
        (
            f"M5 x {length} mm bolt + fender washers + nyloc nut",
            bolt_counts[length],
        )
        for length in sorted(bolt_counts)
    )
    bolt_mapping = "; ".join(
        f"{index}-dimple corner uses M5 x {length} mm"
        for index, length in enumerate(bolt_lengths, start=1)
    )
    wedge["bearing_gap_mm_by_hole"] = [round(value, 3) for value in hole_gaps]
    wedge["recommended_bolt_lengths_mm"] = bolt_lengths
    WEDGE_PANEL_CHECKS.append(
        (wedge, target, tuple(panel_samples), f"{wedge.name}/{target.name}")
    )
    WEDGE_BORE_CHECKS.append(
        (wedge, target, tuple(bore_centers), f"{wedge.name}/{target.name}")
    )
    # The bracket/wedge and wedge/panel interfaces are face-to-face.  Each
    # first object is shifted 0.1 mm away from its mate during validation so a
    # coplanar triangle is not mistaken for volume penetration.
    CLEARANCE_CHECKS.extend(
        (
            (
                bracket,
                wedge,
                -base_side * bracket_axis * 0.1,
                f"{bracket.name}/{wedge.name}",
            ),
            (
                wedge,
                target,
                Vector((0.0, 0.0, wedge_world_z_sign * 0.1)),
                f"{wedge.name}/{target.name}",
            ),
            (
                bracket,
                target,
                Vector((0.0, 0.0, 0.0)),
                f"{bracket.name}/{target.name}",
            ),
        )
    )
    return wedge, bolt_hardware, bolt_mapping


def add_insert_boss_and_mount_pattern(
    target: bpy.types.Object,
    bracket: bpy.types.Object,
    base_side: float,
    *,
    boss_depth: float = 16.0,
    pilot_depth: float = 12.0,
) -> None:
    """Create a planar node boss with accessible blind heat-set-insert pilots."""
    contact_z = base_side * (
        CFG.anchor_base_center + CFG.anchor_base_thickness * 0.5
    )
    boss_center_z = contact_z + base_side * boss_depth * 0.5
    boss = add_box(
        target.name + "_" + bracket.name + "_Insert_Boss",
        (68.0, 54.0, boss_depth),
        bevel=0.0,
    )
    boss.matrix_world = bracket.matrix_world @ Matrix.Translation(
        (0.0, 0.0, boss_center_z)
    )
    boolean_apply(
        target,
        boss,
        "UNION",
        target.name + "_" + bracket.name + "_Boss_Union",
    )

    direction = bracket.matrix_world.to_3x3() @ Vector((0.0, 0.0, base_side))
    world_holes: list[tuple[float, float, float]] = []
    local_holes = bracket["mount_holes_local"]
    for index, coordinates in enumerate(local_holes, start=1):
        x, y = float(coordinates[0]), float(coordinates[1])
        mouth = bracket.matrix_world @ Vector((x, y, contact_z))
        location = mouth + direction * (pilot_depth * 0.5)
        world_holes.append(tuple(float(value) for value in mouth))
        cutter = add_cylinder_along_vector(
            f"{target.name}_{bracket.name}_Insert_Pilot_{index}",
            3.4,
            pilot_depth + 0.5,
            location,
            direction,
        )
        boolean_apply(
            target,
            cutter,
            "DIFFERENCE",
            f"{target.name}_{bracket.name}_Insert_Pocket_{index}",
        )
    MOUNT_PATTERN_CHECKS.append((target, bracket, tuple(world_holes), base_side))


def cut_insert_mount_pattern(
    target: bpy.types.Object,
    bracket: bpy.types.Object,
    base_side: float,
    *,
    pilot_depth: float = 12.0,
) -> None:
    """Cut accessible blind insert pockets in an existing planar target face."""
    contact_z = base_side * (
        CFG.anchor_base_center + CFG.anchor_base_thickness * 0.5
    )
    direction = bracket.matrix_world.to_3x3() @ Vector((0.0, 0.0, base_side))
    world_holes: list[tuple[float, float, float]] = []
    for index, coordinates in enumerate(bracket["mount_holes_local"], start=1):
        x, y = float(coordinates[0]), float(coordinates[1])
        mouth = bracket.matrix_world @ Vector((x, y, contact_z))
        location = mouth + direction * (pilot_depth * 0.5)
        world_holes.append(tuple(float(value) for value in mouth))
        cutter = add_cylinder_along_vector(
            f"{target.name}_{bracket.name}_Insert_Pilot_{index}",
            3.4,
            pilot_depth + 0.5,
            location,
            direction,
        )
        boolean_apply(
            target,
            cutter,
            "DIFFERENCE",
            f"{target.name}_{bracket.name}_Insert_Pocket_{index}",
        )
    MOUNT_PATTERN_CHECKS.append((target, bracket, tuple(world_holes), base_side))


def clip_mount_face_clearance(
    target: bpy.types.Object,
    bracket: bpy.types.Object,
    base_side: float,
    cutter_dimensions: tuple[float, float, float] = (84.0, 70.0, 50.0),
) -> None:
    """Trim target material that protrudes through a bracket bearing plane."""
    contact_z = base_side * (
        CFG.anchor_base_center + CFG.anchor_base_thickness * 0.5
    )
    # The cutter occupies the bracket side of the plane and reaches 0.05 mm
    # into the node.  This leaves a deterministic non-interpenetrating fit
    # instead of coincident Boolean faces from overlapping angled bosses.
    cutter_depth = cutter_dimensions[2]
    cutter_center_z = contact_z - base_side * (cutter_depth * 0.5 - 0.05)
    cutter = add_box(
        target.name + "_" + bracket.name + "_Face_Clearance",
        cutter_dimensions,
    )
    cutter.matrix_world = bracket.matrix_world @ Matrix.Translation(
        (0.0, 0.0, cutter_center_z)
    )
    boolean_apply(
        target,
        cutter,
        "DIFFERENCE",
        target.name + "_" + bracket.name + "_Face_Clip",
    )


def add_floor_strap_slots(panel: bpy.types.Object, name: str) -> None:
    """Cut four through-slots for two 25 mm straps across a boot/foot link."""
    for x in (-64.0, 64.0):
        for y in (-55.0, 55.0):
            cutter = add_box(
                f"{name}_Foot_Strap_Slot",
                (8.0, 34.0, 24.0),
                (x, y, 0.0),
                bevel=3.5,
            )
            boolean_apply(panel, cutter, "DIFFERENCE", f"{name}_Foot_Strap_Cut")


def add_head_mount_web(
    shell: bpy.types.Object,
    radius_x: float,
    radius_y: float,
    local_z: float,
) -> None:
    """Join a four-hole central head land to the elliptical TPU ring."""
    pieces = (
        add_box("BODY_HEAD_MOUNT_CENTER", (80.0, 68.0, 8.0), (0.0, 0.0, local_z), 3.0),
        add_box(
            "BODY_HEAD_MOUNT_X_WEB",
            (radius_x * 2.0, 14.0, 8.0),
            (0.0, 0.0, local_z),
            3.0,
        ),
        add_box(
            "BODY_HEAD_MOUNT_Y_WEB",
            (14.0, radius_y * 2.0, 8.0),
            (0.0, 0.0, local_z),
            3.0,
        ),
    )
    union_many(shell, pieces, "BODY_HEAD_MOUNT_WEB_UNION")


def subdivide_line(
    start: Sequence[float],
    end: Sequence[float],
    max_span: float,
) -> list[Vector]:
    point_a = Vector(start)
    point_b = Vector(end)
    count = max(1, math.ceil((point_b - point_a).length / max_span))
    return [point_a.lerp(point_b, index / count) for index in range(count + 1)]


@dataclass
class ChainPart:
    record: PartRecord
    matrix: Matrix
    length: float
    start: Vector
    end: Vector


def build_link_chain(
    prefix: str,
    start: Sequence[float],
    end: Sequence[float],
    pivot_axis: Sequence[float],
    category: str = "01_STRUCTURE_PETG_ABS",
    radius: float | None = None,
) -> list[ChainPart]:
    points = subdivide_line(start, end, CFG.max_link_span * CFG.body_scale)
    result: list[ChainPart] = []
    for index, (point_a, point_b) in enumerate(zip(points, points[1:]), start=1):
        length = (point_b - point_a).length
        part_id = f"{prefix}_{index:02d}"
        obj = build_pivot_link(part_id, length, radius=radius)
        matrix = frame_between(point_a, point_b, pivot_axis)
        obj.matrix_world = matrix
        record = register_part(
            part_id,
            obj,
            category,
            CFG.rigid_material,
            "Use the exported orientation: link axis horizontal and both transverse bores vertical; support the upper clevis plate from the bed.",
            "The next part's MALE start lug enters this part's FEMALE end. Install the M5 straight-lock bolt at print splits; omit it only at an intentional anatomical joint.",
            CFG.pivot_bolt + "; M5 x 35 mm straight-lock bolt at rigid print splits",
        )
        chain_part = ChainPart(record, matrix, length, point_a, point_b)
        if result:
            previous = result[-1]
            register_connection(
                f"{prefix}_RIGID_SPLICE_{index - 1:02d}_{index:02d}",
                previous.record.part_id + ".END_FEMALE",
                record.part_id + ".START_MALE",
                (
                    ("M8 x 40 mm class 8.8 bolt + 2 washers + nyloc nut", 1),
                    ("M5 x 35 mm bolt + 2 washers + nyloc nut (straight lock)", 1),
                ),
                "Align both center bores and the offset straight-lock bores; install both bolts so this print split cannot fold.",
                point_a=previous.matrix @ Vector((0.0, 0.0, previous.length * 0.5)),
                point_b=matrix @ Vector((0.0, 0.0, -length * 0.5)),
                axis_a=frame_x_axis(previous.matrix),
                axis_b=frame_x_axis(matrix),
                terminal_a="FEMALE",
                terminal_b="MALE",
            )
        result.append(chain_part)
    return result


def register_chain_joint(
    connection_id: str,
    chain_a: Sequence[ChainPart],
    chain_b: Sequence[ChainPart],
    *,
    locked: bool = False,
) -> None:
    end_part = chain_a[-1]
    start_part = chain_b[0]
    hardware: list[tuple[str, int]] = [
        ("M8 x 40 mm class 8.8 bolt + 2 washers + nyloc nut", 1)
    ]
    if locked:
        hardware.append(
            ("M5 x 35 mm bolt + 2 washers + nyloc nut (straight lock)", 1)
        )
    register_connection(
        connection_id,
        end_part.record.part_id + ".END_FEMALE",
        start_part.record.part_id + ".START_MALE",
        hardware,
        "Install the M8 pivot with washers on both printed faces. "
        + ("Install the M5 straight lock." if locked else "Leave the M5 lock bore empty for intentional articulation."),
        point_a=end_part.matrix @ Vector((0.0, 0.0, end_part.length * 0.5)),
        point_b=start_part.matrix @ Vector((0.0, 0.0, -start_part.length * 0.5)),
        axis_a=frame_x_axis(end_part.matrix),
        axis_b=frame_x_axis(start_part.matrix),
        terminal_a="FEMALE",
        terminal_b="MALE",
    )


def register_anchor_joint(
    connection_id: str,
    anchor_id: str,
    anchor_matrix: Matrix,
    chain: Sequence[ChainPart],
    *,
    at_chain_start: bool,
    locked: bool = True,
) -> None:
    link = chain[0] if at_chain_start else chain[-1]
    terminal_z = -link.length * 0.5 if at_chain_start else link.length * 0.5
    anchor_point = anchor_matrix @ Vector((0.0, 0.0, 0.0))
    link_point = link.matrix @ Vector((0.0, 0.0, terminal_z))
    link_terminal = "MALE" if at_chain_start else "FEMALE"
    anchor_terminal = "FEMALE" if at_chain_start else "MALE"
    hardware: list[tuple[str, int]] = [
        ("M8 x 40 mm class 8.8 bolt + 2 washers + nyloc nut", 1)
    ]
    if locked:
        hardware.append(
            ("M5 x 35 mm bolt + 2 washers + nyloc nut (straight lock)", 1)
        )
    register_connection(
        connection_id,
        anchor_id + f".{anchor_terminal}",
        link.record.part_id + f".{link_terminal}",
        hardware,
        "Seat the link in the anchor, install the M8 pivot, then install the M5 straight lock for the generated pose.",
        point_a=anchor_point,
        point_b=link_point,
        axis_a=frame_x_axis(anchor_matrix),
        axis_b=frame_x_axis(link.matrix),
        terminal_a=anchor_terminal,
        terminal_b=link_terminal,
    )


SLEEVE_LINK_SADDLE_RADIUS = CFG.link_radius + 0.4
SLEEVE_ROD_CAP_PROJECTION_MM = 3.0
SLEEVE_ROD_CENTER_TOLERANCE_MM = 1.0
SLEEVE_HARDWARE_MAX_RADIUS_MM = 10.0
SLEEVE_LACE_BORE_RADIUS_MM = 2.6
HAND_FORM_MIN_WIDTH_MM = 78.0
HAND_FORM_MIN_DEPTH_MM = 64.0


def sleeve_mount_rod_length(bottom_radius_y: float, top_radius_y: float) -> int:
    """Return a cut length with room for both washer/nut/cap stacks."""
    middle_radius_y = (bottom_radius_y + top_radius_y) * 0.5
    return int(math.ceil((middle_radius_y * 2.0 + 20.0) / 10.0) * 10)


def add_link_sleeve_mount_bore(link: ChainPart) -> None:
    """Cut the transverse M5 rod path that retains a TPU clamshell."""
    obj = link.record.obj
    if obj.get("sleeve_mount_through_bore"):
        return
    cutter = add_cylinder(
        f"{obj.name}_SLEEVE_MOUNT_THROUGH_HOLE",
        2.8,
        52.0,
        axis="Y",
    )
    cutter.matrix_world = link.matrix
    boolean_apply(
        obj,
        cutter,
        "DIFFERENCE",
        f"{obj.name}_SLEEVE_MOUNT_THROUGH_BORE",
    )
    obj["sleeve_mount_through_bore"] = [0.0, 0.0, 0.0]
    link.record.print_notes = (
        "Use the exported orientation: link axis horizontal and the local-X "
        "pivot/lock bores vertical. The 5.6 mm local-Y sleeve-mount bore is "
        "horizontal; enable short-bridge settings or local bore support, then "
        "ream it to 5.6 mm. Support the upper clevis plate from the bed."
    )
    link.record.fasteners += "; 1 x configuration-length M5 sleeve through-rod"
    link.record.local_dimensions = local_mesh_dimensions(obj)
    obj["print_notes"] = link.record.print_notes
    obj["fasteners"] = link.record.fasteners
    obj["local_dimensions_mm"] = [
        round(value, 3) for value in link.record.local_dimensions
    ]


def build_chain_sleeves(
    prefix: str,
    chain: Sequence[ChainPart],
    radius_start: tuple[float, float],
    radius_end: tuple[float, float],
) -> list[PartRecord]:
    records: list[PartRecord] = []
    count = len(chain)
    for index, link in enumerate(chain, start=1):
        t0 = (index - 1) / count
        t1 = index / count
        bottom = tuple(
            radius_start[axis] + (radius_end[axis] - radius_start[axis]) * t0
            for axis in range(2)
        )
        top = tuple(
            radius_start[axis] + (radius_end[axis] - radius_start[axis]) * t1
            for axis in range(2)
        )
        sleeve_length = max(45.0, link.length - CFG.lug_radius * 2.35)
        part_id = f"{prefix}_{index:02d}"
        add_link_sleeve_mount_bore(link)
        rod_length = sleeve_mount_rod_length(bottom[1], top[1])
        mount_hardware = (
            f"M5 fully threaded rod cut to {rod_length} mm + "
            "2 x 20 mm fender washers + 2 nyloc nuts + 2 low-profile "
            f"thread-protector caps (maximum {SLEEVE_HARDWARE_MAX_RADIUS_MM * 2.0:g} mm "
            f"outside diameter and {SLEEVE_ROD_CAP_PROJECTION_MM:g} mm past each rod end)"
        )
        half_records: list[PartRecord] = []
        for half_name, side_sign in (("FRONT", 1.0), ("REAR", -1.0)):
            half_id = f"{part_id}_{half_name}"
            half = add_open_elliptical_sleeve_half(
                half_id,
                bottom,
                top,
                sleeve_length,
                4.0,
                side_sign,
                0.0,
            )
            half.matrix_world = link.matrix
            record = register_part(
                half_id,
                half,
                "02_BODY_FORMS_TPU",
                CFG.flexible_material,
                "Print upright on an open end with 4+ walls; the longitudinal mount web and open clamshell need no trapped support.",
                f"Place around the matching rigid link and pass the configuration-length M5 rod through both TPU webs and the rigid link. With caps off, center the bare rod so its tip-to-sleeve-face projection differs by no more than {SLEEVE_ROD_CENTER_TOLERANCE_MM:g} mm between front and rear; hold that position while clamping with fender washers and nyloc nuts, then cap it and lace both long seams. Do not rely on sleeve friction.",
                mount_hardware + "; 4 mm shock cord or reusable zip ties",
                "Dressing/fit surface only; it is not impact padding.",
            )
            records.append(record)
            half_records.append(record)
            saddle_bore_center = link.matrix @ Vector(
                (0.0, side_sign * SLEEVE_LINK_SADDLE_RADIUS, 0.0)
            )
            WEDGE_BORE_CHECKS.append(
                (
                    half,
                    link.record.obj,
                    (saddle_bore_center,),
                    f"{half.name}/{link.record.obj.name} sleeve mount",
                )
            )
            CLEARANCE_CHECKS.append(
                (
                    half,
                    link.record.obj,
                    Vector((0.0, 0.0, 0.0)),
                    f"{half.name}/{link.record.obj.name} sleeve clearance",
                )
            )
        CLAMSHELL_PAIR_CHECKS.append(
            (half_records[0].obj, half_records[1].obj)
        )
        register_connection(
            f"{part_id}_STRUCTURAL_MOUNT",
            link.record.part_id + ".SLEEVE_THROUGH_BORE",
            f"{half_records[0].part_id}+{half_records[1].part_id}",
            (
                (mount_hardware, 1),
                ("4 mm shock cord or 4.8 mm reusable zip tie", 6),
            ),
            f"Place both TPU saddle webs around the rigid link and pass the listed M5 threaded rod through the aligned front-web, rigid-link, and rear-web bores. Before tightening and with caps off, measure from each bare rod tip to its adjacent outer sleeve face; center the rod so those projections differ by no more than {SLEEVE_ROD_CENTER_TOLERANCE_MM:g} mm. Hold it centered while installing fender washers and nyloc nuts without crushing the TPU, then deburr and install the specified low-profile caps. Lace the three paired holes along both longitudinal seams. The through-rod is the mandatory structural retainer for the body form.",
        )
    return records


# ---------------------------------------------------------------------------
# MANNEQUIN ASSEMBLY


def scaled(point: Sequence[float]) -> Vector:
    return Vector(point) * CFG.body_scale


def structural_shoulder_half_width() -> float:
    """Keep the rigid shoulder mount outside the configured chest form."""
    return max(
        CFG.shoulder_width_mm * 0.5,
        CFG.chest_width_mm * 0.5 + 45.0,
    )


def derived_hand_form_width_depth() -> tuple[float, float]:
    """Return the TPU hand envelope after clearance and bracket-safe floors."""
    return (
        max(
            CFG.hand_width_mm + CFG.gear_clearance_mm * 2.0,
            HAND_FORM_MIN_WIDTH_MM,
        ),
        max(
            CFG.hand_width_mm * 0.58 + CFG.gear_clearance_mm * 2.0,
            HAND_FORM_MIN_DEPTH_MM,
        ),
    )


def structural_pelvis_depth() -> float:
    """Keep fixed-size hip/saddle interfaces supported at small statures."""
    return max(120.0, 120.0 * CFG.body_scale)


def structural_pelvis_thickness() -> float:
    """Preserve M6 washer seats and ligament at the rear-saddle pattern."""
    return max(40.0, 24.0 * CFG.body_scale)


def matrix_with_translation(matrix: Matrix, offset_local: Sequence[float]) -> Matrix:
    result = matrix.copy()
    result.translation = matrix @ Vector(offset_local)
    return result


def align_start_anchor_below_horizontal_land(
    pivot: Vector,
    next_point: Vector,
    pivot_axis: Vector,
    land_underside_z: float,
    minimum_wedge_thickness: float = 4.0,
) -> Vector:
    """Lower a start pivot, leaving a printable wedge below a panel."""
    result = pivot.copy()
    contact_z = -(
        CFG.anchor_base_center + CFG.anchor_base_thickness * 0.5
    )
    for _ in range(20):
        frame = frame_between(result, next_point, pivot_axis)
        rotation = frame.to_3x3()
        corner_offsets = [
            (rotation @ Vector((x, y, contact_z))).z
            for x in (-34.0, 34.0)
            for y in (-27.0, 27.0)
        ]
        updated_z = (
            land_underside_z - minimum_wedge_thickness - max(corner_offsets)
        )
        if abs(updated_z - result.z) < 0.001:
            result.z = updated_z
            break
        result.z = updated_z
    return result


def align_start_anchor_above_horizontal_land(
    pivot: Vector,
    next_point: Vector,
    pivot_axis: Vector,
    land_top_z: float,
    minimum_wedge_thickness: float = 4.0,
) -> Vector:
    """Raise a start pivot, leaving a printable wedge above a panel."""
    result = pivot.copy()
    contact_z = -(
        CFG.anchor_base_center + CFG.anchor_base_thickness * 0.5
    )
    for _ in range(20):
        frame = frame_between(result, next_point, pivot_axis)
        rotation = frame.to_3x3()
        corner_offsets = [
            (rotation @ Vector((x, y, contact_z))).z
            for x in (-34.0, 34.0)
            for y in (-27.0, 27.0)
        ]
        updated_z = (
            land_top_z + minimum_wedge_thickness - min(corner_offsets)
        )
        if abs(updated_z - result.z) < 0.001:
            result.z = updated_z
            break
        result.z = updated_z
    return result


def build_lower_body() -> dict[str, list[ChainPart]]:
    chains: dict[str, list[ChainPart]] = {}
    pelvis_underside_z = (
        900.0 * CFG.body_scale - structural_pelvis_thickness() * 0.5
    )
    for side_name, side_sign in (("L", -1.0), ("R", 1.0)):
        hip = scaled((160.0 * side_sign, 0.0, 850.0))
        knee = scaled((300.0 * side_sign, 115.0, 505.0))
        ankle = scaled((185.0 * side_sign, 25.0, 115.0))
        for _ in range(8):
            leg_plane_normal = (knee - hip).cross(ankle - knee).normalized()
            updated_hip = align_start_anchor_below_horizontal_land(
                hip,
                knee,
                leg_plane_normal,
                pelvis_underside_z,
            )
            if (updated_hip - hip).length < 0.001:
                hip = updated_hip
                break
            hip = updated_hip
        leg_plane_normal = (knee - hip).cross(ankle - knee).normalized()
        desired_foot_direction = Vector((0.0, 275.0, -60.0)) * CFG.body_scale
        foot_direction = (
            desired_foot_direction
            - leg_plane_normal * desired_foot_direction.dot(leg_plane_normal)
        )
        toe = ankle + foot_direction

        thigh = build_link_chain(
            f"STRUCT_{side_name}_THIGH", hip, knee, leg_plane_normal
        )
        shin = build_link_chain(
            f"STRUCT_{side_name}_SHIN", knee, ankle, leg_plane_normal
        )
        foot = build_link_chain(
            f"STRUCT_{side_name}_FOOT", ankle, toe, leg_plane_normal
        )
        chains[f"{side_name}_THIGH"] = thigh
        chains[f"{side_name}_SHIN"] = shin
        chains[f"{side_name}_FOOT"] = foot

        bracket = build_anchor_bracket(f"STRUCT_{side_name}_HIP_BRACKET")
        bracket.matrix_world = frame_between(hip, knee, leg_plane_normal)
        bracket.matrix_world.translation = hip
        pelvis_target = bpy.data.objects[f"STRUCT_PELVIS_{side_name}"]
        hip_wedge_id = f"STRUCT_{side_name}_HIP_WEDGE"
        hip_wedge, hip_bolt_hardware, hip_bolt_mapping = (
            build_mating_wedge_and_mount_pattern(
            hip_wedge_id,
            pelvis_target,
            bracket,
            -1.0,
            cutter_depth=95.0 * CFG.body_scale,
            target_surface_z=pelvis_underside_z,
            target_panel_thickness=structural_pelvis_thickness(),
            wedge_world_z_sign=-1.0,
            )
        )
        register_part(
            hip_wedge_id,
            hip_wedge,
            "01_STRUCTURE_PETG_ABS",
            CFG.rigid_material,
            "Print on the 68 x 54 mm angled-bracket face with 6+ walls and 40% gyroid infill.",
            "Place the horizontal face against the pelvis underside and the angled face against the hip bracket; align all four modeled bores.",
            "Shares the four configuration-derived M5 hip-mount bolts",
        )
        register_part(
            f"STRUCT_{side_name}_HIP_BRACKET",
            bracket,
            "01_STRUCTURE_PETG_ABS",
            CFG.rigid_material,
            "Print base-down; use 6+ walls and 35% gyroid infill.",
            "Bolt through the matching pelvis half, then capture the first thigh MALE lug.",
            "4 x M5 bolts plus " + CFG.pivot_bolt,
        )
        register_anchor_joint(
            f"{side_name}_HIP_PIVOT",
            f"STRUCT_{side_name}_HIP_BRACKET",
            bracket.matrix_world,
            thigh,
            at_chain_start=True,
            locked=True,
        )
        register_chain_joint(f"{side_name}_KNEE_PIVOT", thigh, shin)
        register_chain_joint(f"{side_name}_ANKLE_PIVOT", shin, foot)
        register_connection(
            f"{side_name}_HIP_BRACKET_MOUNT",
            f"STRUCT_PELVIS_{side_name}+{hip_wedge_id}",
            f"STRUCT_{side_name}_HIP_BRACKET.BASE",
            hip_bolt_hardware,
            "Through-bolt the bracket, separate full-area wedge, and pelvis using the modeled coaxial pattern; use washers at both printed outer faces. On the terminal-facing bracket face, shallow dot groups identify each hole. Marked-hole bolt map: "
            + hip_bolt_mapping,
        )

        if CFG.generate_body_shell:
            thigh_radius = (
                CFG.thigh_circumference_mm / math.tau + CFG.gear_clearance_mm
            )
            calf_radius = (
                CFG.calf_circumference_mm / math.tau + CFG.gear_clearance_mm
            )
            build_chain_sleeves(
                f"BODY_{side_name}_THIGH_SLEEVE",
                thigh,
                (thigh_radius, thigh_radius * 0.86),
                (thigh_radius * 0.72, thigh_radius * 0.65),
            )
            build_chain_sleeves(
                f"BODY_{side_name}_CALF_SLEEVE",
                shin,
                (calf_radius, calf_radius * 0.94),
                (calf_radius * 0.73, calf_radius * 0.67),
            )
            for index, link in enumerate(foot, start=1):
                outer_dimensions = (
                    CFG.foot_width_mm + CFG.gear_clearance_mm * 2.0,
                    CFG.foot_width_mm * 0.78 + CFG.gear_clearance_mm * 2.0,
                    max(70.0, link.length - 28.0),
                )
                for half_name, half_sign in (("FRONT", 1.0), ("REAR", -1.0)):
                    shell_id = (
                        f"BODY_{side_name}_BOOT_SHELL_{index:02d}_{half_name}"
                    )
                    shell = add_open_box_half(
                        shell_id,
                        outer_dimensions,
                        4.0,
                        half_sign,
                    )
                    add_edge_lace_holes(
                        shell,
                        shell_id,
                        outer_dimensions[0],
                        outer_dimensions[2],
                        outer_dimensions[1],
                        "Y",
                        rows=3,
                    )
                    shell.matrix_world = link.matrix
                    shell_record = register_part(
                        shell_id,
                        shell,
                        "02_BODY_FORMS_TPU",
                        CFG.flexible_material,
                        "Print cavity-up with 4 walls; the exported clamshell needs no trapped support.",
                        "Lace the reinforced edge holes to close both halves around the matching foot link.",
                        "4 mm shock cord",
                        "Dressing form only; not a skate or protective boot.",
                    )
                    if half_name == "FRONT":
                        front_shell = shell_record.obj
                    else:
                        CLAMSHELL_PAIR_CHECKS.append((front_shell, shell_record.obj))
    return chains


def build_pelvis_and_torso() -> dict[str, list[ChainPart]]:
    s = CFG.body_scale
    # The two pelvis halves meet at a butt seam.  Separate top/bottom lap
    # plates clamp the seam without putting two printable solids in the same
    # preview volume, and both hip lands share the same underside elevation.
    pelvis_half_width = max(200.0, 200.0 * s)
    pelvis_depth = structural_pelvis_depth()
    pelvis_thickness = structural_pelvis_thickness()
    pelvis_center_z = 900.0 * s
    pelvis_dimensions = (pelvis_half_width, pelvis_depth, pelvis_thickness)
    for side_name, side_sign in (("L", -1.0), ("R", 1.0)):
        panel_id = f"STRUCT_PELVIS_{side_name}"
        panel_center_x = pelvis_half_width * 0.5 * side_sign
        global_lap_x = 45.0 * s * side_sign
        local_lap_x = global_lap_x - panel_center_x
        panel = build_bolted_panel(
            panel_id,
            pelvis_dimensions,
            ((local_lap_x, -35.0 * s), (local_lap_x, 35.0 * s)),
            # Keep the center butt seam, rear saddle strip, and hip-wedge
            # bearing faces planar.  A whole-box bevel rounds away these
            # structural interfaces on the minimum-height pelvis.
            bevel=0.0,
        )
        panel.location = (panel_center_x, 0.0, pelvis_center_z)
        register_part(
            panel_id,
            panel,
            "01_STRUCTURE_PETG_ABS",
            CFG.rigid_material,
            "Print flat on the broad face; 6+ walls and 30-40% gyroid infill.",
            "Butt the center edge against the other pelvis half, then clamp both faces with the separate top and bottom lap plates.",
            "2 shared M6 x 75 mm lap bolts",
        )

    lap_thickness = 8.0 * s
    lap_dimensions = (140.0 * s, 100.0 * s, lap_thickness)
    lap_center_offset = pelvis_thickness * 0.5 + lap_thickness * 0.5
    for face_name, z in (
        ("TOP", pelvis_center_z + lap_center_offset),
        ("BOTTOM", pelvis_center_z - lap_center_offset),
    ):
        part_id = f"STRUCT_PELVIS_LAP_{face_name}"
        lap = build_bolted_panel(
            part_id,
            lap_dimensions,
            ((-45.0 * s, -35.0 * s), (-45.0 * s, 35.0 * s),
             (45.0 * s, -35.0 * s), (45.0 * s, 35.0 * s)),
            bevel=5.0,
        )
        lap.location = (0.0, 0.0, z)
        register_part(
            part_id,
            lap,
            "01_STRUCTURE_PETG_ABS",
            CFG.rigid_material,
            "Print flat with 7 walls and 40% gyroid infill.",
            "Clamp across the pelvis butt seam; its four bores align with the two bores in each pelvis half.",
            "4 shared M6 x 75 mm lap bolts",
        )
    register_connection(
        "PELVIS_CENTER_LAP",
        "STRUCT_PELVIS_L+STRUCT_PELVIS_R",
        "STRUCT_PELVIS_LAP_TOP+STRUCT_PELVIS_LAP_BOTTOM",
        (("M6 x 75 mm bolt + 2 washers + nyloc nut", 4),),
        "Butt the pelvis halves, sandwich them between both lap plates, and align all four modeled through-bores.",
    )

    if CFG.generate_stand:
        # Rear saddle gives the optional stand a flat, supported land spanning
        # both halves.  A structure-only build has no unused saddle or holes.
        saddle_row_offset = 10.0
        saddle = add_box(
            "STRUCT_PELVIS_REAR_SADDLE",
            (160.0 * s, 18.0, 80.0 * s),
            bevel=5.0,
        )
        for x in (-60.0 * s, 60.0 * s):
            for z in (-saddle_row_offset, saddle_row_offset):
                cutter = add_cylinder(
                    "STRUCT_PELVIS_REAR_SADDLE_HOLE",
                    3.2,
                    24.0,
                    (x, 0.0, z),
                    axis="Y",
                )
                boolean_apply(
                    saddle,
                    cutter,
                    "DIFFERENCE",
                    "STRUCT_PELVIS_REAR_SADDLE_BORE",
                )
        saddle.location = (
            0.0,
            -pelvis_depth * 0.5 - 9.0,
            pelvis_center_z,
        )
        saddle_row_z = (
            pelvis_center_z - saddle_row_offset,
            pelvis_center_z + saddle_row_offset,
        )
        for side_name, side_sign in (("L", -1.0), ("R", 1.0)):
            pelvis_target = bpy.data.objects[f"STRUCT_PELVIS_{side_name}"]
            for z in saddle_row_z:
                cutter = add_cylinder(
                    f"STRUCT_PELVIS_{side_name}_SADDLE_MATE_HOLE",
                    3.2,
                    pelvis_depth + 6.0,
                    (60.0 * side_sign * s, 0.0, z),
                    axis="Y",
                )
                boolean_apply(
                    pelvis_target,
                    cutter,
                    "DIFFERENCE",
                    f"STRUCT_PELVIS_{side_name}_SADDLE_MATE_BORE",
                )
        for side_name in ("L", "R"):
            pelvis_target = bpy.data.objects[f"STRUCT_PELVIS_{side_name}"]
            side_sign = -1.0 if side_name == "L" else 1.0
            bore_centers = tuple(
                Vector(
                    (
                        60.0 * side_sign * s,
                        -pelvis_depth * 0.5,
                        z,
                    )
                )
                for z in saddle_row_z
            )
            bearing_samples = tuple(
                center + Vector(offset)
                for center in bore_centers
                for offset in (
                    (-5.0, 0.0, 0.0),
                    (5.0, 0.0, 0.0),
                    (0.0, 0.0, -5.0),
                    (0.0, 0.0, 5.0),
                    (-7.0, 0.0, 0.0),
                    (7.0, 0.0, 0.0),
                    (0.0, 0.0, -7.0),
                    (0.0, 0.0, 7.0),
                )
            )
            label = f"{saddle.name}/{pelvis_target.name}"
            CLEARANCE_CHECKS.append(
                (
                    saddle,
                    pelvis_target,
                    Vector((0.0, -0.1, 0.0)),
                    label,
                )
            )
            WEDGE_PANEL_CHECKS.append(
                (saddle, pelvis_target, bearing_samples, label)
            )
            WEDGE_BORE_CHECKS.append(
                (saddle, pelvis_target, bore_centers, label)
            )
        register_part(
            "STRUCT_PELVIS_REAR_SADDLE",
            saddle,
            "01_STRUCTURE_PETG_ABS",
            CFG.rigid_material,
            "Print flat on the broad face with 7 walls and 40% gyroid infill.",
            "Seat across the rear faces of both pelvis halves; four long through-bolts terminate at accessible front-face nuts.",
            "4 x M6 x 170 mm through-bolts and 2 drilled steel backing plates",
        )
        register_connection(
            "PELVIS_REAR_SADDLE_MOUNT",
            "STRUCT_PELVIS_REAR_SADDLE",
            "STRUCT_PELVIS_L+STRUCT_PELVIS_R",
            (
                ("M6 x 170 mm bolt + washers + nyloc nut", 4),
                (
                    "3 mm steel two-hole backing plate, 50 x 40 mm minimum; install 50 mm horizontal and 40 mm vertical; drill the 20 mm vertical modeled row",
                    2,
                ),
            ),
            "Use only the modeled saddle rows; place one drilled two-hole steel load-spreader plate under each pair of accessible front-face nuts, with its 50 mm dimension horizontal and 40 mm dimension vertical.",
        )

    pelvis_stack_top_z = (
        pelvis_center_z + pelvis_thickness * 0.5 + lap_thickness
    )
    spine_start = Vector((0.0, 0.0, pelvis_stack_top_z + 40.0))
    spine_end = Vector((0.0, 0.0, 1345.0 * s - 40.0))
    spine_anchor = build_anchor_bracket("STRUCT_SPINE_BASE_BRACKET")
    spine_anchor.matrix_world = frame_between(spine_start, spine_end, (1.0, 0.0, 0.0))
    spine_anchor.matrix_world.translation = spine_start
    pelvis_stack_height = pelvis_thickness + 2.0 * lap_thickness
    spine_mount_cutter_depth = 2.0 * (
        pelvis_stack_height + CFG.anchor_base_thickness * 0.5 + 3.0
    )
    cut_bracket_mount_pattern(
        bpy.data.objects["STRUCT_PELVIS_LAP_TOP"],
        spine_anchor,
        -1.0,
        spine_mount_cutter_depth,
    )
    for pelvis_stack_id in (
        "STRUCT_PELVIS_L",
        "STRUCT_PELVIS_R",
        "STRUCT_PELVIS_LAP_BOTTOM",
    ):
        cut_bracket_mount_pattern(
            bpy.data.objects[pelvis_stack_id],
            spine_anchor,
            -1.0,
            spine_mount_cutter_depth,
            register_contact_check=False,
        )
    spine_mount_holes = tuple(
        spine_anchor.matrix_world @ Vector(coordinates)
        for coordinates in spine_anchor["mount_holes_local"]
    )
    for pelvis_stack_id in (
        "STRUCT_PELVIS_LAP_TOP",
        "STRUCT_PELVIS_L",
        "STRUCT_PELVIS_R",
        "STRUCT_PELVIS_LAP_BOTTOM",
    ):
        register_horizontal_bore_face_checks(
            bpy.data.objects[pelvis_stack_id],
            spine_mount_holes,
            minimum_radius=2.5,
            maximum_radius=3.5,
            label=f"SPINE_BASE_BRACKET_MOUNT/{pelvis_stack_id}",
        )
    register_part(
        "STRUCT_SPINE_BASE_BRACKET",
        spine_anchor,
        "01_STRUCTURE_PETG_ABS",
        CFG.rigid_material,
        "Print base-down with 6+ walls.",
        "Through-bolt to the modeled top lap-plate pedestal and capture the first spine link.",
        "4 x M5 x 90 mm fully threaded ISO 4017 / DIN 933 bolts plus "
        + CFG.pivot_bolt,
    )
    spine = build_link_chain("STRUCT_SPINE", spine_start, spine_end, (1.0, 0.0, 0.0))
    register_anchor_joint(
        "SPINE_BASE_PIVOT",
        "STRUCT_SPINE_BASE_BRACKET",
        spine_anchor.matrix_world,
        spine,
        at_chain_start=True,
        locked=True,
    )
    register_connection(
        "SPINE_BASE_BRACKET_MOUNT",
        "STRUCT_PELVIS_LAP_TOP+STRUCT_PELVIS_L+STRUCT_PELVIS_R+STRUCT_PELVIS_LAP_BOTTOM",
        "STRUCT_SPINE_BASE_BRACKET.BASE",
        (("M5 x 90 mm fully threaded ISO 4017 / DIN 933 bolt + fender washers + nyloc nut", 4),),
        "Use the four coaxial holes through the bracket, both pelvis halves, and both lap plates; nuts remain accessible below the bottom lap.",
    )
    spine_top_anchor = build_anchor_bracket(
        "STRUCT_SPINE_TOP_BRACKET",
        terminal_type="MALE",
        base_side=1.0,
    )
    spine_top_anchor.matrix_world = frame_between(
        spine_start,
        spine_end,
        (1.0, 0.0, 0.0),
    )
    spine_top_anchor.matrix_world.translation = spine_end
    register_part(
        "STRUCT_SPINE_TOP_BRACKET",
        spine_top_anchor,
        "01_STRUCTURE_PETG_ABS",
        CFG.rigid_material,
        "Print base-down with 6+ walls and 35% gyroid infill.",
        "Bolt through the shoulder-center bridge; its MALE lug captures the final spine FEMALE clevis.",
        "4 shared M5 x 60 mm bolts plus " + CFG.pivot_bolt,
    )
    register_anchor_joint(
        "SPINE_TOP_PIVOT",
        "STRUCT_SPINE_TOP_BRACKET",
        spine_top_anchor.matrix_world,
        spine,
        at_chain_start=False,
        locked=True,
    )

    # Three-piece shoulder bridge: a fixed bed-safe center and two wings whose
    # outer edges follow the configured real-gear shoulder width.
    shoulder_center_z = 1355.0 * s
    shoulder_wing_z = 1375.0 * s
    shoulder_bridge_depth = max(150.0, 140.0 * s)
    center = build_bolted_panel(
        "STRUCT_SHOULDER_CENTER",
        (220.0, shoulder_bridge_depth, 20.0 * s),
        ((-95.0, -25.0 * s), (-95.0, 25.0 * s),
         (95.0, -25.0 * s), (95.0, 25.0 * s)),
        bevel=8.0,
    )
    center.location = (0.0, 0.0, shoulder_center_z)
    cut_bracket_mount_pattern(
        center,
        spine_top_anchor,
        1.0,
        80.0 * s,
    )
    register_part(
        "STRUCT_SHOULDER_CENTER",
        center,
        "01_STRUCTURE_PETG_ABS",
        CFG.rigid_material,
        "Print flat; use 6+ walls and 35% gyroid infill.",
        "Clamp the spine-top and neck-base brackets to opposite faces with four shared bolts. Stack each 25 mm wing lap on the top face using the coaxial hole pair.",
        "4 x M6 x 60 mm wing-lap bolts; 4 shared M5 x 60 mm vertical-bracket bolts",
    )
    for side_name, side_sign in (("L", -1.0), ("R", 1.0)):
        wing_id = f"STRUCT_SHOULDER_WING_{side_name}"
        inner_edge = 85.0
        outer_edge = structural_shoulder_half_width() + 20.0
        wing_width = outer_edge - inner_edge
        wing_center_x = side_sign * (inner_edge + outer_edge) * 0.5
        inner_hole_global_x = side_sign * 95.0
        inner_hole_local_x = inner_hole_global_x - wing_center_x
        wing = build_bolted_panel(
            wing_id,
            (wing_width, shoulder_bridge_depth, 20.0 * s),
            ((inner_hole_local_x, -25.0 * s),
             (inner_hole_local_x, 25.0 * s)),
            bevel=8.0,
        )
        wing.location = (wing_center_x, 0.0, shoulder_wing_z)
        register_part(
            wing_id,
            wing,
            "01_STRUCTURE_PETG_ABS",
            CFG.rigid_material,
            "Print flat; use 6+ walls and 35% gyroid infill.",
            "Stack the inner 25 mm lap on the center bridge; the hole pair is coaxial. The outer edge and wedge follow the larger structural span derived from shoulder width and chest clearance.",
            "2 x M6 x 60 mm lap bolts; shoulder hardware in goalie_connections.csv",
        )
        register_connection(
            f"SHOULDER_{side_name}_WING_LAP",
            "STRUCT_SHOULDER_CENTER",
            wing_id,
            (("M6 x 60 mm bolt + 2 washers + nyloc nut", 2),),
            "Stack the 20 mm wing above the 20 mm center bridge and align the modeled lap bores.",
        )

    if CFG.generate_body_shell:
        torso_panels: list[
            tuple[str, tuple[float, float, float], tuple[float, float, float], str]
        ] = []
        for level_name, width, depth, z in (
            ("LOWER", CFG.waist_width_mm, CFG.waist_depth_mm, 1055.0 * s),
            ("UPPER", CFG.chest_width_mm, CFG.chest_depth_mm, 1238.0 * s),
        ):
            face_panel_width = width * 0.5 - 4.0
            face_center_x = width * 0.25 + 2.0
            for face_name, face_sign in (("FRONT", 1.0), ("BACK", -1.0)):
                for side_name, side_sign in (("L", -1.0), ("R", 1.0)):
                    torso_panels.append(
                        (
                            f"BODY_TORSO_{face_name}_{side_name}_{level_name}",
                            (face_panel_width, 16.0, 178.0 * s),
                            (side_sign * face_center_x, face_sign * depth * 0.5, z),
                            "Y",
                        )
                    )
            for side_name, side_sign in (("L", -1.0), ("R", 1.0)):
                side_height = (120.0 if level_name == "UPPER" else 178.0) * s
                # Preserve the upper side panel's lower edge while lowering
                # only its top edge to form a deliberate armpit relief around
                # the rigid shoulder wedge/bracket stack.
                side_z = (1209.0 if level_name == "UPPER" else 1055.0) * s
                torso_panels.append(
                    (
                        f"BODY_TORSO_SIDE_{side_name}_{level_name}",
                        (16.0, depth - 16.0, side_height),
                        (side_sign * width * 0.5, 0.0, side_z),
                        "X",
                    )
                )
        for part_id, dimensions, location, through_axis in torso_panels:
            panel = add_box(part_id, dimensions, bevel=7.0 * s)
            if through_axis == "Y":
                add_edge_lace_holes(
                    panel,
                    part_id,
                    dimensions[0],
                    dimensions[2],
                    dimensions[1],
                    "Y",
                )
            else:
                add_edge_lace_holes(
                    panel,
                    part_id,
                    dimensions[1],
                    dimensions[2],
                    dimensions[0],
                    "X",
                )
            panel.location = location
            register_part(
                part_id,
                panel,
                "02_BODY_FORMS_TPU",
                CFG.flexible_material,
                "Print on the broad face with 4 walls and 10% gyroid infill.",
                "Lace the modeled reinforced edge holes to neighboring panels; leave room for torso flex.",
                CFG.panel_fastener,
                "Dressing/fit surface only; not impact protection.",
            )
    return {"SPINE": spine}


def build_upper_body() -> dict[str, list[ChainPart]]:
    chains: dict[str, list[ChainPart]] = {}
    s = CFG.body_scale
    shoulder_half = structural_shoulder_half_width()
    arm_points = {
        "L": (
            Vector((-shoulder_half, 15.0 * s, 1365.0 * s)),
            Vector((-shoulder_half - 135.0 * s, 105.0 * s, 1160.0 * s)),
            Vector((-shoulder_half - 220.0 * s, 210.0 * s, 1005.0 * s)),
        ),
        "R": (
            Vector((shoulder_half, 15.0 * s, 1365.0 * s)),
            Vector((shoulder_half + 135.0 * s, 105.0 * s, 1160.0 * s)),
            Vector((shoulder_half + 220.0 * s, 210.0 * s, 1005.0 * s)),
        ),
    }
    for side_name, (shoulder, elbow, wrist) in arm_points.items():
        # Keep shoulder, elbow, wrist, and palm in one plane.  One unchanged
        # plane normal then becomes the real shared M8 pivot axis at every arm
        # joint instead of being projected to slightly different axes.
        upper_direction = elbow - shoulder
        forearm_direction = wrist - elbow
        for _ in range(8):
            plane_normal = (elbow - shoulder).cross(forearm_direction).normalized()
            updated_shoulder = align_start_anchor_below_horizontal_land(
                shoulder,
                elbow,
                plane_normal,
                1365.0 * s,
            )
            if (updated_shoulder - shoulder).length < 0.001:
                shoulder = updated_shoulder
                break
            shoulder = updated_shoulder
        upper_direction = elbow - shoulder
        plane_normal = upper_direction.cross(forearm_direction).normalized()
        palm = wrist + forearm_direction.normalized() * (95.0 * s)
        upper = build_link_chain(
            f"STRUCT_{side_name}_UPPER_ARM", shoulder, elbow, plane_normal
        )
        forearm = build_link_chain(
            f"STRUCT_{side_name}_FOREARM", elbow, wrist, plane_normal
        )
        hand = build_link_chain(
            f"STRUCT_{side_name}_HAND", wrist, palm, plane_normal
        )
        chains[f"{side_name}_UPPER_ARM"] = upper
        chains[f"{side_name}_FOREARM"] = forearm
        chains[f"{side_name}_HAND"] = hand

        bracket = build_anchor_bracket(f"STRUCT_{side_name}_SHOULDER_BRACKET")
        bracket.matrix_world = frame_between(shoulder, elbow, plane_normal)
        bracket.matrix_world.translation = shoulder
        shoulder_target = bpy.data.objects[f"STRUCT_SHOULDER_WING_{side_name}"]
        shoulder_wedge_id = f"STRUCT_{side_name}_SHOULDER_WEDGE"
        shoulder_wedge, shoulder_bolt_hardware, shoulder_bolt_mapping = (
            build_mating_wedge_and_mount_pattern(
            shoulder_wedge_id,
            shoulder_target,
            bracket,
            -1.0,
            cutter_depth=90.0 * s,
            target_surface_z=1365.0 * s,
            target_panel_thickness=20.0 * s,
            wedge_world_z_sign=-1.0,
            )
        )
        register_part(
            shoulder_wedge_id,
            shoulder_wedge,
            "01_STRUCTURE_PETG_ABS",
            CFG.rigid_material,
            "Print on the 68 x 54 mm angled-bracket face with 6+ walls and 40% gyroid infill.",
            "Place the horizontal face against the shoulder-wing underside and the angled face against the shoulder bracket; align all four modeled bores.",
            "Shares the four configuration-derived M5 shoulder-mount bolts",
        )
        register_part(
            f"STRUCT_{side_name}_SHOULDER_BRACKET",
            bracket,
            "01_STRUCTURE_PETG_ABS",
            CFG.rigid_material,
            "Print base-down with 6+ walls and 35% gyroid infill.",
            "Bolt to the shoulder wing and capture the first upper-arm MALE lug.",
            "4 x M5 bolts plus " + CFG.pivot_bolt,
        )
        register_anchor_joint(
            f"{side_name}_SHOULDER_PIVOT",
            f"STRUCT_{side_name}_SHOULDER_BRACKET",
            bracket.matrix_world,
            upper,
            at_chain_start=True,
            locked=True,
        )
        register_chain_joint(f"{side_name}_ELBOW_PIVOT", upper, forearm)
        register_chain_joint(f"{side_name}_WRIST_PIVOT", forearm, hand)
        register_connection(
            f"{side_name}_SHOULDER_BRACKET_MOUNT",
            f"STRUCT_SHOULDER_WING_{side_name}+{shoulder_wedge_id}",
            f"STRUCT_{side_name}_SHOULDER_BRACKET.BASE",
            shoulder_bolt_hardware,
            "Through-bolt the bracket, separate full-area wedge, and shoulder wing using the modeled coaxial pattern; use washers at both printed outer faces. On the terminal-facing bracket face, shallow dot groups identify each hole. Marked-hole bolt map: "
            + shoulder_bolt_mapping,
        )
        if CFG.generate_body_shell:
            torso_side = bpy.data.objects[
                f"BODY_TORSO_SIDE_{side_name}_UPPER"
            ]
            for rigid_neighbor, label in (
                (bracket, "shoulder bracket"),
                (shoulder_wedge, "shoulder wedge"),
                (upper[0].record.obj, "first upper-arm link"),
            ):
                CLEARANCE_CHECKS.append(
                    (
                        rigid_neighbor,
                        torso_side,
                        Vector((0.0, 0.0, 0.0)),
                        f"{rigid_neighbor.name}/{torso_side.name} ({label})",
                    )
                )

        palm_anchor_id = f"STRUCT_{side_name}_PALM_BRACKET"
        palm_anchor = build_anchor_bracket(
            palm_anchor_id,
            terminal_type="MALE",
            base_side=1.0,
        )
        palm_anchor.matrix_world = frame_between(wrist, palm, plane_normal)
        palm_anchor.matrix_world.translation = palm
        register_part(
            palm_anchor_id,
            palm_anchor,
            "01_STRUCTURE_PETG_ABS",
            CFG.rigid_material,
            "Print base-down with 6+ walls and 30% gyroid infill.",
            "Capture the hand link's final FEMALE clevis; "
            + ("bolt through the TPU hand clamshells with broad washers." if CFG.generate_body_shell else "use the four-hole base as the direct real-gear strap adapter."),
            "4 x M5 bolts, fender washers, plus " + CFG.pivot_bolt,
        )
        register_anchor_joint(
            f"{side_name}_PALM_PIVOT",
            palm_anchor_id,
            palm_anchor.matrix_world,
            hand,
            at_chain_start=False,
            locked=True,
        )
        if CFG.generate_body_shell:
            register_connection(
                f"{side_name}_PALM_FORM_MOUNT",
                palm_anchor_id + ".BASE",
                f"BODY_{side_name}_HAND_FORM_FRONT+BODY_{side_name}_HAND_FORM_REAR",
                (("M5 x 45 mm bolt + 2 fender washers + nyloc nut", 4),),
                "Use the four coaxial palm-end holes (two per TPU clamshell) with fender washers after lacing the halves around the hand link.",
            )

        if CFG.generate_body_shell:
            upper_arm_radius = (
                CFG.upper_arm_circumference_mm / math.tau + CFG.gear_clearance_mm
            )
            forearm_radius = (
                CFG.forearm_circumference_mm / math.tau + CFG.gear_clearance_mm
            )
            build_chain_sleeves(
                f"BODY_{side_name}_UPPER_ARM_SLEEVE",
                upper,
                (upper_arm_radius, upper_arm_radius * 0.91),
                (upper_arm_radius * 0.79, upper_arm_radius * 0.72),
            )
            forearm_sleeves = build_chain_sleeves(
                f"BODY_{side_name}_FOREARM_SLEEVE",
                forearm,
                (forearm_radius, forearm_radius * 0.91),
                (forearm_radius * 0.74, forearm_radius * 0.68),
            )
            # Preserve at least a 5 mm TPU border around the 68 x 54 mm palm
            # bracket even at the allowed minimum hand/clearance settings.
            # This also leaves the 32 x 44 mm rigid link inside two 4 mm walls.
            hand_form_width, hand_form_depth = derived_hand_form_width_depth()
            hand_dimensions = (
                hand_form_width,
                hand_form_depth,
                # The wrist-open tray starts exactly at the wrist and ends
                # 44 mm beyond the palm pivot.  Its distal inner end-wall
                # surface is therefore the palm bracket's +40 mm contact face.
                hand[-1].length + 44.0,
            )
            for half_name, half_sign in (("FRONT", 1.0), ("REAR", -1.0)):
                hand_shell_id = f"BODY_{side_name}_HAND_FORM_{half_name}"
                hand_shell = add_open_box_half(
                    hand_shell_id,
                    hand_dimensions,
                    4.0,
                    half_sign,
                    open_negative_z=True,
                )
                add_edge_lace_holes(
                    hand_shell,
                    hand_shell_id,
                    hand_dimensions[0],
                    hand_dimensions[2],
                    hand_dimensions[1],
                    "Y",
                    rows=3,
                )
                # With the shortened asymmetric height, +22 mm puts the open
                # proximal rim at the wrist and preserves the distal mount web
                # at the palm bracket.  Bake this offset before posing.
                hand_shell.location.z = 22.0
                apply_object_transform(
                    hand_shell,
                    location=True,
                    rotation=False,
                    scale=False,
                )
                hand_shell.matrix_world = hand[-1].matrix
                # Preserve a 3.95 mm reinforced TPU end wall while trimming
                # bevel spill from the bracket side of its bearing plane.
                # This produces a real planar bracket/web interface instead
                # of relying on nominal tray dimensions alone.
                clip_mount_face_clearance(
                    hand_shell,
                    palm_anchor,
                    1.0,
                    # Only clear the actual 68 x 54 x 12 mm bracket plate.
                    # The small allowances remove Boolean/bevel spill without
                    # cutting into unrelated distal tray walls.
                    (68.4, 54.4, 12.15),
                )
                cut_bracket_mount_pattern(
                    hand_shell,
                    palm_anchor,
                    1.0,
                    70.0,
                )
                shell_record = register_part(
                    hand_shell_id,
                    hand_shell,
                    "02_BODY_FORMS_TPU",
                    CFG.flexible_material,
                    "Print cavity-up with the wrist opening unobstructed, 4 walls, and no trapped support.",
                    "Slide the wrist-open halves around the hand link, then lace them; the modeled distal holes align with the rigid palm bracket.",
                    "4 mm shock cord and 2 shared M5 palm bolts per half",
                    "Dressing form only; not hand protection.",
                )
                for neighbor, neighbor_label in (
                    (hand[-1].record.obj, "hand link"),
                    (forearm[-1].record.obj, "final forearm link"),
                    (forearm_sleeves[-2].obj, "final forearm sleeve front"),
                    (forearm_sleeves[-1].obj, "final forearm sleeve rear"),
                ):
                    CLEARANCE_CHECKS.append(
                        (
                            hand_shell,
                            neighbor,
                            Vector((0.0, 0.0, 0.0)),
                            f"{hand_shell.name}/{neighbor.name} ({neighbor_label})",
                        )
                    )
                if half_name == "FRONT":
                    front_hand_shell = shell_record.obj
                else:
                    CLAMSHELL_PAIR_CHECKS.append(
                        (front_hand_shell, shell_record.obj)
                    )
    return chains


def build_head_and_neck() -> dict[str, list[ChainPart]]:
    neck_start = Vector((0.0, 0.0, 1365.0 * CFG.body_scale + 40.0))
    neck_end = scaled((0.0, 0.0, 1510.0))
    neck_anchor = build_anchor_bracket("STRUCT_NECK_BASE_BRACKET")
    neck_anchor.matrix_world = frame_between(neck_start, neck_end, (1.0, 0.0, 0.0))
    neck_anchor.matrix_world.translation = neck_start
    cut_bracket_mount_pattern(
        bpy.data.objects["STRUCT_SHOULDER_CENTER"],
        neck_anchor,
        -1.0,
        80.0 * CFG.body_scale,
    )
    register_part(
        "STRUCT_NECK_BASE_BRACKET",
        neck_anchor,
        "01_STRUCTURE_PETG_ABS",
        CFG.rigid_material,
        "Print base-down with 6+ walls.",
        "Bolt to the shoulder-center plate and capture the first neck link.",
        "4 shared M5 x 60 mm bolts plus " + CFG.pivot_bolt,
    )
    neck = build_link_chain("STRUCT_NECK", neck_start, neck_end, (1.0, 0.0, 0.0))
    register_anchor_joint(
        "NECK_BASE_PIVOT",
        "STRUCT_NECK_BASE_BRACKET",
        neck_anchor.matrix_world,
        neck,
        at_chain_start=True,
        locked=True,
    )
    register_connection(
        "SHOULDER_CENTER_VERTICAL_BRACKET_STACK",
        "STRUCT_SPINE_TOP_BRACKET.BASE+STRUCT_SHOULDER_CENTER",
        "STRUCT_NECK_BASE_BRACKET.BASE",
        (("M5 x 60 mm bolt + fender washers + nyloc nut", 4),),
        "Use four shared bolts through the lower spine bracket, shoulder center, and upper neck bracket; do not try to install two nuts in each coaxial bore.",
    )
    head_anchor = build_anchor_bracket(
        "STRUCT_HEAD_CORE_BRACKET",
        terminal_type="MALE",
        base_side=1.0,
    )
    head_anchor.matrix_world = frame_between(neck_start, neck_end, (1.0, 0.0, 0.0))
    head_anchor.matrix_world.translation = neck_end
    register_part(
        "STRUCT_HEAD_CORE_BRACKET",
        head_anchor,
        "01_STRUCTURE_PETG_ABS",
        CFG.rigid_material,
        "Print base-down with 6+ walls and 30% gyroid infill.",
        "Capture the final neck FEMALE clevis; "
        + ("the base carries the laced TPU head forms with broad washers." if CFG.generate_body_shell else "the base is a direct certified-mask fit reference only."),
        "4 x M5 bolts, fender washers, plus " + CFG.pivot_bolt,
    )
    register_anchor_joint(
        "HEAD_CORE_PIVOT",
        "STRUCT_HEAD_CORE_BRACKET",
        head_anchor.matrix_world,
        neck,
        at_chain_start=False,
        locked=True,
    )

    if CFG.generate_body_shell:
        s = CFG.body_scale
        head_radius_x = CFG.head_width_mm * 0.5 + CFG.gear_clearance_mm
        head_radius_y = CFG.head_depth_mm * 0.5 + CFG.gear_clearance_mm
        lower = add_open_elliptical_sleeve(
            "BODY_HEAD_LOWER",
            (head_radius_x * 0.95, head_radius_y * 0.94),
            (head_radius_x, head_radius_y),
            88.0 * s,
            4.0,
        )
        add_head_seam_holes(
            lower,
            "BODY_HEAD_LOWER",
            head_radius_x * 2.0,
            head_radius_y * 2.0,
            88.0 * s,
        )
        lower_center_z = 1535.0 * s
        bracket_contact_z = neck_end.z + (
            CFG.anchor_base_center + CFG.anchor_base_thickness * 0.5
        )
        add_head_mount_web(
            lower,
            head_radius_x,
            head_radius_y,
            bracket_contact_z - lower_center_z + 4.0,
        )
        lower.location = scaled((0.0, 0.0, 1535.0))
        cut_bracket_mount_pattern(
            lower,
            head_anchor,
            1.0,
            40.0,
        )
        register_part(
            "BODY_HEAD_LOWER",
            lower,
            "02_BODY_FORMS_TPU",
            CFG.flexible_material,
            "Print upright with 4 walls; the open ends reduce support.",
            "Slide over the neck core, bolt the modeled internal web to the head bracket, and lace to the upper head shell.",
            "4 x M5 x 45 mm bolts with fender washers; 4 mm shock cord",
            "Head dressing form only; not a helmet or mask.",
        )
        register_connection(
            "HEAD_FORM_MOUNT",
            "STRUCT_HEAD_CORE_BRACKET.BASE",
            "BODY_HEAD_LOWER",
            (("M5 x 45 mm bolt + 2 fender washers + nyloc nut", 4),),
            "Fasten the lower ring's reinforced internal web to the core bracket with broad washers, then lace on the upper ring.",
        )
        upper = add_open_elliptical_sleeve(
            "BODY_HEAD_UPPER",
            (head_radius_x, head_radius_y),
            (head_radius_x * 0.73, head_radius_y * 0.73),
            92.0 * s,
            4.0,
        )
        add_head_seam_holes(
            upper,
            "BODY_HEAD_UPPER",
            head_radius_x * 2.0,
            head_radius_y * 2.0,
            92.0 * s,
        )
        upper.location = scaled((0.0, 0.0, 1625.0))
        register_part(
            "BODY_HEAD_UPPER",
            upper,
            "02_BODY_FORMS_TPU",
            CFG.flexible_material,
            "Print upright; bridge or add a separate foam crown rather than closing the top in the slicer.",
            "Lace to the lower head shell and use only for fitting a real certified goalie mask.",
            CFG.panel_fastener,
            "Head dressing form only; not a helmet or mask.",
        )
    return {"NECK": neck}


# ---------------------------------------------------------------------------
# OPTIONAL DISPLAY-ONLY GOALIE GEAR


DISPLAY_GEAR_WARNING = (
    "DISPLAY/COSTUME ONLY. Printed goalie gear is not certified protective "
    "equipment and must never be worn for play, practice, or impact testing."
)


def ellipse_perimeter_mm(radius_x: float, radius_y: float) -> float:
    """Ramanujan perimeter approximation for a dressed sleeve section."""
    return math.pi * (
        3.0 * (radius_x + radius_y)
        - math.sqrt(
            (3.0 * radius_x + radius_y)
            * (radius_x + 3.0 * radius_y)
        )
    )


LEG_PAD_SADDLE_CONTACT_GAP_MM = 0.4


def add_leg_pad_saddle_rails(
    panel: bpy.types.Object,
    name: str,
    panel_width: float,
    panel_depth: float,
    panel_offset_y: float,
    sleeve_bottom: tuple[float, float],
    sleeve_top: tuple[float, float],
    sleeve_height: float,
) -> tuple[tuple[Vector, ...], float, float]:
    """Add two broad rear lands that stop pad straps short of rod hardware."""
    rail_height = min(80.0, sleeve_height * 0.65)
    maximum_radius_x = max(sleeve_bottom[0], sleeve_top[0])
    lace_row_z_values = (
        -sleeve_height * 0.5 + 10.0,
        0.0,
        sleeve_height * 0.5 - 10.0,
    )
    lace_center_x_values = []
    for lace_z in lace_row_z_values:
        interpolation = lace_z / sleeve_height + 0.5
        radius_x = (
            sleeve_bottom[0]
            + (sleeve_top[0] - sleeve_bottom[0]) * interpolation
        )
        lace_center_x_values.append(max(6.0, radius_x - 6.0))
    nearest_lace_center_x = min(lace_center_x_values)
    minimum_side_clearance = 2.25
    usable_inner_x = SLEEVE_HARDWARE_MAX_RADIUS_MM + minimum_side_clearance
    usable_outer_x = (
        nearest_lace_center_x
        - SLEEVE_LACE_BORE_RADIUS_MM
        - minimum_side_clearance
    )
    available_width = usable_outer_x - usable_inner_x
    if available_width < 6.5:
        raise ValueError(
            f"{name}: only {available_width:.3f} mm remains between the "
            "sleeve hardware and seam-lacing envelopes"
        )
    # Use the full 14 mm land where possible. At the allowed smallest calf,
    # narrow it only enough to keep 2 mm of free space beside both the 20 mm
    # washer/cap stack and the installed 4 mm seam cord.
    rail_width = min(14.0, available_width - 0.5)
    half_rail_width = rail_width * 0.5
    minimum_center_x = usable_inner_x + half_rail_width
    maximum_center_x = usable_outer_x - half_rail_width
    desired_center_x = min(panel_width * 0.30, maximum_radius_x * 0.45)
    rail_center_x = min(
        max(desired_center_x, minimum_center_x),
        maximum_center_x,
    )
    hardware_lateral_clearance = (
        rail_center_x - half_rail_width - SLEEVE_HARDWARE_MAX_RADIUS_MM
    )
    lace_lateral_clearance = (
        nearest_lace_center_x
        - SLEEVE_LACE_BORE_RADIUS_MM
        - (rail_center_x + half_rail_width)
    )
    panel_land_y = -panel_depth * 0.5 + 1.5
    rails: list[bpy.types.Object] = []
    distal_samples: list[Vector] = []

    def sleeve_surface_y(x: float, z: float) -> float:
        interpolation = z / sleeve_height + 0.5
        radius_x = (
            sleeve_bottom[0]
            + (sleeve_top[0] - sleeve_bottom[0]) * interpolation
        )
        radius_y = (
            sleeve_bottom[1]
            + (sleeve_top[1] - sleeve_bottom[1]) * interpolation
        )
        radial_fraction = min(0.999, abs(x) / radius_x)
        return radius_y * math.sqrt(1.0 - radial_fraction * radial_fraction)

    for side_name, side_sign in (("L", -1.0), ("R", 1.0)):
        x0 = side_sign * rail_center_x - rail_width * 0.5
        x1 = side_sign * rail_center_x + rail_width * 0.5
        x_low, x_high = sorted((x0, x1))
        z_low = -rail_height * 0.5
        z_high = rail_height * 0.5
        subdivisions = 4
        x_values = tuple(
            x_low + (x_high - x_low) * index / subdivisions
            for index in range(subdivisions + 1)
        )
        z_values = tuple(
            z_low + (z_high - z_low) * index / subdivisions
            for index in range(subdivisions + 1)
        )
        distal = tuple(
            Vector(
                (
                    x,
                    sleeve_surface_y(x, z)
                    - panel_offset_y
                    + LEG_PAD_SADDLE_CONTACT_GAP_MM,
                    z,
                )
            )
            for z in z_values
            for x in x_values
        )
        grid_width = subdivisions + 1
        grid_size = grid_width * grid_width
        vertices = [
            (x, panel_land_y, z)
            for z in z_values
            for x in x_values
        ]
        vertices.extend(tuple(point) for point in distal)
        faces: list[tuple[int, ...]] = []

        def grid_index(layer: int, z_index: int, x_index: int) -> int:
            return layer * grid_size + z_index * grid_width + x_index

        for z_index in range(subdivisions):
            for x_index in range(subdivisions):
                p00 = grid_index(0, z_index, x_index)
                p10 = grid_index(0, z_index, x_index + 1)
                p11 = grid_index(0, z_index + 1, x_index + 1)
                p01 = grid_index(0, z_index + 1, x_index)
                d00 = grid_index(1, z_index, x_index)
                d10 = grid_index(1, z_index, x_index + 1)
                d11 = grid_index(1, z_index + 1, x_index + 1)
                d01 = grid_index(1, z_index + 1, x_index)
                faces.append((p00, p01, p11, p10))
                faces.append((d00, d10, d11, d01))
        for index in range(subdivisions):
            # Bottom and top edge strips.
            faces.append(
                (
                    grid_index(0, 0, index),
                    grid_index(0, 0, index + 1),
                    grid_index(1, 0, index + 1),
                    grid_index(1, 0, index),
                )
            )
            faces.append(
                (
                    grid_index(0, subdivisions, index + 1),
                    grid_index(0, subdivisions, index),
                    grid_index(1, subdivisions, index),
                    grid_index(1, subdivisions, index + 1),
                )
            )
            # Left and right edge strips.
            faces.append(
                (
                    grid_index(0, index + 1, 0),
                    grid_index(0, index, 0),
                    grid_index(1, index, 0),
                    grid_index(1, index + 1, 0),
                )
            )
            faces.append(
                (
                    grid_index(0, index, subdivisions),
                    grid_index(0, index + 1, subdivisions),
                    grid_index(1, index + 1, subdivisions),
                    grid_index(1, index, subdivisions),
                )
            )
        mesh = bpy.data.meshes.new(f"{name}_Saddle_Rail_{side_name}_Mesh")
        mesh.from_pydata(vertices, [], faces)
        mesh.validate(clean_customdata=True)
        mesh.update()
        rail = bpy.data.objects.new(f"{name}_Saddle_Rail_{side_name}", mesh)
        bpy.context.collection.objects.link(rail)
        recalc_normals(rail)
        rails.append(rail)
        distal_samples.extend(distal)

    union_many(panel, rails, name + "_Saddle_Rails_Union")
    return (
        tuple(distal_samples),
        hardware_lateral_clearance,
        lace_lateral_clearance,
    )


def add_strap_slots(
    panel: bpy.types.Object,
    name: str,
    width: float,
    height: float,
    depth: float,
) -> bpy.types.Object:
    # Two horizontal capsule-like slots made as rounded boxes.  The slots are
    # deliberately well inside the panel boundary for TPU tear resistance.
    for index, z in enumerate((-height * 0.34, height * 0.34), start=1):
        cutter = add_box(
            f"{name}_Strap_Slot_{index}",
            (min(34.0, width * 0.28), depth + 6.0, 6.0),
            (0.0, 0.0, z),
            bevel=3.0,
        )
        boolean_apply(panel, cutter, "DIFFERENCE", f"{name}_Strap_Cut_{index}")
    return panel


def build_leg_pad_gear(lower_chains: dict[str, list[ChainPart]]) -> None:
    for side_name in ("L", "R"):
        # Three shin modules and the two links nearest the knee on the thigh.
        candidates = list(lower_chains[f"{side_name}_SHIN"])
        thigh = lower_chains[f"{side_name}_THIGH"]
        candidates.extend(reversed(thigh[-2:]))
        for index, link in enumerate(candidates, start=1):
            part_id = f"GEAR_{side_name}_LEG_PAD_PANEL_{index:02d}"
            link_number = link.record.part_id.rsplit("_", 1)[-1]
            link_index = int(link_number)
            if "_SHIN_" in link.record.part_id:
                sleeve_root = f"BODY_{side_name}_CALF_SLEEVE_{link_number}"
                sleeve_chain = lower_chains[f"{side_name}_SHIN"]
                base_radius = (
                    CFG.calf_circumference_mm / math.tau
                    + CFG.gear_clearance_mm
                )
                sleeve_start_y = base_radius * 0.94
                sleeve_end_y = base_radius * 0.67
                sleeve_start_x = base_radius
                sleeve_end_x = base_radius * 0.73
            else:
                sleeve_root = f"BODY_{side_name}_THIGH_SLEEVE_{link_number}"
                sleeve_chain = lower_chains[f"{side_name}_THIGH"]
                base_radius = (
                    CFG.thigh_circumference_mm / math.tau
                    + CFG.gear_clearance_mm
                )
                sleeve_start_y = base_radius * 0.86
                sleeve_end_y = base_radius * 0.65
                sleeve_start_x = base_radius
                sleeve_end_x = base_radius * 0.72
            t0 = (link_index - 1) / len(sleeve_chain)
            t1 = link_index / len(sleeve_chain)
            sleeve_bottom_y = (
                sleeve_start_y
                + (sleeve_end_y - sleeve_start_y) * t0
            )
            sleeve_top_y = (
                sleeve_start_y
                + (sleeve_end_y - sleeve_start_y) * t1
            )
            sleeve_bottom_x = (
                sleeve_start_x
                + (sleeve_end_x - sleeve_start_x) * t0
            )
            sleeve_top_x = (
                sleeve_start_x
                + (sleeve_end_x - sleeve_start_x) * t1
            )
            height = min(link.length - 10.0, 185.0)
            width = 148.0 * CFG.body_scale
            depth = 30.0
            rod_length = sleeve_mount_rod_length(
                sleeve_bottom_y,
                sleeve_top_y,
            )
            # Clear both the tapered TPU shell and the capped transverse rod.
            # The specified cap projection is reserved at each centered rod
            # end and a further 3 mm is deliberate pad-to-hardware air
            # clearance.  That gap also absorbs the permitted 0.5 mm front
            # bias when the two measured projections differ by at most 1 mm.
            front_hardware_envelope = max(
                sleeve_bottom_y,
                sleeve_top_y,
                rod_length * 0.5 + SLEEVE_ROD_CAP_PROJECTION_MM,
            )
            panel_offset_y = front_hardware_envelope + depth * 0.5 + 3.0
            sleeve_outer_x = max(sleeve_bottom_x, sleeve_top_x)
            sleeve_outer_y = max(sleeve_bottom_y, sleeve_top_y)
            panel_to_shell_gap = max(
                0.0,
                panel_offset_y - depth * 0.5 - sleeve_outer_y,
            )
            # Each loop includes the largest ellipse in this tapered link,
            # two panel-to-shell spans, two passes through the panel depth,
            # and 150 mm of usable hook/loop overlap. Round each cut upward.
            strap_cut_length = int(
                math.ceil(
                    (
                        ellipse_perimeter_mm(sleeve_outer_x, sleeve_outer_y)
                        + panel_to_shell_gap * 2.0
                        + depth * 2.0
                        + 150.0
                    )
                    / 10.0
                )
                * 10
            )
            DISPLAY_GEAR_STRAP_CUT_LENGTHS_MM.extend(
                (strap_cut_length, strap_cut_length)
            )
            panel = add_box(part_id, (width, depth, height), bevel=10.0)
            sleeve_length = max(
                45.0,
                link.length - CFG.lug_radius * 2.35,
            )
            (
                saddle_samples_local,
                saddle_hardware_lateral_clearance,
                saddle_lace_lateral_clearance,
            ) = add_leg_pad_saddle_rails(
                panel,
                part_id,
                width,
                depth,
                panel_offset_y,
                (sleeve_bottom_x, sleeve_bottom_y),
                (sleeve_top_x, sleeve_top_y),
                sleeve_length,
            )
            add_strap_slots(panel, part_id, width, height, depth)
            add_edge_lace_holes(panel, part_id, width, height, depth, "Y", rows=3)
            # Put the broad cosmetic/front face on the bed so both integral
            # rear saddle rails grow upward without support.
            panel["print_rotation_euler"] = [-math.pi * 0.5, 0.0, 0.0]
            # World +Y is the goalie-facing front.  In the generated leg
            # frames, +local Y has the forward component; -local Y incorrectly
            # places these modules behind the calf/thigh.
            panel.matrix_world = matrix_with_translation(
                link.matrix,
                (0.0, panel_offset_y, 0.0),
            )
            register_part(
                part_id,
                panel,
                "03_DISPLAY_GOALIE_GEAR_TPU",
                "TPU_95A_DISPLAY_GEAR",
                "Print flat on the broad front face with both integral rear saddle rails upward; use 4-5 walls and 12% gyroid infill.",
                "Lace adjacent modules with shock cord and route both modeled straps around the front-mounted matching TPU clamshell. Keep every seam-cord exit outside the saddle rails. Tighten only until both broad rear rails seat on the sleeve; the open center channel must remain clear of the capped through-rod hardware.",
                f"2 x 25 mm hook-and-loop straps cut to {strap_cut_length} mm; 4.8 mm reusable zip ties or 4 mm shock cord",
                DISPLAY_GEAR_WARNING,
            )
            register_connection(
                f"{part_id}_FRONT_STRAP_MOUNT",
                part_id,
                f"{sleeve_root}_FRONT+{sleeve_root}_REAR",
                ((f"25 mm hook-and-loop strap cut to {strap_cut_length} mm", 2),),
                f"Keep the pad panel on the goalie-facing world-+Y/front side. Center one {strap_cut_length} mm strap through each of the panel's two modeled slots (one strap per slot), wrap its two free ends in opposite directions around the directly through-bolted TPU clamshell, and overlap hook to loop on the rear. Confirm both sleeve seam-cord exits remain outside the adaptive-width rails. Tighten evenly only until both rear rails seat broadly on the sleeve; verify the open center channel does not touch the capped through-rod, and do not route the panel behind the calf.",
            )
            FRONT_GEAR_CHECKS.append(
                (
                    panel,
                    link.record.obj,
                    (link.matrix.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized(),
                    panel_offset_y,
                    f"{part_id}/{link.record.part_id}",
                )
            )
            CLEARANCE_CHECKS.append(
                (
                    panel,
                    bpy.data.objects[sleeve_root + "_FRONT"],
                    Vector((0.0, 0.0, 0.0)),
                    f"{part_id}/{sleeve_root}_FRONT pad clearance",
                )
            )
            PAD_SADDLE_CONTACT_CHECKS.append(
                (
                    panel,
                    bpy.data.objects[sleeve_root + "_FRONT"],
                    tuple(panel.matrix_world @ point for point in saddle_samples_local),
                    LEG_PAD_SADDLE_CONTACT_GAP_MM,
                    f"{part_id}/{sleeve_root}_FRONT saddle lands",
                )
            )
            hardware_clearance_at_land_contact = (
                panel_offset_y
                - depth * 0.5
                - LEG_PAD_SADDLE_CONTACT_GAP_MM
                - (
                    rod_length * 0.5
                    + SLEEVE_ROD_CAP_PROJECTION_MM
                    + SLEEVE_ROD_CENTER_TOLERANCE_MM * 0.5
                )
            )
            PAD_HARDWARE_CLEARANCE_CHECKS.append(
                (
                    hardware_clearance_at_land_contact,
                    f"{part_id} capped-rod channel at saddle contact",
                )
            )
            PAD_SADDLE_LATERAL_CLEARANCE_CHECKS.append(
                (
                    saddle_hardware_lateral_clearance,
                    saddle_lace_lateral_clearance,
                    f"{part_id} saddle-rail side corridor",
                )
            )


def build_chest_gear() -> None:
    s = CFG.body_scale
    panels = (
        ("GEAR_CHEST_CENTER_LOWER", (220.0, 28.0, 178.0), (0.0, 112.0, 1080.0)),
        ("GEAR_CHEST_CENTER_UPPER", (220.0, 28.0, 178.0), (0.0, 120.0, 1260.0)),
        ("GEAR_CHEST_WING_L", (112.0, 28.0, 178.0), (-165.0, 100.0, 1230.0)),
        ("GEAR_CHEST_WING_R", (112.0, 28.0, 178.0), (165.0, 100.0, 1230.0)),
        ("GEAR_SHOULDER_FLOAT_L", (172.0, 32.0, 105.0), (-220.0, 75.0, 1380.0)),
        ("GEAR_SHOULDER_FLOAT_R", (172.0, 32.0, 105.0), (220.0, 75.0, 1380.0)),
    )
    for part_id, raw_dimensions, raw_location in panels:
        dimensions = tuple(value * s for value in raw_dimensions)
        panel = add_box(part_id, dimensions, bevel=12.0 * s)
        add_strap_slots(panel, part_id, dimensions[0], dimensions[2], dimensions[1])
        add_edge_lace_holes(
            panel,
            part_id,
            dimensions[0],
            dimensions[2],
            dimensions[1],
            "Y",
            rows=3,
        )
        panel.location = scaled(raw_location)
        register_part(
            part_id,
            panel,
            "03_DISPLAY_GOALIE_GEAR_TPU",
            "TPU_95A_DISPLAY_GEAR",
            "Print flat on the rear face with 4-5 walls and 10-15% gyroid infill.",
            "Lace overlapping panels; attach around the body-form panels with shock cord, not rigid fasteners.",
            "4 mm shock cord or reusable zip ties",
            DISPLAY_GEAR_WARNING,
        )


def build_glove_gear(upper_chains: dict[str, list[ChainPart]]) -> None:
    # Conventional setup: catcher on mannequin left, blocker on right.
    left_hand = upper_chains["L_HAND"][-1]
    right_hand = upper_chains["R_HAND"][-1]

    catcher = add_cylinder("GEAR_CATCHER_PALM", 106.0, 18.0, axis="Y", vertices=64)
    catcher_bevel = catcher.modifiers.new("GEAR_CATCHER_EDGE_ROUND", "BEVEL")
    catcher_bevel.width = 5.0
    catcher_bevel.segments = 3
    select_only(catcher)
    bpy.ops.object.modifier_apply(modifier=catcher_bevel.name)
    cleanup_mesh(catcher)
    for index in range(12):
        angle = math.tau * index / 12.0
        cutter = add_cylinder(
            f"GEAR_CATCHER_RIM_LACE_HOLE_{index}",
            2.6,
            24.0,
            (82.0 * math.cos(angle), 0.0, 82.0 * math.sin(angle)),
            axis="Y",
            vertices=32,
        )
        boolean_apply(catcher, cutter, "DIFFERENCE", "GEAR_CATCHER_RIM_LACE_BORE")
    catcher.matrix_world = matrix_with_translation(left_hand.matrix, (0.0, -35.0, 40.0))
    register_part(
        "GEAR_CATCHER_PALM",
        catcher,
        "03_DISPLAY_GOALIE_GEAR_TPU",
        "TPU_95A_DISPLAY_GEAR",
        "Print flat with the palm disk on the bed; 5 walls and 12% gyroid infill.",
        "Lace a fabric pocket to the rim if desired and strap the part to the left hand form.",
        "25 mm hook-and-loop strap",
        DISPLAY_GEAR_WARNING,
    )
    catcher_cuff = add_box("GEAR_CATCHER_CUFF", (150.0, 32.0, 145.0), bevel=18.0)
    add_edge_lace_holes(
        catcher_cuff,
        "GEAR_CATCHER_CUFF",
        150.0,
        145.0,
        32.0,
        "Y",
        rows=3,
    )
    catcher_cuff.matrix_world = matrix_with_translation(left_hand.matrix, (0.0, -20.0, -80.0))
    register_part(
        "GEAR_CATCHER_CUFF",
        catcher_cuff,
        "03_DISPLAY_GOALIE_GEAR_TPU",
        "TPU_95A_DISPLAY_GEAR",
        "Print on the broad rear face with 4 walls.",
        "Lace to the catcher palm and strap loosely around the wrist form.",
        "Shock cord and 25 mm hook-and-loop strap",
        DISPLAY_GEAR_WARNING,
    )

    for index, z_offset in enumerate((-92.0, 92.0), start=1):
        part_id = f"GEAR_BLOCKER_PANEL_{index:02d}"
        blocker = add_box(part_id, (220.0, 32.0, 180.0), bevel=13.0)
        add_strap_slots(blocker, part_id, 220.0, 180.0, 32.0)
        add_edge_lace_holes(blocker, part_id, 220.0, 180.0, 32.0, "Y", rows=3)
        blocker.matrix_world = matrix_with_translation(
            right_hand.matrix,
            (0.0, -35.0, z_offset),
        )
        register_part(
            part_id,
            blocker,
            "03_DISPLAY_GOALIE_GEAR_TPU",
            "TPU_95A_DISPLAY_GEAR",
            "Print flat on the rear face with 5 walls and 12% gyroid infill.",
            "Lace the two panels along their short edges and strap the assembly to the right hand form.",
            "Shock cord and 25 mm hook-and-loop strap",
            DISPLAY_GEAR_WARNING,
        )


# ---------------------------------------------------------------------------
# OPTIONAL PRINTED STAND


def build_stand() -> None:
    """Build a stacked base and node-connected, positively locked backstay."""
    base_specs = (
        (
            "STAND_BASE_CENTER",
            (190.0, 190.0, 18.0),
            (0.0, -120.0, 9.0),
            ((-77.5, -22.0), (-77.5, 22.0), (77.5, -22.0), (77.5, 22.0),
             (-22.0, -77.5), (22.0, -77.5), (-22.0, 77.5), (22.0, 77.5)),
        ),
        (
            "STAND_BASE_LEFT",
            (230.0, 100.0, 18.0),
            (-175.0, -120.0, 27.0),
            ((97.5, -22.0), (97.5, 22.0), (-88.0, -22.0), (-88.0, 22.0)),
        ),
        (
            "STAND_BASE_RIGHT",
            (230.0, 100.0, 18.0),
            (175.0, -120.0, 27.0),
            ((-97.5, -22.0), (-97.5, 22.0), (88.0, -22.0), (88.0, 22.0)),
        ),
        (
            "STAND_BASE_FRONT",
            (70.0, 230.0, 18.0),
            (0.0, 55.0, 27.0),
            ((-22.0, -97.5), (22.0, -97.5), (-22.0, 88.0), (22.0, 88.0)),
        ),
        (
            "STAND_BASE_REAR",
            (70.0, 230.0, 18.0),
            (0.0, -295.0, 27.0),
            ((-22.0, 97.5), (22.0, 97.5), (-22.0, -88.0), (22.0, -88.0)),
        ),
    )
    base_objects: dict[str, bpy.types.Object] = {}
    for part_id, dimensions, location, holes in base_specs:
        part = build_bolted_panel(part_id, dimensions, holes, bevel=5.0)
        part.location = location
        base_objects[part_id] = part
        register_part(
            part_id,
            part,
            "04_STAND_PETG_ABS",
            CFG.rigid_material,
            "Print flat with 7+ walls and 40% gyroid infill.",
            "The 18 mm center plate is the lower lap; place rails above it with 35 mm overlap and coaxial holes. Support outer rail ends with rubber feet.",
            "See goalie_connections.csv for exact lap hardware.",
            "Display stand only; use the floor sheet and mandatory anti-tip tether.",
        )
    for suffix, rail in (
        ("LEFT", "STAND_BASE_LEFT"),
        ("RIGHT", "STAND_BASE_RIGHT"),
        ("FRONT", "STAND_BASE_FRONT"),
        ("REAR", "STAND_BASE_REAR"),
    ):
        register_connection(
            f"BASE_{suffix}_LAP",
            "STAND_BASE_CENTER",
            rail,
            (("M6 x 55 mm bolt + 2 washers + nyloc nut", 2),),
            "Stack the rail above the center plate and align the paired modeled bores.",
        )
        register_connection(
            f"BASE_{suffix}_FLOOR_MOUNT",
            rail,
            "PURCHASED_18MM_PLYWOOD_FLOOR_SHEET",
            (("M6 x 55 mm bolt + large washers + nyloc nut", 2),),
            "Use the rail's outer modeled hole pair to through-bolt the complete stand base to the shared plywood floor sheet.",
        )

    for side_name, side_sign in (("L", -1.0), ("R", 1.0)):
        part_id = f"STAND_{side_name}_FOOT_PLATE"
        foot_plate = build_bolted_panel(
            part_id,
            (180.0, 230.0, 18.0),
            ((-70.0, -92.0), (70.0, -92.0), (-70.0, 92.0), (70.0, 92.0)),
            bevel=5.0,
        )
        add_floor_strap_slots(foot_plate, part_id)
        foot_plate.location = (185.0 * side_sign * CFG.body_scale, 155.0, 9.0)
        register_part(
            part_id,
            foot_plate,
            "04_STAND_PETG_ABS",
            CFG.rigid_material,
            "Print flat with 7+ walls and 40% gyroid infill.",
            (
                "Route two 25 mm straps through the four modeled slots around the TPU boot clamshell; through-bolt to the shared plywood floor sheet."
                if CFG.generate_body_shell
                else "Route two 25 mm straps through the four modeled slots around the rigid structural foot link; through-bolt to the shared plywood floor sheet."
            ),
            "4 x M6 x 45 mm floor-sheet bolts and two 25 mm straps",
            "A shared plywood floor sheet and anti-tip tether are mandatory for a dressed mannequin.",
        )
        register_connection(
            f"{side_name}_FOOT_PLATE_FLOOR_MOUNT",
            part_id,
            "PURCHASED_18MM_PLYWOOD_FLOOR_SHEET",
            (("M6 x 45 mm bolt + large washer + nyloc nut", 4),),
            "Bolt through the modeled corner holes and plywood; recess bolt heads below the floor sheet.",
        )

    s = CFG.body_scale
    upright_y = -200.0
    node_z = 380.0 * s
    node_radius = 75.0
    # A compact rounded core plus four deep planar bosses gives every bracket
    # a real bearing surface and keeps every insert pocket face-accessible.
    node = add_box("STAND_UPRIGHT_NODE", (100.0, 100.0, 100.0), bevel=15.0)
    node.location = (0.0, upright_y, node_z)

    upright_bottom = Vector((0.0, upright_y, 58.0))
    anchor_face_offset = CFG.anchor_base_center + CFG.anchor_base_thickness * 0.5
    node_bottom_pivot = Vector(
        (0.0, upright_y, node_z - node_radius - anchor_face_offset)
    )
    node_top_pivot = Vector(
        (0.0, upright_y, node_z + node_radius + anchor_face_offset)
    )
    upright_top = Vector((0.0, upright_y, 920.0 * s))
    lower_upright = build_link_chain(
        "STAND_REAR_UPRIGHT_LOWER",
        upright_bottom,
        node_bottom_pivot,
        (1.0, 0.0, 0.0),
        category="04_STAND_PETG_ABS",
        radius=19.0,
    )
    upper_upright = build_link_chain(
        "STAND_REAR_UPRIGHT_UPPER",
        node_top_pivot,
        upright_top,
        (1.0, 0.0, 0.0),
        category="04_STAND_PETG_ABS",
        radius=19.0,
    )

    base_anchor = build_anchor_bracket("STAND_BASE_UPRIGHT_BRACKET")
    base_anchor.matrix_world = frame_between(upright_bottom, node_bottom_pivot, (1.0, 0.0, 0.0))
    base_anchor.matrix_world.translation = upright_bottom
    cut_bracket_mount_pattern(
        base_objects["STAND_BASE_CENTER"], base_anchor, -1.0, 70.0
    )
    register_part(
        "STAND_BASE_UPRIGHT_BRACKET",
        base_anchor,
        "04_STAND_PETG_ABS",
        CFG.rigid_material,
        "Print base-down with 7+ walls and 45% gyroid infill.",
        "Mount on top of the center plate using its coaxial modeled bores.",
        "4 x M5 x 45 mm bolts plus pivot hardware in goalie_connections.csv",
        "Display stand only; inspect after every move.",
    )
    register_anchor_joint(
        "STAND_BASE_UPRIGHT_PIVOT",
        "STAND_BASE_UPRIGHT_BRACKET",
        base_anchor.matrix_world,
        lower_upright,
        at_chain_start=True,
        locked=True,
    )
    register_connection(
        "STAND_BASE_UPRIGHT_MOUNT",
        "STAND_BASE_CENTER",
        "STAND_BASE_UPRIGHT_BRACKET.BASE",
        (("M5 x 45 mm bolt + fender washer + nyloc nut", 4),),
        "Use the modeled coaxial base/bracket holes.",
    )

    lower_node_anchor = build_anchor_bracket(
        "STAND_NODE_LOWER_BRACKET", terminal_type="MALE", base_side=1.0
    )
    lower_node_anchor.matrix_world = frame_between(
        upright_bottom, node_bottom_pivot, (1.0, 0.0, 0.0)
    )
    lower_node_anchor.matrix_world.translation = node_bottom_pivot
    add_insert_boss_and_mount_pattern(
        node, lower_node_anchor, 1.0, boss_depth=30.0
    )
    upper_node_anchor = build_anchor_bracket("STAND_NODE_UPPER_BRACKET")
    upper_node_anchor.matrix_world = frame_between(
        node_top_pivot, upright_top, (1.0, 0.0, 0.0)
    )
    upper_node_anchor.matrix_world.translation = node_top_pivot
    add_insert_boss_and_mount_pattern(
        node, upper_node_anchor, -1.0, boss_depth=30.0
    )
    node_mount_faces: list[tuple[bpy.types.Object, float]] = [
        (lower_node_anchor, 1.0),
        (upper_node_anchor, -1.0),
    ]
    for part_id, anchor, chain, at_start in (
        ("STAND_NODE_LOWER_BRACKET", lower_node_anchor, lower_upright, False),
        ("STAND_NODE_UPPER_BRACKET", upper_node_anchor, upper_upright, True),
    ):
        register_part(
            part_id,
            anchor,
            "04_STAND_PETG_ABS",
            CFG.rigid_material,
            "Print base-down with 7+ walls and 45% gyroid infill.",
            "Seat on the matching planar node boss and install four short screws into accessible heat-set inserts.",
            "4 x M5 x 20 mm screws and M5 heat-set inserts plus pivot hardware in goalie_connections.csv",
            "Display stand only; inspect after every move.",
        )
        register_anchor_joint(
            part_id + "_PIVOT",
            part_id,
            anchor.matrix_world,
            chain,
            at_chain_start=at_start,
            locked=True,
        )
        register_connection(
            part_id + "_MOUNT",
            "STAND_UPRIGHT_NODE",
            part_id + ".BASE",
            (("M5 x 20 mm socket screw + washer + heat-set insert", 4),),
            "Heat-set the four inserts from the planar boss face, then use the modeled coaxial bracket holes; do not attempt to put nuts inside the solid node.",
        )

    # Two diagonal links land on separate sides of the node, avoiding the
    # colliding coincident clevises of a single-point truss.
    for side_name, side_sign in (("L", -1.0), ("R", 1.0)):
        base_land = Vector((205.0 * side_sign, -120.0, 36.0))
        node_center = Vector((0.0, upright_y, node_z))
        direction = (node_center - base_land).normalized()
        start_pivot = base_land + direction * anchor_face_offset
        end_pivot = node_center - direction * (
            node_radius + anchor_face_offset
        )
        start_pivot = align_start_anchor_above_horizontal_land(
            start_pivot,
            end_pivot,
            Vector((0.0, 1.0, 0.0)),
            36.0,
        )
        diagonal = build_link_chain(
            f"STAND_DIAGONAL_{side_name}",
            start_pivot,
            end_pivot,
            (0.0, 1.0, 0.0),
            category="04_STAND_PETG_ABS",
            radius=18.0,
        )
        diagonal_frame = frame_between(start_pivot, end_pivot, (0.0, 1.0, 0.0))
        base_bracket_id = f"STAND_DIAGONAL_{side_name}_BASE_BRACKET"
        base_bracket = build_anchor_bracket(base_bracket_id)
        base_bracket.matrix_world = diagonal_frame
        base_bracket.matrix_world.translation = start_pivot
        base_target = base_objects[
            f"STAND_BASE_{'LEFT' if side_name == 'L' else 'RIGHT'}"
        ]
        base_wedge_id = f"STAND_DIAGONAL_{side_name}_BASE_WEDGE"
        base_wedge, base_bolt_hardware, base_bolt_mapping = (
            build_mating_wedge_and_mount_pattern(
            base_wedge_id,
            base_target,
            base_bracket,
            -1.0,
            cutter_depth=85.0,
            target_surface_z=36.0,
            target_panel_thickness=18.0,
            wedge_world_z_sign=1.0,
            )
        )
        register_part(
            base_wedge_id,
            base_wedge,
            "04_STAND_PETG_ABS",
            CFG.rigid_material,
            "Print on the 68 x 54 mm angled-bracket face with 7+ walls and 45% gyroid infill.",
            "Place the horizontal face on the side rail and the angled face under the diagonal base bracket; align all four modeled bores.",
            "Shares the four configuration-derived M5 diagonal-base bolts",
            "Display stand only; use the floor sheet and mandatory tether.",
        )
        node_bracket_id = f"STAND_DIAGONAL_{side_name}_NODE_BRACKET"
        node_bracket = build_anchor_bracket(
            node_bracket_id, terminal_type="MALE", base_side=1.0
        )
        node_bracket.matrix_world = diagonal_frame
        node_bracket.matrix_world.translation = end_pivot
        add_insert_boss_and_mount_pattern(
            node, node_bracket, 1.0, boss_depth=30.0
        )
        node_mount_faces.append((node_bracket, 1.0))
        for part_id, bracket in (
            (base_bracket_id, base_bracket),
            (node_bracket_id, node_bracket),
        ):
            register_part(
                part_id,
                bracket,
                "04_STAND_PETG_ABS",
                CFG.rigid_material,
                "Print mounting-plate-down with 7+ walls and 45% gyroid infill.",
                "Use the modeled mating holes at the rail or upright node.",
                "4 x M5 screws plus pivot hardware in goalie_connections.csv",
                "Display stand only; use the mandatory tether.",
            )
        register_anchor_joint(
            f"STAND_DIAGONAL_{side_name}_BASE_PIVOT",
            base_bracket_id,
            base_bracket.matrix_world,
            diagonal,
            at_chain_start=True,
            locked=True,
        )
        register_anchor_joint(
            f"STAND_DIAGONAL_{side_name}_NODE_PIVOT",
            node_bracket_id,
            node_bracket.matrix_world,
            diagonal,
            at_chain_start=False,
            locked=True,
        )
        register_connection(
            f"STAND_DIAGONAL_{side_name}_BASE_MOUNT",
            f"STAND_BASE_{'LEFT' if side_name == 'L' else 'RIGHT'}+{base_wedge_id}",
            base_bracket_id + ".BASE",
            base_bolt_hardware,
            "Through-bolt the rail, separate full-area wedge, and diagonal bracket using the four modeled coaxial holes; use washers at both printed outer faces. On the terminal-facing bracket face, shallow dot groups identify each hole. Marked-hole bolt map: "
            + base_bolt_mapping,
        )
        register_connection(
            f"STAND_DIAGONAL_{side_name}_NODE_MOUNT",
            "STAND_UPRIGHT_NODE",
            node_bracket_id + ".BASE",
            (("M5 x 20 mm socket screw + washer + heat-set insert", 4),),
            "Heat-set four inserts from the planar diagonal boss and install short screws through the coaxial bracket holes.",
        )

    for node_bracket, base_side in node_mount_faces:
        clip_mount_face_clearance(node, node_bracket, base_side)

    register_part(
        "STAND_UPRIGHT_NODE",
        node,
        "04_STAND_PETG_ABS",
        CFG.rigid_material,
        "Print with a 12 mm brim and tree support under the 150 mm node; use 8 walls and 50% gyroid infill. Install heat-set inserts only after cooling.",
        "The rounded central core has four unioned planar bosses with face-accessible blind insert pockets for the lower, upper, left-diagonal, and right-diagonal brackets.",
        "16 x M5 heat-set inserts; see goalie_connections.csv.",
        "Display stand only; node does not replace the anti-tip tether.",
    )

    # Bridge into the planar saddle across the rear faces of both pelvis halves.
    saddle_rear_y = -structural_pelvis_depth() * 0.5 - 18.0
    pelvis_back = Vector(
        (0.0, saddle_rear_y - anchor_face_offset, 920.0 * s)
    )
    bridge = build_link_chain(
        "STAND_PELVIS_BRIDGE",
        upright_top,
        pelvis_back,
        (1.0, 0.0, 0.0),
        category="04_STAND_PETG_ABS",
        radius=19.0,
    )
    register_chain_joint("STAND_TOP_CORNER_PIVOT", upper_upright, bridge)
    pelvis_bracket = build_anchor_bracket(
        "STAND_PELVIS_BRACKET", terminal_type="MALE", base_side=1.0
    )
    pelvis_bracket.matrix_world = frame_between(
        upright_top, pelvis_back, (1.0, 0.0, 0.0)
    )
    pelvis_bracket.matrix_world.translation = pelvis_back
    cut_insert_mount_pattern(
        bpy.data.objects["STRUCT_PELVIS_REAR_SADDLE"],
        pelvis_bracket,
        1.0,
        pilot_depth=12.0,
    )
    register_part(
        "STAND_PELVIS_BRACKET",
        pelvis_bracket,
        "04_STAND_PETG_ABS",
        CFG.rigid_material,
        "Print mounting-plate-down with 7+ walls and 45% gyroid infill.",
        "Mount against the planar rear saddle using its face-accessible heat-set inserts.",
        "4 x M5 x 20 mm screws and M5 heat-set inserts plus pivot hardware in goalie_connections.csv",
        "Display stand only; use the mandatory tether.",
    )
    register_anchor_joint(
        "STAND_PELVIS_BRIDGE_END_PIVOT",
        "STAND_PELVIS_BRACKET",
        pelvis_bracket.matrix_world,
        bridge,
        at_chain_start=False,
        locked=True,
    )
    register_connection(
        "STAND_PELVIS_BRACKET_MOUNT",
        "STRUCT_PELVIS_REAR_SADDLE",
        "STAND_PELVIS_BRACKET.BASE",
        (("M5 x 20 mm socket screw + washer + heat-set insert", 4),),
        "Heat-set the four inserts from the rear saddle face, then install the bracket with short screws; the separate M6 saddle bolts terminate at accessible front nuts.",
    )

    # Positive corner lock: two side plates and two shared through-bolts clamp
    # the actual upright and bridge link bodies, rather than relying on holes
    # that exist only in the lock plates.
    upright_direction = (upright_top - upper_upright[-1].start).normalized()
    bridge_direction = (bridge[0].end - upright_top).normalized()
    upright_lock_hole = upright_top - upright_direction * 65.0
    bridge_lock_hole = upright_top + bridge_direction * 65.0
    lock_span = (bridge_lock_hole - upright_lock_hole).length
    lock_frame = frame_between(
        upright_lock_hole,
        bridge_lock_hole,
        (1.0, 0.0, 0.0),
    )
    for target, location, label in (
        (upper_upright[-1].record.obj, upright_lock_hole, "UPRIGHT"),
        (bridge[0].record.obj, bridge_lock_hole, "BRIDGE"),
    ):
        cutter = add_cylinder_along_vector(
            f"STAND_TOP_CORNER_{label}_THROUGH_HOLE",
            3.2,
            70.0,
            location,
            (1.0, 0.0, 0.0),
        )
        boolean_apply(
            target,
            cutter,
            "DIFFERENCE",
            f"STAND_TOP_CORNER_{label}_THROUGH_BORE",
        )

    for side_name, x in (("L", -22.5), ("R", 22.5)):
        part_id = f"STAND_TOP_CORNER_LOCK_{side_name}"
        lock = add_box(part_id, (7.0, 32.0, lock_span + 44.0), bevel=3.0)
        for z in (-lock_span * 0.5, lock_span * 0.5):
            cutter = add_cylinder(
                part_id + "_Shared_Bolt_Hole",
                3.2,
                12.0,
                (0.0, 0.0, z),
                axis="X",
            )
            boolean_apply(lock, cutter, "DIFFERENCE", part_id + "_Shared_Bore")
        lock.matrix_world = lock_frame.copy()
        lock.matrix_world.translation.x = x
        register_part(
            part_id,
            lock,
            "04_STAND_PETG_ABS",
            CFG.rigid_material,
            "Print flat with 7 walls and 50% gyroid infill.",
            "Install on one side across the upright/bridge corner; both plates share one through-bolt at each modeled structural-member bore.",
            "2 shared M6 x 70 mm bolts, fender washers, nyloc nuts",
            "Display stand only; both lock plates and tether are mandatory.",
        )
    register_connection(
        "STAND_TOP_CORNER_LOCK_MOUNT",
        "STAND_TOP_CORNER_LOCK_L+STAND_TOP_CORNER_LOCK_R",
        f"{upper_upright[-1].record.part_id}+{bridge[0].record.part_id}",
        (("M6 x 70 mm bolt + fender washers + nyloc nut", 2),),
        "Pass one shared bolt through both lock plates and the upper-upright bore, and the other through both plates and the bridge bore.",
    )

    # Printed fairlead plus a purchased forged eye bolt provides a steel tether
    # load path through the full rounded node core.
    tether = add_box("STAND_TETHER_FAIRLEAD", (70.0, 18.0, 70.0), bevel=10.0)
    tether_hole = add_cylinder(
        "STAND_TETHER_EYE_HOLE", 5.3, 24.0, axis="Y", vertices=48
    )
    boolean_apply(tether, tether_hole, "DIFFERENCE", "STAND_TETHER_FAIRLEAD_BORE")
    node_core_half_depth = 50.0
    tether.location = (0.0, upright_y - node_core_half_depth - 9.0, node_z)
    node_tether_hole = add_cylinder(
        "STAND_NODE_TETHER_THROUGH_HOLE",
        5.3,
        node_radius * 2.0 + 24.0,
        (0.0, upright_y, node_z),
        axis="Y",
        vertices=48,
    )
    boolean_apply(node, node_tether_hole, "DIFFERENCE", "STAND_NODE_TETHER_BORE")
    register_part(
        "STAND_TETHER_FAIRLEAD",
        tether,
        "04_STAND_PETG_ABS",
        CFG.rigid_material,
        "Print flat with 8 walls and 50% gyroid infill.",
        "Place on the rear node face; a purchased M10 forged shoulder eye bolt passes through this fairlead and the full node.",
        "1 x M10 x 200 mm forged shoulder eye bolt, large washers, rated locknut",
        "A tether rated at least 1 kN is mandatory whenever the dressed mannequin is upright.",
    )
    register_connection(
        "TETHER_STEEL_LOAD_PATH",
        "STAND_TETHER_FAIRLEAD+STAND_UPRIGHT_NODE",
        "PURCHASED_RATED_TETHER",
        (("M10 x 200 mm forged shoulder eye bolt + large washers + rated locknut", 1),),
        "Route a rated tether from the forged eye to a structural wall/floor anchor; the printed fairlead is not the rated element.",
    )


# ---------------------------------------------------------------------------
# VALIDATION, EXPORT, AND DOCUMENTATION


def mesh_diagnostics(obj: bpy.types.Object) -> tuple[int, int]:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    non_manifold = sum(1 for edge in bm.edges if not edge.is_manifold)
    remaining = set(bm.faces)
    shells = 0
    while remaining:
        shells += 1
        stack = [remaining.pop()]
        while stack:
            face = stack.pop()
            for edge in face.edges:
                for linked in edge.link_faces:
                    if linked in remaining:
                        remaining.remove(linked)
                        stack.append(linked)
    bm.free()
    return non_manifold, shells


def fits_build_volume(dimensions: Sequence[float]) -> bool:
    margin = CFG.build_margin
    return (
        dimensions[0] <= CFG.build_x - margin
        and dimensions[1] <= CFG.build_y - margin
        and dimensions[2] <= CFG.build_z - margin
    )


def print_dimensions(record: PartRecord) -> tuple[float, float, float]:
    x, y, z = record.local_dimensions
    rotation = best_print_rotation(record)
    if abs(abs(rotation[0]) - math.pi * 0.5) < 0.001:
        return (x, z, y)
    if abs(abs(rotation[1]) - math.pi * 0.5) < 0.001:
        return (z, y, x)
    return (x, y, z)


def validate_parts() -> None:
    failures: list[str] = []
    for record in PARTS:
        dimensions = local_mesh_dimensions(record.obj)
        record.local_dimensions = dimensions
        oriented = print_dimensions(record)
        if not fits_build_volume(oriented):
            failures.append(
                f"{record.part_id}: print_dimensions={tuple(round(v, 2) for v in oriented)}"
            )
        non_manifold, shells = mesh_diagnostics(record.obj)
        if non_manifold:
            failures.append(f"{record.part_id}: {non_manifold} non-manifold edges")
        if shells != 1:
            failures.append(f"{record.part_id}: {shells} disconnected mesh shells")
        if record.part_id.endswith("_WEDGE"):
            bed_contact_area = print_bed_contact_area(record)
            if bed_contact_area < 3000.0:
                failures.append(
                    f"{record.part_id}: only {bed_contact_area:.1f} mm^2 of "
                    "coplanar print-bed contact; expected the full bracket face"
                )
            print(
                f"BED_CONTACT_CHECK id={record.part_id} "
                f"area_mm2={bed_contact_area:.2f}"
            )
        print(
            "PART_CHECK "
            f"id={record.part_id} "
            f"dimensions={tuple(round(value, 2) for value in dimensions)} "
            f"print_dimensions={tuple(round(value, 2) for value in oriented)} "
            f"non_manifold={non_manifold} shells={shells}"
        )
    if failures:
        raise RuntimeError("Part validation failed:\n  " + "\n  ".join(failures))


def world_aabb(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    low = Vector(tuple(min(corner[axis] for corner in corners) for axis in range(3)))
    high = Vector(tuple(max(corner[axis] for corner in corners) for axis in range(3)))
    return low, high


def world_bvh(
    obj: bpy.types.Object,
    translation: Vector | None = None,
) -> BVHTree:
    offset = translation if translation is not None else Vector((0.0, 0.0, 0.0))
    vertices = [obj.matrix_world @ vertex.co + offset for vertex in obj.data.vertices]
    polygons = [tuple(polygon.vertices) for polygon in obj.data.polygons]
    return BVHTree.FromPolygons(vertices, polygons, all_triangles=False)


def overlap_center_bounds(
    obj: bpy.types.Object,
    polygon_indices: Iterable[int],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    centers = [
        obj.matrix_world @ obj.data.polygons[index].center
        for index in set(polygon_indices)
    ]
    if not centers:
        zero = (0.0, 0.0, 0.0)
        return zero, zero
    return (
        tuple(min(center[axis] for center in centers) for axis in range(3)),
        tuple(max(center[axis] for center in centers) for axis in range(3)),
    )


def validate_assembly() -> None:
    failures: list[str] = []
    part_ids = [record.part_id for record in PARTS]
    duplicate_part_ids = sorted({item for item in part_ids if part_ids.count(item) > 1})
    if duplicate_part_ids:
        failures.append(f"duplicate part IDs: {duplicate_part_ids}")
    connection_ids = [record.connection_id for record in CONNECTIONS]
    duplicate_connection_ids = sorted(
        {item for item in connection_ids if connection_ids.count(item) > 1}
    )
    if duplicate_connection_ids:
        failures.append(f"duplicate connection IDs: {duplicate_connection_ids}")

    known_parts = set(part_ids)
    for connection in CONNECTIONS:
        for mate_field in (connection.mate_a, connection.mate_b):
            for mate in mate_field.split("+"):
                base_part = mate.split(".", 1)[0]
                if (
                    not base_part.startswith("PURCHASED_")
                    and base_part not in known_parts
                ):
                    failures.append(
                        f"{connection.connection_id}: unresolved mate {base_part}"
                    )

    for connection in CONNECTIONS:
        if connection.point_a is None:
            continue
        point_error = (connection.point_a - connection.point_b).length
        axis_alignment = abs(connection.axis_a.dot(connection.axis_b))
        if point_error > 0.05:
            failures.append(
                f"{connection.connection_id}: pivot centers differ by {point_error:.3f} mm"
            )
        if axis_alignment < 0.9995:
            angle = math.degrees(math.acos(min(1.0, max(-1.0, axis_alignment))))
            failures.append(
                f"{connection.connection_id}: pivot axes differ by {angle:.3f} degrees"
            )
        if {connection.terminal_a, connection.terminal_b} != {"MALE", "FEMALE"}:
            failures.append(
                f"{connection.connection_id}: terminals are not complementary "
                f"({connection.terminal_a}, {connection.terminal_b})"
            )
        part_a = connection.mate_a.split(".", 1)[0]
        part_b = connection.mate_b.split(".", 1)[0]
        if part_a in bpy.data.objects and part_b in bpy.data.objects:
            overlaps = world_bvh(bpy.data.objects[part_a]).overlap(
                world_bvh(bpy.data.objects[part_b])
            )
            if overlaps:
                failures.append(
                    f"{connection.connection_id}: mating link meshes interpenetrate "
                    f"({len(overlaps)} triangle pairs)"
                )

    for target, bracket, holes, base_side in MOUNT_PATTERN_CHECKS:
        if len(holes) != 4 or len(set(holes)) != 4:
            failures.append(f"{target.name}/{bracket.name}: invalid four-hole mate pattern")
        if target.name not in bpy.data.objects or bracket.name not in bpy.data.objects:
            failures.append(f"{target.name}/{bracket.name}: mating object missing")
        modeled_holes = tuple(
            tuple(float(value) for value in (bracket.matrix_world @ Vector(local)))
            for local in bracket["mount_holes_local"]
        )
        hole_axis = (
            bracket.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))
        ).normalized()
        if any(
            (
                (Vector(recorded) - Vector(modeled))
                - hole_axis
                * (Vector(recorded) - Vector(modeled)).dot(hole_axis)
            ).length
            > 0.01
            for recorded, modeled in zip(holes, modeled_holes)
        ):
            failures.append(
                f"{target.name}/{bracket.name}: projected bores do not match actual bracket holes"
            )
        # Test the actual modeled contact face, not merely the recorded hole
        # count.  Coplanar triangle contact is expected here, so BVH overlap is
        # not a valid volume-intersection test by itself.
        target_bvh = world_bvh(target)
        contact_z = base_side * (
            CFG.anchor_base_center + CFG.anchor_base_thickness * 0.5
        )
        if "HAND_FORM_FRONT" in target.name:
            contact_samples = ((-16.0, 10.0), (0.0, 10.0), (16.0, 10.0))
        elif "HAND_FORM_REAR" in target.name:
            contact_samples = ((-16.0, -10.0), (0.0, -10.0), (16.0, -10.0))
        else:
            contact_samples = (
                (0.0, 0.0),
                (-16.0, -10.0),
                (-16.0, 10.0),
                (16.0, -10.0),
                (16.0, 10.0),
            )
        contact_distances: list[float] = []
        for x, y in contact_samples:
            sample = bracket.matrix_world @ Vector((x, y, contact_z))
            nearest = target_bvh.find_nearest(sample)
            contact_distances.append(
                float("inf") if nearest[0] is None else float(nearest[3])
            )
        if max(contact_distances) > 1.25:
            failures.append(
                f"{target.name}/{bracket.name}: mounting face lacks full-area contact "
                f"(max sample gap {max(contact_distances):.3f} mm)"
            )
        # Move the bracket 0.1 mm away from the nominal contact plane before
        # intersecting the BVHs.  Any remaining overlap is real penetration,
        # while coincident face triangles no longer produce false positives.
        shifted_bracket_bvh = world_bvh(
            bracket,
            -base_side * hole_axis * 0.1,
        )
        penetrations = target_bvh.overlap(shifted_bracket_bvh)
        if penetrations:
            separation_probe = tuple(
                (
                    distance,
                    len(
                        target_bvh.overlap(
                            world_bvh(
                                bracket,
                                -base_side * hole_axis * distance,
                            )
                        )
                    ),
                )
                for distance in (0.5, 1.0, 2.0, 4.0, 6.0)
            )
            failures.append(
                f"{target.name}/{bracket.name}: mounting solids interpenetrate "
                f"after 0.1 mm contact separation ({len(penetrations)} triangle pairs; "
                f"probe={separation_probe})"
            )

    for first, second, separation, label in CLEARANCE_CHECKS:
        penetrations = world_bvh(first, separation).overlap(world_bvh(second))
        if penetrations:
            first_bounds = overlap_center_bounds(
                first,
                (pair[0] for pair in penetrations),
            )
            second_bounds = overlap_center_bounds(
                second,
                (pair[1] for pair in penetrations),
            )
            failures.append(
                f"{label}: assembly solids interpenetrate "
                f"({len(penetrations)} triangle pairs; polygon-center bounds "
                f"{first_bounds} / {second_bounds})"
            )

    for panel, sleeve, samples, expected_gap, label in PAD_SADDLE_CONTACT_CHECKS:
        panel_bvh = world_bvh(panel)
        sleeve_bvh = world_bvh(sleeve)
        panel_surface_distances: list[float] = []
        sleeve_gaps: list[float] = []
        for sample in samples:
            panel_nearest = panel_bvh.find_nearest(sample)
            sleeve_nearest = sleeve_bvh.find_nearest(sample)
            panel_surface_distances.append(
                float("inf")
                if panel_nearest[0] is None
                else float(panel_nearest[3])
            )
            sleeve_gaps.append(
                float("inf")
                if sleeve_nearest[0] is None
                else float(sleeve_nearest[3])
            )
        if max(panel_surface_distances) > 0.25:
            failures.append(
                f"{label}: saddle samples are not on the integral panel rails "
                f"(max panel distance {max(panel_surface_distances):.3f} mm)"
            )
        if any(abs(gap - expected_gap) > 0.65 for gap in sleeve_gaps):
            failures.append(
                f"{label}: rear saddle rails do not follow the sleeve contact "
                f"surface (gaps {tuple(round(gap, 3) for gap in sleeve_gaps)} mm; "
                f"expected {expected_gap:.3f} mm)"
            )
        print(
            f"PAD_SADDLE_CONTACT_CHECK id={label} "
            f"gap_range_mm=({min(sleeve_gaps):.3f},{max(sleeve_gaps):.3f})"
        )

    for clearance, label in PAD_HARDWARE_CLEARANCE_CHECKS:
        if clearance < 2.0:
            failures.append(
                f"{label}: only {clearance:.3f} mm central capped-rod "
                "clearance remains when the saddle rails seat"
            )
        else:
            print(
                f"PAD_HARDWARE_CLEARANCE_CHECK id={label} "
                f"clearance_mm={clearance:.3f}"
            )

    for hardware_gap, lace_gap, label in PAD_SADDLE_LATERAL_CLEARANCE_CHECKS:
        if hardware_gap < 2.0 or lace_gap < 2.0:
            failures.append(
                f"{label}: rail does not clear both installed hardware and "
                f"seam cord (hardware {hardware_gap:.3f} mm; "
                f"lace-bore edge {lace_gap:.3f} mm)"
            )
        else:
            print(
                f"PAD_SADDLE_LATERAL_CLEARANCE_CHECK id={label} "
                f"hardware_mm={hardware_gap:.3f} lace_mm={lace_gap:.3f}"
            )

    for panel, link, forward_axis, expected_offset, label in FRONT_GEAR_CHECKS:
        offset = panel.matrix_world.translation - link.matrix_world.translation
        forward_distance = offset.dot(forward_axis)
        if abs(forward_distance - expected_offset) > 0.01 or offset.y <= 0.0:
            failures.append(
                f"{label}: goalie pad is not on the leg front "
                f"(local-forward offset {forward_distance:.3f} mm; "
                f"expected {expected_offset:.3f} mm; "
                f"world-Y offset {offset.y:.3f} mm)"
            )
        else:
            print(
                f"FRONT_GEAR_CHECK id={label} "
                f"local_forward_mm={forward_distance:.3f} "
                f"expected_mm={expected_offset:.3f} "
                f"world_y_mm={offset.y:.3f}"
            )

    for wedge, target, samples, label in WEDGE_PANEL_CHECKS:
        wedge_bvh = world_bvh(wedge)
        target_bvh = world_bvh(target)
        wedge_distances = []
        target_distances = []
        for sample in samples:
            nearest_wedge = wedge_bvh.find_nearest(sample)
            nearest_target = target_bvh.find_nearest(sample)
            wedge_distances.append(
                float("inf")
                if nearest_wedge[0] is None
                else float(nearest_wedge[3])
            )
            target_distances.append(
                float("inf")
                if nearest_target[0] is None
                else float(nearest_target[3])
            )
        if max(wedge_distances) > 0.25 or max(target_distances) > 0.25:
            failures.append(
                f"{label}: wedge/target support is missing around a mount bore "
                f"(wedge max gap {max(wedge_distances):.3f} mm; "
                f"target max gap {max(target_distances):.3f} mm)"
            )

    for wedge, target, centers, label in WEDGE_BORE_CHECKS:
        wedge_bvh = world_bvh(wedge)
        target_bvh = world_bvh(target)
        for index, center in enumerate(centers, start=1):
            wedge_nearest = wedge_bvh.find_nearest(center)
            target_nearest = target_bvh.find_nearest(center)
            wedge_radius = (
                float("inf")
                if wedge_nearest[0] is None
                else float(wedge_nearest[3])
            )
            target_radius = (
                float("inf")
                if target_nearest[0] is None
                else float(target_nearest[3])
            )
            if not (
                2.5 <= wedge_radius <= 3.5
                and 2.5 <= target_radius <= 3.5
            ):
                failures.append(
                    f"{label}: bore {index} lacks a supported fastener entry "
                    f"(wedge radius {wedge_radius:.3f} mm; "
                    f"target radius {target_radius:.3f} mm)"
                )

    for target, centers, minimum_radius, maximum_radius, label in BORE_FACE_CHECKS:
        target_bvh = world_bvh(target)
        radii: list[float] = []
        for index, center in enumerate(centers, start=1):
            nearest = target_bvh.find_nearest(center)
            radius = (
                float("inf")
                if nearest[0] is None
                else float(nearest[3])
            )
            radii.append(radius)
            if not minimum_radius <= radius <= maximum_radius:
                failures.append(
                    f"{label}: bore-face sample {index} is not open "
                    f"(entry radius {radius:.3f} mm; expected "
                    f"{minimum_radius:.3f}-{maximum_radius:.3f} mm)"
                )
        print(
            f"BORE_FACE_CHECK id={label} samples={len(radii)} "
            f"radius_range=({min(radii):.3f},{max(radii):.3f})"
        )

    for front, rear in CLAMSHELL_PAIR_CHECKS:
        front_low, _ = local_mesh_bounds(front)
        _, rear_high = local_mesh_bounds(rear)
        seam_overlap = rear_high.y - front_low.y
        if seam_overlap > 0.05:
            failures.append(
                f"{front.name}/{rear.name}: clamshell halves overlap by "
                f"{seam_overlap:.3f} mm across their mating plane"
            )

    # These interfaces are deliberately stacked face-to-face.  Positive AABB
    # overlap would mean the assembly preview contains interpenetrating solids.
    contact_pairs = [
        ("STRUCT_PELVIS_L", "STRUCT_PELVIS_R"),
    ]
    for part_a, part_b in contact_pairs:
        low_a, high_a = world_aabb(bpy.data.objects[part_a])
        low_b, high_b = world_aabb(bpy.data.objects[part_b])
        overlap = [min(high_a[i], high_b[i]) - max(low_a[i], low_b[i]) for i in range(3)]
        if min(overlap) > 0.05:
            failures.append(
                f"{part_a}/{part_b}: unintended AABB volume overlap {tuple(round(v, 3) for v in overlap)}"
            )

    required_connections = {
        "PELVIS_CENTER_LAP",
        "SPINE_BASE_PIVOT",
        "SPINE_TOP_PIVOT",
        "NECK_BASE_PIVOT",
        "HEAD_CORE_PIVOT",
    }
    if CFG.generate_stand:
        required_connections.update(
            {
                "STAND_BASE_UPRIGHT_PIVOT",
                "STAND_PELVIS_BRIDGE_END_PIVOT",
                "TETHER_STEEL_LOAD_PATH",
            }
        )
    missing_connections = required_connections - set(connection_ids)
    if missing_connections:
        failures.append(f"required connection records missing: {sorted(missing_connections)}")

    if failures:
        raise RuntimeError("Assembly validation failed:\n  " + "\n  ".join(failures))
    print(
        "ASSEMBLY_CHECK_COMPLETE "
        f"connections={len(CONNECTIONS)} mount_patterns={len(MOUNT_PATTERN_CHECKS)}"
    )


def best_print_rotation(record: PartRecord) -> tuple[float, float, float]:
    # Anchor brackets need their mounting plate on the bed even though local Y
    # happens to be a few millimeters smaller than local Z.  Every other part
    # uses the smallest axis as print height.
    explicit = record.obj.get("print_rotation_euler")
    if explicit is not None:
        return tuple(float(value) for value in explicit)
    dimensions = record.local_dimensions
    smallest_axis = min(range(3), key=lambda axis: dimensions[axis])
    if smallest_axis == 0:  # local X -> print Z
        return (0.0, math.pi / 2.0, 0.0)
    if smallest_axis == 1:  # local Y -> print Z
        return (math.pi / 2.0, 0.0, 0.0)
    return (0.0, 0.0, 0.0)


def triangulate_export_mesh(obj: bpy.types.Object) -> None:
    """Triangulate explicitly so the STL exporter cannot create sliver facets."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(
        bm,
        faces=list(bm.faces),
        quad_method="BEAUTY",
        ngon_method="BEAUTY",
    )
    # Some exact-boolean boundaries contain a zero-volume folded sliver: two
    # coincident triangles whose short edges only connect to each other while
    # the long edge already has the two proper solid-surface faces.  Deleting
    # the complete coincident group collapses that flap back to the long edge;
    # retaining one triangle would instead open the surface.  Canonicalize at
    # float32 precision because that is the precision written to binary STL.
    facet_groups: dict[
        tuple[tuple[float, float, float], ...],
        list[bmesh.types.BMFace],
    ] = {}
    for face in bm.faces:
        key = tuple(
            sorted(
                tuple(
                    struct.unpack("<f", struct.pack("<f", float(vertex.co[axis])))[0]
                    for axis in range(3)
                )
                for vertex in face.verts
            )
        )
        facet_groups.setdefault(key, []).append(face)
    folded_slivers = [
        face
        for faces in facet_groups.values()
        if len(faces) > 1
        for face in faces
    ]
    if folded_slivers:
        bmesh.ops.delete(bm, geom=folded_slivers, context="FACES")
        print(
            f"EXPORT_SLIVER_CLEANUP id={obj.name} "
            f"removed_facets={len(folded_slivers)}"
        )
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def prepare_export_copy(record: PartRecord) -> bpy.types.Object:
    source = record.obj
    duplicate = source.copy()
    duplicate.data = source.data.copy()
    ensure_collection("99_EXPORT_TEMP").objects.link(duplicate)
    duplicate.matrix_world = Matrix.Identity(4)
    duplicate.rotation_euler = best_print_rotation(record)
    apply_object_transform(duplicate, location=False, rotation=True, scale=True)
    # Blender's STL exporter may triangulate a valid concave n-gon into paired
    # near-collinear sliver facets.  Triangulating the isolated print-pose copy
    # with BMesh avoids those duplicate facets without modifying the assembly.
    triangulate_export_mesh(duplicate)
    low, high = local_mesh_bounds(duplicate)
    duplicate.location = (
        -(low.x + high.x) * 0.5,
        -(low.y + high.y) * 0.5,
        -low.z,
    )
    apply_object_transform(duplicate, location=True, rotation=False, scale=False)
    duplicate.name = record.part_id + "_EXPORT"
    return duplicate


def print_bed_contact_area(record: PartRecord) -> float:
    """Return exact coplanar bed-face area in the documented print pose."""
    duplicate = prepare_export_copy(record)
    try:
        low, _ = local_mesh_bounds(duplicate)
        tolerance = 0.01
        return sum(
            float(polygon.area)
            for polygon in duplicate.data.polygons
            if all(
                abs(duplicate.data.vertices[index].co.z - low.z) <= tolerance
                for index in polygon.vertices
            )
        )
    finally:
        delete_object(duplicate)


def export_stl(path: Path, obj: bpy.types.Object) -> None:
    select_only(obj)
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(
            filepath=str(path),
            export_selected_objects=True,
            ascii_format=False,
        )
    else:
        bpy.ops.export_mesh.stl(filepath=str(path), use_selection=True, ascii=False)
    print(f"EXPORTED {path}")


def validate_binary_stl(path: Path, part_id: str) -> None:
    """Validate the delivered triangulation rather than only the source mesh."""
    data = path.read_bytes()
    if len(data) < 84:
        raise RuntimeError(f"{part_id}: exported STL is shorter than its header")
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    expected_size = 84 + triangle_count * 50
    if triangle_count == 0 or len(data) != expected_size:
        raise RuntimeError(
            f"{part_id}: invalid binary STL size/triangle count "
            f"({len(data)} bytes, {triangle_count} triangles, expected {expected_size})"
        )

    facet_counts: Counter[tuple[tuple[float, float, float], ...]] = Counter()
    edge_faces: dict[
        tuple[tuple[float, float, float], tuple[float, float, float]],
        list[int],
    ] = {}
    low = [math.inf, math.inf, math.inf]
    high = [-math.inf, -math.inf, -math.inf]
    degenerate = 0
    for face_index in range(triangle_count):
        values = struct.unpack_from("<12f", data, 84 + face_index * 50)
        vertices = tuple(
            tuple(float(values[3 + vertex * 3 + axis]) for axis in range(3))
            for vertex in range(3)
        )
        if not all(math.isfinite(value) for vertex in vertices for value in vertex):
            raise RuntimeError(f"{part_id}: exported STL contains non-finite vertices")
        for vertex in vertices:
            for axis, value in enumerate(vertex):
                low[axis] = min(low[axis], value)
                high[axis] = max(high[axis], value)

        facet_counts[tuple(sorted(vertices))] += 1
        for edge in (
            (vertices[0], vertices[1]),
            (vertices[1], vertices[2]),
            (vertices[2], vertices[0]),
        ):
            edge_faces.setdefault(tuple(sorted(edge)), []).append(face_index)

        edge_a = tuple(vertices[1][axis] - vertices[0][axis] for axis in range(3))
        edge_b = tuple(vertices[2][axis] - vertices[0][axis] for axis in range(3))
        cross = (
            edge_a[1] * edge_b[2] - edge_a[2] * edge_b[1],
            edge_a[2] * edge_b[0] - edge_a[0] * edge_b[2],
            edge_a[0] * edge_b[1] - edge_a[1] * edge_b[0],
        )
        if math.sqrt(sum(component * component for component in cross)) <= 1e-8:
            degenerate += 1

    duplicates = sum(count - 1 for count in facet_counts.values() if count > 1)
    non_manifold = sum(1 for faces in edge_faces.values() if len(faces) != 2)
    adjacency: list[set[int]] = [set() for _ in range(triangle_count)]
    for faces in edge_faces.values():
        if len(faces) == 2:
            adjacency[faces[0]].add(faces[1])
            adjacency[faces[1]].add(faces[0])
    remaining = set(range(triangle_count))
    shells = 0
    while remaining:
        shells += 1
        stack = [remaining.pop()]
        while stack:
            for neighbor in adjacency[stack.pop()]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)

    dimensions = tuple(high[axis] - low[axis] for axis in range(3))
    failures: list[str] = []
    if duplicates:
        failures.append(f"{duplicates} duplicate facets")
    if degenerate:
        failures.append(f"{degenerate} zero-area facets")
    if non_manifold:
        failures.append(f"{non_manifold} non-manifold edges")
    if shells != 1:
        failures.append(f"{shells} disconnected shells")
    if abs(low[2]) > 0.001:
        failures.append(f"minimum Z is {low[2]:.6f} mm instead of zero")
    if not fits_build_volume(dimensions):
        failures.append(
            f"exported dimensions {tuple(round(value, 3) for value in dimensions)} "
            "exceed the usable print volume"
        )
    if failures:
        raise RuntimeError(f"{part_id}: exported STL validation failed: " + "; ".join(failures))
    print(
        f"STL_CHECK id={part_id} triangles={triangle_count} "
        f"dimensions={tuple(round(value, 2) for value in dimensions)} "
        "duplicates=0 degenerate=0 non_manifold=0 shells=1 min_z=0"
    )


def export_parts(output_dir: Path) -> None:
    stl_root = output_dir / "stl"
    for record in PARTS:
        category_dir = stl_root / record.category.lower()
        category_dir.mkdir(parents=True, exist_ok=True)
        duplicate = prepare_export_copy(record)
        try:
            path = category_dir / f"{record.part_id.lower()}.stl"
            export_stl(path, duplicate)
            validate_binary_stl(path, record.part_id)
        finally:
            delete_object(duplicate)


def write_manifest(output_dir: Path) -> Path:
    manifest = output_dir / "goalie_parts_manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            (
                "part_id",
                "category",
                "material",
                "local_x_mm",
                "local_y_mm",
                "local_z_mm",
                "print_x_mm",
                "print_y_mm",
                "print_z_mm",
                "fits_250x250x200",
                "print_notes",
                "assembly_notes",
                "fasteners",
                "safety",
            )
        )
        for record in PARTS:
            oriented = print_dimensions(record)
            writer.writerow(
                (
                    record.part_id,
                    record.category,
                    record.material,
                    *(f"{value:.3f}" for value in record.local_dimensions),
                    *(f"{value:.3f}" for value in oriented),
                    "YES" if fits_build_volume(oriented) else "NO",
                    record.print_notes,
                    record.assembly_notes,
                    record.fasteners,
                    record.safety,
                )
            )
    print(f"WROTE {manifest}")
    return manifest


def display_gear_strap_purchase_summary() -> tuple[int, int, int, float]:
    """Return purchase meters, cut count/range, and calculated leg-pad meters."""
    if not CFG.generate_gear or not DISPLAY_GEAR_STRAP_CUT_LENGTHS_MM:
        return (0, 0, 0, 0.0)
    leg_pad_total_mm = sum(DISPLAY_GEAR_STRAP_CUT_LENGTHS_MM)
    # Catcher, cuff, and blocker attachments retain a separate conservative
    # 4 m allowance. Add 10% cutting/adjustment waste to the complete order.
    purchase_m = math.ceil((leg_pad_total_mm + 4000.0) * 1.10 / 1000.0)
    return (
        purchase_m,
        min(DISPLAY_GEAR_STRAP_CUT_LENGTHS_MM),
        max(DISPLAY_GEAR_STRAP_CUT_LENGTHS_MM),
        leg_pad_total_mm / 1000.0,
    )


def write_hardware_bom(output_dir: Path) -> Path:
    bom = output_dir / "HARDWARE_BOM.txt"
    totals: Counter[str] = Counter()
    for connection in CONNECTIONS:
        for description, quantity in connection.hardware:
            totals[description] += quantity
    lines = [
        "Hockey goalie mannequin - configuration-derived hardware BOM",
        "",
        f"Printed parts: {len(PARTS)}",
        f"Registered connections: {len(CONNECTIONS)}",
        "",
    ]
    lines.extend(f"{quantity:4d}  {description}" for description, quantity in sorted(totals.items()))
    strap_purchase_m, strap_cut_min, strap_cut_max, leg_pad_strap_m = (
        display_gear_strap_purchase_summary()
    )
    if CFG.generate_gear:
        display_strap_line = (
            f"{strap_purchase_m} m  25 mm hook-and-loop strap for display gear "
            f"({len(DISPLAY_GEAR_STRAP_CUT_LENGTHS_MM)} leg-pad cuts of "
            f"{strap_cut_min}-{strap_cut_max} mm total {leg_pad_strap_m:.2f} m, "
            "plus 4 m glove/wrist allowance and 10% waste)"
        )
    else:
        display_strap_line = "0 m  display-gear straps omitted"
    lines.extend(
        (
            "",
            "Consumables",
            "-----------",
            "20 m  4 mm shock cord or 4.8 mm reusable zip ties" if CFG.generate_body_shell else "0 m  TPU-form lacing omitted",
            display_strap_line,
            "2 m   25 mm hook-and-loop strap for both stand foot plates" if CFG.generate_stand else "0 m  stand foot straps omitted",
            "5 m   3 mm closed-cell foam contact tape",
            "1     18 mm plywood floor sheet, recommended 900 x 900 mm" if CFG.generate_stand else "0     stand floor sheet omitted",
            "1     tether rated at least 1 kN with a structural site anchor" if CFG.generate_stand else "0     stand tether omitted",
            "",
            "Use washers on every printed bearing face. Do not substitute brittle PLA",
            "for structural parts. Re-tighten nyloc nuts after 24 hours and inspect",
            "every pivot/lock bore for whitening, splitting, or creep.",
        )
    )
    text = "\n".join(lines) + "\n"
    bom.write_text(text, encoding="utf-8")
    print(f"WROTE {bom}")
    return bom


def write_connections(output_dir: Path) -> Path:
    path = output_dir / "goalie_connections.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ("connection_id", "mate_a", "mate_b", "hardware", "assembly_notes")
        )
        for connection in CONNECTIONS:
            hardware = "; ".join(
                f"{quantity} x {description}"
                for description, quantity in connection.hardware
            )
            writer.writerow(
                (
                    connection.connection_id,
                    connection.mate_a,
                    connection.mate_b,
                    hardware,
                    connection.assembly_notes,
                )
            )
    print(f"WROTE {path}")
    return path


def write_fit_guide(output_dir: Path) -> Path:
    path = output_dir / "FIT_AND_PROTOTYPE_GUIDE.txt"
    strap_purchase_m, strap_cut_min, strap_cut_max, leg_pad_strap_m = (
        display_gear_strap_purchase_summary()
    )
    hand_form_width, hand_form_depth = derived_hand_form_width_depth()
    text = f"""Hockey goalie mannequin fit configuration (millimeters)

stature:                 {CFG.stature_mm:.1f}
shoulder width:           {CFG.shoulder_width_mm:.1f}
derived structural shoulder span: {structural_shoulder_half_width() * 2.0:.1f}
chest width / depth:      {CFG.chest_width_mm:.1f} / {CFG.chest_depth_mm:.1f}
waist width / depth:      {CFG.waist_width_mm:.1f} / {CFG.waist_depth_mm:.1f}
head width / depth:       {CFG.head_width_mm:.1f} / {CFG.head_depth_mm:.1f}
thigh circumference:      {CFG.thigh_circumference_mm:.1f}
calf circumference:       {CFG.calf_circumference_mm:.1f}
upper-arm circumference:  {CFG.upper_arm_circumference_mm:.1f}
forearm circumference:    {CFG.forearm_circumference_mm:.1f}
hand width (configured):  {CFG.hand_width_mm:.1f}
derived TPU hand-form width / depth: {hand_form_width:.1f} / {hand_form_depth:.1f}
foot width:               {CFG.foot_width_mm:.1f}
per-side TPU form allowance: {CFG.gear_clearance_mm:.1f}

``gear-clearance-mm`` is added once per side (twice across a diameter) to the
configured body dimensions. It is a soft-form/dressing allowance, not empty
air clearance. If working backward from a gear's measured internal width,
subtract twice this value before supplying the corresponding body dimension;
do not add it again. Confirm the result with the representative coupons below.
The hand form is a special case because it must surround the rigid palm bracket:
its actual outer width is the larger of configured hand width plus twice the
allowance or {HAND_FORM_MIN_WIDTH_MM:g} mm, and its actual outer depth is the larger of 0.58 times
configured hand width plus twice the allowance or {HAND_FORM_MIN_DEPTH_MM:g} mm. The derived TPU hand-form
line above is authoritative for glove/catcher fit; the subtract-twice method
cannot produce a smaller form when either structural floor controls.
The derived structural shoulder span can exceed the configured fit width when
needed to keep rigid brackets outside the chest and the relieved upper side
panels. This does not add soft-form clearance to the measured shoulder width.
Before printing the full set, print one pivot pair, one straight-lock pair,
one limb sleeve, one torso-panel corner, and one bracket/panel coupon.
Every limb sleeve is a two-half clamshell retained by the configuration-length
M5 threaded rod listed in goalie_connections.csv. The rod must pass through
both TPU saddle webs and the rigid link; use both fender washers and nyloc nuts,
leave the TPU shaped but uncrushed, and keep the caps off while centering the
bare rod. Measure from each rod tip to its adjacent outer sleeve face; the two
projections must differ by no more than {SLEEVE_ROD_CENTER_TOLERANCE_MM:g} mm.
Hold it centered while tightening, then deburr and install low-profile caps
no larger than {SLEEVE_HARDWARE_MAX_RADIUS_MM * 2.0:g} mm outside diameter and
projecting no more than {SLEEVE_ROD_CAP_PROJECTION_MM:g} mm past each rod end.
Lace all three paired holes on both long seams and recheck clamp load after
24 hours.
Optional printed knee/shin pads belong on world +Y, the goalie-facing front,
with both modeled strap runs around the mounted clamshell. Tighten both straps
evenly only until the paired integral rear saddle rails seat on the sleeve
outside the washer/cap envelope. Confirm every 4 mm seam-cord exit remains
outside the adaptive-width rails and verify the central capped-rod channel
remains clear. This configuration uses {len(DISPLAY_GEAR_STRAP_CUT_LENGTHS_MM)} leg-pad straps cut to
{strap_cut_min}-{strap_cut_max} mm ({leg_pad_strap_m:.2f} m total); buy
{strap_purchase_m} m of 25 mm hook-and-loop for all printed display gear after
the documented glove/wrist allowance and cutting waste.
For every angled wedge stack, sort its four generated M5 bolt lengths beside
the matching one-, two-, three-, and four-dimple hole groups recessed into the
terminal-facing bracket surface before covering the marks with washers.

The nominal values are adult display-fit starting points, not a claim of fit
to every brand or size. After dressing, place the assembled stand on its final
900 x 900 x 18 mm plywood sheet, install the 1 kN tether, and apply a 1.5x
expected accidental horizontal service load (minimum 150 N) at shoulder height.
No base lift, permanent deformation, fastener movement, or cracking is allowed.
Repeat the test after 24 hours under dressed static load.
"""
    path.write_text(text, encoding="utf-8")
    print(f"WROTE {path}")
    return path


def add_scene_documentation() -> None:
    scene = bpy.context.scene
    scene["generator"] = Path(__file__).name
    scene["stature_mm"] = CFG.stature_mm
    scene["print_volume_mm"] = [CFG.build_x, CFG.build_y, CFG.build_z]
    scene["part_count"] = len(PARTS)
    scene["safety"] = (
        "Display/equipment-fit mannequin only. Not human support and not certified protective gear."
    )


def save_blend(output_dir: Path) -> Path:
    path = output_dir / "hockey_goalie_mannequin_assembly.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    print(f"SAVED {path}")
    return path


def prepare_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    marker = output_dir / ".goalie_generator_output"
    if not marker.exists():
        existing_entries = sorted(path.name for path in output_dir.iterdir())
        if existing_entries:
            preview = ", ".join(existing_entries[:5])
            if len(existing_entries) > 5:
                preview += ", ..."
            raise RuntimeError(
                f"Refusing nonempty unmarked output directory {output_dir}. "
                "Choose an empty directory or one already bearing the goalie "
                f"generator marker. Existing entries: {preview}"
            )
    if marker.exists():
        for filename in (
            "goalie_parts_manifest.csv",
            "goalie_connections.csv",
            "HARDWARE_BOM.txt",
            "FIT_AND_PROTOTYPE_GUIDE.txt",
            "hockey_goalie_mannequin_assembly.blend",
        ):
            path = output_dir / filename
            if path.exists():
                path.unlink()
        stl_root = output_dir / "stl"
        if stl_root.exists():
            for path in stl_root.rglob("*.stl"):
                path.unlink()
            for directory in sorted(
                (path for path in stl_root.rglob("*") if path.is_dir()),
                key=lambda item: len(item.parts),
                reverse=True,
            ):
                if not any(directory.iterdir()):
                    directory.rmdir()
            if not any(stl_root.iterdir()):
                stl_root.rmdir()
    marker.write_text(
        "Managed output directory for hockey_goalie_mannequin_blender.py\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="goalie_output")
    parser.add_argument("--stature-mm", type=float, default=1880.0)
    parser.add_argument("--shoulder-width-mm", type=float)
    parser.add_argument("--chest-width-mm", type=float)
    parser.add_argument("--chest-depth-mm", type=float)
    parser.add_argument("--waist-width-mm", type=float)
    parser.add_argument("--waist-depth-mm", type=float)
    parser.add_argument("--head-width-mm", type=float)
    parser.add_argument("--head-depth-mm", type=float)
    parser.add_argument("--thigh-circumference-mm", type=float)
    parser.add_argument("--calf-circumference-mm", type=float)
    parser.add_argument("--upper-arm-circumference-mm", type=float)
    parser.add_argument("--forearm-circumference-mm", type=float)
    parser.add_argument("--hand-width-mm", type=float)
    parser.add_argument("--foot-width-mm", type=float)
    parser.add_argument("--gear-clearance-mm", type=float, default=8.0)
    parser.add_argument("--no-export", action="store_true")
    parser.add_argument("--no-gear", action="store_true")
    parser.add_argument("--no-body-shell", action="store_true")
    parser.add_argument("--no-stand", action="store_true")
    parser.add_argument("--no-save-blend", action="store_true")
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(arguments)


def configure_from_args(args: argparse.Namespace) -> None:
    if not 1500.0 <= args.stature_mm <= 2050.0:
        raise ValueError("--stature-mm must be between 1500 and 2050")
    CFG.stature_mm = args.stature_mm
    scale = CFG.body_scale

    def fitted_value(
        option_name: str,
        supplied: float | None,
        reference: float,
        lower: float,
        upper: float,
    ) -> float:
        value = (
            supplied
            if supplied is not None
            else min(max(reference * scale, lower), upper)
        )
        if not lower <= value <= upper:
            raise ValueError(f"--{option_name} must be between {lower:g} and {upper:g} mm")
        return value

    CFG.shoulder_width_mm = fitted_value(
        "shoulder-width-mm", args.shoulder_width_mm, 570.0, 460.0, 620.0
    )
    CFG.chest_width_mm = fitted_value(
        "chest-width-mm", args.chest_width_mm, 440.0, 320.0, 460.0
    )
    CFG.chest_depth_mm = fitted_value(
        "chest-depth-mm", args.chest_depth_mm, 190.0, 140.0, 230.0
    )
    CFG.waist_width_mm = fitted_value(
        "waist-width-mm", args.waist_width_mm, 360.0, 280.0, 440.0
    )
    CFG.waist_depth_mm = fitted_value(
        "waist-depth-mm", args.waist_depth_mm, 170.0, 130.0, 220.0
    )
    CFG.head_width_mm = fitted_value(
        "head-width-mm", args.head_width_mm, 164.0, 140.0, 205.0
    )
    CFG.head_depth_mm = fitted_value(
        "head-depth-mm", args.head_depth_mm, 190.0, 160.0, 220.0
    )
    CFG.thigh_circumference_mm = fitted_value(
        "thigh-circumference-mm", args.thigh_circumference_mm, 450.0, 320.0, 600.0
    )
    CFG.calf_circumference_mm = fitted_value(
        "calf-circumference-mm", args.calf_circumference_mm, 345.0, 250.0, 480.0
    )
    CFG.upper_arm_circumference_mm = fitted_value(
        "upper-arm-circumference-mm", args.upper_arm_circumference_mm, 365.0, 260.0, 500.0
    )
    CFG.forearm_circumference_mm = fitted_value(
        "forearm-circumference-mm", args.forearm_circumference_mm, 295.0, 210.0, 420.0
    )
    CFG.hand_width_mm = fitted_value(
        "hand-width-mm", args.hand_width_mm, 92.0, 70.0, 125.0
    )
    CFG.foot_width_mm = fitted_value(
        "foot-width-mm", args.foot_width_mm, 105.0, 80.0, 135.0
    )
    if not 2.0 <= args.gear_clearance_mm <= 15.0:
        raise ValueError("--gear-clearance-mm must be between 2 and 15")
    CFG.gear_clearance_mm = args.gear_clearance_mm
    usable_xy = min(CFG.build_x, CFG.build_y) - CFG.build_margin
    head_form_width = CFG.head_width_mm + CFG.gear_clearance_mm * 2.0
    head_form_depth = CFG.head_depth_mm + CFG.gear_clearance_mm * 2.0
    if max(head_form_width, head_form_depth) > usable_xy:
        raise ValueError(
            "Head dimensions plus twice --gear-clearance-mm must not exceed "
            f"the {usable_xy:g} mm usable XY print span; requested "
            f"{head_form_width:.1f} x {head_form_depth:.1f} mm"
        )
    CFG.output_dir = Path(args.output_dir).expanduser().resolve()
    CFG.export_stl = not args.no_export
    CFG.generate_gear = not args.no_gear and not args.no_body_shell
    CFG.generate_body_shell = not args.no_body_shell
    CFG.generate_stand = not args.no_stand
    CFG.save_blend = not args.no_save_blend


def main() -> list[PartRecord]:
    args = parse_args()
    configure_from_args(args)
    prepare_output_dir(CFG.output_dir)
    clear_scene()
    set_units()
    setup_materials()
    for collection_name in (
        "01_STRUCTURE_PETG_ABS",
        "02_BODY_FORMS_TPU",
        "03_DISPLAY_GOALIE_GEAR_TPU",
        "04_STAND_PETG_ABS",
    ):
        ensure_collection(collection_name)

    build_pelvis_and_torso()
    lower_chains = build_lower_body()
    upper_chains = build_upper_body()
    build_head_and_neck()
    if CFG.generate_gear:
        build_leg_pad_gear(lower_chains)
        build_chest_gear()
        build_glove_gear(upper_chains)
    if CFG.generate_stand:
        build_stand()

    validate_parts()
    validate_assembly()
    add_scene_documentation()
    write_manifest(CFG.output_dir)
    write_connections(CFG.output_dir)
    write_hardware_bom(CFG.output_dir)
    write_fit_guide(CFG.output_dir)
    if CFG.export_stl:
        export_parts(CFG.output_dir)
    if CFG.save_blend:
        save_blend(CFG.output_dir)
    print(
        "GOALIE_BUILD_COMPLETE "
        f"parts={len(PARTS)} stature_mm={CFG.stature_mm:.1f} "
        f"output={CFG.output_dir}"
    )
    return PARTS


if __name__ == "__main__":
    main()
