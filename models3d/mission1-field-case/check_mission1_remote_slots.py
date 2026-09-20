"""Reject missing slot walls, tipping, lost squeeze, button contact and tray resizing.

blender --background --factory-startup --threads 8 --python-exit-code 1 \
  --python models3d/mission1-field-case/check_mission1_remote_slots.py

The three affected assembly parts are built fresh; no lower camera cache needed.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission1_field_case_blender as case
from check_mission1_alternate_closure import must_reject


def overlap(a, b):
    case.bpy.context.view_layer.update()
    al, ah = case.object_world_bounds(a)
    bl, bh = case.object_world_bounds(b)
    if any(ah[i] <= bl[i] + 1e-5 or bh[i] <= al[i] + 1e-5 for i in range(3)):
        return 0.0
    return case.exact_transformed_intersection(
        a, b, first_location=a.location.copy(), first_rotation=a.rotation_euler.copy(),
        second_location=b.location.copy(), second_rotation=b.rotation_euler.copy())[1]


def main():
    case.clear_scene()
    case.set_units()
    material = case.make_material('Integral_Slots_Check', (.4, .4, .4))
    parts = {key: constructor(material) for key, constructor in (
        ('base', case.create_base),
        ('accessory_organizer', case.create_accessory_organizer),
        ('fan_case_pair_lid_pad', case.create_fan_case_pair_lid_pad))}
    refs = case.create_accessory_reference_mockups(material)
    for key, obj in parts.items():
        case.validate_built_part(key, obj)

    def check(changed=None, references=None):
        case.validate_accessory_remote_slots(
            {**parts, **(changed or {})}, refs if references is None else references, overlap)

    def mutate(key, name, size, center, operation, message):
        obj = parts[key].copy()
        obj.data = parts[key].data.copy()
        case.bpy.context.collection.objects.link(obj)
        tool = case.add_rounded_box(name, size, center, bevel=0)
        case.boolean_apply(obj, tool, operation)
        try:
            must_reject(lambda: check({key: obj}), message)
        finally:
            case.bpy.data.objects.remove(obj, do_unlink=True)

    check()
    # Remove one actual nub while preserving the surrounding deep slot walls.
    mutate('accessory_organizer', 'REGRESSION_Missing_Nub', (8.2, 1.2, 3.2),
           (60.75, -70.05, 139), 'DIFFERENCE', 'retention nub missing')
    # Four-corner probes must reject absent or shallow side walls.
    mutate('accessory_organizer', 'REGRESSION_Missing_Side_Wall', (1.5, 3, 22),
           (69.85, -66.75, 134), 'DIFFERENCE', 'full-depth side support')
    mutate('accessory_organizer', 'REGRESSION_Shallow_Side_Wall', (1.5, 3, 6),
           (69.85, -66.75, 143), 'DIFFERENCE', 'full-depth side support')
    # Cut the lengthwise guide strips, keeping all squeeze nubs and the four
    # side-support probes intact: the separate tipping check must catch it.
    tipping = parts['accessory_organizer'].copy()
    tipping.data = parts['accessory_organizer'].data.copy()
    case.bpy.context.collection.objects.link(tipping)
    for x in (55.5, 68.0):
        tool = case.add_rounded_box('REGRESSION_End_Guide_Tunnel',
            (0.9, 52, 24), (x, -47, 134.5), bevel=0)
        case.difference_from(tipping, tool)
    try:
        must_reject(lambda: check({'accessory_organizer': tipping}),
                    'tip without engaging slot walls')
    finally:
        case.bpy.data.objects.remove(tipping, do_unlink=True)
    # A rib in the recessed button air clears the reference remote body.
    mutate('accessory_organizer', 'REGRESSION_Front_Button_Rib', (1, 8, 20),
           (104, 25, 131), 'UNION', 'button clearance obstructed')
    mutate('accessory_organizer', 'REGRESSION_Unauthorized_Body_Contact', (2, 8, 20),
           (84, 25, 131), 'UNION', 'outside designated plain body patches')
    mutate('accessory_organizer', 'REGRESSION_Tray_Growth', (2, 8, 12),
           (111.5, 0, 128), 'UNION', 'outer dimensions changed')

    custom = next(obj for obj in refs if obj.get('remote_slot') == 'Custom_3')
    must_reject(lambda: check(references=[obj for obj in refs if obj != custom]),
                'three custom and two OEM')
    original = custom.location.copy()
    try:
        custom.location.x += .5
        must_reject(check, 'differs from its measured slot envelope')
    finally:
        custom.location = original

    original = case.ACCESSORY_REMOTE_GRIP_INTERFERENCE
    try:
        case.ACCESSORY_REMOTE_GRIP_INTERFERENCE = 0.0
        loose = case.create_accessory_organizer(material)
        try:
            must_reject(lambda: check({'accessory_organizer': loose}), 'lacks local squeeze retention')
        finally:
            case.bpy.data.objects.remove(loose, do_unlink=True)
    finally:
        case.ACCESSORY_REMOTE_GRIP_INTERFERENCE = original

    thick = parts['fan_case_pair_lid_pad'].copy()
    thick.data = parts['fan_case_pair_lid_pad'].data.copy()
    case.bpy.context.collection.objects.link(thick)
    for vertex in thick.data.vertices:
        vertex.co.z -= 3.0
    try:
        must_reject(lambda: check({'fan_case_pair_lid_pad': thick}),
                    'clearance below lid pad is insufficient')
    finally:
        case.bpy.data.objects.remove(thick, do_unlink=True)
    check()
    print('FIELD_CASE_REMOTE_SLOTS_REGRESSION_PASS mutations=11', flush=True)


if __name__ == '__main__':
    main()
