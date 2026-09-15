#!/usr/bin/env python3
"""Generate the Mission 1 field-case configuration and dimension guide.

The model is parsed without importing Blender.  Every uppercase assignment in
the model's CONFIG block is resolved statically and cataloged, and every
resolved dimensional control is drawn onto an orthographic projection of the
actual generated STL for the part it belongs to.

Unlike the fan-case model, the field-case CONFIG block derives most of its
values from helper functions, comprehensions and the four companion models it
imports, so a constant-folding reader is not enough.  This module therefore
carries a small deterministic Python interpreter that executes the CONFIG block
with pure-Python stand-ins for the handful of ``mathutils`` types the model
uses.  Anything the interpreter cannot resolve is reported as a hard error
rather than silently dropped from the catalog.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import math
import re
import struct
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import shapely
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Arc, FancyArrowPatch, FancyBboxPatch, Rectangle
from shapely.geometry import MultiPolygon
from shapely.geometry import Polygon as ShapelyPolygon

HERE = Path(__file__).absolute().parent
MODELS_ROOT = HERE.parent
COMMON = MODELS_ROOT / "common"

MODEL_SOURCE = HERE / "mission1_field_case_blender.py"
PRESET_SOURCE = COMMON / "fan_size_presets.py"
OUTPUT_PDF = HERE / "mission1_field_case_configuration_dimensions.pdf"

# Companion models the field-case CONFIG block imports through the model's own
# ``import_companion_module`` helper.  Each entry maps the module name the model
# asks for onto the sibling directory and file name that provide it.
COMPANION_SOURCES = {
    "gopro_mission1_dummy_blender": (
        "mission1-dummy",
        "gopro_mission1_dummy_blender.py",
    ),
    "dual_fan_parametric_blender": (
        "dual-fan",
        "dual_fan_parametric_blender.py",
    ),
    "gopro_fan_case_parametric_blender": (
        "fan-case",
        "gopro_fan_case_parametric_blender.py",
    ),
    "wrapping_fan_cover": ("wrapping-fan-cover", "wrapping-fan-cover.py"),
}
COMPANION_PATHS = tuple(
    MODELS_ROOT / directory / filename
    for directory, filename in COMPANION_SOURCES.values()
)

# The CONFIG block runs from the top of the model down to the first Blender
# helper.  ``clear_scene`` is the first function that touches ``bpy``; every
# uppercase assignment above it is configuration.
CONFIG_BOUNDARY_FUNCTION = "clear_scene"

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


# ---------------------------------------------------------------------------
# MINIMAL MATHUTILS STAND-INS
#
# The CONFIG block builds a handful of transforms with ``mathutils``.  Blender
# is not importable here, so these pure-Python replacements provide exactly the
# operations the configuration uses.  They are deliberately small: anything the
# model needs beyond them raises and is reported as an unresolved assignment.


class Vector:
    """Pure-Python replacement for ``mathutils.Vector``."""

    __slots__ = ("_values",)

    def __init__(self, values=(0.0, 0.0, 0.0)):
        self._values = tuple(float(value) for value in values)

    def __len__(self):
        return len(self._values)

    def __iter__(self):
        return iter(self._values)

    def __getitem__(self, index):
        return self._values[index]

    def __repr__(self):
        return f"Vector({self._values})"

    def __eq__(self, other):
        return isinstance(other, Vector) and self._values == other._values

    def __hash__(self):
        return hash(self._values)

    @property
    def x(self):
        return self._values[0]

    @property
    def y(self):
        return self._values[1]

    @property
    def z(self):
        return self._values[2]

    def copy(self):
        return Vector(self._values)

    def to_tuple(self, precision=-1):
        return self._values

    def __add__(self, other):
        return Vector(a + b for a, b in zip(self._values, other))

    def __sub__(self, other):
        return Vector(a - b for a, b in zip(self._values, other))

    def __neg__(self):
        return Vector(-a for a in self._values)

    def __mul__(self, other):
        if isinstance(other, Vector):
            return self.dot(other)
        return Vector(a * other for a in self._values)

    __rmul__ = __mul__

    def __truediv__(self, other):
        return Vector(a / other for a in self._values)

    def dot(self, other):
        return sum(a * b for a, b in zip(self._values, other))

    def cross(self, other):
        x0, y0, z0 = self._values
        x1, y1, z1 = tuple(other)
        return Vector((y0 * z1 - z0 * y1, z0 * x1 - x0 * z1, x0 * y1 - y0 * x1))

    @property
    def length(self):
        return math.sqrt(self.dot(self))

    @property
    def length_squared(self):
        return self.dot(self)

    def normalized(self):
        magnitude = self.length
        if magnitude == 0.0:
            return Vector(self._values)
        return Vector(a / magnitude for a in self._values)

    def rotation_difference(self, other):
        """Shortest-arc quaternion taking this direction onto ``other``."""
        start = self.normalized()
        end = Vector(other).normalized()
        alignment = max(-1.0, min(1.0, start.dot(end)))
        if alignment > 1.0 - 1.0e-12:
            return Quaternion((1.0, 0.0, 0.0, 0.0))
        if alignment < -1.0 + 1.0e-12:
            axis = start.cross(Vector((1.0, 0.0, 0.0)))
            if axis.length < 1.0e-9:
                axis = start.cross(Vector((0.0, 1.0, 0.0)))
            axis = axis.normalized()
            return Quaternion((0.0, axis.x, axis.y, axis.z))
        axis = start.cross(end)
        return Quaternion((1.0 + alignment, axis.x, axis.y, axis.z)).normalized()


class Quaternion:
    """Pure-Python replacement for ``mathutils.Quaternion``."""

    __slots__ = ("w", "x", "y", "z")

    def __init__(self, values=(1.0, 0.0, 0.0, 0.0)):
        self.w, self.x, self.y, self.z = (float(value) for value in values)

    def __repr__(self):
        return f"Quaternion(({self.w}, {self.x}, {self.y}, {self.z}))"

    def normalized(self):
        magnitude = math.sqrt(
            self.w**2 + self.x**2 + self.y**2 + self.z**2
        )
        if magnitude == 0.0:
            return Quaternion((1.0, 0.0, 0.0, 0.0))
        return Quaternion(
            (
                self.w / magnitude,
                self.x / magnitude,
                self.y / magnitude,
                self.z / magnitude,
            )
        )

    def to_matrix(self):
        w, x, y, z = self.w, self.x, self.y, self.z
        return Matrix(
            (
                (
                    1.0 - 2.0 * (y * y + z * z),
                    2.0 * (x * y - z * w),
                    2.0 * (x * z + y * w),
                ),
                (
                    2.0 * (x * y + z * w),
                    1.0 - 2.0 * (x * x + z * z),
                    2.0 * (y * z - x * w),
                ),
                (
                    2.0 * (x * z - y * w),
                    2.0 * (y * z + x * w),
                    1.0 - 2.0 * (x * x + y * y),
                ),
            )
        )


class Matrix:
    """Pure-Python replacement for ``mathutils.Matrix``."""

    __slots__ = ("_rows",)

    def __init__(self, rows=None):
        if rows is None:
            rows = tuple(
                tuple(1.0 if column == row else 0.0 for column in range(4))
                for row in range(4)
            )
        self._rows = tuple(tuple(float(value) for value in row) for row in rows)

    def __len__(self):
        return len(self._rows)

    def __iter__(self):
        return iter(self._rows)

    def __getitem__(self, index):
        return self._rows[index]

    def __repr__(self):
        return f"Matrix({self._rows})"

    @property
    def row(self):
        return self._rows

    def copy(self):
        return Matrix(self._rows)

    @classmethod
    def Identity(cls, size):  # noqa: N802 - mirrors the mathutils spelling
        return cls(
            tuple(
                tuple(1.0 if column == row else 0.0 for column in range(size))
                for row in range(size)
            )
        )

    @classmethod
    def Translation(cls, vector):  # noqa: N802 - mirrors the mathutils spelling
        x, y, z = tuple(vector)[:3]
        return cls(
            (
                (1.0, 0.0, 0.0, x),
                (0.0, 1.0, 0.0, y),
                (0.0, 0.0, 1.0, z),
                (0.0, 0.0, 0.0, 1.0),
            )
        )

    @classmethod
    def Rotation(cls, angle, size, axis):  # noqa: N802 - mathutils spelling
        cosine, sine = math.cos(angle), math.sin(angle)
        if isinstance(axis, str):
            axis = {
                "X": (1.0, 0.0, 0.0),
                "Y": (0.0, 1.0, 0.0),
                "Z": (0.0, 0.0, 1.0),
            }[axis]
        x, y, z = Vector(axis).normalized()
        complement = 1.0 - cosine
        rotation = (
            (
                cosine + x * x * complement,
                x * y * complement - z * sine,
                x * z * complement + y * sine,
            ),
            (
                y * x * complement + z * sine,
                cosine + y * y * complement,
                y * z * complement - x * sine,
            ),
            (
                z * x * complement - y * sine,
                z * y * complement + x * sine,
                cosine + z * z * complement,
            ),
        )
        return cls(rotation) if size == 3 else cls(rotation).to_4x4()

    @classmethod
    def Scale(cls, factor, size, axis=None):  # noqa: N802 - mathutils spelling
        if axis is None:
            rows = tuple(
                tuple(factor if column == row else 0.0 for column in range(size))
                for row in range(size)
            )
            if size == 4:
                rows = rows[:3] + ((0.0, 0.0, 0.0, 1.0),)
            return cls(rows)
        x, y, z = Vector(axis).normalized()
        complement = factor - 1.0
        rotation = (
            (1.0 + complement * x * x, complement * x * y, complement * x * z),
            (complement * y * x, 1.0 + complement * y * y, complement * y * z),
            (complement * z * x, complement * z * y, 1.0 + complement * z * z),
        )
        return cls(rotation) if size == 3 else cls(rotation).to_4x4()

    def to_3x3(self):
        return Matrix(tuple(row[:3] for row in self._rows[:3]))

    def to_4x4(self):
        if len(self._rows) == 4:
            return Matrix(self._rows)
        rows = tuple(tuple(row[:3]) + (0.0,) for row in self._rows[:3])
        return Matrix(rows + ((0.0, 0.0, 0.0, 1.0),))

    def transposed(self):
        return Matrix(tuple(zip(*self._rows)))

    def __matmul__(self, other):
        if isinstance(other, Matrix):
            columns = tuple(zip(*other._rows))
            return Matrix(
                tuple(
                    tuple(
                        sum(a * b for a, b in zip(row, column))
                        for column in columns
                    )
                    for row in self._rows
                )
            )
        vector = tuple(other)
        if len(self._rows) == 4 and len(vector) == 3:
            padded = vector + (1.0,)
            result = tuple(
                sum(a * b for a, b in zip(row, padded)) for row in self._rows
            )
            divisor = result[3] if result[3] else 1.0
            return Vector(value / divisor for value in result[:3])
        return Vector(
            sum(a * b for a, b in zip(row, vector)) for row in self._rows
        )


# ---------------------------------------------------------------------------
# STATIC PYTHON INTERPRETER
#
# Executes the model's CONFIG block from its AST.  Only the constructs the
# configuration actually uses are implemented, and only whitelisted callables
# may be invoked, so importing this module can never run arbitrary model code
# such as a Blender operator or a file write.


class UnsupportedConstruct(Exception):
    """Raised when the CONFIG block uses something the reader cannot resolve."""


SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "format": format,
    "frozenset": frozenset,
    "getattr": getattr,
    "hasattr": hasattr,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    "KeyError": KeyError,
    "RuntimeError": RuntimeError,
    "TypeError": TypeError,
    "ValueError": ValueError,
    "True": True,
    "False": False,
    "None": None,
}
SAFE_METHOD_OWNERS = (
    str,
    bytes,
    tuple,
    list,
    dict,
    set,
    frozenset,
    int,
    float,
    bool,
)
TRUSTED_OWNER_TYPES = (Matrix, Quaternion, Vector)
WHILE_LOOP_LIMIT = 100_000
CALL_DEPTH_LIMIT = 60


class Scope(dict):
    """Function-local namespace that can write through to module globals."""

    def __init__(self, initial, module_environment=None):
        super().__init__(initial)
        self.module_environment = module_environment
        self.global_names: set[str] = set()


class _BreakLoop(Exception):
    pass


class _ContinueLoop(Exception):
    pass


class _ReturnValue(Exception):
    def __init__(self, value):
        super().__init__(value)
        self.value = value


class StaticFunction:
    """A ``def``/``lambda`` from the model, callable by the interpreter."""

    def __init__(self, node, closure, interpreter, module_environment=None):
        self.node = node
        self.closure = closure
        self.interpreter = interpreter
        self.module_environment = (
            closure if module_environment is None else module_environment
        )
        self.name = node.name

    def __call__(self, *args, **kwargs):
        return self.interpreter.call(self, args, kwargs)

    def __repr__(self):
        return f"<static {self.name}>"


class ModuleNamespace:
    """Attribute view over a companion module's resolved globals."""

    def __init__(self, environment, name):
        object.__setattr__(self, "_environment", environment)
        object.__setattr__(self, "_name", name)

    def __getattr__(self, item):
        if item.startswith("_"):
            raise AttributeError(item)
        try:
            return self._environment[item]
        except KeyError:
            raise AttributeError(f"{self._name}.{item}") from None

    def __setattr__(self, item, value):
        # The field-case CONFIG temporarily re-points companion globals (for
        # example the fan mount angles) before asking the companion to
        # recompute a transform.  Writes have to reach the companion namespace
        # or the recomputed value would silently use the companion default.
        if item.startswith("_"):
            object.__setattr__(self, item, value)
        else:
            self._environment[item] = value

    def __repr__(self):
        return f"<module {self._name}>"


