"""Procedural GoPro MISSION 1 dummy calibrated from GoproDummy_noscreens.stl.

The supplied Shapr3D STL is used only as a dimensional reference; this module
does not import it.  Running this file in Blender recreates a lightweight,
configurable dummy from primitives and can export it as a new STL.

Reference coordinates use X=body width, Y=optical/front depth, and Z=height.
The canonical enclosure orientation puts the lens-face center at the origin,
with +X along the outward optical axis, +Y tangential, and +Z upward.  The
canonical form is rolled 180 degrees around the optical axis because that is
the useful orientation inside the current enclosure.
"""

from __future__ import annotations

import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


# ---------------------------------------------------------------------------
# CONFIG AND REFERENCE MEASUREMENTS (millimeters)

CLEAR_SCENE = True
EXPORT_STL = True
EXPORT_PATH = "gopro_mission1_dummy_recreated.stl"
BUILD_CANONICAL_ENCLOSURE_ORIENTATION = False

# Source used to calibrate this reconstruction.  It is documentation only and
# is deliberately not loaded by the generator.
REFERENCE_STL = (
    "gopro-mission-1/Pirch0/gopro-mission1-pro-dummy-step-stl-files/"
    "GoproDummy_noscreens.stl"
)

# Exact ADMesh/Blender bounds of the supplied STL.
REFERENCE_MIN_X = -42.0
REFERENCE_MAX_X = 39.0
REFERENCE_MIN_Y = 0.0
REFERENCE_MAX_Y = 44.4
REFERENCE_MIN_Z = -25.5
REFERENCE_MAX_Z = 28.5
REFERENCE_ENVELOPE_WIDTH = REFERENCE_MAX_X - REFERENCE_MIN_X       # 81.0
REFERENCE_ENVELOPE_DEPTH = REFERENCE_MAX_Y - REFERENCE_MIN_Y       # 44.4
REFERENCE_ENVELOPE_HEIGHT = REFERENCE_MAX_Z - REFERENCE_MIN_Z      # 54.0

# Rounded main body reconstructed from the reference shell.
BODY_WIDTH = 78.0
BODY_DEPTH = 27.8
BODY_HEIGHT = 51.0
BODY_CORNER_RADIUS = 4.0

# The supplied dummy's square lens housing.  Its 44.4 mm face is 16.6 mm in
# front of the 27.8 mm body face.  The tapered rear shoulder overlaps the body.
LENS_CENTER_X = -20.1
LENS_CENTER_Z = 5.0
LENS_FACE_Y = 44.4
LENS_FACE_WIDTH = 41.8
LENS_FACE_HEIGHT = 41.8
LENS_FACE_CORNER_RADIUS = 5.0
LENS_SHOULDER_Y = 20.0
LENS_FULL_SIZE_Y = 29.7
LENS_SHOULDER_WIDTH = 34.0
LENS_SHOULDER_HEIGHT = 34.0
LENS_SHOULDER_CORNER_RADIUS = 7.0

# External controls measured from the supplied dummy.
TOP_BUTTON_CENTER = (18.0, 13.9, 26.875)
TOP_BUTTON_SIZE = (18.0, 18.0, 3.25)
TOP_BUTTON_RADIUS = 1.5
SIDE_BUTTON_CENTER = (-40.375, 13.5, -3.0)
SIDE_BUTTON_SIZE = (3.25, 13.0, 14.0)
SIDE_BUTTON_RADIUS = 1.0

ROUNDED_RECTANGLE_SEGMENTS = 12
BOOLEAN_SOLVER = "EXACT"
BOOLEAN_CLEANUP_DISTANCE = 0.0001

