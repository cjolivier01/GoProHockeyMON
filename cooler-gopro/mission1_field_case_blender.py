"""Parametric rugged field case for two GoPro MISSION 1 cameras.

The generator creates every printable component from Blender primitives.  It
does not import, bundle, or modify third-party meshes.  The default kit holds:

* two GoPro MISSION 1 / MISSION 1 PRO cameras standing upright with their
  lenses opposed and laterally nested,
* four MISSION 1 Enduro 2 / HERO13-format batteries, terminal end downward,
* a flush-top recessed TPU equipment tray and a TPU lid pad,
* a TPU dust/splash gasket, two Pelican-style hinged draw latches, and
  printable hinge/latch pins,
* two flush lid-lettering inlays for a three-color top surface.

The case is Pelican/rugged-box inspired, but all geometry here is independently
parameterized.  In particular, the user-supplied MakerWorld example is used as
a functional precedent for recessed upper/lower inserts, gasket, case shell,
and multicolor lid; its Standard Digital File License does not allow remixing,
so none of its mesh geometry is consumed by this script.  The latch reference
is likewise used only to understand the operation of a Pelican replacement
latch; the latch below is independently parameterized.

Reference sources (checked 2026-08-27):

* Local camera envelope: ``gopro_mission1_dummy_blender.py``
* User-supplied one-camera precedent:
  https://makerworld.com/en/models/2890334-gopro-mission-1-rugged-box
* User-supplied Pelican replacement-latch precedent:
  https://makerworld.com/en/models/810330-pelican-case-latch
* Four-battery travel magazine (slot-layout cross-check):
  https://www.printables.com/model/1777128-gopro-hero-9-13-battery-magazine-for-air-travel
* One-camera rugged case with battery slots and separate seal/latch:
  https://www.printables.com/model/367570-gopro-9101112-rugged-case-2-battery-box

Run inside Blender::

    /home/colivier/Apps/Blender/blender \
      --background --factory-startup \
      --python mission1_field_case_blender.py

Set ``EXPORT_STL = True`` below, or use
``make -C cooler-gopro mission1-field-case`` from the repository root, to emit
all printable STLs.  Import the lid plus both lettering STLs together as one
multi-part object in the slicer, then assign the shell, title, and subtitle
their desired colors.  Print two copies each of the latch and latch-pin STLs.

All dimensions are millimeters.  X is case width, Y is case depth, and Z is
height.  Every default printable part validates below 250 x 250 mm in XY.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


def import_mission1_module():
    """Import the companion camera reference from CLI or Blender Text Editor."""
    script_path = Path(__file__).expanduser().resolve()
    script_parent = script_path.parent
    candidates = []

    def add_candidate(path) -> None:
        directory = Path(path).expanduser().resolve()
        if directory not in candidates:
            candidates.append(directory)

    # Blender's Text Editor may report a synthetic path such as
    # ``project.blend/mission1_field_case_blender.py``. In that case the
    # apparent parent is the .blend file itself, and the scripts live beside
    # that file.
    if script_parent.suffix.lower() == ".blend" or script_parent.is_file():
        add_candidate(script_parent.parent)
    add_candidate(script_parent)

    if bpy.data.filepath:
        add_candidate(Path(bpy.data.filepath).parent)

    text_name = script_path.name
    for text_block in bpy.data.texts:
        if text_block.name == text_name and text_block.filepath:
            add_candidate(Path(bpy.path.abspath(text_block.filepath)).parent)

    add_candidate(Path.cwd())

    module_name = "gopro_mission1_dummy_blender"
    for directory in candidates:
        if (directory / f"{module_name}.py").is_file():
            if str(directory) not in sys.path:
                sys.path.insert(0, str(directory))
            return __import__(module_name)

    searched = ", ".join(str(directory) for directory in candidates)
    raise ModuleNotFoundError(
        f"Could not locate {module_name}.py; searched: {searched}"
    )


mission1 = import_mission1_module()


# ---------------------------------------------------------------------------
# EXPORT AND SCENE CONFIGURATION

CLEAR_SCENE = True
BUILD_REFERENCE_MOCKUPS = True
EXPORT_STL = False
EXPORT_DIRECTORY = ""
SAVE_BLEND = False
BLEND_PATH = "mission1_field_case.blend"

BASE_STL_NAME = "mission1_field_case_base.stl"
LID_STL_NAME = "mission1_field_case_lid.stl"
LOWER_TRAY_STL_NAME = "mission1_field_case_lower_tray_tpu.stl"
LID_RETAINER_STL_NAME = "mission1_field_case_lid_retainer_tpu.stl"
GASKET_STL_NAME = "mission1_field_case_gasket_tpu.stl"
LATCH_STL_NAME = "mission1_field_case_pelican_latch_print_two.stl"
LATCH_PIN_STL_NAME = "mission1_field_case_latch_pin_print_two.stl"
HINGE_PIN_STL_NAME = "mission1_field_case_hinge_pin.stl"
TITLE_INLAY_STL_NAME = "mission1_field_case_lid_title_inlay.stl"
SUBTITLE_INLAY_STL_NAME = "mission1_field_case_lid_subtitle_inlay.stl"

PRINTABLE_STL_NAMES = (
    BASE_STL_NAME,
    LID_STL_NAME,
    LOWER_TRAY_STL_NAME,
    LID_RETAINER_STL_NAME,
    GASKET_STL_NAME,
    LATCH_STL_NAME,
    LATCH_PIN_STL_NAME,
    HINGE_PIN_STL_NAME,
    TITLE_INLAY_STL_NAME,
    SUBTITLE_INLAY_STL_NAME,
)


# ---------------------------------------------------------------------------
# PARAMETRIC CASE CONFIGURATION

MAX_PRINT_XY = 250.0

# Compact double-capacity shell based on the proportions and component split
# of the supplied one-camera example, without consuming its mesh geometry.
CASE_WIDTH = 132.0
CASE_DEPTH = 154.0
BASE_HEIGHT = 62.0
CASE_CORNER_RADIUS = 12.0
WALL_THICKNESS = 4.5
BASE_FLOOR_THICKNESS = 3.2

LID_PLATE_THICKNESS = 4.0
LID_WALL_HEIGHT = 11.0
LID_FLANGE_OUTSET = 2.0
LID_DISPLAY_OFFSET_X = 170.0

# The lower TPU insert is a continuous recessed tray.  All cavity walls point
# down from one flat top surface; nothing protrudes above TRAY_HEIGHT.
INSERT_SIDE_CLEARANCE = 0.5
TRAY_HEIGHT = 35.0
TRAY_FLOOR_THICKNESS = 3.0
INSERT_CORNER_RADIUS = CASE_CORNER_RADIUS - WALL_THICKNESS - 0.5

# Camera cavities are cut directly with expanded copies of the procedural
# MISSION 1 mesh.  Camera 1 faces +Y; camera 2 faces -Y and is rolled in plan,
# so the offset lens lobes share the central space without touching.
CAMERA_WIDTH = mission1.REFERENCE_ENVELOPE_WIDTH
CAMERA_HEIGHT = mission1.REFERENCE_ENVELOPE_HEIGHT
CAMERA_DEPTH = mission1.REFERENCE_ENVELOPE_DEPTH
CAMERA_POCKET_CLEARANCE_XY = 0.8
CAMERA_POCKET_CLEARANCE_Z = 0.4
CAMERA_FLOOR_Z = TRAY_FLOOR_THICKNESS
MIN_CAMERA_POCKET_WEB = 2.0
CAMERA_PAIR_CENTER_Y = 20.0
CAMERA_LENS_PROJECTION = mission1.LENS_FACE_Y - mission1.BODY_DEPTH
CAMERA_OPPOSED_BODY_CLEARANCE = 4.0
CAMERA_PAIR_HALF_SEPARATION = (
    mission1.BODY_DEPTH + (CAMERA_LENS_PROJECTION + CAMERA_OPPOSED_BODY_CLEARANCE) / 2.0
)
CAMERA_LATERAL_NEST_OFFSET = 2.7
CAMERA_PLACEMENTS = (
    (
        -CAMERA_LATERAL_NEST_OFFSET,
        CAMERA_PAIR_CENTER_Y - CAMERA_PAIR_HALF_SEPARATION,
        0.0,
    ),
    (
        CAMERA_LATERAL_NEST_OFFSET,
        CAMERA_PAIR_CENTER_Y + CAMERA_PAIR_HALF_SEPARATION,
        180.0,
    ),
)

# Enduro 2 is HERO13 compatible.  Contemporary printed battery holders expose
# about 34 x 13.5 mm slots.  These deliberately looser pockets also accept the
# older HERO9-12 Enduro outline, with tuneable clearance for printer variance.
BATTERY_HEIGHT = 40.8
BATTERY_WIDTH = 34.0
BATTERY_THICKNESS = 13.5
BATTERY_CLEARANCE = 1.0
BATTERY_POCKET_WIDTH = BATTERY_THICKNESS + BATTERY_CLEARANCE
BATTERY_POCKET_DEPTH = BATTERY_WIDTH + BATTERY_CLEARANCE
# Battery floors raise their top surfaces level with the camera body tops.  The
# camera shutter buttons sit in dedicated reliefs in the uniform lid pad.
BATTERY_FLOOR_Z = CAMERA_FLOOR_Z + mission1.BODY_HEIGHT - BATTERY_HEIGHT
BATTERY_CENTERS = (
    (-30.0, -48.0),
    (-10.0, -48.0),
    (10.0, -48.0),
    (30.0, -48.0),
)

LID_RETAINER_HEIGHT = 12.4
LID_BUTTON_RELIEF_DEPTH = 4.2
LID_BUTTON_RELIEF_CLEARANCE = 1.0

# A shallow lid channel retains a slightly proud TPU gasket.  It is intended
# as dust/splash protection, not as a certified waterproof seal.
GASKET_CHANNEL_WIDTH = 2.6
GASKET_WIDTH = 2.2
GASKET_CHANNEL_DEPTH = 1.2
GASKET_HEIGHT = 1.6
GASKET_FIT_CLEARANCE = 0.2

# Hinge axis is along X.  The pin hole is generous enough for a metal rod or
# the included flat-bottom printable D-profile pin.
HINGE_AXIS_Y = CASE_DEPTH / 2.0 + 3.8
HINGE_OUTER_DIAMETER = 10.0
HINGE_HOLE_DIAMETER = 3.5
HINGE_PIN_DIAMETER = 2.9
HINGE_BASE_SEGMENTS = ((-52.0, -28.0), (-9.0, 9.0), (28.0, 52.0))
HINGE_LID_SEGMENTS = ((-27.4, -9.6), (9.6, 27.4))
HINGE_PIN_X0 = -53.0
HINGE_PIN_X1 = 53.0

# Two independently generated, one-piece hinged draw levers emulate the broad
# U-shaped Pelican latch: side rails, a lower pull tab, an upper cam bridge,
# and a hook that draws the lid catch down as the lever closes.
LATCH_X_CENTERS = (-38.0, 38.0)
LATCH_WIDTH = 30.0
LATCH_HEIGHT = 32.0
LATCH_DEPTH = 5.2
LATCH_SIDE_RAIL_WIDTH = 5.0
LATCH_GRIP_HEIGHT = 8.0
LATCH_PULL_TAB_WIDTH = 22.0
LATCH_PULL_TAB_HEIGHT = 18.0
LATCH_PULL_TAB_OVERLAP = 1.5
LATCH_TOP_BRIDGE_HEIGHT = 7.0
LATCH_WINDOW_WIDTH = 17.0
LATCH_WINDOW_HEIGHT = 17.0
LATCH_PIVOT_DIAMETER = 3.0
LATCH_PIVOT_HOLE_DIAMETER = 3.6
LATCH_PIVOT_BARREL_DIAMETER = 8.4
LATCH_PIVOT_Z = 46.5
LATCH_EAR_WIDTH = 4.0
LATCH_EAR_DEPTH = 16.0
LATCH_EAR_HEIGHT = 17.0
LATCH_MOUNT_CLEARANCE = 0.35
LATCH_MOUNT_OFFSET_Y = 7.0
LATCH_CATCH_WIDTH = 18.0
LATCH_CATCH_DEPTH = 5.0
LATCH_CATCH_HEIGHT = 4.5
LATCH_PIN_LENGTH = (
    LATCH_WIDTH + 2.0 * LATCH_MOUNT_CLEARANCE + 2.0 * LATCH_EAR_WIDTH + 1.0
)

# Integrated fixed carry handle.  Its forward projection is included in the
# maximum-part validation rather than treated as a separate printable piece.
HANDLE_OUTER_SIZE = (84.0, 28.0)
HANDLE_INNER_SIZE = (58.0, 12.0)
HANDLE_CENTER_Y = -89.5
HANDLE_INNER_CENTER_Y = -90.5
HANDLE_HEIGHT = 10.0

# Flush multi-material lettering.  The inlays start at the same build plane as
# the lid outer face and are imported with the lid as separate slicer parts.
LID_TITLE = "MISSION 1 FIELD KIT"
LID_SUBTITLE = "2 CAMS  |  4 BATTERIES"
LID_TITLE_SIZE = 10.0
LID_SUBTITLE_SIZE = 4.7
LID_TITLE_MAX_WIDTH = 112.0
LID_SUBTITLE_MAX_WIDTH = 106.0
LID_INLAY_DEPTH = 0.8
LID_INLAY_CLEARANCE = 0.08

ROUNDED_RECT_SEGMENTS = 10
BOOLEAN_SOLVER = "EXACT"
BOOLEAN_CLEANUP_DISTANCE = 0.0001


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
    recalc_normals(obj)


def create_mesh_object(name: str, vertices, faces):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(clean_customdata=True)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    recalc_normals(obj)
    return obj


def rounded_rectangle_loop(width: float, depth: float, radius: float):
    radius = min(max(radius, 0.0), width / 2.0, depth / 2.0)
    points = []
    corners = (
        (width / 2.0 - radius, depth / 2.0 - radius, 0.0, 90.0),
        (-width / 2.0 + radius, depth / 2.0 - radius, 90.0, 180.0),
        (-width / 2.0 + radius, -depth / 2.0 + radius, 180.0, 270.0),
        (width / 2.0 - radius, -depth / 2.0 + radius, 270.0, 360.0),
    )
    for center_x, center_y, angle0, angle1 in corners:
        for step in range(ROUNDED_RECT_SEGMENTS):
            angle = math.radians(
                angle0 + (angle1 - angle0) * step / ROUNDED_RECT_SEGMENTS
            )
            points.append(
                (
                    center_x + radius * math.cos(angle),
                    center_y + radius * math.sin(angle),
                )
            )
    return points


def add_rounded_prism(
    name: str,
    width: float,
    depth: float,
    z0: float,
    z1: float,
    radius: float,
    location_xy=(0.0, 0.0),
):
    loop = rounded_rectangle_loop(width, depth, radius)
    cx, cy = location_xy
    count = len(loop)
    vertices = [(cx + x, cy + y, z0) for x, y in loop]
    vertices.extend((cx + x, cy + y, z1) for x, y in loop)
    faces = [list(reversed(range(count))), list(range(count, count * 2))]
    for index in range(count):
        next_index = (index + 1) % count
        faces.append((index, next_index, count + next_index, count + index))
    return create_mesh_object(name, vertices, faces)


def add_rounded_box(name, dimensions, location, bevel=0.6):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0.0:
        modifier = obj.modifiers.new(name + "_Bevel", "BEVEL")
        modifier.width = min(bevel, min(dimensions) / 2.1)
        modifier.segments = 3
        modifier.affect = "EDGES"
        select_only(obj)
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    recalc_normals(obj)
    return obj


def add_cylinder_z(name, radius, depth, location, vertices=64):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=depth,
        location=location,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    recalc_normals(obj)
    return obj


def add_cylinder_x(name, radius, length, location, vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=length,
        location=location,
        rotation=(0.0, math.pi / 2.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    recalc_normals(obj)
    return obj


def extrude_loop_x(name: str, loop_yz, x0: float, x1: float):
    count = len(loop_yz)
    vertices = [(x0, y, z) for y, z in loop_yz]
    vertices.extend((x1, y, z) for y, z in loop_yz)
    faces = [list(reversed(range(count))), list(range(count, count * 2))]
    for index in range(count):
        next_index = (index + 1) % count
        faces.append((index, next_index, count + next_index, count + index))
    return create_mesh_object(name, vertices, faces)


def mesh_vertex_islands(bm):
    """Return edge-connected vertex islands from a populated BMesh."""
    remaining = set(bm.verts)
    islands = []
    while remaining:
        island = []
        stack = [remaining.pop()]
        while stack:
            vertex = stack.pop()
            island.append(vertex)
            for edge in vertex.link_edges:
                neighbor = edge.other_vert(vertex)
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
        islands.append(island)
    return islands


def boolean_apply(
    target,
    tool,
    operation: str,
    delete_tool=True,
    solver=BOOLEAN_SOLVER,
):
    modifier = target.modifiers.new(
        target.name + "_" + operation.title(),
        "BOOLEAN",
    )
    modifier.operation = operation
    modifier.solver = solver
    modifier.object = tool
    select_only(target)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    if delete_tool:
        bpy.data.objects.remove(tool, do_unlink=True)
    cleanup_mesh(target)
    return target


def union_into(target, component):
    return boolean_apply(target, component, "UNION")


def difference_from(target, cutter, solver=BOOLEAN_SOLVER):
    return boolean_apply(target, cutter, "DIFFERENCE", solver=solver)


def rounded_ring(
    name,
    outer_size,
    inner_size,
    z0,
    z1,
    outer_radius,
    inner_radius,
    center=(0.0, 0.0),
):
    ring = add_rounded_prism(
        name,
        outer_size[0],
        outer_size[1],
        z0,
        z1,
        outer_radius,
        center,
    )
    cutter = add_rounded_prism(
        name + "_Inner_Cutter",
        inner_size[0],
        inner_size[1],
        z0 - 0.2,
        z1 + 0.2,
        inner_radius,
        center,
    )
    return difference_from(ring, cutter)


def assign_material(obj, material) -> None:
    if obj.data and hasattr(obj.data, "materials"):
        obj.data.materials.clear()
        obj.data.materials.append(material)


def make_material(name, color, metallic=0.0, roughness=0.45):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1.0)
    material.metallic = metallic
    material.roughness = roughness
    return material


def object_world_bounds(obj):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    minimum = Vector(
        (
            min(v.x for v in corners),
            min(v.y for v in corners),
            min(v.z for v in corners),
        )
    )
    maximum = Vector(
        (
            max(v.x for v in corners),
            max(v.y for v in corners),
            max(v.z for v in corners),
        )
    )
    return minimum, maximum


def object_world_dimensions(obj):
    minimum, maximum = object_world_bounds(obj)
    return maximum - minimum


def translate_object(obj, offset):
    obj.location += Vector(offset)
    bpy.context.view_layer.update()
    return obj


def expand_mesh_about_bounds(obj, clearance_xyz) -> None:
    """Expand a mesh by per-side clearances while preserving its shape."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    minimum = Vector(
        (
            min(vertex.co.x for vertex in bm.verts),
            min(vertex.co.y for vertex in bm.verts),
            min(vertex.co.z for vertex in bm.verts),
        )
    )
    maximum = Vector(
        (
            max(vertex.co.x for vertex in bm.verts),
            max(vertex.co.y for vertex in bm.verts),
            max(vertex.co.z for vertex in bm.verts),
        )
    )
    center = (minimum + maximum) / 2.0
    dimensions = maximum - minimum
    scale = Vector(
        tuple(
            (dimensions[axis] + 2.0 * clearance_xyz[axis]) / dimensions[axis]
            for axis in range(3)
        )
    )
    for vertex in bm.verts:
        relative = vertex.co - center
        vertex.co = center + Vector(
            (
                relative.x * scale.x,
                relative.y * scale.y,
                relative.z * scale.z,
            )
        )
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    recalc_normals(obj)


