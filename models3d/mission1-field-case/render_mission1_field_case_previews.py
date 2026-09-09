"""Render documentation previews for the MISSION 1 field case loadouts.

Run from the repository root with::

    blender --background --factory-startup \
      --python models3d/mission1-field-case/render_mission1_field_case_previews.py

The script builds the same validated reference scene as the model generator and
writes both loadouts, the TPU snap hinge/coupon, and the closed latch protectors
to ``renderings/``.
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
    carrier = make_principled_material(
        "Preview_TPU_Carrier_Amber",
        (1.0, 0.42, 0.035),
        roughness=0.43,
    )
    storage_bin = make_principled_material(
        "Preview_TPU_Storage_Bin",
        (0.93, 0.12, 0.018),
        roughness=0.45,
    )
    closing_pad = make_principled_material(
        "Preview_TPU_Flat_Closing_Pad",
        (1.0, 0.68, 0.08),
        roughness=0.46,
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
    cable = make_principled_material(
        "Fan_Cable_Black",
        (0.018, 0.022, 0.028),
        roughness=0.37,
    )
    tpu_lid = make_principled_material(
        "Preview_TPU_68D_Lid",
        (0.12, 0.16, 0.23),
        roughness=0.46,
    )
    hardware = make_principled_material(
        "Fan_Case_Fastener_Steel",
        (0.42, 0.47, 0.54),
        metallic=0.68,
        roughness=0.25,
    )
    assign_material(PARTS["base"], shell)
    assign_material(PARTS["lid"], shell)
    assign_material(PARTS["logo_orange_inlay"], tray)
    assign_material(PARTS["fan_cradle"], tray)
    assign_material(PARTS["equipment_tray"], tray)
    assign_material(PARTS["fan_case_pair_insert"], tray)
    assign_material(PARTS["fan_case_pair_carrier"], carrier)
    assign_material(PARTS["fan_case_pair_storage_bin"], storage_bin)
    assign_material(PARTS["fan_case_pair_lid_pad"], closing_pad)
    assign_material(PARTS["tpu_hinge_coupon"], tray)
    assign_material(PARTS["tpu_snap_lid"], tpu_lid)
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
    for prefix in (
        "REFERENCE_ONLY_Fan_Case_Enduro_Battery_",
        "REFERENCE_ONLY_Fan_Case_Battery_Door_",
    ):
        for obj in reference_objects(prefix):
            assign_material(obj, battery)
    for obj in reference_objects("REFERENCE_ONLY_Fan_Case_Assembly_"):
        if "MISSION1" in obj.name:
            assign_material(obj, camera)
        elif "Direct_40mm_Rear_Fan" in obj.name:
            assign_material(obj, installed_fan)
        elif "Wrapping_Fan_Cover" in obj.name:
            assign_material(obj, battery)
        elif any(
            token in obj.name
            for token in ("M3x40_Bolt", "M3_Hex_Head", "Thumb_Nut")
        ):
            assign_material(obj, hardware)
        else:
            assign_material(obj, fan_holder)
    for prefix in (
        "REFERENCE_ONLY_Fan_Case_Cable_Lead_",
        "REFERENCE_ONLY_Fan_Case_Cable_Coil_",
        "REFERENCE_ONLY_Fan_Case_PWM_Plug_",
    ):
        for obj in reference_objects(prefix):
            assign_material(obj, cable)


def set_visible(part_keys=(), reference_prefixes=()):
    """Show only the selected printable and exact reference objects."""
    visible_parts = set(part_keys)
    for key, obj in PARTS.items():
        obj.hide_render = key not in visible_parts
    for obj in reference_objects("REFERENCE_ONLY_"):
        obj.hide_render = not obj.name.startswith(tuple(reference_prefixes))


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


def render_loaded_compact_stack(camera):
    # A steep view preserves the complete printable shell and exterior impact
    # protectors while still looking down into the recessed upper tray.
    PARTS["base"].hide_render = False
    camera.location = (340.0, -430.0, 500.0)
    aim_object(camera, (0.0, -3.0, 62.0))
    bpy.context.scene.render.filepath = str(
        RENDER_DIRECTORY / "mission1_field_case_fan_tier_cutaway.png"
    )
    bpy.ops.render.render(write_still=True)


def render_exploded_stack(camera):
    PARTS["equipment_tray"].hide_render = False
    for prefix in (
        "REFERENCE_ONLY_MISSION1_",
        "REFERENCE_ONLY_Enduro2_",
        "REFERENCE_ONLY_MISSION1_Battery_Cage_Door_",
    ):
        for obj in reference_objects(prefix):
            obj.hide_render = False

    stack_gap = 30.0
    cradle_shift = (
        field_case.BASE_HEIGHT
        + stack_gap
        - field_case.FAN_CRADLE_INSTALLED_Z
    )
    equipment_shift = (
        field_case.FAN_ASSEMBLY_INSTALLED_TOP_Z
        + cradle_shift
        + stack_gap
        - field_case.EQUIPMENT_TRAY_INSTALLED_Z
    )
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


def render_closed_latch_protectors(camera):
    for obj in PARTS.values():
        obj.hide_render = True
    for obj in reference_objects("REFERENCE_ONLY_"):
        obj.hide_render = True
    PARTS["base"].hide_render = False

    lid_location, lid_rotation = field_case.installed_lid_pose(0.0)
    installed_lid_parts = []
    for key in ("lid", "logo_orange_inlay"):
        source = PARTS[key]
        installed = source.copy()
        installed.data = source.data.copy()
        installed.name = f"PREVIEW_ONLY_Closed_{source.name}"
        bpy.context.collection.objects.link(installed)
        installed.location = lid_location
        installed.rotation_euler = lid_rotation
        installed.hide_render = False
        installed_lid_parts.append(installed)

    for prefix in (
        "REFERENCE_ONLY_CLOSED_Pelican_Source_",
        "REFERENCE_ONLY_Latch_",
        "REFERENCE_ONLY_Folded_Pivoting_Handle",
        "REFERENCE_ONLY_Handle_",
    ):
        for obj in reference_objects(prefix):
            obj.hide_render = False

    camera.location = (400.0, -540.0, 265.0)
    aim_object(camera, (0.0, -5.0, 56.0))
    bpy.context.scene.render.filepath = str(
        RENDER_DIRECTORY / "mission1_field_case_latch_protectors.png"
    )
    bpy.ops.render.render(write_still=True)

    for obj in installed_lid_parts:
        obj.hide_render = True


def render_fan_case_loadout(camera):
    """Show the two complete assemblies beneath the fan-side storage bin."""
    set_visible(
        (
            "base",
            "fan_case_pair_insert",
            "fan_case_pair_carrier",
            "fan_case_pair_storage_bin",
        ),
        (
            "REFERENCE_ONLY_Fan_Case_Assembly_",
            "REFERENCE_ONLY_Fan_Case_Cable_Lead_",
            "REFERENCE_ONLY_Fan_Case_Cable_Coil_",
            "REFERENCE_ONLY_Fan_Case_PWM_Plug_",
            "REFERENCE_ONLY_Fan_Case_Enduro_Battery_",
            "REFERENCE_ONLY_Fan_Case_Battery_Door_",
        ),
    )
    camera.location = (345.0, -440.0, 455.0)
    aim_object(camera, (0.0, -3.0, 56.0))
    bpy.context.scene.render.filepath = str(
        RENDER_DIRECTORY / "mission1_field_case_fan_case_loadout.png"
    )
    bpy.ops.render.render(write_still=True)


def render_handed_fan_loadout(camera):
    """Expose the independently angled fans, contoured bulk, and cable routes."""
    set_visible(
        ("fan_case_pair_insert",),
        (
            "REFERENCE_ONLY_Fan_Case_Assembly_",
            "REFERENCE_ONLY_Fan_Case_Cable_Lead_",
            "REFERENCE_ONLY_Fan_Case_Cable_Coil_",
            "REFERENCE_ONLY_Fan_Case_PWM_Plug_",
            "REFERENCE_ONLY_Fan_Case_Enduro_Battery_",
            "REFERENCE_ONLY_Fan_Case_Battery_Door_",
        ),
    )
    original_lens = camera.data.lens
    camera.data.lens = 55.0
    camera.location = (0.0, -285.0, 330.0)
    aim_object(camera, (0.0, -5.0, 38.0))
    bpy.context.scene.render.filepath = str(
        RENDER_DIRECTORY / "mission1_field_case_handed_fan_loadout.png"
    )
    bpy.ops.render.render(write_still=True)
    camera.data.lens = original_lens


def render_bottom_cable_routes(camera):
    """Show both alternative bottom exits per fan with assemblies removed.

    Four highlighted leads illustrate alternatives, not four installed cables.
    The cradle and accessories stay in their real installed positions.
    """
    set_visible(("fan_case_pair_insert",), (
        "REFERENCE_ONLY_Fan_Case_Cable_Coil_", "REFERENCE_ONLY_Fan_Case_PWM_Plug_",
        "REFERENCE_ONLY_Fan_Case_Enduro_Battery_", "REFERENCE_ONLY_Fan_Case_Battery_Door_"))
    materials = (
        make_principled_material("Preview_Bottom_Left_Cable", (0.02, 0.6, 0.95)),
        make_principled_material("Preview_Bottom_Right_Cable", (0.5, 0.95, 0.12)),
    )
    temporary = []
    original_lens = camera.data.lens
    try:
        for index, routes in enumerate(field_case.FAN_CASE_PAIR_STORAGE["cable_route_options"], 1):
            for side_index, route in enumerate(routes):
                lead = field_case.add_round_polyline(
                    f"Preview_Bottom_Cable_Option_{index}_{side_index}",
                    route, field_case.FAN_CASE_CABLE_DIAMETER)
                temporary.append(lead)
                assign_material(lead, materials[side_index])
        camera.data.lens = 55.0
        camera.location = (0.0, -285.0, 330.0)
        aim_object(camera, (0.0, -5.0, 38.0))
        bpy.context.scene.render.filepath = str(
            RENDER_DIRECTORY / "mission1_field_case_bottom_cable_routes.png")
        bpy.ops.render.render(write_still=True)
    finally:
        camera.data.lens = original_lens
        for obj in temporary:
            bpy.data.objects.remove(obj, do_unlink=True)


def render_fan_side_storage(camera):
    """Lift the deep tray to expose its battery-side storage and shallow tray."""
    set_visible(
        (
            "base",
            "fan_case_pair_insert",
            "fan_case_pair_carrier",
            "fan_case_pair_storage_bin",
        ),
        (
            "REFERENCE_ONLY_Fan_Case_Assembly_",
            "REFERENCE_ONLY_Fan_Case_Cable_Lead_",
            "REFERENCE_ONLY_Fan_Case_Cable_Coil_",
            "REFERENCE_ONLY_Fan_Case_PWM_Plug_",
            "REFERENCE_ONLY_Fan_Case_Enduro_Battery_",
            "REFERENCE_ONLY_Fan_Case_Battery_Door_",
        ),
    )
    storage_bin = PARTS["fan_case_pair_storage_bin"]
    storage_bin.location.z += 72.0
    camera.location = (390.0, -510.0, 480.0)
    aim_object(camera, (0.0, -12.0, 83.0))
    bpy.context.scene.render.filepath = str(
        RENDER_DIRECTORY / "mission1_field_case_fan_side_storage.png"
    )
    bpy.ops.render.render(write_still=True)
    storage_bin.location.z -= 72.0


def render_fan_side_support_path(camera):
    """Show the thick wall-backed cradle and both useful level-bottom trays."""
    keys = ("fan_case_pair_insert", "fan_case_pair_carrier", "fan_case_pair_storage_bin")
    set_visible(keys)
    original_locations = {key: PARTS[key].location.copy() for key in keys}
    PARTS["fan_case_pair_insert"].location.x -= 128.0
    PARTS["fan_case_pair_carrier"].location = (
        128.0, 20.0, -field_case.FAN_CASE_PAIR_OVERHEAD_STORAGE["carrier_bounds"][4])
    PARTS["fan_case_pair_storage_bin"].location = (
        128.0, -25.0, -field_case.FAN_CASE_PAIR_OVERHEAD_STORAGE["bin_bottom_z"])
    camera.data.lens = 52.0
    camera.location = (455.0, -650.0, 470.0)
    aim_object(camera, (0.0, -10.0, 35.0))
    bpy.context.scene.render.filepath = str(
        RENDER_DIRECTORY / "mission1_field_case_fan_side_support_path.png")
    bpy.ops.render.render(write_still=True)
    for key, location in original_locations.items():
        PARTS[key].location = location
    camera.data.lens = 58.0


def render_fan_side_closed_stack(camera):
    """Show the flat lid pad seated directly on the continuous bin rim."""
    set_visible(
        (
            "fan_case_pair_insert",
            "fan_case_pair_carrier",
            "fan_case_pair_storage_bin",
            "fan_case_pair_lid_pad",
        )
    )
    lid_pad = PARTS["fan_case_pair_lid_pad"]
    original_location = lid_pad.location.copy()
    original_rotation = lid_pad.rotation_euler.copy()
    lid_pad.location, lid_pad.rotation_euler = (
        field_case.installed_flat_lid_pad_pose(0.0)
    )

    camera.data.lens = 68.0
    camera.location = (360.0, -505.0, 155.0)
    aim_object(camera, (0.0, -34.0, 79.0))
    bpy.context.scene.render.filepath = str(
        RENDER_DIRECTORY / "mission1_field_case_fan_side_closed_stack.png"
    )
    bpy.ops.render.render(write_still=True)

    lid_pad.location = original_location
    lid_pad.rotation_euler = original_rotation
    camera.data.lens = 58.0


def render_fan_case_insert_detail(camera):
    """Expose both actual curved mold cavities and the accessory storage."""
    set_visible(
        ("fan_case_pair_insert",),
        (
            "REFERENCE_ONLY_Fan_Case_Cable_Coil_",
            "REFERENCE_ONLY_Fan_Case_Cable_Lead_",
            "REFERENCE_ONLY_Fan_Case_PWM_Plug_",
            "REFERENCE_ONLY_Fan_Case_Enduro_Battery_",
            "REFERENCE_ONLY_Fan_Case_Battery_Door_",
        ),
    )
    camera.data.lens = 55.0
    camera.location = (0.0, -285.0, 330.0)
    aim_object(camera, (0.0, -5.0, 38.0))
    bpy.context.scene.render.filepath = str(
        RENDER_DIRECTORY / "mission1_field_case_fan_case_insert_detail.png"
    )
    bpy.ops.render.render(write_still=True)
    camera.data.lens = 58.0


def render_fan_case_front_hardware(camera):
    """Show the three M3x40 shafts and low-profile thumb nuts per case."""
    set_visible((), ("REFERENCE_ONLY_Fan_Case_Assembly_",))
    camera.data.lens = 72.0
    camera.location = (235.0, 325.0, 180.0)
    aim_object(camera, (0.0, 20.0, 42.0))
    bpy.context.scene.render.filepath = str(
        RENDER_DIRECTORY / "mission1_field_case_fan_case_front_hardware.png"
    )
    bpy.ops.render.render(write_still=True)
    camera.data.lens = 58.0


def render_fan_case_loadout_exploded(camera):
    """Explode the lower insert, assemblies, carrier, bin, and flat lid pad."""
    set_visible(
        (
            "base",
            "fan_case_pair_insert",
            "fan_case_pair_carrier",
            "fan_case_pair_storage_bin",
            "fan_case_pair_lid_pad",
        ),
        (
            "REFERENCE_ONLY_Fan_Case_Assembly_",
            "REFERENCE_ONLY_Fan_Case_Cable_Coil_",
            "REFERENCE_ONLY_Fan_Case_PWM_Plug_",
            "REFERENCE_ONLY_Fan_Case_Enduro_Battery_",
            "REFERENCE_ONLY_Fan_Case_Battery_Door_",
        ),
    )
    insert_shift = 35.0
    assembly_shift = 76.0
    PARTS["fan_case_pair_insert"].location.z += insert_shift
    for prefix in (
        "REFERENCE_ONLY_Fan_Case_Cable_Coil_",
        "REFERENCE_ONLY_Fan_Case_Cable_Lead_",
        "REFERENCE_ONLY_Fan_Case_PWM_Plug_",
        "REFERENCE_ONLY_Fan_Case_Enduro_Battery_",
        "REFERENCE_ONLY_Fan_Case_Battery_Door_",
    ):
        for obj in reference_objects(prefix):
            obj.location.z += insert_shift
    for obj in reference_objects("REFERENCE_ONLY_Fan_Case_Assembly_"):
        obj.location.z += assembly_shift

    PARTS["fan_case_pair_carrier"].location.z += 102.0
    PARTS["fan_case_pair_storage_bin"].location.z += 152.0

    lid_pad = PARTS["fan_case_pair_lid_pad"]
    # The lid component is now a flat keyed closing pad; all short hold-down
    # features remain on the carrier inside the base.
    lid_pad.location = (0.0, 0.0, 300.0)
    lid_pad.rotation_euler = (0.0, 0.0, 0.0)

    camera.location = (570.0, -720.0, 520.0)
    aim_object(camera, (0.0, -1.0, 125.0))
    bpy.context.scene.render.filepath = str(
        RENDER_DIRECTORY / "mission1_field_case_fan_case_loadout_exploded.png"
    )
    bpy.ops.render.render(write_still=True)


def render_tpu_snap_hinge(camera):
    """Show the optional 68D lid snapped over an installed round rod."""
    set_visible(("base", "tpu_snap_lid"))
    lid_location, lid_rotation = field_case.installed_lid_pose(52.0)
    PARTS["tpu_snap_lid"].location = lid_location
    PARTS["tpu_snap_lid"].rotation_euler = lid_rotation

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64,
        radius=field_case.HINGE_ROD_DIAMETER / 2.0,
        depth=field_case.HINGE_ROD_X1 - field_case.HINGE_ROD_X0,
        location=(0.0, field_case.HINGE_AXIS_Y, field_case.BASE_HEIGHT),
        rotation=(0.0, math.pi / 2.0, 0.0),
    )
    rod = bpy.context.object
    rod.name = "PREVIEW_ONLY_Installed_4p1mm_Hinge_Rod"
    assign_material(
        rod,
        make_principled_material(
            "Preview_Hinge_Rod_Steel",
            (0.38, 0.43, 0.50),
            metallic=0.72,
            roughness=0.24,
        ),
    )

    camera.data.lens = 76.0
    camera.location = (205.0, 315.0, 190.0)
    aim_object(camera, (0.0, 79.0, 108.0))
    bpy.context.scene.render.filepath = str(
        RENDER_DIRECTORY / "mission1_field_case_tpu_snap_hinge.png"
    )
    bpy.ops.render.render(write_still=True)
    rod.hide_render = True
    camera.data.lens = 58.0


def render_tpu_hinge_coupon(camera):
    """Show four dot-coded 68D throat banks, including their shared roots."""
    set_visible(("tpu_hinge_coupon",))
    coupon = PARTS["tpu_hinge_coupon"]
    coupon.location = (0.0, 0.0, 0.0)
    # Turn the dot-coded grip edge toward the camera while retaining a clear
    # oblique view into all four receiver mouths.
    coupon.rotation_euler = (0.0, 0.0, math.pi)
    camera.data.lens = 55.0
    bpy.context.view_layer.update()
    framing_scale = max(coupon.dimensions.x / 59.0, 1.0)
    camera.location = Vector((115.0, -145.0, 100.0)) * framing_scale
    aim_object(camera, (0.0, 2.0, 7.0))
    bpy.context.scene.render.filepath = str(
        RENDER_DIRECTORY / "mission1_field_case_tpu_hinge_coupon.png"
    )
    bpy.ops.render.render(write_still=True)
    camera.data.lens = 58.0


def render_reinforced_hinge_sections(camera):
    """Show exact rigid/TPU jaw sections with their broad plate roots."""
    set_visible(())
    sections = []
    for key, profile, display_x in (
        ("lid", field_case.HINGE_PROFILE_RIGID_SLIDE, -13.0),
        ("tpu_snap_lid", field_case.HINGE_PROFILE_TPU_68D_SNAP, 13.0),
    ):
        x0, x1 = field_case.lid_hinge_segments(profile)[0]
        center_x = field_case.LID_DISPLAY_OFFSET_X + (x0 + x1) / 2.0
        source = PARTS[key]
        section = source.copy()
        section.data = source.data.copy()
        bpy.context.collection.objects.link(section)
        section.name = f"PREVIEW_ONLY_Reinforced_{key}_Section"
        clip = field_case.add_rounded_box(
            "PREVIEW_ONLY_Hinge_Section_Cutter",
            (2.0, 15.0, 20.0),
            (center_x, -field_case.HINGE_AXIS_Y + 2.5, 8.0),
            bevel=0.0,
        )
        field_case.boolean_apply(section, clip, "INTERSECT")
        positions = [section.matrix_world @ v.co for v in section.data.vertices]
        section.location = (0.0, 0.0, 0.0)
        section.rotation_euler = (0.0, 0.0, 0.0)
        section.scale = (1.0, 1.0, 1.0)
        for vertex, position in zip(section.data.vertices, positions):
            vertex.co = (
                display_x + position.y + field_case.HINGE_AXIS_Y,
                -(position.x - center_x),
                position.z,
            )
        field_case.recalc_normals(section)
        if key == "tpu_snap_lid":
            assign_material(section, PARTS["fan_case_pair_insert"].data.materials[0])
        section.hide_render = False
        sections.append(section)
    camera.data.lens = 58.0
    camera.location = (22.0, -105.0, 50.0)
    aim_object(camera, (1.5, 0.0, 7.0))
    bpy.context.scene.render.filepath = str(
        RENDER_DIRECTORY / "mission1_field_case_reinforced_hinge_sections.png"
    )
    bpy.ops.render.render(write_still=True)
    for section in sections:
        bpy.data.objects.remove(section, do_unlink=True)


field_case.BUILD_REFERENCE_MOCKUPS = True
field_case.EXPORT_STL = False
field_case.SAVE_BLEND = False
PARTS = field_case.build_mission1_field_case()
RENDER_DIRECTORY.mkdir(parents=True, exist_ok=True)
CAMERA = set_studio_scene()
hide_non_storage_objects()
set_reference_materials()
render_loaded_compact_stack(CAMERA)
render_exploded_stack(CAMERA)
render_closed_latch_protectors(CAMERA)
render_fan_case_loadout(CAMERA)
render_handed_fan_loadout(CAMERA)
render_bottom_cable_routes(CAMERA)
render_fan_side_storage(CAMERA)
render_fan_side_support_path(CAMERA)
render_fan_side_closed_stack(CAMERA)
render_fan_case_insert_detail(CAMERA)
render_fan_case_front_hardware(CAMERA)
render_fan_case_loadout_exploded(CAMERA)
render_reinforced_hinge_sections(CAMERA)
render_tpu_snap_hinge(CAMERA)
render_tpu_hinge_coupon(CAMERA)
print(f"FIELD_CASE_RENDERED_PREVIEWS {RENDER_DIRECTORY}")
