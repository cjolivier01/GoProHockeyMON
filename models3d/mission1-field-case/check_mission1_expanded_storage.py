"""Validate the expanded alternate case and reject realistic packing regressions.

    blender --background --factory-startup --threads 8 --python-exit-code 1 \
      --python models3d/mission1-field-case/check_mission1_expanded_storage.py \
      -- --scene /path/to/current-field-case.blend

Omit --scene to build the lower insert and camera references from source.
Cached mode reuses only those expensive, unchanged lower components.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission1_field_case_blender as case
from check_mission1_field_case_bottom_cables import arguments, load_or_build_loadout
from check_mission1_alternate_closure import must_reject


def main():
    args = arguments()
    parts, refs, _, source = load_or_build_loadout(args.scene)
    refs = [obj for obj in refs if obj.name.startswith('REFERENCE_ONLY_Fan_Case_')]
    material = case.make_material('Expanded_Storage_Check', (.4, .4, .4))
    for key, constructor in (
        ('base', case.create_base),
        ('fan_case_pair_carrier', case.create_fan_case_pair_overhead_carrier),
        ('fan_case_pair_storage_bin', case.create_fan_case_pair_storage_bin),
        ('accessory_organizer', case.create_accessory_organizer),
        ('remote_retainer', case.create_accessory_remote_retainer),
        ('fan_case_pair_lid_pad', case.create_fan_case_pair_lid_pad),
    ):
        parts[key] = constructor(material)
    for key, profile in (('lid', case.HINGE_PROFILE_RIGID_SLIDE),
                         ('tpu_snap_lid', case.HINGE_PROFILE_TPU_68D_SNAP)):
        parts[key], inlay = case.create_lid(material, material, hinge_profile=profile)
        case.bpy.data.objects.remove(inlay, do_unlink=True)
    accessories = case.create_accessory_reference_mockups(material)
    refs.extend(accessories)
    case.validate_configuration()
    for key, obj in parts.items():
        case.validate_built_part(key, obj)
    case.validate_accessory_storage(parts, refs)
    case.validate_alternate_lid_closure(parts, refs)

    mount = next(obj for obj in accessories if 'Mount' in obj.name)
    original = mount.location.copy()
    try:
        mount.location.x += 1000.0
        must_reject(lambda: case.validate_accessory_storage(parts, refs), 'outside assigned cavity')
    finally:
        mount.location = original
    original_projection = case.ACCESSORY_REMOTE_BUTTON_PROJECTION
    try:
        case.ACCESSORY_REMOTE_BUTTON_PROJECTION = 30.0
        big_refs = case.create_accessory_reference_mockups(material)
        try:
            must_reject(lambda: case.validate_accessory_storage(
                parts, [obj for obj in refs if obj not in accessories] + big_refs), 'outside assigned cavity')
        finally:
            for obj in big_refs:
                case.bpy.data.objects.remove(obj, do_unlink=True)
    finally:
        case.ACCESSORY_REMOTE_BUTTON_PROJECTION = original_projection

    # Block the allocated cable bay with a divider, leaving other trays valid.
    blocked = parts['accessory_organizer'].copy()
    blocked.data = parts['accessory_organizer'].data.copy()
    case.bpy.context.collection.objects.link(blocked)
    barrier = case.add_rounded_box('REGRESSION_Coil_Bay_Barrier', (4, 140, 25),
        (-29.5, 0, case.ACCESSORY_ORGANIZER_BOTTOM_Z + 16), bevel=0)
    case.union_into(blocked, barrier)
    try:
        must_reject(lambda: case.validate_accessory_storage(
            {**parts, 'accessory_organizer': blocked}, refs), 'envelope obstructed')
    finally:
        case.bpy.data.objects.remove(blocked, do_unlink=True)
    print(f'FIELD_CASE_EXPANDED_STORAGE_REGRESSION_PASS source={source}', flush=True)


if __name__ == '__main__':
    main()
