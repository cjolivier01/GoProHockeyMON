"""Render the lower-insert cavity before/after its rear fan-depth relief.

Run from the repository root with::

    blender --background --factory-startup --threads 8 --python-exit-code 1 \
      --python models3d/mission1-field-case/render_mission1_fan_rear_clearance.py
"""

from pathlib import Path
import sys

import bpy
from mathutils import Vector


DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DIRECTORY))

import mission1_field_case_blender as case
from render_mission1_latch_previews import aim, label


def main():
    case.clear_scene()
    neutral = case.make_material("Rear_Clearance_Build", (0.5, 0.5, 0.5))
    references = case.create_fan_case_pair_reference_mockups(*([neutral] * 7))

    configured_allowance = case.FAN_CASE_REAR_DEPTH_ALLOWANCE
    try:
        case.FAN_CASE_REAR_DEPTH_ALLOWANCE = 0.0
        before = case.create_fan_case_pair_insert(neutral, references)
        case.FAN_CASE_REAR_DEPTH_ALLOWANCE = configured_allowance
        after = case.create_fan_case_pair_insert(neutral, references)
    finally:
        case.FAN_CASE_REAR_DEPTH_ALLOWANCE = configured_allowance

    for obj in references:
        obj.hide_render = True
        obj.hide_set(True)

    before.color = (0.34, 0.41, 0.50, 1.0)
    after.color = (0.34, 0.41, 0.50, 1.0)

    # Subtract the two completed inserts so the orange overlay cannot claim
    # theoretical cutter space that a later union or outer clip refilled.
    removed = before.copy()
    removed.data = before.data.copy()
    removed.name = "Actual_Finished_Insert_Material_Removed"
    bpy.context.collection.objects.link(removed)
    cutter = after.copy()
    cutter.data = after.data.copy()
    cutter.name = "TEMPORARY_Revised_Insert_Difference_Cutter"
    bpy.context.collection.objects.link(cutter)
    case.boolean_apply(removed, cutter, "DIFFERENCE")
    _minimum, maximum = case.object_world_bounds(removed)
    if len(removed.data.polygons) == 0 or maximum.z <= case.FAN_CASE_PAIR_INSERT_FLOOR:
        raise RuntimeError("Finished before/after inserts have no rear relief difference")
    removed.color = (1.0, 0.28, 0.035, 1.0)

    before.location.x = -118.0
    after.location.x = 118.0
    removed.location.x = 118.0
    removed.location.z = 35.0

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1100
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studio_light = "paint.sl"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.show_object_outline = True
    scene.display.shading.background_type = "WORLD"
    scene.world.color = (0.025, 0.035, 0.055)
    scene.view_settings.view_transform = "Standard"
    scene.display.render_aa = "32"

    camera_data = bpy.data.cameras.new("Rear_Clearance_Camera")
    camera = bpy.data.objects.new("Rear_Clearance_Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 500.0
    camera.data.clip_end = 2000.0
    camera.location = (0.0, -430.0, 430.0)
    aim(camera, (0.0, 6.0, 30.0))
    scene.camera = camera

    captions = (
        ("REAR FAN POCKET: +1.5 mm DEPTH", -232, 134, 8.5),
        ("Local relief follows each handed fan axis; case envelope is unchanged",
         -232, 118, 5.3),
        ("BEFORE / nominal 20 mm fan", -218, 83, 6.7),
        ("AFTER / accepts 21.5 mm fan", 18, 83, 6.7),
        ("Orange: actual finished-mesh material removed, lifted 35 mm for visibility",
         18, -93, 5.1),
        ("Only the lower TPU insert needs reprinting", -232, -116, 5.5),
        ("Source-built ±15° geometry | 1.0 mm running clearance retained",
         -232, -132, 4.7),
    )
    labels = []
    target = Vector((0.0, 6.0, 30.0))
    for text, x, y, size in captions:
        position = target + camera.rotation_euler.to_quaternion() @ Vector(
            (x, y, camera.data.ortho_scale)
        )
        labels.append(label(camera, text, position, size))

    output = DIRECTORY / "renderings" / "mission1_fan_rear_clearance.png"
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"Missing rear-clearance rendering: {output}")
    print(
        "MISSION1_FAN_REAR_CLEARANCE_RENDER_PASS "
        f"allowance={configured_allowance:.3f} output={output}",
        flush=True,
    )


if __name__ == "__main__":
    main()
