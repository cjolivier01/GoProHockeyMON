#!/usr/bin/env python3
"""Generate CAD-style configuration drawings for the Hockeymom dual-camera cover.

The script reads scalar defaults from ``hockeymom_3_cam_cover_original_style_blender.py``
without importing Blender, so the labels track the current generator.  The
drawings are explanatory, not manufacturing drawings; geometry is schematic
and explicitly marked NTS (not to scale).

Run with a Python that has matplotlib, for example::

    /home/colivier/miniforge3/bin/python generate_hockeymom_config_dimension_pdf.py
"""

from __future__ import annotations

import ast
import hashlib
import math
import warnings
from datetime import datetime, timezone
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Arc, Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle, Wedge


# Preserve the invocation path instead of resolving a workspace symlink.  This
# keeps the generated PDF beside the script name the user actually ran (for
# example, in the Blender project directory) while still reading the colocated
# current generator through that same workspace view.
HERE = Path(__file__).absolute().parent
MODEL_SOURCE = HERE / "hockeymom_3_cam_cover_original_style_blender.py"
CAMERA_SOURCE = HERE / "gopro_mission1_dummy_blender.py"
OUTPUT_PDF = HERE / "hockeymom_3_cam_cover_configuration_dimensions.pdf"
TOTAL_SHEETS = 15

# Matplotlib warns when an equal-aspect schematic asks it to preserve both a
# fixed view window and a fixed panel rectangle.  It safely expands the view;
# suppress the otherwise noisy, repeated diagnostic during batch generation.
warnings.filterwarnings("ignore", message="Ignoring fixed .* limits.*")

INK = "#152536"
BLUE = "#1668a8"
CYAN = "#2f91b8"
ORANGE = "#db6b28"
GREEN = "#39865b"
RED = "#b34848"
PURPLE = "#7657a8"
GRAY = "#607181"
LIGHT = "#eef3f6"
GRID = "#dce5ea"
WHITE = "#ffffff"


def _safe_value(node: ast.AST, env: dict[str, object]):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return env[node.id]
    if isinstance(node, ast.Tuple):
        return tuple(_safe_value(item, env) for item in node.elts)
    if isinstance(node, ast.List):
        return [_safe_value(item, env) for item in node.elts]
    if isinstance(node, ast.UnaryOp):
        value = _safe_value(node.operand, env)
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.UAdd):
            return +value
    if isinstance(node, ast.BinOp):
        left = _safe_value(node.left, env)
        right = _safe_value(node.right, env)
        operators = {
            ast.Add: lambda a, b: a + b,
            ast.Sub: lambda a, b: a - b,
            ast.Mult: lambda a, b: a * b,
            ast.Div: lambda a, b: a / b,
        }
        for operator_type, operation in operators.items():
            if isinstance(node.op, operator_type):
                return operation(left, right)
    raise ValueError


