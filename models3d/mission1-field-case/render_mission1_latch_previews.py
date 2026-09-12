"""Render the actual reinforced latch meshes and their unchanged case fit.

From the repository root::

    blender --background --factory-startup --threads 8 --python-exit-code 1 \
      --python models3d/mission1-field-case/render_mission1_latch_previews.py

The comparison rebuilds the pre-reinforcement hook from commit 717b07b.  Pass
``-- --baseline-ref REF`` to compare another revision.  No STL is used as a
geometry source.  The current pair of printable latch STLs is also exported.
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


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def label(camera, text, location, size=1.6):
    curve = bpy.data.curves.new(text, 'FONT')
    curve.body = text
    curve.size = size
    curve.extrude = 0.0
    obj = bpy.data.objects.new(text, curve)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = camera.rotation_euler
    obj.color = (0.88, 0.92, 0.98, 1.0)
    return obj


def render(camera, name, position, target, scale):
    camera.location = position
    camera.data.ortho_scale = scale
    aim(camera, target)
    bpy.context.scene.render.filepath = str(DIRECTORY / 'renderings' / name)
    bpy.ops.render.render(write_still=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline-ref', default='717b07b')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    case.clear_scene()
    case.set_units()
    orange = case.make_material('Reinforced_Hook', (0.95, 0.29, 0.055))
    gray = case.make_material('Original_Hook', (0.40, 0.45, 0.53))
    lever, hook = case.create_pelican_latch_parts(orange)
    bpy.context.view_layer.update()
    for name, obj in (('latch_lever', lever), ('latch_hook', hook)):
        case.validate_built_part(name, obj)
    case.validate_built_latch_hook_capture(hook)
    for filename, obj in ((case.LATCH_LEVER_STL_NAME, lever), (case.LATCH_HOOK_STL_NAME, hook)):
        case.export_stl(DIRECTORY / filename, obj)

    baseline_source = subprocess.check_output(
        ['git', 'show', f'{args.baseline_ref}:models3d/mission1-field-case/mission1_field_case_blender.py'],
        cwd=DIRECTORY, text=True,
    )
    baseline = {'__name__': 'latch_baseline', '__file__': case.__file__}
    exec(compile(baseline_source, case.__file__, 'exec'), baseline)
    old_lever, old_hook = baseline['create_pelican_latch_parts'](gray)
    old_lever.hide_render = True
    lever.hide_render = True
    for obj, color in ((old_hook, (0.40, 0.45, 0.53, 1)), (hook, (0.95, 0.29, 0.055, 1))):
        obj.rotation_euler = (0, 0, 0)
        obj.color = color

    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1100
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.studiolight_rotate_z = math.radians(25)
    scene.display.shading.color_type = 'OBJECT'
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = 'BOTH'
    scene.display.shading.show_object_outline = True
    scene.display.shading.background_type = 'WORLD'
    scene.world.color = (0.035, 0.045, 0.065)
    scene.view_settings.view_transform = 'Standard'
    scene.display.render_aa = '32'
    camera = bpy.data.objects.new('Latch_Review_Camera', bpy.data.cameras.new('Latch_Review_Camera'))
    bpy.context.collection.objects.link(camera)
    camera.data.type = 'ORTHO'
    camera.data.clip_start = 0.1
    camera.data.clip_end = 2000
    scene.camera = camera
    (DIRECTORY / 'renderings').mkdir(exist_ok=True)

    old_hook.location = (0, 0, 13)
    hook.location = (0, 0, -11)
    camera.location = (120, -18, 0)
    aim(camera, (0, -18, 0))
    labels = [
        label(camera, 'BEFORE  /  original connector below 1 mm', (12, -42, 20), 1.35),
        label(camera, 'REINFORCED  /  3.4 mm neck, 3.2 mm pivot wall', (12, -42, -3.6), 1.35),
        label(camera, 'Case and lid geometry unchanged', (12, -42, -23), 1.3),
    ]
    # Workbench includes text in its shadow pass; omit shadows for this
    # annotated orthographic view so headings do not project onto the hooks.
    scene.display.shading.show_shadows = False
    render(camera, 'mission1_latch_web_comparison.png', (120, -18, 0), (0, -18, 0), 69)
    for obj in labels:
        obj.hide_render = True
    old_hook.hide_render = True
    hook.location = (0, 0, 0)
    scene.display.shading.show_shadows = True
    render(camera, 'mission1_latch_reinforced_hook.png', (65, 16, 39), (0, -18, -1), 61)

    shell = case.make_material('Unchanged_Case', (0.19, 0.24, 0.30))
    base = case.create_base(shell)
    lid, inlay = case.create_lid(shell, orange)
    for obj in (base, lid):
        obj.color = (0.19, 0.24, 0.30, 1)
    inlay.hide_render = True
    lid.location, lid.rotation_euler = case.installed_lid_pose(0.0)
    lever.hide_render = False
    lever.color = (0.34, 0.40, 0.48, 1)
    case.position_installed_latch_lever(lever, case.LATCH_X_CENTERS[1])
    case.position_installed_latch_hook(hook, case.LATCH_X_CENTERS[1])
    # Show the real mating surfaces by cutting away only the outer guard in
    # these temporary visualization copies.  Production meshes stay intact.
    for source in (base, lid):
        display = source.copy()
        display.data = source.data.copy()
        bpy.context.collection.objects.link(display)
        source.hide_render = True
        case.select_only(display)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        cutter = case.add_rounded_box('PREVIEW_ONLY_Remove_Outer_Guard', (100, 90, 150), (142.3, -107, 90), bevel=0)
        case.difference_from(display, cutter)
        display.hide_render = False
    target = (82, -90, 84)
    camera.location = (153, -174, 117)
    aim(camera, target)
    caption_location = Vector(target) + camera.rotation_euler.to_quaternion() @ Vector((-48, 30, 80))
    label(camera, 'Installed / outer guard cut away for visibility', caption_location, 1.8)
    scene.display.shading.show_shadows = False
    render(camera, 'mission1_latch_reinforced_installed.png', (153, -174, 117), target, 104)
    print('FIELD_CASE_LATCH_PREVIEWS_COMPLETE', flush=True)


if __name__ == '__main__':
    main()
