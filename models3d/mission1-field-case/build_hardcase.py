#!/usr/bin/env python3
"""
build_hardcase.py
=================

Procedural Blender generator for a Storm-/Pelican-style waterproof hard case.

The proportions, wall thicknesses, seal geometry, hinge axis, latch and handle
positions were reverse-engineered from the STL set that sits next to this file
(Snowmix "Hardcase v2.1", Printables #932697) by slicing the meshes and fitting
the profiles.  Nothing is imported at run time -- every part is generated from
the parameters in ``P`` below, so you can change the size, wall thickness,
corner radius, seal fit, etc. and get a consistent case back.

Usage
-----
    ~/Apps/Blender/blender --python build_hardcase.py
    ~/Apps/Blender/blender --background --python build_hardcase.py -- \
        --scale 0.5 --open 65 --save hardcase.blend

Or paste it into Blender's Text Editor and hit Run.

CLI options (after the ``--`` separator)
    --scale F     uniform scale, 1.0 / 0.75 / 0.5 match the printable variants
    --open D      lid opening angle in degrees (0 = closed)
    --handle D    handle swing angle in degrees (0 = stowed against the front)
    --no-scene    don't touch units / camera / lights
    --save PATH   save a .blend when finished
    --render PATH render a still when finished

Layout
------
Origin is at the centre of the case footprint, Z=0 at the outside of the base.
+Y is the front (latches, handle, pressure-release button), -Y is the hinge.
Units are millimetres (1 Blender unit == 1 mm).

Everything hangs off empties so the assembly stays poseable after generation:

    HardCase                (root, carries the global scale)
    +- Hinge.Axis           rotate X to open the lid
    |    +- Lid, lid knuckles, catch lugs, guard ribs
    +- Handle.Pivot         rotate X to swing the handle out
    |    +- Handle
    +- Latch.Pivot.L/R      rotate X to flip the latches open
    |    +- Latch bodies
    +- Base, seal, feet, button, hardware
"""

from __future__ import annotations

import math
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

# ---------------------------------------------------------------------------
# Parameters -- all dimensions in mm at 100 % scale
# ---------------------------------------------------------------------------

P = {
    # -- global ------------------------------------------------------------
    "scale":            1.00,   # 1.00 / 0.75 / 0.50 -> the printable variants
    "corner_seg":       16,     # arc segments per plan-view corner
    "lid_open_deg":      0.0,
    "handle_deg":        0.0,
    "latch_open_deg":    0.0,

    # -- main body ---------------------------------------------------------
    "body_w":         250.0,    # outer width  (X) of the shell body
    "body_d":         190.0,    # outer depth  (Y) of the shell body
    "corner_r":        25.0,    # plan-view corner radius of the body
    "wall":             4.0,    # nominal side-wall thickness
    "floor_t":          4.5,    # floor / ceiling thickness
    "base_h":          84.0,    # Z of the parting plane (top of the base flange)
    "lid_h":           40.0,    # parting plane -> top of the lid

    # -- soft outer edge (bottom of the base, top of the lid) --------------
    # A CAD-style variable blend; the tables further down hold its shape, these
    # two numbers set how far it reaches.
    "soft_h":          24.0,    # height of the blend
    "soft_w":          16.3,    # inset of the flat face from the side wall

    # -- matching inner blend (floor->wall, ceiling->wall) -----------------
    "soft_h_in":       21.5,
    "soft_w_in":       15.9,    # extra inset on top of `wall`

    # -- bumper flange around the parting line -----------------------------
    "flange_out":      10.0,    # how far it stands proud of the body
    "flange_h":         7.0,    # straight part
    "flange_ramp":      9.0,    # ramp from the body up to the flange

    # -- tongue & groove seal ----------------------------------------------
    "lip_inset":        5.25,   # lip outer face, measured in from the flange edge
    "lip_w":            4.5,    # lip thickness
    "lip_h":            3.0,    # lip height above the parting plane
    "nub_w":            1.5,    # sealing nub on top of the lip
    "nub_h":            1.0,
    "groove_clear":     0.25,   # per-side clearance of the lid groove over the lip
    "groove_depth":     6.3,
    "seal_h":           3.5,    # TPU gasket height

    # -- hinge --------------------------------------------------------------
    "hinge_y":       -112.7,    # hinge axis, Y  (the axis sits *on* the parting plane)
    "hinge_r":          7.0,    # knuckle radius
    "hinge_pin_d":      4.0,
    # knuckles alternate base / lid; mirrored to -X as well
    "hinge_base_x":  ((41.75, 10.0), (66.25, 10.0), (90.73, 10.0)),
    "hinge_lid_x":   ((24.76, 12.48), (52.13, 6.24), (76.63, 6.24)),

    # -- latches ------------------------------------------------------------
    "latch_x":         73.5,    # centre of each latch
    "latch_ear_x":   (58.0, 89.0),   # the two ears it pivots between
    "latch_ear_w":      6.0,
    "latch_w":         23.25,   # latch body width
    "latch_pivot_y":  112.0,
    "latch_pivot_z":   36.0,
    "latch_pin_d":      4.0,
    "lug_w":           24.0,    # catch lug on the lid
    "lug_y0":          99.6,
    "lug_y1":         104.6,
    "lug_h":            7.0,

    # -- handle -------------------------------------------------------------
    "handle_ear_x":    42.0,    # inner ear; the outer one is the latch ear at 58
    "handle_pivot_y": 109.0,
    "handle_pivot_z":  60.0,
    "handle_pin_d":     6.0,
    "handle_arm_x":    50.0,    # arm centre
    "handle_arm_t":     9.0,    # arm thickness along X
    "handle_arm_l":    45.0,    # pivot -> grip centre
    "handle_grip_l":  109.0,    # overall span
    "handle_depth":    23.0,    # section depth, along Y when stowed
    "handle_grip_t":   19.8,    # section thickness, along Z when stowed

    # -- pressure-release button -------------------------------------------
    "btn_z":           54.5,
    "btn_house_w":     45.0,
    "btn_house_h":     27.0,
    "btn_house_out":   10.0,
    "btn_pocket_d":    34.0,
    "btn_cap_d":       30.0,    # scallop root diameter
    "btn_cap_amp":      1.0,    # scallop depth (peak dia = cap_d + 2*amp)
    "btn_lobes":         16,
    "btn_cap_t":        3.0,
    "btn_stem_d":       9.2,
    "btn_bore_d":       4.0,

    # -- side bumper ribs ---------------------------------------------------
    "side_rib_y":      47.0,
    "side_rib_w":       6.0,
    "side_rib_out":     9.1,
    "side_rib_z":   (20.0, 77.0),

    # -- decorative front ribs ---------------------------------------------
    "front_rib_x":     33.75,
    "front_rib_w":     10.5,
    "front_rib_out":    6.0,
    "front_rib_z":  (42.0, 68.0),

    # -- TPU feet ------------------------------------------------------------
    "foot_x":          84.85,
    "foot_y":          55.0,
    "foot_size":       30.0,
    "foot_r":           8.0,
    "foot_t":           4.0,
}

