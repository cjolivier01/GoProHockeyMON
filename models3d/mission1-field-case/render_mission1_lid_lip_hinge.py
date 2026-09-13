"""Render actual before/after lid sections and the Sports AI lid artwork.

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
    bpy.ops.wm.open_mainfile(filepath=str(args.baseline.resolve()))
    names = json.loads(bpy.context.scene['cached_field_case_parts'])
    previous = {}
    for key in ('lid', 'tpu_snap_lid'):
        obj = bpy.data.objects[names[key]]
        previous[key] = ([tuple(v.co) for v in obj.data.vertices],
                         [tuple(p.vertices) for p in obj.data.polygons])
    bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
    names = json.loads(bpy.context.scene['cached_field_case_parts'])
    parts = {key: bpy.data.objects[name] for key, name in names.items()}
    for obj in bpy.context.scene.objects:
        obj.hide_render = True
    for key, (vertices, polygons) in previous.items():
        mesh = bpy.data.meshes.new('Previous_' + key)
        mesh.from_pydata(vertices, [], polygons)
        obj = bpy.data.objects.new('Previous_' + key, mesh)
        bpy.context.collection.objects.link(obj)
        obj.hide_render = True
        previous[key] = obj
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1050
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.display.shading.light = 'FLAT'
    scene.display.shading.color_type = 'OBJECT'
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = 'BOTH'
    scene.display.shading.show_object_outline = True
    scene.display.shading.background_type = 'WORLD'
    scene.world.color = (.025, .035, .055)
    scene.view_settings.view_transform = 'Standard'
    scene.display.render_aa = '32'
    camera = bpy.data.objects.new('Lid_Review_Camera', bpy.data.cameras.new('Lid_Review_Camera'))
    bpy.context.collection.objects.link(camera)
    camera.data.type = 'ORTHO'
    camera.data.clip_end = 3000
    scene.camera = camera
    previews = []

    def copy(source, color, offset_y=0, section=None, pose=None):
        obj = source.copy()
        obj.data = source.data.copy()
        bpy.context.collection.objects.link(obj)
        obj.hide_render = False
        if pose:
            obj.location, obj.rotation_euler = pose
        bpy.context.view_layer.update()
        if section:
            case.select_only(obj)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            cutter = case.add_rounded_box('Preview_Section_Cutter', section[1], section[0], bevel=0)
            case.boolean_apply(obj, cutter, 'INTERSECT', solver='EXACT')
        obj.location.y += offset_y
        obj.color = color
        previews.append(obj)
        return obj

    def clear():
        for obj in previews:
            bpy.data.objects.remove(obj, do_unlink=True)
        previews.clear()

    def render(filename, position, target, scale, captions):
        camera.location = position
        camera.data.ortho_scale = scale
        aim(camera, target)
        labels = []
        captions = [*captions, (f'Review round {args.review_round} | Actual source-built meshes | Dimensions in mm',
                                -scale * .46, -scale * .268, scale * .011)]
        for text, x, y, size in captions:
            location = Vector(target) + camera.rotation_euler.to_quaternion() @ Vector((x, y, scale))
            labels.append(label(camera, text, location, size))
        scene.render.filepath = str(DIRECTORY / 'renderings' / filename)
        bpy.ops.render.render(write_still=True)
        for obj in labels:
            bpy.data.objects.remove(obj, do_unlink=True)

    shell, rigid, tpu, hardware = (.22, .27, .34, 1), (.30, .60, .85, 1), (1, .43, .10, 1), (.42, .76, .55, 1)
    section = ((82, -96, 161), (1.4, 25, 21))
    hook = parts['latch_hook'].copy()
    hook.data = parts['latch_hook'].data.copy()
    bpy.context.collection.objects.link(hook)
    hook.hide_render = True
    case.position_installed_latch_hook(hook, 82)
    bpy.context.view_layer.update()
    hook_pose = (hook.location.copy(), hook.rotation_euler.copy())
    for source, color, shift in ((previous['lid'], (.62, .66, .72, 1), -29),
                                 (parts['lid'], rigid, 0), (parts['tpu_snap_lid'], tpu, 29)):
        copy(parts['base'], shell, shift, section=section)
        copy(source, color, shift, section=section, pose=case.installed_lid_pose(0))
        copy(hook, hardware, shift, section=section, pose=hook_pose)
    render('mission1_lid_lip_thickness.png', (482, -96, 161), (82, -96, 161), 95,
           [('LATCH-BEARING LIP / same contact height', -44, 24, 2.2),
            ('Previous: 2.4', -40, 15, 2.0), ('Rigid: 3.2', -11, 15, 2.0), ('68D TPU: 4.0', 17, 15, 2.0),
            ('Added material supports the lip from below; latch take-up stays the same.', -44, -19, 1.5)])
    clear()
    bpy.data.objects.remove(hook, do_unlink=True)

    x0, x1 = case.lid_hinge_segments(case.HINGE_PROFILE_TPU_68D_SNAP)[0]
    cx = case.LID_DISPLAY_OFFSET_X + (x0 + x1) / 2
    cy, cz = -case.HINGE_AXIS_Y, case.LID_WALL_HEIGHT
    section = ((cx, cy, cz), (1.0, 15, 15))
    for source, color, shift in ((previous['tpu_snap_lid'], (.62, .66, .72, 1), -11),
                                 (parts['tpu_snap_lid'], tpu, 11)):
        copy(source, color, shift, section=section)
        rod = case.add_cylinder_x('Preview_Seated_3p8_Rod', 1.9, 1.1, (cx, cy + shift, cz), vertices=96)
        rod.color = (.32, .68, .86, 1)
        previews.append(rod)
    render('mission1_tpu_hinge_snap_comparison.png', (cx + 300, cy, cz), (cx, cy, cz), 45,
           [('TPU HINGE / closer snap entrance', -21, 11, 1.15),
            ('Previous: 3.6 opening', -19, 7, .85), ('Revised: 3.5 opening', 2, 7, .85),
            ('0.2 interference', -18, -7, .8), ('0.3 interference', 3, -7, .8),
            ('Same 3.8 rod and 4.55 seated receiver; revised throat length 1.55.', -21, -10, .62)])
    clear()

    copy(parts['lid'], (.09, .12, .16, 1), pose=case.installed_lid_pose(0))
    copy(parts['logo_orange_inlay'], (1, .34, .025, 1), pose=case.installed_lid_pose(0))
    render('mission1_sports_ai_lid.png', (0, -180, 600), (0, 0, 166), 440,
           [('SPORTS AI / same Neuropol lettering style', -202, 113, 8),
            ('Flush orange inlay shared by the rigid and 68D TPU lids', -202, -99, 6)])
    print('LID_LIP_HINGE_PREVIEWS_PASS', flush=True)


if __name__ == '__main__':
    main()
