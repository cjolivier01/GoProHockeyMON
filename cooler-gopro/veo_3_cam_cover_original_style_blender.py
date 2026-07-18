"""Original-style Veo Cam 3 cover reconstruction for Blender.

This is deliberately a simpler starting point than the configurable enclosed
case generator.  It rebuilds the *spirit* of ``veo_3_cam_cover.stl`` as one
clean, open-bottom protective shell with:

* the same approximate 215 x 234 x 71 mm envelope,
* a broad rounded body and domed roof,
* two camera openings on the same side of the body,
* camera axes angled apart in plan, and
* one projecting eyelid/visor directly above each camera opening.

Run inside Blender::

    /tmp/blender-apt/root/usr/bin/blender \
      --background --factory-startup \
      --python veo_3_cam_cover_original_style_blender.py

All dimensions are millimeters.  X is body width, Y is body depth, and Z is
height.  Camera azimuths are measured counter-clockwise from +X when viewed
from above.  Dominant surfaces around the source openings point near 124 and
236 degrees; the angle remains a single configurable value because the
triangulated source does not expose an exact optical axis.
"""

from __future__ import annotations

import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


# ---------------------------------------------------------------------------
# CONFIG

CLEAR_SCENE = True
EXPORT_STL = False
EXPORT_DIRECTORY = ""
OUTPUT_STL_NAME = "veo_3_cam_cover_original_style.stl"

RENDER_PREVIEW = False
PREVIEW_PATH = "veo_3_cam_cover_original_style.png"
PREVIEW_RESOLUTION_X = 1100
PREVIEW_RESOLUTION_Y = 850

# Source STL envelope: 215.167 x 233.661 x 70.653 mm.
BODY_WIDTH = 215.167
BODY_DEPTH = 189.0
BODY_HEIGHT = 70.653
BODY_WALL_THICKNESS = 3.2
ROOF_THICKNESS = 3.2
FOOTPRINT_EXPONENT = 3.2  # 2=ellipse; larger is more rectangular
FOOTPRINT_POINTS = 192

# (Z, XY scale) controls the lower edge, vertical skirt, shoulder, and dome.
BODY_SECTIONS = (
    (0.0, 0.96),
    (6.0, 0.99),
    (12.0, 1.00),
    (49.0, 1.00),
    (58.0, 0.995),
    (65.0, 0.97),
    (BODY_HEIGHT, 0.88),
)

# Both camera openings sit on the -X half of the shell.  The default follows
# the source mesh's dominant opening-surround directions.
CAMERA_CENTERLINE_AZIMUTH_DEG = 180.0
CAMERA_HALF_ANGLE_DEG = 56.0
CAMERA_AZIMUTHS_DEG = (
    CAMERA_CENTERLINE_AZIMUTH_DEG - CAMERA_HALF_ANGLE_DEG,
    CAMERA_CENTERLINE_AZIMUTH_DEG + CAMERA_HALF_ANGLE_DEG,
)

EYE_CENTER_Z = 26.0
EYE_OPENING_WIDTH = 58.0
EYE_OPENING_HEIGHT = 36.0
EYE_OPENING_CORNER_RADIUS = 11.0

# Raised surround around each opening.
EYE_BEZEL_WIDTH = 68.0
EYE_BEZEL_HEIGHT = 46.0
EYE_BEZEL_CORNER_RADIUS = 14.5
EYE_BEZEL_INSET = 8.0
EYE_BEZEL_PROJECTION = 1.5

# The eyelid is a tapered wedge whose lower/front edge overhangs the eye.
VISORS_ENABLED = True
VISOR_BACK_WIDTH = 108.0
VISOR_FRONT_WIDTH = 58.0
VISOR_BACK_INSET = 11.0
VISOR_PROJECTION = 14.0
VISOR_BACK_BOTTOM_Z = 48.5
VISOR_BACK_TOP_Z = 59.0
VISOR_FRONT_BOTTOM_Z = 48.0
VISOR_FRONT_TOP_Z = 54.0
VISOR_EDGE_RADIUS = 1.5