def transform_reference_xy(point_xy, placement):
    """Transform reference-camera XY coordinates into tray coordinates."""
    location_x, location_y, angle_deg = placement
    angle = math.radians(angle_deg)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return (
        location_x + point_xy[0] * cosine - point_xy[1] * sine,
        location_y + point_xy[0] * sine + point_xy[1] * cosine,
    )


def build_placed_camera(name, placement, as_cutter=False):
    """Build the true procedural camera shape in its opposed tray pose."""
    camera = mission1.build_mission1_dummy(name=name, canonical=False)
    if as_cutter:
        expand_mesh_about_bounds(
            camera,
            (
                CAMERA_POCKET_CLEARANCE_XY,
                CAMERA_POCKET_CLEARANCE_XY,
                CAMERA_POCKET_CLEARANCE_Z,
            ),
        )
    minimum_z = min(vertex.co.z for vertex in camera.data.vertices)
    camera.location = (
        placement[0],
        placement[1],
        CAMERA_FLOOR_Z - minimum_z,
    )
    camera.rotation_euler.z = math.radians(placement[2])
    bpy.context.view_layer.update()
    return camera


def add_text_mesh(
    name,
    body,
    size,
    max_width,
    center,
    depth,
    mirror_y=False,
):
    bpy.ops.object.text_add(location=center)
    text_obj = bpy.context.object
    text_obj.name = name
    curve = text_obj.data
    curve.name = name + "_Curve"
    curve.body = body
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = size
    curve.extrude = max(depth / 2.0, 0.01)
    curve.bevel_depth = 0.06
    curve.bevel_resolution = 2
    if mirror_y:
        text_obj.scale.y = -1.0
    bpy.context.view_layer.update()
    if text_obj.dimensions.x > max_width:
        factor = max_width / text_obj.dimensions.x
        text_obj.scale.x *= factor
        text_obj.scale.y *= factor
    select_only(text_obj)
    bpy.ops.object.convert(target="MESH")
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    cleanup_mesh(text_obj)
    target_z0 = center[2]
    minimum, maximum = object_world_bounds(text_obj)
    current_depth = maximum.z - minimum.z
    if current_depth > 0.0:
        text_obj.scale.z *= depth / current_depth
        select_only(text_obj)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    cleanup_mesh(text_obj)
    minimum, _maximum = object_world_bounds(text_obj)
    text_obj.location.z += target_z0 - minimum.z
    bpy.context.view_layer.update()
    return text_obj


