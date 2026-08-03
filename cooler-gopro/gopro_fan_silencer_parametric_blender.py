"""Parametric curved-baffle silencer for standard square fans.

Run inside Blender:

    blender --background --python gopro_fan_silencer_parametric_blender.py

Or select a supported size through Make:

    make FAN_SILENCER_SIZE=80 fan-silencer

``FAN_SIZE_MM`` selects a shared 40, 60, 80, or 120 mm fan preset.  The default
40 mm build bolts between ``gopro_fan_case_parametric_blender.py`` and its fan,
using the case's 32 mm square M3 pattern and 37 mm airflow opening on both
faces.  Larger presets build as standalone standard fan-to-fan interfaces.

The acoustic geometry follows the concentric curved-baffle approach of
"Intake Fan Silencer PSU" by grizzie17 (CC BY 4.0):
https://www.thingiverse.com/thing:5177333/comments

The fan-case generator is used only to cross-check the shared fan mounting
dimensions.  None of its internal baffle geometry is reused as a design model.

A fan-facing annular shield covers the blade-sweep region.  Concentric inner
and outer skirts form the first curved acoustic cup.  A second, spaced center
shield catches oblique sound that could otherwise escape through the first
shield's hub opening; its curved rim faces the fan to form another open cup.
Air follows parallel inner and outer turns around the overlapping shields.
Radial arms and bolt pads echo the reference's spoke layout.

The assembly has five unique support-free parts:

* print two flanges with a broad face on the bed;
* print three expansion spacers with an axial face on the bed;
* print one annular curved-baffle insert with its plate on the bed;
* print one center curved-baffle insert with its disk on the bed; and
* print one common alignment sleeve upright on its case-facing end.

The sleeve is a straight square tube with a support-free 45-degree transition
to a short fan-frame pocket.  It registers every sandwich layer to one common
datum instead of accumulating clearance at the bolt holes, and the pocket
registers the fan to the same datum.  All air and acoustic surfaces remain
exposed before assembly.  Four long through-bolts clamp the seven-part
sandwich inside the sleeve; no internal supports or adhesive are required.
The external silencer is an alternative to the removable acoustic cartridge
enabled by ``BAFFLE_CARTRIDGE_ENABLED`` in the case generator.  Do not install
both restrictions in series unless measured airflow or the fan's pressure/flow
curve has verified that configuration.

All dimensions are millimeters.

Axes in assembled coordinates:
    X - fan width
    Y - airflow and bolt direction, from the fan toward the case
    Z - fan height
"""

from __future__ import annotations

import ast
import itertools
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

try:
    from fan_size_presets import get_standard_fan_preset
except ModuleNotFoundError as error:
    if error.name != "fan_size_presets":
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from fan_size_presets import get_standard_fan_preset


# ---------------------------------------------------------------------------
# CONFIG

CLEAR_SCENE = True
LAYOUT_MODE = "assembled"  # "assembled" or "print_bed"

# Shared preset selector.  AUTO uses the GoPro case's verified 37 mm/M3 rear
# interface for the default 40 mm size and standard preset dimensions for all
# larger sizes.  OFF uses the standard 40 mm preset too; REQUIRED rejects any
# size other than 40 mm.
FAN_SIZE_MM = 40
CASE_INTERFACE_MODE = "AUTO"  # "AUTO", "REQUIRED", or "OFF"
FAN_OPENING_DIAMETER_OVERRIDE = None
FAN_HUB_DIAMETER_OVERRIDE = None
FAN_HOLE_SPACING_OVERRIDE = None
FAN_BOLT_HOLE_DIAMETER_OVERRIDE = None
FAN_BLADE_SWEEP_DIAMETER_OVERRIDE = None
THROUGH_BOLT_DIAMETER_OVERRIDE = None

EXPORT_STL = False
EXPORT_DIRECTORY = ""
EXPORT_COMBINED_STL = True
EXPORT_SEPARATE_STLS = True
COMBINED_STL_NAME = "gopro_40mm_fan_silencer.stl"
FLANGE_STL_NAME = "gopro_40mm_fan_silencer_flange.stl"
SPACER_STL_NAME = "gopro_40mm_fan_silencer_spacer.stl"
CURVED_BAFFLE_STL_NAME = "gopro_40mm_fan_silencer_curved_baffle.stl"
CENTER_BAFFLE_STL_NAME = "gopro_40mm_fan_silencer_center_baffle.stl"
ALIGNMENT_SLEEVE_STL_NAME = "gopro_40mm_fan_silencer_alignment_sleeve.stl"

# Default resolved values are reapplied from ``FAN_SIZE_MM`` at every build so
# Blender-console and Make overrides work without reloading the module.
FAN_NOMINAL_SIZE = 40.0
FAN_PRESET_DEPTH = 20.0
FAN_REFERENCE = "Noctua NF-A4x20"
FAN_OPENING_DIAMETER = 37.0
FAN_HOLE_SPACING = 32.0
FAN_BOLT_HOLE_DIAMETER = 3.6
FAN_HUB_DIAMETER = 20.0
FAN_BLADE_SWEEP_DIAMETER = 36.0
THROUGH_BOLT_DIAMETER = 3.0
CASE_INTERFACE_ACTIVE = True
FAN_SCALE = 1.0

# Frame and airway proportions.  Axial labyrinth dimensions scale with the fan
# so radial-turn area does not collapse relative to opening area on larger
# presets; printable wall/plate thicknesses remain nozzle-friendly constants.
MINIMUM_FRAME_OVERHANG_PER_SIDE = 1.7
FRAME_OVERHANG_FRACTION = 0.025
RESOLVED_FRAME_OVERHANG_PER_SIDE = 1.7
OUTER_SIZE = 43.4
FLANGE_THICKNESS = 2.0
SPACER_DEPTH_AT_40MM = 7.0
SPACER_DEPTH = 7.0
SPACER_OUTER_WALL = 1.20
CORNER_BOSS_RADIAL_WALL = 1.1
CORNER_BOSS_SIZE = 5.8
CORNER_BOSS_WEB_WIDTH = 1.2
CORNER_BOSS_WEB_OVERLAP = 0.1
MINIMUM_CASE_PAD_MARGIN = 0.75

# Curved acoustic labyrinth.  The annular plate covers the declared blade
# sweep from the fan hub to the resolved opening edge.  Both skirts remain
# entirely on the plate footprint, so their union does not silently reduce the
# measured throat.  A second center disk overlaps the first plate's hub opening
# in projection and blocks oblique blade-to-case rays.
BAFFLE_PLATE_THICKNESS = 1.4
SHIELD_INNER_RADIUS = FAN_HUB_DIAMETER / 2.0
SHIELD_OUTER_RADIUS = FAN_OPENING_DIAMETER / 2.0 + 0.22
CENTER_BLOCKER_RADIUS = 14.75
MINIMUM_ACOUSTIC_OVERLAP = 0.20
CURVED_SKIRT_THICKNESS = 1.2
CURVED_SKIRT_HEIGHT_AT_40MM = 2.0
CURVED_SKIRT_HEIGHT = 2.0
OUTER_SKIRT_CORNER_GAP_DEG = 10.0
RADIAL_ARM_WIDTH = 1.2
RADIAL_ARM_INNER_RADIUS = 17.5
RADIAL_ARM_OUTER_RADIUS = 19.9
RADIAL_ARM_PAD_OVERLAP = 1.4
RADIAL_ARM_ANGLES_DEG = (45.0, 135.0, 225.0, 315.0)
FAN_SIDE_MARK_HEIGHT = 0.4
# Sublayer relief keeps the locating ears clear of adjacent spacer faces while
# their bolt pads carry clamp load.  At 0.05 mm it is absorbed by a normal
# first layer when the inserts print plate-down and does not require supports.
LOCATOR_TAB_AXIAL_CLEARANCE = 0.05

# One removable square sleeve locates every layer from its outside edges, so
# tolerances do not accumulate through six serial interfaces.  The short fan
# pocket references the fan frame to that same datum.  Allowances below are
# conservative radial/vector budgets used by both analytic and shifted-ray
# validation; PRINT_DATUM_RELATIVE_ALLOWANCE is total relative error, not a
# per-part value.
STACK_SLEEVE_CLEARANCE_PER_SIDE = 0.10
FAN_FRAME_POCKET_CLEARANCE_PER_SIDE = 0.20
FAN_FRAME_SIZE_TOLERANCE = 0.10
PRINT_DATUM_RELATIVE_ALLOWANCE = 0.10
SLEEVE_WALL_THICKNESS = 0.60
FAN_FRAME_POCKET_DEPTH = 0.80
STANDARD_CHAMBER_ALIGNMENT_ALLOWANCE = 0.60
# Total relative allowance for printed bore-size error at the case/flange pair.
INTERFACE_PRINT_HOLE_ALLOWANCE = 0.15
MINIMUM_INTERFACE_AIRWAY_OVERLAP_RATIO = 0.95

# Airway validation conservatively treats installed through-bolts as solid and
# samples the final curved-baffle projection, including the spacer towers,
# their wall webs, and the radial arms.
AIRWAY_SAMPLE_COUNT_PER_AXIS = 505
MINIMUM_AIRWAY_TO_FAN_AREA_RATIO = 0.65

# The source defaults below are cross-checked without executing the much larger
# case generator, preventing its fan interface from silently drifting away.
CASE_GENERATOR_NAME = "gopro_fan_case_parametric_blender.py"
CASE_INTERFACE_CONFIG_NAMES = (
    "FAN_OPENING_DIAMETER",
    "FAN_HOLE_SPACING_X",
    "FAN_HOLE_SPACING_Z",
    "FAN_HOLE_DIAMETER",
    "BACK_DOME_FAN_PAD_WIDTH",
    "BACK_DOME_FAN_PAD_HEIGHT",
    "BAFFLE_CARTRIDGE_ENABLED",
)

# Boolean, mesh, and print-bed quality.
CYLINDER_SEGMENTS = 128
BOOLEAN_SOLVER = "EXACT"
BOOLEAN_CLEANUP_DISTANCE = 0.0001
BOOLEAN_MINIMUM_VOLUME_CHANGE = 1.0e-6
PRINT_PART_GAP = 4.0


