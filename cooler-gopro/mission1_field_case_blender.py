"""Parametric rugged field case for two GoPro MISSION 1 cameras.

The generator creates every printable component without loading an STL or font
from disk.  The default kit holds:

* two GoPro MISSION 1 / MISSION 1 PRO cameras standing upright with their
  lenses opposed and laterally nested, including flared soft-lens-hood reliefs,
* four MISSION 1 Enduro 2 / HERO13-format batteries, terminal end downward,
* two shallow flat pockets for the removable camera battery-cage doors,
* a flush-top recessed TPU equipment tray and a one-way-keyed TPU lid pad,
* a TPU dust/splash gasket, two source-derived two-piece Pelican latch
  mechanisms mounted on M3 fixed pivots and 4 mm moving-link rods, and a
  separate pivoting handle,
* raised orange GoPro-style ``GoPro Missions`` lettering with four matching blocks.

The case is Pelican/rugged-box inspired.  The user-supplied MakerWorld example is used as
a functional precedent for recessed upper/lower inserts, gasket, case shell,
and multicolor lid; its Standard Digital File License does not allow remixing,
so none of its mesh geometry is consumed by this script.  The user-supplied
``pelican_case_blender_2.9.blend`` is a separate visual/mechanical reference.
Its latch lever and hook surfaces are embedded below as compressed coordinate
data, scaled to this case, re-bored for M3/4 mm pivot hardware, and relieved only
where the source visualization's two rigid bodies intersect through their
working sweep.  Generation never reads that ``.blend``—or any STL—at runtime.

Reference sources (checked 2026-08-27):

* Local camera envelope: ``gopro_mission1_dummy_blender.py``
* User-supplied one-camera precedent:
  https://makerworld.com/en/models/2890334-gopro-mission-1-rugged-box
* User-supplied latch mechanism source: ``~/pelican_case_blender_2.9.blend``
* Local pivoting-handle references (``handle/files``):
  https://www.thingiverse.com/thing:2926036
* Four-battery travel magazine (slot-layout cross-check):
  https://www.printables.com/model/1777128-gopro-hero-9-13-battery-magazine-for-air-travel
* One-camera rugged case with battery slots and separate seal/latch:
  https://www.printables.com/model/367570-gopro-9101112-rugged-case-2-battery-box

Run inside Blender::

    blender --background --factory-startup \
      --python mission1_field_case_blender.py

Set ``EXPORT_STL = True`` below, or use
``make -C cooler-gopro mission1-field-case`` from the repository root, to emit
all ten printable-part STLs and ``mission1_field_case_ams_project.3mf``.
The 3MF contains the complete six-plate project; its lid is one compound object
with a black shell and one raised orange text-and-block body.  The standalone
lid STLs remain available for other slicers.  Print two copies each of the
latch lever and hook STLs.  An M3 countersunk screw and captive nut mount each
lever between integrated case guards, and a 4 mm rod joins its moving hook.
The handle bar is a separate print and its mounting lugs are generated as part
of the base shell.

All dimensions are millimeters.  X is case width, Y is case depth, and Z is
height.  Every default printable part validates below 250 x 250 mm in XY.
"""

from __future__ import annotations

import base64
import gzip
import importlib.util
import json
import lzma
import math
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from itertools import pairwise
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
        module_path = directory / f"{module_name}.py"
        if module_path.is_file():
            if str(directory) not in sys.path:
                sys.path.insert(0, str(directory))
            # Text Editor runs share one Python interpreter. Importing only by
            # name can reuse an old module or one from another checkout. Load
            # the exact discovered path and cache it only after it succeeds.
            specification = importlib.util.spec_from_file_location(
                module_name, module_path
            )
            if specification is None or specification.loader is None:
                raise ImportError(f"Could not load companion module: {module_path}")
            module = importlib.util.module_from_spec(specification)
            previous_module = sys.modules.get(module_name)
            sys.modules[module_name] = module
            try:
                specification.loader.exec_module(module)
            except Exception:
                if previous_module is None:
                    sys.modules.pop(module_name, None)
                else:
                    sys.modules[module_name] = previous_module
                raise
            return module, directory

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
LATCH_LEVER_STL_NAME = "mission1_field_case_pelican_latch_lever_print_two.stl"
LATCH_HOOK_STL_NAME = "mission1_field_case_pelican_latch_hook_print_two.stl"
HANDLE_BAR_STL_NAME = "mission1_field_case_pivoting_handle_bar.stl"
HINGE_PIN_STL_NAME = "mission1_field_case_hinge_pin.stl"
LOGO_ORANGE_INLAY_STL_NAME = "mission1_field_case_lid_logo_orange_inlay.stl"
PROJECT_3MF_NAME = "mission1_field_case_ams_project.3mf"

PRINTABLE_STL_NAMES = (
    BASE_STL_NAME,
    LID_STL_NAME,
    LOWER_TRAY_STL_NAME,
    LID_RETAINER_STL_NAME,
    GASKET_STL_NAME,
    LATCH_LEVER_STL_NAME,
    LATCH_HOOK_STL_NAME,
    HANDLE_BAR_STL_NAME,
    HINGE_PIN_STL_NAME,
    LOGO_ORANGE_INLAY_STL_NAME,
)


# ---------------------------------------------------------------------------
# PARAMETRIC CASE CONFIGURATION

MAX_PRINT_XY = 250.0

# Compact double-capacity shell based on the proportions and component split
# of the supplied one-camera example, without consuming its mesh geometry.
CASE_WIDTH = 216.0
CASE_DEPTH = 154.0
BASE_HEIGHT = 62.0
CASE_CORNER_RADIUS = 12.0
WALL_THICKNESS = 4.5
BASE_FLOOR_THICKNESS = 3.2

LID_PLATE_THICKNESS = 4.0
LID_WALL_HEIGHT = 11.0
LID_FLANGE_OUTSET = 5.0
LID_FLANGE_FLARE_START_Z = 3.0
LID_FLANGE_EDGE_START_Z = 8.0
LID_LATCH_TROUGH_WIDTH = 21.6
LID_LATCH_TROUGH_SHOULDER_WIDTH = 4.5
LID_LATCH_TROUGH_SHOULDER_RISE = 1.0
LID_LATCH_RECESS_BACK_WALL = 4.0
LID_LATCH_CAPTURE_RAIL_RADIUS = 1.3
LID_LATCH_CAPTURE_RAIL_CENTER_OUTSET = 6.0
LID_LATCH_CAPTURE_RAIL_CENTER_Z = 11.0
LID_LATCH_CAPTURE_WEB_THICKNESS = 1.2
LID_LATCH_CAPTURE_RAIL_END_OVERLAP = 0.4
LID_LATCH_CAPTURE_BAY_Z0 = LID_PLATE_THICKNESS
LID_LATCH_CAPTURE_BAY_CLEARANCE = 0.5
LID_LATCH_LOAD_LEDGE_THICKNESS = 2.4
LID_LATCH_LOAD_LEDGE_RAIL_EMBED = 0.2
LID_LATCH_LOAD_LEDGE_BACK_OVERLAP = 1.0
LID_LATCH_LOAD_LEDGE_AXIAL_OVERLAP = 0.4
LID_LATCH_CAPTURE_TOWER_OUTSET = 0.7
LID_LATCH_PROTECTOR_TOP_CAP_RISE = 0.0
LID_DISPLAY_OFFSET_X = 215.0

# The lower TPU insert is a continuous recessed tray.  All cavity walls point
# down from one flat top surface; nothing protrudes above TRAY_HEIGHT.
INSERT_SIDE_CLEARANCE = 0.5
TRAY_HEIGHT = 35.0
TRAY_FLOOR_THICKNESS = 3.0
LOWER_TRAY_INSTALLED_Z = BASE_FLOOR_THICKNESS
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

# User-measured Mission 1 battery envelope. The pocket adds 1 mm total in both
# plan dimensions, while retaining the existing 21.8 mm insertion depth and
# leaving enough of the 40.56 mm battery exposed for a finger grip.
BATTERY_HEIGHT = 40.56
BATTERY_WIDTH = 33.5
BATTERY_THICKNESS = 12.5
BATTERY_CLEARANCE = 1.0
BATTERY_POCKET_WIDTH = BATTERY_THICKNESS + BATTERY_CLEARANCE
BATTERY_POCKET_DEPTH = BATTERY_WIDTH + BATTERY_CLEARANCE
BATTERY_POCKET_INSERTION_DEPTH = 21.8
BATTERY_FLOOR_Z = TRAY_HEIGHT - BATTERY_POCKET_INSERTION_DEPTH
BATTERY_CENTERS = (
    (-30.0, -48.0),
    (-10.0, -48.0),
    (10.0, -48.0),
    (30.0, -48.0),
)

# Each removable battery-cage door lies flat in a 50 x 11 mm pocket sunk only
# 11 mm into the TPU. The 18 mm inspection solid therefore remains 7 mm proud
# for finger access. Matching lid-pad bosses prevent either door from rattling.
BATTERY_DOOR_SIZE = (50.0, 10.0, 18.0)
BATTERY_DOOR_SLOT_SIZE = (BATTERY_DOOR_SIZE[0], 11.0)
BATTERY_DOOR_SLOT_DEPTH = 11.0
BATTERY_DOOR_SLOT_FLOOR_Z = TRAY_HEIGHT - BATTERY_DOOR_SLOT_DEPTH
BATTERY_DOOR_SLOT_CENTERS = ((-70.0, -60.0), (70.0, -60.0))
BATTERY_DOOR_LID_HOLD_DOWN_SIZE = (42.0, 7.0)
BATTERY_DOOR_LID_HOLD_DOWN_EXTENSION = (
    CAMERA_FLOOR_Z
    + mission1.BODY_HEIGHT
    - (BATTERY_DOOR_SLOT_FLOOR_Z + BATTERY_DOOR_SIZE[2])
)

# Two deep miscellaneous-storage pockets follow the large side channels shown
# in the supplied lower_tray.stl reference.  The left pocket continues beside
# both opposed cameras.  The right pocket is one continuous stepped cavity: a
# wide lower lobe clears the battery-door slot and the flared lens hood, while
# a narrower upper lobe continues beside the rear camera.  A circular cutter
# rounds the re-entrant step to avoid a TPU tear point.  Their envelopes
# preserve 4 mm to the tray floor, outer side walls, door slots, battery row,
# and camera/hood cutters.  The 0.1 mm reductions at both outer edges preserve
# 4 mm after mesh polygonization, and the left pocket's 0.1 mm inboard
# reduction makes its hood web a true 4 mm.
MISC_COMPARTMENT_MIN_WEB = 4.0
MISC_COMPARTMENT_FLOOR_Z = MISC_COMPARTMENT_MIN_WEB
MISC_COMPARTMENT_LOBE_BOUNDS = (
    (((-98.9, -61.1), (-50.4, 68.0)),),
    (
        ((40.9, 98.9), (-50.4, 2.5)),
        ((61.0, 98.9), (-0.5, 68.0)),
    ),
)
MISC_COMPARTMENT_CORNER_RADIUS = 3.0
MISC_COMPARTMENT_STEP_FILLETS = ((), ((61.0, 2.5, 2.0),))

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
GASKET_HEIGHT = 1.45
GASKET_FIT_CLEARANCE = 0.2

# Hinge axis is along X.  A 4.1 mm rod runs only through the base knuckles.
# Each lid receiver opens rearward, parallel to the lid plate in print
# orientation.  The closed case cannot lift off vertically; the unchanged base
# remains in the actual slot escape path through 65 degrees, and the complete
# lid slides diagonally up/forward off the rod at 70 degrees open.
HINGE_AXIS_Y = CASE_DEPTH / 2.0 + 3.8
HINGE_OUTER_DIAMETER = 10.0
HINGE_ROD_DIAMETER = 4.1
HINGE_BASE_HOLE_DIAMETER = 4.5
HINGE_LID_RECEIVER_DIAMETER = 4.8
HINGE_LID_SLOT_WIDTH = 4.6
HINGE_LID_SLOT_TILT_DEGREES = 0.0
HINGE_LID_RELEASE_ANGLE_DEGREES = 70.0
HINGE_LID_PRE_RELEASE_BLOCK_ANGLE_DEGREES = 65.0
HINGE_LID_PRE_RELEASE_SWEEP_STEP_DEGREES = 5.0
HINGE_LID_RELEASE_PATH_SAMPLES = 17
HINGE_OPEN_SWEEP_MAX_ANGLE_DEGREES = 110.0
HINGE_OPEN_SWEEP_STEP_DEGREES = 1.0
HINGE_PIN_DIAMETER = HINGE_ROD_DIAMETER
HINGE_BASE_SEGMENTS = ((-76.0, -42.0), (-18.0, 18.0), (42.0, 76.0))
HINGE_LID_SEGMENTS = ((-41.4, -18.6), (18.6, 41.4))
HINGE_ROD_END_INSET = 0.5
HINGE_ROD_X0 = HINGE_BASE_SEGMENTS[0][0] + HINGE_ROD_END_INSET
HINGE_ROD_X1 = HINGE_BASE_SEGMENTS[-1][1] - HINGE_ROD_END_INSET
HINGE_LID_END_STOP_BASE_CLEARANCE = 0.3
HINGE_LID_END_STOP_LENGTH = 3.0
HINGE_LID_END_STOP_DIAMETER = 6.0
HINGE_RIM_RELIEF_RADIAL_CLEARANCE = 0.4
HINGE_RIM_RELIEF_AXIAL_CLEARANCE = 0.2
HINGE_ROD_PATH_AXIAL_CLEARANCE = 0.2
HINGE_BORE_CUTTER_AXIAL_OVERTRAVEL = 0.6
HINGE_BORE_VALIDATION_RADIAL_CLEARANCE = 0.005
HINGE_ROD_RELEASE_AXIAL_VALIDATION_INSET = 0.05

# Each base knuckle grows from a full-width 45-degree web rather than leaving
# the lower half of its circular barrel unsupported.  The ramp meets the
# barrel at its lower-outboard tangent, while a small overlap into the rear
# wall makes the Boolean bond robust without entering the internal envelope.
HINGE_BASE_GUSSET_WALL_OVERLAP = 0.3
HINGE_BASE_GUSSET_MAX_OVERHANG_DEGREES = 45.0
HINGE_BASE_GUSSET_TANGENT_OFFSET = HINGE_OUTER_DIAMETER / 2.0 / math.sqrt(2.0)
HINGE_BASE_GUSSET_TANGENT_Y = HINGE_AXIS_Y + HINGE_BASE_GUSSET_TANGENT_OFFSET
HINGE_BASE_GUSSET_TANGENT_Z = BASE_HEIGHT - HINGE_BASE_GUSSET_TANGENT_OFFSET
HINGE_BASE_GUSSET_ROOT_Y = CASE_DEPTH / 2.0 - HINGE_BASE_GUSSET_WALL_OVERLAP
HINGE_BASE_GUSSET_ROOT_Z = HINGE_BASE_GUSSET_TANGENT_Z - (
    HINGE_BASE_GUSSET_TANGENT_Y - HINGE_BASE_GUSSET_ROOT_Y
)
HINGE_BASE_GUSSET_PROFILE_YZ = (
    (HINGE_BASE_GUSSET_ROOT_Y, HINGE_BASE_GUSSET_ROOT_Z),
    (HINGE_BASE_GUSSET_TANGENT_Y, HINGE_BASE_GUSSET_TANGENT_Z),
    (HINGE_BASE_GUSSET_ROOT_Y, HINGE_BASE_GUSSET_TANGENT_Z),
)


def support_free_mount_profile_yz(
    pivot_y,
    pivot_z,
    body_y,
    body_lower_z,
    body_upper_z,
    outer_radius,
    *,
    upper_arc_steps=6,
    return_steps=6,
):
    """Return a printable case-mount profile with a curved upper return.

    The lower body web rises to the pivot boss before extending outward.  Its
    exposed boss edge is a 45-degree chord from the bottom point to the most
    outward point, so the case prints upright without a horizontal ledge.  The
    upper half follows a circular arc, then a quadratic curve blends back into
    the case wall instead of ending in sharp projecting corners.
    """
    bottom = (pivot_y, pivot_z - outer_radius)
    outward = (pivot_y - outer_radius, pivot_z)
    profile = [(body_y, body_lower_z), bottom, outward]
    for step in range(1, upper_arc_steps + 1):
        angle = math.pi - (math.pi / 2.0) * step / upper_arc_steps
        profile.append(
            (
                pivot_y + outer_radius * math.cos(angle),
                pivot_z + outer_radius * math.sin(angle),
            )
        )
    top = profile[-1]
    control = (
        pivot_y + 0.58 * (body_y - pivot_y),
        top[1],
    )
    for step in range(1, return_steps + 1):
        t = step / return_steps
        one_minus_t = 1.0 - t
        profile.append(
            (
                one_minus_t * one_minus_t * top[0]
                + 2.0 * one_minus_t * t * control[0]
                + t * t * body_y,
                one_minus_t * one_minus_t * top[1]
                + 2.0 * one_minus_t * t * control[1]
                + t * t * body_upper_z,
            )
        )
    return tuple(profile)


# Every handle/latch pivot uses this same minimum radial ligament.  All
# reinforcement bosses derive from it; large increases may also require more
# exterior clearance while the internal case envelope remains fixed.
PIVOT_MIN_WALL_THICKNESS = 2.0
PIVOT_REINFORCEMENT_MARGIN = 0.5
PIVOT_REFERENCE_MAX_BORE_RADIUS = 2.2
PIVOT_MOUNT_RADIUS_MARGIN = 0.31
PIVOT_MOUNT_OUTER_RADIUS = (
    PIVOT_REFERENCE_MAX_BORE_RADIUS + PIVOT_MIN_WALL_THICKNESS
) * math.sqrt(2.0) + PIVOT_MOUNT_RADIUS_MARGIN
PIVOT_MOUNT_BODY_Y = -CASE_DEPTH / 2.0 + 0.3
PIVOT_MOUNT_RAMP_VERTICAL_MARGIN = 0.5

# The two-piece mechanism comes from the latch bodies in the user-supplied
# ``pelican_case_blender_2.9.blend``.  The embedded coordinates are already
# scaled to 80% for this shorter case.  The lever's fixed and moving bores are
# 4.4 mm running fit around their 4 mm moving-link rod.  The hook cheeks retain
# that rod in a 3.9 mm press-fit bore.  The fixed lever pivot instead uses one
# M3 countersunk screw through both integrated case guards and a 3.5 mm
# easy-running lever bore, with a captive nut on the case-center side.
# The source visualization contained rigid-body overlaps; only their internal
# 0-to-80-degree relative sweep was relieved before the meshes were embedded.
LATCH_X_CENTERS = (-82.0, 82.0)
LATCH_LINK_ROD_DIAMETER = 4.0
LATCH_PRESS_FIT_BORE_DIAMETER = 3.9
LATCH_RUNNING_BORE_DIAMETER = 4.4
LATCH_FIXED_M3_NOMINAL_DIAMETER = 3.0
LATCH_FIXED_M3_CLEARANCE_DIAMETER = 3.5
LATCH_FIXED_M3_COUNTERSINK_DIAMETER = 6.4
LATCH_FIXED_M3_COUNTERSINK_DEPTH = (
    LATCH_FIXED_M3_COUNTERSINK_DIAMETER
    - LATCH_FIXED_M3_CLEARANCE_DIAMETER
) / 2.0
LATCH_FIXED_M3_NOMINAL_HEAD_DIAMETER = 5.6
LATCH_FIXED_M3_NUT_ACROSS_FLATS = 5.8
LATCH_FIXED_M3_NOMINAL_NUT_ACROSS_FLATS = 5.5
LATCH_FIXED_M3_NUT_DEPTH = 2.7
LATCH_FIXED_M3_NOMINAL_NUT_THICKNESS = 2.4
LATCH_FIXED_M3_RECESS_BOOLEAN_OVERTRAVEL = 0.2
LATCH_FIXED_M3_MIN_RECESS_FLOOR = 1.0
LATCH_FIXED_M3_BOLT_LENGTH = 35.0
LATCH_FIXED_M3_MIN_THREAD_ENGAGEMENT = LATCH_FIXED_M3_NOMINAL_NUT_THICKNESS
LATCH_FIXED_M3_MAX_TIP_PROTRUSION = 3.0
LATCH_LID_INSTALLED_Z = BASE_HEIGHT + LID_WALL_HEIGHT
LATCH_SOURCE_SCALE = 0.8
LATCH_WIDTH = 20.48
LATCH_LEVER_PRINT_SIZE = (43.113704, 18.100159, LATCH_WIDTH)
LATCH_HOOK_PRINT_SIZE = (16.732555, 50.241260, LATCH_WIDTH)
LATCH_LINK_PIVOT_LOCAL_YZ = (0.733023, -10.648121)
LATCH_BASE_PIVOT_Y = -85.0
LATCH_BASE_PIVOT_Z = 41.65
LATCH_LEVER_CLOSED_ANGLE = 0.0
LATCH_LEVER_OPEN_ANGLE = -80.0
LATCH_HOOK_CLOSED_ANGLE = -80.0
LATCH_HOOK_CAM_ROTATION_DEGREES = -12.0
LATCH_HOOK_CAM_GUARD_ROTATION_DEGREES = -5.0
LATCH_HOOK_POST_RELEASE_FOLLOW_RATIO = 0.2
LATCH_SWEEP_STEP_DEGREES = 2.0
LATCH_SWEEP_RESIDUAL_VOLUME_LIMIT = 1e-5
LATCH_AXIAL_CONTACT_RESIDUAL_VOLUME_LIMIT = 0.001
LATCH_MAX_CAPTURE_FREE_LIFT = 0.15
LATCH_BASE_EAR_WIDTH = 4.0
LATCH_BASE_EAR_AXIAL_CLEARANCE = 0.2
LATCH_BASE_EAR_CENTER_OFFSET_X = (
    LATCH_WIDTH / 2.0 + LATCH_BASE_EAR_AXIAL_CLEARANCE + LATCH_BASE_EAR_WIDTH / 2.0
)
LATCH_MOUNT_LOWER_Z = (
    LATCH_BASE_PIVOT_Z
    - PIVOT_MOUNT_OUTER_RADIUS
    - abs(PIVOT_MOUNT_BODY_Y - LATCH_BASE_PIVOT_Y)
    - PIVOT_MOUNT_RAMP_VERTICAL_MARGIN
)
LATCH_BASE_EAR_PROFILE_YZ = support_free_mount_profile_yz(
    LATCH_BASE_PIVOT_Y,
    LATCH_BASE_PIVOT_Z,
    PIVOT_MOUNT_BODY_Y,
    LATCH_MOUNT_LOWER_Z,
    54.5,
    PIVOT_MOUNT_OUTER_RADIUS,
)
LATCH_LEVER_FIXED_BOSS_RADIUS = (
    LATCH_FIXED_M3_CLEARANCE_DIAMETER / 2.0
    + PIVOT_MIN_WALL_THICKNESS
    + PIVOT_REINFORCEMENT_MARGIN
)
LATCH_LEVER_LINK_BOSS_RADIUS = (
    LATCH_RUNNING_BORE_DIAMETER / 2.0
    + PIVOT_MIN_WALL_THICKNESS
    + PIVOT_REINFORCEMENT_MARGIN
)
LATCH_HOOK_LINK_BOSS_RADIUS = (
    LATCH_PRESS_FIT_BORE_DIAMETER / 2.0
    + PIVOT_MIN_WALL_THICKNESS
    + PIVOT_REINFORCEMENT_MARGIN
)
# The source lever has an 8.8 mm central link tongue.  The hook uses two outer
# cheeks beginning at X = +/-4.6 mm, leaving 0.2 mm running clearance per side.
LATCH_LEVER_LINK_TONGUE_WIDTH = 8.8
LATCH_HOOK_CHEEK_INNER_X = 4.6
LATCH_HOOK_CHEEK_OUTER_X = LATCH_WIDTH / 2.0
LATCH_HOOK_CHEEK_WIDTH = LATCH_HOOK_CHEEK_OUTER_X - LATCH_HOOK_CHEEK_INNER_X
LATCH_REINFORCEMENT_RUNNING_CLEARANCE = 0.30
LATCH_REINFORCEMENT_AXIAL_CLEARANCE = 0.10
LATCH_REINFORCEMENT_RELIEF_STEP_DEGREES = 10.0
LATCH_DETENT_SIDES = (-1.0, 1.0)
LATCH_DETENT_LOCAL_YZ = (5.0, -4.0)
LATCH_DETENT_BOSS_RADIUS = 1.5
LATCH_DETENT_BOSS_PROTRUSION = 1.40
LATCH_DETENT_DIMPLE_RADIUS = 1.75
LATCH_DETENT_DIMPLE_DEPTH = 1.45
LATCH_DETENT_MIN_INTERFERENCE = 0.80
LATCH_DETENT_RELEASE_ANGLE = -22.0
LATCH_DETENT_SWEEP_STEP_DEGREES = 0.25
LATCH_DETENT_MIN_PEAK_VOLUME = 0.05
LATCH_DETENT_RELEASE_RESIDUAL_VOLUME_LIMIT = 0.0001
LATCH_WRONG_WAY_STOP_ANGLE = 10.0
LATCH_WRONG_WAY_STOP_MIN_VOLUME = 10.0
LATCH_CAPTURE_RAIL_PATH_CLEARANCE = 0.1
LATCH_CAPTURE_HOOK_WALL = 2.0
LATCH_CAPTURE_CLEARANCE_SWEEP_STEP_DEGREES = 2.0
LATCH_CAPTURE_RELEASE_GUARD_ANGLE = -12.0
LATCH_CAPTURE_FULL_RELEASE_ANGLE = -24.0
LATCH_CAPTURE_RELEASE_GUARD_MIN_VOLUME = 0.1
LATCH_CAPTURE_UPPER_ARM_THICKNESS = 3.2
LATCH_CAPTURE_UPPER_ARM_FRONT_OVERLAP = 0.2
LATCH_CAPTURE_UPPER_ARM_AXIAL_INSET = 0.04
LATCH_CAPTURE_NUB_RADIUS = 1.4
LATCH_CAPTURE_NUB_ROOT_BOSS_RADIUS = 1.7
LATCH_CAPTURE_ROOT_BOSS_LEDGE_CLEARANCE = 0.05
LATCH_CAPTURE_NUB_RAIL_CLEARANCE = 0.10
LATCH_CAPTURE_NUB_AXIAL_WIDTH = 16.0
LATCH_CAPTURE_NUB_RECESS_AXIAL_CLEARANCE = 0.4
LATCH_CAPTURE_NUB_LEDGE_CLEARANCE = 0.25
LATCH_CAPTURE_NUB_CORE_RADIAL_MARGIN = 0.35
LATCH_CAPTURE_NUB_CORE_AXIAL_MARGIN = 0.4
LATCH_CAPTURE_FLAT_PAD_AXIAL_WIDTH = 18.0
LATCH_CAPTURE_FLAT_PAD_CASEWARD_LENGTH = 1.3
LATCH_CAPTURE_FLAT_PAD_HEIGHT = 2.8
LATCH_CAPTURE_FLAT_PAD_SEATED_CLEARANCE = 0.14
LATCH_CAPTURE_FLAT_PAD_RAIL_CLEARANCE = 0.05
LATCH_CAPTURE_LOWER_JAW_REMOVAL_CASEWARD_Y = -82.5
LATCH_CAPTURE_OUTWARD_PEEL_TRAVEL = 0.6
LATCH_CAPTURE_OUTWARD_PEEL_MIN_VOLUME = 0.02
LID_LATCH_LOAD_LEDGE_CONTACT_Z = LID_LATCH_CAPTURE_RAIL_CENTER_Z - 0.2
LATCH_LINK_ROD_LENGTH = LATCH_WIDTH
LATCH_FINGER_ACCESS_CLEARANCE = 24.0
LATCH_MOUNT_HANDLE_CLEARANCE = 20.0
LATCH_PROTECTOR_BASE_WIDTH = 6.0
LATCH_PROTECTOR_AXIAL_OUTWARD_SHIFT = (
    LATCH_PROTECTOR_BASE_WIDTH - LATCH_BASE_EAR_WIDTH
) / 2.0
LATCH_FIXED_M3_GUARD_SPAN = (
    LATCH_WIDTH
    + 2.0 * LATCH_BASE_EAR_AXIAL_CLEARANCE
    + 2.0 * LATCH_PROTECTOR_BASE_WIDTH
)
LATCH_PROTECTOR_BODY_Y = -CASE_DEPTH / 2.0 + 0.3
LATCH_PROTECTOR_FRONT_Y = -98.0
LATCH_PROTECTOR_ROOT_Z = 3.0
LATCH_PROTECTOR_FRONT_LOWER_Z = LATCH_PROTECTOR_ROOT_Z + abs(
    LATCH_PROTECTOR_FRONT_Y - LATCH_PROTECTOR_BODY_Y
)
LATCH_PROTECTOR_FRONT_UPPER_Z = 53.5
LATCH_PROTECTOR_TOP_Z = 56.5
LATCH_PROTECTOR_PROFILE_YZ = (
    (LATCH_PROTECTOR_BODY_Y, LATCH_PROTECTOR_ROOT_Z),
    (LATCH_PROTECTOR_FRONT_Y, LATCH_PROTECTOR_FRONT_LOWER_Z),
    (LATCH_PROTECTOR_FRONT_Y, LATCH_PROTECTOR_FRONT_UPPER_Z),
    (LATCH_PROTECTOR_FRONT_Y + 1.5, LATCH_PROTECTOR_FRONT_UPPER_Z + 2.0),
    (LATCH_PROTECTOR_BODY_Y, LATCH_PROTECTOR_TOP_Z),
)

# Each closed source hook nests in a deep molded bay cut through the lid skirt.
# A 2.6 mm horizontal rail is embedded through the outer edge of a continuous
# 2.4 mm load ledge bonded to the 4 mm recess back wall.  The hook's broad flat
# pad presses downward on that ledge; its cylindrical boss sits behind the rail
# only to prevent outward escape.  A second overlapping round boss gives the
# TPU retention feature a thick root instead of a folding wedge.  Buttressed
# side towers support both ends and prevent lateral walk-off.
LID_LATCH_LIP_DRAW = GASKET_HEIGHT - GASKET_CHANNEL_DEPTH
LID_LATCH_RIM_EDGE_THICKNESS = LID_WALL_HEIGHT - LID_FLANGE_EDGE_START_Z
LID_LATCH_CAPTURE_RAIL_CENTER_Y = (
    CASE_DEPTH / 2.0 + LID_FLANGE_OUTSET + LID_LATCH_CAPTURE_RAIL_CENTER_OUTSET
)
LATCH_CAPTURE_RAIL_INSTALLED_Y = -LID_LATCH_CAPTURE_RAIL_CENTER_Y
LATCH_CAPTURE_RAIL_INSTALLED_Z = LATCH_LID_INSTALLED_Z - LID_LATCH_CAPTURE_RAIL_CENTER_Z
LATCH_CAPTURE_LOAD_LEDGE_INSTALLED_Z = (
    LATCH_LID_INSTALLED_Z - LID_LATCH_LOAD_LEDGE_CONTACT_Z
)
LATCH_CAPTURE_NUB_INSTALLED_Z = (
    LATCH_CAPTURE_LOAD_LEDGE_INSTALLED_Z
    + LATCH_CAPTURE_NUB_LEDGE_CLEARANCE
    + LATCH_CAPTURE_NUB_RADIUS
)
LATCH_CAPTURE_NUB_RAIL_CENTER_DISTANCE = (
    LID_LATCH_CAPTURE_RAIL_RADIUS
    + LATCH_CAPTURE_NUB_RADIUS
    + LATCH_CAPTURE_NUB_RAIL_CLEARANCE
)
LATCH_CAPTURE_NUB_RAIL_VERTICAL_OFFSET = (
    LATCH_CAPTURE_NUB_INSTALLED_Z - LATCH_CAPTURE_RAIL_INSTALLED_Z
)
LATCH_CAPTURE_NUB_RAIL_CASEWARD_OFFSET = math.sqrt(
    max(
        0.0,
        LATCH_CAPTURE_NUB_RAIL_CENTER_DISTANCE**2
        - LATCH_CAPTURE_NUB_RAIL_VERTICAL_OFFSET**2,
    )
)
LATCH_CAPTURE_NUB_INSTALLED_Y = (
    LATCH_CAPTURE_RAIL_INSTALLED_Y + LATCH_CAPTURE_NUB_RAIL_CASEWARD_OFFSET
)
LID_LATCH_CAPTURE_NUB_CENTER_Y = -LATCH_CAPTURE_NUB_INSTALLED_Y
LID_LATCH_CAPTURE_NUB_CENTER_Z = LATCH_LID_INSTALLED_Z - LATCH_CAPTURE_NUB_INSTALLED_Z
LATCH_CAPTURE_FLAT_PAD_OUTWARD_INSTALLED_Y = (
    LATCH_CAPTURE_RAIL_INSTALLED_Y
    + LID_LATCH_CAPTURE_RAIL_RADIUS
    + LATCH_CAPTURE_RAIL_PATH_CLEARANCE
    + LATCH_CAPTURE_FLAT_PAD_RAIL_CLEARANCE
)
LATCH_CAPTURE_FLAT_PAD_CASEWARD_INSTALLED_Y = (
    LATCH_CAPTURE_FLAT_PAD_OUTWARD_INSTALLED_Y + LATCH_CAPTURE_FLAT_PAD_CASEWARD_LENGTH
)
LATCH_CAPTURE_FLAT_PAD_BOTTOM_INSTALLED_Z = (
    LATCH_CAPTURE_LOAD_LEDGE_INSTALLED_Z + LATCH_CAPTURE_FLAT_PAD_SEATED_CLEARANCE
)
LATCH_CAPTURE_FLAT_PAD_TOP_INSTALLED_Z = (
    LATCH_CAPTURE_FLAT_PAD_BOTTOM_INSTALLED_Z + LATCH_CAPTURE_FLAT_PAD_HEIGHT
)
LATCH_CAPTURE_ROOT_BOSS_INSTALLED_Y = (
    LATCH_CAPTURE_NUB_INSTALLED_Y + LATCH_CAPTURE_FLAT_PAD_CASEWARD_INSTALLED_Y
) / 2.0
LATCH_CAPTURE_ROOT_BOSS_INSTALLED_Z = (
    LATCH_CAPTURE_LOAD_LEDGE_INSTALLED_Z
    + LID_LATCH_LIP_DRAW
    + LATCH_CAPTURE_NUB_ROOT_BOSS_RADIUS
    + LATCH_CAPTURE_ROOT_BOSS_LEDGE_CLEARANCE
)


def latch_hook_global_angle_degrees(lever_angle: float) -> float:
    """Cam the true-behind round boss clear of the lid capture rail."""
    if lever_angle <= LATCH_CAPTURE_FULL_RELEASE_ANGLE:
        return (
            LATCH_HOOK_CLOSED_ANGLE
            + LATCH_HOOK_CAM_ROTATION_DEGREES
            + LATCH_HOOK_POST_RELEASE_FOLLOW_RATIO
            * (lever_angle - LATCH_CAPTURE_FULL_RELEASE_ANGLE)
        )
    if lever_angle >= LATCH_CAPTURE_RELEASE_GUARD_ANGLE:
        guard_span = LATCH_LEVER_CLOSED_ANGLE - LATCH_CAPTURE_RELEASE_GUARD_ANGLE
        guard_progress = (LATCH_LEVER_CLOSED_ANGLE - lever_angle) / guard_span
        cam_rotation = LATCH_HOOK_CAM_GUARD_ROTATION_DEGREES * guard_progress
    else:
        release_span = (
            LATCH_CAPTURE_RELEASE_GUARD_ANGLE - LATCH_CAPTURE_FULL_RELEASE_ANGLE
        )
        release_progress = (
            LATCH_CAPTURE_RELEASE_GUARD_ANGLE - lever_angle
        ) / release_span
        cam_rotation = (
            LATCH_HOOK_CAM_GUARD_ROTATION_DEGREES
            + (LATCH_HOOK_CAM_ROTATION_DEGREES - LATCH_HOOK_CAM_GUARD_ROTATION_DEGREES)
            * release_progress
        )
    cam_rotation = min(
        0.0,
        max(LATCH_HOOK_CAM_ROTATION_DEGREES, cam_rotation),
    )
    return LATCH_HOOK_CLOSED_ANGLE + cam_rotation


def latch_hook_origin_yz(lever_angle: float):
    """Return the moving hook-pivot origin in installed case coordinates."""
    lever_radians = math.radians(lever_angle)
    link_y, link_z = LATCH_LINK_PIVOT_LOCAL_YZ
    return (
        LATCH_BASE_PIVOT_Y
        + math.cos(lever_radians) * link_y
        - math.sin(lever_radians) * link_z,
        LATCH_BASE_PIVOT_Z
        + math.sin(lever_radians) * link_y
        + math.cos(lever_radians) * link_z,
    )


def latch_rail_in_hook_local_yz(lever_angle: float):
    """Transform the fixed lid rail into the cammed moving hook frame."""
    hook_origin_y, hook_origin_z = latch_hook_origin_yz(lever_angle)
    hook_radians = math.radians(latch_hook_global_angle_degrees(lever_angle))
    delta_y = LATCH_CAPTURE_RAIL_INSTALLED_Y - hook_origin_y
    delta_z = LATCH_CAPTURE_RAIL_INSTALLED_Z - hook_origin_z
    return (
        math.cos(hook_radians) * delta_y + math.sin(hook_radians) * delta_z,
        -math.sin(hook_radians) * delta_y + math.cos(hook_radians) * delta_z,
    )


def installed_yz_in_hook_local(
    lever_angle: float, installed_y: float, installed_z: float
):
    """Transform an installed case point into the moving hook's local frame."""
    hook_origin_y, hook_origin_z = latch_hook_origin_yz(lever_angle)
    hook_radians = math.radians(latch_hook_global_angle_degrees(lever_angle))
    delta_y = installed_y - hook_origin_y
    delta_z = installed_z - hook_origin_z
    return (
        math.cos(hook_radians) * delta_y + math.sin(hook_radians) * delta_z,
        -math.sin(hook_radians) * delta_y + math.cos(hook_radians) * delta_z,
    )


def hook_local_yz_in_installed(lever_angle: float, local_y: float, local_z: float):
    """Transform a moving-hook point into installed case coordinates."""
    hook_origin_y, hook_origin_z = latch_hook_origin_yz(lever_angle)
    hook_radians = math.radians(latch_hook_global_angle_degrees(lever_angle))
    return (
        hook_origin_y
        + math.cos(hook_radians) * local_y
        - math.sin(hook_radians) * local_z,
        hook_origin_z
        + math.sin(hook_radians) * local_y
        + math.cos(hook_radians) * local_z,
    )


# Separate reference-shaped U handle.  The base lugs are unioned into the case
# shell; only the bar is a separate print.  ROD uses a retaining fit in the
# fixed lugs.  M4 regenerates 4.4 mm clearance bores for M4 x 20 hardware.
HANDLE_HARDWARE_MODE = "ROD"
HANDLE_ROD_DIAMETER = 4.0
HANDLE_PRESS_FIT_BORE_DIAMETER = 3.9
HANDLE_RUNNING_BORE_DIAMETER = 4.4
HANDLE_PIVOT_X = 42.5
HANDLE_BASE_LUG_X = HANDLE_PIVOT_X
HANDLE_PIVOT_RADIUS_MARGIN = 0.16
HANDLE_PIVOT_BOSS_RADIUS = (
    PIVOT_REFERENCE_MAX_BORE_RADIUS + PIVOT_MIN_WALL_THICKNESS
) * math.sqrt(2.0) + HANDLE_PIVOT_RADIUS_MARGIN
HANDLE_FOLDED_FACE_CLEARANCE = 0.5
HANDLE_PIVOT_Y = (
    -CASE_DEPTH / 2.0 - HANDLE_PIVOT_BOSS_RADIUS - HANDLE_FOLDED_FACE_CLEARANCE
)
HANDLE_PIVOT_Z = LATCH_LID_INSTALLED_Z / 2.0
HANDLE_BAR_OUTER_WIDTH = 95.0
HANDLE_BAR_INNER_WIDTH = 75.0
HANDLE_BAR_DROP = 32.5
HANDLE_BAR_DEPTH = 11.0
HANDLE_BAR_THICKNESS = 2.0 * HANDLE_PIVOT_BOSS_RADIUS
HANDLE_GRIP_HOLE_DIAMETER = 7.0
HANDLE_GRIP_HOLE_COUNT = 5
HANDLE_GRIP_HOLE_PITCH = 12.0
HANDLE_BASE_LUG_WIDTH = 5.0
HANDLE_AXIAL_CLEARANCE = 0.4
HANDLE_MIN_USABLE_GRIP_WIDTH = 75.0
HANDLE_RAISED_FINGER_CLEARANCE = 25.0
HANDLE_SWEEP_STEP_DEGREES = 2.0
HANDLE_SWEEP_RESIDUAL_VOLUME_LIMIT = 1e-5
HANDLE_PRINT_OFFSET_Y = -285.0
HANDLE_MOUNT_LOWER_Z = (
    HANDLE_PIVOT_Z
    - PIVOT_MOUNT_OUTER_RADIUS
    - abs(PIVOT_MOUNT_BODY_Y - HANDLE_PIVOT_Y)
    - PIVOT_MOUNT_RAMP_VERTICAL_MARGIN
)
HANDLE_BASE_EAR_PROFILE_YZ = support_free_mount_profile_yz(
    HANDLE_PIVOT_Y,
    HANDLE_PIVOT_Z,
    PIVOT_MOUNT_BODY_Y,
    HANDLE_MOUNT_LOWER_Z,
    49.0,
    PIVOT_MOUNT_OUTER_RADIUS,
)
HANDLE_FORK_SWEEP_CLEARANCE = 0.6
HANDLE_FORK_RELIEF_LENGTH = 2.0 * (
    max(
        math.hypot(y - HANDLE_PIVOT_Y, z - HANDLE_PIVOT_Z)
        for y, z in HANDLE_BASE_EAR_PROFILE_YZ
    )
    + HANDLE_FORK_SWEEP_CLEARANCE
)

# LZMA-compressed lever and hook coordinates extracted from the user-supplied
# Blender 2.90 case scene.  The visible source surfaces are retained at 80%
# scale.  The fixed/link bores and hidden mutual-sweep surfaces were adapted as
# described above so these visualization meshes become printable moving parts.
PELICAN_BLEND_LATCH_MESHES_LZMA_BASE85 = (
    b"{Wp48S^xk9=GL@E0stWa8~^|S5YJf5<iC^e{#^h8064E0vQzL=XSz(d@F#4%T$CQkt#l)-mO#77C?f1Cc6mXl^CAeM4?Yi$ZF70i"
    b"6N)jCNO4+#k=$I0rhEcfUFmqzGdcU!i<4g)r*|@l*bMNJ?s(lD1eb*5^8yd2;Xng-Mzt#}R<FjFN0OE*PJIwlyw!r^Jdl&FAA5zn"
    b"Fvu4;TMzQ$*?u*&^meS+l{$McZYq8=R}%}TYK)-TNc#IC`5gwA5db^)C$p`N&}pF2lN;c~$5<nJ199Zn&)wBkC>H<QUZ>-{OslYR"
    b"4}8nvN}jOS>VDi#`jr;i54cAvo=*vNvJYZpX&lW`d8CyLplB_UwS441Bz9qPw}P|`^`Z*A@lI!)NC1wz(<+SEAGGuCCS%o>cAVZ@"
    b"wnUO>{<7%Bl9Wz3wRRLF9Tu59_EK=tb3{&Ja?UrQsv!nEc@Kjm{^y>+nu4+Zr*7UEY?nFFV7nTBvR$rxQYja}H93D@iLvbQV#4E{"
    b"Xd<0D=4$n^p<mgd1}wU~r<e{voa63pt&q+bn>6X}E~vb!aHCln`K_q$e6C+~lZGWlb$R}q!1oELZ07@!w6}82LKgHaiW34~y0y5G"
    b"u{tt!%s@K|iQ90G>v0RdUvnOV3dzW|Sdpj%o<i`47`Od~6O2DVQ{)E}b%*-U%0vID@QXxGgz5w`F-NCJtet`wdcM4eVs0+g$jAm8"
    b"i-Y`6bIbHz5%sQIk!An0^_@XxU878F$}H_tzY(*q01QQJLLNYiV8=M`d&)m`W(ND3KaoB1_&Wdb$M;evZF8bUHywraJ|>b0CPaPJ"
    b"uqwxvQ)JT<`2RA^yL}_HRA{;h({e_yZvYDB!DFN)Zq?11#Yse4UhUMt%y315T1eYGs8TgPl`j3T&WyBWIG~h8>F5V=pbzoZwh7?e"
    b"Ns$!(>F|y`<Qc#!mlB;YLo%HKNVHN4n<o}}9wT|;u&`M1`00YKC#8t!e?cX0ZK^o?>iE|YRn3q4-d3wzb~8ggtZ_bPCi*mWH?;4C"
    b"&1KO6pMUo^q+Ev||0IXglEt|zKN;X+PW46yx9|`|^47qf0<sB^6<xPDZW9wLvVcpfjtr)9q_VBgc-@PeA7edfL{j>~8*N_lAOV2o"
    b"w67r6Z{4->WHeccm{TRJBP{TY8Lq^H3c^XwDT1TT=ZX&T7_=hXY(mZic=vdpTlpdMcr@8Jg39mlTwb%=EiBF_RDW=6lX6(Bj>NVo"
    b"vSX3}1?GRFoL$#&Rlrpu3@-vP(}YxBPN)^{h85JLR?z!f!+*OV<sxPK@se>y)ZEpE;MQ;7XVR!UbNh#_yG{D$_Fl9|C3@i~t{65W"
    b"VOUKt5<H(}8=_(&*OOg(pHidgTC_!t>pxnToyU*dWPUR5z^Ef;B9_W!6tWxmn#qT|;&mm+kY}>B(9wy{59^hey8R@u?~A!<r9DFL"
    b"kV8QP9@~YAnx;l1L@19^MJlp_WiE#GKm?;$WnLSmkPhhq3xPNM%f%X@MtvBtri!ymfW_evMz$bkb*?Q*qg_&%mupud*e{(owTC2V"
    b"d$m2CCCrdXz0wpfy>E-C!T<lu1Z*5FQpo8pPJP;-bVCU+a2HP{v>uO(#mW`UXpS&Zwld|~iHMB<m5y;A-qS6#B7m?Is1!9elx0i)"
    b"l>@92Z*0qV23ij7;3iGdJU!C|d~yBv_fe8E^VUy6c3se;)vEnc);`9#?GjLy?6;+e_%l~<g<PM;O1FiE|GRRHD09>=>C}6|gbV<-"
    b"YM8EMd9UreJlp~0o8p)Z>1+c3iu#ZDUTYNv!T~dB=u3n5j(6fps&*5g%wBOANnAub%6}|v)hd>Hb<yr#zcu%}Pv-}RdLIhBErjFQ"
    b"XtO@P_Uo;Knw)9$X5;47-zi*-bD4l-r2Yt~46~&2IcP0eB8AW?T*C8T;P-*Le@By7Ztj8$%J3K?Eyom{nCl+gB2B^}hcTT0fkWTM"
    b"3QIE<9kerF7*fQ?i0wv5KJF_oFT>Jc)^U#egmq-`Yq&el$_ZKk0Fz@#1?=IKIsi8eN-UH}$a@S?NNQNR*ZH2ZOE7$#x5n`~0~yC)"
    b">VLJRfQ+I)h7uf>I^zFpWlkmF2q<#~3>TXDatJ^4ptPhsL1f(mXe|e&4G$Kyqc*Jgp(>PC{2S#F1@F<!A`qxqAQ4Dpt20kwBJ^!B"
    b"=sl;Au&Ta-Bd2Y+q)SENZ@5Z!4Ob8J!-|yU5s0~+?fVyS>WEU++8^ne&ITnHk0M<i6T~6I8SW=Q8b*xKmn|!26q8>)54|4gC}Z`n"
    b"S6<i4+!B+&an&5-YPoP9Lo+#`6*{&L>H{f8q35$B8v_-9^*qw?IW1gzaTNtXH+CY1Ozbn$9c`#{Fy#g{K>x|72$(25Qq&eVz)x6M"
    b"$Kl5D@MCuH-4zSWZxW~^Q<|O}QrH}%Ie=>1*5S;#s|cf1C>g-5t$|CcnzD%k<2jhHTN0K^!m}d<7D_DQTLX-IitR`NvJ?BiB<QRT"
    b"SNapGf|!iNq3XFy`P?h&7Sb>Ip9(Zh^&q8laN^hQk*9OMznPeL(D&H=u%@B_&S4U(oBrO%!Uq-7`h|}Fqpa3X1W)KlJf_XTI{P(J"
    b"gPimD_#Z$1(BU-sWFr7Tj09Ew(;~h|!&Ydck1LQtgYEY+(+M(yc#;}HfP?3?&AdRgI}aen@3Md0<7ln6;NKkn*xnY!^U21brSiqB"
    b"az)o;i@?Z0!Z*yA(*0Y>IyfZoyDpme7uP6S??L^+If5XA=dja9XF=E68%EuI)sArQh6#8VdJTe?*FPD(dlTrkMlNcSSpAKUw4j!d"
    b"T?Ec$F?o{J8MUHBP-&=v+}-CpE-fc)%gZ2{>RLGBBXoYI$^1&DUhAtl80mq(jigZvTAOR6e}TIn8`}iqxi`v9ug*sYj5=BHQm;b("
    b"QOJzE!of@$!CgNKl{2#q&I}=FLueN!`7^(;7t^2#Sw)ijzyet-<M9=&#f+v~%L=jJF5Bs$wB$@G18wfoERC!?d~wM(UzchX$*A2Z"
    b"KjHrN;D<-}=!#2d1)u`4)ZJ1pS6ZR^-pg3Mq-2MT5JQZh3=&;KUt4s5L$KE2Z_d52x`=IVE;%q3f3$z;b}dE6T)G+RE?Fksax0D9"
    b";l|Xjx|wVe<U6l89lE7lDA=f41`CB`psILu`Mw#V*NCg`AK<CQxB{Ar0XwrX=Z))dg3dEX+zbVW)p0pj_4{gf+|SS+^#Vgnd*hU?"
    b"*Lbr><tFtpC&eof6-ntp<RfeWAS;Decy^)8Z=+z`Vh5&)J+;DoxMw6G$qk?VenO1Py{1S-G}O(Kj}>bET4c&ns4hZR)6A?1_}WHQ"
    b"SGo(6C5#4A2D${DGU>y3rj9qr=D;LmJ<Q6N;o-=Pm}thAxWqUJ28Z!a1u0zUAT69x%hr`p{j9kb*jsEDeHH1mC$LBC5KM_1>nux@"
    b"oaSOKbnF(5wj{2a*XBW|vtUa&HMFqE&X`q|^biq9`XDe?1Mw=%tA}M{I@-$FyhVF0Y*snnLHiKrW(NtpK}W^N>4bkd*Kfmx8%64}"
    b"2ezELremg8KbBN{V(18Tu0!48EE;7Dy2*k_t%)CVnx=*kSag_Nt{gtkavfl%PjR>L{FunzcZuCPlgIH!8@J(k_;G?Jc300Q6qN_f"
    b"R4No$|GFzvU8M);_|dEl7nW}nr{WPi_u*vyR7kF6dhGO-6#mObA-jN{=?{(%q`z$;jj63wVbh^BHNmFUuK%opFWK2hlsXmue0qlW"
    b"q33V{A>mTV3+m?ii^f6t-yoS^3k3CEaEEJ^r@<yyv|?!Nb~~H0VJY;_StUgr$|s|;pewjQmPhbi+YG6a#u32qQ(DQ-3;CxU-S=17"
    b"c>4Iq^6o)8<aMbEZBKvi4jKB%<Pm~&hH<~>i)+o(WgPq?A>FMa#3PG6ZN}MuxQyhq5NHworYyf>i8#jaBn?4G9M+nu4=kXTz?h05"
    b"ryStx{FEvH=>&tZ66KX!1U>-<$f9^WgKq5otnC~DO-dV|UaiAb90bl$O`e480-W{H)Sfc1=U_rutW|8)t2T{eS_{ZVJJOY)lI4i$"
    b"EI&Zt2qfaaqUkafTTqL6{hmg^d(uWCfO)1<{ppzxPfRmFy9yrXgmP+u5ZM|6FZs9T#w0+Q(iyml9|BU4F4vZnN|FN~U<~6IeZheO"
    b"kj9)LzTB#vB9J`I%G63;;*r*4MYM>>wOrMWK!w6|$4P3ppp2<qK?MdMhyq5{LX(`1QzRyX(~V2>KB$P3iPL_&2PU0x)VsRS>yN<j"
    b"rDF2#GCGoL-Xoq5Hl!}2thfQ`(K1S*E|W8!WdC8NTx%;e$(Pe$pGn}D1|9&rlk|&X;Z<b)&Bj^-8o=!zPz(ZB4hfm65oQ?Ukgl*h"
    b"9UJFWugD?p1Gz)>C#tk5WVddarJA2Ve6-S&ds7`&#_^q1QIwK-hbEVDH}!kV-mDh;J<>a?J@Uq_gW@0JN{j=)QJ8qxGYBz#3E@(Z"
    b"CaGehR`%-hv{~LZqxSL8&V4;r>cuiu^&3yxFp<?kq&OGq2b*H|XlWA><9tr-kDaGM&BTBA<%UN_w3X5Ui^@cdawn+f>$|pRbZy1Y"
    b"M5Fuah<w|>hs(;TCL6j;esC)4bDy2ePeo!=xo_lo?@OL8sWy`;C89>I%0#u@UbSP-QAxNa=~j$KP4ig=xPvAXpoBR{d}l*sDCIB("
    b"t{5@s{L<vB#b~iUM5&3<I2yv68$E-A*J;qPVp@;W-uI|zh5~-ua3ct!qfaStjEFJF+F!Bo6P>f}Dk+<d>?_Uzz5cqmJM{L+nlLYV"
    b"uaCVa<w4}1bCB%oSx!35wPp5Di|c#C110=(Ki~ztS9~}T;_qD!N)JZ!>&_gwG2`JYmfTOw!$H>&D!-Z}CNzNyk@zNVz<6s0bUwfP"
    b"?ysw~LEoSAOd4pCXu89KNySF_Q2n}h3FoJRWCjbgK5${&9Ras#YhFU(<u9;5eSt1hTxEwH)wVqaITzsaOeTs6#dEX;C)c7|`Eo2U"
    b"e><&y6!*Jh-E!473fnI%49R?*b9laP?@=D?3bk1xjUZp<7EPhX9R62ZY1ufR7`#B<WD<EPQtLU9gG}j%h^~nd_9Zl)o_%D3RH>+T"
    b"PNSIrDs6i-ot^&z5kyhyuAA{NsJv~GW&HQ1Z4kI~AChkaY~j)fvivn7QEkgQ{tdon-zE>vtmhLa=?k_xbuI_7aY&AFr3n+`IqlWr"
    b"A@U0Pk5ctH_a*=0ULQz<Si><qrc7K7P+7>Sh*Nxbt=b=qYSfD~0ZBGmH`Q^~xk3{fd9W%y`)4UHqwTVZVD!9|@W=umOzSTs46t8i"
    b"J^H#zq567F>eSepl@&+ckvneILMxo4a1g`}+XS8e&ZX?WZFLdQHZyRAK)4Evgv1J6q`{94ou>Bp0_vFDOs&x1_Y!Er#3#AG-5q#G"
    b"6MSoEcdjnT_AWTUYvTF^bKW6Tah|bC{g&}LlHDIlr9dCGJz9mCp6+pvuf(K#AxihI(RC#EO=(_hpAId=?hra_)v-!Us5W10M<Zfz"
    b"AhnmMmko*DZq-DOf0Gyl^~%`Bg=5|3U-)2hu*E7Rm@3LS{CQ7J&qAcdDDg_vy@lth^Gog={y29URf!=JDN~)`O+p$w3k>g`{N+rh"
    b"6CND`9wGz-OxQ1xf~g~5YqE!_>02I-?W0+OTpGXMi=Qulc(ni!LchvWEe1r6eK{?sRRZQXjQA){RAFV|YAm1HUybWM#!2`z)_^Ms"
    b"6F29pIh2`ik+MT^1R_Web{ldGz*+NMX^5E!sV1Vi`Ksg<?9rD8T~pvZ%xAzf`&a<0pL(@s2kL~YcrBHP%YN91bq6Ji#*3|dX88B~"
    b"R>}8A8pzcH*zcoTClX)0jIkMeJ}>JEhAiAeJG6L!<^{@?yRw*y&yzsXhwo}7mBcC3kHUO@AO7~FHkh3n0Y7TdqcH0Co?EFHh_0zo"
    b"Ny{)GlvOwtIX%pgy^W9qf8cE097gI45$T^qamZ`JWsA0_DuS8L<z|qL;cYnlS;qQBO3dC*Kmr6rm15<y7yCBbqp*R1n{U3?W^aT;"
    b"$n(J~GcnA<4)FeFUZlG3D@L=j%MKrflyqA=joFDhemX8ZNgFqPyt$YJp#^9l+`tC#3ozumQ!MfyWNe2q`P(q6bSKO%@^L%FA!uF("
    b"e7Z~ivT=GahR<<a<+Arx<cAmZoK_vIIX8&y9ZwW94o#WAVYfO-iHTO3bR;7tWq2FQBWZGK?pwgPOr)pW`8-<(q%}4(ocz0trXIpm"
    b"<P-SwEPS@|NgmQJa5bHaQHiD0$JYSltpGJe(Do*Pq}t(!V~a}S*(BZL6%7IVnjc}NQ|Rg(tC&L0=5y7$oZCbu!Ei*$rx8hRR0(n9"
    b"Wq0fbbSKl7n}GQ9VZcH{yiMDUi6s#}l#MedyN$>w-dAd&TJD5tN4&cGWI=NWb`)mpt_@7D7l+M|2G7n~5S|szr|P}fwza=j6vh5n"
    b"&m8#SN)=FPf})sHsvZfWL0%~*vQ%b#AEsz6H}Xa5{;C}8u3Y4j_z0vlJ0f=ht&BnsKmXZanpEw=LCd*K$g)#<Y50XoMLUUeLcg1c"
    b"Dncra6sa7YxmE;pFGK|bzZq5RS&lcu{YaKF`LgJfSKW15P?Qomlm!ruj1+Aj(ZSgKvQ-1|@jrF*wAG$G==2==KxE|RY?E=t<vGeW"
    b"&ITbYWL($F{VlYfov!e2dVl-gjkV$$5e{DWE)TWs@y$)YPAp5EX{VZqS_Jl%HHMSOo(FqV91jpY6^^ru+X0-;6E*;360Mz5t6=Ah"
    b"_r5JRrjcw}n@p}9_nAr?{xu^RGb2cE=W4VzZ#a6mU%=j-tX&gMXjv90Twc%_i|zAMN(d$#=XQF+RmZg~Q|$}kKG2M(g7&>cC*z|L"
    b"U^J)HtLXMUan7Aw9EQql9$nOCtWD(g$;EuUmx-|XJDk5S=A(0xYF22>$EQS_53>dUY|nyuX9b8WyBeLQ58$Q9{TP~>cFm`w&Z%7G"
    b"@5t>dVzf<77k>G!QGdIutmk6-glTI+G%pjUDd>-B?p01Lx(XD$dodE*oGP>h@u!BDTv+oD`Q~@}Yo&Q>qa)$ljSqHBbyhRc*)>Un"
    b"M;GHqUYo;=6p&V|-hS}J>=#*l()TOdN_LGGhO0wd=u0Z_$4GN{rC0hXl+vw|1jmKPKyizFGZUsX+Heg_OjAC<my$AgX(;(T9@}0X"
    b"n(E1PD0acX@wmxDyKwVygDMPsYMcx<%Zh(d<7l$pYnglHa$-q#4xRMKbrQSt{Dk+}d7+wZW$)@S$6KhPtbt(H1+6FsrB__IGPpbj"
    b"**?!FcODu>i46y@xv<lAUvCmCzy$~L=94PU(Kj+g^%&JA=?pVF{pG-ppd}ef0tK;}2I}78WZ4zt|K^k@+=yyK30mh3vrT9BMMZ7~"
    b"^<7Nx{c7*zfR(lQefpamZh+({;#UE^5)<zOjiSH(+*)4uH224rMkl`$`4VnyjLZ;a|8@A<HDZ_msteU)VWA*+v|pzwWCzc!Y(>nQ"
    b"{?Y+-$g&t3%(N8fIEEu?eLidQD%NoY%Zkst)}@!uz`nq7L|Lrh62ars2yuG%V+v5}Lx%P{$?nj{6PxC#p=G7|SL8WIYp8p2%g8e5"
    b"NzEZuI@b9>{KMFlJod?<#N+$V;rU6DbrPO!I?;RfhL~}QMWuDecqe#l8ouO7J2n}CaS1mT=1^Pmg3|P@hiZ$yiMa4H|6d|T=t|kW"
    b"%$I?i5g&D`2djhm4eyNdq?HdLGZy<ef}4s;j}7pXr*Xsx@|BV|Shy&v_Lr~_6VrXxnp3pwj>PI0Wa9w%Okyqy&Za5>Vu#|dnJ}Mw"
    b"e`zR^7KyOWIfZ>0U9q8nUg=Qd$-V&4S(h@n*)|3yxPmU|#n4PPlLZ`n*gpPW&kuFu=mgl)v7tj2TZS>X3hj<6>vL8T>1E{m;SPLt"
    b"hs|;mljTqGw;?`xDsPKC43}}Udo&4I`=H;UJ6fLbd9%e?UQ=#6MfIgW_T%M7EySYDKh;O|*j@KG%7QWmgqwW~x?AXjMZVwDZ8Cgn"
    b"JrZj<6x6%eAB7P)K2jin4L*DBQ0d<q;)BT0G02X$4%WecmY;GaN;Bb^OJ@S-!#@OL$K5n$32+)x0g|NGKCE)W%=&?yC!g$XvV2d!"
    b"JY(=_+OU859jlxLne3veb>@Ufknp5){ha((ytpz?w5Eh<f8-0(yP0^$_;{eiNAlH;rEs{R^y~r5i44QYh3=L#SJUI*O8hSRgN|-T"
    b"f|^xy86Zm$(Cyp@0i|#ABXH7Z7?9DoA&suKMbM1Jyz36-$r6Ig#mSBAd$~ZvE$+1ncXVB#!#tItIX=Ogd0f&xY&Z#d!+U5i4|%(I"
    b"kLpeEL~|{dA6Snkd<tz1*KG|a+o1aYu^fSS*R($N-^EZD+3R$Jb;6UVW7uELdE&1&9J^E7{ar|qY|M}2v#i^&vp5fbCz@t3W%dAD"
    b"CE}&IWF-9QP5)f850lz$C@k}}P=hSTz`P~ga-JC`-ddiyu;1$6qC7%RG?Tc@86kL)c7c_0ipI?^J4K!6l*^Hi!GKgv&0G16pGlPh"
    b"e(&}%@M3<%hd|5uZ#=m9sX8_mR5HNpTkzYt9-aOeK<%fAZt)yHNWGA;l)W9#D0IkH97&>3`6k0ok1D;I^x4MQJ#kWdF&>^h&+J~q"
    b"m+sm~#QIV~p|&8avRF>Nqr1hX;CmgOLDHSmpnw9beA7fyoOqUPXiDA7EYf~u&-f>e&Tola`;K$~dMU|Ip4wl0B4#tqwD#2Ph=Xij"
    b"Q8#Df`BRso>?edwS}~d$118HjwvEIeKr)fABvvOq78gBkeLr8jo}{h+Plq0}m@=30$Fn8+u{Z*3ra`UP<`OYg4Jt?%jkmU;WSBP3"
    b"s%K0O@Ctd~hj~h~0a&K+-*HkPjTN=wr$Y0ALha7FZC&Vm@QbK4DzC)5|JS4QS_fbC+O2Z|Z4xX91ANHwa!6d}^@CWZltBNyz6(pq"
    b"#BbJ~NtQ;jmYhY#NRE=1mFYP-9h_{Bvx9q$>4YEJUuFpRsv-Fn8Uh3u3Xi0ikS@4MMcY|Q-X1Z<<Xe(PBi<L96C9C=J21i>`iWt1"
    b"X2O#L`L^_Mi<Kst7Y{Oi?jM7KZ8p_Z$EE>sx=jDDcaE}zruXcj!T<MCMNH8XD>wAHr^>d;rfNzh_~h^@ENp0N9s$?VfL0R35g8%0"
    b"jhZ7?qzf750f=hwc{6xsGeuzEGD=V>#}xy#K1U5|Gz40%4P^~kiLBWYJ-YL4p4UcNqpr`ZPFVB>f7RKlnTAz6kYtN7p5Y;%dOVuF"
    b"8Jr+bv8Ar$;p46>t!PL#jJh?X?KROMVi`WJ8Wo)Ut5nsPb17_YPsL8<zSilF3@b*HxwIupmHyyR3V5B!m05}jnL%~}RXW25J@4bV"
    b"KJXE9-aD%vgBR`3`lURb*wW>FxeSi}yK75-0Y{#{OPA`pyrm}@o;#)+D)m2E0MZ8!Du5BQ>sF6RpF<%=fq$r6?gJp2+Yr-A7q1(|"
    b"8F8^Xm{7KMMmq(>wMdw}u@HPb{Gs+<FW$jBuiw9dk$EA~x^^d!?T$8&&Tow4H-R&Je#URK1#HlzKE8n?oIGf@1ta!cS-#t0!fsHw"
    b"10LoF{`5ueZQMmve+hZtA@~cUmuTzFN577$hfLWp$;!HH&v1KG?`t)9F4;`YKJ)*J-DmKf;}Ctm`OnIknWp7;gXmZt)gG_0-8&YG"
    b"wMfDdGaq2~o#=yR!>2k3AYk|)V|G0<QZs2Odi6pzNKo(UY@X#;;(5VkqXN-aKXgldtNnxas{>@3|BNm0()Pcp)H&x`ZO7{F!7fKo"
    b"rjAwsj41x%B3*C!sfkPKrcCh6Rv66Y&%`{s^4mbXM*faH;&5r3164Y(7!VmOYzx0#29~zN2)tr?ww*ns9s@lXXCV<58<aI3P=+a^"
    b"Ke>iiLUtJsg@DCLKcKdm5=K(yw5fizx3_jDW(pLmDRm=CuSG;K1>I*G?D%&5FzYa%*Nd?-1c?Y4y+rS!>g`%iGQ~MbTc4gy5`PS<"
    b"IZ<Yn*I6lgR2beCXhd<tZt+EUEZHxVLaBd`qyc*hHNhxE_Bj1O`}^9jhcz+qV_Z3jfj|3H68){WaN>zVqy75Hf9NJTx0;Ja=Sn%~"
    b"OM}&7`jF5h7Q_+DF@E|89W@1=&v7)30*n0U<XxvLVlP5haW+%N)60ezZ>5Q%EUkUWSxtF{8UhI_8JBZx0nc9moNlQGq^(k8K!X3<"
    b"nyrr~@R}kSg&5p=hzsaVzlQG-MD%K}iu+i{-t|$T96zmqR1qn-9w!_ioorF8O|Rn$Ul4+vT#X}A1E7JwWC$oTcrc;6_d&%L$484p"
    b"+uWGj=HI@CI?)niG5*Z|xk`j%eZL;SL}7urbnZ4SE!D)V@%qhEBl~Qx4)l_Ho!*uH5MQv#L7Ek651S6)t#o3v`C|KqS#>~SM!4sJ"
    b"opUOtX_nO;J`G&a?Ym<M)iiB238)YdC`1Um!5%x7vXip{4Un!Hu%RCfgIhA4HCv2Y?IpANT0klJu%T_`nvdIRTaF~<IZM47L44LY"
    b"H4nlx4QKVL%8+mOWkY1Exv{nI8l%b@4o-vwEjtC177mN!!LbO2cIUz9jUe(Ut2+VPoc*S~_eyz4Ldd8%*6e`I6nSVF014xWTBA^K"
    b"X{cr<!*xaG{r06amJINQZ5(_8rrClpvtkJAXPKKDm(w=WbD62k|9Wz?+8z+r)@-a14QL3}pt@J!x6=wT+uCr~$%H%Tb@E|fo;lXS"
    b"!M57F>#~C>aVDzT=O1Y?utd<FQxq{Z&~6@FEHL9J@0TOz1EXa9PZ>DeDGJf0>(<h)k{juo4^Lim<j7NbJ%`KV5zpT2549%8>eYP3"
    b"iusSLF^j`%GTc*|tS8_@r~v7{-C$3!BfB<kxwN8eAeMIO^#h@({zM0ak0w_A{50|tZ}1d=W*a~Lwsuvj=766b$1;M$PBD0F+r+Iu"
    b"%0({sr+t;8SkHY!%<X?J`VU}5EEjRY9Zi3&CU~IKW;gj~zdPP-ob7Ns?(b~gH^heW&KgV?3F>oghDRwCdLnz1arrwzZ=xT+zAupJ"
    b"UlE^7jnFlS9PEe))>LRW2ceOUFw(}K5PtGPZvql@Db|-ie^Jz9xZ)q_75X|em-^-J-}R!Z2a2&a^5p<wjq1$7>)*x*p(4C(zWdUH"
    b"48!N_VpC4=&dpX8J)FA>Q8dL2UPT~$;4r>Q&TfS~jo*+kf+;(^vuDBXAT)@t*OJ=5@^w-LB@B;={CIu)lVdK&BM9eER+p+TZq(&r"
    b"Ad^_obet<mxA`<7>;kr_T(q6a^Ti=d_?r)a`8MEAJo+=)@b|TjH19pS?YmV%pVZjo9hADqC7feQFV5`)QU*1Zmmz6~{WcAodZEm2"
    b"^+J;u4~pU?@}peAJR9W-?Y0>@i8yw~+w3o1uR76@OF3+J?rx6~t(b^~{^`rl*hwsy1^wqfsH)Sr{**B-y9Nj=O|))!a#E<aD<~|W"
    b"xJvL!fuh2f*o2%<am_Wkgnn*QiVqG;#ej!?;k?Pz&8hyH7b6_&G4;Z1W`=p2enO7~Rau4w4SICtqj)=gD@iR-jSJ(&G%bnWm!(+j"
    b"oCHc_t%Z@v*yL)%u3uvl;~~>lJ}#rm>9Lk8aL2rQ3L2RW03mRz_#^3>(yEIG=w@>)%NIdM3-XHt%QY@_;^}1<2>5IX3ea`LGNjhR"
    b"vML~5wdH{bPd~z#BbECQ0y8Ze6+G-2C~pXA7#uaJ){jYK3+phT(sJ9GQij|TO#9VFx)_cbGOEdZ7QP&Xu(jkD-mj~~$2_6CHq!=T"
    b"(<Ch~j7Tw>neF#v(N^*U>j00%+7`hBR12*%z|!kqT!+e+iI9r<$&BwVo}LVzJ~0n~Rsas)!eh@_kgS;0%^B<>sr+Ui+YywWR4AKn"
    b"offR9HGz{Mm&h*Mg{Cw^^;cN^-&UheXnXmHwZn&4-sEhy7`VYvPhU_B{t})JsKPtgn0ELgwTQ*OHd-1{Cf|^lG!#Z?2Hojj!81Rj"
    b"fayGzU$8*>`{YFB@=c6BGfSgnEWG;Tm^!9U=DB+m>wZF=GYa5#j}K{?NfS_nWVXV6Jsfm?Z=w7stfC#Fs0`Pg`E#4_GxXc(jCw>E"
    b"S!L40yJqadWxQ>B-)YRH^9VCGicqL4uF~iA;_xf8(O!z2rD^BIu}ZoO>p4-&=sMM&xG2vDEJi0-4T{cZZFl2c%h4Ol>r2I5m6;c|"
    b"SH=%xWR3Hc6R3h)%U(WF0m=wv5_R|kLRvvWb`BkX{<_-gl{kD(hU86snY`1)o>#4!r!2ufh_+O;up*;)(I9C&9Y@V}h~By6JC0-J"
    b")Ymr!0ciMX)+u{$1+>#cGy25-zyI{qNuwd1^*ds|4dGLkesU1-o;k1#{JyX#uAHwX2syda92D5>;%9fI#{J+Hkla_IFJ%*ReCwVs"
    b"GGw023V*%#2v$#Cp}ITcHO@OS0jGfo4Kb^j<ac%P>R)QGuk;|>o#`{TcyZ1ehlJ8YyMU_DX0OM_q_O;oq*q<R&dZujb=sLeeBE0x"
    b"lB#2tK^kU|ht*(PzL;P+`Z5R!fU#F%GcYQW4Kdet0_=x~!MW3RjkF-w;Z#`kj}P`gz72LNC?<QjoYP#!Uh2}w&A56iBiGG3trqX9"
    b"->i2o=w{%f0Gey|KToliPuD|<@X*&<K_`JsFCZWJAmNamEqj+GevC<fEY@imRK5MfM0=nLR`^w_be772z(B_k<{~dYs-TL=NKDen"
    b"W^7+s+){y%9FDc5jw+)+N8KbgfIXXT$_5~aiAuvd6BhvTri%nwCAbe`^onNgT#S_g;fEG>Wk_djj!zxn`IkKRaek(bt{HiX;N+PI"
    b"1g^b$rs?&Jw_F9T0|1u3s%17tS5j#v#Q;lVuHi$IGF2AIjxL=VMh~rooLJww+GnZI`0Ht>-lqR->exrWPgPAnI}{(3iC$4piZNXz"
    b"K@v{wy~vlP@;!O=dPPl}cI*h{8g1;8Sxv=z2kikt(oq9!O!w;Ir67)m9QIxz_cnRQau_;Q6LU@!G4RS`!pkeUB96+RAKM>QvynA*"
    b"9?mWUj$>tY9qgnX(QVY<98O9jAN_n@P@fAuea|bT8ql-a?f2SqAjnsPXBFEFU%*;PAvcf|gDkGAXSgD#stVd>g~%b1XB`*>1`0RY"
    b"qC}>G7kY2EV5TdgC=Xr36euzS?no$%bos1)DBSOqm}CsbfNlM{QaNfP2+YKy;%YFyo^49q$4!>>mS6IXK>Sk=j6wmb%fbN`&d*5&"
    b"2!9HGEU60`eL1lEx2}N9u+v?8mWGYq;?=MCR(3nb5RpIR5+BNFmSNqz`w9R;GeLXdnV48i7|2d~BFFwN^BS~jb8u@T6b*~B5fzmT"
    b"GH*o5n1kf?f=T{4NIM#jVian22G{SiA3Ikoi^L$hb^&MLGw1n}?szB|)*YKQ;jR@!*EkPtHZv~^W{d48uu|C#kn24V#^e&)k+*YO"
    b"w&nvb$?mx$xN(D|il*Znswv49c*<{nXE>59mCNU2vdGv`C|0s`q!T1h>yC4uG;07Fw@SyKDDXzN8bU^_R;lE@2gB3aKOcbKkjW}V"
    b"5xvDTu24_b-Vkdw|1Q_FDcLP&T1l=*V49E^2=7r%BvrUE&@20K#Jk1-<F$mS3PwBupW9i>O2g(-zlmxGP_`xG9UDF5j8M2Ej{YpM"
    b"fO-;F7aq{3eVs^}*t8=J4)x(q!4{iLI6gzT`FI_G4<h%@PL9H0wTXfA^Zw`ovGJdMgLj3`;iGV1NXbGc|13O3b=4EEc3hS492Kq)"
    b"!R!y%ic=4<7KN*Rd9lpoaow*{3j0d}1z?c&hR3=YOt5Q(1dV|nc|kmRy9mW-D2++s^o;k7v)bQD#z?C_F*=U(-99sn)t0HPnXfvD"
    b"PX;t>unV?Y#jv&r05c_}Y8cZS2g`p6$DS#W?zGXBf!inKPTX-%Z4maw5ERxbtjo|dg~ODlI~V5=EuPc4#;A1$&l`cbJ1$VCOHT1N"
    b"69h}~cS{1eYBYGGqGuW14(?j4F+n|=!77lG-D2_|l+lTH7cMB2b+~I^6digG2@lQ)Gn;096E7HDTEGupO7XXV(=w<{P!|b8qh^V|"
    b"r+zMCp6H{E^>%;{gw~y9wDUsud>_n3C@*ZVKr=2S4NdJG<1dBr66q&AyJ3=PDHcGD4=51ca|q0HZzhm)B@3_;7_W=Pr!dZkqd|s)"
    b"SRM9@d<{q=sd=2BbSt@kEqpJ9f?`-mB4Wdmi7Pd{a+3U#(aW-5=2)Jjo@A{bK+ZNygA(jU?&STD_HR3~|F}TA*5NYFvx_tO5yqP{"
    b"*NUZ|7ks)f5ncQKUI1Ax+BtQm<-s>6jza5F({k6to?eJbkE-c`RHk_Q;342BB1L@MvjNlhId0!4X`PTk$R%Wm5Xt*fwMMK0(lY+^"
    b"8!g@}GE3Z^=BF>5AG9C4IBpGwTMuu<`RG*$1gpD1X~P6<z4M8GoN47z;AoW0>oveHD<*J$&&~}}3>3ZjT1QPt|Jc7Z<$_3fR?Ykf"
    b"17Omg_Vq>jmiw@GMt(ZbH1W!a4Ce|{coLZW6srHBVv$5UI|Vs8`vZAXyP*SuK<;qQwVvJb>E&^rgqVSVyDbpribS@1*0g<je0+UT"
    b"ip5-i^Jx$!6A)PLUX`TRz~JLh6;x(J?|62xZ5~#Vb0I$k2pz)bQ6E3F^jrd3izOi=8H(K(mIh`^&T9aHh-Q)ux;XA1+^b#oL}Bj@"
    b"3~q-Lb`AE&)n{Ew=mNSxZ>T3r-Oy~TrgC>oMKAc8pO2Tm1YC40vP;{jy(B!ZZpdIqxh$W`U7RlsiTg!d1m44A=1Q~P;a@Fbr7bM%"
    b"mr(|%=vo?LFu-%_%NklC5?2(hS2h%+CH7R$Y0c$n`Vfl*3n4;I_7B<oM*OfOb(h6aTc7Naw350z5VZ4V^Ewq<sv8T1;R!O`qa@2w"
    b"9D_oX1b~yJc5CUGSZn>IimMZJaRFnSXk3LK0s8A$KQLT$$FH2h0Li(n4hIVNAr!wCf_+raXhdfx+X}_85>`0XfI|Ta+CfBWd|By9"
    b"*pAaK$VW3t4&V{6ht5Zv1a8v!x<TXQ9p1an?LH_nKp;gq@re*P=4;=H|09X4PnVc-C?WU6M#9T!+5ysqUd4NWsU6<?Hf&4p==bTi"
    b"0KpV;0piZ0G(+q2t{fih_the^MGHnn$D&(Y_i?io!trZ?s@Ffj_2*~AB}OSGxDQ*TVaxCWMxt!x_)lwrY?f4qH(eq6!zvsJO(@f7"
    b"MZpxXaM0MWG=x!Uf%kgq9^-h~{0qph6w@$abp>>FzqjF<V2}?RL^-4Rzri+g71qbft-Agt(JTnKoR~8ce*!xIe4N!Ctf9PUX(l)R"
    b"ns(cjprY8u<;I%lp=T-``{o%x&a_6$Xs%9gW@-uiaQ`f(w(%ulql_IA^2hS7aI4H42Qo4pK|L!nKjD!EnM#Otv13Rgv95qX_Jq|^"
    b"NqgqXDejpCSfi|VdHF|UKNX`91cg{}+C5EAdCwGMz9B(l*o|8ECW@T+Wt^p_6ABYiG##SoSg(1b;O1a3{6JYSKpz%g3~|-aHR>1n"
    b"AiG}cmwKRHv4^e0JRA8js3T|;@<7(Mkc6jw<B(S)4>@IG?wt5VPs_90L&(x-$XyU^0y>h-+quCNT6h^bR<9+?tG)nK*DsSa!XyAI"
    b"C11^vjCo_NRKpAu^G@<o2Yt2qheL3O!pB#l7F(}}{*|cGu4w2mzxmr(wICY&p|^39aTNzu=E4p9zGiIo&0i9W5d-nd5J(PLA9dib"
    b"8(T;a?7rpxyY9^IS+)OjQN$E;qq(j)M*^qI>vALY$+}xW8z$SjMs__-l61eQjoMr1{O5Tb$%P%ZKu?CA&c~w%R;eV#fIBL+R?6Y1"
    b"U=-h)SbSWcTr+b&2aq#3p?JaZT?YxK&b1*Fg=1pQzN;XbV@{du6*d;$IfI}n2&+i?_@5m}Kq$&99mAFui5`y_0V%KAef=UHtc27x"
    b"+V-`QvszA~`UgU~BlV_`GqnaV12so`bB$YmxIU4Q^)b9y{^;T|%vcS}IC1l)e|Dn$4D3aROhlJ$N91Ito}jK{3(tiN{;~s-V89{9"
    b"v2`9H(=Z(jThdB~gQ6;vi47a*@?s-;9Yaq#HMb4yP7!o)UIXK=^XsgNN0py7z*YqXk+;8&)TYj53?2%(@(!w_%<Y0^NA`}Ip(QN3"
    b"2eMza1CEzw6J2zi|2^QDZ-o&EKjcA`2}wCda1omAQ>#%Xq*62z5CWm+&Fj3huq(dOQ~!&RQ=MF%=8IP`60RC{6!;1&Dc+I9k8MV&"
    b"1&q;KM&$((ONgq3X0IjW7od-<W!ISE^ED>5=#fFs?fEyC9^zVk(^Fbth*R%9z&s5awzE15Q-aW%$&TJ<s3-5;XZl`r)5grY@ZzrQ"
    b"U159>62`8)-({~QiYh+|S=wqW8udmJ0g_+&JLnOYdH0LcqcI+QeyN>psLWUQ(KdAbdYi78VJZHd<1i<qr*-H9bzrvw{z0kW=xK_E"
    b"_Fr|xD;`_}#mlHRPpM^_O!LNpW}M;B5yj!yyu|9mq>vBL8{fT|mzBg%TK*By>0>m&L_MG-`xNnD()q<_pr)a@vfO}}a`JljVQ;Za"
    b"DtIh#eN~M7fz#j&fI&{^z#s2TZDOM;RbUFeJ9SNoKP!@=Ni)q3at%i0c18)l=Qs$>6zAMyh+QFpMT+Q)z^~@YRYOnQs<_SL8YLn@"
    b"I&NoWv`vK@V=Sjjek&Fu?neX_-O@AUk0!O^{V>w$sh82VIRcMWQPu(1V0fdKXX+x9cQGC(2WqUIOhDQZ1W9{52R{|}m(jiD*}hVP"
    b"&}9JUP}@jLQCJw0Tq8QU@Yp~;ZJ#3|Xf@3p#aCI7&YU=gQN4WZO@-^LRj%->3pyB`P%jy`Qp7VrMCCf64pNB`pKwhP^$sQh1QD<y"
    b"0ygGf{q2oI4;QNT1#Kp`j*yoVnm47B9}*2CwVPf`oIp=$;=vRUptK)d6N1sfZT0A7$%*%^=^Q?(2#svkm9}br-gT>V279a^O#pOY"
    b"nh7QmUxTZ{6B!ukOXNsJV02q))bR*1%GMc>`G7`5p1^`$D&n=BF277EaT{{1NxqtY6VN$Kl|ay?FEkjGSCECw<5Es6F-|Xmj2{Zj"
    b"9-zUUNdXQzGT^R&v5<|(Ins|Srw7;h2jg^=h;KPu_tMN5qQREt`%z%a`EJbK!MBYW67JEb9_ei8)R$d{^P;~V>J44c5D9!|oMJlk"
    b"z`GD(L(`Rp%a}z3u|&qCY^9A24bVh&%PZ;!g10-4LEN`iP3>^sc;Xqm+N$lFijm1iEtwwywg@|%(^L~lsc0Pg!Cu%ObWHjkAB=a@"
    b"j8zjqeN7A3V~wbc)Ab?avwG{5`;Gaf^n{I$7V%AC3Cpjy7h*&Aj1H`OuR<RJhdef4C+a6T_c&qoRf|%UP{yvvc>^hN6*3~+=m@i)"
    b"6|ALvMmV{F$%nm>J#&*sNmh-+umtW!RjAr&JG_ZYzP|WW`ZGrt4ftLX6a9$SVSqZ|1Tir)-t2=D1k0orSpM($_i4<)4PPEn-+WCe"
    b"cm=J(EX~e^!J&B)JIjK$?u)30i}m^>ek2i4SAicAZttQO&)d@!zLfYUyygOQA{+B0!YeO<5=j^?L8tqH3CtTS(J>z1P8)CK!t#Mi"
    b"U<r8vo*KJ2ZeXK`Z?p~Ca*ji2l=UWO4a7$&DokbQjx^`=Z)*HLco9LaCG~+W155bBH$3w^ZK`o;v2nLd?W0?QTMjFqeS5hOCQD&h"
    b"l18_g;QO<Kh4W#$3r|$ZASJfA#7RMnApH}=*$Waan-&No7XH2O2%p{Xtc3#xvpagV9K=!3rlwdqjsm0xm?OwW9y=r3O83A->|1tp"
    b"aj>elbCcnJ-gqO3XC+Os4pC}}+C3LWJX9j?uuZ{d5W_4_@{FP2X{`2iB^#^G$%-(6f%y!}tM;jsv%(*=uXtVz-tju}f&*r;=(lib"
    b"U%s%Lu@Te+2F*l~+v0ae$C1FzeZb<=HS#hzBZciHz;qId3hHfg6xr*+`7EP-(Keh)s)gAq6{>Ny+JvgIE{N&4KcTL(fkJQxognud"
    b"AVLNO^R%t2NnRs}95!Hk5UJ^6hfUI2X*~%NgoV^0^!f5Kyw&h1n7!jaH?I!wUSbChicnZ!O@fEFQ^o0d2a&jJ<vci+MW;f-lN2)9"
    b"gX04)XZF9MzsR*zY{33pjzuVR*Pp^d4|kx$F7&FtD;KufZhYRQJ$%3^X0n4-=-Zhkds2ePy6iy<4z-;YTg^Sa$@!>^nG04%DhGdJ"
    b"m6Ey&&9cRvOu}MeOq1>ZWRi6w4>(v2@j89oH@y*ZSO98P{D0u|WzNHrYrEY^xK5c%rL4tF)5|ekT9+5g0$xnATt`*GaOKoRw_3|t"
    b"*0W*ZA4ZmZ{cQod<kU46RafDV7*!>!urgXe2=VX-9pfNy=dLu9i?$d@6A^V1fQa0{9ly^4X*obOD~x4iKgmPdl#76CXgFh0{_}J~"
    b"xWIt5<Lsmr6Kw#$@#_oDP`Jg5bV<c)DnISSs;N*X2M~qfK0ulfk7mF*U$5W#bFK*jet=Y_lMPKw5R)3<y08Uas0vJTDTmFIW6vd0"
    b"DTPc&ePcH9MkPbCUl~d{jb?;22?nfAG0*XMK{EnnPp|-gL5bBij|tzj=*BEPQG#>5#Sap(m7galC(XezdK4Pu?HQy5j|;QSFp~}o"
    b"SK@+OY6+PzY?U!hpQx!J#vO)fxoaL>6`xVZt#wPa7|iK>W>JYN4_40_s50)0+!S&6z4srwtkHGKdx#lOP2@ZmPyU4(7y(tsoGt0="
    b"j<Us)?x3b{<Pjazc`h5gQF`5IJdq*>gY1I#q`4CSrwx#jSe8WczJX^8lxll{^;m<yApJw7X?u!u0+?BmU|;A+RuW4<!y(GLXm2TE"
    b">=Y9kpwS3m9wM&cCdm_*f$_wWtMExYNCOw!6mtaMA&A(r*u(yZBU9KA;2kF?%qK-GE5_r@H*QRc76RGuaAy4S&eHI^PpmytEKmvm"
    b"AteOA5cZr{Loznr7MMrG0y!@i|2~ikcxPTc)WE?AuLw2}4I7u6n-1OwT3XjQBXiQ%IseH%c;@2e>a-XGkdq}&PrkL+!N>I;HOC`d"
    b"JhP7z=0!teEeBEtjqFJbe_z3iux^3S+oN)jF1B2kWKL7JatiJ!4(8V3{eP~xP1UAW_{yUCiYvpZe@d0+xf;}jG>d(SC2YC2CW)fk"
    b"u(#B4`aw!4VSvEUuv#ThdIcdM?G}gLhsD$-Hu=B@(a+$V2x2fMA<}lW&hI?-7iul*#&{}h=c{f8UG0mJwc=7YH=3gI*OoAPRVQwa"
    b"EEfOdLmzoIv<E?T@uboitg)rWntkpCIDfrCI7Pryz<sU?iRH}9&KjlR*JDC5@xLksKRe_!wKIf?Ttuk94`+bN4j<h$*rrqy2h>{;"
    b"hR`Jxy4InHqn_FWHXGK%@v|=6VasAzg&)B8_F+O}D;iYC*}PUCW0x_H_@CoyAqmpx5Yyy!#)Vs>SI4ZG4Q4nx5E%ZTy+f+ocppR|"
    b"k?P8NM*rw|M}#}J7wz4qkYX{O-}0E2+B?$Cr6|_HVVMWhcmQ+m>RR*RN%xBRjE@HnE6@<ibOqQ$59vb^aKMcxX)H7e@-k`v3~0|S"
    b"p@=DVa@}*$JD=KwV%r=j_`PIzix!Q5WoD4Y_(Ecor9VX*mhtDXnbR5R3iFC}jfM#j0Pb{RUnqqvI#Dg!i)I&lI<>xXb|}>c34@EJ"
    b"ALjYWfBRbodEn+?>+mi5wCaz;e0+o#;vw<D&G8<lW6P8n0fPqUO;p`g5XnZ%2!%1SX9HYOOz+N?FNQ0{hZGQ=b1Ghc5}zZ4E|O%h"
    b"vT<Cpj*ni-`itiUDrQE2(Co|J)|;P|Bv(UN!Tyf1uDJx?CJE4VS<7dCnMfr-GR@udG+l_fu>JOS2m<FK1y9=O9ad>R9hCx#>6$5="
    b"E7#c;hzpA6$<N8U>$EOZJd715ca2SBu`OB%S5zR0Xw${9MRU|%IDN7Ebibf%FuWhD&_(HN%4UI1fSg5{G#tl_9ZU$qp2?N7G~*~J"
    b"MmIy&LZo!aAE%%NKrWDLYUi^vhyIMX*5SstZ|5^A4F%SKjKT{OC<oxErmytWWd$N(F-Q8?``%qy+kInb<*bK)_NBiE^Pcvor7QrE"
    b"(MP6BqMo0%GN<>Dcy&q?u}qp_st5eKbj`QTftFsP{uSo_x_%1~<WG9c+9ul1tcB|gpFGO{aMJ@>psj*_2<8E<$?H!4DYZu1!=pj5"
    b"Zr0?68VYCF%7SVt<AfQ&#nf|0&3st$#jQ6*b9HaOyxQXF)<5Cx$P}8WIvvrN*9Y@HM{y=nXx-V<Hx?YSG{P}W`vo8GHvxGhAi2!&"
    b"OAEuOD~sr%aUpe^<h7>}1DxPur~7ex&1DUta+MQK!8krrh+W{%`MI4PlD|^37y)YwXsxQN*r2PMvj7#W2ARv`FX^eNIN<iiVb>*c"
    b"$o#(e!$%y@=b_FQtlipO(UflHtbU9xPL6@7DYx3p8Cp)__+h5PzR}inA>5ccRkO_=y5IYml&fu^Gf6r4g)1iGL)T11l|lJr!W6@q"
    b"Q)kVUf|ha;=?kuFN|u2~axFiK+6y*wV1YRaFm<e*V2z)Wy)fRT_cV2el*}PpugRs%Ib2)_A-)=TJVU8$=E3-YQDJ5p&1a*@P0%;u"
    b"HCHGJP<Yz4{+1e`^J3WxG6G{h2*QDbLt33UF8yKdW}&&oS(QKg?>+fpv00>KMuM(<6FBTWY&5%U+PBDe-xskTq#hJ|dyP%3iGc`&"
    b"VwIN)&-eQk;11;Tb+32A%KdsWlpF1}>AlroZzM(+p(;kZ=1o1n|I0MYU9MB0NdSX_4A>I<?JHq_6!RJ&w+*P@dZUpap7UD9kAois"
    b"qPF`13(oG4gt64LVKOtEX1F-bnnwSn))0XuN%Qrwvk=}y6@Y2{YsnFOjJrEIrE<E41FWtO8e2xVU0#?5)IB34iGt!L)4O(M?5vg5"
    b"DBch_tE?t}>?Fo@@FNdcuR4{(S7-cqUb%03p1KVry>D!{ggx8>M8?VQL{GT;3=}%j)#sV|Rla)&uNC>5MU5_vq(jsD1h`DuDVo2Z"
    b"W4Q?Nw|`@WL&S?Rhh}so)HiCwNsgElwyMQ@izo+MzK`7dvNw$etED-{<Ih|tpV!DXeFWCH9uzBHf-9w5Dymk+TBeoSYpQmPk4yA~"
    b"137ucl}Ut~R(9%BRV2lZv!vRT*^x2mR1PG-&@EvzU=(WIYfkkl)<{uCRd^H7Ckw2)g^jJr<w;o0-?02``$ZB!z5fD+v%?P5%mXHH"
    b"RnQP67!8!Vyb@tLuovfbQ3y%>BpR}ec2O}+A0<EdC<^xzEU~kR>r}#HdlCf|nMO*^#OPTsyrDv^q_TA2KHL@}-gE-G{AwrY6Zq}J"
    b"bouyxnhtRo;$~IwN4WWTFoU1YU-l&Afff=fR4bk?4&3t!a^*DOK9&faJJ6M5&VE5cZp|q@LQb-yy#ihiyRA+iyUeegZECxj$+_>g"
    b"CkpF_xYv(*b|2g)X$1P&Y!h$Vqu2h`_nY{N6$FYmsCC!l9sCLy_(#6fJ7@HvmwYs#TtLHLt2^I~KJ^SpeZ<0KkejZ_WyypwtjEo7"
    b"LeUbQ4u^uP<{pT-0`JX5^svX8#WtRNLhNlyga|IkQ<>1wEES*+ADS9Z%3S&{VC(uBa4(@6laL$sF0QsnyIkuy^X>kjI})cyXZb}%"
    b"t*Y+AaUzw*FSl=QH)7=WT3gt9J4anr^%G?pY|6*c!11uMD{t-8x<Pq%Lr6l#P|(W78gC%euF=Eyo>)7&%OMTmKmQKfCq{h)P<P5{"
    b"Zf0ORc$;-TnRv`a4&P_kX$}5gwVpSKJbcu3&LuIaWZAcSKahLLHv&It`+~O62i^z-j>SQz%O$@=uSXt^HH$cr2VdYPW!lxiV>J9X"
    b"DxgjBn2I}orX7v6`5sZ4e8fcU$2R`9qKH`$NE&-idG1(LLKEU$Hbw;w$Exbd<lYNiSul9%CfAN0899f@Ae0q?LTHkIZ>7ZNzyfQq"
    b"{TL4x3&`w+C?uxN7_R~5yhCG|w`n$&pElT<lP+;Iwxs`ZppNSz$yu8^0b-{;PtkSR8JxPRmCq8ocj6Bt-4yqyDEc1m-TPvTZfUNA"
    b"0}@Otbh0BYp5cR%*uNT+Udws6<R4=s7jKM9pDmBde*ZrJog|bPm6qpdVg1xqcowIg8^a~Yy?d<dPshtRQSX#9`nqEwsU5#UGW1Q$"
    b"#aI8gwlNV0sgyX<Qlw{so&vc_>GuzqrF%Th=+>EhDJsgb>W;xt+6C9=Drl_COSt>7??82J2ojIJ2=#A8Sq2K`rpLB(z-uuwUTmH5"
    b"OD`CtApU{5)Y%~Pd*C>4tCX2kXH0Al4^M{yxpy))gQ;-{Ujq=MsJAdEiQ<1I5^3<^?I7l0B^|W`Gy)^-T0ZQ5?ilVi{zSlxT6IEi"
    b"DP!GlQT8}6XvDw<T3LXg_j2i}!6;0zi*5a+zS)G@Pa>MEk9NQrQU9Vo1X5T+G+o{Gp!0}2VQfq&z#03#djhlI;kabL@nSxQ*!){t"
    b"nHnZKP)I5r+WYCgITnibn>LS%F$B8uH_bD^v^n0n;0MpXs#ahxO5zw3Zq;IF<_#gztlT6WmaVxI+;k)UnPVRNb+cUq_9=<wmCJ1T"
    b"NhSIn=Iu;eHxjnQ4eDc8)89)jdcP5)FGX$Cuyb;BB-;5x?1fB+i}iCnV(Clq1H+0i)@hbggRY&rruKS2_gOh_>5ALnpvRj6r*~EL"
    b"sy&qa9TEx2A!x|jiw}j!lIVB}I`o-rRdQ5xjwGi@8CzGbOoZ{ckq{YXfo=<N43H2SA`7oBmjO&vtze;}(zFgf-Xb673vk9kp1r*M"
    b"G8P$Nub_^Vl&G`dW4zD5r-y@CJZQe^4S3zes!H{BUAO?RmhQ2(Gl_n-L-DXU(QWa8N8L8B*GPW6*Ros7-Otr(B51g`o+;ym(>yly"
    b"8UMN>+)1>J?`)lSuTs>&1&`ApRyMR?=@zfW?PLKjHpAi(Sn-b_<&^D+;gfkd8d@3?HA`lQT$#G_{85!PcR7xeg<<Z#@O)$58GK-G"
    b"-lGEs6)Id7NtR39lk5}6l6wJ1dbG6lbgqc^hnRYw+C|KVbP9bpg1_($IR=T)wymD2c;o*mqP0ez1*GcmNmEoqkZ?%<AE{cAPh5(O"
    b"feCr_!tEIhDgpg^wQ_DV=(;ch9utT7QMP5b_3Eim-W#S3(&|XpwXZA}jiM$7r5^{OzvlvXK0rls?}(Z~{m=EMm<vCb^32y9l&CQ|"
    b"kU~ld>YK=yIww5^nMUuFtFA4vn1^r}J2vzN63~t(V5pD1&E-`00_7eYL;{Q;Q{IO9I{!`FUl*$;;qxPqU@<!y;Kbb;X^wqE*2&l&"
    b"xF;aOJM^*;g2ACi`x&hFubOZdH0)@+R6|joOkT?|ziBUCp$k{9?yQgsWU(6)6_0J7@wegO;GI{c89VbScm8cg83Mxb@<KHs0NctL"
    b"x1d9#aq5&(1DU~A8|(6`s43}4>Mf|hq?<tXw^X({cpsZ)FF^=;lV;x%7wBKRC(G`6i?q{|z%6-;XlNh?h!asfo6;h9rV<|%cf^k?"
    b"39pxA51v50^;eTp(D?5U8au-hmkP^f_f;V;{KQ`9w@#WxjD=%VJ<yW65Ji^1ZS;6(KKm`j{Qp+asxbEwKL1tdcegXw_<ecS+8Eb~"
    b"lY=P?75w8j66V~S#LT!}h3UQYA!@s$gN*512_}v^5Pjl~P1?}pzeZfk-%4z3@{S@v!N*s=yKdF~i?Piy<@5I`9}cfm!kKlD<bK-C"
    b"FbD5Hirl925H}gpjZUnY`G%2B`L4Vx+!%4(2{sdHTLfkZyUP)H2gO7Rbij`&Yodkh%2_B@qcRK&$ls7xwk}>LW8E(axMILnwWQ+Z"
    b"HFcJ}ixX~YOxd%zqx(?KE_Yp*U7v<|ubLuRloSL`A;bbi<FMX;x>_Neh9gT#<hR70ijI8}20%Tx%0f4eXcX=ZyB3bG^eS0ac9|=+"
    b"Kk#WT9mGvBCzA4AQh_(u6YUa@9+1q4*5141QE3RWCf~nRaNU7X+H-jy_gLscQddKj|9lQ)kw=AlRrT7BD;v7Fn*$Bb4m@6R5A9Cg"
    b"jY@0$!Ky{vNG$U;9h-i3Abjr2kym#!vUE^7W7VyvL-Zs*FRLKiIYYk?4EXU<b+dL-Gh83Sb}|?-F1~I+n>i<k%vM?8q+IXD)_O5S"
    b"YR{RDQy{7+#}Z62UCkZCT|6g3^j(4|M+-$E4>y4OnQw-(?!&SrIxphU>5)gmTj*=JL{$KSDJ~ZYxcP%EWpSYLge*!iPkK&FoM(e$"
    b"sQtONIR`P2WUx6qw2_XzO29f??XLPZB!lCi#;BQSa|fCkj|^abAWg4eCSOB|sOFVZNj2Yw#74@E(QlhKQvKemss5DAQT(zW(PIq&"
    b"8B*P%@DJZFnWAI!=6M-Q>2Pe481Y{yonBu533*nJ(DuecN4JN1;I;1Jb7tR}DsuSG)NA7Rx~Qcsd-vY}o%g2~_Lk{1C$}m496a>R"
    b"<Pgp=M0M$MuwS!OJnA0JUG4iqOu&Ihv2vN{H60aB`R!VJ5<^@$@$G?DWsi>XLnsC0G2*-mr8I$?{9?5?oN&)2uBt>ncPCX0R?vFn"
    b"X>tr}>s(7&&Rcpw2}X^VIEWWDWZih0!MnQkqgeb2eoxFn(pnVwjdo(_@O&UE%1EVNnkb)!FN<g0s4}YeC;ykXszP1E)GxcTgl$fi"
    b"<v=Fk!Se~t)Nb+pA-S}=RE$FUsidmZH;cwS!A+TGSc6i^Jj(i673qDJaK05U5c3rOXvmz16ziLnH!?W|-qh)pwDGik;e~rKPwr`z"
    b"$b@;qe4ZXTtg+ff+vm&HIMNg5KG@jxNq2pDeK@)N2FVmkPQzLsJt9yxnz+`&AO@A;a5sA{1m;kVNGWk>Ir&8_&`pTn>&|qc7Q?tM"
    b"WL*JPS9C*^w*%Ho7vHIqJ8v*+gfP;D`gD(i2H~WNBg5%Q;5F7}QTRoETFrDPPKk*MZ5xi}_>4`PGoaeQlZ~!wW{706c?=%&Ic45B"
    b"){--H+rkj?U3VF{#$d2Oq!-}20rhesvq{_n2?}eCOiWh?tnl>{+T`x!?_a%2cO%^m92z@?P%>VwIE>X}u6kCnr{Rb|g!}J;o;%pV"
    b"M0nFSL26mbiaC%CZaJ8gn1zZrT?pK|q|O${xvZjz7u%4iwB~Ed%+_VjelZI?kkxm+0*P$wG0AG;lh{IJC}~Pg7q2xZay*uh%h?Me"
    b"W}^#oaY0B+XF3Ct4+xnnfnEuaakBBzu~uiW*|iQ7bmD~XfIc1}4bbF5(}5OTNL$HWWcKjj(zKR|s?=X$m7lDhD3Of$;GRl5Db}N!"
    b"DHL*@^H}fQ*KJqZAc-fk$TM95zxMVq86^h@`?)<aN~CQhYtA%>4RhQd#S*X3<gV>K>dY0dS!l&k6!ILFO+abYT}vw)GULEnI3l#y"
    b"2o-NRG>r2Qeo;s;i6|>k^u_I#Z=}#RgNM-yuF(8JK{2TBmdgrm6Ln<D(s4+m3b&*rYpMJ&t8v$$Fq5jS3rph$gaP=+XuwtqJ{M9="
    b"fd3`HSKEnKmzwtGRLq7HRGL1>ocClY4RMhovBBp?cg7_)*xb0OD{jCH(8%YCw>5|MZG?OgW{vb5Q&^)b8D#yhG?C}5NVlS?giiiU"
    b"^@lPI$gel1qhw(xj$*Hj=#u{lF4nsd_MpVIA&UuB1o5u)?fU^@z`d$wLq@a>0Otb&yS+SyH$QCVkHvU)^%nuE#&MfM$8@uX=a&C`"
    b"gT9T@#1jVmPaZyb!}X#(nQva}Y9;{{JF#=8wuuwL92mxx*xlqWJ6P~pgB@@X^EdxO*z~wSb6vzqiE$bl9m?zup1_#jlR_xXsGl~F"
    b"(0?bR-?PghQK{AawxKGSSA32%P0X)vjg^O1U_d=P8q6DTwhJj28I6n!Jm`OZ!Lx}inMH6-6i5W6iWmgxkuy98H>@e{&nTc8^7ZV@"
    b"V;&&)6|7{j=4>G7fqM0j7<WNqubcDz?n@3eF#3Of-`WTPEe#cx5_&vu+gpT9nM3Z}J}y9g2n&@qdY;so2vTT9^-58n9D?Cl|LnjM"
    b"pAs2u;_Sj{;g7NnKlvhD^aleVQVj+!mE`n69FTbt#b+IRbM&a=Xs0Lw6`ag)ZhCyLIF%4{!=6$P^{-`quagExeQ6v!5*A{b9-_#P"
    b";=YWvFdu&Em6xxla_>e=Yn%E1!a&^H%Ogid>3KmFmk$s)wf7ooSHUG~`#X*lLYy9LZ4({i4U}`r+tE;Dzvh3BC>MK$=vLljB=iln"
    b"f5vBzC*flyBt8R=%ts=BAuU0zqf_hQo4(LYI`xh^@fhHy4VeMyq@EwXEp8C{Kt6w%Js>$GCwI&AxV9H!54O?92lnFb`2r$GBuP`I"
    b"X7=CtLzz)4Y}+ra%#=B{98ER0Xpw08^hv8H$-*Ki^!V7FeV~I4POiJ*XM>_}%(Uy`8_drTYExc)6P10n{2UV>C{_K!9~k+qNt&AA"
    b"#@8B))1#_}R*va=R_uZu4BfQ~k7)`@?Tj*qoD?^gn50@J#js3ypB;$E;3M!lyZu@J0M9X=gsFwyy=#TA57Nijry;*MSf^6Yz9nzC"
    b"u8lCr5yZC3V5>ut9)+%)?+KY{n@FSu*5b7=KmfNRtm7bxWzxwx>*`6zd~=qSa%afq(_~jOViKlJEb?5SqoJ29nI`g+S%z)$)U~OZ"
    b"ds`bo;O5UQXc|&`=44>p_>Gw?I#FB_tlVHEc~{TcFnc559I<Fo->~2y0IlMQo~AvQ@*Pt(DmC(1x;ia|oM;PH=5p<AN~q38)p}V^"
    b"jwsOK7YOKjD&$4t!P+^_I_a^ej@@=FEOhk`5KsqSNEnxRb+=jo77HkV8^|Oo!M>@zuQuPSj2fg^Wo(5IN5X-6Qmyo>xeUV+e;q7#"
    b"9=my~_<_dH>=AsWK5zm#fOP|D=ErpWl+t=%W?GmSo2#TrIj~XE3^6gMKt8_-#Bwh?KQ^wS0cMkP#6t6bryruVT==2YgkrKvIlBDx"
    b")`r$<4e5*Z#ucO~1^H(nIN^TPN38XJ?vGi`iy;P%HGj7<MT+&DG5E>9{zwz9MHp{wTe&Pwon2xsS=NP9-NE`o71}@9KzTunU{Veh"
    b"Sk!P_BO{>x<Z?U8a%>hC$W&H<>jnkX<%c@FAVOc#yj`}#&d|!jYFCe6J4sKAZ2>tT>@~X@E?DSBE@!@v&5mEbX?6iR`u<uXe#O4b"
    b"gM{s}&~8BLb*IV##v4v}P_^ue*_)Rr&`ojl*<6%5^P+yrYM2HYiQ>!;HOq20VUNlZBj!|Qb4|;b<bjK>^xMdGJUPip(IY$C3A_AJ"
    b"kWE8yr(VA5kUu6uW>?T0DKVh>BM|6i_CMd|J{rJhg_wyo1${I5(#CKd`I_p^AI`qH`H=`V#x@y(0x8>OUDU`t)k5GQQ@TqRawJ4V"
    b"5bEzNAbn)nHW%d?;``p9#og0D@!Z+jU&k_>^3(HI?g|d;CjM(<zNXxEG)E;`3CbO+G*hA2pjA!xLaYoVHB=IT+!GNnFrAEOKJvK1"
    b"u0=yEC=w_OZ9HfNc@`sj4o_%CQ~J7rtnh?Bw=_Qr58==FE<qa4H4q?MREOnFhZ4F1qr>Sk<^YBl_eKX&hlQ~t(MhG~R~d$_gjRO_"
    b"Xg+J=e>@(k*b-tt6F>48i=eaMBWcK^JBc?Rf`@KAC|c74wcat1`onuAb%=(GeUUq-UD$PZt65LZ^@4OSbZQS@Sjw$!ldsFI4@EKE"
    b"5`08-=vWkM5I#>r)d}!=Zk$mHeedYN>Tt+<%GhNQJIe6+-GUiJ>njGd`K>)<JcClOL6Cn>O3km<*VW}hcQ(27Gq;T1tdVN1;HK*1"
    b"urzelMfun!Y}lbaq{+uF&0<AxYF!%nz4K3^5D8)Exqr%99^M&kzGN>vla>GxLm#p?Mi{ff&2f|!dkX0+rx2S&h?1<mbU$e+MoAkS"
    b"6}x^P_|M1&(#RMBv3m>TG8P@bktk0PAyi*t2rJ-rtbxu0mgRgQI;3|bc?s`kWU3xhmOBf!cxB7~S|uRXPbiJ+#Ko0jw_C1!MxPVl"
    b"SN~2<SxRSucY7|@)>8y=Xb4;9&RoKs)6w(Qd;W{i{1&tC{x@Hu2%X0OZnY7%(uFT+A-`$f-!LyEQm2q3t)!=Hal~!{A5(B}cWl81"
    b"^7+Uxjh09;kDOpzqd+i!qKusZ2eSr$8Hl5z@192JmvFvNlE;yVD?uA|b}A_+vsHvmBGfT>2TgKZ8jqlv<HswI05PYqzMSLPuiyso"
    b"zh#a{d)@iWWj#Qqwb_|;$qXHX=X_upgnJvg3r{hPFPU=SDw7C#+2tRodr4P+y%ku&_W8+Knk~snW?&BZ(amqY(7WGapO5;2#hByB"
    b")N_@yGpwZfvUMFlzQ8IyjwAO#!|m2s%&4GJSf5zf5Navk#bby`&N#{|&Z+%R0|!B@wG#+FLHnAD#U@^J?WmP;Xp=o{!97c}v*+Z6"
    b"cCxEp&!Ba%P1jHu+F8+55NYBzp{lp}g~@DiXu_4k(W8ov9FV?o%L%#<2oz9NP9z}y7~_?=NR_Rewfqlq7??;0NRl|pfCd<eEL^Xo"
    b"AxQs&7g?Z<0%h^-OUPbSo^|=&!*}rHROSeX8ZK&t&gC&D)WhSO@ai-(am!(T7Q1o5e^ZpR@Cn|d%b$2&CJhSwKI2%o?ybMk-oKzT"
    b"H2lu?S7ck>#IfA2>H$7rCbp_{9<ZG@CSN58t-lI^MJ{_-Uq&M1zmw2H#=u^%goT*l$V?dhQUvqp&vfC|R_(o($8g<@poK3@HR#EB"
    b"8aCCdjiKXvP~;U>zr1@QHcs~+RWNNbw{7I|6cRL<eu4X#L!FD<5LN>33ryHetZjDC(VOxA&Ozob=d}*XV&;vsGbOAhrJCdZUrYnb"
    b"bwvimbP4uek_Z~*_!e7Hh20TuTa_f6jNsB$;y4265tK7x1hsL==z9LT?VKDr{Pl(^08HH`W3db`;A0gb7C<SiTF-TY`wXbqzepGX"
    b"c~)RW)-z@J8*dOS|5fZVZE_J(rAv6q6ig)e^^c%QNhpCoXoEqYII*exK8lJL-neV;J{JBK)7{6x>bSk-I0jKGCNIQf+GHvLywnb3"
    b"bS~ckxAc<NL_U*?mYY0T2{@6-XJ9@NxHTQ62a*Jq=$UbsBZ((Fi3_X?FKIE@sG5y0tOar(WoAXGUBL^Wc$0D|*UC|PStzK+1q?Cn"
    b"6CM@ib~1lvCmF$fLy*>yT_SIQk5sTxXDSj4-E6b8kUxLQN?vT%C{>jL)tT9yd;o2ciIox^MB|&6fOS=|c@;y>(=lL&JK0p%M<{Hp"
    b"4fo2#$QEFG#Z^C0%cpLm&s@<b0Ko>h2q>Ug1RinL3rlMo^S=(tYjMljlK+ngwei<QNqi4WdlI40xLXA)nx9e7v=}zsP0Zc<?f5{A"
    b"G$Gr#5yCJ9al^X@wU1HtSUrHhs7?m{_MjA+OTDL&Fz}FcwT?lxG5pe3na!t+2xx4(J)Me+o>KK#P{_r4LaL7d$u=}NsI&7eXuU`n"
    b"QlEDSIkyn`UNnAf<SrU)@7c{F>Qn6kJFn@ld}-tgu3Ysvp6dU%@E+_^bOINjQz3ugw)tjRKB&-{tI>x^C9X3`xhm&N_Jzny)zZ(j"
    b"X3pofat<^eR(5}StlBYW4NMf(0f$HsHLQ&kI6aYUbqME#=hkkvkYAfQQbaLA+Jy-I-2xw8sM-IZBS}So%qyjsygke}zW8kSH?p!%"
    b"pN4gd2WUsoMGq!V!ICJ?3s61yo}@^_M&0>KmwQR(fRkE?mIBKYZPgOe5-*11kUZPzsi@vp(`6Uihj1u(Xj~TLlW4znA9Co^1i7se"
    b"sIx+V#Lco>w1d-rQ03O5#Otnwbj%&13tDJW(0KKf{0@!4kv1^n1)1T<@g#T-LHv5_Du}|WPT@VTWARDQg^w-zQ}*T1QCUpG(o^uw"
    b"HyeQX$k@RUwkOB7&lz4lQ#O}nx>2XKV((!^1e{yhnyHhw+xbs6!urDNem&tGmfYb4xC2#mhW@=AyH8OQTZAlpgU>2kZ4&x+<;6aB"
    b"GN?qMEL1lGG%Rgd=ws^D&^bmKmr(F95TIor(&Oee+Pu0}Akg`R_|pAqZK|cPHA;bs%_O{Ej#Vb`QZqFG8U)uH&WRN?pZkGC&8%Am"
    b"|L?3RIPhO~I3`{r4HdG7610_Km=XJ%1y&fY`%-Hr^1<hlh&*c{T6vY?Bn8|nE1?}sKRnTfB!U{;SlQ&jcou!xfgT<>Bh<0QA6h2Z"
    b"(w?XY@)UHFTT5z-bBW^2%)lMU+**4ylw=eu%cwOs%*bpoxC?Tc^#3SRzIshNjxXI0qe*;?0+u`2$Ho&6$L_aNYlo>HewPblH>*mB"
    b"{fpwbXMxu9OB@#00riJ+<i~NQOV3(%Uk=CE$I+1m06uy_zfNc<o(s7V0LQR>tJbDUi|YTv+D`><o^POyba8~M+C2+NUSp23n5yAU"
    b"=0mRY39Q1g7H{@h32X>Iu>;Db&4Tnfnj#K2O{T?Pv^`mg_LSOK6yY86%kP>f2!h?i+?1N!I?@e~M)!mV`s(3sCk`a;z}X-!!;k2h"
    b"`2kA+J9_br+RVr6k@<!!jZ}3<baLodBC$9jPe9azL^r2Jfy#*y?~yu3Sl_VV7F0m(c<Cm3SCb1WFa|TTlz(fM1wk$qx%i`insV($"
    b"$OwxV$~wTnrHUY*?{7J=pjEpkWVS9WJ}dU}sM#6v*PfJjU^+@xF~a2h>}+HU=AGV|=BEpboI)#fe;U{3YyKavGHf#MaF{&)KSr;@"
    b"eVZ!~*MWgd)~QmeuAt`*j0GeKbxXK|6q=oi$V<fg3Z!NG-Kqhnjze+Zx(RXjNm2jge^jjK3bh#T4V48meVYHrp+`afM|Qk;stWv}"
    b"A24S!I2<(0mct@Acp;5_ze)t?wJP^{Y$fTf<lAAl0zS1to&%LrK4r2Vm(;rbwZ?th3uqBJ%bX3PG77YnPcUsU$UBI){~DUpQf;sm"
    b"zRvV;d86z20E`JYc=_4P@X8h0st(8T#7yjG=no4{-oUEOQ{tEg-irPu{!dSB$D9$|6)9&F=;QhUiFC7hfl!wvd(EW_91Jrn3#!)&"
    b"$+HH5q|QZOQxq<Op>q_NmEeQaGHf+or7QZ-zzS3cgyZXH76!~v^>19=qNdnp<j+#S-dec#rUtc*9Q*zl0c5O>2}nI$WNs+>YmfB`"
    b"^lOzgaGhzu5{;O=Pfr)Bw&f1ps#_fs#tkO8t2d@Sq&q&7e^}*&b8gb#$&3I2roMbmxTiUDce1a-Zf^kL*&U9r-Qt+Gc9P|Lq1v#>"
    b"=ld>xk+?lsD>U5CDP&4OIB~LXwInEOWea`#^&79$9?yYA+*>JM0Yr@v;J6*^mV8ImBHZF;2eZFvF2tAhW^eSFf{je6P(0r}Np}g2"
    b"(7Fr69K*^I3g-#_c*2u3;s4@fQFo$`2ZGryQBamQ{<q*cb<=*XEeYljROt+dBNX3)D{++|2t?5#qiA@5F66wEV)?Vq?Y|@H+s=7t"
    b"cN{9g+YvPtau;?8MmWaSZ86d*#8S_LTox_?098F7o`ZY+0;<OGWgFRJ2WgasKwEic?X^+U<eA+UY$lzScv4P7sXSApVm9AV%)YcB"
    b">3;$@wg}#g?ve?z7U;TOdL^FSO|+R>H02XlxUF_gacDP!&wf7z2-3v?UvNj1{mhKEb~t%0T`pY^7_VwJZ>FMO?|LN#x_YBknu$Pf"
    b"j65p@tQG%iZn=KRxFp^5g~g!jmW@w3>}z}~ixGnb3#Tc|*!*;bxvwbev?4A2e3hi8n{-10G>h->CkCqqb7F>ht+ZyvG?L~DGE(#*"
    b"bXIDw;R7y@YRyp;)Q~hAp#c4IzO3V&qQfWDX<)1of7omF`<I2~QL=x9smD9z%3M?dK@$-4oXmcJIw+X~4Fh7ij<E^-pwhVkK>T{E"
    b"#kG{M`+*l`yn?@AKI}O(<w9B=LJmkTg6zyyX(6c(yvDQOHeCi(8iXKA$Hd@n1>Y^6LVS~Ba$7FT&m-D>AHH~n0iYz&p5yVh6IL}<"
    b"RV}Oj5bzp{FkA5n4W-?bvace%3;%~xj*np5DOUDht;4j2c)5kB83dW7P>KBePS#Z}{^{4~y3!s}qy|KseX9hyKN)c?wxMgpv(J*U"
    b"h&`bqd)&rY`31DTg^ns1+whPxq~nfQsw){=H`k~XJ8+;oZtiU|h7u{=+(21*lk)A%2}Y=wz~`5?SxW^)_tLc1ASR@|WgZh>cxB6!"
    b"-YlRpV&7titXoHuW6dSd5?Q#-jP?dBbwoCZw<F>}qPwtJ@f516Z{-U5pO;J2;<RmXZMGZ5-an?JDK}>x8}4KGH>2z3mn{=C#S7X8"
    b"7gKq!003J>s7Y#DOB)E=QoSpJH4x!(8mt<d_lb_!v<biRr#>9H=)tXfUdUCw4M<@4L;She3`kPS-crB0woBEyUEY3bKKRwlHuwCD"
    b"pcCppq--TF9<BYkLoNzK_t0=9woW^pw65-pddBj1Ee2W4cl7$XZyt{X_S21^`?WiMya}L6Gvq4TzkT~!wD@|&NIg%MmLs{9H|7)B"
    b"#VS}o0^KDuRJnT#Z17qN<Xk}dI59~GN0c?{;cG?Zh+1X<K%K2Oh4cDOXxC&sehU#Es^}mh!CPpzI8=&xn`XaR6s2_3XhG(0#h98f"
    b"L#BmuK{<2rGS`zEOE_nPCS%K#u`ki!AwlT?NK0R?5@6gq9T<+?#GW92(!(2nElD#Jzdy+Lv$z{=^4$}N^-a0CGklUWwo9Ih+l!~^"
    b"Zs;ghqBLf2<Ro1mo29uXc^VQ|!(S<jRQABjpC|efoUn=TtUVZs{50E|FJ3)X3ht5zE(9!BiQVwFG-4i?gRW_;H8om0sMyQc`S}|o"
    b"1}9-tANmKa3AiN=ViMOsj+d<uyu~5Z#7Vov{n{OEV$Yxz$C1s41UNb!o5(S+9G0KpyjV?A5e9jpWY*AF(p*V*&Q;T1$xfI|)0zGT"
    b"v<6a=I4fGS;Gr?q8B&F(Z+&<NL_T513dPVI<}Ccy5VQjGkOkhnt1^Quj61*m^3H-8eTeS1!mRa*0j6nMm5EbB!YM`C@Mcv?Gbk6T"
    b"1-GmyN^rnd$T0g)iI*+$bj-;3j7-ODDjO}AP%7>!uA$|Ll-;EG-i!N%AU4JF32|->-<`=Z0l-GxrT{)wf6_TN1cg+%h0*P%Er|Um"
    b"gRMN~p0?!M*n)2h4Wh@m;}0CWGpOLW7t~>ss|b50yFPWWj%1S~{sPEB7DzR85B*MsHIZIhlwa>@J@RgsJ~rjAIf>bpT$#sPxhwWV"
    b"JToFoQIS~c`K&}s+J1=_#vrJ=N&e_s(yaJ%@8Xo)YY(oUnxiCybJZ>*x=YwLTO}MA@b9IK5pPxgy3;J0ZecWp9nN)xN7)7Oo;Y-O"
    b"=uVOGd0Mbg@dG&^P*)se+iA_O6(14Y$E)gQLmN$77f)#=3^Zi0lr?uPQ0K+)t*P~ys>IlK=Wxxx;IS9jy<fPWl+)Ygku;a(yeN(y"
    b"iyIqx!)IE8Z13K*ci+O~iWl6%S!(C47*SgWG+>fMDrvp=B?vWeb7rF%(ZI}tSlc}<6NB7d4<BJ*9fA|V_Ad=+!l@=I^)V~4(`%w?"
    b"FHuV@mje=rE|KOuL`-&IW|R%feKE4zS+!8Ry(9aI`-P8rXoScPX0^S*AC3-FC^|<qqZ5uKYR@9>Hm3;zV6(~>B)oisY1YA~M@6{D"
    b";(BC#OMie^O%c}XIhBFP9({Yd+2|t5q2R0?%$aNjLe@<OwkUPgA{a}cq0!$ih0~`nIR0dj!wgBL5vT%zoJUO&RZ!R>dk4|zo?0o="
    b"m}ggfLb2ab$%Lw}lVc`EY-n9p03-ITh(d58>@M#UjLvUobYPDc<m2{6BRU3C{qSwRr{)?<*haL>lQ$<alY%=KwL3kFWrdueD9Ao7"
    b"T2VK;cjMr6HEu{lmRAtTj3bf^`A+erF|bGAco>3S*-$feR_<<l6zdDt7%G2ey@kCEjs(`1PNK}9?AKRJU(}0w1@Oj~B$!*sw%&5F"
    b"hd)v?MJ~Vyc_A`${~X+r>_C80psLS_R&gfeCnc+E3AT+Srq$E4a~c+Y%Reshw_}DzZOzS>a1s<WYu@sL63y^&2a6Q)t>N=89aE5C"
    b"nEArEnbtE#(231&)ZDn}tz;7btZ9$31ua@yW&oTUidiRhfFY+ti)?3Hu9k~&J5>eid3U)c@s7lnyYVI1eY(L5++kMYg4kkXn9%dJ"
    b"N*jZ*^0qjM3IK;Q!A_xN*gn91Xz7I2@QBN=X3<1U7(9V^VDdE)5&UhHxn?n}QeGEf$qWW4D;WZ__QgSDU5uH!V0-GLT+hQTFhn~H"
    b"aL3+VC|}ZFNbIBc&2GMn-eH*}gLnU$|3~5`uCrVH$NyU8@KYwA@SrRqCR8)99?VOFI~hR}-}pE-Poa@2!gE9w<qrC|qi{g_-nK_A"
    b");JM5%C_KKMLZ6`Q9quc5&VEdwI*BFXQw7JXQK`<-#&SJH{4G>m993427K)zgfCa*#6W{e1WZXBKG2FW)ZqTGw)Q^6FLs}L#Y@s1"
    b"im^xqe5~5)dl6eAlF9c9%^`Ku_77E1Hpvu?N7#%wh^-<{MX&jxmM`F%tHP;pXf+P`@GzmB6ltzwoCxo0;AQ&B?Go69&!BU^MnaaN"
    b"({-dIvY>Wl1ByeE61DFnj79t@NE^537ZCGV-`q?vc*x!x2vQ5PpqocIT_vE*X8~&P2B+xnqp!K0duQ?i+0^yKa!{P`ZMm(>)7@6D"
    b"_krtPWFsJLX^`8%g&YBAI;qvvFv*AlATTwmGFrf<Z%_o3Io=tXf$k~S|3)}Nz|QbF4tI3?5KpB_onlr_a=M{kURfs_R~#^#{F>*V"
    b"n$-Yjd|(y9mQu7FDiRj9Xk8)71FX#(oEegVD)^}o!8M3V)TXBDh!D|Vj{$`v2gWBp?EGI*%am=dXWdm6a;b{OdO5t6Uwl>;wgTrj"
    b"AEepS0SW~(w)<yAPdFIQz8(|GW3v1pXmwBZF}a(VyJ`Xs1%>C<Bf4uQrqwhAn#)aL1^KOt!IZ9rj*0X-lq!GL6B8WJl2@0BrxZNg"
    b"C8YEoRn^>8*uHX3!HQ%Yp-AtzOwh2Wb5M;#o#Pom=lv9mz&Zl}oRtu1obVd#1&mXZLy<H(8ie(_@GVOKyjv|Y`2HJ4a7N=sA?q5L"
    b"P7iohY4VueNp$NG)E3n11}&HRl#8A`{XdX_F)|TvgvRl@mP7w$fADern-4p%J!At};^=4TIIyUG%)tg8xlG7o<lNulqN5U0ZUO9R"
    b"F#W*zJNvD`Vn4sU>moPMAG8v5?teTNZxHi*!1-VXGy0(7Ndkl)Er}XV*wVwYRN<Pf-se7OB0gkdjqUt^!ves;0(NU20y<r^hxI6V"
    b"4dpa=<(+cp%&!84mJG;cD+obGUvg$-#wskYiS+$0Vf~f%dEm)hO-tU4*q2B(O@?CHv&-<h(!`F$nIvRkx@YsGYI)cWekY`2*8d9H"
    b"UaznDJ&WkfjtyWQq#;2cI49K^(PBpOQxnAQg`Ft$C>)k({epwN7<{+2krDxV*8+dNr%kV}WLIKP-?Y3{aFS|6_u@|dQDjUA^=Os-"
    b"mnNyxO*GPA+JoWI-)Ub4E4QEnr>V@_$8Sl?{fBuokhMBwr;Jo88T`7h0k1jPa24B>T+ia}l#h|b$78?XwSkY4Xwo9ytZbaPW+PW8"
    b"vfl_0lN=qb>an7|g6D~5a)LhlN&I*Lf?nxDL^S+r!?BGV;ZJs>N>)$Oiv3v`L-Pept0pc8+9|;Fh<d4HqMgRiGNUGr5x#3%na`Ds"
    b"fv3d`9}%?46X2jKVKo-bX$yy`GR1O7x~t%{IcOyT$oG_vBQ7abk_9%6g5_bb0;zr?t41dAlF~>{uM?LzI&iB|A<Q!QtG*%T(`3J$"
    b"b_f}Vszi7jcUQC%1C3&VslKVGt<*Z@cg85%%9*;zo6FU8TQTc*2jif|0+gE^1T{yY>(6IDk)fh~AzPY3BXlq67>y`c4<$5>@nr28"
    b"*cs{f-E#FR0z%nUr2=sp6Rs=3OAD5Jkm`6HAQF~UQT>{$(G;y)^EEb%36mhE?hBX-1Wmt}iv@F6L<)H9oBS^QShz7&?aRPBYX!@k"
    b"XDFn17eV&Oz-Bm7LvTqPlNS~LCtJr{dvs~s>G$T1z={ruGJ%Nevv)(nnv-Oe0INflDBvrt^c8KdoV#$BE4TJ{PptDODOQ+%059Nf"
    b"dj98tp8m6TXGl8f)vN6mMF%<GB9Y5UG3<UbdvQ=8UfX<3T#uO7rzdFI`k?d1k&}Md#ETJh+A{Rze#Tdh5BByfD#(eh;|8yC(EAVz"
    b"dH=M5-pqObhPa6LiEbbx@DELb4n%B{WZ}-b*8oU#7=CMwIM9w~W?tx7(Tw1_u=M!>oJn1ZbX40*n42|kD-=6c<qtUs(AMPvZ@%#&"
    b")Nr&vl8!a0_2whx(r49tEa`gs0qZESCUJWEr1{<>ci#R6$VY7#72~A}eGfwAm@J+%5<n1Lt(6m4*o6VP4;onVHcXF;$^}^!SQ5IZ"
    b"#eEUoueKIulBFP23C$}EFK593iBU%WZw!6Y_Op^p+1!f)u3ByjdxLO3rOudD^ipX!fkt}bl=o^F9ut1hHjBH;IrOh7mH^#HZ~@}c"
    b"e>PJcm0zMiGwM8EHw_+}{Oy8p@Nb?Zr7huTgygKq$>XF@LDuU^H016G<MHXKfbGo=mTVGF_6jIH`PWlv*1kD`Vl&GYiJ-}SimS2p"
    b"n1zM6dc*b8Ri=fCwqX+ZfPPW^biuQ)K(tZJ8V){z^~YsQRJOrl{q|qmO?m>`z|H4~BI=+3qO0}gqZ^00Ok>!?_Uxeiod(h^0OPNo"
    b"z<-AA*gnlhnV^$u%l&)F@T(gSL7Q7>zAIFszCwiKpAKlr$fECuKeF{N3TbUTlW9#NFuWTTUVh&a3}Cn;0s-|~L#>k?x8l7-SRa=s"
    b"*h3Bq*XbdVOO9~^<G2Ff^KH*k(KOMUyXuO}wrWxfeLDTolQJRL7=Gzp5TL8RoEw2Ia>7#a%oFsm+;i$C?aX+&LSHi}S9Xu_kzjQ("
    b"xW9Qye}%h!%I7ec?1hE@i-zQK8<>s5jN5{FIDQISA7gjx#4GXI?Rcd$2;VvOA$JfU5;@yq$CqI>FVnm4AityjyiTP%l*89NNs2yI"
    b"-v8*+v_`ndrS}W~775eBmMIc;Wgy57u|Vq&<q>cx>~c3G2cJrz3|aE3okQ>7q;rc1&=Q=b!jo^&IKcz2%wU0ZG?p)MyqB<GjdR*)"
    b"tNA*ue(N`l9c^?Q=)6<cL)e^}xHyYckYNe>ta~=a-a*UnSBe<f@X7_91Iu3qcn6^@z%G5?*l@zFE(5SPW*ouHZv|P;|GOL-UOLw)"
    b"*DzA#a(ePVEybCMgxbc-$zvMNKK3RdWTAQzZ8Cq=8irbrMdo3vY-pKsps%lJmC5@JQ&dU6(`qcY`x%6IC)4IJ%H-vy6gM2Y)@bA3"
    b"Omv~(Zj8Qj?&+r)QzIR++&TlqKiZ}^<ErX}O&G?wj7Rqz>W+|UzoRo<hO9XzdOqgBLRxBPhstmoo1fN@!()5x3&^94_wWOAbb?jQ"
    b"thw``cQ&}lGl0};8uQ>Qt-%g|1k-s8*P<rP%2Civ*z}A4H)Qh3_$|XKHn*d8$*>fmoiF-tHcAk}ib8uPysAC&H(<`Ej>4TCQ>Hi-"
    b"-9Aw^Y^0zQ<_li?p@(Ui5;fFxC#9pL)nJG)j35<-=#DA>=-AE4Mv5?C_IH*6WlUABbvi7`rot*YKP3?jLF=?;&-9g2cVY#zA1a~>"
    b"#7?#K$b|7W^z~KKEAc?0;Cfc&ny&4+3__X1kUX}I6^ab`Jwm-4hsfm@<f}-rQ2^v{!v8J&pcr17Lr^F8MA@YXSO3(I2kB|vDP8qH"
    b"-u2#<=fp3G=xoaM*ZIf9AOc+sn*#^sk_OLm$(xwFhg+2bg8J*zF^DaHKC~Di&i;jLV54thGz3HAGR2;~rOC4Faj{45sUkd7l7&iR"
    b"0S$77T4Lh*Wkuz4`oG|_yvp*(!4D)_a((}jN8X%1O6NxN67kAC6H8}$A|QTb%D;Oq7PP$A`cu$7z4tHsn{3q$FVaWRw@Jk##$M^n"
    b"QaL2r8+RG_lGMq6TUxFp3oY5gDTq5(z3qV_=+2Cu_Q0XCk6}l800uU<-w%P2lQkrg_w}PghvtMFw$<R-bUj%zSeb&7B}*)Vmam@_"
    b"r^}9QmdLaJg)+EM{kXYj{-KA(bzUj}eWl<JL{!dzLBJrY4k9?`Wi<$~=DigT+m@d!17?f|X^rzZ>TOjuRTdP;VH2c@=<0_@aVCiQ"
    b"ck}$T0C_CSM0pm@^s4I}1bUd5K%9(t6G1Q?f!I~U!rWF=>R$tM_XPe3z_xuXYSP&MxCQ(qBMTR@#_~*f{OuOr$FEra1g7!SFYL8O"
    b"?PbG1WM62~4txmr|5=N(`(!K?<_B=127PWqp@RRot5}H9bq>rjf@80pBu+sT$5AWDD&_lMZtrQK9~73B#}}_z<6#%n*7lyQ%zo|("
    b"EBSY7wu~Zi97?;$8qRE@n`5x`#$w3zO-ug46_@aOtpPL>=hd^Er6}G_%d7WBF*{uLvtprF)QO{!3Nq!T@QQ`A&i_mp0IYQ3Ln-J9"
    b"42n51-&EJ>e8}K6{B;y+({x4-_BKt_`V6LO6<m+Pc8hat(6$50YC}K&{ue=*C6VO%o0!l=vx_d4BzkKruwyR7G&s3FAqZ6~u*J{I"
    b"Gz`uT8x+dFDmQE0koXDT!~pqX-f4L`I*!~EsAGW>wOEbq;6X3=-%k<h397;T!%F*Cfb&lpAZ?%C@9aPtycYBv+aI=Lb|OsoVn%;+"
    b"M%On;gncd^;cX^)RAfTk(Zvgt0S3MCD44dP^dZ9C8`srdvia>IBF0Uyn*5tZl#-%2QnlE_5)t)s|5&1RVnCECDv}npVQt4-*AWN_"
    b"7BqzGQwc-OqW|?-+v)6Iq?zBsh8=SNS6>!Jihhzl86@|{Kvqhm*TXE&G1!@pA5t1=Z`K9i{<v|)|LDi~SiiX|qA9#H+uU2>FN{d|"
    b"J*&2+P}DR4B@n36M|T|-2U#uP8uYEz|6HnK?OE7$&A4DF--WP{6e_z)YKKpQf7TSRHdicK%*9L@!Mh3@jp32*K7RR&(0iXPEN(e<"
    b"IW01M)Q)n+w+A~EkKuZjhHoeZ4~p}@e4Rx&n)bo^$%568Gj1QtiWKkC!cTkre87+Rp3IqHh8(wDpCx13-yC9W@ti%JDGy&vIbz=u"
    b"GXto6-(34EItuA4_1xt`AX(gXU`+D{^7KRLe65NGXjHx+j7CSnju5=b;uI>h{MFnW<XmnA$z#h(?=f=mTse6$h|1kxl7Bz;&<~Kf"
    b"hNLrHP4>)k8{1a=3W>kN+G||}z2UL1UcuWrp0T|EGbD1*&Rl=Nm0WQ}E83h0xDt^6WIQTXSuJd~?Z)0~7ZuX|fr4NX?iAT)wSH;U"
    b"@q2&xog0yOvN~;h^!QNYl;C3f{yc95t)dZ=RbOY~xe<De(%mOUdAk%7Z+fN*_DrWX8}1a;woRiJbPT>^K>E)zp(1NpxiNJLa)oBT"
    b"z=PWk)i2L+ZV4$wK<?FI2ZTQ8$TC}~JCEf6eb#RSYz1P1e1~1z52ohaGBP}f58y|Y;eP123Ee_m4`Ud<;l5Qlu-&f$0VP$lX7qXa"
    b"fK{QOhul>nCm6PQ5^F(LvK6TV*s+;MQD=g81(r|M&VS1lObDkOPi0c5lRnM;&UvwypI3knZ@PvP*`QTu=(}$d+V)rb*fYm1p8A&@"
    b"9Gsuo?#Wt6lt4&hcxnw&USRI?l{C7>*EuQazu9Dt&BC#&lN5vbBe%j6-?L120~Bw*oa<vk<6ws#Wwz)QkEJUxI(eO%P5BXiFVV*N"
    b"D-r2d90#ZT(?Y|;`bbcSdoMjwwXCsmdJ7~$lqv-sKff+(<tm_Gn|rKIPV`4NP`FQ6%>=4seZqrhn&i!TU-wB2A1#Ei3{?z7*okyY"
    b"tA625tKK6V>NN3rEOvc#@OtI{g|$6X>B9v{5Z(>uU8^(6cbK6MdLBu0y>yC0LQdhsO?~eU69Qq;izH1m{ZT3~GUUI0eXGvveM3>_"
    b"mbK~Pu^b;_DIrt)aDlvot@+Bdct$wp?EZ?pepd?<SrGILI9*Drb<wb)<aUGq5J<e{$2FJ$5rN;lV0%k&;8V#Ro#w4Ly9ZVA`CA0O"
    b"5;gs}u7U1NvwMe?YsOZPH+Mr@!kYA;B7$f0vN<-r0=AT}b5qNk&!#zN!HP|F(GZ(^bEe-nbK773)GfDa6{54d4Ga2#97Cq)k%3Q("
    b")lmV2#cq=23$AZg;y#fB2d_~!PdQu>bKyV*Cdn|-8#fp389{)Yq?_Pgj(H+$S5lPZKA7~wjpDNl(3+Db?29?0dQ&r;Ptvadak8Ts"
    b"o=i8#oaH}&!V_s*(22PJP!?tNagyoZAU0wQNgfGvo@heWT+q}MgT-zBxobWd{Ou+jBqjnWhk2qw8>+t>C4)U&6SO82P4f6Bo1%hw"
    b"2&nI^&WF$#3F^hlu6_wi`N&%Rg%W#WFD**|x^Z(~dQ4h=A?dl{`1&U4?8?rR5U-Rcs`3fZY4YhbIeImYMs!DWOuqgH0E{u|1UUYs"
    b"@ageTnN0=Q;VK4&GSc2@h3`(HLa5ppsAG@kzr)+J+>BEQPBS8~8SOoQu-aj3_0#$J!JO@2!YflqW7(!l$K(7~j>jR>NY}#5!Y<NZ"
    b"`;BC22WG(GQQ5a&%?~s>AwZ@vD`haHgur#n;I}58PfzBHstFofp_duT24#v1AXT}xq^i0Y@6RK?ZpbcQUBjYpi%`ZDu^y~W0F((L"
    b"J^$I5r2q*omNd#|f7@Wq0r*!dv&A#7hI&X0uFuot?%hV%yshhO|LK`X(EFoEG=-t03cI@4t{JY%A0mbG8CZbR-vv<V*BkbKkfB+e"
    b"R;ktqS4IqjHX*35)iFtU$GK{qL!vSL|3`F-QkoInJG4LGqRGvMxrae=lnbd-!@lmeYa920|2&xDxDC2xPNfR?=joSsR!)sfo~}G6"
    b"p`8C(+y!Ncq(#M;&BsQ6kTYFr-T?i=TGjUcCjR;9tSvYR(Fj$Q<{1Ps<?-e;-DUOZyf7n>3gv(iod*zssPtIn+n*h+3^Z~mE<_!}"
    b"F~Q71p228trcf)2!WP2$UL<6N4}|V(Us!n#MR%PrqY@5Pt@1`s4bk~lnQZjBVny~sJ{c}Lxnyv|d-;O>Xz$?-FRFp1f702p^Tvd`"
    b";_JJ&b?1mnv7Fy7ktn6VNKW_w5Uf=RruNZs+Rju_`P;i?4h%w;j4Wn4TY#86pQod~6{+?vz7JEqawjbbSC3CtI|m{_Sfw+*s)<5o"
    b"WsNxKKhqd4lV&NL+k4f*gakUVSLrEl1SE?Zj3K*RTc7W3O=MfzwlVk6Ci>**!<hv<mZKrYjT$X<Av9`hXc8*t11==4-M_eRBU;$0"
    b"KHtwqWA*+;T}B*{n#&F<6|QcY^ML@EW{A%li=+!REfIwxN|l-Yn(dgw$xsxDONn|w09||rM0Kss##pSSqNy@CxxjX()5J(tf_&WQ"
    b"-IkH~0wS!P6|^yWMd>Cplc38PD;G;BCb$8ncrdV7*W_0wg6^?QZajX>qePGp7Mj5^dEknM_nibYndI6rG4ZSdH~*RG$F94~2oS-H"
    b";iwr#B;PL{;SRUPA{e6bQ5%-rR|qCN^Hn_@u<9Lc45hc?Y$0j@dG#)WKGfTcznNgx+p;Bb--yD~ZX;DOM>ya$gDQ#k8l92_y!gZi"
    b"L45UuljjG~L=GH`Pg?}#3lMk{e%+N;L@SX$o_I8aXEz-A+>%i#(a4K>DMQg&094l+6sS`8{Bsa`Z$qW`%!Si%SW#3pXGn+8&#D$a"
    b"RBM<DCe-~5-X`=p92CET-X7$xsBTxq$<w9KB>FfSSUKQezpT=afL+~yC(iL|<@EWJ@^rYI;3J%ugAiD+yM6I(5y$wn5yP=-eZ;R6"
    b"BhI|$x07|=Ho|McOmcpLLl(D|qqrQh%*9i9%31uYXh)zwKGGnRN85*Vtw1c1vT>e%PFwc4>w8~k<!Y0H@<nzB33G($wavA-9h$>-"
    b"v<+#-QC`G$PM!O&;>})+5Ei<q>MfPzqPB-7l47_Km<$j%`$Bdi_VlhHf)etM6^GmpGf)zs28t)u8^$j0PKI67{P!4NgAODN0%0=Y"
    b"073(VLSWzPQ`AE&kt9V{TMQVSbQ{gxZY(KgV%KN?byUib8%?vxdRl{qSp=lVDiRg_0k+cJ41J?dYlF0Yb9~-x?=`5(=!ei`Ksmvw"
    b"#Mo7YDM#~Zl05ProaC`(Pf%Jj4JIe^T$<0J775D7e$@q~)A93A(H21BRw;jRY}3gObDG`X7O^NAiObDJ>OVvX(b@A>ZFZ*W>1=Dw"
    b"xxSRA=X;ToM{Fs5i;GdYDg*F)Q#hXBWv(RU?s}nfgK^NFF0|POT;P=2@QEy%ylJdU?~+SI)FX`X6{KhG6}YRA(dvt?{g=my&(_r$"
    b"_)W~57p8@s*$h%t@3hFD$yX6_n<Gr^f5*)ySvz=D&v4G_^W<7jc{nCH(xc2awS(0-tiG~?@js?4yH9hEqy={nK&p)_s&kQNuLVbz"
    b"Vlx)FtC*HQCeLaIxoeQ$pVNTmOE`Q#LbCs!DZ#2pO_F(6Tf3><U7f8V`r6-K0v1}v(QR0h2zZv-a>q?2_ESos!?mt7?878s2@P(L"
    b"_DoTvQ@_slwpS%ETf2~kpEDAJ<G3c^z;;&<j!=!;dJs!q^wR9hOZiF{cOk#3@^Q|T9Jj`YNW3yK;-12J+c8zsc7>_g98x{0J}vQ("
    b"LUIp%*?3x7IhI8$=~}Y=uWPFa_is7=%pFm;#nN@^2i4~n+Rd7iSn-Ay$&Nu<Ekd+wyY0J{Gz%3e($h*t8ka9@{wQtgz^ldE>+m^Y"
    b"oG-9<eK-OzM5v=y<2ajB_~=d}gZizOt1(GeGXHBy_|#6Fr-Yb;GJVRwuqIY46!z#Ot&j&>h}SEPe^SQbAL7ldjgW#(8rccZBT2SO"
    b"9M($$xZl)5J9%&E9%|hQZx#lNM<6I!vzehX6EOfFmHK2tTcLPtxJlw#jQ#4P&wc_nb;#4Ax55j}nqYF5#qU@6zz}cs$%0(Sahvz@"
    b"CKz(uhHz=(TlnB$V4Z`sWO4K;6VqPL{$Gf2-TXY~E$NdrsKknyC?wT;UHS8y*2h~urPS$<09(W)Q%H(!0kHz)D;l(r|2UnCB4=^b"
    b"65}ZX0uYmg0o=`~5PV1ZZGnjo6Pb<pAF&o~J3pmkDb29J!gqW(mDZwFSC8%o`}46VDVfi)JH*#hVNVqqEU7W63CFGTHXY<HPa0V&"
    b"$YI(HQ|LnqnMaUYB(;x-?V%zLOKsL5zo0-m+6VyAy)nk*(4fnL-Ab@4a3C>9gyC};t-H^@c30?9<ZzhpdZVA3N^@3%C+xfp4FuT^"
    b">pa}t-mY^c+l?v!?;J-SJxEsvs41aNHxk9~qbN5(ilz*Ae>%kKi%0~{AYK^{m2INW>2GF`2JyaGBq+irnbDWf7;%_tpAP0rgnu^6"
    b"6neD49#<ih@$$(*^VTL?P`qGP&dTHWj?nLuXfb1j#;SOJo9|x#SRy)mR&Ows$GL0Q4`wKv>}*_+I8oB|pnCoSc8q3Q+FBr$a$wa;"
    b"8i{&vTy&`&C~N}(vH1L0EDHZqMmgB!Okb1WQ4W!7^A0z-VlMAkFWNZ!{J7>ns7k9F_95Yn51lBvF}q^{U}=V9FD=<2PvjycuZf}^"
    b"xBOPs0>VJ4IkMZZG`y4BxM-07Y-~-iUQZE%tJDL{Ad^m4|4m{icmuDx_A;q@xjasb%}%EELQK>M=(3>_tTWg!H+j7OD&EjoyfshC"
    b"62p|dT8{M}(X9ryPJX{e*7+B#k%Q}HfHhT1!3iZH+C(7FtAd`Iupdq|!~ZdFOTX?So6KJ2b!;<CBs)f2I(<&|=3n*NwrIjBn%9~o"
    b"mF`#&aNey!$1tALbi3ax(Y3+g{$w*y=G)nJy8k-q)mq(vUgs~HUv+Y&^~`m+{A-I|(T2+#0XJ@Xj?Pm>b)|_h7TL!aCTi3j<#gIN"
    b"RMO`f0MJFgrpXutUuTz&PK}p)kNqJyoe{}{4=SVP>Fv0}o~cY@YdKN_ThWL<Kt(sn)^^j!cI>WbDVttnh!i3t&?ZU|O~eK`(H1VK"
    b"Y&n2;VFbo|3*=m$z)}TKCC!|eR(v}d3k>O6Ys^n9vw1@1*aGy2Qsfzu`=O$6NVp*Em?W>_9GDCsk2fk)PAQ_~j#*J&iwG%V3!d6="
    b"tsmy1lW4$UHr_Mt+Y8}1q+(!gGY#V$Zjb@|ZjTs&iz%Zn=U}kt!)CbS$W~z(<smUa*q|CScEUPh{N`9S=b{hUd6}o?rZ48+bBw#-"
    b">R+(zfDW@;+W+0&>s}LWHL$n7htw!PF1`8;SPQzKr)>SmS>WS;{1p-DCb2~@L@EYT><31B$$|Lh3o-yvvre-I2pz_w62VI5Z09}U"
    b"Ylyk9vz8NYW{J==pU0rdURhb6*#_H^`(|yg1UQOD(%&b*fBLb4<1PMVfPB2vH->T4LZ&g7+kEIVP=K8zGu7D1h*&}D)a9fYc35Wn"
    b"$&Fjt?M=iUzn)5K{&o6Ljza2|OTq2texC?uMuae>N-}qhK|$>SqlDSewVPp>>qvTnekw2_wsvcODVNd6+S><Z#QzdjLf9GGlFy*x"
    b"nZ8Zp1J}+{b#DkE(|lXSV{1{~N@w<BcgqRg(<<-D9M2f8ofmt%@o_Q*ana|sYit!K^t`D8OA2wkgM26WnwRbtT5q|i3?zv8;OZCn"
    b"5Z<Hwt$h0=l`7PvhHDUg>7Hlchi_(qtEMyB&#{BG6=lT>>Xh-CLi#ZlsRj{j57MLU>?O!Fbo?e?an_iPT^(yb3;L1n6HLW6;wS!w"
    b"<bVKuMjZWxr10AZjuoJwtRL!>`7&`G;02s9tnX<zWCpmFi`O3F?&5{DzuJEU`x;7%jZ)m==z8trnVEc4qaD{b2oHJ)E<8aeKMPtI"
    b";AKL<N3Co)rQE~{_E9!$_95Mo7M`Y>ND@7=W-n1Y$@?trd!VKUoRk+o+ptmwMjlVc0=Y$kAv=_4`&Zq`xPIe3b7(S*I24eWp3=g="
    b"ijwm|i$S4Z0x|JO{uJOergMxXoZSSu<iWS@&$!ONh;_&dxE$*f!*CNHNUs2MeT*9X1k?wxZ0*}exVB;$y4xxi#B!*UMg}t7&fKL$"
    b"#2*$U@AI|s!ksXcZFlx;5sy4?u94^;bk!SG0qG+(N}&$rJfO>))1i3EU9qn66K7<a7i-HuQ5{E?tE8(Qxo7jKnntPGClYRtT)C0m"
    b"sgzk$E$D<;(^TjL_uLKY+?#8n)S|Fsa)OKNt=J|@<l?)s1#9fm&wEhtmTP!9sHv`~ccW(CRypR~k}Z;%gn~=CCS6rBphzLSO00*J"
    b"Q%pmwYZ&`@p(YKmqhcxDa+>kd!%_7x*Um$C-8HWmT{@JI3`07TInkNHvVKlCaK7&-dS7WQ$`|5<;-(GNV8bPD_meIe$SN4jc@)m*"
    b"TvWwyc>|XouOfGA;7x}vEECwNNG2q?D}YVml5|u78dHa(?5N@SN+{(VJjk(~E6dv{{f6vNrlh$U$--8{4_<uIQx8<^U$q21^%5QA"
    b"UP!4vQvv3Ft|LDL6=l*j#T{)|uE_0Z`h-xEe*I9B0_5%oPwM4I`VfMQH+Ow`t_&2L+F-;bpoqzU$EM(@gmow~mQK{pcYO`2h64O?"
    b"j7wO<);jw}nireL*keu&R!|uM&c#UT%?62`fD+k?ei1|SM0<U&C%)^woAzK*bHk{)paB*X1uuT(&B?ut8L-=6Q7{_{b!!Wp@l^MP"
    b"3g2ld3X9c9xriNDK{&HD6fK=S)aE+*fEsO~=_SHLVayXjdWigv;0c7<2qgP>SjCN3$Olm;XwQwdH$dWWS9QZDg;E-rh_9Q2NEv}f"
    b"1&xdt!T}4*u1-B6$KYxgT~u0JEYZ+4xH<S`GOX}Q*PneZ-q(^m+u9U4ZKa9Ea_R}VW?OqTmZ>KoqLoH6R8Z>$kTS|itl`=Wf}hd5"
    b"n^^LS&cF4-@X5_G`~Bdnub7)6N<6%V47ReADoFcPKFyN#6F-?-D*|RNq8#L@n75^a76@b{CxEW!8#An(lmV_+D=Urv1j&hS9^_U-"
    b"B{NwCvV506kdMp!^`94n6`mrLjiW7zo+K}bIL;ia;l9BLC1SBWqiH;m=M?0FL09A+0*1<GFV4!Ttl&wPD-J(8;E8G?5i5r#Qn(9s"
    b"U>N;7mC)=OcO2orVU)O_HdT4Bvg7ykCn9bINP)fZrt_5CBU91fF<0R8fe%`qGJEqP1+Sh0hf~)oy<$-T3Fa7VmB&g4wjT2a5FrL9"
    b"sn#M(%_U*ro&L_>%&Vu89BPkzY}HZiOSF+$#(;>_6yP@C)>luBYKrX(^Py0WqjGS$ZTsdhqQkrZq6{jWKXc-zL{~~M5ONW_n2cLj"
    b"kSCeHv5x2{V^mYrBA6q6y4s8C6$M5{^M{X*4SKJU_&jWOUNEm3XX&4%{1sx9!%7)DWisFhq`ex!7LvEsib!<%vKkH)|D4xP*$CN?"
    b"3Ww^i0&}JX%Z|-qvBw_}+LD$PvM<ABZ8%qWo2aw+=DSjNWUxR*+XOc!IGCD5W^@;2wRs^B1I=9P>4Yq<ck^z9<;BMwibR4k5BN6$"
    b"WKn4}y(Q&)EJKZm*qaIMWhcQ8sGvI@=be|C0{LuEk-27R_uyXT%k|dj4X~a{YY8phm&)~%O(T-tviRV~dEWuSezb0Gwm?g#A1{o0"
    b"7Hl%CB%jI3Zlca%21S)ckeBGFTdCdTH2T$7=$U|zJ{7}7Xnqb-e(d0j;z~;7^4k=yC*`MYl<##>h#Go~pj!je#qrKMYWzC39ZyJ7"
    b"Pe}VOGJ8i|Ce;)~HSPD1Q2cuR^i;?0p7ycW$C>Kn<-SR)uZ&k=AOzGZrq`xWC3CoNE{T%{#(gk4R<%T1?bV|ka<XTomWp}KL?MZC"
    b"1k%sPYa@dh4y4o8r&2%}ObBQawZdL_dzEysz)s=~9GYnQ5PYWsRsbsi)pJ|O@QDAdZo*u|5EihowZHFGw*YA!P%iy$30j{&3I?Sa"
    b"qEo7&(Micz*(H*;m~$Ck*qFArJ-YX^TFj+d(88zABIy+m4y|^Y>5}{so%v@E@6O;io(_jN%bGxn?lOkO)AcGX%|66NPs|GzNC&Bh"
    b"m{q7op2$LlosLx^vlGrI0hM%~{ANN2Ie4H-v-VxF1LktD9BdXv9iXnSTZ0&c*}HfrgIm=HEL%<6%49Zy!83HPvy7u#N0Hnl*MpXa"
    b"=+B|XuRcyX&g{x4Noxg5XJ5_H*;$sZJ6@$4Hm<U-P&kIM+rP?G!-7IF23+fA$MwtTL;1wX-IBa5f;t~b34wWJxj=2jaq6f7$J%nc"
    b"yZ2ZBBi|YtICcHo9#v~miq}h+G+m&M-wh4O96(BCBE#E|>=(cy*+#)-eZedxcy|s?p*wXXU_4}kZ}~j+af!IHF1H{@rSr1A-1;8d"
    b"x!&V*3NJAHL6_+GT@d2!3j(<r#=YKBJBQkz{eNd&KfK`rQ1S6L<A36aw@wCPSB96Ep(5d#cb+8rbcCoRt)vfI=;(bz4>gpwKs-DN"
    b"*e^~!$SPidb*08$8CfpOHonY4N<hs@gYD=1px{<)Oj;#WScBsEarW>i%!X89R#0Z@+mxJAFp7Uy{p-joSJKJ;nR{h*bQH0$|Cy{^"
    b"AD=QHZR50~C^1(J$7|UMe!oZ%l1FDJR(Ik>RJnq0;s5;#whi1xvii2_lk0&JDI?B)xBSAVaVnNn%@kN2&Qk}EH8q<622FfY+Uu;S"
    b"ecd@3v;3_Zr+o5AI`jF0OY+L~WcXyOf05h_4fU>A&&6#zb_u2g5x=u~{NCy4&w<t#^k<IZkxWHMcLMyd2_IsxZym`!k9%q&mJuRP"
    b"QJpBq+x4aDPtxXyi>CrIG2b$m$Ki+S2x!G3_^F|`R+t$B0af?VD>|+~#U^}Y#}L{h8A3cBo+_*=srQN*P0p-3qkk2DM-DGSn;W&p"
    b"2AC$L?lT(-*m|N1t9J+Y`9dDogVPu(mh>I8ma<2-TW$oBgGkjZw^I_%Wmt_u-l7|7;T{EJn9s-)DJS6?*ol}>`=<wwWni%q`aRT?"
    b"nY8hL(@uQb-^muJFA&YT9<*Qv^P0Tu0Ddt}N(FbS_)lPq-92S@U;7zR3K6HpPDNoSKaiw7LK2inTwvccZ%kLQ>Ma_opB{utesJk7"
    b"yys6BEg4Wds#f27{;74=AmMCHKX3peHYQ;fh|oP3TzF8VpXi?JXL<)AhsdLea@skaW^%*3LnsZd^B<CP;cLNp<`tz~Pd{5f_z!<x"
    b"b-VMB6E8Qz>Df3}U68f}9^|+Ah}xA*hN!?T)Ju@~+4P}7M~@f3PSnj;_^#_QH{?)CN$j88KoHF)o2FV0Vq7y1|GPRw+8u^}h|jv1"
    b"ztR^l3-z$_4S@kJEvj~KI+SGperL#T^9AhK)&Csp&T7heg%HN&)s?;uMiX^rhs9OWm2k?7EPI)@T9uFS-`V6O0uQ*oLuKvWUeET)"
    b"dg<Z<#t$3xT{|Mx1Gbx(I8HiP{F#I4hY-^}wF#z2l<t(}#>K1t@``JLbQ8Ud`S-UnlS0ZTyK@^qDdi9|ID&-5(r+XtosZ$uOk4rP"
    b"$FdbH_CxHR-DdoA!^=j6J$;WAj_b?L{ZaNL)9CAY8;BtDNiWyZfX@;Pv=yZzV%H7yvihn=!MQRRL`w<^U&aA}Yrx<z4bN{*PW!t9"
    b"{1=Tb#?ptsL=fh07xI-zH%Pyi#}Xm>WTB!tVoZ9EFOh+pXY2UiBHlx~Yght_+_s^)`^nDWzONj!&)T8TcpQP&p=l3FgAk|4|7Uc8"
    b"Y2s-^&B9mXIg)@l<sWA1Ed1Ie1S5qSDy4n*8rx?1A$;}5y&O&m3s(_-?vJ;BY|`%(3End65Fb2Yu|s9WKfCx{u}&A;r#lbULD|AE"
    b";<eG>3hs}BTqlgaj|rL$vh@48FMEMrW%Tf?5cCvm<-sB<Xqzf%&j7kS%+KX<c`t2eAKsKE7>sts5qDbX9i=2_2k}w+d$YG<_>PU`"
    b"p5g}=yrsk3m*I3~CD7hubxyXGD;r6!7)04CSw35M61D63k!E2V7-wG6NZ;x_0>`}pVs5;Pu7%s963duKukM0_7+Po6jaJQ%379lA"
    b"YB|bcCSk-z1gVw1iMA}_cpoVjNDoi0QOnRA|K1g8;<1F!&Sx;I8=P9S;%9fTq4ri<d4PzcdKy^eXa4vd7FP>G-$EG&8?6#cr?9@S"
    b"(vQ=dm5uBq9S@8)OB`i8>6mD+iFU1;5wH%9#EF-Q3EsaVoPqnhmIpSF6JoMEQI|%VQH~aCmAAaZpMgx+BC`k!<DE(!DA4L74c3*m"
    b"ZpN#_uK!up+U<;{_JnYFQP1`4s{@q#L5^mHV}cK2;jPaYNJ-kLL&>DYYMzkteZ}NN>7*J(Ra05SoTT>jp6?pnFw6Ti+UfZ6S29&1"
    b"dkI)vssJbIbH@jpB067a+vy?^Zub)a1-l_!4$w2wq6{Da71Z9X+>&#rJSKzb2(L^u(n{>N;Nf(2juk7<hwbV@6HmvKeVB&YuAk2f"
    b"Ay1y73DJB-`-K99ngWO1?Lym!D`lhT%z4>1jbCMGNiA<RG!%*_?1}9&H91CB%xVh4;qFDZNNbkS1Ec5av&R%0;T(*wAB|_i7@j$m"
    b"$EHcqb8T0xfw`A|1>CdhXjX3eFe1tOyY+=?WH;p&)N@&S%Shgy)+q*wc(zu0soJ{3b-Y~m0c)-@@H8KR5_smc;-&#)yhUxuzgwo)"
    b">4Ji`5gGLji+bL0zAqxHJqP^BqNh#Ks$SV4nQUt~u%wWCkW3h`Rdv@<5zNtC*y|&Ie`tJB!hJYcKgF^Bt#-YTXri2KO#}}!i7vLF"
    b"RXBAK7jO0#Y{4lx#tA07fg`+ahWcOM0af5C<f3sVcym_8oXE}-amzJDEq8ARGA?k)MZLb7e@vPzAw1q&KnqX`+@~JhjX{N1#<<nY"
    b"fqIc=FvwJsdzP%U_a0h_O#RdJ+5y&E8feu4+krrgO!1Ws+Ec`^^j>c&@f#hrFHqAHaLE}xA_={5q<6ClfW5>ziXK4#IfT#t8aA4V"
    b"crbLVxkS&wIENC)Iy+TLgrRiV)JMMFPGqn_nH)>}(DFkn$~gP4^ODPY%f-Z4g=L|U*#)N<w3v8tta<1oEeg=@Z8BAX<B`xy@{*p9"
    b"-_)ZMrTKXZ>h4w1&WOCgWJ8mPDq%_SgYNQS3T)p1;~y*4FMM!FUCt0+_5T)g656y~bas{OW$FhBJBU<lm%e|FfUu?hLthpK^Rhc&"
    b"Z}&pc*DKAWLM-e5m;UWg3!$>%4m-m?yYBh_BzT(t?M1SEBUYJUyw!ErZ)(;IM}F>GztLlbj*n-Z{9)M)70wD+pW1CBT)nQ+n=A!C"
    b"Nh?^!h9XekF(TQB&}TkL6fLIY=w7h45GJLtxEsezrU_fDl(yW9Ku`hHJZ2G3_`8rH8R}meKl<6uc$(Y0NFHJamAgAe3T-w~OjpPt"
    b"q@I=3pN%z{ZC)g?<4akV6&6nS6MkDZa!>VSB)Rtiu+l<2{P*){bNT!@4JfqONT%Eb8KL6Q>j=c9Zg;PRoRaHqhC$)N2}43^Hnmq_"
    b"tB88YxAklo8&>A~SFeLhJi66MV8=%VkW%QC^6*vEn^WUDyk3A%vDCnheb#+KFV1EA-BGPr(bDj6(}*gVPH%{ZEotZht{;X*t4oN="
    b"JJ#x?%98ID-!90_BVH*({PNSz-0Xbm(LV|Dh&YDZEEmc!c;_RXSp8oG&*omo*G_%XI6G?+y`f3!7}1{H%)2_bc!b0az7Gurt!CX&"
    b"8l8KwC%TJryU+`IBkwx3`Z4cHAWmeP$`RHomeA@{z&on-d^Ct|Na{E|Meny`(mF?Z3L6(Mz5GA&nE;0~C{Ugv<HlL{ql}APy3K_i"
    b"SY%le=}0>MfGWgjMwr4BV8U*TJuF)am1J&l=m#+SMH_9A%9&+>^Ic9>cW4LZ%j7pX$^n^NqQktIrT)huC}t|O7LQ31A<nn<H!%w4"
    b"92$@l2~y)29m?rBE!x{3)k?CH346^19xqmBF~{RCRR3o<?qT*;Vzg;9LtYDvgUTVWeuQAj<oIE~Qr6R=6lK&1dFl8=f$))8M5t*w"
    b"8qPi9ZBA8mY5u#qBlTBlriZMJb$oNC9qxqU2@y-pkkYd1P%eCzlALA_o#n>a9oS+SB?dc}ICG$O^+IGc2hWkl;%Yv-J9Jn);eMH("
    b"BO4JsYo&id?~4GLEZxgrrbdZMz33Re3*j018PRYm5j`X78?-J!KPBaX>P(5*P<s>$(?Bd_F|#v~e99gS{;*S5h%9h0NcYB6%%NfH"
    b"uS6$pF`xW3=ouqi$=U+724zI+;0&X@x^721^16d~>L06XS~Re3ZQ;b{{bfx&8=ye=2cwnKkum3ynDrZyfHpF7xr6;>U9H$?uoe=k"
    b";z(IkMB4$~(<`h?|L68q!BLH;ab8>I8{-Z}g$M9kA)fn*9^!-ARUd9|3EVw?Z%LXI&1&@!<Lp9>@iTOr=f9B!H+-#oc@<jgnrA|&"
    b"l1)LW98Kc9%XbX2IDe0%vE5y)<Wm8;I}kAN-n_X0K~yLZOVC6-CuIWs9746E+>;d(cP$>ktv1+p`1^9vL%=;{VZt8H;VGk$<bt<j"
    b"ykkoQ#!6?pXURDv=5Oltt?kT0DZzu}P%3isuU@6<TgsfYtD_rwW0-3L3>Cq2mfT93ltPkedRx4x^=6hfCqUWlXZFmPO2#si(LFfI"
    b"LqF2zl1Q@Qh&+p=dzBm-64onsNe+$qCa1%F`2t9DBCsB;j0Bf+0c!m0)B$v_VM(sG!O(g`dEJ+%s&utrj!g1_Yu1w%np%1zH-V2Q"
    b"W7B_X+K9jifV!p7R-W5Ht$g4B`M&2BL3NJh*-iFhBYqL!4{oFT6@_gw2tW@^+T~zv-S#I|JDe|2v$!no94s6+f^Hem<%a&moC&V1"
    b"oox2=@wARzr8uq2K`H3EG35cg7EoELiS(-gxcIgXhjq7KR6P5-IEO$X0zDg#NF+NDj<#y|me2VnK@B37UNI_aj(1V9PsJHdQcg<!"
    b"X$kk5Wp2d)Kb;_<Ej-{0;6xj(GqVmASqoaxH3J6I!TbMRG^e=ZBCa(_GYP`A@SWVYpTVs(8<JHwK%&?bU<x@%%ES&O3NXZ8<Tdtj"
    b"nm;pG+G<U2S(N42L#We~!J7lzn)m}dyLNsMZ2mOz5=U4px^oQw!L%;)5SK>Ys`>NI-&0PX5QPox9swT(?83Zb1(A3C)X$o5(nRLd"
    b"cp@5P;Y_CcJ}^zQUla%akF6(3k)C+#T5I=l1u07PJdSplv+?csgn19Z%yQ6Q?{{%Y7RH1kCzxQ5lzK0CoD`BU3O()>U)SZCeo6=o"
    b"=k5@ZrtiDTU=Lv#rSr%M1A{qs1`T>4XL=hm2cEEuKd^>xm?r6$^m{~E3AagYa|LCdT-z;Z=cQP<v{-;^H^;W}WNnP0+@6+gKxYLy"
    b"#Qx72{T&9xWtIg-r248^+afgM;xP3*25}?S-Dh!#fbDG4M710(Fe8Mkq$2~Hh$d&-eK->^C$LN92}Fy(8+`1-h8!r|AEm0Gj-z0+"
    b"7#&BnrPedN?v=~xxizZ6m6^Wwys>6IG}c3pGN++o4|)w4@U5x6T{pU^lO1#LmAkr(d!Ttd_nJ@R@l7%cOcd918!jemZ;o=z6f<F6"
    b"JPJF$YPNiMaB&eK{K=djeMV%%C+g5SJFYR?)Kqbt;Ee~%C7mp&`@n@NI~9LaBua&P5M^|2v#kv#vICtO|MghVvz(Wp?-csl?x_QP"
    b"O4NJkj6Yg3*zKtT4#{g!%rdRS7{j5F;isS*L(n5w;s4g*oMeO@S|wZ@3~2yiioP%6J)|cifU6o{XE_+Vd(HKI9ISnObB;P_tW?x2"
    b"e2KF;h=W>I3cqZadD*LJC0vF6nV*)(AoCw_7q)#!YcO2(-u1sYTDi_EZFL>l%Q?h}$(|HihazPU@$*P>ju|1@QDQn}BGtPZh&OgR"
    b"{GNPxqOQhS_rgLP6T3sDXbbAkx8Y&}155Sw{k1aySV36XwfbE{Hd4%~L`XK)FTTcCh}g^rFVPl?`qXsZezX&4L*{B+c<bRdae_lc"
    b"p`-sH5KnyGiWX$oep@VV)bE@_VOJ}d=Q<WNA_cTZwgbe9lT>2D(mVKdF<ySABm<gKnWw!{XWQ*`PMxebidE=%p~V=&IvfK?B@}U$"
    b"RGuRAl?G-HS)+-V6FY_hlU5k?qXr7ubXgRekr6I;9-UUC0x)K@klfA=?5_vaBCC7^-zO1?kK_vF7X>J@+1_hRoyE)vZ|wLb4vPRx"
    b"K^Ggs`8Khz7TfriW6`&D(tTw#8XZYQ)xY$oAxLjOGo<4Bglytt0FR<kdVeh0#Y!ezrj_V$WLq2{xM&O+eL3;MMp9bvTDlFY;!XL3"
    b"AL_W2H{SeQIDr9=D?yCbaHjYvyYWP@3RT^ph#3XPtB%-7Iim|H%OHrJD1WCRNOd-q?yPQqXLSuxHbo4&b?rX$%_YpCS;fIe^7<%&"
    b"G8hQe|Ij$IQ9B191dr)!*_+biwfmHm@;Yf>Dox^eb3b)S%m`#*k~;#ZhbmR|8JI;ocEwlIoPnCCk{f<z#)5nPvUaW#6+0@keTWe1"
    b"8ziD>WWJvnlzi9chq&(q?=4VcZX)l3y2~X=UTnxcs$q&SXAxtt=m)xD)M)~*7ct+cckPP~CSaNdy~%&{;Qa#k`BUZ!219zs^u$-M"
    b"#)tbF7XkLsyfku@W%Xd`{a20M(sKQ_EIW20H{Cv0WLIfMJiE}I0{JQBF*tK%n<EZe(e5!!m+#pk#irg+EUg4*2HCu_-GOZpg3mb5"
    b"X1n)#ByhZboN-h0LW1YR*?fuO*ec$L{<ogKTp-|Z>DtYpNW|-<)9rh2PqLpNH0hmMD`>;A{r{*Yl<++Y@V||cw#djtH8ER?gv3!y"
    b"U<(>P+~)np6M0jJuuWJRKGG)sm%<xhE{hq9tuyMYe%g?<_aGs`(LS>`@wFo0UfiV!Pou<^V#tSqSF(re<JRE#1M8&rGT_;-`n~-q"
    b"S+EHOFw>4=zMA!FUHPlzN=^MCVYv{519&cg<Laf${Ncd5tgPj&S*~OJbLC7{JVfJ+pZwhPgn`D=li_9biE@^)BYm|9of2db#yxj|"
    b"nm{My!Iem@bOb~oFzBg~H@5b0W*pKv7QbGg{ZKtg01et6a7IV{8RQcX;N-x5fqQ|~>rPC04}F}tfnzOAG<9f#5^r*=vA05EioFj$"
    b"4gOnf|60RXtJ)T|<7EUcYh?P0FyFK=xqfXc!5;2x8m8oloXuuMPcOg*DDek=1j5KU1YmCx`VIVpr#0fUI{U)cFbZHN-tb@(H-A9~"
    b"^EgDd8RLn4Wi!kS&=&Jt@%-Ajhus7pEQB2+q6!_wDS#d-*=;*B6d!-On86N&Q(>lTcoI^jm8UP_q)nz(+V05{+Eb{+=u%Ei3s2A@"
    b"m>-g;m*#AWxB+b5=fQiS5z7%vaRRx3H)O9Sb>pFE4lArgfdUWqb!X^w8L_*eic1Z`f-G^tXEJ50?n(>JXN-N>!|!Kjlb$STFalgI"
    b"0n{@|uu68Yon9o^$2bn&nj!oUEylz$ysl0vZj5}HFII=McWG%N^l%IKRUO>9TvB)z;`$4z9(-7AHT@e|GcHf&KT#xbo<9KKV*uH<"
    b"<HrX#BO)3_FJA!QjRuxc!5hNZLqlC~Vrt98!6zX0YgAFTc}s`RzL^!@aGxdFrhwOG_uaRmp`Oa+JNDvi@Le2#x<w;xEMrdt-SktO"
    b"`utS=l8jkOs7H{ASLY=$1FFzquv1r0;Fhkj%1CPtmnNb9G-Evd>UpLZvQVI(Clk3yvtl^AfPbR^i&<Yq&Q$qB50WQ`4ClRg8E$7{"
    b"@nG(pKiG2ee__8JZFR^kcb^0;6~121I0v)hiQLN+3&^J+cScO&>E^ma-5PPa8ij!YwXH-C2eP#szn*2y?ft=nNK9!79zlE2{S;V7"
    b"4&{cFL#_zoIEgCq-i&NfiA?u;&hlnArl(+ncCF2DI=GOK>7ky+KZT!_G399`n*vi5ho7FZ4ZxOK(L)lh;j`;7k%wqi0sRna!a?Fz"
    b"i<KU`Bst^8w6cIY2W-p8GV)J5psHLR{i?$M_VwbT_0+)*ZR;-oCc#?yq3w@uDD4eOS3mYk>;SnbY@7nd3x_SVXZL+F^FTc%Uvmyw"
    b"P%AT<VH>9TB&Jl;(@01Gn{!tV2Nw5q2>;A;@Ho5)z(^MxsuqrfNsd^Wz_F&dS=5Y+dNO$mdP*zibW>CTGRT9d+Oqqcl=pBjwVGU8"
    b"9Qs6zms;09COgzaM8(JK+r-|1xlkTv!ab^M;RX#|U*ISag_^s8UECt|669$Pn7C~8V#m*^gstZH5)$k&<s`IY0JUc~V!^=sgRw@%"
    b"4-+gD&<M&>dZHs4C<TTMsY;`;V-jwkK_ZOQ>8dRT4=L^Fy<OU?UjZSx0^E1lA9NHv0TXizK;Ez1uB9ejnp6$U+zT*58Drtzu3ye;"
    b"V5rt*Bsil0w)}17VSmI`q-(I=TEAvdRjg#Wx~qfdE8`JoPYq|c4zjyRMtGG~)GAhHu}U?`f9zl6fxQjZ72ERJ*Zdu44o7(;9Pi1Y"
    b"%r|s1UV@NHSIX}{%q7oH83O*Y%{C5IvMNd~1%|VY-oTx|^u8F2fein0YagePtzYUG^3(R6rWVvdv34q;YXQ+|(Q<TeXWq$kphJu@"
    b"sx;7eZ!U74@@Vtx+bBpuH^wu;9b5M744(8CKVf<>J*J+J<5}+qI_W|?Z8L4(Q@r>noUSa`m$$4$EtngGgPf^Kk1`W#)DH`}M?=O("
    b"D((tqg?ewm@Gl8I{Ozg~615y3pOTp+P`4(JLy&w#Ez@?n#H4fkox=iv6@2QceMKLhNTZ1c?rIrxY8iQX<Ge^QKF*ZI40}QT)~2(y"
    b"kV%Y7t#w7r=9^R(G~_li9PJROb}>v1BOTq~)2vzuowWoZg90ItxUXkrdD*9m+Sbd=-F*;(y$V27L0OmPL-zQ)d0qD=%+PMggGB@0"
    b"GphQpW9tRMm^K~Og-*rbYt)Zcd0F5Eq)u7M5)S1rdz#cZSEUalm7SWLPyCHBS4C8Y_*Q(~43tnaoyeV26ptX6P>vVs_V@iYSS+S$"
    b"Kt-m1nTv#5TB4hjlp`l2$zliLb~tFw@T)VkZ>EwjN6Qvq5P`<8hEH%*J5nqUE2US4b(~^DrQIf{Sw~Wqn_w+dp)uy;U%SMsOS+$}"
    b"=~}+JCYCEl2ly|_KrGa(JW>+?OqM(fahZ~2j4Dtvv%s1RJzB;2$*Qhro?_dAoe4Yb`Wqz1`UY1l@m#qYcn+qmomtpP4{XbCG^enf"
    b"Ce@gVM_sgI9RK!s)TUh})dbu;u0z4&Z&FZBt@^xj*GeV<?x{jIZ+VGcLBj13#c@M7ECVd5LgR!|H84m(QsPo5YOanLMYk{JOO~$3"
    b"=(Al4clsh=1rfP%tHOC?#pD6sNmn8*y|P}L0Z4cA=kals_(7%y$H0tS?fdt>F;{+?qg1Wrs+4M^sNvrafG0z`FW%Unl$bqyoM<42"
    b"PB*Pq#q|b~eUf6i%PVGzN2MVbkKle%N0}2)whxLCH&g|d<3Z$WW~SQEWyjnJBGD@zk;&qHcKIWy{kT`*NIk=l!nLtZlXy*Kz<c=j"
    b"?6prLMfNyC94pMj$|$hY$rflyE%#RwkCpe$x7V%|2VRJmqfZNoqD(*f0}3uTi;~%bw5J$~6@9wi3MXN-8^RUdgAA}|ADrRs-2B#="
    b"%l2-u?Y+9~0z%-e%G+zV&QSmNbg~ciMSDd1NazyEOs1J7!MVhP_74#TUy$ifpUJPva~!Nys|b@@ZcBVnl1GAdmmzbz$Q5g_Yi-k5"
    b"pUkBnfxL?r2iYL=Ma>c-+^|YCC{P!elS8E@8r+)kQ8-J&L?m}_<~-jY4C&c^X4`+ff>ZutJ}*(DLZ^%pJ$_M^Sk#Z&YbSeLzq5G8"
    b"#!Yc+j+a5=G()I^JbNy+E|+%Q7m>+y_wNLkd2wzXD8UPz>Pw`pGHB22$#PO<BQvG$IT2g)EG_p?YW{{I@U&;}zjE%v#y34>_j1tN"
    b"Y%PK+w#g~;fZg%2obXuA|6jFeD_Fz>S9+TTM6F_M5cd_XS!QWfnJqg_)ymo6rq6=XWWl2e*KLiV>yw;^uR=m(t0%WB3wQiJ>=iS#"
    b"^+B)OxD(V*U{-A+Y@3eW^=S=<q#{4=6?hU!rqjz@xLRc%E}!20o&zGo$<>Q~w27&k(8kRboP?HF;~--tV8<L7q}4}c1mC$i{nV}1"
    b"^M+maX*kuXI^qIK#$d<0k%ok^&oKXF%0lBc8m02Q2rsB^A_reSL=lMAPWMgNU)W>ieT(Wg^JRkGwo(J{c~r?=2*ZQ9thS?<1o5$p"
    b"Y>es#L@|@UHVI}1)m7FsG69+pY`Bv~M<M5IG&Do!o2#|<&#GO)h7sU7e6hS|EFqyKJI%Qq?%B9%oi?CgtPA|Vp1juPi0<O16oPUD"
    b"ud@rW!)`0HejkJ03!_@t=$|I1RqqeQ6PlUHp(K#8ArjId<ACVyZF$vm<b=NkHMBnFaio>3_S{5>l8D@_0ub8`a3{z>e6X0`gq+Yn"
    b"BjSS`!dluf>ITAs38<(le5gEZ$d8CX+#xxVdw>|-<9`=%{ahZMXB&Y2MPp=`u?df-n*N?O>wc}hj9+c=OJHXSCfE3UE)1OT<Nv|&"
    b"!u)8Q?yG=`csbM3R+KH|HL@Q)iPvKWuUo&h#{2B6j9sM{&`}_c#Y^tl@dsF%Z)QJpi@jrA1Ng%MPVVXy2-yxnEf(4&3i?y=vPwZs"
    b"^<HgNZo!#0&pL%+$g$fes@h8QgM+^nxZZDNUA59B5q7?m7`FLkCqFvIe7%zLnPl~*VHF3h4f)*nd~b^)7P+PB$WoKPdjz-n>MLDV"
    b"*R-2+mju0FAgi|)G9Vr!gLk8g`7b~nT;Z<-s3TVUc5{YFPblC6&cO5f1AlANUg$)<FuEz^ZNH+`c}(N-=Ri*n(AFQj>S+%bzR=%3"
    b"EKOqDEWKGzYFBA`j+gK>w_SeNeKIE|>}%p}a)p*7H(HJnbbjBNu#zKKn%K<$(%!{1fV8}6FyLTOd+p^|NWD|W_5Xx&JeuenvM>+}"
    b"-eejAb#F*`!VU=|8$6_PReu4bxB^>gL~SD9v6H(a%m0SCv6Y>BdXRk~{-+qy*AC3z04_sLkTfW{`MiAJ*xOgJhd_G^-7)P^l0>rU"
    b"G`^s+luw-gJ`D6*P?tDm4lE${sF**z#fD@cgZE>uV!k$Sas$PKn6PL!FK+BbG7Ka|Yd^ZXJUGIQac%CS&8Wo%UmCC=CWhDuc)Ak7"
    b"zH%hcqUv*GCY-&@1*TdtS`{W@HGzNOP{`c4DPB&7$5k(C?c$-<8F7n97E(=}9N^$`@t-H+sb2K*5sc#9<!7dyyH!`lOu))AaMRHN"
    b"laG&GJA^s^<^tRf+eN%uz9VyECq9A1j$N&^I=Zu%8mderk}T}(c4@(w0Q*M$X-V=FaL5=u)&V*3YGHG8{9jE@hn-rMhy&e*YXTkF"
    b"=>4y(IZ=W{n#=rE;QM&7{3H;SN==H~?tU-WvRptAg}xRJyo}}0(badqL<U<{v>_5(MRa*mH5Sr}$MtJv7x{gS^&6(%z7akg|E;iF"
    b"XXl+_DaLq9>rq>&lfYI88gqc#w-K(qXD&(=@&kkF8nyTZ{DSIn2Y%VFSW<Xy#)4SlSj5dcyQK!whUT&eL{%q+>ob@?f<k5OAx0C5"
    b"^FiLdL3!eom^;!^s9tdXADsnGOF&uhN*Ty$v|9fgmM<^Ym@`N=ni&D*`Aa%cFKxh{M)0uIPQD(a_}-$4pAR@Wuzg43+rPcbMP?Oc"
    b"TJ2`C&iUhy!n-V(zvjWPxA>m4@RZi$=nuGKsKJ^6_bsO5Qv(_+)rHVS8MfQmr-_%W=Z3%|{^R$W@R^yeJ)Cjfc4g|130<Bz^%W4e"
    b"H>j)J3iBfRPlONURbyNvjJ6<mf&LC$p~#CetF_2-gDHlwDaEGP{vGb8%l<+3pN-9mp$|_`LwbF@rwv@5_avU(b^1So)HcVj^jH!j"
    b"Ob88@-_~3>Pq~zg4xk@^4`LvtbQ`fPv(#&Fr-ed^Rp8(UkJ~7lxh-y&oiVHlQ@Bo)a4PSJ)B3!xB4S_6F^5!oQ~-#m)*N9)c-2tQ"
    b"tdi;6@p?DtD4OC|_&#eaTxowb{upRbLvemR30<txul!RI*(CER+qd)Y3VKMPB4DgcXTS^HLe8p-i{>?d3dfW3rYV}WJPryDHUdd@"
    b"GHs$3xFzqxcW)z~^7%SLhkC$;l|qQjeZwG+!^&D2;>{*VMv`n>h(ga$sWS3-npF4f;j98kBH+lPi;JhTqYA+$i|T5*@>maW-5>xm"
    b"u?G`^EUy~AerfKDp+IiVX&I0@HtdAvL6N7u%i043qg-Q=l~@<9JEWwl)U;`W`vXlBaAx#$TZx^9@7(k`QT2-5Gp&q+R=U$eF~IPV"
    b"l+*7|hV#?S;cyP`lYT`kqFwb!tukGo@_93VGiA;&osL@8wu88^@oo#6!;a`(3b2HI+>5T=L|STkxX3Z@FxcLd^^vg0BC7{MwF7+^"
    b"PYvFYhv#TjXuzs{Xn9-5;P7^^@8I-0H(oyoa*na;GBTWd6U&`cH^9<0hqfobWoJ@Ac0$QMY1r%_R+PLci`e<?Jp#Z&R;?3;x+~+i"
    b"XV^C|MWNJtZol=$3ypR>>MNJ7F!MbkU&i{WbRwu|l%=W^^3#5OGl;-)>5!U>sf}NDXTJ=xa}o;`A;Ji3H@HJ&DSK@eO7;lTTY{Yu"
    b"%+HzxYcW6R<B5;%NLW+7lQ*VVh1Lr<oTV34gZ5(cJHS}QfVpm76+EZ=i=IPO1LuI|?#Vxw&OgQpzZ43wCCBJohsqSjhIAMkGQ97m"
    b"wkwt!b<Yc&gFH9*)`GueG#^Ii^T@oJh>YijMh{BEI<;;y_40D$|Mr28vIelOJ5$ulig%3h!ctZvuTH}Fw0%Z~)SeA=*nmU{R94;3"
    b"p#a{MJfd@~@7wGXL+T;;rIKCmGla&4TXiP>APE?jBjb*E=J91UA-@(!XP^hBBjEH(ps5xKe71W()u~<^0J%g6gSG2dw6cYPy$^*9"
    b"+A+Mds^W^@+-l0l4&m+n0Z7p8^KEm)i``lOE4KYaYtR$<yY9+L$3jQ*%SdQG$L-N4)rn4M1*<Hb#?uSY{sQZ_8b`m>59dn7Y|4-7"
    b"?RmyQrqkqn0eHuuQO8{!Arekb_>wA6%dM=zGtDK@cWtejS~;Xidfo(3)X2H?GlcH_juo@{NOEy!@sqr?I)Ok`c+W>h$fN{{!f0}V"
    b"sCfdikY*!v(6MkPVwAHA)3>;)JKNtnJbdrS{1NYo7*|HuygNnS&FCuz!ig*5mp)D_a6Q$>t1m2Ccun=sriydxlsHPCd#HYN!b;WD"
    b"Glrt0JG|(u)~g%0nRAgJr2P+thFqjoG#d*N1~qu4&vz+sL)IV@2_0Kcqv{zWylGV8qd||c@wqHvF*#XLw5jD_7*m(YC!`HoJ%A&U"
    b"0Es+hT?|&tH@KtZr1AF%?haZ6K_Fs~X+{%9F@zPN_dfN@x^;Ge&|Ot>u>U!2Yna`9Ask;ymkR-KqMo)?R^>DEyhvnO)2`gF_ckk4"
    b"Tp;AshxyO9vA)V(!PA7AqKQPAY`g3?u`aKZt;m(=p<z<-$Q4p&4b>>^dBGT<+W1QGN>hHj@DMJyejwH1VOdaOGXMZ7BPw!YCmyC_"
    b"%2b5K6Xerhl$QqmBnb6Z&<PHr`(x}eyF6XESJWoh0ag`TqxBt)IVSze=<F}!*Y{EGx!6*py##t+r9E`T{a8_UlgL~R7CA*9HBM+Q"
    b"W13iOLG$Xe)#GRgdn%hS`$QNS)Qn{ngel1-vxxw<n~j98N~}9rah3gty2mRDIY1oF?~#Y7ImX9l|2cef`)F)l1cl?HPpz{NlP|2g"
    b"Zc_L9L?(dT^9|FIJkAzzBg!wKmBt)RlZ3h(u7?HFeXZoLG6O7Vo~z!Z^CYy8C-C2cnzgMb#6(r9<H4_ogHLx6Vd$)iqfo}{H!kGc"
    b"V#Py&*GYycRi0m>XNEmyO-j_hz$9;kzy!omQ`S|{*n|T%CDUJ>0WM(m{YeG&tTk?&NNQbR1)5ElyBk-Biw_YHoL(JbJWuusmm37Z"
    b"axIW$uu;bbP?4ZL0dD7)P=8YSFZ8D2_%h!hg4l0Sbly@5S&NeEi(7X^?(_8F!F_d3Wxb(H_`UbsfJ6t66#6N-mqX64Lj;a%g}-56"
    b"@lyU{^iXXUTLCK;GaB(9;B+K`8m(XVIS?p5PqFg0;^8gY>~^5=f#4r_qWXF--Y3nhUk2Z~&t!0=ba57}QFFvtyx`)C1U0nS%+GJ;"
    b"n(T~uht`o!gFVftkWP*H<3iNJ3%G{oz4og6@^PO0v4S3AUXTE>cfyWIf_zFKP*}PBwYiEySa`Lb@{k{W7_B1kTH9d($a;lQpwtSG"
    b"$FU><(I1aP2L^`d!XhexFhvB^J-A{dq%&9(G2TL;tz0a&k8ymZ6)CK_%qd7|^1`AF(j6t-#ObTEj6djb@TJUrDYj$#IwwZ}Z)W6u"
    b"FLJNxO2>6DM@W0aEYXxb5}NLLYETt(W8_gPI{0AR=9_NQ^6U8O*C@*v+oQ2L`SJpRjF!%vRnUl6;H5#TuhZ@q1R~6m17xJL2QM?J"
    b"%w=&${j_lK0<&78O6R87;+4(8VH7OGs`_1X{~G<>6BD30Y>Ty~#ZU-KS|APd!z{1&@auZxA;)-p_V;PPvy|IRI_+s_O9fp;xd*v2"
    b"IJu}&|Jt~C|59gDlhV(`#Af(hFW>ZcZ1Pz0&6GHs9FrHw{(_vcr!w$;mwy<Zsfu-eTzZ9~E%et7sxX}DM^7wJy>|av>C`x8@4Abl"
    b"A~w@kT~FDqv!a>{KHXNOIALJhbGHQ3=x6LSx64=U<cFBV2m;p5eiIl-<t%bpmZEt0tD6%(BFC5k(*3#dK=Y&WSXn`!ESnoMG(8AS"
    b"yat`cgB%vjtS$AA8*%VU5#EDA*=LmRRw_wUTCqLFe;K*HqYR`#9oB07uFo&z>#hEpXCI9};KKD=qAqdb>Q%gogw)1U(L$;6oW0Fr"
    b"?a_mw7sq;~z>tf62)<$5Ga;kIFtVH~(A@*-J}v(;M?#|^S7u9X@}N}0Kh>T3J4}%I8f#!diRko5=wlH29Jx)9R*=5nRxGdvC)UMj"
    b"=I?WU{(S8<TJ6<$Q818!q_JEAsSj<pna?dX1kv;26cND5l}GZK{6OfoUpur+ktG@^84ICY3=f99@gIIrXc;`n9tdjvdB%dg@ATXY"
    b"Pi63b5(JdI6DGaFl}OEAl)!}=uoSwQW)h#~0y@`J<1&e2xI6`9Urs#Tq4f!_H1#?3*pgLpUUD%oOli)2X4jRVFpgrdWN}Br13Z4p"
    b"CZtf5;v+tiW*6<iFM(|GQT&+0RM_A~_rW=Ye&GH!0XT=&j|*Om;;1r;cD${)BlI-3N1%=M;_fu>wa-*^iF1S9SArEia3aThI!E+8"
    b"^30z~b(X?1?)^Ys2TYJGtpVgScb}i9(cL1mSU?<1y6stkAwkq(i7N&4#0Ne`D!%~?AvyR0wN}|#e`=&@<&<dL4`Y)-o=;o*Mc!{Z"
    b"2AlZqKlHD)<#z&v-i3F~gR<D<a$YA_EiFCIzVVFH6aN*KM7le0onGEO`;F8?w`fmJKhiOklu^osJ%DOlGD{m}8zz2=LkX5v1kq?V"
    b"TR`8uLunOuU+PTbwo}NVPsmbZ)*i7KtHheoV%`BP1i6S37^T+gL9sw<1xP9!U?=te>VbVysV=o@*Q%%}pbcttD;!-mxRj9u13olh"
    b"{q$vgMNDTGLH|NUBY^e^$p2G8$j(?Fv+o7sZBS)?(PrxXu=GLU=e;N#8ZMQpz|nD{e-?pl0UjSJ{`VUpmDRG{??er+3juRHskK!o"
    b"(EV~<I41HJZ@+3^@B|mcaw>USdLMn9%Y|m2L^4>3=sJuwD63skZ5ly?;8#f70|3lGzMN^G;FEGiFh^VX1g^OnhP{7U%CNlkmeZzL"
    b"Xx#887|?`q^z!XL6j!uWbg|q@@5weLdbnNaEt<GJw<gFZ>xBve0ETpQyPvkYo7i!p>`t4F?3Mk2CDGZJ)mhUWqCRssgIGCzAZMQF"
    b"%C-E|IfuUB5q)g4qD}dkKaQoKhIy~Qp(uuF#-(%&7Q70#?aL7HX|_g$sPge|z;S+)EA!%1K#xO!l6IaHN87xH2m9CyNR$le1s(-b"
    b"w(ClF)?7^shY6*7!6g9c>h=q7^y`MU51BB2w^eZjf9)59vO{l?M3FPq00HEWE*ueSN_{(7R)7kDGye9v36$Ch5$11g0fv3f!xL=C"
    b"RZP0;BHoy2O3BX0tA2@^p1@ELLG~l0Fznl|Uzwh3VLOsJkgphK27;lr$aU21Z@^Iug3iWK#~8J)eC9O>L`Y(ll#@oiT3vYnTBgx("
    b"SBUFFuRB04K<ZiyUy3w_GIuQ)6N{Buf*1!XM{{&RV%4>tx;(nE@5B!WMI5OZxFLyJ!yA5>fSTZ5F3SjG1@SQMJ>E%*MM*y#qT;MQ"
    b"@QG8#zr##epXLiDibCi{<>?#KhOxtv)flp>jlqVIzxfq5j0KXO$apP9?I-I5qlg7iSUT8;RCbA<x2916w+~iI9H^VRNSL24Vz-8|"
    b"<-`ujU%o0+Bv6NBx2o$o`Q(X?bD?%;nI>jZf-BUbzahaBt5<Pv&s|<Dwd&&#2+0a6x7XBpPcH9DE%El%K#u8=x6Ec2rYx0RxwTHb"
    b"I^qH^gU@rfc#w1ErC4y&5ae-XB-V^t1IAI=l6~3K#85t|<QwA2^%g2kM81f&A51c*!VT)kkA*$8e9{aw-xW9i^NI_NS$11F?Po|u"
    b"A0FM(7}E1RH=%xe^Sf(1`|;?Rz8?7$XR+JTPGxM3jC+~fe(7RD4CF~M|7)?>sV@>2L4xO%XouOii7(?e9mfJH0&5D0kV}>D*N>u`"
    b"$DSiYfc+4?`up}M?s|G<HT0_6eOEHgyQDx!PTEU#Dxz;MgAp|tTWV`EX<ku<K~A!_KJBOAXBtRKqxXS$lw|RfR%dZ0*@4%6`gY)g"
    b"D2Y=(SIr*?*C1F0;K%!aW~8QGl~4H$W{I1!L&N|MqURH?U1kitu1oR1WMmAQzxV@(-{)+p?1nF3#B|0_{+zd*5LkWUVGzvPAxT6W"
    b"uKS4bES_83NhFkOT1qdxbb?_nDhd`M$Mfb5(~Tglp}WW$Z$G2CGLvwzn{XBl;}vNJH{hIC>y+ONa5Cd-5CF_seskH?vTh->aCLKQ"
    b"D(kH>eRq1-QY=&<`>uPthF?#K9Asn`!XsHBG3f-C^ppb?&RjLLyE&+t!~C%vFBXy31?1J+gckCW!&MGmTaPYh_VDBRWT{eNnP;($"
    b"c?}(Av@rhyeTn}@vIlI%crIx!u{<DVRczY5UtnC~7K<!sc3b<P)3+qDSn<KNwE=rf_M+oen7pEdh8R6AY_K)()N96p!=2p1l${r+"
    b"AU(?+w$o(5X`Kcw5UM<7S6^8hxUiNA-jr{(b&RC|il4KM{iaKbT%^L~8F@mC0o=7Kp_WJiaPy3SXn*b_l4qg}t0$vcF?|dENd|x!"
    b"M?{1aXX!-s`+^&Ac>T2gr9CE{Vc6^d!hSuirWQqawmnNGG}GXjuAR_RRUwe^m<}r&BJ@(F_<4<vJYaVUbn`_{^`RJ5K*%h}IKpVE"
    b"$Vyh0zhpKnE{nO`vr2R{>AfUI#VtG_x2<kSOd!;}{gaewznscKPD7N-jF1C$uy`Gk#*jlg;NqQX&Gdde)H0<l(!T`zta!AgY`BFY"
    b"Wkl}Xx#9koS4GT<?OO{I9bz*&kOuykhS-M|-<PhH<yS}=nrDG*YZvGlvu1!n>xwmFkR?{ZiRcb)s+SWOA%I>#U|smHofITeRNn#X"
    b"=uMXF0L@xk@1w#d^<bk^D3M%gwJlm9@118R-4=A~YGO8Jm|{wq?t@pe;6dojx`@>ZcO_6n@f^^$MDyD(`^_CsO=KzO5e@JmJ|951"
    b"LbTB*%KeS!?`m@zDoJ<SCAQtxI>^hp_-$8O5G-#E2F4Kko3mLKfv;4Zv|BBY4AT6cv64RpS_~#2t6==oNhtX;#kp73nHx$v$$FlC"
    b"21{1oxHeE+$e5Wu^IW_3_Xi?ZLsO-_owte1JjCy|8*fqZ2!uu6`1uZ9G)}G8d|@(0G_J8}2Tp*)lK%L1;#vQO*J|=oT5bN*1*AQj"
    b"fRvr>98Ka%F4lSsDlaTX+y4hP$r~>23+q-Ld1B(Yv8Pc!GVj0|h%iF9{}N0)?9SCzz{PJ>idXp-Q6LYl*!n3wZPR!1$%$`AWG{Zv"
    b"{P3wU++Hb$m(;{r_Swgqt+CKq1qP@Gqst5Cp82GDV4Y}CF{<-EN#OTcEjEd4#uGZ9hCY7@9|&Y$l>BwqbsHMn;&-~<Njq}z1TlsD"
    b"VIrLvJ2&Ng_6M5XvjEpbb(PQi`zu8TP&+eJPmdQ>PR<UY9ggzxZE>Fy^{%g)AD?BO_Eqv}GFd5L-^qn<c@`cZUnD%9CXch|YPGb+"
    b"cZGsLIL5lmnBo<A$0OiY@wxYn9E5NkCr=o$>ZRQ?RdIfBo>&>z1|$Vk&kqv&xONvUJIjVsL>~S2&&Mi#LqTr89~xv7tyblhOvws}"
    b"9SZb(n!}lCt<I?Wvb;zpatiC?!FCayPT@!<@);45)Jhd4LbPl2HZ&OO2*aRtIOhBIAb@|A&3zP)FK6vFM|XwCf`c<EJMBF<>E_Wi"
    b"&L+)@9Rw?=Y)E_OJ!m+;1o(r3cJ@BWy$lb3!dV|}5CxgBzTVC2u9wqCQA27snkxy67=o;S_wv=+<V&P#bYwb(mW=eGC8mb7K|N#4"
    b"USs5-Ymkxn>W}z<bgIlFgzl)JJ`6)}-_un9akJaq(@!T_Eiio;d{`ixU{+*`!Qu-2?e24()beZowoVMN%FxGN&!Q<TK<BLjx+meq"
    b"*mWY18ynlAyUIiBEW;<~AbH8l>@BYmr~Hnn)_Oirp(&=qcrRk5@jXr-6d_Ac=yn<==1_Tn(5>h6Y{cDQwzCgGC5=lnE3}VZGqpsZ"
    b"0#yeStLQY2KwG=X?la4$AXT#)X9?&XpD};Ngmt^eHwv;FK1{Q7(BR*Ah*Jixv<stm*FgF4(=J_J=d8DVSB0mDepyexs*~?SMo8M_"
    b"4rPfVJ2>Q~lMg6Ydhq`-30xRP&`oY;LKE-mAyWH;j=SGYtUxSV2WZ8qAAqX~+FwJf0`?yKXlY2}dG-6iu_aj3ea5Zpga5U#UC*+v"
    b"nMa@@AT?mhvSdy-q0si|Na%q5OTzrCx%Vs-j5MSLM~EdKni&jhQL5-Q*8uBIqTgj>Jeq)~pv3Z~%VhKG4AF-~HyV%*wdV1)D(A}<"
    b"_7gRc4?qA=m!f6hkMi3ozFXnu`(4VfYq5_3-9(@I35AEtdZ71hj1;NMj`Cul!x3Fp0z3YK%W;Dg!oj^`*R-{h169%0gL~tkGPi5A"
    b"6kFz@feI9^8{9ti=QIXqxOOo)aRkf~Y+-LRp^JzONm<(W2g$W1?t_!e94Jg=HY8nP@&AUz#e3}zL+OgeF=buxrFjuU8f|bPtUh?h"
    b"5dF3#)?)@33#_^^P=Qk-pNVwi?`MS|VCH(Cqnp>`9e$Tzi;xnk+he_FzEWh&Xrg6lly9j>CL6sXMBOy%WG)qrzGmVzu_oc}{|xo^"
    b"s_wOIA*+j$q?TeYmrT6!Vf#8XnNjch(3<Zzi4k>ILsr&|$F$Rtqov-eJ_BBs3N1~m4+%GN=z>eM?RgsJ8c5dss>I6^QUdZRGa<n="
    b"Gv*dvP4cAMaSC2Q*k63kS^5FSSAwh~z#x3t@3?{^v&FG57dK$>a-Q^@xURbU7uv5kD-%Ro2cx;&xK803HBRpV`4BqBa8DXweh+8G"
    b"px6moyqCXg{;Xu@uHZ{XlwECQAQN}kHgbQbSoRuda-QK_FQu)W+f#F2T&-^iW)YgA(?cwLB7?IsY90T{hT~o7wOq9P#BBk)a}pdt"
    b")r?2TC(9nhub2FyM{b>fPInGY4glbpB*0s0z#78p1!_1u{EOgE6pSYl04hx-z)KTF@1A55nVV=SOS12X;Le72&xo=xvj<!vcF96p"
    b"3bE3>`B6X97*kIs;@`UZx>4Xj-NI5u9!qaujn=mF2=4TCv2b?ZO8YkHYNc#NFgtIVxPT>imJF2>nA%<}s{kEvjch}x!>@{*8U<J="
    b"%0M6%rMSJqd8XXzbc1l`p=hzeD~lS}Wd@6tTEkJnwc|$|jfO&h=QOh#_z{Ot$36lN=5y?<-^o3_RenBXt*6QB3>#9*Vb+s6O~VC7"
    b"Rq20T;_tbIs6!);WE5?i%mZ6~7ypgU&7Gw@KsR})&a@D;Ix@%7<*@HFBb~_jT!<hNfYOkIq1S{>`3?}}^AOP(h3>n#XOT6qUf<B;"
    b"t8byh4R!7Aa1aK^D(Ze`jAzZ<%N*!Tn^6I7>vRtH$z(K)z2ExRnaTdp5Ahjc6Z23BLK(ojLy@<~`VOMFbwo?s7Ux$L)^^CuUBvLa"
    b"I?8!4Hkt6~BwpUNtr3}EDxC~OTPJOkySS$@U`eTf-8E5hWbcdX`_RLY8~t+<b<gsL$xh?J5rbGPuM<^K<!pUvYk3jB`jTQww@gi_"
    b"nb7s^PkPx<eVol^^|``^$G{@>xlivfPyJ4wlL`8HL*>=LUnN`u5bDvhy&Y<|!$@1CiT)ct2J9V@9D&5igqGX9xg!y<DZidVkq4CR"
    b"5dmEq%1na8EV;{R^n?l*lBQcG0rK+vs<s_qU$@fgH)~)b+$aGmG&orIa}$M9VYI)S@S}Idy7M2>&NL5dLx!LOjxDjPWiIHCOxm!J"
    b"r`{dXI2aTbCk>>5oQxvbxxhj_&T=79Z!e9>oL3s%lTb@+uH~Sfd6%9&zbNc2h3uh4`vKdRW6R(Oz5oI?E>_v47b^2z&&YC$n9)#K"
    b"qO^K2&kqtF)Y3cd3S_+%pB)OegitJchrkODdK)4(;}<#Y*+)T&HqG=1@iy3hnZV1q4NlYx!QDzo;lW=>K!%Htq$XGYVQttL7Kc_6"
    b"H}+4V?GxrH08#45w+5MN$~xIl0o#qdjpm@I?okyg!CzM#^5F1Re*n0b58*qoiNY4G8f0V2M{koZlxyG^>B9zUbLG+hKxt*|o#>_p"
    b"zf&KJI#hkDrA;@T`P!gl7D>Gmx-BWP4q}BrzIg2Z8r}J{1_yb!AHE3kC|Nrau1rEfdzL5_PiH7izeGDgWnHSAa+#^5wvGuLTl||>"
    b"a(c)wQ7{{tuTXz22#K?hRRN2E&+M|Evk)uN2xFWa?+P|(zb|h@8%+gkG<7X;|9cA!=ALnGm*zli#x0MLO$&m?j1(Gb==wof!O9I&"
    b"n&sLqFbg=xSZ=K5&zc4vD~^r;l873AqP}bq1|98%Ed0w9@f{sf?PJhd&{n*!$KhNY)j#4~QF6S%i*BCpO+_kj*~XKPo$4noblBh`"
    b"7n)s>r=6k{Tp+DDd0LeDu_7AAj^=_4e&X(>743SXho&#B#&5X*dn>V>PT0}SO^AgDeSmsqE>BDw9G=NNSbj6xc25mm$7GW_(V)YO"
    b"xY!BQbP-?LqX5%OCh`h!y`k^(pc;^ki+aWqU;hxu^rSmmmpw{tMrKJE)<BfHT;9}l_2Oook8GB@w4MMSr}|CjT<?6=Eq%+V;f~}S"
    b"bzOci5u=_hrPeSTGX4`oKKyQ|U&OHwBXo0!1s-P(SQO!=s+l^X2CvU<C5xl#2|{jG(Og&cQRn?w*-sMEw$<cfmBFbC)z-b1YGiT0"
    b"W20OaVd*oGUx`Z>ItY~!6_r=5eLL~G(d%QkM)pJKg$_IO+53xSB&MH#)MhnYPg(^9L?entD|fp?mJoy5PPj&tgF_1+u(K6cho@m2"
    b";L5_+kMz;-x1^8I1Ya}0@@fn590d&zsyOj;3hQGT^irwE0fI&Z$~^8$nCvWzV*$AOvZucP(W>9hx|Ea2e~pkus949TX{|J+0~Iv8"
    b"4MSmL4!P=v`)S|g)3`j;vYCB)MY_R#@~B<76wsIm8rDsvK7b_fsfe-^F6<;a^>+a9@Dj___!CD@bpaI5Vm?$tjKmsNr#}qrnPCLg"
    b"#;2a&!5pAEU6&z$W4)-i_DObh=>df}oE^w>%Gvpkt}+4fLtipFI`>*!8hDmqfs8GP3y4hl?oG0?H?C{{OA@^<gtT75i@EAj;c0+j"
    b"i-|<yGA^FHX~h~fCGzV8#jCuWLFN(M&A!OgCh{f0MNph0v?%f!NV`S8CW8OC5NF;U=9(8Xo|)UMOoF~Bv!uzO-P<EZ0>GXPCxuc`"
    b"hU;j;u9tBnPMMuo_;TsZMIisnV~&fJ)%>ZOseuG7BLVKv0W2yRV^*MEe0y&&M#ViNz@178xr^F~i!&b)8!8JZx<A!W;+J+iW9I>k"
    b"0x}ckyO0<eru7guY77R~K$8N*P!xVn9>d8#XlPE!tOr`L7tAi%6J5_baBoi3BtrWhS&}dr{A&&tAl1xKmZ?u;gc#zJw?=n7kD;`5"
    b"k528xG*<fRIWJ4LaLus9jB2u=5%pyY2gW^`0Mjn%OmqC4i60LHm3??^*)XfRXOh*<e0KqYW|K9C-bRMD){jR#6#QSFD&F6l%#S9o"
    b"*#-(}Lw#mgRX=-ryc959{wMlcnzGnEySn_DQ3gkdv&|M_ALfm)iVw;#Wznwxg-eRTu~o8+b0oiVG^bk}15=DC3V`UH#~VhgfylC+"
    b"+1cTm?}|^6g!bOD`6i$6CQtl~v7>g!8J+UdsdCJ+0AIN&!Q2wGCy$~e;N(LZstJg+*}aPp*jFR<SXe#%@-dpjHnFV#ZbrP>fzxu4"
    b"nyT8uE#r;is+sl^I)4PD#>2pSmxa{>HZ0Mr9b2+i5;Q#8Xj6Z*BIpsH)vZ@xOlv#XPC=o_R*kb=7ZRU=Gn?z3MIqD(nX1w=6WDjG"
    b"c-&VvZ3gpGiAshk%gzL**OR|&Bv4y^C+saMd|@W>{tduuWDY46GFIh7ElT|hHuVa_S{p_`Ub3SJJ}|`<7))jCyTy~b+&ItB)?)~^"
    b"y3W>CDu=<u7hVgV%xbcJ=P9QDDK6Jpu2c{~WC25?*kBwJB$PV2`SzDx<O~Q|Xa4KHS2!0({yY=opjSaRuR|$M1I#%r+Uf!C2v<BJ"
    b"K}r|N!-i1)4ZMaSE52&B8hhoL#-~%`@)@wG_%g+dc}=rY+B$mb#<3wL$@2-K2hOpXS{=U|rO_4bIf`6RFjVT+${Rg5=ew9)|95;C"
    b"o%o#U*k-1;7NTL)gIdV1`qE~h%@VQqoNmKs*w&o-1U|tu4M4CI{<Z8r0V0)A_hevYZUEKtxIiIIDVGZ8LVFCLxRk*Bym?9(=S!LI"
    b"*=v54J$82NT#@4u^+ei=6d)MA-XHdjuIo-A-C;I{oI|Y2T5=5nwX><NoW>^O!6Td#GQ3k}uL<Hg>6jb`(OT2$C7=<16Zj8QG{K+S"
    b"E^=_7XnJEJgNm-xXRuw9S3=c!D%={m(<Ilme=6uRyj-Bx_^zI28*dv!@;LCh6d~_a9P)#8==<8Nc^V5a&oX_~k<Rrn!OwKz@6aC2"
    b"d#3%>$$Q#mx^Ix8Zl6jP@Xp(%QWJ@jwIiXdPv18bb`c|Yn?LD=4cR=uAEa8v>Oea3DH$t<qbZf2*Q?hRz(zV3Q_uzFaA;5654QX?"
    b"*h&CG?<h98qv>xN=#oVfz9S^!i;!;3sc;7gKS`Rg5u0s%$XvaSWzjRw&vEj+yw4(ybg+WM9#SFTI6r#^c;>l0l<vOt`?q+I+S(%V"
    b"WMpK6t(0+1z`eehD_qM5qTJG}Eb~ye<8ZgY6!^Zpk?FxB3pQgiHme9q1t7DkI%3>XUhqR{IQ6;0GKb06O&;Sy_m|{y9mS8lgr%UX"
    b"C`@jo2lq&`3%^>0Bhv_;9bPL_m1<a#{fP#o#u}j_wz^Z5KP37E;0j9`7y-k;E@d=bS<1lurI&?j^2(H$Y<LQeG7Bsl8pD8bv%`u#"
    b"eh@3%KrE`Nf!NEQmX7k=ZSQoLcD!*4=)c2nD!6_w+S%Ru3S_Gls(4mhtDL*$R_GK2`*9TvP&vf8z_0!R4q>p@_n{_s)w<&yv&i-?"
    b"FcwYo_TyeZa=IQ>dawXh-R#qjPh+_R&P)b=OaN{;)yiRP4_K|)kyN^watyQ{0NiqHr+Y2zzHVY|*MPjN(7lyP@XvB`YdJE$P$p!W"
    b"hU%dw=p0(g;NMQNGf7J6OVXl1Q+L60r}v=jM~tUabZuCujcn5?qT!D&iIhb;ZO2%*DEll?JtOTk+*LI;05<It`K92NQuI2yR7~V1"
    b"rBEsHZ8HD>C8XG#N%Q$;5m(xKik_dzwy8XnowuodtS>8LH(PrwYRH*C(e2^RXBX4SC=Fs|lTX*fkpY~h$R?kYh2bo)gBy{27eLQy"
    b"y_@Fn^YGu~@(D>C58@dT-TjVJn<sR)nZhi1AGYg`Z)I85vRwtX_jseODya8NQik6227a}ICfnQnXg<aAzJLJ@DP+v{F$9ZWK`jmv"
    b"9QMHY&|-Bc7cA6P;5#4)BKrSj$5+D#F@683SnV<PR4wK?MGNc8M`ae#YL1vx>5eX-ZsVh>dcE@-2%>Js*Q&P4bUY!%yxs;jaUpb^"
    b"akhTQT6~F0X<c1^b?xjJ*Uxm7Xg6Ig^~QlL{_?u>9+VQ=JW^PngufEqF}YGCXr=q;Ov<&Ha&NJzr$!`(q+{qrDzOVOvh&5&v3GS9"
    b")D_5lvwzq2R8Uugxu#wei@tfBZ^2u?9qsH{T1pE7`Q)*bZbXxodsLs--UMihb354DkOhgAqy^)An|8f(2k%_XyNLXT=AKi8)YxsC"
    b"ku$2Zah2k$_Fq;{Zi8xs#$>+{B;SmkzuEAS5l!LZ>b!|m%@(JV_EM$&RMRfg<MK8VWen7yZ^ME7m7db@vBx{7mIE*sT{D|mIt6<`"
    b"p}5aBwI)f<f<M7@$NTQMnU~ftwZ%9#%qAqQ^}>eW$jtomDRe9SDxPM~Dq9|nh5eNDr81C$QP|>7N3BwUkTSMOGOt6ZC<bl*ckkh)"
    b"I!c6n#s0qK1PC!OT7ukR&t@o33$xfd4&VJPC+4sO5xDwV6KRGB8g5uu`|#iZ_pliYbO$T0X<?J=6;q`%SFC6|8Q&CcnlAcI_*<CW"
    b"monk1&eBhveTIURTBZiyxQr<UF~G_1+gXhfYEPZ@q-mT=`!PDzKU{a@if*R+H12~lGDvWV_6X7L<wFy_1^F7*Yms;$MNVPE+37hM"
    b"d`nr~%{XlXc1*ouR_u-h+cb7rp0AT2YjPrtvp1hAeR6rf8EXnSe-vyc4z8>07loUvYV!dQX>^GkKP^}t%ucpBg$MWDq+2MwCtHVU"
    b"!>EM#EITvnoMFpT+T$F?5-bhHaj(Zpql|k!7Im?OeZMwkjU1WI0)MqQ=;xzo?Dbf=PFu=D+M3`6Rzs8oSDNmWC?IaaFYp)d0SLqn"
    b"3$&?(Cp6UO0VGDf9QANB;Y&D^UsXH<IOfSMcR*t8qHAf(PMGP*cWJ35*#Ny|<mAIdn`;;bU|QLQEUUtadlMePjfXoKm2ag}Nt=^O"
    b"?##;fo5-}mezeE;*!4YaB?j5o8NExWK=FmBa~fG0+1OvzV{N8AAJ-lMnmo4Nwg}pMV8QOidP2Fvu+=mASr>~4T4kaUYtsp#g|8;|"
    b"U|l0V98oK_XW!H3z$b(WZX@>McYeN(QvW~E=<)jClsh6?$0slfF-ejOiLHI|j9YPuv(e|q_Ka$kopaPRA;>C(NS;W?vq*kaJKkYt"
    b"@Kv;uNyqH(4^59o%uLL&PK-zd&S2Xhx-@Qx#Wsbz9<GzWb%1vEoo#XcjTp*>4T?zm#a2LLNo*QmhNIz*RPq_r05R^Z0^QApsrLT3"
    b"ySYXqWCuC__i!g*p@gje$_DIVA{2(foJfI0=K>@o)M1<*2EFIdVi#<?7Ld~4lqPb=P>@O?IN0JZz@6!NFgG2!q4Q!gtjYapu&F*R"
    b"WeCMfH$FVL0y?Ws2RJ+#he0*0`tdbSxBh#YdtO9!2`sZqv6>ym9T{RIYqDIlYw5Ls!0Et+Yk6CPWDPotT!X@7x(Y60+35l6a!NDs"
    b"Mc?-+Q{T%(nrL}^bnnX*sI?zPpgUicFShoZVTWEEg~*Q5sWno;Zpdtl`}~Fr=Z>`nguu82T|CUL=oVv^MPex_*mM1UY8aO4PS7X^"
    b"eQt_mEI`WcDWsb<4GQ0Yg>(Qa+`kQE5bYz|wL`(@%OCEHQu&*N1Udea?hT_3dnXF=$-v<#M^|5cU4n(QYfB0-kz{EIU$N?C?NQ$4"
    b"oP^CnMEMefg#{}|11)(3(4r?NyS+LUuQwA=WaZB>j#Ij`ttg=A&p7fUvVA5t_lI(ACjiSJW(0#G9NJaes949zKr8<px>zn(7Zj7B"
    b"o4R!bPWUbN51@c~i99lp&`I*zz_!I4DCE%)rl$ZV+$Maa2s{W*lvE&l6F`j}|C-fSOU7#c-y~*i7;>4~<TSpf-RUwOZ<VsS+!1tU"
    b"yocgGF{3MWqxR*jsUmT5{9Xg)@fVXlxeAn`(0pOTLA<vUT85*2-ZAQ+h1$y-FPc0a8wBjY?;BVcdues=#lNz-G%$7iX9P6LHtMGn"
    b"?}YG!po4!z7b|P8VpBVN8SHBk+=O;0E<D?F@-QYmlTU*D9=P$A!dk4W0FD;dkA-(mvc@N9PzzrYr-aW7s+zMfzV?caPs@lU8y$!l"
    b"V>hN?Xk7aDO@H7#d&qQi0Qzwgh0ljKK@0QRrLbYz0N9SrotQ)rL@MS-02(ClM&@_P?{b7q9=+-T3H%8LNJlwGb~S|E)IDjyttQUi"
    b"(uO%Zl(X#FNLAX2J-P=gKBg)O@T`B;HF!R@=hb~yg+<Ka=qFD9GY==nhz7p&6D0-spl7twbn}bk@(7pt9l0UY*V#Q}@sej%=9RV!"
    b"irM@QS7kV04@2$vCk}G#>N@MCUrWkGSFG0qEUW!KM;yuO8rkqIio#iVz|#m5?-s}%7LiM$<&)Oj{IHrkI4f{MnSn-CoDTZ6F{(!M"
    b"3ZCirz$oj_$Ol5Gry4)@m5m=3;TfSOB-dpYPj3Xy$=&OkrFC@`^t@9g;><=Kd$W2VMY%=hKHgPy4x*FjSw>6~!K-Zu=OXLf)2;Oy"
    b"ta+w2#r6qsdpA*h-OfmSD5#~5Vump;ngqf+$SN0V*k?OoI^Od>Z=tDdK0Oc>;$L<_=Dw*xF0_=5xowAb(8=d+wuQOw?=&cHOeB)v"
    b"30-&k>?h^(5-8epMw@74Q-O6`#76i661I9&F+@`|whnQ%K7(rU9*-X+P@4E0tnDy9=Wu~fioq?^WU9DpeJ|jL1=B2BUR&SXBYw>c"
    b"shPr?i6P_Ru);#nR`oz>Ci`4a9q+s)olG(=nYkG))kJCgR!0(zh61shU3~Eyh#<AUS*hy!w^Nm3;eEe`b`mDZJ8|=MUG)q<XLS5U"
    b"p6X(;#N#@RDtO;a6*4cC4Q|AaOk9esx^i!*V>~s7_r(SmlkMZ$s@f>P8xo>bn;mR#PD;kO4k@kW;bMV5)je0A?a=`#HF(P=$t{aY"
    b"D<fDN9OfmsbqVWkG(@zUm0_NZtsD&VV#gscalftUMof?~(>fBGVbGMiZx4c(l(FS}28!)52}3M_AFZi<deh^Uah~k~2S2cdRpwnt"
    b"s_+&7^cgot=iU{3_aPz_tYLizluX}d>RSYiylQswpJk^cK>_gkQ>(3k#{~Epm>S$#OkvxSQ<JIKPneP8=tRKe@E0X+{rk8&7Ig8{"
    b"r){d8N`)%;B4vx<68B2H(<S}KBg=v{_mZ)BsivK)RExBC|DT6DoY6%p_MT21+pQ^Xyu1{)F)j5Gtiuw6Oq<7s7Vt1E;d#%{yPp04"
    b"Vyz`EiMh%AP+k-f`;nTA(jgDV&vmY)aZ13z_6k{i=W9w#DJ|h(J_oxCi@?UUs3!|RPSh<{5Lb3ka>!A6Q*U*X_Ec~(1r5O$=!Gs7"
    b"(r3^k*`TO%RuSKw7oYBUGqD5F>7mG)!cPziVv`-6+TxplELlD1_ArS6M`G-Fh)#TXflMVyJ84Q4!SrNt4<FyWZ}DEl_Hm_8F8M}H"
    b"s{{hKBfGj|dXD^EE?%i<d`r!W&NOl?d`VA?+*xL4u-hak9|&BPGP|^z2k|3ezn6YD14^jZOZOE~r+Z#y-YW7mO8VvXS$A>%@W5Lf"
    b"2NV$-6*eV;6!;<jroXAfe}j|BP+a)|wbI<S=T%iKG|(l6O6`S%AvI6Vl!}bbD%*KG3JkU_0;0MuQa)bJmkVOZLiR$qdD6m;^EU%l"
    b";6xmbbDf^GRaYZ?YNf*Z=dCo$7gpLI;hM}gv^VdsXaR!H`91*x#3^bBR#(5{2d|JjA7}G{oum4+)*H$89qP{FUBp)j!xJPt(cD5;"
    b"cO}APUQ%D!>4sCwT90C^Nn7PBvhrDvYXJEgEHJ(-)d&Ajl9r-^m4|+T6+5@@L%r5$!T>CYQ&!eM=A=x{KVaj2_O5})Mfx;_nVz$V"
    b"t7kg?@K5Pk@DvX<QtjEXzMcQ7PjO}<h<?zpQIxVfBE}r+Y=b%ME`@x7pvuuw7DB7HxUxB3`>%awPZ8MBDke!rOFzjF&gm8RDz+dG"
    b"zU~-XpG~df5~!1TaB#{aPMV<b&{+xSDN)9~?3Z)fxc5qUoI|Bqp`CO{@;7k>C}ibbgBuUEAeh6I&fM2t10^X>K5YD3<tGarn`=u~"
    b"uRZLu5Y3B=fsS`ki?yi$cW=ND)1j-E9po~Ip~LLbqWu)O_+0t;cU|ShMXW5Pw;t2aQ}T4id{4Sc6727iWW#O9kfBml_VtCZLrCl>"
    b"D)tAZpdwju=)Q1Ei@|QUu|^MY3S(x3BjnYUGm4LqFNuEY@%?2+L=v)Ua_3Fm4oAeco9-0kyTE95?&kzxJd{fRckHJ#D<`uvraLtt"
    b"Z%PlIS^?LR9sZV7!A4$9+;^*tft*2Fu0WHKq|`g(aPWO>W-*DN&spd#p@g@n4^y4@9U+Dx^;_D9w1K8bhjNk4J%wzaTgP<<zqjiQ"
    b"u&Y_KRc%cXu*9FFyu&LyY20k(ef<b?Hc4tI&5|8a_)Ohus}iB&zy8i3xO3zO17BQ++T^A@d^P;_ndZsxAHy7C-3bf5k4#5Pfg=|t"
    b"8N3Oc2vL&!Av)_iZ`PG`8-$jIpLlXj0UL?h&lM8h<VN<<rxXy~L${A74z<#U&N8fm+oo38T_uMb=2zDzjqF~7H}m1$E|~iIRjs-m"
    b"*F7x~<Um6F0Y8w%>RKNu;5)EDQCwBXsJ{I(uE|;DCt3tMPDGHCdM7hMWN!79TesR#vo7LKG9u|=OnvSz$2(-C(g6wVVhS>q-uuwJ"
    b"l=kQIwYktM>SkUB!ZL;C-2}Kvw$ej_Rq~?)SSvUgModN5$8smCpFpr3ZsVtwr*;=m$Yf2%a%ZqV>t)xp`ovrZH}pcR8}Mg$z-2~l"
    b"p?Zt(S+Ls}Vuz^yn~vKrIQHMILMrl>lH102nq}$thIw0kI)+y1ac`hd<D!r_d>Qo2xZINqd^#V2Uhvc3%qrbv0?s(|dRoUL`1Rf9"
    b"#<uKPz}qrb0Jks#2*p#UEW;+=K<J!tz}o~o<J-10r5n6Oo9@6V>stg>VUd)Fq;ON%U=(t|3&RBnERA}(_V3NuzL8ro<||n_su=rj"
    b"2)WSCytC;}xVR_|8Fa{53+BP{g)InD-oS*KOesKS-29ROT73sQo1Mvo^xB@a`TJkN{AIc{@x(Gul)B7F#DSc^asIJWgtf0_Us2_m"
    b"=2(;_IakFubTLQA5DeY!xN!`Uwd&<WlhjwzF>8bb+2vq=F-7QEbPgT@1eg5e3mJO0Q95DADl^%R_{LAD@pi+Y<H_-hGDrc9Z#xe9"
    b"AEhoJYhG6MBRmr+uup)un}2|auyzNMvEX^-$;dGn@a~hC3Ik|tcR0oGXg*OJYr=kWA;lJP3Cc%d%mgxENNI^0^%=REoNe}<R`cjD"
    b"@@|U0!utG2Mz&Zq?01J~s`K<89~!%i?_hX_lDsGzaV9JWr8)}0R}Bo4(nkN$PPCTp7|JNW>Us$0`wKA=(q@DwC^ff~e^R`NRWsX3"
    b"*OA5W+0Y1YWM(Yp{qb$a+n!Gs&CXVGH1RjN3&MX9!FV8yHBPj0(r+g!NHU8LRHB6?mo)bxUBkV1o324hbs-lv8@x?T3<<cp&%a8<"
    b"iD$WEkr;j@J0u^DkyV@ZURetlf^m_%sPU;1xIi|f`bL-+!BfJ5v}iwX-nIgrgBha}4ae|dX1V$b^f6-?b=?`-;f@qKD>e5XAPzc-"
    b"Dp_@FVhS<M*cVahAb@vD#C4r<UJ8DKv$VefX9SSLl~*LeB;ezFV)m|%pe^OZc{f#uqgPu<f?p2W^L;`_GP+puAu}sQ@_H=hzdVqx"
    b"qfu%Zbws7Tz=M9;P;#BHkC)oJ#0nqf((p}<4EB^=6qyS?KC6(=b5y8?`hW~COO)F&4)tMdN`I^Vdy{-d^WgF%L099wVL^Urtq|#E"
    b"j*vE$-pL`lMGUc*l5(N@3B1CUo-`cIfkbK$a%^9RUtXeK=fsob6G~P;Gk8nPa8#s=mM)qXHoy9ir%`$gl^c)xYlH4hfEPg>54uCq"
    b"Bnwwt9?VkqJ?G;{%}(k}pNS!@Q9)U#i!9U;{GD!>hHZ997O9z<liw4pjz6Q+n@9$n1k+5L31!<ptjN22#drkTsM`n+S(WaFiMcO~"
    b"$5L;GpwPM|p_8no=ZX>Wri7j1uv<Tnl_5(g7e`^Peut>G%1Y+E(t~+h%_u(Nuwe?Uc4Vb;qD^D&>ro3b&ez*T)xpa*LRR6>pN*k*"
    b"8U73Cn@7c@Bt8@plmpxZi$qRGS_QI7@bcPLqQLvTP#>%vWH)3}s|a@f9P8byW!@v3#*z)6PEE-*U5QPxrzz9r3E=MiKZ$0%mCSwB"
    b"eR$(3DCU{u&IfO5F;w<PncB$M?w~ChNmvx2mt+hxGayg_P#IP~%G;RZ>HzFg2Toohqz9cqFah-NG#2sG;HvU8h$}&%p1)%XUR+nO"
    b"2!@2Lqd#tQklalMfA4!930s0Z4FM5y&W%Zh<>S2elzBx_T=vTS!@=ISPGhVi=xxZ{Db&A^XUhS4VApfSXS~fq+KSX9;Qa;y>Z+AY"
    b"eTcDAb<I0}6Nq+<v!shf<DGW#ho|CPaOR}mjk&0A!^u`?L=H6mhY{PGE+-A7tn#j$+CC(JdAdzeL})IKzu-!fYvO}g<$Xsyy)n*W"
    b"9?8-u-4YIk)=GOmqvKTk$c5f6Rf!hi_gZ3D7{Z})WS4Bt=4+PSua|gAGd0qY)#j!u1OZg$!cjdhsVi@l7)()tQ$32*$z4Mrc$=I?"
    b"^3abMvrr}`GXv>1H?&AIu8Z(-0YwrR!?eoAU&Zr+;+dR%LvrEIIGuH7Jdt7u7pF3GhA959(FSvSngN1B=GN)#SjQS7ECC_LdTewj"
    b"sm{YvKoenqwstaU9V+!wP0KARr98p)SAr0m_+g`fQ4R&DQlGt6S`=c$Af*F*iu;0y>HEz={2BBJsV?_rV}{JKOat||*GnHm9zN?g"
    b"lfi&URmE!YJ<V>#+(C90P{g#gNL{cwTw$UrJue%yp46Kwa6P0UGH^UYrQ@}f?=-;1*1z?cbtTr9+8P+VMZu1RY0TRGvJfyvVHBRG"
    b"?46iXbw_Ye5MnShbgSqpuZGbeFkOC@1Gf)e{>9KV|HA`s7oz=gMY(Lzyp#AL?%Tou=Hlg>Z;%Txd&2k>RN{HNbSwr^Shwvt^}@e&"
    b"L1_<K7yq~($N_UGJFgz^y7e<=!pBwk%iwgvI3hSK&mNVf5iG{FvnnQ(T5`cYiN^Bu3F~Yr;ybYw8ZSAq2zd|V*QuK~Muv&TnYLak"
    b"#33;pz?)RGbhOs4nZtn>J=V(*<ONmlGoP=U5cPeEk)#gnSxxzaJC0qG+8>9}LfpaS1|Gzr>>k>s>06cB0buN%h?24=UEI6dxMQ4j"
    b"@g?Y4Ed3ZWr_*UcOL2IU(ZNf*3(N5lZxDMJbfTMKr7n<4mX4N4p{xx3-TmyS3l#f=7sLAx7P=i7IKyqTM|B@89or?9qOVUKuExrB"
    b"zpoQs9ay+csdVx>>9r@Op@Dvj%8#>~GU(lQ47*q-?NSu}`ux7Ixm?5{4Dr3FN06T8+3QfxnYA*x_-y+RCEf!bd7XF4z}7w(t(wjr"
    b"i$$=Jyc(m5(e`5^j4#P1(%_xSBUDeRX(42o5|lt$aCcKC2^cg{+`Sag`_us{GKK;P`%X7SgZdW6;uw61uTz{y@^aH4tP3aclLn|U"
    b"CeeY(2&4-ahcBI=P;W00nN4V=gEp@kmo`)`_O59p8g^vi&=xJi6&%M%+goPH+1`l5(IfA}-`~I^bX-SpG1Lyhi!T~5vJAinUL!!q"
    b"yVCs_V}GBMjAvnZ@c@`5-3!`bTp<GMwOcLl=3scU!lDNBW3`o@7jWi&R=9Rs7^%Z3`oCP_c6QcByr1hVNLn)_AEp%>gPLg}N{(b^"
    b"z<Fl3fWJpEACoX$yX6_jzfdb8eR+}jl4GzEw_Hj`Cidnw>-yuB2_FNK7pgib9r+O?B=C65*{Rw6%7j$JE+ziS)}t~?7Eu1DfPlje"
    b"mcV9+xIyggM^*IwW$F_j7GZcf2Nu^tB#VZUo5+)RUP=;u9i=G6<~9wPLXZ_MOR%)lwaY*+3>i2Ted2yWzN@Rb+Dnhs9i4axN=LH7"
    b"s{t}R#Z=90Me8cbmQPSeQ+$QLlR@-v_;kZulzEX_MnJ=hQQ&82sT7S0uicz-%8HZg;3;~v^O>w)7HPI&|E|WhU8(N#*fDnyB(vfu"
    b"1rDz;SEhRtt^i+TL8h7dlA}CxR@2Kfg~wql8saP>r^vt?X*+K2b;`R~aT7*gDhuA_wYEXa3YJLYB&Ga0E`Dq>q9x|9kwVZ4t!vlW"
    b"YA77SlEMZ;TWzmoJbhUJRv-FE0{g&i4gym#$d%}OahRa^BAQjtF8zJ+BeDT9(!tt6w>%DJbITLAFu)bV3MG$uvW*1GeM=8(`@O^$"
    b"eJjATk*rCiLhziWyLc1mqe*FR%!W*+yw{5R@h^B@SMI21!!mVrwS-%2udfEe!4Er;DP&1^6~RWgs_i&Z9^>n9Y*Vd+Gj735<>H;g"
    b"&2KeSuc&=$O_lyY%+XwFnw&pi%_i{lv^wz-=+nc=dQHC0L&)flOg-Ej)Iegq)dp^0q2{?W9O^2A0LA=XZGj6$FRcH@5g6Dwi6~20"
    b"WbODCDB;~{Mla7V`;ZpFw1uR+AeXD_Uym8FX@p_x-pBx*%VPbixYIhsHJW#h$zG8fb%-2I*rEkmQ}AO10%X=|#IYO$?xe3cvYd;h"
    b"9(3sjQ_F9`S+G}k9Y}eD%+E<srJ!CzEq+!TI~i@>*R-+<XZ%4a#G27Kkn?zLULN}gSkvu_<PP>q<0R<m;}OD_c*k!S%g^X{V6Cyu"
    b"LuYtbggU*5TFRMjGa+F-kmv`UBzZ}d#j(v+h%fSQP_!aRFz#q(t3?vR4V2uJw^<=jz~vRwKfJ)IC;u{1T=0Ncy^NAQ!f5OG1q~Ta"
    b"HmaMNIW%>=wpmjJcV=>Y{LZ%$xu3_3u;8ga`a50r5(o2{(o_Qt{tJMqSusXU+@W@4RjC73JLF3+!E;%*C;t-8;8Qgv@bOq}cb~`|"
    b"-+S6(c1KgT$9KdmqqQ|~&H10FVCmaVVY-{*C7IIoy-9S?YMYdO>B>NE*QHn*{Iug&`G&$1lc%}JpybDfYwjIh={ZDX>6D0u!Ilv("
    b"S8P{XO75s^cSbx}D4BFETQrq`Dt@KqMh<Pg_0&6r$C)EQB;zc=Ua*MtI-k{ZLq$`U=uwC=PqH2daz<EZaYD>koGyF#IUe$^&)v{o"
    b"A%d}@&P#<-_yF?M*F+bN=I~T1$9w;eScFHI*(Z<Nk$`V;ZUBH>{E+kHYTu-;tLG<L%p(tx!cFgoGEt#&F%$Ur;<Dgz#qHX@da8yC"
    b"W0PQJRQm#qR^4vz$<KwaA)NDGYqXnt%VLkZ()va&;-+G1B?td%+|Y;Ccx9jiXN{a!QpE!GShGXs5s-Y|#YP9=$fCC;30#o_(BRVL"
    b"8V#orPjwCdT(}V0nM??~&%3+--j#ke?1-qs@`S8xQAUupJA+G~WEyWJL9ahcNby=i)v?DSdh++6Fs@5+CxB(uYS~wiwNn+mOGD=n"
    b"rNf*Yokr<#3o>LcUpf!F?k5dvshw6*&T!>BRxQ6v@~7N2TXEB0!lT))LRLRwapi+|M<yNG-7Y|{T;4L{(cQ2`Zq~0==E;o=YPUVk"
    b"!`zt$DR}S6ygVbkRF-K-)gnYl|7q`3gG#27KF_-@B8qc(Fn>44Rb*k&-Husc6_YH7g#Kf`Dg3)cJ&X_1E-7SpTI+?Wv)Z_E;1ck-"
    b"HwdxCFdBolzZ*VxoQw529{QYc@*Nam1#yP3{VChHpHEaO{6gFU8Z^M^Hd=kp`BF-Fba{-yzt@RF9Q+%+AQi;~tK;shs-Ip=uu!ll"
    b"A1q?fibbzQx>4ww&u214x@5H*zA|h*Ni^M+h>8%V44Ln(Q08lwT^s(UzBV>+wADnoAN}g(_j{dXzmisVDJQV#v`AB9RFcdxTU-VG"
    b"`CHmW+ud4mo7$gslog%Yp@X%(M-c9H;**}uJKkvPaBgqPEaa!KjmWOfl8?GWlvbF<_NYGzv^xP5Dqx-1h$>{i%H)ZmAJGww@h+el"
    b"7e;niPugbZz+)v2yU^mv8e}xmP=46+>L5ewvd(Y9oF=iv2aS)0X}VHlULcE%CqF8C;Zb$K^<u@`$f&I(0h)Z8`a@(<u4_B>Bv4V4"
    b"=S#=H25<p2j(8#<kJMU@Cn4u%p6oZY63sW3Cu&1~0q-OvuRxsWkeUj@vYgT12#0GxfK8U(Trsc|E)V^-g)u0u!D#0H46lB_-CcXD"
    b"aY93nx!5_5qutMil_CEb+H21j4ij!ouPQk_#GryLjtCE??rgewwhm>}{6X|EZ{lw2Et-NJGeDTWN5}oz!kpHkx~E4>7#;tG^%~^>"
    b"Qom<+y|}_YM2~|U-W3gPW&JyPi*Y1La$=;*5TOsetN+(itoa_PJ=*#MyV+q_5WE;2eB&h>3H0PaL<WmJ(0vGCKV!6`)(;LO)B=jS"
    b"itB+;8)Qva?igUhOWSgWCfLNkjCU5))rULv(12PS1-IQjIu|LF|3p$=+jpmf|NrTa(F#p>G#an*Ln@Maugg;bY+l>xjU`JRx66x~"
    b"C%NiR^R=eHb?E%Vld9(~oL>6rivJ~aeJMIr)A%(oa!&rzjmu$-^sW@Z_}xCvigIH!nX1km=_sPq`Y@^gioVG79D2nzj_Jr)A*_y1"
    b"b_6Eh%STeHs$Iq$kf}}j3I_vxHu4CXJ5P)<D-=&<G#9vTa@BqIP>XbGDnjPEnUCTWq1^rZz+{7QCd4rpP|wBGw6KbEKKCNJY^BX>"
    b"sg+80E$_XpTe8Sip&)8CmH46^w&dsTnf0Vzu_iNEhS5jQ$#@IU%9KQ;-zMZ^zAsu9I)gh54kfg8Pya*w0Ib@=4vVtw_@8FZ;P<}4"
    b"i{g}^+_z5B#6C;~${ol1IY>N$roJ}tc@YThPr~!^>RsS(w(X9$yk`7pTTcjUOHhXz?rK6sZRe?F#KvCFO13wmF~}9WO(og9#!<hZ"
    b")8FTW<+%JUM>yPYjmRW<`oTznxowHLjJYxy@%rWhqYS=ro?}rXQ+60jL3~(hW$Oroeo1!)v!nx*d%nkzzo6$GJ-BB}(e$~^k1hlS"
    b"9KNv;9jguVo~T+c94gjaW8`m;to&mWZ1mzURSItomJ58y%Yfd7(+jB}4Yy%;F3xuScqHe_-T+?dWuYL70bvDw)q+1~_jCJE7@T!F"
    b"`IYGFultP^u1l~R8}Oz)V0yUj5d1LH)BALwOY$EZRpJb;vWT=0?*+vTk2ubv!TS_c0eTMj9?(x#i$_Dx(<CDnw2wI#hewcF?HBi="
    b"NFJgLwRJ#aW*K4{k-&4ClxO3?LD4Y}G`e+^%MJ1zttC`#7U-*Ls3HGdtp02URmHSnrLW`a%!k`bMEvP?6^IPt^Kir3w@@A-uw$Cq"
    b"PM}v$eLrS32%nQa8uDS;hwSQHWXHyBlr)R5id3GW1GU1JdAxZH$OzSH@=8oO5=6!b*KXP1jiejnYEICuV6r~l4Quf`Q<4=b-1*v5"
    b"=7@<RDq`c1X)KLYy|vswZf`PPz?0Lap~0AUPQ&x%T<^7~nXI1tEguFhmvvcglYEV-?`tkFnzl&c_^%_XoxZD?NklR%32W+DN*U`#"
    b"R3<g{F?9_uuX7R0zF&dt8)}bh8Ks=yWsipIiVJ=nNreKLZFamgRzkc%R=Ku{hDt&<x3`$0x^bJqK&1T(tkr472W6TYoB?eg&P6Dr"
    b"ET~7=;UzKUXcN!|`w+Aw$X*opqo4Wa1jz|Xvc5btt7TXJIDWyrarj-pl(eEwFRpXhyf2A4Z3`Ddd~2<TRiIB=ktEETl-a8;8|BAr"
    b"=Bn~BZ&WyXXCd8vkQDfi4_HCL-hL@641VrP;0=g^Jy`TIIDYtKHS8lmux*i~Z&X!=Bc!kvPP(X6-~fp&M0WYT_pBy|m?~KkCM1`|"
    b"V%K`^oDF4d=!C5k-;cRwBR$;M)Gjmuatns2gOnl0a@33mIqf4kOT_;DnyIVT<pa52ujkHYD3wBVQ}wCHqPPVpiw=z*C3!s8hj)Pq"
    b"_b#LCIuJB+8@)Ba&eLo&NaJC0drk`Qlt8yZ202f`*N0u8Od^m25)Xcfa!n&a1PFq&BWGWGs3V|E*~5i)G`!n*J+X#=*JgULAJtpN"
    b"=btE2z6~ws&NHUTxTE6-FQJx?`ZV8e!BA>!T4SdG7K+0XS5BY2BP>ayaTOS#=!pzAIY;d>6I^4P-<3mO?pb#f%QGv%BH0IBsE@?)"
    b"SV4f4mDFe8x~4~LR0bwn@am7(t(N7ol5qXtO40WfIuPPzwhT`yAR1H}Xqm`@-)B^qa(n+Iq7|%8A~>%igg!OIW8;tYEDCFRcaqwc"
    b"#QIKj3R}#kC1b{(q`S2~u`(3p@X_EJ)3Ue9e8yUL_K|e_e~JAkY|bMP@0cAz9D!ypFtgY&KuPEad6vg>fJplkX{i==>TMzs$gJH1"
    b"!{c{h$sbX!+8}gV#jJIk6`f#$g%E(vxV`p-W#<?`LYi$KeL-lK3Y{p+6h|^&&Yc<+NE&_g(U{g%6fk}FC!X(6JsXSyfwgqx9j|k+"
    b"SMMrDKK9H|ETDq#$uTOOMu<PRo&Mvf9T2QSu{$d)1eG;lEfZKbnjON6?$?r8hXmU$GBUDxjeQTH1}T-6ko>!$cp#Y>Gv}0h@z5+Q"
    b"5<wwHhr19LnfvQLIVzRbd2cI5sj80>o@Pm@n-<Ea7hYV~qtv`%`z~%UbIw*#7+-Y#Dq~i>4w{@t6okAZ-*4F|y;wCADqXe;L5m?L"
    b"v{B(<cYd3NQ-V~H0hV}Q72%P3a)!AEKVUh)nO+2@8-#SvddO=#jkmx~ZrnAc8(o(B#$Aj1i+`1Eo1APKl8OWpZatK<DZ8AdLR^$a"
    b"hqcGR=>3cVX58bmlDzFWIR)~0D5SC=-vA$9I3c2}EJ0~y3Zcwt{wBm<^vkBhOYwGN7C_R4z0X(q8LSCWDhXymx0lKgJ1L_WDl9G_"
    b"3i(WSI_fdgMqE*q%A_4g8}y%%JxMM0_+JD-wO!X<7Z(!MO*4w`u|**W;7vG|bKMd-awcQYa@;lx4wh3q@y*$Oc=#R!+%NP(L@xQo"
    b"nGEilg0rmxb|Xu+W^GdniuGd7zvE9&^H}J?!;9RHg^Y!9a5-jk3dMAw5U^Pi#CS!aH;ASK>g@}f(|RT{o!%tDG!^Y>q0ib^p1jyT"
    b"yBgi1n55sWDViKjS=C}p$=fLYtnQI!6u3tOL{5PGAbY3s&-YodpwSx_;E|nk@<N>9RRDxFI>N!68s(k$OiXgIMhgT@7BQ2WuAydV"
    b"n{TSTkN-3v8VW>jPonm2pk?$u+rF{0Vf#>2^OYYpO-0dvGJV&Lc9YlXnuBG0o5}}dP$`?0Nr>2SLZ-Ua3y>_8e=UUn`1~!p`{V=J"
    b"4FKzczj8c(jeoQq9tmPS*__Hgy}jrr3H!|Nbu1ecy1`q)S4OXax$8VV&ibx^O72<$QdxBZ{JVvIxNT8|!&Z$Sj68C6Bi`ayd=bvW"
    b"_iKc7QskjoeZ~bmgB9a3wXWmPNMzG9QB2vnCD%RuFe(zKI^keKT_?vLUSGUnQPerPO2g`PbE<HG7Td=y#dgdBr`N17qYxbU$y)N0"
    b"m*OEgx@?K9;gS05`6B<NVgTT@LjWA?TXcUjc5>9bO}8SV@N_V3y=9^gz-f2wpc_eu4kJZF_4JHME0A}yvw7v&=lVDua8%Fj>oG5H"
    b"WHcrFm6~-61v+SHKTA$UhI~eR7^3Fa3AiFmV(Q;2`O?}N)abeEczVs9rsYY0kr6PWCmD$A9Jc{<PnL4hD3EXCYiUJgWe*C%$kP;d"
    b"W%dY4?bs{$dJc{^1V%NOG<?<7g4lw_=%~1#$X@zW4lkjLcDJF_ZpaZj=;>b#Zn6+4l)N!F?!3>2qWX{%VTwe0u7ABR0Y{}!bz=^k"
    b"7hwuYH;$_Zk;>*;mOV1<P=M!jW7EuDngrPPSV@BRWR8C%Y&%Hqik-Kg?po?VtcVvFX?JuXGi!Fy+Gh9cq9L7af`N76%HALkS^Vyk"
    b"$Bt_O|E$?1X)#Y#$d<muGXSyyPL;0}Lkr?RZi_FP6(X~i;li_rX^LMRbnf~UNW=YF8A^-@Doi`=7|T&0ksihJc8Nk6%}qtLVASxR"
    b"VE;|q+MZhK-C5>&4H!0{wFDU0d(at9%FF}6bkG|&OcOkvKBk@p=;0EtJ)o@0V04Jo>Ze)}Rd-Ml@Yx8HaB@{EZad+>)LoR{m0aX%"
    b"b)F=tSfc;&uuX2K35iWsctI)tzb5toGO{i(PltmxpJOAE0AR?`%&ipa)&XYijmmi8$00$*2g%E$-jaeENLqCc^k5G<X4o4qAwf`d"
    b"wp@0KDfF~CzJj`96peYttm~he3bGym2WlwlW-)Aj-W?X_<3B2dEkZ*nVNJ=Hokq+7uEz({W~4$Jfa|vtKi%`IWgSV4I!w=C3ql#p"
    b"B*omvRVy?gBE9JSavJvEVa-E@g4gPC(NkVI7#W30iAXg5&OCud1D+ciCjcAPT#YFx_foO0lSq(RMUE_Hxb@Dd`S?Orsya%pQ;sp-"
    b"vO0thjF1qY(+$K~ua<^}62#`od7KNkxMH5KZ$rG2CT(z1@Y=og)GCFFx>3WL&7n6NuFHYq(yOmPk0J##%pC}mcUN~2j`dT3LeC{|"
    b"&%G_99_QR^!L$gaJ$gA)`I2MXZrcFHmT#G15<q7iESy#9W`BZf*%&23-afoEmqw58@2Vi2XlVWvPxNYg|D&_W&rxI3g}R+ia^x|F"
    b"|Lv<d14PRHVZ-zV0y1kmKftpg=|*1Z843D7im?y6AK&oaxqf54s%jA^4F}8<)UzEq<T@4>dX~`-vPtZeKrRils>36f`s=9IF&xkU"
    b"pZAL8+nG&kTmG2EsS19KcB`Q?tM9!yiPciA?qKQT54&ei+{gdDzk_2A>V@_Sdp*ouFwcZSjBG|eudD{!uG6>Kj0%I5w$mLF7(j?c"
    b"^+lc0hS=cjp`9R|2nhWcJl)#hrzT={QRVu<PK>&#@VGEEb=+vCxHOuod62l*5%yI7G|$r$13h`Tka1NWii?ZZM|)B~Ti;V+6^%&>"
    b"$Q6z2&HA{o#nmM$r*<<rJ!<_QODN%~94&@(okR5UOmk@Ye6;{^g8ifgLz0!6bch#}DEUlkxB06w>yo-hb=-Meqnz}1As(yJ5tj@&"
    b"J?#SF#TAm#^BS*(gw--dVnyqMU@y24lZ&6!Xc4J6;S#GudiByup|(9+{fHIt4=~5o_G?VWr6D%2$Hc2e8|n1}oRlp%qnx)Ooyv$N"
    b";ezp)K8d;f`qTdGxnv6kcu7FjL!fnA<?lFTiF!mGx)%B+e%(9CotJt-x#Vr@vh8e^%~2QTZlpaaJAPZkWG8@EX4NR!FRFu323Fs2"
    b"bwIWsvQZ`{tqBMCK^?zDcJ6@~O5HEC!G;UdeKfvy^1QIq@vsgRzydOvyDf^Qut%H&h<r|^>iz_;a^fg64iq7JQR^AK&k!D7C1N8f"
    b"*jISv2q6buwtXQl@7Y@RGdh=vLYRUeNp-zs+IN4Yj^e{|U;Owt1|&>59@EB6Pj!L-BC*o3Ea<~T;n2CF`pD{ZIJu9k#^$n!8v?+Q"
    b"kTBSc@2@@9t8g*h7zf50>ED)^EK0y{4DE8l3$PRhVP!zB!4RubaSP6YJ?lDf&udA4zhcOl8`voO4}#OWcvmRxWoo#{!(<$g6-){~"
    b"<S^TR+3t3^)lgSfmO!*``l|yUR!|d6@ba=nD(H3&n5;pwtx+^Tsk<H=j(~9%5)(@&7W`wdQ@iWSVNC93aofjhzawZ@IUNtr!`fBX"
    b"He6jxl)h+Q4`@r{6YvBl{v<)ExE9e(DC8`dvV?h}24v*K*bn%}C=3{jrld&R!6=>i*zeY*4uhXIWsXQqlO0n>3QC2Luqn$UCXZ|L"
    b"-qT>O>5RZ{!dm-VTtz7IK*EGe(B)h?RmESYQ>n_hjujjXfHbSoB=`kdPu^BV|Eb)^4r0gVq8)(nyKXiq?~dSK!>~bQbK6eN9EybL"
    b"8m*)o!qAg#H<y+{qoEbuDd!sV@@26!U|6$q5wZqTQdw7RRq#MsNrq*wyZQsxe*x|l^HhMVPe?4rdV+P(&Bl2ILBo)~@p)6bJeX)N"
    b"IOo9E8QMj`bk4}*1$D&;=rq{6n$`DYjH9@@`%mPRG<dS!M7QF?S3UpZu_yeV9|FJETw@${kE4uNp!mH<6SJ8$-+SNI;rJJ2KjJk%"
    b"8|E80a%TKJ_%VxsZVK_=p%g_eJ#>8Hs3|ZqX-=_0nA&NP<nByUBn?WCw_<T_N$VNMzR2Wwn=H#Al<vdxg?e=0n2T<p@Q@Iz|MP$k"
    b"<k9;Q9ABDH1m_hsnkzz&AilUkNEpQ~C-5}!s%wOM8hxy1q+>YmKvr6&gt?CqFdKoK(U%oa>Gu=bL5Hf_h9lPW`=qXLVPn8Fv=&;P"
    b"-O%zXFvNo>#kh6%;of_fGi1~*Qi=l|u@B&L{LikvXq5mVKvDihh#J^><&&}3i5)<=YH;C|dcS=7duyf0BOb{r8OQEh?mk|Raw1j1"
    b"`%QV;kP6fHst$rsydf%;8@i->N!!^IcL`Hsjs=D&^w!jb;klSIC`XCP>3_~p>{Z<)RSS{-!q7bQLN><ruckHJDGa*fF#QeDru7h*"
    b"6gMFl>Zv4}Nr8)%{4`G2P9>McNk6=Dgkb0yFeK`c8zi9+$QCl$wo~+fFBLTng!LQrw>6#uU@ox+j8lxk&YT|o{wT(>Xdkwj#{ceE"
    b"S?Jki5{Lo{%dH0x;m^b+n*rL%qc-i?h-#2`-`{Qg$c!o)x>j|RQt}GM1ACMzXTM{n0nFYu=yW%jjx2)zvXqNdKFKA9srQx_bW)2O"
    b"E#iy3o#uF2TkLt8Sd7@UN^Q4rQGr6mn=wJH6VSv5`5FI%DmR$ublTR0c$pR^QaE$^9<$^b(`5)uU(kOBV=3Ke^jB{+H91qJu%of{"
    b"Pe+@4qgQ=+RF0;icGx2mJGm>GDP!~4Pn=*%xWSeZO23wC)D#0t?#wpyAD&k5WQAX^mCIl1k4z}B;bdt^jLZWp6x0~sLB;iNxCi!#"
    b"J%|Z_hqg=dRp7=-&>}H9)5OXV$AF3MgxH&+Xr*c49vy5*t^h(DQZ!xeY;0Wg<N*%4fhqL5e&JhqyMNV(&!EhK+!>)y2D9KpAbIhO"
    b"XxPUgGmZ3%Ib7I;m(K~9g{eY5fUeV{T1qG0b-e;Tnsl@-z9@knhno`%Z06}{vdQIuMi+RuQ5UGkSHVAZ+OT6(JX&E~*kB8GhlSB+"
    b"wG+>cU{i`FrALB!pH4;NR1tPtbr0NT$zblcs^ZKM==7@9M_5-(V*02p4ya*s`k&IoBx_ohLPv6BOGN$Az+h%@6;>sD^=43{p^_3O"
    b"KzL^~DAN?obao6ED|zyhSK5}XL0VkywT@<<9nt6S7CA`1H6@8p_=^Df6n&`yu_(pwXE>7?YiyZh20(h?uv}a#gAwND?YGZg#8}kR"
    b"erZI7zc=Ep@nw=yHAWc$T6`wRG8Ln?vYzT~p%7ttnBy#=wcgDOh(1pNe)t6}d~`PHd-BK}#~1;zt+ZXzCS|$3mhVkq1!R;I-0G^$"
    b"YD>e&1-soCz~|<8wOE_+;#lpvS-qFbNJYCo@&n0fbsNo|5v1*UB7QuLD;^1Sl-o`L+vGw;bbKnmEr(PP<kk{`O+0M0o$MMnjCLzT"
    b"*ZooC*Nx^d?L~X|2i!rg#TbGo;XdG~#refJSK%Vhj>pR;A`Cr(s&&!YL(M0H3{bD_F_XL8g8R|BixzUSWy1&x$s2^SAo;1TSTZ|2"
    b"@vWrSu7B3o>yj-bx5MfA{L@gru+ownA*(Rfz1<@UU>qOQTZ00>{<Js{?=`h>KjlB3u6NJi=B#8JGe{~BLnCPjl+2v-&2rrqiKqn("
    b"9j>pU?!>~m-)<xV;09Z^84lhX&#!g-4m(AnDqdA=3tm$OXg*#@C^pG+Hv<wshGe|!=n(L??@(%lub0=!l+K<srEAwJB%Sv<rUsfz"
    b"{-7l>>iGoqc<K1WAOMk!>>C6Xg+c05PfhI#)nhJptu-6s2*7qwk5>W3)i8X-=z?}y5DMGn7s&-<|EyoSA<Dj3Kz%4)p4;Ns{!jH?"
    b"%VRoth&^B@>KCF7*p3S0mzJ9!m_0vmTzm41APCJ>m!>Us_S1GURG|4{5f!CS1<25m2lc#U_MQ?!q~w1pzcB7jY?ITQ$;hnWH*}-)"
    b"nZ*OkSIQfcV{A&OsFF4XMOBDdAj-A=IV`Xqi+TeO@`ZDm&Me;`J#eC{$P4R0X#~$Z5lYA_?EMe1Hf_qBhHDSnG`W#9^r5mF?k$|i"
    b"$4=+?3$sK{@_>@itp$`5WyNPu+J>cXW3fDf%H~}F;B!8hL@S~1x|1{yUGC<O2IlaMns~^;;&rtQgOzL#)j(mYGMM!M5j+Sf2ITT9"
    b"N|*Pc&*svK8VM&|I!o=Iu-j0{rM`JaaMaNsH*a}NHHHN4X)z2d?21sS0PnHbDO3kSuHqWT`k4^oA#m#^O3^QDiEEQb19c2rw9{8i"
    b"bPia)2UB(!g4ygI1?lNlO{f8rEf0K8MQV5YU2WFQ4FKp$Guif->1keo8d|3s&i-M&q238A9O<J6Che<)PEss`g)1j?q(<gP`nTWq"
    b"=UFZ;RpzJ55SWXpVOSYwas+FzdJz~{AmDYz#}PnH3(E}Z?DVc(G2+zYCGkb;7fVJ2QPX1(UEa4!f{sgFI-(Rres?`scFv=Xe_rub"
    b"1FXDt#`&YqbcIw%e(m54pDZ<H7vz;^hWHx-3-nFp`UXm8Vmei>RA6%G24>FAnYcx6$GAs~;3*4(qs-fu<I!95(6==1&qPxqBe%<P"
    b"gK^{|pTy*v=kvRmH(Xz9<59qPo|>7Jc0d52!<+=W$rEY|lj!rBQk<btl}v6Me9F2*FLZ{g9F{VH3E7uaz24&~T~u)iT;R2-M&B$O"
    b"sv31{sh`MLJD1&`;ig$ym>c9w_J?J8+g!IJIcvf|yC8SwjkWp2w4Q4LU&^aEgUOs)qheYk&3@lRF^$L?At?Idm3yYCI4`jUKNT_`"
    b"a-+>^W%>xLi@LxVe~|O?tpODw?Ua}n9@vlb0m+qy!NQIfDDqSeOq=YLXdtjj8uJ;}OSaL##uzT`{VIX>e(NkgOW7gAo9IT+l*Til"
    b"$Y-1qntns3SP_K5eqGnp^SJJq+_AEToZTpeywx4`?m9z<E1dks{w1iEyvSvLyPUh$Ou4KyL0HSh6h^2xh5_kk=b#!G1i49ha)V(W"
    b"bLojz7dCy00Y!6@>dHh2DCIP^hCV_70BwJII=D&j=90D18OsxnK3UrbYeQ3DB#Kj}b_Xxanl$)WgK~wTTUuF?ou?VkKOn^IW)hMx"
    b"{tb4?PJLl6S?Hq39?_C!|Fzp{4oStJyqL?E#c!HjcKB$9u)c_UQRh3#V^oaO+zC3R3GK2?=i6qj5?Z9yF(4>8*Ep7W%(6#NvUaN$"
    b"2q$GjXv0TGgubDhsg%}#j2@hJ^z^!mTJ=y$n{I^+aM)G7zzaIA(IwrhKZSWTSI1ubIPSy)K>5yYA#O~1z-p)=^Betny;jUd?v<f6"
    b"1=Q|tCb2UnaD8f5kAzeeZwiwZh?@Hq`hOdSR)E8vc)SUSuQJ#yvK=n<9-i<#UO<x`G*?jkT<>iC_B^%ysTzp;Z6?r+WZ6acz3F?S"
    b"oV*v8c%%acjB1Y{QVdhZvRfdp1RI&~Kh%Gn7!U_R`>srk8hgKu0Ga??yg{jHW^I}^x%X-iH9oM?T_y(akQso3t_pl|1VIzn>S_~E"
    b"G_smC*AH}k@<j|?kxvMpYzxe=0G%2`Nr`AZma5QP#*ErlZ&|hj+SfX<#()-Y(83MVhT{K(Xu+dQy^;kOG^Nxi(eArC>WaYJBR-9l"
    b"3Ua;oMnz0#_^EcCK{;-DNTNnF2Z2d^)8tasT0{jH37gJU=fSo2J+vW(ClhwWXp15#h3d=7c3-G{x!JYW2FsJaaOUY%TBO=4l)+Ux"
    b"X92cai0A^jZjbCNRETHquv4g1Uvud!(rdAuFIu+WN+n;0v1qR;%7`DO_-cUM+lv$~bO1|K2k}n#Vpz_64aaRK#pfG^jdyR$2S`NB"
    b"AZU}^*q!Ny7^z$gTt7CZ1?uDx@(kh1F|J11Lq7PBTsxauG+J_V(|D%btFt>2IY5CY$3LRbhv@hHf$A-Lvt&6QQ%)?VsLvO2>_TsF"
    b"sv2xhHD-+BR_t{@y2RyJa2K|Pz!Wzyn**<ZZD+NB2C5x~(M^^9&~N(`gOe~2y=-pP7%zJeR02^#NL@h`Ctiif?@c=oG*BaZkc95%"
    b"$+MsC<ZcUIxmb7Job^U4?x6e`hEos0F2@k*P!f*ua0$CDCo@C@27!9-a?Q-zmwy>szvCLHImsm)bxKcNQ6;?73iQLE6QZom7wFav"
    b"GT=Uj2&FVkVsUd}U%5pcS5#`4xp*l@n@bpL$B)n-8+-Hk>_klNePHIwJb%Uq9_3`78Cl7R(_xg?GBCos>GJBew8^1;8U=?)ybjyK"
    b"aP>-%PMNeV(xUV1C@ueqf2Jqj`I%kRm8qCM!nc%5ie<b01_DD=KI{_>E$Mwg7Zz7u{Oy{;7>FrVtA3f`fnUIfU#|}0US~6h0leCW"
    b"MfRDLH9sgO!lH0i0RI&y{b?%}udySMI<~rqga-CZS4%GOu?0&Od@`Vq?bBbf+A+GINupUYo-Y?8FFuEIjLT5^JJLYX!h$QI8!*eL"
    b"863JeVrPOzEGfB)(wjkz%y9EZ+d8wB2#yua6+bX((9A`OhL;Rd_-|%mxE0$CO*am^MoNW6Kt=FRtl^bOd!Mv-(vLQ}f}qC6)7~1q"
    b"7RR<_aMnm;3X3O`bi0O5!G8*Ras|GL+=}5r5q6e1AQe-lWCeDKy5yjc*{##|`yj~U0%ay|^ERc@47_2;>xj|(hMk`cX5sE$O?6Oz"
    b"xDON5kBFa@oVA=Zg4}pKL<S?CfbN1b*ZW5(z(3RQ;QVj$pU*?rQ{3L_>=WR2sy8IJ<W!-FN9;EsCKZ}oeFsNL(;v70T2H*c)tZA$"
    b"c&n`yok=4A92^(@&ewFGWZ;5Q7nlAIFVigsaV5tjR1HV4n+cG*@f8VI=LAdz{lNmMtM$<@H290tX53ajwE1NaOwYs_$&c<E!k6?L"
    b"uZ<W&jgge=LovwUQ$B{(13S&v3il!z%GghGD6&P;0veJ{t2Ti9zZI!mxxvn_^}*@q)5K>|I_;NJm!}m}HM$zX`chOt5|yBdAi+xZ"
    b"SuUM^7OveCn9+qZMdeQ|5lJ#gQ0Y!iQ|m~QLC8To_4BX$KcEVUx*#h0W}q&Dv#53L)Qaq^i{A*~AbuA5uVP29;7!L$ty4nfDSY<y"
    b"%0z-oInA^~N*u{wn!q8U*`rgoa!~&}AK_vTv%}`bP09iZ^e^Z30k?>;xQ9Z?EppKvtQ7*4m5bB~BjD4-%A^S@T3hgCYA~QGTs!1j"
    b"Jj&;E{0V%iv#;Gw8FymI6`#gJV(?5w2jU{|tA$E<pct2Qnh#(pH;b=cr{O9Oc2(CubT4UioVcBa=cY@S8*uG$)J9s`OMa4jQpKdG"
    b"BQ}N3BPDtR2=_1E_!p4QY~q*pX{F2gl=Ti>1JbKko=7u#j{gc0fve(HoPNX<%^%eB25dW@FoFUAFP7y}|Jhe`u{bkSA;pof_&RCT"
    b"4<|$KIhazWVC$%p6fx$u>b7|Fg4Jmd)}}Rw=H3>)?;wXZ8J9nm{Pl<a2*%>rDp-}Kbd>}Mqb}+c+70lP*0mLk=yAkIlkxry;7W+^"
    b"fCd_&`t8N8XB>zYKksd!Y*b%pPV^Dzj`tz3L^VhE?sF??=tuzQF>LDA7HHJ2UvASoWf+|{q`9Q20Q-SR`Oe~|56m`V!D3&Iyk#?x"
    b"rMtXG(0>pOi2p}(hInfC0Nqmu$91=8eL6)DCGlv8PMy$%*Z~IdysvTNxoRlGt@~3(NIMY0+T^~|2}&>)oM0|p+|Q*upVb<I9woqg"
    b"u;zY0K?A54-^=^n%4ZAE9*^Njh<lYTBsCoIm(U=7ze3{vYQYSejkbuuq)L9hu7u0&r`6bG;)XYAY@DJSo8=6CR}ZygVXV}VnJ%5J"
    b"+lsjG<D$LS(!dzHu1>i=E8X7Rz!KB=N7w{b?~8J#Xlqe}z47SQ5Xmkb>SZu7rlkGb-_wi%a7=?y17(1ng{`KHj;%W|Lo;AHcMEXZ"
    b"jjk3egB`sv3A|VxL;sW5uV0Hz+8|r~0g3)-C2hJlee^Dlm%8HOk#F4Q95r@9(KL+K4T1kI+79b0B19(tcKQ@|-)UVAR!_ty2ZNlp"
    b"htROwY}Z$q7^HbYt2H0VA|$HZdLc`x2!ft|Y%Nvd7>eK}^qMxt3a1xhy?R_PNAUva)z*f~OulA$&+VsCod;Pe@B2VUlL1<77&bOB"
    b"S1sf(wE91qftN2o_sX&^V=^T-;0wZc1u^0*b-R$Z;3J<!W*Rf2wsBmrq}~`eBU@LSe0<VvcjEnrS{aflmXqz8QaCkK3Uz`t^T6-P"
    b"@$~`_i~0GsnIYQ{Jx)u%!Is-9&pxrz*Uzh|Wo1wY(*rs<TG+M&p^@A!Qdxel34HQuLA$~csud+vyX!CHzh<yxP^k)DcYfR-6Fug6"
    b"+xocMfYinOqw^^^U+XnZ8mtt43)o;1q(q~2=ZfojQCr&La4tM3<Pjb($_#r5;7DHeApBkC7ga2f%Q7N-NvrqLiFQ&l(V<TN9SdtV"
    b"WmR98D@Lnb$!YA3Ks=8%>atu8Ri7`BU7uik08aK;Hs_Ia+7@EsJXeiiQ(WJMSX>+BiSy!O@Vv0ZUAsx06E{wN8-=Llw-%<s6b~2k"
    b"L5#R%ciidqinSN0>rVwM7=5cUT)W6K#%`_4jAMh?d!Md}O~guu^aoT@YqDfxOwVfgIn$;-E>RpP&MrM!qgynHsI&EsGAU2IhM2+9"
    b"Yza=sp?bGD`8eW(W?IpQ3B3i|(<>2`tYXx2O%an-9WtS*)n68<l7E7gjE=K-=STp;>8g*TxztDagI}xz5iD&8Y(soG(HPrakHnNR"
    b"1ULfEI&AuAXEJ&cl?@K|L0hUvtx@f!5DMPw=VB`nZ_PIvucach+`SBzn1G6|Zk&7!;9txSamiD_lVO^x$|PRn8Q=K#0zX!E`k&t("
    b")HMMy^QF(3qV*l?UMjAaxF#$ZL{uI~t+JpwRX>ljLM{vU0smArb~6K^xKuySpqVF&8iu{sOKr?h-e#gPE`9#!#}E&oQW?hdiDxoB"
    b"=Nl#)oojVF!NmDj&SwconAKoc_!Pk)7pn7!!&T%TkocU(Msxa==y$!cT{nIRZ-LK5A0l%2uYC+5NDmmcm?701e)@rg`O(sD9cO$8"
    b"G1p%6oG?*)7<$@+2?FaDM+&4YCrn`^$7i6~|NQp*^=BfG2E8F+#zRgP%f2!74;N`eDWRh9n{;8KmF!J&^z)K5juID-Y?#6h5_Sf{"
    b">B)MoA0<SpaN-XzsrI5~k0%jFsWbJ&cwL$E5~ME{#+8$|mSTSaaRs`oyXj|Sxwn_wz|6!XIad7su4fc5fB;LOZoZ${V%0-S`f8CB"
    b"|AL~n!#BeYJ609{SnDg;rl^@*nj0s+)=h}fg(x=h`0AVs&@}bhRoL+o-qS4De(RY6q~JFL2Q@!!50)f_{ir~x@=|d&Qx2k-KiIXX"
    b"COS(RLy09h?m?J8%`NMCZPYaAwnS+z`~PuMibvIlMXa=Ag5#6r?g<$^LDFXh?72}uxySXIkf_Xwwo8l(NC5KPU#Ea3PM+C+vq==$"
    b"MivpDyDw2)zhjSOGJw+0R|juv-CLf|`~<FdAgS1W6N@lm!xBa>75Ooer?RoLf<NyLsb_62<)LnGCCv%5hAUc%nA9T|!{pd7`3M2T"
    b"$^E1M%gV|I*@0q6an|ru7yeNbYm?&e)o8PYczK1goHX>z`LtzK-g=)V4$iyQ=aVYi?vO6LksyoI$nUE)Ak=MJ#F^k0{|zPGQ%Sgx"
    b"U1(ad(+&w2`AJV3ec?pu0UYRbJhjdJ{^yj>3Woc~DHo5vm3%1V7xGiuS|vGkN*X}QKXlXg)oOIAxpPrHSch+FOff=7mH*qbTW)@Z"
    b";k&i>85c~xb|r?x`1hfRPE{N8Wl6J|rPcdvW9M}ZgboO{{r3|){mT4*zi&m3$s-O{mg_($Ixr2J8AeP^l`BpY-2B;H0Naptb6|2y"
    b"${HA!0~fld1PLkO-_Y`SQt|GA2TV^62CvBbI4gof+v9RINHghH7q1;#_9W1}_Uw(!bdSRZlXADMwadcBEZNkzD|87%Q5F}y^w1mM"
    b"fXI8xZ_ENH`HBYuq+$|U7h(zw$F_v@T#8}#fE5bbFljVhy}7?>f6>@zv8M1*b6-kmXYRWrvIV0Fez^I8^A@h#3Yeo`wE!^pCmjBI"
    b"-AP-9B3|40kj6pZpquG!pu*L@_jv-d8Tl^4)NI8we}F|8v#wvC3+()-qyn}aM_<^|TNWx?jXjYML}wVADaqJ~7@1LlF~p?8nHxO^"
    b"Q(vK#TC^`BoTuW+yXWTn-)2l0iY4pfJY5y-YLU_*g5}nw@dgx0*>ZSp3SIp6X*<>O!zfMq6QQj#dR8eEx3`@$JMd+Kc<X_0UG7GJ"
    b"PP+@wTiAS$R>huDlp8^Mml(tG(=b}kV15+m;;D|Ubmw$RQxC%t@4>jj$;mPqUYwf~3z!mbnHjt)fJzZ!Qwc{$Ys1d(UiNy%ge;3G"
    b"?Hb4`f`(R#oc{B5OUWDJt-hCekFf93a0|`W8JnRc_KRuY;G1uwfDpm&0r;J?b|ULcGLu^j)$-Cpt|?*?9Jm^Ak*v(=d-w*Z`SnU6"
    b"2c3@0)fA~R-^;jEM!rfzv3vOU{e43~vZHvpKk~_~51C%Wa!uXzfbAwi0UMouOq&57-|f0?0k#o?t#@r1_C#Lu`0)q46^-QmULDa4"
    b"UB9XWPc*ie+ZlhoyRy9^oHJZ&D`7jbdT3iBd*eWASJuJ+8x3s<wUY2OedCeK6yq|WEKRAsjQ>|fG2og;7RsyC%Q}@41jGeklkIAi"
    b"x|(Cn-}JR+#|l*Ojd+^OI6R~;7xkXB4t4*Piwd5Qsg4%Bpg)dDXf=UUM)50#FKkoQ<ILY|<E|mF<Vvf@jJppM8RwiWp}h42hbvvj"
    b"#@-1K){-fL<e2ywi;Kc(ijx=>#(jqBPqu%1T%PVxTisq3Yu4=3s9oQ`XFmcV;WGJbSG^9|J2~TgI?JDie?6<**#ou@d3k|Cq6oy#"
    b"8iMzgNq3W(hR$T>b%mxKGJZ7&KpD8~&XvzNs!B+>Lz<;NtM^@eJ4PHDavF;11_)E@Z$P`?T6<P8mewI=FU2G%_909)-*;b{A60F-"
    b"NVp!o7rHqd5i`Fez>1mgwAZx<c~UIQBe2)p-hbzE4@?;L9@NfaEEI^$N6=BFchbK<y%*w(v}R%5f#wAve$LTg{I=o6njB!4uL+$L"
    b"@7|Slj}k-I>+LWajCW=(y%dZ(ae#N0-;GnNK+99Juo7N14nf8!F}v|M0+MfI{Jfn=P^Ybmdfhq;47;m<?YhYZ-tE-#JWg|=?LYoq"
    b"4C8qMOswyt^<YYlqP(=4n=2QYt3XP~MhA~%nj;9=n;^x3ZQk{1bdH%S_4Y-Aen;eux;EeYrvmok<5CfALOUzQx}upUyMLdUOzy1y"
    b"?^lY6J;^c8>)v2u$c*ftI@kvqKa~qb93jLvJ_W`usxJ`PnvZ&srPj`HA)g~|ghrC)?#n{fOkxx3sHdYYJs-@UUX#s)srvOj6bPSk"
    b"`y(rH7+&(Zp-=@HzKSkx1C&&I?18s+$k2}AE6&PhDs_UD?4HNqjG`ShOws^9l4C<GR-We*oCHMxuBlBMpe(B=`uPJnuMJo9(8{!<"
    b"s3`7Dt^YF@Vjbl;sj8OU`6M~r+sb3b#cx-=BwiwVQnZFu$7Hg@R!W{QA5E+RDDOrPTbmsV5!I!ZyT8^Q7^T^}5udvG*FGBALOo-X"
    b"W_|kjPpNrII8>&sY5nZ8&t7k-?sxP<PC-`F8(`v`<C?%1q`yORS9b^X2#-&P%{~x2HTcOb^PONTA@9)%y^5zZYwVqOUfWMkrS*d4"
    b"XZE`|2~Y4zWAbpiE+|)a(~kh(5Behd*}9vEEnk~$za1og*pal2Y6tHJ+H?nMI8O>41sW<j?PHyH3!Xklo}-W_!6Opi+r+D>t$<NV"
    b"rld{8P}!^x%o8Sqo3)hemtVlkVb^8kDhfKst}k2c&OdyXvfb5yHvSyo9CJL^f1p&HK3-l)H5@Q+{}g2K-LsD>l<L7yHL-7DA-fbS"
    b"PJF|vR6gx_{g_Cd*%gVKfctdV%1e1gV$em2*pedM<1ZcoKixeh^x<mhNTm5HTU-x7{EzXr<hvuO*+k|F<}soLRCt>Qa}+#^YK<k<"
    b"#vuCFnF9Lb`al|BqLR(rW}K+hECS}o*wA4S<3}vkX&R*(0ui@tML`D>`=|}SARUv@P<VZMOCvxtjiW5F1%^I|K&|~zub^WE+1l%b"
    b"?}5r0ovhzf*pvj!_GhA?OIu;z|3GB{hsI$rGGNEzXAd9B*16g8aLyt8UHpG?=4o%?q?2Wgeb<0SkI;Vut^QhpQh)^wi8OWiyml}|"
    b"8Cr2piB30L#qQGCBXB6xZgKvBDJSw}9-1{R!N2d8c%M&VQ!^<2uKNaSPDmEgbjYO|JFVBi?D@sf>X7bLEAx9q!?w88`awm)RZ;cm"
    b"C1!Z#Ey>bMOutvt;GLTu)EXq3c-nB#V`4t|>QJP`JGS&MDKu|*p#Ejfydp)eJmWK+ZQEh#sif>$jKCm5U-iUM^@?*d&JlC7aZ7EH"
    b"e_OQkw)(QQ#^hXV^eG+1K~~Y(C`|258&kP|9w|^|=;Q46ZVOJ2#cD7QvpCCAf6(`T=@>FGc2AKEw(OM&%YnOWh&yR3q391{wwP!J"
    b">rl%e;?Hs-0BQO#i=P2YYWuP-(2!_OGDl5p2cT5q0vh<;e-Pg&+-#PRl1?xqvM&x;_J~u|@D6a3hsP-?*F7O#7T{vfrr}#23#ct+"
    b"6!fYKGK2<_TilkUB<Mvk+&C`#lpRUe7|QEReaQkr!DDBbO(kYb*s|tvJ}Q?VAfuZ4^%@sVc4oX#L19)X18wlSCf&KkQv$J@M`AaI"
    b"0alWLfJ`dybLSC^=YV;nA4d#Ck?gu~)b0VZPhT$)VA;sdWE>ZVK~68;s{C2l?3@j`vDk|&B#378w*Xo5oLL`d{Z523pul?b02)@f"
    b"a_%jNFrgGB!Y0&wV>KG#pLS?*(2O}EdC+DtNhwz{CSB&&Z60Z!n0Co*x^=KBX4y@;U5G`=*8OCo-VPC5<0ykQ;>gUBG3<OA0Rm}#"
    b"T@H{b7MoZD{kh>0qAFwZrt3dnCc?#Oe;Vo_)rb%1+d-=ag-xxPLhs{0>75h`f(Hm&^L=(P9z)|&Jes2O8O<2|wb%q3{q>H>Abvt~"
    b"$s+WM<(`%UWHQ;$v?*8Wrwah|XE&Kj>Feo(4P(q^1c9d={Y(JqFl};hq>Ge6QMdXN3~v6FM?5VX3pL#9d9DU}q7fQ3Zbh3Da`PSG"
    b"wyx#j2w5&RR)&0|l>J0#^1&Y$$F~&frx#Ujs6=47mHgP8IGvsgLbRY7Jp8`5LeG@}YS89u9_tp6My$QMpfG>ON=J46c%u+q4YpG*"
    b"ywp9fCO$E#hS=%NO$N2l6fBR57FC5OZjQZ11RE9T-rHFytDvfv#LpL+opM6W&ex)jui8MOL!f#Ase+uiBhP#BmZxeAxqbqgGhT`1"
    b"uJ4ZhU_xlk->26(F1-g9_o|m)f`5Eu1P*rO_79~kJ4Hl~sy#tCnmH60ZiFT4^{Uemfu)lenyN9YwQ7wzzk0T)i3ScbCjg-o%Fh+m"
    b"icA`bgP}3(`g3#X?FV&}P8HAhGePS~OsrbYioIAbY)noAa6AlnrU&=!<RE0ZC1cPZ69Us=I()6%MVh&p{ROJforfd|g*|(BwOkrK"
    b"z^S7hiekSt*AKd{pZ%Cp=~St9r%?nGI?uD&dI&S*QZ%G58wa7D<)zOHlN$T&B7qd!YG-h|Y5Z4qlPHXy3kP|(`=jt8IlZAMh6#dU"
    b"b4%o4uIPSQvswwCrMovW{7}7>%9FLn686=_j1~yz|CtyRHsXE_`;$#?GHkvGwoA>dEEk;yht&<UVyKK)HXy-F9qS78M`}qjkSIV0"
    b"#28P`b6dt*=J~d)z<UzwgPrO@$z;dp+yqB{xL2Ip0t3uxQjLOqK>4#)CJP5poM%J8Mxgx`7WXuX$1Oq!HuU%_0_WY56;ut5dVT%_"
    b"h6h(lPU@y?4wF%uA*k(dgO{t5a|T#lQa8wiA;JpnE8RV;`*QrA>y(=eA_TjZTe1~wvK)*C9<&2TJ5A^1rhD2TcH#FHPbRM)=6^+6"
    b"4LLN>Vmiu9%N)G>1Sds^+#Z9&v=)?PN%QfPRc9usHeqH|-IWt&J@CM&m~g4rn!s}(*fT?<hu3V7+HEy0ybtswPETJT#oet%?v?@j"
    b"lnHd!$22DFc^_j%7b2B}fPlre2(&CxcN)D3HGCJT_kFe~U)=9Gs0c@=Qd})C>DUw%e92_*nfa#}0=q`05I?LMyh#xV!C`acBI@Bt"
    b"6KW{^>3G%L3`P*smouMtpevckKfksNR`U6z{ned0L^R#Y)T?hJKKr^x*ejAfi{xH=7=PK|iKO<l3~`n)%XZkmMZ<O?U)B*q@iXl{"
    b"u1_kz^V2%$W=J5(DdTHny}T=3c|^&zCurJXZrA)^!hNMwD@e68b$*32(jT)x?>x$X_zEPs?S8Y7Ax|*>8&Xjm5nIWc_Gne?qxLwA"
    b"ISjV#$zo#B?l>G&xnR3dw4s3RfRnXLT1SO>{hRT}s(stov?y0u!j7DXg)#sqyKl214NOV#B)9NE%c}P*-W|rj_wXT)g^%b7CVkHK"
    b"Ht3E<D@D`MLChMx_f-_j^6{!-^9xf{>_`d){+P({mxRW3@@R%)pfLo<3u)b#T_v>%&l`~S!|WaRL;mLKR3f$_G4*+X$x<#PkZ(I`"
    b"0iY(>|5CJw8odK`1SRL_t=hj_%;_{l2U_s#B>r${!MFDn2y6LnZe1b%K0kd>E7{)DS2Mt-g_mQ+E*e}_OcOFtdcVhoQ*!pFrT`aa"
    b"$SGV+S#xS(Yke0-p22~lKcJ>{_-UXG%1z{l8~i~luf;cJAJ$nG4Y8N_{?A$A_SW-&=*WLh>a2t~hv^9?m4=Q1$R5r@HhXAcZQq0J"
    b"Uorb?Ttw;ui<(_wAI6~yd0;L(!w^y_O0UoT-of{3B@&kC-yCF&8&dA#F~Jlmi!C*A-Lk|b%t%*@-CuP4=F=#?L6=$D?l$A?+e|K&"
    b"zaK$A0H1_(4^_AdzQ;FkViP%t=usCk#Ghp))DEX8dY0cDXEo&drd8LHQuV(m$e5R57!)|dX3^?Am?S7x0w)qc0Q7YQ2?!XF0kmY~"
    b"+h}TbJjMHBD6<L+*B<Du<0LX<#cXqR9q*9wJiQyqM$d?Xa~Gp<6`)pW>1hf$RO8Rb$nbe?Ot2!>Jz*3?P0_pws2D~OV)5=n45pYk"
    b"Rfw2a>QnovHjdq8aMN`vob?HefYGX-?hyf+|0BC%J>s83r5n-F*rcsgUg<X7_&r^fNorXMZ}%QaX&369)&M8_+&)iv6OIF`SGm7D"
    b"ErGmnIufU#4@nHItaN7L)q6uO+!F&K%7RmYkw<_-)lA?RNS%}^TChtxyqd|IMXG^dhlqU24#i!+)J2JRtV;KAugqEQaYP3@qJd+U"
    b"YO{jK`uq4L<zRf@!u|4xs$A8lrMNf{vV^D&9col%F}u~CvHjLA0_)MVjB9EK$LMQcgIYPWDH$3k6>);Sz4X}aqFJZU)|V0vtP@St"
    b"+1`4BDIkbrZb*}$9i-e8ezbJ*NOP0x<^8it>w2Z6OvgH3{pgVlX^VpK(XxTu2MT9S=U0N&{5dD{5}yAJ&Q6Cby9+L<k7^E<a0TLj"
    b"lb6Qm7GRh!2_n++u?=neCp5Kp=?kOKjVxqB8uVSSm_4&oGgOF`ShRH9%fJexE{Rol=X(A)QbFxx@D9Wgjn<?oIp1;OUZBc%sz-#g"
    b"Pm}B?xCu&<6OHaPX(Tk~aq<gE97HT}%ul!!hE9`rjMOxUC`I|oey$rckDt^$c!nyCCEN8$Vqj3$#2|42*mjs6VBI{fzbLakrE6$+"
    b"p;v{+oG4Pkp>k2ZmXnfIx`TWPlr(}#i9rkKNWgYYFlE9nQ4!+qzdTig3jmy|w%b^d92MPbE7FVgr(Z~1sl|Sqm`R4fyc*eB>AnnR"
    b"gegAfz|AgWq|}#>n@X!7G}E%AnTX*l!&lL#v#=BIoN{csVcBd8y7|x$i}SN(P*~S_=&Gv|h*DpLJr|KogxNor0B7FJj7;>~r~@1z"
    b"$Ay8m-U5-jx$1zf0;0<^ol#$&!fw1yMWv^N=P&CLz%)YscH|XJn8wh^*oy@0s5sS~>Qy}<oBFuv4$__TL60lR<FAOINRS}>!_;~N"
    b"o$yqoe_d#Fnjoj5VDdQowGX{o(KH>A4O(kIM$F*$Fxee@;p1beda~J7l7!6(OE{@mSdk)UZkL@?9$q|0#4tXhx`m&mSCNoOXibdP"
    b"H<u0^q_@?vgYM_w3!lUUhqnu=$E*Qtmu%De6*)oqz^Q7I2{H@0ak=7=GFp-$FJm`UJD^`S2SE^TiGH;Nnq$7fQ^8-Fb2?R0`FUA<"
    b"Pvv}bwE3Wz>qi{d8-B%S1kXY)Kmcy11PhS+xzPn_*o~ol-?{(Az=eeHG5d2vL~vM)ZXq~oMM==kLa{_Rzs+fgcXrB9?pqLICo@hK"
    b"p(Q03PYkUGybWwz^d<@XE}4pYTNsBZERB?~yI7aiuNKQh!E`)**P=AO1RVlM0vb^Up<{r61%b1m+#Ui~+(PpYpBN(rLO^*2-&vAS"
    b"l9ZD=Y-*EsRT68%-EDB3Qv*t;QC870oIkfW{XsZ5c?$1-fwEYV)gGuRkRD%Q`xwco>_0*1p@rO!dk|Rr6UwVP6lvJ@Q2SK&MbCZM"
    b"mE=#uQKo1LrFsk+y!AiqLpe68j`|vHopIS&K)1bp(c(O+c`acAPGghW49QDs#YJ)dD=7(1oFTYi5M*FqnRGt)2p(i+`aWFTW*-Om"
    b"L_@3}U&!j1SHsQ3$>jf53Fj@I%&Xnjtl#9LQ|+`3t=1FZrNI4_81rCU!Yo0U92N^(FSV=mJdE*e_s1uyvo0=&1_DVbQW_rZll#|5"
    b"KDt}IEkAHBBmrR1ug+>b=m0m{+-Oql0rFL9sZNe8No)!+dj|tH%TPE_pE<Z;1no@F#?rD;XG{Zae>FZGEd4mISaxBah|nGy0gSBm"
    b"4VhS`H+2JdiYUeQhFD?49!U-AW)LQK%W2?D1`eNN|2Bd&$(^=iUId1y%F%t~4;7=kw;;lBEvnCoB#B2*+BdYW)iBX%zjeb@ZbIH|"
    b"8$<wjK(ME1yS!Vd<I{1GhHOIO(s~!JZ0@HpY}I{_M`XRhRDg(}6*z+I3aEm4%)bm6&s?3RRRsQb{e=#P8mqXFmLC<&-BgH*pEtBq"
    b"=S-!j1u_L}N50qA>nHIYOMUf@AO1g{(U+S1NRI580ZQz#B<LEWU1>`8N~nLj#uLDbn}-Bo;7$EINVw%JwC$DbtxI`pRqi*OmQ~iM"
    b"h(wlwtKJmr=a8&gc(kb&aCdBA6&XF0KzAu%YI<WRUdq!gz;1u-{cWWsEz*;_vWTR=P$i4t_-M6X?|q>~$$u?787T)d>z|Wn=jEr;"
    b"XwXxUOztQM?-{4X!tH=G7l!gj99vb-5y>_m8x<GvaA-M13enu0f(r-=r3@`x37fBO*cOrl<-V$2f47k5E;8L=7hN!DbyN2ilqK86"
    b"&pdArt^zMshe1i^MF_n%_81u;c|I9e<=2Ih_=BPAm09MPXwCyXX-k&oJ>ZuHPciH%Qjwn(+BhD^2<mg3E=d%46qm1mEl$D0ewp6c"
    b"TCMI&4$*RI7enupAU0i-gNMVw8^S(yB62j+;MeTz+7tj7TAQutbpEksS<nov%KxZ>Km8zn2z>;78Mf7!{vY{J-(9P673<Q>=5eaQ"
    b")n#>nmOc1}F840^qQVx9;zxU6Q?f6K<}^M2<EvG8uQE<S8(_c=6SEsuj4)sWk1^pvawR5%Ep6STrrkbRicIpgS6z91-(kZ_u9BIo"
    b"*S<!e#DK##v)(A+s0LeP`{SoqN6DCRFh0BrTS>?s%E=(}^|7eyw*bbGHl8Fd8UV)tU&+(rrG%dLA0wp7_Jt6nkhm4mXI6j{FWVrY"
    b"XnUv*Zv)y$hc4h2xV_E~hcV8it^pQE@vH`iY**DKp)R>I1F(8bu&@~wq1BrsR|3ZYA<d|#Munnp=nb1e{XPhw1?8&fUPhhYZv{H?"
    b"R1Ha2+&mqcEM@g^=pb>x*??L_@geCu?|D0JxX#+a!x1f%R=gZHYKU0;(|?K_^R8FiOP%hcMKuxMdTUEM>+_Axh@UG1MeZ@DNag$Z"
    b"bBBC3pt>P|7rLGM`zy{Au1z??xq{MBYb{4!=l-VFdqUQXjq++d*7t!%xso|itA2jq44z3Ih7kkAQVC26@$K;sZK-P*hG()D2weEz"
    b"Bu2ce9Cd&uC+l~bV90R6>)<)L7I%z)W^J6hj%SC-2->Rgu3jolyg7@IR>0uIstb;n>ze{>Cn=OY{LbUC*rr<vJ$8-k&>@Wnxm04S"
    b"fMHVzy1)*XP)KJdw5wG=T)>Ed>8)GdvkLFq6HrB9r@=7-6tqAfbMJm5D)wU8i`Jf!vFg!>@xng3S8ZWBzkZJ09vmv@hI+JtI{Q)N"
    b"1<Qa&-Z7orz=q*qZ@owHpsE>rnQq>`2caHbp`{V0>iT~5nQ8uExQv?q0rD;S1uH5G;;;9)1i|dbqyauNS+;XLMg5>Yuqc0v7GP^="
    b"-KU6ikqXiItum3u{N<5*wPh{%0t(ryHBZr#T3%SRi67Ma`0ca2|8uXcGkkDU7i>aD^$|;@k>VFcnp9TEN<<X_03f7IK~Z^$6CTI;"
    b"PS=<cK1$*m+`uK_x<PvY^KpG%S%LQC%p|X*HHAM3Pnu0mvx1R@#$DenLZ!_N6Q6_*dLM4w;g(NwL$s5o2oJdCDWmqxj#WVb!rLgb"
    b"kt&$OimxPrOXXas)Is3C_Ocb}Ir(oGL$kcj&6OO`x>++afB$t7AhXFoL=3EH??=v8I+D+P1792xsDCZDxq0e4AOD&<^r`$+VR^3u"
    b"<i~9b7qu5b8Ivuu%Mh7kn7xIeJT2wZx%mBNdvOb#CbC_$Wc*}U3wFJ0)w6qBw2Bd*h%ISTA7q!*(ddGaiA&A3%%hp&9XbFZ7lBR-"
    b"soV^>@zN&hXen>y3L|9=g$S0nxsi$Huuo@fJuL^F{$YMQUvFcLYgaCq_{%y*dr{+TY64*WQUsn2Wc0^8M1ufTQ_ZaQ4mp_$komsM"
    b"Wt@$;zW<YXajGg*G8V{ICE&9(RYJ{)q_S4%SE6(?Vq*KEd{)#BpFVR#aq6koS;gk9vqwb?)}mS&RN$l&$Zs<@PP-D&g(e7uHZxV|"
    b"$6BhoCRysmL=uzzqJ$~PCzwFN68BY$r4b(z0+T9eEH5yc``-vGr5iH}AS9GFExwG^`8{2la5Q_hqFiSHYaT@Lspqq+W2YsO-ztH?"
    b"vn!k)+4?8+^*Yk^ioU)AkZ3sRf4VGrZpC({BFc_%D+RlzE2Q=If0ws~!iBfKJd%`z{?87DyxM|L!a~tK$Bm|NZ7)tldc((u%AI4x"
    b"(zMlpjr*xd+d2p!;I#3TH25G>-3N_1K?M2vUJhmE^vKrEglrm<xWXvO^9BG{YtT-1l^w^1*kq`E5neM%O0?n1c&Z@^QN?{6o1{X@"
    b"glLr)LZy}M0xosy#YsKON{az1sQAtlblGtcZfq0#Gor^o@LJ6<U7gf-O|95lMZkcdc=U*+J&zy{n{BPDxg38c{AHeO8<h6dT!lEp"
    b"Q+2jRt0ftv7IF2dz61+&qTg%lH$@P`YnWaOU!G0hxVmU-x8G1AG*yz>g<cQZbNEr(j`e__#-f{rUqIN=YCgEo3?C8xVi8zp3%s9E"
    b"W=kwDt^&n{R)=d)*RUL1KxmBF=!0UZcf*1f7+?3IWf?-opUw2bfQ;hu`UH-?mmN~&aM>_CTXL#!L#H)O<C|FyAVqoHcgxl*8-}ZR"
    b"G_h_Ak#6V^hi#w9`;m~!`xQJI)W?9ds0-uG6+<&aE4pk`(p2}6C+pf_@J3T^*0|1&YbHB|K;@0?$LoF`n|Jd!V58I8LyO!<l`CLi"
    b"3U3kXS)5^N(z#*Nr!ACmAG7b&z4|tz<^~uUj;lg8WoEGheWxLV{RwR#$WK+Iyt&y#29mAa((%~hb+ny>tUt~8h?xbIhkMR3E1Ssn"
    b"+w685uFEU$5OnNvwkBwcH?#(Dkw)3Y1km6S)dK|6<`{8Ju-KJLg)lEal5Gz9-*%ptF2g8G9l-+7v?00k%SmT6l`R4*IbL^5t*n;~"
    b"YXaWnf@Dye==&g*z;8buz5TcL{f;4H4=mF4J9*cqP+naOeIpl%;qn=xMNQLV|KcRiWBHbMQ=(~p320>ch`J^2PoQ(>d~70qJR3)G"
    b"1~5KY^gK{glH!OQO6{Dn=KAeWzJ{+Xp`h<aXyF_Tp+|h$whoA3d1N-8ZPonmhqNpbu5IQw@#NHT8&wWyCgyhR-CA}3z&&ozOI(bw"
    b"b6XO?PndwIIH)BGs)<hGN`6g!*ezZs5FX$>K#fvJ%aP)TQS5#lc@{YrZ0*)x*0x1Q2Q~Gb!UqPdzEX@c(t7e@CBkCA^Qr<R%MAdU"
    b"uy^A&B6;k0YMgrdu0?Ridy;JB4rBAp|Ba>ErCb6Avg6q$7hGV6rpGd>)-A$A9kUH}`HsXu2~5d<OB$l&>`QG56J3d|#?Boz9|L_Z"
    b"^kX)Xzfg#$SC^RqRACqU^*X0<p))fUDu|Vs$uf{9pSZzf6UOk^zCU2*YLd{|&LUuMRzm6wUj3^5eA%vbj5m4uhhe!Vl&^oruhfM@"
    b"av}ZMEXHcUM>k#w3H~)+<}t~Dq>H2>$`K?z%aLDqNn!I`MhY}#(ptQ+2em;9HSSyoPZF35Pjh2_dn<J5LJ{^$3p}t@+jU)3r!z#+"
    b"_ildZk>RYU<PG~wt*MKxG@@h=AvjwuLrFd#)<uFp%vXOG!tM2f@K`fh6Swf!Umgb+N?Eo|0`zWYEy+=M-@zveS<xV8s@hw|3m<>-"
    b"m2{R`=n8t$uE}R%s5a$F!ga6tD|j98<fEw@clW$Uq}<Mb`guqpGy{UhCfLDuRS!h~n`pRq4Z)ju(bp%*XE1PIkIu`>BZ9?&j?br;"
    b"p>r7?e+I&p061Y8v;xrfuQ%~lcD50_0i|8wQ!G%~-DU%nkXe{%8MUk|>EbG3HvD8p9$=$ybwSI0IjedH<5QbzE;15#yJ+lUC5|iY"
    b"g{P%g!GIIwY=F5!myl%^la;&uI9**cwT=)o(V9eiGF$3uWqU|EmD)SNxaK(sT#p&wwbGw>IYz~IVuzTLNTPaX2e<XU$Oy~WmI#dM"
    b"b7(%CWQ4XIZ??wQjw}N?cv%87pFI%2w>-D}OuTT3p#BX;K*hTYK7e?#a<a-uaT9@8FTh-I5>v-aOqdXe6WzpugD<JYz>nVUIl6>_"
    b"Dj%@LP8#t|H5_@Z4$qp<lkP4fqq-0N&K|JNiLKq~QY&x{oLQ>L4UZEz9|%EYxeYR_>D}_fQpZs7Wk{OV$RiEk^m%SEJ6;Qm=aoQ_"
    b"V`?aroU3Cz_r3(uj<qzNj#}K5NdG!U*cQ^F;xIL=MZRj^vT+FpCeNy?#}|!T$H`PAht<#^d6HnRN3?O?={)RM%HjIR2033Z7U+!j"
    b"MBwXj20Prr^Fn~^zrX0os$@8AKxcaB9wQUvr}bQECxKMfJfeuZvb6<L<#8$>gKD|4XTrO@TFeK3lacF4ZOgZic>v<uz6@ZBWq&I2"
    b"{G<u!dKiq&VhBf|XjRSR=(Q0GZU#}O4ajo3vHo8Nosk}&TtPUgdQCF>x_(B9Li%;v*9)u;xIOs|(DFLlQX?TNP5~{mO6MB*SB?WS"
    b"77qBKzk42zP;Cm!ZkBYDJg;4eo+C6U3}rb_87=r1U~v2Yp28*HL`u5yadis$0u6Y=Gs^0hcw4$7sN6(YoCmx0KE{@R@*JxM-|cp!"
    b"0P4$7B~u-Cj^)*k0G=_e6Z{+nncCmUNayIGZMXSQmI5bi)lYzivGeUoskp(0AOWggx$GbyV<}MHs%W1_kt1T)mPq36&AohC=VhAr"
    b"_aH~8F*CXJmI=i(sIcR%*5<V|fJi$|1s>goE2Al3r6hTi6?T!fUi)E9zP-S2xaP$cYd<b*<TjmfB}~nUZd^PVg)^lLyDT}<>sFK}"
    b"v8tcC4~L9t(H$+Z(q&wKSOJ7B`sk;aP(76z++6`p6H5jyAoey3WPH!`*$w@<fO{&{EI(cetC8@<fW|VUKU;KxA~Dbm;1U%UE^Hp@"
    b"TET0X8Ti}(Xo~s>0wu~I8JqXxUFb7riK|JJmvK0_n8Kbz|6#jE$7Y3^ZereK9!=b)^IW82QfGKtBNETPa9RZPuPweSFnZWVdix|r"
    b"%j@-3!;QbLTq2+)UBW+Id&`F8ZmOd{0c6;XYMdkezLa-XNZoIA+uP!I2a|%8=uWKgsFjATiviy}^9$~Hut{^zTV~q?wM)0hD!no+"
    b"dRHwjn0%}|k?8so%LsjEyW?Ss89L{W%4S6q4B9cqILPiu-hGa%j$G2-bk3eGkx$oE8h}5?Gq*gy-w2?`<#$03q*A(FaC4$e32MTW"
    b"lyth%uB&_C4-`WC1XXmgh&yFebT!t7R<QWnyf42|A`_FNDLjdy|ND8lv}1%ms6J<NlHDCbT4uy-vNyJ#7Agoj<Q?H8-v7u!Q%G*2"
    b"W>dw3^u1xzEsNOUG?NEx3?N4WT_;+5F+C(fIr4iD5x|!zEld<gp`Xu9jYG|9h7qVST(ufp*+7i1hq>y2tqNU$*O-2q3-+(kf0K?F"
    b")zZptPwy!qb@M&G;|4u6G)r0999rToFIHce|Bp|S9&;``g>EK33&&TR*$tst-!Ap+ekS~u&oz^NDiP0t|0&3m>lV({$SL8?{Ah}p"
    b"1`30_dGZZU0uiQ5wA9S6!4ta7W@0ASUo`^~E*eDgNBn_`zQSYrih3)skHyM9^AD-;*)7iVJO<xa<rkWup%6atl7jvz4>-Id;#i&8"
    b"7}MmPk3J(Yuh1#NF;-#!Vc--ow{j7_ewaZcjPuP^km2>FgHukn)qlHT*_j1i3l<<9B0coD^!N2W0*Bu449<AvG+_i9zHZ_tlp5`m"
    b"07A|ZI{0bVKRn?Cy;<K9s{zO?ko&9y<l=UG<bJ{Uux-^6f;`Mz5<n_^fSPXJ)<U*)f91LHQ>-Iks_5>^c$w(vgdN+6f43S_cvlh^"
    b"CDoTO=_7F<1>Ov`QG7F=cQ|p`Z(NG!QpIdT`G?4~RC)zHoQ#L%#fAwgZWajz_K3NQbV)fyRHGO6)N3;ve?roZr4hSsnxs|alZ<)q"
    b"NwPY<m~W(znoM6yhWinWivaduz;INn!lTfvV?>{Zf{BN6)c(+rEa8JbMPH(y1%q2miA2QGa(&&msP4?#WXwx1zPLh2HWQC=yqTVi"
    b"*`qfTI8HLXI@Bb#G@;L|b!L%;6D8+eD_oTj`|9C2+083IC)T00CrUQhiQYS@GoO!umk~*wYWtVLXz9(iN}xO-570R8^x))_TrjDT"
    b"Bu$XTVe{c4;)T-|ecN&8v-i8Si!-H9I<Y~J<RBMkzGZ#G(tMeT42rpxJzZqP&-vWQW+b<@l0?M6kM)AQ2iqLgSW7$R=_`cT&K_ls"
    b"sgu5+bwtH<|Lx|+CA&}tAqWH7JA*oogFnE@ve-juZ#uG3zOPoOE`fWnmf-n2XtMmgoUrPkn9}%&ii6)4=NydJLHUq8+x5pxLh9RR"
    b"aDO7%z>3JSA_W>Q*Hpej!QX;QSln9B#>QVegS37i7B2OvVUAUj*ck$$`mJs3;_yBcDI{_^D%W^!lp{yP0UQcvIiC9*z51n>DPc+a"
    b"<~<|F2Oil{6enu1WklnDl^Y$Qj7pXTXL~Ot4P(MZ5d{K=8HwP?R9l70q5ATxpOUc1FO_phBEOH@kCHBkMqoh<(FFwfw1@uztmT`O"
    b"_;Sv-GL{8swNjud6F@c(Mx=y^db^6|rHimQ<{_(q2T-Nl?#SNQ+9yw9o8nf~<i1Bu%rrs6jL&@$+z$9TxZ@KDSahEPQE91Q@y^iB"
    b"W9mBTFf~aYLpor+KfcK}sUknAFKhqcRs-%6sh4b{Mp@u&ZYx=ufs$(yJ~+;NYX)433nv?V<Mc&hKEwF)A0c7Qgjs|$W|HSnobj%7"
    b"vkpHG4xKP>#!m4#*aLN+ZD*nQN0~pr@()}+w;|b1qvkER8D$=SoZg<i(sL@S)qw)aJrW?`(^m=NzioE(sh0xCfzfP*Qvdnfi+4AH"
    b"AvnKhk!o>$Wl%gbt%Hw=uqeu>6kkzA!J{w<vK3=CBh3PTyPEMS7x#lYp#;nZ27hXror!I$XF?qgQxk}Hk!bB>fanUOK!X%A0dao2"
    b"wfM+x*mpVfHv!Xx?skVftk(mXIyFkU`zZ<0C6S-Jb`fSQ*Axl30~V6x?JE+sKF{}9MDnz7+pPg1cCK1ZOM-5hbmz1X?q>;oga9*h"
    b"U>?^>GeVT<R=PHV@7<!rZ|&|bRfS+Ld^mq^!B~x271x&2=z+#f;xXI)_<*6Mhb6A@o*QP_x^8a=Gj%o^q2ittK26f`zS~n^7GhpN"
    b"0;1t>5_u(@Vr6DB03<gDMs1hUMI1E9YL;d8TW$KMUc?=|QJMagP>@d%`^2e$!$N=jm{b<gE(TXGPsHeVNMlb?%{ud63hG#!J&@iv"
    b"P^|_rQ69W4TlKY^ld<S=scGGxqHNFF0;fVP?AO5aKCK~-w{WdmF+6dAx#Zann+RxDVeIiiycd6TEsDZxPqLtDB%lpxx;LmADhv`*"
    b"CL#mXq`cL*91T{>O4%=Y`+UPnDA<<`v0E=){eA)7wXk=Z+WMx=Jh<0+tD)8OQ3kPO;!|R6-V2>GaLwlu!<-IX?ba^->#bAwnf!XP"
    b"EU8m@FPS==$Gzm}haoFaR}q>sopG#T=z?$tT*UwyKMx%7VvY;v?^DT=Q?zW|ysipr=AICvPqpE@LysYCBQjy6S-&)~_eVC7xgf$("
    b"F#MxV(Y0)!)<eD->>t5bY(RdceeS+INKo3&aaPOZGOxbbxTNvf#3drC++~s|1ZPlf+GcQs(x$L-VkRjz)wAc@BEpw_^fiZKO}pSd"
    b"u|M9to1u{d*m15xaLn8m=9P!BqO$u}lb0T}?uZlVtF7T3l_St(q~%@g{+b`0TCy)CEyg03)<4bNqwQ!vd6J^ch$y5n^nkj~W-_<V"
    b"3Arn8@U+Q{&gtXx;fxg;0!?YgOmi!b&WnV{cYPuV2?0N)hH6ddIJOG0w)*>Vfkr0=4hF3<Jvx{GS;F_-ArXE#D1m*rg)lvq=@mzR"
    b"<!0>GNgAV02)x4J*IW~S+#?Opr4<Xw-ZFJsQkh%2;%tz=wJL)a`<1=3!kO473P5Fl1z$F>6aa6|CS@XWc^KY|q$ZG4M)dAZJtk&1"
    b">}f_^t`DpsTW6_RO=~>xo2L_k1$+qL-q20*qzCWK8tvIy9dR>MDA`4e0|6505Mx*Frek*@)!U)Z45W?nxzn+u(1FQo;jeSEzoTch"
    b"c60yar(Gmk%&M91>}9~f^Qr{W@3o;;jjmm!CT5Fo26j&!``Pt!2kWhU{5M|+k5Q$A{aqd09_(O8H}6h1(AS<06>AW_yVq$@1jeM0"
    b"7Lk$Yv1UljnWbZ8-oT|Xc7iG2)(t-)G|x|5Y1WiF-fY1sDA<^WU^bGpTc_5jJk#F>jjqy88S++AlRed{$mf%`@dDKnsrLxmQ<7O#"
    b"`EH5&wQeW}7nCFP^~8jA?TzdE1yT+v%Yl%ZYi5Seyy52EmbUcb){pGYfDUq_h9w4GO%VynnO89*o#a%asO0L+C_VCRf#*-#nEHCW"
    b"GJHo}aes}#_6eVI3xO7hSf~&YFIu<1@sd`k_A#nWXW^kgkAVw0?6uhgIlGS{VHD|1W9&R?Ae9irL+CRiVlA@+UnWVe6BO18xbjk)"
    b"HPjE_w<lM~YtGCahRR>tOph2Zn^bb1Ty*i7p|}7>n+VlB!SW5)Xd){NVP+4GF?rJmOUV?$VV2j~ngRG{#yCbFmqSHNwvp(wgx)D("
    b">WBBk(F+g6U+f^|l>FM{f}y)dN$iA$UxDz>>&7u(ZPWiV*>OwJeELuKUN@RqZ7!7mchQhRL-}?^VEAlzYQ<ro0Pd_Gb0cCmE_=DZ"
    b"lE1}LU9(Myv=KX!_&S*{x@7Rd!ep_P_~uo%R~lD4Jm<lO#|(OUjBB)ZA`9@zB?lwI0-{R4m*&#{qNMLpOi~NrBF`&HWtGus3JrN("
    b"VHw-vqYa&#4#vad`r$Jw8iY?4>A0tOw3nm*0R1DR@`@8R{5s1^!PnsXkRZ)Ft7mfTpb#^lzo5w>o?h?k_oBK%w3EAMR%L!8Mt=MG"
    b";o=-nv2svYZf=Vp9<IuDuM!4`YZ0pVXmZ@J<3-FGjKoJ2^A8$VHfX87x;|+|RlZzoy5zUvIr4g*%KOS-CReIHt@xakx3aBNaV<r>"
    b"KC~{A@pH^ImaI2q6U4jpRwSp9$~#$5^VqWr<mfv6uXa!DrU&exj^r~Qph<ofgVaNbx}Urfx(OXur&uU>rKkglPi+O-?#{k`^Tgd8"
    b"UgJKZ+g;>cCdp5tq+J!Tus#NDmlDbMFLE55D9RQyHNd^_R5W0p9v>6+uBJ{cxRO*L6OCY<JhQ#(T~$1yG>#Ngr(ScT+CPAWNuR>O"
    b"V<jx<HUIGkQT3o$Vf+PxkV4t~bM|?#Zh192voY4)%_(AlWKZ_y3D3!p*RRu5Lgy$x>Vo_!)sH60Vj>HhiJu5vAp^sTHcv@+=Q&h@"
    b"vvzj+m}d+dRoydBa$iY8?~74<shqrn+}SshGG03J>MBKO2m_uHTdGPhZ$w*4MXBn@33IWN$Vz1{9k}L}j`u6`c*!0QF(6iJ%(4EU"
    b";U3EOwm1sczL4GHqgz)fFiWc*F1-I{sE|tM>5jb`^pOEvJ1x&i)1Q*syC~eWhQl^x;#R9;O7dNI@m#S!ItndeX;^X(+l-=%u<i|s"
    b"vv;lI5xUFGCvz>c+J;cT(72=ny;G<3q8O_pLxd@~J#SB345Sp@mo_XU(o?3@+y*-U9@Z9!FZ!N%gSpxTs%|JQT@+z8wpK@q29uAq"
    b"uEtlV3u9yEv_!0-&R(}}K^C)PfX{J3uKtq;+;z}bz*3A;!@6NSS!^QscyLFKZZ~e;Jslg>D=Y!N2t)V4tDq06SB>+#DQFnZp}Mz%"
    b"Q9&ftw8hDHGK-}%>XC3eR{npyv>=P0*(fMUI69?%?s!DWim<U`5v$Ag@=$8CJM(x*q#beMSj+A)V_QEKZ0)Lo4>IENVQTD>16h@~"
    b"Rz+zEcPD<gvsSG8NY8$X%)A*9AZbizl@I#oFS%(L9cEY@(%CyiWwTI#-c(!i>74-20%bDCRx7F<(5P#Riy)(BsabM=ER8)RiecNM"
    b"Vl7+kBAgYYjq4N%;^4*rwd@GIEvqI<FKtL}i})6IxEz1!+WAu?bcw(vqB>2D9|jVRR;Zk#_+iN-MQ=#&oLMsBPN(in-_`5ctX`C^"
    b"!m|Yw0ZUtvw;rSKc&er{aeeH@(%eYMdvq?z6MVuEMy&M+zq<gVC6a>heq`L=CyjQH0!5(Yijo~!1n8q33E_I4J3c0hI>B>j8q-XE"
    b"0HAP0t3o0WZ_>`2{p;pvW4LeM9ekjx*WgEQr>u!HZvL5fFgTn0f%|KG%%fi8L6x{T>^qeEH5pLtlbTdL&SIZrly~w-Ds5;C0b<Vl"
    b"{ov8Q7z<~kB4oeaB3V-8b;af%Px><TQPoHwPyP{MeHX4A9$T2{!_|*leN!W4tJJk2zKsUn^GnekILZ`~T!3Xd71I~q)&!ozoIK%&"
    b"wN;YtFS;gDb;y8tY&rBOay~rTTV>^$5g;NY5<ewr(qaPsZY-qjY(41@1hos!^oIWMQpa8V{AqN7obhDVaH3-AHO%g5An>M@vz9?y"
    b"dz?m2k5xf?NzzBw;%8p&U|^VV`xXlYA7!H)Z~eYuR>?KhIORydDzwFG4i%ll&Oev{J80zqllmh1mE+CmlbY#_3iCOJ??9ou^V!3)"
    b"B!ptMiqGL$Hk_Z?L{<+w<V57wpl3w&u=mi26ZgfCaz3gQ=L-hfMx#grwUuAp0S$)Qwmj{0&b0T)5ZHdIGL=7gO=g_)NOCe=A3#Qo"
    b"?S<rr7mc2cxCah5p7`sAO@#=J*flk#gf~6JtJKOHgm<6sIjiqrO6j{exOP2^1lG-^zUGb#v1VFx*Ru?Zx31!G+&h>m(*Fa54CdRj"
    b"2@R^vrvnbN{g%jF*#fCnq3UjCg_kN`5Iy_Oz9e{{D#mBZGHyaRzEQ<p3ov3P_mz?X0VnS+@)rA~yjg=ChE4pf6GpXPX3hwPakD=H"
    b"s&GU@KLFvbw3uSjjNRG->&>)u9dQ?~vTpt{G7#iR!WjH-j+Mz{0W`q5&mIU}&2e1pw^~C*W^!Vy@Cuc+_S%j*4QSn=?c;}3z0$g}"
    b"r`1D?ART#2G{}ItHI5fMVEaSS<p6_9Qxsup-n7Fk(*(sr-5X!-O0d3Rd2=3Zf%4S}#%F$Gv|XL#^5#5uC|d0$U(RTEM=~guI+;=y"
    b"h%(&%nTo<@s0Qh9ra=LqsQHNrQM%JmV5)v6N83@-JWvcqgd(s$)e|`R#k2V;lQmhSqS1Zyrqzz%$wG~0{cBu&2hu|@KZUYjs+o@y"
    b"T_cV9IO2;mINLuYkC)0G5^>xLDmtX3-#{IJUdK^lmJ+^0I?pzxY&X#SXDg7E5K?|3QT3Skz5UWFJoc;-<)KTpVqehw>rXx!rkNgA"
    b"kg;Brhft6oJ4l{+dl>lL5C!7v`X2L=uj$GD&tH6T7>s%;l4?$=GscNTh6Zx*xHEr&r95R7`qAB{_RAnns#LjP*3`rA{9d&*)XRgH"
    b"s3TQES8mp22x{Ou*Bqj9_@hi{^y~>l#s9jMbH>9;<}jc`j#6zjGNM{3A=Z`sS?k9%)ZHd!y0olXX9|4={R+w6cg&LUbwGD0)yO4p"
    b"M<5|(lidV3j36y|eGU9a$FJ-#dNE9VQsO6u82HdpoKIY1J@0V>ES_R2H!gt+8u5%53Ut&9XS5Qsm(yl}gC1<*vyT+3NS_}G@xa%*"
    b"Fy8vB5%Kbl@q^5GoV?UXDa*MkODx0#p_0BGe9|YKsCN`?)4oq{a=Rx`mavoO0Y#W4xB323J31JMi@vqy78PnQlmK45wndg22!+l_"
    b"OBK!PDzI*cWPfZ`_OJvj>#h3}3Z9_vXZEF4di<47IN}OZA!{5~!9`q$kpp{&F5X^}n0<R>1~6`5)mu&t*In@`lQl5A`K_Y2Q(smg"
    b"?$Ttl7{O&v&`QxvA6}U5k{ssh=}%b8MEz?pvWjJ>+8e{tz!=ROhqcJw=$!9c9M{CxQOyMy%J<}PZa%Q`_Pnb|<wM~P*kj`lVHi&4"
    b"3E{cU4ei*>bsx!`C0Q9g%D(@)Fpe#CR&$bS;XxBtAbSnTNbv1m!~mtV4DNq)AIY3BTNeH}a}X>#N5Do=szsWjsDE$PI-=m&-VMAY"
    b"E(dn48G5)3juN!%nG@ZGuxx#9G~IRw<_Yl68_6bZ7(G^mBE(?dHqbaFev-UWJ3e5bHjwl19Lc=TIrs262$<cs8t1(I&r!MP{eKHa"
    b"((b{S-f<aTsffp)Zpd#NB^}$MN~n~Fg&-*rhscAOgtx80IJ#H!KKG?C{=5?P>}$3~=MJZnwh>-jI6#X3hI#BZmRZgo&@yJe<vE17"
    b"%A4V9+jW~lPZ#p%^Ee^bWS-$Ir-;?#MVI09UtRq3iT;DzC#-V>D>g4^2Q>$3RfQzYV2UH{s@~={39Yit!aUG&`I#&b=?%+I445I3"
    b"GadRacC+R9vEQtKoWQTv2x5!$`l!w5*;I^G)-<QESaXH<IEQR|krp*kQNE!=BbSzuLEjtN<SMK=L8Wa)-_>W%7fu-O*Td;F=-g!h"
    b"zytWVLFCJ9ax-njXanRgwv~dJ4Z-oY`-@I;;70HyCtpVaJ^5Gz$9Nz#;xVvnwOGPLx(?CC1hI|9+xv^LSB59=vUZ(iZzaCkeXgOo"
    b"eb!5&-Xwy$<jRSY+TEY>W9BO=ziIE`gvXcS*h93#kl-HiKvJg}rz;@zf9a|}X)ZgmH+w0q3gZa)SLevVq`|IoCHNcl;e=I{Qi=nz"
    b"fg@wN@dW4EA`gVsEVeB=kmAk0cV~FU_YMb|=(qT=IqSDM@dI}kvwu)RNEH=d1~?z#2sE84d$Ow7@N6D$&sryehZaKa;CQ`9Ejx(w"
    b"32bkYGrVtC<eTGfZ$HO-dP)FzVp;?UZy-k>+VUdMgv-<t2MtJ*kfM^dD_&~=6=t7=8g2@05*Th7B|}m@k_O+h$htA!Ehx{f`h+16"
    b"jOt4#p1#-=oIpUV2$O>O%Bex4!GU$0d`PK~aIs?{s(~5&!Z73jE9<1E*r@*5MfVxOe9rF5dg5+d3a^ae*ed-d(#}ZEv<x~qMjMTm"
    b"Fj`bgWMfh6IUmSVwewAT^}BU9=l+wptX-P`I;p?Nxe8#VoxDaoYdrhGC+;SBmm=Ijr0uMN5M6*E!X}uD-pm=Ol;_SWnS|{o$Rp7}"
    b"wd@@L4LW<8>)tZ2m?%XWsw)G0gAY{o)Vy&UYuwlw4HT;;&MNh|V{t8a7X!0v7PXx_`_K(@G7F04?9U=P3hO@pDLsG{nUCG;q>e0&"
    b"7FK%}<}WvU=a0boLQlD7hW9|TC1MXKIO=3CaOO~HLxN~GabSV_M5%sn3EHOkqr8K_IJl6faw=fQulwp~-+v25enNi1ssK=AuoN^@"
    b"A<Bt9=ZG3?E7B)pVQ)ciJv+dh$3Y9YLEVDZId+le(K<iK%zS$%zX9?eqid2ou*hF53l2hg(v2oI!o|f$)bkpespRSGx>|h%W2^o`"
    b"PO_C#iRwLGi)iP8@HjIlFpo92&g(`LVdDnHHF;!okcfz@s}oN3bOtfk4}xlgWvqlSHKCw#t%usYo@Zl^0r4ilw$L@o`@065EYr;+"
    b"m&%?Wgi}Jvw!)t<cHx4CDn5hMei59p%P!@WQI;$T>LS@;iWoI1Mc|;0B6|Qxj76h1Z!Z2EsSX!Rl@<<!2VFPm99e-gE>&|&F_nAy"
    b"1+_ZYuzd13R+oVks3C&_>p#VAXf*AkzCmv=imw1#+sHkx1asGZIa>yF{pSu{_e$i1B}{Tof`nd%+&KrBmaRB|cSdRIT&r2`Wb&4<"
    b"*VHq6rfstZhnCCng8vDuC1)<G$m{oqc*^KA=%f{$>C3pKX}nv>UPO@R;vm1C3$sV@f9RgGm{7u4JLG2Fdm4HH-U5j1d^i;rn~n>("
    b"H2?uj{vo;*VDw}Pk`GzpVy1tP_`>TP;n`g_Haa9n!WQv!8)$~PD(F|_0hnq2>jC(^dGi=b#HnJ<#mDjCKd$VfGz>1o`GrXUG3#>T"
    b"N<_QRO!zyVbo%B|?LwUASSz4KJQJ&*l=~9|VPV!=C29v4`4hHHwJM7$+2|$G`n^<-Pq&yV_bzn!w*UXL;8VxG3c9#EC0aPjMCd;6"
    b"ER>Y9pW&CsW>}b*RIH@p@J+~CgqmSl#;-M#V*#TY;pJ<NzruNw6Rgf`R)tT44~XPP;wJU96_C{g%UL1aZ_iG0g=DtT1*VY$<$p(J"
    b"%%08BIKAyKba|a()x@^VqJ`v<)7xafk=zIGv>8$j&92eYs(o22p5hT&!`L{BtL2V#?IN7Tct9_JoLk0~GK$+^m8xs<HABy&TKZJ{"
    b"C`E6tnWX)k8h0^8f4w_6%Gu1OD#eKlE>sd~YePCNsA;lq{)17gv%c`F0WD@qMPV2X$KQZto1QHenvI*Z)CWs+3nuWk%j9oPdd}11"
    b"HysQZnGV}c#i~tgU{I!Y0v(pI{l-BQsvQYBH;xX!3@~&xve_3r!jg8j7w2d&qfloW-<zE<<pXgt(Tjd+HX}J?7jk>MnD}&qpZg-p"
    b"zBgJm>=;C^r|Od4EEBN|QM2XTh3Tvt9NnIGEK1}Q15=wqC=2*jlRBvoKJu;Jt$0cf$S1D5Peu>nTKSjl1tD5&glZvdJCvw*Bzi<T"
    b"v*c-5eSKWJEyNWvAx#D~#P>qrBZ*yI=nUBXFPdjhDLjqmlNrt?<G{@rfE#^(u3ijxMLQMRw+bPJ9SD<xI-F54cZI%nfz>?GucA<<"
    b"`y$^LX%hv$!+Ry&UkdUzeqPxj3Si@59ou#1)rlz=-_z#VB3Xn8*nkcqE8R$4$!P$LS`!~*V_fuw<ja6!ygBNFWF>-!>Iw^q(i!%3"
    b"8-DoH%porj+SA%`LlE)G&-j{cb;+|G`0QAGXXk>g^qb`?Y^3|eUk7~ZxR5^wRPZtg&oWwWs2dX6ZpshmmnORVP8gTWYVG|!VDnKd"
    b"7t&C}9{*vTQux*PW##&^y!WR?0TC(#_O#UM)qe>YEE?REx>-0H<Ack_0KE#Vqp)Toz09E8Fot18vGaTQ!f{a;ru4|9&0zxwV3ER!"
    b"9|4iD)sr!+ByvWXDatd}(zfz8Jusl9x*a1~QtWFh3jpaW=$6d@yy?AZyZXHsoudKHi2HIg;BKonP^8r&fkkz2?BqOUFT7dM5F=7F"
    b"){A@wPx;`3crUB(WQU^uw!jzAdqngSmpsOeCTU);YZ47)wkuZ5=?%yWO!lKjVUUVFn3=N9G^#ALm5P@1IqHOfOo1lnK5qbENz1Id"
    b"XV+Ji;x#vDRvC7>n(s<m83ZF%qT~g?22q=p-~CurezY#Do|?5sA*a&PAPb(8XnI0K04KO1rZ*9F-t0+p)`FzX)Wg5BHi!@EtWq*r"
    b"!Sj5Cd=s=C<!g+d=aQ8=L!{K&=NvcdOtLO)j}HQL{Qih$hQg7iQGay$Fg5f368%p%gC&jlpmFG1lAr~fnAd;_Pi2brNQO(fYT)hi"
    b"L`u<lmq~Zls|#JnVZw~?^QM3FpjUabF#;HT71EG*qO%R@&vcG`LtIpCPPcVXRG|6{_7hSkKf{F*If{lBO(dKxU{5b;2gBusgpydF"
    b"0PAx42q=S+5ri~1P_-F5W5Q8BUgwfL5JKOGW(1Y>);`AzR?k?wVWmy}mW1p(zq^UVGI~e{&`e<_3YCLPhDgl-4xE>EfX=66o(utb"
    b"b>z)sFTTG?ciNH;w7oVPBn?Xh=`To^#&AAkgwV50ir)m_E7xSvOwwNvXN9LeKtmUlKWLP>)F)M6)Q0I^G`RyP*%4><%-qb+jN{oL"
    b"K7^W~#RUG|0IowxTE<lOeU2+z&8?b_UqbyDIjv4<pVC9Sp*OIv+fjyXPx3&$N9L<&H!QTxUQBJe0rbvf9r*3TAU`kkCmBYb+i=~L"
    b"E`a0n>ht7+*67wh<Emw6Y{+`S8l;n4{`d8;a*|u>sG4|r;`?Y%SjfCeRv@%tjbJ1rFd>Cki@~X*su-N+Rpha#;URMs6Rw1k4N_6V"
    b"ZugM9(?4&ZX=%i8mr!MaLA9m4g{h{T=A$ekc>|7-T)@Hk*o_}ovy1-~Rwbiii8z3BPi+1JXH>g{?s-v-f5>?kkKdv^gKAbS0|zDu"
    b"7fxr3;<}bOsSXkqAKH7KQ_BTH^4f^LSND1$;l+?Nb}9vV2UP#?v{N}OW>Y_PDBHYON#>!0c!>)eW>}cx91eQ_dIRrQH{Zlv*bAyS"
    b"Nk%UC3o<_JOvJFZA!@!d<imnE<?w6Sch6wudgT;ib72_iAiu|kny~{wy}+4yL+pH%P200}Ko#<d;^Qkm8@u|+n&Ecw+<2!-GB-Mj"
    b"92(1!klqxmD!WMP+KtDV;7BftqHA{d!I~r5i?|Y=vks0w*4=FbZm%PKna@(x2S%h(G4HJ+$GsG$W)mD1+YIr~vE_>H#f71@^*&&@"
    b"V+6`o)ZP5@mc-o@e94$sdp62A7zZhxaBItSTR*}|F9<6;GP0j$*SMA&oY&lsVn7E_I_<<|F5W=SGRWU_*$hKDu^C>eQd8K^>-g4A"
    b"E~Hi5Z!|Q5R#(eg;5n@o;{1^?m)WF8;YYkRDuk)#{qWd}1vr+RnZbr#95rQ1TQlPOy>RLc2xE_RDJ{v5el55^tz26pMAVl+-A{|n"
    b"^$bAII38r|giZDROFr>Z7TIgQWmRH1Sb<<#kg)R!DVcgUZekDBYcktq<I-(n{T5#ylZ3L5CFo8a3+J1X4^MGN0YnkLrGsSyy`N|%"
    b"8Dd{Wnihiq_aUg&_R0Y=GS&Y?uZY%)(_#|@p6qxFO(L8D1`WP(_NLu5RhwySA}1vy`vm4h(Y{xCqnZ@O#bYYI2-6*<0?TwBiY1u|"
    b"9-U>vu=-wuuj$$D<B>L0ZmgBxV+w`NNfHS1jlEE0;#BHBnBgRyI`&%S$_m}jd1Y|#5PjBVo`61x51vEk3L4YN5<^VF&D}(nTzjZ?"
    b"qXueXi6EQqgLRZS&aSu8WqL;psWNpP&5EtrOG8EZ@94my(ZmyfWa!KlUJ0R^<K$)<h6eUbacjslS(hEw7RbZZdvR2_f)Q+dtZ6#7"
    b"QvTwawCjm)B8*-22*%t!nns?H958UX8p^eljVp#_-;O1*6DC$F8T84`ns6*#axRIdsa<AtJqC}`m#|ws$&u_t1;2z@GJyd5+k!qn"
    b"t;ITbKvEbe1+HsM%szz|1;+P2Yuh5-h~V_jxXcc6L4{5*@qEInriBOrhC)uwb&a>Pk?KN0AU9$yqU6GQJK{!}DSIas*(EDxAGJW|"
    b";=lJAr_esX0aCGu_&l=BMA<K%23o^~uJsYFX3pl!p=?U%Q~7E!Gqug0)Noy~tV;ioZqHG{;$0J9g`q1(fC>ajNytbz;ObwWv0nH{"
    b"a!L1Bekpzo-mFIHReoRy)D~}!1ATf-DbYk*c^kG8;3nCc730}Y0}B8I13MDmpX2WI0Hh1B#5=uFOgN<RymS>r2-N$TlAt*cJpvBt"
    b"P(+_D-@}64hFe~TC&(>3am>S{55huxemNEav)4}=rsx{<BrDkco-6_n*976#2!rUXnvj9*q&|qxE(3fhzw&Rj{4;6;LU;DWoexJI"
    b"R*N$g;~|NJy)TaWkXmbh1N0R*5AoT{<|qA>I1t}UC=k#PX;3+5G86y3sPU0lCS8)J2tmwY7EIpVZTFoGFSx;jdg8GUV{b$foI=OP"
    b"?w|tQrgePyc!u`pj%1Y#-C0HE`;i#6mu$Br;I{+iQJ4r1-M=mB{%b(rsNs)7FP)2cDd`_9f-DqPLsxU2l+)sZS|{o@8oo`#@>hsb"
    b"$0~U>5yvFdhiPOH)dBbd);lN--12f={pB9tZ^Zc9%dtF=3AKI;mAC4TK)yGj!4%o59wkI3K|Cf%W*ND8wvsvVib9i)%Su`rC5{Nq"
    b"^^6s>MbzuBtMfm2JItj|ZkxY?ebNi&9Xv>|d6g#AP^``v)ZVrC1^<+R!5f=&=T;lxC{o#+Ri;8ku0JqBYFO~0?H`VMnYFxt!@{l="
    b"m+TB{<!Kc&fj*#6{#D1}w_IvIE`$T&Eos^n$4`>5dW16+=MEEgG0pN<bMh?OF><Io%XyC9BVT5gDI+O#4vVVG988fwuoViHS|N4O"
    b"ixO(Y7afeCK}?oM7svBD>0l)oAN4xsi)l%ZqGPX_gbu)b$>t@db>TNTH>!hs@TNPbSD?jlE43ZwA8S!=JcogZv~`T_8K^UhR_LH~"
    b"Btp3c_}Y}63E0y_b;Fm1wl37uQ83de5XhApHBj7A#{jrm4-r)QwoSM%3sv57my}k{t{;|o)f`aZLq=xKe?$Lc5}5iGA^0a9$0FdX"
    b"a>V6hGQ73dOyw-xZ@vG|F{{O8zmvEhtTRr^BH#ZLDSX&6w5(0I>x~#Iz0GA?JBfeY=9OQni6aTP8(B+EWOLL@7;%sj`BMF<_}M?v"
    b"o>MJ|<xzji*A9G)lGI?~S*H1%hoRDNJ7EcB#y6j&)y<~=5xqz&uG;OP7dSNGbM0;EZP;k?MZ2vU8FSHkB-JtXu@_y$xkm$#yOyE>"
    b"D0ZYpIKQy5($x<;NZvHBq@!x&Vhq>wxvDOTHNh(p4S89n!KMDSR~R`}lmP-*Y=^N<=tVj{72yzScEY4LGb|Wf!qk<xsaH%OUM}u("
    b"^~sqDT@_=8)7UII-l`g!9Z6?+1OR@etFg#`Qby5ou?vHag?5_rB(T?Ue1E3{z#rkd!?DY0PbPvP61YZmadWPE3C}XEKfl$DuEPM&"
    b"!(igBnNKjbQC|xnM8Ha)a<mBJ66@gz@kD<F>eS@-9aVNDsYXR#O*#-Gs^8oUghtv{lnryJYe;KfNOsd#;H!-6()5yDGi^z>W*Zi!"
    b"UAA6Ij#XaELqGs;V~8L@qPBYSflkn#^a}WW9P8MvG6cOoXNicU#a^_34ZM?UDV};mU8Jc{Vd0F+mvkpRGwH59f8#Xc28wu@<{qeS"
    b"6&$5~EHRrep@Z0s?~)}R%*?Z6okzO1VS?IrRDTECsAL#&%8gV|;_D*Yp7j=@**T9#Gcsjh10cz3aZG>@YG<vQxC}?P==pLWe7c`N"
    b"pSE?}MEs++XdZw>w8-&=VB8iRgJxg^Zqh@O*=fchl9qGSB9AN{=xDu(P;nR(8cBw74H`q$3meUuHbizw78aMq9u5NYh;U@#oL^fS"
    b"t*Cl@8BfVYg3Bx#F=xEswuom^6CH0_uJ3|D9JvRk`x1$RL-;l)R5%`oH_Ck^QzIHKw)$_gT?ia^^bR$oKkfNC*t-u_5=td8v7A>^"
    b"B7NN7e2^RNpQvs&$e)=7Gr>$R!R*2FImS}XH3)xpUQ~Nv`Lt#4#tksK^(<xzHO7#WC9vT6U>!v}?^;yjmgA5m$FuGKoQYBtWG;Ba"
    b"bqZYM*!;=K&wC$byVWYcVW=HhR#{`587}>=CyI?B4D-v8a0%R0pK{!>&^U^rLr{mSl2w$VCW3Ah80Y;z5^T8-&sB$`hup@^(tsCs"
    b"sU0m`jslS}#qcc?ftUoorN&7Gi1mn+K&74enIm-d4fTBlAzHY6wjQSxTzbl^^W7gM+`!zQ1J`TYVe;B+m4YhZEdoJG$V?r?B^_Bt"
    b"1(wctdy+!fYh?YLWDLh>D&d4r{r5ZPJVO&A>I$7>+yMIaJw=XX9BB6$|8iK=haWox?y&y%uvq?tk@;bScz6qU9bx!4x0It58<18M"
    b"j9NLnN(km4jM2J1VLaBlvedOV#pLx3MJlXt3iy8ZlOa7xdVnGLWJ$dXzRSPphqUU^9xQ%|3W`^FS*)!6mg2*RIuL?Y2oWq!Z)|sy"
    b"P-jT%8~=NMB)TB}6umjyC*Fx*K!0&J=eX4XXp(4&;8G>PF$`e+p4IXdx$&IHi{y$^7aMs%FPN*RIlD?VOOaBnfpQ_{-%K?^wv;*x"
    b"kV*WeGJy_t10NU%S@D~g7@1IP%WI)EPer9K!3iih_?WAw47kb9=vW5U6m&kKvxo<dN}gf%8Z%z?>!_}&%|y#iqj1g-5_Th5FsjKC"
    b"mxTu@`@-P_ZBSbWXx2K_!&{x3DAl5FWyS;%sb@)0Qp*%jati%GpCBeuP7HHoqIDoITM`7^ma77-=*V`WdN(?DWq%9W*^eLpdrG1-"
    b"JUk=P5eIn<tT3tjC8O%jm~a17zHc0p?n{KKRm)ov_(6|iq4a`h(U4e?yAA4qcb9B2kd8K1A~QTAeWQWu<sXn|5#)Q4+_LrPnY^Wp"
    b"g+|yU{vNy_AF+jDt+yB=z%+JxV{2}W>d?pnw}`*PcIs7dxVY{;>tGbR`15HRZG~U12zAYn3)+<)1eG9hc<$Bd5&zeCdBho_2I<W}"
    b"Ol^HaM$hRmBL46jO>9IZXlD@5n`r#K029)<`?4I4R?@xNKb&OlUz9k=+shZ;kc2LW?fWXYxxZT0>9_mWy0lC$=Zf@J;0TxW9icRB"
    b"*nOkvi@zi1Y;w&#w^F*Sc5zunP!Fz4;21r`I6j=KD<JH_5pm1`L+0AwqUb3!h2x@Zxf%s(F&lSh#FS#!HV~j&kbj{)kN{~sFK8h}"
    b"7Z-Ks8~l=4*jvJDqn3Mc)?Dm>NZk@c(;%yAxdPLXsOxXz<1|uP=)B-loZ26{X_%DeFOg-he;yg-up>#R!943I&X$D7n)fy2ORpZA"
    b"pjEE)5md!)?3f2POd}GX{>>XEnO#mbz%^ZmTE>=?pjD&Gk3R~k<BHLKr(#g<&FOn?WKL%mhccJ>_ugI^Tv@mSF|op)Smfr|)7c1p"
    b"0)}Ln+sJL)lr`A<jVJe$Cz|lQ^v->y@+E=Brh+qY<T$O%i1!@LNc+`LXtg1X+7eYZm8nxnI+TMZj<o>kV_5TDW5*e0@{sK7z>G!H"
    b"Ktf3twK5Zqu%_&wow7N=Jnipl9Mh6;Z5ijdk+JewWBwK1EhM516Xep<y+ajH7f#nz%zT7uHuL3JIuVboYIkArw34KJJ+X6<4cETF"
    b"C*4rF%_<GsCFrwhF;_0LHDhv0UHB`O2(}`<hbe|tQDCpTu6k`}4@FV#opYDrfOn9SR#tapTmxi9?H<8csX!e$$+`~szz=&ELO|!+"
    b"Ir`-?X~1UQlLqgvLjCF*&`bE9qKdUk=7ly{v>BHgOs>+$_7GPLK+eAlk_>8$ym_jnfra}>u;UD8qBk#HGpn|{h+e-UXgobyhuKzA"
    b")bac?@C1SE!0uJVmClkoF8hX83{XQli>@}0WiKN~=k+S`A4264;nU6U`(GFgx;f|onF4~V;jA!_5kCw^$`VB-UC`kWa3fy@s(JWg"
    b"iX39>fWclBljSS><aQpO;&7P5h`gLZ^8``jZfl7ATUWUKybIfCxVDZh_oqOK2RJy)POj^o7GZv<9w=6CnuOVkz}#JEox%lDPo*PC"
    b"y@3>S@z|?U#|&o{P}rZ(2K7a?v(3T5zd7;>dzFtEPXBO-2!^7x+HbnR0gd*&?yEG+`w@j#=_)iFKLBE(0xe!=%*|ed%By0|64ng|"
    b"XWUucCDMW1NMw|Am<?$5pZfa3xL!vnW%!x>XAkn5bY{H5l^n$N?o+m<)N#moT_(}V19u~l*8+o@_XN09+XNcSNO^l}$P~^diXv8`"
    b"<$%5D4snjfgzox{TpvC|fXX}x{mOHYpRyys;{wox0EDk?#q=#&mWA>;0P2diH<QipJ4pgyV?K&CMeE`d{PC*?()PlVXEwPt<yVSu"
    b"LaDp6TF+Bois$1SN#qNyK~XV%b%XI#HFL~4C4u{&24z^{YV&IorB>EpGOqMK{v}z2njFU*JU5N6hGRa@_CTBv*-Mcxw(iNI)M~_@"
    b"d+wBFANs;8Ed16KF+vvbuFfw*K9(9VtrGu8YaYo~p_ApwZFo>ZR6Y@pC8|EElV`IEcjF=4{Zf@nlXo>?8c_d1R@-4rrt59#ZpM6y"
    b"!hYqyta6LWizLk-Dr~qo(m*qC;Gh#e^D{&8D=M0oN6Cth#kYNeHAZe~NYfuH6I@^hHMP@D>|NM;<%B#Of~d@(Qf{him+n)YaJQ$s"
    b"2u+$8?X9no6#@<9GJjsa5+T5XYU4vS16j5{QC_rc%jUv|6_gy8gVXv@YThs4XXYX7hwNr*6ghi;R1%!QZL4RREkynTQ6RBc>#_O>"
    b";N=cLyB-`pi2960q=$I^7&8BC>gI#pou}k)*pb8^akVY$IIBIxS8)eZaD@{*7>O+qh6Ex!MI}-j%$YZidUctFzH%P0B=;{^#M<xc"
    b"qO^$TFIeUnfx}wV!@lj~IOP_yWS30#;OdUp^y|fuz<GSMTSlH#WF8ks@5A09RpzVA3(ECA%%bbO|3ZqB%jHRvwe99`tsg2RBd*jl"
    b"Rbu98&S%IvjD;qmL)c%M@Z%U{5{*~`CS-oN9e^U8B@GcV%5pG|8=@%Tt>iyVI#!S@8jtT%bkMQVdo%x_^~vjJ$a&A{PGhXT2|yl*"
    b"0vwrg<ZQ(c{sS=rgB;_hbUu2@<|k<UJ&KPB)Tx<DZS5SyWX5`k`Gu^h{bv^{TLHj#OGtCZYLXwy)sIYuM5Ta2;H@|xBu7KPRhdL&"
    b"l$)G1yKXOMQLF^#Es3QOKXdRDV6`)4DWgz_`*TTk_9R}MVUpjEn$%rv$;xa=az(WL5>vZ#60V}1aLQeOG~{)?vt@NnHgV}n{fDE_"
    b"+eINBqq5`_?Rcw6<v9qV=*o`M6Ie#9i`j7W=C8x&PK^V`6@+<*-kdz#h|K)l0y#O&vs4>H3&A!;3`&VvYB$)5govh$#FVA5-ab1$"
    b"59jykdXDN%>uC-l{7Py0Oed`-p>rPzNI|m<R>>WgBJrPqf8J^cYP?CNih5sneZe`GJ?B1~bEnN*dGMgdzP550q!uf}J3m0^PZc#%"
    b"Wy2^V_!_FdR`GMP@qj5|QGs&!-P4-8O{x>y+h$hzTQMdk5nMO?`=)2A()m4~-L!)K#_XlkUmDfWemf#mxJp>x(Gg1HAbiEwSU2~<"
    b"H3YJ>faQF5>XHPQzXY3%(Sf2~s?&t;T=m;v;op)`sId;tsD4xR<=V8}2Sm;tiPT!P+qrcXWm}f-d{wYW3)%{)MBI*9xt=!606Jk1"
    b"xl2`1K}ne&=Em4lKTG0YN`$4Hxsb!V0MRq;oJOBnMtp42JmxoaBBP#0N!+7fP09`v+nO?>5tj?Ag8NFOeH)B@q9l?pmRSx+BoeU>"
    b"$8<gAV**E|u+_`b^<WrRjr|_>;QB4m3@xNKLO$q1R1$vs2>?G=?-6G#vSEdr?2j9qyPhz#2g6X*zk_8_+aF|%?d?|~Ri2h;P};m5"
    b"d=0#TTRal=pf#a@CJM%b<20)St>6$hn+(2=3utu|4~XWPV7u%iI1Rh-q<dcBKxG`gfXy{TQyl5=Gxm_dDGQbL5@Mch_3H30<_ktL"
    b"^PJR|=)`@)>w~`ReFvs7es-ao|9a5S{<cDZVLUrDB{JNnB_p<;OQus|unx>HA2p}(@+<y*+!5btg@b_HAGz4zc7PSZiqO*6LtC;@"
    b"_g3}NGJjS^ASc#rh8A!TA`|#;gL;fw)KU}h*!sV7pe^+K`PrNa9l0#?eO-2Ft6-RbS2Iym<Mbx&c^DnPdDwW?$n|-Idl5#SMkyh-"
    b"safz?DH4n9WrT-W2ijDGIxagIh8l?idMi3vQijfQ`4tbD?Vd8Z&SoS*fnklUoSqOE&TT6AJJgklt<^1WJ)pTqigH0&pY){i58Xp>"
    b"K^592j_MVfwe+}F(--?%XU(QB=U*kU1)SnRDC7?Xct&+UGX`C`r48sdAOh90%vx*LZJYL9Ed@K)n@V&rA#D(o0e`dlXpvUKPt59@"
    b"y2knAUv2VmzF;99EZ;+^L)AvT15bg)N1>v;Qef=j|LF}Qy>d})$P~JfYfu@D0W=1Gne3l(F|U04Emy^nPs=v2Z}to0eK?$Lv22bD"
    b"AP^zcfJ|YZoy)hP>C$gA3JjyuFo&NdLQAw_$HZUXSy65G&7qb;!p(Y92d8=VN{Q2PO&t6IE*y$AUx2H<{`w;3i&x*5RZrWRniE7!"
    b"d?Z_cf*h2a@);hA*!&bkoY0(%sXfcT2b?Lqyza?#&fuANL8lj4k@PE?$IYbodoA<avJ6792!f~-3QCTz=)OY=mn^TA&DCltSw@$4"
    b"@tkb}7Y6s<>S<K~dHyBo+bw83gv0(3cnOGkQ-E-#Wp547gD$shwmj+nA~aX>j18bAZXHvSIps-liXeBN5Zkvr%ta}VK=!kt3ZKit"
    b"je;NfTSkGbWlk&VBPx%*(9JvK*k>EpA5&eA6BQEr?zr{-8`zEJYfSUQAT!<)U*U)i!~;2IttnLddh`^$HDE$A;NbKxPBrZRY>Ugy"
    b"@QG1`)|R|C-mzPz&oFcVH1tL*TxLXf2{9P_8;L0@-xH6RRU18mjbQ9%FV3Dmkg)+8>Bz&%3m?qp^)5PhRcQzT?=X&Qk>q@?%B@bH"
    b";QV(!dCquk^^i6$D-LrjQ<V9)6!y_8E5Nn)zWQeXeoi}fgOtj6xtvN}ZqKEe*fdazJI2YmdN!nQfm=w?)%^8Pz?pZT()7n{2}K_^"
    b"0xh!*2{fXoQcxNjzg8Kz#9?#n@{&qibo(#s(PA9eW07#tmE#BgV<ThhnP`wu%fa!e>D2a*xZr(LSEqB|L?clKrI2){)Az{&E%YDo"
    b"x;FEpJ0hw0ze(C+-xAZjwY0YlNZx>^;dSua12AYg{=u%hO=8pP#&LvvFYRr)VYe6g^{ts`7zcUjs8u@MXx3gNRl+nS1@X7Y^Csu-"
    b"D?|DtV(-|j1Mi^=r!&eLD<mzer04H%ccGMztx%lv^FgLQeAqly-t9;@?{WsKEiFGKFV~I2Io!miPO{BZul0)HaJ^UqUxX}RHI1lc"
    b"KT~!Tj)Xj^EpU6ZiJFc6*g-t&o&mx1np2iAyi)czQG9pz|8JkUjTqUPm2YvtciU;<#nr$W&cs^lJLPa<t6IvVmDsvoFR%0}R0hIz"
    b"y@q0(!V{@On!6qX@Ut-Q^VB5ZkoEpXjGiIZepX~yD6uMChJk4x-jxXo)=mxPZvz`028gT}Cz<n{|KA=HoF~`<vOVSaBKSSnn*yfz"
    b"HXwaRY^Y2UPZ<R7*cIaGP7PF=(JtI_%~!nCa5gluJjuGmL9b&hwO~?HM~o>H&Uhd9YmJr<hJKbT{8x2pNNkuKBYkKs9sk-h0oxu?"
    b"3$8HzF!Jb;Sy<rKw5(Q~gTDs$0!wvEv1dGA!3&>widUCCc>hv4=!K0i1u|h3aI3f|>CVSX=%tBT&{OYI?Y?@7y<I*xPK_r=+smYa"
    b"><=7(=V6rxaFb>Avt}G95@HChF17wb*cng!FTRXS(HM1g_0PSf8l)1IzPE%!hhfL?P1OpBb>JagFJk@4w)BXUKTFnIr3$Hm%G_<H"
    b"Wjzu1sLytV#!D!PC*VQg>Vdut>iE%1=lq^ipD;F=5`=(Mt^Teuz-NAu5eHp?_i}kVZ582S9PZ7k{JDXfogkfQ0DsS&1w!B@T(f#6"
    b"K<5P8Z8(i*RrOgI;o3_Gb%Ud3s3D`}5pdF$1s-U4I|@&Ek4ZzPXO@Zxs7eCN(s`D#|J+e2t*b|+-SoCn5oU<FwtlOu8+nALku4(W"
    b"t%v6uyV2-+;aUUT<G>UopkV-meBz4&kLOacDtu$nnmg05XV&>6ieS*n{`!oCePIm)Ri?}ru4`v$axBH9zN~b2?ZPn=kg)aqixNl_"
    b"2BEXQ-?Lf+qPK<yqeF@U2dc?&q`pqdy%A1;JMHgketOv7_%!kbMK!|a6<t24`L`cbwCn?!_@=Y{MCng%0A#&ByZ1^uNl)#OfFG0|"
    b"4=`n@PPX#v8ZLmQIn1RnIjKvzsf%0J=8;QuPSoEft9BzPZRypVkizuc3uoqpnrF#x29;TN$)-4vX9i$al93!cNGuVOav*}g@HO#F"
    b"HzjIXZ;cIrF-s`@GAi#4H3Fa6Dd7ZlvVMH$;lFfHaE;z2^!I%tT>ot?DX@W_40!W<K}ZGhP0fCq{cd>-WnSl)XBcPC_N8<<LMjTL"
    b"eY8jDHKAE!L(f?aS#n7+`1nemXXUG8T9poGhqtY8UoxvY>+zQ=^G+C|&%SfUSi*e_>g9`Q6=U!TgUA}i_<sGbjC5589PbeTMr6rz"
    b"!y}6jd6yNIqZvMQpVgMn6fDn-pa}pOF3c6+sy{WT5(VarmPSC>cu6hQ-qTqAS|nUF0gBE+FR#YDqn$)L#!H*jK_g`*?=h-y{nG3-"
    b"bYU)K*DtJE1jY-YQH-IoOt$HHl(w@}sA3+_PVAN2p<sKsBETf)erZ{i&8**}S%JHWb}6T!M`r|_;72uL5k;^nC%A9`yJ=d;XW7<e"
    b">5K00Roam)IC8EXv^5y;Ad*l?L!wXvL&>n^N||~Qv&EW~9#;NO`z%638di{+RRXlu{T-^T?FnUxU%9;i&pu#I`P<KVtX4V8FGtYU"
    b"hKzPB44vk0&yC2Gfd#H-A@HKEHS9@tgH3gQF5vb3rH3~yn@((?ziiaAazY2c{N+x}cxcgN)A)~~-)UnSjr5hj_>!^ly4vy-PKhy$"
    b"eB;=T5Ab4DjQ{Bnse7D!%l^Ren8jZ&&=jcy5eKG}A^ByU@-Wt%M`Mw)gp-^F4P4$zJP}D2Imsg?fSQFtoGS`U9nZ2OgY9;c-Cw~6"
    b"sw1FQ=CB1}36>8vBo496MSh}@pHU>nP183J<2&+SPwvGCKRazau+kg}78?qY93ZCLbvw{5!WqWrIoyR+2ftyuVqQ3gsG1P1-Fg$="
    b"<j3{UM}&qmVl{R`7TlB9PFbOaTqTD1?7YC!#gWU*u3!o{K(E9-wbPSg6E=FvM5)9qL~J^qZSg&1EOBYxt}@7{ufM14#*6dPmgXEA"
    b"oWZ8-r_v&CDOJf6tDmtonMt<Cjc-70XcnetSO%pMvt_nyf@TbUh@Q%smb%9qVT3kDXkC1I)VLXw<zElUUBs;rooiVvgZ*y>^a6p{"
    b"IKWdrn9=hxR@_vKjdJYfENeII<?b9)CYGOGhzr-dVXWf6>d_CGRS;SAJ2hBqHxe*U=zF060{gy}t<?u1zM&mBW5&C*d*AK!7(5Dm"
    b"V3hs=k-O3D=>WVWYbDpqu+A<wPgjHT8`L~QXeNgShb+eboTI1!SeSSby)AX7dG_Pu4X1FFZ@kZupR-v?JD;g}k%dGScCiXIN0?lv"
    b"$~VPAe$U#%^66UVdzr6*!3t~p%%NmSm4Y{sj+1lD#=M61>jBY8q;D>xmRb!0xBKyt$Ny_}FTU9XMq+AyR`Tc)5RD;H>@yA7&m+M4"
    b"5NRK+2Z2TstS63N+eEiiswATaWy9yUWBZ0l>*kW+WA5h+YoR#gjm!mC`*&k`tC$!-I|f9>-57^}fHk;?jIQmudiN`E24<+b=k-Ur"
    b"9dmo$7iti$SM{O<yRZ6@8hkXfeh=iTDJ4#cs~iO_#mr@R5xzND^@<f3o}UJ&70wY60-d~FPJH7sJ%uYX+7+c|H!BI`ikIo5wuD8_"
    b"VxPCjQ`>%o5x6eNC{Bu&!KmIyLqOYo>nN@LSv7cE$RJv%uycI04z#ex<=k{5XcB0QwrKQB8%sp;^edMHq(@(s^HuaD7Q7}fyK?_^"
    b"`pi6s62N`eU+CI1li~^FY-8lV1m-9-ph+<SY@610F$?4T$O)%{LWs;rJZiQMRxl7q@I(DSme3lP&>fp5&~+!2j**}bhnk2J$p(GB"
    b"IcSjUYGW6D30>QKiR`P-&?~U~;CYohz&8l&yKa4CVtNUk*!tV6&IS~KoNgZu;kM68j17Ip0|~WxG%ca{^HNnjkH|`)YvO#-o%A{^"
    b"8-C~J;ij3Ba@~7-mij$Y&E4}VbG@)OU?j`Blp<7@kaBvx2c}SW#=+W9&(jjKxZ84a(jpOS0hs+5O(spGCg?j+zFbpuijtmIrGp>8"
    b"BR4XJsai#4Rf{`FpS_OQ#pT#)joJX@+MBTAIs&;!j7f)Q&ywm?eI(#@<juUWu8tBgqhS<G$Q)Qh4RJTZ30D$XwomfVJPssMsl4gV"
    b"xv1%2))T~Z)}qB<@GNDIYjFsEr{=2cSnq~bhF$;)IM~hq)HUFnl|-@j0dW;Dsy8?OI@l*bp9PCMVaZTtI~y5>Mw!_{CWZX%h_k2h"
    b"ELO$03#fqs8iBfoY*k&VBMf|MyR+w~?rqFbf{u?gs2mLo3fZE&|1jUjXtc%Wj@gLyaTV)YA!*Jc3!D$KyaH^6Y~?(I(KaD&t5r8Z"
    b"ykP8k+F~)4g${r~`jX2S5?gJ$fDf_Hkxe7+vYuY{snk*p3W1-1Rn{3dm3GLd2q5MqrBa^aGDb=o;A&XJBwo8_x}SgyePeVzEC?d|"
    b"<3h<d#%%U07UZnXBE6glwfi+oq^DNiAD)tYm!jhE(Jd=IJ!&Q0v==t+-{H8xkS*Vw7w#--x3&M`vmATa@ENkaee2PauU`>a13?Wy"
    b"!~fkFsNMm;X;u-XSs6g3^WJkD4JD&V_XaER3nf8-V*Q3>%cnNn)yO2lHTP!_y6d-nQbg}NV2TBVg%y5bHR?9AMV<637vI7h1*-cF"
    b"<WR(h_I=A6Qp@SK)R=fcKF?PARR^?QAJwVmwWG#L)bFnP^JO^qg|L&GSe#$Sokqt--)kWZMRu`SHN+*9Yrua27^$fij7@~nZUhf)"
    b"EJ=P*%YfWEJa3(7vo2EKX9`Dap|W#f-@A0vY%Dk8;vKQfLx~{a)jmfU83J}BTN#ty0xTe2>+eCW(_rcL;sZ_<u#)pGkv@RycE?LW"
    b"2?%i8lEv*AD;7*TeZIIhF^zDz1PW^0r<Lh<DP5H4Ju}r2<uCNym`D5qTubGo$&Lds)E+-r7dD$P>)kV3N6kcltbdRRcU)^W|JT`c"
    b"9*;ED+)Q^D0+RM6!R6jRe_jOL5Axg1m(p1kl-e>VfYkPyp1%8Bx+}v((3%Q8_}iGFOu#^@=jm5QxS7sZ?iMA}QRuxF<Vg&ZGH61X"
    b"FD1_NI}S+}0{4^QG^!&-cm+Jdhqx@>Ps}plI(t%;f5=e8yYCYhagP}A*ccO{zcLDvoRqR-*$B=)_4->Tyn<|!F-kM9e9bR6Ik-cu"
    b"1hwh0M=71w&ktxV_y9Svo*ZvRJVN+O`m(D$`UuD^>5-q8`Ck{ViH3SZzSJ4!D`KAp#66aW5zBSr<E{LpLjJDyi3=l8gJg=x7@N%&"
    b"(BI<sR^)T?0_}sPw(Pw2#plNSp_n~vPG!$%RfkKw8QZ-Er}WP|SZv%&=x@>-em_HlV_S2$dJ{*Y50&$5bqJeD3}#4;s<G(ezR628"
    b"8(u~7_B3b)@qnn)>%MF2;d3ul&NOFoaLD<kGLy-98~jYM($N=hHs>zxpW;nD+m{Ld>D&N3k3dQ^WZ*dFt3dw3E?ShL`zYxb**N>{"
    b"4|xLC_YpswDaTWOtOedS6?bp!<{yGJ`(V4PB8@3`mmj-)hEAzp8W%o#U%Mc+2R&mi5H1dGTG5^!az$Yb5)?ez2AsP}YJXlI?eQFE"
    b"Er0JXETF@EN|tBKvJ-IgDmJBbTs<8PT&%&I$O0_KfbWfhM604C+!oyuVkUU%c~cTlo}mH8(bEIvx_;5JD*&M&tlj`-^S=`xSbo|*"
    b"<I#@_jd5}7vP7noG){m`=RQsHZ6}s{!2(!-JYd`ABq!B~mIKov3S`8n+Isn)9^RI&Z{x}j1{7<^zQja=|C}OTfa}*}6V|dJzYi+M"
    b"Ph<(}#)X_^nU6Zy)|<syY~-e=WrG_1Ei!H*)t88jR<Ov5Vt@b~WZsqKLDMNnSBoDB#cl=2))2k@ycW;wq~OXYu{@55+MZsV%A9C6"
    b"u-??gCqlkanN6*H|7HZ7a+ix5VNp8bCd3vW@1G2k??6Xc#e+y0hfWs4fx{ycATSrn3?GrXVJ&!s6Tcn&7Y;P_ra0)S`OR{TlAFh("
    b"(*rdOwy=2LGk$#Lrbw6RhM^)<rlk}a`EaFAg1TI8Xwz;q65nxwgwO#vEpFRJMY^s!_Dcm`D#9wwJ&`1RoEagTx7@9FArSGo(DRV7"
    b"61ZUx1XL{}h;i9c(~p_z@l~5y>F^c#`W8=+kD1Fsf_BZSYAF4AK<w#C!wrzX$(#?8Og4-ony||M8}KTvF39X0gq#BkZJ>LA*5;k="
    b"%V8!EU04CXms9^+r)9%wPAt@yWu9}kSwy+Em)@6ZK`v(JaX?Sv@IhTAc8H#PCSsuzweV8}P(6@r{NN)EiU{k&C3Zd%&P5AU!BM%!"
    b"@Bz;i=MOI^@#AMElh#dGX*l_xw5iv1!||ioN`<k%?XFTW38)b5U<lwH-t#vLuy)F@W_q%I1^iWA1yKBMblgT`#t^O;Ru1@kRP7b>"
    b"=TmZhi#N65uhf=wE(_rO9)bezO(0c{#04vWvT*+kO|j+@OEs*%ndSG<GN)z>^;56XxkBS-K?g&~i`(zlWixFA|1Q5yYvX{EH76)`"
    b"GPT_IHeX%RK;?GLm%9$qNNHX}{TYwN;;I$WR@N&2A7<eEKS<TPFO|!;6873V$YqeMHPk&xRMDH8DH|cqS4Hm~sSDW|KDRCT<hTLy"
    b"HF9F2x(&s{rwjYfRcp=TowSx3yCF$T=|3WjzbZhUk8Lg1Y8?o<x5Ii1@AsjPb{^h#e>XPGv{#nCL4SZeTtrwPlHq$Dv}g!@3Hr_b"
    b"C%n=_Bc{6&l-q?}Pac%9L5n+26t8|UZN*+WnqnzD?k7mB6+8Lr{R24^p`izWO95!~|MV<qZ!X8i8igYSt>jl@8G3rMM3-esw)IQ4"
    b"&rP=ehc-pozqF7R-gQ>TLvDQt6}^o?vx3B}X{6Gat&*IP9D2xbMX#=nSf=Z^VB2`>@0y4_4dabC&)cB{zKNvV?Zh+ju-D7*Hr2gP"
    b"X20%RxMU!T=c@r-h2ZEf&h4Og$U3x&Oy7t+mEk}iTp`bthd2u)!Lb*J+W{Q@O`_1BahY|tic4_bTT8$hqAp=_*;ie*eKPZJX9|r*"
    b"D@LNriDw8HX8rwkA9EOYyvQeKIj`AOL*T^XAa5wu+ABZlw3+Dz)Qt$?EX6Q{caaLqe3_-vQ@(SHE5L`EO7b}Wu1^48teH_k(pUGE"
    b"alW8Lc_jWc^m(L1ZY@ba^pdt$nNjL9$97CMOe3s0FZv{Gp~(4%mnF=t#f0uS<jL57{oc+L&{@8G!z+kte)=!Ul;aRM=`BCcOq}5i"
    b"y2XaU@qBrbU<=Ew5{^E&?E1@o?PehNiB{21JA!+zO_(@-ZvDmAyS|{*jz(I!W%VEHD0)UvUpi7y!g9*`gprfan{%1T6|ZMcVUmPd"
    b"rcrfLaEW9sA@m)KHy#!Mbuq$}n=gE<sO*vNNmWEQ^(oX@K)a36=3~kMJW;8CoT0soW_F@hso@U8Y21IHBeL%<s3eq{CC6^w(F$KL"
    b"x$_(+zQGDq*?PU|y4PUA-QQxt;<bk4mzvq``emoRUv<6*x7zbJqM(7|nGgTm0D|aMBqiCZE(yRTh0_TP+|DPt14pFQm}069v)xfs"
    b"aq0>?dbx^+$z0pgXiE4csA_x)7RKg7L)*dN#rOWM;FnFnLvNDN`kqUXIG^(kn$zs%=<iQ8Xl+Z5iwLG`i|MxrOu`4Us0>{^D34KB"
    b"RhMgqby~4j+RYRaH9gkr+GFR^hD3qO6Idj9uBfd4zVnKyuQgu+U|$FZ#_{eTy9@tnOWP%OHcQ^+h!SzE*nHEduTdT4o*xzrje$#c"
    b"w!9LRg#T2)VktEo87P?kb+#2GZTn67#?&bR8t&COSqxsub#q{JjQqQAJrATTDP!uluzvGhY*l-dH$9(mo3yjcsn;8w?b1EbOa9a9"
    b"W&rOZJFhYR@idmuyj5c6N83)s-=Y=y(V7qR*!3!ui@kQbft&Fvud>;IjIb}B5jpn#n%R8&f?e(Pn;I@fM!!4>PxY54AF(C^z!9@H"
    b"&ZEQ9g5gb))xEy!9c5!@I9^Z)eHMWubaiAPRd|0z{hjA9i9!2=yy-)p=8YDC>S=axW;EqI!Qy_ZYT^f2FnGW)p`S<g(ZfPmjav!1"
    b"GUKpRpr{Ur_K$FR7<sFAcyt~zG_GW<7-1k~ZUNH>_-wD;dL<ANIc(W2WBA57@UqO`4&%Z6g!jxBFV1M(c~<DAxqN|f`S?2dVb{}L"
    b"G|^FUS`EhwL)+fTF1eR%o2?illXtL*zc2#+XIa$?%_JOMzdxRUES)f_50)#Y8^Z$4t53rFw+vlAFh>DfBzKa1K$lpC8ye%LSvAa7"
    b"ha^`HFY|QepLl&tgimZ9U(4uuI$a?&fzE3eGz{ejq~FBIlqi-sJt<K5JTYwG{RuJQO9T8m3(BKLIo99{)TcnZEhU%29$z*>ef`SY"
    b"^eUZ6D%k%zAC+Em&Y-N!!fjrlN`Ttjr^&(RNO1}r?<(2Uqzm7KPUO!f#dd7JJ%)T|TAqA(#$mqk@?WcwpQyf$*kzWyaVzl-MG}6U"
    b"`xJ`b(BD-c!WF;$8h89x(YBC$I7(<7H4|)Zr^m8^e}S3;U+!-9KC47VA2IRgFUD{V`w2<u-~mB)Yv5?wxBGX`3vfSaQL`a*8cNS_"
    b")7oZO$RB1RD5S}0?h5djt0@?dO`23Glq*Raqx&#=GsY=)DvS=CF6~hDDIkqU2Z{m2bE`pUiPap}S-T6hJEL5&NHEN*F{KH0qkG%("
    b"(8BO(5c4b9LGN~AA0J0L9B5mz(g$ltJ;b?o^{_We**Ml@;oOgMGjfG$Q(fRQYy|-6?H@GHfGGhG^mij_`a<O0_N!9jS>v^1PolsJ"
    b"MA!||V_S|t&fnnzE6JzEfiG7nkmaJ8TuRvWuSgyWCY>`)LA0FSf#o$FSgP-%3LF&ukNaXTl~k-E%(ft`gHsLO`YDb5dF)dj-#0&d"
    b"onCI3gY=xJ&Cq*r^S#u6?aB(G&rksD-(b=NHlkkO&oJ1ahE8GEDm`8f{)~@8zT5ft_JX4VXnQx;rV3uGTM%8WW@g>n29n$RN_m8t"
    b"^F1DmhL(&=wGL{&?A@bN?84n&f00w}C2pMh4m)w$$`YBQ{tqF)=Dfs@jaToA02MarCIpc$&4eeqF#uZs05Xq42!w!mE6!HxbLR3^"
    b"hB~`Q2aN6?)TVY?7O50~e#)&=&0C_#*Tv3lSxD2nHygk}`wH={*uo$<Zps|c_!&6;3d{hwod)D6w%Y%s_&g}#5fIJuX(d&*)3bVY"
    b"*=YLN>$n0OJc$AEP$~H9cWJ-nyXS3MZ`u~7HQdf$p|5I*KKA0gVW30TkpGv-W`FF93l>F12@uVXc5j?B`@F1~s8+F+L_2zYb}|(c"
    b"0O4*4B)vx%x@{Ta3hrixSmShSE_{R<K|;(O2Moh#f!M>KeWUL-jroDfZPjsNZC}M9LaMDQ#27efZ~;eh`K#rv><A)zv(YGB>r5Oq"
    b"iZzlBPdVE=1H!*ltM*hoR#y9O1Y9JGXA_hfBm#>!i!w`{efL8H0-*FB{o<UJwUg5cq=K;r7dv64uCxA=)|z${^I(w>o@L*}^WV4F"
    b"`f@HkF+x&BABQS}_>SH096ie^?tml;hU65xKX0iESAqDwVT>z{UIlBLED;Ud%^j-P)e1jtq7^A1fwST5sLmskrOcqza62ad!i)+7"
    b"9jg5bs3Y|m$li(99!3&x8|UP({a5wM%PHI2P=2+P0{qS7ABcIKeL&9X<TG7|jnrO|7>}K<S)_zV7g8&-WN>JuGI|%Ex=;Y$dbjr3"
    b"-;(VC)BP}$L^iHdpPE!lZk%M~immLk_O_ARq&3yHUh}FM`AG+GMh^zmdCPpKv64oLv_4WBrso<d?D>%MR6x(}w}<m_l^vuEJuski"
    b"4!oT?3B2=sVH0npqbc^S&a}}kWxDjWOYmJ%rHv1<>_1K(QCv4$1f|A+O&=Nn;YV2lJBM06me2B|trtb@F%90>sb#(B6?I8>4!aak"
    b"S+CQ4+8xR+UlxS;slh9FkSdn7zpz0Wwex`JmZyVaa?y8FO$$$gGr9UF`#``REd8>Owa7*^0ty9!Huc^>&FI9TtN9$!raW)GqE-aq"
    b"x;AexI0?0?(jYiRsU=E9H$Go~?v13pH>Mt)1T3RDiJfxso!z8dbMwH&Z1onFifh=dOKKIA<VHb5hX=<N)lhR$Hw&_kNV0dp#PV|y"
    b"$EYfB4t9zy6kI5mi9Ja6Vvn4d)V=5?$H_x6-o6@h6235NRbX737A}ARSp5A52BZ9It&;w5AmwoAQ4WWmAa##<NuLz-TuYQ8%afX="
    b"qCw#<*lsTN_;AQU({BM_ve-wP;aR0fkzc{upV4UN)%9diE;rhTKtL^XB5gxPCsE8!u$$yNBI%wfYjLIvlhB`>8DZymP8y;=$6L!-"
    b"%_M688!dzfH-7c8!N>8jzFLbtG3m2F7c1$ZZ21sGIN!-2t<4DCY9JcC8%c(UCW>tTDh4D-RzFQlK9dq+@YwRvC8@e{eNUA7sY6$A"
    b"yc;ASiurQ|KW4MPU=);SV_iUgt)ICehHT!~UYRP3%N|n4xM}UUgq*&dhWJT$^Ae8Rhp82C90k!xwv<<PN2!iMcL@KO#rX2~*?$dz"
    b"FL_O<w;+3CW1&Qt$nJxDVv~w04?=O%_3<~60ELAUk>4IT$E}c84VHIQUp~$iI|rR{e_%g7*W%!mvA&Eje;Ro#OV+&K<sb{D3BteZ"
    b"t?7-${5Ct1u90T%x9WG*FkY^N)y<vX!c5%Dc%%4Dw?qt=v?4|3O}b8v-JhL)QgArpWtb6KLS4Lb1vM@N+kP)LpC14~xoCA!{udNN"
    b"<Cfxl?4ho(&Qh&!+AmI#7v$K7Yu`P{)Me>C8*3A`KNAYK%2tMTi1ZJAiS+>tN@{XGA19>E`)GV(o16;jZ2}P68MTLa%1w%YTtCz1"
    b"6Vk05qAG8rcGRK~10ltaZ?uGbS^24AH(0s@pllA9gF*?t#sk0uSa3{B{<xnGttn;VlpTA)n52+B{|3a-I46xkh=b#L)XN1XWGJ)4"
    b"i|*0z;FjqWxAD7fJ0wM1eb9gyz6Hvv9)QZ3cH)#M!I|(jAJ$Cz6izT5DPx?qjg_?&DQ2&6qDD+^-B`fO4);Ixf?9(~tRfL#lPn&f"
    b"@LRthxrqBhy2xItb5qW#vK;u@2x)>-#XQ2q=EX<(jxMOLc!>2t2AnU7oJwvZm$qMvwq}X78W#T#7w4pw-)DJ1Jo9y5ZL~tvhq3La"
    b"po6Neqhue<ePnLOJTcg|-(B;E@PX-sXP;gLR!||E(O^F=oK1_C8>v&WVPO01jHhSa0M_s1M1L1LDaO?_PfU5~;ca56#!hc4M&o&3"
    b"ON5}_p}e1#@-`*dK)fGx%I&9Pmnl0~`vGmIW2bV5k~83L{exp8>Tl&&bovarr})caZD!^>T1B$~nnHq-cYcRMnxKDaP>|B#-k)!L"
    b"t<&%}sB_7OIy54+9VIreJxu?cmXdqLg@=BuRrldQ9$x*b9!8wOk1=8YU^sB?erL;u1x5ZdZ?ZQX96V-!G2{}4ch?tYk9kp-y3#py"
    b"2sys$EV($iPV0lb+Zm7xrXKC7sf!Hg!A+Lr0_XW_&q#Fee#z@;HY6|>7>ukZ(^)&BRnD#^95-T~va&r%<%0YIkw(vnPk2OVnj3Nj"
    b"CJ_WzF<zNv%qnn~Ri(vntYORA{Rji;8ZJjr>eh$QTsk07_~dhZ<t516%#EUeOp#%AM)OxO#8%Ld*3E;_r&aN<>~0VV20{AGx^Wag"
    b"?ZR`HH7_O4VP>J4Ar4`)6>yY^!xGivofyB4a$H(25Y(9u@)Yu;Wsk5fR8T~CK)$+<yd95?ny4;yGE!S(uJo8NQj^T!m?LOi++EfT"
    b"H%jHt?~9^0xpO%EqOp<0YnE89FTP!`Id8@x7*Q!{snO9=^=lGRr#_{kz5-VfB8KJAiMRuKsljz$1n!CYL<WhIaw@2$9D_}r1tX=%"
    b"D65eLaa-tfP_K`H8>zMGED6(oF-1IwT@;)Jz(v`9psAgLa3!<5z4j-c$>GUsZb=d$f82peuc2m`805pEU~z(Jv}^y#3azH~tGNH!"
    b"j1AdSB3Ha8v&(V-;Y^x=5-nj4cXW4>%A+{&CE#0qh_d9IKBg&ORdVHFrSLT<0}jFy*Ej{d-~dmO5)A;3;8u<bT_G&1<Z7PKhwQ)*"
    b"2$oM_Bb;gGBA8rmt?2O&<bpov9E9jW0-}i=Damml#o+K!^j&e+E9C@5yOB$iDAR}>Xwc@E=}HKlxEJ;`R76YZkTX9`XUc6xug5>8"
    b"X1nPhv$4B_SMI$8-_z;HxB+USks0n&o8GFGP}@d;5>;T+6tY^UjUON%#rC0+w1tXw^Z8adYHwQ4c_A}E?!*Oy2{(V=FPfLQr+D3W"
    b"NY?qBPo6l62r$r51Ay_g_64vld>It~J`8cAFxpP14LEn50z^h^MAN!Iy8uj_+E0qXES9}4OzQh@FQNGCA8*YHZDaNi-`eZ5cYBc8"
    b"gDDVyD!wTK{yf!)NnTaypl15-63|ux@}^NZS|eMB*kb!|){=gX^8kni*pu1(j_IXjqIxm7K7dO1_d2^=7%>yaHa}p0N)}jBGR>Lc"
    b"gZ)C3Z1KW_{DOGVW8@E(CG}~La{H2X2=9y?J`Z=XsL}2{JBfVA^Md|O?8^&%Mq*M}r;Po}@aYHbr&4PbapIwqd;&<D`r&f5IjINq"
    b"C8jb<<H_h*EDIobWTyYPQ@gkyLF}jl40xMw?7~bRm8noJwZ1lVyA}Xp$1TBKVtlo=BR+b|Bo3Ho9U5pI$qzSCf=OYUG8Hp+8Jg;%"
    b"xKJ3-VQfJI%I=W30p~v`KO#8K=^Ml@45+!aD=x0_h5tqw{$@~c+fD3_PkJFCL)T}AAGd3wk%>6;`_Z0cPgcnBp(AkG=-T<TdmH(C"
    b"9W^>q?Ll`-|FxlHHqnpuhqX`y$ME2j8?Dq_sV9uV{GWatxfbje5G)A+)N~?tXXm%H0emyc?)|Qg{i%33DCe7W-)U)mL`qD-yEP^E"
    b"a0`&LJWx7`f1Av-`#-HDrkW}Pp+vh^*m}Y~o&<`_UcPqmDI@w>f=y3Vj5P&{Q*N>Her+QY%iFALe0Hylb$Je@l>>;VF%o=WD_nD`"
    b"CHREfKx|;Jsh-WabtR<Fw3~-5t%M5-S{<am965`I{N9=jW#0UG&h!sYnCJ+Le^m+fIiIevMmlD8bDtis0*0v-S*k|3`c{}5_yCtS"
    b"?TMw_$?Bi;8_D-=VJ1}`A9n#emw43Q&6lR&9cg`x<nQOI6_Qgw2j`79^WcSdXNVzTC8HwzZm7$20AKDZ=S8SvoxV3?M$l4S7t=12"
    b"{gIp>_`<$o-y<SceI8vaRLaq3+v^|Uu~vOo*6mrUVAY85tz}FWS#&_ca2Kx)Eu}UB1$6<NbN1_yvkl=CyD0?d?GhRl#n3GT5!=YV"
    b"1Gpo$O%XcfD23tcZP9C~gE!9)?Y7nJF$5<4EmMB|$k7BXhPDyf1Qz+a?XQBMa0<W8ywtO+z1#*Z(PQrTJTo}Dj#Hwld1Wyk=2X-B"
    b"rs89?Y?hTeBWMOcD|U1Vso;6Mnx889aP7*6AFSOkXug1=XgEPoghz=Y03CKH$@jKSRDpu;zj%aq`SHFy>fw$L0<LiU2+dvVOIiEA"
    b"-S};p;KsOEswxLLt~ezYZ5Qj1Sj&SI>NG<#O~eBaCdkjak6KWaQkmg^0~Wq*fK1zvQK|!x3fVNZq%p0!wH3iUJOKXa^vFvcXlI!x"
    b"&^YrPa6Mp|ahJO88#A7hV2Ap-6+;5OI#Pv38dAT{<O0)33UhK@2CRQ4D6XcM+LNWDMeaIa0Crd_1mj^Ki6>^S+ns1pQu0mv`h_ls"
    b"c^0ZBVPd%)4Rr>k2QqfUTk=Za@I<#qghFiRlS>LvW(Cd3l?vYHUYL&QONccd>vV&u6)5m%u0Vv~;|o9hsW4_#xTkB8RdbM^#`fu;"
    b"7^aj{pyn1Pk7c$@^aOBUSuz|#yJ%9l0X2cQk~lxN3q+E@9Pg@~2}=@L85+j5eV!zpBHchcy{=nQ78FWN8YpoTZeThagG<9e37P4g"
    b"D4cuyGFi-?((Mm3Mq5?m*Jmu8H;=j>jmdRegIYo(J`V4M0|sZNf-cYvbA|J!k`6V4*^I{TE1~z8P*8|J49#K`pyobz9S6%B#hh45"
    b"GW`Oy@gWo?%uv?QrT_)<lSnVwl@V&jgu&Vc3@uuTH(sihOONt+rlY*K_;YzF<kzgJY5ANWPyY*+Kxw61;Rjs&mVq0hv2`c{(cny#"
    b"N^olsn<P{>Tz)vQJtmVw;f_fiq;lJmKLwPYFLCl!Ml<*?OCTO8NqsAUl$c&myXpHDs%WX)$8W=U(j4fhAw4|E;&BP@3Zr-l!Y>IK"
    b"q~q#%$bs-PoV^YRzg=uP@9G9l&RyL@iRzQW`64NMI1SBATtF=6eZWK$X0dE)^hNQy{Ps^_+%Ml{Q|Beg3L1E;@_yxym!|u?5o|;b"
    b"TvjEFUxx^fIg0`gmxVF0+!*2s{KI;H8z0R-P_OA{!fO92U))y=Qn`3M!R$Lc%wg}h=w~tZ2^fI`KEQwld*lJ80_{m9^!(MHvm*$R"
    b"eDg9Gn5Kj8cVRWz0_&6oF4dsmqxx_3+65MTCg~|=sZcin%UX3EOZu8tFmgkIW8mIHzG%^;7s>7K$jO6`h=*LBsuS5_gsZE6*t-2e"
    b"Of-FJ_Wc`$<|O7JrjV+C4U0Fu@ijLSaDueL(Hv7mzMc1(T46{pZGYf=QJpLM8agGXG(-}v!eG)rM>Wbu__jz=n_PR<=TX1YOo50u"
    b"D|Aep7<or93&E>Jb%5^)BgygX&{p6Rb6Gi^tv6~ZOaQgJoq$@pf97AW{-{B?;_e@II$S#1b_6MZ-_1r;?o#kH`h=N%2iG6_x{<69"
    b"^PT&drfTAv1pB3wju+m{&!R5wvY8A#Nl22QhZmvSF}$u&4y7nwOevq%W!31n-o>EG_O?qNEH5@AxlR<EJ!uMhLYSIUyWV-Zlc)}6"
    b"k>5Gap9qH9=!?J2XNa&3M6S@dxiFPD{wi~WAJSp(#x`J>vAa1U)e#1p{%pw3s(NAgsQ`Zui(xD@N<ff&dKSU6J$9Iee4?Pv{R;Li"
    b"Tx7m4nu2>r|BuBOho88I+WZfVA6n5_>s3VD8jj+zOii?Fy)n`A2n;+Li5m~neDRR<@~EeAYEwbm0e_?qzb1sfGOa`tps`;`)G7|P"
    b"?sP`hQ6QD|J{2;w7j@f~d&g);CuP>RDm*9pasNUTL8~o&N{jB!e-ePDvuN7v;Wz}iUx#gVW_;`F81VFP>@=;`!g1mF#9v7O<-~%*"
    b"p~~8ux3@kjiy4E`=n<Uh6<>^bU{x@Ip;dq8G}+GV>+4D|n;QG^HF!kY!h;MU!UEGv*btT^3iq8^g0bLXO!zhG7_zuj<3by1QyQQc"
    b"X9|js%19Ak1C$FJUp47hMq~z5(twz@@)coPw#y`E>^%uy`}PVqA>IfDHpaY&pmzhARap%r$abMUl0=w)VSEGnHDPrqfi9v3;4X3E"
    b"`KM4!mqilwl<%$G7u}_zeZqhgv4%}G4~(c=gUIr(dqn7eYAHINRX`bSZI!3Lqs+K%9N|s-yj5ihbQ2KUdHAMnvmnQ9XfyRJa+N0y"
    b"p)Nl$>z1P$3+0(~?IB$e$)J_?(|B*Xnw%jhxJ<dnredk*y|e*n+@(9NG^T+dPpA-wmNz^Bz`EeTlde{DdWfe#$;0b?ft_=wY&{aC"
    b"poZ{{+!6wVZnyBIX7=rn4#eYseziMjJwCxao7EnSQNMD*oamY#G(ICXT_@_nGKNO`d#I4wr&UREfXGc&3upX^eg)8xV%i<nWZIlg"
    b"a;|1m5t<=xb3?%{L**k6oQFeu`Xdgto{W45Rcc>^Y<{^wg;MAVkWX5zuN2W$IHCYN)ct>@_0IqS<lM>=##bSNT6Ve;IZ+&+d|Hq$"
    b"O`*N1N`M)teijlLM@nzb^)BM5lI<;dVu&}ZLzNhtZ$43NZ$%uQ!>_S@@SbA~kRKt~pkqRq-<bZJ5umefLwxTyp%)-u>0tJj;b{;o"
    b"vbEL+W=E-N(q8`&vFAL(75U>qO1sIgT)v)@@zOHTt*&b<&LDoqfxxc_mVxJ{IjfWZ8PHz93AUZEEHmPKM~LQJvLTjY!0<*zE<!l|"
    b"y!LK^wc`}z;34j_(`irSV)8f7U^V6SMs%;#kHm573SbU$%;Op5Z4p^i%Rw9Y@te{Am3UED(3rkSQeWMf7S2ORMU0BLSfrx-&QijQ"
    b"-Qx!8VFBi+`~kGhn2wD@aXWvxMA7-p|3euw(DXc|JXlYB<Xe2&V<oeMbKhpKfssu5?C~~njr4BAKP9R9INvf0=N3ie0$)$&MMlnJ"
    b"4#FYOaM8{pgcy4LjlcbNh%Utc!})Tr(-Ti1b)UF$6X9%xKd7425T&m3K5%forBYyr3!5Xl#zcsF^_gHGHe4ITulG6Jt;9ik?!cD8"
    b"s>Q#L{>OuP>cs_zTQ()y`<QC^CIu-9U<IoA&Lz2FC$+#eDywEv!IJBZLOzd@bo|oVCT3@NuTRO~WvN=}+00T@tE3S!qpS4LKlT5l"
    b"YsT<uKFhqy$FMQ08=+pf$I3(Rd6BVDgcy+PP*cR*hH*cqx^R_0KaqLW8kAo5;n^9ux;5LGJ)O9PFpEZ-PDCB-gh}}$uE1e(t8<zP"
    b"bQ^zFpe<%|YYnOOU9K<IM+P(g9>;VDtVrg1Q+b;#T^|*GK_v3VbXzEgO?n+&`wT2M2_;4X_ICB34qmX~3NX=w6`pYoS9t0am;?XC"
    b"-Fv3LimZR~XlL;PjA(c%Xrna`2H0P7%Yb)EKkp?6n0Xg<iCN;#{k$g;Bz*yC2o}B8Qx>uEHFYiZ){vyM({~UFn$nz&S*f?UBe29&"
    b"n0rwCF5U{%-MvRT)7cZNTX*KeF%8aX=?#iPrF^1QcP%C%<=+Xx&eyUoStRHuiMmcad<T8PIUmL9uf*p#l{7BCeA>=bH-hxXjEj|&"
    b"y$*AbcPXvUSlM4GD1M_Fo(&|0*bYJ&Tcm8#SJ3xW0#muNx4S$K4yoZ(9%|_N!&GP+OEc+NKf#is@kaloHJ4qTK7C|2W1=Pf<L5hH"
    b"OCG}1HmhQ%VwEj^mHsr`lp^XMaA#9&oi0usNMj~&WyA$Rt%B*$!*A+?j0VnZr-8;-wnw|9%ub~UN@Ox~bJ0djaBhRE=-4`r-S0>4"
    b">z_WX@=^eWf_|ypTU+2C9%(9PiZewcSR3mRT~kL~Ml!F)JzrX*p38lZ!0o06Ngba81NMAao$iniDyZzGIF4$bR$Ic5mS{zfP#C(a"
    b";IFhInb>^=d-pu{Ct8mXV-EYreHC@z3%f1xHz|`{Wm%aIx5Z`octBf63q(>e1E=~ur}vOV0r%v|Fy9{|jSTuHL_yGmT2N5t&^yg*"
    b"6ZaXH;o+`aIUPXt(A@ap#3h@fbr|r-**VdK&7Z84*B`!0f;N8j7H9;IcfQNvLJ5gM&zN^ntj{aR1J=u^F3Z9IN}VIFiQ6p2F{C$E"
    b"9VT+0vYWW;BhQBh`EfPh43|JeI}Qrv!rbP$ufC;7I94r^(n?R<C7ltP;*Az$An(ZSC*^YCB*vbGPB52M(3hU<d*&yowe8!9DDUTs"
    b")K)>t7s)w>RgQE$F_XZP^CJe{^>-JE%!Y_~uO^`}{~{SOk;SI-oLvl$6()aPMG$2vUZMQ+zOY*GsP*wg7-o3sZUfMV(+C2GBmijv"
    b"ZSb)H^iYFK89$I;;<;3-B&q@Ip2qOsr`NgK^wvDgRdd?sPnYyF13@4mU#ZH2){V98n)21P<4)P6N*eXA5>=M+V8|zs@0T@^vB}^$"
    b"M9D`;t`^q}A2qHR>A{rp;3&A68qrQ9$-W+1c*{D-uosFq;I1Z3EId!$EjE7rff5k|>Ut?lsA--ZA6IClTk;big;kikc7DkAG-*X1"
    b"m$Hn_`DjT+0wCu+<kZ-|f$sk<9*CLc0SXeH@8y4pn_zkktxX*OA*=^}UC$PBBTM`vffyZ(V=sqkNEX6*8Av*uC)oWwYbA>_P=O`D"
    b"*-fonnA~3k!BPIIF4-BbJu2tup)gGEgip*is%$){x)?jqxqc!=pLgjej_gv1rH<NL6E|JTKA4ZY@hHX-50R-LT!qXKdEzs<v6gBF"
    b"cyQpj8XRB+wsr8;^di^d?wq+pq?z-OxmmIJy2#b_%^r4Myg>BhjuG^ziL3<H#CwYzn+Rx63*<pMi)EwqMni+nUq}SIP9qi<6qH9*"
    b"PUCR<X0%gA)|7)i`P~kKlUweH)_z3g!Rh40{@<SNwH^yjgmBnYl<ns?s6(N^w4DkM+mIhTq3GW?lL~JPR$<^_289MhnUM+=>oP3%"
    b"N1g&iGVEaeD~jbfCs}?Phkj!(q$pH@5=Bf+8RswU)vmSSv8V-o(vy_S$eRxK9ngN&Jj+MN!!LnRW{B$=C-OncDiwx@t|)*iqP`v}"
    b"Fx-YpZa_&M{sF~fsMGwH!<UnO0%kQD%F!8DSrPFTMB>HvL#Tj4Z)znnU^K%S;fl7KKwe!`Kl+2EI<-X}BwVhDm+HmU2!_OUFZPZg"
    b"Dk#7#CW4Qhscq$)CQ1LA(&a~oR{SeLmuvsh5$oymZg)drzauv_5i;2(T-lU%2DwP93L`Vpz$jk@y<MCr@gr6ZCj&{$aBa&u``5ys"
    b"xYtZn9_2+y_NNGO`y+t^oQi-B!p^J@y1}o`{QGlKI>>gMK+tB$>;phwfACSZpl!NrGPSsv_wl5{*k-Kf==-`vq$nGhj?K?{yX)a-"
    b"e5&FsE~Q_L@lRcr6U0zf#AcU=vt>bNkmceMixCsteas)N!&%zF_FQq_U}hbk(D#M|Zgy<ZDDOsDVk%B+f4*29Jn&-+KKa?F&r0M~"
    b"sloL~4&bM7!M%Y=Fi>BlSz5B0fA&!ayGN;L9W$V;gSv`y(u$u#%I)L*i`&%2cBfHWcuQNg6znlx7|sHpY1>m3`yUF88{yrS6as=!"
    b"qnKg(Ce?t%SP9+PQfK?~+lG=DM(8Q6pl^HkSuv1U%9~}~U67N>nG`YNqEu$dnBnTGcq}Kf*AYNj24!p<gs$u+)=?3Cb~|gTeXT@5"
    b"6`I3{nvQOG;K;Fiw>%*2g3sWBNP4dgD8<<vJ+#1=Gh1PXH2sDg2eGKBV;A7I%A<i$q;!V=c_A_th1c$D>IlxGo#Rts@8bnoi@`<H"
    b"2T;wn{+I|(a5~2*_}$um{7FBF)U))x&}Wizx`q^@9<n7%TS^jz(P0#7nZ<MmBh;>`gO#u@Hcl@%pQ)aP1yA>mF5loaJsUzD<kVU_"
    b"IkK|qAXGdX?m)zXFmmb=_|5Ix_f^~C2OCLju=<LsG-eacLnpdQ`dZPq4)>i6XQyk9Px)vKMJyr!SdqwPxV8eC^EIEtaeM?l5ukU8"
    b"j&iAIYtsF?Avnlo9G3a!rY5jme?c*`Mydo$uY+#6n3I6{`4Gu=>X&E@WKc?SUlE44BXaF-uu3`g9(0h}hSRaLK^P4*Yo5yrO%S*D"
    b"*{FaqrYw*dc_k_by?`JMALLTbJM>55PBX1-rc_{*|AdaA%n@m_|C6mUT3KU0m7m;}E~w*&Et1t0eWe-umxpfpHrNvVS(aAn#;QOd"
    b"SFrOZgP{cI%XTJiGBnZg8EOd|Tj!y8-#1ut#tWQs@f&mZiu_OEYchlRb+s&k61{=yK;jcdCL9>S%|z*Cbj#B5{MgSgICw4669?@5"
    b"48>iT79sz|TAIkiFq-UTrLr>U7K0o~3WN2?fUV!mAB{<Pg`t+wy2WgN$W|Q=D+@$Ur89yw3YAWZKoi9bC<zYLDT4;rINeAc;VumR"
    b"T=?mqs7)KF&0@PIdx!xJj-U^kcP+*<KNR62w*BEV&`)MEoOaEkHs=>c^SEHj(S~iaixjxdt~kyO6Lw#pCP%e{kUu$ztqax*JGq>E"
    b"OXoK)Ou7(ziFgyMx~Z2G45oT5{2;4>hxN>nDIJ#RzCsrF$5;cSbrGk9z0aDJALq{KS`c}Vvg+-KgDHyulz?ODhGi8shZ_kzyhb^9"
    b"#agg*SX3)jR{G=Q3|Hkt$0a1-`C-q^>I0YdZc<`(kZ&|dK!nUOl%J>sVeYMMXK`QR{%@doOu}OLP4sKDXd1td7Y~Bs21~F(uAO%H"
    b"dYGzy08G+YRAo?sE~csMVmdbB(W?L!-ee~QY^#<(oeX6rxM%#hK}8`kQ-A}a=O4~B6GQEMg!3*nPGiz6ihRMo$fduLA=XE)qBdl`"
    b"EHjcU*KAW%w#xRrIXqFes}w9LFG=oi*@qG*ZsjFV56={Dre&Mg^Sd5TWA6mWbfE*kVbubqa``2zqx}Fp%CH{T2-vQ%9Q{z!IsSnv"
    b"W$?H&-70RW*cw>-wxp9V2gLRYAz&rr3?bW+R2$|nHX?Gz*~nd6(e4(9T}isjex}>sl#H=_ud&3@e`wP@er6zLFSZhE)6i@KEDuRA"
    b"*CKM-@dawS(<%Dej+74fxtkt>hzCtTlJ>iRglRdyixm5UIHY}E#>AD!?Jg*F0*wQ%?S;PbXmPO3!76685~~`xMI(BQ)5$SJm$FKO"
    b"olcpeVj5;~M&`WCUTN@t7GGva72ngtq0X;l?wW4R*f^>>ko9du!|3V%wK_z-@OkH>7z)x>5PTMcG*jtUD2rPvd9ekQ{z;k$^33^N"
    b"W7KI)mbiiZN?7M-_k?vkRF-yfyHUZUdcC#TEl9GC8tFxlFMwu~1tAfHTtg7O6pz;<w|7fmwTeHvw4^;bIs3=2;ZLwMenOO=WBBaW"
    b"3BFTz0;dOn6jLP*Um-kA$o>iQOWhvpEXVFIZh;YBMT)5t2R3$#IM=l3+OIQ8)n~f`1yIhL3vKg`*QYO-2l0I0YDw858U%xSK`TWC"
    b"a~}Zn=(S<N4Q7s=pwbp~`7yA-s-X0-P+J%(X2|Uf5JUq7idL@@THayI8AZ;#z4YpkX;A7_Oo+fb*TUOiGat2?{Oa0MaZNwyR|jL&"
    b"G`hvpeljFkTS^*TXbs5qbQHOjtH8-s>3<^V=lq#qWW4Z8&M*>x-$3<w(~cWa_l-@jAN%kH#6Y6yD3rly;3lu2f~S~b5XUN98fZ!u"
    b"YQTvPhF+0GBGaGEWo++aGBA0gk#KJFS^6iF7gitW4|s|ah`1IQZb~~%rX9^s)=ED)oL_^Lp3}yI+1z4uDfURT`n_BGTg;yS>Eiy)"
    b"BK8~I{#hVb<jOo90r<BeCJ@9u1}Pz89D)$Rm<Bq<rITD{{dapoPed=qK3j|vktdUwmmR59nuO}(s!&iV6ih}!%D1jK_^041aXt-?"
    b"eAoe#Z{nvyyZFA`D_gA42QH9WT~MHqVyI$EAn&rquTu!&j?@B~%i;Vfd;ssMA@2DvF-n9-$;pLfd_)L^rUDnfbC-WI3*>#|tLe~Z"
    b"m<4<@qTg?2dBJ&yWd?fvsyTB%LS}bc$YW_Q3oDVAR7GcOeTmwqvq=q$l3rkg(`aZz7nK*RL+WlJPUUhG-QOIDQI<1W>s&pAP`5z-"
    b"19q}^ROn)8?JlZtgEcc4L$8HBRRu+GNP~5nz*>_^aYVz_OS2nZ#2|tJH{4>_v#zVKNEo$AhhAS_-A-{pd4=0NPa9Ed?*8Ao-O`h#"
    b"r?MTD-WjGNUlyp$$p`My=qdUw270Sf8YOX2He@};JaFy@Zm*N8qjr+a;;r5#xoV#H`NPmU)?j`D;hO|Q<od8DXND?PE6HW=I=w9J"
    b"WyK*G`0?wUgUnZu;+z}sm&+z{E5HaOC%R+_>@=q18iai!%;6{I#L-x`qRW~fKiIR1^6%I&>O(uv`*}bxQ5`$`;SPsZ$C^JSyFaG<"
    b"Yv3U<gq78G^3|Y>Vg+(0yH5xj<#$6Dw9RuFeBZZ8yrm)%R20cZ-ItR-vfuYuHh36WuA+{EMkMQ?tGFfkVZG32UTkOo57iIcR3PiN"
    b"6kRd_l2<&*FD+kb5opiiRW{}8tm^d8q$mM$&h*sn+jc<Ug$P>WAJg_ok-vTt@RG`4fm`wG!Df~+mqD3#=WZdX=njc(qw$jE!KV+2"
    b"SiM5533HFZ$I0)sJ!FXQB8=q81K~1|2>N%NAbExC>HbZ@VmtFIEI}Z_5kD(!8fSayO704MyBjl0*!RjLv7X!U_j}_qsYu0i)LWTS"
    b"wL>teFsb!sfXzdJUAFhTwjj*D+16JU$I%h06C9(5HG~{X{Zc8xkdmh&<_7aPD)+C-dZ<lzgdTNjV57ibQd$u(jb3Ldn9$!M5Y7Ws"
    b"^^bBE0INUJ?*Ir-a*7bHRy>{Jp}Fs(sd_=Jnoa3vVDIQZhht@tZ2oDwo#%vip#sd~0hc-~HgmPT^-@)GFVNQ2c*#Zbyb;tqQC%dy"
    b">6yyBB<SppZWbF8Mib+XvBl*(KH}lMfWC=n(wU#x<Ny?w2srpz9NE@UPc(qnSN`>MpF4WVPfNgUHFnWO3if#6Oe-2^V>bUcY)QoR"
    b"KNRJx_*FdP&=3fv3WIYevQBLAv1yu%4`u*r{9#2Hx6@RrkK6q#ZrDW%fsKqx9jF#I4WW6I%7P=*lPlc{8MyaE&TC`?<TAqdLvI-e"
    b"IPOoh^9Gzr!Dc3(N1nJ6raU_;6Qzz87ad|hjWx9{M^%KVP1g3yv~Vb*iPUWjl(?LyZLbYjLAXf=Z8u@spdlX$FwKsFvh<5BQ#gWa"
    b"8foP`Oxhr%^DDbCrf>=PE9*c(p{3;eJ{fLfcJ)(?VdhfZ^Po(81nQ~o+fu%nLb{AXvLL{E$zWW<t&Brm3h6r8<1*58_=>>IS_gkM"
    b"vdKusWno|XH`ObOLHD7S$A=0x@gzN<U&Z}edwdXU$QZk3euWf2+(c({duIxSsBM(zSet8^t;)Rq6hELDgEbwuOI@?qr92NV8J+s2"
    b"jiRiA8HAiv4`MM`yB~8gZK$J^Z19=7SakLPbVKQMr!Ipc3GpUlD->75Tg>b8@&IFlQN$#dmuDuoT6yGXz~&!PlbUN?3dOD?5Q#k^"
    b"sp;6r#d>;M$BIxZJ;R-hEBZ!<iFH|(A3hXeNHA)F#4s^-_HF%Ha=X7!*i@>gc755GmUrf6h;3q*OX=K;aj62Z_qYke6*80WN0ISB"
    b"cufVzhx7c_moVd<OoF}@ih&EXx3N?_E4<LZMrH4}wgUuxxK+^D$I4O46`z;HXZVjyfxFup9wg%{0ff?KL+HJgcc64hzR=dtR{b;b"
    b"RIN3U1Fl7jgW+%NlWB_8Z!vaNXIR(U+ZzMtnlL#N#oO7c8HVz)nDN@Rn=tS9w*v00_Z=^-Xp$=cb4>iP!Joh1<2TtH96il%+E+}l"
    b"mR9QS-9SOQ<N{u2=&l!jm=I!?=!aq?P6Dx{wQYXV@mc(_t=#tq&`uoL0|Jv>_27QdJcb8S8ht`(RV;0ul%1}I!EftpX>chFojXCa"
    b"pc$gKyP%ldfnU+glcgC2U786-MR0jWgNx?yH1N(eFFINRV16%}tTe;Hxa}h>G0uc?olHL)w^;_3*1HMtelwi(De`UsueE}boSV{i"
    b"BM=q<hx}d3PFI|tmGG>=J@lLE{drHLqI`p#{^*9R=>(@tz`<QkY;~QAc=+2p#R{ZD6owX8nDB$IuN>c4b6+VgddtYh-=RZl1f-tw"
    b"T?I`_UpSHUo|sW550C`%Rr7bDf?SG5OS@UZryWxrj(B~crn}XaEkN0d#w%wmH|3!iS$@-zwM<0YW7Emy!uL1upY|YzaNfrRu1})!"
    b"2H56l_1bZKn#|dpB%FezGNWNvZZ<OxrapK7psxO4Qc6FEwRRL!`74_09n#gQddU71a?oj&2A7Wxd5H7nTZT1%taq*5(HEvX4;w6z"
    b"of*1|EPKP=kI-eLmgN*PdFLGz?^9=A_-x0)%7ayW=BrX$t=$L0Mp>P4wC%%spWt;ni!|}k5_23p72btK<Jc&8tcuuvV^vqH+tvTJ"
    b"n>GZJwIg8({*{)Wfa{EgzIDi|y-PaXwp62QV+~S{a7Pjz@)?O(O{MJFr+I{Xgd4Al*vrb$O&4J6%ar~-oDRjJboMp<0%3D9&!3hL"
    b"UkLyF3510v^Yj>Sq_XF#y<ay%RUQ&GMfnMQzm%XPD^x62@!)}+^a}vFkg%D3RL@YrAc?W6^}`bi0M+6GLM<BPFndM;k<&`G@Mb6L"
    b"1aLb)Qpic-%|F$qfnz(*MSKYLQ<)9VmZv3B5Nq3-8EU=x-et=OkUu@t>aksz`SIT7dfh~3C^+bd1$3Lx(2yZcZaDe97~l+@7K^$Y"
    b"oY-gz@|v9UtHp8=^7A7jVJ=E&18vT&_21MmdtJlB|8kk9#Ga{hTB7M(I(q0Dj6?RoCvp9+fQN{yYNs&hT{~pVk^EBpk$tCpCixL%"
    b"MDR#VM24@iJ?{Y~FpMy%+~cr6Sg!1fBk2xt*)8llsUUkQ=y)Vz0_wWXFH5g}3T*_4kKmWT|0B`E-4@ao0F%^pIYq><9ll++;PO;n"
    b"t;8~SQX2EkW1VNvk}%JT*!s4>ppx~X5rZkJ68P32t*jbp8NDEOqDzIkmK#CfYi~28P?uE~3mWzJ;222_P2HRYXbyu14L-&D%_Q8C"
    b"`TNS~PGKz6+RvJ+d`*Z9rqjPq#7VxfTTUOvC=+nDZ0WhW*8n-H(pK$T_BaI;-xcyXxQh)GWWNnpH9Giz@JP*oc?O4x&6s)o_0Kw#"
    b"AQ#R4Div+DK}Q8D!VZeWNXL}@q6SQpqUVGAmSO%yCLKeZgFY>W`DHa;dbK8-sb6Ti95X4=qGj5kEH(vQR1tKhDp=A?kq^HbwY02%"
    b"+i$UVja)}_LrbfxL}oam7?<`U9YG3Hs>rq_Zaf#~xvrm5H97onFn0MC7T~}m7cehl8vkd)DD5QI$xrA*=|;sA>hKmnxS9n5Ar0zf"
    b"=c5ScpF;hc_MR>IAZ2lV{Aq#q%e67wuMEtie-6!^-rPi~4tB+hI9rzQ@~aD?(rI$K8{24x*FR>s5J)m{H1BS`vXN0_tM)f!mr$J&"
    b"B>LeS0YjC^r6{DPX!`#K6oU{n-1em^Uye|hpOMcWFKU5ntoC~Qy}{l*1zq6_M1FLnzc3jF>PHc;CGSC?s3;c=lM@Qt7X1rHNjfZa"
    b"h%ZAo8G&0&WYpr_kbXxsLL?q{UCXHP1ehZOrR45v*K8q(?g?}ugeCy_z`_-=m{B4*UhPZP!OTFar~RP(LEyprwF<(Or&Q0;5*KA-"
    b"Emd{lp`3<*9~3t>jAerIL1dC{u1i}x5m6A-_wdJt2!Vhgbym}*(sWW~9Z6hSka1~RoD&1{L8OgZCs=Gp_~1ud|Mba3Zo)s82c`eq"
    b"Sferi(Q}1QxH=@dHr@2ehWiAKe6Vg`Z=ZIbpUOaA^X&*EHN~v;3h2vdl7?8&A)}atmRDM!^8qK(_a2^yQ^0}D%*UTc)+)b2;wUP~"
    b"!sS4*zhIIdEMA@kB9AD+ZRtmn6?~B&75DRS#UmWcN<Iw7Fduu+EO^ahlndTm#>MdYz{D^dN;M&*b?Hy6Jr*kGuc#rmTSn!BlZn?h"
    b"31NfVlvT09J;`$41<ZZLh_)*kw>MRxK`*yC=P*8BRQDOVosks6k4ggZ(vodWja5E~JHSK^g>biZ$V&!eA;M6IWXnB?^-J?8@;r$$"
    b"$NkTy6__HY?oW733hRqql7BP69@hSnEik2`DwUH~E!uU2%0s>m-S3!0GU#n=FJb=4hf^<uM@tKGfAaQiea-DblX5XRw!9Z>fKf&t"
    b"sY5fzDQCWJ`>qA6l={6f0R$k@@BD7S2to!y0aJ+UOrBD0;3r5UsBsMId;mO+BM;lhBT|Q0k9MDFb7|VnPzia^;WwBUW>gz;9g_~C"
    b"5!kwz7ts;cAm4`~4sSL7F<W`<3W-UP@L<n%2}RmHMIR+r`n(8Oowk|z+b*Mc|K|D$uAa^KRY0J6ykKNfS%XPVh~!!$)_@m}0BRDi"
    b"TCsuf;ZXf9gK!yn<Zk$I{c2xbWV(I5s0A<H57<14QeQVT*R+R8n77dDVD6p^o862g+#H9AkwQO*2c6g&>vekJ|0z=BA3bv)o6&QH"
    b"EL`q(EBGw=$$KLT-*iZ+bNYna)tsse?vjWdEL3)ZRFZI4^cC{?5_c*+f#~bFOj955FpQ1hvOG|txjU=y<MU}(#<<D3{OvZRMmX@z"
    b"I|bQLu?aAc8qtYdI3%lgyajd%EEcpNfRW9m2LbFWks4-%J^Lj<MwcvJd_GtTG7QTMc!zd|NWs_Pv+KEK_y8O?cwLI%j=KHY!)jBh"
    b"Baz;2;|2P~khG=#m#XFzq6(>)5(lx!J;QPWiX2psDPC{A0I&p%;3_{(2|NQqTIMaF+|TgsK89Nm7ZcowBQ%lSP)^wM-y8UdGPM2x"
    b"n+bpt%ZBC$ea2t&-o^O(H&b-8pQtQK(uNK{n}}27AsOA2k*x&6hHJ}?Q^@NBJq$qTm=q6qq&+B(^(Y!3Y7Nj;kbBQ%D#?<!;~>PQ"
    b"s&X>0VhdP!btd4RQ?To(>a-YmEt704HXrc?BWu?dx!SUv5~4H$z)h38$)Mc4NsL!)0R>+wtGMars+b-juu2QJg;VycF0q*M=jLv~"
    b"Lp)T2$|1!R&|e`~;y))-m)f{<jVA;FH>r@IN`K;8NpHp5&Htx#!WzI;UnGayhOcA&5Tl3;8_^Rhu1{sNx9k9KZj>p!hBUZXrU%a8"
    b"VfeYywQrVTT}VMW_R@nE{fq;5<(Ra$B0q5je>O|oi}i=~0q0KdzqpTz|3cRwZc25<Fqj^~yKOC`WdIR`0Uy+-?xJ(SvLh%&Gmz@M"
    b"3zfC5nG9JFJz=*clB7OM)$rWm-I*ERo(0yl*93nsl&>1Cousff2FyNd&Rp=)Qd1C<S17+p;)rP~-|v?IPmx5A8~Pf+jpr(4zTZsI"
    b"C!G=uS?+k+vbU0l5NVCzny#{~;VU{dG9oO2GqZLWye}lAKWhZ`Bt8DrFDAD>htJo#v;0W7n5N0ZX6Q(_w9`oOr^(K{zTx7Ds@7>A"
    b"{?zV|t~62>h9JuMALrJw2U=-vF;UFkIGy=TV)L8tyu|b8hBNQB`Dul+g|Iv>22sFV8Be*rC>36r4eqhfE)-Q7GfU}VGkxvQ1uV|#"
    b"9FyR{c;ldDQ^sBqXR<8iph^u6`jikLRhVMy3%Ui|Ev{Iq2B?!#I^m_=7#zYL6(i8s8T4rhi<Bw6?*F&noNmd*kYi?Jb-(Im%mX1s"
    b"Mhqc)(mV{Bkv~+QF~CmY4*>=oVwV_U0%E4}ZyCfA21Mkgi9=HgQM8Y(h|H2bgjuMuXK1iu^2~Re#kJfyNvjU|=P^ax`Frfqeui7$"
    b";$lDvpK|I+@&zI42E7xEEugj*k!MRKw87+wh)yQ5uofW3wKEG{9o!<$lPd2_e~_8hTix+)qCnG+1X9xX^PRe;h&CJbmSY$s;Rg8@"
    b">aVFUF(Syk+gkyFjtx4pfFR;jfH^23krw}D#4!{IavoB-(y}OYzQB+DG$fE518h*wzxpnq8`8K)wIre4J&0IaiCwD0xr_DJo+_3Y"
    b"m>j9Y{Kql~bS2eJ8NIYmQz_4R!zh5rknL7hQjN~TYk9%jAZ~Lz-qB@r5B6N~0`yuJrRCTkUI30pgPmM$aKAOoKIGP{+*ValT_NJK"
    b"PFz7=8e;LN1wn0j?r1i*BxRIg2yqiN=}jS4T*K8%K5QV}r5`Q)RMT-Qv+NIwvg#9Eq_FUF3Z6TIBbI0`TSv$HD~E}6$Qjr7OV8+("
    b"%}kQw^W`%asv_k^1|zT`G|mT3ATV@L(RIzox&_Q)=INby-q^5@{$<#B0@spOq&RuaoRRpHg4D|5dA`Ag)T-10O4E+Nl87GDfJ7;v"
    b"qd0NT$e-jlR#dx)RuqfN{WoFKnxJGTZJVzDY(YtR$eo!TQKqbI;l75UX7x6(&bIXd(Lu|HOq3Ty1(G<XUluOwVRkh_^LLt)8?R-m"
    b"3HhHA2hmNbf$sv`cSPibm1;L1OsqBa*_0vx$~^pd1pp1200HQo2Y|yQ_U+=ZvBYQl0ssI200dcD"
)

# Raised orange GoPro-style mark with strokes 50% wider than the original.
LID_LOGO_TEXT = "GoPro Missions"
LID_LOGO_TEXT_SIZE = 18.0
LID_LOGO_TEXT_MAX_WIDTH = 122.0
LID_LOGO_TEXT_CENTER_Y = -7.0
LID_LOGO_LEGACY_MIN_FEATURE_WIDTH = 1.475
LID_LOGO_MIN_THICKNESS_MULTIPLIER = 1.5
LID_LOGO_TEXT_OUTLINE_OFFSET = (
    LID_LOGO_LEGACY_MIN_FEATURE_WIDTH
    * (LID_LOGO_MIN_THICKNESS_MULTIPLIER - 1.0)
    / 2.0
)
LID_LOGO_BLOCK_SIZE = (14.0, 5.0)
LID_LOGO_BLOCK_GAP = 2.0
LID_LOGO_BLOCK_CENTER_Y = 18.0
LID_INLAY_DEPTH = 0.8

# Embedded CC0 Neuropol 3.100 glyph subset used for the GoPro-style lettering.
NEUROPOL_GOPRO_MISSIONS_OTF_GZIP_BASE64 = (
    "H4sICB2mkWoCA05ldXJvcG9sLUdvUHJvLU1pc3Npb25zLm90ZgC9F2lwE+f1rVbatbRC2DWi5VjtgjGnkYQxBDANlMM0DNiObSgE"
    "KJKttaxYh1nJB0wytATGnZqZBMKQtsM1ntLhMKFuqUlgmk6BZkppeiYdmClJj2mHSQo1bem3Zk3Vt59WRjJJ21/dnW/3vfe963vv"
    "fd/brWloqAEnfAlYWL6yqkp+dHeTDgDvAlh3r1m1ugqKwAEwJoS08Wtqa+pvvnTHifgLiL+1pn7Diuj+1D4A11LEJ9bU+8ojHzQL"
    "ALabiAeaYsE2Zh7zZwDn7xAPtSjB0LKKhgTONyC+sAUJ9het9xG/gPi0lliqS7zJtCG+H/GZsWBXGzhqEYSf4uDiwZjys4fvrEZw"
    "EY5TbYlkKv0VGIf+rMJ5GQB50VsGrBZgGKaoWmlXE22J6Nw6JdweDaoGsUybBNpkJ2iiRfOwmmTVJzjZ406rvklvnswFHqq2obqx"
    "54eufGpIKQIbw7hWb9jWtFFRk5FEXJ7vnef31ylRJZhUQnIkLpf7yyvk9nhIUeWVK/1yNNKkxJOKV65OyGok3JJKyqqSVNQOJeQd"
    "7UwWr06osWAUZHQZBHDjMsphCVTBeghCBHZAF+yG/XAIjsJJ6IM3MRS/hFuMn6liNjLbmTATZV5hDjNHmcvM22cPHj1/fu/RVklQ"
    "Tuz53sCJQ/0egTt94Ehf376jMUkI9HZdvdp7bGAgday+PtUVwEnduqXvuxK+7ZteH5DIg8WiwBuyHqGy51ScrNBLSSk5fLbn4vbB"
    "umtCt9vQKQl6bVmdbpeEsJLQJ3uE0wRuBQaEuaL+gNcL760nmz2CvnlmtV6EmskzxHbjriTwFy6fJVaPsLr7Ehl8V+D1gg+fJbUe"
    "Ei8Xkan2wx+RAonEeGIvu6bXeoTrgYEepG+7fe0jSWDPaePdvtv1ZIGHpLi/neqMSmE+Gu+SPcNLudjeXc9HDu46LWmzKsSz/EdP"
    "X9VrPPoOrjJ8/Ix0kj9z/thvPMTDnT54pO/c3iMxSRc53b+4zisJxHq5tVHSB/kpIhkcsazP+YBM1O3E3kOEnmUYj7u67Yb+jEfg"
    "L751jtg9wlPiAtH1p3mE6ZovXmfJCu01d3/HoUCwY4/iGY6iMr1kyOouEYXhr3Z/VnRdIvd//bQosOSKdt2tV/qe1XlJv2/YvM+/"
    "2XfynufWVFE43nOt7p8yKfz89wWjfmeCF+bBWqjBiq6HBnAwDMuVVyxctGZddW2Ja/iPrjki+3CJBu7vJF/dvr39pZBHr5rl0C+X"
    "ikSUHfqUEge5ypENf3+bFEuuuQ6vw+fwi+yDmbjQGQ59cLromiGWOlxLxSVi98vaOz3E/zKnL3+VJ+AgE4TBg04nKT7gHKM9GPdw"
    "uft8MRQa1WmDsVAMnwYP+OEp+BzW6DqogyZohR/Cvxg7J4uC0rtn4GKvUXf8FIfAlYlC05bndUw7269NcuuxeeJsx1CpHpvjMKMv"
    "+ETSzC1EstCiY3D5wOaZDkGPc7NEwT3NoTdPE0mM8kx3CG4yuT8RlgStuLt/iOnrOcUOzSAT3MMB7Qe23k71tcikLWrqi9KwNtWh"
    "xXlt2nCnbceJb+7un/T6icPf6pW0Eq3TNhzn0cmL1ElN499Qe59r3fFltcPjuoiVGfntFbJgHVnWc6P4zqWhSvejwqkOEuGLf6G1"
    "e0VSukgcvsG1vvBCVNLurS9z6EX8bHE4Qg5wrkdN3ZeUfi1aKbqMBAKwE76+dl9ryfaxSx8Ay94xDjFt7c+/bbz/UDFjSXpp2ssF"
    "2PcNTrAAvdhV4GO24fsnMN02B3zsTfDBbZDYZpjDboXpzAC+3TDV0M++n/biGfgi6qnkAtRi7uUAKzubeQVTBnAQb0j/JfNmNuLx"
    "8hDAMpbjWQvDFFgB8qUbNtfWwHI8hpKW99Jb4cfo46+yPJYFlvfoScviswjpGUkGCka0WIBHLANboRBLJgPbYAxIJsxROguM1Y5Y"
    "HMpMmEH6N0zYAi44Y8IsbIU3TNgKMjPOhG0wkakwYS6HXgDjmWoTtufATljIhEx4DHuTydpyQcg2ch6POp6zx3VeC8CyVyCKIwhJ"
    "fIYwIhFch3F0+3FUINSOeAjnVIRX4u3HdxS5mpAWp1JepFRDAp8q0sPQAimkG5hC51XooLq9yKWgPhV523BEqfUwUqJoX4WNlDeJ"
    "OhLUh/n08PDjXYlHx2Y8QmoQGq1j7igtlSizGBbiqKQbexHq8f9XqU+2XYfzO5GyjvIFoRF5FLrGFOpKYovz4Z1CHkNzJlIxGp9m"
    "qsuIhRexBFIbUC5CY5Odk5ESpJRGlFSobfWJnOTmIIgj/j9E28iWSrWkkM+gGRTDixi1bcg8R/kTH5tRGeP92AsZNSZMyynqRRKP"
    "SxnXnF1vMid6KcqbkQgiZSdSWmhlhZHSiZCBy/SpmPpzoyXDF2hcUjjTYa57J863U+mgGblcK/k682NcNmIp400SuTM6Dako3pno"
    "GzYU037+2jNxDFH5RupHKkdndlfUIr3RjKQMq2isg+Z+yo9vxp7hn0qxJtPTIEKpkTjFzEyMrrWmUXltysuql2oNI19bjj+hHG98"
    "sMvMuw9r3Iu++9BKA41jdk0Kfq6lqL8pmuWEmd9GGpf8ijR2UCeNcmavZDwJPbFnHtd6J/UkW6dBMwdNdHfuzKnrTL5CI3siUxE"
    "GnqCW44hleBspJRu5/J2RGllZfl146aqz1E6qoZWegEm65mz0kjQmISqp0jjK+EkTRA7DOy/2qP9HhoB2V6Nf0e5A31bjRwF7TSG"
    "ly7AGP7Zr6S5MptN5lDio6XT69+nL6YH0hfSR9NfSh5/otRnteKX3Gf8iH3MZEk4TNj6kGLBTGkM7tQdrgIkGU3HsW1aqJ52ZbV"
    "XU+EhnxZ8alC2gvdaCFWJwbsVIcLTH/8cr/Q8cf/2ESQY1WFAbR/u24ZfRwa20Y2e8ZSmtIPuVgnMsjsf+j4fPjPg/cv0bpiqxz"
    "FgOAAA=="
)

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


def add_uv_sphere(name, radius, location, segments=32, ring_count=16):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=ring_count,
        radius=radius,
        location=location,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
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


def add_cone_x(
    name,
    negative_x_radius,
    positive_x_radius,
    length,
    location,
    vertices=64,
):
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=negative_x_radius,
        radius2=positive_x_radius,
        depth=length,
        location=location,
        rotation=(0.0, math.pi / 2.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    recalc_normals(obj)
    return obj


def regular_hexagon_loop_yz(center_y, center_z, across_flats):
    circumradius = across_flats / math.sqrt(3.0)
    return tuple(
        (
            center_y + circumradius * math.cos(math.radians(30.0 + 60.0 * step)),
            center_z + circumradius * math.sin(math.radians(30.0 + 60.0 * step)),
        )
        for step in range(6)
    )


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


def support_free_pivot_boss_loop_yz(center_y, center_z, radius, arc_steps=12):
    """Return an outer pivot boss with 45-degree printable lower chords."""
    loop = [(center_y, center_z - radius), (center_y - radius, center_z)]
    for step in range(1, arc_steps + 1):
        angle = math.pi - math.pi * step / arc_steps
        loop.append(
            (
                center_y + radius * math.cos(angle),
                center_z + radius * math.sin(angle),
            )
        )
    return tuple(loop)


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


def rounded_ring_frustum(
    name,
    bottom_outer_size,
    top_outer_size,
    inner_size,
    z0,
    z1,
    bottom_outer_radius,
    top_outer_radius,
    inner_radius,
    center=(0.0, 0.0),
):
    """Create a manifold rounded ring with one continuous sloped exterior."""
    bottom_outer = rounded_rectangle_loop(
        bottom_outer_size[0], bottom_outer_size[1], bottom_outer_radius
    )
    top_outer = rounded_rectangle_loop(
        top_outer_size[0], top_outer_size[1], top_outer_radius
    )
    inner = rounded_rectangle_loop(inner_size[0], inner_size[1], inner_radius)
    if not len(bottom_outer) == len(top_outer) == len(inner):
        raise ValueError("Rounded ring frustum loops must have equal resolution")
    cx, cy = center
    count = len(bottom_outer)
    vertices = [(cx + x, cy + y, z0) for x, y in bottom_outer]
    vertices.extend((cx + x, cy + y, z1) for x, y in top_outer)
    vertices.extend((cx + x, cy + y, z0) for x, y in inner)
    vertices.extend((cx + x, cy + y, z1) for x, y in inner)
    faces = []
    for index in range(count):
        next_index = (index + 1) % count
        bottom_outer_index = index
        bottom_outer_next = next_index
        top_outer_index = count + index
        top_outer_next = count + next_index
        bottom_inner_index = 2 * count + index
        bottom_inner_next = 2 * count + next_index
        top_inner_index = 3 * count + index
        top_inner_next = 3 * count + next_index
        faces.extend(
            (
                (
                    bottom_outer_index,
                    bottom_inner_index,
                    bottom_inner_next,
                    bottom_outer_next,
                ),
                (
                    top_outer_index,
                    top_outer_next,
                    top_inner_next,
                    top_inner_index,
                ),
                (
                    bottom_outer_index,
                    bottom_outer_next,
                    top_outer_next,
                    top_outer_index,
                ),
                (
                    bottom_inner_index,
                    top_inner_index,
                    top_inner_next,
                    bottom_inner_next,
                ),
            )
        )
    return create_mesh_object(name, vertices, faces)


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


_embedded_logo_font = None


def load_embedded_logo_font():
    """Load the self-contained Neuropol glyph subset into Blender once."""
    global _embedded_logo_font
    if _embedded_logo_font is not None:
        return _embedded_logo_font
    payload = gzip.decompress(base64.b64decode(NEUROPOL_GOPRO_MISSIONS_OTF_GZIP_BASE64))
    if len(payload) != 3672:
        raise RuntimeError("Embedded Neuropol subset failed its size check")
    with tempfile.NamedTemporaryFile(
        prefix="mission1-neuropol-",
        suffix=".otf",
        delete=False,
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)
        temporary_file.write(payload)
    try:
        _embedded_logo_font = bpy.data.fonts.load(str(temporary_path))
    finally:
        temporary_path.unlink(missing_ok=True)
    return _embedded_logo_font


def widen_planar_mesh_xy(obj, offset):
    """Buffer an extruded planar mesh in XY and rebuild a manifold solid."""
    try:
        from shapely import (
            BufferJoinStyle,
            constrained_delaunay_triangles,
            set_precision,
            union_all,
        )
        from shapely.geometry import Polygon
    except ImportError as error:
        raise RuntimeError(
            "Widening the Mission 1 lid lettering requires Shapely 2.1 or newer "
            "in Blender's Python environment. Install or upgrade Shapely there, "
            "or set LID_LOGO_TEXT_OUTLINE_OFFSET to 0.0 to disable widening."
        ) from error

    z_values = [vertex.co.z for vertex in obj.data.vertices]
    z0 = min(z_values)
    z1 = max(z_values)
    top_faces = []
    for face in obj.data.polygons:
        coordinates = [obj.data.vertices[index].co for index in face.vertices]
        if all(math.isclose(coordinate.z, z1, abs_tol=1e-6) for coordinate in coordinates):
            polygon = Polygon([(coordinate.x, coordinate.y) for coordinate in coordinates])
            if polygon.is_valid and polygon.area > 1e-9:
                top_faces.append(polygon)
    if not top_faces:
        raise RuntimeError(f"{obj.name} has no planar top faces to widen")

    buffered = union_all(top_faces).buffer(
        offset,
        quad_segs=8,
        join_style=BufferJoinStyle.round,
    )
    buffered = set_precision(buffered, grid_size=0.01).simplify(
        0.01, preserve_topology=True
    )
    polygons = list(buffered.geoms) if buffered.geom_type == "MultiPolygon" else [buffered]
    vertices = []
    vertex_indices = {}
    faces = []

    def vertex_index(x, y, z):
        key = (round(x, 8), round(y, 8), round(z, 8))
        if key not in vertex_indices:
            vertex_indices[key] = len(vertices)
            vertices.append((x, y, z))
        return vertex_indices[key]

    for polygon in polygons:
        for triangle in constrained_delaunay_triangles(polygon).geoms:
            coordinates = list(triangle.exterior.coords)[:-1]
            bottom = [vertex_index(x, y, z0) for x, y in coordinates]
            top = [vertex_index(x, y, z1) for x, y in coordinates]
            faces.append(tuple(reversed(bottom)))
            faces.append(tuple(top))
        for ring in (polygon.exterior, *polygon.interiors):
            coordinates = list(ring.coords)[:-1]
            for index, (x0, y0) in enumerate(coordinates):
                x1, y1 = coordinates[(index + 1) % len(coordinates)]
                faces.append(
                    (
                        vertex_index(x0, y0, z0),
                        vertex_index(x1, y1, z0),
                        vertex_index(x1, y1, z1),
                        vertex_index(x0, y0, z1),
                    )
                )

    obj.data.clear_geometry()
    obj.data.from_pydata(vertices, [], faces)
    obj.data.update()
    cleanup_mesh(obj)
    recalc_normals(obj)
    return obj


def add_text_mesh(
    name,
    body,
    size,
    max_width,
    center,
    depth,
    mirror_y=False,
    font=None,
    outline_offset=0.0,
):
    bpy.ops.object.text_add(location=center)
    text_obj = bpy.context.object
    text_obj.name = name
    curve = text_obj.data
    curve.name = name + "_Curve"
    curve.body = body
    if font is not None:
        curve.font = font
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = size
    curve.extrude = max(depth / 2.0, 0.01)
    # Vertical glyph walls leave one exact horizontal bonding plane for the
    # multicolor body; a curved font bevel can create micron-scale sloped gaps.
    curve.bevel_depth = 0.0
    curve.bevel_resolution = 0
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
    if outline_offset > 0.0:
        widen_planar_mesh_xy(text_obj, outline_offset)
    return text_obj


# ---------------------------------------------------------------------------
# VALIDATION


def rectangles_overlap(a_center, a_size, b_center, b_size, gap=0.0):
    return (
        abs(a_center[0] - b_center[0]) < (a_size[0] + b_size[0]) / 2.0 + gap
        and abs(a_center[1] - b_center[1]) < (a_size[1] + b_size[1]) / 2.0 + gap
    )


def circle_rectangle_clearance(circle_center, circle_radius, rectangle_bounds):
    """Return edge clearance from an XY circle to an axis-aligned rectangle."""
    rectangle_min_x, rectangle_max_x, rectangle_min_y, rectangle_max_y = (
        rectangle_bounds
    )
    delta_x = max(
        rectangle_min_x - circle_center[0],
        0.0,
        circle_center[0] - rectangle_max_x,
    )
    delta_y = max(
        rectangle_min_y - circle_center[1],
        0.0,
        circle_center[1] - rectangle_max_y,
    )
    return math.hypot(delta_x, delta_y) - circle_radius


def validate_configuration() -> None:
    inner_width = CASE_WIDTH - 2.0 * WALL_THICKNESS
    inner_depth = CASE_DEPTH - 2.0 * WALL_THICKNESS
    tray_width = inner_width - 2.0 * INSERT_SIDE_CLEARANCE
    tray_depth = inner_depth - 2.0 * INSERT_SIDE_CLEARANCE

    if not (
        math.isclose(BATTERY_POCKET_DEPTH, 34.5, abs_tol=1e-6)
        and math.isclose(BATTERY_POCKET_WIDTH, 13.5, abs_tol=1e-6)
        and math.isclose(BATTERY_POCKET_INSERTION_DEPTH, 21.8, abs_tol=1e-6)
    ):
        raise ValueError("Battery pockets must remain 34.5 x 13.5 x 21.8 mm")
    if not (
        BATTERY_DOOR_SLOT_SIZE == (50.0, 11.0)
        and math.isclose(BATTERY_DOOR_SLOT_DEPTH, 11.0, abs_tol=1e-6)
    ):
        raise ValueError("Battery-door pockets must remain 50 x 11 x 11 mm")
    if any(
        hold_down >= pocket
        for hold_down, pocket in zip(
            BATTERY_DOOR_LID_HOLD_DOWN_SIZE, BATTERY_DOOR_SLOT_SIZE
        )
    ):
        raise ValueError("Battery-door lid hold-down must fit inside the door outline")
    if min(WALL_THICKNESS, BASE_FLOOR_THICKNESS, TRAY_FLOOR_THICKNESS) < 2.0:
        raise ValueError("Default shell walls and all floors must remain at least 2 mm")
    if not math.isclose(
        LOWER_TRAY_INSTALLED_Z,
        BASE_FLOOR_THICKNESS,
        abs_tol=1e-6,
    ):
        raise ValueError("The installed lower tray must rest on top of the base floor")
    hinge_segments = sorted(
        (*HINGE_BASE_SEGMENTS, *HINGE_LID_SEGMENTS),
        key=lambda segment: segment[0],
    )
    minimum_hinge_axial_gap = min(
        following[0] - preceding[1] for preceding, following in pairwise(hinge_segments)
    )
    if minimum_hinge_axial_gap < 2.0 * HINGE_RIM_RELIEF_AXIAL_CLEARANCE + 0.1:
        raise ValueError("Alternating hinge segments need clearance between barrels")
    if HINGE_RIM_RELIEF_RADIAL_CLEARANCE < LID_LATCH_LIP_DRAW + 0.1:
        raise ValueError("Hinge rim relief must accommodate the full lid take-up")
    base_hinge_bore_probe_diameter = HINGE_BASE_HOLE_DIAMETER - 2.0 * (
        HINGE_BORE_VALIDATION_RADIAL_CLEARANCE
    )
    lid_receiver_probe_diameter = HINGE_LID_RECEIVER_DIAMETER - 2.0 * (
        HINGE_BORE_VALIDATION_RADIAL_CLEARANCE
    )
    if not (
        0.0 < HINGE_BORE_VALIDATION_RADIAL_CLEARANCE <= 0.01
        and base_hinge_bore_probe_diameter > HINGE_ROD_DIAMETER
        and lid_receiver_probe_diameter > HINGE_ROD_DIAMETER
    ):
        raise ValueError("Hinge rod clearances must remain positive and near-nominal")
    if not (
        HINGE_ROD_DIAMETER < HINGE_LID_SLOT_WIDTH < HINGE_LID_RECEIVER_DIAMETER
    ):
        raise ValueError(
            "Lid hinge slot must clear the rod but remain narrower than its receiver"
        )
    if not math.isclose(HINGE_LID_SLOT_TILT_DEGREES, 0.0, abs_tol=1e-6):
        raise ValueError("Lid hinge slot must remain parallel to the lid plate")
    if not (
        0.0
        < HINGE_LID_PRE_RELEASE_BLOCK_ANGLE_DEGREES
        < HINGE_LID_RELEASE_ANGLE_DEGREES
        <= HINGE_OPEN_SWEEP_MAX_ANGLE_DEGREES
    ):
        raise ValueError("Hinge block, release, and sweep angles are inconsistent")
    blocked_escape_direction = (
        HINGE_LID_PRE_RELEASE_BLOCK_ANGLE_DEGREES
        - HINGE_LID_SLOT_TILT_DEGREES
    )
    release_escape_direction = (
        HINGE_LID_RELEASE_ANGLE_DEGREES - HINGE_LID_SLOT_TILT_DEGREES
    )
    if not 60.0 <= blocked_escape_direction < release_escape_direction <= 75.0:
        raise ValueError("Hinge slot/release angles no longer use the proven base stop")
    if not 1.0 <= HINGE_LID_PRE_RELEASE_SWEEP_STEP_DEGREES <= 5.0:
        raise ValueError("Pre-release hinge sweep must be sampled every 1-5 degrees")
    if HINGE_LID_RELEASE_PATH_SAMPLES < 17:
        raise ValueError("Hinge release validation needs at least 17 path samples")
    if not 1.0 <= HINGE_OPEN_SWEEP_STEP_DEGREES <= 2.0:
        raise ValueError("Hinge opening sweep must be sampled every 1-2 degrees")
    left_base_outer_face = HINGE_BASE_SEGMENTS[0][0]
    right_base_outer_face = HINGE_BASE_SEGMENTS[-1][1]
    left_stop_inner_face = (
        left_base_outer_face - HINGE_LID_END_STOP_BASE_CLEARANCE
    )
    right_stop_inner_face = (
        right_base_outer_face + HINGE_LID_END_STOP_BASE_CLEARANCE
    )
    rod_end_clearances = (
        HINGE_ROD_X0 - left_stop_inner_face,
        right_stop_inner_face - HINGE_ROD_X1,
    )
    if min(rod_end_clearances) < 0.5:
        raise ValueError("Hinge rod needs at least 0.5 mm clearance from each lid stop")
    if not 0.0 < HINGE_ROD_RELEASE_AXIAL_VALIDATION_INSET < min(
        rod_end_clearances
    ):
        raise ValueError("Hinge release axial validation inset is invalid")
    if HINGE_LID_END_STOP_DIAMETER < HINGE_ROD_DIAMETER + 1.0:
        raise ValueError("Lid hinge end stops need at least 0.5 mm radial rod coverage")
    end_stop_base_wall_clearance = (
        HINGE_AXIS_Y
        - CASE_DEPTH / 2.0
        - HINGE_LID_END_STOP_DIAMETER / 2.0
    )
    if end_stop_base_wall_clearance < 0.5:
        raise ValueError("Lid hinge end stops sit too close to the base rear wall")
    if HINGE_ROD_PATH_AXIAL_CLEARANCE < HINGE_RIM_RELIEF_AXIAL_CLEARANCE:
        raise ValueError("Lid rim relief must cover the complete hinge rod path")
    hinge_gusset_run = HINGE_BASE_GUSSET_TANGENT_Y - HINGE_BASE_GUSSET_ROOT_Y
    hinge_gusset_rise = HINGE_BASE_GUSSET_TANGENT_Z - HINGE_BASE_GUSSET_ROOT_Z
    hinge_gusset_overhang = math.degrees(
        math.atan2(hinge_gusset_run, hinge_gusset_rise)
    )
    if hinge_gusset_overhang > HINGE_BASE_GUSSET_MAX_OVERHANG_DEGREES + 1e-6:
        raise ValueError("Base hinge gusset exceeds the configured printable overhang")
    if not 0.1 <= HINGE_BASE_GUSSET_WALL_OVERLAP < WALL_THICKNESS:
        raise ValueError("Base hinge gusset needs a bounded positive rear-wall overlap")
    if HINGE_BASE_GUSSET_ROOT_Y < CASE_DEPTH / 2.0 - WALL_THICKNESS:
        raise ValueError("Base hinge gusset intrudes into the locked internal depth")
    if not BASE_FLOOR_THICKNESS < HINGE_BASE_GUSSET_ROOT_Z:
        raise ValueError("Base hinge gusset root must remain above the case floor")
    if not (
        HINGE_BASE_GUSSET_TANGENT_Z
        < BASE_HEIGHT - HINGE_BASE_HOLE_DIAMETER / 2.0
    ):
        raise ValueError("Base hinge gusset must remain below the rod bore")

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
    for index, center in enumerate(BATTERY_DOOR_SLOT_CENTERS):
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
        for other in BATTERY_DOOR_SLOT_CENTERS[index + 1 :]:
            if rectangles_overlap(
                center, door_slot_size, other, door_slot_size, gap=2.0
            ):
                raise ValueError("Battery-cage-door slots need a 2 mm TPU web")
        nearest_camera = min(bounds[2] for bounds in camera_bounds)
        if center[1] + door_slot_size[1] / 2.0 + 4.0 > nearest_camera:
            raise ValueError("Battery-cage-door slot needs 4 mm camera clearance")
        hold_down_center = (center[0], -center[1])
        if (
            abs(hold_down_center[0]) + BATTERY_DOOR_LID_HOLD_DOWN_SIZE[0] / 2.0
            > retainer_width / 2.0
            or abs(hold_down_center[1]) + BATTERY_DOOR_LID_HOLD_DOWN_SIZE[1] / 2.0
            > retainer_depth / 2.0
        ):
            raise ValueError("Battery-door lid hold-down exceeds the TPU lid pad")

    if not (
        len(MISC_COMPARTMENT_LOBE_BOUNDS) == 2
        and len(MISC_COMPARTMENT_STEP_FILLETS) == 2
    ):
        raise ValueError("Exactly two miscellaneous compartments are required")
    if MISC_COMPARTMENT_FLOOR_Z < MISC_COMPARTMENT_MIN_WEB:
        raise ValueError("Miscellaneous compartments need a 4 mm TPU floor")
    misc_lobe_specs = []
    for compartment_index, (lobe_bounds, step_fillets) in enumerate(
        zip(MISC_COMPARTMENT_LOBE_BOUNDS, MISC_COMPARTMENT_STEP_FILLETS),
        start=1,
    ):
        if not lobe_bounds:
            raise ValueError("Each miscellaneous compartment needs a cavity lobe")
        compartment_lobe_specs = []
        for x_bounds, y_bounds in lobe_bounds:
            misc_width = x_bounds[1] - x_bounds[0]
            misc_depth = y_bounds[1] - y_bounds[0]
            misc_center = (sum(x_bounds) / 2.0, sum(y_bounds) / 2.0)
            misc_size = (misc_width, misc_depth)
            misc_bounds = (*x_bounds, *y_bounds)
            compartment_lobe_specs.append((misc_center, misc_size, misc_bounds))
            if (
                abs(misc_center[0]) + misc_width / 2.0 + MISC_COMPARTMENT_MIN_WEB
                > tray_width / 2.0 + 1e-6
                or abs(misc_center[1]) + misc_depth / 2.0 + MISC_COMPARTMENT_MIN_WEB
                > tray_depth / 2.0 + 1e-6
            ):
                raise ValueError("Miscellaneous compartment weakens a TPU side wall")
            for bounds in (*camera_bounds, *hood_bounds):
                neighbor_center = (
                    (bounds[0] + bounds[1]) / 2.0,
                    (bounds[2] + bounds[3]) / 2.0,
                )
                neighbor_size = (bounds[1] - bounds[0], bounds[3] - bounds[2])
                if rectangles_overlap(
                    misc_center,
                    misc_size,
                    neighbor_center,
                    neighbor_size,
                    gap=MISC_COMPARTMENT_MIN_WEB,
                ):
                    raise ValueError(
                        "Miscellaneous compartment needs 4 mm from camera recesses"
                    )
            for center in BATTERY_CENTERS:
                if rectangles_overlap(
                    misc_center,
                    misc_size,
                    center,
                    battery_size,
                    gap=MISC_COMPARTMENT_MIN_WEB,
                ):
                    raise ValueError(
                        "Miscellaneous compartment needs 4 mm from battery pockets"
                    )
            for center in BATTERY_DOOR_SLOT_CENTERS:
                if rectangles_overlap(
                    misc_center,
                    misc_size,
                    center,
                    door_slot_size,
                    gap=MISC_COMPARTMENT_MIN_WEB,
                ):
                    raise ValueError(
                        "Miscellaneous compartment needs 4 mm from battery-door slots"
                    )

        connected_lobes = {0}
        while True:
            newly_connected = {
                candidate_index
                for connected_index in connected_lobes
                for candidate_index, candidate in enumerate(compartment_lobe_specs)
                if candidate_index not in connected_lobes
                and rectangles_overlap(
                    compartment_lobe_specs[connected_index][0],
                    compartment_lobe_specs[connected_index][1],
                    candidate[0],
                    candidate[1],
                )
            }
            if not newly_connected:
                break
            connected_lobes.update(newly_connected)
        if len(connected_lobes) != len(compartment_lobe_specs):
            raise ValueError(
                f"Miscellaneous compartment {compartment_index} is not continuous"
            )

        for fillet_x, fillet_y, fillet_radius in step_fillets:
            fillet_center = (fillet_x, fillet_y)
            if fillet_radius <= 0.0:
                raise ValueError("Miscellaneous step fillet radius must be positive")
            if (
                abs(fillet_x) + fillet_radius + MISC_COMPARTMENT_MIN_WEB
                > tray_width / 2.0 + 1e-6
                or abs(fillet_y) + fillet_radius + MISC_COMPARTMENT_MIN_WEB
                > tray_depth / 2.0 + 1e-6
            ):
                raise ValueError("Miscellaneous step fillet weakens a TPU side wall")
            if (
                sum(
                    circle_rectangle_clearance(
                        fillet_center,
                        fillet_radius,
                        lobe_spec[2],
                    )
                    <= 0.0
                    for lobe_spec in compartment_lobe_specs
                )
                < 2
            ):
                raise ValueError(
                    "Miscellaneous step fillet must blend two cavity lobes"
                )
            for bounds in (*camera_bounds, *hood_bounds):
                if (
                    circle_rectangle_clearance(
                        fillet_center,
                        fillet_radius,
                        bounds,
                    )
                    < MISC_COMPARTMENT_MIN_WEB
                ):
                    raise ValueError(
                        "Miscellaneous step fillet needs 4 mm from camera recesses"
                    )
            for center in BATTERY_CENTERS:
                battery_bounds = (
                    center[0] - battery_size[0] / 2.0,
                    center[0] + battery_size[0] / 2.0,
                    center[1] - battery_size[1] / 2.0,
                    center[1] + battery_size[1] / 2.0,
                )
                if (
                    circle_rectangle_clearance(
                        fillet_center,
                        fillet_radius,
                        battery_bounds,
                    )
                    < MISC_COMPARTMENT_MIN_WEB
                ):
                    raise ValueError(
                        "Miscellaneous step fillet needs 4 mm from battery pockets"
                    )
            for center in BATTERY_DOOR_SLOT_CENTERS:
                door_bounds = (
                    center[0] - door_slot_size[0] / 2.0,
                    center[0] + door_slot_size[0] / 2.0,
                    center[1] - door_slot_size[1] / 2.0,
                    center[1] + door_slot_size[1] / 2.0,
                )
                if (
                    circle_rectangle_clearance(
                        fillet_center,
                        fillet_radius,
                        door_bounds,
                    )
                    < MISC_COMPARTMENT_MIN_WEB
                ):
                    raise ValueError(
                        "Miscellaneous step fillet needs 4 mm from battery-door slots"
                    )

        misc_lobe_specs.append(compartment_lobe_specs)

    for first_lobe in misc_lobe_specs[0]:
        for second_lobe in misc_lobe_specs[1]:
            if rectangles_overlap(
                first_lobe[0],
                first_lobe[1],
                second_lobe[0],
                second_lobe[1],
                gap=MISC_COMPARTMENT_MIN_WEB,
            ):
                raise ValueError(
                    "Miscellaneous compartments need a 4 mm separating web"
                )

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
    battery_door_top = (
        BASE_FLOOR_THICKNESS + BATTERY_DOOR_SLOT_FLOOR_Z + BATTERY_DOOR_SIZE[2]
    )
    battery_door_pad_compression = (
        battery_door_top
        + LID_RETAINER_HEIGHT
        + BATTERY_DOOR_LID_HOLD_DOWN_EXTENSION
        - installed_lid_inner_face
    )
    if not 0.2 <= battery_door_pad_compression <= 1.5:
        raise ValueError(
            "Battery-door lid hold-down preload must remain 0.2-1.5 mm; "
            f"computed {battery_door_pad_compression:.2f} mm"
        )
    camera_button_top = BASE_FLOOR_THICKNESS + CAMERA_FLOOR_Z + CAMERA_HEIGHT
    relief_ceiling = installed_lid_inner_face - (
        LID_RETAINER_HEIGHT - LID_BUTTON_RELIEF_DEPTH
    )
    if relief_ceiling - camera_button_top < 0.3:
        raise ValueError("Lid pad button relief does not clear the shutter buttons")

    if PIVOT_MIN_WALL_THICKNESS < 2.0:
        raise ValueError("Pivot minimum wall must remain at least 2 mm")
    if PIVOT_REINFORCEMENT_MARGIN < 0.0:
        raise ValueError("Pivot reinforcement margin cannot be negative")
    maximum_mount_bore_radius = (
        max(
            LATCH_PRESS_FIT_BORE_DIAMETER,
            LATCH_RUNNING_BORE_DIAMETER,
            HANDLE_PRESS_FIT_BORE_DIAMETER,
            HANDLE_RUNNING_BORE_DIAMETER,
        )
        / 2.0
    )
    if not math.isclose(
        PIVOT_REFERENCE_MAX_BORE_RADIUS,
        maximum_mount_bore_radius,
        abs_tol=1e-6,
    ):
        raise ValueError("Pivot reference bore radius is stale")
    mount_lower_chord_wall = (
        PIVOT_MOUNT_OUTER_RADIUS / math.sqrt(2.0) - maximum_mount_bore_radius
    )
    mount_roof_wall = (
        PIVOT_MOUNT_OUTER_RADIUS - math.sqrt(2.0) * maximum_mount_bore_radius
    )
    if min(mount_lower_chord_wall, mount_roof_wall) < PIVOT_MIN_WALL_THICKNESS:
        raise ValueError(
            "Support-free mount bosses violate the configured pivot minimum wall"
        )
    for name, profile, pivot_y, pivot_z in (
        (
            "latch",
            LATCH_BASE_EAR_PROFILE_YZ,
            LATCH_BASE_PIVOT_Y,
            LATCH_BASE_PIVOT_Z,
        ),
        (
            "handle",
            HANDLE_BASE_EAR_PROFILE_YZ,
            HANDLE_PIVOT_Y,
            HANDLE_PIVOT_Z,
        ),
    ):
        lower_anchor_y, lower_anchor_z = profile[0]
        bottom_y, bottom_z = profile[1]
        lower_rise = bottom_z - lower_anchor_z
        lower_outset = abs(bottom_y - lower_anchor_y)
        if lower_rise + 1e-6 < lower_outset:
            raise ValueError(
                f"{name.title()} mount lower web exceeds a 45-degree printable slope"
            )
        if not math.isclose(bottom_y, pivot_y, abs_tol=1e-6):
            raise ValueError(f"{name.title()} mount ramp misses its pivot centerline")
        if not math.isclose(
            bottom_z,
            pivot_z - PIVOT_MOUNT_OUTER_RADIUS,
            abs_tol=1e-6,
        ):
            raise ValueError(f"{name.title()} mount ramp misses its pivot boss")
    lever_fixed_wall = (
        LATCH_LEVER_FIXED_BOSS_RADIUS
        - LATCH_FIXED_M3_CLEARANCE_DIAMETER / 2.0
    )
    lever_link_wall = LATCH_LEVER_LINK_BOSS_RADIUS - LATCH_RUNNING_BORE_DIAMETER / 2.0
    hook_link_wall = LATCH_HOOK_LINK_BOSS_RADIUS - LATCH_PRESS_FIT_BORE_DIAMETER / 2.0
    detent_to_bore_wall = (
        math.hypot(*LATCH_DETENT_LOCAL_YZ)
        - LATCH_DETENT_DIMPLE_RADIUS
        - LATCH_FIXED_M3_CLEARANCE_DIAMETER / 2.0
    )
    if (
        min(
            lever_fixed_wall,
            lever_link_wall,
            hook_link_wall,
            detent_to_bore_wall,
        )
        < PIVOT_MIN_WALL_THICKNESS
    ):
        raise ValueError("Latch parts violate the configured pivot minimum wall")
    link_center_distance = math.hypot(*LATCH_LINK_PIVOT_LOCAL_YZ)
    relief_cutter_radius = (
        LATCH_LEVER_FIXED_BOSS_RADIUS + LATCH_REINFORCEMENT_RUNNING_CLEARANCE
    )
    relief_sample_chord = (
        2.0
        * link_center_distance
        * math.sin(math.radians(LATCH_REINFORCEMENT_RELIEF_STEP_DEGREES) / 2.0)
    )
    maximum_covered_chord = 2.0 * math.sqrt(
        relief_cutter_radius * relief_cutter_radius
        - LATCH_LEVER_FIXED_BOSS_RADIUS * LATCH_LEVER_FIXED_BOSS_RADIUS
    )
    if relief_sample_chord > maximum_covered_chord:
        raise ValueError("Latch reinforcement sweep relief is sampled too coarsely")
    hook_ring_clearance_from_fixed_relief = (
        link_center_distance - relief_cutter_radius - LATCH_HOOK_LINK_BOSS_RADIUS
    )
    if hook_ring_clearance_from_fixed_relief < 0.5:
        raise ValueError("Fixed-boss sweep relief weakens the hook pivot ring")

    press_fit_interference = (
        LATCH_LINK_ROD_DIAMETER - LATCH_PRESS_FIT_BORE_DIAMETER
    )
    running_clearance = (
        LATCH_RUNNING_BORE_DIAMETER - LATCH_LINK_ROD_DIAMETER
    )
    if not 0.05 <= press_fit_interference <= 0.20:
        raise ValueError("Latch retaining bores need 0.05-0.20 mm rod interference")
    if running_clearance < 0.4:
        raise ValueError("Latch lever pivots need at least 0.4 mm running clearance")
    if LATCH_BASE_EAR_AXIAL_CLEARANCE < 0.2:
        raise ValueError("Latch lever needs at least 0.2 mm clearance at each case ear")
    detent_interference = LATCH_DETENT_BOSS_PROTRUSION - LATCH_BASE_EAR_AXIAL_CLEARANCE
    detent_closed_clearance = LATCH_DETENT_DIMPLE_DEPTH - detent_interference
    if detent_interference < LATCH_DETENT_MIN_INTERFERENCE:
        raise ValueError("Latch snap detent has too little positive interference")
    if detent_closed_clearance < LATCH_BASE_EAR_AXIAL_CLEARANCE + 0.05:
        raise ValueError("Latch snap dimples do not clear the full axial play")
    if detent_closed_clearance > 0.75:
        raise ValueError("Latch snap dimples are too loose at the centered pose")
    if not 0.1 <= LATCH_DETENT_SWEEP_STEP_DEGREES <= 0.25:
        raise ValueError("Latch detent validation needs 0.1-0.25 degree sampling")
    if LATCH_DETENT_MIN_PEAK_VOLUME < 0.05:
        raise ValueError("Latch detent validation needs a meaningful release bump")
    if LATCH_DETENT_RELEASE_RESIDUAL_VOLUME_LIMIT > 0.0001:
        raise ValueError("Latch detent release residual limit is too permissive")
    if LATCH_LINK_ROD_LENGTH < LATCH_WIDTH - 0.1:
        raise ValueError("Latch link rod does not span both hook cheeks")
    fixed_m3_clearance = (
        LATCH_FIXED_M3_CLEARANCE_DIAMETER
        - LATCH_FIXED_M3_NOMINAL_DIAMETER
    )
    if fixed_m3_clearance < 0.4:
        raise ValueError("Latch fixed pivots need an easy-running M3 clearance")
    countersink_diametral_clearance = (
        LATCH_FIXED_M3_COUNTERSINK_DIAMETER
        - LATCH_FIXED_M3_NOMINAL_HEAD_DIAMETER
    )
    if countersink_diametral_clearance < 0.4:
        raise ValueError("Latch M3 countersinks do not fully contain the screw heads")
    expected_countersink_depth = (
        LATCH_FIXED_M3_COUNTERSINK_DIAMETER
        - LATCH_FIXED_M3_CLEARANCE_DIAMETER
    ) / 2.0
    if not math.isclose(
        LATCH_FIXED_M3_COUNTERSINK_DEPTH,
        expected_countersink_depth,
        abs_tol=1e-6,
    ):
        raise ValueError("Latch fixed-pivot countersink is not 90 degrees")
    countersink_seat_inset = countersink_diametral_clearance / 2.0
    nut_diametral_clearance = (
        LATCH_FIXED_M3_NUT_ACROSS_FLATS
        - LATCH_FIXED_M3_NOMINAL_NUT_ACROSS_FLATS
    )
    nut_depth_clearance = (
        LATCH_FIXED_M3_NUT_DEPTH
        - LATCH_FIXED_M3_NOMINAL_NUT_THICKNESS
    )
    if nut_diametral_clearance < 0.2 or nut_depth_clearance < 0.2:
        raise ValueError("Latch captive M3 nut recess is too tight")
    countersink_floor = (
        LATCH_PROTECTOR_BASE_WIDTH - LATCH_FIXED_M3_COUNTERSINK_DEPTH
    )
    nut_recess_floor = LATCH_PROTECTOR_BASE_WIDTH - LATCH_FIXED_M3_NUT_DEPTH
    if min(countersink_floor, nut_recess_floor) < LATCH_FIXED_M3_MIN_RECESS_FLOOR:
        raise ValueError("Latch guard recesses leave too little material behind them")
    fixed_m3_thread_engagement = (
        LATCH_FIXED_M3_BOLT_LENGTH
        + countersink_seat_inset
        - (LATCH_FIXED_M3_GUARD_SPAN - LATCH_FIXED_M3_NUT_DEPTH)
    )
    fixed_m3_tip_protrusion = (
        LATCH_FIXED_M3_BOLT_LENGTH
        + countersink_seat_inset
        - LATCH_FIXED_M3_GUARD_SPAN
    )
    if fixed_m3_thread_engagement < LATCH_FIXED_M3_MIN_THREAD_ENGAGEMENT:
        raise ValueError("Latch fixed-pivot M3 screw does not fully engage its nut")
    if not 0.0 <= fixed_m3_tip_protrusion <= LATCH_FIXED_M3_MAX_TIP_PROTRUSION:
        raise ValueError("Latch fixed-pivot M3 screw protrusion is unsafe")
    link_axial_clearance = (
        2.0 * LATCH_HOOK_CHEEK_INNER_X - LATCH_LEVER_LINK_TONGUE_WIDTH
    ) / 2.0
    if link_axial_clearance < 0.2 - 1e-6:
        raise ValueError("Latch lever tongue needs 0.2 mm clearance at each hook cheek")
    if LATCH_HOOK_CHEEK_WIDTH < PIVOT_MIN_WALL_THICKNESS:
        raise ValueError("Latch hook cheeks are thinner than the configured minimum")
    if not 0.5 <= LATCH_SWEEP_STEP_DEGREES <= 5.0:
        raise ValueError("Latch sweep validation step must remain 0.5-5 degrees")
    if not 0.0 < LATCH_SWEEP_RESIDUAL_VOLUME_LIMIT <= 0.1:
        raise ValueError("Latch sweep residual-volume limit must be at most 0.1 mm3")
    if not (
        LATCH_SWEEP_RESIDUAL_VOLUME_LIMIT
        < LATCH_AXIAL_CONTACT_RESIDUAL_VOLUME_LIMIT
        <= 0.001
    ):
        raise ValueError("Latch axial-contact residual limit must be at most 0.001 mm3")
    lever_lower_z = LATCH_BASE_PIVOT_Z - 38.413704
    lever_upper_z = LATCH_BASE_PIVOT_Z + 3.197739
    if lever_lower_z < 2.0 or lever_upper_z > BASE_HEIGHT - 5.0:
        raise ValueError("Closed source latch lever no longer fits the base front")

    if not 0.15 <= LID_LATCH_LIP_DRAW <= 0.40:
        raise ValueError("Lid lip needs 0.15-0.40 mm of over-center draw")
    if not math.isclose(
        LID_LATCH_LIP_DRAW,
        GASKET_HEIGHT - GASKET_CHANNEL_DEPTH,
        abs_tol=1e-6,
    ):
        raise ValueError("Latch draw must equal the unloaded gasket protrusion")
    flare_height = LID_FLANGE_EDGE_START_Z - LID_FLANGE_FLARE_START_Z
    if LID_FLANGE_OUTSET > flare_height + 1e-6:
        raise ValueError("Lid rim flare exceeds a 45-degree self-supporting slope")
    if LID_LATCH_RIM_EDGE_THICKNESS < 3.0:
        raise ValueError("Lid skirt needs at least a 3 mm loaded tip")
    skirt_radial_tip = CASE_DEPTH / 2.0 + LID_FLANGE_OUTSET - (CASE_DEPTH - 0.8) / 2.0
    if skirt_radial_tip < 4.0:
        raise ValueError("Lid skirt tip needs at least 4 mm radial thickness")
    trough_side_clearance = (LID_LATCH_TROUGH_WIDTH - LATCH_WIDTH) / 2.0
    if not 0.35 <= trough_side_clearance <= 0.8:
        raise ValueError("Latch trough needs 0.35-0.8 mm clearance per hook side")
    if LID_LATCH_TROUGH_SHOULDER_RISE < 0.8:
        raise ValueError("Latch trough shoulders are too low to retain the hook")
    if LID_LATCH_RECESS_BACK_WALL < 4.0:
        raise ValueError("Latch recess leaves too little skirt behind the lip")
    if LID_LATCH_RECESS_BACK_WALL >= skirt_radial_tip:
        raise ValueError("Latch recess does not cut into the lid skirt")
    if LID_LATCH_CAPTURE_RAIL_RADIUS < 1.2:
        raise ValueError("Latch capture rail needs at least a 2.4 mm diameter")
    if not 5.5 <= LID_LATCH_CAPTURE_RAIL_CENTER_OUTSET <= 6.5:
        raise ValueError("Latch capture rail center needs a 5.5-6.5 mm rim outset")
    if LID_LATCH_CAPTURE_WEB_THICKNESS < 1.2:
        raise ValueError("Latch capture rail web is too thin")
    if LID_LATCH_LOAD_LEDGE_THICKNESS < 2.4:
        raise ValueError("Latch load ledge needs at least 2.4 mm thickness")
    if not 0.1 <= LID_LATCH_LOAD_LEDGE_RAIL_EMBED <= 0.5:
        raise ValueError("Latch rail needs 0.1-0.5 mm ledge-center embed")
    if LID_LATCH_LOAD_LEDGE_BACK_OVERLAP < 1.0:
        raise ValueError("Latch load ledge needs at least 1 mm back-wall overlap")
    if LID_LATCH_LOAD_LEDGE_AXIAL_OVERLAP < LID_LATCH_CAPTURE_RAIL_END_OVERLAP:
        raise ValueError("Latch load ledge must reach both rail-end supports")
    if not math.isclose(
        LID_LATCH_LOAD_LEDGE_CONTACT_Z,
        LID_LATCH_CAPTURE_RAIL_CENTER_Z - 0.2,
        abs_tol=1e-6,
    ):
        raise ValueError("Latch rail must be embedded through the load-ledge edge")
    if LATCH_CAPTURE_HOOK_WALL < PIVOT_MIN_WALL_THICKNESS:
        raise ValueError("Latch capture hook wall violates the minimum-wall rule")
    if not 0.08 <= LATCH_CAPTURE_RAIL_PATH_CLEARANCE <= 0.30:
        raise ValueError("Latch capture rail path needs 0.08-0.30 mm clearance")
    capture_slot_height = 2.0 * (
        LID_LATCH_CAPTURE_RAIL_RADIUS + LATCH_CAPTURE_RAIL_PATH_CLEARANCE
    )
    capture_rail_diameter = 2.0 * LID_LATCH_CAPTURE_RAIL_RADIUS
    if capture_slot_height - capture_rail_diameter > 0.6:
        raise ValueError("Latch capture path leaves excessive rail clearance")
    rail_bottom_z = LID_LATCH_CAPTURE_RAIL_CENTER_Z - LID_LATCH_CAPTURE_RAIL_RADIUS
    if rail_bottom_z < LID_FLANGE_EDGE_START_Z + 1.0:
        raise ValueError("Latch capture rail lacks a printable lower support rise")
    if LID_LATCH_CAPTURE_BAY_Z0 > rail_bottom_z:
        raise ValueError("Latch capture bay does not open below the horizontal rail")
    if LID_LATCH_CAPTURE_RAIL_CENTER_Y - LID_LATCH_CAPTURE_RAIL_RADIUS <= (
        (CASE_DEPTH - 0.8) / 2.0 + LID_LATCH_RECESS_BACK_WALL
    ):
        raise ValueError("Latch capture rail does not stand proud of its back wall")
    if LID_LATCH_TROUGH_WIDTH > 25.0:
        raise ValueError("Latch capture rail exceeds the printable bridge span")
    if LID_LATCH_TROUGH_SHOULDER_WIDTH < 4.0:
        raise ValueError("Latch capture rail side towers are too thin")
    if not 1.0 <= LATCH_CAPTURE_CLEARANCE_SWEEP_STEP_DEGREES <= 3.0:
        raise ValueError("Latch rail-clearance sweep step must remain 1-3 degrees")
    if not (
        LATCH_CAPTURE_FULL_RELEASE_ANGLE
        < LATCH_DETENT_RELEASE_ANGLE
        < LATCH_CAPTURE_RELEASE_GUARD_ANGLE
        < LATCH_LEVER_CLOSED_ANGLE
    ):
        raise ValueError("Latch capture guard/release angles are out of sequence")
    if LATCH_CAPTURE_UPPER_ARM_THICKNESS < 3.2:
        raise ValueError("Latch upper capture arm needs at least 3.2 mm thickness")
    if LATCH_CAPTURE_NUB_RADIUS < 1.4:
        raise ValueError("Latch behind-rail boss needs at least a 2.8 mm diameter")
    if LATCH_CAPTURE_NUB_ROOT_BOSS_RADIUS < LATCH_CAPTURE_NUB_RADIUS + 0.3:
        raise ValueError("Latch behind-rail boss needs a larger rounded root")
    if LATCH_CAPTURE_ROOT_BOSS_LEDGE_CLEARANCE < 0.05:
        raise ValueError("Latch root boss must clear the preloaded flat ledge")
    if LATCH_CAPTURE_NUB_AXIAL_WIDTH < 16.0:
        raise ValueError("Latch behind-rail boss needs at least 16 mm axial width")
    if LATCH_CAPTURE_NUB_RAIL_VERTICAL_OFFSET >= LATCH_CAPTURE_NUB_RAIL_CENTER_DISTANCE:
        raise ValueError("Latch retention boss cannot reach behind the lid rail")
    if not 0.20 <= LATCH_CAPTURE_NUB_LEDGE_CLEARANCE <= 0.35:
        raise ValueError("Round retention boss needs 0.20-0.35 mm ledge clearance")
    if LATCH_CAPTURE_FLAT_PAD_AXIAL_WIDTH < 18.0:
        raise ValueError("Latch downward-bearing pad needs at least 18 mm width")
    if LATCH_CAPTURE_FLAT_PAD_AXIAL_WIDTH > LID_LATCH_TROUGH_WIDTH - 1.0:
        raise ValueError("Latch downward-bearing pad lacks side clearance")
    if LATCH_CAPTURE_FLAT_PAD_CASEWARD_LENGTH < 1.2:
        raise ValueError("Latch downward-bearing pad is too short")
    if LATCH_CAPTURE_FLAT_PAD_HEIGHT < 2.8:
        raise ValueError("Latch downward-bearing pad is too thin at its root")
    if not 0.10 <= LATCH_CAPTURE_FLAT_PAD_SEATED_CLEARANCE < LID_LATCH_LIP_DRAW:
        raise ValueError("Latch flat-pad seated clearance cannot create lid preload")
    if (
        LATCH_CAPTURE_NUB_LEDGE_CLEARANCE
        < LATCH_CAPTURE_FLAT_PAD_SEATED_CLEARANCE + 0.05
    ):
        raise ValueError("Round boss would carry load before the flat latch pad")
    if LATCH_MAX_CAPTURE_FREE_LIFT - LATCH_CAPTURE_FLAT_PAD_SEATED_CLEARANCE < 0.005:
        raise ValueError("Flat latch pad no longer captures the attempted lid lift")
    if LID_LATCH_LIP_DRAW - LATCH_CAPTURE_FLAT_PAD_SEATED_CLEARANCE < 0.08:
        raise ValueError("Flat latch pad provides too little gasket preload")
    nub_recess_depth = (
        LID_LATCH_CAPTURE_RAIL_CENTER_Y
        - LID_LATCH_CAPTURE_RAIL_RADIUS
        - ((CASE_DEPTH - 0.8) / 2.0 + LID_LATCH_RECESS_BACK_WALL)
    )
    nub_release_depth = (
        2.0 * LATCH_CAPTURE_NUB_RADIUS
        + LATCH_CAPTURE_NUB_RAIL_CLEARANCE
        + 2.0 * LATCH_CAPTURE_NUB_LEDGE_CLEARANCE
    )
    if nub_recess_depth < nub_release_depth:
        raise ValueError("Lid recess is too shallow for the round TPU boss")
    release_pad_bottom_z = min(
        hook_local_yz_in_installed(
            LATCH_CAPTURE_FULL_RELEASE_ANGLE,
            *installed_yz_in_hook_local(
                LATCH_LEVER_CLOSED_ANGLE,
                pad_y,
                LATCH_CAPTURE_FLAT_PAD_BOTTOM_INSTALLED_Z,
            ),
        )[1]
        for pad_y in (
            LATCH_CAPTURE_FLAT_PAD_OUTWARD_INSTALLED_Y,
            LATCH_CAPTURE_FLAT_PAD_CASEWARD_INSTALLED_Y,
        )
    )
    released_ledge_z = LATCH_CAPTURE_LOAD_LEDGE_INSTALLED_Z + LID_LATCH_LIP_DRAW
    if release_pad_bottom_z - released_ledge_z < 0.02:
        raise ValueError("Flat latch pad does not lift clear of the load ledge")
    if LATCH_CAPTURE_OUTWARD_PEEL_TRAVEL <= LATCH_CAPTURE_RAIL_PATH_CLEARANCE:
        raise ValueError("Latch peel validation travel must exceed rail clearance")
    protector_inner_offset = (
        LATCH_BASE_EAR_CENTER_OFFSET_X
        + LATCH_PROTECTOR_AXIAL_OUTWARD_SHIFT
        - LATCH_PROTECTOR_BASE_WIDTH / 2.0
    )
    moving_latch_outer_offset = LATCH_WIDTH / 2.0 + LATCH_BASE_EAR_AXIAL_CLEARANCE
    if protector_inner_offset < moving_latch_outer_offset - 1e-6:
        raise ValueError("Base latch protectors enter the moving latch envelope")
    if LATCH_PROTECTOR_BASE_WIDTH < 4.0:
        raise ValueError("Base latch protectors need at least 4 mm thickness")
    protector_ramp_run = abs(LATCH_PROTECTOR_FRONT_Y - LATCH_PROTECTOR_BODY_Y)
    protector_ramp_rise = LATCH_PROTECTOR_FRONT_LOWER_Z - LATCH_PROTECTOR_ROOT_Z
    if protector_ramp_rise + 1e-6 < protector_ramp_run:
        raise ValueError("Base latch protector lower ramp exceeds a 45-degree overhang")
    lever_front_y = LATCH_BASE_PIVOT_Y - LATCH_LEVER_PRINT_SIZE[1] / 2.0
    if LATCH_PROTECTOR_FRONT_Y > lever_front_y - 1.0:
        raise ValueError("Base latch protectors do not stand proud of the lever")

    if HANDLE_HARDWARE_MODE not in {"ROD", "M4"}:
        raise ValueError("HANDLE_HARDWARE_MODE must be ROD or M4")
    handle_arm_width = (HANDLE_BAR_OUTER_WIDTH - HANDLE_BAR_INNER_WIDTH) / 2.0
    handle_arm_inner_edge = HANDLE_BAR_INNER_WIDTH / 2.0
    handle_arm_outer_edge = HANDLE_BAR_OUTER_WIDTH / 2.0
    handle_lug_inner_edge = HANDLE_BASE_LUG_X - HANDLE_BASE_LUG_WIDTH / 2.0
    handle_lug_outer_edge = HANDLE_BASE_LUG_X + HANDLE_BASE_LUG_WIDTH / 2.0
    if not math.isclose(HANDLE_BASE_LUG_X, HANDLE_PIVOT_X, abs_tol=1e-6):
        raise ValueError("Handle fixed lugs must align with the forked pivot axes")
    if (
        handle_lug_inner_edge < handle_arm_inner_edge
        or handle_lug_outer_edge > handle_arm_outer_edge
    ):
        raise ValueError("Handle fixed lugs must remain inside the forked arms")
    handle_fork_cheek_thickness = (
        handle_arm_width - HANDLE_BASE_LUG_WIDTH - 2.0 * HANDLE_AXIAL_CLEARANCE
    ) / 2.0
    if handle_fork_cheek_thickness < PIVOT_MIN_WALL_THICKNESS:
        raise ValueError("Handle pivot forks violate the configured pivot minimum wall")
    if HANDLE_BAR_INNER_WIDTH < HANDLE_MIN_USABLE_GRIP_WIDTH:
        raise ValueError("Handle needs its specified unobstructed adult-hand width")
    handle_ear_sweep_radius = max(
        math.hypot(y - HANDLE_PIVOT_Y, z - HANDLE_PIVOT_Z)
        for y, z in HANDLE_BASE_EAR_PROFILE_YZ
    )
    if HANDLE_FORK_RELIEF_LENGTH / 2.0 < handle_ear_sweep_radius + 0.5:
        raise ValueError("Handle fork relief does not clear the fixed ear sweep")
    if HANDLE_HARDWARE_MODE == "ROD":
        handle_interference = HANDLE_ROD_DIAMETER - HANDLE_PRESS_FIT_BORE_DIAMETER
        if not 0.05 <= handle_interference <= 0.20:
            raise ValueError("Handle fixed lugs need 0.05-0.20 mm rod interference")
    handle_running_clearance = HANDLE_RUNNING_BORE_DIAMETER - HANDLE_ROD_DIAMETER
    if handle_running_clearance < 0.4:
        raise ValueError("Handle bar needs at least 0.4 mm running clearance")
    handle_pivot_lower_chord_wall = (
        HANDLE_PIVOT_BOSS_RADIUS / math.sqrt(2.0) - HANDLE_RUNNING_BORE_DIAMETER / 2.0
    )
    handle_pivot_roof_wall = (
        HANDLE_PIVOT_BOSS_RADIUS - math.sqrt(2.0) * HANDLE_RUNNING_BORE_DIAMETER / 2.0
    )
    if (
        min(handle_pivot_lower_chord_wall, handle_pivot_roof_wall)
        < PIVOT_MIN_WALL_THICKNESS
    ):
        raise ValueError("Handle bar pivot violates the configured minimum wall")
    assembled_front_center_z = LATCH_LID_INSTALLED_Z / 2.0
    if not math.isclose(HANDLE_PIVOT_Z, assembled_front_center_z, abs_tol=1e-6):
        raise ValueError("Handle pivot must stay vertically centered on the case front")
    handle_lower_z = HANDLE_PIVOT_Z - HANDLE_BAR_DROP
    if handle_lower_z < 3.0:
        raise ValueError("Folded handle must remain above the case floor")
    folded_handle_face_gap = -CASE_DEPTH / 2.0 - (
        HANDLE_PIVOT_Y + HANDLE_BAR_THICKNESS / 2.0
    )
    if folded_handle_face_gap < HANDLE_FOLDED_FACE_CLEARANCE:
        raise ValueError(
            "Folded handle intersects or sits too close to the case face; "
            f"computed {folded_handle_face_gap:.2f} mm"
        )
    if not 0.5 <= HANDLE_SWEEP_STEP_DEGREES <= 5.0:
        raise ValueError("Handle sweep validation step must remain 0.5-5 degrees")
    if not 0.0 < HANDLE_SWEEP_RESIDUAL_VOLUME_LIMIT <= 0.001:
        raise ValueError("Handle sweep residual-volume limit is too permissive")
    handle_pivot_outset = -CASE_DEPTH / 2.0 - HANDLE_PIVOT_Y
    handle_raised_finger_gap = handle_pivot_outset + HANDLE_BAR_DROP - HANDLE_BAR_DEPTH
    if handle_raised_finger_gap < HANDLE_RAISED_FINGER_CLEARANCE:
        raise ValueError(
            "Raised handle needs its specified adult-finger clearance; "
            f"computed {handle_raised_finger_gap:.2f} mm"
        )
    latch_mount_half_width = (
        LATCH_WIDTH / 2.0 + LATCH_BASE_EAR_AXIAL_CLEARANCE + LATCH_BASE_EAR_WIDTH
    )
    latch_mount_inner_x = min(abs(x) for x in LATCH_X_CENTERS) - latch_mount_half_width
    latch_lever_inner_x = min(abs(x) for x in LATCH_X_CENTERS) - LATCH_WIDTH / 2.0
    latch_outer_x = max(abs(x) for x in LATCH_X_CENTERS) + latch_mount_half_width
    handle_outer_x = HANDLE_BAR_OUTER_WIDTH / 2.0
    latch_handle_clearance = latch_lever_inner_x - handle_outer_x
    if latch_handle_clearance < LATCH_FINGER_ACCESS_CLEARANCE:
        raise ValueError(
            "Folded/swinging handle enters the latch finger-access zone: "
            f"computed {latch_handle_clearance:.2f} mm"
        )
    latch_mount_handle_clearance = latch_mount_inner_x - handle_outer_x
    if latch_mount_handle_clearance < LATCH_MOUNT_HANDLE_CLEARANCE:
        raise ValueError(
            "Handle sits too close to the integrated latch mount: "
            f"computed {latch_mount_handle_clearance:.2f} mm"
        )
    latch_case_edge_clearance = CASE_WIDTH / 2.0 - latch_outer_x
    if latch_case_edge_clearance < 4.0:
        raise ValueError("Exact latch needs at least 4 mm clearance from the case edge")
    handle_lug_outer_x = HANDLE_BASE_LUG_X + HANDLE_BASE_LUG_WIDTH / 2.0
    if latch_lever_inner_x - handle_lug_outer_x < LATCH_FINGER_ACCESS_CLEARANCE:
        raise ValueError("Handle bases enter the latch finger-access zones")

    # Conservative analytic envelopes include every projection on each part.
    base_print_width = max(
        CASE_WIDTH + 7.8,
        2.0 * (HANDLE_BASE_LUG_X + HANDLE_BASE_LUG_WIDTH / 2.0),
    )
    mount_front = min(
        min(point[0] for point in LATCH_BASE_EAR_PROFILE_YZ),
        min(point[0] for point in HANDLE_BASE_EAR_PROFILE_YZ),
        LATCH_PROTECTOR_FRONT_Y,
    )
    hinge_back = HINGE_AXIS_Y + HINGE_OUTER_DIAMETER / 2.0
    base_print_depth = hinge_back - mount_front
    lid_print_width = CASE_WIDTH + 2.0 * LID_FLANGE_OUTSET
    lid_front = (
        LID_LATCH_CAPTURE_RAIL_CENTER_Y
        + LID_LATCH_CAPTURE_RAIL_RADIUS
        + LID_LATCH_CAPTURE_TOWER_OUTSET
    )
    lid_back = -HINGE_AXIS_Y - HINGE_OUTER_DIAMETER / 2.0
    lid_print_depth = lid_front - lid_back
    for part, dimensions in (
        ("base", (base_print_width, base_print_depth)),
        ("lid", (lid_print_width, lid_print_depth)),
        ("lower TPU tray", (tray_width, tray_depth)),
        ("lid retainer", (tray_width, tray_depth)),
        ("gasket", (CASE_WIDTH - 3.8, CASE_DEPTH - 3.8)),
        ("Pelican latch lever", LATCH_LEVER_PRINT_SIZE[:2]),
        ("Pelican latch hook", LATCH_HOOK_PRINT_SIZE[:2]),
        ("pivoting handle bar", (HANDLE_BAR_OUTER_WIDTH, HANDLE_BAR_DROP + 2.0)),
        ("hinge pin", (HINGE_ROD_X1 - HINGE_ROD_X0, HINGE_PIN_DIAMETER)),
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
        f"battery_pocket={BATTERY_POCKET_DEPTH:.1f}x"
        f"{BATTERY_POCKET_WIDTH:.1f}x{BATTERY_POCKET_INSERTION_DEPTH:.1f} "
        f"door_pocket={BATTERY_DOOR_SLOT_SIZE[0]:.1f}x"
        f"{BATTERY_DOOR_SLOT_SIZE[1]:.1f}x{BATTERY_DOOR_SLOT_DEPTH:.1f} "
        f"door_pad_preload={battery_door_pad_compression:.2f} "
        f"tray_installed_z={LOWER_TRAY_INSTALLED_Z:.2f} "
        f"misc_pockets={misc_lobe_specs[0][0][1][0]:.1f}x"
        f"{misc_lobe_specs[0][0][1][1]:.1f}/right_step="
        f"{misc_lobe_specs[1][0][1][0]:.1f}x"
        f"{misc_lobe_specs[1][0][1][1]:.1f}+"
        f"{misc_lobe_specs[1][1][1][0]:.1f}x"
        f"{misc_lobe_specs[1][1][1][1]:.1f}x"
        f"{TRAY_HEIGHT - MISC_COMPARTMENT_FLOOR_Z:.1f} "
        f"misc_web={MISC_COMPARTMENT_MIN_WEB:.1f} "
        f"latch_source_scale={LATCH_SOURCE_SCALE:.2f} "
        f"latch_lever={LATCH_LEVER_PRINT_SIZE[0]:.2f}x"
        f"{LATCH_LEVER_PRINT_SIZE[1]:.2f}x{LATCH_LEVER_PRINT_SIZE[2]:.2f} "
        f"latch_hook={LATCH_HOOK_PRINT_SIZE[0]:.2f}x"
        f"{LATCH_HOOK_PRINT_SIZE[1]:.2f}x{LATCH_HOOK_PRINT_SIZE[2]:.2f} "
        f"latch_link_rod={LATCH_LINK_ROD_DIAMETER:.2f} "
        f"latch_press_bore={LATCH_PRESS_FIT_BORE_DIAMETER:.2f} "
        f"latch_running_bore={LATCH_RUNNING_BORE_DIAMETER:.2f} "
        f"latch_fixed_m3_clearance={LATCH_FIXED_M3_CLEARANCE_DIAMETER:.2f} "
        f"latch_fixed_m3_countersink={LATCH_FIXED_M3_COUNTERSINK_DIAMETER:.2f}x"
        f"{LATCH_FIXED_M3_COUNTERSINK_DEPTH:.2f} "
        f"latch_fixed_m3_nut_recess={LATCH_FIXED_M3_NUT_ACROSS_FLATS:.2f}x"
        f"{LATCH_FIXED_M3_NUT_DEPTH:.2f} "
        f"latch_fixed_m3_screw=M3x{LATCH_FIXED_M3_BOLT_LENGTH:.0f} "
        f"latch_fixed_m3_engagement={fixed_m3_thread_engagement:.2f} "
        f"latch_fixed_m3_tip={fixed_m3_tip_protrusion:.2f} "
        f"latch_ear_clearance={LATCH_BASE_EAR_AXIAL_CLEARANCE:.2f} "
        f"pivot_min_wall={PIVOT_MIN_WALL_THICKNESS:.2f} "
        f"mount_chord_wall={mount_lower_chord_wall:.2f} "
        f"mount_roof_wall={mount_roof_wall:.2f} "
        f"latch_boss_wall={min(lever_fixed_wall, lever_link_wall, hook_link_wall):.2f} "
        f"latch_detent_wall={detent_to_bore_wall:.2f} "
        f"latch_lip_draw={LID_LATCH_LIP_DRAW:.2f} "
        f"latch_rim_outset={LID_FLANGE_OUTSET:.2f} "
        f"latch_rim_edge={LID_LATCH_RIM_EDGE_THICKNESS:.2f} "
        f"latch_skirt_radial={skirt_radial_tip:.2f} "
        f"latch_trough={LID_LATCH_TROUGH_WIDTH:.2f} "
        f"latch_rail_diameter={capture_rail_diameter:.2f} "
        f"latch_rail_outset={LID_LATCH_CAPTURE_RAIL_CENTER_OUTSET:.2f} "
        f"latch_rail_web={LID_LATCH_CAPTURE_WEB_THICKNESS:.2f} "
        f"latch_load_ledge={LID_LATCH_LOAD_LEDGE_THICKNESS:.2f} "
        f"latch_rail_path_clearance={LATCH_CAPTURE_RAIL_PATH_CLEARANCE:.2f} "
        f"latch_rail_release={LATCH_CAPTURE_FULL_RELEASE_ANGLE:.2f}deg "
        f"latch_capture_hook_wall={LATCH_CAPTURE_HOOK_WALL:.2f} "
        f"latch_round_boss={2.0 * LATCH_CAPTURE_NUB_RADIUS:.2f}x"
        f"{LATCH_CAPTURE_NUB_AXIAL_WIDTH:.2f} "
        f"latch_round_root={2.0 * LATCH_CAPTURE_NUB_ROOT_BOSS_RADIUS:.2f} "
        f"latch_flat_pad={LATCH_CAPTURE_FLAT_PAD_CASEWARD_LENGTH:.2f}x"
        f"{LATCH_CAPTURE_FLAT_PAD_AXIAL_WIDTH:.2f} "
        f"latch_protector={LATCH_PROTECTOR_BASE_WIDTH:.2f}x"
        f"{abs(LATCH_PROTECTOR_FRONT_Y - LATCH_PROTECTOR_BODY_Y):.2f} "
        f"lid_protector={LID_LATCH_TROUGH_SHOULDER_WIDTH:.2f} "
        f"latch_handle_clearance={latch_handle_clearance:.2f} "
        f"latch_mount_handle_clearance={latch_mount_handle_clearance:.2f} "
        f"handle_mode={HANDLE_HARDWARE_MODE} "
        f"handle_fork_cheek={handle_fork_cheek_thickness:.2f} "
        f"handle_pivot_chord_wall={handle_pivot_lower_chord_wall:.2f} "
        f"handle_pivot_roof_wall={handle_pivot_roof_wall:.2f} "
        f"handle_folded_face_gap={folded_handle_face_gap:.2f} "
        f"handle_grip_width={HANDLE_BAR_INNER_WIDTH:.2f} "
        f"handle_center_z={HANDLE_PIVOT_Z:.2f} "
        f"handle_raised_finger_gap={handle_raised_finger_gap:.2f} "
        f"hinge_rod={HINGE_ROD_DIAMETER:.2f} "
        f"hinge_base_bore={HINGE_BASE_HOLE_DIAMETER:.2f} "
        f"hinge_lid_receiver={HINGE_LID_RECEIVER_DIAMETER:.2f} "
        f"hinge_lid_slot={HINGE_LID_SLOT_WIDTH:.2f} "
        f"hinge_lid_slot_tilt={HINGE_LID_SLOT_TILT_DEGREES:.1f}deg "
        f"hinge_release={HINGE_LID_RELEASE_ANGLE_DEGREES:.1f}deg "
        f"hinge_end_stop={HINGE_LID_END_STOP_DIAMETER:.2f}x"
        f"{HINGE_LID_END_STOP_LENGTH:.2f} "
        f"hinge_rod_length={HINGE_ROD_X1 - HINGE_ROD_X0:.2f} "
        f"hinge_rod_axial_play={sum(rod_end_clearances):.2f}"
    )
    print(
        "FIELD_CASE_PRINT_ENVELOPES "
        f"base={base_print_width:.1f}x{base_print_depth:.1f} "
        f"lid={lid_print_width:.1f}x{lid_print_depth:.1f} "
        f"limit={MAX_PRINT_XY:.1f}"
    )


# ---------------------------------------------------------------------------
# PART BUILDERS


def latch_fixed_m3_outer_direction(latch_x):
    return -1.0 if latch_x < 0.0 else 1.0


def latch_fixed_m3_guard_faces(latch_x):
    outer_direction = latch_fixed_m3_outer_direction(latch_x)
    half_span = LATCH_FIXED_M3_GUARD_SPAN / 2.0
    return (
        latch_x + outer_direction * half_span,
        latch_x - outer_direction * half_span,
        outer_direction,
    )


def add_latch_fixed_m3_countersink(name, latch_x):
    head_face_x, _nut_face_x, outer_direction = latch_fixed_m3_guard_faces(latch_x)
    cutter_length = (
        LATCH_FIXED_M3_COUNTERSINK_DEPTH
        + LATCH_FIXED_M3_RECESS_BOOLEAN_OVERTRAVEL
    )
    cutter_center_x = head_face_x - outer_direction * (
        LATCH_FIXED_M3_COUNTERSINK_DEPTH
        - LATCH_FIXED_M3_RECESS_BOOLEAN_OVERTRAVEL
    ) / 2.0
    small_radius = LATCH_FIXED_M3_CLEARANCE_DIAMETER / 2.0
    # Grow the overtravel end by the same amount so the physical recess keeps
    # its true 45-degree-per-side (90-degree included) countersink angle.
    large_radius = (
        LATCH_FIXED_M3_COUNTERSINK_DIAMETER / 2.0
        + LATCH_FIXED_M3_RECESS_BOOLEAN_OVERTRAVEL
    )
    return add_cone_x(
        name,
        large_radius if outer_direction < 0.0 else small_radius,
        large_radius if outer_direction > 0.0 else small_radius,
        cutter_length,
        (cutter_center_x, LATCH_BASE_PIVOT_Y, LATCH_BASE_PIVOT_Z),
        vertices=64,
    )


def add_latch_fixed_m3_nut_recess(name, latch_x, across_flats=None, depth=None):
    _head_face_x, nut_face_x, outer_direction = latch_fixed_m3_guard_faces(latch_x)
    across_flats = (
        LATCH_FIXED_M3_NUT_ACROSS_FLATS
        if across_flats is None
        else across_flats
    )
    depth = LATCH_FIXED_M3_NUT_DEPTH if depth is None else depth
    recess_outer_x = nut_face_x - outer_direction * (
        LATCH_FIXED_M3_RECESS_BOOLEAN_OVERTRAVEL
    )
    recess_inner_x = nut_face_x + outer_direction * depth
    return extrude_loop_x(
        name,
        regular_hexagon_loop_yz(
            LATCH_BASE_PIVOT_Y,
            LATCH_BASE_PIVOT_Z,
            across_flats,
        ),
        min(recess_outer_x, recess_inner_x),
        max(recess_outer_x, recess_inner_x),
    )


def lid_hinge_slot_opening_local_yz():
    radians = math.radians(HINGE_LID_SLOT_TILT_DEGREES)
    return -math.cos(radians), -math.sin(radians)


def lid_hinge_escape_global_yz(open_angle_degrees):
    """Return the installed lid's unit translation along its receiver slot."""
    effective_angle = math.radians(
        open_angle_degrees - HINGE_LID_SLOT_TILT_DEGREES
    )
    return -math.cos(effective_angle), math.sin(effective_angle)


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

    # Exterior impact ribs are deliberately below the sealing edge.  The
    # front-center ribs are omitted because they would obstruct the measured
    # 24 mm finger corridor between the carry handle and each moving latch.
    # The integrated handle/latch mounts already reinforce that face.
    rib_specs = []
    for x in (-42.0, 0.0, 42.0):
        rib_specs.append(((x, CASE_DEPTH / 2.0 + 1.3, 24.0), (6.0, 4.8, 42.0)))
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

    # Each lid knuckle needs a cylindrical swing pocket through the base's
    # otherwise continuous rear wall and rim.  Cut these before adding the
    # alternating base knuckles so the relief cannot weaken their barrels.
    for index, (x0, x1) in enumerate(HINGE_LID_SEGMENTS, start=1):
        relief = add_cylinder_x(
            f"Base_Rear_Rim_Relief_For_Lid_Knuckle_{index}",
            HINGE_OUTER_DIAMETER / 2.0 + HINGE_RIM_RELIEF_RADIAL_CLEARANCE,
            x1 - x0 + 2.0 * HINGE_RIM_RELIEF_AXIAL_CLEARANCE,
            ((x0 + x1) / 2.0, HINGE_AXIS_Y, BASE_HEIGHT),
        )
        difference_from(base, relief)

    # The base knuckles share one continuous 4.5 mm path for the user's 4.1 mm
    # rod.  This bore enlargement is the only base-side hinge change.  A
    # full-width lower web rises from the rear wall at 45 degrees and meets
    # each barrel tangentially, eliminating its unsupported lower arc while
    # adding substantially more bonded section at the shell.
    for index, (x0, x1) in enumerate(HINGE_BASE_SEGMENTS, start=1):
        gusset = extrude_loop_x(
            f"Base_Hinge_Knuckle_{index}_Support_Free_Gusset",
            HINGE_BASE_GUSSET_PROFILE_YZ,
            x0,
            x1,
        )
        union_into(base, gusset)
        knuckle = add_cylinder_x(
            f"Base_Hinge_Knuckle_{index}",
            HINGE_OUTER_DIAMETER / 2.0,
            x1 - x0,
            ((x0 + x1) / 2.0, HINGE_AXIS_Y, BASE_HEIGHT),
        )
        union_into(base, knuckle)
        hole = add_teardrop_hole_x(
            f"Base_Hinge_Hole_{index}",
            HINGE_BASE_HOLE_DIAMETER / 2.0,
            x1 - x0 + 2.0 * HINGE_BORE_CUTTER_AXIAL_OVERTRAVEL,
            ((x0 + x1) / 2.0, HINGE_AXIS_Y, BASE_HEIGHT),
            arc_steps=90,
        )
        difference_from(base, hole)

    # The source lever sits between two reinforced case ears.  Each ear rises
    # from the shell on a printable lower ramp, wraps the pivot with the shared
    # minimum wall, and curves back into the body above the bore.  Their common
    # M3 clearance path is drilled after the thicker guards are joined below.
    for index, x in enumerate(LATCH_X_CENTERS, start=1):
        for side in (-1.0, 1.0):
            ear_x = x + side * LATCH_BASE_EAR_CENTER_OFFSET_X
            ear = extrude_loop_x(
                f"Base_Latch_{index}_Integrated_Pivot_Ear",
                LATCH_BASE_EAR_PROFILE_YZ,
                ear_x - LATCH_BASE_EAR_WIDTH / 2.0,
                ear_x + LATCH_BASE_EAR_WIDTH / 2.0,
            )
            if side in LATCH_DETENT_SIDES:
                inner_face_x = ear_x - side * LATCH_BASE_EAR_WIDTH / 2.0
                boss_center_x = inner_face_x + side * (
                    LATCH_DETENT_BOSS_RADIUS - LATCH_DETENT_BOSS_PROTRUSION
                )
                detent_boss = add_uv_sphere(
                    f"Base_Latch_{index}_Closed_Lever_Snap_Detent",
                    LATCH_DETENT_BOSS_RADIUS,
                    (
                        boss_center_x,
                        LATCH_BASE_PIVOT_Y + LATCH_DETENT_LOCAL_YZ[0],
                        LATCH_BASE_PIVOT_Z + LATCH_DETENT_LOCAL_YZ[1],
                    ),
                )
                union_into(ear, detent_boss)
            union_into(base, ear)

    # Thick impact cheeks stand proud of both sides of each closed lever, as
    # on the supplied Pelican reference.  Their lower faces grow from the
    # shell on 45-degree ramps, their front edges shield the lever from snags,
    # and their chamfered tops return into the body without a brittle corner.
    # The cheeks overlap the existing pivot ears.  Their 6 mm axial thickness
    # fully contains the flush M3 head and captive nut.  Drill one continuous
    # easy-running M3 path after union, then open a 90-degree countersink on the
    # case-outside guard and a support-free hex nut pocket on the inboard guard.
    for index, x in enumerate(LATCH_X_CENTERS, start=1):
        for side in (-1.0, 1.0):
            ear_x = x + side * LATCH_BASE_EAR_CENTER_OFFSET_X
            protector_center_x = ear_x + side * LATCH_PROTECTOR_AXIAL_OUTWARD_SHIFT
            protector = extrude_loop_x(
                f"Base_Latch_{index}_Side_Impact_Protector",
                LATCH_PROTECTOR_PROFILE_YZ,
                protector_center_x - LATCH_PROTECTOR_BASE_WIDTH / 2.0,
                protector_center_x + LATCH_PROTECTOR_BASE_WIDTH / 2.0,
            )
            union_into(base, protector)
        protected_bore = add_teardrop_hole_x(
            f"Base_Latch_{index}_M3_Easy_Running_Through_Hole",
            LATCH_FIXED_M3_CLEARANCE_DIAMETER / 2.0,
            LATCH_FIXED_M3_GUARD_SPAN + 0.8,
            (x, LATCH_BASE_PIVOT_Y, LATCH_BASE_PIVOT_Z),
        )
        difference_from(base, protected_bore)
        countersink = add_latch_fixed_m3_countersink(
            f"Base_Latch_{index}_Outside_M3_Countersink",
            x,
        )
        difference_from(base, countersink)
        nut_recess = add_latch_fixed_m3_nut_recess(
            f"Base_Latch_{index}_Inside_M3_Captive_Nut_Recess",
            x,
        )
        difference_from(base, nut_recess)

    # The suitcase-handle base is part of the shell: one reinforced, ramped lug
    # per side sits inside a relieved fork in the separate handle arm.  Its
    # upper edge curves back into the case body, and its horizontal bore has a
    # printable 45-degree roof.  Keeping both lugs outside the 75 mm grip
    # opening preserves the full raised finger gap.
    handle_base_bore = (
        HANDLE_PRESS_FIT_BORE_DIAMETER
        if HANDLE_HARDWARE_MODE == "ROD"
        else HANDLE_RUNNING_BORE_DIAMETER
    )
    for side in (-1.0, 1.0):
        lug_x = side * HANDLE_BASE_LUG_X
        lug = extrude_loop_x(
            "Base_Integrated_Handle_Pivot_Lug",
            HANDLE_BASE_EAR_PROFILE_YZ,
            lug_x - HANDLE_BASE_LUG_WIDTH / 2.0,
            lug_x + HANDLE_BASE_LUG_WIDTH / 2.0,
        )
        hole = add_teardrop_hole_x(
            "Base_Integrated_Handle_Pivot_Hole",
            handle_base_bore / 2.0,
            HANDLE_BASE_LUG_WIDTH + 0.8,
            (lug_x, HANDLE_PIVOT_Y, HANDLE_PIVOT_Z),
        )
        difference_from(lug, hole)
        union_into(base, lug)

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
            f"Battery_Cage_Door_{index}_50x11x11_Storage_Pocket",
            BATTERY_DOOR_SLOT_SIZE[0],
            BATTERY_DOOR_SLOT_SIZE[1],
            BATTERY_DOOR_SLOT_FLOOR_Z,
            TRAY_HEIGHT + 0.4,
            1.3,
            center,
        )
        difference_from(tray, slot)

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

    for compartment_index, (lobe_bounds, step_fillets) in enumerate(
        zip(MISC_COMPARTMENT_LOBE_BOUNDS, MISC_COMPARTMENT_STEP_FILLETS),
        start=1,
    ):
        for lobe_index, (x_bounds, y_bounds) in enumerate(lobe_bounds, start=1):
            misc_width = x_bounds[1] - x_bounds[0]
            misc_depth = y_bounds[1] - y_bounds[0]
            pocket = add_rounded_prism(
                "Miscellaneous_Storage_Compartment_"
                f"{compartment_index}_Lobe_{lobe_index}",
                misc_width,
                misc_depth,
                MISC_COMPARTMENT_FLOOR_Z,
                TRAY_HEIGHT + 0.4,
                MISC_COMPARTMENT_CORNER_RADIUS,
                (sum(x_bounds) / 2.0, sum(y_bounds) / 2.0),
            )
            difference_from(tray, pocket)

        for fillet_index, (fillet_x, fillet_y, fillet_radius) in enumerate(
            step_fillets,
            start=1,
        ):
            fillet_height = TRAY_HEIGHT + 0.4 - MISC_COMPARTMENT_FLOOR_Z
            fillet = add_cylinder_z(
                "Miscellaneous_Storage_Compartment_"
                f"{compartment_index}_Step_Fillet_{fillet_index}",
                fillet_radius,
                fillet_height,
                (
                    fillet_x,
                    fillet_y,
                    MISC_COMPARTMENT_FLOOR_Z + fillet_height / 2.0,
                ),
                vertices=48,
            )
            difference_from(tray, fillet)

    assign_material(tray, material)
    return tray


def create_lid(
    shell_material,
    logo_orange_material,
):
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
    # Pelican-style continuous mouth rim. A true rounded frustum grows outward
    # at 45 degrees from the lid wall, followed by a 3 mm loaded edge. Unlike a
    # localized hanging keeper, this ledge distributes latch load around the
    # complete perimeter and is supported at every print layer.
    flange_flare = rounded_ring_frustum(
        "Lid_Protective_Flared_Rim",
        (CASE_WIDTH, CASE_DEPTH),
        (
            CASE_WIDTH + 2.0 * LID_FLANGE_OUTSET,
            CASE_DEPTH + 2.0 * LID_FLANGE_OUTSET,
        ),
        (CASE_WIDTH - 0.8, CASE_DEPTH - 0.8),
        LID_FLANGE_FLARE_START_Z,
        LID_FLANGE_EDGE_START_Z,
        CASE_CORNER_RADIUS,
        CASE_CORNER_RADIUS + LID_FLANGE_OUTSET,
        CASE_CORNER_RADIUS - 0.4,
        (dx, 0.0),
    )
    union_into(lid, flange_flare)
    flange_edge = rounded_ring(
        "Lid_Protective_Flared_Rim_Loaded_Edge",
        (
            CASE_WIDTH + 2.0 * LID_FLANGE_OUTSET,
            CASE_DEPTH + 2.0 * LID_FLANGE_OUTSET,
        ),
        (CASE_WIDTH - 0.8, CASE_DEPTH - 0.8),
        LID_FLANGE_EDGE_START_Z,
        LID_WALL_HEIGHT,
        CASE_CORNER_RADIUS + LID_FLANGE_OUTSET,
        CASE_CORNER_RADIUS - 0.4,
        (dx, 0.0),
    )
    union_into(lid, flange_edge)

    # Match the supplied Pelican case's actual capture architecture: first cut
    # a deep molded bay through the front skirt while retaining a 4 mm back
    # wall.  A full-width 2.4 mm ledge then fills the radial gap and embeds the
    # horizontal rail through its outer edge.  The latch's flat bearing pad
    # presses on this ledge to pull the lid down; its round boss sits above the
    # ledge and behind the exposed half of the rail only to prevent outward
    # escape.  Robust side towers guide the 20.48 mm hook, prevent lateral
    # walk-off, and tie both ledge and rail ends into the lid rim.
    rim_front_y = CASE_DEPTH / 2.0 + LID_FLANGE_OUTSET
    rim_inner_front_y = (CASE_DEPTH - 0.8) / 2.0
    recess_back_y = rim_inner_front_y + LID_LATCH_RECESS_BACK_WALL
    rail_outer_y = LID_LATCH_CAPTURE_RAIL_CENTER_Y + LID_LATCH_CAPTURE_RAIL_RADIUS
    bay_outer_y = rail_outer_y + LID_LATCH_CAPTURE_BAY_CLEARANCE
    bay_top_z = (
        LID_LATCH_CAPTURE_RAIL_CENTER_Z
        + LID_LATCH_CAPTURE_RAIL_RADIUS
        + LID_LATCH_CAPTURE_BAY_CLEARANCE
    )
    side_web_z1 = LID_LATCH_CAPTURE_RAIL_CENTER_Z + LID_LATCH_CAPTURE_RAIL_RADIUS - 0.1
    side_web_z0 = side_web_z1 - LID_LATCH_CAPTURE_WEB_THICKNESS
    tower_back_y = recess_back_y - 0.2
    tower_slope_start_y = rim_front_y - 1.0
    tower_base_z = LID_FLANGE_EDGE_START_Z - LID_LATCH_TROUGH_SHOULDER_RISE
    tower_outer_y = rail_outer_y + LID_LATCH_CAPTURE_TOWER_OUTSET
    tower_slope_top_z = tower_base_z + tower_outer_y - tower_slope_start_y
    tower_top_z = max(
        LID_LATCH_CAPTURE_RAIL_CENTER_Z + LID_LATCH_CAPTURE_RAIL_RADIUS + 0.2,
        tower_slope_top_z + LID_LATCH_PROTECTOR_TOP_CAP_RISE,
    )
    tower_profile_yz = (
        (tower_back_y, tower_base_z),
        (tower_slope_start_y, tower_base_z),
        (tower_outer_y, tower_slope_top_z),
        (tower_outer_y, tower_top_z),
        (tower_back_y, tower_top_z),
    )
    for index, x in enumerate(LATCH_X_CENTERS, start=1):
        bay = extrude_loop_x(
            f"Lid_Latch_{index}_Deep_Molded_Capture_Bay_Cutter",
            (
                (recess_back_y, LID_LATCH_CAPTURE_BAY_Z0),
                (bay_outer_y, LID_LATCH_CAPTURE_BAY_Z0),
                (bay_outer_y, bay_top_z),
                (recess_back_y, bay_top_z),
            ),
            dx + x - LID_LATCH_TROUGH_WIDTH / 2.0,
            dx + x + LID_LATCH_TROUGH_WIDTH / 2.0,
        )
        difference_from(lid, bay)
        rail = add_cylinder_x(
            f"Lid_Latch_{index}_Horizontal_Capture_Rail",
            LID_LATCH_CAPTURE_RAIL_RADIUS,
            LID_LATCH_TROUGH_WIDTH + 2.0 * LID_LATCH_CAPTURE_RAIL_END_OVERLAP,
            (
                dx + x,
                LID_LATCH_CAPTURE_RAIL_CENTER_Y,
                LID_LATCH_CAPTURE_RAIL_CENTER_Z,
            ),
            vertices=64,
        )
        union_into(lid, rail)
        # The outer vertical webs reinforce the rail ends.  The full-width
        # ledge below is the primary load path: it overlaps the back wall,
        # reaches both protective towers, and intersects the rail through its
        # centerline so the cylinder is no longer a stand-alone bridge.
        nub_recess_half_width = (
            LATCH_CAPTURE_NUB_AXIAL_WIDTH / 2.0
            + LATCH_CAPTURE_NUB_RECESS_AXIAL_CLEARANCE
        )
        web_outer_half_width = LID_LATCH_TROUGH_WIDTH / 2.0
        for side in (-1.0, 1.0):
            web_x0 = (
                dx
                + x
                + min(
                    side * nub_recess_half_width,
                    side * web_outer_half_width,
                )
            )
            web_x1 = (
                dx
                + x
                + max(
                    side * nub_recess_half_width,
                    side * web_outer_half_width,
                )
            )
            web = extrude_loop_x(
                f"Lid_Latch_{index}_Capture_Rail_Side_Back_Web",
                (
                    (
                        recess_back_y - 0.2,
                        side_web_z0,
                    ),
                    (
                        LID_LATCH_CAPTURE_RAIL_CENTER_Y,
                        side_web_z0,
                    ),
                    (
                        LID_LATCH_CAPTURE_RAIL_CENTER_Y,
                        side_web_z1,
                    ),
                    (
                        recess_back_y - 0.2,
                        side_web_z1,
                    ),
                ),
                web_x0,
                web_x1,
            )
            union_into(lid, web)
        load_ledge_front_y = (
            LID_LATCH_CAPTURE_RAIL_CENTER_Y + LID_LATCH_LOAD_LEDGE_RAIL_EMBED
        )
        load_ledge_back_y = recess_back_y - LID_LATCH_LOAD_LEDGE_BACK_OVERLAP
        load_ledge_half_width = (
            LID_LATCH_TROUGH_WIDTH / 2.0 + LID_LATCH_LOAD_LEDGE_AXIAL_OVERLAP
        )
        load_ledge = extrude_loop_x(
            f"Lid_Latch_{index}_Full_Width_Flat_Downward_Load_Ledge",
            (
                (load_ledge_back_y, LID_LATCH_LOAD_LEDGE_CONTACT_Z),
                (load_ledge_front_y, LID_LATCH_LOAD_LEDGE_CONTACT_Z),
                (
                    load_ledge_front_y,
                    LID_LATCH_LOAD_LEDGE_CONTACT_Z + LID_LATCH_LOAD_LEDGE_THICKNESS,
                ),
                (
                    load_ledge_back_y,
                    LID_LATCH_LOAD_LEDGE_CONTACT_Z + LID_LATCH_LOAD_LEDGE_THICKNESS,
                ),
            ),
            dx + x - load_ledge_half_width,
            dx + x + load_ledge_half_width,
        )
        union_into(lid, load_ledge)
        load_ledge_back_riser = extrude_loop_x(
            f"Lid_Latch_{index}_Load_Ledge_Back_Wall_Reinforcement",
            (
                (load_ledge_back_y, LID_WALL_HEIGHT - 1.0),
                (recess_back_y + 0.2, LID_WALL_HEIGHT - 1.0),
                (
                    recess_back_y + 0.2,
                    LID_LATCH_LOAD_LEDGE_CONTACT_Z + LID_LATCH_LOAD_LEDGE_THICKNESS,
                ),
                (
                    load_ledge_back_y,
                    LID_LATCH_LOAD_LEDGE_CONTACT_Z + LID_LATCH_LOAD_LEDGE_THICKNESS,
                ),
            ),
            dx + x - load_ledge_half_width,
            dx + x + load_ledge_half_width,
        )
        union_into(lid, load_ledge_back_riser)
        for side in (-1.0, 1.0):
            inner_x = dx + x + side * LID_LATCH_TROUGH_WIDTH / 2.0
            outer_x = inner_x + side * LID_LATCH_TROUGH_SHOULDER_WIDTH
            tower = extrude_loop_x(
                f"Lid_Latch_{index}_Capture_Rail_Side_Tower",
                tower_profile_yz,
                min(inner_x, outer_x),
                max(inner_x, outer_x),
            )
            union_into(lid, tower)

    # The base knuckles swing through the continuous rear lid flange.  Matching
    # cylindrical pockets preserve the alternating-barrel hinge instead of
    # letting the surrounding rim collide before the lid can close.
    for index, (x0, x1) in enumerate(HINGE_BASE_SEGMENTS, start=1):
        relief_x0 = x0 - HINGE_RIM_RELIEF_AXIAL_CLEARANCE
        relief_x1 = x1 + HINGE_RIM_RELIEF_AXIAL_CLEARANCE
        if index == 1:
            relief_x0 = min(
                relief_x0,
                HINGE_ROD_X0 - HINGE_ROD_PATH_AXIAL_CLEARANCE,
                HINGE_BASE_SEGMENTS[0][0]
                - HINGE_LID_END_STOP_BASE_CLEARANCE
                - HINGE_ROD_RELEASE_AXIAL_VALIDATION_INSET,
            )
        if index == len(HINGE_BASE_SEGMENTS):
            relief_x1 = max(
                relief_x1,
                HINGE_ROD_X1 + HINGE_ROD_PATH_AXIAL_CLEARANCE,
                HINGE_BASE_SEGMENTS[-1][1]
                + HINGE_LID_END_STOP_BASE_CLEARANCE
                + HINGE_ROD_RELEASE_AXIAL_VALIDATION_INSET,
            )
        relief = add_cylinder_x(
            f"Lid_Rear_Rim_Relief_For_Base_Knuckle_{index}",
            HINGE_OUTER_DIAMETER / 2.0 + HINGE_RIM_RELIEF_RADIAL_CLEARANCE,
            relief_x1 - relief_x0,
            (
                dx + (relief_x0 + relief_x1) / 2.0,
                -HINGE_AXIS_Y,
                LID_WALL_HEIGHT,
            ),
        )
        difference_from(lid, relief)

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
    # around X places it on the base's +Y hinge line.  Union each barrel into
    # the complete flared rim, cut a round 4.5 mm receiver, then open that
    # receiver through its rear side with a 4.6 mm slot.  The installed escape
    # vector remains blocked by the unchanged base through 65 degrees.  At 70
    # degrees the lid slides diagonally up/forward off the already-installed 4.1
    # mm base rod.  These full-width slots need removable print support; the
    # extra 0.5 mm width leaves cleanup allowance around the physical rod.
    for index, (x0, x1) in enumerate(HINGE_LID_SEGMENTS, start=1):
        knuckle = add_cylinder_x(
            f"Lid_Hinge_Knuckle_{index}",
            HINGE_OUTER_DIAMETER / 2.0,
            x1 - x0,
            (dx + (x0 + x1) / 2.0, -HINGE_AXIS_Y, LID_WALL_HEIGHT),
        )
        union_into(lid, knuckle)
        receiver = add_cylinder_x(
            f"Lid_Hinge_Open_Rod_Receiver_{index}",
            HINGE_LID_RECEIVER_DIAMETER / 2.0,
            x1 - x0 + 2.0 * HINGE_BORE_CUTTER_AXIAL_OVERTRAVEL,
            (dx + (x0 + x1) / 2.0, -HINGE_AXIS_Y, LID_WALL_HEIGHT),
            vertices=90,
        )
        difference_from(lid, receiver)
        slot_opening_y, slot_opening_z = lid_hinge_slot_opening_local_yz()
        slot_perpendicular_y = -slot_opening_z
        slot_perpendicular_z = slot_opening_y
        slot_t0 = -0.2
        slot_t1 = HINGE_OUTER_DIAMETER / 2.0 + 0.8
        slot_half_width = HINGE_LID_SLOT_WIDTH / 2.0

        def slot_point(t, transverse):
            return (
                -HINGE_AXIS_Y
                + t * slot_opening_y
                + transverse * slot_perpendicular_y,
                LID_WALL_HEIGHT
                + t * slot_opening_z
                + transverse * slot_perpendicular_z,
            )

        slot = extrude_loop_x(
            f"Lid_Hinge_{HINGE_LID_SLOT_TILT_DEGREES:.0f}deg_"
            f"Straight_Release_Slot_{index}",
            (
                slot_point(slot_t0, -slot_half_width),
                slot_point(slot_t1, -slot_half_width),
                slot_point(slot_t1, slot_half_width),
                slot_point(slot_t0, slot_half_width),
            ),
            dx + x0 - HINGE_BORE_CUTTER_AXIAL_OVERTRAVEL,
            dx + x1 + HINGE_BORE_CUTTER_AXIAL_OVERTRAVEL,
        )
        difference_from(lid, slot)

    # Two short solid bosses sit just beyond the outer faces of the base's end
    # knuckles.  The 151 mm rod ends inside those faces, so these lid-mounted
    # stops pass outside the rod during drop-on installation and then block
    # axial walk-off in either direction.  Their smaller 6 mm diameter clears
    # the unchanged base rear wall while remaining deeply bonded into the lid
    # rim around the hinge axis.
    for side, base_outer_face in (
        (-1.0, HINGE_BASE_SEGMENTS[0][0]),
        (1.0, HINGE_BASE_SEGMENTS[-1][1]),
    ):
        stop_inner_face = (
            base_outer_face + side * HINGE_LID_END_STOP_BASE_CLEARANCE
        )
        stop_center_x = (
            stop_inner_face + side * HINGE_LID_END_STOP_LENGTH / 2.0
        )
        end_stop = add_cylinder_x(
            "Lid_Hinge_Left_Solid_Rod_End_Stop"
            if side < 0.0
            else "Lid_Hinge_Right_Solid_Rod_End_Stop",
            HINGE_LID_END_STOP_DIAMETER / 2.0,
            HINGE_LID_END_STOP_LENGTH,
            (
                dx + stop_center_x,
                -HINGE_AXIS_Y,
                LID_WALL_HEIGHT,
            ),
            vertices=90,
        )
        union_into(lid, end_stop)

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

    # Pre-mirroring Y makes the logo read normally after the lid is installed.
    # A small curve offset widens every stroke by 50% without replacing the
    # compact GoPro-style face or enlarging the original lettering footprint.
    logo_text_objects = [
        add_text_mesh(
            "Lid_GoPro_Missions_Orange_Inlay",
            LID_LOGO_TEXT,
            LID_LOGO_TEXT_SIZE,
            LID_LOGO_TEXT_MAX_WIDTH,
            (dx, LID_LOGO_TEXT_CENTER_Y, 0.0),
            LID_INLAY_DEPTH,
            mirror_y=True,
            font=load_embedded_logo_font(),
            outline_offset=LID_LOGO_TEXT_OUTLINE_OFFSET,
        )
    ]
    requested_text_dimension = (
        LID_LOGO_LEGACY_MIN_FEATURE_WIDTH * LID_LOGO_MIN_THICKNESS_MULTIPLIER
    )
    print(
        "FIELD_CASE_LID_TEXT_TARGET "
        f"requested_minimum={requested_text_dimension:.3f}mm "
        f"legacy={LID_LOGO_LEGACY_MIN_FEATURE_WIDTH:.3f}mm "
        f"multiplier={LID_LOGO_MIN_THICKNESS_MULTIPLIER:.2f}x "
        f"outline_offset={LID_LOGO_TEXT_OUTLINE_OFFSET:.5f}mm"
    )
    block_total_width = 4.0 * LID_LOGO_BLOCK_SIZE[0] + 3.0 * LID_LOGO_BLOCK_GAP
    block_start_x = -block_total_width / 2.0 + LID_LOGO_BLOCK_SIZE[0] / 2.0
    block_specs = ("one", "two", "three", "four")
    blocks = {}
    for block_index, block_name in enumerate(block_specs):
        block = add_rounded_prism(
            f"Lid_GoPro_Logo_Orange_Block_{block_index + 1}_Inlay",
            LID_LOGO_BLOCK_SIZE[0],
            LID_LOGO_BLOCK_SIZE[1],
            0.0,
            LID_INLAY_DEPTH,
            0.7,
            (
                dx
                + block_start_x
                + block_index * (LID_LOGO_BLOCK_SIZE[0] + LID_LOGO_BLOCK_GAP),
                LID_LOGO_BLOCK_CENTER_Y,
            ),
        )
        blocks[block_name] = block

    # All lid lettering and blocks intentionally share one orange material and
    # one slicer body, leaving only two AMS filaments on the compound lid.
    logo_orange = logo_text_objects[0]
    select_only(logo_orange)
    for text_obj in logo_text_objects[1:]:
        text_obj.select_set(True)
    for block in blocks.values():
        block.select_set(True)
    bpy.context.view_layer.objects.active = logo_orange
    bpy.ops.object.join()
    logo_orange.name = "Lid_GoPro_Missions_And_Blocks_Orange_Inlay"
    # Keep the curved orange mark as a shallow raised face. Its top bonds to
    # the lid's uninterrupted build-facing plane without fragile font booleans.
    logo_orange.location.z -= LID_INLAY_DEPTH
    bpy.context.view_layer.update()

    assign_material(lid, shell_material)
    assign_material(logo_orange, logo_orange_material)
    return lid, logo_orange


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

    # The doors sit 11 mm below the camera/battery contact plane because only
    # 10 mm of their 18 mm height is recessed. These localized extensions meet
    # the proud door tops with the same lid preload as the taller equipment.
    for index, center in enumerate(BATTERY_DOOR_SLOT_CENTERS, start=1):
        hold_down = add_rounded_prism(
            f"Battery_Cage_Door_{index}_Lid_Hold_Down_Pad",
            BATTERY_DOOR_LID_HOLD_DOWN_SIZE[0],
            BATTERY_DOOR_LID_HOLD_DOWN_SIZE[1],
            LID_RETAINER_HEIGHT - 0.2,
            LID_RETAINER_HEIGHT + BATTERY_DOOR_LID_HOLD_DOWN_EXTENSION,
            2.0,
            (center[0], -center[1]),
        )
        union_into(retainer, hold_down)

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


def decode_embedded_pelican_latch_meshes():
    """Decode the lever and hook derived from the supplied Blender mechanism."""
    payload = lzma.decompress(base64.b85decode(PELICAN_BLEND_LATCH_MESHES_LZMA_BASE85))
    mesh_count = struct.unpack_from("<I", payload, 0)[0]
    if mesh_count != 2:
        raise ValueError("Embedded Pelican mechanism must contain lever and hook")
    offset = 4
    meshes = []
    for _mesh_index in range(mesh_count):
        vertex_count, face_count = struct.unpack_from("<II", payload, offset)
        offset += 8
        vertices = [
            struct.unpack_from("<fff", payload, offset + index * 12)
            for index in range(vertex_count)
        ]
        offset += vertex_count * 12
        faces = [
            struct.unpack_from("<III", payload, offset + index * 12)
            for index in range(face_count)
        ]
        offset += face_count * 12
        meshes.append((vertices, faces))
    if offset != len(payload):
        raise ValueError("Embedded Pelican mechanism payload has an invalid size")
    return tuple(meshes)


def create_pelican_latch_parts(material):
    """Create separate, side-down lever and hook prints from the source meshes."""
    payloads = decode_embedded_pelican_latch_meshes()
    specifications = (
        (
            "Field_Case_Pelican_Source_Lever_Print_Two",
            "Pelican_Source_Lever_Mesh",
        ),
        (
            "Field_Case_Pelican_Source_Hook_Print_Two",
            "Pelican_Source_Hook_Mesh",
        ),
    )
    parts = []
    for part_index, ((vertices, faces), (object_name, mesh_name)) in enumerate(
        zip(payloads, specifications)
    ):
        mesh = bpy.data.meshes.new(mesh_name)
        mesh.from_pydata(vertices, (), faces)
        mesh.update(calc_edges=True)
        if mesh.validate(verbose=False, clean_customdata=True):
            raise ValueError(f"Embedded latch mesh {mesh_name} required cleanup")
        part = bpy.data.objects.new(object_name, mesh)
        bpy.context.collection.objects.link(part)
        if part_index == 0:
            fixed_boss = add_cylinder_x(
                "Pelican_Lever_Reinforced_Fixed_Pivot_Boss",
                LATCH_LEVER_FIXED_BOSS_RADIUS,
                LATCH_WIDTH,
                (0.0, 0.0, 0.0),
                vertices=64,
            )
            union_into(part, fixed_boss)
            link_boss = add_cylinder_x(
                "Pelican_Lever_Reinforced_Link_Pivot_Boss",
                LATCH_LEVER_LINK_BOSS_RADIUS,
                LATCH_LEVER_LINK_TONGUE_WIDTH,
                (0.0, *LATCH_LINK_PIVOT_LOCAL_YZ),
                vertices=64,
            )
            union_into(part, link_boss)
            # The hook carries its reinforced link bore in two outer cheeks.
            # Clear those exact axial bands from the source lever frame while
            # preserving the lever's reinforced central link tongue.
            for side in (-1.0, 1.0):
                cheek_center_x = side * (
                    LATCH_HOOK_CHEEK_INNER_X + LATCH_HOOK_CHEEK_WIDTH / 2.0
                )
                hook_boss_relief = add_cylinder_x(
                    "Pelican_Lever_Clearance_For_Reinforced_Hook_Cheek",
                    LATCH_HOOK_LINK_BOSS_RADIUS + LATCH_REINFORCEMENT_RUNNING_CLEARANCE,
                    LATCH_HOOK_CHEEK_WIDTH + 2.0 * LATCH_REINFORCEMENT_AXIAL_CLEARANCE,
                    (cheek_center_x, *LATCH_LINK_PIVOT_LOCAL_YZ),
                    vertices=64,
                )
                difference_from(part, hook_boss_relief)
            fixed_bore = add_cylinder_x(
                "Pelican_Lever_3p5mm_M3_Fixed_Running_Bore",
                LATCH_FIXED_M3_CLEARANCE_DIAMETER / 2.0,
                LATCH_WIDTH + 0.8,
                (0.0, 0.0, 0.0),
                vertices=64,
            )
            difference_from(part, fixed_bore)
            link_bore = add_cylinder_x(
                "Pelican_Lever_4p4mm_Link_Running_Bore",
                LATCH_RUNNING_BORE_DIAMETER / 2.0,
                LATCH_LEVER_LINK_TONGUE_WIDTH + 0.8,
                (0.0, *LATCH_LINK_PIVOT_LOCAL_YZ),
                vertices=64,
            )
            difference_from(part, link_bore)
            for side in LATCH_DETENT_SIDES:
                dimple_center_x = side * (
                    LATCH_WIDTH / 2.0
                    + LATCH_DETENT_DIMPLE_RADIUS
                    - LATCH_DETENT_DIMPLE_DEPTH
                )
                dimple = add_uv_sphere(
                    "Pelican_Source_Lever_Closed_Snap_Dimple_Cutter",
                    LATCH_DETENT_DIMPLE_RADIUS,
                    (
                        dimple_center_x,
                        LATCH_DETENT_LOCAL_YZ[0],
                        LATCH_DETENT_LOCAL_YZ[1],
                    ),
                )
                difference_from(part, dimple)
        else:
            for side in (-1.0, 1.0):
                cheek_center_x = side * (
                    LATCH_HOOK_CHEEK_INNER_X + LATCH_HOOK_CHEEK_WIDTH / 2.0
                )
                cheek_boss = add_cylinder_x(
                    "Pelican_Hook_Reinforced_Link_Pivot_Cheek",
                    LATCH_HOOK_LINK_BOSS_RADIUS,
                    LATCH_HOOK_CHEEK_WIDTH,
                    (cheek_center_x, 0.0, 0.0),
                    vertices=64,
                )
                union_into(part, cheek_boss)
            hook_bore = add_cylinder_x(
                "Pelican_Hook_3p9mm_Link_Press_Fit_Bore",
                LATCH_PRESS_FIT_BORE_DIAMETER / 2.0,
                LATCH_WIDTH + 0.8,
                (0.0, 0.0, 0.0),
                vertices=64,
            )
            difference_from(part, hook_bore)
            # The source hook's rounded lower tooth made the latch look as if
            # it were balancing on, or biting around, the lid rail.  Remove
            # that lower jaw.  The replacement follows the requested Pelican
            # load path: a full-width upper arm carries a broad flat bearing
            # pad that presses on the lid ledge.  A cylindrical TPU boss and
            # larger overlapping root sit above that pad and behind the rail
            # only to block outward escape.
            lower_jaw_corners_installed = (
                (-91.0, 53.0),
                (LATCH_CAPTURE_LOWER_JAW_REMOVAL_CASEWARD_Y, 53.0),
                (LATCH_CAPTURE_LOWER_JAW_REMOVAL_CASEWARD_Y, 61.85),
                (-91.0, 61.85),
            )
            lower_jaw_cutter = extrude_loop_x(
                "Pelican_Hook_Remove_Obsolete_Lower_Capture_Jaw",
                tuple(
                    installed_yz_in_hook_local(
                        LATCH_LEVER_CLOSED_ANGLE,
                        installed_y,
                        installed_z,
                    )
                    for installed_y, installed_z in lower_jaw_corners_installed
                ),
                -LATCH_WIDTH / 2.0 - 0.4,
                LATCH_WIDTH / 2.0 + 0.4,
            )
            difference_from(part, lower_jaw_cutter)

            rail_local_y, rail_local_z = latch_rail_in_hook_local_yz(
                LATCH_LEVER_CLOSED_ANGLE
            )
            rail_running_radius = (
                LID_LATCH_CAPTURE_RAIL_RADIUS + LATCH_CAPTURE_RAIL_PATH_CLEARANCE
            )
            upper_arm_inner_y = rail_local_y - rail_running_radius
            upper_arm_outer_y = upper_arm_inner_y - LATCH_CAPTURE_UPPER_ARM_THICKNESS
            _release_rail_y, release_rail_z = latch_rail_in_hook_local_yz(
                LATCH_CAPTURE_FULL_RELEASE_ANGLE
            )
            upper_arm_front_z = (
                release_rail_z
                - rail_running_radius
                + LATCH_CAPTURE_UPPER_ARM_FRONT_OVERLAP
            )
            nub_center_y, nub_center_z = installed_yz_in_hook_local(
                LATCH_LEVER_CLOSED_ANGLE,
                LATCH_CAPTURE_NUB_INSTALLED_Y,
                LATCH_CAPTURE_NUB_INSTALLED_Z,
            )
            upper_arm_back_z = nub_center_z + 0.5 * LATCH_CAPTURE_NUB_RADIUS
            obsolete_upper_tooth_cutter = extrude_loop_x(
                "Pelican_Hook_Remove_Obsolete_Caseward_Upper_Tooth",
                (
                    (-50.0, upper_arm_back_z - 0.05),
                    (-24.0, upper_arm_back_z - 0.05),
                    (-24.0, 15.0),
                    (-50.0, 15.0),
                ),
                -LATCH_WIDTH / 2.0 - 0.4,
                LATCH_WIDTH / 2.0 + 0.4,
            )
            difference_from(part, obsolete_upper_tooth_cutter)
            upper_arm = extrude_loop_x(
                "Pelican_Hook_Full_Width_Reinforced_Upper_Arm",
                (
                    (upper_arm_outer_y, upper_arm_front_z),
                    (upper_arm_inner_y, upper_arm_front_z),
                    (upper_arm_inner_y, upper_arm_back_z),
                    (upper_arm_outer_y, upper_arm_back_z),
                ),
                -LATCH_WIDTH / 2.0 + LATCH_CAPTURE_UPPER_ARM_AXIAL_INSET,
                LATCH_WIDTH / 2.0 - LATCH_CAPTURE_UPPER_ARM_AXIAL_INSET,
            )
            union_into(part, upper_arm)

            flat_pad_corners_installed = (
                (
                    LATCH_CAPTURE_FLAT_PAD_OUTWARD_INSTALLED_Y,
                    LATCH_CAPTURE_FLAT_PAD_BOTTOM_INSTALLED_Z,
                ),
                (
                    LATCH_CAPTURE_FLAT_PAD_CASEWARD_INSTALLED_Y,
                    LATCH_CAPTURE_FLAT_PAD_BOTTOM_INSTALLED_Z,
                ),
                (
                    LATCH_CAPTURE_FLAT_PAD_CASEWARD_INSTALLED_Y,
                    LATCH_CAPTURE_FLAT_PAD_TOP_INSTALLED_Z,
                ),
                (
                    LATCH_CAPTURE_FLAT_PAD_OUTWARD_INSTALLED_Y,
                    LATCH_CAPTURE_FLAT_PAD_TOP_INSTALLED_Z,
                ),
            )
            flat_bearing_pad = extrude_loop_x(
                "Pelican_Hook_Broad_Flat_Downward_Bearing_Pad",
                tuple(
                    installed_yz_in_hook_local(
                        LATCH_LEVER_CLOSED_ANGLE,
                        installed_y,
                        installed_z,
                    )
                    for installed_y, installed_z in flat_pad_corners_installed
                ),
                -LATCH_CAPTURE_FLAT_PAD_AXIAL_WIDTH / 2.0,
                LATCH_CAPTURE_FLAT_PAD_AXIAL_WIDTH / 2.0,
            )
            union_into(part, flat_bearing_pad)

            capture_nub = add_cylinder_x(
                "Pelican_Hook_Central_Behind_Rail_Round_TPU_Boss",
                LATCH_CAPTURE_NUB_RADIUS,
                LATCH_CAPTURE_NUB_AXIAL_WIDTH,
                (0.0, nub_center_y, nub_center_z),
                vertices=64,
            )
            union_into(part, capture_nub)
            root_boss_center_y, root_boss_center_z = installed_yz_in_hook_local(
                LATCH_LEVER_CLOSED_ANGLE,
                LATCH_CAPTURE_ROOT_BOSS_INSTALLED_Y,
                LATCH_CAPTURE_ROOT_BOSS_INSTALLED_Z,
            )
            root_boss = add_cylinder_x(
                "Pelican_Hook_Round_TPU_Boss_Reinforced_Root",
                LATCH_CAPTURE_NUB_ROOT_BOSS_RADIUS,
                LATCH_CAPTURE_NUB_AXIAL_WIDTH,
                (0.0, root_boss_center_y, root_boss_center_z),
                vertices=64,
            )
            union_into(part, root_boss)

            # Sample the fixed rail in the cammed moving-hook frame and remove
            # its close-running envelope.  The first 12 degrees retain the
            # round boss behind the rail while the flat pad still bears on the
            # ledge.  By 24 degrees both pad and boss have lifted clear of the
            # continuous ledge and the rail exits below the upper arm; no
            # lower jaw, pointed wedge, or disconnected tooth is needed.
            release_sweep_steps = max(
                1,
                math.ceil(
                    abs(LATCH_CAPTURE_FULL_RELEASE_ANGLE - LATCH_LEVER_CLOSED_ANGLE)
                    / LATCH_CAPTURE_CLEARANCE_SWEEP_STEP_DEGREES
                ),
            )
            for step in range(release_sweep_steps + 1):
                lever_angle = (
                    LATCH_LEVER_CLOSED_ANGLE
                    + (LATCH_CAPTURE_FULL_RELEASE_ANGLE - LATCH_LEVER_CLOSED_ANGLE)
                    * step
                    / release_sweep_steps
                )
                local_y, local_z = latch_rail_in_hook_local_yz(lever_angle)
                capture_sweep_clearance = add_cylinder_x(
                    f"Pelican_Hook_Rail_Release_Sweep_{step:02d}",
                    rail_running_radius,
                    LATCH_WIDTH + 0.8,
                    (0.0, local_y, local_z),
                    vertices=64,
                )
                difference_from(part, capture_sweep_clearance)
            release_lift_steps = 4
            release_lift_distance = LID_LATCH_LIP_DRAW + LATCH_MAX_CAPTURE_FREE_LIFT
            for step in range(1, release_lift_steps + 1):
                lift = release_lift_distance * step / release_lift_steps
                local_y, local_z = installed_yz_in_hook_local(
                    LATCH_CAPTURE_FULL_RELEASE_ANGLE,
                    LATCH_CAPTURE_RAIL_INSTALLED_Y,
                    LATCH_CAPTURE_RAIL_INSTALLED_Z + lift,
                )
                release_lift_clearance = add_cylinder_x(
                    f"Pelican_Hook_Rail_Lid_Lift_Release_{step:02d}",
                    rail_running_radius,
                    LATCH_WIDTH + 0.8,
                    (0.0, local_y, local_z),
                    vertices=64,
                )
                difference_from(part, release_lift_clearance)
            # The reinforced fixed lever boss is circular and stationary in
            # the lever frame.  In the rotating hook frame it follows this
            # sampled arc.  Relieving that swept envelope preserves the full
            # toggle motion without thinning the hook's own link-pivot ring.
            relief_steps = max(
                1,
                math.ceil(
                    abs(LATCH_LEVER_OPEN_ANGLE - LATCH_LEVER_CLOSED_ANGLE)
                    / LATCH_REINFORCEMENT_RELIEF_STEP_DEGREES
                ),
            )
            link_y, link_z = LATCH_LINK_PIVOT_LOCAL_YZ
            for step in range(relief_steps + 1):
                lever_angle = (
                    LATCH_LEVER_CLOSED_ANGLE
                    + (LATCH_LEVER_OPEN_ANGLE - LATCH_LEVER_CLOSED_ANGLE)
                    * step
                    / relief_steps
                )
                relative_angle = math.radians(
                    latch_hook_global_angle_degrees(lever_angle) - lever_angle
                )
                delta_y = -link_y
                delta_z = -link_z
                fixed_y_in_hook = (
                    math.cos(relative_angle) * delta_y
                    + math.sin(relative_angle) * delta_z
                )
                fixed_z_in_hook = (
                    -math.sin(relative_angle) * delta_y
                    + math.cos(relative_angle) * delta_z
                )
                fixed_boss_relief = add_cylinder_x(
                    "Pelican_Hook_Clearance_For_Reinforced_Fixed_Lever_Boss",
                    LATCH_LEVER_FIXED_BOSS_RADIUS
                    + LATCH_REINFORCEMENT_RUNNING_CLEARANCE,
                    LATCH_WIDTH + 0.8,
                    (0.0, fixed_y_in_hook, fixed_z_in_hook),
                    vertices=64,
                )
                difference_from(part, fixed_boss_relief)
        # A broad source side is the support-free print face.  Keep the mesh
        # data itself in its installed coordinate frame so reference copies can
        # be positioned by simply clearing this object transform.
        part.rotation_euler.y = math.radians(90.0)
        part.location.z = LATCH_WIDTH / 2.0
        assign_material(part, material)
        parts.append(part)
    return tuple(parts)


def create_pivoting_handle_bar(material):
    """Create the separate U handle bar with reference-style grip holes."""
    arm_width = (HANDLE_BAR_OUTER_WIDTH - HANDLE_BAR_INNER_WIDTH) / 2.0
    arm_center_x = HANDLE_BAR_INNER_WIDTH / 2.0 + arm_width / 2.0
    grip_center_y = -HANDLE_BAR_DROP + HANDLE_BAR_DEPTH / 2.0
    handle = add_rounded_box(
        "Field_Case_Pivoting_Handle_Bar",
        (HANDLE_BAR_OUTER_WIDTH, HANDLE_BAR_DEPTH, HANDLE_BAR_THICKNESS),
        (0.0, grip_center_y, HANDLE_BAR_THICKNESS / 2.0),
        bevel=3.2,
    )
    arm_length = HANDLE_BAR_DROP - HANDLE_BAR_DEPTH + 3.0
    for side in (-1.0, 1.0):
        arm = add_rounded_box(
            "Pivoting_Handle_Arm",
            (arm_width, arm_length, HANDLE_BAR_THICKNESS),
            (
                side * arm_center_x,
                -arm_length / 2.0 + 1.5,
                HANDLE_BAR_THICKNESS / 2.0,
            ),
            bevel=2.6,
        )
        union_into(handle, arm)
        pivot_barrel = extrude_loop_x(
            "Pivoting_Handle_Reinforced_Support_Free_Pivot_Boss",
            support_free_pivot_boss_loop_yz(
                0.0,
                HANDLE_BAR_THICKNESS / 2.0,
                HANDLE_PIVOT_BOSS_RADIUS,
            ),
            side * HANDLE_PIVOT_X - arm_width / 2.0,
            side * HANDLE_PIVOT_X + arm_width / 2.0,
        )
        union_into(handle, pivot_barrel)
        pivot_hole = add_teardrop_hole_x(
            "Pivoting_Handle_4p4mm_Running_Hole",
            HANDLE_RUNNING_BORE_DIAMETER / 2.0,
            arm_width + 0.8,
            (side * HANDLE_PIVOT_X, 0.0, HANDLE_BAR_THICKNESS / 2.0),
        )
        difference_from(handle, pivot_hole)
        fork_relief = add_rounded_box(
            "Pivoting_Handle_Fixed_Lug_Sweep_Relief",
            (
                HANDLE_BASE_LUG_WIDTH + 2.0 * HANDLE_AXIAL_CLEARANCE,
                HANDLE_FORK_RELIEF_LENGTH,
                HANDLE_BAR_THICKNESS + 1.0,
            ),
            (
                side * HANDLE_PIVOT_X,
                0.0,
                HANDLE_BAR_THICKNESS / 2.0,
            ),
            bevel=0.0,
        )
        difference_from(handle, fork_relief)

    for hole_index in range(HANDLE_GRIP_HOLE_COUNT):
        hole_x = (
            hole_index - (HANDLE_GRIP_HOLE_COUNT - 1) / 2.0
        ) * HANDLE_GRIP_HOLE_PITCH
        grip_hole = add_cylinder_z(
            "Pivoting_Handle_Grip_Hole",
            HANDLE_GRIP_HOLE_DIAMETER / 2.0,
            HANDLE_BAR_THICKNESS + 1.0,
            (hole_x, grip_center_y, HANDLE_BAR_THICKNESS / 2.0),
            vertices=36,
        )
        difference_from(handle, grip_hole)

    # The first grip primitive carries a nonzero construction origin.  Bake it
    # before applying the print offset so installed reference copies rotate
    # around the documented local pivot coordinates.
    select_only(handle)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    translate_object(handle, (0.0, HANDLE_PRINT_OFFSET_Y, 0.0))
    assign_material(handle, material)
    return handle


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
        HINGE_ROD_X0,
        HINGE_ROD_X1,
    )
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


def position_installed_latch_lever(lever, x: float) -> None:
    lever.rotation_euler = (0.0, 0.0, 0.0)
    lever.location = (x, LATCH_BASE_PIVOT_Y, LATCH_BASE_PIVOT_Z)


def position_installed_latch_hook(hook, x: float) -> None:
    hook.rotation_euler = (math.radians(LATCH_HOOK_CLOSED_ANGLE), 0.0, 0.0)
    hook.location = (
        x,
        LATCH_BASE_PIVOT_Y + LATCH_LINK_PIVOT_LOCAL_YZ[0],
        LATCH_BASE_PIVOT_Z + LATCH_LINK_PIVOT_LOCAL_YZ[1],
    )


def create_latch_fixed_m3_reference_hardware(
    name,
    latch_x,
    material=None,
    seat_clearance=0.0,
):
    """Build a nominal seated screw/nut pair for assembly views only."""
    head_face_x, nut_face_x, outer_direction = latch_fixed_m3_guard_faces(latch_x)
    seat_inset = (
        LATCH_FIXED_M3_COUNTERSINK_DIAMETER
        - LATCH_FIXED_M3_NOMINAL_HEAD_DIAMETER
    ) / 2.0 - seat_clearance
    head_depth = (
        LATCH_FIXED_M3_NOMINAL_HEAD_DIAMETER
        - LATCH_FIXED_M3_NOMINAL_DIAMETER
    ) / 2.0
    head_top_x = head_face_x - outer_direction * seat_inset
    head_inner_x = head_top_x - outer_direction * head_depth
    head = add_cone_x(
        name + "_Countersunk_Head",
        (
            LATCH_FIXED_M3_NOMINAL_HEAD_DIAMETER / 2.0
            if outer_direction < 0.0
            else LATCH_FIXED_M3_NOMINAL_DIAMETER / 2.0
        ),
        (
            LATCH_FIXED_M3_NOMINAL_HEAD_DIAMETER / 2.0
            if outer_direction > 0.0
            else LATCH_FIXED_M3_NOMINAL_DIAMETER / 2.0
        ),
        head_depth,
        (
            (head_top_x + head_inner_x) / 2.0,
            LATCH_BASE_PIVOT_Y,
            LATCH_BASE_PIVOT_Z,
        ),
        vertices=64,
    )
    if material is not None:
        assign_material(head, material)

    tip_x = head_top_x - outer_direction * LATCH_FIXED_M3_BOLT_LENGTH
    shaft = add_cylinder_x(
        name + "_Shaft",
        LATCH_FIXED_M3_NOMINAL_DIAMETER / 2.0,
        abs(tip_x - head_inner_x),
        (
            (tip_x + head_inner_x) / 2.0,
            LATCH_BASE_PIVOT_Y,
            LATCH_BASE_PIVOT_Z,
        ),
        vertices=64,
    )
    if material is not None:
        assign_material(shaft, material)

    nut_floor_x = nut_face_x + outer_direction * LATCH_FIXED_M3_NUT_DEPTH
    nut_open_x = (
        nut_floor_x
        - outer_direction * LATCH_FIXED_M3_NOMINAL_NUT_THICKNESS
    )
    nut = extrude_loop_x(
        name + "_Captive_Nut",
        regular_hexagon_loop_yz(
            LATCH_BASE_PIVOT_Y,
            LATCH_BASE_PIVOT_Z,
            LATCH_FIXED_M3_NOMINAL_NUT_ACROSS_FLATS,
        ),
        min(nut_floor_x, nut_open_x),
        max(nut_floor_x, nut_open_x),
    )
    if material is not None:
        assign_material(nut, material)
    return head, shaft, nut


def create_latch_reference_mockups(parts, materials):
    latch_material, rod_material = materials
    objects = []
    for index, x in enumerate(LATCH_X_CENTERS, start=1):
        lever = duplicate_reference_part(
            parts["latch_lever"],
            f"REFERENCE_ONLY_CLOSED_Pelican_Source_Lever_{index}",
            latch_material,
        )
        position_installed_latch_lever(lever, x)
        objects.append(lever)
        hook = duplicate_reference_part(
            parts["latch_hook"],
            f"REFERENCE_ONLY_CLOSED_Pelican_Source_Hook_{index}",
            latch_material,
        )
        position_installed_latch_hook(hook, x)
        objects.append(hook)
        objects.extend(
            create_latch_fixed_m3_reference_hardware(
                f"REFERENCE_ONLY_Latch_{index}_M3x"
                f"{LATCH_FIXED_M3_BOLT_LENGTH:.0f}_Fixed_Pivot",
                x,
                rod_material,
            )
        )
        link_pin = add_cylinder_x(
            f"REFERENCE_ONLY_Latch_{index}_4mm_Link_Rod",
            LATCH_LINK_ROD_DIAMETER / 2.0,
            LATCH_LINK_ROD_LENGTH,
            (
                x,
                LATCH_BASE_PIVOT_Y + LATCH_LINK_PIVOT_LOCAL_YZ[0],
                LATCH_BASE_PIVOT_Z + LATCH_LINK_PIVOT_LOCAL_YZ[1],
            ),
            vertices=36,
        )
        assign_material(link_pin, rod_material)
        objects.append(link_pin)
    return objects


def exact_transformed_intersection(
    first,
    second,
    *,
    first_location=(0.0, 0.0, 0.0),
    first_rotation=(0.0, 0.0, 0.0),
    second_location=(0.0, 0.0, 0.0),
    second_rotation=(0.0, 0.0, 0.0),
    return_bounds=False,
):
    """Return face count and volume of an exact temporary solid intersection."""
    probe = first.copy()
    probe.data = first.data.copy()
    probe.name = "TEMPORARY_Installed_Clearance_Intersection"
    bpy.context.collection.objects.link(probe)
    probe.location = first_location
    probe.rotation_euler = first_rotation
    tool = second.copy()
    tool.data = second.data.copy()
    tool.name = "TEMPORARY_Installed_Clearance_Tool"
    bpy.context.collection.objects.link(tool)
    tool.location = second_location
    tool.rotation_euler = second_rotation
    try:
        modifier = probe.modifiers.new("Exact_Installed_Intersection", "BOOLEAN")
        modifier.operation = "INTERSECT"
        modifier.solver = "EXACT"
        modifier.object = tool
        select_only(probe)
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        bm = bmesh.new()
        try:
            bm.from_mesh(probe.data)
            face_count = len(bm.faces)
            volume = abs(bm.calc_volume(signed=True)) if bm.faces else 0.0
            if bm.verts:
                coordinates = [probe.matrix_world @ vertex.co for vertex in bm.verts]
                bounds = tuple(
                    (
                        min(coordinate[axis] for coordinate in coordinates),
                        max(coordinate[axis] for coordinate in coordinates),
                    )
                    for axis in range(3)
                )
            else:
                bounds = None
        finally:
            bm.free()
    finally:
        bpy.data.objects.remove(tool, do_unlink=True)
        bpy.data.objects.remove(probe, do_unlink=True)
    if return_bounds:
        return face_count, volume, bounds
    return face_count, volume


def validate_built_lid_capture_rails(lid) -> None:
    """Prove each rail is embedded in a solid full-width lid load ledge."""
    rim_inner_front_y = (CASE_DEPTH - 0.8) / 2.0
    recess_back_y = rim_inner_front_y + LID_LATCH_RECESS_BACK_WALL
    load_ledge_front_y = (
        LID_LATCH_CAPTURE_RAIL_CENTER_Y + LID_LATCH_LOAD_LEDGE_RAIL_EMBED
    )
    load_ledge_back_y = recess_back_y - LID_LATCH_LOAD_LEDGE_BACK_OVERLAP
    load_ledge_half_width = (
        LID_LATCH_TROUGH_WIDTH / 2.0 + LID_LATCH_LOAD_LEDGE_AXIAL_OVERLAP
    )
    probe_dimensions = (1.0, 0.2, 0.2)

    def overlap_at(name, location, dimensions=probe_dimensions):
        probe = add_rounded_box(name, dimensions, location, bevel=0.0)
        try:
            _faces, volume = exact_transformed_intersection(
                lid,
                probe,
                second_location=location,
            )
        finally:
            bpy.data.objects.remove(probe, do_unlink=True)
        return volume

    minimum_solid_fill = math.prod(probe_dimensions) * 0.95
    back_wall_dimensions = (1.0, 0.5, 0.2)
    minimum_back_wall_fill = math.prod(back_wall_dimensions) * 0.95
    ledge_probe_dimensions = (0.5, 0.4, 0.4)
    minimum_ledge_fill = math.prod(ledge_probe_dimensions) * 0.95
    bay_air_volumes = []
    rail_volumes = []
    nub_recess_air_volumes = []
    load_ledge_volumes = []
    rail_ledge_bond_volumes = []
    ledge_back_bond_volumes = []
    back_wall_volumes = []
    for index, x in enumerate(LATCH_X_CENTERS, start=1):
        center_x = LID_DISPLAY_OFFSET_X + x
        bay_air_volumes.append(
            overlap_at(
                f"TEMPORARY_Lid_Latch_{index}_Open_Bay_Probe",
                (
                    center_x,
                    LID_LATCH_CAPTURE_RAIL_CENTER_Y,
                    LID_LATCH_CAPTURE_RAIL_CENTER_Z
                    - LID_LATCH_CAPTURE_RAIL_RADIUS
                    - 0.25,
                ),
            )
        )
        rail_volumes.append(
            overlap_at(
                f"TEMPORARY_Lid_Latch_{index}_Solid_Rail_Probe",
                (
                    center_x,
                    LID_LATCH_CAPTURE_RAIL_CENTER_Y,
                    LID_LATCH_CAPTURE_RAIL_CENTER_Z,
                ),
            )
        )
        nub_recess_air_volumes.append(
            overlap_at(
                f"TEMPORARY_Lid_Latch_{index}_Open_Retention_Boss_Recess_Probe",
                (
                    center_x,
                    LID_LATCH_CAPTURE_NUB_CENTER_Y,
                    LID_LATCH_CAPTURE_NUB_CENTER_Z,
                ),
            )
        )
        for probe_index, probe_x in enumerate(
            (
                center_x - load_ledge_half_width + 0.5,
                center_x,
                center_x + load_ledge_half_width - 0.5,
            ),
            start=1,
        ):
            load_ledge_volumes.append(
                overlap_at(
                    f"TEMPORARY_Lid_Latch_{index}_Load_Ledge_Probe_{probe_index}",
                    (
                        probe_x,
                        (load_ledge_back_y + load_ledge_front_y) / 2.0,
                        LID_LATCH_LOAD_LEDGE_CONTACT_Z + 0.6,
                    ),
                    ledge_probe_dimensions,
                )
            )
        rail_ledge_bond_volumes.append(
            overlap_at(
                f"TEMPORARY_Lid_Latch_{index}_Rail_Embedded_In_Ledge_Probe",
                (
                    center_x,
                    LID_LATCH_CAPTURE_RAIL_CENTER_Y,
                    LID_LATCH_LOAD_LEDGE_CONTACT_Z + 0.4,
                ),
                ledge_probe_dimensions,
            )
        )
        ledge_back_bond_volumes.append(
            overlap_at(
                f"TEMPORARY_Lid_Latch_{index}_Ledge_Back_Wall_Bond_Probe",
                (
                    center_x,
                    (load_ledge_back_y + recess_back_y) / 2.0,
                    LID_WALL_HEIGHT - 0.3,
                ),
                ledge_probe_dimensions,
            )
        )
        back_wall_volumes.append(
            overlap_at(
                f"TEMPORARY_Lid_Latch_{index}_Solid_Back_Wall_Probe",
                (
                    center_x,
                    (rim_inner_front_y + recess_back_y) / 2.0,
                    LID_LATCH_CAPTURE_RAIL_CENTER_Z - 1.0,
                ),
                back_wall_dimensions,
            )
        )
    if max(bay_air_volumes) > 1e-7:
        raise ValueError("Lid skirt filled the molded latch capture bay")
    if min(rail_volumes) < minimum_solid_fill:
        raise ValueError("A generated horizontal latch capture rail is hollow")
    if max(nub_recess_air_volumes) > 1e-7:
        raise ValueError("A generated latch retention-boss recess is obstructed")
    if min(load_ledge_volumes) < minimum_ledge_fill:
        raise ValueError("A generated latch load ledge is hollow or too narrow")
    if min(rail_ledge_bond_volumes) < minimum_ledge_fill:
        raise ValueError("A generated latch rail is not embedded in its load ledge")
    if min(ledge_back_bond_volumes) < minimum_ledge_fill:
        raise ValueError("A generated latch load ledge misses the lid back wall")
    if min(back_wall_volumes) < minimum_back_wall_fill:
        raise ValueError("A generated latch recess weakened its skirt back wall")
    print(
        "FIELD_CASE_LID_RAIL_VALID "
        f"bay_air_max={max(bay_air_volumes):.9f} "
        f"rail_solid_min={min(rail_volumes):.6f} "
        f"nub_recess_air_max={max(nub_recess_air_volumes):.9f} "
        f"load_ledge_solid_min={min(load_ledge_volumes):.6f} "
        f"rail_ledge_bond_min={min(rail_ledge_bond_volumes):.6f} "
        f"ledge_back_bond_min={min(ledge_back_bond_volumes):.6f} "
        f"back_wall_solid_min={min(back_wall_volumes):.6f}"
    )


def validate_built_latch_hook_capture(hook) -> None:
    """Prove the hook retains its flat bearing pad and round retention boss."""
    rail_local_y, _rail_local_z = latch_rail_in_hook_local_yz(LATCH_LEVER_CLOSED_ANGLE)
    rail_running_radius = (
        LID_LATCH_CAPTURE_RAIL_RADIUS + LATCH_CAPTURE_RAIL_PATH_CLEARANCE
    )
    upper_arm_inner_y = rail_local_y - rail_running_radius
    upper_arm_outer_y = upper_arm_inner_y - LATCH_CAPTURE_UPPER_ARM_THICKNESS
    _release_rail_y, release_rail_z = latch_rail_in_hook_local_yz(
        LATCH_CAPTURE_FULL_RELEASE_ANGLE
    )
    upper_arm_front_z = (
        release_rail_z - rail_running_radius + LATCH_CAPTURE_UPPER_ARM_FRONT_OVERLAP
    )
    nub_center_y, nub_center_z = installed_yz_in_hook_local(
        LATCH_LEVER_CLOSED_ANGLE,
        LATCH_CAPTURE_NUB_INSTALLED_Y,
        LATCH_CAPTURE_NUB_INSTALLED_Z,
    )
    upper_arm_back_z = nub_center_z + 0.5 * LATCH_CAPTURE_NUB_RADIUS
    root_boss_center_y, root_boss_center_z = installed_yz_in_hook_local(
        LATCH_LEVER_CLOSED_ANGLE,
        LATCH_CAPTURE_ROOT_BOSS_INSTALLED_Y,
        LATCH_CAPTURE_ROOT_BOSS_INSTALLED_Z,
    )

    def overlap_with_sphere(name, location, radius=0.18):
        probe = add_uv_sphere(name, radius, location, segments=24, ring_count=12)
        try:
            _faces, volume = exact_transformed_intersection(
                hook,
                probe,
                second_location=location,
            )
        finally:
            bpy.data.objects.remove(probe, do_unlink=True)
        return volume

    def overlap_with_cylinder(name, location, radius, length):
        probe = add_cylinder_x(name, radius, length, location, vertices=64)
        try:
            _faces, volume = exact_transformed_intersection(
                hook,
                probe,
                second_location=location,
                second_rotation=probe.rotation_euler.copy(),
            )
        finally:
            bpy.data.objects.remove(probe, do_unlink=True)
        return volume

    def overlap_with_extruded_loop(name, loop, x0, x1):
        probe = extrude_loop_x(name, loop, x0, x1)
        try:
            _faces, volume = exact_transformed_intersection(hook, probe)
        finally:
            bpy.data.objects.remove(probe, do_unlink=True)
        return volume

    arm_probe_z = (upper_arm_front_z + upper_arm_back_z) / 2.0
    arm_probe_y = (upper_arm_inner_y + upper_arm_outer_y) / 2.0
    arm_volumes = [
        overlap_with_sphere(
            f"TEMPORARY_Latch_Upper_Arm_Solid_Probe_{index}",
            (x, arm_probe_y, arm_probe_z),
        )
        for index, x in enumerate(
            (-LATCH_WIDTH / 2.0 + 0.5, 0.0, LATCH_WIDTH / 2.0 - 0.5),
            start=1,
        )
    ]
    core_length = (
        LATCH_CAPTURE_NUB_AXIAL_WIDTH - 2.0 * LATCH_CAPTURE_NUB_CORE_AXIAL_MARGIN
    )
    nub_core_radius = LATCH_CAPTURE_NUB_RADIUS - LATCH_CAPTURE_NUB_CORE_RADIAL_MARGIN
    root_core_radius = (
        LATCH_CAPTURE_NUB_ROOT_BOSS_RADIUS - LATCH_CAPTURE_NUB_CORE_RADIAL_MARGIN
    )
    nub_core_volume = overlap_with_cylinder(
        "TEMPORARY_Latch_Round_Boss_Full_Core_Probe",
        (0.0, nub_center_y, nub_center_z),
        nub_core_radius,
        core_length,
    )
    root_core_volume = overlap_with_cylinder(
        "TEMPORARY_Latch_Round_Boss_Root_Core_Probe",
        (0.0, root_boss_center_y, root_boss_center_z),
        root_core_radius,
        core_length,
    )
    neck_center_y = (nub_center_y + root_boss_center_y) / 2.0
    neck_center_z = (nub_center_z + root_boss_center_z) / 2.0
    neck_core_radius = 0.8
    neck_core_volume = overlap_with_cylinder(
        "TEMPORARY_Latch_Round_Boss_Neck_Core_Probe",
        (0.0, neck_center_y, neck_center_z),
        neck_core_radius,
        core_length,
    )
    pad_core_y0 = LATCH_CAPTURE_FLAT_PAD_OUTWARD_INSTALLED_Y + 0.1
    pad_core_y1 = LATCH_CAPTURE_FLAT_PAD_CASEWARD_INSTALLED_Y - 0.1
    pad_core_z0 = LATCH_CAPTURE_FLAT_PAD_BOTTOM_INSTALLED_Z + 0.05
    pad_core_z1 = LATCH_CAPTURE_FLAT_PAD_TOP_INSTALLED_Z - 0.2
    pad_core_loop = tuple(
        installed_yz_in_hook_local(
            LATCH_LEVER_CLOSED_ANGLE,
            installed_y,
            installed_z,
        )
        for installed_y, installed_z in (
            (pad_core_y0, pad_core_z0),
            (pad_core_y1, pad_core_z0),
            (pad_core_y1, pad_core_z1),
            (pad_core_y0, pad_core_z1),
        )
    )
    pad_core_x0 = -LATCH_CAPTURE_FLAT_PAD_AXIAL_WIDTH / 2.0 + 0.4
    pad_core_x1 = LATCH_CAPTURE_FLAT_PAD_AXIAL_WIDTH / 2.0 - 0.4
    pad_core_volume = overlap_with_extruded_loop(
        "TEMPORARY_Latch_Flat_Bearing_Pad_Core_Probe",
        pad_core_loop,
        pad_core_x0,
        pad_core_x1,
    )
    lower_jaw_local_y, lower_jaw_local_z = installed_yz_in_hook_local(
        LATCH_LEVER_CLOSED_ANGLE,
        -87.5,
        58.5,
    )
    lower_jaw_volume = overlap_with_sphere(
        "TEMPORARY_Latch_Obsolete_Lower_Jaw_Air_Probe",
        (0.0, lower_jaw_local_y, lower_jaw_local_z),
        radius=0.25,
    )
    minimum_arm_probe_volume = 4.0 / 3.0 * math.pi * 0.18**3 * 0.9
    if min(arm_volumes) < minimum_arm_probe_volume:
        raise ValueError(
            "Latch reinforced upper arm is not solid across its full width"
        )
    expected_nub_core_volume = math.pi * nub_core_radius**2 * core_length
    expected_root_core_volume = math.pi * root_core_radius**2 * core_length
    expected_neck_core_volume = math.pi * neck_core_radius**2 * core_length
    expected_pad_core_volume = (
        (pad_core_x1 - pad_core_x0)
        * (pad_core_y1 - pad_core_y0)
        * (pad_core_z1 - pad_core_z0)
    )
    if nub_core_volume < 0.95 * expected_nub_core_volume:
        raise ValueError("Latch round behind-rail boss lacks a full solid core")
    if root_core_volume < 0.95 * expected_root_core_volume:
        raise ValueError("Latch round behind-rail boss root is hollow or carved")
    if neck_core_volume < 0.95 * expected_neck_core_volume:
        raise ValueError("Latch round behind-rail boss has a thin folding neck")
    if pad_core_volume < 0.95 * expected_pad_core_volume:
        raise ValueError("Latch flat downward-bearing pad is hollow or sweep-carved")
    if lower_jaw_volume > 1e-7:
        raise ValueError("Obsolete lower latch jaw remains below the lid rail")
    print(
        "FIELD_CASE_LATCH_HOOK_CAPTURE_VALID "
        f"upper_arm_thickness={LATCH_CAPTURE_UPPER_ARM_THICKNESS:.2f} "
        f"upper_arm_solid_min={min(arm_volumes):.6f} "
        f"round_boss={2.0 * LATCH_CAPTURE_NUB_RADIUS:.2f}x"
        f"{LATCH_CAPTURE_NUB_AXIAL_WIDTH:.2f} "
        f"round_root_diameter={2.0 * LATCH_CAPTURE_NUB_ROOT_BOSS_RADIUS:.2f} "
        f"boss_core={nub_core_volume:.6f}/{expected_nub_core_volume:.6f} "
        f"root_core={root_core_volume:.6f}/{expected_root_core_volume:.6f} "
        f"neck_core={neck_core_volume:.6f}/{expected_neck_core_volume:.6f} "
        f"flat_pad_core={pad_core_volume:.6f}/{expected_pad_core_volume:.6f} "
        f"lower_jaw_air={lower_jaw_volume:.9f}"
    )


def validate_built_latch_impact_protectors(parts) -> None:
    """Prove the base/lid impact cheeks are solid and leave lever access open."""

    def overlap_at(part, name, location, dimensions):
        probe = add_rounded_box(name, dimensions, location, bevel=0.0)
        try:
            _faces, volume = exact_transformed_intersection(
                part,
                probe,
                second_location=location,
            )
        finally:
            bpy.data.objects.remove(probe, do_unlink=True)
        return volume

    base_probe_dimensions = (0.8, 0.5, 0.8)
    base_minimum_fill = math.prod(base_probe_dimensions) * 0.9
    base_guard_volumes = []
    base_bond_volumes = []
    access_air_volumes = []
    lid_guard_volumes = []
    lid_probe_dimensions = (0.8, 0.4, 0.4)
    lid_minimum_fill = math.prod(lid_probe_dimensions) * 0.9
    for index, x in enumerate(LATCH_X_CENTERS, start=1):
        access_air_volumes.append(
            overlap_at(
                parts["base"],
                f"TEMPORARY_Latch_{index}_Protector_Finger_Access_Probe",
                (x, LATCH_PROTECTOR_FRONT_Y + 1.0, 36.0),
                (LATCH_WIDTH - 1.0, 0.5, 1.0),
            )
        )
        for side in (-1.0, 1.0):
            protector_center_x = x + side * (
                LATCH_BASE_EAR_CENTER_OFFSET_X + LATCH_PROTECTOR_AXIAL_OUTWARD_SHIFT
            )
            base_guard_volumes.append(
                overlap_at(
                    parts["base"],
                    f"TEMPORARY_Latch_{index}_Base_Protector_Solid_Probe",
                    (protector_center_x, LATCH_PROTECTOR_FRONT_Y + 0.3, 40.0),
                    base_probe_dimensions,
                )
            )
            base_bond_volumes.append(
                overlap_at(
                    parts["base"],
                    f"TEMPORARY_Latch_{index}_Base_Protector_Bond_Probe",
                    (protector_center_x, LATCH_PROTECTOR_BODY_Y, 40.0),
                    base_probe_dimensions,
                )
            )
            lid_tower_center_x = (
                LID_DISPLAY_OFFSET_X
                + x
                + side
                * (LID_LATCH_TROUGH_WIDTH / 2.0 + LID_LATCH_TROUGH_SHOULDER_WIDTH / 2.0)
            )
            lid_tower_outer_y = (
                LID_LATCH_CAPTURE_RAIL_CENTER_Y
                + LID_LATCH_CAPTURE_RAIL_RADIUS
                + LID_LATCH_CAPTURE_TOWER_OUTSET
            )
            lid_tower_slope_start_y = CASE_DEPTH / 2.0 + LID_FLANGE_OUTSET - 1.0
            lid_tower_base_z = LID_FLANGE_EDGE_START_Z - LID_LATCH_TROUGH_SHOULDER_RISE
            lid_tower_slope_top_z = (
                lid_tower_base_z + lid_tower_outer_y - lid_tower_slope_start_y
            )
            lid_guard_volumes.append(
                overlap_at(
                    parts["lid"],
                    f"TEMPORARY_Latch_{index}_Lid_Protector_Solid_Probe",
                    (
                        lid_tower_center_x,
                        lid_tower_outer_y - 0.5,
                        lid_tower_slope_top_z - 0.25,
                    ),
                    lid_probe_dimensions,
                )
            )
    if min(base_guard_volumes) < base_minimum_fill:
        raise ValueError("A base latch impact protector is hollow")
    if min(base_bond_volumes) < base_minimum_fill:
        raise ValueError("A base latch impact protector is not bonded to the shell")
    if max(access_air_volumes) > 1e-7:
        raise ValueError("Base latch protectors obstruct lever finger access")
    if min(lid_guard_volumes) < lid_minimum_fill:
        raise ValueError("A lid latch impact protector is hollow")
    print(
        "FIELD_CASE_LATCH_PROTECTORS_VALID "
        f"base_thickness={LATCH_PROTECTOR_BASE_WIDTH:.2f} "
        f"base_solid_min={min(base_guard_volumes):.6f} "
        f"base_bond_min={min(base_bond_volumes):.6f} "
        f"lid_thickness={LID_LATCH_TROUGH_SHOULDER_WIDTH:.2f} "
        f"lid_solid_min={min(lid_guard_volumes):.6f} "
        f"finger_access_air_max={max(access_air_volumes):.9f}"
    )


def validate_built_latch_fixed_m3_hardware(parts) -> None:
    """Prove both recessed M3 fixed pivots fit and retain guard material."""
    base_path_overlaps = []
    lever_path_overlaps = []
    head_overlaps = []
    shaft_overlaps = []
    nut_overlaps = []
    countersink_floor_volumes = []
    nut_floor_volumes = []
    path_probe_radius = LATCH_FIXED_M3_CLEARANCE_DIAMETER / 2.0 - 0.05

    lever_path_probe = add_cylinder_x(
        "TEMPORARY_Latch_Lever_M3_Easy_Running_Path_Probe",
        path_probe_radius,
        LATCH_WIDTH - 0.2,
        (0.0, 0.0, 0.0),
        vertices=64,
    )
    try:
        _faces, lever_path_overlap = exact_transformed_intersection(
            parts["latch_lever"],
            lever_path_probe,
            second_location=lever_path_probe.location.copy(),
            second_rotation=lever_path_probe.rotation_euler.copy(),
        )
    finally:
        bpy.data.objects.remove(lever_path_probe, do_unlink=True)
    lever_path_overlaps.append(lever_path_overlap)

    floor_probe_dimensions = (0.3, 0.3, 0.3)
    minimum_floor_fill = math.prod(floor_probe_dimensions) * 0.9
    for index, latch_x in enumerate(LATCH_X_CENTERS, start=1):
        head_face_x, nut_face_x, outer_direction = latch_fixed_m3_guard_faces(
            latch_x
        )
        path_probe = add_cylinder_x(
            f"TEMPORARY_Latch_{index}_Base_M3_Easy_Running_Path_Probe",
            path_probe_radius,
            LATCH_FIXED_M3_GUARD_SPAN - 0.2,
            (latch_x, LATCH_BASE_PIVOT_Y, LATCH_BASE_PIVOT_Z),
            vertices=64,
        )
        try:
            _faces, path_overlap = exact_transformed_intersection(
                parts["base"],
                path_probe,
                second_location=path_probe.location.copy(),
                second_rotation=path_probe.rotation_euler.copy(),
            )
        finally:
            bpy.data.objects.remove(path_probe, do_unlink=True)
        base_path_overlaps.append(path_overlap)

        hardware = create_latch_fixed_m3_reference_hardware(
            f"TEMPORARY_Latch_{index}_Nominal_M3_Hardware_Envelope",
            latch_x,
            seat_clearance=0.05,
        )
        try:
            hardware_overlaps = []
            for hardware_part in hardware:
                _faces, overlap = exact_transformed_intersection(
                    parts["base"],
                    hardware_part,
                    second_location=hardware_part.location.copy(),
                    second_rotation=hardware_part.rotation_euler.copy(),
                )
                hardware_overlaps.append(overlap)
            head_overlaps.append(hardware_overlaps[0])
            shaft_overlaps.append(hardware_overlaps[1])
            nut_overlaps.append(hardware_overlaps[2])
        finally:
            for hardware_part in hardware:
                bpy.data.objects.remove(hardware_part, do_unlink=True)

        floor_specs = (
            (
                f"TEMPORARY_Latch_{index}_Countersink_Floor_Solid_Probe",
                (
                    head_face_x
                    - outer_direction
                    * (LATCH_FIXED_M3_COUNTERSINK_DEPTH + 0.25),
                    LATCH_BASE_PIVOT_Y,
                    LATCH_BASE_PIVOT_Z + 3.0,
                ),
                countersink_floor_volumes,
            ),
            (
                f"TEMPORARY_Latch_{index}_Nut_Recess_Floor_Solid_Probe",
                (
                    nut_face_x
                    + outer_direction * (LATCH_FIXED_M3_NUT_DEPTH + 0.25),
                    LATCH_BASE_PIVOT_Y,
                    LATCH_BASE_PIVOT_Z + 3.0,
                ),
                nut_floor_volumes,
            ),
        )
        for probe_name, probe_location, output in floor_specs:
            floor_probe = add_rounded_box(
                probe_name,
                floor_probe_dimensions,
                probe_location,
                bevel=0.0,
            )
            try:
                _faces, floor_volume = exact_transformed_intersection(
                    parts["base"],
                    floor_probe,
                    second_location=probe_location,
                )
            finally:
                bpy.data.objects.remove(floor_probe, do_unlink=True)
            output.append(floor_volume)

    maximum_air_overlap = max(
        *base_path_overlaps,
        *lever_path_overlaps,
        *head_overlaps,
        *shaft_overlaps,
        *nut_overlaps,
    )
    if maximum_air_overlap > 1e-6:
        raise ValueError(
            "Latch fixed-pivot M3 path or recessed hardware envelope is obstructed: "
            f"maximum_volume={maximum_air_overlap:.6f} "
            f"base_paths={base_path_overlaps} lever_paths={lever_path_overlaps} "
            f"heads={head_overlaps} shafts={shaft_overlaps} nuts={nut_overlaps}"
        )
    if min(countersink_floor_volumes) < minimum_floor_fill:
        raise ValueError(
            "A latch M3 countersink breaks through its guard: "
            f"volumes={countersink_floor_volumes} required={minimum_floor_fill}"
        )
    if min(nut_floor_volumes) < minimum_floor_fill:
        raise ValueError(
            "A latch captive M3 nut recess breaks through its guard: "
            f"volumes={nut_floor_volumes} required={minimum_floor_fill}"
        )

    countersink_seat_inset = (
        LATCH_FIXED_M3_COUNTERSINK_DIAMETER
        - LATCH_FIXED_M3_NOMINAL_HEAD_DIAMETER
    ) / 2.0
    thread_engagement = (
        LATCH_FIXED_M3_BOLT_LENGTH
        + countersink_seat_inset
        - (LATCH_FIXED_M3_GUARD_SPAN - LATCH_FIXED_M3_NUT_DEPTH)
    )
    print(
        "FIELD_CASE_LATCH_FIXED_M3_VALID "
        f"latches={len(LATCH_X_CENTERS)} "
        f"through_bore={LATCH_FIXED_M3_CLEARANCE_DIAMETER:.2f} "
        f"path_probe={2.0 * path_probe_radius:.2f} "
        f"air_overlap_max={maximum_air_overlap:.6f} "
        f"countersink={LATCH_FIXED_M3_COUNTERSINK_DIAMETER:.2f}x"
        f"{LATCH_FIXED_M3_COUNTERSINK_DEPTH:.2f} "
        f"nut_recess={LATCH_FIXED_M3_NUT_ACROSS_FLATS:.2f}x"
        f"{LATCH_FIXED_M3_NUT_DEPTH:.2f} "
        f"countersink_floor_min={min(countersink_floor_volumes):.6f} "
        f"nut_floor_min={min(nut_floor_volumes):.6f} "
        f"screw=M3x{LATCH_FIXED_M3_BOLT_LENGTH:.0f} "
        f"thread_engagement={thread_engagement:.2f}"
    )


def validate_installed_latch_mechanics(parts) -> None:
    seated_lid_location = (-LID_DISPLAY_OFFSET_X, 0.0, LATCH_LID_INSTALLED_Z)
    lid_rotation = (math.pi, 0.0, 0.0)
    sweep_degrees = abs(LATCH_LEVER_OPEN_ANGLE - LATCH_LEVER_CLOSED_ANGLE)
    sweep_steps = max(1, math.ceil(sweep_degrees / LATCH_SWEEP_STEP_DEGREES))
    axial_offsets = (
        -LATCH_BASE_EAR_AXIAL_CLEARANCE,
        0.0,
        LATCH_BASE_EAR_AXIAL_CLEARANCE,
    )
    maximum_lever_base_overlap = (0.0, LATCH_LEVER_CLOSED_ANGLE, 0.0, 0)
    maximum_hook_base_overlap = (0.0, LATCH_LEVER_CLOSED_ANGLE, 0.0, 0)
    maximum_link_overlap = (0.0, LATCH_LEVER_CLOSED_ANGLE, 0.0, 0)
    maximum_lid_overlap = (0.0, LATCH_LEVER_CLOSED_ANGLE, 0.0, 0)
    maximum_detent_overlap = (0.0, LATCH_LEVER_CLOSED_ANGLE, 0.0, 0)
    closed_hook_poses = {}
    seated_volumes = {}

    detent_bosses = []
    for side in LATCH_DETENT_SIDES:
        detent_ear_x = LATCH_X_CENTERS[1] + side * LATCH_BASE_EAR_CENTER_OFFSET_X
        detent_inner_face_x = detent_ear_x - side * LATCH_BASE_EAR_WIDTH / 2.0
        boss = add_uv_sphere(
            "TEMPORARY_Latch_Snap_Detent_Validation_Boss",
            LATCH_DETENT_BOSS_RADIUS,
            (
                detent_inner_face_x
                + side * (LATCH_DETENT_BOSS_RADIUS - LATCH_DETENT_BOSS_PROTRUSION),
                LATCH_BASE_PIVOT_Y + LATCH_DETENT_LOCAL_YZ[0],
                LATCH_BASE_PIVOT_Z + LATCH_DETENT_LOCAL_YZ[1],
            ),
        )
        detent_bosses.append(boss)

    def detent_intersection(lever_location, lever_rotation):
        face_count = 0
        volume = 0.0
        for boss in detent_bosses:
            faces, partial_volume = exact_transformed_intersection(
                boss,
                parts["latch_lever"],
                first_location=boss.location,
                second_location=lever_location,
                second_rotation=lever_rotation,
            )
            face_count += faces
            volume += partial_volume
        return face_count, volume

    for axial_offset in axial_offsets:
        lever_location = (
            LATCH_X_CENTERS[1] + axial_offset,
            LATCH_BASE_PIVOT_Y,
            LATCH_BASE_PIVOT_Z,
        )
        for sample_index in range(sweep_steps + 1):
            sample_ratio = sample_index / sweep_steps
            lever_angle = LATCH_LEVER_CLOSED_ANGLE + sample_ratio * (
                LATCH_LEVER_OPEN_ANGLE - LATCH_LEVER_CLOSED_ANGLE
            )
            hook_angle = latch_hook_global_angle_degrees(lever_angle)
            lever_radians = math.radians(lever_angle)
            hook_origin_y, hook_origin_z = latch_hook_origin_yz(lever_angle)
            hook_location = (
                lever_location[0],
                hook_origin_y,
                hook_origin_z,
            )
            lever_rotation = (lever_radians, 0.0, 0.0)
            hook_rotation = (math.radians(hook_angle), 0.0, 0.0)

            lever_base_faces, lever_base_volume = exact_transformed_intersection(
                parts["base"],
                parts["latch_lever"],
                second_location=lever_location,
                second_rotation=lever_rotation,
            )
            if lever_base_volume > maximum_lever_base_overlap[0]:
                maximum_lever_base_overlap = (
                    lever_base_volume,
                    lever_angle,
                    axial_offset,
                    lever_base_faces,
                )
            detent_faces, detent_volume = detent_intersection(
                lever_location, lever_rotation
            )
            if detent_volume > maximum_detent_overlap[0]:
                maximum_detent_overlap = (
                    detent_volume,
                    lever_angle,
                    axial_offset,
                    detent_faces,
                )
            unexpected_lever_base_volume = max(0.0, lever_base_volume - detent_volume)
            axial_contact_limit = (
                LATCH_SWEEP_RESIDUAL_VOLUME_LIMIT
                if math.isclose(axial_offset, 0.0, abs_tol=1e-9)
                else LATCH_AXIAL_CONTACT_RESIDUAL_VOLUME_LIMIT
            )
            if unexpected_lever_base_volume > axial_contact_limit:
                raise ValueError(
                    "Coupled latch lever sweep collides with the base: "
                    f"angle={lever_angle:.2f} axial={axial_offset:+.2f} "
                    f"faces={lever_base_faces} volume={lever_base_volume:.6f} "
                    f"detent_volume={detent_volume:.6f}"
                )
            if (
                lever_angle <= LATCH_DETENT_RELEASE_ANGLE
                and detent_volume > LATCH_DETENT_RELEASE_RESIDUAL_VOLUME_LIMIT
            ):
                raise ValueError(
                    "Latch snap detents do not clear after release: "
                    f"angle={lever_angle:.2f} axial={axial_offset:+.2f} "
                    f"volume={detent_volume:.6f}"
                )

            link_faces, link_volume = exact_transformed_intersection(
                parts["latch_lever"],
                parts["latch_hook"],
                first_location=lever_location,
                first_rotation=lever_rotation,
                second_location=hook_location,
                second_rotation=hook_rotation,
            )
            if link_volume > maximum_link_overlap[0]:
                maximum_link_overlap = (
                    link_volume,
                    lever_angle,
                    axial_offset,
                    link_faces,
                )
            if link_volume > LATCH_SWEEP_RESIDUAL_VOLUME_LIMIT:
                raise ValueError(
                    "Coupled latch sweep relief blocks the moving hook: "
                    f"lever_angle={lever_angle:.2f} axial={axial_offset:+.2f} "
                    f"faces={link_faces} volume={link_volume:.6f}"
                )

            hook_base_faces, hook_base_volume = exact_transformed_intersection(
                parts["base"],
                parts["latch_hook"],
                second_location=hook_location,
                second_rotation=hook_rotation,
            )
            if hook_base_volume > maximum_hook_base_overlap[0]:
                maximum_hook_base_overlap = (
                    hook_base_volume,
                    lever_angle,
                    axial_offset,
                    hook_base_faces,
                )
            if hook_base_volume > axial_contact_limit:
                raise ValueError(
                    "Coupled latch hook sweep collides with the base: "
                    f"lever_angle={lever_angle:.2f} axial={axial_offset:+.2f} "
                    f"faces={hook_base_faces} volume={hook_base_volume:.6f}"
                )

            lid_faces, lid_volume = exact_transformed_intersection(
                parts["lid"],
                parts["latch_hook"],
                first_location=seated_lid_location,
                first_rotation=lid_rotation,
                second_location=hook_location,
                second_rotation=hook_rotation,
            )
            if lid_volume > maximum_lid_overlap[0]:
                maximum_lid_overlap = (
                    lid_volume,
                    lever_angle,
                    axial_offset,
                    lid_faces,
                )
            if lid_volume > LATCH_SWEEP_RESIDUAL_VOLUME_LIMIT:
                _debug_faces, _debug_volume, collision_bounds = (
                    exact_transformed_intersection(
                        parts["lid"],
                        parts["latch_hook"],
                        first_location=seated_lid_location,
                        first_rotation=lid_rotation,
                        second_location=hook_location,
                        second_rotation=hook_rotation,
                        return_bounds=True,
                    )
                )
                raise ValueError(
                    "Coupled latch release sweep collides with the seated lid rim: "
                    f"lever_angle={lever_angle:.2f} axial={axial_offset:+.2f} "
                    f"faces={lid_faces} volume={lid_volume:.6f} "
                    f"bounds={collision_bounds}"
                )
            if sample_index == 0:
                closed_hook_poses[axial_offset] = (hook_location, hook_rotation)
                seated_volumes[axial_offset] = lid_volume

    if len(closed_hook_poses) != len(axial_offsets):
        raise ValueError("Coupled latch validation did not sample every closed pose")

    # The 2-degree rigid-body sweep above is appropriate for gross collision
    # checks but can step over a narrow snap peak. Measure both opposed bosses
    # at quarter-degree spacing at the center and both axial-play extremes.
    detent_sweep_degrees = abs(LATCH_DETENT_RELEASE_ANGLE - LATCH_LEVER_CLOSED_ANGLE)
    detent_sweep_steps = max(
        1, math.ceil(detent_sweep_degrees / LATCH_DETENT_SWEEP_STEP_DEGREES)
    )
    detent_results = {}
    for axial_offset in axial_offsets:
        lever_location = (
            LATCH_X_CENTERS[1] + axial_offset,
            LATCH_BASE_PIVOT_Y,
            LATCH_BASE_PIVOT_Z,
        )
        peak = (0.0, LATCH_LEVER_CLOSED_ANGLE, 0)
        closed_volume = None
        released_volume = None
        for sample_index in range(detent_sweep_steps + 1):
            sample_ratio = sample_index / detent_sweep_steps
            lever_angle = LATCH_LEVER_CLOSED_ANGLE + sample_ratio * (
                LATCH_DETENT_RELEASE_ANGLE - LATCH_LEVER_CLOSED_ANGLE
            )
            detent_faces, detent_volume = detent_intersection(
                lever_location,
                (math.radians(lever_angle), 0.0, 0.0),
            )
            if detent_volume > peak[0]:
                peak = (detent_volume, lever_angle, detent_faces)
            if detent_volume > maximum_detent_overlap[0]:
                maximum_detent_overlap = (
                    detent_volume,
                    lever_angle,
                    axial_offset,
                    detent_faces,
                )
            if sample_index == 0:
                closed_volume = detent_volume
            if sample_index == detent_sweep_steps:
                released_volume = detent_volume
        if closed_volume is None or released_volume is None:
            raise ValueError("Latch detent sweep did not sample both end poses")
        if closed_volume > 1e-6:
            raise ValueError(
                "Latch detents have no closed-pose axial clearance: "
                f"axial={axial_offset:+.2f} volume={closed_volume:.6f}"
            )
        if peak[0] < LATCH_DETENT_MIN_PEAK_VOLUME:
            raise ValueError(
                "Latch snap detent release bump is too weak: "
                f"axial={axial_offset:+.2f} peak={peak[0]:.6f}"
            )
        if released_volume > LATCH_DETENT_RELEASE_RESIDUAL_VOLUME_LIMIT:
            raise ValueError(
                "Latch snap detents remain engaged at their release angle: "
                f"axial={axial_offset:+.2f} volume={released_volume:.6f}"
            )
        detent_results[axial_offset] = (peak, closed_volume, released_volume)

    for boss in detent_bosses:
        bpy.data.objects.remove(boss, do_unlink=True)

    wrong_way_radians = math.radians(LATCH_WRONG_WAY_STOP_ANGLE)
    wrong_way_volumes = []
    for axial_offset in axial_offsets:
        lever_location = (
            LATCH_X_CENTERS[1] + axial_offset,
            LATCH_BASE_PIVOT_Y,
            LATCH_BASE_PIVOT_Z,
        )
        wrong_way_faces, wrong_way_volume = exact_transformed_intersection(
            parts["base"],
            parts["latch_lever"],
            second_location=lever_location,
            second_rotation=(wrong_way_radians, 0.0, 0.0),
        )
        if not wrong_way_faces or wrong_way_volume < LATCH_WRONG_WAY_STOP_MIN_VOLUME:
            raise ValueError(
                "Closed latch lever is not positively stopped across axial play"
            )
        wrong_way_volumes.append(wrong_way_volume)

    capture_lid_location = (
        seated_lid_location[0],
        seated_lid_location[1],
        seated_lid_location[2] + LATCH_MAX_CAPTURE_FREE_LIFT,
    )
    uncompressed_lid_location = (
        seated_lid_location[0],
        seated_lid_location[1],
        seated_lid_location[2] + LID_LATCH_LIP_DRAW,
    )
    capture_volumes = []
    preload_volumes = []
    outward_peel_volumes = []
    flat_pad_lift_volumes = []
    flat_pad_preload_volumes = []
    central_capture_rail = add_cylinder_x(
        "TEMPORARY_Central_Lid_Rail_Outward_Peel_Probe",
        LID_LATCH_CAPTURE_RAIL_RADIUS,
        LATCH_CAPTURE_NUB_AXIAL_WIDTH - 2.0 * LATCH_BASE_EAR_AXIAL_CLEARANCE,
        (
            LATCH_X_CENTERS[1],
            LATCH_CAPTURE_RAIL_INSTALLED_Y,
            LATCH_CAPTURE_RAIL_INSTALLED_Z,
        ),
        vertices=64,
    )
    flat_ledge_probe_dimensions = (
        LATCH_CAPTURE_FLAT_PAD_AXIAL_WIDTH - 2.0 * LATCH_BASE_EAR_AXIAL_CLEARANCE,
        LATCH_CAPTURE_FLAT_PAD_CASEWARD_LENGTH + 0.4,
        LID_LATCH_LOAD_LEDGE_THICKNESS,
    )
    flat_ledge_probe_location = (
        LATCH_X_CENTERS[1],
        (
            LATCH_CAPTURE_FLAT_PAD_OUTWARD_INSTALLED_Y
            + LATCH_CAPTURE_FLAT_PAD_CASEWARD_INSTALLED_Y
        )
        / 2.0,
        LATCH_CAPTURE_LOAD_LEDGE_INSTALLED_Z - LID_LATCH_LOAD_LEDGE_THICKNESS / 2.0,
    )
    central_load_ledge = add_rounded_box(
        "TEMPORARY_Central_Lid_Flat_Load_Ledge_Probe",
        flat_ledge_probe_dimensions,
        flat_ledge_probe_location,
        bevel=0.0,
    )
    for axial_offset in axial_offsets:
        closed_hook_location, closed_hook_rotation = closed_hook_poses[axial_offset]
        capture_faces, capture_volume = exact_transformed_intersection(
            parts["lid"],
            parts["latch_hook"],
            first_location=capture_lid_location,
            first_rotation=lid_rotation,
            second_location=closed_hook_location,
            second_rotation=closed_hook_rotation,
        )
        if not capture_faces or capture_volume < 0.01:
            raise ValueError(
                "Closed hook no longer captures lid lift across axial play: "
                f"axial={axial_offset:+.2f} volume={capture_volume:.6f}"
            )
        capture_volumes.append(capture_volume)

        flat_lift_location = (
            flat_ledge_probe_location[0],
            flat_ledge_probe_location[1],
            flat_ledge_probe_location[2] + LATCH_MAX_CAPTURE_FREE_LIFT,
        )
        flat_lift_faces, flat_lift_volume = exact_transformed_intersection(
            central_load_ledge,
            parts["latch_hook"],
            first_location=flat_lift_location,
            second_location=closed_hook_location,
            second_rotation=closed_hook_rotation,
        )
        if not flat_lift_faces or flat_lift_volume < 0.05:
            raise ValueError(
                "Flat latch pad no longer captures attempted lid lift: "
                f"axial={axial_offset:+.2f} volume={flat_lift_volume:.6f}"
            )
        flat_pad_lift_volumes.append(flat_lift_volume)

        preload_faces, preload_volume = exact_transformed_intersection(
            parts["lid"],
            parts["latch_hook"],
            first_location=uncompressed_lid_location,
            first_rotation=lid_rotation,
            second_location=closed_hook_location,
            second_rotation=closed_hook_rotation,
        )
        if not preload_faces or preload_volume < 0.1:
            raise ValueError(
                "Closed latch no longer preloads its capture rail across axial play: "
                f"axial={axial_offset:+.2f} volume={preload_volume:.6f}"
            )
        preload_volumes.append(preload_volume)

        flat_preload_location = (
            flat_ledge_probe_location[0],
            flat_ledge_probe_location[1],
            flat_ledge_probe_location[2] + LID_LATCH_LIP_DRAW,
        )
        flat_preload_faces, flat_preload_volume = exact_transformed_intersection(
            central_load_ledge,
            parts["latch_hook"],
            first_location=flat_preload_location,
            second_location=closed_hook_location,
            second_rotation=closed_hook_rotation,
        )
        if not flat_preload_faces or flat_preload_volume < 0.5:
            raise ValueError(
                "Flat latch pad no longer presses down on the lid ledge: "
                f"axial={axial_offset:+.2f} volume={flat_preload_volume:.6f}"
            )
        flat_pad_preload_volumes.append(flat_preload_volume)

        peeled_hook_location = (
            closed_hook_location[0],
            closed_hook_location[1] - LATCH_CAPTURE_OUTWARD_PEEL_TRAVEL,
            closed_hook_location[2],
        )
        peel_faces, peel_volume = exact_transformed_intersection(
            central_capture_rail,
            parts["latch_hook"],
            first_location=central_capture_rail.location,
            second_location=peeled_hook_location,
            second_rotation=closed_hook_rotation,
        )
        if not peel_faces or peel_volume < LATCH_CAPTURE_OUTWARD_PEEL_MIN_VOLUME:
            raise ValueError(
                "Closed hook can peel outward past the behind-rail nub: "
                f"axial={axial_offset:+.2f} volume={peel_volume:.6f}"
            )
        outward_peel_volumes.append(peel_volume)
    bpy.data.objects.remove(central_capture_rail, do_unlink=True)
    bpy.data.objects.remove(central_load_ledge, do_unlink=True)

    guarded_capture_volumes = []
    released_capture_volumes = []
    for lever_angle, output, require_capture in (
        (LATCH_CAPTURE_RELEASE_GUARD_ANGLE, guarded_capture_volumes, True),
        (LATCH_CAPTURE_FULL_RELEASE_ANGLE, released_capture_volumes, False),
    ):
        hook_angle = latch_hook_global_angle_degrees(lever_angle)
        hook_origin_y, hook_origin_z = latch_hook_origin_yz(lever_angle)
        for axial_offset in axial_offsets:
            hook_location = (
                LATCH_X_CENTERS[1] + axial_offset,
                hook_origin_y,
                hook_origin_z,
            )
            hook_rotation = (math.radians(hook_angle), 0.0, 0.0)
            faces, volume, bounds = exact_transformed_intersection(
                parts["lid"],
                parts["latch_hook"],
                first_location=uncompressed_lid_location,
                first_rotation=lid_rotation,
                second_location=hook_location,
                second_rotation=hook_rotation,
                return_bounds=True,
            )
            if require_capture and (
                not faces or volume < LATCH_CAPTURE_RELEASE_GUARD_MIN_VOLUME
            ):
                raise ValueError(
                    "Latch hook releases the horizontal rail before deliberate opening: "
                    f"axial={axial_offset:+.2f} "
                    f"lever={lever_angle:.2f} volume={volume:.6f}"
                )
            if not require_capture and volume > LATCH_SWEEP_RESIDUAL_VOLUME_LIMIT:
                raise ValueError(
                    "Latch hook does not fully release the horizontal rail: "
                    f"axial={axial_offset:+.2f} "
                    f"lever={lever_angle:.2f} faces={faces} volume={volume:.6f} "
                    f"bounds={bounds}"
                )
            output.append(volume)

    toggle_angle = math.degrees(
        math.atan(LATCH_LINK_PIVOT_LOCAL_YZ[0] / LATCH_LINK_PIVOT_LOCAL_YZ[1])
    )
    toggle_radians = math.radians(toggle_angle)
    toggle_offset_z = (
        math.sin(toggle_radians) * LATCH_LINK_PIVOT_LOCAL_YZ[0]
        + math.cos(toggle_radians) * LATCH_LINK_PIVOT_LOCAL_YZ[1]
    )
    closed_offset_z = LATCH_LINK_PIVOT_LOCAL_YZ[1]
    over_center_depth = closed_offset_z - toggle_offset_z
    if not LATCH_LEVER_OPEN_ANGLE < toggle_angle < LATCH_LEVER_CLOSED_ANGLE:
        raise ValueError("Latch moving pivot no longer crosses an over-center position")
    if over_center_depth < 0.02:
        raise ValueError("Latch over-center travel is too shallow to retain closure")
    minimum_detent_peak = min(
        (result[0][0], axial_offset, result[0][1])
        for axial_offset, result in detent_results.items()
    )
    maximum_closed_detent = max(result[1] for result in detent_results.values())
    maximum_released_detent = max(result[2] for result in detent_results.values())
    print(
        "FIELD_CASE_INSTALLED_LATCH_VALID "
        f"coupled_samples={len(axial_offsets) * (sweep_steps + 1)} "
        f"detent_samples={len(axial_offsets) * (detent_sweep_steps + 1)} "
        f"axial_range=+/-{LATCH_BASE_EAR_AXIAL_CLEARANCE:.2f} "
        f"lever_base_sweep_intersection={maximum_lever_base_overlap[0]:.6f} "
        f"snap_detent_peak_min={minimum_detent_peak[0]:.6f}@"
        f"{minimum_detent_peak[2]:.2f}deg/axial{minimum_detent_peak[1]:+.2f} "
        f"snap_detent_peak_max={maximum_detent_overlap[0]:.6f}@"
        f"{maximum_detent_overlap[1]:.2f}deg/"
        f"axial{maximum_detent_overlap[2]:+.2f} "
        f"detent_closed_max={maximum_closed_detent:.6f} "
        f"detent_released_max={maximum_released_detent:.6f}@"
        f"{LATCH_DETENT_RELEASE_ANGLE:.2f}deg "
        f"hook_base_sweep_intersection={maximum_hook_base_overlap[0]:.6f} "
        f"link_sweep_intersection={maximum_link_overlap[0]:.6f} "
        f"lid_release_sweep_intersection={maximum_lid_overlap[0]:.6f} "
        f"capture_at_{LATCH_MAX_CAPTURE_FREE_LIFT:.2f}mm_min="
        f"{min(capture_volumes):.6f} "
        f"uncompressed_rail_preload_min={min(preload_volumes):.6f} "
        f"flat_pad_lift_capture_min={min(flat_pad_lift_volumes):.6f} "
        f"flat_pad_preload_min={min(flat_pad_preload_volumes):.6f} "
        f"outward_peel_capture_min={min(outward_peel_volumes):.6f}@"
        f"{LATCH_CAPTURE_OUTWARD_PEEL_TRAVEL:.2f}mm "
        f"rail_guard_at_{LATCH_CAPTURE_RELEASE_GUARD_ANGLE:.2f}deg_min="
        f"{min(guarded_capture_volumes):.6f} "
        f"rail_release_at_{LATCH_CAPTURE_FULL_RELEASE_ANGLE:.2f}deg_max="
        f"{max(released_capture_volumes):.6f} "
        f"seated_intersection_max={max(seated_volumes.values()):.6f} "
        f"over_center_angle={toggle_angle:.2f} "
        f"over_center_depth={over_center_depth:.3f}"
        f" wrong_way_stop_min={min(wrong_way_volumes):.6f}"
    )


def validate_installed_handle_mechanics(parts) -> None:
    """Sweep the reinforced moving handle through its complete working arc."""
    sweep_steps = max(1, math.ceil(90.0 / HANDLE_SWEEP_STEP_DEGREES))
    maximum_overlap = (0.0, 0.0, 0)
    local_pivot_z = HANDLE_BAR_THICKNESS / 2.0
    for sample_index in range(sweep_steps + 1):
        angle = 90.0 * sample_index / sweep_steps
        radians = math.radians(angle)
        handle_location = (
            0.0,
            HANDLE_PIVOT_Y + math.sin(radians) * local_pivot_z,
            HANDLE_PIVOT_Z - math.cos(radians) * local_pivot_z,
        )
        faces, volume = exact_transformed_intersection(
            parts["base"],
            parts["handle_bar"],
            second_location=handle_location,
            second_rotation=(radians, 0.0, 0.0),
        )
        if volume > maximum_overlap[0]:
            maximum_overlap = (volume, angle, faces)
        if volume > HANDLE_SWEEP_RESIDUAL_VOLUME_LIMIT:
            raise ValueError(
                "Pivoting handle sweep collides with the reinforced case mounts: "
                f"angle={angle:.2f} faces={faces} volume={volume:.6f}"
            )
    print(
        "FIELD_CASE_INSTALLED_HANDLE_VALID "
        f"samples={sweep_steps + 1} "
        f"sweep=0.00-90.00deg "
        f"maximum_intersection={maximum_overlap[0]:.6f}@"
        f"{maximum_overlap[1]:.2f}deg"
    )


def installed_lid_pose(open_angle_degrees, lift=0.0):
    """Return a lid transform with its receiver axis fixed on the base rod."""
    rotation_x = math.pi - math.radians(open_angle_degrees)
    local_axis_y = -HINGE_AXIS_Y
    local_axis_z = LID_WALL_HEIGHT
    rotated_axis_y = (
        math.cos(rotation_x) * local_axis_y
        - math.sin(rotation_x) * local_axis_z
    )
    rotated_axis_z = (
        math.sin(rotation_x) * local_axis_y
        + math.cos(rotation_x) * local_axis_z
    )
    return (
        (
            -LID_DISPLAY_OFFSET_X,
            HINGE_AXIS_Y - rotated_axis_y,
            BASE_HEIGHT - rotated_axis_z + lift,
        ),
        (rotation_x, 0.0, 0.0),
    )


def validate_installed_lid_hinge_release(parts) -> None:
    """Prove the actual slot path stays blocked until deliberate release."""
    release_travel = (
        HINGE_OUTER_DIAMETER / 2.0
        + HINGE_ROD_DIAMETER / 2.0
        + 0.2
    )
    maximum_release_overlap = 0.0
    maximum_seated_axial_contact = 0.0
    minimum_pre_release_block = None
    maximum_base_lid_release_overlap = 0.0
    blocked_steps = math.ceil(
        HINGE_LID_PRE_RELEASE_BLOCK_ANGLE_DEGREES
        / HINGE_LID_PRE_RELEASE_SWEEP_STEP_DEGREES
    )
    blocked_angles = tuple(
        HINGE_LID_PRE_RELEASE_BLOCK_ANGLE_DEGREES
        * step
        / blocked_steps
        for step in range(blocked_steps + 1)
    )
    left_stop_inner_face = (
        HINGE_BASE_SEGMENTS[0][0] - HINGE_LID_END_STOP_BASE_CLEARANCE
    )
    right_stop_inner_face = (
        HINGE_BASE_SEGMENTS[-1][1] + HINGE_LID_END_STOP_BASE_CLEARANCE
    )
    rod_axial_offsets = (
        -(
            HINGE_ROD_X0
            - left_stop_inner_face
            - HINGE_ROD_RELEASE_AXIAL_VALIDATION_INSET
        ),
        0.0,
        right_stop_inner_face
        - HINGE_ROD_X1
        - HINGE_ROD_RELEASE_AXIAL_VALIDATION_INSET,
    )
    rod_probe = add_cylinder_x(
        "TEMPORARY_Installed_Full_151mm_Hinge_Rod_Probe",
        HINGE_ROD_DIAMETER / 2.0,
        HINGE_ROD_X1 - HINGE_ROD_X0,
        (0.0, 0.0, 0.0),
        vertices=90,
    )
    centered_rod_location = (
        (HINGE_ROD_X0 + HINGE_ROD_X1) / 2.0,
        HINGE_AXIS_Y,
        BASE_HEIGHT,
    )
    try:
        for blocked_angle in blocked_angles:
            seated_location, blocked_rotation = installed_lid_pose(blocked_angle)
            escape_y, escape_z = lid_hinge_escape_global_yz(blocked_angle)
            maximum_path_block = 0.0
            for sample_index in range(1, HINGE_LID_RELEASE_PATH_SAMPLES):
                sample_travel = release_travel * sample_index / (
                    HINGE_LID_RELEASE_PATH_SAMPLES - 1
                )
                blocked_location = (
                    seated_location[0],
                    seated_location[1] + escape_y * sample_travel,
                    seated_location[2] + escape_z * sample_travel,
                )
                _rod_faces, rod_block = exact_transformed_intersection(
                    parts["lid"],
                    rod_probe,
                    first_location=blocked_location,
                    first_rotation=blocked_rotation,
                    second_location=centered_rod_location,
                    second_rotation=rod_probe.rotation_euler.copy(),
                )
                _base_faces, base_block = exact_transformed_intersection(
                    parts["base"],
                    parts["lid"],
                    second_location=blocked_location,
                    second_rotation=blocked_rotation,
                )
                maximum_path_block = max(
                    maximum_path_block,
                    rod_block,
                    base_block,
                )
            if maximum_path_block <= 1e-6:
                raise ValueError(
                    "Lid can escape along its slot before the release angle: "
                    f"angle={blocked_angle:.2f} travel={release_travel:.3f}"
                )
            minimum_pre_release_block = (
                maximum_path_block
                if minimum_pre_release_block is None
                else min(minimum_pre_release_block, maximum_path_block)
            )

        release_location, release_rotation = installed_lid_pose(
            HINGE_LID_RELEASE_ANGLE_DEGREES
        )
        escape_y, escape_z = lid_hinge_escape_global_yz(
            HINGE_LID_RELEASE_ANGLE_DEGREES
        )
        for axial_offset in rod_axial_offsets:
            rod_location = (
                centered_rod_location[0] + axial_offset,
                centered_rod_location[1],
                centered_rod_location[2],
            )
            for sample_index in range(HINGE_LID_RELEASE_PATH_SAMPLES):
                sample_travel = release_travel * sample_index / (
                    HINGE_LID_RELEASE_PATH_SAMPLES - 1
                )
                lid_location = (
                    release_location[0],
                    release_location[1] + escape_y * sample_travel,
                    release_location[2] + escape_z * sample_travel,
                )
                _release_faces, release_overlap = exact_transformed_intersection(
                    parts["lid"],
                    rod_probe,
                    first_location=lid_location,
                    first_rotation=release_rotation,
                    second_location=rod_location,
                    second_rotation=rod_probe.rotation_euler.copy(),
                )
                if sample_index == 0:
                    maximum_seated_axial_contact = max(
                        maximum_seated_axial_contact,
                        release_overlap,
                    )
                elif release_overlap > 1e-6:
                    raise ValueError(
                        "Lid hinge obstructs its full-rod release path: "
                        f"axial={axial_offset:+.3f} sample={sample_index} "
                        f"angle={HINGE_LID_RELEASE_ANGLE_DEGREES:.1f} "
                        f"travel={sample_travel:.3f} "
                        f"volume={release_overlap:.6f}"
                    )
                if sample_index > 0:
                    maximum_release_overlap = max(
                        maximum_release_overlap,
                        release_overlap,
                    )
        for sample_index in range(HINGE_LID_RELEASE_PATH_SAMPLES):
            sample_travel = release_travel * sample_index / (
                HINGE_LID_RELEASE_PATH_SAMPLES - 1
            )
            lid_location = (
                release_location[0],
                release_location[1] + escape_y * sample_travel,
                release_location[2] + escape_z * sample_travel,
            )
            _faces, base_lid_overlap = exact_transformed_intersection(
                parts["base"],
                parts["lid"],
                second_location=lid_location,
                second_rotation=release_rotation,
            )
            if base_lid_overlap > 1e-6:
                raise ValueError(
                    "Base obstructs lid travel at the hinge release angle: "
                    f"sample={sample_index} travel={sample_travel:.3f} "
                    f"volume={base_lid_overlap:.6f}"
                )
            maximum_base_lid_release_overlap = max(
                maximum_base_lid_release_overlap,
                base_lid_overlap,
            )
    finally:
        bpy.data.objects.remove(rod_probe, do_unlink=True)

    print(
        "FIELD_CASE_LID_HINGE_RELEASE_VALID "
        f"blocked_angles=0.0-{blocked_angles[-1]:.1f} "
        f"blocked_angle_samples={len(blocked_angles)} "
        f"blocked_path_samples="
        f"{len(blocked_angles) * (HINGE_LID_RELEASE_PATH_SAMPLES - 1)} "
        f"blocked_intersection_min={minimum_pre_release_block:.6f} "
        f"release_angle={HINGE_LID_RELEASE_ANGLE_DEGREES:.1f} "
        f"release_full_rod_samples="
        f"{len(rod_axial_offsets) * HINGE_LID_RELEASE_PATH_SAMPLES} "
        f"rod_axial_offsets={','.join(f'{value:+.2f}' for value in rod_axial_offsets)} "
        f"release_travel={release_travel:.3f} "
        f"seated_axial_contact_max={maximum_seated_axial_contact:.6f} "
        f"rod_overlap_max={maximum_release_overlap:.6f} "
        f"base_overlap_max={maximum_base_lid_release_overlap:.6f}"
    )


def validate_installed_case_hinge_sweep(parts) -> None:
    """Reject positive-volume base/lid collision through the working sweep."""
    sweep_steps = math.ceil(
        HINGE_OPEN_SWEEP_MAX_ANGLE_DEGREES / HINGE_OPEN_SWEEP_STEP_DEGREES
    )
    maximum_overlap = (0.0, 0.0)
    for sample_index in range(sweep_steps + 1):
        open_angle = (
            HINGE_OPEN_SWEEP_MAX_ANGLE_DEGREES
            * sample_index
            / sweep_steps
        )
        lid_location, lid_rotation = installed_lid_pose(
            open_angle,
            0.01 if sample_index == 0 else 0.0,
        )
        _faces, overlap = exact_transformed_intersection(
            parts["base"],
            parts["lid"],
            second_location=lid_location,
            second_rotation=lid_rotation,
        )
        if overlap > maximum_overlap[0]:
            maximum_overlap = (overlap, open_angle)
        if overlap > 1e-6:
            raise ValueError(
                "Base/lid hinge sweep collides: "
                f"angle={open_angle:.2f} volume={overlap:.6f}"
            )
    print(
        "FIELD_CASE_HINGE_SWEEP_VALID "
        f"samples={sweep_steps + 1} "
        f"range=0.0-{HINGE_OPEN_SWEEP_MAX_ANGLE_DEGREES:.1f}deg "
        f"maximum_intersection={maximum_overlap[0]:.6f}@"
        f"{maximum_overlap[1]:.2f}deg"
    )


def validate_installed_case_closure(parts) -> None:
    """Reject positive-volume base/lid interference at the hard hinge seat."""
    # A 0.01 mm lift avoids treating the intentionally coincident hard-stop
    # surfaces as Boolean volume while remaining far smaller than printable
    # clearance.  Any unrelieved knuckle/rim collision remains positive here.
    near_seated_lid_location, closed_lid_rotation = installed_lid_pose(0.0, 0.01)
    faces, volume, bounds = exact_transformed_intersection(
        parts["base"],
        parts["lid"],
        second_location=near_seated_lid_location,
        second_rotation=closed_lid_rotation,
        return_bounds=True,
    )
    if faces or volume > 1e-6:
        raise ValueError(
            "Closed base/lid geometry still collides around the hinge: "
            f"faces={faces} volume={volume:.6f} bounds={bounds}"
        )
    print(
        "FIELD_CASE_CLOSURE_VALID "
        f"near_seated_intersection={volume:.6f} "
        f"hinge_relief={HINGE_RIM_RELIEF_RADIAL_CLEARANCE:.2f}"
    )


def validate_built_base_hinge_gussets(base) -> None:
    """Prove every support-free web is bonded and every rod bore stays open."""
    ramp_mid_y = (HINGE_BASE_GUSSET_ROOT_Y + HINGE_BASE_GUSSET_TANGENT_Y) / 2.0
    ramp_mid_z = (HINGE_BASE_GUSSET_ROOT_Z + HINGE_BASE_GUSSET_TANGENT_Z) / 2.0
    solid_probe_size_yz = 0.3
    solid_probe_inset_z = 0.6
    minimum_solid_fraction = 0.95
    minimum_solid_fill = None
    bore_overlap_maximum = 0.0

    for index, (x0, x1) in enumerate(HINGE_BASE_SEGMENTS, start=1):
        solid_probe_dimensions = (
            x1 - x0 - 1.0,
            solid_probe_size_yz,
            solid_probe_size_yz,
        )
        solid_probe = add_rounded_box(
            f"TEMPORARY_Base_Hinge_Gusset_{index}_Solid_Probe",
            solid_probe_dimensions,
            (
                (x0 + x1) / 2.0,
                ramp_mid_y,
                ramp_mid_z + solid_probe_inset_z,
            ),
            bevel=0.0,
        )
        try:
            _faces, solid_fill = exact_transformed_intersection(
                base,
                solid_probe,
                second_location=solid_probe.location.copy(),
            )
        finally:
            bpy.data.objects.remove(solid_probe, do_unlink=True)
        required_solid_fill = math.prod(solid_probe_dimensions) * minimum_solid_fraction
        if solid_fill < required_solid_fill:
            raise ValueError(
                "Base hinge support web is not fully bonded: "
                f"segment={index} volume={solid_fill:.6f} "
                f"required={required_solid_fill:.6f}"
            )
        minimum_solid_fill = (
            solid_fill
            if minimum_solid_fill is None
            else min(minimum_solid_fill, solid_fill)
        )

        bore_probe = add_cylinder_x(
            f"TEMPORARY_Base_Hinge_{index}_Open_Bore_Probe",
            HINGE_BASE_HOLE_DIAMETER / 2.0
            - HINGE_BORE_VALIDATION_RADIAL_CLEARANCE,
            x1 - x0 - 0.8,
            ((x0 + x1) / 2.0, HINGE_AXIS_Y, BASE_HEIGHT),
        )
        try:
            bore_faces, bore_overlap = exact_transformed_intersection(
                base,
                bore_probe,
                second_location=bore_probe.location.copy(),
                second_rotation=bore_probe.rotation_euler.copy(),
            )
        finally:
            bpy.data.objects.remove(bore_probe, do_unlink=True)
        if bore_faces or bore_overlap > 1e-6:
            raise ValueError(
                "Base hinge rod bore is obstructed after gusseting: "
                f"segment={index} faces={bore_faces} volume={bore_overlap:.6f}"
            )
        bore_overlap_maximum = max(bore_overlap_maximum, bore_overlap)

    full_path_probe = add_cylinder_x(
        "TEMPORARY_Base_Full_Hinge_Rod_Path_Probe",
        HINGE_BASE_HOLE_DIAMETER / 2.0
        - HINGE_BORE_VALIDATION_RADIAL_CLEARANCE,
        HINGE_ROD_X1 - HINGE_ROD_X0,
        (
            (HINGE_ROD_X0 + HINGE_ROD_X1) / 2.0,
            HINGE_AXIS_Y,
            BASE_HEIGHT,
        ),
    )
    try:
        full_path_faces, full_path_overlap = exact_transformed_intersection(
            base,
            full_path_probe,
            second_location=full_path_probe.location.copy(),
            second_rotation=full_path_probe.rotation_euler.copy(),
        )
    finally:
        bpy.data.objects.remove(full_path_probe, do_unlink=True)
    if full_path_faces or full_path_overlap > 1e-6:
        raise ValueError(
            "Base obstructs the continuous hinge rod path: "
            f"faces={full_path_faces} volume={full_path_overlap:.6f}"
        )

    hinge_gusset_overhang = math.degrees(
        math.atan2(
            HINGE_BASE_GUSSET_TANGENT_Y - HINGE_BASE_GUSSET_ROOT_Y,
            HINGE_BASE_GUSSET_TANGENT_Z - HINGE_BASE_GUSSET_ROOT_Z,
        )
    )
    bore_probe_diameter = HINGE_BASE_HOLE_DIAMETER - 2.0 * (
        HINGE_BORE_VALIDATION_RADIAL_CLEARANCE
    )
    print(
        "FIELD_CASE_BASE_HINGE_GUSSETS_VALID "
        f"count={len(HINGE_BASE_SEGMENTS)} "
        f"overhang={hinge_gusset_overhang:.2f}deg "
        f"root_z={HINGE_BASE_GUSSET_ROOT_Z:.3f} "
        f"tangent_yz={HINGE_BASE_GUSSET_TANGENT_Y:.3f},"
        f"{HINGE_BASE_GUSSET_TANGENT_Z:.3f} "
        f"solid_probe_min={minimum_solid_fill:.6f} "
        f"bore_probe_diameter={bore_probe_diameter:.3f} "
        f"bore_overlap_max={bore_overlap_maximum:.6f} "
        f"full_rod_path_overlap={full_path_overlap:.6f}"
    )


def validate_built_lid_hinge_receivers(lid) -> None:
    """Prove each receiver and its angled release path stay open."""
    bore_overlap_maximum = 0.0
    release_overlap_maximum = 0.0
    release_samples = HINGE_LID_RELEASE_PATH_SAMPLES
    for index, (x0, x1) in enumerate(HINGE_LID_SEGMENTS, start=1):
        bore_probe = add_cylinder_x(
            f"TEMPORARY_Lid_Hinge_{index}_Open_Bore_Probe",
            HINGE_LID_RECEIVER_DIAMETER / 2.0
            - HINGE_BORE_VALIDATION_RADIAL_CLEARANCE,
            x1 - x0 - 0.8,
            (
                LID_DISPLAY_OFFSET_X + (x0 + x1) / 2.0,
                -HINGE_AXIS_Y,
                LID_WALL_HEIGHT,
            ),
        )
        try:
            bore_faces, bore_overlap = exact_transformed_intersection(
                lid,
                bore_probe,
                second_location=bore_probe.location.copy(),
                second_rotation=bore_probe.rotation_euler.copy(),
            )
        finally:
            bpy.data.objects.remove(bore_probe, do_unlink=True)
        if bore_faces or bore_overlap > 1e-6:
            raise ValueError(
                "Lid hinge rod receiver is obstructed by the completed rim: "
                f"segment={index} faces={bore_faces} volume={bore_overlap:.6f}"
            )
        bore_overlap_maximum = max(bore_overlap_maximum, bore_overlap)

        rod_probe = add_cylinder_x(
            f"TEMPORARY_Lid_Hinge_{index}_4p1mm_Release_Probe",
            HINGE_ROD_DIAMETER / 2.0,
            x1 - x0 - 0.8,
            (0.0, 0.0, 0.0),
            vertices=90,
        )
        try:
            slot_opening_y, slot_opening_z = lid_hinge_slot_opening_local_yz()
            release_travel = (
                HINGE_OUTER_DIAMETER / 2.0
                + HINGE_ROD_DIAMETER / 2.0
                + 0.2
            )
            for sample_index in range(release_samples):
                sample_travel = release_travel * sample_index / (
                    release_samples - 1
                )
                release_faces, release_overlap = exact_transformed_intersection(
                    lid,
                    rod_probe,
                    second_location=(
                        LID_DISPLAY_OFFSET_X + (x0 + x1) / 2.0,
                        -HINGE_AXIS_Y + slot_opening_y * sample_travel,
                        LID_WALL_HEIGHT + slot_opening_z * sample_travel,
                    ),
                    second_rotation=rod_probe.rotation_euler.copy(),
                )
                if release_faces or release_overlap > 1e-6:
                    raise ValueError(
                        "Lid hinge slot obstructs 4.1 mm rod release: "
                        f"segment={index} sample={sample_index} "
                        f"faces={release_faces} volume={release_overlap:.6f}"
                    )
                release_overlap_maximum = max(
                    release_overlap_maximum,
                    release_overlap,
                )
        finally:
            bpy.data.objects.remove(rod_probe, do_unlink=True)

    full_path_probe = add_cylinder_x(
        "TEMPORARY_Lid_Full_Hinge_Rod_Path_Probe",
        HINGE_LID_RECEIVER_DIAMETER / 2.0
        - HINGE_BORE_VALIDATION_RADIAL_CLEARANCE,
        HINGE_ROD_X1 - HINGE_ROD_X0,
        (
            LID_DISPLAY_OFFSET_X + (HINGE_ROD_X0 + HINGE_ROD_X1) / 2.0,
            -HINGE_AXIS_Y,
            LID_WALL_HEIGHT,
        ),
    )
    try:
        full_path_faces, full_path_overlap = exact_transformed_intersection(
            lid,
            full_path_probe,
            second_location=full_path_probe.location.copy(),
            second_rotation=full_path_probe.rotation_euler.copy(),
        )
    finally:
        bpy.data.objects.remove(full_path_probe, do_unlink=True)
    if full_path_faces or full_path_overlap > 1e-6:
        raise ValueError(
            "Lid obstructs the continuous hinge rod path: "
            f"faces={full_path_faces} volume={full_path_overlap:.6f}"
        )

    probe_diameter = HINGE_LID_RECEIVER_DIAMETER - 2.0 * (
        HINGE_BORE_VALIDATION_RADIAL_CLEARANCE
    )
    print(
        "FIELD_CASE_LID_HINGE_RECEIVERS_VALID "
        f"count={len(HINGE_LID_SEGMENTS)} "
        f"probe_diameter={probe_diameter:.3f} "
        f"slot_width={HINGE_LID_SLOT_WIDTH:.3f} "
        f"slot_tilt={HINGE_LID_SLOT_TILT_DEGREES:.1f}deg "
        f"rod_diameter={HINGE_ROD_DIAMETER:.3f} "
        f"release_angle={HINGE_LID_RELEASE_ANGLE_DEGREES:.1f} "
        f"release_samples={len(HINGE_LID_SEGMENTS) * release_samples} "
        f"release_overlap_max={release_overlap_maximum:.6f} "
        f"overlap_max={bore_overlap_maximum:.6f} "
        f"full_rod_path_overlap={full_path_overlap:.6f}"
    )


def validate_built_lid_hinge_end_stops(lid) -> None:
    """Prove both solid lid bosses block axial escape of the shortened rod."""
    minimum_solid_fill = None
    retention_volumes = []
    solid_probe_radius = HINGE_LID_END_STOP_DIAMETER / 2.0 - 0.2
    solid_probe_length = HINGE_LID_END_STOP_LENGTH - 0.4
    required_solid_fill = (
        math.pi * solid_probe_radius**2 * solid_probe_length * 0.95
    )

    end_specs = (
        (-1.0, HINGE_BASE_SEGMENTS[0][0], HINGE_ROD_X0),
        (1.0, HINGE_BASE_SEGMENTS[-1][1], HINGE_ROD_X1),
    )
    for side, base_outer_face, rod_end_x in end_specs:
        stop_inner_face = (
            base_outer_face + side * HINGE_LID_END_STOP_BASE_CLEARANCE
        )
        stop_center_x = (
            stop_inner_face + side * HINGE_LID_END_STOP_LENGTH / 2.0
        )
        solid_probe = add_cylinder_x(
            "TEMPORARY_Lid_Hinge_Solid_End_Stop_Probe",
            solid_probe_radius,
            solid_probe_length,
            (
                LID_DISPLAY_OFFSET_X + stop_center_x,
                -HINGE_AXIS_Y,
                LID_WALL_HEIGHT,
            ),
            vertices=90,
        )
        try:
            _faces, solid_fill = exact_transformed_intersection(
                lid,
                solid_probe,
                second_location=solid_probe.location.copy(),
                second_rotation=solid_probe.rotation_euler.copy(),
            )
        finally:
            bpy.data.objects.remove(solid_probe, do_unlink=True)
        if solid_fill < required_solid_fill:
            raise ValueError(
                "Lid hinge rod end stop is not solid: "
                f"side={side:+.0f} volume={solid_fill:.6f} "
                f"required={required_solid_fill:.6f}"
            )
        minimum_solid_fill = (
            solid_fill
            if minimum_solid_fill is None
            else min(minimum_solid_fill, solid_fill)
        )

        rod_end_clearance = abs(stop_inner_face - rod_end_x)
        retention_probe = add_cylinder_x(
            "TEMPORARY_Lid_Hinge_Axial_Rod_Retention_Probe",
            HINGE_ROD_DIAMETER / 2.0,
            HINGE_ROD_X1 - HINGE_ROD_X0,
            (0.0, 0.0, 0.0),
            vertices=90,
        )
        try:
            retention_faces, retention_volume = exact_transformed_intersection(
                lid,
                retention_probe,
                second_location=(
                    LID_DISPLAY_OFFSET_X + side * (rod_end_clearance + 0.1),
                    -HINGE_AXIS_Y,
                    LID_WALL_HEIGHT,
                ),
                second_rotation=retention_probe.rotation_euler.copy(),
            )
        finally:
            bpy.data.objects.remove(retention_probe, do_unlink=True)
        if not retention_faces or retention_volume < 0.5:
            raise ValueError(
                "Lid hinge end stop does not retain axial rod travel: "
                f"side={side:+.0f} volume={retention_volume:.6f}"
            )
        retention_volumes.append(retention_volume)

    left_stop_inner_face = (
        HINGE_BASE_SEGMENTS[0][0] - HINGE_LID_END_STOP_BASE_CLEARANCE
    )
    right_stop_inner_face = (
        HINGE_BASE_SEGMENTS[-1][1] + HINGE_LID_END_STOP_BASE_CLEARANCE
    )
    axial_play = (
        right_stop_inner_face
        - left_stop_inner_face
        - (HINGE_ROD_X1 - HINGE_ROD_X0)
    )
    print(
        "FIELD_CASE_LID_HINGE_END_STOPS_VALID "
        "count=2 "
        f"diameter={HINGE_LID_END_STOP_DIAMETER:.3f} "
        f"length={HINGE_LID_END_STOP_LENGTH:.3f} "
        f"base_axial_clearance={HINGE_LID_END_STOP_BASE_CLEARANCE:.3f} "
        f"rod_length={HINGE_ROD_X1 - HINGE_ROD_X0:.3f} "
        f"rod_axial_play={axial_play:.3f} "
        f"solid_probe_min={minimum_solid_fill:.6f} "
        f"retention_probe_min={min(retention_volumes):.6f}"
    )


def validate_installed_lower_tray(parts) -> None:
    """Prove the tray rests on, rather than intersects, the rigid base floor."""
    tray_minimum, tray_maximum = object_world_bounds(parts["lower_tray"])
    if not math.isclose(
        tray_minimum.z,
        LOWER_TRAY_INSTALLED_Z,
        abs_tol=1e-6,
    ):
        raise ValueError(
            "Installed lower tray bottom does not align with the base floor top: "
            f"tray_z={tray_minimum.z:.6f} floor_z={BASE_FLOOR_THICKNESS:.6f}"
        )
    if not math.isclose(
        tray_maximum.z,
        LOWER_TRAY_INSTALLED_Z + TRAY_HEIGHT,
        abs_tol=1e-6,
    ):
        raise ValueError("Installed lower tray height is inconsistent")

    # Lift the tray by a negligible amount to avoid treating its intended
    # coplanar floor contact as Boolean volume. Any real floor or wall overlap
    # remains after this 0.001 mm numerical-clearance probe.
    validation_lift = 0.001
    clearance_faces, clearance_volume = exact_transformed_intersection(
        parts["base"],
        parts["lower_tray"],
        second_location=(
            0.0,
            0.0,
            LOWER_TRAY_INSTALLED_Z + validation_lift,
        ),
    )
    if clearance_faces or clearance_volume > 1e-6:
        raise ValueError(
            "Installed lower tray intersects the rigid case: "
            f"faces={clearance_faces} volume={clearance_volume:.6f}"
        )

    # A small deliberate downward probe must intersect the base floor. This
    # guards against fixing an overlap by accidentally leaving the tray
    # floating above its support surface.
    contact_probe_depth = 0.05
    contact_faces, contact_volume = exact_transformed_intersection(
        parts["base"],
        parts["lower_tray"],
        second_location=(
            0.0,
            0.0,
            LOWER_TRAY_INSTALLED_Z - contact_probe_depth,
        ),
    )
    if not contact_faces or contact_volume < 100.0:
        raise ValueError("Installed lower tray does not contact the rigid base floor")
    print(
        "FIELD_CASE_INSTALLED_TRAY_VALID "
        f"base_floor_top={BASE_FLOOR_THICKNESS:.3f} "
        f"tray_bottom={tray_minimum.z:.3f} "
        f"clearance_intersection={clearance_volume:.6f} "
        f"contact_probe={contact_probe_depth:.3f}/"
        f"{contact_volume:.6f}"
    )


def create_reference_mockups(materials, parts):
    objects = []
    (
        camera_material,
        battery_material,
        latch_material,
        latch_rod_material,
        carry_handle_material,
    ) = materials
    for index, placement in enumerate(CAMERA_PLACEMENTS, start=1):
        mockup = build_placed_camera(
            f"REFERENCE_ONLY_MISSION1_{index}",
            placement,
            as_cutter=False,
        )
        translate_object(mockup, (0.0, 0.0, LOWER_TRAY_INSTALLED_Z))
        assign_material(mockup, camera_material)
        objects.append(mockup)
    for index, center in enumerate(BATTERY_CENTERS, start=1):
        mockup = add_rounded_prism(
            f"REFERENCE_ONLY_Enduro2_{index}",
            BATTERY_THICKNESS,
            BATTERY_WIDTH,
            BATTERY_FLOOR_Z,
            BATTERY_FLOOR_Z + BATTERY_HEIGHT,
            1.6,
            center,
        )
        translate_object(mockup, (0.0, 0.0, LOWER_TRAY_INSTALLED_Z))
        assign_material(mockup, battery_material)
        objects.append(mockup)
    for index, center in enumerate(BATTERY_DOOR_SLOT_CENTERS, start=1):
        mockup = add_rounded_prism(
            f"REFERENCE_ONLY_MISSION1_Battery_Cage_Door_{index}",
            BATTERY_DOOR_SIZE[0],
            BATTERY_DOOR_SIZE[1],
            BATTERY_DOOR_SLOT_FLOOR_Z,
            BATTERY_DOOR_SLOT_FLOOR_Z + BATTERY_DOOR_SIZE[2],
            1.3,
            center,
        )
        translate_object(mockup, (0.0, 0.0, LOWER_TRAY_INSTALLED_Z))
        assign_material(mockup, battery_material)
        objects.append(mockup)
    objects.extend(
        create_latch_reference_mockups(
            parts,
            (latch_material, latch_rod_material),
        )
    )
    handle = duplicate_reference_part(
        parts["handle_bar"],
        "REFERENCE_ONLY_Folded_Pivoting_Handle",
        carry_handle_material,
    )
    handle.rotation_euler.x = math.radians(90.0)
    handle.location = (
        0.0,
        HANDLE_PIVOT_Y + HANDLE_BAR_THICKNESS / 2.0,
        HANDLE_PIVOT_Z,
    )
    objects.append(handle)
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


def export_stl(path: Path, obj, print_origin=None, expected_minimum_z=0.0) -> Path:
    if print_origin is None:
        print_origin = Vector((0.0, 0.0, 0.0))
    payload = evaluated_mesh_payload(obj, print_origin)
    minimum_print_z = min(vertex[2] for vertex in payload[0])
    if not math.isclose(minimum_print_z, expected_minimum_z, abs_tol=1e-5):
        raise ValueError(
            f"STL print origin leaves {obj.name} at Z={minimum_print_z:.6f}; "
            f"expected {expected_minimum_z:.6f}"
        )
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
    if abs(value) < 0.000000005:
        value = 0.0
    return f"{value:.8f}".rstrip("0").rstrip(".")


def validate_triangle_payload(name, vertices, triangles) -> None:
    if not vertices or not triangles:
        raise ValueError(f"Cannot export empty triangle mesh: {name}")
    face_keys = set()
    edge_uses = {}
    zero_area_faces = []
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
        if sum(component * component for component in cross) == 0.0:
            zero_area_faces.append(face_index)
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
    if zero_area_faces:
        raise ValueError(
            f"{name} has {len(zero_area_faces)} zero-area triangles; "
            f"first={zero_area_faces[0]}"
        )
    invalid_edges = [edge for edge, uses in edge_uses.items() if len(uses) != 2]
    if invalid_edges:
        first_edge = invalid_edges[0]
        raise ValueError(
            f"{name} has {len(invalid_edges)} non-manifold triangle edges; "
            f"first={first_edge} coordinates="
            f"{vertices[first_edge[0]]!r}->{vertices[first_edge[1]]!r} "
            f"uses={edge_uses[first_edge]!r}"
        )
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
        # Preserve the supplied latch bodies' repaired triangle topology.
        preserve_topology = obj.name.startswith("Field_Case_Pelican_Source_")
        positions = {}
        for vertex in bm.verts:
            position = world @ vertex.co - origin
            key = tuple(round(float(position[axis]), 8) for axis in range(3))
            if preserve_topology:
                vertex_indices[vertex.index] = len(vertices)
                vertices.append(key)
            else:
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
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            header = f"Reco field-case part: {name}".encode("ascii")[:80]
            temporary_file.write(header.ljust(80, b"\0"))
            temporary_file.write(struct.pack("<I", len(triangles)))
            for triangle in triangles:
                point_0, point_1, point_2 = (vertices[index] for index in triangle)
                # STL vertices are float32. Calculate the stored facet normal
                # from those exact float32 coordinates as well; using the
                # higher-precision source coordinates can produce a mismatched
                # normal on very small source-mesh facets.
                point_0 = struct.unpack("<fff", struct.pack("<fff", *point_0))
                point_1 = struct.unpack("<fff", struct.pack("<fff", *point_1))
                point_2 = struct.unpack("<fff", struct.pack("<fff", *point_2))
                edge_01 = tuple(point_1[axis] - point_0[axis] for axis in range(3))
                edge_02 = tuple(point_2[axis] - point_0[axis] for axis in range(3))
                normal = (
                    edge_01[1] * edge_02[2] - edge_01[2] * edge_02[1],
                    edge_01[2] * edge_02[0] - edge_01[0] * edge_02[2],
                    edge_01[0] * edge_02[1] - edge_01[1] * edge_02[0],
                )
                length = math.sqrt(sum(component * component for component in normal))
                if length == 0.0:
                    raise ValueError(
                        f"{name} has a float32-collapsed triangle in its STL payload"
                    )
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
        if temporary_path is not None and temporary_path.exists():
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
    for inlay_index, (vertices, triangles) in enumerate(inlay_payloads, start=1):
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
                containing_z = []
                for lid_triangle_indices in lid_triangles:
                    lid_triangle = [
                        lid_vertices[index] for index in lid_triangle_indices
                    ]
                    if point_in_triangle_xy(centroid, lid_triangle):
                        containing_z.append(
                            tuple(round(point[2], 6) for point in lid_triangle)
                        )
                raise ValueError(
                    f"Logo inlay {inlay_index} top face at {centroid} does not "
                    f"contact the lid bonding surface; nearby lid Z={containing_z[:8]}"
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
        "default_filament_colour": ["", "", ""],
        "different_settings_to_system": ["", "", ""],
        "enable_support": "0",
        "extruder_clearance_dist_to_rod": "33",
        "extruder_clearance_height_to_lid": "90",
        "extruder_clearance_height_to_rod": "34",
        "extruder_clearance_max_radius": "68",
        "filament_colour": [
            "#161616",
            "#F23809",
            "#F23809",
        ],
        "filament_ids": ["", "", ""],
        "filament_is_support": ["0", "0", "0"],
        "filament_settings_id": [
            BAMBU_RIGID_FILAMENT_SETTINGS_ID,
            BAMBU_RIGID_FILAMENT_SETTINGS_ID,
            BAMBU_TPU_FILAMENT_SETTINGS_ID,
        ],
        "filament_type": ["PETG", "PETG", "TPU"],
        "flush_multiplier": ["1"],
        "flush_volumes_matrix": [
            "0" if row == column else "280" for row in range(3) for column in range(3)
        ],
        "inherits_group": ["", "", ""],
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
            "Printable field-case kit with a compound two-color lid object.",
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
            "name": "AMS Lid - Shell and GoPro Missions Logo",
            "keys": (
                "lid",
                "logo_orange_inlay",
            ),
            "source_files": (
                LID_STL_NAME,
                LOGO_ORANGE_INLAY_STL_NAME,
            ),
            "extruders": (1, 2),
            "dimensions": dimensions_xy("lid"),
            "copies": 1,
            "plate": 1,
        },
    ]
    remaining_groups = (
        ("lower_tray", LOWER_TRAY_STL_NAME, 3, 1, 2, None),
        ("lid_retainer", LID_RETAINER_STL_NAME, 3, 1, 3, None),
        ("gasket", GASKET_STL_NAME, 3, 1, 4, None),
        (
            "latch_lever",
            LATCH_LEVER_STL_NAME,
            1,
            2,
            5,
            ((30.0, 30.0), (85.0, 30.0)),
        ),
        (
            "latch_hook",
            LATCH_HOOK_STL_NAME,
            1,
            2,
            5,
            ((30.0, 80.0), (75.0, 80.0)),
        ),
        (
            "handle_bar",
            HANDLE_BAR_STL_NAME,
            1,
            1,
            5,
            ((145.0, 100.0),),
        ),
        ("hinge_pin", HINGE_PIN_STL_NAME, 1, 1, 5, ((45.0, 190.0),)),
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
        group_minimums = [object_world_bounds(parts[key])[0] for key in group["keys"]]
        origin = Vector(
            tuple(min(minimum[axis] for minimum in group_minimums) for axis in range(3))
        )
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

    with tempfile.NamedTemporaryFile(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)
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
    object_model_paths = [f"3D/Objects/object_{index}.model" for index in range(1, 10)]
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
            "5",
            "AMS Lid - Shell and GoPro Missions Logo",
            ("3", "4"),
            object_model_paths[1],
        ),
        ("7", "Field_Case_Recessed_TPU_Lower_Tray", ("6",), object_model_paths[2]),
        ("9", "Field_Case_Recessed_TPU_Lid_Pad", ("8",), object_model_paths[3]),
        ("11", "Field_Case_TPU_Gasket", ("10",), object_model_paths[4]),
        (
            "13",
            "Field_Case_Pelican_Source_Lever_Print_Two",
            ("12",),
            object_model_paths[5],
        ),
        (
            "15",
            "Field_Case_Pelican_Source_Hook_Print_Two",
            ("14",),
            object_model_paths[6],
        ),
        (
            "17",
            "Field_Case_Pivoting_Handle_Bar",
            ("16",),
            object_model_paths[7],
        ),
        ("19", "Field_Case_Hinge_Pin", ("18",), object_model_paths[8]),
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
        (mesh_payloads["4"],),
    )

    expected_parts = {
        "1": (BASE_STL_NAME, "1"),
        "3": (LID_STL_NAME, "1"),
        "4": (LOGO_ORANGE_INLAY_STL_NAME, "2"),
        "6": (LOWER_TRAY_STL_NAME, "3"),
        "8": (LID_RETAINER_STL_NAME, "3"),
        "10": (GASKET_STL_NAME, "3"),
        "12": (LATCH_LEVER_STL_NAME, "1"),
        "14": (LATCH_HOOK_STL_NAME, "1"),
        "16": (HANDLE_BAR_STL_NAME, "1"),
        "18": (HINGE_PIN_STL_NAME, "1"),
    }
    settings_objects = model_settings.findall("object")
    settings_parts = model_settings.findall("object/part")
    if {node.get("id") for node in settings_objects} != set(components_by_id):
        raise ValueError("3MF model settings describe incorrect logical objects")
    expected_object_extruders = {
        "2": "1",
        "5": "1",
        "7": "3",
        "9": "3",
        "11": "3",
        "13": "1",
        "15": "1",
        "17": "1",
        "19": "1",
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
        (("5", "0"),),
        (("7", "0"),),
        (("9", "0"),),
        (("11", "0"),),
        (
            ("13", "0"),
            ("13", "1"),
            ("15", "0"),
            ("15", "1"),
            ("17", "0"),
            ("19", "0"),
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
    if identify_ids != [str(index) for index in range(1, 12)]:
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
        "filament_colour": [
            "#161616",
            "#F23809",
            "#F23809",
        ],
        "filament_type": ["PETG", "PETG", "TPU"],
        "filament_settings_id": [
            BAMBU_RIGID_FILAMENT_SETTINGS_ID,
            BAMBU_RIGID_FILAMENT_SETTINGS_ID,
            BAMBU_TPU_FILAMENT_SETTINGS_ID,
        ],
        "printer_settings_id": BAMBU_PRINTER_SETTINGS_ID,
        "print_settings_id": BAMBU_PROCESS_SETTINGS_ID,
        "flush_volumes_matrix": [
            "0" if row == column else "280" for row in range(3) for column in range(3)
        ],
    }
    for key, expected_value in expected_project_settings.items():
        if project_settings.get(key) != expected_value:
            raise ValueError(f"3MF project has an unexpected {key}")

    extruders = {value[1] for value in expected_parts.values()}
    print(
        "FIELD_CASE_3MF_VALID "
        f"mesh_parts={len(mesh_objects)} objects={len(component_objects)} "
        f"lid_components=2 lid_islands={lid_islands} "
        f"build_items={len(build_items)} extruders={','.join(sorted(extruders))}"
    )


def validate_built_part(name: str, obj) -> None:
    minimum, _maximum = object_world_bounds(obj)
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
    if name in {"latch_lever", "latch_hook", "handle_bar"} and minimum.z < -1e-5:
        raise ValueError(
            f"Built {name} extends {abs(minimum.z):.3f} mm below the print bed"
        )
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    non_manifold_edges = [edge for edge in bm.edges if not edge.is_manifold]
    non_manifold = len(non_manifold_edges)
    non_manifold_locations = [
        tuple(
            round(float(value), 3)
            for value in (edge.verts[0].co + edge.verts[1].co) / 2.0
        )
        for edge in non_manifold_edges[:8]
    ]
    volume = bm.calc_volume(signed=False)
    vertex_islands = mesh_vertex_islands(bm)
    connected_components = len(vertex_islands)
    island_bounds = [
        (
            tuple(
                round(min(float(vertex.co[axis]) for vertex in island), 3)
                for axis in range(3)
            ),
            tuple(
                round(max(float(vertex.co[axis]) for vertex in island), 3)
                for axis in range(3)
            ),
        )
        for island in vertex_islands
    ]
    bm.free()
    if non_manifold:
        raise ValueError(
            f"Built {name} has {non_manifold} non-manifold edges at "
            f"{non_manifold_locations}"
        )
    if volume < 0.001:
        raise ValueError(f"Built {name} has near-zero volume: {volume:.6f} mm^3")
    expected_components = 1
    if not name.startswith("logo_") and connected_components != expected_components:
        raise ValueError(
            f"Built {name} contains {connected_components} disconnected islands; "
            f"expected {expected_components}; bounds={island_bounds}"
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
    logo_orange_material = make_material(
        "Logo_Orange", (0.95, 0.22, 0.035), roughness=0.4
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
    latch_reference_material = make_material(
        "Pelican_Source_Latch_Reference", (0.82, 0.06, 0.03), roughness=0.38
    )
    latch_rod_reference_material = make_material(
        "Latch_4mm_Rod_Reference", (0.55, 0.58, 0.62), metallic=0.55, roughness=0.28
    )
    carry_handle_reference_material = make_material(
        "Pivoting_Handle_Reference", (0.12, 0.14, 0.18), roughness=0.38
    )
    parts = {}
    parts["base"] = create_base(shell_material)
    parts["lower_tray"] = create_lower_tray(tpu_material)
    translate_object(parts["lower_tray"], (0.0, 0.0, LOWER_TRAY_INSTALLED_Z))
    lid, logo_orange = create_lid(
        shell_material,
        logo_orange_material,
    )
    parts["lid"] = lid
    parts["logo_orange_inlay"] = logo_orange
    parts["gasket"] = create_gasket(tpu_material)
    parts["lid_retainer"] = create_lid_retainer(tpu_material)
    parts["latch_lever"], parts["latch_hook"] = create_pelican_latch_parts(
        hardware_material
    )
    parts["handle_bar"] = create_pivoting_handle_bar(hardware_material)
    parts["hinge_pin"] = create_hinge_pin(hardware_material)

    if BUILD_REFERENCE_MOCKUPS:
        create_reference_mockups(
            (
                camera_material,
                battery_material,
                latch_reference_material,
                latch_rod_reference_material,
                carry_handle_reference_material,
            ),
            parts,
        )

    for name, obj in parts.items():
        validate_built_part(name, obj)
    validate_installed_lower_tray(parts)
    validate_built_base_hinge_gussets(parts["base"])
    validate_built_lid_hinge_receivers(parts["lid"])
    validate_built_lid_hinge_end_stops(parts["lid"])
    validate_installed_lid_hinge_release(parts)
    validate_installed_case_hinge_sweep(parts)
    validate_installed_case_closure(parts)
    validate_built_lid_capture_rails(parts["lid"])
    validate_built_latch_hook_capture(parts["latch_hook"])
    validate_built_latch_impact_protectors(parts)
    validate_built_latch_fixed_m3_hardware(parts)
    validate_installed_latch_mechanics(parts)
    validate_installed_handle_mechanics(parts)
    lid_payload = evaluated_mesh_payload(parts["lid"], Vector((0.0, 0.0, 0.0)))
    logo_orange_payload = evaluated_mesh_payload(
        parts["logo_orange_inlay"], Vector((0.0, 0.0, 0.0))
    )
    lid_islands = validate_lid_bonding_payloads(
        lid_payload,
        (logo_orange_payload,),
    )
    bonding_z = max(vertex[2] for vertex in logo_orange_payload[0])
    print(f"FIELD_CASE_LID_BONDED islands={lid_islands} plane_z={bonding_z:.2f}")

    if EXPORT_STL:
        exports = (
            (BASE_STL_NAME, parts["base"]),
            (LID_STL_NAME, parts["lid"]),
            (LOWER_TRAY_STL_NAME, parts["lower_tray"]),
            (LID_RETAINER_STL_NAME, parts["lid_retainer"]),
            (GASKET_STL_NAME, parts["gasket"]),
            (LATCH_LEVER_STL_NAME, parts["latch_lever"]),
            (LATCH_HOOK_STL_NAME, parts["latch_hook"]),
            (HANDLE_BAR_STL_NAME, parts["handle_bar"]),
            (HINGE_PIN_STL_NAME, parts["hinge_pin"]),
            (LOGO_ORANGE_INLAY_STL_NAME, parts["logo_orange_inlay"]),
        )
        for filename, obj in exports:
            print_origin = None
            expected_minimum_z = 0.0
            if obj is parts["lower_tray"]:
                print_origin = Vector((0.0, 0.0, LOWER_TRAY_INSTALLED_Z))
            elif obj is parts["lid"] or obj is parts["logo_orange_inlay"]:
                print_origin = Vector((0.0, 0.0, -LID_INLAY_DEPTH))
                if obj is parts["lid"]:
                    expected_minimum_z = LID_INLAY_DEPTH
            export_stl(
                export_path(filename),
                obj,
                print_origin,
                expected_minimum_z,
            )
        project_path = export_3mf_project(export_path(PROJECT_3MF_NAME), parts)
        validate_3mf_project(project_path)

    if SAVE_BLEND:
        path = Path(BLEND_PATH).expanduser().resolve()
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        print(f"FIELD_CASE_SAVED_BLEND {path}")

    return parts


if __name__ == "__main__":
    build_mission1_field_case()