def read_assignments(path: Path) -> dict[str, object]:
    """Read literal/arithmetic top-level assignments without executing a file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: dict[str, object] = {}
    for statement in tree.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            result[target.id] = _safe_value(statement.value, result)
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
    return result


C = read_assignments(MODEL_SOURCE)
M = read_assignments(CAMERA_SOURCE)


def val(name: str, fallback):
    return C.get(name, fallback)


def cam(name: str, fallback):
    return M.get(name, fallback)


def num(value, decimals=1):
    if isinstance(value, int):
        return str(value)
    return f"{float(value):.{decimals}f}"


def mm(name: str, fallback, decimals=1):
    return f"{num(val(name, fallback), decimals)} mm"


def deg(name: str, fallback, decimals=1):
    return f"{num(val(name, fallback), decimals)} deg"


def direct_purchased_wheel_drive() -> bool:
    return val(
        "CAMERA_IDLER_SECTOR_DRIVE_STYLE",
        "purchased_wheel_direct",
    ) == "purchased_wheel_direct"


def idler_sector_mesh_clearance() -> float:
    name = (
        "CAMERA_IDLER_DIRECT_SECTOR_MESH_CENTER_CLEARANCE"
        if direct_purchased_wheel_drive()
        else "CAMERA_IDLER_SECTOR_MESH_CENTER_CLEARANCE"
    )
    return float(val(name, 0.52 if direct_purchased_wheel_drive() else 0.30))


SOURCE_HASH = hashlib.sha256(MODEL_SOURCE.read_bytes()).hexdigest()[:12]
GENERATED = datetime.now(timezone.utc).strftime("%Y-%m-%d")


mpl.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 8.2,
        "axes.edgecolor": INK,
        "text.color": INK,
        "pdf.fonttype": 42,
        "savefig.facecolor": WHITE,
    }
)
mpl.set_loglevel("error")


def new_sheet(number: int, title: str, subtitle: str = ""):
    fig = plt.figure(figsize=(11, 8.5), facecolor=WHITE)
    fig.subplots_adjust(0, 0, 1, 1)
    fig.text(0.055, 0.947, title, fontsize=18, weight="bold", color=INK)
    if subtitle:
        fig.text(0.055, 0.918, subtitle, fontsize=8.8, color=GRAY)
    fig.add_artist(plt.Line2D([0.055, 0.945], [0.902, 0.902], color=BLUE, lw=2.0))
    fig.add_artist(Rectangle((0.045, 0.035), 0.91, 0.93, transform=fig.transFigure,
                             fill=False, edgecolor=INK, lw=0.9))
    fig.add_artist(Rectangle((0.045, 0.035), 0.91, 0.055, transform=fig.transFigure,
                             facecolor=LIGHT, edgecolor=INK, lw=0.8))
    fig.text(0.058, 0.058, "HOCKEYMOM DUAL-CAMERA ENCLOSURE", fontsize=7.7, weight="bold")
    fig.text(0.294, 0.058, "CONFIGURATION DIMENSION GUIDE", fontsize=7.7)
    fig.text(0.557, 0.058, f"SOURCE {SOURCE_HASH}", fontsize=7.3)
    fig.text(0.735, 0.058, f"UTC {GENERATED}", fontsize=7.3)
    fig.text(0.858, 0.058, f"SHEET {number:02d}/{TOTAL_SHEETS:02d}", fontsize=7.7, weight="bold")
    fig.text(0.058, 0.0425, "ALL DIMENSIONS mm | NTS | CONFIGURED VALUES; SOLVERS MAY CLAMP REQUESTS",
             fontsize=6.5, color=GRAY)
    return fig


def panel(fig, rect, title: str, view: str = ""):
    ax = fig.add_axes(rect)
    ax.set_facecolor("#fbfdfe")
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color(GRID)
        spine.set_linewidth(0.8)
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
    ax.set_aspect("equal", adjustable="datalim")
    ax.text(0.02, 0.965, title, transform=ax.transAxes, va="top", ha="left",
            fontsize=9.5, weight="bold", color=INK,
            bbox=dict(facecolor=WHITE, edgecolor="none", pad=1.5, alpha=0.95), zorder=20)
    if view:
        ax.text(0.98, 0.965, view, transform=ax.transAxes, va="top", ha="right",
                fontsize=7.2, weight="bold", color=GRAY, zorder=20)
    return ax


def setup(ax, xmin, xmax, ymin, ymax):
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)


def centerline(ax, p1, p2):
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=GRAY, lw=0.65,
            ls=(0, (7, 2, 1.5, 2)), zorder=1)


def dim_h(ax, x1, x2, y, obj_y, label, color=BLUE):
    ax.plot([x1, x1], [obj_y, y], color=color, lw=0.75)
    ax.plot([x2, x2], [obj_y, y], color=color, lw=0.75)
    ax.add_patch(FancyArrowPatch((x1, y), (x2, y), arrowstyle="<|-|>",
                                 mutation_scale=8, lw=0.85, color=color))
    ax.text((x1 + x2) / 2, y, label, ha="center", va="bottom", color=color,
            fontsize=7.7, bbox=dict(facecolor=WHITE, edgecolor="none", pad=0.9), zorder=15)


def dim_v(ax, y1, y2, x, obj_x, label, color=BLUE):
    ax.plot([obj_x, x], [y1, y1], color=color, lw=0.75)
    ax.plot([obj_x, x], [y2, y2], color=color, lw=0.75)
    ax.add_patch(FancyArrowPatch((x, y1), (x, y2), arrowstyle="<|-|>",
                                 mutation_scale=8, lw=0.85, color=color))
    ax.text(x, (y1 + y2) / 2, label, ha="left", va="center", rotation=90,
            color=color, fontsize=7.7,
            bbox=dict(facecolor=WHITE, edgecolor="none", pad=0.9), zorder=15)


def dim_aligned(ax, p1, p2, offset, label, color=BLUE):
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    nx, ny = -dy / length, dx / length
    q1 = (x1 + nx * offset, y1 + ny * offset)
    q2 = (x2 + nx * offset, y2 + ny * offset)
    ax.plot([x1, q1[0]], [y1, q1[1]], color=color, lw=0.75)
    ax.plot([x2, q2[0]], [y2, q2[1]], color=color, lw=0.75)
    ax.add_patch(FancyArrowPatch(q1, q2, arrowstyle="<|-|>", mutation_scale=8,
                                 lw=0.85, color=color))
    rotation = math.degrees(math.atan2(dy, dx))
    ax.text((q1[0] + q2[0]) / 2, (q1[1] + q2[1]) / 2, label,
            ha="center", va="bottom", rotation=rotation, rotation_mode="anchor",
            color=color, fontsize=7.7,
            bbox=dict(facecolor=WHITE, edgecolor="none", pad=0.9), zorder=15)


def leader(ax, xy, text_xy, text, color=ORANGE, align="left"):
    ax.annotate(text, xy=xy, xytext=text_xy, ha=align, va="center", fontsize=7.4,
                color=color, arrowprops=dict(arrowstyle="-|>", color=color, lw=0.8),
                bbox=dict(boxstyle="round,pad=0.18", fc=WHITE, ec=color, lw=0.55), zorder=30)


def note_box(fig, rect, title, lines, accent=BLUE):
    ax = fig.add_axes(rect)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0.012,rounding_size=0.02",
                                transform=ax.transAxes, facecolor=LIGHT, edgecolor=GRID, lw=0.9))
    ax.add_patch(Rectangle((0, 0), 0.012, 1, transform=ax.transAxes,
                           facecolor=accent, edgecolor="none"))
    ax.text(0.04, 0.86, title, transform=ax.transAxes, fontsize=8.2,
            weight="bold", color=accent, va="top")
    ax.text(0.04, 0.70, "\n".join(lines), transform=ax.transAxes, fontsize=7.1,
            color=INK, va="top", linespacing=1.34)
    return ax


def soft_triangle(depth=234, width=180, taper_scale=1.0, taper_start=0.55, samples=160):
    """Schematic rounded-triangle footprint in (front/rear, transverse) axes."""
    upper = []
    for index in range(samples + 1):
        u = index / samples
        x = -depth / 2 + depth * u
        # Blunt nose, widest through mid-body, rounded broad rear corners.
        core = math.sin(math.pi * (0.05 + 0.90 * u)) ** 0.42
        bias = 0.66 + 0.34 * u
        half = width / 2 * min(1.0, core * bias * 1.18)
        if u > taper_start:
            blend = (u - taper_start) / (1 - taper_start)
            blend = blend * blend * (3 - 2 * blend)
            half *= 1 - (1 - taper_scale) * blend
        upper.append((x, half))
    return upper + [(x, -y) for x, y in reversed(upper)]


def rotated_rect(cx, cy, length, width, angle_deg):
    angle = math.radians(angle_deg)
    ux, uy = math.cos(angle), math.sin(angle)
    vx, vy = -uy, ux
    return [
        (cx + sx * length / 2 * ux + sy * width / 2 * vx,
         cy + sx * length / 2 * uy + sy * width / 2 * vy)
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))
    ]


def page_cover(pdf):
    fig = new_sheet(1, "CONFIGURATION DIMENSION GUIDE",
                    "Parametric Hockeymom-style enclosure for two GoPro MISSION 1 cameras")
    ax = fig.add_axes([0.075, 0.18, 0.55, 0.67])
    ax.axis("off")
    setup(ax, -145, 145, -115, 115)
    outline = soft_triangle(220, 175, 0.75, 0.55)
    ax.add_patch(Polygon(outline, closed=True, facecolor="#e8f2f8", edgecolor=BLUE, lw=2.0))
    # Eye surrounds and axes at the camera-side nose.
    for sign in (-1, 1):
        cy = sign * 31
        ax.add_patch(FancyBboxPatch((-126, cy - 24), 17, 48,
                                    boxstyle="round,pad=0,rounding_size=6",
                                    facecolor=WHITE, edgecolor=ORANGE, lw=2.0))
        ax.plot([-118, -55], [cy, cy + sign * 44], color=ORANGE, lw=1.1, ls="--")
    # Rear fan stations.
    for cy in (-50, 50):
        ax.add_patch(Rectangle((86, cy - 22.5), 16, 45, facecolor="#dcebdd",
                               edgecolor=GREEN, lw=1.5))
        ax.add_patch(Circle((94, cy), 12, facecolor="none", edgecolor=GREEN, lw=1.2))
    # Lid line and fasteners.
    ax.plot([p[0] for p in outline] + [outline[0][0]],
            [p[1] for p in outline] + [outline[0][1]], color=INK, lw=0.55, ls="--")
    for x, y in ((-25, -72), (-25, 72), (55, -65), (55, 65)):
        ax.add_patch(Circle((x, y), 4.4, facecolor=WHITE, edgecolor=PURPLE, lw=1.2))
        ax.add_patch(Circle((x, y), 1.5, facecolor=PURPLE, edgecolor="none"))
    ax.text(-137, -105, "CAMERA SIDE / FRONT", color=ORANGE, fontsize=8, weight="bold")
    ax.text(68, -105, "FAN SIDE / REAR", color=GREEN, fontsize=8, weight="bold")
    centerline(ax, (-140, 0), (135, 0))

    fig.text(0.655, 0.812, "DRAWING SET", fontsize=11, weight="bold", color=INK)
    sections = [
        ("02", "Shell, footprint & rear taper"),
        ("03", "Camera axes, eyes & lens outset"),
        ("04", "Vertical camera packaging & airflow"),
        ("05", "Lid, four posts & M3 hardware"),
        ("06", "Cradle and removable brackets"),
        ("07", "Purchased worm & horizontal journals"),
        ("08", ("Direct purchased-wheel" if direct_purchased_wheel_drive() else
                "Legacy coaxial-pinion") + " drivetrain & centers"),
        ("09", "Vertical journals & support-free assembly"),
        ("10", "Carrier guide & yaw-safe eye guard"),
        ("11", "Rear fan stations & alignment"),
        ("12", "Baffled acoustic cassette & microphone"),
        ("13", "Bottom 1/4-inch captive-nut mount"),
        ("14", "Bottom keystone snap sockets"),
        ("15", "Major parameter quick reference"),
    ]
    y = 0.775
    for number, title in sections:
        fig.text(0.658, y, number, fontsize=8, color=WHITE, weight="bold",
                 bbox=dict(boxstyle="round,pad=0.25", fc=BLUE, ec=BLUE))
        fig.text(0.700, y, title, fontsize=8.2, color=INK)
        y -= 0.041
    note_box(fig, [0.65, 0.105, 0.275, 0.085], "HOW TO USE",
             ["Names match the Python configuration block.",
              "Blue = dimension; orange = optical/critical.",
              "Values are defaults read at PDF generation time."], BLUE)
    pdf.savefig(fig)
    plt.close(fig)


def page_body(pdf):
    fig = new_sheet(2, "SHELL, FOOTPRINT & REAR TAPER",
                    "X runs camera-side (-X) to fan-side (+X); Y is transverse width; Z is height")
    ax = panel(fig, [0.065, 0.48, 0.56, 0.39], "ROUNDED-TRIANGULAR FOOTPRINT", "TOP")
    depth = float(val("BODY_DEPTH", 233.661))
    width = float(val("BODY_WIDTH", 180.0))
    scale = float(val("REAR_WIDTH_TAPER_SCALE", 0.75))
    start = float(val("REAR_WIDTH_TAPER_START_FRACTION", 0.55))
    base = soft_triangle(depth, width, 1.0, start)
    tapered = soft_triangle(depth, width, scale, start)
    ax.add_patch(Polygon(base, closed=True, facecolor="none", edgecolor=GRAY, lw=0.9, ls="--"))
    ax.add_patch(Polygon(tapered, closed=True, facecolor="#e6f1f7", edgecolor=BLUE, lw=1.6))
    xstart = -depth / 2 + start * depth
    centerline(ax, (-depth / 2 - 12, 0), (depth / 2 + 12, 0))
    ax.plot([xstart, xstart], [-width / 2 - 5, width / 2 + 5], color=ORANGE, lw=1.0, ls="--")
    dim_h(ax, -depth / 2, depth / 2, -width / 2 - 20, -width / 2, f"BODY_DEPTH = {num(depth,3)}")
    dim_v(ax, -width / 2, width / 2, -depth / 2 - 20, -depth / 2,
          f"BODY_WIDTH = {num(width,1)}")
    dim_h(ax, -depth / 2, xstart, width / 2 + 17, width / 2,
          f"TAPER START = {num(start*100,0)}% DEPTH", ORANGE)
    leader(ax, (depth / 2 - 6, scale * width * 0.42), (depth * 0.18, width * 0.57),
           f"REAR_WIDTH_TAPER_SCALE = {num(scale,2)}\nnominal rear width = {num(scale*width,1)}", GREEN)
    leader(ax, (-depth * 0.28, width * 0.30), (-depth * 0.05, width * 0.44),
           f"FOOTPRINT_TRIANGULARITY = {num(val('FOOTPRINT_TRIANGULARITY',0.68),2)}", PURPLE)
    setup(ax, -depth / 2 - 32, depth / 2 + 32, -width / 2 - 30, width / 2 + 30)

    ax2 = panel(fig, [0.65, 0.48, 0.285, 0.39], "ROOF / HEIGHT TAPER", "SIDE")
    h = float(val("BODY_HEIGHT", 72.653))
    base_h = float(val("BASE_HEIGHT", 68.0))
    reduce = float(val("REAR_HEIGHT_REDUCTION", 10.0))
    hs = float(val("REAR_HEIGHT_TAPER_START_FRACTION", 0.88))
    knee = -depth / 2 + hs * depth
    ax2.add_patch(Polygon([(-depth/2, 0), (depth/2, 0), (depth/2, h-reduce),
                           (knee, h), (-depth/2, h)], closed=True,
                          facecolor="#e6f1f7", edgecolor=BLUE, lw=1.5))
    ax2.plot([-depth/2, depth/2], [base_h, base_h-reduce], color=GREEN, lw=1.0, ls="--")
    ax2.plot([knee, knee], [0, h+5], color=ORANGE, lw=1.0, ls="--")
    dim_v(ax2, 0, h, -depth/2-22, -depth/2, f"BODY_HEIGHT\n{num(h,3)}")
    dim_v(ax2, base_h, h, -depth/2-9, -depth/2, f"LID\n{num(h-base_h,3)}")
    dim_v(ax2, h-reduce, h, depth/2+16, depth/2, f"REQUEST\n-{num(reduce,1)}", ORANGE)
    dim_h(ax2, -depth/2, knee, h+14, h, f"HEIGHT TAPER START = {num(hs*100,0)}%", ORANGE)
    leader(ax2, (depth/2-5, 12), (depth*0.10, 23),
           f"vertical anchor >= {mm('REAR_HEIGHT_TAPER_ANCHOR_Z',12)}", GREEN)
    setup(ax2, -depth/2-35, depth/2+35, -8, h+23)

    note_box(fig, [0.065, 0.275, 0.275, 0.145], "SOLVER BEHAVIOR",
             [f"REAR_TAPER_SOLVER = {val('REAR_TAPER_SOLVER','keepout')!r}",
              f"protected margin = {mm('REAR_TAPER_PROTECTED_MARGIN',4)}",
              f"minimum taper run = {mm('REAR_TAPER_MIN_RUN',30)}",
              f"maximum roof slope = {deg('REAR_TAPER_MAX_SLOPE_DEG',18)}"], ORANGE)
    note_box(fig, [0.355, 0.275, 0.275, 0.145], "BOTTOM EDGE LOFT",
             ["BODY_SECTIONS = (Z, XY scale)",
              "0.0 -> 0.96   |   6.0 -> 0.99",
              "12.0 -> 1.00 | BASE_HEIGHT -> 1.00",
              f"wall = {mm('BODY_WALL_THICKNESS',3.2)}; floor = {mm('BOTTOM_THICKNESS',3.2)}"], PURPLE)
    note_box(fig, [0.65, 0.275, 0.285, 0.145], "IMPORTANT",
             ["Width and height taper start only after protected",
              "camera, cartridge and hardware envelopes. A request",
              "may be clamped; the generator reports resolved values.",
              "Standard validated default: 10.0 request -> 8.5 resolved.",
              "Screw islands remain locally horizontal."], GREEN)
    pdf.savefig(fig)
    plt.close(fig)


def page_optics(pdf):
    fig = new_sheet(3, "CAMERA AXES, EYES & LENS OUTSET",
                    "Camera half-angle is a primary shell-shape input; the nose broadens when tighter overlap requires it")
    ax = panel(fig, [0.065, 0.48, 0.49, 0.39], "CAMERA CENTERLINES", "TOP / PLAN")
    half = float(val("CAMERA_HALF_ANGLE_DEG", 35.0))
    sep = 2 * half
    origin = (74, 0)
    ax.add_patch(Polygon([(-80,-60),(95,-78),(105,78),(-80,60)], closed=True,
                         facecolor="#edf4f7", edgecolor=BLUE, lw=1.3))
    for sign in (-1, 1):
        angle = 180 + sign * half
        rad = math.radians(angle)
        cx, cy = 25, sign * 25
        ax.add_patch(Polygon(rotated_rect(cx, cy, 44, 32, angle), closed=True,
                             facecolor="#d7dde2", edgecolor=INK, lw=1.0))
        ax.plot([cx, cx + 105*math.cos(rad)], [cy, cy + 105*math.sin(rad)],
                color=ORANGE, lw=1.3)
        ax.add_patch(Circle((cx + 20*math.cos(rad), cy + 20*math.sin(rad)), 6,
                            facecolor=ORANGE, edgecolor=INK, lw=0.6))
    ax.add_patch(Arc(origin, 68, 68, theta1=180-half, theta2=180+half,
                     edgecolor=ORANGE, lw=1.2))
    ax.text(44, 0, f"2 x HALF_ANGLE\n= {num(sep,1)} deg separation", ha="center", va="center",
            fontsize=8, color=ORANGE, bbox=dict(fc=WHITE, ec=ORANGE, lw=0.6))
    leader(ax, (-55, 0), (-5, 62), "axes centered on eye openings", ORANGE)
    centerline(ax, (-95, 0), (112, 0))
    setup(ax, -100, 115, -92, 92)

    ax2 = panel(fig, [0.58, 0.48, 0.355, 0.39], "OPENING + RAISED SURROUND", "NORMAL TO EYE")
    ow = float(val("EYE_OPENING_WIDTH", 58.0)); oh = float(val("EYE_OPENING_HEIGHT", 46.0))
    bw = float(val("EYE_BEZEL_WIDTH", 64.0)); bh = float(val("EYE_BEZEL_HEIGHT", 52.0))
    ax2.add_patch(FancyBboxPatch((-bw/2,-bh/2), bw,bh,
                                 boxstyle=f"round,pad=0,rounding_size={val('EYE_BEZEL_CORNER_RADIUS',14.5)}",
                                 facecolor="#cce0ec", edgecolor=BLUE, lw=1.4))
    ax2.add_patch(FancyBboxPatch((-ow/2,-oh/2), ow,oh,
                                 boxstyle=f"round,pad=0,rounding_size={val('EYE_OPENING_CORNER_RADIUS',10)}",
                                 facecolor=WHITE, edgecolor=ORANGE, lw=1.5))
    slot = float(val("EYE_TOP_LOADING_SLOT_WIDTH",44.0))
    ax2.add_patch(Rectangle((-slot/2,0),slot,bh/2+10,facecolor="#fff5ea",edgecolor=ORANGE,lw=0.8,ls="--"))
    dim_h(ax2,-ow/2,ow/2,-bh/2-11,-oh/2,f"OPENING {num(ow,1)}")
    dim_v(ax2,-oh/2,oh/2,bw/2+11,ow/2,f"OPENING {num(oh,1)}")
    dim_h(ax2,-bw/2,bw/2,bh/2+6,bh/2,f"BEZEL {num(bw,1)}")
    dim_v(ax2,-bh/2,bh/2,-bw/2-14,-bw/2,f"BEZEL {num(bh,1)}")
    dim_h(ax2,-slot/2,slot/2,8,0,f"TOP SLOT {num(slot,1)}",ORANGE)
    leader(ax2,(ow/2-5,oh/2-3),(45,28),f"corner R{num(val('EYE_OPENING_CORNER_RADIUS',10),1)}",PURPLE)
    setup(ax2,-55,58,-43,47)

    ax3 = panel(fig, [0.065, 0.195, 0.49, 0.225], "SHALLOW RIM + PRINTABLE REAR TRANSITION", "LOWER-EYE SECTION")
    bezel = float(val("EYE_BEZEL_DEPTH", 5.0))
    recess = float(val("EYE_FACE_RECESS_MAX_DEPTH", 18.0))
    relief = float(val("EYE_ADJUSTABLE_BODY_RELIEF_DEPTH", 3.0))
    retained_lip = float(val("EYE_FRONT_STRUCTURAL_RIM_DEPTH", 2.0))
    root_land = float(val("EYE_REAR_RELIEF_ROOT_LAND", 0.50))
    ramp_angle = float(val("EYE_REAR_RELIEF_PRINT_ANGLE_DEG", 45.0))
    ramp_run = (((bh - oh) / 2.0) - root_land) / math.tan(math.radians(ramp_angle))
    root_depth = bezel - retained_lip - ramp_run
    eye_advance = float(val("ADJUSTABLE_EYE_FORWARD_CLEARANCE_OFFSET", 1.75))
    # The drawing is deliberately exaggerated: 14 plot units show the 2 mm
    # front rim and 22 show the 3 mm transition so both are legible in print.
    ax3.add_patch(Rectangle((5, -13), 14, 13, facecolor="#cce0ec", edgecolor=BLUE, lw=1.2))
    ax3.add_patch(Polygon([(-17, -2), (5, -13), (5, 0), (-17, 0)], closed=True,
                          facecolor="#dcebdc", edgecolor=GREEN, lw=1.2))
    ax3.plot([-17, 19], [0, 0], color=ORANGE, lw=1.35)
    ax3.add_patch(FancyBboxPatch((-50, 6), 31, 26, boxstyle="round,pad=0,rounding_size=3",
                                 facecolor="#d7dde2", edgecolor=INK, lw=1.0))
    ax3.add_patch(Rectangle((-19, 12), 46, 14, facecolor="#f3c7aa", edgecolor=ORANGE, lw=0.9))
    ax3.plot([19, 19], [-16, 36], color=BLUE, lw=0.8, ls="--")
    dim_h(ax3, -17, 5, -18, -13, f"RAMP RUN {num(ramp_run,1)}", GREEN)
    dim_h(ax3, 5, 19, -27, -13, f"FRONT RIM {num(retained_lip,1)}")
    leader(ax3, (-17, -1), (-48, -8),
           f"root land / depth\n{num(root_land,2)} / {num(root_depth,2)}", GREEN)
    leader(ax3, (-5, -6), (-51, 2), f"print ramp {num(ramp_angle,1)} deg\nrear body relief {num(relief,1)}", GREEN)
    leader(ax3, (27, 19), (43, 30), "lens face projects\nbeyond shallow eye", ORANGE)
    leader(ax3, (19, 3), (36, -6), f"nominal bezel depth {num(bezel,1)}\nlocalized recess <= {num(recess,1)}", BLUE)
    setup(ax3, -58, 68, -31, 41)

    note_box(fig,[0.58,0.195,0.355,0.225],"PLACEMENT RULES",
             [f"CAMERA_FORWARD_PLACEMENT_MODE = {val('CAMERA_FORWARD_PLACEMENT_MODE','maximize')!r}",
              f"fixed independent advance = {val('CAMERA_FIXED_INDEPENDENT_FORWARD_ADVANCE_ENABLED',True)} (needs recess + fixed relief)",
              f"adjustable eye advance = {num(eye_advance,2)} mm",
              f"rear eye relief / retained rim = {num(relief,1)} / {num(retained_lip,1)} mm",
              f"rear root land / depth = {num(root_land,2)} / {num(root_depth,2)} mm",
              f"actual printable ramp angle = {num(ramp_angle,1)} deg",
              f"floor-rooted recess web width = {mm('EYE_RECESS_BASE_SUPPORTED_WEB_WIDTH',6)}",
              f"configured minimum yaw-sweep protrusion = {mm('CAMERA_LENS_MIN_SWEEP_EYE_FACE_PROTRUSION',7.2)}",
              "Actual solved protrusions are printed by each Blender build.",
              "No deep throat or floating recess-anchor bars are generated."],ORANGE)
    pdf.savefig(fig); plt.close(fig)


def page_vertical(pdf):
    fig = new_sheet(4,"VERTICAL CAMERA PACKAGING & FLOOR AIRFLOW",
                    "The MISSION 1 body is supported above the floor; the full reference envelope includes buttons and lens")
    ax = panel(fig,[0.065,0.40,0.53,0.47],"CAMERA + SUPPORT DATUM","SIDE SECTION")
    floor=float(val("BOTTOM_THICKNESS",3.2)); gap=float(val("CAMERA_FLOOR_CLEARANCE",4.5))
    body_h=float(cam("BODY_HEIGHT",51.0)); env_h=float(cam("REFERENCE_ENVELOPE_HEIGHT",54.0))
    body_d=float(cam("BODY_DEPTH",27.8)); env_d=float(cam("REFERENCE_ENVELOPE_DEPTH",44.4))
    lens_proj=env_d-body_d
    ax.add_patch(Rectangle((-52,0),104,floor,facecolor="#b9d4e4",edgecolor=BLUE,lw=1.2))
    ax.add_patch(Rectangle((-30,floor),12,gap,facecolor="#dcebdd",edgecolor=GREEN,lw=0.8))
    ax.add_patch(Rectangle((18,floor),12,gap,facecolor="#dcebdd",edgecolor=GREEN,lw=0.8))
    ax.add_patch(FancyBboxPatch((-39,floor+gap),78,body_h,boxstyle="round,pad=0,rounding_size=4",
                                facecolor="#d7dde2",edgecolor=INK,lw=1.2))
    ax.add_patch(FancyBboxPatch((-26,floor+gap+body_h-5),17,3,boxstyle="round,pad=0,rounding_size=1",
                                facecolor=GRAY,edgecolor=INK,lw=0.7))
    ax.add_patch(Rectangle((-34,floor+gap+12),27,lens_proj,facecolor=ORANGE,edgecolor=INK,lw=0.7))
    for x in (-10,0,10):
        ax.add_patch(FancyArrowPatch((x,floor+1),(x,floor+gap+22),arrowstyle="-|>",
                                     mutation_scale=8,color=GREEN,lw=1.1))
    dim_v(ax,floor,floor+gap,-48,-39,f"FLOOR CLEARANCE\n{num(gap,1)}",GREEN)
    dim_v(ax,floor+gap,floor+gap+body_h,47,39,f"BODY {num(body_h,1)}")
    dim_v(ax,floor+gap,floor+gap+env_h,58,39,f"ENVELOPE {num(env_h,1)}",PURPLE)
    dim_h(ax,-39,39,floor+gap+body_h+12,floor+gap+body_h,f"BODY WIDTH {num(cam('BODY_WIDTH',78),1)}")
    leader(ax,(-20,floor+gap+12),(-48,40),f"lens projection {num(lens_proj,1)}",ORANGE)
    setup(ax,-64,70,-4,80)

    ax2=panel(fig,[0.62,0.48,0.315,0.39],"VENTED SUPPORT PADS","BOTTOM / PLAN")
    pad_l=float(val("CAMERA_SUPPORT_PAD_RADIAL_LENGTH",19)); pad_w=float(val("CAMERA_SUPPORT_PAD_TANGENTIAL_WIDTH",12)); spacing=float(val("CAMERA_SUPPORT_PAD_TANGENTIAL_SPACING",36))
    ax2.add_patch(FancyBboxPatch((-39,-14),78,28,boxstyle="round,pad=0,rounding_size=4",
                                 facecolor="none",edgecolor=INK,lw=1.0))
    for y in (-spacing/2,spacing/2):
        ax2.add_patch(Rectangle((-pad_l/2,y-pad_w/2),pad_l,pad_w,facecolor="#dcebdd",edgecolor=GREEN,lw=1.1))
    dim_v(ax2,-spacing/2,spacing/2,49,39,f"PAD SPACING {num(spacing,1)}")
    dim_h(ax2,-pad_l/2,pad_l/2,-29,-14,f"RADIAL LENGTH {num(pad_l,1)}")
    dim_v(ax2,-pad_w/2,pad_w/2,-49,-39,f"WIDTH {num(pad_w,1)}")
    ax2.add_patch(FancyArrowPatch((-31,0),(31,0),arrowstyle="-|>",mutation_scale=10,color=GREEN,lw=1.3))
    ax2.text(0,3,"open cooling path",ha="center",color=GREEN,fontsize=7.5)
    setup(ax2,-58,62,-40,40)

    note_box(fig,[0.065,0.18,0.255,0.15],"VERTICAL DEFAULTS",
             [f"minimum accepted floor gap = {mm('CAMERA_MIN_FLOOR_AIR_GAP',3)}",
              "EYE_CENTER_Z = None (derived from camera)",
              f"body height = {num(body_h,1)}; full envelope = {num(env_h,1)}",
              f"base/lid seam = Z {num(val('BASE_HEIGHT',68),1)}"],BLUE)
    note_box(fig,[0.34,0.18,0.255,0.15],"AIRFLOW INTENT",
             ["Rear fans wash the camera back and sides.",
              "Split rear guides and vented tray preserve flow.",
              "Raised support pads maintain under-body passage.",
              "Eye annuli act as forward exhausts."],GREEN)
    note_box(fig,[0.62,0.18,0.315,0.23],"MISSION 1 REFERENCE ENVELOPE",
             [f"body-only: {num(cam('BODY_WIDTH',78),1)} W x {num(body_d,1)} D x {num(body_h,1)} H",
              f"full measured envelope: {num(cam('REFERENCE_ENVELOPE_WIDTH',81),1)} W x {num(env_d,1)} D x {num(env_h,1)} H",
              f"lens face width/height = {num(cam('LENS_FACE_WIDTH',41.8),1)}",
              f"lens face Y = {num(cam('LENS_FACE_Y',44.4),1)}",
              "Full envelope includes lens projection and controls.",
              "Dummy is upright unless CAMERA_UPSIDE_DOWN=True."],PURPLE)
    pdf.savefig(fig); plt.close(fig)


def page_lid(pdf):
    fig=new_sheet(5,"LID, FOUR POSTS & M3 HARDWARE",
                  "Auto placement keeps posts clear of cameras, brackets, cartridge, fans and service paths")
    ax=panel(fig,[0.065,0.43,0.46,0.44],"FOUR-POINT RETENTION","TOP")
    outline=soft_triangle(190,145,0.75,0.55)
    ax.add_patch(Polygon(outline,closed=True,facecolor="#edf4f7",edgecolor=BLUE,lw=1.3))
    post_d=float(val("FASTENER_POST_DIAMETER",10.5))
    points=((-38,-49),(-38,49),(45,-43),(45,43))
    for index,(x,y) in enumerate(points,1):
        ax.add_patch(Circle((x,y),post_d/2,facecolor=WHITE,edgecolor=PURPLE,lw=1.3))
        ax.add_patch(Circle((x,y),1.7,facecolor=PURPLE,edgecolor="none"))
        ax.text(x+5,y+5,str(index),color=PURPLE,fontsize=7,weight="bold")
    centerline(ax,(-105,0),(110,0)); centerline(ax,(0,-78),(0,78))
    dim_v(ax,-49,49,-65,-38,"AUTO POST PAIR",PURPLE)
    leader(ax,points[0],(-89,-69),f"post OD {num(post_d,1)}",PURPLE)
    leader(ax,(45,43),(72,66),f"min center spacing {mm('FASTENER_POST_MIN_CENTER_SPACING',18)}",PURPLE)
    setup(ax,-110,115,-90,90)

    ax2=panel(fig,[0.55,0.43,0.385,0.44],"SOCKET-HEAD + HEAT INSERT STACK","SECTION")
    lid_t=float(val("LID_THICKNESS",4.653)); post_h=34
    ax2.add_patch(Rectangle((-46,post_h),92,lid_t,facecolor="#ccebd7",edgecolor=GREEN,lw=1.2))
    ax2.add_patch(Rectangle((-post_d/2,0),post_d,post_h,facecolor="#cce0ec",edgecolor=BLUE,lw=1.2))
    # bore, insert, counterbore
    hole=float(val("HEAT_INSERT_HOLE_DIAMETER",4)); depth=float(val("HEAT_INSERT_HOLE_DEPTH",15.5))
    ax2.add_patch(Rectangle((-hole/2,post_h-depth),hole,depth+lid_t,facecolor=WHITE,edgecolor=INK,lw=0.7))
    cb=float(val("LID_SCREW_HEAD_COUNTERBORE_DIAMETER",6.2)); cbd=float(val("LID_SCREW_HEAD_COUNTERBORE_DEPTH",3.3))
    ax2.add_patch(Rectangle((-cb/2,post_h+lid_t-cbd),cb,cbd,facecolor="#fff5ea",edgecolor=ORANGE,lw=0.9))
    lead=float(val("HEAT_INSERT_LEADIN_DIAMETER",4.8)); leadd=float(val("HEAT_INSERT_LEADIN_DEPTH",1))
    ax2.add_patch(Polygon([(-lead/2,post_h),(-hole/2,post_h-leadd),(hole/2,post_h-leadd),(lead/2,post_h)],
                          closed=True,facecolor="#f7d9c5",edgecolor=ORANGE,lw=0.7))
    ax2.add_patch(Rectangle((-2.3,post_h-depth+1),4.6,depth-3,facecolor="#d8b66a",edgecolor=INK,lw=0.8,hatch="///"))
    dim_h(ax2,-post_d/2,post_d/2,-6,0,f"POST OD {num(post_d,1)}")
    dim_h(ax2,-hole/2,hole/2,14,20,f"INSERT PILOT dia {num(hole,1)}",ORANGE)
    dim_v(ax2,post_h-depth,post_h,15,post_d/2,f"DEPTH {num(depth,1)}",ORANGE)
    dim_v(ax2,post_h,post_h+lid_t,37,46,f"LID {num(lid_t,3)}",GREEN)
    leader(ax2,(cb/2,post_h+lid_t-cbd/2),(49,43),f"counterbore dia {num(cb,1)} x {num(cbd,1)} deep",ORANGE,"right")
    leader(ax2,(0,post_h+lid_t),(49,52),f"shank clearance dia {mm('LID_SCREW_CLEARANCE_DIAMETER',3.4)}",BLUE,"right")
    setup(ax2,-53,57,-12,58)

    ax3=panel(fig,[0.065,0.18,0.46,0.18],"LOCATING LIP","LOCAL SECTION")
    lip_d=float(val("LID_LIP_DEPTH",3)); lip_t=float(val("LID_LIP_THICKNESS",1.8)); lip_c=float(val("LID_LIP_CLEARANCE",0.30))
    ax3.add_patch(Rectangle((-42,12),84,lid_t,facecolor="#ccebd7",edgecolor=GREEN,lw=1.0))
    ax3.add_patch(Rectangle((-35,0),7,12,facecolor="#cce0ec",edgecolor=BLUE,lw=1.0))
    ax3.add_patch(Rectangle((28,0),7,12,facecolor="#cce0ec",edgecolor=BLUE,lw=1.0))
    ax3.add_patch(Rectangle((-28-lip_t,12-lip_d),lip_t,lip_d,facecolor="#ccebd7",edgecolor=GREEN,lw=1.0))
    ax3.add_patch(Rectangle((28,12-lip_d),lip_t,lip_d,facecolor="#ccebd7",edgecolor=GREEN,lw=1.0))
    dim_v(ax3,12-lip_d,12,-39,-30,f"DEPTH {num(lip_d,1)}",GREEN)
    dim_h(ax3,28,28+lip_t,4,9,f"THICK {num(lip_t,1)}",GREEN)
    leader(ax3,(29.8,10.5),(54,5),f"radial clearance {num(lip_c,2)}",BLUE,"right")
    setup(ax3,-48,60,-4,23)

    note_box(fig,[0.55,0.18,0.385,0.18],"PLACEMENT / CLEARANCE",
             [f"FASTENER_POST_PLACEMENT = {val('FASTENER_POST_PLACEMENT','auto')!r}",
              f"edge clearance = {mm('FASTENER_POST_EDGE_CLEARANCE',2)}",
              f"camera clearance = {mm('FASTENER_POST_CAMERA_CLEARANCE',10)}",
              f"post top clearance = {mm('FASTENER_POST_TOP_CLEARANCE',0.20,2)}",
              f"hold-down/lid pocket clearance = {mm('CAMERA_BRACKET_LID_LIP_RELIEF_CLEARANCE',0.50,2)}",
              f"minimum pocket-to-lid web = {mm('CAMERA_HOLD_DOWN_LID_RELIEF_MIN_UNDERSIDE_WEB',0.15,2)}",
              "Rear taper uses local post heights and flat screw islands."],PURPLE)
    pdf.savefig(fig); plt.close(fig)


def page_retention(pdf):
    fig=new_sheet(6,"CAMERA CRADLE & REMOVABLE BRACKETS",
                  "Snug fixed guides, monolithic L-corner upper locators and split rear stops retain the camera while preserving airflow")
    ax=panel(fig,[0.065,0.43,0.48,0.44],"FIXED CRADLE","TOP")
    bw=float(cam("BODY_WIDTH",78)); bd=float(cam("BODY_DEPTH",27.8))
    ax.add_patch(FancyBboxPatch((-bw/2,-bd/2),bw,bd,boxstyle="round,pad=0,rounding_size=4",
                                facecolor="#e1e5e8",edgecolor=INK,lw=1.1))
    guide_t=float(val("CAMERA_CRADLE_SIDE_GUIDE_THICKNESS",7)); guide_l=float(val("CAMERA_CRADLE_SIDE_GUIDE_RADIAL_LENGTH",8))
    ax.add_patch(Rectangle((-bw/2-guide_t,-bd/2),guide_t,guide_l,facecolor="#cce0ec",edgecolor=BLUE,lw=1.0))
    datum_w=float(val("CAMERA_FRONT_STOP_FLOOR_DATUM_WIDTH",8)); datum_plot_depth=3.5
    ax.add_patch(Rectangle((-bw/2+9,-bd/2-datum_plot_depth),datum_w,datum_plot_depth,
                           facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.0))
    rear_t=float(val("CAMERA_CRADLE_REAR_GUIDE_THICKNESS",7)); rear_w=float(val("CAMERA_CRADLE_REAR_GUIDE_TANGENTIAL_WIDTH",50)); air=float(val("CAMERA_CRADLE_REAR_GUIDE_CENTER_AIR_GAP",18))
    seg=(rear_w-air)/2
    for sign in (-1,1):
        x0=sign*air/2 + (0 if sign>0 else -seg)
        ax.add_patch(Rectangle((x0,bd/2),seg,rear_t,facecolor="#cce0ec",edgecolor=BLUE,lw=1.0))
    ax.add_patch(FancyArrowPatch((0,bd/2+rear_t+13),(0,bd/2-9),arrowstyle="-|>",mutation_scale=10,color=GREEN,lw=1.2))
    dim_h(ax,-air/2,air/2,bd/2+rear_t+8,bd/2+rear_t,f"CENTER AIR GAP {num(air,1)}",GREEN)
    dim_h(ax,-rear_w/2,rear_w/2,-bd/2-14,-bd/2,f"REAR GUIDE TOTAL {num(rear_w,1)}")
    dim_v(ax,-bd/2,-bd/2+guide_l,-bw/2-guide_t-8,-bw/2-guide_t,f"SIDE LENGTH {num(guide_l,1)}")
    leader(ax,(-bw/2-guide_t/2,-bd/2+4),(-63,20),f"side guide {num(guide_t,1)} thick x {mm('CAMERA_CRADLE_SIDE_GUIDE_HEIGHT',12)} high",BLUE)
    leader(ax,(-bw/2+9+datum_w/2,-bd/2-datum_plot_depth/2),(-56,-31),
           "floor-rooted front datum\n(no suspended eye pads)",ORANGE)
    setup(ax,-72,72,-40,46)

    ax2=panel(fig,[0.57,0.43,0.365,0.44],"UPPER CLAMP + L LOCATORS","EXPLODED")
    thick=float(val("CAMERA_BRACKET_THICKNESS",4.8)); locator_t=float(val("CAMERA_BRACKET_USB_SIDE_LOCATOR_THICKNESS",5)); locator_h=float(val("CAMERA_BRACKET_USB_SIDE_LOCATOR_HEIGHT",6)); locator_l=float(val("CAMERA_BRACKET_USB_SIDE_LOCATOR_RADIAL_LENGTH",10))
    ax2.add_patch(FancyBboxPatch((-39,0),78,51,boxstyle="round,pad=0,rounding_size=4",
                                 facecolor="#e1e5e8",edgecolor=INK,lw=1.0))
    ax2.add_patch(Rectangle((-43,61),86,thick,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.2))
    # continuous L cheeks + roof overlap
    for sign in (-1,1):
        x=sign*(39+locator_t/2)
        ax2.add_patch(Rectangle((x-locator_t/2,51-locator_h),locator_t,10+locator_h,
                                facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.0))
        ax2.add_patch(Polygon([(x-locator_t/2,61),(x+locator_t/2,61),(sign*31,51),(sign*36,51)],
                              closed=True,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.0))
    ax2.add_patch(Rectangle((-39,48),16,3,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.0))
    ax2.add_patch(Rectangle((23,48),16,3,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.0))
    dim_v(ax2,61,61+thick,-52,-43,f"PLATE {num(thick,1)}",ORANGE)
    dim_v(ax2,51-locator_h,51,51,43,f"CONTACT {num(locator_h,1)}",ORANGE)
    dim_h(ax2,-39,39,72,65.8,"ROOF COVERS BOTH GUIDES",ORANGE)
    leader(ax2,(-42,55),(-65,33),f"locator {num(locator_t,1)} thick x {num(locator_l,1)} radial",ORANGE)
    leader(ax2,(31,49),(69,37),"continuous L-return\n(no butt-jointed tab)",PURPLE,"right")
    setup(ax2,-70,75,-8,82)

    ax3=panel(fig,[0.065,0.18,0.48,0.18],"SPLIT REAR CLAMP + AIR PASSAGE","REAR")
    lip_w=float(val("CAMERA_BRACKET_REAR_LIP_WIDTH",62)); lip_gap=float(val("CAMERA_BRACKET_REAR_LIP_CENTER_AIR_GAP",30)); lip_h=float(val("CAMERA_BRACKET_REAR_LIP_HEIGHT",12)); lip_t=float(val("CAMERA_BRACKET_REAR_LIP_THICKNESS",3))
    seg=(lip_w-lip_gap)/2
    ax3.add_patch(Rectangle((-39,0),78,32,facecolor="#e1e5e8",edgecolor=INK,lw=1.0))
    for sign in (-1,1):
        x0=sign*lip_gap/2+(0 if sign>0 else -seg)
        ax3.add_patch(Rectangle((x0,32),seg,lip_h,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.0))
    ax3.add_patch(FancyArrowPatch((0,52),(0,15),arrowstyle="-|>",mutation_scale=10,color=GREEN,lw=1.2))
    dim_h(ax3,-lip_gap/2,lip_gap/2,48,44,f"AIR GAP {num(lip_gap,1)}",GREEN)
    dim_v(ax3,32,44,47,39,f"LIP H {num(lip_h,1)}",ORANGE)
    setup(ax3,-52,56,-5,60)

    note_box(fig,[0.57,0.18,0.365,0.18],"FIT / STRENGTH DEFAULTS",
             [f"cradle side clearance = {mm('CAMERA_CRADLE_SIDE_CLEARANCE',0,1)} (snug)",
              f"front datum = {val('CAMERA_FRONT_STOP_STYLE','floor_rooted')!r}; {mm('CAMERA_FRONT_STOP_FLOOR_DATUM_WIDTH',8)} wide x {mm('CAMERA_FRONT_STOP_FLOOR_DATUM_HEIGHT_ABOVE_CAMERA_BOTTOM',12)} high",
              f"upper locator clearance = {mm('CAMERA_BRACKET_USB_SIDE_LOCATOR_CLEARANCE',0.10,2)}",
              f"guide plate overhang = {mm('CAMERA_BRACKET_GUIDE_PLATE_OVERHANG',2)}",
              f"arm width / plate embed = {mm('CAMERA_BRACKET_ARM_WIDTH',10)} / {mm('CAMERA_BRACKET_ARM_PLATE_EMBED',7)}",
              "USB case-wall openings are disabled; internal access remains."],ORANGE)
    pdf.savefig(fig); plt.close(fig)


def page_worm(pdf):
    fig=new_sheet(7,"PURCHASED WORM & HORIZONTAL PRINTED JOURNALS",
                  "The measured 3.81 mm stainless worm shaft runs in calibrated, lightly frictional 4.24 mm printed journals at both split saddles and the wall passage")
    shaft=float(val("CAMERA_WORM_SHAFT_DIAMETER",4.0))
    module=float(val("CAMERA_GEAR_MODULE",0.5))
    diameter_quotient=float(val("CAMERA_WORM_DIAMETER_QUOTIENT",18.0))
    worm_od=(diameter_quotient+2.0)*module
    hub_od=float(val("CAMERA_WORM_PLAIN_HUB_DIAMETER",10.0))
    total=float(val("CAMERA_WORM_LENGTH",20.0))
    threaded=float(val("CAMERA_WORM_THREADED_LENGTH",15.0))
    hub=float(val("CAMERA_WORM_PLAIN_HUB_LENGTH",5.0))
    bore=float(val("CAMERA_WORM_PLAIN_BUSHING_BORE_DIAMETER",4.24))
    max_clear=float(val("CAMERA_WORM_PLAIN_BUSHING_MAX_DIAMETRAL_CLEARANCE",0.40))

    ax=panel(fig,[0.065,0.48,0.55,0.39],"PURCHASED 1-START WORM ON STAINLESS SHAFT","SIDE")
    ax.add_patch(Rectangle((-24,-shaft/2),72,shaft,facecolor="#9ba6ae",edgecolor=INK,lw=0.8))
    ax.add_patch(Rectangle((0,-worm_od/2),threaded,worm_od,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.2))
    ax.add_patch(Rectangle((threaded,-hub_od/2),hub,hub_od,facecolor="#d8b66a",edgecolor=ORANGE,lw=1.2))
    for x in [i*1.5 for i in range(11)]:
        ax.plot([x-1.2,x+1.2],[-worm_od/2,worm_od/2],color=ORANGE,lw=0.65)
    centerline(ax,(-30,0),(53,0))
    dim_h(ax,0,total,14,worm_od/2,f"OVERALL {num(total,1)}")
    dim_h(ax,0,threaded,10,worm_od/2,f"THREADED {num(threaded,1)}",ORANGE)
    dim_h(ax,threaded,total,-11,-worm_od/2,f"PLAIN HUB {num(hub,1)}",PURPLE)
    dim_v(ax,-worm_od/2,worm_od/2,-8,0,f"OD {num(worm_od,1)}",ORANGE)
    dim_v(ax,-shaft/2,shaft/2,43,48,f"SHAFT dia {num(shaft,1)}",BLUE)
    leader(ax,(17.5,0),(38,8),f"plain / set-screw hub dia {num(hub_od,1)}\ntoward enclosure wall",PURPLE)
    setup(ax,-34,58,-max(17,hub_od/2+8),max(22,hub_od/2+12))

    ax2=panel(fig,[0.64,0.48,0.295,0.39],"SPLIT PRINTED JOURNAL","END SECTION")
    capw=float(val("CAMERA_WORM_CAP_TOTAL_WIDTH",26)); screwsp=float(val("CAMERA_WORM_CAP_SCREW_SPACING",16))
    ax2.add_patch(FancyBboxPatch((-capw/2,0),capw,10,boxstyle="round,pad=0,rounding_size=1.2",
                                 facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.1))
    ax2.add_patch(FancyBboxPatch((-capw/2,-10),capw,10,boxstyle="round,pad=0,rounding_size=1.2",
                                 facecolor="#cce0ec",edgecolor=BLUE,lw=1.1))
    ax2.add_patch(Circle((0,0),bore/2,facecolor=WHITE,edgecolor=RED,lw=1.1))
    ax2.add_patch(Circle((0,0),shaft/2,facecolor="#9ba6ae",edgecolor=INK,lw=0.7))
    for x in (-screwsp/2,screwsp/2):
        ax2.add_patch(Circle((x,5.2),1.7,facecolor=WHITE,edgecolor=PURPLE,lw=0.9))
    dim_h(ax2,-capw/2,capw/2,-16,-10,f"CAP WIDTH {num(capw,1)}")
    dim_h(ax2,-screwsp/2,screwsp/2,15,10,f"M3 SPACING {num(screwsp,1)}",PURPLE)
    leader(ax2,(bore/2,0),(25,-4),f"PRINTED BORE dia {num(bore,2)}",RED,"right")
    leader(ax2,(shaft/2,0),(25,5),f"4 mm rod in {num(bore,2)} bore\n{num(bore-shaft,2)} diametral play",BLUE,"right")
    setup(ax2,-22,30,-22,22)

    ax3=panel(fig,[0.065,0.18,0.55,0.22],"THREE HORIZONTAL SUPPORT STATIONS","SCHEMATIC PLAN")
    ax3.plot([-70,72],[0,0],color=GRAY,lw=4.0,solid_capstyle="round")
    for x,label in ((-42,"INNER SPLIT SUPPORT"),(8,"OUTER SPLIT SUPPORT"),(58,"WALL PASSAGE")):
        ax3.add_patch(Rectangle((x-5,-10),10,20,facecolor="#cce0ec",edgecolor=BLUE,lw=1.0))
        ax3.add_patch(Circle((x,0),3.0,facecolor=WHITE,edgecolor=RED,lw=1.0))
        ax3.text(x,-17,label,ha="center",va="top",fontsize=6.7,color=INK,weight="bold")
    ax3.add_patch(Rectangle((-17,-7),20,14,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.0))
    dim_h(ax3,-17,3,13,7,f"WORM {num(total,1)}",ORANGE)
    leader(ax3,(58,3),(73,13),f"same dia {num(bore,2)} close-fit bore",RED,"right")
    setup(ax3,-78,78,-27,27)

    note_box(fig,[0.64,0.18,0.295,0.22],"DEFAULT + FIT TUNING",
             [f"CAMERA_WORM_BEARINGS_ENABLED = {val('CAMERA_WORM_BEARINGS_ENABLED',False)}",
              f"plain journal bore = {num(bore,2)} mm",
              "Default intent: perceptible drag; shaft should not freewheel",
              f"Close-fit validator: bore - rod <= {num(max_clear,2)} mm",
              "Measure rod; use smallest 4.20-4.40 coupon that turns.",
              "Hand line-ream hard-seated caps if needed; never power-drill.",
              "Mark caps; reinstall over shaft; alternate M3 screws only snug.",
              "Verify/deburr metal worm bore; set measured endplay with shims.",
              f"Min bearing/key roof = {mm('CAMERA_WORM_CAP_MIN_BEARING_ROOF',1.5)} / {mm('CAMERA_WORM_CAP_MIN_KEY_ROOF',1.5)}",
              f"Insert pilot = {mm('CAMERA_WORM_CAP_INSERT_HOLE_DIAMETER',4)} x {mm('CAMERA_WORM_CAP_INSERT_DEPTH',5.5)} deep."],PURPLE)
    pdf.savefig(fig); plt.close(fig)


def page_idler_gears(pdf):
    direct=direct_purchased_wheel_drive()
    drive_name=("DIRECT PURCHASED-WHEEL" if direct else "LEGACY COAXIAL-PINION")
    subtitle=(
        "The lowered purchased 30T worm wheel meshes directly with both the horizontal worm and the cartridge's 170T-equivalent sector"
        if direct else
        "Horizontal purchased worm drives a vertical purchased wheel; a coaxial printed spur pinion then drives the 170T-equivalent sector"
    )
    fig=new_sheet(8,f"{drive_name} TWO-MESH DRIVETRAIN",subtitle)
    module=float(val("CAMERA_GEAR_MODULE",0.5)); sector_teeth=float(val("CAMERA_GEAR_EQUIVALENT_TEETH",170))
    pinion_teeth=float(val("CAMERA_IDLER_PINION_TEETH",30)); wheel_teeth=float(val("CAMERA_IDLER_TEETH",30))
    sector_r=module*sector_teeth/2; pinion_r=module*pinion_teeth/2
    wheel_r=module*wheel_teeth/2; worm_r=float(val("CAMERA_WORM_DIAMETER_QUOTIENT",18))*module/2
    drive_r=wheel_r if direct else pinion_r
    sector_clearance=idler_sector_mesh_clearance()
    sector_cd=sector_r+drive_r+sector_clearance
    worm_cd=wheel_r+worm_r+float(val("CAMERA_WORM_IDLER_MESH_CENTER_CLEARANCE",0.28))

    ax=panel(fig,[0.065,0.40,0.56,0.47],"PITCH CENTERS & POWER FLOW","TOP / PLAN")
    # Match the model: pivot, vertical wheel, and horizontal-worm pitch center
    # are collinear along gear_direction; the worm shaft runs on the
    # perpendicular tangent through that final center.
    pivot=(-26,-18); idler=(pivot[0]+sector_cd,pivot[1]); worm=(idler[0]+worm_cd,idler[1])
    ax.add_patch(Wedge(pivot,sector_r+1,105,255,width=6,facecolor="#cce0ec",edgecolor=BLUE,lw=1.2))
    ax.add_patch(Circle(pivot,2.2,facecolor=WHITE,edgecolor=PURPLE,lw=1.0))
    ax.add_patch(Circle(idler,drive_r,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.2))
    if not direct:
        ax.add_patch(Circle(idler,wheel_r-1.2,facecolor="#d8b66a",edgecolor=INK,lw=0.8,ls="--"))
    ax.add_patch(Circle(worm,worm_r,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.0))
    ax.plot([worm[0],worm[0]],[worm[1]-30,worm[1]+30],color=GRAY,lw=3.0)
    centerline(ax,(pivot[0],pivot[1]),(idler[0],idler[1]))
    centerline(ax,(idler[0],idler[1]),(worm[0],worm[1]))
    sector_drive_label="WHEEL" if direct else "PINION"
    dim_h(ax,pivot[0],idler[0],-43,pivot[1],f"{sector_drive_label}-SECTOR CENTER DISTANCE = {num(sector_cd,2)}",BLUE)
    dim_h(ax,idler[0],worm[0],-39,idler[1],f"WORM-WHEEL C.D. {num(worm_cd,2)}",ORANGE)
    leader(ax,pivot,(-63,28),f"170T-eq sector\npitch R {num(sector_r,1)}",BLUE)
    idler_note=(
        "LOWERED PURCHASED 30T WHEEL\nDIRECTLY DRIVES SECTOR"
        if direct else
        "PURCHASED WHEEL + PRINTED PINION\nCOAXIAL ON VERTICAL SHAFT"
    )
    leader(ax,idler,(34,-35),idler_note,PURPLE)
    leader(ax,worm,(64,34),"horizontal worm axis\n(plan projection)",ORANGE)
    ax.add_patch(FancyArrowPatch((worm[0]-2,-9),(idler[0]+7,-9),arrowstyle="-|>",mutation_scale=10,color=GREEN,lw=1.2))
    ax.add_patch(FancyArrowPatch((idler[0]-7,-9),(pivot[0]+18,-9),arrowstyle="-|>",mutation_scale=10,color=GREEN,lw=1.2))
    setup(ax,-78,82,-52,48)

    ax2=panel(fig,[0.65,0.52,0.285,0.35],"PURCHASED WORM WHEEL","ELEVATION")
    wheel_od=float(val("CAMERA_IDLER_OUTER_DIAMETER",16)); wheel_h=float(val("CAMERA_IDLER_TOTAL_HEIGHT",12)); tooth_h=float(val("CAMERA_IDLER_TOOTH_FACE_HEIGHT",6)); hub_h=float(val("CAMERA_IDLER_HUB_HEIGHT",6))
    ax2.add_patch(Rectangle((-wheel_od/2,0),wheel_od,tooth_h,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.2,hatch="///"))
    ax2.add_patch(Rectangle((-5,tooth_h),10,hub_h,facecolor="#d8b66a",edgecolor=INK,lw=1.0))
    dim_h(ax2,-wheel_od/2,wheel_od/2,-4,0,f"OD {num(wheel_od,1)}",ORANGE)
    dim_v(ax2,0,wheel_h,12,wheel_od/2,f"OVERALL {num(wheel_h,1)}",BLUE)
    dim_v(ax2,0,tooth_h,-12,-wheel_od/2,f"TEETH {num(tooth_h,1)}",ORANGE)
    ax2.text(0,15.8,f"30T, m{num(module,1)} | 4 mm bore | 10 mm hub",
             ha="center",va="center",fontsize=7.0,color=PURPLE,
             bbox=dict(boxstyle="round,pad=0.18",fc=WHITE,ec=PURPLE,lw=0.55))
    setup(ax2,-18,25,-7,19)

    if direct:
        ax3=panel(fig,[0.65,0.20,0.285,0.25],"DIRECT FACE ALIGNMENT","SECTION")
        bottom=float(val("BOTTOM_THICKNESS",3.2)); floor_clear=float(val("CAMERA_WORM_FLOOR_CLEARANCE",1.40))
        worm_outer=(float(val("CAMERA_WORM_DIAMETER_QUOTIENT",18))+2.0)*module/2.0
        mesh_z=bottom+floor_clear+worm_outer
        sector_face=float(val("CAMERA_GEAR_FACE_WIDTH",3.6)); tooth_h=float(val("CAMERA_IDLER_TOOTH_FACE_HEIGHT",6.0))
        sector_z0=mesh_z-sector_face/2; tooth_z0=mesh_z-tooth_h/2
        ax3.add_patch(Rectangle((-8,tooth_z0),16,tooth_h,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.1,hatch="///"))
        ax3.add_patch(Rectangle((8.5,sector_z0),8,sector_face,facecolor="#cce0ec",edgecolor=BLUE,lw=1.1))
        centerline(ax3,(-13,mesh_z),(21,mesh_z))
        dim_v(ax3,tooth_z0,tooth_z0+tooth_h,-14,-8,f"WHEEL BAND {num(tooth_h,1)}",ORANGE)
        dim_v(ax3,sector_z0,sector_z0+sector_face,21,16.5,f"SECTOR {num(sector_face,1)}",BLUE)
        leader(ax3,(0,mesh_z),(14,16),f"common center Z {num(mesh_z,2)}",PURPLE)
        setup(ax3,-19,25,3.5,18)
    else:
        ax3=panel(fig,[0.65,0.20,0.285,0.25],"PRINTED COAXIAL PINION","TOP")
        pinion_od=module*(pinion_teeth+2); d_bore=float(val("CAMERA_IDLER_PINION_SHAFT_BORE_DIAMETER",4.25)); flat=float(val("CAMERA_IDLER_PINION_SHAFT_FLAT_DEPTH",0.45))
        ax3.add_patch(Circle((0,0),pinion_od/2,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.2))
        ax3.add_patch(Circle((0,0),d_bore/2,facecolor=WHITE,edgecolor=INK,lw=0.8))
        ax3.add_patch(Rectangle((d_bore/2-flat,-d_bore/2),flat,d_bore,facecolor="#f3c7aa",edgecolor=RED,lw=0.8))
        dim_h(ax3,-pinion_od/2,pinion_od/2,-12,-pinion_od/2,f"TIP OD {num(pinion_od,1)}",ORANGE)
        leader(ax3,(d_bore/2-flat/2,0),(14,5),f"D-bore dia {num(d_bore,2)}\nflat depth {num(flat,2)}",RED)
        leader(ax3,(-3,5),(-14,12),f"printed {num(pinion_teeth,0)}T m{num(module,1)}",PURPLE)
        setup(ax3,-19,25,-16,17)

    note_box(fig,[0.065,0.18,0.27,0.15],"CENTER-DISTANCE FORMULAS",
             [f"worm-wheel = {num(worm_r,1)} + {num(wheel_r,1)} + {mm('CAMERA_WORM_IDLER_MESH_CENTER_CLEARANCE',0.28,2)} = {num(worm_cd,2)}",
              f"{sector_drive_label.lower()}-sector = {num(drive_r,1)} + {num(sector_r,1)} + {num(sector_clearance,2)} mm = {num(sector_cd,2)}",
              "Dimensions are pitch-center distances."],BLUE)
    ratio_lines=(
        [f"drive style = {val('CAMERA_IDLER_SECTOR_DRIVE_STYLE','purchased_wheel_direct')}",
         f"1-start worm -> purchased {num(wheel_teeth,0)}T wheel -> {num(sector_teeth,0)}T sector",
         "Overall nominal ratio remains 170:1.",
         "Prototype: hand-test the worm-wheel tooth helix against the spur sector."]
        if direct else
        [f"1-start worm -> {num(wheel_teeth,0)}T wheel -> {num(pinion_teeth,0)}T pinion -> {num(sector_teeth,0)}T sector",
         "30T wheel and 30T pinion are locked coaxially.",
         "Overall nominal ratio remains 170:1.",
         "File a matching 0.45 mm shallow flat on the 4 mm shaft."]
    )
    note_box(fig,[0.355,0.18,0.27,0.15],"RATIO / PHYSICAL FIT",ratio_lines,ORANGE)
    pdf.savefig(fig); plt.close(fig)


def page_idler_assembly(pdf):
    direct=direct_purchased_wheel_drive()
    fig=new_sheet(9,"VERTICAL IDLER JOURNALS & SUPPORT-FREE ASSEMBLY",
                  "The lowered direct-drive wheel is installed with the shaft before the removable two-arm M3 upper cap; a clamp collar retains the stack" if direct else
                  "A blind lower printed journal and removable two-arm M3 upper cap support the 4 mm vertical shaft; a clamp collar retains it")
    bore=float(val("CAMERA_IDLER_SHAFT_RUNNING_BORE_DIAMETER",4.24)); shaft=float(val("CAMERA_IDLER_SHAFT_DIAMETER",4.0))
    wheel_h=float(val("CAMERA_IDLER_TOTAL_HEIGHT",12)); pinion_h=float(val("CAMERA_IDLER_PINION_FACE_WIDTH",3.6)); cap_t=float(val("CAMERA_IDLER_CAP_THICKNESS",4)); collar_h=float(val("CAMERA_IDLER_SHAFT_TOP_COLLAR_HEIGHT",4))
    lower_gap=float(val("CAMERA_IDLER_LOWER_BUSHING_WHEEL_CLEARANCE",0.15)); wheel_gap=float(val("CAMERA_IDLER_PINION_WHEEL_GAP",0.15)); cap_gap=float(val("CAMERA_IDLER_CAP_WHEEL_CLEARANCE",0.40)); collar_gap=float(val("CAMERA_IDLER_SHAFT_TOP_COLLAR_CLEARANCE",0.15))
    bottom=float(val("BOTTOM_THICKNESS",3.2)); floor_clear=float(val("CAMERA_IDLER_SHAFT_FLOOR_CLEARANCE",0.40))
    module=float(val("CAMERA_GEAR_MODULE",0.5)); worm_floor=float(val("CAMERA_WORM_FLOOR_CLEARANCE",1.40))
    worm_outer=(float(val("CAMERA_WORM_DIAMETER_QUOTIENT",18))+2.0)*module/2.0
    mesh_z=bottom+worm_floor+worm_outer
    tooth_h=float(val("CAMERA_IDLER_TOOTH_FACE_HEIGHT",6.0)); hub_h=float(val("CAMERA_IDLER_HUB_HEIGHT",6.0))
    tooth_at_bottom=val("CAMERA_IDLER_TOOTH_BAND_POSITION","bottom")=="bottom"
    pinion_z0=mesh_z-pinion_h/2.0; pinion_z1=pinion_z0+pinion_h
    if direct:
        tooth_z0=mesh_z-tooth_h/2.0; tooth_z1=tooth_z0+tooth_h
        wheel_z0=tooth_z0 if tooth_at_bottom else tooth_z1-wheel_h
    else:
        wheel_z0=pinion_z1+wheel_gap
        tooth_z0=wheel_z0 if tooth_at_bottom else wheel_z0+wheel_h-tooth_h
        tooth_z1=tooth_z0+tooth_h
    wheel_z1=wheel_z0+wheel_h
    lower_rotating_z=wheel_z0 if direct else pinion_z0-float(val("CAMERA_IDLER_PINION_HUB_EXTENSION",0.5))
    lower_support_top=lower_rotating_z-lower_gap
    cap_z0=wheel_z1+cap_gap; cap_z1=cap_z0+cap_t
    collar_z0=cap_z1+collar_gap; collar_z1=collar_z0+collar_h

    ax=panel(fig,[0.065,0.39,0.45,0.48],"VERTICAL SHAFT STACK","SECTION")
    ax.add_patch(Rectangle((-34,0),68,bottom,facecolor="#cce0ec",edgecolor=BLUE,lw=1.0))
    ax.add_patch(Rectangle((-5,bottom),10,lower_support_top-bottom,facecolor="#cce0ec",edgecolor=BLUE,lw=1.0))
    ax.add_patch(Rectangle((-bore/2,floor_clear),bore,max(lower_support_top-floor_clear,0.01),
                           facecolor=WHITE,edgecolor=RED,lw=0.8))
    ax.add_patch(Rectangle((-shaft/2,floor_clear),shaft,collar_z1-floor_clear,facecolor="#9ba6ae",edgecolor=INK,lw=0.7))
    if not direct:
        ax.add_patch(Rectangle((-8,pinion_z0),16,pinion_h,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.0))
    # Draw the purchased wheel as a narrow hub plus its wider tooth band so
    # the direct-drive lowering and common sector/worm centerline are visible.
    ax.add_patch(Rectangle((-5,wheel_z0),10,wheel_h,facecolor="#d8b66a",edgecolor=INK,lw=1.0))
    ax.add_patch(Rectangle((-8,tooth_z0),16,tooth_h,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.0,hatch="///"))
    ax.add_patch(Rectangle((-17,cap_z0),34,cap_t,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.0))
    ax.add_patch(Rectangle((-bore/2,cap_z0),bore,cap_t,facecolor=WHITE,edgecolor=RED,lw=0.8))
    ax.add_patch(Rectangle((-4,collar_z0),8,collar_h,facecolor="#d8b66a",edgecolor=INK,lw=1.0))
    dim_v(ax,floor_clear,lower_support_top,28,5,f"BLIND BORE dia {num(bore,2)}",RED)
    if not direct:
        dim_v(ax,pinion_z0,pinion_z1,-25,-8,f"PINION {num(pinion_h,1)}",ORANGE)
    dim_v(ax,wheel_z0,wheel_z1,25,8,f"WHEEL {num(wheel_h,1)}",PURPLE)
    dim_v(ax,cap_z0,cap_z1,-25,-17,f"CAP {num(cap_t,1)}",ORANGE)
    dim_v(ax,collar_z0,collar_z1,15,4,f"COLLAR {num(collar_h,1)}",PURPLE)
    leader(ax,(0,(floor_clear+lower_support_top)/2),(-29,14),f"4 mm shaft in {num(bore,2)} printed journal",RED)
    leader(ax,(8,wheel_z0),(43,7),f"lower thrust gap {num(lower_gap,2)}",GREEN,"right")
    if direct:
        centerline(ax,(-12,mesh_z),(18,mesh_z))
        leader(ax,(8,mesh_z),(43,14),f"worm + sector center Z {num(mesh_z,2)}",GREEN,"right")
    else:
        leader(ax,(8,wheel_z0-0.08),(43,18),f"wheel/pinion gap {num(wheel_gap,2)}",GREEN,"right")
    setup(ax,-42,47,-1,max(collar_z1+4,33))

    ax2=panel(fig,[0.54,0.48,0.395,0.39],"REMOVABLE TWO-ARM UPPER CAP","TOP")
    offset=float(val("CAMERA_IDLER_CAP_POST_TANGENTIAL_OFFSET",14)); post_d=float(val("CAMERA_IDLER_CAP_POST_DIAMETER",10)); capw=float(val("CAMERA_IDLER_CAP_WIDTH",12)); armw=float(val("CAMERA_IDLER_CAP_ARM_WIDTH",6))
    ax2.add_patch(Circle((0,0),capw/2,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.1))
    for sign in (-1,1):
        ax2.add_patch(Rectangle((-armw/2,min(0,sign*offset)),armw,offset,facecolor="#f3c7aa",edgecolor=ORANGE,lw=0.9))
        ax2.add_patch(Circle((0,sign*offset),post_d/2,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.0))
        ax2.add_patch(Circle((0,sign*offset),float(val("CAMERA_IDLER_CAP_SCREW_CLEARANCE",3.4))/2,facecolor=WHITE,edgecolor=PURPLE,lw=0.8))
    ax2.add_patch(Circle((0,0),bore/2,facecolor=WHITE,edgecolor=RED,lw=1.0))
    dim_v(ax2,-offset,offset,13,post_d/2,f"POST CENTERS {num(2*offset,1)}",PURPLE)
    dim_h(ax2,-armw/2,armw/2,-6,-8,f"ARM {num(armw,1)}",ORANGE)
    leader(ax2,(0,offset),(18,18),f"M3 clearance {mm('CAMERA_IDLER_CAP_SCREW_CLEARANCE',3.4)}\nhead sink dia {mm('CAMERA_IDLER_CAP_SCREW_HEAD_DIAMETER',6.5)}",PURPLE)
    leader(ax2,(0,0),(-17,3),f"upper journal dia {num(bore,2)}",RED,"right")
    setup(ax2,-25,34,-24,26)

    note_box(fig,[0.54,0.30,0.395,0.12],"FIXED POSTS / INSERTS",
             [f"post OD = {mm('CAMERA_IDLER_CAP_POST_DIAMETER',10)}; insert pilot = {mm('CAMERA_IDLER_CAP_INSERT_HOLE_DIAMETER',4)} x {mm('CAMERA_IDLER_CAP_INSERT_DEPTH',5.5)} deep",
              f"blind-journal floor land above enclosure underside = {num(floor_clear,2)} mm",
              f"cap thickness = {num(cap_t,1)}; head sink = dia {mm('CAMERA_IDLER_CAP_SCREW_HEAD_DIAMETER',6.5)} x {mm('CAMERA_IDLER_CAP_SCREW_HEAD_DEPTH',2.4)} deep",
              f"wheel / tooth band Z = {num(wheel_z0,2)}-{num(wheel_z1,2)} / {num(tooth_z0,2)}-{num(tooth_z1,2)}",
              (f"direct root bridge >= {mm('CAMERA_IDLER_DIRECT_SECTOR_ROOT_BRIDGE_MIN_HEIGHT',3.20,2)} high x {mm('CAMERA_IDLER_DIRECT_SECTOR_RIM_MIN_RADIAL_WIDTH',3.00,2)} radial; pocket {mm('CAMERA_IDLER_DIRECT_LOWER_WHEEL_POCKET_CLEARANCE',0.15,2)} / floor land {mm('CAMERA_IDLER_DIRECT_LOWER_WHEEL_POCKET_MIN_ROOT_LAND',0.55,2)}" if direct else
               "legacy printed pinion sits above the carrier under-web"),
              f"top clamp collar = dia {mm('CAMERA_IDLER_SHAFT_TOP_COLLAR_DIAMETER',8)} x {num(collar_h,1)} high; cap clearance {num(collar_gap,2)}"],PURPLE)

    ax3=panel(fig,[0.065,0.12,0.87,0.15],"LID-OFF SUPPORT-FREE ASSEMBLY / REVERSE FOR SERVICE","ASSEMBLY")
    preassemble=("purchased wheel on bare\n4 mm shaft; no pinion" if direct else
                 "printed pinion + purchased\nwheel on bare 4 mm shaft")
    steps=[
        ("1","WORM FIRST","install worm/shaft and\ntwo split journal caps"),
        ("2","CARRIER","reverse path: upright at 72/12 mm;\n30 deg at 12/8, 15 deg at 5, seat"),
        ("3","PREASSEMBLE",preassemble),
        ("4","LOWER / MESH","stack into blind journal; turn\nworm/carrier to phase teeth"),
        ("5","RETAIN","M3 upper cap + top collar;\nhold-down, camera + lid"),
    ]
    for i,(number,verb,detail) in enumerate(steps):
        x=-92+i*46
        ax3.add_patch(FancyBboxPatch((x,-12),39,24,boxstyle="round,pad=0.4,rounding_size=2",
                                     facecolor=LIGHT,edgecolor=BLUE,lw=0.9))
        ax3.text(x+4,5,number,ha="center",va="center",fontsize=9,weight="bold",color=WHITE,
                 bbox=dict(boxstyle="circle,pad=0.25",fc=BLUE,ec=BLUE))
        ax3.text(x+10,6,verb,fontsize=7.4,weight="bold",color=BLUE,va="center")
        ax3.text(x+4,-1,detail,fontsize=6.2,color=INK,va="top")
        if i<4:
            ax3.add_patch(FancyArrowPatch((x+39,0),(x+45,0),arrowstyle="-|>",mutation_scale=8,color=GREEN,lw=1.0))
    setup(ax3,-98,138,-17,17)
    pdf.savefig(fig); plt.close(fig)


def page_carrier_guard(pdf):
    fig=new_sheet(10,"ROTATING CARRIER GUIDE & YAW-SAFE EYE GUARD",
                  "The final 14 mm carrier guides and compact front datum remain behind the assembled eye-rim guard through the full yaw sweep")
    guide_h=float(val("CAMERA_CARRIER_GUIDE_HEIGHT",14)); guide_t=float(val("CAMERA_CARRIER_GUIDE_THICKNESS",5)); front_w=float(val("CAMERA_CARRIER_FRONT_STOP_WIDTH",14)); margin=float(val("CAMERA_CARRIER_FRONT_STOP_EYE_GUARD_MARGIN",0.35)); yaw=float(val("ADJUSTABLE_CAMERA_YAW_RANGE_DEG",10))
    ax=panel(fig,[0.065,0.43,0.45,0.44],"GUIDE HEIGHT & CAMERA DATUM","SIDE")
    ax.add_patch(Rectangle((-44,0),88,3.2,facecolor="#cce0ec",edgecolor=BLUE,lw=1.0))
    ax.add_patch(Rectangle((-38,3.2),76,3.2,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.0))
    ax.add_patch(FancyBboxPatch((-35,6.4),70,51,boxstyle="round,pad=0,rounding_size=4",facecolor="#e1e5e8",edgecolor=INK,lw=1.0))
    for x in (-40,35):
        ax.add_patch(Rectangle((x,6.4),guide_t,guide_h,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.1))
    dim_v(ax,6.4,6.4+guide_h,-49,-40,f"FINAL GUIDE {num(guide_h,1)}",ORANGE)
    dim_h(ax,35,35+guide_t,1,6.4,f"THICK {num(guide_t,1)}",ORANGE)
    leader(ax,(-37.5,20),(-54,42),"guide top stops below\nexterior eye guard band",BLUE)
    leader(ax,(0,6.4),(31,-5),f"tray {mm('CAMERA_CARRIER_TRAY_THICKNESS',3.2)} thick",PURPLE)
    setup(ax,-60,62,-9,68)

    ax2=panel(fig,[0.54,0.43,0.395,0.44],"FRONT DATUM VS. EYE-RIM GUARD","NORMAL / SECTION")
    opening=float(val("EYE_OPENING_WIDTH",58)); guard=float(val("EYE_APERTURE_GUARD_BAND_OFFSET",0.75)); keep=float(val("EYE_INTERNAL_CUTTER_KEEP_OUT_MARGIN",0.35))
    ax2.add_patch(FancyBboxPatch((-32,-25),64,50,boxstyle="round,pad=0,rounding_size=11",facecolor="#cce0ec",edgecolor=BLUE,lw=1.2))
    ax2.add_patch(FancyBboxPatch((-opening/2,-23),opening,46,boxstyle="round,pad=0,rounding_size=10",facecolor=WHITE,edgecolor=ORANGE,lw=1.2))
    ax2.add_patch(FancyBboxPatch((-opening/2-guard,-23-guard),opening+2*guard,46+2*guard,boxstyle="round,pad=0,rounding_size=10.5",facecolor="none",edgecolor=RED,lw=1.0,ls="--"))
    ax2.add_patch(Rectangle((-front_w/2,-21),front_w,5,facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.0))
    dim_h(ax2,-front_w/2,front_w/2,-31,-21,f"FRONT DATUM WIDTH {num(front_w,1)}",ORANGE)
    dim_v(ax2,-23-guard,-23,39,32,f"GUARD OFFSET {num(guard,2)}",RED)
    leader(ax2,(front_w/2,-18),(40,-12),f"yaw-safe margin >= {num(margin,2)}",GREEN,"right")
    leader(ax2,(-29,-10),(-43,11),f"internal cutter keep-out {num(keep,2)}",RED)
    setup(ax2,-48,50,-38,38)

    ax3=panel(fig,[0.065,0.15,0.57,0.20],"FRONT DATUM THROUGH FULL YAW","TOP / PLAN")
    for angle,color,alpha in ((-yaw,GRAY,0.14),(0,ORANGE,0.22),(yaw,GRAY,0.14)):
        ax3.add_patch(Polygon(rotated_rect(0,0,45,72,angle),closed=True,facecolor=color,alpha=alpha,edgecolor=color,lw=0.9))
        rad=math.radians(angle)
        cx=-22*math.cos(rad); cy=-22*math.sin(rad)
        ax3.add_patch(Rectangle((cx-front_w/2,cy-2.5),front_w,5,angle=angle,rotation_point="center",facecolor="#f3c7aa",edgecolor=ORANGE,lw=0.8))
    ax3.plot([-31,-31],[-48,48],color=RED,lw=2.0,ls="--")
    ax3.text(-34,42,"EYE-RIM GUARD LIMIT",rotation=90,va="top",ha="right",color=RED,fontsize=7,weight="bold")
    ax3.add_patch(Arc((0,0),58,58,theta1=180-yaw,theta2=180+yaw,edgecolor=ORANGE,lw=1.1))
    ax3.text(-15,31,f"+/- {num(yaw,1)} deg sweep",color=ORANGE,fontsize=7.5,weight="bold")
    leader(ax3,(-22,0),(30,-35),"front datum is solved on flat body land\nand checked at every yaw sample",GREEN)
    setup(ax3,-48,55,-52,52)

    note_box(fig,[0.66,0.15,0.275,0.20],"GUARD / CHIMNEY LIMITS",
             [f"front-stop eye-guard margin = {num(margin,2)} mm",
              f"eye aperture guard-band offset = {num(guard,2)} mm",
              f"internal cutter keep-out = {num(keep,2)} mm",
              f"chimney wall guard = {mm('CAMERA_CARRIER_TOP_LOADING_CHIMNEY_WALL_GUARD',0.60,2)}",
              f"sweep-cut clearance = {mm('CAMERA_CARRIER_SWEEP_CUT_CLEARANCE',0.30,2)}",
              "Final mesh validation rejects any guard-band breach."],GREEN)
    pdf.savefig(fig); plt.close(fig)


def page_fans(pdf):
    fig=new_sheet(11,"REAR 40 mm FAN STATIONS",
                  "Two Noctua-style fans seat on 45 x 45 flats; each station may follow its rear-wall tangent")
    ax=panel(fig,[0.065,0.40,0.52,0.47],"PAD, OPENING & MOUNT PATTERN","REAR ELEVATION")
    pad=float(val("REAR_FAN_PAD_SIZE",45)); offset=float(val("REAR_FAN_CENTERLINE_OFFSET",50)); z=float(val("REAR_FAN_CENTER_Z",35)); spacing=float(val("REAR_FAN_MOUNT_SPACING",32)); opening=float(val("REAR_FAN_AIR_OPENING_DIAMETER",36))
    ax.add_patch(Rectangle((-90,0),180,76,facecolor="#edf4f7",edgecolor=BLUE,lw=1.1))
    for cy in (-offset,offset):
        ax.add_patch(Rectangle((cy-pad/2,z-pad/2),pad,pad,facecolor=WHITE,edgecolor=GREEN,lw=1.5))
        ax.add_patch(Circle((cy,z),opening/2,facecolor="#e6f4eb",edgecolor=GREEN,lw=1.2))
        for sx in (-1,1):
            for sz in (-1,1):
                ax.add_patch(Circle((cy+sx*spacing/2,z+sz*spacing/2),1.7,facecolor=WHITE,edgecolor=PURPLE,lw=0.8))
    centerline(ax,(-98,z),(98,z)); centerline(ax,(0,-7),(0,82))
    dim_h(ax,-offset,offset,72,z,f"CENTER-TO-CENTER {num(2*offset,1)}")
    dim_h(ax,-offset-pad/2,-offset+pad/2,-9,0,f"PAD {num(pad,1)}")
    dim_v(ax,z-pad/2,z+pad/2,-99,-offset-pad/2,f"PAD {num(pad,1)}")
    dim_h(ax,-offset-spacing/2,-offset+spacing/2,z+11,z,f"HOLES {num(spacing,1)}",PURPLE)
    leader(ax,(-offset+opening/2,z),(-18,11),f"air opening dia {num(opening,1)}",GREEN)
    leader(ax,(offset+spacing/2,z+spacing/2),(90,66),f"mount hole dia {mm('REAR_FAN_MOUNT_HOLE_DIAMETER',3.4)}",PURPLE,"right")
    setup(ax,-110,110,-18,88)

    ax2=panel(fig,[0.61,0.47,0.325,0.40],"LOCAL WALL ALIGNMENT","TOP / PLAN")
    wall=[(-42,-58),(-12,-63),(17,-61),(45,-51)]
    ax2.plot([p[0] for p in wall],[p[1] for p in wall],color=BLUE,lw=4,solid_capstyle="round")
    for x,y,ang in ((-27,-61,5),(31,-56,19)):
        ax2.add_patch(Polygon(rotated_rect(x,y+14,10,40,ang),closed=True,facecolor="#dcebdd",edgecolor=GREEN,lw=1.2))
        ax2.plot([x-26*math.sin(math.radians(ang)),x+26*math.sin(math.radians(ang))],
                 [y-26*math.cos(math.radians(ang)),y+26*math.cos(math.radians(ang))],color=ORANGE,lw=0.9,ls="--")
    leader(ax2,(31,-42),(7,2),"pad plane parallel to\nlocal rear-wall tangent",ORANGE)
    ax2.add_patch(FancyArrowPatch((-27,-42),(-27,22),arrowstyle="-|>",mutation_scale=10,color=GREEN,lw=1.2))
    ax2.text(-24,13,"intake",color=GREEN,fontsize=8)
    setup(ax2,-60,62,-75,32)

    note_box(fig,[0.065,0.18,0.25,0.15],"FAN ENVELOPE",
             [f"frame = {mm('REAR_FAN_FRAME_SIZE',40)} square",
              f"depth = {mm('REAR_FAN_DEPTH',10)}",
              f"hub dia = {mm('REAR_FAN_HUB_DIAMETER',20)}",
              f"body clearance = {mm('REAR_FAN_BODY_CLEARANCE',1)}"],GREEN)
    note_box(fig,[0.335,0.18,0.25,0.15],"PAD PLACEMENT",
             [f"pad inside = {val('REAR_FAN_PAD_INSIDE',True)} (default)",
              f"face outset = {mm('REAR_FAN_PAD_FACE_OUTSET',1.5)}",
              f"minimum pad gap = {mm('REAR_FAN_PAD_GAP',4)}",
              f"align to local wall = {val('REAR_FAN_ALIGN_TO_LOCAL_WALL',True)}"],BLUE)
    note_box(fig,[0.61,0.18,0.325,0.22],"COOLING VALIDATION",
             [f"airflow direction = {val('REAR_FAN_AIRFLOW_DIRECTION','intake')!r}",
              f"plume half-angle = {deg('CAMERA_COOLING_FAN_PLUME_HALF_ANGLE_DEG',14)}",
              f"minimum rear-face wash = {num(100*float(val('CAMERA_COOLING_MIN_REAR_FACE_WASH_RATIO',0.22)),0)}%",
              f"minimum exhaust/fan area = {num(100*float(val('CAMERA_COOLING_MIN_EXHAUST_TO_FAN_AREA_RATIO',0.75)),0)}%",
              "Offsets may be customized symmetrically or per fan with",
              "REAR_FAN_CENTER_TANGENTS."],GREEN)
    pdf.savefig(fig); plt.close(fig)


def page_acoustic(pdf):
    fig=new_sheet(12,"OPTIONAL BAFFLED ACOUSTIC CASSETTE",
                  "A removable tortuous-path cassette blocks direct fan-to-microphone line of sight; no separate microphone blocker is used")
    ax=panel(fig,[0.065,0.40,0.57,0.47],"DIVIDED INLETS, PLENUM, BAFFLES & OUTLETS","FLOW PLAN")
    # rear is right; cameras/front at left
    ax.add_patch(Rectangle((58,-65),14,130,facecolor="#dcebdd",edgecolor=GREEN,lw=1.2))
    for y in (-39,39):
        ax.add_patch(Rectangle((38,y-18),20,36,facecolor="#dbe8f3",edgecolor=BLUE,lw=1.0))
        ax.add_patch(FancyArrowPatch((72,y),(45,y),arrowstyle="-|>",mutation_scale=10,color=GREEN,lw=1.2))
    ax.add_patch(Rectangle((-28,-64),66,128,facecolor="#e8f0f6",edgecolor=BLUE,lw=1.2))
    # six alternating baffles: three per path
    for y0,sign in ((-52,1),(0,-1)):
        for i in range(3):
            x=24-i*20
            yy=y0+26
            if (i+sign)%2:
                ax.add_patch(FancyBboxPatch((x-2,yy-23),4,34,boxstyle="round,pad=0,rounding_size=2",
                                            facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.0))
            else:
                ax.add_patch(FancyBboxPatch((x-2,yy-11),4,34,boxstyle="round,pad=0,rounding_size=2",
                                            facecolor="#f3c7aa",edgecolor=ORANGE,lw=1.0))
    for y in (-36,36):
        path=[(38,y),(22,y+12),(5,y-10),(-13,y+10),(-40,y)]
        ax.add_patch(FancyArrowPatch(path=mpl.path.Path(path,[1,3,3,3,3]),arrowstyle="-|>",
                                     mutation_scale=10,color=GREEN,lw=1.5))
        ax.add_patch(Rectangle((-44,y-15),16,30,facecolor="#dcebdd",edgecolor=GREEN,lw=1.0))
    dim_h(ax,38,58,68,65,f"INLET DEPTH {mm('FAN_ACOUSTIC_DIVIDED_INLET_DEPTH',16)}")
    dim_h(ax,-28,38,-76,-64,f"PLENUM DEPTH\n{mm('FAN_ACOUSTIC_PLENUM_DEPTH',30)}")
    leader(ax,(2,-15),(-13,-56),f"six baffles; {mm('FAN_ACOUSTIC_BAFFLE_THICKNESS',2)} thick",ORANGE)
    leader(ax,(-36,36),(-76,60),f"broad outlet height {mm('FAN_ACOUSTIC_OUTLET_HEIGHT',41)}",GREEN)
    leader(ax,(24,54),(72,60),"direct acoustic line of sight blocked",RED,"right")
    setup(ax,-85,85,-88,88)

    ax2=panel(fig,[0.66,0.48,0.275,0.39],"REAR MIC — CAMERA BACK","")
    w=float(cam("BODY_WIDTH",78)); h=float(cam("BODY_HEIGHT",51)); inset=float(val("CAMERA_REAR_MIC_BACK_PANEL_EDGE_INSET",5))
    ax2.add_patch(FancyBboxPatch((-w/2,-h/2),w,h,boxstyle="round,pad=0,rounding_size=4",
                                 facecolor="#e1e5e8",edgecolor=INK,lw=1.2))
    ax2.add_patch(Rectangle((-29,-17),58,34,facecolor="#27323b",edgecolor=INK,lw=0.7))
    mic=(-w/2+inset,-h/2+inset)
    ax2.add_patch(Circle(mic,2.3,facecolor=RED,edgecolor=INK,lw=0.7))
    dim_h(ax2,-w/2,mic[0],-h/2-10,-h/2,f"INSET {num(inset,1)}",RED)
    dim_v(ax2,-h/2,mic[1],-w/2-10,-w/2,f"INSET {num(inset,1)}",RED)
    leader(ax2,mic,(5,-39),"rear mic: bottom-left\nwhen viewed from back",RED)
    ax2.text(0,33,"NO LOCAL BLOCKER",ha="center",color=BLUE,weight="bold",fontsize=8)
    setup(ax2,-57,58,-46,45)

    note_box(fig,[0.065,0.18,0.27,0.15],"CASSETTE GEOMETRY",
             [f"wall = {mm('FAN_ACOUSTIC_WALL_THICKNESS',2)}",
              f"baffle width / nose radius = {mm('FAN_ACOUSTIC_BAFFLE_WIDTH',34)} / {mm('FAN_ACOUSTIC_NOSE_RADIUS',5)}",
              f"fan gap = {mm('FAN_ACOUSTIC_FAN_GAP',8)}",
              f"side expansion = {mm('FAN_ACOUSTIC_PLENUM_SIDE_EXPANSION',10)}"],BLUE)
    note_box(fig,[0.355,0.18,0.28,0.15],"FLOW TARGETS",
             [f"minimum total throat = {num(val('FAN_ACOUSTIC_MIN_TOTAL_THROAT_AREA',1713),0)} mm2",
              f"minimum per path = {num(val('FAN_ACOUSTIC_MIN_PER_CAMERA_PATH_AREA',800),0)} mm2",
              f"maximum imbalance = {num(100*float(val('FAN_ACOUSTIC_MAX_PATH_IMBALANCE',0.20)),0)}%",
              f"outlet plume half-angle = {deg('FAN_ACOUSTIC_OUTLET_PLUME_HALF_ANGLE_DEG',8)}"],GREEN)
    note_box(fig,[0.66,0.18,0.275,0.23],"ACOUSTIC INTENT",
             ["The bottom-left microphone point is used for ray checks.",
              "Alternating rounded baffles prevent a straight fan-to-mic path.",
              "Broad side/bottom outlets retain cooling cross-section.",
              "The cassette is removable for service.",
              "No separate mic blocker/deflector is part of this design."],ORANGE)
    pdf.savefig(fig); plt.close(fig)


def page_nut(pdf):
    fig=new_sheet(13,"BOTTOM 1/4-INCH CAPTIVE-NUT MOUNT",
                  "A press-fit 1/4-20 hex nut loads from inside; six flexible ramped lips retain it after insertion")
    ax=panel(fig,[0.065,0.43,0.47,0.44],"AUTO-RESOLVED FLOOR LOCATION","BOTTOM / PLAN")
    depth=float(val("BODY_DEPTH",233.661)); width=float(val("BODY_WIDTH",180)); frac=float(val("BOTTOM_MOUNT_HOLE_FRONT_TO_BACK_FRACTION",0.5))
    outline=soft_triangle(depth,width,0.75,0.55)
    ax.add_patch(Polygon(outline,closed=True,facecolor="#edf4f7",edgecolor=BLUE,lw=1.3))
    x=-depth/2+frac*depth; y=float(val("BOTTOM_MOUNT_HOLE_LATERAL_TARGET",0))
    od=float(val("BOTTOM_MOUNT_NUT_HOLDER_OUTER_DIAMETER",24)); hole=float(val("BOTTOM_MOUNT_HOLE_DIAMETER",6.8))
    ax.add_patch(Circle((x,y),od/2,facecolor="#dcebdd",edgecolor=GREEN,lw=1.3))
    ax.add_patch(Circle((x,y),hole/2,facecolor=WHITE,edgecolor=INK,lw=1.0))
    centerline(ax,(-depth/2-8,0),(depth/2+8,0))
    dim_h(ax,-depth/2,x,-width/2-18,-width/2,f"PREFERRED STATION {num(frac*100,0)}% DEPTH")
    dim_v(ax,0,y+0.01,x+25,x,f"LATERAL TARGET {num(y,1)}")
    leader(ax,(x+od/2,y),(62,48),f"boss OD {num(od,1)}; through hole dia {num(hole,1)}",GREEN)
    setup(ax,-depth/2-25,depth/2+30,-width/2-28,width/2+28)

    ax2=panel(fig,[0.56,0.43,0.375,0.44],"CAPTIVE NUT + SNAP LIPS","SECTION / DETAIL")
    nut_af=float(val("BOTTOM_MOUNT_NUT_ACROSS_FLATS",11.11)); nut_t=float(val("BOTTOM_MOUNT_NUT_THICKNESS",5.56)); lip_h=float(val("BOTTOM_MOUNT_NUT_SNAP_LIP_HEIGHT",1.5)); lip_p=float(val("BOTTOM_MOUNT_NUT_SNAP_LIP_PROJECTION",0.4))
    ax2.add_patch(Rectangle((-od/2,0),od,15,facecolor="#ccebd7",edgecolor=GREEN,lw=1.2))
    ax2.add_patch(Rectangle((-nut_af/2,3.2),nut_af,nut_t,facecolor="#d8b66a",edgecolor=INK,lw=1.0,hatch="///"))
    ax2.add_patch(Rectangle((-hole/2,-2),hole,12,facecolor=WHITE,edgecolor=INK,lw=0.7))
    for sign in (-1,1):
        base=sign*nut_af/2
        pts=[(base,3.2+nut_t),(base+sign*(3.5),3.2+nut_t),(base+sign*(3.5),3.2+nut_t+lip_h),(base-sign*lip_p,3.2+nut_t+0.2)]
        ax2.add_patch(Polygon(pts,closed=True,facecolor="#f3c7aa",edgecolor=ORANGE,lw=0.9))
    dim_h(ax2,-nut_af/2,nut_af/2,-7,3.2,f"NUT AF {num(nut_af,2)}",ORANGE)
    dim_v(ax2,3.2,3.2+nut_t,17,nut_af/2,f"NUT {num(nut_t,2)}",ORANGE)
    dim_h(ax2,-od/2,od/2,19,15,f"HOLDER OD {num(od,1)}",GREEN)
    leader(ax2,(nut_af/2+1,3.2+nut_t+0.5),(19,15),
           f"snap lip {num(lip_h,1)} H\n{num(lip_p,1)} projection",ORANGE,"right")
    leader(ax2,(0,5),(-27,12),f"nominal thread dia {mm('BOTTOM_MOUNT_NUT_THREAD_DIAMETER',6.35,2)}",BLUE,"right")
    setup(ax2,-36,40,-12,26)

    note_box(fig,[0.065,0.18,0.285,0.17],"PLACEMENT SEARCH",
             [f"auto lateral = {val('BOTTOM_MOUNT_HOLE_AUTO_LATERAL',True)}",
              f"auto front/back = {val('BOTTOM_MOUNT_HOLE_AUTO_FRONT_TO_BACK',True)}",
              f"edge clearance = {mm('BOTTOM_MOUNT_HOLE_EDGE_CLEARANCE',3)}",
              f"keep-out clearance = {mm('BOTTOM_MOUNT_HOLE_KEEP_OUT_CLEARANCE',2)}",
              "Preferred 50% station remains if it clears all geometry."],BLUE)
    note_box(fig,[0.37,0.18,0.265,0.17],"PRESS FIT",
             [f"pocket interference = {mm('BOTTOM_MOUNT_NUT_PRESS_INTERFERENCE',0.15,2)}",
              f"minimum holder wall = {mm('BOTTOM_MOUNT_NUT_HOLDER_MIN_WALL',4)}",
              f"minimum seat width = {mm('BOTTOM_MOUNT_NUT_MIN_SEAT_WIDTH',2)}",
              f"nut thickness tolerance = {mm('BOTTOM_MOUNT_NUT_THICKNESS_TOLERANCE',0.3)}"],ORANGE)
    note_box(fig,[0.655,0.18,0.28,0.17],"RETENTION",
             ["Six independent flexible ramped lips permit top loading.",
              f"retention clearance = {mm('BOTTOM_MOUNT_NUT_SNAP_LIP_RETENTION_CLEARANCE',0.35,2)}",
              f"flex wall = {mm('BOTTOM_MOUNT_NUT_SNAP_FLEX_WALL_THICKNESS',0.8)}",
              "Measure the actual plated nut and calibrate press fit."],GREEN)
    pdf.savefig(fig); plt.close(fig)


def page_keystone(pdf):
    fig=new_sheet(14,"BOTTOM KEYSTONE SNAP SOCKETS",
                  "Three cartridges install from inside and finish flush with the exterior bottom face")
    ax=panel(fig,[0.065,0.43,0.47,0.44],"THREE-SOCKET CORNER CLUSTER","BOTTOM / PLAN")
    depth=190; width=145; outline=soft_triangle(depth,width,0.75,0.55)
    ax.add_patch(Polygon(outline,closed=True,facecolor="#edf4f7",edgecolor=BLUE,lw=1.3))
    count=int(val("BOTTOM_KEYSTONE_COUNT",3)); spacing=float(val("BOTTOM_KEYSTONE_CENTER_SPACING",30)); ox=float(val("BOTTOM_KEYSTONE_SOCKET_OUTER_X",17.7)); oy=float(val("BOTTOM_KEYSTONE_SOCKET_OUTER_Y",25))
    x=62; y0=50
    for i in range(count):
        y=y0-i*spacing
        ax.add_patch(Rectangle((x-ox/2,y-oy/2),ox,oy,facecolor="#e8dff3",edgecolor=PURPLE,lw=1.1))
        ax.add_patch(Rectangle((x-8.05,y-7.35),16.1,14.7,facecolor=WHITE,edgecolor=INK,lw=0.8))
        ax.text(x,y,str(i+1),ha="center",va="center",fontsize=7,color=PURPLE,weight="bold")
    dim_v(ax,y0-(count-1)*spacing,y0,90,x+ox/2,f"PITCH {num(spacing,1)}",PURPLE)
    dim_h(ax,x-ox/2,x+ox/2,-61,-55,f"SOCKET {num(ox,1)}")
    leader(ax,(x+ox/2,y0+oy/2),(17,75),f"rear/side insets {mm('BOTTOM_KEYSTONE_REAR_EDGE_INSET',10)} / {mm('BOTTOM_KEYSTONE_SIDE_EDGE_INSET',10)}",BLUE)
    setup(ax,-105,108,-85,85)

    ax2=panel(fig,[0.56,0.43,0.375,0.44],"SNAP SOCKET + FLUSH FACE","SECTION")
    sh=float(val("BOTTOM_KEYSTONE_SOCKET_HEIGHT",9.75)); recess=float(val("BOTTOM_KEYSTONE_FACE_RECESS_DEPTH",1.5)); body_h=float(val("BOTTOM_KEYSTONE_INTERNAL_BODY_HEIGHT",30))
    ax2.add_patch(Rectangle((-45,-4),90,4,facecolor="#cce0ec",edgecolor=BLUE,lw=1.1))
    ax2.add_patch(Rectangle((-ox/2,0),ox,sh,facecolor="#e8dff3",edgecolor=PURPLE,lw=1.1))
    ax2.add_patch(Rectangle((-11,sh),22,body_h,facecolor="#d9dde1",edgecolor=INK,lw=1.0))
    ax2.add_patch(Rectangle((-9.75,-recess),19.5,recess,facecolor=WHITE,edgecolor=PURPLE,lw=0.8))
    ax2.plot([-20,20],[0,0],color=ORANGE,lw=1.5)
    ax2.text(22,0,"Z = 0 exterior / flush",va="center",fontsize=7.7,color=ORANGE,weight="bold")
    dim_v(ax2,0,sh,-18,-ox/2,f"SOCKET H {num(sh,2)}",PURPLE)
    dim_v(ax2,-recess,0,17,10,f"RECESS {num(recess,1)}",PURPLE)
    dim_h(ax2,-11,11,sh+body_h+6,sh+body_h,f"BODY {mm('BOTTOM_KEYSTONE_INTERNAL_BODY_X',22)}")
    leader(ax2,(0,sh+8),(50,20),"cartridge inserted\nfrom enclosure interior",GREEN,"right")
    setup(ax2,-52,58,-10,50)

    ax3=panel(fig,[0.065,0.18,0.47,0.18],"SOCKET FACE GEOMETRY","BOTTOM")
    px=float(val("BOTTOM_KEYSTONE_FACE_POCKET_X",19.5)); py=float(val("BOTTOM_KEYSTONE_FACE_POCKET_Y",16.6)); cx=float(val("BOTTOM_KEYSTONE_CUTOUT_X",16.1)); cy=float(val("BOTTOM_KEYSTONE_CUTOUT_Y",14.7))
    ax3.add_patch(Rectangle((-px/2,-py/2),px,py,facecolor="#e8dff3",edgecolor=PURPLE,lw=1.1))
    ax3.add_patch(Rectangle((-cx/2,-cy/2),cx,cy,facecolor=WHITE,edgecolor=INK,lw=1.0))
    dim_h(ax3,-px/2,px/2,-14,-py/2,f"POCKET {num(px,1)}")
    dim_v(ax3,-py/2,py/2,15,px/2,f"POCKET {num(py,1)}")
    dim_h(ax3,-cx/2,cx/2,12,cy/2,f"CUTOUT {num(cx,1)}",PURPLE)
    setup(ax3,-24,28,-18,19)

    note_box(fig,[0.56,0.18,0.375,0.18],"REFERENCE SNAP SOCKET",
             [f"use reference STL = {val('BOTTOM_KEYSTONE_USE_REFERENCE_SNAP_SOCKET',True)}",
              f"outer = {mm('BOTTOM_KEYSTONE_SOCKET_OUTER_X',17.7)} x {mm('BOTTOM_KEYSTONE_SOCKET_OUTER_Y',25)}",
              f"inner clear = {mm('BOTTOM_KEYSTONE_SOCKET_INNER_CLEAR_X',14.7)} x {mm('BOTTOM_KEYSTONE_SOCKET_INNER_CLEAR_Y',22)}",
              f"row axis = {val('BOTTOM_KEYSTONE_ROW_AXIS','y')!r}; corner Y sign = {num(val('BOTTOM_KEYSTONE_CORNER_Y_SIGN',1),0)}",
              "Auto placement moves the cluster around protected keep-outs."],PURPLE)
    pdf.savefig(fig); plt.close(fig)


def page_index(pdf):
    fig=new_sheet(15,"MAJOR PARAMETER QUICK REFERENCE",
                  "Edit the CONFIG block near the top of hockeymom_3_cam_cover_original_style_blender.py; dimensions are millimeters")
    gear_module=float(val("CAMERA_GEAR_MODULE",0.5))
    direct=direct_purchased_wheel_drive()
    sector_radius=float(val("CAMERA_GEAR_EQUIVALENT_TEETH",170))*gear_module/2
    pinion_radius=float(val("CAMERA_IDLER_PINION_TEETH",30))*gear_module/2
    wheel_radius=float(val("CAMERA_IDLER_TEETH",30))*gear_module/2
    worm_radius=float(val("CAMERA_WORM_DIAMETER_QUOTIENT",18))*gear_module/2
    sector_center_distance=(
        sector_radius+(wheel_radius if direct else pinion_radius)
        +idler_sector_mesh_clearance()
    )
    worm_center_distance=(
        wheel_radius+worm_radius
        +float(val("CAMERA_WORM_IDLER_MESH_CENTER_CLEARANCE",0.28))
    )
    groups=[
        ("SHELL / TAPER",[
            ("BODY_WIDTH / BODY_DEPTH",f"{num(val('BODY_WIDTH',180),1)} / {num(val('BODY_DEPTH',233.661),3)}"),
            ("BODY_HEIGHT / BASE_HEIGHT",f"{num(val('BODY_HEIGHT',72.653),3)} / {num(val('BASE_HEIGHT',68),1)}"),
            ("FOOTPRINT_TRIANGULARITY",num(val('FOOTPRINT_TRIANGULARITY',0.68),2)),
            ("REAR_WIDTH_TAPER_SCALE",num(val('REAR_WIDTH_TAPER_SCALE',0.75),2)),
            ("REAR_*_TAPER_START_FRACTION",f"{num(val('REAR_WIDTH_TAPER_START_FRACTION',.55),2)} / {num(val('REAR_HEIGHT_TAPER_START_FRACTION',.88),2)}"),
            ("REAR_HEIGHT_REDUCTION",num(val('REAR_HEIGHT_REDUCTION',10),1)),
        ]),
        ("OPTICS / CAMERA",[
            ("CAMERA_HALF_ANGLE_DEG",num(val('CAMERA_HALF_ANGLE_DEG',35),1)),
            ("EYE_OPENING_WIDTH / HEIGHT",f"{num(val('EYE_OPENING_WIDTH',58),1)} / {num(val('EYE_OPENING_HEIGHT',46),1)}"),
            ("EYE_BEZEL_WIDTH / HEIGHT / DEPTH",f"{num(val('EYE_BEZEL_WIDTH',64),1)} / {num(val('EYE_BEZEL_HEIGHT',52),1)} / {num(val('EYE_BEZEL_DEPTH',5),1)}"),
            ("FORWARD MODE / FIXED INDEP. / ADJ. OFFSET",f"{val('CAMERA_FORWARD_PLACEMENT_MODE','maximize')} / {val('CAMERA_FIXED_INDEPENDENT_FORWARD_ADVANCE_ENABLED',True)} / {num(val('ADJUSTABLE_EYE_FORWARD_CLEARANCE_OFFSET',1.7),2)}"),
            ("EYE REAR RELIEF / RETAINED LIP",f"{num(val('EYE_ADJUSTABLE_BODY_RELIEF_DEPTH',2),1)} / {num(val('EYE_BEZEL_DEPTH',5)-val('EYE_ADJUSTABLE_BODY_RELIEF_DEPTH',2),1)}"),
            ("FLOOR GAP / EYE WEB / FRONT DATUM",f"{num(val('CAMERA_FLOOR_CLEARANCE',4.5),1)} / {num(val('EYE_RECESS_BASE_SUPPORTED_WEB_WIDTH',6),1)} / {num(val('CAMERA_FRONT_STOP_FLOOR_DATUM_WIDTH',8),1)}"),
        ]),
        ("LID / RETENTION",[
            ("LID_THICKNESS",num(val('LID_THICKNESS',4.653),3)),
            ("LID_LIP_DEPTH / THICKNESS / CLEARANCE",f"{num(val('LID_LIP_DEPTH',3),1)} / {num(val('LID_LIP_THICKNESS',1.8),1)} / {num(val('LID_LIP_CLEARANCE',.3),2)}"),
            ("FASTENER_POST_DIAMETER",num(val('FASTENER_POST_DIAMETER',10.5),1)),
            ("HEAT_INSERT_HOLE_DIAMETER / DEPTH",f"{num(val('HEAT_INSERT_HOLE_DIAMETER',4),1)} / {num(val('HEAT_INSERT_HOLE_DEPTH',15.5),1)}"),
            ("LID_SCREW_CLEARANCE_DIAMETER",num(val('LID_SCREW_CLEARANCE_DIAMETER',3.4),1)),
            ("LID_SCREW_HEAD_COUNTERBORE_*",f"dia {num(val('LID_SCREW_HEAD_COUNTERBORE_DIAMETER',6.2),1)} x {num(val('LID_SCREW_HEAD_COUNTERBORE_DEPTH',3.3),1)} deep"),
        ]),
        ("DRIVETRAIN / CARRIER",[
            ("CAMERA_CARTRIDGE_WORM_ENABLED",str(val('CAMERA_CARTRIDGE_WORM_ENABLED',True))),
            ("IDLER SECTOR DRIVE STYLE",str(val('CAMERA_IDLER_SECTOR_DRIVE_STYLE','purchased_wheel_direct')).replace('_',' ')),
            ("WORM OD / L / THREAD / HUB",f"{num(val('CAMERA_WORM_PLAIN_HUB_DIAMETER',10),1)} / {num(val('CAMERA_WORM_LENGTH',20),1)} / {num(val('CAMERA_WORM_THREADED_LENGTH',15),1)} / {num(val('CAMERA_WORM_PLAIN_HUB_LENGTH',5),1)}"),
            ("H / V JOURNAL BORES",f"{num(val('CAMERA_WORM_PLAIN_BUSHING_BORE_DIAMETER',4.24),2)} / {num(val('CAMERA_IDLER_SHAFT_RUNNING_BORE_DIAMETER',4.24),2)}"),
            (f"WORM-WHEEL / {'WHEEL' if direct else 'PINION'}-SECTOR C.D.",f"{num(worm_center_distance,2)} / {num(sector_center_distance,2)}"),
            (("STAGES: START / WHEEL / SECTOR" if direct else "STAGES: START / WHEEL / PINION / SECTOR"),
             (f"{num(val('CAMERA_WORM_STARTS',1),0)} / {num(val('CAMERA_IDLER_TEETH',30),0)} / {num(val('CAMERA_GEAR_EQUIVALENT_TEETH',170),0)}" if direct else
              f"{num(val('CAMERA_WORM_STARTS',1),0)} / {num(val('CAMERA_IDLER_TEETH',30),0)} / {num(val('CAMERA_IDLER_PINION_TEETH',30),0)} / {num(val('CAMERA_GEAR_EQUIVALENT_TEETH',170),0)}")),
            ("GUIDE H / EYE-GUARD MARGIN",f"{num(val('CAMERA_CARRIER_GUIDE_HEIGHT',14),1)} / {num(val('CAMERA_CARRIER_FRONT_STOP_EYE_GUARD_MARGIN',0.35),2)}"),
        ]),
        ("FANS / ACOUSTICS",[
            ("REAR_FAN_PAD_SIZE / FRAME_SIZE",f"{num(val('REAR_FAN_PAD_SIZE',45),1)} / {num(val('REAR_FAN_FRAME_SIZE',40),1)}"),
            ("REAR_FAN_CENTERLINE_OFFSET / CENTER_Z",f"{num(val('REAR_FAN_CENTERLINE_OFFSET',50),1)} / {num(val('REAR_FAN_CENTER_Z',35),1)}"),
            ("REAR_FAN_MOUNT_SPACING / OPENING_DIAMETER",f"{num(val('REAR_FAN_MOUNT_SPACING',32),1)} / {num(val('REAR_FAN_AIR_OPENING_DIAMETER',36),1)}"),
            ("REAR_FAN_PAD_INSIDE / ALIGN_TO_LOCAL_WALL",f"{val('REAR_FAN_PAD_INSIDE',True)} / {val('REAR_FAN_ALIGN_TO_LOCAL_WALL',True)}"),
            ("FAN_ACOUSTIC_ATTENUATOR_ENABLED",str(val('FAN_ACOUSTIC_ATTENUATOR_ENABLED',False))),
            ("BAFFLE THICKNESS / WIDTH / OUTLET HEIGHT",f"{num(val('FAN_ACOUSTIC_BAFFLE_THICKNESS',2),1)} / {num(val('FAN_ACOUSTIC_BAFFLE_WIDTH',34),1)} / {num(val('FAN_ACOUSTIC_OUTLET_HEIGHT',41),1)}"),
        ]),
        ("BOTTOM INTERFACES",[
            ("BOTTOM_MOUNT_HOLE_FRONT_TO_BACK_FRACTION",num(val('BOTTOM_MOUNT_HOLE_FRONT_TO_BACK_FRACTION',.5),2)),
            ("BOTTOM_MOUNT_HOLE_DIAMETER",num(val('BOTTOM_MOUNT_HOLE_DIAMETER',6.8),1)),
            ("NUT THREAD / AF / THICKNESS",f"{num(val('BOTTOM_MOUNT_NUT_THREAD_DIAMETER',6.35),2)} / {num(val('BOTTOM_MOUNT_NUT_ACROSS_FLATS',11.11),2)} / {num(val('BOTTOM_MOUNT_NUT_THICKNESS',5.56),2)}"),
            ("BOTTOM_KEYSTONE_COUNT",num(val('BOTTOM_KEYSTONE_COUNT',3),0)),
            ("KEYSTONE SOCKET OUTER X / Y / H",f"{num(val('BOTTOM_KEYSTONE_SOCKET_OUTER_X',17.7),1)} / {num(val('BOTTOM_KEYSTONE_SOCKET_OUTER_Y',25),1)} / {num(val('BOTTOM_KEYSTONE_SOCKET_HEIGHT',9.75),2)}"),
            ("BOTTOM_KEYSTONE_CENTER_SPACING",num(val('BOTTOM_KEYSTONE_CENTER_SPACING',30),1)),
        ]),
    ]
    positions=[(0.065,0.58),(0.365,0.58),(0.665,0.58),(0.065,0.245),(0.365,0.245),(0.665,0.245)]
    for (title,rows),(x,y) in zip(groups,positions):
        ax=fig.add_axes([x,y,0.27,0.285]); ax.axis("off")
        ax.add_patch(FancyBboxPatch((0,0),1,1,boxstyle="round,pad=0.012,rounding_size=0.02",
                                    transform=ax.transAxes,facecolor="#fbfdfe",edgecolor=GRID,lw=0.9))
        ax.add_patch(Rectangle((0,0.86),1,0.14,transform=ax.transAxes,facecolor=BLUE,edgecolor="none"))
        ax.text(0.04,0.93,title,transform=ax.transAxes,va="center",fontsize=8.2,weight="bold",color=WHITE)
        yy=0.79
        for name,value in rows:
            ax.text(0.04,yy,name,transform=ax.transAxes,fontsize=5.9,color=GRAY,va="center")
            ax.text(0.96,yy,value,transform=ax.transAxes,fontsize=6.7,color=INK,ha="right",va="center",weight="bold")
            ax.plot([0.04,0.96],[yy-0.055,yy-0.055],transform=ax.transAxes,color=GRID,lw=0.45)
            yy-=0.123
    fig.text(0.065,0.165,"KEY ENABLE SWITCHES",fontsize=8.5,weight="bold",color=INK)
    switches=[
        ("EYE_TOP_LOADING_ENABLED",val("EYE_TOP_LOADING_ENABLED",True)),
        ("CAMERA_CRADLES_ENABLED",val("CAMERA_CRADLES_ENABLED",True)),
        ("CAMERA_BRACKETS_ENABLED",val("CAMERA_BRACKETS_ENABLED",True)),
        ("CAMERA_USB_CASE_OPENINGS_ENABLED",val("CAMERA_USB_CASE_OPENINGS_ENABLED",False)),
        ("REAR_FANS_ENABLED",val("REAR_FANS_ENABLED",True)),
        ("CAMERA_WORM_BEARINGS_ENABLED",val("CAMERA_WORM_BEARINGS_ENABLED",False)),
        ("CAMERA_IDLER_BEARINGS_ENABLED",val("CAMERA_IDLER_BEARINGS_ENABLED",False)),
        ("EYE_RECESS_BASE_SUPPORTED_WEB_ENABLED",val("EYE_RECESS_BASE_SUPPORTED_WEB_ENABLED",True)),
        ("BOTTOM_MOUNT_NUT_HOLDER_ENABLED",val("BOTTOM_MOUNT_NUT_HOLDER_ENABLED",True)),
        ("BOTTOM_KEYSTONES_ENABLED",val("BOTTOM_KEYSTONES_ENABLED",True)),
    ]
    switch_positions = [
        (0.055, 0.145), (0.235, 0.145), (0.415, 0.145), (0.595, 0.145), (0.775, 0.145),
        (0.055, 0.108), (0.235, 0.108), (0.415, 0.108), (0.595, 0.108), (0.775, 0.108),
    ]
    for (name,state),(x,y) in zip(switches,switch_positions):
        color=GREEN if state else GRAY
        fig.text(x,y,"ON" if state else "OFF",fontsize=6.7,weight="bold",color=WHITE,
                 bbox=dict(boxstyle="round,pad=0.22",fc=color,ec=color))
        fig.text(x+0.032,y,name,fontsize=4.9,color=INK)
    pdf.savefig(fig); plt.close(fig)


def main():
    with PdfPages(OUTPUT_PDF, metadata={
        "Title":"Hockeymom Dual-Camera Enclosure Configuration Dimension Guide",
        "Author":"Generated from hockeymom_3_cam_cover_original_style_blender.py",
        "Subject":"Parametric configuration engineering diagrams",
        "Keywords":"Hockeymom GoPro MISSION 1 CAD dimensions configuration",
    }) as pdf:
        for build_page in (
            page_cover,page_body,page_optics,page_vertical,page_lid,page_retention,
            page_worm,page_idler_gears,page_idler_assembly,page_carrier_guard,
            page_fans,page_acoustic,page_nut,page_keystone,page_index,
        ):
            build_page(pdf)
    print(f"Wrote {OUTPUT_PDF}")


if __name__ == "__main__":
    main()
