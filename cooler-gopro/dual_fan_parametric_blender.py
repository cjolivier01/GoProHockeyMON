"""Parametric dual-fan holder with a two-hole camera mount for Blender.

Run inside Blender:

    blender --background --python dual_fan_parametric_blender.py

All dimensions are millimeters. Edit the values in CONFIG, then run the
script. The default dimensions follow ``gopro-dual-fan.stl`` while keeping
the geometry centered and easy to modify.

Axes:
    X - across the two fans
    Y - vertical in the fan plane
    Z - fan depth; the camera mount projects toward negative Z
"""

from __future__ import annotations

import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector


# ---------------------------------------------------------------------------
# CONFIG

CLEAR_SCENE = True
EXPORT_STL = False
EXPORT_STL_PATH = "gopro_dual_fan_parametric.stl"

# Mesh and boolean quality.
CYLINDER_SEGMENTS = 96
CORNER_SEGMENTS = 10
BOOLEAN_SOLVER = "EXACT"
BOOLEAN_OVERLAP = 0.08
UNION_ALL_PARTS = True
DEBUG_BOOLEAN_STEPS = False
CLEAN_COINCIDENT_FACE_TOLERANCE = 1.0e-5

# Fan cages. Distances are measured independently from the stalk centerline.
FAN_1_DISTANCE_FROM_CENTER = 52.5
FAN_2_DISTANCE_FROM_CENTER = 52.5
FAN_FRAME_SIZE = 66.7
FAN_FRAME_DEPTH = 14.7
FAN_FRAME_WALL = 3.0
FAN_FRAME_CORNER_RADIUS = 2.5
GRILL_THICKNESS = 2.8

# Fan angles relative to the unrotated support, in Blender XYZ Euler degrees.
# Fan 1 is on the negative-X (left) side; fan 2 is on positive X (right).
FAN_1_ROTATION_DEG = (0.0, 0.0, 0.0)
FAN_2_ROTATION_DEG = (0.0, 0.0, 0.0)

# "support_contact" rotates around the lower-inner connection to the support.
# "fan_center" rotates around the geometric center of each fan cage.
FAN_ROTATION_PIVOT_MODE = "support_contact"
FAN_ROTATION_PIVOT_INWARD_X = 17.0
FAN_ROTATION_PIVOT_ABOVE_BOTTOM_Y = 1.0
FAN_ROTATION_PIVOT_Z = 2.25

# Fan airflow grille.
AIRFLOW_DIAMETER = 61.4
GRILL_BAR_WIDTH = 2.0
GRILL_CENTER_DISK_DIAMETER = 21.4
GRILL_RING_CENTER_RADII = (16.7, 23.7)
GRILL_RING_WIDTH = 2.0
GRILL_CONNECTION_OVERLAP = 1.0

# Four fan screw holes in each cage.
FAN_HOLE_SPACING = 50.0
FAN_HOLE_DIAMETER = 4.2
FAN_HOLE_COUNTERSINK_ENABLED = True
FAN_HOLE_COUNTERSINK_DIAMETER = 7.6
FAN_HOLE_COUNTERSINK_DEPTH = 2.2
FAN_HOLE_COLLARS_ENABLED = True
FAN_HOLE_COLLAR_DIAMETER = 6.0
FAN_HOLE_COLLAR_HEIGHT = 0.5

# Optional U-shaped fan-wire exit cut into one wall from the open back. The
# offset is local to each fan and runs along the selected wall. On TOP/BOTTOM,
# positive values move right, so the defaults put a slot at each bottom-right.
FAN_WIRE_SLOT_ENABLED = True
FAN_WIRE_SLOT_SIDE = "BOTTOM"  # "TOP", "BOTTOM", "LEFT", or "RIGHT"
FAN_WIRE_SLOT_WIDTH = 5.0
FAN_WIRE_SLOT_DEPTH = 9.0
FAN_WIRE_SLOT_OFFSET = 22.0

# Twisted support joining the stalk to the two fan cages.
SUPPORT_ENABLED = True
SUPPORT_THICKNESS = 4.5
SUPPORT_HUB_WIDTH = 76.2
SUPPORT_HUB_DEPTH_Y = 10.0
SUPPORT_HUB_BELOW_FAN_Y = 17.2
SUPPORT_ARM_START_X = 18.0
SUPPORT_ARM_CENTER_WIDTH = 18.0
SUPPORT_ARM_FAN_WIDTH = 22.0
SUPPORT_ARM_HUB_INSERT_Y = 2.0
SUPPORT_ARM_FAN_INSERT_Y = 4.0
SUPPORT_ARM_SECTIONS = 10

# Stalk projecting from the support toward the camera mount.
STALK_ENABLED = True
STALK_WIDTH = 16.1
STALK_DEPTH_Y = 7.25
STALK_LENGTH_Z = 31.2
STALK_BOTTOM_Y_OVERHANG = 0.5

