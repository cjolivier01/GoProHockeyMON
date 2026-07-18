"""
Parametric bent horn / duct for Blender.

Run inside Blender:
    blender --python horn_parametric_blender.py

Units are millimeters. Edit the parameters in the CONFIG section below.

The key option is FLARE_MODE:
    "after_bend"    -> turn first, then expand in the outlet segment
    "through_bend"  -> expand during the bend, then keep the outlet constant
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.geometry import tessellate_polygon


# ---------------------------------------------------------------------------
# CONFIG

CLEAR_SCENE = True
EXPORT_STL = False
EXPORT_STL_PATH = "horn_parametric_blender.stl"

# Mesh quality.
RING_SEGMENTS = 96
INLET_SECTIONS = 5
BEND_SECTIONS = 10
OUTLET_SECTIONS = 12
FLANGE_CORNER_SEGMENTS = 8

# Duct dimensions.
WALL_THICKNESS = 1.6
INLET_INNER_DIAMETER = 35.8
OUTLET_INNER_DIAMETER = 63.4

# Centerline dimensions.
INLET_STRAIGHT_LENGTH = 6.0
BEND_ANGLE_DEG = 45.0
BEND_Z_SIGN = 1.0
BEND_RADIUS = 32.0
OUTLET_LENGTH = 2.0

# "after_bend" or "through_bend".
FLARE_MODE = "through_bend"

# Inlet flange.
INLET_FLANGE_ENABLED = True
INLET_FLANGE_WIDTH = 44.0
INLET_FLANGE_HEIGHT = 44.0
INLET_FLANGE_THICKNESS = 3.0
INLET_FLANGE_CORNER_RADIUS = 2.0
INLET_FLANGE_OVERLAP = 0.8
INLET_FLANGE_BORE_CLEARANCE = 0.15

# Inlet bolt pattern.
INLET_BOLT_HOLES_ENABLED = True
INLET_BOLT_SPACING_Y = 34.0
INLET_BOLT_SPACING_Z = 34.0
INLET_BOLT_HOLE_DIAMETER = 4.2

# Optional short straight lip at the outlet mouth.
OUTLET_LIP_ENABLED = False
OUTLET_LIP_LENGTH = 2.0

# Join the separate duct/flange/lip objects into one mesh with Blender booleans.
# Disable this if you want the editable source objects kept separate.
BOOLEAN_UNION_PARTS = True
BOOLEAN_SOLVER = "EXACT"

SHOW_CENTERLINE = False


# ---------------------------------------------------------------------------
# Geometry helpers


def clamp(value: float, lo: float, hi: float) -> float:
    return min(max(value, lo), hi)


def rotate_y(point: tuple[float, float, float], angle_rad: float) -> tuple[float, float, float]:
    x, y, z = point
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return (c * x + s * z, y, -s * x + c * z)


def throat_outer_radius() -> float:
    return INLET_INNER_DIAMETER / 2.0 + WALL_THICKNESS


def final_outer_radius() -> float:
    return OUTLET_INNER_DIAMETER / 2.0 + WALL_THICKNESS


def section_count() -> int:
    return INLET_SECTIONS + BEND_SECTIONS + OUTLET_SECTIONS + 1


def flare_fraction_at(k: int) -> float:
    if FLARE_MODE == "through_bend":
        return clamp((k - INLET_SECTIONS) / max(BEND_SECTIONS, 1), 0.0, 1.0)
    if FLARE_MODE == "after_bend":
        return clamp(
            (k - INLET_SECTIONS - BEND_SECTIONS) / max(OUTLET_SECTIONS, 1),
            0.0,
            1.0,
        )
    raise ValueError('FLARE_MODE must be "after_bend" or "through_bend"')


def outer_radius_at(k: int) -> float:
    return throat_outer_radius() + (
        final_outer_radius() - throat_outer_radius()
    ) * flare_fraction_at(k)


def inner_radius_at(k: int) -> float:
    return max(outer_radius_at(k) - WALL_THICKNESS, 0.1)


def inlet_center(i: int) -> tuple[float, float, float]:
    t = i / max(INLET_SECTIONS, 1)
    a = math.radians(BEND_ANGLE_DEG)
    return (
        INLET_STRAIGHT_LENGTH * t * math.cos(a),
        0.0,
        BEND_Z_SIGN * INLET_STRAIGHT_LENGTH * t * math.sin(a),
    )


def bend_center(i: int) -> tuple[float, float, float]:
    u = i / max(BEND_SECTIONS, 1)
    bend_angle = math.radians(BEND_ANGLE_DEG)
    theta = bend_angle * (1.0 - u)
    p = inlet_center(INLET_SECTIONS)
    return (
        p[0] + BEND_RADIUS * (math.sin(bend_angle) - math.sin(theta)),
        0.0,
        p[2] + BEND_Z_SIGN * BEND_RADIUS * (math.cos(theta) - math.cos(bend_angle)),
    )


def outlet_center(i: int) -> tuple[float, float, float]:
    t = i / max(OUTLET_SECTIONS, 1)
    p = bend_center(BEND_SECTIONS)
    return (p[0] + OUTLET_LENGTH * t, 0.0, p[2])


def section_center(k: int) -> tuple[float, float, float]:
    if k <= INLET_SECTIONS:
        return inlet_center(k)
    if k <= INLET_SECTIONS + BEND_SECTIONS:
        return bend_center(k - INLET_SECTIONS)
    return outlet_center(k - INLET_SECTIONS - BEND_SECTIONS)


def section_angle(k: int) -> float:
    if k <= INLET_SECTIONS:
        return math.radians(BEND_Z_SIGN * BEND_ANGLE_DEG)
    if k <= INLET_SECTIONS + BEND_SECTIONS:
        u = (k - INLET_SECTIONS) / max(BEND_SECTIONS, 1)
        return math.radians(BEND_Z_SIGN * BEND_ANGLE_DEG * (1.0 - u))
    return 0.0


def ring_point(k: int, j: int, radius: float) -> tuple[float, float, float]:
    c = section_center(k)
    a = section_angle(k)
    phi = 2.0 * math.pi * j / RING_SEGMENTS
    y_component = radius * math.cos(phi)
    normal_component = radius * math.sin(phi)
    normal = (-math.sin(a), 0.0, math.cos(a))
    return (
        c[0] + normal[0] * normal_component,
        c[1] + y_component,
        c[2] + normal[2] * normal_component,
    )


def create_mesh_object(name: str, vertices: list[tuple[float, float, float]], faces: list[list[int]]):
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(clean_customdata=True)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    recalc_normals(obj)
    return obj


def recalc_normals(obj) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")


# ---------------------------------------------------------------------------
# Duct mesh


def create_duct_object():
    n_sections = section_count()

    vertices = []
    for k in range(n_sections):
        for j in range(RING_SEGMENTS):
            vertices.append(ring_point(k, j, outer_radius_at(k)))
    for k in range(n_sections):
        for j in range(RING_SEGMENTS):
            vertices.append(ring_point(k, j, inner_radius_at(k)))

    def outer_i(k: int, j: int) -> int:
        return k * RING_SEGMENTS + (j % RING_SEGMENTS)

    def inner_i(k: int, j: int) -> int:
        return n_sections * RING_SEGMENTS + k * RING_SEGMENTS + (j % RING_SEGMENTS)

    faces = []
    for k in range(n_sections - 1):
        for j in range(RING_SEGMENTS):
            faces.append([outer_i(k + 1, j), outer_i(k + 1, j + 1), outer_i(k, j + 1)])
            faces.append([outer_i(k + 1, j), outer_i(k, j + 1), outer_i(k, j)])

            faces.append([inner_i(k, j), inner_i(k, j + 1), inner_i(k + 1, j + 1)])
            faces.append([inner_i(k, j), inner_i(k + 1, j + 1), inner_i(k + 1, j)])

    for j in range(RING_SEGMENTS):
        faces.append([inner_i(0, j + 1), inner_i(0, j), outer_i(0, j)])
        faces.append([inner_i(0, j + 1), outer_i(0, j), outer_i(0, j + 1)])

        last = n_sections - 1
        faces.append([inner_i(last, j), inner_i(last, j + 1), outer_i(last, j + 1)])
        faces.append([inner_i(last, j), outer_i(last, j + 1), outer_i(last, j)])

    obj = create_mesh_object("Parametric_Horn_Duct", vertices, faces)
    shade_smooth(obj)
    return obj


# ---------------------------------------------------------------------------
# Flange and outlet lip


def rounded_rect_loop(width: float, height: float, radius: float, segments: int):
    r = min(max(radius, 0.0), width / 2.0, height / 2.0)
    if r == 0:
        return [
            (width / 2.0, -height / 2.0),
            (width / 2.0, height / 2.0),
            (-width / 2.0, height / 2.0),
            (-width / 2.0, -height / 2.0),
        ]

    points = []
    centers = [
        (width / 2.0 - r, height / 2.0 - r, 0.0, 90.0),
        (-width / 2.0 + r, height / 2.0 - r, 90.0, 180.0),
        (-width / 2.0 + r, -height / 2.0 + r, 180.0, 270.0),
        (width / 2.0 - r, -height / 2.0 + r, 270.0, 360.0),
    ]
    for cy, cz, a0, a1 in centers:
        for i in range(segments + 1):
            if points and i == 0:
                continue
            a = math.radians(a0 + (a1 - a0) * i / segments)
            points.append((cy + r * math.cos(a), cz + r * math.sin(a)))
    return points


def circle_loop(cy: float, cz: float, radius: float, segments: int, clockwise: bool):
    if clockwise:
        indexes = range(segments, 0, -1)
    else:
        indexes = range(segments)
    return [
        (
            cy + radius * math.cos(2.0 * math.pi * i / segments),
            cz + radius * math.sin(2.0 * math.pi * i / segments),
        )
        for i in indexes
    ]


def transform_flange_point(local: tuple[float, float, float]) -> tuple[float, float, float]:
    angle = math.radians(-BEND_Z_SIGN * BEND_ANGLE_DEG)
    return rotate_y(local, angle)


def create_flange_object():
    thickness = INLET_FLANGE_THICKNESS + INLET_FLANGE_OVERLAP
    x0 = -INLET_FLANGE_THICKNESS
    x1 = INLET_FLANGE_OVERLAP

    loops = [
        rounded_rect_loop(
            INLET_FLANGE_WIDTH,
            INLET_FLANGE_HEIGHT,
            INLET_FLANGE_CORNER_RADIUS,
            FLANGE_CORNER_SEGMENTS,
        )
    ]
    loops.append(
        circle_loop(
            0.0,
            0.0,
            INLET_INNER_DIAMETER / 2.0 + INLET_FLANGE_BORE_CLEARANCE,
            RING_SEGMENTS,
            clockwise=True,
        )
    )

    if INLET_BOLT_HOLES_ENABLED:
        for sy in (-1, 1):
            for sz in (-1, 1):
                loops.append(
                    circle_loop(
                        sy * INLET_BOLT_SPACING_Y / 2.0,
                        sz * INLET_BOLT_SPACING_Z / 2.0,
                        INLET_BOLT_HOLE_DIAMETER / 2.0,
                        max(24, RING_SEGMENTS // 4),
                        clockwise=True,
                    )
                )

    flat_2d = [point for loop in loops for point in loop]
    loop_offsets = []
    offset = 0
    for loop in loops:
        loop_offsets.append(offset)
        offset += len(loop)

    tess_loops = [[Vector((y, z, 0.0)) for y, z in loop] for loop in loops]
    triangles = tessellate_polygon(tess_loops)

    vertices = []
    for x in (x0, x1):
        for y, z in flat_2d:
            vertices.append(transform_flange_point((x, y, z)))

    front_offset = len(flat_2d)
    faces = []
    for tri in triangles:
        faces.append([front_offset + tri[0], front_offset + tri[1], front_offset + tri[2]])
        faces.append([tri[2], tri[1], tri[0]])

    for loop_index, loop in enumerate(loops):
        start = loop_offsets[loop_index]
        n = len(loop)
        for i in range(n):
            a = start + i
            b = start + ((i + 1) % n)
            if loop_index == 0:
                faces.append([a, b, front_offset + b])
                faces.append([a, front_offset + b, front_offset + a])
            else:
                faces.append([b, a, front_offset + a])
                faces.append([b, front_offset + a, front_offset + b])

    obj = create_mesh_object("Parametric_Horn_Inlet_Flange", vertices, faces)
    shade_flat(obj)
    return obj


def create_outlet_lip_object():
    last = section_count() - 1
    radius_outer = outer_radius_at(last)
    radius_inner = inner_radius_at(last)
    center = section_center(last)
    x0 = center[0]
    x1 = center[0] + OUTLET_LIP_LENGTH

    vertices = []
    for x in (x0, x1):
        for r in (radius_outer, radius_inner):
            for j in range(RING_SEGMENTS):
                phi = 2.0 * math.pi * j / RING_SEGMENTS
                vertices.append((x, r * math.cos(phi), center[2] + r * math.sin(phi)))

    def idx(x_layer: int, ring: int, j: int) -> int:
        return x_layer * 2 * RING_SEGMENTS + ring * RING_SEGMENTS + (j % RING_SEGMENTS)

    faces = []
    for j in range(RING_SEGMENTS):
        faces.append([idx(1, 0, j), idx(1, 0, j + 1), idx(0, 0, j + 1)])
        faces.append([idx(1, 0, j), idx(0, 0, j + 1), idx(0, 0, j)])

        faces.append([idx(0, 1, j), idx(0, 1, j + 1), idx(1, 1, j + 1)])
        faces.append([idx(0, 1, j), idx(1, 1, j + 1), idx(1, 1, j)])

        faces.append([idx(0, 1, j + 1), idx(0, 1, j), idx(0, 0, j)])
        faces.append([idx(0, 1, j + 1), idx(0, 0, j), idx(0, 0, j + 1)])

        faces.append([idx(1, 1, j), idx(1, 1, j + 1), idx(1, 0, j + 1)])
        faces.append([idx(1, 1, j), idx(1, 0, j + 1), idx(1, 0, j)])

    obj = create_mesh_object("Parametric_Horn_Outlet_Lip", vertices, faces)
    shade_smooth(obj)
    return obj


# ---------------------------------------------------------------------------
# Blender scene operations


def shade_smooth(obj) -> None:
    for poly in obj.data.polygons:
        poly.use_smooth = True


def shade_flat(obj) -> None:
    for poly in obj.data.polygons:
        poly.use_smooth = False


def boolean_union(base_obj, operand_obj):
    bpy.context.view_layer.objects.active = base_obj
    base_obj.select_set(True)
    modifier = base_obj.modifiers.new("Union_" + operand_obj.name, "BOOLEAN")
    modifier.operation = "UNION"
    modifier.object = operand_obj
    modifier.solver = BOOLEAN_SOLVER
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(operand_obj, do_unlink=True)
    recalc_normals(base_obj)
    return base_obj


def add_centerline_markers() -> None:
    material = bpy.data.materials.new("Centerline_Red")
    material.diffuse_color = (1.0, 0.0, 0.0, 1.0)
    for k in range(section_count()):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, radius=0.9, location=section_center(k))
        bpy.context.object.data.materials.append(material)


def set_units() -> None:
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 0.001


def export_stl(obj) -> None:
    path = Path(EXPORT_STL_PATH)
    if not path.is_absolute():
        blend_path = Path(bpy.data.filepath).parent if bpy.data.filepath else Path.cwd()
        path = blend_path / path

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(filepath=str(path), export_selected_objects=True)
    else:
        bpy.ops.export_mesh.stl(filepath=str(path), use_selection=True)


def build_horn():
    if CLEAR_SCENE:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()

    set_units()

    duct = create_duct_object()
    parts = [duct]

    if INLET_FLANGE_ENABLED:
        parts.append(create_flange_object())

    if OUTLET_LIP_ENABLED:
        parts.append(create_outlet_lip_object())

    final_obj = duct
    if BOOLEAN_UNION_PARTS:
        for part in parts[1:]:
            final_obj = boolean_union(final_obj, part)
    else:
        bpy.ops.object.select_all(action="DESELECT")
        for part in parts:
            part.select_set(True)
        bpy.context.view_layer.objects.active = final_obj

    final_obj.name = "Parametric_Horn"
    final_obj.data.name = "Parametric_Horn_Mesh"

    if SHOW_CENTERLINE:
        add_centerline_markers()

    if EXPORT_STL:
        export_stl(final_obj)

    return final_obj


if __name__ == "__main__":
    build_horn()

