"""Render the actual five integral TPU-85A slots, loaded tray and button air volumes.

blender --background --factory-startup --threads 8 --python-exit-code 1 \
  --python models3d/mission1-field-case/render_mission1_remote_slots.py \
  -- --scene /path/to/validated-field-case.blend --review-round 1
"""
import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DIRECTORY))
import mission1_field_case_blender as case
from render_mission1_latch_previews import aim, label


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--review-round', type=int, default=1)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
    names = json.loads(bpy.context.scene['cached_field_case_parts'])
    parts = {key: bpy.data.objects[name] for key, name in names.items()}
    refs = [obj for obj in bpy.context.scene.objects
            if obj.name.startswith('REFERENCE_ONLY_Field_Accessory_')]
    for obj in bpy.context.scene.objects:
        obj.hide_render = True
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1450
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'MATERIAL'
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = 'BOTH'
    scene.display.shading.show_object_outline = True
    scene.display.shading.background_type = 'WORLD'
    scene.world.color = (.035, .045, .065)
    scene.view_settings.view_transform = 'Standard'
    scene.display.render_aa = '32'
    camera = bpy.data.objects.new('Remote_Slots_Camera', bpy.data.cameras.new('Remote_Slots_Camera'))
    bpy.context.collection.objects.link(camera)
    camera.data.type = 'ORTHO'
    camera.data.clip_start = .1
    camera.data.clip_end = 3000
    scene.camera = camera
    previews = []
    colors = {'tray': (.85, .32, .055), 'tpu': (.20, .68, .43),
              'Custom': (.57, .38, .82), 'OEM': (.88, .63, .20),
              'coil': (.14, .54, .66), 'air': (.30, .85, 1.0)}

    def show(source, color, offset=(0, 0, 0), wire=False):
        obj = source.copy()
        obj.data = source.data.copy()
        bpy.context.collection.objects.link(obj)
        obj.hide_render = False
        obj.location += Vector(offset)
        obj.data.materials.clear()
        obj.data.materials.append(case.make_material('Preview_' + source.name, color))
        if wire:
            mod = obj.modifiers.new('Clearance_Outline', 'WIREFRAME')
            mod.thickness = .22
        previews.append(obj)
        return obj

    def clear():
        for obj in previews:
            bpy.data.objects.remove(obj, do_unlink=True)
        previews.clear()

    def render(name, position, target, scale, captions):
        camera.location = position
        camera.data.ortho_scale = scale
        aim(camera, target)
        labels = []
        footer = f'Review round {args.review_round} | Source geometry | Remote envelopes, not detailed button CAD'
        captions = [*captions, (footer, -scale * .46, -scale * .375, scale * .010)]
        for text, x, y, size in captions:
            location = Vector(target) + camera.rotation_euler.to_quaternion() @ Vector((x, y, scale))
            obj = label(camera, text, location, size)
            obj.data.materials.append(case.make_material('Preview_Text', (.95, .97, 1)))
            labels.append(obj)
        scene.render.filepath = str(DIRECTORY / 'renderings' / name)
        bpy.ops.render.render(write_still=True)
        for obj in labels:
            bpy.data.objects.remove(obj, do_unlink=True)

    show(parts['accessory_organizer'], colors['tpu'])
    for obj in refs:
        if 'Mount' not in obj.name:
            color = 'coil' if 'Coil' in obj.name else ('Custom' if 'Custom' in obj.name else 'OEM')
            show(obj, colors[color])
    render('mission1_remote_tray_loaded.png', (0, 0, 600), (0, 0, 138), 275,
           [('FIVE REMOTES / ORIGINAL TRAY ENVELOPE', -126, 98, 4.7),
            ('Cord: 154 mm diameter', -100, 4, 3.7), ('42 mm deep', -79, -4, 3.7),
            ('2 OEM', 62, 71, 3.5), ('3 custom', 57, -79, 3.5),
            ('223 x 169 x 46.3 mm tray / flat lid retained', -126, -97, 3.6)])
    clear()

    show(parts['accessory_organizer'], colors['tpu'])
    render('mission1_remote_slots.png', (290, -330, 640), (0, 0, 139), 310,
           [('ONE-PIECE TPU-85A TRAY / DEEP REMOTE SLOTS', -143, 110, 4.8),
            ('26 mm pocket depth / continuous side support', -143, 101, 3.7),
            ('Three custom slots + two OEM slots', -143, -100, 3.7),
            ('Original cord bay and outside dimensions', -143, -109, 3.7)])
    clear()

    rack = show(parts['accessory_organizer'], colors['tpu'])
    cutter = case.add_rounded_box('PREVIEW_ONLY_Slot_Bank', (67, 169, 70), (81, 0, 140), bevel=0)
    case.boolean_apply(rack, cutter, 'INTERSECT')
    for obj in refs:
        if 'remote_slot' in obj:
            color = 'Custom' if 'Custom' in obj.name else 'OEM'
            show(obj, colors[color], (0, 0, 26))
    render('mission1_remote_loading.png', (315, -340, 520), (80.25, -5.5, 147), 230,
           [('LOAD STRAIGHT DOWN / BUTTON EDGE UP', -94, 74, 3.7),
            ('Purple: custom controls    Gold: OEM backups', -94, 65, 2.9),
            ('Remotes raised 26 mm to show loading', -94, 58, 2.9),
            ('Slot-bank detail / integral with the whole tray', -105, -75, 3.0),
            ('Deep walls resist tipping; small end nubs grip the casing', -105, -82, 2.9)])
    clear()

    # Section through one integral OEM pocket exposes the recessed button air.
    spec = next(s for s in case.accessory_remote_specs() if s['id'] == 'OEM_2')
    body = next(o for o in refs if o.get('remote_slot') == spec['id'])
    rack = show(parts['accessory_organizer'], colors['tpu'])
    cutter = case.add_rounded_box('PREVIEW_ONLY_Remote_Section', (26, 42, 60), (93, 46, 145), bevel=0)
    case.boolean_apply(rack, cutter, 'INTERSECT')
    body_preview = show(body, colors['OEM'])
    cutter = case.add_rounded_box('PREVIEW_ONLY_Body_Section', (26, 42, 60), (93, 46, 145), bevel=0)
    case.boolean_apply(body_preview, cutter, 'INTERSECT')
    for probe in case.create_accessory_remote_keepouts(spec):
        show(probe, colors['air'], wire=True)
        bpy.data.objects.remove(probe, do_unlink=True)
    # Actual pad plane at maximum stack allowance, cropped for legibility.
    pad = show(parts['fan_case_pair_lid_pad'], (.4, .48, .55))
    pad.location, pad.rotation_euler = case.installed_flat_lid_pad_pose(0)
    pad.location.z -= case.FAN_CASE_PAIR_LID_STACK_TOLERANCE
    bpy.context.view_layer.update()
    cutter = case.add_rounded_box('PREVIEW_ONLY_Pad_Section', (26, 42, 10), (93, 46, 165), bevel=0)
    case.boolean_apply(pad, cutter, 'INTERSECT')
    render('mission1_remote_button_clearance.png', (325, -260, 290), (94, 25, 147), 132,
           [('OEM BUTTON CLEARANCE / CLOSED STACK', -60, 48, 2.6),
            ('Cyan: 3 mm front + 2 mm upper keep-outs', -60, 41, 2.0),
            ('3.4 mm actual headroom with stack allowance', -60, -42, 2.0),
            ('6 mm casing guides at each end: verify button positions', -60, -47, 1.9)])
    print('FIELD_CASE_REMOTE_SLOTS_PREVIEWS_COMPLETE', flush=True)


if __name__ == '__main__':
    main()