# Canonical keepout coordinates, relative to the lens-face center after a
# 180-degree optical-axis roll.  These are consumed by the enclosure builder.
CANONICAL_RADIAL_MIN = REFERENCE_MIN_Y - LENS_FACE_Y                # -44.4
CANONICAL_RADIAL_MAX = REFERENCE_MAX_Y - LENS_FACE_Y                # 0.0
CANONICAL_TANGENTIAL_MIN = REFERENCE_MIN_X - LENS_CENTER_X          # -21.9
CANONICAL_TANGENTIAL_MAX = REFERENCE_MAX_X - LENS_CENTER_X          # 59.1
CANONICAL_VERTICAL_MIN = -(REFERENCE_MAX_Z - LENS_CENTER_Z)         # -23.5
CANONICAL_VERTICAL_MAX = -(REFERENCE_MIN_Z - LENS_CENTER_Z)         # 30.5
CANONICAL_ENVELOPE_CENTER_RADIAL = (
    CANONICAL_RADIAL_MIN + CANONICAL_RADIAL_MAX
) / 2.0
CANONICAL_ENVELOPE_CENTER_TANGENTIAL = (
    CANONICAL_TANGENTIAL_MIN + CANONICAL_TANGENTIAL_MAX
) / 2.0
CANONICAL_ENVELOPE_CENTER_VERTICAL = (
    CANONICAL_VERTICAL_MIN + CANONICAL_VERTICAL_MAX
) / 2.0


# ---------------------------------------------------------------------------
# BLENDER HELPERS


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def set_units() -> None:
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 0.001


def select_only(obj) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def recalc_normals(obj) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def cleanup_mesh(obj) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(
        bm,
        verts=list(bm.verts),
        dist=BOOLEAN_CLEANUP_DISTANCE,
    )
    bmesh.ops.dissolve_degenerate(
        bm,
        edges=list(bm.edges),
        dist=BOOLEAN_CLEANUP_DISTANCE,
    )
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


def add_beveled_box(name: str, dimensions, location, bevel: float):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    modifier = obj.modifiers.new(name + "_Rounded_Edges", "BEVEL")
    modifier.width = min(bevel, min(dimensions) / 2.1)
    modifier.segments = 6
    modifier.affect = "EDGES"
    select_only(obj)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    recalc_normals(obj)
    return obj


def rounded_rectangle_loop(width: float, height: float, radius: float):
    radius = min(max(radius, 0.0), width / 2.0, height / 2.0)
    points = []
    corners = (
        (width / 2.0 - radius, height / 2.0 - radius, 0.0, 90.0),
        (-width / 2.0 + radius, height / 2.0 - radius, 90.0, 180.0),
        (-width / 2.0 + radius, -height / 2.0 + radius, 180.0, 270.0),
        (width / 2.0 - radius, -height / 2.0 + radius, 270.0, 360.0),
    )
    for center_x, center_z, angle0, angle1 in corners:
        for step in range(ROUNDED_RECTANGLE_SEGMENTS):
            angle = math.radians(
                angle0
                + (angle1 - angle0) * step / ROUNDED_RECTANGLE_SEGMENTS
            )
            points.append(
                (
                    center_x + radius * math.cos(angle),
                    center_z + radius * math.sin(angle),
                )
            )
    return points


def lens_housing(name: str):
    sections = (
        (
            LENS_SHOULDER_Y,
            rounded_rectangle_loop(
                LENS_SHOULDER_WIDTH,
                LENS_SHOULDER_HEIGHT,
                LENS_SHOULDER_CORNER_RADIUS,
            ),
        ),
        (
            LENS_FULL_SIZE_Y,
            rounded_rectangle_loop(
                LENS_FACE_WIDTH,
                LENS_FACE_HEIGHT,
                LENS_FACE_CORNER_RADIUS,
            ),
        ),
        (
            LENS_FACE_Y,
            rounded_rectangle_loop(
                LENS_FACE_WIDTH,
                LENS_FACE_HEIGHT,
                LENS_FACE_CORNER_RADIUS,
            ),
        ),
    )
    count = len(sections[0][1])
    vertices = []
    for y, loop in sections:
        vertices.extend(
            (LENS_CENTER_X + x, y, LENS_CENTER_Z + z)
            for x, z in loop
        )
    rear_center = len(vertices)
    vertices.append((LENS_CENTER_X, sections[0][0], LENS_CENTER_Z))
    front_center = len(vertices)
    vertices.append((LENS_CENTER_X, sections[-1][0], LENS_CENTER_Z))

    def vertex(section, index):
        return section * count + index % count

    faces = []
    for section in range(len(sections) - 1):
        for index in range(count):
            faces.append(
                [
                    vertex(section, index),
                    vertex(section + 1, index),
                    vertex(section + 1, index + 1),
                    vertex(section, index + 1),
                ]
            )
    last = len(sections) - 1
    for index in range(count):
        faces.append([rear_center, vertex(0, index), vertex(0, index + 1)])
        faces.append(
            [front_center, vertex(last, index + 1), vertex(last, index)]
        )
    return create_mesh_object(name, vertices, faces)