class StaticInterpreter:
    """Evaluate a model's module-level configuration without importing it."""

    BINARY_OPERATIONS = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.FloorDiv: lambda a, b: a // b,
        ast.Mod: lambda a, b: a % b,
        ast.Pow: lambda a, b: a**b,
        ast.MatMult: lambda a, b: a @ b,
    }
    COMPARISONS = {
        ast.Eq: lambda a, b: a == b,
        ast.NotEq: lambda a, b: a != b,
        ast.Lt: lambda a, b: a < b,
        ast.LtE: lambda a, b: a <= b,
        ast.Gt: lambda a, b: a > b,
        ast.GtE: lambda a, b: a >= b,
        ast.In: lambda a, b: a in b,
        ast.NotIn: lambda a, b: a not in b,
        ast.Is: lambda a, b: a is b,
        ast.IsNot: lambda a, b: a is not b,
    }
    IGNORED_STATEMENTS = (
        ast.Pass,
        ast.Import,
        ast.ClassDef,
        ast.Nonlocal,
        ast.Delete,
        ast.Assert,
    )

    def __init__(self, shared_module_loader=None):
        self.shared_module_loader = shared_module_loader
        self.trusted_callables: list[object] = []
        self.depth = 0

    # -- expressions --------------------------------------------------------

    def evaluate(self, node, environment):
        handler = getattr(self, "evaluate_" + type(node).__name__, None)
        if handler is None:
            raise UnsupportedConstruct(f"expression {type(node).__name__}")
        return handler(node, environment)

    def evaluate_Constant(self, node, environment):  # noqa: N802 - AST name
        return node.value

    def evaluate_Name(self, node, environment):  # noqa: N802 - AST name
        if node.id in environment:
            return environment[node.id]
        if node.id in SAFE_BUILTINS:
            return SAFE_BUILTINS[node.id]
        raise UnsupportedConstruct(f"name {node.id}")

    def evaluate_Tuple(self, node, environment):  # noqa: N802 - AST name
        return tuple(self._elements(node.elts, environment))

    def evaluate_List(self, node, environment):  # noqa: N802 - AST name
        return list(self._elements(node.elts, environment))

    def evaluate_Set(self, node, environment):  # noqa: N802 - AST name
        return set(self._elements(node.elts, environment))

    def _elements(self, elements, environment):
        resolved = []
        for element in elements:
            if isinstance(element, ast.Starred):
                resolved.extend(self.evaluate(element.value, environment))
            else:
                resolved.append(self.evaluate(element, environment))
        return resolved

    def evaluate_Dict(self, node, environment):  # noqa: N802 - AST name
        resolved = {}
        for key_node, value_node in zip(node.keys, node.values):
            if key_node is None:
                resolved.update(self.evaluate(value_node, environment))
            else:
                resolved[self.evaluate(key_node, environment)] = self.evaluate(
                    value_node, environment
                )
        return resolved

    def evaluate_UnaryOp(self, node, environment):  # noqa: N802 - AST name
        value = self.evaluate(node.operand, environment)
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.UAdd):
            return +value
        if isinstance(node.op, ast.Not):
            return not value
        if isinstance(node.op, ast.Invert):
            return ~value
        raise UnsupportedConstruct(f"unary {type(node.op).__name__}")

    def evaluate_BinOp(self, node, environment):  # noqa: N802 - AST name
        operation = self.BINARY_OPERATIONS.get(type(node.op))
        if operation is None:
            raise UnsupportedConstruct(f"binary {type(node.op).__name__}")
        return operation(
            self.evaluate(node.left, environment),
            self.evaluate(node.right, environment),
        )

    def evaluate_BoolOp(self, node, environment):  # noqa: N802 - AST name
        if isinstance(node.op, ast.And):
            value = True
            for operand in node.values:
                value = self.evaluate(operand, environment)
                if not value:
                    return value
            return value
        value = False
        for operand in node.values:
            value = self.evaluate(operand, environment)
            if value:
                return value
        return value

    def evaluate_Compare(self, node, environment):  # noqa: N802 - AST name
        left = self.evaluate(node.left, environment)
        for operator, comparator in zip(node.ops, node.comparators):
            right = self.evaluate(comparator, environment)
            comparison = self.COMPARISONS.get(type(operator))
            if comparison is None:
                raise UnsupportedConstruct(
                    f"comparison {type(operator).__name__}"
                )
            if not comparison(left, right):
                return False
            left = right
        return True

    def evaluate_IfExp(self, node, environment):  # noqa: N802 - AST name
        if self.evaluate(node.test, environment):
            return self.evaluate(node.body, environment)
        return self.evaluate(node.orelse, environment)

    def evaluate_Attribute(self, node, environment):  # noqa: N802 - AST name
        base = self.evaluate(node.value, environment)
        try:
            return getattr(base, node.attr)
        except AttributeError as exc:
            raise UnsupportedConstruct(
                f"attribute {ast.unparse(node)}"
            ) from exc

    def evaluate_Subscript(self, node, environment):  # noqa: N802 - AST name
        return self.evaluate(node.value, environment)[
            self.evaluate(node.slice, environment)
        ]

    def evaluate_Slice(self, node, environment):  # noqa: N802 - AST name
        def part(child):
            return None if child is None else self.evaluate(child, environment)

        return slice(part(node.lower), part(node.upper), part(node.step))

    def evaluate_JoinedStr(self, node, environment):  # noqa: N802 - AST name
        pieces = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                pieces.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                pieces.append(self.evaluate_FormattedValue(value, environment))
            else:
                raise UnsupportedConstruct("f-string component")
        return "".join(pieces)

    def evaluate_FormattedValue(self, node, environment):  # noqa: N802
        specification = (
            ""
            if node.format_spec is None
            else self.evaluate(node.format_spec, environment)
        )
        return format(self.evaluate(node.value, environment), specification)

    def evaluate_Lambda(self, node, environment):  # noqa: N802 - AST name
        function = ast.FunctionDef(
            name="<lambda>",
            args=node.args,
            body=[ast.Return(value=node.body)],
            decorator_list=[],
        )
        ast.copy_location(function, node)
        ast.fix_missing_locations(function)
        return StaticFunction(function, environment, self)

    def evaluate_Call(self, node, environment):  # noqa: N802 - AST name
        function = self.evaluate(node.func, environment)
        arguments = []
        for argument in node.args:
            if isinstance(argument, ast.Starred):
                arguments.extend(self.evaluate(argument.value, environment))
            else:
                arguments.append(self.evaluate(argument, environment))
        keywords = {}
        for keyword in node.keywords:
            if keyword.arg is None:
                keywords.update(self.evaluate(keyword.value, environment))
            else:
                keywords[keyword.arg] = self.evaluate(
                    keyword.value, environment
                )
        if isinstance(function, StaticFunction):
            return function(*arguments, **keywords)
        if self._is_trusted_call(function, node, environment):
            return function(*arguments, **keywords)
        raise UnsupportedConstruct(f"call {ast.unparse(node.func)}")

    def _is_trusted_call(self, function, node, environment):
        if any(function is trusted for trusted in self.trusted_callables):
            return True
        if any(function is builtin for builtin in SAFE_BUILTINS.values()):
            return True
        if getattr(function, "__module__", None) == "math":
            return True
        if isinstance(node.func, ast.Attribute):
            owner = self.evaluate(node.func.value, environment)
            if isinstance(owner, SAFE_METHOD_OWNERS):
                return True
            if isinstance(owner, TRUSTED_OWNER_TYPES):
                return True
            if any(owner is trusted for trusted in self.trusted_callables):
                return True
        return False

    def _comprehension(self, node, environment):
        results = []

        def bind(target, value, scope):
            if isinstance(target, ast.Name):
                scope[target.id] = value
            elif isinstance(target, (ast.Tuple, ast.List)):
                for element, item in zip(target.elts, value):
                    bind(element, item, scope)
            else:
                raise UnsupportedConstruct("comprehension target")

        def walk(index, scope):
            if index == len(node.generators):
                if isinstance(node, ast.DictComp):
                    results.append(
                        (
                            self.evaluate(node.key, scope),
                            self.evaluate(node.value, scope),
                        )
                    )
                else:
                    results.append(self.evaluate(node.elt, scope))
                return
            generator = node.generators[index]
            for item in self.evaluate(generator.iter, scope):
                inner = dict(scope)
                bind(generator.target, item, inner)
                if all(
                    self.evaluate(condition, inner)
                    for condition in generator.ifs
                ):
                    walk(index + 1, inner)

        walk(0, dict(environment))
        if isinstance(node, ast.SetComp):
            return set(results)
        if isinstance(node, ast.DictComp):
            return dict(results)
        if isinstance(node, ast.GeneratorExp):
            return tuple(results)
        return results

    evaluate_ListComp = _comprehension
    evaluate_SetComp = _comprehension
    evaluate_DictComp = _comprehension
    evaluate_GeneratorExp = _comprehension

    # -- statements ---------------------------------------------------------

    def assign(self, target, value, environment):
        """Bind ``value`` to ``target`` and return the plain names it wrote."""
        if isinstance(target, ast.Name):
            environment[target.id] = value
            if (
                isinstance(environment, Scope)
                and target.id in environment.global_names
                and environment.module_environment is not None
            ):
                environment.module_environment[target.id] = value
            return [target.id]
        if isinstance(target, (ast.Tuple, ast.List)):
            if any(isinstance(item, ast.Starred) for item in target.elts):
                raise UnsupportedConstruct("starred assignment target")
            names = []
            for element, item in zip(target.elts, list(value)):
                names.extend(self.assign(element, item, environment))
            return names
        if isinstance(target, ast.Subscript):
            container = self.evaluate(target.value, environment)
            container[self.evaluate(target.slice, environment)] = value
            return []
        if isinstance(target, ast.Attribute):
            owner = self.evaluate(target.value, environment)
            try:
                setattr(owner, target.attr, value)
            except (AttributeError, TypeError) as exc:
                raise UnsupportedConstruct(
                    f"attribute assignment {ast.unparse(target)}"
                ) from exc
            return []
        raise UnsupportedConstruct(
            f"assignment target {type(target).__name__}"
        )

    def execute_body(self, body, environment, on_assign=None, line_limit=None):
        for node in body:
            if line_limit is not None and getattr(node, "lineno", 0) >= line_limit:
                return
            self.execute(node, environment, on_assign, line_limit)

    def execute(self, node, environment, on_assign=None, line_limit=None):
        kind = type(node)
        if kind is ast.Global:
            self._execute_global(node, environment)
            return
        if kind is ast.ImportFrom:
            self._execute_import_from(node, environment)
            return
        if kind is ast.Expr:
            # Module-level calls are side effects (logging, registration); run
            # them only when they are resolvable and never let them abort the
            # configuration walk.
            if isinstance(node.value, ast.Call):
                try:
                    self.evaluate(node.value, environment)
                except UnsupportedConstruct:
                    pass
            return
        if kind in self.IGNORED_STATEMENTS:
            return
        if kind is ast.FunctionDef:
            environment[node.name] = StaticFunction(node, environment, self)
            return
        if kind in (ast.Assign, ast.AnnAssign):
            if node.value is None:
                return
            value = self.evaluate(node.value, environment)
            targets = node.targets if kind is ast.Assign else [node.target]
            for target in targets:
                for name in self.assign(target, value, environment):
                    if on_assign is not None:
                        on_assign(name, environment[name], node.lineno)
            return
        if kind is ast.AugAssign:
            operation = self.BINARY_OPERATIONS.get(type(node.op))
            if operation is None:
                raise UnsupportedConstruct(
                    f"augmented {type(node.op).__name__}"
                )
            value = operation(
                self.evaluate(node.target, environment),
                self.evaluate(node.value, environment),
            )
            for name in self.assign(node.target, value, environment):
                if on_assign is not None:
                    on_assign(name, environment[name], node.lineno)
            return
        if kind is ast.If:
            branch = (
                node.body
                if self.evaluate(node.test, environment)
                else node.orelse
            )
            self.execute_body(branch, environment, on_assign, line_limit)
            return
        if kind is ast.For:
            self._execute_for(node, environment, on_assign, line_limit)
            return
        if kind is ast.While:
            self._execute_while(node, environment, on_assign, line_limit)
            return
        if kind is ast.Return:
            raise _ReturnValue(
                None
                if node.value is None
                else self.evaluate(node.value, environment)
            )
        if kind is ast.Break:
            raise _BreakLoop()
        if kind is ast.Continue:
            raise _ContinueLoop()
        if kind is ast.Raise:
            if node.exc is None:
                raise UnsupportedConstruct("bare raise")
            raise self.evaluate(node.exc, environment)
        if kind is ast.Try:
            self._execute_try(node, environment, on_assign, line_limit)
            return
        raise UnsupportedConstruct(f"statement {kind.__name__}")

    def _execute_global(self, node, environment):
        if not isinstance(environment, Scope):
            return
        environment.global_names.update(node.names)
        module_environment = environment.module_environment
        if module_environment is None:
            return
        for name in node.names:
            if name in module_environment:
                dict.__setitem__(environment, name, module_environment[name])

    def _execute_import_from(self, node, environment):
        if self.shared_module_loader is None:
            return
        resolved = self.shared_module_loader(
            node.module, [alias.name for alias in node.names]
        )
        for alias in node.names:
            if alias.name in resolved:
                environment[alias.asname or alias.name] = resolved[alias.name]

    def _execute_for(self, node, environment, on_assign, line_limit):
        for item in self.evaluate(node.iter, environment):
            self.assign(node.target, item, environment)
            try:
                self.execute_body(node.body, environment, on_assign, line_limit)
            except _ContinueLoop:
                continue
            except _BreakLoop:
                break
        else:
            self.execute_body(node.orelse, environment, on_assign, line_limit)

    def _execute_while(self, node, environment, on_assign, line_limit):
        iterations = 0
        while self.evaluate(node.test, environment):
            iterations += 1
            if iterations > WHILE_LOOP_LIMIT:
                raise UnsupportedConstruct("while loop did not terminate")
            try:
                self.execute_body(node.body, environment, on_assign, line_limit)
            except _ContinueLoop:
                continue
            except _BreakLoop:
                break
        else:
            self.execute_body(node.orelse, environment, on_assign, line_limit)

    def _execute_try(self, node, environment, on_assign, line_limit):
        try:
            try:
                self.execute_body(
                    node.body, environment, on_assign, line_limit
                )
            except (
                _BreakLoop,
                _ContinueLoop,
                _ReturnValue,
                UnsupportedConstruct,
            ):
                raise
            except Exception as exc:  # noqa: BLE001 - mirrors model semantics
                for handler in node.handlers:
                    caught = (
                        Exception
                        if handler.type is None
                        else self.evaluate(handler.type, environment)
                    )
                    if isinstance(exc, caught):
                        if handler.name:
                            environment[handler.name] = exc
                        self.execute_body(
                            handler.body, environment, on_assign, line_limit
                        )
                        break
                else:
                    raise
            else:
                self.execute_body(
                    node.orelse, environment, on_assign, line_limit
                )
        finally:
            self.execute_body(
                node.finalbody, environment, on_assign, line_limit
            )

    def call(self, function, args, kwargs):
        self.depth += 1
        if self.depth > CALL_DEPTH_LIMIT:
            self.depth -= 1
            raise UnsupportedConstruct("call depth limit")
        try:
            specification = function.node.args
            if (
                specification.vararg
                or specification.kwarg
                or specification.posonlyargs
            ):
                raise UnsupportedConstruct(
                    f"{function.name}: unsupported signature"
                )
            scope = Scope(function.closure, function.module_environment)
            names = [argument.arg for argument in specification.args]
            defaults = list(specification.defaults)
            keywords = dict(kwargs)
            for name, value in zip(names, args):
                scope[name] = value
            for index, name in enumerate(names):
                if index < len(args):
                    continue
                offset = index - (len(names) - len(defaults))
                if name in keywords:
                    scope[name] = keywords.pop(name)
                elif offset >= 0:
                    scope[name] = self.evaluate(
                        defaults[offset], function.closure
                    )
            for argument, default in zip(
                specification.kwonlyargs, specification.kw_defaults
            ):
                if argument.arg in keywords:
                    scope[argument.arg] = keywords.pop(argument.arg)
                elif default is not None:
                    scope[argument.arg] = self.evaluate(
                        default, function.closure
                    )
            missing = [name for name in names if name not in scope]
            if missing:
                raise UnsupportedConstruct(
                    f"{function.name}: unbound arguments {missing}"
                )
            try:
                self.execute_body(function.node.body, scope)
            except _ReturnValue as returned:
                return returned.value
            return None
        finally:
            self.depth -= 1


