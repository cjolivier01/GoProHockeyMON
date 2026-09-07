"""
Parametric bent horn / duct for Blender.

Run inside Blender:
    blender --python horn_parametric_blender.py

Units are millimeters. Edit the parameters in the CONFIG section below.
Select the standard fan mounted at each end with INLET_FAN_SIZE_MM and
OUTLET_FAN_SIZE_MM.  Their shared presets drive the duct openings, flange
footprints, mounting-hole patterns, and mounting-hole diameters.

Blender 5.2 or newer is required for the watertight manifold flange unions.

The key option is FLARE_MODE:
    "after_bend"    -> turn first, then expand in the outlet segment
    "through_bend"  -> expand during the bend, then keep the outlet constant
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.geometry import tessellate_polygon


def find_fan_preset_directory() -> Path:
    """Locate fan_size_presets.py for file and Blender Text Editor runs."""
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
    candidates.extend(directory.parent / "common" for directory in tuple(candidates))

    searched = []
    for directory in candidates:
        if directory in searched:
            continue
        searched.append(directory)
        module_path = directory / "fan_size_presets.py"
        if not module_path.is_file():
            continue
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
            if loaded_path != module_path.resolve():
                del sys.modules["fan_size_presets"]
        return directory
    raise ModuleNotFoundError(
        "Could not locate fan_size_presets.py. Searched: "
        + ", ".join(str(path) for path in searched)
    )


FAN_PRESET_DIRECTORY = find_fan_preset_directory()

from fan_size_presets import get_standard_fan_preset  # noqa: E402


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

# Fan interfaces. Supported sizes come from common/fan_size_presets.py.
# These two selections resolve all fan-specific dimensions at build time.
INLET_FAN_SIZE_MM = 40
OUTLET_FAN_SIZE_MM = 40

# Duct construction.
WALL_THICKNESS = 1.6

# Centerline dimensions.
INLET_STRAIGHT_LENGTH = 6.0
BEND_ANGLE_DEG = 35.0
BEND_Z_SIGN = 1.0
# Minimum centerline radius. Larger fan selections automatically increase the
# effective radius enough to keep the inside of the swept duct from folding
# through itself.
BEND_RADIUS = 45.0
OUTLET_LENGTH = 2.0

# "after_bend" or "through_bend".
FLARE_MODE = "through_bend"

# Standard fan flanges. Frame size, central opening, mounting-hole spacing,
# and mounting-hole diameter are derived independently for each selected end.
INLET_FLANGE_ENABLED = True
OUTLET_FLANGE_ENABLED = True
INLET_MOUNTING_HOLES_ENABLED = True
OUTLET_MOUNTING_HOLES_ENABLED = True
FLANGE_THICKNESS = 3.0
FLANGE_CORNER_RADIUS = 2.0
FLANGE_OVERLAP = 0.8
FLANGE_BORE_CLEARANCE = 0.15

# Optional short straight lip at the outlet mouth.
OUTLET_LIP_ENABLED = False
OUTLET_LIP_LENGTH = 2.0

# Join the separate duct/flange/lip objects into one mesh with Blender booleans.
# Disable this if you want the editable source objects kept separate.
BOOLEAN_UNION_PARTS = True
# Blender 5.2's manifold solver keeps both flange unions watertight. The
# legacy exact solver leaves open edge fans where these tessellated flanges
# meet the swept duct.
BOOLEAN_SOLVER = "MANIFOLD"
MINIMUM_BLENDER_VERSION = (5, 2, 0)
BOOLEAN_CLEANUP_DISTANCE = 1.0e-6

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


def inlet_fan_preset():
    return get_standard_fan_preset(INLET_FAN_SIZE_MM)


def outlet_fan_preset():
    return get_standard_fan_preset(OUTLET_FAN_SIZE_MM)


def throat_outer_radius() -> float:
    return float(inlet_fan_preset()["opening"]) / 2.0 + WALL_THICKNESS


def final_outer_radius() -> float:
    return float(outlet_fan_preset()["opening"]) / 2.0 + WALL_THICKNESS


def effective_bend_radius() -> float:
    minimum_for_duct = max(throat_outer_radius(), final_outer_radius()) + (
        2.0 * WALL_THICKNESS
    )
    return max(BEND_RADIUS, minimum_for_duct)


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
    radius = effective_bend_radius()
    return (
        p[0] + radius * (math.sin(bend_angle) - math.sin(theta)),
        0.0,
        p[2]
        + BEND_Z_SIGN * radius * (math.cos(theta) - math.cos(bend_angle)),
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


def transform_flange_point(
    local: tuple[float, float, float], end_name: str
) -> tuple[float, float, float]:
    if end_name == "inlet":
        angle = math.radians(-BEND_Z_SIGN * BEND_ANGLE_DEG)
        return rotate_y(local, angle)
    if end_name == "outlet":
        center = section_center(section_count() - 1)
        return (
            center[0] + local[0],
            center[1] + local[1],
            center[2] + local[2],
        )
    raise ValueError(f"Unknown flange end {end_name!r}")


def create_flange_object(end_name: str):
    if end_name == "inlet":
        preset = inlet_fan_preset()
        x0 = -FLANGE_THICKNESS
        x1 = FLANGE_OVERLAP
        mounting_holes_enabled = INLET_MOUNTING_HOLES_ENABLED
    elif end_name == "outlet":
        preset = outlet_fan_preset()
        x0 = -FLANGE_OVERLAP
        x1 = FLANGE_THICKNESS
        mounting_holes_enabled = OUTLET_MOUNTING_HOLES_ENABLED
    else:
        raise ValueError(f"Unknown flange end {end_name!r}")

    frame = float(preset["frame"])
    opening = float(preset["opening"])
    hole_spacing = float(preset["hole_spacing"])
    hole_diameter = float(preset["hole_diameter"])

    loops = [
        rounded_rect_loop(
            frame,
            frame,
            FLANGE_CORNER_RADIUS,
            FLANGE_CORNER_SEGMENTS,
        )
    ]
    loops.append(
        circle_loop(
            0.0,
            0.0,
            opening / 2.0 + FLANGE_BORE_CLEARANCE,
            RING_SEGMENTS,
            clockwise=True,
        )
    )

    if mounting_holes_enabled:
        for sy in (-1, 1):
            for sz in (-1, 1):
                loops.append(
                    circle_loop(
                        sy * hole_spacing / 2.0,
                        sz * hole_spacing / 2.0,
                        hole_diameter / 2.0,
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
            vertices.append(transform_flange_point((x, y, z), end_name))

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

    obj = create_mesh_object(
        f"Parametric_Horn_{end_name.title()}_Flange", vertices, faces
    )
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
    cleanup_boolean_mesh(base_obj)
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


def validate_configuration() -> None:
    if BOOLEAN_UNION_PARTS and bpy.app.version < MINIMUM_BLENDER_VERSION:
        required = ".".join(str(value) for value in MINIMUM_BLENDER_VERSION)
        detected = ".".join(str(value) for value in bpy.app.version)
        raise RuntimeError(
            f"Blender {required} or newer is required for manifold flange "
            f"unions; detected {detected}"
        )
    if RING_SEGMENTS < 12:
        raise ValueError("RING_SEGMENTS must be at least 12")
    if min(INLET_SECTIONS, BEND_SECTIONS, OUTLET_SECTIONS) < 1:
        raise ValueError("Every centerline section count must be at least 1")
    if WALL_THICKNESS <= 0.0:
        raise ValueError("WALL_THICKNESS must be positive")
    if FLANGE_THICKNESS <= 0.0 or FLANGE_OVERLAP <= 0.0:
        raise ValueError("Flange thickness and overlap must be positive")
    if FLANGE_BORE_CLEARANCE < 0.0:
        raise ValueError("FLANGE_BORE_CLEARANCE cannot be negative")
    if BEND_RADIUS <= 0.0:
        raise ValueError("BEND_RADIUS must be positive")
    if BEND_Z_SIGN not in (-1.0, 1.0):
        raise ValueError("BEND_Z_SIGN must be -1.0 or 1.0")
    flare_fraction_at(section_count() - 1)

    for end_name, preset in (
        ("inlet", inlet_fan_preset()),
        ("outlet", outlet_fan_preset()),
    ):
        frame = float(preset["frame"])
        opening = float(preset["opening"])
        spacing = float(preset["hole_spacing"])
        hole_diameter = float(preset["hole_diameter"])
        if opening + 2.0 * WALL_THICKNESS >= frame:
            raise ValueError(
                f"The {end_name} duct outer diameter does not fit its "
                f"{frame:g} mm standard fan frame"
            )
        if opening + 2.0 * FLANGE_BORE_CLEARANCE >= frame:
            raise ValueError(
                f"The {end_name} flange bore does not fit its "
                f"{frame:g} mm standard fan frame"
            )
        if spacing / 2.0 + hole_diameter / 2.0 >= frame / 2.0:
            raise ValueError(
                f"The {end_name} mounting holes exceed its "
                f"{frame:g} mm standard fan frame"
            )


def build_horn():
    validate_configuration()

    if CLEAR_SCENE:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()

    set_units()

    duct = create_duct_object()
    parts = [duct]

    if INLET_FLANGE_ENABLED:
        parts.append(create_flange_object("inlet"))

    if OUTLET_FLANGE_ENABLED:
        parts.append(create_flange_object("outlet"))

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