# Two-hole block at the end of the stalk.
MOUNT_BLOCK_ENABLED = True
MOUNT_BLOCK_WIDTH = 28.45
MOUNT_BLOCK_HEIGHT_Z = 18.8
MOUNT_BLOCK_DEPTH_Y = 7.25
MOUNT_BLOCK_OVERLAP = 0.15
MOUNT_HOLE_SPACING = 12.0
MOUNT_HOLE_DIAMETER = 4.2
MOUNT_COUNTERSINK_ENABLED = True
MOUNT_COUNTERSINK_DIAMETER = 7.2
MOUNT_COUNTERSINK_DEPTH = 3.6


# ---------------------------------------------------------------------------
# Basic mesh helpers


def validate_config() -> None:
    positive = {
        "FAN_1_DISTANCE_FROM_CENTER": FAN_1_DISTANCE_FROM_CENTER,
        "FAN_2_DISTANCE_FROM_CENTER": FAN_2_DISTANCE_FROM_CENTER,
        "FAN_FRAME_SIZE": FAN_FRAME_SIZE,
        "FAN_FRAME_DEPTH": FAN_FRAME_DEPTH,
        "FAN_FRAME_WALL": FAN_FRAME_WALL,
        "GRILL_THICKNESS": GRILL_THICKNESS,
        "AIRFLOW_DIAMETER": AIRFLOW_DIAMETER,
        "FAN_HOLE_DIAMETER": FAN_HOLE_DIAMETER,
        "FAN_WIRE_SLOT_WIDTH": FAN_WIRE_SLOT_WIDTH,
        "FAN_WIRE_SLOT_DEPTH": FAN_WIRE_SLOT_DEPTH,
        "SUPPORT_THICKNESS": SUPPORT_THICKNESS,
        "SUPPORT_HUB_WIDTH": SUPPORT_HUB_WIDTH,
        "SUPPORT_HUB_DEPTH_Y": SUPPORT_HUB_DEPTH_Y,
        "SUPPORT_HUB_BELOW_FAN_Y": SUPPORT_HUB_BELOW_FAN_Y,
        "SUPPORT_ARM_CENTER_WIDTH": SUPPORT_ARM_CENTER_WIDTH,
        "SUPPORT_ARM_FAN_WIDTH": SUPPORT_ARM_FAN_WIDTH,
        "SUPPORT_ARM_HUB_INSERT_Y": SUPPORT_ARM_HUB_INSERT_Y,
        "SUPPORT_ARM_FAN_INSERT_Y": SUPPORT_ARM_FAN_INSERT_Y,
        "STALK_WIDTH": STALK_WIDTH,
        "STALK_DEPTH_Y": STALK_DEPTH_Y,
        "STALK_LENGTH_Z": STALK_LENGTH_Z,
        "MOUNT_BLOCK_WIDTH": MOUNT_BLOCK_WIDTH,
        "MOUNT_BLOCK_HEIGHT_Z": MOUNT_BLOCK_HEIGHT_Z,
        "MOUNT_BLOCK_DEPTH_Y": MOUNT_BLOCK_DEPTH_Y,
        "MOUNT_HOLE_DIAMETER": MOUNT_HOLE_DIAMETER,
    }
    for name, value in positive.items():
        if value <= 0:
            raise ValueError(f"{name} must be positive")

    if FAN_FRAME_WALL * 2.0 >= FAN_FRAME_SIZE:
        raise ValueError("FAN_FRAME_WALL leaves no opening")
    if not 0 < GRILL_THICKNESS < FAN_FRAME_DEPTH:
        raise ValueError("GRILL_THICKNESS must be less than FAN_FRAME_DEPTH")
    if AIRFLOW_DIAMETER >= FAN_FRAME_SIZE:
        raise ValueError("AIRFLOW_DIAMETER must be smaller than FAN_FRAME_SIZE")
    if GRILL_CENTER_DISK_DIAMETER >= AIRFLOW_DIAMETER:
        raise ValueError("GRILL_CENTER_DISK_DIAMETER must fit inside the airflow opening")

    if FAN_WIRE_SLOT_SIDE not in {"TOP", "BOTTOM", "LEFT", "RIGHT"}:
        raise ValueError(
            "FAN_WIRE_SLOT_SIDE must be TOP, BOTTOM, LEFT, or RIGHT"
        )
    if FAN_WIRE_SLOT_DEPTH >= FAN_FRAME_DEPTH - GRILL_THICKNESS:
        raise ValueError(
            "FAN_WIRE_SLOT_DEPTH must leave material between the slot and grille"
        )
    slot_half_width = FAN_WIRE_SLOT_WIDTH / 2.0
    straight_wall_half_length = FAN_FRAME_SIZE / 2.0 - FAN_FRAME_CORNER_RADIUS
    if abs(FAN_WIRE_SLOT_OFFSET) + slot_half_width > straight_wall_half_length:
        raise ValueError(
            "FAN_WIRE_SLOT_OFFSET and FAN_WIRE_SLOT_WIDTH must keep the slot "
            "inside the straight portion of its wall"
        )

    airflow_radius = AIRFLOW_DIAMETER / 2.0
    for radius in GRILL_RING_CENTER_RADII:
        if radius <= GRILL_RING_WIDTH / 2.0:
            raise ValueError("Each grille ring radius must exceed half its width")
        if radius + GRILL_RING_WIDTH / 2.0 >= airflow_radius:
            raise ValueError("Each grille ring must fit inside AIRFLOW_DIAMETER")

    fan_hole_extent = FAN_HOLE_SPACING / 2.0 + FAN_HOLE_COUNTERSINK_DIAMETER / 2.0
    if fan_hole_extent >= FAN_FRAME_SIZE / 2.0:
        raise ValueError("Fan holes or countersinks do not fit inside the fan frame")

    mount_hole_extent = MOUNT_HOLE_SPACING / 2.0 + MOUNT_COUNTERSINK_DIAMETER / 2.0
    if mount_hole_extent >= MOUNT_BLOCK_WIDTH / 2.0:
        raise ValueError("Mount holes or countersinks do not fit inside MOUNT_BLOCK_WIDTH")
    if MOUNT_COUNTERSINK_DIAMETER >= MOUNT_BLOCK_HEIGHT_Z:
        raise ValueError("Mount countersinks do not fit inside MOUNT_BLOCK_HEIGHT_Z")

    if FAN_ROTATION_PIVOT_MODE not in {"support_contact", "fan_center"}:
        raise ValueError('FAN_ROTATION_PIVOT_MODE must be "support_contact" or "fan_center"')
    if not 0.0 <= FAN_ROTATION_PIVOT_INWARD_X < FAN_FRAME_SIZE / 2.0:
        raise ValueError("FAN_ROTATION_PIVOT_INWARD_X must remain inside the fan frame")
    if SUPPORT_ARM_SECTIONS < 2:
        raise ValueError("SUPPORT_ARM_SECTIONS must be at least 2")
    if SUPPORT_ARM_HUB_INSERT_Y >= SUPPORT_HUB_DEPTH_Y:
        raise ValueError("SUPPORT_ARM_HUB_INSERT_Y must be less than SUPPORT_HUB_DEPTH_Y")
    if SUPPORT_ARM_FAN_INSERT_Y >= FAN_FRAME_SIZE / 2.0:
        raise ValueError("SUPPORT_ARM_FAN_INSERT_Y must remain inside the fan frame")
    for name, rotation in (
        ("FAN_1_ROTATION_DEG", FAN_1_ROTATION_DEG),
        ("FAN_2_ROTATION_DEG", FAN_2_ROTATION_DEG),
    ):
        if len(rotation) != 3 or not all(math.isfinite(value) for value in rotation):
            raise ValueError(f"{name} must contain three finite XYZ angles")


