"""Parametric one-to-three-fan holder with a detachable GoPro adapter.

Run inside Blender:

    blender --background --python dual_fan_parametric_blender.py

All dimensions are millimeters. Edit the values in CONFIG, then run the
script. The default two-fan dimensions follow ``gopro-dual-fan.stl`` while
keeping every supported fan array centered and easy to modify.

``FAN_GRILL_ON_BACK=True`` is the support-conscious default.  With zero fan
rotation angles, place the shared rear grille/support/stalk plane face-down on
the print bed.  Set it to ``False`` for the original front-grille layout.

``STALK_DROPPED_ROUTE_ENABLED`` adds a down/back/up return that lowers large
fans relative to the GoPro receiver. For a single fan,
``SINGLE_FAN_AIRFLOW_SPLITTER_ENABLED`` also creates a separate standard-hole
splitter-vane module that redirects center airflow toward left/right cameras.
``STALK_LATERAL_DEFLECTION_X`` shifts the fan array sideways from the receiver
and angles the stalk between them; zero retains the centered arrangement.

Axes:
    X - across the fan array
    Y - vertical in the fan plane; the GoPro fingers project toward negative Y
    Z - fan depth; the camera mount projects toward negative Z
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector


def find_fan_preset_directory() -> Path:
    """Locate fan_size_presets.py when run from a Blender Text datablock."""
    candidates = []

    def add_file_parent(raw_path) -> None:
        if not raw_path:
            return
        try:
            expanded = bpy.path.abspath(str(raw_path))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            expanded = str(raw_path)
        path = Path(expanded).expanduser()
        try:
            path = path.resolve()
        except OSError:
            path = path.absolute()
        candidates.append(path.parent)

    space_data = getattr(bpy.context, "space_data", None)
    active_text = getattr(space_data, "text", None)
    add_file_parent(getattr(active_text, "filepath", ""))
    script_name = Path(__file__).name
    loaded_texts = tuple(getattr(bpy.data, "texts", ()))
    for text in loaded_texts:
        if Path(text.name).name == script_name:
            add_file_parent(getattr(text, "filepath", ""))
    script_directory = Path(__file__).expanduser().resolve().parent
    if script_directory.suffix.lower() == ".blend":
        candidates.append(script_directory.parent)
    else:
        candidates.append(script_directory)
    if bpy.data.filepath:
        candidates.append(Path(bpy.data.filepath).expanduser().resolve().parent)
    for text in loaded_texts:
        add_file_parent(getattr(text, "filepath", ""))
    candidates.append(Path.cwd().resolve())
    candidates.extend(
        Path(entry).expanduser().resolve()
        for entry in sys.path
        if entry and Path(entry).expanduser().is_dir()
    )

    searched = []
    for directory in candidates:
        if directory in searched:
            continue
        searched.append(directory)
        if (directory / "fan_size_presets.py").is_file():
            directory_text = str(directory)
            while directory_text in sys.path:
                sys.path.remove(directory_text)
            sys.path.insert(0, directory_text)
            loaded_module = sys.modules.get("fan_size_presets")
            if loaded_module is not None:
                loaded_path = getattr(loaded_module, "__file__", "")
                try:
                    loaded_path = Path(loaded_path).expanduser().resolve()
                except (OSError, TypeError, ValueError):
                    loaded_path = None
                if loaded_path != (directory / "fan_size_presets.py").resolve():
                    del sys.modules["fan_size_presets"]
            return directory
    raise ModuleNotFoundError(
        "Could not locate fan_size_presets.py. Searched: "
        + ", ".join(str(path) for path in searched)
    )


FAN_PRESET_DIRECTORY = find_fan_preset_directory()

from fan_size_presets import STANDARD_FAN_PRESETS  # noqa: E402


# ---------------------------------------------------------------------------
# CONFIG

CLEAR_SCENE = True
EXPORT_STL = False
# Leave None to derive a count/size-specific holder filename.  Build tooling or
# Blender console users may set an explicit path to override it.
EXPORT_STL_PATH = None
EXPORT_ADAPTER_STL_PATH = "gopro_dual_fan_adapter.stl"
# Leave None for a size-specific single-fan splitter filename.
EXPORT_AIRFLOW_SPLITTER_STL_PATH = None

# Structural profile for the fan holder.  The detachable GoPro adapter remains
# a separate rigid part in every mode; only the holder dimensions and fastener
# treatment change.  TPU is deliberately stiffened by geometry instead of
# relying on very high slicer infill.
MATERIAL_MODE = "RIGID"  # "RIGID" or "TPU"
# MATERIAL_MODE = "TPU"

# Slicer guidance is informational because STL files cannot encode these
# settings.  Five to six walls should provide at least a 2.0-2.4 mm shell.
TPU_RECOMMENDED_INFILL_PERCENT = (40, 45)
TPU_RECOMMENDED_INFILL_PATTERN = "gyroid"
TPU_RECOMMENDED_WALLS = (5, 6)
TPU_MOUNT_SCREW_EXTRA_LENGTH_MM = 4.0

# Mesh and boolean quality.
CYLINDER_SEGMENTS = 96
CORNER_SEGMENTS = 10
BOOLEAN_SOLVER = "EXACT"
# Blender 5.2's EXACT solver can leave open edge fans where the independently
# manifold fan/support parts are assembled.  Use MANIFOLD only for those final
# unions; older Blender versions fall back to EXACT after enum inspection.
ASSEMBLY_BOOLEAN_SOLVER = "MANIFOLD"
# The receiver block's through-hole/countersink cuts feed directly into its
# final assembly seam.  Keeping these n-gons on the same watertight solver
# avoids spatially coincident face pairs after the block/stalk union.
MOUNT_BLOCK_BOOLEAN_SOLVER = "MANIFOLD"
BOOLEAN_OVERLAP = 0.08
BOOLEAN_MINIMUM_VOLUME_CHANGE = 1.0e-6
UNION_ALL_PARTS = True
DEBUG_BOOLEAN_STEPS = False
CLEAN_COINCIDENT_FACE_TOLERANCE = 1.0e-5
# Weld only numerically identical Boolean vertices before triangulation.  This
# avoids open STL edges when Blender tessellates an otherwise manifold n-gon,
# while remaining far below the script's modeled clearances and overlaps.
TRIANGULATION_WELD_DISTANCE = 1.0e-9

# Fan array.  FAN_COUNT consumes the first entries from FAN_SIZES_MM and
# FAN_ROTATIONS_DEG, so changing only FAN_COUNT selects the normal one-, two-,
# or three-fan arrangement.  Edit an entry in FAN_SIZES_MM to mix sizes.
FAN_COUNT = 2
FAN_SIZES_MM = (80, 80, 60)
FAN_ROTATIONS_DEG = (
    (0.0, 0.0, 0.0),
    (0.0, 0.0, 0.0),
    (0.0, 0.0, 0.0),
)

# Put each airflow grille on the fan cage's rear face.  With zero fan rotation
# angles, the rear grilles, support, and support-side stalk end share one plane
# so the holder can be printed rear-face-down without generated supports.
# Set False to retain the original front-grille geometry byte-for-byte for the
# same remaining configuration values.
FAN_GRILL_ON_BACK = True

# Shared Noctua reference dimensions: nominal frame size, depth, square
# mounting-hole spacing, and fan-frame hole diameter.  The holder sleeves only
# FAN_FRAME_DEPTH millimeters at the selected grille side; the remainder of a
# 20/25 mm fan may protrude from the opposite open face.
FAN_PRESETS = {size: dict(preset) for size, preset in STANDARD_FAN_PRESETS.items()}
FAN_REFERENCE_SIZE_MM = 60.0
# The original centers at +/-52.5 mm leave 45 mm between nominal 60 mm bodies.
FAN_BODY_GAP_MM = 47.5 + 5.0
#FAN_FRAME_DEPTH = 14.7
FAN_FRAME_DEPTH = 20.0
FAN_FRAME_CORNER_RADIUS = 2.5
# The original rigid cavity is 60.7 mm around a nominal 60 mm fan.
# FAN_BODY_CLEARANCE_PER_SIDE = 0.35
FAN_BODY_CLEARANCE_PER_SIDE = 1.0
# FAN_FRAME_WALL and GRILL_THICKNESS are selected in MATERIAL_PROFILES below.

# "support_contact" rotates around the lower-inner connection to the support.
# "fan_center" rotates around the geometric center of each fan cage.
FAN_ROTATION_PIVOT_MODE = "support_contact"
# Size-dependent values below are specified for the 60 mm reference and scale
# linearly for each selected fan.
FAN_ROTATION_PIVOT_INWARD_X_AT_REFERENCE = 17.0
FAN_ROTATION_PIVOT_ABOVE_BOTTOM_Y = 1.0
FAN_ROTATION_PIVOT_Z = 2.25

# Fan airflow grille.
AIRFLOW_DIAMETER_AT_REFERENCE = 61.4
# Preserve at least the original 60 mm design's web between the airflow cut and
# the 7.6 mm countersink.  This caps the 40 mm opening instead of scaling it into
# its closer 32 mm mounting-hole pattern.
AIRFLOW_TO_COUNTERSINK_MIN_WEB = 0.8
GRILL_CENTER_DISK_DIAMETER_AT_REFERENCE = 21.4
GRILL_RING_CENTER_RADII_AT_REFERENCE = (16.7, 23.7)
GRILL_CONNECTION_OVERLAP = 1.0
# GRILL_BAR_WIDTH and GRILL_RING_WIDTH are selected in MATERIAL_PROFILES.

# Four fan screw holes in each cage.
FAN_HOLE_COUNTERSINK_DIAMETER = 7.6
FAN_HOLE_COUNTERSINK_DEPTH = 2.2
FAN_HOLE_COLLAR_DIAMETER = 6.0
FAN_HOLE_COLLAR_HEIGHT = 0.5
# FAN_HOLE_COUNTERSINK_ENABLED and FAN_HOLE_COLLARS_ENABLED are selected in
# MATERIAL_PROFILES.

# Optional U-shaped fan-wire exit cut into one wall from the open fan-insertion
# face. The offset is local to each fan and runs along the selected wall. On
# TOP/BOTTOM, positive values move right, so the defaults put a slot at each
# bottom-right.
FAN_WIRE_SLOT_ENABLED = True
FAN_WIRE_SLOT_SIDE = "BOTTOM"  # "TOP", "BOTTOM", "LEFT", or "RIGHT"
FAN_WIRE_SLOT_WIDTH = 5.0
FAN_WIRE_SLOT_DEPTH = 9.0
FAN_WIRE_SLOT_OFFSET_AT_REFERENCE = 22.0

# Optional bolt-on outlet splitter for a single fan. The thin square frame
# uses the standard fan holes, while paired hollow-center vanes redirect the
# otherwise wasted middle airflow toward left/right camera positions without
# the weight and blockage of a solid wedge. It is a separate part so the fan
# remains removable and should be printed rigid. Orient the fan to exhaust
# through this module toward the GoPro/cameras (negative Z). The outlet angle
# is measured per side from the fan axis.
SINGLE_FAN_AIRFLOW_SPLITTER_ENABLED = False
SINGLE_FAN_SPLITTER_OUTLET_ANGLE_DEG = 25.0
SINGLE_FAN_SPLITTER_VANE_LENGTH_Z = 25.0
SINGLE_FAN_SPLITTER_LEADING_EDGE_WIDTH = 2.4
SINGLE_FAN_SPLITTER_VANE_THICKNESS = 2.0
SINGLE_FAN_SPLITTER_PLATE_THICKNESS = 3.0
SINGLE_FAN_SPLITTER_EDGE_WEB = 3.0
SINGLE_FAN_SPLITTER_HOLE_CLEARANCE = 0.4
# Extra separation above the highest dropped-route receiver/stalk surface. A
# camera-facing notch is cut only when rear grilles and the dropped route are
# both active; the four-hole mounting plate remains complete.
SINGLE_FAN_SPLITTER_HOLDER_CLEARANCE = 1.0

# Twisted support joining the stalk to the selected fan cages.  A 38.1 mm hub
# segment per fan and 36 mm arm-start pitch reproduce the original dual layout.
SUPPORT_ENABLED = True
SUPPORT_HUB_WIDTH_PER_FAN = 38.1
SUPPORT_HUB_WIDTH_OVERRIDE = None
SUPPORT_HUB_BELOW_FAN_Y = 17.2
SUPPORT_ARM_START_PITCH_X = 36.0
SUPPORT_ARM_HUB_INSERT_Y = 2.0
SUPPORT_ARM_FAN_INSERT_Y_AT_REFERENCE = 4.0
SUPPORT_ARM_SECTIONS = 10
# SUPPORT_THICKNESS, SUPPORT_HUB_DEPTH_Y, and the arm widths are selected in
# MATERIAL_PROFILES.

# Stalk projecting from the support toward the camera mount.
STALK_ENABLED = True
STALK_LENGTH_Z = 46.2
# Signed lateral offset from the mounting-block centerline to the fan/support
# centerline. The stalk angle is derived from this amount and its effective
# length, so the same offset produces a greater angle on a shorter stalk.
# Positive values shift the fan array toward +X; zero keeps it centered.
STALK_LATERAL_DEFLECTION_X = 5.0
STALK_BOTTOM_Y_OVERHANG = 0.5
# Route the stalk downward from the GoPro receiver, rearward behind the camera
# plane, then slightly upward into the fan support. With DROP_Y greater than
# RETURN_RISE_Y, the fan sits lower by their difference relative to the mount.
# STALK_ROUTE_TRANSITION_ANGLE_DEG is measured away from the rearward Z axis;
# values above 45 degrees make the down/up legs more nearly vertical and may
# need removable external supports. STALK_ROUTE_BACK_Z controls the straight
# rearward section; STALK_LENGTH_Z controls only the original straight layout.
STALK_DROPPED_ROUTE_ENABLED = True
STALK_ROUTE_DROP_Y = 17.0
# STALK_ROUTE_BACK_Z = 30.0
STALK_ROUTE_BACK_Z = 40.0
STALK_ROUTE_RETURN_RISE_Y = 10.0
STALK_ROUTE_TRANSITION_ANGLE_DEG = 70.0
# STALK_WIDTH and STALK_DEPTH_Y are selected in MATERIAL_PROFILES.

# Two-hole receiver block fixed to the end of the stalk.
MOUNT_BLOCK_ENABLED = True
MOUNT_BLOCK_WIDTH = 28.45
MOUNT_BLOCK_HEIGHT_Z = 18.8
MOUNT_BLOCK_OVERLAP = 0.15
MOUNT_HOLE_SPACING = 12.0
# Legacy variable names retained for configuration compatibility.  In rigid
# mode these dimensions now describe a cylindrical, flat-bottomed counterbore
# for the mounting-screw head rather than a conical countersink.
MOUNT_COUNTERSINK_DIAMETER = 7.2
MOUNT_COUNTERSINK_DEPTH = 3.6
# MOUNT_BLOCK_DEPTH_Y, MOUNT_HOLE_DIAMETER, and MOUNT_COUNTERSINK_ENABLED are
# selected in MATERIAL_PROFILES.

# Detachable right-angle GoPro adapter fitted to the receiver block above.
# These defaults reproduce the newly measured ``gopro-dual-fan.stl`` mount.
# It remains a separate object in its assembled position so the M3 fasteners
# and heat inserts remain functional rather than being fused by the body union.
GOPRO_ADAPTER_ENABLED = True
GOPRO_ADAPTER_PRONG_COUNT = 3  # 3 matches the STL; set to 2 for a male mount.
GOPRO_ADAPTER_MATING_GAP = 0.0
GOPRO_ADAPTER_PLATE_WIDTH = 28.0
GOPRO_ADAPTER_PLATE_HEIGHT_Z = 18.09
GOPRO_ADAPTER_PLATE_DEPTH_Y = 11.44
GOPRO_ADAPTER_HOLE_Z_OFFSET = 0.13
GOPRO_ADAPTER_ROOT_WIDTH = 16.46

# M3 heat-insert sockets measured from the adapter STL. The larger pocket
# opens toward the stalk receiver and tapers into the smaller through pilot.
GOPRO_ADAPTER_INSERT_DIAMETER = 5.76
GOPRO_ADAPTER_INSERT_DEPTH = 9.49
GOPRO_ADAPTER_INSERT_PILOT_DIAMETER = 3.74
GOPRO_ADAPTER_INSERT_TRANSITION_DEPTH = 0.51

# GoPro interface dimensions. The two-prong option uses the same pitch and
# shifts the two fingers between the three-prong positions for compatibility.
GOPRO_PRONG_THICKNESS = 3.0
GOPRO_PRONG_GAP = 3.1
GOPRO_PRONG_RADIUS = 7.5
GOPRO_PIVOT_HOLE_DIAMETER = 5.0
GOPRO_PIVOT_FROM_MATING_FACE_Y = 23.51
GOPRO_PIVOT_BELOW_MOUNT_HOLES_Z = 13.23

# Captive M5 nut feature from the three-prong STL. It is omitted automatically
# for the two-prong option because the mating three-prong half carries the nut.
GOPRO_NUT_TRAP_ENABLED = True
GOPRO_NUT_BOSS_DIAMETER = 12.0
GOPRO_NUT_BOSS_DEPTH = 3.15
GOPRO_NUT_ACROSS_FLATS = 8.0


# Values controlled by MATERIAL_MODE.  Edit these profiles rather than the
# corresponding scalar defaults above when tuning a material mode.  Keeping a
# complete rigid profile also lets callers switch modes between repeated builds
# in the same Blender process without retaining TPU values.
_RIGID_MATERIAL_PROFILE = {
    "FAN_FRAME_WALL": 1.0,
    # Mixed-size layouts place cages at coordinates where Blender's EXACT
    # solver can leave tiny open triangles around otherwise valid screw holes.
    "FAN_CAGE_BOOLEAN_SOLVER": "MANIFOLD",
    "GRILL_THICKNESS": 2.8,
    "GRILL_BAR_WIDTH": 2.0,
    "GRILL_RING_WIDTH": 2.0,
    "FAN_HOLE_COUNTERSINK_ENABLED": True,
    "FAN_HOLE_COLLARS_ENABLED": True,
    "SUPPORT_THICKNESS": 6.5,
    "SUPPORT_HUB_DEPTH_Y": 10.0,
    "SUPPORT_ARM_CENTER_WIDTH": 18.0,
    "SUPPORT_ARM_FAN_WIDTH": 22.0,
    "STALK_WIDTH": 16.1,
    "STALK_DEPTH_Y": 10.0,
    "STALK_END_FLARES_ENABLED": False,
    "MOUNT_BLOCK_DEPTH_Y": 10.0,
    "MOUNT_HOLE_DIAMETER": 4.2,
    "MOUNT_COUNTERSINK_ENABLED": True,
}
MATERIAL_PROFILES = {
    "RIGID": _RIGID_MATERIAL_PROFILE,
    "TPU": {
        **_RIGID_MATERIAL_PROFILE,
        # Per-fan outer sizes grow automatically to preserve the same 0.35 mm
        # cavity clearance when this profile selects thicker walls.
        "FAN_FRAME_WALL": 4.0,
        "GRILL_THICKNESS": 3.5,
        "GRILL_BAR_WIDTH": 2.6,
        "GRILL_RING_WIDTH": 2.6,
        # Flat faces accept button/pan heads and broad washers without the
        # wedging and long-term preload loss caused by countersinks in TPU.
        "FAN_HOLE_COUNTERSINK_ENABLED": False,
        "FAN_HOLE_COLLARS_ENABLED": False,
        "SUPPORT_THICKNESS": 10.0,
        "SUPPORT_HUB_DEPTH_Y": 13.0,
        "SUPPORT_ARM_CENTER_WIDTH": 22.0,
        "SUPPORT_ARM_FAN_WIDTH": 28.0,
        "STALK_WIDTH": 22.0,
        "STALK_DEPTH_Y": 15.0,
        "STALK_END_FLARES_ENABLED": True,
        "MOUNT_BLOCK_DEPTH_Y": 11.0,
        "MOUNT_HOLE_DIAMETER": 3.6,
        # Keep the flexible receiver face unrecessed for a broad washer.
        "MOUNT_COUNTERSINK_ENABLED": False,
    },
}

# TPU stalk flares spread bending loads into the support hub and receiver.  The
# rigid profile keeps the original rectangular stalk in legacy front-grille
# mode; rear-grille mode enables these transitions for support-free printing.
STALK_END_FLARES_ENABLED = False
STALK_HUB_FLARE_WIDTH = 38.0
STALK_HUB_FLARE_LENGTH_Z = 8.0
STALK_MOUNT_FLARE_LENGTH_Z = 6.5
_APPLIED_MATERIAL_MODE = None


def apply_material_profile() -> None:
    global _APPLIED_MATERIAL_MODE
    global FAN_FRAME_WALL
    global FAN_CAGE_BOOLEAN_SOLVER
    global GRILL_THICKNESS
    global GRILL_BAR_WIDTH
    global GRILL_RING_WIDTH
    global FAN_HOLE_COUNTERSINK_ENABLED
    global FAN_HOLE_COLLARS_ENABLED
    global SUPPORT_THICKNESS
    global SUPPORT_HUB_DEPTH_Y
    global SUPPORT_ARM_CENTER_WIDTH
    global SUPPORT_ARM_FAN_WIDTH
    global STALK_WIDTH
    global STALK_DEPTH_Y
    global STALK_END_FLARES_ENABLED
    global MOUNT_BLOCK_DEPTH_Y
    global MOUNT_HOLE_DIAMETER
    global MOUNT_COUNTERSINK_ENABLED

    try:
        profile = MATERIAL_PROFILES[MATERIAL_MODE]
    except KeyError as error:
        choices = ", ".join(sorted(MATERIAL_PROFILES))
        raise ValueError(
            f"MATERIAL_MODE must be one of: {choices}; got {MATERIAL_MODE!r}"
        ) from error

    FAN_FRAME_WALL = profile["FAN_FRAME_WALL"]
    FAN_CAGE_BOOLEAN_SOLVER = profile["FAN_CAGE_BOOLEAN_SOLVER"]
    GRILL_THICKNESS = profile["GRILL_THICKNESS"]
    GRILL_BAR_WIDTH = profile["GRILL_BAR_WIDTH"]
    GRILL_RING_WIDTH = profile["GRILL_RING_WIDTH"]
    FAN_HOLE_COUNTERSINK_ENABLED = profile["FAN_HOLE_COUNTERSINK_ENABLED"]
    FAN_HOLE_COLLARS_ENABLED = profile["FAN_HOLE_COLLARS_ENABLED"]
    SUPPORT_THICKNESS = profile["SUPPORT_THICKNESS"]
    SUPPORT_HUB_DEPTH_Y = profile["SUPPORT_HUB_DEPTH_Y"]
    SUPPORT_ARM_CENTER_WIDTH = profile["SUPPORT_ARM_CENTER_WIDTH"]
    SUPPORT_ARM_FAN_WIDTH = profile["SUPPORT_ARM_FAN_WIDTH"]
    STALK_WIDTH = profile["STALK_WIDTH"]
    STALK_DEPTH_Y = profile["STALK_DEPTH_Y"]
    STALK_END_FLARES_ENABLED = profile["STALK_END_FLARES_ENABLED"]
    MOUNT_BLOCK_DEPTH_Y = profile["MOUNT_BLOCK_DEPTH_Y"]
    MOUNT_HOLE_DIAMETER = profile["MOUNT_HOLE_DIAMETER"]
    MOUNT_COUNTERSINK_ENABLED = profile["MOUNT_COUNTERSINK_ENABLED"]
    _APPLIED_MATERIAL_MODE = MATERIAL_MODE


def set_material_mode(mode: str) -> None:
    """Select a profile while leaving later explicit scalar overrides intact."""
    global MATERIAL_MODE
    MATERIAL_MODE = mode
    apply_material_profile()


set_material_mode(MATERIAL_MODE)


# ---------------------------------------------------------------------------
# Basic mesh helpers


def support_hub_width() -> float:
    if SUPPORT_HUB_WIDTH_OVERRIDE is not None:
        return float(SUPPORT_HUB_WIDTH_OVERRIDE)
    return SUPPORT_HUB_WIDTH_PER_FAN * FAN_COUNT


def fan_assembly_center_x() -> float:
    """Return the fan/support centerline relative to the receiver centerline."""
    return float(STALK_LATERAL_DEFLECTION_X)


def single_fan_splitter_opening_diameter(fan) -> float:
    hole_radius = (fan["hole_diameter"] + SINGLE_FAN_SPLITTER_HOLE_CLEARANCE) / 2.0
    hole_center_radius = math.sqrt(2.0) * fan["hole_spacing"] / 2.0
    hole_limited_diameter = 2.0 * (
        hole_center_radius - hole_radius - SINGLE_FAN_SPLITTER_EDGE_WEB
    )
    edge_limited_diameter = fan["size"] - 2.0 * SINGLE_FAN_SPLITTER_EDGE_WEB
    return min(hole_limited_diameter, edge_limited_diameter)


def resolve_fan_specs():
    if FAN_REFERENCE_SIZE_MM <= 0.0:
        raise ValueError("FAN_REFERENCE_SIZE_MM must be positive")
    if not isinstance(FAN_COUNT, int) or isinstance(FAN_COUNT, bool):
        raise ValueError("FAN_COUNT must be an integer")
    if not 1 <= FAN_COUNT <= 3:
        raise ValueError("FAN_COUNT must be 1, 2, or 3")
    if len(FAN_SIZES_MM) < FAN_COUNT:
        raise ValueError("FAN_SIZES_MM must contain at least FAN_COUNT entries")
    if len(FAN_ROTATIONS_DEG) < FAN_COUNT:
        raise ValueError("FAN_ROTATIONS_DEG must contain at least FAN_COUNT entries")
    if FAN_BODY_GAP_MM < 0.0:
        raise ValueError("FAN_BODY_GAP_MM cannot be negative")

    selected_sizes = []
    for index, raw_size in enumerate(FAN_SIZES_MM[:FAN_COUNT], start=1):
        if raw_size not in FAN_PRESETS:
            choices = ", ".join(str(size) for size in sorted(FAN_PRESETS))
            raise ValueError(
                f"Fan {index} size {raw_size!r} is unsupported; choose {choices} mm"
            )
        selected_sizes.append(float(raw_size))

    total_width = sum(selected_sizes) + FAN_BODY_GAP_MM * (FAN_COUNT - 1)
    cursor_x = -total_width / 2.0
    specs = []
    for index, (size, rotation) in enumerate(
        zip(selected_sizes, FAN_ROTATIONS_DEG[:FAN_COUNT]),
        start=1,
    ):
        if len(rotation) != 3 or not all(math.isfinite(value) for value in rotation):
            raise ValueError(
                f"FAN_ROTATIONS_DEG[{index - 1}] must contain three finite XYZ angles"
            )
        preset = FAN_PRESETS[int(size)]
        scale = size / FAN_REFERENCE_SIZE_MM
        array_center_x = cursor_x + size / 2.0
        center_x = fan_assembly_center_x() + array_center_x
        cavity_size = size + 2.0 * FAN_BODY_CLEARANCE_PER_SIDE
        hole_spacing = float(preset["hole_spacing"])
        hole_center_radius = math.sqrt(2.0) * hole_spacing / 2.0
        maximum_airflow_radius = (
            hole_center_radius
            - FAN_HOLE_COUNTERSINK_DIAMETER / 2.0
            - AIRFLOW_TO_COUNTERSINK_MIN_WEB
        )
        airflow_diameter = min(
            AIRFLOW_DIAMETER_AT_REFERENCE * scale,
            2.0 * maximum_airflow_radius,
        )
        support_arm_fan_insert_y = min(
            SUPPORT_ARM_FAN_INSERT_Y_AT_REFERENCE * scale,
            FAN_FRAME_WALL - BOOLEAN_OVERLAP,
        )
        specs.append(
            {
                "index": index,
                "size": size,
                "depth": float(preset["depth"]),
                "reference": preset["reference"],
                "center_x": center_x,
                "array_center_x": array_center_x,
                "rotation": tuple(float(value) for value in rotation),
                "cavity_size": cavity_size,
                "frame_size": cavity_size + 2.0 * FAN_FRAME_WALL,
                "airflow_diameter": airflow_diameter,
                "grill_center_disk_diameter": (
                    GRILL_CENTER_DISK_DIAMETER_AT_REFERENCE * scale
                ),
                "grill_ring_center_radii": tuple(
                    radius * scale
                    for radius in GRILL_RING_CENTER_RADII_AT_REFERENCE
                ),
                "hole_spacing": hole_spacing,
                "hole_diameter": float(preset["hole_diameter"]),
                "wire_slot_offset": FAN_WIRE_SLOT_OFFSET_AT_REFERENCE * scale,
                "pivot_inward_x": (
                    FAN_ROTATION_PIVOT_INWARD_X_AT_REFERENCE * scale
                ),
                "support_arm_fan_insert_y": support_arm_fan_insert_y,
                "support_arm_center_width": SUPPORT_ARM_CENTER_WIDTH * scale,
                "support_arm_fan_width": SUPPORT_ARM_FAN_WIDTH * scale,
            }
        )
        cursor_x += size + FAN_BODY_GAP_MM
    return specs


def validate_config() -> None:
    fan_specs = resolve_fan_specs()
    resolved_hub_width = support_hub_width()
    positive = {
        "FAN_REFERENCE_SIZE_MM": FAN_REFERENCE_SIZE_MM,
        "FAN_FRAME_DEPTH": FAN_FRAME_DEPTH,
        "FAN_FRAME_WALL": FAN_FRAME_WALL,
        "GRILL_THICKNESS": GRILL_THICKNESS,
        "AIRFLOW_TO_COUNTERSINK_MIN_WEB": AIRFLOW_TO_COUNTERSINK_MIN_WEB,
        "FAN_WIRE_SLOT_WIDTH": FAN_WIRE_SLOT_WIDTH,
        "FAN_WIRE_SLOT_DEPTH": FAN_WIRE_SLOT_DEPTH,
        "SINGLE_FAN_SPLITTER_VANE_LENGTH_Z": (
            SINGLE_FAN_SPLITTER_VANE_LENGTH_Z
        ),
        "SINGLE_FAN_SPLITTER_OUTLET_ANGLE_DEG": (
            SINGLE_FAN_SPLITTER_OUTLET_ANGLE_DEG
        ),
        "SINGLE_FAN_SPLITTER_LEADING_EDGE_WIDTH": (
            SINGLE_FAN_SPLITTER_LEADING_EDGE_WIDTH
        ),
        "SINGLE_FAN_SPLITTER_VANE_THICKNESS": (
            SINGLE_FAN_SPLITTER_VANE_THICKNESS
        ),
        "SINGLE_FAN_SPLITTER_PLATE_THICKNESS": (
            SINGLE_FAN_SPLITTER_PLATE_THICKNESS
        ),
        "SINGLE_FAN_SPLITTER_EDGE_WEB": SINGLE_FAN_SPLITTER_EDGE_WEB,
        "SINGLE_FAN_SPLITTER_HOLE_CLEARANCE": (
            SINGLE_FAN_SPLITTER_HOLE_CLEARANCE
        ),
        "SINGLE_FAN_SPLITTER_HOLDER_CLEARANCE": (
            SINGLE_FAN_SPLITTER_HOLDER_CLEARANCE
        ),
        "SUPPORT_THICKNESS": SUPPORT_THICKNESS,
        "SUPPORT_HUB_WIDTH": resolved_hub_width,
        "SUPPORT_HUB_WIDTH_PER_FAN": SUPPORT_HUB_WIDTH_PER_FAN,
        "SUPPORT_HUB_DEPTH_Y": SUPPORT_HUB_DEPTH_Y,
        "SUPPORT_HUB_BELOW_FAN_Y": SUPPORT_HUB_BELOW_FAN_Y,
        "SUPPORT_ARM_START_PITCH_X": SUPPORT_ARM_START_PITCH_X,
        "SUPPORT_ARM_CENTER_WIDTH": SUPPORT_ARM_CENTER_WIDTH,
        "SUPPORT_ARM_FAN_WIDTH": SUPPORT_ARM_FAN_WIDTH,
        "SUPPORT_ARM_HUB_INSERT_Y": SUPPORT_ARM_HUB_INSERT_Y,
        "SUPPORT_ARM_FAN_INSERT_Y_AT_REFERENCE": (
            SUPPORT_ARM_FAN_INSERT_Y_AT_REFERENCE
        ),
        "STALK_WIDTH": STALK_WIDTH,
        "STALK_DEPTH_Y": STALK_DEPTH_Y,
        "STALK_LENGTH_Z": STALK_LENGTH_Z,
        "STALK_ROUTE_DROP_Y": STALK_ROUTE_DROP_Y,
        "STALK_ROUTE_BACK_Z": STALK_ROUTE_BACK_Z,
        "STALK_ROUTE_RETURN_RISE_Y": STALK_ROUTE_RETURN_RISE_Y,
        "STALK_ROUTE_TRANSITION_ANGLE_DEG": (
            STALK_ROUTE_TRANSITION_ANGLE_DEG
        ),
        "MOUNT_BLOCK_WIDTH": MOUNT_BLOCK_WIDTH,
        "MOUNT_BLOCK_HEIGHT_Z": MOUNT_BLOCK_HEIGHT_Z,
        "MOUNT_BLOCK_DEPTH_Y": MOUNT_BLOCK_DEPTH_Y,
        "MOUNT_HOLE_DIAMETER": MOUNT_HOLE_DIAMETER,
        "GOPRO_ADAPTER_PLATE_WIDTH": GOPRO_ADAPTER_PLATE_WIDTH,
        "GOPRO_ADAPTER_PLATE_HEIGHT_Z": GOPRO_ADAPTER_PLATE_HEIGHT_Z,
        "GOPRO_ADAPTER_PLATE_DEPTH_Y": GOPRO_ADAPTER_PLATE_DEPTH_Y,
        "GOPRO_ADAPTER_ROOT_WIDTH": GOPRO_ADAPTER_ROOT_WIDTH,
        "GOPRO_ADAPTER_INSERT_DIAMETER": GOPRO_ADAPTER_INSERT_DIAMETER,
        "GOPRO_ADAPTER_INSERT_DEPTH": GOPRO_ADAPTER_INSERT_DEPTH,
        "GOPRO_ADAPTER_INSERT_PILOT_DIAMETER": GOPRO_ADAPTER_INSERT_PILOT_DIAMETER,
        "GOPRO_ADAPTER_INSERT_TRANSITION_DEPTH": GOPRO_ADAPTER_INSERT_TRANSITION_DEPTH,
        "GOPRO_PRONG_THICKNESS": GOPRO_PRONG_THICKNESS,
        "GOPRO_PRONG_GAP": GOPRO_PRONG_GAP,
        "GOPRO_PRONG_RADIUS": GOPRO_PRONG_RADIUS,
        "GOPRO_PIVOT_HOLE_DIAMETER": GOPRO_PIVOT_HOLE_DIAMETER,
        "GOPRO_PIVOT_FROM_MATING_FACE_Y": GOPRO_PIVOT_FROM_MATING_FACE_Y,
        "GOPRO_PIVOT_BELOW_MOUNT_HOLES_Z": GOPRO_PIVOT_BELOW_MOUNT_HOLES_Z,
        "GOPRO_NUT_BOSS_DIAMETER": GOPRO_NUT_BOSS_DIAMETER,
        "GOPRO_NUT_BOSS_DEPTH": GOPRO_NUT_BOSS_DEPTH,
        "GOPRO_NUT_ACROSS_FLATS": GOPRO_NUT_ACROSS_FLATS,
    }
    for name, value in positive.items():
        if value <= 0:
            raise ValueError(f"{name} must be positive")

    if not math.isfinite(STALK_LATERAL_DEFLECTION_X):
        raise ValueError("STALK_LATERAL_DEFLECTION_X must be finite")
    if (
        not math.isclose(STALK_LATERAL_DEFLECTION_X, 0.0, abs_tol=1.0e-12)
        and (not STALK_ENABLED or not MOUNT_BLOCK_ENABLED or not SUPPORT_ENABLED)
    ):
        raise ValueError(
            "STALK_LATERAL_DEFLECTION_X requires the stalk, mount block, "
            "and fan support"
        )

    boolean_options = {
        "FAN_GRILL_ON_BACK": FAN_GRILL_ON_BACK,
        "SINGLE_FAN_AIRFLOW_SPLITTER_ENABLED": (
            SINGLE_FAN_AIRFLOW_SPLITTER_ENABLED
        ),
        "STALK_DROPPED_ROUTE_ENABLED": STALK_DROPPED_ROUTE_ENABLED,
    }
    for name, value in boolean_options.items():
        if not isinstance(value, bool):
            raise ValueError(f"{name} must be True or False")

    if STALK_DROPPED_ROUTE_ENABLED:
        if not STALK_ENABLED or not MOUNT_BLOCK_ENABLED:
            raise ValueError(
                "STALK_DROPPED_ROUTE_ENABLED requires the stalk and mount block"
            )
        if STALK_ROUTE_DROP_Y <= STALK_ROUTE_RETURN_RISE_Y:
            raise ValueError(
                "STALK_ROUTE_DROP_Y must exceed STALK_ROUTE_RETURN_RISE_Y "
                "to lower the fan relative to the mount"
            )
        if STALK_ROUTE_TRANSITION_ANGLE_DEG >= 90.0:
            raise ValueError(
                "STALK_ROUTE_TRANSITION_ANGLE_DEG must be less than 90 degrees"
            )

    if SINGLE_FAN_AIRFLOW_SPLITTER_ENABLED:
        if FAN_COUNT != 1:
            raise ValueError(
                "SINGLE_FAN_AIRFLOW_SPLITTER_ENABLED requires FAN_COUNT = 1"
            )
        if SINGLE_FAN_SPLITTER_OUTLET_ANGLE_DEG > 45.0:
            raise ValueError(
                "SINGLE_FAN_SPLITTER_OUTLET_ANGLE_DEG must be at most 45 "
                "degrees for support-free printing"
            )
        fan = fan_specs[0]
        opening_radius = single_fan_splitter_opening_diameter(fan) / 2.0
        splitter_hole_radius = (
            fan["hole_diameter"] + SINGLE_FAN_SPLITTER_HOLE_CLEARANCE
        ) / 2.0
        if fan["hole_spacing"] / 2.0 + splitter_hole_radius >= fan["size"] / 2.0:
            raise ValueError("Single-fan splitter mounting holes exceed its frame")
        downstream_half_width = (
            SINGLE_FAN_SPLITTER_LEADING_EDGE_WIDTH / 2.0
            + SINGLE_FAN_SPLITTER_VANE_LENGTH_Z
            * math.tan(math.radians(SINGLE_FAN_SPLITTER_OUTLET_ANGLE_DEG))
        )
        if opening_radius <= 0.0:
            raise ValueError("Single-fan splitter airflow opening is not positive")
        if downstream_half_width >= opening_radius - BOOLEAN_OVERLAP:
            raise ValueError(
                "Single-fan splitter angle/length makes the downstream vanes "
                "wider than its airflow opening"
            )
        if SINGLE_FAN_SPLITTER_VANE_THICKNESS >= downstream_half_width:
            raise ValueError(
                "SINGLE_FAN_SPLITTER_VANE_THICKNESS leaves no hollow center"
            )

    if FAN_BODY_CLEARANCE_PER_SIDE < 0.0:
        raise ValueError("FAN_BODY_CLEARANCE_PER_SIDE cannot be negative")
    if FAN_FRAME_WALL <= BOOLEAN_OVERLAP:
        raise ValueError("FAN_FRAME_WALL must exceed BOOLEAN_OVERLAP")
    if not 0 < GRILL_THICKNESS < FAN_FRAME_DEPTH:
        raise ValueError("GRILL_THICKNESS must be less than FAN_FRAME_DEPTH")
    if FAN_GRILL_ON_BACK and SUPPORT_THICKNESS >= FAN_FRAME_DEPTH:
        raise ValueError(
            "Rear-grille support thickness must be less than FAN_FRAME_DEPTH"
        )

    if FAN_WIRE_SLOT_SIDE not in {"TOP", "BOTTOM", "LEFT", "RIGHT"}:
        raise ValueError(
            "FAN_WIRE_SLOT_SIDE must be TOP, BOTTOM, LEFT, or RIGHT"
        )
    if FAN_WIRE_SLOT_DEPTH >= FAN_FRAME_DEPTH - GRILL_THICKNESS:
        raise ValueError(
            "FAN_WIRE_SLOT_DEPTH must leave material between the slot and grille"
        )
    slot_half_width = FAN_WIRE_SLOT_WIDTH / 2.0
    for fan in fan_specs:
        label = f"Fan {fan['index']} ({fan['size']:.0f} mm)"
        frame_size = fan["frame_size"]
        cavity_size = frame_size - 2.0 * FAN_FRAME_WALL
        required_cavity = fan["size"] + 2.0 * FAN_BODY_CLEARANCE_PER_SIDE
        if cavity_size + 1.0e-9 < required_cavity:
            raise ValueError(
                f"{label} cavity is {cavity_size:.3f} mm; "
                f"at least {required_cavity:.3f} mm is required"
            )
        if fan["airflow_diameter"] <= 0.0:
            raise ValueError(f"{label} mounting pattern leaves no airflow opening")
        if fan["airflow_diameter"] >= frame_size:
            raise ValueError(f"{label} airflow opening does not fit its frame")
        if fan["grill_center_disk_diameter"] >= fan["airflow_diameter"]:
            raise ValueError(f"{label} center disk does not fit its airflow opening")
        straight_wall_half_length = frame_size / 2.0 - FAN_FRAME_CORNER_RADIUS
        if (
            abs(fan["wire_slot_offset"]) + slot_half_width
            > straight_wall_half_length
        ):
            raise ValueError(f"{label} wire slot does not fit its straight wall")
        airflow_radius = fan["airflow_diameter"] / 2.0
        for radius in fan["grill_ring_center_radii"]:
            if radius <= GRILL_RING_WIDTH / 2.0:
                raise ValueError(f"{label} grille ring is too small")
            if radius + GRILL_RING_WIDTH / 2.0 >= airflow_radius:
                raise ValueError(f"{label} grille ring exceeds the airflow opening")
        fan_hole_extent = (
            fan["hole_spacing"] / 2.0 + FAN_HOLE_COUNTERSINK_DIAMETER / 2.0
        )
        if fan_hole_extent >= frame_size / 2.0:
            raise ValueError(f"{label} mounting holes do not fit inside the frame")
        if not 0.0 <= fan["pivot_inward_x"] < frame_size / 2.0:
            raise ValueError(f"{label} rotation pivot must remain inside the frame")
        if not 0.0 < fan["support_arm_fan_insert_y"] <= FAN_FRAME_WALL:
            raise ValueError(f"{label} support-arm insertion must remain in the wall")
        if fan["support_arm_fan_insert_y"] >= frame_size / 2.0:
            raise ValueError(f"{label} support-arm insertion exceeds the frame")

    mount_hole_extent = MOUNT_HOLE_SPACING / 2.0 + MOUNT_COUNTERSINK_DIAMETER / 2.0
    if mount_hole_extent >= MOUNT_BLOCK_WIDTH / 2.0:
        raise ValueError("Mount holes or counterbores do not fit inside MOUNT_BLOCK_WIDTH")
    if MOUNT_COUNTERSINK_DIAMETER >= MOUNT_BLOCK_HEIGHT_Z:
        raise ValueError("Mount counterbores do not fit inside MOUNT_BLOCK_HEIGHT_Z")
    if MOUNT_COUNTERSINK_ENABLED and (
        MOUNT_COUNTERSINK_DIAMETER <= MOUNT_HOLE_DIAMETER
        or MOUNT_COUNTERSINK_DEPTH >= MOUNT_BLOCK_DEPTH_Y
    ):
        raise ValueError(
            "Rigid mount counterbores require a larger head diameter and "
            "must leave a positive-depth shoulder"
        )
    if (
        FAN_GRILL_ON_BACK
        and STALK_ENABLED
        and MOUNT_BLOCK_ENABLED
        and MOUNT_BLOCK_DEPTH_Y > STALK_DEPTH_Y
    ):
        raise ValueError(
            "Rear-grille support-free printing requires MOUNT_BLOCK_DEPTH_Y "
            "to be no greater than STALK_DEPTH_Y"
        )

    if GOPRO_ADAPTER_PRONG_COUNT not in {2, 3}:
        raise ValueError("GOPRO_ADAPTER_PRONG_COUNT must be 2 or 3")
    if GOPRO_ADAPTER_MATING_GAP < 0.0:
        raise ValueError("GOPRO_ADAPTER_MATING_GAP cannot be negative")
    if GOPRO_ADAPTER_ENABLED and not MOUNT_BLOCK_ENABLED:
        raise ValueError("GOPRO_ADAPTER_ENABLED requires MOUNT_BLOCK_ENABLED")
    if (
        GOPRO_ADAPTER_INSERT_DEPTH + GOPRO_ADAPTER_INSERT_TRANSITION_DEPTH
        >= GOPRO_ADAPTER_PLATE_DEPTH_Y
    ):
        raise ValueError("GoPro adapter insert socket leaves no through-pilot depth")
    adapter_hole_extent_x = (
        MOUNT_HOLE_SPACING / 2.0 + GOPRO_ADAPTER_INSERT_DIAMETER / 2.0
    )
    if adapter_hole_extent_x >= GOPRO_ADAPTER_PLATE_WIDTH / 2.0:
        raise ValueError("GoPro adapter insert sockets do not fit across the plate")
    adapter_hole_extent_z = (
        abs(GOPRO_ADAPTER_HOLE_Z_OFFSET)
        + GOPRO_ADAPTER_INSERT_DIAMETER / 2.0
    )
    if adapter_hole_extent_z >= GOPRO_ADAPTER_PLATE_HEIGHT_Z / 2.0:
        raise ValueError("GoPro adapter insert sockets do not fit vertically")
    prong_pack_width = (
        GOPRO_ADAPTER_PRONG_COUNT * GOPRO_PRONG_THICKNESS
        + (GOPRO_ADAPTER_PRONG_COUNT - 1) * GOPRO_PRONG_GAP
    )
    if prong_pack_width >= GOPRO_ADAPTER_ROOT_WIDTH:
        raise ValueError("GoPro prong pack must be narrower than the adapter root")
    if GOPRO_PIVOT_HOLE_DIAMETER >= 2.0 * GOPRO_PRONG_RADIUS:
        raise ValueError("GOPRO_PIVOT_HOLE_DIAMETER must fit inside the prongs")
    if GOPRO_NUT_ACROSS_FLATS <= GOPRO_PIVOT_HOLE_DIAMETER:
        raise ValueError("GOPRO_NUT_ACROSS_FLATS must exceed the pivot hole")
    if GOPRO_NUT_ACROSS_FLATS >= GOPRO_NUT_BOSS_DIAMETER:
        raise ValueError("GOPRO_NUT_ACROSS_FLATS must fit inside the nut boss")

    if FAN_ROTATION_PIVOT_MODE not in {"support_contact", "fan_center"}:
        raise ValueError('FAN_ROTATION_PIVOT_MODE must be "support_contact" or "fan_center"')
    if SUPPORT_ARM_SECTIONS < 2:
        raise ValueError("SUPPORT_ARM_SECTIONS must be at least 2")
    if SUPPORT_ARM_HUB_INSERT_Y >= SUPPORT_HUB_DEPTH_Y:
        raise ValueError("SUPPORT_ARM_HUB_INSERT_Y must be less than SUPPORT_HUB_DEPTH_Y")
    if stalk_end_flares_active():
        if STALK_HUB_FLARE_WIDTH <= STALK_WIDTH:
            raise ValueError("STALK_HUB_FLARE_WIDTH must exceed STALK_WIDTH")
        if STALK_HUB_FLARE_WIDTH >= resolved_hub_width:
            raise ValueError("STALK_HUB_FLARE_WIDTH must fit inside SUPPORT_HUB_WIDTH")
        if STALK_HUB_FLARE_LENGTH_Z <= 0.0:
            raise ValueError("STALK_HUB_FLARE_LENGTH_Z must be positive")
        if STALK_MOUNT_FLARE_LENGTH_Z <= 0.0:
            raise ValueError("STALK_MOUNT_FLARE_LENGTH_Z must be positive")
        if (
            STALK_HUB_FLARE_LENGTH_Z + STALK_MOUNT_FLARE_LENGTH_Z
            >= effective_stalk_path_length()
        ):
            raise ValueError("Stalk flare lengths must leave a straight center section")
        minimum_mount_flare_length = max(
            0.0, (MOUNT_BLOCK_WIDTH - STALK_WIDTH) / 2.0
        )
        if STALK_MOUNT_FLARE_LENGTH_Z < minimum_mount_flare_length:
            raise ValueError(
                "STALK_MOUNT_FLARE_LENGTH_Z must provide a 45-degree or "
                "shallower receiver transition"
            )
    if STALK_ENABLED:
        compensated_stalk_width = STALK_WIDTH * stalk_lateral_width_scale()
        if MOUNT_BLOCK_ENABLED and compensated_stalk_width > MOUNT_BLOCK_WIDTH:
            raise ValueError(
                "STALK_LATERAL_DEFLECTION_X and the effective stalk length "
                f"require {compensated_stalk_width:.3f} mm of global-X stalk "
                f"width, exceeding MOUNT_BLOCK_WIDTH={MOUNT_BLOCK_WIDTH:.3f} mm"
            )
        support_interface_width = (
            STALK_HUB_FLARE_WIDTH
            if stalk_end_flares_active()
            else resolved_hub_width
        )
        if SUPPORT_ENABLED and compensated_stalk_width > support_interface_width:
            raise ValueError(
                "STALK_LATERAL_DEFLECTION_X and the effective stalk length "
                f"require {compensated_stalk_width:.3f} mm of global-X stalk "
                "width, exceeding the support-side interface width "
                f"{support_interface_width:.3f} mm"
            )
    if STALK_DROPPED_ROUTE_ENABLED:
        route_corner_setback = STALK_DEPTH_Y / 2.0 * math.tan(
            math.radians(STALK_ROUTE_TRANSITION_ANGLE_DEG) / 2.0
        )
        drop_run_z = stalk_route_transition_z(STALK_ROUTE_DROP_Y)
        rise_run_z = stalk_route_transition_z(STALK_ROUTE_RETURN_RISE_Y)
        if min(drop_run_z, rise_run_z) <= route_corner_setback:
            raise ValueError(
                "STALK_ROUTE_DROP_Y and STALK_ROUTE_RETURN_RISE_Y must leave "
                "enough transition run for the routed stalk thickness"
            )
        if STALK_ROUTE_BACK_Z <= 2.0 * route_corner_setback:
            raise ValueError(
                "STALK_ROUTE_BACK_Z is too short for the routed stalk thickness "
                "at the selected transition angle"
            )


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


def fan_inward_sign(fan) -> float:
    if fan["array_center_x"] < -1.0e-9:
        return 1.0
    if fan["array_center_x"] > 1.0e-9:
        return -1.0
    return 0.0


def fan_grill_z_bounds():
    if FAN_GRILL_ON_BACK:
        return (FAN_FRAME_DEPTH - GRILL_THICKNESS, FAN_FRAME_DEPTH)
    return (0.0, GRILL_THICKNESS)


def fan_housing_z_bounds():
    if FAN_GRILL_ON_BACK:
        return (0.0, FAN_FRAME_DEPTH - GRILL_THICKNESS + BOOLEAN_OVERLAP)
    return (GRILL_THICKNESS - BOOLEAN_OVERLAP, FAN_FRAME_DEPTH)


def attachment_plane_z() -> float:
    """Return the common grille/support/stalk print datum."""
    return FAN_FRAME_DEPTH if FAN_GRILL_ON_BACK else 0.0


def support_z_bounds():
    plane_z = attachment_plane_z()
    if FAN_GRILL_ON_BACK:
        return (plane_z - SUPPORT_THICKNESS, plane_z)
    return (plane_z, plane_z + SUPPORT_THICKNESS)


def support_arm_center_z() -> float:
    z0, z1 = support_z_bounds()
    return (z0 + z1) / 2.0


def stalk_route_transition_z(delta_y: float) -> float:
    angle = math.radians(STALK_ROUTE_TRANSITION_ANGLE_DEG)
    return delta_y / math.tan(angle)


def effective_stalk_length_z() -> float:
    if STALK_DROPPED_ROUTE_ENABLED:
        return (
            stalk_route_transition_z(STALK_ROUTE_DROP_Y)
            + STALK_ROUTE_BACK_Z
            + stalk_route_transition_z(STALK_ROUTE_RETURN_RISE_Y)
        )
    return STALK_LENGTH_Z


def stalk_z_bounds():
    plane_z = attachment_plane_z()
    length_z = effective_stalk_length_z()
    if FAN_GRILL_ON_BACK:
        return (plane_z - length_z, plane_z)
    return (-length_z, plane_z + BOOLEAN_OVERLAP)


def stalk_end_flares_active() -> bool:
    # Rear-face-down printing starts at the support-side end of the stalk.
    # A wide first-layer root and a 45-degree receiver transition avoid a
    # cantilevered receiver block even when the rigid profile disables the
    # legacy assembly-orientation flares.
    return STALK_END_FLARES_ENABLED or FAN_GRILL_ON_BACK


def fan_rotation_pivot(fan):
    center_x = fan["center_x"]
    if FAN_ROTATION_PIVOT_MODE == "fan_center":
        return (center_x, 0.0, FAN_FRAME_DEPTH / 2.0)

    pivot_z = FAN_ROTATION_PIVOT_Z
    if FAN_GRILL_ON_BACK:
        pivot_z = FAN_FRAME_DEPTH - pivot_z
    return (
        center_x + fan_inward_sign(fan) * fan["pivot_inward_x"],
        -fan["frame_size"] / 2.0 + FAN_ROTATION_PIVOT_ABOVE_BOTTOM_Y,
        pivot_z,
    )


def fan_rotation_quaternion(rotation_deg):
    angles = tuple(math.radians(value) for value in rotation_deg)
    return Euler(angles, "XYZ").to_quaternion()


def transform_fan_point(point, fan):
    pivot = Vector(fan_rotation_pivot(fan))
    rotation = fan_rotation_quaternion(fan["rotation"])
    return pivot + rotation @ (Vector(point) - pivot)


def rotate_fan_part(obj, fan) -> None:
    if all(abs(value) < 1.0e-12 for value in fan["rotation"]):
        return

    pivot = fan_rotation_pivot(fan)
    rotation = fan_rotation_quaternion(fan["rotation"]).to_matrix().to_4x4()
    transform = (
        Matrix.Translation(pivot)
        @ rotation
        @ Matrix.Translation(tuple(-value for value in pivot))
    )
    # Boolean tools created by Blender primitives retain translation in their
    # object matrix, while generated cage meshes use world-space vertices and
    # an identity matrix.  Bake either representation before applying the
    # shared fan rotation so cages and post-assembly cutters stay aligned.
    obj.data.transform(transform @ obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
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


def yz_polygon_prism(name: str, loop, x0: float, x1: float):
    if x1 <= x0:
        raise ValueError(f"{name}: x1 must be greater than x0")
    count = len(loop)
    vertices = [(x0, y, z) for y, z in loop]
    vertices.extend((x1, y, z) for y, z in loop)
    center_y = sum(y for y, _ in loop) / count
    center_z = sum(z for _, z in loop) / count
    vertices.extend(((x0, center_y, center_z), (x1, center_y, center_z)))
    left_center = count * 2
    right_center = left_center + 1

    faces = []
    for i in range(count):
        j = (i + 1) % count
        faces.append([i, j, count + j, count + i])
        faces.append([left_center, j, i])
        faces.append([right_center, count + i, count + j])
    return create_mesh_object(name, vertices, faces)


def xz_polygon_prism(name: str, loop, y0: float, y1: float):
    if y1 <= y0:
        raise ValueError(f"{name}: y1 must be greater than y0")
    count = len(loop)
    vertices = [(x, y0, z) for x, z in loop]
    vertices.extend((x, y1, z) for x, z in loop)
    center_x = sum(x for x, _ in loop) / count
    center_z = sum(z for _, z in loop) / count
    vertices.extend(((center_x, y0, center_z), (center_x, y1, center_z)))
    back_center = count * 2
    front_center = back_center + 1

    faces = []
    for i in range(count):
        j = (i + 1) % count
        faces.append([i, j, count + j, count + i])
        faces.append([back_center, j, i])
        faces.append([front_center, count + i, count + j])
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


def radial_profile_y(name: str, profile, x=0.0, z=0.0):
    if len(profile) < 2:
        raise ValueError(f"{name}: radial profile requires at least two sections")
    vertices = []
    for y, radius in profile:
        for segment in range(CYLINDER_SEGMENTS):
            angle = 2.0 * math.pi * segment / CYLINDER_SEGMENTS
            vertices.append(
                (
                    x + radius * math.cos(angle),
                    y,
                    z + radius * math.sin(angle),
                )
            )

    faces = []
    for section in range(len(profile) - 1):
        current = section * CYLINDER_SEGMENTS
        following = (section + 1) * CYLINDER_SEGMENTS
        for segment in range(CYLINDER_SEGMENTS):
            nxt = (segment + 1) % CYLINDER_SEGMENTS
            faces.append(
                [
                    current + segment,
                    current + nxt,
                    following + nxt,
                    following + segment,
                ]
            )

    vertices.extend(
        (
            (x, profile[0][0], z),
            (x, profile[-1][0], z),
        )
    )
    first_center = len(vertices) - 2
    last_center = len(vertices) - 1
    last_ring = (len(profile) - 1) * CYLINDER_SEGMENTS
    for segment in range(CYLINDER_SEGMENTS):
        nxt = (segment + 1) % CYLINDER_SEGMENTS
        faces.append([first_center, segment, nxt])
        faces.append([last_center, last_ring + nxt, last_ring + segment])
    return create_mesh_object(name, vertices, faces)


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


def mesh_volume(obj) -> float:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    volume = abs(bm.calc_volume(signed=True)) if bm.faces else 0.0
    bm.free()
    return volume


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
    if DEBUG_BOOLEAN_STEPS:
        print(
            f"{label}: operation={operation} "
            f"non_manifold_edges={non_manifold_edge_count(base)}"
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


def boolean_difference(
    base,
    tools,
    label="Cut",
    solver=None,
    require_geometry_change=False,
):
    tool = join_disconnected_tools(label + "_Tools", list(tools))
    return apply_boolean(
        base,
        tool,
        "DIFFERENCE",
        label,
        solver=solver,
        require_geometry_change=require_geometry_change,
    )


# ---------------------------------------------------------------------------
# Parametric parts


def fan_hole_centers(fan):
    half = fan["hole_spacing"] / 2.0
    center_x = fan["center_x"]
    return [
        (center_x + sx * half, sy * half)
        for sx in (-1.0, 1.0)
        for sy in (-1.0, 1.0)
    ]


def create_fan_wire_slot_cutter(fan, outside_extension=0.0):
    index = fan["index"]
    center_x = fan["center_x"]
    frame_size = fan["frame_size"]
    # Extend through the selected wall and beyond the open fan-insertion face
    # so the result is a true U-shaped exit rather than an enclosed pocket.
    cutter_depth = FAN_WIRE_SLOT_DEPTH + 2.0 * BOOLEAN_OVERLAP
    if FAN_GRILL_ON_BACK:
        cutter_z = FAN_WIRE_SLOT_DEPTH / 2.0 - BOOLEAN_OVERLAP
    else:
        cutter_z = (
            FAN_FRAME_DEPTH
            - FAN_WIRE_SLOT_DEPTH / 2.0
            + BOOLEAN_OVERLAP
        )
    if FAN_WIRE_SLOT_SIDE in {"TOP", "BOTTOM"}:
        side_sign = 1.0 if FAN_WIRE_SLOT_SIDE == "TOP" else -1.0
        cutter_dimensions = (
            FAN_WIRE_SLOT_WIDTH,
            FAN_FRAME_WALL + 2.0 * BOOLEAN_OVERLAP + outside_extension,
            cutter_depth,
        )
        cutter_location = (
            center_x + fan["wire_slot_offset"],
            side_sign
            * (
                frame_size / 2.0
                - FAN_FRAME_WALL / 2.0
                + outside_extension / 2.0
            ),
            cutter_z,
        )
    else:
        side_sign = 1.0 if FAN_WIRE_SLOT_SIDE == "RIGHT" else -1.0
        cutter_dimensions = (
            FAN_FRAME_WALL + 2.0 * BOOLEAN_OVERLAP + outside_extension,
            FAN_WIRE_SLOT_WIDTH,
            cutter_depth,
        )
        cutter_location = (
            center_x
            + side_sign
            * (
                frame_size / 2.0
                - FAN_FRAME_WALL / 2.0
                + outside_extension / 2.0
            ),
            fan["wire_slot_offset"],
            cutter_z,
        )
    return add_box(
        f"Fan_{index}_Wire_Slot",
        cutter_dimensions,
        cutter_location,
    )


def cut_fan_wire_slot(cage, fan) -> None:
    if not FAN_WIRE_SLOT_ENABLED:
        return

    index = fan["index"]
    cutter = create_fan_wire_slot_cutter(fan)
    boolean_difference(
        cage,
        [cutter],
        f"Fan_{index}_Wire_Slot_Cut",
        solver=FAN_CAGE_BOOLEAN_SOLVER,
    )


def recut_assembled_fan_wire_slots(holder, fan_specs, assembly_vertices) -> None:
    """Keep later assembly unions from filling rear fan-wire exits."""
    if not FAN_GRILL_ON_BACK or not FAN_WIRE_SLOT_ENABLED:
        return

    cutters = []
    for fan in fan_specs:
        outside_extension = 0.0
        if assembly_vertices and FAN_WIRE_SLOT_SIDE == "BOTTOM":
            pivot = Vector(fan_rotation_pivot(fan))
            inverse_rotation = fan_rotation_quaternion(fan["rotation"]).inverted()
            minimum_assembly_y = min(
                (
                    pivot
                    + inverse_rotation @ (Vector(vertex) - pivot)
                ).y
                for vertex in assembly_vertices
            )
            outside_extension = max(
                0.0,
                -fan["frame_size"] / 2.0 - minimum_assembly_y,
            )
        cutter = create_fan_wire_slot_cutter(fan, outside_extension)
        rotate_fan_part(cutter, fan)
        cutters.append(cutter)
    boolean_difference(
        holder,
        cutters,
        "Assembly_Wire_Slot_Recut",
        solver=ASSEMBLY_BOOLEAN_SOLVER,
    )


def create_fan_cage(fan):
    index = fan["index"]
    center_x = fan["center_x"]
    frame_size = fan["frame_size"]
    prefix = f"Fan_{index}"
    grill_z0, grill_z1 = fan_grill_z_bounds()
    housing_z0, housing_z1 = fan_housing_z_bounds()

    grill = rounded_rectangle_prism(
        prefix + "_Grill_Frame",
        frame_size,
        frame_size,
        FAN_FRAME_CORNER_RADIUS,
        grill_z0,
        grill_z1,
        center_x=center_x,
    )
    grill_cutters = [
        add_cylinder_z(
            prefix + "_Airflow_Cut",
            fan["airflow_diameter"] / 2.0,
            grill_z0 - BOOLEAN_OVERLAP,
            grill_z1 + BOOLEAN_OVERLAP,
            x=center_x,
        )
    ]
    boolean_difference(
        grill,
        grill_cutters,
        prefix + "_Openings",
        solver=FAN_CAGE_BOOLEAN_SOLVER,
    )

    housing = rounded_rectangle_prism(
        prefix + "_Housing",
        frame_size,
        frame_size,
        FAN_FRAME_CORNER_RADIUS,
        housing_z0,
        housing_z1,
        center_x=center_x,
    )
    inner_size = fan["cavity_size"]
    housing_cut = add_box(
        prefix + "_Housing_Opening",
        (
            inner_size,
            inner_size,
            housing_z1 - housing_z0 + 2.0 * BOOLEAN_OVERLAP,
        ),
        (center_x, 0.0, (housing_z0 + housing_z1) / 2.0),
    )
    boolean_difference(
        housing,
        [housing_cut],
        prefix + "_Housing_Cut",
        solver=FAN_CAGE_BOOLEAN_SOLVER,
    )
    boolean_union(
        grill,
        housing,
        prefix + "_Housing_Union",
        solver=FAN_CAGE_BOOLEAN_SOLVER,
    )

    bar_length = fan["airflow_diameter"] + 2.0 * GRILL_CONNECTION_OVERLAP
    horizontal_bar = add_box(
        prefix + "_Horizontal_Bar",
        (bar_length, GRILL_BAR_WIDTH, GRILL_THICKNESS),
        (center_x, 0.0, (grill_z0 + grill_z1) / 2.0),
    )
    vertical_bar = add_box(
        prefix + "_Vertical_Bar",
        (GRILL_BAR_WIDTH, bar_length, GRILL_THICKNESS),
        (center_x, 0.0, (grill_z0 + grill_z1) / 2.0),
    )
    boolean_union(
        grill,
        horizontal_bar,
        prefix + "_Horizontal_Bar_Union",
        solver=FAN_CAGE_BOOLEAN_SOLVER,
    )
    boolean_union(
        grill,
        vertical_bar,
        prefix + "_Vertical_Bar_Union",
        solver=FAN_CAGE_BOOLEAN_SOLVER,
    )

    for ring_index, radius in enumerate(
        fan["grill_ring_center_radii"],
        start=1,
    ):
        ring = annular_prism(
            f"{prefix}_Ring_{ring_index}",
            center_x,
            0.0,
            radius - GRILL_RING_WIDTH / 2.0,
            radius + GRILL_RING_WIDTH / 2.0,
            grill_z0,
            grill_z1,
        )
        boolean_union(
            grill,
            ring,
            prefix + f"_Ring_{ring_index}_Union",
            solver=FAN_CAGE_BOOLEAN_SOLVER,
        )

    center_disk = add_cylinder_z(
        prefix + "_Center_Disk",
        fan["grill_center_disk_diameter"] / 2.0,
        grill_z0,
        grill_z1,
        x=center_x,
    )
    boolean_union(
        grill,
        center_disk,
        prefix + "_Center_Disk_Union",
        solver=FAN_CAGE_BOOLEAN_SOLVER,
    )

    if FAN_HOLE_COLLARS_ENABLED and FAN_HOLE_COLLAR_HEIGHT > 0.0:
        if FAN_GRILL_ON_BACK:
            collar_z0 = grill_z0 - FAN_HOLE_COLLAR_HEIGHT
            collar_z1 = grill_z0 + BOOLEAN_OVERLAP
        else:
            collar_z0 = grill_z1 - BOOLEAN_OVERLAP
            collar_z1 = grill_z1 + FAN_HOLE_COLLAR_HEIGHT
        for collar_index, (x, y) in enumerate(fan_hole_centers(fan), start=1):
            collar = add_cylinder_z(
                f"{prefix}_Screw_Collar_{collar_index}",
                FAN_HOLE_COLLAR_DIAMETER / 2.0,
                collar_z0,
                collar_z1,
                x=x,
                y=y,
            )
            boolean_union(
                grill,
                collar,
                prefix + f"_Screw_Collar_{collar_index}_Union",
                solver=FAN_CAGE_BOOLEAN_SOLVER,
            )

    # Drill after adding the optional solid collars. This avoids coincident
    # cylindrical surfaces between pre-cut holes and annular collar meshes.
    if FAN_GRILL_ON_BACK:
        screw_hole_bottom = grill_z0
        if FAN_HOLE_COLLARS_ENABLED:
            screw_hole_bottom -= FAN_HOLE_COLLAR_HEIGHT
        screw_hole_bottom -= BOOLEAN_OVERLAP
        screw_hole_top = grill_z1 + BOOLEAN_OVERLAP
    else:
        screw_hole_bottom = grill_z0 - BOOLEAN_OVERLAP
        screw_hole_top = grill_z1
        if FAN_HOLE_COLLARS_ENABLED:
            screw_hole_top += FAN_HOLE_COLLAR_HEIGHT
        screw_hole_top += BOOLEAN_OVERLAP
    screw_hole_cuts = []
    for hole_index, (x, y) in enumerate(fan_hole_centers(fan), start=1):
        screw_hole_cuts.append(
            add_cylinder_z(
                f"{prefix}_Screw_Cut_{hole_index}",
                fan["hole_diameter"] / 2.0,
                screw_hole_bottom,
                screw_hole_top,
                x=x,
                y=y,
            )
        )
    boolean_difference(
        grill,
        screw_hole_cuts,
        prefix + "_Screw_Holes",
        solver=FAN_CAGE_BOOLEAN_SOLVER,
    )

    if FAN_HOLE_COUNTERSINK_ENABLED and FAN_HOLE_COUNTERSINK_DEPTH > 0.0:
        countersinks = []
        for hole_index, (x, y) in enumerate(fan_hole_centers(fan), start=1):
            if FAN_GRILL_ON_BACK:
                radius1 = fan["hole_diameter"] / 2.0
                radius2 = FAN_HOLE_COUNTERSINK_DIAMETER / 2.0
                countersink_z0 = grill_z1 - FAN_HOLE_COUNTERSINK_DEPTH
                countersink_z1 = grill_z1 + BOOLEAN_OVERLAP
            else:
                radius1 = FAN_HOLE_COUNTERSINK_DIAMETER / 2.0
                radius2 = fan["hole_diameter"] / 2.0
                countersink_z0 = grill_z0 - BOOLEAN_OVERLAP
                countersink_z1 = grill_z0 + FAN_HOLE_COUNTERSINK_DEPTH
            countersinks.append(
                add_cone_z(
                    f"{prefix}_Screw_Countersink_{hole_index}",
                    radius1,
                    radius2,
                    countersink_z0,
                    countersink_z1,
                    x=x,
                    y=y,
                )
            )
        boolean_difference(
            grill,
            countersinks,
            prefix + "_Countersinks",
            solver=FAN_CAGE_BOOLEAN_SOLVER,
        )

    cut_fan_wire_slot(grill, fan)

    grill.name = prefix + "_Cage"
    grill.data.name = prefix + "_Cage_Mesh"
    return grill


def single_fan_splitter_mount_face_z(fan) -> float:
    # With a rear grille, the fan seats against the grille's inner face or the
    # rigid screw collars that protrude from it. The splitter bolts against the
    # resulting camera-side fan face. With the legacy front grille, the
    # camera-facing exterior grille itself is the mounting face.
    if FAN_GRILL_ON_BACK:
        grill_inner_z = fan_grill_z_bounds()[0]
        if FAN_HOLE_COLLARS_ENABLED:
            grill_inner_z -= FAN_HOLE_COLLAR_HEIGHT
        return grill_inner_z - fan["depth"]
    return attachment_plane_z()


def single_fan_splitter_holder_clearance_y() -> float:
    return (
        mount_stalk_center_y()
        + max(STALK_DEPTH_Y, MOUNT_BLOCK_DEPTH_Y) / 2.0
        + SINGLE_FAN_SPLITTER_HOLDER_CLEARANCE
    )


def create_single_fan_splitter_holder_clearance_cutter(
    fan,
    opening_radius: float,
    plate_z0: float,
    downstream_z: float,
):
    if not FAN_GRILL_ON_BACK or not STALK_DROPPED_ROUTE_ENABLED:
        return None

    margin = 2.0 * BOOLEAN_OVERLAP
    cutter_z0 = downstream_z - margin
    cutter_z1 = plate_z0
    cutter_radius = opening_radius + margin
    cutter = add_box(
        "Single_Fan_Splitter_Downstream_Clearance_Envelope",
        (
            2.0 * cutter_radius,
            2.0 * cutter_radius,
            cutter_z1 - cutter_z0,
        ),
        (
            fan["center_x"],
            0.0,
            (cutter_z0 + cutter_z1) / 2.0,
        ),
    )
    rotate_fan_part(cutter, fan)

    bpy.context.view_layer.update()
    corners = [
        cutter.matrix_world @ Vector(corner) for corner in cutter.bound_box
    ]
    minimum = Vector(
        tuple(min(corner[axis] for corner in corners) for axis in range(3))
    )
    maximum = Vector(
        tuple(max(corner[axis] for corner in corners) for axis in range(3))
    )
    clearance_y = single_fan_splitter_holder_clearance_y()
    if clearance_y <= minimum.y + 1.0e-9:
        bpy.data.objects.remove(cutter, do_unlink=True)
        return None
    if clearance_y >= maximum.y - BOOLEAN_OVERLAP:
        bpy.data.objects.remove(cutter, do_unlink=True)
        raise ValueError(
            "Dropped-route holder clearance would remove the single-fan "
            "splitter vanes"
        )

    lower_half_space = add_box(
        "Single_Fan_Splitter_Holder_Clearance_Half_Space",
        (
            maximum.x - minimum.x + 2.0 * margin,
            clearance_y - minimum.y + margin,
            maximum.z - minimum.z + 2.0 * margin,
        ),
        (
            (minimum.x + maximum.x) / 2.0,
            (minimum.y + clearance_y - margin) / 2.0,
            (minimum.z + maximum.z) / 2.0,
        ),
    )
    apply_boolean(
        cutter,
        lower_half_space,
        "INTERSECT",
        "Single_Fan_Splitter_Holder_Clearance_Intersection",
        solver=FAN_CAGE_BOOLEAN_SOLVER,
        require_geometry_change=True,
    )
    return cutter


def create_single_fan_airflow_splitter(fan):
    center_x = fan["center_x"]
    mount_face_z = single_fan_splitter_mount_face_z(fan)
    plate_z0 = mount_face_z - SINGLE_FAN_SPLITTER_PLATE_THICKNESS
    plate_z1 = mount_face_z
    root_z = plate_z0 + BOOLEAN_OVERLAP
    downstream_z = root_z - SINGLE_FAN_SPLITTER_VANE_LENGTH_Z

    frame = rounded_rectangle_prism(
        "Single_Fan_Splitter_Mounting_Frame",
        fan["size"],
        fan["size"],
        min(FAN_FRAME_CORNER_RADIUS, fan["size"] / 10.0),
        plate_z0,
        plate_z1,
        center_x=center_x,
    )
    opening_diameter = single_fan_splitter_opening_diameter(fan)
    cutters = [
        add_cylinder_z(
            "Single_Fan_Splitter_Airflow_Opening",
            opening_diameter / 2.0,
            plate_z0 - BOOLEAN_OVERLAP,
            plate_z1 + BOOLEAN_OVERLAP,
            x=center_x,
        )
    ]
    splitter_hole_radius = (
        fan["hole_diameter"] + SINGLE_FAN_SPLITTER_HOLE_CLEARANCE
    ) / 2.0
    for hole_index, (x, y) in enumerate(fan_hole_centers(fan), start=1):
        cutters.append(
            add_cylinder_z(
                f"Single_Fan_Splitter_Mount_Hole_{hole_index}",
                splitter_hole_radius,
                plate_z0 - BOOLEAN_OVERLAP,
                plate_z1 + BOOLEAN_OVERLAP,
                x=x,
                y=y,
            )
        )
    boolean_difference(
        frame,
        cutters,
        "Single_Fan_Splitter_Frame_Openings",
        solver=FAN_CAGE_BOOLEAN_SOLVER,
        require_geometry_change=True,
    )

    leading_half_width = SINGLE_FAN_SPLITTER_LEADING_EDGE_WIDTH / 2.0
    downstream_half_width = (
        leading_half_width
        + SINGLE_FAN_SPLITTER_VANE_LENGTH_Z
        * math.tan(math.radians(SINGLE_FAN_SPLITTER_OUTLET_ANGLE_DEG))
    )
    vane_thickness = SINGLE_FAN_SPLITTER_VANE_THICKNESS
    left_vane_profile = [
        (center_x - leading_half_width, root_z),
        (center_x - downstream_half_width, downstream_z),
        (center_x - downstream_half_width + vane_thickness, downstream_z),
        (center_x, root_z),
    ]
    right_vane_profile = [
        (center_x, root_z),
        (center_x + downstream_half_width - vane_thickness, downstream_z),
        (center_x + downstream_half_width, downstream_z),
        (center_x + leading_half_width, root_z),
    ]
    opening_radius = opening_diameter / 2.0
    leading_edge = xz_polygon_prism(
        "Single_Fan_Splitter_Leading_Edge",
        [
            (center_x - leading_half_width, plate_z0),
            (center_x + leading_half_width, plate_z0),
            (center_x + leading_half_width, plate_z1),
            (center_x - leading_half_width, plate_z1),
        ],
        -opening_radius - BOOLEAN_OVERLAP,
        opening_radius + BOOLEAN_OVERLAP,
    )
    boolean_union(
        frame,
        leading_edge,
        "Single_Fan_Splitter_Leading_Edge_Union",
        solver=ASSEMBLY_BOOLEAN_SOLVER,
        require_geometry_change=True,
    )
    for side, profile in (
        ("Left", left_vane_profile),
        ("Right", right_vane_profile),
    ):
        vane = xz_polygon_prism(
            f"Single_Fan_{side}_Airflow_Splitter_Vane",
            profile,
            -opening_radius - BOOLEAN_OVERLAP,
            opening_radius + BOOLEAN_OVERLAP,
        )
        boolean_union(
            frame,
            vane,
            f"Single_Fan_{side}_Splitter_Vane_Union",
            solver=ASSEMBLY_BOOLEAN_SOLVER,
            require_geometry_change=True,
        )
    rotate_fan_part(frame, fan)
    holder_clearance_cutter = (
        create_single_fan_splitter_holder_clearance_cutter(
            fan,
            opening_radius,
            plate_z0,
            downstream_z,
        )
    )
    if holder_clearance_cutter is not None:
        boolean_difference(
            frame,
            [holder_clearance_cutter],
            "Single_Fan_Splitter_Dropped_Holder_Clearance",
            solver=ASSEMBLY_BOOLEAN_SOLVER,
            require_geometry_change=True,
        )
    frame.name = "Bolt_On_Single_Fan_Airflow_Splitter"
    frame.data.name = frame.name + "_Mesh"
    return frame


def support_bottom_y(fan_specs=None) -> float:
    fan_specs = fan_specs or resolve_fan_specs()
    largest_frame_size = max(fan["frame_size"] for fan in fan_specs)
    return -largest_frame_size / 2.0 - SUPPORT_HUB_BELOW_FAN_Y


def support_hub_top_y(fan_specs=None) -> float:
    return support_bottom_y(fan_specs) + SUPPORT_HUB_DEPTH_Y


def create_twisted_support_arm(name: str, fan, start_x: float, fan_specs):
    arm_center_z = support_arm_center_z()
    start = Vector(
        (
            start_x,
            support_hub_top_y(fan_specs) - SUPPORT_ARM_HUB_INSERT_Y,
            arm_center_z,
        )
    )
    end_z = arm_center_z if FAN_GRILL_ON_BACK else FAN_ROTATION_PIVOT_Z
    end_unrotated = (
        fan["center_x"] + fan_inward_sign(fan) * fan["pivot_inward_x"],
        -fan["frame_size"] / 2.0 + fan["support_arm_fan_insert_y"],
        end_z,
    )
    end = transform_fan_point(end_unrotated, fan)
    target_rotation = fan_rotation_quaternion(fan["rotation"])
    identity = Quaternion((1.0, 0.0, 0.0, 0.0))

    vertices = []
    for section in range(SUPPORT_ARM_SECTIONS + 1):
        t = section / SUPPORT_ARM_SECTIONS
        smooth_t = t * t * (3.0 - 2.0 * t)
        center = start.lerp(end, t)
        orientation = identity.slerp(target_rotation, smooth_t)
        x_axis = orientation @ Vector((1.0, 0.0, 0.0))
        z_axis = orientation @ Vector((0.0, 0.0, 1.0))
        width = fan["support_arm_center_width"] + (
            fan["support_arm_fan_width"] - fan["support_arm_center_width"]
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


def create_support(fan_specs):
    bottom_y = support_bottom_y(fan_specs)
    top_y = support_hub_top_y(fan_specs)
    hub_width = support_hub_width()
    center_x = fan_assembly_center_x()
    loop = [
        (center_x - hub_width / 2.0, bottom_y),
        (center_x + hub_width / 2.0, bottom_y),
        (center_x + hub_width / 2.0, top_y),
        (center_x - hub_width / 2.0, top_y),
    ]
    support_z0, support_z1 = support_z_bounds()
    hub = polygon_prism("Fan_Support_Hub", loop, support_z0, support_z1)
    center_index = (len(fan_specs) - 1) / 2.0
    for zero_based_index, fan in enumerate(fan_specs):
        start_x = (
            center_x
            + (zero_based_index - center_index) * SUPPORT_ARM_START_PITCH_X
        )
        arm = create_twisted_support_arm(
            f"Fan_{fan['index']}_Twisted_Support",
            fan,
            start_x,
            fan_specs,
        )
        boolean_union(hub, arm, f"Support_Arm_{fan['index']}_Union")
    hub.name = "Twisted_Fan_Support"
    hub.data.name = "Twisted_Fan_Support_Mesh"
    return hub


def stalk_center_y() -> float:
    return support_bottom_y() + STALK_DEPTH_Y / 2.0 - STALK_BOTTOM_Y_OVERHANG


def mount_stalk_center_y() -> float:
    if STALK_DROPPED_ROUTE_ENABLED:
        return (
            stalk_center_y()
            + STALK_ROUTE_DROP_Y
            - STALK_ROUTE_RETURN_RISE_Y
        )
    return stalk_center_y()


def routed_stalk_centerline():
    z0, z1 = stalk_z_bounds()
    low_y = stalk_center_y() - STALK_ROUTE_RETURN_RISE_Y
    return (
        (mount_stalk_center_y(), z0),
        (low_y, z0 + stalk_route_transition_z(STALK_ROUTE_DROP_Y)),
        (low_y, z1 - stalk_route_transition_z(STALK_ROUTE_RETURN_RISE_Y)),
        (stalk_center_y(), z1),
    )


def routed_stalk_path_distances(points):
    distances = [0.0]
    for (y0, z0), (y1, z1) in zip(points, points[1:]):
        distances.append(distances[-1] + math.hypot(y1 - y0, z1 - z0))
    return tuple(distances)


def effective_stalk_path_length() -> float:
    if not STALK_DROPPED_ROUTE_ENABLED:
        return STALK_LENGTH_Z
    return routed_stalk_path_distances(routed_stalk_centerline())[-1]


def stalk_lateral_width_scale() -> float:
    """Compensate global-X width so its centerline-normal projection is exact."""
    path_length = effective_stalk_path_length()
    return math.hypot(path_length, STALK_LATERAL_DEFLECTION_X) / path_length


def stalk_center_x_at_distance(distance: float, total_length: float) -> float:
    if total_length <= 0.0:
        return 0.0
    return fan_assembly_center_x() * distance / total_length


def stalk_lateral_angle_deg() -> float:
    """Return the signed sweep angle away from the un-deflected stalk route."""
    return math.degrees(
        math.atan2(STALK_LATERAL_DEFLECTION_X, effective_stalk_path_length())
    )


def routed_stalk_point_at_distance(points, distances, distance):
    for segment_index in range(len(points) - 1):
        segment_end = distances[segment_index + 1]
        if distance <= segment_end + 1.0e-9:
            segment_start = distances[segment_index]
            segment_length = segment_end - segment_start
            t = max(0.0, min(1.0, (distance - segment_start) / segment_length))
            y0, z0 = points[segment_index]
            y1, z1 = points[segment_index + 1]
            return (
                y0 + (y1 - y0) * t,
                z0 + (z1 - z0) * t,
                segment_index,
            )
    y, z = points[-1]
    return (y, z, len(points) - 2)


def routed_stalk_section_offset(points, distances, distance, segment_index):
    half_depth = STALK_DEPTH_Y / 2.0
    total_length = distances[-1]
    # Keep both ends parallel to the mount/support interfaces. The intermediate
    # sections follow the route normal so steep legs retain their full specified
    # thickness instead of becoming thin in the load-bearing direction.
    if math.isclose(distance, 0.0, abs_tol=1.0e-9) or math.isclose(
        distance, total_length, abs_tol=1.0e-9
    ):
        return (half_depth, 0.0)

    for corner_index, corner_distance in enumerate(distances[1:-1], start=1):
        if not math.isclose(distance, corner_distance, abs_tol=1.0e-9):
            continue
        before_y = points[corner_index][0] - points[corner_index - 1][0]
        before_z = points[corner_index][1] - points[corner_index - 1][1]
        after_y = points[corner_index + 1][0] - points[corner_index][0]
        after_z = points[corner_index + 1][1] - points[corner_index][1]
        before_length = math.hypot(before_y, before_z)
        after_length = math.hypot(after_y, after_z)
        before_normal = (before_z / before_length, -before_y / before_length)
        after_normal = (after_z / after_length, -after_y / after_length)
        miter_y = before_normal[0] + after_normal[0]
        miter_z = before_normal[1] + after_normal[1]
        miter_length = math.hypot(miter_y, miter_z)
        miter_y /= miter_length
        miter_z /= miter_length
        miter_projection = (
            miter_y * before_normal[0] + miter_z * before_normal[1]
        )
        miter_scale = half_depth / miter_projection
        return (miter_y * miter_scale, miter_z * miter_scale)

    y0, z0 = points[segment_index]
    y1, z1 = points[segment_index + 1]
    segment_length = math.hypot(y1 - y0, z1 - z0)
    return (
        half_depth * (z1 - z0) / segment_length,
        -half_depth * (y1 - y0) / segment_length,
    )


def routed_stalk_half_width(distance: float, total_length: float) -> float:
    width_scale = stalk_lateral_width_scale()
    half_stalk_width = STALK_WIDTH / 2.0
    if not stalk_end_flares_active():
        return half_stalk_width * width_scale

    if distance < STALK_MOUNT_FLARE_LENGTH_Z:
        t = distance / STALK_MOUNT_FLARE_LENGTH_Z
        mount_normal_half_width = MOUNT_BLOCK_WIDTH / (2.0 * width_scale)
        normal_half_width = mount_normal_half_width + (
            half_stalk_width - mount_normal_half_width
        ) * t
        return normal_half_width * width_scale
    if distance > total_length - STALK_HUB_FLARE_LENGTH_Z:
        t = (
            distance - (total_length - STALK_HUB_FLARE_LENGTH_Z)
        ) / STALK_HUB_FLARE_LENGTH_Z
        hub_normal_half_width = STALK_HUB_FLARE_WIDTH / (2.0 * width_scale)
        normal_half_width = half_stalk_width + (
            hub_normal_half_width - half_stalk_width
        ) * t
        return normal_half_width * width_scale
    return half_stalk_width * width_scale


def create_routed_stalk():
    points = routed_stalk_centerline()
    distances = routed_stalk_path_distances(points)
    total_length = distances[-1]
    section_distance_candidates = [0.0, *distances[1:-1], total_length]
    if stalk_end_flares_active():
        mount_flare_end = STALK_MOUNT_FLARE_LENGTH_Z
        hub_flare_start = total_length - STALK_HUB_FLARE_LENGTH_Z
        # A route-normal section very near a flush end would protrude through
        # that end's mounting plane. When a flare fits entirely inside a sloped
        # end leg, let it taper across the whole leg between the already-needed
        # endpoint/corner sections instead.
        if mount_flare_end >= distances[1]:
            section_distance_candidates.append(mount_flare_end)
        if hub_flare_start <= distances[-2]:
            section_distance_candidates.append(hub_flare_start)
    section_distances = []
    for distance in sorted(section_distance_candidates):
        if not section_distances or not math.isclose(
            distance, section_distances[-1], abs_tol=1.0e-9
        ):
            section_distances.append(distance)

    vertices = []
    for distance in section_distances:
        center_x = stalk_center_x_at_distance(distance, total_length)
        center_y, center_z, segment_index = routed_stalk_point_at_distance(
            points, distances, distance
        )
        offset_y, offset_z = routed_stalk_section_offset(
            points, distances, distance, segment_index
        )
        half_width = routed_stalk_half_width(distance, total_length)
        vertices.extend(
            (
                (center_x - half_width, center_y - offset_y, center_z - offset_z),
                (center_x + half_width, center_y - offset_y, center_z - offset_z),
                (center_x + half_width, center_y + offset_y, center_z + offset_z),
                (center_x - half_width, center_y + offset_y, center_z + offset_z),
            )
        )

    section_count = len(section_distances)
    faces = []
    for section in range(section_count - 1):
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
    last = (section_count - 1) * 4
    faces.append([last, last + 1, last + 2, last + 3])
    return create_mesh_object("Mount_Stalk_Dropped_Return", vertices, faces)


def create_stalk():
    if STALK_DROPPED_ROUTE_ENABLED:
        return create_routed_stalk()

    z0, z1 = stalk_z_bounds()
    length_z = z1 - z0

    def center_x(z: float) -> float:
        return fan_assembly_center_x() * (z - z0) / length_z

    if stalk_end_flares_active():
        mount_flare_z = z0 + STALK_MOUNT_FLARE_LENGTH_Z
        hub_flare_z = z1 - STALK_HUB_FLARE_LENGTH_Z
        half_mount_width = routed_stalk_half_width(0.0, length_z)
        half_stalk_width = routed_stalk_half_width(
            STALK_MOUNT_FLARE_LENGTH_Z,
            length_z,
        )
        half_hub_flare_width = routed_stalk_half_width(length_z, length_z)
        profile = [
            (-half_mount_width, z0),
            (half_mount_width, z0),
            (center_x(mount_flare_z) + half_stalk_width, mount_flare_z),
            (center_x(hub_flare_z) + half_stalk_width, hub_flare_z),
            (fan_assembly_center_x() + half_hub_flare_width, z1),
            (fan_assembly_center_x() - half_hub_flare_width, z1),
            (center_x(hub_flare_z) - half_stalk_width, hub_flare_z),
            (center_x(mount_flare_z) - half_stalk_width, mount_flare_z),
        ]
        center_y = stalk_center_y()
        return xz_polygon_prism(
            "Mount_Stalk_With_End_Flares",
            profile,
            center_y - STALK_DEPTH_Y / 2.0,
            center_y + STALK_DEPTH_Y / 2.0,
        )
    half_stalk_width = routed_stalk_half_width(0.0, length_z)
    return xz_polygon_prism(
        "Mount_Stalk",
        [
            (-half_stalk_width, z0),
            (half_stalk_width, z0),
            (fan_assembly_center_x() + half_stalk_width, z1),
            (fan_assembly_center_x() - half_stalk_width, z1),
        ],
        stalk_center_y() - STALK_DEPTH_Y / 2.0,
        stalk_center_y() + STALK_DEPTH_Y / 2.0,
    )


def mount_block_center_z() -> float:
    top_z = stalk_z_bounds()[0] + MOUNT_BLOCK_OVERLAP
    return top_z - MOUNT_BLOCK_HEIGHT_Z / 2.0


def create_mount_block():
    center_z = mount_block_center_z()
    center_y = mount_stalk_center_y()
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
    boolean_difference(
        block,
        through_cuts,
        "Mount_Through_Holes",
        solver=MOUNT_BLOCK_BOOLEAN_SOLVER,
        require_geometry_change=True,
    )

    if MOUNT_COUNTERSINK_ENABLED and MOUNT_COUNTERSINK_DEPTH > 0.0:
        outer_y = center_y + MOUNT_BLOCK_DEPTH_Y / 2.0 + BOOLEAN_OVERLAP
        inner_y = outer_y - MOUNT_COUNTERSINK_DEPTH - BOOLEAN_OVERLAP
        counterbores = []
        for hole_index, x in enumerate((-MOUNT_HOLE_SPACING / 2.0, MOUNT_HOLE_SPACING / 2.0), start=1):
            counterbores.append(
                add_cylinder_y(
                    f"Mount_Counterbore_{hole_index}",
                    MOUNT_COUNTERSINK_DIAMETER / 2.0,
                    inner_y,
                    outer_y,
                    x=x,
                    z=center_z,
                )
            )
        boolean_difference(
            block,
            counterbores,
            "Mount_Counterbores",
            solver=MOUNT_BLOCK_BOOLEAN_SOLVER,
            require_geometry_change=True,
        )

    return block


def gopro_prong_centers_x():
    pitch = GOPRO_PRONG_THICKNESS + GOPRO_PRONG_GAP
    center_index = (GOPRO_ADAPTER_PRONG_COUNT - 1) / 2.0
    return [
        (index - center_index) * pitch
        for index in range(GOPRO_ADAPTER_PRONG_COUNT)
    ]


def gopro_prong_profile(root_y: float, pivot_y: float, pivot_z: float):
    points = [(root_y, pivot_z + GOPRO_PRONG_RADIUS)]
    half_circle_segments = max(8, CYLINDER_SEGMENTS // 2)
    for segment in range(half_circle_segments + 1):
        angle = math.pi / 2.0 + math.pi * segment / half_circle_segments
        points.append(
            (
                pivot_y + GOPRO_PRONG_RADIUS * math.cos(angle),
                pivot_z + GOPRO_PRONG_RADIUS * math.sin(angle),
            )
        )
    points.append((root_y, pivot_z - GOPRO_PRONG_RADIUS))
    return points


def create_gopro_adapter():
    mount_hole_z = mount_block_center_z()
    mating_y = (
        mount_stalk_center_y()
        - MOUNT_BLOCK_DEPTH_Y / 2.0
        - GOPRO_ADAPTER_MATING_GAP
    )
    plate_front_y = mating_y - GOPRO_ADAPTER_PLATE_DEPTH_Y
    plate_center_z = mount_hole_z - GOPRO_ADAPTER_HOLE_Z_OFFSET
    plate_bottom_z = plate_center_z - GOPRO_ADAPTER_PLATE_HEIGHT_Z / 2.0
    pivot_y = mating_y - GOPRO_PIVOT_FROM_MATING_FACE_Y
    pivot_z = mount_hole_z - GOPRO_PIVOT_BELOW_MOUNT_HOLES_Z
    prong_bottom_z = pivot_z - GOPRO_PRONG_RADIUS

    adapter = add_box(
        "GoPro_Adapter_Mounting_Plate",
        (
            GOPRO_ADAPTER_PLATE_WIDTH,
            GOPRO_ADAPTER_PLATE_DEPTH_Y,
            GOPRO_ADAPTER_PLATE_HEIGHT_Z,
        ),
        (
            0.0,
            (plate_front_y + mating_y) / 2.0,
            plate_center_z,
        ),
    )

    # The narrower lower root is the right-angle reinforcement seen in the
    # source STL. It supports every finger without filling the finger gaps.
    root = add_box(
        "GoPro_Adapter_Lower_Root",
        (
            GOPRO_ADAPTER_ROOT_WIDTH,
            GOPRO_ADAPTER_PLATE_DEPTH_Y,
            plate_bottom_z - prong_bottom_z + BOOLEAN_OVERLAP,
        ),
        (
            0.0,
            (plate_front_y + mating_y) / 2.0,
            (prong_bottom_z + plate_bottom_z + BOOLEAN_OVERLAP) / 2.0,
        ),
    )
    boolean_union(adapter, root, "GoPro_Adapter_Root_Union")

    finger_profile = gopro_prong_profile(
        plate_front_y + BOOLEAN_OVERLAP,
        pivot_y,
        pivot_z,
    )
    prong_bounds = []
    for index, center_x in enumerate(gopro_prong_centers_x(), start=1):
        x0 = center_x - GOPRO_PRONG_THICKNESS / 2.0
        x1 = center_x + GOPRO_PRONG_THICKNESS / 2.0
        prong_bounds.append((x0, x1))
        prong = yz_polygon_prism(
            f"GoPro_Prong_{index}",
            finger_profile,
            x0,
            x1,
        )
        boolean_union(adapter, prong, f"GoPro_Prong_{index}_Union")

    left_prong_x = min(x0 for x0, _ in prong_bounds)
    right_prong_x = max(x1 for _, x1 in prong_bounds)
    nut_trap_enabled = (
        GOPRO_NUT_TRAP_ENABLED and GOPRO_ADAPTER_PRONG_COUNT == 3
    )
    pivot_cut_x0 = left_prong_x - BOOLEAN_OVERLAP
    if nut_trap_enabled:
        boss_outer_x = left_prong_x - GOPRO_NUT_BOSS_DEPTH
        boss = add_cylinder_x(
            "GoPro_M5_Nut_Boss",
            GOPRO_NUT_BOSS_DIAMETER / 2.0,
            boss_outer_x,
            left_prong_x + BOOLEAN_OVERLAP,
            y=pivot_y,
            z=pivot_z,
        )
        boolean_union(adapter, boss, "GoPro_M5_Nut_Boss_Union")

        hex_radius = GOPRO_NUT_ACROSS_FLATS / (2.0 * math.cos(math.pi / 6.0))
        hex_loop = [
            (
                pivot_y + hex_radius * math.cos(2.0 * math.pi * i / 6.0),
                pivot_z + hex_radius * math.sin(2.0 * math.pi * i / 6.0),
            )
            for i in range(6)
        ]
        hex_cut = yz_polygon_prism(
            "GoPro_M5_Hex_Nut_Trap",
            hex_loop,
            boss_outer_x - BOOLEAN_OVERLAP,
            left_prong_x + BOOLEAN_OVERLAP,
        )
        boolean_difference(adapter, [hex_cut], "GoPro_M5_Hex_Nut_Trap_Cut")
        pivot_cut_x0 = boss_outer_x - BOOLEAN_OVERLAP

    pivot_cut = add_cylinder_x(
        "GoPro_Pivot_Hole",
        GOPRO_PIVOT_HOLE_DIAMETER / 2.0,
        pivot_cut_x0,
        right_prong_x + BOOLEAN_OVERLAP,
        y=pivot_y,
        z=pivot_z,
    )
    boolean_difference(adapter, [pivot_cut], "GoPro_Pivot_Hole_Cut")

    # Cut the heat-insert sockets last so their measured stepped/tapered
    # profiles remain exact even where the mounting plate joins the root.
    insert_cuts = []
    insert_pocket_inner_y = mating_y - GOPRO_ADAPTER_INSERT_DEPTH
    insert_transition_inner_y = (
        insert_pocket_inner_y - GOPRO_ADAPTER_INSERT_TRANSITION_DEPTH
    )
    for index, x in enumerate(
        (-MOUNT_HOLE_SPACING / 2.0, MOUNT_HOLE_SPACING / 2.0),
        start=1,
    ):
        insert_cuts.append(
            radial_profile_y(
                f"GoPro_M3_Heat_Insert_Socket_{index}",
                (
                    (
                        mating_y + BOOLEAN_OVERLAP,
                        GOPRO_ADAPTER_INSERT_DIAMETER / 2.0,
                    ),
                    (
                        insert_pocket_inner_y,
                        GOPRO_ADAPTER_INSERT_DIAMETER / 2.0,
                    ),
                    (
                        insert_transition_inner_y,
                        GOPRO_ADAPTER_INSERT_PILOT_DIAMETER / 2.0,
                    ),
                    (
                        plate_front_y - BOOLEAN_OVERLAP,
                        GOPRO_ADAPTER_INSERT_PILOT_DIAMETER / 2.0,
                    ),
                ),
                x=x,
                z=mount_hole_z,
            )
        )
    boolean_difference(adapter, insert_cuts, "GoPro_M3_Heat_Insert_Sockets")

    adapter.name = f"Detachable_GoPro_Adapter_{GOPRO_ADAPTER_PRONG_COUNT}_Prong"
    adapter.data.name = adapter.name + "_Mesh"
    return adapter


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
    original_non_manifold = sum(
        1 for edge in bm.edges if len(edge.link_faces) != 2
    )
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

    removed_count = 0
    if remove:
        bmesh.ops.delete(bm, geom=list(remove), context="FACES")
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        repaired_non_manifold = sum(
            1 for edge in bm.edges if len(edge.link_faces) != 2
        )
        if repaired_non_manifold <= original_non_manifold:
            bm.to_mesh(obj.data)
            obj.data.update()
            removed_count = len(remove)
        else:
            print(
                "COINCIDENT_FACE_CLEANUP_SKIPPED "
                f"{obj.name}: non_manifold_edges="
                f"{original_non_manifold}->{repaired_non_manifold}"
            )
    bm.free()
    return removed_count


def triangulate_mesh(obj) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(
        bm,
        verts=list(bm.verts),
        dist=TRIANGULATION_WELD_DISTANCE,
    )
    bmesh.ops.triangulate(
        bm,
        faces=list(bm.faces),
        quad_method="BEAUTY",
        ngon_method="BEAUTY",
    )
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def export_stl(objects, output_path) -> Path:
    path = Path(output_path)
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


def default_holder_stl_path(fan_specs) -> str:
    count_label = {1: "single", 2: "dual", 3: "triple"}[len(fan_specs)]
    size_label = "-".join(f"{fan['size']:g}" for fan in fan_specs)
    return f"gopro_{count_label}_fan_{size_label}mm_parametric.stl"


def default_airflow_splitter_stl_path(fan) -> str:
    return f"gopro_single_fan_{fan['size']:g}mm_airflow_splitter.stl"


def world_z_bounds(obj):
    corners = (obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    z_values = [corner.z for corner in corners]
    return (min(z_values), max(z_values))


def validate_rear_grill_print_plane(parts, contact_parts, fan_specs) -> None:
    if not FAN_GRILL_ON_BACK:
        print("REAR_GRILL_PRINT_PLANE SKIP grill_position=front")
        return
    if any(
        abs(angle) > 1.0e-12
        for fan in fan_specs
        for angle in fan["rotation"]
    ):
        print("REAR_GRILL_PRINT_PLANE SKIP fan_rotations=nonzero")
        return

    bpy.context.view_layer.update()
    plane_z = attachment_plane_z()
    tolerance = 1.0e-5
    for part in parts:
        _, maximum_z = world_z_bounds(part)
        if maximum_z > plane_z + tolerance:
            raise RuntimeError(
                f"{part.name} extends {maximum_z - plane_z:.6f} mm "
                "past the rear print plane"
            )
    for label, part in contact_parts:
        _, maximum_z = world_z_bounds(part)
        if not math.isclose(maximum_z, plane_z, abs_tol=tolerance):
            raise RuntimeError(
                f"{label} ends at Z={maximum_z:.6f}, expected {plane_z:.6f}"
            )
    support_strategy = (
        "external_removable_supports_for_dropped_route"
        if STALK_DROPPED_ROUTE_ENABLED
        else "coplanar_base_and_45deg_receiver_flare"
    )
    print(
        "REAR_GRILL_PRINT_PLANE PASS "
        f"plane_z={plane_z:.2f}mm fan_rotations=zero "
        f"contacts={','.join(label for label, _ in contact_parts)} "
        "orientation=rear_face_down "
        f"support_strategy={support_strategy}"
    )


def build_dual_fan():
    # A direct MATERIAL_MODE assignment remains convenient for Blender's
    # console and --python-expr.  Reapply only after an actual mode change so
    # explicit scalar tuning performed after profile selection remains intact.
    if MATERIAL_MODE != _APPLIED_MATERIAL_MODE:
        apply_material_profile()
    validate_config()
    fan_specs = resolve_fan_specs()
    if CLEAR_SCENE:
        clear_scene()
    set_units()

    parts = []
    wire_slot_extent_parts = []
    print_plane_contacts = []
    if SUPPORT_ENABLED:
        support = create_support(fan_specs)
        parts.append(support)
        wire_slot_extent_parts.append(support)
        print_plane_contacts.append(("support", support))

    for fan in fan_specs:
        cage = create_fan_cage(fan)
        rotate_fan_part(cage, fan)
        parts.append(cage)
        wire_slot_extent_parts.append(cage)
        print_plane_contacts.append((f"fan_{fan['index']}_grille", cage))

    if STALK_ENABLED:
        stalk = create_stalk()
        parts.append(stalk)
        print_plane_contacts.append(("stalk_end", stalk))
    if MOUNT_BLOCK_ENABLED:
        parts.append(create_mount_block())
    gopro_adapter = create_gopro_adapter() if GOPRO_ADAPTER_ENABLED else None
    airflow_splitter = (
        create_single_fan_airflow_splitter(fan_specs[0])
        if SINGLE_FAN_AIRFLOW_SPLITTER_ENABLED
        else None
    )
    # The bottom wire-slot recut must follow the fan cages and shared support,
    # but a dropped stalk/receiver can extend much farther in fan-local Y. Do
    # not let that unrelated geometry lengthen the cutter through the holder.
    wire_slot_extent_vertices = tuple(
        part.matrix_world @ vertex.co
        for part in (
            wire_slot_extent_parts if STALK_DROPPED_ROUTE_ENABLED else parts
        )
        for vertex in part.data.vertices
    )

    validate_rear_grill_print_plane(parts, print_plane_contacts, fan_specs)

    if UNION_ALL_PARTS:
        final = parts[0]
        for part in parts[1:]:
            boolean_union(
                final,
                part,
                "Assembly_Union",
                solver=ASSEMBLY_BOOLEAN_SOLVER,
                require_geometry_change=True,
            )
        recut_assembled_fan_wire_slots(
            final, fan_specs, wire_slot_extent_vertices
        )
        count_label = {1: "Single", 2: "Dual", 3: "Triple"}[FAN_COUNT]
        final.name = f"Parametric_{count_label}_Fan_Holder"
        final.data.name = final.name + "_Mesh"
        holder_objects = [final]
    else:
        final = parts[0]
        holder_objects = parts
        for part in holder_objects:
            recut_assembled_fan_wire_slots(
                part, fan_specs, wire_slot_extent_vertices
            )
    final_objects = list(holder_objects)
    if gopro_adapter is not None:
        final_objects.append(gopro_adapter)
    if airflow_splitter is not None:
        final_objects.append(airflow_splitter)
    for part in final_objects:
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
        if count:
            raise RuntimeError(f"{obj.name} has {count} non-manifold edges")
        if shells != 1:
            raise RuntimeError(f"{obj.name} has {shells} disconnected shells")

    print(f"MATERIAL_MODE={MATERIAL_MODE}")
    print(f"FAN_GRILL_POSITION={'BACK' if FAN_GRILL_ON_BACK else 'FRONT'}")
    print(f"STALK_END_FLARES_ACTIVE={stalk_end_flares_active()}")
    if STALK_DROPPED_ROUTE_ENABLED:
        print(
            "STALK_ROUTE=DROPPED_RETURN "
            f"drop={STALK_ROUTE_DROP_Y:.2f}mm "
            f"straight_back={STALK_ROUTE_BACK_Z:.2f}mm "
            f"return_rise={STALK_ROUTE_RETURN_RISE_Y:.2f}mm "
            f"transition_angle={STALK_ROUTE_TRANSITION_ANGLE_DEG:.2f}deg "
            f"fan_center_lowering={STALK_ROUTE_DROP_Y - STALK_ROUTE_RETURN_RISE_Y:.2f}mm "
            "external_supports=recommended"
        )
    else:
        print("STALK_ROUTE=STRAIGHT")
    print(
        "STALK_LATERAL_DEFLECTION "
        f"offset_x={STALK_LATERAL_DEFLECTION_X:.2f}mm "
        f"angle={stalk_lateral_angle_deg():.2f}deg "
        "mount_center_x=0.00mm "
        f"fan_center_x={fan_assembly_center_x():.2f}mm "
        f"normal_width={STALK_WIDTH:.2f}mm "
        f"global_x_width={STALK_WIDTH * stalk_lateral_width_scale():.2f}mm"
    )
    print(f"FAN_COUNT={FAN_COUNT}")
    if airflow_splitter is not None:
        clearance_notch = (
            "enabled"
            if FAN_GRILL_ON_BACK and STALK_DROPPED_ROUTE_ENABLED
            else "disabled"
        )
        print(
            "SINGLE_FAN_AIRFLOW_SPLITTER=ENABLED "
            f"outlet_angle_per_side={SINGLE_FAN_SPLITTER_OUTLET_ANGLE_DEG:.2f}deg "
            f"vane_length={SINGLE_FAN_SPLITTER_VANE_LENGTH_Z:.2f}mm "
            f"opening={single_fan_splitter_opening_diameter(fan_specs[0]):.2f}mm "
            f"mount_face_z={single_fan_splitter_mount_face_z(fan_specs[0]):.2f}mm "
            f"holder_clearance_notch={clearance_notch} "
            "mount=standard_four_hole airflow=toward_cameras material=RIGID "
            "print_orientation=mount_face_down"
        )
    else:
        print("SINGLE_FAN_AIRFLOW_SPLITTER=DISABLED")
    for fan in fan_specs:
        print(
            f"FAN_{fan['index']} reference={fan['reference']} "
            f"body={fan['size']:.1f}x{fan['size']:.1f}x{fan['depth']:.1f}mm "
            f"cavity={fan['cavity_size']:.2f}mm "
            f"frame={fan['frame_size']:.2f}mm "
            f"center_x={fan['center_x']:.2f}mm"
        )
    if MATERIAL_MODE == "TPU":
        print(
            "TPU_SLICER_GUIDANCE "
            f"infill={TPU_RECOMMENDED_INFILL_PERCENT[0]}-"
            f"{TPU_RECOMMENDED_INFILL_PERCENT[1]}% "
            f"pattern={TPU_RECOMMENDED_INFILL_PATTERN} "
            f"walls={TPU_RECOMMENDED_WALLS[0]}-"
            f"{TPU_RECOMMENDED_WALLS[1]}"
        )
        print("Detachable_GoPro_Adapter material=RIGID")
        print(
            "TPU_MOUNT_HARDWARE "
            f"M3_screw_extra_length={TPU_MOUNT_SCREW_EXTRA_LENGTH_MM:.1f}mm"
        )

    if EXPORT_STL:
        holder_output_path = (
            EXPORT_STL_PATH
            if EXPORT_STL_PATH is not None
            else default_holder_stl_path(fan_specs)
        )
        holder_path = export_stl(holder_objects, holder_output_path)
        print(f"Wrote holder {holder_path}")
        if gopro_adapter is not None:
            adapter_path = export_stl([gopro_adapter], EXPORT_ADAPTER_STL_PATH)
            print(f"Wrote rigid adapter {adapter_path}")
        if airflow_splitter is not None:
            splitter_output_path = (
                EXPORT_AIRFLOW_SPLITTER_STL_PATH
                if EXPORT_AIRFLOW_SPLITTER_STL_PATH is not None
                else default_airflow_splitter_stl_path(fan_specs[0])
            )
            splitter_path = export_stl(
                [airflow_splitter],
                splitter_output_path,
            )
            print(f"Wrote airflow splitter {splitter_path}")

    select_only(final)
    return final


if __name__ == "__main__":
    build_dual_fan()
