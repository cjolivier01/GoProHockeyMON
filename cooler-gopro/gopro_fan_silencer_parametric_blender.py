"""Parametric, support-accessible silencer for the case's 40 mm fan.

Run inside Blender:

    blender --background --python gopro_fan_silencer_parametric_blender.py

The silencer bolts between ``gopro_fan_case_parametric_blender.py`` and its
40 mm fan.  It uses the same 32 mm square M3 pattern and 37 mm airflow opening
on both faces.  Three widely spaced alternating baffles remove the direct
fan-to-case sound path while retaining a continuous S-shaped airway.

This external silencer is an alternative to the removable acoustic cartridge
enabled by ``BAFFLE_CARTRIDGE_ENABLED`` in the case generator.  Do not install
both restrictions in series unless measured airflow or the selected fan's
pressure/flow curve has verified that configuration.

The assembly deliberately has only two unique printable parts:

* print two flanges with a broad face on the bed; and
* print two core halves with the smooth outside wall on the bed and the open
  acoustic channel facing up.

The core halves are identical: rotate one 180 degrees around the airflow axis
for assembly.  All airway faces therefore remain exposed for inspection and
cleanup until the four long M3 fan bolts clamp the sandwich together.  No
internal supports are required.  The only horizontal bridge in the suggested
orientation is the 3.6 mm roof of each straight, end-accessible bolt bore.

The acoustic approach is an original parametric implementation inspired by
the direct-sound blocking principle described at:
https://www.thingiverse.com/thing:5177333/comments

All dimensions are millimeters.

Axes in assembled coordinates:
    X - fan width; the reusable core half occupies X >= 0
    Y - airflow and bolt direction, from the fan toward the case
    Z - fan height
"""

from __future__ import annotations

import math
import ast
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


# ---------------------------------------------------------------------------
# CONFIG

CLEAR_SCENE = True
LAYOUT_MODE = "assembled"  # "assembled" or "print_bed"

EXPORT_STL = False
EXPORT_DIRECTORY = ""
EXPORT_COMBINED_STL = True
EXPORT_SEPARATE_STLS = True
COMBINED_STL_NAME = "gopro_40mm_fan_silencer.stl"
FLANGE_STL_NAME = "gopro_40mm_fan_silencer_flange.stl"
CORE_HALF_STL_NAME = "gopro_40mm_fan_silencer_core_half.stl"

# Both faces match the rear fan interface in the parametric GoPro case.
FAN_NOMINAL_SIZE = 40.0
FAN_OPENING_DIAMETER = 37.0
FAN_HOLE_SPACING = 32.0
FAN_BOLT_HOLE_DIAMETER = 3.6

# The 43 mm envelope leaves 1 mm per side on the case's 45 mm rear fan pad and
# overhangs a nominal 40 mm fan by 1.5 mm per side.
OUTER_SIZE = 43.0
FLANGE_THICKNESS = 2.0
CORE_DEPTH = 37.0
CORE_OUTER_WALL = 1.30
CORE_TOP_BOTTOM_WALL = 1.30
CORNER_BOSS_SIZE = 5.8
CORNER_BOSS_WEB_WIDTH = 1.2
CORNER_BOSS_WEB_OVERLAP = 0.1
MINIMUM_CASE_PAD_MARGIN = 0.75

# The identical core halves self-key at the center seam.  A tongue on each
# positive-Z acoustic surface enters the negative-Z groove of the rotated mate;
# the same arrangement seals the upper/lower perimeter walls.  This keeps the
# seam from becoming a narrow direct-sound bypass despite bolt-hole clearance.
SEAM_TONGUE_DEPTH = 0.9
SEAM_TONGUE_ROOT_OVERLAP = 0.15
SEAM_FIT_CLEARANCE = 0.20
SEAM_EDGE_INSET = 0.30

