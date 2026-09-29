"""Render the actual straight and handed 30-degree fan-case endpoint assemblies.

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
        handed = case.handed_storage_fan_angles((magnitude,))
        group = case.create_fan_case_source_reference_mockups(
            *([material] * 7),
            assembly_index=assembly_index,
            fan_angles=handed[0 if sign < 0 else 1][0],
        )
        for obj in group:
            obj.location = placement
        objects.extend(group)
    bpy.context.view_layer.update()
    return objects


def check_saved_scene_matches_configuration(references):
    """Reject a scene whose reference pair is not the configured one.

    This is a partial staleness check and deliberately advertises its limit:
    it compares the saved reference pair against the nominal envelope, which
    catches a scene built at a different reference pose, case size or
    placement. It does NOT prove the saved insert was molded over the current
    yaw range -- the sweep leaves the nominal envelope untouched, and the TPU
    it removes sits low in the cradle rather than in the cover pocket, so no
    cheap analytic probe distinguishes the two inserts. Regenerate the scene
    whenever the sampled range changes.
    """
    worst = 0.0
    for assembly_index in range(1, case.FAN_CASE_STORAGE_COUNT + 1):
        group = [
            obj for obj in references
            if obj.name.startswith(
                f'REFERENCE_ONLY_Fan_Case_Assembly_{assembly_index}_'
            )
        ]
        if not group:
            raise RuntimeError(f'Saved scene lacks assembly {assembly_index}')
        bounds = [case.object_world_bounds(obj) for obj in group]
        merged = tuple(
            value
            for axis in range(3)
            for value in (min(item[0][axis] for item in bounds),
                          max(item[1][axis] for item in bounds))
        )
        expected = case.FAN_CASE_PAIR_STORAGE['installed_reference_bounds'][
            assembly_index - 1
        ]
        deviation = max(abs(a - b) for a, b in zip(merged, expected))
        if deviation > 0.06:
            raise RuntimeError(
                'Saved scene does not match the current configuration: '
                f'assembly={assembly_index} deviation={deviation:.4f} mm '
                f'actual={merged} expected={expected}'
            )
        worst = max(worst, deviation)
    return worst


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
    deviation = check_saved_scene_matches_configuration(nominal)
    print(
        'FAN_ANGLE_RANGE_SCENE_MATCHES_CONFIG '
        f'reference_deviation={deviation:.6f}',
        flush=True,
    )

    # The saved scene holds the mid-range reference pair, so build both
    # endpoints of the supported range explicitly.
    snapshots = {}
    for magnitude in (case.FAN_CASE_STORAGE_MIN_FAN_YAW_DEGREES,
                      case.FAN_CASE_STORAGE_MAX_FAN_YAW_DEGREES):
        endpoint = build_endpoint_pair(material, magnitude)
        snapshots[magnitude] = [
            mesh_snapshot(insert), *(mesh_snapshot(obj) for obj in endpoint)
        ]
        for obj in endpoint:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)

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
        (case.FAN_CASE_STORAGE_MIN_FAN_YAW_DEGREES, -125.0, (.13, .62, .82, 1.0)),
        (case.FAN_CASE_STORAGE_MAX_FAN_YAW_DEGREES, 125.0, (1.0, .34, .06, 1.0)),
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

    low = case.FAN_CASE_STORAGE_MIN_FAN_YAW_DEGREES
    high = case.FAN_CASE_STORAGE_MAX_FAN_YAW_DEGREES
    step = case.FAN_CASE_STORAGE_FAN_YAW_SAMPLE_STEP_DEGREES
    captions = (
        ('HANDED FAN-CASE RANGE / ACTUAL SOURCE GEOMETRY', -246, 133, 7.7),
        (f'{low:g} degrees / both fans straight' if not low
         else f'-{low:g} degrees / +{low:g} degrees', -226, 104, 6.2),
        (f'-{high:g} degrees / +{high:g} degrees', 24, 104, 6.2),
        ('CYAN: minimum angle', -226, -111, 5.0),
        ('ORANGE: maximum angle', 24, -111, 5.0),
        (f'Same lower insert accepts every {step:g}-degree pose from '
         f'{low:g} through {high:g} degrees', -246, -129, 5.2),
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
    minimum_endpoints = f'{low:g}' if not low else f'-{low:g},+{low:g}'
    print(
        'FAN_ANGLE_RANGE_PREVIEW_PASS '
        f'endpoints={minimum_endpoints},-{high:g},+{high:g}',
        flush=True,
    )


if __name__ == '__main__':
    main()
