"""Clean parametric GoPro fan case and removable accessories for Blender.

Run inside Blender:

    blender --background --python gopro_fan_case_parametric_blender.py

All dimensions are millimeters. The defaults follow ``gopro-fan-case.stl``
without reproducing its internal scraps or jagged hole edges. The generated
objects include the rear shell, removable insert, captive buttons, selected
front retainer, and—when enabled—the acoustic tray and keyed lid. Rigid
cartridges add a groove-located TPU gasket; TPU cartridges carry the same seal
as an integral rear bead. Every exported printable object is validated as an
independent manifold shell.

Axes:
    X - case width
    Y - case depth and insertion direction
    Z - case height
"""

from __future__ import annotations

import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


# ---------------------------------------------------------------------------
# CONFIG

CLEAR_SCENE = True
LAYOUT_MODE = "assembled"  # "assembled" or "print_bed"
PRINT_BED_GAP = 12.0

# Select each printed assembly piece independently.  The back shell includes
# the dome and carries the captured hex hardware; its TPU profile uses deeper
# snap tabs.  The sleeve has no material-specific dimensions yet, while the
# retainer profile resolves thicker TPU gate/keeper geometry.  The two captive
# press-through buttons remain TPU-only.
BACK_MATERIAL_MODE = "TPU"  # "RIGID" or "TPU"
SLEEVE_MATERIAL_MODE = "RIGID"  # "RIGID" or "TPU"
RETAINER_MATERIAL_MODE = "RIGID"  # "RIGID" or "TPU"
BAFFLE_CARTRIDGE_MATERIAL_MODE = "TPU"  # "RIGID" or "TPU"

# Post-build viewport/render visibility. Geometry is still built, validated,
# and exported when hidden, making it easy to inspect either part by itself.
SHOW_BACK_SHELL = True
SHOW_HOLLOW_INSERT = True
SHOW_BUTTONS = True
SHOW_FRONT_RETAINER = True
SHOW_BAFFLE_CARTRIDGE = True

# The front plate depends on the case fasteners, but remains optional so the
# pre-existing fastener-disabled sleeve configuration can still be built.
RETAINER_ENABLED = True
# Select the assembled camera-retention mechanism.  Both printable options are
# exported: SWING_GATE rides on all three M3 shafts and stays captive on the
# upper-right shaft; ROTATING_KEEPERS puts one indexed 180-degree cam under
# each existing thumbnut.
RETAINER_STYLE = "SWING_GATE"  # "SWING_GATE" or "ROTATING_KEEPERS"

EXPORT_STL = False
EXPORT_DIRECTORY = ""
EXPORT_COMBINED_STL = True
EXPORT_SEPARATE_STLS = True
COMBINED_STL_NAME = "gopro_fan_case_parametric.stl"
BACK_STL_NAME = "gopro_fan_case_back.stl"
INSERT_STL_NAME = "gopro_fan_case_insert.stl"
BUTTON_STL_NAME = "gopro_fan_case_button.stl"
RETAINER_STL_NAME = "gopro_fan_case_front_retainer.stl"
RETAINER_KEEPER_STL_NAME = "gopro_fan_case_rotating_keeper.stl"
BAFFLE_TRAY_STL_NAME = "gopro_fan_case_baffle_tray.stl"
BAFFLE_LID_STL_NAME = "gopro_fan_case_baffle_lid.stl"
BAFFLE_GASKET_STL_NAME = "gopro_fan_case_baffle_gasket.stl"

# Mesh and boolean quality.
CYLINDER_SEGMENTS = 96
CORNER_SEGMENTS = 12
INSERT_DEPTH_SECTIONS = 8
BOOLEAN_SOLVER = "EXACT"
# Blender 5.2's EXACT solver can leave open edge fans at the small retention,
# stop, and fan-boss unions.  Use MANIFOLD only for those closed-solid unions;
# older Blender versions fall back to EXACT after enum inspection.
WATERTIGHT_DETAIL_UNION_SOLVER = "MANIFOLD"
BOOLEAN_OVERLAP = 0.08
BOOLEAN_CLEANUP_DISTANCE = 0.0001
BOOLEAN_MINIMUM_VOLUME_CHANGE = 1.0e-6

# Rear fan/socket shell. Y=0 is its smooth front surface.
BACK_OUTER_WIDTH = 96.65
BACK_OUTER_HEIGHT = 65.74
BACK_DEPTH = 21.2
BACK_CORNER_RADIUS = 10.0
BACK_FACE_THICKNESS = 3.0

# Optional smooth exterior dome. The central fan pad remains an exact flat
# rectangle at the dome's rearmost Y position. The full-width front rim ends
# just behind the camera stops so adjacent cases have more swivel clearance.
BACK_DOME_ENABLED = True
BACK_DOME_DEPTH = 10.0
BACK_DOME_START_BEHIND_CAMERA_STOPS = 0.5
# Keep the three narrow screw chimneys at the former rear-face plane so the
# existing hex seats, retention tabs, and screw lengths remain unchanged.
BACK_DOME_FASTENER_CHIMNEY_REAR_Y = 0.0
BACK_DOME_FAN_PAD_WIDTH = 45.0
BACK_DOME_FAN_PAD_HEIGHT = 45.0
BACK_DOME_SECTIONS = 12
BACK_DOME_LOOP_POINTS = 128

# Mating socket. The insert dimensions below plus these values determine fit.
FIT_CLEARANCE_X = 0.30
FIT_CLEARANCE_Z = 0.30
INSERTION_DEPTH = 3.4

# Continuous sleeve-capture groove at the existing screw-boss assembly datum.
# The ordinary INSERTION_DEPTH remains unchanged.  Only the sleeve wall extends
# forward by the engagement depth; the insert and back-shell screw bosses still
# meet at INSERTION_DEPTH's original plane.  Clearance is applied independently
# from the structural inner lip and the material left outside the groove.
SLEEVE_CAPTURE_SLOT_ENABLED = True
SLEEVE_CAPTURE_ENGAGEMENT_DEPTH = 0.80
# SLEEVE_CAPTURE_FIT_CLEARANCE = 0.25
SLEEVE_CAPTURE_FIT_CLEARANCE = 0.20
SLEEVE_CAPTURE_INNER_LIP_THICKNESS = 1.20
SLEEVE_CAPTURE_BOTTOM_CLEARANCE = 0.15
SLEEVE_CAPTURE_FLOOR_THICKNESS = 0.50
SLEEVE_CAPTURE_MIN_OUTER_WALL_X = 1.50
SLEEVE_CAPTURE_MIN_OUTER_WALL_Z = 1.20

# Smooth fan opening and screw pattern on the rear shell.
FAN_OPENING_ENABLED = True
FAN_CENTER_X = -4.0
FAN_CENTER_Z = 0.0
FAN_OPENING_DIAMETER = 37.0
FAN_HOLE_SPACING_X = 32.0
FAN_HOLE_SPACING_Z = 32.0
FAN_HOLE_DIAMETER = 3.6
FAN_HOLE_BOSSES_ENABLED = True
FAN_HOLE_BOSS_DIAMETER = 7.0
FAN_HOLE_BOSS_HEIGHT = 1.0

# Optional removable Offset-S acoustic cartridge.  It occupies only the
# existing domed rear cavity: a sealed inlet gasket feeds two alternating
# full-width baffles, whose projected edges overlap to remove every straight
# fan-to-camera sound path. The cartridge is a side-open tray plus a separately
# printed keyed lid; it avoids bulk internal supports but retains one controlled
# bridge across the existing-camera-stop relief. A groove-located TPU gasket,
# or an integral bead when the tray itself is TPU, seals the circular inlet.
# Two compliant top/bottom tongues engage shallow receiver ribs added to the
# back shell without changing its exterior envelope.
BAFFLE_CARTRIDGE_ENABLED = True
BAFFLE_REAR_Y = -5.20
BAFFLE_FRONT_Y = 14.00
BAFFLE_REAR_WIDTH = 44.0
BAFFLE_FRONT_WIDTH = 70.0
BAFFLE_BODY_HEIGHT = 44.0
BAFFLE_BODY_DEPTH_SECTIONS = 8
BAFFLE_STOP_CLEARANCE = 0.80
# These four dimensions are selected by BAFFLE_CARTRIDGE_MATERIAL_PROFILES.
BAFFLE_WALL_THICKNESS = 1.60
BAFFLE_INTERNAL_THICKNESS_Y = 1.80
BAFFLE_LID_PLATE_THICKNESS_X = 1.20
BAFFLE_SNAP_TONGUE_THICKNESS_Z = 1.00

# Rear inlet stack. Three pointed slots retain most of the fan-circle area
# while keeping every closing roof safely self-supporting in print space. The
# thin separator ribs also stiffen the rear face. A rigid cartridge locates its
# separately printed TPU gasket in a shallow annular rear groove. A continuous
# gasket-shaped floor land backs the seal even where the pointed inlet cutters
# extend beyond the circular bore. With the TPU cartridge profile, the same
# exposed sealing ring is unioned directly to the tray. Four scallops register
# either seal around the fan bosses.
BAFFLE_INLET_DIAMETER = 37.0
BAFFLE_INLET_SLOT_COUNT = 3
BAFFLE_INLET_SEPARATOR_THICKNESS_Z = 2.00
BAFFLE_INLET_ROOF_APEX_X = 21.0
BAFFLE_INLET_ROOF_RUN_X = 12.0
BAFFLE_GASKET_OUTER_DIAMETER = 39.0
BAFFLE_GASKET_INNER_DIAMETER = 37.0
BAFFLE_GASKET_THICKNESS_Y = 2.40
BAFFLE_GASKET_BOSS_CLEARANCE = 0.15
BAFFLE_GASKET_GROOVE_DEPTH_Y = 0.40
BAFFLE_GASKET_GROOVE_RADIAL_CLEARANCE = 0.20

# Alternating baffles and broad forward outlet.  The first blocker leaves top
# and bottom lanes; the second closes those lanes and leaves a center throat.
# One broad pointed outlet avoids the poorly supported thin separator post
# created by a two-slot outlet while retaining a self-supporting closing roof.
BAFFLE_FIRST_Y = 4.70
BAFFLE_FIRST_BLOCKER_HEIGHT_Z = 22.0
BAFFLE_SECOND_Y = 9.60
BAFFLE_SECOND_OPENING_HEIGHT_Z = 16.0
BAFFLE_MIN_EDGE_OVERLAP_Z = 2.0
BAFFLE_MIN_THROAT_AREA = 870.0
BAFFLE_OUTLET_WIDTH = 52.0
BAFFLE_OUTLET_HEIGHT = 19.7
BAFFLE_OUTLET_SLOT_COUNT = 1
BAFFLE_OUTLET_SEPARATOR_THICKNESS_Z = 2.00
BAFFLE_OUTLET_ROOF_RUN_X = 15.0
BAFFLE_MIN_ROOF_ANGLE_DEG = 60.0
BAFFLE_OUTLET_MIN_FRONT_WALL_SIDE_BAND_X = 3.00

# The +X side lid replaces the removed side wall.  Its broad outer plate sits
# flush with the tray while a shallow inner key locates it for bonding after
# the airway is inspected and cleaned.  Robust tray-side returns tie both
# camera-side members into the perimeter for more than 3 mm before the lid
# edge. Two shallow lid pockets capture those returns while leaving the lid's
# center key continuous and avoiding a TPU bridge across the airway. TPU also
# receives a shallow groove for the first center blocker.
BAFFLE_LID_KEY_DEPTH_X = 1.80
BAFFLE_LID_FIT_CLEARANCE = 0.25
BAFFLE_TPU_LID_BLOCKER_SLOT_DEPTH_X = 0.60
BAFFLE_TPU_LID_BLOCKER_SLOT_ENGAGEMENT_X = 0.35
BAFFLE_TPU_LID_BLOCKER_SLOT_CLEARANCE_Y = 0.20
BAFFLE_TPU_LID_BLOCKER_SLOT_CLEARANCE_Z = 0.25
BAFFLE_SECOND_END_FRAME_DEPTH_Y = 3.20
BAFFLE_SECOND_END_FRAME_REAR_SHIFT_Y = 0.40
BAFFLE_SECOND_END_FRAME_CONNECTION_X = 3.50
BAFFLE_SECOND_END_FRAME_LID_ENGAGEMENT_X = 0.80
BAFFLE_SECOND_END_FRAME_LID_POCKET_DEPTH_X = 1.00
BAFFLE_SECOND_END_FRAME_LID_CLEARANCE_Y = 0.20
BAFFLE_SECOND_END_FRAME_LID_CLEARANCE_Z = 0.20
BAFFLE_SECOND_END_FRAME_LID_MIN_WALL = 0.70

# Top/bottom cartridge retention. Each long tongue is carried at the tray's
# centerline, clear of the existing left/right camera stops. The tongues follow
# the dome wall, snap past shallow back-shell receiver ribs, and remain
# accessible from the front after the sleeve is removed. Their hooks seat just
# behind the receiver crests, maintaining gasket preload until deliberately
# flexed toward the cartridge center for removal.
BAFFLE_SNAP_RECEIVER_Y = 12.20
BAFFLE_SNAP_RECEIVER_WIDTH_X = 8.0
BAFFLE_SNAP_RECEIVER_DEPTH_Y = 2.20
BAFFLE_SNAP_RECEIVER_PROJECTION_Z = 1.25
BAFFLE_SNAP_RECEIVER_BEVEL = 0.25
BAFFLE_SNAP_TONGUE_ROOT_Y = 4.00
BAFFLE_SNAP_TONGUE_WIDTH_X = 10.0
BAFFLE_SNAP_TONGUE_WALL_OFFSET = 1.30
BAFFLE_SNAP_ROOT_DEPTH_Y = 1.80
BAFFLE_SNAP_HOOK_PROTRUSION_Z = 0.70
BAFFLE_SNAP_HOOK_SEATED_OFFSET_Y = 1.00
BAFFLE_SNAP_INTERFERENCE_Z = 0.45

# Smooth rectangular vent and diagonal louvers to the fan's right.
VENT_ENABLED = False
VENT_CENTER_X = 27.0
VENT_CENTER_Z = 0.0
VENT_WIDTH = 14.0
VENT_HEIGHT = 38.0
VENT_CORNER_RADIUS = 1.5
VENT_SLAT_COUNT = 12
VENT_SLAT_WIDTH = 1.0
VENT_SLAT_ANGLE_DEG = 42.0

# Three perimeter fasteners shared by both parts, as (X, Z) positions.
CASE_FASTENERS_ENABLED = True
CASE_FASTENER_POSITIONS_XZ = (
    (-31.0, -28.4),
    (30.0, -28.4),
    (31.0, 28.5),
)
BACK_FASTENER_HOLE_DIAMETER = 4.0
BACK_FASTENER_BOSS_DIAMETER = 8.0
# Minimum sampled common bearing area between each back/insert boss pair at
# the assembly datum after the perimeter groove removes its required sector.
BACK_FASTENER_MIN_DATUM_CONTACT_AREA = 15.0
# Axial gap between the rear tube end and the insert-boss socket boundary.
# Its distance behind the open rim is INSERTION_DEPTH plus this value.
BACK_FASTENER_TO_INSERT_SOCKET_GAP = 0.0
INSERT_FASTENER_HOLE_DIAMETER = 3.4
INSERT_FASTENER_BOSS_DIAMETER = 7.0
FASTENER_BOSS_SOCKET_CLEARANCE = 0.25

# Original-style M3 hex-head recesses in the rear perimeter fasteners.
# The seat-to-insert distance preserves the original screw reach.
BACK_FASTENER_HEX_RETENTION_ENABLED = True
BACK_FASTENER_HEX_WIDTH_X = 6.61
BACK_FASTENER_HEX_HEIGHT_Z = 5.70
BACK_FASTENER_HEX_SEAT_TO_INSERT = 6.2076
BACK_FASTENER_HEX_TRANSITION_DEPTH = 0.358
# Nominal M3 hex-nut/head thickness used to place the retaining tabs against
# the installed part's rear face.  Measure the actual hardware before tuning.
BACK_FASTENER_HEX_PART_THICKNESS_Y = 2.40
BACK_FASTENER_RETENTION_TABS_ENABLED = True
BACK_FASTENER_RETENTION_TAB_WIDTH_X = 1.0
BACK_FASTENER_RETENTION_TAB_DEPTH_Y = 2.0
# These two dimensions are selected by BACK_MATERIAL_PROFILES below.
BACK_FASTENER_RETENTION_TAB_PROTRUSION = 0.30
BACK_FASTENER_RETENTION_TAB_OFFSET_FROM_SEAT = 3.30
BACK_FASTENER_RETENTION_TAB_BEVEL = 0.12

# Six rear-shell stops prevent the camera sliding past the insert frame.
CAMERA_STOPS_ENABLED = True
# Fan clearance can include an extra radial gap. With case-boss clearance
# disabled, only a 0.001 mm solver allowance exposes the tube boundary without
# recreating the earlier visible annular gap around it.
CAMERA_STOP_CLEAR_FAN_BOSSES = True
CAMERA_STOP_CLEAR_CASE_BOSSES = False
CAMERA_STOP_FASTENER_CLEARANCE = 0.35
# All six stops share this gap to the insert-boss socket boundary. Keep it
# equal to BACK_FASTENER_TO_INSERT_SOCKET_GAP for flush end faces.
CAMERA_STOP_TO_INSERT_SOCKET_GAP = 0.0
# Each entry is:
# (name, x_min, x_max, z_min, z_max, attachment)
# The X/Z bounds are the original STL's camera-facing rectangular
# protrusions, localized around the rebuilt rear shell's center. Every stop
# starts inside the rear wall so none can float above the interior surface.
CAMERA_STOP_SPECS = (
    (
        "Top_Left",
        -22.17404,
        -18.91444,
        22.89582,
        28.89912,
        "top",
    ),
    (
        "Top_Right",
        19.46286,
        22.72356,
        22.89312,
        28.89002,
        "top",
    ),
    (
        "Bottom_Right",
        19.02846,
        22.28786,
        -28.95938,
        -22.96408,
        "bottom",
    ),
    (
        "Left_Side",
        -44.18734,
        -37.66224,
        10.89562,
        13.88582,
        "left",
    ),
    (
        "Right_Side",
        35.81276,
        42.34596,
        -1.95428,
        1.03572,
        "right",
    ),
    (
        "Bottom_Left_Large",
        -41.62234,
        -20.76764,
        -28.95648,
        -12.79718,
        "bottom",
    ),
)

# Open insert frame. Its front sits inside the rear shell when assembled.
INSERT_FRONT_WIDTH = 90.55
INSERT_FRONT_HEIGHT = 61.45
INSERT_REAR_WIDTH = 90.55

# Keep front/rear equal for straight walls; change either value to add taper.
INSERT_REAR_HEIGHT = 61.45
INSERT_DEPTH = 26.5
INSERT_OUTER_CORNER_RADIUS = 8.0
INSERT_WALL_X = 2.0
INSERT_WALL_Z = 1.8

# Large opening through the insert's bottom wall.
BOTTOM_ACCESS_ENABLED = True
BOTTOM_ACCESS_WIDTH = 50.0
#BOTTOM_ACCESS_DEPTH = 20.0
#BOTTOM_ACCESS_Y_OFFSET = 3.5
BOTTOM_ACCESS_DEPTH = 20.5
BOTTOM_ACCESS_Y_OFFSET = 3.0

# The original has different openings on its two side walls.
LEFT_ROUND_PORT_ENABLED = True
LEFT_ROUND_PORT_DIAMETER = 6.1875
# LEFT_ROUND_PORT_Y_OFFSET = 14.3367
LEFT_ROUND_PORT_Y_OFFSET = 13.5867
LEFT_ROUND_PORT_Z = -1.4828

# USB opening through only the positive-X side wall.
RIGHT_USB_PORT_ENABLED = True
RIGHT_USB_PORT_WIDTH_Y = 13.1998
RIGHT_USB_PORT_HEIGHT_Z = 7.2
RIGHT_USB_PORT_CORNER_RADIUS = 3.6
#RIGHT_USB_PORT_Y_OFFSET = 13.8894
RIGHT_USB_PORT_Y_OFFSET = 13.6894
RIGHT_USB_PORT_Z = -17.9001

# Optional circular port through only the top wall.
TOP_PORT_ENABLED = True
TOP_PORT_DIAMETER = 6.1875
TOP_PORT_X = 18.0
TOP_PORT_Y_OFFSET = 14.3367

# Two identical captive TPU actuators fit the left and top circular ports.
# Install each one from inside the sleeve, tapered end first.  The exterior
# bead compresses through the port and springs back to keep the loose button
# with the sleeve when the camera is removed.  Print two copies in TPU,
# independently of the back, sleeve, and retainer material selections.
BUTTON_STEM_DIAMETER = 5.75
BUTTON_TOTAL_HEIGHT = 6.83
BUTTON_INNER_FLANGE_THICKNESS = 0.75
BUTTON_INNER_FLANGE_DIAMETER = 8.0
#BUTTON_RETENTION_RIM_DIAMETER = 6.60
#BUTTON_RETENTION_RIM_HEIGHT = 0.85
BUTTON_RETENTION_RIM_DIAMETER = 6.70
BUTTON_RETENTION_RIM_HEIGHT = 0.95
BUTTON_RETENTION_SHOULDER_HEIGHT = 0.10
BUTTON_RETENTION_LEAD_IN_HEIGHT = 0.55

# Captive swing-away front gate.  It rides directly on the three existing M3
# bolt shafts, behind the ordinary thumbnuts.  The upper-right bolt is its
# closed pivot; curved tracks clear the two lower bolts during the first part
# of the swing.  Loosen all three thumbnuts slightly, swing the gate without
# removing any hardware, then close it and retighten the clamp nuts.
RETAINER_GATE_RIGID_THICKNESS_Y = 2.5
RETAINER_GATE_TPU_THICKNESS_Y = 4.0
RETAINER_HORIZONTAL_END_MARGIN_X = 8.0
RETAINER_HORIZONTAL_BAR_HEIGHT_Z = 13.15
RETAINER_LOWER_EDGE_MARGIN_Z = 4.20
RETAINER_UPRIGHT_WIDTH_X = 10.0
RETAINER_TOP_EDGE_MARGIN_Z = 4.10
RETAINER_CORNER_RADIUS = 3.0
RETAINER_RELIEF_CENTER_X = -3.0
RETAINER_RELIEF_CENTER_Z = 27.75
RETAINER_RELIEF_RADIUS = 54.75
RETAINER_MIN_HOLE_WEB = 2.0

# M3 running fit and the curved lower-bolt release tracks.  A 7 mm washer (or
# a thumbnut with at least that bearing diameter) spreads clamp load over the
# locally slotted gate.
RETAINER_GATE_BOLT_TRACK_DIAMETER = 3.6
RETAINER_GATE_MIN_NUT_BEARING_DIAMETER = 7.0
RETAINER_GATE_LOWER_LEFT_RELEASE_ANGLE_DEG = 11.0
RETAINER_GATE_LOWER_RIGHT_RELEASE_ANGLE_DEG = 22.0
RETAINER_GATE_SWEEP_STEP_DEG = 2.0

# Three alternate 180-degree keeper cams use the same M3 bolt shafts and
# ordinary thumbnuts.  In the closed position their rounded lobes overlap the
# camera envelope.  Turned outward, their circular hubs stay behind the
# sleeve's camera-support runners so the camera can slide past.  TPU receives
# extra Y thickness because clamp load can otherwise curl the flexible lobe.
RETAINER_KEEPER_BOLT_HOLE_DIAMETER = 3.6
RETAINER_KEEPER_HUB_DIAMETER = 5.9
RETAINER_KEEPER_MIN_HOLE_WEB = 1.0
RETAINER_KEEPER_LOBE_WIDTH_X = 5.9
RETAINER_KEEPER_CLOSED_PROJECTION_Z = 9.0
RETAINER_KEEPER_RIGID_THICKNESS_Y = 3.0
RETAINER_KEEPER_TPU_THICKNESS_Y = 4.5

# Two shallow slots on the keeper's sleeve-facing side engage two matching
# keys on each insert fastener boss.  The diametrically opposed keys index both
# the closed and 180-degree-open positions.  Loosen and lift the keeper by the
# recess depth before turning it; the thumbnut remains on the M3 shaft.
RETAINER_KEEPER_INDEX_ENABLED = True
RETAINER_KEEPER_INDEX_RADIAL_OFFSET = 2.40
RETAINER_KEEPER_INDEX_KEY_WIDTH_X = 1.50
RETAINER_KEEPER_INDEX_KEY_HEIGHT_Z = 0.45
RETAINER_KEEPER_INDEX_KEY_PROJECTION_Y = 0.40
RETAINER_KEEPER_INDEX_FIT_CLEARANCE = 0.10
RETAINER_KEEPER_INDEX_RECESS_DEPTH_Y = 0.55
RETAINER_KEEPER_INDEX_KEY_BEVEL = 0.08

# Six internal rails that position the camera inside the insert frame.
LOCATING_TABS_ENABLED = True
# Each entry is (name, x_min, x_max, z_min, z_max, attachment). These are
# the exact inner-contour bounds measured from the original insert STL and
# localized around the insert's front outer profile.
LOCATING_TAB_SPECS = (
    ("Top_Left", -25.06990, -21.79990, 25.12495, 28.84125, "top"),
    ("Top_Right", 27.56750, 30.83750, 25.12495, 28.84125, "top"),
    ("Bottom_Left", -30.19290, -26.92290, -28.92505, -25.12505, "bottom"),
    ("Bottom_Right", 26.05940, 29.32940, -28.92505, -25.12505, "bottom"),
    ("Left_Side", -43.27290, -39.13090, 5.87510, 8.87510, "left"),
    ("Right_Side", 39.13110, 43.27310, 1.49996, 4.49996, "right"),
)

# Lens-clearance lead-ins at the camera-entry end of the insert. Each value
# is (taper_length_y, remaining_front_projection). A zero projection makes
# the guide flush with the inner wall at the open end.
LENS_CLEARANCE_GUIDE_TAPERS = {
    "Top_Left": (6.0, 0.35),
    "Left_Side": (6.0, 0.35),
}
LENS_CLEARANCE_CUTTER_MARGIN = 1.0

# Side snap bumps and matching pockets in the rear shell.
SNAP_ENABLED = True
SNAP_BUMP_PROTRUSION = 0.45
SNAP_BUMP_LENGTH_Y = 2.5
SNAP_BUMP_LENGTH_Z = 8.0
SNAP_BUMP_Y_OFFSET = 1.1
SNAP_POCKET_CLEARANCE = 0.20
SNAP_EDGE_RADIUS = 0.35

# Viewport colors only; STL files do not store these.
BACK_COLOR = (0.10, 0.38, 0.70, 1.0)
INSERT_COLOR = (0.88, 0.26, 0.08, 1.0)
BUTTON_COLOR = (0.12, 0.12, 0.12, 1.0)
RETAINER_COLOR = (0.18, 0.62, 0.30, 1.0)
RETAINER_KEEPER_COLOR = (0.56, 0.24, 0.68, 1.0)
BAFFLE_TRAY_COLOR = (0.93, 0.42, 0.12, 1.0)
BAFFLE_LID_COLOR = (1.00, 0.64, 0.25, 1.0)
BAFFLE_GASKET_COLOR = (0.12, 0.46, 0.24, 1.0)


# Back-shell values controlled by BACK_MATERIAL_MODE.  Keep a complete rigid
# profile so switching modes between builds in one Blender process restores
# rigid values.
_RIGID_BACK_MATERIAL_PROFILE = {
    # A 3.30 mm center offset places the seat-facing side of each 2.00 mm-deep
    # tab 0.10 mm into a nominal 2.40 mm-thick hex part.  The small preload
    # holds the hardware against its final seat instead of allowing axial play.
    "BACK_FASTENER_RETENTION_TAB_OFFSET_FROM_SEAT": 3.30,
    "BACK_FASTENER_RETENTION_TAB_PROTRUSION": 0.30,
}
BACK_MATERIAL_PROFILES = {
    "RIGID": _RIGID_BACK_MATERIAL_PROFILE,
    "TPU": {
        **_RIGID_BACK_MATERIAL_PROFILE,
        # TPU can flex away from the hex part, so add another 0.20 mm of
        # engagement while retaining clearance around the 4.0 mm shaft bore.
        "BACK_FASTENER_RETENTION_TAB_PROTRUSION": 0.50,
    },
}
_APPLIED_BACK_MATERIAL_MODE = None


def apply_back_material_profile() -> None:
    global _APPLIED_BACK_MATERIAL_MODE
    global BACK_FASTENER_RETENTION_TAB_OFFSET_FROM_SEAT
    global BACK_FASTENER_RETENTION_TAB_PROTRUSION

    try:
        profile = BACK_MATERIAL_PROFILES[BACK_MATERIAL_MODE]
    except KeyError as error:
        choices = ", ".join(sorted(BACK_MATERIAL_PROFILES))
        raise ValueError(
            "BACK_MATERIAL_MODE must be one of: "
            f"{choices}; got {BACK_MATERIAL_MODE!r}"
        ) from error

    BACK_FASTENER_RETENTION_TAB_OFFSET_FROM_SEAT = profile[
        "BACK_FASTENER_RETENTION_TAB_OFFSET_FROM_SEAT"
    ]
    BACK_FASTENER_RETENTION_TAB_PROTRUSION = profile[
        "BACK_FASTENER_RETENTION_TAB_PROTRUSION"
    ]
    _APPLIED_BACK_MATERIAL_MODE = BACK_MATERIAL_MODE


def set_back_material_mode(mode: str) -> None:
    """Select the back-shell profile while preserving scalar overrides."""
    global BACK_MATERIAL_MODE
    BACK_MATERIAL_MODE = mode
    apply_back_material_profile()


set_back_material_mode(BACK_MATERIAL_MODE)


_RIGID_BAFFLE_CARTRIDGE_MATERIAL_PROFILE = {
    "BAFFLE_WALL_THICKNESS": 1.60,
    "BAFFLE_INTERNAL_THICKNESS_Y": 1.80,
    "BAFFLE_LID_PLATE_THICKNESS_X": 1.20,
    "BAFFLE_SNAP_TONGUE_THICKNESS_Z": 1.00,
}
BAFFLE_CARTRIDGE_MATERIAL_PROFILES = {
    "RIGID": _RIGID_BAFFLE_CARTRIDGE_MATERIAL_PROFILE,
    "TPU": {
        **_RIGID_BAFFLE_CARTRIDGE_MATERIAL_PROFILE,
        "BAFFLE_WALL_THICKNESS": 2.00,
        "BAFFLE_INTERNAL_THICKNESS_Y": 2.40,
        "BAFFLE_LID_PLATE_THICKNESS_X": 2.00,
        "BAFFLE_SNAP_TONGUE_THICKNESS_Z": 1.60,
    },
}
_APPLIED_BAFFLE_CARTRIDGE_MATERIAL_MODE = None


def apply_baffle_cartridge_material_profile() -> None:
    global _APPLIED_BAFFLE_CARTRIDGE_MATERIAL_MODE
    global BAFFLE_WALL_THICKNESS
    global BAFFLE_INTERNAL_THICKNESS_Y
    global BAFFLE_LID_PLATE_THICKNESS_X
    global BAFFLE_SNAP_TONGUE_THICKNESS_Z

    try:
        profile = BAFFLE_CARTRIDGE_MATERIAL_PROFILES[
            BAFFLE_CARTRIDGE_MATERIAL_MODE
        ]
    except KeyError as error:
        choices = ", ".join(sorted(BAFFLE_CARTRIDGE_MATERIAL_PROFILES))
        raise ValueError(
            "BAFFLE_CARTRIDGE_MATERIAL_MODE must be one of: "
            f"{choices}; got {BAFFLE_CARTRIDGE_MATERIAL_MODE!r}"
        ) from error

    BAFFLE_WALL_THICKNESS = profile["BAFFLE_WALL_THICKNESS"]
    BAFFLE_INTERNAL_THICKNESS_Y = profile[
        "BAFFLE_INTERNAL_THICKNESS_Y"
    ]
    BAFFLE_LID_PLATE_THICKNESS_X = profile[
        "BAFFLE_LID_PLATE_THICKNESS_X"
    ]
    BAFFLE_SNAP_TONGUE_THICKNESS_Z = profile[
        "BAFFLE_SNAP_TONGUE_THICKNESS_Z"
    ]
    _APPLIED_BAFFLE_CARTRIDGE_MATERIAL_MODE = (
        BAFFLE_CARTRIDGE_MATERIAL_MODE
    )


def set_baffle_cartridge_material_mode(mode: str) -> None:
    global BAFFLE_CARTRIDGE_MATERIAL_MODE
    BAFFLE_CARTRIDGE_MATERIAL_MODE = mode
    apply_baffle_cartridge_material_profile()


set_baffle_cartridge_material_mode(BAFFLE_CARTRIDGE_MATERIAL_MODE)


# ---------------------------------------------------------------------------
# Configuration and scene helpers


def insert_start_y() -> float:
    """Assembly datum where the opposing screw-boss faces meet."""
    return BACK_DEPTH - INSERTION_DEPTH


def insert_sleeve_leading_y() -> float:
    engagement = (
        SLEEVE_CAPTURE_ENGAGEMENT_DEPTH
        if SLEEVE_CAPTURE_SLOT_ENABLED
        else 0.0
    )
    return insert_start_y() - engagement


def insert_inner_corner_radius() -> float:
    return INSERT_OUTER_CORNER_RADIUS - max(INSERT_WALL_X, INSERT_WALL_Z)


def resolved_insert_inner_corner_radius() -> float:
    """Mirror the legacy helper's full inner-radius clamp when slot-disabled."""
    radius = insert_inner_corner_radius()
    if SLEEVE_CAPTURE_SLOT_ENABLED:
        return radius
    return min(
        max(radius, 0.5),
        insert_inner_width() / 2.0,
        insert_inner_height() / 2.0,
    )


def sleeve_capture_groove_outer_dimensions():
    clearance = SLEEVE_CAPTURE_FIT_CLEARANCE
    return (
        INSERT_FRONT_WIDTH + 2.0 * clearance,
        INSERT_FRONT_HEIGHT + 2.0 * clearance,
        INSERT_OUTER_CORNER_RADIUS + clearance,
    )


def sleeve_capture_groove_inner_dimensions():
    clearance = SLEEVE_CAPTURE_FIT_CLEARANCE
    return (
        insert_inner_width() - 2.0 * clearance,
        insert_inner_height() - 2.0 * clearance,
        insert_inner_corner_radius() - clearance,
    )


def sleeve_capture_opening_dimensions():
    inner_width, inner_height, inner_radius = (
        sleeve_capture_groove_inner_dimensions()
    )
    lip = SLEEVE_CAPTURE_INNER_LIP_THICKNESS
    return (
        inner_width - 2.0 * lip,
        inner_height - 2.0 * lip,
        inner_radius - lip,
    )


def sleeve_capture_outer_support_dimensions():
    groove_width, groove_height, groove_radius = (
        sleeve_capture_groove_outer_dimensions()
    )
    corner_support = max(
        SLEEVE_CAPTURE_MIN_OUTER_WALL_X,
        SLEEVE_CAPTURE_MIN_OUTER_WALL_Z,
    )
    return (
        groove_width + 2.0 * SLEEVE_CAPTURE_MIN_OUTER_WALL_X,
        groove_height + 2.0 * SLEEVE_CAPTURE_MIN_OUTER_WALL_Z,
        groove_radius + corner_support,
    )


def effective_back_outer_dimensions():
    """Return a shell envelope containing both the legacy and slot contours."""
    if not SLEEVE_CAPTURE_SLOT_ENABLED:
        return BACK_OUTER_WIDTH, BACK_OUTER_HEIGHT, BACK_CORNER_RADIUS

    support_width, support_height, support_radius = (
        sleeve_capture_outer_support_dimensions()
    )
    requested_corner_center = (
        BACK_OUTER_WIDTH / 2.0 - BACK_CORNER_RADIUS,
        BACK_OUTER_HEIGHT / 2.0 - BACK_CORNER_RADIUS,
    )
    support_corner_center = (
        support_width / 2.0 - support_radius,
        support_height / 2.0 - support_radius,
    )
    corner_center_distance = math.hypot(
        requested_corner_center[0] - support_corner_center[0],
        requested_corner_center[1] - support_corner_center[1],
    )
    margin = max(
        0.0,
        (BACK_OUTER_WIDTH - support_width) / 2.0,
        (BACK_OUTER_HEIGHT - support_height) / 2.0,
        BACK_CORNER_RADIUS + corner_center_distance - support_radius,
    )
    return (
        support_width + 2.0 * margin,
        support_height + 2.0 * margin,
        support_radius + margin,
    )


def sleeve_capture_groove_floor_y() -> float:
    return insert_sleeve_leading_y() - SLEEVE_CAPTURE_BOTTOM_CLEARANCE


def sleeve_capture_ledge_start_y() -> float:
    return sleeve_capture_groove_floor_y() - SLEEVE_CAPTURE_FLOOR_THICKNESS


def back_exterior_y() -> float:
    return -BACK_DOME_DEPTH if BACK_DOME_ENABLED else 0.0


def fan_pad_inner_y() -> float:
    return back_exterior_y() + BACK_FACE_THICKNESS


def fan_boss_end_y() -> float:
    return fan_pad_inner_y() + FAN_HOLE_BOSS_HEIGHT


def back_fastener_hex_seat_y() -> float:
    return insert_start_y() - BACK_FASTENER_HEX_SEAT_TO_INSERT


def back_fastener_bore_start_y() -> float:
    return back_fastener_hex_seat_y() + BACK_FASTENER_HEX_TRANSITION_DEPTH


def back_fastener_retention_tab_center_y() -> float:
    return (
        back_fastener_hex_seat_y()
        - BACK_FASTENER_RETENTION_TAB_OFFSET_FROM_SEAT
    )


def back_fastener_retention_axial_preload() -> float:
    """Return tab overlap with a seated nominal hex part along Y."""
    return (
        BACK_FASTENER_HEX_PART_THICKNESS_Y
        + BACK_FASTENER_RETENTION_TAB_DEPTH_Y / 2.0
        - BACK_FASTENER_RETENTION_TAB_OFFSET_FROM_SEAT
    )


def back_fastener_end_y() -> float:
    return insert_start_y() - BACK_FASTENER_TO_INSERT_SOCKET_GAP


def camera_stop_end_y() -> float:
    return insert_start_y() - CAMERA_STOP_TO_INSERT_SOCKET_GAP


def dome_outer_transition_y() -> float:
    return camera_stop_end_y() - BACK_DOME_START_BEHIND_CAMERA_STOPS


def dome_inner_transition_y() -> float:
    return camera_stop_end_y()


def rear_shell_start_y() -> float:
    return dome_outer_transition_y() if BACK_DOME_ENABLED else 0.0


def smoothstep(value: float) -> float:
    value = min(max(value, 0.0), 1.0)
    return value * value * (3.0 - 2.0 * value)