def set_units() -> None:
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 0.001


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def recalc_normals(obj) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def create_mesh_object(name: str, vertices, faces):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(clean_customdata=True)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    recalc_normals(obj)
    return obj


def fan_rotation_pivot(center_x: float):
    if FAN_ROTATION_PIVOT_MODE == "fan_center":
        return (center_x, 0.0, FAN_FRAME_DEPTH / 2.0)

    inward_sign = 1.0 if center_x < 0.0 else -1.0
    return (
        center_x + inward_sign * FAN_ROTATION_PIVOT_INWARD_X,
        -FAN_FRAME_SIZE / 2.0 + FAN_ROTATION_PIVOT_ABOVE_BOTTOM_Y,
        FAN_ROTATION_PIVOT_Z,
    )


def fan_rotation_quaternion(rotation_deg):
    angles = tuple(math.radians(value) for value in rotation_deg)
    return Euler(angles, "XYZ").to_quaternion()


def transform_fan_point(point, center_x: float, rotation_deg):
    pivot = Vector(fan_rotation_pivot(center_x))
    rotation = fan_rotation_quaternion(rotation_deg)
    return pivot + rotation @ (Vector(point) - pivot)


def rotate_fan_cage(obj, center_x: float, rotation_deg) -> None:
    if all(abs(value) < 1.0e-12 for value in rotation_deg):
        return

    pivot = fan_rotation_pivot(center_x)
    rotation = fan_rotation_quaternion(rotation_deg).to_matrix().to_4x4()
    transform = (
        Matrix.Translation(pivot)
        @ rotation
        @ Matrix.Translation(tuple(-value for value in pivot))
    )
    obj.data.transform(transform)
    obj.data.update()
    recalc_normals(obj)