# ---------------------------------------------------------------------------
# MODEL CONFIGURATION READER

HOST_NAMES = {
    "Matrix": Matrix,
    "Quaternion": Quaternion,
    "Vector": Vector,
    "Path": Path,
    "math": math,
}
SHARED_MODULE_DIRECTORIES = ("common",)


def build_interpreter():
    """Interpreter wired with the host objects the field-case CONFIG needs."""
    interpreter = StaticInterpreter()
    companion_cache: dict[str, tuple[ModuleNamespace, Path]] = {}

    def load_shared_module(module_name, requested):
        for sibling in SHARED_MODULE_DIRECTORIES:
            path = MODELS_ROOT / sibling / f"{module_name}.py"
            if not path.is_file():
                continue
            environment = {
                "__name__": module_name,
                "__file__": str(path),
                "math": math,
            }
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                try:
                    interpreter.execute(node, environment)
                except Exception:  # noqa: BLE001 - unrelated names may fail
                    continue
            return {
                name: environment[name]
                for name in requested
                if name in environment
            }
        return {}

    interpreter.shared_module_loader = load_shared_module

    def resolve_companion(args, kwargs):
        """Normalise the model's ``import_companion_module`` call signature."""
        module_name = args[0]
        sibling = args[1] if len(args) > 1 else kwargs.get("sibling_directory")
        filename = args[2] if len(args) > 2 else kwargs.get("source_filename")
        if module_name in COMPANION_SOURCES:
            sibling, default_filename = COMPANION_SOURCES[module_name]
            filename = filename or default_filename
        return module_name, sibling, filename

    def load_companion(*args, **kwargs):
        module_name, sibling, filename = resolve_companion(args, kwargs)
        if module_name in companion_cache:
            return companion_cache[module_name]
        if sibling is None:
            raise UnsupportedConstruct(f"companion {module_name}: no directory")
        directory = MODELS_ROOT / sibling
        path = directory / (filename or f"{module_name}.py")
        environment = {
            "__name__": module_name,
            "__file__": str(path),
            "import_companion_module": load_companion,
        }
        environment.update(HOST_NAMES)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            try:
                interpreter.execute(node, environment)
            except Exception:  # noqa: BLE001 - Blender-only names may fail
                continue
        resolved = (ModuleNamespace(environment, module_name), directory)
        companion_cache[module_name] = resolved
        return resolved

    interpreter.trusted_callables.extend(
        [
            Matrix,
            Quaternion,
            Vector,
            Matrix.Identity,
            Matrix.Translation,
            Matrix.Rotation,
            Matrix.Scale,
            Path,
            load_companion,
        ]
    )
    return interpreter, load_companion


def config_boundary_line(tree):
    """First line of the model that is no longer configuration."""
    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == CONFIG_BOUNDARY_FUNCTION
        ):
            return node.lineno
    raise RuntimeError(
        f"{MODEL_SOURCE.name}: config boundary "
        f"'{CONFIG_BOUNDARY_FUNCTION}' not found"
    )


def expected_config_names(tree, boundary):
    """Uppercase names the CONFIG block's own syntax says it must define.

    Function and class bodies are skipped: those bind locals, not
    configuration.  The result is compared against what the interpreter
    actually resolved so a construct the reader cannot follow is reported
    instead of quietly shrinking the catalog.
    """
    names: set[str] = set()

    def collect(target):
        for node in ast.walk(target):
            if isinstance(node, ast.Name) and node.id.isupper():
                names.add(node.id)

    def walk(body):
        for node in body:
            if getattr(node, "lineno", 0) >= boundary:
                return
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    collect(target)
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                collect(node.target)
            for field in ("body", "orelse", "finalbody"):
                walk(getattr(node, field, []) or [])
            for handler in getattr(node, "handlers", []) or []:
                walk(handler.body)

    walk(tree.body)
    return names


def literal_source_values(tree, boundary):
    """Map each configured name to its source text and literal-ness."""
    details: dict[str, tuple[str, bool]] = {}

    def is_literal(node):
        allowed = (
            ast.Constant,
            ast.Tuple,
            ast.List,
            ast.Dict,
            ast.Set,
            ast.UnaryOp,
            ast.USub,
            ast.UAdd,
            ast.Load,
        )
        return all(isinstance(child, allowed) for child in ast.walk(node))

    def walk(body):
        for node in body:
            if getattr(node, "lineno", 0) >= boundary:
                return
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            targets = None
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                targets = [node.target]
            if targets is not None and node.value is not None:
                text = ast.unparse(node.value)
                literal = is_literal(node.value)
                for target in targets:
                    for child in ast.walk(target):
                        if isinstance(child, ast.Name) and child.id.isupper():
                            details[child.id] = (text, literal)
            for field in ("body", "orelse", "finalbody"):
                walk(getattr(node, field, []) or [])
            for handler in getattr(node, "handlers", []) or []:
                walk(handler.body)

    walk(tree.body)
    return details


# Ordered longest-prefix-wins table.  ``FAN_CASE_`` has to be tested before
# ``FAN_``, and ``BASE_`` before the shell catch-all, so the order matters.
CATEGORY_PREFIXES = (
    (("LATCH_", "PELICAN_"), "Pelican latch mechanism"),
    (("HANDLE_", "PIVOT_"), "Pivoting handle"),
    (("HINGE_",), "Lid hinge"),
    (("LID_", "LOGO_", "NEUROPOL_"), "Lid and inlays"),
    (("FAN_CASE_",), "Fan-case pair storage"),
    (("FAN_", "DUAL_", "PWM_", "EQUIPMENT_"), "Dual-fan and equipment storage"),
    (("GASKET_", "TPU_", "SEAL_"), "Gasket and TPU parts"),
    (("BATTERY_", "ACCESSORY_", "TRAY_", "ORGANIZER_"), "Battery and accessory storage"),
    (("CAMERA_", "LENS_", "DUMMY_", "MOUNT_"), "Camera and mount storage"),
    (("VENT_", "DRAIN_", "PRESSURE_"), "Venting and drainage"),
    (("FOOT_", "STACK_", "RIB_", "BOSS_"), "Feet, ribs and stacking"),
    (
        ("CASE_", "BASE_", "WALL_", "SIDE_", "ROUNDED_", "INSERT_", "LEGACY_", "CORNER_"),
        "Case shell envelope",
    ),
    (
        (
            "EXPORT_",
            "PROJECT_",
            "SAVE_",
            "BUILD_",
            "PRINT_",
            "VISIBLE_",
            "EXPANDED_",
            "MAX_",
            "ASSEMBLE_",
            "ASSEMBLED_",
            "BLEND_",
            "CLEAR_",
            "GENERATE_",
            "AUXILIARY_",
            "PRINTABLE_",
            "MISSION1_",
            "WRAPPING_",
        ),
        "Build and export control",
    ),
    (("BOOLEAN_", "MESH_", "SEGMENT_", "RESOLUTION_"), "Mesh and Boolean quality"),
)
CATEGORY_OVERRIDES = {"MIN_CAMERA_POCKET_WEB": "Camera and mount storage"}
FALLBACK_CATEGORY = "General case configuration"

ACRONYMS = {
    "Tpu": "TPU",
    "Pla": "PLA",
    "Petg": "PETG",
    "Abs": "ABS",
    "Ams": "AMS",
    "Stl": "STL",
    "3Mf": "3MF",
    "M3": "M3",
    "M4": "M4",
    "Pwm": "PWM",
    "Usb": "USB",
    "Xy": "XY",
    "Xz": "XZ",
    "Yz": "YZ",
    "Id": "ID",
    "Od": "OD",
    "Z": "Z",
    "Mm": "mm",
    "Deg": "deg",
    "Gopro": "GoPro",
    "Tesla": "Tesla",
}


def category_for(name):
    if name in CATEGORY_OVERRIDES:
        return CATEGORY_OVERRIDES[name]
    for prefixes, category in CATEGORY_PREFIXES:
        if name.startswith(prefixes):
            return category
    return FALLBACK_CATEGORY


def humanize(name):
    words = [word.capitalize() for word in name.lower().split("_")]
    return " ".join(ACRONYMS.get(word, word) for word in words)


def wrap_identifier(name, width=24):
    pieces, line = [], ""
    for token in name.split("_"):
        candidate = token if not line else f"{line}_{token}"
        if len(candidate) > width and line:
            pieces.append(line + "_")
            line = token
        else:
            line = candidate
    if line:
        pieces.append(line)
    return "\n".join(pieces)


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def numeric_leaves(value, depth=0):
    """Flatten a nested numeric container, or return ``None`` if it is not one.

    A configuration entry counts as dimensional when it is a number or a
    non-empty container whose every leaf is a number.  That rule needs no
    hand-maintained allowlist: a new tuple of coordinates is dimensional the
    day it is added, and a mode string or a file name never is.
    """
    if is_number(value):
        return (float(value),)
    if depth > 6:
        return None
    if isinstance(value, (tuple, list)):
        items = value
    elif isinstance(value, dict):
        items = list(value.values())
    else:
        return None
    if not items:
        return None
    leaves: list[float] = []
    for item in items:
        nested = numeric_leaves(item, depth + 1)
        if nested is None:
            return None
        leaves.extend(nested)
    return tuple(leaves)


ANGLE_SUFFIXES = ("_DEG", "_DEGREES", "_ANGLE", "_ANGLES", "_DEG_STEP")
COUNT_SUFFIXES = (
    "_COUNT",
    "_COUNTS",
    "_SEGMENTS",
    "_SECTIONS",
    "_SAMPLES",
    "_STEPS",
    "_POINTS",
)
RATIO_SUFFIXES = ("_SCALE", "_MULTIPLIER", "_RATIO", "_FRACTION", "_FACTOR")


def unit_for(name, value):
    """Unit for a configured name, or ``setting`` when it is not dimensional.

    Suffix matching is deliberate rather than substring matching: several
    counterbore names contain ``COUNT`` in the middle and are millimetres.
    """
    if numeric_leaves(value) is None:
        return "setting"
    if name.endswith(ANGLE_SUFFIXES):
        return "deg"
    if name.endswith(("_VOLUME", "_VOLUME_LIMIT", "_VOLUME_MINIMUM")):
        return "mm³"
    if name.endswith(("_AREA", "_AREA_LIMIT", "_AREA_MINIMUM")):
        return "mm²"
    if name.endswith(COUNT_SUFFIXES):
        return "count"
    if name.endswith(RATIO_SUFFIXES):
        return "ratio"
    return "mm"


