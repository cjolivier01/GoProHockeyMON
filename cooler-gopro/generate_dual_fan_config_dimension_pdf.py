#!/usr/bin/env python3
"""Generate the dual-fan holder configuration dimension guide.

The model is parsed without importing Blender. Every uppercase CONFIG value is
catalogued, material-profile dimensions are resolved for the selected profile,
and the shared 40/60/80/120 mm fan references are expanded into individual
engineering dimensions. Printable holder and adapter views come from their
current STL files; disabled alternate geometry is drawn from the same
parameters used by the Blender generator.
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
from fan_size_presets import STANDARD_FAN_PRESETS
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Arc, Circle, FancyArrowPatch, FancyBboxPatch
from matplotlib.patches import Polygon, Rectangle
from shapely import affinity
from shapely.geometry import MultiPolygon
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union


HERE = Path(__file__).absolute().parent
MODEL_SOURCE = HERE / "dual_fan_parametric_blender.py"
PRESET_SOURCE = HERE / "fan_size_presets.py"
OUTPUT_PDF = HERE / "gopro_dual_fan_configuration_dimensions.pdf"
PART_STLS = {
    "holder": HERE / "gopro_dual_fan_parametric.stl",
    "adapter": HERE / "gopro_dual_fan_adapter.stl",
}

INK = "#152536"
BLUE = "#176ea6"
CYAN = "#55a9c5"
ORANGE = "#d66b2d"
GREEN = "#3d8a61"
RED = "#b54848"
PURPLE = "#7553a6"
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


@dataclass(frozen=True)
class DimensionEntry:
    identity: str
    source_name: str
    value: object
    unit: str
    category: str
    description: str
    source_line: int
    profile_controlled: bool
    view: str


CATEGORY_PREFIXES = (
    ("Build, export and mesh", ("CLEAR_", "EXPORT_", "BOOLEAN_", "UNION_", "DEBUG_", "CYLINDER_", "CORNER_", "CLEAN_", "TRIANGULATION_", "ASSEMBLY_")),
    ("Material and print guidance", ("MATERIAL_", "TPU_")),
    ("Fan array and rotation", ("FAN_COUNT", "FAN_SIZES", "FAN_ROTATIONS", "FAN_REFERENCE", "FAN_BODY_GAP", "FAN_ROTATION_")),
    ("Fan cage and grille", ("FAN_FRAME_", "FAN_BODY_CLEARANCE", "AIRFLOW_", "GRILL_", "FAN_HOLE_", "FAN_WIRE_")),
    ("Airflow splitter", ("SINGLE_FAN_",)),
    ("Support structure", ("SUPPORT_",)),
    ("Stalk route", ("STALK_",)),
    ("Receiver block", ("MOUNT_",)),
    ("GoPro adapter", ("GOPRO_",)),
)


EXACT_DESCRIPTIONS = {
    "FAN_SIZES_MM": "Nominal square-frame size for each configurable fan slot.",
    "FAN_ROTATIONS_DEG": "XYZ cage rotation for each fan about the selected pivot.",
    "FAN_BODY_GAP_MM": "Clear distance between adjacent nominal fan bodies.",
    "FAN_BODY_CLEARANCE_PER_SIDE": "Running clearance on each side of a fan body inside its cage.",
    "FAN_FRAME_DEPTH": "Axial depth of the printed fan cage, excluding any protruding fan body.",
    "FAN_FRAME_WALL": "Material-profile wall thickness outside the fan cavity.",
    "STALK_ROUTE_DROP_Y": "Downward travel after the receiver when the routed stalk is enabled.",
    "STALK_ROUTE_BACK_Z": "Straight rearward leg between the routed stalk transitions.",
    "STALK_ROUTE_RETURN_RISE_Y": "Upward return into the fan support at the routed stalk end.",
    "STALK_LATERAL_DEFLECTION_X": "Signed fan/support offset from the mounting-block centerline; zero is inline, and shorter stalks produce a greater angle for the same offset.",
    "SINGLE_FAN_SPLITTER_OUTLET_ANGLE_DEG": "Outward airflow angle of each splitter vane from the fan axis.",
    "SINGLE_FAN_SPLITTER_VANE_LENGTH_Z": "Camera-facing axial length of the two airflow vanes.",
    "SUPPORT_HUB_WIDTH_OVERRIDE": "Optional explicit support-hub width; None uses width-per-fan times fan count.",
    "GOPRO_PIVOT_FROM_MATING_FACE_Y": "Distance from the adapter mating face to the GoPro pivot axis.",
    "GOPRO_PIVOT_BELOW_MOUNT_HOLES_Z": "Vertical offset from the receiver fastener row to the GoPro pivot axis.",
}


def category_for(name: str) -> str:
    for category, prefixes in CATEGORY_PREFIXES:
        if name.startswith(prefixes):
            return category
    return "Other configuration"


def humanize(name: str) -> str:
    words = name.lower().replace("_", " ")
    words = words.replace(" gopro ", " GoPro ")
    words = words.replace(" tpu ", " TPU ")
    words = words.replace(" stl ", " STL ")
    return words.strip().capitalize()


def description_for(name: str, category: str) -> str:
    if name in EXACT_DESCRIPTIONS:
        return EXACT_DESCRIPTIONS[name]
    if name.endswith("_ENABLED"):
        return f"Switch controlling {humanize(name).lower()}."
    if name.endswith(("_PATH", "_DIRECTORY")):
        return f"Output location for {humanize(name).lower()}."
    if name.endswith(("_COUNT", "_SEGMENTS", "_SECTIONS", "_WALLS")):
        return f"Discrete count or resolution setting for {humanize(name).lower()}."
    return f"{humanize(name)}; part of the {category.lower()} configuration."


DIMENSIONLESS_NUMERIC_NAMES = {
    "CYLINDER_SEGMENTS",
    "CORNER_SEGMENTS",
    "FAN_COUNT",
    "GOPRO_ADAPTER_PRONG_COUNT",
    "SUPPORT_ARM_SECTIONS",
}


def unit_for(name: str, value: object) -> str:
    if name == "SUPPORT_HUB_WIDTH_OVERRIDE":
        return "mm"
    if isinstance(value, bool) or isinstance(value, str) or value is None:
        return "setting"
    if name in DIMENSIONLESS_NUMERIC_NAMES:
        return "setting"
    if name in {"TPU_95A_RECOMMENDED_INFILL_PERCENT", "TPU_95A_RECOMMENDED_WALLS"}:
        return "setting"
    if isinstance(value, (tuple, list, dict)):
        return "setting"
    if name.endswith("_DEG"):
        return "deg"
    if name == "BOOLEAN_MINIMUM_VOLUME_CHANGE":
        return "mm³"
    return "mm"


def assignment_names(statement: ast.stmt) -> set[str]:
    if isinstance(statement, ast.Assign):
        return {
            target.id
            for target in statement.targets
            if isinstance(target, ast.Name)
        }
    if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
        return {statement.target.id}
    return set()


def read_model_config():
    tree = ast.parse(MODEL_SOURCE.read_text(encoding="utf-8"), filename=str(MODEL_SOURCE))
    line_by_name = {
        name: statement.lineno
        for statement in tree.body
        for name in assignment_names(statement)
    }
    try:
        start_line = line_by_name["CLEAR_SCENE"]
        end_line = line_by_name["_APPLIED_MATERIAL_MODE"]
    except KeyError as exc:
        raise RuntimeError("Could not identify the dual-fan CONFIG boundaries") from exc

    expected_names = {
        name
        for statement in tree.body
        if start_line <= getattr(statement, "lineno", -1) < end_line
        for name in assignment_names(statement)
        if name.isupper() and not name.startswith("_")
    }
    env: dict[str, object] = {"STANDARD_FAN_PRESETS": STANDARD_FAN_PRESETS}
    parsed: list[tuple[str, object, int]] = []
    unsupported = []
    for statement in tree.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        names = assignment_names(statement)
        if len(names) != 1:
            continue
        name = next(iter(names))
        expression = statement.value
        if expression is None:
            continue
        if name == "FAN_PRESETS":
            value = {size: dict(preset) for size, preset in STANDARD_FAN_PRESETS.items()}
        else:
            try:
                value = safe_value(expression, env)
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                if name in expected_names:
                    unsupported.append((name, statement.lineno))
                continue
        env[name] = value
        parsed.append((name, value, statement.lineno))
    if unsupported:
        raise RuntimeError(f"Unsupported uppercase dual-fan CONFIG assignments: {unsupported}")

    source_config = {
        name: (value, line)
        for name, value, line in parsed
        if name in expected_names
    }
    if set(source_config) != expected_names:
        raise RuntimeError(
            "Dual-fan CONFIG catalog mismatch: "
            f"missing={sorted(expected_names - set(source_config))} "
            f"unexpected={sorted(set(source_config) - expected_names)}"
        )
    mode = source_config["MATERIAL_MODE"][0]
    profiles = env.get("MATERIAL_PROFILES")
    if not isinstance(profiles, dict) or mode not in profiles:
        raise RuntimeError(f"Could not resolve material profile {mode!r}")
    selected_profile = dict(profiles[mode])

    entries = []
    for name, (source_value, line) in sorted(source_config.items(), key=lambda item: item[1][1]):
        value = selected_profile.get(name, source_value)
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
                profile_controlled=name in selected_profile,
            )
        )
    profile_line = line_by_name["MATERIAL_PROFILES"]
    existing = {entry.name for entry in entries}
    for name, value in selected_profile.items():
        if name in existing:
            continue
        category = category_for(name)
        entries.append(
            ConfigEntry(
                name=name,
                value=value,
                source_value=None,
                source_line=profile_line,
                category=category,
                description=description_for(name, category),
                unit=unit_for(name, value),
                profile_controlled=True,
            )
        )
    return env, tuple(entries), frozenset(expected_names)


ENV, CONFIG_ENTRIES, EXPECTED_CONFIG_NAMES = read_model_config()
C = {entry.name: entry.value for entry in CONFIG_ENTRIES}


def require_current_part_stls() -> None:
    missing = [path.name for path in PART_STLS.values() if not path.is_file()]
    if missing:
        raise RuntimeError(
            "Engineering drawings require the generated dual-fan STLs; "
            "run `make dual-fan` first. Missing: " + ", ".join(missing)
        )
    source_mtime = max(MODEL_SOURCE.stat().st_mtime, PRESET_SOURCE.stat().st_mtime)
    stale = [
        path.name
        for path in PART_STLS.values()
        if path.stat().st_mtime + 1.0e-6 < source_mtime
    ]
    if stale:
        raise RuntimeError(
            "Engineering-drawing STL projections are stale; run "
            "`make -B dual-fan`. Stale: " + ", ".join(stale)
        )


require_current_part_stls()
SOURCE_HASH = hashlib.sha256(
    MODEL_SOURCE.read_bytes()
    + PRESET_SOURCE.read_bytes()
    + Path(__file__).read_bytes()
    + b"".join(path.read_bytes() for path in PART_STLS.values())
).hexdigest()[:12]


def base_name(identity: str) -> str:
    return identity.split("[", 1)[0]


def view_for(name: str) -> str:
    if name.startswith("STANDARD_FAN_PRESETS["):
        size = name.split("[", 1)[1].split("]", 1)[0]
        suffix = "_side" if name.endswith(".DEPTH") else ""
        return f"preset_{size}{suffix}"
    root = base_name(name)
    if root in {"FAN_SIZES_MM", "FAN_ROTATIONS_DEG", "FAN_BODY_GAP_MM"}:
        return "array_front"
    if root.startswith(("BOOLEAN_", "CLEAN_", "TRIANGULATION_")):
        return "mesh_detail"
    if root == "TPU_95A_MOUNT_SCREW_EXTRA_LENGTH_MM":
        return "assembly_side"
    if root.startswith("SINGLE_FAN_"):
        if root == "SINGLE_FAN_SPLITTER_HOLDER_CLEARANCE":
            return "splitter_clearance"
        if any(token in root for token in ("LENGTH_Z", "PLATE_THICKNESS", "VANE_THICKNESS", "HOLDER_CLEARANCE", "OUTLET_ANGLE")):
            return "splitter_side"
        return "splitter_front"
    if root.startswith("SUPPORT_"):
        if root == "SUPPORT_THICKNESS":
            return "support_side"
        return "support_front"
    if root.startswith("STALK_"):
        if root in {
            "STALK_WIDTH",
            "STALK_HUB_FLARE_WIDTH",
            "STALK_LATERAL_DEFLECTION_X",
        }:
            return "stalk_front"
        return "stalk_side"
    if root.startswith("MOUNT_"):
        if root in {"MOUNT_BLOCK_DEPTH_Y", "MOUNT_COUNTERSINK_DEPTH"}:
            return "mount_side"
        return "mount_detail"
    if root.startswith("GOPRO_"):
        if any(token in root for token in ("MATING_GAP", "INSERT_DEPTH", "TRANSITION_DEPTH", "PLATE_DEPTH_Y", "PIVOT_FROM", "PIVOT_BELOW", "PRONG_RADIUS", "PIVOT_HOLE")):
            return "adapter_side"
        return "adapter_front"
    if root.startswith("FAN_ROTATION_"):
        if root in {"FAN_ROTATION_PIVOT_INWARD_X_AT_REFERENCE", "FAN_ROTATION_PIVOT_ABOVE_BOTTOM_Y"}:
            return "fan_reference"
        return "fan_side"
    if root.startswith("FAN_WIRE_"):
        if root == "FAN_WIRE_SLOT_OFFSET_AT_REFERENCE":
            return "fan_reference"
        if root == "FAN_WIRE_SLOT_WIDTH":
            return "fan_front"
        return "fan_side"
    if root.startswith("FAN_HOLE_") and any(token in root for token in ("DEPTH", "HEIGHT")):
        return "fan_side"
    if root in {"FAN_FRAME_DEPTH", "GRILL_THICKNESS", "FAN_HOLE_COLLAR_HEIGHT"}:
        return "fan_side"
    if root in {
        "FAN_REFERENCE_SIZE_MM",
        "FAN_ROTATION_PIVOT_INWARD_X_AT_REFERENCE",
        "FAN_ROTATION_PIVOT_ABOVE_BOTTOM_Y",
        "AIRFLOW_DIAMETER_AT_REFERENCE",
        "GRILL_CENTER_DISK_DIAMETER_AT_REFERENCE",
        "GRILL_RING_CENTER_RADII_AT_REFERENCE",
        "FAN_WIRE_SLOT_OFFSET_AT_REFERENCE",
    }:
        return "fan_reference"
    if root.startswith(("FAN_", "AIRFLOW_", "GRILL_")):
        return "fan_front"
    return "assembly_front"


def expand_dimensions(entries: tuple[ConfigEntry, ...]) -> tuple[DimensionEntry, ...]:
    dimensions = []
    for entry in entries:
        expanded: list[tuple[str, object, str]] = []
        if entry.name == "FAN_SIZES_MM":
            expanded = [
                (f"FAN_SIZES_MM[{index}]", value, "mm")
                for index, value in enumerate(entry.value)
            ]
        elif entry.name == "FAN_ROTATIONS_DEG":
            expanded = [
                (f"FAN_ROTATIONS_DEG[{fan_index}].{axis}", value, "deg")
                for fan_index, rotation in enumerate(entry.value)
                for axis, value in zip("XYZ", rotation)
            ]
        elif entry.name == "GRILL_RING_CENTER_RADII_AT_REFERENCE":
            expanded = [
                (f"GRILL_RING_CENTER_RADII_AT_REFERENCE[{index}]", value, "mm")
                for index, value in enumerate(entry.value)
            ]
        elif entry.unit != "setting":
            expanded = [(entry.name, entry.value, entry.unit)]
        for identity, value, unit in expanded:
            dimensions.append(
                DimensionEntry(
                    identity=identity,
                    source_name=entry.name,
                    value=value,
                    unit=unit,
                    category=entry.category,
                    description=entry.description,
                    source_line=entry.source_line,
                    profile_controlled=entry.profile_controlled,
                    view=view_for(identity),
                )
            )
    preset_tree = ast.parse(PRESET_SOURCE.read_text(encoding="utf-8"))
    preset_line = next(
        statement.lineno
        for statement in preset_tree.body
        if "STANDARD_FAN_PRESETS" in assignment_names(statement)
    )
    labels = {
        "frame": "Nominal square fan frame size.",
        "depth": "Purchased fan body depth.",
        "hole_spacing": "Square mounting-hole center spacing.",
        "hole_diameter": "Manufacturer mounting-hole diameter reference.",
        "opening": "Nominal unobstructed fan-face opening.",
        "hub": "Nominal motor-hub diameter.",
    }
    for size, preset in sorted(STANDARD_FAN_PRESETS.items()):
        for key, description in labels.items():
            identity = f"STANDARD_FAN_PRESETS[{size}].{key.upper()}"
            dimensions.append(
                DimensionEntry(
                    identity=identity,
                    source_name="FAN_PRESETS",
                    value=preset[key],
                    unit="mm",
                    category="Standard fan references",
                    description=description,
                    source_line=preset_line,
                    profile_controlled=False,
                    view=view_for(identity),
                )
            )
    return tuple(dimensions)


DIMENSION_ENTRIES = expand_dimensions(CONFIG_ENTRIES)
DIMENSION_IDENTITIES = frozenset(entry.identity for entry in DIMENSION_ENTRIES)
if len(DIMENSION_IDENTITIES) != len(DIMENSION_ENTRIES):
    raise RuntimeError("Duplicate identities in dual-fan dimensional inventory")

DIMENSION_SOURCE_NAMES = {entry.source_name for entry in DIMENSION_ENTRIES}
SETTING_ENTRIES = tuple(
    entry
    for entry in CONFIG_ENTRIES
    if entry.name not in DIMENSION_SOURCE_NAMES
)

VIEW_ORDER = (
    "array_front",
    "assembly_front",
    "assembly_side",
    "fan_front",
    "fan_reference",
    "fan_side",
    "support_front",
    "support_side",
    "stalk_front",
    "stalk_side",
    "mount_detail",
    "mount_side",
    "adapter_front",
    "adapter_side",
    "splitter_front",
    "splitter_side",
    "splitter_clearance",
    "mesh_detail",
    "preset_40",
    "preset_40_side",
    "preset_60",
    "preset_60_side",
    "preset_80",
    "preset_80_side",
    "preset_120",
    "preset_120_side",
)
VIEW_TITLES = {
    "array_front": "FAN ARRAY — ACTUAL HOLDER FRONT PROJECTION",
    "assembly_front": "COMPLETE HOLDER — ACTUAL FRONT PROJECTION",
    "assembly_side": "HOLDER + ADAPTER — ACTUAL SIDE PROJECTION",
    "fan_front": "FAN CAGE / GRILLE — ACTUAL FRONT PROJECTION",
    "fan_reference": "60 MM REFERENCE CAGE — PARAMETRIC FRONT GEOMETRY",
    "fan_side": "FAN CAGE / WIRE EXIT — ACTUAL SIDE PROJECTION",
    "support_front": "TWISTED SUPPORT + HUB — ACTUAL FRONT PROJECTION",
    "support_side": "TWISTED SUPPORT THICKNESS — ACTUAL SIDE PROJECTION",
    "stalk_front": "STALK LATERAL OFFSET AND FLARE WIDTHS — ACTUAL XZ PROJECTION",
    "stalk_side": "STRAIGHT + LOWERED STALK ROUTES — ACTUAL ASSEMBLY REFERENCE",
    "mount_detail": "TWO-HOLE RECEIVER — ACTUAL ORTHOGRAPHIC PROJECTION",
    "mount_side": "TWO-HOLE RECEIVER DEPTH — ACTUAL SIDE PROJECTION",
    "adapter_front": "DETACHABLE GOPRO ADAPTER — ACTUAL FRONT PROJECTION",
    "adapter_side": "DETACHABLE GOPRO ADAPTER — ACTUAL SIDE PROJECTION",
    "splitter_front": "BOLT-ON AIRFLOW SPLITTER — PARAMETRIC FRONT GEOMETRY",
    "splitter_side": "BOLT-ON AIRFLOW SPLITTER — PARAMETRIC SIDE GEOMETRY",
    "splitter_clearance": "SPLITTER / LOWERED HOLDER CLEARANCE — PARAMETRIC SIDE SECTION",
    "mesh_detail": "BOOLEAN / TESSELLATION CONTROLS ON ACTUAL HOLDER",
    "preset_40": "40 MM STANDARD FAN — ENGINEERING REFERENCE",
    "preset_40_side": "40 MM STANDARD FAN DEPTH — SIDE REFERENCE",
    "preset_60": "60 MM STANDARD FAN — ENGINEERING REFERENCE",
    "preset_60_side": "60 MM STANDARD FAN DEPTH — SIDE REFERENCE",
    "preset_80": "80 MM STANDARD FAN — ENGINEERING REFERENCE",
    "preset_80_side": "80 MM STANDARD FAN DEPTH — SIDE REFERENCE",
    "preset_120": "120 MM STANDARD FAN — ENGINEERING REFERENCE",
    "preset_120_side": "120 MM STANDARD FAN DEPTH — SIDE REFERENCE",
}

DRAWINGS_PER_PAGE = 3
SETTINGS_PER_PAGE = 8
entries_by_view = {view: [] for view in VIEW_ORDER}
for dimension_entry in DIMENSION_ENTRIES:
    entries_by_view[dimension_entry.view].append(dimension_entry)
DRAWING_PAGE_GROUPS = tuple(
    (view, tuple(entries[index:index + DRAWINGS_PER_PAGE]))
    for view in VIEW_ORDER
    for entries in (entries_by_view[view],)
    for index in range(0, len(entries), DRAWINGS_PER_PAGE)
)
planned = [entry.identity for _view, group in DRAWING_PAGE_GROUPS for entry in group]
if set(planned) != DIMENSION_IDENTITIES or len(planned) != len(set(planned)):
    raise RuntimeError(
        "Invalid dual-fan engineering-drawing plan: "
        f"missing={sorted(DIMENSION_IDENTITIES - set(planned))}"
    )

CURATED_PAGE_COUNT = 3
DRAWING_PAGE_COUNT = len(DRAWING_PAGE_GROUPS)
SETTINGS_PAGE_COUNT = math.ceil(len(SETTING_ENTRIES) / SETTINGS_PER_PAGE)
TOTAL_PAGES = 1 + CURATED_PAGE_COUNT + DRAWING_PAGE_COUNT + SETTINGS_PAGE_COUNT + 1
VISUAL_MANIFEST_HASH = hashlib.sha256(
    "\n".join(
        f"{view}:{entry.identity}:{entry.unit}"
        for view, group in DRAWING_PAGE_GROUPS
        for entry in group
    ).encode("utf-8")
).hexdigest()[:12]
VISUAL_COVERAGE_MARKER = (
    f"engineering-dimensions-{len(DIMENSION_ENTRIES)}-of-"
    f"{len(DIMENSION_ENTRIES)}-manifest-{VISUAL_MANIFEST_HASH}"
)
FEATURE_CALLOUT_MARKER = (
    f"feature-callouts-{len(DIMENSION_ENTRIES)}-of-{len(DIMENSION_ENTRIES)}"
)
SETTINGS_COVERAGE_MARKER = f"settings-{len(SETTING_ENTRIES)}-of-{len(SETTING_ENTRIES)}"
DRAWN_DIMENSION_IDENTITIES: set[str] = set()
CATALOGUED_SETTING_NAMES: set[str] = set()


def fmt(value: object) -> str:
    if value is None:
        return "AUTO / None"
    if isinstance(value, float):
        if value == 0.0:
            return "0.0"
        if abs(value) < 0.001:
            return f"{value:.3g}"
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if isinstance(value, dict):
        return f"{len(value)} keyed entries"
    if isinstance(value, (tuple, list)) and len(value) > 4:
        return f"{len(value)} entries"
    return repr(value)


def dimension_value(entry: DimensionEntry) -> str:
    if entry.identity == "SUPPORT_HUB_WIDTH_OVERRIDE" and entry.value is None:
        resolved = float(C["SUPPORT_HUB_WIDTH_PER_FAN"]) * int(C["FAN_COUNT"])
        return f"AUTO / None → {fmt(resolved)} mm"
    return f"{fmt(entry.value)} {entry.unit}"


def wrap_identifier(name: str, width: int = 31) -> str:
    segments = re.findall(r"[^_]+_?", name)
    lines = []
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


PROJECTION_AXES = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}


@lru_cache(maxsize=None)
def projected_part_geometry(part: str, plane: str):
    axes = PROJECTION_AXES[plane]
    polygons = []
    for triangle in load_stl_triangles(part):
        points = triangle[:, axes]
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
    return unary_union(polygons)


def geometry_polygons(geometry):
    if geometry.geom_type == "Polygon":
        return (geometry,)
    if isinstance(geometry, MultiPolygon):
        return tuple(geometry.geoms)
    return tuple(item for item in geometry.geoms if item.geom_type == "Polygon")


def draw_projected_geometry(ax, geometry, facecolor, edgecolor, alpha=1.0, zorder=1):
    for polygon in geometry_polygons(geometry):
        ax.add_patch(
            Polygon(
                np.asarray(polygon.exterior.coords),
                closed=True,
                facecolor=facecolor,
                edgecolor=edgecolor,
                alpha=alpha,
                linewidth=0.9,
                zorder=zorder,
            )
        )
        for interior in polygon.interiors:
            ax.add_patch(
                Polygon(
                    np.asarray(interior.coords),
                    closed=True,
                    facecolor=WHITE,
                    edgecolor=edgecolor,
                    linewidth=0.45,
                    zorder=zorder + 0.1,
                )
            )


def merged_bounds(*bounds):
    return (
        min(item[0] for item in bounds),
        min(item[1] for item in bounds),
        max(item[2] for item in bounds),
        max(item[3] for item in bounds),
    )


def set_bounds(ax, bounds, padding=0.23):
    minimum_x, minimum_y, maximum_x, maximum_y = bounds
    width = max(maximum_x - minimum_x, 1.0)
    height = max(maximum_y - minimum_y, 1.0)
    pad = padding * max(width, height)
    ax.set_xlim(minimum_x - pad, maximum_x + pad)
    ax.set_ylim(minimum_y - pad, maximum_y + pad)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def resolved_fan_specs(count: int | None = None):
    count = int(C["FAN_COUNT"] if count is None else count)
    sizes = tuple(float(value) for value in C["FAN_SIZES_MM"][:count])
    total_width = sum(sizes) + float(C["FAN_BODY_GAP_MM"]) * (count - 1)
    cursor = -total_width / 2.0
    specs = []
    for index, size in enumerate(sizes):
        preset = STANDARD_FAN_PRESETS[int(size)]
        center_x = (
            float(C["STALK_LATERAL_DEFLECTION_X"])
            + cursor
            + size / 2.0
        )
        scale = size / float(C["FAN_REFERENCE_SIZE_MM"])
        cavity = size + 2.0 * float(C["FAN_BODY_CLEARANCE_PER_SIDE"])
        frame = cavity + 2.0 * float(C["FAN_FRAME_WALL"])
        hole_spacing = float(preset["hole_spacing"])
        hole_center_radius = math.sqrt(2.0) * hole_spacing / 2.0
        max_airflow_radius = (
            hole_center_radius
            - float(C["FAN_HOLE_COUNTERSINK_DIAMETER"]) / 2.0
            - float(C["AIRFLOW_TO_COUNTERSINK_MIN_WEB"])
        )
        airflow = min(
            float(C["AIRFLOW_DIAMETER_AT_REFERENCE"]) * scale,
            2.0 * max_airflow_radius,
        )
        specs.append(
            {
                "index": index,
                "size": size,
                "center_x": center_x,
                "frame": frame,
                "cavity": cavity,
                "airflow": airflow,
                "hole_spacing": hole_spacing,
                "hole_diameter": float(preset["hole_diameter"]),
                "scale": scale,
            }
        )
        cursor += size + float(C["FAN_BODY_GAP_MM"])
    return tuple(specs)


def configured_stalk_z_length() -> float:
    if not C["STALK_DROPPED_ROUTE_ENABLED"]:
        return float(C["STALK_LENGTH_Z"])
    angle = math.radians(float(C["STALK_ROUTE_TRANSITION_ANGLE_DEG"]))
    return (
        float(C["STALK_ROUTE_DROP_Y"]) / math.tan(angle)
        + float(C["STALK_ROUTE_BACK_Z"])
        + float(C["STALK_ROUTE_RETURN_RISE_Y"]) / math.tan(angle)
    )


def configured_stalk_path_length() -> float:
    if not C["STALK_DROPPED_ROUTE_ENABLED"]:
        return float(C["STALK_LENGTH_Z"])
    angle = math.radians(float(C["STALK_ROUTE_TRANSITION_ANGLE_DEG"]))
    return (
        float(C["STALK_ROUTE_DROP_Y"]) / math.sin(angle)
        + float(C["STALK_ROUTE_BACK_Z"])
        + float(C["STALK_ROUTE_RETURN_RISE_Y"]) / math.sin(angle)
    )


def stalk_lateral_width_scale() -> float:
    path_length = configured_stalk_path_length()
    return math.hypot(
        path_length,
        float(C["STALK_LATERAL_DEFLECTION_X"]),
    ) / path_length


def support_datums():
    specs = resolved_fan_specs()
    largest_frame = max(spec["frame"] for spec in specs)
    bottom_y = -largest_frame / 2.0 - float(C["SUPPORT_HUB_BELOW_FAN_Y"])
    top_y = bottom_y + float(C["SUPPORT_HUB_DEPTH_Y"])
    width = C["SUPPORT_HUB_WIDTH_OVERRIDE"]
    if width is None:
        width = float(C["SUPPORT_HUB_WIDTH_PER_FAN"]) * int(C["FAN_COUNT"])
    plane_z = float(C["FAN_FRAME_DEPTH"]) if C["FAN_GRILL_ON_BACK"] else 0.0
    stalk_length_z = configured_stalk_z_length()
    if C["FAN_GRILL_ON_BACK"]:
        support_z = (plane_z - float(C["SUPPORT_THICKNESS"]), plane_z)
        stalk_z = (plane_z - stalk_length_z, plane_z)
    else:
        support_z = (plane_z, plane_z + float(C["SUPPORT_THICKNESS"]))
        stalk_z = (-stalk_length_z, plane_z)
    stalk_y = bottom_y + float(C["STALK_DEPTH_Y"]) / 2.0 - float(C["STALK_BOTTOM_Y_OVERHANG"])
    return {
        "bottom_y": bottom_y,
        "top_y": top_y,
        "width": float(width),
        "plane_z": plane_z,
        "support_z0": support_z[0],
        "support_z1": support_z[1],
        "stalk_z0": stalk_z[0],
        "stalk_z1": stalk_z[1],
        "stalk_y": stalk_y,
        "fan_center_x": float(C["STALK_LATERAL_DEFLECTION_X"]),
        "mount_center_x": 0.0,
    }


def mount_datums(dropped: bool | None = None):
    datums = support_datums()
    if dropped is None:
        dropped = bool(C["STALK_DROPPED_ROUTE_ENABLED"])
    delta_y = 0.0
    if dropped:
        delta_y = float(C["STALK_ROUTE_DROP_Y"]) - float(C["STALK_ROUTE_RETURN_RISE_Y"])
    center_y = datums["stalk_y"] + delta_y
    top_z = datums["stalk_z0"] + float(C["MOUNT_BLOCK_OVERLAP"])
    center_z = top_z - float(C["MOUNT_BLOCK_HEIGHT_Z"]) / 2.0
    return {
        "center_y": center_y,
        "center_z": center_z,
        "top_z": top_z,
        "bottom_z": top_z - float(C["MOUNT_BLOCK_HEIGHT_Z"]),
        "front_y": center_y - float(C["MOUNT_BLOCK_DEPTH_Y"]) / 2.0,
        "back_y": center_y + float(C["MOUNT_BLOCK_DEPTH_Y"]) / 2.0,
    }


def adapter_datums(dropped: bool | None = None):
    mount = mount_datums(dropped)
    mating_y = (
        mount["center_y"]
        - float(C["MOUNT_BLOCK_DEPTH_Y"]) / 2.0
        - float(C["GOPRO_ADAPTER_MATING_GAP"])
    )
    plate_front_y = mating_y - float(C["GOPRO_ADAPTER_PLATE_DEPTH_Y"])
    plate_center_z = mount["center_z"] - float(C["GOPRO_ADAPTER_HOLE_Z_OFFSET"])
    pivot_y = mating_y - float(C["GOPRO_PIVOT_FROM_MATING_FACE_Y"])
    pivot_z = mount["center_z"] - float(C["GOPRO_PIVOT_BELOW_MOUNT_HOLES_Z"])
    return {
        **mount,
        "mating_y": mating_y,
        "plate_front_y": plate_front_y,
        "plate_center_z": plate_center_z,
        "plate_bottom_z": plate_center_z - float(C["GOPRO_ADAPTER_PLATE_HEIGHT_Z"]) / 2.0,
        "plate_top_z": plate_center_z + float(C["GOPRO_ADAPTER_PLATE_HEIGHT_Z"]) / 2.0,
        "pivot_y": pivot_y,
        "pivot_z": pivot_z,
    }


def configured_slot_specs(holder_bounds):
    active_specs = resolved_fan_specs()
    slots = []
    for index, size_value in enumerate(C["FAN_SIZES_MM"]):
        size = float(size_value)
        if index < len(active_specs):
            slots.append(
                {
                    "index": index,
                    "size": size,
                    "center_x": active_specs[index]["center_x"],
                    "center_y": 0.0,
                    "active": True,
                }
            )
        else:
            slots.append(
                {
                    "index": index,
                    "size": size,
                    "center_x": (holder_bounds[0] + holder_bounds[2]) / 2.0,
                    "center_y": holder_bounds[1] - 12.0 - size / 2.0,
                    "active": False,
                }
            )
    return tuple(slots)


def draw_fan_overlay(ax, spec, color=ORANGE, alpha=0.9):
    center_x = spec["center_x"]
    frame = spec["frame"]
    ax.add_patch(
        FancyBboxPatch(
            (center_x - frame / 2.0, -frame / 2.0),
            frame,
            frame,
            boxstyle=f"round,pad=0,rounding_size={float(C['FAN_FRAME_CORNER_RADIUS'])}",
            fill=False,
            edgecolor=color,
            linewidth=0.75,
            linestyle="--",
            alpha=alpha,
            zorder=6,
        )
    )
    ax.add_patch(
        Circle(
            (center_x, 0.0),
            spec["airflow"] / 2.0,
            fill=False,
            edgecolor=color,
            linewidth=0.7,
            zorder=6,
        )
    )
    disk = float(C["GRILL_CENTER_DISK_DIAMETER_AT_REFERENCE"]) * spec["scale"]
    ax.add_patch(Circle((center_x, 0.0), disk / 2.0, fill=False, edgecolor=GREEN, linewidth=0.6, zorder=7))
    half = spec["hole_spacing"] / 2.0
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            ax.add_patch(
                Circle(
                    (center_x + sx * half, sy * half),
                    spec["hole_diameter"] / 2.0,
                    fill=False,
                    edgecolor=RED,
                    linewidth=0.6,
                    zorder=7,
                )
            )


def draw_holder_front(ax, detail: str):
    geometry = projected_part_geometry("holder", "xy")
    draw_projected_geometry(ax, geometry, "#dceaf3", BLUE, alpha=0.84)
    for spec in resolved_fan_specs():
        draw_fan_overlay(ax, spec)
    bounds = geometry.bounds
    if detail == "array_front":
        for slot in configured_slot_specs(geometry.bounds):
            size = slot["size"]
            center_x = slot["center_x"]
            center_y = slot["center_y"]
            ax.add_patch(
                Rectangle(
                    (center_x - size / 2.0, center_y - size / 2.0),
                    size,
                    size,
                    fill=False,
                    edgecolor=GREEN if slot["active"] else PURPLE,
                    linewidth=0.85,
                    linestyle="--",
                    zorder=8,
                )
            )
            ax.text(
                center_x,
                center_y + size / 2.0 - 3.0,
                f"SLOT {slot['index'] + 1} — {'ACTIVE' if slot['active'] else 'INACTIVE'}",
                fontsize=4.8,
                color=GREEN if slot["active"] else PURPLE,
                ha="center",
                va="top",
                weight="bold",
                zorder=9,
            )
            slot_bounds = (
                center_x - size / 2.0,
                center_y - size / 2.0,
                center_x + size / 2.0,
                center_y + size / 2.0,
            )
            bounds = merged_bounds(bounds, slot_bounds)
    if detail == "mesh_detail":
        min_x, min_y, max_x, max_y = geometry.bounds
        for x, y in ((min_x + 0.18 * (max_x - min_x), max_y - 0.18 * (max_y - min_y)), (0.0, min_y + 0.2 * (max_y - min_y))):
            ax.add_patch(Circle((x, y), 0.07 * (max_x - min_x), fill=False, edgecolor=PURPLE, linewidth=1.0, linestyle=":"))
    return bounds


def draw_reference_fan(ax):
    """Draw the live 60 mm design datum used by every *_AT_REFERENCE value."""
    size = float(C["FAN_REFERENCE_SIZE_MM"])
    cavity = size + 2.0 * float(C["FAN_BODY_CLEARANCE_PER_SIDE"])
    frame = cavity + 2.0 * float(C["FAN_FRAME_WALL"])
    preset = STANDARD_FAN_PRESETS[int(size)]
    airflow = float(C["AIRFLOW_DIAMETER_AT_REFERENCE"])
    center_disk = float(C["GRILL_CENTER_DISK_DIAMETER_AT_REFERENCE"])
    corner = float(C["FAN_FRAME_CORNER_RADIUS"])
    ax.add_patch(
        FancyBboxPatch(
            (-frame / 2.0, -frame / 2.0),
            frame,
            frame,
            boxstyle=f"round,pad=0,rounding_size={corner}",
            facecolor="#dceaf3",
            edgecolor=BLUE,
            linewidth=1.1,
        )
    )
    ax.add_patch(Rectangle((-size / 2.0, -size / 2.0), size, size, fill=False, edgecolor=GREEN, linewidth=0.75, linestyle="--"))
    ax.add_patch(Circle((0.0, 0.0), airflow / 2.0, facecolor=WHITE, edgecolor=CYAN, linewidth=1.0))
    for radius in C["GRILL_RING_CENTER_RADII_AT_REFERENCE"]:
        ax.add_patch(Circle((0.0, 0.0), float(radius), fill=False, edgecolor=BLUE, linewidth=float(C["GRILL_RING_WIDTH"])))
    ax.add_patch(Circle((0.0, 0.0), center_disk / 2.0, facecolor=LIGHT, edgecolor=GREEN, linewidth=0.9))
    bar_width = float(C["GRILL_BAR_WIDTH"])
    ax.add_patch(Rectangle((-bar_width / 2.0, -airflow / 2.0), bar_width, airflow, facecolor="#dceaf3", edgecolor=BLUE, linewidth=0.5))
    ax.add_patch(Rectangle((-airflow / 2.0, -bar_width / 2.0), airflow, bar_width, facecolor="#dceaf3", edgecolor=BLUE, linewidth=0.5))
    half = float(preset["hole_spacing"]) / 2.0
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            ax.add_patch(Circle((sx * half, sy * half), float(C["FAN_HOLE_COUNTERSINK_DIAMETER"]) / 2.0, facecolor=WHITE, edgecolor=RED, linewidth=0.75))
    offset = float(C["FAN_WIRE_SLOT_OFFSET_AT_REFERENCE"])
    slot_width = float(C["FAN_WIRE_SLOT_WIDTH"])
    ax.add_patch(Rectangle((offset - slot_width / 2.0, -frame / 2.0), slot_width, float(C["FAN_FRAME_WALL"]), facecolor=WHITE, edgecolor=ORANGE, linewidth=0.8))
    pivot_x = float(C["FAN_ROTATION_PIVOT_INWARD_X_AT_REFERENCE"])
    pivot_y = -frame / 2.0 + float(C["FAN_ROTATION_PIVOT_ABOVE_BOTTOM_Y"])
    ax.add_patch(Circle((pivot_x, pivot_y), 1.1, facecolor=ORANGE, edgecolor=RED, linewidth=0.7, zorder=10))
    ax.text(0.0, frame / 2.0 + 2.2, "60 mm DESIGN DATUM", color=GREEN, fontsize=5.3, ha="center", weight="bold")
    return (-frame / 2.0, -frame / 2.0, frame / 2.0, frame / 2.0)


def draw_holder_side(ax, include_adapter=True):
    holder = projected_part_geometry("holder", "yz")
    draw_projected_geometry(ax, holder, "#dceaf3", BLUE, alpha=0.82)
    bounds = holder.bounds
    if include_adapter:
        adapter = projected_part_geometry("adapter", "yz")
        draw_projected_geometry(ax, adapter, "#f7d9ca", ORANGE, alpha=0.88, zorder=4)
        bounds = merged_bounds(bounds, adapter.bounds)
    size = max(float(value) for value in C["FAN_SIZES_MM"][: int(C["FAN_COUNT"])] )
    fan_depth = max(float(STANDARD_FAN_PRESETS[int(value)]["depth"]) for value in C["FAN_SIZES_MM"][: int(C["FAN_COUNT"])] )
    z0 = -fan_depth if C["FAN_GRILL_ON_BACK"] else 0.0
    ax.add_patch(
        Rectangle(
            (-size / 2.0, z0),
            size,
            fan_depth,
            fill=False,
            edgecolor=GREEN,
            linewidth=0.8,
            linestyle="--",
            zorder=7,
        )
    )
    return bounds


def dropped_route_points():
    datums = support_datums()
    stalk_y = datums["stalk_y"]
    drop = float(C["STALK_ROUTE_DROP_Y"])
    rise = float(C["STALK_ROUTE_RETURN_RISE_Y"])
    angle = math.radians(float(C["STALK_ROUTE_TRANSITION_ANGLE_DEG"]))
    drop_run = drop / math.tan(angle)
    rise_run = rise / math.tan(angle)
    length = drop_run + float(C["STALK_ROUTE_BACK_Z"]) + rise_run
    plane = datums["plane_z"]
    z0 = plane - length
    z1 = plane
    low_y = stalk_y - rise
    return (
        (stalk_y + drop - rise, z0),
        (low_y, z0 + drop_run),
        (low_y, z1 - rise_run),
        (stalk_y, z1),
    )


def configured_stalk_route_points():
    if C["STALK_DROPPED_ROUTE_ENABLED"]:
        return dropped_route_points()
    datums = support_datums()
    return (
        (datums["stalk_y"], datums["stalk_z0"]),
        (datums["stalk_y"], datums["stalk_z1"]),
    )


def stalk_route_distances(points):
    distances = [0.0]
    for start, end in zip(points, points[1:]):
        distances.append(
            distances[-1]
            + math.hypot(end[0] - start[0], end[1] - start[1])
        )
    return tuple(distances)


def stalk_route_point_at_distance(points, distances, distance):
    for index, (start, end) in enumerate(zip(points, points[1:])):
        segment_start = distances[index]
        segment_end = distances[index + 1]
        if distance <= segment_end + 1.0e-9:
            ratio = (distance - segment_start) / (segment_end - segment_start)
            return (
                start[0] + ratio * (end[0] - start[0]),
                start[1] + ratio * (end[1] - start[1]),
            )
    return points[-1]


def stalk_global_half_width_at_distance(distance, total_length):
    width_scale = stalk_lateral_width_scale()
    half_stalk_width = float(C["STALK_WIDTH"]) / 2.0
    flares_active = bool(C["STALK_END_FLARES_ENABLED"] or C["FAN_GRILL_ON_BACK"])
    if not flares_active:
        return half_stalk_width * width_scale

    mount_flare = float(C["STALK_MOUNT_FLARE_LENGTH_Z"])
    hub_flare = float(C["STALK_HUB_FLARE_LENGTH_Z"])
    if distance < mount_flare:
        t = distance / mount_flare
        mount_normal_half_width = (
            float(C["MOUNT_BLOCK_WIDTH"]) / (2.0 * width_scale)
        )
        return (
            mount_normal_half_width
            + (half_stalk_width - mount_normal_half_width) * t
        ) * width_scale
    if distance > total_length - hub_flare:
        t = (distance - (total_length - hub_flare)) / hub_flare
        hub_normal_half_width = (
            float(C["STALK_HUB_FLARE_WIDTH"]) / (2.0 * width_scale)
        )
        return (
            half_stalk_width
            + (hub_normal_half_width - half_stalk_width) * t
        ) * width_scale
    return half_stalk_width * width_scale


def stalk_front_sections():
    points = configured_stalk_route_points()
    distances = stalk_route_distances(points)
    total_length = distances[-1]
    section_distances = [0.0, *distances[1:-1], total_length]
    if C["STALK_END_FLARES_ENABLED"] or C["FAN_GRILL_ON_BACK"]:
        mount_flare_end = float(C["STALK_MOUNT_FLARE_LENGTH_Z"])
        hub_flare_start = total_length - float(C["STALK_HUB_FLARE_LENGTH_Z"])
        if len(distances) == 2 or mount_flare_end >= distances[1]:
            section_distances.append(mount_flare_end)
        if len(distances) == 2 or hub_flare_start <= distances[-2]:
            section_distances.append(hub_flare_start)
    section_distances = sorted(set(section_distances))
    deflection = float(C["STALK_LATERAL_DEFLECTION_X"])
    sections = []
    for distance in section_distances:
        _y, z = stalk_route_point_at_distance(
            points,
            distances,
            distance,
        )
        sections.append(
            (
                distance,
                deflection * distance / total_length,
                z,
                stalk_global_half_width_at_distance(distance, total_length),
            )
        )
    return tuple(sections), points, distances


def routed_stalk_outline(points):
    half_depth = float(C["STALK_DEPTH_Y"]) / 2.0
    offsets = []
    for index, point in enumerate(points):
        if index in {0, len(points) - 1}:
            offsets.append((half_depth, 0.0))
            continue
        before_y = point[0] - points[index - 1][0]
        before_z = point[1] - points[index - 1][1]
        after_y = points[index + 1][0] - point[0]
        after_z = points[index + 1][1] - point[1]
        before_length = math.hypot(before_y, before_z)
        after_length = math.hypot(after_y, after_z)
        before_normal = (before_z / before_length, -before_y / before_length)
        after_normal = (after_z / after_length, -after_y / after_length)
        miter_y = before_normal[0] + after_normal[0]
        miter_z = before_normal[1] + after_normal[1]
        miter_length = math.hypot(miter_y, miter_z)
        miter_y /= miter_length
        miter_z /= miter_length
        projection = miter_y * before_normal[0] + miter_z * before_normal[1]
        scale = half_depth / projection
        offsets.append((miter_y * scale, miter_z * scale))
    negative = [(point[0] - offset[0], point[1] - offset[1]) for point, offset in zip(points, offsets)]
    positive = [(point[0] + offset[0], point[1] + offset[1]) for point, offset in zip(points, offsets)]
    return tuple(negative + list(reversed(positive)))


def draw_stalk_routes(ax):
    holder = projected_part_geometry("holder", "yz")
    draw_projected_geometry(ax, holder, LIGHT, GRAY, alpha=0.35)
    bounds = holder.bounds
    size = max(float(value) for value in C["FAN_SIZES_MM"][: int(C["FAN_COUNT"])])
    fan_depth = max(float(STANDARD_FAN_PRESETS[int(value)]["depth"]) for value in C["FAN_SIZES_MM"][: int(C["FAN_COUNT"])])
    z0 = -fan_depth if C["FAN_GRILL_ON_BACK"] else 0.0
    ax.add_patch(Rectangle((-size / 2.0, z0), size, fan_depth, fill=False, edgecolor=GREEN, linewidth=0.8, linestyle="--", zorder=3))
    points = dropped_route_points()
    outline = routed_stalk_outline(points)
    ax.add_patch(Polygon(outline, closed=True, facecolor="#d9cfea", edgecolor=PURPLE, linewidth=1.2, alpha=0.88, zorder=8))
    ax.plot(
        [point[0] for point in points],
        [point[1] for point in points],
        color=WHITE,
        linewidth=0.8,
        linestyle="--",
        zorder=9,
    )
    dropped_mount = mount_datums(dropped=True)
    ax.add_patch(
        Rectangle(
            (dropped_mount["front_y"], dropped_mount["bottom_z"]),
            float(C["MOUNT_BLOCK_DEPTH_Y"]),
            float(C["MOUNT_BLOCK_HEIGHT_Z"]),
            facecolor="#f7d9ca",
            edgecolor=ORANGE,
            linewidth=1.1,
            zorder=10,
        )
    )
    adapter = projected_part_geometry("adapter", "yz")
    y_shift = float(C["STALK_ROUTE_DROP_Y"]) - float(C["STALK_ROUTE_RETURN_RISE_Y"])
    translated_adapter = affinity.translate(adapter, xoff=y_shift, yoff=0.0)
    draw_projected_geometry(ax, translated_adapter, "#f7d9ca", ORANGE, alpha=0.9, zorder=11)
    ax.text(points[1][0], points[1][1], "FULL-SCALE LOWERED ROUTE", color=PURPLE, fontsize=5.8, weight="bold", ha="right")
    ax.text(holder.bounds[0], holder.bounds[3], "GRAY = STRAIGHT-ROUTE REFERENCE", color=GRAY, fontsize=4.8, ha="left", va="bottom")
    route_bounds = (
        min(point[0] for point in outline),
        min(point[1] for point in outline),
        max(point[0] for point in outline),
        max(point[1] for point in outline),
    )
    return merged_bounds(bounds, route_bounds, translated_adapter.bounds)


def splitter_opening(spec) -> float:
    hole_radius = (spec["hole_diameter"] + float(C["SINGLE_FAN_SPLITTER_HOLE_CLEARANCE"])) / 2.0
    hole_center_radius = math.sqrt(2.0) * spec["hole_spacing"] / 2.0
    hole_limited = 2.0 * (hole_center_radius - hole_radius - float(C["SINGLE_FAN_SPLITTER_EDGE_WEB"]))
    edge_limited = spec["size"] - 2.0 * float(C["SINGLE_FAN_SPLITTER_EDGE_WEB"])
    return min(hole_limited, edge_limited)


def draw_splitter_front(ax):
    spec = resolved_fan_specs(1)[0]
    size = spec["size"]
    opening = splitter_opening(spec)
    ax.add_patch(
        FancyBboxPatch(
            (-size / 2.0, -size / 2.0),
            size,
            size,
            boxstyle=f"round,pad=0,rounding_size={min(float(C['FAN_FRAME_CORNER_RADIUS']), size / 10.0)}",
            facecolor="#e6e0f2",
            edgecolor=PURPLE,
            linewidth=1.1,
        )
    )
    ax.add_patch(Circle((0.0, 0.0), opening / 2.0, facecolor=WHITE, edgecolor=BLUE, linewidth=1.0, zorder=3))
    half = spec["hole_spacing"] / 2.0
    hole_radius = (spec["hole_diameter"] + float(C["SINGLE_FAN_SPLITTER_HOLE_CLEARANCE"])) / 2.0
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            ax.add_patch(Circle((sx * half, sy * half), hole_radius, facecolor=WHITE, edgecolor=RED, linewidth=0.8, zorder=5))
    lead = float(C["SINGLE_FAN_SPLITTER_LEADING_EDGE_WIDTH"])
    ax.add_patch(Rectangle((-lead / 2.0, -opening / 2.0), lead, opening, facecolor=ORANGE, edgecolor=RED, alpha=0.9, zorder=6))
    ax.annotate("AIRFLOW LEFT", (-opening * 0.38, 0.0), (0.0, -opening * 0.2), arrowprops={"arrowstyle": "->", "color": GREEN}, color=GREEN, fontsize=5.3)
    ax.annotate("AIRFLOW RIGHT", (opening * 0.38, 0.0), (0.0, opening * 0.2), arrowprops={"arrowstyle": "->", "color": GREEN}, color=GREEN, fontsize=5.3)
    return (-size / 2.0, -size / 2.0, size / 2.0, size / 2.0)


def draw_splitter_side(ax):
    spec = resolved_fan_specs(1)[0]
    size = spec["size"]
    plate = float(C["SINGLE_FAN_SPLITTER_PLATE_THICKNESS"])
    length = float(C["SINGLE_FAN_SPLITTER_VANE_LENGTH_Z"])
    lead = float(C["SINGLE_FAN_SPLITTER_LEADING_EDGE_WIDTH"]) / 2.0
    downstream = lead + length * math.tan(math.radians(float(C["SINGLE_FAN_SPLITTER_OUTLET_ANGLE_DEG"])))
    thickness = float(C["SINGLE_FAN_SPLITTER_VANE_THICKNESS"])
    ax.add_patch(Rectangle((-size / 2.0, -plate), size, plate, facecolor="#e6e0f2", edgecolor=PURPLE, linewidth=1.0))
    left = [(-lead, -plate), (-downstream, -plate - length), (-downstream + thickness, -plate - length), (0.0, -plate)]
    right = [(0.0, -plate), (downstream - thickness, -plate - length), (downstream, -plate - length), (lead, -plate)]
    for points in (left, right):
        ax.add_patch(Polygon(points, closed=True, facecolor="#f7d9ca", edgecolor=RED, linewidth=1.0))
    ax.annotate("TO CAMERAS", (0.0, -plate - length), (0.0, -plate - length * 0.55), arrowprops={"arrowstyle": "->", "color": GREEN}, color=GREEN, fontsize=5.5, ha="center")
    return (-size / 2.0, -plate - length, size / 2.0, 0.0)


def draw_splitter_clearance(ax):
    """YZ section through the optional plate notch and dropped holder."""
    points = dropped_route_points()
    outline = routed_stalk_outline(points)
    ax.add_patch(Polygon(outline, closed=True, facecolor="#d9cfea", edgecolor=PURPLE, linewidth=1.0, alpha=0.8, zorder=5))
    mount = mount_datums(dropped=True)
    ax.add_patch(
        Rectangle(
            (mount["front_y"], mount["bottom_z"]),
            float(C["MOUNT_BLOCK_DEPTH_Y"]),
            float(C["MOUNT_BLOCK_HEIGHT_Z"]),
            facecolor="#f7d9ca",
            edgecolor=ORANGE,
            linewidth=1.0,
            zorder=6,
        )
    )
    highest_holder_y = (
        mount["center_y"]
        + max(float(C["STALK_DEPTH_Y"]), float(C["MOUNT_BLOCK_DEPTH_Y"])) / 2.0
    )
    notch_y = highest_holder_y + float(C["SINGLE_FAN_SPLITTER_HOLDER_CLEARANCE"])
    spec = resolved_fan_specs(1)[0]
    fan_depth = float(STANDARD_FAN_PRESETS[int(spec["size"])]["depth"])
    if C["FAN_GRILL_ON_BACK"]:
        mount_face_z = float(C["FAN_FRAME_DEPTH"]) - float(C["GRILL_THICKNESS"])
        if C["FAN_HOLE_COLLARS_ENABLED"]:
            mount_face_z -= float(C["FAN_HOLE_COLLAR_HEIGHT"])
        mount_face_z -= fan_depth
    else:
        mount_face_z = 0.0
    plate_z0 = mount_face_z - float(C["SINGLE_FAN_SPLITTER_PLATE_THICKNESS"])
    vane_z = plate_z0 + float(C["BOOLEAN_OVERLAP"]) - float(C["SINGLE_FAN_SPLITTER_VANE_LENGTH_Z"])
    half_size = spec["size"] / 2.0
    opening_radius = splitter_opening(spec) / 2.0
    # The four-hole plate remains complete; only the downstream vane envelope
    # below the holder-clearance datum is removed.
    ax.add_patch(Rectangle((-half_size, plate_z0), 2.0 * half_size, mount_face_z - plate_z0, facecolor="#e6e0f2", edgecolor=PURPLE, linewidth=1.0, zorder=8))
    ax.add_patch(Rectangle((notch_y, vane_z), opening_radius - notch_y, plate_z0 - vane_z, facecolor="#f7d9ca", edgecolor=RED, linewidth=0.8, zorder=7))
    ax.add_patch(Rectangle((-opening_radius, vane_z), notch_y + opening_radius, plate_z0 - vane_z, fill=False, edgecolor=GRAY, linewidth=0.7, linestyle=":", zorder=6))
    ax.text(
        (-opening_radius + notch_y) / 2.0 - 2.0,
        (vane_z + plate_z0) / 2.0,
        "NOTCH REMOVES\nTHIS ENVELOPE",
        fontsize=4.4,
        color=GRAY,
        ha="center",
        va="center",
        bbox={"boxstyle": "round,pad=0.14", "facecolor": WHITE, "edgecolor": GRAY, "linewidth": 0.45},
        zorder=35,
    )
    ax.plot((highest_holder_y, highest_holder_y), (vane_z, mount_face_z), color=ORANGE, linewidth=0.8, linestyle=":", zorder=10)
    ax.plot((notch_y, notch_y), (vane_z, mount_face_z), color=GREEN, linewidth=0.9, linestyle="--", zorder=10)
    reference_z = (vane_z + plate_z0) / 2.0
    ax.annotate(
        "HIGHEST HOLDER SURFACE",
        (highest_holder_y, reference_z),
        (highest_holder_y - 12.0, mount_face_z + 4.0),
        fontsize=4.8,
        color=ORANGE,
        ha="right",
        bbox={"boxstyle": "round,pad=0.15", "facecolor": WHITE, "edgecolor": ORANGE, "linewidth": 0.5},
        arrowprops={
            "arrowstyle": "->",
            "color": ORANGE,
            "linewidth": 0.65,
            # Follow the envelope edge instead of crossing its context label.
            "connectionstyle": "angle3,angleA=0,angleB=90",
        },
    )
    ax.annotate("SPLITTER NOTCH EDGE", (notch_y, reference_z), (notch_y + 12.0, vane_z - 4.0), fontsize=4.8, color=GREEN, ha="left", bbox={"boxstyle": "round,pad=0.15", "facecolor": WHITE, "edgecolor": GREEN, "linewidth": 0.5}, arrowprops={"arrowstyle": "->", "color": GREEN, "linewidth": 0.65})
    bounds = (
        min(-half_size, -opening_radius, min(point[0] for point in outline), mount["front_y"]),
        min(min(point[1] for point in outline), mount["bottom_z"], vane_z),
        max(half_size, opening_radius, max(point[0] for point in outline), mount["back_y"]),
        max(max(point[1] for point in outline), mount["top_z"], mount_face_z),
    )
    return bounds


def draw_adapter_view(ax, plane):
    geometry = projected_part_geometry("adapter", plane)
    draw_projected_geometry(ax, geometry, "#f7d9ca", ORANGE, alpha=0.9)
    if plane == "yz":
        pivot_y = -float(C["GOPRO_PIVOT_FROM_MATING_FACE_Y"])
        ax.add_patch(Circle((pivot_y, geometry.centroid.y), float(C["GOPRO_PIVOT_HOLE_DIAMETER"]) / 2.0, facecolor=WHITE, edgecolor=RED, linewidth=0.8, zorder=6))
    return geometry.bounds


def draw_standard_fan(ax, size: int):
    preset = STANDARD_FAN_PRESETS[size]
    frame = float(preset["frame"])
    radius = min(4.0, frame / 12.0)
    ax.add_patch(FancyBboxPatch((-frame / 2.0, -frame / 2.0), frame, frame, boxstyle=f"round,pad=0,rounding_size={radius}", facecolor="#dceaf3", edgecolor=BLUE, linewidth=1.1))
    ax.add_patch(Circle((0.0, 0.0), float(preset["opening"]) / 2.0, facecolor=WHITE, edgecolor=CYAN, linewidth=1.0))
    ax.add_patch(Circle((0.0, 0.0), float(preset["hub"]) / 2.0, facecolor=LIGHT, edgecolor=GREEN, linewidth=0.9))
    half = float(preset["hole_spacing"]) / 2.0
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            ax.add_patch(Circle((sx * half, sy * half), float(preset["hole_diameter"]) / 2.0, facecolor=WHITE, edgecolor=RED, linewidth=0.8))
    ax.text(0.0, 0.0, preset["reference"], fontsize=5.5, color=GREEN, ha="center", va="center", weight="bold")
    ax.text(frame / 2.0, -frame / 2.0, f"DEPTH {fmt(preset['depth'])} mm", fontsize=5.3, color=ORANGE, ha="right", va="top")
    return (-frame / 2.0, -frame / 2.0, frame / 2.0, frame / 2.0)


def draw_standard_fan_side(ax, size: int):
    preset = STANDARD_FAN_PRESETS[size]
    frame = float(preset["frame"])
    depth = float(preset["depth"])
    ax.add_patch(
        Rectangle(
            (0.0, -frame / 2.0),
            depth,
            frame,
            facecolor="#dceaf3",
            edgecolor=BLUE,
            linewidth=1.1,
        )
    )
    ax.add_patch(
        Rectangle(
            (depth * 0.12, -frame * 0.42),
            depth * 0.76,
            frame * 0.84,
            fill=False,
            edgecolor=CYAN,
            linewidth=0.8,
            linestyle="--",
        )
    )
    ax.text(
        depth / 2.0,
        0.0,
        preset["reference"],
        fontsize=5.5,
        color=GREEN,
        ha="center",
        va="center",
        rotation=90,
        weight="bold",
    )
    return (0.0, -frame / 2.0, depth, frame / 2.0)


def draw_actual_view(ax, view: str):
    if view.startswith("preset_"):
        suffix = view.split("_", 1)[1]
        side_view = suffix.endswith("_side")
        size = int(suffix.removesuffix("_side"))
        bounds = draw_standard_fan_side(ax, size) if side_view else draw_standard_fan(ax, size)
        return bounds, "PARAMETRIC MANUFACTURER REFERENCE"
    if view == "fan_reference":
        return draw_reference_fan(ax), "PARAMETRIC 60 MM DESIGN DATUM"
    if view in {"array_front", "assembly_front", "fan_front", "support_front", "mesh_detail"}:
        return draw_holder_front(ax, view), "ACTUAL STL ORTHOGRAPHIC PROJECTION"
    if view in {"assembly_side", "fan_side"}:
        return draw_holder_side(ax), "ACTUAL STL ORTHOGRAPHIC PROJECTION"
    if view in {"support_side", "mount_side"}:
        return draw_holder_side(ax, include_adapter=False), "ACTUAL STL ORTHOGRAPHIC PROJECTION"
    if view == "stalk_front":
        geometry = projected_part_geometry("holder", "xz")
        draw_projected_geometry(ax, geometry, "#dceaf3", BLUE, alpha=0.84)
        return geometry.bounds, "ACTUAL STL ORTHOGRAPHIC PROJECTION"
    if view == "stalk_side":
        return draw_stalk_routes(ax), "ACTUAL STL + PARAMETRIC LOWERED-ROUTE OVERLAY"
    if view == "mount_detail":
        geometry = projected_part_geometry("holder", "xz")
        draw_projected_geometry(ax, geometry, "#dceaf3", BLUE, alpha=0.84)
        return geometry.bounds, "ACTUAL STL ORTHOGRAPHIC PROJECTION"
    if view == "adapter_front":
        return draw_adapter_view(ax, "xz"), "ACTUAL STL ORTHOGRAPHIC PROJECTION"
    if view == "adapter_side":
        return draw_adapter_view(ax, "yz"), "ACTUAL STL ORTHOGRAPHIC PROJECTION"
    if view == "splitter_front":
        return draw_splitter_front(ax), "PARAMETRIC PRINTED-PART GEOMETRY"
    if view == "splitter_side":
        return draw_splitter_side(ax), "PARAMETRIC PRINTED-PART GEOMETRY"
    if view == "splitter_clearance":
        return draw_splitter_clearance(ax), "PARAMETRIC HOLDER / SPLITTER SIDE SECTION"
    raise ValueError(f"Unknown drawing view: {view}")


def new_page(page_number: int, title: str, subtitle: str):
    fig = plt.figure(figsize=(11.0, 8.5))
    fig.add_artist(Rectangle((0.03, 0.035), 0.94, 0.93, transform=fig.transFigure, fill=False, edgecolor=INK, linewidth=0.8))
    fig.text(0.055, 0.936, title, fontsize=15.0, weight="bold", color=INK, va="top")
    fig.text(0.055, 0.905, subtitle, fontsize=7.0, color=GRAY, va="top")
    fig.add_artist(plt.Line2D((0.05, 0.95), (0.885, 0.885), transform=fig.transFigure, color=GRID, linewidth=0.8))
    fig.text(0.055, 0.052, f"GOPRO DUAL-FAN CONFIGURATION DIMENSION GUIDE • source-{SOURCE_HASH}", fontsize=6.2, color=GRAY)
    fig.text(0.945, 0.052, f"SHEET {page_number} / {TOTAL_PAGES}", fontsize=6.2, color=GRAY, ha="right")
    return fig


def panel(fig, rect, title: str):
    fig.add_artist(FancyBboxPatch((rect[0], rect[1]), rect[2], rect[3], transform=fig.transFigure, boxstyle="round,pad=0.008,rounding_size=0.008", facecolor=LIGHT, edgecolor=GRID, linewidth=0.8, zorder=-10))
    fig.text(rect[0] + 0.012, rect[1] + rect[3] - 0.018, title, fontsize=6.4, weight="bold", color=BLUE, va="top")


def draw_preset_annotation(ax, entry, index, bounds, color) -> bool:
    match = re.fullmatch(r"STANDARD_FAN_PRESETS\[(\d+)\]\.([A-Z_]+)", entry.identity)
    if match is None:
        return False
    size = int(match.group(1))
    key = match.group(2).lower()
    preset = STANDARD_FAN_PRESETS[size]
    minimum_x, minimum_y, maximum_x, maximum_y = bounds
    width = maximum_x - minimum_x
    height = maximum_y - minimum_y
    label = f"D{index + 1}  {entry.identity} = {dimension_value(entry)}"
    if key == "depth":
        y = minimum_y - (0.10 + 0.08 * index) * height
        start = (0.0, y)
        end = (float(preset["depth"]), y)
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="<->", mutation_scale=8, color=color, linewidth=0.9, zorder=20))
        ax.plot((start[0], start[0]), (minimum_y, y), color=color, linewidth=0.55)
        ax.plot((end[0], end[0]), (minimum_y, y), color=color, linewidth=0.55)
        ax.text((start[0] + end[0]) / 2.0, y, label, fontsize=4.8, color=color, weight="bold", ha="center", va="bottom", bbox={"boxstyle": "round,pad=0.16", "facecolor": WHITE, "edgecolor": color, "linewidth": 0.5}, zorder=30)
        return True
    if key in {"frame", "hole_spacing"}:
        span = float(preset[key])
        y = minimum_y - (0.10 + 0.08 * index) * height
        start = (-span / 2.0, y)
        end = (span / 2.0, y)
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="<->", mutation_scale=8, color=color, linewidth=0.9, zorder=20))
        ax.plot((start[0], start[0]), (minimum_y, y), color=color, linewidth=0.55)
        ax.plot((end[0], end[0]), (minimum_y, y), color=color, linewidth=0.55)
        ax.text(0.0, y, label, fontsize=4.8, color=color, weight="bold", ha="center", va="bottom", bbox={"boxstyle": "round,pad=0.16", "facecolor": WHITE, "edgecolor": color, "linewidth": 0.5}, zorder=30)
        return True
    if key == "hole_diameter":
        half = float(preset["hole_spacing"]) / 2.0
        center = (half, half)
        radius = float(preset[key]) / 2.0
    elif key in {"opening", "hub"}:
        center = (0.0, 0.0)
        radius = float(preset[key]) / 2.0
    else:
        return False
    ax.add_patch(Circle(center, radius, fill=False, edgecolor=color, linewidth=1.0, zorder=20))
    ax.add_patch(FancyArrowPatch(center, (center[0] + radius, center[1]), arrowstyle="<->", mutation_scale=7, color=color, linewidth=0.8, zorder=21))
    ax.text(minimum_x + 0.5 * width, maximum_y + (0.10 + 0.08 * index) * height, label, fontsize=4.8, color=color, weight="bold", ha="center", va="center", bbox={"boxstyle": "round,pad=0.18", "facecolor": WHITE, "edgecolor": color, "linewidth": 0.55}, zorder=30)
    return True


def annotation_label(entry: DimensionEntry, index: int) -> str:
    return f"D{index + 1}  {entry.identity} = {dimension_value(entry)}"


def reserve_dimension_rail(ax, orientation: str, proposed: float, witness: float) -> float:
    """Stagger callout rails so later labels cannot obscure earlier ones."""
    bounds = getattr(ax, "_engineering_bounds")
    span = max(bounds[2] - bounds[0], bounds[3] - bounds[1], 1.0)
    spacing = 0.055 * span
    attribute = f"_used_{orientation}_rails"
    used = getattr(ax, attribute)
    direction = 1.0 if proposed > witness else -1.0
    candidate = proposed
    while any(abs(candidate - previous) < 0.82 * spacing for previous in used):
        candidate += direction * spacing
    used.append(candidate)
    return candidate


def horizontal_dimension(ax, x0, x1, witness_y, line_y, label, color):
    line_y = reserve_dimension_rail(ax, "horizontal", line_y, witness_y)
    if math.isclose(x0, x1, abs_tol=1.0e-9):
        ax.plot((x0, x0), (witness_y - 1.5, witness_y + 1.5), color=color, linewidth=1.0, zorder=21)
        ax.annotate(
            label + "  (COINCIDENT DATUMS)",
            (x0, witness_y),
            (x0, line_y),
            fontsize=4.7,
            color=color,
            weight="bold",
            ha="center",
            bbox={"boxstyle": "round,pad=0.18", "facecolor": WHITE, "edgecolor": color, "linewidth": 0.55},
            arrowprops={"arrowstyle": "->", "color": color, "linewidth": 0.7},
            zorder=30,
        )
        return
    ax.add_patch(FancyArrowPatch((x0, line_y), (x1, line_y), arrowstyle="<->", mutation_scale=8, color=color, linewidth=0.9, zorder=20))
    ax.plot((x0, x0), (witness_y, line_y), color=color, linewidth=0.55)
    ax.plot((x1, x1), (witness_y, line_y), color=color, linewidth=0.55)
    ax.text((x0 + x1) / 2.0, line_y, label, fontsize=4.7, color=color, weight="bold", ha="center", va="bottom", bbox={"boxstyle": "round,pad=0.16", "facecolor": WHITE, "edgecolor": color, "linewidth": 0.5}, zorder=30)


def vertical_dimension(ax, y0, y1, witness_x, line_x, label, color):
    line_x = reserve_dimension_rail(ax, "vertical", line_x, witness_x)
    if math.isclose(y0, y1, abs_tol=1.0e-9):
        ax.plot((witness_x - 1.5, witness_x + 1.5), (y0, y0), color=color, linewidth=1.0, zorder=21)
        ax.annotate(
            label + "  (COINCIDENT DATUMS)",
            (witness_x, y0),
            (line_x, y0),
            fontsize=4.7,
            color=color,
            weight="bold",
            ha="center",
            bbox={"boxstyle": "round,pad=0.18", "facecolor": WHITE, "edgecolor": color, "linewidth": 0.55},
            arrowprops={"arrowstyle": "->", "color": color, "linewidth": 0.7},
            zorder=30,
        )
        return
    ax.add_patch(FancyArrowPatch((line_x, y0), (line_x, y1), arrowstyle="<->", mutation_scale=8, color=color, linewidth=0.9, zorder=20))
    ax.plot((witness_x, line_x), (y0, y0), color=color, linewidth=0.55)
    ax.plot((witness_x, line_x), (y1, y1), color=color, linewidth=0.55)
    ax.text(line_x, (y0 + y1) / 2.0, label, fontsize=4.7, color=color, weight="bold", rotation=90, ha="center", va="center", bbox={"boxstyle": "round,pad=0.16", "facecolor": WHITE, "edgecolor": color, "linewidth": 0.5}, zorder=30)


def radial_dimension(ax, center, radius, label, color, *, text_angle=90.0):
    ax.add_patch(Circle(center, radius, fill=False, edgecolor=color, linewidth=1.0, zorder=20))
    angle = math.radians(text_angle)
    end = (center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle))
    ax.add_patch(FancyArrowPatch(center, end, arrowstyle="<->", mutation_scale=7, color=color, linewidth=0.8, zorder=21))
    text_distance = 0.45 * max(radius, 4.0)
    text_position = (
        end[0] + text_distance * math.cos(angle),
        end[1] + text_distance * math.sin(angle),
    )
    ax.annotate(
        label,
        end,
        text_position,
        fontsize=4.7,
        color=color,
        weight="bold",
        ha="left" if math.cos(angle) >= 0.0 else "right",
        va="bottom" if math.sin(angle) >= 0.0 else "top",
        bbox={"boxstyle": "round,pad=0.18", "facecolor": WHITE, "edgecolor": color, "linewidth": 0.55},
        arrowprops={"arrowstyle": "->", "color": color, "linewidth": 0.65},
        zorder=30,
    )


def detail_dimension(ax, anchor, text_position, label, color, note="DETAIL NTS"):
    # Detail leaders share the horizontal callout lanes with linear
    # dimensions. Reserving that lane prevents long boxed identifiers from
    # being drawn on top of one another even when their anchors differ.
    text_position = (
        text_position[0],
        reserve_dimension_rail(ax, "horizontal", text_position[1], anchor[1]),
    )
    ax.add_patch(Circle(anchor, 1.2, fill=False, edgecolor=color, linestyle=":", linewidth=1.0, zorder=20))
    ax.annotate(
        f"{label}  ({note})",
        anchor,
        text_position,
        fontsize=4.7,
        color=color,
        weight="bold",
        ha="center",
        bbox={"boxstyle": "round,pad=0.18", "facecolor": WHITE, "edgecolor": color, "linewidth": 0.55},
        arrowprops={"arrowstyle": "->", "color": color, "linewidth": 0.75},
        zorder=30,
    )


def angle_dimension(ax, center, radius, angle_deg, baseline_deg, label, color):
    theta1 = baseline_deg
    theta2 = baseline_deg + angle_deg
    if math.isclose(angle_deg, 0.0, abs_tol=1.0e-9):
        theta1 -= 2.0
        theta2 += 2.0
    ax.add_patch(Arc(center, 2.0 * radius, 2.0 * radius, theta1=min(theta1, theta2), theta2=max(theta1, theta2), color=color, linewidth=1.1, zorder=20))
    for theta in (baseline_deg, baseline_deg + angle_deg):
        radians = math.radians(theta)
        ax.plot((center[0], center[0] + radius * math.cos(radians)), (center[1], center[1] + radius * math.sin(radians)), color=color, linewidth=0.7, zorder=20)
    text_theta = math.radians(baseline_deg + angle_deg / 2.0)
    text_position = (center[0] + radius * 1.55 * math.cos(text_theta), center[1] + radius * 1.55 * math.sin(text_theta))
    ax.text(text_position[0], text_position[1], label, fontsize=4.7, color=color, weight="bold", ha="center", va="center", bbox={"boxstyle": "round,pad=0.18", "facecolor": WHITE, "edgecolor": color, "linewidth": 0.55}, zorder=30)


def draw_array_annotation(ax, entry, index, bounds, color):
    name = entry.identity
    holder_bounds = projected_part_geometry("holder", "xy").bounds
    slots = configured_slot_specs(holder_bounds)
    size_match = re.fullmatch(r"FAN_SIZES_MM\[(\d+)\]", name)
    if size_match:
        slot = slots[int(size_match.group(1))]
        half = slot["size"] / 2.0
        line_y = slot["center_y"] - half - 4.0 - 2.5 * index
        horizontal_dimension(ax, slot["center_x"] - half, slot["center_x"] + half, slot["center_y"] - half, line_y, annotation_label(entry, index), color)
        return True
    rotation_match = re.fullmatch(r"FAN_ROTATIONS_DEG\[(\d+)\]\.([XYZ])", name)
    if rotation_match:
        slot = slots[int(rotation_match.group(1))]
        axis = rotation_match.group(2)
        baseline = {"X": 15.0, "Y": 135.0, "Z": 255.0}[axis]
        radius = slot["size"] * (0.16 + 0.045 * index)
        angle_dimension(ax, (slot["center_x"], slot["center_y"]), radius, float(entry.value), baseline, annotation_label(entry, index), color)
        ax.text(slot["center_x"], slot["center_y"], f"{axis}-AXIS", fontsize=4.5, color=color, ha="center", va="center", weight="bold")
        return True
    if name == "FAN_BODY_GAP_MM":
        specs = resolved_fan_specs()
        left_edge = specs[0]["center_x"] + specs[0]["size"] / 2.0
        right_edge = specs[1]["center_x"] - specs[1]["size"] / 2.0
        y = min(-specs[0]["size"] / 2.0, -specs[1]["size"] / 2.0)
        horizontal_dimension(ax, left_edge, right_edge, y, y - 7.0, annotation_label(entry, index), color)
        return True
    return False


def draw_fan_reference_annotation(ax, entry, index, bounds, color):
    name = entry.identity
    size = float(C["FAN_REFERENCE_SIZE_MM"])
    frame = size + 2.0 * float(C["FAN_BODY_CLEARANCE_PER_SIDE"]) + 2.0 * float(C["FAN_FRAME_WALL"])
    label = annotation_label(entry, index)
    if name == "FAN_REFERENCE_SIZE_MM":
        horizontal_dimension(ax, -size / 2.0, size / 2.0, -size / 2.0, -frame / 2.0 - 5.0, label, color)
        return True
    if name == "FAN_ROTATION_PIVOT_INWARD_X_AT_REFERENCE":
        x0 = 0.0
        x1 = float(entry.value)
        y = -frame / 2.0 + float(C["FAN_ROTATION_PIVOT_ABOVE_BOTTOM_Y"])
        horizontal_dimension(ax, x0, x1, y, -frame / 2.0 - 5.0, label, color)
        return True
    if name == "FAN_ROTATION_PIVOT_ABOVE_BOTTOM_Y":
        y0 = -frame / 2.0
        y1 = y0 + float(entry.value)
        x = float(C["FAN_ROTATION_PIVOT_INWARD_X_AT_REFERENCE"])
        vertical_dimension(ax, y0, y1, x, -frame / 2.0 - 6.0, label, color)
        return True
    if name == "FAN_WIRE_SLOT_OFFSET_AT_REFERENCE":
        horizontal_dimension(ax, 0.0, float(entry.value), -frame / 2.0, -frame / 2.0 - 5.0, label, color)
        return True
    if name == "AIRFLOW_DIAMETER_AT_REFERENCE":
        radial_dimension(ax, (0.0, 0.0), float(entry.value) / 2.0, label, color, text_angle=18.0)
        return True
    if name == "GRILL_CENTER_DISK_DIAMETER_AT_REFERENCE":
        radial_dimension(ax, (0.0, 0.0), float(entry.value) / 2.0, label, color, text_angle=145.0)
        return True
    ring_match = re.fullmatch(r"GRILL_RING_CENTER_RADII_AT_REFERENCE\[(\d+)\]", name)
    if ring_match:
        radial_dimension(ax, (0.0, 0.0), float(entry.value), label, color, text_angle=55.0 + 75.0 * int(ring_match.group(1)))
        return True
    return False


def draw_fan_front_annotation(ax, entry, index, bounds, color):
    name = entry.identity
    spec = resolved_fan_specs()[0]
    cx = spec["center_x"]
    frame = spec["frame"]
    cavity = spec["cavity"]
    size = spec["size"]
    label = annotation_label(entry, index)
    ax.add_patch(Rectangle((cx - size / 2.0, -size / 2.0), size, size, fill=False, edgecolor=GREEN, linewidth=0.65, linestyle=":"))
    ax.add_patch(Rectangle((cx - cavity / 2.0, -cavity / 2.0), cavity, cavity, fill=False, edgecolor=ORANGE, linewidth=0.65, linestyle="--"))
    if name == "FAN_FRAME_CORNER_RADIUS":
        radius = float(entry.value)
        center = (cx + frame / 2.0 - radius, frame / 2.0 - radius)
        radial_dimension(ax, center, radius, label, color, text_angle=45.0)
        return True
    if name == "FAN_BODY_CLEARANCE_PER_SIDE":
        body_edge = cx + size / 2.0
        cavity_edge = cx + cavity / 2.0
        ax.plot((body_edge, body_edge), (size * 0.15, size * 0.38), color=GREEN, linewidth=0.9)
        ax.plot((cavity_edge, cavity_edge), (size * 0.15, size * 0.38), color=ORANGE, linewidth=0.9)
        horizontal_dimension(ax, body_edge, cavity_edge, size * 0.28, frame / 2.0 + 7.0, label + "  (TRUE-SCALE EDGE DETAIL)", color)
        return True
    half = spec["hole_spacing"] / 2.0
    hole_center = (cx + half, half)
    if name == "AIRFLOW_TO_COUNTERSINK_MIN_WEB":
        direction = math.sqrt(0.5)
        airflow_edge = (cx + spec["airflow"] / 2.0 * direction, spec["airflow"] / 2.0 * direction)
        hole_edge = (hole_center[0] - float(C["FAN_HOLE_COUNTERSINK_DIAMETER"]) / 2.0 * direction, hole_center[1] - float(C["FAN_HOLE_COUNTERSINK_DIAMETER"]) / 2.0 * direction)
        ax.plot((airflow_edge[0], hole_edge[0]), (airflow_edge[1], hole_edge[1]), color=color, linewidth=1.2, zorder=20)
        detail_dimension(ax, ((airflow_edge[0] + hole_edge[0]) / 2.0, (airflow_edge[1] + hole_edge[1]) / 2.0), (cx, frame / 2.0 + 8.0), label, color, note="MINIMUM WEB")
        return True
    if name == "GRILL_CONNECTION_OVERLAP":
        radius = float(C["GRILL_RING_CENTER_RADII_AT_REFERENCE"][0]) * spec["scale"]
        anchor = (cx + radius, 0.0)
        detail_dimension(ax, anchor, (cx, frame / 2.0 + 8.0), label, color, note="BAR / RING UNION DETAIL")
        return True
    if name == "FAN_HOLE_COUNTERSINK_DIAMETER":
        radial_dimension(ax, hole_center, float(entry.value) / 2.0, label, color, text_angle=35.0)
        return True
    if name == "FAN_HOLE_COLLAR_DIAMETER":
        radial_dimension(ax, hole_center, float(entry.value) / 2.0, label, color, text_angle=145.0)
        return True
    slot_center = cx + float(C["FAN_WIRE_SLOT_OFFSET_AT_REFERENCE"]) * spec["scale"]
    if name == "FAN_WIRE_SLOT_WIDTH":
        width = float(entry.value)
        horizontal_dimension(ax, slot_center - width / 2.0, slot_center + width / 2.0, -frame / 2.0, -frame / 2.0 - 7.0, label, color)
        return True
    if name == "FAN_FRAME_WALL":
        horizontal_dimension(ax, cx + cavity / 2.0, cx + frame / 2.0, frame * 0.28, frame / 2.0 + 7.0, label, color)
        return True
    if name == "GRILL_BAR_WIDTH":
        width = float(entry.value)
        horizontal_dimension(ax, cx - width / 2.0, cx + width / 2.0, 0.0, -frame / 2.0 - 7.0, label, color)
        return True
    if name == "GRILL_RING_WIDTH":
        width = float(entry.value)
        radius = float(C["GRILL_RING_CENTER_RADII_AT_REFERENCE"][1]) * spec["scale"]
        horizontal_dimension(ax, cx + radius - width / 2.0, cx + radius + width / 2.0, 0.0, frame / 2.0 + 7.0, label, color)
        return True
    return False


def draw_fan_side_annotation(ax, entry, index, bounds, color):
    name = entry.identity
    spec = resolved_fan_specs()[0]
    frame = spec["frame"]
    depth = float(C["FAN_FRAME_DEPTH"])
    grill = float(C["GRILL_THICKNESS"])
    label = annotation_label(entry, index)
    ax.add_patch(Rectangle((-frame / 2.0, 0.0), frame, depth, fill=False, edgecolor=BLUE, linewidth=1.0, zorder=12))
    grill_z0 = depth - grill if C["FAN_GRILL_ON_BACK"] else 0.0
    ax.add_patch(Rectangle((-frame / 2.0, grill_z0), frame, grill, facecolor="#d9eaf1", edgecolor=CYAN, linewidth=0.7, alpha=0.55, zorder=11))
    hole_y = spec["hole_spacing"] / 2.0
    counter_depth = float(C["FAN_HOLE_COUNTERSINK_DEPTH"])
    counter_z0 = depth - counter_depth if C["FAN_GRILL_ON_BACK"] else 0.0
    ax.add_patch(Rectangle((hole_y - float(C["FAN_HOLE_COUNTERSINK_DIAMETER"]) / 2.0, counter_z0), float(C["FAN_HOLE_COUNTERSINK_DIAMETER"]), counter_depth, fill=False, edgecolor=RED, linewidth=0.7, linestyle="--", zorder=14))
    collar_height = float(C["FAN_HOLE_COLLAR_HEIGHT"])
    collar_z0 = grill_z0 - collar_height if C["FAN_GRILL_ON_BACK"] else grill_z0 + grill
    ax.add_patch(Rectangle((hole_y - float(C["FAN_HOLE_COLLAR_DIAMETER"]) / 2.0, collar_z0), float(C["FAN_HOLE_COLLAR_DIAMETER"]), collar_height, fill=False, edgecolor=GREEN, linewidth=0.7, linestyle="--", zorder=14))
    wire_depth = float(C["FAN_WIRE_SLOT_DEPTH"])
    wire_z0 = 0.0 if C["FAN_GRILL_ON_BACK"] else depth - wire_depth
    ax.add_patch(Rectangle((-frame / 2.0, wire_z0), float(C["FAN_FRAME_WALL"]), wire_depth, facecolor=WHITE, edgecolor=ORANGE, linewidth=0.7, zorder=13))
    if name == "FAN_FRAME_DEPTH":
        vertical_dimension(ax, 0.0, depth, frame / 2.0, frame / 2.0 + 7.0, label, color)
        return True
    if name == "FAN_ROTATION_PIVOT_Z":
        pivot = depth - float(entry.value) if C["FAN_GRILL_ON_BACK"] else float(entry.value)
        vertical_dimension(ax, pivot, depth if C["FAN_GRILL_ON_BACK"] else 0.0, 0.0, frame / 2.0 + 7.0, label, color)
        ax.add_patch(Circle((0.0, pivot), 0.8, facecolor=color, edgecolor=color, zorder=20))
        return True
    if name == "FAN_HOLE_COUNTERSINK_DEPTH":
        z1 = depth
        z0 = z1 - float(entry.value)
        vertical_dimension(ax, z0, z1, frame * 0.28, frame / 2.0 + 7.0, label, color)
        return True
    if name == "FAN_HOLE_COLLAR_HEIGHT":
        inner = grill_z0
        vertical_dimension(ax, inner - float(entry.value), inner, frame * 0.28, frame / 2.0 + 7.0, label, color)
        return True
    if name == "FAN_WIRE_SLOT_DEPTH":
        if C["FAN_GRILL_ON_BACK"]:
            z0, z1 = 0.0, float(entry.value)
        else:
            z0, z1 = depth - float(entry.value), depth
        vertical_dimension(ax, z0, z1, -frame * 0.25, -frame / 2.0 - 7.0, label, color)
        return True
    if name == "GRILL_THICKNESS":
        vertical_dimension(ax, grill_z0, grill_z0 + grill, 0.0, frame / 2.0 + 7.0, label, color)
        return True
    return False


def draw_support_annotation(ax, entry, index, bounds, color):
    name = entry.identity
    datums = support_datums()
    label = annotation_label(entry, index)
    width = datums["width"]
    support_center_x = datums["fan_center_x"]
    bottom = datums["bottom_y"]
    top = datums["top_y"]
    ax.add_patch(Rectangle((support_center_x - width / 2.0, bottom), width, top - bottom, fill=False, edgecolor=PURPLE, linewidth=1.0, zorder=15))
    if name == "SUPPORT_HUB_WIDTH_PER_FAN":
        value = float(entry.value)
        horizontal_dimension(ax, support_center_x - width / 2.0, support_center_x - width / 2.0 + value, bottom, bottom - 8.0, label, color)
        return True
    if name == "SUPPORT_HUB_WIDTH_OVERRIDE":
        horizontal_dimension(ax, support_center_x - width / 2.0, support_center_x + width / 2.0, bottom, bottom - 8.0, label, color)
        return True
    if name == "SUPPORT_HUB_BELOW_FAN_Y":
        fan_bottom = -max(spec["frame"] for spec in resolved_fan_specs()) / 2.0
        # Keep this long rotated label outside both hub-width labels below the
        # part; same-orientation rail staggering cannot prevent that crossing.
        vertical_dimension(ax, bottom, fan_bottom, support_center_x - width / 2.0, bounds[0] - 8.0, label, color)
        return True
    if name == "SUPPORT_ARM_START_PITCH_X":
        pitch = float(entry.value)
        horizontal_dimension(ax, support_center_x - pitch / 2.0, support_center_x + pitch / 2.0, top - float(C["SUPPORT_ARM_HUB_INSERT_Y"]), bottom - 8.0, label, color)
        return True
    if name == "SUPPORT_ARM_HUB_INSERT_Y":
        value = float(entry.value)
        vertical_dimension(ax, top - value, top, support_center_x + float(C["SUPPORT_ARM_START_PITCH_X"]) / 2.0, support_center_x + width / 2.0 + 8.0, label, color)
        return True
    if name == "SUPPORT_ARM_FAN_INSERT_Y_AT_REFERENCE":
        ref_bottom = -float(C["FAN_REFERENCE_SIZE_MM"]) / 2.0
        center_x = resolved_fan_specs()[0]["center_x"]
        ref_size = float(C["FAN_REFERENCE_SIZE_MM"])
        ax.add_patch(Rectangle((center_x - ref_size / 2.0, -ref_size / 2.0), ref_size, ref_size, fill=False, edgecolor=GRAY, linewidth=0.7, linestyle=":", zorder=13))
        ax.text(center_x, ref_size / 2.0, "60 mm SUPPORT DATUM", fontsize=4.5, color=GRAY, ha="center", va="bottom")
        applied = min(float(entry.value), float(C["FAN_FRAME_WALL"]) - float(C["BOOLEAN_OVERLAP"]))
        vertical_dimension(ax, ref_bottom, ref_bottom + applied, center_x, bounds[2] + 8.0, label + f"  → {fmt(applied)} mm APPLIED @ 60 mm REF", color)
        return True
    if name == "SUPPORT_HUB_DEPTH_Y":
        vertical_dimension(ax, bottom, top, support_center_x + width / 2.0, support_center_x + width / 2.0 + 8.0, label, color)
        return True
    if name in {"SUPPORT_ARM_CENTER_WIDTH", "SUPPORT_ARM_FAN_WIDTH"}:
        value = float(entry.value)
        spec = resolved_fan_specs()[0]
        applied = value * spec["scale"]
        if name == "SUPPORT_ARM_CENTER_WIDTH":
            center_x = support_center_x - float(C["SUPPORT_ARM_START_PITCH_X"]) / 2.0
            witness_y = top - float(C["SUPPORT_ARM_HUB_INSERT_Y"])
        else:
            center_x = spec["center_x"] + float(C["FAN_ROTATION_PIVOT_INWARD_X_AT_REFERENCE"]) * spec["scale"]
            applied_insert = min(
                float(C["SUPPORT_ARM_FAN_INSERT_Y_AT_REFERENCE"]) * spec["scale"],
                float(C["FAN_FRAME_WALL"]) - float(C["BOOLEAN_OVERLAP"]),
            )
            witness_y = -spec["frame"] / 2.0 + applied_insert
        horizontal_dimension(ax, center_x - applied / 2.0, center_x + applied / 2.0, witness_y, bottom - 8.0, label + f"  → {fmt(applied)} mm ON {fmt(spec['size'])} mm FAN", color)
        return True
    return False


def draw_support_side_annotation(ax, entry, index, bounds, color):
    if entry.identity != "SUPPORT_THICKNESS":
        return False
    datums = support_datums()
    vertical_dimension(ax, datums["support_z0"], datums["support_z1"], datums["bottom_y"], bounds[2] + 8.0, annotation_label(entry, index), color)
    return True


def draw_stalk_front_annotation(ax, entry, index, bounds, color):
    name = entry.identity
    datums = support_datums()
    z0, z1 = datums["stalk_z0"], datums["stalk_z1"]
    stalk_width = float(C["STALK_WIDTH"])
    hub_width = float(C["STALK_HUB_FLARE_WIDTH"])
    deflection = float(C["STALK_LATERAL_DEFLECTION_X"])
    sections, route_points, route_distances = stalk_front_sections()
    total_length = route_distances[-1]
    right_profile = [
        (center_x + half_width, z)
        for _distance, center_x, z, half_width in sections
    ]
    left_profile = [
        (center_x - half_width, z)
        for _distance, center_x, z, half_width in sections
    ]
    profile = right_profile + list(reversed(left_profile))
    ax.add_patch(Polygon(profile, closed=True, facecolor="#d9eaf1", edgecolor=PURPLE, linewidth=1.1, alpha=0.85, zorder=15))
    ax.plot(
        [section[1] for section in sections],
        [section[2] for section in sections],
        color=GRAY,
        linewidth=0.75,
        linestyle="--",
        zorder=16,
    )
    if name == "STALK_HUB_FLARE_WIDTH":
        horizontal_dimension(ax, deflection - hub_width / 2.0, deflection + hub_width / 2.0, z1, z1 + 8.0, annotation_label(entry, index), color)
        return True
    if name == "STALK_WIDTH":
        if C["STALK_DROPPED_ROUTE_ENABLED"]:
            sample_distance = (route_distances[1] + route_distances[2]) / 2.0
        else:
            sample_distance = total_length / 2.0
        _sample_y, sample_z = stalk_route_point_at_distance(
            route_points,
            route_distances,
            sample_distance,
        )
        sample_x = deflection * sample_distance / total_length
        sweep_ratio = deflection / total_length
        sweep_scale = math.hypot(1.0, sweep_ratio)
        normal_x = 1.0 / sweep_scale
        normal_z = -sweep_ratio / sweep_scale
        endpoint_0 = (
            sample_x - normal_x * stalk_width / 2.0,
            sample_z - normal_z * stalk_width / 2.0,
        )
        endpoint_1 = (
            sample_x + normal_x * stalk_width / 2.0,
            sample_z + normal_z * stalk_width / 2.0,
        )
        ax.add_patch(FancyArrowPatch(endpoint_0, endpoint_1, arrowstyle="<->", mutation_scale=8, color=color, linewidth=0.9, zorder=20))
        detail_dimension(
            ax,
            ((endpoint_0[0] + endpoint_1[0]) / 2.0, (endpoint_0[1] + endpoint_1[1]) / 2.0),
            ((bounds[0] + bounds[2]) / 2.0, z0 - 8.0),
            annotation_label(entry, index),
            color,
            note="TRUE WIDTH NORMAL TO DEFLECTED CENTERLINE",
        )
        return True
    if name == "STALK_LATERAL_DEFLECTION_X":
        horizontal_dimension(ax, 0.0, deflection, z1, z1 + 8.0, annotation_label(entry, index), color)
        angle = math.degrees(math.atan2(deflection, total_length))
        ax.text(
            deflection / 2.0,
            (z0 + z1) / 2.0,
            f"DERIVED SWEEP ANGLE = {fmt(round(angle, 2))}°",
            fontsize=4.8,
            color=color,
            weight="bold",
            ha="center",
            bbox={"boxstyle": "round,pad=0.16", "facecolor": WHITE, "edgecolor": color, "linewidth": 0.5},
            zorder=30,
        )
        return True
    return False


def route_point_at_distance(points, distance, *, from_end=False):
    ordered = tuple(reversed(points)) if from_end else points
    remaining = distance
    for start, end in zip(ordered, ordered[1:]):
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        if remaining <= length:
            ratio = remaining / length
            return (start[0] + ratio * (end[0] - start[0]), start[1] + ratio * (end[1] - start[1]))
        remaining -= length
    return ordered[-1]


def draw_stalk_side_annotation(ax, entry, index, bounds, color):
    name = entry.identity
    datums = support_datums()
    points = dropped_route_points()
    label = annotation_label(entry, index)
    if name == "STALK_LENGTH_Z":
        vertical_dimension(ax, datums["stalk_z0"], datums["stalk_z1"], datums["stalk_y"], bounds[2] + 8.0, label + "  (STRAIGHT ROUTE)", color)
        return True
    if name == "STALK_BOTTOM_Y_OVERHANG":
        stalk_bottom = datums["stalk_y"] - float(C["STALK_DEPTH_Y"]) / 2.0
        horizontal_dimension(ax, datums["bottom_y"], stalk_bottom, datums["stalk_z1"], bounds[1] - 6.0, label, color)
        return True
    if name == "STALK_ROUTE_DROP_Y":
        horizontal_dimension(ax, points[1][0], points[0][0], points[0][1], bounds[1] - 7.0, label, color)
        return True
    if name == "STALK_ROUTE_BACK_Z":
        vertical_dimension(ax, points[1][1], points[2][1], points[1][0], bounds[0] - 8.0, label, color)
        return True
    if name == "STALK_ROUTE_RETURN_RISE_Y":
        horizontal_dimension(ax, points[2][0], points[3][0], points[3][1], bounds[1] - 7.0, label, color)
        return True
    if name == "STALK_ROUTE_TRANSITION_ANGLE_DEG":
        angle_dimension(ax, points[2], 9.0, -float(entry.value), 90.0, label, color)
        return True
    if name == "STALK_HUB_FLARE_LENGTH_Z":
        endpoint = route_point_at_distance(points, float(entry.value), from_end=True)
        ax.add_patch(FancyArrowPatch(points[-1], endpoint, arrowstyle="<->", mutation_scale=8, color=color, linewidth=0.9, zorder=20))
        detail_dimension(ax, endpoint, (bounds[2] + 2.0, bounds[3] + 6.0), label, color, note="ALONG ROUTE")
        return True
    if name == "STALK_MOUNT_FLARE_LENGTH_Z":
        endpoint = route_point_at_distance(points, float(entry.value))
        ax.add_patch(FancyArrowPatch(points[0], endpoint, arrowstyle="<->", mutation_scale=8, color=color, linewidth=0.9, zorder=20))
        detail_dimension(ax, endpoint, (bounds[0] - 2.0, bounds[1] - 6.0), label, color, note="ALONG ROUTE")
        return True
    if name == "STALK_DEPTH_Y":
        half = float(entry.value) / 2.0
        horizontal_dimension(ax, points[1][0] - half, points[1][0] + half, points[1][1], bounds[1] - 7.0, label, color)
        return True
    return False


def draw_mount_annotation(ax, entry, index, bounds, color):
    name = entry.identity
    mount = mount_datums()
    width = float(C["MOUNT_BLOCK_WIDTH"])
    height = float(C["MOUNT_BLOCK_HEIGHT_Z"])
    center_z = mount["center_z"]
    label = annotation_label(entry, index)
    ax.add_patch(Rectangle((-width / 2.0, mount["bottom_z"]), width, height, facecolor="#d9eaf1", edgecolor=PURPLE, linewidth=1.0, alpha=0.82, zorder=14))
    for x in (-float(C["MOUNT_HOLE_SPACING"]) / 2.0, float(C["MOUNT_HOLE_SPACING"]) / 2.0):
        ax.add_patch(Circle((x, center_z), float(C["MOUNT_HOLE_DIAMETER"]) / 2.0, facecolor=WHITE, edgecolor=GREEN, linewidth=0.8, zorder=16))
        ax.add_patch(Circle((x, center_z), float(C["MOUNT_COUNTERSINK_DIAMETER"]) / 2.0, fill=False, edgecolor=RED, linewidth=0.7, linestyle="--", zorder=15))
    if name == "MOUNT_BLOCK_WIDTH":
        horizontal_dimension(ax, -width / 2.0, width / 2.0, mount["bottom_z"], mount["bottom_z"] - 6.0, label, color)
        return True
    if name == "MOUNT_BLOCK_HEIGHT_Z":
        vertical_dimension(ax, mount["bottom_z"], mount["top_z"], width / 2.0, bounds[2] + 6.0, label, color)
        return True
    if name == "MOUNT_BLOCK_OVERLAP":
        vertical_dimension(ax, support_datums()["stalk_z0"], mount["top_z"], 0.0, bounds[2] + 6.0, label, color)
        return True
    if name == "MOUNT_HOLE_SPACING":
        half = float(entry.value) / 2.0
        horizontal_dimension(ax, -half, half, center_z, mount["bottom_z"] - 6.0, label, color)
        return True
    if name == "MOUNT_COUNTERSINK_DIAMETER":
        radial_dimension(ax, (-float(C["MOUNT_HOLE_SPACING"]) / 2.0, center_z), float(entry.value) / 2.0, label, color, text_angle=135.0)
        return True
    if name == "MOUNT_HOLE_DIAMETER":
        radial_dimension(ax, (float(C["MOUNT_HOLE_SPACING"]) / 2.0, center_z), float(entry.value) / 2.0, label, color, text_angle=35.0)
        return True
    return False


def draw_mount_side_annotation(ax, entry, index, bounds, color):
    mount = mount_datums()
    name = entry.identity
    label = annotation_label(entry, index)
    ax.add_patch(Rectangle((mount["front_y"], mount["bottom_z"]), float(C["MOUNT_BLOCK_DEPTH_Y"]), float(C["MOUNT_BLOCK_HEIGHT_Z"]), facecolor="#d9eaf1", edgecolor=PURPLE, linewidth=1.0, alpha=0.82, zorder=14))
    ax.add_patch(Rectangle((mount["front_y"], mount["center_z"] - float(C["MOUNT_COUNTERSINK_DIAMETER"]) / 2.0), float(C["MOUNT_COUNTERSINK_DEPTH"]), float(C["MOUNT_COUNTERSINK_DIAMETER"]), fill=False, edgecolor=RED, linewidth=0.7, linestyle="--", zorder=15))
    if name == "MOUNT_BLOCK_DEPTH_Y":
        horizontal_dimension(ax, mount["front_y"], mount["back_y"], mount["bottom_z"], mount["bottom_z"] - 6.0, label, color)
        return True
    if name == "MOUNT_COUNTERSINK_DEPTH":
        horizontal_dimension(ax, mount["front_y"], mount["front_y"] + float(entry.value), mount["center_z"], mount["top_z"] + 6.0, label + "  (COUNTERBORE REF)", color)
        return True
    return False


def draw_adapter_front_annotation(ax, entry, index, bounds, color):
    name = entry.identity
    data = adapter_datums()
    label = annotation_label(entry, index)
    plate_width = float(C["GOPRO_ADAPTER_PLATE_WIDTH"])
    mount_z = data["center_z"]
    if name == "GOPRO_ADAPTER_PLATE_WIDTH":
        horizontal_dimension(ax, -plate_width / 2.0, plate_width / 2.0, data["plate_top_z"], data["plate_top_z"] + 6.0, label, color)
        return True
    if name == "GOPRO_ADAPTER_PLATE_HEIGHT_Z":
        vertical_dimension(ax, data["plate_bottom_z"], data["plate_top_z"], plate_width / 2.0, plate_width / 2.0 + 6.0, label, color)
        return True
    if name == "GOPRO_ADAPTER_HOLE_Z_OFFSET":
        vertical_dimension(ax, data["plate_center_z"], mount_z, 0.0, plate_width / 2.0 + 6.0, label, color)
        return True
    if name == "GOPRO_ADAPTER_ROOT_WIDTH":
        width = float(entry.value)
        horizontal_dimension(ax, -width / 2.0, width / 2.0, data["plate_bottom_z"], data["plate_bottom_z"] - 6.0, label, color)
        return True
    hole_center = (-float(C["MOUNT_HOLE_SPACING"]) / 2.0, mount_z)
    if name == "GOPRO_ADAPTER_INSERT_DIAMETER":
        radial_dimension(ax, hole_center, float(entry.value) / 2.0, label, color, text_angle=145.0)
        return True
    if name == "GOPRO_ADAPTER_INSERT_PILOT_DIAMETER":
        radial_dimension(ax, hole_center, float(entry.value) / 2.0, label, color, text_angle=35.0)
        return True
    if name in {"GOPRO_PRONG_THICKNESS", "GOPRO_PRONG_GAP"}:
        thickness = float(C["GOPRO_PRONG_THICKNESS"])
        gap = float(C["GOPRO_PRONG_GAP"])
        section_z = data["pivot_z"] - float(C["GOPRO_PRONG_RADIUS"]) - 5.0
        centers = [-(thickness + gap), 0.0, thickness + gap]
        for center in centers:
            ax.add_patch(Rectangle((center - thickness / 2.0, section_z), thickness, 3.0, facecolor="#f7d9ca", edgecolor=ORANGE, linewidth=0.7, zorder=15))
        if name == "GOPRO_PRONG_THICKNESS":
            x0, x1 = centers[1] - thickness / 2.0, centers[1] + thickness / 2.0
        else:
            x0, x1 = centers[1] + thickness / 2.0, centers[2] - thickness / 2.0
        horizontal_dimension(ax, x0, x1, section_z, section_z - 4.0, label + "  (PRONG STACK SECTION)", color)
        return True
    if name in {"GOPRO_NUT_BOSS_DIAMETER", "GOPRO_NUT_ACROSS_FLATS"}:
        center = (0.0, data["plate_bottom_z"] + 6.5)
        boss_radius = float(C["GOPRO_NUT_BOSS_DIAMETER"]) / 2.0
        ax.add_patch(Circle(center, boss_radius, facecolor="#f7d9ca", edgecolor=ORANGE, linewidth=0.9, zorder=14))
        across = float(C["GOPRO_NUT_ACROSS_FLATS"])
        circumradius = across / math.sqrt(3.0)
        hex_points = [(center[0] + circumradius * math.cos(math.radians(30.0 + 60.0 * i)), center[1] + circumradius * math.sin(math.radians(30.0 + 60.0 * i))) for i in range(6)]
        ax.add_patch(Polygon(hex_points, closed=True, facecolor=WHITE, edgecolor=GREEN, linewidth=0.8, zorder=15))
        ax.text(center[0], center[1] + boss_radius + 1.8, "NUT TRAP END VIEW — NTS", fontsize=4.5, color=ORANGE, ha="center", weight="bold")
        if name == "GOPRO_NUT_BOSS_DIAMETER":
            radial_dimension(ax, center, boss_radius, label + "  (NUT-END VIEW)", color, text_angle=35.0)
        else:
            horizontal_dimension(ax, center[0] - across / 2.0, center[0] + across / 2.0, center[1], center[1] - boss_radius - 4.0, label + "  (NUT-END VIEW)", color)
        return True
    if name == "GOPRO_NUT_BOSS_DEPTH":
        depth = float(entry.value)
        section_y = data["plate_bottom_z"] - 10.0
        ax.add_patch(Rectangle((-depth / 2.0, section_y), depth, 4.0, facecolor="#f7d9ca", edgecolor=ORANGE, linewidth=0.8, zorder=15))
        horizontal_dimension(ax, -depth / 2.0, depth / 2.0, section_y, section_y - 4.0, label + "  (BOSS AXIAL SECTION)", color)
        return True
    return False


def draw_adapter_side_annotation(ax, entry, index, bounds, color):
    name = entry.identity
    data = adapter_datums()
    label = annotation_label(entry, index)
    ax.add_patch(Rectangle((data["plate_front_y"], data["plate_bottom_z"]), float(C["GOPRO_ADAPTER_PLATE_DEPTH_Y"]), float(C["GOPRO_ADAPTER_PLATE_HEIGHT_Z"]), fill=False, edgecolor=ORANGE, linewidth=1.0, zorder=15))
    insert_depth = float(C["GOPRO_ADAPTER_INSERT_DEPTH"])
    insert_radius = float(C["GOPRO_ADAPTER_INSERT_DIAMETER"]) / 2.0
    pilot_radius = float(C["GOPRO_ADAPTER_INSERT_PILOT_DIAMETER"]) / 2.0
    transition = float(C["GOPRO_ADAPTER_INSERT_TRANSITION_DEPTH"])
    insert_end = data["mating_y"] - insert_depth
    ax.add_patch(Rectangle((insert_end, data["center_z"] - insert_radius), insert_depth, 2.0 * insert_radius, fill=False, edgecolor=PURPLE, linewidth=0.7, linestyle="--", zorder=15))
    ax.add_patch(Polygon([(insert_end - transition, data["center_z"] - pilot_radius), (insert_end, data["center_z"] - insert_radius), (insert_end, data["center_z"] + insert_radius), (insert_end - transition, data["center_z"] + pilot_radius)], closed=True, fill=False, edgecolor=GREEN, linewidth=0.7, linestyle="--", zorder=15))
    pivot = (data["pivot_y"], data["pivot_z"])
    if name == "GOPRO_ADAPTER_MATING_GAP":
        mount_face = data["front_y"]
        horizontal_dimension(ax, data["mating_y"], mount_face, data["center_z"], data["plate_top_z"] + 6.0, label, color)
        return True
    if name == "GOPRO_ADAPTER_PLATE_DEPTH_Y":
        horizontal_dimension(ax, data["plate_front_y"], data["mating_y"], data["plate_top_z"], data["plate_top_z"] + 6.0, label, color)
        return True
    if name == "GOPRO_ADAPTER_INSERT_DEPTH":
        horizontal_dimension(ax, data["mating_y"] - float(entry.value), data["mating_y"], data["center_z"], data["plate_top_z"] + 6.0, label, color)
        return True
    if name == "GOPRO_ADAPTER_INSERT_TRANSITION_DEPTH":
        horizontal_dimension(ax, insert_end - float(entry.value), insert_end, data["center_z"], data["plate_bottom_z"] - 6.0, label, color)
        return True
    if name == "GOPRO_PRONG_RADIUS":
        radial_dimension(ax, pivot, float(entry.value), label, color, text_angle=45.0)
        return True
    if name == "GOPRO_PIVOT_HOLE_DIAMETER":
        radial_dimension(ax, pivot, float(entry.value) / 2.0, label, color, text_angle=145.0)
        return True
    if name == "GOPRO_PIVOT_FROM_MATING_FACE_Y":
        horizontal_dimension(ax, data["pivot_y"], data["mating_y"], data["pivot_z"], data["plate_bottom_z"] - 6.0, label, color)
        return True
    if name == "GOPRO_PIVOT_BELOW_MOUNT_HOLES_Z":
        vertical_dimension(ax, data["pivot_z"], data["center_z"], data["pivot_y"], bounds[0] - 7.0, label, color)
        return True
    return False


def draw_splitter_front_annotation(ax, entry, index, bounds, color):
    name = entry.identity
    spec = resolved_fan_specs(1)[0]
    opening = splitter_opening(spec)
    label = annotation_label(entry, index)
    if name == "SINGLE_FAN_SPLITTER_LEADING_EDGE_WIDTH":
        width = float(entry.value)
        horizontal_dimension(ax, -width / 2.0, width / 2.0, -opening / 2.0, -spec["size"] / 2.0 - 6.0, label, color)
        return True
    if name == "SINGLE_FAN_SPLITTER_EDGE_WEB":
        horizontal_dimension(ax, opening / 2.0, spec["size"] / 2.0, 0.0, spec["size"] / 2.0 + 6.0, label, color)
        return True
    if name == "SINGLE_FAN_SPLITTER_HOLE_CLEARANCE":
        half = spec["hole_spacing"] / 2.0
        center = (half, half)
        purchased_radius = spec["hole_diameter"] / 2.0
        splitter_radius = (spec["hole_diameter"] + float(entry.value)) / 2.0
        ax.add_patch(Circle(center, purchased_radius, fill=False, edgecolor=GREEN, linewidth=1.0, zorder=20))
        ax.add_patch(Circle(center, splitter_radius, fill=False, edgecolor=color, linewidth=1.0, zorder=21))
        detail_dimension(ax, (center[0] + splitter_radius, center[1]), (0.0, spec["size"] / 2.0 + 14.0), label, color, note="DIAMETRAL HOLE CLEARANCE")
        return True
    return False


def draw_splitter_side_annotation(ax, entry, index, bounds, color):
    name = entry.identity
    label = annotation_label(entry, index)
    plate = float(C["SINGLE_FAN_SPLITTER_PLATE_THICKNESS"])
    length = float(C["SINGLE_FAN_SPLITTER_VANE_LENGTH_Z"])
    lead = float(C["SINGLE_FAN_SPLITTER_LEADING_EDGE_WIDTH"]) / 2.0
    downstream = lead + length * math.tan(math.radians(float(C["SINGLE_FAN_SPLITTER_OUTLET_ANGLE_DEG"])))
    if name == "SINGLE_FAN_SPLITTER_OUTLET_ANGLE_DEG":
        angle_dimension(ax, (0.0, -plate), 10.0, -float(entry.value), -90.0, label, color)
        return True
    if name == "SINGLE_FAN_SPLITTER_VANE_LENGTH_Z":
        vertical_dimension(ax, -plate - length, -plate, downstream, bounds[2] + 6.0, label, color)
        return True
    if name == "SINGLE_FAN_SPLITTER_VANE_THICKNESS":
        thickness = float(entry.value)
        horizontal_dimension(ax, downstream - thickness, downstream, -plate - length, -plate - length - 5.0, label, color)
        return True
    if name == "SINGLE_FAN_SPLITTER_PLATE_THICKNESS":
        vertical_dimension(ax, -plate, 0.0, bounds[2], bounds[2] + 6.0, label, color)
        return True
    return False


def draw_splitter_clearance_annotation(ax, entry, index, bounds, color):
    if entry.identity != "SINGLE_FAN_SPLITTER_HOLDER_CLEARANCE":
        return False
    mount = mount_datums(dropped=True)
    highest_holder_y = mount["center_y"] + max(float(C["STALK_DEPTH_Y"]), float(C["MOUNT_BLOCK_DEPTH_Y"])) / 2.0
    notch_y = highest_holder_y + float(entry.value)
    horizontal_dimension(ax, highest_holder_y, notch_y, mount["center_z"], bounds[1] - 6.0, annotation_label(entry, index), color)
    return True


def draw_mesh_annotation(ax, entry, index, bounds, color):
    if entry.identity not in {"BOOLEAN_OVERLAP", "BOOLEAN_MINIMUM_VOLUME_CHANGE", "CLEAN_COINCIDENT_FACE_TOLERANCE", "TRIANGULATION_WELD_DISTANCE"}:
        return False
    geometry = projected_part_geometry("holder", "xy")
    anchors = (
        (geometry.bounds[0] + 0.27 * (geometry.bounds[2] - geometry.bounds[0]), geometry.bounds[3] - 0.20 * (geometry.bounds[3] - geometry.bounds[1])),
        (0.0, geometry.bounds[1] + 0.17 * (geometry.bounds[3] - geometry.bounds[1])),
        (geometry.bounds[2] - 0.22 * (geometry.bounds[2] - geometry.bounds[0]), geometry.bounds[1] + 0.22 * (geometry.bounds[3] - geometry.bounds[1])),
        (geometry.bounds[0] + 0.48 * (geometry.bounds[2] - geometry.bounds[0]), geometry.bounds[3] - 0.28 * (geometry.bounds[3] - geometry.bounds[1])),
    )
    anchor = anchors[index % len(anchors)]
    detail_dimension(ax, anchor, (bounds[0] + (0.28 + 0.20 * index) * (bounds[2] - bounds[0]), bounds[3] + 8.0), annotation_label(entry, index), color, note="MESH / BOOLEAN DETAIL NTS")
    return True


def draw_feature_annotation(ax, view, entry, index, bounds, color):
    handlers = {
        "array_front": draw_array_annotation,
        "fan_front": draw_fan_front_annotation,
        "fan_reference": draw_fan_reference_annotation,
        "fan_side": draw_fan_side_annotation,
        "support_front": draw_support_annotation,
        "support_side": draw_support_side_annotation,
        "stalk_front": draw_stalk_front_annotation,
        "stalk_side": draw_stalk_side_annotation,
        "mount_detail": draw_mount_annotation,
        "mount_side": draw_mount_side_annotation,
        "adapter_front": draw_adapter_front_annotation,
        "adapter_side": draw_adapter_side_annotation,
        "splitter_front": draw_splitter_front_annotation,
        "splitter_side": draw_splitter_side_annotation,
        "splitter_clearance": draw_splitter_clearance_annotation,
        "mesh_detail": draw_mesh_annotation,
    }
    if view == "assembly_side" and entry.identity == "TPU_95A_MOUNT_SCREW_EXTRA_LENGTH_MM":
        data = adapter_datums()
        horizontal_dimension(ax, data["plate_front_y"] - float(entry.value), data["plate_front_y"], data["center_z"], data["plate_bottom_z"] - 6.0, annotation_label(entry, index), color)
        return True
    handler = handlers.get(view)
    return bool(handler and handler(ax, entry, index, bounds, color))


def draw_annotations(ax, view, entries, bounds):
    ax._engineering_bounds = bounds
    ax._used_horizontal_rails = []
    ax._used_vertical_rails = []
    colors = (RED, PURPLE, GREEN)
    for index, entry in enumerate(entries):
        color = colors[index % len(colors)]
        if draw_preset_annotation(ax, entry, index, bounds, color):
            DRAWN_DIMENSION_IDENTITIES.add(entry.identity)
            continue
        if not draw_feature_annotation(ax, view, entry, index, bounds, color):
            raise RuntimeError(
                f"No feature-specific engineering callout for {entry.identity} on {view}"
            )
        DRAWN_DIMENSION_IDENTITIES.add(entry.identity)


def draw_dimension_cards(ax, entries):
    ax.axis("off")
    card_height = 0.29
    for index, entry in enumerate(entries):
        top = 0.98 - index * 0.32
        bottom = top - card_height
        color = (RED, PURPLE, GREEN)[index % 3]
        ax.add_patch(FancyBboxPatch((0.01, bottom), 0.98, card_height, transform=ax.transAxes, boxstyle="round,pad=0.008,rounding_size=0.012", facecolor=WHITE, edgecolor=color, linewidth=0.8))
        ax.text(0.055, top - 0.035, f"D{index + 1}", transform=ax.transAxes, fontsize=7.0, weight="bold", color=WHITE, ha="center", va="center", bbox={"boxstyle": "round,pad=0.18", "facecolor": color, "edgecolor": "none"})
        wrapped_name = wrap_identifier(entry.identity, width=26)
        ax.text(0.12, top - 0.018, wrapped_name, transform=ax.transAxes, fontsize=5.6, weight="bold", color=BLUE, va="top", linespacing=1.02)
        name_lines = wrapped_name.count("\n") + 1
        value_y = top - 0.054 - 0.030 * name_lines
        ax.text(0.055, value_y, dimension_value(entry), transform=ax.transAxes, fontsize=6.7, weight="bold", color=ORANGE, va="top")
        ax.text(0.055, value_y - 0.052, textwrap.fill(entry.description, 35), transform=ax.transAxes, fontsize=4.9, color=INK, va="top", linespacing=1.05)
        profile = " • profile-resolved" if entry.profile_controlled else ""
        ax.text(0.055, bottom + 0.018, f"{entry.category} • line {entry.source_line}{profile}", transform=ax.transAxes, fontsize=4.8, color=GRAY, va="bottom")


def page_dimension_drawing(pdf, page_number: int, view: str, entries):
    fig = new_page(page_number, VIEW_TITLES[view], "Every callout is linked to an exact Python variable; geometry is current-scale unless marked NTS.")
    panel(fig, [0.05, 0.115, 0.68, 0.745], "ENGINEERING DRAWING")
    drawing_ax = fig.add_axes([0.065, 0.14, 0.65, 0.64])
    bounds, proof_label = draw_actual_view(drawing_ax, view)
    draw_annotations(drawing_ax, view, entries, bounds)
    set_bounds(drawing_ax, bounds, padding=0.34)
    drawing_ax.text(0.0, 1.02, proof_label, transform=drawing_ax.transAxes, fontsize=5.8, color=BLUE, weight="bold", va="bottom")
    panel(fig, [0.75, 0.115, 0.20, 0.745], "DIMENSION CALLOUTS")
    cards_ax = fig.add_axes([0.758, 0.14, 0.184, 0.64])
    draw_dimension_cards(cards_ax, entries)
    pdf.savefig(fig)
    plt.close(fig)


def page_cover(pdf):
    fig = new_page(1, "GOPRO DUAL-FAN CONFIGURATION DIMENSION GUIDE", "Live engineering drawings for the parametric holder, adapter, lowered route, splitter and standard fans.")
    ax = fig.add_axes([0.06, 0.16, 0.61, 0.66])
    bounds, _label = draw_actual_view(ax, "assembly_front")
    set_bounds(ax, bounds, padding=0.10)
    ax.set_title("CURRENT HOLDER — ACTUAL STL FRONT PROJECTION", fontsize=7.0, color=BLUE, weight="bold")
    panel(fig, [0.70, 0.16, 0.25, 0.66], "COVERAGE CONTRACT")
    items = (
        ("CONFIG settings parsed", len(CONFIG_ENTRIES)),
        ("Engineering dimensions", len(DIMENSION_ENTRIES)),
        ("Non-dimensional settings", len(SETTING_ENTRIES)),
        ("Drawing sheets", DRAWING_PAGE_COUNT),
        ("Unmapped dimensions", 0),
    )
    for index, (label, value) in enumerate(items):
        y = 0.75 - index * 0.105
        fig.text(0.73, y, str(value), fontsize=16.0, color=(BLUE, ORANGE, GREEN, PURPLE, RED)[index], weight="bold")
        fig.text(0.79, y + 0.003, label, fontsize=6.0, color=INK, va="center")
    fig.text(0.73, 0.245, "Each dimensional identity is routed exactly once, drawn on a recognizable part view, indexed by its full source name, and checked in the rendered PDF.", fontsize=6.1, color=GRAY, wrap=True)
    pdf.savefig(fig)
    plt.close(fig)


def page_parts_overview(pdf, page_number: int):
    fig = new_page(page_number, "PRINTED PARTS AND ORTHOGRAPHIC DATUMS", "Holder and adapter views come from the current generated STL files; the optional splitter is drawn from its live parameters.")
    views = (
        ([0.055, 0.49, 0.42, 0.34], "assembly_front", "HOLDER — FRONT / XY"),
        ([0.515, 0.49, 0.42, 0.34], "assembly_side", "HOLDER + ADAPTER — SIDE / YZ"),
        ([0.055, 0.12, 0.42, 0.29], "adapter_front", "DETACHABLE ADAPTER — XZ"),
        ([0.515, 0.12, 0.42, 0.29], "splitter_side", "BOLT-ON SPLITTER — XZ"),
    )
    for rect, view, title in views:
        panel(fig, rect, title)
        ax = fig.add_axes([rect[0] + 0.015, rect[1] + 0.025, rect[2] - 0.03, rect[3] - 0.075])
        bounds, label = draw_actual_view(ax, view)
        set_bounds(ax, bounds, padding=0.11)
        ax.text(0.5, -0.08, label, transform=ax.transAxes, fontsize=4.8, color=GRAY, ha="center")
    pdf.savefig(fig)
    plt.close(fig)


def page_options_overview(pdf, page_number: int):
    fig = new_page(page_number, "LOWERED ROUTE AND SPLIT AIRFLOW OPTIONS", "Alternate geometry remains dimensioned even when its build switch is currently False.")
    panel(fig, [0.055, 0.14, 0.50, 0.70], "DOWN / BACK / UP STALK ROUTE")
    route_ax = fig.add_axes([0.075, 0.18, 0.46, 0.57])
    bounds, label = draw_actual_view(route_ax, "stalk_side")
    set_bounds(route_ax, bounds, padding=0.13)
    route_ax.text(0.5, -0.08, label, transform=route_ax.transAxes, fontsize=5.0, color=GRAY, ha="center")
    panel(fig, [0.59, 0.14, 0.35, 0.70], "FOUR-HOLE AIRFLOW SPLITTER")
    split_ax = fig.add_axes([0.61, 0.23, 0.31, 0.47])
    bounds, label = draw_actual_view(split_ax, "splitter_front")
    set_bounds(split_ax, bounds, padding=0.15)
    split_ax.text(0.5, -0.10, label, transform=split_ax.transAxes, fontsize=5.0, color=GRAY, ha="center")
    fig.text(0.61, 0.18, "The full center leading edge and two 22° default vanes redirect otherwise wasted center airflow toward separated cameras.", fontsize=5.7, color=INK, wrap=True)
    pdf.savefig(fig)
    plt.close(fig)


def page_profiles_overview(pdf, page_number: int):
    fig = new_page(page_number, "MATERIAL PROFILES AND STANDARD FAN REFERENCES", "Profile-resolved dimensions use the selected material; purchased-fan dimensions remain shared across generators.")
    profile = ENV["MATERIAL_PROFILES"]
    ax = fig.add_axes([0.055, 0.17, 0.50, 0.64])
    ax.axis("off")
    ax.text(0.0, 1.03, "PROFILE-CONTROLLED GEOMETRY", fontsize=7.0, color=BLUE, weight="bold")
    keys = sorted({key for values in profile.values() for key in values if unit_for(key, profile["RIGID"].get(key)) != "setting"})
    ax.text(0.02, 0.97, "VARIABLE", fontsize=5.8, weight="bold", color=GRAY)
    ax.text(0.63, 0.97, "RIGID", fontsize=5.8, weight="bold", color=BLUE)
    ax.text(0.81, 0.97, "TPU_95A", fontsize=5.8, weight="bold", color=ORANGE)
    for index, key in enumerate(keys):
        y = 0.925 - index * 0.055
        ax.add_patch(Rectangle((0.0, y - 0.018), 0.98, 0.046, transform=ax.transAxes, facecolor=WHITE if index % 2 else LIGHT, edgecolor="none"))
        ax.text(0.02, y, key, fontsize=5.1, color=INK, va="center")
        ax.text(0.63, y, fmt(profile["RIGID"].get(key)), fontsize=5.4, color=BLUE, va="center")
        ax.text(0.81, y, fmt(profile["TPU_95A"].get(key)), fontsize=5.4, color=ORANGE, va="center")
    panel(fig, [0.59, 0.15, 0.35, 0.68], "STANDARD FAN SET")
    fan_ax = fig.add_axes([0.61, 0.28, 0.31, 0.40])
    bounds = draw_standard_fan(fan_ax, int(C["FAN_SIZES_MM"][0]))
    set_bounds(fan_ax, bounds, padding=0.12)
    sizes = ", ".join(str(size) for size in sorted(STANDARD_FAN_PRESETS))
    fig.text(0.62, 0.21, f"Supported nominal sizes: {sizes} mm", fontsize=6.2, color=BLUE, weight="bold")
    fig.text(0.62, 0.18, "Frame, depth, mounting pattern, opening and hub values are individually covered on the fan-reference sheets.", fontsize=5.6, color=GRAY, wrap=True)
    pdf.savefig(fig)
    plt.close(fig)


def page_settings(pdf, page_number: int, entries):
    fig = new_page(page_number, "NON-DIMENSIONAL CONFIGURATION APPENDIX", "Switches, filenames, solvers, discrete counts and print-process settings; physical dimensions are on engineering sheets.")
    panel(fig, [0.055, 0.15, 0.34, 0.67], "ACTUAL ASSEMBLY REFERENCE")
    ax = fig.add_axes([0.075, 0.23, 0.30, 0.49])
    bounds, _label = draw_actual_view(ax, "assembly_front")
    set_bounds(ax, bounds, padding=0.10)
    cards = fig.add_axes([0.43, 0.14, 0.52, 0.69])
    cards.axis("off")
    for index, entry in enumerate(entries):
        y = 0.96 - index * 0.116
        cards.add_patch(FancyBboxPatch((0.0, y - 0.08), 0.99, 0.095, transform=cards.transAxes, boxstyle="round,pad=0.005", facecolor=WHITE if index % 2 else LIGHT, edgecolor=GRID, linewidth=0.5))
        cards.text(0.02, y, entry.name, transform=cards.transAxes, fontsize=5.5, color=BLUE, weight="bold", va="top")
        cards.text(0.57, y, fmt(entry.value), transform=cards.transAxes, fontsize=5.5, color=ORANGE, weight="bold", va="top")
        cards.text(0.02, y - 0.040, textwrap.fill(entry.description, 70), transform=cards.transAxes, fontsize=4.8, color=GRAY, va="top")
        CATALOGUED_SETTING_NAMES.add(entry.name)
    pdf.savefig(fig)
    plt.close(fig)


def page_coverage(pdf, page_number: int):
    missing_drawings = sorted(DIMENSION_IDENTITIES - DRAWN_DIMENSION_IDENTITIES)
    unexpected_drawings = sorted(DRAWN_DIMENSION_IDENTITIES - DIMENSION_IDENTITIES)
    expected_settings = {entry.name for entry in SETTING_ENTRIES}
    missing_settings = sorted(expected_settings - CATALOGUED_SETTING_NAMES)
    if missing_drawings or unexpected_drawings or missing_settings:
        raise RuntimeError(
            "Dimension-guide coverage failure: "
            f"missing drawings={missing_drawings}, unexpected={unexpected_drawings}, "
            f"missing settings={missing_settings}"
        )
    fig = new_page(page_number, "DIMENSION COVERAGE AND SOURCE CLASSIFICATION", "Generated proof that every physical configuration dimension has a recognizable engineering drawing.")
    metrics = (
        ("FEATURE CALLOUTS", f"{len(DRAWN_DIMENSION_IDENTITIES)}/{len(DIMENSION_ENTRIES)}", GREEN),
        ("SETTINGS CATALOGUED", f"{len(CATALOGUED_SETTING_NAMES)}/{len(SETTING_ENTRIES)}", BLUE),
        ("UNMAPPED", "0", RED),
        ("DRAWING SHEETS", str(DRAWING_PAGE_COUNT), PURPLE),
    )
    for index, (label, value, color) in enumerate(metrics):
        x = 0.07 + index * 0.225
        fig.text(x, 0.76, value, fontsize=20.0, weight="bold", color=color)
        fig.text(x, 0.72, label, fontsize=6.0, color=GRAY, weight="bold")
    panel(fig, [0.065, 0.24, 0.42, 0.38], "AUTOMATIC FAILURE CONDITIONS")
    checks = (
        "New uppercase CONFIG assignment is not statically catalogued",
        "Profile dimension is absent from the selected profile inventory",
        "Dimension is missing, duplicated, or routed to an unknown view",
        "Graphical callout or exact variable text is absent from the PDF",
        "Current holder/adapter STL is missing or stale",
        "Source fingerprint, coverage marker, page count, or PDF EOF drifts",
    )
    for index, text in enumerate(checks):
        fig.text(0.085, 0.565 - index * 0.047, f"✓  {text}", fontsize=5.8, color=INK)
    panel(fig, [0.52, 0.24, 0.42, 0.38], "EMBEDDED COVERAGE MANIFEST")
    fig.text(0.545, 0.55, f"source-{SOURCE_HASH}", fontsize=7.0, color=BLUE, weight="bold")
    fig.text(0.545, 0.49, VISUAL_COVERAGE_MARKER, fontsize=5.5, color=GREEN, wrap=True)
    fig.text(0.545, 0.45, FEATURE_CALLOUT_MARKER, fontsize=5.5, color=BLUE)
    fig.text(0.545, 0.41, SETTINGS_COVERAGE_MARKER, fontsize=5.5, color=PURPLE)
    fig.text(0.545, 0.34, "STL-derived views: holder + detachable adapter\nParameter-derived parts: splitter + lowered route\nShared references: 40/60/80/120 mm fans", fontsize=6.0, color=GRAY, linespacing=1.45)
    pdf.savefig(fig)
    plt.close(fig)


def normalized_pdf_text(text: str) -> str:
    return re.sub(r"\s+", "", text).replace("−", "-")


def validate_rendered_pdf() -> None:
    data = OUTPUT_PDF.read_bytes()
    for marker in (
        f"source-{SOURCE_HASH}",
        VISUAL_COVERAGE_MARKER,
        FEATURE_CALLOUT_MARKER,
        SETTINGS_COVERAGE_MARKER,
    ):
        if marker.encode("ascii") not in data:
            raise RuntimeError(f"Generated PDF is missing marker {marker}")
    if not data.rstrip().endswith(b"%%EOF"):
        raise RuntimeError(f"Incomplete dimension guide: {OUTPUT_PDF.name} has no PDF EOF marker")
    page_count = len(re.findall(rb"/Type\s*/Page\b", data))
    if page_count != TOTAL_PAGES:
        raise RuntimeError(f"Generated PDF has {page_count} pages; expected {TOTAL_PAGES}")
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(OUTPUT_PDF), "-"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("pdftotext is required for dimension coverage validation") from exc
    extracted = normalized_pdf_text(result.stdout)
    missing = [
        entry.identity
        for entry in DIMENSION_ENTRIES
        if normalized_pdf_text(entry.identity) not in extracted
    ]
    for label in (
        "ACTUALSTLORTHOGRAPHICPROJECTION",
        "PARAMETRICPRINTED-PARTGEOMETRY",
        "40MMSTANDARDFAN",
        "120MMSTANDARDFAN",
    ):
        if normalized_pdf_text(label) not in extracted:
            missing.append(label)
    if missing:
        raise RuntimeError("Rendered PDF is missing engineering coverage text: " + ", ".join(missing))


def check_pdf_sync() -> None:
    if not OUTPUT_PDF.is_file():
        raise RuntimeError(f"Missing generated dimension guide: {OUTPUT_PDF}")
    validate_rendered_pdf()
    print(
        f"PASS {OUTPUT_PDF.name}: source-{SOURCE_HASH} "
        f"dimensions={len(DIMENSION_ENTRIES)} settings={len(SETTING_ENTRIES)} "
        f"pages={TOTAL_PAGES}"
    )


def generate_pdf() -> None:
    DRAWN_DIMENSION_IDENTITIES.clear()
    CATALOGUED_SETTING_NAMES.clear()
    temporary = tempfile.NamedTemporaryFile(
        prefix=OUTPUT_PDF.stem + "-",
        suffix=".pdf",
        dir=HERE,
        delete=False,
    )
    temporary_path = Path(temporary.name)
    temporary.close()
    try:
        with PdfPages(
            temporary_path,
            metadata={
                "Title": "GoPro dual-fan configuration dimension guide",
                "Subject": "STL-derived engineering drawings and complete CONFIG coverage",
                "Keywords": (
                    f"source-{SOURCE_HASH} {VISUAL_COVERAGE_MARKER} "
                    f"{FEATURE_CALLOUT_MARKER} {SETTINGS_COVERAGE_MARKER}"
                ),
            },
        ) as pdf:
            page_cover(pdf)
            page_parts_overview(pdf, 2)
            page_options_overview(pdf, 3)
            page_profiles_overview(pdf, 4)
            page_number = 5
            for view, entries in DRAWING_PAGE_GROUPS:
                page_dimension_drawing(pdf, page_number, view, entries)
                page_number += 1
            for index in range(0, len(SETTING_ENTRIES), SETTINGS_PER_PAGE):
                page_settings(pdf, page_number, SETTING_ENTRIES[index:index + SETTINGS_PER_PAGE])
                page_number += 1
            page_coverage(pdf, page_number)
            if page_number != TOTAL_PAGES:
                raise RuntimeError(f"Page-plan drift: emitted final sheet {page_number}, expected {TOTAL_PAGES}")
        temporary_path.replace(OUTPUT_PDF)
        OUTPUT_PDF.chmod(0o644)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    validate_rendered_pdf()
    print(
        f"Wrote {OUTPUT_PDF} pages={TOTAL_PAGES} "
        f"dimensions={len(DIMENSION_ENTRIES)} settings={len(SETTING_ENTRIES)} "
        f"source-{SOURCE_HASH}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-sync",
        action="store_true",
        help="Verify that the generated PDF matches the current sources and coverage plan.",
    )
    args = parser.parse_args()
    if args.check_sync:
        check_pdf_sync()
    else:
        generate_pdf()


if __name__ == "__main__":
    main()
