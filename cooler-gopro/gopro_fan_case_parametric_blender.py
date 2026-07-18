"""Clean parametric two-piece GoPro fan case for Blender.

Run inside Blender:

    blender --background --python gopro_fan_case_parametric_blender.py

All dimensions are millimeters. The defaults follow ``gopro-fan-case.stl``
without reproducing its internal scraps or jagged hole edges. The generated
objects are two independent manifold shells: a shallow fan/socket shell and
an open frame that snaps into it.

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


# ---------------------------------------------------------------------------
# CONFIG

CLEAR_SCENE = True
LAYOUT_MODE = "assembled"  # "assembled" or "print_bed"
PRINT_BED_GAP = 12.0

# Post-build viewport/render visibility. Geometry is still built, validated,
# and exported when hidden, making it easy to inspect either part by itself.
SHOW_BACK_SHELL = True
SHOW_HOLLOW_INSERT = True

EXPORT_STL = False
EXPORT_DIRECTORY = ""
EXPORT_COMBINED_STL = True
EXPORT_SEPARATE_STLS = True
COMBINED_STL_NAME = "gopro_fan_case_parametric.stl"
BACK_STL_NAME = "gopro_fan_case_back.stl"
INSERT_STL_NAME = "gopro_fan_case_insert.stl"

# Mesh and boolean quality.
CYLINDER_SEGMENTS = 96
CORNER_SEGMENTS = 12
INSERT_DEPTH_SECTIONS = 8
BOOLEAN_SOLVER = "EXACT"
BOOLEAN_OVERLAP = 0.08
BOOLEAN_CLEANUP_DISTANCE = 0.0001

# Rear fan/socket shell. Y=0 is its smooth front surface.
BACK_OUTER_WIDTH = 96.65
BACK_OUTER_HEIGHT = 65.74
BACK_DEPTH = 21.2
BACK_CORNER_RADIUS = 10.0
BACK_FACE_THICKNESS = 3.0

# Optional smooth exterior dome. The central fan pad remains an exact flat
# rectangle at the dome's outermost Y position; the surrounding surface
# blends back into the rear shell perimeter.
BACK_DOME_ENABLED = False
BACK_DOME_DEPTH = 10.0
BACK_DOME_FAN_PAD_WIDTH = 45.0
BACK_DOME_FAN_PAD_HEIGHT = 45.0
BACK_DOME_SECTIONS = 12
BACK_DOME_LOOP_POINTS = 128

# Mating socket. The insert dimensions below plus these values determine fit.
FIT_CLEARANCE_X = 0.30
FIT_CLEARANCE_Z = 0.30
INSERTION_DEPTH = 3.4

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
# Axial gap between the rear tube end and the insert-boss socket boundary.
# Its distance behind the open rim is INSERTION_DEPTH plus this value.
BACK_FASTENER_TO_INSERT_SOCKET_GAP = 0.0
INSERT_FASTENER_HOLE_DIAMETER = 3.3
INSERT_FASTENER_BOSS_DIAMETER = 7.0
FASTENER_BOSS_SOCKET_CLEARANCE = 0.25

# Original-style M3 hex-head recesses in the rear perimeter fasteners.
# The seat-to-insert distance preserves the original screw reach.
BACK_FASTENER_HEX_RETENTION_ENABLED = True
BACK_FASTENER_HEX_WIDTH_X = 6.61
BACK_FASTENER_HEX_HEIGHT_Z = 5.70
BACK_FASTENER_HEX_SEAT_TO_INSERT = 6.2076
BACK_FASTENER_HEX_TRANSITION_DEPTH = 0.358
BACK_FASTENER_RETENTION_TABS_ENABLED = True
BACK_FASTENER_RETENTION_TAB_WIDTH_X = 1.0
BACK_FASTENER_RETENTION_TAB_DEPTH_Y = 2.0
BACK_FASTENER_RETENTION_TAB_PROTRUSION = 0.30
BACK_FASTENER_RETENTION_TAB_OFFSET_FROM_SEAT = 6.642
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
INSERT_DEPTH = 25.3
INSERT_OUTER_CORNER_RADIUS = 8.0
INSERT_WALL_X = 2.0
INSERT_WALL_Z = 1.8

# Large opening through the insert's bottom wall.
BOTTOM_ACCESS_ENABLED = True
BOTTOM_ACCESS_WIDTH = 50.0
BOTTOM_ACCESS_DEPTH = 20.0
BOTTOM_ACCESS_Y_OFFSET = 3.5

# The original has different openings on its two side walls.
LEFT_ROUND_PORT_ENABLED = True
LEFT_ROUND_PORT_DIAMETER = 6.1875
LEFT_ROUND_PORT_Y_OFFSET = 14.3367
LEFT_ROUND_PORT_Z = -1.4828

# USB opening through only the positive-X side wall.
RIGHT_USB_PORT_ENABLED = True
RIGHT_USB_PORT_WIDTH_Y = 13.1998
RIGHT_USB_PORT_HEIGHT_Z = 7.2
RIGHT_USB_PORT_CORNER_RADIUS = 3.6
RIGHT_USB_PORT_Y_OFFSET = 13.8894
RIGHT_USB_PORT_Z = -17.9001

# Optional circular port through only the top wall.
TOP_PORT_ENABLED = True
TOP_PORT_DIAMETER = 6.1875
TOP_PORT_X = 18.0
TOP_PORT_Y_OFFSET = 14.3367

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


# ---------------------------------------------------------------------------
# Configuration and scene helpers


def insert_start_y() -> float:
    return BACK_DEPTH - INSERTION_DEPTH


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


def back_fastener_end_y() -> float:
    return insert_start_y() - BACK_FASTENER_TO_INSERT_SOCKET_GAP


def camera_stop_end_y() -> float:
    return insert_start_y() - CAMERA_STOP_TO_INSERT_SOCKET_GAP


def smoothstep(value: float) -> float:
    value = min(max(value, 0.0), 1.0)
    return value * value * (3.0 - 2.0 * value)


def dome_surface_y_approx(x: float, z: float) -> float:
    if not BACK_DOME_ENABLED:
        return 0.0
    x_from_pad = max(abs(x - FAN_CENTER_X) - BACK_DOME_FAN_PAD_WIDTH / 2.0, 0.0)
    z_from_pad = max(abs(z - FAN_CENTER_Z) - BACK_DOME_FAN_PAD_HEIGHT / 2.0, 0.0)
    x_run = max(BACK_OUTER_WIDTH / 2.0 - BACK_DOME_FAN_PAD_WIDTH / 2.0, 0.001)
    z_run = max(BACK_OUTER_HEIGHT / 2.0 - BACK_DOME_FAN_PAD_HEIGHT / 2.0, 0.001)
    radial_t = max(x_from_pad / x_run, z_from_pad / z_run)
    return -BACK_DOME_DEPTH * (1.0 - smoothstep(radial_t))


def socket_width() -> float:
    return INSERT_FRONT_WIDTH + 2.0 * FIT_CLEARANCE_X


def socket_height() -> float:
    return INSERT_FRONT_HEIGHT + 2.0 * FIT_CLEARANCE_Z


def insert_inner_width() -> float:
    return INSERT_FRONT_WIDTH - 2.0 * INSERT_WALL_X


def insert_inner_height() -> float:
    return INSERT_FRONT_HEIGHT - 2.0 * INSERT_WALL_Z


def validate_config() -> None:
    positive = {
        "BACK_OUTER_WIDTH": BACK_OUTER_WIDTH,
        "BACK_OUTER_HEIGHT": BACK_OUTER_HEIGHT,
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
        "FAN_OPENING_DIAMETER": FAN_OPENING_DIAMETER,
        "FAN_HOLE_DIAMETER": FAN_HOLE_DIAMETER,
        "VENT_WIDTH": VENT_WIDTH,
        "VENT_HEIGHT": VENT_HEIGHT,
        "SNAP_BUMP_LENGTH_Y": SNAP_BUMP_LENGTH_Y,
        "SNAP_BUMP_LENGTH_Z": SNAP_BUMP_LENGTH_Z,
        "LEFT_ROUND_PORT_DIAMETER": LEFT_ROUND_PORT_DIAMETER,
        "RIGHT_USB_PORT_WIDTH_Y": RIGHT_USB_PORT_WIDTH_Y,
        "RIGHT_USB_PORT_HEIGHT_Z": RIGHT_USB_PORT_HEIGHT_Z,
        "BACK_FASTENER_HEX_WIDTH_X": BACK_FASTENER_HEX_WIDTH_X,
        "BACK_FASTENER_HEX_HEIGHT_Z": BACK_FASTENER_HEX_HEIGHT_Z,
        "BACK_FASTENER_HEX_SEAT_TO_INSERT": BACK_FASTENER_HEX_SEAT_TO_INSERT,
        "BACK_FASTENER_HEX_TRANSITION_DEPTH": BACK_FASTENER_HEX_TRANSITION_DEPTH,
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
    for name, value in positive.items():
        if value <= 0.0:
            raise ValueError(f"{name} must be positive")

    if LAYOUT_MODE not in {"assembled", "print_bed"}:
        raise ValueError('LAYOUT_MODE must be "assembled" or "print_bed"')
    if not 0.0 < BACK_FACE_THICKNESS < BACK_DEPTH:
        raise ValueError("BACK_FACE_THICKNESS must be less than BACK_DEPTH")
    if not 0.0 < INSERTION_DEPTH < min(BACK_DEPTH, INSERT_DEPTH):
        raise ValueError("INSERTION_DEPTH must fit inside both parts")
    if INSERT_DEPTH_SECTIONS < 1:
        raise ValueError("INSERT_DEPTH_SECTIONS must be at least 1")
    if BACK_DOME_SECTIONS < 2:
        raise ValueError("BACK_DOME_SECTIONS must be at least 2")
    if BACK_DOME_LOOP_POINTS < 16 or BACK_DOME_LOOP_POINTS % 4:
        raise ValueError("BACK_DOME_LOOP_POINTS must be a multiple of 4 and at least 16")
    if (
        BACK_DOME_FAN_PAD_WIDTH >= BACK_OUTER_WIDTH
        or BACK_DOME_FAN_PAD_HEIGHT >= BACK_OUTER_HEIGHT
    ):
        raise ValueError("The dome fan pad must fit inside the rear shell perimeter")
    if insert_inner_width() <= 0.0 or insert_inner_height() <= 0.0:
        raise ValueError("Insert wall thickness leaves no interior opening")
    if socket_width() >= BACK_OUTER_WIDTH or socket_height() >= BACK_OUTER_HEIGHT:
        raise ValueError("The mating socket does not fit inside the rear shell")
    if FAN_OPENING_DIAMETER >= min(BACK_OUTER_WIDTH, BACK_OUTER_HEIGHT):
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

    low_center = len(vertices)
    vertices.append((center_x, y_positions[0], center_z))
    high_center = len(vertices)
    vertices.append((center_x, y_positions[-1], center_z))
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
    outer_loop = resample_closed_loop(
        rounded_rectangle_path_from_top(
            BACK_OUTER_WIDTH,
            BACK_OUTER_HEIGHT,
            BACK_CORNER_RADIUS,
            CORNER_SEGMENTS,
        ),
        BACK_DOME_LOOP_POINTS,
    )

    vertices = []
    for section in range(BACK_DOME_SECTIONS + 1):
        radial_t = section / BACK_DOME_SECTIONS
        height_t = smoothstep(radial_t)
        y = (
            -BACK_DOME_DEPTH * (1.0 - height_t)
            + BOOLEAN_OVERLAP * height_t
        )
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
    vertices.append((FAN_CENTER_X, -BACK_DOME_DEPTH, FAN_CENTER_Z))
    outer_center = len(vertices)
    vertices.append((0.0, BOOLEAN_OVERLAP, 0.0))
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
            -BACK_DOME_DEPTH * (1.0 - height_t)
            + BACK_FACE_THICKNESS
            + inner_surface_offset_y
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
            fan_pad_inner_y() + inner_surface_offset_y,
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
    outer_loops = []
    inner_loops = []
    for section in range(INSERT_DEPTH_SECTIONS + 1):
        t = section / INSERT_DEPTH_SECTIONS
        width = INSERT_FRONT_WIDTH + (INSERT_REAR_WIDTH - INSERT_FRONT_WIDTH) * t
        height = INSERT_FRONT_HEIGHT + (INSERT_REAR_HEIGHT - INSERT_FRONT_HEIGHT) * t
        outer_loops.append(
            rounded_rectangle_loop(width, height, INSERT_OUTER_CORNER_RADIUS)
        )
        inner_radius = max(
            INSERT_OUTER_CORNER_RADIUS - max(INSERT_WALL_X, INSERT_WALL_Z),
            0.5,
        )
        inner_loops.append(
            rounded_rectangle_loop(
                insert_inner_width(),
                insert_inner_height(),
                inner_radius,
            )
        )

    loop_count = len(outer_loops[0])
    vertices = []
    for section in range(INSERT_DEPTH_SECTIONS + 1):
        y = insert_start_y() + INSERT_DEPTH * section / INSERT_DEPTH_SECTIONS
        vertices.extend((x, y, z) for x, z in outer_loops[section])
        vertices.extend((x, y, z) for x, z in inner_loops[section])

    stride = loop_count * 2

    def outer(section, index):
        return section * stride + index % loop_count

    def inner(section, index):
        return section * stride + loop_count + index % loop_count

    faces = []
    for section in range(INSERT_DEPTH_SECTIONS):
        for i in range(loop_count):
            j = i + 1
            faces.append(
                [outer(section, i), outer(section + 1, i), outer(section + 1, j), outer(section, j)]
            )
            faces.append(
                [inner(section, j), inner(section + 1, j), inner(section + 1, i), inner(section, i)]
            )

    last = INSERT_DEPTH_SECTIONS
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


def add_beveled_box(name: str, dimensions, location, bevel: float):
    obj = add_box(name, dimensions, location)
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
    cleanup_boolean_mesh(base)
    recalc_normals(base)
    return base


def boolean_union(base, part, label="Union"):
    return apply_boolean(base, part, "UNION", label + "_" + part.name)


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

    center_y = (
        back_fastener_hex_seat_y()
        - BACK_FASTENER_RETENTION_TAB_OFFSET_FROM_SEAT
    )
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
            )
    return back


def create_back_shell():
    back = rounded_rectangle_prism_y(
        "Rear_Fan_Shell",
        BACK_OUTER_WIDTH,
        BACK_OUTER_HEIGHT,
        BACK_CORNER_RADIUS,
        0.0,
        BACK_DEPTH,
    )
    dome = create_back_dome()
    if dome is not None:
        boolean_union(back, dome, "Rear_Dome_Union")
    socket_radius = max(INSERT_OUTER_CORNER_RADIUS + max(FIT_CLEARANCE_X, FIT_CLEARANCE_Z), 0.5)
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
                    dome_surface_y_approx(x, z) - BOOLEAN_OVERLAP,
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
        boolean_union(back, camera_stops, "Camera_Stops_Union")

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
        boolean_union(back, fan_boss_group, "Fan_Bosses_Union")

    back.name = "GoPro_Fan_Case_Back"
    back.data.name = "GoPro_Fan_Case_Back_Mesh"
    return back


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

    create_locating_tabs(insert)
    create_snap_bumps(insert)

    cuts = []
    if CASE_FASTENERS_ENABLED:
        for index, (x, z) in enumerate(CASE_FASTENER_POSITIONS_XZ, start=1):
            cuts.append(
                add_cylinder_y(
                    f"Insert_Fastener_Hole_{index}",
                    INSERT_FASTENER_HOLE_DIAMETER / 2.0,
                    insert_start_y() - BOOLEAN_OVERLAP,
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


def assign_material(obj, name: str, color) -> None:
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    obj.data.materials.append(material)


def apply_layout(back, insert) -> None:
    if LAYOUT_MODE == "assembled":
        return
    insert.location.x = (
        BACK_OUTER_WIDTH / 2.0 + INSERT_REAR_WIDTH / 2.0 + PRINT_BED_GAP
    )
    insert.location.y = -insert_start_y()


def apply_post_build_visibility(back, insert) -> None:
    for obj, visible in (
        (back, SHOW_BACK_SHELL),
        (insert, SHOW_HOLLOW_INSERT),
    ):
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


def build_gopro_fan_case():
    validate_config()
    if CLEAR_SCENE:
        clear_scene()
    set_units()

    back = create_back_shell()
    insert = create_insert_frame()
    validate_object(back)
    validate_object(insert)
    assign_material(back, "Rear_Shell_Blue", BACK_COLOR)
    assign_material(insert, "Insert_Frame_Orange", INSERT_COLOR)
    apply_layout(back, insert)

    if EXPORT_STL:
        directory = export_base_directory()
        if EXPORT_COMBINED_STL:
            export_stl(directory / COMBINED_STL_NAME, [back, insert])
        if EXPORT_SEPARATE_STLS:
            export_stl(directory / BACK_STL_NAME, [back])
            export_stl(directory / INSERT_STL_NAME, [insert])

    bpy.ops.object.select_all(action="DESELECT")
    apply_post_build_visibility(back, insert)
    visible_objects = [
        obj
        for obj, visible in (
            (back, SHOW_BACK_SHELL),
            (insert, SHOW_HOLLOW_INSERT),
        )
        if visible
    ]
    for obj in visible_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = (
        visible_objects[0] if visible_objects else None
    )
    return back, insert


if __name__ == "__main__":
    build_gopro_fan_case()