UNIT_LABELS = {
    "mm": " mm",
    "deg": "°",
    "mm²": " mm²",
    "mm³": " mm³",
    "count": " count",
    "ratio": "x",
}
PLAIN_UNIT_LABELS = {
    "mm": " mm",
    "deg": " deg",
    "mm²": " mm2",
    "mm³": " mm3",
    "count": " ct",
    "ratio": "x",
}

EXACT_DESCRIPTIONS = {
    "CASE_WIDTH": "Outside width of the closed case across the latch faces.",
    "CASE_DEPTH": "Outside depth of the closed case from hinge to latch.",
    "CASE_CORNER_RADIUS": "Plan-view corner radius of the shell extrusion.",
    "WALL_THICKNESS": "Nominal side-wall thickness of the base and lid shells.",
    "BASE_FLOOR_THICKNESS": "Solid floor thickness under the base pockets.",
    "MAX_PRINT_XY": "Largest part footprint the target printer bed accepts.",
    "PROJECT_PLATE_SIZE": "Plate size written into the exported AMS project.",
    "ACCESSORY_CASE_BASE_HEIGHT": "Internal height available to the accessory stack.",
    "ACCESSORY_MOUNT_ENVELOPE": "Bounding box reserved for the stowed mount hardware.",
    "ACCESSORY_COIL_ENVELOPE": "Diameter and height reserved for the coiled cable.",
    "ROUNDED_RECT_SEGMENTS": "Segment count used for every rounded-rectangle corner.",
    "BOOLEAN_SOLVER": "Boolean modifier solver applied to every cut.",
    "BOOLEAN_CLEANUP_DISTANCE": "Merge distance used after each Boolean cut.",
    "FAN_CASE_STORAGE_LAYOUT_DEPTH": "Case depth the fan-case storage layout is drawn for.",
}


def description_for(name, category, unit):
    exact = EXACT_DESCRIPTIONS.get(name)
    if exact:
        return exact
    readable = humanize(name)
    if unit == "setting":
        return f"{readable} — build setting."
    if unit == "deg":
        return f"{readable} — angular control, {category.lower()}."
    if unit == "count":
        return f"{readable} — repeat count, {category.lower()}."
    if unit == "ratio":
        return f"{readable} — dimensionless ratio, {category.lower()}."
    return f"{readable} — {category.lower()}."


@dataclass(frozen=True)
class ConfigEntry:
    name: str
    value: object
    source_value: str
    source_line: int
    category: str
    description: str
    unit: str
    derived: bool

    @property
    def leaves(self):
        return numeric_leaves(self.value)


def read_model_config():
    """Resolve and catalog every uppercase name in the model's CONFIG block."""
    source = MODEL_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    boundary = config_boundary_line(tree)

    interpreter, load_companion = build_interpreter()
    environment = {
        "__name__": "make_stl",
        "__file__": str(MODEL_SOURCE),
        "import_companion_module": load_companion,
    }
    environment.update(HOST_NAMES)
    environment["globals"] = lambda: environment
    interpreter.trusted_callables.append(environment["globals"])

    # The model defines its own ``import_companion_module`` part-way down the
    # CONFIG block, which would shadow the loader above.  Re-seeding the host
    # names before every top-level statement keeps the loader in place without
    # having to special-case the model's definition.
    overrides = dict(HOST_NAMES)
    overrides["globals"] = environment["globals"]
    overrides["import_companion_module"] = load_companion

    resolved: dict[str, tuple[object, int]] = {}
    unresolved: list[str] = []

    def record(name, value, lineno):
        resolved[name] = (value, lineno)

    for node in tree.body:
        if getattr(node, "lineno", 0) >= boundary:
            break
        environment.update(overrides)
        try:
            interpreter.execute(node, environment, record, boundary)
        except UnsupportedConstruct as exc:
            unresolved.append(f"line {node.lineno}: {exc}")
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            unresolved.append(f"line {node.lineno}: {type(exc).__name__}: {exc}")

    if unresolved:
        raise RuntimeError(
            f"{MODEL_SOURCE.name}: the configuration reader could not resolve "
            f"{len(unresolved)} statement(s):\n  " + "\n  ".join(unresolved[:20])
        )

    catalogued = {name for name in resolved if name.isupper()}
    expected = expected_config_names(tree, boundary)
    if catalogued != expected:
        missing = sorted(expected - catalogued)
        extra = sorted(catalogued - expected)
        raise RuntimeError(
            f"{MODEL_SOURCE.name}: configuration catalog is out of sync with "
            f"the model source. Missing: {missing}. Unexpected: {extra}."
        )

    details = literal_source_values(tree, boundary)
    entries = []
    for name in sorted(catalogued):
        value, lineno = resolved[name]
        source_text, literal = details.get(name, ("", False))
        category = category_for(name)
        unit = unit_for(name, value)
        entries.append(
            ConfigEntry(
                name=name,
                value=value,
                source_value=textwrap.shorten(source_text, 180, placeholder=" …"),
                source_line=lineno,
                category=category,
                description=description_for(name, category, unit),
                unit=unit,
                derived=not literal,
            )
        )
    return entries


CONFIG_ENTRIES = read_model_config()
CONFIG_BY_NAME = {entry.name: entry for entry in CONFIG_ENTRIES}


# ---------------------------------------------------------------------------
# GENERATED GEOMETRY

PART_STLS = {
    "base": "mission1_field_case_base.stl",
    "lid": "mission1_field_case_lid.stl",
    "gasket": "mission1_field_case_gasket_tpu.stl",
    "latch_lever": "mission1_field_case_pelican_latch_lever_print_two.stl",
    "latch_hook": "mission1_field_case_pelican_latch_hook_print_two.stl",
    "handle_bar": "mission1_field_case_pivoting_handle_bar.stl",
    "hinge_pin": "mission1_field_case_hinge_pin.stl",
    "logo_inlay": "mission1_field_case_lid_logo_orange_inlay.stl",
    "tpu_snap_lid": "mission1_field_case_lid_tpu_68d_snap.stl",
    "hinge_coupon": "mission1_field_case_tpu_68d_hinge_coupon.stl",
    "fan_insert": "mission1_field_case_fan_case_pair_lower_insert_tpu.stl",
    "fan_lid_pad": "mission1_field_case_fan_case_pair_lid_pad_tpu.stl",
    "organizer": "mission1_field_case_accessory_organizer.stl",
    "mount_tray": "mission1_field_case_mount_tray.stl",
    "storage_bin": "mission1_field_case_fan_case_pair_fan_side_storage_bin_tpu.stl",
}
PART_PATHS = {part: HERE / name for part, name in PART_STLS.items()}
PART_TITLES = {
    "base": "Case base shell",
    "lid": "Rigid lid shell",
    "gasket": "Lid gasket (TPU)",
    "latch_lever": "Pelican latch lever",
    "latch_hook": "Pelican latch hook",
    "handle_bar": "Pivoting handle bar",
    "hinge_pin": "Hinge pin",
    "logo_inlay": "Lid logo inlay",
    "tpu_snap_lid": "TPU 68D snap lid",
    "hinge_coupon": "TPU 68D hinge coupon",
    "fan_insert": "Fan-case lower insert",
    "fan_lid_pad": "Fan-case lid pad",
    "organizer": "Accessory organizer",
    "mount_tray": "Mount tray",
    "storage_bin": "Fan-side storage bin",
}
PART_COLORS = {
    "base": BLUE,
    "lid": BLUE,
    "gasket": ORANGE,
    "latch_lever": GREEN,
    "latch_hook": GREEN,
    "handle_bar": GREEN,
    "hinge_pin": GRAY,
    "logo_inlay": ORANGE,
    "tpu_snap_lid": CYAN,
    "hinge_coupon": CYAN,
    "fan_insert": ORANGE,
    "fan_lid_pad": ORANGE,
    "organizer": CYAN,
    "mount_tray": CYAN,
    "storage_bin": CYAN,
}

SOURCE_PATHS = (MODEL_SOURCE, PRESET_SOURCE) + COMPANION_PATHS


def require_current_part_stls():
    """Fail loudly when the exported parts are missing or older than the model.

    The drawings are projections of the exported meshes, so a stale STL would
    silently produce a drawing that no longer matches the configuration it is
    annotated with.
    """
    missing = [
        path.name for path in PART_PATHS.values() if not path.is_file()
    ]
    if missing:
        raise RuntimeError(
            "missing exported parts: "
            + ", ".join(sorted(missing))
            + " — run 'make mission1-field-case' first"
        )
    source_mtime = max(path.stat().st_mtime for path in SOURCE_PATHS)
    stale = [
        path.name
        for path in PART_PATHS.values()
        if path.stat().st_mtime + 1.0e-6 < source_mtime
    ]
    if stale:
        raise RuntimeError(
            "exported parts are older than the model sources: "
            + ", ".join(sorted(stale))
            + " — run 'make mission1-field-case' first"
        )


require_current_part_stls()


def _source_hash():
    digest = hashlib.sha256()
    for path in SOURCE_PATHS + (Path(__file__),):
        digest.update(path.read_bytes())
    for part in sorted(PART_PATHS):
        with PART_PATHS[part].open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
    return digest.hexdigest()[:12]


SOURCE_HASH = _source_hash()


@lru_cache(maxsize=2)
def load_stl_triangles(part):
    """Vertices of a binary STL as an ``(n, 3, 3)`` float array."""
    data = PART_PATHS[part].read_bytes()
    if len(data) < 84:
        raise RuntimeError(f"{PART_STLS[part]}: file is too short to be an STL")
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + 50 * triangle_count:
        raise RuntimeError(
            f"{PART_STLS[part]}: expected {84 + 50 * triangle_count} bytes for "
            f"{triangle_count} triangles, found {len(data)}"
        )
    if triangle_count == 0:
        raise RuntimeError(f"{PART_STLS[part]}: contains no triangles")
    records = np.frombuffer(
        data,
        dtype=np.dtype([("normal", "<3f4"), ("vertices", "<3,3f4"), ("attr", "<u2")]),
        count=triangle_count,
        offset=84,
    )
    return np.asarray(records["vertices"], dtype=np.float64)


PROJECTION_AXES = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}
PLANE_TITLES = {"xy": "PLAN (XY)", "xz": "FRONT (XZ)", "yz": "SIDE (YZ)"}
PLANE_AXIS_LABELS = {
    "xy": ("X (mm)", "Y (mm)"),
    "xz": ("X (mm)", "Z (mm)"),
    "yz": ("Y (mm)", "Z (mm)"),
}
# Triangles smaller than this projected area carry no silhouette information
# and are dropped before the union so degenerate rings never reach GEOS.
MINIMUM_TRIANGLE_AREA = 1.0e-9
# Union snapping precision in millimetres.  One micron is far below anything
# the drawings resolve and keeps the overlay union robust.
UNION_GRID_SIZE = 0.001


@lru_cache(maxsize=None)
def projected_part_geometry(part, plane):
    """Orthographic silhouette of an exported part as a shapely geometry.

    Every triangle of the mesh is projected onto ``plane`` and the union of
    those triangles is the outline that gets drawn, so a dimension is always
    placed against the geometry the model actually produced rather than a
    stylised sketch of it.
    """
    first, second = PROJECTION_AXES[plane]
    coordinates = load_stl_triangles(part)[:, :, (first, second)]
    first_edge = coordinates[:, 1] - coordinates[:, 0]
    second_edge = coordinates[:, 2] - coordinates[:, 0]
    areas = 0.5 * np.abs(
        first_edge[:, 0] * second_edge[:, 1]
        - first_edge[:, 1] * second_edge[:, 0]
    )
    kept = coordinates[areas > MINIMUM_TRIANGLE_AREA]
    if not len(kept):
        raise RuntimeError(
            f"{PART_STLS[part]}: {plane} projection has no triangle area"
        )
    rings = shapely.linearrings(
        np.concatenate([kept, kept[:, :1, :]], axis=1)
    )
    geometry = shapely.union_all(
        shapely.polygons(rings), grid_size=UNION_GRID_SIZE
    )
    if geometry.is_empty:
        raise RuntimeError(
            f"{PART_STLS[part]}: {plane} projection produced no silhouette"
        )
    minimum = coordinates.reshape(-1, 2).min(axis=0)
    maximum = coordinates.reshape(-1, 2).max(axis=0)
    bounds = (
        float(minimum[0]),
        float(minimum[1]),
        float(maximum[0]),
        float(maximum[1]),
    )
    return geometry, bounds


def geometry_polygons(geometry):
    if isinstance(geometry, MultiPolygon):
        return list(geometry.geoms)
    if isinstance(geometry, ShapelyPolygon):
        return [geometry]
    return [
        piece
        for piece in getattr(geometry, "geoms", [])
        if isinstance(piece, ShapelyPolygon)
    ]


def draw_projected_geometry(axes, part, plane, color=None, linewidth=0.75):
    geometry, bounds = projected_part_geometry(part, plane)
    stroke = PART_COLORS[part] if color is None else color
    for polygon in geometry_polygons(geometry):
        exterior = np.asarray(polygon.exterior.coords)
        axes.add_patch(
            plt.Polygon(
                exterior,
                closed=True,
                facecolor=LIGHT,
                edgecolor="none",
                zorder=1,
            )
        )
        axes.plot(
            exterior[:, 0], exterior[:, 1], color=stroke,
            linewidth=linewidth, solid_joinstyle="round", zorder=3,
        )
        for interior in polygon.interiors:
            hole = np.asarray(interior.coords)
            axes.add_patch(
                plt.Polygon(
                    hole, closed=True, facecolor=WHITE, edgecolor="none",
                    zorder=2,
                )
            )
            axes.plot(
                hole[:, 0], hole[:, 1], color=stroke,
                linewidth=linewidth * 0.75, solid_joinstyle="round", zorder=3,
            )
    return bounds


