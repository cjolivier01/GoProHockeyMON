"""Parametric, printable Veo Cam 3-style enclosure with a removable lid.

Run with the portable Blender documented in ``stl-to-python.md``::

    /tmp/blender-apt/root/usr/bin/blender \
      --background --factory-startup \
      --python veo_3_cam_cover_parametric_blender.py

The defaults reconstruct the overall envelope of ``veo_3_cam_cover.stl`` as
a clean two-piece enclosure.  Unlike the reference cover, the generated base
has a floor, a continuous wall, a mating lip, and a removable screw-fastened
lid.  Optional internal cradles hold two GoPro-sized action cameras with one
lens aimed through each of the two opposing eye openings.

All dimensions are millimeters.

Axes:
    X - enclosure width
    Y - enclosure depth; front eye looks toward -Y, rear eye toward +Y
    Z - enclosure height; the lid removes upward

The file intentionally keeps user-facing dimensions as module constants so a
Blender ``--python-expr`` invocation can import the module, override any
setting, and call :func:`build_veo_cam3_case`.
"""

from __future__ import annotations

import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


# ---------------------------------------------------------------------------
# CONFIG: build, layout, export, and preview

CLEAR_SCENE = True
LAYOUT_MODE = "assembled"  # "assembled", "print_bed", or "exploded"
PRINT_BED_GAP = 15.0
EXPLODED_LID_LIFT = 55.0
EXPLODED_CAMERA_LIFT = 10.0

EXPORT_STL = False
EXPORT_DIRECTORY = ""
EXPORT_COMBINED_STL = True
EXPORT_SEPARATE_STLS = True
NORMALIZE_SEPARATE_STLS = True  # center XY and place each part on Z=0
COMBINED_STL_NAME = "veo_3_cam_cover_parametric.stl"
BASE_STL_NAME = "veo_3_cam_cover_base.stl"
LID_STL_NAME = "veo_3_cam_cover_lid.stl"

SHOW_GOPRO_MOCKUPS = False  # viewport/render reference only; never exported
RENDER_PREVIEW = False
PREVIEW_PATH = "veo_3_cam_cover_exploded.png"
PREVIEW_RESOLUTION_X = 1200
PREVIEW_RESOLUTION_Y = 900

# Mesh and boolean quality.
FOOTPRINT_POINTS = 192
CYLINDER_SEGMENTS = 72
ROUNDED_CORNER_SEGMENTS = 12
BOOLEAN_SOLVER = "EXACT"
BOOLEAN_OVERLAP = 0.20
BOOLEAN_CLEANUP_DISTANCE = 0.0001


# ---------------------------------------------------------------------------
# CONFIG: enclosure envelope and shell

# Reference STL envelope: 215.167 x 233.661 x 70.653 mm.  The central body is
# narrower in Y; the opposing protective eye bezels create the full depth.
BODY_WIDTH = 215.17
BODY_DEPTH = 201.00
BODY_HEIGHT = 70.65
FOOTPRINT_EXPONENT = 8.0  # 2=ellipse; larger values make a rounded squircle

SEAM_Z = 58.0
BASE_FLOOR_THICKNESS = 3.2
BASE_WALL_THICKNESS = 3.2
LID_WALL_THICKNESS = 2.7
LID_TOP_THICKNESS = 3.2

# Bottom and top shaping are scale factors relative to BODY_WIDTH/BODY_DEPTH.
BOTTOM_ROUND_HEIGHT = 8.0
BOTTOM_SCALE = 0.92
LID_DOME_SECTIONS = (
    # (absolute Z, footprint scale)
    (SEAM_Z, 1.00),
    (63.5, 1.00),
    (66.5, 0.975),
    (69.0, 0.91),
    (BODY_HEIGHT, 0.79),
)

# Male base lip / female lid fit.  The screw bosses are the primary closure;
# the lip aligns the pieces and limits dust ingress.
LIP_ENABLED = True
LIP_HEIGHT = 5.0
LIP_THICKNESS = 1.8
LIP_CLEARANCE = 0.30  # clearance on each side of the male lip

# Optional cord-gasket groove cut into the top of the base wall.
GASKET_GROOVE_ENABLED = False
GASKET_GROOVE_WIDTH = 1.2
GASKET_GROOVE_DEPTH = 0.8
GASKET_GROOVE_OUTER_INSET = 0.75


# ---------------------------------------------------------------------------
# CONFIG: paired eye openings and protective bezels

EYES_ENABLED = True
FRONT_EYE_CENTER_X = -40.0
REAR_EYE_CENTER_X = 40.0
EYE_CENTER_Z = 28.0

# The opening flares outward to reduce wide-angle lens vignetting.
EYE_INNER_WIDTH = 58.0
EYE_INNER_HEIGHT = 40.0
EYE_OUTER_WIDTH = 68.0
EYE_OUTER_HEIGHT = 42.0
EYE_CORNER_RADIUS = 12.0

EYE_BEZEL_RIM = 4.5
# Chosen so the default total Y envelope is approximately the source STL.
EYE_BEZEL_PROJECTION = (233.661 - BODY_DEPTH) / 2.0
EYE_BROW_ENABLED = True
EYE_BROW_EXTRA_PROJECTION = 0.0
EYE_BROW_HEIGHT = 3.6
EYE_BROW_SIDE_OVERHANG = 3.0


# ---------------------------------------------------------------------------
# CONFIG: removable-lid fasteners

LID_FASTENERS_ENABLED = True
LID_FASTENER_POSITIONS_XY = (
    (-75.0, -34.0),
    (75.0, -34.0),
    (-75.0, 34.0),
    (75.0, 34.0),
)
LID_FASTENER_BASE_BOSS_DIAMETER = 10.0
LID_FASTENER_LID_BOSS_DIAMETER = 10.0
LID_FASTENER_CLEARANCE_DIAMETER = 3.4  # M3 clearance
LID_FASTENER_BASE_PILOT_DIAMETER = 4.2  # typical M3 heat-set insert pocket
LID_FASTENER_BASE_PILOT_DEPTH = 11.0
LID_FASTENER_COUNTERBORE_DIAMETER = 6.5
LID_FASTENER_COUNTERBORE_DEPTH = 3.0
LID_FASTENER_COLUMN_BOTTOM_CLEARANCE = 0.35


