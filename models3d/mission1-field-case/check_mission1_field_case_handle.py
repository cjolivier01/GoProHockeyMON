"""Validate the Mission 1 replacement handle, hardware and installed tool access.

    blender --background --factory-startup --threads 8 --python-exit-code 1 \
      --python models3d/mission1-field-case/check_mission1_field_case_handle.py
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission1_field_case_blender as case
from check_mission1_field_case_latch import validate_fixed_part_compatibility


def must_reject(action, expected):
    try:
        action()
    except ValueError as error:
        assert expected in str(error), str(error)
    else:
        raise AssertionError(f"Invalid geometry accepted: {expected}")


def main():
    case.clear_scene()
    case.set_units()
    case.validate_configuration()
    material = case.make_material('Handle_Check', (0.4, 0.4, 0.4))
    base = case.create_base(material)
    lid, inlay = case.create_lid(material, material)
    lever, hook = case.create_pelican_latch_parts(material)
    handle = case.create_pivoting_handle_bar(material)
    parts = dict(base=base, lid=lid, latch_lever=lever, latch_hook=hook, handle_bar=handle)
    for name, obj in parts.items():
        case.validate_built_part(name, obj)
    for name in ('base', 'lid'):
        validate_fixed_part_compatibility(name, parts[name])
    case.validate_built_handle_strength(handle)
    case.validate_built_handle_m3_hardware(parts)
    case.validate_installed_handle_mechanics(parts)
    case.validate_installed_handle_allen_access(parts)

    # Reject a local weak fork even when most of the handle remains solid.
    weak = handle.copy()
    weak.data = handle.data.copy()
    case.bpy.context.collection.objects.link(weak)
    weak.location = (0, 0, 0)
    notch = case.add_rounded_box('TEMPORARY_Weak_Fork', (3, 2, 3), (38.1, -11.5, 6.1), bevel=0)
    case.difference_from(weak, notch)
    must_reject(lambda: case.validate_built_handle_strength(weak), 'solid load path')
    case.bpy.data.objects.remove(weak, do_unlink=True)

    # Put an obstruction in the long-leg turning path, away from the socket.
    obstruction = case.add_rounded_box('TEMPORARY_Blocked_Allen_Turn', (6, 6, 6),
                                       (8.4, case.HANDLE_PIVOT_Y - 30, case.HANDLE_PIVOT_Z), bevel=0)
    case.select_only(obstruction)
    case.bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    must_reject(lambda: case.validate_installed_handle_allen_access({**parts, 'base': obstruction}),
                'Allen access blocked')
    case.bpy.data.objects.remove(obstruction, do_unlink=True)

    bolt_length = case.HANDLE_M3_BOLT_LENGTH
    try:
        case.HANDLE_M3_BOLT_LENGTH = 12.0
        must_reject(case.validate_configuration, 'fully engage')
    finally:
        case.HANDLE_M3_BOLT_LENGTH = bolt_length
    print('FIELD_CASE_HANDLE_REGRESSION_PASS weak_fork=reject blocked_key=reject short_bolt=reject')


if __name__ == '__main__':
    main()