# Geometry quality.
ROUNDED_CORNER_SEGMENTS = 14
BOOLEAN_SOLVER = "EXACT"
BOOLEAN_OVERLAP = 0.25
BOOLEAN_CLEANUP_DISTANCE = 0.0001

COVER_COLOR = (0.10, 0.38, 0.72, 1.0)


# ---------------------------------------------------------------------------
# Configuration and scene helpers


def validate_config() -> None:
    positive = {
        "BODY_WIDTH": BODY_WIDTH,
        "BODY_DEPTH": BODY_DEPTH,
        "BODY_HEIGHT": BODY_HEIGHT,
        "BODY_WALL_THICKNESS": BODY_WALL_THICKNESS,
        "ROOF_THICKNESS": ROOF_THICKNESS,
        "EYE_OPENING_WIDTH": EYE_OPENING_WIDTH,
        "EYE_OPENING_HEIGHT": EYE_OPENING_HEIGHT,
        "EYE_BEZEL_WIDTH": EYE_BEZEL_WIDTH,
        "EYE_BEZEL_HEIGHT": EYE_BEZEL_HEIGHT,
        "VISOR_BACK_WIDTH": VISOR_BACK_WIDTH,
        "VISOR_FRONT_WIDTH": VISOR_FRONT_WIDTH,
    }
    for name, value in positive.items():
        if value <= 0.0:
            raise ValueError(f"{name} must be positive")
    if FOOTPRINT_EXPONENT < 2.0:
        raise ValueError("FOOTPRINT_EXPONENT must be at least 2")
    if FOOTPRINT_POINTS < 32 or FOOTPRINT_POINTS % 4:
        raise ValueError("FOOTPRINT_POINTS must be a multiple of four and at least 32")
    if tuple(z for z, _ in BODY_SECTIONS) != tuple(
        sorted(z for z, _ in BODY_SECTIONS)
    ):
        raise ValueError("BODY_SECTIONS must be ordered by increasing Z")
    if BODY_SECTIONS[0][0] != 0.0 or BODY_SECTIONS[-1][0] != BODY_HEIGHT:
        raise ValueError("BODY_SECTIONS must span Z=0 through BODY_HEIGHT")
    if EYE_OPENING_WIDTH >= EYE_BEZEL_WIDTH or EYE_OPENING_HEIGHT >= EYE_BEZEL_HEIGHT:
        raise ValueError("Eye openings must fit inside the bezels")
    if EYE_CENTER_Z - EYE_BEZEL_HEIGHT / 2.0 < 0.0:
        raise ValueError("Eye bezel extends below the cover")
    if VISORS_ENABLED and VISOR_BACK_BOTTOM_Z > VISOR_BACK_TOP_Z:
        raise ValueError("Visor back Z values are reversed")
    if VISORS_ENABLED and VISOR_FRONT_BOTTOM_Z > VISOR_FRONT_TOP_Z:
        raise ValueError("Visor front Z values are reversed")


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


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


