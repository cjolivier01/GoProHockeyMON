"""Geometric reconstruction of the supplied M1_lens_cap.stl (millimeters).

The reference is measurement-only: no mesh, encoded coordinates, or external
file is read. Print closed face down. The original fitting dimensions are
preserved; the camera dummy's approximate corner radius is not a fit gauge.
"""

import math


STL_NAME = "mission1_lens_cap_tpu_for_ams_print_two.stl"
OUTER_WIDTH = 48.0
OUTER_RADIUS = 13.0
HEIGHT = 11.0
FLOOR = 1.5
SEAT_Z = 3.0
INNER_WIDTH = 42.0
INNER_RADIUS = 10.0
OUTER_DRAFT_DEGREES = 10.0
MOUTH_DRAFT_DEGREES = 15.0
MOUTH_START_Z = 9.0
BOTTOM_CHAMFER = 0.25
FLOOR_FILLET = 0.5
SEAT_INNER_X = 19.25
SEAT_LENGTH = 22.0
RIB_WIDTH = 2.0
RIB_PROJECTION = 0.15
RIB_TOP_Z = 8.45
RIB_FADE_Z = 9.01
SEGMENTS = 32


def outline(width, radius):
    """Include both tangencies of each circular corner."""
    points = []
    for sx, sy, start in ((1, 1, 0), (-1, 1, 90),
                          (-1, -1, 180), (1, -1, 270)):
        for step in range(SEGMENTS + 1):
            angle = math.radians(start + 90 * step / SEGMENTS)
            points.append((sx * (width / 2 - radius) + radius * math.cos(angle),
                           sy * (width / 2 - radius) + radius * math.sin(angle)))
    return points


def loft(g, name, sections):
    vertices = [(x, y, z) for z, width, radius in sections
                for x, y in outline(width, radius)]
    count = len(vertices) // len(sections)
    faces = [tuple(reversed(range(count))),
             tuple(range(len(vertices) - count, len(vertices)))]
    for ring in range(len(sections) - 1):
        for i in range(count):
            a, b = ring * count + i, ring * count + (i + 1) % count
            faces.append((a, b, b + count, a + count))
    return g["create_mesh_object"](name, vertices, faces)


def build(g, name="MISSION1_Lens_Cap_TPU_For_AMS"):
    inset = (HEIGHT - SEAT_Z) * math.tan(math.radians(OUTER_DRAFT_DEGREES))
    cap = loft(g, name, (
        (0.0, OUTER_WIDTH - 2 * BOTTOM_CHAMFER, OUTER_RADIUS - BOTTOM_CHAMFER),
        (BOTTOM_CHAMFER, OUTER_WIDTH, OUTER_RADIUS),
        (SEAT_Z, OUTER_WIDTH, OUTER_RADIUS),
        (HEIGHT, OUTER_WIDTH - 2 * inset, OUTER_RADIUS - inset),
    ))
    sections = []
    for step in range(9):
        angle = math.pi / 2 * step / 8
        inset = FLOOR_FILLET * (1 - math.sin(angle))
        z = FLOOR + FLOOR_FILLET * (1 - math.cos(angle))
        sections.append((z, INNER_WIDTH - 2 * inset, INNER_RADIUS - inset))
    sections.append((MOUTH_START_Z, INNER_WIDTH, INNER_RADIUS))
    flare = (HEIGHT + 0.2 - MOUTH_START_Z) * math.tan(math.radians(MOUTH_DRAFT_DEGREES))
    sections.append((HEIGHT + 0.2, INNER_WIDTH + 2 * flare, INNER_RADIUS + flare))
    g["difference_from"](cap, loft(g, "Lens_Cap_Inner_Cavity", sections))
    for side in (-1, 1):
        # Flat 3 mm seating lands, backed into the wall; the lens face has
        # 1.5 mm of relief over the thin central floor.
        seat = g["add_rounded_prism"]("Lens_Cap_Seating_Land",
            2.5, SEAT_LENGTH, FLOOR - .2, SEAT_Z, .5,
            (side * (SEAT_INNER_X + 1.25), 0.0))
        g["union_into"](cap, seat)
    # Small local contact on the negative-Y inner wall, present in the source
    # cap. Its bottom blends into the cavity floor fillet; its top fades back
    # into the wall at the entry flare.
    wall_y = -INNER_WIDTH / 2
    rib = g["extrude_loop_x"]("Lens_Cap_Internal_Retention_Rib", (
        (wall_y - .2, FLOOR - .2),
        (wall_y + RIB_PROJECTION, FLOOR - .2),
        (wall_y + RIB_PROJECTION, RIB_TOP_Z),
        (wall_y - .02, RIB_FADE_Z),
        (wall_y - .2, RIB_FADE_Z),
    ), -RIB_WIDTH / 2, RIB_WIDTH / 2)
    g["union_into"](cap, rib)
    cap.name = name
    return cap
