"""Parametric rugged field case for two GoPro MISSION 1 cameras.

The generator creates every printable component from Blender primitives.  It
does not import, bundle, or modify third-party meshes.  The default kit holds:

* two GoPro MISSION 1 / MISSION 1 PRO cameras standing upright with their
  lenses opposed and laterally nested, including flared soft-lens-hood reliefs,
* four MISSION 1 Enduro 2 / HERO13-format batteries, terminal end downward,
* two edge-on slots for the removable camera battery-cage doors,
* a flush-top recessed TPU equipment tray and a one-way-keyed TPU lid pad,
* a TPU dust/splash gasket, two Pelican-style over-center draw latches, and
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
all twelve printable-part STLs and ``mission1_field_case_ams_project.3mf``.  The
3MF contains the complete six-plate project; its lid is one compound object
with separate shell, title, and subtitle color bodies.  The standalone lid
STLs remain available for other slicers.  Print two copies each of the latch
handle, latch bail, base-pin, and link-pin STLs when using standalone files.

All dimensions are millimeters.  X is case width, Y is case depth, and Z is
height.  Every default printable part validates below 250 x 250 mm in XY.
"""

from __future__ import annotations

import json
import math
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
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
        directory = Path(path).expanduser()
        try:
            directory = directory.resolve()
        except OSError:
            directory = directory.absolute()
        if directory not in candidates:
            candidates.append(directory)

    def add_text_file_parent(raw_path) -> None:
        if not raw_path:
            return
        try:
            expanded = bpy.path.abspath(str(raw_path))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            expanded = str(raw_path)
        add_candidate(Path(expanded).parent)

    # A Text Editor run can replace ``__file__`` with a synthetic root path
    # such as ``/script.py``. Prefer the active Text datablock's real filepath,
    # then inspect every loaded Text datablock for context-free runs.
    space_data = getattr(bpy.context, "space_data", None)
    active_text = getattr(space_data, "text", None)
    add_text_file_parent(getattr(active_text, "filepath", ""))

    text_name = script_path.name
    loaded_texts = tuple(getattr(bpy.data, "texts", ()))
    for text_block in loaded_texts:
        if Path(text_block.name).name == text_name:
            add_text_file_parent(getattr(text_block, "filepath", ""))
    for text_block in loaded_texts:
        add_text_file_parent(getattr(text_block, "filepath", ""))

    # Blender's Text Editor may report a synthetic path such as
    # ``project.blend/mission1_field_case_blender.py``. In that case the
    # apparent parent is the .blend file itself, and the scripts live beside
    # that file.
    if script_parent.suffix.lower() == ".blend" or script_parent.is_file():
        add_candidate(script_parent.parent)
    add_candidate(script_parent)

    if bpy.data.filepath:
        add_candidate(Path(bpy.data.filepath).parent)

    add_candidate(Path.cwd())

    module_name = "gopro_mission1_dummy_blender"
    for directory in candidates:
        if (directory / f"{module_name}.py").is_file():
            if str(directory) not in sys.path:
                sys.path.insert(0, str(directory))
            return __import__(module_name), directory

    searched = ", ".join(str(directory) for directory in candidates)
    raise ModuleNotFoundError(
        f"Could not locate {module_name}.py; searched: {searched}"
    )


mission1, MISSION1_SOURCE_DIRECTORY = import_mission1_module()


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
LATCH_HANDLE_STL_NAME = "mission1_field_case_over_center_latch_handle_print_two.stl"
LATCH_BAIL_STL_NAME = "mission1_field_case_over_center_latch_bail_print_two.stl"
LATCH_BASE_PIN_STL_NAME = "mission1_field_case_latch_base_pin_print_two.stl"
LATCH_LINK_PIN_STL_NAME = "mission1_field_case_latch_link_pin_print_two.stl"
HINGE_PIN_STL_NAME = "mission1_field_case_hinge_pin.stl"
TITLE_INLAY_STL_NAME = "mission1_field_case_lid_title_inlay.stl"
SUBTITLE_INLAY_STL_NAME = "mission1_field_case_lid_subtitle_inlay.stl"
PROJECT_3MF_NAME = "mission1_field_case_ams_project.3mf"

