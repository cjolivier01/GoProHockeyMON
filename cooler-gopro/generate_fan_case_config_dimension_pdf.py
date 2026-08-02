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
import struct
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Arc, Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle
from shapely import affinity
from shapely.geometry import MultiPolygon
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union


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
    ("Insert sleeve", ("SLEEVE_MATERIAL_", "INSERT_FRONT_", "INSERT_REAR_", "INSERT_DEPTH", "INSERT_OUTER_", "INSERT_WALL_")),
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
    "BACK_MATERIAL_MODE": "Selects RIGID or TPU geometry for the combined back shell/dome; TPU receives deeper captured-hex retention tabs.",
    "SLEEVE_MATERIAL_MODE": "Selects the hollow sleeve print material independently; current sleeve dimensions are shared by RIGID and TPU.",
    "RETAINER_MATERIAL_MODE": "Selects RIGID or TPU thickness independently for both front-retainer options.",
    "BUTTON_STEM_DIAMETER": "Diameter of the actuator shaft that slides through each circular sleeve port.",
    "BUTTON_TOTAL_HEIGHT": "Overall inside-to-outside actuator height, including its inner flange and exterior retention bead.",
    "BUTTON_INNER_FLANGE_THICKNESS": "Thickness of the flat camera-side flange that prevents the actuator escaping outward.",
    "BUTTON_INNER_FLANGE_DIAMETER": "Diameter of the camera-side contact flange and inward travel stop.",
    "BUTTON_RETENTION_RIM_DIAMETER": "Maximum diameter of the compressible exterior TPU bead that snaps through the sleeve port.",
    "BUTTON_RETENTION_RIM_HEIGHT": "Axial length reserved for the exterior snap-bead profile.",
    "BUTTON_RETENTION_SHOULDER_HEIGHT": "Short inward-facing taper that resists pulling the installed button back through the port.",
    "BUTTON_RETENTION_LEAD_IN_HEIGHT": "Tapered tip length that guides and compresses the TPU bead during inside-out installation.",
    "BUTTON_STL_NAME": "Output filename for one canonical captive button; print two copies in TPU.",
    "RETAINER_ENABLED": "Build and export both direct-on-M3 front-retainer options.",
    "RETAINER_STYLE": "Selects the assembled/combined retention option: SWING_GATE or ROTATING_KEEPERS; both printable STLs are exported.",
    "RETAINER_GATE_RIGID_THICKNESS_Y": "Swing-gate clamp thickness when RETAINER_MATERIAL_MODE is RIGID.",
    "RETAINER_GATE_TPU_THICKNESS_Y": "Increased swing-gate clamp thickness when RETAINER_MATERIAL_MODE is TPU.",
    "RETAINER_HORIZONTAL_END_MARGIN_X": "Horizontal material added beyond the leftmost and rightmost case-fastener axes.",
    "RETAINER_HORIZONTAL_BAR_HEIGHT_Z": "Full lower-bar height before the camera-clearance scallop is removed.",
    "RETAINER_LOWER_EDGE_MARGIN_Z": "Distance from the lower fastener row to the retainer's bottom edge.",
    "RETAINER_UPRIGHT_WIDTH_X": "Width of the narrow upright joining the right lower and upper fasteners.",
    "RETAINER_TOP_EDGE_MARGIN_Z": "Distance from the upper fastener axis to the retainer's top edge.",
    "RETAINER_RELIEF_RADIUS": "Radius of the large circular scallop that preserves camera clearance above the lower retaining strap.",
    "RETAINER_MIN_HOLE_WEB": "Minimum configured material outside the swing gate's direct-M3 pivot bearing and release tracks.",
    "RETAINER_GATE_BOLT_TRACK_DIAMETER": "Running diameter around the existing M3 shafts in the gate's pivot and curved lower release tracks.",
    "RETAINER_GATE_MIN_NUT_BEARING_DIAMETER": "Minimum recommended thumbnut or washer bearing diameter over the slotted gate.",
    "RETAINER_GATE_LOWER_LEFT_RELEASE_ANGLE_DEG": "Gate angle where the lower-left M3 track clears the plate edge.",
    "RETAINER_GATE_LOWER_RIGHT_RELEASE_ANGLE_DEG": "Gate angle where the lower-right M3 track fully clears into the camera relief.",
    "RETAINER_GATE_SWEEP_STEP_DEG": "Angular chord sampling used to form continuous rounded lower-bolt tracks.",
    "RETAINER_KEEPER_BOLT_HOLE_DIAMETER": "M3 running-hole diameter through each rotating keeper.",
    "RETAINER_KEEPER_HUB_DIAMETER": "Circular keeper hub diameter; sized to remain behind the camera-support runners when open.",
    "RETAINER_KEEPER_MIN_HOLE_WEB": "Minimum radial keeper material retained outside the M3 running hole.",
    "RETAINER_KEEPER_LOBE_WIDTH_X": "Tangential width of the rounded camera-blocking keeper lobe.",
    "RETAINER_KEEPER_CLOSED_PROJECTION_Z": "Distance from the M3 axis to the inward lobe tip in the closed position.",
    "RETAINER_KEEPER_RIGID_THICKNESS_Y": "Keeper clamp thickness when RETAINER_MATERIAL_MODE is RIGID; always thicker than the rigid gate.",
    "RETAINER_KEEPER_TPU_THICKNESS_Y": "Keeper clamp thickness when RETAINER_MATERIAL_MODE is TPU; always thicker than the TPU gate.",
    "RETAINER_KEEPER_INDEX_ENABLED": "Adds paired sleeve-face keys and matching keeper/gate slots for indexed 0/180-degree positions.",
    "RETAINER_KEEPER_INDEX_RADIAL_OFFSET": "Distance from each M3 axis to the center of each opposed index key and slot.",
    "RETAINER_KEEPER_INDEX_KEY_WIDTH_X": "Tangential width of each raised sleeve-face index key.",
    "RETAINER_KEEPER_INDEX_KEY_HEIGHT_Z": "Radial height of each raised sleeve-face index key.",
    "RETAINER_KEEPER_INDEX_KEY_PROJECTION_Y": "Axial height of each sleeve-face index key.",
    "RETAINER_KEEPER_INDEX_FIT_CLEARANCE": "Per-side keeper-slot clearance around each sleeve-face index key.",
    "RETAINER_KEEPER_INDEX_RECESS_DEPTH_Y": "Keeper/gate lift needed to disengage the index keys before turning or swinging.",
    "RETAINER_KEEPER_INDEX_KEY_BEVEL": "Edge bevel on the sleeve-face index keys for easier re-engagement.",
    "RETAINER_STL_NAME": "Output filename for the direct-M3 captive swing gate, exported flat for printing.",
    "RETAINER_KEEPER_STL_NAME": "Output filename for one indexed rotating keeper; print three in the selected material.",
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


def wrap_identifier(name: str, width: int = 24) -> str:
    """Wrap CONFIG identifiers at underscores without mangling words."""
    segments = re.findall(r"[^_]+_?", name)
    lines: list[str] = []
    current = ""
    for segment in segments:
        if current and len(current) + len(segment) > width:
            lines.append(current)
            current = segment
        else:
            current += segment
    if current:
        lines.append(current)
    return "\n".join(lines)


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
        if "_RIGID_BACK_MATERIAL_PROFILE" in names
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
    material_mode = source_config["BACK_MATERIAL_MODE"][0]
    profiles = env.get("BACK_MATERIAL_PROFILES", {})
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
PART_STLS = {
    "back": HERE / str(C["BACK_STL_NAME"]),
    "insert": HERE / str(C["INSERT_STL_NAME"]),
    "button": HERE / str(C["BUTTON_STL_NAME"]),
    "gate": HERE / str(C["RETAINER_STL_NAME"]),
    "keeper": HERE / str(C["RETAINER_KEEPER_STL_NAME"]),
}


def require_current_part_stls() -> None:
    missing = [path.name for path in PART_STLS.values() if not path.is_file()]
    if missing:
        raise RuntimeError(
            "Engineering drawings require the generated component STLs; "
            "run `make fan-case` first. Missing: " + ", ".join(missing)
        )
    source_mtime = MODEL_SOURCE.stat().st_mtime
    stale = [
        path.name
        for path in PART_STLS.values()
        if path.stat().st_mtime + 1.0e-6 < source_mtime
    ]
    if stale:
        raise RuntimeError(
            "Engineering-drawing STL projections are stale relative to the "
            "model source; run `make -B fan-case`. Stale: "
            + ", ".join(stale)
        )


require_current_part_stls()
SOURCE_HASH = hashlib.sha256(
    MODEL_SOURCE.read_bytes()
    + Path(__file__).read_bytes()
    + b"".join(path.read_bytes() for path in PART_STLS.values())
).hexdigest()[:12]


PHYSICAL_SETTING_NAMES = frozenset(
    {
        "CASE_FASTENER_POSITIONS_XZ",
        "CAMERA_STOP_SPECS",
        "LOCATING_TAB_SPECS",
        "LENS_CLEARANCE_GUIDE_TAPERS",
    }
)
VISUAL_DIMENSION_ENTRIES = tuple(
    entry
    for entry in CONFIG_ENTRIES
    if entry.unit != "setting" or entry.name in PHYSICAL_SETTING_NAMES
)
NON_DIMENSION_SETTING_ENTRIES = tuple(
    entry for entry in CONFIG_ENTRIES if entry not in VISUAL_DIMENSION_ENTRIES
)
DRAWINGS_PER_PAGE = 4
SETTINGS_PER_PAGE = 9


def drawing_view_for(entry: ConfigEntry) -> str:
    name = entry.name
    if name == "PRINT_BED_GAP":
        return "print_bed"
    if name.startswith(("BOOLEAN_", "CYLINDER_", "CORNER_")):
        return "mesh_quality"
    if name == "INSERT_DEPTH_SECTIONS":
        return "insert_side"
    if name in {"BACK_DOME_FAN_PAD_WIDTH", "BACK_DOME_FAN_PAD_HEIGHT"}:
        return "back_front"
    if name.startswith("BACK_DOME_") or name in {
        "BACK_DEPTH",
        "BACK_FACE_THICKNESS",
    } or name == "FAN_HOLE_BOSS_HEIGHT":
        return "back_side"
    if name.startswith("BACK_OUTER_") or name == "BACK_CORNER_RADIUS":
        return "back_front"
    if name in {
        "INSERTION_DEPTH",
        "SLEEVE_CAPTURE_ENGAGEMENT_DEPTH",
        "SLEEVE_CAPTURE_BOTTOM_CLEARANCE",
        "SLEEVE_CAPTURE_FLOOR_THICKNESS",
        "CAMERA_STOP_TO_INSERT_SOCKET_GAP",
    }:
        return "capture_section"
    if name.startswith(("SLEEVE_CAPTURE_", "FIT_CLEARANCE_")):
        return "capture_joint"
    if name.startswith(("FAN_", "VENT_")):
        return "back_front"
    if name in {
        "BACK_FASTENER_TO_INSERT_SOCKET_GAP",
        "BACK_FASTENER_HEX_SEAT_TO_INSERT",
        "BACK_FASTENER_HEX_TRANSITION_DEPTH",
        "BACK_FASTENER_HEX_PART_THICKNESS_Y",
        "BACK_FASTENER_RETENTION_TAB_DEPTH_Y",
        "BACK_FASTENER_RETENTION_TAB_OFFSET_FROM_SEAT",
        "BACK_FASTENER_RETENTION_TAB_BEVEL",
    }:
        return "fastener_section"
    if name.startswith(("CASE_FASTENER_", "BACK_FASTENER_", "INSERT_FASTENER_", "FASTENER_BOSS_")):
        return "fastener_detail"
    if name.startswith("CAMERA_STOP_") or name == "CAMERA_STOPS_ENABLED":
        return "camera_stops"
    if name.startswith("INSERT_"):
        return "insert_front" if name != "INSERT_DEPTH" else "insert_side"
    if name == "SNAP_BUMP_LENGTH_Z":
        return "snap_front"
    if name.startswith("SNAP_"):
        return "snap_detail"
    if name.endswith("_Y_OFFSET") or name in {
        "BOTTOM_ACCESS_DEPTH",
        "RIGHT_USB_PORT_WIDTH_Y",
    }:
        return "ports_side"
    if name.startswith(("BOTTOM_ACCESS_", "LEFT_ROUND_", "RIGHT_USB_", "TOP_PORT_")):
        return "ports_access"
    if name.startswith("BUTTON_"):
        return "button_profile"
    if name in {
        "RETAINER_KEEPER_RIGID_THICKNESS_Y",
        "RETAINER_KEEPER_TPU_THICKNESS_Y",
        "RETAINER_KEEPER_INDEX_KEY_PROJECTION_Y",
        "RETAINER_KEEPER_INDEX_RECESS_DEPTH_Y",
        "RETAINER_KEEPER_INDEX_KEY_BEVEL",
    }:
        return "keeper_side"
    if name.startswith("RETAINER_KEEPER_"):
        return "rotating_keeper"
    if name in {
        "RETAINER_GATE_RIGID_THICKNESS_Y",
        "RETAINER_GATE_TPU_THICKNESS_Y",
    }:
        return "gate_side"
    if name in {
        "RETAINER_GATE_LOWER_LEFT_RELEASE_ANGLE_DEG",
        "RETAINER_GATE_LOWER_RIGHT_RELEASE_ANGLE_DEG",
        "RETAINER_GATE_SWEEP_STEP_DEG",
    }:
        return "gate_sweep"
    if name.startswith("RETAINER_"):
        return "swing_gate"
    if name == "LENS_CLEARANCE_GUIDE_TAPERS":
        return "locating_side"
    if name.startswith(("LOCATING_", "LENS_CLEARANCE_")):
        return "locating_rails"
    if name.startswith("BACK_DOME_"):
        return "back_side"
    return "mesh_quality"


DRAWING_VIEW_ORDER = (
    "back_front",
    "back_side",
    "capture_joint",
    "capture_section",
    "fastener_detail",
    "fastener_section",
    "camera_stops",
    "insert_front",
    "insert_side",
    "ports_access",
    "ports_side",
    "locating_rails",
    "locating_side",
    "snap_detail",
    "snap_front",
    "button_profile",
    "swing_gate",
    "gate_side",
    "gate_sweep",
    "rotating_keeper",
    "keeper_side",
    "print_bed",
    "mesh_quality",
)
EXPANDED_DIMENSION_NAMES = frozenset(
    {
        "CAMERA_STOP_SPECS",
        "LOCATING_TAB_SPECS",
    }
)
entries_by_view = {view: [] for view in DRAWING_VIEW_ORDER}
for visual_entry in VISUAL_DIMENSION_ENTRIES:
    entries_by_view[drawing_view_for(visual_entry)].append(visual_entry)


def drawing_groups_for_view(entries):
    """Group ordinary callouts, reserving a full sheet for dense spec tables."""
    current = []
    for entry in entries:
        if entry.name in EXPANDED_DIMENSION_NAMES:
            if current:
                yield tuple(current)
                current = []
            yield (entry,)
            continue
        current.append(entry)
        if len(current) == DRAWINGS_PER_PAGE:
            yield tuple(current)
            current = []
    if current:
        yield tuple(current)


DRAWING_PAGE_GROUPS = tuple(
    (view, group)
    for view in DRAWING_VIEW_ORDER
    for group in drawing_groups_for_view(entries_by_view[view])
)
CURATED_PAGE_COUNT = 6
DRAWING_PAGE_COUNT = len(DRAWING_PAGE_GROUPS)
SETTINGS_PAGE_COUNT = math.ceil(
    len(NON_DIMENSION_SETTING_ENTRIES) / SETTINGS_PER_PAGE
)
CATALOG_PAGE_COUNT = DRAWING_PAGE_COUNT + SETTINGS_PAGE_COUNT
TOTAL_PAGES = 1 + CURATED_PAGE_COUNT + CATALOG_PAGE_COUNT + 1
GRAPHICALLY_ANNOTATED_NAMES: set[str] = set()
GRAPHICAL_ANNOTATION_KINDS: dict[str, str] = {}
GRAPHICAL_PRIMITIVE_RECORDS: dict[str, tuple[str, tuple[tuple[float, float], ...]]] = {}
CATALOGUED_SETTING_NAMES: set[str] = set()