# ---------------------------------------------------------------------------
# Derived dimensions and validation


def chamber_half_size() -> float:
    return OUTER_SIZE / 2.0 - SPACER_OUTER_WALL


def sleeve_inner_size() -> float:
    return OUTER_SIZE + 2.0 * STACK_SLEEVE_CLEARANCE_PER_SIDE


def sleeve_outer_size() -> float:
    return sleeve_inner_size() + 2.0 * SLEEVE_WALL_THICKNESS


def fan_frame_pocket_size() -> float:
    return FAN_NOMINAL_SIZE + 2.0 * FAN_FRAME_POCKET_CLEARANCE_PER_SIDE


def fan_frame_transition_depth() -> float:
    """45-degree maximum overhang while the upright sleeve narrows inward."""
    return (sleeve_inner_size() - fan_frame_pocket_size()) / 2.0


def stack_max_relative_offset() -> float:
    """Worst radial offset between any two sleeve-located printed layers."""
    clearance_offset = math.sqrt(2.0) * 2.0 * STACK_SLEEVE_CLEARANCE_PER_SIDE
    return clearance_offset + PRINT_DATUM_RELATIVE_ALLOWANCE


def fan_to_stack_max_offset() -> float:
    """Worst radial fan-center offset from any sleeve-located layer."""
    per_axis = (
        FAN_FRAME_POCKET_CLEARANCE_PER_SIDE
        + STACK_SLEEVE_CLEARANCE_PER_SIDE
        + FAN_FRAME_SIZE_TOLERANCE / 2.0
    )
    return math.sqrt(2.0) * per_axis + PRINT_DATUM_RELATIVE_ALLOWANCE


def total_assembly_depth() -> float:
    return 2.0 * FLANGE_THICKNESS + 3.0 * SPACER_DEPTH + 2.0 * BAFFLE_PLATE_THICKNESS


def annular_baffle_center_y() -> float:
    return -(SPACER_DEPTH + BAFFLE_PLATE_THICKNESS) / 2.0


def center_baffle_center_y() -> float:
    return -annular_baffle_center_y()


def fan_face_y() -> float:
    return -total_assembly_depth() / 2.0


def case_face_y() -> float:
    return total_assembly_depth() / 2.0


def case_flange_near_face_y() -> float:
    return case_face_y() - FLANGE_THICKNESS


def annular_ray_interpolation() -> float:
    return (annular_baffle_center_y() - fan_face_y()) / (
        case_flange_near_face_y() - fan_face_y()
    )


def required_outer_shield_radius() -> float:
    """Outer radius needed for shifted fan-to-case rays at the first plate."""
    interpolation = annular_ray_interpolation()
    nominal_ray_radius = (
        1.0 - interpolation
    ) * FAN_BLADE_SWEEP_DIAMETER / 2.0 + interpolation * FAN_OPENING_DIAMETER / 2.0
    position_uncertainty = (
        1.0 - interpolation
    ) * fan_to_stack_max_offset() + interpolation * stack_max_relative_offset()
    return nominal_ray_radius + position_uncertainty


def fan_opening_area() -> float:
    return math.pi * (FAN_OPENING_DIAMETER / 2.0) ** 2


def object_prefix() -> str:
    return f"GoPro_{int(FAN_NOMINAL_SIZE)}mm_Fan_Silencer"


def outer_skirt_covered_fraction() -> float:
    total_gap = len(RADIAL_ARM_ANGLES_DEG) * 2.0 * OUTER_SKIRT_CORNER_GAP_DEG
    return (360.0 - total_gap) / 360.0


def corner_obstruction_rectangles():
    """Return spacer bolt-tower/web projections in the XZ plane."""
    hole_center = FAN_HOLE_SPACING / 2.0
    boss_half = CORNER_BOSS_SIZE / 2.0
    web_half = CORNER_BOSS_WEB_WIDTH / 2.0
    chamber_half = chamber_half_size()
    rectangles = []
    for x_sign in (-1.0, 1.0):
        for z_sign in (-1.0, 1.0):
            x = x_sign * hole_center
            z = z_sign * hole_center
            rectangles.append(
                (x - boss_half, x + boss_half, z - boss_half, z + boss_half)
            )
            if x_sign > 0.0:
                x_web = (
                    x + boss_half - CORNER_BOSS_WEB_OVERLAP,
                    chamber_half,
                )
            else:
                x_web = (
                    -chamber_half,
                    x - boss_half + CORNER_BOSS_WEB_OVERLAP,
                )
            rectangles.append((x_web[0], x_web[1], z - web_half, z + web_half))
            if z_sign > 0.0:
                z_web = (
                    z + boss_half - CORNER_BOSS_WEB_OVERLAP,
                    chamber_half,
                )
            else:
                z_web = (
                    -chamber_half,
                    z - boss_half + CORNER_BOSS_WEB_OVERLAP,
                )
            rectangles.append((x - web_half, x + web_half, z_web[0], z_web[1]))
    return tuple(rectangles)


def point_in_radial_arm(
    x: float,
    z: float,
    angle_deg: float,
    inner_radius: float = RADIAL_ARM_INNER_RADIUS,
    margin: float = 0.0,
) -> bool:
    angle = math.radians(angle_deg)
    radial = x * math.cos(angle) + z * math.sin(angle)
    tangent = -x * math.sin(angle) + z * math.cos(angle)
    return (
        inner_radius - margin <= radial <= RADIAL_ARM_OUTER_RADIUS + margin
        and abs(tangent) <= RADIAL_ARM_WIDTH / 2.0 + margin
    )


def point_in_corner_obstruction(x: float, z: float, margin: float = 0.0) -> bool:
    return any(
        x0 - margin <= x <= x1 + margin and z0 - margin <= z <= z1 + margin
        for x0, x1, z0, z1 in corner_obstruction_rectangles()
    )


def annular_baffle_projection_is_solid(x: float, z: float, margin: float = 0.0) -> bool:
    """Installed solid union at the annular baffle's narrowest plane."""
    radius = math.hypot(x, z)
    if SHIELD_INNER_RADIUS - margin <= radius <= SHIELD_OUTER_RADIUS + margin:
        return True
    if point_in_corner_obstruction(x, z, margin):
        return True
    return any(
        point_in_radial_arm(x, z, angle, margin=margin)
        for angle in RADIAL_ARM_ANGLES_DEG
    )


def center_baffle_projection_is_solid(x: float, z: float, margin: float = 0.0) -> bool:
    """Installed solid union at the center blocker's narrowest plane."""
    if math.hypot(x, z) <= CENTER_BLOCKER_RADIUS + margin:
        return True
    if point_in_corner_obstruction(x, z, margin):
        return True
    arm_inner_radius = CENTER_BLOCKER_RADIUS - 0.2
    return any(
        point_in_radial_arm(x, z, angle, arm_inner_radius, margin)
        for angle in RADIAL_ARM_ANGLES_DEG
    )


def sampled_open_area(solid_test) -> float:
    """Lower-bound one installed XZ throat with whole-cell solid margins."""
    half = chamber_half_size()
    count = AIRWAY_SAMPLE_COUNT_PER_AXIS
    pitch = 2.0 * half / count
    cell_margin = pitch / math.sqrt(2.0)
    open_cells = 0
    for x_index in range(count):
        x = -half + (x_index + 0.5) * pitch
        for z_index in range(count):
            z = -half + (z_index + 0.5) * pitch
            if not solid_test(x, z, cell_margin):
                open_cells += 1
    return open_cells * pitch**2


def sampled_annular_outer_open_area() -> float:
    """Return the connected outer route through the annular baffle plane."""
    half = chamber_half_size()
    count = AIRWAY_SAMPLE_COUNT_PER_AXIS
    pitch = 2.0 * half / count
    cell_margin = pitch / math.sqrt(2.0)
    open_cells = 0
    for x_index in range(count):
        x = -half + (x_index + 0.5) * pitch
        for z_index in range(count):
            z = -half + (z_index + 0.5) * pitch
            if (
                math.hypot(x, z) - cell_margin > SHIELD_OUTER_RADIUS
                and not annular_baffle_projection_is_solid(x, z, cell_margin)
            ):
                open_cells += 1
    return open_cells * pitch**2


def annular_baffle_open_area() -> float:
    return sampled_open_area(annular_baffle_projection_is_solid)


def center_baffle_open_area() -> float:
    return sampled_open_area(center_baffle_projection_is_solid)


def first_curved_turn_area() -> float:
    """Parallel radial routes around the two fan-facing annular skirts."""
    axial_gap = SPACER_DEPTH - CURVED_SKIRT_HEIGHT
    inner_turn = 2.0 * math.pi * SHIELD_INNER_RADIUS * axial_gap
    outer_skirt_inner_radius = SHIELD_OUTER_RADIUS - CURVED_SKIRT_THICKNESS
    outer_turn = (
        2.0
        * math.pi
        * outer_skirt_inner_radius
        * outer_skirt_covered_fraction()
        * axial_gap
    )
    return inner_turn + outer_turn


def second_curved_turn_area() -> float:
    """Center route around the second cup, plus the parallel outer route."""
    axial_gap = SPACER_DEPTH - CURVED_SKIRT_HEIGHT
    rim_inner_radius = CENTER_BLOCKER_RADIUS - CURVED_SKIRT_THICKNESS
    center_turn = 2.0 * math.pi * rim_inner_radius * axial_gap
    return center_turn + sampled_annular_outer_open_area()


def minimum_airway_area() -> float:
    return min(
        annular_baffle_open_area(),
        center_baffle_open_area(),
        first_curved_turn_area(),
        second_curved_turn_area(),
    )