def duplicate_as_cutter(source, name, clearance):
    cutter = source.copy()
    cutter.data = source.data.copy()
    cutter.name = name
    cutter.data.name = name + "_Mesh"
    bpy.context.collection.objects.link(cutter)

    # Grow each disconnected glyph around its own center. Scaling the complete
    # word would mostly move the outer letters and leave interior glyphs with
    # almost no fit clearance.
    bm = bmesh.new()
    bm.from_mesh(cutter.data)
    for island in mesh_vertex_islands(bm):
        min_x = min(vertex.co.x for vertex in island)
        max_x = max(vertex.co.x for vertex in island)
        min_y = min(vertex.co.y for vertex in island)
        max_y = max(vertex.co.y for vertex in island)
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        width = max_x - min_x
        height = max_y - min_y
        scale_x = (width + 2.0 * clearance) / width
        scale_y = (height + 2.0 * clearance) / height
        for vertex in island:
            vertex.co.x = center_x + (vertex.co.x - center_x) * scale_x
            vertex.co.y = center_y + (vertex.co.y - center_y) * scale_y
    bm.to_mesh(cutter.data)
    bm.free()
    cutter.data.update()

    dims = object_world_dimensions(cutter)
    cutter.scale.z *= (dims.z + 0.4) / dims.z
    select_only(cutter)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    minimum, _maximum = object_world_bounds(cutter)
    cutter.location.z -= minimum.z + 0.1
    bpy.context.view_layer.update()
    return cutter