def dome_surface_y_approx(x: float, z: float) -> float:
    if not BACK_DOME_ENABLED:
        return 0.0
    back_width, back_height, _back_radius = effective_back_outer_dimensions()
    x_from_pad = max(abs(x - FAN_CENTER_X) - BACK_DOME_FAN_PAD_WIDTH / 2.0, 0.0)
    z_from_pad = max(abs(z - FAN_CENTER_Z) - BACK_DOME_FAN_PAD_HEIGHT / 2.0, 0.0)
    x_run = max(back_width / 2.0 - BACK_DOME_FAN_PAD_WIDTH / 2.0, 0.001)
    z_run = max(back_height / 2.0 - BACK_DOME_FAN_PAD_HEIGHT / 2.0, 0.001)
    radial_t = max(x_from_pad / x_run, z_from_pad / z_run)
    height_t = smoothstep(radial_t)
    return back_exterior_y() + (
        dome_outer_transition_y() - back_exterior_y()
    ) * height_t


def back_fastener_boss_start_y(x: float, z: float) -> float:
    if BACK_DOME_ENABLED:
        return min(
            dome_surface_y_approx(x, z),
            BACK_DOME_FASTENER_CHIMNEY_REAR_Y,
        )
    return 0.0


def socket_width() -> float:
    return INSERT_FRONT_WIDTH + 2.0 * FIT_CLEARANCE_X


def socket_height() -> float:
    return INSERT_FRONT_HEIGHT + 2.0 * FIT_CLEARANCE_Z


def socket_corner_radius() -> float:
    return max(
        INSERT_OUTER_CORNER_RADIUS + max(FIT_CLEARANCE_X, FIT_CLEARANCE_Z),
        0.5,
    )


def insert_inner_width() -> float:
    return INSERT_FRONT_WIDTH - 2.0 * INSERT_WALL_X


def insert_inner_height() -> float:
    return INSERT_FRONT_HEIGHT - 2.0 * INSERT_WALL_Z


def baffle_depth_fraction(y: float) -> float:
    return (y - BAFFLE_REAR_Y) / (BAFFLE_FRONT_Y - BAFFLE_REAR_Y)


def baffle_body_bounds_at_y(y: float):
    """Return the linearly tapered cartridge's left/right/bottom/top bounds."""
    t = min(max(baffle_depth_fraction(y), 0.0), 1.0)
    rear_left = FAN_CENTER_X - BAFFLE_REAR_WIDTH / 2.0
    rear_right = FAN_CENTER_X + BAFFLE_REAR_WIDTH / 2.0
    front_left = -BAFFLE_FRONT_WIDTH / 2.0
    front_right = BAFFLE_FRONT_WIDTH / 2.0
    left = rear_left + (front_left - rear_left) * t
    right = rear_right + (front_right - rear_right) * t
    return left, right, -BAFFLE_BODY_HEIGHT / 2.0, BAFFLE_BODY_HEIGHT / 2.0


def baffle_bottom_left_stop_spec():
    for spec in CAMERA_STOP_SPECS:
        if spec[0] == "Bottom_Left_Large":
            return spec
    raise ValueError(
        "BAFFLE_CARTRIDGE_ENABLED requires the Bottom_Left_Large camera stop"
    )


def baffle_stop_relief_corner():
    _name, _x0, x1, _z0, z1, _attachment = baffle_bottom_left_stop_spec()
    return x1 + BAFFLE_STOP_CLEARANCE, z1 + BAFFLE_STOP_CLEARANCE


def baffle_outer_loop_at_y(y: float):
    left, right, bottom, top = baffle_body_bounds_at_y(y)
    step_x, step_z = baffle_stop_relief_corner()
    return [
        (left, top),
        (right, top),
        (right, bottom),
        (step_x, bottom),
        (step_x, step_z),
        (left, step_z),
    ]


def baffle_inner_loop_at_y(y: float):
    left, right, bottom, top = baffle_body_bounds_at_y(y)
    step_x, step_z = baffle_stop_relief_corner()
    wall = BAFFLE_WALL_THICKNESS
    return [
        (left + wall, top - wall),
        (right - wall, top - wall),
        (right - wall, bottom + wall),
        (step_x + wall, bottom + wall),
        (step_x + wall, step_z + wall),
        (left + wall, step_z + wall),
    ]


def baffle_effective_airway_bounds_at_y(y: float):
    left, right, bottom, top = baffle_body_bounds_at_y(y)
    return (
        left + BAFFLE_WALL_THICKNESS,
        right
        - BAFFLE_WALL_THICKNESS
        - BAFFLE_LID_KEY_DEPTH_X,
        bottom + BAFFLE_WALL_THICKNESS,
        top - BAFFLE_WALL_THICKNESS,
    )


def baffle_slot_spans(
    total_height: float,
    count: int,
    separator_thickness: float,
    center_z: float = 0.0,
):
    open_height = total_height - (count - 1) * separator_thickness
    slot_height = open_height / count
    first_bottom = center_z - total_height / 2.0
    return tuple(
        (
            first_bottom + index * (slot_height + separator_thickness),
            first_bottom
            + index * (slot_height + separator_thickness)
            + slot_height,
        )
        for index in range(count)
    )


def baffle_pointed_slot_loops(
    left_x: float,
    roof_apex_x: float,
    roof_run_x: float,
    spans,
):
    """Return broad inlet/outlet slots with self-supporting pointed roofs."""
    shoulder_x = roof_apex_x - roof_run_x
    return tuple(
        [
            (left_x, bottom),
            (shoulder_x, bottom),
            (roof_apex_x, (bottom + top) / 2.0),
            (shoulder_x, top),
            (left_x, top),
        ]
        for bottom, top in spans
    )


def baffle_inlet_loops():
    radius = BAFFLE_INLET_DIAMETER / 2.0
    return baffle_pointed_slot_loops(
        FAN_CENTER_X - radius,
        FAN_CENTER_X + BAFFLE_INLET_ROOF_APEX_X,
        BAFFLE_INLET_ROOF_RUN_X,
        baffle_slot_spans(
            BAFFLE_INLET_DIAMETER,
            BAFFLE_INLET_SLOT_COUNT,
            BAFFLE_INLET_SEPARATOR_THICKNESS_Z,
            FAN_CENTER_Z,
        ),
    )


def baffle_outlet_loops():
    half_width = BAFFLE_OUTLET_WIDTH / 2.0
    return baffle_pointed_slot_loops(
        -half_width,
        half_width,
        BAFFLE_OUTLET_ROOF_RUN_X,
        baffle_slot_spans(
            BAFFLE_OUTLET_HEIGHT,
            BAFFLE_OUTLET_SLOT_COUNT,
            BAFFLE_OUTLET_SEPARATOR_THICKNESS_Z,
        ),
    )


def baffle_inlet_effective_area() -> float:
    """Numerically integrate fan-circle area retained by the pointed slots."""
    radius = BAFFLE_INLET_DIAMETER / 2.0
    spans = baffle_slot_spans(
        BAFFLE_INLET_DIAMETER,
        BAFFLE_INLET_SLOT_COUNT,
        BAFFLE_INLET_SEPARATOR_THICKNESS_Z,
    )
    slices = 4096
    slice_height = 2.0 * radius / slices
    area = 0.0
    for index in range(slices):
        z = -radius + (index + 0.5) * slice_height
        circle_half_width = math.sqrt(max(radius * radius - z * z, 0.0))
        for bottom, top in spans:
            if bottom <= z <= top:
                half_slot_height = (top - bottom) / 2.0
                slot_center_z = (bottom + top) / 2.0
                roof_x = BAFFLE_INLET_ROOF_APEX_X - (
                    BAFFLE_INLET_ROOF_RUN_X
                    * abs(z - slot_center_z)
                    / half_slot_height
                )
                area += (
                    min(circle_half_width, roof_x)
                    + circle_half_width
                ) * slice_height
                break
    return area


def baffle_throat_areas():
    first_left, first_right, first_bottom, first_top = (
        baffle_effective_airway_bounds_at_y(BAFFLE_FIRST_Y)
    )
    step_x, step_z = baffle_stop_relief_corner()
    step_inner_x = step_x + BAFFLE_WALL_THICKNESS
    step_inner_z = step_z + BAFFLE_WALL_THICKNESS
    first_width = first_right - first_left
    first_height = first_top - first_bottom
    first_area = (
        first_width * (first_height - BAFFLE_FIRST_BLOCKER_HEIGHT_Z)
    )
    lower_lane_top = -BAFFLE_FIRST_BLOCKER_HEIGHT_Z / 2.0
    if step_inner_z < lower_lane_top:
        first_area -= max(step_inner_x - first_left, 0.0) * max(
            step_inner_z - first_bottom,
            0.0,
        )

    frame_rear_y = (
        BAFFLE_SECOND_Y
        - BAFFLE_SECOND_END_FRAME_REAR_SHIFT_Y
        - BAFFLE_SECOND_END_FRAME_DEPTH_Y / 2.0
    )
    second_left, second_right, _bottom, _top = (
        baffle_effective_airway_bounds_at_y(frame_rear_y)
    )
    second_area = (
        (second_right - second_left)
        * BAFFLE_SECOND_OPENING_HEIGHT_Z
        - 2.0
        * BAFFLE_SECOND_END_FRAME_CONNECTION_X
        * baffle_boolean_join_overlap()
    )
    outlet_open_height = BAFFLE_OUTLET_HEIGHT - (
        (BAFFLE_OUTLET_SLOT_COUNT - 1)
        * BAFFLE_OUTLET_SEPARATOR_THICKNESS_Z
    )
    outlet_area = (
        BAFFLE_OUTLET_WIDTH - BAFFLE_OUTLET_ROOF_RUN_X / 2.0
    ) * outlet_open_height
    return first_area, second_area, outlet_area


def baffle_gasket_is_integral() -> bool:
    return BAFFLE_CARTRIDGE_MATERIAL_MODE == "TPU"


def baffle_gasket_exposed_height() -> float:
    """Free seal height projecting behind the cartridge rear face."""
    return BAFFLE_GASKET_THICKNESS_Y - BAFFLE_GASKET_GROOVE_DEPTH_Y


def baffle_gasket_installed_gap() -> float:
    """Installed space occupied by the seal, including a rigid-tray groove."""
    surface_gap = BAFFLE_REAR_Y - fan_pad_inner_y()
    if baffle_gasket_is_integral():
        return surface_gap
    return surface_gap + BAFFLE_GASKET_GROOVE_DEPTH_Y


def baffle_gasket_compression() -> float:
    free_height = (
        baffle_gasket_exposed_height()
        if baffle_gasket_is_integral()
        else BAFFLE_GASKET_THICKNESS_Y
    )
    return free_height - baffle_gasket_installed_gap()


def baffle_camera_clearance() -> float:
    return camera_stop_end_y() - BAFFLE_FRONT_Y


def baffle_sleeve_clearance() -> float:
    return insert_sleeve_leading_y() - BAFFLE_FRONT_Y


def dome_cavity_radial_t_at_y(y: float) -> float:
    """Invert the inner dome's smoothstep Y mapping for fit features."""
    if y <= fan_pad_inner_y():
        return 0.0
    if y >= dome_inner_transition_y():
        return 1.0
    target = (
        (y - fan_pad_inner_y())
        / (dome_inner_transition_y() - fan_pad_inner_y())
    )
    lower = 0.0
    upper = 1.0
    for _iteration in range(48):
        middle = (lower + upper) / 2.0
        if smoothstep(middle) < target:
            lower = middle
        else:
            upper = middle
    return (lower + upper) / 2.0


def dome_cavity_half_height_at_y(y: float) -> float:
    t = dome_cavity_radial_t_at_y(y)
    return (
        BACK_DOME_FAN_PAD_HEIGHT / 2.0
        + (socket_height() / 2.0 - BACK_DOME_FAN_PAD_HEIGHT / 2.0) * t
    )


def baffle_snap_tongue_front_y() -> float:
    return BAFFLE_FRONT_Y - BAFFLE_WALL_THICKNESS / 2.0


def baffle_snap_tongue_center_x_at_y(y: float) -> float:
    del y
    return 0.0


def baffle_snap_auxiliary_center_x_at_y(y: float, axial_depth: float) -> float:
    del axial_depth
    return baffle_snap_tongue_center_x_at_y(y)


def baffle_snap_hook_y() -> float:
    return BAFFLE_SNAP_RECEIVER_Y - BAFFLE_SNAP_HOOK_SEATED_OFFSET_Y


def baffle_snap_tongue_center_z_at_y(y: float, side: float) -> float:
    root_y = BAFFLE_SNAP_TONGUE_ROOT_Y
    front_y = baffle_snap_tongue_front_y()
    t = min(max((y - root_y) / (front_y - root_y), 0.0), 1.0)
    root_center = (
        dome_cavity_half_height_at_y(root_y)
        - BAFFLE_SNAP_TONGUE_WALL_OFFSET
        - BAFFLE_SNAP_TONGUE_THICKNESS_Z / 2.0
    )
    front_center = (
        dome_cavity_half_height_at_y(front_y)
        - BAFFLE_SNAP_TONGUE_WALL_OFFSET
        - BAFFLE_SNAP_TONGUE_THICKNESS_Z / 2.0
    )
    return side * (root_center + (front_center - root_center) * t)


def baffle_snap_tongue_angle(side: float) -> float:
    root_y = BAFFLE_SNAP_TONGUE_ROOT_Y
    front_y = baffle_snap_tongue_front_y()
    delta_z = (
        baffle_snap_tongue_center_z_at_y(front_y, side)
        - baffle_snap_tongue_center_z_at_y(root_y, side)
    )
    return math.atan2(delta_z, front_y - root_y)


def baffle_snap_resolved_interference() -> float:
    """Return seated hook overtravel past the back-shell receiver crest."""
    hook_outer_z = (
        abs(baffle_snap_tongue_center_z_at_y(baffle_snap_hook_y(), 1.0))
        + BAFFLE_SNAP_TONGUE_THICKNESS_Z / 2.0
        + BAFFLE_SNAP_HOOK_PROTRUSION_Z
    )
    receiver_inner_z = (
        dome_cavity_half_height_at_y(BAFFLE_SNAP_RECEIVER_Y)
        - BAFFLE_SNAP_RECEIVER_PROJECTION_Z
    )
    return hook_outer_z - receiver_inner_z


def baffle_acoustic_visibility_required_inlet_z(
    internal_thickness_y: float | None = None,
) -> float:
    """Minimum inlet |Z| for a ray to thread both finite-thickness baffles.

    The least-demanding ray grazes the first blocker's forward edge and the
    second blocker's rear edge on the same side of the airway. Extrapolating
    that segment back to the inlet produces a conservative visibility bound;
    any sign-changing ray is necessarily steeper and needs still more inlet
    height.
    """
    if internal_thickness_y is None:
        internal_thickness_y = BAFFLE_INTERNAL_THICKNESS_Y
    half_depth = internal_thickness_y / 2.0
    first_front_y = BAFFLE_FIRST_Y + half_depth
    second_rear_y = BAFFLE_SECOND_Y - half_depth
    first_edge_z = BAFFLE_FIRST_BLOCKER_HEIGHT_Z / 2.0
    second_edge_z = BAFFLE_SECOND_OPENING_HEIGHT_Z / 2.0
    turn_gap = second_rear_y - first_front_y
    return first_edge_z + (
        (first_edge_z - second_edge_z)
        * (first_front_y - BAFFLE_REAR_Y)
        / turn_gap
    )


def resolved_retainer_layout():
    """Resolve the reference-style swing-gate outline from fastener axes."""
    ordered = sorted(CASE_FASTENER_POSITIONS_XZ, key=lambda point: point[1])
    lower_left, lower_right = sorted(ordered[:2], key=lambda point: point[0])
    upper = ordered[2]
    minimum_x = min(point[0] for point in CASE_FASTENER_POSITIONS_XZ)
    maximum_x = max(point[0] for point in CASE_FASTENER_POSITIONS_XZ)
    bar_bottom_z = lower_left[1] - RETAINER_LOWER_EDGE_MARGIN_Z
    bar_top_z = bar_bottom_z + RETAINER_HORIZONTAL_BAR_HEIGHT_Z
    upright_top_z = upper[1] + RETAINER_TOP_EDGE_MARGIN_Z
    return {
        "lower_left": lower_left,
        "lower_right": lower_right,
        "upper": upper,
        "bar_center_x": (minimum_x + maximum_x) / 2.0,
        "bar_width": (
            maximum_x
            - minimum_x
            + 2.0 * RETAINER_HORIZONTAL_END_MARGIN_X
        ),
        "bar_bottom_z": bar_bottom_z,
        "bar_top_z": bar_top_z,
        "bar_center_z": (bar_bottom_z + bar_top_z) / 2.0,
        "bar_left_x": minimum_x - RETAINER_HORIZONTAL_END_MARGIN_X,
        "bar_right_x": maximum_x + RETAINER_HORIZONTAL_END_MARGIN_X,
        "upright_center_z": (bar_bottom_z + upright_top_z) / 2.0,
        "upright_height": upright_top_z - bar_bottom_z,
        "upright_top_z": upright_top_z,
    }


def retainer_assembly_face_y() -> float:
    return insert_start_y() + INSERT_DEPTH


def retainer_gate_assembled_y() -> float:
    return retainer_assembly_face_y()


def retainer_bolt_sweep_point(bolt, pivot, angle_deg: float):
    """Return a fixed bolt's coordinates in a gate rotated by angle_deg."""
    angle = math.radians(angle_deg)
    delta_x = bolt[0] - pivot[0]
    delta_z = bolt[1] - pivot[1]
    return (
        pivot[0]
        + math.cos(angle) * delta_x
        + math.sin(angle) * delta_z,
        pivot[1]
        - math.sin(angle) * delta_x
        + math.cos(angle) * delta_z,
    )


def retainer_bolt_sweep_angles(end_angle_deg: float):
    steps = max(
        1,
        int(math.ceil(end_angle_deg / RETAINER_GATE_SWEEP_STEP_DEG)),
    )
    return [end_angle_deg * index / steps for index in range(steps + 1)]


def retainer_keeper_thickness_y() -> float:
    if RETAINER_MATERIAL_MODE == "TPU":
        return RETAINER_KEEPER_TPU_THICKNESS_Y
    return RETAINER_KEEPER_RIGID_THICKNESS_Y


def retainer_gate_thickness_y() -> float:
    if RETAINER_MATERIAL_MODE == "TPU":
        return RETAINER_GATE_TPU_THICKNESS_Y
    return RETAINER_GATE_RIGID_THICKNESS_Y


def retainer_index_key_centers(x: float, z: float):
    return (
        (x, z - RETAINER_KEEPER_INDEX_RADIAL_OFFSET),
        (x, z + RETAINER_KEEPER_INDEX_RADIAL_OFFSET),
    )


def retainer_index_recess_dimensions():
    clearance = 2.0 * RETAINER_KEEPER_INDEX_FIT_CLEARANCE
    return (
        RETAINER_KEEPER_INDEX_KEY_WIDTH_X + clearance,
        RETAINER_KEEPER_INDEX_KEY_HEIGHT_Z + clearance,
    )


def insert_outer_dimensions_at_t(t: float):
    """Return the tapered insert's outer X/Z dimensions at depth fraction t."""
    return (
        INSERT_FRONT_WIDTH + (INSERT_REAR_WIDTH - INSERT_FRONT_WIDTH) * t,
        INSERT_FRONT_HEIGHT + (INSERT_REAR_HEIGHT - INSERT_FRONT_HEIGHT) * t,
    )


def rounded_rectangle_containment_margin(
    outer_width: float,
    outer_height: float,
    outer_radius: float,
    inner_width: float,
    inner_height: float,
    inner_radius: float,
) -> float:
    """Return the minimum radial/straight margin between centered contours.

    A rounded rectangle is the Minkowski sum of a rectangle and a disk.  Its
    support function in the first quadrant is ``a*cos + b*sin + radius``.
    Comparing those support functions catches diagonal corner interference
    that independent X/Z extent checks miss, without rejecting a contour that
    tapers inward far enough for its corners to lie below the outer flats.
    """
    delta_a = (
        outer_width / 2.0
        - outer_radius
        - (inner_width / 2.0 - inner_radius)
    )
    delta_b = (
        outer_height / 2.0
        - outer_radius
        - (inner_height / 2.0 - inner_radius)
    )
    if delta_a < 0.0 and delta_b < 0.0:
        support_delta = -math.hypot(delta_a, delta_b)
    else:
        support_delta = min(delta_a, delta_b)
    return outer_radius - inner_radius + support_delta


def validate_rounded_rectangle_dimensions(
    name: str,
    width: float,
    height: float,
    radius: float,
) -> None:
    """Reject contours that the mesh helpers would otherwise silently clamp."""
    if width <= 0.0 or height <= 0.0:
        raise ValueError(
            f"{name} rounded rectangle must have positive width/height; "
            f"got {width:.3f} x {height:.3f} mm"
        )
    maximum_radius = min(width, height) / 2.0
    if not 0.0 < radius <= maximum_radius:
        raise ValueError(
            f"{name} rounded rectangle radius must be positive and no larger "
            f"than {maximum_radius:.3f} mm for its {width:.3f} x "
            f"{height:.3f} mm contour; got {radius:.3f} mm"
        )


def validate_retainer_config() -> None:
    """Validate geometry shared by both front-retainer options."""
    if not RETAINER_ENABLED:
        return
    if not CASE_FASTENERS_ENABLED:
        raise ValueError(
            "RETAINER_ENABLED requires CASE_FASTENERS_ENABLED; disable the "
            "retainer or enable the three case fasteners"
        )
    if len(CASE_FASTENER_POSITIONS_XZ) != 3:
        raise ValueError(
            "The swing-away front camera gate requires exactly three "
            "CASE_FASTENER_POSITIONS_XZ entries"
        )
    if RETAINER_STYLE not in {"SWING_GATE", "ROTATING_KEEPERS"}:
        raise ValueError(
            "RETAINER_STYLE must be SWING_GATE or ROTATING_KEEPERS; got "
            f"{RETAINER_STYLE!r}"
        )

    layout = resolved_retainer_layout()
    lower_left = layout["lower_left"]
    lower_right = layout["lower_right"]
    upper = layout["upper"]
    if abs(lower_left[1] - lower_right[1]) > 0.25:
        raise ValueError(
            "The front camera gate requires its two lower fasteners to "
            "share a horizontal row within 0.25 mm"
        )
    if upper[1] <= max(lower_left[1], lower_right[1]):
        raise ValueError(
            "The front camera gate requires one fastener above the two "
            "lower fasteners"
        )
    if RETAINER_GATE_BOLT_TRACK_DIAMETER < INSERT_FASTENER_HOLE_DIAMETER:
        raise ValueError(
            "RETAINER_GATE_BOLT_TRACK_DIAMETER must pass the same M3 shafts "
            "as INSERT_FASTENER_HOLE_DIAMETER"
        )
    required_upright_width = 2.0 * (
        abs(upper[0] - lower_right[0])
        + RETAINER_GATE_BOLT_TRACK_DIAMETER / 2.0
        + RETAINER_MIN_HOLE_WEB
    )
    if RETAINER_UPRIGHT_WIDTH_X < required_upright_width:
        raise ValueError(
            "RETAINER_UPRIGHT_WIDTH_X cannot provide the configured minimum "
            "web around the upper-right M3 pivot; need at least "
            f"{required_upright_width:.3f} mm"
        )
    required_edge_margin = (
        RETAINER_GATE_BOLT_TRACK_DIAMETER / 2.0
        + RETAINER_MIN_HOLE_WEB
    )
    if min(
        RETAINER_HORIZONTAL_END_MARGIN_X,
        RETAINER_LOWER_EDGE_MARGIN_Z,
        RETAINER_HORIZONTAL_BAR_HEIGHT_Z - RETAINER_LOWER_EDGE_MARGIN_Z,
        RETAINER_TOP_EDGE_MARGIN_Z,
    ) < required_edge_margin:
        raise ValueError(
            "The gate edge margins must preserve "
            f"{RETAINER_MIN_HOLE_WEB:.3f} mm outside each closed bolt pocket"
        )
    if RETAINER_GATE_MIN_NUT_BEARING_DIAMETER <= (
        RETAINER_GATE_BOLT_TRACK_DIAMETER
    ):
        raise ValueError(
            "RETAINER_GATE_MIN_NUT_BEARING_DIAMETER must exceed the bolt-track "
            "diameter so the thumbnuts can clamp the gate"
        )
    if RETAINER_CORNER_RADIUS > min(
        RETAINER_HORIZONTAL_BAR_HEIGHT_Z,
        RETAINER_UPRIGHT_WIDTH_X,
    ) / 2.0:
        raise ValueError(
            "RETAINER_CORNER_RADIUS must fit the lower bar and upright"
        )
    relief_bottom_z = RETAINER_RELIEF_CENTER_Z - RETAINER_RELIEF_RADIUS
    bar_half_width = layout["bar_width"] / 2.0
    if not (
        layout["bar_center_x"] - bar_half_width
        < RETAINER_RELIEF_CENTER_X
        < layout["bar_center_x"] + bar_half_width
    ):
        raise ValueError(
            "RETAINER_RELIEF_CENTER_X must lie within the horizontal bar"
        )
    minimum_center_strap_top = (
        layout["bar_bottom_z"] + RETAINER_MIN_HOLE_WEB
    )
    if not minimum_center_strap_top < relief_bottom_z < layout["bar_top_z"]:
        raise ValueError(
            "The gate relief must cut the horizontal bar while leaving at "
            "least RETAINER_MIN_HOLE_WEB of central strap"
        )
    if not (
        0.0 < RETAINER_GATE_LOWER_LEFT_RELEASE_ANGLE_DEG < 45.0
        and 0.0 < RETAINER_GATE_LOWER_RIGHT_RELEASE_ANGLE_DEG < 45.0
    ):
        raise ValueError(
            "Both lower-bolt release angles must lie between 0 and 45 degrees"
        )
    if RETAINER_GATE_SWEEP_STEP_DEG > min(
        RETAINER_GATE_LOWER_LEFT_RELEASE_ANGLE_DEG,
        RETAINER_GATE_LOWER_RIGHT_RELEASE_ANGLE_DEG,
    ):
        raise ValueError(
            "RETAINER_GATE_SWEEP_STEP_DEG is too coarse for the release tracks"
        )

    left_release = retainer_bolt_sweep_point(
        lower_left,
        upper,
        RETAINER_GATE_LOWER_LEFT_RELEASE_ANGLE_DEG,
    )
    if left_release[0] >= layout["bar_left_x"]:
        raise ValueError(
            "The lower-left bolt track does not reach the gate edge"
        )
    right_release = retainer_bolt_sweep_point(
        lower_right,
        upper,
        RETAINER_GATE_LOWER_RIGHT_RELEASE_ANGLE_DEG,
    )
    if (
        (right_release[0] - RETAINER_RELIEF_CENTER_X) ** 2
        + (right_release[1] - RETAINER_RELIEF_CENTER_Z) ** 2
        >= RETAINER_RELIEF_RADIUS**2
    ):
        raise ValueError(
            "The lower-right bolt track does not reach the camera relief"
        )

    keeper_radius = RETAINER_KEEPER_HUB_DIAMETER / 2.0
    keeper_hole_radius = RETAINER_KEEPER_BOLT_HOLE_DIAMETER / 2.0
    if RETAINER_KEEPER_BOLT_HOLE_DIAMETER < INSERT_FASTENER_HOLE_DIAMETER:
        raise ValueError(
            "RETAINER_KEEPER_BOLT_HOLE_DIAMETER must pass the same M3 shafts "
            "as INSERT_FASTENER_HOLE_DIAMETER"
        )
    if keeper_radius <= keeper_hole_radius + RETAINER_KEEPER_MIN_HOLE_WEB:
        raise ValueError(
            "RETAINER_KEEPER_HUB_DIAMETER leaves too little material around "
            "the M3 running hole; increase the hub diameter or reduce "
            "RETAINER_KEEPER_MIN_HOLE_WEB"
        )
    if RETAINER_KEEPER_LOBE_WIDTH_X > RETAINER_KEEPER_HUB_DIAMETER:
        raise ValueError(
            "RETAINER_KEEPER_LOBE_WIDTH_X must not exceed the hub diameter; "
            "otherwise the open keeper can project beyond the camera runners"
        )
    if RETAINER_KEEPER_CLOSED_PROJECTION_Z <= keeper_radius:
        raise ValueError(
            "RETAINER_KEEPER_CLOSED_PROJECTION_Z must extend beyond the hub"
        )

    bottom_runner_z = max(
        spec[4] for spec in LOCATING_TAB_SPECS if spec[5] == "bottom"
    )
    top_runner_z = min(
        spec[3] for spec in LOCATING_TAB_SPECS if spec[5] == "top"
    )
    lower_open_clearance = min(
        bottom_runner_z - point[1] - keeper_radius
        for point in (lower_left, lower_right)
    )
    upper_open_clearance = upper[1] - keeper_radius - top_runner_z
    if min(lower_open_clearance, upper_open_clearance) <= 0.0:
        raise ValueError(
            "The rotating-keeper hub projects past a camera-support runner in "
            "the open position; reduce RETAINER_KEEPER_HUB_DIAMETER"
        )
    lower_closed_overlap = min(
        point[1] + RETAINER_KEEPER_CLOSED_PROJECTION_Z - bottom_runner_z
        for point in (lower_left, lower_right)
    )
    upper_closed_overlap = (
        top_runner_z
        - (upper[1] - RETAINER_KEEPER_CLOSED_PROJECTION_Z)
    )
    if min(lower_closed_overlap, upper_closed_overlap) <= 0.0:
        raise ValueError(
            "The rotating-keeper lobe does not project inward beyond the "
            "camera-support runners when closed"
        )
    if RETAINER_GATE_RIGID_THICKNESS_Y >= RETAINER_GATE_TPU_THICKNESS_Y:
        raise ValueError(
            "RETAINER_GATE_TPU_THICKNESS_Y must exceed the rigid gate thickness"
        )
    if RETAINER_KEEPER_RIGID_THICKNESS_Y >= RETAINER_KEEPER_TPU_THICKNESS_Y:
        raise ValueError(
            "RETAINER_KEEPER_TPU_THICKNESS_Y must exceed the rigid thickness"
        )
    if (
        RETAINER_KEEPER_RIGID_THICKNESS_Y
        <= RETAINER_GATE_RIGID_THICKNESS_Y
        or RETAINER_KEEPER_TPU_THICKNESS_Y
        <= RETAINER_GATE_TPU_THICKNESS_Y
    ):
        raise ValueError(
            "Each rotating-keeper thickness must exceed the matching "
            "swing-gate thickness"
        )
    if RETAINER_KEEPER_INDEX_ENABLED:
        recess_width, recess_height = retainer_index_recess_dimensions()
        recess_inner_radius = (
            RETAINER_KEEPER_INDEX_RADIAL_OFFSET - recess_height / 2.0
        )
        recess_outer_radius = math.hypot(
            recess_width / 2.0,
            RETAINER_KEEPER_INDEX_RADIAL_OFFSET + recess_height / 2.0,
        )
        if recess_inner_radius <= keeper_hole_radius:
            raise ValueError(
                "The keeper index recesses overlap the M3 running hole"
            )
        if recess_outer_radius >= keeper_radius:
            raise ValueError(
                "The keeper index recesses do not fit inside the circular hub"
            )
        if (
            RETAINER_KEEPER_INDEX_KEY_PROJECTION_Y
            >= RETAINER_KEEPER_INDEX_RECESS_DEPTH_Y
        ):
            raise ValueError(
                "RETAINER_KEEPER_INDEX_RECESS_DEPTH_Y must exceed the sleeve "
                "key projection so a clamped keeper can seat fully"
            )
        if (
            RETAINER_KEEPER_INDEX_RECESS_DEPTH_Y
            >= RETAINER_KEEPER_RIGID_THICKNESS_Y
        ):
            raise ValueError(
                "The keeper index recess must leave material in the thinner "
                "rigid keeper"
            )
        key_outer_radius = math.hypot(
            RETAINER_KEEPER_INDEX_KEY_WIDTH_X / 2.0,
            RETAINER_KEEPER_INDEX_RADIAL_OFFSET
            + RETAINER_KEEPER_INDEX_KEY_HEIGHT_Z / 2.0,
        )
        if key_outer_radius >= INSERT_FASTENER_BOSS_DIAMETER / 2.0:
            raise ValueError(
                "The keeper index keys do not fit on the insert fastener boss"
            )