# Three widely spaced alternating blockers force two changes of vertical
# direction.  The 9.1 mm clear gap between blockers keeps each transverse turn
# above the same 65% open-area floor used for their axial openings.
BAFFLE_THICKNESS = 1.4
BAFFLE_CENTERS_Y = (-10.5, 0.0, 10.5)
BAFFLE_TYPES = ("CENTER", "OUTER", "CENTER")
CENTER_BLOCKER_HALF_HEIGHT = 9.60
OUTER_BLOCKER_OPENING_HALF_HEIGHT = 9.15
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

# Boolean and mesh quality.
CYLINDER_SEGMENTS = 96
BOOLEAN_SOLVER = "EXACT"
BOOLEAN_CLEANUP_DISTANCE = 0.0001
BOOLEAN_MINIMUM_VOLUME_CHANGE = 1.0e-6

# Print-bed spacing used by the combined STL and optional scene layout.
PRINT_PART_GAP = 4.0


# ---------------------------------------------------------------------------
# Derived dimensions and validation


def total_assembly_depth() -> float:
    return CORE_DEPTH + 2.0 * FLANGE_THICKNESS


def cavity_half_height() -> float:
    return OUTER_SIZE / 2.0 - CORE_TOP_BOTTOM_WALL


def cavity_width() -> float:
    # The two halves meet at X=0; each retains only its outside wall.
    return OUTER_SIZE - 2.0 * CORE_OUTER_WALL


def corner_obstruction_rectangles():
    """Return full-assembly bolt-tower/web projections in the XZ plane."""
    hole_center = FAN_HOLE_SPACING / 2.0
    boss_half = CORNER_BOSS_SIZE / 2.0
    web_half = CORNER_BOSS_WEB_WIDTH / 2.0
    cavity_x_half = cavity_width() / 2.0
    cavity_z_half = cavity_half_height()
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
                    cavity_x_half,
                )
            else:
                x_web = (
                    -cavity_x_half,
                    x - boss_half + CORNER_BOSS_WEB_OVERLAP,
                )
            rectangles.append((x_web[0], x_web[1], z - web_half, z + web_half))
            if z_sign > 0.0:
                z_web = (
                    z + boss_half - CORNER_BOSS_WEB_OVERLAP,
                    cavity_z_half,
                )
            else:
                z_web = (
                    -cavity_z_half,
                    z - boss_half + CORNER_BOSS_WEB_OVERLAP,
                )
            rectangles.append((x - web_half, x + web_half, z_web[0], z_web[1]))
    return tuple(rectangles)


def rectangle_union_area_in_opening(rectangles, z_ranges) -> float:
    """Measure rectangle-union area clipped to the rectangular air lanes."""
    cavity_x_half = cavity_width() / 2.0
    cavity_z_half = cavity_half_height()
    clipped = []
    for x0, x1, z0, z1 in rectangles:
        x0 = max(-cavity_x_half, x0)
        x1 = min(cavity_x_half, x1)
        z0 = max(-cavity_z_half, z0)
        z1 = min(cavity_z_half, z1)
        if x1 > x0 and z1 > z0:
            clipped.append((x0, x1, z0, z1))
    x_edges = sorted(
        {
            -cavity_x_half,
            cavity_x_half,
            *(value for rect in clipped for value in rect[:2]),
        }
    )
    z_edges = sorted(
        {
            *(value for z_range in z_ranges for value in z_range),
            *(value for rect in clipped for value in rect[2:]),
        }
    )
    area = 0.0
    for x0, x1 in zip(x_edges, x_edges[1:]):
        sample_x = (x0 + x1) / 2.0
        for z0, z1 in zip(z_edges, z_edges[1:]):
            sample_z = (z0 + z1) / 2.0
            if not any(low <= sample_z <= high for low, high in z_ranges):
                continue
            if any(
                rx0 <= sample_x <= rx1 and rz0 <= sample_z <= rz1
                for rx0, rx1, rz0, rz1 in clipped
            ):
                area += (x1 - x0) * (z1 - z0)
    return area