# ---------------------------------------------------------------------------
# CONFIG: optional dual-GoPro mounting

GOPRO_MOUNT_STYLE = "cradle"  # "cradle", "fingers", or "none"

# GoPro HERO 9-13-sized body envelope; adjust for another camera.
GOPRO_BODY_WIDTH = 71.8
GOPRO_BODY_DEPTH = 33.6
GOPRO_BODY_HEIGHT = 50.8
GOPRO_BODY_CLEARANCE_XY = 0.7
GOPRO_BODY_CLEARANCE_Z = 0.6

# Lens offsets are measured from camera body center in world coordinates.
# The default camera orientation is upside-down so the offset lens aligns to
# the relatively low Veo eye while leaving material beneath the cradle.
FRONT_GOPRO_LENS_OFFSET_X = 10.0
REAR_GOPRO_LENS_OFFSET_X = -10.0
GOPRO_LENS_OFFSET_Z = -7.0
GOPRO_LENS_CLEARANCE_FROM_INNER_WALL = 3.5

# Open-top cradle.  The lid provides final vertical retention when installed.
CRADLE_PLATFORM_SIDE_CLEARANCE = 0.7
CRADLE_PLATFORM_TOP_CLEARANCE = 0.5
CRADLE_RAIL_THICKNESS = 2.2
CRADLE_RAIL_HEIGHT = 11.0
CRADLE_RAIL_BASE_OVERLAP = 3.0
CRADLE_RAIL_PLATFORM_OVERLAP = 0.8
CRADLE_RAIL_END_LENGTH = 13.0
CRADLE_DETENTS_ENABLED = True
CRADLE_DETENT_PROJECTION = 0.55
CRADLE_DETENT_HEIGHT = 1.2

# Alternative standard three-prong GoPro mount built into the floor.
GOPRO_FINGER_COUNT = 3
GOPRO_FINGER_THICKNESS = 3.0
GOPRO_FINGER_GAP = 3.2
GOPRO_FINGER_DEPTH = 12.0
GOPRO_FINGER_HEIGHT = 14.0
GOPRO_FINGER_PIN_DIAMETER = 5.2
GOPRO_FINGER_BASE_WIDTH = 30.0
GOPRO_FINGER_BASE_DEPTH = 22.0
GOPRO_FINGER_BASE_HEIGHT = 3.0


# ---------------------------------------------------------------------------
# CONFIG: optional service openings and bottom mount

# Disabled defaults keep the enclosure closed except for eyes and screw bores.
CABLE_PORT_ENABLED = False
CABLE_PORT_SIDE = "right"  # "left" or "right"
CABLE_PORT_DIAMETER = 12.0
CABLE_PORT_CENTER_Y = 0.0
CABLE_PORT_CENTER_Z = 20.0

VENTS_ENABLED = False
VENT_SIDE = "right"
VENT_COUNT = 5
VENT_SLOT_DEPTH_Y = 18.0
VENT_SLOT_HEIGHT_Z = 2.2
VENT_SLOT_SPACING_Z = 5.0
VENT_CENTER_Y = 0.0
VENT_CENTER_Z = 26.0

BOTTOM_INSERT_ENABLED = False
BOTTOM_INSERT_BOSS_DIAMETER = 20.0
BOTTOM_INSERT_POCKET_DIAMETER = 8.5  # approximately 1/4-20 insert OD
BOTTOM_INSERT_POCKET_DEPTH = 8.5
BOTTOM_INSERT_BOSS_HEIGHT = 12.0


# Viewport and preview colors (STL does not retain materials).
BASE_COLOR = (0.08, 0.28, 0.62, 1.0)
LID_COLOR = (0.10, 0.62, 0.34, 1.0)
GOPRO_COLOR = (0.035, 0.04, 0.05, 1.0)
LENS_COLOR = (0.02, 0.10, 0.16, 1.0)


# ---------------------------------------------------------------------------
# Configuration helpers and validation


def inner_base_width() -> float:
    return BODY_WIDTH - 2.0 * BASE_WALL_THICKNESS


def inner_base_depth() -> float:
    return BODY_DEPTH - 2.0 * BASE_WALL_THICKNESS


def inner_lid_width() -> float:
    return BODY_WIDTH - 2.0 * LID_WALL_THICKNESS


def inner_lid_depth() -> float:
    return BODY_DEPTH - 2.0 * LID_WALL_THICKNESS


def lip_outer_width() -> float:
    return inner_lid_width() - 2.0 * LIP_CLEARANCE


def lip_outer_depth() -> float:
    return inner_lid_depth() - 2.0 * LIP_CLEARANCE


def camera_specs():
    """Return name, facing sign, eye X, lens-X offset for both cameras."""
    return (
        ("Front", -1.0, FRONT_EYE_CENTER_X, FRONT_GOPRO_LENS_OFFSET_X),
        ("Rear", 1.0, REAR_EYE_CENTER_X, REAR_GOPRO_LENS_OFFSET_X),
    )


def camera_body_center(facing: float, eye_x: float, lens_offset_x: float):
    x = eye_x - lens_offset_x
    wall_inner_y = facing * (BODY_DEPTH / 2.0 - BASE_WALL_THICKNESS)
    # Moving opposite the facing sign goes inward from either exterior wall.
    y = wall_inner_y - facing * (
        GOPRO_LENS_CLEARANCE_FROM_INNER_WALL + GOPRO_BODY_DEPTH / 2.0
    )
    z = EYE_CENTER_Z - GOPRO_LENS_OFFSET_Z
    return (x, y, z)


def superellipse_value(x: float, y: float, width: float, depth: float) -> float:
    return (abs(x) / (width / 2.0)) ** FOOTPRINT_EXPONENT + (
        abs(y) / (depth / 2.0)
    ) ** FOOTPRINT_EXPONENT


