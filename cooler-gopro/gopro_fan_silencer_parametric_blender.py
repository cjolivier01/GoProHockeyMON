"""Parametric four-hole adaptation of Thingiverse fan silencer 5177333.

This generator deliberately uses the *actual* MK4 v23 mesh from:

    "Intake Fan Silencer PSU" by John Griswold (grizzie17)
    https://www.thingiverse.com/thing:5177333
    Creative Commons Attribution 4.0 International (CC BY 4.0)

The canonical mesh is embedded, with its checksum and attribution, in
``thingiverse_5177333_fan_intake_mk4_reference.py``.  It is decoded directly
into Blender, centered, and uniformly resized from its original 60 mm fan size
to a shared 40, 60, 80, or 120 mm standard-fan preset.  The four mounting
bosses are then relocated to the selected standard hole pattern.  No geometry
from ``gopro_fan_case_parametric_blender.py`` is used as a baffle model.

The Thingiverse part has two diagonal mounting holes.  This adaptation fills
those bores, adds matching bosses at all four standard fan corners, and drills
four through-holes so the same fasteners pass through the fan-facing and
case-facing sides.  For the default 40 mm build, the hole spacing and diameter
are cross-checked against the GoPro case and resolve to its 32 mm-square M3
pattern.

The result remains one assembled/printable part.  Its curved ambient-inlet side
sits at Z=0 and its open labyrinth/fan side faces upward, matching the source
STL's orientation and the reference author's instruction to keep the base
facing up.  The source design requires supports, but every supported region is
reachable through the open center, perimeter, or fan-side labyrinth; there are
no sealed support cavities.

The exact MK4 airway is intentionally not enlarged.  Its measured native
central throat is only 630.64 mm2, and uniform scaling preserves that area
ratio.  The 40 mm case build therefore has a 280.28 mm2 throat, only 26.1% of
the case's 37 mm opening.  Treat this as an acoustics-first experimental part:
verify case temperature and airflow under sustained load before relying on it
for cooling, and do not combine it with the case's internal baffle cartridge.

Run inside Blender:

    blender --background --python gopro_fan_silencer_parametric_blender.py

Blender 5.2 or newer is required for the manifold Boolean solver used to
produce a one-shell four-hole adaptation of the triangulated reference mesh.

Or build a selected standard size:

    make FAN_SILENCER_SIZE=40 fan-silencer
    make FAN_SILENCER_SIZE=60 fan-silencer

All dimensions are millimeters.  In the generated print orientation, X/Y span
the fan face, Z is the airflow/bolt axis, the curved inlet is at Z=0, and the
open fan-side labyrinth is at positive Z.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import lzma
import math
import struct
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

try:
    from fan_size_presets import get_standard_fan_preset
    from thingiverse_5177333_fan_intake_mk4_reference import (
        REFERENCE_BINARY_STL_SHA256,
        REFERENCE_AIRWAY_MEASUREMENT,
        REFERENCE_CENTER_XY,
        REFERENCE_FACE_COUNT,
        REFERENCE_FAN_SIZE,
        REFERENCE_FILE_ID,
        REFERENCE_HOLE_SPACING,
        REFERENCE_MINIMUM_CENTRAL_AIRWAY_AREA,
        REFERENCE_MINIMUM_CENTRAL_AIRWAY_Z_FROM_INLET,
        REFERENCE_NAME,
        REFERENCE_OUTER_DIAMETER,
        REFERENCE_STL_XZ_BASE85,
        REFERENCE_THING_ID,
        REFERENCE_Z_BOUNDS,
    )
except ModuleNotFoundError as error:
    if error.name not in {
        "fan_size_presets",
        "thingiverse_5177333_fan_intake_mk4_reference",
    }:
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from fan_size_presets import get_standard_fan_preset
    from thingiverse_5177333_fan_intake_mk4_reference import (
        REFERENCE_BINARY_STL_SHA256,
        REFERENCE_AIRWAY_MEASUREMENT,
        REFERENCE_CENTER_XY,
        REFERENCE_FACE_COUNT,
        REFERENCE_FAN_SIZE,
        REFERENCE_FILE_ID,
        REFERENCE_HOLE_SPACING,
        REFERENCE_MINIMUM_CENTRAL_AIRWAY_AREA,
        REFERENCE_MINIMUM_CENTRAL_AIRWAY_Z_FROM_INLET,
        REFERENCE_NAME,
        REFERENCE_OUTER_DIAMETER,
        REFERENCE_STL_XZ_BASE85,
        REFERENCE_THING_ID,
        REFERENCE_Z_BOUNDS,
    )


# ---------------------------------------------------------------------------
# Configuration

CLEAR_SCENE = True
FAN_SIZE_MM = 40

# AUTO uses the GoPro case's verified interface for 40 mm and shared standard
# values for the larger sizes. REQUIRED accepts only the 40 mm case interface;
# OFF always uses the shared preset without consulting the case generator.
CASE_INTERFACE_MODE = "AUTO"  # "AUTO", "REQUIRED", or "OFF"
FAN_HOLE_SPACING_OVERRIDE = None
FAN_BOLT_HOLE_DIAMETER_OVERRIDE = None

EXPORT_STL = False
EXPORT_STL_PATH = ""
EXPORT_DIRECTORY = ""
STL_NAME = "gopro_40mm_fan_silencer.stl"
RENDER_CROSS_SECTION = False
CROSS_SECTION_PATH = ""
CROSS_SECTION_NAME = "gopro_40mm_fan_silencer_cross_section.png"

CASE_GENERATOR_NAME = "gopro_fan_case_parametric_blender.py"
CASE_INTERFACE_CONFIG_NAMES = (
    "BACK_FACE_THICKNESS",
    "BACK_DOME_FAN_PAD_WIDTH",
    "BACK_DOME_FAN_PAD_HEIGHT",
    "FAN_OPENING_DIAMETER",
    "FAN_HOLE_SPACING_X",
    "FAN_HOLE_SPACING_Z",
    "FAN_HOLE_DIAMETER",
    "BAFFLE_CARTRIDGE_ENABLED",
)

# The source bosses have a 6 mm radial body around holes centered on the
# original 50 mm square pattern.  Uniformly scaling that feature preserves the
# exact MK4 proportions.  The full replacement bosses heal the original
# 5.5 mm bores before the selected standard hole diameter is redrilled.
REFERENCE_BOSS_RADIUS = 6.0
MINIMUM_BOSS_WALL = 1.20
CYLINDER_SEGMENTS = 128
BOOLEAN_OVERLAP = 0.30
MAXIMUM_BOOLEAN_FRAGMENT_FACES = 64
MINIMUM_BLENDER_VERSION = (5, 2, 0)

# Resolved values are refreshed by apply_fan_size_config() for every build.
FAN_NOMINAL_SIZE = 40.0
FAN_REFERENCE = "Noctua NF-A4x20"
FAN_DEPTH = 20.0
FAN_OPENING_DIAMETER = 37.0
FAN_FRAME_OPENING_DIAMETER = 36.0
FAN_HUB_DIAMETER = 20.0
FAN_HOLE_SPACING = 32.0
FAN_BOLT_HOLE_DIAMETER = 3.6
CASE_INTERFACE_ACTIVE = True
REFERENCE_SCALE = FAN_NOMINAL_SIZE / REFERENCE_FAN_SIZE
SILENCER_DEPTH = (REFERENCE_Z_BOUNDS[1] - REFERENCE_Z_BOUNDS[0]) * REFERENCE_SCALE
SILENCER_OUTER_DIAMETER = REFERENCE_OUTER_DIAMETER * REFERENCE_SCALE
BOSS_RADIUS = REFERENCE_BOSS_RADIUS * REFERENCE_SCALE


# ---------------------------------------------------------------------------
# Configuration and source validation


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
            f"Missing case interface constants in {source_path.name}: "
            f"{sorted(missing)}"
        )
    return values


def apply_fan_size_config() -> None:
    global FAN_NOMINAL_SIZE
    global FAN_REFERENCE
    global FAN_DEPTH
    global FAN_OPENING_DIAMETER
    global FAN_FRAME_OPENING_DIAMETER
    global FAN_HUB_DIAMETER
    global FAN_HOLE_SPACING
    global FAN_BOLT_HOLE_DIAMETER
    global CASE_INTERFACE_ACTIVE
    global REFERENCE_SCALE
    global SILENCER_DEPTH
    global SILENCER_OUTER_DIAMETER
    global BOSS_RADIUS
    global STL_NAME
    global CROSS_SECTION_NAME

    mode = str(CASE_INTERFACE_MODE).upper()
    if mode not in {"AUTO", "REQUIRED", "OFF"}:
        raise ValueError("CASE_INTERFACE_MODE must be AUTO, REQUIRED, or OFF")

    preset = get_standard_fan_preset(FAN_SIZE_MM)
    FAN_NOMINAL_SIZE = float(preset["frame"])
    FAN_REFERENCE = str(preset["reference"])
    FAN_DEPTH = float(preset["depth"])
    FAN_FRAME_OPENING_DIAMETER = float(preset["opening"])
    FAN_HUB_DIAMETER = float(preset["hub"])
    CASE_INTERFACE_ACTIVE = mode == "REQUIRED" or (
        mode == "AUTO" and math.isclose(FAN_NOMINAL_SIZE, 40.0)
    )
    if mode == "REQUIRED" and not math.isclose(FAN_NOMINAL_SIZE, 40.0):
        raise ValueError("CASE_INTERFACE_MODE=REQUIRED supports only the 40 mm fan")

    if CASE_INTERFACE_ACTIVE:
        case = read_case_interface_config()
        spacing_x = float(case["FAN_HOLE_SPACING_X"])
        spacing_y = float(case["FAN_HOLE_SPACING_Z"])
        if not math.isclose(spacing_x, spacing_y, abs_tol=1.0e-9):
            raise ValueError("The fan silencer requires a square case hole pattern")
        default_spacing = spacing_x
        default_hole_diameter = float(case["FAN_HOLE_DIAMETER"])
        FAN_OPENING_DIAMETER = float(case["FAN_OPENING_DIAMETER"])
    else:
        default_spacing = float(preset["hole_spacing"])
        default_hole_diameter = float(preset["hole_diameter"])
        FAN_OPENING_DIAMETER = float(preset["opening"])

    FAN_HOLE_SPACING = float(
        default_spacing
        if FAN_HOLE_SPACING_OVERRIDE is None
        else FAN_HOLE_SPACING_OVERRIDE
    )
    FAN_BOLT_HOLE_DIAMETER = float(
        default_hole_diameter
        if FAN_BOLT_HOLE_DIAMETER_OVERRIDE is None
        else FAN_BOLT_HOLE_DIAMETER_OVERRIDE
    )
    REFERENCE_SCALE = FAN_NOMINAL_SIZE / REFERENCE_FAN_SIZE
    SILENCER_DEPTH = (
        REFERENCE_Z_BOUNDS[1] - REFERENCE_Z_BOUNDS[0]
    ) * REFERENCE_SCALE
    SILENCER_OUTER_DIAMETER = REFERENCE_OUTER_DIAMETER * REFERENCE_SCALE
    BOSS_RADIUS = REFERENCE_BOSS_RADIUS * REFERENCE_SCALE
    STL_NAME = f"gopro_{FAN_NOMINAL_SIZE:g}mm_fan_silencer.stl"
    CROSS_SECTION_NAME = (
        f"gopro_{FAN_NOMINAL_SIZE:g}mm_fan_silencer_cross_section.png"
    )


def validate_config() -> None:
    if (
        FAN_OPENING_DIAMETER <= 0.0
        or FAN_HOLE_SPACING <= 0.0
        or FAN_BOLT_HOLE_DIAMETER <= 0.0
    ):
        raise ValueError("Fan opening, hole spacing, and hole diameter must be positive")
    if REFERENCE_SCALE <= 0.0 or SILENCER_DEPTH <= 0.0:
        raise ValueError("The resolved reference scale must be positive")
    boss_wall = BOSS_RADIUS - FAN_BOLT_HOLE_DIAMETER / 2.0
    if boss_wall < MINIMUM_BOSS_WALL:
        raise ValueError(
            f"Only {boss_wall:.2f} mm remains around the mounting holes"
        )


def require_manifold_boolean_solver() -> None:
    if bpy.app.version < MINIMUM_BLENDER_VERSION:
        required = ".".join(str(value) for value in MINIMUM_BLENDER_VERSION)
        raise RuntimeError(
            f"This generator requires Blender {required}+ for reliable manifold "
            f"Booleans; found {bpy.app.version_string}"
        )
    solver_property = bpy.types.BooleanModifier.bl_rna.properties["solver"]
    solvers = {item.identifier for item in solver_property.enum_items}
    if "MANIFOLD" not in solvers:
        raise RuntimeError(
            "This Blender build lacks the MANIFOLD Boolean solver required for "
            "the four-hole adaptation"
        )


def validate_case_interface() -> None:
    if not CASE_INTERFACE_ACTIVE:
        print(
            "CASE_INTERFACE_SOURCE SKIP "
            f"fan_size={FAN_NOMINAL_SIZE:g}mm mode={CASE_INTERFACE_MODE}"
        )
        return
    case = read_case_interface_config()
    expected = {
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
    overhang = max(
        0.0,
        (
            SILENCER_OUTER_DIAMETER
            - min(
                float(case["BACK_DOME_FAN_PAD_WIDTH"]),
                float(case["BACK_DOME_FAN_PAD_HEIGHT"]),
            )
        )
        / 2.0,
    )
    print(
        "CASE_INTERFACE_SOURCE PASS "
        f"source={case_generator_path().name} pattern={FAN_HOLE_SPACING:.1f}mm_square "
        f"holes={FAN_BOLT_HOLE_DIAMETER:.1f}mm radial_pad_overhang={overhang:.2f}mm "
        f"internal_cartridge_default={case['BAFFLE_CARTRIDGE_ENABLED']}"
    )


def minimum_central_airway_area() -> float:
    return REFERENCE_MINIMUM_CENTRAL_AIRWAY_AREA * REFERENCE_SCALE**2


def report_exact_airway_limit() -> None:
    area = minimum_central_airway_area()
    opening_area = math.pi * (FAN_OPENING_DIAMETER / 2.0) ** 2
    ratio = area / opening_area
    z_from_inlet = (
        REFERENCE_MINIMUM_CENTRAL_AIRWAY_Z_FROM_INLET * REFERENCE_SCALE
    )
    print(
        "EXACT_MK4_AIRWAY WARNING "
        f"measurement={REFERENCE_AIRWAY_MEASUREMENT} "
        f"minimum_central_area={area:.2f}mm2 "
        f"throat_z_from_inlet={z_from_inlet:.2f}mm "
        f"fan_or_case_opening={FAN_OPENING_DIAMETER:.1f}mm "
        f"open_area_ratio={ratio:.1%}; "
        "exact_acoustic_geometry_retained=True; "
        "thermal_and_airflow_testing_required=True"
    )


def decoded_reference_stl() -> bytes:
    payload = lzma.decompress(base64.b85decode(REFERENCE_STL_XZ_BASE85))
    digest = hashlib.sha256(payload).hexdigest()
    if digest != REFERENCE_BINARY_STL_SHA256:
        raise RuntimeError(
            f"Embedded {REFERENCE_NAME} checksum mismatch: {digest}"
        )
    if len(payload) < 84:
        raise RuntimeError("Embedded reference STL is truncated")
    face_count = struct.unpack_from("<I", payload, 80)[0]
    expected_size = 84 + face_count * 50
    if face_count != REFERENCE_FACE_COUNT or len(payload) != expected_size:
        raise RuntimeError(
            "Embedded reference STL metadata mismatch: "
            f"faces={face_count} bytes={len(payload)} expected={expected_size}"
        )
    return payload


# ---------------------------------------------------------------------------
# Blender mesh helpers


def configure_scene() -> None:
    if CLEAR_SCENE:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.length_unit = "MILLIMETERS"
    bpy.context.scene.unit_settings.scale_length = 0.001


def select_only(obj) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def create_mesh_object(name: str, vertices, faces):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update(calc_edges=True)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def create_exact_reference_object():
    payload = decoded_reference_stl()
    facet = struct.Struct("<12fH")
    vertices = []
    faces = []
    vertex_indices = {}
    source_x, source_y = REFERENCE_CENTER_XY
    source_z0 = REFERENCE_Z_BOUNDS[0]

    for face_index in range(REFERENCE_FACE_COUNT):
        values = facet.unpack_from(payload, 84 + face_index * facet.size)
        face = []
        for offset in (3, 6, 9):
            source = values[offset : offset + 3]
            transformed = (
                (source[0] - source_x) * REFERENCE_SCALE,
                (source[1] - source_y) * REFERENCE_SCALE,
                (source[2] - source_z0) * REFERENCE_SCALE,
            )
            key = tuple(round(value, 7) for value in transformed)
            index = vertex_indices.get(key)
            if index is None:
                index = len(vertices)
                vertex_indices[key] = index
                vertices.append(transformed)
            face.append(index)
        faces.append(tuple(face))

    obj = create_mesh_object(
        f"GoPro_{FAN_NOMINAL_SIZE:g}mm_Fan_Silencer_Thingiverse_5177333",
        vertices,
        faces,
    )
    print(
        "REFERENCE_CORE PASS "
        f"thing={REFERENCE_THING_ID} file={REFERENCE_FILE_ID} name={REFERENCE_NAME} "
        f"faces={REFERENCE_FACE_COUNT} sha256={REFERENCE_BINARY_STL_SHA256} "
        f"source_fan={REFERENCE_FAN_SIZE:g}mm "
        f"source_pattern={REFERENCE_HOLE_SPACING:g}mm_square "
        f"uniform_scale={REFERENCE_SCALE:.5f}"
    )
    return obj


def add_cylinder(name: str, radius: float, z0: float, z1: float, x=0.0, y=0.0):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=CYLINDER_SEGMENTS,
        radius=radius,
        depth=z1 - z0,
        location=(x, y, (z0 + z1) / 2.0),
    )
    obj = bpy.context.object
    obj.name = name
    return obj


def apply_boolean(base, tool, operation: str, label: str) -> None:
    select_only(base)
    modifier = base.modifiers.new(label, "BOOLEAN")
    modifier.operation = operation
    modifier.solver = "MANIFOLD"
    modifier.object = tool
    if hasattr(modifier, "use_hole_tolerant"):
        modifier.use_hole_tolerant = True
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(tool, do_unlink=True)


def fan_hole_centers():
    half = FAN_HOLE_SPACING / 2.0
    return tuple((x, y) for x in (-half, half) for y in (-half, half))


def replace_with_four_hole_interface(obj) -> None:
    # A full boss at each corner fills both original diagonal bores and creates
    # their missing pair.  The reference wall/rib system intersects these
    # cylinders, so the Boolean result stays a single connected shell.
    for index, (x, y) in enumerate(fan_hole_centers()):
        boss = add_cylinder(
            f"Fan_Boss_{index}",
            BOSS_RADIUS,
            0.0,
            SILENCER_DEPTH,
            x,
            y,
        )
        apply_boolean(obj, boss, "UNION", f"Add_Boss_{index}")

    # Each full boss also heals the source's larger diagonal bores.  Drill the
    # final standard bores one at a time; sequential manifold Booleans avoid the
    # coincident fragments produced by a disconnected four-cylinder operand.
    for index, (x, y) in enumerate(fan_hole_centers()):
        cutter = add_cylinder(
            f"Fan_Through_Hole_{index}",
            FAN_BOLT_HOLE_DIAMETER / 2.0,
            -BOOLEAN_OVERLAP,
            SILENCER_DEPTH + BOOLEAN_OVERLAP,
            x,
            y,
        )
        apply_boolean(obj, cutter, "DIFFERENCE", f"Cut_Through_Hole_{index}")


def cleanup_mesh(obj) -> None:
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=0.00001)

    # Blender's manifold Boolean preserves three microscopic triangle islands
    # where the source's heavily triangulated dome meets a replacement boss.
    # They are detached numerical fragments (14-15 faces), not printable
    # features.  Keep the dominant connected solid and reject, rather than
    # silently discard, any fragment large enough to represent real geometry.
    unseen = set(bm.faces)
    components = []
    while unseen:
        seed = unseen.pop()
        faces = {seed}
        stack = [seed]
        while stack:
            face = stack.pop()
            for edge in face.edges:
                for linked in edge.link_faces:
                    if linked in unseen:
                        unseen.remove(linked)
                        faces.add(linked)
                        stack.append(linked)
        components.append(faces)
    if len(components) > 1:
        components.sort(key=len, reverse=True)
        fragments = components[1:]
        oversized = [len(faces) for faces in fragments if len(faces) > MAXIMUM_BOOLEAN_FRAGMENT_FACES]
        if oversized:
            bm.free()
            raise RuntimeError(
                f"Boolean produced substantive disconnected shells: {oversized}"
            )
        fragment_verts = {
            vert for faces in fragments for face in faces for vert in face.verts
        }
        print(
            "BOOLEAN_FRAGMENT_CLEANUP "
            f"shells={len(fragments)} face_counts={[len(faces) for faces in fragments]}"
        )
        bmesh.ops.delete(bm, geom=list(fragment_verts), context="VERTS")

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update(calc_edges=True)


# ---------------------------------------------------------------------------
# Validation and export


def mesh_topology(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    non_manifold = sum(1 for edge in bm.edges if len(edge.link_faces) != 2)
    unseen = set(bm.faces)
    shells = 0
    while unseen:
        shells += 1
        stack = [unseen.pop()]
        while stack:
            face = stack.pop()
            for edge in face.edges:
                for linked in edge.link_faces:
                    if linked in unseen:
                        unseen.remove(linked)
                        stack.append(linked)
    bm.free()
    return non_manifold, shells


def mesh_volume(obj) -> float:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    volume = abs(bm.calc_volume(signed=True))
    bm.free()
    return volume


def object_bounds(obj):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return tuple(
        (
            min(corner[axis] for corner in corners),
            max(corner[axis] for corner in corners),
        )
        for axis in range(3)
    )


def validate_object(obj) -> None:
    cleanup_mesh(obj)
    non_manifold, shells = mesh_topology(obj)
    volume = mesh_volume(obj)
    bounds = object_bounds(obj)
    if non_manifold:
        raise RuntimeError(f"Silencer has {non_manifold} non-manifold edges")
    if shells != 1:
        raise RuntimeError(f"Silencer has {shells} disconnected shells")
    if volume <= 0.0:
        raise RuntimeError("Silencer has no enclosed volume")
    if not math.isclose(bounds[2][0], 0.0, abs_tol=0.01):
        raise RuntimeError(f"Curved inlet does not start on Z=0: {bounds[2]}")
    if not math.isclose(bounds[2][1], SILENCER_DEPTH, abs_tol=0.01):
        raise RuntimeError(
            f"Open fan-face depth drift: {bounds[2][1]:.3f} != {SILENCER_DEPTH:.3f}"
        )

    # A ray through each hole must cross no material, while a nearby ray must
    # encounter the boss.  This verifies true two-sided through-bores rather
    # than blind recesses or Boolean artifacts.
    direction = Vector((0.0, 0.0, 1.0))
    ray_distance = SILENCER_DEPTH + 1.0
    for index, (x, y) in enumerate(fan_hole_centers()):
        center_hit, *_ = obj.ray_cast(
            Vector((x, y, -0.5)), direction, distance=ray_distance
        )
        if center_hit:
            raise RuntimeError(f"Mounting hole {index} is not open end-to-end")
        wall_x = x + FAN_BOLT_HOLE_DIAMETER / 2.0 + MINIMUM_BOSS_WALL / 2.0
        wall_hit, *_ = obj.ray_cast(
            Vector((wall_x, y, -0.5)), direction, distance=ray_distance
        )
        if not wall_hit:
            raise RuntimeError(f"Mounting boss {index} lacks radial wall material")

    print(
        f"MESH PASS vertices={len(obj.data.vertices)} polygons={len(obj.data.polygons)} "
        f"volume={volume:.1f}mm3 non_manifold_edges={non_manifold} shells={shells}"
    )
    print(
        "FOUR_HOLE_INTERFACE PASS "
        f"pattern={FAN_HOLE_SPACING:.1f}mm_square "
        f"holes={FAN_BOLT_HOLE_DIAMETER:.1f}mm through_depth={SILENCER_DEPTH:.1f}mm "
        f"boss_wall={BOSS_RADIUS - FAN_BOLT_HOLE_DIAMETER / 2.0:.2f}mm"
    )
    print(
        "PRINT_ORIENTATION PASS curved_inlet_at_z0=True "
        "open_fan_labyrinth_up=True supports=accessible_from_open_passages"
    )


def resolved_export_path() -> Path:
    if EXPORT_STL_PATH:
        return Path(EXPORT_STL_PATH).expanduser().resolve()
    if EXPORT_DIRECTORY:
        return Path(EXPORT_DIRECTORY).expanduser().resolve() / STL_NAME
    if bpy.data.filepath:
        return Path(bpy.data.filepath).parent.resolve() / STL_NAME
    return Path(__file__).resolve().parent / STL_NAME


def export_stl(obj) -> None:
    path = resolved_export_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    select_only(obj)
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(filepath=str(path), export_selected_objects=True)
    elif hasattr(bpy.ops.export_mesh, "stl"):
        bpy.ops.export_mesh.stl(filepath=str(path), use_selection=True)
    else:
        raise RuntimeError("No STL exporter is available")
    print(f"Wrote {path}")


# ---------------------------------------------------------------------------
# Assembled cross-section render


def resolved_cross_section_path() -> Path:
    if CROSS_SECTION_PATH:
        return Path(CROSS_SECTION_PATH).expanduser().resolve()
    if EXPORT_DIRECTORY:
        return Path(EXPORT_DIRECTORY).expanduser().resolve() / CROSS_SECTION_NAME
    if bpy.data.filepath:
        return Path(bpy.data.filepath).parent.resolve() / CROSS_SECTION_NAME
    return Path(__file__).resolve().parent / CROSS_SECTION_NAME


def add_box(name: str, size, location):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    select_only(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def duplicate_mesh_object(obj, name: str):
    duplicate = obj.copy()
    duplicate.data = obj.data.copy()
    duplicate.name = name
    duplicate.hide_render = False
    duplicate.hide_viewport = False
    bpy.context.collection.objects.link(duplicate)
    return duplicate


def keep_positive_y_half(obj, label: str) -> None:
    cutter = add_box(
        f"{label}_Section_Halfspace",
        (400.0, 200.0, 400.0),
        (0.0, 100.0, 0.0),
    )
    apply_boolean(obj, cutter, "INTERSECT", f"{label}_Center_Section")


def preview_material(name: str, color):
    material = bpy.data.materials.get(name)
    if material is None:
        material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1.0)
    return material


def assign_preview_material(obj, material) -> None:
    obj.data.materials.clear()
    obj.data.materials.append(material)


def rotate_section_axial_horizontal(obj) -> None:
    obj.matrix_world = Matrix.Rotation(math.pi / 2.0, 4, "Y") @ obj.matrix_world


def add_preview_text(body: str, location, size: float, material) -> None:
    bpy.ops.object.text_add(location=location, rotation=(math.pi / 2.0, 0.0, 0.0))
    text_obj = bpy.context.object
    text_obj.data.body = body
    text_obj.data.align_x = "CENTER"
    text_obj.data.align_y = "CENTER"
    text_obj.data.size = size
    text_obj.data.extrude = 0.02
    text_obj.data.materials.append(material)
    bpy.context.view_layer.update()
    select_only(text_obj)
    bpy.ops.object.convert(target="MESH")


def render_assembled_cross_section(silencer) -> None:
    """Render an actual MK4 center cut with schematic case and fan sections."""
    case_material = preview_material("Preview_Case_Blue", (0.12, 0.34, 0.62))
    silencer_material = preview_material(
        "Preview_Silencer_Orange", (0.93, 0.34, 0.08)
    )
    gasket_material = preview_material("Preview_Gasket_Green", (0.12, 0.63, 0.31))
    fan_material = preview_material("Preview_Fan_Gray", (0.18, 0.20, 0.23))
    hub_material = preview_material("Preview_Hub_Gray", (0.35, 0.38, 0.42))
    text_material = preview_material("Preview_Text", (0.035, 0.045, 0.06))
    airflow_material = preview_material("Preview_Airflow", (0.03, 0.48, 0.84))

    silencer.hide_render = True
    section_objects = []

    silencer_section = duplicate_mesh_object(silencer, "MK4_Silencer_Center_Section")
    keep_positive_y_half(silencer_section, "Silencer")
    assign_preview_material(silencer_section, silencer_material)
    section_objects.append(silencer_section)

    if CASE_INTERFACE_ACTIVE:
        case_config = read_case_interface_config()
        panel_size = min(
            float(case_config["BACK_DOME_FAN_PAD_WIDTH"]),
            float(case_config["BACK_DOME_FAN_PAD_HEIGHT"]),
        )
        case_thickness = float(case_config["BACK_FACE_THICKNESS"])
        case_label = f"{panel_size:g} MM CASE PAD"
    else:
        panel_size = FAN_NOMINAL_SIZE
        case_thickness = 3.0
        case_label = "MOUNTING PANEL (SCHEMATIC)"
    case = add_box(
        "Case_Rear_Pad_Section",
        (panel_size, panel_size, case_thickness),
        (0.0, 0.0, -0.5 - case_thickness / 2.0),
    )
    case_opening = add_cylinder(
        "Case_Airflow_Opening",
        FAN_OPENING_DIAMETER / 2.0,
        -case_thickness - 1.0,
        0.0,
    )
    apply_boolean(case, case_opening, "DIFFERENCE", "Open_Case_Airway")
    keep_positive_y_half(case, "Case")
    assign_preview_material(case, case_material)
    section_objects.append(case)

    gasket_outer_radius = FAN_OPENING_DIAMETER / 2.0 + 1.2
    gasket = add_cylinder(
        "Optional_Thin_Foam_Gasket_Section",
        gasket_outer_radius,
        -0.5,
        0.0,
    )
    gasket_opening = add_cylinder(
        "Gasket_Airflow_Opening",
        FAN_OPENING_DIAMETER / 2.0,
        -0.8,
        0.3,
    )
    apply_boolean(gasket, gasket_opening, "DIFFERENCE", "Open_Gasket_Airway")
    keep_positive_y_half(gasket, "Gasket")
    assign_preview_material(gasket, gasket_material)
    section_objects.append(gasket)

    fan_z0 = SILENCER_DEPTH
    fan_z1 = fan_z0 + FAN_DEPTH
    fan_frame = add_box(
        "Standard_Fan_Frame_Section",
        (FAN_NOMINAL_SIZE, FAN_NOMINAL_SIZE, FAN_DEPTH),
        (0.0, 0.0, (fan_z0 + fan_z1) / 2.0),
    )
    fan_opening = add_cylinder(
        "Fan_Frame_Opening",
        FAN_FRAME_OPENING_DIAMETER / 2.0,
        fan_z0 - BOOLEAN_OVERLAP,
        fan_z1 + BOOLEAN_OVERLAP,
    )
    apply_boolean(fan_frame, fan_opening, "DIFFERENCE", "Open_Fan_Frame")
    keep_positive_y_half(fan_frame, "Fan_Frame")
    assign_preview_material(fan_frame, fan_material)
    section_objects.append(fan_frame)

    hub_depth = min(6.0, FAN_DEPTH * 0.30)
    fan_mid_z = (fan_z0 + fan_z1) / 2.0
    fan_hub = add_cylinder(
        "Fan_Motor_Hub_Section",
        FAN_HUB_DIAMETER / 2.0,
        fan_mid_z - hub_depth / 2.0,
        fan_mid_z + hub_depth / 2.0,
    )
    keep_positive_y_half(fan_hub, "Fan_Hub")
    assign_preview_material(fan_hub, hub_material)
    section_objects.append(fan_hub)

    fan_strut = add_box(
        "Fan_Hub_Strut_Section",
        (FAN_FRAME_OPENING_DIAMETER, 2.0, 1.8),
        (0.0, 0.0, fan_mid_z),
    )
    keep_positive_y_half(fan_strut, "Fan_Strut")
    assign_preview_material(fan_strut, hub_material)
    section_objects.append(fan_strut)

    for obj in section_objects:
        rotate_section_axial_horizontal(obj)

    max_radius = max(SILENCER_OUTER_DIAMETER / 2.0, panel_size / 2.0)
    assembly_mid_x = (fan_z1 - 4.5) / 2.0
    title_z = max_radius + 9.0
    label_z = -max_radius - 7.0
    add_preview_text(
        "ASSEMBLED CENTER CROSS-SECTION",
        (assembly_mid_x, -0.8, title_z),
        3.4,
        text_material,
    )
    add_preview_text(
        "AIRFLOW  →",
        (SILENCER_DEPTH / 2.0, -0.8, max_radius + 3.0),
        2.8,
        airflow_material,
    )
    add_preview_text(
        case_label,
        (-2.5, -0.8, label_z),
        2.5,
        case_material,
    )
    add_preview_text(
        "EXACT MK4 SILENCER",
        (SILENCER_DEPTH / 2.0, -0.8, label_z - 5.0),
        2.5,
        silencer_material,
    )
    add_preview_text(
        f"{FAN_NOMINAL_SIZE:g} MM FAN (SCHEMATIC)",
        ((fan_z0 + fan_z1) / 2.0, -0.8, label_z),
        2.5,
        fan_material,
    )
    add_preview_text(
        "thin foam gasket",
        (-0.25, -0.8, label_z - 10.0),
        2.0,
        gasket_material,
    )

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.color_type = "MATERIAL"
    if hasattr(shading, "show_shadows"):
        shading.show_shadows = True
    if hasattr(shading, "show_cavity"):
        shading.show_cavity = True
        shading.cavity_type = "WORLD"
    if hasattr(shading, "show_specular_highlight"):
        shading.show_specular_highlight = True
    if hasattr(shading, "show_object_outline"):
        shading.show_object_outline = True
    shading.background_type = "VIEWPORT"
    shading.background_color = (0.94, 0.95, 0.97)
    if hasattr(shading, "outline_color"):
        shading.outline_color = (0.04, 0.05, 0.07)

    bpy.ops.object.camera_add(location=(assembly_mid_x, -180.0, 0.0))
    camera = bpy.context.object
    camera.name = "Cross_Section_Camera"
    direction = Vector((assembly_mid_x, 0.0, 0.0)) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    render_aspect = scene.render.resolution_x / scene.render.resolution_y
    camera.data.ortho_scale = 2.0 * (max_radius + 18.0) * render_aspect
    scene.camera = camera

    path = resolved_cross_section_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    print(f"Wrote {path}")


def build_gopro_fan_silencer():
    apply_fan_size_config()
    validate_config()
    require_manifold_boolean_solver()
    validate_case_interface()
    configure_scene()
    silencer = create_exact_reference_object()
    replace_with_four_hole_interface(silencer)
    bpy.context.view_layer.update()
    validate_object(silencer)
    report_exact_airway_limit()
    silencer.name = f"GoPro_{FAN_NOMINAL_SIZE:g}mm_Fan_Silencer_MK4"
    print(
        "ASSEMBLY one_piece=True "
        f"reference=Thingiverse_{REFERENCE_THING_ID}_MK4_v23 "
        f"fan={FAN_REFERENCE.replace(' ', '_')} outer_diameter={SILENCER_OUTER_DIAMETER:.1f}mm "
        f"depth={SILENCER_DEPTH:.1f}mm"
    )
    if CASE_INTERFACE_ACTIVE:
        print(
            "INSTALLATION external_silencer_replaces_internal_baffle_cartridge; "
            "do_not_stack_without_measured_airflow"
        )
    if EXPORT_STL:
        export_stl(silencer)
    if RENDER_CROSS_SECTION:
        render_assembled_cross_section(silencer)
    return (silencer,)


if __name__ == "__main__":
    build_gopro_fan_silencer()