def required_center_blocker_radius() -> float:
    """Radius needed to catch shifted first-hole-to-case ray segments."""
    interpolation = (center_baffle_center_y() - annular_baffle_center_y()) / (
        case_flange_near_face_y() - annular_baffle_center_y()
    )
    nominal_ray_radius = (
        1.0 - interpolation
    ) * SHIELD_INNER_RADIUS + interpolation * FAN_OPENING_DIAMETER / 2.0
    position_uncertainty = (
        interpolation * stack_max_relative_offset() + stack_max_relative_offset()
    )
    return nominal_ray_radius + position_uncertainty


def polygon_apothem(radius: float) -> float:
    return radius * math.cos(math.pi / CYLINDER_SEGMENTS)


def round_up(value: float, quantum: float) -> float:
    return math.ceil((value - 1.0e-12) / quantum) * quantum


def apply_fan_size_config() -> None:
    """Resolve every size-dependent dimension from the selected shared preset."""
    global COMBINED_STL_NAME
    global FLANGE_STL_NAME
    global SPACER_STL_NAME
    global CURVED_BAFFLE_STL_NAME
    global CENTER_BAFFLE_STL_NAME
    global ALIGNMENT_SLEEVE_STL_NAME
    global FAN_NOMINAL_SIZE
    global FAN_PRESET_DEPTH
    global FAN_REFERENCE
    global FAN_OPENING_DIAMETER
    global FAN_HOLE_SPACING
    global FAN_BOLT_HOLE_DIAMETER
    global FAN_HUB_DIAMETER
    global FAN_BLADE_SWEEP_DIAMETER
    global THROUGH_BOLT_DIAMETER
    global CASE_INTERFACE_ACTIVE
    global FAN_SCALE
    global OUTER_SIZE
    global RESOLVED_FRAME_OVERHANG_PER_SIDE
    global SPACER_DEPTH
    global CORNER_BOSS_SIZE
    global SHIELD_INNER_RADIUS
    global SHIELD_OUTER_RADIUS
    global CENTER_BLOCKER_RADIUS
    global CURVED_SKIRT_HEIGHT
    global RADIAL_ARM_INNER_RADIUS
    global RADIAL_ARM_OUTER_RADIUS

    preset = get_standard_fan_preset(FAN_SIZE_MM)
    mode = str(CASE_INTERFACE_MODE).upper()
    if mode not in {"AUTO", "REQUIRED", "OFF"}:
        raise ValueError("CASE_INTERFACE_MODE must be 'AUTO', 'REQUIRED', or 'OFF'")
    if mode == "REQUIRED" and FAN_SIZE_MM != 40:
        raise ValueError("The GoPro case interface supports only FAN_SIZE_MM=40")
    CASE_INTERFACE_ACTIVE = mode == "REQUIRED" or (mode == "AUTO" and FAN_SIZE_MM == 40)

    FAN_NOMINAL_SIZE = float(preset["frame"])
    FAN_PRESET_DEPTH = float(preset["depth"])
    FAN_REFERENCE = str(preset["reference"])
    FAN_SCALE = FAN_NOMINAL_SIZE / 40.0
    opening_default = 37.0 if CASE_INTERFACE_ACTIVE else preset["opening"]
    bolt_hole_default = 3.6 if CASE_INTERFACE_ACTIVE else preset["hole_diameter"]
    FAN_OPENING_DIAMETER = float(
        FAN_OPENING_DIAMETER_OVERRIDE
        if FAN_OPENING_DIAMETER_OVERRIDE is not None
        else opening_default
    )
    FAN_HUB_DIAMETER = float(
        FAN_HUB_DIAMETER_OVERRIDE
        if FAN_HUB_DIAMETER_OVERRIDE is not None
        else preset["hub"]
    )
    FAN_HOLE_SPACING = float(
        FAN_HOLE_SPACING_OVERRIDE
        if FAN_HOLE_SPACING_OVERRIDE is not None
        else preset["hole_spacing"]
    )
    FAN_BOLT_HOLE_DIAMETER = float(
        FAN_BOLT_HOLE_DIAMETER_OVERRIDE
        if FAN_BOLT_HOLE_DIAMETER_OVERRIDE is not None
        else bolt_hole_default
    )
    FAN_BLADE_SWEEP_DIAMETER = float(
        FAN_BLADE_SWEEP_DIAMETER_OVERRIDE
        if FAN_BLADE_SWEEP_DIAMETER_OVERRIDE is not None
        else preset["opening"]
    )
    THROUGH_BOLT_DIAMETER = float(
        THROUGH_BOLT_DIAMETER_OVERRIDE
        if THROUGH_BOLT_DIAMETER_OVERRIDE is not None
        else (3.0 if CASE_INTERFACE_ACTIVE else 4.0)
    )

    RESOLVED_FRAME_OVERHANG_PER_SIDE = max(
        MINIMUM_FRAME_OVERHANG_PER_SIDE,
        FAN_NOMINAL_SIZE * FRAME_OVERHANG_FRACTION,
    )
    if not CASE_INTERFACE_ACTIVE:
        RESOLVED_FRAME_OVERHANG_PER_SIDE += STANDARD_CHAMBER_ALIGNMENT_ALLOWANCE
    OUTER_SIZE = FAN_NOMINAL_SIZE + 2.0 * RESOLVED_FRAME_OVERHANG_PER_SIDE
    SPACER_DEPTH = SPACER_DEPTH_AT_40MM * FAN_SCALE
    CURVED_SKIRT_HEIGHT = CURVED_SKIRT_HEIGHT_AT_40MM * FAN_SCALE
    CORNER_BOSS_SIZE = FAN_BOLT_HOLE_DIAMETER + 2.0 * CORNER_BOSS_RADIAL_WALL
    SHIELD_INNER_RADIUS = FAN_HUB_DIAMETER / 2.0
    apothem_factor = math.cos(math.pi / CYLINDER_SEGMENTS)
    SHIELD_OUTER_RADIUS = round_up(
        (required_outer_shield_radius() + MINIMUM_ACOUSTIC_OVERLAP + 0.01)
        / apothem_factor,
        0.01,
    )
    CENTER_BLOCKER_RADIUS = round_up(
        (required_center_blocker_radius() + MINIMUM_ACOUSTIC_OVERLAP + 0.01)
        / apothem_factor,
        0.05,
    )
    RADIAL_ARM_INNER_RADIUS = SHIELD_OUTER_RADIUS - CURVED_SKIRT_THICKNESS
    hole_center_radius = math.sqrt(2.0) * FAN_HOLE_SPACING / 2.0
    pad_inner_radius = hole_center_radius - math.sqrt(2.0) * CORNER_BOSS_SIZE / 2.0
    RADIAL_ARM_OUTER_RADIUS = pad_inner_radius + RADIAL_ARM_PAD_OVERLAP

    size_label = f"{int(FAN_NOMINAL_SIZE)}mm"
    prefix = f"gopro_{size_label}_fan_silencer"
    COMBINED_STL_NAME = prefix + ".stl"
    FLANGE_STL_NAME = prefix + "_flange.stl"
    SPACER_STL_NAME = prefix + "_spacer.stl"
    CURVED_BAFFLE_STL_NAME = prefix + "_curved_baffle.stl"
    CENTER_BAFFLE_STL_NAME = prefix + "_center_baffle.stl"
    ALIGNMENT_SLEEVE_STL_NAME = prefix + "_alignment_sleeve.stl"


def segment_radial_range_at_y_interval(
    source,
    target,
    y0: float,
    y1: float,
    center_x: float = 0.0,
    center_z: float = 0.0,
):
    """Return ray radii inside an interval relative to a blocker center."""
    source_x, source_y, source_z = source
    target_x, target_y, target_z = target

    def point_at(y):
        amount = (y - source_y) / (target_y - source_y)
        return (
            source_x + amount * (target_x - source_x) - center_x,
            source_z + amount * (target_z - source_z) - center_z,
        )

    x0, z0 = point_at(y0)
    x1, z1 = point_at(y1)
    dx = x1 - x0
    dz = z1 - z0
    length_squared = dx * dx + dz * dz
    if length_squared <= 1.0e-12:
        minimum = math.hypot(x0, z0)
    else:
        closest = max(0.0, min(1.0, -(x0 * dx + z0 * dz) / length_squared))
        minimum = math.hypot(x0 + closest * dx, z0 + closest * dz)
    maximum = max(math.hypot(x0, z0), math.hypot(x1, z1))
    return minimum, maximum


def ray_hits_annular_plate(
    source,
    target,
    center_x: float = 0.0,
    center_z: float = 0.0,
) -> bool:
    center = annular_baffle_center_y()
    half = BAFFLE_PLATE_THICKNESS / 2.0
    minimum, maximum = segment_radial_range_at_y_interval(
        source,
        target,
        center - half,
        center + half,
        center_x,
        center_z,
    )
    return maximum >= SHIELD_INNER_RADIUS and minimum <= SHIELD_OUTER_RADIUS


def ray_hits_center_plate(
    source,
    target,
    center_x: float = 0.0,
    center_z: float = 0.0,
) -> bool:
    center = center_baffle_center_y()
    half = BAFFLE_PLATE_THICKNESS / 2.0
    minimum, _maximum = segment_radial_range_at_y_interval(
        source,
        target,
        center - half,
        center + half,
        center_x,
        center_z,
    )
    return minimum <= CENTER_BLOCKER_RADIUS


def polar_point(
    radius: float,
    angle: float,
    y: float,
    center_x: float = 0.0,
    center_z: float = 0.0,
):
    return (
        center_x + radius * math.cos(angle),
        y,
        center_z + radius * math.sin(angle),
    )


def sound_path_sample_points(
    source_radius_steps: int,
    target_radius_steps: int,
    angular_steps: int,
    source_offset=(0.0, 0.0),
    target_offset=(0.0, 0.0),
):
    source_points = []
    for radius_index in range(source_radius_steps):
        radius = FAN_HUB_DIAMETER / 2.0 + (
            FAN_BLADE_SWEEP_DIAMETER / 2.0 - FAN_HUB_DIAMETER / 2.0
        ) * radius_index / (source_radius_steps - 1)
        for angle_index in range(angular_steps):
            source_points.append(
                polar_point(
                    radius,
                    2.0 * math.pi * angle_index / angular_steps,
                    fan_face_y(),
                    *source_offset,
                )
            )

    target_points = [(target_offset[0], case_flange_near_face_y(), target_offset[1])]
    for radius_index in range(1, target_radius_steps):
        radius = FAN_OPENING_DIAMETER / 2.0 * radius_index / (target_radius_steps - 1)
        for angle_index in range(angular_steps):
            target_points.append(
                polar_point(
                    radius,
                    2.0 * math.pi * angle_index / angular_steps,
                    case_flange_near_face_y(),
                    *target_offset,
                )
            )
    return source_points, target_points