def validate_drawing_plan() -> None:
    """Prove that every dimensional CONFIG entry is routed exactly once."""
    planned_names = [
        entry.name
        for _view, entries in DRAWING_PAGE_GROUPS
        for entry in entries
    ]
    expected_names = {entry.name for entry in VISUAL_DIMENSION_ENTRIES}
    duplicate_names = sorted(
        name for name in set(planned_names) if planned_names.count(name) != 1
    )
    missing_names = sorted(expected_names - set(planned_names))
    unexpected_names = sorted(set(planned_names) - expected_names)
    if duplicate_names or missing_names or unexpected_names:
        raise RuntimeError(
            "Invalid engineering-drawing plan: "
            f"duplicates={duplicate_names}, missing={missing_names}, "
            f"unexpected={unexpected_names}"
        )


validate_drawing_plan()
VISUAL_MANIFEST_HASH = hashlib.sha256(
    "\n".join(
        f"{view}:{entry.name}:{entry.unit}"
        for view, entries in DRAWING_PAGE_GROUPS
        for entry in entries
    ).encode("utf-8")
).hexdigest()[:12]
VISUAL_COVERAGE_MARKER = (
    f"engineering-dimensions-{len(VISUAL_DIMENSION_ENTRIES)}-of-"
    f"{len(VISUAL_DIMENSION_ENTRIES)}-manifest-{VISUAL_MANIFEST_HASH}"
)
SETTINGS_COVERAGE_MARKER = (
    f"settings-{len(NON_DIMENSION_SETTING_ENTRIES)}-of-"
    f"{len(NON_DIMENSION_SETTING_ENTRIES)}"
)


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


def boss_assembly_datum_y() -> float:
    return float(C["BACK_DEPTH"]) - float(C["INSERTION_DEPTH"])


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
        ("DETAIL DRAWINGS", str(DRAWING_PAGE_COUNT)),
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
        (
            f"8–{7 + DRAWING_PAGE_COUNT}",
            "STL-derived engineering views with every dimensional CONFIG callout",
        ),
        (
            f"{8 + DRAWING_PAGE_COUNT}–{TOTAL_PAGES - 1}",
            "Non-dimensional settings appendix with actual assembly references",
        ),
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
    fig = new_page(7, "FASTENERS, QUICK RETAINERS AND SNAPS", subtitle)
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
    left.text(0, 6.2, f"resolved tab projection = {projection:.2f} mm ({C['BACK_MATERIAL_MODE']} back)", ha="center", fontsize=7.0, color=ORANGE)
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
    note(right, 0.04, 0.46, "SLEEVE SNAP", [f"{C['SLEEVE_MATERIAL_MODE']}; bump {fmt(C['SNAP_BUMP_PROTRUSION'])} mm", f"pocket clearance {fmt(C['SNAP_POCKET_CLEARANCE'])} mm", f"edge R {fmt(C['SNAP_EDGE_RADIUS'])} mm"], GREEN)
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
        gate_thickness = (
            C["RETAINER_GATE_TPU_THICKNESS_Y"]
            if C["RETAINER_MATERIAL_MODE"] == "TPU"
            else C["RETAINER_GATE_RIGID_THICKNESS_Y"]
        )
        keeper_thickness = (
            C["RETAINER_KEEPER_TPU_THICKNESS_Y"]
            if C["RETAINER_MATERIAL_MODE"] == "TPU"
            else C["RETAINER_KEEPER_RIGID_THICKNESS_Y"]
        )
        retainer_lines = [
            f"active {C['RETAINER_STYLE']}; both STLs exported",
            f"{C['RETAINER_MATERIAL_MODE']} gate {retainer_width:.2f} × {retainer_height:.2f} × {fmt(gate_thickness)} mm on M3 shafts",
            "loosen all three thumbnuts; lift/swing without removal",
            f"3 {C['RETAINER_MATERIAL_MODE']} keepers: {fmt(keeper_thickness)} mm thick; Ø {fmt(C['RETAINER_KEEPER_HUB_DIAMETER'])} hub; lift {fmt(C['RETAINER_KEEPER_INDEX_RECESS_DEPTH_Y'])} mm, turn 180°",
        ]
    else:
        retainer_lines = ["disabled in this configuration"]
    note(right, 0.04, 0.235, "QUICK FRONT RETAINER OPTIONS", retainer_lines, RED)
    pdf.savefig(fig)
    plt.close(fig)


VIEW_TITLES = {
    "back_front": "BACK SHELL / DOME — ACTUAL FRONT PROJECTION",
    "back_side": "BACK SHELL / DOME — ACTUAL SIDE PROJECTION",
    "capture_joint": "ASSEMBLED BACK + SLEEVE — ACTUAL FRONT PROJECTION",
    "capture_section": "SLEEVE CAPTURE — ACTUAL AXIAL SECTION PROJECTION",
    "fastener_detail": "CASE FASTENERS ON ACTUAL BACK + SLEEVE PROJECTION",
    "fastener_section": "FASTENER POST / HEX RETENTION — ACTUAL AXIAL PROJECTION",
    "camera_stops": "CAMERA STOPS INSIDE ACTUAL BACK CONTOUR",
    "insert_front": "HOLLOW SLEEVE — ACTUAL FRONT PROJECTION",
    "insert_side": "HOLLOW SLEEVE — ACTUAL SIDE PROJECTION",
    "ports_access": "PORTS AND ACCESS ON ACTUAL SLEEVE PROJECTION",
    "ports_side": "PORT DEPTHS AND Y OFFSETS — ACTUAL SLEEVE SIDE PROJECTION",
    "locating_rails": "CAMERA RUNNERS ON ACTUAL SLEEVE CONTOUR",
    "locating_side": "CAMERA RUNNER TAPERS — ACTUAL SLEEVE SIDE PROJECTION",
    "snap_detail": "SLEEVE SNAP — ACTUAL TOP PROJECTION",
    "snap_front": "SLEEVE SNAP HEIGHT — ACTUAL FRONT PROJECTION",
    "button_profile": "CAPTIVE BUTTON — ACTUAL PRINTED PROFILE",
    "swing_gate": "SWING GATE — ACTUAL PRINTED OUTLINE",
    "gate_side": "SWING GATE MATERIAL THICKNESS — ACTUAL EDGE PROJECTION",
    "gate_sweep": "SWING GATE RELEASE — ACTUAL SWEEP OUTLINES",
    "rotating_keeper": "ROTATING KEEPER — ACTUAL PRINTED OUTLINE",
    "keeper_side": "ROTATING KEEPER INDEX / THICKNESS — ACTUAL EDGE PROJECTION",
    "print_bed": "PRINT-BED LAYOUT — ACTUAL PART OUTLINES",
    "mesh_quality": "MESH CONSTRUCTION ON ACTUAL RETAINER PARTS",
}


@lru_cache(maxsize=None)
def load_stl_triangles(part: str) -> np.ndarray:
    path = PART_STLS[part]
    data = path.read_bytes()
    if len(data) < 84:
        raise RuntimeError(f"Invalid STL header: {path}")
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    expected_size = 84 + 50 * triangle_count
    if len(data) != expected_size:
        raise RuntimeError(
            f"Engineering drawings require binary STL data; {path.name} has "
            f"{len(data)} bytes, expected {expected_size}"
        )
    triangles = np.empty((triangle_count, 3, 3), dtype=float)
    for index in range(triangle_count):
        values = struct.unpack_from("<12fH", data, 84 + 50 * index)
        triangles[index] = np.asarray(values[3:12], dtype=float).reshape(3, 3)
    return triangles


PROJECTION_AXES = {
    "xy": (0, 1),
    "xz": (0, 2),
    "yz": (1, 2),
}


@lru_cache(maxsize=None)
def projected_part_geometry(part: str, plane: str, flip_vertical: bool = False):
    coordinate_axes = PROJECTION_AXES[plane]
    polygons = []
    for triangle in load_stl_triangles(part):
        points = triangle[:, coordinate_axes]
        area_twice = abs(
            (points[1, 0] - points[0, 0]) * (points[2, 1] - points[0, 1])
            - (points[1, 1] - points[0, 1]) * (points[2, 0] - points[0, 0])
        )
        if area_twice <= 1.0e-8:
            continue
        polygon = ShapelyPolygon(points)
        if polygon.is_valid and polygon.area > 1.0e-8:
            polygons.append(polygon)
    if not polygons:
        raise RuntimeError(f"No projected area for {part} in {plane}")
    geometry = unary_union(polygons)
    if flip_vertical:
        geometry = affinity.scale(geometry, xfact=1.0, yfact=-1.0, origin=(0, 0))
    return geometry


def geometry_polygons(geometry):
    if geometry.geom_type == "Polygon":
        return (geometry,)
    if isinstance(geometry, MultiPolygon):
        return tuple(geometry.geoms)
    return tuple(
        item for item in geometry.geoms if item.geom_type == "Polygon"
    )


def draw_projected_geometry(
    ax,
    geometry,
    facecolor,
    edgecolor,
    alpha: float = 1.0,
    linewidth: float = 1.1,
    linestyle: str = "-",
    zorder: float = 1.0,
):
    for polygon in geometry_polygons(geometry):
        ax.add_patch(
            Polygon(
                np.asarray(polygon.exterior.coords),
                closed=True,
                facecolor=facecolor,
                edgecolor=edgecolor,
                alpha=alpha,
                linewidth=linewidth,
                linestyle=linestyle,
                zorder=zorder,
            )
        )
        for interior in polygon.interiors:
            ax.add_patch(
                Polygon(
                    np.asarray(interior.coords),
                    closed=True,
                    facecolor="#fbfdfe",
                    edgecolor=edgecolor,
                    linewidth=max(0.55, linewidth * 0.7),
                    linestyle=linestyle,
                    zorder=zorder + 0.1,
                )
            )


def set_drawing_bounds(ax, bounds, padding_fraction: float = 0.10):
    minimum_x, minimum_y, maximum_x, maximum_y = bounds
    width = max(maximum_x - minimum_x, 1.0)
    height = max(maximum_y - minimum_y, 1.0)
    padding_x = width * padding_fraction
    padding_y = height * padding_fraction
    ax.set_xlim(minimum_x - padding_x, maximum_x + padding_x)
    ax.set_ylim(minimum_y - padding_y, maximum_y + padding_y)
    ax.set_aspect("equal", adjustable="box")


def union_bounds(geometries):
    minimum_x = min(geometry.bounds[0] for geometry in geometries)
    minimum_y = min(geometry.bounds[1] for geometry in geometries)
    maximum_x = max(geometry.bounds[2] for geometry in geometries)
    maximum_y = max(geometry.bounds[3] for geometry in geometries)
    return minimum_x, minimum_y, maximum_x, maximum_y


def retainer_layout_for_drawings():
    """Resolve the gate datums using the same equations as the model."""
    ordered = sorted(C["CASE_FASTENER_POSITIONS_XZ"], key=lambda point: point[1])
    lower_left, lower_right = sorted(ordered[:2], key=lambda point: point[0])
    upper = ordered[2]
    minimum_x = min(float(point[0]) for point in ordered)
    maximum_x = max(float(point[0]) for point in ordered)
    bar_bottom_z = float(lower_left[1]) - float(C["RETAINER_LOWER_EDGE_MARGIN_Z"])
    bar_top_z = bar_bottom_z + float(C["RETAINER_HORIZONTAL_BAR_HEIGHT_Z"])
    upright_top_z = float(upper[1]) + float(C["RETAINER_TOP_EDGE_MARGIN_Z"])
    return {
        "lower_left": tuple(map(float, lower_left)),
        "lower_right": tuple(map(float, lower_right)),
        "upper": tuple(map(float, upper)),
        "bar_left_x": minimum_x - float(C["RETAINER_HORIZONTAL_END_MARGIN_X"]),
        "bar_right_x": maximum_x + float(C["RETAINER_HORIZONTAL_END_MARGIN_X"]),
        "bar_bottom_z": bar_bottom_z,
        "bar_top_z": bar_top_z,
        "upright_left_x": float(upper[0]) - float(C["RETAINER_UPRIGHT_WIDTH_X"]) / 2.0,
        "upright_right_x": float(upper[0]) + float(C["RETAINER_UPRIGHT_WIDTH_X"]) / 2.0,
        "upright_top_z": upright_top_z,
    }


def capture_joint_detail_points(bounds):
    """Return enlarged NTS section endpoints for the six capture controls."""
    minimum_x, minimum_z, maximum_x, maximum_z = bounds
    scale = 10.0
    x_sleeve = minimum_x + 0.20 * (maximum_x - minimum_x)
    x_groove = x_sleeve + scale * float(C["SLEEVE_CAPTURE_FIT_CLEARANCE"])
    x_socket = x_sleeve + scale * float(C["FIT_CLEARANCE_X"])
    x_support = x_groove + scale * float(C["SLEEVE_CAPTURE_MIN_OUTER_WALL_X"])
    x_z_detail = maximum_x - 0.24 * (maximum_x - minimum_x)
    z_sleeve = minimum_z + 0.24 * (maximum_z - minimum_z)
    z_groove = z_sleeve + scale * float(C["SLEEVE_CAPTURE_FIT_CLEARANCE"])
    z_socket = z_sleeve + scale * float(C["FIT_CLEARANCE_Z"])
    z_support = z_groove + scale * float(C["SLEEVE_CAPTURE_MIN_OUTER_WALL_Z"])
    lip_opening = minimum_x + 0.43 * (maximum_x - minimum_x)
    lip_groove = lip_opening + scale * float(C["SLEEVE_CAPTURE_INNER_LIP_THICKNESS"])
    return {
        "FIT_CLEARANCE_X": ((x_sleeve, 10.0), (x_socket, 10.0)),
        "SLEEVE_CAPTURE_FIT_CLEARANCE": ((x_sleeve, 4.0), (x_groove, 4.0)),
        "SLEEVE_CAPTURE_MIN_OUTER_WALL_X": ((x_groove, -2.0), (x_support, -2.0)),
        "FIT_CLEARANCE_Z": ((x_z_detail, z_sleeve), (x_z_detail, z_socket)),
        "SLEEVE_CAPTURE_MIN_OUTER_WALL_Z": ((x_z_detail - 7.0, z_groove), (x_z_detail - 7.0, z_support)),
        "SLEEVE_CAPTURE_INNER_LIP_THICKNESS": ((lip_opening, -18.0), (lip_groove, -18.0)),
        "x_surfaces": (x_sleeve, x_groove, x_socket, x_support),
        "z_surfaces": (z_sleeve, z_groove, z_socket, z_support),
        "lip_surfaces": (lip_opening, lip_groove),
    }


def port_access_detail_points(bounds):
    minimum_x, minimum_z, maximum_x, maximum_z = bounds
    left_center = (minimum_x + 0.30 * (maximum_x - minimum_x), 10.0)
    top_center = (minimum_x + 0.68 * (maximum_x - minimum_x), 10.0)
    usb_center = (minimum_x + 0.68 * (maximum_x - minimum_x), -12.0)
    return {
        "left_center": left_center,
        "top_center": top_center,
        "usb_center": usb_center,
    }


def record_graphical_primitive(entry: ConfigEntry, kind: str, *points) -> None:
    converted = tuple((float(point[0]), float(point[1])) for point in points)
    GRAPHICAL_PRIMITIVE_RECORDS[entry.name] = (kind, converted)