# Shape of the soft outer edge, normalised: t = height/soft_h, s = inset/soft_w.
# Sampled off the reference lid, which uses the same blend as the base bottom.
EDGE_OUT = (
    (0.0000, 1.0000), (0.0417, 0.9387), (0.0833, 0.8589), (0.1250, 0.7822),
    (0.1667, 0.7055), (0.2083, 0.6166), (0.2500, 0.5399), (0.2917, 0.4724),
    (0.3333, 0.4110), (0.4167, 0.3098), (0.5000, 0.2270), (0.5833, 0.1595),
    (0.6667, 0.1043), (0.7500, 0.0613), (0.8333, 0.0307), (0.9167, 0.0123),
    (1.0000, 0.0000),
)

# Matching inner blend: t = height/soft_h_in, s = (inset - wall)/soft_w_in.
EDGE_IN = (
    (0.0000, 1.0000), (0.0233, 0.9201), (0.0698, 0.7616), (0.1628, 0.5478),
    (0.2558, 0.3969), (0.3488, 0.2843), (0.4419, 0.1975), (0.5349, 0.1289),
    (0.6279, 0.0774), (0.7209, 0.0396), (0.8140, 0.0151), (0.9070, 0.0031),
    (1.0000, 0.0000),
)

SMOOTH_ANGLE = math.radians(35.0)


# ---------------------------------------------------------------------------
# Small geometry helpers
# ---------------------------------------------------------------------------

def rounded_rect(hw: float, hd: float, r: float, seg: int):
    """CCW points of a rounded rectangle centred on the origin.

    Offsetting the whole outline by `o` is just (hw-o, hd-o, r-o), which is what
    makes the shell sweep below exact rather than approximate.
    """
    r = max(min(r, hw, hd), 1e-3)
    pts = []
    for cx, cy, a0 in ((hw - r, hd - r, 0.0),
                       (-hw + r, hd - r, math.pi * 0.5),
                       (-hw + r, -hd + r, math.pi),
                       (hw - r, -hd + r, math.pi * 1.5)):
        for k in range(seg + 1):
            a = a0 + math.pi * 0.5 * k / seg
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def circle_pts(r: float, n: int, phase: float = 0.0):
    return [(r * math.cos(phase + 2 * math.pi * i / n),
             r * math.sin(phase + 2 * math.pi * i / n)) for i in range(n)]


def arc_pts(cx: float, cy: float, r: float, a0: float, a1: float, seg: int):
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / seg),
             cy + r * math.sin(a0 + (a1 - a0) * k / seg)) for k in range(seg + 1)]


def dedupe(seq, eps: float = 1e-6):
    out = []
    for p in seq:
        if not out or abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps:
            out.append(p)
    return out


def soft_edge(depth: float, width: float, z_face: float, sign: int, table=EDGE_OUT,
              base_inset: float = 0.0):
    """(inset, z) points of a blend leaving a flat face at `z_face`.

    `sign` is +1 when the material is above the face (base bottom) and -1 when
    it is below it (lid top).
    """
    return [(base_inset + width * s, z_face + sign * depth * t) for t, s in table]


# ---------------------------------------------------------------------------
# bmesh -> object plumbing
# ---------------------------------------------------------------------------

def finish(bm, name: str, coll, mat=None, smooth: bool = True):
    """Clean up a bmesh, turn it into an object and link it."""
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.validate(verbose=False)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if mat is not None:
        ob.data.materials.append(mat)
    if smooth:
        shade_auto_smooth(ob)
    return ob


