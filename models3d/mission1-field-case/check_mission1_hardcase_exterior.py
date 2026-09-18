"""Check rounded shell printing geometry and retained packing contacts.

Run with Blender --background --factory-startup --python-exit-code 1 --python
this_file.py. This intentionally builds only the changed shell/pad components.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission1_field_case_blender as case
from check_mission1_field_case_latch import validate_fixed_part_compatibility


def must_reject(action, text):
    try:
        action()
    except (ValueError, AssertionError) as error:
        if text:
            assert text in str(error), str(error)
        print('EXTERIOR_REGRESSION_REJECTED', str(error), flush=True)
    else:
        raise AssertionError('Accepted regression: ' + text)


def main():
    case.clear_scene()
    case.set_units()
    material = case.make_material('Exterior_Check', (.4, .4, .4))
    parts = {'base': case.create_base(material),
             'fan_case_pair_lid_pad': case.create_fan_case_pair_lid_pad(material)}
    for key, profile in (('lid', case.HINGE_PROFILE_RIGID_SLIDE),
                         ('tpu_snap_lid', case.HINGE_PROFILE_TPU_68D_SNAP)):
        parts[key], inlay = case.create_lid(material, material, profile)
        case.bpy.data.objects.remove(inlay, do_unlink=True)
    for key, obj in parts.items():
        case.validate_built_part(key, obj)
    for key in ('base', 'lid'):
        validate_fixed_part_compatibility(key, parts[key])
    case.validate_built_hardcase_exterior(parts)
    case.validate_raised_lid_pad(parts)

    # A broad shelf over a side shoulder must not become an accepted bridge.
    shelf_lid = parts['lid'].copy()
    shelf_lid.data = shelf_lid.data.copy()
    case.bpy.context.collection.objects.link(shelf_lid)
    shelf = case.add_rounded_box('REGRESSION_Unsupported_Side_Shelf',
        (14, 30, 2), (case.LID_DISPLAY_OFFSET_X + 115, 0, case.LID_DOME_RISE - 2), bevel=0)
    case.union_into(shelf_lid, shelf)
    try:
        must_reject(lambda: case.validate_built_hardcase_exterior(
            {**parts, 'lid': shelf_lid}), 'outside the hardware bridges')
    finally:
        case.bpy.data.objects.remove(shelf_lid, do_unlink=True)

    if case.LID_DOME_RISE:
        pad = parts['fan_case_pair_lid_pad']
        short_pad = pad.copy()
        short_pad.data = pad.data.copy()
        case.bpy.context.collection.objects.link(short_pad)
        cutter = case.add_rounded_box('REGRESSION_Short_Roof_Spacer', (250, 190, 4),
            (case.LID_DISPLAY_OFFSET_X, case.FAN_CASE_PAIR_LID_PAD_DISPLAY_Y, 26), bevel=0)
        case.difference_from(short_pad, cutter)
        try:
            must_reject(lambda: case.validate_raised_lid_pad(
                {**parts, 'fan_case_pair_lid_pad': short_pad}), 'does not reach the roof')
        finally:
            case.bpy.data.objects.remove(short_pad, do_unlink=True)
    print('FIELD_CASE_HARDCASE_EXTERIOR_REGRESSION_PASS', flush=True)


if __name__ == '__main__':
    main()