# ---------------------------------------------------------------------------
# VALIDATION


def rectangles_overlap(a_center, a_size, b_center, b_size, gap=0.0):
    return (
        abs(a_center[0] - b_center[0]) < (a_size[0] + b_size[0]) / 2.0 + gap
        and abs(a_center[1] - b_center[1]) < (a_size[1] + b_size[1]) / 2.0 + gap
    )


def validate_configuration() -> None:
    inner_width = CASE_WIDTH - 2.0 * WALL_THICKNESS
    inner_depth = CASE_DEPTH - 2.0 * WALL_THICKNESS
    tray_width = inner_width - 2.0 * INSERT_SIDE_CLEARANCE
    tray_depth = inner_depth - 2.0 * INSERT_SIDE_CLEARANCE

    if BATTERY_POCKET_WIDTH < BATTERY_THICKNESS or BATTERY_POCKET_DEPTH < BATTERY_WIDTH:
        raise ValueError("Battery pockets do not clear the Enduro envelope")
    if min(WALL_THICKNESS, BASE_FLOOR_THICKNESS, TRAY_FLOOR_THICKNESS) < 2.0:
        raise ValueError("Default rigid walls must remain at least 2 mm")

    camera_bounds = []
    reference_corners = (
        (mission1.REFERENCE_MIN_X, mission1.REFERENCE_MIN_Y),
        (mission1.REFERENCE_MIN_X, mission1.REFERENCE_MAX_Y),
        (mission1.REFERENCE_MAX_X, mission1.REFERENCE_MIN_Y),
        (mission1.REFERENCE_MAX_X, mission1.REFERENCE_MAX_Y),
    )
    for placement in CAMERA_PLACEMENTS:
        transformed = [
            transform_reference_xy(corner, placement) for corner in reference_corners
        ]
        min_x = min(point[0] for point in transformed) - CAMERA_POCKET_CLEARANCE_XY
        max_x = max(point[0] for point in transformed) + CAMERA_POCKET_CLEARANCE_XY
        min_y = min(point[1] for point in transformed) - CAMERA_POCKET_CLEARANCE_XY
        max_y = max(point[1] for point in transformed) + CAMERA_POCKET_CLEARANCE_XY
        camera_bounds.append((min_x, max_x, min_y, max_y))
        if min_x < -tray_width / 2.0 or max_x > tray_width / 2.0:
            raise ValueError(f"Camera cavity exceeds tray width: {placement}")
        if min_y < -tray_depth / 2.0 or max_y > tray_depth / 2.0:
            raise ValueError(f"Camera cavity exceeds tray depth: {placement}")

    camera_center_x = (mission1.REFERENCE_MIN_X + mission1.REFERENCE_MAX_X) / 2.0
    camera_center_y = (mission1.REFERENCE_MIN_Y + mission1.REFERENCE_MAX_Y) / 2.0
    cutter_scale_x = (CAMERA_WIDTH + 2.0 * CAMERA_POCKET_CLEARANCE_XY) / CAMERA_WIDTH
    cutter_scale_y = (CAMERA_DEPTH + 2.0 * CAMERA_POCKET_CLEARANCE_XY) / CAMERA_DEPTH
    lens_right_edge = mission1.LENS_CENTER_X + mission1.LENS_FACE_WIDTH / 2.0
    expanded_lens_right_edge = (
        camera_center_x + (lens_right_edge - camera_center_x) * cutter_scale_x
    )
    lateral_lens_web = 2.0 * (CAMERA_LATERAL_NEST_OFFSET - expanded_lens_right_edge)
    if lateral_lens_web < MIN_CAMERA_POCKET_WEB:
        raise ValueError(
            f"Expanded camera lens cavities need a {MIN_CAMERA_POCKET_WEB:.1f} mm "
            f"TPU web; computed {lateral_lens_web:.2f} mm"
        )
    expanded_lens_face = (
        camera_center_y + (mission1.LENS_FACE_Y - camera_center_y) * cutter_scale_y
    )
    expanded_body_face = (
        camera_center_y + (mission1.BODY_DEPTH - camera_center_y) * cutter_scale_y
    )
    camera_1_lens_face = CAMERA_PLACEMENTS[0][1] + expanded_lens_face
    camera_2_body_face = CAMERA_PLACEMENTS[1][1] - expanded_body_face
    axial_body_web = camera_2_body_face - camera_1_lens_face
    if axial_body_web < MIN_CAMERA_POCKET_WEB:
        raise ValueError(
            f"Expanded lens/body cavities need a {MIN_CAMERA_POCKET_WEB:.1f} mm "
            f"TPU web; computed {axial_body_web:.2f} mm"
        )

    battery_size = (BATTERY_POCKET_WIDTH, BATTERY_POCKET_DEPTH)
    for index, center in enumerate(BATTERY_CENTERS):
        if abs(center[0]) + battery_size[0] / 2.0 > tray_width / 2.0:
            raise ValueError(f"Battery cavity exceeds tray width: {center}")
        if abs(center[1]) + battery_size[1] / 2.0 > tray_depth / 2.0:
            raise ValueError(f"Battery cavity exceeds tray depth: {center}")
        for other in BATTERY_CENTERS[index + 1 :]:
            if rectangles_overlap(center, battery_size, other, battery_size, gap=2.0):
                raise ValueError(f"Battery cavities overlap: {center} and {other}")
        battery_top = center[1] + battery_size[1] / 2.0
        nearest_camera = min(bounds[2] for bounds in camera_bounds)
        if battery_top + 4.0 > nearest_camera:
            raise ValueError("Battery row needs 4 mm clearance from the camera pair")

    camera_contact_top = BASE_FLOOR_THICKNESS + CAMERA_FLOOR_Z + mission1.BODY_HEIGHT
    battery_top = BASE_FLOOR_THICKNESS + BATTERY_FLOOR_Z + BATTERY_HEIGHT
    content_top = max(camera_contact_top, battery_top)
    installed_lid_inner_face = BASE_HEIGHT + (LID_WALL_HEIGHT - LID_PLATE_THICKNESS)
    pad_compression = content_top + LID_RETAINER_HEIGHT - installed_lid_inner_face
    if not 0.2 <= pad_compression <= 1.5:
        raise ValueError(
            "TPU lid retainer preload must remain 0.2-1.5 mm; "
            f"computed {pad_compression:.2f} mm"
        )
    camera_button_top = BASE_FLOOR_THICKNESS + CAMERA_FLOOR_Z + CAMERA_HEIGHT
    relief_ceiling = installed_lid_inner_face - (
        LID_RETAINER_HEIGHT - LID_BUTTON_RELIEF_DEPTH
    )
    if relief_ceiling - camera_button_top < 0.3:
        raise ValueError("Lid pad button relief does not clear the shutter buttons")

    # Conservative analytic envelopes include every projection on each part.
    base_print_width = max(CASE_WIDTH + 7.8, HANDLE_OUTER_SIZE[0])
    handle_front = HANDLE_CENTER_Y - HANDLE_OUTER_SIZE[1] / 2.0
    hinge_back = HINGE_AXIS_Y + HINGE_OUTER_DIAMETER / 2.0
    base_print_depth = hinge_back - handle_front
    lid_print_width = CASE_WIDTH + 2.0 * LID_FLANGE_OUTSET
    lid_front = CASE_DEPTH / 2.0 + LATCH_CATCH_DEPTH
    lid_back = -HINGE_AXIS_Y - HINGE_OUTER_DIAMETER / 2.0
    lid_print_depth = lid_front - lid_back
    for part, dimensions in (
        ("base", (base_print_width, base_print_depth)),
        ("lid", (lid_print_width, lid_print_depth)),
        ("lower TPU tray", (tray_width, tray_depth)),
        ("lid retainer", (tray_width, tray_depth)),
        ("gasket", (CASE_WIDTH - 3.8, CASE_DEPTH - 3.8)),
        (
            "Pelican latch",
            (
                LATCH_WIDTH,
                LATCH_HEIGHT
                - LATCH_GRIP_HEIGHT / 2.0
                + LATCH_PULL_TAB_HEIGHT
                - LATCH_PULL_TAB_OVERLAP,
            ),
        ),
        ("latch pin", (LATCH_PIN_LENGTH + 2.2, 6.0)),
        ("hinge pin", (HINGE_PIN_X1 - HINGE_PIN_X0 + 2.1, 6.0)),
    ):
        if dimensions[0] > MAX_PRINT_XY or dimensions[1] > MAX_PRINT_XY:
            raise ValueError(f"{part} exceeds {MAX_PRINT_XY:.0f} mm: {dimensions}")

    print(
        "FIELD_CASE_CONFIG "
        f"shell={CASE_WIDTH:.1f}x{CASE_DEPTH:.1f}x{BASE_HEIGHT:.1f} "
        f"tray={tray_width:.1f}x{tray_depth:.1f}x{TRAY_HEIGHT:.1f} "
        f"lens_web={lateral_lens_web:.2f} axial_web={axial_body_web:.2f} "
        f"pad_preload={pad_compression:.2f}"
    )
    print(
        "FIELD_CASE_PRINT_ENVELOPES "
        f"base={base_print_width:.1f}x{base_print_depth:.1f} "
        f"lid={lid_print_width:.1f}x{lid_print_depth:.1f} "
        f"limit={MAX_PRINT_XY:.1f}"
    )


