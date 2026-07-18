"""Parametric flat PC-fan cover for Blender.

Run from a terminal:

    blender --background --python flat-fan-cover.py

Edit only the CONFIG section for normal use.  Dimensions are millimetres.
The command above writes ``flat-fan-cover.stl`` beside this script by default.
The 60 mm defaults reproduce the proportions of ``fan-cover.stl`` while
using a proper 4.3 mm Noctua-style through-hole instead of that STL's
approximately 8.2 mm mounting openings.

Axes:
    X/Y - fan face
    Z   - cover thickness; Z=0 is the print-bed side
"""

from __future__ import annotations

import math
from pathlib import Path

import bmesh
import bpy


# ---------------------------------------------------------------------------
# CONFIG

CLEAR_SCENE = True
EXPORT_STL = True
EXPORT_DIRECTORY = ""  # Empty means the directory containing this script.
EXPORT_STL_NAME = "flat-fan-cover.stl"
SAVE_BLEND = False
SAVE_BLEND_NAME = "flat-fan-cover.blend"

# Select a square fan preset.  Noctua is the dimensional golden set where it
# offers a matching size.  The 50/70/100/180 mm entries are generic industry
# sizes and are deliberately labelled as such.  Every value remains
# overridable below.
FAN_SIZE_MM = 60
FAN_PRESETS = {
    # size: depth, mounting patterns, mounting hole diameter, reference
    40: {
        "depth": 20.0,
        "patterns": ((32.0, 32.0),),
        "hole": 4.3,
        "reference": "Noctua NF-A4x20",
    },
    50: {
        "depth": 15.0,
        "patterns": ((40.0, 40.0),),
        "hole": 4.3,
        "reference": "generic 50 mm axial fan",
    },
    60: {
        "depth": 25.0,
        "patterns": ((50.0, 50.0),),
        "hole": 4.3,
        "reference": "Noctua NF-A6x25",
    },
    70: {
        "depth": 15.0,
        "patterns": ((60.0, 60.0),),
        "hole": 4.3,
        "reference": "generic 70 mm axial fan",
    },
    80: {
        "depth": 25.0,
        "patterns": ((71.5, 71.5),),
        "hole": 4.3,
        "reference": "Noctua NF-A8",
    },
    92: {
        "depth": 25.0,
        "patterns": ((82.5, 82.5),),
        "hole": 4.3,
        "reference": "Noctua NF-A9",
    },
    100: {
        "depth": 25.0,
        "patterns": ((90.0, 90.0),),
        "hole": 4.3,
        "reference": "generic 100 mm axial fan; verify uncommon hardware",
    },
    120: {
        "depth": 25.0,
        "patterns": ((105.0, 105.0),),
        "hole": 4.3,
        "reference": "Noctua NF-A12x25",
    },
    140: {
        "depth": 25.0,
        "patterns": ((124.5, 124.5),),
        "hole": 4.3,
        "reference": "Noctua NF-A14",
    },
    180: {
        "depth": 32.0,
        "patterns": ((165.0, 165.0),),
        "hole": 4.3,
        "reference": "generic 180 mm PC fan",
    },
    200: {
        "depth": 30.0,
        # NF-A20 supports all three patterns.  Index 0 is its usual square
        # pattern; select 1 or 2 with MOUNT_PATTERN_INDEX if needed.
        "patterns": ((154.0, 154.0), (170.0, 170.0), (110.0, 180.0)),
        "hole": 4.3,
        "reference": "Noctua NF-A20",
    },
}

# Set an override to a number, or leave it as None to use the selected preset.
FAN_WIDTH_OVERRIDE = None
FAN_HEIGHT_OVERRIDE = None
MOUNT_PATTERN_INDEX = 0
MOUNT_SPACING_X_OVERRIDE = None
MOUNT_SPACING_Y_OVERRIDE = None
MOUNT_HOLE_DIAMETER_OVERRIDE = None
MOUNT_HOLE_EXTRA_CLEARANCE = 0.0

