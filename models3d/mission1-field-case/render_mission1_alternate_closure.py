"""Render source-generated sections of the alternate lid clearance correction.

    blender --background --factory-startup --threads 8 --python-exit-code 1 \
      --python models3d/mission1-field-case/render_mission1_alternate_closure.py \
      -- --scene /path/to/current-field-case.blend --review-round 0

Omit --scene to build the unchanged lower cradle and references from source.
"""
import argparse
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DIRECTORY))
import mission1_field_case_blender as case
from check_mission1_field_case_bottom_cables import load_or_build_loadout
from render_mission1_latch_previews import aim, label


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scene', type=Path)
    parser.add_argument('--review-round', type=int, default=0)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    parts, references, _, _ = load_or_build_loadout(args.scene)
    references = [obj for obj in references if obj.name.startswith('REFERENCE_ONLY_Fan_Case_')]
    shell_color = (.24, .32, .43, 1)
    tray_color = (.95, .40, .10, 1)
    pad_color = (.20, .80, .57, 1)
    material = case.make_material('Closure_Section', shell_color[:3])
    if args.scene:
        parts['base'] = case.create_base(material)
    lid, inlay = case.create_lid(material, material)
    lid.location, lid.rotation_euler = case.installed_lid_pose(0)
    rear = case.create_fan_case_pair_overhead_carrier(material)
    pad = case.create_fan_case_pair_lid_pad(material)
    pad.location, pad.rotation_euler = case.installed_flat_lid_pad_pose(0)
    saved_depth = case.FAN_CASE_PAIR_TRAY_KEY_NOTCH_DEPTH
    saved_thickness = case.FAN_CASE_PAIR_LID_PAD_PLATE_THICKNESS
    try:
        case.FAN_CASE_PAIR_TRAY_KEY_NOTCH_DEPTH = 0
        old_rear = case.create_fan_case_pair_overhead_carrier(material)
        case.FAN_CASE_PAIR_LID_PAD_PLATE_THICKNESS = 3
        old_pad = case.create_fan_case_pair_lid_pad(material)
        old_pad.location, old_pad.rotation_euler = case.installed_flat_lid_pad_pose(0)
    finally:
        case.FAN_CASE_PAIR_TRAY_KEY_NOTCH_DEPTH = saved_depth
        case.FAN_CASE_PAIR_LID_PAD_PLATE_THICKNESS = saved_thickness
    for obj in bpy.context.scene.objects:
        obj.hide_render = True

    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = 1800
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
    camera = bpy.data.objects.new('Alternate_Closure_Camera', bpy.data.cameras.new('Alternate_Closure_Camera'))
    bpy.context.collection.objects.link(camera)
    camera.data.type = 'ORTHO'
    camera.data.clip_start = .1
    camera.data.clip_end = 2000
    scene.camera = camera

    def section(source, center, dimensions, color, offset=(0, 0, 0)):
        obj = source.copy()
        obj.data = source.data.copy()
        bpy.context.collection.objects.link(obj)
        obj.hide_render = False
        case.select_only(obj)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        clip = case.add_rounded_box('PREVIEW_ONLY_Section', dimensions, center, bevel=0)
        case.boolean_apply(obj, clip, 'INTERSECT')
        obj.location += Vector(offset)
        obj.color = color
        return obj

    def render(name, position, target, scale, captions):
        camera.location = position
        camera.data.ortho_scale = scale
        aim(camera, target)
        labels = []
        for text, x, y, size in captions:
            location = Vector(target) + camera.rotation_euler.to_quaternion() @ Vector((x, y, scale))
            obj = label(camera, text, location, size)
            obj.hide_render = False
            labels.append(obj)
        location = Vector(target) + camera.rotation_euler.to_quaternion() @ Vector((-scale*.47, -scale*scene.render.resolution_y/scene.render.resolution_x/2 + scale*.025, scale))
        labels.append(label(camera, f'Review round {args.review_round} | Actual mesh sections | Case and lid dimensions unchanged', location, scale*.011))
        scene.render.filepath = str(DIRECTORY / 'renderings' / name)
        bpy.ops.render.render(write_still=True)
        for obj in labels:
            bpy.data.objects.remove(obj, do_unlink=True)

    sections = []
    for offset_y, tray, lining in ((14, old_rear, old_pad), (-14, rear, pad)):
        for source, color in ((lid, shell_color), (tray, tray_color), (lining, pad_color)):
            sections.append(section(source, (-42, 68, 103), (2, 24, 14), color, (0, offset_y, 0)))
    render('mission1_alternate_lid_key_clearance.png', (-150, 68, 103), (-42, 68, 103), 57,
           [('BEFORE / key hits rear tray', -26, 13.5, 1.1),
            ('AFTER / key clears rim notch', 2, 13.5, 1.1),
            ('0.8 mm rigid interference', -26, -9, 1.05),
            ('14 x 8 mm notch, 3 mm deep', 2, -9, 1.05),
            ('Blue: lid + key   Orange: rear tray   Green: pad', -26, -12, .90)])
    for obj in sections:
        obj.hide_render = True

    sources = [(parts['base'], shell_color), (lid, shell_color), (rear, tray_color),
               (parts['fan_case_pair_storage_bin'], tray_color), (pad, pad_color),
               (parts['fan_case_pair_insert'], (.60, .32, .12, 1))]
    sources.extend((obj, (.45, .57, .70, 1)) for obj in references)
    bpy.context.view_layer.update()
    for source, color in sources:
        minimum, maximum = case.object_world_bounds(source)
        if minimum.x > 56 or maximum.x < 48:
            continue
        section(source, (52, 0, 59), (8, 220, 122), color)
    scene.render.resolution_y = 1350
    render('mission1_alternate_closed_stack_clearance.png', (350, 0, 58), (52, 0, 58), 210,
           [('CLOSED ALTERNATE STACK / nominal 97.8 mm base', -98, 57, 3.0),
            ('Front deep tray', -87, 33, 2.5), ('Rear shallow tray', 3, 33, 2.5),
            ('2 mm lid pad: 0.70 mm gap above tray rims', -98, -62, 2.8),
            ('0.15 mm gap if only the base is 97.25 mm high', -98, -68, 2.6)])
    for obj in bpy.context.scene.objects:
        obj.hide_render = True
    original = (case.HINGE_BASE_HOLE_DIAMETER, case.HINGE_LID_RECEIVER_DIAMETER,
                case.HINGE_LID_SLOT_WIDTH)
    try:
        case.HINGE_BASE_HOLE_DIAMETER = 4.5
        case.HINGE_LID_RECEIVER_DIAMETER = 4.8
        case.HINGE_LID_SLOT_WIDTH = 4.6
        old_base = case.create_base(material)
        old_lid, old_inlay = case.create_lid(material, material)
        old_lid.location, old_lid.rotation_euler = case.installed_lid_pose(0)
    finally:
        (case.HINGE_BASE_HOLE_DIAMETER, case.HINGE_LID_RECEIVER_DIAMETER,
         case.HINGE_LID_SLOT_WIDTH) = original
    for obj in (old_base, old_lid, old_inlay):
        obj.hide_render = True
    for offset_y, base_source, lid_source in ((14, old_base, old_lid),
                                             (-14, parts['base'], lid)):
        for source, source_x, row in ((base_source, 0, 9), (lid_source, 30, -9)):
            section(source, (source_x, case.HINGE_AXIS_Y, case.BASE_HEIGHT),
                    (2, 14, 14), shell_color,
                    (-source_x, offset_y - case.HINGE_AXIS_Y, row - case.BASE_HEIGHT))
            rod = case.add_cylinder_x('PREVIEW_ONLY_3p8mm_Rod', 1.9, 3,
                                      (0, offset_y, row), vertices=180)
            rod.color = (.85, .70, .30, 1)
    scene.render.resolution_y = 1500
    render('mission1_alternate_hinge_clearance.png', (-150, 0, 0), (0, 0, 0), 60,
           [('BEFORE / 3.8 mm rod', -27, 21, 1.3),
            ('AFTER / 25% less clearance', 1, 21, 1.2),
            ('Base bore: 4.500 mm', -27, 17, 1.15),
            ('Base bore: 4.325 mm', 1, 17, 1.15),
            ('Lid receiver: 4.800 mm', -27, -18, 1.15),
            ('Lid receiver: 4.550 mm', 1, -18, 1.15),
            ('Rigid slot: 4.600 mm', -27, -21, 1.1),
            ('Rigid slot: 4.400 mm', 1, -21, 1.1)])
    print('FIELD_CASE_ALTERNATE_CLOSURE_PREVIEWS_COMPLETE', flush=True)


if __name__ == '__main__':
    main()