def validate_baffle_cartridge_config() -> None:
    if not BAFFLE_CARTRIDGE_ENABLED:
        return
    if not (BACK_DOME_ENABLED and FAN_OPENING_ENABLED and CAMERA_STOPS_ENABLED):
        raise ValueError(
            "BAFFLE_CARTRIDGE_ENABLED requires the rear dome, fan opening, "
            "and camera stops"
        )
    positive = {
        "BAFFLE_REAR_WIDTH": BAFFLE_REAR_WIDTH,
        "BAFFLE_FRONT_WIDTH": BAFFLE_FRONT_WIDTH,
        "BAFFLE_BODY_HEIGHT": BAFFLE_BODY_HEIGHT,
        "BAFFLE_WALL_THICKNESS": BAFFLE_WALL_THICKNESS,
        "BAFFLE_INTERNAL_THICKNESS_Y": BAFFLE_INTERNAL_THICKNESS_Y,
        "BAFFLE_LID_PLATE_THICKNESS_X": BAFFLE_LID_PLATE_THICKNESS_X,
        "BAFFLE_STOP_CLEARANCE": BAFFLE_STOP_CLEARANCE,
        "BAFFLE_INLET_DIAMETER": BAFFLE_INLET_DIAMETER,
        "BAFFLE_INLET_SEPARATOR_THICKNESS_Z": (
            BAFFLE_INLET_SEPARATOR_THICKNESS_Z
        ),
        "BAFFLE_INLET_ROOF_APEX_X": BAFFLE_INLET_ROOF_APEX_X,
        "BAFFLE_INLET_ROOF_RUN_X": BAFFLE_INLET_ROOF_RUN_X,
        "BAFFLE_GASKET_OUTER_DIAMETER": BAFFLE_GASKET_OUTER_DIAMETER,
        "BAFFLE_GASKET_INNER_DIAMETER": BAFFLE_GASKET_INNER_DIAMETER,
        "BAFFLE_GASKET_THICKNESS_Y": BAFFLE_GASKET_THICKNESS_Y,
        "BAFFLE_GASKET_BOSS_CLEARANCE": BAFFLE_GASKET_BOSS_CLEARANCE,
        "BAFFLE_GASKET_GROOVE_DEPTH_Y": BAFFLE_GASKET_GROOVE_DEPTH_Y,
        "BAFFLE_GASKET_GROOVE_RADIAL_CLEARANCE": (
            BAFFLE_GASKET_GROOVE_RADIAL_CLEARANCE
        ),
        "BAFFLE_FIRST_BLOCKER_HEIGHT_Z": BAFFLE_FIRST_BLOCKER_HEIGHT_Z,
        "BAFFLE_SECOND_OPENING_HEIGHT_Z": BAFFLE_SECOND_OPENING_HEIGHT_Z,
        "BAFFLE_MIN_EDGE_OVERLAP_Z": BAFFLE_MIN_EDGE_OVERLAP_Z,
        "BAFFLE_MIN_THROAT_AREA": BAFFLE_MIN_THROAT_AREA,
        "BAFFLE_OUTLET_WIDTH": BAFFLE_OUTLET_WIDTH,
        "BAFFLE_OUTLET_HEIGHT": BAFFLE_OUTLET_HEIGHT,
        "BAFFLE_OUTLET_SEPARATOR_THICKNESS_Z": (
            BAFFLE_OUTLET_SEPARATOR_THICKNESS_Z
        ),
        "BAFFLE_OUTLET_ROOF_RUN_X": BAFFLE_OUTLET_ROOF_RUN_X,
        "BAFFLE_MIN_ROOF_ANGLE_DEG": BAFFLE_MIN_ROOF_ANGLE_DEG,
        "BAFFLE_OUTLET_MIN_FRONT_WALL_SIDE_BAND_X": (
            BAFFLE_OUTLET_MIN_FRONT_WALL_SIDE_BAND_X
        ),
        "BAFFLE_LID_KEY_DEPTH_X": BAFFLE_LID_KEY_DEPTH_X,
        "BAFFLE_LID_FIT_CLEARANCE": BAFFLE_LID_FIT_CLEARANCE,
        "BAFFLE_TPU_LID_BLOCKER_SLOT_DEPTH_X": (
            BAFFLE_TPU_LID_BLOCKER_SLOT_DEPTH_X
        ),
        "BAFFLE_TPU_LID_BLOCKER_SLOT_ENGAGEMENT_X": (
            BAFFLE_TPU_LID_BLOCKER_SLOT_ENGAGEMENT_X
        ),
        "BAFFLE_TPU_LID_BLOCKER_SLOT_CLEARANCE_Y": (
            BAFFLE_TPU_LID_BLOCKER_SLOT_CLEARANCE_Y
        ),
        "BAFFLE_TPU_LID_BLOCKER_SLOT_CLEARANCE_Z": (
            BAFFLE_TPU_LID_BLOCKER_SLOT_CLEARANCE_Z
        ),
        "BAFFLE_SECOND_END_FRAME_DEPTH_Y": (
            BAFFLE_SECOND_END_FRAME_DEPTH_Y
        ),
        "BAFFLE_SECOND_END_FRAME_REAR_SHIFT_Y": (
            BAFFLE_SECOND_END_FRAME_REAR_SHIFT_Y
        ),
        "BAFFLE_SECOND_END_FRAME_CONNECTION_X": (
            BAFFLE_SECOND_END_FRAME_CONNECTION_X
        ),
        "BAFFLE_SECOND_END_FRAME_LID_ENGAGEMENT_X": (
            BAFFLE_SECOND_END_FRAME_LID_ENGAGEMENT_X
        ),
        "BAFFLE_SECOND_END_FRAME_LID_POCKET_DEPTH_X": (
            BAFFLE_SECOND_END_FRAME_LID_POCKET_DEPTH_X
        ),
        "BAFFLE_SECOND_END_FRAME_LID_CLEARANCE_Y": (
            BAFFLE_SECOND_END_FRAME_LID_CLEARANCE_Y
        ),
        "BAFFLE_SECOND_END_FRAME_LID_CLEARANCE_Z": (
            BAFFLE_SECOND_END_FRAME_LID_CLEARANCE_Z
        ),
        "BAFFLE_SECOND_END_FRAME_LID_MIN_WALL": (
            BAFFLE_SECOND_END_FRAME_LID_MIN_WALL
        ),
        "BAFFLE_SNAP_RECEIVER_WIDTH_X": BAFFLE_SNAP_RECEIVER_WIDTH_X,
        "BAFFLE_SNAP_RECEIVER_DEPTH_Y": BAFFLE_SNAP_RECEIVER_DEPTH_Y,
        "BAFFLE_SNAP_RECEIVER_PROJECTION_Z": (
            BAFFLE_SNAP_RECEIVER_PROJECTION_Z
        ),
        "BAFFLE_SNAP_RECEIVER_BEVEL": BAFFLE_SNAP_RECEIVER_BEVEL,
        "BAFFLE_SNAP_TONGUE_WIDTH_X": BAFFLE_SNAP_TONGUE_WIDTH_X,
        "BAFFLE_SNAP_TONGUE_THICKNESS_Z": (
            BAFFLE_SNAP_TONGUE_THICKNESS_Z
        ),
        "BAFFLE_SNAP_TONGUE_WALL_OFFSET": (
            BAFFLE_SNAP_TONGUE_WALL_OFFSET
        ),
        "BAFFLE_SNAP_ROOT_DEPTH_Y": BAFFLE_SNAP_ROOT_DEPTH_Y,
        "BAFFLE_SNAP_HOOK_PROTRUSION_Z": (
            BAFFLE_SNAP_HOOK_PROTRUSION_Z
        ),
        "BAFFLE_SNAP_HOOK_SEATED_OFFSET_Y": (
            BAFFLE_SNAP_HOOK_SEATED_OFFSET_Y
        ),
        "BAFFLE_SNAP_INTERFERENCE_Z": BAFFLE_SNAP_INTERFERENCE_Z,
    }
    for name, value in positive.items():
        if value <= 0.0:
            raise ValueError(f"{name} must be positive")
    if BAFFLE_BODY_DEPTH_SECTIONS < 2:
        raise ValueError("BAFFLE_BODY_DEPTH_SECTIONS must be at least 2")
    if BAFFLE_INLET_SLOT_COUNT < 1 or BAFFLE_OUTLET_SLOT_COUNT < 1:
        raise ValueError("The baffle inlet/outlet slot counts must be positive")
    if (
        (BAFFLE_INLET_SLOT_COUNT - 1)
        * BAFFLE_INLET_SEPARATOR_THICKNESS_Z
        >= BAFFLE_INLET_DIAMETER
        or (BAFFLE_OUTLET_SLOT_COUNT - 1)
        * BAFFLE_OUTLET_SEPARATOR_THICKNESS_Z
        >= BAFFLE_OUTLET_HEIGHT
    ):
        raise ValueError("The baffle separators consume their openings")
    if not (
        fan_boss_end_y()
        < BAFFLE_REAR_Y
        < BAFFLE_FIRST_Y
        < BAFFLE_SECOND_Y
        < BAFFLE_FRONT_Y
        < insert_sleeve_leading_y()
        and BAFFLE_FRONT_Y < camera_stop_end_y()
    ):
        raise ValueError(
            "The baffle gasket, body, baffles, sleeve, and camera-stop "
            "clearances are not in assembly order"
        )
    if abs(BAFFLE_INLET_DIAMETER - FAN_OPENING_DIAMETER) > 1.0e-6:
        raise ValueError(
            "BAFFLE_INLET_DIAMETER must match FAN_OPENING_DIAMETER for a "
            "sealed transition"
        )
    if BAFFLE_REAR_WIDTH >= BACK_DOME_FAN_PAD_WIDTH:
        raise ValueError("The baffle rear width must fit inside the fan pad")
    if BAFFLE_BODY_HEIGHT >= BACK_DOME_FAN_PAD_HEIGHT:
        raise ValueError("The baffle body height must fit inside the fan pad")
    if BAFFLE_FRONT_WIDTH >= socket_width():
        raise ValueError("The baffle front width must fit inside the back socket")
    if BAFFLE_BODY_HEIGHT >= socket_height():
        raise ValueError("The baffle body height must fit inside the back socket")
    if BAFFLE_WALL_THICKNESS * 2.0 >= min(
        BAFFLE_REAR_WIDTH,
        BAFFLE_BODY_HEIGHT,
    ):
        raise ValueError("BAFFLE_WALL_THICKNESS consumes the cartridge airway")
    if BAFFLE_LID_PLATE_THICKNESS_X > BAFFLE_WALL_THICKNESS:
        raise ValueError(
            "BAFFLE_LID_PLATE_THICKNESS_X cannot exceed the side wall"
        )
    if BAFFLE_LID_KEY_DEPTH_X + BAFFLE_LID_FIT_CLEARANCE >= (
        BAFFLE_REAR_WIDTH / 2.0
    ):
        raise ValueError("The baffle lid key consumes the rear airway")
    if BAFFLE_TPU_LID_BLOCKER_SLOT_DEPTH_X >= BAFFLE_LID_KEY_DEPTH_X:
        raise ValueError(
            "The TPU blocker slot must leave a closed floor in the lid key"
        )
    if (
        BAFFLE_TPU_LID_BLOCKER_SLOT_ENGAGEMENT_X
        >= BAFFLE_TPU_LID_BLOCKER_SLOT_DEPTH_X
    ):
        raise ValueError(
            "The TPU blocker tab needs clearance before the slot floor"
        )
    if BAFFLE_SECOND_END_FRAME_DEPTH_Y < 3.0:
        raise ValueError(
            "BAFFLE_SECOND_END_FRAME_DEPTH_Y must provide at least 3 mm "
            "of solid axial support"
        )
    frame_member_overlap_x = (
        BAFFLE_SECOND_END_FRAME_CONNECTION_X - BAFFLE_LID_FIT_CLEARANCE
    )
    if frame_member_overlap_x < 3.0:
        raise ValueError(
            "BAFFLE_SECOND_END_FRAME_CONNECTION_X must connect each "
            "camera-side member for at least 3 mm after the tray/lid "
            f"running gap; actual overlap={frame_member_overlap_x:.3f} mm"
        )
    if (
        BAFFLE_SECOND_END_FRAME_LID_ENGAGEMENT_X
        >= BAFFLE_SECOND_END_FRAME_LID_POCKET_DEPTH_X
    ):
        raise ValueError(
            "The second-baffle end frame needs clearance before its lid-"
            "pocket floor"
        )
    if (
        BAFFLE_SECOND_END_FRAME_LID_POCKET_DEPTH_X
        >= BAFFLE_LID_KEY_DEPTH_X
    ):
        raise ValueError(
            "The second-baffle end-frame pocket must leave a closed floor "
            "in the lid key"
        )
    lid_pocket_floor = (
        BAFFLE_LID_KEY_DEPTH_X
        - BAFFLE_SECOND_END_FRAME_LID_POCKET_DEPTH_X
    )
    if lid_pocket_floor < BAFFLE_SECOND_END_FRAME_LID_MIN_WALL:
        raise ValueError(
            "The second-baffle end-frame lid pocket leaves only "
            f"{lid_pocket_floor:.3f} mm of floor; minimum="
            f"{BAFFLE_SECOND_END_FRAME_LID_MIN_WALL:.3f} mm"
        )
    frame_center_y = (
        BAFFLE_SECOND_Y - BAFFLE_SECOND_END_FRAME_REAR_SHIFT_Y
    )
    frame_half_y = BAFFLE_SECOND_END_FRAME_DEPTH_Y / 2.0
    frame_rear_y = frame_center_y - frame_half_y
    frame_front_y = frame_center_y + frame_half_y
    largest_internal_half_y = max(
        profile["BAFFLE_INTERNAL_THICKNESS_Y"]
        for profile in BAFFLE_CARTRIDGE_MATERIAL_PROFILES.values()
    ) / 2.0
    if not (
        frame_rear_y
        <= BAFFLE_SECOND_Y - largest_internal_half_y
        < BAFFLE_SECOND_Y + largest_internal_half_y
        <= frame_front_y
    ):
        raise ValueError(
            "The second-baffle end frame must cover the complete axial "
            "thickness of both camera-side members"
        )
    frame_pocket_rear_y = (
        frame_rear_y - BAFFLE_SECOND_END_FRAME_LID_CLEARANCE_Y
    )
    frame_pocket_front_y = (
        frame_front_y + BAFFLE_SECOND_END_FRAME_LID_CLEARANCE_Y
    )
    for material_mode, profile in (
        BAFFLE_CARTRIDGE_MATERIAL_PROFILES.items()
    ):
        profile_wall = profile["BAFFLE_WALL_THICKNESS"]
        profile_key_start_y = (
            BAFFLE_REAR_Y + profile_wall + BAFFLE_LID_FIT_CLEARANCE
        )
        profile_key_end_y = (
            BAFFLE_FRONT_Y - profile_wall - BAFFLE_LID_FIT_CLEARANCE
        )
        axial_walls = (
            frame_pocket_rear_y - profile_key_start_y,
            profile_key_end_y - frame_pocket_front_y,
        )
        if min(axial_walls) < BAFFLE_SECOND_END_FRAME_LID_MIN_WALL:
            raise ValueError(
                f"The {material_mode} second-baffle end-frame pocket must "
                "retain the configured minimum front and rear lid-key walls: "
                f"available={axial_walls}, minimum="
                f"{BAFFLE_SECOND_END_FRAME_LID_MIN_WALL:.3f} mm"
            )
    if baffle_gasket_is_integral():
        slot_half_y = (
            BAFFLE_INTERNAL_THICKNESS_Y / 2.0
            + BAFFLE_TPU_LID_BLOCKER_SLOT_CLEARANCE_Y
        )
        slot_half_z = (
            BAFFLE_FIRST_BLOCKER_HEIGHT_Z / 2.0
            + BAFFLE_TPU_LID_BLOCKER_SLOT_CLEARANCE_Z
        )
        key_start_y = (
            BAFFLE_REAR_Y
            + BAFFLE_WALL_THICKNESS
            + BAFFLE_LID_FIT_CLEARANCE
        )
        key_end_y = (
            BAFFLE_FRONT_Y
            - BAFFLE_WALL_THICKNESS
            - BAFFLE_LID_FIT_CLEARANCE
        )
        if not (
            key_start_y < BAFFLE_FIRST_Y - slot_half_y
            < BAFFLE_FIRST_Y + slot_half_y < key_end_y
        ):
            raise ValueError(
                "The TPU center-blocker slot does not fit within the lid key"
            )
        key_half_height = (
            BAFFLE_BODY_HEIGHT / 2.0
            - BAFFLE_WALL_THICKNESS
            - BAFFLE_LID_FIT_CLEARANCE
        )
        if slot_half_z >= key_half_height:
            raise ValueError(
                "The TPU blocker slot consumes the top/bottom lid key"
            )
    if not (
        BAFFLE_GASKET_OUTER_DIAMETER
        > BAFFLE_GASKET_INNER_DIAMETER
        >= BAFFLE_INLET_DIAMETER
    ):
        raise ValueError("The baffle gasket diameters do not surround the inlet")
    if BAFFLE_GASKET_GROOVE_DEPTH_Y >= min(
        BAFFLE_GASKET_THICKNESS_Y,
        BAFFLE_WALL_THICKNESS,
    ):
        raise ValueError(
            "The gasket groove must leave both gasket exposure and rear-wall "
            "floor thickness"
        )
    if BAFFLE_WALL_THICKNESS - BAFFLE_GASKET_GROOVE_DEPTH_Y < 0.80:
        raise ValueError(
            "The gasket groove must retain at least 0.80 mm of rear-wall floor"
        )
    if (
        BAFFLE_GASKET_INNER_DIAMETER
        - 2.0 * BAFFLE_GASKET_GROOVE_RADIAL_CLEARANCE
        <= 0.0
    ):
        raise ValueError("The gasket groove clearance consumes its inner bore")
    inlet_shoulder_x = (
        BAFFLE_INLET_ROOF_APEX_X - BAFFLE_INLET_ROOF_RUN_X
    )
    if not (
        -BAFFLE_INLET_DIAMETER / 2.0
        < inlet_shoulder_x
        < BAFFLE_INLET_ROOF_APEX_X
    ):
        raise ValueError("The baffle inlet roof shoulder is invalid")
    rear_left, rear_right, _rear_bottom, _rear_top = (
        baffle_body_bounds_at_y(BAFFLE_REAR_Y)
    )
    if FAN_CENTER_X + BAFFLE_INLET_ROOF_APEX_X >= rear_right:
        raise ValueError("The pointed inlet roof consumes the rear right wall")
    if BAFFLE_OUTLET_ROOF_RUN_X >= BAFFLE_OUTLET_WIDTH:
        raise ValueError("BAFFLE_OUTLET_ROOF_RUN_X consumes the outlet")
    outlet_front_wall_bands = baffle_outlet_front_wall_side_band_widths()
    if (
        min(outlet_front_wall_bands)
        < BAFFLE_OUTLET_MIN_FRONT_WALL_SIDE_BAND_X
    ):
        raise ValueError(
            "The pointed outlet leaves an undersized side band in the solid "
            "front wall: "
            f"available={outlet_front_wall_bands}, minimum="
            f"{BAFFLE_OUTLET_MIN_FRONT_WALL_SIDE_BAND_X:.3f} mm"
        )
    front_left_for_print = baffle_body_bounds_at_y(BAFFLE_FRONT_Y)[0]
    print_vertical_x_factor = 1.0 / math.sqrt(
        1.0
        + (
            (front_left_for_print - rear_left)
            / (BAFFLE_FRONT_Y - BAFFLE_REAR_Y)
        ) ** 2
    )
    inlet_slot_half_height = (
        BAFFLE_INLET_DIAMETER
        - (BAFFLE_INLET_SLOT_COUNT - 1)
        * BAFFLE_INLET_SEPARATOR_THICKNESS_Z
    ) / (2.0 * BAFFLE_INLET_SLOT_COUNT)
    outlet_slot_half_height = (
        BAFFLE_OUTLET_HEIGHT
        - (BAFFLE_OUTLET_SLOT_COUNT - 1)
        * BAFFLE_OUTLET_SEPARATOR_THICKNESS_Z
    ) / (2.0 * BAFFLE_OUTLET_SLOT_COUNT)
    inlet_downward_normal = (
        print_vertical_x_factor
        * inlet_slot_half_height
        / math.hypot(inlet_slot_half_height, BAFFLE_INLET_ROOF_RUN_X)
    )
    outlet_downward_normal = (
        print_vertical_x_factor
        * outlet_slot_half_height
        / math.hypot(outlet_slot_half_height, BAFFLE_OUTLET_ROOF_RUN_X)
    )
    maximum_downward_normal = math.cos(
        math.radians(BAFFLE_MIN_ROOF_ANGLE_DEG)
    )
    if (
        inlet_downward_normal > maximum_downward_normal
        or outlet_downward_normal > maximum_downward_normal
    ):
        raise ValueError(
            "The pointed inlet/outlet roofs are below BAFFLE_MIN_ROOF_ANGLE_DEG "
            "in the exported tray orientation"
        )
    compression = baffle_gasket_compression()
    if not 0.0 < compression < baffle_gasket_exposed_height() / 2.0:
        raise ValueError(
            "The baffle seal stack needs positive compression below half its "
            "exposed free height"
        )
    overlap = (
        BAFFLE_FIRST_BLOCKER_HEIGHT_Z
        - BAFFLE_SECOND_OPENING_HEIGHT_Z
    ) / 2.0
    if overlap < BAFFLE_MIN_EDGE_OVERLAP_Z:
        raise ValueError(
            "The alternating baffles do not provide the configured acoustic "
            "line-of-sight overlap"
        )
    rear_wall_plane_y = BAFFLE_REAR_Y
    front_wall_plane_y = BAFFLE_FRONT_Y
    thickness_cases = [("ACTIVE", BAFFLE_INTERNAL_THICKNESS_Y)]
    thickness_cases.extend(
        (material_mode, profile["BAFFLE_INTERNAL_THICKNESS_Y"])
        for material_mode, profile in BAFFLE_CARTRIDGE_MATERIAL_PROFILES.items()
        if abs(
            profile["BAFFLE_INTERNAL_THICKNESS_Y"]
            - BAFFLE_INTERNAL_THICKNESS_Y
        )
        > 1.0e-9
    )
    for material_mode, internal_thickness in thickness_cases:
        half_internal = internal_thickness / 2.0
        first_rear_y = BAFFLE_FIRST_Y - half_internal
        first_front_y = BAFFLE_FIRST_Y + half_internal
        second_rear_y = BAFFLE_SECOND_Y - half_internal
        second_front_y = BAFFLE_SECOND_Y + half_internal
        if not (
            rear_wall_plane_y
            < first_rear_y
            < first_front_y
            < second_rear_y
            < second_front_y
            < front_wall_plane_y
        ):
            raise ValueError(
                f"The {material_mode} finite-thickness baffles overlap a "
                "wall or each other"
            )
        turn_gap = second_rear_y - first_front_y
        if turn_gap <= max(BAFFLE_WALL_THICKNESS, internal_thickness):
            raise ValueError(
                f"The {material_mode} baffles leave only {turn_gap:.3f} mm "
                "for the acoustic turn"
            )
        required_inlet_z = baffle_acoustic_visibility_required_inlet_z(
            internal_thickness
        )
        if required_inlet_z <= BAFFLE_INLET_DIAMETER / 2.0:
            raise ValueError(
                f"The {material_mode} baffles permit direct acoustic line "
                f"of sight: required inlet |Z|={required_inlet_z:.3f} mm"
            )
    inlet_area = baffle_inlet_effective_area()
    first_area, second_area, outlet_area = baffle_throat_areas()
    if min(inlet_area, first_area, second_area, outlet_area) < (
        BAFFLE_MIN_THROAT_AREA
    ):
        raise ValueError(
            "The baffle airway is below BAFFLE_MIN_THROAT_AREA: "
            f"inlet={inlet_area:.2f} first={first_area:.2f} "
            f"second={second_area:.2f} outlet={outlet_area:.2f} mm2"
        )
    front_left, front_right, front_bottom, front_top = (
        baffle_effective_airway_bounds_at_y(BAFFLE_FRONT_Y)
    )
    if (
        BAFFLE_OUTLET_WIDTH >= front_right - front_left
        or BAFFLE_OUTLET_HEIGHT >= front_top - front_bottom
    ):
        raise ValueError("The baffle outlet does not fit in the forward face")
    if not (
        BAFFLE_SNAP_TONGUE_ROOT_Y
        < baffle_snap_hook_y()
        < BAFFLE_SNAP_RECEIVER_Y
        < baffle_snap_tongue_front_y()
    ):
        raise ValueError(
            "The seated hook and receiver must lie in order along each tongue"
        )
    if BAFFLE_SNAP_HOOK_SEATED_OFFSET_Y <= compression:
        raise ValueError(
            "The snap latch travel must exceed the inlet-gasket compression"
        )
    resolved_interference = baffle_snap_resolved_interference()
    if abs(resolved_interference - BAFFLE_SNAP_INTERFERENCE_Z) > 0.02:
        raise ValueError(
            "BAFFLE_SNAP_INTERFERENCE_Z does not match the receiver/hook "
            f"stack; resolved {resolved_interference:.3f} mm"
        )
    step_x, step_z = baffle_stop_relief_corner()
    rear_left, rear_right, rear_bottom, rear_top = baffle_body_bounds_at_y(
        BAFFLE_REAR_Y
    )
    if not (
        rear_left + BAFFLE_WALL_THICKNESS
        < step_x
        < rear_right - BAFFLE_WALL_THICKNESS
        and rear_bottom + BAFFLE_WALL_THICKNESS
        < step_z
        < rear_top - BAFFLE_WALL_THICKNESS
    ):
        raise ValueError("The bottom-left stop relief collapses the rear body")


def validate_config() -> None:
    material_choices = {"RIGID", "TPU"}
    for name, mode in (
        ("BACK_MATERIAL_MODE", BACK_MATERIAL_MODE),
        ("SLEEVE_MATERIAL_MODE", SLEEVE_MATERIAL_MODE),
        ("RETAINER_MATERIAL_MODE", RETAINER_MATERIAL_MODE),
        (
            "BAFFLE_CARTRIDGE_MATERIAL_MODE",
            BAFFLE_CARTRIDGE_MATERIAL_MODE,
        ),
    ):
        if mode not in material_choices:
            raise ValueError(
                f"{name} must be RIGID or TPU; got {mode!r}"
            )
    positive = {
        "BACK_OUTER_WIDTH": BACK_OUTER_WIDTH,
        "BACK_OUTER_HEIGHT": BACK_OUTER_HEIGHT,
        "BACK_CORNER_RADIUS": BACK_CORNER_RADIUS,
        "BACK_DEPTH": BACK_DEPTH,
        "BACK_FACE_THICKNESS": BACK_FACE_THICKNESS,
        "BACK_DOME_DEPTH": BACK_DOME_DEPTH,
        "BACK_DOME_FAN_PAD_WIDTH": BACK_DOME_FAN_PAD_WIDTH,
        "BACK_DOME_FAN_PAD_HEIGHT": BACK_DOME_FAN_PAD_HEIGHT,
        "INSERTION_DEPTH": INSERTION_DEPTH,
        "INSERT_FRONT_WIDTH": INSERT_FRONT_WIDTH,
        "INSERT_FRONT_HEIGHT": INSERT_FRONT_HEIGHT,
        "INSERT_REAR_WIDTH": INSERT_REAR_WIDTH,
        "INSERT_REAR_HEIGHT": INSERT_REAR_HEIGHT,
        "INSERT_DEPTH": INSERT_DEPTH,
        "INSERT_WALL_X": INSERT_WALL_X,
        "INSERT_WALL_Z": INSERT_WALL_Z,
        "FIT_CLEARANCE_X": FIT_CLEARANCE_X,
        "FIT_CLEARANCE_Z": FIT_CLEARANCE_Z,
        "FAN_OPENING_DIAMETER": FAN_OPENING_DIAMETER,
        "FAN_HOLE_DIAMETER": FAN_HOLE_DIAMETER,
        "VENT_WIDTH": VENT_WIDTH,
        "VENT_HEIGHT": VENT_HEIGHT,
        "SNAP_BUMP_LENGTH_Y": SNAP_BUMP_LENGTH_Y,
        "SNAP_BUMP_LENGTH_Z": SNAP_BUMP_LENGTH_Z,
        "LEFT_ROUND_PORT_DIAMETER": LEFT_ROUND_PORT_DIAMETER,
        "TOP_PORT_DIAMETER": TOP_PORT_DIAMETER,
        "RIGHT_USB_PORT_WIDTH_Y": RIGHT_USB_PORT_WIDTH_Y,
        "RIGHT_USB_PORT_HEIGHT_Z": RIGHT_USB_PORT_HEIGHT_Z,
        "BUTTON_STEM_DIAMETER": BUTTON_STEM_DIAMETER,
        "BUTTON_TOTAL_HEIGHT": BUTTON_TOTAL_HEIGHT,
        "BUTTON_INNER_FLANGE_THICKNESS": (
            BUTTON_INNER_FLANGE_THICKNESS
        ),
        "BUTTON_INNER_FLANGE_DIAMETER": BUTTON_INNER_FLANGE_DIAMETER,
        "BUTTON_RETENTION_RIM_DIAMETER": BUTTON_RETENTION_RIM_DIAMETER,
        "BUTTON_RETENTION_RIM_HEIGHT": BUTTON_RETENTION_RIM_HEIGHT,
        "BUTTON_RETENTION_SHOULDER_HEIGHT": (
            BUTTON_RETENTION_SHOULDER_HEIGHT
        ),
        "BUTTON_RETENTION_LEAD_IN_HEIGHT": (
            BUTTON_RETENTION_LEAD_IN_HEIGHT
        ),
        "BACK_FASTENER_HEX_WIDTH_X": BACK_FASTENER_HEX_WIDTH_X,
        "BACK_FASTENER_HEX_HEIGHT_Z": BACK_FASTENER_HEX_HEIGHT_Z,
        "BACK_FASTENER_HEX_SEAT_TO_INSERT": BACK_FASTENER_HEX_SEAT_TO_INSERT,
        "BACK_FASTENER_HEX_TRANSITION_DEPTH": BACK_FASTENER_HEX_TRANSITION_DEPTH,
        "BACK_FASTENER_HEX_PART_THICKNESS_Y": (
            BACK_FASTENER_HEX_PART_THICKNESS_Y
        ),
        "BACK_FASTENER_RETENTION_TAB_WIDTH_X": (
            BACK_FASTENER_RETENTION_TAB_WIDTH_X
        ),
        "BACK_FASTENER_RETENTION_TAB_DEPTH_Y": (
            BACK_FASTENER_RETENTION_TAB_DEPTH_Y
        ),
        "BACK_FASTENER_RETENTION_TAB_PROTRUSION": (
            BACK_FASTENER_RETENTION_TAB_PROTRUSION
        ),
        "BACK_FASTENER_RETENTION_TAB_OFFSET_FROM_SEAT": (
            BACK_FASTENER_RETENTION_TAB_OFFSET_FROM_SEAT
        ),
        "LENS_CLEARANCE_CUTTER_MARGIN": LENS_CLEARANCE_CUTTER_MARGIN,
    }
    if SLEEVE_CAPTURE_SLOT_ENABLED:
        positive.update(
            {
                "SLEEVE_CAPTURE_ENGAGEMENT_DEPTH": (
                    SLEEVE_CAPTURE_ENGAGEMENT_DEPTH
                ),
                "SLEEVE_CAPTURE_FIT_CLEARANCE": (
                    SLEEVE_CAPTURE_FIT_CLEARANCE
                ),
                "SLEEVE_CAPTURE_INNER_LIP_THICKNESS": (
                    SLEEVE_CAPTURE_INNER_LIP_THICKNESS
                ),
                "SLEEVE_CAPTURE_BOTTOM_CLEARANCE": (
                    SLEEVE_CAPTURE_BOTTOM_CLEARANCE
                ),
                "SLEEVE_CAPTURE_FLOOR_THICKNESS": (
                    SLEEVE_CAPTURE_FLOOR_THICKNESS
                ),
                "SLEEVE_CAPTURE_MIN_OUTER_WALL_X": (
                    SLEEVE_CAPTURE_MIN_OUTER_WALL_X
                ),
                "SLEEVE_CAPTURE_MIN_OUTER_WALL_Z": (
                    SLEEVE_CAPTURE_MIN_OUTER_WALL_Z
                ),
            }
        )
        if (
            CASE_FASTENERS_ENABLED
            and BACK_FASTENER_TO_INSERT_SOCKET_GAP
            <= BOOLEAN_CLEANUP_DISTANCE
        ):
            positive["BACK_FASTENER_MIN_DATUM_CONTACT_AREA"] = (
                BACK_FASTENER_MIN_DATUM_CONTACT_AREA
            )
    if RETAINER_ENABLED:
        positive.update(
            {
                "RETAINER_GATE_RIGID_THICKNESS_Y": (
                    RETAINER_GATE_RIGID_THICKNESS_Y
                ),
                "RETAINER_GATE_TPU_THICKNESS_Y": (
                    RETAINER_GATE_TPU_THICKNESS_Y
                ),
                "RETAINER_HORIZONTAL_END_MARGIN_X": (
                    RETAINER_HORIZONTAL_END_MARGIN_X
                ),
                "RETAINER_HORIZONTAL_BAR_HEIGHT_Z": (
                    RETAINER_HORIZONTAL_BAR_HEIGHT_Z
                ),
                "RETAINER_LOWER_EDGE_MARGIN_Z": (
                    RETAINER_LOWER_EDGE_MARGIN_Z
                ),
                "RETAINER_UPRIGHT_WIDTH_X": RETAINER_UPRIGHT_WIDTH_X,
                "RETAINER_TOP_EDGE_MARGIN_Z": RETAINER_TOP_EDGE_MARGIN_Z,
                "RETAINER_CORNER_RADIUS": RETAINER_CORNER_RADIUS,
                "RETAINER_RELIEF_RADIUS": RETAINER_RELIEF_RADIUS,
                "RETAINER_MIN_HOLE_WEB": RETAINER_MIN_HOLE_WEB,
                "RETAINER_GATE_BOLT_TRACK_DIAMETER": (
                    RETAINER_GATE_BOLT_TRACK_DIAMETER
                ),
                "RETAINER_GATE_MIN_NUT_BEARING_DIAMETER": (
                    RETAINER_GATE_MIN_NUT_BEARING_DIAMETER
                ),
                "RETAINER_GATE_LOWER_LEFT_RELEASE_ANGLE_DEG": (
                    RETAINER_GATE_LOWER_LEFT_RELEASE_ANGLE_DEG
                ),
                "RETAINER_GATE_LOWER_RIGHT_RELEASE_ANGLE_DEG": (
                    RETAINER_GATE_LOWER_RIGHT_RELEASE_ANGLE_DEG
                ),
                "RETAINER_GATE_SWEEP_STEP_DEG": (
                    RETAINER_GATE_SWEEP_STEP_DEG
                ),
                "RETAINER_KEEPER_BOLT_HOLE_DIAMETER": (
                    RETAINER_KEEPER_BOLT_HOLE_DIAMETER
                ),
                "RETAINER_KEEPER_HUB_DIAMETER": RETAINER_KEEPER_HUB_DIAMETER,
                "RETAINER_KEEPER_MIN_HOLE_WEB": (
                    RETAINER_KEEPER_MIN_HOLE_WEB
                ),
                "RETAINER_KEEPER_LOBE_WIDTH_X": RETAINER_KEEPER_LOBE_WIDTH_X,
                "RETAINER_KEEPER_CLOSED_PROJECTION_Z": (
                    RETAINER_KEEPER_CLOSED_PROJECTION_Z
                ),
                "RETAINER_KEEPER_RIGID_THICKNESS_Y": (
                    RETAINER_KEEPER_RIGID_THICKNESS_Y
                ),
                "RETAINER_KEEPER_TPU_THICKNESS_Y": (
                    RETAINER_KEEPER_TPU_THICKNESS_Y
                ),
            }
        )
        if RETAINER_KEEPER_INDEX_ENABLED:
            positive.update(
                {
                    "RETAINER_KEEPER_INDEX_RADIAL_OFFSET": (
                        RETAINER_KEEPER_INDEX_RADIAL_OFFSET
                    ),
                    "RETAINER_KEEPER_INDEX_KEY_WIDTH_X": (
                        RETAINER_KEEPER_INDEX_KEY_WIDTH_X
                    ),
                    "RETAINER_KEEPER_INDEX_KEY_HEIGHT_Z": (
                        RETAINER_KEEPER_INDEX_KEY_HEIGHT_Z
                    ),
                    "RETAINER_KEEPER_INDEX_KEY_PROJECTION_Y": (
                        RETAINER_KEEPER_INDEX_KEY_PROJECTION_Y
                    ),
                    "RETAINER_KEEPER_INDEX_FIT_CLEARANCE": (
                        RETAINER_KEEPER_INDEX_FIT_CLEARANCE
                    ),
                    "RETAINER_KEEPER_INDEX_RECESS_DEPTH_Y": (
                        RETAINER_KEEPER_INDEX_RECESS_DEPTH_Y
                    ),
                    "RETAINER_KEEPER_INDEX_KEY_BEVEL": (
                        RETAINER_KEEPER_INDEX_KEY_BEVEL
                    ),
                }
            )
    for name, value in positive.items():
        if value <= 0.0:
            raise ValueError(f"{name} must be positive")

    if LAYOUT_MODE not in {"assembled", "print_bed"}:
        raise ValueError('LAYOUT_MODE must be "assembled" or "print_bed"')
    if not LEFT_ROUND_PORT_ENABLED or not TOP_PORT_ENABLED:
        raise ValueError(
            "Captive buttons require LEFT_ROUND_PORT_ENABLED and "
            "TOP_PORT_ENABLED so both button stems have sleeve openings"
        )
    smallest_button_port = min(
        LEFT_ROUND_PORT_DIAMETER,
        TOP_PORT_DIAMETER,
    )
    largest_button_port = max(
        LEFT_ROUND_PORT_DIAMETER,
        TOP_PORT_DIAMETER,
    )
    if BUTTON_STEM_DIAMETER >= smallest_button_port:
        raise ValueError(
            "BUTTON_STEM_DIAMETER must be smaller than both captive-button "
            f"ports; got {BUTTON_STEM_DIAMETER:.3f} mm stem and "
            f"{smallest_button_port:.3f} mm smallest port"
        )
    if BUTTON_INNER_FLANGE_DIAMETER <= largest_button_port:
        raise ValueError(
            "BUTTON_INNER_FLANGE_DIAMETER must exceed both captive-button "
            f"ports; got {BUTTON_INNER_FLANGE_DIAMETER:.3f} mm flange and "
            f"{largest_button_port:.3f} mm largest port"
        )
    if BUTTON_RETENTION_RIM_DIAMETER <= largest_button_port:
        raise ValueError(
            "BUTTON_RETENTION_RIM_DIAMETER must exceed both captive-button "
            "ports to retain the buttons after installation; got "
            f"{BUTTON_RETENTION_RIM_DIAMETER:.3f} mm rim and "
            f"{largest_button_port:.3f} mm largest port"
        )
    if BUTTON_RETENTION_RIM_DIAMETER >= BUTTON_INNER_FLANGE_DIAMETER:
        raise ValueError(
            "BUTTON_RETENTION_RIM_DIAMETER must be smaller than "
            "BUTTON_INNER_FLANGE_DIAMETER"
        )
    if BUTTON_TOTAL_HEIGHT <= (
        BUTTON_INNER_FLANGE_THICKNESS + BUTTON_RETENTION_RIM_HEIGHT
    ):
        raise ValueError(
            "BUTTON_TOTAL_HEIGHT must leave a positive stem length between "
            "the inner flange and exterior retention rim"
        )
    if (
        BUTTON_RETENTION_SHOULDER_HEIGHT
        + BUTTON_RETENTION_LEAD_IN_HEIGHT
        > BUTTON_RETENTION_RIM_HEIGHT
    ):
        raise ValueError(
            "BUTTON_RETENTION_SHOULDER_HEIGHT plus "
            "BUTTON_RETENTION_LEAD_IN_HEIGHT cannot exceed "
            "BUTTON_RETENTION_RIM_HEIGHT"
        )
    validate_retainer_config()
    validate_baffle_cartridge_config()
    if not 0.0 < BACK_FACE_THICKNESS < BACK_DEPTH:
        raise ValueError("BACK_FACE_THICKNESS must be less than BACK_DEPTH")
    if not 0.0 < INSERTION_DEPTH < min(BACK_DEPTH, INSERT_DEPTH):
        raise ValueError("INSERTION_DEPTH must fit inside both parts")
    rim_start_z = BUTTON_TOTAL_HEIGHT - BUTTON_RETENTION_RIM_HEIGHT
    minimum_rim_start_z = (
        BUTTON_INNER_FLANGE_THICKNESS + max(INSERT_WALL_X, INSERT_WALL_Z)
    )
    if rim_start_z <= minimum_rim_start_z:
        raise ValueError(
            "The captive-button retention rim must sit completely beyond "
            "both sleeve walls when the inner flange is seated; increase "
            "BUTTON_TOTAL_HEIGHT or reduce BUTTON_RETENTION_RIM_HEIGHT"
        )
    if min(FIT_CLEARANCE_X, FIT_CLEARANCE_Z) <= BOOLEAN_CLEANUP_DISTANCE:
        raise ValueError(
            "FIT_CLEARANCE_X and FIT_CLEARANCE_Z must both exceed the "
            f"{BOOLEAN_CLEANUP_DISTANCE:.4f} mm mesh-cleanup tolerance"
        )
    if INSERT_DEPTH_SECTIONS < 1:
        raise ValueError("INSERT_DEPTH_SECTIONS must be at least 1")
    if BACK_DOME_SECTIONS < 2:
        raise ValueError("BACK_DOME_SECTIONS must be at least 2")
    if BACK_DOME_LOOP_POINTS < 16 or BACK_DOME_LOOP_POINTS % 4:
        raise ValueError("BACK_DOME_LOOP_POINTS must be a multiple of 4 and at least 16")
    if BACK_DOME_START_BEHIND_CAMERA_STOPS < 0.0:
        raise ValueError(
            "BACK_DOME_START_BEHIND_CAMERA_STOPS cannot be negative"
        )
    if BACK_DOME_ENABLED and not (
        back_exterior_y() < dome_outer_transition_y() < BACK_DEPTH
    ):
        raise ValueError("The exterior dome transition must fit within the shell depth")
    if BACK_DOME_ENABLED and not (
        fan_pad_inner_y() < dome_inner_transition_y() <= BACK_DEPTH
    ):
        raise ValueError("The interior dome transition must fit within the shell depth")
    if BACK_DOME_ENABLED and not (
        back_exterior_y()
        <= BACK_DOME_FASTENER_CHIMNEY_REAR_Y
        < dome_outer_transition_y()
    ):
        raise ValueError(
            "BACK_DOME_FASTENER_CHIMNEY_REAR_Y must lie within the dome depth"
        )
    retention_tab_rear_y = (
        back_fastener_retention_tab_center_y()
        - BACK_FASTENER_RETENTION_TAB_DEPTH_Y / 2.0
    )
    if (
        BACK_DOME_ENABLED
        and BACK_FASTENER_HEX_RETENTION_ENABLED
        and BACK_FASTENER_RETENTION_TABS_ENABLED
        and BACK_DOME_FASTENER_CHIMNEY_REAR_Y
        >= retention_tab_rear_y - BOOLEAN_OVERLAP
    ):
        raise ValueError(
            "The dome fastener chimneys must begin behind the hex retention tabs"
        )
    effective_back_width, effective_back_height, effective_back_radius = (
        effective_back_outer_dimensions()
    )
    insert_inner_radius = resolved_insert_inner_corner_radius()
    base_contours = (
        (
            "Requested back shell",
            BACK_OUTER_WIDTH,
            BACK_OUTER_HEIGHT,
            BACK_CORNER_RADIUS,
        ),
        (
            "Insert front outer",
            INSERT_FRONT_WIDTH,
            INSERT_FRONT_HEIGHT,
            INSERT_OUTER_CORNER_RADIUS,
        ),
        (
            "Insert rear outer",
            INSERT_REAR_WIDTH,
            INSERT_REAR_HEIGHT,
            INSERT_OUTER_CORNER_RADIUS,
        ),
        (
            "Insert inner opening",
            insert_inner_width(),
            insert_inner_height(),
            insert_inner_radius,
        ),
        (
            "Ordinary socket",
            socket_width(),
            socket_height(),
            socket_corner_radius(),
        ),
        (
            "Effective back shell",
            effective_back_width,
            effective_back_height,
            effective_back_radius,
        ),
    )
    for name, width, height, radius in base_contours:
        validate_rounded_rectangle_dimensions(name, width, height, radius)

    for name, width, height in (
        ("front", INSERT_FRONT_WIDTH, INSERT_FRONT_HEIGHT),
        ("rear", INSERT_REAR_WIDTH, INSERT_REAR_HEIGHT),
    ):
        inner_margin = rounded_rectangle_containment_margin(
            width,
            height,
            INSERT_OUTER_CORNER_RADIUS,
            insert_inner_width(),
            insert_inner_height(),
            insert_inner_radius,
        )
        if inner_margin <= BOOLEAN_CLEANUP_DISTANCE:
            raise ValueError(
                f"The insert {name} outer contour does not contain its "
                f"constant inner opening: minimum wall margin "
                f"{inner_margin:.3f} mm; required more than "
                f"{BOOLEAN_CLEANUP_DISTANCE:.4f} mm"
            )
    if (
        BACK_DOME_FAN_PAD_WIDTH >= effective_back_width
        or BACK_DOME_FAN_PAD_HEIGHT >= effective_back_height
    ):
        raise ValueError("The dome fan pad must fit inside the rear shell perimeter")
    if insert_inner_width() <= 0.0 or insert_inner_height() <= 0.0:
        raise ValueError("Insert wall thickness leaves no interior opening")
    if (
        socket_width() >= effective_back_width
        or socket_height() >= effective_back_height
    ):
        raise ValueError("The mating socket does not fit inside the rear shell")
    insertion_t = INSERTION_DEPTH / INSERT_DEPTH
    overlap_width, overlap_height = insert_outer_dimensions_at_t(insertion_t)
    remaining_socket_clearance_x = (socket_width() - overlap_width) / 2.0
    remaining_socket_clearance_z = (socket_height() - overlap_height) / 2.0
    remaining_socket_corner_clearance = rounded_rectangle_containment_margin(
        socket_width(),
        socket_height(),
        socket_corner_radius(),
        overlap_width,
        overlap_height,
        INSERT_OUTER_CORNER_RADIUS,
    )
    if min(
        remaining_socket_clearance_x,
        remaining_socket_clearance_z,
        remaining_socket_corner_clearance,
    ) <= BOOLEAN_CLEANUP_DISTANCE:
        raise ValueError(
            "The tapered insert does not fit through the ordinary socket for "
            f"the full {INSERTION_DEPTH:.3f} mm insertion overlap: sleeve "
            f"contour reaches {overlap_width:.3f} x {overlap_height:.3f} mm "
            f"inside a {socket_width():.3f} x {socket_height():.3f} mm socket "
            "(remaining per-face X/Z clearance "
            f"{remaining_socket_clearance_x:.3f}/"
            f"{remaining_socket_clearance_z:.3f} mm; minimum rounded-contour "
            f"clearance {remaining_socket_corner_clearance:.3f} mm). Reduce "
            "the outward "
            "taper, enlarge the socket clearance, or keep the overlap "
            "section straight."
        )
    if SLEEVE_CAPTURE_SLOT_ENABLED:
        if SLEEVE_CAPTURE_ENGAGEMENT_DEPTH >= INSERTION_DEPTH:
            raise ValueError(
                "SLEEVE_CAPTURE_ENGAGEMENT_DEPTH must be smaller than the "
                "ordinary INSERTION_DEPTH"
            )
        if SLEEVE_CAPTURE_FIT_CLEARANCE >= min(
            FIT_CLEARANCE_X,
            FIT_CLEARANCE_Z,
        ):
            raise ValueError(
                "SLEEVE_CAPTURE_FIT_CLEARANCE must be smaller than both "
                "ordinary socket clearances so the groove and socket cutters "
                "do not have coincident outer contours"
            )
        groove_outer_width, groove_outer_height, groove_outer_radius = (
            sleeve_capture_groove_outer_dimensions()
        )
        groove_inner_width, groove_inner_height, groove_inner_radius = (
            sleeve_capture_groove_inner_dimensions()
        )
        opening_width, opening_height, opening_radius = (
            sleeve_capture_opening_dimensions()
        )
        support_width, support_height, support_radius = (
            sleeve_capture_outer_support_dimensions()
        )
        for name, width, height, radius in (
            (
                "Sleeve capture groove outer face",
                groove_outer_width,
                groove_outer_height,
                groove_outer_radius,
            ),
            (
                "Sleeve capture groove inner face",
                groove_inner_width,
                groove_inner_height,
                groove_inner_radius,
            ),
            (
                "Sleeve capture lip opening",
                opening_width,
                opening_height,
                opening_radius,
            ),
            (
                "Sleeve capture outer support",
                support_width,
                support_height,
                support_radius,
            ),
        ):
            validate_rounded_rectangle_dimensions(name, width, height, radius)
        minimum_corner_support = min(
            SLEEVE_CAPTURE_MIN_OUTER_WALL_X,
            SLEEVE_CAPTURE_MIN_OUTER_WALL_Z,
        )
        groove_corner_center = (
            groove_outer_width / 2.0 - groove_outer_radius,
            groove_outer_height / 2.0 - groove_outer_radius,
        )
        support_corner_center = (
            support_width / 2.0 - support_radius,
            support_height / 2.0 - support_radius,
        )
        resolved_corner_support = (
            support_radius
            - groove_outer_radius
            - math.hypot(
                support_corner_center[0] - groove_corner_center[0],
                support_corner_center[1] - groove_corner_center[1],
            )
        )
        if (
            resolved_corner_support
            < minimum_corner_support - BOOLEAN_CLEANUP_DISTANCE
        ):
            raise ValueError(
                "The sleeve capture outer-support contour leaves only "
                f"{resolved_corner_support:.3f} mm at a rounded corner; "
                f"required {minimum_corner_support:.3f} mm"
            )
        effective_corner_center = (
            effective_back_width / 2.0 - effective_back_radius,
            effective_back_height / 2.0 - effective_back_radius,
        )
        support_containment = (
            effective_back_radius
            - support_radius
            - math.hypot(
                effective_corner_center[0] - support_corner_center[0],
                effective_corner_center[1] - support_corner_center[1],
            )
        )
        if support_containment < -BOOLEAN_CLEANUP_DISTANCE:
            raise ValueError(
                "The effective back-shell contour does not contain the "
                "sleeve-capture support contour"
            )
        requested_corner_center = (
            BACK_OUTER_WIDTH / 2.0 - BACK_CORNER_RADIUS,
            BACK_OUTER_HEIGHT / 2.0 - BACK_CORNER_RADIUS,
        )
        requested_containment = (
            effective_back_radius
            - BACK_CORNER_RADIUS
            - math.hypot(
                effective_corner_center[0] - requested_corner_center[0],
                effective_corner_center[1] - requested_corner_center[1],
            )
        )
        if requested_containment < -BOOLEAN_CLEANUP_DISTANCE:
            raise ValueError(
                "The effective back-shell contour does not contain the "
                "requested legacy back-shell contour"
            )
        if min(
            groove_inner_width,
            groove_inner_height,
            groove_inner_radius,
            opening_width,
            opening_height,
            opening_radius,
        ) <= 0.0:
            raise ValueError(
                "The sleeve capture clearance/lip leaves an invalid inner "
                "opening or rounded-corner radius"
            )
        if not (
            sleeve_capture_ledge_start_y()
            < sleeve_capture_groove_floor_y()
            < insert_sleeve_leading_y()
            < insert_start_y()
        ):
            raise ValueError(
                "The sleeve capture floor, bottom clearance, leading edge, "
                "and screw-boss datum are not in assembly order"
            )
        if sleeve_capture_ledge_start_y() <= back_exterior_y():
            raise ValueError(
                "The sleeve capture groove breaks through the front of the "
                "back shell; reduce its depth/clearance or deepen the shell"
            )
    if FAN_OPENING_DIAMETER >= min(effective_back_width, effective_back_height):
        raise ValueError("FAN_OPENING_DIAMETER is too large for the rear shell")
    fan_mount_radius = max(
        FAN_HOLE_DIAMETER / 2.0,
        FAN_HOLE_BOSS_DIAMETER / 2.0 if FAN_HOLE_BOSSES_ENABLED else 0.0,
    )
    fan_extent_x = max(
        FAN_OPENING_DIAMETER / 2.0,
        FAN_HOLE_SPACING_X / 2.0 + fan_mount_radius,
    )
    fan_extent_z = max(
        FAN_OPENING_DIAMETER / 2.0,
        FAN_HOLE_SPACING_Z / 2.0 + fan_mount_radius,
    )
    if (
        fan_extent_x > BACK_DOME_FAN_PAD_WIDTH / 2.0
        or fan_extent_z > BACK_DOME_FAN_PAD_HEIGHT / 2.0
    ):
        raise ValueError("The fan opening or a screw boss extends beyond the dome fan pad")
    if SNAP_BUMP_PROTRUSION <= FIT_CLEARANCE_X:
        raise ValueError(
            "SNAP_BUMP_PROTRUSION must exceed FIT_CLEARANCE_X to create a snap"
        )
    if SNAP_BUMP_Y_OFFSET + SNAP_BUMP_LENGTH_Y > INSERTION_DEPTH + 0.5:
        raise ValueError("The snap bump must remain within the insertion overlap")
    if BACK_FASTENER_TO_INSERT_SOCKET_GAP < 0.0:
        raise ValueError("BACK_FASTENER_TO_INSERT_SOCKET_GAP cannot be negative")
    if (
        SLEEVE_CAPTURE_SLOT_ENABLED
        and CASE_FASTENERS_ENABLED
        and BACK_FASTENER_TO_INSERT_SOCKET_GAP
        <= BOOLEAN_CLEANUP_DISTANCE
    ):
        common_boss_radius = min(
            BACK_FASTENER_BOSS_DIAMETER,
            INSERT_FASTENER_BOSS_DIAMETER,
        ) / 2.0
        common_bore_radius = max(
            BACK_FASTENER_HOLE_DIAMETER,
            INSERT_FASTENER_HOLE_DIAMETER,
        ) / 2.0
        maximum_boss_contact_area = math.pi * (
            common_boss_radius**2 - common_bore_radius**2
        )
        if BACK_FASTENER_MIN_DATUM_CONTACT_AREA >= maximum_boss_contact_area:
            raise ValueError(
                "BACK_FASTENER_MIN_DATUM_CONTACT_AREA must be smaller than "
                "the common boss annulus area "
                f"({maximum_boss_contact_area:.2f} mm2)"
            )
    if CAMERA_STOP_TO_INSERT_SOCKET_GAP < 0.0:
        raise ValueError("CAMERA_STOP_TO_INSERT_SOCKET_GAP cannot be negative")
    if CAMERA_STOP_FASTENER_CLEARANCE < 0.0:
        raise ValueError("CAMERA_STOP_FASTENER_CLEARANCE cannot be negative")
    if BACK_FASTENER_HEX_WIDTH_X >= BACK_FASTENER_BOSS_DIAMETER:
        raise ValueError("The fastener hex corners do not fit inside the rear boss")
    if BACK_FASTENER_HEX_HEIGHT_Z >= BACK_FASTENER_BOSS_DIAMETER:
        raise ValueError("The fastener hex flats do not fit inside the rear boss")
    if not back_exterior_y() < back_fastener_hex_seat_y():
        raise ValueError("The fastener hex seat must be inside the rear shell")
    if back_fastener_bore_start_y() >= back_fastener_end_y():
        raise ValueError("The fastener transition leaves no rear shaft tube")
    if 2.0 * BACK_FASTENER_RETENTION_TAB_PROTRUSION >= (
        BACK_FASTENER_HEX_HEIGHT_Z - BACK_FASTENER_HOLE_DIAMETER
    ):
        raise ValueError("The fastener retaining tabs obstruct the shaft bore")
    if BACK_FASTENER_HEX_RETENTION_ENABLED and BACK_FASTENER_RETENTION_TABS_ENABLED:
        tab_center_y = back_fastener_retention_tab_center_y()
        tab_entry_face_y = (
            tab_center_y - BACK_FASTENER_RETENTION_TAB_DEPTH_Y / 2.0
        )
        tab_seat_face_y = (
            tab_center_y + BACK_FASTENER_RETENTION_TAB_DEPTH_Y / 2.0
        )
        if tab_entry_face_y <= back_exterior_y() + BOOLEAN_OVERLAP:
            raise ValueError(
                "The fastener retaining tabs do not fit inside the hex recess"
            )
        if tab_seat_face_y >= back_fastener_hex_seat_y():
            raise ValueError("The fastener retaining tabs extend through the hex seat")
        axial_preload = back_fastener_retention_axial_preload()
        if axial_preload < 0.0:
            raise ValueError(
                "The fastener retaining tabs leave axial play behind the seated "
                f"hex parts ({-axial_preload:.3f} mm gap)"
            )
        if axial_preload >= BACK_FASTENER_HEX_PART_THICKNESS_Y:
            raise ValueError(
                "The fastener retaining tabs block the hex parts from seating"
            )
    valid_attachments = {"top", "bottom", "left", "right"}
    for spec in CAMERA_STOP_SPECS:
        name, x0, x1, z0, z1, attachment = spec
        if x1 <= x0 or z1 <= z0:
            raise ValueError(f"Camera stop {name} has invalid X/Z bounds")
        if camera_stop_end_y() <= fan_pad_inner_y() - BOOLEAN_OVERLAP:
            raise ValueError(f"Camera stop {name} has no positive Y depth")
        if attachment not in valid_attachments:
            raise ValueError(f"Camera stop {name} has an invalid attachment side")

    for spec in LOCATING_TAB_SPECS:
        name, x0, x1, z0, z1, attachment = spec
        if x1 <= x0 or z1 <= z0:
            raise ValueError(f"Locating rail {name} has invalid X/Z bounds")
        if attachment not in valid_attachments:
            raise ValueError(f"Locating rail {name} has an invalid attachment side")

    rail_specs_by_name = {spec[0]: spec for spec in LOCATING_TAB_SPECS}
    for name, (
        taper_length,
        front_projection,
    ) in LENS_CLEARANCE_GUIDE_TAPERS.items():
        if name not in rail_specs_by_name:
            raise ValueError(f"Lens-clearance guide {name} is not a locating rail")
        if not 0.0 < taper_length <= INSERT_DEPTH:
            raise ValueError(f"Lens-clearance guide {name} has an invalid taper length")
        if front_projection < 0.0:
            raise ValueError(
                f"Lens-clearance guide {name} cannot have negative projection"
            )
        _, x0, x1, z0, z1, attachment = rail_specs_by_name[name]
        if attachment == "top":
            full_projection = insert_inner_height() / 2.0 - z0
        elif attachment == "right":
            full_projection = insert_inner_width() / 2.0 - x0
        elif attachment == "left":
            full_projection = x1 + insert_inner_width() / 2.0
        else:
            raise ValueError(
                f"Lens-clearance guide {name} must attach to the top or a side wall"
            )
        if front_projection >= full_projection:
            raise ValueError(
                f"Lens-clearance guide {name} front projection must be below its full projection"
            )

    if not 0.0 <= RIGHT_USB_PORT_CORNER_RADIUS <= min(
        RIGHT_USB_PORT_WIDTH_Y, RIGHT_USB_PORT_HEIGHT_Z
    ) / 2.0:
        raise ValueError("RIGHT_USB_PORT_CORNER_RADIUS does not fit the USB port")

    stop_by_name = {spec[0]: spec for spec in CAMERA_STOP_SPECS}
    rail_by_name = {spec[0]: spec for spec in LOCATING_TAB_SPECS}
    stop_overhangs = {
        "Top_Left": rail_by_name["Top_Left"][3] - stop_by_name["Top_Left"][3],
        "Top_Right": rail_by_name["Top_Right"][3] - stop_by_name["Top_Right"][3],
        "Bottom_Left": (
            stop_by_name["Bottom_Left_Large"][4]
            - rail_by_name["Bottom_Left"][4]
        ),
        "Bottom_Right": (
            stop_by_name["Bottom_Right"][4]
            - rail_by_name["Bottom_Right"][4]
        ),
        "Left_Side": stop_by_name["Left_Side"][2] - rail_by_name["Left_Side"][2],
        "Right_Side": rail_by_name["Right_Side"][1] - stop_by_name["Right_Side"][1],
    }
    for name, overhang in stop_overhangs.items():
        if overhang <= 0.0:
            raise ValueError(
                f"Camera stop {name} must project past its insert locating rail"
            )