def rounded_rectangle_loop(width: float, height: float, radius: float, segments: int):
    radius = min(max(radius, 0.0), width / 2.0, height / 2.0)
    if radius == 0.0:
        return [
            (-width / 2.0, -height / 2.0),
            (width / 2.0, -height / 2.0),
            (width / 2.0, height / 2.0),
            (-width / 2.0, height / 2.0),
        ]

    points = []
    corners = [
        (width / 2.0 - radius, height / 2.0 - radius, 0.0, 90.0),
        (-width / 2.0 + radius, height / 2.0 - radius, 90.0, 180.0),
        (-width / 2.0 + radius, -height / 2.0 + radius, 180.0, 270.0),
        (width / 2.0 - radius, -height / 2.0 + radius, 270.0, 360.0),
    ]
    for corner_index, (cx, cy, a0, a1) in enumerate(corners):
        for i in range(segments + 1):
            if corner_index == len(corners) - 1 and i == segments:
                continue
            angle = math.radians(a0 + (a1 - a0) * i / segments)
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def polygon_prism(name: str, loop, z0: float, z1: float, offset=(0.0, 0.0)):
    if z1 <= z0:
        raise ValueError(f"{name}: z1 must be greater than z0")
    ox, oy = offset
    points = [(x + ox, y + oy) for x, y in loop]
    count = len(points)
    vertices = [(x, y, z0) for x, y in points]
    vertices.extend((x, y, z1) for x, y in points)
    center_x = sum(x for x, _ in points) / count
    center_y = sum(y for _, y in points) / count
    vertices.extend(((center_x, center_y, z0), (center_x, center_y, z1)))
    bottom_center = count * 2
    top_center = bottom_center + 1

    faces = []
    for i in range(count):
        j = (i + 1) % count
        faces.append([i, j, count + j, count + i])
        faces.append([bottom_center, j, i])
        faces.append([top_center, count + i, count + j])
    return create_mesh_object(name, vertices, faces)


def rounded_rectangle_prism(
    name: str,
    width: float,
    height: float,
    radius: float,
    z0: float,
    z1: float,
    center_x: float = 0.0,
    center_y: float = 0.0,
):
    loop = rounded_rectangle_loop(width, height, radius, CORNER_SEGMENTS)
    return polygon_prism(name, loop, z0, z1, offset=(center_x, center_y))


def annular_prism(
    name: str,
    center_x: float,
    center_y: float,
    inner_radius: float,
    outer_radius: float,
    z0: float,
    z1: float,
):
    count = CYLINDER_SEGMENTS
    outer = []
    inner = []
    for i in range(count):
        angle = 2.0 * math.pi * i / count
        c = math.cos(angle)
        s = math.sin(angle)
        outer.append((center_x + outer_radius * c, center_y + outer_radius * s))
        inner.append((center_x + inner_radius * c, center_y + inner_radius * s))

    vertices = [(x, y, z0) for x, y in outer]
    vertices.extend((x, y, z1) for x, y in outer)
    vertices.extend((x, y, z0) for x, y in inner)
    vertices.extend((x, y, z1) for x, y in inner)

    def outer_bottom(i):
        return i % count

    def outer_top(i):
        return count + i % count

    def inner_bottom(i):
        return count * 2 + i % count

    def inner_top(i):
        return count * 3 + i % count

    faces = []
    for i in range(count):
        j = i + 1
        faces.append([outer_bottom(i), outer_bottom(j), outer_top(j), outer_top(i)])
        faces.append([inner_bottom(i), inner_top(i), inner_top(j), inner_bottom(j)])
        faces.append([outer_bottom(j), outer_bottom(i), inner_bottom(i), inner_bottom(j)])
        faces.append([outer_top(i), outer_top(j), inner_top(j), inner_top(i)])
    return create_mesh_object(name, vertices, faces)


