"""Render the generated cap and shared cable bay from a validated scene.

blender -b --python this_file.py -- --scene /path/to/field-case.blend
"""

import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DIRECTORY))
import mission1_field_case_blender as case
from render_mission1_latch_previews import aim, label


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
    for obj in bpy.data.objects:
        obj.hide_render = True
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
    scene.world.color = (.025, .035, .055)
    scene.view_settings.view_transform = "Standard"
    scene.display.render_aa = "32"
    camera = bpy.data.objects.new("Packing_Camera", bpy.data.cameras.new("Packing_Camera"))
    bpy.context.collection.objects.link(camera)
    camera.data.type = "ORTHO"
    camera.data.clip_end = 2000
    scene.camera = camera

    def show(obj, color):
        obj.hide_render = False
        obj.hide_set(False)
        obj.color = (*color, 1)

    def render(filename, position, target, scale, title, subtitle):
        camera.location = position
        camera.data.ortho_scale = scale
        aim(camera, target)
        labels = []
        for text, y, size in ((title, .26, .025), (subtitle, -.27, .016)):
            point = Vector(target) + camera.rotation_euler.to_quaternion() @ Vector((-.46 * scale, y * scale, scale))
            labels.append(label(camera, text, point, scale * size))
        scene.render.filepath = str(DIRECTORY / "renderings" / filename)
        bpy.ops.render.render(write_still=True)
        for obj in labels:
            bpy.data.objects.remove(obj, do_unlink=True)

    insert = bpy.data.objects["Field_Case_Fan_Case_Pair_Lower_TPU_Insert"]
    show(insert, (.37, .44, .52))
    shown = [insert]
    for obj in tuple(bpy.data.objects):
        if obj.name.startswith("REFERENCE_ONLY_Fan_Case_Lens_Cap_"):
            show(obj, (.95, .3, .08)); shown.append(obj)
        elif obj.name.startswith("REFERENCE_ONLY_Shared_Y_Cable_"):
            show(obj, (1, .55, .05)); shown.append(obj)
        elif obj.name.startswith(("REFERENCE_ONLY_Fan_Case_Cable_", "REFERENCE_ONLY_Fan_Case_PWM_")):
            show(obj, (.09, .16, .24)); shown.append(obj)
        elif obj.name.startswith(("REFERENCE_ONLY_Fan_Case_Enduro_", "REFERENCE_ONLY_Fan_Case_Battery_Door_")):
            show(obj, (.62, .78, .89)); shown.append(obj)
    render("mission1_caps_shared_cable_insert.png", (230, -320, 390), (0, 0, 30), 470,
           "CAPPED LENSES / SHARED CABLE BAY", "Actual generated insert | Camera bodies and upper trays hidden")

    # Isolate the front bay and uncover the two lips above the central coil.
    section = insert.copy()
    section.data = insert.data.copy()
    bpy.context.collection.objects.link(section)
    case.boolean_apply(section, case.add_rounded_box("Front_Storage_Detail",
        (240, 60, 100), (0, -60, 50), bevel=0), "INTERSECT")
    insert.hide_render = True
    show(section, (.37, .44, .52))
    for obj in shown:
        if "Lens_Cap_" in obj.name or obj.name.endswith(("Shared_Y_Cable_USB_A", "Shared_Y_Cable_Splitter")):
            obj.hide_render = True
    render("mission1_shared_cable_retaining_lips.png", (-5, -200, 350), (-5, -55, 20), 280,
           "OPEN CABLE BAY / RETAINING LIPS", "Coil loads from above | 45-degree retaining lips | USB plug and splitter hidden")
    for obj in (*shown, section):
        obj.hide_render = True
    cap = case.lens_cap.build(vars(case))
    show(cap, (.95, .3, .08))
    render("mission1_geometric_lens_cap.png", (70, -90, 100), (0, 0, 4), 78,
           "MISSION 1 LENS CAP", "48 x 48 x 11 mm | TPU for AMS | Print two, closed face down")

    cap.hide_render = True
    parts = {key: bpy.data.objects[name] for key, name in
             json.loads(scene["cached_field_case_parts"]).items()}
    lid_location, lid_rotation = case.installed_lid_pose(0)
    for key in ("lid", "logo_orange_inlay"):
        parts[key].location, parts[key].rotation_euler = lid_location, lid_rotation
    case.pose_gasket_with_lid(parts["gasket"], lid_location, lid_rotation)
    exterior = [parts[key] for key in ("base", "lid", "logo_orange_inlay", "gasket")]
    handle = bpy.data.objects["REFERENCE_ONLY_Folded_Pivoting_Handle"]
    handle.rotation_euler = (0, 0, 0)
    handle.location = (0, case.HANDLE_PIVOT_Y,
                       case.HANDLE_PIVOT_Z - case.HANDLE_LOCAL_PIVOT_Z)
    exterior.append(handle)
    exterior.extend(obj for obj in bpy.data.objects if obj.name.startswith((
        "REFERENCE_ONLY_CLOSED_Pelican_Source_", "REFERENCE_ONLY_Latch_",
        "REFERENCE_ONLY_Handle_")))
    bpy.context.view_layer.update()
    carrying = Matrix.Rotation(-math.pi / 2, 4, "X")
    for obj in exterior:
        obj.matrix_world = carrying @ obj.matrix_world
        show(obj, (.95, .3, .08) if obj == parts["logo_orange_inlay"] else (.28, .34, .42))
    render("mission1_lid_carry_orientation.png", (240, 650, 200), (0, 95, 10), 560,
           "LID ARTWORK / CARRY ORIENTATION", "Handle at top | Symbol and lettering read upright")


if __name__ == "__main__":
    main()