def shade_auto_smooth(ob):
    for poly in ob.data.polygons:
        poly.use_smooth = True
    # Blender 4.1+ replaced the mesh flag with a modifier-based operator.
    try:
        prev = bpy.context.view_layer.objects.active
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        bpy.ops.object.shade_auto_smooth(angle=SMOOTH_ANGLE)
        ob.select_set(False)
        bpy.context.view_layer.objects.active = prev
    except Exception:
        pass


def sweep_shell(profile, hw, hd, r0, seg, name, coll, mat=None,
                closed: bool = False, cap_first: bool = True, cap_last: bool = True):
    """Sweep a 2D profile given as (inset, z) around a rounded-rect path.

    With `closed` the profile is treated as a loop (used for the gasket);
    otherwise the two open ends are capped with n-gons.
    """
    profile = dedupe(profile)
    bm = bmesh.new()
    rings = []
    for inset, z in profile:
        pts = rounded_rect(hw - inset, hd - inset, r0 - inset, seg)
        rings.append([bm.verts.new((x, y, z)) for x, y in pts])

    n = len(rings[0])
    pairs = list(zip(rings, rings[1:]))
    if closed:
        pairs.append((rings[-1], rings[0]))
    for a, b in pairs:
        for i in range(n):
            j = (i + 1) % n
            try:
                bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError:
                pass  # degenerate slice, skip
    if not closed:
        if cap_first:
            bm.faces.new(list(reversed(rings[0])))
        if cap_last:
            bm.faces.new(rings[-1])
    return finish(bm, name, coll, mat)


_AXIS_MAP = {"X": (1, 2, 0), "Y": (0, 2, 1), "Z": (0, 1, 2)}


def extrude_profile(pts2d, axis: str, a0: float, a1: float, name: str, coll,
                    mat=None, bevel: float = 0.0, bevel_seg: int = 2,
                    smooth: bool = True):
    """Extrude a closed CCW polygon along one of the world axes.

    `pts2d` is in the plane perpendicular to `axis`: (Y,Z) for X, (X,Z) for Y,
    (X,Y) for Z.
    """
    i0, i1, ia = _AXIS_MAP[axis]
    pts2d = dedupe(pts2d)
    bm = bmesh.new()
    rings = []
    for a in (a0, a1):
        ring = []
        for p in pts2d:
            co = [0.0, 0.0, 0.0]
            co[i0], co[i1], co[ia] = p[0], p[1], a
            ring.append(bm.verts.new(co))
        rings.append(ring)
    n = len(pts2d)
    for i in range(n):
        j = (i + 1) % n
        try:
            bm.faces.new((rings[0][i], rings[0][j], rings[1][j], rings[1][i]))
        except ValueError:
            pass
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel > 0.0:
        try:
            bmesh.ops.bevel(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
                            offset=bevel, segments=bevel_seg, profile=0.5,
                            affect="EDGES", clamp_overlap=True)
        except Exception:
            pass
    return finish(bm, name, coll, mat, smooth)


def cylinder(radius: float, length: float, axis: str, centre, name: str, coll,
             mat=None, seg: int = 32, smooth: bool = True):
    bm = bmesh.new()
    rot = {"X": Matrix.Rotation(math.pi / 2, 4, "Y"),
           "Y": Matrix.Rotation(math.pi / 2, 4, "X"),
           "Z": Matrix.Identity(4)}[axis]
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                          radius1=radius, radius2=radius, depth=length,
                          matrix=Matrix.Translation(Vector(centre)) @ rot)
    return finish(bm, name, coll, mat, smooth)


def bridge_tube(loop_a, loop_b, level_a: float, level_b: float, axis: str,
                name: str, coll, mat=None, smooth: bool = True):
    """Build a closed 'plate with a hole' solid from two concentric loops.

    Both loops must have the same vertex count; they are bridged at each end so
    the result is a watertight tube (used for the button housing).
    """
    assert len(loop_a) == len(loop_b)
    i0, i1, ia = _AXIS_MAP[axis]

    def place(p, a):
        co = [0.0, 0.0, 0.0]
        co[i0], co[i1], co[ia] = p[0], p[1], a
        return co

    bm = bmesh.new()
    outer = [[bm.verts.new(place(p, lv)) for p in loop_a] for lv in (level_a, level_b)]
    inner = [[bm.verts.new(place(p, lv)) for p in loop_b] for lv in (level_a, level_b)]
    n = len(loop_a)
    for i in range(n):
        j = (i + 1) % n
        for ring in (outer, inner):                      # outer skin, pocket wall
            try:
                bm.faces.new((ring[0][i], ring[0][j], ring[1][j], ring[1][i]))
            except ValueError:
                pass
        for k in (0, 1):                                 # the two annular faces
            try:
                bm.faces.new((outer[k][i], outer[k][j], inner[k][j], inner[k][i]))
            except ValueError:
                pass
    return finish(bm, name, coll, mat, smooth)


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

def make_material(name, colour, roughness=0.5, metallic=0.0):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    if mat.node_tree is None:                     # `use_nodes` is going away in 6.0
        mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*colour, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
    mat.diffuse_color = (*colour, 1.0)
    return mat


def build_materials():
    return {
        "abs":    make_material("ABS.Black", (0.032, 0.032, 0.035), 0.55),
        "abs2":   make_material("ABS.Black.Satin", (0.048, 0.048, 0.052), 0.38),
        "tpu":    make_material("TPU.Dark", (0.022, 0.022, 0.025), 0.85),
        "red":    make_material("ABS.Red", (0.65, 0.055, 0.045), 0.42),
        "steel":  make_material("Steel.Stainless", (0.62, 0.63, 0.65), 0.28, 1.0),
    }


