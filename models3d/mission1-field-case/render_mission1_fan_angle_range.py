"""Render the actual handed 15- and 30-degree fan-case endpoint assemblies.

blender --background --factory-startup --python this_file.py -- \
  --scene current-case.blend
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


def mesh_snapshot(obj):
    """Return evaluated world-space vertices and faces for one visible mesh."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        vertices = [tuple(evaluated.matrix_world @ vertex.co) for vertex in mesh.vertices]
        faces = [tuple(polygon.vertices) for polygon in mesh.polygons]
    finally:
        evaluated.to_mesh_clear()
    return obj.name, vertices, faces


def build_endpoint_pair(material, magnitude):
    objects = []
    for assembly_index, (placement, sign) in enumerate(
        zip(case.FAN_CASE_PAIR_STORAGE['placements'], (-1.0, 1.0)),
        start=1,
    ):
        group = case.create_fan_case_source_reference_mockups(
            *([material] * 7),
            assembly_index=assembly_index,
            fan_angles=(sign * magnitude, 0.0),
        )
        for obj in group:
            obj.location = placement
        objects.extend(group)
    bpy.context.view_layer.update()
    return objects


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scene', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))

    names = json.loads(bpy.context.scene['cached_field_case_parts'])
    insert = bpy.data.objects[names['fan_case_pair_insert']]
    nominal = [
        obj for obj in bpy.context.scene.objects
        if obj.name.startswith('REFERENCE_ONLY_Fan_Case_Assembly_')
    ]
    if not nominal:
        raise RuntimeError('Saved scene does not contain the nominal fan-case references')
    material = nominal[0].material_slots[0].material
    endpoint = build_endpoint_pair(material, 30.0)
    snapshots = {
        15: [mesh_snapshot(insert), *(mesh_snapshot(obj) for obj in nominal)],
        30: [mesh_snapshot(insert), *(mesh_snapshot(obj) for obj in endpoint)],
    }

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

    camera = bpy.data.objects.new(
        'Fan_Angle_Range_Camera',
        bpy.data.cameras.new('Fan_Angle_Range_Camera'),
    )
    bpy.context.collection.objects.link(camera)
    camera.data.type = 'ORTHO'
    camera.data.clip_end = 2000
    camera.data.ortho_scale = 525
    camera.location = (0, -510, 410)
    aim(camera, (0, 5, 25))
    scene.camera = camera

    for magnitude, offset_x, color in (
        (15, -125.0, (.13, .62, .82, 1.0)),
        (30, 125.0, (1.0, .34, .06, 1.0)),
    ):
        for name, vertices, faces in snapshots[magnitude]:
            obj = case.create_mesh_object(
                f'Preview_{magnitude}_{name}', vertices, faces
            )
            obj.location.x += offset_x
            obj.color = (
                (.35, .41, .48, 1.0)
                if 'Lower_TPU_Insert' in name
                else color
            )

    captions = (
        ('HANDED FAN-CASE RANGE / ACTUAL SOURCE GEOMETRY', -246, 133, 7.7),
        ('-15 degrees / +15 degrees', -226, 104, 6.2),
        ('-30 degrees / +30 degrees', 24, 104, 6.2),
        ('CYAN: minimum angle', -226, -111, 5.0),
        ('ORANGE: maximum angle', 24, -111, 5.0),
        ('Same lower insert accepts every 1.25-degree pose from 15 through 30 degrees',
         -246, -129, 5.2),
        ('Case width, depth, height and assembly centers unchanged', -246, -143, 4.8),
    )
    for text, x, y, size in captions:
        position = Vector((0, 5, 25)) + camera.rotation_euler.to_quaternion() @ Vector(
            (x, y, 525)
        )
        label(camera, text, position, size)

    scene.render.filepath = str(
        DIRECTORY / 'renderings' / 'mission1_fan_angle_range.png'
    )
    bpy.ops.render.render(write_still=True)
    print('FAN_ANGLE_RANGE_PREVIEW_PASS endpoints=-15,+15,-30,+30', flush=True)


if __name__ == '__main__':
    main()
