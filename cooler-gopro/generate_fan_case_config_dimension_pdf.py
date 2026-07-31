#!/usr/bin/env python3
"""Generate CAD-style configuration drawings for the GoPro fan case.

The script reads configurable values from
``gopro_fan_case_parametric_blender.py`` without importing Blender.  The
drawings are explanatory, not manufacturing drawings, and are marked NTS.

Run with a Python that has matplotlib, for example::

    python3 generate_fan_case_config_dimension_pdf.py
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import math
import re
import tempfile
import textwrap
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle


HERE = Path(__file__).absolute().parent
MODEL_SOURCE = HERE / "gopro_fan_case_parametric_blender.py"
OUTPUT_PDF = HERE / "gopro_fan_case_configuration_dimensions.pdf"

mpl.rcParams["pdf.compression"] = 0
warnings.filterwarnings("ignore", message="Ignoring fixed .* limits.*")

INK = "#142435"
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
    if isinstance(node, ast.Dict):
        result = {}
        for key_node, value_node in zip(node.keys, node.values):
            value = _safe_value(value_node, env)
            if key_node is None:
                result.update(value)
            else:
                result[_safe_value(key_node, env)] = value
        return result
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


def _assignment_target_names(target: ast.AST) -> tuple[str, ...]:
    if isinstance(target, ast.Name):
        return (target.id,)
    if isinstance(target, (ast.Tuple, ast.List)):
        return tuple(
            name
            for element in target.elts
            for name in _assignment_target_names(element)
        )
    if isinstance(target, ast.Starred):
        return _assignment_target_names(target.value)
    return ()


def _supported_top_level_assignments(
    tree: ast.Module,
    path: Path,
) -> tuple[tuple[str, ast.AST, int], ...]:
    supported = []
    unsupported: dict[str, int] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            if len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
                supported.append((statement.targets[0].id, statement.value, statement.lineno))
                continue
            targets = statement.targets
        elif isinstance(statement, ast.AnnAssign):
            if isinstance(statement.target, ast.Name) and statement.value is not None:
                supported.append((statement.target.id, statement.value, statement.lineno))
                continue
            targets = (statement.target,)
        elif isinstance(statement, ast.AugAssign):
            targets = (statement.target,)
        else:
            continue

        for target in targets:
            for name in _assignment_target_names(target):
                if name.isupper() and not name.startswith("_"):
                    unsupported[name] = statement.lineno

    if unsupported:
        details = ", ".join(
            f"{name} (line {line})" for name, line in sorted(unsupported.items())
        )
        raise RuntimeError(
            f"Unsupported top-level uppercase assignment form in {path}: {details}"
        )
    return tuple(supported)


def _assignment_comment(source_lines: list[str], line_number: int) -> str:
    comments = []
    assignment_line = source_lines[line_number - 1]
    if "#" in assignment_line:
        inline = assignment_line.split("#", 1)[1].strip()
        if inline:
            comments.append(inline)

    index = line_number - 2
    while index >= 0:
        stripped = source_lines[index].strip()
        if not stripped:
            break
        if not stripped.startswith("#"):
            break
        comment = stripped.lstrip("#").strip()
        if comment and not set(comment) <= {"-"}:
            comments.insert(0, comment)
        index -= 1

    compact = " ".join(comments)
    compact = re.sub(r"\s+", " ", compact).strip()
    return compact


def read_assignments(path: Path):
    source_text = path.read_text(encoding="utf-8")
    source_lines = source_text.splitlines()
    tree = ast.parse(source_text, filename=str(path))
    values: dict[str, object] = {}
    lines: dict[str, int] = {}
    descriptions: dict[str, str] = {}
    unresolved: dict[str, int] = {}

    for name, expression, line in _supported_top_level_assignments(tree, path):
        lines[name] = line
        descriptions[name] = _assignment_comment(source_lines, line)
        try:
            value = _safe_value(expression, values)
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            unresolved[name] = line
            continue
        values[name] = value

    return values, lines, descriptions, unresolved


RAW_VALUES, CONFIG_LINES, CONFIG_DESCRIPTIONS, UNRESOLVED = read_assignments(MODEL_SOURCE)
IGNORED_UNRESOLVED = set()
unexpected_unresolved = {
    name: line
    for name, line in UNRESOLVED.items()
    if name.isupper() and not name.startswith("_") and name not in IGNORED_UNRESOLVED
}
if unexpected_unresolved:
    raise RuntimeError(
        "Unsupported uppercase configuration assignments require safe parsing "
        f"or explicit classification: {unexpected_unresolved}"
    )


def selected_values() -> tuple[dict[str, object], dict[str, str]]:
    values = dict(RAW_VALUES)
    overrides: dict[str, str] = {}
    material_mode = values.get("MATERIAL_MODE")
    profiles = values.get("MATERIAL_PROFILES")
    if isinstance(material_mode, str) and isinstance(profiles, dict):
        profile = profiles.get(material_mode)
        if isinstance(profile, dict):
            for name, value in profile.items():
                if name in values:
                    values[name] = value
                    overrides[name] = f"MATERIAL_MODE={material_mode}"
    return values, overrides


C, PROFILE_OVERRIDES = selected_values()


SOURCE_HASH = hashlib.sha256(
    MODEL_SOURCE.read_bytes() + Path(__file__).read_bytes()
).hexdigest()[:16]


@dataclass(frozen=True)
class ConfigEntry:
    name: str
    value: object
    line: int
    group: str
    kind: str
    description: str
    dimensional: bool
    override: str = ""


GROUP_RULES = (
    ("Back shell", ("BACK_OUTER", "BACK_DEPTH", "BACK_CORNER", "BACK_FACE", "BACK_SOCKET")),
    ("Back dome", ("BACK_DOME",)),
    ("Insert capture slot", ("INSERT_SOCKET_SLOT", "FIT_CLEARANCE", "INSERTION_DEPTH")),
    ("Fan and vent", ("FAN_", "VENT_")),
    ("Case fasteners", ("CASE_FASTENER", "BACK_FASTENER", "INSERT_FASTENER", "FASTENER_BOSS")),
    ("Camera stops", ("CAMERA_STOP",)),
    ("Insert sleeve", ("INSERT_FRONT", "INSERT_REAR", "INSERT_DEPTH", "INSERT_OUTER", "INSERT_WALL")),
    ("Insert openings", ("BOTTOM_", "LEFT_", "RIGHT_", "TOP_")),
    ("Interior rails", ("LOCATING_", "LENS_")),
    ("Snap retention", ("SNAP_",)),
    ("Mesh/export settings", ("CLEAR_SCENE", "LAYOUT_", "PRINT_BED", "SHOW_", "EXPORT_", "COMBINED_", "BACK_STL", "INSERT_STL", "CYLINDER_", "CORNER_", "BOOLEAN_", "WATERTIGHT_")),
    ("Material and colors", ("MATERIAL_", "BACK_COLOR", "INSERT_COLOR")),
)

SKIP_CONFIG_NAMES = {"MATERIAL_PROFILES"}
NON_DIMENSIONAL_TOKENS = (
    "ENABLED",
    "SHOW",
    "EXPORT",
    "NAME",
    "MODE",
    "SOLVER",
    "SEGMENTS",
    "SECTIONS",
    "COUNT",
    "LOOP_POINTS",
    "COLOR",
    "CLEAR_SCENE",
    "LAYOUT",
)
DIMENSIONAL_TOKENS = (
    "WIDTH",
    "HEIGHT",
    "DEPTH",
    "DIAMETER",
    "RADIUS",
    "THICKNESS",
    "CLEARANCE",
    "SPACING",
    "OFFSET",
    "GAP",
    "POSITION",
    "POSITIONS",
    "PROTRUSION",
    "BEVEL",
    "LENGTH",
    "ANGLE",
    "SPECS",
    "TAPERS",
    "OVERLAP",
    "DISTANCE",
    "VOLUME",
)


def classify_group(name: str) -> str:
    for group, prefixes in GROUP_RULES:
        if any(name.startswith(prefix) for prefix in prefixes):
            return group
    return "Other configuration"


def contains_number(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, dict):
        return any(contains_number(item) for item in value.values())
    if isinstance(value, (tuple, list)):
        return any(contains_number(item) for item in value)
    return False


def humanize(name: str) -> str:
    return name.lower().replace("_", " ")


def is_dimensional(name: str, value: object) -> bool:
    if name in SKIP_CONFIG_NAMES or name.startswith("_"):
        return False
    if not contains_number(value):
        return False
    if any(token in name for token in DIMENSIONAL_TOKENS):
        return not name.endswith("COLOR")
    if any(token in name for token in NON_DIMENSIONAL_TOKENS):
        return False
    return isinstance(value, (int, float, tuple, list, dict))


def infer_kind(name: str, dimensional: bool) -> str:
    if not dimensional:
        return "build/display setting"
    if "ANGLE" in name:
        return "angular dimension"
    if "DIAMETER" in name:
        return "diameter"
    if "RADIUS" in name:
        return "radius"
    if "POSITIONS" in name or name.endswith("_XZ") or name.endswith("_SPECS"):
        return "coordinate table"
    if "VOLUME" in name:
        return "volume threshold"
    if any(token in name for token in ("WIDTH", "HEIGHT", "DEPTH", "THICKNESS", "CLEARANCE", "SPACING", "OFFSET", "GAP", "PROTRUSION", "BEVEL", "LENGTH", "OVERLAP")):
        return "linear dimension"
    return "numeric dimension"


def format_value(value: object, max_length: int = 82) -> str:
    def scalar(item: object) -> str:
        if isinstance(item, float):
            return f"{item:.4g}"
        return repr(item)

    if isinstance(value, (int, float, bool, str)) or value is None:
        text = scalar(value)
    elif isinstance(value, dict):
        parts = [f"{key}: {format_value(val, 32)}" for key, val in value.items()]
        text = "{" + ", ".join(parts) + "}"
    elif isinstance(value, (tuple, list)):
        parts = [format_value(item, 28) for item in value]
        text = "(" + ", ".join(parts) + (")" if isinstance(value, tuple) else "]")
        if isinstance(value, list):
            text = "[" + ", ".join(parts) + "]"
    else:
        text = repr(value)

    if len(text) > max_length:
        return text[: max_length - 3] + "..."
    return text


def build_entries() -> tuple[tuple[ConfigEntry, ...], tuple[ConfigEntry, ...]]:
    entries = []
    for name, value in sorted(C.items(), key=lambda item: CONFIG_LINES.get(item[0], 0)):
        if name in SKIP_CONFIG_NAMES or name.startswith("_"):
            continue
        dimensional = is_dimensional(name, value)
        description = CONFIG_DESCRIPTIONS.get(name) or humanize(name)
        override = PROFILE_OVERRIDES.get(name, "")
        if override:
            description = f"{description} Selected profile override: {override}."
        entries.append(
            ConfigEntry(
                name=name,
                value=value,
                line=CONFIG_LINES.get(name, 0),
                group=classify_group(name),
                kind=infer_kind(name, dimensional),
                description=description,
                dimensional=dimensional,
                override=override,
            )
        )
    dimensions = tuple(entry for entry in entries if entry.dimensional)
    settings = tuple(entry for entry in entries if not entry.dimensional)
    return dimensions, settings


DIMENSION_ENTRIES, SETTING_ENTRIES = build_entries()
INVENTORY_ROWS_PER_PAGE = 8
DIMENSION_INVENTORY_PAGES = math.ceil(len(DIMENSION_ENTRIES) / INVENTORY_ROWS_PER_PAGE)
SETTING_INVENTORY_PAGES = math.ceil(len(SETTING_ENTRIES) / INVENTORY_ROWS_PER_PAGE)
CURATED_PAGE_COUNT = 5
TOTAL_SHEETS = 1 + CURATED_PAGE_COUNT + DIMENSION_INVENTORY_PAGES + SETTING_INVENTORY_PAGES + 1
CURRENT_SHEET = 0


def mm(name: str) -> float:
    return float(C[name])


def rounded_box(ax, cx, cz, width, height, radius, edge, face, lw=1.2, ls="-", alpha=1.0):
    patch = FancyBboxPatch(
        (cx - width / 2.0, cz - height / 2.0),
        width,
        height,
        boxstyle=f"round,pad=0,rounding_size={min(radius, width / 2.0, height / 2.0)}",
        linewidth=lw,
        linestyle=ls,
        edgecolor=edge,
        facecolor=face,
        alpha=alpha,
    )
    ax.add_patch(patch)
    return patch


def arrow(ax, start, end, label, color=BLUE, text_offset=(0.0, 0.0), size=8):
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={"arrowstyle": "<->", "color": color, "lw": 1.0, "shrinkA": 0, "shrinkB": 0},
    )
    tx = (start[0] + end[0]) / 2.0 + text_offset[0]
    ty = (start[1] + end[1]) / 2.0 + text_offset[1]
    ax.text(tx, ty, label, color=color, fontsize=size, ha="center", va="center")


def setup_ax(fig, rect, xlim, ylim, title):
    ax = fig.add_axes(rect)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")
    ax.text(0.0, 1.015, title, transform=ax.transAxes, fontsize=11, weight="bold", color=INK)
    return ax


def new_page(title: str, subtitle: str):
    fig = plt.figure(figsize=(11, 8.5))
    fig.patch.set_facecolor(WHITE)
    fig.text(0.055, 0.95, title, fontsize=18, weight="bold", color=INK)
    fig.text(0.055, 0.918, subtitle, fontsize=9.5, color=GRAY)
    fig.text(0.055, 0.055, "NTS schematic drawings. Dimensions are driven by source variables.", fontsize=7.5, color=GRAY)
    fig.text(0.56, 0.055, f"source-{SOURCE_HASH}", fontsize=7.5, color=GRAY)
    fig.text(0.925, 0.055, f"p.{CURRENT_SHEET + 1}/{TOTAL_SHEETS}", fontsize=7.5, color=GRAY, ha="right")
    return fig


def save_page(pdf, fig):
    global CURRENT_SHEET
    CURRENT_SHEET += 1
    pdf.savefig(fig)
    plt.close(fig)


def page_title(pdf):
    fig = new_page(
        "GoPro Fan Case Configuration Dimension Guide",
        "Back shell, insert sleeve, TPU capture slot, fasteners, ports, snap features and generated inventory.",
    )
    ax = setup_ax(fig, [0.07, 0.19, 0.48, 0.62], (-55, 55), (-40, 40), "Rear shell XZ reference")
    rounded_box(ax, 0, 0, mm("BACK_OUTER_WIDTH"), mm("BACK_OUTER_HEIGHT"), mm("BACK_CORNER_RADIUS"), BLUE, LIGHT, 1.8)
    rounded_box(ax, 0, 0, mm("INSERT_FRONT_WIDTH") + 2 * mm("FIT_CLEARANCE_X"), mm("INSERT_FRONT_HEIGHT") + 2 * mm("FIT_CLEARANCE_Z"), mm("INSERT_OUTER_CORNER_RADIUS") + max(mm("FIT_CLEARANCE_X"), mm("FIT_CLEARANCE_Z")), PURPLE, WHITE, 1.5, "--")
    rounded_box(ax, 0, 0, mm("INSERT_FRONT_WIDTH") - 2 * mm("INSERT_WALL_X") - 2 * mm("INSERT_SOCKET_SLOT_INNER_CLEARANCE") - 2 * mm("INSERT_SOCKET_SLOT_EDGE_THICKNESS"), mm("INSERT_FRONT_HEIGHT") - 2 * mm("INSERT_WALL_Z") - 2 * mm("INSERT_SOCKET_SLOT_INNER_CLEARANCE") - 2 * mm("INSERT_SOCKET_SLOT_EDGE_THICKNESS"), 4.0, CYAN, WHITE, 1.2)
    ax.add_patch(Circle((mm("FAN_CENTER_X"), mm("FAN_CENTER_Z")), mm("FAN_OPENING_DIAMETER") / 2.0, fill=False, edgecolor=ORANGE, linewidth=1.4))
    for sx in (-1, 1):
        for sz in (-1, 1):
            ax.add_patch(Circle((mm("FAN_CENTER_X") + sx * mm("FAN_HOLE_SPACING_X") / 2.0, mm("FAN_CENTER_Z") + sz * mm("FAN_HOLE_SPACING_Z") / 2.0), mm("FAN_HOLE_DIAMETER") / 2.0, fill=False, edgecolor=ORANGE, linewidth=1.0))
    for x, z in C["CASE_FASTENER_POSITIONS_XZ"]:
        ax.add_patch(Circle((x, z), mm("BACK_FASTENER_BOSS_DIAMETER") / 2.0, fill=False, edgecolor=GREEN, linewidth=1.0))
    arrow(ax, (-mm("BACK_OUTER_WIDTH") / 2, -38), (mm("BACK_OUTER_WIDTH") / 2, -38), "BACK_OUTER_WIDTH", BLUE, (0, -3))
    arrow(ax, (53, -mm("BACK_OUTER_HEIGHT") / 2), (53, mm("BACK_OUTER_HEIGHT") / 2), "BACK_OUTER_HEIGHT", BLUE, (5, 0))

    fig.text(0.61, 0.76, "Default assembly profile", fontsize=13, weight="bold", color=INK)
    facts = (
        ("material", C["MATERIAL_MODE"]),
        ("slot depth", f"{mm('INSERT_SOCKET_SLOT_DEPTH'):.2f} mm"),
        ("slot edge", f"{mm('INSERT_SOCKET_SLOT_EDGE_THICKNESS'):.2f} mm"),
        ("outer wall X/Z", f"{(mm('BACK_OUTER_WIDTH') - (mm('INSERT_FRONT_WIDTH') + 2 * mm('FIT_CLEARANCE_X'))) / 2:.2f} / {(mm('BACK_OUTER_HEIGHT') - (mm('INSERT_FRONT_HEIGHT') + 2 * mm('FIT_CLEARANCE_Z'))) / 2:.2f} mm"),
        ("dimension entries", str(len(DIMENSION_ENTRIES))),
        ("settings entries", str(len(SETTING_ENTRIES))),
    )
    y = 0.70
    for label, value in facts:
        fig.text(0.61, y, label.upper(), fontsize=7.5, color=GRAY)
        fig.text(0.78, y, value, fontsize=10.5, color=INK)
        y -= 0.055
    note = (
        "The TPU capture slot is modeled as an annular groove at the front of "
        "the rear socket. The smaller through-opening leaves a TPU edge between "
        "the insert sleeve and the back-shell interior."
    )
    fig.text(0.61, 0.35, textwrap.fill(note, 50), fontsize=9, color=INK, linespacing=1.35)
    save_page(pdf, fig)


def page_slot_section(pdf):
    fig = new_page(
        "Rear Socket Capture Slot",
        "Y/Z section showing the insert sleeve seated into the configurable front groove.",
    )
    exterior_y = -mm("BACK_DOME_DEPTH") if C["BACK_DOME_ENABLED"] else 0.0
    face_inner_y = exterior_y + mm("BACK_FACE_THICKNESS")
    back_depth = mm("BACK_DEPTH")
    insert_start = back_depth - mm("INSERTION_DEPTH")
    slot_back = insert_start + mm("INSERT_SOCKET_SLOT_DEPTH")
    outer_half = mm("BACK_OUTER_HEIGHT") / 2.0
    socket_half = (mm("INSERT_FRONT_HEIGHT") + 2.0 * mm("FIT_CLEARANCE_Z")) / 2.0
    insert_outer_half = mm("INSERT_FRONT_HEIGHT") / 2.0
    insert_inner_half = (mm("INSERT_FRONT_HEIGHT") - 2.0 * mm("INSERT_WALL_Z")) / 2.0
    slot_inner_half = insert_inner_half - mm("INSERT_SOCKET_SLOT_INNER_CLEARANCE")
    slot_open_half = slot_inner_half - mm("INSERT_SOCKET_SLOT_EDGE_THICKNESS")

    ax = setup_ax(fig, [0.08, 0.18, 0.84, 0.66], (exterior_y - 2, back_depth + 4), (-outer_half - 6, outer_half + 6), "Y/Z socket section")
    ax.add_patch(Rectangle((exterior_y, -outer_half), back_depth - exterior_y, 2 * outer_half, facecolor=LIGHT, edgecolor=BLUE, linewidth=1.4))
    ax.add_patch(Rectangle((face_inner_y, -slot_open_half), slot_back - face_inner_y, 2 * slot_open_half, facecolor=WHITE, edgecolor=CYAN, linewidth=1.1))
    ax.add_patch(Rectangle((slot_back, -socket_half), back_depth - slot_back, 2 * socket_half, facecolor=WHITE, edgecolor=PURPLE, linewidth=1.1))
    ax.add_patch(Rectangle((insert_start, slot_inner_half), slot_back - insert_start, socket_half - slot_inner_half, facecolor=WHITE, edgecolor=PURPLE, linewidth=1.0))
    ax.add_patch(Rectangle((insert_start, -socket_half), slot_back - insert_start, socket_half - slot_inner_half, facecolor=WHITE, edgecolor=PURPLE, linewidth=1.0))
    ax.add_patch(Rectangle((insert_start, insert_inner_half), back_depth - insert_start, insert_outer_half - insert_inner_half, facecolor=ORANGE, edgecolor=ORANGE, alpha=0.55))
    ax.add_patch(Rectangle((insert_start, -insert_outer_half), back_depth - insert_start, insert_outer_half - insert_inner_half, facecolor=ORANGE, edgecolor=ORANGE, alpha=0.55))
    arrow(ax, (0, outer_half + 3), (back_depth, outer_half + 3), "BACK_DEPTH", BLUE, (0, 1.5))
    arrow(ax, (insert_start, -outer_half - 3), (back_depth, -outer_half - 3), "INSERTION_DEPTH", ORANGE, (0, -1.5))
    arrow(ax, (insert_start, socket_half + 2.6), (slot_back, socket_half + 2.6), "INSERT_SOCKET_SLOT_DEPTH", PURPLE, (0, 1.5), 7.5)
    arrow(ax, (slot_back + 1.0, slot_open_half), (slot_back + 1.0, slot_inner_half), "EDGE", GREEN, (2.7, 0), 7.5)
    ax.text(face_inner_y, -outer_half - 5, "inner face", fontsize=7.5, color=GRAY, ha="center")
    ax.text(back_depth, -outer_half - 5, "open rear", fontsize=7.5, color=GRAY, ha="center")
    save_page(pdf, fig)


def page_rear_xz(pdf):
    fig = new_page(
        "Rear Shell XZ Dimensions",
        "Outer perimeter, insert socket, slot opening, fan opening and shared fastener positions.",
    )
    ax = setup_ax(fig, [0.07, 0.15, 0.86, 0.70], (-58, 58), (-42, 42), "Back shell rear view")
    socket_w = mm("INSERT_FRONT_WIDTH") + 2 * mm("FIT_CLEARANCE_X")
    socket_h = mm("INSERT_FRONT_HEIGHT") + 2 * mm("FIT_CLEARANCE_Z")
    slot_inner_w = mm("INSERT_FRONT_WIDTH") - 2 * mm("INSERT_WALL_X") - 2 * mm("INSERT_SOCKET_SLOT_INNER_CLEARANCE")
    slot_inner_h = mm("INSERT_FRONT_HEIGHT") - 2 * mm("INSERT_WALL_Z") - 2 * mm("INSERT_SOCKET_SLOT_INNER_CLEARANCE")
    opening_w = slot_inner_w - 2 * mm("INSERT_SOCKET_SLOT_EDGE_THICKNESS")
    opening_h = slot_inner_h - 2 * mm("INSERT_SOCKET_SLOT_EDGE_THICKNESS")
    rounded_box(ax, 0, 0, mm("BACK_OUTER_WIDTH"), mm("BACK_OUTER_HEIGHT"), mm("BACK_CORNER_RADIUS"), BLUE, LIGHT, 1.8)
    rounded_box(ax, 0, 0, socket_w, socket_h, mm("INSERT_OUTER_CORNER_RADIUS") + max(mm("FIT_CLEARANCE_X"), mm("FIT_CLEARANCE_Z")), PURPLE, "none", 1.2, "--")
    rounded_box(ax, 0, 0, slot_inner_w, slot_inner_h, 5.8, GREEN, "none", 1.0, "--")
    rounded_box(ax, 0, 0, opening_w, opening_h, 5.1, CYAN, WHITE, 1.0)
    ax.add_patch(Circle((mm("FAN_CENTER_X"), mm("FAN_CENTER_Z")), mm("FAN_OPENING_DIAMETER") / 2.0, fill=False, edgecolor=ORANGE, linewidth=1.4))
    for sx in (-1, 1):
        for sz in (-1, 1):
            x = mm("FAN_CENTER_X") + sx * mm("FAN_HOLE_SPACING_X") / 2.0
            z = mm("FAN_CENTER_Z") + sz * mm("FAN_HOLE_SPACING_Z") / 2.0
            ax.add_patch(Circle((x, z), mm("FAN_HOLE_BOSS_DIAMETER") / 2.0, fill=False, edgecolor=ORANGE, linewidth=0.8))
            ax.add_patch(Circle((x, z), mm("FAN_HOLE_DIAMETER") / 2.0, fill=False, edgecolor=RED, linewidth=0.8))
    for index, (x, z) in enumerate(C["CASE_FASTENER_POSITIONS_XZ"], start=1):
        ax.add_patch(Circle((x, z), mm("BACK_FASTENER_BOSS_DIAMETER") / 2.0, fill=False, edgecolor=GREEN, linewidth=1.0))
        ax.text(x, z, str(index), fontsize=7, color=GREEN, ha="center", va="center")
    arrow(ax, (-socket_w / 2, 38), (socket_w / 2, 38), "socket width", PURPLE, (0, 2), 7.5)
    arrow(ax, (54, -socket_h / 2), (54, socket_h / 2), "socket height", PURPLE, (4, 0), 7.5)
    save_page(pdf, fig)


def page_insert(pdf):
    fig = new_page(
        "Insert Sleeve Dimensions",
        "Open sleeve wall dimensions, insertion overlap and access opening controls.",
    )
    ax = setup_ax(fig, [0.07, 0.18, 0.43, 0.62], (-50, 50), (-36, 36), "Insert XZ wall")
    rounded_box(ax, 0, 0, mm("INSERT_FRONT_WIDTH"), mm("INSERT_FRONT_HEIGHT"), mm("INSERT_OUTER_CORNER_RADIUS"), ORANGE, "#fde9df", 1.6)
    rounded_box(ax, 0, 0, mm("INSERT_FRONT_WIDTH") - 2 * mm("INSERT_WALL_X"), mm("INSERT_FRONT_HEIGHT") - 2 * mm("INSERT_WALL_Z"), 6.0, ORANGE, WHITE, 1.2)
    arrow(ax, (-mm("INSERT_FRONT_WIDTH") / 2, -34), (mm("INSERT_FRONT_WIDTH") / 2, -34), "INSERT_FRONT_WIDTH", ORANGE, (0, -2), 7.5)
    arrow(ax, (48, -mm("INSERT_FRONT_HEIGHT") / 2), (48, mm("INSERT_FRONT_HEIGHT") / 2), "INSERT_FRONT_HEIGHT", ORANGE, (4, 0), 7.5)
    arrow(ax, (mm("INSERT_FRONT_WIDTH") / 2 - mm("INSERT_WALL_X"), 26), (mm("INSERT_FRONT_WIDTH") / 2, 26), "INSERT_WALL_X", BLUE, (0, 3), 7.5)
    arrow(ax, (-34, mm("INSERT_FRONT_HEIGHT") / 2 - mm("INSERT_WALL_Z")), (-34, mm("INSERT_FRONT_HEIGHT") / 2), "INSERT_WALL_Z", BLUE, (-5, 0), 7.5)

    ax2 = setup_ax(fig, [0.56, 0.24, 0.36, 0.50], (0, mm("INSERT_DEPTH") + 5), (-10, 10), "Insert Y depth")
    ax2.add_patch(Rectangle((0, -4), mm("INSERT_DEPTH"), 8, facecolor="#fde9df", edgecolor=ORANGE, linewidth=1.5))
    ax2.add_patch(Rectangle((0, -1.8), mm("INSERTION_DEPTH"), 3.6, facecolor=PURPLE, edgecolor=PURPLE, alpha=0.35))
    arrow(ax2, (0, 7), (mm("INSERT_DEPTH"), 7), "INSERT_DEPTH", ORANGE, (0, 1.5), 8)
    arrow(ax2, (0, -7), (mm("INSERTION_DEPTH"), -7), "INSERTION_DEPTH inside back", PURPLE, (0, -1.3), 7.5)
    save_page(pdf, fig)


def page_fasteners(pdf):
    fig = new_page(
        "Fastener And Snap Retention",
        "Shared screw bosses, rear hex retention tabs, insert boss sockets and side snap features.",
    )
    ax = setup_ax(fig, [0.08, 0.18, 0.38, 0.62], (-42, 42), (-36, 36), "Case fastener locations")
    rounded_box(ax, 0, 0, mm("INSERT_FRONT_WIDTH"), mm("INSERT_FRONT_HEIGHT"), mm("INSERT_OUTER_CORNER_RADIUS"), ORANGE, "none", 1.0)
    for index, (x, z) in enumerate(C["CASE_FASTENER_POSITIONS_XZ"], start=1):
        ax.add_patch(Circle((x, z), mm("BACK_FASTENER_BOSS_DIAMETER") / 2.0, fill=False, edgecolor=GREEN, linewidth=1.2))
        ax.add_patch(Circle((x, z), mm("BACK_FASTENER_HOLE_DIAMETER") / 2.0, fill=False, edgecolor=RED, linewidth=0.9))
        ax.text(x, z + 6, f"F{index}", fontsize=8, color=GREEN, ha="center")
    ax2 = setup_ax(fig, [0.55, 0.26, 0.36, 0.42], (-8, 8), (-6, 8), "Rear hex seat")
    hex_half_w = mm("BACK_FASTENER_HEX_WIDTH_X") / 2.0
    hex_half_h = mm("BACK_FASTENER_HEX_HEIGHT_Z") / 2.0
    hex_points = [
        (hex_half_w, 0),
        (hex_half_w / 2, hex_half_h),
        (-hex_half_w / 2, hex_half_h),
        (-hex_half_w, 0),
        (-hex_half_w / 2, -hex_half_h),
        (hex_half_w / 2, -hex_half_h),
    ]
    ax2.add_patch(Polygon(hex_points, fill=False, edgecolor=GREEN, linewidth=1.5))
    ax2.add_patch(Circle((0, 0), mm("BACK_FASTENER_HOLE_DIAMETER") / 2.0, fill=False, edgecolor=RED, linewidth=1.0))
    ax2.add_patch(Rectangle((-mm("BACK_FASTENER_RETENTION_TAB_WIDTH_X") / 2, hex_half_h - mm("BACK_FASTENER_RETENTION_TAB_PROTRUSION")), mm("BACK_FASTENER_RETENTION_TAB_WIDTH_X"), mm("BACK_FASTENER_RETENTION_TAB_PROTRUSION"), facecolor=PURPLE, edgecolor=PURPLE, alpha=0.65))
    ax2.add_patch(Rectangle((-mm("BACK_FASTENER_RETENTION_TAB_WIDTH_X") / 2, -hex_half_h), mm("BACK_FASTENER_RETENTION_TAB_WIDTH_X"), mm("BACK_FASTENER_RETENTION_TAB_PROTRUSION"), facecolor=PURPLE, edgecolor=PURPLE, alpha=0.65))
    arrow(ax2, (-hex_half_w, 6), (hex_half_w, 6), "HEX_WIDTH_X", GREEN, (0, 1), 7)
    arrow(ax2, (6.5, -hex_half_h), (6.5, hex_half_h), "HEX_HEIGHT_Z", GREEN, (2, 0), 7)
    save_page(pdf, fig)


def page_ports_rails(pdf):
    fig = new_page(
        "Insert Ports And Interior Rails",
        "Bottom access, round/USB/top ports, locating rails and lens-clearance guide tapers.",
    )
    ax = setup_ax(fig, [0.07, 0.18, 0.50, 0.62], (-48, 48), (-35, 35), "Insert XZ features")
    rounded_box(ax, 0, 0, mm("INSERT_FRONT_WIDTH"), mm("INSERT_FRONT_HEIGHT"), mm("INSERT_OUTER_CORNER_RADIUS"), ORANGE, "#fde9df", 1.3)
    rounded_box(ax, 0, 0, mm("INSERT_FRONT_WIDTH") - 2 * mm("INSERT_WALL_X"), mm("INSERT_FRONT_HEIGHT") - 2 * mm("INSERT_WALL_Z"), 6.0, ORANGE, WHITE, 1.0)
    for name, x0, x1, z0, z1, attachment in C["LOCATING_TAB_SPECS"]:
        ax.add_patch(Rectangle((x0, z0), x1 - x0, z1 - z0, facecolor=CYAN, edgecolor=CYAN, alpha=0.55))
    ax.add_patch(Rectangle((-mm("BOTTOM_ACCESS_WIDTH") / 2, -mm("INSERT_FRONT_HEIGHT") / 2), mm("BOTTOM_ACCESS_WIDTH"), 5, facecolor=WHITE, edgecolor=RED, linewidth=1.0))
    ax.text(0, -31, "BOTTOM_ACCESS_WIDTH", fontsize=7.5, color=RED, ha="center")
    ax.text(mm("TOP_PORT_X"), mm("INSERT_FRONT_HEIGHT") / 2 - 2, "TOP_PORT", fontsize=7.5, color=GREEN, ha="center")
    ax2 = setup_ax(fig, [0.62, 0.27, 0.28, 0.42], (0, mm("INSERT_DEPTH") + 2), (-15, 15), "Port Y offsets")
    ax2.add_patch(Rectangle((0, -3), mm("INSERT_DEPTH"), 6, facecolor="#fde9df", edgecolor=ORANGE, linewidth=1.2))
    for label, value, color in (
        ("left round", mm("LEFT_ROUND_PORT_Y_OFFSET"), GREEN),
        ("USB", mm("RIGHT_USB_PORT_Y_OFFSET"), RED),
        ("top", mm("TOP_PORT_Y_OFFSET"), BLUE),
        ("bottom access", mm("BOTTOM_ACCESS_Y_OFFSET"), PURPLE),
    ):
        ax2.plot([value, value], [-8, 8], color=color, linewidth=1.0)
        ax2.text(value, 10, label, fontsize=7, color=color, ha="center", rotation=45)
    save_page(pdf, fig)


def page_inventory(pdf, entries: tuple[ConfigEntry, ...], title: str, subtitle: str):
    for page_index in range(math.ceil(len(entries) / INVENTORY_ROWS_PER_PAGE)):
        fig = new_page(title, subtitle)
        start = page_index * INVENTORY_ROWS_PER_PAGE
        chunk = entries[start:start + INVENTORY_ROWS_PER_PAGE]
        y = 0.83
        for entry in chunk:
            fig.patches.append(
                FancyBboxPatch(
                    (0.055, y - 0.075),
                    0.89,
                    0.083,
                    boxstyle="round,pad=0.006,rounding_size=0.008",
                    transform=fig.transFigure,
                    facecolor=LIGHT,
                    edgecolor=GRID,
                    linewidth=0.8,
                )
            )
            fig.text(0.073, y - 0.006, entry.name, fontsize=9.0, weight="bold", color=INK)
            fig.text(0.073, y - 0.030, f"{entry.group} | {entry.kind} | line {entry.line}", fontsize=7.0, color=GRAY)
            fig.text(0.42, y - 0.006, format_value(entry.value), fontsize=8.0, color=BLUE)
            desc = textwrap.fill(entry.description, 92)
            fig.text(0.42, y - 0.033, desc, fontsize=7.0, color=INK)
            y -= 0.091
        save_page(pdf, fig)


def page_coverage(pdf):
    fig = new_page(
        "Coverage And Synchronization",
        "Generated proof that the guide was built from the current source hash.",
    )
    lines = [
        f"Model source: {MODEL_SOURCE.name}",
        f"Generator source: {Path(__file__).name}",
        f"Source hash: source-{SOURCE_HASH}",
        f"Dimensional configuration entries: {len(DIMENSION_ENTRIES)}",
        f"Build/display setting entries: {len(SETTING_ENTRIES)}",
        f"Total sheets: {TOTAL_SHEETS}",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
    ]
    y = 0.78
    for line in lines:
        fig.text(0.11, y, line, fontsize=11, color=INK)
        y -= 0.06
    note = (
        "Generation fails on unsupported uppercase assignment forms so newly added "
        "configuration values cannot silently disappear from the inventory. Use "
        "`make fan-case-dim-pdf` to rebuild and `make check-fan-case-dim-pdf-sync` "
        "to verify the embedded source hash."
    )
    fig.text(0.11, 0.28, textwrap.fill(note, 96), fontsize=9, color=GRAY, linespacing=1.35)
    save_page(pdf, fig)


def write_pdf() -> None:
    global CURRENT_SHEET
    CURRENT_SHEET = 0
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{OUTPUT_PDF.stem}.",
        suffix=".tmp.pdf",
        dir=OUTPUT_PDF.parent,
        delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with PdfPages(
            temporary_path,
            metadata={
                "Title": "GoPro Fan Case Configuration Dimension Guide",
                "Author": "generate_fan_case_config_dimension_pdf.py",
                "Subject": "Parametric GoPro fan case CAD configuration dimensions",
                "Keywords": f"GoPro fan case CAD dimensions configuration source-{SOURCE_HASH}",
            },
        ) as pdf:
            page_title(pdf)
            page_slot_section(pdf)
            page_rear_xz(pdf)
            page_insert(pdf)
            page_fasteners(pdf)
            page_ports_rails(pdf)
            page_inventory(
                pdf,
                DIMENSION_ENTRIES,
                "Dimensional Configuration Inventory",
                "Every parsed top-level numeric dimensional control, grouped by feature.",
            )
            page_inventory(
                pdf,
                SETTING_ENTRIES,
                "Build And Display Configuration Inventory",
                "Non-dimensional switches, names, colors, solvers and sampling controls.",
            )
            page_coverage(pdf)
        if CURRENT_SHEET != TOTAL_SHEETS:
            raise RuntimeError(
                f"Page-count drift: wrote {CURRENT_SHEET}, expected {TOTAL_SHEETS}"
            )
        temporary_path.replace(OUTPUT_PDF)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    print(
        f"Wrote {OUTPUT_PDF} sheets={TOTAL_SHEETS} "
        f"dimensions={len(DIMENSION_ENTRIES)} settings={len(SETTING_ENTRIES)} "
        f"source={SOURCE_HASH}"
    )


def check_sync() -> None:
    if not OUTPUT_PDF.is_file():
        raise RuntimeError(f"Missing generated dimension guide: {OUTPUT_PDF}")
    pdf_data = OUTPUT_PDF.read_bytes()
    expected = f"source-{SOURCE_HASH}".encode("ascii")
    if expected not in pdf_data:
        raise RuntimeError(
            f"Stale dimension guide: {OUTPUT_PDF.name} does not contain "
            f"{expected.decode()}. Regenerate it with `make fan-case-dim-pdf`."
        )
    if not pdf_data.rstrip().endswith(b"%%EOF"):
        raise RuntimeError(f"Incomplete dimension guide: {OUTPUT_PDF.name}")
    page_count = len(re.findall(rb"/Type\s*/Page\b", pdf_data))
    if page_count != TOTAL_SHEETS:
        raise RuntimeError(
            f"Incomplete dimension guide: {OUTPUT_PDF.name} has {page_count} "
            f"page objects; expected {TOTAL_SHEETS}."
        )
    print(f"Synchronized {OUTPUT_PDF} source={SOURCE_HASH}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-sync",
        action="store_true",
        help="verify that the existing PDF matches the model and generator sources",
    )
    args = parser.parse_args()
    if args.check_sync:
        check_sync()
    else:
        write_pdf()


if __name__ == "__main__":
    main()
