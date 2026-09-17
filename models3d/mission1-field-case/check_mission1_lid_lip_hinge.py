"""Check reinforced lid lips and reject weak-lip/wide-snap regressions.

Run with Blender --background --factory-startup --python-exit-code 1 --python
this_file.py. Optional -- --scene /path/to/current-case.blend reuses a current
source-built scene; without it the affected parts and mating hardware are built.
"""
import argparse
import json
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
        print('LID_LIP_HINGE_REGRESSION_REJECTED', str(error), flush=True)
    else:
        raise AssertionError(f'Regression accepted: {expected}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scene', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    if args.scene:
        case.bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
        names = json.loads(case.bpy.context.scene['cached_field_case_parts'])
        parts = {key: case.bpy.data.objects[name] for key, name in names.items()}
    else:
        case.clear_scene()
        case.set_units()
        material = case.make_material('Lid_Lip_Hinge_Check', (.4, .4, .4))
        parts = {'base': case.create_base(material)}
        parts['latch_lever'], parts['latch_hook'] = case.create_pelican_latch_parts(material)
        for key, profile in (('lid', case.HINGE_PROFILE_RIGID_SLIDE),
                             ('tpu_snap_lid', case.HINGE_PROFILE_TPU_68D_SNAP)):
            parts[key], inlay = case.create_lid(material, material, hinge_profile=profile)
            case.bpy.data.objects.remove(inlay, do_unlink=True)
        parts['tpu_hinge_coupon'] = case.create_tpu_hinge_coupon(material)
    case.bpy.context.view_layer.update()
    case.validate_configuration()
    validate_fixed_part_compatibility('base', parts['base'])
    for key in ('lid', 'tpu_snap_lid'):
        lid = parts[key]
        case.validate_built_part(key, lid)
        case.validate_built_lid_capture_rails(lid)
        case.validate_installed_case_closure({**parts, 'lid': lid})
        case.validate_installed_case_hinge_sweep({**parts, 'lid': lid})
        case.validate_installed_latch_mechanics({**parts, 'lid': lid})
        weak = lid.copy()
        weak.data = lid.data.copy()
        case.bpy.context.collection.objects.link(weak)
        # Remove a short central strip down to the previous 2.4 mm lip.
        old_bottom = case.LID_LATCH_LOAD_LEDGE_CONTACT_Z + 2.4
        cutter = case.add_rounded_box('REGRESSION_Thin_Lid_Lip', (2.0, 10.0, 4.0),
            (case.LID_DISPLAY_OFFSET_X + case.LATCH_X_CENTERS[0],
             case.LID_LATCH_CAPTURE_RAIL_CENTER_Y - 1.0, old_bottom + 2.0), bevel=0.0)
        cutter.location.z += case.LID_DOME_RISE
        case.difference_from(weak, cutter)
        try:
            must_reject(lambda: case.validate_built_lid_capture_rails(weak), 'full')
        finally:
            case.bpy.data.objects.remove(weak, do_unlink=True)
    case.validate_tpu_snap_lid(parts['tpu_snap_lid'])
    case.validate_tpu_hinge_coupon(parts['tpu_hinge_coupon'])
    wide = parts['tpu_snap_lid'].copy()
    wide.data = wide.data.copy()
    case.bpy.context.collection.objects.link(wide)
    for x0, x1 in case.lid_hinge_segments(case.HINGE_PROFILE_TPU_68D_SNAP):
        cutter = case.extrude_loop_x('REGRESSION_Wide_TPU_Throat',
            case.hinge_slot_loop_yz(-case.HINGE_AXIS_Y, case.LID_WALL_HEIGHT,
                case.HINGE_PROFILE_TPU_68D_SNAP, throat_width=3.6),
            case.LID_DISPLAY_OFFSET_X + x0 - .01, case.LID_DISPLAY_OFFSET_X + x1 + .01)
        cutter.location.z += case.LID_DOME_RISE
        case.difference_from(wide, cutter)
    try:
        must_reject(lambda: case.validate_tpu_snap_lid(wide), 'calibrated throat')
    finally:
        case.bpy.data.objects.remove(wide, do_unlink=True)
    print('LID_LIP_HINGE_REGRESSION_PASS', flush=True)


if __name__ == '__main__':
    main()