def cleanup_mesh(obj) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=BOOLEAN_CLEANUP_DISTANCE)
    bmesh.ops.dissolve_degenerate(
        bm, edges=list(bm.edges), dist=BOOLEAN_CLEANUP_DISTANCE
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
# Mesh primitives


def superellipse_loop(width: float, depth: float):
    power = 2.0 / FOOTPRINT_EXPONENT
    points = []
    for index in range(FOOTPRINT_POINTS):
        angle = 2.0 * math.pi * index / FOOTPRINT_POINTS
        cosine = math.cos(angle)
        sine = math.sin(angle)
        points.append(
            (
                width / 2.0 * math.copysign(abs(cosine) ** power, cosine),
                depth / 2.0 * math.copysign(abs(sine) ** power, sine),
            )
        )
    return points


def rounded_rectangle_loop(width: float, height: float, radius: float):
    radius = min(max(radius, 0.0), width / 2.0, height / 2.0)
    points = []
    corners = (
        (width / 2.0 - radius, height / 2.0 - radius, 0.0, 90.0),
        (-width / 2.0 + radius, height / 2.0 - radius, 90.0, 180.0),
        (-width / 2.0 + radius, -height / 2.0 + radius, 180.0, 270.0),
        (width / 2.0 - radius, -height / 2.0 + radius, 270.0, 360.0),
    )
    for cx, cz, angle0, angle1 in corners:
        for step in range(ROUNDED_CORNER_SEGMENTS):
            angle = math.radians(
                angle0 + (angle1 - angle0) * step / ROUNDED_CORNER_SEGMENTS
            )
            points.append((cx + radius * math.cos(angle), cz + radius * math.sin(angle)))
    return points


def loft_solid(name: str, sections):
    count = len(sections[0][1])
    if len(sections) < 2 or any(len(loop) != count for _, loop in sections):
        raise ValueError("Loft requires at least two equal-length loops")
    vertices = []
    for z, loop in sections:
        vertices.extend((x, y, z) for x, y in loop)

    def vertex(section, index):
        return section * count + index % count

    faces = []
    for section in range(len(sections) - 1):
        for index in range(count):
            faces.append(
                [
                    vertex(section, index),
                    vertex(section, index + 1),
                    vertex(section + 1, index + 1),
                    vertex(section + 1, index),
                ]
            )
    bottom_center = len(vertices)
    vertices.append((0.0, 0.0, sections[0][0]))
    top_center = len(vertices)
    vertices.append((0.0, 0.0, sections[-1][0]))
    last = len(sections) - 1
    for index in range(count):
        faces.append([bottom_center, vertex(0, index + 1), vertex(0, index)])
        faces.append([top_center, vertex(last, index), vertex(last, index + 1)])
    return create_mesh_object(name, vertices, faces)


def body_scale_at_z(z: float) -> float:
    if z <= BODY_SECTIONS[0][0]:
        return BODY_SECTIONS[0][1]
    if z >= BODY_SECTIONS[-1][0]:
        return BODY_SECTIONS[-1][1]
    for (z0, scale0), (z1, scale1) in zip(BODY_SECTIONS, BODY_SECTIONS[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            t = t * t * (3.0 - 2.0 * t)
            return scale0 + (scale1 - scale0) * t
    raise RuntimeError("Could not interpolate body scale")


def radial_surface_distance(angle_deg: float) -> float:
    angle = math.radians(angle_deg)
    cosine = abs(math.cos(angle))
    sine = abs(math.sin(angle))
    denominator = (
        (cosine / (BODY_WIDTH / 2.0)) ** FOOTPRINT_EXPONENT
        + (sine / (BODY_DEPTH / 2.0)) ** FOOTPRINT_EXPONENT
    )
    return denominator ** (-1.0 / FOOTPRINT_EXPONENT)


def axis_point(angle_deg: float, radial: float, tangent: float, z: float):
    angle = math.radians(angle_deg)
    normal = Vector((math.cos(angle), math.sin(angle), 0.0))
    side = Vector((-math.sin(angle), math.cos(angle), 0.0))
    return normal * radial + side * tangent + Vector((0.0, 0.0, z))


def rounded_rectangle_prism_axis(
    name: str,
    angle_deg: float,
    radial0: float,
    radial1: float,
    width: float,
    height: float,
    radius: float,
    center_z: float,
):
    loop = rounded_rectangle_loop(width, height, radius)
    count = len(loop)
    vertices = []
    for radial in (radial0, radial1):
        vertices.extend(
            tuple(axis_point(angle_deg, radial, tangent, center_z + local_z))
            for tangent, local_z in loop
        )
    low_center = len(vertices)
    vertices.append(tuple(axis_point(angle_deg, radial0, 0.0, center_z)))
    high_center = len(vertices)
    vertices.append(tuple(axis_point(angle_deg, radial1, 0.0, center_z)))
    faces = []
    for index in range(count):
        next_index = (index + 1) % count
        faces.append([index, count + index, count + next_index, next_index])
        faces.append([low_center, next_index, index])
        faces.append([high_center, count + index, count + next_index])
    return create_mesh_object(name, vertices, faces)


def visor_wedge(name: str, angle_deg: float, surface_radius: float):
    radial_back = surface_radius - VISOR_BACK_INSET
    radial_front = surface_radius + VISOR_PROJECTION
    back_half = VISOR_BACK_WIDTH / 2.0
    front_half = VISOR_FRONT_WIDTH / 2.0
    local_vertices = (
        (radial_back, -back_half, VISOR_BACK_BOTTOM_Z),
        (radial_back, back_half, VISOR_BACK_BOTTOM_Z),
        (radial_back, back_half, VISOR_BACK_TOP_Z),
        (radial_back, -back_half, VISOR_BACK_TOP_Z),
        (radial_front, -front_half, VISOR_FRONT_BOTTOM_Z),
        (radial_front, front_half, VISOR_FRONT_BOTTOM_Z),
        (radial_front, front_half, VISOR_FRONT_TOP_Z),
        (radial_front, -front_half, VISOR_FRONT_TOP_Z),
    )
    vertices = [tuple(axis_point(angle_deg, radial, tangent, z)) for radial, tangent, z in local_vertices]
    faces = (
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (3, 7, 4, 0),
    )
    obj = create_mesh_object(name, vertices, faces)
    modifier = obj.modifiers.new(name + "_Soft_Edges", "BEVEL")
    modifier.width = VISOR_EDGE_RADIUS
    modifier.segments = 4
    modifier.affect = "EDGES"
    select_only(obj)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    recalc_normals(obj)
    return obj


# ---------------------------------------------------------------------------
# Booleans and construction


def select_only(obj) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def join_tools(name: str, objects):
    objects = list(objects)
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
    cleanup_mesh(base)
    recalc_normals(base)
    return base


def boolean_union(base, part, label="Union"):
    return apply_boolean(base, part, "UNION", label + "_" + part.name)


def boolean_difference(base, tools, label="Cut"):
    tools = list(tools)
    if not tools:
        return base
    return apply_boolean(base, join_tools(label + "_Tools", tools), "DIFFERENCE", label)


def create_cover():
    outer_sections = tuple(
        (z, superellipse_loop(BODY_WIDTH * scale, BODY_DEPTH * scale))
        for z, scale in BODY_SECTIONS
    )
    cover = loft_solid("Veo_3_Original_Style_Cover", outer_sections)

    cavity_top = BODY_HEIGHT - ROOF_THICKNESS
    cavity_z_values = [-BOOLEAN_OVERLAP]
    cavity_z_values.extend(z for z, _ in BODY_SECTIONS[1:-1] if z < cavity_top)
    cavity_z_values.append(cavity_top)
    cavity_sections = []
    for z in cavity_z_values:
        scale = body_scale_at_z(max(z, 0.0))
        cavity_sections.append(
            (
                z,
                superellipse_loop(
                    BODY_WIDTH * scale - 2.0 * BODY_WALL_THICKNESS,
                    BODY_DEPTH * scale - 2.0 * BODY_WALL_THICKNESS,
                ),
            )
        )
    boolean_difference(
        cover,
        [loft_solid("Open_Bottom_Inner_Cavity", cavity_sections)],
        "Open_Bottom_Inner_Cavity",
    )

    # Add the raised camera surrounds first, then place each eyelid directly
    # over its corresponding opening.
    for index, angle in enumerate(CAMERA_AZIMUTHS_DEG, start=1):
        surface = radial_surface_distance(angle)
        bezel = rounded_rectangle_prism_axis(
            f"Eye_{index}_Raised_Surround",
            angle,
            surface - EYE_BEZEL_INSET,
            surface + EYE_BEZEL_PROJECTION,
            EYE_BEZEL_WIDTH,
            EYE_BEZEL_HEIGHT,
            EYE_BEZEL_CORNER_RADIUS,
            EYE_CENTER_Z,
        )
        boolean_union(cover, bezel, f"Eye_{index}_Surround_Union")
        if VISORS_ENABLED:
            boolean_union(
                cover,
                visor_wedge(f"Eye_{index}_Eyelid_Visor", angle, surface),
                f"Eye_{index}_Visor_Union",
            )

    eye_cutters = []
    for index, angle in enumerate(CAMERA_AZIMUTHS_DEG, start=1):
        surface = radial_surface_distance(angle)
        eye_cutters.append(
            rounded_rectangle_prism_axis(
                f"Eye_{index}_Opening",
                angle,
                surface - BODY_WALL_THICKNESS - EYE_BEZEL_INSET,
                surface + EYE_BEZEL_PROJECTION + VISOR_PROJECTION + BOOLEAN_OVERLAP,
                EYE_OPENING_WIDTH,
                EYE_OPENING_HEIGHT,
                EYE_OPENING_CORNER_RADIUS,
                EYE_CENTER_Z,
            )
        )
    boolean_difference(cover, eye_cutters, "Paired_Camera_Openings")
    cover.name = "Veo_3_Cam_Cover_Original_Style"
    return cover


# ---------------------------------------------------------------------------
# Validation, export, and preview


def assign_material(obj) -> None:
    material = bpy.data.materials.get("Veo_Original_Style_Material")
    if material is None:
        material = bpy.data.materials.new("Veo_Original_Style_Material")
    material.diffuse_color = COVER_COLOR
    obj.data.materials.clear()
    obj.data.materials.append(material)


def triangulate_mesh(obj) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def non_manifold_edge_count(obj) -> int:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    count = sum(1 for edge in bm.edges if not edge.is_manifold)
    bm.free()
    return count


def connected_shell_count(obj) -> int:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    remaining = set(bm.faces)
    shell_count = 0
    while remaining:
        shell_count += 1
        stack = [remaining.pop()]
        while stack:
            face = stack.pop()
            for edge in face.edges:
                for linked in edge.link_faces:
                    if linked in remaining:
                        remaining.remove(linked)
                        stack.append(linked)
    bm.free()
    return shell_count


def validate_object(obj) -> None:
    non_manifold = non_manifold_edge_count(obj)
    shells = connected_shell_count(obj)
    dimensions = tuple(round(value, 3) for value in obj.dimensions)
    print(
        f"VALIDATION {obj.name}: dimensions={dimensions} "
        f"vertices={len(obj.data.vertices)} faces={len(obj.data.polygons)} "
        f"non_manifold_edges={non_manifold} connected_shells={shells}"
    )
    if non_manifold:
        raise RuntimeError(f"{obj.name} has {non_manifold} non-manifold edges")
    if shells != 1:
        raise RuntimeError(f"{obj.name} has {shells} connected shells")


def output_directory() -> Path:
    if EXPORT_DIRECTORY:
        directory = Path(EXPORT_DIRECTORY).expanduser().resolve()
    else:
        directory = Path(__file__).resolve().parent
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def export_stl(obj) -> Path:
    path = output_directory() / OUTPUT_STL_NAME
    select_only(obj)
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(filepath=str(path), export_selected_objects=True)
    else:
        bpy.ops.export_mesh.stl(filepath=str(path), use_selection=True)
    print(f"EXPORTED {path}")
    return path


def render_preview(obj) -> None:
    if not RENDER_PREVIEW:
        return
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "paint.sl"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "WORLD"
    scene.display.shading.curvature_ridge_factor = 1.5
    scene.display.shading.curvature_valley_factor = 1.2
    scene.world.color = (0.025, 0.025, 0.025)

    bpy.ops.object.camera_add(location=(-390.0, -40.0, 190.0))
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = max(obj.dimensions.x, obj.dimensions.y) * 1.40
    target = Vector((0.0, 0.0, BODY_HEIGHT * 0.43))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    scene.render.resolution_x = PREVIEW_RESOLUTION_X
    scene.render.resolution_y = PREVIEW_RESOLUTION_Y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    path = Path(PREVIEW_PATH)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED {path}")


def build_original_style_cover():
    validate_config()
    if CLEAR_SCENE:
        clear_scene()
    set_units()
    cover = create_cover()
    assign_material(cover)
    triangulate_mesh(cover)
    validate_object(cover)
    if EXPORT_STL:
        export_stl(cover)
    render_preview(cover)
    return cover


if __name__ == "__main__":
    build_original_style_cover()
