"""Render the current flat battery and hold-down bar inside the open case.

Run with Blender, for example from the repository root:
  blender --background --factory-startup --python-exit-code 1 \
    --python models3d/hockeymon-camera-case/render_flat_battery_review.py

The model is rebuilt and validated from its current source. This illustration
adds a nominal battery envelope and screw heads, and hides the removable lid
and fan. It does not modify the model source or any printable exports.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import bpy
from mathutils import Vector


HERE = Path(__file__).resolve().parent


def material(obj, name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=HERE / "docs/images/flat_battery_open_base.png")
    parser.add_argument("--save-scene", type=Path,
                        help="Optionally save the review scene for inspection.")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = parser.parse_args(argv)

    source = HERE / "hockeymom_cam_case_blender.py"
    model = {"__name__": "flat_battery_review", "__file__": str(source)}
    exec(compile(source.read_bytes(), str(source), "exec"), model)
    model["EXPORT_STL"] = False
    model["EXPORT_3MF"] = False
    model["RENDER_PREVIEW"] = False
    model["PREVIEW_SHOW_CAMERA_MOCKUPS"] = True
    base, lid = model["build_hockeymom_cam_case"]()
    layout = model["_RESOLVED_REAR_BATTERY_LAYOUT"]
    if layout is None:
        raise ValueError("The flat battery bay must be enabled for this view")
    bracket = bpy.data.objects["Hockeymom_Cam_Case_Battery_Bracket"]

    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        obj.hide_render = obj is lid or obj.name.startswith("Hockeymom_Cam_Case_Lid_Fan_")
        obj.hide_set(False)
        if obj.hide_render:
            continue
        if obj is base:
            material(obj, "Review_Case_Blue", (0.12, 0.32, 0.42))
        elif obj is bracket:
            material(obj, "Review_Retaining_Bar", (0.46, 0.52, 0.57))
        elif obj.name.startswith("Camera_") and "Mockup" in obj.name:
            material(obj, "Review_Camera", (0.18, 0.20, 0.22))
        else:
            material(obj, "Review_Interior_Parts", (0.29, 0.40, 0.47))

    bounds = layout["pack_bounds"]
    pack = model["add_beveled_box"](
        "Review_Battery_Envelope_Not_For_Print",
        tuple(high - low for low, high in bounds),
        tuple((low + high) / 2 for low, high in bounds),
        bevel=0.8,
    )
    material(pack, "Review_Battery_Gold", (0.95, 0.58, 0.16))
    record = model["rear_battery_bracket_layout"](layout)
    for index, (x, y) in enumerate(record["centers"], start=1):
        screw = model["add_cylinder_z"](
            f"Review_Battery_M3_Head_{index}_Not_For_Print",
            model["M3_SOCKET_HEAD_NOMINAL_DIAMETER"] / 2,
            record["bounds"][2][1],
            record["bounds"][2][1] + model["M3_SOCKET_HEAD_NOMINAL_HEIGHT"],
            x, y,
        )
        material(screw, "Review_Screw_Steel", (0.72, 0.75, 0.79))

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.studio_light = "paint.sl"
    shading.color_type = "MATERIAL"
    shading.show_shadows = True
    shading.show_cavity = True
    shading.cavity_type = "BOTH"
    shading.show_object_outline = True
    shading.background_type = "WORLD"
    scene.world.color = (0.86, 0.89, 0.92)
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1300
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.name = "Flat_Battery_Review_Camera"
    camera.data.type = "ORTHO"
    target = Vector((-3.0, 0.0, 30.0))
    camera.location = target + Vector((210.0, -260.0, 660.0))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    bpy.context.view_layer.update()
    rotation = camera.rotation_euler.to_quaternion()
    right = rotation @ Vector((1.0, 0.0, 0.0))
    up = rotation @ Vector((0.0, 1.0, 0.0))
    points = [obj.matrix_world @ vertex.co
              for obj in scene.objects if obj.type == "MESH" and not obj.hide_render
              for vertex in obj.data.vertices]
    low_x, high_x = min(p.dot(right) for p in points), max(p.dot(right) for p in points)
    low_y, high_y = min(p.dot(up) for p in points), max(p.dot(up) for p in points)
    camera.location += (right * ((low_x + high_x) / 2 - target.dot(right))
                        + up * ((low_y + high_y) / 2 - target.dot(up)))
    aspect = scene.render.resolution_x / scene.render.resolution_y
    camera.data.ortho_scale = 1.12 * max(high_x - low_x, (high_y - low_y) * aspect)

    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(output)
    if args.save_scene:
        snapshot = args.save_scene.expanduser().resolve()
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(snapshot))
    bpy.ops.render.render(write_still=True)
    print(f"FLAT_BATTERY_REVIEW_RENDER {output} pack_bounds={bounds}")


if __name__ == "__main__":
    main()
