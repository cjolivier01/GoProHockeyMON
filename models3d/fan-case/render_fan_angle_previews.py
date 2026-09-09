"""Render inside/outside comparisons of the adjustable rear fan mount.

    blender --background --factory-startup --threads 8 --python-exit-code 1 \
        --python models3d/fan-case/render_fan_angle_previews.py

Each option runs the complete assembly validation before rendering the bare
rear shell. The cartridge is hidden in inside views so its sealing surface,
the fixed camera stops, and the changing airflow passage can be inspected.
"""

from pathlib import Path
import math
import sys

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gopro_fan_case_parametric_blender as case


OPTIONS = (
    ("straight", 0, 0),
    ("left_45", -45, 0),
    ("right_45", 45, 0),
    ("down_45", 0, -45),
    ("up_45", 0, 45),
    ("right_30_down_20", 30, -20),
    ("right_45_up_45", 45, 45),
)
OUTPUT = HERE / "renderings"


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def studio():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.12, 0.15, 0.19, 1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.55
    scene.view_settings.look = "AgX - Medium High Contrast"
    for name, position, energy in (
        ("Key", (80, -140, 200), 2.5),
        ("Interior", (-60, 150, 140), 2.0),
        ("Fill", (-160, -80, 20), 0.8),
    ):
        data = bpy.data.lights.new(name, "SUN")
        data.energy = energy
        data.angle = math.radians(15)
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.location = position
        aim(obj, (0, 0, 0))
    data = bpy.data.cameras.new("Preview_Camera")
    data.type = "ORTHO"
    data.ortho_scale = 136
    data.clip_end = 2000
    camera = bpy.data.objects.new("Preview_Camera", data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    return camera


def main():
    OUTPUT.mkdir(exist_ok=True)
    for name, horizontal, vertical in OPTIONS:
        case.FAN_ANGLE_HORIZONTAL_DEG = horizontal
        case.FAN_ANGLE_VERTICAL_DEG = vertical
        case.EXPORT_STL = False
        case.LAYOUT_MODE = "assembled"
        print(f"PREVIEW_OPTION {name} horizontal={horizontal} vertical={vertical}", flush=True)
        back, _insert = case.build_gopro_fan_case()
        for obj in bpy.context.scene.objects:
            obj.hide_render = obj != back
        material = bpy.data.materials.new("Preview_Shell")
        material.diffuse_color = (0.12, 0.43, 0.55, 1)
        material.use_nodes = True
        shader = material.node_tree.nodes.get("Principled BSDF")
        shader.inputs["Base Color"].default_value = material.diffuse_color
        shader.inputs["Roughness"].default_value = 0.36
        back.data.materials.clear()
        back.data.materials.append(material)
        camera = studio()
        for view, position, target in (
            ("outside", (65, -210, 95), (0, -16, 0)),
            ("inside", (60, 210, 100), (0, -8, 0)),
        ):
            camera.location = position
            aim(camera, target)
            bpy.context.scene.render.filepath = str(OUTPUT / f"fan_angle_{name}_{view}.png")
            bpy.ops.render.render(write_still=True)
        if name == "right_30_down_20":
            # One assembled example verifies how the unchanged adapter sits
            # on the tilted pad. Its canonical STL still prints flange-down.
            adapter = bpy.data.objects.get("GoPro_Fan_Case_Rear_Fan_Adapter")
            if adapter is None:
                raise RuntimeError("The default rear adapter is missing")
            adapter.hide_render = False
            camera.location = (170, -180, 100)
            camera.data.ortho_scale = 170
            aim(camera, (0, -30, 0))
            bpy.context.scene.render.filepath = str(OUTPUT / "fan_angle_adapter_assembled.png")
            bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