# ---------------------------------------------------------------------------
# Shell profiles
# ---------------------------------------------------------------------------

def _seal_insets():
    """Insets (measured in from the nominal body face) of the tongue & groove."""
    lip_o = -P["flange_out"] + P["lip_inset"]
    lip_i = lip_o + P["lip_w"]
    nub_o = lip_o + (P["lip_w"] - P["nub_w"]) * 0.5
    nub_i = nub_o + P["nub_w"]
    grv_o = lip_o - P["groove_clear"]
    grv_i = lip_i + P["groove_clear"]
    return lip_o, lip_i, nub_o, nub_i, grv_o, grv_i


def base_profile():
    """(inset, z) section of the base shell, outside face first."""
    bh, fo, fh, fr = P["base_h"], P["flange_out"], P["flange_h"], P["flange_ramp"]
    lip_o, lip_i, nub_o, nub_i, _, _ = _seal_insets()
    z_lip = bh + P["lip_h"]
    z_nub = z_lip + P["nub_h"]

    prof = list(soft_edge(P["soft_h"], P["soft_w"], 0.0, +1))
    prof += [(0.0, bh - fr - fh),                       # up the side wall
             (-fo, bh - fh),                            # flange ramp
             (-fo, bh),                                 # flange, parting plane
             (lip_o, bh),                               # rim, outboard of the lip
             (lip_o, z_lip), (nub_o, z_lip),            # sealing lip + nub
             (nub_o, z_nub), (nub_i, z_nub),
             (nub_i, z_lip), (lip_i, z_lip),
             (lip_i, bh),                               # rim, inboard of the lip
             (P["wall"], bh),                           # inner wall
             (P["wall"], P["floor_t"] + P["soft_h_in"])]
    prof += list(reversed(soft_edge(P["soft_h_in"], P["soft_w_in"], P["floor_t"],
                                    +1, EDGE_IN, P["wall"])))
    return prof


def lid_profile():
    """(inset, z) section of the lid shell, outside face first."""
    bh, fo, fh, fr = P["base_h"], P["flange_out"], P["flange_h"], P["flange_ramp"]
    top = bh + P["lid_h"]
    _, _, _, _, grv_o, grv_i = _seal_insets()
    z_grv = bh + P["groove_depth"]

    prof = list(soft_edge(P["soft_h"], P["soft_w"], top, -1))
    prof += [(0.0, bh + fh + fr),
             (-fo, bh + fh),
             (-fo, bh),                                 # rim face, on the parting plane
             (grv_o, bh), (grv_o, z_grv),               # seal groove
             (grv_i, z_grv), (grv_i, bh),
             (P["wall"], bh),
             (P["wall"], top - P["floor_t"] - P["soft_h_in"])]
    prof += list(reversed(soft_edge(P["soft_h_in"], P["soft_w_in"],
                                    top - P["floor_t"], -1, EDGE_IN, P["wall"])))
    return prof


def seal_profile():
    """Closed (inset, z) section of the TPU gasket."""
    lip_o, lip_i, nub_o, nub_i, _, _ = _seal_insets()
    z0 = P["base_h"] + P["lip_h"]           # rests on the shoulder of the lip
    z1 = z0 + P["seal_h"]
    z_slot = z0 + P["nub_h"]                # slot that swallows the sealing nub
    return [(lip_o, z0), (lip_o, z1), (lip_i, z1), (lip_i, z0),
            (nub_i, z0), (nub_i, z_slot), (nub_o, z_slot), (nub_o, z0)]


# ---------------------------------------------------------------------------
# Part builders
# ---------------------------------------------------------------------------

def build_base(coll, mats):
    hw, hd = P["body_w"] * 0.5, P["body_d"] * 0.5
    return sweep_shell(base_profile(), hw, hd, P["corner_r"], P["corner_seg"],
                       "Case.Base", coll, mats["abs"])


def build_lid(coll, mats):
    hw, hd = P["body_w"] * 0.5, P["body_d"] * 0.5
    return sweep_shell(lid_profile(), hw, hd, P["corner_r"], P["corner_seg"],
                       "Case.Lid", coll, mats["abs"])


def build_seal(coll, mats):
    hw, hd = P["body_w"] * 0.5, P["body_d"] * 0.5
    return sweep_shell(seal_profile(), hw, hd, P["corner_r"], P["corner_seg"],
                       "Seal.TPU", coll, mats["tpu"], closed=True)


