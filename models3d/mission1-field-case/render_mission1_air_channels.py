"""Render validated tray air channels from front, rear, underside and sections.

blender --background --factory-startup --threads 4 --python-exit-code 1 \
  --python models3d/mission1-field-case/render_mission1_air_channels.py \
  -- --scene /path/to/validated-field-case.blend
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

OUTPUT = DIRECTORY / 'renderings'


def render_previews(parts):
    for obj in bpy.context.scene.objects:
        obj.hide_render = True
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1400
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
    camera = bpy.data.objects.new('Air_Channel_Camera', bpy.data.cameras.new('Air_Channel_Camera'))
    bpy.context.collection.objects.link(camera)
    camera.data.type = 'ORTHO'
    camera.data.clip_start = .05
    camera.data.clip_end = 3000
    scene.camera = camera
    previews = []
    green, orange, gray, cyan = (.20, .68, .43), (.87, .43, .11), (.32, .39, .49), (.12, .78, .98)

    def show(source, color, section=None):
        obj = source.copy()
        obj.data = source.data.copy()
        bpy.context.collection.objects.link(obj)
        obj.hide_render = False
        if section:
            size, center = section
            cutter = case.add_rounded_box('PREVIEW_Section', size, center, bevel=0)
            case.boolean_apply(obj, cutter, 'INTERSECT')
        obj.data.materials.clear()
        obj.data.materials.append(case.make_material('Preview_' + source.name, color))
        previews.append(obj)
        return obj

    def air_line(points, radius=.16):
        curve = bpy.data.curves.new('Airflow_Illustration', 'CURVE')
        curve.dimensions = '3D'
        curve.bevel_depth = radius
        curve.bevel_resolution = 3
        line = curve.splines.new('POLY')
        line.points.add(len(points) - 1)
        for p, co in zip(line.points, points): p.co = (*co, 1)
        obj = bpy.data.objects.new('Airflow_Illustration', curve)
        bpy.context.collection.objects.link(obj)
        obj.data.materials.append(case.make_material('Airflow', cyan))
        previews.append(obj)

    def arrow(start, end, radius=.2):
        air_line((start, end), radius * .35)
        direction = Vector(end) - Vector(start)
        bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=radius, radius2=0,
            depth=radius * 3, location=Vector(end) - direction.normalized() * radius * 1.5)
        obj = bpy.context.object
        obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
        obj.data.materials.append(case.make_material('Airflow_Arrow', cyan))
        previews.append(obj)

    def clear():
        for obj in previews: bpy.data.objects.remove(obj, do_unlink=True)
        previews.clear()

    def render(name, position, target, scale, captions):
        camera.location = position
        camera.data.ortho_scale = scale
        aim(camera, target)
        labels = []
        for text, x, y, size in captions:
            location = Vector(target) + camera.rotation_euler.to_quaternion() @ Vector((x, y, scale))
            obj = label(camera, text, location, size)
            obj.data.materials.append(case.make_material('Label', (.95, .97, 1)))
            labels.append(obj)
        scene.render.filepath = str(OUTPUT / name)
        bpy.ops.render.render(write_still=True)
        for obj in labels: bpy.data.objects.remove(obj, do_unlink=True)

    show(parts['accessory_organizer'], green)
    for x, side, edge in case.accessory_air_channel_specs():
        air_line(((x, edge - side * .4, 165), (x, edge - side * .4, 119)), .22)
        arrow((x, edge - side * .4, 161), (x, edge - side * .4, 150), .9)
    render('mission1_air_channels_overview.png', (240, -360, 390), (0, 0, 139), 330,
        [('TRAY AIR CHANNELS / TPU-85A', -153, 114, 5.3),
         ('Four outside grooves: 5 mm wide x 1 mm deep', -153, 103, 3.9),
         ('Two on the front + two on the rear', -153, -104, 4.0),
         ('Cyan shows air paths / tray remains 223 x 169 x 46.3 mm', -153, -114, 3.7)])
    clear()

    show(parts['accessory_organizer'], green)
    for x, side, edge in case.accessory_air_channel_specs():
        air_line(((x, edge - side * .4, 165), (x, edge - side * .4, 119)), .22)
        arrow((x, edge - side * .4, 161), (x, edge - side * .4, 150), .9)
    render('mission1_air_channels_rear.png', (-240, 360, 390), (0, 0, 139), 330,
        [('REAR VIEW / TWO ADDITIONAL AIR CHANNELS', -153, 114, 5.0),
         ('Existing grip notches and lid-key clearance retained', -153, 103, 3.7),
         ('Cyan shows the outside air paths', -153, -110, 4.0)])
    clear()

    show(parts['accessory_organizer'], green)
    for x, side, edge in case.accessory_air_channel_specs():
        for offset in case.ACCESSORY_AIR_CHANNEL_BRANCH_OFFSETS:
            air_line(((x + offset, edge - side * .5, 118.3),
                      (x + offset, edge - side * 4.3, 118.3),
                      (x + offset, edge - side * 4.3, 116.8)), .13)
    render('mission1_air_channels_underside.png', (190, -270, -170), (0, 0, 120), 325,
        [('UNDERSIDE / FOUR PAIRS OF AIR PASSAGES', -150, 112, 4.9),
         ('Eight pitched passages cross the lower tray contact rim', -150, 102, 3.7),
         ('Main floor stays 3 mm / passage roofs leave at least 2 mm', -150, -110, 3.6)])
    clear()

    # Half of the front-right groove exposes both its remaining side wall and
    # the turn across the lower tray's contact rim. No assembly part is lifted.
    branch_x = 80 + case.ACCESSORY_AIR_CHANNEL_BRANCH_OFFSETS[0]
    section = ((.5, 23, 18), (branch_x, -80, 120))
    for key, color in (('base', gray), ('fan_case_pair_carrier', orange), ('accessory_organizer', green)):
        show(parts[key], color, section)
    path_x = branch_x + .35
    air_line(((path_x, -84, 128), (path_x, -84, 118.3),
              (path_x, -80.2, 118.3), (path_x, -80.2, 116)), .11)
    arrow((path_x, -84, 127), (path_x, -84, 124), .4)
    arrow((path_x, -83.7, 118.3), (path_x, -80.2, 118.3), .22)
    arrow((path_x, -80.2, 117.8), (path_x, -80.2, 116.1), .28)
    render('mission1_air_channels_seated_section.png', (350, -81, 120), (branch_x, -81, 120), 34,
        [('AIR REACHES BELOW THE SEATED TRAY', -15.8, 11.7, .66),
         ('Actual section / no separation added between trays', -15.8, 10.2, .45),
         ('Case wall', -15.5, 6.5, .48), ('TPU organizer', 2, 6.5, .55),
         ('Air turns over the contact rim', -3.8, -4, .5),
         ('Lower mount tray', -15.5, -8.9, .5),
         ('Cyan = airflow / 2 mm floor remains above each passage', -15.8, -11.4, .43)])
    clear()

    # Looking up at a cropped edge shows the paired pitched passages at full
    # scale: a 1 mm bearing rib remains between them and no flat roof bridges.
    section = ((13, 11, 9), (80, -81.5, 120.5))
    show(parts['accessory_organizer'], green, section)
    render('mission1_air_channels_underside_detail.png', (97, -113, 103), (80, -82, 120), 21,
        [('UNDERSIDE TURN / TWO PITCHED PASSAGES', -9.8, 7.3, .43),
         ('Each passage: 2 mm wide x 1 mm high / 45-degree roof', -9.8, 6.3, .30),
         ('1 mm central rib / at least 2 mm of floor above', -9.8, -6.8, .34)])
    print('FIELD_CASE_AIR_CHANNEL_RENDERINGS_COMPLETE', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scene', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
    names = json.loads(bpy.context.scene['cached_field_case_parts'])
    parts = {k: bpy.data.objects[name] for k, name in names.items()}
    render_previews(parts)


if __name__ == '__main__':
    main()
