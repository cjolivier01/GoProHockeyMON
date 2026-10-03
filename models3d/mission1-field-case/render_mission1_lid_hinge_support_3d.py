"""Render the actual lid/base hinge joint before and after reinforcement.

blender --background --python this_file.py -- --scene current.blend \
    --baseline-lid old/mission1_field_case_lid.stl

The scene must have the source-built parts in ``cached_field_case_parts``.
The baseline STL uses the same expanded-case datums as the current lid.
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--baseline-lid", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
    names = json.loads(bpy.context.scene["cached_field_case_parts"])
    base, lid = (bpy.data.objects[names[key]] for key in ("base", "lid"))
    for obj in bpy.context.scene.objects:
        obj.hide_render = True
    bpy.ops.wm.stl_import(filepath=str(args.baseline_lid.resolve()))
    previous = bpy.context.object
    # STL exports include the raised-roof print translation; installed_lid_pose
    # operates on the source's rim datum, before that translation.
    for vertex in previous.data.vertices:
        vertex.co.z -= case.LID_DOME_RISE
    previous.data.update()
    for obj in (previous, lid):
        obj.location, obj.rotation_euler = case.installed_lid_pose(0)
        obj.color = (.26, .48, .68, 1)
        obj.hide_render = True
    base.color = (.19, .23, .29, 1)
    base.hide_render = False
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x, scene.render.resolution_y = 1600, 1100
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "paint.sl"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.show_object_outline = True
    scene.display.shading.background_type = "WORLD"
    scene.world.color = (.035, .045, .065)
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = 1.0
    scene.display.render_aa = "32"
    camera = bpy.data.objects.new("Hinge_Review_Camera", bpy.data.cameras.new("Hinge_Review_Camera"))
    bpy.context.collection.objects.link(camera)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 73
    camera.data.clip_end = 2000
    camera.location = (175, 205, case.BASE_HEIGHT + 45)
    target = Vector((30, case.HINGE_AXIS_Y, case.BASE_HEIGHT + 11))
    aim(camera, target)
    scene.camera = camera
    output = DIRECTORY / "docs/images"
    output.mkdir(parents=True, exist_ok=True)
    for obj, suffix, caption in (
        (previous, "before", "Previous: notch above hinge"),
        (lid, "after", "Reinforced: continuous shoulder into hinge"),
    ):
        obj.hide_render = False
        labels = []
        for text, x, y, size in (
            (caption, -33, 21, 1.6),
            ("Same base, pin axis and lid height", -33, -22, 1.3),
        ):
            location = target + camera.rotation_euler.to_quaternion() @ Vector((x, y, 100))
            labels.append(label(camera, text, location, size))
        scene.render.filepath = str(output / f"mission1_lid_hinge_shoulder_{suffix}.png")
        bpy.ops.render.render(write_still=True)
        for item in labels:
            bpy.data.objects.remove(item, do_unlink=True)
        obj.hide_render = True


if __name__ == "__main__":
    main()
