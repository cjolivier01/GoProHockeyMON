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


# Base baselines retain the authorized hinge-clearance reduction. Lid baselines
# include the thicker bearing lips and Sports AI artwork requested afterward.
COMPACT_FIXED_PART_BASELINES = {
    "base": (
        3713,
        2543,
        "8f5a3124dfd45c3747120c52cfae962bc67985edb365162b4a313c3c17b7c1f8",
    ),
    "lid": (
        4039, 2724,
        "4677757d976d46f41389ba455e1d5af9617cf6d01e7ddeb26f9d2bc476611c04",
    ),
}


# Expanded hardware revision: broaden the exterior latch mounts and handle
# lugs while preserving the authorized shell interior and storage dimensions.
# The full-thickness 119.8 mm handle places its fixed lugs at +/-52.8 mm.
# Only the expanded lid baseline changes for the raised hollow roof.
EXPANDED_FIXED_PART_BASELINES = {
    "base": (3719, 2546,
             "ff1cd59f17132bfc88df871d4f31b4c84c95a5338b71de6aa7de5e967c88f7a7"),
    "lid": (
        4676, 3358,
        "d12dd37f5399bc4ed21117e1e465149c1cc0c2137f1c649258fa9675668c952d",
    ),
}
FIXED_PART_BASELINES = (EXPANDED_FIXED_PART_BASELINES if case.EXPANDED_ACCESSORY_STORAGE
                        else COMPACT_FIXED_PART_BASELINES)


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
    expected_case_dimensions = ((234.0, 180.0, 160.0) if case.EXPANDED_ACCESSORY_STORAGE
                                else (234.0, 158.0, 97.8))
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

    # A localized weak section must fail even if the rest of the hook is solid.
    notched_hook = hook.copy()
    notched_hook.data = hook.data.copy()
    case.bpy.context.collection.objects.link(notched_hook)
    try:
        notch = case.add_rounded_box(
            "TEMPORARY_Weak_Hook_Web", (2.0, 2.0, 2.0),
            (7.0, -27.0, -6.3), bevel=0.0,
        )
        notched_hook.location = (0.0, 0.0, 0.0)
        notched_hook.rotation_euler = (0.0, 0.0, 0.0)
        case.difference_from(notched_hook, notch)
        try:
            case.validate_built_latch_hook_web(notched_hook)
        except ValueError as error:
            assert "continuous 3 mm solid core" in str(error), str(error)
        else:
            raise AssertionError("A locally thinned hook web was accepted")
    finally:
        case.bpy.data.objects.remove(notched_hook, do_unlink=True)
    print("FIELD_CASE_LATCH_WEAK_WEB_REJECTED", flush=True)

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
