"""Render source-generated replacement handle and installed Allen access.

Run in background Blender; optional arguments: -- --review-round 1.
"""
import argparse
import math
from pathlib import Path
import subprocess
import sys

import bpy
from mathutils import Vector

DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DIRECTORY))
import mission1_field_case_blender as case
from render_mission1_latch_previews import aim, label


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--review-round', type=int, default=0)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    case.clear_scene()
    case.set_units()
    orange = case.make_material('Handle_Orange', (.94, .30, .06))
    gray = case.make_material('Case_Gray', (.22, .28, .36))
    handle = case.create_pivoting_handle_bar(orange)
    handle.color = (.94, .30, .06, 1)
    source = subprocess.check_output(
        ['git', 'show', 'dc2d805:models3d/mission1-field-case/mission1_field_case_blender.py'],
        cwd=DIRECTORY, text=True,
    )
    baseline = {'__name__': 'handle_baseline', '__file__': case.__file__}
    exec(compile(source, case.__file__, 'exec'), baseline)
    old = baseline['create_pivoting_handle_bar'](gray)
    old.color = (.40, .46, .54, 1)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = 1700
    scene.render.resolution_y = 1100
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'OBJECT'
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = 'BOTH'
    scene.display.shading.show_object_outline = True
    scene.display.shading.background_type = 'WORLD'
    scene.world.color = (.035, .045, .065)
    scene.view_settings.view_transform = 'Standard'
    scene.display.render_aa = '32'
    camera = bpy.data.objects.new('Handle_Review_Camera', bpy.data.cameras.new('Handle_Review_Camera'))
    bpy.context.collection.objects.link(camera)
    camera.data.type = 'ORTHO'
    camera.data.clip_start = .1
    camera.data.clip_end = 2000
    scene.camera = camera
    (DIRECTORY / 'renderings').mkdir(exist_ok=True)

    def render(filename, position, target, scale, captions):
        camera.location = position
        camera.data.ortho_scale = scale
        aim(camera, target)
        labels = []
        for text, x, y, size in captions:
            point = Vector(target) + camera.rotation_euler.to_quaternion() @ Vector((x, y, scale))
            labels.append(label(camera, text, point, size))
        point = Vector(target) + camera.rotation_euler.to_quaternion() @ Vector((-scale*.46, -scale*.29, scale))
        labels.append(label(camera, f'Review round {args.review_round}  |  Source-generated geometry', point, scale*.010))
        scene.render.filepath = str(DIRECTORY / 'renderings' / filename)
        bpy.ops.render.render(write_still=True)
        for obj in labels:
            bpy.data.objects.remove(obj, do_unlink=True)

    old.location = (-57, 0, 0)
    handle.location = (57, 0, 0)
    render('mission1_handle_comparison.png', (65, -150, 220), (0, -17, 5), 244,
           [('BEFORE / perforated 11 x 12.2 mm grip', -114,  60, 3.2),
            ('NEW / solid 16 x 18 mm grip', 9, 60, 3.2),
            ('Continuous fork cheeks; existing base and lid fit', -107, -50, 3.1),
            ('75 mm at grip / 66.8 mm between reinforced forks', -107, -58, 3.1)])
    old.hide_render = True
    handle.location = (0, case.HANDLE_PIVOT_Y + case.HANDLE_LOCAL_PIVOT_Z, case.HANDLE_PIVOT_Z)
    handle.rotation_euler = (math.pi / 2, 0, 0)
    base = case.create_base(gray)
    lid, inlay = case.create_lid(gray, orange)
    for obj in (base, lid):
        obj.color = (.22, .28, .36, 1)
    inlay.hide_render = True
    lid.location, lid.rotation_euler = case.installed_lid_pose(0)
    lever, hook = case.create_pelican_latch_parts(orange)
    for x in case.LATCH_X_CENTERS:
        for original, positioner in ((lever, case.position_installed_latch_lever), (hook, case.position_installed_latch_hook)):
            obj = original.copy()
            obj.data = original.data.copy()
            bpy.context.collection.objects.link(obj)
            obj.color = (.58, .65, .73, 1)
            positioner(obj, x)
        case.create_latch_fixed_m3_reference_hardware('Latch_Reference', x)
    lever.hide_render = hook.hide_render = True
    for side in (-1, 1):
        for obj in case.create_handle_m3_reference_hardware('Handle_Reference', side, case.HANDLE_PIVOT_Y, case.HANDLE_PIVOT_Z):
            obj.color = (.76, .80, .86, 1)
    render('mission1_handle_installed.png', (150, -310, 160), (0, -72, 55), 246,
           [('SOLID CARRY HANDLE / existing case and lid', -112, 66, 3.5),
            ('Nuts face the latch protectors; Allen heads face the center', -112, -62, 3.0)])
    # A bent reference L-key in the center corridor. Its dimensioned conservative
    # insertion/turn envelopes are tested separately by the generator.
    side = 1
    head_x, _, direction = case.handle_m3_pivot_faces(side)
    bend_x = head_x + direction * case.HANDLE_ALLEN_SHORT_LEG
    pz, py = case.HANDLE_PIVOT_Z, case.HANDLE_PIVOT_Y
    curve = bpy.data.curves.new('2p5mm_Allen_Key', 'CURVE')
    curve.dimensions = '3D'
    curve.bevel_depth = 2.5 / math.sqrt(3)
    curve.bevel_resolution = 3
    spline = curve.splines.new('POLY')
    radius = case.HANDLE_ALLEN_BEND_RADIUS
    points = [(head_x + 1.5, py, pz), (bend_x + radius, py, pz)]
    points.extend((bend_x + radius - radius * math.sin(math.radians(a)),
                   py - radius + radius * math.cos(math.radians(a)), pz) for a in range(5, 91, 5))
    points.append((bend_x, py - case.HANDLE_ALLEN_LONG_LEG, pz))
    spline.points.add(len(points) - 1)
    for point, xyz in zip(spline.points, points):
        point.co = (*xyz, 1)
    key = bpy.data.objects.new('Allen_Key_Inboard_Access', curve)
    bpy.context.collection.objects.link(key)
    key.color = (.20, .88, .64, 1)
    render('mission1_handle_allen_access.png', (-110, -265, 155), (0, -108, 42), 159,
           [('INBOARD ALLEN ACCESS / handle folded', -74, 43, 2.6),
            [('25 x 70 mm L-key / 60-degree tightening sector'), -74, -43, 2.15]])
    print('FIELD_CASE_HANDLE_PREVIEWS_COMPLETE', flush=True)


if __name__ == '__main__':
    main()
