#!/usr/bin/env python3
"""Generate the GoPro fan-case configuration and sleeve-joint dimension guide.

The model is parsed without importing Blender.  Every uppercase assignment in
the model's CONFIG block is cataloged, while the curated engineering sheets
explain the back shell, insert sleeve, continuous capture groove, assembly
datum, fasteners, ports, snaps and manufacturing controls.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import math
import re
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle


HERE = Path(__file__).absolute().parent
MODEL_SOURCE = HERE / "gopro_fan_case_parametric_blender.py"
OUTPUT_PDF = HERE / "gopro_fan_case_configuration_dimensions.pdf"

INK = "#152536"
BLUE = "#176ea6"
CYAN = "#55a9c5"
ORANGE = "#d66b2d"
GREEN = "#3d8a61"
RED = "#b54848"
GRAY = "#657580"
LIGHT = "#edf3f6"
GRID = "#d8e2e8"
WHITE = "#ffffff"

mpl.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 8.0,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK,
        "text.color": INK,
        "figure.facecolor": WHITE,
        "savefig.facecolor": WHITE,
    }
)


def safe_value(node: ast.AST, env: dict[str, object]):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return env[node.id]
    if isinstance(node, ast.Tuple):
        return tuple(safe_value(item, env) for item in node.elts)
    if isinstance(node, ast.List):
        return [safe_value(item, env) for item in node.elts]
    if isinstance(node, ast.Dict):
        result = {}
        for key_node, value_node in zip(node.keys, node.values):
            value = safe_value(value_node, env)
            if key_node is None:
                result.update(value)
            else:
                result[safe_value(key_node, env)] = value
        return result
    if isinstance(node, ast.UnaryOp):
        value = safe_value(node.operand, env)
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.UAdd):
            return +value
    if isinstance(node, ast.BinOp):
        left = safe_value(node.left, env)
        right = safe_value(node.right, env)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
    raise ValueError(f"Unsupported static expression: {ast.dump(node)}")


@dataclass(frozen=True)
class ConfigEntry:
    name: str
    value: object
    source_value: object
    source_line: int
    category: str
    description: str
    unit: str
    profile_controlled: bool


CATEGORY_PREFIXES = (
    ("Button actuators", ("BUTTON_",)),
    ("Front camera retainer", ("RETAINER_",)),
    ("Build, export and viewport", ("CLEAR_", "LAYOUT_", "PRINT_BED_", "SHOW_", "EXPORT_", "COMBINED_", "BACK_STL_", "INSERT_STL_", "MATERIAL_")),
    ("Mesh and Boolean quality", ("CYLINDER_", "CORNER_", "BOOLEAN_", "WATERTIGHT_", "INSERT_DEPTH_SECTIONS")),
    ("Sleeve capture joint", ("SLEEVE_CAPTURE_", "FIT_CLEARANCE_", "INSERTION_DEPTH")),
    ("Back shell and dome", ("BACK_OUTER_", "BACK_DEPTH", "BACK_CORNER_", "BACK_FACE_", "BACK_DOME_")),
    ("Fan and vent", ("FAN_", "VENT_")),
    ("Case fasteners", ("CASE_FASTENER_", "BACK_FASTENER_", "INSERT_FASTENER_", "FASTENER_BOSS_")),
    ("Camera stops", ("CAMERA_STOP_", "CAMERA_STOPS_")),
    ("Insert sleeve", ("INSERT_FRONT_", "INSERT_REAR_", "INSERT_DEPTH", "INSERT_OUTER_", "INSERT_WALL_")),
    ("Access ports", ("BOTTOM_ACCESS_", "LEFT_ROUND_", "RIGHT_USB_", "TOP_PORT_")),
    ("Locators and snaps", ("LOCATING_", "LENS_CLEARANCE_", "SNAP_")),
    ("Viewport colors", ("BACK_COLOR", "INSERT_COLOR")),
)


EXACT_DESCRIPTIONS = {
    "BACK_OUTER_WIDTH": "Requested legacy back-shell width; the enabled capture joint may expand the effective envelope to contain its support contour.",
    "BACK_OUTER_HEIGHT": "Requested legacy back-shell height; the enabled capture joint may expand the effective envelope to contain its support contour.",
    "BACK_CORNER_RADIUS": "Requested legacy back-shell corner radius; the enabled capture joint derives a containing effective radius when necessary.",
    "INSERTION_DEPTH": "Ordinary sleeve overlap measured rearward from the screw-boss assembly datum.",
    "SLEEVE_CAPTURE_SLOT_ENABLED": "Enables the continuous four-sided groove, interior retaining lip and extended sleeve edge.",
    "SLEEVE_CAPTURE_ENGAGEMENT_DEPTH": "Distance the sleeve leading wall extends beyond the boss datum into the groove.",
    "SLEEVE_CAPTURE_FIT_CLEARANCE": "Lateral clearance on each of the sleeve wall's inner and outer groove faces.",
    "SLEEVE_CAPTURE_INNER_LIP_THICKNESS": "Structural back-shell material retained between the groove and open interior.",
    "SLEEVE_CAPTURE_BOTTOM_CLEARANCE": "Axial gap between the seated sleeve edge and groove floor when boss faces meet.",
    "SLEEVE_CAPTURE_FLOOR_THICKNESS": "Back-shell material remaining beneath the bottom of the capture groove.",
    "SLEEVE_CAPTURE_MIN_OUTER_WALL_X": "Required structural side-wall support outside the groove at its deepest section in X.",
    "SLEEVE_CAPTURE_MIN_OUTER_WALL_Z": "Required structural top/bottom support outside the groove at its deepest section in Z.",
    "BACK_FASTENER_MIN_DATUM_CONTACT_AREA": "Minimum sampled common bearing area retained between each back/insert boss pair after the groove cut.",
    "BACK_FASTENER_TO_INSERT_SOCKET_GAP": "Face-to-face gap between back and insert screw bosses at the assembly datum; normally zero.",
    "FIT_CLEARANCE_X": "Ordinary per-side sleeve/socket sliding clearance along X before groove engagement.",
    "FIT_CLEARANCE_Z": "Ordinary per-side sleeve/socket sliding clearance along Z before groove engagement.",
    "INSERT_OUTER_CORNER_RADIUS": "Sleeve outside corner radius; groove radii are derived by adding/subtracting fit offsets.",
    "INSERT_WALL_X": "Sleeve side-wall thickness used to derive its inner contour and groove inner face.",
    "INSERT_WALL_Z": "Sleeve top/bottom-wall thickness used to derive its inner contour and groove inner face.",
    "CASE_FASTENER_POSITIONS_XZ": "Three screw-axis locations; boss faces define the final assembled spacing.",
    "CAMERA_STOP_SPECS": "Named X/Z bounds and attachment side for each rear-shell camera stop.",
    "LOCATING_TAB_SPECS": "Named X/Z bounds and attachment side for each insert locating rail.",
    "LENS_CLEARANCE_GUIDE_TAPERS": "Per-rail taper length and remaining projection at the camera-entry end.",
    "MATERIAL_MODE": "Selects RIGID or TPU fastener-retention geometry; the sleeve slot remains independently switchable.",
    "BUTTON_STEM_DIAMETER": "Diameter of the actuator shaft that slides through each circular sleeve port.",
    "BUTTON_TOTAL_HEIGHT": "Overall inside-to-outside actuator height, including its inner flange and exterior retention bead.",
    "BUTTON_INNER_FLANGE_THICKNESS": "Thickness of the flat camera-side flange that prevents the actuator escaping outward.",
    "BUTTON_INNER_FLANGE_DIAMETER": "Diameter of the camera-side contact flange and inward travel stop.",
    "BUTTON_RETENTION_RIM_DIAMETER": "Maximum diameter of the compressible exterior TPU bead that snaps through the sleeve port.",
    "BUTTON_RETENTION_RIM_HEIGHT": "Axial length reserved for the exterior snap-bead profile.",
    "BUTTON_RETENTION_SHOULDER_HEIGHT": "Short inward-facing taper that resists pulling the installed button back through the port.",
    "BUTTON_RETENTION_LEAD_IN_HEIGHT": "Tapered tip length that guides and compresses the TPU bead during inside-out installation.",
    "BUTTON_STL_NAME": "Output filename for one canonical captive button; print two copies in TPU.",
    "RETAINER_ENABLED": "Build and export the removable front camera-retaining plate; requires the three case fasteners.",
    "RETAINER_THICKNESS_Y": "Front-retainer plate thickness along the case insertion axis.",
    "RETAINER_HOLE_DIAMETER": "Diameter of each of the three front-retainer screw passages.",
    "RETAINER_HORIZONTAL_END_MARGIN_X": "Horizontal material added beyond the leftmost and rightmost case-fastener axes.",
    "RETAINER_HORIZONTAL_BAR_HEIGHT_Z": "Full lower-bar height before the camera-clearance scallop is removed.",
    "RETAINER_LOWER_EDGE_MARGIN_Z": "Distance from the lower fastener row to the retainer's bottom edge.",
    "RETAINER_UPRIGHT_WIDTH_X": "Width of the narrow upright joining the right lower and upper fasteners.",
    "RETAINER_TOP_EDGE_MARGIN_Z": "Distance from the upper fastener axis to the retainer's top edge.",
    "RETAINER_RELIEF_RADIUS": "Radius of the large circular scallop that preserves camera clearance above the lower retaining strap.",
    "RETAINER_MIN_HOLE_WEB": "Minimum configured radial bearing web validated around each retainer screw passage.",
    "RETAINER_STL_NAME": "Output filename for the front camera-retaining plate, exported flat for printing.",
}


def category_for(name: str) -> str:
    for category, prefixes in CATEGORY_PREFIXES:
        if name.startswith(prefixes):
            return category
    return "Other configuration"


def humanize(name: str) -> str:
    words = name.lower().replace("_", " ")
    replacements = {
        " x ": " X ",
        " y ": " Y ",
        " z ": " Z ",
        " usb ": " USB ",
        " stl ": " STL ",
        " mm ": " mm ",
    }
    words = " " + words + " "
    for old, new in replacements.items():
        words = words.replace(old, new)
    return words.strip().capitalize()


def description_for(name: str, category: str) -> str:
    if name in EXACT_DESCRIPTIONS:
        return EXACT_DESCRIPTIONS[name]
    label = humanize(name)
    if name.endswith("_ENABLED") or name.startswith(("SHOW_", "EXPORT_", "CLEAR_")):
        return f"Switch controlling {label.lower()}."
    if name.endswith(("_COUNT", "_SEGMENTS", "_SECTIONS", "_LOOP_POINTS")):
        return f"Discrete geometry resolution/count for {label.lower()}."
    if name.endswith(("_PATH", "_NAME", "_DIRECTORY")):
        return f"Output naming/location setting for {label.lower()}."
    if name.endswith(("_SPECS", "_POSITIONS_XZ", "_TAPERS")):
        return f"Configured record set defining {label.lower()}."
    return f"{label}; part of the {category.lower()} configuration."


def unit_for(name: str, value: object) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "setting"
    if name.endswith("_DEG"):
        return "deg"
    if name == "BOOLEAN_MINIMUM_VOLUME_CHANGE":
        return "mm³"
    if name.endswith("_AREA"):
        return "mm²"
    if name.endswith(("_COUNT", "_SEGMENTS", "_SECTIONS", "_POINTS")):
        return "count"
    return "mm"


def assignment_target_names(target: ast.AST) -> set[str]:
    """Collect every name in an assignment target, including destructuring."""
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return {
            name
            for element in target.elts
            for name in assignment_target_names(element)
        }
    if isinstance(target, ast.Starred):
        return assignment_target_names(target.value)
    return set()


def read_model_config():
    tree = ast.parse(MODEL_SOURCE.read_text(encoding="utf-8"), filename=str(MODEL_SOURCE))
    assignment_names_by_line = []
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            names = {
                name
                for target in statement.targets
                for name in assignment_target_names(target)
            }
        elif isinstance(statement, ast.AnnAssign):
            names = assignment_target_names(statement.target)
        else:
            continue
        assignment_names_by_line.append((statement.lineno, names))

    boundary_lines = [
        line
        for line, names in assignment_names_by_line
        if "_RIGID_MATERIAL_PROFILE" in names
    ]
    if len(boundary_lines) != 1:
        raise RuntimeError(
            "Could not identify exactly one fan-case CONFIG/material-profile "
            "boundary"
        )
    config_boundary = boundary_lines[0]
    expected_config_names = {
        name
        for line, names in assignment_names_by_line
        if line < config_boundary
        for name in names
        if name.isupper()
    }

    env: dict[str, object] = {}
    parsed: list[tuple[str, object, int]] = []
    unsupported = []
    for statement in tree.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        if isinstance(statement, ast.Assign):
            if len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
                names = {
                    name
                    for target in statement.targets
                    for name in assignment_target_names(target)
                    if name.isupper()
                }
                unsupported.extend((name, statement.lineno) for name in names)
                continue
            name = statement.targets[0].id
            expression = statement.value
        else:
            if not isinstance(statement.target, ast.Name) or statement.value is None:
                continue
            name = statement.target.id
            expression = statement.value
        try:
            value = safe_value(expression, env)
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            if name.isupper() and (config_boundary is None or statement.lineno < config_boundary):
                unsupported.append((name, statement.lineno))
            continue
        env[name] = value
        parsed.append((name, value, statement.lineno))

    if unsupported:
        raise RuntimeError(f"Unsupported uppercase CONFIG assignments: {unsupported}")

    source_config = {
        name: (value, line)
        for name, value, line in parsed
        if line < config_boundary and name.isupper()
    }
    catalogued_names = set(source_config)
    if catalogued_names != expected_config_names:
        raise RuntimeError(
            "Fan-case CONFIG catalog mismatch: "
            f"missing={sorted(expected_config_names - catalogued_names)} "
            f"unexpected={sorted(catalogued_names - expected_config_names)}"
        )
    material_mode = source_config["MATERIAL_MODE"][0]
    profiles = env.get("MATERIAL_PROFILES", {})
    profile = profiles.get(material_mode, {}) if isinstance(profiles, dict) else {}
    entries = []
    for name, (source_value, line) in sorted(source_config.items(), key=lambda item: item[1][1]):
        value = profile.get(name, source_value)
        category = category_for(name)
        entries.append(
            ConfigEntry(
                name=name,
                value=value,
                source_value=source_value,
                source_line=line,
                category=category,
                description=description_for(name, category),
                unit=unit_for(name, value),
                profile_controlled=name in profile,
            )
        )
    return env, tuple(entries), frozenset(expected_config_names)


ENV, CONFIG_ENTRIES, EXPECTED_CONFIG_NAMES = read_model_config()
C = {entry.name: entry.value for entry in CONFIG_ENTRIES}
SOURCE_HASH = hashlib.sha256(
    MODEL_SOURCE.read_bytes() + Path(__file__).read_bytes()
).hexdigest()[:12]
CATALOG_PER_PAGE = 8
CURATED_PAGE_COUNT = 6
CATALOG_PAGE_COUNT = math.ceil(len(CONFIG_ENTRIES) / CATALOG_PER_PAGE)
TOTAL_PAGES = 1 + CURATED_PAGE_COUNT + CATALOG_PAGE_COUNT + 1


def fmt(value: object) -> str:
    if isinstance(value, float):
        if value == 0.0:
            return "0.0"
        if abs(value) < 0.001:
            return f"{value:.3g}"
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if isinstance(value, tuple) and len(value) > 4:
        return f"{len(value)} entries: {value!r}"
    if isinstance(value, dict):
        return f"{len(value)} entries: {value!r}"
    return repr(value)


def resolved_capture_geometry():
    enabled = bool(C["SLEEVE_CAPTURE_SLOT_ENABLED"])
    clearance = float(C["SLEEVE_CAPTURE_FIT_CLEARANCE"])
    groove_width = float(C["INSERT_FRONT_WIDTH"]) + 2.0 * clearance
    groove_height = float(C["INSERT_FRONT_HEIGHT"]) + 2.0 * clearance
    groove_radius = float(C["INSERT_OUTER_CORNER_RADIUS"]) + clearance
    support_x = float(C["SLEEVE_CAPTURE_MIN_OUTER_WALL_X"])
    support_z = float(C["SLEEVE_CAPTURE_MIN_OUTER_WALL_Z"])
    support_width = groove_width + 2.0 * support_x
    support_height = groove_height + 2.0 * support_z
    support_radius = groove_radius + max(support_x, support_z)
    requested_width = float(C["BACK_OUTER_WIDTH"])
    requested_height = float(C["BACK_OUTER_HEIGHT"])
    requested_radius = float(C["BACK_CORNER_RADIUS"])
    requested_center = (
        requested_width / 2.0 - requested_radius,
        requested_height / 2.0 - requested_radius,
    )
    support_center = (
        support_width / 2.0 - support_radius,
        support_height / 2.0 - support_radius,
    )
    center_distance = math.hypot(
        requested_center[0] - support_center[0],
        requested_center[1] - support_center[1],
    )
    margin = max(
        0.0,
        (requested_width - support_width) / 2.0,
        (requested_height - support_height) / 2.0,
        requested_radius + center_distance - support_radius,
    )
    result = {
        "enabled": enabled,
        "groove_width": groove_width,
        "groove_height": groove_height,
        "groove_radius": groove_radius,
        "support_width": support_width,
        "support_height": support_height,
        "support_radius": support_radius,
        "back_width": support_width + 2.0 * margin,
        "back_height": support_height + 2.0 * margin,
        "back_radius": support_radius + margin,
    }
    if not enabled:
        result.update(
            {
                "back_width": requested_width,
                "back_height": requested_height,
                "back_radius": requested_radius,
            }
        )
    return result


def new_page(page_number: int, title: str, subtitle: str = ""):
    fig = plt.figure(figsize=(11.0, 8.5))
    fig.text(0.055, 0.945, title, fontsize=15.0, weight="bold", color=INK)
    if subtitle:
        fig.text(0.055, 0.916, subtitle, fontsize=7.5, color=GRAY)
    fig.add_artist(Rectangle((0.05, 0.895), 0.90, 0.002, transform=fig.transFigure, facecolor=BLUE, edgecolor="none"))
    fig.text(0.055, 0.034, "GOPRO FAN-CASE CONFIGURATION DIMENSION GUIDE • NTS WHERE NOTED", fontsize=6.6, color=GRAY)
    fig.text(0.50, 0.034, f"source-{SOURCE_HASH}", fontsize=6.6, color=GRAY, ha="center")
    fig.text(0.945, 0.034, f"SHEET {page_number} / {TOTAL_PAGES}", fontsize=6.6, color=GRAY, ha="right")
    return fig


def panel(fig, rect, title: str, subtitle: str = ""):
    ax = fig.add_axes(rect)
    ax.set_facecolor("#fbfdfe")
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.text(0.02, 0.97, title, transform=ax.transAxes, va="top", fontsize=8.8, weight="bold", color=BLUE)
    if subtitle:
        ax.text(0.02, 0.92, subtitle, transform=ax.transAxes, va="top", fontsize=6.5, color=GRAY)
    return ax


def dimension(ax, start, end, label: str, color=BLUE, offset=(0.0, 0.0)):
    start = (start[0] + offset[0], start[1] + offset[1])
    end = (end[0] + offset[0], end[1] + offset[1])
    arrow = FancyArrowPatch(start, end, arrowstyle="<->", mutation_scale=8, linewidth=0.8, color=color)
    ax.add_patch(arrow)
    vertical = abs(end[1] - start[1]) > abs(end[0] - start[0])
    ax.text(
        (start[0] + end[0]) / 2.0,
        (start[1] + end[1]) / 2.0,
        label,
        fontsize=6.3,
        color=color,
        ha="center",
        va="center" if vertical else "bottom",
        rotation=90 if vertical else 0,
        bbox={"facecolor": WHITE, "edgecolor": "none", "alpha": 0.78, "pad": 0.6},
    )


def note(ax, x, y, title: str, lines, color=BLUE):
    height = 0.075 + 0.038 * len(lines)
    box = FancyBboxPatch((x, y - height), 0.42, height, boxstyle="round,pad=0.012,rounding_size=0.012", transform=ax.transAxes, facecolor=WHITE, edgecolor=color, linewidth=0.8)
    ax.add_patch(box)
    ax.text(x + 0.015, y - 0.025, title, transform=ax.transAxes, fontsize=7.0, weight="bold", color=color, va="top")
    ax.text(x + 0.015, y - 0.064, "\n".join(lines), transform=ax.transAxes, fontsize=6.2, color=INK, va="top", linespacing=1.25)


def capture_disabled_page(pdf, page_number: int, title: str, details):
    """Render a truthful replacement for a groove sheet when the slot is off."""
    fig = new_page(
        page_number,
        title,
        "SLEEVE_CAPTURE_SLOT_ENABLED = False • capture geometry is inactive",
    )
    ax = panel(
        fig,
        [0.08, 0.16, 0.84, 0.66],
        "LEGACY SOCKET CONFIGURATION",
        "The slot-only CONFIG values remain catalogued but do not affect this build.",
    )
    ax.axis("off")
    ax.add_patch(
        FancyBboxPatch(
            (0.04, 0.57),
            0.92,
            0.27,
            boxstyle="round,pad=0.018,rounding_size=0.025",
            transform=ax.transAxes,
            facecolor=LIGHT,
            edgecolor=BLUE,
        )
    )
    ax.text(
        0.08,
        0.76,
        "CAPTURE GROOVE DISABLED",
        transform=ax.transAxes,
        fontsize=15,
        weight="bold",
        color=BLUE,
        va="top",
    )
    ax.text(
        0.08,
        0.67,
        "No groove, retaining lip, groove floor, support enlargement, or "
        "extra sleeve engagement is generated.",
        transform=ax.transAxes,
        fontsize=9.0,
        color=INK,
        va="top",
        wrap=True,
    )
    for index, detail in enumerate(details):
        ax.text(
            0.09,
            0.44 - index * 0.10,
            f"• {detail}",
            transform=ax.transAxes,
            fontsize=8.4,
            color=INK,
            va="top",
        )
    pdf.savefig(fig)
    plt.close(fig)


def page_cover(pdf):
    capture_enabled = bool(C["SLEEVE_CAPTURE_SLOT_ENABLED"])
    subtitle = (
        "Back shell, removable insert sleeve and continuous TPU capture groove"
        if capture_enabled
        else "Back shell and removable insert sleeve • optional capture groove disabled"
    )
    fig = new_page(1, "GOPRO FAN-CASE CONFIGURATION DIMENSION GUIDE", subtitle)
    ax = fig.add_axes([0.06, 0.12, 0.88, 0.72])
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((0.01, 0.50), 0.98, 0.45, boxstyle="round,pad=0.02,rounding_size=0.03", transform=ax.transAxes, facecolor=LIGHT, edgecolor=GRID))
    headline = (
        "ONE DATUM • TWO PARTS • ONE CAPTURED PERIMETER"
        if capture_enabled
        else "ONE DATUM • TWO PARTS • LEGACY SOCKET ACTIVE"
    )
    overview = (
        "The sleeve slides through the ordinary socket, then its leading wall "
        "enters a shallow four-sided groove. The three opposing screw-boss "
        "faces establish final assembly spacing; the sleeve retains axial "
        "bottom clearance."
        if capture_enabled
        else "The capture slot is disabled in this source configuration. The "
        "sleeve uses only the ordinary socket overlap, the back shell retains "
        "its requested legacy envelope, and no retaining groove or extra "
        "sleeve engagement is generated."
    )
    ax.text(0.05, 0.88, headline, transform=ax.transAxes, fontsize=13, weight="bold", color=BLUE)
    ax.text(0.05, 0.79, overview, transform=ax.transAxes, fontsize=9.0, color=INK, wrap=True)
    stats = (
        ("CONFIG SETTINGS", str(len(CONFIG_ENTRIES))),
        ("CURATED DRAWINGS", str(CURATED_PAGE_COUNT)),
        ("CATALOG SHEETS", str(CATALOG_PAGE_COUNT)),
        ("SOURCE HASH", SOURCE_HASH),
    )
    for index, (label, value) in enumerate(stats):
        x = 0.05 + index * 0.235
        ax.add_patch(FancyBboxPatch((x, 0.57), 0.20, 0.13, boxstyle="round,pad=0.01", transform=ax.transAxes, facecolor=WHITE, edgecolor=GRID))
        ax.text(x + 0.10, 0.655, value, transform=ax.transAxes, fontsize=12, weight="bold", color=ORANGE, ha="center")
        ax.text(x + 0.10, 0.595, label, transform=ax.transAxes, fontsize=6.5, color=GRAY, ha="center")
    ax.text(0.03, 0.43, "DOCUMENT MAP", transform=ax.transAxes, fontsize=10, weight="bold", color=INK)
    capture_rows = (
        (
            ("2", "Assembly datum and axial stack"),
            ("3", "Straight groove section and independent clearances"),
            ("4", "Continuous rounded-corner groove plan"),
        )
        if capture_enabled
        else (
            ("2", "Assembly datum — capture geometry inactive"),
            ("3", "Groove controls inactive in this configuration"),
            ("4", "Legacy back-shell contour — no support expansion"),
        )
    )
    rows = capture_rows + (
        ("5", "Back-shell, dome, fan and vent layout"),
        ("6", "Insert sleeve, walls, ports and access"),
        ("7", "Fasteners, hex capture, stops and snaps"),
        (f"8–{7 + CATALOG_PAGE_COUNT}", "Exhaustive CONFIG catalog in source order"),
        (str(TOTAL_PAGES), "Coverage and synchronization proof"),
    )
    for index, (pages, label) in enumerate(rows):
        y = 0.38 - index * 0.043
        ax.text(0.05, y, pages, transform=ax.transAxes, fontsize=7.2, weight="bold", color=BLUE)
        ax.text(0.14, y, label, transform=ax.transAxes, fontsize=7.2, color=INK)
    pdf.savefig(fig)
    plt.close(fig)


def page_assembly_datum(pdf):
    if not C["SLEEVE_CAPTURE_SLOT_ENABLED"]:
        capture_disabled_page(
            pdf,
            2,
            "ASSEMBLY DATUM AND AXIAL STACK",
            (
                f"Ordinary sleeve overlap remains {fmt(C['INSERTION_DEPTH'])} mm.",
                "The sleeve leading edge stops at the screw-boss datum; extra engagement is 0.0 mm.",
                f"Configured boss face gap remains {fmt(C['BACK_FASTENER_TO_INSERT_SOCKET_GAP'])} mm.",
            ),
        )
        return
    fig = new_page(2, "ASSEMBLY DATUM AND AXIAL STACK", "Boss faces meet first; the sleeve edge remains clear of the groove bottom")
    ax = panel(fig, [0.06, 0.14, 0.60, 0.70], "SIDE SECTION THROUGH A STRAIGHT SLEEVE WALL", "Assembly Y increases toward the removable insert")
    ax.set_xlim(0.0, 8.0)
    ax.set_ylim(0.0, 6.2)
    datum = 4.5
    engagement = float(C["SLEEVE_CAPTURE_ENGAGEMENT_DEPTH"])
    bottom_clearance = float(C["SLEEVE_CAPTURE_BOTTOM_CLEARANCE"])
    floor = float(C["SLEEVE_CAPTURE_FLOOR_THICKNESS"])
    scale = 1.5
    leading = datum - engagement * scale
    groove_floor = leading - bottom_clearance * scale
    ledge_start = groove_floor - floor * scale
    ax.add_patch(Rectangle((ledge_start, 0.6), datum - ledge_start, 1.1, facecolor=BLUE, alpha=0.85))
    ax.add_patch(Rectangle((ledge_start, 1.7), floor * scale, 2.1, facecolor=BLUE, alpha=0.85))
    ax.add_patch(Rectangle((groove_floor, 3.1), datum - groove_floor, 0.7, facecolor=BLUE, alpha=0.85))
    ax.add_patch(Rectangle((leading, 1.8), 3.0, 1.2, facecolor=ORANGE, alpha=0.9))
    ax.add_patch(Rectangle((0.8, 4.5), datum - 0.8, 0.8, facecolor=BLUE, alpha=0.85))
    ax.add_patch(Rectangle((datum, 4.5), 2.5, 0.8, facecolor=ORANGE, alpha=0.9))
    ax.axvline(datum, color=RED, linewidth=1.0, linestyle="--")
    ax.text(datum, 5.65, "SCREW-BOSS DATUM", color=RED, fontsize=7.2, weight="bold", ha="center")
    dimension(ax, (leading, 1.3), (datum, 1.3), f"SLEEVE_CAPTURE_ENGAGEMENT_DEPTH = {fmt(C['SLEEVE_CAPTURE_ENGAGEMENT_DEPTH'])} mm")
    dimension(ax, (groove_floor, 0.85), (leading, 0.85), f"BOTTOM_CLEARANCE = {fmt(C['SLEEVE_CAPTURE_BOTTOM_CLEARANCE'])} mm", GREEN)
    dimension(ax, (ledge_start, 0.25), (groove_floor, 0.25), f"FLOOR_THICKNESS = {fmt(C['SLEEVE_CAPTURE_FLOOR_THICKNESS'])} mm", ORANGE)
    ax.text(5.0, 2.45, "INSERT SLEEVE", color=ORANGE, fontsize=7.5, weight="bold")
    ax.text(1.0, 4.85, "BACK BOSS", color=WHITE, fontsize=7.0, weight="bold")
    ax.text(4.8, 4.85, "INSERT BOSS", color=WHITE, fontsize=7.0, weight="bold")
    side = panel(fig, [0.69, 0.14, 0.25, 0.70], "DATUM RULES")
    side.axis("off")
    note(side, 0.05, 0.92, "ASSEMBLED POSITION", [f"INSERTION_DEPTH = {fmt(C['INSERTION_DEPTH'])} mm", f"boss face gap = {fmt(C['BACK_FASTENER_TO_INSERT_SOCKET_GAP'])} mm", "Screw bosses carry clamp load."], BLUE)
    note(side, 0.05, 0.62, "SLEEVE EDGE", ["Extends past the boss datum.", "Enters the groove without", "touching its axial floor."], ORANGE)
    note(side, 0.05, 0.35, "FAIL-FAST VALIDATION", ["Rejects reversed axial order,", "front-wall breakthrough and", "incompatible groove radii."], RED)
    pdf.savefig(fig)
    plt.close(fig)


def page_groove_section(pdf):
    if not C["SLEEVE_CAPTURE_SLOT_ENABLED"]:
        capture_disabled_page(
            pdf,
            3,
            "CAPTURE GROOVE — STRAIGHT CROSS-SECTION",
            (
                "The ordinary socket clearance remains active; capture-groove face clearance does not.",
                "No retaining lip or axial groove floor exists in the printable back shell.",
                "Slot dimensions on the catalog sheets are inactive settings retained for later use.",
            ),
        )
        return
    fig = new_page(3, "CAPTURE GROOVE — STRAIGHT CROSS-SECTION", "Fit clearance, retaining lip and outer material are separate controls")
    ax = panel(fig, [0.06, 0.14, 0.63, 0.70], "SECTION NORMAL TO A STRAIGHT SIDE", "Blue = back shell • orange = sleeve wall • white = clearance")
    ax.set_xlim(0.0, 10.0)
    ax.set_ylim(0.0, 7.0)
    outer_wall = 2.2
    clearance = 0.55
    sleeve = 1.5
    lip = 1.4
    x0 = 1.0
    opening_end = x0 + 1.0
    lip_end = opening_end + lip
    sleeve_start = lip_end + clearance
    sleeve_end = sleeve_start + sleeve
    outer_start = sleeve_end + clearance
    ax.add_patch(Rectangle((x0, 0.8), 8.0, 0.9, facecolor=BLUE))
    ax.add_patch(Rectangle((opening_end, 1.7), lip, 3.8, facecolor=BLUE))
    ax.add_patch(Rectangle((outer_start, 1.7), outer_wall, 3.8, facecolor=BLUE))
    ax.add_patch(Rectangle((sleeve_start, 2.1), sleeve, 3.8, facecolor=ORANGE))
    ax.text(0.35, 3.6, "OPEN\nINTERIOR", fontsize=7.0, color=GRAY, ha="center")
    ax.text((opening_end + lip_end) / 2.0, 4.1, "INNER\nRETAINING\nLIP", fontsize=6.6, color=WHITE, ha="center", weight="bold")
    ax.text((sleeve_start + sleeve_end) / 2.0, 4.2, "SLEEVE\nLEADING\nWALL", fontsize=6.8, color=WHITE, ha="center", weight="bold")
    ax.text(outer_start + outer_wall / 2.0, 4.2, "OUTER\nBACK-SHELL\nWALL", fontsize=6.7, color=WHITE, ha="center", weight="bold")
    dimension(ax, (opening_end, 6.15), (lip_end, 6.15), f"INNER_LIP = {fmt(C['SLEEVE_CAPTURE_INNER_LIP_THICKNESS'])} mm", GREEN)
    dimension(ax, (lip_end, 5.75), (sleeve_start, 5.75), f"CLEARANCE = {fmt(C['SLEEVE_CAPTURE_FIT_CLEARANCE'])} mm", BLUE)
    dimension(ax, (sleeve_end, 5.75), (outer_start, 5.75), "same per-face clearance", BLUE)
    dimension(
        ax,
        (outer_start, 6.45),
        (outer_start + outer_wall, 6.45),
        "DEEP-GROOVE SUPPORT X / Z",
        RED,
    )
    side = panel(fig, [0.72, 0.14, 0.22, 0.70], "CURRENT RESOLVED VALUES")
    side.axis("off")
    outer_w = float(C["INSERT_FRONT_WIDTH"]) + 2.0 * float(C["SLEEVE_CAPTURE_FIT_CLEARANCE"])
    outer_h = float(C["INSERT_FRONT_HEIGHT"]) + 2.0 * float(C["SLEEVE_CAPTURE_FIT_CLEARANCE"])
    capture = resolved_capture_geometry()
    envelope_x = (capture["back_width"] - outer_w) / 2.0
    envelope_z = (capture["back_height"] - outer_h) / 2.0
    note(side, 0.04, 0.90, "GROOVE", [f"outer {outer_w:.2f} × {outer_h:.2f} mm", f"per-face fit {fmt(C['SLEEVE_CAPTURE_FIT_CLEARANCE'])} mm", f"depth {fmt(C['SLEEVE_CAPTURE_ENGAGEMENT_DEPTH'])} mm + bottom gap"], BLUE)
    note(side, 0.04, 0.66, "SUPPORT WALLS", [f"inner lip {fmt(C['SLEEVE_CAPTURE_INNER_LIP_THICKNESS'])} mm", f"deepest X {fmt(C['SLEEVE_CAPTURE_MIN_OUTER_WALL_X'])} mm", f"deepest Z {fmt(C['SLEEVE_CAPTURE_MIN_OUTER_WALL_Z'])} mm"], GREEN)
    note(side, 0.04, 0.42, "ENVELOPE MARGINS", [f"beyond groove X {envelope_x:.2f} mm", f"beyond groove Z {envelope_z:.2f} mm", "Includes material behind ledge."], BLUE)
    note(side, 0.04, 0.18, "NO MEMBRANE", ["Annular ledge; center stays open."], RED)
    pdf.savefig(fig)
    plt.close(fig)


def page_groove_plan(pdf):
    if not C["SLEEVE_CAPTURE_SLOT_ENABLED"]:
        capture_disabled_page(
            pdf,
            4,
            "CONTINUOUS GROOVE AND ROUNDED CORNERS",
            (
                f"Active back contour is {fmt(C['BACK_OUTER_WIDTH'])} × {fmt(C['BACK_OUTER_HEIGHT'])} mm.",
                f"Active back corner radius is the requested legacy {fmt(C['BACK_CORNER_RADIUS'])} mm.",
                "No groove-support contour expands the back-shell envelope.",
            ),
        )
        return
    fig = new_page(4, "CONTINUOUS GROOVE AND ROUNDED CORNERS", "All four straight sides and four corners share offset-derived contours")
    ax = panel(fig, [0.06, 0.13, 0.64, 0.72], "SOCKET-FACE PLAN", "Dashed orange = sleeve • cyan = deepest outer-support contour")
    ax.set_xlim(-52, 52)
    ax.set_ylim(-37, 37)
    ax.set_aspect("equal")
    capture = resolved_capture_geometry()
    back_w = capture["back_width"]
    back_h = capture["back_height"]
    back_r = capture["back_radius"]
    clearance = float(C["SLEEVE_CAPTURE_FIT_CLEARANCE"])
    groove_w = float(C["INSERT_FRONT_WIDTH"]) + 2.0 * clearance
    groove_h = float(C["INSERT_FRONT_HEIGHT"]) + 2.0 * clearance
    groove_r = float(C["INSERT_OUTER_CORNER_RADIUS"]) + clearance
    inner_w = float(C["INSERT_FRONT_WIDTH"]) - 2.0 * float(C["INSERT_WALL_X"]) - 2.0 * clearance
    inner_h = float(C["INSERT_FRONT_HEIGHT"]) - 2.0 * float(C["INSERT_WALL_Z"]) - 2.0 * clearance
    inner_r = float(C["INSERT_OUTER_CORNER_RADIUS"]) - max(float(C["INSERT_WALL_X"]), float(C["INSERT_WALL_Z"])) - clearance
    lip = float(C["SLEEVE_CAPTURE_INNER_LIP_THICKNESS"])
    contours = (
        (back_w, back_h, back_r, BLUE, 2.0, "-"),
        (capture["support_width"], capture["support_height"], capture["support_radius"], CYAN, 1.2, "-"),
        (groove_w, groove_h, groove_r, BLUE, 1.2, "-"),
        (float(C["INSERT_FRONT_WIDTH"]), float(C["INSERT_FRONT_HEIGHT"]), float(C["INSERT_OUTER_CORNER_RADIUS"]), ORANGE, 1.2, "--"),
        (inner_w, inner_h, inner_r, BLUE, 1.2, "-"),
        (inner_w - 2.0 * lip, inner_h - 2.0 * lip, inner_r - lip, GREEN, 1.2, "-"),
    )
    for width, height, radius, color, linewidth, linestyle in contours:
        ax.add_patch(FancyBboxPatch((-width / 2.0, -height / 2.0), width, height, boxstyle=f"round,pad=0,rounding_size={radius}", fill=False, edgecolor=color, linewidth=linewidth, linestyle=linestyle))
    ax.text(0, 0, "OPEN INTERIOR", ha="center", va="center", fontsize=9, color=GRAY)
    dimension(ax, (-back_w / 2.0, -35), (back_w / 2.0, -35), f"EFFECTIVE BACK WIDTH = {back_w:.2f} mm")
    dimension(ax, (50, -back_h / 2.0), (50, back_h / 2.0), f"EFFECTIVE BACK HEIGHT = {back_h:.2f} mm")
    side = panel(fig, [0.73, 0.13, 0.21, 0.72], "RADIUS DERIVATION")
    side.axis("off")
    note(side, 0.04, 0.93, "OUTER GROOVE", ["R = INSERT_OUTER_CORNER_RADIUS", "+ SLEEVE_CAPTURE_FIT_CLEARANCE", f"= {groove_r:.2f} mm"], BLUE)
    note(side, 0.04, 0.61, "INNER GROOVE", ["R = sleeve inner radius", "− fit clearance", f"= {inner_r:.2f} mm"], ORANGE)
    note(side, 0.04, 0.34, "LIP OPENING", ["R = groove inner radius", "− retaining-lip thickness", f"= {inner_r - lip:.2f} mm"], GREEN)
    pdf.savefig(fig)
    plt.close(fig)


def page_back_shell(pdf):
    fig = new_page(5, "BACK SHELL, DOME, FAN AND VENT", "Plan dimensions preserve the original fan opening and internal hardware")
    ax = panel(fig, [0.06, 0.13, 0.64, 0.72], "FRONT / FAN-FACE PLAN")
    ax.set_xlim(-52, 52)
    ax.set_ylim(-37, 37)
    ax.set_aspect("equal")
    capture = resolved_capture_geometry()
    width = capture["back_width"]
    height = capture["back_height"]
    radius = capture["back_radius"]
    ax.add_patch(FancyBboxPatch((-width / 2, -height / 2), width, height, boxstyle=f"round,pad=0,rounding_size={radius}", facecolor=LIGHT, edgecolor=BLUE, linewidth=1.5))
    fan_x = float(C["FAN_CENTER_X"])
    fan_z = float(C["FAN_CENTER_Z"])
    fan_r = float(C["FAN_OPENING_DIAMETER"]) / 2.0
    ax.add_patch(Circle((fan_x, fan_z), fan_r, facecolor=WHITE, edgecolor=ORANGE, linewidth=1.4))
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            x = fan_x + sx * float(C["FAN_HOLE_SPACING_X"]) / 2.0
            z = fan_z + sz * float(C["FAN_HOLE_SPACING_Z"]) / 2.0
            ax.add_patch(Circle((x, z), float(C["FAN_HOLE_DIAMETER"]) / 2.0, facecolor=WHITE, edgecolor=BLUE))
    for x, z in C["CASE_FASTENER_POSITIONS_XZ"]:
        ax.add_patch(Circle((x, z), float(C["BACK_FASTENER_BOSS_DIAMETER"]) / 2.0, fill=False, edgecolor=RED, linewidth=1.1))
    dimension(ax, (fan_x - fan_r, fan_z - 23), (fan_x + fan_r, fan_z - 23), f"FAN_OPENING_DIAMETER = {fmt(C['FAN_OPENING_DIAMETER'])} mm", ORANGE)
    dimension(ax, (fan_x - float(C["FAN_HOLE_SPACING_X"]) / 2.0, 24), (fan_x + float(C["FAN_HOLE_SPACING_X"]) / 2.0, 24), f"FAN_HOLE_SPACING_X = {fmt(C['FAN_HOLE_SPACING_X'])} mm")
    side = panel(fig, [0.73, 0.13, 0.21, 0.72], "DEPTH / OPTIONS")
    side.axis("off")
    envelope_label = "effective" if capture["enabled"] else "legacy active"
    note(side, 0.04, 0.93, "BACK SHELL", [f"depth {fmt(C['BACK_DEPTH'])} mm", f"{envelope_label} {width:.2f} × {height:.2f} mm", f"{envelope_label} corner R {radius:.2f} mm"], BLUE)
    note(side, 0.04, 0.65, "DOME", [f"enabled {C['BACK_DOME_ENABLED']}", f"depth {fmt(C['BACK_DOME_DEPTH'])} mm", f"fan pad {fmt(C['BACK_DOME_FAN_PAD_WIDTH'])} × {fmt(C['BACK_DOME_FAN_PAD_HEIGHT'])} mm"], GREEN)
    note(side, 0.04, 0.36, "VENT", [f"enabled {C['VENT_ENABLED']}", f"opening {fmt(C['VENT_WIDTH'])} × {fmt(C['VENT_HEIGHT'])} mm", f"slats {fmt(C['VENT_SLAT_COUNT'])} at {fmt(C['VENT_SLAT_ANGLE_DEG'])}°"], ORANGE)
    pdf.savefig(fig)
    plt.close(fig)


def page_insert(pdf):
    capture_enabled = bool(C["SLEEVE_CAPTURE_SLOT_ENABLED"])
    subtitle = (
        "The sleeve wall extends into the groove; bosses and port datums remain fixed"
        if capture_enabled
        else "Capture slot disabled; sleeve begins at the original boss datum"
    )
    fig = new_page(6, "INSERT SLEEVE, PORTS AND ACCESS", subtitle)
    ax = panel(fig, [0.06, 0.13, 0.57, 0.72], "INSERT FRONT CONTOUR")
    ax.set_xlim(-50, 50)
    ax.set_ylim(-35, 35)
    ax.set_aspect("equal")
    outer_w = float(C["INSERT_FRONT_WIDTH"])
    outer_h = float(C["INSERT_FRONT_HEIGHT"])
    inner_w = outer_w - 2.0 * float(C["INSERT_WALL_X"])
    inner_h = outer_h - 2.0 * float(C["INSERT_WALL_Z"])
    outer_r = float(C["INSERT_OUTER_CORNER_RADIUS"])
    inner_r = outer_r - max(float(C["INSERT_WALL_X"]), float(C["INSERT_WALL_Z"]))
    if not capture_enabled:
        inner_r = min(max(inner_r, 0.5), inner_w / 2.0, inner_h / 2.0)
    ax.add_patch(FancyBboxPatch((-outer_w / 2, -outer_h / 2), outer_w, outer_h, boxstyle=f"round,pad=0,rounding_size={outer_r}", facecolor="#f8dfd2", edgecolor=ORANGE, linewidth=1.5))
    ax.add_patch(FancyBboxPatch((-inner_w / 2, -inner_h / 2), inner_w, inner_h, boxstyle=f"round,pad=0,rounding_size={inner_r}", facecolor=WHITE, edgecolor=ORANGE, linewidth=1.0))
    dimension(ax, (-outer_w / 2, -33), (outer_w / 2, -33), f"INSERT_FRONT_WIDTH = {fmt(C['INSERT_FRONT_WIDTH'])} mm", ORANGE)
    dimension(ax, (48, -outer_h / 2), (48, outer_h / 2), f"INSERT_FRONT_HEIGHT = {fmt(C['INSERT_FRONT_HEIGHT'])} mm", ORANGE)
    dimension(ax, (inner_w / 2, 0), (outer_w / 2, 0), f"WALL_X = {fmt(C['INSERT_WALL_X'])} mm", BLUE)
    dimension(ax, (0, inner_h / 2), (0, outer_h / 2), f"WALL_Z = {fmt(C['INSERT_WALL_Z'])} mm", BLUE)
    side = panel(fig, [0.66, 0.13, 0.28, 0.72], "DEPTH AND OPENINGS")
    side.axis("off")
    active_extension = C["SLEEVE_CAPTURE_ENGAGEMENT_DEPTH"] if capture_enabled else 0.0
    note(side, 0.04, 0.94, "SLEEVE DEPTH", [f"body depth {fmt(C['INSERT_DEPTH'])} mm", f"active leading extension {fmt(active_extension)} mm", f"rear {fmt(C['INSERT_REAR_WIDTH'])} × {fmt(C['INSERT_REAR_HEIGHT'])} mm"], ORANGE)
    note(side, 0.04, 0.70, "BOTTOM ACCESS", [f"enabled {C['BOTTOM_ACCESS_ENABLED']}", f"{fmt(C['BOTTOM_ACCESS_WIDTH'])} × {fmt(C['BOTTOM_ACCESS_DEPTH'])} mm", f"Y offset {fmt(C['BOTTOM_ACCESS_Y_OFFSET'])} mm"], BLUE)
    note(side, 0.04, 0.46, "SIDE / TOP PORTS", [f"left Ø {fmt(C['LEFT_ROUND_PORT_DIAMETER'])} mm", f"USB {fmt(C['RIGHT_USB_PORT_WIDTH_Y'])} × {fmt(C['RIGHT_USB_PORT_HEIGHT_Z'])} mm", f"top Ø {fmt(C['TOP_PORT_DIAMETER'])} mm"], GREEN)
    note(side, 0.04, 0.22, "CAPTIVE BUTTONS · PRINT 2 IN TPU", [f"stem Ø {fmt(C['BUTTON_STEM_DIAMETER'])} · height {fmt(C['BUTTON_TOTAL_HEIGHT'])} mm", f"inside flange Ø {fmt(C['BUTTON_INNER_FLANGE_DIAMETER'])} × {fmt(C['BUTTON_INNER_FLANGE_THICKNESS'])} mm", f"snap rim Ø {fmt(C['BUTTON_RETENTION_RIM_DIAMETER'])} mm · install from inside"], RED)
    pdf.savefig(fig)
    plt.close(fig)


def page_fasteners(pdf):
    capture_enabled = bool(C["SLEEVE_CAPTURE_SLOT_ENABLED"])
    subtitle = (
        "Retention geometry remains open and serviceable after adding the groove"
        if capture_enabled
        else "Retention geometry in the active legacy socket configuration"
    )
    fig = new_page(7, "FASTENERS, HEX CAPTURE, RETAINER AND SNAPS", subtitle)
    left = panel(fig, [0.06, 0.14, 0.42, 0.69], "HEX PART AND TWO RETAINING TABS", "Section across one rear fastener")
    left.set_xlim(-5, 5)
    left.set_ylim(-1, 8)
    hex_w = float(C["BACK_FASTENER_HEX_WIDTH_X"])
    hex_h = float(C["BACK_FASTENER_HEX_HEIGHT_Z"])
    hex_center_y = 3.5
    hex_points = (
        (hex_w / 2.0, hex_center_y),
        (hex_w / 4.0, hex_center_y + hex_h / 2.0),
        (-hex_w / 4.0, hex_center_y + hex_h / 2.0),
        (-hex_w / 2.0, hex_center_y),
        (-hex_w / 4.0, hex_center_y - hex_h / 2.0),
        (hex_w / 4.0, hex_center_y - hex_h / 2.0),
    )
    left.add_patch(Polygon(hex_points, closed=True, facecolor="#d8b66a", edgecolor=INK))
    projection = float(C["BACK_FASTENER_RETENTION_TAB_PROTRUSION"])
    left.add_patch(Rectangle((-0.5, hex_center_y + hex_h / 2.0 - projection), 1.0, projection, facecolor=BLUE))
    left.add_patch(Rectangle((-0.5, hex_center_y - hex_h / 2.0), 1.0, projection, facecolor=BLUE))
    left.add_patch(Circle((0, hex_center_y), float(C["BACK_FASTENER_HOLE_DIAMETER"]) / 2.0, facecolor=WHITE, edgecolor=RED))
    dimension(left, (-hex_w / 2, 6.8), (hex_w / 2, 6.8), f"HEX_WIDTH_X = {fmt(C['BACK_FASTENER_HEX_WIDTH_X'])} mm")
    left.text(0, 6.2, f"resolved tab projection = {projection:.2f} mm ({C['MATERIAL_MODE']})", ha="center", fontsize=7.0, color=ORANGE)
    contact_text = (
        f"minimum retained boss contact = {fmt(C['BACK_FASTENER_MIN_DATUM_CONTACT_AREA'])} mm²"
        if capture_enabled
        else "groove-related boss-contact threshold inactive"
    )
    left.text(0, 5.85, contact_text, ha="center", fontsize=7.0, color=GREEN)
    right = panel(fig, [0.52, 0.14, 0.42, 0.69], "ASSEMBLY RETENTION SUMMARY")
    right.axis("off")
    note(right, 0.04, 0.94, "THREE CASE FASTENERS", [f"back bore Ø {fmt(C['BACK_FASTENER_HOLE_DIAMETER'])} mm", f"insert bore Ø {fmt(C['INSERT_FASTENER_HOLE_DIAMETER'])} mm", f"socket clearance {fmt(C['FASTENER_BOSS_SOCKET_CLEARANCE'])} mm"], BLUE)
    note(right, 0.04, 0.70, "HEX SNAP", [f"part thickness {fmt(C['BACK_FASTENER_HEX_PART_THICKNESS_Y'])} mm", f"tab depth {fmt(C['BACK_FASTENER_RETENTION_TAB_DEPTH_Y'])} mm", f"seat offset {fmt(C['BACK_FASTENER_RETENTION_TAB_OFFSET_FROM_SEAT'])} mm"], ORANGE)
    note(right, 0.04, 0.46, "SLEEVE SNAP", [f"bump {fmt(C['SNAP_BUMP_PROTRUSION'])} mm", f"pocket clearance {fmt(C['SNAP_POCKET_CLEARANCE'])} mm", f"edge R {fmt(C['SNAP_EDGE_RADIUS'])} mm"], GREEN)
    if C["RETAINER_ENABLED"]:
        fastener_xs = [
            float(point[0]) for point in C["CASE_FASTENER_POSITIONS_XZ"]
        ]
        fastener_zs = sorted(
            float(point[1]) for point in C["CASE_FASTENER_POSITIONS_XZ"]
        )
        retainer_width = (
            max(fastener_xs)
            - min(fastener_xs)
            + 2.0 * float(C["RETAINER_HORIZONTAL_END_MARGIN_X"])
        )
        retainer_height = (
            fastener_zs[-1]
            + float(C["RETAINER_TOP_EDGE_MARGIN_Z"])
            - (
                fastener_zs[0]
                - float(C["RETAINER_LOWER_EDGE_MARGIN_Z"])
            )
        )
        retainer_lines = [
            f"overall {retainer_width:.2f} × {retainer_height:.2f} × {fmt(C['RETAINER_THICKNESS_Y'])} mm",
            f"3 holes Ø {fmt(C['RETAINER_HOLE_DIAMETER'])} mm on case axes",
            "retainer seats flush to the insert entry face",
        ]
    else:
        retainer_lines = ["disabled in this configuration"]
    note(right, 0.04, 0.22, "FRONT CAMERA RETAINER", retainer_lines, RED)
    pdf.savefig(fig)
    plt.close(fig)


def page_catalog(pdf):
    first_page = 8
    for page_offset in range(CATALOG_PAGE_COUNT):
        page_number = first_page + page_offset
        start = page_offset * CATALOG_PER_PAGE
        entries = CONFIG_ENTRIES[start : start + CATALOG_PER_PAGE]
        fig = new_page(page_number, "EXHAUSTIVE CONFIG CATALOG", f"Source-order entries {start + 1}–{start + len(entries)} of {len(CONFIG_ENTRIES)}")
        ax = fig.add_axes([0.06, 0.09, 0.88, 0.79])
        ax.axis("off")
        card_height = 0.115
        for row, entry in enumerate(entries):
            y_top = 0.985 - row * (card_height + 0.008)
            face = "#f6fafc" if row % 2 == 0 else WHITE
            ax.add_patch(FancyBboxPatch((0.0, y_top - card_height), 1.0, card_height, boxstyle="round,pad=0.006,rounding_size=0.008", transform=ax.transAxes, facecolor=face, edgecolor=GRID, linewidth=0.7))
            ax.text(0.014, y_top - 0.026, entry.name, transform=ax.transAxes, fontsize=7.4, weight="bold", color=BLUE, va="top")
            profile_note = " • resolved by material profile" if entry.profile_controlled else ""
            ax.text(0.014, y_top - 0.057, f"{entry.category} • {entry.unit} • source line {entry.source_line}{profile_note}", transform=ax.transAxes, fontsize=6.0, color=GRAY, va="top")
            value_text = textwrap.fill(fmt(entry.value), width=64, break_long_words=False, break_on_hyphens=False)
            ax.text(0.47, y_top - 0.025, value_text, transform=ax.transAxes, fontsize=6.3, color=ORANGE, va="top", family="DejaVu Sans Mono")
            description = textwrap.fill(entry.description, width=106, break_long_words=False, break_on_hyphens=False)
            ax.text(0.014, y_top - 0.086, description, transform=ax.transAxes, fontsize=6.15, color=INK, va="top")
        pdf.savefig(fig)
        plt.close(fig)


def page_coverage(pdf):
    fig = new_page(TOTAL_PAGES, "COVERAGE AND SYNCHRONIZATION PROOF", "The generated guide fails rather than silently omitting CONFIG assignments")
    ax = fig.add_axes([0.07, 0.14, 0.86, 0.70])
    ax.axis("off")
    categories = {}
    for entry in CONFIG_ENTRIES:
        categories[entry.category] = categories.get(entry.category, 0) + 1
    ax.add_patch(FancyBboxPatch((0.0, 0.70), 1.0, 0.26, boxstyle="round,pad=0.015,rounding_size=0.02", transform=ax.transAxes, facecolor=LIGHT, edgecolor=GRID))
    ax.text(0.04, 0.89, "CATALOG COVERAGE", transform=ax.transAxes, fontsize=12, weight="bold", color=BLUE)
    ax.text(0.04, 0.81, f"{len(CONFIG_ENTRIES)} / {len(EXPECTED_CONFIG_NAMES)} uppercase CONFIG assignments cataloged", transform=ax.transAxes, fontsize=10, weight="bold", color=GREEN)
    ax.text(0.04, 0.75, f"Model + generator fingerprint: source-{SOURCE_HASH}", transform=ax.transAxes, fontsize=7.4, color=GRAY)
    sorted_categories = sorted(categories.items())
    for index, (category, count) in enumerate(sorted_categories):
        column = index // 6
        row = index % 6
        x = 0.03 + column * 0.48
        y = 0.62 - row * 0.075
        ax.text(x, y, f"{count:>3}", transform=ax.transAxes, fontsize=8.0, weight="bold", color=ORANGE)
        ax.text(x + 0.05, y, category, transform=ax.transAxes, fontsize=7.1, color=INK)
    ax.add_patch(FancyBboxPatch((0.0, 0.04), 1.0, 0.13, boxstyle="round,pad=0.015,rounding_size=0.02", transform=ax.transAxes, facecolor=WHITE, edgecolor=BLUE))
    ax.text(0.03, 0.125, "SYNC CONTRACT", transform=ax.transAxes, fontsize=8.5, weight="bold", color=BLUE)
    ax.text(0.03, 0.075, "`make check-fan-case-dim-pdf-sync` verifies the source fingerprint, expected page count and PDF EOF marker. Any model or generator edit makes the existing local guide stale.", transform=ax.transAxes, fontsize=7.1, color=INK)
    pdf.savefig(fig)
    plt.close(fig)


def check_pdf_sync():
    if not OUTPUT_PDF.is_file():
        raise RuntimeError(f"Missing generated dimension guide: {OUTPUT_PDF}")
    data = OUTPUT_PDF.read_bytes()
    expected = f"source-{SOURCE_HASH}".encode("ascii")
    if expected not in data:
        raise RuntimeError(
            f"Stale dimension guide: {OUTPUT_PDF.name} does not contain "
            f"{expected.decode()}. Regenerate it with `make fan-case-dim-pdf`."
        )
    if not data.rstrip().endswith(b"%%EOF"):
        raise RuntimeError(f"Incomplete dimension guide: {OUTPUT_PDF.name} has no PDF EOF marker")
    page_count = len(re.findall(rb"/Type\s*/Page\b", data))
    if page_count != TOTAL_PAGES:
        raise RuntimeError(
            f"Incomplete dimension guide: {OUTPUT_PDF.name} has {page_count} pages; "
            f"expected {TOTAL_PAGES}."
        )
    print(f"Synchronized {OUTPUT_PDF} source={SOURCE_HASH} pages={TOTAL_PAGES}")


def main():
    handle = tempfile.NamedTemporaryFile(
        prefix=f".{OUTPUT_PDF.stem}.",
        suffix=".pdf.tmp",
        dir=OUTPUT_PDF.parent,
        delete=False,
    )
    temporary_path = Path(handle.name)
    handle.close()
    try:
        with PdfPages(
            temporary_path,
            metadata={
                "Title": "GoPro Fan-Case Exhaustive Configuration Dimension Guide",
                "Author": "Generated from gopro_fan_case_parametric_blender.py",
                "Subject": "Back shell, sleeve capture groove and insert dimensions",
                "Keywords": f"GoPro fan case TPU sleeve groove source-{SOURCE_HASH}",
            },
        ) as pdf:
            page_cover(pdf)
            page_assembly_datum(pdf)
            page_groove_section(pdf)
            page_groove_plan(pdf)
            page_back_shell(pdf)
            page_insert(pdf)
            page_fasteners(pdf)
            page_catalog(pdf)
            page_coverage(pdf)
        temporary_path.replace(OUTPUT_PDF)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    print(
        f"Wrote {OUTPUT_PDF} pages={TOTAL_PAGES} config={len(CONFIG_ENTRIES)} "
        f"source={SOURCE_HASH} missing=0"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-sync",
        action="store_true",
        help="verify the existing PDF against the model and this generator",
    )
    arguments = parser.parse_args()
    if arguments.check_sync:
        check_pdf_sync()
    else:
        main()
