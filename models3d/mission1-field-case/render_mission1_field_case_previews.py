"""Render documentation previews for the MISSION 1 dual-fan field case.

Run from the repository root with::

    blender --background --factory-startup \
      --python models3d/mission1-field-case/render_mission1_field_case_previews.py

The script builds the same validated reference scene as the model generator and
writes a loaded lower-tier section plus an exploded storage-stack view to
``renderings/``.
"""

from pathlib import Path
import math
import sys

import bpy
from mathutils import Vector


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import mission1_field_case_blender as field_case


RENDER_DIRECTORY = SCRIPT_DIRECTORY / "renderings"
RENDER_RESOLUTION = (1600, 1100)


def make_principled_material(name, color, metallic=0.0, roughness=0.42):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    material.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    material.diffuse_color = (*color, 1.0)
    return material


def assign_material(obj, material):
    obj.data.materials.clear()
    obj.data.materials.append(material)


def aim_object(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat(
        "-Z", "Y"
    ).to_euler()


def add_sun_light(name, location, energy, angle, target):
    data = bpy.data.lights.new(name, type="SUN")
    data.energy = energy
    data.angle = math.radians(angle)
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    aim_object(obj, target)
    return obj


def set_studio_scene():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = RENDER_RESOLUTION
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.use_file_extension = True
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 20
    scene.render.filepath = ""
    scene.view_settings.look = "AgX - Medium High Contrast"

    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.055, 0.07, 0.10, 1.0)
    background.inputs["Strength"].default_value = 0.62

    camera_data = bpy.data.cameras.new("Documentation_Camera")
    camera = bpy.data.objects.new("Documentation_Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.data.lens = 58.0
    camera.data.sensor_width = 36.0
    camera.data.clip_start = 0.1
    camera.data.clip_end = 5000.0
    scene.camera = camera

    target = (0.0, 0.0, 90.0)
    add_sun_light(
        "Studio_Key",
        (300.0, -360.0, 470.0),
        2.8,
        12.0,
        target,
    )
    add_sun_light(
        "Studio_Fill",
        (-330.0, -160.0, 280.0),
        1.4,
        18.0,
        target,
    )
    add_sun_light(
        "Studio_Rim",
        (120.0, 330.0, 390.0),
        2.0,
        10.0,
        target,
    )

    bpy.ops.mesh.primitive_plane_add(size=1400.0, location=(0.0, 0.0, -3.0))
    ground = bpy.context.object
    ground.name = "Studio_Ground"
    assign_material(
        ground,
        make_principled_material(
            "Studio_Ground_Material",
            (0.14, 0.16, 0.20),
            roughness=0.72,
        ),
    )
    return camera


def reference_objects(prefix):
    return [obj for obj in bpy.context.scene.objects if obj.name.startswith(prefix)]


def set_reference_materials():
    shell = make_principled_material(
        "Preview_Rugged_Shell",
        (0.08, 0.105, 0.15),
        roughness=0.31,
    )
    tray = make_principled_material(
        "Preview_TPU_Orange",
        (1.0, 0.19, 0.025),
        roughness=0.44,
    )
    fan_holder = make_principled_material(
        "Fan_Holder_Teal",
        (0.025, 0.34, 0.42),
        metallic=0.08,
        roughness=0.34,
    )
    installed_fan = make_principled_material(
        "Installed_Fan_Charcoal",
        (0.075, 0.09, 0.12),
        roughness=0.30,
    )
    camera = make_principled_material(
        "Mission_Camera_Graphite",
        (0.15, 0.19, 0.25),
        metallic=0.12,
        roughness=0.30,
    )
    battery = make_principled_material(
        "Battery_Ice",
        (0.52, 0.66, 0.78),
        metallic=0.06,
        roughness=0.36,
    )
    assign_material(PARTS["base"], shell)
    assign_material(PARTS["fan_cradle"], tray)
    assign_material(PARTS["equipment_tray"], tray)
    for obj in reference_objects("REFERENCE_ONLY_Stored_"):
        assign_material(obj, fan_holder)
    for obj in reference_objects("REFERENCE_ONLY_Installed_80mm_Fan_"):
        assign_material(obj, installed_fan)
    for obj in reference_objects("REFERENCE_ONLY_MISSION1_"):
        assign_material(obj, camera)
    for obj in reference_objects("REFERENCE_ONLY_Enduro2_"):
        assign_material(obj, battery)
    for obj in reference_objects("REFERENCE_ONLY_MISSION1_Battery_Cage_Door_"):
        assign_material(obj, battery)


def hide_non_storage_objects():
    visible_parts = {"base", "fan_cradle", "equipment_tray"}
    for key, obj in PARTS.items():
        obj.hide_render = key not in visible_parts
    visible_prefixes = (
        "REFERENCE_ONLY_Stored_",
        "REFERENCE_ONLY_Installed_80mm_Fan_",
        "REFERENCE_ONLY_MISSION1_",
        "REFERENCE_ONLY_Enduro2_",
        "REFERENCE_ONLY_MISSION1_Battery_Cage_Door_",
    )
    for obj in reference_objects("REFERENCE_ONLY_"):
        obj.hide_render = not obj.name.startswith(visible_prefixes)


def render_loaded_fan_tier(camera):
    cutaway_base = PARTS["base"].copy()
    cutaway_base.data = PARTS["base"].data.copy()
    cutaway_base.name = "PREVIEW_ONLY_Lower_Fan_Tier_Sectioned_Base"
    bpy.context.collection.objects.link(cutaway_base)
    section_height = 72.0
    section_cutter = field_case.add_rounded_box(
        "PREVIEW_ONLY_Base_Upper_Section_Cutter",
        (500.0, 500.0, 300.0),
        (0.0, 0.0, section_height + 150.0),
        bevel=0.0,
    )
    field_case.difference_from(cutaway_base, section_cutter)
    PARTS["base"].hide_render = True
    PARTS["equipment_tray"].hide_render = True
    content_prefixes = (
        "REFERENCE_ONLY_MISSION1_",
        "REFERENCE_ONLY_Enduro2_",
        "REFERENCE_ONLY_MISSION1_Battery_Cage_Door_",
    )
    for prefix in content_prefixes:
        for obj in reference_objects(prefix):
            obj.hide_render = True
    camera.location = (420.0, -515.0, 380.0)
    aim_object(camera, (0.0, 0.0, 58.0))
    bpy.context.scene.render.filepath = str(
        RENDER_DIRECTORY / "mission1_field_case_fan_tier_cutaway.png"
    )
    bpy.ops.render.render(write_still=True)
    cutaway_base.hide_render = True
    PARTS["base"].hide_render = False


def render_exploded_stack(camera):
    PARTS["equipment_tray"].hide_render = False
    for prefix in (
        "REFERENCE_ONLY_MISSION1_",
        "REFERENCE_ONLY_Enduro2_",
        "REFERENCE_ONLY_MISSION1_Battery_Cage_Door_",
    ):
        for obj in reference_objects(prefix):
            obj.hide_render = False

    cradle_shift = 191.8
    equipment_shift = 221.0
    PARTS["fan_cradle"].location.z += cradle_shift
    PARTS["equipment_tray"].location.z += equipment_shift
    for prefix in (
        "REFERENCE_ONLY_Stored_",
        "REFERENCE_ONLY_Installed_80mm_Fan_",
    ):
        for obj in reference_objects(prefix):
            obj.location.z += cradle_shift
    for prefix in (
        "REFERENCE_ONLY_MISSION1_",
        "REFERENCE_ONLY_Enduro2_",
        "REFERENCE_ONLY_MISSION1_Battery_Cage_Door_",
    ):
        for obj in reference_objects(prefix):
            obj.location.z += equipment_shift

    camera.location = (750.0, -920.0, 620.0)
    aim_object(camera, (0.0, 0.0, 205.0))
    bpy.context.scene.render.filepath = str(
        RENDER_DIRECTORY / "mission1_field_case_storage_exploded.png"
    )
    bpy.ops.render.render(write_still=True)


field_case.BUILD_REFERENCE_MOCKUPS = True
field_case.EXPORT_STL = False
field_case.SAVE_BLEND = False
PARTS = field_case.build_mission1_field_case()
RENDER_DIRECTORY.mkdir(parents=True, exist_ok=True)
CAMERA = set_studio_scene()
hide_non_storage_objects()
set_reference_materials()
render_loaded_fan_tier(CAMERA)
render_exploded_stack(CAMERA)
print(f"FIELD_CASE_RENDERED_PREVIEWS {RENDER_DIRECTORY}")
