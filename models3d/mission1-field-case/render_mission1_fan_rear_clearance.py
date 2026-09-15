"""Render a clear top-view detail of the rear fan-depth relief.

Run from the repository root with::

    blender --background --factory-startup --threads 8 --python-exit-code 1 \
      --python models3d/mission1-field-case/render_mission1_fan_rear_clearance.py
"""

from pathlib import Path
import sys

import bpy
from mathutils import Vector
from PIL import Image, ImageDraw, ImageFont


DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DIRECTORY))

import mission1_field_case_blender as case
from render_mission1_latch_previews import aim


def clipped_fan_pocket(source, name, detail_center, panel_center):
    """Return one actual finished-mesh fan-pocket detail for comparison."""
    display = source.copy()
    display.data = source.data.copy()
    display.name = name
    bpy.context.collection.objects.link(display)
    clip = case.add_rounded_box(
        name + "_Clip",
        (66.0, 52.0, 90.0),
        (detail_center.x, detail_center.y, 42.0),
        bevel=0.0,
    )
    case.boolean_apply(display, clip, "INTERSECT")
    delta = panel_center - detail_center
    display.location += delta
    return display, delta


def transformed_preview_box(name, size, center, transform, placement, delta, color):
    """Create a thin plan-view overlay in the fan assembly's real pose."""
    obj = case.add_rounded_box(name, size, center, bevel=0.12)
    obj.matrix_world = transform @ obj.matrix_world
    obj.location += placement + delta
    obj.location.z = case.FAN_CASE_PAIR_CARRIER_SUPPORT["web_top_z"] + 3.0
    obj.color = color
    return obj