def clear_scene() -> None:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


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


def cleanup_boolean_mesh(obj) -> None:
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


def cleanup_opposing_triangle_pairs(obj, label: str) -> int:
    """Remove zero-thickness face pairs exposed by final mesh tessellation.

    Blender's Boolean result can be manifold as polygons while two adjacent
    n-gons tessellate to the same tiny triangle with opposite winding.  That
    pair is a zero-thickness flap in the exported STL.  Tessellate explicitly,
    remove only exact opposing triangle pairs, and require the resulting mesh
    to remain closed.
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(
        bm,
        faces=list(bm.faces),
        quad_method="BEAUTY",
        ngon_method="BEAUTY",
    )
    bm.verts.ensure_lookup_table()
    bm.verts.index_update()
    bm.faces.ensure_lookup_table()

    faces_by_vertices = {}
    for face in bm.faces:
        face.normal_update()
        key = tuple(sorted(vertex.index for vertex in face.verts))
        faces_by_vertices.setdefault(key, []).append(face)

    remove_faces = set()
    for coincident_faces in faces_by_vertices.values():
        available = list(coincident_faces)
        while available:
            face = available.pop()
            opposing_index = next(
                (
                    index
                    for index, candidate in enumerate(available)
                    if face.normal.dot(candidate.normal) < -0.999999
                ),
                None,
            )
            if opposing_index is not None:
                remove_faces.add(face)
                remove_faces.add(available.pop(opposing_index))

    if remove_faces:
        bmesh.ops.delete(bm, geom=list(remove_faces), context="FACES")

    non_manifold_edges = sum(
        len(edge.link_faces) != 2 for edge in bm.edges
    )
    if non_manifold_edges:
        bm.free()
        raise RuntimeError(
            f"{label} tessellation cleanup left {non_manifold_edges} "
            "non-manifold edges"
        )

    removed_count = len(remove_faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    recalc_normals(obj)
    if removed_count:
        print(
            f"TESSELLATION_CLEANUP {label}: "
            f"removed_opposing_triangles={removed_count}"
        )
    return removed_count


def remove_tiny_mesh_components(obj, minimum_faces: int = 8) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    unseen = set(bm.verts)
    remove_verts = []
    while unseen:
        seed = unseen.pop()
        stack = [seed]
        component = [seed]
        while stack:
            vertex = stack.pop()
            for edge in vertex.link_edges:
                neighbor = edge.other_vert(vertex)
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    stack.append(neighbor)
                    component.append(neighbor)
        component_faces = {
            face for vertex in component for face in vertex.link_faces
        }
        if len(component_faces) < minimum_faces:
            remove_verts.extend(component)
    if remove_verts:
        bmesh.ops.delete(bm, geom=remove_verts, context="VERTS")
        bm.to_mesh(obj.data)
        obj.data.update()
    bm.free()


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
# Primitive mesh helpers


def rounded_rectangle_loop(width: float, height: float, radius: float):
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
    for corner_index, (cx, cz, a0, a1) in enumerate(corners):
        for i in range(CORNER_SEGMENTS + 1):
            if corner_index == len(corners) - 1 and i == CORNER_SEGMENTS:
                continue
            angle = math.radians(a0 + (a1 - a0) * i / CORNER_SEGMENTS)
            points.append((cx + radius * math.cos(angle), cz + radius * math.sin(angle)))
    return points


def rounded_rectangle_path_from_top(
    width: float, height: float, radius: float, corner_segments: int
):
    half_width = width / 2.0
    half_height = height / 2.0
    radius = min(max(radius, 0.0), half_width, half_height)
    if radius == 0.0:
        return [
            (0.0, half_height),
            (-half_width, half_height),
            (-half_width, 0.0),
            (-half_width, -half_height),
            (0.0, -half_height),
            (half_width, -half_height),
            (half_width, 0.0),
            (half_width, half_height),
        ]

    points = [(0.0, half_height), (-half_width + radius, half_height)]
    corners = (
        (-half_width + radius, half_height - radius, 90.0, 180.0),
        (-half_width + radius, -half_height + radius, 180.0, 270.0),
        (half_width - radius, -half_height + radius, 270.0, 360.0),
        (half_width - radius, half_height - radius, 0.0, 90.0),
    )
    cardinal_points = (
        (-half_width, 0.0),
        (0.0, -half_height),
        (half_width, 0.0),
    )
    for corner_index, (cx, cz, angle0, angle1) in enumerate(corners):
        for step in range(1, corner_segments + 1):
            angle = math.radians(
                angle0 + (angle1 - angle0) * step / corner_segments
            )
            points.append(
                (cx + radius * math.cos(angle), cz + radius * math.sin(angle))
            )
        if corner_index < len(cardinal_points):
            points.append(cardinal_points[corner_index])
    return points


def resample_closed_loop(loop, count: int):
    points = list(loop)
    segment_lengths = []
    perimeter = 0.0
    for index, point in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        length = math.hypot(next_point[0] - point[0], next_point[1] - point[1])
        segment_lengths.append(length)
        perimeter += length

    result = []
    segment_index = 0
    segment_start_distance = 0.0
    for sample_index in range(count):
        target_distance = perimeter * sample_index / count
        while (
            segment_index < len(points) - 1
            and segment_start_distance + segment_lengths[segment_index]
            < target_distance
        ):
            segment_start_distance += segment_lengths[segment_index]
            segment_index += 1
        point = points[segment_index]
        next_point = points[(segment_index + 1) % len(points)]
        length = segment_lengths[segment_index]
        fraction = (target_distance - segment_start_distance) / length
        result.append(
            (
                point[0] + (next_point[0] - point[0]) * fraction,
                point[1] + (next_point[1] - point[1]) * fraction,
            )
        )
    return result


def polygon_prism_y(name: str, loop, y0: float, y1: float, offset=(0.0, 0.0)):
    ox, oz = offset
    points = [(x + ox, z + oz) for x, z in loop]
    count = len(points)
    center_x = sum(x for x, _ in points) / count
    center_z = sum(z for _, z in points) / count
    vertices = [(x, y0, z) for x, z in points]
    vertices.extend((x, y1, z) for x, z in points)
    vertices.extend(((center_x, y0, center_z), (center_x, y1, center_z)))
    front_center = count * 2
    rear_center = front_center + 1

    faces = []
    for i in range(count):
        j = (i + 1) % count
        faces.append([i, count + i, count + j, j])
        faces.append([front_center, i, j])
        faces.append([rear_center, count + j, count + i])
    return create_mesh_object(name, vertices, faces)


def capsule_prism_y(name: str, point0, point1, radius: float, y0: float, y1: float):
    """Create a continuous round-ended slot cutter between two X/Z points."""
    delta_x = point1[0] - point0[0]
    delta_z = point1[1] - point0[1]
    if math.hypot(delta_x, delta_z) <= BOOLEAN_CLEANUP_DISTANCE:
        return add_cylinder_y(
            name,
            radius,
            y0,
            y1,
            x=point0[0],
            z=point0[1],
        )
    direction_angle = math.atan2(delta_z, delta_x)
    cap_segments = max(12, CYLINDER_SEGMENTS // 2)
    loop = []
    for index in range(cap_segments + 1):
        angle = direction_angle - math.pi / 2.0 + math.pi * index / cap_segments
        loop.append(
            (
                point1[0] + radius * math.cos(angle),
                point1[1] + radius * math.sin(angle),
            )
        )
    for index in range(cap_segments + 1):
        angle = direction_angle + math.pi / 2.0 + math.pi * index / cap_segments
        loop.append(
            (
                point0[0] + radius * math.cos(angle),
                point0[1] + radius * math.sin(angle),
            )
        )
    return polygon_prism_y(name, loop, y0, y1)


def rounded_rectangle_prism_y(
    name: str,
    width: float,
    height: float,
    radius: float,
    y0: float,
    y1: float,
    center_x: float = 0.0,
    center_z: float = 0.0,
):
    return polygon_prism_y(
        name,
        rounded_rectangle_loop(width, height, radius),
        y0,
        y1,
        offset=(center_x, center_z),
    )


def rounded_rectangle_ring_prism_y(
    name: str,
    outer_width: float,
    outer_height: float,
    outer_radius: float,
    inner_width: float,
    inner_height: float,
    inner_radius: float,
    y0: float,
    y1: float,
):
    """Create one closed rounded-rectangle annulus without a broad membrane."""
    validate_rounded_rectangle_dimensions(
        f"{name} outer",
        outer_width,
        outer_height,
        outer_radius,
    )
    validate_rounded_rectangle_dimensions(
        f"{name} inner",
        inner_width,
        inner_height,
        inner_radius,
    )
    if not (
        outer_width > inner_width > 0.0
        and outer_height > inner_height > 0.0
        and outer_radius > inner_radius > 0.0
        and y1 > y0
    ):
        raise ValueError(f"Invalid rounded-rectangle ring dimensions for {name}")

    outer_loop = rounded_rectangle_loop(
        outer_width,
        outer_height,
        outer_radius,
    )
    inner_loop = rounded_rectangle_loop(
        inner_width,
        inner_height,
        inner_radius,
    )
    if len(outer_loop) != len(inner_loop):
        raise RuntimeError(f"Rounded-rectangle ring loops do not align for {name}")

    count = len(outer_loop)
    vertices = [(x, y0, z) for x, z in outer_loop]
    vertices.extend((x, y1, z) for x, z in outer_loop)
    vertices.extend((x, y0, z) for x, z in inner_loop)
    vertices.extend((x, y1, z) for x, z in inner_loop)
    outer_low = 0
    outer_high = count
    inner_low = 2 * count
    inner_high = 3 * count

    faces = []
    for index in range(count):
        next_index = (index + 1) % count
        faces.extend(
            (
                (
                    outer_low + index,
                    outer_high + index,
                    outer_high + next_index,
                    outer_low + next_index,
                ),
                (
                    inner_low + next_index,
                    inner_high + next_index,
                    inner_high + index,
                    inner_low + index,
                ),
                (
                    outer_low + next_index,
                    outer_low + index,
                    inner_low + index,
                    inner_low + next_index,
                ),
                (
                    outer_high + index,
                    outer_high + next_index,
                    inner_high + next_index,
                    inner_high + index,
                ),
            )
        )
    return create_mesh_object(name, vertices, faces)


def annular_cylinder_y(
    name: str,
    outer_radius: float,
    inner_radius: float,
    y0: float,
    y1: float,
    x: float = 0.0,
    z: float = 0.0,
):
    if not 0.0 < inner_radius < outer_radius:
        raise ValueError("An annular cylinder needs positive inner and outer radii")
    if y1 <= y0:
        raise ValueError("An annular cylinder needs positive depth")

    vertices = []
    for radius, y in (
        (outer_radius, y0),
        (outer_radius, y1),
        (inner_radius, y0),
        (inner_radius, y1),
    ):
        vertices.extend(
            (
                x + radius * math.cos(2.0 * math.pi * index / CYLINDER_SEGMENTS),
                y,
                z + radius * math.sin(2.0 * math.pi * index / CYLINDER_SEGMENTS),
            )
            for index in range(CYLINDER_SEGMENTS)
        )

    outer_front = 0
    outer_back = CYLINDER_SEGMENTS
    inner_front = 2 * CYLINDER_SEGMENTS
    inner_back = 3 * CYLINDER_SEGMENTS
    faces = []
    for index in range(CYLINDER_SEGMENTS):
        next_index = (index + 1) % CYLINDER_SEGMENTS
        faces.extend(
            (
                (
                    outer_front + index,
                    outer_back + index,
                    outer_back + next_index,
                    outer_front + next_index,
                ),
                (
                    inner_front + index,
                    inner_front + next_index,
                    inner_back + next_index,
                    inner_back + index,
                ),
                (
                    outer_front + index,
                    outer_front + next_index,
                    inner_front + next_index,
                    inner_front + index,
                ),
                (
                    outer_back + index,
                    inner_back + index,
                    inner_back + next_index,
                    outer_back + next_index,
                ),
            )
        )
    return create_mesh_object(name, vertices, faces)


def rounded_rectangle_prism_x(
    name: str,
    width_y: float,
    height_z: float,
    radius: float,
    x0: float,
    x1: float,
    center_y: float = 0.0,
    center_z: float = 0.0,
):
    loop = rounded_rectangle_loop(width_y, height_z, radius)
    points = [(y + center_y, z + center_z) for y, z in loop]
    count = len(points)
    center_loop_y = sum(y for y, _ in points) / count
    center_loop_z = sum(z for _, z in points) / count
    vertices = [(x0, y, z) for y, z in points]
    vertices.extend((x1, y, z) for y, z in points)
    vertices.extend(
        ((x0, center_loop_y, center_loop_z), (x1, center_loop_y, center_loop_z))
    )
    low_center = count * 2
    high_center = low_center + 1

    faces = []
    for i in range(count):
        j = (i + 1) % count
        faces.append([i, j, count + j, count + i])
        faces.append([low_center, j, i])
        faces.append([high_center, count + i, count + j])
    return create_mesh_object(name, vertices, faces)


def loft_through_loops_y(
    name: str,
    loops,
    y_positions,
    center_x: float = 0.0,
    center_z: float = 0.0,
    cap_centers=None,
):
    if len(loops) != len(y_positions) or len(loops) < 2:
        raise ValueError("A loft needs matching loops/Y positions and two sections")
    loop_sizes = {len(loop) for loop in loops}
    if len(loop_sizes) == 1:
        count = len(loops[0])
        sampled_loops = [list(loop) for loop in loops]
    else:
        count = max(loop_sizes)
        sampled_loops = [resample_closed_loop(loop, count) for loop in loops]
    vertices = []
    for y, loop in zip(y_positions, sampled_loops):
        vertices.extend((x + center_x, y, z + center_z) for x, z in loop)

    def vertex(section, index):
        return section * count + index % count

    faces = []
    for section in range(len(sampled_loops) - 1):
        for index in range(count):
            next_index = index + 1
            faces.append(
                [
                    vertex(section, index),
                    vertex(section + 1, index),
                    vertex(section + 1, next_index),
                    vertex(section, next_index),
                ]
            )

    if cap_centers is None:
        low_cap_center = (0.0, 0.0)
        high_cap_center = (0.0, 0.0)
    else:
        low_cap_center, high_cap_center = cap_centers
    low_center = len(vertices)
    vertices.append(
        (
            low_cap_center[0] + center_x,
            y_positions[0],
            low_cap_center[1] + center_z,
        )
    )
    high_center = len(vertices)
    vertices.append(
        (
            high_cap_center[0] + center_x,
            y_positions[-1],
            high_cap_center[1] + center_z,
        )
    )
    last_section = len(sampled_loops) - 1
    for index in range(count):
        next_index = index + 1
        faces.append([low_center, vertex(0, index), vertex(0, next_index)])
        faces.append(
            [
                high_center,
                vertex(last_section, next_index),
                vertex(last_section, index),
            ]
        )
    return create_mesh_object(name, vertices, faces)


def create_back_dome():
    if not BACK_DOME_ENABLED:
        return None

    inner_loop = resample_closed_loop(
        rounded_rectangle_path_from_top(
            BACK_DOME_FAN_PAD_WIDTH,
            BACK_DOME_FAN_PAD_HEIGHT,
            0.0,
            CORNER_SEGMENTS,
        ),
        BACK_DOME_LOOP_POINTS,
    )
    inner_loop = [
        (x + FAN_CENTER_X, z + FAN_CENTER_Z) for x, z in inner_loop
    ]
    back_width, back_height, back_radius = effective_back_outer_dimensions()
    outer_loop = resample_closed_loop(
        rounded_rectangle_path_from_top(
            back_width,
            back_height,
            back_radius,
            CORNER_SEGMENTS,
        ),
        BACK_DOME_LOOP_POINTS,
    )

    vertices = []
    for section in range(BACK_DOME_SECTIONS + 1):
        radial_t = section / BACK_DOME_SECTIONS
        height_t = smoothstep(radial_t)
        y = back_exterior_y() + (
            dome_outer_transition_y()
            + BOOLEAN_OVERLAP
            - back_exterior_y()
        ) * height_t
        for inner_point, outer_point in zip(inner_loop, outer_loop):
            x = inner_point[0] + (outer_point[0] - inner_point[0]) * radial_t
            z = inner_point[1] + (outer_point[1] - inner_point[1]) * radial_t
            vertices.append((x, y, z))

    loop_count = BACK_DOME_LOOP_POINTS

    def vertex(section, index):
        return section * loop_count + index % loop_count

    faces = []
    for section in range(BACK_DOME_SECTIONS):
        for index in range(loop_count):
            next_index = index + 1
            faces.append(
                [
                    vertex(section, index),
                    vertex(section + 1, index),
                    vertex(section + 1, next_index),
                    vertex(section, next_index),
                ]
            )

    inner_center = len(vertices)
    vertices.append((FAN_CENTER_X, back_exterior_y(), FAN_CENTER_Z))
    outer_center = len(vertices)
    vertices.append((0.0, dome_outer_transition_y() + BOOLEAN_OVERLAP, 0.0))
    last_section = BACK_DOME_SECTIONS
    for index in range(loop_count):
        next_index = index + 1
        faces.append([inner_center, vertex(0, next_index), vertex(0, index)])
        faces.append(
            [
                outer_center,
                vertex(last_section, index),
                vertex(last_section, next_index),
            ]
        )
    return create_mesh_object("Rear_Exterior_Dome", vertices, faces)


def create_back_dome_cavity(
    socket_radius: float,
    inner_surface_offset_y: float = 0.0,
    name: str = "Rear_Domed_Socket_Cavity",
):
    inner_loop = resample_closed_loop(
        rounded_rectangle_path_from_top(
            BACK_DOME_FAN_PAD_WIDTH,
            BACK_DOME_FAN_PAD_HEIGHT,
            0.0,
            CORNER_SEGMENTS,
        ),
        BACK_DOME_LOOP_POINTS,
    )
    inner_loop = [
        (x + FAN_CENTER_X, z + FAN_CENTER_Z) for x, z in inner_loop
    ]
    socket_loop = resample_closed_loop(
        rounded_rectangle_path_from_top(
            socket_width(),
            socket_height(),
            socket_radius,
            CORNER_SEGMENTS,
        ),
        BACK_DOME_LOOP_POINTS,
    )

    section_loops = []
    y_positions = []
    inner_surface_y = fan_pad_inner_y() + inner_surface_offset_y
    outer_surface_y = dome_inner_transition_y() + inner_surface_offset_y
    for section in range(BACK_DOME_SECTIONS + 1):
        radial_t = section / BACK_DOME_SECTIONS
        height_t = smoothstep(radial_t)
        section_loops.append(
            [
                (
                    inner_point[0]
                    + (socket_point[0] - inner_point[0]) * radial_t,
                    inner_point[1]
                    + (socket_point[1] - inner_point[1]) * radial_t,
                )
                for inner_point, socket_point in zip(inner_loop, socket_loop)
            ]
        )
        y_positions.append(
            inner_surface_y
            + (outer_surface_y - inner_surface_y) * height_t
        )
    section_loops.append(socket_loop)
    y_positions.append(BACK_DEPTH + BOOLEAN_OVERLAP)

    vertices = []
    for y, loop in zip(y_positions, section_loops):
        vertices.extend((x, y, z) for x, z in loop)

    loop_count = BACK_DOME_LOOP_POINTS

    def vertex(section, index):
        return section * loop_count + index % loop_count

    faces = []
    for section in range(len(section_loops) - 1):
        for index in range(loop_count):
            next_index = index + 1
            faces.append(
                [
                    vertex(section, index),
                    vertex(section + 1, index),
                    vertex(section + 1, next_index),
                    vertex(section, next_index),
                ]
            )

    inner_center = len(vertices)
    vertices.append(
        (
            FAN_CENTER_X,
            inner_surface_y,
            FAN_CENTER_Z,
        )
    )
    front_center = len(vertices)
    vertices.append((0.0, BACK_DEPTH + BOOLEAN_OVERLAP, 0.0))
    last_section = len(section_loops) - 1
    for index in range(loop_count):
        next_index = index + 1
        faces.append([inner_center, vertex(0, index), vertex(0, next_index)])
        faces.append(
            [
                front_center,
                vertex(last_section, next_index),
                vertex(last_section, index),
            ]
        )
    return create_mesh_object(name, vertices, faces)


def create_insert_tube():
    sections = []
    if SLEEVE_CAPTURE_SLOT_ENABLED:
        # The added groove engagement is a straight continuation of the
        # configured front contour.  Keep the original taper's t=0 section at
        # the screw-boss datum so changing INSERT_REAR_* cannot change socket
        # or groove fit there.
        sections.append((insert_sleeve_leading_y(), 0.0))
    sections.extend(
        (
            insert_start_y() + INSERT_DEPTH * section / INSERT_DEPTH_SECTIONS,
            section / INSERT_DEPTH_SECTIONS,
        )
        for section in range(INSERT_DEPTH_SECTIONS + 1)
    )

    outer_loops = []
    inner_loops = []
    for _y, t in sections:
        width, height = insert_outer_dimensions_at_t(t)
        outer_loops.append(
            rounded_rectangle_loop(width, height, INSERT_OUTER_CORNER_RADIUS)
        )
        inner_radius = resolved_insert_inner_corner_radius()
        inner_loops.append(
            rounded_rectangle_loop(
                insert_inner_width(),
                insert_inner_height(),
                inner_radius,
            )
        )

    loop_count = len(outer_loops[0])
    vertices = []
    for (y, _t), outer_loop, inner_loop in zip(
        sections,
        outer_loops,
        inner_loops,
    ):
        vertices.extend((x, y, z) for x, z in outer_loop)
        vertices.extend((x, y, z) for x, z in inner_loop)

    stride = loop_count * 2

    def outer(section, index):
        return section * stride + index % loop_count

    def inner(section, index):
        return section * stride + loop_count + index % loop_count

    faces = []
    for section in range(len(sections) - 1):
        for i in range(loop_count):
            j = i + 1
            faces.append(
                [outer(section, i), outer(section + 1, i), outer(section + 1, j), outer(section, j)]
            )
            faces.append(
                [inner(section, j), inner(section + 1, j), inner(section + 1, i), inner(section, i)]
            )

    last = len(sections) - 1
    for i in range(loop_count):
        j = i + 1
        faces.append([outer(0, j), outer(0, i), inner(0, i), inner(0, j)])
        faces.append(
            [outer(last, i), outer(last, j), inner(last, j), inner(last, i)]
        )
    return create_mesh_object("Insert_Frame", vertices, faces)


def add_box(name: str, dimensions, location, rotation=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.rotation_euler = rotation
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    return obj


def add_beveled_box(
    name: str,
    dimensions,
    location,
    bevel: float,
    rotation=(0.0, 0.0, 0.0),
):
    obj = add_box(name, dimensions, location, rotation=rotation)
    modifier = obj.modifiers.new(name + "_Bevel", "BEVEL")
    modifier.width = min(bevel, min(dimensions) / 2.1)
    modifier.segments = 3
    modifier.affect = "EDGES"
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    recalc_normals(obj)
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


def add_cylinder_x(name: str, radius: float, x0: float, x1: float, y=0.0, z=0.0):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=CYLINDER_SEGMENTS,
        radius=radius,
        depth=x1 - x0,
        location=((x0 + x1) / 2.0, y, z),
        rotation=(0.0, math.pi / 2.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
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


def mesh_volume(obj) -> float:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    volume = abs(bm.calc_volume(signed=True)) if bm.faces else 0.0
    bm.free()
    return volume


def mesh_intersection_volume(first, second, label: str) -> float:
    """Measure an exact Boolean intersection without changing source objects."""
    first_copy = first.copy()
    first_copy.data = first.data.copy()
    bpy.context.collection.objects.link(first_copy)
    second_copy = second.copy()
    second_copy.data = second.data.copy()
    bpy.context.collection.objects.link(second_copy)
    first_name = first_copy.name
    second_name = second_copy.name
    try:
        apply_boolean(
            first_copy,
            second_copy,
            "INTERSECT",
            label,
            solver=BOOLEAN_SOLVER,
        )
        return mesh_volume(first_copy)
    finally:
        for object_name in (first_name, second_name):
            temporary = bpy.data.objects.get(object_name)
            if temporary is not None:
                bpy.data.objects.remove(temporary, do_unlink=True)


def available_boolean_solvers(modifier):
    if not hasattr(modifier, "solver"):
        return set()
    return {
        item.identifier
        for item in modifier.bl_rna.properties["solver"].enum_items
    }


def resolve_boolean_solver(modifier, requested: str, label: str):
    available = available_boolean_solvers(modifier)
    if not available or requested in available:
        return requested if available else None
    if requested == "MANIFOLD" and "EXACT" in available:
        print(
            f"BOOLEAN_SOLVER_FALLBACK {label}: "
            "MANIFOLD unavailable; using EXACT"
        )
        return "EXACT"
    raise ValueError(
        f"Boolean solver {requested!r} is unavailable for {label}; "
        f"available={sorted(available)}"
    )


def apply_boolean(
    base,
    tool,
    operation: str,
    label: str,
    solver=None,
    require_geometry_change=False,
):
    select_only(base)
    modifier = base.modifiers.new(label, "BOOLEAN")
    modifier.operation = operation
    modifier.object = tool
    requested_solver = solver or BOOLEAN_SOLVER
    resolved_solver = resolve_boolean_solver(modifier, requested_solver, label)
    if resolved_solver is not None:
        modifier.solver = resolved_solver
    if hasattr(modifier, "use_self"):
        modifier.use_self = False
    if resolved_solver == "MANIFOLD":
        base_non_manifold = non_manifold_edge_count(base)
        tool_non_manifold = non_manifold_edge_count(tool)
        if base_non_manifold or tool_non_manifold:
            raise RuntimeError(
                f"Manifold Boolean {label} requires manifold operands; "
                f"base={base_non_manifold} tool={tool_non_manifold}"
            )
    before_volume = mesh_volume(base) if require_geometry_change else None
    modifier_name = modifier.name
    result = bpy.ops.object.modifier_apply(modifier=modifier_name)
    if "FINISHED" not in result or base.modifiers.get(modifier_name) is not None:
        raise RuntimeError(
            f"Boolean {label} did not apply: operation={operation} "
            f"solver={resolved_solver or 'legacy'} result={result}"
        )
    bpy.data.objects.remove(tool, do_unlink=True)
    cleanup_boolean_mesh(base)
    recalc_normals(base)
    if resolved_solver == "MANIFOLD":
        result_non_manifold = non_manifold_edge_count(base)
        if result_non_manifold:
            raise RuntimeError(
                f"Manifold Boolean {label} produced "
                f"{result_non_manifold} non-manifold edges"
            )
    if require_geometry_change:
        after_volume = mesh_volume(base)
        if abs(after_volume - before_volume) <= BOOLEAN_MINIMUM_VOLUME_CHANGE:
            raise RuntimeError(
                f"Boolean {label} made no measurable volume change; "
                f"before={before_volume:.9f} after={after_volume:.9f}"
            )
    return base


def boolean_union(
    base,
    part,
    label="Union",
    solver=None,
    require_geometry_change=False,
):
    return apply_boolean(
        base,
        part,
        "UNION",
        label + "_" + part.name,
        solver=solver,
        require_geometry_change=require_geometry_change,
    )


def boolean_difference(base, tools, label="Cut"):
    tool = join_disconnected_tools(label + "_Tools", list(tools))
    return apply_boolean(base, tool, "DIFFERENCE", label)


# ---------------------------------------------------------------------------
# Rear fan/socket shell


def fan_hole_positions():
    return [
        (
            FAN_CENTER_X + sx * FAN_HOLE_SPACING_X / 2.0,
            FAN_CENTER_Z + sz * FAN_HOLE_SPACING_Z / 2.0,
        )
        for sx in (-1.0, 1.0)
        for sz in (-1.0, 1.0)
    ]


def create_snap_pocket_cutters():
    if not SNAP_ENABLED:
        return []
    pocket_depth_x = SNAP_BUMP_PROTRUSION + SNAP_POCKET_CLEARANCE
    pocket_length_y = SNAP_BUMP_LENGTH_Y + 2.0 * SNAP_POCKET_CLEARANCE
    pocket_length_z = SNAP_BUMP_LENGTH_Z + 2.0 * SNAP_POCKET_CLEARANCE
    y = insert_start_y() + SNAP_BUMP_Y_OFFSET + SNAP_BUMP_LENGTH_Y / 2.0
    cutters = []
    for side in (-1.0, 1.0):
        x = side * (socket_width() / 2.0 + pocket_depth_x / 2.0 - BOOLEAN_OVERLAP)
        cutters.append(
            add_beveled_box(
                f"Snap_Pocket_{'Left' if side < 0 else 'Right'}",
                (pocket_depth_x + BOOLEAN_OVERLAP, pocket_length_y, pocket_length_z),
                (x, y, 0.0),
                SNAP_EDGE_RADIUS + SNAP_POCKET_CLEARANCE,
            )
        )
    return cutters


def create_insert_boss_socket_cutter(index: int, x: float, z: float):
    socket_radius = (
        INSERT_FASTENER_BOSS_DIAMETER / 2.0
        + FASTENER_BOSS_SOCKET_CLEARANCE
    )
    if BACK_FASTENER_TO_INSERT_SOCKET_GAP > BOOLEAN_CLEANUP_DISTANCE:
        return add_cylinder_y(
            f"Insert_Boss_Socket_{index}",
            socket_radius,
            insert_start_y(),
            BACK_DEPTH + BOOLEAN_OVERLAP,
            x=x,
            z=z,
        )

    # At zero gap the larger rear boss reaches the socket's start plane. Keep
    # the same straight socket cylinder used for positive gaps, and union a
    # short wider trimming section onto its start. The rear boss is extended
    # into this section during construction and trimmed back to exact contact.
    trim_radius = max(
        socket_radius,
        BACK_FASTENER_BOSS_DIAMETER / 2.0
        + 10.0 * BOOLEAN_CLEANUP_DISTANCE,
    )
    socket = add_cylinder_y(
        f"Insert_Boss_Socket_{index}",
        socket_radius,
        insert_start_y(),
        BACK_DEPTH + BOOLEAN_OVERLAP,
        x=x,
        z=z,
    )
    trim = add_cylinder_y(
        f"Insert_Boss_Socket_Lead_In_{index}",
        trim_radius,
        insert_start_y(),
        insert_start_y() + 2.0 * BOOLEAN_OVERLAP,
        x=x,
        z=z,
    )
    boolean_union(socket, trim, "Insert_Boss_Socket_Lead_In_Union")
    return socket


def create_camera_stop_back_volume(socket_radius: float):
    if BACK_DOME_ENABLED:
        return create_back_dome_cavity(
            socket_radius,
            inner_surface_offset_y=-BOOLEAN_OVERLAP,
            name="Camera_Stop_Back_Volume",
        )
    return rounded_rectangle_prism_y(
        "Camera_Stop_Back_Volume",
        socket_width(),
        socket_height(),
        socket_radius,
        BACK_FACE_THICKNESS - BOOLEAN_OVERLAP,
        BACK_DEPTH + BOOLEAN_OVERLAP,
    )


def create_camera_stops(back_volume):
    if not CAMERA_STOPS_ENABLED:
        return None
    stops = []
    for spec in CAMERA_STOP_SPECS:
        name, x0, x1, z0, z1, attachment = spec
        y0 = back_exterior_y() - BOOLEAN_OVERLAP
        y1 = camera_stop_end_y()

        # Extend only away from the camera opening so the measured inward
        # stop face is unchanged while the stop remains joined to the shell.
        if attachment == "top":
            z1 = max(z1, socket_height() / 2.0 + BOOLEAN_OVERLAP)
        elif attachment == "bottom":
            z0 = min(z0, -socket_height() / 2.0 - BOOLEAN_OVERLAP)
        elif attachment == "left":
            x0 = min(x0, -socket_width() / 2.0 - BOOLEAN_OVERLAP)
        elif attachment == "right":
            x1 = max(x1, socket_width() / 2.0 + BOOLEAN_OVERLAP)

        stops.append(
            add_box(
                f"Camera_Stop_{name}",
                (x1 - x0, y1 - y0, z1 - z0),
                ((x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0),
            )
        )
    stop_group = join_disconnected_tools("Camera_Stop_Group", stops)
    apply_boolean(
        stop_group,
        back_volume,
        "INTERSECT",
        "Camera_Stop_Back_Clip",
    )
    return stop_group


def clear_camera_stop_fastener_access(camera_stops):
    if camera_stops is None:
        return None
    cutters = []
    y1 = insert_start_y() + BOOLEAN_OVERLAP
    if CAMERA_STOP_CLEAR_FAN_BOSSES and FAN_HOLE_BOSSES_ENABLED:
        radius = FAN_HOLE_BOSS_DIAMETER / 2.0 + CAMERA_STOP_FASTENER_CLEARANCE
        fan_y0 = back_exterior_y() - BOOLEAN_OVERLAP
        for index, (x, z) in enumerate(fan_hole_positions(), start=1):
            cutters.append(
                add_cylinder_y(
                    f"Camera_Stop_Fan_Access_{index}",
                    radius,
                    fan_y0,
                    y1,
                    x=x,
                    z=z,
                )
            )
    if CASE_FASTENERS_ENABLED:
        if CAMERA_STOP_CLEAR_CASE_BOSSES:
            radius = (
                BACK_FASTENER_BOSS_DIAMETER / 2.0
                + CAMERA_STOP_FASTENER_CLEARANCE
            )
        else:
            radius = (
                BACK_FASTENER_BOSS_DIAMETER / 2.0
                + 10.0 * BOOLEAN_CLEANUP_DISTANCE
            )
        case_y0 = back_exterior_y() - BOOLEAN_OVERLAP
        for index, (x, z) in enumerate(CASE_FASTENER_POSITIONS_XZ, start=1):
            cutters.append(
                add_cylinder_y(
                    f"Camera_Stop_Case_Access_{index}",
                    radius,
                    case_y0,
                    y1,
                    x=x,
                    z=z,
                )
            )
    if cutters:
        boolean_difference(
            camera_stops,
            cutters,
            "Camera_Stop_Fastener_Access",
        )
    remove_tiny_mesh_components(camera_stops)
    return camera_stops


def back_fastener_hex_loop():
    half_width = BACK_FASTENER_HEX_WIDTH_X / 2.0
    half_height = BACK_FASTENER_HEX_HEIGHT_Z / 2.0
    return [
        (half_width, 0.0),
        (half_width / 2.0, half_height),
        (-half_width / 2.0, half_height),
        (-half_width, 0.0),
        (-half_width / 2.0, -half_height),
        (half_width / 2.0, -half_height),
    ]


def create_back_fastener_opening_cutters(index, x, z):
    if not BACK_FASTENER_HEX_RETENTION_ENABLED:
        return [
            add_cylinder_y(
                f"Rear_Fastener_Hole_{index}",
                BACK_FASTENER_HOLE_DIAMETER / 2.0,
                back_exterior_y() - 2.0 * BOOLEAN_OVERLAP,
                BACK_DEPTH + BOOLEAN_OVERLAP,
                x=x,
                z=z,
            )
        ]

    hex_loop = back_fastener_hex_loop()
    circle_loop = [
        (
            BACK_FASTENER_HOLE_DIAMETER / 2.0 * math.cos(2.0 * math.pi * i / CYLINDER_SEGMENTS),
            BACK_FASTENER_HOLE_DIAMETER / 2.0 * math.sin(2.0 * math.pi * i / CYLINDER_SEGMENTS),
        )
        for i in range(CYLINDER_SEGMENTS)
    ]
    seat_y = back_fastener_hex_seat_y()
    bore_start_y = back_fastener_bore_start_y()
    return [
        loft_through_loops_y(
            f"Rear_Fastener_Hex_And_Bore_{index}",
            (hex_loop, hex_loop, circle_loop, circle_loop),
            (
                back_exterior_y() - 2.0 * BOOLEAN_OVERLAP,
                seat_y,
                bore_start_y,
                BACK_DEPTH + BOOLEAN_OVERLAP,
            ),
            center_x=x,
            center_z=z,
        )
    ]


def add_back_fastener_retention_tabs(back):
    if not (
        CASE_FASTENERS_ENABLED
        and BACK_FASTENER_HEX_RETENTION_ENABLED
        and BACK_FASTENER_RETENTION_TABS_ENABLED
    ):
        return back

    center_y = back_fastener_retention_tab_center_y()
    half_hex_height = BACK_FASTENER_HEX_HEIGHT_Z / 2.0
    tab_height = BACK_FASTENER_RETENTION_TAB_PROTRUSION + BOOLEAN_OVERLAP
    for fastener_index, (x, z) in enumerate(CASE_FASTENER_POSITIONS_XZ, start=1):
        for side in (-1.0, 1.0):
            tab = add_beveled_box(
                f"Rear_Fastener_Retention_Tab_{fastener_index}_{'Top' if side > 0 else 'Bottom'}",
                (
                    BACK_FASTENER_RETENTION_TAB_WIDTH_X,
                    BACK_FASTENER_RETENTION_TAB_DEPTH_Y,
                    tab_height,
                ),
                (
                    x,
                    center_y,
                    z
                    + side
                    * (
                        half_hex_height
                        - BACK_FASTENER_RETENTION_TAB_PROTRUSION / 2.0
                        + BOOLEAN_OVERLAP / 2.0
                    ),
                ),
                BACK_FASTENER_RETENTION_TAB_BEVEL,
            )
            boolean_union(
                back,
                tab,
                f"Rear_Fastener_Retention_Tab_{fastener_index}_Union",
                solver=WATERTIGHT_DETAIL_UNION_SOLVER,
                require_geometry_change=True,
            )
    return back


def add_sleeve_capture_ledge(back):
    if not SLEEVE_CAPTURE_SLOT_ENABLED:
        return back
    support_width, support_height, support_radius = (
        sleeve_capture_outer_support_dimensions()
    )
    opening_width, opening_height, opening_radius = (
        sleeve_capture_opening_dimensions()
    )
    ledge = rounded_rectangle_ring_prism_y(
        "Sleeve_Capture_Ledge",
        support_width,
        support_height,
        support_radius,
        opening_width,
        opening_height,
        opening_radius,
        sleeve_capture_ledge_start_y(),
        insert_start_y() + BOOLEAN_OVERLAP,
    )
    return boolean_union(
        back,
        ledge,
        "Sleeve_Capture_Ledge_Union",
        solver=WATERTIGHT_DETAIL_UNION_SOLVER,
        require_geometry_change=True,
    )


def cut_sleeve_capture_groove(back):
    if not SLEEVE_CAPTURE_SLOT_ENABLED:
        return back
    groove_outer_width, groove_outer_height, groove_outer_radius = (
        sleeve_capture_groove_outer_dimensions()
    )
    groove_inner_width, groove_inner_height, groove_inner_radius = (
        sleeve_capture_groove_inner_dimensions()
    )
    cutter = rounded_rectangle_ring_prism_y(
        "Sleeve_Capture_Groove_Cutter",
        groove_outer_width,
        groove_outer_height,
        groove_outer_radius,
        groove_inner_width,
        groove_inner_height,
        groove_inner_radius,
        sleeve_capture_groove_floor_y(),
        insert_start_y() + 2.0 * BOOLEAN_OVERLAP,
    )
    apply_boolean(
        back,
        cutter,
        "DIFFERENCE",
        "Sleeve_Capture_Groove",
        solver=WATERTIGHT_DETAIL_UNION_SOLVER,
        require_geometry_change=True,
    )
    cleanup_opposing_triangle_pairs(back, "Sleeve_Capture_Groove")
    return back


def add_baffle_snap_receivers(back):
    if not BAFFLE_CARTRIDGE_ENABLED:
        return back
    half_height = dome_cavity_half_height_at_y(BAFFLE_SNAP_RECEIVER_Y)
    receiver_height = (
        BAFFLE_SNAP_RECEIVER_PROJECTION_Z + BOOLEAN_OVERLAP
    )
    for side in (-1.0, 1.0):
        receiver = add_beveled_box(
            f"Baffle_Snap_Receiver_{'Top' if side > 0 else 'Bottom'}",
            (
                BAFFLE_SNAP_RECEIVER_WIDTH_X,
                BAFFLE_SNAP_RECEIVER_DEPTH_Y,
                receiver_height,
            ),
            (
                baffle_snap_auxiliary_center_x_at_y(
                    BAFFLE_SNAP_RECEIVER_Y,
                    BAFFLE_SNAP_RECEIVER_DEPTH_Y
                    + 2.0 * baffle_boolean_join_overlap(),
                ),
                BAFFLE_SNAP_RECEIVER_Y,
                side
                * (
                    half_height
                    - BAFFLE_SNAP_RECEIVER_PROJECTION_Z / 2.0
                    + BOOLEAN_OVERLAP / 2.0
                ),
            ),
            BAFFLE_SNAP_RECEIVER_BEVEL,
        )
        boolean_union(
            back,
            receiver,
            f"Baffle_Snap_Receiver_{'Top' if side > 0 else 'Bottom'}_Union",
            solver=WATERTIGHT_DETAIL_UNION_SOLVER,
            require_geometry_change=True,
        )
    return back


def create_back_shell():
    back_width, back_height, back_radius = effective_back_outer_dimensions()
    back = rounded_rectangle_prism_y(
        "Rear_Fan_Shell",
        back_width,
        back_height,
        back_radius,
        rear_shell_start_y(),
        BACK_DEPTH,
    )
    dome = create_back_dome()
    if dome is not None:
        boolean_union(back, dome, "Rear_Dome_Union")
    socket_radius = socket_corner_radius()
    if BACK_DOME_ENABLED:
        cavity = create_back_dome_cavity(socket_radius)
    else:
        cavity = rounded_rectangle_prism_y(
            "Rear_Socket_Cavity",
            socket_width(),
            socket_height(),
            socket_radius,
            BACK_FACE_THICKNESS,
            BACK_DEPTH + BOOLEAN_OVERLAP,
        )
    camera_stop_back_volume = (
        create_camera_stop_back_volume(socket_radius)
        if CAMERA_STOPS_ENABLED
        else None
    )
    boolean_difference(back, [cavity], "Rear_Socket")
    add_sleeve_capture_ledge(back)
    camera_stops = create_camera_stops(camera_stop_back_volume)
    clear_camera_stop_fastener_access(camera_stops)

    if CASE_FASTENERS_ENABLED:
        back_fastener_bosses = []
        boss_construction_end_y = back_fastener_end_y()
        if BACK_FASTENER_TO_INSERT_SOCKET_GAP <= BOOLEAN_CLEANUP_DISTANCE:
            boss_construction_end_y += BOOLEAN_OVERLAP
        for index, (x, z) in enumerate(CASE_FASTENER_POSITIONS_XZ, start=1):
            back_fastener_bosses.append(
                add_cylinder_y(
                    f"Rear_Fastener_Boss_{index}",
                    BACK_FASTENER_BOSS_DIAMETER / 2.0,
                    back_fastener_boss_start_y(x, z) - BOOLEAN_OVERLAP,
                    boss_construction_end_y,
                    x=x,
                    z=z,
                )
            )
        back_fastener_boss_group = join_disconnected_tools(
            "Rear_Fastener_Boss_Group",
            back_fastener_bosses,
        )
        boolean_union(back, back_fastener_boss_group, "Rear_Fastener_Bosses_Union")

    cuts = []
    insert_boss_socket_cutters = []
    if FAN_OPENING_ENABLED:
        cuts.append(
            add_cylinder_y(
                "Fan_Opening",
                FAN_OPENING_DIAMETER / 2.0,
                back_exterior_y() - BOOLEAN_OVERLAP,
                fan_pad_inner_y() + BOOLEAN_OVERLAP,
                x=FAN_CENTER_X,
                z=FAN_CENTER_Z,
            )
        )
        for index, (x, z) in enumerate(fan_hole_positions(), start=1):
            cuts.append(
                add_cylinder_y(
                    f"Fan_Hole_{index}",
                    FAN_HOLE_DIAMETER / 2.0,
                    back_exterior_y() - BOOLEAN_OVERLAP,
                    fan_boss_end_y() + BOOLEAN_OVERLAP,
                    x=x,
                    z=z,
                )
            )

    if VENT_ENABLED:
        cuts.append(
            rounded_rectangle_prism_y(
                "Vent_Opening",
                VENT_WIDTH,
                VENT_HEIGHT,
                VENT_CORNER_RADIUS,
                back_exterior_y() - BOOLEAN_OVERLAP,
                BACK_FACE_THICKNESS + BOOLEAN_OVERLAP,
                center_x=VENT_CENTER_X,
                center_z=VENT_CENTER_Z,
            )
        )

    if CASE_FASTENERS_ENABLED:
        for index, (x, z) in enumerate(CASE_FASTENER_POSITIONS_XZ, start=1):
            cuts.extend(create_back_fastener_opening_cutters(index, x, z))
            insert_boss_socket_cutters.append(
                create_insert_boss_socket_cutter(index, x, z)
            )
    cuts.extend(create_snap_pocket_cutters())
    if cuts:
        boolean_difference(back, cuts, "Rear_Openings")
    if insert_boss_socket_cutters:
        boolean_difference(
            back,
            insert_boss_socket_cutters,
            "Insert_Boss_Sockets",
        )

    add_back_fastener_retention_tabs(back)

    if VENT_ENABLED and VENT_SLAT_COUNT > 0:
        slat_length = VENT_WIDTH * 1.65
        spacing = VENT_HEIGHT / (VENT_SLAT_COUNT + 1)
        vent_surface_y = dome_surface_y_approx(VENT_CENTER_X, VENT_CENTER_Z)
        for index in range(VENT_SLAT_COUNT):
            z = VENT_CENTER_Z + (index - (VENT_SLAT_COUNT - 1) / 2.0) * spacing
            slat = add_box(
                f"Vent_Slat_{index + 1}",
                (slat_length, BACK_FACE_THICKNESS, VENT_SLAT_WIDTH),
                (
                    VENT_CENTER_X,
                    vent_surface_y + BACK_FACE_THICKNESS / 2.0,
                    z,
                ),
                rotation=(0.0, math.radians(VENT_SLAT_ANGLE_DEG), 0.0),
            )
            boolean_union(back, slat, "Vent_Slat_Union")

    if camera_stops is not None:
        boolean_union(
            back,
            camera_stops,
            "Camera_Stops_Union",
            solver=WATERTIGHT_DETAIL_UNION_SOLVER,
            require_geometry_change=True,
        )
        remove_tiny_mesh_components(back)

    # Build short fan bosses with their bores already present. Reopening a
    # 1 mm solid boss with a second boolean can leave non-manifold edge fans.
    if FAN_HOLE_BOSSES_ENABLED:
        fan_bosses = []
        for index, (x, z) in enumerate(fan_hole_positions(), start=1):
            if FAN_OPENING_ENABLED:
                fan_bosses.append(
                    annular_cylinder_y(
                        f"Fan_Boss_{index}",
                        FAN_HOLE_BOSS_DIAMETER / 2.0,
                        FAN_HOLE_DIAMETER / 2.0,
                        fan_pad_inner_y() - BOOLEAN_OVERLAP,
                        fan_boss_end_y(),
                        x=x,
                        z=z,
                    )
                )
            else:
                fan_bosses.append(
                    add_cylinder_y(
                        f"Fan_Boss_{index}",
                        FAN_HOLE_BOSS_DIAMETER / 2.0,
                        fan_pad_inner_y() - BOOLEAN_OVERLAP,
                        fan_boss_end_y(),
                        x=x,
                        z=z,
                    )
                )
        fan_boss_group = join_disconnected_tools("Fan_Boss_Group", fan_bosses)
        boolean_union(
            back,
            fan_boss_group,
            "Fan_Bosses_Union",
            solver=WATERTIGHT_DETAIL_UNION_SOLVER,
            require_geometry_change=True,
        )

    add_baffle_snap_receivers(back)

    # Cut last so later camera-stop and boss unions cannot bridge any portion
    # of the continuous four-sided groove.
    cut_sleeve_capture_groove(back)

    back.name = "GoPro_Fan_Case_Back"
    back.data.name = "GoPro_Fan_Case_Back_Mesh"
    return back


# ---------------------------------------------------------------------------
# Removable fan acoustic baffle cartridge


def baffle_shell_sections(inner=False):
    wall = BAFFLE_WALL_THICKNESS
    if inner:
        start_y = BAFFLE_REAR_Y + wall
        end_y = BAFFLE_FRONT_Y - wall
        loop_at_y = baffle_inner_loop_at_y
    else:
        start_y = BAFFLE_REAR_Y
        end_y = BAFFLE_FRONT_Y
        loop_at_y = baffle_outer_loop_at_y
    return tuple(
        (
            start_y
            + (end_y - start_y) * section / BAFFLE_BODY_DEPTH_SECTIONS,
            loop_at_y(
                start_y
                + (end_y - start_y)
                * section
                / BAFFLE_BODY_DEPTH_SECTIONS
            ),
        )
        for section in range(BAFFLE_BODY_DEPTH_SECTIONS + 1)
    )


def create_baffle_side_opening_cutter():
    loops = []
    y_positions = []
    cut_margin = max(1.5, 2.0 * BOOLEAN_OVERLAP)
    for section in range(BAFFLE_BODY_DEPTH_SECTIONS + 1):
        y = (
            BAFFLE_REAR_Y
            + (BAFFLE_FRONT_Y - BAFFLE_REAR_Y)
            * section
            / BAFFLE_BODY_DEPTH_SECTIONS
        )
        _left, right, bottom, top = baffle_body_bounds_at_y(y)
        cutter_left = baffle_tray_side_opening_x_at_y(y)
        loops.append(
            [
                (cutter_left, bottom - cut_margin),
                (right + cut_margin, bottom - cut_margin),
                (right + cut_margin, top + cut_margin),
                (cutter_left, top + cut_margin),
            ]
        )
        if section == 0:
            y -= cut_margin
        elif section == BAFFLE_BODY_DEPTH_SECTIONS:
            y += cut_margin
        y_positions.append(y)
    return loft_through_loops_y(
        "Baffle_Tray_Side_Opening",
        loops,
        y_positions,
        cap_centers=tuple(
            (
                sum(point[0] for point in loop) / len(loop),
                sum(point[1] for point in loop) / len(loop),
            )
            for loop in (loops[0], loops[-1])
        ),
    )


def baffle_boolean_join_overlap() -> float:
    """Return a bevel-safe overlap for the cartridge's Boolean joints."""
    return max(0.45, 5.0 * BOOLEAN_OVERLAP)