def build_hinge(coll_base, coll_lid, mats):
    """Interleaved knuckles on the parting plane plus the two 4 mm pins."""
    hy, hz, r = P["hinge_y"], P["base_h"], P["hinge_r"]
    hd = P["body_d"] * 0.5
    wall_y = -hd                                  # outer face of the back wall
    z_fl = P["base_h"] - P["flange_h"]
    seg = 16
    out = []

    def knuckle(xc, w, upper, name, coll):
        # Three quarters of a barrel centred on the hinge axis, closed off by a
        # tail that runs back into the flange of whichever half it belongs to.
        # The axis sits exactly on the parting plane, so base and lid knuckles
        # are identical apart from which way the tail points.
        s = 1 if upper else -1
        prof = arc_pts(hy, hz, r, 0.0, s * 1.5 * math.pi, seg * 3 // 2)
        prof += [(wall_y, hz - s * r), (wall_y, hz)]
        if not upper:
            prof = list(reversed(prof))
        return extrude_profile(prof, "X", xc - w * 0.5, xc + w * 0.5,
                               name, coll, mats["abs"], bevel=0.3)

    for sx in (-1, 1):
        for i, (xc, w) in enumerate(P["hinge_base_x"]):
            out.append(knuckle(sx * xc, w, True, f"Hinge.Base.{'LR'[sx > 0]}{i}", coll_base))
        for i, (xc, w) in enumerate(P["hinge_lid_x"]):
            out.append(knuckle(sx * xc, w, False, f"Hinge.Lid.{'LR'[sx > 0]}{i}", coll_lid))

        xs = [x for x, _ in P["hinge_base_x"]] + [x for x, _ in P["hinge_lid_x"]]
        ws = [w for _, w in P["hinge_base_x"]] + [w for _, w in P["hinge_lid_x"]]
        lo = min(x - w * 0.5 for x, w in zip(xs, ws)) - 3.0
        hi = max(x + w * 0.5 for x, w in zip(xs, ws)) + 3.0
        out.append(cylinder(P["hinge_pin_d"] * 0.5, hi - lo, "X",
                            (sx * (lo + hi) * 0.5, hy, hz),
                            f"Hinge.Pin.{'LR'[sx > 0]}", coll_base, mats["steel"]))

    # gussets carrying the knuckles down the back wall
    tip = hy + r - 13.17          # 118.87 from centre on the reference part
    for sx in (-1, 1):
        for i, (xc, w) in enumerate(P["hinge_base_x"]):
            prof = [(wall_y, 20.0), (wall_y - 6.0, 26.0), (tip, z_fl - 6.0),
                    (tip, z_fl), (wall_y, z_fl)]
            out.append(extrude_profile(prof, "X", sx * xc - w * 0.5, sx * xc + w * 0.5,
                                       f"Hinge.Gusset.{'LR'[sx > 0]}{i}", coll_base,
                                       mats["abs"], bevel=0.8))
    return out


def _ear_profile(y_wall, y_tip, z0, z1, z_ramp):
    """Side view of a rib that ramps out of the case wall and runs up to z1."""
    return [(y_wall, z0), (y_wall + 11.0, z0), (y_tip, z_ramp), (y_tip, z1),
            (y_wall, z1)]


def build_latches(coll_base, coll_lid, pivots, mats):
    hd = P["body_d"] * 0.5
    y_tip = 120.5
    out = []

    # --- ears on the base -------------------------------------------------
    for sx in (-1, 1):
        for i, xc in enumerate(P["latch_ear_x"]):
            prof = _ear_profile(hd, y_tip, 26.0, P["base_h"], 40.0)
            w = P["latch_ear_w"]
            out.append(extrude_profile(prof, "X", sx * xc - w * 0.5, sx * xc + w * 0.5,
                                       f"Latch.Ear.{'LR'[sx > 0]}{i}", coll_base,
                                       mats["abs"], bevel=1.2))

    # --- matching guard ribs + catch lugs on the lid ----------------------
    for sx in (-1, 1):
        for i, xc in enumerate(P["latch_ear_x"]):
            prof = [(hd, P["base_h"]), (y_tip, P["base_h"]),
                    (y_tip, P["base_h"] + P["flange_h"]),
                    (hd, P["base_h"] + P["flange_h"] + 3.0)]
            w = P["latch_ear_w"]
            out.append(extrude_profile(prof, "X", sx * xc - w * 0.5, sx * xc + w * 0.5,
                                       f"Latch.Guard.{'LR'[sx > 0]}{i}", coll_lid,
                                       mats["abs"], bevel=1.0))
        lug = [(P["lug_y0"], P["base_h"]), (P["lug_y1"], P["base_h"]),
               (P["lug_y1"], P["base_h"] + P["lug_h"] - 1.5),
               (P["lug_y1"] - 1.5, P["base_h"] + P["lug_h"]),
               (P["lug_y0"], P["base_h"] + P["lug_h"])]
        w = P["lug_w"]
        out.append(extrude_profile(lug, "X", sx * P["latch_x"] - w * 0.5,
                                   sx * P["latch_x"] + w * 0.5,
                                   f"Latch.Lug.{'LR'[sx > 0]}", coll_lid,
                                   mats["abs"], bevel=0.6))

    # --- latch body: over-centre lever with a hook on top -----------------
    py, pz = P["latch_pivot_y"], P["latch_pivot_z"]
    for sx in (-1, 1):
        key = "LR"[sx > 0]
        piv = pivots[f"latch_{key}"]
        # Profile in the YZ plane, in the pivot's local frame: an over-centre
        # lever with a short tail below the pin and a hook on top that closes
        # down onto the lid lug.  Local Z 55 is the top face of that lug.
        body = [(-6.0, -10.0),                       # tail, inner corner
                (4.0, -9.0), (7.5, -2.0),            # tail, outer corner
                (8.0, 14.0), (7.0, 34.0),            # belly of the outer face
                (5.0, 50.0), (3.5, 58.0),
                (-1.0, 62.0),                        # top, outer round
                (-13.0, 62.0), (-13.0, 55.0),        # nose drops past the lug
                (-4.5, 55.0),                        # hook bears on the lug top
                (-4.5, 48.0), (-6.0, 44.0),          # inner face, clears the flanges
                (-6.0, 20.0), (-4.0, 0.0)]
        w = P["latch_w"]
        ob = extrude_profile([(y + py, z + pz) for y, z in body], "X",
                             sx * P["latch_x"] - w * 0.5, sx * P["latch_x"] + w * 0.5,
                             f"Latch.Body.{key}", coll_base, mats["abs2"], bevel=1.4)
        parent_keep(ob, piv)
        out.append(ob)
        out.append(cylinder(P["latch_pin_d"] * 0.5, 41.0, "X",
                            (sx * P["latch_x"], py, pz),
                            f"Latch.Pin.{key}", coll_base, mats["steel"]))
    return out


def build_handle(coll, pivot, mats):
    hd = P["body_d"] * 0.5
    y_tip = 120.5
    out = []

    # inner mounting ears (the outer pair is shared with the latch ears)
    for sx in (-1, 1):
        prof = _ear_profile(hd, y_tip, 28.0, 76.0, 53.0)
        w = P["latch_ear_w"]
        xc = sx * P["handle_ear_x"]
        out.append(extrude_profile(prof, "X", xc - w * 0.5, xc + w * 0.5,
                                   f"Handle.Ear.{'LR'[sx > 0]}", coll, mats["abs"],
                                   bevel=1.2))

    # arms + grip, modelled in the pivot's local frame (hanging straight down)
    half_d = P["handle_depth"] * 0.5
    arm_l = P["handle_arm_l"]
    arm = arc_pts(0.0, 0.0, half_d, math.radians(0), math.radians(180), 12)
    arm += [(-half_d, -arm_l), (half_d, -arm_l)]
    for sx in (-1, 1):
        xc = sx * P["handle_arm_x"]
        t = P["handle_arm_t"]
        ob = extrude_profile(arm, "X", xc - t * 0.5, xc + t * 0.5,
                             f"Handle.Arm.{'LR'[sx > 0]}", coll, mats["abs2"], bevel=1.2)
        parent_local(ob, pivot)
        out.append(ob)

    grip = rounded_rect(half_d, P["handle_grip_t"] * 0.5, 7.5, 8)
    grip = [(y, z - arm_l) for y, z in grip]
    ob = extrude_profile(grip, "X", -P["handle_grip_l"] * 0.5, P["handle_grip_l"] * 0.5,
                         "Handle.Grip", coll, mats["abs2"], bevel=1.5)
    parent_local(ob, pivot)
    out.append(ob)

    for sx in (-1, 1):
        out.append(cylinder(P["handle_pin_d"] * 0.5, 22.0, "X",
                            (sx * P["handle_arm_x"], P["handle_pivot_y"],
                             P["handle_pivot_z"]),
                            f"Handle.Pin.{'LR'[sx > 0]}", coll, mats["steel"]))
    return out


def build_button(coll, mats):
    hd = P["body_d"] * 0.5
    z = P["btn_z"]
    y0, y1 = hd, hd + P["btn_house_out"]
    seg = P["corner_seg"]
    n = 4 * (seg + 1)

    outer = rounded_rect(P["btn_house_w"] * 0.5, P["btn_house_h"] * 0.5, 6.0, seg)
    outer = [(x, y + z) for x, y in outer]
    pocket = circle_pts(P["btn_pocket_d"] * 0.5, n, math.pi * 0.25)
    pocket = [(x, y + z) for x, y in pocket]
    house = bridge_tube(outer, pocket, y0, y1, "Y", "Button.Housing", coll, mats["abs"])

    # scalloped knurl cap
    lobes, r0, amp = P["btn_lobes"], P["btn_cap_d"] * 0.5, P["btn_cap_amp"]
    cap = []
    for i in range(lobes * 6):
        a = 2 * math.pi * i / (lobes * 6)
        rr = r0 + amp * math.cos(lobes * a)
        cap.append((rr * math.cos(a), z + rr * math.sin(a)))
    cap_ob = extrude_profile(cap, "Y", y1 - P["btn_cap_t"], y1 + 1.0,
                             "Button.Cap", coll, mats["abs2"], bevel=0.5)
    stem = cylinder(P["btn_stem_d"] * 0.5, P["btn_house_out"] + 2.0, "Y",
                    (0.0, hd + P["btn_house_out"] * 0.5 - 1.0, z),
                    "Button.Stem", coll, mats["abs2"])
    bolt = cylinder(P["btn_bore_d"] * 0.6, 4.0, "Y", (0.0, y1 + 1.2, z),
                    "Button.Bolt", coll, mats["steel"], seg=6)
    return [house, cap_ob, stem, bolt]


def build_ribs(coll, mats):
    """Side bumper ribs and the decorative ribs either side of the button."""
    hw, hd = P["body_w"] * 0.5, P["body_d"] * 0.5
    out = []

    z0, z1 = P["side_rib_z"]
    for sx in (-1, 1):
        for sy in (-1, 1):
            yc = sy * P["side_rib_y"]
            w = P["side_rib_w"]
            prof = [(sx * (hw - 2.0), z0), (sx * (hw + P["side_rib_out"]), z0 + 6.0),
                    (sx * (hw + P["side_rib_out"]), z1 - 6.0), (sx * (hw - 2.0), z1)]
            if sx < 0:
                prof = list(reversed(prof))
            out.append(extrude_profile(prof, "Y", yc - w * 0.5, yc + w * 0.5,
                                       f"Rib.Side.{'LR'[sx > 0]}{'BF'[sy > 0]}",
                                       coll, mats["abs"], bevel=1.0))

    z0, z1 = P["front_rib_z"]
    for sx in (-1, 1):
        xc = sx * P["front_rib_x"]
        w = P["front_rib_w"]
        prof = [(hd - 2.0, z0), (hd + P["front_rib_out"], z0 + 4.0),
                (hd + P["front_rib_out"], z1 - 4.0), (hd - 2.0, z1)]
        out.append(extrude_profile(prof, "X", xc - w * 0.5, xc + w * 0.5,
                                   f"Rib.Front.{'LR'[sx > 0]}", coll, mats["abs"],
                                   bevel=1.0))
    return out


def build_feet(coll, mats):
    out = []
    pad = rounded_rect(P["foot_size"] * 0.5, P["foot_size"] * 0.5, P["foot_r"], 8)
    for sx in (-1, 1):
        for sy in (-1, 1):
            pts = [(x + sx * P["foot_x"], y + sy * P["foot_y"]) for x, y in pad]
            out.append(extrude_profile(pts, "Z", -P["foot_t"], 0.2,
                                       f"Foot.{'LR'[sx > 0]}{'BF'[sy > 0]}",
                                       coll, mats["tpu"], bevel=1.0))
    return out


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def parent_keep(child, parent):
    """Parent a child that was built in world space, without moving it."""
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


def parent_local(child, parent):
    """Parent a child whose geometry is already in the parent's local frame."""
    child.parent = parent
    child.matrix_parent_inverse = Matrix.Identity(4)


def new_collection(name, parent):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
    if coll.name not in {c.name for c in parent.children}:
        parent.children.link(coll)
    return coll


def new_empty(name, location, coll, size=20.0):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = "PLAIN_AXES"
    ob.empty_display_size = size
    ob.location = location
    coll.objects.link(ob)
    return ob


def clear_previous():
    """Remove a previous run plus Blender's default startup objects."""
    doomed = []
    old = bpy.data.collections.get("HardCase")
    if old:
        def walk(c):
            doomed.extend(c.objects)
            for ch in c.children:
                walk(ch)
        walk(old)
    for name in ("Cube", "Camera", "Light"):
        ob = bpy.data.objects.get(name)
        if ob:
            doomed.append(ob)
    for ob in set(doomed):
        bpy.data.objects.remove(ob, do_unlink=True)
    if old:
        def purge(c):
            for ch in list(c.children):
                purge(ch)
            bpy.data.collections.remove(c)
        purge(old)


VIEWS = {
    "iso":   (520.0, 620.0, 400.0),     # front / right / above -- the hero angle
    "front": (0.0, 900.0, 180.0),
    "back":  (-420.0, -640.0, 380.0),   # shows the hinge
    "right": (900.0, 0.0, 180.0),
    "top":   (1.0, 1.0, 900.0),
}


def setup_scene(view: str = "iso"):
    scn = bpy.context.scene
    scn.unit_settings.system = "METRIC"
    scn.unit_settings.scale_length = 0.001
    scn.unit_settings.length_unit = "MILLIMETERS"

    # An open lid is a lot taller than a closed one, so back the camera off and
    # raise the aim point in proportion.
    lift = math.sin(math.radians(min(max(P["lid_open_deg"], 0.0), 120.0)))
    dist = (1.0 + 0.55 * lift) * P["scale"]

    aim = bpy.data.objects.get("HardCase.Aim")
    if aim is None:
        aim = bpy.data.objects.new("HardCase.Aim", None)
        aim.empty_display_type = "SPHERE"
        aim.empty_display_size = 10.0
        scn.collection.objects.link(aim)
    aim.location = (0.0, 0.0, (62.0 + 85.0 * lift) * P["scale"])

    def track(ob, target=aim):
        con = ob.constraints.get("Track To") or ob.constraints.new("TRACK_TO")
        con.target = target
        con.track_axis = "TRACK_NEGATIVE_Z"
        con.up_axis = "UP_Y"

    cam = bpy.data.objects.get("HardCase.Camera")
    if cam is None:
        cam_data = bpy.data.cameras.new("HardCase.Camera")
        cam_data.lens = 80.0
        cam_data.clip_start = 1.0
        cam_data.clip_end = 20000.0
        cam = bpy.data.objects.new("HardCase.Camera", cam_data)
        scn.collection.objects.link(cam)
    cam.location = tuple(c * dist for c in VIEWS.get(view, VIEWS["iso"]))
    track(cam)
    scn.camera = cam

    # Light power is in watts against raw Blender units, and 1 unit is 1 mm
    # here, so the numbers have to be ~1e6 bigger than a metre-scale scene.
    lights = (("Key", (620, 520, 780), 1.1e7, 420.0),
              ("Fill", (-780, 420, 260), 3.2e6, 600.0),
              ("Rim", (-180, -820, 620), 6.0e6, 420.0))
    for name, loc, power, size in lights:
        key = f"HardCase.{name}"
        ob = bpy.data.objects.get(key)
        if ob is None:
            ld = bpy.data.lights.new(key, "AREA")
            ld.size = size
            ob = bpy.data.objects.new(key, ld)
            scn.collection.objects.link(ob)
        ob.location = tuple(c * dist for c in loc)
        ob.data.energy = power * dist * dist        # keep exposure constant
        track(ob)

    world = scn.world or bpy.data.worlds.new("World")
    scn.world = world
    if world.node_tree is None:
        world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.035, 0.038, 0.045, 1.0)
        bg.inputs[1].default_value = 1.0
    try:
        scn.view_settings.view_transform = "AgX"
        scn.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass


def build(scene_setup=True, view="iso"):
    clear_previous()
    mats = build_materials()

    root_coll = new_collection("HardCase", bpy.context.scene.collection)
    c_base = new_collection("HardCase.Base", root_coll)
    c_lid = new_collection("HardCase.Lid", root_coll)
    c_soft = new_collection("HardCase.Soft", root_coll)
    c_hw = new_collection("HardCase.Hardware", root_coll)

    root = new_empty("HardCase", (0.0, 0.0, 0.0), root_coll, 60.0)
    hinge = new_empty("Hinge.Axis", (0.0, P["hinge_y"], P["base_h"]), root_coll, 30.0)
    hpiv = new_empty("Handle.Pivot", (0.0, P["handle_pivot_y"], P["handle_pivot_z"]),
                     root_coll, 18.0)
    pivots = {"hinge": hinge, "handle": hpiv}
    for sx in (-1, 1):
        key = "LR"[sx > 0]
        pivots[f"latch_{key}"] = new_empty(
            f"Latch.Pivot.{key}",
            (sx * P["latch_x"], P["latch_pivot_y"], P["latch_pivot_z"]), root_coll, 14.0)

    base_parts = [build_base(c_base, mats)]
    lid_parts = [build_lid(c_lid, mats)]
    soft_parts = [build_seal(c_soft, mats)] + build_feet(c_soft, mats)

    hinge_parts = build_hinge(c_base, c_lid, mats)
    latch_parts = build_latches(c_base, c_lid, pivots, mats)
    handle_parts = build_handle(c_hw, hpiv, mats)
    button_parts = build_button(c_hw, mats)
    rib_parts = build_ribs(c_base, mats)

    # --- parenting --------------------------------------------------------
    lid_names = {"Case.Lid"}
    for ob in hinge_parts + latch_parts:
        if ob.name.startswith(("Hinge.Lid", "Latch.Guard", "Latch.Lug")):
            lid_names.add(ob.name)

    everything = (base_parts + lid_parts + soft_parts + hinge_parts +
                  latch_parts + handle_parts + button_parts + rib_parts)
    for ob in everything:
        if ob.parent is not None:          # already on a latch / handle pivot
            continue
        parent_keep(ob, hinge if ob.name in lid_names else root)
    for piv in (hinge, hpiv):
        parent_keep(piv, root)
    for sx in (-1, 1):
        parent_keep(pivots[f"latch_{'LR'[sx > 0]}"], root)

    # --- pose + global scale ---------------------------------------------
    hinge.rotation_euler = (math.radians(P["lid_open_deg"]), 0.0, 0.0)
    hpiv.rotation_euler = (math.radians(P["handle_deg"]), 0.0, 0.0)
    for sx in (-1, 1):
        pivots[f"latch_{'LR'[sx > 0]}"].rotation_euler = (
            math.radians(-P["latch_open_deg"]), 0.0, 0.0)
    root.scale = (P["scale"],) * 3

    if scene_setup:
        setup_scene(view)

    return root, everything