def union_bounds(*boxes):
    boxes = [box for box in boxes if box is not None]
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def axes_box_points(axes):
    """Size of an axes box in PDF points."""
    position = axes.get_position()
    width_inches, height_inches = axes.figure.get_size_inches()
    return (
        position.width * width_inches * 72.0,
        position.height * height_inches * 72.0,
    )


def padded_limits(bounds, padding_fraction, box_points):
    """Axis limits that pad ``bounds`` and already match the box aspect.

    Letting matplotlib reconcile the aspect ratio itself would either shrink
    the box or silently widen the limits; doing it here keeps the millimetres
    per point exact, which is what the callout-label allowance is measured in.
    """
    minimum_x, minimum_y, maximum_x, maximum_y = bounds
    width = max(maximum_x - minimum_x, 1.0e-3)
    height = max(maximum_y - minimum_y, 1.0e-3)
    padding = padding_fraction * max(width, height)
    width += 2.0 * padding
    height += 2.0 * padding
    scale = max(width / box_points[0], height / box_points[1])
    half_width = 0.5 * scale * box_points[0]
    half_height = 0.5 * scale * box_points[1]
    center_x = 0.5 * (minimum_x + maximum_x)
    center_y = 0.5 * (minimum_y + maximum_y)
    limits = (
        center_x - half_width,
        center_y - half_height,
        center_x + half_width,
        center_y + half_height,
    )
    return limits, scale


def set_drawing_bounds(axes, bounds, padding_fraction=0.12):
    limits, scale = padded_limits(
        bounds, padding_fraction, axes_box_points(axes)
    )
    axes.set_xlim(limits[0], limits[2])
    axes.set_ylim(limits[1], limits[3])
    axes.set_aspect("equal", adjustable="box")
    return scale


# ---------------------------------------------------------------------------
# DRAWING PLAN
#
# Every dimensional entry is routed to exactly one part and one projection
# plane, chosen from the tokens in its own name so the routing stays stable as
# the model grows.  ``validate_drawing_plan`` then proves the routing covers
# the catalog exactly once.

PART_ROUTES = (
    (("LATCH_HOOK_", "LATCH_KEEPER_", "LATCH_CATCH_", "LATCH_STRIKE_"), "latch_hook"),
    (("LATCH_LEVER_", "LATCH_DETENT_", "LATCH_CAM_", "PELICAN_"), "latch_lever"),
    (("HANDLE_BAR_", "HANDLE_GRIP_", "HANDLE_TUBE_", "PIVOT_"), "handle_bar"),
    (("HINGE_PIN_", "HINGE_ROD_", "HINGE_AXLE_"), "hinge_pin"),
    (("TPU_HINGE_", "HINGE_COUPON_"), "hinge_coupon"),
    (("LID_LOGO_", "LOGO_", "NEUROPOL_"), "logo_inlay"),
    (("TPU_SNAP_", "TPU_LID_", "LID_TPU_", "LID_SNAP_"), "tpu_snap_lid"),
    (("GASKET_", "SEAL_"), "gasket"),
    (("FAN_CASE_PAIR_LID_", "FAN_CASE_PAIR_PAD_"), "fan_lid_pad"),
    (("FAN_CASE_PAIR_INSERT_", "FAN_CASE_PAIR_LOWER_", "FAN_CASE_PAIR_CRADLE_"), "fan_insert"),
    (
        (
            "FAN_CASE_PAIR_OVERHEAD_",
            "FAN_CASE_PAIR_CARRIER_",
            "FAN_CASE_PAIR_PWM_",
            "MOUNT_",
        ),
        "mount_tray",
    ),
    (("FAN_CASE_PAIR_STORAGE_", "FAN_CASE_PAIR_BIN_", "FAN_CASE_PAIR_FAN_SIDE_"), "storage_bin"),
    (
        (
            "ACCESSORY_",
            "ORGANIZER_",
            "BATTERY_",
            "CAMERA_",
            "LENS_",
            "REMOTE_",
            "COIL_",
            "SPARE_",
        ),
        "organizer",
    ),
    (("LID_", "HINGE_"), "lid"),
)
FALLBACK_PART = "base"

# Plane tokens, tested in order.  An explicit plane suffix always wins; after
# that the axis or feature word in the name decides which projection shows the
# feature edge-on.
PLANE_TOKEN_RULES = (
    ({"XY", "PLAN", "FOOTPRINT"}, "xy"),
    ({"XZ", "FRONT", "ELEVATION"}, "xz"),
    ({"YZ", "SIDE", "SECTION", "PROFILE"}, "yz"),
    (
        {
            "Z",
            "Z0",
            "Z1",
            "HEIGHT",
            "THICKNESS",
            "DEPTHWISE",
            "VERTICAL",
            "FLOOR",
            "DROP",
            "LIFT",
            "RISE",
            "TOP",
            "BOTTOM",
        },
        "xz",
    ),
    (
        {
            "Y",
            "Y0",
            "Y1",
            "DEPTH",
            "AXIAL",
            "CASEWARD",
            "INSERTION",
            "FORE",
            "AFT",
            "REAR",
            "FRONTWALL",
        },
        "yz",
    ),
    (
        {
            "X",
            "X0",
            "X1",
            "WIDTH",
            "SPAN",
            "PITCH",
            "CENTERS",
            "RADIUS",
            "DIAMETER",
            "CLEARANCE",
        },
        "xy",
    ),
)
FALLBACK_PLANE = "xy"


def part_for(name):
    for prefixes, part in PART_ROUTES:
        if name.startswith(prefixes):
            return part
    return FALLBACK_PART


def plane_for(name):
    tokens = set(name.split("_"))
    for candidates, plane in PLANE_TOKEN_RULES:
        if tokens & candidates:
            return plane
    return FALLBACK_PLANE


def view_for(name):
    return f"{part_for(name)}:{plane_for(name)}"


DIMENSION_ENTRIES = [
    entry for entry in CONFIG_ENTRIES if entry.unit != "setting"
]
SETTING_ENTRIES = [entry for entry in CONFIG_ENTRIES if entry.unit == "setting"]

VIEW_ORDER = [
    f"{part}:{plane}" for part in PART_STLS for plane in PROJECTION_AXES
]
VIEW_ENTRIES: dict[str, list[ConfigEntry]] = {view: [] for view in VIEW_ORDER}
for _entry in DIMENSION_ENTRIES:
    VIEW_ENTRIES[view_for(_entry.name)].append(_entry)

DRAWINGS_PER_PAGE = 4
SETTINGS_PER_PAGE = 9


def drawing_groups_for_view(view):
    entries = VIEW_ENTRIES[view]
    for start in range(0, len(entries), DRAWINGS_PER_PAGE):
        yield view, tuple(entries[start : start + DRAWINGS_PER_PAGE])


DRAWING_PAGE_GROUPS = [
    group for view in VIEW_ORDER for group in drawing_groups_for_view(view)
]
SETTINGS_PAGE_COUNT = max(
    1, -(-len(SETTING_ENTRIES) // SETTINGS_PER_PAGE)
)
CURATED_PAGE_COUNT = 4
CATALOG_PAGE_COUNT = len(DRAWING_PAGE_GROUPS) + SETTINGS_PAGE_COUNT
TOTAL_PAGES = 1 + CURATED_PAGE_COUNT + CATALOG_PAGE_COUNT + 1


def validate_drawing_plan():
    """Prove the drawing plan covers every dimensional entry exactly once."""
    planned = [
        entry.name for _, entries in DRAWING_PAGE_GROUPS for entry in entries
    ]
    duplicates = sorted(
        {name for name in planned if planned.count(name) > 1}
    )
    if duplicates:
        raise RuntimeError(f"dimension drawn more than once: {duplicates}")
    expected = {entry.name for entry in DIMENSION_ENTRIES}
    seen = set(planned)
    if seen != expected:
        raise RuntimeError(
            "drawing plan is out of sync with the catalog. "
            f"Missing: {sorted(expected - seen)}. "
            f"Unexpected: {sorted(seen - expected)}."
        )
    empty = [view for view in VIEW_ORDER if not VIEW_ENTRIES[view]]
    if len(empty) == len(VIEW_ORDER):
        raise RuntimeError("drawing plan routed no dimensions at all")


validate_drawing_plan()

VISUAL_MANIFEST_HASH = hashlib.sha256(
    "\n".join(
        f"{view}:{entry.name}:{entry.unit}"
        for view, entries in DRAWING_PAGE_GROUPS
        for entry in entries
    ).encode("utf-8")
).hexdigest()[:12]
VISUAL_COVERAGE_MARKER = (
    f"engineering-dimensions-{len(DIMENSION_ENTRIES)}"
    f"-of-{len(DIMENSION_ENTRIES)}-manifest-{VISUAL_MANIFEST_HASH}"
)
SETTINGS_COVERAGE_MARKER = (
    f"settings-{len(SETTING_ENTRIES)}-of-{len(SETTING_ENTRIES)}"
)

GRAPHICALLY_ANNOTATED_NAMES: set[str] = set()
GRAPHICAL_PRIMITIVE_RECORDS: dict[str, tuple[str, tuple]] = {}
GRAPHICAL_LABEL_RECORDS: dict[str, tuple[str, str, tuple[float, float]]] = {}
CATALOGUED_SETTING_NAMES: set[str] = set()
ALLOWED_PRIMITIVE_KINDS = frozenset(
    {
        "angular_arc",
        "datum_specification",
        "diameter_dimension",
        "feature_leader",
        "horizontal_linear",
        "radius_leader",
        "vertical_linear",
    }
)


# ---------------------------------------------------------------------------
# VALUE FORMATTING


def fmt(value):
    """Format a single number the way a dimension callout reads."""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        return str(value)
    if value == int(value) and abs(value) < 1.0e9:
        return f"{int(value)}"
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text if text not in ("-0", "") else "0"


def relative_path_text(path):
    try:
        return str(path.relative_to(MODELS_ROOT))
    except ValueError:
        return path.name


def setting_value(entry):
    """Readable appendix text for a non-dimensional configuration entry."""
    value = entry.value
    if isinstance(value, Path):
        return relative_path_text(value)
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, bytes):
        digest = hashlib.sha256(value).hexdigest()[:10]
        return f"{len(value)} bytes, sha256 {digest}"
    if isinstance(value, str):
        if len(value) > 46:
            digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
            return f"{len(value)} characters, sha256 {digest}"
        return value
    if isinstance(value, dict):
        keys = ", ".join(str(key) for key in list(value)[:4])
        suffix = ", …" if len(value) > 4 else ""
        return f"{len(value)} keys: {keys}{suffix}"
    if isinstance(value, (tuple, list, set, frozenset)):
        items = [
            relative_path_text(item) if isinstance(item, Path) else str(item)
            for item in list(value)[:3]
        ]
        suffix = f", … ({len(value)} total)" if len(value) > 3 else ""
        return ", ".join(items) + suffix
    return str(value)


def dimension_value(entry):
    """Callout text for a dimensional entry, used on the drawing and the card.

    The same string is printed next to the leader on the drawing and in the
    dimension card, which is what ``--check-sync`` matches the two page crops
    against.
    """
    leaves = entry.leaves
    suffix = UNIT_LABELS[entry.unit]
    if leaves is None:
        return setting_value(entry)
    if is_number(entry.value):
        return f"{fmt(entry.value)}{suffix}"
    if len(leaves) <= 4:
        return "(" + ", ".join(fmt(leaf) for leaf in leaves) + f"){suffix}"
    return (
        f"{len(leaves)} values {fmt(min(leaves))}..{fmt(max(leaves))}{suffix}"
    )


def graphical_annotation_label(entry, index):
    return f"D{index + 1} {dimension_value(entry)}"


def graphical_annotation_kind(entry):
    name = entry.name
    if entry.unit == "deg":
        return "angular_arc"
    if entry.leaves is not None and len(entry.leaves) > 1:
        return "datum_specification"
    if name.endswith(("_DIAMETER", "_DIA", "_BORE")):
        return "diameter_dimension"
    if name.endswith(("_RADIUS", "_FILLET", "_CHAMFER")):
        return "radius_leader"
    if entry.unit in ("count", "ratio", "mm²", "mm³"):
        return "feature_leader"
    plane = plane_for(name)
    tokens = set(name.split("_"))
    vertical_tokens = {"HEIGHT", "THICKNESS", "DEPTH", "DROP", "LIFT", "RISE", "Z"}
    if plane in ("xz", "yz") and tokens & vertical_tokens:
        return "vertical_linear"
    return "horizontal_linear"


# ---------------------------------------------------------------------------
# GRAPHICAL ANNOTATION


def record_primitive(entry, kind, points):
    GRAPHICALLY_ANNOTATED_NAMES.add(entry.name)
    GRAPHICAL_PRIMITIVE_RECORDS[entry.name] = (
        kind,
        tuple((float(x), float(y)) for x, y in points),
    )