def baffle_lid_key_inner_x_at_y(y: float) -> float:
    """Return the airway-facing surface of the lid's shallow locating key."""
    right = baffle_body_bounds_at_y(y)[1]
    return right - BAFFLE_WALL_THICKNESS - BAFFLE_LID_KEY_DEPTH_X


def baffle_tray_side_opening_x_at_y(y: float) -> float:
    """Return the open edge shared by the tray wall and internal blockers."""
    return baffle_lid_key_inner_x_at_y(y) - BAFFLE_LID_FIT_CLEARANCE


def baffle_second_end_frame_center_y() -> float:
    """Return the frame center, shifted rearward to keep its lid pocket blind."""
    return BAFFLE_SECOND_Y - BAFFLE_SECOND_END_FRAME_REAR_SHIFT_Y


def baffle_second_end_frame_y_bounds(clearance: float = 0.0):
    half_depth = BAFFLE_SECOND_END_FRAME_DEPTH_Y / 2.0 + clearance
    center_y = baffle_second_end_frame_center_y()
    return center_y - half_depth, center_y + half_depth


def create_baffle_second_end_frame_piece(
    name: str,
    inner_extension_x: float,
    bottom_z: float,
    top_z: float,
):
    """Loft one tapered piece of the camera-side tray end frame."""
    y_positions = baffle_second_end_frame_y_bounds()
    loops = []
    for y in y_positions:
        lid_key_inner_x = baffle_lid_key_inner_x_at_y(y)
        loops.append(
            [
                (lid_key_inner_x - inner_extension_x, bottom_z),
                (
                    lid_key_inner_x
                    + BAFFLE_SECOND_END_FRAME_LID_ENGAGEMENT_X,
                    bottom_z,
                ),
                (
                    lid_key_inner_x
                    + BAFFLE_SECOND_END_FRAME_LID_ENGAGEMENT_X,
                    top_z,
                ),
                (lid_key_inner_x - inner_extension_x, top_z),
            ]
        )
    return loft_through_loops_y(
        name,
        loops,
        y_positions,
        cap_centers=tuple(
            (
                sum(point[0] for point in loop) / len(loop),
                sum(point[1] for point in loop) / len(loop),
            )
            for loop in loops
        ),
    )


def add_baffle_second_end_frame(tray):
    """Add robust lid-captured returns to both camera-side baffle ends."""
    _left, _right, bottom, top = baffle_body_bounds_at_y(BAFFLE_SECOND_Y)
    half_opening = BAFFLE_SECOND_OPENING_HEIGHT_Z / 2.0
    join_overlap = baffle_boolean_join_overlap()
    pieces = (
        create_baffle_second_end_frame_piece(
            "Baffle_Second_End_Frame_Top_Connection",
            BAFFLE_SECOND_END_FRAME_CONNECTION_X,
            half_opening - join_overlap,
            top,
        ),
        create_baffle_second_end_frame_piece(
            "Baffle_Second_End_Frame_Bottom_Connection",
            BAFFLE_SECOND_END_FRAME_CONNECTION_X,
            bottom,
            -half_opening + join_overlap,
        ),
    )
    for piece, operation in zip(
        pieces,
        (
            "Baffle_Second_End_Frame_Top_Union",
            "Baffle_Second_End_Frame_Bottom_Union",
        ),
    ):
        boolean_union(
            tray,
            piece,
            operation,
            solver=WATERTIGHT_DETAIL_UNION_SOLVER,
            require_geometry_change=True,
        )
    return tray


def baffle_outlet_cutter_rear_y() -> float:
    """Return the rear extent of the camera-facing outlet cutter."""
    return (
        BAFFLE_FRONT_Y
        - BAFFLE_WALL_THICKNESS
        - baffle_boolean_join_overlap()
        - BOOLEAN_OVERLAP
    )


def baffle_outlet_front_wall_side_band_widths():
    """Return the narrowest left/right bands in the solid outlet wall.

    The cavity is intentionally open behind this plane, so there is no
    structural web to measure at the outlet cutter's rear overlap. The tapered
    wall widens toward its exterior face, making its inner plane the limiting
    solid cross-section.
    """
    front_wall_inner_y = BAFFLE_FRONT_Y - BAFFLE_WALL_THICKNESS
    left, _right, _bottom, _top = baffle_body_bounds_at_y(front_wall_inner_y)
    half_outlet_width = BAFFLE_OUTLET_WIDTH / 2.0
    left_connection = (
        -half_outlet_width - (left + BAFFLE_WALL_THICKNESS)
    )
    right_connection = (
        baffle_tray_side_opening_x_at_y(front_wall_inner_y)
        - half_outlet_width
    )
    return left_connection, right_connection


def baffle_internal_member_x_bounds(center_y: float):
    """Keep an axial baffle inside the tapered side walls over its depth."""
    half_depth = BAFFLE_INTERNAL_THICKNESS_Y / 2.0
    low_bounds = baffle_body_bounds_at_y(center_y - half_depth)
    high_bounds = baffle_body_bounds_at_y(center_y + half_depth)
    wall_inset = BAFFLE_WALL_THICKNESS / 4.0
    left = max(low_bounds[0], high_bounds[0]) + wall_inset
    right = min(low_bounds[1], high_bounds[1]) - wall_inset
    if right <= left:
        raise ValueError("The tapered baffle has no printable X span")
    return left, right


def add_baffle_internal_members(tray):
    left, right = baffle_internal_member_x_bounds(BAFFLE_FIRST_Y)
    first = add_beveled_box(
        "Baffle_First_Center_Blocker",
        (
            right - left,
            BAFFLE_INTERNAL_THICKNESS_Y,
            BAFFLE_FIRST_BLOCKER_HEIGHT_Z,
        ),
        (
            (left + right) / 2.0,
            BAFFLE_FIRST_Y,
            0.0,
        ),
        min(BAFFLE_INTERNAL_THICKNESS_Y / 2.5, 0.70),
    )
    boolean_union(
        tray,
        first,
        "Baffle_First_Blocker_Union",
        solver=WATERTIGHT_DETAIL_UNION_SOLVER,
        require_geometry_change=True,
    )

    left, right = baffle_internal_member_x_bounds(BAFFLE_SECOND_Y)
    _outer_left, _outer_right, bottom, top = baffle_body_bounds_at_y(
        BAFFLE_SECOND_Y
    )
    half_opening = BAFFLE_SECOND_OPENING_HEIGHT_Z / 2.0
    top_member = add_beveled_box(
        "Baffle_Second_Top_Member",
        (
            right - left,
            BAFFLE_INTERNAL_THICKNESS_Y,
            top - half_opening + BOOLEAN_OVERLAP,
        ),
        (
            (left + right) / 2.0,
            BAFFLE_SECOND_Y,
            (top + half_opening) / 2.0,
        ),
        min(BAFFLE_INTERNAL_THICKNESS_Y / 2.5, 0.70),
    )
    boolean_union(
        tray,
        top_member,
        "Baffle_Second_Top_Union",
        solver=WATERTIGHT_DETAIL_UNION_SOLVER,
        require_geometry_change=True,
    )

    step_x, step_z = baffle_stop_relief_corner()
    bottom_loop = [
        (left, -half_opening),
        (right, -half_opening),
        (right, bottom + BAFFLE_WALL_THICKNESS / 4.0),
        (step_x + BAFFLE_WALL_THICKNESS / 4.0, bottom + BAFFLE_WALL_THICKNESS / 4.0),
        (step_x + BAFFLE_WALL_THICKNESS / 4.0, step_z + BAFFLE_WALL_THICKNESS / 4.0),
        (left, step_z + BAFFLE_WALL_THICKNESS / 4.0),
    ]
    bottom_member = polygon_prism_y(
        "Baffle_Second_Bottom_Member",
        bottom_loop,
        BAFFLE_SECOND_Y - BAFFLE_INTERNAL_THICKNESS_Y / 2.0,
        BAFFLE_SECOND_Y + BAFFLE_INTERNAL_THICKNESS_Y / 2.0,
    )
    boolean_union(
        tray,
        bottom_member,
        "Baffle_Second_Bottom_Union",
        solver=WATERTIGHT_DETAIL_UNION_SOLVER,
        require_geometry_change=True,
    )
    return tray


def add_baffle_tpu_lid_blocker_tab(tray):
    """Extend the flexible first blocker into its shallow lid-side slot."""
    if not baffle_gasket_is_integral():
        return tray

    half_y = BAFFLE_INTERNAL_THICKNESS_Y / 2.0
    half_z = BAFFLE_FIRST_BLOCKER_HEIGHT_Z / 2.0
    y_positions = (BAFFLE_FIRST_Y - half_y, BAFFLE_FIRST_Y + half_y)
    join_overlap = baffle_boolean_join_overlap()
    loops = []
    for y in y_positions:
        tray_edge_x = baffle_tray_side_opening_x_at_y(y)
        slot_entry_x = baffle_lid_key_inner_x_at_y(y)
        loops.append(
            [
                (tray_edge_x - join_overlap, -half_z),
                (
                    slot_entry_x
                    + BAFFLE_TPU_LID_BLOCKER_SLOT_ENGAGEMENT_X,
                    -half_z,
                ),
                (
                    slot_entry_x
                    + BAFFLE_TPU_LID_BLOCKER_SLOT_ENGAGEMENT_X,
                    half_z,
                ),
                (tray_edge_x - join_overlap, half_z),
            ]
        )
    tab = loft_through_loops_y(
        "Baffle_TPU_First_Blocker_Lid_Tab",
        loops,
        y_positions,
        cap_centers=tuple(
            (
                sum(point[0] for point in loop) / len(loop),
                sum(point[1] for point in loop) / len(loop),
            )
            for loop in loops
        ),
    )
    boolean_union(
        tray,
        tab,
        "Baffle_TPU_First_Blocker_Lid_Tab_Union",
        solver=WATERTIGHT_DETAIL_UNION_SOLVER,
        require_geometry_change=True,
    )
    return tray


def add_baffle_snap_tongues(component):
    root_y = BAFFLE_SNAP_TONGUE_ROOT_Y
    front_y = baffle_snap_tongue_front_y()
    # The tongue pieces are beveled independently before they are unioned.
    # A coincident or BOOLEAN_OVERLAP-sized joint can therefore be shaved
    # away at the bevel and survive the union as a disconnected shell. Bury
    # each piece far enough into its neighbours to leave a robust printable
    # neck after beveling and Boolean cleanup.
    join_overlap = baffle_boolean_join_overlap()
    for side in (-1.0, 1.0):
        arm_y_positions = (
            root_y - join_overlap,
            front_y + join_overlap,
        )
        arm_loops = []
        for y in arm_y_positions:
            center_x = baffle_snap_tongue_center_x_at_y(y)
            center_z = baffle_snap_tongue_center_z_at_y(y, side)
            half_width = BAFFLE_SNAP_TONGUE_WIDTH_X / 2.0
            half_thickness = BAFFLE_SNAP_TONGUE_THICKNESS_Z / 2.0
            arm_loops.append(
                [
                    (center_x - half_width, center_z + half_thickness),
                    (center_x + half_width, center_z + half_thickness),
                    (center_x + half_width, center_z - half_thickness),
                    (center_x - half_width, center_z - half_thickness),
                ]
            )
        arm = loft_through_loops_y(
            f"Baffle_Snap_Tongue_{'Top' if side > 0 else 'Bottom'}",
            tuple(arm_loops),
            arm_y_positions,
            cap_centers=tuple(
                (
                    sum(point[0] for point in loop) / len(loop),
                    sum(point[1] for point in loop) / len(loop),
                )
                for loop in arm_loops
            ),
        )

        root_z = baffle_snap_tongue_center_z_at_y(root_y, side)
        angle = baffle_snap_tongue_angle(side)

        body_surface_z = side * BAFFLE_BODY_HEIGHT / 2.0
        arm_inner_z = root_z - side * BAFFLE_SNAP_TONGUE_THICKNESS_Z / 2.0
        root_bridge_height = (
            abs(arm_inner_z - body_surface_z) + 2.0 * join_overlap
        )
        root_bridge = add_box(
            f"Baffle_Snap_Root_{'Top' if side > 0 else 'Bottom'}",
            (
                BAFFLE_SNAP_TONGUE_WIDTH_X,
                BAFFLE_SNAP_ROOT_DEPTH_Y + 2.0 * join_overlap,
                root_bridge_height,
            ),
            (
                baffle_snap_auxiliary_center_x_at_y(
                    root_y,
                    BAFFLE_SNAP_ROOT_DEPTH_Y + 2.0 * join_overlap,
                ),
                root_y,
                (body_surface_z + arm_inner_z) / 2.0,
            ),
        )
        boolean_union(
            component,
            root_bridge,
            f"Baffle_Snap_Root_{'Top' if side > 0 else 'Bottom'}_Union",
            solver=WATERTIGHT_DETAIL_UNION_SOLVER,
            require_geometry_change=True,
        )
        boolean_union(
            component,
            arm,
            f"Baffle_Snap_Tongue_{'Top' if side > 0 else 'Bottom'}_Union",
            solver=WATERTIGHT_DETAIL_UNION_SOLVER,
            require_geometry_change=True,
        )

        hook_y = baffle_snap_hook_y()
        hook_center_z = (
            baffle_snap_tongue_center_z_at_y(
                hook_y,
                side,
            )
            + side
            * (
                BAFFLE_SNAP_TONGUE_THICKNESS_Z / 2.0
                + BAFFLE_SNAP_HOOK_PROTRUSION_Z / 2.0
                - join_overlap
            )
        )
        hook = add_beveled_box(
            f"Baffle_Snap_Hook_{'Top' if side > 0 else 'Bottom'}",
            (
                BAFFLE_SNAP_TONGUE_WIDTH_X,
                BAFFLE_SNAP_RECEIVER_DEPTH_Y + 2.0 * join_overlap,
                BAFFLE_SNAP_HOOK_PROTRUSION_Z + 2.0 * join_overlap,
            ),
            (
                baffle_snap_auxiliary_center_x_at_y(
                    hook_y,
                    BAFFLE_SNAP_RECEIVER_DEPTH_Y
                    + 2.0 * join_overlap,
                ),
                hook_y,
                hook_center_z,
            ),
            min(BAFFLE_SNAP_RECEIVER_BEVEL, 0.20),
            rotation=(angle, 0.0, 0.0),
        )
        boolean_union(
            component,
            hook,
            f"Baffle_Snap_Hook_{'Top' if side > 0 else 'Bottom'}_Union",
            solver=WATERTIGHT_DETAIL_UNION_SOLVER,
            require_geometry_change=True,
        )
    return component