def radial_offset_vectors(radius: float):
    return tuple(
        (
            radius * math.cos(2.0 * math.pi * index / 8.0),
            radius * math.sin(2.0 * math.pi * index / 8.0),
        )
        for index in range(8)
    )


def validate_blade_to_case_sound_paths() -> None:
    """Sample nominal and independently shifted fan/stack acoustic rays."""
    source_points, target_points = sound_path_sample_points(19, 14, 36)
    rays = 0
    for source in source_points:
        for target in target_points:
            rays += 1
            if not (
                ray_hits_annular_plate(source, target)
                or ray_hits_center_plate(source, target)
            ):
                raise RuntimeError(
                    "A sampled blade-to-case ray bypasses both curved baffles: "
                    f"source={source} target={target}"
                )

    shifted_rays = 0
    fan_offsets = radial_offset_vectors(fan_to_stack_max_offset())
    stack_offsets = radial_offset_vectors(stack_max_relative_offset())
    for source_offset in fan_offsets:
        shifted_sources, _unused = sound_path_sample_points(
            9,
            7,
            12,
            source_offset=source_offset,
        )
        for target_offset in stack_offsets:
            _unused, shifted_targets = sound_path_sample_points(
                9,
                7,
                12,
                target_offset=target_offset,
            )
            for center_offset in stack_offsets:
                for source in shifted_sources:
                    for target in shifted_targets:
                        shifted_rays += 1
                        if not (
                            ray_hits_annular_plate(source, target)
                            or ray_hits_center_plate(source, target, *center_offset)
                        ):
                            raise RuntimeError(
                                "A shifted blade-to-case ray bypasses both baffles: "
                                f"source_offset={source_offset} "
                                f"target_offset={target_offset} "
                                f"center_offset={center_offset} "
                                f"source={source} target={target}"
                            )
    print(
        "CURVED_SOUND_PATH PASS "
        f"finite_rays={rays} shifted_rays={shifted_rays} "
        f"analytic_overlap_margin="
        f"{polygon_apothem(CENTER_BLOCKER_RADIUS) - required_center_blocker_radius():.2f}mm "
        f"fan_to_stack_offset={fan_to_stack_max_offset():.2f}mm "
        f"stack_relative_offset={stack_max_relative_offset():.2f}mm "
        f"blade_root_diameter={FAN_HUB_DIAMETER:.1f}mm"
    )


def case_generator_path() -> Path:
    return Path(__file__).resolve().with_name(CASE_GENERATOR_NAME)


def read_case_interface_config():
    source_path = case_generator_path()
    if not source_path.is_file():
        raise FileNotFoundError(f"Case generator not found: {source_path}")
    tree = ast.parse(source_path.read_text(encoding="utf-8"), source_path.name)
    values = {}
    wanted = set(CASE_INTERFACE_CONFIG_NAMES)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in wanted:
                values[target.id] = ast.literal_eval(node.value)
    missing = wanted - values.keys()
    if missing:
        raise ValueError(
            f"Missing case interface constants in {source_path.name}: {sorted(missing)}"
        )
    return values


def validate_case_interface() -> None:
    if not CASE_INTERFACE_ACTIVE:
        print(
            "CASE_INTERFACE_SOURCE SKIP "
            f"fan_size={FAN_NOMINAL_SIZE:g}mm mode={CASE_INTERFACE_MODE}"
        )
        return
    case = read_case_interface_config()
    expected = {
        "FAN_OPENING_DIAMETER": FAN_OPENING_DIAMETER,
        "FAN_HOLE_SPACING_X": FAN_HOLE_SPACING,
        "FAN_HOLE_SPACING_Z": FAN_HOLE_SPACING,
        "FAN_HOLE_DIAMETER": FAN_BOLT_HOLE_DIAMETER,
    }
    mismatches = {
        name: (case[name], expected_value)
        for name, expected_value in expected.items()
        if not math.isclose(float(case[name]), expected_value, abs_tol=1.0e-9)
    }
    if mismatches:
        raise ValueError(f"Silencer/case fan interface drift: {mismatches}")
    pad_margin = (
        min(case["BACK_DOME_FAN_PAD_WIDTH"], case["BACK_DOME_FAN_PAD_HEIGHT"])
        - OUTER_SIZE
    ) / 2.0
    if pad_margin < MINIMUM_CASE_PAD_MARGIN:
        raise ValueError(
            f"Only {pad_margin:.2f} mm per side remains on the case fan pad"
        )
    sleeve_margin = (
        min(case["BACK_DOME_FAN_PAD_WIDTH"], case["BACK_DOME_FAN_PAD_HEIGHT"])
        - sleeve_outer_size()
    ) / 2.0
    if sleeve_margin < -1.0e-9:
        raise ValueError(
            f"The alignment sleeve overhangs the case fan pad by {-sleeve_margin:.2f} mm"
        )
    print(
        "CASE_INTERFACE_SOURCE PASS "
        f"source={case_generator_path().name} pad_margin={pad_margin:.2f}mm "
        f"sleeve_margin={sleeve_margin:.2f}mm "
        f"internal_cartridge_default={case['BAFFLE_CARTRIDGE_ENABLED']}"
    )


def validate_config() -> None:
    if LAYOUT_MODE not in {"assembled", "print_bed"}:
        raise ValueError("LAYOUT_MODE must be 'assembled' or 'print_bed'")
    if OUTER_SIZE < FAN_NOMINAL_SIZE:
        raise ValueError("OUTER_SIZE must cover the nominal fan face")
    if FAN_OPENING_DIAMETER >= OUTER_SIZE - 2.0:
        raise ValueError("The flange needs material around the airflow opening")
    if FAN_BOLT_HOLE_DIAMETER <= 3.0:
        raise ValueError("The through-bolt holes need positive print clearance")
    if not 0.0 < THROUGH_BOLT_DIAMETER < FAN_BOLT_HOLE_DIAMETER:
        raise ValueError("The selected through-bolt must fit the fan bolt holes")
    if not 0.0 < FAN_HUB_DIAMETER < FAN_OPENING_DIAMETER:
        raise ValueError("FAN_HUB_DIAMETER must fit inside the fan opening")
    if not FAN_HUB_DIAMETER < FAN_BLADE_SWEEP_DIAMETER <= FAN_OPENING_DIAMETER:
        raise ValueError(
            "The declared blade sweep must fit inside the interface opening"
        )
    if FAN_FRAME_POCKET_CLEARANCE_PER_SIDE <= 0.0:
        raise ValueError("The fan-frame pocket needs positive assembly clearance")
    if STACK_SLEEVE_CLEARANCE_PER_SIDE <= 0.0:
        raise ValueError("The alignment sleeve needs positive assembly clearance")
    if SLEEVE_WALL_THICKNESS < 0.6:
        raise ValueError("The alignment sleeve wall must remain printable")
    if fan_frame_transition_depth() <= 0.0:
        raise ValueError("The alignment sleeve must narrow toward the fan frame")
    if MINIMUM_ACOUSTIC_OVERLAP <= 0.0:
        raise ValueError("The acoustic overlap reserve must remain positive")

    hole_center = FAN_HOLE_SPACING / 2.0
    outer_half = OUTER_SIZE / 2.0
    if hole_center + FAN_BOLT_HOLE_DIAMETER / 2.0 >= outer_half:
        raise ValueError("Fan bolt holes break through the outside edge")
    if CORNER_BOSS_SIZE <= FAN_BOLT_HOLE_DIAMETER + 2.0:
        raise ValueError("Corner bosses leave too little radial bolt material")
    boss_outer_edge = hole_center + CORNER_BOSS_SIZE / 2.0
    if boss_outer_edge >= outer_half:
        raise ValueError("Corner bosses break through the configured envelope")
    if boss_outer_edge >= chamber_half_size():
        raise ValueError("Corner bosses leave no open length for their wall webs")
    if CORNER_BOSS_WEB_WIDTH <= 0.0:
        raise ValueError("Corner-boss wall webs need positive width")
    if not 0.0 < CORNER_BOSS_WEB_OVERLAP < CORNER_BOSS_SIZE / 2.0:
        raise ValueError("Corner-boss web overlap must enter each boss")

    if BAFFLE_PLATE_THICKNESS <= 0.0:
        raise ValueError("The annular baffle plate needs positive thickness")
    if not 0.0 < SHIELD_INNER_RADIUS < SHIELD_OUTER_RADIUS:
        raise ValueError("The shield radii must define a positive annulus")
    if SHIELD_INNER_RADIUS > FAN_HUB_DIAMETER / 2.0:
        raise ValueError(
            "The annular shield leaves part of the declared blade root exposed"
        )
    if (
        polygon_apothem(SHIELD_OUTER_RADIUS)
        < required_outer_shield_radius() + MINIMUM_ACOUSTIC_OVERLAP
    ):
        raise ValueError(
            "The polygonal acoustic shield lacks shifted outer-edge overlap"
        )
    if SHIELD_OUTER_RADIUS >= chamber_half_size():
        raise ValueError("The annular shield leaves no outer route in the chamber")
    if CURVED_SKIRT_THICKNESS <= 0.0:
        raise ValueError("Curved skirts need positive wall thickness")
    if 2.0 * CURVED_SKIRT_THICKNESS >= SHIELD_OUTER_RADIUS - SHIELD_INNER_RADIUS:
        raise ValueError("The two curved skirts overlap across the annular cup")
    if not 0.0 < CURVED_SKIRT_HEIGHT < SPACER_DEPTH:
        raise ValueError("Curved skirts must fit within one expansion spacer")
    if not 0.0 < OUTER_SKIRT_CORNER_GAP_DEG < 45.0:
        raise ValueError("Outer-skirt corner gaps must remain below 45 degrees")
    if len(RADIAL_ARM_ANGLES_DEG) != 4:
        raise ValueError("The four-hole insert needs four radial support arms")
    if not (
        SHIELD_INNER_RADIUS
        < RADIAL_ARM_INNER_RADIUS
        < SHIELD_OUTER_RADIUS
        < RADIAL_ARM_OUTER_RADIUS
    ):
        raise ValueError("Radial arms must overlap and leave the annular shield")
    if not SHIELD_INNER_RADIUS < CENTER_BLOCKER_RADIUS < SHIELD_OUTER_RADIUS:
        raise ValueError("The center blocker must overlap the annular shield opening")
    if CENTER_BLOCKER_RADIUS - CURVED_SKIRT_THICKNESS <= SHIELD_INNER_RADIUS:
        raise ValueError("The center blocker's curved cup is too narrow")
    if FAN_SIDE_MARK_HEIGHT <= 0.0:
        raise ValueError("The fan-side orientation mark needs positive height")
    if not 0.0 < LOCATOR_TAB_AXIAL_CLEARANCE < BAFFLE_PLATE_THICKNESS / 2.0:
        raise ValueError("The locator-tab face clearance must fit in the baffle plate")

    guaranteed_center_radius = polygon_apothem(CENTER_BLOCKER_RADIUS)
    required_center_radius = required_center_blocker_radius()
    if guaranteed_center_radius < required_center_radius + MINIMUM_ACOUSTIC_OVERLAP:
        raise ValueError(
            "The polygonal center blocker lacks acoustic overlap: "
            f"guaranteed={guaranteed_center_radius:.3f}mm "
            f"required={required_center_radius + MINIMUM_ACOUSTIC_OVERLAP:.3f}mm"
        )

    open_ratio = minimum_airway_area() / fan_opening_area()
    if open_ratio < MINIMUM_AIRWAY_TO_FAN_AREA_RATIO:
        raise ValueError(
            f"Minimum curved-baffle airway is only {open_ratio:.1%} of the fan opening"
        )