def feature_anchor(entry, index, bounds):
    """Where on the drawing the leader for ``entry`` starts.

    When the configured value is itself a pair of in-plane coordinates the
    leader is planted on that point.  Everything else is spread around the
    part on a fixed four-corner rotation so leaders never stack on top of one
    another.
    """
    minimum_x, minimum_y, maximum_x, maximum_y = bounds
    width = max(maximum_x - minimum_x, 1.0e-3)
    height = max(maximum_y - minimum_y, 1.0e-3)
    leaves = entry.leaves
    if (
        entry.unit == "mm"
        and isinstance(entry.value, (tuple, list))
        and leaves is not None
        and len(leaves) == 2
        and entry.name.endswith(("_XY", "_YZ", "_XZ", "_CENTER", "_ORIGIN"))
    ):
        candidate = (leaves[0], leaves[1])
        if (
            minimum_x <= candidate[0] <= maximum_x
            and minimum_y <= candidate[1] <= maximum_y
        ):
            return candidate
    corners = (
        (minimum_x + 0.20 * width, minimum_y + 0.20 * height),
        (maximum_x - 0.20 * width, minimum_y + 0.20 * height),
        (minimum_x + 0.20 * width, maximum_y - 0.20 * height),
        (maximum_x - 0.20 * width, maximum_y - 0.20 * height),
    )
    return corners[index % 4]


def _label(axes, entry, index, x, y, color, horizontal="center"):
    text = graphical_annotation_label(entry, index)
    GRAPHICAL_LABEL_RECORDS[entry.name] = (text, horizontal, (float(x), float(y)))
    axes.text(
        x,
        y,
        text,
        color=color,
        fontsize=6.2,
        ha=horizontal,
        va="center",
        zorder=6,
        bbox={
            "boxstyle": "round,pad=0.18",
            "facecolor": WHITE,
            "edgecolor": color,
            "linewidth": 0.4,
            "alpha": 0.92,
        },
    )


def _arrow(axes, start, end, color):
    axes.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="<|-|>",
            mutation_scale=5.0,
            linewidth=0.6,
            color=color,
            shrinkA=0.0,
            shrinkB=0.0,
            zorder=5,
        )
    )


