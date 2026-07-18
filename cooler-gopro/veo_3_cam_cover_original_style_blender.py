"""Original-style Veo Cam 3 cover reconstruction for Blender.

This rebuilds the *spirit* of ``veo_3_cam_cover.stl`` as a printable two-part
enclosure with:

* the same approximate 215 x 234 x 71 mm baseline envelope, expanded at the
  camera-side nose only when the configured camera angle requires it,
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
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


def import_mission1_module():
    """Find the companion module when run externally or from a Blender text."""
    script_path = Path(__file__).expanduser().resolve()
    script_directory = script_path.parent
    candidates = [Path.cwd().resolve(), script_directory]
    # Blender text blocks commonly report a virtual path like
    # ``project.blend/script.py``.  Its parent is the .blend file, while the
    # companion module actually sits beside that file.
    if script_directory.suffix.lower() == ".blend":
        candidates.append(script_directory.parent)
    if bpy.data.filepath:
        candidates.append(Path(bpy.data.filepath).expanduser().resolve().parent)

    searched = []
    for directory in candidates:
        module_path = directory / "gopro_mission1_dummy_blender.py"
        if module_path in searched:
            continue
        searched.append(module_path)
        if module_path.is_file():
            directory_text = str(directory)
            if directory_text not in sys.path:
                sys.path.insert(0, directory_text)
            import gopro_mission1_dummy_blender

            return gopro_mission1_dummy_blender
    raise ModuleNotFoundError(
        "Could not locate gopro_mission1_dummy_blender.py. Searched: "
        + ", ".join(str(path) for path in searched)
    )


mission1 = import_mission1_module()


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

# Visibility in Blender after the generator finishes.  These are applied only
# after export and preview rendering, so hidden parts are still generated and
# included in the requested output files.
SHOW_MAIN_BODY_AFTER_BUILD = True
SHOW_TOP_AFTER_BUILD = False

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

# Both camera openings sit on the -X half of the shell.  The half-angle is a
# primary shape input: reducing it keeps the cameras closer together and the
# camera-driven footprint automatically broadens/blunts the -X nose as needed.
CAMERA_CENTERLINE_AZIMUTH_DEG = 180.0
CAMERA_HALF_ANGLE_DEG = 30.0
# Set a two-value tuple to override the symmetric centerline/half-angle logic.
CAMERA_AZIMUTHS_DEG = None

# The supplied dummy extends 23.5 mm below its lens center when mounted
# upside-down.  This eye height leaves the configured 2 mm floor clearance.
EYE_CENTER_Z = 28.7
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
VISORS_ENABLED = False
VISOR_BACK_WIDTH = 92.0
VISOR_FRONT_WIDTH = 60.0
VISOR_BACK_INSET = 12.0
# A small positive overlap keeps the beveled visor Boolean robust where its
# front edge meets the camera-driven face plane.
VISOR_PROJECTION = 0.25
VISOR_BACK_BOTTOM_Z = 48.5
VISOR_BACK_TOP_Z = 59.0
VISOR_FRONT_BOTTOM_Z = 48.0
VISOR_FRONT_TOP_Z = 54.0
VISOR_EDGE_RADIUS = 1.5

# MISSION 1 measurements come from the supplied GoproDummy_noscreens.stl and
# its procedural recreation in gopro_mission1_dummy_blender.py.  The full
# 81 x 44.4 x 54 mm envelope includes its 16.6 mm lens projection, top button,
# and side button.  Width is tangential to the optical axis; depth is radial.
CAMERA_BODY_ONLY_WIDTH = mission1.BODY_WIDTH
CAMERA_BODY_ONLY_DEPTH = mission1.BODY_DEPTH
CAMERA_BODY_ONLY_HEIGHT = mission1.BODY_HEIGHT
CAMERA_BODY_WIDTH = mission1.REFERENCE_ENVELOPE_WIDTH
CAMERA_BODY_DEPTH = mission1.REFERENCE_ENVELOPE_DEPTH
CAMERA_BODY_HEIGHT = mission1.REFERENCE_ENVELOPE_HEIGHT
CAMERA_FRONT_CLEARANCE = 0.25
CAMERA_FLOOR_CLEARANCE = 2.0
# Eye/lens offsets relative to the complete reference-envelope center after
# the dummy's configured 180-degree roll.  These align the actual lens face,
# rather than the rectangular envelope center, with each eye opening.
CAMERA_LENS_OFFSET_Z = -mission1.CANONICAL_ENVELOPE_CENTER_VERTICAL
CAMERA_ENVELOPE_TANGENTIAL_OFFSET = (
    mission1.CANONICAL_ENVELOPE_CENTER_TANGENTIAL
)
CAMERA_BODY_MUTUAL_CLEARANCE = 1.0
CAMERA_DRIVEN_NOSE_ENABLED = True
CAMERA_NOSE_SHELL_CLEARANCE = 1.5
CAMERA_NOSE_CONTACT_TOLERANCE = 0.01
CAMERA_NOSE_MAX_EXPANSION = 80.0

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
FASTENER_AUTO_SEARCH_RADIUS = 90.0
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
        "CAMERA_BODY_ONLY_WIDTH": CAMERA_BODY_ONLY_WIDTH,
        "CAMERA_BODY_ONLY_DEPTH": CAMERA_BODY_ONLY_DEPTH,
        "CAMERA_BODY_ONLY_HEIGHT": CAMERA_BODY_ONLY_HEIGHT,
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
    camera_bottom = camera_body_center_z() - CAMERA_BODY_HEIGHT / 2.0
    camera_top = camera_body_center_z() + CAMERA_BODY_HEIGHT / 2.0
    if camera_bottom < BOTTOM_THICKNESS + CAMERA_FLOOR_CLEARANCE - 1e-6:
        raise ValueError("Camera envelope intersects the closed bottom")
    if camera_top >= BASE_HEIGHT:
        raise ValueError("Camera envelope is too tall for the closed base")
    if (
        CAMERA_FRONT_CLEARANCE < 0.0
        or CAMERA_FLOOR_CLEARANCE < 0.0
        or CAMERA_BODY_MUTUAL_CLEARANCE < 0.0
    ):
        raise ValueError("Camera clearances cannot be negative")
    if CAMERA_NOSE_SHELL_CLEARANCE < 0.0:
        raise ValueError("CAMERA_NOSE_SHELL_CLEARANCE cannot be negative")
    if CAMERA_NOSE_CONTACT_TOLERANCE <= 0.0:
        raise ValueError("CAMERA_NOSE_CONTACT_TOLERANCE must be positive")
    if CAMERA_NOSE_MAX_EXPANSION < 0.0:
        raise ValueError("CAMERA_NOSE_MAX_EXPANSION cannot be negative")
    if (
        CAMERA_BODY_WIDTH < CAMERA_BODY_ONLY_WIDTH
        or CAMERA_BODY_DEPTH < CAMERA_BODY_ONLY_DEPTH
        or CAMERA_BODY_HEIGHT < CAMERA_BODY_ONLY_HEIGHT
    ):
        raise ValueError("Camera fit envelope cannot be smaller than its bare body")
    if CAMERA_AZIMUTHS_DEG is None and not 0.0 < CAMERA_HALF_ANGLE_DEG < 90.0:
        raise ValueError("CAMERA_HALF_ANGLE_DEG must be between 0 and 90 degrees")
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


def camera_body_center_z() -> float:
    return EYE_CENTER_Z - CAMERA_LENS_OFFSET_Z


def minimum_body_scale_between(z0: float, z1: float) -> float:
    if z0 > z1:
        z0, z1 = z1, z0
    samples = [z0, z1]
    samples.extend(z for z, _ in BODY_SECTIONS if z0 <= z <= z1)
    return min(body_scale_at_z(z) for z in samples)


def camera_minimum_body_scale() -> float:
    z0 = camera_body_center_z() - CAMERA_BODY_HEIGHT / 2.0
    z1 = camera_body_center_z() + CAMERA_BODY_HEIGHT / 2.0
    return minimum_body_scale_between(z0, z1)


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


def scale_loop(loop, scale_x: float, scale_y: float = None):
    scale_y = scale_x if scale_y is None else scale_y
    return [(x * scale_x, y * scale_y) for x, y in loop]


def inset_footprint_loop(loop, inset: float):
    if inset < 0.0:
        raise ValueError("Footprint inset cannot be negative")
    if inset == 0.0:
        return list(loop)

    def clip_halfplane(polygon, normal, maximum_projection):
        result = []
        previous = polygon[-1]
        previous_projection = previous[0] * normal[0] + previous[1] * normal[1]
        previous_inside = previous_projection <= maximum_projection + 1e-9
        for current in polygon:
            current_projection = current[0] * normal[0] + current[1] * normal[1]
            current_inside = current_projection <= maximum_projection + 1e-9
            if current_inside != previous_inside:
                denominator = current_projection - previous_projection
                fraction = (maximum_projection - previous_projection) / denominator
                result.append(
                    (
                        previous[0] + (current[0] - previous[0]) * fraction,
                        previous[1] + (current[1] - previous[1]) * fraction,
                    )
                )
            if current_inside:
                result.append(current)
            previous = current
            previous_projection = current_projection
            previous_inside = current_inside
        return result

    # Intersect all edge half-planes shifted inward by a constant distance.
    # Unlike a per-corner miter, this automatically drops an acute corner when
    # its two shifted edges would cross beyond the rest of the polygon.
    extent = max(max(abs(x), abs(y)) for x, y in loop) + inset + 1.0
    result = [(-extent, -extent), (extent, -extent), (extent, extent), (-extent, extent)]
    for index, point in enumerate(loop):
        following = loop[(index + 1) % len(loop)]
        edge = (following[0] - point[0], following[1] - point[1])
        length = math.hypot(*edge)
        if length <= 1e-10:
            raise ValueError("Footprint contains duplicate adjacent points")
        inward = (-edge[1] / length, edge[0] / length)
        shifted_projection = point[0] * inward[0] + point[1] * inward[1] + inset
        result = clip_halfplane(
            result,
            (-inward[0], -inward[1]),
            -shifted_projection,
        )
        if len(result) < 3:
            raise ValueError("Footprint inset collapses the configured body")
    result = convex_hull_2d(result)
    return vertex_preserving_resample(result, len(loop))


def convex_hull_2d(points):
    unique = sorted(set((round(x, 9), round(y, 9)) for x, y in points))
    if len(unique) < 3:
        raise ValueError("Convex hull needs at least three unique points")

    def cross(origin, a, b):
        return (a[0] - origin[0]) * (b[1] - origin[1]) - (
            a[1] - origin[1]
        ) * (b[0] - origin[0])

    lower = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0.0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0.0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def clip_convex_polygon_halfplane(loop, normal, maximum_projection: float):
    """Clip a convex CCW loop to dot(point, normal) <= maximum_projection."""
    result = []
    previous = loop[-1]
    previous_projection = previous[0] * normal[0] + previous[1] * normal[1]
    previous_inside = previous_projection <= maximum_projection + 1e-9
    for current in loop:
        current_projection = current[0] * normal[0] + current[1] * normal[1]
        current_inside = current_projection <= maximum_projection + 1e-9
        if current_inside != previous_inside:
            denominator = current_projection - previous_projection
            if abs(denominator) <= 1e-12:
                raise ValueError("Footprint half-plane clip encountered a parallel edge")
            fraction = (maximum_projection - previous_projection) / denominator
            result.append(
                (
                    previous[0] + (current[0] - previous[0]) * fraction,
                    previous[1] + (current[1] - previous[1]) * fraction,
                )
            )
        if current_inside:
            result.append(current)
        previous = current
        previous_projection = current_projection
        previous_inside = current_inside
    if len(result) < 3:
        raise ValueError("Camera face constraints removed the entire body footprint")
    return result


def resample_closed_loop(loop, count: int):
    segment_lengths = []
    perimeter = 0.0
    for index, point in enumerate(loop):
        next_point = loop[(index + 1) % len(loop)]
        length = math.dist(point, next_point)
        segment_lengths.append(length)
        perimeter += length
    result = []
    segment_index = 0
    segment_start = 0.0
    for sample_index in range(count):
        target = perimeter * sample_index / count
        while (
            segment_index < len(loop) - 1
            and segment_start + segment_lengths[segment_index] < target
        ):
            segment_start += segment_lengths[segment_index]
            segment_index += 1
        point = loop[segment_index]
        next_point = loop[(segment_index + 1) % len(loop)]
        length = segment_lengths[segment_index]
        fraction = 0.0 if length <= 1e-12 else (target - segment_start) / length
        result.append(
            (
                point[0] + (next_point[0] - point[0]) * fraction,
                point[1] + (next_point[1] - point[1]) * fraction,
            )
        )
    return result


def vertex_preserving_resample(loop, count: int):
    """Add edge samples while retaining every original polygon vertex."""
    if count < len(loop):
        raise ValueError("Vertex-preserving resample count is smaller than the loop")
    if count == len(loop):
        return list(loop)
    lengths = [
        math.dist(loop[index], loop[(index + 1) % len(loop)])
        for index in range(len(loop))
    ]
    perimeter = sum(lengths)
    extras = count - len(loop)
    exact_allocations = [extras * length / perimeter for length in lengths]
    allocations = [int(value) for value in exact_allocations]
    remainder = extras - sum(allocations)
    ranking = sorted(
        range(len(loop)),
        key=lambda index: (exact_allocations[index] - allocations[index], lengths[index]),
        reverse=True,
    )
    for index in ranking[:remainder]:
        allocations[index] += 1

    result = []
    for index, point in enumerate(loop):
        following = loop[(index + 1) % len(loop)]
        result.append(point)
        for step in range(1, allocations[index] + 1):
            fraction = step / (allocations[index] + 1)
            result.append(
                (
                    point[0] + (following[0] - point[0]) * fraction,
                    point[1] + (following[1] - point[1]) * fraction,
                )
            )
    return result


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


def hollow_loft_solid(name: str, outer_sections, inner_sections):
    """Build a closed-bottom, open-top shell without a cavity Boolean."""
    outer_count = len(outer_sections[0][1])
    inner_count = len(inner_sections[0][1])
    if (
        len(outer_sections) < 2
        or len(inner_sections) < 2
        or outer_count != inner_count
        or any(len(loop) != outer_count for _, loop in outer_sections)
        or any(len(loop) != inner_count for _, loop in inner_sections)
    ):
        raise ValueError("Hollow loft requires equal-length outer and inner loops")
    if abs(outer_sections[-1][0] - inner_sections[-1][0]) > 1e-9:
        raise ValueError("Hollow loft outer and inner loops must share a top Z")

    vertices = []
    outer_offsets = []
    for z, loop in outer_sections:
        outer_offsets.append(len(vertices))
        vertices.extend((x, y, z) for x, y in loop)
    inner_offsets = []
    for z, loop in inner_sections:
        inner_offsets.append(len(vertices))
        vertices.extend((x, y, z) for x, y in loop)

    faces = []
    for section in range(len(outer_sections) - 1):
        low = outer_offsets[section]
        high = outer_offsets[section + 1]
        for index in range(outer_count):
            next_index = (index + 1) % outer_count
            faces.append(
                [low + index, low + next_index, high + next_index, high + index]
            )
    for section in range(len(inner_sections) - 1):
        low = inner_offsets[section]
        high = inner_offsets[section + 1]
        for index in range(inner_count):
            next_index = (index + 1) % inner_count
            faces.append(
                [low + index, high + index, high + next_index, low + next_index]
            )

    bottom_center = len(vertices)
    vertices.append((0.0, 0.0, outer_sections[0][0]))
    floor_center = len(vertices)
    vertices.append((0.0, 0.0, inner_sections[0][0]))
    outer_bottom = outer_offsets[0]
    inner_bottom = inner_offsets[0]
    outer_top = outer_offsets[-1]
    inner_top = inner_offsets[-1]
    for index in range(outer_count):
        next_index = (index + 1) % outer_count
        faces.append([bottom_center, outer_bottom + next_index, outer_bottom + index])
        faces.append([floor_center, inner_bottom + index, inner_bottom + next_index])
        faces.append(
            [
                outer_top + index,
                outer_top + next_index,
                inner_top + next_index,
                inner_top + index,
            ]
        )
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


def lid_with_alignment_lip(name: str, outer_loop, lip_outer_loop, lip_inner_loop):
    """Build the plate and downward locating ring as one manifold mesh."""
    count = len(outer_loop)
    if len(lip_outer_loop) != count or len(lip_inner_loop) != count:
        raise ValueError("Lid and alignment-lip loops must have equal lengths")
    lip_bottom_z = BASE_HEIGHT - LID_LIP_DEPTH
    vertices = []

    def add_loop(loop, z):
        offset = len(vertices)
        vertices.extend((x, y, z) for x, y in loop)
        return offset

    outer_bottom = add_loop(outer_loop, BASE_HEIGHT)
    outer_top = add_loop(outer_loop, BODY_HEIGHT)
    lip_outer_top = add_loop(lip_outer_loop, BASE_HEIGHT)
    lip_outer_bottom = add_loop(lip_outer_loop, lip_bottom_z)
    lip_inner_top = add_loop(lip_inner_loop, BASE_HEIGHT)
    lip_inner_bottom = add_loop(lip_inner_loop, lip_bottom_z)
    top_center = len(vertices)
    vertices.append((0.0, 0.0, BODY_HEIGHT))
    underside_center = len(vertices)
    vertices.append((0.0, 0.0, BASE_HEIGHT))

    faces = []
    for index in range(count):
        next_index = (index + 1) % count
        faces.append(
            [
                outer_bottom + index,
                outer_bottom + next_index,
                outer_top + next_index,
                outer_top + index,
            ]
        )
        faces.append([top_center, outer_top + index, outer_top + next_index])
        faces.append(
            [
                outer_bottom + index,
                lip_outer_top + index,
                lip_outer_top + next_index,
                outer_bottom + next_index,
            ]
        )
        faces.append(
            [
                lip_outer_bottom + index,
                lip_outer_bottom + next_index,
                lip_outer_top + next_index,
                lip_outer_top + index,
            ]
        )
        faces.append(
            [
                lip_inner_bottom + index,
                lip_inner_top + index,
                lip_inner_top + next_index,
                lip_inner_bottom + next_index,
            ]
        )
        faces.append(
            [
                lip_outer_bottom + index,
                lip_inner_bottom + index,
                lip_inner_bottom + next_index,
                lip_outer_bottom + next_index,
            ]
        )
        faces.append(
            [underside_center, lip_inner_top + next_index, lip_inner_top + index]
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


def radial_surface_distance(
    angle_deg: float, tangent_offset: float = 0.0, footprint_loop=None
) -> float:
    loop = (
        superellipse_loop(BODY_WIDTH, BODY_DEPTH)
        if footprint_loop is None
        else footprint_loop
    )
    angle = math.radians(angle_deg)
    direction = (math.cos(angle), math.sin(angle))
    tangent_axis = (-math.sin(angle), math.cos(angle))
    line_offset = (
        tangent_axis[0] * tangent_offset,
        tangent_axis[1] * tangent_offset,
    )

    def cross(a, b):
        return a[0] * b[1] - a[1] * b[0]

    hits = []
    for index, point in enumerate(loop):
        next_point = loop[(index + 1) % len(loop)]
        edge = (next_point[0] - point[0], next_point[1] - point[1])
        denominator = cross(direction, edge)
        if abs(denominator) < 1e-10:
            continue
        shifted_point = (point[0] - line_offset[0], point[1] - line_offset[1])
        radial = cross(shifted_point, edge) / denominator
        fraction = cross(shifted_point, direction) / denominator
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
    center_tangent: float = 0.0,
):
    loop = rounded_rectangle_loop(width, height, radius)
    count = len(loop)
    vertices = []
    for radial in (radial0, radial1):
        vertices.extend(
            tuple(
                axis_point(
                    angle_deg,
                    radial,
                    center_tangent + tangent,
                    center_z + local_z,
                )
            )
            for tangent, local_z in loop
        )
    low_center = len(vertices)
    vertices.append(
        tuple(axis_point(angle_deg, radial0, center_tangent, center_z))
    )
    high_center = len(vertices)
    vertices.append(
        tuple(axis_point(angle_deg, radial1, center_tangent, center_z))
    )
    faces = []
    for index in range(count):
        next_index = (index + 1) % count
        faces.append([index, count + index, count + next_index, next_index])
        faces.append([low_center, next_index, index])
        faces.append([high_center, count + index, count + next_index])
    return create_mesh_object(name, vertices, faces)


def visor_wedge(
    name: str,
    angle_deg: float,
    surface_radius: float,
    center_tangent: float = 0.0,
):
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
    vertices = [
        tuple(axis_point(angle_deg, radial, center_tangent + tangent, z))
        for radial, tangent, z in local_vertices
    ]
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


def rectangles_overlap(camera_a, camera_b, clearance=0.0) -> bool:
    corners_a = camera_xy_corners(camera_a, clearance / 2.0)
    corners_b = camera_xy_corners(camera_b, clearance / 2.0)
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


def cameras_at_radius(radius: float):
    cameras = []
    for index, angle in enumerate(camera_azimuths(), start=1):
        center = axis_point(
            angle,
            radius,
            CAMERA_ENVELOPE_TANGENTIAL_OFFSET,
            0.0,
        )
        cameras.append(
            {
                "index": index,
                "angle": angle,
                "radial": radius,
                "tangent": CAMERA_ENVELOPE_TANGENTIAL_OFFSET,
                "eye_tangent": 0.0,
                "center_xy": (center.x, center.y),
            }
        )
    return cameras


def camera_requirements_fit_eye_halfplanes(cameras) -> bool:
    requirement_points = camera_nose_requirement_points(cameras)
    for point in requirement_points:
        for camera in cameras:
            angle = math.radians(camera["angle"])
            projection = point[0] * math.cos(angle) + point[1] * math.sin(angle)
            if projection > camera["required_surface"] + CAMERA_NOSE_CONTACT_TOLERANCE:
                return False
    return True


def minimum_nonoverlap_camera_radius() -> float:
    low = 0.0
    high = max(BODY_WIDTH, BODY_DEPTH) + CAMERA_NOSE_MAX_EXPANSION
    high_cameras = cameras_at_radius(high)
    if (
        rectangles_overlap(
            high_cameras[0], high_cameras[1], CAMERA_BODY_MUTUAL_CLEARANCE
        )
        or not camera_requirements_fit_eye_halfplanes(high_cameras)
    ):
        raise ValueError(
            "Camera half-angle is too small for the configured MISSION 1 envelope "
            "and eye faces within CAMERA_NOSE_MAX_EXPANSION"
        )
    for _ in range(64):
        middle = (low + high) / 2.0
        cameras = cameras_at_radius(middle)
        if (
            rectangles_overlap(
                cameras[0], cameras[1], CAMERA_BODY_MUTUAL_CLEARANCE
            )
            or not camera_requirements_fit_eye_halfplanes(cameras)
        ):
            low = middle
        else:
            high = middle
    return high


def camera_nose_requirement_points(cameras):
    points = []
    shell_clearance = BODY_WALL_THICKNESS + CAMERA_NOSE_SHELL_CLEARANCE
    minimum_scale = camera_minimum_body_scale()
    for camera in cameras:
        points.extend(
            (x / minimum_scale, y / minimum_scale)
            for x, y in camera_xy_corners(camera, shell_clearance)
        )
        required_surface = (
            camera["radial"]
            + CAMERA_BODY_DEPTH / 2.0
            + CAMERA_FRONT_CLEARANCE
            + EYE_FACE_INSET
            + EYE_BEZEL_DEPTH
        )
        camera["required_surface"] = required_surface
        eye_half_width = EYE_BEZEL_WIDTH / 2.0 + CAMERA_NOSE_SHELL_CLEARANCE
        points.append(
            tuple(
                axis_point(
                    camera["angle"], required_surface, -eye_half_width, 0.0
                )[:2]
            )
        )
        points.append(
            tuple(
                axis_point(
                    camera["angle"], required_surface, eye_half_width, 0.0
                )[:2]
            )
        )
    return points


def build_camera_driven_footprint(cameras):
    baseline = convex_hull_2d(superellipse_loop(BODY_WIDTH, BODY_DEPTH))
    if not CAMERA_DRIVEN_NOSE_ENABLED:
        return baseline
    requirement_points = camera_nose_requirement_points(cameras)
    # The camera faces are shape constraints, not merely additions to the
    # original outline.  Clipping the baseline lets large half-angles pull the
    # corresponding sides inward, while small half-angles still broaden the
    # camera-side nose.  The rear of the rounded-triangular baseline survives.
    trimmed_baseline = baseline
    for camera in cameras:
        angle = math.radians(camera["angle"])
        trimmed_baseline = clip_convex_polygon_halfplane(
            trimmed_baseline,
            (math.cos(angle), math.sin(angle)),
            camera["required_surface"],
        )
    for point in requirement_points:
        for camera in cameras:
            angle = math.radians(camera["angle"])
            projection = point[0] * math.cos(angle) + point[1] * math.sin(angle)
            if projection > camera["required_surface"] + CAMERA_NOSE_CONTACT_TOLERANCE:
                raise ValueError(
                    "No convex minimum-spacing shell fits the configured camera "
                    "and eye envelopes. Reduce eye/bezel width or shell clearance, "
                    "or increase CAMERA_BODY_MUTUAL_CLEARANCE."
                )
    # Keep the actual hull vertices.  Uniform perimeter resampling can bridge
    # across a required corner and silently shave away configured clearance.
    result = convex_hull_2d(trimmed_baseline + requirement_points)
    result = vertex_preserving_resample(
        result,
        max(FOOTPRINT_POINTS, len(result)),
    )
    baseline_width = max(x for x, _ in baseline) - min(x for x, _ in baseline)
    baseline_depth = max(y for _, y in baseline) - min(y for _, y in baseline)
    result_width = max(x for x, _ in result) - min(x for x, _ in result)
    result_depth = max(y for _, y in result) - min(y for _, y in result)
    expansion = max(result_width - baseline_width, result_depth - baseline_depth)
    if expansion > CAMERA_NOSE_MAX_EXPANSION:
        raise ValueError(
            f"Camera-driven nose needs {expansion:.2f} mm expansion, exceeding "
            "CAMERA_NOSE_MAX_EXPANSION"
        )
    return result


def resolve_camera_layout():
    if CAMERA_DRIVEN_NOSE_ENABLED:
        cameras = cameras_at_radius(minimum_nonoverlap_camera_radius())
        footprint = build_camera_driven_footprint(cameras)
        for camera in cameras:
            surface = radial_surface_distance(camera["angle"], 0.0, footprint)
            contact_error = abs(surface - camera["required_surface"])
            if contact_error > CAMERA_NOSE_CONTACT_TOLERANCE:
                raise ValueError(
                    f"Camera {camera['index']} face misses its solved shell plane by "
                    f"{contact_error:.4f} mm"
                )
            camera["surface"] = surface
            camera["eye_inner_wall"] = surface - EYE_FACE_INSET - EYE_BEZEL_DEPTH
    else:
        footprint = convex_hull_2d(superellipse_loop(BODY_WIDTH, BODY_DEPTH))
        cameras = []
        for index, angle in enumerate(camera_azimuths(), start=1):
            surface = radial_surface_distance(angle, 0.0, footprint)
            eye_inner_wall = surface - EYE_FACE_INSET - EYE_BEZEL_DEPTH
            radial = (
                eye_inner_wall
                - CAMERA_FRONT_CLEARANCE
                - CAMERA_BODY_DEPTH / 2.0
            )
            center = axis_point(
                angle,
                radial,
                CAMERA_ENVELOPE_TANGENTIAL_OFFSET,
                0.0,
            )
            cameras.append(
                {
                    "index": index,
                    "angle": angle,
                    "radial": radial,
                    "tangent": CAMERA_ENVELOPE_TANGENTIAL_OFFSET,
                    "eye_tangent": 0.0,
                    "surface": surface,
                    "eye_inner_wall": eye_inner_wall,
                    "center_xy": (center.x, center.y),
                }
            )

    inner_loop = inset_footprint_loop(
        scale_loop(footprint, camera_minimum_body_scale()),
        BODY_WALL_THICKNESS,
    )
    if rectangles_overlap(cameras[0], cameras[1], CAMERA_BODY_MUTUAL_CLEARANCE):
        raise ValueError("Camera-driven footprint still leaves overlapping camera bodies")
    for camera in cameras:
        if not all(
            point_in_polygon(corner, inner_loop)
            for corner in camera_xy_corners(camera)
        ):
            raise ValueError(
                f"Camera {camera['index']} is not contained by the solved inner footprint"
            )
        print(
            f"CAMERA_LAYOUT {camera['index']}: center_xy="
            f"({camera['center_xy'][0]:.2f}, {camera['center_xy'][1]:.2f}) "
            f"angle={camera['angle']:.2f} "
            f"envelope_tangent={camera['tangent']:.2f} lens_tangent=0.00 "
            f"front_gap={CAMERA_FRONT_CLEARANCE:.2f}"
        )
    baseline = superellipse_loop(BODY_WIDTH, BODY_DEPTH)
    solved_width = max(x for x, _ in footprint) - min(x for x, _ in footprint)
    solved_depth = max(y for _, y in footprint) - min(y for _, y in footprint)
    baseline_width = max(x for x, _ in baseline) - min(x for x, _ in baseline)
    baseline_depth = max(y for _, y in baseline) - min(y for _, y in baseline)
    print(
        f"CAMERA_DRIVEN_FOOTPRINT dimensions=({solved_width:.2f}, {solved_depth:.2f}) "
        f"expansion=({solved_width - baseline_width:.2f}, "
        f"{solved_depth - baseline_depth:.2f})"
    )
    return cameras, footprint


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


def resolve_fastener_post_positions(cameras, footprint):
    post_minimum_scale = minimum_body_scale_between(
        BOTTOM_THICKNESS - BOOLEAN_OVERLAP,
        BASE_HEIGHT - FASTENER_POST_TOP_CLEARANCE,
    )
    inner_loop = inset_footprint_loop(
        scale_loop(footprint, post_minimum_scale), BODY_WALL_THICKNESS
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


def add_camera_openings_and_visors(base, cameras):
    # Add the raised camera surrounds first, then place each eyelid directly
    # over its corresponding opening.
    for camera in cameras:
        index = camera["index"]
        angle = camera["angle"]
        surface = camera["surface"]
        tangent = camera["eye_tangent"]
        bezel = rounded_rectangle_prism_axis(
            f"Eye_{index}_Raised_Surround",
            angle,
            surface - EYE_FACE_INSET - EYE_BEZEL_DEPTH,
            surface - EYE_FACE_INSET,
            EYE_BEZEL_WIDTH,
            EYE_BEZEL_HEIGHT,
            EYE_BEZEL_CORNER_RADIUS,
            EYE_CENTER_Z,
            center_tangent=tangent,
        )
        boolean_union(base, bezel, f"Eye_{index}_Surround_Union")
        if VISORS_ENABLED:
            boolean_union(
                base,
                visor_wedge(
                    f"Eye_{index}_Eyelid_Visor",
                    angle,
                    surface,
                    center_tangent=tangent,
                ),
                f"Eye_{index}_Visor_Union",
            )

    # Keep the two cutters in separate Boolean stages because close camera
    # angles can make their tool volumes overlap inside the body.
    for camera in cameras:
        index = camera["index"]
        angle = camera["angle"]
        surface = camera["surface"]
        tangent = camera["eye_tangent"]
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
                    center_tangent=tangent,
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


def create_base(positions, cameras, footprint):
    outer_sections = tuple(
        (z, scale_loop(footprint, scale))
        for z, scale in BODY_SECTIONS
    )
    cavity_z_values = [BOTTOM_THICKNESS]
    cavity_z_values.extend(
        z for z, _ in BODY_SECTIONS[1:-1] if BOTTOM_THICKNESS < z < BASE_HEIGHT
    )
    cavity_z_values.append(BASE_HEIGHT)
    inner_sections = []
    for z in cavity_z_values:
        scale = body_scale_at_z(z)
        inner_sections.append(
            (
                z,
                inset_footprint_loop(
                    scale_loop(footprint, scale), BODY_WALL_THICKNESS
                ),
            )
        )
    base = hollow_loft_solid(
        "Veo_3_Closed_Bottom_Base",
        outer_sections,
        tuple(inner_sections),
    )
    add_camera_openings_and_visors(base, cameras)
    add_fastener_posts(base, positions)
    base.name = "Veo_3_Cam_Cover_Closed_Base"
    return base


def create_lid(positions, footprint):
    outer_loop = list(footprint)
    if LID_LIP_ENABLED:
        lip_outer_loop = inset_footprint_loop(
            footprint, BODY_WALL_THICKNESS + LID_LIP_CLEARANCE
        )
        lip_inner_loop = inset_footprint_loop(
            lip_outer_loop,
            LID_LIP_THICKNESS,
        )
        lid = lid_with_alignment_lip(
            "Veo_3_Flat_Removable_Lid",
            outer_loop,
            lip_outer_loop,
            lip_inner_loop,
        )
    else:
        lid = loft_solid(
            "Veo_3_Flat_Removable_Lid",
            ((BASE_HEIGHT, outer_loop), (BODY_HEIGHT, outer_loop)),
        )

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
    for camera in cameras:
        lens_face_radius = camera["radial"] + CAMERA_BODY_DEPTH / 2.0
        mockup = mission1.place_canonical_dummy(
            camera["angle"],
            lens_face_radius,
            EYE_CENTER_Z,
            f"Camera_{camera['index']}_Keepout_Mockup",
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


def apply_final_visibility(base, lid) -> None:
    base.hide_set(not SHOW_MAIN_BODY_AFTER_BUILD)
    base.hide_render = not SHOW_MAIN_BODY_AFTER_BUILD
    lid.hide_set(not SHOW_TOP_AFTER_BUILD)
    lid.hide_render = not SHOW_TOP_AFTER_BUILD
    print(
        "FINAL_VISIBILITY "
        f"main_body={SHOW_MAIN_BODY_AFTER_BUILD} top={SHOW_TOP_AFTER_BUILD}"
    )


def build_original_style_cover():
    validate_config()
    if CLEAR_SCENE:
        clear_scene()
    set_units()
    cameras, footprint = resolve_camera_layout()
    positions = resolve_fastener_post_positions(cameras, footprint)
    base = create_base(positions, cameras, footprint)
    lid = create_lid(positions, footprint)
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
    apply_final_visibility(base, lid)
    return base, lid


if __name__ == "__main__":
    build_original_style_cover()
