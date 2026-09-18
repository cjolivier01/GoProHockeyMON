"""Build and validate only the Mission 1 case latch load path.

Run from the repository root with::

    blender --background --factory-startup --threads 8 --python-exit-code 1 \
        --python models3d/mission1-field-case/check_mission1_field_case_latch.py
"""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission1_field_case_blender as case


def validate_fixed_part_compatibility(name, obj) -> None:
    """Check the preserved interior surfaces, allowing authorized exterior edits."""
    from mathutils import Vector
    depth = 180.0 if case.EXPANDED_ACCESSORY_STORAGE else 158.0
    height = 160.0 if case.EXPANDED_ACCESSORY_STORAGE else 97.8
    assert (case.CASE_WIDTH, case.CASE_DEPTH, case.BASE_HEIGHT) == (234.0, depth, height)
    if name == "base":
        # Measure at the cardinal tangencies so polygon faceting cannot
        # obscure the actual nominal dimensions. Avoid the tray bearing rails.
        xt, yt = 117 - case.CASE_CORNER_RADIUS, depth / 2 - case.CASE_CORNER_RADIUS
        rays = [((0, yt, 60), (1, 0, 0), 112.5),
                ((0, -yt, 60), (-1, 0, 0), 112.5),
                ((-xt, 0, 60), (0, 1, 0), depth / 2 - 4.5),
                ((xt, 0, 60), (0, -1, 0), depth / 2 - 4.5),
                ((0, 0, 20), (0, 0, -1), 16.8)]
    else:
        rays = [((case.LID_DISPLAY_OFFSET_X, 0, 10), (0, 0, -1), 6.0 + case.LID_DOME_RISE)]
    for origin, direction, distance in rays:
        hit, point, _normal, _index = obj.ray_cast(Vector(origin), Vector(direction))
        assert hit, (name, origin, direction)
        assert abs((point - Vector(origin)).length - distance) < 0.001, (name, point, distance)
    print(f"FIELD_CASE_{name.upper()}_INTERIOR_COMPATIBLE", flush=True)


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
