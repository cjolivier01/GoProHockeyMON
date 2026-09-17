"""Reject blocked tray vents and damaged material around their underside turns.

blender --background --factory-startup --threads 8 --python-exit-code 1 \
  --python models3d/mission1-field-case/check_mission1_air_channels.py \
  -- --scene /path/to/validated-field-case.blend

The case and both vented trays are built fresh. A cached scene may supply the
unchanged lower insert; omit --scene to build that loadout from source too.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission1_field_case_blender as case
from check_mission1_remote_slots import overlap
from check_mission1_alternate_closure import must_reject
from check_mission1_field_case_bottom_cables import arguments, load_or_build_loadout


def main():
    args = arguments()
    parts, _refs, _groups, _source = load_or_build_loadout(args.scene)
    material = case.make_material('Air_Channel_Check', (.4, .4, .4))
    for key, constructor in (
        ('base', case.create_base),
        ('fan_case_pair_carrier', case.create_fan_case_pair_overhead_carrier),
        ('fan_case_pair_storage_bin', case.create_fan_case_pair_storage_bin),
        ('accessory_organizer', case.create_accessory_organizer)):
        if args.scene:
            parts[key] = constructor(material)
        case.validate_built_part(key, parts[key])

    def check(changed=None):
        combined = {**parts, **(changed or {})}
        case.validate_accessory_air_channels(combined, overlap)
        case.validate_mount_tray_air_channels(combined, overlap)

    def mutate(key, name, size, center, operation, message):
        obj = parts[key].copy()
        obj.data = parts[key].data.copy()
        case.bpy.context.collection.objects.link(obj)
        cutter = case.add_rounded_box(name, size, center, bevel=0)
        case.boolean_apply(obj, cutter, operation)
        try:
            must_reject(lambda: check({key: obj}), message)
        finally:
            case.bpy.data.objects.remove(obj, do_unlink=True)

    check()
    for key, bounds_key in (('accessory_organizer', 'organizer_bounds'),
                            ('fan_case_pair_carrier', 'carrier_bounds')):
        bottom = case.FAN_CASE_PAIR_OVERHEAD_STORAGE[bounds_key][4]
        mutate(key, 'REGRESSION_Blocked_Outside_Vent', (5, 1, 1),
               (-80, -83.95, bottom + 22), 'UNION', 'air path blocked')
        # A side groove alone is insufficient: the underside opening must
        # cross the supporting rim into the cavity beneath the seated tray.
        mutate(key, 'REGRESSION_Filled_Underedge_Passage', (2, 5, 1.05),
               (-81.5, -82, bottom + .525), 'UNION', 'air path blocked')
        mutate(key, 'REGRESSION_Thin_Air_Passage_Floor', (1.8, 2, 1),
               (-81.5, -81.5, bottom + 2.75), 'DIFFERENCE', 'lacks its 2 mm floor')
        mutate(key, 'REGRESSION_Thin_Vent_Wall', (4, 2, 5),
               (-80, -81.5, bottom + 22), 'DIFFERENCE', 'lacks its 2 mm wall')
        mutate(key, 'REGRESSION_Missing_Central_Bearing_Rib', (.9, 2.2, .9),
               (-80, -81.5, bottom + .45), 'DIFFERENCE', 'central bearing rib is missing')
    # The lower tray's own geometry can be correct while its support blocks
    # the exit. Include the actual utility bin in the obstruction regression.
    bottom = case.FAN_CASE_PAIR_OVERHEAD_STORAGE['carrier_bounds'][4]
    mutate('fan_case_pair_storage_bin', 'REGRESSION_Blocked_Lower_Exit', (1, 2, .8),
           (-81.5, -80.5, bottom - .4), 'UNION', 'Mount tray air path blocked')
    print('FIELD_CASE_AIR_CHANNEL_REGRESSION_PASS trays=2 mutations=11', flush=True)


if __name__ == '__main__':
    main()