def create_baffle_tray():
    outer_sections = baffle_shell_sections(inner=False)
    tray = loft_through_loops_y(
        "Baffle_Cartridge_Outer_Solid",
        tuple(loop for _y, loop in outer_sections),
        tuple(y for y, _loop in outer_sections),
    )
    inner_sections = baffle_shell_sections(inner=True)
    cavity = loft_through_loops_y(
        "Baffle_Cartridge_Inner_Cavity",
        tuple(loop for _y, loop in inner_sections),
        tuple(y for y, _loop in inner_sections),
    )
    join_overlap = baffle_boolean_join_overlap()
    for index, loop in enumerate(baffle_inlet_loops(), start=1):
        inlet = polygon_prism_y(
            f"Baffle_Inlet_Opening_{index}",
            loop,
            BAFFLE_REAR_Y - BOOLEAN_OVERLAP,
            BAFFLE_REAR_Y
            + BAFFLE_WALL_THICKNESS
            + join_overlap
            + BOOLEAN_OVERLAP,
        )
        boolean_union(
            cavity,
            inlet,
            f"Baffle_Cavity_Inlet_Cutter_{index}_Union",
            solver=WATERTIGHT_DETAIL_UNION_SOLVER,
            require_geometry_change=True,
        )
    # Include the inlet neck in the cavity cutter so the first subtraction
    # opens the airway to the exterior. An entirely enclosed cavity surface
    # is vulnerable to orientation inversion in Blender's Exact solver when
    # a later operation first pierces it.
    apply_boolean(
        tray,
        cavity,
        "DIFFERENCE",
        "Baffle_Cavity_And_Inlet",
        solver=BOOLEAN_SOLVER,
        require_geometry_change=True,
    )
    for index, loop in enumerate(baffle_outlet_loops(), start=1):
        outlet = polygon_prism_y(
            f"Baffle_Forward_Outlet_{index}",
            loop,
            baffle_outlet_cutter_rear_y(),
            BAFFLE_FRONT_Y + BOOLEAN_OVERLAP,
        )
        apply_boolean(
            tray,
            outlet,
            "DIFFERENCE",
            f"Baffle_Outlet_{index}",
            solver=BOOLEAN_SOLVER,
            require_geometry_change=True,
        )

    if not baffle_gasket_is_integral():
        groove = create_baffle_seal_ring(
            "Baffle_Gasket_Locating_Groove",
            BAFFLE_REAR_Y - BOOLEAN_OVERLAP,
            BAFFLE_REAR_Y + BAFFLE_GASKET_GROOVE_DEPTH_Y,
            locating_clearance=BAFFLE_GASKET_GROOVE_RADIAL_CLEARANCE,
        )
        apply_boolean(
            tray,
            groove,
            "DIFFERENCE",
            "Baffle_Gasket_Locating_Groove",
            solver=WATERTIGHT_DETAIL_UNION_SOLVER,
            require_geometry_change=True,
        )
        groove_floor = create_baffle_seal_ring(
            "Baffle_Gasket_Continuous_Groove_Floor",
            BAFFLE_REAR_Y
            + BAFFLE_GASKET_GROOVE_DEPTH_Y,
            BAFFLE_REAR_Y + BAFFLE_WALL_THICKNESS,
        )
        boolean_union(
            tray,
            groove_floor,
            "Baffle_Gasket_Continuous_Groove_Floor_Union",
            solver=WATERTIGHT_DETAIL_UNION_SOLVER,
            require_geometry_change=True,
        )

    add_baffle_internal_members(tray)
    side_opening = create_baffle_side_opening_cutter()
    apply_boolean(
        tray,
        side_opening,
        "DIFFERENCE",
        "Baffle_Tray_Side_Opening",
        solver=WATERTIGHT_DETAIL_UNION_SOLVER,
        require_geometry_change=True,
    )
    add_baffle_second_end_frame(tray)
    add_baffle_tpu_lid_blocker_tab(tray)
    add_baffle_snap_tongues(tray)
    if baffle_gasket_is_integral():
        integral_seal = create_baffle_seal_ring(
            "Baffle_Integral_TPU_Inlet_Seal",
            BAFFLE_REAR_Y - baffle_gasket_exposed_height(),
            BAFFLE_REAR_Y + baffle_boolean_join_overlap(),
        )
        boolean_union(
            tray,
            integral_seal,
            "Baffle_Integral_TPU_Inlet_Seal_Union",
            solver=WATERTIGHT_DETAIL_UNION_SOLVER,
            require_geometry_change=True,
        )
    tray.name = "GoPro_Fan_Case_Baffle_Tray"
    tray.data.name = "GoPro_Fan_Case_Baffle_Tray_Mesh"
    return tray


def baffle_lid_outer_loop_at_y(y: float):
    _left, right, bottom, top = baffle_body_bounds_at_y(y)
    return [
        (right - BAFFLE_LID_PLATE_THICKNESS_X, bottom),
        (right, bottom),
        (right, top),
        (right - BAFFLE_LID_PLATE_THICKNESS_X, top),
    ]


def baffle_lid_key_loop_at_y(y: float):
    _left, right, bottom, top = baffle_body_bounds_at_y(y)
    inner_right = right - BAFFLE_WALL_THICKNESS
    return [
        (
            inner_right - BAFFLE_LID_KEY_DEPTH_X,
            bottom + BAFFLE_WALL_THICKNESS + BAFFLE_LID_FIT_CLEARANCE,
        ),
        (
            right - BAFFLE_LID_PLATE_THICKNESS_X + BOOLEAN_OVERLAP,
            bottom + BAFFLE_WALL_THICKNESS + BAFFLE_LID_FIT_CLEARANCE,
        ),
        (
            right - BAFFLE_LID_PLATE_THICKNESS_X + BOOLEAN_OVERLAP,
            top - BAFFLE_WALL_THICKNESS - BAFFLE_LID_FIT_CLEARANCE,
        ),
        (
            inner_right - BAFFLE_LID_KEY_DEPTH_X,
            top - BAFFLE_WALL_THICKNESS - BAFFLE_LID_FIT_CLEARANCE,
        ),
    ]


def create_baffle_tpu_lid_slot_cutter(
    name: str,
    center_y: float,
    half_height_z: float,
):
    """Create an upward-open, support-free groove at one baffle station."""
    slot_half_y = (
        BAFFLE_INTERNAL_THICKNESS_Y / 2.0
        + BAFFLE_TPU_LID_BLOCKER_SLOT_CLEARANCE_Y
    )
    y_positions = (
        center_y - slot_half_y,
        center_y + slot_half_y,
    )
    loops = []
    for y in y_positions:
        slot_entry_x = baffle_lid_key_inner_x_at_y(y)
        loops.append(
            [
                (slot_entry_x - BOOLEAN_OVERLAP, -half_height_z),
                (
                    slot_entry_x + BAFFLE_TPU_LID_BLOCKER_SLOT_DEPTH_X,
                    -half_height_z,
                ),
                (
                    slot_entry_x + BAFFLE_TPU_LID_BLOCKER_SLOT_DEPTH_X,
                    half_height_z,
                ),
                (slot_entry_x - BOOLEAN_OVERLAP, half_height_z),
            ]
        )
    return loft_through_loops_y(
        name,
        loops,
        y_positions,
        cap_centers=tuple(
            (
                sum(point[0] for point in loop) / len(loop),
                sum(point[1] for point in loop) / len(loop),
            )
            for loop in loops
        ),
    )


def create_baffle_second_end_frame_lid_pocket(
    name: str,
    bottom_z: float,
    top_z: float,
):
    """Create one close-fit, outward-open pocket for a tray end return."""
    y_positions = baffle_second_end_frame_y_bounds(
        BAFFLE_SECOND_END_FRAME_LID_CLEARANCE_Y
    )
    loops = []
    for y in y_positions:
        pocket_entry_x = baffle_lid_key_inner_x_at_y(y)
        loops.append(
            [
                (pocket_entry_x - BOOLEAN_OVERLAP, bottom_z),
                (
                    pocket_entry_x
                    + BAFFLE_SECOND_END_FRAME_LID_POCKET_DEPTH_X,
                    bottom_z,
                ),
                (
                    pocket_entry_x
                    + BAFFLE_SECOND_END_FRAME_LID_POCKET_DEPTH_X,
                    top_z,
                ),
                (pocket_entry_x - BOOLEAN_OVERLAP, top_z),
            ]
        )
    return loft_through_loops_y(
        name,
        loops,
        y_positions,
        cap_centers=tuple(
            (
                sum(point[0] for point in loop) / len(loop),
                sum(point[1] for point in loop) / len(loop),
            )
            for loop in loops
        ),
    )


def create_baffle_lid():
    outer_loops = (
        baffle_lid_outer_loop_at_y(BAFFLE_REAR_Y),
        baffle_lid_outer_loop_at_y(BAFFLE_FRONT_Y),
    )
    outer = loft_through_loops_y(
        "Baffle_Lid_Outer_Plate",
        outer_loops,
        (BAFFLE_REAR_Y, BAFFLE_FRONT_Y),
        cap_centers=tuple(
            (
                sum(point[0] for point in loop) / len(loop),
                sum(point[1] for point in loop) / len(loop),
            )
            for loop in outer_loops
        ),
    )
    key_start_y = (
        BAFFLE_REAR_Y
        + BAFFLE_WALL_THICKNESS
        + BAFFLE_LID_FIT_CLEARANCE
    )
    key_end_y = (
        BAFFLE_FRONT_Y
        - BAFFLE_WALL_THICKNESS
        - BAFFLE_LID_FIT_CLEARANCE
    )
    key_loops = (
        baffle_lid_key_loop_at_y(key_start_y),
        baffle_lid_key_loop_at_y(key_end_y),
    )
    key = loft_through_loops_y(
        "Baffle_Lid_Inner_Key",
        key_loops,
        (key_start_y, key_end_y),
        cap_centers=tuple(
            (
                sum(point[0] for point in loop) / len(loop),
                sum(point[1] for point in loop) / len(loop),
            )
            for loop in key_loops
        ),
    )
    boolean_union(
        outer,
        key,
        "Baffle_Lid_Key_Union",
        solver=WATERTIGHT_DETAIL_UNION_SOLVER,
        require_geometry_change=True,
    )
    _left, _right, body_bottom, body_top = baffle_body_bounds_at_y(
        baffle_second_end_frame_center_y()
    )
    frame_join_overlap = baffle_boolean_join_overlap()
    frame_half_opening = BAFFLE_SECOND_OPENING_HEIGHT_Z / 2.0
    frame_pocket_specs = (
        (
            "Baffle_Second_Top_End_Lid_Pocket",
            frame_half_opening
            - frame_join_overlap
            - BAFFLE_SECOND_END_FRAME_LID_CLEARANCE_Z,
            body_top + BOOLEAN_OVERLAP,
        ),
        (
            "Baffle_Second_Bottom_End_Lid_Pocket",
            body_bottom - BOOLEAN_OVERLAP,
            -frame_half_opening
            + frame_join_overlap
            + BAFFLE_SECOND_END_FRAME_LID_CLEARANCE_Z,
        ),
    )
    for pocket_name, pocket_bottom_z, pocket_top_z in frame_pocket_specs:
        frame_pocket = create_baffle_second_end_frame_lid_pocket(
            pocket_name,
            pocket_bottom_z,
            pocket_top_z,
        )
        apply_boolean(
            outer,
            frame_pocket,
            "DIFFERENCE",
            pocket_name,
            solver=WATERTIGHT_DETAIL_UNION_SOLVER,
            require_geometry_change=True,
        )
    if baffle_gasket_is_integral():
        slot_name = "Baffle_TPU_First_Blocker_Lid_Slot"
        slot = create_baffle_tpu_lid_slot_cutter(
            slot_name,
            BAFFLE_FIRST_Y,
            BAFFLE_FIRST_BLOCKER_HEIGHT_Z / 2.0
            + BAFFLE_TPU_LID_BLOCKER_SLOT_CLEARANCE_Z,
        )
        apply_boolean(
            outer,
            slot,
            "DIFFERENCE",
            slot_name,
            solver=WATERTIGHT_DETAIL_UNION_SOLVER,
            require_geometry_change=True,
        )
    outer.name = "GoPro_Fan_Case_Baffle_Lid"
    outer.data.name = "GoPro_Fan_Case_Baffle_Lid_Mesh"
    return outer


def create_baffle_seal_ring(
    name: str,
    y0: float,
    y1: float,
    locating_clearance: float = 0.0,
):
    outer_radius = (
        BAFFLE_GASKET_OUTER_DIAMETER / 2.0 + locating_clearance
    )
    inner_radius = (
        BAFFLE_GASKET_INNER_DIAMETER / 2.0 - locating_clearance
    )
    ring = annular_cylinder_y(
        name,
        outer_radius,
        inner_radius,
        y0,
        y1,
        x=FAN_CENTER_X,
        z=FAN_CENTER_Z,
    )
    scallop_clearance = max(
        BAFFLE_GASKET_BOSS_CLEARANCE - locating_clearance,
        0.0,
    )
    scallops = []
    for index, (x, z) in enumerate(fan_hole_positions(), start=1):
        scallops.append(
            add_cylinder_y(
                f"{name}_Fan_Boss_Clearance_{index}",
                FAN_HOLE_BOSS_DIAMETER / 2.0
                + scallop_clearance,
                y0 - BOOLEAN_OVERLAP,
                y1 + BOOLEAN_OVERLAP,
                x=x,
                z=z,
            )
        )
    boolean_difference(ring, scallops, f"{name}_Boss_Scallops")
    return ring


def create_baffle_gasket():
    gasket = create_baffle_seal_ring(
        "Baffle_TPU_Inlet_Gasket",
        fan_pad_inner_y(),
        fan_pad_inner_y() + BAFFLE_GASKET_THICKNESS_Y,
    )
    gasket.name = "GoPro_Fan_Case_Baffle_Gasket"
    gasket.data.name = "GoPro_Fan_Case_Baffle_Gasket_Mesh"
    return gasket


def create_baffle_cartridge():
    if not BAFFLE_CARTRIDGE_ENABLED:
        return ()
    tray = create_baffle_tray()
    lid = create_baffle_lid()
    if baffle_gasket_is_integral():
        return tray, lid
    return tray, lid, create_baffle_gasket()


# ---------------------------------------------------------------------------
# Mating insert frame


def create_locating_tabs(insert):
    if not LOCATING_TABS_ENABLED:
        return insert
    y0 = insert_start_y()
    y1 = insert_start_y() + INSERT_DEPTH
    depth = y1 - y0
    center_y = (y0 + y1) / 2.0
    taper_cutters = []

    for spec in LOCATING_TAB_SPECS:
        name, x0, x1, z0, z1, attachment = spec
        # The measured bounds describe the exposed rail. Add a small overlap
        # only toward its supporting insert wall for a reliable solid union.
        if attachment == "top":
            z1 = max(z1, insert_inner_height() / 2.0 + BOOLEAN_OVERLAP)
        elif attachment == "bottom":
            z0 = min(z0, -insert_inner_height() / 2.0 - BOOLEAN_OVERLAP)
        elif attachment == "left":
            x0 = min(x0, -insert_inner_width() / 2.0 - BOOLEAN_OVERLAP)
        elif attachment == "right":
            x1 = max(x1, insert_inner_width() / 2.0 + BOOLEAN_OVERLAP)

        tab = add_box(
            f"Locating_Rail_{name}",
            (x1 - x0, depth, z1 - z0),
            ((x0 + x1) / 2.0, center_y, (z0 + z1) / 2.0),
        )
        boolean_union(insert, tab, f"Locating_Rail_{name}_Union")

        taper = LENS_CLEARANCE_GUIDE_TAPERS.get(name)
        if taper is not None:
            taper_length, front_projection = taper
            cutter_margin = LENS_CLEARANCE_CUTTER_MARGIN
            taper_start_y = y1 - taper_length
            cutter_start_y = taper_start_y - BOOLEAN_OVERLAP
            cutter_end_y = y1 + BOOLEAN_OVERLAP
            if attachment == "top":
                front_z0 = insert_inner_height() / 2.0 - front_projection
                slope = (front_z0 - z0) / taper_length
                start_top = z0 - slope * BOOLEAN_OVERLAP
                end_top = front_z0 + slope * BOOLEAN_OVERLAP
                cutter_bottom = min(start_top, z0) - cutter_margin
                start_loop = [
                    (x0 - cutter_margin, cutter_bottom),
                    (x1 + cutter_margin, cutter_bottom),
                    (x1 + cutter_margin, start_top),
                    (x0 - cutter_margin, start_top),
                ]
                end_loop = [
                    (x0 - cutter_margin, cutter_bottom),
                    (x1 + cutter_margin, cutter_bottom),
                    (x1 + cutter_margin, end_top),
                    (x0 - cutter_margin, end_top),
                ]
            elif attachment == "right":
                front_x0 = insert_inner_width() / 2.0 - front_projection
                slope = (front_x0 - x0) / taper_length
                start_right = x0 - slope * BOOLEAN_OVERLAP
                end_right = front_x0 + slope * BOOLEAN_OVERLAP
                cutter_left = min(start_right, x0) - cutter_margin
                start_loop = [
                    (cutter_left, z0 - cutter_margin),
                    (start_right, z0 - cutter_margin),
                    (start_right, z1 + cutter_margin),
                    (cutter_left, z1 + cutter_margin),
                ]
                end_loop = [
                    (cutter_left, z0 - cutter_margin),
                    (end_right, z0 - cutter_margin),
                    (end_right, z1 + cutter_margin),
                    (cutter_left, z1 + cutter_margin),
                ]
            else:
                front_x1 = -insert_inner_width() / 2.0 + front_projection
                slope = (front_x1 - x1) / taper_length
                start_left = x1 - slope * BOOLEAN_OVERLAP
                end_left = front_x1 + slope * BOOLEAN_OVERLAP
                cutter_right = max(start_left, x1) + cutter_margin
                start_loop = [
                    (start_left, z0 - cutter_margin),
                    (cutter_right, z0 - cutter_margin),
                    (cutter_right, z1 + cutter_margin),
                    (start_left, z1 + cutter_margin),
                ]
                end_loop = [
                    (end_left, z0 - cutter_margin),
                    (cutter_right, z0 - cutter_margin),
                    (cutter_right, z1 + cutter_margin),
                    (end_left, z1 + cutter_margin),
                ]
            taper_cutters.append(
                loft_through_loops_y(
                    f"Locating_Rail_{name}_Lens_Clearance",
                    (start_loop, end_loop),
                    (cutter_start_y, cutter_end_y),
                )
            )
    if taper_cutters:
        boolean_difference(insert, taper_cutters, "Lens_Clearance_Guide_Tapers")
    return insert


def create_snap_bumps(insert):
    if not SNAP_ENABLED:
        return insert
    y = insert_start_y() + SNAP_BUMP_Y_OFFSET + SNAP_BUMP_LENGTH_Y / 2.0
    for side in (-1.0, 1.0):
        x = side * (
            INSERT_FRONT_WIDTH / 2.0
            + SNAP_BUMP_PROTRUSION / 2.0
            - BOOLEAN_OVERLAP
        )
        bump = add_beveled_box(
            f"Snap_Bump_{'Left' if side < 0 else 'Right'}",
            (
                SNAP_BUMP_PROTRUSION + BOOLEAN_OVERLAP,
                SNAP_BUMP_LENGTH_Y,
                SNAP_BUMP_LENGTH_Z,
            ),
            (x, y, 0.0),
            SNAP_EDGE_RADIUS,
        )
        boolean_union(insert, bump, "Snap_Bump_Union")
    return insert


def add_retainer_index_keys(insert):
    """Add two shallow 0/180-degree index keys at each sleeve fastener."""
    if not (RETAINER_ENABLED and RETAINER_KEEPER_INDEX_ENABLED):
        return insert
    face_y = retainer_assembly_face_y()
    key_depth = RETAINER_KEEPER_INDEX_KEY_PROJECTION_Y + BOOLEAN_OVERLAP
    center_y = (
        face_y
        + RETAINER_KEEPER_INDEX_KEY_PROJECTION_Y / 2.0
        - BOOLEAN_OVERLAP / 2.0
    )
    for fastener_index, (bolt_x, bolt_z) in enumerate(
        CASE_FASTENER_POSITIONS_XZ,
        start=1,
    ):
        for key_index, (key_x, key_z) in enumerate(
            retainer_index_key_centers(bolt_x, bolt_z),
            start=1,
        ):
            key = add_beveled_box(
                f"Retainer_Index_Key_{fastener_index}_{key_index}",
                (
                    RETAINER_KEEPER_INDEX_KEY_WIDTH_X,
                    key_depth,
                    RETAINER_KEEPER_INDEX_KEY_HEIGHT_Z,
                ),
                (key_x, center_y, key_z),
                RETAINER_KEEPER_INDEX_KEY_BEVEL,
            )
            boolean_union(
                insert,
                key,
                f"Retainer_Index_Key_{fastener_index}_{key_index}_Union",
                solver=WATERTIGHT_DETAIL_UNION_SOLVER,
                require_geometry_change=True,
            )
    return insert


def create_insert_frame():
    insert = create_insert_tube()

    if CASE_FASTENERS_ENABLED:
        for index, (x, z) in enumerate(CASE_FASTENER_POSITIONS_XZ, start=1):
            boss = add_cylinder_y(
                f"Insert_Fastener_Boss_{index}",
                INSERT_FASTENER_BOSS_DIAMETER / 2.0,
                insert_start_y(),
                insert_start_y() + INSERT_DEPTH,
                x=x,
                z=z,
            )
            boolean_union(insert, boss, "Insert_Fastener_Boss_Union")

    add_retainer_index_keys(insert)

    create_locating_tabs(insert)
    create_snap_bumps(insert)

    cuts = []
    if CASE_FASTENERS_ENABLED:
        for index, (x, z) in enumerate(CASE_FASTENER_POSITIONS_XZ, start=1):
            cuts.append(
                add_cylinder_y(
                    f"Insert_Fastener_Hole_{index}",
                    INSERT_FASTENER_HOLE_DIAMETER / 2.0,
                    insert_sleeve_leading_y() - BOOLEAN_OVERLAP,
                    insert_start_y() + INSERT_DEPTH + BOOLEAN_OVERLAP,
                    x=x,
                    z=z,
                )
            )

    if BOTTOM_ACCESS_ENABLED:
        y0 = insert_start_y() + BOTTOM_ACCESS_Y_OFFSET
        cuts.append(
            add_box(
                "Bottom_Access_Opening",
                (
                    BOTTOM_ACCESS_WIDTH,
                    BOTTOM_ACCESS_DEPTH,
                    (INSERT_REAR_HEIGHT - insert_inner_height()) / 2.0 + 2.0,
                ),
                (
                    0.0,
                    y0 + BOTTOM_ACCESS_DEPTH / 2.0,
                    -INSERT_REAR_HEIGHT / 2.0,
                ),
            )
        )

    if LEFT_ROUND_PORT_ENABLED:
        cuts.append(
            add_cylinder_x(
                "Left_Round_Port",
                LEFT_ROUND_PORT_DIAMETER / 2.0,
                -max(INSERT_FRONT_WIDTH, INSERT_REAR_WIDTH) / 2.0
                - BOOLEAN_OVERLAP,
                0.0,
                y=insert_start_y() + LEFT_ROUND_PORT_Y_OFFSET,
                z=LEFT_ROUND_PORT_Z,
            )
        )

    if RIGHT_USB_PORT_ENABLED:
        cuts.append(
            rounded_rectangle_prism_x(
                "Right_USB_Port",
                RIGHT_USB_PORT_WIDTH_Y,
                RIGHT_USB_PORT_HEIGHT_Z,
                RIGHT_USB_PORT_CORNER_RADIUS,
                0.0,
                max(INSERT_FRONT_WIDTH, INSERT_REAR_WIDTH) / 2.0
                + BOOLEAN_OVERLAP,
                center_y=insert_start_y() + RIGHT_USB_PORT_Y_OFFSET,
                center_z=RIGHT_USB_PORT_Z,
            )
        )

    if TOP_PORT_ENABLED:
        cuts.append(
            add_cylinder_z(
                "Top_Port",
                TOP_PORT_DIAMETER / 2.0,
                insert_inner_height() / 2.0 - BOOLEAN_OVERLAP,
                INSERT_REAR_HEIGHT / 2.0 + BOOLEAN_OVERLAP,
                x=TOP_PORT_X,
                y=insert_start_y() + TOP_PORT_Y_OFFSET,
            )
        )

    if cuts:
        boolean_difference(insert, cuts, "Insert_Openings")

    insert.name = "GoPro_Fan_Case_Insert"
    insert.data.name = "GoPro_Fan_Case_Insert_Mesh"
    return insert


def create_captive_button_mesh():
    """Create one watertight rotational button along local +Z.

    The local origin is the flat inside face of the camera-side flange.  This
    also makes the separately exported button stand on that flange without
    needing a print-orientation transform.
    """
    stem_radius = BUTTON_STEM_DIAMETER / 2.0
    flange_radius = BUTTON_INNER_FLANGE_DIAMETER / 2.0
    rim_radius = BUTTON_RETENTION_RIM_DIAMETER / 2.0
    rim_start_z = BUTTON_TOTAL_HEIGHT - BUTTON_RETENTION_RIM_HEIGHT
    rim_full_z = rim_start_z + BUTTON_RETENTION_SHOULDER_HEIGHT
    lead_in_start_z = (
        BUTTON_TOTAL_HEIGHT - BUTTON_RETENTION_LEAD_IN_HEIGHT
    )
    profile = (
        (0.0, flange_radius),
        (BUTTON_INNER_FLANGE_THICKNESS, flange_radius),
        (BUTTON_INNER_FLANGE_THICKNESS, stem_radius),
        (rim_start_z, stem_radius),
        (rim_full_z, rim_radius),
        (lead_in_start_z, rim_radius),
        (BUTTON_TOTAL_HEIGHT, stem_radius),
    )

    vertices = []
    for z, radius in profile:
        for index in range(CYLINDER_SEGMENTS):
            angle = 2.0 * math.pi * index / CYLINDER_SEGMENTS
            vertices.append(
                (radius * math.cos(angle), radius * math.sin(angle), z)
            )
    bottom_center = len(vertices)
    vertices.append((0.0, 0.0, 0.0))
    top_center = len(vertices)
    vertices.append((0.0, 0.0, BUTTON_TOTAL_HEIGHT))

    def ring(profile_index: int, segment_index: int) -> int:
        return (
            profile_index * CYLINDER_SEGMENTS
            + segment_index % CYLINDER_SEGMENTS
        )

    faces = []
    for profile_index in range(len(profile) - 1):
        for segment_index in range(CYLINDER_SEGMENTS):
            next_index = segment_index + 1
            faces.append(
                (
                    ring(profile_index, segment_index),
                    ring(profile_index, next_index),
                    ring(profile_index + 1, next_index),
                    ring(profile_index + 1, segment_index),
                )
            )
    last_profile_index = len(profile) - 1
    for segment_index in range(CYLINDER_SEGMENTS):
        next_index = segment_index + 1
        faces.append(
            (
                bottom_center,
                ring(0, next_index),
                ring(0, segment_index),
            )
        )
        faces.append(
            (
                top_center,
                ring(last_profile_index, segment_index),
                ring(last_profile_index, next_index),
            )
        )

    button = create_mesh_object("GoPro_Captive_Button_Top", vertices, faces)
    button.data.name = "GoPro_Captive_Button_Mesh"
    return button


def create_captive_buttons():
    """Create and install the two identical buttons in their sleeve ports."""
    top_button = create_captive_button_mesh()
    top_button.location = (
        TOP_PORT_X,
        insert_start_y() + TOP_PORT_Y_OFFSET,
        insert_inner_height() / 2.0 - BUTTON_INNER_FLANGE_THICKNESS,
    )

    left_button = top_button.copy()
    left_button.data = top_button.data
    left_button.name = "GoPro_Captive_Button_Left"
    bpy.context.collection.objects.link(left_button)
    left_button.location = (
        -insert_inner_width() / 2.0 + BUTTON_INNER_FLANGE_THICKNESS,
        insert_start_y() + LEFT_ROUND_PORT_Y_OFFSET,
        LEFT_ROUND_PORT_Z,
    )
    # Local +Z is the insertion/outward axis.  The left port points toward -X.
    left_button.rotation_euler = (0.0, -math.pi / 2.0, 0.0)
    return left_button, top_button


def create_retainer_index_recess_cutters(name_prefix: str, bolt_centers):
    """Create rear-face pockets for the sleeve's paired index keys."""
    if not RETAINER_KEEPER_INDEX_ENABLED:
        return []
    recess_width, recess_height = retainer_index_recess_dimensions()
    y0 = -BOOLEAN_OVERLAP
    y1 = RETAINER_KEEPER_INDEX_RECESS_DEPTH_Y
    cutters = []
    for bolt_index, (bolt_x, bolt_z) in enumerate(bolt_centers, start=1):
        for recess_index, (recess_x, recess_z) in enumerate(
            retainer_index_key_centers(bolt_x, bolt_z),
            start=1,
        ):
            cutters.append(
                add_box(
                    f"{name_prefix}_{bolt_index}_{recess_index}",
                    (recess_width, y1 - y0, recess_height),
                    (recess_x, (y0 + y1) / 2.0, recess_z),
                )
            )
    return cutters


def create_front_retainer():
    """Create the direct-M3 captive swing gate and lower-bolt tracks."""
    layout = resolved_retainer_layout()
    thickness = retainer_gate_thickness_y()
    retainer = rounded_rectangle_prism_y(
        "Front_Retainer_Lower_Bar",
        layout["bar_width"],
        RETAINER_HORIZONTAL_BAR_HEIGHT_Z,
        RETAINER_CORNER_RADIUS,
        0.0,
        thickness,
        center_x=layout["bar_center_x"],
        center_z=layout["bar_center_z"],
    )

    relief = add_cylinder_y(
        "Front_Retainer_Camera_Relief",
        RETAINER_RELIEF_RADIUS,
        -BOOLEAN_OVERLAP,
        thickness + BOOLEAN_OVERLAP,
        x=RETAINER_RELIEF_CENTER_X,
        z=RETAINER_RELIEF_CENTER_Z,
    )
    boolean_difference(retainer, [relief], "Front_Retainer_Relief")

    upright = rounded_rectangle_prism_y(
        "Front_Retainer_Upper_Upright",
        RETAINER_UPRIGHT_WIDTH_X,
        layout["upright_height"],
        RETAINER_CORNER_RADIUS,
        0.0,
        thickness,
        center_x=layout["upper"][0],
        center_z=layout["upright_center_z"],
    )
    boolean_union(
        retainer,
        upright,
        "Front_Retainer_Upright_Union",
        solver=WATERTIGHT_DETAIL_UNION_SOLVER,
        require_geometry_change=True,
    )

    cutter_y0 = -BOOLEAN_OVERLAP
    cutter_y1 = thickness + BOOLEAN_OVERLAP
    clearance_radius = RETAINER_GATE_BOLT_TRACK_DIAMETER / 2.0
    lower_left = layout["lower_left"]
    lower_right = layout["lower_right"]
    pivot = layout["upper"]
    cutters = []

    # The upper-right M3 bolt remains through this closed bearing at all times.
    cutters.append(
        add_cylinder_y(
            "Front_Retainer_Pivot_Bearing",
            clearance_radius,
            cutter_y0,
            cutter_y1,
            x=pivot[0],
            z=pivot[1],
        )
    )

    # Both lower M3 bolts follow full-width tracks as the loosened gate begins
    # to swing.  The left track exits the edge; the right reaches the relief.
    left_angles = retainer_bolt_sweep_angles(
        RETAINER_GATE_LOWER_LEFT_RELEASE_ANGLE_DEG
    )
    left_points = [
        retainer_bolt_sweep_point(lower_left, pivot, angle)
        for angle in left_angles
    ]
    for index, (point0, point1) in enumerate(
        zip(left_points, left_points[1:]),
        start=1,
    ):
        cutters.append(
            capsule_prism_y(
                f"Front_Retainer_Lower_Left_Bolt_Track_{index}",
                point0,
                point1,
                clearance_radius,
                cutter_y0,
                cutter_y1,
            )
        )

    right_angles = retainer_bolt_sweep_angles(
        RETAINER_GATE_LOWER_RIGHT_RELEASE_ANGLE_DEG
    )
    right_points = [
        retainer_bolt_sweep_point(lower_right, pivot, angle)
        for angle in right_angles
    ]
    for index, (point0, point1) in enumerate(
        zip(right_points, right_points[1:]),
        start=1,
    ):
        cutters.append(
            capsule_prism_y(
                f"Front_Retainer_Lower_Right_Bolt_Track_{index}",
                point0,
                point1,
                clearance_radius,
                cutter_y0,
                cutter_y1,
            )
        )

    # These cutters deliberately overlap to form smooth cam tracks.  Applying
    # them sequentially avoids Blender EXACT treating their joined internal
    # faces as one self-intersecting compound and deleting the whole gate.
    for index, cutter in enumerate(cutters, start=1):
        boolean_difference(
            retainer,
            [cutter],
            f"Front_Retainer_Bolt_Track_{index}",
        )

    # The common insert carries paired low-profile keeper-index keys.  Matching
    # shallow pockets let this gate clamp flush too.  Lift the loosened gate by
    # the pocket depth before swinging it so the fixed keys clear the rear face.
    index_cutters = create_retainer_index_recess_cutters(
        "Front_Retainer_Index_Recess",
        CASE_FASTENER_POSITIONS_XZ,
    )
    for index, cutter in enumerate(index_cutters, start=1):
        boolean_difference(
            retainer,
            [cutter],
            f"Front_Retainer_Index_Recess_{index}",
        )
    retainer.name = "GoPro_Fan_Case_Swing_Gate"
    retainer.data.name = "GoPro_Fan_Case_Swing_Gate_Mesh"
    retainer.location.y = retainer_gate_assembled_y()
    return retainer


def create_rotating_keeper_mesh():
    """Create one indexed keeper with its closed lobe pointing along local +Z."""
    thickness = retainer_keeper_thickness_y()
    hub_radius = RETAINER_KEEPER_HUB_DIAMETER / 2.0
    lobe = rounded_rectangle_prism_y(
        "Rotating_Keeper_Lobe",
        RETAINER_KEEPER_LOBE_WIDTH_X,
        RETAINER_KEEPER_CLOSED_PROJECTION_Z,
        RETAINER_KEEPER_LOBE_WIDTH_X / 2.0,
        0.0,
        thickness,
        center_z=RETAINER_KEEPER_CLOSED_PROJECTION_Z / 2.0,
    )
    hub = add_cylinder_y(
        "Rotating_Keeper_Hub",
        hub_radius,
        0.0,
        thickness,
    )
    boolean_union(
        lobe,
        hub,
        "Rotating_Keeper_Hub_Union",
        solver=WATERTIGHT_DETAIL_UNION_SOLVER,
        require_geometry_change=True,
    )
    shaft_hole = add_cylinder_y(
        "Rotating_Keeper_M3_Hole",
        RETAINER_KEEPER_BOLT_HOLE_DIAMETER / 2.0,
        -BOOLEAN_OVERLAP,
        thickness + BOOLEAN_OVERLAP,
    )
    boolean_difference(lobe, [shaft_hole], "Rotating_Keeper_M3_Hole")
    index_cutters = create_retainer_index_recess_cutters(
        "Rotating_Keeper_Index_Recess",
        ((0.0, 0.0),),
    )
    for index, cutter in enumerate(index_cutters, start=1):
        boolean_difference(
            lobe,
            [cutter],
            f"Rotating_Keeper_Index_Recess_{index}",
        )
    lobe.name = "GoPro_Fan_Case_Rotating_Keeper_Lower_Left"
    lobe.data.name = "GoPro_Fan_Case_Rotating_Keeper_Mesh"
    return lobe


def create_rotating_keepers():
    """Install one closed keeper on each existing M3 case-fastener shaft."""
    layout = resolved_retainer_layout()
    positions = (
        ("Lower_Left", layout["lower_left"], 0.0),
        ("Lower_Right", layout["lower_right"], 0.0),
        ("Upper_Right", layout["upper"], math.pi),
    )
    base = create_rotating_keeper_mesh()
    keepers = []
    for index, (name, (x, z), rotation_y) in enumerate(positions):
        if index == 0:
            keeper = base
        else:
            keeper = base.copy()
            keeper.data = base.data
            bpy.context.collection.objects.link(keeper)
        keeper.name = f"GoPro_Fan_Case_Rotating_Keeper_{name}"
        keeper.location = (x, retainer_assembly_face_y(), z)
        keeper.rotation_euler = (0.0, rotation_y, 0.0)
        keepers.append(keeper)
    return tuple(keepers)


# ---------------------------------------------------------------------------
# Validation, layout, materials, and export


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