def axial_airway_area(kind: str) -> float:
    cavity_half = cavity_half_height()
    if kind == "CENTER":
        z_ranges = (
            (-cavity_half, -CENTER_BLOCKER_HALF_HEIGHT),
            (CENTER_BLOCKER_HALF_HEIGHT, cavity_half),
        )
    elif kind == "OUTER":
        z_ranges = (
            (
                -OUTER_BLOCKER_OPENING_HALF_HEIGHT,
                OUTER_BLOCKER_OPENING_HALF_HEIGHT,
            ),
        )
    else:
        raise ValueError(f"Unsupported baffle type {kind!r}")
    nominal_area = cavity_width() * sum(high - low for low, high in z_ranges)
    obstruction_area = rectangle_union_area_in_opening(
        corner_obstruction_rectangles(), z_ranges
    )
    return nominal_area - obstruction_area


def minimum_turn_area() -> float:
    turn_areas = []
    for previous, current in zip(BAFFLE_CENTERS_Y, BAFFLE_CENTERS_Y[1:]):
        clear_gap = current - previous - BAFFLE_THICKNESS
        # Every CENTER/OUTER transition turns around two blocker edges.
        turn_areas.append(2.0 * cavity_width() * clear_gap)
    return min(turn_areas) if turn_areas else math.inf


