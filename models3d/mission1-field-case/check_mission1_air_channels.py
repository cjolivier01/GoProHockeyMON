"""Reject blocked tray vents and damaged material around their underside turns.

blender --background --factory-startup --threads 8 --python-exit-code 1 \
  --python models3d/mission1-field-case/check_mission1_air_channels.py
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission1_field_case_blender as case
from check_mission1_remote_slots import overlap
from check_mission1_alternate_closure import must_reject


def main():
    case.clear_scene()
    case.set_units()
    material = case.make_material('Air_Channel_Check', (.4, .4, .4))
    parts = {key: constructor(material) for key, constructor in (
        ('base', case.create_base),
        ('fan_case_pair_carrier', case.create_fan_case_pair_overhead_carrier),
        ('accessory_organizer', case.create_accessory_organizer))}
    tray = parts['accessory_organizer']
    for key, obj in parts.items():
        case.validate_built_part(key, obj)

    def check(changed=None):
        case.validate_accessory_air_channels({**parts, **(changed or {})}, overlap)

    def mutate(name, size, center, operation, message):
        obj = tray.copy()
        obj.data = tray.data.copy()
        case.bpy.context.collection.objects.link(obj)
        cutter = case.add_rounded_box(name, size, center, bevel=0)
        case.boolean_apply(obj, cutter, operation)
        try:
            must_reject(lambda: check({'accessory_organizer': obj}), message)
        finally:
            case.bpy.data.objects.remove(obj, do_unlink=True)

    check()
    mutate('REGRESSION_Blocked_Outside_Vent', (5, 1, 1),
           (-80, -83.95, 140), 'UNION', 'air path blocked')
    # A side groove alone is insufficient: the lower tray seals the underside
    # until the opening crosses its bearing rim into the cavity.
    mutate('REGRESSION_Filled_Underedge_Passage', (2, 5, 1.05),
           (-81.5, -82, 118.525), 'UNION', 'air path blocked')
    mutate('REGRESSION_Thin_Air_Passage_Floor', (1.8, 2, 1),
           (-81.5, -81.5, 120.75), 'DIFFERENCE', 'lacks its 2 mm floor')
    mutate('REGRESSION_Thin_Vent_Wall', (4, 2, 5),
           (-80, -81.5, 140), 'DIFFERENCE', 'lacks its 2 mm wall')
    mutate('REGRESSION_Missing_Central_Bearing_Rib', (.9, 2.2, .9),
           (-80, -81.5, 118.45), 'DIFFERENCE', 'central bearing rib is missing')
    print('FIELD_CASE_AIR_CHANNEL_REGRESSION_PASS mutations=5', flush=True)


if __name__ == '__main__':
    main()
