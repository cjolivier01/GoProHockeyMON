"""Regression-check strict TPU hinge-coupon STL and 3MF export payloads.

Run from the repository root with::

    blender --background --factory-startup --threads 4 --python-exit-code 1 \
        --python models3d/mission1-field-case/check_mission1_field_case_coupon_export.py

The 3MF path intentionally normalizes to the coupon's nonzero bounding-box
minimum.  That exercises the precision-sensitive path that differs from the
standalone STL's zero export origin.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import sys

from mathutils import Vector


sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission1_field_case_blender as case


REPEAT_COUNT = 8


def payload_digest(payload) -> str:
    vertices, triangles = payload
    digest = hashlib.sha256()
    for vertex in vertices:
        digest.update(struct.pack("<3d", *vertex))
    for triangle in triangles:
        digest.update(struct.pack("<3I", *triangle))
    return digest.hexdigest()


def repeated_strict_payload(obj, origin, label: str):
    payloads = [
        case.evaluated_mesh_payload(obj, origin)
        for _index in range(REPEAT_COUNT)
    ]
    signatures = {
        (len(vertices), len(triangles), payload_digest((vertices, triangles)))
        for vertices, triangles in payloads
    }
    if len(signatures) != 1:
        raise AssertionError(f"{label} export payload is not repeatable: {signatures}")
    vertices, triangles = payloads[0]
    print(
        f"FIELD_CASE_COUPON_{label}_PAYLOAD_PASS "
        f"repeats={REPEAT_COUNT} vertices={len(vertices)} "
        f"triangles={len(triangles)} sha256={payload_digest(payloads[0])}",
        flush=True,
    )
    return payloads[0]


def validate_float32_stl_payload(payload) -> None:
    vertices, triangles = payload
    packed_vertices = tuple(
        struct.unpack("<fff", struct.pack("<fff", *vertex))
        for vertex in vertices
    )
    case.validate_triangle_payload(
        "Field_Case_TPU_Hinge_Coupon_Float32_STL",
        packed_vertices,
        triangles,
    )
    print(
        "FIELD_CASE_COUPON_FLOAT32_STL_PASS "
        f"vertices={len(packed_vertices)} triangles={len(triangles)}",
        flush=True,
    )


def check_coupon_export() -> None:
    case.clear_scene()
    case.set_units()
    material = case.make_material("Coupon_Export_Check", (1.0, 0.2, 0.05))
    coupon = case.create_tpu_hinge_coupon(material)
    case.validate_built_part("tpu_hinge_coupon", coupon)
    case.validate_tpu_hinge_coupon(coupon)

    stl_payload = repeated_strict_payload(
        coupon,
        Vector((0.0, 0.0, 0.0)),
        "STL_ZERO_ORIGIN",
    )
    validate_float32_stl_payload(stl_payload)

    project_origin = case.object_world_bounds(coupon)[0]
    repeated_strict_payload(coupon, project_origin, "3MF_MIN_ORIGIN")

    transformed = coupon.copy()
    transformed.data = coupon.data.copy()
    transformed.name = coupon.name + "_Translated_Rotated"
    case.bpy.context.collection.objects.link(transformed)
    transformed.location = (637.25, -418.75, 82.125)
    transformed.rotation_euler = (0.19, -0.31, 0.47)
    case.bpy.context.view_layer.update()
    transformed_origin = case.object_world_bounds(transformed)[0]
    repeated_strict_payload(
        transformed,
        transformed_origin,
        "3MF_TRANSFORMED_MIN_ORIGIN",
    )

    print(
        "FIELD_CASE_COUPON_EXPORT_REGRESSION_PASS "
        f"banks={len(case.TPU_HINGE_COUPON_THROATS)} "
        f"repeats_per_mode={REPEAT_COUNT} "
        "strict_manifold_validation=true float32_stl_validation=true",
        flush=True,
    )


if __name__ == "__main__":
    check_coupon_export()