# ---------------------------------------------------------------------------
# PART BUILDERS


def create_base(material):
    base = add_rounded_prism(
        "Field_Case_Base",
        CASE_WIDTH,
        CASE_DEPTH,
        0.0,
        BASE_HEIGHT,
        CASE_CORNER_RADIUS,
    )
    inner = add_rounded_prism(
        "Base_Interior_Cutter",
        CASE_WIDTH - 2.0 * WALL_THICKNESS,
        CASE_DEPTH - 2.0 * WALL_THICKNESS,
        BASE_FLOOR_THICKNESS,
        BASE_HEIGHT + 0.5,
        CASE_CORNER_RADIUS - WALL_THICKNESS,
    )
    difference_from(base, inner)

    handle = rounded_ring(
        "Integrated_Fixed_Handle",
        HANDLE_OUTER_SIZE,
        HANDLE_INNER_SIZE,
        0.0,
        HANDLE_HEIGHT,
        6.0,
        5.0,
        (0.0, HANDLE_CENTER_Y),
    )
    # Offset the hole toward the front to retain a thick shell attachment bar.
    handle_inner_shift = HANDLE_INNER_CENTER_Y - HANDLE_CENTER_Y
    if abs(handle_inner_shift) > 1e-6:
        # Rebuild with the deliberately offset inner opening.
        bpy.data.objects.remove(handle, do_unlink=True)
        handle = add_rounded_prism(
            "Integrated_Fixed_Handle",
            HANDLE_OUTER_SIZE[0],
            HANDLE_OUTER_SIZE[1],
            0.0,
            HANDLE_HEIGHT,
            6.0,
            (0.0, HANDLE_CENTER_Y),
        )
        opening = add_rounded_prism(
            "Handle_Opening_Cutter",
            HANDLE_INNER_SIZE[0],
            HANDLE_INNER_SIZE[1],
            -0.2,
            HANDLE_HEIGHT + 0.2,
            5.0,
            (0.0, HANDLE_INNER_CENTER_Y),
        )
        difference_from(handle, opening)
    union_into(base, handle)

    # Exterior impact ribs are deliberately below the sealing edge.
    rib_specs = []
    for x in (-42.0, 0.0, 42.0):
        rib_specs.append(((x, CASE_DEPTH / 2.0 + 1.3, 24.0), (6.0, 4.8, 42.0)))
    for x in (-52.0, 52.0):
        rib_specs.append(((x, -CASE_DEPTH / 2.0 - 1.0, 24.0), (6.0, 4.5, 42.0)))
    for x in (-CASE_WIDTH / 2.0 - 1.3, CASE_WIDTH / 2.0 + 1.3):
        for y in (-38.0, 38.0):
            rib_specs.append(((x, y, 22.0), (5.0, 24.0, 38.0)))
    for index, (location, dimensions) in enumerate(rib_specs, start=1):
        rib = add_rounded_box(
            f"Base_Impact_Rib_{index}",
            dimensions,
            location,
            bevel=0.9,
        )
        union_into(base, rib)

    # Alternating hinge knuckles share one continuous 3.5 mm pin bore.
    for index, (x0, x1) in enumerate(HINGE_BASE_SEGMENTS, start=1):
        knuckle = add_cylinder_x(
            f"Base_Hinge_Knuckle_{index}",
            HINGE_OUTER_DIAMETER / 2.0,
            x1 - x0,
            ((x0 + x1) / 2.0, HINGE_AXIS_Y, BASE_HEIGHT),
        )
        hole = add_cylinder_x(
            f"Base_Hinge_Hole_{index}",
            HINGE_HOLE_DIAMETER / 2.0,
            x1 - x0 + 0.8,
            ((x0 + x1) / 2.0, HINGE_AXIS_Y, BASE_HEIGHT),
        )
        difference_from(knuckle, hole)
        union_into(base, knuckle)

    # Each Pelican-style lever pivots between a pair of protected base ears.
    mount_y = -CASE_DEPTH / 2.0 - LATCH_MOUNT_OFFSET_Y
    for index, x in enumerate(LATCH_X_CENTERS, start=1):
        for side in (-1.0, 1.0):
            ear_x = x + side * (
                LATCH_WIDTH / 2.0 + LATCH_MOUNT_CLEARANCE + LATCH_EAR_WIDTH / 2.0
            )
            ear = add_rounded_box(
                f"Base_Latch_{index}_Pivot_Ear",
                (LATCH_EAR_WIDTH, LATCH_EAR_DEPTH, LATCH_EAR_HEIGHT),
                (ear_x, mount_y, LATCH_PIVOT_Z),
                bevel=1.0,
            )
            hole = add_cylinder_x(
                f"Base_Latch_{index}_Pivot_Hole",
                LATCH_PIVOT_HOLE_DIAMETER / 2.0,
                LATCH_EAR_WIDTH + 0.8,
                (ear_x, mount_y, LATCH_PIVOT_Z),
                vertices=36,
            )
            difference_from(ear, hole)
            union_into(base, ear)

    assign_material(base, material)
    return base