# Main plate.  A 3.35 mm overhang recreates the original 66.7 mm cover around
# a 60 mm fan.  Set either outer-size override for a non-uniform border.
COVER_OVERHANG_PER_SIDE = 3.35
COVER_OUTER_WIDTH_OVERRIDE = None
COVER_OUTER_HEIGHT_OVERRIDE = None
COVER_THICKNESS = 2.9
COVER_CORNER_RADIUS = 2.5
EDGE_BEVEL = 0.30
EDGE_BEVEL_SEGMENTS = 3

# Circular airflow opening and concentric grille.
AIRFLOW_DIAMETER_OVERRIDE = None
AIRFLOW_EDGE_INSET = 0.50  # Auto diameter = min(fan width, height) - this.
GRILLE_RING_RADIUS_FRACTIONS = (0.56, 0.80)  # Fractions of airflow radius.
GRILLE_RING_RADII_OVERRIDE = None
GRILLE_RING_WIDTH = 2.0
GRILLE_CROSSBAR_WIDTH = 2.0
GRILLE_CROSSBAR_ANGLE_DEG = 0.0
GRILLE_CENTER_DISK_DIAMETER_OVERRIDE = None
GRILLE_CENTER_DISK_DIAMETER_FRACTION = 0.3583333333  # 21.5 mm at 60 mm.

# Four fan mounting holes.  The optional front counterbores preserve the
# original cover's visual weight while the through-hole remains correctly
# sized for Noctua frames and normal PC fan screws.
MOUNT_HOLES_ENABLED = True
MOUNT_COUNTERBORES_ENABLED = True
MOUNT_COUNTERBORE_DIAMETER = 8.2
MOUNT_COUNTERBORE_DEPTH = 1.2

# Mesh/boolean quality.  Increase CYLINDER_SEGMENTS for very large covers.
CYLINDER_SEGMENTS = 96
CORNER_SEGMENTS = 10
BOOLEAN_SOLVER = "EXACT"
BOOLEAN_OVERLAP = 0.08
FAIL_ON_NON_MANIFOLD = True
DEBUG_BOOLEAN_STEPS = False


# Dimensional sources used for the golden set:
# https://www.noctua.at/en/products/nf-a4x20-pwm/specifications
# https://www.noctua.at/en/products/nf-a6x25-pwm/specifications
# https://www.noctua.at/en/products/nf-a8-pwm/specifications
# https://www.noctua.at/en/products/nf-a9-pwm/specifications
# https://www.noctua.at/en/products/nf-a12x25-pwm/specifications
# https://www.noctua.at/en/products/nf-a14-pwm/specifications
# https://www.noctua.at/en/products/nf-a20-pwm/specifications
# Cross-check containing 40/120/200 mm spacing values:
# https://aphnetworks.com/reviews/noctua-nf-a-series


# ---------------------------------------------------------------------------
# Mesh helpers

def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def set_units() -> None:
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 0.001


def create_mesh_object(name: str, vertices, faces):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


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
    corners = (
        (width / 2.0 - radius, height / 2.0 - radius, 0.0),
        (-width / 2.0 + radius, height / 2.0 - radius, 90.0),
        (-width / 2.0 + radius, -height / 2.0 + radius, 180.0),
        (width / 2.0 - radius, -height / 2.0 + radius, 270.0),
    )
    for cx, cy, start_degrees in corners:
        for index in range(segments):
            angle = math.radians(start_degrees + 90.0 * index / segments)
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def polygon_prism(name: str, loop, z0: float, z1: float):
    count = len(loop)
    vertices = [(x, y, z0) for x, y in loop]
    vertices.extend((x, y, z1) for x, y in loop)
    center_x = sum(x for x, _ in loop) / count
    center_y = sum(y for _, y in loop) / count
    vertices.extend(((center_x, center_y, z0), (center_x, center_y, z1)))
    bottom_center = count * 2
    top_center = bottom_center + 1
    faces = []
    for index in range(count):
        nxt = (index + 1) % count
        faces.append((index, nxt, count + nxt, count + index))
        faces.append((bottom_center, nxt, index))
        faces.append((top_center, count + index, count + nxt))
    return create_mesh_object(name, vertices, faces)