def validate_config() -> None:
    positive = {
        "BODY_WIDTH": BODY_WIDTH,
        "BODY_DEPTH": BODY_DEPTH,
        "BODY_HEIGHT": BODY_HEIGHT,
        "SEAM_Z": SEAM_Z,
        "BASE_FLOOR_THICKNESS": BASE_FLOOR_THICKNESS,
        "BASE_WALL_THICKNESS": BASE_WALL_THICKNESS,
        "LID_WALL_THICKNESS": LID_WALL_THICKNESS,
        "LID_TOP_THICKNESS": LID_TOP_THICKNESS,
        "BOTTOM_ROUND_HEIGHT": BOTTOM_ROUND_HEIGHT,
        "LIP_HEIGHT": LIP_HEIGHT,
        "LIP_THICKNESS": LIP_THICKNESS,
        "EYE_INNER_WIDTH": EYE_INNER_WIDTH,
        "EYE_INNER_HEIGHT": EYE_INNER_HEIGHT,
        "EYE_OUTER_WIDTH": EYE_OUTER_WIDTH,
        "EYE_OUTER_HEIGHT": EYE_OUTER_HEIGHT,
        "EYE_BEZEL_RIM": EYE_BEZEL_RIM,
        "GOPRO_BODY_WIDTH": GOPRO_BODY_WIDTH,
        "GOPRO_BODY_DEPTH": GOPRO_BODY_DEPTH,
        "GOPRO_BODY_HEIGHT": GOPRO_BODY_HEIGHT,
    }
    for name, value in positive.items():
        if value <= 0.0:
            raise ValueError(f"{name} must be positive")

    if LAYOUT_MODE not in {"assembled", "print_bed", "exploded"}:
        raise ValueError('LAYOUT_MODE must be "assembled", "print_bed", or "exploded"')
    if GOPRO_MOUNT_STYLE not in {"cradle", "fingers", "none"}:
        raise ValueError('GOPRO_MOUNT_STYLE must be "cradle", "fingers", or "none"')
    if CABLE_PORT_SIDE not in {"left", "right"} or VENT_SIDE not in {
        "left",
        "right",
    }:
        raise ValueError('Port/vent sides must be "left" or "right"')
    if FOOTPRINT_POINTS < 32 or FOOTPRINT_POINTS % 4:
        raise ValueError("FOOTPRINT_POINTS must be a multiple of 4 and at least 32")
    if FOOTPRINT_EXPONENT < 2.0:
        raise ValueError("FOOTPRINT_EXPONENT must be at least 2")
    if not BASE_FLOOR_THICKNESS < BOTTOM_ROUND_HEIGHT < SEAM_Z:
        raise ValueError("Bottom rounding must sit above the floor and below the seam")
    if not SEAM_Z < BODY_HEIGHT - LID_TOP_THICKNESS:
        raise ValueError("The seam leaves no usable lid interior")
    if not 0.5 <= BOTTOM_SCALE <= 1.0:
        raise ValueError("BOTTOM_SCALE must be between 0.5 and 1.0")
    if inner_base_width() <= 0.0 or inner_base_depth() <= 0.0:
        raise ValueError("Base walls leave no interior")
    if inner_lid_width() <= 0.0 or inner_lid_depth() <= 0.0:
        raise ValueError("Lid walls leave no interior")
    if LIP_ENABLED:
        if LIP_THICKNESS * 2.0 >= min(lip_outer_width(), lip_outer_depth()):
            raise ValueError("LIP_THICKNESS leaves no opening")
        # The lip must overlap the top of the base wall so it is connected.
        if lip_outer_width() <= inner_base_width() or lip_outer_depth() <= inner_base_depth():
            raise ValueError("Lip does not overlap the base wall; reduce lid wall/clearance")
    if EYE_OUTER_WIDTH < EYE_INNER_WIDTH or EYE_OUTER_HEIGHT < EYE_INNER_HEIGHT:
        raise ValueError("The eye flare must not narrow toward the exterior")
    eye_outer_top = EYE_CENTER_Z + EYE_OUTER_HEIGHT / 2.0 + EYE_BEZEL_RIM
    if EYES_ENABLED and eye_outer_top >= SEAM_Z:
        raise ValueError("Eye bezel reaches the lid seam; lower or shrink the eye")
    if EYES_ENABLED and EYE_CENTER_Z - EYE_OUTER_HEIGHT / 2.0 - EYE_BEZEL_RIM <= 0.0:
        raise ValueError("Eye bezel reaches below the enclosure")

    if tuple(sorted(z for z, _ in LID_DOME_SECTIONS)) != tuple(
        z for z, _ in LID_DOME_SECTIONS
    ):
        raise ValueError("LID_DOME_SECTIONS must be ordered by increasing Z")
    if abs(LID_DOME_SECTIONS[0][0] - SEAM_Z) > 1e-6:
        raise ValueError("The first lid section must start at SEAM_Z")
    if abs(LID_DOME_SECTIONS[-1][0] - BODY_HEIGHT) > 1e-6:
        raise ValueError("The final lid section must be at BODY_HEIGHT")

    if GOPRO_MOUNT_STYLE != "none":
        for name, facing, eye_x, lens_x in camera_specs():
            cx, cy, cz = camera_body_center(facing, eye_x, lens_x)
            if cz - GOPRO_BODY_HEIGHT / 2.0 <= BASE_FLOOR_THICKNESS:
                raise ValueError(f"{name} GoPro intersects the base floor")
            if cz + GOPRO_BODY_HEIGHT / 2.0 >= BODY_HEIGHT - LID_TOP_THICKNESS:
                raise ValueError(f"{name} GoPro intersects the lid roof")
            # All four XY corners must fit the nominal inner footprint.
            for sx in (-1.0, 1.0):
                for sy in (-1.0, 1.0):
                    x = cx + sx * (GOPRO_BODY_WIDTH / 2.0 + GOPRO_BODY_CLEARANCE_XY)
                    y = cy + sy * (GOPRO_BODY_DEPTH / 2.0 + GOPRO_BODY_CLEARANCE_XY)
                    value = superellipse_value(x, y, inner_lid_width(), inner_lid_depth())
                    if value >= 1.0:
                        raise ValueError(
                            f"{name} GoPro does not fit the inner footprint (value={value:.3f})"
                        )


# ---------------------------------------------------------------------------
# Scene and mesh helpers


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


def cleanup_boolean_mesh(obj) -> None:
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


