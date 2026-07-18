"""Parametric wraparound PC-fan cover for Blender.

Run from a terminal:

    blender --background --python wrapping-fan-cover.py

Edit only the CONFIG section for normal use.  Dimensions are millimetres.
The command above writes ``wrapping-fan-cover.stl`` beside this script by default.
The 40x40x20 mm default follows ``fan-cover-20mm.stl``: a petal-pattern
front grille and four walls that sleeve over the fan.  The front face is put
at Z=0 so the generated cover is already oriented for printing face-down.

Axes:
    X/Y - fan face
    Z   - sleeve depth, from grille toward the open back
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
EXPORT_STL_NAME = "wrapping-fan-cover.stl"
SAVE_BLEND = False
SAVE_BLEND_NAME = "wrapping-fan-cover.blend"

# Select a fan preset.  Noctua is the dimensional golden set where it offers
# the matching frame size.  Non-Noctua generic entries are explicitly marked.
FAN_SIZE_MM = 40
FAN_PRESETS = {
    # size: representative depth, mounting patterns (informational here), ref
    40: {
        "depth": 20.0,
        "patterns": ((32.0, 32.0),),
        "reference": "Noctua NF-A4x20",
    },
    50: {
        "depth": 15.0,
        "patterns": ((40.0, 40.0),),
        "reference": "generic 50 mm axial fan",
    },
    60: {
        "depth": 25.0,
        "patterns": ((50.0, 50.0),),
        "reference": "Noctua NF-A6x25",
    },
    70: {
        "depth": 15.0,
        "patterns": ((60.0, 60.0),),
        "reference": "generic 70 mm axial fan",
    },
    80: {
        "depth": 25.0,
        "patterns": ((71.5, 71.5),),
        "reference": "Noctua NF-A8",
    },
    92: {
        "depth": 25.0,
        "patterns": ((82.5, 82.5),),
        "reference": "Noctua NF-A9",
    },
    100: {
        "depth": 25.0,
        "patterns": ((90.0, 90.0),),
        "reference": "generic 100 mm axial fan; verify uncommon hardware",
    },
    120: {
        "depth": 25.0,
        "patterns": ((105.0, 105.0),),
        "reference": "Noctua NF-A12x25",
    },
    140: {
        "depth": 25.0,
        "patterns": ((124.5, 124.5),),
        "reference": "Noctua NF-A14",
    },
    180: {
        "depth": 32.0,
        "patterns": ((165.0, 165.0),),
        "reference": "generic 180 mm PC fan",
    },
    200: {
        "depth": 30.0,
        "patterns": ((154.0, 154.0), (170.0, 170.0), (110.0, 180.0)),
        "reference": "Noctua NF-A20",
    },
}

# Fan body and fit.  Clearance is applied on every side, so 0.15 gives a
# cavity 0.30 mm wider and taller than the nominal fan.
FAN_WIDTH_OVERRIDE = None
FAN_HEIGHT_OVERRIDE = None
FAN_DEPTH_OVERRIDE = None
FIT_CLEARANCE_PER_SIDE = 0.15
DEPTH_CLEARANCE = 0.10

# Sleeve and face.  The default total depth is 20 + 0.1 + 1.2 = 21.3 mm,
# matching the source cover.  Individual sides can be disabled for clips or
# a partially wrapping shroud.
WALL_THICKNESS = 1.0
FRONT_THICKNESS = 1.2
FRONT_CORNER_RADIUS = 0.65
WRAP_LEFT_SIDE = True
WRAP_RIGHT_SIDE = True
WRAP_BOTTOM_SIDE = True
WRAP_TOP_SIDE = True
EDGE_BEVEL = 0.15
EDGE_BEVEL_SEGMENTS = 2

# Four-petal grille.  The pattern is made from four circles centred on the
# midpoints of the fan frame, exactly like the source STL.  Set the radius
# override to depart from the automatically scaled half-frame radius.
GRILLE_BORDER_INSET = 1.2
GRILLE_LINE_WIDTH = 1.2
GRILLE_PETAL_RADIUS_OVERRIDE = None
GRILLE_CENTER_DISK_DIAMETER_OVERRIDE = None
GRILLE_CENTER_DISK_DIAMETER_FRACTION = 0.525

# Optional U-shaped wire exit cut into one wall at the open back.
CABLE_NOTCH_ENABLED = True
CABLE_NOTCH_SIDE = "TOP"  # "TOP", "BOTTOM", "LEFT", or "RIGHT"
CABLE_NOTCH_WIDTH = 5.0
CABLE_NOTCH_DEPTH = 5.0
CABLE_NOTCH_OFFSET = 0.0

# Optional shallow internal ribs for a friction/snap fit.  Leave disabled for
# predictable fit; enable after measuring the actual fan's corner pads.
RETENTION_RIBS_ENABLED = False
RETENTION_RIB_DISTANCE_FROM_FRONT = 10.6
RETENTION_RIB_WIDTH_Z = 0.6
RETENTION_RIB_PROTRUSION = 0.25

# Mesh/boolean quality.
CYLINDER_SEGMENTS = 96
CORNER_SEGMENTS = 8
BOOLEAN_SOLVER = "EXACT"
BOOLEAN_OVERLAP = 0.08
FAIL_ON_NON_MANIFOLD = True
DEBUG_BOOLEAN_STEPS = False


# Noctua dimensional sources used for the golden-set presets:
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


def rounded_rectangle_prism(name: str, width: float, height: float, radius: float, z0: float, z1: float):
    return polygon_prism(name, rounded_rectangle_loop(width, height, radius, CORNER_SEGMENTS), z0, z1)


def annular_prism(name: str, center_x: float, center_y: float, inner_radius: float, outer_radius: float, z0: float, z1: float):
    count = CYLINDER_SEGMENTS
    outer = []
    inner = []
    for index in range(count):
        angle = 2.0 * math.pi * index / count
        cosine = math.cos(angle)
        sine = math.sin(angle)
        outer.append((center_x + outer_radius * cosine, center_y + outer_radius * sine))
        inner.append((center_x + inner_radius * cosine, center_y + inner_radius * sine))
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


def add_box(name: str, dimensions, location):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    obj.dimensions = dimensions
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
    if DEBUG_BOOLEAN_STEPS:
        print(f"{label}: operation={operation} mesh_stats={mesh_stats(base)}")
    return base


def boolean_union(base, part, label: str):
    return apply_boolean(base, part, "UNION", label)


def boolean_difference(base, tool, label: str):
    return apply_boolean(base, tool, "DIFFERENCE", label)


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
    fan_width = float(FAN_WIDTH_OVERRIDE if FAN_WIDTH_OVERRIDE is not None else FAN_SIZE_MM)
    fan_height = float(FAN_HEIGHT_OVERRIDE if FAN_HEIGHT_OVERRIDE is not None else FAN_SIZE_MM)
    fan_depth = float(FAN_DEPTH_OVERRIDE if FAN_DEPTH_OVERRIDE is not None else preset["depth"])
    inner_width = fan_width + 2.0 * FIT_CLEARANCE_PER_SIDE
    inner_height = fan_height + 2.0 * FIT_CLEARANCE_PER_SIDE
    outer_width = inner_width + 2.0 * WALL_THICKNESS
    outer_height = inner_height + 2.0 * WALL_THICKNESS
    total_depth = FRONT_THICKNESS + fan_depth + DEPTH_CLEARANCE
    petal_radius = float(
        GRILLE_PETAL_RADIUS_OVERRIDE
        if GRILLE_PETAL_RADIUS_OVERRIDE is not None
        else min(fan_width, fan_height) / 2.0
    )
    hub_diameter = float(
        GRILLE_CENTER_DISK_DIAMETER_OVERRIDE
        if GRILLE_CENTER_DISK_DIAMETER_OVERRIDE is not None
        else min(fan_width, fan_height) * GRILLE_CENTER_DISK_DIAMETER_FRACTION
    )
    return preset, fan_width, fan_height, fan_depth, inner_width, inner_height, outer_width, outer_height, total_depth, petal_radius, hub_diameter


def validate_config(values) -> None:
    preset, fan_width, fan_height, fan_depth, inner_width, inner_height, outer_width, outer_height, total_depth, petal_radius, hub_diameter = values
    del preset, fan_depth, inner_width, inner_height, total_depth
    positives = {
        "fan width": fan_width,
        "fan height": fan_height,
        "outer width": outer_width,
        "outer height": outer_height,
        "WALL_THICKNESS": WALL_THICKNESS,
        "FRONT_THICKNESS": FRONT_THICKNESS,
        "GRILLE_BORDER_INSET": GRILLE_BORDER_INSET,
        "GRILLE_LINE_WIDTH": GRILLE_LINE_WIDTH,
        "petal radius": petal_radius,
        "center disk diameter": hub_diameter,
    }
    for label, value in positives.items():
        if value <= 0.0:
            raise ValueError(f"{label} must be positive")
    if FIT_CLEARANCE_PER_SIDE < 0.0 or DEPTH_CLEARANCE < 0.0:
        raise ValueError("Fit clearances cannot be negative")
    if 2.0 * GRILLE_BORDER_INSET >= min(fan_width, fan_height):
        raise ValueError("GRILLE_BORDER_INSET leaves no airflow opening")
    if GRILLE_LINE_WIDTH >= 2.0 * petal_radius:
        raise ValueError("GRILLE_LINE_WIDTH is too large for the petal radius")
    if hub_diameter >= min(fan_width, fan_height):
        raise ValueError("Center disk must fit inside the fan face")
    if not any((WRAP_LEFT_SIDE, WRAP_RIGHT_SIDE, WRAP_BOTTOM_SIDE, WRAP_TOP_SIDE)):
        raise ValueError("Enable at least one wrap side")
    if CABLE_NOTCH_SIDE not in {"TOP", "BOTTOM", "LEFT", "RIGHT"}:
        raise ValueError("CABLE_NOTCH_SIDE must be TOP, BOTTOM, LEFT, or RIGHT")


def add_wrap_walls(cover, inner_width: float, inner_height: float, outer_width: float, outer_height: float, total_depth: float):
    z_center = total_depth / 2.0
    if WRAP_LEFT_SIDE:
        wall = add_box(
            "Left_Wall",
            (WALL_THICKNESS, outer_height, total_depth),
            (-inner_width / 2.0 - WALL_THICKNESS / 2.0, 0.0, z_center),
        )
        boolean_union(cover, wall, "Union_Left_Wall")
    if WRAP_RIGHT_SIDE:
        wall = add_box(
            "Right_Wall",
            (WALL_THICKNESS, outer_height, total_depth),
            (inner_width / 2.0 + WALL_THICKNESS / 2.0, 0.0, z_center),
        )
        boolean_union(cover, wall, "Union_Right_Wall")
    if WRAP_BOTTOM_SIDE:
        wall = add_box(
            "Bottom_Wall",
            (outer_width, WALL_THICKNESS, total_depth),
            (0.0, -inner_height / 2.0 - WALL_THICKNESS / 2.0, z_center),
        )
        boolean_union(cover, wall, "Union_Bottom_Wall")
    if WRAP_TOP_SIDE:
        wall = add_box(
            "Top_Wall",
            (outer_width, WALL_THICKNESS, total_depth),
            (0.0, inner_height / 2.0 + WALL_THICKNESS / 2.0, z_center),
        )
        boolean_union(cover, wall, "Union_Top_Wall")


def add_retention_ribs(cover, inner_width: float, inner_height: float):
    if not RETENTION_RIBS_ENABLED:
        return
    z = FRONT_THICKNESS + RETENTION_RIB_DISTANCE_FROM_FRONT
    depth = RETENTION_RIB_WIDTH_Z
    if WRAP_LEFT_SIDE:
        rib = add_box(
            "Left_Retention_Rib",
            (WALL_THICKNESS + RETENTION_RIB_PROTRUSION, inner_height, depth),
            (-inner_width / 2.0 - (WALL_THICKNESS - RETENTION_RIB_PROTRUSION) / 2.0, 0.0, z),
        )
        boolean_union(cover, rib, "Union_Left_Rib")
    if WRAP_RIGHT_SIDE:
        rib = add_box(
            "Right_Retention_Rib",
            (WALL_THICKNESS + RETENTION_RIB_PROTRUSION, inner_height, depth),
            (inner_width / 2.0 + (WALL_THICKNESS - RETENTION_RIB_PROTRUSION) / 2.0, 0.0, z),
        )
        boolean_union(cover, rib, "Union_Right_Rib")
    if WRAP_BOTTOM_SIDE:
        rib = add_box(
            "Bottom_Retention_Rib",
            (inner_width, WALL_THICKNESS + RETENTION_RIB_PROTRUSION, depth),
            (0.0, -inner_height / 2.0 - (WALL_THICKNESS - RETENTION_RIB_PROTRUSION) / 2.0, z),
        )
        boolean_union(cover, rib, "Union_Bottom_Rib")
    if WRAP_TOP_SIDE:
        rib = add_box(
            "Top_Retention_Rib",
            (inner_width, WALL_THICKNESS + RETENTION_RIB_PROTRUSION, depth),
            (0.0, inner_height / 2.0 + (WALL_THICKNESS - RETENTION_RIB_PROTRUSION) / 2.0, z),
        )
        boolean_union(cover, rib, "Union_Top_Rib")


def cut_cable_notch(cover, inner_width: float, inner_height: float, total_depth: float):
    if not CABLE_NOTCH_ENABLED:
        return
    z = total_depth - CABLE_NOTCH_DEPTH / 2.0 + BOOLEAN_OVERLAP
    depth = CABLE_NOTCH_DEPTH + 2.0 * BOOLEAN_OVERLAP
    if CABLE_NOTCH_SIDE in {"TOP", "BOTTOM"}:
        sign = 1.0 if CABLE_NOTCH_SIDE == "TOP" else -1.0
        y = sign * (inner_height / 2.0 + WALL_THICKNESS / 2.0)
        cutter = add_box(
            "Cable_Notch",
            (CABLE_NOTCH_WIDTH, WALL_THICKNESS + 2.0 * BOOLEAN_OVERLAP, depth),
            (CABLE_NOTCH_OFFSET, y, z),
        )
    else:
        sign = 1.0 if CABLE_NOTCH_SIDE == "RIGHT" else -1.0
        x = sign * (inner_width / 2.0 + WALL_THICKNESS / 2.0)
        cutter = add_box(
            "Cable_Notch",
            (WALL_THICKNESS + 2.0 * BOOLEAN_OVERLAP, CABLE_NOTCH_WIDTH, depth),
            (x, CABLE_NOTCH_OFFSET, z),
        )
    boolean_difference(cover, cutter, "Cut_Cable_Notch")


def build_wrapping_fan_cover():
    values = resolved_dimensions()
    validate_config(values)
    preset, fan_width, fan_height, fan_depth, inner_width, inner_height, outer_width, outer_height, total_depth, petal_radius, hub_diameter = values
    if CLEAR_SCENE:
        clear_scene()
    set_units()

    # Solid front plate first, then open its square airflow field.
    cover = rounded_rectangle_prism(
        "Wrapping_Fan_Cover",
        outer_width,
        outer_height,
        FRONT_CORNER_RADIUS,
        0.0,
        FRONT_THICKNESS,
    )
    airflow_width = fan_width - 2.0 * GRILLE_BORDER_INSET
    airflow_height = fan_height - 2.0 * GRILLE_BORDER_INSET
    airflow_cut = add_box(
        "Square_Airflow_Opening",
        (airflow_width, airflow_height, FRONT_THICKNESS + 2.0 * BOOLEAN_OVERLAP),
        (0.0, 0.0, FRONT_THICKNESS / 2.0),
    )
    boolean_difference(cover, airflow_cut, "Cut_Airflow_Opening")

    add_wrap_walls(cover, inner_width, inner_height, outer_width, outer_height, total_depth)

    # Four clipped circles form the same flower/petal grille as the source.
    centers = (
        (0.0, fan_height / 2.0),
        (0.0, -fan_height / 2.0),
        (-fan_width / 2.0, 0.0),
        (fan_width / 2.0, 0.0),
    )
    for index, (x, y) in enumerate(centers, start=1):
        extension = BOOLEAN_OVERLAP * (1.0 + index * 0.25)
        ring = annular_prism(
            f"Petal_Circle_{index}",
            x,
            y,
            petal_radius - GRILLE_LINE_WIDTH / 2.0,
            petal_radius + GRILLE_LINE_WIDTH / 2.0,
            -extension,
            FRONT_THICKNESS + extension,
        )
        clip = add_box(
            f"Petal_Clip_{index}",
            (
                fan_width + 2.0 * BOOLEAN_OVERLAP,
                fan_height + 2.0 * BOOLEAN_OVERLAP,
                FRONT_THICKNESS + 2.0 * (extension + BOOLEAN_OVERLAP),
            ),
            (0.0, 0.0, FRONT_THICKNESS / 2.0),
        )
        boolean_intersection(ring, clip, f"Clip_Petal_{index}")
        boolean_union(cover, ring, f"Union_Petal_{index}")

    hub_extension = BOOLEAN_OVERLAP * 2.5
    hub = add_cylinder(
        "Grille_Center_Disk",
        hub_diameter / 2.0,
        -hub_extension,
        FRONT_THICKNESS + hub_extension,
    )
    boolean_union(cover, hub, "Union_Center_Disk")

    z_trim = add_box(
        "Final_Z_Trim",
        (
            outer_width + 2.0 * BOOLEAN_OVERLAP,
            outer_height + 2.0 * BOOLEAN_OVERLAP,
            total_depth,
        ),
        (0.0, 0.0, total_depth / 2.0),
    )
    boolean_intersection(cover, z_trim, "Trim_Grille_Thickness")

    add_retention_ribs(cover, inner_width, inner_height)
    cut_cable_notch(cover, inner_width, inner_height, total_depth)
    bevel_mesh(cover)
    recalc_normals(cover)
    triangulate(cover)
    recalc_normals(cover)
    cover.name = f"Wrapping_Fan_Cover_{FAN_SIZE_MM}mm"
    cover.data.name = cover.name + "_Mesh"

    non_manifold, shells = mesh_stats(cover)
    print(
        f"{cover.name}: preset={preset['reference']!r} fan={fan_width:g}x{fan_height:g}x{fan_depth:g} mm "
        f"cavity={inner_width:g}x{inner_height:g} mm total_depth={total_depth:g} mm "
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
    build_wrapping_fan_cover()