def report(objects):
    bpy.context.view_layer.update()      # parent transforms are lazy
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    faces = 0
    for ob in objects:
        faces += len(ob.data.polygons)
        for corner in ob.bound_box:
            w = ob.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    size = hi - lo
    print("-" * 62)
    print(f"  parts        : {len(objects)} ({faces} faces)")
    print(f"  bounding box : {size.x:.1f} x {size.y:.1f} x {size.z:.1f} mm")
    print(f"  wall / floor : {P['wall']:.1f} / {P['floor_t']:.1f} mm")
    print(f"  scale        : {P['scale'] * 100:.0f} %")
    print("-" * 62)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args(argv):
    opts = {"scene": True, "save": None, "render": None, "view": "iso", "clay": False}
    keys = {"--scale": "scale", "--open": "lid_open_deg", "--handle": "handle_deg",
            "--latch": "latch_open_deg"}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in keys:
            i += 1
            P[keys[a]] = float(argv[i])
        elif a == "--no-scene":
            opts["scene"] = False
        elif a == "--clay":
            opts["clay"] = True
        elif a in ("--save", "--render", "--view"):
            i += 1
            opts[a[2:]] = argv[i]
        i += 1
    return opts


def clay_shading():
    """Flat grey on everything -- makes the geometry legible when checking it."""
    grey = make_material("Clay", (0.52, 0.52, 0.53), 0.45)
    for ob in bpy.data.objects:
        if ob.type == "MESH":
            ob.data.materials.clear()
            ob.data.materials.append(grey)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts = parse_args(argv)

    _, objects = build(opts["scene"], opts["view"])
    if opts["clay"]:
        clay_shading()
    report(objects)

    if opts["render"]:
        scn = bpy.context.scene
        scn.render.filepath = opts["render"]
        scn.render.resolution_x, scn.render.resolution_y = 1600, 1100
        scn.render.image_settings.file_format = "PNG"
        if scn.render.engine == "CYCLES":
            scn.cycles.samples = 96
        bpy.ops.render.render(write_still=True)
        print(f"rendered -> {opts['render']}")
    if opts["save"]:
        bpy.ops.wm.save_as_mainfile(filepath=bpy.path.abspath(opts["save"]))
        print(f"saved -> {opts['save']}")


if __name__ == "__main__":
    main()