def superellipse_loop(width: float, depth: float, exponent: float = None, count: int = None):
    exponent = FOOTPRINT_EXPONENT if exponent is None else exponent
    count = FOOTPRINT_POINTS if count is None else count
    power = 2.0 / exponent
    points = []
    for index in range(count):
        angle = 2.0 * math.pi * index / count
        cosine = math.cos(angle)
        sine = math.sin(angle)
        x = width / 2.0 * math.copysign(abs(cosine) ** power, cosine)
        y = depth / 2.0 * math.copysign(abs(sine) ** power, sine)
        points.append((x, y))
    return points


def rounded_rectangle_loop(width: float, height: float, radius: float):
    radius = min(max(radius, 0.0), width / 2.0, height / 2.0)
    if radius <= 0.0:
        return [
            (width / 2.0, height / 2.0),
            (-width / 2.0, height / 2.0),
            (-width / 2.0, -height / 2.0),
            (width / 2.0, -height / 2.0),
        ]
    points = []
    corners = (
        (width / 2.0 - radius, height / 2.0 - radius, 0.0, 90.0),
        (-width / 2.0 + radius, height / 2.0 - radius, 90.0, 180.0),
        (-width / 2.0 + radius, -height / 2.0 + radius, 180.0, 270.0),
        (width / 2.0 - radius, -height / 2.0 + radius, 270.0, 360.0),
    )
    for cx, cy, start, end in corners:
        for step in range(ROUNDED_CORNER_SEGMENTS):
            angle = math.radians(start + (end - start) * step / ROUNDED_CORNER_SEGMENTS)
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def loft_solid(name: str, sections):
    """Create a closed Z loft from ``(z, loop)`` sections of equal length."""
    if len(sections) < 2:
        raise ValueError("A loft needs at least two sections")
    count = len(sections[0][1])
    if any(len(loop) != count for _, loop in sections):
        raise ValueError("All loft loops must have the same vertex count")
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
        raise ValueError("Ring loops must have the same vertex count")
    count = len(outer_loop)
    vertices = []
    vertices.extend((x, y, z0) for x, y in outer_loop)
    vertices.extend((x, y, z1) for x, y in outer_loop)
    vertices.extend((x, y, z0) for x, y in inner_loop)
    vertices.extend((x, y, z1) for x, y in inner_loop)
    outer0 = 0
    outer1 = count
    inner0 = count * 2
    inner1 = count * 3
    faces = []
    for i in range(count):
        j = (i + 1) % count
        faces.append([outer0 + i, outer0 + j, outer1 + j, outer1 + i])
        faces.append([inner0 + j, inner0 + i, inner1 + i, inner1 + j])
        faces.append([outer0 + i, inner0 + i, inner0 + j, outer0 + j])
        faces.append([outer1 + j, inner1 + j, inner1 + i, outer1 + i])
    return create_mesh_object(name, vertices, faces)


def polygon_prism_y(name: str, loop, y0: float, y1: float, center_x=0.0, center_z=0.0):
    points = [(x + center_x, z + center_z) for x, z in loop]
    count = len(points)
    vertices = [(x, y0, z) for x, z in points]
    vertices.extend((x, y1, z) for x, z in points)
    center_x_value = sum(x for x, _ in points) / count
    center_z_value = sum(z for _, z in points) / count
    low_center = len(vertices)
    vertices.append((center_x_value, y0, center_z_value))
    high_center = len(vertices)
    vertices.append((center_x_value, y1, center_z_value))
    faces = []
    for i in range(count):
        j = (i + 1) % count
        faces.append([i, count + i, count + j, j])
        faces.append([low_center, j, i])
        faces.append([high_center, count + i, count + j])
    return create_mesh_object(name, vertices, faces)


def rounded_rectangle_prism_y(
    name: str,
    width: float,
    height: float,
    radius: float,
    y0: float,
    y1: float,
    center_x=0.0,
    center_z=0.0,
):
    return polygon_prism_y(
        name,
        rounded_rectangle_loop(width, height, radius),
        y0,
        y1,
        center_x,
        center_z,
    )


def tapered_eye_prism(name: str, facing: float, eye_x: float):
    """Flared rounded-rectangle eye cutter running along Y."""
    outside_y = facing * (BODY_DEPTH / 2.0 + EYE_BEZEL_PROJECTION + BOOLEAN_OVERLAP)
    inside_y = facing * (BODY_DEPTH / 2.0 - BASE_WALL_THICKNESS - 2.0)
    if facing < 0.0:
        y_positions = (outside_y, inside_y)
        dims = (
            (EYE_OUTER_WIDTH, EYE_OUTER_HEIGHT),
            (EYE_INNER_WIDTH, EYE_INNER_HEIGHT),
        )
    else:
        y_positions = (inside_y, outside_y)
        dims = (
            (EYE_INNER_WIDTH, EYE_INNER_HEIGHT),
            (EYE_OUTER_WIDTH, EYE_OUTER_HEIGHT),
        )
    loops = [
        rounded_rectangle_loop(width, height, min(EYE_CORNER_RADIUS, height / 2.0))
        for width, height in dims
    ]
    count = len(loops[0])
    vertices = []
    for y, loop in zip(y_positions, loops):
        vertices.extend((x + eye_x, y, z + EYE_CENTER_Z) for x, z in loop)

    def vertex(section, index):
        return section * count + index % count

    faces = []
    for i in range(count):
        j = (i + 1) % count
        faces.append([vertex(0, i), vertex(1, i), vertex(1, j), vertex(0, j)])
    centers = []
    for y in y_positions:
        centers.append(len(vertices))
        vertices.append((eye_x, y, EYE_CENTER_Z))
    for i in range(count):
        j = (i + 1) % count
        faces.append([centers[0], vertex(0, i), vertex(0, j)])
        faces.append([centers[1], vertex(1, j), vertex(1, i)])
    return create_mesh_object(name, vertices, faces)


