"""Render the lower insert before and after a change to the sampled yaw range.

The baseline is a lower-insert STL exported by the previous revision, which
is written in print coordinates (the installed Z subtracted), so it drops
straight back onto the current scene's insert for comparison.

blender --background --factory-startup --python-exit-code 1 \
  --python this_file.py -- \
  --scene current-case.blend --baseline-insert previous-insert.stl
"""
import argparse
import json
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector

DIRECTORY = Path(__file__).resolve().parent
# Swept yaw range of the exported baseline insert this renderer compares against.
BASELINE_LOW = 15.0
BASELINE_HIGH = 30.0
sys.path.insert(0, str(DIRECTORY))
import mission1_field_case_blender as case
from render_mission1_latch_previews import aim, label


def mesh_volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    value = bm.calc_volume(signed=False)
    bm.free()
    return value


def mesh_snapshot(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        vertices = [tuple(evaluated.matrix_world @ v.co) for v in mesh.vertices]
        faces = [tuple(p.vertices) for p in mesh.polygons]
    finally:
        evaluated.to_mesh_clear()
    return obj.name, vertices, faces


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--baseline-insert', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])

    bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
    names = json.loads(bpy.context.scene['cached_field_case_parts'])
    current = bpy.data.objects[names['fan_case_pair_insert']]

    existing = {o.as_pointer() for o in bpy.data.objects}
    bpy.ops.wm.stl_import(filepath=str(args.baseline_insert.resolve()))
    baseline = next(
        o for o in bpy.data.objects if o.as_pointer() not in existing
    )
    baseline.name = 'BASELINE_Lower_Insert'
    baseline.location = (0.0, 0.0, case.FAN_CASE_PAIR_INSERT_INSTALLED_Z)
    bpy.context.view_layer.update()

    baseline_volume = mesh_volume(baseline)
    current_volume = mesh_volume(current)

    # Capture both parts before the boolean, which consumes its cutter.
    snapshots = {
        'baseline': [mesh_snapshot(baseline)],
        'current': [mesh_snapshot(current)],
    }

    # The TPU the wider sweep carved out of the cradle.
    removed = baseline.copy()
    removed.data = baseline.data.copy()
    bpy.context.collection.objects.link(removed)
    removed.name = 'RELEASED_TPU'
    cutter = current.copy()
    cutter.data = current.data.copy()
    bpy.context.collection.objects.link(cutter)
    bpy.context.view_layer.update()
    case.boolean_apply(removed, cutter, 'DIFFERENCE')
    bpy.context.view_layer.update()
    removed_volume = mesh_volume(removed)
    snapshots['current'].append(mesh_snapshot(removed))

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
        'Insert_Comparison_Camera',
        bpy.data.cameras.new('Insert_Comparison_Camera'),
    )
    bpy.context.collection.objects.link(camera)
    camera.data.type = 'ORTHO'
    camera.data.clip_end = 2000
    camera.data.ortho_scale = 525
    camera.location = (0, -430, 470)
    aim(camera, (0, 5, 25))
    scene.camera = camera

    for key, offset_x in (('baseline', -125.0), ('current', 125.0)):
        for name, vertices, faces in snapshots[key]:
            obj = case.create_mesh_object(
                f'Preview_{key}_{name}', vertices, faces
            )
            obj.location.x += offset_x
            obj.color = (
                (1.0, .34, .06, 1.0) if name == 'RELEASED_TPU'
                else (.35, .41, .48, 1.0)
            )

    low = case.FAN_CASE_STORAGE_MIN_FAN_YAW_DEGREES
    high = case.FAN_CASE_STORAGE_MAX_FAN_YAW_DEGREES
    # The baseline STL predates the current constants, so its own swept range
    # is a fixed property of that export rather than something to read back
    # from the module.
    captions = (
        ('LOWER TPU INSERT / CHANGED SWEPT CAVITY', -246, 137, 7.4),
        ('BEFORE', -226, 110, 6.4),
        (f'swept {BASELINE_HIGH:g} degrees down to {BASELINE_LOW:g} degrees per side',
         -226, 99, 4.6),
        ('AFTER', 24, 110, 6.4),
        (f'swept {high:g} degrees down to {low:g} degrees per side',
         24, 99, 4.6),
        (f'{baseline_volume / 1000.0:.2f} cm3 of TPU',
         -226, -116, 5.0),
        (f'{current_volume / 1000.0:.2f} cm3 of TPU', 24, -116, 5.0),
        (f'ORANGE: the {removed_volume / 1000.0:.2f} cm3 released so a fan '
         f'case at {low:g} degrees seats', 24, -128, 4.6),
        ('Outer envelope, assembly centers and every tray dimension unchanged',
         -246, -145, 4.8),
    )
    for text, x, y, size in captions:
        position = Vector((0, 5, 25)) + camera.rotation_euler.to_quaternion() @ Vector(
            (x, y, 525)
        )
        label(camera, text, position, size)

    output = DIRECTORY / 'renderings' / 'mission1_fan_angle_insert_comparison.png'
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)
    print(
        'FAN_ANGLE_INSERT_COMPARISON_PASS '
        f'baseline_cm3={baseline_volume / 1000.0:.3f} '
        f'current_cm3={current_volume / 1000.0:.3f} '
        f'released_cm3={removed_volume / 1000.0:.3f}',
        flush=True,
    )


if __name__ == '__main__':
    main()