def add_slot_depth_overlay(panel_name, delta, band_color):
    """Outline the same rectangular slot and highlight its rear 1.5 mm."""
    transform = case.FAN_CASE_PAIR_STORAGE["fan_transforms"][0]
    placement = Vector(case.FAN_CASE_PAIR_STORAGE["placements"][0])
    cover_x0, cover_x1, cover_y0, cover_y1, _z0, _z1 = (
        case.FAN_CASE_PAIR_STORAGE["straight_cover_bounds"]
    )
    clearance = case.FAN_CASE_STORAGE_CLEARANCE + 0.01
    slot_x0 = cover_x0 - clearance
    slot_x1 = cover_x1 + clearance
    nominal_rear_y = cover_y0 - clearance
    front_y = cover_y1 + clearance
    revised_rear_y = nominal_rear_y - case.FAN_CASE_REAR_DEPTH_ALLOWANCE
    slot_width = slot_x1 - slot_x0
    revised_depth = front_y - revised_rear_y
    center_x = (slot_x0 + slot_x1) / 2.0
    center_y = (front_y + revised_rear_y) / 2.0
    outline_color = (0.08, 0.67, 0.95, 1.0)
    line_width = 0.65

    # Cyan is the complete rectangular inlet slot. The colored strip is only
    # the additional 1.5 mm at its back edge, shown at true scale and in the
    # actual -15 degree installed pose.
    for edge_name, size, center in (
        ("Front", (slot_width + line_width, line_width, 0.7),
         (center_x, front_y, 0.0)),
        ("Rear", (slot_width + line_width, line_width, 0.7),
         (center_x, revised_rear_y, 0.0)),
        ("Left", (line_width, revised_depth, 0.7),
         (slot_x0, center_y, 0.0)),
        ("Right", (line_width, revised_depth, 0.7),
         (slot_x1, center_y, 0.0)),
    ):
        transformed_preview_box(
            f"{panel_name}_Fan_Outline_{edge_name}",
            size,
            center,
            transform,
            placement,
            delta,
            outline_color,
        )

    transformed_preview_box(
        f"{panel_name}_Extra_1p5mm_Fan_Depth",
        (slot_width, case.FAN_CASE_REAR_DEPTH_ALLOWANCE, 0.8),
        (
            center_x,
            nominal_rear_y - case.FAN_CASE_REAR_DEPTH_ALLOWANCE / 2.0,
            0.0,
        ),
        transform,
        placement,
        delta,
        band_color,
    )


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
        bpy.data.objects.remove(obj, do_unlink=True)

    # Show only the affected pocket, not the visually dense complete insert.
    # Both panels are clipped from their respective completed lower inserts.
    detail_center = Vector((-58.0, -19.0, 0.0))
    before_panel, before_delta = clipped_fan_pocket(
        before, "Before_Finished_Pocket", detail_center, Vector((-46.0, 0.0, 0.0))
    )
    after_panel, after_delta = clipped_fan_pocket(
        after, "After_Finished_Pocket", detail_center, Vector((46.0, 0.0, 0.0))
    )
    before.hide_render = True
    after.hide_render = True
    before_panel.color = (0.38, 0.46, 0.56, 1.0)
    after_panel.color = (0.38, 0.46, 0.56, 1.0)
    add_slot_depth_overlay("Before", before_delta, (0.96, 0.12, 0.04, 1.0))
    add_slot_depth_overlay("After", after_delta, (0.10, 0.82, 0.28, 1.0))

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 700
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
    camera.data.ortho_scale = 180.0
    camera.data.clip_end = 2000.0
    camera.location = (0.0, 0.0, 500.0)
    aim(camera, (0.0, 0.0, 0.0))
    scene.camera = camera

    output = DIRECTORY / "renderings" / "mission1_fan_rear_clearance.png"
    raw_output = DIRECTORY / "renderings" / "mission1_fan_rear_clearance_raw.png"
    scene.render.filepath = str(raw_output)
    bpy.ops.render.render(write_still=True)
    if not raw_output.is_file() or raw_output.stat().st_size == 0:
        raise RuntimeError(f"Missing raw rear-clearance rendering: {raw_output}")

    # Keep explanatory text in deterministic pixel space. Blender's 3D text
    # is useful for perspective labels, but this straight top view needs a
    # clean diagram-like heading and legend that can never clip at the frame.
    geometry = Image.open(raw_output).convert("RGB")
    canvas = Image.new("RGB", (1800, 1100), (20, 28, 40))
    canvas.paste(geometry, (0, 180))
    draw = ImageDraw.Draw(canvas)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    bold_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    title_font = ImageFont.truetype(bold_path, 50)
    heading_font = ImageFont.truetype(bold_path, 32)
    body_font = ImageFont.truetype(font_path, 27)
    note_font = ImageFont.truetype(font_path, 24)
    white = (235, 241, 248)
    muted = (183, 196, 210)
    red = (245, 70, 38)
    green = (52, 220, 108)
    cyan = (45, 194, 237)

    def centered(text, center_x, y, font, fill=white):
        box = draw.textbbox((0, 0), text, font=font)
        draw.text((center_x - (box[2] - box[0]) / 2, y), text, font=font, fill=fill)

    centered("RECTANGULAR FAN-INLET SLOT: 1.5 mm LONGER AT BACK ONLY",
             900, 25, title_font)
    centered("Top view — slot width, side walls, and every other dimension stay fixed",
             900, 93, body_font, muted)
    centered("BEFORE — fan catches at rear edge", 450, 137, heading_font)
    centered("AFTER — 1.5 mm more rear space", 1350, 137, heading_font)

    draw.rounded_rectangle((85, 910, 125, 950), radius=5, fill=red)
    draw.text((145, 914), "RED: the extra 1.5 mm meets the old rear wall",
              font=body_font, fill=white)
    draw.rounded_rectangle((985, 910, 1025, 950), radius=5, fill=green)
    draw.text((1045, 914), "GREEN: the same 1.5 mm is now open slot",
              font=body_font, fill=white)
    draw.rounded_rectangle((85, 975, 125, 1015), radius=5, fill=cyan)
    draw.text((145, 979), "CYAN: unchanged rectangular slot sides",
              font=body_font, fill=white)
    draw.text((985, 979), "Only the lower TPU insert needs reprinting",
              font=body_font, fill=white)
    centered("Case envelope, fan angle/position, front edge, and all other insert dimensions unchanged",
             900, 1045, note_font, muted)

    canvas.save(output)
    raw_output.unlink()
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"Missing rear-clearance rendering: {output}")
    print(
        "MISSION1_FAN_REAR_CLEARANCE_RENDER_PASS "
        f"allowance={configured_allowance:.3f} output={output}",
        flush=True,
    )


if __name__ == "__main__":
    main()