def draw_actual_view(ax, view: str):
    """Draw an STL-derived orthographic projection and return its bounds."""
    if view in {"back_front", "fastener_detail", "camera_stops"}:
        back = projected_part_geometry("back", "xz")
        draw_projected_geometry(ax, back, "#dceaf3", BLUE, alpha=0.85)
        bounds = back.bounds
        if view == "back_front":
            fan_x = float(C["FAN_CENTER_X"])
            fan_z = float(C["FAN_CENTER_Z"])
            ax.add_patch(
                Circle(
                    (fan_x, fan_z),
                    float(C["FAN_OPENING_DIAMETER"]) / 2.0,
                    fill=False,
                    edgecolor=ORANGE,
                    linewidth=1.0,
                    linestyle="--" if not C["FAN_OPENING_ENABLED"] else "-",
                    zorder=5,
                )
            )
            for x_sign in (-1.0, 1.0):
                for z_sign in (-1.0, 1.0):
                    ax.add_patch(
                        Circle(
                            (
                                fan_x + x_sign * float(C["FAN_HOLE_SPACING_X"]) / 2.0,
                                fan_z + z_sign * float(C["FAN_HOLE_SPACING_Z"]) / 2.0,
                            ),
                            float(C["FAN_HOLE_BOSS_DIAMETER"]) / 2.0,
                            fill=False,
                            edgecolor=ORANGE,
                            linewidth=0.7,
                            zorder=5,
                        )
                    )
            pad_width = float(C["BACK_DOME_FAN_PAD_WIDTH"])
            pad_height = float(C["BACK_DOME_FAN_PAD_HEIGHT"])
            ax.add_patch(
                Rectangle(
                    (fan_x - pad_width / 2.0, fan_z - pad_height / 2.0),
                    pad_width,
                    pad_height,
                    fill=False,
                    edgecolor=GREEN,
                    linewidth=0.8,
                    linestyle="--",
                    zorder=5,
                )
            )
            vent_x = float(C["VENT_CENTER_X"])
            vent_z = float(C["VENT_CENTER_Z"])
            vent_width = float(C["VENT_WIDTH"])
            vent_height = float(C["VENT_HEIGHT"])
            ax.add_patch(
                FancyBboxPatch(
                    (vent_x - vent_width / 2.0, vent_z - vent_height / 2.0),
                    vent_width,
                    vent_height,
                    boxstyle=f"round,pad=0,rounding_size={float(C['VENT_CORNER_RADIUS'])}",
                    fill=False,
                    edgecolor=RED,
                    linewidth=0.9,
                    linestyle="-" if C["VENT_ENABLED"] else "--",
                    zorder=7,
                )
            )
            slat_count = int(C["VENT_SLAT_COUNT"])
            slat_spacing = vent_height / max(1, slat_count)
            slat_angle = math.radians(float(C["VENT_SLAT_ANGLE_DEG"]))
            slat_run = min(vent_width * 0.78, vent_height * 0.18)
            for slat_index in range(slat_count):
                center_z = vent_z - vent_height / 2.0 + (slat_index + 0.5) * slat_spacing
                dx = math.cos(slat_angle) * slat_run / 2.0
                dz = math.sin(slat_angle) * slat_run / 2.0
                ax.plot(
                    (vent_x - dx, vent_x + dx),
                    (center_z - dz, center_z + dz),
                    color=RED,
                    linewidth=max(0.45, float(C["VENT_SLAT_WIDTH"]) * 0.45),
                    linestyle="-" if C["VENT_ENABLED"] else "--",
                    alpha=0.8,
                    zorder=7,
                )
            if not C["VENT_ENABLED"]:
                ax.text(
                    vent_x,
                    vent_z - vent_height / 2.0 - 2.0,
                    "CONFIGURED VENT — DISABLED",
                    fontsize=4.8,
                    color=RED,
                    ha="center",
                    va="top",
                    zorder=8,
                )
        elif view == "fastener_detail":
            insert = projected_part_geometry("insert", "xz")
            draw_projected_geometry(
                ax,
                insert,
                "none",
                ORANGE,
                alpha=0.85,
                linewidth=0.85,
                linestyle="--",
                zorder=4,
            )
            bounds = union_bounds((back, insert))
            for index, (x, z) in enumerate(C["CASE_FASTENER_POSITIONS_XZ"], start=1):
                ax.add_patch(
                    Circle(
                        (x, z),
                        float(C["INSERT_FASTENER_BOSS_DIAMETER"]) / 2.0,
                        fill=False,
                        edgecolor=ORANGE,
                        linewidth=1.0,
                        linestyle="--",
                        zorder=5,
                    )
                )
                ax.add_patch(
                    Circle(
                        (x, z),
                        float(C["BACK_FASTENER_BOSS_DIAMETER"]) / 2.0,
                        fill=False,
                        edgecolor=RED,
                        linewidth=1.3,
                        zorder=5,
                    )
                )
                ax.add_patch(
                    Circle(
                        (x, z),
                        float(C["INSERT_FASTENER_HOLE_DIAMETER"]) / 2.0,
                        fill=False,
                        edgecolor=RED,
                        linewidth=0.7,
                        linestyle=":",
                        zorder=6,
                    )
                )
                ax.text(
                    x,
                    z,
                    f"P{index}\n({fmt(x)}, {fmt(z)})",
                    fontsize=5.4,
                    ha="center",
                    va="center",
                    color=RED,
                    weight="bold",
                    zorder=6,
                )
            hex_width = float(C["BACK_FASTENER_HEX_WIDTH_X"])
            hex_height = float(C["BACK_FASTENER_HEX_HEIGHT_Z"])
            hex_x, hex_z = C["CASE_FASTENER_POSITIONS_XZ"][0]
            hex_points = [
                (
                    hex_x + math.cos(math.radians(30.0 + 60.0 * vertex)) * hex_width / 2.0,
                    hex_z + math.sin(math.radians(30.0 + 60.0 * vertex)) * hex_height / 2.0,
                )
                for vertex in range(6)
            ]
            ax.add_patch(
                Polygon(
                    hex_points,
                    closed=True,
                    fill=False,
                    edgecolor=ORANGE,
                    linewidth=1.0,
                    linestyle="--",
                    zorder=7,
                )
            )
        elif view == "camera_stops":
            ax.axhline(0.0, color=GRAY, linewidth=0.5, linestyle=":", zorder=4)
            ax.axvline(0.0, color=GRAY, linewidth=0.5, linestyle=":", zorder=4)
            for spec in C["CAMERA_STOP_SPECS"]:
                name, x0, x1, z0, z1, _attachment = spec
                ax.add_patch(
                    Rectangle(
                        (x0, z0),
                        x1 - x0,
                        z1 - z0,
                        facecolor=ORANGE,
                        edgecolor=RED,
                        alpha=0.72,
                        linewidth=0.8,
                        zorder=5,
                    )
                )
                ax.text(
                    (x0 + x1) / 2.0,
                    (z0 + z1) / 2.0,
                    name.replace("_", "\n"),
                    fontsize=4.1,
                    ha="center",
                    va="center",
                    color=INK,
                    zorder=6,
                )
            table_lines = [
                f"{name}: X {fmt(x0)}..{fmt(x1)}  Z {fmt(z0)}..{fmt(z1)} mm"
                for name, x0, x1, z0, z1, _attachment in C["CAMERA_STOP_SPECS"]
            ]
            ax.text(
                0.0,
                10.0,
                "CAMERA-STOP DATUM TABLE\n" + "\n".join(table_lines),
                fontsize=4.2,
                family="monospace",
                ha="center",
                va="center",
                color=INK,
                bbox={"facecolor": WHITE, "edgecolor": RED, "alpha": 0.90, "pad": 3.0},
                zorder=9,
            )
        return bounds
    if view == "back_side":
        back = projected_part_geometry("back", "yz")
        draw_projected_geometry(ax, back, "#dceaf3", BLUE, alpha=0.9)
        for station in range(1, int(C["BACK_DOME_SECTIONS"])):
            y = back.bounds[0] + station * (back.bounds[2] - back.bounds[0]) / int(C["BACK_DOME_SECTIONS"])
            ax.plot(
                (y, y),
                (back.bounds[1], back.bounds[3]),
                color=GRID,
                linewidth=0.35,
                linestyle=":",
                zorder=4,
            )
        outline = max(geometry_polygons(back), key=lambda polygon: polygon.area).exterior
        loop_points = int(C["BACK_DOME_LOOP_POINTS"])
        samples = [
            outline.interpolate(index / loop_points, normalized=True)
            for index in range(loop_points)
        ]
        ax.scatter(
            [sample.x for sample in samples],
            [sample.y for sample in samples],
            s=1.8,
            facecolors=WHITE,
            edgecolors=BLUE,
            linewidths=0.25,
            alpha=0.75,
            zorder=5,
        )
        return back.bounds
    if view == "capture_joint":
        back = projected_part_geometry("back", "xz")
        insert = projected_part_geometry("insert", "xz")
        draw_projected_geometry(ax, back, "#dceaf3", BLUE, alpha=0.68)
        draw_projected_geometry(ax, insert, "#f7d9ca", ORANGE, alpha=0.80, zorder=3)
        bounds = union_bounds((back, insert))
        detail = capture_joint_detail_points(bounds)
        for x, color in zip(
            detail["x_surfaces"],
            (ORANGE, RED, BLUE, GREEN),
        ):
            ax.plot((x, x), (-6.0, 14.0), color=color, linewidth=1.05, zorder=9)
        for z, color in zip(
            detail["z_surfaces"],
            (ORANGE, RED, BLUE, GREEN),
        ):
            ax.plot((detail["FIT_CLEARANCE_Z"][0][0] - 10.0, detail["FIT_CLEARANCE_Z"][0][0] + 3.0), (z, z), color=color, linewidth=1.05, zorder=9)
        for x, color in zip(detail["lip_surfaces"], (RED, GREEN)):
            ax.plot((x, x), (-22.0, -14.0), color=color, linewidth=1.15, zorder=9)
        ax.text(
            sum(detail["lip_surfaces"]) / 2.0,
            -23.0,
            "INNER GROOVE → CAPTURE OPENING (ENLARGED NTS)",
            fontsize=4.1,
            color=RED,
            ha="center",
            va="top",
            zorder=10,
        )
        ax.text(
            bounds[0] + 0.5 * (bounds[2] - bounds[0]),
            22.0,
            "ENLARGED PERIMETER SECTIONS — NTS\nORANGE sleeve · RED groove · BLUE socket · GREEN support",
            fontsize=5.2,
            color=BLUE,
            weight="bold",
            ha="center",
            zorder=10,
        )
        return bounds
    if view in {"capture_section", "fastener_section"}:
        back = projected_part_geometry("back", "yz")
        insert = projected_part_geometry("insert", "yz")
        draw_projected_geometry(ax, back, "#dceaf3", BLUE, alpha=0.65)
        draw_projected_geometry(ax, insert, "#f7d9ca", ORANGE, alpha=0.72, zorder=3)
        datum_y = boss_assembly_datum_y()
        ax.axvline(datum_y, color=RED, linewidth=0.8, linestyle="--", zorder=6)
        ax.text(
            datum_y,
            max(back.bounds[3], insert.bounds[3]),
            "BOSS DATUM Y",
            fontsize=5.0,
            color=RED,
            ha="center",
            va="bottom",
            zorder=7,
        )
        if view == "fastener_section":
            section_z = float(C["CASE_FASTENER_POSITIONS_XZ"][0][1])
            boss_radius = float(C["BACK_FASTENER_BOSS_DIAMETER"]) / 2.0
            ax.add_patch(
                Rectangle(
                    (datum_y - float(C["BACK_FASTENER_HEX_PART_THICKNESS_Y"]), section_z - boss_radius),
                    float(C["BACK_FASTENER_HEX_PART_THICKNESS_Y"]),
                    2.0 * boss_radius,
                    facecolor="#f6d8b8",
                    edgecolor=ORANGE,
                    linewidth=0.9,
                    alpha=0.8,
                    zorder=7,
                )
            )
            ax.text(
                datum_y - float(C["BACK_FASTENER_HEX_PART_THICKNESS_Y"]) / 2.0,
                section_z,
                "HEX / TAB\nSECTION",
                fontsize=4.5,
                color=INK,
                ha="center",
                va="center",
                zorder=8,
            )
            bevel_scale = 8.0
            detail_left = datum_y + 2.0
            detail_bottom = section_z - 7.0
            detail_width = 4.8
            detail_height = 4.0
            detail_bevel = float(C["BACK_FASTENER_RETENTION_TAB_BEVEL"]) * bevel_scale
            ax.add_patch(
                Polygon(
                    (
                        (detail_left, detail_bottom),
                        (detail_left + detail_width, detail_bottom),
                        (detail_left + detail_width, detail_bottom + detail_height - detail_bevel),
                        (detail_left + detail_width - detail_bevel, detail_bottom + detail_height),
                        (detail_left, detail_bottom + detail_height),
                    ),
                    closed=True,
                    facecolor="#f5c9c9",
                    edgecolor=RED,
                    linewidth=0.9,
                    zorder=9,
                )
            )
            ax.text(
                detail_left + detail_width / 2.0,
                detail_bottom - 0.6,
                "RETENTION TAB EDGE ×8 — NTS",
                fontsize=3.8,
                color=RED,
                ha="center",
                va="top",
                zorder=10,
            )
            return (
                datum_y - 8.0,
                section_z - 9.0,
                datum_y + 10.0,
                section_z + 9.0,
            )
        ledge_y = (
            boss_assembly_datum_y()
            - float(C["SLEEVE_CAPTURE_ENGAGEMENT_DEPTH"])
            - float(C["SLEEVE_CAPTURE_BOTTOM_CLEARANCE"])
            - float(C["SLEEVE_CAPTURE_FLOOR_THICKNESS"])
        )
        return (
            ledge_y - 0.7,
            -10.0,
            float(C["BACK_DEPTH"]) + 0.8,
            10.0,
        )
    if view in {"insert_front", "ports_access", "locating_rails", "snap_front"}:
        insert = projected_part_geometry("insert", "xz")
        draw_projected_geometry(ax, insert, "#f7d9ca", ORANGE, alpha=0.88)
        bounds = insert.bounds
        if view == "ports_access":
            minimum_x, minimum_z, maximum_x, maximum_z = bounds
            port_markers = (
                (
                    (minimum_x, float(C["LEFT_ROUND_PORT_Z"])),
                    "LEFT ROUND",
                ),
                (
                    (maximum_x, float(C["RIGHT_USB_PORT_Z"])),
                    "USB",
                ),
                (
                    (float(C["TOP_PORT_X"]), maximum_z),
                    "TOP ROUND",
                ),
                ((0.0, minimum_z), "BOTTOM ACCESS"),
            )
            for (x, z), label in port_markers:
                ax.plot(x, z, marker="o", markersize=5, color=RED, zorder=6)
                ax.text(x, z + 2.3, label, fontsize=5.2, ha="center", color=RED)
            details = port_access_detail_points(bounds)
            port_radius = float(C["LEFT_ROUND_PORT_DIAMETER"]) / 2.0
            for center, label in (
                (details["left_center"], "LEFT PORT — FACE-NORMAL"),
                (details["top_center"], "TOP PORT — FACE-NORMAL"),
            ):
                ax.add_patch(
                    Circle(
                        center,
                        port_radius,
                        facecolor=WHITE,
                        edgecolor=RED,
                        linewidth=1.0,
                        zorder=8,
                    )
                )
                ax.plot(
                    (center[0] - port_radius - 1.0, center[0] + port_radius + 1.0),
                    (center[1], center[1]),
                    color=GRID,
                    linewidth=0.35,
                    zorder=7,
                )
                ax.plot(
                    (center[0], center[0]),
                    (center[1] - port_radius - 1.0, center[1] + port_radius + 1.0),
                    color=GRID,
                    linewidth=0.35,
                    zorder=7,
                )
                ax.text(center[0], center[1] - port_radius - 1.0, label, fontsize=3.9, color=RED, ha="center", va="top", zorder=9)
            usb_width = float(C["RIGHT_USB_PORT_WIDTH_Y"])
            usb_height = float(C["RIGHT_USB_PORT_HEIGHT_Z"])
            usb_radius = float(C["RIGHT_USB_PORT_CORNER_RADIUS"])
            usb_center = details["usb_center"]
            ax.add_patch(
                FancyBboxPatch(
                    (usb_center[0] - usb_width / 2.0, usb_center[1] - usb_height / 2.0),
                    usb_width,
                    usb_height,
                    boxstyle=f"round,pad=0,rounding_size={usb_radius}",
                    facecolor=WHITE,
                    edgecolor=RED,
                    linewidth=1.0,
                    zorder=8,
                )
            )
            ax.text(usb_center[0], usb_center[1] - usb_height / 2.0 - 1.0, "USB — FACE-NORMAL", fontsize=3.9, color=RED, ha="center", va="top", zorder=9)
            for source, target in (
                ((minimum_x, float(C["LEFT_ROUND_PORT_Z"])), details["left_center"]),
                ((float(C["TOP_PORT_X"]), maximum_z), details["top_center"]),
                ((maximum_x, float(C["RIGHT_USB_PORT_Z"])), details["usb_center"]),
            ):
                ax.plot((source[0], target[0]), (source[1], target[1]), color=GRAY, linewidth=0.45, linestyle=":", zorder=7)
        elif view == "locating_rails":
            ax.axhline(0.0, color=GRAY, linewidth=0.5, linestyle=":", zorder=4)
            ax.axvline(0.0, color=GRAY, linewidth=0.5, linestyle=":", zorder=4)
            for spec in C["LOCATING_TAB_SPECS"]:
                name, x0, x1, z0, z1, _attachment = spec
                ax.add_patch(
                    Rectangle(
                        (x0, z0),
                        x1 - x0,
                        z1 - z0,
                        facecolor=GREEN,
                        edgecolor=INK,
                        alpha=0.75,
                        linewidth=0.7,
                        zorder=5,
                    )
                )
                ax.text(
                    (x0 + x1) / 2.0,
                    (z0 + z1) / 2.0,
                    name.replace("_", "\n"),
                    fontsize=4.1,
                    ha="center",
                    va="center",
                    color=INK,
                    zorder=6,
                )
            table_lines = [
                f"{name}: X {fmt(x0)}..{fmt(x1)}  Z {fmt(z0)}..{fmt(z1)} mm"
                for name, x0, x1, z0, z1, _attachment in C["LOCATING_TAB_SPECS"]
            ]
            ax.text(
                0.0,
                7.0,
                "RUNNER DATUM TABLE\n" + "\n".join(table_lines),
                fontsize=4.1,
                family="monospace",
                ha="center",
                va="center",
                color=INK,
                bbox={"facecolor": WHITE, "edgecolor": GREEN, "alpha": 0.92, "pad": 3.0},
                zorder=9,
            )
        elif view == "snap_front":
            half_width = float(C["INSERT_FRONT_WIDTH"]) / 2.0
            snap_height = float(C["SNAP_BUMP_LENGTH_Z"])
            ax.add_patch(
                Rectangle(
                    (half_width, -snap_height / 2.0),
                    float(C["SNAP_BUMP_PROTRUSION"]),
                    snap_height,
                    facecolor=GREEN,
                    edgecolor=RED,
                    linewidth=0.9,
                    zorder=7,
                )
            )
        return bounds
    if view in {"ports_side", "locating_side"}:
        insert = projected_part_geometry("insert", "yz")
        draw_projected_geometry(ax, insert, "#f7d9ca", ORANGE, alpha=0.88)
        if view == "ports_side":
            port_records = (
                ("LEFT", float(C["LEFT_ROUND_PORT_Y_OFFSET"]), float(C["LEFT_ROUND_PORT_Z"])),
                ("USB", float(C["RIGHT_USB_PORT_Y_OFFSET"]), float(C["RIGHT_USB_PORT_Z"])),
                ("TOP", float(C["TOP_PORT_Y_OFFSET"]), insert.bounds[3]),
                ("BOTTOM", float(C["BOTTOM_ACCESS_Y_OFFSET"]), insert.bounds[1]),
            )
            datum_y = boss_assembly_datum_y()
            for label, offset, z in port_records:
                y = datum_y + offset
                ax.plot(y, z, marker="o", markersize=4.0, color=RED, zorder=7)
                ax.text(y, z + 2.0, label, fontsize=4.7, color=RED, ha="center", zorder=8)
        else:
            datum_y = insert.bounds[0]
            taper_length = max(
                float(spec[0]) for spec in C["LENS_CLEARANCE_GUIDE_TAPERS"].values()
            )
            projection = max(
                float(spec[1]) for spec in C["LENS_CLEARANCE_GUIDE_TAPERS"].values()
            )
            z = insert.bounds[3] - 4.0
            ax.add_patch(
                Polygon(
                    (
                        (datum_y, z),
                        (datum_y + taper_length, z),
                        (datum_y + taper_length, z - projection),
                        (datum_y, z - 2.0),
                    ),
                    closed=True,
                    facecolor="#d7efd9",
                    edgecolor=GREEN,
                    linewidth=0.9,
                    zorder=7,
                )
            )
            ax.text(datum_y + taper_length / 2.0, z + 1.2, "GUIDE TAPER", fontsize=4.8, color=GREEN, ha="center")
        return insert.bounds
    if view in {"insert_side", "snap_detail"}:
        plane = "yz" if view == "insert_side" else "xy"
        insert = projected_part_geometry("insert", plane)
        draw_projected_geometry(ax, insert, "#f7d9ca", ORANGE, alpha=0.90)
        if view == "snap_detail":
            start_y = float(C["BACK_DEPTH"]) - float(C["INSERTION_DEPTH"])
            center_y = (
                start_y
                + float(C["SNAP_BUMP_Y_OFFSET"])
                + float(C["SNAP_BUMP_LENGTH_Y"]) / 2.0
            )
            half_width = float(C["INSERT_FRONT_WIDTH"]) / 2.0
            for side in (-1.0, 1.0):
                protrusion = float(C["SNAP_BUMP_PROTRUSION"])
                start_x = half_width if side > 0 else -half_width - protrusion
                effective_radius = min(
                    float(C["SNAP_EDGE_RADIUS"]),
                    min(protrusion, float(C["SNAP_BUMP_LENGTH_Y"])) / 2.1,
                )
                ax.add_patch(
                    FancyBboxPatch(
                        (
                            start_x,
                            center_y - float(C["SNAP_BUMP_LENGTH_Y"]) / 2.0,
                        ),
                        protrusion,
                        float(C["SNAP_BUMP_LENGTH_Y"]),
                        boxstyle=f"round,pad=0,rounding_size={effective_radius}",
                        facecolor=GREEN,
                        edgecolor=RED,
                        linewidth=0.8,
                        zorder=5,
                    )
                )
            detail_width = float(C["SNAP_BUMP_LENGTH_Y"])
            detail_height = float(C["SNAP_BUMP_LENGTH_Z"])
            detail_left = half_width - 4.4
            detail_bottom = center_y - detail_height / 2.0
            ax.add_patch(
                FancyBboxPatch(
                    (detail_left, detail_bottom),
                    detail_width,
                    detail_height,
                    boxstyle=f"round,pad=0,rounding_size={float(C['SNAP_EDGE_RADIUS'])}",
                    facecolor="#d7efd9",
                    edgecolor=RED,
                    linewidth=1.0,
                    zorder=7,
                )
            )
            ax.text(
                detail_left + detail_width / 2.0,
                detail_bottom - 0.5,
                "SNAP OUTER FACE (Y–Z) — ENLARGED NTS",
                fontsize=4.0,
                color=RED,
                ha="center",
                va="top",
                zorder=8,
            )
            return (
                half_width - 5.0,
                center_y - 5.0,
                half_width + float(C["SNAP_BUMP_PROTRUSION"]) + 3.0,
                center_y + 5.0,
            )
        section_start = boss_assembly_datum_y()
        section_end = section_start + float(C["INSERT_DEPTH"])
        for section in range(int(C["INSERT_DEPTH_SECTIONS"]) + 1):
            y = section_start + (section_end - section_start) * section / int(C["INSERT_DEPTH_SECTIONS"])
            ax.plot(
                (y, y),
                (insert.bounds[1], insert.bounds[3]),
                color=BLUE,
                linewidth=0.42,
                linestyle=":" if section not in {0, int(C["INSERT_DEPTH_SECTIONS"])} else "--",
                zorder=6,
            )
            ax.text(
                y,
                insert.bounds[3] + 1.2,
                str(section),
                fontsize=3.8,
                color=BLUE,
                ha="center",
                va="bottom",
                zorder=7,
            )
        ax.text(
            (section_start + section_end) / 2.0,
            insert.bounds[1] - 2.0,
            f"{C['INSERT_DEPTH_SECTIONS']} EQUAL AXIAL SECTIONS",
            fontsize=4.6,
            color=BLUE,
            weight="bold",
            ha="center",
            va="top",
            zorder=7,
        )
        return insert.bounds
    if view == "button_profile":
        button = projected_part_geometry("button", "xz")
        draw_projected_geometry(ax, button, "#d7d9dc", INK, alpha=0.95)
        return button.bounds
    if view == "swing_gate":
        gate = projected_part_geometry("gate", "xy", True)
        draw_projected_geometry(ax, gate, "#d7efd9", GREEN, alpha=0.95)
        ax.add_patch(
            Circle(
                (
                    float(C["RETAINER_RELIEF_CENTER_X"]),
                    float(C["RETAINER_RELIEF_CENTER_Z"]),
                ),
                float(C["RETAINER_RELIEF_RADIUS"]),
                fill=False,
                edgecolor=RED,
                linewidth=0.7,
                linestyle="--",
                alpha=0.75,
                zorder=6,
            )
        )
        return gate.bounds
    if view == "gate_side":
        gate = projected_part_geometry("gate", "xz")
        draw_projected_geometry(ax, gate, "#d7efd9", GREEN, alpha=0.95)
        rigid = float(C["RETAINER_GATE_RIGID_THICKNESS_Y"])
        tpu = float(C["RETAINER_GATE_TPU_THICKNESS_Y"])
        minimum_x, minimum_z, maximum_x, _maximum_z = gate.bounds
        ax.plot((minimum_x, maximum_x), (rigid, rigid), color=GREEN, linewidth=0.8, zorder=6)
        ax.plot((minimum_x, maximum_x), (tpu, tpu), color=RED, linewidth=0.9, linestyle="--", zorder=6)
        ax.text(maximum_x, tpu, "TPU ALTERNATE", fontsize=4.8, color=RED, ha="right", va="bottom")
        return minimum_x, minimum_z, maximum_x, max(gate.bounds[3], tpu)
    if view == "gate_sweep":
        gate = projected_part_geometry("gate", "xy", True)
        left_angle = float(C["RETAINER_GATE_LOWER_LEFT_RELEASE_ANGLE_DEG"])
        right_angle = float(C["RETAINER_GATE_LOWER_RIGHT_RELEASE_ANGLE_DEG"])
        draw_projected_geometry(ax, gate, "#d7efd9", GREEN, alpha=0.78)
        for angle, color in ((left_angle, ORANGE), (right_angle, RED)):
            ghost = affinity.rotate(gate, angle, origin=tuple(C["CASE_FASTENER_POSITIONS_XZ"][2]))
            draw_projected_geometry(
                ax,
                ghost,
                "none",
                color,
                alpha=0.75,
                linewidth=0.8,
                linestyle="--",
                zorder=5,
            )
        sweep_bounds = union_bounds(
            (
                gate,
                affinity.rotate(gate, left_angle, origin=tuple(C["CASE_FASTENER_POSITIONS_XZ"][2])),
                affinity.rotate(gate, right_angle, origin=tuple(C["CASE_FASTENER_POSITIONS_XZ"][2])),
            )
        )
        return sweep_bounds
    if view == "rotating_keeper":
        keeper = projected_part_geometry("keeper", "xy", True)
        draw_projected_geometry(ax, keeper, "#eadcf1", "#793f91", alpha=0.95)
        index_radius = float(C["RETAINER_KEEPER_INDEX_RADIAL_OFFSET"])
        for sign in (-1.0, 1.0):
            ax.add_patch(
                Rectangle(
                    (
                        -float(C["RETAINER_KEEPER_INDEX_KEY_WIDTH_X"]) / 2.0,
                        sign * index_radius - float(C["RETAINER_KEEPER_INDEX_KEY_HEIGHT_Z"]) / 2.0,
                    ),
                    float(C["RETAINER_KEEPER_INDEX_KEY_WIDTH_X"]),
                    float(C["RETAINER_KEEPER_INDEX_KEY_HEIGHT_Z"]),
                    fill=False,
                    edgecolor=RED,
                    linewidth=0.8,
                    zorder=7,
                )
            )
        return keeper.bounds
    if view == "keeper_side":
        keeper = projected_part_geometry("keeper", "xz")
        draw_projected_geometry(ax, keeper, "#eadcf1", "#793f91", alpha=0.95)
        rigid = float(C["RETAINER_KEEPER_RIGID_THICKNESS_Y"])
        tpu = float(C["RETAINER_KEEPER_TPU_THICKNESS_Y"])
        minimum_x, minimum_z, maximum_x, _maximum_z = keeper.bounds
        ax.plot((minimum_x, maximum_x), (rigid, rigid), color="#793f91", linewidth=0.8, zorder=6)
        ax.plot((minimum_x, maximum_x), (tpu, tpu), color=RED, linewidth=0.9, linestyle="--", zorder=6)
        key_x = 0.0
        key_width = float(C["RETAINER_KEEPER_INDEX_KEY_WIDTH_X"])
        recess = float(C["RETAINER_KEEPER_INDEX_RECESS_DEPTH_Y"])
        ax.add_patch(
            Rectangle(
                (key_x - key_width / 2.0, rigid - recess),
                key_width,
                recess,
                facecolor="#f5c9c9",
                edgecolor=RED,
                linewidth=0.8,
                zorder=7,
            )
        )
        ax.text(maximum_x, tpu, "TPU ALTERNATE", fontsize=4.8, color=RED, ha="right", va="bottom")
        detail_scale = 4.0
        detail_width = float(C["RETAINER_KEEPER_INDEX_KEY_WIDTH_X"]) * detail_scale
        detail_height = float(C["RETAINER_KEEPER_INDEX_KEY_PROJECTION_Y"]) * detail_scale
        detail_bevel = float(C["RETAINER_KEEPER_INDEX_KEY_BEVEL"]) * detail_scale
        detail_left = -detail_width / 2.0
        detail_bottom = tpu + 1.2
        key_profile = (
            (detail_left, detail_bottom),
            (detail_left, detail_bottom + detail_height - detail_bevel),
            (detail_left + detail_bevel, detail_bottom + detail_height),
            (detail_left + detail_width - detail_bevel, detail_bottom + detail_height),
            (detail_left + detail_width, detail_bottom + detail_height - detail_bevel),
            (detail_left + detail_width, detail_bottom),
        )
        ax.add_patch(
            Polygon(
                key_profile,
                closed=True,
                facecolor="#f5c9c9",
                edgecolor=RED,
                linewidth=1.0,
                zorder=9,
            )
        )
        ax.text(
            0.0,
            detail_bottom + detail_height + 0.45,
            "SLEEVE INDEX KEY CORNER ×4 — NTS",
            fontsize=4.2,
            color=RED,
            weight="bold",
            ha="center",
            va="bottom",
            zorder=10,
        )
        return minimum_x, minimum_z, maximum_x, detail_bottom + detail_height + 1.0
    if view == "print_bed":
        gap = float(C["PRINT_BED_GAP"])
        back = projected_part_geometry("back", "xz")
        insert = affinity.translate(
            projected_part_geometry("insert", "xz"),
            xoff=back.bounds[2] - projected_part_geometry("insert", "xz").bounds[0] + gap,
        )
        gate = affinity.translate(
            projected_part_geometry("gate", "xy", True),
            xoff=insert.bounds[2] - projected_part_geometry("gate", "xy", True).bounds[0] + gap,
        )
        keeper = affinity.translate(
            projected_part_geometry("keeper", "xy", True),
            xoff=gate.bounds[2] - projected_part_geometry("keeper", "xy", True).bounds[0] + gap,
        )
        for geometry, face, edge in (
            (back, "#dceaf3", BLUE),
            (insert, "#f7d9ca", ORANGE),
            (gate, "#d7efd9", GREEN),
            (keeper, "#eadcf1", RED),
        ):
            draw_projected_geometry(ax, geometry, face, edge, alpha=0.88)
        return union_bounds((back, insert, gate, keeper))
    if view == "mesh_quality":
        gate = projected_part_geometry("gate", "xy", True)
        keeper_base = projected_part_geometry("keeper", "xy", True)
        keeper = affinity.translate(
            keeper_base,
            xoff=gate.bounds[2] - keeper_base.bounds[0] + 15.0,
        )
        draw_projected_geometry(ax, gate, "#edf6ee", GREEN, alpha=0.90)
        draw_projected_geometry(ax, keeper, "#f1e9f5", RED, alpha=0.90)
        triangles = load_stl_triangles("keeper")[:, :, (0, 1)].copy()
        triangles[:, :, 1] *= -1.0
        triangles[:, :, 0] += gate.bounds[2] - keeper_base.bounds[0] + 15.0
        for triangle in triangles[:: max(1, len(triangles) // 180)]:
            closed = np.vstack((triangle, triangle[0]))
            ax.plot(closed[:, 0], closed[:, 1], color=GRAY, linewidth=0.25, alpha=0.55)
        overlap = float(C["BOOLEAN_OVERLAP"])
        detail_x = gate.bounds[0] + 0.20 * (gate.bounds[2] - gate.bounds[0])
        detail_y = gate.bounds[1] + 0.16 * (gate.bounds[3] - gate.bounds[1])
        ax.add_patch(
            Rectangle(
                (detail_x, detail_y),
                10.0,
                5.0,
                fill=False,
                edgecolor=BLUE,
                linewidth=0.7,
                zorder=8,
            )
        )
        ax.add_patch(
            Rectangle(
                (detail_x + overlap, detail_y + overlap),
                10.0,
                5.0,
                fill=False,
                edgecolor=RED,
                linewidth=0.7,
                linestyle="--",
                zorder=8,
            )
        )
        ax.text(detail_x + 5.0, detail_y + 6.0, "PRE-BOOLEAN OVERLAP DETAIL", fontsize=4.6, color=BLUE, ha="center")
        corner_center = (gate.bounds[0] + 15.0, gate.bounds[3] - 13.0)
        corner_radius = 8.0
        corner_angles = np.linspace(0.0, math.pi / 2.0, int(C["CORNER_SEGMENTS"]) + 1)
        corner_points = np.column_stack(
            (
                corner_center[0] + corner_radius * np.cos(corner_angles),
                corner_center[1] + corner_radius * np.sin(corner_angles),
            )
        )
        ax.plot(corner_points[:, 0], corner_points[:, 1], color=RED, linewidth=0.85, zorder=9)
        ax.scatter(corner_points[:, 0], corner_points[:, 1], s=4.0, facecolor=WHITE, edgecolor=RED, linewidth=0.4, zorder=10)
        ax.plot((corner_center[0], corner_center[0] + corner_radius), (corner_center[1], corner_center[1]), color=GRAY, linewidth=0.45, zorder=8)
        ax.plot((corner_center[0], corner_center[0]), (corner_center[1], corner_center[1] + corner_radius), color=GRAY, linewidth=0.45, zorder=8)
        ax.text(corner_center[0] + corner_radius / 2.0, corner_center[1] + corner_radius + 1.0, "ROUNDED-CORNER CHORDS", fontsize=4.2, color=RED, ha="center", zorder=10)

        cleanup_origin = (-12.0, 8.0)
        cleanup_span = 4.0
        ax.plot(
            (cleanup_origin[0], cleanup_origin[0] + cleanup_span),
            (cleanup_origin[1], cleanup_origin[1]),
            color=RED,
            linewidth=1.2,
            marker="o",
            markersize=3.0,
            zorder=9,
        )
        ax.annotate(
            "MERGE SHORT EDGE → ONE VERTEX\nENLARGED ×40,000 — NTS",
            xy=(cleanup_origin[0] + cleanup_span / 2.0, cleanup_origin[1]),
            xytext=(cleanup_origin[0], cleanup_origin[1] + 5.0),
            fontsize=4.0,
            color=RED,
            ha="center",
            arrowprops={"arrowstyle": "->", "color": RED, "linewidth": 0.7},
            zorder=10,
        )

        sliver_origin = (3.0, 7.0)
        sliver_width = 5.0
        sliver_height = 2.5
        ax.add_patch(
            Polygon(
                (
                    sliver_origin,
                    (sliver_origin[0] + sliver_width, sliver_origin[1]),
                    (sliver_origin[0] + sliver_width * 0.15, sliver_origin[1] + sliver_height),
                ),
                closed=True,
                facecolor="#f5c9c9",
                edgecolor=RED,
                hatch="////",
                linewidth=0.8,
                zorder=9,
            )
        )
        ax.text(sliver_origin[0] + sliver_width / 2.0, sliver_origin[1] + sliver_height + 0.8, "BOOLEAN ΔV SLIVER — NTS", fontsize=4.0, color=RED, ha="center", zorder=10)
        return union_bounds((gate, keeper))
    raise RuntimeError(f"Unknown drawing view {view}")


def feature_anchor(view: str, entry: ConfigEntry, index: int, bounds):
    minimum_x, minimum_y, maximum_x, maximum_y = bounds
    width = maximum_x - minimum_x
    height = maximum_y - minimum_y
    defaults = (
        (minimum_x + 0.18 * width, maximum_y - 0.18 * height),
        (maximum_x - 0.18 * width, maximum_y - 0.18 * height),
        (minimum_x + 0.18 * width, minimum_y + 0.18 * height),
        (maximum_x - 0.18 * width, minimum_y + 0.18 * height),
    )
    name = entry.name
    if view == "back_front":
        if name.startswith("FAN_"):
            return float(C["FAN_CENTER_X"]), float(C["FAN_CENTER_Z"])
        if name.startswith("VENT_"):
            return float(C["VENT_CENTER_X"]), float(C["VENT_CENTER_Z"])
        return defaults[index % len(defaults)]
    if view == "fastener_detail":
        return tuple(C["CASE_FASTENER_POSITIONS_XZ"][index % 3])
    if view == "fastener_section":
        return (
            boss_assembly_datum_y(),
            float(C["CASE_FASTENER_POSITIONS_XZ"][0][1]),
        )
    if view == "camera_stops":
        spec = C["CAMERA_STOP_SPECS"][index % len(C["CAMERA_STOP_SPECS"])]
        return (spec[1] + spec[2]) / 2.0, (spec[3] + spec[4]) / 2.0
    if view == "ports_access":
        if name.startswith("LEFT_ROUND_"):
            return minimum_x, float(C["LEFT_ROUND_PORT_Z"])
        if name.startswith("RIGHT_USB_"):
            return maximum_x, float(C["RIGHT_USB_PORT_Z"])
        if name.startswith("TOP_PORT_"):
            return float(C["TOP_PORT_X"]), maximum_y
        return 0.0, minimum_y
    if view == "ports_side":
        datum_y = boss_assembly_datum_y()
        if name.startswith("LEFT_ROUND_"):
            return datum_y + float(C["LEFT_ROUND_PORT_Y_OFFSET"]), float(C["LEFT_ROUND_PORT_Z"])
        if name.startswith("RIGHT_USB_"):
            return datum_y + float(C["RIGHT_USB_PORT_Y_OFFSET"]), float(C["RIGHT_USB_PORT_Z"])
        if name.startswith("TOP_PORT_"):
            return datum_y + float(C["TOP_PORT_Y_OFFSET"]), maximum_y
        return datum_y + float(C["BOTTOM_ACCESS_Y_OFFSET"]), minimum_y
    if view == "locating_rails":
        spec = C["LOCATING_TAB_SPECS"][index % len(C["LOCATING_TAB_SPECS"])]
        return (spec[1] + spec[2]) / 2.0, (spec[3] + spec[4]) / 2.0
    if view == "button_profile":
        if name == "BUTTON_STEM_DIAMETER":
            return 0.0, (minimum_y + maximum_y) / 2.0
        if name == "BUTTON_INNER_FLANGE_DIAMETER":
            return 0.0, minimum_y + float(C["BUTTON_INNER_FLANGE_THICKNESS"]) / 2.0
        if name == "BUTTON_INNER_FLANGE_THICKNESS":
            return minimum_x, minimum_y + float(C["BUTTON_INNER_FLANGE_THICKNESS"]) / 2.0
        if name.startswith("BUTTON_RETENTION_"):
            return 0.0, maximum_y - float(C["BUTTON_RETENTION_RIM_HEIGHT"]) / 2.0
        if "HEIGHT" in name or "THICKNESS" in name:
            return minimum_x, (minimum_y + maximum_y) / 2.0
        return maximum_x, (minimum_y + maximum_y) / 2.0
    if view == "gate_side":
        return (minimum_x + maximum_x) / 2.0, minimum_y
    if view == "gate_sweep":
        return tuple(C["CASE_FASTENER_POSITIONS_XZ"][2])
    if view == "swing_gate":
        if "RELIEF" in name:
            return float(C["RETAINER_RELIEF_CENTER_X"]), float(C["RETAINER_RELIEF_CENTER_Z"])
        return tuple(C["CASE_FASTENER_POSITIONS_XZ"][index % 3])
    if view == "rotating_keeper":
        if "INDEX" in name:
            return 0.0, float(C["RETAINER_KEEPER_INDEX_RADIAL_OFFSET"])
        if "PROJECTION" in name or "LOBE" in name:
            return 0.0, float(C["RETAINER_KEEPER_CLOSED_PROJECTION_Z"])
        return 0.0, 0.0
    if view == "keeper_side":
        return 0.0, minimum_y
    if view == "snap_detail":
        start_y = float(C["BACK_DEPTH"]) - float(C["INSERTION_DEPTH"])
        return (
            float(C["INSERT_FRONT_WIDTH"]) / 2.0
            + float(C["SNAP_BUMP_PROTRUSION"]) / 2.0,
            start_y
            + float(C["SNAP_BUMP_Y_OFFSET"])
            + float(C["SNAP_BUMP_LENGTH_Y"]) / 2.0,
        )
    if view == "snap_front":
        return maximum_x, 0.0
    if view == "locating_side":
        return minimum_x + float(next(iter(C["LENS_CLEARANCE_GUIDE_TAPERS"].values()))[0]) / 2.0, maximum_y - 4.0
    if view == "mesh_quality":
        gate = projected_part_geometry("gate", "xy", True)
        keeper_base = projected_part_geometry("keeper", "xy", True)
        keeper_x_offset = gate.bounds[2] - keeper_base.bounds[0] + 15.0
        if name == "CYLINDER_SEGMENTS":
            return keeper_x_offset, 0.0
        if name == "CORNER_SEGMENTS":
            return gate.bounds[2], gate.bounds[3]
        detail_x = gate.bounds[0] + 0.20 * (gate.bounds[2] - gate.bounds[0])
        detail_y = gate.bounds[1] + 0.16 * (gate.bounds[3] - gate.bounds[1])
        if name == "BOOLEAN_OVERLAP":
            return detail_x + 5.0, detail_y + 2.5
        return gate.bounds[2], gate.bounds[1]
    return defaults[index % len(defaults)]


def dimension_value(entry: ConfigEntry) -> str:
    if entry.name == "CASE_FASTENER_POSITIONS_XZ":
        return "; ".join(
            f"({fmt(x)}, {fmt(z)}) mm" for x, z in entry.value
        )
    if entry.name == "CAMERA_STOP_SPECS":
        return "\n".join(
            f"{name}: X {fmt(x0)}..{fmt(x1)}, Z {fmt(z0)}..{fmt(z1)} mm"
            for name, x0, x1, z0, z1, _attachment in entry.value
        )
    if entry.name == "LOCATING_TAB_SPECS":
        return "\n".join(
            f"{name}: X {fmt(x0)}..{fmt(x1)}, Z {fmt(z0)}..{fmt(z1)} mm"
            for name, x0, x1, z0, z1, _attachment in entry.value
        )
    if entry.name == "LENS_CLEARANCE_GUIDE_TAPERS":
        values = "; ".join(
            f"{name} {fmt(length)}/{fmt(projection)} mm"
            for name, (length, projection) in entry.value.items()
        )
        return values
    value = fmt(entry.value)
    if entry.unit == "mm":
        return f"{value} mm"
    if entry.unit == "deg":
        return f"{value}°"
    if entry.unit == "mm²":
        return f"{value} mm²"
    if entry.unit == "mm³":
        return f"{value} mm³"
    if entry.unit == "count":
        return f"{value} segments / count"
    return value


def graphical_annotation_value(entry: ConfigEntry) -> str:
    if entry.name == "LENS_CLEARANCE_GUIDE_TAPERS":
        unique_tapers = sorted(set(entry.value.values()))
        return "; ".join(
            f"L={fmt(length)} mm P={fmt(projection)} mm"
            for length, projection in unique_tapers
        )
    if entry.name in PHYSICAL_SETTING_NAMES:
        return "DATUMED SPECIFICATION"
    value = fmt(entry.value)
    suffixes = {
        "mm": "mm",
        "deg": "deg",
        "mm²": "mm^2",
        "mm³": "mm^3",
        "count": "count",
    }
    return f"{value} {suffixes[entry.unit]}"


def graphical_annotation_label(entry: ConfigEntry, index: int) -> str:
    return f"D{index + 1} {graphical_annotation_value(entry)}"


def graphical_annotation_kind(entry: ConfigEntry) -> str:
    name = entry.name
    if entry.name in PHYSICAL_SETTING_NAMES:
        return "datum_specification"
    if entry.unit == "deg":
        return "angular_arc"
    if entry.unit in {"count", "mm²", "mm³"}:
        return "construction_note"
    if entry.name in {"LEFT_ROUND_PORT_DIAMETER", "TOP_PORT_DIAMETER"}:
        return "radius_leader"
    if "DIAMETER" in name:
        return "diameter_dimension"
    if "RADIUS" in name or "BEVEL" in name:
        return "radius_leader"
    if name == "FAN_HOLE_BOSS_HEIGHT" or (
        name.startswith("BUTTON_") and "THICKNESS" in name
    ):
        return "axial_linear" if name == "FAN_HOLE_BOSS_HEIGHT" else "vertical_linear"
    if any(token in name for token in ("CENTER_X", "_X_OFFSET", "PORT_X")):
        return "x_ordinate"
    if name.endswith("_Z") or "CENTER_Z" in name:
        return "z_ordinate"
    if name.endswith("_X") or "WIDTH" in name or "CLEARANCE_X" in name:
        return "horizontal_linear"
    if name.endswith("_Z") or "HEIGHT" in name or "CLEARANCE_Z" in name:
        return "vertical_linear"
    if any(token in name for token in ("_Y", "DEPTH", "THICKNESS", "GAP", "CLEARANCE", "PROJECTION", "OFFSET", "SEAT_TO_INSERT")):
        return "axial_linear"
    return "feature_leader"


def draw_linear_annotation(
    ax,
    start,
    end,
    label: str,
    offset: float,
    vertical: bool,
) -> None:
    if vertical:
        dimension_start = (start[0] + offset, start[1])
        dimension_end = (end[0] + offset, end[1])
        ax.plot((start[0], dimension_start[0]), (start[1], start[1]), color=RED, linewidth=0.55, zorder=18)
        ax.plot((end[0], dimension_end[0]), (end[1], end[1]), color=RED, linewidth=0.55, zorder=18)
    else:
        dimension_start = (start[0], start[1] + offset)
        dimension_end = (end[0], end[1] + offset)
        ax.plot((start[0], start[0]), (start[1], dimension_start[1]), color=RED, linewidth=0.55, zorder=18)
        ax.plot((end[0], end[0]), (end[1], dimension_end[1]), color=RED, linewidth=0.55, zorder=18)
    ax.add_patch(
        FancyArrowPatch(
            dimension_start,
            dimension_end,
            arrowstyle="<->",
            mutation_scale=7,
            linewidth=0.8,
            color=RED,
            zorder=19,
        )
    )
    midpoint = (
        (dimension_start[0] + dimension_end[0]) / 2.0,
        (dimension_start[1] + dimension_end[1]) / 2.0,
    )
    ax.text(
        *midpoint,
        label,
        fontsize=5.4,
        weight="bold",
        color=RED,
        ha="center",
        va="center",
        rotation=90 if vertical else 0,
        bbox={"facecolor": WHITE, "edgecolor": "none", "alpha": 0.90, "pad": 0.55},
        zorder=20,
    )


def draw_radius_annotation(ax, center, radius: float, angle_deg: float, label: str) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    endpoint = (
        center[0] + radius * math.cos(angle),
        center[1] + radius * math.sin(angle),
    )
    ax.add_patch(
        FancyArrowPatch(
            center,
            endpoint,
            arrowstyle="-|>",
            mutation_scale=7,
            linewidth=0.85,
            color=RED,
            zorder=19,
        )
    )
    midpoint = ((center[0] + endpoint[0]) / 2.0, (center[1] + endpoint[1]) / 2.0)
    ax.text(
        midpoint[0],
        midpoint[1],
        f"{label}  R",
        fontsize=5.4,
        weight="bold",
        color=RED,
        ha="center",
        va="center",
        bbox={"facecolor": WHITE, "edgecolor": "none", "alpha": 0.90, "pad": 0.55},
        zorder=20,
    )
    ax.plot(center[0], center[1], marker="+", markersize=4.0, color=RED, zorder=20)
    return endpoint


def draw_specific_graphical_annotation(
    ax,
    view: str,
    entry: ConfigEntry,
    index: int,
    bounds,
    label: str,
) -> bool:
    """Draw dimensions whose endpoints cannot be inferred from their names."""
    name = entry.name
    minimum_x, minimum_y, maximum_x, maximum_y = bounds

    def linear(start, end, vertical=False, offset=0.0, annotation_label=label):
        draw_linear_annotation(ax, start, end, annotation_label, offset, vertical)
        record_graphical_primitive(entry, "linear", start, end)
        return True

    def radius(center, value, angle_deg=45.0):
        endpoint = draw_radius_annotation(ax, center, value, angle_deg, label)
        record_graphical_primitive(entry, "radius", center, endpoint)
        return True

    def leader(anchor, text_position, annotation_label=label, primitive_kind="leader"):
        ax.annotate(
            annotation_label,
            xy=anchor,
            xycoords="data",
            xytext=text_position,
            textcoords="data",
            fontsize=5.4,
            weight="bold",
            color=RED,
            ha="center",
            va="center",
            bbox={"boxstyle": "round,pad=0.18", "facecolor": WHITE, "edgecolor": RED, "linewidth": 0.6},
            arrowprops={"arrowstyle": "->", "color": RED, "linewidth": 0.8},
            zorder=20,
        )
        record_graphical_primitive(entry, primitive_kind, anchor, text_position)
        return True

    if view == "back_front":
        fan_x = float(C["FAN_CENTER_X"])
        fan_z = float(C["FAN_CENTER_Z"])
        spacing_x = float(C["FAN_HOLE_SPACING_X"])
        spacing_z = float(C["FAN_HOLE_SPACING_Z"])
        if name == "BACK_DOME_FAN_PAD_WIDTH":
            half = float(entry.value) / 2.0
            return linear((fan_x - half, fan_z), (fan_x + half, fan_z), False, 2.0)
        if name == "BACK_DOME_FAN_PAD_HEIGHT":
            half = float(entry.value) / 2.0
            return linear((fan_x, fan_z - half), (fan_x, fan_z + half), True, 2.0)
        if name == "FAN_HOLE_SPACING_X":
            z = fan_z + spacing_z / 2.0
            return linear((fan_x - spacing_x / 2.0, z), (fan_x + spacing_x / 2.0, z), False, 2.0)
        if name == "FAN_HOLE_SPACING_Z":
            x = fan_x + spacing_x / 2.0
            return linear((x, fan_z - spacing_z / 2.0), (x, fan_z + spacing_z / 2.0), True, 2.0)
        if name in {"FAN_HOLE_DIAMETER", "FAN_HOLE_BOSS_DIAMETER"}:
            center = (
                fan_x + (-1.0 if name == "FAN_HOLE_DIAMETER" else 1.0) * spacing_x / 2.0,
                fan_z + spacing_z / 2.0,
            )
            diameter = float(entry.value)
            return linear((center[0] - diameter / 2.0, center[1]), (center[0] + diameter / 2.0, center[1]), False, 1.5, f"{label} DIA")
        if name == "FAN_OPENING_DIAMETER":
            diameter = float(entry.value)
            return linear((fan_x - diameter / 2.0, fan_z), (fan_x + diameter / 2.0, fan_z), False, -2.0, f"{label} DIA")
        if name == "BACK_CORNER_RADIUS":
            value = float(entry.value)
            center = (maximum_x - value, maximum_y - value)
            return radius(center, value, 45.0)
        if name == "VENT_CORNER_RADIUS":
            value = float(entry.value)
            center = (
                float(C["VENT_CENTER_X"]) + float(C["VENT_WIDTH"]) / 2.0 - value,
                float(C["VENT_CENTER_Z"]) + float(C["VENT_HEIGHT"]) / 2.0 - value,
            )
            return radius(center, value, 45.0)

    if view == "back_side":
        back_exterior = -float(C["BACK_DOME_DEPTH"]) if C["BACK_DOME_ENABLED"] else 0.0
        if name == "BACK_DEPTH":
            return linear((0.0, 18.0), (float(entry.value), 18.0), False, 0.0)
        if name == "BACK_FACE_THICKNESS":
            return linear((back_exterior, 8.0), (back_exterior + float(entry.value), 8.0), False, 0.0)
        if name == "BACK_DOME_DEPTH":
            return linear((back_exterior, -8.0), (0.0, -8.0), False, 0.0)
        if name == "BACK_DOME_START_BEHIND_CAMERA_STOPS":
            stop_end = boss_assembly_datum_y() - float(C["CAMERA_STOP_TO_INSERT_SOCKET_GAP"])
            return linear((stop_end - float(entry.value), -18.0), (stop_end, -18.0), False, 0.0)
        if name == "FAN_HOLE_BOSS_HEIGHT":
            start = back_exterior + float(C["BACK_FACE_THICKNESS"])
            return linear((start, float(C["FAN_CENTER_Z"])), (start + float(entry.value), float(C["FAN_CENTER_Z"])), False, 1.5)

    if view == "fastener_section" and name == "BACK_FASTENER_RETENTION_TAB_BEVEL":
        datum = boss_assembly_datum_y()
        section_z = float(C["CASE_FASTENER_POSITIONS_XZ"][0][1])
        scale = 8.0
        detail_left = datum + 2.0
        detail_bottom = section_z - 7.0
        detail_width = 4.8
        detail_height = 4.0
        bevel = float(entry.value) * scale
        anchor = (
            detail_left + detail_width - bevel / 2.0,
            detail_bottom + detail_height - bevel / 2.0,
        )
        return leader(
            anchor,
            (datum + 5.0, section_z + 5.5),
            f"{label} BEVEL · DETAIL ×8 NTS",
            "bevel",
        )

    if view == "capture_joint" and name in {
        "FIT_CLEARANCE_X",
        "FIT_CLEARANCE_Z",
        "SLEEVE_CAPTURE_FIT_CLEARANCE",
        "SLEEVE_CAPTURE_INNER_LIP_THICKNESS",
        "SLEEVE_CAPTURE_MIN_OUTER_WALL_X",
        "SLEEVE_CAPTURE_MIN_OUTER_WALL_Z",
    }:
        start, end = capture_joint_detail_points(bounds)[name]
        vertical = abs(end[1] - start[1]) > abs(end[0] - start[0])
        return linear(start, end, vertical, 0.0, f"{label}  ENLARGED NTS")

    if view == "capture_section":
        datum = boss_assembly_datum_y()
        engagement = float(C["SLEEVE_CAPTURE_ENGAGEMENT_DEPTH"])
        leading = datum - engagement
        floor = leading - float(C["SLEEVE_CAPTURE_BOTTOM_CLEARANCE"])
        ledge = floor - float(C["SLEEVE_CAPTURE_FLOOR_THICKNESS"])
        section_lines = {
            "INSERTION_DEPTH": ((datum, 8.0), (float(C["BACK_DEPTH"]), 8.0)),
            "SLEEVE_CAPTURE_ENGAGEMENT_DEPTH": ((leading, 4.0), (datum, 4.0)),
            "SLEEVE_CAPTURE_BOTTOM_CLEARANCE": ((floor, 0.0), (leading, 0.0)),
            "SLEEVE_CAPTURE_FLOOR_THICKNESS": ((ledge, -4.0), (floor, -4.0)),
        }
        if name in section_lines:
            return linear(*section_lines[name], vertical=False, offset=0.0)
        if name == "CAMERA_STOP_TO_INSERT_SOCKET_GAP":
            stop_end = datum - float(entry.value)
            if abs(float(entry.value)) <= 1.0e-12:
                ax.plot((datum, datum), (-8.8, -6.4), color=RED, linewidth=1.2, zorder=19)
                ax.plot((datum - 0.16, datum + 0.16), (-7.6, -7.6), color=RED, linewidth=0.9, zorder=19)
                return leader((datum, -7.6), (datum + 1.8, -8.5), f"{label}  COINCIDENT", "coincident")
            return linear((stop_end, -8.0), (datum, -8.0), False, 0.0)

    if view == "insert_front":
        if name == "INSERT_OUTER_CORNER_RADIUS":
            value = float(entry.value)
            center = (maximum_x - value, maximum_y - value)
            return radius(center, value, 45.0)
        if name == "INSERT_WALL_X":
            outer = float(C["INSERT_FRONT_WIDTH"]) / 2.0
            return linear((outer - float(entry.value), 0.0), (outer, 0.0), False, 2.0)
        if name == "INSERT_WALL_Z":
            outer = float(C["INSERT_FRONT_HEIGHT"]) / 2.0
            return linear((0.0, outer - float(entry.value)), (0.0, outer), True, 2.0)

    if view == "insert_side":
        section_start = boss_assembly_datum_y()
        section_end = section_start + float(C["INSERT_DEPTH"])
        if name == "INSERT_DEPTH":
            return linear((section_start, 0.0), (section_end, 0.0), False, 3.0)
        if name == "INSERT_DEPTH_SECTIONS":
            return leader((section_start + (section_end - section_start) / 2.0, maximum_y), (section_start + (section_end - section_start) / 2.0, maximum_y + 7.0), label, "construction")

    if view == "ports_access":
        details = port_access_detail_points(bounds)
        if name == "BOTTOM_ACCESS_WIDTH":
            half = float(entry.value) / 2.0
            return linear((-half, minimum_y), (half, minimum_y), False, -2.0)
        if name == "LEFT_ROUND_PORT_DIAMETER":
            center = details["left_center"]
            diameter = float(entry.value)
            return linear((center[0] - diameter / 2.0, center[1]), (center[0] + diameter / 2.0, center[1]), False, 0.0, f"{label} DIA")
        if name == "TOP_PORT_DIAMETER":
            center = details["top_center"]
            diameter = float(entry.value)
            return linear((center[0] - diameter / 2.0, center[1]), (center[0] + diameter / 2.0, center[1]), False, 0.0, f"{label} DIA")
        if name == "LEFT_ROUND_PORT_Z":
            return linear((minimum_x, 0.0), (minimum_x, float(entry.value)), True, -2.0)
        if name == "RIGHT_USB_PORT_Z":
            return linear((maximum_x, 0.0), (maximum_x, float(entry.value)), True, 2.0)
        if name == "RIGHT_USB_PORT_HEIGHT_Z":
            center = details["usb_center"]
            half = float(entry.value) / 2.0
            return linear((center[0], center[1] - half), (center[0], center[1] + half), True, 1.5)
        if name == "RIGHT_USB_PORT_CORNER_RADIUS":
            center = details["usb_center"]
            value = float(entry.value)
            corner_center = (
                center[0] + float(C["RIGHT_USB_PORT_WIDTH_Y"]) / 2.0 - value,
                center[1] + float(C["RIGHT_USB_PORT_HEIGHT_Z"]) / 2.0 - value,
            )
            return radius(corner_center, value, 45.0)
        if name == "TOP_PORT_X":
            return linear((0.0, maximum_y), (float(entry.value), maximum_y), False, 2.0)

    if view == "ports_side":
        datum = boss_assembly_datum_y()
        offset_names = {
            "BOTTOM_ACCESS_Y_OFFSET": float(C["BOTTOM_ACCESS_Y_OFFSET"]),
            "LEFT_ROUND_PORT_Y_OFFSET": float(C["LEFT_ROUND_PORT_Y_OFFSET"]),
            "RIGHT_USB_PORT_Y_OFFSET": float(C["RIGHT_USB_PORT_Y_OFFSET"]),
            "TOP_PORT_Y_OFFSET": float(C["TOP_PORT_Y_OFFSET"]),
        }
        z_by_name = {
            "BOTTOM_ACCESS_Y_OFFSET": minimum_y + 8.0,
            "LEFT_ROUND_PORT_Y_OFFSET": -2.0,
            "RIGHT_USB_PORT_Y_OFFSET": -13.0,
            "TOP_PORT_Y_OFFSET": maximum_y - 3.0,
        }
        if name in offset_names:
            return linear((datum, z_by_name[name]), (datum + offset_names[name], z_by_name[name]), False, 1.2 * (-1.0 if index % 2 == 0 else 1.0))
        if name == "BOTTOM_ACCESS_DEPTH":
            start = datum + float(C["BOTTOM_ACCESS_Y_OFFSET"])
            return linear((start, minimum_y), (start + float(entry.value), minimum_y), False, -1.8)
        if name == "RIGHT_USB_PORT_WIDTH_Y":
            center = datum + float(C["RIGHT_USB_PORT_Y_OFFSET"])
            half = float(entry.value) / 2.0
            return linear((center - half, -13.0), (center + half, -13.0), False, 1.8)

    if view == "snap_detail":
        datum = boss_assembly_datum_y()
        bump_start = datum + float(C["SNAP_BUMP_Y_OFFSET"])
        bump_end = bump_start + float(C["SNAP_BUMP_LENGTH_Y"])
        half_width = float(C["INSERT_FRONT_WIDTH"]) / 2.0
        protrusion = float(C["SNAP_BUMP_PROTRUSION"])
        if name == "SNAP_BUMP_PROTRUSION":
            return linear((half_width, (bump_start + bump_end) / 2.0), (half_width + protrusion, (bump_start + bump_end) / 2.0), False, 0.8)
        if name == "SNAP_BUMP_LENGTH_Y":
            return linear((half_width + protrusion, bump_start), (half_width + protrusion, bump_end), True, 0.8)
        if name == "SNAP_BUMP_Y_OFFSET":
            return linear((half_width, datum), (half_width, bump_start), True, -0.8)
        if name == "SNAP_POCKET_CLEARANCE":
            return linear((half_width + protrusion, bump_end), (half_width + protrusion + float(entry.value), bump_end), False, 0.8)
        if name == "SNAP_EDGE_RADIUS":
            detail_left = half_width - 4.4
            detail_width = float(C["SNAP_BUMP_LENGTH_Y"])
            detail_height = float(C["SNAP_BUMP_LENGTH_Z"])
            detail_bottom = (bump_start + bump_end) / 2.0 - detail_height / 2.0
            value = float(entry.value)
            center = (detail_left + detail_width - value, detail_bottom + detail_height - value)
            return radius(center, value, 45.0)

    if view == "swing_gate":
        layout = retainer_layout_for_drawings()
        if name == "RETAINER_HORIZONTAL_END_MARGIN_X":
            return linear((layout["bar_left_x"], layout["lower_left"][1]), layout["lower_left"], False, -3.5)
        if name == "RETAINER_HORIZONTAL_BAR_HEIGHT_Z":
            x = (layout["bar_left_x"] + layout["bar_right_x"]) / 2.0
            return linear((x, layout["bar_bottom_z"]), (x, layout["bar_top_z"]), True, -2.0)
        if name == "RETAINER_LOWER_EDGE_MARGIN_Z":
            x = layout["lower_right"][0]
            return linear((x, layout["bar_bottom_z"]), layout["lower_right"], True, 3.0)
        if name == "RETAINER_UPRIGHT_WIDTH_X":
            z = layout["upper"][1] - 7.0
            return linear((layout["upright_left_x"], z), (layout["upright_right_x"], z), False, 2.0)
        if name == "RETAINER_TOP_EDGE_MARGIN_Z":
            x = layout["upper"][0]
            return linear(layout["upper"], (x, layout["upright_top_z"]), True, 5.0)
        if name == "RETAINER_CORNER_RADIUS":
            value = float(entry.value)
            center = (layout["upright_left_x"] + value, layout["upright_top_z"] - value)
            return radius(center, value, 135.0)
        if name == "RETAINER_RELIEF_CENTER_X":
            return linear((0.0, float(C["RETAINER_RELIEF_CENTER_Z"])), (float(entry.value), float(C["RETAINER_RELIEF_CENTER_Z"])), False, 2.0)
        if name == "RETAINER_RELIEF_CENTER_Z":
            return linear((float(C["RETAINER_RELIEF_CENTER_X"]), 0.0), (float(C["RETAINER_RELIEF_CENTER_X"]), float(entry.value)), True, -2.0)
        if name == "RETAINER_RELIEF_RADIUS":
            return radius((float(C["RETAINER_RELIEF_CENTER_X"]), float(C["RETAINER_RELIEF_CENTER_Z"])), float(entry.value), -90.0)
        if name == "RETAINER_MIN_HOLE_WEB":
            hole_edge = layout["upper"][0] - float(C["RETAINER_GATE_BOLT_TRACK_DIAMETER"]) / 2.0
            return linear((hole_edge - float(entry.value), layout["upper"][1]), (hole_edge, layout["upper"][1]), False, 0.0, f"{label} MIN")
        if name == "RETAINER_GATE_BOLT_TRACK_DIAMETER":
            center = layout["upper"]
            half = float(entry.value) / 2.0
            return linear((center[0] - half, center[1]), (center[0] + half, center[1]), False, -3.0, f"{label} DIA")
        if name == "RETAINER_GATE_MIN_NUT_BEARING_DIAMETER":
            center = layout["upper"]
            value = float(entry.value)
            ax.add_patch(Circle(center, value / 2.0, fill=False, edgecolor=RED, linewidth=0.75, linestyle="--", zorder=17))
            return linear((center[0] - value / 2.0, center[1]), (center[0] + value / 2.0, center[1]), False, 3.0, f"{label} MIN DIA")

    if view == "rotating_keeper":
        if name == "RETAINER_KEEPER_MIN_HOLE_WEB":
            hole_radius = float(C["RETAINER_KEEPER_BOLT_HOLE_DIAMETER"]) / 2.0
            hub_radius = float(C["RETAINER_KEEPER_HUB_DIAMETER"]) / 2.0
            actual_web = hub_radius - hole_radius
            return linear((hole_radius, 0.0), (hub_radius, 0.0), False, 2.0, f"{label} MIN (actual {actual_web:.2f} mm)")

    if view == "keeper_side" and name == "RETAINER_KEEPER_INDEX_KEY_BEVEL":
        scale = 4.0
        width = float(C["RETAINER_KEEPER_INDEX_KEY_WIDTH_X"]) * scale
        height = float(C["RETAINER_KEEPER_INDEX_KEY_PROJECTION_Y"]) * scale
        bevel = float(entry.value) * scale
        bottom = float(C["RETAINER_KEEPER_TPU_THICKNESS_Y"]) + 1.2
        anchor = (width / 2.0 - bevel / 2.0, bottom + height - bevel / 2.0)
        return leader(anchor, (-width / 2.0 - 0.8, bottom + height + 0.8), f"{label} BEVEL · DETAIL ×4 NTS", "bevel")

    if view == "mesh_quality":
        gate = projected_part_geometry("gate", "xy", True)
        if name == "CORNER_SEGMENTS":
            center = (gate.bounds[0] + 15.0, gate.bounds[3] - 13.0)
            anchor = (center[0] + 8.0 / math.sqrt(2.0), center[1] + 8.0 / math.sqrt(2.0))
            return leader(anchor, (center[0] - 1.0, center[1] + 12.0), f"{label} CHORDS", "construction")
        if name == "BOOLEAN_CLEANUP_DISTANCE":
            origin = (-12.0, 8.0)
            return leader((origin[0] + 2.0, origin[1]), (origin[0] - 2.0, origin[1] - 6.0), f"{label} MERGE LIMIT", "construction")
        if name == "BOOLEAN_MINIMUM_VOLUME_CHANGE":
            origin = (3.0, 7.0)
            return leader((origin[0] + 2.0, origin[1] + 0.8), (origin[0] + 9.0, origin[1] + 7.0), f"{label} MIN ΔV", "construction")

    return False


def draw_graphical_annotations(ax, view: str, entries, bounds) -> None:
    minimum_x, minimum_y, maximum_x, maximum_y = bounds
    width = max(maximum_x - minimum_x, 1.0)
    height = max(maximum_y - minimum_y, 1.0)
    for index, entry in enumerate(entries):
        kind = graphical_annotation_kind(entry)
        label = graphical_annotation_label(entry, index)
        anchor = feature_anchor(view, entry, index, bounds)
        numeric_value = (
            abs(float(entry.value))
            if isinstance(entry.value, (int, float)) and not isinstance(entry.value, bool)
            else 0.0
        )
        lane = 0.08 + (index // 2) * 0.10
        lane_sign = -1.0 if index % 2 == 0 else 1.0

        if draw_specific_graphical_annotation(
            ax,
            view,
            entry,
            index,
            bounds,
            label,
        ):
            GRAPHICALLY_ANNOTATED_NAMES.add(entry.name)
            GRAPHICAL_ANNOTATION_KINDS[entry.name] = kind
            continue

        if entry.name == "PRINT_BED_GAP":
            back = projected_part_geometry("back", "xz")
            insert_minimum = back.bounds[2] + float(C["PRINT_BED_GAP"])
            start = (back.bounds[2], minimum_y)
            end = (insert_minimum, minimum_y)
            draw_linear_annotation(
                ax,
                start,
                end,
                label,
                -lane * height,
                False,
            )
            record_graphical_primitive(entry, "linear", start, end)
        elif view == "snap_detail" and kind == "axial_linear" and numeric_value > 1.0e-9:
            snap_start_y = boss_assembly_datum_y()
            if entry.name == "SNAP_BUMP_Y_OFFSET":
                start_y = snap_start_y
                end_y = snap_start_y + numeric_value
            else:
                start_y = anchor[1] - numeric_value / 2.0
                end_y = anchor[1] + numeric_value / 2.0
            draw_linear_annotation(
                ax,
                (anchor[0], start_y),
                (anchor[0], end_y),
                label,
                lane_sign * lane * width,
                True,
            )
            record_graphical_primitive(
                entry,
                "linear",
                (anchor[0], start_y),
                (anchor[0], end_y),
            )
        elif view in {"gate_side", "keeper_side"} and kind == "axial_linear" and numeric_value > 1.0e-9:
            draw_linear_annotation(
                ax,
                (anchor[0], 0.0),
                (anchor[0], numeric_value),
                label,
                lane_sign * lane * width,
                True,
            )
            record_graphical_primitive(
                entry,
                "linear",
                (anchor[0], 0.0),
                (anchor[0], numeric_value),
            )
        elif kind == "angular_arc":
            radius = max((0.11 + index * 0.08) * min(width, height), 4.0 + index * 3.0)
            angle = numeric_value
            ax.add_patch(
                Arc(
                    anchor,
                    2.0 * radius,
                    2.0 * radius,
                    theta1=0.0,
                    theta2=angle,
                    color=RED,
                    linewidth=0.9,
                    zorder=18,
                )
            )
            ax.plot(
                (anchor[0], anchor[0] + radius),
                (anchor[1], anchor[1]),
                color=RED,
                linewidth=0.6,
                zorder=18,
            )
            ax.plot(
                (anchor[0], anchor[0] + radius * math.cos(math.radians(angle))),
                (anchor[1], anchor[1] + radius * math.sin(math.radians(angle))),
                color=RED,
                linewidth=0.6,
                zorder=18,
            )
            label_angle = math.radians(max(12.0, angle / 2.0))
            ax.text(
                anchor[0] + radius * 1.28 * math.cos(label_angle),
                anchor[1] + radius * 1.28 * math.sin(label_angle),
                label,
                fontsize=5.4,
                weight="bold",
                color=RED,
                bbox={"facecolor": WHITE, "edgecolor": "none", "alpha": 0.9, "pad": 0.5},
                zorder=20,
            )
            record_graphical_primitive(
                entry,
                "arc",
                anchor,
                (anchor[0] + radius, anchor[1]),
                (
                    anchor[0] + radius * math.cos(math.radians(angle)),
                    anchor[1] + radius * math.sin(math.radians(angle)),
                ),
            )
        elif kind == "diameter_dimension":
            span = max(numeric_value, 0.08 * width)
            diameter_offset = lane_sign * lane * height
            start = (anchor[0] - span / 2.0, anchor[1])
            end = (anchor[0] + span / 2.0, anchor[1])
            draw_linear_annotation(
                ax,
                start,
                end,
                f"{label} DIA",
                diameter_offset,
                False,
            )
            record_graphical_primitive(entry, "diameter", start, end)
        elif kind == "radius_leader" and numeric_value > 1.0e-9:
            endpoint = draw_radius_annotation(ax, anchor, numeric_value, 45.0, label)
            record_graphical_primitive(entry, "radius", anchor, endpoint)
        elif kind in {"horizontal_linear", "x_ordinate", "axial_linear"} and numeric_value > 1.0e-9:
            if kind == "x_ordinate":
                start_x, end_x = 0.0, float(entry.value)
            elif entry.name in {"BACK_OUTER_WIDTH", "INSERT_FRONT_WIDTH", "INSERT_REAR_WIDTH"}:
                start_x, end_x = -numeric_value / 2.0, numeric_value / 2.0
            else:
                start_x, end_x = anchor[0] - numeric_value / 2.0, anchor[0] + numeric_value / 2.0
            draw_linear_annotation(
                ax,
                (start_x, anchor[1]),
                (end_x, anchor[1]),
                label,
                lane_sign * lane * height,
                False,
            )
            record_graphical_primitive(
                entry,
                "linear",
                (start_x, anchor[1]),
                (end_x, anchor[1]),
            )
        elif kind in {"vertical_linear", "z_ordinate"} and numeric_value > 1.0e-9:
            if kind == "z_ordinate":
                start_y, end_y = 0.0, float(entry.value)
            elif entry.name in {"BACK_OUTER_HEIGHT", "INSERT_FRONT_HEIGHT", "INSERT_REAR_HEIGHT"}:
                start_y, end_y = -numeric_value / 2.0, numeric_value / 2.0
            else:
                start_y, end_y = anchor[1] - numeric_value / 2.0, anchor[1] + numeric_value / 2.0
            draw_linear_annotation(
                ax,
                (anchor[0], start_y),
                (anchor[0], end_y),
                label,
                lane_sign * lane * width,
                True,
            )
            record_graphical_primitive(
                entry,
                "linear",
                (anchor[0], start_y),
                (anchor[0], end_y),
            )
        else:
            label_positions = (
                (minimum_x + 0.12 * width, maximum_y + 0.13 * height),
                (maximum_x - 0.12 * width, maximum_y + 0.13 * height),
                (minimum_x + 0.12 * width, minimum_y - 0.13 * height),
                (maximum_x - 0.12 * width, minimum_y - 0.13 * height),
            )
            ax.annotate(
                label,
                xy=anchor,
                xycoords="data",
                xytext=label_positions[index % len(label_positions)],
                textcoords="data",
                fontsize=5.4,
                weight="bold",
                color=RED,
                ha="center",
                va="center",
                bbox={"boxstyle": "round,pad=0.18", "facecolor": WHITE, "edgecolor": RED, "linewidth": 0.6},
                arrowprops={"arrowstyle": "->", "color": RED, "linewidth": 0.8},
                zorder=20,
            )
            record_graphical_primitive(
                entry,
                "leader",
                anchor,
                label_positions[index % len(label_positions)],
            )
        GRAPHICALLY_ANNOTATED_NAMES.add(entry.name)
        GRAPHICAL_ANNOTATION_KINDS[entry.name] = kind


def draw_dimension_cards(ax, entries):
    ax.axis("off")
    card_gap = 0.018
    expanded_single = (
        len(entries) == 1 and entries[0].name in EXPANDED_DIMENSION_NAMES
    )
    if expanded_single:
        card_height = 0.94
    else:
        card_height = min(
            0.40 if len(entries) == 1 else 0.30,
            (0.965 - card_gap * max(0, len(entries) - 1))
            / max(1, len(entries)),
        )
    for index, entry in enumerate(entries):
        y_top = 0.985 - index * (card_height + card_gap)
        y_bottom = y_top - card_height
        ax.add_patch(
            FancyBboxPatch(
                (0.01, y_bottom),
                0.98,
                card_height,
                boxstyle="round,pad=0.008,rounding_size=0.014",
                transform=ax.transAxes,
                facecolor=WHITE,
                edgecolor=RED if index % 2 else BLUE,
                linewidth=0.9,
            )
        )
        ax.text(
            0.055,
            y_top - 0.030,
            f"D{index + 1}",
            transform=ax.transAxes,
            fontsize=7.0,
            weight="bold",
            color=WHITE,
            ha="center",
            va="center",
            bbox={
                "boxstyle": "round,pad=0.18",
                "facecolor": RED,
                "edgecolor": "none",
            },
        )
        wrapped_name = wrap_identifier(entry.name)
        ax.text(
            0.11,
            y_top - 0.020,
            wrapped_name,
            transform=ax.transAxes,
            fontsize=6.35,
            weight="bold",
            color=BLUE,
            va="top",
            linespacing=1.05,
        )
        name_lines = wrapped_name.count("\n") + 1
        value_y = y_top - 0.052 - 0.028 * name_lines
        value_text = dimension_value(entry)
        value_font_size = 6.2 if expanded_single else (5.0 if "\n" in value_text else 7.0)
        value_wrap_width = 34
        ax.text(
            0.055,
            value_y,
            textwrap.fill(
                value_text,
                width=value_wrap_width,
                break_long_words=False,
                break_on_hyphens=False,
                replace_whitespace=False,
            ),
            transform=ax.transAxes,
            fontsize=value_font_size,
            weight="bold",
            color=ORANGE,
            va="top",
            linespacing=1.08,
        )
        profile_note = " • profile-resolved" if entry.profile_controlled else ""
        ax.text(
            0.055,
            y_bottom + 0.020,
            f"{entry.category} • source line {entry.source_line}{profile_note}",
            transform=ax.transAxes,
            fontsize=5.25,
            color=GRAY,
            va="bottom",
        )


def page_dimension_drawing(pdf, page_number: int, view: str, entries) -> None:
    title = VIEW_TITLES[view]
    fig = new_page(
        page_number,
        title,
        "Red extension lines, arrows, arcs and feature leaders show each value; full CONFIG names appear at right.",
    )
    panel(
        fig,
        [0.055, 0.12, 0.66, 0.74],
        "ENGINEERING VIEW — ACTUAL STL ORTHOGRAPHIC PROJECTION",
        "Vector silhouette is calculated from the current generated component, not a generic placeholder.",
    )
    # Keep the orthographic geometry and its leaders below the fixed drawing
    # header.  A shared axis previously let tall projections overwrite the
    # title, making both the object and the proof label hard to read.
    drawing_ax = fig.add_axes([0.065, 0.135, 0.64, 0.625])
    drawing_ax.set_facecolor("none")
    drawing_ax.set_xticks([])
    drawing_ax.set_yticks([])
    for spine in drawing_ax.spines.values():
        spine.set_visible(False)
    bounds = draw_actual_view(drawing_ax, view)
    set_drawing_bounds(drawing_ax, bounds, padding_fraction=0.25)
    draw_graphical_annotations(drawing_ax, view, entries, bounds)
    panel(fig, [0.735, 0.12, 0.225, 0.74], "DIMENSION CALLOUTS")
    cards_ax = fig.add_axes([0.742, 0.135, 0.211, 0.625])
    cards_ax.set_facecolor("none")
    draw_dimension_cards(cards_ax, entries)
    pdf.savefig(fig)
    plt.close(fig)


def draw_assembly_thumbnail(ax):
    back = projected_part_geometry("back", "xz")
    insert = projected_part_geometry("insert", "xz")
    draw_projected_geometry(ax, back, "#dceaf3", BLUE, alpha=0.72)
    draw_projected_geometry(ax, insert, "#f7d9ca", ORANGE, alpha=0.72, zorder=3)
    if C["RETAINER_STYLE"] == "ROTATING_KEEPERS":
        keeper_base = projected_part_geometry("keeper", "xy", True)
        layout = sorted(C["CASE_FASTENER_POSITIONS_XZ"], key=lambda point: point[1])
        lower = sorted(layout[:2], key=lambda point: point[0])
        upper = layout[2]
        for x, z, angle in (
            (*lower[0], 0.0),
            (*lower[1], 0.0),
            (*upper, 180.0),
        ):
            keeper = affinity.rotate(keeper_base, angle, origin=(0, 0))
            keeper = affinity.translate(keeper, xoff=x, yoff=z)
            draw_projected_geometry(ax, keeper, "#eadcf1", RED, alpha=0.92, zorder=5)
    else:
        gate = projected_part_geometry("gate", "xy", True)
        draw_projected_geometry(ax, gate, "#d7efd9", GREEN, alpha=0.92, zorder=5)
    set_drawing_bounds(ax, union_bounds((back, insert)), padding_fraction=0.08)
    ax.set_title("ACTUAL ASSEMBLED-PART PROJECTIONS", fontsize=7.0, color=BLUE)


def page_settings_appendix(pdf, page_number: int, entries) -> None:
    fig = new_page(
        page_number,
        "NON-DIMENSIONAL CONFIGURATION APPENDIX",
        "Switches, filenames, material labels and viewport settings; dimensional controls are on drawing sheets.",
    )
    drawing_ax = panel(fig, [0.055, 0.15, 0.35, 0.66], "ASSEMBLY REFERENCE")
    draw_assembly_thumbnail(drawing_ax)
    cards = fig.add_axes([0.43, 0.12, 0.53, 0.73])
    cards.axis("off")
    row_height = 0.101
    for index, entry in enumerate(entries):
        y_top = 0.99 - index * row_height
        cards.add_patch(
            FancyBboxPatch(
                (0.0, y_top - 0.086),
                1.0,
                0.080,
                boxstyle="round,pad=0.005,rounding_size=0.008",
                transform=cards.transAxes,
                facecolor="#f8fbfc" if index % 2 == 0 else WHITE,
                edgecolor=GRID,
                linewidth=0.6,
            )
        )
        cards.text(
            0.015,
            y_top - 0.018,
            entry.name,
            transform=cards.transAxes,
            fontsize=6.3,
            weight="bold",
            color=BLUE,
            va="top",
        )
        cards.text(
            0.50,
            y_top - 0.018,
            textwrap.fill(fmt(entry.value), width=42, break_long_words=False),
            transform=cards.transAxes,
            fontsize=6.0,
            color=ORANGE,
            va="top",
            family="DejaVu Sans Mono",
        )
        cards.text(
            0.015,
            y_top - 0.055,
            textwrap.fill(entry.description, width=88, break_long_words=False),
            transform=cards.transAxes,
            fontsize=5.35,
            color=INK,
            va="top",
        )
    CATALOGUED_SETTING_NAMES.update(entry.name for entry in entries)
    pdf.savefig(fig)
    plt.close(fig)


def page_catalog(pdf):
    page_number = 8
    for view, entries in DRAWING_PAGE_GROUPS:
        page_dimension_drawing(pdf, page_number, view, entries)
        page_number += 1
    for start in range(0, len(NON_DIMENSION_SETTING_ENTRIES), SETTINGS_PER_PAGE):
        page_settings_appendix(
            pdf,
            page_number,
            NON_DIMENSION_SETTING_ENTRIES[start : start + SETTINGS_PER_PAGE],
        )
        page_number += 1
    if page_number != TOTAL_PAGES:
        raise RuntimeError(
            f"Drawing-page assembly ended at {page_number}; coverage page is "
            f"configured as {TOTAL_PAGES}"
        )


def page_coverage(pdf):
    fig = new_page(TOTAL_PAGES, "COVERAGE AND SYNCHRONIZATION PROOF", "The generated guide fails rather than silently omitting CONFIG assignments")
    ax = fig.add_axes([0.07, 0.14, 0.86, 0.70])
    ax.axis("off")
    categories = {}
    for entry in CONFIG_ENTRIES:
        categories[entry.category] = categories.get(entry.category, 0) + 1
    ax.add_patch(FancyBboxPatch((0.0, 0.70), 1.0, 0.26, boxstyle="round,pad=0.015,rounding_size=0.02", transform=ax.transAxes, facecolor=LIGHT, edgecolor=GRID))
    ax.text(0.04, 0.89, "ENGINEERING-DRAWING COVERAGE", transform=ax.transAxes, fontsize=12, weight="bold", color=BLUE)
    ax.text(
        0.04,
        0.83,
        f"{len(GRAPHICALLY_ANNOTATED_NAMES)} / {len(VISUAL_DIMENSION_ENTRIES)} dimensional controls graphically annotated with endpoint records",
        transform=ax.transAxes,
        fontsize=10,
        weight="bold",
        color=GREEN,
    )
    ax.text(
        0.04,
        0.785,
        f"{len(CATALOGUED_SETTING_NAMES)} / {len(NON_DIMENSION_SETTING_ENTRIES)} non-dimensional settings documented",
        transform=ax.transAxes,
        fontsize=8.0,
        weight="bold",
        color=GREEN,
    )
    ax.text(0.04, 0.735, f"Model + generator + STL fingerprint: source-{SOURCE_HASH}", transform=ax.transAxes, fontsize=7.4, color=GRAY)
    sorted_categories = sorted(categories.items())
    category_columns = 3
    rows_per_column = math.ceil(len(sorted_categories) / category_columns)
    for index, (category, count) in enumerate(sorted_categories):
        column = index // rows_per_column
        row = index % rows_per_column
        x = 0.02 + column * 0.33
        y = 0.62 - row * 0.082
        ax.text(x, y, f"{count:>3}", transform=ax.transAxes, fontsize=8.0, weight="bold", color=ORANGE)
        ax.text(x + 0.045, y, category, transform=ax.transAxes, fontsize=6.6, color=INK)
    ax.add_patch(FancyBboxPatch((0.0, 0.04), 1.0, 0.13, boxstyle="round,pad=0.015,rounding_size=0.02", transform=ax.transAxes, facecolor=WHITE, edgecolor=BLUE))
    ax.text(0.03, 0.125, "SYNC CONTRACT", transform=ax.transAxes, fontsize=8.5, weight="bold", color=BLUE)
    ax.text(
        0.03,
        0.075,
        "Before writing, the generator requires one finite, non-degenerate graphical primitive record per dimensional control. make check-fan-case-dim-pdf-sync then extracts each cropped engineering panel, requires its matching annotation label, and independently verifies the complete CONFIG name/value in the cropped callout-card region. It also checks the source fingerprint, page count, coverage manifest and PDF EOF marker.",
        transform=ax.transAxes,
        fontsize=7.1,
        color=INK,
        wrap=True,
    )
    pdf.savefig(fig)
    plt.close(fig)


def normalized_pdf_text(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def validate_pdf_engineering_drawings() -> None:
    """Extract the PDF and prove each planned dimension is on its drawing."""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(OUTPUT_PDF), "-"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Engineering-drawing validation requires the `pdftotext` command"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Could not extract the dimension guide for drawing validation: "
            + exc.stderr.strip()
        ) from exc

    extracted_pages = result.stdout.split("\f")
    if extracted_pages and not extracted_pages[-1].strip():
        extracted_pages.pop()
    if len(extracted_pages) != TOTAL_PAGES:
        raise RuntimeError(
            "Engineering-drawing text extraction found "
            f"{len(extracted_pages)} pages; expected {TOTAL_PAGES}"
        )

    try:
        drawing_result = subprocess.run(
            [
                "pdftotext",
                "-layout",
                "-x",
                "0",
                "-y",
                "0",
                "-W",
                "575",
                "-H",
                "612",
                str(OUTPUT_PDF),
                "-",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "Could not extract cropped engineering panels for graphical-dimension validation"
        ) from exc
    drawing_pages = drawing_result.stdout.split("\f")
    if drawing_pages and not drawing_pages[-1].strip():
        drawing_pages.pop()
    if len(drawing_pages) != TOTAL_PAGES:
        raise RuntimeError(
            "Cropped engineering-panel extraction found "
            f"{len(drawing_pages)} pages; expected {TOTAL_PAGES}"
        )
    try:
        card_result = subprocess.run(
            [
                "pdftotext",
                "-layout",
                "-x",
                "575",
                "-y",
                "0",
                "-W",
                "217",
                "-H",
                "612",
                str(OUTPUT_PDF),
                "-",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "Could not extract dimension cards for exact-name/value validation"
        ) from exc
    card_pages = card_result.stdout.split("\f")
    if card_pages and not card_pages[-1].strip():
        card_pages.pop()
    if len(card_pages) != TOTAL_PAGES:
        raise RuntimeError(
            "Dimension-card extraction found "
            f"{len(card_pages)} pages; expected {TOTAL_PAGES}"
        )

    failures: list[str] = []
    for page_offset, (_view, entries) in enumerate(DRAWING_PAGE_GROUPS):
        page_number = 8 + page_offset
        page_text = normalized_pdf_text(extracted_pages[page_number - 1])
        drawing_text = normalized_pdf_text(drawing_pages[page_number - 1])
        card_text = normalized_pdf_text(card_pages[page_number - 1])
        for required_label in (
            "ENGINEERING VIEW",
            "ACTUAL STL ORTHOGRAPHIC PROJECTION",
        ):
            if normalized_pdf_text(required_label) not in page_text:
                failures.append(f"sheet {page_number}: missing {required_label!r}")
        for entry in entries:
            annotation_index = entries.index(entry)
            graphical_label = graphical_annotation_label(entry, annotation_index)
            if normalized_pdf_text(graphical_label) not in drawing_text:
                failures.append(
                    f"sheet {page_number}: {entry.name} missing graphical annotation "
                    f"{graphical_label!r} inside engineering panel"
                )
            expected_name = normalized_pdf_text(entry.name)
            expected_value = normalized_pdf_text(dimension_value(entry))
            missing_fields = []
            if expected_name not in card_text:
                missing_fields.append(entry.name)
            if expected_value not in card_text:
                missing_fields.append(dimension_value(entry))
            if missing_fields:
                failures.append(
                    f"sheet {page_number}: {entry.name} missing complete card fields "
                    f"{missing_fields}"
                )
    if failures:
        raise RuntimeError(
            "Engineering-drawing coverage validation failed:\n  "
            + "\n  ".join(failures)
        )


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
    for marker in (VISUAL_COVERAGE_MARKER, SETTINGS_COVERAGE_MARKER):
        if marker.encode("ascii") not in data:
            raise RuntimeError(
                f"Incomplete dimension guide: missing coverage marker {marker}. "
                "Regenerate it with `make fan-case-dim-pdf`."
            )
    if not data.rstrip().endswith(b"%%EOF"):
        raise RuntimeError(f"Incomplete dimension guide: {OUTPUT_PDF.name} has no PDF EOF marker")
    page_count = len(re.findall(rb"/Type\s*/Page\b", data))
    if page_count != TOTAL_PAGES:
        raise RuntimeError(
            f"Incomplete dimension guide: {OUTPUT_PDF.name} has {page_count} pages; "
            f"expected {TOTAL_PAGES}."
        )
    validate_pdf_engineering_drawings()
    print(
        f"Synchronized {OUTPUT_PDF} source={SOURCE_HASH} pages={TOTAL_PAGES} "
        f"visual_dimensions={len(VISUAL_DIMENSION_ENTRIES)}/{len(VISUAL_DIMENSION_ENTRIES)} "
        f"settings={len(NON_DIMENSION_SETTING_ENTRIES)}/{len(NON_DIMENSION_SETTING_ENTRIES)}"
    )


def validate_rendered_coverage() -> None:
    expected_visual = {entry.name for entry in VISUAL_DIMENSION_ENTRIES}
    expected_settings = {entry.name for entry in NON_DIMENSION_SETTING_ENTRIES}
    if GRAPHICALLY_ANNOTATED_NAMES != expected_visual:
        raise RuntimeError(
            "Engineering drawings did not graphically annotate every dimensional CONFIG: "
            f"missing={sorted(expected_visual - GRAPHICALLY_ANNOTATED_NAMES)}, "
            f"unexpected={sorted(GRAPHICALLY_ANNOTATED_NAMES - expected_visual)}"
        )
    if set(GRAPHICAL_PRIMITIVE_RECORDS) != expected_visual:
        raise RuntimeError(
            "Engineering-drawing primitive coverage mismatch: "
            f"missing={sorted(expected_visual - set(GRAPHICAL_PRIMITIVE_RECORDS))}, "
            f"unexpected={sorted(set(GRAPHICAL_PRIMITIVE_RECORDS) - expected_visual)}"
        )
    invalid_primitives = []
    for name, (primitive_kind, points) in GRAPHICAL_PRIMITIVE_RECORDS.items():
        if len(points) < 2 or not all(
            math.isfinite(coordinate)
            for point in points
            for coordinate in point
        ):
            invalid_primitives.append(f"{name}:{primitive_kind}:invalid-points")
            continue
        if max(
            math.hypot(point[0] - points[0][0], point[1] - points[0][1])
            for point in points[1:]
        ) <= 1.0e-9:
            invalid_primitives.append(f"{name}:{primitive_kind}:degenerate")
    if invalid_primitives:
        raise RuntimeError(
            "Invalid graphical dimension primitives: "
            + ", ".join(invalid_primitives)
        )
    invalid_kinds = sorted(
        name
        for name in expected_visual
        if GRAPHICAL_ANNOTATION_KINDS.get(name)
        not in {
            "datum_specification",
            "angular_arc",
            "construction_note",
            "diameter_dimension",
            "radius_leader",
            "x_ordinate",
            "z_ordinate",
            "horizontal_linear",
            "vertical_linear",
            "axial_linear",
            "feature_leader",
        }
    )
    if invalid_kinds:
        raise RuntimeError(
            f"Invalid or missing graphical annotation kinds: {invalid_kinds}"
        )
    if CATALOGUED_SETTING_NAMES != expected_settings:
        raise RuntimeError(
            "Settings appendix coverage mismatch: "
            f"missing={sorted(expected_settings - CATALOGUED_SETTING_NAMES)}, "
            f"unexpected={sorted(CATALOGUED_SETTING_NAMES - expected_settings)}"
        )


def main():
    GRAPHICALLY_ANNOTATED_NAMES.clear()
    GRAPHICAL_ANNOTATION_KINDS.clear()
    GRAPHICAL_PRIMITIVE_RECORDS.clear()
    CATALOGUED_SETTING_NAMES.clear()
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
                "Title": "GoPro Fan-Case Engineering Drawing and Configuration Guide",
                "Author": "Generated from gopro_fan_case_parametric_blender.py",
                "Subject": "Back shell, sleeve capture groove and insert dimensions",
                "Keywords": (
                    "GoPro fan case engineering drawings "
                    f"source-{SOURCE_HASH} {VISUAL_COVERAGE_MARKER} "
                    f"{SETTINGS_COVERAGE_MARKER}"
                ),
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
            validate_rendered_coverage()
            page_coverage(pdf)
        temporary_path.replace(OUTPUT_PDF)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    print(
        f"Wrote {OUTPUT_PDF} pages={TOTAL_PAGES} config={len(CONFIG_ENTRIES)} "
        f"source={SOURCE_HASH} visual_dimensions="
        f"{len(GRAPHICALLY_ANNOTATED_NAMES)}/{len(VISUAL_DIMENSION_ENTRIES)} "
        f"settings={len(CATALOGUED_SETTING_NAMES)}/{len(NON_DIMENSION_SETTING_ENTRIES)}"
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
