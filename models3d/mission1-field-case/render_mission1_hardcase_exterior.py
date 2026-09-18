"""Render the actual revised shell and its two source references for review."""
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
import build_hardcase as reference


def configure(review_round):
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x, scene.render.resolution_y = 1600, 1200
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.studiolight_rotate_z = math.radians(25)
    scene.display.shading.color_type = 'OBJECT'
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = 'BOTH'
    scene.display.shading.show_object_outline = True
    scene.display.shading.background_type = 'WORLD'
    scene.world.color = (.055, .065, .08)
    scene.view_settings.view_transform = 'Standard'
    scene.display.render_aa = '32'
    scene.render.use_stamp = True
    for field in ('date', 'time', 'render_time', 'frame', 'frame_range', 'memory',
                  'hostname', 'camera', 'lens', 'scene', 'marker', 'filename'):
        setattr(scene.render, 'use_stamp_' + field, False)
    scene.render.use_stamp_note = True
    scene.render.stamp_note_text = ('Initial proposal - before reviews' if review_round == 0
                                    else f'After review round {review_round}')
    scene.render.stamp_font_size = 20
    camera = bpy.data.objects.new('Exterior_Review_Camera', bpy.data.cameras.new('Exterior_Review_Camera'))
    bpy.context.collection.objects.link(camera)
    camera.data.type = 'ORTHO'
    camera.data.clip_end = 3000
    scene.camera = camera
    return camera


def render(camera, filename, position, target, scale):
    camera.location = position
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.ortho_scale = scale
    bpy.context.scene.render.filepath = str(DIRECTORY / 'renderings' / filename)
    bpy.ops.render.render(write_still=True)


def build_parts(module):
    shell = module.make_material('Exterior_Shell', (.26, .32, .39))
    orange = module.make_material('Exterior_Orange', (.95, .28, .04))
    base = module.create_base(shell)
    lid, inlay = module.create_lid(shell, orange)
    handle = module.create_pivoting_handle_bar(shell)
    lever, hook = module.create_pelican_latch_parts(shell)
    for obj in (base, lid, handle):
        obj.color = (.26, .32, .39, 1)
    inlay.color = (.95, .28, .04, 1)
    lid.location, lid.rotation_euler = module.installed_lid_pose(0)
    inlay.location, inlay.rotation_euler = module.installed_lid_pose(0)
    for index, x in enumerate(module.LATCH_X_CENTERS):
        if index:
            lever = lever.copy(); lever.data = lever.data.copy()
            hook = hook.copy(); hook.data = hook.data.copy()
            bpy.context.collection.objects.link(lever)
            bpy.context.collection.objects.link(hook)
        module.position_installed_latch_lever(lever, x)
        module.position_installed_latch_hook(hook, x)
        lever.color = hook.color = (.12, .15, .19, 1)
    handle.rotation_euler.x = math.radians(90)
    handle.location = (0, module.HANDLE_PIVOT_Y + module.HANDLE_LOCAL_PIVOT_Z,
                       module.HANDLE_PIVOT_Z)
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and not obj.hide_render:
            reference.shade_auto_smooth(obj)
    bpy.context.view_layer.update()
    return base, lid, inlay


def main():
    import types
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-round", type=int, default=0)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    case.clear_scene()
    case.set_units()
    camera = configure(args.review_round)
    base, lid, inlay = build_parts(case)
    for name, position, target, scale in (
        ('front', (370, -510, 345), (0, 0, 85), 390),
        ('rear', (-365, 510, 320), (0, 0, 85), 340),
        ('side', (500, -50, 140), (0, 0, 95), 330),
        ('rim', (310, -460, 250), (40, -65, 149), 195),
    ):
        render(camera, f'mission1_hardcase_{name}.png', position, target, scale)
    for obj in bpy.data.objects:
        if obj.type == 'MESH': obj.hide_render = True
    base.hide_render = False
    render(camera, 'mission1_hardcase_base_hinge_buttresses.png',
           (-260, 360, 215), (0, 92, 88), 260)
    render(camera, 'mission1_hardcase_base_interior.png', (330, -440, 660), (0, 0, 80), 390)
    base.hide_render = True
    lid.hide_render = True
    pad = case.create_fan_case_pair_lid_pad(case.make_material('Pad_Spacer', (.25, .70, .48)))
    pad.color = (.25, .70, .48, 1)
    pad.location = (-145, 0, 0)
    lid.hide_render = False
    lid.rotation_euler = (0, 0, 0)
    lid.location = (145 - case.LID_DISPLAY_OFFSET_X, 0, case.LID_DOME_RISE)
    render(camera, 'mission1_hardcase_lid_and_spacer.png', (420, -520, 490), (0, 0, 15), 620)
    for obj in bpy.data.objects:
        if obj.type == 'MESH': obj.hide_render = True
    base.hide_render = False
    tpu_lid, tpu_inlay = case.create_lid(case.make_material('TPU_Hinge_View', (.25, .70, .48)),
        case.make_material('TPU_Inlay_View', (.95, .28, .04)), case.HINGE_PROFILE_TPU_68D_SNAP)
    tpu_lid.color, tpu_inlay.color = (.25, .70, .48, 1), (.95, .28, .04, 1)
    for obj in (tpu_lid, tpu_inlay):
        obj.location, obj.rotation_euler = case.installed_lid_pose(case.TPU_HINGE_RELEASE_ANGLE_DEGREES)
        reference.shade_auto_smooth(obj)
    rod = case.add_cylinder_x('Preview_Installed_Hinge_Rod', case.HINGE_ROD_DIAMETER / 2,
        case.HINGE_ROD_X1 - case.HINGE_ROD_X0,
        (0, case.HINGE_AXIS_Y, case.BASE_HEIGHT), vertices=64)
    rod.color = (.95, .62, .15, 1)
    render(camera, 'mission1_hardcase_tpu_hinge.png', (90, 250, 90), (27, 92, 163), 105)
    for obj in bpy.data.objects:
        if obj.type == 'MESH': obj.hide_render = True
    source = subprocess.check_output(['git', 'show', 'a9d8807:models3d/mission1-field-case/mission1_field_case_blender.py'], cwd=DIRECTORY, text=True)
    baseline = types.ModuleType('exterior_baseline')
    baseline.__file__ = str(DIRECTORY / 'mission1_field_case_blender.py')
    exec(compile(source, baseline.__file__, 'exec'), baseline.__dict__)
    build_parts(baseline)
    render(camera, 'mission1_hardcase_before.png', (370, -510, 345), (0, 0, 85), 390)
    for obj in bpy.data.objects:
        if obj.type == 'MESH': obj.hide_render = True
    _, objects = reference.build(scene_setup=False)
    # Reference uses +Y as front; rotate the complete pose into our convention.
    bpy.data.objects['HardCase'].rotation_euler.z = math.pi
    for obj in objects:
        obj.color = (.26, .32, .39, 1)
    render(camera, 'mission1_hardcase_reference.png', (370, -510, 345), (0, 0, 60), 370)


if __name__ == '__main__':
    main()