def create_lower_tray(material):
    inner_width = CASE_WIDTH - 2.0 * WALL_THICKNESS
    inner_depth = CASE_DEPTH - 2.0 * WALL_THICKNESS
    tray_width = inner_width - 2.0 * INSERT_SIDE_CLEARANCE
    tray_depth = inner_depth - 2.0 * INSERT_SIDE_CLEARANCE
    tray = add_rounded_prism(
        "Field_Case_Recessed_TPU_Lower_Tray",
        tray_width,
        tray_depth,
        0.0,
        TRAY_HEIGHT,
        INSERT_CORNER_RADIUS,
    )

    # The procedural camera itself forms each cavity.  This retains the body
    # bevels, side/top controls, tapered lens shoulder, and full square lens
    # housing instead of approximating the camera as a rectangular envelope.
    for index, placement in enumerate(CAMERA_PLACEMENTS, start=1):
        cutter = build_placed_camera(
            f"Camera_{index}_True_Shape_Cavity_Cutter",
            placement,
            as_cutter=True,
        )
        difference_from(tray, cutter)

        body_center = transform_reference_xy(
            (0.0, mission1.BODY_DEPTH / 2.0),
            placement,
        )
        scoop_x = -45.5 if index == 1 else 45.5
        scoop = add_cylinder_z(
            f"Camera_{index}_Finger_Scoop",
            8.0,
            14.0,
            (scoop_x, body_center[1], TRAY_HEIGHT - 7.0),
            vertices=48,
        )
        difference_from(tray, scoop)

    for index, center in enumerate(BATTERY_CENTERS, start=1):
        cavity = add_rounded_prism(
            f"Battery_{index}_Cavity",
            BATTERY_POCKET_WIDTH,
            BATTERY_POCKET_DEPTH,
            BATTERY_FLOOR_Z,
            TRAY_HEIGHT + 0.4,
            1.6,
            center,
        )
        difference_from(tray, cavity)
        scoop = add_cylinder_z(
            f"Battery_{index}_Finger_Scoop",
            6.0,
            12.0,
            (center[0], -67.0, TRAY_HEIGHT - 6.0),
            vertices=40,
        )
        difference_from(tray, scoop)

    assign_material(tray, material)
    return tray


def create_lid(shell_material, title_material, subtitle_material):
    dx = LID_DISPLAY_OFFSET_X
    lid = add_rounded_prism(
        "Field_Case_Lid",
        CASE_WIDTH,
        CASE_DEPTH,
        0.0,
        LID_PLATE_THICKNESS,
        CASE_CORNER_RADIUS,
        (dx, 0.0),
    )
    wall = rounded_ring(
        "Lid_Wall",
        (CASE_WIDTH, CASE_DEPTH),
        (
            CASE_WIDTH - 2.0 * WALL_THICKNESS,
            CASE_DEPTH - 2.0 * WALL_THICKNESS,
        ),
        LID_PLATE_THICKNESS - 0.2,
        LID_WALL_HEIGHT,
        CASE_CORNER_RADIUS,
        CASE_CORNER_RADIUS - WALL_THICKNESS,
        (dx, 0.0),
    )
    union_into(lid, wall)
    flange = rounded_ring(
        "Lid_Protective_Flange",
        (
            CASE_WIDTH + 2.0 * LID_FLANGE_OUTSET,
            CASE_DEPTH + 2.0 * LID_FLANGE_OUTSET,
        ),
        (CASE_WIDTH - 0.8, CASE_DEPTH - 0.8),
        LID_WALL_HEIGHT - 3.0,
        LID_WALL_HEIGHT,
        CASE_CORNER_RADIUS + LID_FLANGE_OUTSET,
        CASE_CORNER_RADIUS - 0.4,
        (dx, 0.0),
    )
    union_into(lid, flange)

    groove_outer = (
        CASE_WIDTH - 3.6,
        CASE_DEPTH - 3.6,
    )
    groove_inner = (
        groove_outer[0] - 2.0 * GASKET_CHANNEL_WIDTH,
        groove_outer[1] - 2.0 * GASKET_CHANNEL_WIDTH,
    )
    groove = rounded_ring(
        "Lid_Gasket_Channel_Cutter",
        groove_outer,
        groove_inner,
        LID_WALL_HEIGHT - GASKET_CHANNEL_DEPTH,
        LID_WALL_HEIGHT + 0.2,
        CASE_CORNER_RADIUS - 1.8,
        CASE_CORNER_RADIUS - 1.8 - GASKET_CHANNEL_WIDTH,
        (dx, 0.0),
    )
    difference_from(lid, groove)

    # In print orientation the lid's hinge is at -Y; flipping the finished lid
    # around X places it on the base's +Y hinge line.
    for index, (x0, x1) in enumerate(HINGE_LID_SEGMENTS, start=1):
        knuckle = add_cylinder_x(
            f"Lid_Hinge_Knuckle_{index}",
            HINGE_OUTER_DIAMETER / 2.0,
            x1 - x0,
            (dx + (x0 + x1) / 2.0, -HINGE_AXIS_Y, LID_WALL_HEIGHT),
        )
        hole = add_cylinder_x(
            f"Lid_Hinge_Hole_{index}",
            HINGE_HOLE_DIAMETER / 2.0,
            x1 - x0 + 0.8,
            (dx + (x0 + x1) / 2.0, -HINGE_AXIS_Y, LID_WALL_HEIGHT),
        )
        difference_from(knuckle, hole)
        union_into(lid, knuckle)

    # Broad catches map to the case front after the lid is turned over.  The
    # lever's upper cam hook draws against their lower edge when closed.
    lid_catch_local_z = 5.3
    for index, x in enumerate(LATCH_X_CENTERS, start=1):
        catch = add_rounded_box(
            f"Lid_Pelican_Latch_Catch_{index}",
            (LATCH_CATCH_WIDTH, LATCH_CATCH_DEPTH, LATCH_CATCH_HEIGHT),
            (dx + x, CASE_DEPTH / 2.0 + 1.8, lid_catch_local_z),
            bevel=0.9,
        )
        union_into(lid, catch)

    # Pre-mirroring Y makes the text read normally after the lid is flipped
    # into its installed orientation.  Both inserts remain flush with z=0.
    title = add_text_mesh(
        "Lid_Title_Inlay",
        LID_TITLE,
        LID_TITLE_SIZE,
        LID_TITLE_MAX_WIDTH,
        (dx, -5.0, 0.0),
        LID_INLAY_DEPTH,
        mirror_y=True,
    )
    subtitle = add_text_mesh(
        "Lid_Subtitle_Inlay",
        LID_SUBTITLE,
        LID_SUBTITLE_SIZE,
        LID_SUBTITLE_MAX_WIDTH,
        (dx, 15.0, 0.0),
        LID_INLAY_DEPTH,
        mirror_y=True,
    )
    title_cutter = duplicate_as_cutter(
        title,
        "Lid_Title_Recess_Cutter",
        LID_INLAY_CLEARANCE,
    )
    subtitle_cutter = duplicate_as_cutter(
        subtitle,
        "Lid_Subtitle_Recess_Cutter",
        LID_INLAY_CLEARANCE,
    )
    # Blender's exact solver can misclassify the disconnected, nested shells
    # produced by converted font glyphs.  Its manifold solver is deterministic
    # for these already-validated watertight cutters and preserves the lid.
    difference_from(lid, title_cutter, solver="MANIFOLD")
    difference_from(lid, subtitle_cutter, solver="MANIFOLD")

    assign_material(lid, shell_material)
    assign_material(title, title_material)
    assign_material(subtitle, subtitle_material)
    return lid, title, subtitle