def concave_polygon_prism(name: str, loop, z0: float, z1: float):
    """Extrude a simple concave loop without a center-fan triangulation."""
    count = len(loop)
    vertices = [(x, y, z0) for x, y in loop]
    vertices.extend((x, y, z1) for x, y in loop)
    faces = [tuple(reversed(range(count))), tuple(range(count, count * 2))]
    for index in range(count):
        nxt = (index + 1) % count
        faces.append((index, nxt, count + nxt, count + index))
    return create_mesh_object(name, vertices, faces)


def annular_gap_sector_prism(
    name: str,
    inner_radius: float,
    outer_radius: float,
    quadrant: int,
    z0: float,
    z1: float,
):
    """Create one quadrant of an annular gap, leaving constant-width bars."""
    half_bar = GRILLE_CROSSBAR_WIDTH / 2.0
    outer_start = math.asin(min(0.999999, half_bar / outer_radius))
    inner_start = math.asin(min(0.999999, half_bar / inner_radius))
    segments = max(8, CYLINDER_SEGMENTS // 4)
    points = []
    for index in range(segments + 1):
        angle = outer_start + (math.pi / 2.0 - 2.0 * outer_start) * index / segments
        points.append((outer_radius * math.cos(angle), outer_radius * math.sin(angle)))
    for index in range(segments, -1, -1):
        angle = inner_start + (math.pi / 2.0 - 2.0 * inner_start) * index / segments
        points.append((inner_radius * math.cos(angle), inner_radius * math.sin(angle)))
    rotation = quadrant * math.pi / 2.0 + math.radians(GRILLE_CROSSBAR_ANGLE_DEG)
    cosine = math.cos(rotation)
    sine = math.sin(rotation)
    rotated = [(x * cosine - y * sine, x * sine + y * cosine) for x, y in points]
    return concave_polygon_prism(name, rotated, z0, z1)


def rounded_rectangle_prism(name: str, width: float, height: float, radius: float, z0: float, z1: float):
    return polygon_prism(name, rounded_rectangle_loop(width, height, radius, CORNER_SEGMENTS), z0, z1)


def annular_prism(name: str, inner_radius: float, outer_radius: float, z0: float, z1: float):
    count = CYLINDER_SEGMENTS
    outer = []
    inner = []
    for index in range(count):
        angle = 2.0 * math.pi * index / count
        cosine = math.cos(angle)
        sine = math.sin(angle)
        outer.append((outer_radius * cosine, outer_radius * sine))
        inner.append((inner_radius * cosine, inner_radius * sine))

    vertices = [(x, y, z0) for x, y in outer]
    vertices.extend((x, y, z1) for x, y in outer)
    vertices.extend((x, y, z0) for x, y in inner)
    vertices.extend((x, y, z1) for x, y in inner)
    faces = []
    for index in range(count):
        nxt = (index + 1) % count
        ob, ot = index, count + index
        ib, it = count * 2 + index, count * 3 + index
        nob, not_ = nxt, count + nxt
        nib, nit = count * 2 + nxt, count * 3 + nxt
        faces.extend(((ob, nob, not_, ot), (ib, it, nit, nib), (nob, ob, ib, nib), (ot, not_, nit, it)))
    return create_mesh_object(name, vertices, faces)


def add_box(name: str, dimensions, location, rotation_z_degrees: float = 0.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    obj.dimensions = dimensions
    obj.rotation_euler.z = math.radians(rotation_z_degrees)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def add_cylinder(name: str, radius: float, z0: float, z1: float, x: float = 0.0, y: float = 0.0):
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


def select_only(obj) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def join_tools(name: str, tools):
    tools = list(tools)
    if len(tools) == 1:
        tools[0].name = name
        return tools[0]
    bpy.ops.object.select_all(action="DESELECT")
    for tool in tools:
        tool.select_set(True)
    bpy.context.view_layer.objects.active = tools[0]
    bpy.ops.object.join()
    tools[0].name = name
    return tools[0]


def separate_loose_parts(obj, name_prefix: str):
    """Return one object per disconnected shell in ``obj``."""
    select_only(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.separate(type="LOOSE")
    bpy.ops.object.mode_set(mode="OBJECT")
    parts = list(bpy.context.selected_objects)
    parts.sort(key=lambda item: item.name)
    for index, part in enumerate(parts, start=1):
        part.name = f"{name_prefix}_{index}"
    return parts


def apply_boolean(base, tool, operation: str, label: str):
    select_only(base)
    modifier = base.modifiers.new(label, "BOOLEAN")
    modifier.operation = operation
    modifier.object = tool
    if hasattr(modifier, "solver"):
        modifier.solver = BOOLEAN_SOLVER
    if hasattr(modifier, "use_self"):
        modifier.use_self = False
    if hasattr(modifier, "use_hole_tolerant"):
        modifier.use_hole_tolerant = True
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(tool, do_unlink=True)
    if DEBUG_BOOLEAN_STEPS:
        print(f"{label}: operation={operation} mesh_stats={mesh_stats(base)}")
    return base


def boolean_union(base, part, label: str):
    return apply_boolean(base, part, "UNION", label)


def boolean_difference(base, tools, label: str):
    return apply_boolean(base, join_tools(label + "_Tools", tools), "DIFFERENCE", label)


def boolean_intersection(base, tool, label: str):
    return apply_boolean(base, tool, "INTERSECT", label)


def bevel_mesh(obj) -> None:
    if EDGE_BEVEL <= 0.0:
        return
    select_only(obj)
    modifier = obj.modifiers.new("Edge_Bevel", "BEVEL")
    modifier.width = EDGE_BEVEL
    modifier.segments = EDGE_BEVEL_SEGMENTS
    modifier.limit_method = "ANGLE"
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def recalc_normals(obj) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def triangulate(obj) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=list(bm.faces), quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def mesh_stats(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    non_manifold = sum(1 for edge in bm.edges if not edge.is_manifold)
    remaining = set(bm.verts)
    shells = 0
    while remaining:
        shells += 1
        stack = [remaining.pop()]
        while stack:
            vertex = stack.pop()
            for edge in vertex.link_edges:
                other = edge.other_vert(vertex)
                if other in remaining:
                    remaining.remove(other)
                    stack.append(other)
    bm.free()
    return non_manifold, shells


# ---------------------------------------------------------------------------
# Generator

def resolved_dimensions():
    if FAN_SIZE_MM not in FAN_PRESETS:
        raise ValueError(f"Unsupported FAN_SIZE_MM {FAN_SIZE_MM}; choose {tuple(FAN_PRESETS)}")
    preset = FAN_PRESETS[FAN_SIZE_MM]
    if not 0 <= MOUNT_PATTERN_INDEX < len(preset["patterns"]):
        raise ValueError("MOUNT_PATTERN_INDEX is outside the selected preset's pattern list")

    fan_width = float(FAN_WIDTH_OVERRIDE if FAN_WIDTH_OVERRIDE is not None else FAN_SIZE_MM)
    fan_height = float(FAN_HEIGHT_OVERRIDE if FAN_HEIGHT_OVERRIDE is not None else FAN_SIZE_MM)
    pattern_x, pattern_y = preset["patterns"][MOUNT_PATTERN_INDEX]
    spacing_x = float(MOUNT_SPACING_X_OVERRIDE if MOUNT_SPACING_X_OVERRIDE is not None else pattern_x)
    spacing_y = float(MOUNT_SPACING_Y_OVERRIDE if MOUNT_SPACING_Y_OVERRIDE is not None else pattern_y)
    hole = float(MOUNT_HOLE_DIAMETER_OVERRIDE if MOUNT_HOLE_DIAMETER_OVERRIDE is not None else preset["hole"])
    hole += MOUNT_HOLE_EXTRA_CLEARANCE
    cover_width = float(
        COVER_OUTER_WIDTH_OVERRIDE
        if COVER_OUTER_WIDTH_OVERRIDE is not None
        else fan_width + 2.0 * COVER_OVERHANG_PER_SIDE
    )
    cover_height = float(
        COVER_OUTER_HEIGHT_OVERRIDE
        if COVER_OUTER_HEIGHT_OVERRIDE is not None
        else fan_height + 2.0 * COVER_OVERHANG_PER_SIDE
    )
    airflow = float(
        AIRFLOW_DIAMETER_OVERRIDE
        if AIRFLOW_DIAMETER_OVERRIDE is not None
        else min(fan_width, fan_height) - AIRFLOW_EDGE_INSET
    )
    radii = (
        tuple(float(value) for value in GRILLE_RING_RADII_OVERRIDE)
        if GRILLE_RING_RADII_OVERRIDE is not None
        else tuple(airflow / 2.0 * fraction for fraction in GRILLE_RING_RADIUS_FRACTIONS)
    )
    hub_diameter = float(
        GRILLE_CENTER_DISK_DIAMETER_OVERRIDE
        if GRILLE_CENTER_DISK_DIAMETER_OVERRIDE is not None
        else min(fan_width, fan_height) * GRILLE_CENTER_DISK_DIAMETER_FRACTION
    )
    return preset, fan_width, fan_height, cover_width, cover_height, airflow, spacing_x, spacing_y, hole, radii, hub_diameter


def validate_config(values) -> None:
    preset, fan_width, fan_height, cover_width, cover_height, airflow, spacing_x, spacing_y, hole, radii, hub_diameter = values
    del preset
    positives = {
        "fan width": fan_width,
        "fan height": fan_height,
        "cover width": cover_width,
        "cover height": cover_height,
        "COVER_THICKNESS": COVER_THICKNESS,
        "airflow diameter": airflow,
        "mount spacing X": spacing_x,
        "mount spacing Y": spacing_y,
        "mount hole diameter": hole,
        "GRILLE_RING_WIDTH": GRILLE_RING_WIDTH,
        "GRILLE_CROSSBAR_WIDTH": GRILLE_CROSSBAR_WIDTH,
        "center disk diameter": hub_diameter,
    }
    for label, value in positives.items():
        if value <= 0.0:
            raise ValueError(f"{label} must be positive")
    if airflow >= min(cover_width, cover_height):
        raise ValueError("Airflow opening must fit inside the cover")
    largest_mount_opening = (
        MOUNT_COUNTERBORE_DIAMETER
        if MOUNT_COUNTERBORES_ENABLED and MOUNT_COUNTERBORE_DEPTH > 0.0
        else hole
    )
    if MOUNT_HOLES_ENABLED:
        if spacing_x / 2.0 + largest_mount_opening / 2.0 >= cover_width / 2.0:
            raise ValueError("X mounting holes do not fit inside the cover")
        if spacing_y / 2.0 + largest_mount_opening / 2.0 >= cover_height / 2.0:
            raise ValueError("Y mounting holes do not fit inside the cover")
    if not 0.0 <= MOUNT_COUNTERBORE_DEPTH < COVER_THICKNESS:
        raise ValueError("MOUNT_COUNTERBORE_DEPTH must be in [0, COVER_THICKNESS)")
    for radius in radii:
        if radius <= GRILLE_RING_WIDTH / 2.0:
            raise ValueError("Every grille radius must exceed half GRILLE_RING_WIDTH")
        if radius + GRILLE_RING_WIDTH / 2.0 >= airflow / 2.0:
            raise ValueError("Every grille ring must fit inside the airflow opening")
    occupied = [hub_diameter / 2.0]
    for radius in sorted(radii):
        if radius - GRILLE_RING_WIDTH / 2.0 <= occupied[-1]:
            raise ValueError("Center disk and grille rings must have positive airflow gaps")
        occupied.append(radius + GRILLE_RING_WIDTH / 2.0)


def build_flat_fan_cover():
    values = resolved_dimensions()
    validate_config(values)
    preset, fan_width, fan_height, cover_width, cover_height, airflow, spacing_x, spacing_y, hole, radii, hub_diameter = values
    if CLEAR_SCENE:
        clear_scene()
    set_units()

    cover = rounded_rectangle_prism(
        "Flat_Fan_Cover",
        cover_width,
        cover_height,
        COVER_CORNER_RADIUS,
        0.0,
        COVER_THICKNESS,
    )
    hole_centers = [
        (x_sign * spacing_x / 2.0, y_sign * spacing_y / 2.0)
        for x_sign in (-1.0, 1.0)
        for y_sign in (-1.0, 1.0)
    ]

    # Form the grille subtractively from the solid plate.  Four directly
    # modelled sectors per annular gap leave the center disk, rings, and
    # constant-width crossbars as one manifold body.
    gap_boundaries = []
    inner = hub_diameter / 2.0
    for radius in sorted(radii):
        gap_boundaries.append((inner, radius - GRILLE_RING_WIDTH / 2.0))
        inner = radius + GRILLE_RING_WIDTH / 2.0
    gap_boundaries.append((inner, airflow / 2.0))
    for index, (inner_radius, outer_radius) in enumerate(gap_boundaries, start=1):
        for quadrant in range(4):
            sector = annular_gap_sector_prism(
                f"Airflow_Gap_{index}_Sector_{quadrant + 1}",
                inner_radius,
                outer_radius,
                quadrant,
                -BOOLEAN_OVERLAP,
                COVER_THICKNESS + BOOLEAN_OVERLAP,
            )
            triangulate(sector)
            recalc_normals(sector)
            boolean_difference(
                cover,
                [sector],
                f"Cut_Airflow_Gap_{index}_Sector_{quadrant + 1}",
            )

    # Drill last.  Keeping the stepped counterbores out of the grille boolean
    # sequence avoids coplanar internal faces in Blender's exact solver.
    if MOUNT_HOLES_ENABLED:
        through_holes = []
        for index, (x, y) in enumerate(hole_centers, start=1):
            through_holes.append(
                add_cylinder(
                    f"Mount_Hole_{index}",
                    hole / 2.0,
                    -BOOLEAN_OVERLAP,
                    COVER_THICKNESS + BOOLEAN_OVERLAP,
                    x,
                    y,
                )
            )
        boolean_difference(cover, through_holes, "Mount_Through_Holes")

    if MOUNT_HOLES_ENABLED and MOUNT_COUNTERBORES_ENABLED and MOUNT_COUNTERBORE_DEPTH > 0.0:
        counterbores = []
        for index, (x, y) in enumerate(hole_centers, start=1):
            counterbores.append(
                add_cylinder(
                    f"Mount_Counterbore_{index}",
                    MOUNT_COUNTERBORE_DIAMETER / 2.0,
                    COVER_THICKNESS - MOUNT_COUNTERBORE_DEPTH,
                    COVER_THICKNESS + BOOLEAN_OVERLAP,
                    x,
                    y,
                )
            )
        boolean_difference(cover, counterbores, "Mount_Counterbores")

    bevel_mesh(cover)
    recalc_normals(cover)
    triangulate(cover)
    recalc_normals(cover)
    cover.name = f"Flat_Fan_Cover_{FAN_SIZE_MM}mm"
    cover.data.name = cover.name + "_Mesh"

    non_manifold, shells = mesh_stats(cover)
    print(
        f"{cover.name}: preset={preset['reference']!r} fan={fan_width:g}x{fan_height:g} mm "
        f"mount_spacing={spacing_x:g}x{spacing_y:g} mm through_hole={hole:g} mm "
        f"vertices={len(cover.data.vertices)} polygons={len(cover.data.polygons)} "
        f"non_manifold_edges={non_manifold} connected_shells={shells}"
    )
    if FAIL_ON_NON_MANIFOLD and (non_manifold or shells != 1):
        raise RuntimeError(
            f"Generated mesh failed validation: {non_manifold} non-manifold edges, {shells} shells"
        )

    output_directory = Path(EXPORT_DIRECTORY).expanduser() if EXPORT_DIRECTORY else Path(__file__).resolve().parent
    output_directory.mkdir(parents=True, exist_ok=True)
    select_only(cover)
    if EXPORT_STL:
        path = (output_directory / EXPORT_STL_NAME).resolve()
        if hasattr(bpy.ops.wm, "stl_export"):
            bpy.ops.wm.stl_export(filepath=str(path), export_selected_objects=True)
        else:
            bpy.ops.export_mesh.stl(filepath=str(path), use_selection=True)
        print(f"Wrote {path}")
    if SAVE_BLEND:
        path = (output_directory / SAVE_BLEND_NAME).resolve()
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        print(f"Wrote {path}")
    return cover


if __name__ == "__main__":
    build_flat_fan_cover()
