"""Original-style Veo Cam 3 cover reconstruction for Blender.

This rebuilds the *spirit* of ``veo_3_cam_cover.stl`` as a printable two-part
enclosure with:

* the same approximate 215 x 234 x 71 mm envelope,
* a broad rounded-triangular body with a closed bottom,
* a flat removable lid retained by four socket-head screws,
* M3 heat-set-insert posts automatically kept clear of both cameras,
* two camera openings on the same side of the body,
* camera axes angled apart in plan, and
* one projecting eyelid/visor directly above each camera opening.

Run inside Blender::

    BLENDER_SYSTEM_RESOURCES=/tmp/blender-apt/root/usr/lib/blender \
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
EXPORT_SEPARATE_STLS = True
EXPORT_COMBINED_STL = True
BASE_STL_NAME = "veo_3_cam_cover_original_style_base.stl"
LID_STL_NAME = "veo_3_cam_cover_original_style_lid.stl"
ASSEMBLY_STL_NAME = "veo_3_cam_cover_original_style.stl"
NORMALIZE_SEPARATE_STLS = True

RENDER_PREVIEW = False
PREVIEW_PATH = "veo_3_cam_cover_original_style.png"
PREVIEW_RESOLUTION_X = 1100
PREVIEW_RESOLUTION_Y = 850
PREVIEW_EXPLODED = True
PREVIEW_LID_LIFT = 25.0
PREVIEW_SHOW_CAMERA_MOCKUPS = True

# Source STL envelope: 215.167 x 233.661 x 70.653 mm.
BODY_WIDTH = 215.167
BODY_DEPTH = 233.661
BODY_HEIGHT = 70.653
BASE_HEIGHT = 66.0
LID_THICKNESS = BODY_HEIGHT - BASE_HEIGHT
BOTTOM_THICKNESS = 3.2
BODY_WALL_THICKNESS = 3.2
# 0 produces an ellipse.  Higher values pull the camera end (-X) inward and
# leave a broad rounded rear (+X), producing the source's soft triangle shape.
FOOTPRINT_TRIANGULARITY = 0.68
FOOTPRINT_POINTS = 192

# (Z, XY scale) controls the rounded bottom edge and vertical main body.
BODY_SECTIONS = (
    (0.0, 0.96),
    (6.0, 0.99),
    (12.0, 1.00),
    (BASE_HEIGHT, 1.00),
)

# Lid locating lip.  The screw system provides clamping; this lip aligns the
# flat top and prevents lateral movement.
LID_LIP_ENABLED = True
LID_LIP_DEPTH = 3.0
LID_LIP_THICKNESS = 1.8
LID_LIP_CLEARANCE = 0.30

# Both camera openings sit on the -X half of the shell.  The default follows
# the source mesh's dominant opening-surround directions.
CAMERA_CENTERLINE_AZIMUTH_DEG = 180.0
CAMERA_HALF_ANGLE_DEG = 45.0
# Set a two-value tuple to override the symmetric centerline/half-angle logic.
CAMERA_AZIMUTHS_DEG = None

EYE_CENTER_Z = 26.0
EYE_OPENING_WIDTH = 58.0
EYE_OPENING_HEIGHT = 36.0
EYE_OPENING_CORNER_RADIUS = 11.0
EYE_CUTTER_OUTWARD_EXTENSION = 25.0

# Raised surround around each opening.
EYE_BEZEL_WIDTH = 64.0
EYE_BEZEL_HEIGHT = 46.0
EYE_BEZEL_CORNER_RADIUS = 14.5
EYE_FACE_INSET = 1.0
EYE_BEZEL_DEPTH = 9.0

# The eyelid is a tapered wedge whose lower/front edge overhangs the eye.
VISORS_ENABLED = True
VISOR_BACK_WIDTH = 92.0
VISOR_FRONT_WIDTH = 60.0
VISOR_BACK_INSET = 12.0
VISOR_PROJECTION = 0.0
VISOR_BACK_BOTTOM_Z = 48.5
VISOR_BACK_TOP_Z = 59.0
VISOR_FRONT_BOTTOM_Z = 48.0
VISOR_FRONT_TOP_Z = 54.0
VISOR_EDGE_RADIUS = 1.5

# Camera envelopes used both for placement validation and optional previews.
# Width is tangential to the camera axis; depth is along the optical axis.
CAMERA_BODY_WIDTH = 71.8
CAMERA_BODY_DEPTH = 33.6
CAMERA_BODY_HEIGHT = 50.8
CAMERA_FRONT_CLEARANCE = 2.0
CAMERA_FLOOR_CLEARANCE = 2.0
CAMERA_TANGENTIAL_BODY_OFFSET = 18.0
CAMERA_AUTO_INSET_ENABLED = True
CAMERA_AUTO_INSET_MAX = 18.0
CAMERA_AUTO_INSET_STEP = 1.0

# Four lid fasteners.  "auto" searches around the configurable targets while
# respecting the wall and both oriented camera keepout rectangles.  Set
# FASTENER_POST_PLACEMENT="manual" to use MANUAL_FASTENER_POST_POSITIONS_XY.
FASTENERS_ENABLED = True
FASTENER_POST_PLACEMENT = "auto"  # "auto" or "manual"
FASTENER_POST_TARGETS_XY = (
    (55.0, -65.0),
    (55.0, 65.0),
    (-5.0, -95.0),
    (-5.0, 95.0),
)
MANUAL_FASTENER_POST_POSITIONS_XY = FASTENER_POST_TARGETS_XY
FASTENER_AUTO_SEARCH_RADIUS = 35.0
FASTENER_AUTO_GRID_STEP = 2.0
FASTENER_POST_DIAMETER = 10.5
FASTENER_POST_EDGE_CLEARANCE = 2.0
FASTENER_POST_CAMERA_CLEARANCE = 5.0
FASTENER_POST_MIN_CENTER_SPACING = 18.0
FASTENER_POST_TOP_CLEARANCE = 0.20

# M3 heat-set insert defaults.  Inserts vary by vendor: measure yours and
# override these values.  A 4.0 mm pilot is common for inserts around 4.6 mm
# knurled OD; the smaller pilot supplies the plastic interference for heating.
HEAT_INSERT_HOLE_DIAMETER = 4.0
HEAT_INSERT_HOLE_DEPTH = 6.5
HEAT_INSERT_LEADIN_DIAMETER = 4.8
HEAT_INSERT_LEADIN_DEPTH = 1.0

# M3 socket-head cap screw: 3.4 mm shank clearance and a circular counterbore
# for a nominal 5.5 mm diameter x 3.0 mm high head.  The internal drive is hex;
# the outside of a socket-head cap screw remains cylindrical.
LID_SCREW_CLEARANCE_DIAMETER = 3.4
LID_SCREW_HEAD_COUNTERBORE_DIAMETER = 6.2
LID_SCREW_HEAD_COUNTERBORE_DEPTH = 3.3

# Geometry quality.
ROUNDED_CORNER_SEGMENTS = 14
BOOLEAN_SOLVER = "EXACT"
BOOLEAN_OVERLAP = 0.25
BOOLEAN_CLEANUP_DISTANCE = 0.0001

COVER_COLOR = (0.10, 0.38, 0.72, 1.0)
LID_COLOR = (0.12, 0.62, 0.34, 1.0)
CAMERA_COLOR = (0.03, 0.035, 0.045, 1.0)


# ---------------------------------------------------------------------------
# Configuration and scene helpers


def validate_config() -> None:
    positive = {
        "BODY_WIDTH": BODY_WIDTH,
        "BODY_DEPTH": BODY_DEPTH,
        "BODY_HEIGHT": BODY_HEIGHT,
        "BASE_HEIGHT": BASE_HEIGHT,
        "LID_THICKNESS": LID_THICKNESS,
        "BOTTOM_THICKNESS": BOTTOM_THICKNESS,
        "BODY_WALL_THICKNESS": BODY_WALL_THICKNESS,
        "EYE_OPENING_WIDTH": EYE_OPENING_WIDTH,
        "EYE_OPENING_HEIGHT": EYE_OPENING_HEIGHT,
        "EYE_BEZEL_WIDTH": EYE_BEZEL_WIDTH,
        "EYE_BEZEL_HEIGHT": EYE_BEZEL_HEIGHT,
        "VISOR_BACK_WIDTH": VISOR_BACK_WIDTH,
        "VISOR_FRONT_WIDTH": VISOR_FRONT_WIDTH,
        "CAMERA_BODY_WIDTH": CAMERA_BODY_WIDTH,
        "CAMERA_BODY_DEPTH": CAMERA_BODY_DEPTH,
        "CAMERA_BODY_HEIGHT": CAMERA_BODY_HEIGHT,
        "FASTENER_POST_DIAMETER": FASTENER_POST_DIAMETER,
        "HEAT_INSERT_HOLE_DIAMETER": HEAT_INSERT_HOLE_DIAMETER,
        "HEAT_INSERT_HOLE_DEPTH": HEAT_INSERT_HOLE_DEPTH,
        "LID_SCREW_CLEARANCE_DIAMETER": LID_SCREW_CLEARANCE_DIAMETER,
        "LID_SCREW_HEAD_COUNTERBORE_DIAMETER": (
            LID_SCREW_HEAD_COUNTERBORE_DIAMETER
        ),
        "LID_SCREW_HEAD_COUNTERBORE_DEPTH": LID_SCREW_HEAD_COUNTERBORE_DEPTH,
    }
    for name, value in positive.items():
        if value <= 0.0:
            raise ValueError(f"{name} must be positive")
    if not 0.0 <= FOOTPRINT_TRIANGULARITY < 0.85:
        raise ValueError("FOOTPRINT_TRIANGULARITY must be between 0 and 0.85")
    if FOOTPRINT_POINTS < 32 or FOOTPRINT_POINTS % 4:
        raise ValueError("FOOTPRINT_POINTS must be a multiple of four and at least 32")
    if tuple(z for z, _ in BODY_SECTIONS) != tuple(
        sorted(z for z, _ in BODY_SECTIONS)
    ):
        raise ValueError("BODY_SECTIONS must be ordered by increasing Z")
    if BODY_SECTIONS[0][0] != 0.0 or BODY_SECTIONS[-1][0] != BASE_HEIGHT:
        raise ValueError("BODY_SECTIONS must span Z=0 through BASE_HEIGHT")
    if abs(BASE_HEIGHT + LID_THICKNESS - BODY_HEIGHT) > 1e-6:
        raise ValueError("BASE_HEIGHT + LID_THICKNESS must equal BODY_HEIGHT")
    if not 0.0 < BOTTOM_THICKNESS < BASE_HEIGHT:
        raise ValueError("BOTTOM_THICKNESS must fit below the base opening")
    if FASTENER_POST_PLACEMENT not in {"auto", "manual"}:
        raise ValueError('FASTENER_POST_PLACEMENT must be "auto" or "manual"')
    if HEAT_INSERT_HOLE_DIAMETER >= FASTENER_POST_DIAMETER:
        raise ValueError("Heat-insert hole must fit inside the fastener post")
    if LID_SCREW_HEAD_COUNTERBORE_DIAMETER <= LID_SCREW_CLEARANCE_DIAMETER:
        raise ValueError("Socket-head counterbore must exceed shank clearance")
    if LID_SCREW_HEAD_COUNTERBORE_DEPTH >= LID_THICKNESS:
        raise ValueError("Counterbore depth must leave material in the lid")
    if len(FASTENER_POST_TARGETS_XY) != 4:
        raise ValueError("Exactly four fastener post targets are required")
    if len(MANUAL_FASTENER_POST_POSITIONS_XY) != 4:
        raise ValueError("Exactly four manual fastener positions are required")
    if (
        CAMERA_FLOOR_CLEARANCE + BOTTOM_THICKNESS + CAMERA_BODY_HEIGHT
        >= BASE_HEIGHT
    ):
        raise ValueError("Camera envelope is too tall for the closed base")
    if EYE_OPENING_WIDTH >= EYE_BEZEL_WIDTH or EYE_OPENING_HEIGHT >= EYE_BEZEL_HEIGHT:
        raise ValueError("Eye openings must fit inside the bezels")
    if EYE_CENTER_Z - EYE_BEZEL_HEIGHT / 2.0 < 0.0:
        raise ValueError("Eye bezel extends below the cover")
    if VISORS_ENABLED and VISOR_BACK_BOTTOM_Z > VISOR_BACK_TOP_Z:
        raise ValueError("Visor back Z values are reversed")
    if VISORS_ENABLED and VISOR_FRONT_BOTTOM_Z > VISOR_FRONT_TOP_Z:
        raise ValueError("Visor front Z values are reversed")


def camera_azimuths():
    if CAMERA_AZIMUTHS_DEG is not None:
        if len(CAMERA_AZIMUTHS_DEG) != 2:
            raise ValueError("CAMERA_AZIMUTHS_DEG override must contain two angles")
        return tuple(float(angle) for angle in CAMERA_AZIMUTHS_DEG)
    return (
        CAMERA_CENTERLINE_AZIMUTH_DEG - CAMERA_HALF_ANGLE_DEG,
        CAMERA_CENTERLINE_AZIMUTH_DEG + CAMERA_HALF_ANGLE_DEG,
    )


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
    # An egg/limaçon-like loop gives a rounded triangular plan without a sharp
    # apex.  Normalize Y afterward so BODY_DEPTH remains an exact dimension.
    raw_points = []
    for index in range(FOOTPRINT_POINTS):
        angle = 2.0 * math.pi * index / FOOTPRINT_POINTS
        cosine = math.cos(angle)
        sine = math.sin(angle)
        raw_points.append(
            (width / 2.0 * cosine, depth / 2.0 * sine * (1.0 + FOOTPRINT_TRIANGULARITY * cosine))
        )
    maximum_y = max(abs(y) for _, y in raw_points)
    y_scale = (depth / 2.0) / maximum_y
    return [(x, y * y_scale) for x, y in raw_points]


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


def ring_prism(name: str, outer_loop, inner_loop, z0: float, z1: float):
    if len(outer_loop) != len(inner_loop):
        raise ValueError("Ring loops must have equal vertex counts")
    count = len(outer_loop)
    vertices = []
    vertices.extend((x, y, z0) for x, y in outer_loop)
    vertices.extend((x, y, z1) for x, y in outer_loop)
    vertices.extend((x, y, z0) for x, y in inner_loop)
    vertices.extend((x, y, z1) for x, y in inner_loop)
    outer0, outer1, inner0, inner1 = 0, count, count * 2, count * 3
    faces = []
    for index in range(count):
        next_index = (index + 1) % count
        faces.append(
            [outer0 + index, outer0 + next_index, outer1 + next_index, outer1 + index]
        )
        faces.append(
            [inner0 + next_index, inner0 + index, inner1 + index, inner1 + next_index]
        )
        faces.append(
            [outer0 + index, inner0 + index, inner0 + next_index, outer0 + next_index]
        )
        faces.append(
            [outer1 + next_index, inner1 + next_index, inner1 + index, outer1 + index]
        )
    return create_mesh_object(name, vertices, faces)


def add_cylinder_z(
    name: str, radius: float, z0: float, z1: float, x: float = 0.0, y: float = 0.0
):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=72,
        radius=radius,
        depth=z1 - z0,
        location=(x, y, (z0 + z1) / 2.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    return obj


def add_beveled_box(name: str, dimensions, location, rotation_z=0.0, bevel=2.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.rotation_euler.z = rotation_z
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    modifier = obj.modifiers.new(name + "_Bevel", "BEVEL")
    modifier.width = min(bevel, min(dimensions) / 2.1)
    modifier.segments = 3
    modifier.affect = "EDGES"
    select_only(obj)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    recalc_normals(obj)
    return obj


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
    loop = superellipse_loop(BODY_WIDTH, BODY_DEPTH)
    angle = math.radians(angle_deg)
    direction = (math.cos(angle), math.sin(angle))

    def cross(a, b):
        return a[0] * b[1] - a[1] * b[0]

    hits = []
    for index, point in enumerate(loop):
        next_point = loop[(index + 1) % len(loop)]
        edge = (next_point[0] - point[0], next_point[1] - point[1])
        denominator = cross(direction, edge)
        if abs(denominator) < 1e-10:
            continue
        radial = cross(point, edge) / denominator
        fraction = cross(point, direction) / denominator
        if radial >= 0.0 and -1e-8 <= fraction <= 1.0 + 1e-8:
            hits.append(radial)
    if not hits:
        raise RuntimeError(f"No footprint intersection at {angle_deg} degrees")
    return min(hits)


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
# Camera keepouts and automatic fastener-post placement


def point_in_polygon(point, loop) -> bool:
    x, y = point
    inside = False
    for index, (x0, y0) in enumerate(loop):
        x1, y1 = loop[(index + 1) % len(loop)]
        if (y0 > y) != (y1 > y):
            crossing_x = (x1 - x0) * (y - y0) / (y1 - y0) + x0
            if x < crossing_x:
                inside = not inside
    return inside


def point_segment_distance(point, start, end) -> float:
    px, py = point
    x0, y0 = start
    x1, y1 = end
    dx, dy = x1 - x0, y1 - y0
    length_squared = dx * dx + dy * dy
    if length_squared <= 1e-12:
        return math.hypot(px - x0, py - y0)
    fraction = ((px - x0) * dx + (py - y0) * dy) / length_squared
    fraction = min(max(fraction, 0.0), 1.0)
    return math.hypot(px - (x0 + fraction * dx), py - (y0 + fraction * dy))


def polygon_boundary_distance(point, loop) -> float:
    return min(
        point_segment_distance(point, loop[index], loop[(index + 1) % len(loop)])
        for index in range(len(loop))
    )


def camera_xy_corners(camera, clearance=0.0):
    half_depth = CAMERA_BODY_DEPTH / 2.0 + clearance
    half_width = CAMERA_BODY_WIDTH / 2.0 + clearance
    return [
        tuple(
            axis_point(
                camera["angle"],
                camera["radial"] + radial_sign * half_depth,
                camera["tangent"] + tangent_sign * half_width,
                0.0,
            )[:2]
        )
        for radial_sign in (-1.0, 1.0)
        for tangent_sign in (-1.0, 1.0)
    ]


def rectangles_overlap(camera_a, camera_b) -> bool:
    corners_a = camera_xy_corners(camera_a)
    corners_b = camera_xy_corners(camera_b)
    axes = []
    for camera in (camera_a, camera_b):
        angle = math.radians(camera["angle"])
        axes.extend(((math.cos(angle), math.sin(angle)), (-math.sin(angle), math.cos(angle))))
    for axis in axes:
        projection_a = [x * axis[0] + y * axis[1] for x, y in corners_a]
        projection_b = [x * axis[0] + y * axis[1] for x, y in corners_b]
        if max(projection_a) <= min(projection_b) or max(projection_b) <= min(projection_a):
            return False
    return True


def resolve_camera_layout():
    inner_loop = superellipse_loop(
        BODY_WIDTH - 2.0 * BODY_WALL_THICKNESS,
        BODY_DEPTH - 2.0 * BODY_WALL_THICKNESS,
    )
    cameras = []
    for index, angle in enumerate(camera_azimuths(), start=1):
        surface = radial_surface_distance(angle)
        radial = (
            surface
            - BODY_WALL_THICKNESS
            - CAMERA_FRONT_CLEARANCE
            - CAMERA_BODY_DEPTH / 2.0
        )
        outward_sign = 1.0 if math.sin(math.radians(angle)) >= 0.0 else -1.0
        tangent = -outward_sign * CAMERA_TANGENTIAL_BODY_OFFSET
        camera = {"index": index, "angle": angle, "radial": radial, "tangent": tangent}
        inset = 0.0
        while not all(point_in_polygon(corner, inner_loop) for corner in camera_xy_corners(camera)):
            if not CAMERA_AUTO_INSET_ENABLED or inset >= CAMERA_AUTO_INSET_MAX:
                raise ValueError(
                    f"Camera {index} does not fit the inner footprint; increase body size "
                    "or CAMERA_AUTO_INSET_MAX"
                )
            inset += CAMERA_AUTO_INSET_STEP
            camera["radial"] -= CAMERA_AUTO_INSET_STEP
        camera["auto_inset"] = inset
        center = axis_point(angle, camera["radial"], tangent, 0.0)
        camera["center_xy"] = (center.x, center.y)
        cameras.append(camera)

    if rectangles_overlap(cameras[0], cameras[1]):
        raise ValueError(
            "The two configured camera body envelopes overlap. Increase camera angle, "
            "increase CAMERA_TANGENTIAL_BODY_OFFSET, or reduce the envelope dimensions."
        )
    for camera in cameras:
        print(
            f"CAMERA_LAYOUT {camera['index']}: center_xy="
            f"({camera['center_xy'][0]:.2f}, {camera['center_xy'][1]:.2f}) "
            f"angle={camera['angle']:.2f} auto_inset={camera['auto_inset']:.2f}"
        )
    return cameras


def post_is_valid(position, cameras, inner_loop, accepted_positions=()) -> bool:
    post_radius = FASTENER_POST_DIAMETER / 2.0
    required_edge_distance = post_radius + FASTENER_POST_EDGE_CLEARANCE
    if not point_in_polygon(position, inner_loop):
        return False
    if polygon_boundary_distance(position, inner_loop) < required_edge_distance:
        return False
    for accepted in accepted_positions:
        if math.dist(position, accepted) < FASTENER_POST_MIN_CENTER_SPACING:
            return False
    for camera in cameras:
        angle = math.radians(camera["angle"])
        normal = (math.cos(angle), math.sin(angle))
        tangent_axis = (-math.sin(angle), math.cos(angle))
        radial = position[0] * normal[0] + position[1] * normal[1]
        tangent = position[0] * tangent_axis[0] + position[1] * tangent_axis[1]
        radial_limit = (
            CAMERA_BODY_DEPTH / 2.0
            + FASTENER_POST_CAMERA_CLEARANCE
            + post_radius
        )
        tangent_limit = (
            CAMERA_BODY_WIDTH / 2.0
            + FASTENER_POST_CAMERA_CLEARANCE
            + post_radius
        )
        if (
            abs(radial - camera["radial"]) < radial_limit
            and abs(tangent - camera["tangent"]) < tangent_limit
        ):
            return False
    return True


def resolve_fastener_post_positions(cameras):
    inner_loop = superellipse_loop(
        BODY_WIDTH - 2.0 * BODY_WALL_THICKNESS,
        BODY_DEPTH - 2.0 * BODY_WALL_THICKNESS,
    )
    if FASTENER_POST_PLACEMENT == "manual":
        positions = [tuple(position) for position in MANUAL_FASTENER_POST_POSITIONS_XY]
        accepted = []
        for index, position in enumerate(positions, start=1):
            if not post_is_valid(position, cameras, inner_loop, accepted):
                raise ValueError(
                    f"Manual fastener post {index} at {position} violates a camera, "
                    "wall, or post-spacing keepout"
                )
            accepted.append(position)
    else:
        accepted = []
        steps = int(math.ceil(FASTENER_AUTO_SEARCH_RADIUS / FASTENER_AUTO_GRID_STEP))
        for index, target in enumerate(FASTENER_POST_TARGETS_XY, start=1):
            candidates = []
            for ix in range(-steps, steps + 1):
                for iy in range(-steps, steps + 1):
                    dx = ix * FASTENER_AUTO_GRID_STEP
                    dy = iy * FASTENER_AUTO_GRID_STEP
                    if math.hypot(dx, dy) > FASTENER_AUTO_SEARCH_RADIUS:
                        continue
                    position = (target[0] + dx, target[1] + dy)
                    if post_is_valid(position, cameras, inner_loop, accepted):
                        candidates.append((dx * dx + dy * dy, position))
            if not candidates:
                raise ValueError(
                    f"No valid location found near fastener target {index} {target}; "
                    "move the target or increase FASTENER_AUTO_SEARCH_RADIUS"
                )
            candidates.sort(key=lambda item: (item[0], item[1][0], item[1][1]))
            accepted.append(candidates[0][1])
    result = tuple(accepted)
    print("FASTENER_POST_POSITIONS_XY", result)
    return result


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


def add_camera_openings_and_visors(base):
    # Add the raised camera surrounds first, then place each eyelid directly
    # over its corresponding opening.
    for index, angle in enumerate(camera_azimuths(), start=1):
        surface = radial_surface_distance(angle)
        bezel = rounded_rectangle_prism_axis(
            f"Eye_{index}_Raised_Surround",
            angle,
            surface - EYE_FACE_INSET - EYE_BEZEL_DEPTH,
            surface - EYE_FACE_INSET,
            EYE_BEZEL_WIDTH,
            EYE_BEZEL_HEIGHT,
            EYE_BEZEL_CORNER_RADIUS,
            EYE_CENTER_Z,
        )
        boolean_union(base, bezel, f"Eye_{index}_Surround_Union")
        if VISORS_ENABLED:
            boolean_union(
                base,
                visor_wedge(f"Eye_{index}_Eyelid_Visor", angle, surface),
                f"Eye_{index}_Visor_Union",
            )

    # Keep the two cutters in separate Boolean stages because close camera
    # angles can make their tool volumes overlap inside the body.
    for index, angle in enumerate(camera_azimuths(), start=1):
        surface = radial_surface_distance(angle)
        boolean_difference(
            base,
            [
                rounded_rectangle_prism_axis(
                    f"Eye_{index}_Opening",
                    angle,
                    surface
                    - BODY_WALL_THICKNESS
                    - EYE_BEZEL_DEPTH
                    - EYE_FACE_INSET,
                    surface + EYE_CUTTER_OUTWARD_EXTENSION,
                    EYE_OPENING_WIDTH,
                    EYE_OPENING_HEIGHT,
                    EYE_OPENING_CORNER_RADIUS,
                    EYE_CENTER_Z,
                )
            ],
            f"Camera_Opening_{index}",
        )
    return base


def add_fastener_posts(base, positions):
    if not FASTENERS_ENABLED:
        return base
    post_top = BASE_HEIGHT - FASTENER_POST_TOP_CLEARANCE
    for index, (x, y) in enumerate(positions, start=1):
        post = add_cylinder_z(
            f"Base_Heat_Insert_Post_{index}",
            FASTENER_POST_DIAMETER / 2.0,
            BOTTOM_THICKNESS - BOOLEAN_OVERLAP,
            post_top,
            x,
            y,
        )
        boolean_union(base, post, f"Base_Heat_Insert_Post_{index}_Union")

    insert_cutters = [
        add_cylinder_z(
            f"Heat_Insert_Hole_{index}",
            HEAT_INSERT_HOLE_DIAMETER / 2.0,
            post_top - HEAT_INSERT_HOLE_DEPTH,
            post_top + BOOLEAN_OVERLAP,
            x,
            y,
        )
        for index, (x, y) in enumerate(positions, start=1)
    ]
    boolean_difference(base, insert_cutters, "Heat_Insert_Holes")

    if HEAT_INSERT_LEADIN_DEPTH > 0.0:
        leadin_cutters = [
            add_cylinder_z(
                f"Heat_Insert_Leadin_{index}",
                HEAT_INSERT_LEADIN_DIAMETER / 2.0,
                post_top - HEAT_INSERT_LEADIN_DEPTH,
                post_top + 2.0 * BOOLEAN_OVERLAP,
                x,
                y,
            )
            for index, (x, y) in enumerate(positions, start=1)
        ]
        boolean_difference(base, leadin_cutters, "Heat_Insert_Leadins")
    return base


def create_base(positions):
    outer_sections = tuple(
        (z, superellipse_loop(BODY_WIDTH * scale, BODY_DEPTH * scale))
        for z, scale in BODY_SECTIONS
    )
    base = loft_solid("Veo_3_Closed_Bottom_Base", outer_sections)

    cavity_z_values = [BOTTOM_THICKNESS]
    cavity_z_values.extend(
        z for z, _ in BODY_SECTIONS[1:-1] if BOTTOM_THICKNESS < z < BASE_HEIGHT
    )
    cavity_z_values.append(BASE_HEIGHT + BOOLEAN_OVERLAP)
    cavity_sections = []
    for z in cavity_z_values:
        scale = body_scale_at_z(min(max(z, 0.0), BASE_HEIGHT))
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
        base,
        [loft_solid("Closed_Base_Inner_Cavity", cavity_sections)],
        "Closed_Base_Inner_Cavity",
    )
    add_camera_openings_and_visors(base)
    add_fastener_posts(base, positions)
    base.name = "Veo_3_Cam_Cover_Closed_Base"
    return base


def create_lid(positions):
    outer_loop = superellipse_loop(BODY_WIDTH, BODY_DEPTH)
    lid = loft_solid(
        "Veo_3_Flat_Removable_Lid",
        ((BASE_HEIGHT, outer_loop), (BODY_HEIGHT, outer_loop)),
    )

    if LID_LIP_ENABLED:
        lip_outer_width = (
            BODY_WIDTH - 2.0 * BODY_WALL_THICKNESS - 2.0 * LID_LIP_CLEARANCE
        )
        lip_outer_depth = (
            BODY_DEPTH - 2.0 * BODY_WALL_THICKNESS - 2.0 * LID_LIP_CLEARANCE
        )
        lip = ring_prism(
            "Lid_Alignment_Lip",
            superellipse_loop(lip_outer_width, lip_outer_depth),
            superellipse_loop(
                lip_outer_width - 2.0 * LID_LIP_THICKNESS,
                lip_outer_depth - 2.0 * LID_LIP_THICKNESS,
            ),
            BASE_HEIGHT - LID_LIP_DEPTH,
            BASE_HEIGHT + BOOLEAN_OVERLAP,
        )
        boolean_union(lid, lip, "Lid_Alignment_Lip_Union")

    if FASTENERS_ENABLED:
        clearance_cutters = [
            add_cylinder_z(
                f"Lid_Screw_Clearance_{index}",
                LID_SCREW_CLEARANCE_DIAMETER / 2.0,
                BASE_HEIGHT - LID_LIP_DEPTH - BOOLEAN_OVERLAP,
                BODY_HEIGHT + BOOLEAN_OVERLAP,
                x,
                y,
            )
            for index, (x, y) in enumerate(positions, start=1)
        ]
        boolean_difference(lid, clearance_cutters, "Lid_Screw_Clearance_Holes")

        counterbore_cutters = [
            add_cylinder_z(
                f"Lid_Socket_Head_Counterbore_{index}",
                LID_SCREW_HEAD_COUNTERBORE_DIAMETER / 2.0,
                BODY_HEIGHT - LID_SCREW_HEAD_COUNTERBORE_DEPTH,
                BODY_HEIGHT + 2.0 * BOOLEAN_OVERLAP,
                x,
                y,
            )
            for index, (x, y) in enumerate(positions, start=1)
        ]
        boolean_difference(lid, counterbore_cutters, "Lid_Socket_Head_Counterbores")
    lid.name = "Veo_3_Cam_Cover_Flat_Lid"
    return lid


# ---------------------------------------------------------------------------
# Validation, export, and preview


def assign_material(obj, name: str, color) -> None:
    material = bpy.data.materials.get(name)
    if material is None:
        material = bpy.data.materials.new(name)
    material.diffuse_color = color
    obj.data.materials.clear()
    obj.data.materials.append(material)


def create_camera_mockups(cameras):
    if not PREVIEW_SHOW_CAMERA_MOCKUPS:
        return []
    mockups = []
    center_z = BOTTOM_THICKNESS + CAMERA_FLOOR_CLEARANCE + CAMERA_BODY_HEIGHT / 2.0
    for camera in cameras:
        center = axis_point(
            camera["angle"], camera["radial"], camera["tangent"], center_z
        )
        mockup = add_beveled_box(
            f"Camera_{camera['index']}_Keepout_Mockup",
            (CAMERA_BODY_DEPTH, CAMERA_BODY_WIDTH, CAMERA_BODY_HEIGHT),
            tuple(center),
            rotation_z=math.radians(camera["angle"]),
            bevel=3.0,
        )
        assign_material(mockup, "Camera_Keepout_Material", CAMERA_COLOR)
        mockups.append(mockup)
    return mockups


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
        # Use the invocation directory so symlinked generators still place
        # outputs beside the source/reference STL the user is working from.
        directory = Path.cwd().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def export_stl(path: Path, objects) -> Path:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(filepath=str(path), export_selected_objects=True)
    else:
        bpy.ops.export_mesh.stl(filepath=str(path), use_selection=True)
    print(f"EXPORTED {path}")
    return path


def export_single_stl(path: Path, obj) -> Path:
    if not NORMALIZE_SEPARATE_STLS:
        return export_stl(path, [obj])
    original_location = obj.location.copy()
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    center_x = (min(point.x for point in corners) + max(point.x for point in corners)) / 2.0
    center_y = (min(point.y for point in corners) + max(point.y for point in corners)) / 2.0
    minimum_z = min(point.z for point in corners)
    obj.location += Vector((-center_x, -center_y, -minimum_z))
    result = export_stl(path, [obj])
    obj.location = original_location
    return result


def render_preview(base, lid, camera_mockups) -> None:
    if not RENDER_PREVIEW:
        return
    if PREVIEW_EXPLODED:
        lid.location.z += PREVIEW_LID_LIFT
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

    bpy.ops.object.camera_add(location=(-350.0, -330.0, 300.0))
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = max(BODY_WIDTH, BODY_DEPTH) * 1.60
    target = Vector((0.0, 0.0, BASE_HEIGHT * 0.72))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    scene.render.resolution_x = PREVIEW_RESOLUTION_X
    scene.render.resolution_y = PREVIEW_RESOLUTION_Y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    path = Path(PREVIEW_PATH)
    if not path.is_absolute():
        path = Path.cwd().resolve() / path
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED {path}")


def build_original_style_cover():
    validate_config()
    if CLEAR_SCENE:
        clear_scene()
    set_units()
    cameras = resolve_camera_layout()
    positions = resolve_fastener_post_positions(cameras)
    base = create_base(positions)
    lid = create_lid(positions)
    assign_material(base, "Veo_Base_Material", COVER_COLOR)
    assign_material(lid, "Veo_Lid_Material", LID_COLOR)
    triangulate_mesh(base)
    triangulate_mesh(lid)
    validate_object(base)
    validate_object(lid)
    if EXPORT_STL:
        directory = output_directory()
        if EXPORT_SEPARATE_STLS:
            export_single_stl(directory / BASE_STL_NAME, base)
            export_single_stl(directory / LID_STL_NAME, lid)
        if EXPORT_COMBINED_STL:
            export_stl(directory / ASSEMBLY_STL_NAME, [base, lid])
    camera_mockups = create_camera_mockups(cameras)
    render_preview(base, lid, camera_mockups)
    return base, lid


if __name__ == "__main__":
    build_original_style_cover()