def create_gasket(material):
    groove_outer = (CASE_WIDTH - 3.6, CASE_DEPTH - 3.6)
    gasket_outer = (
        groove_outer[0] - GASKET_FIT_CLEARANCE,
        groove_outer[1] - GASKET_FIT_CLEARANCE,
    )
    gasket_inner = (
        gasket_outer[0] - 2.0 * GASKET_WIDTH,
        gasket_outer[1] - 2.0 * GASKET_WIDTH,
    )
    gasket = rounded_ring(
        "Field_Case_TPU_Gasket",
        gasket_outer,
        gasket_inner,
        0.0,
        GASKET_HEIGHT,
        CASE_CORNER_RADIUS - 1.9,
        CASE_CORNER_RADIUS - 1.9 - GASKET_WIDTH,
    )
    translate_object(gasket, (0.0, 225.0, 0.0))
    assign_material(gasket, material)
    return gasket


def create_lid_retainer(material):
    inner_width = CASE_WIDTH - 2.0 * WALL_THICKNESS
    inner_depth = CASE_DEPTH - 2.0 * WALL_THICKNESS
    retainer_width = inner_width - 2.0 * INSERT_SIDE_CLEARANCE
    retainer_depth = inner_depth - 2.0 * INSERT_SIDE_CLEARANCE
    retainer = add_rounded_prism(
        "Field_Case_Recessed_TPU_Lid_Pad",
        retainer_width,
        retainer_depth,
        0.0,
        LID_RETAINER_HEIGHT,
        INSERT_CORNER_RADIUS,
    )

    # A continuous pad face preloads the aligned camera-body and battery tops.
    # Shallow pockets above the shutter buttons prevent accidental presses.
    # Lid-local Y is the negative of base Y after closing.
    for index, placement in enumerate(CAMERA_PLACEMENTS, start=1):
        button_center = transform_reference_xy(
            (mission1.TOP_BUTTON_CENTER[0], mission1.TOP_BUTTON_CENTER[1]),
            placement,
        )
        relief = add_rounded_prism(
            f"Camera_{index}_Shutter_Button_Relief",
            mission1.TOP_BUTTON_SIZE[0] + 2.0 * LID_BUTTON_RELIEF_CLEARANCE,
            mission1.TOP_BUTTON_SIZE[1] + 2.0 * LID_BUTTON_RELIEF_CLEARANCE,
            LID_RETAINER_HEIGHT - LID_BUTTON_RELIEF_DEPTH,
            LID_RETAINER_HEIGHT + 0.3,
            mission1.TOP_BUTTON_RADIUS + LID_BUTTON_RELIEF_CLEARANCE,
            (button_center[0], -button_center[1]),
        )
        difference_from(retainer, relief)

    translate_object(retainer, (LID_DISPLAY_OFFSET_X, 220.0, 0.0))
    assign_material(retainer, material)
    return retainer


def create_latch(material):
    print_center_y = -150.0
    latch = add_rounded_prism(
        "Field_Case_Pelican_Draw_Latch_Print_Two",
        LATCH_WIDTH,
        LATCH_HEIGHT,
        0.0,
        LATCH_DEPTH,
        4.0,
        (0.0, print_center_y),
    )
    window_center_y = (
        print_center_y
        - LATCH_HEIGHT / 2.0
        + LATCH_GRIP_HEIGHT
        + LATCH_WINDOW_HEIGHT / 2.0
    )
    window = add_rounded_prism(
        "Pelican_Latch_Open_Center_Cutter",
        LATCH_WINDOW_WIDTH,
        LATCH_WINDOW_HEIGHT,
        -0.2,
        LATCH_DEPTH + 0.4,
        2.5,
        (0.0, window_center_y),
    )
    difference_from(latch, window)

    # The cross-axis barrel pivots between the two base ears. The broad lower
    # bridge acts as the pull tab; the open center and thick side rails make
    # the characteristic Pelican-style U-shaped draw lever.
    pivot_y = print_center_y - LATCH_HEIGHT / 2.0 + LATCH_GRIP_HEIGHT / 2.0
    barrel_radius = LATCH_PIVOT_BARREL_DIAMETER / 2.0
    barrel = add_cylinder_x(
        "Pelican_Latch_Pivot_Barrel",
        barrel_radius,
        LATCH_WIDTH - 0.8,
        (0.0, pivot_y, barrel_radius),
        vertices=48,
    )
    union_into(latch, barrel)
    pivot_hole = add_cylinder_x(
        "Pelican_Latch_Pivot_Hole",
        LATCH_PIVOT_HOLE_DIAMETER / 2.0,
        LATCH_WIDTH + 1.0,
        (0.0, pivot_y, barrel_radius),
        vertices=40,
    )
    difference_from(latch, pivot_hole)

    pull_tab_center_y = pivot_y - LATCH_PULL_TAB_HEIGHT / 2.0 + LATCH_PULL_TAB_OVERLAP
    pull_tab = add_rounded_prism(
        "Pelican_Latch_Broad_Pull_Tab",
        LATCH_PULL_TAB_WIDTH,
        LATCH_PULL_TAB_HEIGHT,
        0.0,
        LATCH_DEPTH,
        3.5,
        (0.0, pull_tab_center_y),
    )
    union_into(latch, pull_tab)

    # The inner lip rides over the lid catch and draws it toward the base as
    # the lever closes. Its rounded leading face avoids a sharp stress riser
    # where the latch flexes over the catch.
    hook = add_rounded_box(
        "Pelican_Latch_Upper_Cam_Hook",
        (LATCH_WINDOW_WIDTH + 2.0, 3.2, 3.4),
        (
            0.0,
            print_center_y + LATCH_HEIGHT / 2.0 - LATCH_TOP_BRIDGE_HEIGHT + 0.8,
            1.7,
        ),
        bevel=0.8,
    )
    union_into(latch, hook)

    assign_material(latch, material)
    return latch


def create_latch_pin(material):
    radius = LATCH_PIVOT_DIAMETER / 2.0
    flat = -0.78 * radius
    arc_limit = math.acos(flat / radius)
    arc_steps = 24
    angles = [
        -arc_limit + 2.0 * arc_limit * step / arc_steps for step in range(arc_steps + 1)
    ]
    loop = [
        (radius * math.sin(angle), radius * math.cos(angle) - flat) for angle in angles
    ]
    x0 = -LATCH_PIN_LENGTH / 2.0
    x1 = LATCH_PIN_LENGTH / 2.0
    pin = extrude_loop_x("Field_Case_Latch_Pin_Print_Two", loop, x0, x1)
    head = add_rounded_box(
        "Latch_Pin_Stop_Head",
        (2.2, 5.5, 3.0),
        (x0 - 1.0, 0.0, 1.5),
        bevel=0.65,
    )
    union_into(pin, head)
    translate_object(pin, (0.0, -195.0, 0.0))
    assign_material(pin, material)
    return pin