def minimum_airway_area() -> float:
    axial_areas = {axial_airway_area(kind) for kind in set(BAFFLE_TYPES)}
    return min(*axial_areas, minimum_turn_area())


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
    print(
        "CASE_INTERFACE_SOURCE PASS "
        f"source={case_generator_path().name} pad_margin={pad_margin:.2f}mm "
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
        raise ValueError("The M3 bolt holes need positive print clearance")
    hole_center = FAN_HOLE_SPACING / 2.0
    outer_half = OUTER_SIZE / 2.0
    if hole_center + FAN_BOLT_HOLE_DIAMETER / 2.0 >= outer_half:
        raise ValueError("Fan bolt holes break through the outside edge")
    if CORNER_BOSS_SIZE <= FAN_BOLT_HOLE_DIAMETER + 2.0:
        raise ValueError("Corner bosses leave too little radial bolt material")
    boss_outer_edge = hole_center + CORNER_BOSS_SIZE / 2.0
    if boss_outer_edge >= outer_half:
        raise ValueError("Corner bosses break through the configured envelope")
    if boss_outer_edge >= outer_half - CORE_OUTER_WALL:
        raise ValueError("Corner bosses leave no open length for their wall webs")
    if CORNER_BOSS_WEB_WIDTH <= 0.0:
        raise ValueError("Corner-boss wall webs need positive width")
    if not 0.0 < CORNER_BOSS_WEB_OVERLAP < CORNER_BOSS_SIZE / 2.0:
        raise ValueError("Corner-boss web overlap must enter each boss")
    if cavity_half_height() <= CENTER_BLOCKER_HALF_HEIGHT:
        raise ValueError("Center blockers close the upper and lower air lanes")
    if OUTER_BLOCKER_OPENING_HALF_HEIGHT >= CENTER_BLOCKER_HALF_HEIGHT:
        raise ValueError("Alternating baffles need positive projected overlap")
    if len(BAFFLE_CENTERS_Y) != len(BAFFLE_TYPES):
        raise ValueError("Every baffle center needs a baffle type")
    if len(BAFFLE_CENTERS_Y) < 2:
        raise ValueError("The acoustic path needs at least two blockers")
    if SEAM_TONGUE_DEPTH <= 2.0 * SEAM_TONGUE_ROOT_OVERLAP:
        raise ValueError("Seam tongues need useful engagement beyond the root")
    if SEAM_TONGUE_DEPTH + SEAM_FIT_CLEARANCE >= OUTER_SIZE / 4.0:
        raise ValueError("Seam keys are unreasonably deep for the core half")
    if SEAM_EDGE_INSET < 0.0:
        raise ValueError("SEAM_EDGE_INSET cannot be negative")
    if 2.0 * SEAM_EDGE_INSET >= CORE_TOP_BOTTOM_WALL:
        raise ValueError("SEAM_EDGE_INSET removes the perimeter seam tongue")
    if tuple(sorted(BAFFLE_CENTERS_Y)) != BAFFLE_CENTERS_Y:
        raise ValueError("BAFFLE_CENTERS_Y must be strictly ordered")
    for index, (center, kind) in enumerate(zip(BAFFLE_CENTERS_Y, BAFFLE_TYPES)):
        if kind not in {"CENTER", "OUTER"}:
            raise ValueError(f"Unsupported baffle type at index {index}: {kind}")
        if abs(center) + BAFFLE_THICKNESS / 2.0 >= CORE_DEPTH / 2.0:
            raise ValueError(f"Baffle {index} does not fit within the core")
    for previous, current in zip(BAFFLE_CENTERS_Y, BAFFLE_CENTERS_Y[1:]):
        if current - previous <= BAFFLE_THICKNESS:
            raise ValueError("Adjacent baffles need a positive axial passage")
    for previous, current in zip(BAFFLE_TYPES, BAFFLE_TYPES[1:]):
        if previous == current:
            raise ValueError("Adjacent baffles must alternate opening types")

    fan_area = math.pi * (FAN_OPENING_DIAMETER / 2.0) ** 2
    open_ratio = minimum_airway_area() / fan_area
    if open_ratio < MINIMUM_AIRWAY_TO_FAN_AREA_RATIO:
        raise ValueError(
            f"Minimum airway area is only {open_ratio:.1%} of the fan opening"
        )


def ray_hits_baffle(inlet_z: float, outlet_z: float, baffle_y: float, kind: str):
    half_depth = total_assembly_depth() / 2.0
    fraction = (baffle_y + half_depth) / (2.0 * half_depth)
    ray_z = inlet_z + (outlet_z - inlet_z) * fraction
    if kind == "CENTER":
        return abs(ray_z) <= CENTER_BLOCKER_HALF_HEIGHT
    return abs(ray_z) >= OUTER_BLOCKER_OPENING_HALF_HEIGHT


def validate_sampled_line_of_sight() -> None:
    """Reject any densely sampled straight ray through all configured baffles."""
    radius = FAN_OPENING_DIAMETER / 2.0
    sample_count = 297
    samples = [
        -radius + 2.0 * radius * index / (sample_count - 1)
        for index in range(sample_count)
    ]
    tested = 0
    for inlet_z in samples:
        for outlet_z in samples:
            tested += 1
            if not any(
                ray_hits_baffle(inlet_z, outlet_z, center, kind)
                for center, kind in zip(BAFFLE_CENTERS_Y, BAFFLE_TYPES)
            ):
                raise RuntimeError(
                    "A sampled straight sound path bypasses every baffle: "
                    f"inlet_z={inlet_z:.3f}, outlet_z={outlet_z:.3f}"
                )
    print(
        "ACOUSTIC_LINE_OF_SIGHT PASS "
        f"sampled_rays={tested} baffles={len(BAFFLE_CENTERS_Y)}"
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


def add_box(
    name: str, x0: float, x1: float, y0: float, y1: float, z0: float, z1: float
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
    # Bake bounds into mesh coordinates so mirrored assembly copies rotate
    # around the fan center and print-layout transforms can place Z=0 exactly.
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=True)
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


# ---------------------------------------------------------------------------
# Printable geometry


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
    hole_center = FAN_HOLE_SPACING / 2.0
    for x in (-hole_center, hole_center):
        for z in (-hole_center, hole_center):
            cutters.append(
                add_cylinder_y(
                    "Flange_M3_Cutter",
                    FAN_BOLT_HOLE_DIAMETER / 2.0,
                    -depth_half - 0.2,
                    depth_half + 0.2,
                    x=x,
                    z=z,
                )
            )
    boolean_difference(flange, cutters, "Cut_Flange_Openings")
    flange.name = "GoPro_40mm_Fan_Silencer_Flange_Front"
    return flange


def cavity_y_sections():
    """Yield (y0, y1, opening kind) for every core interval."""
    cursor = -CORE_DEPTH / 2.0
    for center, kind in zip(BAFFLE_CENTERS_Y, BAFFLE_TYPES):
        baffle_y0 = center - BAFFLE_THICKNESS / 2.0
        baffle_y1 = center + BAFFLE_THICKNESS / 2.0
        if baffle_y0 > cursor:
            yield cursor, baffle_y0, "FULL"
        yield baffle_y0, baffle_y1, kind
        cursor = baffle_y1
    if cursor < CORE_DEPTH / 2.0:
        yield cursor, CORE_DEPTH / 2.0, "FULL"


def create_core_cavity_cutters():
    half = OUTER_SIZE / 2.0
    cavity_x1 = half - CORE_OUTER_WALL + 0.02
    cavity_z = cavity_half_height()
    cutters = []
    for index, (y0, y1, kind) in enumerate(cavity_y_sections()):
        # Extend the end intervals through the open front/rear faces.
        if math.isclose(y0, -CORE_DEPTH / 2.0):
            y0 -= 0.2
        if math.isclose(y1, CORE_DEPTH / 2.0):
            y1 += 0.2
        if kind == "FULL":
            z_ranges = ((-cavity_z, cavity_z),)
        elif kind == "CENTER":
            z_ranges = (
                (-cavity_z, -CENTER_BLOCKER_HALF_HEIGHT),
                (CENTER_BLOCKER_HALF_HEIGHT, cavity_z),
            )
        else:
            z_ranges = (
                (
                    -OUTER_BLOCKER_OPENING_HALF_HEIGHT,
                    OUTER_BLOCKER_OPENING_HALF_HEIGHT,
                ),
            )
        for range_index, (z0, z1) in enumerate(z_ranges):
            cutters.append(
                add_box(
                    f"Core_Air_{index}_{range_index}",
                    -0.2,
                    cavity_x1,
                    y0,
                    y1,
                    z0,
                    z1,
                )
            )
    return cutters


def seam_feature_ranges(kind: str):
    """Return matching positive tongue and negative groove Z ranges."""
    if kind == "CENTER":
        tongue = (0.0, CENTER_BLOCKER_HALF_HEIGHT)
    else:
        tongue = (
            OUTER_BLOCKER_OPENING_HALF_HEIGHT,
            cavity_half_height(),
        )
    # A 180-degree rotation around Y maps positive Z to negative Z.
    groove = (-tongue[1], -tongue[0])
    return tongue, groove


def add_core_seam_keys(core) -> None:
    """Add support-free complementary keys to one reusable core half."""
    half = OUTER_SIZE / 2.0
    fit_half = SEAM_FIT_CLEARANCE / 2.0
    tongue_x0 = -SEAM_TONGUE_DEPTH
    tongue_x1 = SEAM_TONGUE_ROOT_OVERLAP
    groove_x1 = SEAM_TONGUE_DEPTH + SEAM_FIT_CLEARANCE

    # Seal and locate the upper/lower outside-wall seams between baffles.
    perimeter_tongue_z = (
        cavity_half_height() + SEAM_EDGE_INSET,
        half - SEAM_EDGE_INSET,
    )
    perimeter_groove_z = (
        -perimeter_tongue_z[1] - fit_half,
        -perimeter_tongue_z[0] + fit_half,
    )
    groove = add_box(
        "Core_Perimeter_Seam_Groove",
        -0.2,
        groove_x1,
        -CORE_DEPTH / 2.0 + SEAM_EDGE_INSET - fit_half,
        CORE_DEPTH / 2.0 - SEAM_EDGE_INSET + fit_half,
        perimeter_groove_z[0],
        perimeter_groove_z[1],
    )
    apply_boolean(
        core,
        groove,
        "DIFFERENCE",
        "Cut_Core_Perimeter_Seam_Groove",
    )
    tongue = add_box(
        "Core_Perimeter_Seam_Tongue",
        tongue_x0,
        tongue_x1,
        -CORE_DEPTH / 2.0 + SEAM_EDGE_INSET,
        CORE_DEPTH / 2.0 - SEAM_EDGE_INSET,
        perimeter_tongue_z[0],
        perimeter_tongue_z[1],
    )
    boolean_union(core, tongue, "Union_Core_Perimeter_Seam_Tongue")

    # Continue that overlapping joint across every internal blocker.  The keys
    # reach each airway edge so ordinary FDM seam roughness cannot align a
    # straight crack through alternating blockers.
    tongue_y_half = BAFFLE_THICKNESS / 2.0 - SEAM_TONGUE_ROOT_OVERLAP
    groove_y_half = tongue_y_half + fit_half
    for index, (center, kind) in enumerate(zip(BAFFLE_CENTERS_Y, BAFFLE_TYPES)):
        tongue_z, groove_z = seam_feature_ranges(kind)
        groove = add_box(
            f"Core_Baffle_Seam_Groove_{index}",
            -0.2,
            groove_x1,
            center - groove_y_half,
            center + groove_y_half,
            groove_z[0] - fit_half,
            groove_z[1] + fit_half,
        )
        apply_boolean(
            core,
            groove,
            "DIFFERENCE",
            f"Cut_Core_Baffle_Seam_Groove_{index}",
        )
        tongue = add_box(
            f"Core_Baffle_Seam_Tongue_{index}",
            tongue_x0,
            tongue_x1,
            center - tongue_y_half,
            center + tongue_y_half,
            tongue_z[0],
            tongue_z[1],
        )
        boolean_union(
            core,
            tongue,
            f"Union_Core_Baffle_Seam_Tongue_{index}",
        )


def create_core_half():
    half = OUTER_SIZE / 2.0
    core = add_box(
        "Silencer_Core_Half_Blank",
        0.0,
        half,
        -CORE_DEPTH / 2.0,
        CORE_DEPTH / 2.0,
        -half,
        half,
    )
    # Adjacent airway boxes deliberately share faces at the baffle boundaries.
    # Applying each closed cutter independently avoids asking Blender's Exact
    # solver to interpret those touching boxes as one self-intersecting tool.
    for index, cutter in enumerate(create_core_cavity_cutters()):
        apply_boolean(
            core,
            cutter,
            "DIFFERENCE",
            f"Cut_Core_Airway_{index}",
        )
    add_core_seam_keys(core)

    # Restore slim printable bolt towers after the airway cut.  Narrow radial
    # webs connect each tower to both adjacent shell walls without letting the
    # fastener structure dominate the upper/lower acoustic lanes.
    hole_center = FAN_HOLE_SPACING / 2.0
    boss_half = CORNER_BOSS_SIZE / 2.0
    web_half = CORNER_BOSS_WEB_WIDTH / 2.0
    for index, z in enumerate((-hole_center, hole_center)):
        boss = add_box(
            f"Core_Corner_Boss_{index}",
            hole_center - boss_half,
            hole_center + boss_half,
            -CORE_DEPTH / 2.0,
            CORE_DEPTH / 2.0,
            z - boss_half,
            z + boss_half,
        )
        boolean_union(core, boss, f"Union_Core_Corner_Boss_{index}")
        side_web = add_box(
            f"Core_Corner_Side_Web_{index}",
            hole_center + boss_half - CORNER_BOSS_WEB_OVERLAP,
            half,
            -CORE_DEPTH / 2.0,
            CORE_DEPTH / 2.0,
            z - web_half,
            z + web_half,
        )
        boolean_union(core, side_web, f"Union_Core_Side_Web_{index}")
        if z > 0.0:
            z0 = z + boss_half - CORNER_BOSS_WEB_OVERLAP
            z1 = half
        else:
            z0 = -half
            z1 = z - boss_half + CORNER_BOSS_WEB_OVERLAP
        top_bottom_web = add_box(
            f"Core_Corner_Top_Bottom_Web_{index}",
            hole_center - web_half,
            hole_center + web_half,
            -CORE_DEPTH / 2.0,
            CORE_DEPTH / 2.0,
            z0,
            z1,
        )
        boolean_union(
            core,
            top_bottom_web,
            f"Union_Core_Top_Bottom_Web_{index}",
        )

    bolt_cutters = [
        add_cylinder_y(
            f"Core_M3_Cutter_{index}",
            FAN_BOLT_HOLE_DIAMETER / 2.0,
            -CORE_DEPTH / 2.0 - 0.2,
            CORE_DEPTH / 2.0 + 0.2,
            x=hole_center,
            z=z,
        )
        for index, z in enumerate((-hole_center, hole_center))
    ]
    boolean_difference(core, bolt_cutters, "Cut_Core_M3_Bores")
    core.name = "GoPro_40mm_Fan_Silencer_Core_Half_Right"
    return core


def duplicate_object(source, name: str, copy_mesh=False):
    duplicate = source.copy()
    duplicate.data = source.data.copy() if copy_mesh else source.data
    bpy.context.collection.objects.link(duplicate)
    duplicate.name = name
    return duplicate


def build_components():
    flange_front = create_flange()
    flange_rear = duplicate_object(flange_front, "GoPro_40mm_Fan_Silencer_Flange_Rear")
    core_right = create_core_half()
    core_left = duplicate_object(core_right, "GoPro_40mm_Fan_Silencer_Core_Half_Left")

    flange_offset = CORE_DEPTH / 2.0 + FLANGE_THICKNESS / 2.0
    flange_front.location.y = flange_offset
    flange_rear.location.y = -flange_offset
    core_left.rotation_euler.y = math.pi
    return flange_front, flange_rear, core_right, core_left


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
    """Reject core-key or core/flange assembled-volume interference."""
    flange_front, flange_rear, core_right, core_left = components
    pairs = (
        (core_right, core_left, "Core_Seam_Fit"),
        (core_right, flange_front, "Right_Core_Front_Flange_Fit"),
        (core_right, flange_rear, "Right_Core_Rear_Flange_Fit"),
        (core_left, flange_front, "Left_Core_Front_Flange_Fit"),
        (core_left, flange_rear, "Left_Core_Rear_Flange_Fit"),
    )
    intersections = {
        label: world_intersection_volume(first, second, label)
        for first, second, label in pairs
    }
    maximum = max(intersections.values())
    if maximum > 0.001:
        raise RuntimeError(f"Assembled components interfere: {intersections}")
    print(
        "ASSEMBLED_FIT PASS "
        f"maximum_boolean_interference={maximum:.9f}mm3 "
        f"seam_clearance={SEAM_FIT_CLEARANCE:.2f}mm"
    )


def validate_interfaces() -> None:
    flange_web = (
        math.hypot(FAN_HOLE_SPACING / 2.0, FAN_HOLE_SPACING / 2.0)
        - FAN_OPENING_DIAMETER / 2.0
        - FAN_BOLT_HOLE_DIAMETER / 2.0
    )
    if flange_web < 2.0:
        raise RuntimeError(f"Only {flange_web:.2f} mm remains between openings")
    print(
        "FAN_INTERFACE PASS "
        f"nominal_fan={FAN_NOMINAL_SIZE:.0f}mm "
        f"hole_pattern={FAN_HOLE_SPACING:.1f}mm_square "
        f"bolt_holes={FAN_BOLT_HOLE_DIAMETER:.1f}mm "
        f"airflow_opening={FAN_OPENING_DIAMETER:.1f}mm "
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
    print("PRINT_LAYOUT PASS parts=4 supports=none_required")


# ---------------------------------------------------------------------------
# Layout and export


def position_flange_for_print(obj, x: float, y: float) -> None:
    obj.rotation_euler = (math.pi / 2.0, 0.0, 0.0)
    obj.location = (x, y, FLANGE_THICKNESS / 2.0)


def position_core_for_print(obj, x: float, y: float) -> None:
    # +90 degrees maps the smooth X=OUTER_SIZE/2 wall to Z=0 and leaves the
    # open half-channel facing upward for support-free printing.
    obj.rotation_euler = (0.0, math.pi / 2.0, 0.0)
    obj.location = (x, y, OUTER_SIZE / 2.0)


def print_row_centers_y():
    row_separation = (OUTER_SIZE + CORE_DEPTH) / 2.0 + PRINT_PART_GAP
    return row_separation / 2.0, -row_separation / 2.0


def make_print_set(flange_source, core_source):
    flange_left = duplicate_object(flange_source, "Print_Flange_1")
    flange_right = duplicate_object(flange_source, "Print_Flange_2")
    core_left = duplicate_object(core_source, "Print_Core_Half_1")
    core_right = duplicate_object(core_source, "Print_Core_Half_2")
    center_offset = (OUTER_SIZE + PRINT_PART_GAP) / 2.0
    flange_row_y, core_row_y = print_row_centers_y()
    position_flange_for_print(flange_left, -center_offset, flange_row_y)
    position_flange_for_print(flange_right, center_offset, flange_row_y)
    position_core_for_print(core_left, -center_offset, core_row_y)
    position_core_for_print(core_right, center_offset, core_row_y)
    copies = (flange_left, flange_right, core_left, core_right)
    bpy.context.view_layer.update()
    validate_print_copies(copies)
    return copies


def apply_scene_layout(components) -> None:
    if LAYOUT_MODE == "assembled":
        return
    flange_front, flange_rear, core_right, core_left = components
    center_offset = (OUTER_SIZE + PRINT_PART_GAP) / 2.0
    flange_row_y, core_row_y = print_row_centers_y()
    position_flange_for_print(flange_front, -center_offset, flange_row_y)
    position_flange_for_print(flange_rear, center_offset, flange_row_y)
    position_core_for_print(core_right, -center_offset, core_row_y)
    position_core_for_print(core_left, center_offset, core_row_y)


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
    for obj in objects:
        if bpy.data.objects.get(obj.name) is not None:
            bpy.data.objects.remove(obj, do_unlink=True)


def export_printable_stls(flange_source, core_source) -> None:
    output = export_base_directory()
    if EXPORT_COMBINED_STL:
        print_set = make_print_set(flange_source, core_source)
        try:
            export_stl(output / COMBINED_STL_NAME, print_set)
        finally:
            remove_objects(print_set)
    if EXPORT_SEPARATE_STLS:
        flange = duplicate_object(flange_source, "Export_Flange")
        position_flange_for_print(flange, 0.0, 0.0)
        try:
            export_stl(output / FLANGE_STL_NAME, (flange,))
        finally:
            remove_objects((flange,))

        core = duplicate_object(core_source, "Export_Core_Half")
        position_core_for_print(core, 0.0, 0.0)
        try:
            export_stl(output / CORE_HALF_STL_NAME, (core,))
        finally:
            remove_objects((core,))


def build_gopro_fan_silencer():
    validate_config()
    validate_case_interface()
    validate_sampled_line_of_sight()
    configure_scene()
    components = build_components()
    # Copies share meshes, so validate each unique printable mesh once.
    validate_object(components[0])
    validate_object(components[2])
    validate_assembled_fit(components)
    validate_interfaces()

    fan_area = math.pi * (FAN_OPENING_DIAMETER / 2.0) ** 2
    print(
        "AIRWAY_AREA PASS "
        f"center_axial={axial_airway_area('CENTER'):.1f}mm2 "
        f"outer_axial={axial_airway_area('OUTER'):.1f}mm2 "
        f"transverse_turn={minimum_turn_area():.1f}mm2 "
        f"minimum={minimum_airway_area():.1f}mm2 "
        f"fan_opening={fan_area:.1f}mm2 "
        f"ratio={minimum_airway_area() / fan_area:.1%}"
    )
    print(
        "ASSEMBLY print_quantity=2x_flange+2x_core_half "
        f"m3_length_increase={total_assembly_depth():.1f}mm "
        "seal=thin_closed_cell_foam_or_tape_optional"
    )
    print(
        "INSTALLATION external_silencer_replaces_internal_baffle_cartridge; "
        "do_not_stack_without_measured_airflow"
    )

    if EXPORT_STL:
        export_printable_stls(components[0], components[2])
    apply_scene_layout(components)
    return components


if __name__ == "__main__":
    build_gopro_fan_silencer()
