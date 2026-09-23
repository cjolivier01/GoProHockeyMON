"""Render actual before/after battery-door pockets and the updated lower insert.

blender --background --factory-startup --python this_file.py -- \
  --scene current-case.blend --baseline previous-case.blend --review-round 1
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
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--review-round', type=int, default=1)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    snapshots = []
    for path in (args.baseline, args.scene):
        bpy.ops.wm.open_mainfile(filepath=str(path.resolve()))
        names = json.loads(bpy.context.scene['cached_field_case_parts'])
        objects = [bpy.data.objects[names['fan_case_pair_insert']]]
        objects.extend(obj for obj in bpy.context.scene.objects if obj.name.startswith((
            'REFERENCE_ONLY_Fan_Case_Enduro_Battery_',
            'REFERENCE_ONLY_Fan_Case_Battery_Door_',
            'REFERENCE_ONLY_Fan_Case_Cable_Coil_',
            'REFERENCE_ONLY_Fan_Case_PWM_Plug_')))
        snapshots.append([(obj.name,
            [tuple(obj.matrix_world @ v.co) for v in obj.data.vertices],
            [tuple(p.vertices) for p in obj.data.polygons]) for obj in objects])
    case.clear_scene()
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1100
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.studio_light = 'paint.sl'
    scene.display.shading.color_type = 'OBJECT'
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = 'BOTH'
    scene.display.shading.show_object_outline = True
    scene.display.shading.background_type = 'WORLD'
    scene.world.color = (.025, .035, .055)
    scene.view_settings.view_transform = 'Standard'
    scene.display.render_aa = '32'
    camera = bpy.data.objects.new('Door_Access_Camera', bpy.data.cameras.new('Door_Access_Camera'))
    bpy.context.collection.objects.link(camera)
    camera.data.type = 'ORTHO'
    camera.data.clip_end = 2000
    scene.camera = camera
    visible = []

    def show(snapshot, offset_x=0, section=False):
        for name, vertices, faces in snapshot:
            obj = case.create_mesh_object('Preview_' + name, vertices, faces)
            if 'Lower_TPU_Insert' in name:
                obj.color = (.37, .44, .52, 1)
                if section:
                    cutter = case.add_rounded_box('Preview_Front_Section', (240, 63, 100),
                                                  (0, -51.5, 50), bevel=0)
                    case.boolean_apply(obj, cutter, 'INTERSECT')
            elif 'Battery_Door_' in name:
                obj.color = (1, .42, .08, 1)
            elif 'Battery_' in name:
                obj.color = (.62, .78, .89, 1)
            else:
                obj.color = (.08, .12, .16, 1)
            obj.location.x += offset_x
            visible.append(obj)

    def render(filename, position, target, scale, captions):
        camera.location = position
        camera.data.ortho_scale = scale
        aim(camera, target)
        captions = [*captions,
            (f'Review round {args.review_round} | Actual source-built geometry | Heights measured from insert underside',
             -scale * .465, -scale * .28, scale * .011)]
        labels = []
        for text, x, y, size in captions:
            position = Vector(target) + camera.rotation_euler.to_quaternion() @ Vector((x, y, scale))
            labels.append(label(camera, text, position, size))
        scene.render.filepath = str(DIRECTORY / 'renderings' / filename)
        bpy.ops.render.render(write_still=True)
        for obj in labels:
            bpy.data.objects.remove(obj, do_unlink=True)

    show(snapshots[0], -125, section=True)
    show(snapshots[1], 125, section=True)
    render('mission1_raised_battery_door_pockets.png', (0, -480, 360), (0, -50, 30), 520,
        [('BATTERY DOORS RAISED 11.76 mm', -241, 128, 8.5),
         ('Front section of the TPU insert / trays removed', -241, 112, 5.8),
         ('BEFORE', -231, 72, 7), ('AFTER / door tops match batteries', 19, 72, 7),
         ('Door floor: 13.8 mm', -231, -68, 6), ('Door floor: 25.56 mm', 19, -68, 6),
         ('Pocket rim: 24.8 mm', -231, -81, 6), ('Pocket rim: 36.56 mm', 19, -81, 6),
         ('Door top: 31.8 mm', -231, -94, 6), ('Door + battery tops: 43.56 mm', 19, -94, 6),
         ('11 mm seating depth and 7 mm exposed grip retained', -241, -122, 6)])
    for obj in visible:
        bpy.data.objects.remove(obj, do_unlink=True)
    visible.clear()
    show(snapshots[1])
    render('mission1_field_case_fan_case_insert_detail.png', (0, -310, 310), (0, 0, 36), 410,
        [('LEVEL BATTERY + DOOR TOPS / 43.56 mm', -190, 108, 6.5),
         ('Orange: battery doors / blue: batteries', -190, 94, 4.8),
         ('Lower insert also accepts handed 15-30 degree fans', -190, -102, 5.0)])
    print('BATTERY_DOOR_ACCESS_PREVIEWS_PASS', flush=True)


if __name__ == '__main__':
    main()
