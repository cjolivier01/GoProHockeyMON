"""Render the source-built wide hardware and its fit on the expanded case.

    blender --background --factory-startup --threads 8 --python-exit-code 1 \
      --python models3d/mission1-field-case/render_mission1_wide_hardware.py
"""
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


BASELINE_REVISION = "b93c7d6f7bd9984781f4c418cdcd283853ee9ddd"


def main():
    case.clear_scene()
    case.set_units()
    shell = case.make_material('Shell', (.24, .30, .38))
    orange = case.make_material('Wide_Hardware', (.95, .30, .06))
    before = case.make_material('Previous_Hardware', (.48, .55, .64))
    lever, hook = case.create_pelican_latch_parts(orange)
    handle = case.create_pivoting_handle_bar(orange)
    minimum_gap = case.validate_wide_hardware_clearance(
        {'latch_lever': lever, 'latch_hook': hook, 'handle_bar': handle})
    full_turn_gap = case.validate_handle_closed_latch_full_rotation(
        {'latch_lever': lever, 'latch_hook': hook, 'handle_bar': handle})
    source = subprocess.check_output(
        ['git', 'show', f'{BASELINE_REVISION}:models3d/mission1-field-case/mission1_field_case_blender.py'],
        cwd=DIRECTORY, text=True,
    )
    previous = {'__name__': 'previous_hardware', '__file__': case.__file__}
    exec(compile(source, case.__file__, 'exec'), previous)
    old_lever, old_hook = previous['create_pelican_latch_parts'](before)
    old_handle = previous['create_pivoting_handle_bar'](before)
    old_parts = (old_lever, old_hook, old_handle)
    new_parts = (lever, hook, handle)
    for obj in new_parts:
        obj.color = (.95, .30, .06, 1)
    for obj in old_parts:
        obj.color = (.48, .55, .64, 1)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1200
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
    camera = bpy.data.objects.new('Wide_Hardware_Camera', bpy.data.cameras.new('Wide_Hardware_Camera'))
    bpy.context.collection.objects.link(camera)
    camera.data.type = 'ORTHO'
    camera.data.clip_start = .1
    camera.data.clip_end = 3000
    scene.camera = camera
    output = DIRECTORY / 'renderings'
    output.mkdir(exist_ok=True)

    def render(filename, position, target, scale, captions):
        camera.location = position
        camera.data.ortho_scale = scale
        aim(camera, target)
        labels = []
        for text, x, y, size in captions:
            point = Vector(target) + camera.rotation_euler.to_quaternion() @ Vector((x, y, scale))
            labels.append(label(camera, text, point, size))
        scene.render.filepath = str(output / filename)
        bpy.ops.render.render(write_still=True)
        for obj in labels:
            bpy.data.objects.remove(obj, do_unlink=True)

    for parts, dx in ((old_parts, -80), (new_parts, 80)):
        for obj, x, y in ((parts[0], -28, 45), (parts[1], 28, 45), (parts[2], 0, -28)):
            obj.location = (dx + x, y, 0)
            obj.rotation_euler = (0, 0, 0)
        parts[0].rotation_euler.x = math.pi / 2
    render('mission1_wide_hardware_comparison.png', (0, -40, 500), (0, -6, 0), 340,
           [('BEFORE / 40.96 mm / M3 x 50', -153, 94, 5),
            ('CURRENT / 30.96 mm / M3 x 40', 14, 94, 5),
            ('119.8 mm handle unchanged', -153, -91, 4.6),
            ('10 mm narrower fixed-pivot stack', 14, -91, 4.6)])
    for obj in old_parts:
        obj.hide_render = True
    base = case.create_base(shell)
    lid, inlay = case.create_lid(shell, orange)
    base.color = lid.color = (.24, .30, .38, 1)
    inlay.color = (.95, .30, .06, 1)
    lid.location, lid.rotation_euler = case.installed_lid_pose(0)
    inlay.location, inlay.rotation_euler = lid.location.copy(), lid.rotation_euler.copy()
    for x in case.LATCH_X_CENTERS:
        for original, positioner in ((lever, case.position_installed_latch_lever),
                                     (hook, case.position_installed_latch_hook)):
            obj = original.copy()
            obj.data = original.data.copy()
            bpy.context.collection.objects.link(obj)
            positioner(obj, x)
        for obj in case.create_latch_fixed_m3_reference_hardware('Latch_Hardware', x):
            obj.color = (.68, .74, .82, 1)
    lever.hide_render = hook.hide_render = True
    for side in (-1, 1):
        for obj in case.create_handle_m3_reference_hardware(
                'Handle_Hardware', side, case.HANDLE_PIVOT_Y, case.HANDLE_PIVOT_Z):
            obj.color = (.68, .74, .82, 1)
    handle.location = (0, case.HANDLE_PIVOT_Y + case.HANDLE_LOCAL_PIVOT_Z, case.HANDLE_PIVOT_Z)
    handle.rotation_euler = (math.pi / 2, 0, 0)
    render('mission1_wide_hardware_installed.png', (270, -420, 285), (0, -8, 88), 350,
           [('30.96 mm LATCHES / M3 x 40 FIXED PIVOTS', -161, 103, 5.2),
            ('Same case, lid, tray, insert and coupon envelopes', -161, -103, 4)])
    handle.location = (0, case.HANDLE_PIVOT_Y, case.HANDLE_PIVOT_Z - case.HANDLE_LOCAL_PIVOT_Z)
    handle.rotation_euler = (0, 0, 0)
    render('mission1_wide_hardware_clearance.png', (0, -600, 105), (0, -95, 111), 270,
           [('HANDLE RAISED / FRONT CLEARANCE', -125, 80, 4.6),
            (f'Normal 0-90 degree travel: {minimum_gap:.2f} mm vertical separation', -125, -72, 3.8),
            (f'Full 360 degree rotation: {full_turn_gap:.2f} mm lateral gap including play', -125, -82, 3.8)])

    # Show the actual side-profile linkage just before and after its pressure
    # peak. The two poses use copies of the production latch meshes; the pivot
    # dots are visualization markers placed just in front of their side faces.
    for obj in tuple(bpy.context.scene.objects):
        if obj != camera:
            obj.hide_render = True
    peak_material = case.make_material('Peak_Load_Pose', (.98, .62, .08))
    closed_material = case.make_material('Fully_Closed_Pose', (.95, .30, .06))
    pivot_material = case.make_material('Pivot_Markers', (.76, .84, .94))

    def add_pose(angle, y_shift, material, prefix):
        pose_lever = lever.copy()
        pose_lever.data = lever.data.copy()
        pose_lever.name = prefix + '_Lever'
        bpy.context.collection.objects.link(pose_lever)
        pose_lever.location = (
            0.0,
            case.LATCH_BASE_PIVOT_Y + y_shift,
            case.LATCH_BASE_PIVOT_Z,
        )
        pose_lever.rotation_euler = (math.radians(angle), 0.0, 0.0)
        pose_lever.hide_render = False
        pose_lever.color = material.diffuse_color
        case.assign_material(pose_lever, material)

        hook_y, hook_z = case.latch_hook_origin_yz(angle)
        pose_hook = hook.copy()
        pose_hook.data = hook.data.copy()
        pose_hook.name = prefix + '_Hook'
        bpy.context.collection.objects.link(pose_hook)
        pose_hook.location = (0.0, hook_y + y_shift, hook_z)
        pose_hook.rotation_euler = (
            math.radians(case.latch_hook_global_angle_degrees(angle)),
            0.0,
            0.0,
        )
        pose_hook.hide_render = False
        pose_hook.color = material.diffuse_color
        case.assign_material(pose_hook, material)

        radians = math.radians(angle)
        local_y, local_z = case.LATCH_LINK_PIVOT_LOCAL_YZ
        moving_y = (
            case.LATCH_BASE_PIVOT_Y
            + math.cos(radians) * local_y
            - math.sin(radians) * local_z
            + y_shift
        )
        moving_z = (
            case.LATCH_BASE_PIVOT_Z
            + math.sin(radians) * local_y
            + math.cos(radians) * local_z
        )
        marker_x = case.LATCH_WIDTH / 2.0 + 1.5
        for marker_name, marker_y, marker_z in (
            ('Fixed', case.LATCH_BASE_PIVOT_Y + y_shift, case.LATCH_BASE_PIVOT_Z),
            ('Moving', moving_y, moving_z),
        ):
            marker = case.add_uv_sphere(
                prefix + '_' + marker_name + '_Pivot',
                1.35,
                (marker_x, marker_y, marker_z),
                segments=32,
                ring_count=16,
            )
            marker.hide_render = False
            marker.color = pivot_material.diffuse_color
            case.assign_material(marker, pivot_material)

    peak_angle = -7.35
    add_pose(peak_angle, -37.0, peak_material, 'Peak_Load')
    add_pose(case.LATCH_LEVER_CLOSED_ANGLE, 37.0, closed_material, 'Fully_Closed')
    render(
        'mission1_latch_over_center.png',
        (400, case.LATCH_BASE_PIVOT_Y - 35.0, case.LATCH_BASE_PIVOT_Z + 12.0),
        (0, case.LATCH_BASE_PIVOT_Y, case.LATCH_BASE_PIVOT_Z),
        135,
        [
            ('PEAK LOAD / -7.35 deg', -63, 32, 4.4),
            ('FULLY CLOSED / +3.00 deg', 8, 32, 4.4),
            ('11.07 deg past dead center / draw relaxes 0.116 mm', -63, -29, 4.0),
        ],
    )
    print('FIELD_CASE_WIDE_HARDWARE_RENDERINGS_PASS', flush=True)


if __name__ == '__main__':
    main()