PRINTABLE_STL_NAMES = (
    BASE_STL_NAME,
    LID_STL_NAME,
    LOWER_TRAY_STL_NAME,
    LID_RETAINER_STL_NAME,
    GASKET_STL_NAME,
    LATCH_HANDLE_STL_NAME,
    LATCH_BAIL_STL_NAME,
    LATCH_BASE_PIN_STL_NAME,
    LATCH_LINK_PIN_STL_NAME,
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
# The optional soft MISSION 1 Pro lens hood flares beyond the square lens
# housing.  Its tray relief is a plan-view trapezoid: narrow at the lens base
# and wider/longer toward the hood mouth, matching the supplied case photos.
LENS_HOOD_INNER_Y = mission1.LENS_FULL_SIZE_Y - 1.0
LENS_HOOD_OUTER_Y = mission1.LENS_FACE_Y + 10.0
LENS_HOOD_INNER_WIDTH = mission1.LENS_FACE_WIDTH + 1.6
LENS_HOOD_OUTER_WIDTH = 54.0 + 2.0 * CAMERA_POCKET_CLEARANCE_XY
LENS_HOOD_RELIEF_Z0 = 8.0
LENS_HOOD_RELIEF_Z1 = TRAY_HEIGHT + 0.5
CAMERA_LENS_PROJECTION = LENS_HOOD_OUTER_Y - mission1.BODY_DEPTH
CAMERA_OPPOSED_BODY_CLEARANCE = 4.0
CAMERA_PAIR_HALF_SEPARATION = (
    mission1.BODY_DEPTH + (CAMERA_LENS_PROJECTION + CAMERA_OPPOSED_BODY_CLEARANCE) / 2.0
)
CAMERA_LATERAL_NEST_OFFSET = 9.0
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

# The removable MISSION 1 battery-cage doors store edge-on in these two thin
# slots.  A widened top scoop makes each flexible door easy to pinch out.
BATTERY_DOOR_SLOT_SIZE = (4.6, 32.0)
BATTERY_DOOR_SLOT_FLOOR_Z = 3.0
BATTERY_DOOR_SLOT_CENTERS = ((-50.0, -48.0), (50.0, -48.0))
BATTERY_DOOR_FINGER_SCOOP_RADIUS = 5.0
BATTERY_DOOR_FINGER_SCOOP_DEPTH = 10.0

LID_RETAINER_HEIGHT = 12.4
LID_BUTTON_RELIEF_DEPTH = 4.2
LID_BUTTON_RELIEF_CLEARANCE = 1.0
LID_PAD_KEY_CENTER = (-42.0, -69.0)
LID_PAD_KEY_NOTCH_SIZE = (14.0, 8.0)
LID_PAD_KEY_BOSS_SIZE = (12.0, 6.0, 4.0)

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

# Two independently generated, two-link over-center draw latches.  A central
# handle pivots on the base ears.  A separate U-shaped bail pivots on the
# handle, hooks the lid catch, and elastically crosses the fixed-pivot/catch
# centerline during closing.  This is a real toggle linkage rather than the
# earlier one-piece snap lip.
LATCH_X_CENTERS = (-38.0, 38.0)
LATCH_PIVOT_DIAMETER = 3.0
LATCH_PIVOT_HOLE_DIAMETER = 3.6
LATCH_PIVOT_Z = 46.5
LATCH_EAR_WIDTH = 4.0
LATCH_MOUNT_CLEARANCE = 0.35
LATCH_MOUNT_OFFSET_Y = 7.0
LATCH_BASE_PIVOT_Y = -CASE_DEPTH / 2.0 - LATCH_MOUNT_OFFSET_Y

LATCH_HANDLE_WIDTH = 20.0
LATCH_HANDLE_DEPTH = 5.2
LATCH_HANDLE_STEM_HEIGHT = 33.0
LATCH_HANDLE_PULL_TAB_WIDTH = 22.0
LATCH_HANDLE_PULL_TAB_HEIGHT = 20.0
LATCH_HANDLE_BASE_AXIS_LOCAL_Z = 4.5
LATCH_HANDLE_BASE_BARREL_DIAMETER = 8.8
LATCH_HANDLE_LINK_BARREL_DIAMETER = 6.4
LATCH_HANDLE_LINK_RADIUS = 8.0
LATCH_TARGET_OVER_CENTER_OFFSET = 2.0
LATCH_PULL_TAB_EAR_CLEARANCE = 0.5

LATCH_BAIL_OUTER_WIDTH = 43.0
LATCH_BAIL_RAIL_WIDTH = 3.5
LATCH_BAIL_FRAME_DEPTH = 4.8
LATCH_BAIL_PIVOT_LOCAL_Z = LATCH_HANDLE_LINK_BARREL_DIAMETER / 2.0
LATCH_BAIL_BRIDGE_HEIGHT = 5.0
LATCH_BAIL_HOOK_LIP_HEIGHT = 2.4
LATCH_BAIL_HOOK_FINGER_WIDTH = 3.0
LATCH_BAIL_HOOK_FINGER_CENTER_X = 6.5
LATCH_BAIL_CATCH_RUNNING_CLEARANCE = 0.45
LATCH_BAIL_HOOK_JOINT_OVERLAP = 0.3
LATCH_BAIL_HOOK_RISER_DEPTH = 1.2

LATCH_CATCH_WIDTH = 18.0
LATCH_CATCH_DIAMETER = 5.0
LATCH_CATCH_SUPPORT_WIDTH = 9.0
LATCH_CATCH_LOCAL_Y = CASE_DEPTH / 2.0 + 5.0
LATCH_CATCH_LOCAL_Z = 6.5
LATCH_LID_INSTALLED_Z = BASE_HEIGHT + LID_WALL_HEIGHT
LATCH_CATCH_WORLD_Y = -LATCH_CATCH_LOCAL_Y
LATCH_CATCH_WORLD_Z = LATCH_LID_INSTALLED_Z - LATCH_CATCH_LOCAL_Z

_LATCH_PC_Y = LATCH_CATCH_WORLD_Y - LATCH_BASE_PIVOT_Y
_LATCH_PC_Z = LATCH_CATCH_WORLD_Z - LATCH_PIVOT_Z
LATCH_FIXED_SPAN = math.hypot(_LATCH_PC_Y, _LATCH_PC_Z)
_LATCH_PC_UNIT_Y = _LATCH_PC_Y / LATCH_FIXED_SPAN
_LATCH_PC_UNIT_Z = _LATCH_PC_Z / LATCH_FIXED_SPAN
_LATCH_Q_ALONG = math.sqrt(
    LATCH_HANDLE_LINK_RADIUS**2 - LATCH_TARGET_OVER_CENTER_OFFSET**2
)
# Outward is toward more-negative world Y at the front of the case.
LATCH_LINK_PIVOT_WORLD_Y = (
    LATCH_BASE_PIVOT_Y
    - _LATCH_Q_ALONG * _LATCH_PC_UNIT_Y
    + LATCH_TARGET_OVER_CENTER_OFFSET * _LATCH_PC_UNIT_Z
)
LATCH_LINK_PIVOT_WORLD_Z = (
    LATCH_PIVOT_Z
    - _LATCH_Q_ALONG * _LATCH_PC_UNIT_Z
    - LATCH_TARGET_OVER_CENTER_OFFSET * _LATCH_PC_UNIT_Y
)
LATCH_HANDLE_INSTALL_TRANSLATE_Y = LATCH_BASE_PIVOT_Y + LATCH_HANDLE_BASE_AXIS_LOCAL_Z
LATCH_HANDLE_LINK_AXIS_LOCAL_Y = LATCH_LINK_PIVOT_WORLD_Z - LATCH_PIVOT_Z
LATCH_HANDLE_LINK_AXIS_LOCAL_Z = (
    LATCH_HANDLE_INSTALL_TRANSLATE_Y - LATCH_LINK_PIVOT_WORLD_Y
)
LATCH_BAIL_EFFECTIVE_LENGTH = math.hypot(
    LATCH_CATCH_WORLD_Y - LATCH_LINK_PIVOT_WORLD_Y,
    LATCH_CATCH_WORLD_Z - LATCH_LINK_PIVOT_WORLD_Z,
)
LATCH_DEAD_CENTER_TRAVEL = (
    LATCH_FIXED_SPAN + LATCH_HANDLE_LINK_RADIUS - LATCH_BAIL_EFFECTIVE_LENGTH
)
LATCH_BAIL_CLOSED_ANGLE = math.atan2(
    LATCH_CATCH_WORLD_Z - LATCH_LINK_PIVOT_WORLD_Z,
    LATCH_CATCH_WORLD_Y - LATCH_LINK_PIVOT_WORLD_Y,
)
LATCH_BAIL_HOOK_REACH = LATCH_CATCH_DIAMETER - LATCH_BAIL_CATCH_RUNNING_CLEARANCE
LATCH_BAIL_BRIDGE_START_Y = LATCH_BAIL_EFFECTIVE_LENGTH + LATCH_CATCH_DIAMETER / 2.0
LATCH_BAIL_LENGTH = LATCH_BAIL_BRIDGE_START_Y + LATCH_BAIL_BRIDGE_HEIGHT
LATCH_BAIL_HOOK_FINGER_HEIGHT = LATCH_BAIL_HOOK_LIP_HEIGHT + 0.3
LATCH_BAIL_HOOK_UNDERSIDE_Z = (
    LATCH_BAIL_PIVOT_LOCAL_Z
    + LATCH_CATCH_DIAMETER / 2.0
    + LATCH_BAIL_CATCH_RUNNING_CLEARANCE
)

LATCH_EAR_INNER_X = max(
    LATCH_HANDLE_WIDTH / 2.0 + 0.4,
    LATCH_HANDLE_PULL_TAB_WIDTH / 2.0 + LATCH_PULL_TAB_EAR_CLEARANCE,
)
LATCH_EAR_SHELL_Y = -CASE_DEPTH / 2.0 + 0.3
LATCH_EAR_LOWER_PIVOT_Z = 43.0
LATCH_EAR_LOWER_SHELL_Z = 37.0
LATCH_EAR_PROFILE_YZ = (
    (LATCH_EAR_SHELL_Y, 31.0),
    (LATCH_EAR_SHELL_Y, 52.0),
    (LATCH_BASE_PIVOT_Y, 52.0),
    (LATCH_BASE_PIVOT_Y - 4.5, LATCH_PIVOT_Z),
    (LATCH_BASE_PIVOT_Y, LATCH_EAR_LOWER_PIVOT_Z),
    (LATCH_EAR_SHELL_Y, LATCH_EAR_LOWER_SHELL_Z),
)
LATCH_BASE_PIN_LENGTH = 2.0 * (LATCH_EAR_INNER_X + LATCH_EAR_WIDTH) + 1.0
LATCH_LINK_PIN_LENGTH = LATCH_BAIL_OUTER_WIDTH + 1.0
LATCH_STOP_DEPTH = 2.7
LATCH_STOP_CENTER_Y = -CASE_DEPTH / 2.0 - 1.15

LATCH_HANDLE_PRINT_OFFSET_Y = -150.0
LATCH_BAIL_PRINT_OFFSET_Y = -200.0
LATCH_BASE_PIN_PRINT_OFFSET_Y = -235.0
LATCH_LINK_PIN_PRINT_OFFSET_Y = -250.0

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
LID_TITLE_SIZE = 12.0
LID_SUBTITLE_SIZE = 6.2
LID_TITLE_MAX_WIDTH = 122.0
LID_SUBTITLE_MAX_WIDTH = 118.0
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


def extrude_loop_z(name: str, loop_xy, z0: float, z1: float):
    count = len(loop_xy)
    vertices = [(x, y, z0) for x, y in loop_xy]
    vertices.extend((x, y, z1) for x, y in loop_xy)
    faces = [list(reversed(range(count))), list(range(count, count * 2))]
    for index in range(count):
        next_index = (index + 1) % count
        faces.append((index, next_index, count + next_index, count + index))
    return create_mesh_object(name, vertices, faces)


def add_teardrop_hole_x(name, radius, length, location, arc_steps=30):
    """Create a self-supporting horizontal-bore cutter with 45-degree roof."""
    center_x, center_y, center_z = location
    angles = [
        math.radians(45.0 - 270.0 * step / arc_steps) for step in range(arc_steps + 1)
    ]
    loop = [
        (
            center_y + radius * math.cos(angle),
            center_z + radius * math.sin(angle),
        )
        for angle in angles
    ]
    loop.append((center_y, center_z + math.sqrt(2.0) * radius))
    return extrude_loop_x(
        name,
        loop,
        center_x - length / 2.0,
        center_x + length / 2.0,
    )


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


def union_into(target, component, solver=BOOLEAN_SOLVER):
    return boolean_apply(target, component, "UNION", solver=solver)


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


def lens_hood_relief_loop(placement):
    """Return the opposed camera's soft lens-hood relief in tray XY."""
    canonical = (
        (
            mission1.LENS_CENTER_X - LENS_HOOD_INNER_WIDTH / 2.0,
            LENS_HOOD_INNER_Y,
        ),
        (
            mission1.LENS_CENTER_X + LENS_HOOD_INNER_WIDTH / 2.0,
            LENS_HOOD_INNER_Y,
        ),
        (
            mission1.LENS_CENTER_X + LENS_HOOD_OUTER_WIDTH / 2.0,
            LENS_HOOD_OUTER_Y,
        ),
        (
            mission1.LENS_CENTER_X - LENS_HOOD_OUTER_WIDTH / 2.0,
            LENS_HOOD_OUTER_Y,
        ),
    )
    return tuple(transform_reference_xy(point, placement) for point in canonical)


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
    _source_minimum, source_maximum = object_world_bounds(source)
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

    # Cut 0.1 mm through the build-facing surface, but stop at the inlay's top
    # plane.  The shared horizontal face bonds AMS-printed text to the lid;
    # leaving overcut above the inlay would produce physically loose glyphs.
    dims = object_world_dimensions(cutter)
    cutter.scale.z *= (dims.z + 0.1) / dims.z
    select_only(cutter)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    _minimum, maximum = object_world_bounds(cutter)
    cutter.location.z += source_maximum.z - maximum.z
    bpy.context.view_layer.update()
    _minimum, maximum = object_world_bounds(cutter)
    if not math.isclose(maximum.z, source_maximum.z, abs_tol=1e-6):
        raise RuntimeError(f"{name} does not preserve the inlay bonding plane")
    return cutter


# ---------------------------------------------------------------------------
# VALIDATION


def rectangles_overlap(a_center, a_size, b_center, b_size, gap=0.0):
    return (
        abs(a_center[0] - b_center[0]) < (a_size[0] + b_size[0]) / 2.0 + gap
        and abs(a_center[1] - b_center[1]) < (a_size[1] + b_size[1]) / 2.0 + gap
    )


def point_segment_distance_2d(point, start, end) -> float:
    segment_x = end[0] - start[0]
    segment_y = end[1] - start[1]
    length_squared = segment_x * segment_x + segment_y * segment_y
    if length_squared <= 1e-12:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    projection = (
        (point[0] - start[0]) * segment_x + (point[1] - start[1]) * segment_y
    ) / length_squared
    projection = max(0.0, min(1.0, projection))
    nearest = (
        start[0] + projection * segment_x,
        start[1] + projection * segment_y,
    )
    return math.hypot(point[0] - nearest[0], point[1] - nearest[1])


def point_in_polygon_2d(point, polygon) -> bool:
    inside = False
    for start, end in zip(polygon, polygon[1:] + polygon[:1]):
        if (start[1] > point[1]) == (end[1] > point[1]):
            continue
        crossing_x = start[0] + (point[1] - start[1]) * (end[0] - start[0]) / (
            end[1] - start[1]
        )
        if point[0] < crossing_x:
            inside = not inside
    return inside


def latch_link_pin_sweep_clearance(sample_count=720) -> float:
    """Return minimum radial clearance from the link pin to a fixed ear."""
    open_pivot = latch_open_link_pivot()
    closed_angle = math.atan2(
        LATCH_LINK_PIVOT_WORLD_Z - LATCH_PIVOT_Z,
        LATCH_LINK_PIVOT_WORLD_Y - LATCH_BASE_PIVOT_Y,
    )
    open_angle = math.atan2(
        open_pivot[1] - LATCH_PIVOT_Z,
        open_pivot[0] - LATCH_BASE_PIVOT_Y,
    )
    sweep_angle = (open_angle - closed_angle + math.pi) % (2.0 * math.pi) - math.pi
    minimum_center_distance = math.inf
    for sample in range(sample_count + 1):
        angle = closed_angle + sweep_angle * sample / sample_count
        center = (
            LATCH_BASE_PIVOT_Y + LATCH_HANDLE_LINK_RADIUS * math.cos(angle),
            LATCH_PIVOT_Z + LATCH_HANDLE_LINK_RADIUS * math.sin(angle),
        )
        if point_in_polygon_2d(center, LATCH_EAR_PROFILE_YZ):
            return -LATCH_PIVOT_DIAMETER / 2.0
        center_distance = min(
            point_segment_distance_2d(center, start, end)
            for start, end in zip(
                LATCH_EAR_PROFILE_YZ,
                LATCH_EAR_PROFILE_YZ[1:] + LATCH_EAR_PROFILE_YZ[:1],
            )
        )
        minimum_center_distance = min(minimum_center_distance, center_distance)
    return minimum_center_distance - LATCH_PIVOT_DIAMETER / 2.0


def latch_open_bridge_lid_clearance(sample_count=720) -> float:
    """Return conservative clearance from the open bail bridge to the lid."""
    open_pivot = latch_open_link_pivot()
    rotation = math.atan2(
        LATCH_CATCH_WORLD_Z - open_pivot[1],
        LATCH_CATCH_WORLD_Y - open_pivot[0],
    )
    location_y = open_pivot[0] + math.sin(rotation) * LATCH_BAIL_PIVOT_LOCAL_Z
    location_z = open_pivot[1] - math.cos(rotation) * LATCH_BAIL_PIVOT_LOCAL_Z
    lid_front_y = -CASE_DEPTH / 2.0
    lid_plate_bottom_z = LATCH_LID_INSTALLED_Z - LID_PLATE_THICKNESS
    lid_plate_top_z = LATCH_LID_INSTALLED_Z
    minimum_clearance = math.inf
    for sample in range(sample_count + 1):
        local_y = (
            LATCH_BAIL_BRIDGE_START_Y + LATCH_BAIL_BRIDGE_HEIGHT * sample / sample_count
        )
        world_y = location_y + math.cos(rotation) * local_y
        world_z = location_z + math.sin(rotation) * local_y
        delta_y = max(lid_front_y - world_y, 0.0)
        if world_z < lid_plate_bottom_z:
            delta_z = lid_plate_bottom_z - world_z
        elif world_z > lid_plate_top_z:
            delta_z = world_z - lid_plate_top_z
        else:
            delta_z = 0.0
        minimum_clearance = min(minimum_clearance, math.hypot(delta_y, delta_z))
    return minimum_clearance


def validate_configuration() -> None:
    inner_width = CASE_WIDTH - 2.0 * WALL_THICKNESS
    inner_depth = CASE_DEPTH - 2.0 * WALL_THICKNESS
    tray_width = inner_width - 2.0 * INSERT_SIDE_CLEARANCE
    tray_depth = inner_depth - 2.0 * INSERT_SIDE_CLEARANCE

    if BATTERY_POCKET_WIDTH < BATTERY_THICKNESS or BATTERY_POCKET_DEPTH < BATTERY_WIDTH:
        raise ValueError("Battery pockets do not clear the Enduro envelope")
    if min(WALL_THICKNESS, BASE_FLOOR_THICKNESS, TRAY_FLOOR_THICKNESS) < 2.0:
        raise ValueError("Default shell walls and all floors must remain at least 2 mm")

    retainer_width = tray_width
    retainer_depth = tray_depth
    key_x, key_y = LID_PAD_KEY_CENTER
    notch_width, notch_depth = LID_PAD_KEY_NOTCH_SIZE
    boss_width, boss_depth, boss_height = LID_PAD_KEY_BOSS_SIZE
    if notch_width - boss_width < 1.0 or notch_depth - boss_depth < 1.0:
        raise ValueError("Lid-pad key needs at least 0.5 mm clearance per side")
    if boss_height <= 1.0:
        raise ValueError("Lid-pad key boss is too shallow to reject reverse seating")
    if abs(key_x) + notch_width / 2.0 >= retainer_width / 2.0:
        raise ValueError("Lid-pad key notch must remain clear of the side perimeter")
    notch_min_y = key_y - notch_depth / 2.0
    notch_max_y = key_y + notch_depth / 2.0
    if not notch_min_y <= -retainer_depth / 2.0 < notch_max_y:
        raise ValueError("Lid-pad key notch must remain open through one end perimeter")

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

    hood_bounds = []
    for placement in CAMERA_PLACEMENTS:
        hood_loop = lens_hood_relief_loop(placement)
        min_x = min(point[0] for point in hood_loop)
        max_x = max(point[0] for point in hood_loop)
        min_y = min(point[1] for point in hood_loop)
        max_y = max(point[1] for point in hood_loop)
        hood_bounds.append((min_x, max_x, min_y, max_y))
        if min_x < -tray_width / 2.0 or max_x > tray_width / 2.0:
            raise ValueError("Soft lens-hood relief exceeds the tray width")
        if min_y < -tray_depth / 2.0 or max_y > tray_depth / 2.0:
            raise ValueError("Soft lens-hood relief exceeds the tray depth")
    hood_lateral_web = max(
        hood_bounds[1][0] - hood_bounds[0][1],
        hood_bounds[0][0] - hood_bounds[1][1],
    )
    if hood_lateral_web < MIN_CAMERA_POCKET_WEB:
        raise ValueError(
            f"Soft lens-hood reliefs need a {MIN_CAMERA_POCKET_WEB:.1f} mm TPU "
            f"web; computed {hood_lateral_web:.2f} mm"
        )
    camera_1_hood_front = CAMERA_PLACEMENTS[0][1] + LENS_HOOD_OUTER_Y
    camera_2_body_face = CAMERA_PLACEMENTS[1][1] - mission1.BODY_DEPTH
    hood_body_web = camera_2_body_face - camera_1_hood_front
    if hood_body_web < CAMERA_OPPOSED_BODY_CLEARANCE - 1e-6:
        raise ValueError(
            "Opposed soft lens hood does not clear the other camera body; "
            f"computed {hood_body_web:.2f} mm"
        )

    battery_size = (BATTERY_POCKET_WIDTH, BATTERY_POCKET_DEPTH)
    for index, center in enumerate(BATTERY_CENTERS):
        if abs(center[0]) + battery_size[0] / 2.0 > tray_width / 2.0:
            raise ValueError(f"Battery cavity exceeds tray width: {center}")
        if abs(center[1]) + battery_size[1] / 2.0 > tray_depth / 2.0:
            raise ValueError(f"Battery cavity exceeds tray depth: {center}")
        for other in BATTERY_CENTERS[index + 1 :]:
            if rectangles_overlap(center, battery_size, other, battery_size, gap=2.0):
                raise ValueError(
                    "Battery cavities overlap or have less than 2 mm clearance: "
                    f"{center} and {other}"
                )
        battery_top = center[1] + battery_size[1] / 2.0
        nearest_camera = min(bounds[2] for bounds in camera_bounds)
        if battery_top + 4.0 > nearest_camera:
            raise ValueError("Battery row needs 4 mm clearance from the camera pair")

    door_slot_size = BATTERY_DOOR_SLOT_SIZE
    for center in BATTERY_DOOR_SLOT_CENTERS:
        if abs(center[0]) + door_slot_size[0] / 2.0 > tray_width / 2.0:
            raise ValueError(f"Battery-cage-door slot exceeds tray width: {center}")
        if abs(center[1]) + door_slot_size[1] / 2.0 > tray_depth / 2.0:
            raise ValueError(f"Battery-cage-door slot exceeds tray depth: {center}")
        for battery_center in BATTERY_CENTERS:
            if rectangles_overlap(
                center,
                door_slot_size,
                battery_center,
                battery_size,
                gap=2.0,
            ):
                raise ValueError(
                    "Battery-cage-door slot collides with a battery pocket"
                )
        nearest_camera = min(bounds[2] for bounds in camera_bounds)
        if center[1] + door_slot_size[1] / 2.0 + 4.0 > nearest_camera:
            raise ValueError("Battery-cage-door slot needs 4 mm camera clearance")

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

    pc_y = LATCH_CATCH_WORLD_Y - LATCH_BASE_PIVOT_Y
    pc_z = LATCH_CATCH_WORLD_Z - LATCH_PIVOT_Z
    pq_y = LATCH_LINK_PIVOT_WORLD_Y - LATCH_BASE_PIVOT_Y
    pq_z = LATCH_LINK_PIVOT_WORLD_Z - LATCH_PIVOT_Z
    along_fixed_line = (pc_y * pq_y + pc_z * pq_z) / LATCH_FIXED_SPAN
    over_center_offset = (pc_y * pq_z - pc_z * pq_y) / LATCH_FIXED_SPAN
    if along_fixed_line >= 0.0:
        raise ValueError(
            "Latch moving pivot must close on the side of the base pivot opposite "
            "the lid catch"
        )
    if not 1.5 <= abs(over_center_offset) <= 2.5:
        raise ValueError(
            "Closed latch needs a 1.5-2.5 mm over-center offset; "
            f"computed {over_center_offset:.3f} mm"
        )
    if not 0.10 <= LATCH_DEAD_CENTER_TRAVEL <= 0.25:
        raise ValueError(
            "Latch peak draw at dead center must remain 0.10-0.25 mm; "
            f"computed {LATCH_DEAD_CENTER_TRAVEL:.3f} mm"
        )
    over_center_angle = math.degrees(
        math.asin(abs(over_center_offset) / LATCH_HANDLE_LINK_RADIUS)
    )
    if not 10.0 <= over_center_angle <= 16.0:
        raise ValueError(
            "Latch over-center angle must remain 10-16 degrees; "
            f"computed {over_center_angle:.2f} degrees"
        )

    bail_inner_width = LATCH_BAIL_OUTER_WIDTH - 2.0 * LATCH_BAIL_RAIL_WIDTH
    bail_handle_clearance = (bail_inner_width - LATCH_HANDLE_WIDTH) / 2.0
    bail_catch_clearance = (bail_inner_width - LATCH_CATCH_WIDTH) / 2.0
    bail_ear_clearance = bail_inner_width / 2.0 - (LATCH_EAR_INNER_X + LATCH_EAR_WIDTH)
    pull_tab_ear_clearance = LATCH_EAR_INNER_X - LATCH_HANDLE_PULL_TAB_WIDTH / 2.0
    link_pin_ear_sweep_clearance = latch_link_pin_sweep_clearance()
    open_bridge_lid_clearance = latch_open_bridge_lid_clearance()
    hook_radial_clearance = LATCH_BAIL_HOOK_UNDERSIDE_Z - (
        LATCH_BAIL_PIVOT_LOCAL_Z + LATCH_CATCH_DIAMETER / 2.0
    )
    hook_overlap = LATCH_CATCH_DIAMETER / 2.0 - LATCH_BAIL_CATCH_RUNNING_CLEARANCE
    hook_finger_tail_y = (
        LATCH_BAIL_BRIDGE_START_Y
        - LATCH_BAIL_HOOK_REACH / 2.0
        + 0.3
        + (LATCH_BAIL_HOOK_REACH + 0.6) / 2.0
    )
    hook_finger_bridge_overlap = hook_finger_tail_y - LATCH_BAIL_BRIDGE_START_Y
    support_overhang = (LATCH_CATCH_WIDTH - LATCH_CATCH_SUPPORT_WIDTH) / 2.0
    finger_inner_clearance = (
        LATCH_BAIL_HOOK_FINGER_CENTER_X
        - LATCH_BAIL_HOOK_FINGER_WIDTH / 2.0
        - LATCH_CATCH_SUPPORT_WIDTH / 2.0
    )
    finger_outer_margin = (
        LATCH_CATCH_WIDTH / 2.0
        - LATCH_BAIL_HOOK_FINGER_CENTER_X
        - LATCH_BAIL_HOOK_FINGER_WIDTH / 2.0
    )
    for name, value, minimum in (
        ("bail-to-handle lateral clearance", bail_handle_clearance, 0.6),
        ("bail-to-catch lateral clearance", bail_catch_clearance, 1.0),
        ("bail-to-base-ear lateral clearance", bail_ear_clearance, 0.8),
        ("pull-tab clearance from fixed ear", pull_tab_ear_clearance, 0.4),
        ("link-pin swept clearance from fixed ear", link_pin_ear_sweep_clearance, 0.8),
        ("open bail bridge clearance from lid", open_bridge_lid_clearance, 0.5),
        ("bail hook radial running clearance", hook_radial_clearance, 0.4),
        ("bail hook bridge joint", hook_finger_bridge_overlap, 0.5),
        ("bail hook overlap", hook_overlap, 1.5),
        ("catch support side overhang", support_overhang, 3.5),
        ("hook-finger clearance from catch support", finger_inner_clearance, 0.4),
        ("hook-finger margin inside catch end", finger_outer_margin, 0.5),
    ):
        if value < minimum:
            raise ValueError(
                f"Latch {name} needs {minimum:.2f} mm; computed {value:.2f}"
            )
    if LATCH_PIVOT_HOLE_DIAMETER - LATCH_PIVOT_DIAMETER < 0.4:
        raise ValueError("Latch pins need at least 0.4 mm diametral hole clearance")
    if LATCH_BASE_PIN_LENGTH < 2.0 * (LATCH_EAR_INNER_X + LATCH_EAR_WIDTH):
        raise ValueError("Latch base pin does not span both base ears")
    if LATCH_LINK_PIN_LENGTH < LATCH_BAIL_OUTER_WIDTH:
        raise ValueError("Latch link pin does not span both bail ears")
    stop_outer_y = LATCH_STOP_CENTER_Y - LATCH_STOP_DEPTH / 2.0
    if not math.isclose(
        stop_outer_y,
        LATCH_HANDLE_INSTALL_TRANSLATE_Y,
        abs_tol=0.05,
    ):
        raise ValueError("Latch handle and positive closed stop do not meet")

    # Conservative analytic envelopes include every projection on each part.
    base_print_width = max(CASE_WIDTH + 7.8, HANDLE_OUTER_SIZE[0])
    handle_front = HANDLE_CENTER_Y - HANDLE_OUTER_SIZE[1] / 2.0
    hinge_back = HINGE_AXIS_Y + HINGE_OUTER_DIAMETER / 2.0
    base_print_depth = hinge_back - handle_front
    lid_print_width = CASE_WIDTH + 2.0 * LID_FLANGE_OUTSET
    lid_front = max(
        CASE_DEPTH / 2.0 + LID_FLANGE_OUTSET,
        LATCH_CATCH_LOCAL_Y + LATCH_CATCH_DIAMETER / 2.0,
    )
    lid_back = -HINGE_AXIS_Y - HINGE_OUTER_DIAMETER / 2.0
    lid_print_depth = lid_front - lid_back
    for part, dimensions in (
        ("base", (base_print_width, base_print_depth)),
        ("lid", (lid_print_width, lid_print_depth)),
        ("lower TPU tray", (tray_width, tray_depth)),
        ("lid retainer", (tray_width, tray_depth)),
        ("gasket", (CASE_WIDTH - 3.8, CASE_DEPTH - 3.8)),
        (
            "over-center latch handle",
            (LATCH_HANDLE_PULL_TAB_WIDTH, LATCH_HANDLE_STEM_HEIGHT),
        ),
        ("over-center latch bail", (LATCH_BAIL_OUTER_WIDTH, LATCH_BAIL_LENGTH)),
        ("latch base pin", (LATCH_BASE_PIN_LENGTH + 2.2, 6.0)),
        ("latch link pin", (LATCH_LINK_PIN_LENGTH + 2.2, 6.0)),
        ("hinge pin", (HINGE_PIN_X1 - HINGE_PIN_X0 + 2.1, 6.0)),
    ):
        if dimensions[0] > MAX_PRINT_XY or dimensions[1] > MAX_PRINT_XY:
            raise ValueError(f"{part} exceeds {MAX_PRINT_XY:.0f} mm: {dimensions}")

    print(
        "FIELD_CASE_CONFIG "
        f"shell={CASE_WIDTH:.1f}x{CASE_DEPTH:.1f}x{BASE_HEIGHT:.1f} "
        f"tray={tray_width:.1f}x{tray_depth:.1f}x{TRAY_HEIGHT:.1f} "
        f"lens_web={lateral_lens_web:.2f} hood_web={hood_lateral_web:.2f} "
        f"hood_body_web={hood_body_web:.2f} axial_web={axial_body_web:.2f} "
        f"pad_preload={pad_compression:.2f} "
        f"latch_over_center={over_center_offset:.3f} "
        f"latch_angle={over_center_angle:.2f} "
        f"latch_peak_draw={LATCH_DEAD_CENTER_TRAVEL:.3f} "
        f"latch_pin_ear_clearance={link_pin_ear_sweep_clearance:.3f} "
        f"latch_hook_clearance={hook_radial_clearance:.3f} "
        f"latch_open_lid_clearance={open_bridge_lid_clearance:.3f}"
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

    # Each handle pivots between two self-supporting teardrop arms.  Their
    # 45-degree lower edges grow outward from the shell without a floating
    # cantilever, while the moving link pin remains below the arm in the full
    # closed-to-open sweep.  The bail rails run laterally outside these arms.
    mount_y = LATCH_BASE_PIVOT_Y
    for index, x in enumerate(LATCH_X_CENTERS, start=1):
        for side in (-1.0, 1.0):
            ear_x = x + side * (LATCH_EAR_INNER_X + LATCH_EAR_WIDTH / 2.0)
            x0 = ear_x - LATCH_EAR_WIDTH / 2.0
            x1 = ear_x + LATCH_EAR_WIDTH / 2.0
            ear = extrude_loop_x(
                f"Base_Latch_{index}_Pivot_Ear",
                LATCH_EAR_PROFILE_YZ,
                x0,
                x1,
            )
            hole = add_teardrop_hole_x(
                f"Base_Latch_{index}_Pivot_Hole",
                LATCH_PIVOT_HOLE_DIAMETER / 2.0,
                LATCH_EAR_WIDTH + 0.8,
                (ear_x, mount_y, LATCH_PIVOT_Z),
            )
            difference_from(ear, hole)
            union_into(base, ear)

        stop = add_rounded_box(
            f"Base_Latch_{index}_Positive_Closed_Stop",
            (12.0, LATCH_STOP_DEPTH, 10.0),
            (x, LATCH_STOP_CENTER_Y, 29.0),
            bevel=0.8,
        )
        union_into(base, stop)

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

        hood_relief = extrude_loop_z(
            f"Camera_{index}_Soft_Lens_Hood_Flare_Relief",
            lens_hood_relief_loop(placement),
            LENS_HOOD_RELIEF_Z0,
            LENS_HOOD_RELIEF_Z1,
        )
        difference_from(tray, hood_relief)

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

    for index, center in enumerate(BATTERY_DOOR_SLOT_CENTERS, start=1):
        slot = add_rounded_prism(
            f"Battery_Cage_Door_{index}_Thin_Storage_Slot",
            BATTERY_DOOR_SLOT_SIZE[0],
            BATTERY_DOOR_SLOT_SIZE[1],
            BATTERY_DOOR_SLOT_FLOOR_Z,
            TRAY_HEIGHT + 0.4,
            1.3,
            center,
        )
        difference_from(tray, slot)
        door_scoop = add_cylinder_z(
            f"Battery_Cage_Door_{index}_Finger_Scoop",
            BATTERY_DOOR_FINGER_SCOOP_RADIUS,
            BATTERY_DOOR_FINGER_SCOOP_DEPTH,
            (center[0], center[1], TRAY_HEIGHT - BATTERY_DOOR_FINGER_SCOOP_DEPTH / 2.0),
            vertices=40,
        )
        difference_from(tray, door_scoop)

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

    # The asymmetric interior boss mates with the TPU pad's open perimeter
    # notch.  A 180-degree-misrotated pad therefore cannot sit flat with its
    # two camera-button reliefs over the wrong ends of the cameras.
    key_boss = add_rounded_box(
        "Lid_Pad_One_Way_Orientation_Key",
        LID_PAD_KEY_BOSS_SIZE,
        (
            dx + LID_PAD_KEY_CENTER[0],
            LID_PAD_KEY_CENTER[1],
            LID_PLATE_THICKNESS + 1.5,
        ),
        bevel=0.7,
    )
    union_into(lid, key_boss)

    # Rounded catch bars map to the case front after the lid is turned over.
    # Each narrow central gusset grows from the exterior-face build plane at no
    # more than 45 degrees, supports the complete bar, and leaves side
    # overhangs for the bail's paired J-hook fingers.
    for index, x in enumerate(LATCH_X_CENTERS, start=1):
        support = extrude_loop_x(
            f"Lid_Over_Center_Catch_Support_{index}",
            (
                (CASE_DEPTH / 2.0 - 1.0, 0.0),
                (CASE_DEPTH / 2.0, 0.0),
                (
                    LATCH_CATCH_LOCAL_Y + LATCH_CATCH_DIAMETER / 2.0,
                    LATCH_CATCH_LOCAL_Z,
                ),
                (
                    LATCH_CATCH_LOCAL_Y,
                    LATCH_CATCH_LOCAL_Z + LATCH_CATCH_DIAMETER / 2.0,
                ),
                (
                    CASE_DEPTH / 2.0 - 1.0,
                    LATCH_CATCH_LOCAL_Z + LATCH_CATCH_DIAMETER / 2.0,
                ),
            ),
            dx + x - LATCH_CATCH_SUPPORT_WIDTH / 2.0,
            dx + x + LATCH_CATCH_SUPPORT_WIDTH / 2.0,
        )
        union_into(lid, support)
        catch = add_cylinder_x(
            f"Lid_Over_Center_Latch_Catch_{index}",
            LATCH_CATCH_DIAMETER / 2.0,
            LATCH_CATCH_WIDTH,
            (dx + x, LATCH_CATCH_LOCAL_Y, LATCH_CATCH_LOCAL_Z),
            vertices=48,
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

    key_notch = add_rounded_prism(
        "TPU_Lid_Pad_One_Way_Key_Notch",
        LID_PAD_KEY_NOTCH_SIZE[0],
        LID_PAD_KEY_NOTCH_SIZE[1],
        -0.2,
        LID_RETAINER_HEIGHT + 0.3,
        1.4,
        LID_PAD_KEY_CENTER,
    )
    difference_from(retainer, key_notch)

    translate_object(retainer, (LID_DISPLAY_OFFSET_X, 220.0, 0.0))
    assign_material(retainer, material)
    return retainer


def create_latch_handle(material):
    handle_top_y = 8.0
    handle_bottom_y = handle_top_y - LATCH_HANDLE_STEM_HEIGHT
    handle = add_rounded_prism(
        "Field_Case_Over_Center_Latch_Handle_Print_Two",
        LATCH_HANDLE_WIDTH,
        LATCH_HANDLE_STEM_HEIGHT,
        0.0,
        LATCH_HANDLE_DEPTH,
        3.0,
        (0.0, (handle_top_y + handle_bottom_y) / 2.0),
    )
    pull_tab = add_rounded_prism(
        "Over_Center_Latch_Broad_Pull_Tab",
        LATCH_HANDLE_PULL_TAB_WIDTH,
        LATCH_HANDLE_PULL_TAB_HEIGHT,
        0.0,
        LATCH_HANDLE_DEPTH,
        3.5,
        (0.0, handle_bottom_y + LATCH_HANDLE_PULL_TAB_HEIGHT / 2.0),
    )
    union_into(handle, pull_tab)

    base_barrel = add_cylinder_x(
        "Over_Center_Handle_Base_Pivot_Barrel",
        LATCH_HANDLE_BASE_BARREL_DIAMETER / 2.0,
        LATCH_HANDLE_WIDTH,
        (0.0, 0.0, LATCH_HANDLE_BASE_AXIS_LOCAL_Z),
        vertices=48,
    )
    union_into(handle, base_barrel)
    link_barrel = add_cylinder_x(
        "Over_Center_Handle_Moving_Link_Barrel",
        LATCH_HANDLE_LINK_BARREL_DIAMETER / 2.0,
        LATCH_HANDLE_WIDTH,
        (
            0.0,
            LATCH_HANDLE_LINK_AXIS_LOCAL_Y,
            LATCH_HANDLE_LINK_AXIS_LOCAL_Z,
        ),
        vertices=48,
    )
    union_into(handle, link_barrel)

    base_hole = add_teardrop_hole_x(
        "Over_Center_Handle_Base_Pivot_Hole",
        LATCH_PIVOT_HOLE_DIAMETER / 2.0,
        LATCH_HANDLE_WIDTH + 1.0,
        (0.0, 0.0, LATCH_HANDLE_BASE_AXIS_LOCAL_Z),
    )
    difference_from(handle, base_hole)
    link_hole = add_teardrop_hole_x(
        "Over_Center_Handle_Moving_Link_Hole",
        LATCH_PIVOT_HOLE_DIAMETER / 2.0,
        LATCH_HANDLE_WIDTH + 1.0,
        (
            0.0,
            LATCH_HANDLE_LINK_AXIS_LOCAL_Y,
            LATCH_HANDLE_LINK_AXIS_LOCAL_Z,
        ),
    )
    difference_from(handle, link_hole)

    translate_object(handle, (0.0, LATCH_HANDLE_PRINT_OFFSET_Y, 0.0))
    assign_material(handle, material)
    return handle


def create_latch_bail(material):
    rail_center_x = (LATCH_BAIL_OUTER_WIDTH - LATCH_BAIL_RAIL_WIDTH) / 2.0
    bridge = add_rounded_prism(
        "Field_Case_Over_Center_Latch_Bail_Print_Two",
        LATCH_BAIL_OUTER_WIDTH,
        LATCH_BAIL_BRIDGE_HEIGHT,
        0.0,
        LATCH_BAIL_FRAME_DEPTH,
        1.5,
        (
            0.0,
            LATCH_BAIL_BRIDGE_START_Y + LATCH_BAIL_BRIDGE_HEIGHT / 2.0,
        ),
    )
    for side in (-1.0, 1.0):
        rail = add_rounded_prism(
            "Over_Center_Bail_Side_Rail",
            LATCH_BAIL_RAIL_WIDTH,
            LATCH_BAIL_LENGTH,
            0.0,
            LATCH_BAIL_FRAME_DEPTH,
            1.2,
            (side * rail_center_x, LATCH_BAIL_LENGTH / 2.0),
        )
        union_into(bridge, rail, solver="MANIFOLD")
        pivot_ear = add_cylinder_x(
            "Over_Center_Bail_Moving_Pivot_Ear",
            LATCH_HANDLE_LINK_BARREL_DIAMETER / 2.0,
            LATCH_BAIL_RAIL_WIDTH,
            (side * rail_center_x, 0.0, LATCH_BAIL_PIVOT_LOCAL_Z),
            vertices=44,
        )
        union_into(bridge, pivot_ear, solver="MANIFOLD")
        pivot_hole = add_teardrop_hole_x(
            "Over_Center_Bail_Moving_Pivot_Hole",
            LATCH_PIVOT_HOLE_DIAMETER / 2.0,
            LATCH_BAIL_RAIL_WIDTH + 0.8,
            (side * rail_center_x, 0.0, LATCH_BAIL_PIVOT_LOCAL_Z),
        )
        difference_from(bridge, pivot_hole)

    # Paired raised fingers pass beside the catch's narrow central support and
    # wrap the two exposed bar overhangs.  Each elevated return finger clears
    # the catch radially, while a short far-side riser joins it to the bridge to
    # make a retained, printable J hook without blocking assembly.
    for side in (-1.0, 1.0):
        finger_length = LATCH_BAIL_HOOK_REACH + 0.6
        finger_center_y = LATCH_BAIL_BRIDGE_START_Y - LATCH_BAIL_HOOK_REACH / 2.0 + 0.3
        hook_finger = add_rounded_box(
            "Over_Center_Bail_Catch_Return_Finger",
            (
                LATCH_BAIL_HOOK_FINGER_WIDTH,
                finger_length,
                LATCH_BAIL_HOOK_FINGER_HEIGHT,
            ),
            (
                side * LATCH_BAIL_HOOK_FINGER_CENTER_X,
                finger_center_y,
                LATCH_BAIL_HOOK_UNDERSIDE_Z + LATCH_BAIL_HOOK_FINGER_HEIGHT / 2.0,
            ),
            bevel=0.65,
        )
        union_into(bridge, hook_finger, solver="MANIFOLD")
        riser_bottom_z = LATCH_BAIL_FRAME_DEPTH - LATCH_BAIL_HOOK_JOINT_OVERLAP
        riser_top_z = LATCH_BAIL_HOOK_UNDERSIDE_Z + LATCH_BAIL_HOOK_FINGER_HEIGHT
        hook_riser = add_rounded_box(
            "Over_Center_Bail_Catch_Return_Riser",
            (
                LATCH_BAIL_HOOK_FINGER_WIDTH,
                LATCH_BAIL_HOOK_RISER_DEPTH,
                riser_top_z - riser_bottom_z,
            ),
            (
                side * LATCH_BAIL_HOOK_FINGER_CENTER_X,
                LATCH_BAIL_BRIDGE_START_Y + LATCH_BAIL_HOOK_RISER_DEPTH / 2.0,
                (riser_bottom_z + riser_top_z) / 2.0,
            ),
            bevel=0.55,
        )
        union_into(bridge, hook_riser, solver="MANIFOLD")

    translate_object(bridge, (0.0, LATCH_BAIL_PRINT_OFFSET_Y, 0.0))
    assign_material(bridge, material)
    return bridge


def create_latch_pin(name, length, print_offset_y, material):
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
    x0 = -length / 2.0
    x1 = length / 2.0
    pin = extrude_loop_x(name, loop, x0, x1)
    head = add_rounded_box(
        name + "_Stop_Head",
        (2.2, 5.5, 3.0),
        (x0 - 1.0, 0.0, 1.5),
        bevel=0.65,
    )
    union_into(pin, head, solver="MANIFOLD")
    detent = add_rounded_box(
        name + "_Far_End_Friction_Detent",
        (0.8, 3.45, 3.1),
        (x1 - 0.2, 0.0, 1.55),
        bevel=0.45,
    )
    union_into(pin, detent, solver="MANIFOLD")
    translate_object(pin, (0.0, print_offset_y, 0.0))
    assign_material(pin, material)
    return pin


def create_latch_base_pin(material):
    return create_latch_pin(
        "Field_Case_Latch_Base_Pin_Print_Two",
        LATCH_BASE_PIN_LENGTH,
        LATCH_BASE_PIN_PRINT_OFFSET_Y,
        material,
    )


def create_latch_link_pin(material):
    return create_latch_pin(
        "Field_Case_Latch_Link_Pin_Print_Two",
        LATCH_LINK_PIN_LENGTH,
        LATCH_LINK_PIN_PRINT_OFFSET_Y,
        material,
    )


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


def duplicate_reference_part(source, name, material):
    reference = source.copy()
    reference.data = source.data.copy()
    reference.name = name
    reference.data.name = name + "_Mesh"
    bpy.context.collection.objects.link(reference)
    reference.location = (0.0, 0.0, 0.0)
    reference.rotation_euler = (0.0, 0.0, 0.0)
    assign_material(reference, material)
    return reference


def latch_open_link_pivot():
    """Reflect the closed moving pivot across line P-C after dead center."""
    vector_y = LATCH_LINK_PIVOT_WORLD_Y - LATCH_BASE_PIVOT_Y
    vector_z = LATCH_LINK_PIVOT_WORLD_Z - LATCH_PIVOT_Z
    projection = vector_y * _LATCH_PC_UNIT_Y + vector_z * _LATCH_PC_UNIT_Z
    return (
        LATCH_BASE_PIVOT_Y + 2.0 * projection * _LATCH_PC_UNIT_Y - vector_y,
        LATCH_PIVOT_Z + 2.0 * projection * _LATCH_PC_UNIT_Z - vector_z,
    )


def place_reference_handle(source, name, x, link_pivot, material):
    reference = duplicate_reference_part(source, name, material)
    local_vector_angle = math.atan2(
        LATCH_HANDLE_LINK_AXIS_LOCAL_Z - LATCH_HANDLE_BASE_AXIS_LOCAL_Z,
        LATCH_HANDLE_LINK_AXIS_LOCAL_Y,
    )
    world_vector_angle = math.atan2(
        link_pivot[1] - LATCH_PIVOT_Z,
        link_pivot[0] - LATCH_BASE_PIVOT_Y,
    )
    rotation_x = world_vector_angle - local_vector_angle
    reference.rotation_euler.x = rotation_x
    reference.location = (
        x,
        LATCH_BASE_PIVOT_Y + math.sin(rotation_x) * LATCH_HANDLE_BASE_AXIS_LOCAL_Z,
        LATCH_PIVOT_Z - math.cos(rotation_x) * LATCH_HANDLE_BASE_AXIS_LOCAL_Z,
    )
    return reference


def place_reference_bail(source, name, x, link_pivot, material):
    reference = duplicate_reference_part(source, name, material)
    rotation_x = math.atan2(
        LATCH_CATCH_WORLD_Z - link_pivot[1],
        LATCH_CATCH_WORLD_Y - link_pivot[0],
    )
    reference.rotation_euler.x = rotation_x
    reference.location = (
        x,
        link_pivot[0] + math.sin(rotation_x) * LATCH_BAIL_PIVOT_LOCAL_Z,
        link_pivot[1] - math.cos(rotation_x) * LATCH_BAIL_PIVOT_LOCAL_Z,
    )
    return reference


def create_latch_reference_mockups(parts, materials):
    handle_material, bail_material, pin_material = materials
    objects = []
    states = (
        (
            "CLOSED",
            LATCH_X_CENTERS[0],
            (LATCH_LINK_PIVOT_WORLD_Y, LATCH_LINK_PIVOT_WORLD_Z),
        ),
        ("OPEN", LATCH_X_CENTERS[1], latch_open_link_pivot()),
    )
    for state, x, link_pivot in states:
        objects.append(
            place_reference_handle(
                parts["latch_handle"],
                f"REFERENCE_ONLY_{state}_Latch_Handle",
                x,
                link_pivot,
                handle_material,
            )
        )
        objects.append(
            place_reference_bail(
                parts["latch_bail"],
                f"REFERENCE_ONLY_{state}_Latch_Bail",
                x,
                link_pivot,
                bail_material,
            )
        )
        base_pin = add_cylinder_x(
            f"REFERENCE_ONLY_{state}_Latch_Base_Pin",
            LATCH_PIVOT_DIAMETER / 2.0,
            LATCH_BASE_PIN_LENGTH,
            (x, LATCH_BASE_PIVOT_Y, LATCH_PIVOT_Z),
            vertices=36,
        )
        link_pin = add_cylinder_x(
            f"REFERENCE_ONLY_{state}_Latch_Link_Pin",
            LATCH_PIVOT_DIAMETER / 2.0,
            LATCH_LINK_PIN_LENGTH,
            (x, link_pivot[0], link_pivot[1]),
            vertices=36,
        )
        catch = add_cylinder_x(
            f"REFERENCE_ONLY_{state}_Lid_Catch",
            LATCH_CATCH_DIAMETER / 2.0,
            LATCH_CATCH_WIDTH,
            (x, LATCH_CATCH_WORLD_Y, LATCH_CATCH_WORLD_Z),
            vertices=44,
        )
        for item in (base_pin, link_pin, catch):
            assign_material(item, pin_material)
            objects.append(item)
    return objects


def create_reference_mockups(materials, parts):
    objects = []
    camera_material, battery_material, handle_material, bail_material, pin_material = (
        materials
    )
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
    objects.extend(
        create_latch_reference_mockups(
            parts,
            (handle_material, bail_material, pin_material),
        )
    )
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
        # Blender's Text Editor can synthesize ``__file__=/script.py``.  The
        # companion module was resolved from the actual source directory, so
        # it is a safe default and cannot silently redirect exports to ``/``.
        directory = MISSION1_SOURCE_DIRECTORY
    directory.mkdir(parents=True, exist_ok=True)
    return directory / name


def export_stl(path: Path, obj) -> Path:
    payload = evaluated_mesh_payload(obj, Vector((0.0, 0.0, 0.0)))
    write_binary_stl(path, obj.name, payload)
    print(f"FIELD_CASE_EXPORTED {path}")
    return path


THREE_MF_CORE_NAMESPACE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
THREE_MF_PRODUCTION_NAMESPACE = (
    "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
)
THREE_MF_BAMBU_NAMESPACE = "http://schemas.bambulab.com/package/2021"
THREE_MF_RELATIONSHIP_NAMESPACE = (
    "http://schemas.openxmlformats.org/package/2006/relationships"
)
THREE_MF_CONTENT_TYPES_NAMESPACE = (
    "http://schemas.openxmlformats.org/package/2006/content-types"
)
BAMBU_PRINTER_SETTINGS_ID = "Bambu Lab P1S 0.4 nozzle"
BAMBU_PROCESS_SETTINGS_ID = "0.20mm Standard @BBL X1C"
BAMBU_RIGID_FILAMENT_SETTINGS_ID = "Bambu PETG Basic @BBL X1C"
BAMBU_TPU_FILAMENT_SETTINGS_ID = "Generic TPU @BBL P1P"


def three_mf_tag(name: str) -> str:
    return f"{{{THREE_MF_CORE_NAMESPACE}}}{name}"


def three_mf_production_attribute(name: str) -> str:
    return f"{{{THREE_MF_PRODUCTION_NAMESPACE}}}{name}"


def format_3mf_number(value: float) -> str:
    if abs(value) < 0.0000005:
        value = 0.0
    return f"{value:.6f}".rstrip("0").rstrip(".")


def validate_triangle_payload(name, vertices, triangles) -> None:
    if not vertices or not triangles:
        raise ValueError(f"Cannot export empty triangle mesh: {name}")
    face_keys = set()
    edge_uses = {}
    for face_index, triangle in enumerate(triangles):
        if len(triangle) != 3 or len(set(triangle)) != 3:
            raise ValueError(f"{name} has a collapsed triangle at face {face_index}")
        if any(index < 0 or index >= len(vertices) for index in triangle):
            raise ValueError(
                f"{name} triangle {face_index} references a missing vertex"
            )
        try:
            point_0, point_1, point_2 = (vertices[index] for index in triangle)
        except IndexError as error:
            raise ValueError(
                f"{name} triangle {face_index} references a missing vertex"
            ) from error
        if not all(
            math.isfinite(value)
            for point in (point_0, point_1, point_2)
            for value in point
        ):
            raise ValueError(f"{name} has non-finite coordinates at face {face_index}")
        edge_01 = tuple(point_1[axis] - point_0[axis] for axis in range(3))
        edge_02 = tuple(point_2[axis] - point_0[axis] for axis in range(3))
        cross = (
            edge_01[1] * edge_02[2] - edge_01[2] * edge_02[1],
            edge_01[2] * edge_02[0] - edge_01[0] * edge_02[2],
            edge_01[0] * edge_02[1] - edge_01[1] * edge_02[0],
        )
        if sum(component * component for component in cross) <= 1e-18:
            raise ValueError(f"{name} has a zero-area triangle at face {face_index}")
        face_key = tuple(sorted(triangle))
        if face_key in face_keys:
            raise ValueError(f"{name} has a duplicate triangle at face {face_index}")
        face_keys.add(face_key)
        for start, end in (
            (triangle[0], triangle[1]),
            (triangle[1], triangle[2]),
            (triangle[2], triangle[0]),
        ):
            edge_uses.setdefault(tuple(sorted((start, end))), []).append((start, end))
    invalid_edges = [edge for edge, uses in edge_uses.items() if len(uses) != 2]
    if invalid_edges:
        raise ValueError(f"{name} has {len(invalid_edges)} non-manifold triangle edges")
    reversed_edges = [
        edge
        for edge, uses in edge_uses.items()
        if uses[0][0] == uses[1][0] or uses[0][1] == uses[1][1]
    ]
    if reversed_edges:
        raise ValueError(
            f"{name} has {len(reversed_edges)} inconsistently wound triangle edges"
        )


def evaluated_mesh_payload(obj, origin):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        world = evaluated.matrix_world
        vertices = []
        vertex_indices = {}
        positions = {}
        for vertex in bm.verts:
            position = world @ vertex.co - origin
            key = tuple(round(float(position[axis]), 6) for axis in range(3))
            if key not in positions:
                positions[key] = len(vertices)
                vertices.append(key)
            vertex_indices[vertex.index] = positions[key]
        triangles = [
            tuple(vertex_indices[vertex.index] for vertex in face.verts)
            for face in bm.faces
        ]
    finally:
        bm.free()
        evaluated.to_mesh_clear()
    validate_triangle_payload(obj.name, vertices, triangles)
    return vertices, triangles


def write_binary_stl(path: Path, name: str, payload) -> None:
    vertices, triangles = payload
    if len(triangles) >= 2**32:
        raise ValueError(f"{name} has too many triangles for binary STL")
    temporary_file = tempfile.NamedTemporaryFile(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    )
    temporary_path = Path(temporary_file.name)
    try:
        with temporary_file:
            header = f"Reco field-case part: {name}".encode("ascii")[:80]
            temporary_file.write(header.ljust(80, b"\0"))
            temporary_file.write(struct.pack("<I", len(triangles)))
            for triangle in triangles:
                point_0, point_1, point_2 = (vertices[index] for index in triangle)
                edge_01 = tuple(point_1[axis] - point_0[axis] for axis in range(3))
                edge_02 = tuple(point_2[axis] - point_0[axis] for axis in range(3))
                normal = (
                    edge_01[1] * edge_02[2] - edge_01[2] * edge_02[1],
                    edge_01[2] * edge_02[0] - edge_01[0] * edge_02[2],
                    edge_01[0] * edge_02[1] - edge_01[1] * edge_02[0],
                )
                length = math.sqrt(sum(component * component for component in normal))
                unit_normal = tuple(component / length for component in normal)
                temporary_file.write(
                    struct.pack(
                        "<12fH",
                        *unit_normal,
                        *point_0,
                        *point_1,
                        *point_2,
                        0,
                    )
                )
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def triangle_components(triangles):
    vertex_faces = {}
    for face_index, triangle in enumerate(triangles):
        for vertex_index in triangle:
            vertex_faces.setdefault(vertex_index, []).append(face_index)
    remaining = set(range(len(triangles)))
    components = []
    while remaining:
        component = set()
        stack = [remaining.pop()]
        while stack:
            face_index = stack.pop()
            component.add(face_index)
            for vertex_index in triangles[face_index]:
                for neighbor in vertex_faces[vertex_index]:
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        stack.append(neighbor)
        components.append(component)
    return components


def point_in_triangle_xy(point, triangle, epsilon=1e-7) -> bool:
    signs = []
    for index in range(3):
        start = triangle[index]
        end = triangle[(index + 1) % 3]
        signs.append(
            (end[0] - start[0]) * (point[1] - start[1])
            - (end[1] - start[1]) * (point[0] - start[0])
        )
    return not (
        any(value < -epsilon for value in signs)
        and any(value > epsilon for value in signs)
    )


def validate_lid_bonding_payloads(lid_payload, inlay_payloads) -> int:
    lid_vertices, lid_triangles = lid_payload
    inlay_tops = [
        max(vertex[2] for vertex in vertices) for vertices, _triangles in inlay_payloads
    ]
    if not all(math.isclose(top, inlay_tops[0], abs_tol=1e-6) for top in inlay_tops):
        raise ValueError(f"Lid inlays use different bonding planes: {inlay_tops}")
    bonding_z = inlay_tops[0]
    lid_surfaces = []
    for triangle in lid_triangles:
        points = [lid_vertices[index] for index in triangle]
        if all(math.isclose(point[2], bonding_z, abs_tol=1e-6) for point in points):
            lid_surfaces.append(
                (
                    min(point[0] for point in points),
                    max(point[0] for point in points),
                    min(point[1] for point in points),
                    max(point[1] for point in points),
                    points,
                )
            )
    if not lid_surfaces:
        raise ValueError("Lid has no horizontal surface on the inlay bonding plane")

    island_count = 0
    for vertices, triangles in inlay_payloads:
        components = triangle_components(triangles)
        top_faces = {
            face_index
            for face_index, triangle in enumerate(triangles)
            if all(
                math.isclose(vertices[index][2], bonding_z, abs_tol=1e-6)
                for index in triangle
            )
        }
        if any(not component.intersection(top_faces) for component in components):
            raise ValueError("A lettering island has no top bonding surface")
        island_count += len(components)
        for face_index in top_faces:
            points = [vertices[index] for index in triangles[face_index]]
            centroid = (
                sum(point[0] for point in points) / 3.0,
                sum(point[1] for point in points) / 3.0,
            )
            if not any(
                minimum_x - 1e-7 <= centroid[0] <= maximum_x + 1e-7
                and minimum_y - 1e-7 <= centroid[1] <= maximum_y + 1e-7
                and point_in_triangle_xy(centroid, lid_triangle)
                for minimum_x, maximum_x, minimum_y, maximum_y, lid_triangle in lid_surfaces
            ):
                raise ValueError(
                    "A lettering top face does not contact the lid bonding surface"
                )
    return island_count


def production_uuid(file_index: int, part_index: int, suffix: str) -> str:
    return f"{file_index:04x}{part_index:04x}-{suffix}"


def add_3mf_mesh_object(resources, object_id, name, file_index, part_index, payload):
    object_node = ET.SubElement(
        resources,
        three_mf_tag("object"),
        {
            "id": str(object_id),
            "name": name,
            "type": "model",
            three_mf_production_attribute("UUID"): production_uuid(
                file_index,
                part_index,
                "81cb-4c03-9d28-80fed5dfa1dc",
            ),
        },
    )
    mesh_node = ET.SubElement(object_node, three_mf_tag("mesh"))
    vertices_node = ET.SubElement(mesh_node, three_mf_tag("vertices"))
    for x, y, z in payload[0]:
        ET.SubElement(
            vertices_node,
            three_mf_tag("vertex"),
            {
                "x": format_3mf_number(x),
                "y": format_3mf_number(y),
                "z": format_3mf_number(z),
            },
        )
    triangles_node = ET.SubElement(mesh_node, three_mf_tag("triangles"))
    for vertex_1, vertex_2, vertex_3 in payload[1]:
        ET.SubElement(
            triangles_node,
            three_mf_tag("triangle"),
            {
                "v1": str(vertex_1),
                "v2": str(vertex_2),
                "v3": str(vertex_3),
            },
        )


def three_mf_translation(x: float = 0.0, y: float = 0.0, z: float = 0.0) -> str:
    return " ".join(
        format_3mf_number(value)
        for value in (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, x, y, z)
    )


def project_layout(groups, plate_size=256.0, plate_gap_ratio=0.2):
    placements = []
    plate_count = max(group["plate"] for group in groups) + 1
    plate_columns = math.ceil(math.sqrt(plate_count))
    plate_stride = plate_size * (1.0 + plate_gap_ratio)
    for group in groups:
        width, depth = group["dimensions"]
        plate_index = group["plate"]
        plate_origin_x = (plate_index % plate_columns) * plate_stride
        plate_origin_y = -(plate_index // plate_columns) * plate_stride
        copy_offsets = group.get("copy_offsets")
        for copy_index in range(group["copies"]):
            if copy_offsets:
                local_x, local_y = copy_offsets[copy_index]
            else:
                local_x = (plate_size - width) / 2.0
                local_y = (plate_size - depth) / 2.0
            placements.append(
                (
                    group,
                    copy_index,
                    plate_origin_x + local_x,
                    plate_origin_y + local_y,
                )
            )
    return placements


def write_3mf_member(archive, name: str, data: bytes) -> None:
    entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    entry.compress_type = zipfile.ZIP_DEFLATED
    entry.external_attr = 0o100644 << 16
    archive.writestr(entry, data)


def new_3mf_model() -> ET.Element:
    return ET.Element(
        three_mf_tag("model"),
        {
            "unit": "millimeter",
            "{http://www.w3.org/XML/1998/namespace}lang": "en-US",
            "requiredextensions": "p",
            "xmlns:BambuStudio": THREE_MF_BAMBU_NAMESPACE,
        },
    )


def add_3mf_metadata(model, name: str, value: str) -> None:
    node = ET.SubElement(model, three_mf_tag("metadata"), {"name": name})
    node.text = value


def xml_bytes(root) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def add_config_metadata(parent, key: str, value: str) -> None:
    ET.SubElement(parent, "metadata", {"key": key, "value": value})


def add_model_settings_object(config, group) -> None:
    object_node = ET.SubElement(config, "object", {"id": str(group["object_id"])})
    add_config_metadata(object_node, "name", group["name"])
    add_config_metadata(object_node, "extruder", str(group["extruders"][0]))
    ET.SubElement(
        object_node,
        "metadata",
        {"face_count": str(sum(group["face_counts"]))},
    )
    for part_index, (key, mesh_id, extruder, face_count) in enumerate(
        zip(
            group["keys"],
            group["mesh_ids"],
            group["extruders"],
            group["face_counts"],
        )
    ):
        part_node = ET.SubElement(
            object_node,
            "part",
            {"id": str(mesh_id), "subtype": "normal_part"},
        )
        add_config_metadata(part_node, "name", group["part_names"][part_index])
        add_config_metadata(
            part_node,
            "matrix",
            "1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1",
        )
        add_config_metadata(part_node, "source_file", group["source_files"][part_index])
        add_config_metadata(part_node, "source_object_id", "0")
        add_config_metadata(part_node, "source_volume_id", str(part_index))
        add_config_metadata(part_node, "source_offset_x", "0")
        add_config_metadata(part_node, "source_offset_y", "0")
        add_config_metadata(part_node, "source_offset_z", "0")
        add_config_metadata(part_node, "extruder", str(extruder))
        ET.SubElement(
            part_node,
            "mesh_stat",
            {
                "face_count": str(face_count),
                "edges_fixed": "0",
                "degenerate_facets": "0",
                "facets_removed": "0",
                "facets_reversed": "0",
                "backwards_edges": "0",
            },
        )


def project_settings_bytes() -> bytes:
    settings = {
        "bed_exclude_area": ["0x0", "18x0", "18x28", "0x28"],
        "default_filament_colour": ["", "", "", ""],
        "different_settings_to_system": ["", "", "", "", "", ""],
        "enable_support": "0",
        "extruder_clearance_dist_to_rod": "33",
        "extruder_clearance_height_to_lid": "90",
        "extruder_clearance_height_to_rod": "34",
        "extruder_clearance_max_radius": "68",
        "filament_colour": ["#161616", "#009EEA", "#FF470A", "#F23809"],
        "filament_ids": ["", "", "", ""],
        "filament_is_support": ["0", "0", "0", "0"],
        "filament_settings_id": [
            BAMBU_RIGID_FILAMENT_SETTINGS_ID,
            BAMBU_RIGID_FILAMENT_SETTINGS_ID,
            BAMBU_RIGID_FILAMENT_SETTINGS_ID,
            BAMBU_TPU_FILAMENT_SETTINGS_ID,
        ],
        "filament_type": ["PETG", "PETG", "PETG", "TPU"],
        "flush_multiplier": ["1"],
        "flush_volumes_matrix": [
            "0",
            "280",
            "280",
            "280",
            "280",
            "0",
            "280",
            "280",
            "280",
            "280",
            "0",
            "280",
            "280",
            "280",
            "280",
            "0",
        ],
        "inherits_group": ["", "", "", "", "", ""],
        "nozzle_diameter": ["0.4"],
        "print_compatible_printers": [BAMBU_PRINTER_SETTINGS_ID],
        "print_settings_id": BAMBU_PROCESS_SETTINGS_ID,
        "printable_area": ["0x0", "256x0", "256x256", "0x256"],
        "printable_height": "250",
        "printer_model": "Bambu Lab P1S",
        "printer_settings_id": BAMBU_PRINTER_SETTINGS_ID,
        "printer_technology": "FFF",
        "upward_compatible_machine": [],
    }
    return (json.dumps(settings, indent=4, sort_keys=True) + "\n").encode("utf-8")


def export_3mf_project(path: Path, parts) -> Path:
    ET.register_namespace("", THREE_MF_CORE_NAMESPACE)
    ET.register_namespace("p", THREE_MF_PRODUCTION_NAMESPACE)
    model = new_3mf_model()
    for name, value in (
        ("Application", "BambuStudio-02.05.01.52"),
        ("BambuStudio:3mfVersion", "1"),
        ("Title", "Dual MISSION 1 Field Case AMS Project"),
        (
            "Description",
            "Printable field-case kit with a compound three-color lid object.",
        ),
        ("License", "Repository license applies"),
    ):
        add_3mf_metadata(model, name, value)

    resources = ET.SubElement(model, three_mf_tag("resources"))

    def dimensions_xy(key):
        dimensions = object_world_dimensions(parts[key])
        return float(dimensions.x), float(dimensions.y)

    groups = [
        {
            "name": "Base",
            "keys": ("base",),
            "source_files": (BASE_STL_NAME,),
            "extruders": (1,),
            "dimensions": dimensions_xy("base"),
            "copies": 1,
            "plate": 0,
        },
        {
            "name": "AMS Lid - Shell, Title, Subtitle",
            "keys": ("lid", "title_inlay", "subtitle_inlay"),
            "source_files": (
                LID_STL_NAME,
                TITLE_INLAY_STL_NAME,
                SUBTITLE_INLAY_STL_NAME,
            ),
            "extruders": (1, 2, 3),
            "dimensions": dimensions_xy("lid"),
            "copies": 1,
            "plate": 1,
        },
    ]
    remaining_groups = (
        ("lower_tray", LOWER_TRAY_STL_NAME, 4, 1, 2, None),
        ("lid_retainer", LID_RETAINER_STL_NAME, 4, 1, 3, None),
        ("gasket", GASKET_STL_NAME, 4, 1, 4, None),
        (
            "latch_handle",
            LATCH_HANDLE_STL_NAME,
            1,
            2,
            5,
            ((20.0, 30.0), (55.0, 30.0)),
        ),
        (
            "latch_bail",
            LATCH_BAIL_STL_NAME,
            1,
            2,
            5,
            ((90.0, 30.0), (145.0, 30.0)),
        ),
        (
            "latch_base_pin",
            LATCH_BASE_PIN_STL_NAME,
            1,
            2,
            5,
            ((20.0, 90.0), (60.0, 90.0)),
        ),
        (
            "latch_link_pin",
            LATCH_LINK_PIN_STL_NAME,
            1,
            2,
            5,
            ((105.0, 90.0), (165.0, 90.0)),
        ),
        ("hinge_pin", HINGE_PIN_STL_NAME, 1, 1, 5, ((20.0, 120.0),)),
    )
    for (
        key,
        source_file,
        extruder,
        copies,
        plate_index,
        copy_offsets,
    ) in remaining_groups:
        groups.append(
            {
                "name": parts[key].name,
                "keys": (key,),
                "source_files": (source_file,),
                "extruders": (extruder,),
                "dimensions": dimensions_xy(key),
                "copies": copies,
                "plate": plate_index,
                "copy_offsets": copy_offsets,
            }
        )

    object_models = {}
    next_object_id = 1
    for file_index, group in enumerate(groups, start=1):
        submodel = new_3mf_model()
        add_3mf_metadata(submodel, "BambuStudio:3mfVersion", "1")
        subresources = ET.SubElement(submodel, three_mf_tag("resources"))
        origin = object_world_bounds(parts[group["keys"][0]])[0]
        group["mesh_ids"] = []
        group["face_counts"] = []
        group["part_names"] = []
        for part_index, key in enumerate(group["keys"]):
            payload = evaluated_mesh_payload(parts[key], origin)
            mesh_id = next_object_id
            next_object_id += 1
            add_3mf_mesh_object(
                subresources,
                mesh_id,
                parts[key].name,
                file_index,
                part_index,
                payload,
            )
            group["mesh_ids"].append(mesh_id)
            group["face_counts"].append(len(payload[1]))
            group["part_names"].append(parts[key].name)

        ET.SubElement(submodel, three_mf_tag("build"))
        object_path = f"/3D/Objects/object_{file_index}.model"
        object_models[object_path.lstrip("/")] = submodel
        wrapper_id = next_object_id
        next_object_id += 1
        group["object_id"] = wrapper_id
        wrapper = ET.SubElement(
            resources,
            three_mf_tag("object"),
            {
                "id": str(wrapper_id),
                "name": group["name"],
                "type": "model",
                three_mf_production_attribute("UUID"): (
                    f"{file_index:08x}-61cb-4c03-9d28-80fed5dfa1dc"
                ),
            },
        )
        components = ET.SubElement(wrapper, three_mf_tag("components"))
        for part_index, mesh_id in enumerate(group["mesh_ids"]):
            ET.SubElement(
                components,
                three_mf_tag("component"),
                {
                    "objectid": str(mesh_id),
                    "transform": three_mf_translation(),
                    three_mf_production_attribute("path"): object_path,
                    three_mf_production_attribute("UUID"): production_uuid(
                        file_index,
                        part_index,
                        "b206-40ff-9872-83e8017abed1",
                    ),
                },
            )

    placements = project_layout(groups)
    build = ET.SubElement(model, three_mf_tag("build"))
    build.set(
        three_mf_production_attribute("UUID"),
        "2c7c17d8-22b5-4d84-8835-1976022ea369",
    )
    for build_index, (group, copy_index, x, y) in enumerate(placements, start=1):
        ET.SubElement(
            build,
            three_mf_tag("item"),
            {
                "objectid": str(group["object_id"]),
                "transform": three_mf_translation(x, y),
                "printable": "1",
                three_mf_production_attribute("UUID"): (
                    f"{build_index:08x}-b1ec-4553-aec9-835e5b724bb4"
                ),
            },
        )

    content_types = ET.Element(
        "Types",
        {"xmlns": THREE_MF_CONTENT_TYPES_NAMESPACE},
    )
    ET.SubElement(
        content_types,
        "Default",
        {
            "Extension": "rels",
            "ContentType": ("application/vnd.openxmlformats-package.relationships+xml"),
        },
    )
    ET.SubElement(
        content_types,
        "Default",
        {
            "Extension": "model",
            "ContentType": ("application/vnd.ms-package.3dmanufacturing-3dmodel+xml"),
        },
    )
    for extension, content_type in (("png", "image/png"), ("gcode", "text/x.gcode")):
        ET.SubElement(
            content_types,
            "Default",
            {"Extension": extension, "ContentType": content_type},
        )
    relationships = ET.Element(
        "Relationships",
        {"xmlns": THREE_MF_RELATIONSHIP_NAMESPACE},
    )
    ET.SubElement(
        relationships,
        "Relationship",
        {
            "Target": "/3D/3dmodel.model",
            "Id": "rel-1",
            "Type": ("http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"),
        },
    )
    model_relationships = ET.Element(
        "Relationships",
        {"xmlns": THREE_MF_RELATIONSHIP_NAMESPACE},
    )
    for file_index, object_path in enumerate(object_models, start=1):
        ET.SubElement(
            model_relationships,
            "Relationship",
            {
                "Target": f"/{object_path}",
                "Id": f"rel-{file_index}",
                "Type": (
                    "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
                ),
            },
        )

    model_settings = ET.Element("config")
    for group in groups:
        add_model_settings_object(model_settings, group)
    instance_counts = {}
    plate_names = (
        "Shell Base",
        "AMS Lid",
        "TPU Lower Tray",
        "TPU Lid Pad",
        "TPU Gasket",
        "Printed Hardware",
    )
    identify_id = 1
    for plate_index, plate_name in enumerate(plate_names):
        plate = ET.SubElement(model_settings, "plate")
        add_config_metadata(plate, "plater_id", str(plate_index + 1))
        add_config_metadata(plate, "plater_name", plate_name)
        add_config_metadata(plate, "locked", "false")
        add_config_metadata(plate, "filament_map_mode", "Auto For Flush")
        for group, _copy_index, _x, _y in placements:
            if group["plate"] != plate_index:
                continue
            instance_id = instance_counts.get(group["object_id"], 0)
            instance_counts[group["object_id"]] = instance_id + 1
            instance = ET.SubElement(plate, "model_instance")
            add_config_metadata(instance, "object_id", str(group["object_id"]))
            add_config_metadata(instance, "instance_id", str(instance_id))
            add_config_metadata(instance, "identify_id", str(identify_id))
            identify_id += 1
    ET.SubElement(model_settings, "assemble")

    temporary_file = tempfile.NamedTemporaryFile(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    )
    temporary_path = Path(temporary_file.name)
    temporary_file.close()
    try:
        with zipfile.ZipFile(temporary_path, "w") as archive:
            write_3mf_member(archive, "[Content_Types].xml", xml_bytes(content_types))
            write_3mf_member(archive, "_rels/.rels", xml_bytes(relationships))
            write_3mf_member(archive, "3D/3dmodel.model", xml_bytes(model))
            write_3mf_member(
                archive,
                "3D/_rels/3dmodel.model.rels",
                xml_bytes(model_relationships),
            )
            for object_path, object_model in object_models.items():
                write_3mf_member(archive, object_path, xml_bytes(object_model))
            write_3mf_member(
                archive,
                "Metadata/model_settings.config",
                xml_bytes(model_settings),
            )
            write_3mf_member(
                archive,
                "Metadata/project_settings.config",
                project_settings_bytes(),
            )
        validate_3mf_project(temporary_path)
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    print(
        "FIELD_CASE_EXPORTED_3MF "
        f"{path} mesh_parts={len(PRINTABLE_STL_NAMES)} "
        f"objects={len(groups)} build_items={len(placements)}"
    )
    return path


def config_metadata(node) -> dict:
    values = {}
    for metadata in node.findall("metadata"):
        key = metadata.get("key")
        if key in values:
            raise ValueError(f"Duplicate 3MF config metadata key: {key}")
        values[key] = metadata.get("value")
    return values


def mesh_payload_from_xml(mesh_object):
    mesh = mesh_object.find(three_mf_tag("mesh"))
    if mesh is None:
        raise ValueError(f"3MF object {mesh_object.get('id')} has no mesh")
    vertices = [
        tuple(float(node.get(axis)) for axis in ("x", "y", "z"))
        for node in mesh.findall(f"{three_mf_tag('vertices')}/{three_mf_tag('vertex')}")
    ]
    triangles = [
        tuple(int(node.get(key)) for key in ("v1", "v2", "v3"))
        for node in mesh.findall(
            f"{three_mf_tag('triangles')}/{three_mf_tag('triangle')}"
        )
    ]
    validate_triangle_payload(
        f"3MF mesh object {mesh_object.get('id')}",
        vertices,
        triangles,
    )
    return vertices, triangles


def parse_3mf_transform(raw_value):
    values = tuple(float(value) for value in raw_value.split())
    if len(values) != 12:
        raise ValueError(f"Invalid 3MF transform: {raw_value}")
    identity = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    if any(
        not math.isclose(values[index], identity[index], abs_tol=1e-6)
        for index in range(9)
    ):
        raise ValueError(
            f"3MF project uses an unexpected rotation or scale: {raw_value}"
        )
    return values[9], values[10], values[11]


def validate_relationships(root, expected_targets) -> None:
    relationship_tag = f"{{{THREE_MF_RELATIONSHIP_NAMESPACE}}}Relationship"
    relationships = root.findall(relationship_tag)
    targets = [node.get("Target") for node in relationships]
    identifiers = [node.get("Id") for node in relationships]
    relationship_type = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
    if set(targets) != set(expected_targets) or len(targets) != len(expected_targets):
        raise ValueError(f"3MF package has unexpected relationship targets: {targets}")
    if len(identifiers) != len(set(identifiers)) or any(
        not identifier for identifier in identifiers
    ):
        raise ValueError("3MF package relationship IDs must be unique and nonempty")
    if any(node.get("Type") != relationship_type for node in relationships):
        raise ValueError("3MF package has an unexpected relationship type")


def validate_3mf_project(path: Path) -> None:
    object_model_paths = [f"3D/Objects/object_{index}.model" for index in range(1, 11)]
    required_members = {
        "[Content_Types].xml",
        "_rels/.rels",
        "3D/3dmodel.model",
        "3D/_rels/3dmodel.model.rels",
        "Metadata/model_settings.config",
        "Metadata/project_settings.config",
        *object_model_paths,
    }
    with zipfile.ZipFile(path, "r") as archive:
        members = archive.namelist()
        if len(members) != len(set(members)):
            raise ValueError("3MF project contains duplicate ZIP members")
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ValueError(f"3MF project has corrupt ZIP member: {bad_member}")
        missing = required_members.difference(members)
        if missing:
            raise ValueError(
                f"3MF project is missing package members: {sorted(missing)}"
            )
        content_types_raw = archive.read("[Content_Types].xml").decode("utf-8")
        root_relationships_raw = archive.read("_rels/.rels").decode("utf-8")
        model_relationships_raw = archive.read("3D/_rels/3dmodel.model.rels").decode(
            "utf-8"
        )
        content_types = ET.fromstring(content_types_raw)
        root_relationships = ET.fromstring(root_relationships_raw)
        model = ET.fromstring(archive.read("3D/3dmodel.model"))
        object_models = [
            ET.fromstring(archive.read(object_path))
            for object_path in object_model_paths
        ]
        model_relationships = ET.fromstring(model_relationships_raw)
        model_settings = ET.fromstring(archive.read("Metadata/model_settings.config"))
        project_settings = json.loads(
            archive.read("Metadata/project_settings.config").decode("utf-8")
        )

    if (
        ":Relationship" in root_relationships_raw
        or ":Relationship" in model_relationships_raw
    ):
        raise ValueError("Bambu 3MF relationships must use unprefixed XML elements")
    if (
        "<Relationship " not in root_relationships_raw
        or "<Relationship " not in model_relationships_raw
    ):
        raise ValueError("Bambu 3MF relationship elements are missing")
    if ":Default" in content_types_raw or "<Default " not in content_types_raw:
        raise ValueError("3MF content types must use unprefixed XML elements")

    content_namespace = f"{{{THREE_MF_CONTENT_TYPES_NAMESPACE}}}"
    if content_types.tag != content_namespace + "Types":
        raise ValueError("3MF project has an invalid content-types root")
    content_defaults = {
        (node.get("Extension"), node.get("ContentType"))
        for node in content_types.findall(content_namespace + "Default")
    }
    expected_content_defaults = {
        (
            "rels",
            "application/vnd.openxmlformats-package.relationships+xml",
        ),
        (
            "model",
            "application/vnd.ms-package.3dmanufacturing-3dmodel+xml",
        ),
    }
    if not expected_content_defaults.issubset(content_defaults):
        raise ValueError("3MF project is missing required content types")

    relationship_root_tag = f"{{{THREE_MF_RELATIONSHIP_NAMESPACE}}}Relationships"
    if root_relationships.tag != relationship_root_tag:
        raise ValueError("3MF project has an invalid root relationships document")
    if model_relationships.tag != relationship_root_tag:
        raise ValueError("3MF project has an invalid model relationships document")
    validate_relationships(root_relationships, ["/3D/3dmodel.model"])
    expected_relationship_targets = [f"/{path}" for path in object_model_paths]
    validate_relationships(model_relationships, expected_relationship_targets)

    expected_groups = (
        ("2", "Base", ("1",), object_model_paths[0]),
        (
            "6",
            "AMS Lid - Shell, Title, Subtitle",
            ("3", "4", "5"),
            object_model_paths[1],
        ),
        ("8", "Field_Case_Recessed_TPU_Lower_Tray", ("7",), object_model_paths[2]),
        ("10", "Field_Case_Recessed_TPU_Lid_Pad", ("9",), object_model_paths[3]),
        ("12", "Field_Case_TPU_Gasket", ("11",), object_model_paths[4]),
        (
            "14",
            "Field_Case_Over_Center_Latch_Handle_Print_Two",
            ("13",),
            object_model_paths[5],
        ),
        (
            "16",
            "Field_Case_Over_Center_Latch_Bail_Print_Two",
            ("15",),
            object_model_paths[6],
        ),
        (
            "18",
            "Field_Case_Latch_Base_Pin_Print_Two",
            ("17",),
            object_model_paths[7],
        ),
        (
            "20",
            "Field_Case_Latch_Link_Pin_Print_Two",
            ("19",),
            object_model_paths[8],
        ),
        ("22", "Field_Case_Hinge_Pin", ("21",), object_model_paths[9]),
    )
    component_objects = model.findall(
        f"./{three_mf_tag('resources')}/{three_mf_tag('object')}"
    )
    components_by_id = {node.get("id"): node for node in component_objects}
    if set(components_by_id) != {group[0] for group in expected_groups}:
        raise ValueError("3MF project has unexpected logical object IDs")
    wrapper_uuids = [
        node.get(three_mf_production_attribute("UUID")) for node in component_objects
    ]
    if any(not value for value in wrapper_uuids) or len(wrapper_uuids) != len(
        set(wrapper_uuids)
    ):
        raise ValueError("3MF logical object UUIDs must be unique and nonempty")
    component_paths = []
    all_component_uuids = set()
    for object_id, expected_name, expected_mesh_ids, object_path in expected_groups:
        node = components_by_id[object_id]
        if node.get("name") != expected_name:
            raise ValueError(f"3MF object {object_id} has an unexpected name")
        components = node.findall(
            f"{three_mf_tag('components')}/{three_mf_tag('component')}"
        )
        mesh_ids = tuple(component.get("objectid") for component in components)
        if mesh_ids != expected_mesh_ids:
            raise ValueError(f"3MF object {object_id} references incorrect mesh parts")
        for component in components:
            if (
                component.get(three_mf_production_attribute("path"))
                != f"/{object_path}"
            ):
                raise ValueError(f"3MF object {object_id} references an incorrect path")
            parse_3mf_transform(component.get("transform"))
            component_uuid = component.get(three_mf_production_attribute("UUID"))
            if not component_uuid or component_uuid in all_component_uuids:
                raise ValueError("3MF component UUIDs must be unique and nonempty")
            all_component_uuids.add(component_uuid)
            component_paths.append(f"/{object_path}")
    if set(component_paths) != set(expected_relationship_targets):
        raise ValueError("3MF component paths and relationships do not correspond")

    mesh_payloads = {}
    mesh_objects = []
    mesh_uuids = set()
    for object_model, expected_group in zip(object_models, expected_groups):
        objects = object_model.findall(
            f"./{three_mf_tag('resources')}/{three_mf_tag('object')}"
        )
        if tuple(node.get("id") for node in objects) != expected_group[2]:
            raise ValueError(
                f"3MF object model for {expected_group[1]} has incorrect mesh IDs"
            )
        for mesh_object in objects:
            mesh_uuid = mesh_object.get(three_mf_production_attribute("UUID"))
            if not mesh_uuid or mesh_uuid in mesh_uuids:
                raise ValueError("3MF mesh object UUIDs must be unique and nonempty")
            mesh_uuids.add(mesh_uuid)
            mesh_objects.append(mesh_object)
            mesh_payloads[mesh_object.get("id")] = mesh_payload_from_xml(mesh_object)
    if len(mesh_objects) != len(PRINTABLE_STL_NAMES):
        raise ValueError(
            f"3MF project has {len(mesh_objects)} mesh parts, "
            f"expected {len(PRINTABLE_STL_NAMES)}"
        )
    lid_islands = validate_lid_bonding_payloads(
        mesh_payloads["3"],
        (mesh_payloads["4"], mesh_payloads["5"]),
    )

    expected_parts = {
        "1": (BASE_STL_NAME, "1"),
        "3": (LID_STL_NAME, "1"),
        "4": (TITLE_INLAY_STL_NAME, "2"),
        "5": (SUBTITLE_INLAY_STL_NAME, "3"),
        "7": (LOWER_TRAY_STL_NAME, "4"),
        "9": (LID_RETAINER_STL_NAME, "4"),
        "11": (GASKET_STL_NAME, "4"),
        "13": (LATCH_HANDLE_STL_NAME, "1"),
        "15": (LATCH_BAIL_STL_NAME, "1"),
        "17": (LATCH_BASE_PIN_STL_NAME, "1"),
        "19": (LATCH_LINK_PIN_STL_NAME, "1"),
        "21": (HINGE_PIN_STL_NAME, "1"),
    }
    settings_objects = model_settings.findall("object")
    settings_parts = model_settings.findall("object/part")
    if {node.get("id") for node in settings_objects} != set(components_by_id):
        raise ValueError("3MF model settings describe incorrect logical objects")
    expected_object_extruders = {
        "2": "1",
        "6": "1",
        "8": "4",
        "10": "4",
        "12": "4",
        "14": "1",
        "16": "1",
        "18": "1",
        "20": "1",
        "22": "1",
    }
    expected_group_names = {group[0]: group[1] for group in expected_groups}
    for settings_object in settings_objects:
        object_id = settings_object.get("id")
        metadata = config_metadata(settings_object)
        if metadata.get("name") != expected_group_names[object_id]:
            raise ValueError(f"3MF settings object {object_id} has an incorrect name")
        if metadata.get("extruder") != expected_object_extruders[object_id]:
            raise ValueError(
                f"3MF settings object {object_id} has an incorrect extruder"
            )
    if {node.get("id") for node in settings_parts} != set(expected_parts):
        raise ValueError("3MF model settings describe incorrect mesh parts")
    for part in settings_parts:
        source_file, extruder = expected_parts[part.get("id")]
        metadata = config_metadata(part)
        if metadata.get("source_file") != source_file:
            raise ValueError(f"3MF part {part.get('id')} has an incorrect source file")
        if metadata.get("extruder") != extruder:
            raise ValueError(f"3MF part {part.get('id')} has an incorrect extruder")

    plate_names = (
        "Shell Base",
        "AMS Lid",
        "TPU Lower Tray",
        "TPU Lid Pad",
        "TPU Gasket",
        "Printed Hardware",
    )
    expected_plate_instances = (
        (("2", "0"),),
        (("6", "0"),),
        (("8", "0"),),
        (("10", "0"),),
        (("12", "0"),),
        (
            ("14", "0"),
            ("14", "1"),
            ("16", "0"),
            ("16", "1"),
            ("18", "0"),
            ("18", "1"),
            ("20", "0"),
            ("20", "1"),
            ("22", "0"),
        ),
    )
    settings_plates = model_settings.findall("plate")
    if len(settings_plates) != len(plate_names):
        raise ValueError("3MF project has an unexpected plate count")
    identify_ids = []
    for plate_index, plate in enumerate(settings_plates):
        metadata = config_metadata(plate)
        if metadata.get("plater_id") != str(plate_index + 1):
            raise ValueError("3MF plate IDs are not sequential")
        if metadata.get("plater_name") != plate_names[plate_index]:
            raise ValueError(f"3MF plate {plate_index + 1} has an incorrect name")
        actual_instances = []
        for instance in plate.findall("model_instance"):
            values = config_metadata(instance)
            actual_instances.append(
                (values.get("object_id"), values.get("instance_id"))
            )
            identify_ids.append(values.get("identify_id"))
        if tuple(actual_instances) != expected_plate_instances[plate_index]:
            raise ValueError(f"3MF plate {plate_index + 1} has incorrect instances")
    if identify_ids != [str(index) for index in range(1, 15)]:
        raise ValueError("3MF instance identify IDs are not unique and sequential")

    build_items = model.findall(f"./{three_mf_tag('build')}/{three_mf_tag('item')}")
    expected_build_ids = tuple(
        object_id
        for plate in expected_plate_instances
        for object_id, _instance_id in plate
    )
    if tuple(item.get("objectid") for item in build_items) != expected_build_ids:
        raise ValueError("3MF build items do not match the plate instances")
    build_uuids = [
        item.get(three_mf_production_attribute("UUID")) for item in build_items
    ]
    if any(not value for value in build_uuids) or len(build_uuids) != len(
        set(build_uuids)
    ):
        raise ValueError("3MF build item UUIDs must be unique and nonempty")

    group_bounds = {}
    for object_id, _name, mesh_ids, _path in expected_groups:
        points = [point for mesh_id in mesh_ids for point in mesh_payloads[mesh_id][0]]
        group_bounds[object_id] = (
            min(point[0] for point in points),
            max(point[0] for point in points),
            min(point[1] for point in points),
            max(point[1] for point in points),
            min(point[2] for point in points),
            max(point[2] for point in points),
        )
    plate_boxes = [[] for _name in plate_names]
    plate_stride = 256.0 * 1.2
    item_index = 0
    for plate_index, plate_instances in enumerate(expected_plate_instances):
        origin_x = (plate_index % 3) * plate_stride
        origin_y = -(plate_index // 3) * plate_stride
        for _instance in plate_instances:
            item = build_items[item_index]
            translation = parse_3mf_transform(item.get("transform"))
            bounds = group_bounds[item.get("objectid")]
            box = (
                bounds[0] + translation[0],
                bounds[1] + translation[0],
                bounds[2] + translation[1],
                bounds[3] + translation[1],
                bounds[4] + translation[2],
                bounds[5] + translation[2],
            )
            if not (
                origin_x - 1e-6 <= box[0]
                and box[1] <= origin_x + 256.0 + 1e-6
                and origin_y - 1e-6 <= box[2]
                and box[3] <= origin_y + 256.0 + 1e-6
                and -1e-6 <= box[4]
                and box[5] <= 250.0 + 1e-6
            ):
                raise ValueError(
                    f"3MF build item {item_index + 1} is outside its plate"
                )
            local_box = (
                box[0] - origin_x,
                box[1] - origin_x,
                box[2] - origin_y,
                box[3] - origin_y,
            )
            if local_box[0] < 18.0 and local_box[2] < 28.0:
                raise ValueError(
                    f"3MF build item {item_index + 1} overlaps the excluded bed area"
                )
            plate_boxes[plate_index].append(box)
            item_index += 1
    for plate_index, boxes in enumerate(plate_boxes):
        for first_index, first in enumerate(boxes):
            for second in boxes[first_index + 1 :]:
                if (
                    min(first[1], second[1]) - max(first[0], second[0]) > 1e-6
                    and min(first[3], second[3]) - max(first[2], second[2]) > 1e-6
                ):
                    raise ValueError(f"3MF plate {plate_index + 1} has colliding parts")

    expected_project_settings = {
        "filament_colour": ["#161616", "#009EEA", "#FF470A", "#F23809"],
        "filament_type": ["PETG", "PETG", "PETG", "TPU"],
        "filament_settings_id": [
            BAMBU_RIGID_FILAMENT_SETTINGS_ID,
            BAMBU_RIGID_FILAMENT_SETTINGS_ID,
            BAMBU_RIGID_FILAMENT_SETTINGS_ID,
            BAMBU_TPU_FILAMENT_SETTINGS_ID,
        ],
        "printer_settings_id": BAMBU_PRINTER_SETTINGS_ID,
        "print_settings_id": BAMBU_PROCESS_SETTINGS_ID,
        "flush_volumes_matrix": [
            "0",
            "280",
            "280",
            "280",
            "280",
            "0",
            "280",
            "280",
            "280",
            "280",
            "0",
            "280",
            "280",
            "280",
            "280",
            "0",
        ],
    }
    for key, expected_value in expected_project_settings.items():
        if project_settings.get(key) != expected_value:
            raise ValueError(f"3MF project has an unexpected {key}")

    extruders = {value[1] for value in expected_parts.values()}
    print(
        "FIELD_CASE_3MF_VALID "
        f"mesh_parts={len(mesh_objects)} objects={len(component_objects)} "
        f"lid_components=3 lid_islands={lid_islands} "
        f"build_items={len(build_items)} extruders={','.join(sorted(extruders))}"
    )


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
    latch_handle_reference_material = make_material(
        "Latch_Handle_Reference", (0.03, 0.35, 0.9), roughness=0.38
    )
    latch_bail_reference_material = make_material(
        "Latch_Bail_Reference", (0.95, 0.62, 0.04), roughness=0.4
    )
    latch_pin_reference_material = make_material(
        "Latch_Pin_Reference", (0.65, 0.68, 0.72), metallic=0.35, roughness=0.3
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
    parts["latch_handle"] = create_latch_handle(hardware_material)
    parts["latch_bail"] = create_latch_bail(hardware_material)
    parts["latch_base_pin"] = create_latch_base_pin(hardware_material)
    parts["latch_link_pin"] = create_latch_link_pin(hardware_material)
    parts["hinge_pin"] = create_hinge_pin(hardware_material)

    if BUILD_REFERENCE_MOCKUPS:
        create_reference_mockups(
            (
                camera_material,
                battery_material,
                latch_handle_reference_material,
                latch_bail_reference_material,
                latch_pin_reference_material,
            ),
            parts,
        )

    for name, obj in parts.items():
        validate_built_part(name, obj)
    lid_islands = validate_lid_bonding_payloads(
        evaluated_mesh_payload(parts["lid"], Vector((0.0, 0.0, 0.0))),
        (
            evaluated_mesh_payload(
                parts["title_inlay"],
                Vector((0.0, 0.0, 0.0)),
            ),
            evaluated_mesh_payload(
                parts["subtitle_inlay"],
                Vector((0.0, 0.0, 0.0)),
            ),
        ),
    )
    print(f"FIELD_CASE_LID_BONDED islands={lid_islands} plane_z={LID_INLAY_DEPTH:.2f}")

    if EXPORT_STL:
        exports = (
            (BASE_STL_NAME, parts["base"]),
            (LID_STL_NAME, parts["lid"]),
            (LOWER_TRAY_STL_NAME, parts["lower_tray"]),
            (LID_RETAINER_STL_NAME, parts["lid_retainer"]),
            (GASKET_STL_NAME, parts["gasket"]),
            (LATCH_HANDLE_STL_NAME, parts["latch_handle"]),
            (LATCH_BAIL_STL_NAME, parts["latch_bail"]),
            (LATCH_BASE_PIN_STL_NAME, parts["latch_base_pin"]),
            (LATCH_LINK_PIN_STL_NAME, parts["latch_link_pin"]),
            (HINGE_PIN_STL_NAME, parts["hinge_pin"]),
            (TITLE_INLAY_STL_NAME, parts["title_inlay"]),
            (SUBTITLE_INLAY_STL_NAME, parts["subtitle_inlay"]),
        )
        for filename, obj in exports:
            export_stl(export_path(filename), obj)
        project_path = export_3mf_project(export_path(PROJECT_3MF_NAME), parts)
        validate_3mf_project(project_path)

    if SAVE_BLEND:
        path = Path(BLEND_PATH).expanduser().resolve()
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        print(f"FIELD_CASE_SAVED_BLEND {path}")

    return parts


if __name__ == "__main__":
    build_mission1_field_case()