def add_box(name: str, dimensions, location):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def add_cylinder_z(name: str, radius: float, z0: float, z1: float, x=0.0, y=0.0):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=CYLINDER_SEGMENTS,
        radius=radius,
        depth=z1 - z0,
        location=(x, y, (z0 + z1) / 2.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    return obj


def add_cylinder_y(name: str, radius: float, y0: float, y1: float, x=0.0, z=0.0):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=CYLINDER_SEGMENTS,
        radius=radius,
        depth=y1 - y0,
        location=(x, (y0 + y1) / 2.0, z),
        rotation=(math.pi / 2.0, 0.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    return obj


def add_cone_z(
    name: str,
    bottom_radius: float,
    top_radius: float,
    z0: float,
    z1: float,
    x=0.0,
    y=0.0,
):
    bpy.ops.mesh.primitive_cone_add(
        vertices=CYLINDER_SEGMENTS,
        radius1=bottom_radius,
        radius2=top_radius,
        depth=z1 - z0,
        location=(x, y, (z0 + z1) / 2.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    return obj


def add_cone_y_positive(
    name: str,
    wide_radius: float,
    narrow_radius: float,
    y_inner: float,
    y_outer: float,
    x=0.0,
    z=0.0,
):
    # Rotating +90 degrees around X maps the cone's radius1 end to +Y.
    bpy.ops.mesh.primitive_cone_add(
        vertices=CYLINDER_SEGMENTS,
        radius1=wide_radius,
        radius2=narrow_radius,
        depth=y_outer - y_inner,
        location=(x, (y_inner + y_outer) / 2.0, z),
        rotation=(math.pi / 2.0, 0.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    return obj


# ---------------------------------------------------------------------------
# Boolean helpers


def select_only(obj) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def join_disconnected_tools(name: str, objects):
    if len(objects) == 1:
        objects[0].name = name
        return objects[0]
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    objects[0].name = name
    return objects[0]


def apply_boolean(base, tool, operation: str, label: str):
    select_only(base)
    modifier = base.modifiers.new(label, "BOOLEAN")
    modifier.operation = operation
    modifier.object = tool
    if hasattr(modifier, "solver"):
        modifier.solver = BOOLEAN_SOLVER
    if hasattr(modifier, "use_self"):
        modifier.use_self = False
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(tool, do_unlink=True)
    recalc_normals(base)
    if DEBUG_BOOLEAN_STEPS:
        print(
            f"{label}: operation={operation} "
            f"non_manifold_edges={non_manifold_edge_count(base)}"
        )
    return base


def boolean_union(base, part, label="Union"):
    return apply_boolean(base, part, "UNION", label + "_" + part.name)


def boolean_difference(base, tools, label="Cut"):
    tool = join_disconnected_tools(label + "_Tools", list(tools))
    return apply_boolean(base, tool, "DIFFERENCE", label)


# ---------------------------------------------------------------------------
# Parametric parts


def fan_hole_centers(center_x: float):
    half = FAN_HOLE_SPACING / 2.0
    return [(center_x + sx * half, sy * half) for sx in (-1.0, 1.0) for sy in (-1.0, 1.0)]


def cut_fan_wire_slot(cage, center_x: float, index: int) -> None:
    if not FAN_WIRE_SLOT_ENABLED:
        return

    # Extend through the selected wall and beyond the open back so the result is
    # a true U-shaped exit rather than an enclosed pocket.
    cutter_depth = FAN_WIRE_SLOT_DEPTH + 2.0 * BOOLEAN_OVERLAP
    cutter_z = FAN_FRAME_DEPTH - FAN_WIRE_SLOT_DEPTH / 2.0 + BOOLEAN_OVERLAP
    if FAN_WIRE_SLOT_SIDE in {"TOP", "BOTTOM"}:
        side_sign = 1.0 if FAN_WIRE_SLOT_SIDE == "TOP" else -1.0
        cutter_dimensions = (
            FAN_WIRE_SLOT_WIDTH,
            FAN_FRAME_WALL + 2.0 * BOOLEAN_OVERLAP,
            cutter_depth,
        )
        cutter_location = (
            center_x + FAN_WIRE_SLOT_OFFSET,
            side_sign * (FAN_FRAME_SIZE / 2.0 - FAN_FRAME_WALL / 2.0),
            cutter_z,
        )
    else:
        side_sign = 1.0 if FAN_WIRE_SLOT_SIDE == "RIGHT" else -1.0
        cutter_dimensions = (
            FAN_FRAME_WALL + 2.0 * BOOLEAN_OVERLAP,
            FAN_WIRE_SLOT_WIDTH,
            cutter_depth,
        )
        cutter_location = (
            center_x + side_sign * (FAN_FRAME_SIZE / 2.0 - FAN_FRAME_WALL / 2.0),
            FAN_WIRE_SLOT_OFFSET,
            cutter_z,
        )
    cutter = add_box(
        f"Fan_{index}_Wire_Slot",
        cutter_dimensions,
        cutter_location,
    )
    boolean_difference(cage, [cutter], f"Fan_{index}_Wire_Slot_Cut")


def create_fan_cage(center_x: float, index: int):
    prefix = f"Fan_{index}"

    grill = rounded_rectangle_prism(
        prefix + "_Grill_Frame",
        FAN_FRAME_SIZE,
        FAN_FRAME_SIZE,
        FAN_FRAME_CORNER_RADIUS,
        0.0,
        GRILL_THICKNESS,
        center_x=center_x,
    )
    grill_cutters = [
        add_cylinder_z(
            prefix + "_Airflow_Cut",
            AIRFLOW_DIAMETER / 2.0,
            -BOOLEAN_OVERLAP,
            GRILL_THICKNESS + BOOLEAN_OVERLAP,
            x=center_x,
        )
    ]
    boolean_difference(grill, grill_cutters, prefix + "_Openings")

    housing = rounded_rectangle_prism(
        prefix + "_Housing",
        FAN_FRAME_SIZE,
        FAN_FRAME_SIZE,
        FAN_FRAME_CORNER_RADIUS,
        GRILL_THICKNESS - BOOLEAN_OVERLAP,
        FAN_FRAME_DEPTH,
        center_x=center_x,
    )
    inner_size = FAN_FRAME_SIZE - 2.0 * FAN_FRAME_WALL
    housing_cut = add_box(
        prefix + "_Housing_Opening",
        (inner_size, inner_size, FAN_FRAME_DEPTH - GRILL_THICKNESS + 2.0 * BOOLEAN_OVERLAP),
        (center_x, 0.0, (FAN_FRAME_DEPTH + GRILL_THICKNESS) / 2.0),
    )
    boolean_difference(housing, [housing_cut], prefix + "_Housing_Cut")
    boolean_union(grill, housing, prefix + "_Housing_Union")

    bar_length = AIRFLOW_DIAMETER + 2.0 * GRILL_CONNECTION_OVERLAP
    horizontal_bar = add_box(
        prefix + "_Horizontal_Bar",
        (bar_length, GRILL_BAR_WIDTH, GRILL_THICKNESS),
        (center_x, 0.0, GRILL_THICKNESS / 2.0),
    )
    vertical_bar = add_box(
        prefix + "_Vertical_Bar",
        (GRILL_BAR_WIDTH, bar_length, GRILL_THICKNESS),
        (center_x, 0.0, GRILL_THICKNESS / 2.0),
    )
    boolean_union(grill, horizontal_bar, prefix + "_Horizontal_Bar_Union")
    boolean_union(grill, vertical_bar, prefix + "_Vertical_Bar_Union")

    for ring_index, radius in enumerate(GRILL_RING_CENTER_RADII, start=1):
        ring = annular_prism(
            f"{prefix}_Ring_{ring_index}",
            center_x,
            0.0,
            radius - GRILL_RING_WIDTH / 2.0,
            radius + GRILL_RING_WIDTH / 2.0,
            0.0,
            GRILL_THICKNESS,
        )
        boolean_union(grill, ring, prefix + f"_Ring_{ring_index}_Union")

    center_disk = add_cylinder_z(
        prefix + "_Center_Disk",
        GRILL_CENTER_DISK_DIAMETER / 2.0,
        0.0,
        GRILL_THICKNESS,
        x=center_x,
    )
    boolean_union(grill, center_disk, prefix + "_Center_Disk_Union")

    if FAN_HOLE_COLLARS_ENABLED and FAN_HOLE_COLLAR_HEIGHT > 0.0:
        for collar_index, (x, y) in enumerate(fan_hole_centers(center_x), start=1):
            collar = add_cylinder_z(
                f"{prefix}_Screw_Collar_{collar_index}",
                FAN_HOLE_COLLAR_DIAMETER / 2.0,
                GRILL_THICKNESS - BOOLEAN_OVERLAP,
                GRILL_THICKNESS + FAN_HOLE_COLLAR_HEIGHT,
                x=x,
                y=y,
            )
            boolean_union(grill, collar, prefix + f"_Screw_Collar_{collar_index}_Union")

    # Drill after adding the optional solid collars. This avoids coincident
    # cylindrical surfaces between pre-cut holes and annular collar meshes.
    screw_hole_top = GRILL_THICKNESS
    if FAN_HOLE_COLLARS_ENABLED:
        screw_hole_top += FAN_HOLE_COLLAR_HEIGHT
    screw_hole_cuts = []
    for hole_index, (x, y) in enumerate(fan_hole_centers(center_x), start=1):
        screw_hole_cuts.append(
            add_cylinder_z(
                f"{prefix}_Screw_Cut_{hole_index}",
                FAN_HOLE_DIAMETER / 2.0,
                -BOOLEAN_OVERLAP,
                screw_hole_top + BOOLEAN_OVERLAP,
                x=x,
                y=y,
            )
        )
    boolean_difference(grill, screw_hole_cuts, prefix + "_Screw_Holes")

    if FAN_HOLE_COUNTERSINK_ENABLED and FAN_HOLE_COUNTERSINK_DEPTH > 0.0:
        countersinks = []
        for hole_index, (x, y) in enumerate(fan_hole_centers(center_x), start=1):
            countersinks.append(
                add_cone_z(
                    f"{prefix}_Screw_Countersink_{hole_index}",
                    FAN_HOLE_COUNTERSINK_DIAMETER / 2.0,
                    FAN_HOLE_DIAMETER / 2.0,
                    -BOOLEAN_OVERLAP,
                    FAN_HOLE_COUNTERSINK_DEPTH,
                    x=x,
                    y=y,
                )
            )
        boolean_difference(grill, countersinks, prefix + "_Countersinks")

    cut_fan_wire_slot(grill, center_x, index)

    grill.name = prefix + "_Cage"
    grill.data.name = prefix + "_Cage_Mesh"
    return grill


def support_bottom_y() -> float:
    return -FAN_FRAME_SIZE / 2.0 - SUPPORT_HUB_BELOW_FAN_Y


def support_hub_top_y() -> float:
    return support_bottom_y() + SUPPORT_HUB_DEPTH_Y


def create_twisted_support_arm(name: str, side: float, fan_x: float, rotation_deg):
    start = Vector(
        (
            side * SUPPORT_ARM_START_X,
            support_hub_top_y() - SUPPORT_ARM_HUB_INSERT_Y,
            SUPPORT_THICKNESS / 2.0,
        )
    )
    inward_sign = -side
    end_unrotated = (
        fan_x + inward_sign * FAN_ROTATION_PIVOT_INWARD_X,
        -FAN_FRAME_SIZE / 2.0 + SUPPORT_ARM_FAN_INSERT_Y,
        FAN_ROTATION_PIVOT_Z,
    )
    end = transform_fan_point(end_unrotated, fan_x, rotation_deg)
    target_rotation = fan_rotation_quaternion(rotation_deg)
    identity = Quaternion((1.0, 0.0, 0.0, 0.0))

    vertices = []
    for section in range(SUPPORT_ARM_SECTIONS + 1):
        t = section / SUPPORT_ARM_SECTIONS
        smooth_t = t * t * (3.0 - 2.0 * t)
        center = start.lerp(end, t)
        orientation = identity.slerp(target_rotation, smooth_t)
        x_axis = orientation @ Vector((1.0, 0.0, 0.0))
        z_axis = orientation @ Vector((0.0, 0.0, 1.0))
        width = SUPPORT_ARM_CENTER_WIDTH + (
            SUPPORT_ARM_FAN_WIDTH - SUPPORT_ARM_CENTER_WIDTH
        ) * smooth_t
        half_width = width / 2.0
        half_thickness = SUPPORT_THICKNESS / 2.0
        vertices.extend(
            (
                center - x_axis * half_width - z_axis * half_thickness,
                center + x_axis * half_width - z_axis * half_thickness,
                center + x_axis * half_width + z_axis * half_thickness,
                center - x_axis * half_width + z_axis * half_thickness,
            )
        )

    faces = []
    for section in range(SUPPORT_ARM_SECTIONS):
        current = section * 4
        following = (section + 1) * 4
        for corner in range(4):
            next_corner = (corner + 1) % 4
            faces.append(
                [
                    current + corner,
                    following + corner,
                    following + next_corner,
                    current + next_corner,
                ]
            )
    faces.append([3, 2, 1, 0])
    last = SUPPORT_ARM_SECTIONS * 4
    faces.append([last, last + 1, last + 2, last + 3])
    return create_mesh_object(name, vertices, faces)


def create_support(fan_1_x: float, fan_2_x: float):
    bottom_y = support_bottom_y()
    top_y = support_hub_top_y()
    loop = [
        (-SUPPORT_HUB_WIDTH / 2.0, bottom_y),
        (SUPPORT_HUB_WIDTH / 2.0, bottom_y),
        (SUPPORT_HUB_WIDTH / 2.0, top_y),
        (-SUPPORT_HUB_WIDTH / 2.0, top_y),
    ]
    hub = polygon_prism("Fan_Support_Hub", loop, 0.0, SUPPORT_THICKNESS)
    fan_1_arm = create_twisted_support_arm(
        "Fan_1_Twisted_Support",
        -1.0,
        fan_1_x,
        FAN_1_ROTATION_DEG,
    )
    fan_2_arm = create_twisted_support_arm(
        "Fan_2_Twisted_Support",
        1.0,
        fan_2_x,
        FAN_2_ROTATION_DEG,
    )
    boolean_union(hub, fan_1_arm, "Support_Arm_1_Union")
    boolean_union(hub, fan_2_arm, "Support_Arm_2_Union")
    hub.name = "Twisted_Fan_Support"
    hub.data.name = "Twisted_Fan_Support_Mesh"
    return hub


def stalk_center_y() -> float:
    return support_bottom_y() + STALK_DEPTH_Y / 2.0 - STALK_BOTTOM_Y_OVERHANG


def create_stalk():
    z0 = -STALK_LENGTH_Z
    z1 = BOOLEAN_OVERLAP
    return add_box(
        "Mount_Stalk",
        (STALK_WIDTH, STALK_DEPTH_Y, z1 - z0),
        (0.0, stalk_center_y(), (z0 + z1) / 2.0),
    )


def create_mount_block():
    top_z = -STALK_LENGTH_Z + MOUNT_BLOCK_OVERLAP
    bottom_z = top_z - MOUNT_BLOCK_HEIGHT_Z
    center_z = (top_z + bottom_z) / 2.0
    center_y = stalk_center_y()
    block = add_box(
        "Dual_Hole_Mount_Block",
        (MOUNT_BLOCK_WIDTH, MOUNT_BLOCK_DEPTH_Y, MOUNT_BLOCK_HEIGHT_Z),
        (0.0, center_y, center_z),
    )

    through_cuts = []
    for hole_index, x in enumerate((-MOUNT_HOLE_SPACING / 2.0, MOUNT_HOLE_SPACING / 2.0), start=1):
        through_cuts.append(
            add_cylinder_y(
                f"Mount_Through_Hole_{hole_index}",
                MOUNT_HOLE_DIAMETER / 2.0,
                center_y - MOUNT_BLOCK_DEPTH_Y / 2.0 - BOOLEAN_OVERLAP,
                center_y + MOUNT_BLOCK_DEPTH_Y / 2.0 + BOOLEAN_OVERLAP,
                x=x,
                z=center_z,
            )
        )
    boolean_difference(block, through_cuts, "Mount_Through_Holes")

    if MOUNT_COUNTERSINK_ENABLED and MOUNT_COUNTERSINK_DEPTH > 0.0:
        outer_y = center_y + MOUNT_BLOCK_DEPTH_Y / 2.0 + BOOLEAN_OVERLAP
        inner_y = outer_y - MOUNT_COUNTERSINK_DEPTH - BOOLEAN_OVERLAP
        countersinks = []
        for hole_index, x in enumerate((-MOUNT_HOLE_SPACING / 2.0, MOUNT_HOLE_SPACING / 2.0), start=1):
            countersinks.append(
                add_cone_y_positive(
                    f"Mount_Countersink_{hole_index}",
                    MOUNT_COUNTERSINK_DIAMETER / 2.0,
                    MOUNT_HOLE_DIAMETER / 2.0,
                    inner_y,
                    outer_y,
                    x=x,
                    z=center_z,
                )
            )
        boolean_difference(block, countersinks, "Mount_Countersinks")

    return block


# ---------------------------------------------------------------------------
# Build, check, and export


def non_manifold_edge_count(obj) -> int:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    count = sum(1 for edge in bm.edges if len(edge.link_faces) != 2)
    bm.free()
    return count


def connected_shell_count(obj) -> int:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    unseen = set(bm.faces)
    shells = 0
    while unseen:
        shells += 1
        stack = [unseen.pop()]
        while stack:
            face = stack.pop()
            for edge in face.edges:
                for linked_face in edge.link_faces:
                    if linked_face in unseen:
                        unseen.remove(linked_face)
                        stack.append(linked_face)
    bm.free()
    return shells


def remove_opposed_coincident_faces(obj) -> int:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    tolerance = CLEAN_COINCIDENT_FACE_TOLERANCE
    groups = {}
    for face in bm.faces:
        coordinates = tuple(
            sorted(
                tuple(round(float(value) / tolerance) for value in vertex.co)
                for vertex in face.verts
            )
        )
        groups.setdefault((len(face.verts), coordinates), []).append(face)

    remove = set()
    for faces in groups.values():
        available = list(faces)
        while len(available) > 1:
            face = available.pop()
            opposite_index = next(
                (
                    index
                    for index, candidate in enumerate(available)
                    if face.normal.dot(candidate.normal) < -0.9999
                ),
                None,
            )
            if opposite_index is not None:
                remove.add(face)
                remove.add(available.pop(opposite_index))

    if remove:
        bmesh.ops.delete(bm, geom=list(remove), context="FACES")
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(obj.data)
        obj.data.update()
    bm.free()
    return len(remove)


def triangulate_mesh(obj) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(
        bm,
        faces=list(bm.faces),
        quad_method="BEAUTY",
        ngon_method="BEAUTY",
    )
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def export_stl(objects) -> Path:
    path = Path(EXPORT_STL_PATH)
    if not path.is_absolute():
        base = Path(bpy.data.filepath).parent if bpy.data.filepath else Path.cwd()
        path = base / path
    path = path.resolve()

    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]

    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(filepath=str(path), export_selected_objects=True)
    elif hasattr(bpy.ops.export_mesh, "stl"):
        bpy.ops.export_mesh.stl(filepath=str(path), use_selection=True)
    else:
        raise RuntimeError("No STL exporter is available in this Blender installation")
    return path


def build_dual_fan():
    validate_config()
    if CLEAR_SCENE:
        clear_scene()
    set_units()

    fan_1_x = -FAN_1_DISTANCE_FROM_CENTER
    fan_2_x = FAN_2_DISTANCE_FROM_CENTER
    parts = []
    if SUPPORT_ENABLED:
        parts.append(create_support(fan_1_x, fan_2_x))

    fan_1 = create_fan_cage(fan_1_x, 1)
    fan_2 = create_fan_cage(fan_2_x, 2)
    rotate_fan_cage(fan_1, fan_1_x, FAN_1_ROTATION_DEG)
    rotate_fan_cage(fan_2, fan_2_x, FAN_2_ROTATION_DEG)
    parts.extend((fan_1, fan_2))

    if STALK_ENABLED:
        parts.append(create_stalk())
    if MOUNT_BLOCK_ENABLED:
        parts.append(create_mount_block())

    if UNION_ALL_PARTS:
        final = parts[0]
        for part in parts[1:]:
            boolean_union(final, part, "Assembly_Union")
        final.name = "Parametric_Dual_Fan_Holder"
        final.data.name = "Parametric_Dual_Fan_Holder_Mesh"
        final_objects = [final]
    else:
        final = parts[0]
        final_objects = parts
        for part in parts:
            part.select_set(True)

    for obj in final_objects:
        triangulate_mesh(obj)
        removed_faces = remove_opposed_coincident_faces(obj)
        recalc_normals(obj)
        count = non_manifold_edge_count(obj)
        shells = connected_shell_count(obj)
        print(
            f"{obj.name}: vertices={len(obj.data.vertices)} "
            f"polygons={len(obj.data.polygons)} "
            f"non_manifold_edges={count} connected_shells={shells} "
            f"removed_coincident_faces={removed_faces}"
        )
        if UNION_ALL_PARTS and count:
            raise RuntimeError(f"Final mesh has {count} non-manifold edges")
        if UNION_ALL_PARTS and shells != 1:
            raise RuntimeError(
                f"Final mesh has {shells} disconnected shells; reduce the fan angles "
                "or increase SUPPORT_ARM_FAN_INSERT_Y"
            )

    if EXPORT_STL:
        path = export_stl(final_objects)
        print(f"Wrote {path}")

    select_only(final)
    return final


if __name__ == "__main__":
    build_dual_fan()