def boolean_union(base, part, label: str):
    select_only(base)
    modifier = base.modifiers.new(label, "BOOLEAN")
    modifier.operation = "UNION"
    modifier.object = part
    if hasattr(modifier, "solver"):
        modifier.solver = BOOLEAN_SOLVER
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(part, do_unlink=True)
    cleanup_mesh(base)
    recalc_normals(base)
    return base


def canonicalize_about_lens(obj) -> None:
    """Put lens face at origin and roll the reference camera upside down."""
    for vertex in obj.data.vertices:
        reference = vertex.co.copy()
        vertex.co = Vector(
            (
                reference.y - LENS_FACE_Y,
                reference.x - LENS_CENTER_X,
                -(reference.z - LENS_CENTER_Z),
            )
        )
    obj.data.update()
    recalc_normals(obj)


def build_mission1_dummy(
    name: str = "GoPro_MISSION_1_Procedural_Dummy",
    canonical: bool = BUILD_CANONICAL_ENCLOSURE_ORIENTATION,
):
    """Build and return one manifold approximation of the supplied dummy."""
    body = add_beveled_box(
        name + "_Body",
        (BODY_WIDTH, BODY_DEPTH, BODY_HEIGHT),
        (0.0, BODY_DEPTH / 2.0, 0.0),
        BODY_CORNER_RADIUS,
    )
    boolean_union(body, lens_housing(name + "_Lens_Housing"), name + "_Lens")
    top_button = add_beveled_box(
        name + "_Top_Button",
        TOP_BUTTON_SIZE,
        TOP_BUTTON_CENTER,
        TOP_BUTTON_RADIUS,
    )
    boolean_union(body, top_button, name + "_Top_Button_Union")
    side_button = add_beveled_box(
        name + "_Side_Button",
        SIDE_BUTTON_SIZE,
        SIDE_BUTTON_CENTER,
        SIDE_BUTTON_RADIUS,
    )
    boolean_union(body, side_button, name + "_Side_Button_Union")
    # The body primitive is created at its depth center.  Bake that object
    # translation before applying the lens-centered coordinate conversion.
    select_only(body)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    body.name = name
    body.data.name = name + "_Mesh"
    if canonical:
        canonicalize_about_lens(body)
    return body


def place_canonical_dummy(
    angle_deg: float,
    lens_face_radius: float,
    lens_center_z: float,
    name: str = "GoPro_MISSION_1_Procedural_Dummy",
):
    """Build a canonical dummy and place its lens on an enclosure eye axis."""
    obj = build_mission1_dummy(name=name, canonical=True)
    angle = math.radians(angle_deg)
    obj.location = (
        math.cos(angle) * lens_face_radius,
        math.sin(angle) * lens_face_radius,
        lens_center_z,
    )
    obj.rotation_euler.z = angle
    bpy.context.view_layer.update()
    return obj


def mesh_diagnostics(obj) -> tuple[int, int]:
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


def export_stl(path: Path, obj) -> Path:
    select_only(obj)
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(filepath=str(path), export_selected_objects=True)
    else:
        bpy.ops.export_mesh.stl(filepath=str(path), use_selection=True)
    print(f"EXPORTED {path}")
    return path


def main():
    if CLEAR_SCENE:
        clear_scene()
    set_units()
    dummy = build_mission1_dummy()
    non_manifold, shells = mesh_diagnostics(dummy)
    print(
        "MISSION1_DUMMY "
        f"dimensions={tuple(round(value, 3) for value in dummy.dimensions)} "
        f"non_manifold_edges={non_manifold} connected_shells={shells}"
    )
    if non_manifold or shells != 1:
        raise RuntimeError("Procedural MISSION 1 dummy is not one manifold shell")
    if EXPORT_STL:
        path = Path(EXPORT_PATH)
        if not path.is_absolute():
            path = Path.cwd().resolve() / path
        export_stl(path, dummy)
    return dummy


if __name__ == "__main__":
    main()
