"""Render the source-built expanded loadout and its conservative packing envelopes.

    blender --background --factory-startup --threads 8 --python-exit-code 1 \
      --python models3d/mission1-field-case/render_mission1_expanded_storage.py \
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
    parser.add_argument('--scene', type=Path)
    parser.add_argument('--review-round', type=int, default=1)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    if args.scene:
        bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
        names = json.loads(bpy.context.scene['cached_field_case_parts'])
        parts = {key: bpy.data.objects[name] for key, name in names.items()}
    else:
        case.EXPORT_STL = False
        parts = case.build_mission1_field_case()
    refs = [obj for obj in bpy.context.scene.objects
            if obj.name.startswith(('REFERENCE_ONLY_Fan_Case_', 'REFERENCE_ONLY_Field_Accessory_'))]
    accessory_refs = [obj for obj in refs if obj.name.startswith('REFERENCE_ONLY_Field_Accessory_')]
    for obj in bpy.context.scene.objects:
        obj.hide_render = True
    shell = (.25, .32, .42, 1)
    tray = (.92, .37, .08, 1)
    pad = (.25, .70, .48, 1)
    mount = (.92, .70, .26, 1)
    coil = (.15, .62, .72, 1)
    remote = (.58, .36, .77, 1)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1500
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.display.shading.light = 'FLAT'
    scene.display.shading.color_type = 'MATERIAL'
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = 'BOTH'
    scene.display.shading.show_object_outline = True
    scene.display.shading.background_type = 'WORLD'
    scene.world.color = (.035, .045, .065)
    scene.view_settings.view_transform = 'Standard'
    scene.display.render_aa = '32'
    camera = bpy.data.objects.new('Expanded_Storage_Camera', bpy.data.cameras.new('Expanded_Storage_Camera'))
    bpy.context.collection.objects.link(camera)
    camera.data.type = 'ORTHO'
    camera.data.clip_start = .1
    camera.data.clip_end = 3000
    scene.camera = camera
    previews = []

    def copy(source, color, offset=(0, 0, 0), section=None, pose=None):
        obj = source.copy()
        obj.data = source.data.copy()
        bpy.context.collection.objects.link(obj)
        obj.hide_render = False
        if pose:
            obj.location, obj.rotation_euler = pose
        if section:
            bpy.context.view_layer.update()
            original_low, original_high = case.object_world_bounds(obj)
            case.select_only(obj)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            cutter = case.add_rounded_box('PREVIEW_ONLY_Section_Cutter', section[1], section[0], bevel=0)
            case.boolean_apply(obj, cutter, 'INTERSECT')
            if obj.data.vertices:
                low, high = case.object_world_bounds(obj)
                if any(low[i] < original_low[i] - .01 or high[i] > original_high[i] + .01 for i in range(3)):
                    if 'REFERENCE_ONLY_Fan_Case_' not in source.name or 'Wrapping_Fan_Cover' not in source.name:
                        raise ValueError(f'Invalid section intersection: {source.name}')
                    # This compound fan grille produces an invalid preview
                    # Boolean. Omit its slice; never show a cutter complement.
                    print('PREVIEW_SECTION_OMITTED_INVALID_INTERSECTION', source.name, flush=True)
                    bpy.data.objects.remove(obj, do_unlink=True)
                    return None
        obj.location += Vector(offset)
        obj.color = color
        material = case.make_material('Preview_' + source.name, color[:3])
        material.diffuse_color = color
        obj.data.materials.clear()
        obj.data.materials.append(material)
        if source == parts['accessory_organizer'] and section is None:
            top = case.make_material('Preview_Organizer_Rim_And_Dividers', (.12, .40, .26))
            top.diffuse_color = (.12, .40, .26, 1)
            obj.data.materials.append(top)
            for polygon in obj.data.polygons:
                if polygon.normal.z > .9 and polygon.center.z > 122:
                    polygon.material_index = 1
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
        for text, x, y, size in captions:
            location = Vector(target) + camera.rotation_euler.to_quaternion() @ Vector((x, y, scale))
            labels.append(label(camera, text, location, size))
        location = Vector(target) + camera.rotation_euler.to_quaternion() @ Vector(
            (-scale * .47, -scale * scene.render.resolution_y / scene.render.resolution_x / 2 + scale * .025, scale))
        labels.append(label(camera, f'Review round {args.review_round} | Source-built geometry | Accessories shown as clearance envelopes', location, scale * .0105))
        text_material = case.make_material('Preview_White_Text', (.95, .97, 1))
        text_material.diffuse_color = (.95, .97, 1, 1)
        for obj in labels:
            obj.data.materials.append(text_material)
        scene.render.filepath = str(DIRECTORY / 'renderings' / name)
        bpy.ops.render.render(write_still=True)
        for obj in labels:
            bpy.data.objects.remove(obj, do_unlink=True)

    copy(parts['accessory_organizer'], pad)
    for obj in accessory_refs:
        if 'Mount' not in obj.name:
            copy(obj, coil if 'Coil' in obj.name else remote)
    render('mission1_expanded_organizer.png', (0, 0, 500), (0, 0, 140), 270,
           [('COIL + THREE CUSTOM + TWO OEM REMOTES', -124, 98, 4.6),
            ('154 mm coil allowance', -98, 5, 3.9),
            ('42 mm deep', -77, -3, 3.6),
            ('2 OEM', 58, 71, 3.1), ('3 custom', 55, -78, 3.1),
            ('Integral TPU-85A slots / rounded 223 x 169 x 46.3 mm tray', -124, -98, 3.5)])
    clear()

    section = ((-52, 0, 100), (3, 250, 202))
    for key, color in (('base', shell), ('fan_case_pair_insert', tray),
                       ('fan_case_pair_storage_bin', tray), ('fan_case_pair_carrier', tray),
                       ('accessory_organizer', pad)):
        copy(parts[key], color, section=section)
    copy(parts['lid'], shell, section=section, pose=case.installed_lid_pose(0))
    copy(parts['fan_case_pair_lid_pad'], pad, section=section, pose=case.installed_flat_lid_pad_pose(0))
    # One physical X=-52 mm section includes a camera, mount and coil.
    for obj in refs:
        if obj in accessory_refs:
            if 'Remote' not in obj.name:
                copy(obj, mount if 'Mount' in obj.name else coil, section=section)
        elif obj.name.startswith('REFERENCE_ONLY_Fan_Case_Assembly_'):
            low, high = case.object_world_bounds(obj)
            if low.x <= -52 <= high.x:
                copy(obj, (.44, .52, .62, 1), section=section)
    render('mission1_expanded_closed_stack.png', (398, 0, 100), (-52, 0, 100), 295,
           [('ROUNDED CASE / 195 mm closed height', -128, 105, 4.6),
            ('24 mm roof spacer', -64, 80, 3.5),
            ('Coil: 154 mm diameter x 42 mm', -78, 46, 3.8),
            ('Mount allowance: 210 x 146 x 37 mm', -106, 11, 3.4),
            ('Lower front bin retained', -115, -25, 3.0),
            ('Original equipment contact: Z = 165 mm', -128, -98, 3.7)])
    clear()

    copy(parts['base'], shell, section=((0, 0, 45), (300, 280, 90)))
    copy(parts['fan_case_pair_insert'], tray)
    copy(parts['fan_case_pair_storage_bin'], tray)
    for obj in refs:
        if obj not in accessory_refs:
            copy(obj, (.40, .52, .62, 1))
    copy(parts['fan_case_pair_carrier'], tray, (0, 0, 45))
    copy(parts['accessory_organizer'], pad, (0, 0, 125))
    for obj in accessory_refs:
        copy(obj, mount if 'Mount' in obj.name else coil if 'Coil' in obj.name else remote,
             (0, 0, 45 if 'Mount' in obj.name else 125))
    render('mission1_expanded_loadout_exploded.png', (440, -580, 470), (0, 0, 145), 540,
           [('EXPANDED ALTERNATE LOADOUT / stacked removable trays', -250, 202, 6.0),
            ('Case wall cut away to show the cameras and lower bin', -250, -188, 4.7),
            ('Photo mount stays assembled; camera and fan poses retained', -250, -199, 4.7)])
    print('FIELD_CASE_EXPANDED_PREVIEWS_COMPLETE', flush=True)


if __name__ == '__main__':
    main()