def create_hinge_pin(material):
    radius = HINGE_PIN_DIAMETER / 2.0
    # The circle center sits above z=0 so the closing edge of this major arc
    # forms a printable flat.  Do not append chord points: that would make the
    # loop self-cross before extrusion.
    flat = -1.12
    arc_limit = math.acos(flat / radius)
    arc_steps = 24
    angles = [
        -arc_limit + 2.0 * arc_limit * step / arc_steps for step in range(arc_steps + 1)
    ]
    loop = [
        (radius * math.sin(angle), radius * math.cos(angle) - flat) for angle in angles
    ]
    pin = extrude_loop_x(
        "Field_Case_Hinge_Pin",
        loop,
        HINGE_PIN_X0,
        HINGE_PIN_X1,
    )
    head = add_rounded_box(
        "Hinge_Pin_Stop_Head",
        (2.2, 6.0, 3.0),
        (HINGE_PIN_X0 - 1.0, 0.0, 1.5),
        bevel=0.7,
    )
    union_into(pin, head)
    translate_object(pin, (0.0, -180.0, 0.0))
    assign_material(pin, material)
    return pin


def create_reference_mockups(materials):
    objects = []
    camera_material, battery_material = materials
    for index, placement in enumerate(CAMERA_PLACEMENTS, start=1):
        mockup = build_placed_camera(
            f"REFERENCE_ONLY_MISSION1_{index}",
            placement,
            as_cutter=False,
        )
        assign_material(mockup, camera_material)
        objects.append(mockup)
    for index, center in enumerate(BATTERY_CENTERS, start=1):
        mockup = add_rounded_box(
            f"REFERENCE_ONLY_Enduro2_{index}",
            (BATTERY_THICKNESS, BATTERY_WIDTH, BATTERY_HEIGHT),
            (
                center[0],
                center[1],
                BATTERY_FLOOR_Z + BATTERY_HEIGHT / 2.0,
            ),
            bevel=1.2,
        )
        assign_material(mockup, battery_material)
        objects.append(mockup)
    for obj in objects:
        obj.display_type = "SOLID"
        obj.hide_render = False
    return objects


# ---------------------------------------------------------------------------
# EXPORT AND ENTRY POINT


def export_path(name: str) -> Path:
    if EXPORT_DIRECTORY:
        directory = Path(EXPORT_DIRECTORY).expanduser().resolve()
    else:
        directory = Path(__file__).expanduser().resolve().parent
    directory.mkdir(parents=True, exist_ok=True)
    return directory / name


def export_stl(path: Path, obj) -> Path:
    select_only(obj)
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(
            filepath=str(path),
            export_selected_objects=True,
            apply_modifiers=True,
        )
    else:
        bpy.ops.export_mesh.stl(
            filepath=str(path),
            use_selection=True,
            use_mesh_modifiers=True,
        )
    print(f"FIELD_CASE_EXPORTED {path}")
    return path


def validate_built_part(name: str, obj) -> None:
    dimensions = object_world_dimensions(obj)
    if (
        len(obj.data.vertices) < 4
        or len(obj.data.polygons) < 4
        or min(dimensions) < 0.01
    ):
        raise ValueError(
            f"Built {name} is empty or degenerate: "
            f"{dimensions.x:.3f} x {dimensions.y:.3f} x {dimensions.z:.3f}"
        )
    if dimensions.x > MAX_PRINT_XY + 1e-5 or dimensions.y > MAX_PRINT_XY + 1e-5:
        raise ValueError(
            f"Built {name} exceeds {MAX_PRINT_XY:.0f} mm XY: "
            f"{dimensions.x:.2f} x {dimensions.y:.2f}"
        )
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    non_manifold = sum(1 for edge in bm.edges if not edge.is_manifold)
    volume = bm.calc_volume(signed=False)
    connected_components = len(mesh_vertex_islands(bm))
    bm.free()
    if non_manifold:
        raise ValueError(f"Built {name} has {non_manifold} non-manifold edges")
    if volume < 0.001:
        raise ValueError(f"Built {name} has near-zero volume: {volume:.6f} mm^3")
    if name not in {"title_inlay", "subtitle_inlay"} and connected_components != 1:
        raise ValueError(
            f"Built {name} contains {connected_components} disconnected islands"
        )
    print(
        "FIELD_CASE_PART "
        f"{name}={dimensions.x:.2f}x{dimensions.y:.2f}x{dimensions.z:.2f} "
        "manifold=yes"
    )


def build_mission1_field_case():
    validate_configuration()
    if CLEAR_SCENE:
        clear_scene()
    set_units()

    shell_material = make_material(
        "Rugged_Shell_Black", (0.025, 0.03, 0.038), roughness=0.33
    )
    tpu_material = make_material("TPU_Orange", (0.95, 0.22, 0.035), roughness=0.58)
    title_material = make_material("Title_Cyan", (0.0, 0.62, 0.92), roughness=0.4)
    subtitle_material = make_material(
        "Subtitle_Orange", (1.0, 0.28, 0.04), roughness=0.42
    )
    hardware_material = make_material(
        "Printed_Hardware", (0.16, 0.18, 0.22), roughness=0.38
    )
    camera_material = make_material(
        "Camera_Reference", (0.18, 0.2, 0.23), roughness=0.34
    )
    battery_material = make_material(
        "Battery_Reference", (0.88, 0.9, 0.94), roughness=0.5
    )
    parts = {}
    parts["base"] = create_base(shell_material)
    parts["lower_tray"] = create_lower_tray(tpu_material)
    lid, title, subtitle = create_lid(
        shell_material,
        title_material,
        subtitle_material,
    )
    parts["lid"] = lid
    parts["title_inlay"] = title
    parts["subtitle_inlay"] = subtitle
    parts["gasket"] = create_gasket(tpu_material)
    parts["lid_retainer"] = create_lid_retainer(tpu_material)
    parts["latch"] = create_latch(hardware_material)
    parts["latch_pin"] = create_latch_pin(hardware_material)
    parts["hinge_pin"] = create_hinge_pin(hardware_material)

    if BUILD_REFERENCE_MOCKUPS:
        create_reference_mockups((camera_material, battery_material))

    for name, obj in parts.items():
        validate_built_part(name, obj)

    if EXPORT_STL:
        exports = (
            (BASE_STL_NAME, parts["base"]),
            (LID_STL_NAME, parts["lid"]),
            (LOWER_TRAY_STL_NAME, parts["lower_tray"]),
            (LID_RETAINER_STL_NAME, parts["lid_retainer"]),
            (GASKET_STL_NAME, parts["gasket"]),
            (LATCH_STL_NAME, parts["latch"]),
            (LATCH_PIN_STL_NAME, parts["latch_pin"]),
            (HINGE_PIN_STL_NAME, parts["hinge_pin"]),
            (TITLE_INLAY_STL_NAME, parts["title_inlay"]),
            (SUBTITLE_INLAY_STL_NAME, parts["subtitle_inlay"]),
        )
        for filename, obj in exports:
            export_stl(export_path(filename), obj)

    if SAVE_BLEND:
        path = Path(BLEND_PATH).expanduser().resolve()
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        print(f"FIELD_CASE_SAVED_BLEND {path}")

    return parts


if __name__ == "__main__":
    build_mission1_field_case()