# ---------------------------------------------------------------------------
# Scene and primitive helpers


def configure_scene() -> None:
    if CLEAR_SCENE:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 0.001


def select_only(obj) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def create_mesh_object(name: str, vertices, faces):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    cleanup_mesh(obj)
    return obj


def add_box(
    name: str,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    z0: float,
    z1: float,
):
    if x1 <= x0 or y1 <= y0 or z1 <= z0:
        raise ValueError(f"Invalid box bounds for {name}")
    bpy.ops.mesh.primitive_cube_add(
        location=((x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0)
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    obj.dimensions = (x1 - x0, y1 - y0, z1 - z0)
    select_only(obj)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=True)
    return obj


def add_cylinder_y(
    name: str,
    radius: float,
    y0: float,
    y1: float,
    x: float = 0.0,
    z: float = 0.0,
):
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
    select_only(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def add_radial_arm_y(
    name: str,
    angle_deg: float,
    radius0: float,
    radius1: float,
    width: float,
    y0: float,
    y1: float,
):
    angle = math.radians(angle_deg)
    center_radius = (radius0 + radius1) / 2.0
    bpy.ops.mesh.primitive_cube_add(
        location=(
            center_radius * math.cos(angle),
            (y0 + y1) / 2.0,
            center_radius * math.sin(angle),
        ),
        rotation=(0.0, -angle, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    obj.dimensions = (radius1 - radius0, y1 - y0, width)
    select_only(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def add_annular_arc_y(
    name: str,
    inner_radius: float,
    outer_radius: float,
    y0: float,
    y1: float,
    start_deg: float,
    end_deg: float,
):
    sweep = end_deg - start_deg
    segments = max(12, math.ceil(CYLINDER_SEGMENTS * sweep / 360.0))
    vertices = []
    for index in range(segments + 1):
        angle = math.radians(start_deg + sweep * index / segments)
        cosine = math.cos(angle)
        sine = math.sin(angle)
        vertices.extend(
            (
                (inner_radius * cosine, y0, inner_radius * sine),
                (outer_radius * cosine, y0, outer_radius * sine),
                (inner_radius * cosine, y1, inner_radius * sine),
                (outer_radius * cosine, y1, outer_radius * sine),
            )
        )
    faces = []
    for index in range(segments):
        base = 4 * index
        next_base = base + 4
        faces.extend(
            (
                (base, next_base, next_base + 1, base + 1),
                (base + 2, base + 3, next_base + 3, next_base + 2),
                (base, base + 2, next_base + 2, next_base),
                (base + 1, next_base + 1, next_base + 3, base + 3),
            )
        )
    faces.append((0, 1, 3, 2))
    final = 4 * segments
    faces.append((final, final + 2, final + 3, final + 1))
    return create_mesh_object(name, vertices, faces)


def join_objects(name: str, objects):
    objects = list(objects)
    if not objects:
        raise ValueError(f"Cannot create empty joined object {name}")
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


def cleanup_mesh(obj) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=BOOLEAN_CLEANUP_DISTANCE)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=BOOLEAN_CLEANUP_DISTANCE)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def mesh_volume(obj) -> float:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    volume = abs(bm.calc_volume(signed=True)) if bm.faces else 0.0
    bm.free()
    return volume


def apply_boolean(base, tool, operation: str, label: str):
    before_volume = mesh_volume(base)
    select_only(base)
    modifier = base.modifiers.new(label, "BOOLEAN")
    modifier.operation = operation
    modifier.object = tool
    if hasattr(modifier, "solver"):
        modifier.solver = BOOLEAN_SOLVER
    if hasattr(modifier, "use_self"):
        modifier.use_self = False
    modifier_name = modifier.name
    result = bpy.ops.object.modifier_apply(modifier=modifier_name)
    if "FINISHED" not in result or base.modifiers.get(modifier_name) is not None:
        raise RuntimeError(
            f"Boolean {label} failed: operation={operation} result={result}"
        )
    bpy.data.objects.remove(tool, do_unlink=True)
    cleanup_mesh(base)
    after_volume = mesh_volume(base)
    if abs(after_volume - before_volume) <= BOOLEAN_MINIMUM_VOLUME_CHANGE:
        raise RuntimeError(
            f"Boolean {label} made no measurable volume change: "
            f"before={before_volume:.6f} after={after_volume:.6f}"
        )
    return base


def boolean_difference(base, tools, label: str):
    tool = join_objects(label + "_Tools", tools)
    return apply_boolean(base, tool, "DIFFERENCE", label)


def boolean_union(base, part, label: str):
    return apply_boolean(base, part, "UNION", label)


def add_annular_ring_y(
    name: str,
    inner_radius: float,
    outer_radius: float,
    y0: float,
    y1: float,
):
    ring = add_cylinder_y(name, outer_radius, y0, y1)
    cutter = add_cylinder_y(name + "_Inner_Cutter", inner_radius, y0 - 0.2, y1 + 0.2)
    apply_boolean(ring, cutter, "DIFFERENCE", name + "_Open_Center")
    return ring


def square_loop(size: float):
    half = size / 2.0
    return (
        (-half, -half),
        (half, -half),
        (half, half),
        (-half, half),
    )


def add_square_sleeve(
    name: str,
    sections,
    outer_size: float,
):
    """Create a closed square tube whose inner size varies by Y section."""
    outer = square_loop(outer_size)
    vertices = []
    for y, inner_size in sections:
        inner = square_loop(inner_size)
        vertices.extend((x, y, z) for x, z in outer)
        vertices.extend((x, y, z) for x, z in inner)

    def outer_vertex(section, index):
        return section * 8 + index % 4

    def inner_vertex(section, index):
        return section * 8 + 4 + index % 4

    faces = []
    for section in range(len(sections) - 1):
        next_section = section + 1
        for index in range(4):
            next_index = index + 1
            faces.append(
                (
                    outer_vertex(section, index),
                    outer_vertex(section, next_index),
                    outer_vertex(next_section, next_index),
                    outer_vertex(next_section, index),
                )
            )
            faces.append(
                (
                    inner_vertex(section, next_index),
                    inner_vertex(section, index),
                    inner_vertex(next_section, index),
                    inner_vertex(next_section, next_index),
                )
            )

    last_section = len(sections) - 1
    for section in (0, last_section):
        for index in range(4):
            next_index = index + 1
            if section == 0:
                faces.append(
                    (
                        outer_vertex(section, next_index),
                        outer_vertex(section, index),
                        inner_vertex(section, index),
                        inner_vertex(section, next_index),
                    )
                )
            else:
                faces.append(
                    (
                        outer_vertex(section, index),
                        outer_vertex(section, next_index),
                        inner_vertex(section, next_index),
                        inner_vertex(section, index),
                    )
                )
    return create_mesh_object(name, vertices, faces)


# ---------------------------------------------------------------------------
# Printable geometry


def fan_hole_centers():
    center = FAN_HOLE_SPACING / 2.0
    return tuple((x, z) for x in (-center, center) for z in (-center, center))


def create_alignment_sleeve():
    transition_depth = fan_frame_transition_depth()
    fan_end = fan_face_y() - transition_depth - FAN_FRAME_POCKET_DEPTH
    sections = (
        (fan_end, fan_frame_pocket_size()),
        (fan_face_y() - transition_depth, fan_frame_pocket_size()),
        (fan_face_y(), sleeve_inner_size()),
        (case_face_y(), sleeve_inner_size()),
    )
    sleeve = add_square_sleeve(
        "Silencer_Common_Alignment_Sleeve",
        sections,
        sleeve_outer_size(),
    )
    sleeve.name = object_prefix() + "_Alignment_Sleeve"
    return sleeve


def create_flange():
    half = OUTER_SIZE / 2.0
    depth_half = FLANGE_THICKNESS / 2.0
    flange = add_box(
        "Silencer_Flange",
        -half,
        half,
        -depth_half,
        depth_half,
        -half,
        half,
    )
    cutters = [
        add_cylinder_y(
            "Flange_Airflow_Cutter",
            FAN_OPENING_DIAMETER / 2.0,
            -depth_half - 0.2,
            depth_half + 0.2,
        )
    ]
    for index, (x, z) in enumerate(fan_hole_centers()):
        cutters.append(
            add_cylinder_y(
                f"Flange_Bolt_Cutter_{index}",
                FAN_BOLT_HOLE_DIAMETER / 2.0,
                -depth_half - 0.2,
                depth_half + 0.2,
                x=x,
                z=z,
            )
        )
    boolean_difference(flange, cutters, "Cut_Flange_Openings")
    flange.name = object_prefix() + "_Flange_Case"
    return flange


def add_spacer_corner_structure(spacer, y0: float, y1: float) -> None:
    half = OUTER_SIZE / 2.0
    boss_half = CORNER_BOSS_SIZE / 2.0
    web_half = CORNER_BOSS_WEB_WIDTH / 2.0
    for index, (x, z) in enumerate(fan_hole_centers()):
        x_sign = 1.0 if x > 0.0 else -1.0
        z_sign = 1.0 if z > 0.0 else -1.0
        if x_sign > 0.0:
            x0 = x + boss_half - CORNER_BOSS_WEB_OVERLAP
            x1 = half
        else:
            x0 = -half
            x1 = x - boss_half + CORNER_BOSS_WEB_OVERLAP
        side_web = add_box(
            f"Spacer_Side_Web_{index}",
            x0,
            x1,
            y0,
            y1,
            z - web_half,
            z + web_half,
        )
        boolean_union(spacer, side_web, f"Union_Spacer_Side_Web_{index}")

        if z_sign > 0.0:
            z0 = z + boss_half - CORNER_BOSS_WEB_OVERLAP
            z1 = half
        else:
            z0 = -half
            z1 = z - boss_half + CORNER_BOSS_WEB_OVERLAP
        top_bottom_web = add_box(
            f"Spacer_Top_Bottom_Web_{index}",
            x - web_half,
            x + web_half,
            y0,
            y1,
            z0,
            z1,
        )
        boolean_union(
            spacer,
            top_bottom_web,
            f"Union_Spacer_Top_Bottom_Web_{index}",
        )

        boss = add_box(
            f"Spacer_Corner_Boss_{index}",
            x - boss_half,
            x + boss_half,
            y0,
            y1,
            z - boss_half,
            z + boss_half,
        )
        boolean_union(spacer, boss, f"Union_Spacer_Corner_Boss_{index}")


def add_baffle_locator_tabs(baffle, prefix: str, y0: float, y1: float) -> None:
    """Connect each bolt pad to the sleeve datum along already blocked webs."""
    half = OUTER_SIZE / 2.0
    boss_half = CORNER_BOSS_SIZE / 2.0
    web_half = CORNER_BOSS_WEB_WIDTH / 2.0
    for index, (x, z) in enumerate(fan_hole_centers()):
        x_sign = 1.0 if x > 0.0 else -1.0
        z_sign = 1.0 if z > 0.0 else -1.0
        if x_sign > 0.0:
            side_x0 = x + boss_half - CORNER_BOSS_WEB_OVERLAP
            side_x1 = half
        else:
            side_x0 = -half
            side_x1 = x - boss_half + CORNER_BOSS_WEB_OVERLAP
        side_tab = add_box(
            f"{prefix}_Side_Locator_{index}",
            side_x0,
            side_x1,
            y0,
            y1,
            z - web_half,
            z + web_half,
        )
        boolean_union(baffle, side_tab, f"Union_{prefix}_Side_Locator_{index}")

        if z_sign > 0.0:
            tab_z0 = z + boss_half - CORNER_BOSS_WEB_OVERLAP
            tab_z1 = half
        else:
            tab_z0 = -half
            tab_z1 = z - boss_half + CORNER_BOSS_WEB_OVERLAP
        top_bottom_tab = add_box(
            f"{prefix}_Top_Bottom_Locator_{index}",
            x - web_half,
            x + web_half,
            y0,
            y1,
            tab_z0,
            tab_z1,
        )
        boolean_union(
            baffle,
            top_bottom_tab,
            f"Union_{prefix}_Top_Bottom_Locator_{index}",
        )


def create_spacer():
    half = OUTER_SIZE / 2.0
    depth_half = SPACER_DEPTH / 2.0
    chamber_half = chamber_half_size()
    spacer = add_box(
        "Silencer_Expansion_Spacer",
        -half,
        half,
        -depth_half,
        depth_half,
        -half,
        half,
    )
    chamber = add_box(
        "Spacer_Expansion_Chamber_Cutter",
        -chamber_half,
        chamber_half,
        -depth_half - 0.2,
        depth_half + 0.2,
        -chamber_half,
        chamber_half,
    )
    apply_boolean(spacer, chamber, "DIFFERENCE", "Cut_Spacer_Expansion_Chamber")
    add_spacer_corner_structure(spacer, -depth_half, depth_half)

    bolt_cutters = [
        add_cylinder_y(
            f"Spacer_Bolt_Cutter_{index}",
            FAN_BOLT_HOLE_DIAMETER / 2.0,
            -depth_half - 0.2,
            depth_half + 0.2,
            x=x,
            z=z,
        )
        for index, (x, z) in enumerate(fan_hole_centers())
    ]
    boolean_difference(spacer, bolt_cutters, "Cut_Spacer_Bolt_Bores")
    spacer.name = object_prefix() + "_Spacer_Fan"
    return spacer


def outer_skirt_arc_ranges():
    ranges = []
    corner_angles = RADIAL_ARM_ANGLES_DEG
    for index, angle in enumerate(corner_angles):
        next_angle = corner_angles[(index + 1) % len(corner_angles)]
        if next_angle <= angle:
            next_angle += 360.0
        ranges.append(
            (
                angle + OUTER_SKIRT_CORNER_GAP_DEG,
                next_angle - OUTER_SKIRT_CORNER_GAP_DEG,
            )
        )
    return tuple(ranges)


def add_fan_side_mark(base, prefix: str, x0: float) -> None:
    """Emboss a block F on the face whose curved walls must face the fan."""
    plate_half = BAFFLE_PLATE_THICKNESS / 2.0
    y0 = plate_half - 0.15
    y1 = plate_half + FAN_SIDE_MARK_HEIGHT
    strokes = (
        (x0, x0 + 0.8, -2.5, 2.5),
        (x0 + 0.6, x0 + 4.0, 1.7, 2.5),
        (x0 + 0.6, x0 + 3.2, -0.4, 0.4),
    )
    for index, (stroke_x0, stroke_x1, stroke_z0, stroke_z1) in enumerate(strokes):
        stroke = add_box(
            f"{prefix}_Fan_Mark_{index}",
            stroke_x0,
            stroke_x1,
            y0,
            y1,
            stroke_z0,
            stroke_z1,
        )
        boolean_union(base, stroke, f"Union_{prefix}_Fan_Mark_{index}")


def create_curved_baffle():
    plate_half = BAFFLE_PLATE_THICKNESS / 2.0
    baffle = add_annular_ring_y(
        "Curved_Baffle_Annular_Shield",
        SHIELD_INNER_RADIUS,
        SHIELD_OUTER_RADIUS,
        -plate_half,
        plate_half,
    )

    for index, angle in enumerate(RADIAL_ARM_ANGLES_DEG):
        arm = add_radial_arm_y(
            f"Curved_Baffle_Radial_Arm_{index}",
            angle,
            RADIAL_ARM_INNER_RADIUS,
            RADIAL_ARM_OUTER_RADIUS,
            RADIAL_ARM_WIDTH,
            -plate_half,
            plate_half,
        )
        boolean_union(baffle, arm, f"Union_Curved_Baffle_Arm_{index}")

    boss_half = CORNER_BOSS_SIZE / 2.0
    for index, (x, z) in enumerate(fan_hole_centers()):
        pad = add_box(
            f"Curved_Baffle_Bolt_Pad_{index}",
            x - boss_half,
            x + boss_half,
            -plate_half,
            plate_half,
            z - boss_half,
            z + boss_half,
        )
        boolean_union(baffle, pad, f"Union_Curved_Baffle_Bolt_Pad_{index}")
    add_baffle_locator_tabs(
        baffle,
        "Curved_Baffle",
        -plate_half + LOCATOR_TAB_AXIAL_CLEARANCE,
        plate_half - LOCATOR_TAB_AXIAL_CLEARANCE,
    )

    bolt_cutters = [
        add_cylinder_y(
            f"Curved_Baffle_Bolt_Cutter_{index}",
            FAN_BOLT_HOLE_DIAMETER / 2.0,
            -plate_half - 0.2,
            plate_half + 0.2,
            x=x,
            z=z,
        )
        for index, (x, z) in enumerate(fan_hole_centers())
    ]
    boolean_difference(baffle, bolt_cutters, "Cut_Curved_Baffle_Bolt_Bores")

    skirt_y0 = plate_half - 0.15
    skirt_y1 = plate_half + CURVED_SKIRT_HEIGHT
    inner_skirt = add_annular_ring_y(
        "Curved_Baffle_Inner_Skirt",
        SHIELD_INNER_RADIUS,
        SHIELD_INNER_RADIUS + CURVED_SKIRT_THICKNESS,
        skirt_y0,
        skirt_y1,
    )
    boolean_union(baffle, inner_skirt, "Union_Curved_Baffle_Inner_Skirt")

    outer_inner_radius = SHIELD_OUTER_RADIUS - CURVED_SKIRT_THICKNESS
    outer_outer_radius = SHIELD_OUTER_RADIUS
    for index, (start_deg, end_deg) in enumerate(outer_skirt_arc_ranges()):
        arc = add_annular_arc_y(
            f"Curved_Baffle_Outer_Skirt_Arc_{index}",
            outer_inner_radius,
            outer_outer_radius,
            skirt_y0,
            skirt_y1,
            start_deg,
            end_deg,
        )
        boolean_union(baffle, arc, f"Union_Curved_Baffle_Outer_Arc_{index}")

    add_fan_side_mark(baffle, "Curved_Baffle", SHIELD_INNER_RADIUS + 2.0)
    baffle.name = object_prefix() + "_Curved_Baffle"
    return baffle


def create_center_baffle():
    plate_half = BAFFLE_PLATE_THICKNESS / 2.0
    baffle = add_cylinder_y(
        "Center_Baffle_Shield",
        CENTER_BLOCKER_RADIUS,
        -plate_half,
        plate_half,
    )

    arm_inner_radius = CENTER_BLOCKER_RADIUS - 0.2
    for index, angle in enumerate(RADIAL_ARM_ANGLES_DEG):
        arm = add_radial_arm_y(
            f"Center_Baffle_Radial_Arm_{index}",
            angle,
            arm_inner_radius,
            RADIAL_ARM_OUTER_RADIUS,
            RADIAL_ARM_WIDTH,
            -plate_half,
            plate_half,
        )
        boolean_union(baffle, arm, f"Union_Center_Baffle_Arm_{index}")

    boss_half = CORNER_BOSS_SIZE / 2.0
    for index, (x, z) in enumerate(fan_hole_centers()):
        pad = add_box(
            f"Center_Baffle_Bolt_Pad_{index}",
            x - boss_half,
            x + boss_half,
            -plate_half,
            plate_half,
            z - boss_half,
            z + boss_half,
        )
        boolean_union(baffle, pad, f"Union_Center_Baffle_Bolt_Pad_{index}")
    add_baffle_locator_tabs(
        baffle,
        "Center_Baffle",
        -plate_half + LOCATOR_TAB_AXIAL_CLEARANCE,
        plate_half - LOCATOR_TAB_AXIAL_CLEARANCE,
    )

    bolt_cutters = [
        add_cylinder_y(
            f"Center_Baffle_Bolt_Cutter_{index}",
            FAN_BOLT_HOLE_DIAMETER / 2.0,
            -plate_half - 0.2,
            plate_half + 0.2,
            x=x,
            z=z,
        )
        for index, (x, z) in enumerate(fan_hole_centers())
    ]
    boolean_difference(baffle, bolt_cutters, "Cut_Center_Baffle_Bolt_Bores")

    skirt_y0 = plate_half - 0.15
    skirt_y1 = plate_half + CURVED_SKIRT_HEIGHT
    rim = add_annular_ring_y(
        "Center_Baffle_Curved_Rim",
        CENTER_BLOCKER_RADIUS - CURVED_SKIRT_THICKNESS,
        CENTER_BLOCKER_RADIUS,
        skirt_y0,
        skirt_y1,
    )
    boolean_union(baffle, rim, "Union_Center_Baffle_Curved_Rim")
    add_fan_side_mark(baffle, "Center_Baffle", -4.0)
    baffle.name = object_prefix() + "_Center_Baffle"
    return baffle


def duplicate_object(source, name: str, copy_mesh: bool = False):
    duplicate = source.copy()
    duplicate.data = source.data.copy() if copy_mesh else source.data
    bpy.context.collection.objects.link(duplicate)
    duplicate.name = name
    return duplicate


def build_components():
    flange_case = create_flange()
    flange_fan = duplicate_object(flange_case, object_prefix() + "_Flange_Fan")
    spacer_fan = create_spacer()
    spacer_middle = duplicate_object(spacer_fan, object_prefix() + "_Spacer_Middle")
    spacer_case = duplicate_object(spacer_fan, object_prefix() + "_Spacer_Case")
    curved_baffle = create_curved_baffle()
    center_baffle = create_center_baffle()
    alignment_sleeve = create_alignment_sleeve()

    plate_half = BAFFLE_PLATE_THICKNESS / 2.0
    annular_y = annular_baffle_center_y()
    center_y = center_baffle_center_y()
    spacer_fan.location.y = annular_y - plate_half - SPACER_DEPTH / 2.0
    spacer_middle.location.y = 0.0
    spacer_case.location.y = center_y + plate_half + SPACER_DEPTH / 2.0
    flange_fan.location.y = fan_face_y() + FLANGE_THICKNESS / 2.0
    flange_case.location.y = case_face_y() - FLANGE_THICKNESS / 2.0
    curved_baffle.location.y = annular_y
    center_baffle.location.y = center_y
    # Source inserts print with their curved walls and raised F in +Y.  In the
    # assembly both marked cup faces point toward the fan at -Y.
    curved_baffle.rotation_euler.x = math.pi
    center_baffle.rotation_euler.x = math.pi
    return (
        flange_case,
        flange_fan,
        spacer_case,
        spacer_middle,
        spacer_fan,
        curved_baffle,
        center_baffle,
        alignment_sleeve,
    )


# ---------------------------------------------------------------------------
# Mesh, assembly, and print validation


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
    cleanup_mesh(obj)
    non_manifold = non_manifold_edge_count(obj)
    shells = connected_shell_count(obj)
    volume = mesh_volume(obj)
    print(
        f"{obj.name}: vertices={len(obj.data.vertices)} "
        f"polygons={len(obj.data.polygons)} volume={volume:.2f}mm3 "
        f"non_manifold_edges={non_manifold} connected_shells={shells}"
    )
    if non_manifold:
        raise RuntimeError(f"{obj.name} has {non_manifold} non-manifold edges")
    if shells != 1:
        raise RuntimeError(f"{obj.name} has {shells} disconnected shells")
    if volume <= 0.0:
        raise RuntimeError(f"{obj.name} has no enclosed volume")


def world_intersection_volume(first, second, label: str) -> float:
    first_copy = duplicate_object(first, label + "_First", copy_mesh=True)
    second_copy = duplicate_object(second, label + "_Second", copy_mesh=True)
    temporary_names = (first_copy.name, second_copy.name)
    try:
        for obj in (first_copy, second_copy):
            select_only(obj)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        apply_boolean(
            first_copy,
            second_copy,
            "INTERSECT",
            label + "_Intersection",
        )
        return mesh_volume(first_copy)
    finally:
        for name in temporary_names:
            obj = bpy.data.objects.get(name)
            if obj is not None:
                bpy.data.objects.remove(obj, do_unlink=True)


def validate_assembled_fit(components) -> None:
    """Reject assembled-volume interference among the eight printed parts."""
    intersections = {}
    for first, second in itertools.combinations(components, 2):
        label = f"Fit_{first.name}_{second.name}"
        intersections[label] = world_intersection_volume(first, second, label)
    maximum = max(intersections.values())
    if maximum > 0.001:
        raise RuntimeError(f"Assembled components interfere: {intersections}")
    print(
        "ASSEMBLED_FIT PASS "
        f"checked_pairs={len(intersections)} "
        f"maximum_boolean_interference={maximum:.9f}mm3"
    )


def equal_circle_overlap_area(radius: float, center_offset: float) -> float:
    if center_offset >= 2.0 * radius:
        return 0.0
    return 2.0 * radius**2 * math.acos(
        center_offset / (2.0 * radius)
    ) - center_offset / 2.0 * math.sqrt(4.0 * radius**2 - center_offset**2)


def validate_interfaces() -> None:
    flange_web = (
        math.hypot(FAN_HOLE_SPACING / 2.0, FAN_HOLE_SPACING / 2.0)
        - FAN_OPENING_DIAMETER / 2.0
        - FAN_BOLT_HOLE_DIAMETER / 2.0
    )
    if flange_web < 2.0:
        raise RuntimeError(f"Only {flange_web:.2f} mm remains between openings")
    interface_offset = (
        FAN_BOLT_HOLE_DIAMETER - THROUGH_BOLT_DIAMETER + INTERFACE_PRINT_HOLE_ALLOWANCE
    )
    interface_overlap = equal_circle_overlap_area(
        FAN_OPENING_DIAMETER / 2.0,
        interface_offset,
    )
    interface_overlap_ratio = interface_overlap / fan_opening_area()
    if interface_overlap_ratio < MINIMUM_INTERFACE_AIRWAY_OVERLAP_RATIO:
        raise RuntimeError(
            "Bolt-hole play reduces the interface airway overlap to "
            f"{interface_overlap_ratio:.1%}"
        )
    outer_overlap = (
        polygon_apothem(SHIELD_OUTER_RADIUS) - required_outer_shield_radius()
    )
    center_overlap = (
        polygon_apothem(CENTER_BLOCKER_RADIUS) - required_center_blocker_radius()
    )
    if min(outer_overlap, center_overlap) < MINIMUM_ACOUSTIC_OVERLAP:
        raise RuntimeError("Tolerance-adjusted acoustic overlap is below its reserve")
    print(
        "COMMON_REGISTRATION PASS "
        f"sleeve_clearance_per_side={STACK_SLEEVE_CLEARANCE_PER_SIDE:.2f}mm "
        f"fan_pocket_clearance_per_side="
        f"{FAN_FRAME_POCKET_CLEARANCE_PER_SIDE:.2f}mm "
        f"relative_print_allowance={PRINT_DATUM_RELATIVE_ALLOWANCE:.2f}mm "
        f"fan_to_stack_offset={fan_to_stack_max_offset():.2f}mm "
        f"stack_relative_offset={stack_max_relative_offset():.2f}mm "
        f"outer_overlap={outer_overlap:.2f}mm center_overlap={center_overlap:.2f}mm"
    )
    print(
        "FAN_INTERFACE PASS "
        f"nominal_fan={FAN_NOMINAL_SIZE:.0f}mm "
        f"reference={FAN_REFERENCE.replace(' ', '_')} "
        f"fan_depth={FAN_PRESET_DEPTH:.1f}mm "
        f"outer_size={OUTER_SIZE:.1f}mm "
        f"sleeve_outer={sleeve_outer_size():.1f}mm "
        f"hole_pattern={FAN_HOLE_SPACING:.1f}mm_square "
        f"bolt_holes={FAN_BOLT_HOLE_DIAMETER:.1f}mm "
        f"through_bolts=M{THROUGH_BOLT_DIAMETER:g} "
        f"airflow_opening={FAN_OPENING_DIAMETER:.1f}mm "
        f"worst_interface_offset={interface_offset:.2f}mm "
        f"interface_airway_overlap={interface_overlap_ratio:.1%} "
        f"added_stack_depth={total_assembly_depth():.1f}mm"
    )


def object_world_bounds(obj):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return tuple(
        (
            min(corner[axis] for corner in corners),
            max(corner[axis] for corner in corners),
        )
        for axis in range(3)
    )


def validate_common_sleeve_registration(components) -> None:
    """Require every sandwich layer to touch the common square datum."""
    expected = (-OUTER_SIZE / 2.0, OUTER_SIZE / 2.0)
    located_parts = components[:-1]
    for obj in located_parts:
        bounds = object_world_bounds(obj)
        for axis in (0, 2):
            if not all(
                math.isclose(actual, target, abs_tol=0.001)
                for actual, target in zip(bounds[axis], expected)
            ):
                raise RuntimeError(
                    f"{obj.name} does not reach the common sleeve datum on "
                    f"axis {axis}: bounds={bounds[axis]} expected={expected}"
                )
    print(
        "SLEEVE_DATUM_EXTENTS PASS "
        f"located_parts={len(located_parts)} square_size={OUTER_SIZE:.2f}mm"
    )


def validate_print_copies(objects) -> None:
    bounds = [object_world_bounds(obj) for obj in objects]
    for obj, obj_bounds in zip(objects, bounds):
        if obj_bounds[2][0] < -0.001:
            raise RuntimeError(f"{obj.name} extends below the print bed")
        if obj_bounds[2][0] > 0.001:
            raise RuntimeError(
                f"{obj.name} floats {obj_bounds[2][0]:.3f} mm above the print bed"
            )
    for first_index, first in enumerate(bounds):
        for second_index in range(first_index + 1, len(bounds)):
            second = bounds[second_index]
            overlap_x = min(first[0][1], second[0][1]) - max(first[0][0], second[0][0])
            overlap_y = min(first[1][1], second[1][1]) - max(first[1][0], second[1][0])
            if overlap_x > 0.001 and overlap_y > 0.001:
                raise RuntimeError(
                    "Print-bed parts overlap in XY: "
                    f"{objects[first_index].name} and {objects[second_index].name}"
                )
    print("PRINT_LAYOUT PASS parts=8 supports=none_required")


# ---------------------------------------------------------------------------
# Layout and export


def position_axial_part_for_print(obj, x: float, y: float, source_depth: float) -> None:
    obj.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
    obj.location = (x, y, source_depth / 2.0)


def position_curved_baffle_for_print(obj, x: float, y: float) -> None:
    obj.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
    obj.location = (x, y, BAFFLE_PLATE_THICKNESS / 2.0)


def position_alignment_sleeve_for_print(obj, x: float, y: float) -> None:
    obj.rotation_euler = (-math.pi / 2.0, 0.0, 0.0)
    obj.location = (x, y, case_face_y())


def arrange_print_set(
    flange_1,
    flange_2,
    spacer_1,
    spacer_2,
    spacer_3,
    curved_baffle,
    center_baffle,
    alignment_sleeve,
):
    pitch = OUTER_SIZE + PRINT_PART_GAP
    position_axial_part_for_print(flange_1, -pitch, pitch, FLANGE_THICKNESS)
    position_axial_part_for_print(spacer_1, 0.0, pitch, SPACER_DEPTH)
    position_curved_baffle_for_print(curved_baffle, pitch, pitch)
    position_axial_part_for_print(flange_2, -pitch, 0.0, FLANGE_THICKNESS)
    position_axial_part_for_print(spacer_2, 0.0, 0.0, SPACER_DEPTH)
    position_curved_baffle_for_print(center_baffle, pitch, 0.0)
    position_axial_part_for_print(spacer_3, 0.0, -pitch, SPACER_DEPTH)
    position_alignment_sleeve_for_print(alignment_sleeve, -pitch, -pitch)


def make_print_set(
    flange_source,
    spacer_source,
    baffle_source,
    center_baffle_source,
    alignment_sleeve_source,
):
    flange_1 = duplicate_object(flange_source, "Print_Flange_1")
    flange_2 = duplicate_object(flange_source, "Print_Flange_2")
    spacer_1 = duplicate_object(spacer_source, "Print_Spacer_1")
    spacer_2 = duplicate_object(spacer_source, "Print_Spacer_2")
    spacer_3 = duplicate_object(spacer_source, "Print_Spacer_3")
    curved_baffle = duplicate_object(baffle_source, "Print_Curved_Baffle")
    center_baffle = duplicate_object(center_baffle_source, "Print_Center_Baffle")
    alignment_sleeve = duplicate_object(
        alignment_sleeve_source,
        "Print_Alignment_Sleeve",
    )
    copies = (
        flange_1,
        flange_2,
        spacer_1,
        spacer_2,
        spacer_3,
        curved_baffle,
        center_baffle,
        alignment_sleeve,
    )
    arrange_print_set(*copies)
    bpy.context.view_layer.update()
    validate_print_copies(copies)
    return copies


def apply_scene_layout(components) -> None:
    if LAYOUT_MODE == "assembled":
        return
    (
        flange_case,
        flange_fan,
        spacer_case,
        spacer_middle,
        spacer_fan,
        curved_baffle,
        center_baffle,
        alignment_sleeve,
    ) = components
    arrange_print_set(
        flange_case,
        flange_fan,
        spacer_case,
        spacer_middle,
        spacer_fan,
        curved_baffle,
        center_baffle,
        alignment_sleeve,
    )


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
        raise RuntimeError("No STL exporter is available")
    print(f"Wrote {path}")


def remove_objects(objects) -> None:
    names = tuple(obj.name for obj in objects)
    for name in names:
        obj = bpy.data.objects.get(name)
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)


def export_printable_stls(
    flange_source,
    spacer_source,
    baffle_source,
    center_baffle_source,
    alignment_sleeve_source,
) -> None:
    output = export_base_directory()
    if EXPORT_COMBINED_STL:
        print_set = make_print_set(
            flange_source,
            spacer_source,
            baffle_source,
            center_baffle_source,
            alignment_sleeve_source,
        )
        try:
            export_stl(output / COMBINED_STL_NAME, print_set)
        finally:
            remove_objects(print_set)

    if EXPORT_SEPARATE_STLS:
        flange = duplicate_object(flange_source, "Export_Flange")
        position_axial_part_for_print(flange, 0.0, 0.0, FLANGE_THICKNESS)
        try:
            export_stl(output / FLANGE_STL_NAME, (flange,))
        finally:
            remove_objects((flange,))

        spacer = duplicate_object(spacer_source, "Export_Spacer")
        position_axial_part_for_print(spacer, 0.0, 0.0, SPACER_DEPTH)
        try:
            export_stl(output / SPACER_STL_NAME, (spacer,))
        finally:
            remove_objects((spacer,))

        curved_baffle = duplicate_object(baffle_source, "Export_Curved_Baffle")
        position_curved_baffle_for_print(curved_baffle, 0.0, 0.0)
        try:
            export_stl(output / CURVED_BAFFLE_STL_NAME, (curved_baffle,))
        finally:
            remove_objects((curved_baffle,))

        center_baffle = duplicate_object(center_baffle_source, "Export_Center_Baffle")
        position_curved_baffle_for_print(center_baffle, 0.0, 0.0)
        try:
            export_stl(output / CENTER_BAFFLE_STL_NAME, (center_baffle,))
        finally:
            remove_objects((center_baffle,))

        alignment_sleeve = duplicate_object(
            alignment_sleeve_source,
            "Export_Alignment_Sleeve",
        )
        position_alignment_sleeve_for_print(alignment_sleeve, 0.0, 0.0)
        try:
            export_stl(output / ALIGNMENT_SLEEVE_STL_NAME, (alignment_sleeve,))
        finally:
            remove_objects((alignment_sleeve,))


def build_gopro_fan_silencer():
    apply_fan_size_config()
    validate_config()
    validate_case_interface()
    validate_blade_to_case_sound_paths()
    configure_scene()
    components = build_components()
    bpy.context.view_layer.update()
    validate_common_sleeve_registration(components)

    # Copies share meshes, so validate each unique printable mesh once.
    validate_object(components[0])
    validate_object(components[2])
    validate_object(components[5])
    validate_object(components[6])
    validate_object(components[7])
    validate_assembled_fit(components)
    validate_interfaces()

    annular_area = annular_baffle_open_area()
    center_area = center_baffle_open_area()
    first_turn_area = first_curved_turn_area()
    second_turn_area = second_curved_turn_area()
    minimum_area = min(
        annular_area,
        center_area,
        first_turn_area,
        second_turn_area,
    )
    print(
        "CURVED_AIRWAY_AREA PASS "
        f"annular_plane={annular_area:.1f}mm2 "
        f"center_plane={center_area:.1f}mm2 "
        f"first_curved_turn={first_turn_area:.1f}mm2 "
        f"second_curved_turn={second_turn_area:.1f}mm2 "
        f"minimum={minimum_area:.1f}mm2 "
        f"fan_opening={fan_opening_area():.1f}mm2 "
        f"ratio={minimum_area / fan_opening_area():.1%}"
    )
    print(
        "ASSEMBLY print_quantity=2x_flange+3x_spacer+"
        "1x_annular_baffle+1x_center_baffle+1x_alignment_sleeve "
        f"bolt_length_increase={total_assembly_depth():.1f}mm "
        "both_raised_F_cup_faces=fan seal=thin_foam_optional"
    )
    if CASE_INTERFACE_ACTIVE:
        print(
            "INSTALLATION external_silencer_replaces_internal_baffle_cartridge; "
            "do_not_stack_without_measured_airflow"
        )
    else:
        print("INSTALLATION standard_square_fan_sandwich")

    if EXPORT_STL:
        export_printable_stls(
            components[0],
            components[2],
            components[5],
            components[6],
            components[7],
        )
    apply_scene_layout(components)
    return components


if __name__ == "__main__":
    build_gopro_fan_silencer()