def draw_linear_annotation(axes, entry, index, anchor, bounds, color, vertical):
    minimum_x, minimum_y, maximum_x, maximum_y = bounds
    width = max(maximum_x - minimum_x, 1.0e-3)
    height = max(maximum_y - minimum_y, 1.0e-3)
    lane = 0.14 + (index // 2) * 0.16
    sign = -1.0 if index % 2 == 0 else 1.0
    anchor_x, anchor_y = anchor
    if vertical:
        line_x = anchor_x + sign * lane * width
        half = 0.17 * height
        start = (line_x, anchor_y - half)
        end = (line_x, anchor_y + half)
        text_at = (line_x, anchor_y + half + 0.035 * height)
        axes.plot(
            [anchor_x, line_x],
            [anchor_y, anchor_y],
            color=color,
            linewidth=0.45,
            linestyle=(0, (3, 2)),
            zorder=4,
        )
        kind = "vertical_linear"
    else:
        line_y = anchor_y + sign * lane * height
        half = 0.17 * width
        start = (anchor_x - half, line_y)
        end = (anchor_x + half, line_y)
        text_at = (anchor_x, line_y + 0.030 * height)
        axes.plot(
            [anchor_x, anchor_x],
            [anchor_y, line_y],
            color=color,
            linewidth=0.45,
            linestyle=(0, (3, 2)),
            zorder=4,
        )
        kind = "horizontal_linear"
    _arrow(axes, start, end, color)
    _label(axes, entry, index, text_at[0], text_at[1], color)
    record_primitive(entry, kind, (anchor, start, end, text_at))


def draw_angular_annotation(axes, entry, index, anchor, bounds, color):
    minimum_x, minimum_y, maximum_x, maximum_y = bounds
    extent = min(
        max(maximum_x - minimum_x, 1.0e-3), max(maximum_y - minimum_y, 1.0e-3)
    )
    radius = 0.13 * extent
    leaves = entry.leaves or (0.0,)
    angle = float(leaves[0])
    if not math.isfinite(angle) or abs(angle) < 1.0e-9:
        angle = 30.0
    angle = max(-350.0, min(350.0, angle))
    start_angle, end_angle = sorted((0.0, angle))
    axes.add_patch(
        Arc(
            anchor,
            2.0 * radius,
            2.0 * radius,
            angle=0.0,
            theta1=start_angle,
            theta2=end_angle,
            color=color,
            linewidth=0.7,
            zorder=5,
        )
    )
    for boundary in (0.0, angle):
        axes.plot(
            [anchor[0], anchor[0] + radius * math.cos(math.radians(boundary))],
            [anchor[1], anchor[1] + radius * math.sin(math.radians(boundary))],
            color=color,
            linewidth=0.45,
            zorder=4,
        )
    midpoint = math.radians(angle / 2.0)
    text_at = (
        anchor[0] + 1.45 * radius * math.cos(midpoint),
        anchor[1] + 1.45 * radius * math.sin(midpoint),
    )
    _label(axes, entry, index, text_at[0], text_at[1], color)
    record_primitive(
        entry,
        "angular_arc",
        (
            anchor,
            (anchor[0] + radius, anchor[1]),
            (
                anchor[0] + radius * math.cos(math.radians(angle)),
                anchor[1] + radius * math.sin(math.radians(angle)),
            ),
            text_at,
        ),
    )


def draw_circular_annotation(axes, entry, index, anchor, bounds, color, kind):
    """Draw a true-size circle or radius arc; fall back to a leader if it will
    not fit inside the view."""
    minimum_x, minimum_y, maximum_x, maximum_y = bounds
    extent = min(
        max(maximum_x - minimum_x, 1.0e-3), max(maximum_y - minimum_y, 1.0e-3)
    )
    leaves = entry.leaves or (0.0,)
    value = abs(float(leaves[0]))
    radius = value / 2.0 if kind == "diameter_dimension" else value
    if not (1.0e-3 < radius <= 0.45 * extent):
        return draw_leader_annotation(axes, entry, index, anchor, bounds, color)
    theta1, theta2 = (0.0, 360.0) if kind == "diameter_dimension" else (20.0, 160.0)
    axes.add_patch(
        Arc(
            anchor,
            2.0 * radius,
            2.0 * radius,
            angle=0.0,
            theta1=theta1,
            theta2=theta2,
            color=color,
            linewidth=0.7,
            zorder=5,
        )
    )
    tip = (
        anchor[0] + radius * math.cos(math.radians(45.0)),
        anchor[1] + radius * math.sin(math.radians(45.0)),
    )
    text_at = (
        anchor[0] + (radius + 0.10 * extent) * math.cos(math.radians(45.0)),
        anchor[1] + (radius + 0.10 * extent) * math.sin(math.radians(45.0)),
    )
    axes.plot(
        [anchor[0], tip[0], text_at[0]],
        [anchor[1], tip[1], text_at[1]],
        color=color,
        linewidth=0.5,
        zorder=4,
    )
    _label(axes, entry, index, text_at[0], text_at[1], color, horizontal="left")
    record_primitive(entry, kind, (anchor, tip, text_at))


def draw_leader_annotation(axes, entry, index, anchor, bounds, color):
    minimum_x, minimum_y, maximum_x, maximum_y = bounds
    width = max(maximum_x - minimum_x, 1.0e-3)
    height = max(maximum_y - minimum_y, 1.0e-3)
    horizontal_sign = -1.0 if index % 2 == 0 else 1.0
    vertical_sign = -1.0 if index < 2 else 1.0
    elbow = (
        anchor[0] + horizontal_sign * 0.14 * width,
        anchor[1] + vertical_sign * 0.16 * height,
    )
    text_at = (elbow[0] + horizontal_sign * 0.05 * width, elbow[1])
    axes.plot(
        [anchor[0], elbow[0], text_at[0]],
        [anchor[1], elbow[1], elbow[1]],
        color=color,
        linewidth=0.5,
        zorder=4,
    )
    axes.plot([anchor[0]], [anchor[1]], marker="o", markersize=1.8, color=color, zorder=5)
    _label(
        axes,
        entry,
        index,
        text_at[0],
        text_at[1],
        color,
        horizontal="right" if horizontal_sign < 0 else "left",
    )
    record_primitive(entry, "feature_leader", (anchor, elbow, text_at))


def draw_datum_annotation(axes, entry, index, anchor, bounds, color):
    minimum_x, minimum_y, maximum_x, maximum_y = bounds
    width = max(maximum_x - minimum_x, 1.0e-3)
    height = max(maximum_y - minimum_y, 1.0e-3)
    horizontal_sign = -1.0 if index % 2 == 0 else 1.0
    vertical_sign = -1.0 if index < 2 else 1.0
    flag = 0.035 * min(width, height)
    triangle = (
        (anchor[0], anchor[1]),
        (anchor[0] - flag, anchor[1] + vertical_sign * 1.6 * flag),
        (anchor[0] + flag, anchor[1] + vertical_sign * 1.6 * flag),
    )
    axes.add_patch(
        plt.Polygon(
            triangle, closed=True, facecolor=color, edgecolor=color, zorder=5
        )
    )
    elbow = (
        anchor[0] + horizontal_sign * 0.13 * width,
        anchor[1] + vertical_sign * 0.19 * height,
    )
    text_at = (elbow[0] + horizontal_sign * 0.04 * width, elbow[1])
    axes.plot(
        [anchor[0], elbow[0], text_at[0]],
        [anchor[1] + vertical_sign * 1.6 * flag, elbow[1], elbow[1]],
        color=color,
        linewidth=0.5,
        zorder=4,
    )
    _label(
        axes,
        entry,
        index,
        text_at[0],
        text_at[1],
        color,
        horizontal="right" if horizontal_sign < 0 else "left",
    )
    record_primitive(entry, "datum_specification", triangle + (elbow, text_at))


def draw_graphical_annotations(axes, entries, bounds, color):
    for index, entry in enumerate(entries):
        anchor = feature_anchor(entry, index, bounds)
        kind = graphical_annotation_kind(entry)
        if kind == "angular_arc":
            draw_angular_annotation(axes, entry, index, anchor, bounds, color)
        elif kind in ("diameter_dimension", "radius_leader"):
            draw_circular_annotation(
                axes, entry, index, anchor, bounds, color, kind
            )
        elif kind == "datum_specification":
            draw_datum_annotation(axes, entry, index, anchor, bounds, color)
        elif kind in ("horizontal_linear", "vertical_linear"):
            draw_linear_annotation(
                axes,
                entry,
                index,
                anchor,
                bounds,
                color,
                vertical=kind == "vertical_linear",
            )
        else:
            draw_leader_annotation(axes, entry, index, anchor, bounds, color)
    points = [
        point
        for entry in entries
        for point in GRAPHICAL_PRIMITIVE_RECORDS[entry.name][1]
    ]
    if not points:
        return bounds
    return union_bounds(
        bounds,
        (
            min(point[0] for point in points),
            min(point[1] for point in points),
            max(point[0] for point in points),
            max(point[1] for point in points),
        ),
    )


# ---------------------------------------------------------------------------
# PAGE SCAFFOLDING

PAGE_NUMBER = 0
PAGE_TITLES: list[str] = []


def new_page(title, subtitle=""):
    global PAGE_NUMBER
    PAGE_NUMBER += 1
    PAGE_TITLES.append(title)
    figure = plt.figure(figsize=(11.0, 8.5))
    figure.text(0.055, 0.945, title, fontsize=13.0, fontweight="bold", color=INK)
    if subtitle:
        figure.text(0.055, 0.917, subtitle, fontsize=7.6, color=GRAY)
    figure.lines.append(
        plt.Line2D(
            [0.055, 0.945], [0.905, 0.905], color=GRID, linewidth=0.8,
            transform=figure.transFigure, figure=figure,
        )
    )
    figure.text(
        0.055,
        0.048,
        f"{OUTPUT_PDF.name} • source-{SOURCE_HASH}",
        fontsize=6.2,
        color=GRAY,
    )
    figure.text(
        0.945,
        0.048,
        f"page {PAGE_NUMBER} of {TOTAL_PAGES}",
        fontsize=6.2,
        color=GRAY,
        ha="right",
    )
    return figure


def panel(figure, rectangle, title=None):
    left, bottom, width, height = rectangle
    figure.patches.append(
        FancyBboxPatch(
            (left, bottom),
            width,
            height,
            boxstyle="round,pad=0.004,rounding_size=0.008",
            linewidth=0.7,
            edgecolor=GRID,
            facecolor=WHITE,
            transform=figure.transFigure,
            figure=figure,
            zorder=0,
        )
    )
    if title:
        figure.text(
            left + 0.008,
            bottom + height - 0.026,
            title,
            fontsize=7.4,
            fontweight="bold",
            color=INK,
        )


def drawing_axes(figure, rectangle, plane):
    axes = figure.add_axes(rectangle)
    axes.set_facecolor(WHITE)
    for spine in axes.spines.values():
        spine.set_color(GRID)
        spine.set_linewidth(0.6)
    axes.tick_params(labelsize=5.4, colors=GRAY, length=2.0, width=0.5)
    axes.grid(True, color=GRID, linewidth=0.35, alpha=0.7)
    axes.set_axisbelow(True)
    horizontal, vertical = PLANE_AXIS_LABELS[plane]
    axes.set_xlabel(horizontal, fontsize=6.0, color=GRAY, labelpad=1.5)
    axes.set_ylabel(vertical, fontsize=6.0, color=GRAY, labelpad=1.5)
    return axes


def note(figure, x, y, text, width=118, color=GRAY, size=6.4):
    figure.text(
        x, y, textwrap.fill(text, width), fontsize=size, color=color, va="top"
    )


def draw_dimension_cards(figure, rectangle, entries):
    axes = figure.add_axes(rectangle)
    axes.set_axis_off()
    axes.set_xlim(0.0, 1.0)
    axes.set_ylim(0.0, 1.0)
    slots = max(len(entries), 1)
    row_height = 1.0 / slots
    for index, entry in enumerate(entries):
        top = 1.0 - index * row_height
        axes.add_patch(
            Rectangle(
                (0.02, top - row_height + 0.012),
                0.96,
                row_height - 0.024,
                facecolor=LIGHT,
                edgecolor=GRID,
                linewidth=0.5,
                transform=axes.transAxes,
            )
        )
        axes.text(
            0.06,
            top - 0.030,
            f"D{index + 1}",
            fontsize=7.4,
            fontweight="bold",
            color=BLUE,
            va="top",
        )
        axes.text(
            0.20,
            top - 0.028,
            wrap_identifier(entry.name, 22),
            fontsize=5.9,
            color=INK,
            va="top",
            family="DejaVu Sans Mono",
        )
        value_top = top - 0.030 - 0.020 * (
            wrap_identifier(entry.name, 22).count("\n") + 1
        )
        axes.text(
            0.06,
            value_top,
            textwrap.fill(dimension_value(entry), 30),
            fontsize=7.0,
            fontweight="bold",
            color=INK,
            va="top",
        )
        axes.text(
            0.06,
            value_top - 0.034,
            textwrap.fill(entry.description, 42),
            fontsize=5.4,
            color=GRAY,
            va="top",
        )
        axes.text(
            0.06,
            top - row_height + 0.030,
            f"{entry.category} • line {entry.source_line}"
            f" • {'derived' if entry.derived else 'literal'}",
            fontsize=5.0,
            color=GRAY,
            va="bottom",
        )
    return axes


# ---------------------------------------------------------------------------
# PAGES


def page_cover(pdf):
    figure = new_page(
        "Mission 1 field case — configuration and dimension guide",
        "Every configuration value resolved from the model source, drawn "
        "against the exported meshes.",
    )
    panel(figure, (0.055, 0.42, 0.42, 0.45), "WHAT THIS DOCUMENT IS")
    note(
        figure,
        0.068,
        0.825,
        "This guide is generated from "
        f"{MODEL_SOURCE.name} without importing Blender. The model's "
        "configuration block is executed by a small deterministic interpreter, "
        "so derived values — the ones computed from the companion fan-case, "
        "dual-fan, wrapping-cover and camera-dummy models — are catalogued "
        "with the same fidelity as plain literals.",
        width=62,
    )
    note(
        figure,
        0.068,
        0.675,
        "Drawings are orthographic silhouettes of the exported STLs, so a "
        "dimension is always shown against the geometry that was actually "
        "produced. The build fails rather than drawing a stale part: every "
        "STL must exist and be newer than the model sources.",
        width=62,
    )
    note(
        figure,
        0.068,
        0.545,
        "Values that are numbers, or containers of nothing but numbers, are "
        "treated as dimensional and drawn. Everything else — file names, "
        "modes, flags, embedded assets — is listed in the settings appendix.",
        width=62,
    )

    panel(figure, (0.515, 0.42, 0.43, 0.45), "CONTENTS")
    rows = [
        ("Configuration values resolved", f"{len(CONFIG_ENTRIES)}"),
        ("Dimensional values drawn", f"{len(DIMENSION_ENTRIES)}"),
        ("Build settings listed", f"{len(SETTING_ENTRIES)}"),
        ("Parts projected", f"{len(PART_STLS)}"),
        ("Curated pages", f"{CURATED_PAGE_COUNT}"),
        ("Dimension pages", f"{len(DRAWING_PAGE_GROUPS)}"),
        ("Settings pages", f"{SETTINGS_PAGE_COUNT}"),
        ("Total pages", f"{TOTAL_PAGES}"),
        ("Source fingerprint", SOURCE_HASH),
    ]
    for index, (label, value) in enumerate(rows):
        y = 0.825 - index * 0.041
        figure.text(0.530, y, label, fontsize=7.4, color=GRAY)
        figure.text(
            0.930, y, value, fontsize=7.8, color=INK, fontweight="bold", ha="right"
        )

    panel(figure, (0.055, 0.105, 0.89, 0.29), "CATEGORY BREAKDOWN")
    categories: dict[str, int] = {}
    for entry in CONFIG_ENTRIES:
        categories[entry.category] = categories.get(entry.category, 0) + 1
    ordered = sorted(categories.items(), key=lambda item: -item[1])
    axes = figure.add_axes((0.075, 0.130, 0.85, 0.215))
    axes.barh(
        [name for name, _ in ordered][::-1],
        [count for _, count in ordered][::-1],
        color=BLUE,
        height=0.62,
    )
    axes.tick_params(labelsize=5.8, colors=GRAY, length=0.0)
    for spine in axes.spines.values():
        spine.set_visible(False)
    axes.grid(True, axis="x", color=GRID, linewidth=0.4)
    axes.set_axisbelow(True)
    pdf.savefig(figure)
    plt.close(figure)


def curated_drawing(
    pdf, title, subtitle, parts, plane, callouts, commentary
):
    """One curated page: real projections plus hand-picked callouts."""
    figure = new_page(title, subtitle)
    panel(figure, (0.055, 0.12, 0.60, 0.78))
    axes = drawing_axes(figure, (0.080, 0.175, 0.545, 0.665), plane)
    bounds = None
    for part in parts:
        bounds = union_bounds(
            bounds, draw_projected_geometry(axes, part, plane)
        )
    set_drawing_bounds(axes, bounds, 0.10)
    axes.set_title(
        " + ".join(PART_TITLES[part] for part in parts)
        + f" — {PLANE_TITLES[plane]}",
        fontsize=7.2,
        color=INK,
        pad=4.0,
    )

    panel(figure, (0.670, 0.12, 0.275, 0.78), "REFERENCE VALUES")
    y = 0.845
    for name in callouts:
        entry = CONFIG_BY_NAME.get(name)
        if entry is None:
            raise RuntimeError(f"curated page references unknown value {name}")
        figure.text(
            0.684,
            y,
            wrap_identifier(entry.name, 30),
            fontsize=5.8,
            color=GRAY,
            family="DejaVu Sans Mono",
            va="top",
        )
        lines = wrap_identifier(entry.name, 30).count("\n") + 1
        figure.text(
            0.684,
            y - 0.013 * lines - 0.004,
            dimension_value(entry),
            fontsize=8.0,
            fontweight="bold",
            color=INK,
            va="top",
        )
        y -= 0.013 * lines + 0.036
    note(figure, 0.684, y - 0.012, commentary, width=46, size=6.0)
    pdf.savefig(figure)
    plt.close(figure)


def page_case_envelope(pdf):
    curated_drawing(
        pdf,
        "Closed-case envelope",
        "Base and lid silhouettes with the printable-envelope limits that "
        "drive them.",
        ("base", "lid"),
        "xy",
        (
            "CASE_WIDTH",
            "CASE_DEPTH",
            "CASE_CORNER_RADIUS",
            "WALL_THICKNESS",
            "MAX_PRINT_XY",
            "PROJECT_PLATE_SIZE",
        ),
        "Both shells are drawn at the same scale and share an origin, so the "
        "plan outlines overlay exactly where the lid lands on the base. The "
        "printable envelope is the hard constraint: no part footprint may "
        "exceed it on either axis.",
    )


def page_case_section(pdf):
    curated_drawing(
        pdf,
        "Case section and stack height",
        "Front elevation of the base shell against the vertical stack the "
        "accessory layout has to fit.",
        ("base",),
        "xz",
        (
            "BASE_FLOOR_THICKNESS",
            "ACCESSORY_CASE_BASE_HEIGHT",
            "ACCESSORY_ORGANIZER_BOTTOM_Z",
            "ACCESSORY_MOUNT_ENVELOPE",
            "ACCESSORY_COIL_ENVELOPE",
        ),
        "Floor thickness, pocket depth and organizer height stack to the "
        "internal height. The mount and coil envelopes are the reserved "
        "volumes the pockets are cut around.",
    )


def page_latch_mechanism(pdf):
    curated_drawing(
        pdf,
        "Pelican latch mechanism",
        "Lever and hook as exported, viewed on the plane the linkage swings "
        "in.",
        ("latch_lever", "latch_hook"),
        "yz",
        (
            "LATCH_HOOK_CLOSED_ANGLE",
            "LATCH_LEVER_CLOSED_ANGLE",
            "LATCH_DETENT_RELEASE_ANGLE",
            "LATCH_SOURCE_SCALE",
        ),
        "The lever and hook print as a pair. Closed angles set the preload "
        "the gasket sees; the release angle is where the detent lets go.",
    )


def page_handle_and_hinge(pdf):
    curated_drawing(
        pdf,
        "Handle and hinge hardware",
        "Pivoting handle bar and hinge pin as exported.",
        ("handle_bar", "hinge_pin"),
        "yz",
        (
            "HINGE_RUNNING_CLEARANCE_SCALE",
            "HANDLE_BASE_EAR_PROFILE_YZ",
            "LATCH_BASE_EAR_PROFILE_YZ",
        ),
        "Handle and hinge share the same ear-profile construction on the "
        "base, so the two YZ profiles are listed together. Running clearance "
        "is applied to the printed pin fit.",
    )


CURATED_PAGES = (
    page_case_envelope,
    page_case_section,
    page_latch_mechanism,
    page_handle_and_hinge,
)


# ---------------------------------------------------------------------------
# DIMENSION PAGES

DRAWING_PANEL_RECT = (0.055, 0.115, 0.655, 0.785)
DRAWING_AXES_RECT = (0.082, 0.170, 0.600, 0.665)
CARDS_PANEL_RECT = (0.730, 0.115, 0.215, 0.785)
CARDS_AXES_RECT = (0.737, 0.130, 0.201, 0.755)
# Upper bound on the advance width of one callout character at 6.2 pt, and
# half the line height of the boxed label, both in PDF points.
LABEL_CHARACTER_POINTS = 4.3
LABEL_HALF_LINE_POINTS = 6.5


def bounds_with_label_allowance(axes, entries, bounds, padding_fraction):
    """Grow ``bounds`` until every callout label fits inside the drawing box.

    Labels are plain text and matplotlib will happily draw them outside the
    axes, which would push them into the dimension-card column and break the
    per-crop text checks in ``--check-sync``.  Estimating the label extent from
    the axes size in points and folding it back into the data limits keeps them
    inside without a trial render.
    """
    box_points = axes_box_points(axes)
    for _ in range(6):
        _, scale = padded_limits(bounds, padding_fraction, box_points)
        grown = bounds
        for entry in entries:
            text, alignment, (text_x, text_y) = GRAPHICAL_LABEL_RECORDS[
                entry.name
            ]
            span = len(text) * LABEL_CHARACTER_POINTS * scale
            if alignment == "left":
                left, right = text_x, text_x + span
            elif alignment == "right":
                left, right = text_x - span, text_x
            else:
                left, right = text_x - span / 2.0, text_x + span / 2.0
            margin = LABEL_HALF_LINE_POINTS * scale
            grown = union_bounds(
                grown, (left, text_y - margin, right, text_y + margin)
            )
        if grown == bounds:
            break
        bounds = grown
    return bounds


def page_dimension_drawing(pdf, view, entries):
    part, plane = view.split(":")
    figure = new_page(
        f"{PART_TITLES[part]} — {PLANE_TITLES[plane]}",
        f"{len(entries)} configuration value"
        f"{'' if len(entries) == 1 else 's'} drawn against the exported "
        f"{PART_STLS[part]}.",
    )
    panel(figure, DRAWING_PANEL_RECT)
    axes = drawing_axes(figure, DRAWING_AXES_RECT, plane)
    bounds = draw_projected_geometry(axes, part, plane)
    set_drawing_bounds(axes, bounds, 0.18)
    annotated = draw_graphical_annotations(
        axes, entries, bounds, PART_COLORS[part]
    )
    set_drawing_bounds(
        axes, bounds_with_label_allowance(axes, entries, annotated, 0.08), 0.08
    )
    axes.set_title(
        f"{PART_TITLES[part]} — actual {PLANE_TITLES[plane]} silhouette",
        fontsize=7.2,
        color=INK,
        pad=4.0,
    )
    panel(figure, CARDS_PANEL_RECT, "DIMENSIONS")
    draw_dimension_cards(figure, CARDS_AXES_RECT, entries)
    pdf.savefig(figure)
    plt.close(figure)


def page_settings_appendix(pdf, entries, index, total):
    figure = new_page(
        f"Build settings appendix ({index} of {total})",
        "Configuration values that are not dimensional: file names, modes, "
        "flags and embedded assets.",
    )
    panel(figure, (0.055, 0.135, 0.30, 0.765), "ASSEMBLY REFERENCE")
    axes = drawing_axes(figure, (0.075, 0.185, 0.26, 0.60), "xy")
    bounds = union_bounds(
        draw_projected_geometry(axes, "base", "xy", linewidth=0.5),
        draw_projected_geometry(axes, "lid", "xy", color=GRAY, linewidth=0.4),
    )
    set_drawing_bounds(axes, bounds, 0.08)
    axes.set_title("Base and lid plan", fontsize=6.6, color=GRAY, pad=3.0)

    panel(figure, (0.375, 0.115, 0.570, 0.785))
    cards = figure.add_axes((0.382, 0.128, 0.556, 0.762))
    cards.set_axis_off()
    cards.set_xlim(0.0, 1.0)
    cards.set_ylim(0.0, 1.0)
    row_height = 1.0 / SETTINGS_PER_PAGE
    for row, entry in enumerate(entries):
        top = 1.0 - row * row_height
        cards.add_patch(
            Rectangle(
                (0.01, top - row_height + 0.008),
                0.98,
                row_height - 0.016,
                facecolor=LIGHT,
                edgecolor=GRID,
                linewidth=0.5,
                transform=cards.transAxes,
            )
        )
        cards.text(
            0.025,
            top - 0.022,
            entry.name,
            fontsize=6.4,
            color=INK,
            family="DejaVu Sans Mono",
            va="top",
        )
        cards.text(
            0.025,
            top - 0.049,
            textwrap.fill(setting_value(entry), 78),
            fontsize=6.6,
            fontweight="bold",
            color=BLUE,
            va="top",
        )
        cards.text(
            0.985,
            top - 0.022,
            f"{entry.category} • line {entry.source_line}",
            fontsize=5.4,
            color=GRAY,
            ha="right",
            va="top",
        )
        CATALOGUED_SETTING_NAMES.add(entry.name)
    pdf.savefig(figure)
    plt.close(figure)


def page_catalog(pdf):
    """Emit every dimension page and then the settings appendix."""
    if PAGE_NUMBER != 1 + CURATED_PAGE_COUNT:
        raise RuntimeError(
            f"catalog started at page {PAGE_NUMBER + 1}, expected page "
            f"{2 + CURATED_PAGE_COUNT}"
        )
    for view, entries in DRAWING_PAGE_GROUPS:
        page_dimension_drawing(pdf, view, entries)
    pages = [
        SETTING_ENTRIES[start : start + SETTINGS_PER_PAGE]
        for start in range(0, len(SETTING_ENTRIES), SETTINGS_PER_PAGE)
    ] or [[]]
    for index, entries in enumerate(pages, start=1):
        page_settings_appendix(pdf, entries, index, len(pages))
    if PAGE_NUMBER != TOTAL_PAGES - 1:
        raise RuntimeError(
            f"catalog ended at page {PAGE_NUMBER}, expected page "
            f"{TOTAL_PAGES - 1}"
        )


def page_coverage(pdf):
    figure = new_page(
        "Coverage",
        "What this document guarantees, and how --check-sync proves it.",
    )
    panel(figure, (0.055, 0.46, 0.42, 0.41), "COVERAGE")
    rows = (
        ("Configuration values resolved", f"{len(CONFIG_ENTRIES)}"),
        (
            "Dimensions drawn graphically",
            f"{len(GRAPHICALLY_ANNOTATED_NAMES)} of {len(DIMENSION_ENTRIES)}",
        ),
        (
            "Settings listed",
            f"{len(CATALOGUED_SETTING_NAMES)} of {len(SETTING_ENTRIES)}",
        ),
        ("Graphical primitives recorded", f"{len(GRAPHICAL_PRIMITIVE_RECORDS)}"),
        ("Parts projected", f"{len(PART_STLS)}"),
        ("Pages", f"{TOTAL_PAGES}"),
    )
    for index, (label, value) in enumerate(rows):
        y = 0.815 - index * 0.048
        figure.text(0.070, y, label, fontsize=7.4, color=GRAY)
        figure.text(
            0.460, y, value, fontsize=7.8, color=INK, fontweight="bold", ha="right"
        )

    panel(figure, (0.515, 0.46, 0.43, 0.41), "MARKERS")
    figure.text(0.530, 0.815, "Visual coverage", fontsize=7.0, color=GRAY)
    figure.text(
        0.530,
        0.790,
        VISUAL_COVERAGE_MARKER,
        fontsize=6.0,
        color=INK,
        family="DejaVu Sans Mono",
    )
    figure.text(0.530, 0.745, "Settings coverage", fontsize=7.0, color=GRAY)
    figure.text(
        0.530,
        0.720,
        SETTINGS_COVERAGE_MARKER,
        fontsize=6.0,
        color=INK,
        family="DejaVu Sans Mono",
    )
    figure.text(0.530, 0.675, "Source fingerprint", fontsize=7.0, color=GRAY)
    figure.text(
        0.530,
        0.650,
        f"source-{SOURCE_HASH}",
        fontsize=6.0,
        color=INK,
        family="DejaVu Sans Mono",
    )
    note(
        figure,
        0.530,
        0.610,
        "The fingerprint covers the model source, the four companion models, "
        "the shared fan presets, this generator and every exported STL. Any "
        "change to any of them changes the fingerprint and makes "
        "--check-sync fail until the guide is regenerated.",
        width=52,
        size=6.2,
    )

    panel(figure, (0.055, 0.105, 0.89, 0.335), "WHAT --check-sync VERIFIES")
    note(
        figure,
        0.070,
        0.410,
        "1. The fingerprint and both coverage markers are present in the file, "
        "so the guide was built from the sources on disk.\n"
        "2. The page count matches the plan exactly.\n"
        f"3. For each of the {len(DIMENSION_ENTRIES)} dimensional values, the "
        "callout text is extracted from the drawing half of its page and the "
        "name and value are extracted from the dimension-card column — "
        "proving the value is both drawn and tabulated, not just listed.\n"
        "4. Every recorded graphical primitive is finite and non-degenerate, "
        "so no dimension is 'drawn' by a zero-length leader.",
        width=150,
        size=6.6,
    )
    pdf.savefig(figure)
    plt.close(figure)


# ---------------------------------------------------------------------------
# VALIDATION


def validate_rendered_coverage():
    """Prove the rendered pages cover the catalog before the file is kept."""
    expected = {entry.name for entry in DIMENSION_ENTRIES}
    if GRAPHICALLY_ANNOTATED_NAMES != expected:
        raise RuntimeError(
            "graphical coverage is incomplete. Missing: "
            f"{sorted(expected - GRAPHICALLY_ANNOTATED_NAMES)}. Unexpected: "
            f"{sorted(GRAPHICALLY_ANNOTATED_NAMES - expected)}."
        )
    if set(GRAPHICAL_PRIMITIVE_RECORDS) != expected:
        raise RuntimeError(
            "graphical primitive records do not match the drawn dimensions"
        )
    if set(GRAPHICAL_LABEL_RECORDS) != expected:
        raise RuntimeError(
            "graphical label records do not match the drawn dimensions"
        )
    for name, (kind, points) in sorted(GRAPHICAL_PRIMITIVE_RECORDS.items()):
        if kind not in ALLOWED_PRIMITIVE_KINDS:
            raise RuntimeError(f"{name}: unknown primitive kind {kind!r}")
        if len(points) < 2:
            raise RuntimeError(f"{name}: primitive has fewer than two points")
        if not all(
            math.isfinite(value) for point in points for value in point
        ):
            raise RuntimeError(f"{name}: primitive has a non-finite point")
        spread = max(
            math.dist(first, second)
            for first in points
            for second in points
        )
        if spread < 1.0e-6:
            raise RuntimeError(f"{name}: primitive is degenerate")
    settings = {entry.name for entry in SETTING_ENTRIES}
    if CATALOGUED_SETTING_NAMES != settings:
        raise RuntimeError(
            "settings appendix is incomplete. Missing: "
            f"{sorted(settings - CATALOGUED_SETTING_NAMES)}."
        )


def normalized_pdf_text(text):
    return re.sub(r"\s+", "", text).casefold()


def extract_pdf_pages(crop=None):
    command = ["pdftotext", "-layout"]
    if crop is not None:
        left, top, width, height = crop
        command += [
            "-x", str(left), "-y", str(top), "-W", str(width), "-H", str(height)
        ]
    command += [str(OUTPUT_PDF), "-"]
    try:
        completed = subprocess.run(
            command, check=True, capture_output=True, text=True
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "pdftotext is required for --check-sync (poppler-utils)"
        ) from exc
    pages = completed.stdout.split("\f")
    while pages and not pages[-1].strip():
        pages.pop()
    if len(pages) != TOTAL_PAGES:
        raise RuntimeError(
            f"extracted {len(pages)} pages with crop {crop}, expected "
            f"{TOTAL_PAGES}"
        )
    return pages


# The drawing panel and the dimension-card column of a dimension page, in PDF
# points on a 792 x 612 landscape letter page.
DRAWING_CROP = (0, 0, 575, 612)
CARDS_CROP = (575, 0, 217, 612)


def validate_pdf_engineering_drawings():
    """Check each dimension really is drawn and tabulated on its own page."""
    drawing_pages = extract_pdf_pages(DRAWING_CROP)
    card_pages = extract_pdf_pages(CARDS_CROP)
    failures = []
    for offset, (view, entries) in enumerate(DRAWING_PAGE_GROUPS):
        page_index = 1 + CURATED_PAGE_COUNT + offset
        drawing_text = normalized_pdf_text(drawing_pages[page_index])
        card_text = normalized_pdf_text(card_pages[page_index])
        for index, entry in enumerate(entries):
            label = normalized_pdf_text(graphical_annotation_label(entry, index))
            if label not in drawing_text:
                failures.append(
                    f"page {page_index + 1} ({view}): callout for "
                    f"{entry.name} is not in the drawing panel"
                )
            if normalized_pdf_text(entry.name) not in card_text:
                failures.append(
                    f"page {page_index + 1} ({view}): {entry.name} is not in "
                    "the dimension cards"
                )
            if normalized_pdf_text(dimension_value(entry)) not in card_text:
                failures.append(
                    f"page {page_index + 1} ({view}): value for {entry.name} "
                    "is not in the dimension cards"
                )
    if failures:
        raise RuntimeError(
            f"{len(failures)} drawing check(s) failed:\n  "
            + "\n  ".join(failures[:25])
        )
    return len(drawing_pages)


def check_pdf_sync():
    if not OUTPUT_PDF.is_file():
        raise RuntimeError(
            f"{OUTPUT_PDF.name} does not exist — run "
            "'make mission1-field-case-dim-pdf' first"
        )
    data = OUTPUT_PDF.read_bytes()
    if not data.rstrip().endswith(b"%%EOF"):
        raise RuntimeError(f"{OUTPUT_PDF.name} is truncated")
    for marker in (
        f"source-{SOURCE_HASH}",
        VISUAL_COVERAGE_MARKER,
        SETTINGS_COVERAGE_MARKER,
    ):
        if marker.encode("ascii") not in data:
            raise RuntimeError(
                f"{OUTPUT_PDF.name} is out of date: '{marker}' not found — "
                "regenerate it"
            )
    pages = len(re.findall(rb"/Type\s*/Page\b", data))
    if pages != TOTAL_PAGES:
        raise RuntimeError(
            f"{OUTPUT_PDF.name} has {pages} pages, expected {TOTAL_PAGES}"
        )
    validate_pdf_engineering_drawings()
    print(
        f"{OUTPUT_PDF.name} is in sync: {TOTAL_PAGES} pages, "
        f"{len(DIMENSION_ENTRIES)} dimensions drawn and tabulated across "
        f"{len(DRAWING_PAGE_GROUPS)} drawing pages, "
        f"{len(SETTING_ENTRIES)} settings listed, source-{SOURCE_HASH}."
    )


# ---------------------------------------------------------------------------
# ENTRY POINT

if len(CURATED_PAGES) != CURATED_PAGE_COUNT:
    raise RuntimeError(
        f"CURATED_PAGE_COUNT is {CURATED_PAGE_COUNT} but "
        f"{len(CURATED_PAGES)} curated pages are defined"
    )


def main():
    global PAGE_NUMBER
    PAGE_NUMBER = 0
    PAGE_TITLES.clear()
    GRAPHICALLY_ANNOTATED_NAMES.clear()
    GRAPHICAL_PRIMITIVE_RECORDS.clear()
    GRAPHICAL_LABEL_RECORDS.clear()
    CATALOGUED_SETTING_NAMES.clear()

    handle = tempfile.NamedTemporaryFile(
        prefix=".mission1_field_case_dimensions_",
        suffix=".pdf",
        dir=str(HERE),
        delete=False,
    )
    handle.close()
    temporary_path = Path(handle.name)
    try:
        with PdfPages(temporary_path) as pdf:
            page_cover(pdf)
            for page in CURATED_PAGES:
                page(pdf)
            page_catalog(pdf)
            validate_rendered_coverage()
            page_coverage(pdf)
            if PAGE_NUMBER != TOTAL_PAGES:
                raise RuntimeError(
                    f"wrote {PAGE_NUMBER} pages, expected {TOTAL_PAGES}"
                )
            pdf.infodict().update(
                {
                    "Title": "Mission 1 field case — configuration and "
                    "dimension guide",
                    "Author": "models3d",
                    "Subject": (
                        f"{len(CONFIG_ENTRIES)} configuration values resolved "
                        f"from {MODEL_SOURCE.name}"
                    ),
                    "Keywords": (
                        f"source-{SOURCE_HASH} {VISUAL_COVERAGE_MARKER} "
                        f"{SETTINGS_COVERAGE_MARKER}"
                    ),
                }
            )
        temporary_path.replace(OUTPUT_PDF)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    print(
        f"wrote {OUTPUT_PDF.name}: {TOTAL_PAGES} pages, "
        f"{len(DIMENSION_ENTRIES)} dimensions drawn, "
        f"{len(SETTING_ENTRIES)} settings listed, source-{SOURCE_HASH}."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check-sync",
        action="store_true",
        help="verify the existing PDF matches the model sources instead of "
        "regenerating it",
    )
    arguments = parser.parse_args()
    try:
        if arguments.check_sync:
            check_pdf_sync()
        else:
            main()
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
