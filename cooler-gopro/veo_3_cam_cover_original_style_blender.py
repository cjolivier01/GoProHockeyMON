"""Original-style Veo Cam 3 cover reconstruction for Blender.

This rebuilds the *spirit* of ``veo_3_cam_cover.stl`` as a printable two-part
enclosure with:

* the same approximate 215 x 234 x 71 mm baseline envelope, expanded at the
  camera-side nose only when the configured camera angle requires it,
* a broad rounded-triangular body with a closed bottom,
* a flat removable lid retained by four socket-head screws,
* M3 heat-set-insert posts automatically kept clear of both cameras,
* two upright MISSION 1 cameras supported and centered by built-in cradles,
* an optional self-locking worm-driven yaw cartridge for either camera,
* removable, button-relieved camera clamps using M3 heat-set inserts,
* two camera openings on the same side with the lens faces projecting through,
* camera axes angled apart in plan,
* two locally wall-aligned 40 mm fan stations with inside/outside pads,
* three flush-recessed bottom keystone-module mounts, and
* an optional projecting eyelid/visor directly above each camera opening.

Run inside Blender::

    /home/colivier/Apps/Blender/blender \
      --background --factory-startup \
      --python veo_3_cam_cover_original_style_blender.py

All dimensions are millimeters.  X is body width, Y is body depth, and Z is
height.  Camera azimuths are measured counter-clockwise from +X when viewed
from above.  Dominant surfaces around the source openings point near 124 and
236 degrees; the angle remains a single configurable value because the
triangulated source does not expose an exact optical axis.
"""

from __future__ import annotations

import math
import hashlib
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector


def import_mission1_module():
    """Find the companion module when run externally or from a Blender text."""
    script_path = Path(__file__).expanduser().resolve()
    script_directory = script_path.parent
    candidates = [Path.cwd().resolve(), script_directory]
    # Blender text blocks commonly report a virtual path like
    # ``project.blend/script.py``.  Its parent is the .blend file, while the
    # companion module actually sits beside that file.
    if script_directory.suffix.lower() == ".blend":
        candidates.append(script_directory.parent)
    if bpy.data.filepath:
        candidates.append(Path(bpy.data.filepath).expanduser().resolve().parent)

    searched = []
    for directory in candidates:
        module_path = directory / "gopro_mission1_dummy_blender.py"
        if module_path in searched:
            continue
        searched.append(module_path)
        if module_path.is_file():
            directory_text = str(directory)
            if directory_text not in sys.path:
                sys.path.insert(0, directory_text)
            import gopro_mission1_dummy_blender

            return gopro_mission1_dummy_blender
    raise ModuleNotFoundError(
        "Could not locate gopro_mission1_dummy_blender.py. Searched: "
        + ", ".join(str(path) for path in searched)
    )


mission1 = import_mission1_module()


# ---------------------------------------------------------------------------
# CONFIG

CLEAR_SCENE = True
EXPORT_STL = False
EXPORT_DIRECTORY = ""
EXPORT_SEPARATE_STLS = True
EXPORT_COMBINED_STL = True
BASE_STL_NAME = "veo_3_cam_cover_original_style_base.stl"
LID_STL_NAME = "veo_3_cam_cover_original_style_lid.stl"
ASSEMBLY_STL_NAME = "veo_3_cam_cover_original_style.stl"
CAMERA_BRACKET_1_STL_NAME = "veo_3_cam_cover_camera_bracket_1.stl"
CAMERA_BRACKET_2_STL_NAME = "veo_3_cam_cover_camera_bracket_2.stl"
CAMERA_CARRIER_STL_NAME = "veo_3_cam_cover_rotating_camera_cartridge.stl"
CAMERA_WORM_STL_NAME = "veo_3_cam_cover_purchased_worm_reference.stl"
EXPORT_PURCHASED_WORM_REFERENCE_STL = False
NORMALIZE_SEPARATE_STLS = True
# Print-specific exports put the lid exterior and removable bracket top faces
# on the build plate so their deep eye tongues/guides grow upward without a
# large support forest.  The combined STL remains in assembled orientation.
PRINT_ORIENT_SEPARATE_STLS = True
# Preserve the manifold Boolean n-gons in Blender.  The STL exporter performs
# its own output triangulation; destructively triangulating this heavily cut
# shell in-scene can create over-connected diagonals at coincident cut seams.
TRIANGULATE_BASE_IN_SCENE = True
VALIDATE_ASSEMBLY_CLEARANCES = True
ASSEMBLY_INTERSECTION_VOLUME_TOLERANCE = 0.0001
# Blender may return a triangulated zero-thickness mesh for coincident mating
# faces and report a bogus signed volume.  Intersections thinner than this on
# any axis are treated as coplanar contact, not solid interference.
ASSEMBLY_COPLANAR_CONTACT_TOLERANCE = 0.001
VALIDATE_TIGHTENED_BRACKET_CLEARANCES = True
CAMERA_BRACKET_MIN_PRELOAD_CONTACT_VOLUME = 1.0
CAMERA_BRACKET_REAR_CONTACT_VOLUME_TOLERANCE = 0.01
CAMERA_BASE_CONTACT_VOLUME_TOLERANCE = 0.01

# Visibility in Blender after the generator finishes.  These are applied only
# after export and preview rendering, so hidden parts are still generated and
# included in the requested output files.
SHOW_MAIN_BODY_AFTER_BUILD = True
SHOW_TOP_AFTER_BUILD = True
SHOW_CAMERA_CARTRIDGE_AFTER_BUILD = True
SHOW_PURCHASED_WORM_REFERENCE_AFTER_BUILD = True

RENDER_PREVIEW = False
PREVIEW_PATH = "veo_3_cam_cover_original_style.png"
PREVIEW_RESOLUTION_X = 1100
PREVIEW_RESOLUTION_Y = 850
PREVIEW_EXPLODED = True
PREVIEW_LID_LIFT = 25.0
PREVIEW_SHOW_CAMERA_MOCKUPS = True

# Source STL envelope: 215.167 x 233.661 x 70.653 mm.
# BODY_WIDTH = 215.167
BODY_WIDTH = 180
BODY_DEPTH = 233.661
# BODY_DEPTH = 210
# Two extra millimeters preserve lid/bracket clearance after raising the
# cameras and thickening the adjustable pivot tray for stiffness and airflow.
BODY_HEIGHT = 72.653
BASE_HEIGHT = 68.0
LID_THICKNESS = BODY_HEIGHT - BASE_HEIGHT
BOTTOM_THICKNESS = 3.2
BODY_WALL_THICKNESS = 3.2
# 0 produces an ellipse.  Higher values pull the camera end (-X) inward and
# leave a broad rounded rear (+X), producing the source's soft triangle shape.
FOOTPRINT_TRIANGULARITY = 0.68
FOOTPRINT_POINTS = 192

# (Z, XY scale) controls the rounded bottom edge and vertical main body.
BODY_SECTIONS = (
    (0.0, 0.96),
    (6.0, 0.99),
    (12.0, 1.00),
    (BASE_HEIGHT, 1.00),
)

# Lid locating lip.  The screw system provides clamping; this lip aligns the
# flat top and prevents lateral movement.
LID_LIP_ENABLED = True
LID_LIP_DEPTH = 3.0
LID_LIP_THICKNESS = 1.8
LID_LIP_CLEARANCE = 0.30

# Both camera openings sit on the -X half of the shell.  The half-angle is a
# primary shape input: reducing it keeps the cameras closer together and the
# camera-driven footprint automatically broadens/blunts the -X nose as needed.
CAMERA_CENTERLINE_AZIMUTH_DEG = 180.0
CAMERA_HALF_ANGLE_DEG = 35.0
# Set a two-value tuple to override the symmetric centerline/half-angle logic.
CAMERA_AZIMUTHS_DEG = None
# Expand the camera-driven footprint and automatically placed post layouts to
# their mirrored union about CAMERA_CENTERLINE_AZIMUTH_DEG. This keeps the
# enclosure and hardware layout symmetric even though the upright camera's
# lens is offset within its handed body envelope.
FORCE_LAYOUT_SYMMETRY = True

# Camera roll and lens-axis height.  The supplied STL is upright by default;
# set CAMERA_UPSIDE_DOWN=True only when deliberately mounting it that way.
CAMERA_UPSIDE_DOWN = False
# None derives the eye height from the measured camera bottom and configured
# airflow gap.  Set a number only to override that automatic vertical datum.
EYE_CENTER_Z = None
EYE_OPENING_WIDTH = 58.0
EYE_OPENING_HEIGHT = 46.0
EYE_OPENING_CORNER_RADIUS = 10.0
EYE_CUTTER_INWARD_EXTRA = 5.0
EYE_CUTTER_OUTWARD_EXTENSION = 25.0

# Top-loading split eyes.  The base opening becomes a U-slot from the optical
# centerline to the rim; keyed inserts descending from the lid restore the
# upper rounded aperture and raised-surround face when the lid is installed.
EYE_TOP_LOADING_ENABLED = True
EYE_TOP_LOADING_SLOT_WIDTH = 44.0
EYE_TOP_LOADING_SLOT_BOTTOM_OFFSET_Z = 0.0
EYE_LID_CLOSURE_FIT_CLEARANCE = 0.25
EYE_LID_CLOSURE_RADIAL_CLEARANCE = 0.20
EYE_LID_CLOSURE_PLATE_EMBED = 2.5
EYE_LID_CLOSURE_BACKING_THICKNESS = 1.8
EYE_LID_CLOSURE_BACKING_SIDE_OVERLAP = 3.0
EYE_LID_CLOSURE_APERTURE_CLEARANCE = 0.20
# When the optional protruding eyelids are enabled, two short root ribs make
# each split-off center visor monolithic with its lid closure.  The ribs stay
# inside the removable tongue width, so they pass through the base U-slot.
EYE_LID_VISOR_ROOT_RIB_WIDTH = 3.0
EYE_LID_VISOR_ROOT_RIB_EDGE_INSET = 0.35

# Raised surround around each opening.
EYE_BEZEL_WIDTH = 64.0
EYE_BEZEL_HEIGHT = 52.0
EYE_BEZEL_CORNER_RADIUS = 14.5
EYE_FACE_INSET = 1.0
# EYE_BEZEL_DEPTH = 9.0
EYE_BEZEL_DEPTH = 5.0
EYE_FACE_RECESS_ENABLED = True
EYE_FACE_RECESS_BORDER_OVERLAP = 1.0
# Includes the final bracket and cartridge shell-clearance expansions.  The
# flared outside mouth below keeps this structural hull growth out of the FOV.
EYE_FACE_RECESS_MAX_DEPTH = 14.0
# When a low-mounted cartridge sweep pushes the convex outer hull forward,
# flare the outside of the localized eye recess instead of leaving a deep,
# straight-walled tunnel around the lens.  The narrow end remains overlapped
# by the 64 mm eye surround; only unsupported shell in front of it is removed.
EYE_FACE_RECESS_OUTER_FLARE_ENABLED = False
EYE_FACE_RECESS_OUTER_FLARE_ANGLE_DEG = 38.0
EYE_FACE_RECESS_OUTER_FLARE_MAX_PER_SIDE = 10.0


# The eyelid is a tapered wedge whose lower/front edge overhangs the eye.
VISORS_ENABLED = False
VISOR_BACK_WIDTH = 92.0
VISOR_FRONT_WIDTH = 60.0
VISOR_BACK_INSET = 12.0
# A small positive overlap keeps the beveled visor Boolean robust where its
# front edge meets the camera-driven face plane.
VISOR_PROJECTION = 0.25
VISOR_BACK_BOTTOM_Z = 48.5
VISOR_BACK_TOP_Z = 59.0
VISOR_FRONT_BOTTOM_Z = 48.0
VISOR_FRONT_TOP_Z = 54.0
VISOR_EDGE_RADIUS = 1.5
# Preserve the configured visor proportions while automatically moving its
# lower edge above the measured lens housing and limiting its inward reach so
# it cannot bury itself in the wider camera body behind the lens.
VISOR_AUTO_CLEAR_CAMERA = True
VISOR_CAMERA_VERTICAL_CLEARANCE = 0.50
VISOR_CAMERA_BODY_RADIAL_CLEARANCE = 0.30
# Keep the camera-cleared visor shallow enough not to cross the neighboring
# close-angle bezel or the lid's descending alignment lip.  In split-eye mode
# it still overlaps the keyed tongue through the configured root ribs.
VISOR_LID_SAFE_MAX_BACK_INSET = 1.50

# MISSION 1 measurements come from the supplied GoproDummy_noscreens.stl and
# its procedural recreation in gopro_mission1_dummy_blender.py.  The full
# 81 x 44.4 x 54 mm envelope includes its 16.6 mm lens projection, top button,
# and side button.  Width is tangential to the optical axis; depth is radial.
CAMERA_BODY_ONLY_WIDTH = mission1.BODY_WIDTH
CAMERA_BODY_ONLY_DEPTH = mission1.BODY_DEPTH
CAMERA_BODY_ONLY_HEIGHT = mission1.BODY_HEIGHT
CAMERA_BODY_WIDTH = mission1.REFERENCE_ENVELOPE_WIDTH
CAMERA_BODY_DEPTH = mission1.REFERENCE_ENVELOPE_DEPTH
CAMERA_BODY_HEIGHT = mission1.REFERENCE_ENVELOPE_HEIGHT
# "maximize" derives the largest safe outset from the measured front-body
# plane, shell thickness, and printable wall-backed front-stop projection.
# "manual" uses CAMERA_LENS_FACE_OUTSET directly.
CAMERA_FORWARD_PLACEMENT_MODE = "maximize"  # "maximize" or "manual"
CAMERA_LENS_FACE_OUTSET = 1.0
CAMERA_LENS_FACE_MIN_OUTSET = 0.5
CAMERA_LENS_OPENING_CLEARANCE = 0.5
CAMERA_LENS_HOUSING_OTHER_EYE_CLEARANCE = 0.5
CAMERA_OPPOSITE_EYE_SURROUND_CLEARANCE = 0.25
# The rotating camera's lens moves slightly fore/aft as it yaws about its
# under-body pivot.  Reject configurations that pull it back into the eye
# throat anywhere in the usable sweep.
CAMERA_LENS_MIN_SWEEP_EYE_FACE_PROTRUSION = 8.0
CAMERA_FORWARD_SOLVE_STEPS = 48
CAMERA_FORWARD_SOLVE_SAFETY_MARGIN = 0.10
# The integrated support pads supply this gap above the enclosure floor; the
# cameras are not left floating at the nominal eye height.
CAMERA_FLOOR_CLEARANCE = 4.5
CAMERA_MIN_FLOOR_AIR_GAP = 3.0
# None derives these lens/envelope offsets from the selected camera roll at
# build time.  Set a number only to deliberately override the measured dummy.
CAMERA_LENS_OFFSET_Z = None
CAMERA_ENVELOPE_TANGENTIAL_OFFSET = None
CAMERA_BODY_MUTUAL_CLEARANCE = 1.0
CAMERA_DRIVEN_NOSE_ENABLED = True
CAMERA_NOSE_SHELL_CLEARANCE = 1.5
CAMERA_NOSE_CONTACT_TOLERANCE = 0.01
CAMERA_NOSE_MAX_EXPANSION = 80.0

# Optional single-camera aiming cartridge copied from ``dual-cam-case.py``.
# When enabled, the selected camera's fixed cradle and ordinary upper bracket are
# replaced by a rotating lower carrier, pivot-centered upper hold-down,
# printed module-0.5 sector gear, and externally accessible purchased worm.
# The one-start worm is self-locking, so the selected yaw should hold without
# a separate clamp.  The enclosure footprint and eye throat grow automatically
# to clear the complete configured motion range.
CAMERA_CARTRIDGE_WORM_ENABLED = True
ADJUSTABLE_CAMERA_INDEX = 2
ADJUSTABLE_CAMERA_YAW_RANGE_DEG = 10.0
ADJUSTABLE_CAMERA_PREVIEW_YAW_DEG = 0.0
ADJUSTABLE_CAMERA_SWEEP_STEP_DEG = 1.0
# Mirror the tangent-offset pivot and sector to the enclosure's other side
# when camera 1 is selected, keeping the gear and worm outboard instead of
# sending them through camera 2.
ADJUSTABLE_CAMERA_MIRROR_MECHANISM_BY_SIDE = True
# Pivot coordinates use the selected camera's canonical radial/tangential
# frame relative to the lens-face center.
ADJUSTABLE_CAMERA_PIVOT_RADIAL = -22.0
ADJUSTABLE_CAMERA_PIVOT_TANGENTIAL = -10.0
ADJUSTABLE_CAMERA_SWEEP_CLEARANCE = 1.5
# Small final radial cavity allowance for the real faceted carrier/tooth
# envelope after the analytical sweep solve.  The analytical footprint already
# includes the swept carrier, gear, USB service volume, and configured running
# clearance, but its polygonized endpoint can extend about 1 mm farther.  Keep
# this correction small because every extra millimeter also advances the shell
# surrounding both lenses.
CAMERA_CARTRIDGE_SHELL_EXPANSION = 1.15
# Polygon/Boolean roundoff can place a carrier vertex a few microns beyond the
# analytically expanded cavity.  This is not physical clearance; millimeter-
# scale misses still fail (zero expansion misses by about 1.0 mm).
CAMERA_CARRIER_CAVITY_NUMERICAL_TOLERANCE = 0.01

# Rotating lower carrier.  Its tray fits below the camera support plane;
# localized pads preserve the configured under-camera cooling-air gap.
CAMERA_CARRIER_BOTTOM_CLEARANCE = 0.45
CAMERA_CARRIER_TRAY_THICKNESS = 3.20
# The tray extends beneath the complete 5 mm guide/stop thickness.  These
# broad roots are what make the vertical locators structural rather than tabs
# attached along a narrow ledge.
CAMERA_CARRIER_TRAY_RADIAL_MARGIN = 5.0
CAMERA_CARRIER_TRAY_TANGENTIAL_MARGIN = 5.0
# Vent the lower tray while retaining a strong outer frame and two full-depth
# rails directly below the support pads.
CAMERA_CARRIER_TRAY_FRAME_WIDTH = 5.0
CAMERA_CARRIER_SUPPORT_RAIL_WIDTH = 8.0
CAMERA_CARRIER_MIN_TRAY_OPEN_AREA_RATIO = 0.35
CAMERA_CARRIER_CAMERA_CLEARANCE = 0.0
# Installed-fit validation lifts the camera by this tiny amount to separate
# intentional floor-pad contact from real lateral interference.  This is only
# a numerical probe; it does not add physical clearance to the printed cradle.
CAMERA_CARRIER_FIT_PROBE_LIFT = 0.20
CAMERA_CARRIER_GUIDE_HEIGHT = 15.0
CAMERA_CARRIER_GUIDE_THICKNESS = 5.0
CAMERA_CARRIER_GUIDE_TRAY_EMBED = 0.80
CAMERA_CARRIER_FRONT_STOP_WIDTH = 14.0
CAMERA_CARRIER_FRONT_STOP_ROOT_LENGTH = 4.0
CAMERA_CARRIER_FRONT_STOP_ROOT_RAIL_WIDTH = 8.0
CAMERA_CARRIER_SWEEP_CUT_CLEARANCE = 0.30
# The lid-off base has a clear vertical shaft above the complete tray/guide
# footprint.  Besides making the cartridge installable after printing, this
# functions as an open cooling chimney around the lower/rear camera body.
CAMERA_CARRIER_TOP_LOADING_CHIMNEY_ENABLED = True
CAMERA_CARRIER_TOP_LOADING_CHIMNEY_CLEARANCE = 3.0
# A chimney cut can leave a tiny closed remnant of the pre-cut eye surround
# on the mirrored layout.  Remove only bounded, explicitly small fragments;
# a larger disconnected shell is treated as a geometry error.
CAMERA_CARRIER_CHIMNEY_REMOVE_SMALL_FRAGMENTS = False
CAMERA_CARRIER_CHIMNEY_MAX_FRAGMENT_FACES = 128
# Face count alone is not a safe proxy for physical size.  Cleanup is allowed
# only when explicitly enabled and each detached Boolean remnant is also a true
# sliver within both limits.  The safe default leaves every fragment in place
# so single-shell validation fails visibly rather than deleting useful material.
CAMERA_CARRIER_CHIMNEY_MAX_FRAGMENT_VOLUME = 25.0
CAMERA_CARRIER_CHIMNEY_MAX_FRAGMENT_EXTENT = 10.0
# Carrier cleanup is needed for an observed 0.013 mm^3 pivot-bore Boolean
# speck.  Its independent sliver-scale limits are intentionally far below a
# functional guide or gear tooth, so those features can never be auto-deleted.
CAMERA_CARRIER_REMOVE_SMALL_FRAGMENTS = True
CAMERA_CARRIER_MAX_FRAGMENT_FACES = 32
CAMERA_CARRIER_MAX_FRAGMENT_VOLUME = 1.0
CAMERA_CARRIER_MAX_FRAGMENT_EXTENT = 3.0
# Both sides use short, stout fore/aft guide segments.  On the USB/battery side
# those segments stop at the measured plug keepout instead of blocking the
# connector; on the other side they leave an open mid-body cooling channel.
CAMERA_CARRIER_USB_SIDE_GUIDE_ENABLED = True
CAMERA_CARRIER_NON_USB_SIDE_GUIDE_ENABLED = True
CAMERA_CARRIER_SIDE_GUIDE_END_LENGTH = 8.0
CAMERA_CARRIER_USB_GUIDE_MIN_SEGMENT_LENGTH = 3.0
CAMERA_CARRIER_MIN_SIDE_AIR_CHANNEL = 11.0
# Rear end guides overlap the split rear blocks by this much, creating true
# monolithic L-corners instead of fragile coplanar/tiny-corner joins.
CAMERA_CARRIER_REAR_CORNER_OVERLAP = 2.0
# Span the complete solid body width so each rear segment actually joins its
# adjacent side guide.  The center remains open below, and almost 40 mm of
# camera height remains unobstructed above these low guides for fan airflow.
CAMERA_CARRIER_REAR_GUIDE_TOTAL_WIDTH = CAMERA_BODY_ONLY_WIDTH
CAMERA_CARRIER_REAR_GUIDE_CENTER_AIR_GAP = 22.0
CAMERA_CARRIER_REAR_GUIDE_MIN_SEGMENT_WIDTH = 10.0
CAMERA_CARRIER_MIN_REAR_AIR_GAP = 18.0
CAMERA_CARRIER_PIVOT_PIN_DIAMETER = 8.0
CAMERA_CARRIER_PIVOT_CLEARANCE = 0.25
# The raised camera datum and thicker tray give the pin 3.10 mm of radial
# bearing engagement instead of the former 1.70 mm, materially reducing lens
# rocking while retaining a vented under-camera floor.
CAMERA_CARRIER_PIVOT_PIN_HEIGHT = 3.55
CAMERA_CARRIER_MIN_PIVOT_ENGAGEMENT = 3.0
CAMERA_CARRIER_THRUST_PAD_DIAMETER = 18.0
# A replaceable low-friction washer carries the yaw load.  The printed pad is
# only its flat seat; the final value in this stack is intentional free play.
CAMERA_CARRIER_THRUST_PAD_HEIGHT = 0.15
CAMERA_CARRIER_THRUST_WASHER_OD = 16.0
CAMERA_CARRIER_THRUST_WASHER_ID = 8.5
CAMERA_CARRIER_THRUST_WASHER_THICKNESS = 0.25
CAMERA_CARRIER_THRUST_RUNNING_CLEARANCE = 0.05

# Printed sector gear driven by the purchased one-start module-0.5 worm used
# by ``dual-cam-case.py`` (nominal 10 mm OD x 20 mm long, 4 mm shaft bore).
# The 170-tooth-equivalent sector gives 170:1 adjustment: a 10-degree camera
# move takes approximately 4.72 worm turns.
CAMERA_GEAR_MODULE = 0.50
CAMERA_GEAR_EQUIVALENT_TEETH = 170
CAMERA_GEAR_SECTOR_START_DEG = 90.0
CAMERA_GEAR_SECTOR_END_DEG = 150.0
CAMERA_GEAR_CONTACT_DEG = 120.0
# Rotate the mirrored mechanism farther outboard so the worm and its blocks do
# not occupy the asymmetric upright camera tray.  Camera 2 uses zero offset.
CAMERA_GEAR_MIRRORED_ANGLE_OFFSET_DEG = -40.0
CAMERA_GEAR_RIM_INNER_RADIUS = 37.5
CAMERA_GEAR_FACE_WIDTH = 3.6
CAMERA_GEAR_BACKLASH = 0.12
CAMERA_GEAR_MESH_CENTER_CLEARANCE = 0.52
CAMERA_GEAR_MIN_RADIAL_ENGAGEMENT = 0.35
CAMERA_GEAR_TOOTH_TIP_FRACTION = 0.46
CAMERA_GEAR_TOOTH_ROOT_FRACTION = 0.78
CAMERA_GEAR_SECTOR_SAMPLES_PER_TOOTH = 5
CAMERA_WORM_STARTS = 1
CAMERA_WORM_DIAMETER_QUOTIENT = 18.0
CAMERA_WORM_LENGTH = 20.0
CAMERA_WORM_SHAFT_DIAMETER = 4.0
CAMERA_WORM_SHAFT_CLEARANCE = 0.30
CAMERA_WORM_BEARING_OD = 8.0
CAMERA_WORM_BEARING_WIDTH = 3.0
# Negative diameter adjustment makes an FDM press-fit pocket.  Tune this for
# the printer/material; -0.10 mm is a deliberately light nominal interference.
CAMERA_WORM_BEARING_POCKET_DIAMETER_ADJUSTMENT = -0.10
CAMERA_WORM_BEARING_POCKET_DEPTH_CLEARANCE = 0.10
# Keep the worm/gear mesh above the locally thickened 3.2 mm carrier tray.
CAMERA_WORM_FLOOR_CLEARANCE = 1.40
CAMERA_WORM_BLOCK_LENGTH = 6.0
CAMERA_WORM_BLOCK_WIDTH = 12.0
CAMERA_WORM_BLOCK_TOP_CLEARANCE = 0.8
# Each worm end sits close to its bearing with a thin thrust washer/spacer.
# Retain the 4 mm shaft with collars or E-clips outside both bearings.
CAMERA_WORM_THRUST_WASHER_THICKNESS = 0.50
CAMERA_WORM_AXIAL_RUNNING_CLEARANCE = 0.20
CAMERA_WORM_BLOCK_OFFSET = 0.70
CAMERA_WORM_PORT_BOSS_RADIUS = 6.5
CAMERA_WORM_PORT_OUTSET = 3.0
CAMERA_WORM_PORT_INWARD_EXTENSION = 4.0

# A fixed pin below the camera runs in a reinforced arcuate slot in the moving
# tray.  HARD_STOP_LIMIT is the physical contact angle, not the slot-end-center
# angle; the generator shortens the centerline arc to account for running play.
# This compact stop stays inside the camera footprint, does not compete with
# bracket posts, and leaves the outboard forced-air paths open.
CAMERA_HARD_STOP_LIMIT_DEG = 12.0
CAMERA_HARD_STOP_MIRRORED_EXTRA_LIMIT_DEG = 0.0
CAMERA_HARD_STOP_PIN_DIAMETER = 6.0
CAMERA_HARD_STOP_SLOT_RADIUS = 22.0
CAMERA_HARD_STOP_SLOT_LOCAL_ANGLE_DEG = -90.0
CAMERA_HARD_STOP_SLOT_DIAMETRAL_CLEARANCE = 0.40
CAMERA_HARD_STOP_SLOT_REINFORCEMENT_WIDTH = 5.0
CAMERA_HARD_STOP_SLOT_PIVOT_WEB = 1.5
CAMERA_HARD_STOP_SLOT_REINFORCEMENT_EXTRA_HEIGHT = 0.20
CAMERA_HARD_STOP_MIN_ENDPOINT_CLEARANCE = 0.5
# The large worm ratio can overload printed stops.  Treat this as a knob/driver
# limit and use a torque-limited knob or slip clutch where practical.
CAMERA_WORM_MAX_INPUT_TORQUE_NMM = 2.0

# The selected camera's removable bridge bears directly over the yaw pivot,
# supplying vertical preload without an appreciable yaw moment.  A second
# rotating top cap is deliberately omitted: this small stationary interface is
# stiffer, cannot desynchronize from the lower carrier, and obstructs less air.
CAMERA_HOLD_DOWN_PAD_DIAMETER = 10.0
CAMERA_HOLD_DOWN_CENTER_PLATE_DIAMETER = 18.0
# Bond a replaceable PTFE/UHMW/acetal disk to the printed pivot pad.  It is
# centered on the yaw axis, so the stationary bridge adds negligible yaw drag.
CAMERA_HOLD_DOWN_PAD_MATERIAL_THICKNESS = 0.25
CAMERA_HOLD_DOWN_PAD_MATERIAL_CLEARANCE = 0.20
CAMERA_CARRIER_COLOR = (0.92, 0.55, 0.08, 1.0)
CAMERA_WORM_COLOR = (0.72, 0.43, 0.12, 1.0)
CAMERA_CARTRIDGE_DEBUG_MESH_STAGES = False

# Base-integrated camera cradles.  Two pads support each camera at the exact
# modeled lens height.  A short, zero-clearance front-left stop supplies a
# strong lower datum while leaving the USB side and lens-first path open.
CAMERA_CRADLES_ENABLED = True
CAMERA_SUPPORT_PAD_RADIAL_LENGTH = 19.0
CAMERA_SUPPORT_PAD_TANGENTIAL_WIDTH = 12.0
CAMERA_SUPPORT_PAD_TANGENTIAL_SPACING = 36.0
CAMERA_SUPPORT_PAD_EDGE_RADIUS = 0.8
CAMERA_SUPPORT_PAD_MIN_GAP = 2.0
CAMERA_SUPPORT_FEATURE_CLEARANCE = 0.5
CAMERA_CRADLE_SIDE_GUIDE_HEIGHT = 12.0
CAMERA_CRADLE_SIDE_GUIDE_THICKNESS = 7.0
CAMERA_CRADLE_SIDE_GUIDE_RADIAL_LENGTH = 8.0
CAMERA_CRADLE_SIDE_CLEARANCE = 0.0
CAMERA_CRADLE_SIDE_GUIDE_RADIAL_PLACEMENT = "front"  # "front" or "center"
CAMERA_CRADLE_SIDE_GUIDE_FRONT_INSET = 0.5
# A lens-first radial slide brings the wider lens housing across the fixed
# body-side guide.  Clip only the guide height (not its stout thickness) below
# that swept lens envelope so the guide remains snug without becoming a hook.
CAMERA_CRADLE_SIDE_GUIDE_AUTO_CLEAR_LENS_PATH = True
CAMERA_CRADLE_SIDE_GUIDE_LENS_PATH_CLEARANCE = 0.5
CAMERA_CRADLE_SIDE_GUIDE_MIN_RESOLVED_HEIGHT = 6.0
# A short, stout stop remains at the front-left/non-USB lower corner.  Keeping
# it forward and below the lens sweep retains a snug datum without blocking
# the connector side or either camera's validated insertion path.
CAMERA_CRADLE_FIXED_SIDE_GUIDES = "non_usb_only"  # "non_usb_only", "both", "none"
# Split fixed rear tabs are safe with vertical top loading and positively
# locate the camera while preserving a center-bottom cooling-air channel.
# They are automatically omitted in legacy rearward-loading mode so the
# camera can still slide past its final rear datum.
CAMERA_CRADLE_REAR_GUIDE_ENABLED = True
CAMERA_CRADLE_REAR_GUIDE_HEIGHT = 12.0
CAMERA_CRADLE_REAR_GUIDE_THICKNESS = 7.0
CAMERA_CRADLE_REAR_GUIDE_TANGENTIAL_WIDTH = 50.0
# The rear locator is split into two blocks around this open center channel so
# air can enter the cooling gap beneath the camera.
CAMERA_CRADLE_REAR_GUIDE_CENTER_AIR_GAP = 18.0
CAMERA_CRADLE_REAR_GUIDE_MIN_SEGMENT_WIDTH = 10.0
CAMERA_CRADLE_REAR_CLEARANCE = 0.0
CAMERA_CRADLE_GUIDE_EDGE_RADIUS = 0.8

# USB-C access envelope measured from gopro_fan_case_parametric_blender.py.
# Its +X/right-side opening maps to tangent_min in the upright canonical
# MISSION 1 orientation and tangent_max when the camera is upside down.
CAMERA_USB_ACCESS_ENABLED = True
CAMERA_USB_SIDE = "auto"  # "auto", "tangent_min", or "tangent_max"
CAMERA_USB_PORT_RADIAL_WIDTH = 13.1998
CAMERA_USB_PORT_HEIGHT = 7.2
CAMERA_USB_PORT_RADIAL_OFFSET_FROM_BODY_CENTER = 1.2394
CAMERA_USB_PORT_CENTER_ABOVE_BODY_BOTTOM = 12.8249
CAMERA_USB_ACCESS_RADIAL_CLEARANCE = 2.0
CAMERA_USB_ACCESS_VERTICAL_CLEARANCE = 2.0
CAMERA_USB_PLUG_OUTWARD_DEPTH = 30.0
CAMERA_USB_PLUG_BODY_OVERLAP = 1.0
# Extra plan-view clearance between either swept USB plug corridor and the
# opposite camera.  The camera-radius solver grows the case when needed.
CAMERA_USB_ACCESS_OTHER_CAMERA_CLEARANCE = 1.0
VALIDATE_CAMERA_USB_ACCESS = True
CAMERA_USB_ACCESS_INTERSECTION_VOLUME_TOLERANCE = 0.001

# Positive radial location is toward/out through the eye.  Three integrated
# pads project inward from the solid wall around each opening and contact the
# camera's flat front-body face outside the lens housing: two along the roomy
# side and one below/above the opening.  The camera is solved so this is its
# maximum forward position, then the bracket's rear lip holds it there.
CAMERA_FRONT_STOPS_ENABLED = True
# Minimum printable projection in maximize mode.  The solver increases this
# only when the two angled camera/body envelopes require more wall-to-body gap.
CAMERA_FRONT_STOP_PROJECTION = 0.6
CAMERA_FRONT_STOP_SIDE_WIDTH = 3.5
CAMERA_FRONT_STOP_SIDE_HEIGHT = 8.0
CAMERA_FRONT_STOP_RIM_WIDTH = 10.0
CAMERA_FRONT_STOP_RIM_HEIGHT = 3.0
CAMERA_FRONT_STOP_WALL_LAND = 0.25
CAMERA_FRONT_STOP_EDGE_RADIUS = 0.6
CAMERA_FRONT_STOP_CONTACT_TOLERANCE = 0.01

# Four lid fasteners.  "auto" searches around the configurable targets while
# respecting the wall and both oriented camera keepout rectangles.  Set
# FASTENER_POST_PLACEMENT="manual" to use MANUAL_FASTENER_POST_POSITIONS_XY.
FASTENERS_ENABLED = True
FASTENER_POST_PLACEMENT = "auto"  # "auto" or "manual"
FASTENER_POST_TARGETS_XY = (
    (55.0, -65.0),
    (55.0, 65.0),
    (-5.0, -95.0),
    (-5.0, 95.0),
)
MANUAL_FASTENER_POST_POSITIONS_XY = FASTENER_POST_TARGETS_XY
FASTENER_AUTO_SEARCH_RADIUS = 90.0
FASTENER_AUTO_GRID_STEP = 2.0
FASTENER_POST_DIAMETER = 10.5
FASTENER_POST_EDGE_CLEARANCE = 2.0
FASTENER_POST_CAMERA_CLEARANCE = 10.0
FASTENER_POST_MIN_CENTER_SPACING = 18.0
FASTENER_POST_TOP_CLEARANCE = 0.20

# Removable camera-retaining brackets.  Each top-access L-bracket clamps the
# camera downward and has a rear stop that holds the lens forward through its
# opening.  Two vertical M3 screws per bracket enter heat-set inserts in
# dedicated posts joined to the enclosure bottom.
CAMERA_BRACKETS_ENABLED = True
EXPORT_CAMERA_BRACKET_STLS = True
SHOW_CAMERA_BRACKETS_AFTER_BUILD = True
CAMERA_BRACKET_THICKNESS = 4.8
# In the loose/generated pose the plate clears the highest feature (the top
# button) while two rails reach down toward the solid main-body top.  Tightening
# moves the bracket by body-clearance + preload; the rails then flex against the
# body while the plate still clears the button.
CAMERA_BRACKET_TOP_FEATURE_CLEARANCE_Z = 0.8
CAMERA_BRACKET_BODY_CONTACT_CLEARANCE_Z = 0.2
CAMERA_BRACKET_CLAMP_PRELOAD_Z = 0.15
CAMERA_BRACKET_BUTTON_MIN_CLEARANCE_Z = 0.35
CAMERA_BRACKET_CONTACT_RAIL_WIDTH = 5.0
CAMERA_BRACKET_CONTACT_RAIL_EDGE_INSET = 8.0
CAMERA_BRACKET_CONTACT_RAIL_RADIAL_LENGTH = 8.0
# One contact rail is sufficient because the fixed lower guide and removable
# upper locator prevent yaw/tangential motion.  Keeping the rail on the same
# local side as the upper locator avoids a plate spanning the whole camera.
# "outer" retains the older globally-outboard selection when desired;
# "non_usb" moves all removable retention away from the connector side.
# Disable compact mode to restore two full-width contact rails.
CAMERA_BRACKET_COMPACT_OUTER_RAIL_ONLY = True
CAMERA_BRACKET_COMPACT_RAIL_SIDE = "outer"  # "usb", "non_usb", or "outer"
CAMERA_BRACKET_COMPACT_REAR_LIP_WIDTH = 20.0
CAMERA_BRACKET_COMPACT_POST_TANGENTIAL_SPACING = 22.0
CAMERA_BRACKET_BUTTON_RELIEF_MARGIN = 1.0
CAMERA_BRACKET_OVER_CAMERA_DEPTH = 14.0
CAMERA_BRACKET_REAR_LIP_HEIGHT = 12.0
CAMERA_BRACKET_REAR_LIP_THICKNESS = 3.0
CAMERA_BRACKET_REAR_CLEARANCE = 0.0
CAMERA_BRACKET_REAR_LIP_WIDTH = 62.0
# Split the removable rear stop into two pads so air can sweep the camera back.
# Compact outer-rail mode retains its already-short single rear lip.
CAMERA_BRACKET_SPLIT_REAR_LIP = True
CAMERA_BRACKET_REAR_LIP_CENTER_AIR_GAP = 30.0
CAMERA_BRACKET_REAR_LIP_MIN_SEGMENT_WIDTH = 10.0
# Wrap each enabled side locator around the camera's rounded rear corner and
# into its own rear-face stop.  This produces two continuous L-shaped guides:
# one on the USB/battery side and one on the opposite side, while leaving the
# center of the camera back open to cooling air.  The primary plate projects
# beyond every guide footprint so the downturned walls have a monolithic roof
# rather than meeting a beveled plate edge.
CAMERA_BRACKET_L_CORNER_GUIDES_ENABLED = True
CAMERA_BRACKET_L_CORNER_RETURN_INBOARD_LENGTH = 12.0
CAMERA_BRACKET_GUIDE_PLATE_OVERHANG = 2.0
# Radially grow the solved footprint without changing its vertex topology.
# This preserves a real cavity gap around the stronger/wider bracket roofs;
# adding new sharp hull vertices here would destabilize the loft correspondence.
# With two ordinary fixed brackets, retain the original global allowance their
# broad roofs require.  The cartridge-driven footprint already includes its
# fixed hold-down and leaves enough room for the one remaining fixed bracket,
# so a separate with-cartridge value avoids redundantly deep eye surrounds.
CAMERA_BRACKET_SHELL_EXPANSION = 1.25
CAMERA_BRACKET_SHELL_EXPANSION_WITH_CARTRIDGE = 0.0
CAMERA_BRACKET_LID_POST_CLEARANCE = 1.0
CAMERA_BRACKET_LID_LIP_RELIEF_CLEARANCE = 0.5
CAMERA_BRACKET_OTHER_CAMERA_CLEARANCE = 0.5
CAMERA_BRACKET_WALL_CLEARANCE = 1.0
CAMERA_BRACKET_POST_TANGENTIAL_SPACING = 50.0
CAMERA_BRACKET_POST_REAR_CLEARANCE = 1.0
# The split-eye default loads vertically.  The rearward settings remain
# available when EYE_TOP_LOADING_ENABLED=False for the legacy insertion path.
CAMERA_INSTALLATION_REARWARD_TRAVEL = 17.0
CAMERA_INSTALLATION_LENS_RETRACTION_CLEARANCE = 1.0
CAMERA_INSTALLATION_POST_CLEARANCE = 1.0
CAMERA_TOP_LOADING_LIFT = 62.0
VALIDATE_CAMERA_INSTALLATION_PATH = True
CAMERA_INSTALLATION_PATH_STEPS = 20
CAMERA_INSTALLATION_INTERSECTION_VOLUME_TOLERANCE = 0.01
CAMERA_BRACKET_POST_SEARCH_RADIUS = 60.0
CAMERA_BRACKET_POST_SEARCH_STEP = 2.0
CAMERA_BRACKET_MUTUAL_CLEARANCE = 0.8
CAMERA_BRACKET_POST_BASE_DIAMETER = 18.0
# Keep the clamp over the camera compact: only the contact-rail/rear-stop
# region is a full plate.  Each screw gets a small circular boss and a narrow
# radial arm instead of extending the plate to a large bounding rectangle.
CAMERA_BRACKET_PRIMARY_REAR_OVERLAP = 2.0
CAMERA_BRACKET_PRIMARY_TANGENTIAL_MARGIN = 1.5
CAMERA_BRACKET_ARM_WIDTH = 10.0
# Every arm anchor is driven this far inside the primary plate instead of
# merely touching its nearest corner.  The overlap adds material beyond that
# embedded anchor and beyond the circular screw boss.
CAMERA_BRACKET_ARM_PLATE_EMBED = 7.0
CAMERA_BRACKET_ARM_PLATE_OVERLAP = 2.5
CAMERA_BRACKET_ARM_COUNTERBORE_MIN_WEB = 1.5
CAMERA_BRACKET_BOSS_EDGE_MARGIN = 2.5
CAMERA_BRACKET_BOSS_POST_EDGE_MARGIN = 0.75
# Removable upper corner locators replace the obstructing fixed lower guides.
# They constrain yaw only after the lens has been inserted; the USB-side tab
# remains well above the lower connector/battery access envelope.  HEIGHT is
# the flat-side contact band below the body's rounded top corner; the same tab
# continues upward as a stem embedded into the plate.  Full-length triangular
# outside gussets prevent the downturned cheeks from behaving like butt tabs.
CAMERA_BRACKET_USB_SIDE_LOCATOR_ENABLED = True
CAMERA_BRACKET_USB_SIDE_LOCATOR_HEIGHT = 6.0
CAMERA_BRACKET_USB_SIDE_LOCATOR_THICKNESS = 5.0
CAMERA_BRACKET_USB_SIDE_LOCATOR_RADIAL_LENGTH = 10.0
CAMERA_BRACKET_USB_SIDE_LOCATOR_CLEARANCE = 0.10
CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_ENABLED = True
CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_HEIGHT = 6.0
CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_THICKNESS = 5.0
CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_RADIAL_LENGTH = 10.0
CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_CLEARANCE = 0.10
CAMERA_BRACKET_SIDE_LOCATOR_GUSSETS_ENABLED = True
CAMERA_BRACKET_SIDE_LOCATOR_GUSSET_REACH = 5.0
CAMERA_BRACKET_SIDE_LOCATOR_GUSSET_DEPTH = 7.0
CAMERA_BRACKET_SIDE_LOCATOR_GUSSET_ROOT_EMBED = 1.5
CAMERA_BRACKET_SIDE_LOCATOR_PLATE_EMBED = 2.5
CAMERA_BRACKET_COLOR = (0.82, 0.28, 0.08, 1.0)

# M3 heat-set insert defaults.  Inserts vary by vendor: measure yours and
# override these values.  A 4.0 mm pilot is common for inserts around 4.6 mm
# knurled OD; the smaller pilot supplies the plastic interference for heating.
HEAT_INSERT_HOLE_DIAMETER = 4.0
HEAT_INSERT_HOLE_DEPTH = 15.5
HEAT_INSERT_LEADIN_DIAMETER = 4.8
HEAT_INSERT_LEADIN_DEPTH = 1.0

# M3 socket-head cap screw: 3.4 mm shank clearance and a circular counterbore
# for a nominal 5.5 mm diameter x 3.0 mm high head.  The internal drive is hex;
# the outside of a socket-head cap screw remains cylindrical.
LID_SCREW_CLEARANCE_DIAMETER = 3.4
LID_SCREW_HEAD_COUNTERBORE_DIAMETER = 6.2
LID_SCREW_HEAD_COUNTERBORE_DEPTH = 3.3
CAMERA_BRACKET_MIN_COUNTERBORE_FLOOR = 1.5

# Two 40 mm fan stations on the rounded rear (+X) wall.  Each fan
# seats against an exact 45 x 45 mm flat plane.  Standard 40 mm fan mounting
# centers are 32 mm apart in both axes.  By default the two centers sit at the
# configurable +/- centerline offset and each pad follows the rear wall's local
# tangent.  Set REAR_FAN_CENTER_TANGENTS to two signed global-Y offsets for an
# asymmetric layout.
REAR_FANS_ENABLED = True
REAR_FAN_PAD_SIZE = 45.0
REAR_FAN_PAD_GAP = 4.0
# Signed centers default to +/- this global-Y distance.  Set it to None to
# derive the distance from (pad size + pad gap) / 2 instead.
REAR_FAN_CENTERLINE_OFFSET = 32.5
REAR_FAN_CENTER_TANGENTS = None
REAR_FAN_CENTER_Z = 35.0
REAR_FAN_ALIGN_TO_LOCAL_WALL = True
REAR_FAN_WALL_ANGLE_SAMPLE_DISTANCE = 1.0
# True puts the flat fan seating planes inside the cavity (the default).  False
# restores external pads.  FACE_OUTSET is measured inward or outward from the
# corresponding nominal wall surface, depending on this selection.
REAR_FAN_PAD_INSIDE = True
REAR_FAN_PAD_FACE_OUTSET = 1.5
REAR_FAN_PAD_SURFACE_SAMPLES = 24
REAR_FAN_MOUNT_SPACING = 32.0
REAR_FAN_MOUNT_HOLE_DIAMETER = 3.4
REAR_FAN_AIR_OPENING_DIAMETER = 36.0
# Default model is a 40 x 40 x 10 mm Noctua-style fan mounted inside and
# blowing inward.  The keepout is validated against both camera stations and
# every cartridge yaw pose; change depth for a 40 x 20 mm fan.
REAR_FAN_DEPTH = 10.0
REAR_FAN_HUB_DIAMETER = 20.0
REAR_FAN_BODY_CLEARANCE = 1.0
REAR_FAN_AIRFLOW_DIRECTION = "intake"
VALIDATE_REAR_FAN_BODY_CLEARANCE = True
REAR_FAN_CUTTER_INWARD_EXTENSION = 8.0
REAR_FAN_MIN_WEB = 2.0
# Treat the two lens/eye annuli as the primary front exhausts.  These limits
# preserve a rear-fan -> camera body -> eye-opening flow path without adding
# rain/debris-facing perforations to the removable lid.
CAMERA_COOLING_MIN_EXHAUST_TO_FAN_AREA_RATIO = 0.75
CAMERA_COOLING_MIN_EYE_EDGE_GAP = 1.5

# Vertical floor mount for a nominal 1/4-20 UNC fastener.  By default an
# interior boss captures a standard 1/4-inch finished hex nut in a slightly
# undersized press-fit pocket.  Six independent ramped lips let the nut press
# in from above and then catch its top face.  Measure the actual nut and printer
# before production; inch fastener hardware varies by standard and coating.
BOTTOM_MOUNT_HOLE_ENABLED = True
BOTTOM_MOUNT_HOLE_FRONT_TO_BACK_FRACTION = 0.50
BOTTOM_MOUNT_HOLE_LATERAL_TARGET = 0.0
BOTTOM_MOUNT_HOLE_DIAMETER = 6.8
BOTTOM_MOUNT_HOLE_EDGE_CLEARANCE = 3.0
BOTTOM_MOUNT_HOLE_KEEP_OUT_CLEARANCE = 2.0
BOTTOM_MOUNT_HOLE_AUTO_LATERAL = True
BOTTOM_MOUNT_HOLE_SEARCH_RANGE = 80.0
BOTTOM_MOUNT_HOLE_SEARCH_STEP = 2.0
# The preferred fraction remains authoritative when it fits.  When the camera
# envelopes occupy that whole cross-section, this optional search chooses the
# closest safe fore/aft station and prints the resolved fraction.
BOTTOM_MOUNT_HOLE_AUTO_FRONT_TO_BACK = True
BOTTOM_MOUNT_HOLE_FRACTION_SEARCH_RANGE = 0.40
BOTTOM_MOUNT_HOLE_FRACTION_SEARCH_STEP = 0.01
BOTTOM_MOUNT_NUT_HOLDER_ENABLED = True
BOTTOM_MOUNT_NUT_THREAD_DIAMETER = 6.35
BOTTOM_MOUNT_NUT_ACROSS_FLATS = 11.11
BOTTOM_MOUNT_NUT_THICKNESS = 5.56
BOTTOM_MOUNT_NUT_PRESS_INTERFERENCE = 0.15
BOTTOM_MOUNT_NUT_ROTATION_DEG = 0.0
BOTTOM_MOUNT_NUT_HOLDER_OUTER_DIAMETER = 24.0
BOTTOM_MOUNT_NUT_HOLDER_MIN_WALL = 4.0
BOTTOM_MOUNT_NUT_MIN_SEAT_WIDTH = 2.0
BOTTOM_MOUNT_NUT_THICKNESS_TOLERANCE = 0.3
BOTTOM_MOUNT_NUT_SNAP_LIP_RETENTION_CLEARANCE = 0.35
BOTTOM_MOUNT_NUT_SNAP_LIP_HEIGHT = 1.5
BOTTOM_MOUNT_NUT_SNAP_LIP_PROJECTION = 0.4
BOTTOM_MOUNT_NUT_SNAP_LIP_WIDTH = 3.5
BOTTOM_MOUNT_NUT_SNAP_ROOT_EMBED = 0.4
BOTTOM_MOUNT_NUT_SNAP_RELIEF_ENABLED = True
BOTTOM_MOUNT_NUT_SNAP_FLEX_WALL_THICKNESS = 0.8
BOTTOM_MOUNT_NUT_SNAP_RELIEF_DEPTH = 0.5
BOTTOM_MOUNT_NUT_SNAP_SIDE_SLOT_WIDTH = 0.6
BOTTOM_MOUNT_NUT_SNAP_FLEX_HEIGHT = 1.5
BOTTOM_MOUNT_NUT_HOLDER_UNION_SOLVER = "MANIFOLD"

# Three bottom-facing keystone sockets grouped near one rear corner.  The
# default imports the supplied proven socket geometry, seats its exterior face
# exactly at Z=0, and leaves its insertion opening facing the enclosure.  The
# generic pocket/cutout dimensions remain available as a legacy fallback.
BOTTOM_KEYSTONES_ENABLED = True
BOTTOM_KEYSTONE_COUNT = 3
BOTTOM_KEYSTONE_CORNER_Y_SIGN = 1.0
BOTTOM_KEYSTONE_ROW_AXIS = "y"  # "x" runs rear-to-front; "y" runs toward center.
BOTTOM_KEYSTONE_USE_REFERENCE_SNAP_SOCKET = True
BOTTOM_KEYSTONE_REFERENCE_STL = "/home/colivier/Downloads/Keystone Connector.stl"
BOTTOM_KEYSTONE_REFERENCE_SHA256 = (
    "fc71ad6a3c78fa4a76e2909f688800cf900bd4a22e78868db25a4c9470a41c20"
)
BOTTOM_KEYSTONE_REFERENCE_DIMENSION_TOLERANCE = 0.10
BOTTOM_KEYSTONE_SOCKET_OUTER_X = 17.7
BOTTOM_KEYSTONE_SOCKET_OUTER_Y = 25.0
BOTTOM_KEYSTONE_SOCKET_HEIGHT = 9.75
BOTTOM_KEYSTONE_SOCKET_INNER_CLEAR_X = 14.7
BOTTOM_KEYSTONE_SOCKET_INNER_CLEAR_Y = 22.0
BOTTOM_KEYSTONE_SOCKET_BASE_CLEARANCE = 0.10
BOTTOM_KEYSTONE_SOCKET_ROTATION_DEG = 0.0
BOTTOM_KEYSTONE_CUTOUT_X = 16.1
BOTTOM_KEYSTONE_CUTOUT_Y = 14.7
BOTTOM_KEYSTONE_FACE_POCKET_X = 19.5
BOTTOM_KEYSTONE_FACE_POCKET_Y = 16.6
BOTTOM_KEYSTONE_FACE_RECESS_DEPTH = 1.5
BOTTOM_KEYSTONE_INTERNAL_BODY_X = 22.0
BOTTOM_KEYSTONE_INTERNAL_BODY_Y = 25.0
BOTTOM_KEYSTONE_INTERNAL_BODY_HEIGHT = 30.0
BOTTOM_KEYSTONE_CENTER_SPACING = 30.0
BOTTOM_KEYSTONE_REAR_EDGE_INSET = 10.0
BOTTOM_KEYSTONE_SIDE_EDGE_INSET = 10.0
BOTTOM_KEYSTONE_EDGE_CLEARANCE = 2.0
BOTTOM_KEYSTONE_KEEP_OUT_CLEARANCE = 2.0
BOTTOM_KEYSTONE_AUTO_PLACEMENT = True
BOTTOM_KEYSTONE_SEARCH_RANGE = 110.0
BOTTOM_KEYSTONE_SEARCH_STEP = 2.0

# Geometry quality.
ROUNDED_CORNER_SEGMENTS = 14
BOOLEAN_SOLVER = "EXACT"
BOOLEAN_OVERLAP = 0.25
BOOLEAN_CLEANUP_DISTANCE = 0.0001

COVER_COLOR = (0.10, 0.38, 0.72, 1.0)
LID_COLOR = (0.12, 0.62, 0.34, 1.0)
CAMERA_COLOR = (0.03, 0.035, 0.045, 1.0)

# Set during layout solving; kept private so repeated Blender builds can reset
# it and respond to changed configuration values.
_RESOLVED_CAMERA_LENS_FACE_OUTSET = None


# ---------------------------------------------------------------------------
# Configuration and scene helpers


def point_inside_rounded_rectangle(
    point,
    width: float,
    height: float,
    radius: float,
) -> bool:
    """Test a centered 2D point against a rounded rectangle."""
    half_width = width / 2.0
    half_height = height / 2.0
    radius = min(max(radius, 0.0), half_width, half_height)
    x = abs(point[0])
    z = abs(point[1])
    if x > half_width or z > half_height:
        return False
    dx = max(x - (half_width - radius), 0.0)
    dz = max(z - (half_height - radius), 0.0)
    return dx * dx + dz * dz <= radius * radius + 1e-9


def camera_eye_center_z() -> float:
    if EYE_CENTER_Z is not None:
        return float(EYE_CENTER_Z)
    camera_vertical_min = mission1.canonical_vertical_bounds(
        CAMERA_UPSIDE_DOWN
    )[0]
    return (
        BOTTOM_THICKNESS
        + CAMERA_FLOOR_CLEARANCE
        - camera_vertical_min
    )


def camera_lens_face_outset() -> float:
    if _RESOLVED_CAMERA_LENS_FACE_OUTSET is not None:
        return _RESOLVED_CAMERA_LENS_FACE_OUTSET
    if CAMERA_FORWARD_PLACEMENT_MODE == "manual":
        return float(CAMERA_LENS_FACE_OUTSET)
    body_radial = mission1.canonical_body_bounds(CAMERA_UPSIDE_DOWN)[0]
    return (
        -body_radial[1]
        - EYE_FACE_INSET
        - EYE_BEZEL_DEPTH
        - CAMERA_FRONT_STOP_PROJECTION
    )


def camera_front_stop_projection() -> float:
    """Gap from the eye-surround backplane to the front-body plane."""
    body_radial = mission1.canonical_body_bounds(CAMERA_UPSIDE_DOWN)[0]
    return -EYE_FACE_INSET - EYE_BEZEL_DEPTH - (
        camera_lens_face_outset() + body_radial[1]
    )


def camera_front_stop_specs():
    """Resolve three contact patches on solid wall and flat camera face."""
    _, body_tangent, body_vertical = mission1.canonical_body_bounds(
        CAMERA_UPSIDE_DOWN
    )
    flat_tangent = (
        body_tangent[0] + mission1.BODY_CORNER_RADIUS,
        body_tangent[1] - mission1.BODY_CORNER_RADIUS,
    )
    flat_vertical = (
        body_vertical[0] + mission1.BODY_CORNER_RADIUS,
        body_vertical[1] - mission1.BODY_CORNER_RADIUS,
    )
    eye_half_width = EYE_OPENING_WIDTH / 2.0
    eye_half_height = EYE_OPENING_HEIGHT / 2.0
    land = CAMERA_FRONT_STOP_WALL_LAND

    negative_side_room = -eye_half_width - land - flat_tangent[0]
    positive_side_room = flat_tangent[1] - (eye_half_width + land)
    if negative_side_room >= positive_side_room:
        tangent_max = -eye_half_width - land
        tangent_min = tangent_max - CAMERA_FRONT_STOP_SIDE_WIDTH
    else:
        tangent_min = eye_half_width + land
        tangent_max = tangent_min + CAMERA_FRONT_STOP_SIDE_WIDTH
    if (
        tangent_min < flat_tangent[0] - 1e-6
        or tangent_max > flat_tangent[1] + 1e-6
    ):
        raise ValueError("No flat side land remains for camera front stops")

    vertical_min = max(flat_vertical[0], -eye_half_height + land)
    vertical_max = min(flat_vertical[1], eye_half_height - land)
    side_half_height = CAMERA_FRONT_STOP_SIDE_HEIGHT / 2.0
    side_centers = (
        vertical_min + side_half_height,
        vertical_max - side_half_height,
    )
    if side_centers[1] - side_centers[0] < (
        CAMERA_FRONT_STOP_SIDE_HEIGHT / 2.0
    ):
        raise ValueError("Camera front side stops do not fit vertically")

    bottom_room = -eye_half_height - land - flat_vertical[0]
    top_room = flat_vertical[1] - (eye_half_height + land)
    if bottom_room >= top_room:
        rim_max = -eye_half_height - land
        rim_min = rim_max - CAMERA_FRONT_STOP_RIM_HEIGHT
    else:
        rim_min = eye_half_height + land
        rim_max = rim_min + CAMERA_FRONT_STOP_RIM_HEIGHT
    if (
        rim_min < flat_vertical[0] - 1e-6
        or rim_max > flat_vertical[1] + 1e-6
    ):
        raise ValueError("No flat bottom/top land remains for camera front stop")
    rim_tangent_min = -CAMERA_FRONT_STOP_RIM_WIDTH / 2.0
    rim_tangent_max = CAMERA_FRONT_STOP_RIM_WIDTH / 2.0
    if (
        rim_tangent_min < flat_tangent[0] - 1e-6
        or rim_tangent_max > flat_tangent[1] + 1e-6
    ):
        raise ValueError("Camera front rim stop exceeds the flat body face")

    side_tangent = (tangent_min + tangent_max) / 2.0
    rim_vertical = (rim_min + rim_max) / 2.0
    return (
        (
            "Side_Lower",
            side_tangent,
            side_centers[0],
            CAMERA_FRONT_STOP_SIDE_WIDTH,
            CAMERA_FRONT_STOP_SIDE_HEIGHT,
        ),
        (
            "Side_Upper",
            side_tangent,
            side_centers[1],
            CAMERA_FRONT_STOP_SIDE_WIDTH,
            CAMERA_FRONT_STOP_SIDE_HEIGHT,
        ),
        (
            "Rim",
            0.0,
            rim_vertical,
            CAMERA_FRONT_STOP_RIM_WIDTH,
            CAMERA_FRONT_STOP_RIM_HEIGHT,
        ),
    )


def camera_support_pad_tangent_centers():
    """Resolve two body-bottom pads while avoiding a downward-facing button."""
    body_radial, body_tangent, body_vertical = mission1.canonical_body_bounds(
        CAMERA_UPSIDE_DOWN
    )
    flat_min = body_tangent[0] + mission1.BODY_CORNER_RADIUS
    flat_max = body_tangent[1] - mission1.BODY_CORNER_RADIUS
    half_width = CAMERA_SUPPORT_PAD_TANGENTIAL_WIDTH / 2.0
    low = flat_min + half_width
    high = flat_max - half_width
    if low >= high:
        raise ValueError("Camera support pads do not fit the body-bottom width")
    body_center = sum(body_tangent) / 2.0
    nominal_half_spacing = CAMERA_SUPPORT_PAD_TANGENTIAL_SPACING / 2.0
    obstacles = []
    button_radial, button_tangent, button_vertical = (
        mission1.canonical_top_button_bounds(CAMERA_UPSIDE_DOWN)
    )
    pad_radial_center = sum(body_radial) / 2.0
    pad_radial = (
        pad_radial_center - CAMERA_SUPPORT_PAD_RADIAL_LENGTH / 2.0,
        pad_radial_center + CAMERA_SUPPORT_PAD_RADIAL_LENGTH / 2.0,
    )
    radial_overlap = (
        pad_radial[0] < button_radial[1]
        and button_radial[0] < pad_radial[1]
    )
    if button_vertical[0] < body_vertical[0] - 1e-6 and radial_overlap:
        obstacles.append(
            (
                button_tangent[0] - CAMERA_SUPPORT_FEATURE_CLEARANCE,
                button_tangent[1] + CAMERA_SUPPORT_FEATURE_CLEARANCE,
            )
        )

    def valid(center):
        interval = (center - half_width, center + half_width)
        return low - 1e-6 <= center <= high + 1e-6 and not any(
            interval[0] < obstacle[1] and obstacle[0] < interval[1]
            for obstacle in obstacles
        )

    nominal = (
        body_center - nominal_half_spacing,
        body_center + nominal_half_spacing,
    )
    if valid(nominal[0]) and valid(nominal[1]):
        return nominal

    step = 0.25
    count = int(math.ceil((high - low) / step))
    candidates = [low + index * (high - low) / count for index in range(count + 1)]
    candidates = [center for center in candidates if valid(center)]
    pairs = []
    minimum_separation = (
        CAMERA_SUPPORT_PAD_TANGENTIAL_WIDTH + CAMERA_SUPPORT_PAD_MIN_GAP
    )
    for first_index, first in enumerate(candidates):
        for second in candidates[first_index + 1 :]:
            separation = second - first
            if separation < minimum_separation:
                continue
            score = (
                abs(separation - CAMERA_SUPPORT_PAD_TANGENTIAL_SPACING),
                abs((first + second) / 2.0 - body_center),
                -separation,
            )
            pairs.append((score, (first, second)))
    if not pairs:
        raise ValueError("No two camera support pads avoid bottom-side features")
    pairs.sort(key=lambda item: item[0])
    return pairs[0][1]


def resolved_camera_cradle_side_guide_height() -> float:
    """Keep the snug lower guide below the lens housing's slide path."""
    if not CAMERA_CRADLE_SIDE_GUIDE_AUTO_CLEAR_LENS_PATH:
        return CAMERA_CRADLE_SIDE_GUIDE_HEIGHT
    _, _, body_vertical = mission1.canonical_body_bounds(CAMERA_UPSIDE_DOWN)
    body_bottom = body_vertical[0]
    lens_bottom = -mission1.LENS_FACE_HEIGHT / 2.0
    maximum_height = (
        lens_bottom
        - body_bottom
        - CAMERA_CRADLE_SIDE_GUIDE_LENS_PATH_CLEARANCE
    )
    return min(CAMERA_CRADLE_SIDE_GUIDE_HEIGHT, maximum_height)


def eye_top_loading_slot_bottom_z() -> float:
    return camera_eye_center_z() + EYE_TOP_LOADING_SLOT_BOTTOM_OFFSET_Z


def camera_cradle_rear_guides_enabled() -> bool:
    """Rear stops are permanent only when the camera installs from above."""
    return CAMERA_CRADLE_REAR_GUIDE_ENABLED and EYE_TOP_LOADING_ENABLED


def resolved_visor_vertical_shift() -> float:
    if not VISOR_AUTO_CLEAR_CAMERA:
        return 0.0
    lens_top = camera_eye_center_z() + mission1.LENS_FACE_HEIGHT / 2.0
    required_bottom = lens_top + VISOR_CAMERA_VERTICAL_CLEARANCE
    return max(
        0.0,
        required_bottom - min(VISOR_BACK_BOTTOM_Z, VISOR_FRONT_BOTTOM_Z),
    )


def resolved_visor_back_inset() -> float:
    if not VISOR_AUTO_CLEAR_CAMERA:
        return VISOR_BACK_INSET
    body_radial = mission1.canonical_body_bounds(CAMERA_UPSIDE_DOWN)[0]
    body_front_from_surface = camera_lens_face_outset() + body_radial[1]
    maximum_safe_inset = max(
        -body_front_from_surface - VISOR_CAMERA_BODY_RADIAL_CLEARANCE,
        0.0,
    )
    maximum_safe_inset = min(
        maximum_safe_inset,
        VISOR_LID_SAFE_MAX_BACK_INSET,
    )
    return min(VISOR_BACK_INSET, maximum_safe_inset)


def resolved_visor_z(value: float) -> float:
    resolved = value + resolved_visor_vertical_shift()
    # The base owns the two fixed visor wings and the lid owns only the center
    # that passes through the U-slot.  Keeping the common visor profile at or
    # below the joint plane prevents either wing from entering the lid plate.
    if VISOR_AUTO_CLEAR_CAMERA:
        resolved = min(resolved, BASE_HEIGHT)
    return resolved


def eye_opening_cutter_radial_bounds(camera):
    surface = camera["surface"]
    return (
        surface
        - BODY_WALL_THICKNESS
        - EYE_BEZEL_DEPTH
        - EYE_FACE_INSET
        - EYE_CUTTER_INWARD_EXTRA,
        surface + EYE_CUTTER_OUTWARD_EXTENSION,
    )


def eye_lid_closure_radial_bounds(camera):
    """Return central tongue and inside backing-flange radial bounds."""
    wall_inner = camera["eye_inner_wall"]
    backing_max = wall_inner - EYE_LID_CLOSURE_RADIAL_CLEARANCE
    backing_min = backing_max - EYE_LID_CLOSURE_BACKING_THICKNESS
    main_min = backing_max - BOOLEAN_OVERLAP
    main_max = (
        camera["surface"]
        - EYE_FACE_INSET
        - EYE_LID_CLOSURE_RADIAL_CLEARANCE
    )
    if main_max <= main_min:
        raise ValueError("Eye-lid closure has no positive radial thickness")
    return (main_min, main_max), (backing_min, backing_max)


def camera_usb_side_name() -> str:
    if CAMERA_USB_SIDE == "auto":
        return "tangent_max" if CAMERA_UPSIDE_DOWN else "tangent_min"
    return CAMERA_USB_SIDE


def camera_usb_side_sign() -> float:
    return -1.0 if camera_usb_side_name() == "tangent_min" else 1.0


def camera_carrier_side_guide_specs(body_radial, body_tangent):
    """Return stout end-guide segments with an open cooling/USB middle."""
    side_specs = (
        (
            "tangent_min",
            body_tangent[0]
            - CAMERA_CARRIER_CAMERA_CLEARANCE
            - CAMERA_CARRIER_GUIDE_THICKNESS / 2.0,
        ),
        (
            "tangent_max",
            body_tangent[1]
            + CAMERA_CARRIER_CAMERA_CLEARANCE
            + CAMERA_CARRIER_GUIDE_THICKNESS / 2.0,
        ),
    )
    usb_side = camera_usb_side_name()
    radial_span = body_radial[1] - body_radial[0]
    end_length = min(
        CAMERA_CARRIER_SIDE_GUIDE_END_LENGTH,
        radial_span / 2.0,
    )
    usb_radial = camera_usb_local_access_bounds()[0]
    lens_half_width = mission1.LENS_FACE_WIDTH / 2.0
    lens_overhang_sides = set()
    if body_tangent[0] > -lens_half_width:
        lens_overhang_sides.add("tangent_min")
    if body_tangent[1] < lens_half_width:
        lens_overhang_sides.add("tangent_max")
    result = []
    for side_name, tangent in side_specs:
        enabled = (
            CAMERA_CARRIER_USB_SIDE_GUIDE_ENABLED
            if side_name == usb_side
            else CAMERA_CARRIER_NON_USB_SIDE_GUIDE_ENABLED
        )
        if not enabled:
            continue
        if side_name == usb_side:
            segments = (
                (
                    body_radial[0],
                    min(body_radial[1], usb_radial[0]),
                    "rear",
                ),
                (
                    max(body_radial[0], usb_radial[1]),
                    body_radial[1],
                    "front",
                ),
            )
            minimum_length = CAMERA_CARRIER_USB_GUIDE_MIN_SEGMENT_LENGTH
        else:
            segments = (
                (
                    body_radial[0],
                    body_radial[0] + end_length,
                    "rear",
                ),
                (
                    body_radial[1] - end_length,
                    body_radial[1],
                    "front",
                ),
            )
            minimum_length = 0.5
        for radial_min, radial_max, segment_name in segments:
            # The lens taper overhangs one asymmetric main-body side near the
            # front face.  A rectangular front guide there would collide with
            # the lens shoulder; the rear guide and opposite front datum still
            # locate the camera while leaving this area open to cooling air.
            if (
                segment_name == "front"
                and side_name in lens_overhang_sides
            ):
                continue
            if radial_max - radial_min < minimum_length:
                continue
            if segment_name == "rear":
                radial_min -= CAMERA_CARRIER_REAR_CORNER_OVERLAP
            result.append(
                (
                    side_name,
                    segment_name,
                    tangent,
                    radial_min,
                    radial_max,
                )
            )
    return tuple(result)


def camera_carrier_side_air_channel_widths(body_radial, body_tangent):
    """Return the largest unobstructed radial channel on each guided side."""
    widths = {}
    specs = camera_carrier_side_guide_specs(body_radial, body_tangent)
    for side_name in ("tangent_min", "tangent_max"):
        intervals = sorted(
            (
                max(body_radial[0], radial_min),
                min(body_radial[1], radial_max),
            )
            for side, _, _, radial_min, radial_max in specs
            if side == side_name
            and radial_max > body_radial[0]
            and radial_min < body_radial[1]
        )
        if not intervals:
            continue
        cursor = body_radial[0]
        largest_gap = 0.0
        for interval_min, interval_max in intervals:
            largest_gap = max(largest_gap, interval_min - cursor)
            cursor = max(cursor, interval_max)
        widths[side_name] = max(largest_gap, body_radial[1] - cursor)
    return widths


def camera_carrier_end_guide_specs(body_radial, body_tangent):
    """Return split rear stops and the compact front datum in local bounds."""
    body_tangent_center = sum(body_tangent) / 2.0
    rear_segment_width = (
        CAMERA_CARRIER_REAR_GUIDE_TOTAL_WIDTH
        - CAMERA_CARRIER_REAR_GUIDE_CENTER_AIR_GAP
    ) / 2.0
    rear_segment_offset = (
        CAMERA_CARRIER_REAR_GUIDE_CENTER_AIR_GAP + rear_segment_width
    ) / 2.0
    radial_rear_max = body_radial[0] - CAMERA_CARRIER_CAMERA_CLEARANCE
    radial_rear_min = radial_rear_max - CAMERA_CARRIER_GUIDE_THICKNESS
    result = []
    for rear_index, tangent_sign in enumerate((-1.0, 1.0), start=1):
        tangent_center = (
            body_tangent_center + tangent_sign * rear_segment_offset
        )
        tangent_min = tangent_center - rear_segment_width / 2.0
        tangent_max = tangent_center + rear_segment_width / 2.0
        if tangent_sign < 0.0:
            tangent_min -= CAMERA_CARRIER_REAR_CORNER_OVERLAP
        else:
            tangent_max += CAMERA_CARRIER_REAR_CORNER_OVERLAP
        result.append(
            (
                f"rear_{rear_index}",
                radial_rear_min,
                radial_rear_max,
                tangent_min,
                tangent_max,
            )
        )

    # Put the front datum on the broad flat body land beyond the lens/eye
    # housing, not at the battery-side corner where the protruding lens lives.
    lens_side_keepout = max(
        EYE_OPENING_WIDTH / 2.0 + CAMERA_FRONT_STOP_WALL_LAND,
        mission1.LENS_SHOULDER_WIDTH / 2.0
        + CAMERA_LENS_OPENING_CLEARANCE,
    )
    flat_tangent_min = body_tangent[0] + mission1.BODY_CORNER_RADIUS
    flat_tangent_max = body_tangent[1] - mission1.BODY_CORNER_RADIUS
    negative_room = -lens_side_keepout - flat_tangent_min
    positive_room = flat_tangent_max - lens_side_keepout
    if negative_room >= positive_room:
        front_tangent_max = -lens_side_keepout
        front_tangent_min = (
            front_tangent_max - CAMERA_CARRIER_FRONT_STOP_WIDTH
        )
    else:
        front_tangent_min = lens_side_keepout
        front_tangent_max = (
            front_tangent_min + CAMERA_CARRIER_FRONT_STOP_WIDTH
        )
    front_radial_min = body_radial[1] + CAMERA_CARRIER_CAMERA_CLEARANCE
    result.append(
        (
            "front_stop",
            front_radial_min,
            front_radial_min
            + CAMERA_CARRIER_GUIDE_THICKNESS
            - CAMERA_CARRIER_SWEEP_CUT_CLEARANCE,
            front_tangent_min,
            front_tangent_max,
        )
    )
    return tuple(result)


def camera_carrier_tray_airflow_metrics(body_radial, body_tangent):
    """Return vent intervals, open area, and camera-plan open-area ratio."""
    tray_radial_min = body_radial[0] - CAMERA_CARRIER_TRAY_RADIAL_MARGIN
    tray_radial_max = body_radial[1] + CAMERA_CARRIER_TRAY_RADIAL_MARGIN
    tray_tangent_min = (
        body_tangent[0] - CAMERA_CARRIER_TRAY_TANGENTIAL_MARGIN
    )
    tray_tangent_max = (
        body_tangent[1] + CAMERA_CARRIER_TRAY_TANGENTIAL_MARGIN
    )
    vent_radial_min = tray_radial_min + CAMERA_CARRIER_TRAY_FRAME_WIDTH
    vent_radial_max = tray_radial_max - CAMERA_CARRIER_TRAY_FRAME_WIDTH
    vent_tangent_min = tray_tangent_min + CAMERA_CARRIER_TRAY_FRAME_WIDTH
    vent_tangent_max = tray_tangent_max - CAMERA_CARRIER_TRAY_FRAME_WIDTH
    half_rail = CAMERA_CARRIER_SUPPORT_RAIL_WIDTH / 2.0
    front_stop_spec = camera_carrier_end_guide_specs(
        body_radial,
        body_tangent,
    )[-1]
    front_stop_tangent_center = (
        front_stop_spec[3] + front_stop_spec[4]
    ) / 2.0
    retained_specs = [
        (tangent, half_rail)
        for tangent in camera_support_pad_tangent_centers()
    ]
    retained_specs.append(
        (
            front_stop_tangent_center,
            CAMERA_CARRIER_FRONT_STOP_ROOT_RAIL_WIDTH / 2.0,
        )
    )
    retained_intervals = sorted(
        (
            max(vent_tangent_min, tangent - retained_half_width),
            min(vent_tangent_max, tangent + retained_half_width),
        )
        for tangent, retained_half_width in retained_specs
        if tangent + retained_half_width > vent_tangent_min
        and tangent - retained_half_width < vent_tangent_max
    )
    cursor = vent_tangent_min
    vent_intervals = []
    for interval_min, interval_max in retained_intervals:
        if interval_min > cursor + 0.5:
            vent_intervals.append((cursor, interval_min))
        cursor = max(cursor, interval_max)
    if cursor < vent_tangent_max - 0.5:
        vent_intervals.append((cursor, vent_tangent_max))
    vent_open_area = (
        max(vent_radial_max - vent_radial_min, 0.0)
        * sum(
            tangent_max - tangent_min
            for tangent_min, tangent_max in vent_intervals
        )
    )
    camera_plan_area = (
        (body_radial[1] - body_radial[0])
        * (body_tangent[1] - body_tangent[0])
    )
    return (
        vent_radial_min,
        vent_radial_max,
        tuple(vent_intervals),
        vent_open_area,
        vent_open_area / max(camera_plan_area, 1e-6),
    )


def rounded_rectangle_area(width, height, radius):
    radius = min(max(radius, 0.0), width / 2.0, height / 2.0)
    return width * height - (4.0 - math.pi) * radius * radius


def forced_airflow_path_metrics():
    """Return gross/effective fan and lens-annulus exhaust areas."""
    fan_open_area = 2.0 * math.pi * (REAR_FAN_AIR_OPENING_DIAMETER / 2.0) ** 2
    fan_effective_open_area = 2.0 * math.pi * (
        (REAR_FAN_AIR_OPENING_DIAMETER / 2.0) ** 2
        - (REAR_FAN_HUB_DIAMETER / 2.0) ** 2
    )
    eye_area = rounded_rectangle_area(
        EYE_OPENING_WIDTH,
        EYE_OPENING_HEIGHT,
        EYE_OPENING_CORNER_RADIUS,
    )
    lens_area = rounded_rectangle_area(
        mission1.LENS_FACE_WIDTH,
        mission1.LENS_FACE_HEIGHT,
        mission1.LENS_FACE_CORNER_RADIUS,
    )
    exhaust_area = 2.0 * max(eye_area - lens_area, 0.0)
    minimum_edge_gap = min(
        (EYE_OPENING_WIDTH - mission1.LENS_FACE_WIDTH) / 2.0,
        (EYE_OPENING_HEIGHT - mission1.LENS_FACE_HEIGHT) / 2.0,
    )
    return (
        fan_open_area,
        fan_effective_open_area,
        exhaust_area,
        exhaust_area / max(fan_open_area, 1e-6),
        exhaust_area / max(fan_effective_open_area, 1e-6),
        minimum_edge_gap,
    )


def camera_usb_local_access_bounds():
    body_radial, body_tangent, body_vertical = mission1.canonical_body_bounds(
        CAMERA_UPSIDE_DOWN
    )
    radial_center = (
        sum(body_radial) / 2.0
        + CAMERA_USB_PORT_RADIAL_OFFSET_FROM_BODY_CENTER
    )
    radial_half = (
        CAMERA_USB_PORT_RADIAL_WIDTH / 2.0
        + CAMERA_USB_ACCESS_RADIAL_CLEARANCE
    )
    vertical_center = (
        body_vertical[0] + CAMERA_USB_PORT_CENTER_ABOVE_BODY_BOTTOM
    )
    vertical_half = (
        CAMERA_USB_PORT_HEIGHT / 2.0
        + CAMERA_USB_ACCESS_VERTICAL_CLEARANCE
    )
    side_sign = camera_usb_side_sign()
    body_side = body_tangent[0] if side_sign < 0.0 else body_tangent[1]
    if side_sign < 0.0:
        tangent = (
            body_side - CAMERA_USB_PLUG_OUTWARD_DEPTH,
            body_side + CAMERA_USB_PLUG_BODY_OVERLAP,
        )
    else:
        tangent = (
            body_side - CAMERA_USB_PLUG_BODY_OVERLAP,
            body_side + CAMERA_USB_PLUG_OUTWARD_DEPTH,
        )
    return (
        (radial_center - radial_half, radial_center + radial_half),
        tangent,
        (vertical_center - vertical_half, vertical_center + vertical_half),
    )


def bottom_mount_nut_pocket_across_flats() -> float:
    return BOTTOM_MOUNT_NUT_ACROSS_FLATS - BOTTOM_MOUNT_NUT_PRESS_INTERFERENCE


def bottom_mount_nut_seat_z() -> float:
    return BOTTOM_THICKNESS


def bottom_mount_nut_snap_shoulder_z() -> float:
    return (
        bottom_mount_nut_seat_z()
        + BOTTOM_MOUNT_NUT_THICKNESS
        + BOTTOM_MOUNT_NUT_THICKNESS_TOLERANCE
        + BOTTOM_MOUNT_NUT_SNAP_LIP_RETENTION_CLEARANCE
    )


def bottom_mount_nut_snap_relief_base_z() -> float:
    return (
        bottom_mount_nut_snap_shoulder_z()
        - BOTTOM_MOUNT_NUT_SNAP_FLEX_HEIGHT
    )


def bottom_mount_nut_holder_top_z() -> float:
    return (
        bottom_mount_nut_snap_shoulder_z()
        + BOTTOM_MOUNT_NUT_SNAP_LIP_HEIGHT
    )


def bottom_mount_feature_radius() -> float:
    if BOTTOM_MOUNT_NUT_HOLDER_ENABLED:
        return BOTTOM_MOUNT_NUT_HOLDER_OUTER_DIAMETER / 2.0
    return BOTTOM_MOUNT_HOLE_DIAMETER / 2.0


def bottom_keystone_socket_plan_dimensions():
    if not BOTTOM_KEYSTONE_USE_REFERENCE_SNAP_SOCKET:
        return 0.0, 0.0
    angle = math.radians(BOTTOM_KEYSTONE_SOCKET_ROTATION_DEG)
    cosine = abs(math.cos(angle))
    sine = abs(math.sin(angle))
    return (
        BOTTOM_KEYSTONE_SOCKET_OUTER_X * cosine
        + BOTTOM_KEYSTONE_SOCKET_OUTER_Y * sine,
        BOTTOM_KEYSTONE_SOCKET_OUTER_X * sine
        + BOTTOM_KEYSTONE_SOCKET_OUTER_Y * cosine,
    )


def validate_config() -> None:
    positive = {
        "BODY_WIDTH": BODY_WIDTH,
        "BODY_DEPTH": BODY_DEPTH,
        "BODY_HEIGHT": BODY_HEIGHT,
        "BASE_HEIGHT": BASE_HEIGHT,
        "LID_THICKNESS": LID_THICKNESS,
        "BOTTOM_THICKNESS": BOTTOM_THICKNESS,
        "BODY_WALL_THICKNESS": BODY_WALL_THICKNESS,
        "EYE_OPENING_WIDTH": EYE_OPENING_WIDTH,
        "EYE_OPENING_HEIGHT": EYE_OPENING_HEIGHT,
        "EYE_TOP_LOADING_SLOT_WIDTH": EYE_TOP_LOADING_SLOT_WIDTH,
        "EYE_LID_CLOSURE_PLATE_EMBED": EYE_LID_CLOSURE_PLATE_EMBED,
        "EYE_LID_CLOSURE_BACKING_THICKNESS": (
            EYE_LID_CLOSURE_BACKING_THICKNESS
        ),
        "EYE_LID_CLOSURE_BACKING_SIDE_OVERLAP": (
            EYE_LID_CLOSURE_BACKING_SIDE_OVERLAP
        ),
        "EYE_BEZEL_WIDTH": EYE_BEZEL_WIDTH,
        "EYE_BEZEL_HEIGHT": EYE_BEZEL_HEIGHT,
        "EYE_FACE_RECESS_MAX_DEPTH": EYE_FACE_RECESS_MAX_DEPTH,
        "EYE_FACE_RECESS_OUTER_FLARE_MAX_PER_SIDE": (
            EYE_FACE_RECESS_OUTER_FLARE_MAX_PER_SIDE
        ),
        "VISOR_BACK_WIDTH": VISOR_BACK_WIDTH,
        "VISOR_FRONT_WIDTH": VISOR_FRONT_WIDTH,
        "CAMERA_BODY_ONLY_WIDTH": CAMERA_BODY_ONLY_WIDTH,
        "CAMERA_BODY_ONLY_DEPTH": CAMERA_BODY_ONLY_DEPTH,
        "CAMERA_BODY_ONLY_HEIGHT": CAMERA_BODY_ONLY_HEIGHT,
        "CAMERA_BODY_WIDTH": CAMERA_BODY_WIDTH,
        "CAMERA_BODY_DEPTH": CAMERA_BODY_DEPTH,
        "CAMERA_BODY_HEIGHT": CAMERA_BODY_HEIGHT,
        "CAMERA_MIN_FLOOR_AIR_GAP": CAMERA_MIN_FLOOR_AIR_GAP,
        "CAMERA_FORWARD_SOLVE_STEPS": CAMERA_FORWARD_SOLVE_STEPS,
        "CAMERA_SUPPORT_PAD_RADIAL_LENGTH": CAMERA_SUPPORT_PAD_RADIAL_LENGTH,
        "CAMERA_SUPPORT_PAD_TANGENTIAL_WIDTH": (
            CAMERA_SUPPORT_PAD_TANGENTIAL_WIDTH
        ),
        "CAMERA_SUPPORT_PAD_TANGENTIAL_SPACING": (
            CAMERA_SUPPORT_PAD_TANGENTIAL_SPACING
        ),
        "CAMERA_SUPPORT_PAD_MIN_GAP": CAMERA_SUPPORT_PAD_MIN_GAP,
        "CAMERA_CRADLE_SIDE_GUIDE_HEIGHT": CAMERA_CRADLE_SIDE_GUIDE_HEIGHT,
        "CAMERA_CRADLE_SIDE_GUIDE_THICKNESS": (
            CAMERA_CRADLE_SIDE_GUIDE_THICKNESS
        ),
        "CAMERA_CRADLE_SIDE_GUIDE_RADIAL_LENGTH": (
            CAMERA_CRADLE_SIDE_GUIDE_RADIAL_LENGTH
        ),
        "CAMERA_CRADLE_SIDE_GUIDE_MIN_RESOLVED_HEIGHT": (
            CAMERA_CRADLE_SIDE_GUIDE_MIN_RESOLVED_HEIGHT
        ),
        "CAMERA_CRADLE_REAR_GUIDE_HEIGHT": CAMERA_CRADLE_REAR_GUIDE_HEIGHT,
        "CAMERA_CRADLE_REAR_GUIDE_THICKNESS": (
            CAMERA_CRADLE_REAR_GUIDE_THICKNESS
        ),
        "CAMERA_CRADLE_REAR_GUIDE_TANGENTIAL_WIDTH": (
            CAMERA_CRADLE_REAR_GUIDE_TANGENTIAL_WIDTH
        ),
        "CAMERA_CRADLE_REAR_GUIDE_CENTER_AIR_GAP": (
            CAMERA_CRADLE_REAR_GUIDE_CENTER_AIR_GAP
        ),
        "CAMERA_CRADLE_REAR_GUIDE_MIN_SEGMENT_WIDTH": (
            CAMERA_CRADLE_REAR_GUIDE_MIN_SEGMENT_WIDTH
        ),
        "CAMERA_CRADLE_GUIDE_EDGE_RADIUS": CAMERA_CRADLE_GUIDE_EDGE_RADIUS,
        "CAMERA_USB_PORT_RADIAL_WIDTH": CAMERA_USB_PORT_RADIAL_WIDTH,
        "CAMERA_USB_PORT_HEIGHT": CAMERA_USB_PORT_HEIGHT,
        "CAMERA_USB_PORT_CENTER_ABOVE_BODY_BOTTOM": (
            CAMERA_USB_PORT_CENTER_ABOVE_BODY_BOTTOM
        ),
        "CAMERA_USB_PLUG_OUTWARD_DEPTH": CAMERA_USB_PLUG_OUTWARD_DEPTH,
        "CAMERA_USB_PLUG_BODY_OVERLAP": CAMERA_USB_PLUG_BODY_OVERLAP,
        "CAMERA_USB_ACCESS_OTHER_CAMERA_CLEARANCE": (
            CAMERA_USB_ACCESS_OTHER_CAMERA_CLEARANCE
        ),
        "CAMERA_USB_ACCESS_INTERSECTION_VOLUME_TOLERANCE": (
            CAMERA_USB_ACCESS_INTERSECTION_VOLUME_TOLERANCE
        ),
        "CAMERA_FRONT_STOP_PROJECTION": CAMERA_FRONT_STOP_PROJECTION,
        "CAMERA_FRONT_STOP_SIDE_WIDTH": CAMERA_FRONT_STOP_SIDE_WIDTH,
        "CAMERA_FRONT_STOP_SIDE_HEIGHT": CAMERA_FRONT_STOP_SIDE_HEIGHT,
        "CAMERA_FRONT_STOP_RIM_WIDTH": CAMERA_FRONT_STOP_RIM_WIDTH,
        "CAMERA_FRONT_STOP_RIM_HEIGHT": CAMERA_FRONT_STOP_RIM_HEIGHT,
        "CAMERA_FRONT_STOP_CONTACT_TOLERANCE": (
            CAMERA_FRONT_STOP_CONTACT_TOLERANCE
        ),
        "CAMERA_BRACKET_THICKNESS": CAMERA_BRACKET_THICKNESS,
        "CAMERA_BRACKET_CONTACT_RAIL_WIDTH": (
            CAMERA_BRACKET_CONTACT_RAIL_WIDTH
        ),
        "CAMERA_BRACKET_CONTACT_RAIL_EDGE_INSET": (
            CAMERA_BRACKET_CONTACT_RAIL_EDGE_INSET
        ),
        "CAMERA_BRACKET_CONTACT_RAIL_RADIAL_LENGTH": (
            CAMERA_BRACKET_CONTACT_RAIL_RADIAL_LENGTH
        ),
        "CAMERA_BRACKET_COMPACT_REAR_LIP_WIDTH": (
            CAMERA_BRACKET_COMPACT_REAR_LIP_WIDTH
        ),
        "CAMERA_BRACKET_COMPACT_POST_TANGENTIAL_SPACING": (
            CAMERA_BRACKET_COMPACT_POST_TANGENTIAL_SPACING
        ),
        "CAMERA_BRACKET_OVER_CAMERA_DEPTH": (
            CAMERA_BRACKET_OVER_CAMERA_DEPTH
        ),
        "CAMERA_BRACKET_REAR_LIP_HEIGHT": CAMERA_BRACKET_REAR_LIP_HEIGHT,
        "CAMERA_BRACKET_REAR_LIP_THICKNESS": (
            CAMERA_BRACKET_REAR_LIP_THICKNESS
        ),
        "CAMERA_BRACKET_REAR_LIP_WIDTH": CAMERA_BRACKET_REAR_LIP_WIDTH,
        "CAMERA_BRACKET_REAR_LIP_CENTER_AIR_GAP": (
            CAMERA_BRACKET_REAR_LIP_CENTER_AIR_GAP
        ),
        "CAMERA_BRACKET_REAR_LIP_MIN_SEGMENT_WIDTH": (
            CAMERA_BRACKET_REAR_LIP_MIN_SEGMENT_WIDTH
        ),
        "CAMERA_BRACKET_L_CORNER_RETURN_INBOARD_LENGTH": (
            CAMERA_BRACKET_L_CORNER_RETURN_INBOARD_LENGTH
        ),
        "CAMERA_BRACKET_GUIDE_PLATE_OVERHANG": (
            CAMERA_BRACKET_GUIDE_PLATE_OVERHANG
        ),
        "CAMERA_BRACKET_LID_POST_CLEARANCE": (
            CAMERA_BRACKET_LID_POST_CLEARANCE
        ),
        "CAMERA_BRACKET_LID_LIP_RELIEF_CLEARANCE": (
            CAMERA_BRACKET_LID_LIP_RELIEF_CLEARANCE
        ),
        "CAMERA_BRACKET_POST_TANGENTIAL_SPACING": (
            CAMERA_BRACKET_POST_TANGENTIAL_SPACING
        ),
        "CAMERA_INSTALLATION_REARWARD_TRAVEL": (
            CAMERA_INSTALLATION_REARWARD_TRAVEL
        ),
        "CAMERA_INSTALLATION_LENS_RETRACTION_CLEARANCE": (
            CAMERA_INSTALLATION_LENS_RETRACTION_CLEARANCE
        ),
        "CAMERA_INSTALLATION_POST_CLEARANCE": (
            CAMERA_INSTALLATION_POST_CLEARANCE
        ),
        "CAMERA_INSTALLATION_PATH_STEPS": CAMERA_INSTALLATION_PATH_STEPS,
        "CAMERA_TOP_LOADING_LIFT": CAMERA_TOP_LOADING_LIFT,
        "CAMERA_INSTALLATION_INTERSECTION_VOLUME_TOLERANCE": (
            CAMERA_INSTALLATION_INTERSECTION_VOLUME_TOLERANCE
        ),
        "CAMERA_BRACKET_POST_SEARCH_STEP": CAMERA_BRACKET_POST_SEARCH_STEP,
        "CAMERA_BRACKET_POST_BASE_DIAMETER": (
            CAMERA_BRACKET_POST_BASE_DIAMETER
        ),
        "CAMERA_BRACKET_PRIMARY_REAR_OVERLAP": (
            CAMERA_BRACKET_PRIMARY_REAR_OVERLAP
        ),
        "CAMERA_BRACKET_PRIMARY_TANGENTIAL_MARGIN": (
            CAMERA_BRACKET_PRIMARY_TANGENTIAL_MARGIN
        ),
        "CAMERA_BRACKET_ARM_WIDTH": CAMERA_BRACKET_ARM_WIDTH,
        "CAMERA_BRACKET_ARM_PLATE_EMBED": CAMERA_BRACKET_ARM_PLATE_EMBED,
        "CAMERA_BRACKET_ARM_PLATE_OVERLAP": (
            CAMERA_BRACKET_ARM_PLATE_OVERLAP
        ),
        "CAMERA_BRACKET_ARM_COUNTERBORE_MIN_WEB": (
            CAMERA_BRACKET_ARM_COUNTERBORE_MIN_WEB
        ),
        "CAMERA_BRACKET_BOSS_EDGE_MARGIN": (
            CAMERA_BRACKET_BOSS_EDGE_MARGIN
        ),
        "CAMERA_BRACKET_BOSS_POST_EDGE_MARGIN": (
            CAMERA_BRACKET_BOSS_POST_EDGE_MARGIN
        ),
        "CAMERA_BRACKET_USB_SIDE_LOCATOR_HEIGHT": (
            CAMERA_BRACKET_USB_SIDE_LOCATOR_HEIGHT
        ),
        "CAMERA_BRACKET_USB_SIDE_LOCATOR_THICKNESS": (
            CAMERA_BRACKET_USB_SIDE_LOCATOR_THICKNESS
        ),
        "CAMERA_BRACKET_USB_SIDE_LOCATOR_RADIAL_LENGTH": (
            CAMERA_BRACKET_USB_SIDE_LOCATOR_RADIAL_LENGTH
        ),
        "CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_HEIGHT": (
            CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_HEIGHT
        ),
        "CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_THICKNESS": (
            CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_THICKNESS
        ),
        "CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_RADIAL_LENGTH": (
            CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_RADIAL_LENGTH
        ),
        "CAMERA_BRACKET_SIDE_LOCATOR_GUSSET_REACH": (
            CAMERA_BRACKET_SIDE_LOCATOR_GUSSET_REACH
        ),
        "CAMERA_BRACKET_SIDE_LOCATOR_GUSSET_DEPTH": (
            CAMERA_BRACKET_SIDE_LOCATOR_GUSSET_DEPTH
        ),
        "CAMERA_BRACKET_SIDE_LOCATOR_GUSSET_ROOT_EMBED": (
            CAMERA_BRACKET_SIDE_LOCATOR_GUSSET_ROOT_EMBED
        ),
        "CAMERA_BRACKET_SIDE_LOCATOR_PLATE_EMBED": (
            CAMERA_BRACKET_SIDE_LOCATOR_PLATE_EMBED
        ),
        "FASTENER_POST_DIAMETER": FASTENER_POST_DIAMETER,
        "HEAT_INSERT_HOLE_DIAMETER": HEAT_INSERT_HOLE_DIAMETER,
        "HEAT_INSERT_HOLE_DEPTH": HEAT_INSERT_HOLE_DEPTH,
        "LID_SCREW_CLEARANCE_DIAMETER": LID_SCREW_CLEARANCE_DIAMETER,
        "LID_SCREW_HEAD_COUNTERBORE_DIAMETER": (
            LID_SCREW_HEAD_COUNTERBORE_DIAMETER
        ),
        "LID_SCREW_HEAD_COUNTERBORE_DEPTH": LID_SCREW_HEAD_COUNTERBORE_DEPTH,
        "CAMERA_BRACKET_MIN_COUNTERBORE_FLOOR": (
            CAMERA_BRACKET_MIN_COUNTERBORE_FLOOR
        ),
        "CAMERA_BRACKET_MIN_PRELOAD_CONTACT_VOLUME": (
            CAMERA_BRACKET_MIN_PRELOAD_CONTACT_VOLUME
        ),
        "CAMERA_CARRIER_TRAY_THICKNESS": CAMERA_CARRIER_TRAY_THICKNESS,
        "CAMERA_CARRIER_TRAY_FRAME_WIDTH": CAMERA_CARRIER_TRAY_FRAME_WIDTH,
        "CAMERA_CARRIER_SUPPORT_RAIL_WIDTH": (
            CAMERA_CARRIER_SUPPORT_RAIL_WIDTH
        ),
        "CAMERA_CARRIER_FIT_PROBE_LIFT": CAMERA_CARRIER_FIT_PROBE_LIFT,
        "CAMERA_CARRIER_GUIDE_HEIGHT": CAMERA_CARRIER_GUIDE_HEIGHT,
        "CAMERA_CARRIER_GUIDE_THICKNESS": CAMERA_CARRIER_GUIDE_THICKNESS,
        "CAMERA_CARRIER_GUIDE_TRAY_EMBED": (
            CAMERA_CARRIER_GUIDE_TRAY_EMBED
        ),
        "CAMERA_CARRIER_FRONT_STOP_ROOT_LENGTH": (
            CAMERA_CARRIER_FRONT_STOP_ROOT_LENGTH
        ),
        "CAMERA_CARRIER_FRONT_STOP_ROOT_RAIL_WIDTH": (
            CAMERA_CARRIER_FRONT_STOP_ROOT_RAIL_WIDTH
        ),
        "CAMERA_CARRIER_TOP_LOADING_CHIMNEY_CLEARANCE": (
            CAMERA_CARRIER_TOP_LOADING_CHIMNEY_CLEARANCE
        ),
        "CAMERA_CARRIER_CHIMNEY_MAX_FRAGMENT_FACES": (
            CAMERA_CARRIER_CHIMNEY_MAX_FRAGMENT_FACES
        ),
        "CAMERA_CARRIER_MAX_FRAGMENT_FACES": (
            CAMERA_CARRIER_MAX_FRAGMENT_FACES
        ),
        "CAMERA_CARRIER_MAX_FRAGMENT_VOLUME": (
            CAMERA_CARRIER_MAX_FRAGMENT_VOLUME
        ),
        "CAMERA_CARRIER_MAX_FRAGMENT_EXTENT": (
            CAMERA_CARRIER_MAX_FRAGMENT_EXTENT
        ),
        "CAMERA_CARRIER_CHIMNEY_MAX_FRAGMENT_VOLUME": (
            CAMERA_CARRIER_CHIMNEY_MAX_FRAGMENT_VOLUME
        ),
        "CAMERA_CARRIER_CHIMNEY_MAX_FRAGMENT_EXTENT": (
            CAMERA_CARRIER_CHIMNEY_MAX_FRAGMENT_EXTENT
        ),
        "CAMERA_CARRIER_SIDE_GUIDE_END_LENGTH": (
            CAMERA_CARRIER_SIDE_GUIDE_END_LENGTH
        ),
        "CAMERA_CARRIER_USB_GUIDE_MIN_SEGMENT_LENGTH": (
            CAMERA_CARRIER_USB_GUIDE_MIN_SEGMENT_LENGTH
        ),
        "CAMERA_CARRIER_MIN_SIDE_AIR_CHANNEL": (
            CAMERA_CARRIER_MIN_SIDE_AIR_CHANNEL
        ),
        "CAMERA_CARRIER_REAR_CORNER_OVERLAP": (
            CAMERA_CARRIER_REAR_CORNER_OVERLAP
        ),
        "CAMERA_CARRIER_PIVOT_PIN_DIAMETER": (
            CAMERA_CARRIER_PIVOT_PIN_DIAMETER
        ),
        "CAMERA_CARRIER_PIVOT_PIN_HEIGHT": CAMERA_CARRIER_PIVOT_PIN_HEIGHT,
        "CAMERA_CARRIER_MIN_PIVOT_ENGAGEMENT": (
            CAMERA_CARRIER_MIN_PIVOT_ENGAGEMENT
        ),
        "CAMERA_CARRIER_THRUST_PAD_DIAMETER": (
            CAMERA_CARRIER_THRUST_PAD_DIAMETER
        ),
        "CAMERA_CARRIER_THRUST_WASHER_OD": CAMERA_CARRIER_THRUST_WASHER_OD,
        "CAMERA_CARRIER_THRUST_WASHER_ID": CAMERA_CARRIER_THRUST_WASHER_ID,
        "CAMERA_CARRIER_THRUST_WASHER_THICKNESS": (
            CAMERA_CARRIER_THRUST_WASHER_THICKNESS
        ),
        "CAMERA_CARRIER_REAR_GUIDE_TOTAL_WIDTH": (
            CAMERA_CARRIER_REAR_GUIDE_TOTAL_WIDTH
        ),
        "CAMERA_CARRIER_REAR_GUIDE_CENTER_AIR_GAP": (
            CAMERA_CARRIER_REAR_GUIDE_CENTER_AIR_GAP
        ),
        "CAMERA_CARRIER_REAR_GUIDE_MIN_SEGMENT_WIDTH": (
            CAMERA_CARRIER_REAR_GUIDE_MIN_SEGMENT_WIDTH
        ),
        "CAMERA_GEAR_MODULE": CAMERA_GEAR_MODULE,
        "CAMERA_GEAR_FACE_WIDTH": CAMERA_GEAR_FACE_WIDTH,
        "CAMERA_GEAR_MIN_RADIAL_ENGAGEMENT": (
            CAMERA_GEAR_MIN_RADIAL_ENGAGEMENT
        ),
        "CAMERA_WORM_LENGTH": CAMERA_WORM_LENGTH,
        "CAMERA_WORM_SHAFT_DIAMETER": CAMERA_WORM_SHAFT_DIAMETER,
        "CAMERA_WORM_BEARING_OD": CAMERA_WORM_BEARING_OD,
        "CAMERA_WORM_BEARING_WIDTH": CAMERA_WORM_BEARING_WIDTH,
        "CAMERA_WORM_BLOCK_LENGTH": CAMERA_WORM_BLOCK_LENGTH,
        "CAMERA_WORM_BLOCK_WIDTH": CAMERA_WORM_BLOCK_WIDTH,
        "CAMERA_WORM_BLOCK_OFFSET": CAMERA_WORM_BLOCK_OFFSET,
        "CAMERA_WORM_THRUST_WASHER_THICKNESS": (
            CAMERA_WORM_THRUST_WASHER_THICKNESS
        ),
        "CAMERA_WORM_AXIAL_RUNNING_CLEARANCE": (
            CAMERA_WORM_AXIAL_RUNNING_CLEARANCE
        ),
        "CAMERA_WORM_PORT_BOSS_RADIUS": CAMERA_WORM_PORT_BOSS_RADIUS,
        "CAMERA_WORM_MAX_INPUT_TORQUE_NMM": (
            CAMERA_WORM_MAX_INPUT_TORQUE_NMM
        ),
        "CAMERA_HARD_STOP_PIN_DIAMETER": CAMERA_HARD_STOP_PIN_DIAMETER,
        "CAMERA_HOLD_DOWN_PAD_DIAMETER": CAMERA_HOLD_DOWN_PAD_DIAMETER,
        "CAMERA_HOLD_DOWN_PAD_MATERIAL_THICKNESS": (
            CAMERA_HOLD_DOWN_PAD_MATERIAL_THICKNESS
        ),
        "CAMERA_HOLD_DOWN_CENTER_PLATE_DIAMETER": (
            CAMERA_HOLD_DOWN_CENTER_PLATE_DIAMETER
        ),
        "CAMERA_BRACKET_REAR_CONTACT_VOLUME_TOLERANCE": (
            CAMERA_BRACKET_REAR_CONTACT_VOLUME_TOLERANCE
        ),
        "CAMERA_BASE_CONTACT_VOLUME_TOLERANCE": (
            CAMERA_BASE_CONTACT_VOLUME_TOLERANCE
        ),
        "ASSEMBLY_COPLANAR_CONTACT_TOLERANCE": (
            ASSEMBLY_COPLANAR_CONTACT_TOLERANCE
        ),
        "CAMERA_COOLING_MIN_EXHAUST_TO_FAN_AREA_RATIO": (
            CAMERA_COOLING_MIN_EXHAUST_TO_FAN_AREA_RATIO
        ),
        "CAMERA_COOLING_MIN_EYE_EDGE_GAP": (
            CAMERA_COOLING_MIN_EYE_EDGE_GAP
        ),
        "REAR_FAN_PAD_SIZE": REAR_FAN_PAD_SIZE,
        "REAR_FAN_PAD_SURFACE_SAMPLES": REAR_FAN_PAD_SURFACE_SAMPLES,
        "REAR_FAN_WALL_ANGLE_SAMPLE_DISTANCE": (
            REAR_FAN_WALL_ANGLE_SAMPLE_DISTANCE
        ),
        "REAR_FAN_MOUNT_SPACING": REAR_FAN_MOUNT_SPACING,
        "REAR_FAN_MOUNT_HOLE_DIAMETER": REAR_FAN_MOUNT_HOLE_DIAMETER,
        "REAR_FAN_AIR_OPENING_DIAMETER": REAR_FAN_AIR_OPENING_DIAMETER,
        "REAR_FAN_DEPTH": REAR_FAN_DEPTH,
        "REAR_FAN_HUB_DIAMETER": REAR_FAN_HUB_DIAMETER,
        "REAR_FAN_CUTTER_INWARD_EXTENSION": (
            REAR_FAN_CUTTER_INWARD_EXTENSION
        ),
        "REAR_FAN_MIN_WEB": REAR_FAN_MIN_WEB,
        "BOTTOM_MOUNT_HOLE_DIAMETER": BOTTOM_MOUNT_HOLE_DIAMETER,
        "BOTTOM_MOUNT_HOLE_EDGE_CLEARANCE": (
            BOTTOM_MOUNT_HOLE_EDGE_CLEARANCE
        ),
        "BOTTOM_MOUNT_HOLE_KEEP_OUT_CLEARANCE": (
            BOTTOM_MOUNT_HOLE_KEEP_OUT_CLEARANCE
        ),
        "BOTTOM_MOUNT_HOLE_SEARCH_RANGE": BOTTOM_MOUNT_HOLE_SEARCH_RANGE,
        "BOTTOM_MOUNT_HOLE_SEARCH_STEP": BOTTOM_MOUNT_HOLE_SEARCH_STEP,
        "BOTTOM_MOUNT_HOLE_FRACTION_SEARCH_RANGE": (
            BOTTOM_MOUNT_HOLE_FRACTION_SEARCH_RANGE
        ),
        "BOTTOM_MOUNT_HOLE_FRACTION_SEARCH_STEP": (
            BOTTOM_MOUNT_HOLE_FRACTION_SEARCH_STEP
        ),
        "BOTTOM_MOUNT_NUT_THREAD_DIAMETER": BOTTOM_MOUNT_NUT_THREAD_DIAMETER,
        "BOTTOM_MOUNT_NUT_ACROSS_FLATS": BOTTOM_MOUNT_NUT_ACROSS_FLATS,
        "BOTTOM_MOUNT_NUT_THICKNESS": BOTTOM_MOUNT_NUT_THICKNESS,
        "BOTTOM_MOUNT_NUT_HOLDER_OUTER_DIAMETER": (
            BOTTOM_MOUNT_NUT_HOLDER_OUTER_DIAMETER
        ),
        "BOTTOM_MOUNT_NUT_HOLDER_MIN_WALL": (
            BOTTOM_MOUNT_NUT_HOLDER_MIN_WALL
        ),
        "BOTTOM_MOUNT_NUT_MIN_SEAT_WIDTH": BOTTOM_MOUNT_NUT_MIN_SEAT_WIDTH,
        "BOTTOM_MOUNT_NUT_THICKNESS_TOLERANCE": (
            BOTTOM_MOUNT_NUT_THICKNESS_TOLERANCE
        ),
        "BOTTOM_MOUNT_NUT_SNAP_LIP_RETENTION_CLEARANCE": (
            BOTTOM_MOUNT_NUT_SNAP_LIP_RETENTION_CLEARANCE
        ),
        "BOTTOM_MOUNT_NUT_SNAP_LIP_HEIGHT": (
            BOTTOM_MOUNT_NUT_SNAP_LIP_HEIGHT
        ),
        "BOTTOM_MOUNT_NUT_SNAP_LIP_PROJECTION": (
            BOTTOM_MOUNT_NUT_SNAP_LIP_PROJECTION
        ),
        "BOTTOM_MOUNT_NUT_SNAP_LIP_WIDTH": BOTTOM_MOUNT_NUT_SNAP_LIP_WIDTH,
        "BOTTOM_MOUNT_NUT_SNAP_ROOT_EMBED": BOTTOM_MOUNT_NUT_SNAP_ROOT_EMBED,
        "BOTTOM_MOUNT_NUT_SNAP_FLEX_WALL_THICKNESS": (
            BOTTOM_MOUNT_NUT_SNAP_FLEX_WALL_THICKNESS
        ),
        "BOTTOM_MOUNT_NUT_SNAP_RELIEF_DEPTH": (
            BOTTOM_MOUNT_NUT_SNAP_RELIEF_DEPTH
        ),
        "BOTTOM_MOUNT_NUT_SNAP_SIDE_SLOT_WIDTH": (
            BOTTOM_MOUNT_NUT_SNAP_SIDE_SLOT_WIDTH
        ),
        "BOTTOM_MOUNT_NUT_SNAP_FLEX_HEIGHT": (
            BOTTOM_MOUNT_NUT_SNAP_FLEX_HEIGHT
        ),
        "BOTTOM_KEYSTONE_CUTOUT_X": BOTTOM_KEYSTONE_CUTOUT_X,
        "BOTTOM_KEYSTONE_CUTOUT_Y": BOTTOM_KEYSTONE_CUTOUT_Y,
        "BOTTOM_KEYSTONE_FACE_POCKET_X": BOTTOM_KEYSTONE_FACE_POCKET_X,
        "BOTTOM_KEYSTONE_FACE_POCKET_Y": BOTTOM_KEYSTONE_FACE_POCKET_Y,
        "BOTTOM_KEYSTONE_FACE_RECESS_DEPTH": (
            BOTTOM_KEYSTONE_FACE_RECESS_DEPTH
        ),
        "BOTTOM_KEYSTONE_INTERNAL_BODY_X": BOTTOM_KEYSTONE_INTERNAL_BODY_X,
        "BOTTOM_KEYSTONE_INTERNAL_BODY_Y": BOTTOM_KEYSTONE_INTERNAL_BODY_Y,
        "BOTTOM_KEYSTONE_INTERNAL_BODY_HEIGHT": (
            BOTTOM_KEYSTONE_INTERNAL_BODY_HEIGHT
        ),
        "BOTTOM_KEYSTONE_CENTER_SPACING": BOTTOM_KEYSTONE_CENTER_SPACING,
        "BOTTOM_KEYSTONE_SEARCH_RANGE": BOTTOM_KEYSTONE_SEARCH_RANGE,
        "BOTTOM_KEYSTONE_SEARCH_STEP": BOTTOM_KEYSTONE_SEARCH_STEP,
        "BOTTOM_KEYSTONE_REFERENCE_DIMENSION_TOLERANCE": (
            BOTTOM_KEYSTONE_REFERENCE_DIMENSION_TOLERANCE
        ),
        "BOTTOM_KEYSTONE_SOCKET_OUTER_X": BOTTOM_KEYSTONE_SOCKET_OUTER_X,
        "BOTTOM_KEYSTONE_SOCKET_OUTER_Y": BOTTOM_KEYSTONE_SOCKET_OUTER_Y,
        "BOTTOM_KEYSTONE_SOCKET_HEIGHT": BOTTOM_KEYSTONE_SOCKET_HEIGHT,
        "BOTTOM_KEYSTONE_SOCKET_INNER_CLEAR_X": (
            BOTTOM_KEYSTONE_SOCKET_INNER_CLEAR_X
        ),
        "BOTTOM_KEYSTONE_SOCKET_INNER_CLEAR_Y": (
            BOTTOM_KEYSTONE_SOCKET_INNER_CLEAR_Y
        ),
    }
    for name, value in positive.items():
        if value <= 0.0:
            raise ValueError(f"{name} must be positive")
    if not 0.0 <= FOOTPRINT_TRIANGULARITY < 0.85:
        raise ValueError("FOOTPRINT_TRIANGULARITY must be between 0 and 0.85")
    if FOOTPRINT_POINTS < 32 or FOOTPRINT_POINTS % 4:
        raise ValueError("FOOTPRINT_POINTS must be a multiple of four and at least 32")
    if tuple(z for z, _ in BODY_SECTIONS) != tuple(
        sorted(z for z, _ in BODY_SECTIONS)
    ):
        raise ValueError("BODY_SECTIONS must be ordered by increasing Z")
    if BODY_SECTIONS[0][0] != 0.0 or BODY_SECTIONS[-1][0] != BASE_HEIGHT:
        raise ValueError("BODY_SECTIONS must span Z=0 through BASE_HEIGHT")
    if abs(BASE_HEIGHT + LID_THICKNESS - BODY_HEIGHT) > 1e-6:
        raise ValueError("BASE_HEIGHT + LID_THICKNESS must equal BODY_HEIGHT")
    if not 0.0 < BOTTOM_THICKNESS < BASE_HEIGHT:
        raise ValueError("BOTTOM_THICKNESS must fit below the base opening")
    if FASTENER_POST_PLACEMENT not in {"auto", "manual"}:
        raise ValueError('FASTENER_POST_PLACEMENT must be "auto" or "manual"')
    if HEAT_INSERT_HOLE_DIAMETER >= FASTENER_POST_DIAMETER:
        raise ValueError("Heat-insert hole must fit inside the fastener post")
    if LID_SCREW_HEAD_COUNTERBORE_DIAMETER <= LID_SCREW_CLEARANCE_DIAMETER:
        raise ValueError("Socket-head counterbore must exceed shank clearance")
    if LID_SCREW_HEAD_COUNTERBORE_DEPTH >= LID_THICKNESS:
        raise ValueError("Counterbore depth must leave material in the lid")
    if len(FASTENER_POST_TARGETS_XY) != 4:
        raise ValueError("Exactly four fastener post targets are required")
    if len(MANUAL_FASTENER_POST_POSITIONS_XY) != 4:
        raise ValueError("Exactly four manual fastener positions are required")
    camera_vertical = mission1.canonical_vertical_bounds(CAMERA_UPSIDE_DOWN)
    eye_center_z = camera_eye_center_z()
    camera_bottom = eye_center_z + camera_vertical[0]
    camera_top = eye_center_z + camera_vertical[1]
    expected_camera_bottom = BOTTOM_THICKNESS + CAMERA_FLOOR_CLEARANCE
    if abs(camera_bottom - expected_camera_bottom) > 1e-6:
        raise ValueError(
            "EYE_CENTER_Z override must put the camera bottom exactly at "
            "BOTTOM_THICKNESS + CAMERA_FLOOR_CLEARANCE"
        )
    if CAMERA_CRADLES_ENABLED and camera_bottom <= BOTTOM_THICKNESS:
        raise ValueError("Camera support pads require positive floor clearance")
    if CAMERA_FLOOR_CLEARANCE < CAMERA_MIN_FLOOR_AIR_GAP:
        raise ValueError(
            "CAMERA_FLOOR_CLEARANCE must preserve the minimum cooling-air gap"
        )
    if not CAMERA_CRADLES_ENABLED and camera_bottom > BOTTOM_THICKNESS + 1e-6:
        raise ValueError("Camera would float above the floor with cradles disabled")
    if camera_top >= BASE_HEIGHT:
        raise ValueError("Camera envelope is too tall for the closed base")
    nonnegative = {
        "CAMERA_FLOOR_CLEARANCE": CAMERA_FLOOR_CLEARANCE,
        "CAMERA_BODY_MUTUAL_CLEARANCE": CAMERA_BODY_MUTUAL_CLEARANCE,
        "CAMERA_LENS_FACE_MIN_OUTSET": CAMERA_LENS_FACE_MIN_OUTSET,
        "CAMERA_LENS_OPENING_CLEARANCE": CAMERA_LENS_OPENING_CLEARANCE,
        "CAMERA_LENS_HOUSING_OTHER_EYE_CLEARANCE": (
            CAMERA_LENS_HOUSING_OTHER_EYE_CLEARANCE
        ),
        "CAMERA_OPPOSITE_EYE_SURROUND_CLEARANCE": (
            CAMERA_OPPOSITE_EYE_SURROUND_CLEARANCE
        ),
        "CAMERA_LENS_MIN_SWEEP_EYE_FACE_PROTRUSION": (
            CAMERA_LENS_MIN_SWEEP_EYE_FACE_PROTRUSION
        ),
        "CAMERA_FORWARD_SOLVE_SAFETY_MARGIN": (
            CAMERA_FORWARD_SOLVE_SAFETY_MARGIN
        ),
        "CAMERA_CRADLE_SIDE_CLEARANCE": CAMERA_CRADLE_SIDE_CLEARANCE,
        "CAMERA_CRADLE_SIDE_GUIDE_FRONT_INSET": (
            CAMERA_CRADLE_SIDE_GUIDE_FRONT_INSET
        ),
        "CAMERA_CRADLE_SIDE_GUIDE_LENS_PATH_CLEARANCE": (
            CAMERA_CRADLE_SIDE_GUIDE_LENS_PATH_CLEARANCE
        ),
        "CAMERA_CRADLE_REAR_CLEARANCE": CAMERA_CRADLE_REAR_CLEARANCE,
        "CAMERA_BRACKET_SHELL_EXPANSION": CAMERA_BRACKET_SHELL_EXPANSION,
        "CAMERA_BRACKET_SHELL_EXPANSION_WITH_CARTRIDGE": (
            CAMERA_BRACKET_SHELL_EXPANSION_WITH_CARTRIDGE
        ),
        "CAMERA_CARRIER_BOTTOM_CLEARANCE": CAMERA_CARRIER_BOTTOM_CLEARANCE,
        "CAMERA_CARTRIDGE_SHELL_EXPANSION": (
            CAMERA_CARTRIDGE_SHELL_EXPANSION
        ),
        "CAMERA_CARRIER_CAVITY_NUMERICAL_TOLERANCE": (
            CAMERA_CARRIER_CAVITY_NUMERICAL_TOLERANCE
        ),
        "CAMERA_CARRIER_TRAY_RADIAL_MARGIN": (
            CAMERA_CARRIER_TRAY_RADIAL_MARGIN
        ),
        "CAMERA_CARRIER_TRAY_TANGENTIAL_MARGIN": (
            CAMERA_CARRIER_TRAY_TANGENTIAL_MARGIN
        ),
        "CAMERA_CARRIER_CAMERA_CLEARANCE": CAMERA_CARRIER_CAMERA_CLEARANCE,
        "CAMERA_CARRIER_SWEEP_CUT_CLEARANCE": (
            CAMERA_CARRIER_SWEEP_CUT_CLEARANCE
        ),
        "CAMERA_CARRIER_PIVOT_CLEARANCE": CAMERA_CARRIER_PIVOT_CLEARANCE,
        "CAMERA_CARRIER_THRUST_PAD_HEIGHT": (
            CAMERA_CARRIER_THRUST_PAD_HEIGHT
        ),
        "CAMERA_CARRIER_THRUST_RUNNING_CLEARANCE": (
            CAMERA_CARRIER_THRUST_RUNNING_CLEARANCE
        ),
        "CAMERA_GEAR_BACKLASH": CAMERA_GEAR_BACKLASH,
        "CAMERA_GEAR_MESH_CENTER_CLEARANCE": (
            CAMERA_GEAR_MESH_CENTER_CLEARANCE
        ),
        "CAMERA_WORM_SHAFT_CLEARANCE": CAMERA_WORM_SHAFT_CLEARANCE,
        "CAMERA_WORM_BEARING_POCKET_DEPTH_CLEARANCE": (
            CAMERA_WORM_BEARING_POCKET_DEPTH_CLEARANCE
        ),
        "CAMERA_WORM_FLOOR_CLEARANCE": CAMERA_WORM_FLOOR_CLEARANCE,
        "CAMERA_WORM_BLOCK_TOP_CLEARANCE": CAMERA_WORM_BLOCK_TOP_CLEARANCE,
        "CAMERA_WORM_PORT_OUTSET": CAMERA_WORM_PORT_OUTSET,
        "CAMERA_WORM_PORT_INWARD_EXTENSION": (
            CAMERA_WORM_PORT_INWARD_EXTENSION
        ),
        "CAMERA_HOLD_DOWN_PAD_MATERIAL_CLEARANCE": (
            CAMERA_HOLD_DOWN_PAD_MATERIAL_CLEARANCE
        ),
        "CAMERA_USB_ACCESS_RADIAL_CLEARANCE": (
            CAMERA_USB_ACCESS_RADIAL_CLEARANCE
        ),
        "CAMERA_USB_ACCESS_VERTICAL_CLEARANCE": (
            CAMERA_USB_ACCESS_VERTICAL_CLEARANCE
        ),
        "CAMERA_FRONT_STOP_WALL_LAND": CAMERA_FRONT_STOP_WALL_LAND,
        "CAMERA_FRONT_STOP_EDGE_RADIUS": CAMERA_FRONT_STOP_EDGE_RADIUS,
        "EYE_CUTTER_INWARD_EXTRA": EYE_CUTTER_INWARD_EXTRA,
        "EYE_FACE_RECESS_BORDER_OVERLAP": EYE_FACE_RECESS_BORDER_OVERLAP,
        "EYE_TOP_LOADING_SLOT_BOTTOM_OFFSET_Z": (
            EYE_TOP_LOADING_SLOT_BOTTOM_OFFSET_Z
        ),
        "EYE_LID_CLOSURE_FIT_CLEARANCE": EYE_LID_CLOSURE_FIT_CLEARANCE,
        "EYE_LID_CLOSURE_RADIAL_CLEARANCE": (
            EYE_LID_CLOSURE_RADIAL_CLEARANCE
        ),
        "EYE_LID_CLOSURE_APERTURE_CLEARANCE": (
            EYE_LID_CLOSURE_APERTURE_CLEARANCE
        ),
        "CAMERA_SUPPORT_PAD_EDGE_RADIUS": CAMERA_SUPPORT_PAD_EDGE_RADIUS,
        "CAMERA_SUPPORT_FEATURE_CLEARANCE": CAMERA_SUPPORT_FEATURE_CLEARANCE,
        "BOTTOM_MOUNT_NUT_PRESS_INTERFERENCE": (
            BOTTOM_MOUNT_NUT_PRESS_INTERFERENCE
        ),
        "CAMERA_BRACKET_TOP_FEATURE_CLEARANCE_Z": (
            CAMERA_BRACKET_TOP_FEATURE_CLEARANCE_Z
        ),
        "CAMERA_BRACKET_BODY_CONTACT_CLEARANCE_Z": (
            CAMERA_BRACKET_BODY_CONTACT_CLEARANCE_Z
        ),
        "CAMERA_BRACKET_CLAMP_PRELOAD_Z": CAMERA_BRACKET_CLAMP_PRELOAD_Z,
        "CAMERA_BRACKET_BUTTON_MIN_CLEARANCE_Z": (
            CAMERA_BRACKET_BUTTON_MIN_CLEARANCE_Z
        ),
        "CAMERA_BRACKET_BUTTON_RELIEF_MARGIN": (
            CAMERA_BRACKET_BUTTON_RELIEF_MARGIN
        ),
        "CAMERA_BRACKET_REAR_CLEARANCE": CAMERA_BRACKET_REAR_CLEARANCE,
        "CAMERA_BRACKET_USB_SIDE_LOCATOR_CLEARANCE": (
            CAMERA_BRACKET_USB_SIDE_LOCATOR_CLEARANCE
        ),
        "CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_CLEARANCE": (
            CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_CLEARANCE
        ),
        "CAMERA_BRACKET_OTHER_CAMERA_CLEARANCE": (
            CAMERA_BRACKET_OTHER_CAMERA_CLEARANCE
        ),
        "CAMERA_BRACKET_WALL_CLEARANCE": CAMERA_BRACKET_WALL_CLEARANCE,
        "REAR_FAN_PAD_GAP": REAR_FAN_PAD_GAP,
        "REAR_FAN_PAD_FACE_OUTSET": REAR_FAN_PAD_FACE_OUTSET,
        "REAR_FAN_BODY_CLEARANCE": REAR_FAN_BODY_CLEARANCE,
        "BOTTOM_KEYSTONE_REAR_EDGE_INSET": BOTTOM_KEYSTONE_REAR_EDGE_INSET,
        "BOTTOM_KEYSTONE_SIDE_EDGE_INSET": BOTTOM_KEYSTONE_SIDE_EDGE_INSET,
        "BOTTOM_KEYSTONE_EDGE_CLEARANCE": BOTTOM_KEYSTONE_EDGE_CLEARANCE,
        "BOTTOM_KEYSTONE_KEEP_OUT_CLEARANCE": (
            BOTTOM_KEYSTONE_KEEP_OUT_CLEARANCE
        ),
        "BOTTOM_KEYSTONE_SOCKET_BASE_CLEARANCE": (
            BOTTOM_KEYSTONE_SOCKET_BASE_CLEARANCE
        ),
    }
    for name, value in nonnegative.items():
        if value < 0.0:
            raise ValueError(f"{name} cannot be negative")
    if CAMERA_FORWARD_PLACEMENT_MODE not in {"maximize", "manual"}:
        raise ValueError(
            'CAMERA_FORWARD_PLACEMENT_MODE must be "maximize" or "manual"'
        )
    if (
        CAMERA_FORWARD_PLACEMENT_MODE == "maximize"
        and not CAMERA_FRONT_STOPS_ENABLED
    ):
        raise ValueError("Maximized camera placement requires front stops")
    if not isinstance(CAMERA_FORWARD_SOLVE_STEPS, int) or (
        CAMERA_FORWARD_SOLVE_STEPS < 16
    ):
        raise ValueError("CAMERA_FORWARD_SOLVE_STEPS must be an integer at least 16")
    if CAMERA_FLOOR_CLEARANCE < 0.0 or CAMERA_BODY_MUTUAL_CLEARANCE < 0.0:
        raise ValueError("Camera clearances cannot be negative")
    if not 0.0 <= BOTTOM_MOUNT_HOLE_FRONT_TO_BACK_FRACTION <= 1.0:
        raise ValueError(
            "BOTTOM_MOUNT_HOLE_FRONT_TO_BACK_FRACTION must be between 0 and 1"
        )
    if BOTTOM_MOUNT_HOLE_FRACTION_SEARCH_RANGE > 1.0:
        raise ValueError(
            "BOTTOM_MOUNT_HOLE_FRACTION_SEARCH_RANGE cannot exceed 1"
        )
    if not math.isfinite(float(BOTTOM_MOUNT_NUT_ROTATION_DEG)):
        raise ValueError("BOTTOM_MOUNT_NUT_ROTATION_DEG must be finite")
    if BOTTOM_MOUNT_NUT_HOLDER_UNION_SOLVER not in {
        "FLOAT",
        "EXACT",
        "MANIFOLD",
    }:
        raise ValueError("Unsupported captive-nut holder Boolean solver")
    if BOTTOM_MOUNT_NUT_HOLDER_ENABLED:
        nut_pocket_across_flats = bottom_mount_nut_pocket_across_flats()
        nut_corner_diameter = 2.0 * nut_pocket_across_flats / math.sqrt(3.0)
        if BOTTOM_MOUNT_HOLE_DIAMETER <= BOTTOM_MOUNT_NUT_THREAD_DIAMETER:
            raise ValueError(
                "Bottom mount through-hole must clear the configured nut thread"
            )
        if (
            nut_pocket_across_flats - BOTTOM_MOUNT_HOLE_DIAMETER
        ) / 2.0 < BOTTOM_MOUNT_NUT_MIN_SEAT_WIDTH:
            raise ValueError("Bottom mount nut has insufficient floor seating width")
        if BOTTOM_MOUNT_NUT_HOLDER_OUTER_DIAMETER < (
            nut_corner_diameter + 2.0 * BOTTOM_MOUNT_NUT_HOLDER_MIN_WALL
        ):
            raise ValueError("Bottom mount nut holder wall is too thin")
        if BOTTOM_MOUNT_NUT_SNAP_LIP_PROJECTION >= (
            nut_pocket_across_flats - BOTTOM_MOUNT_HOLE_DIAMETER
        ) / 2.0:
            raise ValueError("Bottom mount snap lips project into the bolt passage")
        hex_face_length = nut_pocket_across_flats / math.sqrt(3.0)
        if BOTTOM_MOUNT_NUT_SNAP_LIP_WIDTH >= hex_face_length:
            raise ValueError("Bottom mount snap lips exceed the nut-pocket faces")
        if BOTTOM_MOUNT_NUT_SNAP_ROOT_EMBED >= (
            BOTTOM_MOUNT_NUT_SNAP_FLEX_WALL_THICKNESS
        ):
            raise ValueError("Bottom mount snap-lip root exceeds its flex wall")
        side_slot_outer_radial = (
            nut_pocket_across_flats / 2.0
            + BOTTOM_MOUNT_NUT_SNAP_FLEX_WALL_THICKNESS
            + BOTTOM_MOUNT_NUT_SNAP_RELIEF_DEPTH
            + BOOLEAN_OVERLAP
        )
        relief_outer_tangential = (
            BOTTOM_MOUNT_NUT_SNAP_LIP_WIDTH / 2.0
            + BOTTOM_MOUNT_NUT_SNAP_SIDE_SLOT_WIDTH
        )
        relief_corner_radius = math.hypot(
            side_slot_outer_radial,
            relief_outer_tangential,
        )
        boss_inradius = (
            BOTTOM_MOUNT_NUT_HOLDER_OUTER_DIAMETER
            / 2.0
            * math.cos(math.pi / 72.0)
        )
        remaining_relief_wall = (
            boss_inradius - relief_corner_radius
        )
        if (
            BOTTOM_MOUNT_NUT_SNAP_RELIEF_ENABLED
            and remaining_relief_wall < BOTTOM_MOUNT_NUT_HOLDER_MIN_WALL
        ):
            raise ValueError("Bottom mount snap relief leaves too little outer wall")
        if bottom_mount_nut_snap_relief_base_z() <= BOTTOM_THICKNESS:
            raise ValueError("Bottom mount snap-flex tongues extend into the floor")
        if bottom_mount_nut_holder_top_z() >= BASE_HEIGHT:
            raise ValueError("Bottom mount nut holder does not fit below the lid")
    if not isinstance(BOTTOM_KEYSTONE_COUNT, int) or BOTTOM_KEYSTONE_COUNT < 1:
        raise ValueError("BOTTOM_KEYSTONE_COUNT must be a positive integer")
    if BOTTOM_KEYSTONE_CORNER_Y_SIGN not in {-1.0, 1.0}:
        raise ValueError("BOTTOM_KEYSTONE_CORNER_Y_SIGN must be -1 or +1")
    if BOTTOM_KEYSTONE_ROW_AXIS not in {"x", "y"}:
        raise ValueError('BOTTOM_KEYSTONE_ROW_AXIS must be "x" or "y"')
    if not math.isfinite(float(BOTTOM_KEYSTONE_SOCKET_ROTATION_DEG)):
        raise ValueError("BOTTOM_KEYSTONE_SOCKET_ROTATION_DEG must be finite")
    if BOTTOM_KEYSTONE_USE_REFERENCE_SNAP_SOCKET:
        reference_path = Path(BOTTOM_KEYSTONE_REFERENCE_STL).expanduser()
        if not reference_path.is_file():
            raise ValueError(
                "BOTTOM_KEYSTONE_REFERENCE_STL does not identify a readable file"
            )
        if BOTTOM_KEYSTONE_REFERENCE_SHA256:
            reference_digest = hashlib.sha256(reference_path.read_bytes()).hexdigest()
            if reference_digest != BOTTOM_KEYSTONE_REFERENCE_SHA256.lower():
                raise ValueError("Keystone reference STL SHA-256 does not match")
        if BOTTOM_KEYSTONE_SOCKET_INNER_CLEAR_X >= BOTTOM_KEYSTONE_SOCKET_OUTER_X:
            raise ValueError("Keystone socket X walls have no positive thickness")
        if BOTTOM_KEYSTONE_SOCKET_INNER_CLEAR_Y >= BOTTOM_KEYSTONE_SOCKET_OUTER_Y:
            raise ValueError("Keystone socket Y walls have no positive thickness")
    if (
        BOTTOM_KEYSTONE_FACE_POCKET_X <= BOTTOM_KEYSTONE_CUTOUT_X
        or BOTTOM_KEYSTONE_FACE_POCKET_Y <= BOTTOM_KEYSTONE_CUTOUT_Y
    ):
        raise ValueError("Keystone face pockets must exceed their through cutouts")
    if BOTTOM_KEYSTONE_FACE_RECESS_DEPTH >= BOTTOM_THICKNESS:
        raise ValueError("Keystone face recess must leave a snap-in panel floor")
    if BOTTOM_KEYSTONE_INTERNAL_BODY_HEIGHT >= BASE_HEIGHT - BOTTOM_THICKNESS:
        raise ValueError("Keystone internal body keepout exceeds the base height")
    socket_keepout_x, socket_keepout_y = bottom_keystone_socket_plan_dimensions()
    keystone_row_size = (
        max(
            BOTTOM_KEYSTONE_INTERNAL_BODY_X,
            BOTTOM_KEYSTONE_FACE_POCKET_X,
            BOTTOM_KEYSTONE_CUTOUT_X,
            socket_keepout_x,
        )
        if BOTTOM_KEYSTONE_ROW_AXIS == "x"
        else max(
            BOTTOM_KEYSTONE_INTERNAL_BODY_Y,
            BOTTOM_KEYSTONE_FACE_POCKET_Y,
            BOTTOM_KEYSTONE_CUTOUT_Y,
            socket_keepout_y,
        )
    )
    if BOTTOM_KEYSTONE_CENTER_SPACING < (
        keystone_row_size + 2.0 * BOTTOM_KEYSTONE_KEEP_OUT_CLEARANCE
    ):
        raise ValueError("Keystone center spacing violates body keepouts")
    if REAR_FAN_PAD_SURFACE_SAMPLES < 8:
        raise ValueError("REAR_FAN_PAD_SURFACE_SAMPLES must be at least 8")
    if REAR_FAN_CENTER_TANGENTS is not None and (
        len(REAR_FAN_CENTER_TANGENTS) != 2
    ):
        raise ValueError("REAR_FAN_CENTER_TANGENTS must contain two values")
    if REAR_FAN_CENTERLINE_OFFSET is not None and (
        not math.isfinite(float(REAR_FAN_CENTERLINE_OFFSET))
        or REAR_FAN_CENTERLINE_OFFSET <= 0.0
    ):
        raise ValueError(
            "REAR_FAN_CENTERLINE_OFFSET must be positive or None"
        )
    if REAR_FAN_CENTER_TANGENTS is not None and not all(
        math.isfinite(float(value)) for value in REAR_FAN_CENTER_TANGENTS
    ):
        raise ValueError("REAR_FAN_CENTER_TANGENTS values must be finite")
    if REAR_FANS_ENABLED and REAR_FAN_AIRFLOW_DIRECTION != "intake":
        raise ValueError(
            'REAR_FAN_AIRFLOW_DIRECTION must be "intake" so the validated '
            "path runs rear-to-front across the cameras"
        )
    if (
        REAR_FANS_ENABLED
        and REAR_FAN_HUB_DIAMETER >= REAR_FAN_AIR_OPENING_DIAMETER
    ):
        raise ValueError("Rear fan hub must fit inside the air opening")
    fan_centers = rear_fan_center_tangents()
    if abs(fan_centers[1] - fan_centers[0]) < (
        REAR_FAN_PAD_SIZE + REAR_FAN_PAD_GAP
    ) - 1e-6:
        raise ValueError(
            "Rear fan centerline offsets do not leave the configured pad gap"
        )
    if (
        REAR_FAN_CENTER_Z - REAR_FAN_PAD_SIZE / 2.0 < BOTTOM_THICKNESS
        or REAR_FAN_CENTER_Z + REAR_FAN_PAD_SIZE / 2.0 > BASE_HEIGHT
    ):
        raise ValueError("Rear fan pads must fit vertically on the closed base")
    fan_hole_radius = REAR_FAN_MOUNT_HOLE_DIAMETER / 2.0
    fan_air_radius = REAR_FAN_AIR_OPENING_DIAMETER / 2.0
    fan_corner_distance = math.sqrt(2.0) * REAR_FAN_MOUNT_SPACING / 2.0
    if (
        fan_corner_distance - fan_air_radius - fan_hole_radius
        < REAR_FAN_MIN_WEB
    ):
        raise ValueError("Rear fan air opening leaves too little screw-hole web")
    if (
        REAR_FAN_MOUNT_SPACING / 2.0 + fan_hole_radius
        > REAR_FAN_PAD_SIZE / 2.0
    ):
        raise ValueError("Rear fan screw holes exceed the 45 mm seating pad")
    if REAR_FANS_ENABLED:
        (
            fan_open_area,
            fan_effective_open_area,
            eye_exhaust_area,
            exhaust_ratio,
            effective_exhaust_ratio,
            minimum_eye_gap,
        ) = forced_airflow_path_metrics()
        if exhaust_ratio < CAMERA_COOLING_MIN_EXHAUST_TO_FAN_AREA_RATIO:
            raise ValueError(
                "Eye/lens exhaust area is too small for the two rear fans: "
                f"{exhaust_ratio:.3f} < "
                f"{CAMERA_COOLING_MIN_EXHAUST_TO_FAN_AREA_RATIO:.3f}"
            )
        if minimum_eye_gap < CAMERA_COOLING_MIN_EYE_EDGE_GAP:
            raise ValueError(
                "Eye opening leaves too little cooling gap around the lens: "
                f"{minimum_eye_gap:.2f} < "
                f"{CAMERA_COOLING_MIN_EYE_EDGE_GAP:.2f} mm"
            )
        print(
            "FORCED_AIR_COOLING_PATH "
            "direction=rear_fans_to_camera_bodies_to_eye_annuli "
            f"fan_gross_open_area={fan_open_area:.1f}mm^2 "
            f"fan_hub_adjusted_open_area={fan_effective_open_area:.1f}mm^2 "
            f"eye_exhaust_area={eye_exhaust_area:.1f}mm^2 "
            f"exhaust_to_gross_fan_ratio={exhaust_ratio:.3f} "
            f"exhaust_to_hub_adjusted_fan_ratio="
            f"{effective_exhaust_ratio:.3f} "
            f"minimum_eye_edge_gap={minimum_eye_gap:.2f}mm"
        )
    if not math.isfinite(CAMERA_LENS_FACE_OUTSET):
        raise ValueError("CAMERA_LENS_FACE_OUTSET must be finite")
    for name, value in (
        ("EYE_CENTER_Z", EYE_CENTER_Z),
        ("CAMERA_LENS_OFFSET_Z", CAMERA_LENS_OFFSET_Z),
        (
            "CAMERA_ENVELOPE_TANGENTIAL_OFFSET",
            CAMERA_ENVELOPE_TANGENTIAL_OFFSET,
        ),
    ):
        if value is not None and not math.isfinite(float(value)):
            raise ValueError(f"{name} override must be finite or None")
    resolved_lens_outset = camera_lens_face_outset()
    if resolved_lens_outset < CAMERA_LENS_FACE_MIN_OUTSET:
        raise ValueError(
            "Resolved camera lens outset must keep the lens face positively proud"
        )
    required_installation_travel = (
        resolved_lens_outset
        + EYE_FACE_INSET
        + EYE_BEZEL_DEPTH
        + CAMERA_INSTALLATION_LENS_RETRACTION_CLEARANCE
    )
    if (
        not EYE_TOP_LOADING_ENABLED
        and CAMERA_INSTALLATION_REARWARD_TRAVEL < required_installation_travel
    ):
        raise ValueError(
            "CAMERA_INSTALLATION_REARWARD_TRAVEL does not retract the lens "
            "behind the inner eye wall with the configured clearance"
        )
    if EYE_TOP_LOADING_ENABLED:
        minimum_slot_width = (
            mission1.LENS_FACE_WIDTH
            + 2.0 * CAMERA_LENS_OPENING_CLEARANCE
        )
        if EYE_TOP_LOADING_SLOT_WIDTH < minimum_slot_width:
            raise ValueError(
                "EYE_TOP_LOADING_SLOT_WIDTH does not clear the lens housing"
            )
        if EYE_TOP_LOADING_SLOT_WIDTH >= EYE_BEZEL_WIDTH:
            raise ValueError(
                "EYE_TOP_LOADING_SLOT_WIDTH must leave base-side eye structure"
            )
        if 2.0 * EYE_LID_CLOSURE_FIT_CLEARANCE >= EYE_TOP_LOADING_SLOT_WIDTH:
            raise ValueError("Eye-lid closure fit clearance consumes the insert")
        if VISORS_ENABLED:
            if EYE_LID_VISOR_ROOT_RIB_WIDTH <= 0.0:
                raise ValueError(
                    "Eye-lid visor root ribs must have positive width"
                )
            if EYE_LID_VISOR_ROOT_RIB_EDGE_INSET < 0.0:
                raise ValueError(
                    "Eye-lid visor root-rib edge inset cannot be negative"
                )
            if (
                2.0
                * (
                    EYE_LID_VISOR_ROOT_RIB_WIDTH
                    + EYE_LID_VISOR_ROOT_RIB_EDGE_INSET
                )
                >= EYE_TOP_LOADING_SLOT_WIDTH
                - 2.0 * EYE_LID_CLOSURE_FIT_CLEARANCE
            ):
                raise ValueError(
                    "Eye-lid visor root ribs consume the closure tongue"
                )
        if EYE_LID_CLOSURE_PLATE_EMBED >= LID_THICKNESS:
            raise ValueError("Eye-lid closure embed must remain inside the lid")
        slot_bottom = (
            eye_center_z + EYE_TOP_LOADING_SLOT_BOTTOM_OFFSET_Z
        )
        if not eye_center_z <= slot_bottom < BASE_HEIGHT:
            raise ValueError(
                "Top-loading eye slot must begin at/above the optical center"
            )
        if camera_bottom + CAMERA_TOP_LOADING_LIFT <= BASE_HEIGHT:
            raise ValueError(
                "CAMERA_TOP_LOADING_LIFT must raise the camera bottom above the rim"
            )
    if CAMERA_FRONT_STOPS_ENABLED:
        stop_projection = camera_front_stop_projection()
        if stop_projection <= 0.0:
            raise ValueError("Camera front-body plane intersects the inner eye wall")
        if (
            CAMERA_FORWARD_PLACEMENT_MODE == "maximize"
            and abs(stop_projection - CAMERA_FRONT_STOP_PROJECTION) > 1e-6
        ):
            raise RuntimeError("Maximized front-stop/outset calculation disagrees")
        camera_front_stop_specs()
    if CAMERA_NOSE_SHELL_CLEARANCE < 0.0:
        raise ValueError("CAMERA_NOSE_SHELL_CLEARANCE cannot be negative")
    if CAMERA_NOSE_CONTACT_TOLERANCE <= 0.0:
        raise ValueError("CAMERA_NOSE_CONTACT_TOLERANCE must be positive")
    if CAMERA_NOSE_MAX_EXPANSION < 0.0:
        raise ValueError("CAMERA_NOSE_MAX_EXPANSION cannot be negative")
    if CAMERA_BRACKET_MUTUAL_CLEARANCE < 0.0:
        raise ValueError("CAMERA_BRACKET_MUTUAL_CLEARANCE cannot be negative")
    if (
        CAMERA_BODY_WIDTH < CAMERA_BODY_ONLY_WIDTH
        or CAMERA_BODY_DEPTH < CAMERA_BODY_ONLY_DEPTH
        or CAMERA_BODY_HEIGHT < CAMERA_BODY_ONLY_HEIGHT
    ):
        raise ValueError("Camera fit envelope cannot be smaller than its bare body")
    if CAMERA_AZIMUTHS_DEG is None and not 0.0 < CAMERA_HALF_ANGLE_DEG < 90.0:
        raise ValueError("CAMERA_HALF_ANGLE_DEG must be between 0 and 90 degrees")
    if EYE_OPENING_WIDTH >= EYE_BEZEL_WIDTH or EYE_OPENING_HEIGHT >= EYE_BEZEL_HEIGHT:
        raise ValueError("Eye openings must fit inside the bezels")
    if EYE_FACE_RECESS_ENABLED and (
        EYE_BEZEL_WIDTH - 2.0 * EYE_FACE_RECESS_BORDER_OVERLAP
        <= EYE_OPENING_WIDTH
        or EYE_BEZEL_HEIGHT - 2.0 * EYE_FACE_RECESS_BORDER_OVERLAP
        <= EYE_OPENING_HEIGHT
    ):
        raise ValueError(
            "Eye-face recess must leave an overlap ring outside the eye opening"
        )
    if not 0.0 <= EYE_FACE_RECESS_OUTER_FLARE_ANGLE_DEG < 80.0:
        raise ValueError(
            "EYE_FACE_RECESS_OUTER_FLARE_ANGLE_DEG must be in [0, 80)"
        )
    if (
        EYE_OPENING_WIDTH <= mission1.LENS_FACE_WIDTH
        or EYE_OPENING_HEIGHT <= mission1.LENS_FACE_HEIGHT
    ):
        raise ValueError("Eye openings must clear the MISSION 1 lens housing")
    required_lens_edge_clearance = CAMERA_LENS_OPENING_CLEARANCE
    if REAR_FANS_ENABLED:
        required_lens_edge_clearance = max(
            required_lens_edge_clearance,
            CAMERA_COOLING_MIN_EYE_EDGE_GAP,
        )
    opening_width = EYE_OPENING_WIDTH - 2.0 * required_lens_edge_clearance
    opening_height = EYE_OPENING_HEIGHT - 2.0 * required_lens_edge_clearance
    opening_radius = max(
        EYE_OPENING_CORNER_RADIUS - required_lens_edge_clearance,
        0.0,
    )
    lens_points = rounded_rectangle_loop(
        mission1.LENS_FACE_WIDTH,
        mission1.LENS_FACE_HEIGHT,
        mission1.LENS_FACE_CORNER_RADIUS,
    )
    if not all(
        point_inside_rounded_rectangle(
            point,
            opening_width,
            opening_height,
            opening_radius,
        )
        for point in lens_points
    ):
        raise ValueError(
            "Eye opening corner geometry does not clear the lens housing by "
            "CAMERA_LENS_OPENING_CLEARANCE"
        )
    if eye_center_z - EYE_BEZEL_HEIGHT / 2.0 < 0.0:
        raise ValueError("Eye bezel extends below the cover")
    if CAMERA_CRADLES_ENABLED:
        body_radial, body_tangent, body_vertical = (
            mission1.canonical_body_bounds(CAMERA_UPSIDE_DOWN)
        )
        support_top = eye_center_z + body_vertical[0]
        if support_top <= BOTTOM_THICKNESS:
            raise ValueError("Camera support pads have no positive height")
        flat_radial_min = body_radial[0] + mission1.BODY_CORNER_RADIUS
        flat_radial_max = body_radial[1] - mission1.BODY_CORNER_RADIUS
        flat_tangent_min = body_tangent[0] + mission1.BODY_CORNER_RADIUS
        flat_tangent_max = body_tangent[1] - mission1.BODY_CORNER_RADIUS
        pad_half_width = CAMERA_SUPPORT_PAD_TANGENTIAL_WIDTH / 2.0
        pad_centers = camera_support_pad_tangent_centers()
        if CAMERA_SUPPORT_PAD_RADIAL_LENGTH > (
            flat_radial_max - flat_radial_min
        ) + 1e-6:
            raise ValueError("Camera support pads exceed the flat body-bottom region")
        if (
            pad_centers[0] - pad_half_width < flat_tangent_min - 1e-6
            or pad_centers[1] + pad_half_width > flat_tangent_max + 1e-6
        ):
            raise ValueError("Camera support pads exceed the flat body-bottom region")
        if CAMERA_CRADLE_SIDE_GUIDE_RADIAL_LENGTH > (
            flat_radial_max - flat_radial_min
        ) + 1e-6:
            raise ValueError("Camera side guides exceed the flat body-side region")
        if CAMERA_CRADLE_SIDE_GUIDE_RADIAL_PLACEMENT == "front":
            guide_radial_min = (
                flat_radial_max
                - CAMERA_CRADLE_SIDE_GUIDE_FRONT_INSET
                - CAMERA_CRADLE_SIDE_GUIDE_RADIAL_LENGTH
            )
            if guide_radial_min < flat_radial_min - 1e-6:
                raise ValueError(
                    "Front camera side guide exceeds the flat body-side region"
                )
        if CAMERA_CRADLE_FIXED_SIDE_GUIDES != "none":
            resolved_side_guide_height = (
                resolved_camera_cradle_side_guide_height()
            )
            if resolved_side_guide_height < (
                CAMERA_CRADLE_SIDE_GUIDE_MIN_RESOLVED_HEIGHT - 1e-6
            ):
                raise ValueError(
                    "Lens-path clearance leaves the fixed camera side guide too short"
                )
        if (
            camera_cradle_rear_guides_enabled()
            and CAMERA_CRADLE_REAR_GUIDE_TANGENTIAL_WIDTH
            > (flat_tangent_max - flat_tangent_min) + 1e-6
        ):
            raise ValueError("Camera rear guide exceeds the flat body-back region")
        if camera_cradle_rear_guides_enabled():
            rear_segment_width = (
                CAMERA_CRADLE_REAR_GUIDE_TANGENTIAL_WIDTH
                - CAMERA_CRADLE_REAR_GUIDE_CENTER_AIR_GAP
            ) / 2.0
            if rear_segment_width < (
                CAMERA_CRADLE_REAR_GUIDE_MIN_SEGMENT_WIDTH - 1e-6
            ):
                raise ValueError(
                    "Camera rear-guide air gap leaves undersized guide segments"
                )
    if CAMERA_CRADLE_FIXED_SIDE_GUIDES not in {
        "non_usb_only",
        "both",
        "none",
    }:
        raise ValueError("Unsupported CAMERA_CRADLE_FIXED_SIDE_GUIDES mode")
    if CAMERA_CRADLE_SIDE_GUIDE_RADIAL_PLACEMENT not in {"front", "center"}:
        raise ValueError(
            "Unsupported CAMERA_CRADLE_SIDE_GUIDE_RADIAL_PLACEMENT mode"
        )
    if CAMERA_USB_SIDE not in {"auto", "tangent_min", "tangent_max"}:
        raise ValueError("Unsupported CAMERA_USB_SIDE mode")
    if CAMERA_BRACKET_COMPACT_RAIL_SIDE not in {
        "usb",
        "non_usb",
        "outer",
    }:
        raise ValueError("Unsupported CAMERA_BRACKET_COMPACT_RAIL_SIDE mode")
    if (
        not isinstance(CAMERA_INSTALLATION_PATH_STEPS, int)
        or isinstance(CAMERA_INSTALLATION_PATH_STEPS, bool)
    ):
        raise ValueError("CAMERA_INSTALLATION_PATH_STEPS must be an integer")
    if not math.isfinite(float(CAMERA_USB_PORT_RADIAL_OFFSET_FROM_BODY_CENTER)):
        raise ValueError(
            "CAMERA_USB_PORT_RADIAL_OFFSET_FROM_BODY_CENTER must be finite"
        )
    if CAMERA_USB_ACCESS_ENABLED:
        body_radial, _, body_vertical = mission1.canonical_body_bounds(
            CAMERA_UPSIDE_DOWN
        )
        port_radial_center = (
            sum(body_radial) / 2.0
            + CAMERA_USB_PORT_RADIAL_OFFSET_FROM_BODY_CENTER
        )
        port_vertical_center = (
            body_vertical[0] + CAMERA_USB_PORT_CENTER_ABOVE_BODY_BOTTOM
        )
        if (
            port_radial_center - CAMERA_USB_PORT_RADIAL_WIDTH / 2.0
            < body_radial[0]
            or port_radial_center + CAMERA_USB_PORT_RADIAL_WIDTH / 2.0
            > body_radial[1]
        ):
            raise ValueError("USB port radial bounds exceed the camera body")
        if (
            port_vertical_center - CAMERA_USB_PORT_HEIGHT / 2.0
            < body_vertical[0]
            or port_vertical_center + CAMERA_USB_PORT_HEIGHT / 2.0
            > body_vertical[1]
        ):
            raise ValueError("USB port vertical bounds exceed the camera body")
    if VISORS_ENABLED and VISOR_BACK_BOTTOM_Z > VISOR_BACK_TOP_Z:
        raise ValueError("Visor back Z values are reversed")
    if VISORS_ENABLED and VISOR_FRONT_BOTTOM_Z > VISOR_FRONT_TOP_Z:
        raise ValueError("Visor front Z values are reversed")
    if VISORS_ENABLED and resolved_visor_back_inset() <= 0.0:
        raise ValueError("Camera clearance leaves no positive visor depth")
    if VISORS_ENABLED and max(
        resolved_visor_z(VISOR_BACK_TOP_Z),
        resolved_visor_z(VISOR_FRONT_TOP_Z),
    ) > BODY_HEIGHT + 1e-6:
        raise ValueError(
            "Camera-cleared visor exceeds BODY_HEIGHT; reduce visor height or "
            "camera clearance"
        )
    if CAMERA_CARTRIDGE_WORM_ENABLED:
        if not CAMERA_BRACKETS_ENABLED:
            raise ValueError(
                "The adjustable cartridge requires CAMERA_BRACKETS_ENABLED "
                "for its removable pivot hold-down"
            )
        if not EYE_TOP_LOADING_ENABLED:
            raise ValueError(
                "The cartridge's front/rear stops require top-loading eye "
                "openings so the camera can be installed vertically"
            )
        if ADJUSTABLE_CAMERA_INDEX not in (1, 2):
            raise ValueError("ADJUSTABLE_CAMERA_INDEX must be 1 or 2")
        if not isinstance(
            CAMERA_CARRIER_CHIMNEY_MAX_FRAGMENT_FACES,
            int,
        ) or isinstance(CAMERA_CARRIER_CHIMNEY_MAX_FRAGMENT_FACES, bool):
            raise ValueError(
                "CAMERA_CARRIER_CHIMNEY_MAX_FRAGMENT_FACES must be an integer"
            )
        finite_cartridge_values = {
            "ADJUSTABLE_CAMERA_YAW_RANGE_DEG": (
                ADJUSTABLE_CAMERA_YAW_RANGE_DEG
            ),
            "ADJUSTABLE_CAMERA_PREVIEW_YAW_DEG": (
                ADJUSTABLE_CAMERA_PREVIEW_YAW_DEG
            ),
            "ADJUSTABLE_CAMERA_SWEEP_STEP_DEG": (
                ADJUSTABLE_CAMERA_SWEEP_STEP_DEG
            ),
            "ADJUSTABLE_CAMERA_PIVOT_RADIAL": (
                ADJUSTABLE_CAMERA_PIVOT_RADIAL
            ),
            "ADJUSTABLE_CAMERA_PIVOT_TANGENTIAL": (
                ADJUSTABLE_CAMERA_PIVOT_TANGENTIAL
            ),
            "CAMERA_GEAR_MODULE": CAMERA_GEAR_MODULE,
            "CAMERA_GEAR_EQUIVALENT_TEETH": CAMERA_GEAR_EQUIVALENT_TEETH,
            "CAMERA_GEAR_MIRRORED_ANGLE_OFFSET_DEG": (
                CAMERA_GEAR_MIRRORED_ANGLE_OFFSET_DEG
            ),
            "CAMERA_WORM_STARTS": CAMERA_WORM_STARTS,
            "CAMERA_WORM_DIAMETER_QUOTIENT": (
                CAMERA_WORM_DIAMETER_QUOTIENT
            ),
            "CAMERA_HARD_STOP_MIRRORED_EXTRA_LIMIT_DEG": (
                CAMERA_HARD_STOP_MIRRORED_EXTRA_LIMIT_DEG
            ),
            "CAMERA_HARD_STOP_PIN_DIAMETER": CAMERA_HARD_STOP_PIN_DIAMETER,
            "CAMERA_HARD_STOP_SLOT_RADIUS": CAMERA_HARD_STOP_SLOT_RADIUS,
            "CAMERA_HARD_STOP_SLOT_LOCAL_ANGLE_DEG": (
                CAMERA_HARD_STOP_SLOT_LOCAL_ANGLE_DEG
            ),
            "CAMERA_HARD_STOP_SLOT_DIAMETRAL_CLEARANCE": (
                CAMERA_HARD_STOP_SLOT_DIAMETRAL_CLEARANCE
            ),
            "CAMERA_HARD_STOP_SLOT_REINFORCEMENT_WIDTH": (
                CAMERA_HARD_STOP_SLOT_REINFORCEMENT_WIDTH
            ),
            "CAMERA_HARD_STOP_SLOT_PIVOT_WEB": (
                CAMERA_HARD_STOP_SLOT_PIVOT_WEB
            ),
            "CAMERA_HARD_STOP_SLOT_REINFORCEMENT_EXTRA_HEIGHT": (
                CAMERA_HARD_STOP_SLOT_REINFORCEMENT_EXTRA_HEIGHT
            ),
            "CAMERA_HARD_STOP_MIN_ENDPOINT_CLEARANCE": (
                CAMERA_HARD_STOP_MIN_ENDPOINT_CLEARANCE
            ),
        }
        for name, value in finite_cartridge_values.items():
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        for name, value in (
            ("CAMERA_GEAR_EQUIVALENT_TEETH", CAMERA_GEAR_EQUIVALENT_TEETH),
            ("CAMERA_WORM_STARTS", CAMERA_WORM_STARTS),
        ):
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{name} must be an integer")
        if ADJUSTABLE_CAMERA_YAW_RANGE_DEG <= 0.0:
            raise ValueError("Adjustable camera yaw range must be positive")
        if ADJUSTABLE_CAMERA_SWEEP_STEP_DEG <= 0.0:
            raise ValueError("Adjustable camera sweep step must be positive")
        if abs(ADJUSTABLE_CAMERA_PREVIEW_YAW_DEG) > (
            ADJUSTABLE_CAMERA_YAW_RANGE_DEG + 1e-9
        ):
            raise ValueError("Preview yaw exceeds the mechanical yaw range")
        if not (
            CAMERA_CARRIER_USB_SIDE_GUIDE_ENABLED
            or CAMERA_CARRIER_NON_USB_SIDE_GUIDE_ENABLED
        ):
            raise ValueError("At least one carrier side guide must be enabled")
        body_radial, body_tangent, body_vertical = (
            mission1.canonical_body_bounds(CAMERA_UPSIDE_DOWN)
        )
        tray_radial_size = (
            body_radial[1]
            - body_radial[0]
            + 2.0 * CAMERA_CARRIER_TRAY_RADIAL_MARGIN
        )
        tray_tangent_size = (
            body_tangent[1]
            - body_tangent[0]
            + 2.0 * CAMERA_CARRIER_TRAY_TANGENTIAL_MARGIN
        )
        if 2.0 * CAMERA_CARRIER_TRAY_FRAME_WIDTH >= min(
            tray_radial_size,
            tray_tangent_size,
        ):
            raise ValueError("Carrier tray frame consumes its vented interior")
        if min(
            CAMERA_CARRIER_TRAY_RADIAL_MARGIN,
            CAMERA_CARRIER_TRAY_TANGENTIAL_MARGIN,
        ) < CAMERA_CARRIER_GUIDE_THICKNESS:
            raise ValueError("Carrier tray must fully root the guide thickness")
        if CAMERA_CARRIER_GUIDE_TRAY_EMBED >= CAMERA_CARRIER_TRAY_THICKNESS:
            raise ValueError("Carrier guide embed consumes the complete tray")
        if not 0.0 < CAMERA_CARRIER_FIT_PROBE_LIFT < 1.0:
            raise ValueError(
                "CAMERA_CARRIER_FIT_PROBE_LIFT must be between 0 and 1 mm"
            )
        if not 0.0 < CAMERA_CARRIER_MIN_TRAY_OPEN_AREA_RATIO < 1.0:
            raise ValueError("Carrier minimum tray open-area ratio must be 0..1")
        *_, tray_open_area_ratio = camera_carrier_tray_airflow_metrics(
            body_radial,
            body_tangent,
        )
        if tray_open_area_ratio < CAMERA_CARRIER_MIN_TRAY_OPEN_AREA_RATIO:
            raise ValueError(
                "Carrier rails/frame leave too little open cooling area: "
                f"{tray_open_area_ratio:.3f} < "
                f"{CAMERA_CARRIER_MIN_TRAY_OPEN_AREA_RATIO:.3f}"
            )
        tray_open_area = camera_carrier_tray_airflow_metrics(
            body_radial,
            body_tangent,
        )[3]
        camera_plan_area = tray_open_area / tray_open_area_ratio
        conservative_reinforced_open_ratio = max(
            tray_open_area - camera_hard_stop_reinforcement_plan_area(),
            0.0,
        ) / camera_plan_area
        if conservative_reinforced_open_ratio < (
            CAMERA_CARRIER_MIN_TRAY_OPEN_AREA_RATIO
        ):
            raise ValueError(
                "Hard-stop reinforcement leaves too little conservative cooling "
                f"area: {conservative_reinforced_open_ratio:.3f} < "
                f"{CAMERA_CARRIER_MIN_TRAY_OPEN_AREA_RATIO:.3f}"
            )
        if (
            CAMERA_CARRIER_SUPPORT_RAIL_WIDTH
            > CAMERA_SUPPORT_PAD_TANGENTIAL_WIDTH
        ):
            raise ValueError("Carrier support rails must fit below the support pads")
        rear_segment_width = (
            CAMERA_CARRIER_REAR_GUIDE_TOTAL_WIDTH
            - CAMERA_CARRIER_REAR_GUIDE_CENTER_AIR_GAP
        ) / 2.0
        if rear_segment_width < CAMERA_CARRIER_REAR_GUIDE_MIN_SEGMENT_WIDTH:
            raise ValueError("Carrier rear air gap leaves undersized guide blocks")
        if (
            CAMERA_CARRIER_REAR_GUIDE_CENTER_AIR_GAP
            < CAMERA_CARRIER_MIN_REAR_AIR_GAP
        ):
            raise ValueError("Carrier rear guides choke the cooling-air channel")
        if CAMERA_CARRIER_REAR_GUIDE_TOTAL_WIDTH > (
            body_tangent[1] - body_tangent[0]
        ):
            raise ValueError("Carrier rear guides exceed the camera body width")
        guide_specs = camera_carrier_side_guide_specs(
            body_radial,
            body_tangent,
        )
        if CAMERA_CARRIER_USB_SIDE_GUIDE_ENABLED and not any(
            side == camera_usb_side_name() for side, *_ in guide_specs
        ):
            raise ValueError("USB keepout leaves no usable carrier-side guide")
        side_air_channels = camera_carrier_side_air_channel_widths(
            body_radial,
            body_tangent,
        )
        if any(
            width < CAMERA_CARRIER_MIN_SIDE_AIR_CHANNEL
            for width in side_air_channels.values()
        ):
            raise ValueError(
                "Carrier side guides choke a cooling-air channel: "
                f"{side_air_channels}"
            )
        effective_rear_air_channel = (
            CAMERA_CARRIER_REAR_GUIDE_CENTER_AIR_GAP
            * math.cos(math.radians(ADJUSTABLE_CAMERA_YAW_RANGE_DEG))
        )
        if effective_rear_air_channel < CAMERA_CARRIER_MIN_REAR_AIR_GAP:
            raise ValueError(
                "Carrier rear air channel becomes too narrow at full yaw: "
                f"{effective_rear_air_channel:.2f} < "
                f"{CAMERA_CARRIER_MIN_REAR_AIR_GAP:.2f}"
            )
        configured_camera = {
            "angle": camera_azimuths()[ADJUSTABLE_CAMERA_INDEX - 1]
        }
        resolved_pivot_tangent = adjustable_camera_pivot_tangential(
            configured_camera
        )
        if not (
            body_radial[0]
            <= ADJUSTABLE_CAMERA_PIVOT_RADIAL
            <= body_radial[1]
            and body_tangent[0]
            <= resolved_pivot_tangent
            <= body_tangent[1]
        ):
            raise ValueError("Adjustable camera pivot must lie below the main body")
        carrier_z0 = BOTTOM_THICKNESS + CAMERA_CARRIER_BOTTOM_CLEARANCE
        carrier_z1 = carrier_z0 + CAMERA_CARRIER_TRAY_THICKNESS
        support_top = eye_center_z + body_vertical[0]
        if carrier_z0 <= BOTTOM_THICKNESS:
            raise ValueError("Rotating carrier must clear the enclosure floor")
        if carrier_z1 >= support_top:
            raise ValueError("Rotating carrier tray consumes the camera support gap")
        if CAMERA_CARRIER_PIVOT_PIN_HEIGHT >= (
            CAMERA_CARRIER_BOTTOM_CLEARANCE
            + CAMERA_CARRIER_TRAY_THICKNESS
        ):
            raise ValueError("Pivot pin would protrude through the carrier tray")
        pivot_engagement = (
            CAMERA_CARRIER_PIVOT_PIN_HEIGHT
            - CAMERA_CARRIER_BOTTOM_CLEARANCE
        )
        if pivot_engagement < CAMERA_CARRIER_MIN_PIVOT_ENGAGEMENT:
            raise ValueError(
                "Carrier pivot engagement is too short for the configured "
                f"minimum: {pivot_engagement:.2f} < "
                f"{CAMERA_CARRIER_MIN_PIVOT_ENGAGEMENT:.2f} mm"
            )
        thrust_stack_height = (
            CAMERA_CARRIER_THRUST_PAD_HEIGHT
            + CAMERA_CARRIER_THRUST_WASHER_THICKNESS
            + CAMERA_CARRIER_THRUST_RUNNING_CLEARANCE
        )
        if abs(CAMERA_CARRIER_BOTTOM_CLEARANCE - thrust_stack_height) > 1e-6:
            raise ValueError(
                "CAMERA_CARRIER_BOTTOM_CLEARANCE must equal the printed pad + "
                "thrust washer + running-clearance stack"
            )
        pivot_bore_diameter = (
            CAMERA_CARRIER_PIVOT_PIN_DIAMETER
            + CAMERA_CARRIER_PIVOT_CLEARANCE
        )
        if not (
            pivot_bore_diameter < CAMERA_CARRIER_THRUST_WASHER_ID
            < CAMERA_CARRIER_THRUST_WASHER_OD
            <= CAMERA_CARRIER_THRUST_PAD_DIAMETER
        ):
            raise ValueError("Carrier thrust-washer diameters do not fit the pivot")
        if CAMERA_GEAR_EQUIVALENT_TEETH < 24:
            raise ValueError("Sector gear needs at least 24 equivalent teeth")
        if CAMERA_WORM_STARTS != 1:
            raise ValueError("This self-locking design requires a one-start worm")
        if not (
            CAMERA_GEAR_SECTOR_START_DEG
            < CAMERA_GEAR_CONTACT_DEG
            < CAMERA_GEAR_SECTOR_END_DEG
        ):
            raise ValueError("Worm contact must lie inside the gear sector")
        sector_margin = min(
            CAMERA_GEAR_CONTACT_DEG - CAMERA_GEAR_SECTOR_START_DEG,
            CAMERA_GEAR_SECTOR_END_DEG - CAMERA_GEAR_CONTACT_DEG,
        )
        if sector_margin <= ADJUSTABLE_CAMERA_YAW_RANGE_DEG:
            raise ValueError("Sector lacks teeth beyond the full camera yaw range")
        if CAMERA_HARD_STOP_LIMIT_DEG < ADJUSTABLE_CAMERA_YAW_RANGE_DEG:
            raise ValueError("Hard stops must lie beyond the configured yaw range")
        if CAMERA_HARD_STOP_MIRRORED_EXTRA_LIMIT_DEG < 0.0:
            raise ValueError(
                "CAMERA_HARD_STOP_MIRRORED_EXTRA_LIMIT_DEG cannot be negative"
            )
        if min(
            CAMERA_HARD_STOP_PIN_DIAMETER,
            CAMERA_HARD_STOP_SLOT_RADIUS,
            CAMERA_HARD_STOP_SLOT_REINFORCEMENT_WIDTH,
            CAMERA_HARD_STOP_SLOT_PIVOT_WEB,
        ) <= 0.0:
            raise ValueError("Hard-stop dimensions must be positive")
        if CAMERA_HARD_STOP_SLOT_DIAMETRAL_CLEARANCE < 0.0:
            raise ValueError("Hard-stop slot clearance cannot be negative")
        if CAMERA_HARD_STOP_SLOT_REINFORCEMENT_EXTRA_HEIGHT < 0.0:
            raise ValueError("Hard-stop reinforcement height cannot be negative")
        if CAMERA_HARD_STOP_MIN_ENDPOINT_CLEARANCE < 0.0:
            raise ValueError("Hard-stop endpoint clearance cannot be negative")
        slot_half_width = (
            CAMERA_HARD_STOP_PIN_DIAMETER
            + CAMERA_HARD_STOP_SLOT_DIAMETRAL_CLEARANCE
        ) / 2.0
        if slot_half_width + CAMERA_HARD_STOP_SLOT_REINFORCEMENT_WIDTH >= (
            CAMERA_HARD_STOP_SLOT_RADIUS
        ):
            raise ValueError("Hard-stop slot reinforcement reaches the pivot")
        if (
            carrier_z1 + CAMERA_HARD_STOP_SLOT_REINFORCEMENT_EXTRA_HEIGHT
            >= support_top
        ):
            raise ValueError("Hard-stop reinforcement reaches the camera underside")
        mirrored_hard_stop_limit = (
            CAMERA_HARD_STOP_LIMIT_DEG
            + CAMERA_HARD_STOP_MIRRORED_EXTRA_LIMIT_DEG
        )
        if max(CAMERA_HARD_STOP_LIMIT_DEG, mirrored_hard_stop_limit) >= (
            sector_margin
        ):
            raise ValueError("Hard stops lie beyond the sector's toothed range")
        configured_hard_stop_limit = CAMERA_HARD_STOP_LIMIT_DEG
        if adjustable_mechanism_hand(configured_camera) < 0.0:
            configured_hard_stop_limit += (
                CAMERA_HARD_STOP_MIRRORED_EXTRA_LIMIT_DEG
            )
        endpoint_stop_surface_gap = camera_hard_stop_remaining_travel(
            configured_hard_stop_limit,
            ADJUSTABLE_CAMERA_YAW_RANGE_DEG,
        )
        if endpoint_stop_surface_gap < CAMERA_HARD_STOP_MIN_ENDPOINT_CLEARANCE:
            raise ValueError(
                "Hard-stop slot needs more clearance at the configured yaw "
                f"endpoints: {endpoint_stop_surface_gap:.3f} < "
                f"{CAMERA_HARD_STOP_MIN_ENDPOINT_CLEARANCE:.3f} mm"
            )
        if not (
            0.0
            < CAMERA_GEAR_RIM_INNER_RADIUS
            < camera_sector_root_radius()
            < camera_sector_tip_radius()
        ):
            raise ValueError("Sector gear radii are inconsistent")
        if camera_worm_root_radius() <= (
            CAMERA_WORM_SHAFT_DIAMETER + CAMERA_WORM_SHAFT_CLEARANCE
        ) / 2.0:
            raise ValueError("Worm root is too thin around its shaft bore")
        if CAMERA_WORM_BEARING_OD <= CAMERA_WORM_SHAFT_DIAMETER:
            raise ValueError("Worm bearings must exceed the shaft diameter")
        bearing_pocket_diameter = (
            CAMERA_WORM_BEARING_OD
            + CAMERA_WORM_BEARING_POCKET_DIAMETER_ADJUSTMENT
        )
        if bearing_pocket_diameter <= CAMERA_WORM_SHAFT_DIAMETER:
            raise ValueError("Worm bearing pocket collapses into the shaft bore")
        intended_worm_end_gap = (
            CAMERA_WORM_THRUST_WASHER_THICKNESS
            + CAMERA_WORM_AXIAL_RUNNING_CLEARANCE
        )
        if abs(CAMERA_WORM_BLOCK_OFFSET - intended_worm_end_gap) > 1e-6:
            raise ValueError(
                "CAMERA_WORM_BLOCK_OFFSET must equal the thrust-washer + "
                "axial-clearance stack"
            )
        hold_down_disk_diameter = (
            CAMERA_HOLD_DOWN_PAD_DIAMETER
            - 2.0 * CAMERA_HOLD_DOWN_PAD_MATERIAL_CLEARANCE
        )
        if hold_down_disk_diameter <= 0.0:
            raise ValueError("Hold-down material clearance consumes its pad")
        if CAMERA_HOLD_DOWN_PAD_MATERIAL_THICKNESS <= (
            CAMERA_BRACKET_CLAMP_PRELOAD_Z
        ):
            raise ValueError("Hold-down disk is too thin for the clamp preload")
        radial_engagement = (
            camera_sector_tip_radius()
            + camera_worm_outer_radius()
            - camera_sector_pitch_radius()
            - camera_worm_pitch_radius()
            - CAMERA_GEAR_MESH_CENTER_CLEARANCE
        )
        if radial_engagement < CAMERA_GEAR_MIN_RADIAL_ENGAGEMENT:
            raise ValueError(
                "Worm mesh clearance leaves insufficient radial engagement"
            )
    if CAMERA_BRACKETS_ENABLED:
        if CAMERA_BRACKET_CLAMP_PRELOAD_Z <= 0.0:
            raise ValueError("Camera bracket clamp preload must be positive")
        if (
            resolved_lens_outset - CAMERA_BRACKET_REAR_CLEARANCE
            < CAMERA_LENS_FACE_MIN_OUTSET
        ):
            raise ValueError(
                "Rear-stop play could retract the lens below its minimum outset"
            )
        # The loose plate clears the complete envelope, while its contact rails
        # reference the solid main-body top and bypass the top button.
        _, _, body_vertical = mission1.canonical_body_bounds(
            CAMERA_UPSIDE_DOWN
        )
        body_top = eye_center_z + body_vertical[1]
        plate_underside = camera_top + CAMERA_BRACKET_TOP_FEATURE_CLEARANCE_Z
        bracket_top = (
            plate_underside + CAMERA_BRACKET_THICKNESS
        )
        if bracket_top >= BASE_HEIGHT:
            raise ValueError("Camera brackets do not fit below the removable lid")
        counterbore_floor = (
            CAMERA_BRACKET_THICKNESS - LID_SCREW_HEAD_COUNTERBORE_DEPTH
        )
        if counterbore_floor < CAMERA_BRACKET_MIN_COUNTERBORE_FLOOR:
            raise ValueError(
                "Bracket counterbores leave less than the configured solid floor"
            )
        primary_plate_radial_depth = (
            CAMERA_BRACKET_PRIMARY_REAR_OVERLAP
            + CAMERA_BRACKET_OVER_CAMERA_DEPTH
        )
        if 2.0 * CAMERA_BRACKET_ARM_PLATE_EMBED >= primary_plate_radial_depth:
            raise ValueError(
                "CAMERA_BRACKET_ARM_PLATE_EMBED must leave an interior radial "
                "anchor region in the primary plate"
            )
        if CAMERA_BRACKET_L_CORNER_GUIDES_ENABLED:
            if not (
                CAMERA_BRACKET_USB_SIDE_LOCATOR_ENABLED
                or CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_ENABLED
            ):
                raise ValueError(
                    "L-shaped corner guides require an enabled side locator"
                )
            if CAMERA_BRACKET_GUIDE_PLATE_OVERHANG < 1.2:
                raise ValueError(
                    "Bracket guide-plate overhang must cover the 1.2 mm "
                    "primary-plate edge bevel"
                )
            _, corner_body_tangent, _ = mission1.canonical_body_bounds(
                CAMERA_UPSIDE_DOWN
            )
            if CAMERA_BRACKET_L_CORNER_RETURN_INBOARD_LENGTH <= (
                mission1.BODY_CORNER_RADIUS
            ):
                raise ValueError(
                    "L-shaped rear returns must reach beyond the rounded "
                    "camera corner"
                )
            if 2.0 * CAMERA_BRACKET_L_CORNER_RETURN_INBOARD_LENGTH >= (
                corner_body_tangent[1] - corner_body_tangent[0]
            ):
                raise ValueError(
                    "L-shaped rear returns consume the rear cooling channel"
                )
        if (
            CAMERA_BRACKET_SPLIT_REAR_LIP
            and not CAMERA_BRACKET_COMPACT_OUTER_RAIL_ONLY
            and not CAMERA_BRACKET_L_CORNER_GUIDES_ENABLED
        ):
            rear_lip_segment_width = (
                CAMERA_BRACKET_REAR_LIP_WIDTH
                - CAMERA_BRACKET_REAR_LIP_CENTER_AIR_GAP
            ) / 2.0
            if rear_lip_segment_width < (
                CAMERA_BRACKET_REAR_LIP_MIN_SEGMENT_WIDTH - 1e-6
            ):
                raise ValueError(
                    "Bracket rear-lip air gap leaves undersized stop segments"
                )
        if CAMERA_BRACKET_USB_SIDE_LOCATOR_ENABLED:
            if CAMERA_BRACKET_USB_SIDE_LOCATOR_RADIAL_LENGTH > (
                CAMERA_BRACKET_OVER_CAMERA_DEPTH - mission1.BODY_CORNER_RADIUS
            ) + 1e-6:
                raise ValueError(
                    "Bracket USB-side locator exceeds the supported plate/body land"
                )
            _, _, usb_vertical = camera_usb_local_access_bounds()
            locator_contact_bottom = (
                body_vertical[1]
                - mission1.BODY_CORNER_RADIUS
                - CAMERA_BRACKET_USB_SIDE_LOCATOR_HEIGHT
            )
            if usb_vertical[1] >= locator_contact_bottom:
                raise ValueError(
                    "Bracket USB-side locator intrudes into the USB plug envelope"
                )
        if CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_ENABLED:
            if CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_RADIAL_LENGTH > (
                CAMERA_BRACKET_OVER_CAMERA_DEPTH - mission1.BODY_CORNER_RADIUS
            ) + 1e-6:
                raise ValueError(
                    "Bracket non-USB locator exceeds the supported plate/body land"
                )
            side_button_vertical = mission1.canonical_feature_bounds(
                mission1.SIDE_BUTTON_CENTER,
                mission1.SIDE_BUTTON_SIZE,
                upside_down=CAMERA_UPSIDE_DOWN,
            )[2]
            locator_contact_bottom = (
                body_vertical[1]
                - mission1.BODY_CORNER_RADIUS
                - CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_HEIGHT
            )
            if side_button_vertical[1] >= locator_contact_bottom:
                raise ValueError(
                    "Bracket non-USB locator intrudes into the side-button envelope"
                )
        if CAMERA_BRACKET_SIDE_LOCATOR_GUSSETS_ENABLED:
            enabled_locator_thicknesses = []
            enabled_locator_heights = []
            if CAMERA_BRACKET_USB_SIDE_LOCATOR_ENABLED:
                enabled_locator_thicknesses.append(
                    CAMERA_BRACKET_USB_SIDE_LOCATOR_THICKNESS
                )
                enabled_locator_heights.append(
                    CAMERA_BRACKET_USB_SIDE_LOCATOR_HEIGHT
                )
            if CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_ENABLED:
                enabled_locator_thicknesses.append(
                    CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_THICKNESS
                )
                enabled_locator_heights.append(
                    CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_HEIGHT
                )
            if not enabled_locator_thicknesses:
                raise ValueError("Side-locator gussets require an enabled locator")
            if CAMERA_BRACKET_SIDE_LOCATOR_GUSSET_ROOT_EMBED >= min(
                enabled_locator_thicknesses
            ):
                raise ValueError(
                    "Side-locator gusset root embed must be smaller than the tab"
                )
            maximum_gusset_depth = (
                mission1.BODY_CORNER_RADIUS + min(enabled_locator_heights)
            )
            if CAMERA_BRACKET_SIDE_LOCATOR_GUSSET_DEPTH > maximum_gusset_depth:
                raise ValueError(
                    "Side-locator gusset extends below its vertical tab"
                )
        if CAMERA_BRACKET_SIDE_LOCATOR_PLATE_EMBED >= (
            CAMERA_BRACKET_THICKNESS - CAMERA_BRACKET_MIN_COUNTERBORE_FLOOR
        ):
            raise ValueError(
                "Side-locator plate embed leaves too little bracket-top material"
            )
        minimum_arm_width = (
            LID_SCREW_HEAD_COUNTERBORE_DIAMETER
            + 2.0 * CAMERA_BRACKET_ARM_COUNTERBORE_MIN_WEB
        )
        if CAMERA_BRACKET_ARM_WIDTH < minimum_arm_width:
            raise ValueError(
                "CAMERA_BRACKET_ARM_WIDTH leaves less than the configured web "
                "around the socket-head counterbore"
            )
        clamp_travel = (
            CAMERA_BRACKET_BODY_CONTACT_CLEARANCE_Z
            + CAMERA_BRACKET_CLAMP_PRELOAD_Z
        )
        final_plate_underside = plate_underside - clamp_travel
        if (
            final_plate_underside - camera_top
            < CAMERA_BRACKET_BUTTON_MIN_CLEARANCE_Z - 1e-6
        ):
            raise ValueError(
                "Tightened bracket plate would load the camera's highest control"
            )
        loose_contact_bottom = (
            body_top + CAMERA_BRACKET_BODY_CONTACT_CLEARANCE_Z
        )
        if loose_contact_bottom >= plate_underside:
            raise ValueError("Bracket contact rails have no positive depth")
        body_radial, body_tangent, _ = mission1.canonical_body_bounds(
            CAMERA_UPSIDE_DOWN
        )
        flat_tangent_min = body_tangent[0] + mission1.BODY_CORNER_RADIUS
        flat_tangent_max = body_tangent[1] - mission1.BODY_CORNER_RADIUS
        rail_half_width = CAMERA_BRACKET_CONTACT_RAIL_WIDTH / 2.0
        rail_centers = (
            body_tangent[0] + CAMERA_BRACKET_CONTACT_RAIL_EDGE_INSET,
            body_tangent[1] - CAMERA_BRACKET_CONTACT_RAIL_EDGE_INSET,
        )
        if (
            rail_centers[0] - rail_half_width < flat_tangent_min - 1e-6
            or rail_centers[1] + rail_half_width > flat_tangent_max + 1e-6
        ):
            raise ValueError("Bracket contact rails miss the flat body-top region")
        rail_radial_max = (
            body_radial[0] + CAMERA_BRACKET_OVER_CAMERA_DEPTH
        )
        rail_radial_min = (
            rail_radial_max - CAMERA_BRACKET_CONTACT_RAIL_RADIAL_LENGTH
        )
        if (
            rail_radial_min
            < body_radial[0] + mission1.BODY_CORNER_RADIUS - 1e-6
            or rail_radial_max
            > body_radial[1] - mission1.BODY_CORNER_RADIUS + 1e-6
        ):
            raise ValueError("Bracket contact rails miss the flat body-top region")
        button_radial, button_tangent, button_vertical = (
            mission1.canonical_top_button_bounds(CAMERA_UPSIDE_DOWN)
        )
        if button_vertical[1] > body_vertical[1] + 1e-6:
            relief_tangent = (
                button_tangent[0] - CAMERA_BRACKET_BUTTON_RELIEF_MARGIN,
                button_tangent[1] + CAMERA_BRACKET_BUTTON_RELIEF_MARGIN,
            )
            relief_radial = (
                button_radial[0] - CAMERA_BRACKET_BUTTON_RELIEF_MARGIN,
                button_radial[1] + CAMERA_BRACKET_BUTTON_RELIEF_MARGIN,
            )
            for center in rail_centers:
                rail_tangent = (
                    center - rail_half_width,
                    center + rail_half_width,
                )
                tangent_overlap = (
                    rail_tangent[0] < relief_tangent[1]
                    and relief_tangent[0] < rail_tangent[1]
                )
                radial_overlap = (
                    rail_radial_min < relief_radial[1]
                    and relief_radial[0] < rail_radial_max
                )
                if tangent_overlap and radial_overlap:
                    raise ValueError(
                        "Top-button relief would remove a body contact rail"
                    )


def camera_azimuths():
    if CAMERA_AZIMUTHS_DEG is not None:
        if len(CAMERA_AZIMUTHS_DEG) != 2:
            raise ValueError("CAMERA_AZIMUTHS_DEG override must contain two angles")
        return tuple(float(angle) for angle in CAMERA_AZIMUTHS_DEG)
    return (
        CAMERA_CENTERLINE_AZIMUTH_DEG - CAMERA_HALF_ANGLE_DEG,
        CAMERA_CENTERLINE_AZIMUTH_DEG + CAMERA_HALF_ANGLE_DEG,
    )


def camera_body_center_z() -> float:
    offset = CAMERA_LENS_OFFSET_Z
    if offset is None:
        offset = -mission1.canonical_envelope_center_vertical(
            CAMERA_UPSIDE_DOWN
        )
    return camera_eye_center_z() - float(offset)


def camera_envelope_tangential_offset() -> float:
    if CAMERA_ENVELOPE_TANGENTIAL_OFFSET is None:
        return mission1.canonical_envelope_center_tangential(
            CAMERA_UPSIDE_DOWN
        )
    return float(CAMERA_ENVELOPE_TANGENTIAL_OFFSET)


def minimum_body_scale_between(z0: float, z1: float) -> float:
    if z0 > z1:
        z0, z1 = z1, z0
    samples = [z0, z1]
    samples.extend(z for z, _ in BODY_SECTIONS if z0 <= z <= z1)
    return min(body_scale_at_z(z) for z in samples)


def camera_minimum_body_scale() -> float:
    z0 = camera_body_center_z() - CAMERA_BODY_HEIGHT / 2.0
    z1 = camera_body_center_z() + CAMERA_BODY_HEIGHT / 2.0
    return minimum_body_scale_between(z0, z1)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def set_units() -> None:
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 0.001


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
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=BOOLEAN_CLEANUP_DISTANCE)
    bmesh.ops.dissolve_degenerate(
        bm, edges=list(bm.edges), dist=BOOLEAN_CLEANUP_DISTANCE
    )
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def remove_small_disconnected_shells(
    obj,
    maximum_fragment_faces,
    maximum_fragment_volume,
    maximum_fragment_extent,
    label,
):
    """Delete bounded Boolean remnants while rejecting physical shell splits."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    remaining = set(bm.faces)
    components = []
    while remaining:
        faces = {remaining.pop()}
        stack = list(faces)
        while stack:
            face = stack.pop()
            for edge in face.edges:
                for linked in edge.link_faces:
                    if linked in remaining:
                        remaining.remove(linked)
                        faces.add(linked)
                        stack.append(linked)
        components.append(faces)
    if len(components) <= 1:
        bm.free()
        return 0
    def component_stats(faces):
        vertices = {vertex for face in faces for vertex in face.verts}
        bounds = tuple(
            (
                min(vertex.co[axis] for vertex in vertices),
                max(vertex.co[axis] for vertex in vertices),
            )
            for axis in range(3)
        )
        extents = tuple(high - low for low, high in bounds)
        signed_volume = 0.0
        for face in faces:
            face_vertices = list(face.verts)
            if len(face_vertices) < 3:
                continue
            origin = face_vertices[0].co
            for index in range(1, len(face_vertices) - 1):
                signed_volume += origin.dot(
                    face_vertices[index].co.cross(
                        face_vertices[index + 1].co
                    )
                ) / 6.0
        return {
            "faces": faces,
            "vertices": vertices,
            "bounds": bounds,
            "extents": extents,
            "volume": abs(signed_volume),
        }

    component_records = [component_stats(faces) for faces in components]
    component_records.sort(
        key=lambda record: (
            record["volume"],
            math.prod(record["extents"]),
            len(record["faces"]),
        ),
        reverse=True,
    )
    fragments = component_records[1:]
    oversized = [
        {
            "faces": len(record["faces"]),
            "volume": round(record["volume"], 3),
            "extents": tuple(round(value, 3) for value in record["extents"]),
            "bounds": tuple(
                tuple(round(value, 3) for value in bounds)
                for bounds in record["bounds"]
            ),
        }
        for record in fragments
        if (
            len(record["faces"]) > maximum_fragment_faces
            or record["volume"] > maximum_fragment_volume
            or max(record["extents"]) > maximum_fragment_extent
        )
    ]
    if oversized:
        bm.free()
        raise RuntimeError(
            f"{label} produced oversized disconnected shells: {oversized}"
        )
    fragment_vertices = {
        vertex
        for record in fragments
        for vertex in record["vertices"]
    }
    fragment_descriptions = tuple(
        {
            "faces": len(record["faces"]),
            "volume": round(record["volume"], 3),
            "bounds": tuple(
                tuple(round(value, 3) for value in bounds)
                for bounds in record["bounds"]
            ),
        }
        for record in fragments
    )
    bmesh.ops.delete(bm, geom=list(fragment_vertices), context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    cleanup_mesh(obj)
    recalc_normals(obj)
    print(
        f"BOOLEAN_SMALL_FRAGMENT_REMOVAL {label}: "
        f"fragments={fragment_descriptions}"
    )
    return len(fragments)


def create_mesh_object(name: str, vertices, faces):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(clean_customdata=True)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    recalc_normals(obj)
    return obj


# ---------------------------------------------------------------------------
# Mesh primitives


def superellipse_loop(width: float, depth: float):
    # An egg/limaçon-like loop gives a rounded triangular plan without a sharp
    # apex.  Normalize Y afterward so BODY_DEPTH remains an exact dimension.
    raw_points = []
    for index in range(FOOTPRINT_POINTS):
        angle = 2.0 * math.pi * index / FOOTPRINT_POINTS
        cosine = math.cos(angle)
        sine = math.sin(angle)
        raw_points.append(
            (width / 2.0 * cosine, depth / 2.0 * sine * (1.0 + FOOTPRINT_TRIANGULARITY * cosine))
        )
    maximum_y = max(abs(y) for _, y in raw_points)
    y_scale = (depth / 2.0) / maximum_y
    return [(x, y * y_scale) for x, y in raw_points]


def scale_loop(loop, scale_x: float, scale_y: float = None):
    scale_y = scale_x if scale_y is None else scale_y
    return [(x * scale_x, y * scale_y) for x, y in loop]


def radially_expand_loop(loop, distance: float):
    if distance < 0.0:
        raise ValueError("Radial loop expansion cannot be negative")
    if distance == 0.0:
        return list(loop)
    result = []
    for x, y in loop:
        radius = math.hypot(x, y)
        if radius <= 1e-9:
            raise ValueError("Cannot radially expand a loop vertex at the origin")
        scale = (radius + distance) / radius
        result.append((x * scale, y * scale))
    return result


def inset_footprint_loop(loop, inset: float):
    if inset < 0.0:
        raise ValueError("Footprint inset cannot be negative")
    if inset == 0.0:
        return list(loop)

    def clip_halfplane(polygon, normal, maximum_projection):
        result = []
        previous = polygon[-1]
        previous_projection = previous[0] * normal[0] + previous[1] * normal[1]
        previous_inside = previous_projection <= maximum_projection + 1e-9
        for current in polygon:
            current_projection = current[0] * normal[0] + current[1] * normal[1]
            current_inside = current_projection <= maximum_projection + 1e-9
            if current_inside != previous_inside:
                denominator = current_projection - previous_projection
                fraction = (maximum_projection - previous_projection) / denominator
                result.append(
                    (
                        previous[0] + (current[0] - previous[0]) * fraction,
                        previous[1] + (current[1] - previous[1]) * fraction,
                    )
                )
            if current_inside:
                result.append(current)
            previous = current
            previous_projection = current_projection
            previous_inside = current_inside
        return result

    # Intersect all edge half-planes shifted inward by a constant distance.
    # Unlike a per-corner miter, this automatically drops an acute corner when
    # its two shifted edges would cross beyond the rest of the polygon.
    extent = max(max(abs(x), abs(y)) for x, y in loop) + inset + 1.0
    result = [(-extent, -extent), (extent, -extent), (extent, extent), (-extent, extent)]
    for index, point in enumerate(loop):
        following = loop[(index + 1) % len(loop)]
        edge = (following[0] - point[0], following[1] - point[1])
        length = math.hypot(*edge)
        if length <= 1e-10:
            raise ValueError("Footprint contains duplicate adjacent points")
        inward = (-edge[1] / length, edge[0] / length)
        shifted_projection = point[0] * inward[0] + point[1] * inward[1] + inset
        result = clip_halfplane(
            result,
            (-inward[0], -inward[1]),
            -shifted_projection,
        )
        if len(result) < 3:
            raise ValueError("Footprint inset collapses the configured body")
    result = convex_hull_2d(result)
    return vertex_preserving_resample(result, len(loop))


def convex_hull_2d(points):
    unique = sorted(set((round(x, 9), round(y, 9)) for x, y in points))
    if len(unique) < 3:
        raise ValueError("Convex hull needs at least three unique points")

    def cross(origin, a, b):
        return (a[0] - origin[0]) * (b[1] - origin[1]) - (
            a[1] - origin[1]
        ) * (b[0] - origin[0])

    lower = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0.0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0.0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def clip_convex_polygon_halfplane(loop, normal, maximum_projection: float):
    """Clip a convex CCW loop to dot(point, normal) <= maximum_projection."""
    result = []
    previous = loop[-1]
    previous_projection = previous[0] * normal[0] + previous[1] * normal[1]
    previous_inside = previous_projection <= maximum_projection + 1e-9
    for current in loop:
        current_projection = current[0] * normal[0] + current[1] * normal[1]
        current_inside = current_projection <= maximum_projection + 1e-9
        if current_inside != previous_inside:
            denominator = current_projection - previous_projection
            if abs(denominator) <= 1e-12:
                raise ValueError("Footprint half-plane clip encountered a parallel edge")
            fraction = (maximum_projection - previous_projection) / denominator
            result.append(
                (
                    previous[0] + (current[0] - previous[0]) * fraction,
                    previous[1] + (current[1] - previous[1]) * fraction,
                )
            )
        if current_inside:
            result.append(current)
        previous = current
        previous_projection = current_projection
        previous_inside = current_inside
    if len(result) < 3:
        raise ValueError("Camera face constraints removed the entire body footprint")
    return result


def resample_closed_loop(loop, count: int):
    segment_lengths = []
    perimeter = 0.0
    for index, point in enumerate(loop):
        next_point = loop[(index + 1) % len(loop)]
        length = math.dist(point, next_point)
        segment_lengths.append(length)
        perimeter += length
    result = []
    segment_index = 0
    segment_start = 0.0
    for sample_index in range(count):
        target = perimeter * sample_index / count
        while (
            segment_index < len(loop) - 1
            and segment_start + segment_lengths[segment_index] < target
        ):
            segment_start += segment_lengths[segment_index]
            segment_index += 1
        point = loop[segment_index]
        next_point = loop[(segment_index + 1) % len(loop)]
        length = segment_lengths[segment_index]
        fraction = 0.0 if length <= 1e-12 else (target - segment_start) / length
        result.append(
            (
                point[0] + (next_point[0] - point[0]) * fraction,
                point[1] + (next_point[1] - point[1]) * fraction,
            )
        )
    return result


def vertex_preserving_resample(loop, count: int):
    """Add edge samples while retaining every original polygon vertex."""
    if count < len(loop):
        raise ValueError("Vertex-preserving resample count is smaller than the loop")
    if count == len(loop):
        return list(loop)
    lengths = [
        math.dist(loop[index], loop[(index + 1) % len(loop)])
        for index in range(len(loop))
    ]
    perimeter = sum(lengths)
    extras = count - len(loop)
    exact_allocations = [extras * length / perimeter for length in lengths]
    allocations = [int(value) for value in exact_allocations]
    remainder = extras - sum(allocations)
    ranking = sorted(
        range(len(loop)),
        key=lambda index: (exact_allocations[index] - allocations[index], lengths[index]),
        reverse=True,
    )
    for index in ranking[:remainder]:
        allocations[index] += 1

    result = []
    for index, point in enumerate(loop):
        following = loop[(index + 1) % len(loop)]
        result.append(point)
        for step in range(1, allocations[index] + 1):
            fraction = step / (allocations[index] + 1)
            result.append(
                (
                    point[0] + (following[0] - point[0]) * fraction,
                    point[1] + (following[1] - point[1]) * fraction,
                )
            )
    return result


def rounded_rectangle_loop(width: float, height: float, radius: float):
    radius = min(max(radius, 0.0), width / 2.0, height / 2.0)
    points = []
    corners = (
        (width / 2.0 - radius, height / 2.0 - radius, 0.0, 90.0),
        (-width / 2.0 + radius, height / 2.0 - radius, 90.0, 180.0),
        (-width / 2.0 + radius, -height / 2.0 + radius, 180.0, 270.0),
        (width / 2.0 - radius, -height / 2.0 + radius, 270.0, 360.0),
    )
    for cx, cz, angle0, angle1 in corners:
        for step in range(ROUNDED_CORNER_SEGMENTS):
            angle = math.radians(
                angle0 + (angle1 - angle0) * step / ROUNDED_CORNER_SEGMENTS
            )
            points.append((cx + radius * math.cos(angle), cz + radius * math.sin(angle)))
    return points


def loft_solid(name: str, sections):
    count = len(sections[0][1])
    if len(sections) < 2 or any(len(loop) != count for _, loop in sections):
        raise ValueError("Loft requires at least two equal-length loops")
    vertices = []
    for z, loop in sections:
        vertices.extend((x, y, z) for x, y in loop)

    def vertex(section, index):
        return section * count + index % count

    faces = []
    for section in range(len(sections) - 1):
        for index in range(count):
            faces.append(
                [
                    vertex(section, index),
                    vertex(section, index + 1),
                    vertex(section + 1, index + 1),
                    vertex(section + 1, index),
                ]
            )
    bottom_center = len(vertices)
    vertices.append((0.0, 0.0, sections[0][0]))
    top_center = len(vertices)
    vertices.append((0.0, 0.0, sections[-1][0]))
    last = len(sections) - 1
    for index in range(count):
        faces.append([bottom_center, vertex(0, index + 1), vertex(0, index)])
        faces.append([top_center, vertex(last, index), vertex(last, index + 1)])
    return create_mesh_object(name, vertices, faces)


def hollow_loft_solid(name: str, outer_sections, inner_sections):
    """Build a closed-bottom, open-top shell without a cavity Boolean."""
    outer_count = len(outer_sections[0][1])
    inner_count = len(inner_sections[0][1])
    if (
        len(outer_sections) < 2
        or len(inner_sections) < 2
        or outer_count != inner_count
        or any(len(loop) != outer_count for _, loop in outer_sections)
        or any(len(loop) != inner_count for _, loop in inner_sections)
    ):
        raise ValueError("Hollow loft requires equal-length outer and inner loops")
    if abs(outer_sections[-1][0] - inner_sections[-1][0]) > 1e-9:
        raise ValueError("Hollow loft outer and inner loops must share a top Z")

    vertices = []
    outer_offsets = []
    for z, loop in outer_sections:
        outer_offsets.append(len(vertices))
        vertices.extend((x, y, z) for x, y in loop)
    inner_offsets = []
    for z, loop in inner_sections:
        inner_offsets.append(len(vertices))
        vertices.extend((x, y, z) for x, y in loop)

    faces = []
    for section in range(len(outer_sections) - 1):
        low = outer_offsets[section]
        high = outer_offsets[section + 1]
        for index in range(outer_count):
            next_index = (index + 1) % outer_count
            faces.append(
                [low + index, low + next_index, high + next_index, high + index]
            )
    for section in range(len(inner_sections) - 1):
        low = inner_offsets[section]
        high = inner_offsets[section + 1]
        for index in range(inner_count):
            next_index = (index + 1) % inner_count
            faces.append(
                [low + index, high + index, high + next_index, low + next_index]
            )

    bottom_center = len(vertices)
    vertices.append((0.0, 0.0, outer_sections[0][0]))
    floor_center = len(vertices)
    vertices.append((0.0, 0.0, inner_sections[0][0]))
    outer_bottom = outer_offsets[0]
    inner_bottom = inner_offsets[0]
    outer_top = outer_offsets[-1]
    inner_top = inner_offsets[-1]
    for index in range(outer_count):
        next_index = (index + 1) % outer_count
        faces.append([bottom_center, outer_bottom + next_index, outer_bottom + index])
        faces.append([floor_center, inner_bottom + index, inner_bottom + next_index])
        faces.append(
            [
                outer_top + index,
                outer_top + next_index,
                inner_top + next_index,
                inner_top + index,
            ]
        )
    return create_mesh_object(name, vertices, faces)


def ring_prism(name: str, outer_loop, inner_loop, z0: float, z1: float):
    if len(outer_loop) != len(inner_loop):
        raise ValueError("Ring loops must have equal vertex counts")
    count = len(outer_loop)
    vertices = []
    vertices.extend((x, y, z0) for x, y in outer_loop)
    vertices.extend((x, y, z1) for x, y in outer_loop)
    vertices.extend((x, y, z0) for x, y in inner_loop)
    vertices.extend((x, y, z1) for x, y in inner_loop)
    outer0, outer1, inner0, inner1 = 0, count, count * 2, count * 3
    faces = []
    for index in range(count):
        next_index = (index + 1) % count
        faces.append(
            [outer0 + index, outer0 + next_index, outer1 + next_index, outer1 + index]
        )
        faces.append(
            [inner0 + next_index, inner0 + index, inner1 + index, inner1 + next_index]
        )
        faces.append(
            [outer0 + index, inner0 + index, inner0 + next_index, outer0 + next_index]
        )
        faces.append(
            [outer1 + next_index, inner1 + next_index, inner1 + index, outer1 + index]
        )
    return create_mesh_object(name, vertices, faces)


def lid_with_alignment_lip(name: str, outer_loop, lip_outer_loop, lip_inner_loop):
    """Build the plate and downward locating ring as one manifold mesh."""
    count = len(outer_loop)
    if len(lip_outer_loop) != count or len(lip_inner_loop) != count:
        raise ValueError("Lid and alignment-lip loops must have equal lengths")
    lip_bottom_z = BASE_HEIGHT - LID_LIP_DEPTH
    vertices = []

    def add_loop(loop, z):
        offset = len(vertices)
        vertices.extend((x, y, z) for x, y in loop)
        return offset

    outer_bottom = add_loop(outer_loop, BASE_HEIGHT)
    outer_top = add_loop(outer_loop, BODY_HEIGHT)
    lip_outer_top = add_loop(lip_outer_loop, BASE_HEIGHT)
    lip_outer_bottom = add_loop(lip_outer_loop, lip_bottom_z)
    lip_inner_top = add_loop(lip_inner_loop, BASE_HEIGHT)
    lip_inner_bottom = add_loop(lip_inner_loop, lip_bottom_z)
    top_center = len(vertices)
    vertices.append((0.0, 0.0, BODY_HEIGHT))
    underside_center = len(vertices)
    vertices.append((0.0, 0.0, BASE_HEIGHT))

    faces = []
    for index in range(count):
        next_index = (index + 1) % count
        faces.append(
            [
                outer_bottom + index,
                outer_bottom + next_index,
                outer_top + next_index,
                outer_top + index,
            ]
        )
        faces.append([top_center, outer_top + index, outer_top + next_index])
        faces.append(
            [
                outer_bottom + index,
                lip_outer_top + index,
                lip_outer_top + next_index,
                outer_bottom + next_index,
            ]
        )
        faces.append(
            [
                lip_outer_bottom + index,
                lip_outer_bottom + next_index,
                lip_outer_top + next_index,
                lip_outer_top + index,
            ]
        )
        faces.append(
            [
                lip_inner_bottom + index,
                lip_inner_top + index,
                lip_inner_top + next_index,
                lip_inner_bottom + next_index,
            ]
        )
        faces.append(
            [
                lip_outer_bottom + index,
                lip_inner_bottom + index,
                lip_inner_bottom + next_index,
                lip_outer_bottom + next_index,
            ]
        )
        faces.append(
            [underside_center, lip_inner_top + next_index, lip_inner_top + index]
        )
    return create_mesh_object(name, vertices, faces)


def add_cylinder_z(
    name: str, radius: float, z0: float, z1: float, x: float = 0.0, y: float = 0.0
):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=72,
        radius=radius,
        depth=z1 - z0,
        location=(x, y, (z0 + z1) / 2.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    return obj


def add_hex_prism_z(
    name: str,
    across_flats: float,
    z0: float,
    z1: float,
    x: float = 0.0,
    y: float = 0.0,
    rotation_z: float = 0.0,
):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=6,
        radius=across_flats / math.sqrt(3.0),
        depth=z1 - z0,
        location=(x, y, (z0 + z1) / 2.0),
        rotation=(0.0, 0.0, rotation_z),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    return obj


def add_hex_face_snap_wedge(
    name: str,
    x: float,
    y: float,
    face_angle: float,
    wall_apothem: float,
    projection: float,
    root_embed: float,
    width: float,
    z0: float,
    z1: float,
):
    """Create one inward ramp with a sharp lower retention shoulder."""
    normal = (math.cos(face_angle), math.sin(face_angle))
    tangent = (-normal[1], normal[0])
    root_radius = wall_apothem + root_embed
    inner_radius = wall_apothem - projection
    half_width = width / 2.0

    def point(radius, tangent_offset, z):
        return (
            x + radius * normal[0] + tangent_offset * tangent[0],
            y + radius * normal[1] + tangent_offset * tangent[1],
            z,
        )

    vertices = [
        point(root_radius, -half_width, z0),
        point(root_radius, -half_width, z1),
        point(inner_radius, -half_width, z0),
        point(root_radius, half_width, z0),
        point(root_radius, half_width, z1),
        point(inner_radius, half_width, z0),
    ]
    faces = (
        (0, 2, 1),
        (3, 4, 5),
        (0, 1, 4, 3),
        (0, 3, 5, 2),
        (2, 5, 4, 1),
    )
    return create_mesh_object(name, vertices, faces)


def add_tapered_cylinder_z(
    name: str,
    bottom_radius: float,
    top_radius: float,
    z0: float,
    z1: float,
    x: float = 0.0,
    y: float = 0.0,
):
    bpy.ops.mesh.primitive_cone_add(
        vertices=72,
        radius1=bottom_radius,
        radius2=top_radius,
        depth=z1 - z0,
        location=(x, y, (z0 + z1) / 2.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    return obj


def add_beveled_box(name: str, dimensions, location, rotation_z=0.0, bevel=2.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.rotation_euler.z = rotation_z
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    if bevel > 0.0:
        modifier = obj.modifiers.new(name + "_Bevel", "BEVEL")
        modifier.width = min(bevel, min(dimensions) / 2.1)
        modifier.segments = 3
        modifier.affect = "EDGES"
        select_only(obj)
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    recalc_normals(obj)
    return obj


def body_scale_at_z(z: float) -> float:
    if z <= BODY_SECTIONS[0][0]:
        return BODY_SECTIONS[0][1]
    if z >= BODY_SECTIONS[-1][0]:
        return BODY_SECTIONS[-1][1]
    for (z0, scale0), (z1, scale1) in zip(BODY_SECTIONS, BODY_SECTIONS[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            t = t * t * (3.0 - 2.0 * t)
            return scale0 + (scale1 - scale0) * t
    raise RuntimeError("Could not interpolate body scale")


def radial_surface_distance(
    angle_deg: float, tangent_offset: float = 0.0, footprint_loop=None
) -> float:
    loop = (
        superellipse_loop(BODY_WIDTH, BODY_DEPTH)
        if footprint_loop is None
        else footprint_loop
    )
    angle = math.radians(angle_deg)
    direction = (math.cos(angle), math.sin(angle))
    tangent_axis = (-math.sin(angle), math.cos(angle))
    line_offset = (
        tangent_axis[0] * tangent_offset,
        tangent_axis[1] * tangent_offset,
    )

    def cross(a, b):
        return a[0] * b[1] - a[1] * b[0]

    hits = []
    for index, point in enumerate(loop):
        next_point = loop[(index + 1) % len(loop)]
        edge = (next_point[0] - point[0], next_point[1] - point[1])
        denominator = cross(direction, edge)
        if abs(denominator) < 1e-10:
            continue
        shifted_point = (point[0] - line_offset[0], point[1] - line_offset[1])
        radial = cross(shifted_point, edge) / denominator
        fraction = cross(shifted_point, direction) / denominator
        if radial >= 0.0 and -1e-8 <= fraction <= 1.0 + 1e-8:
            hits.append(radial)
    if not hits:
        raise RuntimeError(f"No footprint intersection at {angle_deg} degrees")
    return min(hits)


def axis_point(angle_deg: float, radial: float, tangent: float, z: float):
    angle = math.radians(angle_deg)
    normal = Vector((math.cos(angle), math.sin(angle), 0.0))
    side = Vector((-math.sin(angle), math.cos(angle), 0.0))
    return normal * radial + side * tangent + Vector((0.0, 0.0, z))


def add_side_locator_gusset(
    name: str,
    angle_deg: float,
    radial_min: float,
    radial_max: float,
    locator_outer_tangent: float,
    side_sign: float,
    z_top: float,
):
    """Add a radial triangular prism that buttresses a locator-to-plate elbow."""
    root_tangent = (
        locator_outer_tangent
        - side_sign * CAMERA_BRACKET_SIDE_LOCATOR_GUSSET_ROOT_EMBED
    )
    outer_tangent = (
        locator_outer_tangent
        + side_sign * CAMERA_BRACKET_SIDE_LOCATOR_GUSSET_REACH
    )
    z_bottom = z_top - CAMERA_BRACKET_SIDE_LOCATOR_GUSSET_DEPTH
    local_vertices = (
        (radial_min, root_tangent, z_bottom),
        (radial_min, root_tangent, z_top),
        (radial_min, outer_tangent, z_top),
        (radial_max, root_tangent, z_bottom),
        (radial_max, root_tangent, z_top),
        (radial_max, outer_tangent, z_top),
    )
    vertices = [
        tuple(axis_point(angle_deg, radial, tangent, z))
        for radial, tangent, z in local_vertices
    ]
    faces = (
        (0, 2, 1),
        (3, 4, 5),
        (0, 3, 5, 2),
        (0, 1, 4, 3),
        (1, 2, 5, 4),
    )
    return create_mesh_object(name, vertices, faces)


def adjustable_camera(cameras):
    """Return the configured moving camera, or None when adjustment is off."""
    if not CAMERA_CARTRIDGE_WORM_ENABLED:
        return None
    for camera in cameras:
        if camera["index"] == ADJUSTABLE_CAMERA_INDEX:
            return camera
    raise ValueError(
        f"ADJUSTABLE_CAMERA_INDEX={ADJUSTABLE_CAMERA_INDEX} is not present"
    )


def camera_is_adjustable(camera) -> bool:
    return (
        CAMERA_CARTRIDGE_WORM_ENABLED
        and camera["index"] == ADJUSTABLE_CAMERA_INDEX
    )


def adjustable_mechanism_hand(camera) -> float:
    """Return +1 on the default side and -1 across the camera centerline."""
    if not ADJUSTABLE_CAMERA_MIRROR_MECHANISM_BY_SIDE:
        return 1.0
    delta = (
        camera["angle"] - CAMERA_CENTERLINE_AZIMUTH_DEG + 180.0
    ) % 360.0 - 180.0
    return 1.0 if delta >= 0.0 else -1.0


def adjustable_camera_pivot_tangential(camera) -> float:
    return ADJUSTABLE_CAMERA_PIVOT_TANGENTIAL * adjustable_mechanism_hand(
        camera
    )


def adjustable_sector_local_angles(camera):
    hand = adjustable_mechanism_hand(camera)
    mirrored_offset = (
        CAMERA_GEAR_MIRRORED_ANGLE_OFFSET_DEG if hand < 0.0 else 0.0
    )
    sector_bounds = sorted(
        (
            hand * CAMERA_GEAR_SECTOR_START_DEG + mirrored_offset,
            hand * CAMERA_GEAR_SECTOR_END_DEG + mirrored_offset,
        )
    )
    return (
        sector_bounds[0],
        sector_bounds[1],
        hand * CAMERA_GEAR_CONTACT_DEG + mirrored_offset,
    )


def adjustable_yaw_samples(include_preview=False):
    """Inclusive mechanical-range samples used by all swept keepout checks."""
    if not CAMERA_CARTRIDGE_WORM_ENABLED:
        return (0.0,)
    limit = ADJUSTABLE_CAMERA_YAW_RANGE_DEG
    step = ADJUSTABLE_CAMERA_SWEEP_STEP_DEG
    count = max(1, int(math.ceil(2.0 * limit / step)))
    values = [
        -limit + 2.0 * limit * index / count
        for index in range(count + 1)
    ]
    # Always retain the nominal pose even when a deliberately coarse step
    # would otherwise produce only the two endpoints.
    values.append(0.0)
    if include_preview:
        values.append(ADJUSTABLE_CAMERA_PREVIEW_YAW_DEG)
    return tuple(sorted(set(round(value, 9) for value in values)))


def adjustable_worm_rotation_degrees(mechanism, yaw_delta):
    """Return worm rotation matching the mirrored sector's physical hand."""
    mesh_tangent = Vector(
        (-mechanism["gear_direction"].y, mechanism["gear_direction"].x, 0.0)
    )
    shaft_alignment = mechanism["shaft_direction"].dot(mesh_tangent)
    return (
        -yaw_delta
        * CAMERA_GEAR_EQUIVALENT_TEETH
        / CAMERA_WORM_STARTS
        * shaft_alignment
        * adjustable_mechanism_hand(mechanism["camera"])
    )


def adjustable_camera_pivot(camera):
    lens_face_radius = camera["radial"] + CAMERA_BODY_DEPTH / 2.0
    pivot_tangent = adjustable_camera_pivot_tangential(camera)
    return axis_point(
        camera["angle"],
        lens_face_radius + ADJUSTABLE_CAMERA_PIVOT_RADIAL,
        camera["eye_tangent"] + pivot_tangent,
        0.0,
    )


def adjustable_camera_local_point(camera, radial, tangent, z, yaw_delta=0.0):
    """Place a canonical lens-centered point after yawing about the floor pin."""
    pivot = adjustable_camera_pivot(camera)
    angle = math.radians(camera["angle"] + yaw_delta)
    relative_radial = radial - ADJUSTABLE_CAMERA_PIVOT_RADIAL
    relative_tangent = tangent - adjustable_camera_pivot_tangential(camera)
    return Vector(
        (
            pivot.x
            + math.cos(angle) * relative_radial
            - math.sin(angle) * relative_tangent,
            pivot.y
            + math.sin(angle) * relative_radial
            + math.cos(angle) * relative_tangent,
            z,
        )
    )


def adjustable_camera_pose_corners(
    camera,
    radial_bounds,
    tangent_bounds,
    yaw_delta,
    clearance=0.0,
):
    return [
        tuple(
            adjustable_camera_local_point(
                camera,
                radial,
                tangent,
                0.0,
                yaw_delta,
            )[:2]
        )
        for radial in (
            radial_bounds[0] - clearance,
            radial_bounds[1] + clearance,
        )
        for tangent in (
            tangent_bounds[0] - clearance,
            tangent_bounds[1] + clearance,
        )
    ]


def camera_sector_pitch_radius() -> float:
    return CAMERA_GEAR_MODULE * CAMERA_GEAR_EQUIVALENT_TEETH / 2.0


def camera_sector_root_radius() -> float:
    return camera_sector_pitch_radius() - 1.25 * CAMERA_GEAR_MODULE


def camera_sector_tip_radius() -> float:
    return camera_sector_pitch_radius() + CAMERA_GEAR_MODULE


def camera_hard_stop_slot_half_width() -> float:
    return (
        CAMERA_HARD_STOP_PIN_DIAMETER
        + CAMERA_HARD_STOP_SLOT_DIAMETRAL_CLEARANCE
    ) / 2.0


def camera_hard_stop_running_clearance_angle_deg() -> float:
    """Angular over-travel from a slot-end center to physical pin contact."""
    radial_clearance = CAMERA_HARD_STOP_SLOT_DIAMETRAL_CLEARANCE / 2.0
    return math.degrees(
        2.0
        * math.asin(
            min(
                radial_clearance / (2.0 * CAMERA_HARD_STOP_SLOT_RADIUS),
                0.99,
            )
        )
    )


def camera_hard_stop_slot_center_limit_deg(physical_limit_deg) -> float:
    """Convert a requested physical stop angle to the arc endpoint angle."""
    return physical_limit_deg - camera_hard_stop_running_clearance_angle_deg()


def camera_hard_stop_remaining_travel(physical_limit_deg, yaw_limit_deg) -> float:
    """Chord travel remaining before the pin physically contacts an end cap."""
    separation = max(physical_limit_deg - yaw_limit_deg, 0.0)
    return (
        2.0
        * CAMERA_HARD_STOP_SLOT_RADIUS
        * math.sin(math.radians(separation) / 2.0)
    )


def camera_hard_stop_reinforcement_radii():
    pivot_bore_radius = (
        CAMERA_CARRIER_PIVOT_PIN_DIAMETER + CAMERA_CARRIER_PIVOT_CLEARANCE
    ) / 2.0
    return (
        pivot_bore_radius + CAMERA_HARD_STOP_SLOT_PIVOT_WEB,
        CAMERA_HARD_STOP_SLOT_RADIUS
        + camera_hard_stop_slot_half_width()
        + CAMERA_HARD_STOP_SLOT_REINFORCEMENT_WIDTH,
    )


def camera_hard_stop_reinforcement_angular_margin_deg() -> float:
    radial_half_width = (
        camera_hard_stop_slot_half_width()
        + CAMERA_HARD_STOP_SLOT_REINFORCEMENT_WIDTH
    )
    return math.degrees(
        math.asin(min(radial_half_width / CAMERA_HARD_STOP_SLOT_RADIUS, 0.99))
    )


def camera_hard_stop_reinforcement_plan_area() -> float:
    inner_radius, outer_radius = camera_hard_stop_reinforcement_radii()
    maximum_limit = (
        CAMERA_HARD_STOP_LIMIT_DEG
        + CAMERA_HARD_STOP_MIRRORED_EXTRA_LIMIT_DEG
    )
    angle = math.radians(
        2.0
        * (
            maximum_limit
            + camera_hard_stop_reinforcement_angular_margin_deg()
        )
    )
    return 0.5 * (outer_radius**2 - inner_radius**2) * angle


def adjustable_hard_stop_geometry(camera):
    """Return the under-camera pin and reinforced arcuate-slot geometry."""
    hard_stop_limit = CAMERA_HARD_STOP_LIMIT_DEG
    if adjustable_mechanism_hand(camera) < 0.0:
        hard_stop_limit += CAMERA_HARD_STOP_MIRRORED_EXTRA_LIMIT_DEG
    slot_center_limit = camera_hard_stop_slot_center_limit_deg(
        hard_stop_limit
    )
    pivot = adjustable_camera_pivot(camera)
    pin_angle = (
        camera["angle"]
        + CAMERA_HARD_STOP_SLOT_LOCAL_ANGLE_DEG
    )
    pin_angle_radians = math.radians(pin_angle)
    pin_position = (
        pivot.x + CAMERA_HARD_STOP_SLOT_RADIUS * math.cos(pin_angle_radians),
        pivot.y + CAMERA_HARD_STOP_SLOT_RADIUS * math.sin(pin_angle_radians),
    )
    return {
        "hard_stop_limit_deg": hard_stop_limit,
        "slot_center_limit_deg": slot_center_limit,
        "pin_angle_deg": pin_angle,
        "pin_position": pin_position,
        "slot_start_deg": pin_angle - slot_center_limit,
        "slot_end_deg": pin_angle + slot_center_limit,
    }


def camera_worm_pitch_radius() -> float:
    return CAMERA_WORM_DIAMETER_QUOTIENT * CAMERA_GEAR_MODULE / 2.0


def camera_worm_outer_radius() -> float:
    return (
        CAMERA_WORM_DIAMETER_QUOTIENT + 2.0
    ) * CAMERA_GEAR_MODULE / 2.0


def camera_worm_root_radius() -> float:
    return max(
        camera_worm_pitch_radius() - 1.2 * CAMERA_GEAR_MODULE,
        CAMERA_WORM_SHAFT_DIAMETER / 2.0 + 1.0,
    )


def ray_polygon_hit(origin, direction, loop):
    """Nearest nonnegative intersection of a ray and a closed polygon."""
    def cross(first, second):
        return first[0] * second[1] - first[1] * second[0]

    hits = []
    for index, point in enumerate(loop):
        next_point = loop[(index + 1) % len(loop)]
        edge = (next_point[0] - point[0], next_point[1] - point[1])
        denominator = cross(direction, edge)
        if abs(denominator) < 1e-10:
            continue
        shifted = (point[0] - origin[0], point[1] - origin[1])
        distance = cross(shifted, edge) / denominator
        fraction = cross(shifted, direction) / denominator
        if distance >= 0.0 and -1e-8 <= fraction <= 1.0 + 1e-8:
            hits.append(distance)
    if not hits:
        raise RuntimeError("Worm shaft ray does not intersect the body footprint")
    return min(hits)


def adjustable_mechanism_layout(cameras, footprint):
    """Resolve the pivot, gear mesh, bearings, wall port, and hard stops."""
    camera = adjustable_camera(cameras)
    if camera is None:
        return None
    pivot = adjustable_camera_pivot(camera)
    sector_start, sector_end, sector_contact = (
        adjustable_sector_local_angles(camera)
    )
    contact_angle_deg = camera["angle"] + sector_contact
    contact_angle = math.radians(contact_angle_deg)
    gear_direction = Vector(
        (math.cos(contact_angle), math.sin(contact_angle), 0.0)
    )
    center_distance = (
        camera_sector_pitch_radius()
        + camera_worm_pitch_radius()
        + CAMERA_GEAR_MESH_CENTER_CLEARANCE
    )
    worm_center = pivot + gear_direction * center_distance
    tangent = Vector((-gear_direction.y, gear_direction.x, 0.0))
    wall_loop = scale_loop(
        footprint,
        body_scale_at_z(
            BOTTOM_THICKNESS
            + CAMERA_WORM_FLOOR_CLEARANCE
            + camera_worm_outer_radius()
        ),
    )
    forward_distance = ray_polygon_hit(
        (worm_center.x, worm_center.y),
        (tangent.x, tangent.y),
        wall_loop,
    )
    backward_distance = ray_polygon_hit(
        (worm_center.x, worm_center.y),
        (-tangent.x, -tangent.y),
        wall_loop,
    )
    if forward_distance <= backward_distance:
        shaft_direction = tangent
        wall_distance = forward_distance
    else:
        shaft_direction = -tangent
        wall_distance = backward_distance
    shaft_angle_deg = math.degrees(
        math.atan2(shaft_direction.y, shaft_direction.x)
    )
    wall_point = worm_center + shaft_direction * wall_distance
    block_offset = (
        CAMERA_WORM_LENGTH / 2.0
        + CAMERA_WORM_BLOCK_OFFSET
        + CAMERA_WORM_BLOCK_LENGTH / 2.0
    )
    outer_block = worm_center + shaft_direction * block_offset
    inner_block = worm_center - shaft_direction * block_offset
    stop_geometry = adjustable_hard_stop_geometry(camera)
    return {
        "camera": camera,
        "pivot": pivot,
        "gear_direction": gear_direction,
        "worm_center": worm_center,
        "shaft_direction": shaft_direction,
        "shaft_angle_deg": shaft_angle_deg,
        "wall_distance": wall_distance,
        "wall_point": wall_point,
        "outer_block": outer_block,
        "inner_block": inner_block,
        "hard_stop_limit_deg": stop_geometry["hard_stop_limit_deg"],
        "hard_stop_slot_center_limit_deg": stop_geometry[
            "slot_center_limit_deg"
        ],
        "hard_stop_pin_angle_deg": stop_geometry["pin_angle_deg"],
        "hard_stop_pin_position": stop_geometry["pin_position"],
        "hard_stop_slot_start_deg": stop_geometry["slot_start_deg"],
        "hard_stop_slot_end_deg": stop_geometry["slot_end_deg"],
    }


def mirror_xy_across_camera_centerline(point):
    """Reflect an XY point across the configured camera centerline."""
    angle = math.radians(CAMERA_CENTERLINE_AZIMUTH_DEG)
    normal = (math.cos(angle), math.sin(angle))
    tangent = (-math.sin(angle), math.cos(angle))
    radial_value = point[0] * normal[0] + point[1] * normal[1]
    tangent_value = point[0] * tangent[0] + point[1] * tangent[1]
    return (
        radial_value * normal[0] - tangent_value * tangent[0],
        radial_value * normal[1] - tangent_value * tangent[1],
    )


def rounded_rectangle_prism_axis(
    name: str,
    angle_deg: float,
    radial0: float,
    radial1: float,
    width: float,
    height: float,
    radius: float,
    center_z: float,
    center_tangent: float = 0.0,
):
    loop = rounded_rectangle_loop(width, height, radius)
    count = len(loop)
    vertices = []
    for radial in (radial0, radial1):
        vertices.extend(
            tuple(
                axis_point(
                    angle_deg,
                    radial,
                    center_tangent + tangent,
                    center_z + local_z,
                )
            )
            for tangent, local_z in loop
        )
    low_center = len(vertices)
    vertices.append(
        tuple(axis_point(angle_deg, radial0, center_tangent, center_z))
    )
    high_center = len(vertices)
    vertices.append(
        tuple(axis_point(angle_deg, radial1, center_tangent, center_z))
    )
    faces = []
    for index in range(count):
        next_index = (index + 1) % count
        faces.append([index, count + index, count + next_index, next_index])
        faces.append([low_center, next_index, index])
        faces.append([high_center, count + index, count + next_index])
    return create_mesh_object(name, vertices, faces)


def rounded_rectangle_flare_shell_axis(
    name: str,
    angle_deg: float,
    radial0: float,
    radial1: float,
    throat_width: float,
    throat_height: float,
    throat_radius: float,
    outer_width: float,
    outer_height: float,
    outer_radius: float,
    center_z: float,
    center_tangent: float = 0.0,
):
    """Create only the material between a straight throat and flared mouth."""
    overlap = BOOLEAN_OVERLAP
    inner_loop = rounded_rectangle_loop(
        throat_width - 2.0 * overlap,
        throat_height - 2.0 * overlap,
        max(throat_radius - overlap, 0.0),
    )
    narrow_outer_loop = rounded_rectangle_loop(
        throat_width + 2.0 * overlap,
        throat_height + 2.0 * overlap,
        throat_radius + overlap,
    )
    wide_outer_loop = rounded_rectangle_loop(
        outer_width,
        outer_height,
        outer_radius,
    )
    if not (
        len(inner_loop)
        == len(narrow_outer_loop)
        == len(wide_outer_loop)
    ):
        raise RuntimeError("Rounded flare-shell loops have mismatched sampling")
    count = len(inner_loop)
    vertices = []
    for radial, loop in (
        (radial0, inner_loop),
        (radial0, narrow_outer_loop),
        (radial1, inner_loop),
        (radial1, wide_outer_loop),
    ):
        vertices.extend(
            tuple(
                axis_point(
                    angle_deg,
                    radial,
                    center_tangent + tangent,
                    center_z + local_z,
                )
            )
            for tangent, local_z in loop
        )
    inner0, outer0, inner1, outer1 = 0, count, 2 * count, 3 * count
    faces = []
    for index in range(count):
        next_index = (index + 1) % count
        faces.append(
            [
                outer0 + index,
                outer0 + next_index,
                outer1 + next_index,
                outer1 + index,
            ]
        )
        faces.append(
            [
                inner0 + next_index,
                inner0 + index,
                inner1 + index,
                inner1 + next_index,
            ]
        )
        faces.append(
            [
                inner0 + index,
                inner0 + next_index,
                outer0 + next_index,
                outer0 + index,
            ]
        )
        faces.append(
            [
                inner1 + next_index,
                inner1 + index,
                outer1 + index,
                outer1 + next_index,
            ]
        )
    return create_mesh_object(name, vertices, faces)


def eye_axis_box(
    name: str,
    camera,
    radial_bounds,
    tangent_width: float,
    z0: float,
    z1: float,
    bevel: float = 0.0,
):
    center = axis_point(
        camera["angle"],
        sum(radial_bounds) / 2.0,
        camera["eye_tangent"],
        (z0 + z1) / 2.0,
    )
    return add_beveled_box(
        name,
        (
            radial_bounds[1] - radial_bounds[0],
            tangent_width,
            z1 - z0,
        ),
        tuple(center),
        rotation_z=math.radians(camera["angle"]),
        bevel=bevel,
    )


def cylinder_prism_axis(
    name: str,
    angle_deg: float,
    radial0: float,
    radial1: float,
    radius: float,
    center_tangent: float,
    center_z: float,
    segments: int = 72,
):
    vertices = []
    for radial in (radial0, radial1):
        for index in range(segments):
            angle = 2.0 * math.pi * index / segments
            vertices.append(
                tuple(
                    axis_point(
                        angle_deg,
                        radial,
                        center_tangent + radius * math.cos(angle),
                        center_z + radius * math.sin(angle),
                    )
                )
            )
    low_center = len(vertices)
    vertices.append(
        tuple(axis_point(angle_deg, radial0, center_tangent, center_z))
    )
    high_center = len(vertices)
    vertices.append(
        tuple(axis_point(angle_deg, radial1, center_tangent, center_z))
    )
    faces = []
    for index in range(segments):
        next_index = (index + 1) % segments
        faces.append(
            [index, segments + index, segments + next_index, next_index]
        )
        faces.append([low_center, next_index, index])
        faces.append(
            [high_center, segments + index, segments + next_index]
        )
    return create_mesh_object(name, vertices, faces)


def rear_fan_center_tangents():
    if REAR_FAN_CENTER_TANGENTS is not None:
        return tuple(float(value) for value in REAR_FAN_CENTER_TANGENTS)
    if REAR_FAN_CENTERLINE_OFFSET is None:
        offset = (REAR_FAN_PAD_SIZE + REAR_FAN_PAD_GAP) / 2.0
    else:
        offset = float(REAR_FAN_CENTERLINE_OFFSET)
    return (-offset, offset)


def rear_fan_wall_normal_angle_deg(footprint, centerline_offset: float) -> float:
    """Return the rear wall's outward XY normal at a global-Y station."""
    if not REAR_FAN_ALIGN_TO_LOCAL_WALL:
        return 0.0
    sample = REAR_FAN_WALL_ANGLE_SAMPLE_DISTANCE
    x_low = radial_surface_distance(
        0.0,
        centerline_offset - sample,
        footprint,
    )
    x_high = radial_surface_distance(
        0.0,
        centerline_offset + sample,
        footprint,
    )
    dx_dy = (x_high - x_low) / (2.0 * sample)
    return math.degrees(math.atan2(-dx_dy, 1.0))


def rear_fan_station_geometry(footprint, center_tangent: float):
    """Resolve the exact flat mounting plane at one curved rear-wall station."""
    half_size = REAR_FAN_PAD_SIZE / 2.0
    count = REAR_FAN_PAD_SURFACE_SAMPLES
    wall_angle_deg = rear_fan_wall_normal_angle_deg(
        footprint,
        center_tangent,
    )
    wall_angle = math.radians(wall_angle_deg)
    wall_tangent = (-math.sin(wall_angle), math.cos(wall_angle))
    center_surface = (
        radial_surface_distance(0.0, center_tangent, footprint),
        center_tangent,
    )
    center_axis_tangent = (
        center_surface[0] * wall_tangent[0]
        + center_surface[1] * wall_tangent[1]
    )
    tangents = [
        center_axis_tangent
        - half_size
        + REAR_FAN_PAD_SIZE * index / count
        for index in range(count + 1)
    ]
    outer_surfaces = [
        radial_surface_distance(wall_angle_deg, tangent, footprint)
        for tangent in tangents
    ]
    if REAR_FAN_PAD_INSIDE:
        inner_footprint = inset_footprint_loop(
            footprint,
            BODY_WALL_THICKNESS,
        )
        wall_surfaces = [
            radial_surface_distance(
                wall_angle_deg,
                tangent,
                inner_footprint,
            )
            for tangent in tangents
        ]
        backing_surfaces = [
            surface + BOOLEAN_OVERLAP for surface in wall_surfaces
        ]
        face_radius = min(wall_surfaces) - REAR_FAN_PAD_FACE_OUTSET
    else:
        wall_surfaces = outer_surfaces
        backing_surfaces = [
            surface - BOOLEAN_OVERLAP for surface in wall_surfaces
        ]
        face_radius = max(wall_surfaces) + REAR_FAN_PAD_FACE_OUTSET
    face_center = axis_point(
        wall_angle_deg,
        face_radius,
        center_axis_tangent,
        REAR_FAN_CENTER_Z,
    )
    return {
        "wall_angle_deg": wall_angle_deg,
        "center_axis_tangent": center_axis_tangent,
        "tangents": tangents,
        "outer_surfaces": outer_surfaces,
        "wall_surfaces": wall_surfaces,
        "backing_surfaces": backing_surfaces,
        "face_radius": face_radius,
        "face_center": face_center,
    }


def curved_backed_flat_pad(name: str, footprint, center_tangent: float):
    half_size = REAR_FAN_PAD_SIZE / 2.0
    count = REAR_FAN_PAD_SURFACE_SAMPLES
    station = rear_fan_station_geometry(footprint, center_tangent)
    wall_angle_deg = station["wall_angle_deg"]
    center_axis_tangent = station["center_axis_tangent"]
    tangents = station["tangents"]
    outer_surfaces = station["outer_surfaces"]
    wall_surfaces = station["wall_surfaces"]
    backing_surfaces = station["backing_surfaces"]
    face_radius = station["face_radius"]
    z0 = REAR_FAN_CENTER_Z - half_size
    z1 = REAR_FAN_CENTER_Z + half_size
    vertices = []
    for tangent, backing_surface in zip(tangents, backing_surfaces):
        vertices.extend(
            (
                tuple(
                    axis_point(
                        wall_angle_deg,
                        backing_surface,
                        tangent,
                        z0,
                    )
                ),
                tuple(
                    axis_point(
                        wall_angle_deg,
                        backing_surface,
                        tangent,
                        z1,
                    )
                ),
                tuple(axis_point(wall_angle_deg, face_radius, tangent, z0)),
                tuple(axis_point(wall_angle_deg, face_radius, tangent, z1)),
            )
        )
    faces = []
    for index in range(count):
        current = index * 4
        following = (index + 1) * 4
        faces.extend(
            (
                [current, following, following + 1, current + 1],
                [current + 2, current + 3, following + 3, following + 2],
                [current, current + 2, following + 2, following],
                [current + 1, following + 1, following + 3, current + 3],
            )
        )
    last = count * 4
    faces.append([0, 1, 3, 2])
    faces.append([last, last + 2, last + 3, last + 1])
    obj = create_mesh_object(name, vertices, faces)
    obj["fan_face_radius"] = face_radius
    obj["fan_min_surface_radius"] = min(outer_surfaces)
    obj["fan_max_surface_radius"] = max(outer_surfaces)
    obj["fan_min_wall_surface_radius"] = min(wall_surfaces)
    obj["fan_max_wall_surface_radius"] = max(wall_surfaces)
    obj["fan_face_angle_deg"] = wall_angle_deg
    obj["fan_center_axis_tangent"] = center_axis_tangent
    obj["fan_centerline_offset"] = center_tangent
    obj["fan_pad_inside"] = REAR_FAN_PAD_INSIDE
    face_center = station["face_center"]
    obj["fan_face_center_x"] = face_center.x
    obj["fan_face_center_y"] = face_center.y
    return obj


def visor_wedge(
    name: str,
    angle_deg: float,
    surface_radius: float,
    center_tangent: float = 0.0,
):
    radial_back = surface_radius - resolved_visor_back_inset()
    radial_front = surface_radius + VISOR_PROJECTION
    back_half = VISOR_BACK_WIDTH / 2.0
    front_half = VISOR_FRONT_WIDTH / 2.0
    local_vertices = (
        (radial_back, -back_half, resolved_visor_z(VISOR_BACK_BOTTOM_Z)),
        (radial_back, back_half, resolved_visor_z(VISOR_BACK_BOTTOM_Z)),
        (radial_back, back_half, resolved_visor_z(VISOR_BACK_TOP_Z)),
        (radial_back, -back_half, resolved_visor_z(VISOR_BACK_TOP_Z)),
        (radial_front, -front_half, resolved_visor_z(VISOR_FRONT_BOTTOM_Z)),
        (radial_front, front_half, resolved_visor_z(VISOR_FRONT_BOTTOM_Z)),
        (radial_front, front_half, resolved_visor_z(VISOR_FRONT_TOP_Z)),
        (radial_front, -front_half, resolved_visor_z(VISOR_FRONT_TOP_Z)),
    )
    vertices = [
        tuple(axis_point(angle_deg, radial, center_tangent + tangent, z))
        for radial, tangent, z in local_vertices
    ]
    faces = (
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
    )
    obj = create_mesh_object(name, vertices, faces)
    modifier = obj.modifiers.new(name + "_Soft_Edges", "BEVEL")
    modifier.width = VISOR_EDGE_RADIUS
    modifier.segments = 4
    modifier.affect = "EDGES"
    select_only(obj)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    recalc_normals(obj)
    return obj


# ---------------------------------------------------------------------------
# Camera keepouts and automatic fastener-post placement


def point_in_polygon(point, loop) -> bool:
    x, y = point
    inside = False
    for index, (x0, y0) in enumerate(loop):
        x1, y1 = loop[(index + 1) % len(loop)]
        if (y0 > y) != (y1 > y):
            crossing_x = (x1 - x0) * (y - y0) / (y1 - y0) + x0
            if x < crossing_x:
                inside = not inside
    return inside


def point_segment_distance(point, start, end) -> float:
    px, py = point
    x0, y0 = start
    x1, y1 = end
    dx, dy = x1 - x0, y1 - y0
    length_squared = dx * dx + dy * dy
    if length_squared <= 1e-12:
        return math.hypot(px - x0, py - y0)
    fraction = ((px - x0) * dx + (py - y0) * dy) / length_squared
    fraction = min(max(fraction, 0.0), 1.0)
    return math.hypot(px - (x0 + fraction * dx), py - (y0 + fraction * dy))


def polygon_boundary_distance(point, loop) -> float:
    return min(
        point_segment_distance(point, loop[index], loop[(index + 1) % len(loop)])
        for index in range(len(loop))
    )


def circular_feature_intersects_plan_loop(
    position,
    feature_radius: float,
    loop,
    clearance: float = 0.0,
) -> bool:
    """Conservatively test a circular post/boss against a plan-view loop."""
    total_radius = feature_radius + clearance
    return point_in_polygon(position, loop) or (
        polygon_boundary_distance(position, loop) < total_radius
    )


def camera_xy_corners(camera, clearance=0.0):
    half_depth = CAMERA_BODY_DEPTH / 2.0 + clearance
    half_width = CAMERA_BODY_WIDTH / 2.0 + clearance
    return [
        tuple(
            axis_point(
                camera["angle"],
                camera["radial"] + radial_sign * half_depth,
                camera["tangent"] + tangent_sign * half_width,
                0.0,
            )[:2]
        )
        for radial_sign in (-1.0, 1.0)
        for tangent_sign in (-1.0, 1.0)
    ]


def camera_envelope_xy_corners_at_yaw(camera, yaw_delta, clearance=0.0):
    if not camera_is_adjustable(camera):
        return camera_xy_corners(camera, clearance)
    return adjustable_camera_pose_corners(
        camera,
        (
            mission1.CANONICAL_RADIAL_MIN,
            mission1.CANONICAL_RADIAL_MAX,
        ),
        mission1.canonical_tangential_bounds(CAMERA_UPSIDE_DOWN),
        yaw_delta,
        clearance,
    )


def camera_usb_access_xy_corners(camera, yaw_delta=0.0, clearance=0.0):
    radial_bounds, tangent_bounds, _ = camera_usb_local_access_bounds()
    radial_bounds = (
        radial_bounds[0] - clearance,
        radial_bounds[1] + clearance,
    )
    tangent_bounds = (
        tangent_bounds[0] - clearance,
        tangent_bounds[1] + clearance,
    )
    if camera_is_adjustable(camera):
        return adjustable_camera_pose_corners(
            camera,
            radial_bounds,
            tangent_bounds,
            yaw_delta,
        )
    lens_face_radius = camera["radial"] + CAMERA_BODY_DEPTH / 2.0
    return [
        tuple(
            axis_point(
                camera["angle"],
                lens_face_radius + radial,
                camera["eye_tangent"] + tangent,
                0.0,
            )[:2]
        )
        for radial in radial_bounds
        for tangent in tangent_bounds
    ]


def adjustable_carrier_plan_points(camera, yaw_delta, clearance=0.0):
    """Conservative tray, gear-sector, and stop-web outline at one yaw."""
    body_radial, body_tangent, _ = mission1.canonical_body_bounds(
        CAMERA_UPSIDE_DOWN
    )
    tray_radial = (
        body_radial[0] - CAMERA_CARRIER_TRAY_RADIAL_MARGIN,
        body_radial[1] + CAMERA_CARRIER_TRAY_RADIAL_MARGIN,
    )
    tray_tangent = (
        body_tangent[0] - CAMERA_CARRIER_TRAY_TANGENTIAL_MARGIN,
        body_tangent[1] + CAMERA_CARRIER_TRAY_TANGENTIAL_MARGIN,
    )
    points = list(
        adjustable_camera_pose_corners(
            camera,
            tray_radial,
            tray_tangent,
            yaw_delta,
            clearance,
        )
    )
    pivot = adjustable_camera_pivot(camera)
    sector_start, sector_end, _ = adjustable_sector_local_angles(camera)
    sector_span = sector_end - sector_start
    sector_samples = max(12, int(math.ceil(abs(sector_span) / 3.0)))
    sector_radius = camera_sector_tip_radius() + clearance
    for index in range(sector_samples + 1):
        local_angle = sector_start + sector_span * index / sector_samples
        angle = math.radians(camera["angle"] + yaw_delta + local_angle)
        points.append(
            (
                pivot.x + sector_radius * math.cos(angle),
                pivot.y + sector_radius * math.sin(angle),
            )
        )
    stop_radius = camera_hard_stop_reinforcement_radii()[1] + clearance
    for index in range(24):
        angle = 2.0 * math.pi * index / 24.0
        points.append(
            (
                pivot.x + stop_radius * math.cos(angle),
                pivot.y + stop_radius * math.sin(angle),
            )
        )
    return points


def adjustable_mechanism_intersects_post(
    position,
    post_radius: float,
    camera,
    mechanism,
) -> bool:
    """Reserve the full carrier sweep and stationary worm hardware for posts."""
    clearance = CAMERA_BRACKET_LID_POST_CLEARANCE
    carrier_loops = mechanism.get("post_carrier_sweep_loops")
    if carrier_loops is None:
        carrier_loops = tuple(
            convex_hull_2d(
                adjustable_carrier_plan_points(camera, yaw_delta)
            )
            for yaw_delta in adjustable_yaw_samples(include_preview=True)
        )
        mechanism["post_carrier_sweep_loops"] = carrier_loops
    for carrier_loop in carrier_loops:
        if circular_feature_intersects_plan_loop(
            position,
            post_radius,
            carrier_loop,
            clearance,
        ):
            return True

    shaft_direction = mechanism["shaft_direction"]
    worm_center = mechanism["worm_center"]
    worm_half_length = CAMERA_WORM_LENGTH / 2.0
    worm_start = (
        worm_center.x - shaft_direction.x * worm_half_length,
        worm_center.y - shaft_direction.y * worm_half_length,
    )
    worm_end = (
        worm_center.x + shaft_direction.x * worm_half_length,
        worm_center.y + shaft_direction.y * worm_half_length,
    )
    if point_segment_distance(position, worm_start, worm_end) < (
        post_radius + camera_worm_outer_radius() + clearance
    ):
        return True

    # A post added after the mechanism Booleans must not refill the shaft
    # passage or either bearing pocket.  Reserve the complete driven shaft run
    # plus the actual bearing-block footprints used to support it.
    inner_block = mechanism["inner_block"]
    wall_point = mechanism["wall_point"]
    shaft_start = (
        inner_block.x
        - shaft_direction.x * CAMERA_WORM_BLOCK_LENGTH / 2.0,
        inner_block.y
        - shaft_direction.y * CAMERA_WORM_BLOCK_LENGTH / 2.0,
    )
    shaft_end = (
        wall_point.x + shaft_direction.x * CAMERA_WORM_PORT_OUTSET,
        wall_point.y + shaft_direction.y * CAMERA_WORM_PORT_OUTSET,
    )
    shaft_radius = max(
        (CAMERA_WORM_SHAFT_DIAMETER + CAMERA_WORM_SHAFT_CLEARANCE) / 2.0,
        (
            CAMERA_WORM_BEARING_OD
            + CAMERA_WORM_BEARING_POCKET_DIAMETER_ADJUSTMENT
        )
        / 2.0,
    )
    if point_segment_distance(position, shaft_start, shaft_end) < (
        post_radius + shaft_radius + clearance
    ):
        return True

    shaft_tangent = (-shaft_direction.y, shaft_direction.x)
    half_length = CAMERA_WORM_BLOCK_LENGTH / 2.0
    half_width = CAMERA_WORM_BLOCK_WIDTH / 2.0
    for block_center in (mechanism["inner_block"], mechanism["outer_block"]):
        block_loop = [
            (
                block_center.x
                + length_sign * half_length * shaft_direction.x
                + width_sign * half_width * shaft_tangent[0],
                block_center.y
                + length_sign * half_length * shaft_direction.y
                + width_sign * half_width * shaft_tangent[1],
            )
            for length_sign, width_sign in (
                (-1.0, -1.0),
                (1.0, -1.0),
                (1.0, 1.0),
                (-1.0, 1.0),
            )
        ]
        if circular_feature_intersects_plan_loop(
            position,
            post_radius,
            block_loop,
            clearance,
        ):
            return True
    return False


def adjustable_carrier_top_loading_chimney_loop(camera):
    """Plan outline removed from the upper base for cartridge installation."""
    body_radial, body_tangent, _ = mission1.canonical_body_bounds(
        CAMERA_UPSIDE_DOWN
    )
    clearance = CAMERA_CARRIER_TOP_LOADING_CHIMNEY_CLEARANCE
    radial_bounds = (
        body_radial[0] - CAMERA_CARRIER_TRAY_RADIAL_MARGIN - clearance,
        body_radial[1] + CAMERA_CARRIER_TRAY_RADIAL_MARGIN + clearance,
    )
    tangent_bounds = (
        body_tangent[0] - CAMERA_CARRIER_TRAY_TANGENTIAL_MARGIN - clearance,
        body_tangent[1] + CAMERA_CARRIER_TRAY_TANGENTIAL_MARGIN + clearance,
    )
    sweep_points = []
    for yaw_delta in adjustable_yaw_samples(include_preview=True):
        sweep_points.extend(
            adjustable_camera_pose_corners(
                camera,
                radial_bounds,
                tangent_bounds,
                yaw_delta,
            )
        )
    return convex_hull_2d(sweep_points), radial_bounds, tangent_bounds


def camera_usb_service_corridors_clear(cameras) -> bool:
    """Keep cameras, carrier, and both plug envelopes clear over full yaw."""
    if not CAMERA_CARTRIDGE_WORM_ENABLED:
        return True
    moving_camera = adjustable_camera(cameras)
    fixed_camera = cameras[1 - cameras.index(moving_camera)]
    clearance = CAMERA_USB_ACCESS_OTHER_CAMERA_CLEARANCE
    fixed_body = convex_hull_2d(
        camera_envelope_xy_corners_at_yaw(
            fixed_camera,
            0.0,
            clearance,
        )
    )
    fixed_usb = None
    if CAMERA_USB_ACCESS_ENABLED:
        fixed_usb = convex_hull_2d(
            camera_usb_access_xy_corners(
                fixed_camera,
                clearance=clearance / 2.0,
            )
        )
    for yaw_delta in adjustable_yaw_samples(include_preview=True):
        moving_body = convex_hull_2d(
            camera_envelope_xy_corners_at_yaw(
                moving_camera,
                yaw_delta,
                clearance,
            )
        )
        carrier = convex_hull_2d(
            adjustable_carrier_plan_points(moving_camera, yaw_delta)
        )
        if convex_polygons_overlap(carrier, fixed_body):
            return False
        if CAMERA_USB_ACCESS_ENABLED:
            moving_usb = convex_hull_2d(
                camera_usb_access_xy_corners(
                    moving_camera,
                    yaw_delta,
                    clearance / 2.0,
                )
            )
            if (
                convex_polygons_overlap(moving_usb, fixed_body)
                or convex_polygons_overlap(fixed_usb, moving_body)
                or convex_polygons_overlap(moving_usb, fixed_usb)
                or convex_polygons_overlap(fixed_usb, carrier)
            ):
                return False
    return True


def camera_installation_sweep_xy_corners(camera, clearance=0.0):
    """Plan-view keepout for vertical loading or the legacy radial slide."""
    if EYE_TOP_LOADING_ENABLED:
        return camera_xy_corners(camera, clearance)
    swept_camera = dict(camera)
    swept_camera["radial"] = (
        camera["radial"] - CAMERA_INSTALLATION_REARWARD_TRAVEL / 2.0
    )
    half_depth = (
        CAMERA_BODY_DEPTH + CAMERA_INSTALLATION_REARWARD_TRAVEL
    ) / 2.0 + clearance
    half_width = CAMERA_BODY_WIDTH / 2.0 + clearance
    return [
        tuple(
            axis_point(
                camera["angle"],
                swept_camera["radial"] + radial_sign * half_depth,
                camera["tangent"] + tangent_sign * half_width,
                0.0,
            )[:2]
        )
        for radial_sign in (-1.0, 1.0)
        for tangent_sign in (-1.0, 1.0)
    ]


def camera_body_xy_corners(camera, clearance=0.0):
    radial_bounds, tangent_bounds, _ = mission1.canonical_body_bounds(
        CAMERA_UPSIDE_DOWN
    )
    lens_face_radius = camera["radial"] + CAMERA_BODY_DEPTH / 2.0
    return [
        tuple(
            axis_point(
                camera["angle"],
                lens_face_radius + radial,
                camera["eye_tangent"] + tangent,
                0.0,
            )[:2]
        )
        for radial in (
            radial_bounds[0] - clearance,
            radial_bounds[1] + clearance,
        )
        for tangent in (
            tangent_bounds[0] - clearance,
            tangent_bounds[1] + clearance,
        )
    ]


def rectangles_overlap(camera_a, camera_b, clearance=0.0) -> bool:
    corners_a = camera_xy_corners(camera_a, clearance / 2.0)
    corners_b = camera_xy_corners(camera_b, clearance / 2.0)
    axes = []
    for camera in (camera_a, camera_b):
        angle = math.radians(camera["angle"])
        axes.extend(((math.cos(angle), math.sin(angle)), (-math.sin(angle), math.cos(angle))))
    for axis in axes:
        projection_a = [x * axis[0] + y * axis[1] for x, y in corners_a]
        projection_b = [x * axis[0] + y * axis[1] for x, y in corners_b]
        if max(projection_a) <= min(projection_b) or max(projection_b) <= min(projection_a):
            return False
    return True


def required_camera_mutual_clearance() -> float:
    clearance = CAMERA_BODY_MUTUAL_CLEARANCE
    if CAMERA_CRADLES_ENABLED:
        guide_overhang = (
            CAMERA_CRADLE_SIDE_CLEARANCE
            + CAMERA_CRADLE_SIDE_GUIDE_THICKNESS
        )
        clearance += 2.0 * guide_overhang
    return clearance


def cameras_at_radius(radius: float):
    cameras = []
    envelope_tangent = camera_envelope_tangential_offset()
    for index, angle in enumerate(camera_azimuths(), start=1):
        center = axis_point(
            angle,
            radius,
            envelope_tangent,
            0.0,
        )
        cameras.append(
            {
                "index": index,
                "angle": angle,
                "radial": radius,
                "tangent": envelope_tangent,
                "eye_tangent": 0.0,
                "center_xy": (center.x, center.y),
            }
        )
    return cameras


def camera_requirements_fit_eye_halfplanes(cameras) -> bool:
    requirement_points = camera_nose_requirement_points(cameras)
    points_per_camera = len(requirement_points) // len(cameras)
    for index, camera in enumerate(cameras):
        angle = math.radians(camera["angle"])
        own_points = requirement_points[
            index * points_per_camera : (index + 1) * points_per_camera
        ]
        for point in own_points:
            projection = point[0] * math.cos(angle) + point[1] * math.sin(angle)
            if projection > camera["required_surface"] + CAMERA_NOSE_CONTACT_TOLERANCE:
                return False
    # Each lens housing is allowed through its own opening, but not through the
    # solid surround belonging to the opposite angled eye.  This constraint is
    # what makes maximum forward placement angle-dependent.
    housing_clearance = CAMERA_LENS_HOUSING_OTHER_EYE_CLEARANCE
    housing_radial = (
        mission1.LENS_SHOULDER_Y - mission1.LENS_FACE_Y - housing_clearance,
        housing_clearance,
    )
    housing_tangent = (
        -mission1.LENS_FACE_WIDTH / 2.0 - housing_clearance,
        mission1.LENS_FACE_WIDTH / 2.0 + housing_clearance,
    )
    for index, camera in enumerate(cameras):
        opposite = cameras[1 - index]
        opposite_angle = math.radians(opposite["angle"])
        lens_face_radius = camera["radial"] + CAMERA_BODY_DEPTH / 2.0
        for radial in housing_radial:
            for tangent in housing_tangent:
                point = axis_point(
                    camera["angle"],
                    lens_face_radius + radial,
                    camera["eye_tangent"] + tangent,
                    0.0,
                )
                projection = (
                    point.x * math.cos(opposite_angle)
                    + point.y * math.sin(opposite_angle)
                )
                if (
                    projection
                    > opposite["required_surface"]
                    + CAMERA_NOSE_CONTACT_TOLERANCE
                ):
                    return False
    # The opposite eye surround is localized rather than a global halfplane.
    # Check the actual rounded main-body outline only where it passes through
    # that solid ring; points far outside the bezel remain in the open cavity.
    body_radial, body_tangent, _ = mission1.canonical_body_bounds(
        CAMERA_UPSIDE_DOWN
    )
    body_radial_center = sum(body_radial) / 2.0
    body_tangent_center = sum(body_tangent) / 2.0
    body_outline = rounded_rectangle_loop(
        mission1.BODY_WIDTH,
        mission1.BODY_DEPTH,
        mission1.BODY_CORNER_RADIUS,
    )
    ring_clearance = CAMERA_OPPOSITE_EYE_SURROUND_CLEARANCE
    ring_tangent_min = EYE_OPENING_WIDTH / 2.0 - ring_clearance
    ring_tangent_max = EYE_BEZEL_WIDTH / 2.0 + ring_clearance
    for index, camera in enumerate(cameras):
        opposite = cameras[1 - index]
        opposite_angle = math.radians(opposite["angle"])
        opposite_normal = (
            math.cos(opposite_angle),
            math.sin(opposite_angle),
        )
        opposite_tangent = (
            -math.sin(opposite_angle),
            math.cos(opposite_angle),
        )
        opposite_inner_wall = (
            opposite["required_surface"]
            - EYE_FACE_INSET
            - EYE_BEZEL_DEPTH
        )
        lens_face_radius = camera["radial"] + CAMERA_BODY_DEPTH / 2.0
        for tangent_delta, radial_delta in body_outline:
            point = axis_point(
                camera["angle"],
                lens_face_radius + body_radial_center + radial_delta,
                camera["eye_tangent"]
                + body_tangent_center
                + tangent_delta,
                0.0,
            )
            tangent_projection = (
                point.x * opposite_tangent[0]
                + point.y * opposite_tangent[1]
            )
            if not (
                ring_tangent_min
                <= abs(tangent_projection)
                <= ring_tangent_max
            ):
                continue
            radial_projection = (
                point.x * opposite_normal[0]
                + point.y * opposite_normal[1]
            )
            if (
                radial_projection
                > opposite_inner_wall
                - ring_clearance
                + CAMERA_NOSE_CONTACT_TOLERANCE
            ):
                return False
    return True


def minimum_nonoverlap_camera_radius() -> float:
    """Keep cameras as close as bodies, guides, and USB service permit."""
    low = 0.0
    high = max(BODY_WIDTH, BODY_DEPTH) + CAMERA_NOSE_MAX_EXPANSION
    high_cameras = cameras_at_radius(high)
    if (
        rectangles_overlap(
            high_cameras[0],
            high_cameras[1],
            required_camera_mutual_clearance(),
        )
        or not camera_usb_service_corridors_clear(high_cameras)
    ):
        raise ValueError(
            "Camera half-angle is too small for the configured MISSION 1 envelope "
            "and cradle/cartridge/USB service keepouts within "
            "CAMERA_NOSE_MAX_EXPANSION"
        )
    for _ in range(64):
        middle = (low + high) / 2.0
        cameras = cameras_at_radius(middle)
        if (
            rectangles_overlap(
                cameras[0],
                cameras[1],
                required_camera_mutual_clearance(),
            )
            or not camera_usb_service_corridors_clear(cameras)
        ):
            low = middle
        else:
            high = middle
    if CAMERA_CARTRIDGE_WORM_ENABLED:
        print(
            "CAMERA_CARTRIDGE_SERVICE_SPACING "
            f"minimum_camera_radius={high:.2f} "
            f"cross_clearance="
            f"{CAMERA_USB_ACCESS_OTHER_CAMERA_CLEARANCE:.2f}"
        )
    return high


def camera_nose_requirement_points(cameras):
    points = []
    shell_clearance = BODY_WALL_THICKNESS + CAMERA_NOSE_SHELL_CLEARANCE
    lens_outset = camera_lens_face_outset()
    minimum_scale = camera_minimum_body_scale()
    for camera in cameras:
        points.extend(
            (x / minimum_scale, y / minimum_scale)
            for x, y in camera_body_xy_corners(camera, shell_clearance)
        )
        required_surface = (
            camera["radial"]
            + CAMERA_BODY_DEPTH / 2.0
            - lens_outset
        )
        camera["required_surface"] = required_surface
        eye_half_width = EYE_BEZEL_WIDTH / 2.0 + CAMERA_NOSE_SHELL_CLEARANCE
        points.append(
            tuple(
                axis_point(
                    camera["angle"], required_surface, -eye_half_width, 0.0
                )[:2]
            )
        )
        points.append(
            tuple(
                axis_point(
                    camera["angle"], required_surface, eye_half_width, 0.0
                )[:2]
            )
        )
    return points


def build_camera_driven_footprint(cameras):
    baseline = convex_hull_2d(superellipse_loop(BODY_WIDTH, BODY_DEPTH))
    if not CAMERA_DRIVEN_NOSE_ENABLED:
        return baseline
    requirement_points = camera_nose_requirement_points(cameras)
    # The camera faces are shape constraints, not merely additions to the
    # original outline.  Clipping the baseline lets large half-angles pull the
    # corresponding sides inward, while small half-angles still broaden the
    # camera-side nose.  The rear of the rounded-triangular baseline survives.
    trimmed_baseline = baseline
    for camera in cameras:
        angle = math.radians(camera["angle"])
        trimmed_baseline = clip_convex_polygon_halfplane(
            trimmed_baseline,
            (math.cos(angle), math.sin(angle)),
            camera["required_surface"],
        )
    points_per_camera = len(requirement_points) // len(cameras)
    for index, camera in enumerate(cameras):
        angle = math.radians(camera["angle"])
        own_points = requirement_points[
            index * points_per_camera : (index + 1) * points_per_camera
        ]
        for point in own_points:
            projection = point[0] * math.cos(angle) + point[1] * math.sin(angle)
            if projection > camera["required_surface"] + CAMERA_NOSE_CONTACT_TOLERANCE:
                raise ValueError(
                    "A camera exceeds its own eye-face/body constraint. Reduce "
                    "eye/bezel width or shell clearance."
                )
    # Keep the actual hull vertices.  Uniform perimeter resampling can bridge
    # across a required corner and silently shave away configured clearance.
    swept_points = []
    moving_camera = adjustable_camera(cameras)
    if moving_camera is not None:
        body_radial, body_tangent, _ = mission1.canonical_body_bounds(
            CAMERA_UPSIDE_DOWN
        )
        sweep_clearance = (
            BODY_WALL_THICKNESS
            + CAMERA_NOSE_SHELL_CLEARANCE
            + ADJUSTABLE_CAMERA_SWEEP_CLEARANCE
        )
        minimum_scale = min(
            camera_minimum_body_scale(),
            body_scale_at_z(
                BOTTOM_THICKNESS + CAMERA_CARRIER_BOTTOM_CLEARANCE
            ),
        )
        for yaw_delta in adjustable_yaw_samples():
            swept_points.extend(
                (x / minimum_scale, y / minimum_scale)
                for x, y in adjustable_camera_pose_corners(
                    moving_camera,
                    body_radial,
                    body_tangent,
                    yaw_delta,
                    sweep_clearance,
                )
            )
        # The outboard printed sector is part of the moving cartridge too.
        # Include its complete yawed tip arc in the camera-driven shell solve;
        # this is especially important when the mechanism is mirrored onto
        # camera 1, where the original Veo outline is tighter on that side.
        sector_start, sector_end, _ = adjustable_sector_local_angles(
            moving_camera
        )
        sector_start += (
            moving_camera["angle"]
            - ADJUSTABLE_CAMERA_YAW_RANGE_DEG
            - 1.0
        )
        sector_end += (
            moving_camera["angle"]
            + ADJUSTABLE_CAMERA_YAW_RANGE_DEG
            + 1.0
        )
        sector_radius = (
            camera_sector_tip_radius()
            + BODY_WALL_THICKNESS
            + ADJUSTABLE_CAMERA_SWEEP_CLEARANCE
        )
        pivot = adjustable_camera_pivot(moving_camera)
        sector_samples = max(
            12,
            int(math.ceil((sector_end - sector_start) / 2.0)),
        )
        for sample_index in range(sector_samples + 1):
            angle = math.radians(
                sector_start
                + (sector_end - sector_start)
                * sample_index
                / sector_samples
            )
            swept_points.append(
                (
                    (
                        pivot.x + sector_radius * math.cos(angle)
                    )
                    / minimum_scale,
                    (
                        pivot.y + sector_radius * math.sin(angle)
                    )
                    / minimum_scale,
                )
            )
        stop_geometry = adjustable_hard_stop_geometry(moving_camera)
        stop_margin = camera_hard_stop_reinforcement_angular_margin_deg()
        stop_sweep_start = (
            stop_geometry["slot_start_deg"]
            - ADJUSTABLE_CAMERA_YAW_RANGE_DEG
            - stop_margin
            - 1.0
        )
        stop_sweep_end = (
            stop_geometry["slot_end_deg"]
            + ADJUSTABLE_CAMERA_YAW_RANGE_DEG
            + stop_margin
            + 1.0
        )
        stop_sweep_radius = (
            camera_hard_stop_reinforcement_radii()[1]
            + BODY_WALL_THICKNESS
            + ADJUSTABLE_CAMERA_SWEEP_CLEARANCE
        )
        stop_samples = max(
            12,
            int(math.ceil((stop_sweep_end - stop_sweep_start) / 2.0)),
        )
        for sample_index in range(stop_samples + 1):
            angle = math.radians(
                stop_sweep_start
                + (stop_sweep_end - stop_sweep_start)
                * sample_index
                / stop_samples
            )
            swept_points.append(
                (
                    (
                        pivot.x + stop_sweep_radius * math.cos(angle)
                    )
                    / minimum_scale,
                    (
                        pivot.y + stop_sweep_radius * math.sin(angle)
                    )
                    / minimum_scale,
                )
            )
    result = convex_hull_2d(
        trimmed_baseline + requirement_points + swept_points
    )
    if FORCE_LAYOUT_SYMMETRY:
        result = convex_hull_2d(
            result
            + [mirror_xy_across_camera_centerline(point) for point in result]
        )
    result = vertex_preserving_resample(
        result,
        max(FOOTPRINT_POINTS, len(result)),
    )
    baseline_width = max(x for x, _ in baseline) - min(x for x, _ in baseline)
    baseline_depth = max(y for _, y in baseline) - min(y for _, y in baseline)
    result_width = max(x for x, _ in result) - min(x for x, _ in result)
    result_depth = max(y for _, y in result) - min(y for _, y in result)
    expansion = max(result_width - baseline_width, result_depth - baseline_depth)
    if expansion > CAMERA_NOSE_MAX_EXPANSION:
        raise ValueError(
            f"Camera-driven nose needs {expansion:.2f} mm expansion, exceeding "
            "CAMERA_NOSE_MAX_EXPANSION"
        )
    return result


def camera_driven_layout_for_outset(lens_outset: float):
    global _RESOLVED_CAMERA_LENS_FACE_OUTSET
    _RESOLVED_CAMERA_LENS_FACE_OUTSET = float(lens_outset)
    cameras = cameras_at_radius(minimum_nonoverlap_camera_radius())
    if not camera_requirements_fit_eye_halfplanes(cameras):
        raise ValueError(
            "Minimum-spacing cameras do not fit the configured eye surrounds "
            "at this lens outset"
        )
    footprint = build_camera_driven_footprint(cameras)
    for camera in cameras:
        raw_surface = radial_surface_distance(camera["angle"], 0.0, footprint)
        surface = camera["required_surface"]
        recess_depth = max(raw_surface - surface, 0.0)
        if recess_depth > EYE_FACE_RECESS_MAX_DEPTH:
            raise ValueError(
                f"Camera {camera['index']} needs {recess_depth:.2f} mm eye-face "
                "recess, exceeding EYE_FACE_RECESS_MAX_DEPTH"
            )
        camera["surface"] = surface
        camera["raw_surface"] = raw_surface
        camera["eye_face_recess_depth"] = recess_depth
        camera["eye_inner_wall"] = (
            surface - EYE_FACE_INSET - EYE_BEZEL_DEPTH
        )
    return cameras, footprint


def resolve_maximized_camera_driven_layout():
    global _RESOLVED_CAMERA_LENS_FACE_OUTSET
    _RESOLVED_CAMERA_LENS_FACE_OUTSET = None
    theoretical_maximum = camera_lens_face_outset()
    minimum = CAMERA_LENS_FACE_MIN_OUTSET

    def attempt(outset):
        try:
            return camera_driven_layout_for_outset(outset)
        except ValueError:
            return None

    minimum_layout = attempt(minimum)
    if minimum_layout is None:
        raise ValueError(
            "No camera-driven shell fits even CAMERA_LENS_FACE_MIN_OUTSET"
        )
    maximum_layout = attempt(theoretical_maximum)
    if maximum_layout is not None:
        resolved = theoretical_maximum
        layout = maximum_layout
    else:
        low = minimum
        high = theoretical_maximum
        layout = minimum_layout
        for _ in range(CAMERA_FORWARD_SOLVE_STEPS):
            middle = (low + high) / 2.0
            candidate = attempt(middle)
            if candidate is None:
                high = middle
            else:
                low = middle
                layout = candidate
        resolved = max(
            minimum,
            low - CAMERA_FORWARD_SOLVE_SAFETY_MARGIN,
        )
        layout = camera_driven_layout_for_outset(resolved)
    _RESOLVED_CAMERA_LENS_FACE_OUTSET = resolved
    print(
        "CAMERA_FORWARD_SOLVE "
        f"theoretical_outset={theoretical_maximum:.2f} "
        f"resolved_outset={resolved:.2f} "
        f"front_stop_projection={camera_front_stop_projection():.2f}"
    )
    return layout


def resolve_camera_layout():
    global _RESOLVED_CAMERA_LENS_FACE_OUTSET
    _RESOLVED_CAMERA_LENS_FACE_OUTSET = None
    if CAMERA_DRIVEN_NOSE_ENABLED:
        if CAMERA_FORWARD_PLACEMENT_MODE == "maximize":
            cameras, footprint = resolve_maximized_camera_driven_layout()
        else:
            cameras, footprint = camera_driven_layout_for_outset(
                CAMERA_LENS_FACE_OUTSET
            )
    else:
        footprint = convex_hull_2d(superellipse_loop(BODY_WIDTH, BODY_DEPTH))
        cameras = []
        envelope_tangent = camera_envelope_tangential_offset()
        lens_outset = camera_lens_face_outset()
        for index, angle in enumerate(camera_azimuths(), start=1):
            surface = radial_surface_distance(angle, 0.0, footprint)
            eye_inner_wall = surface - EYE_FACE_INSET - EYE_BEZEL_DEPTH
            radial = (
                surface
                + lens_outset
                - CAMERA_BODY_DEPTH / 2.0
            )
            center = axis_point(
                angle,
                radial,
                envelope_tangent,
                0.0,
            )
            cameras.append(
                {
                    "index": index,
                    "angle": angle,
                    "radial": radial,
                    "tangent": envelope_tangent,
                    "eye_tangent": 0.0,
                    "surface": surface,
                    "raw_surface": surface,
                    "eye_face_recess_depth": 0.0,
                    "eye_inner_wall": eye_inner_wall,
                    "center_xy": (center.x, center.y),
                }
            )

    inner_loop = inset_footprint_loop(
        scale_loop(footprint, camera_minimum_body_scale()),
        BODY_WALL_THICKNESS,
    )
    if rectangles_overlap(
        cameras[0],
        cameras[1],
        required_camera_mutual_clearance(),
    ):
        raise ValueError("Camera-driven footprint still leaves overlapping camera bodies")
    if not camera_usb_service_corridors_clear(cameras):
        raise ValueError(
            "Camera-driven footprint still obstructs a swept USB service corridor"
        )
    for camera in cameras:
        if not all(
            point_in_polygon(corner, inner_loop)
            for corner in camera_body_xy_corners(camera)
        ):
            raise ValueError(
                f"Camera {camera['index']} is not contained by the solved inner footprint"
            )
        print(
            f"CAMERA_LAYOUT {camera['index']}: center_xy="
            f"({camera['center_xy'][0]:.2f}, {camera['center_xy'][1]:.2f}) "
            f"angle={camera['angle']:.2f} "
            f"envelope_tangent={camera['tangent']:.2f} lens_tangent=0.00 "
            f"lens_outset={camera_lens_face_outset():.2f}"
        )
    baseline = superellipse_loop(BODY_WIDTH, BODY_DEPTH)
    solved_width = max(x for x, _ in footprint) - min(x for x, _ in footprint)
    solved_depth = max(y for _, y in footprint) - min(y for _, y in footprint)
    baseline_width = max(x for x, _ in baseline) - min(x for x, _ in baseline)
    baseline_depth = max(y for _, y in baseline) - min(y for _, y in baseline)
    print(
        f"CAMERA_DRIVEN_FOOTPRINT dimensions=({solved_width:.2f}, {solved_depth:.2f}) "
        f"expansion=({solved_width - baseline_width:.2f}, "
        f"{solved_depth - baseline_depth:.2f})"
    )
    return cameras, footprint


def refresh_camera_eye_recesses(cameras, footprint):
    """Update eye-to-hull depths after bracket/cartridge shell expansion."""
    for camera in cameras:
        raw_surface = radial_surface_distance(
            camera["angle"],
            camera["eye_tangent"],
            footprint,
        )
        recess_depth = max(raw_surface - camera["surface"], 0.0)
        if (
            EYE_FACE_RECESS_ENABLED
            and recess_depth
            > EYE_FACE_RECESS_MAX_DEPTH + CAMERA_NOSE_CONTACT_TOLERANCE
        ):
            raise ValueError(
                f"Camera {camera['index']} needs {recess_depth:.2f} mm "
                "final eye-face recess after shell expansion, exceeding "
                "EYE_FACE_RECESS_MAX_DEPTH"
            )
        camera["raw_surface"] = raw_surface
        camera["eye_face_recess_depth"] = recess_depth


def validate_camera_lens_protrusion(cameras):
    """Keep every lens face ahead of its eye throughout the yaw sweep."""
    expected_nominal = camera_lens_face_outset() + EYE_FACE_INSET
    for camera in cameras:
        eye_angle = math.radians(camera["angle"])
        eye_normal = (math.cos(eye_angle), math.sin(eye_angle))
        eye_face = camera["surface"] - EYE_FACE_INSET
        yaw_samples = (
            adjustable_yaw_samples()
            if camera_is_adjustable(camera)
            else (0.0,)
        )
        protrusions = []
        for yaw_delta in yaw_samples:
            if camera_is_adjustable(camera):
                lens_center = adjustable_camera_local_point(
                    camera,
                    0.0,
                    0.0,
                    camera_eye_center_z(),
                    yaw_delta,
                )
            else:
                lens_center = axis_point(
                    camera["angle"],
                    camera["radial"] + CAMERA_BODY_DEPTH / 2.0,
                    camera["eye_tangent"],
                    camera_eye_center_z(),
                )
            projection = (
                lens_center.x * eye_normal[0]
                + lens_center.y * eye_normal[1]
            )
            protrusions.append((yaw_delta, projection - eye_face))

        nominal = min(
            protrusions,
            key=lambda sample: abs(sample[0]),
        )[1]
        minimum_yaw, minimum = min(
            protrusions,
            key=lambda sample: sample[1],
        )
        maximum_yaw, maximum = max(
            protrusions,
            key=lambda sample: sample[1],
        )
        if abs(nominal - expected_nominal) > 1e-5:
            raise RuntimeError(
                f"Camera {camera['index']} nominal lens placement drifted: "
                f"{nominal:.4f} mm != {expected_nominal:.4f} mm"
            )
        if minimum + 1e-9 < CAMERA_LENS_MIN_SWEEP_EYE_FACE_PROTRUSION:
            raise ValueError(
                f"Camera {camera['index']} lens protrusion falls to "
                f"{minimum:.2f} mm at yaw {minimum_yaw:+.2f} degrees; "
                "reduce ADJUSTABLE_CAMERA_YAW_RANGE_DEG, move the pivot, or "
                "reduce CAMERA_LENS_MIN_SWEEP_EYE_FACE_PROTRUSION"
            )
        raw_hull_protrusion = (
            eye_face + nominal - camera["raw_surface"]
        )
        print(
            f"CAMERA_LENS_PROTRUSION {camera['index']}: "
            f"eye_nominal={nominal:.2f} "
            f"eye_sweep=({minimum:.2f}@{minimum_yaw:+.2f},"
            f"{maximum:.2f}@{maximum_yaw:+.2f}) "
            f"raw_hull_nominal={raw_hull_protrusion:.2f}"
        )


def circular_feature_intersects_camera_installation_sweep(
    position,
    camera,
    feature_radius: float,
    clearance: float,
) -> bool:
    """Conservatively test a round floor feature against the camera slide."""
    if not VALIDATE_CAMERA_INSTALLATION_PATH:
        return False
    if EYE_TOP_LOADING_ENABLED:
        return False
    angle = math.radians(camera["angle"])
    normal = (math.cos(angle), math.sin(angle))
    tangent_axis = (-math.sin(angle), math.cos(angle))
    radial = position[0] * normal[0] + position[1] * normal[1]
    tangent = position[0] * tangent_axis[0] + position[1] * tangent_axis[1]
    total_clearance = clearance + feature_radius
    radial_min = (
        camera["radial"]
        - CAMERA_INSTALLATION_REARWARD_TRAVEL
        - CAMERA_BODY_DEPTH / 2.0
        - total_clearance
    )
    radial_max = (
        camera["radial"] + CAMERA_BODY_DEPTH / 2.0 + total_clearance
    )
    tangent_limit = CAMERA_BODY_WIDTH / 2.0 + total_clearance
    return (
        radial_min < radial < radial_max
        and abs(tangent - camera["tangent"]) < tangent_limit
    )


def camera_bracket_guide_plate_local_bounds(camera):
    """Conservative local plan bounds for the reinforced guide roof."""
    body_radial, body_tangent, _ = mission1.canonical_body_bounds(
        CAMERA_UPSIDE_DOWN
    )
    lens_face_radius = camera["radial"] + CAMERA_BODY_DEPTH / 2.0
    body_back = lens_face_radius + body_radial[0]
    radial_bounds = (
        body_back
        - CAMERA_BRACKET_REAR_CLEARANCE
        - CAMERA_BRACKET_REAR_LIP_THICKNESS
        - CAMERA_BRACKET_GUIDE_PLATE_OVERHANG,
        body_back
        + CAMERA_BRACKET_OVER_CAMERA_DEPTH
        + CAMERA_BRACKET_GUIDE_PLATE_OVERHANG,
    )
    tangent_values = [
        camera["eye_tangent"]
        + body_tangent[0]
        - CAMERA_BRACKET_PRIMARY_TANGENTIAL_MARGIN,
        camera["eye_tangent"]
        + body_tangent[1]
        + CAMERA_BRACKET_PRIMARY_TANGENTIAL_MARGIN,
    ]
    locator_specs = (
        (
            CAMERA_BRACKET_USB_SIDE_LOCATOR_ENABLED,
            camera_usb_side_sign(),
            CAMERA_BRACKET_USB_SIDE_LOCATOR_THICKNESS,
            CAMERA_BRACKET_USB_SIDE_LOCATOR_CLEARANCE,
        ),
        (
            CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_ENABLED,
            -camera_usb_side_sign(),
            CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_THICKNESS,
            CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_CLEARANCE,
        ),
    )
    for enabled, side_sign, thickness, side_clearance in locator_specs:
        if not enabled:
            continue
        body_side = body_tangent[0] if side_sign < 0.0 else body_tangent[1]
        outer_tangent = (
            camera["eye_tangent"]
            + body_side
            + side_sign * (side_clearance + thickness)
        )
        if CAMERA_BRACKET_SIDE_LOCATOR_GUSSETS_ENABLED:
            outer_tangent += (
                side_sign * CAMERA_BRACKET_SIDE_LOCATOR_GUSSET_REACH
            )
        tangent_values.append(outer_tangent)
    return radial_bounds, (
        min(tangent_values) - CAMERA_BRACKET_GUIDE_PLATE_OVERHANG,
        max(tangent_values) + CAMERA_BRACKET_GUIDE_PLATE_OVERHANG,
    )


def circular_feature_intersects_camera_bracket_plate(
    position,
    camera,
    feature_radius: float,
    clearance: float,
) -> bool:
    if not (
        CAMERA_BRACKETS_ENABLED
        and CAMERA_BRACKET_L_CORNER_GUIDES_ENABLED
    ):
        return False
    angle = math.radians(camera["angle"])
    radial = position[0] * math.cos(angle) + position[1] * math.sin(angle)
    tangent = -position[0] * math.sin(angle) + position[1] * math.cos(angle)
    radial_bounds, tangent_bounds = camera_bracket_guide_plate_local_bounds(
        camera
    )
    total_clearance = feature_radius + clearance
    return (
        radial_bounds[0] - total_clearance
        < radial
        < radial_bounds[1] + total_clearance
        and tangent_bounds[0] - total_clearance
        < tangent
        < tangent_bounds[1] + total_clearance
    )


def post_is_valid(
    position,
    cameras,
    inner_loop,
    accepted_positions=(),
    post_diameter=FASTENER_POST_DIAMETER,
    avoid_camera_bracket_plate=False,
    mechanism=None,
) -> bool:
    post_radius = post_diameter / 2.0
    required_edge_distance = post_radius + FASTENER_POST_EDGE_CLEARANCE
    if not point_in_polygon(position, inner_loop):
        return False
    if polygon_boundary_distance(position, inner_loop) < required_edge_distance:
        return False
    minimum_center_spacing = max(
        FASTENER_POST_MIN_CENTER_SPACING,
        post_diameter + FASTENER_POST_EDGE_CLEARANCE,
    )
    for accepted in accepted_positions:
        if math.dist(position, accepted) < minimum_center_spacing:
            return False
    for camera in cameras:
        if CAMERA_USB_ACCESS_ENABLED:
            usb_yaw_samples = (
                adjustable_yaw_samples(include_preview=True)
                if camera_is_adjustable(camera)
                else (0.0,)
            )
            for yaw_delta in usb_yaw_samples:
                usb_loop = convex_hull_2d(
                    camera_usb_access_xy_corners(camera, yaw_delta)
                )
                if (
                    point_in_polygon(position, usb_loop)
                    or polygon_boundary_distance(position, usb_loop)
                    < post_radius + FASTENER_POST_CAMERA_CLEARANCE
                ):
                    return False
        if camera_is_adjustable(camera):
            pivot = adjustable_camera_pivot(camera)
            if mechanism is not None and adjustable_mechanism_intersects_post(
                position,
                post_radius,
                camera,
                mechanism,
            ):
                return False
            if CAMERA_CARRIER_TOP_LOADING_CHIMNEY_ENABLED:
                chimney_loop, _, _ = (
                    adjustable_carrier_top_loading_chimney_loop(camera)
                )
                if (
                    point_in_polygon(position, chimney_loop)
                    or polygon_boundary_distance(position, chimney_loop)
                    < post_radius + CAMERA_BRACKET_LID_POST_CLEARANCE
                ):
                    return False
            if avoid_camera_bracket_plate and math.dist(
                position,
                (pivot.x, pivot.y),
            ) < (
                CAMERA_HOLD_DOWN_CENTER_PLATE_DIAMETER / 2.0
                + post_radius
                + CAMERA_BRACKET_LID_POST_CLEARANCE
            ):
                return False
            envelope_radial = (
                mission1.CANONICAL_RADIAL_MIN,
                mission1.CANONICAL_RADIAL_MAX,
            )
            envelope_tangent = mission1.canonical_tangential_bounds(
                CAMERA_UPSIDE_DOWN
            )
            keepout = FASTENER_POST_CAMERA_CLEARANCE + post_radius
            for yaw_delta in adjustable_yaw_samples():
                pose_angle = math.radians(camera["angle"] + yaw_delta)
                normal = (math.cos(pose_angle), math.sin(pose_angle))
                tangent_axis = (-math.sin(pose_angle), math.cos(pose_angle))
                dx = position[0] - pivot.x
                dy = position[1] - pivot.y
                local_radial = (
                    ADJUSTABLE_CAMERA_PIVOT_RADIAL
                    + dx * normal[0]
                    + dy * normal[1]
                )
                local_tangent = (
                    adjustable_camera_pivot_tangential(camera)
                    + dx * tangent_axis[0]
                    + dy * tangent_axis[1]
                )
                if (
                    envelope_radial[0] - keepout
                    < local_radial
                    < envelope_radial[1] + keepout
                    and envelope_tangent[0] - keepout
                    < local_tangent
                    < envelope_tangent[1] + keepout
                ):
                    return False
            continue
        if (
            avoid_camera_bracket_plate
            and circular_feature_intersects_camera_bracket_plate(
                position,
                camera,
                post_radius,
                CAMERA_BRACKET_LID_POST_CLEARANCE,
            )
        ):
            return False
        if circular_feature_intersects_camera_installation_sweep(
            position,
            camera,
            post_radius,
            CAMERA_INSTALLATION_POST_CLEARANCE,
        ):
            return False
        angle = math.radians(camera["angle"])
        normal = (math.cos(angle), math.sin(angle))
        tangent_axis = (-math.sin(angle), math.cos(angle))
        radial = position[0] * normal[0] + position[1] * normal[1]
        tangent = position[0] * tangent_axis[0] + position[1] * tangent_axis[1]
        radial_limit = (
            CAMERA_BODY_DEPTH / 2.0
            + FASTENER_POST_CAMERA_CLEARANCE
            + post_radius
        )
        tangent_limit = (
            CAMERA_BODY_WIDTH / 2.0
            + FASTENER_POST_CAMERA_CLEARANCE
            + post_radius
        )
        if (
            abs(radial - camera["radial"]) < radial_limit
            and abs(tangent - camera["tangent"]) < tangent_limit
        ):
            return False
    return True


def resolve_symmetric_post_pairs(
    targets,
    index_pairs,
    cameras,
    inner_loop,
    accepted_positions,
    post_diameter,
    search_radius,
    search_step,
    label,
    avoid_camera_bracket_plate=False,
    mechanism=None,
):
    resolved = [None] * len(targets)
    accepted = list(accepted_positions)
    steps = int(math.ceil(search_radius / search_step))
    for first_index, second_index in index_pairs:
        first_target = targets[first_index]
        second_target = targets[second_index]
        candidates = []
        for ix in range(-steps, steps + 1):
            for iy in range(-steps, steps + 1):
                dx = ix * search_step
                dy = iy * search_step
                if math.hypot(dx, dy) > search_radius:
                    continue
                first = (first_target[0] + dx, first_target[1] + dy)
                second = mirror_xy_across_camera_centerline(first)
                if math.dist(second, second_target) > search_radius:
                    continue
                if not post_is_valid(
                    first,
                    cameras,
                    inner_loop,
                    accepted,
                    post_diameter=post_diameter,
                    avoid_camera_bracket_plate=avoid_camera_bracket_plate,
                    mechanism=mechanism,
                ):
                    continue
                if not post_is_valid(
                    second,
                    cameras,
                    inner_loop,
                    [*accepted, first],
                    post_diameter=post_diameter,
                    avoid_camera_bracket_plate=avoid_camera_bracket_plate,
                    mechanism=mechanism,
                ):
                    continue
                score = (
                    math.dist(first, first_target) ** 2
                    + math.dist(second, second_target) ** 2
                )
                candidates.append((score, first, second))
        if not candidates:
            raise ValueError(
                f"No symmetric {label} pair fits targets "
                f"{first_target} and {second_target}"
            )
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        _, first, second = candidates[0]
        resolved[first_index] = first
        resolved[second_index] = second
        accepted.extend((first, second))
    return tuple(resolved)


def resolve_fastener_post_positions(cameras, footprint, mechanism=None):
    if mechanism is None and CAMERA_CARTRIDGE_WORM_ENABLED:
        mechanism = adjustable_mechanism_layout(cameras, footprint)
    post_minimum_scale = minimum_body_scale_between(
        BOTTOM_THICKNESS - BOOLEAN_OVERLAP,
        BASE_HEIGHT - FASTENER_POST_TOP_CLEARANCE,
    )
    inner_loop = inset_footprint_loop(
        scale_loop(footprint, post_minimum_scale), BODY_WALL_THICKNESS
    )
    if FASTENER_POST_PLACEMENT == "manual":
        positions = [tuple(position) for position in MANUAL_FASTENER_POST_POSITIONS_XY]
        accepted = []
        for index, position in enumerate(positions, start=1):
            if not post_is_valid(
                position,
                cameras,
                inner_loop,
                accepted,
                avoid_camera_bracket_plate=True,
                mechanism=mechanism,
            ):
                raise ValueError(
                    f"Manual fastener post {index} at {position} violates a camera, "
                    "wall, or post-spacing keepout"
                )
            accepted.append(position)
    elif FORCE_LAYOUT_SYMMETRY:
        positions = resolve_symmetric_post_pairs(
            tuple(tuple(target) for target in FASTENER_POST_TARGETS_XY),
            ((0, 1), (2, 3)),
            cameras,
            inner_loop,
            (),
            FASTENER_POST_DIAMETER,
            FASTENER_AUTO_SEARCH_RADIUS,
            FASTENER_AUTO_GRID_STEP,
            "lid-fastener post",
            avoid_camera_bracket_plate=True,
            mechanism=mechanism,
        )
        accepted = list(positions)
    else:
        accepted = []
        steps = int(math.ceil(FASTENER_AUTO_SEARCH_RADIUS / FASTENER_AUTO_GRID_STEP))
        for index, target in enumerate(FASTENER_POST_TARGETS_XY, start=1):
            candidates = []
            for ix in range(-steps, steps + 1):
                for iy in range(-steps, steps + 1):
                    dx = ix * FASTENER_AUTO_GRID_STEP
                    dy = iy * FASTENER_AUTO_GRID_STEP
                    if math.hypot(dx, dy) > FASTENER_AUTO_SEARCH_RADIUS:
                        continue
                    position = (target[0] + dx, target[1] + dy)
                    if post_is_valid(
                        position,
                        cameras,
                        inner_loop,
                        accepted,
                        avoid_camera_bracket_plate=True,
                        mechanism=mechanism,
                    ):
                        candidates.append((dx * dx + dy * dy, position))
            if not candidates:
                raise ValueError(
                    f"No valid location found near fastener target {index} {target}; "
                    "move the target or increase FASTENER_AUTO_SEARCH_RADIUS"
                )
            candidates.sort(key=lambda item: (item[0], item[1][0], item[1][1]))
            accepted.append(candidates[0][1])
    result = tuple(accepted)
    print("FASTENER_POST_POSITIONS_XY", result)
    return result


def camera_bracket_contact_rail_tangents(camera, cameras):
    """Choose both body-edge rails or one configurable compact rail."""
    _, body_tangent, _ = mission1.canonical_body_bounds(CAMERA_UPSIDE_DOWN)
    candidates = (
        camera["eye_tangent"]
        + body_tangent[0]
        + CAMERA_BRACKET_CONTACT_RAIL_EDGE_INSET,
        camera["eye_tangent"]
        + body_tangent[1]
        - CAMERA_BRACKET_CONTACT_RAIL_EDGE_INSET,
    )
    if not CAMERA_BRACKET_COMPACT_OUTER_RAIL_ONLY:
        return candidates
    usb_index = 0 if camera_usb_side_name() == "tangent_min" else 1
    if CAMERA_BRACKET_COMPACT_RAIL_SIDE == "usb":
        return (candidates[usb_index],)
    if CAMERA_BRACKET_COMPACT_RAIL_SIDE == "non_usb":
        return (candidates[1 - usb_index],)
    if len(cameras) != 2:
        return (candidates[usb_index],)
    opposite = cameras[1 - cameras.index(camera)]
    opposite_center = Vector((*opposite["center_xy"], 0.0))
    body_radial = mission1.canonical_body_bounds(CAMERA_UPSIDE_DOWN)[0]
    sample_radial = (
        camera["radial"]
        + CAMERA_BODY_DEPTH / 2.0
        + sum(body_radial) / 2.0
    )
    scored = []
    for tangent in candidates:
        point = axis_point(camera["angle"], sample_radial, tangent, 0.0)
        scored.append(((point - opposite_center).length_squared, tangent))
    scored.sort(reverse=True)
    return (scored[0][1],)


def camera_bracket_post_targets(cameras):
    body_radial, body_tangent, _ = mission1.canonical_body_bounds(
        CAMERA_UPSIDE_DOWN
    )
    camera_to_post_clearance = (
        FASTENER_POST_CAMERA_CLEARANCE + CAMERA_BRACKET_POST_REAR_CLEARANCE
    )
    if not EYE_TOP_LOADING_ENABLED:
        camera_to_post_clearance = max(
            camera_to_post_clearance,
            CAMERA_INSTALLATION_REARWARD_TRAVEL
            + CAMERA_INSTALLATION_POST_CLEARANCE,
        )
    rear_offset = (
        CAMERA_BRACKET_POST_BASE_DIAMETER / 2.0
        + camera_to_post_clearance
    )
    targets = []
    for camera in cameras:
        rail_tangents = camera_bracket_contact_rail_tangents(camera, cameras)
        camera["bracket_contact_rail_tangents"] = rail_tangents
        if CAMERA_BRACKET_COMPACT_OUTER_RAIL_ONLY:
            post_tangent_center = rail_tangents[0]
            half_spacing = (
                CAMERA_BRACKET_COMPACT_POST_TANGENTIAL_SPACING / 2.0
            )
        else:
            post_tangent_center = sum(body_tangent) / 2.0
            half_spacing = CAMERA_BRACKET_POST_TANGENTIAL_SPACING / 2.0
        lens_face_radius = camera["radial"] + CAMERA_BODY_DEPTH / 2.0
        post_radius = lens_face_radius + body_radial[0] - rear_offset
        targets.append(
            tuple(
                axis_point(
                    camera["angle"],
                    post_radius,
                    post_tangent_center - half_spacing,
                    0.0,
                )[:2]
            )
        )
        targets.append(
            tuple(
                axis_point(
                    camera["angle"],
                    post_radius,
                    post_tangent_center + half_spacing,
                    0.0,
                )[:2]
            )
        )
    return tuple(targets)


def camera_bracket_post_installation_clearance(position, camera) -> float:
    angle = math.radians(camera["angle"])
    post_radial = position[0] * math.cos(angle) + position[1] * math.sin(angle)
    body_radial = mission1.canonical_body_bounds(CAMERA_UPSIDE_DOWN)[0]
    lens_face_radius = camera["radial"] + CAMERA_BODY_DEPTH / 2.0
    body_back = lens_face_radius + body_radial[0]
    post_front = post_radial + CAMERA_BRACKET_POST_BASE_DIAMETER / 2.0
    return body_back - post_front


def resolve_camera_bracket_post_positions(
    cameras,
    footprint,
    lid_positions,
    mechanism=None,
):
    if not CAMERA_BRACKETS_ENABLED:
        return ((), ())
    if mechanism is None and CAMERA_CARTRIDGE_WORM_ENABLED:
        mechanism = adjustable_mechanism_layout(cameras, footprint)
    post_minimum_scale = minimum_body_scale_between(
        BOTTOM_THICKNESS - BOOLEAN_OVERLAP,
        BASE_HEIGHT,
    )
    inner_loop = inset_footprint_loop(
        scale_loop(footprint, post_minimum_scale), BODY_WALL_THICKNESS
    )
    targets = camera_bracket_post_targets(cameras)
    accepted = list(lid_positions)
    resolved = []
    steps = int(
        math.ceil(
            CAMERA_BRACKET_POST_SEARCH_RADIUS / CAMERA_BRACKET_POST_SEARCH_STEP
        )
    )
    for camera_index in range(2):
        first_target = targets[2 * camera_index]
        second_target = targets[2 * camera_index + 1]
        candidates = []
        for ix in range(-steps, steps + 1):
            for iy in range(-steps, steps + 1):
                dx = ix * CAMERA_BRACKET_POST_SEARCH_STEP
                dy = iy * CAMERA_BRACKET_POST_SEARCH_STEP
                if math.hypot(dx, dy) > CAMERA_BRACKET_POST_SEARCH_RADIUS:
                    continue
                first = (first_target[0] + dx, first_target[1] + dy)
                second = (second_target[0] + dx, second_target[1] + dy)
                if not post_is_valid(
                    first,
                    cameras,
                    inner_loop,
                    accepted,
                    post_diameter=CAMERA_BRACKET_POST_BASE_DIAMETER,
                    mechanism=mechanism,
                ):
                    continue
                if not post_is_valid(
                    second,
                    cameras,
                    inner_loop,
                    [*accepted, first],
                    post_diameter=CAMERA_BRACKET_POST_BASE_DIAMETER,
                    mechanism=mechanism,
                ):
                    continue
                required_installation_clearance = (
                    FASTENER_POST_CAMERA_CLEARANCE
                    + CAMERA_BRACKET_POST_REAR_CLEARANCE
                    if EYE_TOP_LOADING_ENABLED
                    else CAMERA_INSTALLATION_REARWARD_TRAVEL
                    + CAMERA_INSTALLATION_POST_CLEARANCE
                )
                if camera_bracket_post_installation_clearance(
                    first,
                    cameras[camera_index],
                ) < required_installation_clearance:
                    continue
                if camera_bracket_post_installation_clearance(
                    second,
                    cameras[camera_index],
                ) < required_installation_clearance:
                    continue
                candidates.append((dx * dx + dy * dy, first, second))
        if not candidates:
            raise ValueError(
                f"No balanced camera-bracket post pair found for camera "
                f"{camera_index + 1}; increase CAMERA_BRACKET_POST_SEARCH_RADIUS"
            )
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        _, first, second = candidates[0]
        resolved.extend((first, second))
        accepted.extend((first, second))
    result = (tuple(resolved[:2]), tuple(resolved[2:]))
    print("CAMERA_BRACKET_POST_POSITIONS_XY", result)
    for camera, pair in zip(cameras, result):
        minimum_clearance = min(
            camera_bracket_post_installation_clearance(position, camera)
            for position in pair
        )
        print(
            f"CAMERA_INSTALLATION_POST_CLEARANCE {camera['index']}: mode="
            f"{'top' if EYE_TOP_LOADING_ENABLED else 'rearward'} "
            f"resolved_camera_to_post={minimum_clearance:.2f}"
        )
    return result


def point_inside_camera_keepout(position, camera, clearance: float) -> bool:
    angle = math.radians(camera["angle"])
    normal = (math.cos(angle), math.sin(angle))
    tangent_axis = (-math.sin(angle), math.cos(angle))
    radial = position[0] * normal[0] + position[1] * normal[1]
    tangent = position[0] * tangent_axis[0] + position[1] * tangent_axis[1]
    return (
        abs(radial - camera["radial"])
        < CAMERA_BODY_DEPTH / 2.0 + clearance
        and abs(tangent - camera["tangent"])
        < CAMERA_BODY_WIDTH / 2.0 + clearance
    )


def resolve_bottom_mount_hole_position(
    cameras,
    footprint,
    lid_post_positions,
    bracket_position_pairs,
):
    if not BOTTOM_MOUNT_HOLE_ENABLED:
        return None
    front_x = min(x for x, _ in footprint)
    rear_x = max(x for x, _ in footprint)
    hole_radius = BOTTOM_MOUNT_HOLE_DIAMETER / 2.0
    feature_radius = bottom_mount_feature_radius()
    bottom_scale = minimum_body_scale_between(0.0, BOTTOM_THICKNESS)
    bottom_loop = scale_loop(footprint, bottom_scale)
    all_bracket_posts = [
        position for pair in bracket_position_pairs for position in pair
    ]
    steps = int(
        math.ceil(
            BOTTOM_MOUNT_HOLE_SEARCH_RANGE
            / BOTTOM_MOUNT_HOLE_SEARCH_STEP
        )
    )
    offsets = [index * BOTTOM_MOUNT_HOLE_SEARCH_STEP for index in range(-steps, steps + 1)]
    offsets.sort(key=lambda value: (abs(value), value))
    if not BOTTOM_MOUNT_HOLE_AUTO_LATERAL:
        offsets = [0.0]

    fraction_offsets = [0.0]
    if BOTTOM_MOUNT_HOLE_AUTO_FRONT_TO_BACK:
        fraction_steps = int(
            math.ceil(
                BOTTOM_MOUNT_HOLE_FRACTION_SEARCH_RANGE
                / BOTTOM_MOUNT_HOLE_FRACTION_SEARCH_STEP
            )
        )
        fraction_offsets.extend(
            sign * index * BOTTOM_MOUNT_HOLE_FRACTION_SEARCH_STEP
            for index in range(1, fraction_steps + 1)
            for sign in (-1.0, 1.0)
        )
    fractions = []
    for offset in fraction_offsets:
        fraction = BOTTOM_MOUNT_HOLE_FRONT_TO_BACK_FRACTION + offset
        if not 0.0 <= fraction <= 1.0:
            continue
        if any(abs(fraction - existing) < 1e-9 for existing in fractions):
            continue
        fractions.append(fraction)

    for fraction in fractions:
        x = front_x + fraction * (rear_x - front_x)
        for offset in offsets:
            position = (x, BOTTOM_MOUNT_HOLE_LATERAL_TARGET + offset)
            if not point_in_polygon(position, bottom_loop):
                continue
            if polygon_boundary_distance(position, bottom_loop) < (
                feature_radius + BOTTOM_MOUNT_HOLE_EDGE_CLEARANCE
            ):
                continue
            camera_clearance = (
                feature_radius + BOTTOM_MOUNT_HOLE_KEEP_OUT_CLEARANCE
            )
            if any(
                point_inside_camera_keepout(position, camera, camera_clearance)
                for camera in cameras
            ):
                continue
            if any(
                circular_feature_intersects_camera_installation_sweep(
                    position,
                    camera,
                    feature_radius,
                    BOTTOM_MOUNT_HOLE_KEEP_OUT_CLEARANCE,
                )
                for camera in cameras
            ):
                continue
            if any(
                math.dist(position, post) < (
                    feature_radius
                    + FASTENER_POST_DIAMETER / 2.0
                    + BOTTOM_MOUNT_HOLE_KEEP_OUT_CLEARANCE
                )
                for post in lid_post_positions
            ):
                continue
            if any(
                math.dist(position, post) < (
                    feature_radius
                    + CAMERA_BRACKET_POST_BASE_DIAMETER / 2.0
                    + BOTTOM_MOUNT_HOLE_KEEP_OUT_CLEARANCE
                )
                for post in all_bracket_posts
            ):
                continue
            print(
                "BOTTOM_MOUNT_HOLE_POSITION "
                f"requested_fraction="
                f"{BOTTOM_MOUNT_HOLE_FRONT_TO_BACK_FRACTION:.3f} "
                f"resolved_fraction={fraction:.3f} "
                f"xy=({position[0]:.2f}, {position[1]:.2f}) "
                f"feature_radius={feature_radius:.2f} "
                f"hole_radius={hole_radius:.2f}"
            )
            return position
    raise ValueError(
        "No bottom mounting-hole location satisfies the configured "
        "fraction search and camera/post/wall keepouts"
    )


def axis_aligned_rectangle_corners(position, size_x, size_y, clearance=0.0):
    half_x = size_x / 2.0 + clearance
    half_y = size_y / 2.0 + clearance
    return tuple(
        (
            position[0] + sign_x * half_x,
            position[1] + sign_y * half_y,
        )
        for sign_x in (-1.0, 1.0)
        for sign_y in (-1.0, 1.0)
    )


def point_to_axis_aligned_rectangle_distance(point, center, size_x, size_y):
    dx = max(abs(point[0] - center[0]) - size_x / 2.0, 0.0)
    dy = max(abs(point[1] - center[1]) - size_y / 2.0, 0.0)
    return math.hypot(dx, dy)


def convex_polygons_overlap(first, second) -> bool:
    """Separating-axis overlap test for two convex 2D polygons."""
    def cyclic_order(polygon):
        center_x = sum(point[0] for point in polygon) / len(polygon)
        center_y = sum(point[1] for point in polygon) / len(polygon)
        return sorted(
            polygon,
            key=lambda point: math.atan2(
                point[1] - center_y,
                point[0] - center_x,
            ),
        )

    first = cyclic_order(first)
    second = cyclic_order(second)
    axes = []
    for polygon in (first, second):
        for index, point in enumerate(polygon):
            following = polygon[(index + 1) % len(polygon)]
            edge_x = following[0] - point[0]
            edge_y = following[1] - point[1]
            length = math.hypot(edge_x, edge_y)
            if length > 1e-9:
                axes.append((-edge_y / length, edge_x / length))
    for axis_x, axis_y in axes:
        first_projection = [
            x * axis_x + y * axis_y for x, y in first
        ]
        second_projection = [
            x * axis_x + y * axis_y for x, y in second
        ]
        if (
            max(first_projection) <= min(second_projection)
            or max(second_projection) <= min(first_projection)
        ):
            return False
    return True


def resolve_bottom_keystone_positions(
    cameras,
    footprint,
    lid_post_positions,
    bracket_position_pairs,
    bottom_mount_hole_position,
):
    if not BOTTOM_KEYSTONES_ENABLED:
        return ()
    body_top = BOTTOM_THICKNESS + BOTTOM_KEYSTONE_INTERNAL_BODY_HEIGHT
    body_scale = minimum_body_scale_between(BOTTOM_THICKNESS, body_top)
    inner_loop = inset_footprint_loop(
        scale_loop(footprint, body_scale),
        BODY_WALL_THICKNESS,
    )
    bottom_scale = minimum_body_scale_between(0.0, BOTTOM_THICKNESS)
    bottom_loop = scale_loop(footprint, bottom_scale)
    socket_keepout_x, socket_keepout_y = bottom_keystone_socket_plan_dimensions()
    keystone_keepout_x = max(
        BOTTOM_KEYSTONE_INTERNAL_BODY_X,
        BOTTOM_KEYSTONE_FACE_POCKET_X,
        BOTTOM_KEYSTONE_CUTOUT_X,
        socket_keepout_x,
    )
    keystone_keepout_y = max(
        BOTTOM_KEYSTONE_INTERNAL_BODY_Y,
        BOTTOM_KEYSTONE_FACE_POCKET_Y,
        BOTTOM_KEYSTONE_CUTOUT_Y,
        socket_keepout_y,
    )
    side_sign = float(BOTTOM_KEYSTONE_CORNER_Y_SIGN)
    side_extreme = max(side_sign * y for _, y in inner_loop)
    target_y = side_sign * (
        side_extreme
        - BOTTOM_KEYSTONE_SIDE_EDGE_INSET
        - keystone_keepout_y / 2.0
    )
    local_rear_x = radial_surface_distance(0.0, target_y, inner_loop)
    target_x = (
        local_rear_x
        - BOTTOM_KEYSTONE_REAR_EDGE_INSET
        - keystone_keepout_x / 2.0
    )
    all_posts = [
        *(
            (position, FASTENER_POST_DIAMETER / 2.0)
            for position in lid_post_positions
        ),
        *(
            (position, CAMERA_BRACKET_POST_BASE_DIAMETER / 2.0)
            for pair in bracket_position_pairs
            for position in pair
        ),
    ]
    def cluster_positions(shift_x, shift_y):
        positions = []
        for index in range(BOTTOM_KEYSTONE_COUNT):
            if BOTTOM_KEYSTONE_ROW_AXIS == "x":
                positions.append(
                    (
                        target_x + shift_x - index * BOTTOM_KEYSTONE_CENTER_SPACING,
                        target_y + shift_y,
                    )
                )
            else:
                positions.append(
                    (
                        target_x + shift_x,
                        target_y
                        + shift_y
                        - side_sign * index * BOTTOM_KEYSTONE_CENTER_SPACING,
                    )
                )
        return tuple(positions)

    def position_is_valid(position):
        body_corners = axis_aligned_rectangle_corners(
            position,
            keystone_keepout_x,
            keystone_keepout_y,
            BOTTOM_KEYSTONE_EDGE_CLEARANCE,
        )
        if not all(point_in_polygon(corner, inner_loop) for corner in body_corners):
            return False
        bottom_face_x = (
            keystone_keepout_x
            if BOTTOM_KEYSTONE_USE_REFERENCE_SNAP_SOCKET
            else BOTTOM_KEYSTONE_FACE_POCKET_X
        )
        bottom_face_y = (
            keystone_keepout_y
            if BOTTOM_KEYSTONE_USE_REFERENCE_SNAP_SOCKET
            else BOTTOM_KEYSTONE_FACE_POCKET_Y
        )
        pocket_corners = axis_aligned_rectangle_corners(
            position,
            bottom_face_x,
            bottom_face_y,
            BOTTOM_KEYSTONE_EDGE_CLEARANCE,
        )
        if not all(point_in_polygon(corner, bottom_loop) for corner in pocket_corners):
            return False
        body_rectangle = axis_aligned_rectangle_corners(
            position,
            keystone_keepout_x,
            keystone_keepout_y,
        )
        if any(
            convex_polygons_overlap(
                body_rectangle,
                camera_xy_corners(
                    camera,
                    BOTTOM_KEYSTONE_KEEP_OUT_CLEARANCE,
                ),
            )
            for camera in cameras
        ):
            return False
        if VALIDATE_CAMERA_INSTALLATION_PATH and any(
            convex_polygons_overlap(
                body_rectangle,
                camera_installation_sweep_xy_corners(
                    camera,
                    BOTTOM_KEYSTONE_KEEP_OUT_CLEARANCE,
                ),
            )
            for camera in cameras
        ):
            return False
        if any(
            point_to_axis_aligned_rectangle_distance(
                post,
                position,
                keystone_keepout_x,
                keystone_keepout_y,
            )
            < post_radius + BOTTOM_KEYSTONE_KEEP_OUT_CLEARANCE
            for post, post_radius in all_posts
        ):
            return False
        if bottom_mount_hole_position is not None and (
            point_to_axis_aligned_rectangle_distance(
                bottom_mount_hole_position,
                position,
                keystone_keepout_x,
                keystone_keepout_y,
            )
            < bottom_mount_feature_radius()
            + BOTTOM_KEYSTONE_KEEP_OUT_CLEARANCE
        ):
            return False
        return True

    candidates = [(0.0, 0.0)]
    if BOTTOM_KEYSTONE_AUTO_PLACEMENT:
        steps = int(
            math.ceil(
                BOTTOM_KEYSTONE_SEARCH_RANGE / BOTTOM_KEYSTONE_SEARCH_STEP
            )
        )
        candidates = [
            (
                index_x * BOTTOM_KEYSTONE_SEARCH_STEP,
                index_y * BOTTOM_KEYSTONE_SEARCH_STEP,
            )
            for index_x in range(-steps, steps + 1)
            for index_y in range(-steps, steps + 1)
            if math.hypot(index_x, index_y) <= steps
        ]
        candidates.sort(
            key=lambda shift: (
                shift[0] * shift[0] + shift[1] * shift[1],
                abs(shift[1]),
                abs(shift[0]),
                shift[0],
                shift[1],
            )
        )
    for shift_x, shift_y in candidates:
        positions = cluster_positions(shift_x, shift_y)
        if all(position_is_valid(position) for position in positions):
            print(
                "BOTTOM_KEYSTONE_POSITIONS "
                f"corner_y_sign={side_sign:+.0f} axis="
                f"{BOTTOM_KEYSTONE_ROW_AXIS} xy={positions}"
            )
            return positions
    raise ValueError(
        "No bottom-keystone layout satisfies wall, camera, hole, and "
        "fastener-post keepouts"
    )


# ---------------------------------------------------------------------------
# Booleans and construction


def select_only(obj) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def join_tools(name: str, objects):
    objects = list(objects)
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


def apply_boolean(base, tool, operation: str, label: str, solver=None):
    select_only(base)
    modifier = base.modifiers.new(label, "BOOLEAN")
    modifier.operation = operation
    modifier.object = tool
    if hasattr(modifier, "solver"):
        modifier.solver = solver or BOOLEAN_SOLVER
    if hasattr(modifier, "use_self"):
        modifier.use_self = False
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(tool, do_unlink=True)
    cleanup_mesh(base)
    recalc_normals(base)
    return base


def boolean_union(base, part, label="Union", solver=None):
    return apply_boolean(
        base,
        part,
        "UNION",
        label + "_" + part.name,
        solver=solver,
    )


def boolean_difference(base, tools, label="Cut", solver=None):
    tools = list(tools)
    if not tools:
        return base
    return apply_boolean(
        base,
        join_tools(label + "_Tools", tools),
        "DIFFERENCE",
        label,
        solver=solver,
    )


def add_camera_openings_and_visors(base, cameras):
    # A shallow bezel should move the camera and eye face forward even when a
    # distant camera-body corner still defines the convex outer footprint.
    # Recess only the localized eye patch, leaving the rest of the hull free to
    # wrap around both close-spaced cameras.
    if EYE_FACE_RECESS_ENABLED:
        recess_width = EYE_BEZEL_WIDTH - 2.0 * EYE_FACE_RECESS_BORDER_OVERLAP
        recess_height = EYE_BEZEL_HEIGHT - 2.0 * EYE_FACE_RECESS_BORDER_OVERLAP
        recess_radius = max(
            EYE_BEZEL_CORNER_RADIUS - EYE_FACE_RECESS_BORDER_OVERLAP,
            0.0,
        )
        for camera in cameras:
            recess_depth = camera.get("eye_face_recess_depth", 0.0)
            if recess_depth <= CAMERA_NOSE_CONTACT_TOLERANCE:
                continue
            surface = camera["surface"]
            cutter = rounded_rectangle_prism_axis(
                f"Eye_{camera['index']}_Localized_Face_Recess",
                camera["angle"],
                surface
                - EYE_FACE_INSET
                - EYE_BEZEL_DEPTH
                - BOOLEAN_OVERLAP,
                camera["raw_surface"] + EYE_CUTTER_OUTWARD_EXTENSION,
                recess_width,
                recess_height,
                recess_radius,
                camera_eye_center_z(),
                center_tangent=camera["eye_tangent"],
            )
            boolean_difference(
                base,
                [cutter],
                f"Eye_{camera['index']}_Localized_Face_Recess_Cut",
            )
            print(
                f"EYE_FACE_RECESS {camera['index']}: depth={recess_depth:.2f}"
            )
    add_camera_outer_recess_flares(base, cameras)
    add_camera_surrounds_and_visors(base, cameras)
    # Keep the two cutters in separate Boolean stages because close camera
    # angles can make their tool volumes overlap inside the body.
    for camera in cameras:
        index = camera["index"]
        angle = camera["angle"]
        surface = camera["surface"]
        tangent = camera["eye_tangent"]
        opening_tools = [
            rounded_rectangle_prism_axis(
                f"Eye_{index}_Opening",
                angle,
                surface
                - BODY_WALL_THICKNESS
                - EYE_BEZEL_DEPTH
                - EYE_FACE_INSET
                - EYE_CUTTER_INWARD_EXTRA,
                surface + EYE_CUTTER_OUTWARD_EXTENSION,
                EYE_OPENING_WIDTH,
                EYE_OPENING_HEIGHT,
                EYE_OPENING_CORNER_RADIUS,
                camera_eye_center_z(),
                center_tangent=tangent,
            )
        ]
        if camera_is_adjustable(camera):
            # Flare the internal eye throat through the complete yaw range.
            # The nominal outside aperture remains Veo-shaped and unchanged.
            for sample_index, yaw_delta in enumerate(
                adjustable_yaw_samples(),
                start=1,
            ):
                pose_angle = camera["angle"] + yaw_delta
                lens_center = adjustable_camera_local_point(
                    camera,
                    0.0,
                    0.0,
                    camera_eye_center_z(),
                    yaw_delta,
                )
                pose_radians = math.radians(pose_angle)
                pose_normal = (
                    math.cos(pose_radians),
                    math.sin(pose_radians),
                )
                pose_tangent_axis = (
                    -math.sin(pose_radians),
                    math.cos(pose_radians),
                )
                center_radial = (
                    lens_center.x * pose_normal[0]
                    + lens_center.y * pose_normal[1]
                )
                center_tangent = (
                    lens_center.x * pose_tangent_axis[0]
                    + lens_center.y * pose_tangent_axis[1]
                )
                opening_tools.append(
                    rounded_rectangle_prism_axis(
                        f"Eye_{index}_Swept_Throat_{sample_index}",
                        pose_angle,
                        center_radial
                        + mission1.LENS_SHOULDER_Y
                        - mission1.LENS_FACE_Y
                        - CAMERA_LENS_OPENING_CLEARANCE,
                        center_radial + EYE_CUTTER_OUTWARD_EXTENSION,
                        mission1.LENS_FACE_WIDTH
                        + 2.0 * CAMERA_LENS_OPENING_CLEARANCE,
                        mission1.LENS_FACE_HEIGHT
                        + 2.0 * CAMERA_LENS_OPENING_CLEARANCE,
                        mission1.LENS_FACE_CORNER_RADIUS
                        + CAMERA_LENS_OPENING_CLEARANCE,
                        camera_eye_center_z(),
                        center_tangent=center_tangent,
                    )
                )
        boolean_difference(
            base,
            opening_tools,
            f"Camera_Opening_{index}",
        )
    add_camera_top_loading_slots(base, cameras)
    return base


def add_camera_outer_recess_flares(base, cameras):
    """Open the final outer hull without re-cutting the empty eye throats."""
    if not (
        EYE_FACE_RECESS_ENABLED
        and EYE_FACE_RECESS_OUTER_FLARE_ENABLED
    ):
        return base
    recess_width = EYE_BEZEL_WIDTH - 2.0 * EYE_FACE_RECESS_BORDER_OVERLAP
    recess_height = EYE_BEZEL_HEIGHT - 2.0 * EYE_FACE_RECESS_BORDER_OVERLAP
    recess_radius = max(
        EYE_BEZEL_CORNER_RADIUS - EYE_FACE_RECESS_BORDER_OVERLAP,
        0.0,
    )
    for camera in cameras:
        recess_depth = camera.get("eye_face_recess_depth", 0.0)
        if recess_depth <= CAMERA_NOSE_CONTACT_TOLERANCE:
            continue
        flare_start = camera["surface"] - EYE_FACE_INSET + BOOLEAN_OVERLAP
        flare_end = camera["raw_surface"] + BOOLEAN_OVERLAP
        flare_depth = max(flare_end - flare_start, 0.0)
        flare = min(
            flare_depth
            * math.tan(math.radians(EYE_FACE_RECESS_OUTER_FLARE_ANGLE_DEG)),
            EYE_FACE_RECESS_OUTER_FLARE_MAX_PER_SIDE,
        )
        if flare <= CAMERA_NOSE_CONTACT_TOLERANCE:
            continue
        flare_shell = rounded_rectangle_flare_shell_axis(
            f"Eye_{camera['index']}_Outer_Face_Recess_Flare",
            camera["angle"],
            flare_start,
            flare_end,
            recess_width,
            recess_height,
            recess_radius,
            recess_width + 2.0 * flare,
            recess_height + 2.0 * flare,
            recess_radius + flare,
            camera_eye_center_z(),
            center_tangent=camera["eye_tangent"],
        )
        boolean_difference(
            base,
            [flare_shell],
            f"Eye_{camera['index']}_Outer_Face_Recess_Flare_Cut",
        )
        print(
            f"EYE_FACE_RECESS_FLARE {camera['index']}: "
            f"depth={flare_depth:.2f} per_side={flare:.2f}"
        )
    return base


def add_camera_surrounds_and_visors(base, cameras):
    """Add structural bezels/anchors after every intersecting shell cut."""
    for camera in cameras:
        index = camera["index"]
        angle = camera["angle"]
        surface = camera["surface"]
        tangent = camera["eye_tangent"]
        bezel = rounded_rectangle_prism_axis(
            f"Eye_{index}_Raised_Surround",
            angle,
            surface - EYE_FACE_INSET - EYE_BEZEL_DEPTH,
            surface - EYE_FACE_INSET,
            EYE_BEZEL_WIDTH,
            EYE_BEZEL_HEIGHT,
            EYE_BEZEL_CORNER_RADIUS,
            camera_eye_center_z(),
            center_tangent=tangent,
        )
        boolean_union(base, bezel, f"Eye_{index}_Surround_Union")
        if camera.get("eye_face_recess_depth", 0.0) > (
            CAMERA_NOSE_CONTACT_TOLERANCE
        ):
            anchor_vertical = EYE_BEZEL_HEIGHT / 2.0 - 4.5
            for anchor_index, (tangent_sign, vertical_sign) in enumerate(
                (
                    (-1.0, -1.0),
                    (-1.0, 1.0),
                    (1.0, -1.0),
                    (1.0, 1.0),
                ),
                start=1,
            ):
                anchor_width = 5.0 if vertical_sign > 0.0 else 8.0
                anchor_tangent = (
                    EYE_BEZEL_WIDTH / 2.0
                    - anchor_width / 2.0
                    - 0.25
                )
                anchor = rounded_rectangle_prism_axis(
                    f"Eye_{index}_Recess_Anchor_{anchor_index}",
                    angle,
                    surface
                    - EYE_FACE_INSET
                    - EYE_BEZEL_DEPTH
                    - BOOLEAN_OVERLAP,
                    camera["raw_surface"] + BOOLEAN_OVERLAP,
                    anchor_width,
                    8.0,
                    2.0,
                    camera_eye_center_z()
                    + vertical_sign * anchor_vertical,
                    center_tangent=(
                        tangent + tangent_sign * anchor_tangent
                    ),
                )
                boolean_union(
                    base,
                    anchor,
                    f"Eye_{index}_Recess_Anchor_{anchor_index}_Union",
                )
        if VISORS_ENABLED:
            boolean_union(
                base,
                visor_wedge(
                    f"Eye_{index}_Eyelid_Visor",
                    angle,
                    surface,
                    center_tangent=tangent,
                ),
                f"Eye_{index}_Visor_Union",
            )
    return base


def add_camera_top_loading_slots(base, cameras):
    if not EYE_TOP_LOADING_ENABLED:
        return base
    slot_bottom = eye_top_loading_slot_bottom_z()
    for camera in cameras:
        index = camera["index"]
        slot = eye_axis_box(
            f"Eye_{index}_Top_Loading_U_Slot",
            camera,
            eye_opening_cutter_radial_bounds(camera),
            EYE_TOP_LOADING_SLOT_WIDTH,
            slot_bottom,
            BASE_HEIGHT + BOOLEAN_OVERLAP,
        )
        boolean_difference(
            base,
            [slot],
            f"Eye_{index}_Top_Loading_U_Slot_Cut",
        )
        if camera.get("eye_face_recess_depth", 0.0) > (
            CAMERA_NOSE_CONTACT_TOLERANCE
        ):
            _, backing_radial = eye_lid_closure_radial_bounds(camera)
            backing_width = (
                EYE_TOP_LOADING_SLOT_WIDTH
                - 2.0 * EYE_LID_CLOSURE_FIT_CLEARANCE
                + 2.0 * EYE_LID_CLOSURE_BACKING_SIDE_OVERLAP
            )
            backing_pocket = eye_axis_box(
                f"Eye_{index}_Lid_Backing_Flange_Pocket",
                camera,
                (
                    backing_radial[0] - EYE_LID_CLOSURE_FIT_CLEARANCE,
                    backing_radial[1] + EYE_LID_CLOSURE_FIT_CLEARANCE,
                ),
                backing_width + 2.0 * EYE_LID_CLOSURE_FIT_CLEARANCE,
                slot_bottom,
                BASE_HEIGHT + BOOLEAN_OVERLAP,
            )
            boolean_difference(
                base,
                [backing_pocket],
                f"Eye_{index}_Lid_Backing_Flange_Pocket_Cut",
            )
        print(
            f"EYE_TOP_LOADING_SLOT {index}: width="
            f"{EYE_TOP_LOADING_SLOT_WIDTH:.2f} bottom_z={slot_bottom:.2f}"
        )
    return base


def add_camera_front_stops(base, cameras):
    """Add wall-backed pads that positively locate each camera radially."""
    if not CAMERA_FRONT_STOPS_ENABLED:
        return base
    body_radial = mission1.canonical_body_bounds(CAMERA_UPSIDE_DOWN)[0]
    projection = camera_front_stop_projection()
    specs = camera_front_stop_specs()
    for camera in cameras:
        if camera_is_adjustable(camera):
            continue
        lens_face_radius = camera["radial"] + CAMERA_BODY_DEPTH / 2.0
        body_front = lens_face_radius + body_radial[1]
        wall_inner = camera["eye_inner_wall"]
        expected_body_front = wall_inner - projection
        contact_error = abs(body_front - expected_body_front)
        if contact_error > CAMERA_FRONT_STOP_CONTACT_TOLERANCE:
            raise RuntimeError(
                f"Camera {camera['index']} front-stop plane misses its body by "
                f"{contact_error:.4f} mm"
            )
        for label, tangent, vertical, width, height in specs:
            stop = rounded_rectangle_prism_axis(
                f"Camera_{camera['index']}_Front_Stop_{label}",
                camera["angle"],
                body_front,
                wall_inner + BOOLEAN_OVERLAP,
                width,
                height,
                min(CAMERA_FRONT_STOP_EDGE_RADIUS, width / 2.0, height / 2.0),
                camera_eye_center_z() + vertical,
                center_tangent=camera["eye_tangent"] + tangent,
            )
            boolean_union(
                base,
                stop,
                f"Camera_{camera['index']}_Front_Stop_{label}_Union",
            )
        camera["front_stop_contact_radius"] = body_front
        print(
            f"CAMERA_FRONT_STOPS {camera['index']}: projection={projection:.2f} "
            f"body_contact_radius={body_front:.2f} pads={len(specs)}"
        )
    return base


def add_camera_usb_access_openings(base, cameras):
    """Cut the measured plug envelope from each USB side through the shell."""
    if not CAMERA_USB_ACCESS_ENABLED:
        return base
    for camera in cameras:
        yaw_samples = (
            adjustable_yaw_samples(include_preview=True)
            if camera_is_adjustable(camera)
            else (0.0,)
        )
        for sample_index, yaw_delta in enumerate(yaw_samples, start=1):
            cutter = create_camera_usb_access_keepout(camera, yaw_delta)
            boolean_difference(
                base,
                [cutter],
                f"Camera_{camera['index']}_USB_Plug_Access_"
                f"Opening_{sample_index}",
            )
        print(
            f"CAMERA_USB_ACCESS_OPENING {camera['index']}: "
            f"side={camera_usb_side_name()} radial_width="
            f"{CAMERA_USB_PORT_RADIAL_WIDTH:.2f} height="
            f"{CAMERA_USB_PORT_HEIGHT:.2f} plug_depth="
            f"{CAMERA_USB_PLUG_OUTWARD_DEPTH:.2f} "
            f"yaw_samples={len(yaw_samples)}"
        )
    return base


def add_rear_fan_mounts(base, footprint, post_keepouts=()):
    if not REAR_FANS_ENABLED:
        return base
    half_spacing = REAR_FAN_MOUNT_SPACING / 2.0
    air_radius = REAR_FAN_AIR_OPENING_DIAMETER / 2.0
    hole_radius = REAR_FAN_MOUNT_HOLE_DIAMETER / 2.0
    for fan_index, center_tangent in enumerate(
        rear_fan_center_tangents(),
        start=1,
    ):
        pad_side = "Inside" if REAR_FAN_PAD_INSIDE else "Outside"
        pad = curved_backed_flat_pad(
            f"Rear_40mm_Fan_{fan_index}_{pad_side}_45mm_Flat_Pad",
            footprint,
            center_tangent,
        )
        face_radius = pad["fan_face_radius"]
        pad_inside = pad["fan_pad_inside"]
        fan_angle_deg = pad["fan_face_angle_deg"]
        fan_angle = math.radians(fan_angle_deg)
        fan_normal = (math.cos(fan_angle), math.sin(fan_angle))
        fan_tangent = (-math.sin(fan_angle), math.cos(fan_angle))
        center_axis_tangent = pad["fan_center_axis_tangent"]
        face_center_x = pad["fan_face_center_x"]
        face_center_y = pad["fan_face_center_y"]
        if pad_inside:
            cutter_start = face_radius - BOOLEAN_OVERLAP
            cutter_end = pad["fan_max_surface_radius"] + BOOLEAN_OVERLAP
        else:
            cutter_start = (
                pad["fan_min_surface_radius"]
                - BODY_WALL_THICKNESS
                - REAR_FAN_CUTTER_INWARD_EXTENSION
            )
            cutter_end = face_radius + BOOLEAN_OVERLAP
        boolean_union(base, pad, f"Rear_Fan_{fan_index}_Flat_Pad_Union")

        air_cutter = cylinder_prism_axis(
            f"Rear_Fan_{fan_index}_Air_Opening",
            fan_angle_deg,
            cutter_start,
            cutter_end,
            air_radius,
            center_axis_tangent,
            REAR_FAN_CENTER_Z,
        )
        screw_cutters = []
        for tangent_sign in (-1.0, 1.0):
            for z_sign in (-1.0, 1.0):
                screw_cutters.append(
                    cylinder_prism_axis(
                        f"Rear_Fan_{fan_index}_Mount_Hole_"
                        f"{tangent_sign:+.0f}_{z_sign:+.0f}",
                        fan_angle_deg,
                        cutter_start,
                        cutter_end,
                        hole_radius,
                        center_axis_tangent + tangent_sign * half_spacing,
                        REAR_FAN_CENTER_Z + z_sign * half_spacing,
                    )
                )

        # A rearward post would silently block a fan passage.  Reject such a
        # custom layout before cutting rather than leaving a partial airway.
        for x, y, post_radius in post_keepouts:
            post_radial = x * fan_normal[0] + y * fan_normal[1]
            post_tangent = x * fan_tangent[0] + y * fan_tangent[1]
            if (
                post_radial < cutter_start - post_radius
                or post_radial > cutter_end + post_radius
            ):
                continue
            if abs(post_tangent - center_axis_tangent) < (
                air_radius + post_radius
            ):
                raise ValueError(
                    f"Rear fan {fan_index} airflow intersects a fastener post"
                )
        boolean_difference(
            base,
            [air_cutter, *screw_cutters],
            f"Rear_Fan_{fan_index}_Air_And_Mount_Holes",
        )
        print(
            f"REAR_FAN_MOUNT {fan_index}: centerline_offset="
            f"{center_tangent:.2f} angle={fan_angle_deg:.2f}deg "
            f"pad_side={'inside' if pad_inside else 'outside'} "
            f"face_center=({face_center_x:.2f}, "
            f"{face_center_y:.2f}, {REAR_FAN_CENTER_Z:.2f}) "
            f"air_diameter={REAR_FAN_AIR_OPENING_DIAMETER:.2f}"
        )
    return base


def create_rear_fan_body_keepouts(footprint):
    """Create temporary 40 mm fan solids including installation clearance."""
    if not REAR_FANS_ENABLED or not VALIDATE_REAR_FAN_BODY_CLEARANCE:
        return []
    keepouts = []
    depth = REAR_FAN_DEPTH + 2.0 * REAR_FAN_BODY_CLEARANCE
    side = 40.0 + 2.0 * REAR_FAN_BODY_CLEARANCE
    inward_sign = -1.0 if REAR_FAN_PAD_INSIDE else 1.0
    for fan_index, center_tangent in enumerate(
        rear_fan_center_tangents(),
        start=1,
    ):
        station = rear_fan_station_geometry(footprint, center_tangent)
        center_radius = (
            station["face_radius"]
            + inward_sign * REAR_FAN_DEPTH / 2.0
        )
        center = axis_point(
            station["wall_angle_deg"],
            center_radius,
            station["center_axis_tangent"],
            REAR_FAN_CENTER_Z,
        )
        keepout = add_beveled_box(
            f"Rear_Fan_{fan_index}_Physical_Body_Keepout",
            (depth, side, side),
            tuple(center),
            rotation_z=math.radians(station["wall_angle_deg"]),
            bevel=0.0,
        )
        keepout["fan_index"] = fan_index
        keepouts.append(keepout)
    return keepouts


def validate_rear_fan_body_clearances(
    footprint,
    cameras,
    camera_mockups,
    camera_brackets,
    camera_carrier=None,
    camera_worm=None,
):
    """Keep complete fan frames clear of fixed and swept internal hardware."""
    fan_keepouts = create_rear_fan_body_keepouts(footprint)
    if not fan_keepouts:
        return
    targets = [
        (f"bracket_{index}", bracket)
        for index, bracket in enumerate(camera_brackets, start=1)
    ]
    if camera_worm is not None:
        targets.append(("worm", camera_worm))
    temporary_objects = []
    for index, (camera, mockup) in enumerate(
        zip(cameras, camera_mockups),
        start=1,
    ):
        if camera_is_adjustable(camera):
            for yaw_delta in adjustable_yaw_samples(include_preview=True):
                posed = duplicate_object(
                    mockup,
                    f"Rear_Fan_Camera_{index}_Yaw_{yaw_delta:+.1f}",
                )
                pivot = adjustable_camera_pivot(camera)
                rotate_mesh_about_world_axis(
                    posed,
                    (pivot.x, pivot.y, 0.0),
                    (0.0, 0.0, 1.0),
                    yaw_delta,
                )
                targets.append(
                    (f"camera_{index}_yaw_{yaw_delta:+.1f}", posed)
                )
                temporary_objects.append(posed)
        else:
            targets.append((f"camera_{index}", mockup))
    if camera_carrier is not None:
        moving_camera = adjustable_camera(cameras)
        for yaw_delta in adjustable_yaw_samples(include_preview=True):
            posed = posed_carrier_copy(
                camera_carrier,
                moving_camera,
                yaw_delta,
                f"Rear_Fan_Carrier_Yaw_{yaw_delta:+.1f}",
            )
            targets.append((f"carrier_yaw_{yaw_delta:+.1f}", posed))
            temporary_objects.append(posed)
    try:
        for keepout in fan_keepouts:
            fan_index = keepout["fan_index"]
            for target_name, target in targets:
                volume = intersection_metrics(
                    keepout,
                    target,
                    f"rear_fan_{fan_index}_{target_name}",
                )[2]
                if volume > ASSEMBLY_INTERSECTION_VOLUME_TOLERANCE:
                    raise RuntimeError(
                        f"Rear fan {fan_index} body overlaps {target_name}: "
                        f"{volume:.9f} mm^3"
                    )
    finally:
        for obj in (*fan_keepouts, *temporary_objects):
            if obj.name in bpy.data.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
    print(
        "REAR_FAN_BODY_CLEARANCE PASS "
        f"fan_size=40x40x{REAR_FAN_DEPTH:.1f}mm "
        f"clearance={REAR_FAN_BODY_CLEARANCE:.1f}mm "
        f"direction={REAR_FAN_AIRFLOW_DIRECTION}"
    )


def add_fastener_posts(base, positions):
    if not FASTENERS_ENABLED:
        return base
    post_top = BASE_HEIGHT - FASTENER_POST_TOP_CLEARANCE
    for index, (x, y) in enumerate(positions, start=1):
        post = add_cylinder_z(
            f"Base_Heat_Insert_Post_{index}",
            FASTENER_POST_DIAMETER / 2.0,
            BOTTOM_THICKNESS - BOOLEAN_OVERLAP,
            post_top,
            x,
            y,
        )
        boolean_union(base, post, f"Base_Heat_Insert_Post_{index}_Union")

    insert_cutters = [
        add_cylinder_z(
            f"Heat_Insert_Hole_{index}",
            HEAT_INSERT_HOLE_DIAMETER / 2.0,
            post_top - HEAT_INSERT_HOLE_DEPTH,
            post_top + BOOLEAN_OVERLAP,
            x,
            y,
        )
        for index, (x, y) in enumerate(positions, start=1)
    ]
    boolean_difference(base, insert_cutters, "Heat_Insert_Holes")

    if HEAT_INSERT_LEADIN_DEPTH > 0.0:
        leadin_cutters = [
            add_cylinder_z(
                f"Heat_Insert_Leadin_{index}",
                HEAT_INSERT_LEADIN_DIAMETER / 2.0,
                post_top - HEAT_INSERT_LEADIN_DEPTH,
                post_top + 2.0 * BOOLEAN_OVERLAP,
                x,
                y,
            )
            for index, (x, y) in enumerate(positions, start=1)
        ]
        boolean_difference(base, leadin_cutters, "Heat_Insert_Leadins")
    return base


def add_camera_cradles(base, cameras):
    """Add floor supports and a snug, reinforced lower camera socket."""
    if not CAMERA_CRADLES_ENABLED:
        return base
    body_radial, body_tangent, body_vertical = mission1.canonical_body_bounds(
        CAMERA_UPSIDE_DOWN
    )
    body_radial_center = sum(body_radial) / 2.0
    support_top = camera_eye_center_z() + body_vertical[0]
    support_z0 = BOTTOM_THICKNESS - BOOLEAN_OVERLAP
    support_depth = support_top - support_z0
    pad_tangent_centers = camera_support_pad_tangent_centers()

    for camera in cameras:
        if camera_is_adjustable(camera):
            continue
        lens_face_radius = camera["radial"] + CAMERA_BODY_DEPTH / 2.0
        for pad_index, pad_tangent in enumerate(pad_tangent_centers, start=1):
            center = axis_point(
                camera["angle"],
                lens_face_radius + body_radial_center,
                camera["eye_tangent"] + pad_tangent,
                (support_z0 + support_top) / 2.0,
            )
            pad = add_beveled_box(
                f"Camera_{camera['index']}_Support_Pad_{pad_index}",
                (
                    CAMERA_SUPPORT_PAD_RADIAL_LENGTH,
                    CAMERA_SUPPORT_PAD_TANGENTIAL_WIDTH,
                    support_depth,
                ),
                tuple(center),
                rotation_z=math.radians(camera["angle"]),
                bevel=CAMERA_SUPPORT_PAD_EDGE_RADIUS,
            )
            boolean_union(
                base,
                pad,
                f"Camera_{camera['index']}_Support_Pad_{pad_index}_Union",
            )

        side_guide_height = resolved_camera_cradle_side_guide_height()
        side_guide_z1 = support_top + side_guide_height
        side_guide_depth = side_guide_z1 - support_z0
        side_guide_radial_center = body_radial_center
        if CAMERA_CRADLE_SIDE_GUIDE_RADIAL_PLACEMENT == "front":
            side_guide_radial_max = (
                body_radial[1]
                - mission1.BODY_CORNER_RADIUS
                - CAMERA_CRADLE_SIDE_GUIDE_FRONT_INSET
            )
            side_guide_radial_center = (
                side_guide_radial_max
                - CAMERA_CRADLE_SIDE_GUIDE_RADIAL_LENGTH / 2.0
            )
        guide_specs = [
            (
                1,
                "tangent_min",
                body_tangent[0]
                - CAMERA_CRADLE_SIDE_CLEARANCE
                - CAMERA_CRADLE_SIDE_GUIDE_THICKNESS / 2.0,
            ),
            (
                2,
                "tangent_max",
                body_tangent[1]
                + CAMERA_CRADLE_SIDE_CLEARANCE
                + CAMERA_CRADLE_SIDE_GUIDE_THICKNESS / 2.0,
            ),
        ]
        if CAMERA_CRADLE_FIXED_SIDE_GUIDES == "non_usb_only":
            guide_specs = [
                spec for spec in guide_specs if spec[1] != camera_usb_side_name()
            ]
        elif CAMERA_CRADLE_FIXED_SIDE_GUIDES == "none":
            guide_specs = []
        for guide_index, guide_side, tangent in guide_specs:
            center = axis_point(
                camera["angle"],
                lens_face_radius + side_guide_radial_center,
                camera["eye_tangent"] + tangent,
                (support_z0 + side_guide_z1) / 2.0,
            )
            guide = add_beveled_box(
                f"Camera_{camera['index']}_Side_Guide_{guide_index}",
                (
                    CAMERA_CRADLE_SIDE_GUIDE_RADIAL_LENGTH,
                    CAMERA_CRADLE_SIDE_GUIDE_THICKNESS,
                    side_guide_depth,
                ),
                tuple(center),
                rotation_z=math.radians(camera["angle"]),
                bevel=CAMERA_CRADLE_GUIDE_EDGE_RADIUS,
            )
            boolean_union(
                base,
                guide,
                f"Camera_{camera['index']}_Side_Guide_{guide_index}_Union",
            )

        if camera_cradle_rear_guides_enabled():
            body_back = lens_face_radius + body_radial[0]
            rear_guide_z1 = support_top + CAMERA_CRADLE_REAR_GUIDE_HEIGHT
            rear_segment_width = (
                CAMERA_CRADLE_REAR_GUIDE_TANGENTIAL_WIDTH
                - CAMERA_CRADLE_REAR_GUIDE_CENTER_AIR_GAP
            ) / 2.0
            rear_segment_offset = (
                CAMERA_CRADLE_REAR_GUIDE_CENTER_AIR_GAP
                + rear_segment_width
            ) / 2.0
            rear_tangent_center = (
                camera["eye_tangent"] + sum(body_tangent) / 2.0
            )
            for rear_index, tangent_sign in enumerate((-1.0, 1.0), start=1):
                rear_guide_center = axis_point(
                    camera["angle"],
                    body_back
                    - CAMERA_CRADLE_REAR_CLEARANCE
                    - CAMERA_CRADLE_REAR_GUIDE_THICKNESS / 2.0,
                    rear_tangent_center
                    + tangent_sign * rear_segment_offset,
                    (support_z0 + rear_guide_z1) / 2.0,
                )
                rear_guide = add_beveled_box(
                    f"Camera_{camera['index']}_Rear_Guide_{rear_index}",
                    (
                        CAMERA_CRADLE_REAR_GUIDE_THICKNESS,
                        rear_segment_width,
                        rear_guide_z1 - support_z0,
                    ),
                    tuple(rear_guide_center),
                    rotation_z=math.radians(camera["angle"]),
                    bevel=CAMERA_CRADLE_GUIDE_EDGE_RADIUS,
                )
                boolean_union(
                    base,
                    rear_guide,
                    f"Camera_{camera['index']}_Rear_Guide_"
                    f"{rear_index}_Union",
                )
        print(
            f"CAMERA_CRADLE {camera['index']}: support_top={support_top:.2f} "
            f"side_clearance={CAMERA_CRADLE_SIDE_CLEARANCE:.2f} "
            f"rear_clearance={CAMERA_CRADLE_REAR_CLEARANCE:.2f} "
            f"rear_guides={camera_cradle_rear_guides_enabled()} "
            f"rear_air_gap={CAMERA_CRADLE_REAR_GUIDE_CENTER_AIR_GAP:.2f} "
            f"fixed_side_guides={len(guide_specs)} "
            f"side_guide_height="
            f"{(side_guide_height if guide_specs else 0.0):.2f} "
            f"side_guide_radial={side_guide_radial_center:.2f} "
            f"usb_side={camera_usb_side_name()} "
            f"pad_tangents=({pad_tangent_centers[0]:.2f}, "
            f"{pad_tangent_centers[1]:.2f})"
        )
    return base


def polygon_prism_z(name, loop, z0, z1):
    """Create one closed vertical prism from a counter-clockwise XY loop."""
    count = len(loop)
    if count < 3 or z1 <= z0:
        raise ValueError("Polygon prism requires a valid loop and Z interval")
    vertices = [
        (x, y, z)
        for z in (z0, z1)
        for x, y in loop
    ]
    faces = [list(reversed(range(count))), list(range(count, 2 * count))]
    for index in range(count):
        following = (index + 1) % count
        faces.append(
            [index, following, count + following, count + index]
        )
    return create_mesh_object(name, vertices, faces)


def annular_sector_prism(
    name,
    center,
    inner_radius,
    outer_radius,
    angle_start_deg,
    angle_end_deg,
    z0,
    z1,
    samples,
):
    """Create a closed annular-sector prism with radial end faces."""
    samples = max(int(samples), 2)
    angles = [
        math.radians(
            angle_start_deg
            + (angle_end_deg - angle_start_deg) * index / samples
        )
        for index in range(samples + 1)
    ]
    vertices = []
    for z in (z0, z1):
        for radius in (inner_radius, outer_radius):
            vertices.extend(
                (
                    center.x + radius * math.cos(angle),
                    center.y + radius * math.sin(angle),
                    z,
                )
                for angle in angles
            )
    count = samples + 1
    low_inner = 0
    low_outer = count
    high_inner = 2 * count
    high_outer = 3 * count
    faces = []
    for index in range(samples):
        following = index + 1
        faces.extend(
            (
                [
                    low_outer + index,
                    low_outer + following,
                    high_outer + following,
                    high_outer + index,
                ],
                [
                    low_inner + following,
                    low_inner + index,
                    high_inner + index,
                    high_inner + following,
                ],
                [
                    low_inner + index,
                    low_inner + following,
                    low_outer + following,
                    low_outer + index,
                ],
                [
                    high_inner + index,
                    high_outer + index,
                    high_outer + following,
                    high_inner + following,
                ],
            )
        )
    faces.extend(
        (
            [low_inner, low_outer, high_outer, high_inner],
            [
                low_inner + samples,
                high_inner + samples,
                high_outer + samples,
                low_outer + samples,
            ],
        )
    )
    return create_mesh_object(name, vertices, faces)


def gear_tooth_prism(
    name,
    center,
    center_angle_deg,
    root_radius,
    tip_radius,
    root_width_deg,
    tip_width_deg,
    z0,
    z1,
):
    angles = (
        center_angle_deg - root_width_deg / 2.0,
        center_angle_deg - tip_width_deg / 2.0,
        center_angle_deg + tip_width_deg / 2.0,
        center_angle_deg + root_width_deg / 2.0,
    )
    radii = (root_radius, tip_radius, tip_radius, root_radius)
    vertices = []
    for z in (z0, z1):
        for radius, angle_deg in zip(radii, angles):
            angle = math.radians(angle_deg)
            vertices.append(
                (
                    center.x + radius * math.cos(angle),
                    center.y + radius * math.sin(angle),
                    z,
                )
            )
    faces = [
        [0, 3, 2, 1],
        [4, 5, 6, 7],
        [0, 1, 5, 4],
        [1, 2, 6, 5],
        [2, 3, 7, 6],
        [3, 0, 4, 7],
    ]
    return create_mesh_object(name, vertices, faces)


def create_rotating_camera_carrier(camera, mechanism):
    """Create the moving tray, camera guides, sector gear, and pivot bore."""
    body_radial, body_tangent, body_vertical = mission1.canonical_body_bounds(
        CAMERA_UPSIDE_DOWN
    )
    lens_face_radius = camera["radial"] + CAMERA_BODY_DEPTH / 2.0
    tray_z0 = BOTTOM_THICKNESS + CAMERA_CARRIER_BOTTOM_CLEARANCE
    tray_z1 = tray_z0 + CAMERA_CARRIER_TRAY_THICKNESS
    support_top = camera_eye_center_z() + body_vertical[0]
    if tray_z1 >= support_top:
        raise ValueError("Camera carrier tray does not fit below the camera")
    body_radial_center = sum(body_radial) / 2.0
    body_tangent_center = sum(body_tangent) / 2.0
    tray_center = axis_point(
        camera["angle"],
        lens_face_radius + body_radial_center,
        camera["eye_tangent"] + body_tangent_center,
        (tray_z0 + tray_z1) / 2.0,
    )
    carrier = add_beveled_box(
        "Adjustable_Camera_Rotating_Carrier",
        (
            body_radial[1]
            - body_radial[0]
            + 2.0 * CAMERA_CARRIER_TRAY_RADIAL_MARGIN,
            body_tangent[1]
            - body_tangent[0]
            + 2.0 * CAMERA_CARRIER_TRAY_TANGENTIAL_MARGIN,
            CAMERA_CARRIER_TRAY_THICKNESS,
        ),
        tuple(tray_center),
        rotation_z=math.radians(camera["angle"]),
        bevel=0.8,
    )

    def debug_stage(label):
        if CAMERA_CARTRIDGE_DEBUG_MESH_STAGES:
            print(
                f"CARRIER_MESH_STAGE {label}: "
                f"non_manifold={non_manifold_edge_count(carrier)} "
                f"shells={connected_shell_count(carrier)}"
            )

    pad_tangents = camera_support_pad_tangent_centers()
    (
        vent_radial_min,
        vent_radial_max,
        vent_intervals,
        vent_open_area,
        tray_open_area_ratio,
    ) = camera_carrier_tray_airflow_metrics(body_radial, body_tangent)
    for vent_index, (tangent_min, tangent_max) in enumerate(
        vent_intervals,
        start=1,
    ):
        vent_center = axis_point(
            camera["angle"],
            lens_face_radius + (vent_radial_min + vent_radial_max) / 2.0,
            camera["eye_tangent"] + (tangent_min + tangent_max) / 2.0,
            (tray_z0 + tray_z1) / 2.0,
        )
        vent = add_beveled_box(
            f"Adjustable_Carrier_Tray_Air_Bay_{vent_index}",
            (
                vent_radial_max - vent_radial_min,
                tangent_max - tangent_min,
                CAMERA_CARRIER_TRAY_THICKNESS + 2.0 * BOOLEAN_OVERLAP,
            ),
            tuple(vent_center),
            rotation_z=math.radians(camera["angle"]),
            bevel=min(1.0, (tangent_max - tangent_min) / 4.0),
        )
        boolean_difference(
            carrier,
            [vent],
            f"Adjustable_Carrier_Tray_Air_Bay_{vent_index}_Cut",
        )
    debug_stage("tray_vents")

    # Two localized pads preserve cooling air under the camera and use the
    # same feature-aware tangential placement as the original fixed cradle.
    for index, pad_tangent in enumerate(pad_tangents, start=1):
        center = axis_point(
            camera["angle"],
            lens_face_radius + body_radial_center,
            camera["eye_tangent"] + pad_tangent,
            (tray_z1 + support_top) / 2.0,
        )
        pad = add_beveled_box(
            f"Adjustable_Carrier_Support_Pad_{index}",
            (
                CAMERA_SUPPORT_PAD_RADIAL_LENGTH,
                CAMERA_SUPPORT_PAD_TANGENTIAL_WIDTH,
                support_top - tray_z1 + BOOLEAN_OVERLAP,
            ),
            tuple(center),
            rotation_z=math.radians(camera["angle"]),
            bevel=CAMERA_SUPPORT_PAD_EDGE_RADIUS,
        )
        boolean_union(carrier, pad, f"Adjustable_Carrier_Pad_{index}")
    debug_stage("support_pads")

    guide_z0 = tray_z1 - CAMERA_CARRIER_GUIDE_TRAY_EMBED
    guide_z1 = support_top + CAMERA_CARRIER_GUIDE_HEIGHT
    guide_center_z = (guide_z0 + guide_z1) / 2.0
    guide_depth = guide_z1 - guide_z0
    for index, (
        side_name,
        segment_name,
        tangent,
        segment_radial_min,
        segment_radial_max,
    ) in enumerate(
        camera_carrier_side_guide_specs(body_radial, body_tangent),
        start=1,
    ):
        center = axis_point(
            camera["angle"],
            lens_face_radius
            + (segment_radial_min + segment_radial_max) / 2.0,
            camera["eye_tangent"] + tangent,
            guide_center_z,
        )
        guide = add_beveled_box(
            f"Adjustable_Carrier_Side_Guide_{index}_{side_name}_"
            f"{segment_name}",
            (
                segment_radial_max - segment_radial_min,
                CAMERA_CARRIER_GUIDE_THICKNESS,
                guide_depth,
            ),
            tuple(center),
            rotation_z=math.radians(camera["angle"]),
            bevel=0.5,
        )
        boolean_union(
            carrier,
            guide,
            f"Adjustable_Carrier_Side_{index}_{side_name}_{segment_name}",
        )
    debug_stage("side_guides")

    for end_index, (
        end_name,
        end_radial_min,
        end_radial_max,
        end_tangent_min,
        end_tangent_max,
    ) in enumerate(
        camera_carrier_end_guide_specs(body_radial, body_tangent),
        start=1,
    ):
        end_center = axis_point(
            camera["angle"],
            lens_face_radius + (end_radial_min + end_radial_max) / 2.0,
            camera["eye_tangent"]
            + (end_tangent_min + end_tangent_max) / 2.0,
            guide_center_z,
        )
        if end_name == "front_stop":
            root_radial_min = (
                end_radial_min - CAMERA_CARRIER_FRONT_STOP_ROOT_LENGTH
            )
            root_z0 = tray_z0 + BOOLEAN_OVERLAP
            root_z1 = support_top - BOOLEAN_OVERLAP
            root_center = axis_point(
                camera["angle"],
                lens_face_radius
                + (root_radial_min + end_radial_max) / 2.0,
                camera["eye_tangent"]
                + (end_tangent_min + end_tangent_max) / 2.0,
                (root_z0 + root_z1) / 2.0,
            )
            front_root = add_beveled_box(
                "Adjustable_Carrier_Front_Stop_Structural_Root",
                (
                    end_radial_max - root_radial_min,
                    end_tangent_max - end_tangent_min,
                    root_z1 - root_z0,
                ),
                tuple(root_center),
                rotation_z=math.radians(camera["angle"]),
                bevel=0.4,
            )
            if CAMERA_CARTRIDGE_DEBUG_MESH_STAGES:
                _, _, root_overlap = intersection_metrics(
                    carrier,
                    front_root,
                    "debug_carrier_front_stop_root",
                )
                print(
                    "CARRIER_FRONT_STOP_ROOT_OVERLAP "
                    f"volume={root_overlap:.6f}"
                )
            boolean_union(
                carrier,
                front_root,
                "Adjustable_Carrier_Front_Stop_Structural_Root",
                solver="MANIFOLD",
            )
            debug_stage("front_stop_structural_root")
        end_guide = add_beveled_box(
            f"Adjustable_Carrier_End_Guide_{end_index}_{end_name}",
            (
                end_radial_max - end_radial_min,
                end_tangent_max - end_tangent_min,
                guide_depth,
            ),
            tuple(end_center),
            rotation_z=math.radians(camera["angle"]),
            bevel=0.5,
        )
        if CAMERA_CARTRIDGE_DEBUG_MESH_STAGES:
            _, _, end_overlap = intersection_metrics(
                carrier,
                end_guide,
                f"debug_carrier_end_guide_{end_name}",
            )
            print(
                f"CARRIER_END_GUIDE_OVERLAP {end_name}: "
                f"volume={end_overlap:.6f}"
            )
        boolean_union(
            carrier,
            end_guide,
            f"Adjustable_Carrier_End_Guide_{end_index}_{end_name}",
            solver="MANIFOLD" if end_name == "front_stop" else None,
        )
        debug_stage(f"end_guide_{end_name}")
    debug_stage("end_guides")

    pivot = mechanism["pivot"]
    pitch_radius = camera_sector_pitch_radius()
    root_radius = camera_sector_root_radius()
    tip_radius = camera_sector_tip_radius()
    gear_z0 = (
        BOTTOM_THICKNESS
        + CAMERA_WORM_FLOOR_CLEARANCE
        + camera_worm_outer_radius()
        - CAMERA_GEAR_FACE_WIDTH / 2.0
    )
    gear_z1 = gear_z0 + CAMERA_GEAR_FACE_WIDTH
    sector_start, sector_end, sector_contact = (
        adjustable_sector_local_angles(camera)
    )
    global_start = camera["angle"] + sector_start
    global_end = camera["angle"] + sector_end
    tooth_pitch_deg = 360.0 / CAMERA_GEAR_EQUIVALENT_TEETH
    sector_samples = max(
        12,
        int(
            math.ceil(
                (global_end - global_start)
                / tooth_pitch_deg
                * CAMERA_GEAR_SECTOR_SAMPLES_PER_TOOTH
            )
        ),
    )
    lower_sector = annular_sector_prism(
        "Adjustable_Carrier_Gear_Lower_Web",
        pivot,
        max(CAMERA_GEAR_RIM_INNER_RADIUS - 7.0, 1.0),
        tip_radius,
        global_start,
        global_end,
        tray_z0,
        tray_z1 + BOOLEAN_OVERLAP,
        sector_samples,
    )
    boolean_union(carrier, lower_sector, "Adjustable_Carrier_Gear_Lower_Web")
    debug_stage("gear_lower_web")
    rim = annular_sector_prism(
        "Adjustable_Carrier_Gear_Rim",
        pivot,
        CAMERA_GEAR_RIM_INNER_RADIUS,
        root_radius + BOOLEAN_OVERLAP,
        global_start,
        global_end,
        tray_z1 - BOOLEAN_OVERLAP,
        gear_z1,
        sector_samples,
    )
    boolean_union(carrier, rim, "Adjustable_Carrier_Gear_Rim")
    debug_stage("gear_rim")
    backlash_angle = math.degrees(
        CAMERA_GEAR_BACKLASH / max(pitch_radius, 1e-6)
    )
    root_width = max(
        tooth_pitch_deg * CAMERA_GEAR_TOOTH_ROOT_FRACTION - backlash_angle,
        tooth_pitch_deg * 0.25,
    )
    tip_width = max(
        tooth_pitch_deg * CAMERA_GEAR_TOOTH_TIP_FRACTION - backlash_angle,
        tooth_pitch_deg * 0.18,
    )
    tooth_centers = []
    tooth_index = 0
    while True:
        added = False
        for signed_index in ((0,) if tooth_index == 0 else (-tooth_index, tooth_index)):
            center_angle = (
                camera["angle"]
                + sector_contact
                + signed_index * tooth_pitch_deg
            )
            if (
                center_angle - root_width / 2.0 >= global_start - 1e-6
                and center_angle + root_width / 2.0 <= global_end + 1e-6
            ):
                tooth_centers.append(center_angle)
                added = True
        if not added and tooth_index * tooth_pitch_deg > (
            global_end - global_start
        ):
            break
        tooth_index += 1
    for index, center_angle in enumerate(sorted(set(tooth_centers)), start=1):
        tooth = gear_tooth_prism(
            f"Adjustable_Carrier_Gear_Tooth_{index}",
            pivot,
            center_angle,
            root_radius - BOOLEAN_OVERLAP,
            tip_radius,
            root_width,
            tip_width,
            gear_z0,
            gear_z1,
        )
        boolean_union(carrier, tooth, f"Adjustable_Carrier_Gear_Tooth_{index}")
    debug_stage("gear_teeth")

    # A broad, low web ties the arcuate hard-stop slot into the pivot region.
    # It replaces the fragile/outboard stop-arm alternatives while remaining
    # below the camera and inside its plan footprint.
    stop_inner_radius, stop_outer_radius = (
        camera_hard_stop_reinforcement_radii()
    )
    stop_margin_angle = camera_hard_stop_reinforcement_angular_margin_deg()
    stop_reinforcement_top = (
        tray_z1 + CAMERA_HARD_STOP_SLOT_REINFORCEMENT_EXTRA_HEIGHT
    )
    stop_web = annular_sector_prism(
        "Adjustable_Carrier_Hard_Stop_Reinforcement_Web",
        pivot,
        stop_inner_radius,
        stop_outer_radius,
        mechanism["hard_stop_slot_start_deg"] - stop_margin_angle,
        mechanism["hard_stop_slot_end_deg"] + stop_margin_angle,
        tray_z0,
        stop_reinforcement_top,
        64,
    )
    boolean_union(
        carrier,
        stop_web,
        "Adjustable_Carrier_Hard_Stop_Reinforcement_Web",
        solver="MANIFOLD",
    )
    slot_half_width = camera_hard_stop_slot_half_width()
    stop_slot = annular_sector_prism(
        "Adjustable_Carrier_Hard_Stop_Arc_Slot",
        pivot,
        CAMERA_HARD_STOP_SLOT_RADIUS - slot_half_width,
        CAMERA_HARD_STOP_SLOT_RADIUS + slot_half_width,
        mechanism["hard_stop_slot_start_deg"],
        mechanism["hard_stop_slot_end_deg"],
        tray_z0 - BOOLEAN_OVERLAP,
        stop_reinforcement_top + BOOLEAN_OVERLAP,
        48,
    )
    boolean_difference(
        carrier,
        [stop_slot],
        "Adjustable_Carrier_Hard_Stop_Arc_Slot",
        solver="MANIFOLD",
    )
    for index, end_angle_deg in enumerate(
        (
            mechanism["hard_stop_slot_start_deg"],
            mechanism["hard_stop_slot_end_deg"],
        ),
        start=1,
    ):
        end_angle = math.radians(end_angle_deg)
        end_cap = add_cylinder_z(
            f"Adjustable_Carrier_Hard_Stop_Slot_End_{index}",
            slot_half_width,
            tray_z0 - 2.0 * BOOLEAN_OVERLAP,
            stop_reinforcement_top + 2.0 * BOOLEAN_OVERLAP,
            pivot.x + CAMERA_HARD_STOP_SLOT_RADIUS * math.cos(end_angle),
            pivot.y + CAMERA_HARD_STOP_SLOT_RADIUS * math.sin(end_angle),
        )
        boolean_difference(
            carrier,
            [end_cap],
            f"Adjustable_Carrier_Hard_Stop_Slot_End_{index}",
            solver="MANIFOLD",
        )
    debug_stage("reinforced_hard_stop_slot")

    pivot_hole = add_cylinder_z(
        "Adjustable_Carrier_Pivot_Bore",
        CAMERA_CARRIER_PIVOT_PIN_DIAMETER / 2.0
        + CAMERA_CARRIER_PIVOT_CLEARANCE / 2.0,
        tray_z0 - BOOLEAN_OVERLAP,
        tray_z1 + BOOLEAN_OVERLAP,
        pivot.x,
        pivot.y,
    )
    boolean_difference(carrier, [pivot_hole], "Adjustable_Carrier_Pivot_Bore")
    if CAMERA_CARRIER_REMOVE_SMALL_FRAGMENTS:
        remove_small_disconnected_shells(
            carrier,
            CAMERA_CARRIER_MAX_FRAGMENT_FACES,
            CAMERA_CARRIER_MAX_FRAGMENT_VOLUME,
            CAMERA_CARRIER_MAX_FRAGMENT_EXTENT,
            "Adjustable_Camera_Rotating_Carrier",
        )
    debug_stage("pivot_bore")
    carrier.name = "Adjustable_Camera_Rotating_Carrier"
    carrier["pivot_x"] = pivot.x
    carrier["pivot_y"] = pivot.y
    carrier["gear_pitch_radius"] = pitch_radius
    carrier["gear_equivalent_teeth"] = CAMERA_GEAR_EQUIVALENT_TEETH
    carrier["yaw_range_deg"] = ADJUSTABLE_CAMERA_YAW_RANGE_DEG
    carrier["tray_vent_open_area_mm2"] = vent_open_area
    carrier["tray_vent_open_area_ratio"] = tray_open_area_ratio
    carrier["under_camera_air_gap_mm"] = CAMERA_FLOOR_CLEARANCE
    carrier["rear_air_channel_width_mm"] = (
        CAMERA_CARRIER_REAR_GUIDE_CENTER_AIR_GAP
    )
    carrier["hard_stop_slot_radius_mm"] = CAMERA_HARD_STOP_SLOT_RADIUS
    carrier["hard_stop_slot_width_mm"] = 2.0 * slot_half_width
    carrier["hard_stop_reinforcement_width_mm"] = (
        CAMERA_HARD_STOP_SLOT_REINFORCEMENT_WIDTH
    )
    conservative_open_area = max(
        vent_open_area - camera_hard_stop_reinforcement_plan_area(),
        0.0,
    )
    camera_plan_area = vent_open_area / tray_open_area_ratio
    conservative_open_ratio = conservative_open_area / camera_plan_area
    print(
        "CAMERA_CARTRIDGE_AIRFLOW "
        f"tray_open_area={vent_open_area:.1f}mm^2 "
        f"camera_plan_open_ratio={tray_open_area_ratio:.3f} "
        f"conservative_reinforced_open_area={conservative_open_area:.1f}mm^2 "
        f"conservative_reinforced_open_ratio={conservative_open_ratio:.3f} "
        f"under_camera_gap={CAMERA_FLOOR_CLEARANCE:.2f} "
        f"rear_channel={CAMERA_CARRIER_REAR_GUIDE_CENTER_AIR_GAP:.2f} "
        f"side_guide_segments="
        f"{len(camera_carrier_side_guide_specs(body_radial, body_tangent))}"
    )
    print(
        "CAMERA_CARTRIDGE_THRUST_STACK "
        f"printed_pad={CAMERA_CARRIER_THRUST_PAD_HEIGHT:.2f} "
        f"washer={CAMERA_CARRIER_THRUST_WASHER_OD:.2f}ODx"
        f"{CAMERA_CARRIER_THRUST_WASHER_ID:.2f}IDx"
        f"{CAMERA_CARRIER_THRUST_WASHER_THICKNESS:.2f} "
        f"running_clearance={CAMERA_CARRIER_THRUST_RUNNING_CLEARANCE:.2f} "
        f"pivot_engagement="
        f"{CAMERA_CARRIER_PIVOT_PIN_HEIGHT - CAMERA_CARRIER_BOTTOM_CLEARANCE:.2f}"
    )
    print(
        "CAMERA_WORM_DRIVE_PROTOTYPE_WARNING "
        "printed_sector=radial_trapezoid_not_conjugate_worm_wheel "
        "physical_mesh_and_load_test_required=True "
        "matched_purchased_worm_wheel_preferred_for_production=True"
    )
    return carrier


def worm_thread_ridge(
    name,
    center,
    shaft_direction,
    z_center,
    axial_hand=1.0,
    radial_phase_offset=0.0,
):
    """Create a closed trapezoidal helical ridge around the worm shaft."""
    lead = (
        math.pi
        * CAMERA_GEAR_MODULE
        * CAMERA_WORM_STARTS
        * (1.0 if axial_hand >= 0.0 else -1.0)
    )
    # Sink the ridge root into the cylindrical core; exact tangency creates
    # four-face edges when the Boolean samples the helix near a quadrant.
    root_radius = camera_worm_root_radius() - BOOLEAN_OVERLAP
    tip_radius = camera_worm_outer_radius()
    root_width = math.pi * CAMERA_GEAR_MODULE * 0.72
    tip_width = math.pi * CAMERA_GEAR_MODULE * 0.36
    turns = CAMERA_WORM_LENGTH / abs(lead)
    steps = max(96, int(math.ceil(turns * 40.0)))
    start_phase = -math.pi * turns
    end_phase = math.pi * turns
    horizontal_perpendicular = Vector(
        (-shaft_direction.y, shaft_direction.x, 0.0)
    )
    vertices = []
    for index in range(steps + 1):
        phase = start_phase + (end_phase - start_phase) * index / steps
        axial_center = lead * phase / (2.0 * math.pi)
        radial_phase = phase + radial_phase_offset
        radial_direction = (
            horizontal_perpendicular * math.cos(radial_phase)
            + Vector((0.0, 0.0, 1.0)) * math.sin(radial_phase)
        )
        for radius, width in (
            (root_radius, root_width),
            (tip_radius, tip_width),
            (tip_radius, -tip_width),
            (root_radius, -root_width),
        ):
            point = (
                center
                + shaft_direction * (axial_center + width / 2.0)
                + radial_direction * radius
            )
            vertices.append(tuple(point))
    faces = []
    for index in range(steps):
        current = index * 4
        following = (index + 1) * 4
        for edge in range(4):
            next_edge = (edge + 1) % 4
            faces.append(
                [
                    current + edge,
                    current + next_edge,
                    following + next_edge,
                    following + edge,
                ]
            )
    faces.append([0, 1, 2, 3])
    last = steps * 4
    faces.append([last, last + 3, last + 2, last + 1])
    return create_mesh_object(name, vertices, faces)


def create_camera_worm(mechanism):
    center = Vector(
        (
            mechanism["worm_center"].x,
            mechanism["worm_center"].y,
            BOTTOM_THICKNESS
            + CAMERA_WORM_FLOOR_CLEARANCE
            + camera_worm_outer_radius(),
        )
    )
    direction = mechanism["shaft_direction"]
    angle_deg = mechanism["shaft_angle_deg"]
    angle = math.radians(angle_deg)
    tangent_axis = (-math.sin(angle), math.cos(angle))
    center_radial = center.x * math.cos(angle) + center.y * math.sin(angle)
    center_tangent = center.x * tangent_axis[0] + center.y * tangent_axis[1]
    core = cylinder_prism_axis(
        "Adjustable_Camera_Worm_Core",
        angle_deg,
        center_radial - CAMERA_WORM_LENGTH / 2.0,
        center_radial + CAMERA_WORM_LENGTH / 2.0,
        camera_worm_root_radius(),
        center_tangent,
        center.z,
        segments=96,
    )
    mesh_tangent = Vector(
        (-mechanism["gear_direction"].y, mechanism["gear_direction"].x, 0.0)
    )
    shaft_alignment = mechanism["shaft_direction"].dot(mesh_tangent)
    # The directed shaft axis flips when the same purchased right-hand worm is
    # installed from the opposite enclosure side.  Reverse the procedural
    # axial parameter so the reference solid keeps the same physical hand.
    axial_hand = -1.0 if shaft_alignment > 0.0 else 1.0
    ridge = worm_thread_ridge(
        "Adjustable_Camera_Worm_Helical_Thread",
        center,
        direction,
        center.z,
        axial_hand=axial_hand,
        radial_phase_offset=math.pi if axial_hand < 0.0 else 0.0,
    )
    boolean_union(core, ridge, "Adjustable_Camera_Worm_Thread")
    bore = cylinder_prism_axis(
        "Adjustable_Camera_Worm_Shaft_Bore",
        angle_deg,
        center_radial - CAMERA_WORM_LENGTH / 2.0 - BOOLEAN_OVERLAP,
        center_radial + CAMERA_WORM_LENGTH / 2.0 + BOOLEAN_OVERLAP,
        (
            CAMERA_WORM_SHAFT_DIAMETER
            + CAMERA_WORM_SHAFT_CLEARANCE
        )
        / 2.0,
        center_tangent,
        center.z,
        segments=72,
    )
    boolean_difference(core, [bore], "Adjustable_Camera_Worm_Shaft_Bore")
    # The helical ridge can leave a micron-scale four-face edge where a turn is
    # exactly tangent to the core.  Collapse only those zero-length artifacts;
    # a general remove-doubles pass would soften legitimate thread vertices.
    bm = bmesh.new()
    bm.from_mesh(core.data)
    tangent_artifacts = [
        edge
        for edge in bm.edges
        if len(edge.link_faces) > 2 and edge.calc_length() < 0.01
    ]
    if tangent_artifacts:
        bmesh.ops.collapse(bm, edges=tangent_artifacts)
    bmesh.ops.dissolve_degenerate(
        bm,
        edges=list(bm.edges),
        dist=BOOLEAN_CLEANUP_DISTANCE,
    )
    bm.to_mesh(core.data)
    bm.free()
    core.data.update()
    recalc_normals(core)
    core.name = "Purchased_Module_0_5_One_Start_Worm_Reference"
    core["module"] = CAMERA_GEAR_MODULE
    core["starts"] = CAMERA_WORM_STARTS
    core["wheel_ratio"] = CAMERA_GEAR_EQUIVALENT_TEETH / CAMERA_WORM_STARTS
    core["amazon_asin"] = "B0DFCVMC1M"
    core["hardware_reference_only"] = True
    core["procedural_axial_hand"] = axial_hand
    return core


def add_adjustable_camera_base_hardware(base, cameras, footprint):
    mechanism = adjustable_mechanism_layout(cameras, footprint)
    if mechanism is None:
        return base
    pivot = mechanism["pivot"]
    moving_camera = mechanism["camera"]
    sweep_margin = 0.60
    sector_start, sector_end, _ = adjustable_sector_local_angles(
        moving_camera
    )
    sweep_start = (
        moving_camera["angle"]
        + sector_start
        - ADJUSTABLE_CAMERA_YAW_RANGE_DEG
        - 1.0
    )
    sweep_end = (
        moving_camera["angle"]
        + sector_end
        + ADJUSTABLE_CAMERA_YAW_RANGE_DEG
        + 1.0
    )
    gear_sweep_cutter = annular_sector_prism(
        "Adjustable_Carrier_Full_Range_Clearance",
        pivot,
        max(CAMERA_GEAR_RIM_INNER_RADIUS - 7.0 - sweep_margin, 1.0),
        camera_sector_tip_radius() + sweep_margin,
        sweep_start,
        sweep_end,
        BOTTOM_THICKNESS + CAMERA_CARRIER_BOTTOM_CLEARANCE - 0.05,
        (
            BOTTOM_THICKNESS
            + CAMERA_WORM_FLOOR_CLEARANCE
            + camera_worm_outer_radius()
            + CAMERA_GEAR_FACE_WIDTH / 2.0
            + sweep_margin
        ),
        max(
            24,
            int(
                math.ceil(
                    (sweep_end - sweep_start)
                    / (360.0 / CAMERA_GEAR_EQUIVALENT_TEETH)
                    * CAMERA_GEAR_SECTOR_SAMPLES_PER_TOOTH
                )
            ),
        ),
    )
    hardware_gear_sweep_cutter = duplicate_object(
        gear_sweep_cutter,
        "Adjustable_Carrier_Bearing_Hardware_Full_Range_Clearance",
    )
    boolean_difference(
        base,
        [gear_sweep_cutter],
        "Adjustable_Carrier_Full_Range_Clearance",
    )
    # The camera-side guide comes within a fraction of a millimeter of the
    # inside eye wall at the negative yaw endpoint.  Cut only the swept guide
    # envelopes out of the stationary shell; this preserves the external body
    # size and leaves almost the full wall thickness behind the shallow notch.
    body_radial, body_tangent, body_vertical = (
        mission1.canonical_body_bounds(CAMERA_UPSIDE_DOWN)
    )
    guide_z0 = (
        BOTTOM_THICKNESS
        + CAMERA_CARRIER_BOTTOM_CLEARANCE
        + CAMERA_CARRIER_TRAY_THICKNESS
        - CAMERA_CARRIER_GUIDE_TRAY_EMBED
    )
    guide_z1 = (
        camera_eye_center_z()
        + body_vertical[0]
        + CAMERA_CARRIER_GUIDE_HEIGHT
    )
    guide_clearance = CAMERA_CARRIER_SWEEP_CUT_CLEARANCE
    def cut_swept_carrier_member(
        member_name,
        radial_bounds,
        tangent_bounds,
        z_bounds,
        cutter_index,
    ):
        """Relieve the base for one rigid carrier member over full yaw."""
        sweep_points = []
        for yaw_delta in adjustable_yaw_samples():
            sweep_points.extend(
                adjustable_camera_pose_corners(
                    moving_camera,
                    (
                        radial_bounds[0] - guide_clearance,
                        radial_bounds[1] + guide_clearance,
                    ),
                    (
                        tangent_bounds[0] - guide_clearance,
                        tangent_bounds[1] + guide_clearance,
                    ),
                    yaw_delta,
                )
            )
        cutter = polygon_prism_z(
            f"Adjustable_Carrier_{member_name}_Sweep_Clearance",
            convex_hull_2d(sweep_points),
            z_bounds[0] - guide_clearance,
            z_bounds[1] + guide_clearance,
        )
        # Apply each already-unified swept prism separately.  Joining dozens
        # of overlapping pose boxes into one self-intersecting cutter can make
        # Blender's exact Boolean detach otherwise healthy shell regions.
        boolean_difference(
            base,
            [cutter],
            f"Adjustable_Carrier_Member_Sweep_Clearance_{cutter_index}",
        )

    # Relieve the inner wall for the tray's complete yaw envelope too.  The
    # analytical footprint keeps almost all of it inside already, but the
    # rounded tray corners otherwise make small solid contacts with the shell
    # at both configured yaw endpoints.  This cutter starts above the floor,
    # so it creates only shallow internal wall pockets and cannot open the
    # enclosure bottom.
    tray_z0 = BOTTOM_THICKNESS + CAMERA_CARRIER_BOTTOM_CLEARANCE
    tray_z1 = tray_z0 + CAMERA_CARRIER_TRAY_THICKNESS
    cutter_index = 1
    cut_swept_carrier_member(
        "tray",
        (
            body_radial[0] - CAMERA_CARRIER_TRAY_RADIAL_MARGIN,
            body_radial[1] + CAMERA_CARRIER_TRAY_RADIAL_MARGIN,
        ),
        (
            body_tangent[0] - CAMERA_CARRIER_TRAY_TANGENTIAL_MARGIN,
            body_tangent[1] + CAMERA_CARRIER_TRAY_TANGENTIAL_MARGIN,
        ),
        (tray_z0, tray_z1),
        cutter_index,
    )
    guide_specs = camera_carrier_side_guide_specs(
        body_radial,
        body_tangent,
    )
    for guide_index, (
        side_name,
        segment_name,
        guide_tangent,
        guide_radial_min,
        guide_radial_max,
    ) in enumerate(guide_specs, start=1):
        cutter_index += 1
        cut_swept_carrier_member(
            f"{side_name}_{segment_name}",
            (guide_radial_min, guide_radial_max),
            (
                guide_tangent - CAMERA_CARRIER_GUIDE_THICKNESS / 2.0,
                guide_tangent + CAMERA_CARRIER_GUIDE_THICKNESS / 2.0,
            ),
            (guide_z0, guide_z1),
            cutter_index,
        )
    end_guide_specs = camera_carrier_end_guide_specs(
        body_radial,
        body_tangent,
    )
    for (
        end_name,
        end_radial_min,
        end_radial_max,
        end_tangent_min,
        end_tangent_max,
    ) in end_guide_specs:
        cutter_index += 1
        cut_swept_carrier_member(
            end_name,
            (end_radial_min, end_radial_max),
            (end_tangent_min, end_tangent_max),
            (guide_z0, guide_z1),
            cutter_index,
        )
        if end_name == "front_stop":
            support_top = camera_eye_center_z() + body_vertical[0]
            cutter_index += 1
            cut_swept_carrier_member(
                "front_stop_structural_root",
                (
                    end_radial_min
                    - CAMERA_CARRIER_FRONT_STOP_ROOT_LENGTH,
                    end_radial_max,
                ),
                (end_tangent_min, end_tangent_max),
                (
                    tray_z0 + BOOLEAN_OVERLAP,
                    support_top - BOOLEAN_OVERLAP,
                ),
                cutter_index,
            )
    thrust = add_cylinder_z(
        "Adjustable_Carrier_Thrust_Pad",
        CAMERA_CARRIER_THRUST_PAD_DIAMETER / 2.0,
        BOTTOM_THICKNESS - BOOLEAN_OVERLAP,
        BOTTOM_THICKNESS + CAMERA_CARRIER_THRUST_PAD_HEIGHT,
        pivot.x,
        pivot.y,
    )
    boolean_union(base, thrust, "Adjustable_Carrier_Thrust_Pad")
    pivot_pin = add_cylinder_z(
        "Adjustable_Carrier_Pivot_Pin",
        CAMERA_CARRIER_PIVOT_PIN_DIAMETER / 2.0,
        BOTTOM_THICKNESS - BOOLEAN_OVERLAP,
        BOTTOM_THICKNESS + CAMERA_CARRIER_PIVOT_PIN_HEIGHT,
        pivot.x,
        pivot.y,
    )
    boolean_union(base, pivot_pin, "Adjustable_Carrier_Pivot_Pin")

    worm_z = (
        BOTTOM_THICKNESS
        + CAMERA_WORM_FLOOR_CLEARANCE
        + camera_worm_outer_radius()
    )
    block_z0 = BOTTOM_THICKNESS - BOOLEAN_OVERLAP
    block_z1 = (
        worm_z
        + CAMERA_WORM_BEARING_OD / 2.0
        + CAMERA_WORM_BLOCK_TOP_CLEARANCE
    )
    for label, point in (
        ("Inner", mechanism["inner_block"]),
        ("Outer", mechanism["outer_block"]),
    ):
        block = add_beveled_box(
            f"Adjustable_Worm_{label}_Bearing_Block",
            (
                CAMERA_WORM_BLOCK_LENGTH,
                CAMERA_WORM_BLOCK_WIDTH,
                block_z1 - block_z0,
            ),
            (point.x, point.y, (block_z0 + block_z1) / 2.0),
            rotation_z=math.radians(mechanism["shaft_angle_deg"]),
            bevel=0.8,
        )
        boolean_union(base, block, f"Adjustable_Worm_{label}_Bearing_Block")

    direction = mechanism["shaft_direction"]
    shaft_angle = mechanism["shaft_angle_deg"]
    shaft_radians = math.radians(shaft_angle)
    shaft_tangent = (-math.sin(shaft_radians), math.cos(shaft_radians))
    wall_point = mechanism["wall_point"]
    wall_radial = wall_point.x * direction.x + wall_point.y * direction.y
    line_tangent = (
        wall_point.x * shaft_tangent[0] + wall_point.y * shaft_tangent[1]
    )
    boss = cylinder_prism_axis(
        "Adjustable_Worm_External_Port_Boss",
        shaft_angle,
        wall_radial - CAMERA_WORM_PORT_INWARD_EXTENSION,
        wall_radial + CAMERA_WORM_PORT_OUTSET,
        CAMERA_WORM_PORT_BOSS_RADIUS,
        line_tangent,
        worm_z,
        segments=72,
    )
    boolean_union(base, boss, "Adjustable_Worm_External_Port_Boss")

    inner_point = mechanism["inner_block"]
    inner_radial = inner_point.x * direction.x + inner_point.y * direction.y
    shaft_radius = (
        CAMERA_WORM_SHAFT_DIAMETER + CAMERA_WORM_SHAFT_CLEARANCE
    ) / 2.0
    shaft_cutter = cylinder_prism_axis(
        "Adjustable_Worm_Shaft_Passage",
        shaft_angle,
        inner_radial - CAMERA_WORM_BLOCK_LENGTH / 2.0 - BOOLEAN_OVERLAP,
        wall_radial + CAMERA_WORM_PORT_OUTSET + BOOLEAN_OVERLAP,
        shaft_radius,
        line_tangent,
        worm_z,
        segments=72,
    )
    bearing_radius = (
        CAMERA_WORM_BEARING_OD
        + CAMERA_WORM_BEARING_POCKET_DIAMETER_ADJUSTMENT
    ) / 2.0
    pocket_cutters = []
    for label, point, facing_sign in (
        ("Inner", mechanism["inner_block"], 1.0),
        ("Outer", mechanism["outer_block"], -1.0),
    ):
        center_projection = point.x * direction.x + point.y * direction.y
        face_projection = (
            center_projection
            + facing_sign * CAMERA_WORM_BLOCK_LENGTH / 2.0
        )
        pocket_end = (
            face_projection
            - facing_sign
            * (
                CAMERA_WORM_BEARING_WIDTH
                + CAMERA_WORM_BEARING_POCKET_DEPTH_CLEARANCE
            )
        )
        pocket_cutters.append(
            cylinder_prism_axis(
                f"Adjustable_Worm_{label}_Bearing_Pocket",
                shaft_angle,
                min(face_projection, pocket_end) - BOOLEAN_OVERLAP,
                max(face_projection, pocket_end) + BOOLEAN_OVERLAP,
                bearing_radius,
                line_tangent,
                worm_z,
                segments=72,
            )
        )
    # These cutters overlap concentrically.  Apply them in separate Boolean
    # stages; a single joined multi-shell tool leaves coincident cutter faces
    # in Blender's exact solver and can create non-manifold bearing edges.
    boolean_difference(
        base,
        [shaft_cutter],
        "Adjustable_Worm_Shaft_Passage",
    )
    for index, pocket in enumerate(pocket_cutters, start=1):
        boolean_difference(
            base,
            [pocket],
            f"Adjustable_Worm_Bearing_Pocket_{index}",
        )
    # The bearing blocks are added after the main shell sweep cut.  Notch only
    # their carrier-facing corners with the same full-range envelope.
    boolean_difference(
        base,
        [hardware_gear_sweep_cutter],
        "Adjustable_Carrier_Bearing_Hardware_Full_Range_Clearance",
    )
    stop_pin_top = (
        BOTTOM_THICKNESS
        + CAMERA_CARRIER_BOTTOM_CLEARANCE
        + CAMERA_CARRIER_TRAY_THICKNESS
        + CAMERA_HARD_STOP_SLOT_REINFORCEMENT_EXTRA_HEIGHT
        - 0.05
    )
    stop_x, stop_y = mechanism["hard_stop_pin_position"]
    stop = add_cylinder_z(
        "Adjustable_Camera_Under_Tray_Hard_Stop_Pin",
        CAMERA_HARD_STOP_PIN_DIAMETER / 2.0,
        BOTTOM_THICKNESS - BOOLEAN_OVERLAP,
        stop_pin_top,
        stop_x,
        stop_y,
    )
    boolean_union(base, stop, "Adjustable_Camera_Under_Tray_Hard_Stop_Pin")
    endpoint_stop_surface_gap = camera_hard_stop_remaining_travel(
        mechanism["hard_stop_limit_deg"],
        ADJUSTABLE_CAMERA_YAW_RANGE_DEG,
    )
    print(
        "ADJUSTABLE_CAMERA_MECHANISM "
        f"pivot=({pivot.x:.2f},{pivot.y:.2f}) "
        f"gear_pitch_radius={camera_sector_pitch_radius():.2f} "
        f"worm_center=({mechanism['worm_center'].x:.2f},"
        f"{mechanism['worm_center'].y:.2f},{worm_z:.2f}) "
        f"shaft_exit=({wall_point.x:.2f},{wall_point.y:.2f}) "
        f"wall_run={mechanism['wall_distance']:.2f} "
        f"hard_stop_limit={mechanism['hard_stop_limit_deg']:.2f}deg "
        f"slot_center_limit="
        f"{mechanism['hard_stop_slot_center_limit_deg']:.2f}deg "
        f"hard_stop=reinforced_under_tray_arc_slot "
        f"slot_radius={CAMERA_HARD_STOP_SLOT_RADIUS:.2f}mm "
        f"pin_diameter={CAMERA_HARD_STOP_PIN_DIAMETER:.2f}mm "
        f"endpoint_stop_gap={endpoint_stop_surface_gap:.2f}mm"
    )
    print(
        "ADJUSTABLE_WORM_HARDWARE "
        f"bearing_pocket_diameter="
        f"{CAMERA_WORM_BEARING_OD + CAMERA_WORM_BEARING_POCKET_DIAMETER_ADJUSTMENT:.2f} "
        f"worm_end_gap={CAMERA_WORM_BLOCK_OFFSET:.2f} "
        f"thrust_washer={CAMERA_WORM_THRUST_WASHER_THICKNESS:.2f} "
        f"axial_running_clearance={CAMERA_WORM_AXIAL_RUNNING_CLEARANCE:.2f} "
        "shaft_retention=4mm_collars_or_E-clips_outside_both_bearings"
    )
    print(
        "ADJUSTABLE_WORM_TORQUE_WARNING "
        f"do_not_exceed={CAMERA_WORM_MAX_INPUT_TORQUE_NMM:.2f}Nmm "
        f"idealized_stop_force_at_limit="
        f"{CAMERA_WORM_MAX_INPUT_TORQUE_NMM * CAMERA_GEAR_EQUIVALENT_TEETH / CAMERA_WORM_STARTS / CAMERA_HARD_STOP_SLOT_RADIUS:.2f}N "
        "do_not_crank_against_hard_stops=True"
    )
    return base


def camera_bracket_z_bounds():
    highest_feature = camera_eye_center_z() + mission1.canonical_vertical_bounds(
        CAMERA_UPSIDE_DOWN
    )[1]
    underside = highest_feature + CAMERA_BRACKET_TOP_FEATURE_CLEARANCE_Z
    return underside, underside + CAMERA_BRACKET_THICKNESS


def camera_bracket_clamp_travel():
    return (
        CAMERA_BRACKET_BODY_CONTACT_CLEARANCE_Z
        + CAMERA_BRACKET_CLAMP_PRELOAD_Z
    )


def add_camera_bracket_posts(base, bracket_position_pairs):
    if not CAMERA_BRACKETS_ENABLED:
        return base
    positions = [position for pair in bracket_position_pairs for position in pair]
    bracket_underside, _ = camera_bracket_z_bounds()
    post_top = bracket_underside - camera_bracket_clamp_travel()
    for index, (x, y) in enumerate(positions, start=1):
        post = add_tapered_cylinder_z(
            f"Camera_Bracket_Heat_Insert_Post_{index}",
            CAMERA_BRACKET_POST_BASE_DIAMETER / 2.0,
            FASTENER_POST_DIAMETER / 2.0,
            BOTTOM_THICKNESS - BOOLEAN_OVERLAP,
            post_top,
            x,
            y,
        )
        boolean_union(base, post, f"Camera_Bracket_Post_{index}_Union")

    insert_cutters = [
        add_cylinder_z(
            f"Camera_Bracket_Heat_Insert_Hole_{index}",
            HEAT_INSERT_HOLE_DIAMETER / 2.0,
            post_top - HEAT_INSERT_HOLE_DEPTH,
            post_top + BOOLEAN_OVERLAP,
            x,
            y,
        )
        for index, (x, y) in enumerate(positions, start=1)
    ]
    boolean_difference(base, insert_cutters, "Camera_Bracket_Heat_Insert_Holes")
    if HEAT_INSERT_LEADIN_DEPTH > 0.0:
        leadin_cutters = [
            add_cylinder_z(
                f"Camera_Bracket_Heat_Insert_Leadin_{index}",
                HEAT_INSERT_LEADIN_DIAMETER / 2.0,
                post_top - HEAT_INSERT_LEADIN_DEPTH,
                post_top + 2.0 * BOOLEAN_OVERLAP,
                x,
                y,
            )
            for index, (x, y) in enumerate(positions, start=1)
        ]
        boolean_difference(
            base,
            leadin_cutters,
            "Camera_Bracket_Heat_Insert_Leadins",
        )
    return base


def add_bottom_mount_hole(base, position):
    if not BOTTOM_MOUNT_HOLE_ENABLED or position is None:
        return base
    x, y = position
    if BOTTOM_MOUNT_NUT_HOLDER_ENABLED:
        holder_top = bottom_mount_nut_holder_top_z()
        holder = add_cylinder_z(
            "Bottom_Mount_Captive_Nut_Structural_Boss",
            BOTTOM_MOUNT_NUT_HOLDER_OUTER_DIAMETER / 2.0,
            BOTTOM_THICKNESS - BOOLEAN_OVERLAP,
            holder_top,
            x,
            y,
        )

        pocket_across_flats = bottom_mount_nut_pocket_across_flats()
        rotation = math.radians(BOTTOM_MOUNT_NUT_ROTATION_DEG)
        pocket = add_hex_prism_z(
            "Bottom_Mount_Captive_Nut_Press_Fit_Pocket",
            pocket_across_flats,
            bottom_mount_nut_seat_z(),
            holder_top + BOOLEAN_OVERLAP,
            x,
            y,
            rotation_z=rotation,
        )
        boolean_difference(
            holder,
            [pocket],
            "Bottom_Mount_Captive_Nut_Press_Fit_Pocket",
        )

        lip_z0 = bottom_mount_nut_snap_shoulder_z()
        lip_z1 = lip_z0 + BOTTOM_MOUNT_NUT_SNAP_LIP_HEIGHT
        pocket_apothem = pocket_across_flats / 2.0
        back_relief_cutters = []
        side_slot_cutters = []
        if BOTTOM_MOUNT_NUT_SNAP_RELIEF_ENABLED:
            relief_z0 = bottom_mount_nut_snap_relief_base_z()
            relief_z1 = holder_top + BOOLEAN_OVERLAP
            flex_wall = BOTTOM_MOUNT_NUT_SNAP_FLEX_WALL_THICKNESS
            relief_depth = BOTTOM_MOUNT_NUT_SNAP_RELIEF_DEPTH
            side_slot = BOTTOM_MOUNT_NUT_SNAP_SIDE_SLOT_WIDTH
            for relief_index in range(6):
                face_angle = rotation + math.radians(
                    60.0 * relief_index
                )
                normal = (math.cos(face_angle), math.sin(face_angle))
                tangent = (-normal[1], normal[0])

                def relief_center(radial, tangential):
                    return (
                        x + radial * normal[0] + tangential * tangent[0],
                        y + radial * normal[1] + tangential * tangent[1],
                        (relief_z0 + relief_z1) / 2.0,
                    )

                back_relief_cutters.append(
                    add_beveled_box(
                        f"Bottom_Mount_Nut_Lip_{relief_index + 1}_Back_Relief",
                        (
                            relief_depth,
                            BOTTOM_MOUNT_NUT_SNAP_LIP_WIDTH
                            + 2.0 * side_slot,
                            relief_z1 - relief_z0,
                        ),
                        relief_center(
                            pocket_apothem + flex_wall + relief_depth / 2.0,
                            0.0,
                        ),
                        rotation_z=face_angle,
                        bevel=0.0,
                    )
                )
                side_radial_start = pocket_apothem - BOOLEAN_OVERLAP
                side_radial_end = (
                    pocket_apothem
                    + flex_wall
                    + relief_depth
                    + BOOLEAN_OVERLAP
                )
                for tangent_sign in (-1.0, 1.0):
                    side_slot_cutters.append(
                        add_beveled_box(
                            f"Bottom_Mount_Nut_Lip_{relief_index + 1}_"
                            f"Side_Slot_{tangent_sign:+.0f}",
                            (
                                side_radial_end - side_radial_start,
                                side_slot,
                                relief_z1 - relief_z0,
                            ),
                            relief_center(
                                (side_radial_start + side_radial_end) / 2.0,
                                tangent_sign
                                * (
                                    BOTTOM_MOUNT_NUT_SNAP_LIP_WIDTH / 2.0
                                    + side_slot / 2.0
                                ),
                            ),
                            rotation_z=face_angle,
                            bevel=0.0,
                        )
                    )
        for lip_index in range(6):
            face_angle = rotation + math.radians(60.0 * lip_index)
            lip = add_hex_face_snap_wedge(
                f"Bottom_Mount_Nut_Snap_Lip_{lip_index + 1}",
                x,
                y,
                face_angle,
                pocket_apothem,
                BOTTOM_MOUNT_NUT_SNAP_LIP_PROJECTION,
                BOTTOM_MOUNT_NUT_SNAP_ROOT_EMBED,
                BOTTOM_MOUNT_NUT_SNAP_LIP_WIDTH,
                lip_z0,
                lip_z1,
            )
            boolean_union(
                holder,
                lip,
                f"Bottom_Mount_Nut_Snap_Lip_{lip_index + 1}_Union",
            )
        if BOTTOM_MOUNT_NUT_SNAP_RELIEF_ENABLED:
            boolean_difference(
                holder,
                back_relief_cutters,
                "Bottom_Mount_Nut_Snap_Tongue_Back_Reliefs",
            )
            boolean_difference(
                holder,
                side_slot_cutters,
                "Bottom_Mount_Nut_Snap_Tongue_Side_Slots",
            )
        holder_non_manifold = non_manifold_edge_count(holder)
        holder_shells = connected_shell_count(holder)
        print(
            "BOTTOM_MOUNT_NUT_HOLDER_VALIDATION "
            f"non_manifold_edges={holder_non_manifold} "
            f"connected_shells={holder_shells}"
        )
        if holder_non_manifold or holder_shells != 1:
            raise RuntimeError("Captive nut holder is not one manifold component")
        boolean_union(
            base,
            holder,
            "Bottom_Mount_Captive_Nut_Boss_Union",
            solver=BOTTOM_MOUNT_NUT_HOLDER_UNION_SOLVER,
        )

    cutter = add_cylinder_z(
        "Bottom_One_Half_Inch_Through_Hole",
        BOTTOM_MOUNT_HOLE_DIAMETER / 2.0,
        -BOOLEAN_OVERLAP,
        BOTTOM_THICKNESS + BOOLEAN_OVERLAP,
        x,
        y,
    )
    boolean_difference(base, [cutter], "Bottom_One_Half_Inch_Through_Hole")
    if BOTTOM_MOUNT_NUT_HOLDER_ENABLED:
        print(
            "BOTTOM_MOUNT_CAPTIVE_NUT "
            f"thread={BOTTOM_MOUNT_NUT_THREAD_DIAMETER:.2f} "
            f"hole={BOTTOM_MOUNT_HOLE_DIAMETER:.2f} "
            f"nut_af={BOTTOM_MOUNT_NUT_ACROSS_FLATS:.2f} "
            f"pocket_af={bottom_mount_nut_pocket_across_flats():.2f} "
            f"nut_thickness={BOTTOM_MOUNT_NUT_THICKNESS:.2f} "
            f"boss_od={BOTTOM_MOUNT_NUT_HOLDER_OUTER_DIAMETER:.2f} "
            f"retention_clearance="
            f"{BOTTOM_MOUNT_NUT_SNAP_LIP_RETENTION_CLEARANCE:.2f} "
            f"relieved_lips={BOTTOM_MOUNT_NUT_SNAP_RELIEF_ENABLED} "
            f"snap_lips=6"
        )
    return base


def import_bottom_keystone_reference_socket(index, position):
    path = Path(BOTTOM_KEYSTONE_REFERENCE_STL).expanduser().resolve()
    before = set(bpy.data.objects)
    if hasattr(bpy.ops.wm, "stl_import"):
        bpy.ops.wm.stl_import(filepath=str(path))
    else:
        bpy.ops.import_mesh.stl(filepath=str(path))
    imported = [
        obj for obj in bpy.data.objects if obj not in before and obj.type == "MESH"
    ]
    if len(imported) != 1:
        raise RuntimeError(
            f"Expected one mesh in keystone reference STL, found {len(imported)}"
        )
    socket = imported[0]
    coordinates = [vertex.co.copy() for vertex in socket.data.vertices]
    minimum = Vector(
        (
            min(point.x for point in coordinates),
            min(point.y for point in coordinates),
            min(point.z for point in coordinates),
        )
    )
    maximum = Vector(
        (
            max(point.x for point in coordinates),
            max(point.y for point in coordinates),
            max(point.z for point in coordinates),
        )
    )
    measured = maximum - minimum
    expected = Vector(
        (
            BOTTOM_KEYSTONE_SOCKET_OUTER_X,
            BOTTOM_KEYSTONE_SOCKET_OUTER_Y,
            BOTTOM_KEYSTONE_SOCKET_HEIGHT,
        )
    )
    tolerance = BOTTOM_KEYSTONE_REFERENCE_DIMENSION_TOLERANCE
    if any(
        abs(measured[axis] - expected[axis]) > tolerance
        for axis in range(3)
    ):
        raise ValueError(
            "Keystone reference STL dimensions changed: measured="
            f"{tuple(round(value, 3) for value in measured)} expected="
            f"{tuple(round(value, 3) for value in expected)}"
        )
    center_x = (minimum.x + maximum.x) / 2.0
    center_y = (minimum.y + maximum.y) / 2.0
    for vertex in socket.data.vertices:
        vertex.co.x -= center_x
        vertex.co.y -= center_y
        vertex.co.z -= minimum.z
    socket.data.update()
    socket.location = (position[0], position[1], 0.0)
    socket.rotation_euler.z = math.radians(BOTTOM_KEYSTONE_SOCKET_ROTATION_DEG)
    socket.name = f"Bottom_Keystone_{index}_Reference_Snap_Socket"
    cleanup_mesh(socket)
    recalc_normals(socket)
    bpy.context.view_layer.update()
    return socket


def add_bottom_keystone_mounts(base, positions):
    if not BOTTOM_KEYSTONES_ENABLED or not positions:
        return base
    if BOTTOM_KEYSTONE_USE_REFERENCE_SNAP_SOCKET:
        rotation = math.radians(BOTTOM_KEYSTONE_SOCKET_ROTATION_DEG)
        cavity_cutters = [
            add_beveled_box(
                f"Bottom_Keystone_{index}_Reference_Inner_Clearance",
                (
                    BOTTOM_KEYSTONE_SOCKET_INNER_CLEAR_X
                    + 2.0 * BOTTOM_KEYSTONE_SOCKET_BASE_CLEARANCE,
                    BOTTOM_KEYSTONE_SOCKET_INNER_CLEAR_Y
                    + 2.0 * BOTTOM_KEYSTONE_SOCKET_BASE_CLEARANCE,
                    BOTTOM_KEYSTONE_SOCKET_HEIGHT + 2.0 * BOOLEAN_OVERLAP,
                ),
                (
                    x,
                    y,
                    BOTTOM_KEYSTONE_SOCKET_HEIGHT / 2.0,
                ),
                rotation_z=rotation,
                bevel=0.0,
            )
            for index, (x, y) in enumerate(positions, start=1)
        ]
        boolean_difference(
            base,
            cavity_cutters,
            "Bottom_Keystone_Reference_Socket_Inner_Clearances",
        )
        for index, position in enumerate(positions, start=1):
            socket = import_bottom_keystone_reference_socket(index, position)
            boolean_union(
                base,
                socket,
                f"Bottom_Keystone_{index}_Reference_Snap_Socket_Union",
            )
        print(
            "BOTTOM_KEYSTONE_REFERENCE_SNAP_SOCKETS "
            f"count={len(positions)} outer="
            f"({BOTTOM_KEYSTONE_SOCKET_OUTER_X:.2f}, "
            f"{BOTTOM_KEYSTONE_SOCKET_OUTER_Y:.2f}, "
            f"{BOTTOM_KEYSTONE_SOCKET_HEIGHT:.2f}) outside_face_z=0.00 "
            "loading_side=inside"
        )
        return base

    pocket_cutters = []
    through_cutters = []
    for index, (x, y) in enumerate(positions, start=1):
        pocket_cutters.append(
            add_beveled_box(
                f"Bottom_Keystone_{index}_Flush_Face_Pocket",
                (
                    BOTTOM_KEYSTONE_FACE_POCKET_X,
                    BOTTOM_KEYSTONE_FACE_POCKET_Y,
                    BOTTOM_KEYSTONE_FACE_RECESS_DEPTH + BOOLEAN_OVERLAP,
                ),
                (
                    x,
                    y,
                    (
                        BOTTOM_KEYSTONE_FACE_RECESS_DEPTH
                        - BOOLEAN_OVERLAP
                    )
                    / 2.0,
                ),
                bevel=0.0,
            )
        )
        through_cutters.append(
            add_beveled_box(
                f"Bottom_Keystone_{index}_Snap_In_Through_Cutout",
                (
                    BOTTOM_KEYSTONE_CUTOUT_X,
                    BOTTOM_KEYSTONE_CUTOUT_Y,
                    BOTTOM_THICKNESS + 2.0 * BOOLEAN_OVERLAP,
                ),
                (x, y, BOTTOM_THICKNESS / 2.0),
                bevel=0.0,
            )
        )
    boolean_difference(
        base,
        pocket_cutters,
        "Bottom_Keystone_Flush_Face_Pockets",
    )
    boolean_difference(
        base,
        through_cutters,
        "Bottom_Keystone_Snap_In_Through_Cutouts",
    )
    print(
        "BOTTOM_KEYSTONE_FLUSH_MOUNTS "
        f"count={len(positions)} face_recess="
        f"{BOTTOM_KEYSTONE_FACE_RECESS_DEPTH:.2f} "
        f"remaining_snap_panel="
        f"{BOTTOM_THICKNESS - BOTTOM_KEYSTONE_FACE_RECESS_DEPTH:.2f}"
    )
    return base


def create_adjustable_camera_hold_down(camera, post_positions):
    """Stationary two-screw bridge with a low-friction pad on the yaw axis."""
    if len(post_positions) != 2:
        raise ValueError("Adjustable camera hold-down requires two posts")
    pivot = adjustable_camera_pivot(camera)
    underside, top = camera_bracket_z_bounds()
    plate_center_z = (underside + top) / 2.0
    center_radius = CAMERA_HOLD_DOWN_CENTER_PLATE_DIAMETER / 2.0
    bridge = add_cylinder_z(
        "Adjustable_Camera_Hold_Down_Center",
        center_radius,
        underside,
        top,
        pivot.x,
        pivot.y,
    )
    boss_radius = max(
        LID_SCREW_HEAD_COUNTERBORE_DIAMETER / 2.0
        + CAMERA_BRACKET_BOSS_EDGE_MARGIN,
        FASTENER_POST_DIAMETER / 2.0
        + CAMERA_BRACKET_BOSS_POST_EDGE_MARGIN,
    )
    for index, (x, y) in enumerate(post_positions, start=1):
        boss = add_cylinder_z(
            f"Adjustable_Hold_Down_Screw_Boss_{index}",
            boss_radius,
            underside,
            top,
            x,
            y,
        )
        boolean_union(bridge, boss, f"Adjustable_Hold_Down_Boss_{index}")
        dx = pivot.x - x
        dy = pivot.y - y
        length = max(math.hypot(dx, dy) - center_radius, 0.0)
        if length > 1e-6:
            unit_x = dx / math.hypot(dx, dy)
            unit_y = dy / math.hypot(dx, dy)
            end_x = pivot.x - unit_x * center_radius * 0.65
            end_y = pivot.y - unit_y * center_radius * 0.65
            arm = add_beveled_box(
                f"Adjustable_Hold_Down_Arm_{index}",
                (
                    math.hypot(end_x - x, end_y - y)
                    + CAMERA_BRACKET_ARM_PLATE_OVERLAP,
                    CAMERA_BRACKET_ARM_WIDTH,
                    CAMERA_BRACKET_THICKNESS,
                ),
                (
                    (x + end_x) / 2.0,
                    (y + end_y) / 2.0,
                    plate_center_z,
                ),
                rotation_z=math.atan2(end_y - y, end_x - x),
                bevel=1.0,
            )
            boolean_union(bridge, arm, f"Adjustable_Hold_Down_Arm_{index}")

    body_top = camera_eye_center_z() + mission1.canonical_body_bounds(
        CAMERA_UPSIDE_DOWN
    )[2][1]
    pad_bottom = (
        body_top
        + CAMERA_BRACKET_BODY_CONTACT_CLEARANCE_Z
        + CAMERA_HOLD_DOWN_PAD_MATERIAL_THICKNESS
    )
    pad = add_cylinder_z(
        "Adjustable_Hold_Down_Pivot_Pad",
        CAMERA_HOLD_DOWN_PAD_DIAMETER / 2.0,
        pad_bottom,
        underside + BOOLEAN_OVERLAP,
        pivot.x,
        pivot.y,
    )
    boolean_union(bridge, pad, "Adjustable_Hold_Down_Pivot_Pad")
    # The pivot is deliberately near the camera's front plane.  Relieve the
    # outward cap of the center plate around the raised eye surround while
    # retaining the smaller contact pad, which ends just inside this cutter.
    eye_clearance = CAMERA_BRACKET_WALL_CLEARANCE
    surround_cutter = rounded_rectangle_prism_axis(
        "Adjustable_Hold_Down_Eye_Surround_Clearance",
        camera["angle"],
        camera["eye_inner_wall"] - eye_clearance,
        camera["raw_surface"] + EYE_CUTTER_OUTWARD_EXTENSION,
        EYE_BEZEL_WIDTH + 2.0 * eye_clearance,
        EYE_BEZEL_HEIGHT + 2.0 * eye_clearance,
        EYE_BEZEL_CORNER_RADIUS + eye_clearance,
        camera_eye_center_z(),
        center_tangent=camera["eye_tangent"],
    )
    boolean_difference(
        bridge,
        [surround_cutter],
        "Adjustable_Hold_Down_Eye_Surround_Clearance",
    )
    clearance_cutters = []
    counterbore_cutters = []
    for index, (x, y) in enumerate(post_positions, start=1):
        clearance_cutters.append(
            add_cylinder_z(
                f"Adjustable_Hold_Down_M3_Clearance_{index}",
                LID_SCREW_CLEARANCE_DIAMETER / 2.0,
                underside - BOOLEAN_OVERLAP,
                top + BOOLEAN_OVERLAP,
                x,
                y,
            )
        )
        counterbore_cutters.append(
            add_cylinder_z(
                f"Adjustable_Hold_Down_Counterbore_{index}",
                LID_SCREW_HEAD_COUNTERBORE_DIAMETER / 2.0,
                top - LID_SCREW_HEAD_COUNTERBORE_DEPTH,
                top + BOOLEAN_OVERLAP,
                x,
                y,
            )
        )
    boolean_difference(
        bridge,
        clearance_cutters,
        "Adjustable_Hold_Down_M3_Clearance_Holes",
    )
    boolean_difference(
        bridge,
        counterbore_cutters,
        "Adjustable_Hold_Down_Counterbores",
    )
    bridge.name = "Adjustable_Camera_Stationary_Hold_Down"
    bridge["camera_angle_deg"] = camera["angle"]
    bridge["pivot_x"] = pivot.x
    bridge["pivot_y"] = pivot.y
    bridge["contact_pad_bottom_z"] = pad_bottom
    bridge["low_friction_disk_diameter_mm"] = (
        CAMERA_HOLD_DOWN_PAD_DIAMETER
        - 2.0 * CAMERA_HOLD_DOWN_PAD_MATERIAL_CLEARANCE
    )
    bridge["low_friction_disk_thickness_mm"] = (
        CAMERA_HOLD_DOWN_PAD_MATERIAL_THICKNESS
    )
    bridge["clamp_travel_z"] = camera_bracket_clamp_travel()
    print(
        "ADJUSTABLE_HOLD_DOWN_INTERFACE "
        f"disk=PTFE/UHMW/acetal "
        f"diameter={bridge['low_friction_disk_diameter_mm']:.2f} "
        f"thickness={CAMERA_HOLD_DOWN_PAD_MATERIAL_THICKNESS:.2f} "
        f"designed_compression={CAMERA_BRACKET_CLAMP_PRELOAD_Z:.2f}"
    )
    return bridge


def create_camera_bracket(camera, post_positions):
    body_radial, body_tangent, body_vertical = mission1.canonical_body_bounds(
        CAMERA_UPSIDE_DOWN
    )
    angle = math.radians(camera["angle"])
    normal = (math.cos(angle), math.sin(angle))
    tangent_axis = (-math.sin(angle), math.cos(angle))

    def local_coordinates(position):
        return (
            position[0] * normal[0] + position[1] * normal[1],
            position[0] * tangent_axis[0] + position[1] * tangent_axis[1],
        )

    local_posts = [local_coordinates(position) for position in post_positions]
    lens_face_radius = camera["radial"] + CAMERA_BODY_DEPTH / 2.0
    body_back = lens_face_radius + body_radial[0]
    body_tangent_center = camera["eye_tangent"] + sum(body_tangent) / 2.0
    rail_tangents = tuple(
        camera.get(
            "bracket_contact_rail_tangents",
            (
                camera["eye_tangent"]
                + body_tangent[0]
                + CAMERA_BRACKET_CONTACT_RAIL_EDGE_INSET,
                camera["eye_tangent"]
                + body_tangent[1]
                - CAMERA_BRACKET_CONTACT_RAIL_EDGE_INSET,
            ),
        )
    )
    if CAMERA_BRACKET_COMPACT_OUTER_RAIL_ONLY:
        lip_tangent_center = rail_tangents[0]
        lip_width = CAMERA_BRACKET_COMPACT_REAR_LIP_WIDTH
    else:
        lip_tangent_center = body_tangent_center
        lip_width = CAMERA_BRACKET_REAR_LIP_WIDTH
    usb_locator_tangent_bounds = None
    non_usb_locator_tangent_bounds = None
    usb_gusset_tangent_bounds = None
    non_usb_gusset_tangent_bounds = None
    if CAMERA_BRACKET_USB_SIDE_LOCATOR_ENABLED:
        usb_side_sign = camera_usb_side_sign()
        usb_side_tangent = (
            body_tangent[0] if usb_side_sign < 0.0 else body_tangent[1]
        )
        locator_tangent_center = (
            camera["eye_tangent"]
            + usb_side_tangent
            + usb_side_sign
            * (
                CAMERA_BRACKET_USB_SIDE_LOCATOR_CLEARANCE
                + CAMERA_BRACKET_USB_SIDE_LOCATOR_THICKNESS / 2.0
            )
        )
        usb_locator_tangent_bounds = (
            locator_tangent_center
            - CAMERA_BRACKET_USB_SIDE_LOCATOR_THICKNESS / 2.0,
            locator_tangent_center
            + CAMERA_BRACKET_USB_SIDE_LOCATOR_THICKNESS / 2.0,
        )
        if CAMERA_BRACKET_SIDE_LOCATOR_GUSSETS_ENABLED:
            locator_outer_tangent = (
                locator_tangent_center
                + usb_side_sign
                * CAMERA_BRACKET_USB_SIDE_LOCATOR_THICKNESS
                / 2.0
            )
            gusset_outer_tangent = (
                locator_outer_tangent
                + usb_side_sign * CAMERA_BRACKET_SIDE_LOCATOR_GUSSET_REACH
            )
            usb_gusset_tangent_bounds = tuple(
                sorted((locator_outer_tangent, gusset_outer_tangent))
            )
    if CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_ENABLED:
        non_usb_side_sign = -camera_usb_side_sign()
        non_usb_side_tangent = (
            body_tangent[0]
            if non_usb_side_sign < 0.0
            else body_tangent[1]
        )
        non_usb_locator_tangent_center = (
            camera["eye_tangent"]
            + non_usb_side_tangent
            + non_usb_side_sign
            * (
                CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_CLEARANCE
                + CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_THICKNESS / 2.0
            )
        )
        non_usb_locator_tangent_bounds = (
            non_usb_locator_tangent_center
            - CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_THICKNESS / 2.0,
            non_usb_locator_tangent_center
            + CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_THICKNESS / 2.0,
        )
        if CAMERA_BRACKET_SIDE_LOCATOR_GUSSETS_ENABLED:
            non_usb_locator_outer_tangent = (
                non_usb_locator_tangent_center
                + non_usb_side_sign
                * CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_THICKNESS
                / 2.0
            )
            non_usb_gusset_outer_tangent = (
                non_usb_locator_outer_tangent
                + non_usb_side_sign
                * CAMERA_BRACKET_SIDE_LOCATOR_GUSSET_REACH
            )
            non_usb_gusset_tangent_bounds = tuple(
                sorted(
                    (
                        non_usb_locator_outer_tangent,
                        non_usb_gusset_outer_tangent,
                    )
                )
            )
    corner_lip_segments = []
    if CAMERA_BRACKET_L_CORNER_GUIDES_ENABLED:
        if CAMERA_BRACKET_USB_SIDE_LOCATOR_ENABLED:
            usb_locator_outer_tangent = (
                locator_tangent_center
                + usb_side_sign
                * CAMERA_BRACKET_USB_SIDE_LOCATOR_THICKNESS
                / 2.0
            )
            usb_return_inboard_tangent = (
                camera["eye_tangent"]
                + usb_side_tangent
                - usb_side_sign
                * CAMERA_BRACKET_L_CORNER_RETURN_INBOARD_LENGTH
            )
            usb_return_bounds = tuple(
                sorted(
                    (
                        usb_locator_outer_tangent,
                        usb_return_inboard_tangent,
                    )
                )
            )
            corner_lip_segments.append(
                (
                    "USB_Battery_Side",
                    sum(usb_return_bounds) / 2.0,
                    usb_return_bounds[1] - usb_return_bounds[0],
                    usb_return_bounds,
                )
            )
        if CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_ENABLED:
            non_usb_locator_outer_tangent = (
                non_usb_locator_tangent_center
                + non_usb_side_sign
                * CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_THICKNESS
                / 2.0
            )
            non_usb_return_inboard_tangent = (
                camera["eye_tangent"]
                + non_usb_side_tangent
                - non_usb_side_sign
                * CAMERA_BRACKET_L_CORNER_RETURN_INBOARD_LENGTH
            )
            non_usb_return_bounds = tuple(
                sorted(
                    (
                        non_usb_locator_outer_tangent,
                        non_usb_return_inboard_tangent,
                    )
                )
            )
            corner_lip_segments.append(
                (
                    "Opposite_Side",
                    sum(non_usb_return_bounds) / 2.0,
                    non_usb_return_bounds[1] - non_usb_return_bounds[0],
                    non_usb_return_bounds,
                )
            )
    rear_guide_radial_min = (
        body_back
        - CAMERA_BRACKET_REAR_CLEARANCE
        - CAMERA_BRACKET_REAR_LIP_THICKNESS
    )
    rear_guide_radial_max = body_back - CAMERA_BRACKET_REAR_CLEARANCE
    radial_min = body_back - CAMERA_BRACKET_PRIMARY_REAR_OVERLAP
    radial_max = body_back + CAMERA_BRACKET_OVER_CAMERA_DEPTH
    tangent_min = min(
        lip_tangent_center - lip_width / 2.0,
        min(rail_tangents) - CAMERA_BRACKET_CONTACT_RAIL_WIDTH / 2.0,
    ) - CAMERA_BRACKET_PRIMARY_TANGENTIAL_MARGIN
    tangent_max = max(
        lip_tangent_center + lip_width / 2.0,
        max(rail_tangents) + CAMERA_BRACKET_CONTACT_RAIL_WIDTH / 2.0,
    ) + CAMERA_BRACKET_PRIMARY_TANGENTIAL_MARGIN
    if usb_locator_tangent_bounds is not None:
        tangent_min = min(tangent_min, usb_locator_tangent_bounds[0])
        tangent_max = max(tangent_max, usb_locator_tangent_bounds[1])
    if non_usb_locator_tangent_bounds is not None:
        tangent_min = min(tangent_min, non_usb_locator_tangent_bounds[0])
        tangent_max = max(tangent_max, non_usb_locator_tangent_bounds[1])
    if usb_gusset_tangent_bounds is not None:
        tangent_min = min(tangent_min, usb_gusset_tangent_bounds[0])
        tangent_max = max(tangent_max, usb_gusset_tangent_bounds[1])
    if non_usb_gusset_tangent_bounds is not None:
        tangent_min = min(tangent_min, non_usb_gusset_tangent_bounds[0])
        tangent_max = max(tangent_max, non_usb_gusset_tangent_bounds[1])
    for _, _, _, return_bounds in corner_lip_segments:
        tangent_min = min(tangent_min, return_bounds[0])
        tangent_max = max(tangent_max, return_bounds[1])
    if CAMERA_BRACKET_L_CORNER_GUIDES_ENABLED:
        radial_min = min(
            radial_min,
            rear_guide_radial_min - CAMERA_BRACKET_GUIDE_PLATE_OVERHANG,
        )
        radial_max = max(
            radial_max,
            body_back
            + CAMERA_BRACKET_OVER_CAMERA_DEPTH
            + CAMERA_BRACKET_GUIDE_PLATE_OVERHANG,
        )
        tangent_min -= CAMERA_BRACKET_GUIDE_PLATE_OVERHANG
        tangent_max += CAMERA_BRACKET_GUIDE_PLATE_OVERHANG
    if 2.0 * CAMERA_BRACKET_ARM_PLATE_EMBED >= tangent_max - tangent_min:
        raise ValueError(
            f"Camera {camera['index']} bracket plate has no interior "
            "tangential arm-anchor region"
        )
    underside, top = camera_bracket_z_bounds()
    plate_center = axis_point(
        camera["angle"],
        (radial_min + radial_max) / 2.0,
        (tangent_min + tangent_max) / 2.0,
        (underside + top) / 2.0,
    )
    bracket = add_beveled_box(
        f"MISSION1_Camera_Retaining_Bracket_{camera['index']}",
        (
            radial_max - radial_min,
            tangent_max - tangent_min,
            CAMERA_BRACKET_THICKNESS,
        ),
        tuple(plate_center),
        rotation_z=angle,
        bevel=1.2,
    )

    # Circular bosses and compact arms carry the two M3 screws without filling
    # the full post-to-camera bounding rectangle.  Each arm terminates at a
    # point well inside the primary plate; aiming at the nearest plate corner
    # can otherwise leave only a fragile corner-sized Boolean connection.
    boss_radius = max(
        LID_SCREW_HEAD_COUNTERBORE_DIAMETER / 2.0
        + CAMERA_BRACKET_BOSS_EDGE_MARGIN,
        FASTENER_POST_DIAMETER / 2.0
        + CAMERA_BRACKET_BOSS_POST_EDGE_MARGIN,
    )
    arm_specs = []
    for post_index, ((x, y), (post_radial, post_tangent)) in enumerate(
        zip(post_positions, local_posts),
        start=1,
    ):
        boss = add_cylinder_z(
            f"Camera_Bracket_{camera['index']}_Screw_Boss_{post_index}",
            boss_radius,
            underside,
            top,
            x,
            y,
        )
        boolean_union(
            bracket,
            boss,
            f"Camera_Bracket_{camera['index']}_Screw_Boss_{post_index}_Union",
        )
        def embedded_anchor_coordinate(value, lower, upper):
            inset_lower = lower + CAMERA_BRACKET_ARM_PLATE_EMBED
            inset_upper = upper - CAMERA_BRACKET_ARM_PLATE_EMBED
            return min(max(value, inset_lower), inset_upper)

        target_radial = embedded_anchor_coordinate(
            post_radial,
            radial_min,
            radial_max,
        )
        target_tangent = embedded_anchor_coordinate(
            post_tangent,
            tangent_min,
            tangent_max,
        )
        target = axis_point(
            camera["angle"],
            target_radial,
            target_tangent,
            (underside + top) / 2.0,
        )
        dx = target.x - x
        dy = target.y - y
        arm_length = math.hypot(dx, dy)
        if arm_length > 1e-6:
            arm_specs.append(
                (
                    (x + target.x) / 2.0,
                    (y + target.y) / 2.0,
                    arm_length + 2.0 * CAMERA_BRACKET_ARM_PLATE_OVERLAP,
                    math.atan2(dy, dx),
                )
            )
            arm = add_beveled_box(
                f"Camera_Bracket_{camera['index']}_Arm_{post_index}",
                (
                    arm_length
                    + 2.0 * CAMERA_BRACKET_ARM_PLATE_OVERLAP,
                    CAMERA_BRACKET_ARM_WIDTH,
                    CAMERA_BRACKET_THICKNESS,
                ),
                (
                    (x + target.x) / 2.0,
                    (y + target.y) / 2.0,
                    (underside + top) / 2.0,
                ),
                rotation_z=math.atan2(dy, dx),
                bevel=1.0,
            )
            boolean_union(
                bracket,
                arm,
                f"Camera_Bracket_{camera['index']}_Arm_{post_index}_Union",
            )

    lip_segments = [
        (
            "Legacy",
            lip_tangent_center,
            lip_width,
            (
                lip_tangent_center - lip_width / 2.0,
                lip_tangent_center + lip_width / 2.0,
            ),
        )
    ]
    if corner_lip_segments:
        lip_segments = corner_lip_segments
    elif (
        CAMERA_BRACKET_SPLIT_REAR_LIP
        and not CAMERA_BRACKET_COMPACT_OUTER_RAIL_ONLY
    ):
        segment_width = (
            lip_width - CAMERA_BRACKET_REAR_LIP_CENTER_AIR_GAP
        ) / 2.0
        segment_offset = (
            CAMERA_BRACKET_REAR_LIP_CENTER_AIR_GAP + segment_width
        ) / 2.0
        lip_segments = [
            (
                "Tangent_Min",
                lip_tangent_center - segment_offset,
                segment_width,
                (
                    lip_tangent_center - segment_offset - segment_width / 2.0,
                    lip_tangent_center - segment_offset + segment_width / 2.0,
                ),
            ),
            (
                "Tangent_Max",
                lip_tangent_center + segment_offset,
                segment_width,
                (
                    lip_tangent_center + segment_offset - segment_width / 2.0,
                    lip_tangent_center + segment_offset + segment_width / 2.0,
                ),
            ),
        ]
    rear_lip_segment_bounds = []
    for lip_index, (
        segment_label,
        segment_tangent,
        segment_width,
        segment_tangent_bounds,
    ) in enumerate(
        lip_segments,
        start=1,
    ):
        lip_center = axis_point(
            camera["angle"],
            body_back
            - CAMERA_BRACKET_REAR_CLEARANCE
            - CAMERA_BRACKET_REAR_LIP_THICKNESS / 2.0,
            segment_tangent,
            underside - CAMERA_BRACKET_REAR_LIP_HEIGHT / 2.0,
        )
        lip = add_beveled_box(
            f"MISSION1_Camera_Bracket_{camera['index']}_"
            f"{segment_label}_Rear_Stop_{lip_index}",
            (
                CAMERA_BRACKET_REAR_LIP_THICKNESS,
                segment_width,
                CAMERA_BRACKET_REAR_LIP_HEIGHT + 2.0 * BOOLEAN_OVERLAP,
            ),
            tuple(lip_center),
            rotation_z=angle,
            bevel=0.8,
        )
        boolean_union(
            bracket,
            lip,
            f"Camera_Bracket_{camera['index']}_Rear_Stop_{lip_index}",
        )
        rear_lip_segment_bounds.append(
            (
                rear_guide_radial_min,
                rear_guide_radial_max,
                segment_tangent_bounds[0],
                segment_tangent_bounds[1],
                underside
                - CAMERA_BRACKET_REAR_LIP_HEIGHT
                - BOOLEAN_OVERLAP,
                underside + BOOLEAN_OVERLAP,
            )
        )

    # One compact outer rail (or two when configured) bypasses the top/shutter
    # button and puts clamp load onto the broad solid camera top.  Its nominal gap is consumed
    # when the bracket screws are tightened, followed by the configured flex
    # preload before the bracket bears on its post tops.
    body_top = camera_eye_center_z() + body_vertical[1]
    rail_bottom = body_top + CAMERA_BRACKET_BODY_CONTACT_CLEARANCE_Z
    rail_radial_max = body_back + CAMERA_BRACKET_OVER_CAMERA_DEPTH
    rail_radial_min = (
        rail_radial_max - CAMERA_BRACKET_CONTACT_RAIL_RADIAL_LENGTH
    )
    for rail_index, rail_tangent in enumerate(rail_tangents, start=1):
        rail_center = axis_point(
            camera["angle"],
            (rail_radial_min + rail_radial_max) / 2.0,
            rail_tangent,
            (rail_bottom + underside + BOOLEAN_OVERLAP) / 2.0,
        )
        rail = add_beveled_box(
            f"Camera_Bracket_{camera['index']}_Body_Rail_{rail_index}",
            (
                CAMERA_BRACKET_CONTACT_RAIL_RADIAL_LENGTH,
                CAMERA_BRACKET_CONTACT_RAIL_WIDTH,
                underside + BOOLEAN_OVERLAP - rail_bottom,
            ),
            tuple(rail_center),
            rotation_z=angle,
            bevel=0.6,
        )
        boolean_union(
            bracket,
            rail,
            f"Camera_Bracket_{camera['index']}_Body_Rail_{rail_index}_Union",
        )

    usb_locator_bounds = None
    usb_gusset_bounds = None
    if CAMERA_BRACKET_USB_SIDE_LOCATOR_ENABLED:
        locator_radial_max = body_back + CAMERA_BRACKET_OVER_CAMERA_DEPTH
        locator_radial_min = (
            locator_radial_max
            - CAMERA_BRACKET_USB_SIDE_LOCATOR_RADIAL_LENGTH
        )
        if CAMERA_BRACKET_L_CORNER_GUIDES_ENABLED:
            locator_radial_min = min(
                locator_radial_min,
                rear_guide_radial_min - BOOLEAN_OVERLAP,
            )
        locator_z_min = (
            body_top
            - mission1.BODY_CORNER_RADIUS
            - CAMERA_BRACKET_USB_SIDE_LOCATOR_HEIGHT
        )
        locator_z_max = underside + CAMERA_BRACKET_SIDE_LOCATOR_PLATE_EMBED
        locator_center = axis_point(
            camera["angle"],
            (locator_radial_min + locator_radial_max) / 2.0,
            locator_tangent_center,
            (locator_z_min + locator_z_max) / 2.0,
        )
        locator = add_beveled_box(
            f"Camera_Bracket_{camera['index']}_Removable_USB_Side_Locator",
            (
                CAMERA_BRACKET_USB_SIDE_LOCATOR_RADIAL_LENGTH,
                CAMERA_BRACKET_USB_SIDE_LOCATOR_THICKNESS,
                locator_z_max - locator_z_min,
            ),
            tuple(locator_center),
            rotation_z=angle,
            bevel=0.6,
        )
        boolean_union(
            bracket,
            locator,
            f"Camera_Bracket_{camera['index']}_USB_Side_Locator_Union",
        )
        usb_locator_bounds = (
            locator_radial_min,
            locator_radial_max,
            locator_tangent_center
            - CAMERA_BRACKET_USB_SIDE_LOCATOR_THICKNESS / 2.0,
            locator_tangent_center
            + CAMERA_BRACKET_USB_SIDE_LOCATOR_THICKNESS / 2.0,
            locator_z_min,
            locator_z_max,
        )
        if CAMERA_BRACKET_SIDE_LOCATOR_GUSSETS_ENABLED:
            gusset_z_top = (
                underside + CAMERA_BRACKET_SIDE_LOCATOR_PLATE_EMBED
            )
            gusset = add_side_locator_gusset(
                f"Camera_Bracket_{camera['index']}_USB_Locator_Gusset",
                camera["angle"],
                locator_radial_min,
                locator_radial_max,
                locator_outer_tangent,
                usb_side_sign,
                gusset_z_top,
            )
            boolean_union(
                bracket,
                gusset,
                f"Camera_Bracket_{camera['index']}_USB_Locator_Gusset_Union",
                solver="MANIFOLD",
            )
            usb_gusset_bounds = (
                locator_radial_min,
                locator_radial_max,
                usb_gusset_tangent_bounds[0],
                usb_gusset_tangent_bounds[1],
                gusset_z_top - CAMERA_BRACKET_SIDE_LOCATOR_GUSSET_DEPTH,
                gusset_z_top,
            )

    non_usb_locator_bounds = None
    non_usb_gusset_bounds = None
    if CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_ENABLED:
        non_usb_locator_radial_max = (
            body_back + CAMERA_BRACKET_OVER_CAMERA_DEPTH
        )
        non_usb_locator_radial_min = (
            non_usb_locator_radial_max
            - CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_RADIAL_LENGTH
        )
        if CAMERA_BRACKET_L_CORNER_GUIDES_ENABLED:
            non_usb_locator_radial_min = min(
                non_usb_locator_radial_min,
                rear_guide_radial_min - BOOLEAN_OVERLAP,
            )
        non_usb_locator_z_min = (
            body_top
            - mission1.BODY_CORNER_RADIUS
            - CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_HEIGHT
        )
        non_usb_locator_z_max = (
            underside + CAMERA_BRACKET_SIDE_LOCATOR_PLATE_EMBED
        )
        non_usb_locator_center = axis_point(
            camera["angle"],
            (non_usb_locator_radial_min + non_usb_locator_radial_max) / 2.0,
            non_usb_locator_tangent_center,
            (non_usb_locator_z_min + non_usb_locator_z_max) / 2.0,
        )
        non_usb_locator = add_beveled_box(
            f"Camera_Bracket_{camera['index']}_Removable_Non_USB_Side_Locator",
            (
                CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_RADIAL_LENGTH,
                CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_THICKNESS,
                non_usb_locator_z_max - non_usb_locator_z_min,
            ),
            tuple(non_usb_locator_center),
            rotation_z=angle,
            bevel=0.6,
        )
        boolean_union(
            bracket,
            non_usb_locator,
            f"Camera_Bracket_{camera['index']}_Non_USB_Side_Locator_Union",
        )
        non_usb_locator_bounds = (
            non_usb_locator_radial_min,
            non_usb_locator_radial_max,
            non_usb_locator_tangent_center
            - CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_THICKNESS / 2.0,
            non_usb_locator_tangent_center
            + CAMERA_BRACKET_NON_USB_SIDE_LOCATOR_THICKNESS / 2.0,
            non_usb_locator_z_min,
            non_usb_locator_z_max,
        )
        if CAMERA_BRACKET_SIDE_LOCATOR_GUSSETS_ENABLED:
            non_usb_gusset_z_top = (
                underside + CAMERA_BRACKET_SIDE_LOCATOR_PLATE_EMBED
            )
            non_usb_gusset = add_side_locator_gusset(
                f"Camera_Bracket_{camera['index']}_Non_USB_Locator_Gusset",
                camera["angle"],
                non_usb_locator_radial_min,
                non_usb_locator_radial_max,
                non_usb_locator_outer_tangent,
                non_usb_side_sign,
                non_usb_gusset_z_top,
            )
            boolean_union(
                bracket,
                non_usb_gusset,
                f"Camera_Bracket_{camera['index']}_Non_USB_Locator_Gusset_Union",
                solver="MANIFOLD",
            )
            non_usb_gusset_bounds = (
                non_usb_locator_radial_min,
                non_usb_locator_radial_max,
                non_usb_gusset_tangent_bounds[0],
                non_usb_gusset_tangent_bounds[1],
                non_usb_gusset_z_top
                - CAMERA_BRACKET_SIDE_LOCATOR_GUSSET_DEPTH,
                non_usb_gusset_z_top,
            )

    # The rail placement already avoids the top button.  A full through-relief
    # adds a second layer of protection and keeps that control accessible when
    # the enclosure lid is removed.
    button_radial, button_tangent, button_vertical = (
        mission1.canonical_top_button_bounds(CAMERA_UPSIDE_DOWN)
    )
    if button_vertical[1] > body_vertical[1] + 1e-6:
        relief_margin = CAMERA_BRACKET_BUTTON_RELIEF_MARGIN
        relief_z0 = rail_bottom - BOOLEAN_OVERLAP
        relief_z1 = top + BOOLEAN_OVERLAP
        relief_center = axis_point(
            camera["angle"],
            lens_face_radius + sum(button_radial) / 2.0,
            camera["eye_tangent"] + sum(button_tangent) / 2.0,
            (relief_z0 + relief_z1) / 2.0,
        )
        relief = add_beveled_box(
            f"Camera_Bracket_{camera['index']}_Top_Button_Relief",
            (
                button_radial[1] - button_radial[0] + 2.0 * relief_margin,
                button_tangent[1] - button_tangent[0] + 2.0 * relief_margin,
                relief_z1 - relief_z0,
            ),
            tuple(relief_center),
            rotation_z=angle,
            bevel=0.0,
        )
        boolean_difference(
            bracket,
            [relief],
            f"Camera_Bracket_{camera['index']}_Top_Button_Relief_Cut",
        )

    clearance_cutters = [
        add_cylinder_z(
            f"Camera_Bracket_{camera['index']}_M3_Clearance_{hole_index}",
            LID_SCREW_CLEARANCE_DIAMETER / 2.0,
            underside - BOOLEAN_OVERLAP,
            top + BOOLEAN_OVERLAP,
            x,
            y,
        )
        for hole_index, (x, y) in enumerate(post_positions, start=1)
    ]
    boolean_difference(
        bracket,
        clearance_cutters,
        f"Camera_Bracket_{camera['index']}_M3_Clearance_Holes",
    )
    counterbore_cutters = [
        add_cylinder_z(
            f"Camera_Bracket_{camera['index']}_Counterbore_{hole_index}",
            LID_SCREW_HEAD_COUNTERBORE_DIAMETER / 2.0,
            top - LID_SCREW_HEAD_COUNTERBORE_DEPTH,
            top + 2.0 * BOOLEAN_OVERLAP,
            x,
            y,
        )
        for hole_index, (x, y) in enumerate(post_positions, start=1)
    ]
    boolean_difference(
        bracket,
        counterbore_cutters,
        f"Camera_Bracket_{camera['index']}_Socket_Head_Counterbores",
    )
    bracket.name = f"MISSION1_Camera_Retaining_Bracket_{camera['index']}"
    bracket["plate_radial_min"] = radial_min
    bracket["plate_radial_max"] = radial_max
    bracket["plate_tangent_min"] = tangent_min
    bracket["plate_tangent_max"] = tangent_max
    bracket["camera_angle_deg"] = camera["angle"]
    bracket["rear_lip_radial_min"] = rear_guide_radial_min
    bracket["rear_lip_radial_max"] = rear_guide_radial_max
    bracket["rear_lip_tangent_min"] = min(
        bounds[2] for bounds in rear_lip_segment_bounds
    )
    bracket["rear_lip_tangent_max"] = max(
        bounds[3] for bounds in rear_lip_segment_bounds
    )
    bracket["rear_lip_z_min"] = min(
        bounds[4] for bounds in rear_lip_segment_bounds
    )
    bracket["rear_lip_z_max"] = max(
        bounds[5] for bounds in rear_lip_segment_bounds
    )
    bracket["rear_lip_segment_count"] = len(rear_lip_segment_bounds)
    for segment_index, bounds in enumerate(rear_lip_segment_bounds, start=1):
        (
            bracket[f"rear_lip_{segment_index}_radial_min"],
            bracket[f"rear_lip_{segment_index}_radial_max"],
            bracket[f"rear_lip_{segment_index}_tangent_min"],
            bracket[f"rear_lip_{segment_index}_tangent_max"],
            bracket[f"rear_lip_{segment_index}_z_min"],
            bracket[f"rear_lip_{segment_index}_z_max"],
        ) = bounds
    bracket["boss_radius"] = boss_radius
    for post_index, (x, y) in enumerate(post_positions, start=1):
        bracket[f"boss_{post_index}_x"] = x
        bracket[f"boss_{post_index}_y"] = y
    bracket["arm_count"] = len(arm_specs)
    for arm_index, (center_x, center_y, length, arm_angle) in enumerate(
        arm_specs,
        start=1,
    ):
        bracket[f"arm_{arm_index}_center_x"] = center_x
        bracket[f"arm_{arm_index}_center_y"] = center_y
        bracket[f"arm_{arm_index}_length"] = length
        bracket[f"arm_{arm_index}_angle"] = arm_angle
    bracket["contact_rail_bottom_z"] = rail_bottom
    bracket["clamp_travel_z"] = camera_bracket_clamp_travel()
    bracket["usb_side_locator_enabled"] = usb_locator_bounds is not None
    if usb_locator_bounds is not None:
        (
            bracket["usb_locator_radial_min"],
            bracket["usb_locator_radial_max"],
            bracket["usb_locator_tangent_min"],
            bracket["usb_locator_tangent_max"],
            bracket["usb_locator_z_min"],
            bracket["usb_locator_z_max"],
        ) = usb_locator_bounds
    bracket["non_usb_side_locator_enabled"] = (
        non_usb_locator_bounds is not None
    )
    if non_usb_locator_bounds is not None:
        (
            bracket["non_usb_locator_radial_min"],
            bracket["non_usb_locator_radial_max"],
            bracket["non_usb_locator_tangent_min"],
            bracket["non_usb_locator_tangent_max"],
            bracket["non_usb_locator_z_min"],
            bracket["non_usb_locator_z_max"],
        ) = non_usb_locator_bounds
    bracket["usb_locator_gusset_enabled"] = usb_gusset_bounds is not None
    if usb_gusset_bounds is not None:
        (
            bracket["usb_gusset_radial_min"],
            bracket["usb_gusset_radial_max"],
            bracket["usb_gusset_tangent_min"],
            bracket["usb_gusset_tangent_max"],
            bracket["usb_gusset_z_min"],
            bracket["usb_gusset_z_max"],
        ) = usb_gusset_bounds
    bracket["non_usb_locator_gusset_enabled"] = (
        non_usb_gusset_bounds is not None
    )
    if non_usb_gusset_bounds is not None:
        (
            bracket["non_usb_gusset_radial_min"],
            bracket["non_usb_gusset_radial_max"],
            bracket["non_usb_gusset_tangent_min"],
            bracket["non_usb_gusset_tangent_max"],
            bracket["non_usb_gusset_z_min"],
            bracket["non_usb_gusset_z_max"],
        ) = non_usb_gusset_bounds
    return bracket


def camera_bracket_mutual_clearance_tools(bracket):
    """Recreate a conservative envelope for every compact-bracket member."""
    clearance = CAMERA_BRACKET_MUTUAL_CLEARANCE
    underside, top = camera_bracket_z_bounds()
    angle_deg = bracket["camera_angle_deg"]
    angle = math.radians(angle_deg)
    tools = []

    def local_box(label, radial_min, radial_max, tangent_min, tangent_max, z0, z1):
        center = axis_point(
            angle_deg,
            (radial_min + radial_max) / 2.0,
            (tangent_min + tangent_max) / 2.0,
            (z0 + z1) / 2.0,
        )
        return add_beveled_box(
            label,
            (
                radial_max - radial_min,
                tangent_max - tangent_min,
                z1 - z0,
            ),
            tuple(center),
            rotation_z=angle,
            bevel=0.2,
        )

    tools.append(
        local_box(
            "Camera_Bracket_Primary_Plate_Clearance",
            bracket["plate_radial_min"] - clearance,
            bracket["plate_radial_max"] + clearance,
            bracket["plate_tangent_min"] - clearance,
            bracket["plate_tangent_max"] + clearance,
            underside - clearance,
            top + clearance,
        )
    )
    if bracket.get("usb_side_locator_enabled", False):
        tools.append(
            local_box(
                "Camera_Bracket_USB_Side_Locator_Clearance",
                bracket["usb_locator_radial_min"] - clearance,
                bracket["usb_locator_radial_max"] + clearance,
                bracket["usb_locator_tangent_min"] - clearance,
                bracket["usb_locator_tangent_max"] + clearance,
                bracket["usb_locator_z_min"] - clearance,
                bracket["usb_locator_z_max"] + clearance,
            )
        )
    if bracket.get("non_usb_side_locator_enabled", False):
        tools.append(
            local_box(
                "Camera_Bracket_Non_USB_Side_Locator_Clearance",
                bracket["non_usb_locator_radial_min"] - clearance,
                bracket["non_usb_locator_radial_max"] + clearance,
                bracket["non_usb_locator_tangent_min"] - clearance,
                bracket["non_usb_locator_tangent_max"] + clearance,
                bracket["non_usb_locator_z_min"] - clearance,
                bracket["non_usb_locator_z_max"] + clearance,
            )
        )
    if bracket.get("usb_locator_gusset_enabled", False):
        tools.append(
            local_box(
                "Camera_Bracket_USB_Locator_Gusset_Clearance",
                bracket["usb_gusset_radial_min"] - clearance,
                bracket["usb_gusset_radial_max"] + clearance,
                bracket["usb_gusset_tangent_min"] - clearance,
                bracket["usb_gusset_tangent_max"] + clearance,
                bracket["usb_gusset_z_min"] - clearance,
                bracket["usb_gusset_z_max"] + clearance,
            )
        )
    if bracket.get("non_usb_locator_gusset_enabled", False):
        tools.append(
            local_box(
                "Camera_Bracket_Non_USB_Locator_Gusset_Clearance",
                bracket["non_usb_gusset_radial_min"] - clearance,
                bracket["non_usb_gusset_radial_max"] + clearance,
                bracket["non_usb_gusset_tangent_min"] - clearance,
                bracket["non_usb_gusset_tangent_max"] + clearance,
                bracket["non_usb_gusset_z_min"] - clearance,
                bracket["non_usb_gusset_z_max"] + clearance,
            )
        )
    rear_lip_segment_count = int(bracket.get("rear_lip_segment_count", 1))
    for segment_index in range(1, rear_lip_segment_count + 1):
        prefix = f"rear_lip_{segment_index}_"
        tools.append(
            local_box(
                f"Camera_Bracket_Rear_Lip_{segment_index}_Clearance",
                bracket.get(
                    prefix + "radial_min",
                    bracket["rear_lip_radial_min"],
                )
                - clearance,
                bracket.get(
                    prefix + "radial_max",
                    bracket["rear_lip_radial_max"],
                )
                + clearance,
                bracket.get(
                    prefix + "tangent_min",
                    bracket["rear_lip_tangent_min"],
                )
                - clearance,
                bracket.get(
                    prefix + "tangent_max",
                    bracket["rear_lip_tangent_max"],
                )
                + clearance,
                bracket.get(prefix + "z_min", bracket["rear_lip_z_min"])
                - clearance,
                bracket.get(prefix + "z_max", bracket["rear_lip_z_max"])
                + clearance,
            )
        )
    boss_radius = bracket["boss_radius"] + clearance
    for boss_index in (1, 2):
        tools.append(
            add_cylinder_z(
                f"Camera_Bracket_Screw_Boss_{boss_index}_Clearance",
                boss_radius,
                underside - clearance,
                top + clearance,
                bracket[f"boss_{boss_index}_x"],
                bracket[f"boss_{boss_index}_y"],
            )
        )
    for arm_index in range(1, bracket["arm_count"] + 1):
        tools.append(
            add_beveled_box(
                f"Camera_Bracket_Arm_{arm_index}_Clearance",
                (
                    bracket[f"arm_{arm_index}_length"] + 2.0 * clearance,
                    CAMERA_BRACKET_ARM_WIDTH + 2.0 * clearance,
                    CAMERA_BRACKET_THICKNESS + 2.0 * clearance,
                ),
                (
                    bracket[f"arm_{arm_index}_center_x"],
                    bracket[f"arm_{arm_index}_center_y"],
                    (underside + top) / 2.0,
                ),
                rotation_z=bracket[f"arm_{arm_index}_angle"],
                bevel=0.2,
            )
        )
    return tools


def create_camera_brackets(cameras, bracket_position_pairs):
    if not CAMERA_BRACKETS_ENABLED:
        return []
    brackets = [
        (
            create_adjustable_camera_hold_down(camera, positions)
            if camera_is_adjustable(camera)
            else create_camera_bracket(camera, positions)
        )
        for camera, positions in zip(cameras, bracket_position_pairs)
    ]
    if (
        len(brackets) == 2
        and CAMERA_BRACKET_MUTUAL_CLEARANCE > 0.0
        and not any(camera_is_adjustable(camera) for camera in cameras)
    ):
        boolean_difference(
            brackets[1],
            camera_bracket_mutual_clearance_tools(brackets[0]),
            "Camera_Bracket_Mutual_Clearance_Notch",
        )
    # A wide-angle configuration can bring one removable bracket close to the
    # opposite camera even after bracket-vs-bracket notching.  Cut the complete
    # opposite-camera envelope (plus fit clearance) out of each bracket.
    clearance = CAMERA_BRACKET_OTHER_CAMERA_CLEARANCE
    for bracket_index, bracket in enumerate(brackets):
        for camera_index, camera in enumerate(cameras):
            if bracket_index == camera_index:
                continue
            center = axis_point(
                camera["angle"],
                camera["radial"],
                camera["tangent"],
                camera_body_center_z(),
            )
            cutter = add_beveled_box(
                f"Bracket_{bracket_index + 1}_Camera_{camera_index + 1}_Clearance",
                (
                    CAMERA_BODY_DEPTH + 2.0 * clearance,
                    CAMERA_BODY_WIDTH + 2.0 * clearance,
                    CAMERA_BODY_HEIGHT + 2.0 * clearance,
                ),
                tuple(center),
                rotation_z=math.radians(camera["angle"]),
                bevel=0.0,
            )
            boolean_difference(
                bracket,
                [cutter],
                f"Bracket_{bracket_index + 1}_Opposite_Camera_Clearance",
            )
    if brackets:
        body_top = camera_eye_center_z() + mission1.canonical_body_bounds(
            CAMERA_UPSIDE_DOWN
        )[2][1]
        plate_underside, _ = camera_bracket_z_bounds()
        travel = camera_bracket_clamp_travel()
        print(
            "CAMERA_CLAMP_STACK "
            f"body_top={body_top:.2f} loose_rail_gap="
            f"{CAMERA_BRACKET_BODY_CONTACT_CLEARANCE_Z:.2f} "
            f"tightening_travel={travel:.2f} preload="
            f"{CAMERA_BRACKET_CLAMP_PRELOAD_Z:.2f} "
            f"final_plate_underside={plate_underside - travel:.2f}"
        )
    return brackets


def add_adjustable_carrier_top_loading_chimney(base, cameras):
    """Clear a vertical cartridge-installation and cooling shaft."""
    camera = adjustable_camera(cameras)
    if (
        camera is None
        or not CAMERA_CARRIER_TOP_LOADING_CHIMNEY_ENABLED
    ):
        return base
    body_radial, body_tangent, body_vertical = (
        mission1.canonical_body_bounds(CAMERA_UPSIDE_DOWN)
    )
    chimney_loop, radial_bounds, tangent_bounds = (
        adjustable_carrier_top_loading_chimney_loop(camera)
    )
    radial_min, radial_max = radial_bounds
    tangent_min, tangent_max = tangent_bounds
    z0 = camera_eye_center_z() + body_vertical[0] - BOOLEAN_OVERLAP
    z1 = BASE_HEIGHT + BOOLEAN_OVERLAP
    chimney = polygon_prism_z(
        "Adjustable_Carrier_Top_Loading_Airflow_Chimney",
        chimney_loop,
        z0,
        z1,
    )
    boolean_difference(
        base,
        [chimney],
        "Adjustable_Carrier_Top_Loading_Airflow_Chimney",
    )
    if CAMERA_CARRIER_CHIMNEY_REMOVE_SMALL_FRAGMENTS:
        remove_small_disconnected_shells(
            base,
            CAMERA_CARRIER_CHIMNEY_MAX_FRAGMENT_FACES,
            CAMERA_CARRIER_CHIMNEY_MAX_FRAGMENT_VOLUME,
            CAMERA_CARRIER_CHIMNEY_MAX_FRAGMENT_EXTENT,
            "Adjustable_Carrier_Top_Loading_Airflow_Chimney",
        )
    print(
        "CAMERA_CARTRIDGE_LOADING_AIRFLOW_CHIMNEY "
        f"local_size=({radial_max - radial_min:.2f},"
        f"{tangent_max - tangent_min:.2f}) "
        f"yaw_sweep=[{-ADJUSTABLE_CAMERA_YAW_RANGE_DEG:.2f},"
        f"{ADJUSTABLE_CAMERA_YAW_RANGE_DEG:.2f}] "
        f"z=({z0:.2f},{z1:.2f})"
    )
    return base


def create_base(
    positions,
    cameras,
    footprint,
    bracket_position_pairs,
    bottom_mount_hole_position=None,
    bottom_keystone_positions=(),
):
    outer_sections = tuple(
        (z, scale_loop(footprint, scale))
        for z, scale in BODY_SECTIONS
    )
    cavity_z_values = [BOTTOM_THICKNESS]
    cavity_z_values.extend(
        z for z, _ in BODY_SECTIONS[1:-1] if BOTTOM_THICKNESS < z < BASE_HEIGHT
    )
    cavity_z_values.append(BASE_HEIGHT)
    inner_sections = []
    for z in cavity_z_values:
        scale = body_scale_at_z(z)
        inner_sections.append(
            (
                z,
                inset_footprint_loop(
                    scale_loop(footprint, scale), BODY_WALL_THICKNESS
                ),
            )
        )
    base = hollow_loft_solid(
        "Veo_3_Closed_Bottom_Base",
        outer_sections,
        tuple(inner_sections),
    )
    add_camera_openings_and_visors(base, cameras)
    add_camera_front_stops(base, cameras)
    add_camera_cradles(base, cameras)
    add_adjustable_camera_base_hardware(base, cameras, footprint)
    add_rear_fan_mounts(
        base,
        footprint,
        [
            *(
                (x, y, FASTENER_POST_DIAMETER / 2.0)
                for x, y in positions
            ),
            *(
                (x, y, CAMERA_BRACKET_POST_BASE_DIAMETER / 2.0)
                for pair in bracket_position_pairs
                for x, y in pair
            ),
        ],
    )
    add_fastener_posts(base, positions)
    add_camera_bracket_posts(base, bracket_position_pairs)
    add_bottom_mount_hole(base, bottom_mount_hole_position)
    add_bottom_keystone_mounts(base, bottom_keystone_positions)
    add_adjustable_carrier_top_loading_chimney(base, cameras)
    # Cut plug access after all interior hardware so no post, fan pad, or worm
    # structure can silently refill the USB/battery service corridor.
    add_camera_usb_access_openings(base, cameras)
    if (
        CAMERA_CARTRIDGE_WORM_ENABLED
        and CAMERA_CARRIER_CHIMNEY_REMOVE_SMALL_FRAGMENTS
    ):
        # On the opposite cartridge hand, the final USB service cut can isolate
        # one more bounded eye-surround remnant after the chimney cleanup.  Use
        # the same strict size ceiling; a structural split still raises.
        remove_small_disconnected_shells(
            base,
            CAMERA_CARRIER_CHIMNEY_MAX_FRAGMENT_FACES,
            CAMERA_CARRIER_CHIMNEY_MAX_FRAGMENT_VOLUME,
            CAMERA_CARRIER_CHIMNEY_MAX_FRAGMENT_EXTENT,
            "Adjustable_Carrier_Final_Service_Cuts",
        )
    base.name = "Veo_3_Cam_Cover_Closed_Base"
    return base


def add_lid_eye_closures(lid, cameras):
    if not EYE_TOP_LOADING_ENABLED:
        return lid
    z0 = eye_top_loading_slot_bottom_z()
    z1 = BASE_HEIGHT + EYE_LID_CLOSURE_PLATE_EMBED
    main_width = (
        EYE_TOP_LOADING_SLOT_WIDTH
        - 2.0 * EYE_LID_CLOSURE_FIT_CLEARANCE
    )
    backing_width = (
        main_width + 2.0 * EYE_LID_CLOSURE_BACKING_SIDE_OVERLAP
    )
    for camera in cameras:
        index = camera["index"]
        main_radial, backing_radial = eye_lid_closure_radial_bounds(camera)
        closure = eye_axis_box(
            f"Lid_Eye_{index}_Central_Closure_Tongue",
            camera,
            main_radial,
            main_width,
            z0,
            z1,
        )
        backing = eye_axis_box(
            f"Lid_Eye_{index}_Inside_Keyed_Backing_Flange",
            camera,
            backing_radial,
            backing_width,
            z0,
            z1,
        )
        boolean_union(
            closure,
            backing,
            f"Lid_Eye_{index}_Keyed_Backing_Union",
            solver="MANIFOLD",
        )
        aperture_clearance = EYE_LID_CLOSURE_APERTURE_CLEARANCE
        aperture = rounded_rectangle_prism_axis(
            f"Lid_Eye_{index}_Restored_Upper_Aperture",
            camera["angle"],
            backing_radial[0] - BOOLEAN_OVERLAP,
            main_radial[1] + BOOLEAN_OVERLAP,
            EYE_OPENING_WIDTH + 2.0 * aperture_clearance,
            EYE_OPENING_HEIGHT + 2.0 * aperture_clearance,
            EYE_OPENING_CORNER_RADIUS + aperture_clearance,
            camera_eye_center_z(),
            center_tangent=camera["eye_tangent"],
        )
        aperture_cutters = [aperture]
        if camera_is_adjustable(camera):
            for sample_index, yaw_delta in enumerate(
                adjustable_yaw_samples(),
                start=1,
            ):
                pose_angle = camera["angle"] + yaw_delta
                lens_center = adjustable_camera_local_point(
                    camera,
                    0.0,
                    0.0,
                    camera_eye_center_z(),
                    yaw_delta,
                )
                pose_radians = math.radians(pose_angle)
                pose_normal = (
                    math.cos(pose_radians),
                    math.sin(pose_radians),
                )
                pose_tangent_axis = (
                    -math.sin(pose_radians),
                    math.cos(pose_radians),
                )
                center_radial = (
                    lens_center.x * pose_normal[0]
                    + lens_center.y * pose_normal[1]
                )
                center_tangent = (
                    lens_center.x * pose_tangent_axis[0]
                    + lens_center.y * pose_tangent_axis[1]
                )
                aperture_cutters.append(
                    rounded_rectangle_prism_axis(
                        f"Lid_Eye_{index}_Swept_Upper_Throat_{sample_index}",
                        pose_angle,
                        center_radial
                        + mission1.LENS_SHOULDER_Y
                        - mission1.LENS_FACE_Y
                        - aperture_clearance,
                        center_radial + EYE_CUTTER_OUTWARD_EXTENSION,
                        mission1.LENS_FACE_WIDTH
                        + 2.0 * aperture_clearance,
                        mission1.LENS_FACE_HEIGHT
                        + 2.0 * aperture_clearance,
                        mission1.LENS_FACE_CORNER_RADIUS
                        + aperture_clearance,
                        camera_eye_center_z(),
                        center_tangent=center_tangent,
                    )
                )
        boolean_difference(
            closure,
            aperture_cutters,
            f"Lid_Eye_{index}_Upper_Aperture_Cut",
        )
        if VISORS_ENABLED:
            visor_piece = visor_wedge(
                f"Lid_Eye_{index}_Split_Eyelid_Visor",
                camera["angle"],
                camera["surface"],
                center_tangent=camera["eye_tangent"],
            )
            visor_clip = eye_axis_box(
                f"Lid_Eye_{index}_Visor_Slot_Clip",
                camera,
                eye_opening_cutter_radial_bounds(camera),
                main_width,
                z0,
                BASE_HEIGHT + BOOLEAN_OVERLAP,
            )
            apply_boolean(
                visor_piece,
                visor_clip,
                "INTERSECT",
                f"Lid_Eye_{index}_Visor_Slot_Intersection",
                solver="MANIFOLD",
            )
            boolean_union(
                closure,
                visor_piece,
                f"Lid_Eye_{index}_Visor_Union",
                solver="MANIFOLD",
            )
            # The aperture cut removes the central closure material below the
            # aperture roof.  These two outside root ribs span that short gap
            # and tie the removable visor center into the keyed lid tongue.
            # They remain within main_width, avoiding the base-side visor
            # wings and the U-slot fit-clearance envelope.
            rib_radial_width = main_radial[1] - main_radial[0]
            rib_z0 = min(
                resolved_visor_z(VISOR_BACK_TOP_Z),
                resolved_visor_z(VISOR_FRONT_TOP_Z),
            ) - BOOLEAN_OVERLAP
            rib_z1 = (
                camera_eye_center_z()
                + EYE_OPENING_HEIGHT / 2.0
                + EYE_LID_CLOSURE_APERTURE_CLEARANCE
                + BOOLEAN_OVERLAP
            )
            # An automatically lifted visor can already rise above the
            # aperture roof.  In that case a short one-millimeter bridge is
            # sufficient and avoids producing a reversed/negative-height rib.
            rib_z0 = min(rib_z0, rib_z1 - 1.0)
            rib_tangent_offset = (
                main_width / 2.0
                - EYE_LID_VISOR_ROOT_RIB_EDGE_INSET
                - EYE_LID_VISOR_ROOT_RIB_WIDTH / 2.0
            )
            for rib_index, tangent_sign in enumerate((-1.0, 1.0), start=1):
                rib_center = axis_point(
                    camera["angle"],
                    sum(main_radial) / 2.0,
                    camera["eye_tangent"]
                    + tangent_sign * rib_tangent_offset,
                    (rib_z0 + rib_z1) / 2.0,
                )
                root_rib = add_beveled_box(
                    f"Lid_Eye_{index}_Visor_Root_Rib_{rib_index}",
                    (
                        rib_radial_width,
                        EYE_LID_VISOR_ROOT_RIB_WIDTH,
                        rib_z1 - rib_z0,
                    ),
                    tuple(rib_center),
                    rotation_z=math.radians(camera["angle"]),
                    bevel=0.35,
                )
                boolean_union(
                    closure,
                    root_rib,
                    f"Lid_Eye_{index}_Visor_Root_Rib_{rib_index}_Union",
                    solver="MANIFOLD",
                )
        boolean_union(
            lid,
            closure,
            f"Lid_Eye_{index}_Closure_Union",
            solver="MANIFOLD",
        )
        print(
            f"LID_EYE_CLOSURE {index}: tongue_width={main_width:.2f} "
            f"backing_width={backing_width:.2f} z=({z0:.2f}, {z1:.2f})"
        )
    return lid


def add_lid_camera_bracket_reliefs(lid, cameras):
    """Notch only the descending alignment lip around bracket guide roofs."""
    if not (
        LID_LIP_ENABLED
        and CAMERA_BRACKETS_ENABLED
        and CAMERA_BRACKET_L_CORNER_GUIDES_ENABLED
    ):
        return lid
    clearance = CAMERA_BRACKET_LID_LIP_RELIEF_CLEARANCE
    z0 = BASE_HEIGHT - LID_LIP_DEPTH - BOOLEAN_OVERLAP
    z1 = BASE_HEIGHT + BOOLEAN_OVERLAP
    relief_count = 0
    for camera in cameras:
        radial_bounds, tangent_bounds = (
            camera_bracket_guide_plate_local_bounds(camera)
        )
        center = axis_point(
            camera["angle"],
            sum(radial_bounds) / 2.0,
            sum(tangent_bounds) / 2.0,
            (z0 + z1) / 2.0,
        )
        cutter = add_beveled_box(
            f"Lid_Camera_Bracket_{camera['index']}_Lip_Relief",
            (
                radial_bounds[1] - radial_bounds[0] + 2.0 * clearance,
                tangent_bounds[1] - tangent_bounds[0] + 2.0 * clearance,
                z1 - z0,
            ),
            tuple(center),
            rotation_z=math.radians(camera["angle"]),
            bevel=0.0,
        )
        boolean_difference(
            lid,
            [cutter],
            f"Lid_Camera_Bracket_{camera['index']}_Lip_Relief_Cut",
        )
        relief_count += 1
    print(
        "LID_CAMERA_BRACKET_LIP_RELIEFS "
        f"count={relief_count} clearance={clearance:.2f}"
    )
    return lid


def create_lid(positions, footprint, cameras):
    outer_loop = list(footprint)
    if LID_LIP_ENABLED:
        lip_outer_loop = inset_footprint_loop(
            footprint, BODY_WALL_THICKNESS + LID_LIP_CLEARANCE
        )
        lip_inner_loop = inset_footprint_loop(
            lip_outer_loop,
            LID_LIP_THICKNESS,
        )
        lid = lid_with_alignment_lip(
            "Veo_3_Flat_Removable_Lid",
            outer_loop,
            lip_outer_loop,
            lip_inner_loop,
        )
    else:
        lid = loft_solid(
            "Veo_3_Flat_Removable_Lid",
            ((BASE_HEIGHT, outer_loop), (BODY_HEIGHT, outer_loop)),
        )

    add_lid_eye_closures(lid, cameras)
    add_lid_camera_bracket_reliefs(lid, cameras)

    if FASTENERS_ENABLED:
        clearance_cutters = [
            add_cylinder_z(
                f"Lid_Screw_Clearance_{index}",
                LID_SCREW_CLEARANCE_DIAMETER / 2.0,
                BASE_HEIGHT - LID_LIP_DEPTH - BOOLEAN_OVERLAP,
                BODY_HEIGHT + BOOLEAN_OVERLAP,
                x,
                y,
            )
            for index, (x, y) in enumerate(positions, start=1)
        ]
        boolean_difference(lid, clearance_cutters, "Lid_Screw_Clearance_Holes")

        counterbore_cutters = [
            add_cylinder_z(
                f"Lid_Socket_Head_Counterbore_{index}",
                LID_SCREW_HEAD_COUNTERBORE_DIAMETER / 2.0,
                BODY_HEIGHT - LID_SCREW_HEAD_COUNTERBORE_DEPTH,
                BODY_HEIGHT + 2.0 * BOOLEAN_OVERLAP,
                x,
                y,
            )
            for index, (x, y) in enumerate(positions, start=1)
        ]
        boolean_difference(lid, counterbore_cutters, "Lid_Socket_Head_Counterbores")
    lid.name = "Veo_3_Cam_Cover_Flat_Lid"
    return lid


# ---------------------------------------------------------------------------
# Validation, export, and preview


def assign_material(obj, name: str, color) -> None:
    material = bpy.data.materials.get(name)
    if material is None:
        material = bpy.data.materials.new(name)
    material.diffuse_color = color
    obj.data.materials.clear()
    obj.data.materials.append(material)


def create_camera_mockups(cameras, force=False):
    if not PREVIEW_SHOW_CAMERA_MOCKUPS and not force:
        return []
    mockups = []
    for camera in cameras:
        lens_face_radius = camera["radial"] + CAMERA_BODY_DEPTH / 2.0
        if camera_is_adjustable(camera):
            yaw_delta = ADJUSTABLE_CAMERA_PREVIEW_YAW_DEG
            lens_center = adjustable_camera_local_point(
                camera,
                0.0,
                0.0,
                camera_eye_center_z(),
                yaw_delta,
            )
            mockup = mission1.build_mission1_dummy(
                name=f"Camera_{camera['index']}_Keepout_Mockup",
                canonical=True,
                upside_down=CAMERA_UPSIDE_DOWN,
            )
            mockup.location = tuple(lens_center)
            mockup.rotation_euler.z = math.radians(
                camera["angle"] + yaw_delta
            )
            bpy.context.view_layer.update()
        else:
            mockup = mission1.place_canonical_dummy(
                camera["angle"],
                lens_face_radius,
                camera_eye_center_z(),
                f"Camera_{camera['index']}_Keepout_Mockup",
                upside_down=CAMERA_UPSIDE_DOWN,
            )
        assign_material(mockup, "Camera_Keepout_Material", CAMERA_COLOR)
        mockups.append(mockup)
    return mockups


def create_camera_usb_access_keepout(camera, yaw_delta=None):
    radial, tangent, vertical = camera_usb_local_access_bounds()
    lens_face_radius = camera["radial"] + CAMERA_BODY_DEPTH / 2.0
    if yaw_delta is None:
        yaw_delta = (
            ADJUSTABLE_CAMERA_PREVIEW_YAW_DEG
            if camera_is_adjustable(camera)
            else 0.0
        )
    if camera_is_adjustable(camera):
        center = adjustable_camera_local_point(
            camera,
            sum(radial) / 2.0,
            sum(tangent) / 2.0,
            camera_eye_center_z() + sum(vertical) / 2.0,
            yaw_delta,
        )
    else:
        center = axis_point(
            camera["angle"],
            lens_face_radius + sum(radial) / 2.0,
            camera["eye_tangent"] + sum(tangent) / 2.0,
            camera_eye_center_z() + sum(vertical) / 2.0,
        )
    return add_beveled_box(
        f"Camera_{camera['index']}_USB_Plug_Access_Keepout",
        (
            radial[1] - radial[0],
            tangent[1] - tangent[0],
            vertical[1] - vertical[0],
        ),
        tuple(center),
        rotation_z=math.radians(camera["angle"] + yaw_delta),
        bevel=0.0,
    )


def triangulate_mesh(obj) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def non_manifold_edge_count(obj) -> int:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    count = sum(1 for edge in bm.edges if not edge.is_manifold)
    bm.free()
    return count


def connected_shell_count(obj) -> int:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    remaining = set(bm.faces)
    shell_count = 0
    while remaining:
        shell_count += 1
        stack = [remaining.pop()]
        while stack:
            face = stack.pop()
            for edge in face.edges:
                for linked in edge.link_faces:
                    if linked in remaining:
                        remaining.remove(linked)
                        stack.append(linked)
    bm.free()
    return shell_count


def validate_object(obj) -> None:
    non_manifold = non_manifold_edge_count(obj)
    shells = connected_shell_count(obj)
    dimensions = tuple(round(value, 3) for value in obj.dimensions)
    print(
        f"VALIDATION {obj.name}: dimensions={dimensions} "
        f"vertices={len(obj.data.vertices)} faces={len(obj.data.polygons)} "
        f"non_manifold_edges={non_manifold} connected_shells={shells}"
    )
    if non_manifold:
        raise RuntimeError(f"{obj.name} has {non_manifold} non-manifold edges")
    if shells != 1:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        remaining = set(bm.faces)
        diagnostics = []
        while remaining:
            component_faces = {remaining.pop()}
            stack = list(component_faces)
            while stack:
                face = stack.pop()
                for edge in face.edges:
                    for linked in edge.link_faces:
                        if linked in remaining:
                            remaining.remove(linked)
                            component_faces.add(linked)
                            stack.append(linked)
            component_vertices = {
                vertex
                for face in component_faces
                for vertex in face.verts
            }
            bounds = tuple(
                (
                    min(vertex.co[axis] for vertex in component_vertices),
                    max(vertex.co[axis] for vertex in component_vertices),
                )
                for axis in range(3)
            )
            diagnostics.append(
                (
                    len(component_faces),
                    tuple(
                        (round(low, 3), round(high, 3))
                        for low, high in bounds
                    ),
                )
            )
        bm.free()
        diagnostics.sort(reverse=True)
        print(f"DISCONNECTED_SHELL_BOUNDS {obj.name}: {diagnostics}")
        raise RuntimeError(f"{obj.name} has {shells} connected shells")


def duplicate_object(obj, name: str):
    duplicate = obj.copy()
    duplicate.data = obj.data.copy()
    duplicate.name = name
    bpy.context.collection.objects.link(duplicate)
    return duplicate


def intersection_metrics(first, second, label: str):
    first_copy = duplicate_object(first, label + "_A")
    second_copy = duplicate_object(second, label + "_B")
    select_only(first_copy)
    modifier = first_copy.modifiers.new(label, "BOOLEAN")
    modifier.operation = "INTERSECT"
    modifier.object = second_copy
    if hasattr(modifier, "solver"):
        modifier.solver = BOOLEAN_SOLVER
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bm = bmesh.new()
    bm.from_mesh(first_copy.data)
    faces = len(bm.faces)
    vertices = len(bm.verts)
    volume = abs(bm.calc_volume(signed=True)) if bm.faces else 0.0
    if bm.verts:
        bounds = [
            (
                min(vertex.co[axis] for vertex in bm.verts),
                max(vertex.co[axis] for vertex in bm.verts),
            )
            for axis in range(3)
        ]
        extents = tuple(high - low for low, high in bounds)
        if min(extents) <= ASSEMBLY_COPLANAR_CONTACT_TOLERANCE:
            if volume > 0.0:
                print(
                    f"COPLANAR_INTERSECTION_IGNORED {label}: "
                    f"extents={tuple(round(value, 6) for value in extents)} "
                    f"raw_volume={volume:.9f}"
                )
            volume = 0.0
        if (
            label.startswith("carrier_installation_")
            or label.startswith("adjustable_carrier_base_yaw_")
            or label.startswith("adjustable_sector_worm_yaw_")
            or label.endswith("_installed_in_carrier")
        ) and volume > CAMERA_INSTALLATION_INTERSECTION_VOLUME_TOLERANCE:
            world_bounds = tuple(
                (
                    min(
                        (first_copy.matrix_world @ vertex.co)[axis]
                        for vertex in bm.verts
                    ),
                    max(
                        (first_copy.matrix_world @ vertex.co)[axis]
                        for vertex in bm.verts
                    ),
                )
                for axis in range(3)
            )
            print(
                f"CARRIER_INSTALLATION_INTERSECTION_BOUNDS {label}: "
                "local_bounds="
                f"{tuple(tuple(round(value, 3) for value in pair) for pair in bounds)} "
                "world_bounds="
                f"{tuple(tuple(round(value, 3) for value in pair) for pair in world_bounds)}"
            )
            if label.endswith("_installed_in_carrier"):
                remaining_faces = set(bm.faces)
                solid_component_bounds = []
                while remaining_faces:
                    component_faces = {remaining_faces.pop()}
                    stack = list(component_faces)
                    while stack:
                        face = stack.pop()
                        for edge in face.edges:
                            for linked in edge.link_faces:
                                if linked in remaining_faces:
                                    remaining_faces.remove(linked)
                                    component_faces.add(linked)
                                    stack.append(linked)
                    component_vertices = {
                        vertex
                        for face in component_faces
                        for vertex in face.verts
                    }
                    component_bounds = tuple(
                        (
                            min(
                                vertex.co[axis]
                                for vertex in component_vertices
                            ),
                            max(
                                vertex.co[axis]
                                for vertex in component_vertices
                            ),
                        )
                        for axis in range(3)
                    )
                    component_extents = tuple(
                        high - low for low, high in component_bounds
                    )
                    if min(component_extents) > (
                        ASSEMBLY_COPLANAR_CONTACT_TOLERANCE
                    ):
                        solid_component_bounds.append(
                            tuple(
                                (round(low, 4), round(high, 4))
                                for low, high in component_bounds
                            )
                        )
                print(
                    "CARRIER_INSTALLED_SOLID_COMPONENT_BOUNDS "
                    f"{label}: {solid_component_bounds}"
                )
    bm.free()
    bpy.data.objects.remove(first_copy, do_unlink=True)
    bpy.data.objects.remove(second_copy, do_unlink=True)
    return vertices, faces, volume


def validate_camera_usb_access_clearances(
    base,
    camera_brackets,
    camera_mockups,
    cameras,
    camera_carrier=None,
):
    if not CAMERA_USB_ACCESS_ENABLED or not VALIDATE_CAMERA_USB_ACCESS:
        return
    for index, camera in enumerate(cameras):
        yaw_samples = (
            adjustable_yaw_samples(include_preview=True)
            if camera_is_adjustable(camera)
            else (0.0,)
        )
        for yaw_delta in yaw_samples:
            keepout = create_camera_usb_access_keepout(camera, yaw_delta)
            pairs = [("base", base)]
            pairs.extend(
                (f"bracket_{bracket_index}", bracket)
                for bracket_index, bracket in enumerate(
                    camera_brackets,
                    start=1,
                )
            )
            if len(camera_mockups) == len(cameras):
                pairs.extend(
                    (f"other_camera_{camera_index}", mockup)
                    for camera_index, mockup in enumerate(
                        camera_mockups,
                        start=1,
                    )
                    if camera_index != index + 1
                )
            temporary_objects = []
            if camera_is_adjustable(camera) and camera_carrier is not None:
                posed_carrier = posed_carrier_copy(
                    camera_carrier,
                    camera,
                    yaw_delta,
                    f"USB_Carrier_Yaw_{yaw_delta:+.1f}",
                )
                pairs.append(("rotating_carrier", posed_carrier))
                temporary_objects.append(posed_carrier)
                other_camera = cameras[1 - index]
                other_usb = create_camera_usb_access_keepout(
                    other_camera,
                    0.0,
                )
                pairs.append(("other_usb_corridor", other_usb))
                temporary_objects.append(other_usb)
            elif camera_carrier is not None:
                moving_camera = adjustable_camera(cameras)
                for carrier_yaw in adjustable_yaw_samples(
                    include_preview=True
                ):
                    swept_carrier = posed_carrier_copy(
                        camera_carrier,
                        moving_camera,
                        carrier_yaw,
                        f"Fixed_USB_Carrier_Yaw_{carrier_yaw:+.1f}",
                    )
                    pairs.append(
                        (
                            f"rotating_carrier_yaw_{carrier_yaw:+.1f}",
                            swept_carrier,
                        )
                    )
                    temporary_objects.append(swept_carrier)
            for suffix, other in pairs:
                _, _, volume = intersection_metrics(
                    keepout,
                    other,
                    f"camera_{index + 1}_usb_access_yaw_"
                    f"{yaw_delta:+.1f}_{suffix}",
                )
                print(
                    f"USB_ACCESS_CLEARANCE camera_{index + 1} "
                    f"yaw={yaw_delta:+.1f} {suffix}: volume={volume:.9f}"
                )
                if volume > CAMERA_USB_ACCESS_INTERSECTION_VOLUME_TOLERANCE:
                    bpy.data.objects.remove(keepout, do_unlink=True)
                    for temporary in temporary_objects:
                        bpy.data.objects.remove(temporary, do_unlink=True)
                    raise RuntimeError(
                        f"Camera {index + 1} USB plug access overlaps {suffix}"
                    )
            bpy.data.objects.remove(keepout, do_unlink=True)
            for temporary in temporary_objects:
                bpy.data.objects.remove(temporary, do_unlink=True)
    print("USB_ACCESS_CLEARANCE PASS")


def validate_camera_installation_paths(
    base,
    camera_mockups,
    cameras,
    camera_carrier=None,
):
    """Prove each bracket-free camera can follow its configured loading path."""
    if (
        not VALIDATE_CAMERA_INSTALLATION_PATH
        or len(camera_mockups) != len(cameras)
    ):
        return
    for index, (mockup, camera) in enumerate(
        zip(camera_mockups, cameras),
        start=1,
    ):
        angle = math.radians(camera["angle"])
        if EYE_TOP_LOADING_ENABLED:
            path_length = CAMERA_TOP_LOADING_LIFT
            path_vector = (0.0, 0.0, 1.0)
            path_mode = "top"
        else:
            path_length = CAMERA_INSTALLATION_REARWARD_TRAVEL
            path_vector = (-math.cos(angle), -math.sin(angle), 0.0)
            path_mode = "rearward"
        maximum_base_volume = 0.0
        maximum_other_camera_volume = 0.0
        maximum_carrier_volume = 0.0
        posed_carrier = None
        if camera_is_adjustable(camera) and camera_carrier is not None:
            posed_carrier = posed_carrier_copy(
                camera_carrier,
                camera,
                ADJUSTABLE_CAMERA_PREVIEW_YAW_DEG,
                f"Camera_{index}_Installation_Carrier",
            )
            fit_probe = duplicate_object(
                mockup,
                f"Camera_{index}_Installed_Fit_Probe",
            )
            fit_probe.location.z += CAMERA_CARRIER_FIT_PROBE_LIFT
            bpy.context.view_layer.update()
            _, _, final_carrier_volume = intersection_metrics(
                fit_probe,
                posed_carrier,
                f"camera_{index}_installed_in_carrier",
            )
            bpy.data.objects.remove(fit_probe, do_unlink=True)
            print(
                f"CAMERA_CARRIER_INSTALLED_FIT camera={index} "
                f"floor_contact_probe_lift="
                f"{CAMERA_CARRIER_FIT_PROBE_LIFT:.2f} "
                f"volume={final_carrier_volume:.9f}"
            )
            if (
                final_carrier_volume
                > CAMERA_INSTALLATION_INTERSECTION_VOLUME_TOLERANCE
            ):
                bpy.data.objects.remove(posed_carrier, do_unlink=True)
                raise RuntimeError(
                    f"Camera {index} does not fit its rotating carrier"
                )
        for step in range(1, CAMERA_INSTALLATION_PATH_STEPS + 1):
            distance = path_length * step / CAMERA_INSTALLATION_PATH_STEPS
            moving_camera = duplicate_object(
                mockup,
                f"Camera_{index}_Installation_Path_{step}",
            )
            moving_camera.location.x += path_vector[0] * distance
            moving_camera.location.y += path_vector[1] * distance
            moving_camera.location.z += path_vector[2] * distance
            bpy.context.view_layer.update()
            _, _, base_volume = intersection_metrics(
                moving_camera,
                base,
                f"camera_{index}_installation_step_{step}_base",
            )
            if base_volume > CAMERA_INSTALLATION_INTERSECTION_VOLUME_TOLERANCE:
                print(
                    f"CAMERA_INSTALLATION_OBSTRUCTION camera={index} "
                    f"distance={distance:.2f} part=base "
                    f"volume={base_volume:.9f}"
                )
            maximum_base_volume = max(maximum_base_volume, base_volume)
            for other_index, other_camera in enumerate(
                camera_mockups,
                start=1,
            ):
                if other_index == index:
                    continue
                _, _, other_volume = intersection_metrics(
                    moving_camera,
                    other_camera,
                    f"camera_{index}_installation_step_{step}_camera_"
                    f"{other_index}",
                )
                if (
                    other_volume
                    > CAMERA_INSTALLATION_INTERSECTION_VOLUME_TOLERANCE
                ):
                    print(
                        f"CAMERA_INSTALLATION_OBSTRUCTION camera={index} "
                        f"distance={distance:.2f} "
                        f"part=camera_{other_index} "
                        f"volume={other_volume:.9f}"
                    )
                maximum_other_camera_volume = max(
                    maximum_other_camera_volume,
                    other_volume,
                )
            if posed_carrier is not None:
                _, _, carrier_volume = intersection_metrics(
                    moving_camera,
                    posed_carrier,
                    f"camera_{index}_installation_step_{step}_carrier",
                )
                maximum_carrier_volume = max(
                    maximum_carrier_volume,
                    carrier_volume,
                )
            bpy.data.objects.remove(moving_camera, do_unlink=True)
        print(
            f"CAMERA_INSTALLATION_PATH {index}: "
            f"mode={path_mode} travel={path_length:.2f} "
            f"steps={CAMERA_INSTALLATION_PATH_STEPS} "
            f"max_base_volume={maximum_base_volume:.9f} "
            f"max_other_camera_volume={maximum_other_camera_volume:.9f} "
            f"max_carrier_volume={maximum_carrier_volume:.9f}"
        )
        maximum_volume = max(
            maximum_base_volume,
            maximum_other_camera_volume,
            maximum_carrier_volume,
        )
        if posed_carrier is not None:
            bpy.data.objects.remove(posed_carrier, do_unlink=True)
        if maximum_volume > CAMERA_INSTALLATION_INTERSECTION_VOLUME_TOLERANCE:
            raise RuntimeError(
                f"Camera {index} {path_mode} installation path is obstructed"
            )
    print("CAMERA_INSTALLATION_PATH PASS")


def validate_adjustable_carrier_installation_path(base, carrier, cameras):
    """Prove the cartridge can be lowered through the lid-off base opening."""
    if (
        not CAMERA_CARTRIDGE_WORM_ENABLED
        or not VALIDATE_CAMERA_INSTALLATION_PATH
        or carrier is None
    ):
        return
    camera = adjustable_camera(cameras)
    maximum_volume = 0.0
    for step in range(1, CAMERA_INSTALLATION_PATH_STEPS + 1):
        distance = CAMERA_TOP_LOADING_LIFT * step / CAMERA_INSTALLATION_PATH_STEPS
        moving_carrier = duplicate_object(
            carrier,
            f"Carrier_Installation_Path_{step}",
        )
        moving_carrier.location.z += distance
        bpy.context.view_layer.update()
        _, _, volume = intersection_metrics(
            moving_carrier,
            base,
            f"carrier_installation_step_{step}_base",
        )
        if volume > CAMERA_INSTALLATION_INTERSECTION_VOLUME_TOLERANCE:
            print(
                "CAMERA_CARRIER_INSTALLATION_OBSTRUCTION "
                f"step={step} distance={distance:.2f} "
                f"volume={volume:.9f}"
            )
        maximum_volume = max(maximum_volume, volume)
        bpy.data.objects.remove(moving_carrier, do_unlink=True)
    print(
        "CAMERA_CARRIER_INSTALLATION_PATH "
        f"camera={camera['index']} travel={CAMERA_TOP_LOADING_LIFT:.2f} "
        f"steps={CAMERA_INSTALLATION_PATH_STEPS} "
        f"max_base_volume={maximum_volume:.9f}"
    )
    if maximum_volume > CAMERA_INSTALLATION_INTERSECTION_VOLUME_TOLERANCE:
        raise RuntimeError("Rotating carrier top-loading path is obstructed")
    print("CAMERA_CARRIER_INSTALLATION_PATH PASS")


def rotate_mesh_about_world_axis(obj, origin, axis, angle_deg):
    """Rotate an object's mesh around an arbitrary world-space shaft line."""
    rotation = Matrix.Rotation(
        math.radians(angle_deg),
        4,
        Vector(axis).normalized(),
    )
    world_matrix = obj.matrix_world.copy()
    inverse_matrix = world_matrix.inverted()
    world_origin = Vector(origin)
    for vertex in obj.data.vertices:
        world = world_matrix @ vertex.co
        vertex.co = inverse_matrix @ (
            world_origin + rotation @ (world - world_origin)
        )
    obj.data.update()


def posed_carrier_copy(carrier, camera, yaw_delta, name):
    """Duplicate and yaw the lower cartridge about its installed pivot."""
    posed = duplicate_object(carrier, name)
    pivot = adjustable_camera_pivot(camera)
    rotate_mesh_about_world_axis(
        posed,
        (pivot.x, pivot.y, 0.0),
        (0.0, 0.0, 1.0),
        yaw_delta,
    )
    return posed


def validate_adjustable_camera_range(
    cameras,
    footprint,
    base,
    carrier,
    worm,
    camera_mockups,
    camera_brackets,
):
    if not CAMERA_CARTRIDGE_WORM_ENABLED:
        return
    camera = adjustable_camera(cameras)
    if camera is None or carrier is None or worm is None:
        raise RuntimeError("Adjustable camera parts were not generated")
    body_radial, body_tangent, _ = mission1.canonical_body_bounds(
        CAMERA_UPSIDE_DOWN
    )
    fixed_camera = cameras[1 - cameras.index(camera)]
    fixed_camera_index = cameras.index(fixed_camera)
    fixed_mockup = (
        camera_mockups[fixed_camera_index]
        if len(camera_mockups) == len(cameras)
        else None
    )
    fixed_envelope = convex_hull_2d(camera_xy_corners(fixed_camera))
    required_lens_edge_clearance = CAMERA_LENS_OPENING_CLEARANCE
    if REAR_FANS_ENABLED:
        required_lens_edge_clearance = max(
            required_lens_edge_clearance,
            CAMERA_COOLING_MIN_EYE_EDGE_GAP,
        )
    opening_width = EYE_OPENING_WIDTH - 2.0 * required_lens_edge_clearance
    opening_height = EYE_OPENING_HEIGHT - 2.0 * required_lens_edge_clearance
    opening_radius = max(
        EYE_OPENING_CORNER_RADIUS - required_lens_edge_clearance,
        0.0,
    )
    nominal_angle = math.radians(camera["angle"])
    nominal_tangent = (-math.sin(nominal_angle), math.cos(nominal_angle))
    lens_loop = rounded_rectangle_loop(
        mission1.LENS_FACE_WIDTH,
        mission1.LENS_FACE_HEIGHT,
        mission1.LENS_FACE_CORNER_RADIUS,
    )
    pivot = adjustable_camera_pivot(camera)
    mechanism = adjustable_mechanism_layout(cameras, footprint)
    for yaw_delta in adjustable_yaw_samples(include_preview=True):
        body_corners = adjustable_camera_pose_corners(
            camera,
            body_radial,
            body_tangent,
            yaw_delta,
        )
        body_inner_loop = inset_footprint_loop(
            scale_loop(footprint, camera_minimum_body_scale()),
            BODY_WALL_THICKNESS,
        )
        if not all(point_in_polygon(point, body_inner_loop) for point in body_corners):
            raise RuntimeError(
                f"Adjustable camera body leaves the cavity at yaw {yaw_delta:+.2f}"
            )
        moving_envelope = convex_hull_2d(
            adjustable_camera_pose_corners(
                camera,
                (
                    mission1.CANONICAL_RADIAL_MIN,
                    mission1.CANONICAL_RADIAL_MAX,
                ),
                mission1.canonical_tangential_bounds(CAMERA_UPSIDE_DOWN),
                yaw_delta,
                CAMERA_BODY_MUTUAL_CLEARANCE / 2.0,
            )
        )
        if convex_polygons_overlap(moving_envelope, fixed_envelope):
            raise RuntimeError(
                f"Cameras collide at adjustable yaw {yaw_delta:+.2f}"
            )
        for tangent, vertical in lens_loop:
            point = adjustable_camera_local_point(
                camera,
                0.0,
                tangent,
                camera_eye_center_z() + vertical,
                yaw_delta,
            )
            eye_tangent = (
                point.x * nominal_tangent[0]
                + point.y * nominal_tangent[1]
                - camera["eye_tangent"]
            )
            if not point_inside_rounded_rectangle(
                (eye_tangent, vertical),
                opening_width,
                opening_height,
                opening_radius,
            ):
                raise RuntimeError(
                    "Lens face violates the required eye-opening edge gap at "
                    f"yaw {yaw_delta:+.2f}; required="
                    f"{required_lens_edge_clearance:.2f} mm"
                )

        yaw_radians = math.radians(yaw_delta)
        cosine = math.cos(yaw_radians)
        sine = math.sin(yaw_radians)
        for vertex in carrier.data.vertices:
            world = carrier.matrix_world @ vertex.co
            dx = world.x - pivot.x
            dy = world.y - pivot.y
            point = (
                pivot.x + cosine * dx - sine * dy,
                pivot.y + sine * dx + cosine * dy,
            )
            inner = inset_footprint_loop(
                scale_loop(footprint, body_scale_at_z(world.z)),
                BODY_WALL_THICKNESS,
            )
            if not point_in_polygon(point, inner):
                boundary_gap = polygon_boundary_distance(point, inner)
                # The base intentionally receives physical sweep pockets for
                # all low carrier members.  Permit that configured shallow
                # incursion here; the solid carrier/base intersection test
                # below still proves the generated pockets actually clear it.
                allowed_boundary_gap = (
                    CAMERA_CARRIER_SWEEP_CUT_CLEARANCE
                    + CAMERA_CARRIER_CAVITY_NUMERICAL_TOLERANCE
                )
                if boundary_gap > allowed_boundary_gap:
                    raise RuntimeError(
                        f"Rotating carrier leaves the cavity at yaw "
                        f"{yaw_delta:+.2f}: point=({point[0]:.3f},"
                        f"{point[1]:.3f},{world.z:.3f}) "
                        f"boundary_gap={boundary_gap:.3f} "
                        f"allowed_local_relief={allowed_boundary_gap:.3f}"
                    )
    carrier_base = 0.0
    gear_mesh_overlap = 0.0
    carrier_stationary_overlap = 0.0
    worm_axis_origin = Vector(
        (
            mechanism["worm_center"].x,
            mechanism["worm_center"].y,
            BOTTOM_THICKNESS
            + CAMERA_WORM_FLOOR_CLEARANCE
            + camera_worm_outer_radius(),
        )
    )
    for yaw_delta in adjustable_yaw_samples(include_preview=True):
        posed_carrier = posed_carrier_copy(
            carrier,
            camera,
            yaw_delta,
            f"Carrier_Clearance_Yaw_{yaw_delta:+.1f}",
        )
        pose_overlap = intersection_metrics(
            posed_carrier,
            base,
            f"adjustable_carrier_base_yaw_{yaw_delta:+.1f}",
        )[2]
        carrier_base = max(carrier_base, pose_overlap)
        stationary_targets = []
        if fixed_mockup is not None:
            stationary_targets.append(
                (f"fixed_camera_{fixed_camera_index + 1}", fixed_mockup)
            )
        stationary_targets.extend(
            (f"bracket_{index}", bracket)
            for index, bracket in enumerate(camera_brackets, start=1)
        )
        for target_name, target in stationary_targets:
            target_overlap = intersection_metrics(
                posed_carrier,
                target,
                f"adjustable_carrier_yaw_{yaw_delta:+.1f}_{target_name}",
            )[2]
            carrier_stationary_overlap = max(
                carrier_stationary_overlap,
                target_overlap,
            )
            if target_overlap > ASSEMBLY_INTERSECTION_VOLUME_TOLERANCE:
                bpy.data.objects.remove(posed_carrier, do_unlink=True)
                raise RuntimeError(
                    "Rotating carrier overlaps "
                    f"{target_name} at yaw {yaw_delta:+.1f}: "
                    f"{target_overlap:.9f} mm^3"
                )
        posed_worm = duplicate_object(
            worm,
            f"Worm_Clearance_Yaw_{yaw_delta:+.1f}",
        )
        worm_rotation_deg = adjustable_worm_rotation_degrees(
            mechanism,
            yaw_delta,
        )
        rotate_mesh_about_world_axis(
            posed_worm,
            worm_axis_origin,
            mechanism["shaft_direction"],
            worm_rotation_deg,
        )
        pose_gear_overlap = intersection_metrics(
            posed_carrier,
            posed_worm,
            f"adjustable_sector_worm_yaw_{yaw_delta:+.1f}",
        )[2]
        gear_mesh_overlap = max(gear_mesh_overlap, pose_gear_overlap)
        bpy.data.objects.remove(posed_carrier, do_unlink=True)
        bpy.data.objects.remove(posed_worm, do_unlink=True)
        print(
            f"ADJUSTABLE_CARRIER_BASE_CLEARANCE yaw={yaw_delta:+.1f} "
            f"overlap={pose_overlap:.9f}"
        )
        print(
            f"ADJUSTABLE_GEAR_MESH_CLEARANCE yaw={yaw_delta:+.1f} "
            f"worm_rotation={worm_rotation_deg:+.1f}deg "
            f"overlap={pose_gear_overlap:.9f}"
        )
    worm_base = intersection_metrics(
        worm,
        base,
        "adjustable_worm_base",
    )[2]
    radial_engagement = (
        camera_sector_tip_radius()
        + camera_worm_outer_radius()
        - camera_sector_pitch_radius()
        - camera_worm_pitch_radius()
        - CAMERA_GEAR_MESH_CENTER_CLEARANCE
    )
    print(
        "ADJUSTABLE_RANGE_VALIDATION "
        f"yaw=[{-ADJUSTABLE_CAMERA_YAW_RANGE_DEG:.1f},"
        f"{ADJUSTABLE_CAMERA_YAW_RANGE_DEG:.1f}] "
        f"carrier_base_overlap={carrier_base:.9f} "
        f"carrier_stationary_overlap={carrier_stationary_overlap:.9f} "
        f"worm_base_overlap={worm_base:.9f} "
        f"gear_mesh_overlap={gear_mesh_overlap:.9f} "
        f"radial_engagement={radial_engagement:.3f}"
    )
    if carrier_base > ASSEMBLY_INTERSECTION_VOLUME_TOLERANCE:
        raise RuntimeError("Rotating carrier overlaps the stationary base")
    if worm_base > ASSEMBLY_INTERSECTION_VOLUME_TOLERANCE:
        raise RuntimeError("Worm overlaps its stationary bearing structure")
    for target_name, target in (
        *(
            ((f"fixed_camera_{fixed_camera_index + 1}", fixed_mockup),)
            if fixed_mockup is not None
            else ()
        ),
        *tuple(
            (f"bracket_{index}", bracket)
            for index, bracket in enumerate(camera_brackets, start=1)
        ),
    ):
        overlap = intersection_metrics(
            worm,
            target,
            f"adjustable_worm_{target_name}",
        )[2]
        if overlap > ASSEMBLY_INTERSECTION_VOLUME_TOLERANCE:
            raise RuntimeError(
                f"Worm overlaps {target_name}: {overlap:.9f} mm^3"
            )
    if gear_mesh_overlap > ASSEMBLY_INTERSECTION_VOLUME_TOLERANCE:
        raise RuntimeError("Worm and sector gear have solid interference")
    print("ADJUSTABLE_CAMERA_RANGE PASS")


def validate_assembly_clearances(base, lid, camera_brackets, camera_mockups):
    if not VALIDATE_ASSEMBLY_CLEARANCES:
        return
    pairs = [("base_lid", base, lid)]
    if len(camera_mockups) == 2:
        pairs.append(
            ("camera_1_camera_2", camera_mockups[0], camera_mockups[1])
        )
    if len(camera_brackets) == 2:
        pairs.append(
            ("bracket_1_bracket_2", camera_brackets[0], camera_brackets[1])
        )
    for camera_index, camera in enumerate(camera_mockups, start=1):
        pairs.extend(
            (
                (f"camera_{camera_index}_base", camera, base),
                (f"camera_{camera_index}_lid", camera, lid),
            )
        )
        for bracket_index, bracket in enumerate(camera_brackets, start=1):
            pairs.append(
                (
                    f"camera_{camera_index}_bracket_{bracket_index}",
                    camera,
                    bracket,
                )
            )
    for bracket_index, bracket in enumerate(camera_brackets, start=1):
        pairs.extend(
            (
                (f"bracket_{bracket_index}_base", bracket, base),
                (f"bracket_{bracket_index}_lid", bracket, lid),
            )
        )
    for label, first, second in pairs:
        vertices, faces, volume = intersection_metrics(first, second, label)
        print(
            f"ASSEMBLY_CLEARANCE {label}: vertices={vertices} faces={faces} "
            f"volume={volume:.9f}"
        )
        allowed_volume = ASSEMBLY_INTERSECTION_VOLUME_TOLERANCE
        if label in {"camera_1_base", "camera_2_base"}:
            allowed_volume = CAMERA_BASE_CONTACT_VOLUME_TOLERANCE
        if label in {"camera_1_bracket_1", "camera_2_bracket_2"}:
            allowed_volume = CAMERA_BRACKET_REAR_CONTACT_VOLUME_TOLERANCE
        if volume > allowed_volume:
            raise RuntimeError(
                f"Unexpected assembled overlap {label}: {volume:.9f} mm^3"
            )
    print("ASSEMBLY_CLEARANCE PASS")
    if (
        not VALIDATE_TIGHTENED_BRACKET_CLEARANCES
        or len(camera_brackets) != 2
        or len(camera_mockups) != 2
    ):
        return
    travel = camera_bracket_clamp_travel()
    for index, bracket in enumerate(camera_brackets):
        tightened = duplicate_object(
            bracket,
            f"Tightened_Bracket_{index + 1}",
        )
        tightened.location.z -= travel
        bpy.context.view_layer.update()
        own_camera = camera_mockups[index]
        other_camera = camera_mockups[1 - index]
        disk_thickness = bracket.get(
            "low_friction_disk_thickness_mm",
            0.0,
        )
        if disk_thickness > 0.0:
            body_top = camera_eye_center_z() + mission1.canonical_body_bounds(
                CAMERA_UPSIDE_DOWN
            )[2][1]
            final_printed_pad_gap = (
                bracket["contact_pad_bottom_z"] - travel - body_top
            )
            disk_compression = max(
                disk_thickness - final_printed_pad_gap,
                0.0,
            )
            disk_radius = bracket["low_friction_disk_diameter_mm"] / 2.0
            contact_volume = math.pi * disk_radius**2 * disk_compression
            print(
                f"TIGHTENED_LOW_FRICTION_DISK bracket_{index + 1}: "
                f"final_gap={final_printed_pad_gap:.3f} "
                f"compression={disk_compression:.3f}"
            )
        else:
            _, _, contact_volume = intersection_metrics(
                tightened,
                own_camera,
                f"tightened_bracket_{index + 1}_preload",
            )
        print(
            f"TIGHTENED_PRELOAD bracket_{index + 1}: "
            f"contact_volume={contact_volume:.9f}"
        )
        if contact_volume < CAMERA_BRACKET_MIN_PRELOAD_CONTACT_VOLUME:
            bpy.data.objects.remove(tightened, do_unlink=True)
            raise RuntimeError(
                f"Tightened bracket {index + 1} has insufficient camera contact"
            )
        clearance_pairs = (
            ("base", base),
            ("lid", lid),
            ("opposite_camera", other_camera),
        )
        for suffix, other in clearance_pairs:
            _, _, volume = intersection_metrics(
                tightened,
                other,
                f"tightened_bracket_{index + 1}_{suffix}",
            )
            print(
                f"TIGHTENED_CLEARANCE bracket_{index + 1}_{suffix}: "
                f"volume={volume:.9f}"
            )
            if volume > ASSEMBLY_INTERSECTION_VOLUME_TOLERANCE:
                bpy.data.objects.remove(tightened, do_unlink=True)
                raise RuntimeError(
                    f"Tightened bracket {index + 1} overlaps {suffix}"
                )
        bpy.data.objects.remove(tightened, do_unlink=True)
    tightened_first = duplicate_object(
        camera_brackets[0],
        "Tightened_Bracket_1_Pair_Check",
    )
    tightened_second = duplicate_object(
        camera_brackets[1],
        "Tightened_Bracket_2_Pair_Check",
    )
    tightened_first.location.z -= travel
    tightened_second.location.z -= travel
    bpy.context.view_layer.update()
    _, _, pair_volume = intersection_metrics(
        tightened_first,
        tightened_second,
        "tightened_bracket_1_bracket_2",
    )
    print(
        "TIGHTENED_CLEARANCE bracket_1_bracket_2: "
        f"volume={pair_volume:.9f}"
    )
    bpy.data.objects.remove(tightened_first, do_unlink=True)
    bpy.data.objects.remove(tightened_second, do_unlink=True)
    if pair_volume > ASSEMBLY_INTERSECTION_VOLUME_TOLERANCE:
        raise RuntimeError("Tightened camera brackets intersect each other")
    print("TIGHTENED_BRACKET_CLEARANCE PASS")


def validate_camera_bracket_containment(camera_brackets, footprint):
    """Require complete brackets, not just their posts, to stay in the cavity."""
    for bracket in camera_brackets:
        for vertex in bracket.data.vertices:
            point = bracket.matrix_world @ vertex.co
            inner_loop = inset_footprint_loop(
                scale_loop(footprint, body_scale_at_z(point.z)),
                BODY_WALL_THICKNESS,
            )
            xy = (point.x, point.y)
            if (
                not point_in_polygon(xy, inner_loop)
                or polygon_boundary_distance(xy, inner_loop)
                < CAMERA_BRACKET_WALL_CLEARANCE
            ):
                raise RuntimeError(
                    f"{bracket.name} violates configured cavity-wall clearance"
                )
    print("CAMERA_BRACKET_CONTAINMENT PASS")


def output_directory() -> Path:
    if EXPORT_DIRECTORY:
        directory = Path(EXPORT_DIRECTORY).expanduser().resolve()
    else:
        # Use the invocation directory so symlinked generators still place
        # outputs beside the source/reference STL the user is working from.
        directory = Path.cwd().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def export_stl(path: Path, objects) -> Path:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(filepath=str(path), export_selected_objects=True)
    else:
        bpy.ops.export_mesh.stl(filepath=str(path), use_selection=True)
    print(f"EXPORTED {path}")
    return path


def export_single_stl(path: Path, obj, print_face_down=False) -> Path:
    if not NORMALIZE_SEPARATE_STLS:
        return export_stl(path, [obj])
    original_matrix = obj.matrix_world.copy()
    if PRINT_ORIENT_SEPARATE_STLS and print_face_down:
        obj.matrix_world = Matrix.Rotation(math.pi, 4, "X") @ original_matrix
        bpy.context.view_layer.update()
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    center_x = (min(point.x for point in corners) + max(point.x for point in corners)) / 2.0
    center_y = (min(point.y for point in corners) + max(point.y for point in corners)) / 2.0
    minimum_z = min(point.z for point in corners)
    obj.location += Vector((-center_x, -center_y, -minimum_z))
    result = export_stl(path, [obj])
    obj.matrix_world = original_matrix
    bpy.context.view_layer.update()
    return result


def render_preview(base, lid, camera_mockups) -> None:
    if not RENDER_PREVIEW:
        return
    if PREVIEW_EXPLODED:
        lid.location.z += PREVIEW_LID_LIFT
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "paint.sl"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "WORLD"
    scene.display.shading.curvature_ridge_factor = 1.5
    scene.display.shading.curvature_valley_factor = 1.2
    scene.world.color = (0.025, 0.025, 0.025)

    preview_objects = [
        obj
        for obj in scene.objects
        if obj.type == "MESH" and not obj.hide_render
    ]
    preview_points = [
        obj.matrix_world @ Vector(corner)
        for obj in preview_objects
        for corner in obj.bound_box
    ]
    bounds = tuple(
        (
            min(point[axis] for point in preview_points),
            max(point[axis] for point in preview_points),
        )
        for axis in range(3)
    )
    target = Vector(tuple((low + high) / 2.0 for low, high in bounds))
    span_x, span_y, span_z = (high - low for low, high in bounds)
    camera_offset = Vector((-350.0, -330.0, 300.0))
    bpy.ops.object.camera_add(location=target + camera_offset)
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = max(span_x, span_y, span_z * 1.35) * 1.60
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    scene.render.resolution_x = PREVIEW_RESOLUTION_X
    scene.render.resolution_y = PREVIEW_RESOLUTION_Y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    path = Path(PREVIEW_PATH)
    if not path.is_absolute():
        path = Path.cwd().resolve() / path
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED {path}")


def apply_final_visibility(
    base,
    lid,
    camera_brackets,
    camera_carrier=None,
    camera_worm=None,
) -> None:
    base.hide_set(not SHOW_MAIN_BODY_AFTER_BUILD)
    base.hide_render = not SHOW_MAIN_BODY_AFTER_BUILD
    lid.hide_set(not SHOW_TOP_AFTER_BUILD)
    lid.hide_render = not SHOW_TOP_AFTER_BUILD
    for bracket in camera_brackets:
        bracket.hide_set(not SHOW_CAMERA_BRACKETS_AFTER_BUILD)
        bracket.hide_render = not SHOW_CAMERA_BRACKETS_AFTER_BUILD
    if camera_carrier is not None:
        camera_carrier.hide_set(not SHOW_CAMERA_CARTRIDGE_AFTER_BUILD)
        camera_carrier.hide_render = not SHOW_CAMERA_CARTRIDGE_AFTER_BUILD
    if camera_worm is not None:
        camera_worm.hide_set(not SHOW_PURCHASED_WORM_REFERENCE_AFTER_BUILD)
        camera_worm.hide_render = not SHOW_PURCHASED_WORM_REFERENCE_AFTER_BUILD
    print(
        "FINAL_VISIBILITY "
        f"main_body={SHOW_MAIN_BODY_AFTER_BUILD} top={SHOW_TOP_AFTER_BUILD}"
        f" camera_brackets={SHOW_CAMERA_BRACKETS_AFTER_BUILD}"
        f" camera_cartridge={SHOW_CAMERA_CARTRIDGE_AFTER_BUILD}"
        f" worm_reference={SHOW_PURCHASED_WORM_REFERENCE_AFTER_BUILD}"
    )


def apply_adjustable_preview_pose(camera_carrier, camera_worm, mechanism):
    """Pose generated moving parts after validation/export for Blender view."""
    if (
        camera_carrier is None
        or camera_worm is None
        or mechanism is None
        or abs(ADJUSTABLE_CAMERA_PREVIEW_YAW_DEG) <= 1e-9
    ):
        return
    yaw_delta = ADJUSTABLE_CAMERA_PREVIEW_YAW_DEG
    pivot = mechanism["pivot"]
    rotate_mesh_about_world_axis(
        camera_carrier,
        (pivot.x, pivot.y, 0.0),
        (0.0, 0.0, 1.0),
        yaw_delta,
    )
    worm_rotation_deg = adjustable_worm_rotation_degrees(
        mechanism,
        yaw_delta,
    )
    worm_axis_origin = (
        mechanism["worm_center"].x,
        mechanism["worm_center"].y,
        BOTTOM_THICKNESS
        + CAMERA_WORM_FLOOR_CLEARANCE
        + camera_worm_outer_radius(),
    )
    rotate_mesh_about_world_axis(
        camera_worm,
        worm_axis_origin,
        mechanism["shaft_direction"],
        worm_rotation_deg,
    )
    print(
        "ADJUSTABLE_PREVIEW_POSE "
        f"camera_yaw={yaw_delta:+.2f} worm_rotation={worm_rotation_deg:+.2f}"
    )


def build_original_style_cover():
    global _RESOLVED_CAMERA_LENS_FACE_OUTSET
    _RESOLVED_CAMERA_LENS_FACE_OUTSET = None
    validate_config()
    if CLEAR_SCENE:
        clear_scene()
    set_units()
    cameras, footprint = resolve_camera_layout()
    bracket_shell_expansion = (
        CAMERA_BRACKET_SHELL_EXPANSION_WITH_CARTRIDGE
        if CAMERA_CARTRIDGE_WORM_ENABLED
        else CAMERA_BRACKET_SHELL_EXPANSION
    )
    if (
        CAMERA_BRACKETS_ENABLED
        and CAMERA_BRACKET_L_CORNER_GUIDES_ENABLED
        and bracket_shell_expansion > 0.0
    ):
        footprint = radially_expand_loop(
            footprint,
            bracket_shell_expansion,
        )
        print(
            "CAMERA_BRACKET_SHELL_EXPANSION "
            f"radial={bracket_shell_expansion:.2f} "
            f"cartridge_enabled={CAMERA_CARTRIDGE_WORM_ENABLED}"
        )
    if (
        CAMERA_CARTRIDGE_WORM_ENABLED
        and CAMERA_CARTRIDGE_SHELL_EXPANSION > 0.0
    ):
        footprint = radially_expand_loop(
            footprint,
            CAMERA_CARTRIDGE_SHELL_EXPANSION,
        )
        print(
            "CAMERA_CARTRIDGE_SHELL_EXPANSION "
            f"radial={CAMERA_CARTRIDGE_SHELL_EXPANSION:.2f}"
        )
    refresh_camera_eye_recesses(cameras, footprint)
    validate_camera_lens_protrusion(cameras)
    mechanism = adjustable_mechanism_layout(cameras, footprint)
    positions = resolve_fastener_post_positions(cameras, footprint, mechanism)
    bracket_position_pairs = resolve_camera_bracket_post_positions(
        cameras,
        footprint,
        positions,
        mechanism,
    )
    bottom_mount_hole_position = resolve_bottom_mount_hole_position(
        cameras,
        footprint,
        positions,
        bracket_position_pairs,
    )
    bottom_keystone_positions = resolve_bottom_keystone_positions(
        cameras,
        footprint,
        positions,
        bracket_position_pairs,
        bottom_mount_hole_position,
    )
    base = create_base(
        positions,
        cameras,
        footprint,
        bracket_position_pairs,
        bottom_mount_hole_position,
        bottom_keystone_positions,
    )
    lid = create_lid(positions, footprint, cameras)
    camera_brackets = create_camera_brackets(cameras, bracket_position_pairs)
    camera_carrier = None
    camera_worm = None
    moving_camera = adjustable_camera(cameras)
    if moving_camera is not None:
        camera_carrier = create_rotating_camera_carrier(
            moving_camera,
            mechanism,
        )
        camera_worm = create_camera_worm(mechanism)
    validate_camera_bracket_containment(camera_brackets, footprint)
    assign_material(base, "Veo_Base_Material", COVER_COLOR)
    assign_material(lid, "Veo_Lid_Material", LID_COLOR)
    for bracket in camera_brackets:
        assign_material(
            bracket,
            "Camera_Bracket_Material",
            CAMERA_BRACKET_COLOR,
        )
    if camera_carrier is not None:
        assign_material(
            camera_carrier,
            "Camera_Cartridge_Material",
            CAMERA_CARRIER_COLOR,
        )
    if camera_worm is not None:
        assign_material(
            camera_worm,
            "Camera_Worm_Material",
            CAMERA_WORM_COLOR,
        )
    if TRIANGULATE_BASE_IN_SCENE:
        triangulate_mesh(base)
    else:
        print("BASE_TRIANGULATION deferred_to_STL_exporter")
    triangulate_mesh(lid)
    for bracket in camera_brackets:
        triangulate_mesh(bracket)
    for moving_part in (camera_carrier, camera_worm):
        if moving_part is not None:
            triangulate_mesh(moving_part)
    camera_mockups = create_camera_mockups(
        cameras,
        force=(
            VALIDATE_ASSEMBLY_CLEARANCES
            or VALIDATE_CAMERA_USB_ACCESS
            or VALIDATE_CAMERA_INSTALLATION_PATH
            or VALIDATE_REAR_FAN_BODY_CLEARANCE
        ),
    )
    validate_object(base)
    validate_object(lid)
    for bracket in camera_brackets:
        validate_object(bracket)
    for moving_part in (camera_carrier, camera_worm):
        if moving_part is not None:
            validate_object(moving_part)
    validate_adjustable_camera_range(
        cameras,
        footprint,
        base,
        camera_carrier,
        camera_worm,
        camera_mockups,
        camera_brackets,
    )
    validate_assembly_clearances(base, lid, camera_brackets, camera_mockups)
    validate_adjustable_carrier_installation_path(
        base,
        camera_carrier,
        cameras,
    )
    validate_camera_installation_paths(
        base,
        camera_mockups,
        cameras,
        camera_carrier,
    )
    validate_camera_usb_access_clearances(
        base,
        camera_brackets,
        camera_mockups,
        cameras,
        camera_carrier,
    )
    validate_rear_fan_body_clearances(
        footprint,
        cameras,
        camera_mockups,
        camera_brackets,
        camera_carrier,
        camera_worm,
    )
    if EXPORT_STL:
        directory = output_directory()
        if EXPORT_SEPARATE_STLS:
            export_single_stl(directory / BASE_STL_NAME, base)
            export_single_stl(
                directory / LID_STL_NAME,
                lid,
                print_face_down=True,
            )
            if EXPORT_CAMERA_BRACKET_STLS and len(camera_brackets) == 2:
                export_single_stl(
                    directory / CAMERA_BRACKET_1_STL_NAME,
                    camera_brackets[0],
                    print_face_down=True,
                )
                export_single_stl(
                    directory / CAMERA_BRACKET_2_STL_NAME,
                    camera_brackets[1],
                    print_face_down=True,
                )
            if camera_carrier is not None:
                export_single_stl(
                    directory / CAMERA_CARRIER_STL_NAME,
                    camera_carrier,
                )
            if (
                camera_worm is not None
                and EXPORT_PURCHASED_WORM_REFERENCE_STL
            ):
                export_single_stl(
                    directory / CAMERA_WORM_STL_NAME,
                    camera_worm,
                )
        if EXPORT_COMBINED_STL:
            export_stl(
                directory / ASSEMBLY_STL_NAME,
                [
                    base,
                    lid,
                    *camera_brackets,
                    *(
                        [camera_carrier]
                        if camera_carrier is not None
                        else []
                    ),
                    *(
                        [camera_worm]
                        if (
                            camera_worm is not None
                            and EXPORT_PURCHASED_WORM_REFERENCE_STL
                        )
                        else []
                    ),
                ],
            )
    apply_adjustable_preview_pose(camera_carrier, camera_worm, mechanism)
    if not PREVIEW_SHOW_CAMERA_MOCKUPS:
        for mockup in camera_mockups:
            bpy.data.objects.remove(mockup, do_unlink=True)
        camera_mockups = []
    render_preview(base, lid, camera_mockups)
    apply_final_visibility(
        base,
        lid,
        camera_brackets,
        camera_carrier,
        camera_worm,
    )
    return base, lid


if __name__ == "__main__":
    build_original_style_cover()
