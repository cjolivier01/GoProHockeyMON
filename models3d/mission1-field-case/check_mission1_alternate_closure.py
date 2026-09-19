"""Check the full alternate lid stack, including the last five closing degrees.

    blender --background --factory-startup --threads 8 --python-exit-code 1 \
      --python models3d/mission1-field-case/check_mission1_alternate_closure.py

Optional: -- --scene /path/to/current-field-case.blend reuses the expensive
unchanged cradle/reference meshes; the base, rear tray, pad, and both lids are rebuilt.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission1_field_case_blender as case
from check_mission1_field_case_bottom_cables import arguments, load_or_build_loadout
from check_mission1_field_case_latch import validate_fixed_part_compatibility


def must_reject(action, message):
    try:
        action()
    except ValueError as error:
        assert message in str(error), str(error)
        print(f'ALTERNATE_CLOSURE_REGRESSION_REJECTED {error}', flush=True)
    else:
        raise AssertionError(f'Invalid geometry accepted: {message}')


def main():
    args = arguments()
    parts, references, _groups, source = load_or_build_loadout(args.scene)
    references = [obj for obj in references if obj.name.startswith(('REFERENCE_ONLY_Fan_Case_', 'REFERENCE_ONLY_Field_Accessory_'))]
    material = case.make_material('Closure_Check', (0.5, 0.5, 0.5))
    if args.scene:
        parts['base'] = case.create_base(material)
        parts['fan_case_pair_carrier'] = case.create_fan_case_pair_overhead_carrier(material)
        parts['fan_case_pair_lid_pad'] = case.create_fan_case_pair_lid_pad(material)
        if case.EXPANDED_ACCESSORY_STORAGE:
            parts['accessory_organizer'] = case.create_accessory_organizer(material)
            references = [obj for obj in references if not obj.name.startswith('REFERENCE_ONLY_Field_Accessory_')]
            references.extend(case.create_accessory_reference_mockups(material))
    for key, profile in (('lid', case.HINGE_PROFILE_RIGID_SLIDE),
                         ('tpu_snap_lid', case.HINGE_PROFILE_TPU_68D_SNAP)):
        parts[key], inlay = case.create_lid(material, material, hinge_profile=profile)
        case.bpy.data.objects.remove(inlay, do_unlink=True)
    case.validate_configuration()
    for key in ('base', 'lid'):
        validate_fixed_part_compatibility(key, parts[key])
    for key in ('fan_case_pair_carrier', 'fan_case_pair_lid_pad'):
        case.validate_built_part(key, parts[key])
    case.validate_alternate_lid_closure(parts, references)

    # An unnotched top tray must expose the rigid key/rim collision.
    top_key = "accessory_organizer" if case.EXPANDED_ACCESSORY_STORAGE else "fan_case_pair_carrier"
    build_top = case.create_accessory_organizer if case.EXPANDED_ACCESSORY_STORAGE else case.create_fan_case_pair_overhead_carrier
    depth = case.FAN_CASE_PAIR_TRAY_KEY_NOTCH_DEPTH
    try:
        case.FAN_CASE_PAIR_TRAY_KEY_NOTCH_DEPTH = 0.0
        old_tray = build_top(material)
    finally:
        case.FAN_CASE_PAIR_TRAY_KEY_NOTCH_DEPTH = depth
    try:
        must_reject(lambda: case.validate_alternate_lid_closure(
            {**parts, top_key: old_tray}, references), 'closure obstructed')
    finally:
        case.bpy.data.objects.remove(old_tray, do_unlink=True)

    # Reject a contact face moved down by the former 1 mm compression and one
    # that consumes only the 0.2 mm allowance for a shorter printed base. The
    # upper form-fitting surface remains unchanged and still fits the lid.
    for invalid_drop in (1.0, 0.2):
        invalid_pad = parts['fan_case_pair_lid_pad'].copy()
        invalid_pad.data = parts['fan_case_pair_lid_pad'].data.copy()
        case.bpy.context.collection.objects.link(invalid_pad)
        for vertex in invalid_pad.data.vertices:
            vertex.co.z -= invalid_drop
        try:
            must_reject(lambda: case.validate_alternate_lid_closure(
                {**parts, 'fan_case_pair_lid_pad': invalid_pad}, references), 'pad presses')
        finally:
            case.bpy.data.objects.remove(invalid_pad, do_unlink=True)

    wrong_pad = case.create_fan_case_pair_lid_pad(material)
    for vertex in wrong_pad.data.vertices:
        vertex.co.x *= -1
        vertex.co.y *= -1
    try:
        must_reject(lambda: case.validate_alternate_lid_closure(
            {**parts, 'fan_case_pair_lid_pad': wrong_pad}, references), 'pad does not fit its lid')
    finally:
        case.bpy.data.objects.remove(wrong_pad, do_unlink=True)
    print(f'FIELD_CASE_ALTERNATE_CLOSURE_REGRESSION_PASS source={source}', flush=True)


if __name__ == '__main__':
    main()
