"""Build and validate only the Mission 1 case latch load path.

Run from the repository root with::

    blender --background --factory-startup --threads 8 --python-exit-code 1 \
        --python models3d/mission1-field-case/check_mission1_field_case_latch.py
"""

from pathlib import Path
import hashlib
import struct
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission1_field_case_blender as case


FIXED_PART_BASELINES = {
    "base": (
        3713,
        2543,
        "9c985a41d75c3deee79660d402053b0b69c65271bf38ea5e1457deee10f7d31d",
    ),
    "lid": (
        4692,
        3370,
        "13b804a9c537bb009b7747d32a58f9bbfb4cf610c385e91034c9bba00aa5d75f",
    ),
}


def validate_fixed_part_compatibility(name, obj) -> None:
    expected_vertices, expected_polygons, expected_digest = FIXED_PART_BASELINES[name]
    assert len(obj.data.vertices) == expected_vertices
    assert len(obj.data.polygons) == expected_polygons
    canonical_coordinates = sorted(
        tuple(round(float(value), 5) for value in vertex.co)
        for vertex in obj.data.vertices
    )
    digest = hashlib.sha256()
    for coordinate in canonical_coordinates:
        digest.update(
            struct.pack(
                "<3q",
                *(round(value * 100000) for value in coordinate),
            )
        )
    assert digest.hexdigest() == expected_digest
    print(
        f"FIELD_CASE_FIXED_{name.upper()}_COMPATIBLE "
        f"vertices={expected_vertices} polygons={expected_polygons} "
        f"coordinate_sha256={expected_digest}",
        flush=True,
    )


def check_latch() -> None:
    expected_case_dimensions = (234.0, 158.0, 97.8)
    assert (
        case.CASE_WIDTH,
        case.CASE_DEPTH,
        case.BASE_HEIGHT,
    ) == expected_case_dimensions

    case.validate_configuration()
    case.clear_scene()
    case.set_units()
    material = case.make_material("Latch_Check", (0.4, 0.4, 0.4))
    base = case.create_base(material)
    lid, lid_inlay = case.create_lid(material, material)
    lever, hook = case.create_pelican_latch_parts(material)
    case.bpy.context.view_layer.update()
    parts = {
        "base": base,
        "lid": lid,
        "latch_lever": lever,
        "latch_hook": hook,
    }

    for name, obj in parts.items():
        case.validate_built_part(name, obj)
    validate_fixed_part_compatibility("base", base)
    validate_fixed_part_compatibility("lid", lid)
    case.validate_built_lid_capture_rails(lid)
    case.validate_built_latch_hook_capture(hook)
    case.validate_built_latch_impact_protectors(parts)
    case.validate_built_latch_fixed_m3_hardware(parts)
    case.validate_installed_latch_mechanics(parts)

    case.bpy.data.objects.remove(lid_inlay, do_unlink=True)
    print(
        "FIELD_CASE_LATCH_REGRESSION_PASS "
        f"case={case.CASE_WIDTH:.1f}x{case.CASE_DEPTH:.1f}x"
        f"{case.BASE_HEIGHT:.1f} "
        f"hook={case.LATCH_HOOK_OVERALL_LENGTH:.6f} "
        f"closed_angle={case.LATCH_LEVER_CLOSED_ANGLE:.2f}",
        flush=True,
    )


if __name__ == "__main__":
    check_latch()