def add_box(name: str, dimensions, location, rotation=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.rotation_euler = rotation
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    return obj


def add_beveled_box(name: str, dimensions, location, bevel: float):
    obj = add_box(name, dimensions, location)
    modifier = obj.modifiers.new(name + "_Bevel", "BEVEL")
    modifier.width = min(max(bevel, 0.0), min(dimensions) / 2.1)
    modifier.segments = 3
    modifier.affect = "EDGES"
    select_only(obj)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    recalc_normals(obj)
    return obj


def add_cylinder_z(name: str, radius: float, z0: float, z1: float, x=0.0, y=0.0):
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


def add_cylinder_x(name: str, radius: float, x0: float, x1: float, y=0.0, z=0.0):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=CYLINDER_SEGMENTS,
        radius=radius,
        depth=x1 - x0,
        location=((x0 + x1) / 2.0, y, z),
        rotation=(0.0, math.pi / 2.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name + "_Mesh"
    return obj


# ---------------------------------------------------------------------------
# Boolean helpers


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
    cleanup_boolean_mesh(base)
    recalc_normals(base)
    return base


def boolean_union(base, part, label="Union"):
    return apply_boolean(base, part, "UNION", label + "_" + part.name)


def boolean_difference(base, tools, label="Cut"):
    tools = list(tools)
    if not tools:
        return base
    return apply_boolean(base, join_tools(label + "_Tools", tools), "DIFFERENCE", label)


# ---------------------------------------------------------------------------
# Base construction


def create_base_shell():
    outer_sections = (
        (0.0, superellipse_loop(BODY_WIDTH * BOTTOM_SCALE, BODY_DEPTH * BOTTOM_SCALE)),
        (BOTTOM_ROUND_HEIGHT, superellipse_loop(BODY_WIDTH, BODY_DEPTH)),
        (SEAM_Z, superellipse_loop(BODY_WIDTH, BODY_DEPTH)),
    )
    base = loft_solid("Veo_Case_Base", outer_sections)

    floor_scale = BOTTOM_SCALE + (1.0 - BOTTOM_SCALE) * (
        BASE_FLOOR_THICKNESS / BOTTOM_ROUND_HEIGHT
    )
    cavity_sections = (
        (
            BASE_FLOOR_THICKNESS,
            superellipse_loop(
                BODY_WIDTH * floor_scale - 2.0 * BASE_WALL_THICKNESS,
                BODY_DEPTH * floor_scale - 2.0 * BASE_WALL_THICKNESS,
            ),
        ),
        (
            BOTTOM_ROUND_HEIGHT,
            superellipse_loop(inner_base_width(), inner_base_depth()),
        ),
        (
            SEAM_Z + BOOLEAN_OVERLAP,
            superellipse_loop(inner_base_width(), inner_base_depth()),
        ),
    )
    boolean_difference(base, [loft_solid("Base_Cavity", cavity_sections)], "Base_Cavity")

    if LIP_ENABLED:
        outer = superellipse_loop(lip_outer_width(), lip_outer_depth())
        inner = superellipse_loop(
            lip_outer_width() - 2.0 * LIP_THICKNESS,
            lip_outer_depth() - 2.0 * LIP_THICKNESS,
        )
        lip = ring_prism(
            "Base_Alignment_Lip",
            outer,
            inner,
            SEAM_Z - BOOLEAN_OVERLAP,
            SEAM_Z + LIP_HEIGHT,
        )
        boolean_union(base, lip, "Base_Lip_Union")

    add_eye_bezels(base)
    add_base_fastener_bosses(base)
    add_gopro_mounts(base)
    add_bottom_insert(base)
    cut_base_openings(base)
    return base


def add_eye_bezels(base):
    if not EYES_ENABLED:
        return base
    outer_width = EYE_OUTER_WIDTH + 2.0 * EYE_BEZEL_RIM
    outer_height = EYE_OUTER_HEIGHT + 2.0 * EYE_BEZEL_RIM
    radius = EYE_CORNER_RADIUS + EYE_BEZEL_RIM
    for name, facing, eye_x, _ in camera_specs():
        wall_y = facing * BODY_DEPTH / 2.0
        outside_y = facing * (BODY_DEPTH / 2.0 + EYE_BEZEL_PROJECTION)
        y0, y1 = sorted((wall_y - facing * BOOLEAN_OVERLAP, outside_y))
        bezel = rounded_rectangle_prism_y(
            f"{name}_Eye_Bezel",
            outer_width,
            outer_height,
            radius,
            y0,
            y1,
            eye_x,
            EYE_CENTER_Z,
        )
        boolean_union(base, bezel, f"{name}_Eye_Bezel_Union")
        if EYE_BROW_ENABLED:
            brow_width = outer_width + 2.0 * EYE_BROW_SIDE_OVERHANG
            brow_depth = EYE_BEZEL_PROJECTION + EYE_BROW_EXTRA_PROJECTION
            brow_center_y = facing * (
                BODY_DEPTH / 2.0 + brow_depth / 2.0 - BOOLEAN_OVERLAP
            )
            brow_z = EYE_CENTER_Z + outer_height / 2.0 - EYE_BROW_HEIGHT / 2.0
            brow = add_beveled_box(
                f"{name}_Eye_Brow",
                (brow_width, brow_depth + BOOLEAN_OVERLAP, EYE_BROW_HEIGHT),
                (eye_x, brow_center_y, brow_z),
                EYE_BROW_HEIGHT / 2.5,
            )
            boolean_union(base, brow, f"{name}_Eye_Brow_Union")
    return base


def add_base_fastener_bosses(base):
    if not LID_FASTENERS_ENABLED:
        return base
    for index, (x, y) in enumerate(LID_FASTENER_POSITIONS_XY, start=1):
        boss = add_cylinder_z(
            f"Base_Fastener_Boss_{index}",
            LID_FASTENER_BASE_BOSS_DIAMETER / 2.0,
            BASE_FLOOR_THICKNESS - BOOLEAN_OVERLAP,
            SEAM_Z + BOOLEAN_OVERLAP,
            x,
            y,
        )
        boolean_union(base, boss, f"Base_Fastener_Boss_{index}_Union")
    return base


def cradle_platform_top_z() -> float:
    body_bottom = EYE_CENTER_Z - GOPRO_LENS_OFFSET_Z - GOPRO_BODY_HEIGHT / 2.0
    return body_bottom - CRADLE_PLATFORM_TOP_CLEARANCE


def add_cradle(base, name: str, facing: float, center):
    cx, cy, _ = center
    platform_width = GOPRO_BODY_WIDTH + 2.0 * CRADLE_PLATFORM_SIDE_CLEARANCE
    platform_depth = GOPRO_BODY_DEPTH + 2.0 * CRADLE_PLATFORM_SIDE_CLEARANCE
    platform_top = cradle_platform_top_z()
    platform = add_beveled_box(
        f"{name}_GoPro_Platform",
        (
            platform_width,
            platform_depth,
            platform_top - BASE_FLOOR_THICKNESS + BOOLEAN_OVERLAP,
        ),
        (
            cx,
            cy,
            (BASE_FLOOR_THICKNESS + platform_top - BOOLEAN_OVERLAP) / 2.0,
        ),
        0.7,
    )
    boolean_union(base, platform, f"{name}_GoPro_Platform_Union")

    rail_z0 = platform_top - CRADLE_RAIL_BASE_OVERLAP
    rail_z1 = platform_top + CRADLE_RAIL_HEIGHT
    rail_z = (rail_z0 + rail_z1) / 2.0
    rail_total_height = rail_z1 - rail_z0
    rail_depth = platform_depth
    for side in (-1.0, 1.0):
        rail_x = cx + side * (
            GOPRO_BODY_WIDTH / 2.0
            + GOPRO_BODY_CLEARANCE_XY
            + CRADLE_RAIL_THICKNESS / 2.0
            - CRADLE_RAIL_PLATFORM_OVERLAP
        )
        rail = add_beveled_box(
            f"{name}_GoPro_Side_Rail_{'L' if side < 0 else 'R'}",
            (CRADLE_RAIL_THICKNESS, rail_depth, rail_total_height),
            (rail_x, cy, rail_z),
            0.7,
        )
        boolean_union(base, rail, f"{name}_GoPro_Side_Rail_Union")
        if CRADLE_DETENTS_ENABLED:
            detent_x = rail_x - side * (
                CRADLE_RAIL_THICKNESS / 2.0 + CRADLE_DETENT_PROJECTION / 2.0
            )
            detent = add_beveled_box(
                f"{name}_GoPro_Detent_{'L' if side < 0 else 'R'}",
                (
                    CRADLE_DETENT_PROJECTION + BOOLEAN_OVERLAP,
                    CRADLE_RAIL_END_LENGTH,
                    CRADLE_DETENT_HEIGHT,
                ),
                (
                    detent_x,
                    cy - facing * (platform_depth - CRADLE_RAIL_END_LENGTH) / 2.0,
                    platform_top + CRADLE_RAIL_HEIGHT - CRADLE_DETENT_HEIGHT / 2.0,
                ),
                0.35,
            )
            boolean_union(base, detent, f"{name}_GoPro_Detent_Union")

    # A low stop on the inward side leaves the lens-facing side unobstructed.
    stop_y = cy - facing * (
        GOPRO_BODY_DEPTH / 2.0
        + GOPRO_BODY_CLEARANCE_XY
        + CRADLE_RAIL_THICKNESS / 2.0
    ) + facing * CRADLE_RAIL_PLATFORM_OVERLAP
    stop = add_beveled_box(
        f"{name}_GoPro_Inward_Stop",
        (platform_width, CRADLE_RAIL_THICKNESS, rail_total_height),
        (cx, stop_y, rail_z),
        0.7,
    )
    boolean_union(base, stop, f"{name}_GoPro_Inward_Stop_Union")
    return base


def add_finger_mount(base, name: str, center):
    cx, cy, _ = center
    base_top = BASE_FLOOR_THICKNESS + GOPRO_FINGER_BASE_HEIGHT
    pad = add_beveled_box(
        f"{name}_GoPro_Finger_Base",
        (GOPRO_FINGER_BASE_WIDTH, GOPRO_FINGER_BASE_DEPTH, GOPRO_FINGER_BASE_HEIGHT),
        (cx, cy, BASE_FLOOR_THICKNESS + GOPRO_FINGER_BASE_HEIGHT / 2.0 - BOOLEAN_OVERLAP),
        1.0,
    )
    boolean_union(base, pad, f"{name}_GoPro_Finger_Base_Union")
    pitch = GOPRO_FINGER_THICKNESS + GOPRO_FINGER_GAP
    start = -(GOPRO_FINGER_COUNT - 1) * pitch / 2.0
    for index in range(GOPRO_FINGER_COUNT):
        x = cx + start + index * pitch
        finger = add_beveled_box(
            f"{name}_GoPro_Finger_{index + 1}",
            (GOPRO_FINGER_THICKNESS, GOPRO_FINGER_DEPTH, GOPRO_FINGER_HEIGHT),
            (x, cy, base_top + GOPRO_FINGER_HEIGHT / 2.0 - BOOLEAN_OVERLAP),
            1.0,
        )
        boolean_union(base, finger, f"{name}_GoPro_Finger_Union")
    pin_z = base_top + GOPRO_FINGER_HEIGHT * 0.68
    cutter = add_cylinder_x(
        f"{name}_GoPro_Pin_Hole",
        GOPRO_FINGER_PIN_DIAMETER / 2.0,
        cx - GOPRO_FINGER_BASE_WIDTH / 2.0,
        cx + GOPRO_FINGER_BASE_WIDTH / 2.0,
        cy,
        pin_z,
    )
    boolean_difference(base, [cutter], f"{name}_GoPro_Pin_Hole")
    return base


def add_gopro_mounts(base):
    if GOPRO_MOUNT_STYLE == "none":
        return base
    for name, facing, eye_x, lens_x in camera_specs():
        center = camera_body_center(facing, eye_x, lens_x)
        if GOPRO_MOUNT_STYLE == "cradle":
            add_cradle(base, name, facing, center)
        else:
            add_finger_mount(base, name, center)
    return base


def add_bottom_insert(base):
    if not BOTTOM_INSERT_ENABLED:
        return base
    boss = add_cylinder_z(
        "Bottom_Insert_Boss",
        BOTTOM_INSERT_BOSS_DIAMETER / 2.0,
        BASE_FLOOR_THICKNESS - BOOLEAN_OVERLAP,
        BOTTOM_INSERT_BOSS_HEIGHT,
    )
    boolean_union(base, boss, "Bottom_Insert_Boss_Union")
    return base


def cut_base_openings(base):
    cutters = []
    if EYES_ENABLED:
        for name, facing, eye_x, _ in camera_specs():
            cutters.append(tapered_eye_prism(f"{name}_Eye_Opening", facing, eye_x))

    if LID_FASTENERS_ENABLED:
        for index, (x, y) in enumerate(LID_FASTENER_POSITIONS_XY, start=1):
            cutters.append(
                add_cylinder_z(
                    f"Base_Fastener_Pilot_{index}",
                    LID_FASTENER_BASE_PILOT_DIAMETER / 2.0,
                    SEAM_Z - LID_FASTENER_BASE_PILOT_DEPTH,
                    SEAM_Z + BOOLEAN_OVERLAP * 2.0,
                    x,
                    y,
                )
            )

    # These default cutters are mutually disjoint and can share one boolean.
    boolean_difference(base, cutters, "Base_Eyes_And_Fastener_Pilots")

    if GASKET_GROOVE_ENABLED:
        outer = superellipse_loop(
            BODY_WIDTH - 2.0 * GASKET_GROOVE_OUTER_INSET,
            BODY_DEPTH - 2.0 * GASKET_GROOVE_OUTER_INSET,
        )
        inner = superellipse_loop(
            BODY_WIDTH - 2.0 * (GASKET_GROOVE_OUTER_INSET + GASKET_GROOVE_WIDTH),
            BODY_DEPTH - 2.0 * (GASKET_GROOVE_OUTER_INSET + GASKET_GROOVE_WIDTH),
        )
        boolean_difference(
            base,
            [ring_prism(
                "Gasket_Groove",
                outer,
                inner,
                SEAM_Z - GASKET_GROOVE_DEPTH,
                SEAM_Z + BOOLEAN_OVERLAP,
            )],
            "Gasket_Groove",
        )

    if CABLE_PORT_ENABLED:
        side = -1.0 if CABLE_PORT_SIDE == "left" else 1.0
        boolean_difference(
            base,
            [add_cylinder_x(
                "Cable_Port",
                CABLE_PORT_DIAMETER / 2.0,
                side * BODY_WIDTH / 2.0 - side * (BASE_WALL_THICKNESS + 2.0),
                side * (BODY_WIDTH / 2.0 + 2.0),
                CABLE_PORT_CENTER_Y,
                CABLE_PORT_CENTER_Z,
            )],
            "Cable_Port",
        )

    if VENTS_ENABLED:
        side = -1.0 if VENT_SIDE == "left" else 1.0
        x = side * BODY_WIDTH / 2.0
        x_extent = BASE_WALL_THICKNESS + 4.0
        vent_cutters = []
        for index in range(VENT_COUNT):
            z = VENT_CENTER_Z + (index - (VENT_COUNT - 1) / 2.0) * VENT_SLOT_SPACING_Z
            vent_cutters.append(
                add_beveled_box(
                    f"Vent_Slot_{index + 1}",
                    (x_extent, VENT_SLOT_DEPTH_Y, VENT_SLOT_HEIGHT_Z),
                    (x - side * (BASE_WALL_THICKNESS / 2.0), VENT_CENTER_Y, z),
                    VENT_SLOT_HEIGHT_Z / 2.0,
                )
            )
        boolean_difference(base, vent_cutters, "Vent_Slots")

    if BOTTOM_INSERT_ENABLED:
        boolean_difference(
            base,
            [add_cylinder_z(
                "Bottom_Insert_Pocket",
                BOTTOM_INSERT_POCKET_DIAMETER / 2.0,
                -BOOLEAN_OVERLAP,
                BOTTOM_INSERT_POCKET_DEPTH,
            )],
            "Bottom_Insert_Pocket",
        )
    return base


# ---------------------------------------------------------------------------
# Lid construction


def lid_scale_at_z(z: float) -> float:
    sections = LID_DOME_SECTIONS
    if z <= sections[0][0]:
        return sections[0][1]
    if z >= sections[-1][0]:
        return sections[-1][1]
    for (z0, scale0), (z1, scale1) in zip(sections, sections[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            t = t * t * (3.0 - 2.0 * t)
            return scale0 + (scale1 - scale0) * t
    raise RuntimeError("Unable to interpolate lid scale")


def create_lid_shell():
    outer_sections = tuple(
        (z, superellipse_loop(BODY_WIDTH * scale, BODY_DEPTH * scale))
        for z, scale in LID_DOME_SECTIONS
    )
    lid = loft_solid("Veo_Case_Lid", outer_sections)

    cavity_top_z = BODY_HEIGHT - LID_TOP_THICKNESS
    cavity_z_values = [SEAM_Z - 2.0 * BOOLEAN_OVERLAP]
    cavity_z_values.extend(
        z for z, _ in LID_DOME_SECTIONS[1:-1] if z < cavity_top_z
    )
    cavity_z_values.append(cavity_top_z)
    cavity_sections = []
    for z in cavity_z_values:
        scale = lid_scale_at_z(max(z, LID_DOME_SECTIONS[0][0]))
        cavity_sections.append(
            (
                z,
                superellipse_loop(
                    BODY_WIDTH * scale - 2.0 * LID_WALL_THICKNESS,
                    BODY_DEPTH * scale - 2.0 * LID_WALL_THICKNESS,
                ),
            )
        )
    boolean_difference(lid, [loft_solid("Lid_Cavity", cavity_sections)], "Lid_Cavity")

    add_lid_fastener_columns(lid)
    cut_lid_fastener_holes(lid)
    return lid


def add_lid_fastener_columns(lid):
    if not LID_FASTENERS_ENABLED:
        return lid
    for index, (x, y) in enumerate(LID_FASTENER_POSITIONS_XY, start=1):
        column = add_cylinder_z(
            f"Lid_Fastener_Column_{index}",
            LID_FASTENER_LID_BOSS_DIAMETER / 2.0,
            SEAM_Z + LID_FASTENER_COLUMN_BOTTOM_CLEARANCE,
            BODY_HEIGHT - LID_TOP_THICKNESS + BOOLEAN_OVERLAP * 2.0,
            x,
            y,
        )
        boolean_union(lid, column, f"Lid_Fastener_Column_{index}_Union")
    return lid


def cut_lid_fastener_holes(lid):
    if not LID_FASTENERS_ENABLED:
        return lid
    clearance_cutters = []
    counterbore_cutters = []
    for index, (x, y) in enumerate(LID_FASTENER_POSITIONS_XY, start=1):
        clearance_cutters.append(
            add_cylinder_z(
                f"Lid_Fastener_Clearance_{index}",
                LID_FASTENER_CLEARANCE_DIAMETER / 2.0,
                SEAM_Z - BOOLEAN_OVERLAP,
                BODY_HEIGHT + BOOLEAN_OVERLAP,
                x,
                y,
            )
        )
        counterbore_cutters.append(
            add_cylinder_z(
                f"Lid_Fastener_Counterbore_{index}",
                LID_FASTENER_COUNTERBORE_DIAMETER / 2.0,
                BODY_HEIGHT - LID_FASTENER_COUNTERBORE_DEPTH,
                BODY_HEIGHT + BOOLEAN_OVERLAP * 2.0,
                x,
                y,
            )
        )
    # Keep the intersecting clearance and counterbore stages in separate
    # booleans.  Joining overlapping cutter meshes makes the tool itself
    # self-intersecting and can leave open shoulder edges in Blender.
    boolean_difference(lid, clearance_cutters, "Lid_Fastener_Clearance_Holes")
    boolean_difference(lid, counterbore_cutters, "Lid_Fastener_Counterbores")
    return lid


# ---------------------------------------------------------------------------
# Reference GoPro mockups, materials, layout, render, validation, and export


def assign_material(obj, name: str, color):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.diffuse_color = color
    obj.data.materials.clear()
    obj.data.materials.append(material)


def create_gopro_mockups():
    if not SHOW_GOPRO_MOCKUPS:
        return []
    objects = []
    for name, facing, eye_x, lens_x in camera_specs():
        cx, cy, cz = camera_body_center(facing, eye_x, lens_x)
        body = add_beveled_box(
            f"{name}_GoPro_Mockup",
            (GOPRO_BODY_WIDTH, GOPRO_BODY_DEPTH, GOPRO_BODY_HEIGHT),
            (cx, cy, cz),
            4.0,
        )
        assign_material(body, "GoPro_Mockup_Material", GOPRO_COLOR)
        objects.append(body)
        lens_depth = 4.0
        lens_y = cy + facing * (GOPRO_BODY_DEPTH / 2.0 + lens_depth / 2.0)
        lens = add_beveled_box(
            f"{name}_GoPro_Lens_Mockup",
            (25.0, lens_depth, 25.0),
            (eye_x, lens_y, EYE_CENTER_Z),
            4.0,
        )
        assign_material(lens, "GoPro_Lens_Material", LENS_COLOR)
        objects.append(lens)
    return objects


def transform_objects(objects, translation=(0.0, 0.0, 0.0), rotation=None):
    for obj in objects:
        if rotation is not None:
            obj.rotation_euler.rotate(rotation)
        obj.location += Vector(translation)


def apply_layout(base, lid, mockups):
    if LAYOUT_MODE == "assembled":
        return
    if LAYOUT_MODE == "exploded":
        lid.location.z += EXPLODED_LID_LIFT
        for mockup in mockups:
            mockup.location.z += EXPLODED_CAMERA_LIFT
        return
    # Each part rests on a Z=0 print plane, separated along X.
    offset = BODY_WIDTH / 2.0 + PRINT_BED_GAP / 2.0
    base.location.x -= offset
    lid.location.x += offset
    lid.location.z -= SEAM_Z
    for mockup in mockups:
        mockup.hide_viewport = True
        mockup.hide_render = True


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
    shells = 0
    while remaining:
        shells += 1
        stack = [remaining.pop()]
        while stack:
            face = stack.pop()
            for edge in face.edges:
                for linked in edge.link_faces:
                    if linked in remaining:
                        remaining.remove(linked)
                        stack.append(linked)
    bm.free()
    return shells


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


def export_base_directory() -> Path:
    if EXPORT_DIRECTORY:
        path = Path(EXPORT_DIRECTORY).expanduser().resolve()
    else:
        path = Path(__file__).resolve().parent
    path.mkdir(parents=True, exist_ok=True)
    return path


def export_stl(path: Path, objects) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(filepath=str(path), export_selected_objects=True)
    else:
        bpy.ops.export_mesh.stl(filepath=str(path), use_selection=True)
    print(f"EXPORTED {path}")


def export_single_stl(path: Path, obj) -> None:
    if not NORMALIZE_SEPARATE_STLS:
        export_stl(path, [obj])
        return
    original_location = obj.location.copy()
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    center_x = (min(point.x for point in corners) + max(point.x for point in corners)) / 2.0
    center_y = (min(point.y for point in corners) + max(point.y for point in corners)) / 2.0
    minimum_z = min(point.z for point in corners)
    obj.location += Vector((-center_x, -center_y, -minimum_z))
    export_stl(path, [obj])
    obj.location = original_location


def render_preview(base, lid, mockups):
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
    bpy.ops.object.camera_add(location=(320.0, -390.0, 285.0))
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = max(BODY_WIDTH, BODY_DEPTH) * 1.75
    target = Vector((0.0, 0.0, BODY_HEIGHT * 0.95))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    scene.render.resolution_x = PREVIEW_RESOLUTION_X
    scene.render.resolution_y = PREVIEW_RESOLUTION_Y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    output = Path(PREVIEW_PATH)
    if not output.is_absolute():
        output = Path(__file__).resolve().parent / output
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED {output}")


def build_veo_cam3_case():
    validate_config()
    if CLEAR_SCENE:
        clear_scene()
    set_units()

    base = create_base_shell()
    lid = create_lid_shell()
    base.name = "Veo_Cam3_Enclosure_Base"
    lid.name = "Veo_Cam3_Removable_Lid"
    assign_material(base, "Veo_Base_Material", BASE_COLOR)
    assign_material(lid, "Veo_Lid_Material", LID_COLOR)
    mockups = create_gopro_mockups()

    triangulate_mesh(base)
    triangulate_mesh(lid)
    validate_object(base)
    validate_object(lid)
    apply_layout(base, lid, mockups)

    if EXPORT_STL:
        directory = export_base_directory()
        if EXPORT_SEPARATE_STLS:
            export_single_stl(directory / BASE_STL_NAME, base)
            export_single_stl(directory / LID_STL_NAME, lid)
        if EXPORT_COMBINED_STL:
            export_stl(directory / COMBINED_STL_NAME, [base, lid])
    render_preview(base, lid, mockups)
    return base, lid


if __name__ == "__main__":
    build_veo_cam3_case()
