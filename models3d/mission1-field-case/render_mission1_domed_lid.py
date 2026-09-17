"""Render the raised lid, unchanged hardware datums, and printable roof/pad."""
from pathlib import Path
import math
import subprocess
import sys

import bpy
from mathutils import Vector, Euler

DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DIRECTORY))
import mission1_field_case_blender as case
from render_mission1_latch_previews import aim, label


def main():
    case.clear_scene()
    case.set_units()
    shell = case.make_material('Domed_Shell', (.24, .30, .38))
    orange = case.make_material('Domed_Artwork', (.95, .30, .06))
    pad_material = case.make_material('Roof_Pad', (.95, .48, .12))
    metal = case.make_material('Hardware', (.68, .74, .82))
    base = case.create_base(shell)
    lid, logo = case.create_lid(shell, orange)
    lever, hook = case.create_pelican_latch_parts(orange)
    handle = case.create_pivoting_handle_bar(orange)
    parts = dict(base=base, lid=lid, latch_lever=lever, latch_hook=hook, handle_bar=handle)
    hardware = case.create_case_hardware_reference_mockups(parts, orange, metal, orange)
    for obj in (lever, hook, handle):
        obj.hide_render = True
    for obj in (lid, logo):
        obj.location, obj.rotation_euler = case.installed_lid_pose(0)
    pad = case.create_fan_case_pair_lid_pad(pad_material)
    pad.location, pad.rotation_euler = case.installed_flat_lid_pad_pose(0)
    pad.hide_render = True
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and obj.data.materials:
            obj.color = obj.data.materials[0].diffuse_color
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
    camera = bpy.data.objects.new('Domed_Lid_Camera', bpy.data.cameras.new('Domed_Lid_Camera'))
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

    render('mission1_domed_lid_front.png', (290, -440, 315), (0, -5, 100), 480,
           [('RAISED CROWN / EXISTING LATCH AND HANDLE FIT', -216, 145, 5),
            ('24 mm raised roof / base and storage levels retained', -216, -145, 4.8)])
    render('mission1_domed_lid_rear.png', (-280, 430, 300), (0, 5, 100), 480,
           [('HINGE LINE BELOW THE RAISED ROOF', -216, 145, 5.2),
            ('Original hinge receivers, rod and closing geometry', -216, -145, 4.8)])

    # Side-by-side assembled lids share the same seam and hinge heights.
    current = [base, lid, logo, *hardware]
    for obj in current:
        obj.location.x += 148
    source = subprocess.check_output(
        ['git', 'show', '9fc1c0e:models3d/mission1-field-case/mission1_field_case_blender.py'],
        cwd=DIRECTORY, text=True)
    old = {'__name__': 'previous_lid', '__file__': case.__file__}
    exec(compile(source, case.__file__, 'exec'), old)
    old_base = old['create_base'](shell)
    old_lid, old_logo = old['create_lid'](shell, orange)
    for obj in (old_lid, old_logo):
        obj.location, obj.rotation_euler = old['installed_lid_pose'](0)
    old_hardware = old['create_case_hardware_reference_mockups'](parts, orange, metal, orange)
    previous = [old_base, old_lid, old_logo, *old_hardware]
    for obj in previous:
        obj.location.x -= 148
        obj.hide_render = False
        if obj.data.materials:
            obj.color = obj.data.materials[0].diffuse_color
    render('mission1_domed_lid_comparison.png', (0, -700, 325), (0, 0, 105), 620,
           [('BEFORE / 171 mm closed height', -284, 180, 7),
            ('AFTER / 195 mm closed height', 16, 180, 7),
            ('Same base, latch/hinge line, handle and lower inserts', -284, -180, 6.5)])
    for obj in previous:
        obj.hide_render = True
    for obj in current:
        obj.location.x -= 148
        obj.hide_render = True

    # Print views use the actual mesh contact and production bed rotation.
    rotation = (0, math.radians(case.LID_DOME_PRINT_ANGLE), 0)
    transform = Euler(rotation).to_matrix()
    points = [transform @ v.co for v in lid.data.vertices]
    minimum = Vector(tuple(min(p[a] for p in points) for a in range(3)))
    maximum = Vector(tuple(max(p[a] for p in points) for a in range(3)))
    lid.location = (-135-(minimum.x+maximum.x)/2, -(minimum.y+maximum.y)/2, -minimum.z)
    lid.rotation_euler = rotation
    logo.location = lid.location.copy()
    logo.rotation_euler = rotation
    pad.location = (120, 0, 0)
    pad.rotation_euler = (0, 0, 0)
    for obj in (lid, logo, pad):
        obj.hide_render = False
    render('mission1_domed_lid_printing.png', (330,-700,500), (0,0,90), 590,
           [('LID / 60 DEGREE TILT', -272,172,7),
            ('PAD / CURVED SPACER UP', 6,172,7),
            ('Snug supports required on lid; pad prints without supports', -272,-168,5.5),
            ('Spacer preserves the original 165 mm packing face', -272,-181,5.5)])
    for obj in (lid,logo,pad):
        obj.hide_render = True
    tray = case.create_fan_case_pair_overhead_carrier(shell)
    tray.location.z = -case.FAN_CASE_PAIR_OVERHEAD_STORAGE['carrier_bounds'][4]
    tray.color = shell.diffuse_color
    render('mission1_goalpost_shaped_tray.png', (270,-380,420), (0,0,15), 365,
           [('GOALPOST MOUNT / LOOSE SHAPED POCKET',-166,111,4.8),
            ('10 mm contour / finger access / unchanged tray stack',-166,-111,4.1)])
    shape = case.extrude_planar_region('Nominal_Photo_Mount_Silhouette',
        case.goalpost_mount_profile(), 3.1, 4.1)
    shape.color = orange.diffuse_color
    render('mission1_goalpost_loading_direction.png', (0,-180,600), (0,0,15), 335,
           [('FACE-UP LOADING DIRECTION',-145,99,5),
            ('Approximate photo outline / 2.5-3 mm loose clearance',-145,-99,3.9)])
    print('FIELD_CASE_DOMED_LID_RENDERINGS_PASS', flush=True)


if __name__ == '__main__':
    main()