def mesh_bvh(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    return bvh


def bvh_segment_is_blocked(bvhs, start, end) -> bool:
    """Return whether any mesh surface intersects the finite segment."""
    origin = Vector(start)
    delta = Vector(end) - origin
    distance = delta.length
    if distance <= 1.0e-9:
        raise ValueError("Cannot test a zero-length mesh segment")
    direction = delta / distance
    for bvh in bvhs:
        location, _normal, _face_index, hit_distance = bvh.ray_cast(
            origin,
            direction,
            distance,
        )
        if location is not None and hit_distance < distance - 1.0e-5:
            return True
    return False


def point_in_polygon_xz(point, polygon) -> bool:
    """Classify an X/Z point against a simple polygon by odd/even parity."""
    x, z = point
    inside = False
    previous_x, previous_z = polygon[-1]
    for current_x, current_z in polygon:
        crosses = (current_z > z) != (previous_z > z)
        if crosses:
            crossing_x = (
                (previous_x - current_x)
                * (z - current_z)
                / (previous_z - current_z)
                + current_x
            )
            if x < crossing_x:
                inside = not inside
        previous_x, previous_z = current_x, current_z
    return inside


def sampled_opening_points(loops, spacing: float, predicate=None):
    """Return inset grid samples spanning each actual inlet/outlet polygon."""
    samples = []
    for loop in loops:
        minimum_x = min(point[0] for point in loop)
        maximum_x = max(point[0] for point in loop)
        minimum_z = min(point[1] for point in loop)
        maximum_z = max(point[1] for point in loop)
        x_count = max(1, math.ceil((maximum_x - minimum_x) / spacing))
        z_count = max(1, math.ceil((maximum_z - minimum_z) / spacing))
        for x_index in range(x_count):
            x = minimum_x + (x_index + 0.5) * (
                maximum_x - minimum_x
            ) / x_count
            for z_index in range(z_count):
                z = minimum_z + (z_index + 0.5) * (
                    maximum_z - minimum_z
                ) / z_count
                point = (x, z)
                if point_in_polygon_xz(point, loop) and (
                    predicate is None or predicate(point)
                ):
                    samples.append(point)
    return tuple(samples)


def face_down_contact_area(obj, outward_normal) -> float:
    """Measure the coplanar bed face used by face-down STL export."""
    normal = Vector(outward_normal).normalized()
    projections = [normal.dot(vertex.co) for vertex in obj.data.vertices]
    support_plane = max(projections)
    tolerance = 1.0e-4
    return sum(
        polygon.area
        for polygon in obj.data.polygons
        if all(
            abs(normal.dot(obj.data.vertices[index].co) - support_plane)
            <= tolerance
            for index in polygon.vertices
        )
    )


def bvh_point_is_inside(bvh, point) -> bool:
    """Classify a point by majority parity along three non-axial rays."""
    votes = []
    for coordinates in (
        (0.87317, 0.39821, 0.27943),
        (-0.71311, 0.49137, 0.25719),
        (0.18329, -0.92317, 0.33741),
    ):
        direction = Vector(coordinates).normalized()
        origin = Vector(point)
        intersections = 0
        for _ in range(256):
            location, _normal, _face_index, _distance = bvh.ray_cast(
                origin,
                direction,
                1000.0,
            )
            if location is None:
                break
            intersections += 1
            origin = location + direction * 1.0e-4
        else:
            raise RuntimeError(
                "Mesh point-classification ray did not leave the model"
            )
        votes.append(bool(intersections % 2))
    return sum(votes) >= 2


def sampled_fastener_datum_contact_area(back_bvh, insert_bvh, x, z) -> float:
    """Estimate common boss bearing area immediately across the datum."""
    radius = min(
        BACK_FASTENER_BOSS_DIAMETER,
        INSERT_FASTENER_BOSS_DIAMETER,
    ) / 2.0
    grid_size = 36
    cell_size = 2.0 * radius / grid_size
    plane_offset = min(0.01, SLEEVE_CAPTURE_ENGAGEMENT_DEPTH / 10.0)
    common_cells = 0
    for x_index in range(grid_size):
        sample_x = x - radius + (x_index + 0.5) * cell_size
        for z_index in range(grid_size):
            sample_z = z - radius + (z_index + 0.5) * cell_size
            if (sample_x - x) ** 2 + (sample_z - z) ** 2 > radius**2:
                continue
            back_inside = bvh_point_is_inside(
                back_bvh,
                (sample_x, insert_start_y() - plane_offset, sample_z),
            )
            insert_inside = bvh_point_is_inside(
                insert_bvh,
                (sample_x, insert_start_y() + plane_offset, sample_z),
            )
            common_cells += back_inside and insert_inside
    return common_cells * cell_size**2


def validate_sleeve_capture_mesh(back, insert) -> None:
    """Prove the final meshes contain the complete captured sleeve joint."""
    if not SLEEVE_CAPTURE_SLOT_ENABLED:
        return

    outer_width, outer_height, outer_radius = (
        sleeve_capture_groove_outer_dimensions()
    )
    inner_width, inner_height, inner_radius = (
        sleeve_capture_groove_inner_dimensions()
    )
    opening_width, opening_height, opening_radius = (
        sleeve_capture_opening_dimensions()
    )
    support_width, support_height, support_radius = (
        sleeve_capture_outer_support_dimensions()
    )
    axial_probe = min(
        SLEEVE_CAPTURE_BOTTOM_CLEARANCE,
        SLEEVE_CAPTURE_FLOOR_THICKNESS,
        SLEEVE_CAPTURE_ENGAGEMENT_DEPTH,
    ) / 4.0
    floor_below_y = sleeve_capture_groove_floor_y() - axial_probe
    floor_above_y = sleeve_capture_groove_floor_y() + axial_probe
    leading_before_y = insert_sleeve_leading_y() - axial_probe
    leading_after_y = insert_sleeve_leading_y() + axial_probe
    sleeve_y = (
        insert_sleeve_leading_y() + insert_start_y()
    ) / 2.0

    groove_outer_loop = rounded_rectangle_loop(
        outer_width,
        outer_height,
        outer_radius,
    )
    groove_inner_loop = rounded_rectangle_loop(
        inner_width,
        inner_height,
        inner_radius,
    )
    opening_loop = rounded_rectangle_loop(
        opening_width,
        opening_height,
        opening_radius,
    )
    support_loop = rounded_rectangle_loop(
        support_width,
        support_height,
        support_radius,
    )
    sleeve_outer_loop = rounded_rectangle_loop(
        INSERT_FRONT_WIDTH,
        INSERT_FRONT_HEIGHT,
        INSERT_OUTER_CORNER_RADIUS,
    )
    sleeve_inner_loop = rounded_rectangle_loop(
        insert_inner_width(),
        insert_inner_height(),
        insert_inner_corner_radius(),
    )

    loop_lengths = {
        len(loop)
        for loop in (
            groove_outer_loop,
            groove_inner_loop,
            opening_loop,
            support_loop,
            sleeve_outer_loop,
            sleeve_inner_loop,
        )
    }
    if len(loop_lengths) != 1:
        raise RuntimeError("Sleeve-capture validation contours do not align")

    back_samples = [("open_interior", (0.0, sleeve_y, 0.0), False)]
    insert_samples = []
    for index, points in enumerate(
        zip(
            groove_outer_loop,
            groove_inner_loop,
            opening_loop,
            support_loop,
            sleeve_outer_loop,
            sleeve_inner_loop,
        ),
        start=1,
    ):
        (
            groove_outer_point,
            groove_inner_point,
            opening_point,
            support_point,
            sleeve_outer_point,
            sleeve_inner_point,
        ) = points
        groove_point = (
            (groove_outer_point[0] + groove_inner_point[0]) / 2.0,
            (groove_outer_point[1] + groove_inner_point[1]) / 2.0,
        )
        lip_point = (
            (groove_inner_point[0] + opening_point[0]) / 2.0,
            (groove_inner_point[1] + opening_point[1]) / 2.0,
        )
        support_point_mid = (
            (support_point[0] + groove_outer_point[0]) / 2.0,
            (support_point[1] + groove_outer_point[1]) / 2.0,
        )
        sleeve_point = (
            (sleeve_outer_point[0] + sleeve_inner_point[0]) / 2.0,
            (sleeve_outer_point[1] + sleeve_inner_point[1]) / 2.0,
        )
        outer_face_clearance_point = (
            (sleeve_outer_point[0] + groove_outer_point[0]) / 2.0,
            (sleeve_outer_point[1] + groove_outer_point[1]) / 2.0,
        )
        inner_face_clearance_point = (
            (sleeve_inner_point[0] + groove_inner_point[0]) / 2.0,
            (sleeve_inner_point[1] + groove_inner_point[1]) / 2.0,
        )
        back_samples.extend(
            (
                (
                    f"continuous_floor_solid_{index}",
                    (groove_point[0], floor_below_y, groove_point[1]),
                    True,
                ),
                (
                    f"continuous_floor_clearance_{index}",
                    (groove_point[0], floor_above_y, groove_point[1]),
                    False,
                ),
                (
                    f"continuous_leading_clearance_{index}",
                    (groove_point[0], leading_before_y, groove_point[1]),
                    False,
                ),
                (
                    f"continuous_entered_groove_{index}",
                    (groove_point[0], leading_after_y, groove_point[1]),
                    False,
                ),
                (
                    f"continuous_outer_face_clearance_leading_{index}",
                    (
                        outer_face_clearance_point[0],
                        leading_after_y,
                        outer_face_clearance_point[1],
                    ),
                    False,
                ),
                (
                    f"continuous_inner_face_clearance_leading_{index}",
                    (
                        inner_face_clearance_point[0],
                        leading_after_y,
                        inner_face_clearance_point[1],
                    ),
                    False,
                ),
                (
                    f"continuous_outer_face_clearance_mid_{index}",
                    (
                        outer_face_clearance_point[0],
                        sleeve_y,
                        outer_face_clearance_point[1],
                    ),
                    False,
                ),
                (
                    f"continuous_inner_face_clearance_mid_{index}",
                    (
                        inner_face_clearance_point[0],
                        sleeve_y,
                        inner_face_clearance_point[1],
                    ),
                    False,
                ),
                (
                    f"continuous_deep_lip_{index}",
                    (lip_point[0], floor_above_y, lip_point[1]),
                    True,
                ),
                (
                    f"continuous_deep_support_{index}",
                    (
                        support_point_mid[0],
                        floor_above_y,
                        support_point_mid[1],
                    ),
                    True,
                ),
            )
        )
        insert_samples.extend(
            (
                (
                    f"continuous_sleeve_before_leading_{index}",
                    (sleeve_point[0], leading_before_y, sleeve_point[1]),
                    False,
                ),
                (
                    f"continuous_sleeve_after_leading_{index}",
                    (sleeve_point[0], leading_after_y, sleeve_point[1]),
                    True,
                ),
            )
        )

    if CASE_FASTENERS_ENABLED:
        passage_radius = INSERT_FASTENER_HOLE_DIAMETER * 0.4
        passage_y_positions = (leading_after_y, sleeve_y)
        for fastener_index, (x, z) in enumerate(
            CASE_FASTENER_POSITIONS_XZ,
            start=1,
        ):
            for y_index, passage_y in enumerate(passage_y_positions, start=1):
                for angle_index in range(16):
                    angle = 2.0 * math.pi * angle_index / 16.0
                    insert_samples.append(
                        (
                            f"fastener_{fastener_index}_passage_"
                            f"plane_{y_index}_ring_{angle_index + 1}",
                            (
                                x + passage_radius * math.cos(angle),
                                passage_y,
                                z + passage_radius * math.sin(angle),
                            ),
                            False,
                        )
                    )

    back_bvh = mesh_bvh(back)
    insert_bvh = mesh_bvh(insert)
    for obj, bvh, samples in (
        (back, back_bvh, back_samples),
        (insert, insert_bvh, insert_samples),
    ):
        failures = []
        for name, point, expected_inside in samples:
            actual_inside = bvh_point_is_inside(bvh, point)
            if actual_inside != expected_inside:
                failures.append(
                    f"{name} expected={'solid' if expected_inside else 'open'} "
                    f"actual={'solid' if actual_inside else 'open'} point={point}"
                )
        if failures:
            displayed_failures = failures[:12]
            if len(failures) > len(displayed_failures):
                displayed_failures.append(
                    f"... {len(failures) - len(displayed_failures)} more "
                    "sample failures"
                )
            raise RuntimeError(
                f"Final {obj.name} sleeve-capture mesh validation failed: "
                + "; ".join(displayed_failures)
            )

    contact_areas = []
    if (
        CASE_FASTENERS_ENABLED
        and BACK_FASTENER_TO_INSERT_SOCKET_GAP <= BOOLEAN_CLEANUP_DISTANCE
    ):
        for fastener_index, (x, z) in enumerate(
            CASE_FASTENER_POSITIONS_XZ,
            start=1,
        ):
            area = sampled_fastener_datum_contact_area(
                back_bvh,
                insert_bvh,
                x,
                z,
            )
            contact_areas.append(area)
            if area < BACK_FASTENER_MIN_DATUM_CONTACT_AREA:
                raise RuntimeError(
                    "Final sleeve-capture groove leaves insufficient boss "
                    f"contact at fastener {fastener_index}: sampled "
                    f"{area:.2f} mm2; required "
                    f"{BACK_FASTENER_MIN_DATUM_CONTACT_AREA:.2f} mm2"
                )

    print(
        "SLEEVE_CAPTURE_FINAL_MESH PASS "
        f"back_samples={len(back_samples)} insert_samples={len(insert_samples)} "
        f"minimum_boss_contact_area="
        f"{min(contact_areas) if contact_areas else 0.0:.2f}mm2"
    )


def validate_object(obj) -> None:
    recalc_normals(obj)
    non_manifold = non_manifold_edge_count(obj)
    shells = connected_shell_count(obj)
    print(
        f"{obj.name}: vertices={len(obj.data.vertices)} "
        f"polygons={len(obj.data.polygons)} "
        f"non_manifold_edges={non_manifold} connected_shells={shells}"
    )
    if non_manifold:
        raise RuntimeError(f"{obj.name} has {non_manifold} non-manifold edges")
    if shells != 1:
        raise RuntimeError(f"{obj.name} has {shells} disconnected shells")


def validate_baffle_line_of_sight(back, tray, lid) -> None:
    """Prove the installed finite baffles block sampled inlet/outlet rays."""
    inlet_radius = BAFFLE_INLET_DIAMETER / 2.0
    inlet_points = sampled_opening_points(
        baffle_inlet_loops(),
        3.0,
        predicate=lambda point: math.hypot(
            point[0] - FAN_CENTER_X,
            point[1] - FAN_CENTER_Z,
        )
        < inlet_radius - 0.05,
    )
    outlet_points = sampled_opening_points(baffle_outlet_loops(), 4.0)
    if not inlet_points or not outlet_points:
        raise RuntimeError("The acoustic visibility sampler found no openings")

    tray_bvh = mesh_bvh(tray)
    lid_bvh = mesh_bvh(lid)
    cartridge_bvhs = (tray_bvh, lid_bvh)
    reviewer_rays = (
        ((-4.0, -5.21, 14.0), (-4.0, 14.01, 3.0)),
        ((0.0, -5.30, 18.0), (0.0, 14.10, 2.0)),
        ((-4.0, -5.21, 17.4), (-4.0, 14.01, 5.3)),
    )
    for index, (start, end) in enumerate(reviewer_rays, start=1):
        if not bvh_segment_is_blocked(cartridge_bvhs, start, end):
            raise RuntimeError(
                f"Acoustic reviewer ray {index} bypasses the cartridge: "
                f"{start} -> {end}"
            )

    assembled_bvhs = (mesh_bvh(back), tray_bvh, lid_bvh)
    rear_y = BAFFLE_REAR_Y - 0.10
    front_y = BAFFLE_FRONT_Y + 0.10
    tested_segments = 0
    for inlet_x, inlet_z in inlet_points:
        start = (inlet_x, rear_y, inlet_z)
        for outlet_x, outlet_z in outlet_points:
            end = (outlet_x, front_y, outlet_z)
            tested_segments += 1
            if not bvh_segment_is_blocked(assembled_bvhs, start, end):
                raise RuntimeError(
                    "A sampled direct acoustic path bypasses the installed "
                    f"cartridge: {start} -> {end}"
                )

    step_x, _step_z = baffle_stop_relief_corner()
    relief_inlet = (FAN_CENTER_X - 13.0, rear_y, -12.5)
    relief_outlet = (
        max(-BAFFLE_OUTLET_WIDTH / 2.0 + 0.25, step_x - 4.0),
        front_y,
        -BAFFLE_OUTLET_HEIGHT / 2.0 + 0.5,
    )
    if not bvh_segment_is_blocked(assembled_bvhs, relief_inlet, relief_outlet):
        raise RuntimeError(
            "The camera-stop relief corner permits a direct acoustic path"
        )
    print(
        "BAFFLE_LINE_OF_SIGHT PASS "
        f"sampled_segments={tested_segments} "
        f"required_inlet_abs_z="
        f"{baffle_acoustic_visibility_required_inlet_z():.2f}mm "
        f"available_inlet_radius={inlet_radius:.2f}mm"
    )


def validate_baffle_assembled_collisions(back, tray, lid) -> None:
    """Reject shell/cartridge intersections outside latches and TPU seal."""
    tongue_left = -BAFFLE_SNAP_TONGUE_WIDTH_X / 2.0
    tongue_right = BAFFLE_SNAP_TONGUE_WIDTH_X / 2.0
    for name, x0, x1, _z0, _z1, attachment in CAMERA_STOP_SPECS:
        if attachment not in {"top", "bottom"}:
            continue
        if max(tongue_left, x0) < min(tongue_right, x1):
            raise RuntimeError(
                f"The centerline baffle snap overlaps camera stop {name}"
            )

    back_bvh = mesh_bvh(back)
    intentional_pairs = 0
    intentional_seal_pairs = 0
    unexpected = []
    join_overlap = baffle_boolean_join_overlap()
    allowed_y_min = (
        baffle_snap_hook_y()
        - BAFFLE_SNAP_RECEIVER_DEPTH_Y / 2.0
        - join_overlap
        - 0.50
    )
    allowed_y_max = (
        BAFFLE_SNAP_RECEIVER_Y
        + BAFFLE_SNAP_RECEIVER_DEPTH_Y / 2.0
        + join_overlap
        + 0.50
    )
    for component in (tray, lid):
        pairs = mesh_bvh(component).overlap(back_bvh)
        for component_face_index, _back_face_index in pairs:
            if component_face_index >= len(component.data.polygons):
                unexpected.append((component.name, component_face_index))
                continue
            center = component.data.polygons[component_face_index].center
            intentional_latch_overlap = (
                component is tray
                and abs(center.x)
                <= BAFFLE_SNAP_TONGUE_WIDTH_X / 2.0 + 0.50
                and allowed_y_min <= center.y <= allowed_y_max
                and abs(center.z) >= BAFFLE_BODY_HEIGHT / 2.0
            )
            seal_radius = math.hypot(
                center.x - FAN_CENTER_X,
                center.z - FAN_CENTER_Z,
            )
            intentional_integral_seal_overlap = (
                component is tray
                and baffle_gasket_is_integral()
                and center.y <= BAFFLE_REAR_Y + join_overlap
                and BAFFLE_GASKET_INNER_DIAMETER / 2.0 - 0.50
                <= seal_radius
                <= BAFFLE_GASKET_OUTER_DIAMETER / 2.0 + 0.50
            )
            if intentional_latch_overlap:
                intentional_pairs += 1
            elif intentional_integral_seal_overlap:
                intentional_seal_pairs += 1
            else:
                unexpected.append(
                    (
                        component.name,
                        component_face_index,
                        tuple(round(value, 3) for value in center),
                    )
                )
    tray_lid_pairs = mesh_bvh(tray).overlap(mesh_bvh(lid))
    if tray_lid_pairs:
        unexpected.append(("tray_lid", len(tray_lid_pairs)))
    if unexpected:
        raise RuntimeError(
            "The assembled baffle has non-latch mesh collisions: "
            f"{unexpected[:8]}"
        )
    if intentional_pairs == 0:
        raise RuntimeError("The assembled baffle snap does not engage its receivers")
    if baffle_gasket_is_integral() and intentional_seal_pairs == 0:
        raise RuntimeError("The integral TPU seal has no fan-pad compression")
    print(
        "BAFFLE_ASSEMBLED_COLLISIONS PASS "
        f"intentional_latch_triangle_pairs={intentional_pairs} "
        f"intentional_seal_triangle_pairs={intentional_seal_pairs} "
        "unexpected_triangle_pairs=0"
    )


def validate_baffle_lid_insertion_clearance(tray, lid) -> None:
    """Sweep the lid outward from its seat and reject hidden intersections."""
    offsets_x = (0.0, 0.10, 0.25, 0.50, 1.0, 2.0, 4.0)
    intersections = []
    for offset_x in offsets_x:
        moved_lid = lid.copy()
        moved_lid.data = lid.data.copy()
        bpy.context.collection.objects.link(moved_lid)
        moved_lid_name = moved_lid.name
        try:
            for vertex in moved_lid.data.vertices:
                vertex.co.x += offset_x
            volume = mesh_intersection_volume(
                tray,
                moved_lid,
                f"Baffle_Lid_Insertion_Clearance_{offset_x:.2f}",
            )
            intersections.append((offset_x, volume))
        finally:
            temporary = bpy.data.objects.get(moved_lid_name)
            if temporary is not None:
                bpy.data.objects.remove(temporary, do_unlink=True)
    collision_tolerance = 1.0e-5
    failures = [
        (offset_x, volume)
        for offset_x, volume in intersections
        if volume > collision_tolerance
    ]
    if failures:
        raise RuntimeError(
            "The baffle lid intersects the tray along its insertion path: "
            + ", ".join(
                f"offset={offset_x:.2f}mm volume={volume:.6f}mm3"
                for offset_x, volume in failures
            )
        )
    print(
        "BAFFLE_LID_INSERTION_CLEARANCE PASS "
        f"samples={len(intersections)} max_intersection_volume="
        f"{max(volume for _offset, volume in intersections):.6f}mm3"
    )


def validate_baffle_cartridge(back, components) -> None:
    if not BAFFLE_CARTRIDGE_ENABLED:
        if components:
            raise RuntimeError("Disabled baffle cartridge unexpectedly built parts")
        return
    expected_parts = 2 if baffle_gasket_is_integral() else 3
    if len(components) != expected_parts:
        raise RuntimeError(
            "The baffle cartridge requires tray/lid and, for a rigid tray, "
            "a separate TPU gasket"
        )
    tray, lid = components[:2]
    gasket = components[2] if len(components) == 3 else None
    for component in components:
        validate_object(component)
    validate_baffle_line_of_sight(back, tray, lid)
    validate_baffle_assembled_collisions(back, tray, lid)
    validate_baffle_lid_insertion_clearance(tray, lid)

    print_contact_areas = [
        face_down_contact_area(tray, baffle_left_face_outward_normal()),
        face_down_contact_area(lid, baffle_right_face_outward_normal()),
    ]
    minimum_contact_areas = [600.0, 600.0]
    if gasket is not None:
        print_contact_areas.append(
            face_down_contact_area(gasket, (0.0, -1.0, 0.0))
        )
        minimum_contact_areas.append(90.0)
    if any(
        actual < minimum
        for actual, minimum in zip(
            print_contact_areas,
            minimum_contact_areas,
        )
    ):
        raise RuntimeError(
            "A baffle component does not have its intended broad print-bed "
            "print-bed face: "
            f"areas={print_contact_areas}, minimums={minimum_contact_areas}"
        )

    tolerance = 1.0e-4
    key_start_y = (
        BAFFLE_REAR_Y
        + BAFFLE_WALL_THICKNESS
        + BAFFLE_LID_FIT_CLEARANCE
    )
    key_end_y = (
        BAFFLE_FRONT_Y
        - BAFFLE_WALL_THICKNESS
        - BAFFLE_LID_FIT_CLEARANCE
    )
    lid_loops = (
        baffle_lid_outer_loop_at_y(BAFFLE_REAR_Y),
        baffle_lid_outer_loop_at_y(BAFFLE_FRONT_Y),
        baffle_lid_key_loop_at_y(key_start_y),
        baffle_lid_key_loop_at_y(key_end_y),
    )
    expected_lid_bounds = (
        min(point[0] for loop in lid_loops for point in loop),
        BAFFLE_REAR_Y,
        min(point[1] for loop in lid_loops for point in loop),
        max(point[0] for loop in lid_loops for point in loop),
        BAFFLE_FRONT_Y,
        max(point[1] for loop in lid_loops for point in loop),
    )
    lid_coordinates = [vertex.co for vertex in lid.data.vertices]
    actual_lid_bounds = (
        min(coordinate.x for coordinate in lid_coordinates),
        min(coordinate.y for coordinate in lid_coordinates),
        min(coordinate.z for coordinate in lid_coordinates),
        max(coordinate.x for coordinate in lid_coordinates),
        max(coordinate.y for coordinate in lid_coordinates),
        max(coordinate.z for coordinate in lid_coordinates),
    )
    lid_bounds_mismatch = any(
        abs(actual_lid_bounds[index] - expected_lid_bounds[index])
        > tolerance
        for index in range(6)
    )
    if lid_bounds_mismatch:
        raise RuntimeError(
            "Baffle lid bounds do not match its plate/key profiles: "
            f"actual={actual_lid_bounds}, expected={expected_lid_bounds}"
        )

    tray_min_y = min(vertex.co.y for vertex in tray.data.vertices)
    tray_max_y = max(vertex.co.y for vertex in tray.data.vertices)
    expected_tray_min_y = (
        BAFFLE_REAR_Y - baffle_gasket_exposed_height()
        if baffle_gasket_is_integral()
        else BAFFLE_REAR_Y
    )
    if (
        abs(tray_min_y - expected_tray_min_y) > tolerance
        or abs(tray_max_y - BAFFLE_FRONT_Y) > tolerance
    ):
        raise RuntimeError(
            "Baffle tray axial bounds do not match rear/front planes: "
            f"y=({tray_min_y:.5f}, {tray_max_y:.5f}) mm"
        )

    tray_bvh = mesh_bvh(tray)
    lid_bvh = mesh_bvh(lid)
    first_left, first_right, _bottom, _top = (
        baffle_effective_airway_bounds_at_y(BAFFLE_FIRST_Y)
    )
    probe_x = (first_left + first_right) / 2.0
    inlet_probe_span = baffle_slot_spans(
        BAFFLE_INLET_DIAMETER,
        BAFFLE_INLET_SLOT_COUNT,
        BAFFLE_INLET_SEPARATOR_THICKNESS_Z,
        FAN_CENTER_Z,
    )[0]
    inlet_probe_z = sum(inlet_probe_span) / 2.0
    outlet_probe_span = baffle_slot_spans(
        BAFFLE_OUTLET_HEIGHT,
        BAFFLE_OUTLET_SLOT_COUNT,
        BAFFLE_OUTLET_SEPARATOR_THICKNESS_Z,
    )[0]
    outlet_probe_z = sum(outlet_probe_span) / 2.0
    probes = (
        (
            "rear_inlet_open",
            (
                FAN_CENTER_X,
                BAFFLE_REAR_Y + BAFFLE_WALL_THICKNESS / 2.0,
                inlet_probe_z,
            ),
            False,
        ),
        (
            "rear_face_solid",
            (
                FAN_CENTER_X,
                BAFFLE_REAR_Y + BAFFLE_WALL_THICKNESS / 2.0,
                BAFFLE_BODY_HEIGHT / 2.0 - BAFFLE_WALL_THICKNESS / 2.0,
            ),
            True,
        ),
        (
            "first_blocker_solid",
            (probe_x, BAFFLE_FIRST_Y, 0.0),
            True,
        ),
        (
            "first_top_lane_open",
            (
                probe_x,
                BAFFLE_FIRST_Y,
                BAFFLE_FIRST_BLOCKER_HEIGHT_Z / 2.0
                + (
                    BAFFLE_BODY_HEIGHT
                    - 2.0 * BAFFLE_WALL_THICKNESS
                    - BAFFLE_FIRST_BLOCKER_HEIGHT_Z
                )
                / 4.0,
            ),
            False,
        ),
        (
            "second_center_lane_open",
            (probe_x, BAFFLE_SECOND_Y, 0.0),
            False,
        ),
        (
            "second_top_member_solid",
            (
                probe_x,
                BAFFLE_SECOND_Y,
                BAFFLE_SECOND_OPENING_HEIGHT_Z / 2.0 + 2.0,
            ),
            True,
        ),
        (
            "forward_outlet_open",
            (
                0.0,
                BAFFLE_FRONT_Y - BAFFLE_WALL_THICKNESS / 2.0,
                outlet_probe_z,
            ),
            False,
        ),
        (
            "forward_face_solid",
            (
                0.0,
                BAFFLE_FRONT_Y - BAFFLE_WALL_THICKNESS / 2.0,
                BAFFLE_OUTLET_HEIGHT / 2.0 + 2.0,
            ),
            True,
        ),
    )
    failures = [
        name
        for name, point, expected_inside in probes
        if bvh_point_is_inside(tray_bvh, point) != expected_inside
    ]
    if failures:
        raise RuntimeError(
            "Baffle tray internal-geometry validation failed: "
            + ", ".join(failures)
        )

    if baffle_gasket_is_integral():
        slot_entry_x = baffle_lid_key_inner_x_at_y(BAFFLE_FIRST_Y)
        tab_probe = (
            slot_entry_x
            + BAFFLE_TPU_LID_BLOCKER_SLOT_ENGAGEMENT_X / 2.0,
            BAFFLE_FIRST_Y,
            0.0,
        )
        slot_probe = (
            slot_entry_x + BAFFLE_TPU_LID_BLOCKER_SLOT_DEPTH_X / 2.0,
            BAFFLE_FIRST_Y,
            0.0,
        )
        blind_clearance_probe = (
            slot_entry_x
            + (
                BAFFLE_TPU_LID_BLOCKER_SLOT_ENGAGEMENT_X
                + BAFFLE_TPU_LID_BLOCKER_SLOT_DEPTH_X
            )
            / 2.0,
            BAFFLE_FIRST_Y,
            0.0,
        )
        slot_floor_probe = (
            slot_entry_x + BAFFLE_TPU_LID_BLOCKER_SLOT_DEPTH_X + 0.10,
            BAFFLE_FIRST_Y,
            0.0,
        )
        side_wall_y = (
            BAFFLE_FIRST_Y
            + BAFFLE_INTERNAL_THICKNESS_Y / 2.0
            + BAFFLE_TPU_LID_BLOCKER_SLOT_CLEARANCE_Y
            + 0.10
        )
        side_wall_probe = (
            baffle_lid_key_inner_x_at_y(side_wall_y)
            + BAFFLE_TPU_LID_BLOCKER_SLOT_DEPTH_X / 2.0,
            side_wall_y,
            0.0,
        )
        end_wall_probe = (
            slot_entry_x + BAFFLE_TPU_LID_BLOCKER_SLOT_DEPTH_X / 2.0,
            BAFFLE_FIRST_Y,
            BAFFLE_FIRST_BLOCKER_HEIGHT_Z / 2.0
            + BAFFLE_TPU_LID_BLOCKER_SLOT_CLEARANCE_Z
            + 0.10,
        )
        if not bvh_point_is_inside(tray_bvh, tab_probe):
            raise RuntimeError("The TPU first-blocker lid tab is missing")
        if bvh_point_is_inside(lid_bvh, slot_probe):
            raise RuntimeError("The TPU lid blocker locating slot is missing")
        if (
            bvh_point_is_inside(tray_bvh, blind_clearance_probe)
            or bvh_point_is_inside(lid_bvh, blind_clearance_probe)
        ):
            raise RuntimeError(
                "The TPU blocker tab lacks clearance before the slot floor"
            )
        if not all(
            bvh_point_is_inside(lid_bvh, point)
            for point in (slot_floor_probe, side_wall_probe, end_wall_probe)
        ):
            raise RuntimeError(
                "The TPU lid blocker slot lacks a closed floor or locating wall"
            )

        print(
            "BAFFLE_TPU_FIRST_BLOCKER_LID_SLOT PASS count=1 "
            f"depth={BAFFLE_TPU_LID_BLOCKER_SLOT_DEPTH_X:.2f}mm "
            f"engagement={BAFFLE_TPU_LID_BLOCKER_SLOT_ENGAGEMENT_X:.2f}mm "
            f"clearance_y={BAFFLE_TPU_LID_BLOCKER_SLOT_CLEARANCE_Y:.2f}mm "
            f"clearance_z={BAFFLE_TPU_LID_BLOCKER_SLOT_CLEARANCE_Z:.2f}mm"
        )

    frame_rear_y, frame_front_y = baffle_second_end_frame_y_bounds()
    frame_y_samples = (
        frame_rear_y + 0.20,
        baffle_second_end_frame_center_y(),
        frame_front_y - 0.20,
    )
    half_second_opening = BAFFLE_SECOND_OPENING_HEIGHT_Z / 2.0
    connector_z_samples = (
        -half_second_opening - 1.0,
        half_second_opening + 1.0,
    )
    connector_failures = []
    pocket_failures = []
    for y in frame_y_samples:
        frame_entry_x = baffle_lid_key_inner_x_at_y(y)
        connector_x_samples = (
            frame_entry_x - BAFFLE_SECOND_END_FRAME_CONNECTION_X + 0.15,
            frame_entry_x - BAFFLE_SECOND_END_FRAME_CONNECTION_X / 2.0,
            frame_entry_x - 0.15,
            frame_entry_x
            + BAFFLE_SECOND_END_FRAME_LID_ENGAGEMENT_X
            - 0.10,
        )
        for side_index, z in enumerate(connector_z_samples, start=1):
            for x_index, x in enumerate(connector_x_samples, start=1):
                point = (x, y, z)
                if not bvh_point_is_inside(tray_bvh, point):
                    connector_failures.append(
                        f"side_{side_index}_y_{y:.2f}_x_{x_index}"
                    )
                if bvh_point_is_inside(lid_bvh, point):
                    pocket_failures.append(
                        f"side_{side_index}_y_{y:.2f}_x_{x_index}"
                    )
    if connector_failures:
        raise RuntimeError(
            "A camera-side baffle lacks its continuous 3 mm tray-frame "
            "connection: " + ", ".join(connector_failures[:8])
        )
    if pocket_failures:
        raise RuntimeError(
            "A lid pocket does not clear its camera-side baffle end return: "
            + ", ".join(pocket_failures[:8])
        )

    frame_center_y = baffle_second_end_frame_center_y()
    frame_entry_x = baffle_lid_key_inner_x_at_y(frame_center_y)
    blind_clearance_probes = tuple(
        (
            frame_entry_x
            + (
                BAFFLE_SECOND_END_FRAME_LID_ENGAGEMENT_X
                + BAFFLE_SECOND_END_FRAME_LID_POCKET_DEPTH_X
            )
            / 2.0,
            frame_center_y,
            z,
        )
        for z in connector_z_samples
    )
    pocket_floor_probes = tuple(
        (
            frame_entry_x
            + BAFFLE_SECOND_END_FRAME_LID_POCKET_DEPTH_X
            + 0.10,
            frame_center_y,
            z,
        )
        for z in connector_z_samples
    )
    pocket_rear_y, pocket_front_y = baffle_second_end_frame_y_bounds(
        BAFFLE_SECOND_END_FRAME_LID_CLEARANCE_Y
    )
    pocket_wall_probes = tuple(
        (
            baffle_lid_key_inner_x_at_y(y)
            + BAFFLE_SECOND_END_FRAME_LID_POCKET_DEPTH_X / 2.0,
            y,
            z,
        )
        for z in connector_z_samples
        for y in (pocket_rear_y - 0.10, pocket_front_y + 0.10)
    )
    if any(
        bvh_point_is_inside(tray_bvh, point)
        or bvh_point_is_inside(lid_bvh, point)
        for point in blind_clearance_probes
    ):
        raise RuntimeError(
            "A camera-side end return lacks clearance before its lid-pocket "
            "floor"
        )
    if not all(
        bvh_point_is_inside(lid_bvh, point)
        for point in (*pocket_floor_probes, *pocket_wall_probes)
    ):
        raise RuntimeError(
            "A camera-side end-return lid pocket lacks a closed floor or "
            "axial locating wall"
        )
    lid_spine_probe = (
        frame_entry_x + BAFFLE_SECOND_END_FRAME_LID_POCKET_DEPTH_X / 2.0,
        frame_center_y,
        0.0,
    )
    if not bvh_point_is_inside(lid_bvh, lid_spine_probe):
        raise RuntimeError(
            "The paired end-return pockets interrupt the lid's continuous "
            "center spine"
        )
    measured_member_overlap_x = (
        BAFFLE_SECOND_END_FRAME_CONNECTION_X - BAFFLE_LID_FIT_CLEARANCE
    )
    print(
        "BAFFLE_SECOND_END_RETURNS PASS sides=2 continuous_lid_spine=True "
        f"connection_x={BAFFLE_SECOND_END_FRAME_CONNECTION_X:.2f}mm "
        f"member_overlap_x={measured_member_overlap_x:.2f}mm "
        f"axial_pad={BAFFLE_SECOND_END_FRAME_DEPTH_Y:.2f}mm "
        f"lid_engagement={BAFFLE_SECOND_END_FRAME_LID_ENGAGEMENT_X:.2f}mm "
        f"lid_clearance_y={BAFFLE_SECOND_END_FRAME_LID_CLEARANCE_Y:.2f}mm "
        f"lid_clearance_z={BAFFLE_SECOND_END_FRAME_LID_CLEARANCE_Z:.2f}mm "
        f"lid_min_wall={BAFFLE_SECOND_END_FRAME_LID_MIN_WALL:.2f}mm"
    )

    front_wall_probe_y = BAFFLE_FRONT_Y - BAFFLE_WALL_THICKNESS / 2.0
    half_outlet_width = BAFFLE_OUTLET_WIDTH / 2.0
    front_left, _front_right, _bottom, _top = baffle_body_bounds_at_y(
        front_wall_probe_y
    )
    front_wall_side_band_probes = (
        (
            (
                front_left
                + BAFFLE_WALL_THICKNESS
                - half_outlet_width
            )
            / 2.0,
            front_wall_probe_y,
            0.0,
        ),
        (
            (
                half_outlet_width
                + baffle_tray_side_opening_x_at_y(front_wall_probe_y)
            )
            / 2.0,
            front_wall_probe_y,
            0.0,
        ),
    )
    if not all(
        bvh_point_is_inside(tray_bvh, point)
        for point in front_wall_side_band_probes
    ):
        raise RuntimeError(
            "The camera-facing outlet breaks a solid front-wall side band"
        )

    seal = tray if gasket is None else gasket
    gasket_bvh = mesh_bvh(seal)
    gasket_mid_y = (
        BAFFLE_REAR_Y - baffle_gasket_exposed_height() / 2.0
        if gasket is None
        else fan_pad_inner_y() + BAFFLE_GASKET_THICKNESS_Y / 2.0
    )
    if bvh_point_is_inside(
        gasket_bvh,
        (FAN_CENTER_X, gasket_mid_y, FAN_CENTER_Z),
    ):
        raise RuntimeError("The baffle gasket obstructs the fan inlet")
    seal_probe_z = (
        BAFFLE_GASKET_OUTER_DIAMETER
        + BAFFLE_GASKET_INNER_DIAMETER
    ) / 4.0
    if not bvh_point_is_inside(
        gasket_bvh,
        (FAN_CENTER_X, gasket_mid_y, seal_probe_z),
    ):
        raise RuntimeError("The baffle inlet seal ring is missing")
    for index, (x, z) in enumerate(fan_hole_positions(), start=1):
        if bvh_point_is_inside(gasket_bvh, (x, gasket_mid_y, z)):
            raise RuntimeError(
                f"The baffle gasket does not clear fan boss {index}"
            )
    if gasket is not None:
        gasket_cross_section_area = (
            mesh_volume(gasket) / BAFFLE_GASKET_THICKNESS_Y
        )
        expected_compression_volume = (
            gasket_cross_section_area * baffle_gasket_compression()
        )
        actual_compression_volume = mesh_intersection_volume(
            tray,
            gasket,
            "Baffle_Gasket_Tray_Compression_Validation",
        )
        compression_volume_tolerance = max(
            0.01,
            expected_compression_volume * 0.005,
        )
        if (
            abs(actual_compression_volume - expected_compression_volume)
            > compression_volume_tolerance
        ):
            raise RuntimeError(
                "The groove floor does not back the rigid-tray gasket at its "
                "configured compression: "
                f"actual={actual_compression_volume:.6f} mm3 "
                f"expected={expected_compression_volume:.6f} mm3"
            )
        print(
            "BAFFLE_GASKET_GROOVE_SUPPORT PASS "
            f"compression_volume={actual_compression_volume:.6f}mm3 "
            f"expected={expected_compression_volume:.6f}mm3"
        )
    if not baffle_gasket_is_integral():
        groove_mid_y = BAFFLE_REAR_Y + BAFFLE_GASKET_GROOVE_DEPTH_Y / 2.0
        groove_floor_probe_y = (
            BAFFLE_REAR_Y
            + BAFFLE_GASKET_GROOVE_DEPTH_Y
            + (
                BAFFLE_WALL_THICKNESS
                - BAFFLE_GASKET_GROOVE_DEPTH_Y
            )
            / 2.0
        )
        groove_probe = (FAN_CENTER_X, groove_mid_y, seal_probe_z)
        groove_outer_wall_probe = (
            FAN_CENTER_X,
            groove_mid_y,
            BAFFLE_GASKET_OUTER_DIAMETER / 2.0
            + BAFFLE_GASKET_GROOVE_RADIAL_CLEARANCE
            + 0.10,
        )
        floor_probe = (FAN_CENTER_X, groove_floor_probe_y, seal_probe_z)
        if bvh_point_is_inside(tray_bvh, groove_probe):
            raise RuntimeError("The rigid tray gasket locating groove is missing")
        if not bvh_point_is_inside(tray_bvh, groove_outer_wall_probe):
            raise RuntimeError(
                "The rigid tray gasket groove lacks its outer locating wall"
            )
        if not bvh_point_is_inside(tray_bvh, floor_probe):
            raise RuntimeError("The rigid tray gasket groove lacks a solid floor")
        seal_mid_radius = (
            BAFFLE_GASKET_OUTER_DIAMETER
            + BAFFLE_GASKET_INNER_DIAMETER
        ) / 4.0
        floor_support_y = (
            BAFFLE_REAR_Y + BAFFLE_GASKET_GROOVE_DEPTH_Y + 0.10
        )
        supported_samples = 0
        for sample_index in range(72):
            angle = 2.0 * math.pi * sample_index / 72.0
            x = FAN_CENTER_X + seal_mid_radius * math.cos(angle)
            z = FAN_CENTER_Z + seal_mid_radius * math.sin(angle)
            inside_boss_scallop = any(
                math.hypot(x - boss_x, z - boss_z)
                <= FAN_HOLE_BOSS_DIAMETER / 2.0
                + BAFFLE_GASKET_BOSS_CLEARANCE
                for boss_x, boss_z in fan_hole_positions()
            )
            if inside_boss_scallop:
                continue
            supported_samples += 1
            if bvh_point_is_inside(tray_bvh, (x, groove_mid_y, z)):
                raise RuntimeError(
                    "The rigid tray gasket groove channel is obstructed"
                )
            if not bvh_point_is_inside(
                tray_bvh,
                (x, floor_support_y, z),
            ):
                raise RuntimeError(
                    "The rigid tray gasket is not continuously backed by its "
                    "groove floor"
                )
        if supported_samples < 48:
            raise RuntimeError("Too few gasket-floor support samples were tested")

    back_bvh = mesh_bvh(back)
    receiver_half_height = dome_cavity_half_height_at_y(
        BAFFLE_SNAP_RECEIVER_Y
    )
    for side in (-1.0, 1.0):
        receiver_probe = (
            baffle_snap_auxiliary_center_x_at_y(
                BAFFLE_SNAP_RECEIVER_Y,
                BAFFLE_SNAP_RECEIVER_DEPTH_Y
                + 2.0 * baffle_boolean_join_overlap(),
            ),
            BAFFLE_SNAP_RECEIVER_Y,
            side
            * (
                receiver_half_height
                - BAFFLE_SNAP_RECEIVER_PROJECTION_Z / 2.0
            ),
        )
        if not bvh_point_is_inside(back_bvh, receiver_probe):
            raise RuntimeError("A back-shell baffle receiver is missing")

    inlet_area = baffle_inlet_effective_area()
    first_area, second_area, outlet_area = baffle_throat_areas()
    print(
        "FAN_ACOUSTIC_BAFFLE_CARTRIDGE PASS "
        f"material={BAFFLE_CARTRIDGE_MATERIAL_MODE} "
        f"parts={len(components)} seal="
        f"{'integral_TPU' if gasket is None else 'groove_located_TPU'} "
        "bulk_internal_supports_avoided=True "
        f"localized_support_advisory=stop_relief_bridge_and_snap_roots "
        f"stop_relief_bridge={BAFFLE_FRONT_Y - BAFFLE_REAR_Y:.2f}mm "
        f"body_depth={BAFFLE_FRONT_Y - BAFFLE_REAR_Y:.2f}mm "
        f"camera_clearance={baffle_camera_clearance():.2f}mm "
        f"sleeve_clearance={baffle_sleeve_clearance():.2f}mm "
        f"line_of_sight_required_inlet_abs_z="
        f"{baffle_acoustic_visibility_required_inlet_z():.2f}mm "
        f"throat_areas=({inlet_area:.1f},{first_area:.1f},{second_area:.1f},"
        f"{outlet_area:.1f})mm2 outlet_slots={BAFFLE_OUTLET_SLOT_COUNT} "
        f"outlet_separator_post={BAFFLE_OUTLET_SLOT_COUNT > 1} "
        "outlet_front_wall_side_bands=("
        + ",".join(
            f"{width:.2f}"
            for width in baffle_outlet_front_wall_side_band_widths()
        )
        + ")mm "
        "gasket_compression="
        f"{baffle_gasket_compression():.2f}mm "
        f"snap_interference={baffle_snap_resolved_interference():.2f}mm "
        "print_bed_contact_areas=("
        + ",".join(f"{area:.1f}" for area in print_contact_areas)
        + ")mm2"
    )


def validate_captive_buttons(buttons) -> None:
    """Check local dimensions and the assembled axes/port alignment."""
    left_button, top_button = buttons
    validate_object(left_button)
    validate_object(top_button)

    coordinates = [vertex.co for vertex in top_button.data.vertices]
    minimum_z = min(coordinate.z for coordinate in coordinates)
    maximum_z = max(coordinate.z for coordinate in coordinates)
    maximum_radius = max(
        math.hypot(coordinate.x, coordinate.y)
        for coordinate in coordinates
    )
    expected_radius = BUTTON_INNER_FLANGE_DIAMETER / 2.0
    dimension_tolerance = 1.0e-5
    if (
        abs(minimum_z) > dimension_tolerance
        or abs(maximum_z - BUTTON_TOTAL_HEIGHT) > dimension_tolerance
        or abs(maximum_radius - expected_radius) > dimension_tolerance
    ):
        raise RuntimeError(
            "Captive-button mesh bounds do not match its configured profile: "
            f"z=({minimum_z:.5f}, {maximum_z:.5f}) mm, "
            f"radius={maximum_radius:.5f} mm"
        )

    expected_locations = (
        Vector(
            (
                -insert_inner_width() / 2.0
                + BUTTON_INNER_FLANGE_THICKNESS,
                insert_start_y() + LEFT_ROUND_PORT_Y_OFFSET,
                LEFT_ROUND_PORT_Z,
            )
        ),
        Vector(
            (
                TOP_PORT_X,
                insert_start_y() + TOP_PORT_Y_OFFSET,
                insert_inner_height() / 2.0
                - BUTTON_INNER_FLANGE_THICKNESS,
            )
        ),
    )
    expected_axes = (Vector((-1.0, 0.0, 0.0)), Vector((0.0, 0.0, 1.0)))
    for button, expected_location, expected_axis in zip(
        buttons,
        expected_locations,
        expected_axes,
    ):
        actual_axis = button.rotation_euler.to_matrix() @ Vector((0.0, 0.0, 1.0))
        if (
            (button.location - expected_location).length > dimension_tolerance
            or (actual_axis - expected_axis).length > dimension_tolerance
        ):
            raise RuntimeError(
                f"{button.name} is not aligned with its configured sleeve port"
            )

    stem_clearances = (
        (LEFT_ROUND_PORT_DIAMETER - BUTTON_STEM_DIAMETER) / 2.0,
        (TOP_PORT_DIAMETER - BUTTON_STEM_DIAMETER) / 2.0,
    )
    rim_interferences = (
        (BUTTON_RETENTION_RIM_DIAMETER - LEFT_ROUND_PORT_DIAMETER) / 2.0,
        (BUTTON_RETENTION_RIM_DIAMETER - TOP_PORT_DIAMETER) / 2.0,
    )
    print(
        "CAPTIVE_BUTTONS PASS count=2 material=TPU "
        f"stem_diameter={BUTTON_STEM_DIAMETER:.2f}mm "
        f"total_height={BUTTON_TOTAL_HEIGHT:.2f}mm "
        f"inner_flange={BUTTON_INNER_FLANGE_DIAMETER:.2f}x"
        f"{BUTTON_INNER_FLANGE_THICKNESS:.2f}mm "
        f"minimum_radial_stem_clearance={min(stem_clearances):.3f}mm "
        f"minimum_radial_rim_interference={min(rim_interferences):.3f}mm"
    )


def validate_front_retainer(retainer) -> None:
    """Validate the final swing-gate mesh, tracks, and assembly datum."""
    validate_object(retainer)
    tolerance = 1.0e-4
    thickness = retainer_gate_thickness_y()
    expected_y = retainer_gate_assembled_y()
    if (
        abs(retainer.location.x) > tolerance
        or abs(retainer.location.y - expected_y) > tolerance
        or abs(retainer.location.z) > tolerance
        or any(abs(angle) > tolerance for angle in retainer.rotation_euler)
    ):
        raise RuntimeError(
            "The front camera swing gate is not on its M3-shaft bearing plane"
        )

    minimum_y = min(vertex.co.y for vertex in retainer.data.vertices)
    maximum_y = max(vertex.co.y for vertex in retainer.data.vertices)
    if (
        abs(minimum_y) > tolerance
        or abs(maximum_y - thickness) > tolerance
    ):
        raise RuntimeError(
            "Swing-gate mesh thickness does not match "
            "resolved retainer gate thickness: "
            f"y=({minimum_y:.5f}, {maximum_y:.5f}) mm"
        )

    bvh = mesh_bvh(retainer)
    sample_y = thickness / 2.0
    failures = []
    layout = resolved_retainer_layout()
    for fastener_index, (x, z) in enumerate(CASE_FASTENER_POSITIONS_XZ, start=1):
        if bvh_point_is_inside(bvh, (x, sample_y, z)):
            failures.append(f"bolt_{fastener_index}_axis_is_blocked")
        if RETAINER_KEEPER_INDEX_ENABLED:
            for recess_index, (recess_x, recess_z) in enumerate(
                retainer_index_key_centers(x, z),
                start=1,
            ):
                if bvh_point_is_inside(
                    bvh,
                    (
                        recess_x,
                        RETAINER_KEEPER_INDEX_RECESS_DEPTH_Y / 2.0,
                        recess_z,
                    ),
                ):
                    failures.append(
                        f"bolt_{fastener_index}_index_recess_{recess_index}"
                    )

    bearing_sample_radius = (
        RETAINER_GATE_BOLT_TRACK_DIAMETER / 2.0
        + RETAINER_MIN_HOLE_WEB
        - 10.0 * BOOLEAN_CLEANUP_DISTANCE
    )
    pivot_x, pivot_z = layout["upper"]
    for angle_index in range(24):
        angle = 2.0 * math.pi * angle_index / 24.0
        point = (
            pivot_x + bearing_sample_radius * math.cos(angle),
            sample_y,
            pivot_z + bearing_sample_radius * math.sin(angle),
        )
        if not bvh_point_is_inside(bvh, point):
            failures.append(f"pivot_bearing_web_{angle_index + 1}")

    # Check the full M3 shaft envelope, including angles between the rounded
    # capsule chords and the free swing after each track exits.
    shaft_radius = INSERT_FASTENER_HOLE_DIAMETER / 2.0
    for name, bolt, release_angle in (
        (
            "lower_left",
            layout["lower_left"],
            RETAINER_GATE_LOWER_LEFT_RELEASE_ANGLE_DEG,
        ),
        (
            "lower_right",
            layout["lower_right"],
            RETAINER_GATE_LOWER_RIGHT_RELEASE_ANGLE_DEG,
        ),
    ):
        validation_steps = max(1, int(math.ceil(90.0 / 1.0)))
        for step in range(validation_steps + 1):
            gate_angle = 90.0 * step / validation_steps
            bolt_x, bolt_z = retainer_bolt_sweep_point(
                bolt,
                layout["upper"],
                gate_angle,
            )
            for radial_index in range(12):
                radial_angle = 2.0 * math.pi * radial_index / 12.0
                point = (
                    bolt_x + shaft_radius * math.cos(radial_angle),
                    sample_y,
                    bolt_z + shaft_radius * math.sin(radial_angle),
                )
                if bvh_point_is_inside(bvh, point):
                    phase = "track" if gate_angle <= release_angle else "swing"
                    failures.append(
                        f"{name}_{phase}_{gate_angle:.1f}deg_"
                        f"radial_{radial_index + 1}"
                    )
                    break
            if len(failures) >= 12:
                break
        if len(failures) >= 12:
            break
    if failures:
        raise RuntimeError(
            "Swing-gate direct-M3 track validation failed: "
            + ", ".join(failures[:12])
        )

    bounds_x = (
        min(vertex.co.x for vertex in retainer.data.vertices),
        max(vertex.co.x for vertex in retainer.data.vertices),
    )
    bounds_z = (
        min(vertex.co.z for vertex in retainer.data.vertices),
        max(vertex.co.z for vertex in retainer.data.vertices),
    )
    center_strap_height = (
        RETAINER_RELIEF_CENTER_Z
        - RETAINER_RELIEF_RADIUS
        - layout["bar_bottom_z"]
    )
    print(
        "FRONT_CAMERA_SWING_GATE PASS bolts=3 direct_on_m3=True "
        f"assembled_y={expected_y:.2f}mm "
        f"dimensions=({bounds_x[1] - bounds_x[0]:.2f}x"
        f"{bounds_z[1] - bounds_z[0]:.2f}x{thickness:.2f})mm "
        f"material={RETAINER_MATERIAL_MODE} "
        f"bolt_track_diameter={RETAINER_GATE_BOLT_TRACK_DIAMETER:.2f}mm "
        f"minimum_nut_bearing={RETAINER_GATE_MIN_NUT_BEARING_DIAMETER:.2f}mm "
        f"left_release={RETAINER_GATE_LOWER_LEFT_RELEASE_ANGLE_DEG:.1f}deg "
        f"right_release={RETAINER_GATE_LOWER_RIGHT_RELEASE_ANGLE_DEG:.1f}deg "
        f"minimum_center_strap={center_strap_height:.2f}mm"
    )


def validate_retainer_index_keys(insert) -> None:
    """Verify that the sleeve face carries all six keeper index keys."""
    if not RETAINER_KEEPER_INDEX_ENABLED:
        return
    bvh = mesh_bvh(insert)
    sample_y = (
        retainer_assembly_face_y()
        + RETAINER_KEEPER_INDEX_KEY_PROJECTION_Y / 2.0
    )
    failures = []
    for fastener_index, (bolt_x, bolt_z) in enumerate(
        CASE_FASTENER_POSITIONS_XZ,
        start=1,
    ):
        for key_index, (key_x, key_z) in enumerate(
            retainer_index_key_centers(bolt_x, bolt_z),
            start=1,
        ):
            if not bvh_point_is_inside(bvh, (key_x, sample_y, key_z)):
                failures.append(f"key_{fastener_index}_{key_index}")
    if failures:
        raise RuntimeError(
            "Sleeve keeper-index key validation failed: "
            + ", ".join(failures)
        )
    print(
        "FRONT_CAMERA_RETAINER_INDEX_KEYS PASS count=6 "
        f"projection={RETAINER_KEEPER_INDEX_KEY_PROJECTION_Y:.2f}mm "
        f"keeper_lift_to_turn={RETAINER_KEEPER_INDEX_RECESS_DEPTH_Y:.2f}mm"
    )


def validate_rotating_keepers(keepers) -> None:
    """Validate the three material-specific indexed 180-degree keepers."""
    if len(keepers) != len(CASE_FASTENER_POSITIONS_XZ):
        raise RuntimeError("Rotating-keeper mode requires exactly three pieces")
    layout = resolved_retainer_layout()
    expected = (
        (layout["lower_left"], Vector((0.0, 0.0, 1.0))),
        (layout["lower_right"], Vector((0.0, 0.0, 1.0))),
        (layout["upper"], Vector((0.0, 0.0, -1.0))),
    )
    thickness = retainer_keeper_thickness_y()
    tolerance = 1.0e-4
    for index, (keeper, ((expected_x, expected_z), expected_direction)) in enumerate(
        zip(keepers, expected),
        start=1,
    ):
        validate_object(keeper)
        expected_location = Vector(
            (expected_x, retainer_assembly_face_y(), expected_z)
        )
        actual_direction = (
            keeper.rotation_euler.to_matrix() @ Vector((0.0, 0.0, 1.0))
        )
        if (keeper.location - expected_location).length > tolerance:
            raise RuntimeError(
                f"Rotating keeper {index} is not aligned to its M3 shaft"
            )
        if (actual_direction - expected_direction).length > tolerance:
            raise RuntimeError(
                f"Rotating keeper {index} does not point inward when closed"
            )
        minimum_y = min(vertex.co.y for vertex in keeper.data.vertices)
        maximum_y = max(vertex.co.y for vertex in keeper.data.vertices)
        if abs(minimum_y) > tolerance or abs(maximum_y - thickness) > tolerance:
            raise RuntimeError(
                f"Rotating keeper {index} thickness mismatch: "
                f"y=({minimum_y:.5f}, {maximum_y:.5f}) mm"
            )

    bvh = mesh_bvh(keepers[0])
    probe_failures = []
    probes = [
        (
            "shaft_axis",
            (0.0, thickness / 2.0, 0.0),
            False,
        ),
        (
            "hub_wall",
            (
                (
                    RETAINER_KEEPER_BOLT_HOLE_DIAMETER
                    + RETAINER_KEEPER_HUB_DIAMETER
                )
                / 4.0,
                thickness / 2.0,
                0.0,
            ),
            True,
        ),
        (
            "closed_lobe",
            (
                0.0,
                thickness / 2.0,
                RETAINER_KEEPER_CLOSED_PROJECTION_Z - 0.5,
            ),
            True,
        ),
    ]
    if RETAINER_KEEPER_INDEX_ENABLED:
        for direction in (-1.0, 1.0):
            probes.extend(
                (
                    (
                        f"index_recess_{direction:+.0f}",
                        (
                            0.0,
                            RETAINER_KEEPER_INDEX_RECESS_DEPTH_Y / 2.0,
                            direction * RETAINER_KEEPER_INDEX_RADIAL_OFFSET,
                        ),
                        False,
                    ),
                    (
                        f"index_recess_floor_{direction:+.0f}",
                        (
                            0.0,
                            RETAINER_KEEPER_INDEX_RECESS_DEPTH_Y + 0.15,
                            direction * RETAINER_KEEPER_INDEX_RADIAL_OFFSET,
                        ),
                        True,
                    ),
                )
            )
    for name, point, expected_inside in probes:
        if bvh_point_is_inside(bvh, point) != expected_inside:
            probe_failures.append(name)
    if probe_failures:
        raise RuntimeError(
            "Rotating-keeper internal-geometry validation failed: "
            + ", ".join(probe_failures)
        )

    bottom_runner_z = max(
        spec[4] for spec in LOCATING_TAB_SPECS if spec[5] == "bottom"
    )
    top_runner_z = min(
        spec[3] for spec in LOCATING_TAB_SPECS if spec[5] == "top"
    )
    hub_radius = RETAINER_KEEPER_HUB_DIAMETER / 2.0
    lower_open_clearance = min(
        bottom_runner_z - point[1] - hub_radius
        for point in (layout["lower_left"], layout["lower_right"])
    )
    upper_open_clearance = layout["upper"][1] - hub_radius - top_runner_z
    minimum_open_clearance = min(lower_open_clearance, upper_open_clearance)
    lower_closed_overlap = min(
        point[1] + RETAINER_KEEPER_CLOSED_PROJECTION_Z - bottom_runner_z
        for point in (layout["lower_left"], layout["lower_right"])
    )
    upper_closed_overlap = top_runner_z - (
        layout["upper"][1] - RETAINER_KEEPER_CLOSED_PROJECTION_Z
    )
    minimum_closed_overlap = min(lower_closed_overlap, upper_closed_overlap)
    print(
        "FRONT_CAMERA_ROTATING_KEEPERS PASS count=3 direct_on_m3=True "
        f"material={RETAINER_MATERIAL_MODE} thickness={thickness:.2f}mm "
        f"hub_diameter={RETAINER_KEEPER_HUB_DIAMETER:.2f}mm "
        f"closed_projection={RETAINER_KEEPER_CLOSED_PROJECTION_Z:.2f}mm "
        f"minimum_closed_runner_overlap={minimum_closed_overlap:.3f}mm "
        f"minimum_open_runner_clearance={minimum_open_clearance:.3f}mm "
        f"indexed_positions={'2' if RETAINER_KEEPER_INDEX_ENABLED else '0'}"
    )


def assign_material(obj, name: str, color) -> None:
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    obj.data.materials.append(material)


def active_retainer_objects(gate, keepers):
    if not RETAINER_ENABLED:
        return ()
    if RETAINER_STYLE == "ROTATING_KEEPERS":
        return tuple(keepers)
    return (gate,)


def apply_layout(back, insert, buttons, gate, keepers, baffle_components) -> None:
    if LAYOUT_MODE == "assembled":
        return
    back_right_x = max(vertex.co.x for vertex in back.data.vertices)
    insert_left_x = min(vertex.co.x for vertex in insert.data.vertices)
    insert.location.x = back_right_x + PRINT_BED_GAP - insert_left_x
    insert.location.y = -insert_start_y()
    insert_right_x = insert.location.x + max(
        vertex.co.x for vertex in insert.data.vertices
    )
    button_radius = BUTTON_INNER_FLANGE_DIAMETER / 2.0
    next_button_x = insert_right_x + PRINT_BED_GAP + button_radius
    for button in buttons:
        button.location = (next_button_x, 0.0, 0.0)
        button.rotation_euler = (0.0, 0.0, 0.0)
        next_button_x += BUTTON_INNER_FLANGE_DIAMETER + PRINT_BED_GAP
    next_component_x = next_button_x
    if gate is not None:
        gate_min_x = min(vertex.co.x for vertex in gate.data.vertices)
        gate_max_x = max(vertex.co.x for vertex in gate.data.vertices)
        gate.location = (
            next_button_x - gate_min_x,
            0.0,
            0.0,
        )
        gate.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
        next_keeper_x = gate.location.x + gate_max_x + PRINT_BED_GAP
        keeper_width = RETAINER_KEEPER_HUB_DIAMETER
        for keeper in keepers:
            keeper.location = (
                next_keeper_x + keeper_width / 2.0,
                0.0,
                0.0,
            )
            keeper.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
            next_keeper_x += keeper_width + PRINT_BED_GAP
        next_component_x = next_keeper_x
    baffle_print_normals = (
        baffle_left_face_outward_normal(),
        baffle_right_face_outward_normal(),
        (0.0, -1.0, 0.0),
    )
    for component, outward_normal in zip(
        baffle_components,
        baffle_print_normals,
    ):
        component.location = (0.0, 0.0, 0.0)
        component.rotation_mode = "QUATERNION"
        component.rotation_quaternion = baffle_face_down_quaternion(
            outward_normal
        )
        bpy.context.view_layer.update()
        transformed = [
            component.matrix_world @ vertex.co
            for vertex in component.data.vertices
        ]
        minimum_x = min(point.x for point in transformed)
        maximum_x = max(point.x for point in transformed)
        minimum_y = min(point.y for point in transformed)
        minimum_z = min(point.z for point in transformed)
        component.location = (
            next_component_x - minimum_x,
            -minimum_y,
            -minimum_z,
        )
        next_component_x += maximum_x - minimum_x + PRINT_BED_GAP
    bpy.context.view_layer.update()


def world_bed_contact_area(obj) -> float:
    """Return polygon area actually coplanar with Z=0 after scene layout."""
    matrix = obj.matrix_world
    tolerance = 1.0e-4
    return sum(
        polygon.area
        for polygon in obj.data.polygons
        if all(
            abs((matrix @ obj.data.vertices[index].co).z) <= tolerance
            for index in polygon.vertices
        )
    )


def validate_baffle_print_bed_layout(baffle_components) -> None:
    if LAYOUT_MODE != "print_bed" or not baffle_components:
        return
    contact_areas = tuple(
        world_bed_contact_area(component) for component in baffle_components
    )
    minimums = (600.0, 600.0, 90.0)[: len(baffle_components)]
    if any(
        actual < minimum
        for actual, minimum in zip(contact_areas, minimums)
    ):
        raise RuntimeError(
            "The actual baffle print-bed layout lacks broad Z=0 contact: "
            f"areas={contact_areas}, minimums={minimums}"
        )
    print(
        "BAFFLE_PRINT_BED_LAYOUT PASS "
        "contact_areas=("
        + ",".join(f"{area:.1f}" for area in contact_areas)
        + ")mm2"
    )


def apply_post_build_visibility(
    back,
    insert,
    buttons,
    gate,
    keepers,
    baffle_components,
) -> None:
    visibility = [
        (back, SHOW_BACK_SHELL),
        (insert, SHOW_HOLLOW_INSERT),
        *[(button, SHOW_BUTTONS) for button in buttons],
        *[
            (component, SHOW_BAFFLE_CARTRIDGE)
            for component in baffle_components
        ],
    ]
    if gate is not None:
        active = set(active_retainer_objects(gate, keepers))
        visibility.append((gate, SHOW_FRONT_RETAINER and gate in active))
        visibility.extend(
            (keeper, SHOW_FRONT_RETAINER and keeper in active)
            for keeper in keepers
        )
    for obj, visible in visibility:
        obj.hide_set(not visible)
        obj.hide_render = not visible


def export_base_directory() -> Path:
    if EXPORT_DIRECTORY:
        return Path(EXPORT_DIRECTORY).expanduser().resolve()
    if bpy.data.filepath:
        return Path(bpy.data.filepath).parent.resolve()
    return Path(__file__).resolve().parent


def export_stl(path: Path, objects) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    print(f"Wrote {path}")


def export_canonical_button_stl(path: Path, button) -> None:
    """Export one quantity-two button upright without disturbing the scene."""
    saved_location = button.location.copy()
    saved_rotation = button.rotation_euler.copy()
    try:
        button.location = (0.0, 0.0, 0.0)
        button.rotation_euler = (0.0, 0.0, 0.0)
        export_stl(path, [button])
    finally:
        button.location = saved_location
        button.rotation_euler = saved_rotation


def export_canonical_component_stl(path: Path, component) -> None:
    """Export an assembled-coordinate component despite print-bed layout."""
    saved_location = component.location.copy()
    saved_rotation = component.rotation_euler.copy()
    try:
        component.location = (0.0, 0.0, 0.0)
        component.rotation_euler = (0.0, 0.0, 0.0)
        export_stl(path, [component])
    finally:
        component.location = saved_location
        component.rotation_euler = saved_rotation


def baffle_face_down_quaternion(outward_normal):
    return Vector(outward_normal).normalized().rotation_difference(
        Vector((0.0, 0.0, -1.0))
    )


def export_component_face_down(path: Path, component, outward_normal) -> None:
    """Export a component with the selected broad exterior face on the bed."""
    saved_matrix = component.matrix_world.copy()
    saved_rotation_mode = component.rotation_mode
    try:
        component.location = (0.0, 0.0, 0.0)
        component.rotation_mode = "QUATERNION"
        component.rotation_quaternion = baffle_face_down_quaternion(
            outward_normal
        )
        export_stl(path, [component])
    finally:
        component.rotation_mode = saved_rotation_mode
        component.matrix_world = saved_matrix


def baffle_left_face_outward_normal():
    rear_left = FAN_CENTER_X - BAFFLE_REAR_WIDTH / 2.0
    front_left = -BAFFLE_FRONT_WIDTH / 2.0
    slope = (front_left - rear_left) / (BAFFLE_FRONT_Y - BAFFLE_REAR_Y)
    return (-1.0, slope, 0.0)


def baffle_right_face_outward_normal():
    rear_right = FAN_CENTER_X + BAFFLE_REAR_WIDTH / 2.0
    front_right = BAFFLE_FRONT_WIDTH / 2.0
    slope = (front_right - rear_right) / (BAFFLE_FRONT_Y - BAFFLE_REAR_Y)
    return (1.0, -slope, 0.0)


def export_canonical_baffle_tray_stl(path: Path, tray) -> None:
    export_component_face_down(path, tray, baffle_left_face_outward_normal())


def export_canonical_baffle_lid_stl(path: Path, lid) -> None:
    export_component_face_down(path, lid, baffle_right_face_outward_normal())


def export_canonical_baffle_gasket_stl(path: Path, gasket) -> None:
    export_component_face_down(path, gasket, (0.0, -1.0, 0.0))


def export_canonical_retainer_stl(path: Path, retainer) -> None:
    """Export the swing gate flat with its rear surface on the bed."""
    saved_location = retainer.location.copy()
    saved_rotation = retainer.rotation_euler.copy()
    try:
        retainer.location = (0.0, 0.0, 0.0)
        retainer.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
        export_stl(path, [retainer])
    finally:
        retainer.location = saved_location
        retainer.rotation_euler = saved_rotation


def export_canonical_retainer_keeper_stl(path: Path, keeper) -> None:
    """Export one quantity-three keeper flat with its rear face on the bed."""
    saved_location = keeper.location.copy()
    saved_rotation = keeper.rotation_euler.copy()
    try:
        keeper.location = (0.0, 0.0, 0.0)
        keeper.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
        export_stl(path, [keeper])
    finally:
        keeper.location = saved_location
        keeper.rotation_euler = saved_rotation


def build_gopro_fan_case():
    # A direct assignment remains convenient for callers that execute this
    # module into a namespace and then build more than one material variant.
    if BACK_MATERIAL_MODE != _APPLIED_BACK_MATERIAL_MODE:
        apply_back_material_profile()
    if (
        BAFFLE_CARTRIDGE_MATERIAL_MODE
        != _APPLIED_BAFFLE_CARTRIDGE_MATERIAL_MODE
    ):
        apply_baffle_cartridge_material_profile()
    validate_config()
    print(
        "MATERIAL_MODES "
        f"back={BACK_MATERIAL_MODE} sleeve={SLEEVE_MATERIAL_MODE} "
        f"retainer={RETAINER_MATERIAL_MODE} "
        f"baffle={BAFFLE_CARTRIDGE_MATERIAL_MODE} buttons=TPU "
        f"seal={'integral_TPU' if baffle_gasket_is_integral() else 'separate_TPU'}"
    )
    print(
        f"FRONT_CAMERA_RETAINER enabled={RETAINER_ENABLED} "
        f"assembled_style={RETAINER_STYLE}"
    )
    print(
        "BACK_FASTENER_HEX_RETENTION "
        f"count={len(CASE_FASTENER_POSITIONS_XZ) if CASE_FASTENERS_ENABLED else 0} "
        f"tab_projection={BACK_FASTENER_RETENTION_TAB_PROTRUSION:.2f}mm "
        f"axial_preload={back_fastener_retention_axial_preload():.2f}mm"
    )
    if SLEEVE_CAPTURE_SLOT_ENABLED:
        groove_outer_width, groove_outer_height, groove_outer_radius = (
            sleeve_capture_groove_outer_dimensions()
        )
        support_width, support_height, support_radius = (
            sleeve_capture_outer_support_dimensions()
        )
        back_width, back_height, back_radius = effective_back_outer_dimensions()
        envelope_margin_x = (back_width - groove_outer_width) / 2.0
        envelope_margin_z = (back_height - groove_outer_height) / 2.0
        groove_corner_center = (
            groove_outer_width / 2.0 - groove_outer_radius,
            groove_outer_height / 2.0 - groove_outer_radius,
        )
        support_corner_center = (
            support_width / 2.0 - support_radius,
            support_height / 2.0 - support_radius,
        )
        corner_support = (
            support_radius
            - groove_outer_radius
            - math.hypot(
                support_corner_center[0] - groove_corner_center[0],
                support_corner_center[1] - groove_corner_center[1],
            )
        )
        print(
            "SLEEVE_CAPTURE_SLOT enabled=True "
            f"boss_datum_y={insert_start_y():.2f}mm "
            f"ordinary_overlap={INSERTION_DEPTH:.2f}mm "
            f"engagement={SLEEVE_CAPTURE_ENGAGEMENT_DEPTH:.2f}mm "
            f"fit_clearance_per_face={SLEEVE_CAPTURE_FIT_CLEARANCE:.2f}mm "
            f"bottom_clearance={SLEEVE_CAPTURE_BOTTOM_CLEARANCE:.2f}mm "
            f"inner_lip={SLEEVE_CAPTURE_INNER_LIP_THICKNESS:.2f}mm "
            f"floor={SLEEVE_CAPTURE_FLOOR_THICKNESS:.2f}mm "
            f"deep_groove_support_x={SLEEVE_CAPTURE_MIN_OUTER_WALL_X:.2f}mm "
            f"deep_groove_support_z={SLEEVE_CAPTURE_MIN_OUTER_WALL_Z:.2f}mm "
            f"deep_groove_corner_support={corner_support:.2f}mm "
            f"overall_envelope_margin_x={envelope_margin_x:.2f}mm "
            f"overall_envelope_margin_z={envelope_margin_z:.2f}mm "
            f"effective_back_outer={back_width:.2f}x{back_height:.2f}mm "
            f"effective_back_corner_radius={back_radius:.2f}mm "
            f"boss_face_gap={BACK_FASTENER_TO_INSERT_SOCKET_GAP:.2f}mm"
        )
    else:
        print("SLEEVE_CAPTURE_SLOT enabled=False")
    if CLEAR_SCENE:
        clear_scene()
    set_units()

    back = create_back_shell()
    insert = create_insert_frame()
    buttons = create_captive_buttons()
    baffle_components = create_baffle_cartridge()
    gate = create_front_retainer() if RETAINER_ENABLED else None
    keepers = create_rotating_keepers() if RETAINER_ENABLED else ()
    validate_object(back)
    validate_object(insert)
    validate_captive_buttons(buttons)
    validate_baffle_cartridge(back, baffle_components)
    if gate is not None:
        validate_front_retainer(gate)
        validate_retainer_index_keys(insert)
        validate_rotating_keepers(keepers)
    validate_sleeve_capture_mesh(back, insert)
    assign_material(back, f"Rear_Shell_{BACK_MATERIAL_MODE}", BACK_COLOR)
    assign_material(insert, f"Insert_Frame_{SLEEVE_MATERIAL_MODE}", INSERT_COLOR)
    assign_material(buttons[0], "Captive_Button_TPU", BUTTON_COLOR)
    if baffle_components:
        baffle_tray, baffle_lid = baffle_components[:2]
        baffle_gasket = (
            baffle_components[2] if len(baffle_components) == 3 else None
        )
        assign_material(
            baffle_tray,
            f"Baffle_Tray_{BAFFLE_CARTRIDGE_MATERIAL_MODE}",
            BAFFLE_TRAY_COLOR,
        )
        assign_material(
            baffle_lid,
            f"Baffle_Lid_{BAFFLE_CARTRIDGE_MATERIAL_MODE}",
            BAFFLE_LID_COLOR,
        )
        if baffle_gasket is not None:
            assign_material(
                baffle_gasket,
                "Baffle_Inlet_Gasket_TPU",
                BAFFLE_GASKET_COLOR,
            )
    if gate is not None:
        assign_material(
            gate,
            f"Front_Retainer_{RETAINER_MATERIAL_MODE}",
            RETAINER_COLOR,
        )
        assign_material(
            keepers[0],
            f"Rotating_Keeper_{RETAINER_MATERIAL_MODE}",
            RETAINER_KEEPER_COLOR,
        )
    apply_layout(back, insert, buttons, gate, keepers, baffle_components)
    validate_baffle_print_bed_layout(baffle_components)

    if EXPORT_STL:
        directory = export_base_directory()
        if EXPORT_COMBINED_STL:
            combined_objects = [back, insert, *buttons]
            combined_objects.extend(baffle_components)
            if gate is not None:
                combined_objects.extend(active_retainer_objects(gate, keepers))
            export_stl(
                directory / COMBINED_STL_NAME,
                combined_objects,
            )
        if EXPORT_SEPARATE_STLS:
            export_canonical_component_stl(directory / BACK_STL_NAME, back)
            export_canonical_component_stl(directory / INSERT_STL_NAME, insert)
            export_canonical_button_stl(
                directory / BUTTON_STL_NAME,
                buttons[0],
            )
            if baffle_components:
                baffle_tray, baffle_lid = baffle_components[:2]
                baffle_gasket = (
                    baffle_components[2]
                    if len(baffle_components) == 3
                    else None
                )
                export_canonical_baffle_tray_stl(
                    directory / BAFFLE_TRAY_STL_NAME,
                    baffle_tray,
                )
                export_canonical_baffle_lid_stl(
                    directory / BAFFLE_LID_STL_NAME,
                    baffle_lid,
                )
                if baffle_gasket is not None:
                    export_canonical_baffle_gasket_stl(
                        directory / BAFFLE_GASKET_STL_NAME,
                        baffle_gasket,
                    )
            if gate is not None:
                export_canonical_retainer_stl(
                    directory / RETAINER_STL_NAME,
                    gate,
                )
                export_canonical_retainer_keeper_stl(
                    directory / RETAINER_KEEPER_STL_NAME,
                    keepers[0],
                )

    bpy.ops.object.select_all(action="DESELECT")
    apply_post_build_visibility(
        back,
        insert,
        buttons,
        gate,
        keepers,
        baffle_components,
    )
    visibility = [
        (back, SHOW_BACK_SHELL),
        (insert, SHOW_HOLLOW_INSERT),
        *[(button, SHOW_BUTTONS) for button in buttons],
        *[
            (component, SHOW_BAFFLE_CARTRIDGE)
            for component in baffle_components
        ],
    ]
    if gate is not None:
        active = set(active_retainer_objects(gate, keepers))
        visibility.append((gate, SHOW_FRONT_RETAINER and gate in active))
        visibility.extend(
            (keeper, SHOW_FRONT_RETAINER and keeper in active)
            for keeper in keepers
        )
    visible_objects = [obj for obj, visible in visibility if visible]
    for obj in visible_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = (
        visible_objects[0] if visible_objects else None
    )
    return back, insert


if __name__ == "__main__":
    build_gopro_fan_case()
