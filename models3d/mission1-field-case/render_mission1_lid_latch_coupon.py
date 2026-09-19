"""Render the exact-crop TPU lid latch coupon in print and hook-fit poses."""

import argparse
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DIRECTORY))
import mission1_field_case_blender as case
import build_hardcase as reference


def configure(review_round):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studiolight_rotate_z = math.radians(25.0)
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.show_object_outline = True
    scene.display.shading.background_type = "WORLD"
    scene.world.color = (0.055, 0.065, 0.08)
    scene.view_settings.view_transform = "Standard"
    scene.display.render_aa = "32"
    scene.render.use_stamp = True
    for field in (
        "date",
        "time",
        "render_time",
        "frame",
        "frame_range",
        "memory",
        "hostname",
        "camera",
        "lens",
        "scene",
        "marker",
        "filename",
    ):
        setattr(scene.render, "use_stamp_" + field, False)
    scene.render.use_stamp_note = True
    scene.render.stamp_note_text = (
        "Initial proposal - before reviews"
        if review_round == 0
        else f"After review round {review_round}"
    )
    scene.render.stamp_font_size = 20
    camera = bpy.data.objects.new(
        "Latch_Coupon_Review_Camera",
        bpy.data.cameras.new("Latch_Coupon_Review_Camera"),
    )
    bpy.context.collection.objects.link(camera)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 165.0
    camera.data.clip_end = 2000.0
    camera.location = (165.0, -205.0, 150.0)
    camera.rotation_euler = (
        Vector((0.0, 0.0, 17.0)) - camera.location
    ).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-round", type=int, default=0)
    args = parser.parse_args(
        sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    )
    case.clear_scene()
    case.set_units()
    configure(args.review_round)

    tpu = case.make_material("Coupon_TPU_For_AMS", (0.18, 0.48, 0.72))
    orange = case.make_material("Coupon_Orange", (0.95, 0.28, 0.04))
    hardware = case.make_material("Coupon_Hook", (0.95, 0.48, 0.08))
    lid, inlay = case.create_lid(
        tpu,
        orange,
        hinge_profile=case.HINGE_PROFILE_TPU_68D_SNAP,
    )
    print_coupon = case.create_tpu_lid_latch_coupon(lid)
    fitted_coupon = print_coupon.copy()
    fitted_coupon.data = print_coupon.data.copy()
    fitted_coupon.name = "Fitted_TPU_Lid_Latch_Station_Coupon"
    bpy.context.collection.objects.link(fitted_coupon)

    lever, hook = case.create_pelican_latch_parts(hardware)
    bpy.data.objects.remove(lever, do_unlink=True)
    case.position_installed_latch_hook(hook, case.LATCH_X_CENTERS[0])
    lid.location, lid.rotation_euler = case.installed_lid_pose(0.0)
    bpy.context.view_layer.update()
    hook_in_lid_local = lid.matrix_world.inverted() @ hook.matrix_world

    minimum, maximum = case.object_world_bounds(print_coupon)
    center = (minimum + maximum) / 2.0
    print_offset = Vector((-43.0 - center.x, -center.y, 0.0))
    fit_offset = Vector((43.0 - center.x, -center.y, 0.0))
    original_coupon_matrix = print_coupon.matrix_world.copy()
    print_coupon.matrix_world = Matrix.Translation(print_offset) @ original_coupon_matrix
    fitted_coupon.matrix_world = Matrix.Translation(fit_offset) @ original_coupon_matrix
    hook.matrix_world = fitted_coupon.matrix_world @ hook_in_lid_local

    for obj in (print_coupon, fitted_coupon):
        obj.color = (0.18, 0.48, 0.72, 1.0)
        reference.shade_auto_smooth(obj)
    hook.color = (0.95, 0.48, 0.08, 1.0)
    reference.shade_auto_smooth(hook)
    lid.hide_render = True
    inlay.hide_render = True

    bpy.context.scene.render.filepath = str(
        DIRECTORY / "renderings" / "mission1_tpu_lid_latch_coupon.png"
    )
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
