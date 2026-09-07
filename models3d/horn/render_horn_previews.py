"""Render the default and a mixed-size standard-fan horn.

Run from the repository root with::

    blender --background --factory-startup \
      --python models3d/horn/render_horn_previews.py

The images are written to ``models3d/horn/renderings/`` for design review.
"""

from __future__ import annotations

from pathlib import Path

import bpy
from mathutils import Vector


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
HORN_SOURCE = SCRIPT_DIRECTORY / "horn_parametric_blender.py"
RENDER_DIRECTORY = SCRIPT_DIRECTORY / "renderings"
RENDER_RESOLUTION = (1400, 1000)


def load_horn_generator():
    namespace = {
        "__name__": "horn_preview_generator",
        "__file__": str(HORN_SOURCE),
    }
    source = HORN_SOURCE.read_bytes()
    exec(compile(source, str(HORN_SOURCE), "exec"), namespace)
    return namespace


def aim_at(obj, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def object_bounds(obj) -> tuple[Vector, Vector]:
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return (
        Vector(tuple(min(corner[axis] for corner in corners) for axis in range(3))),
        Vector(tuple(max(corner[axis] for corner in corners) for axis in range(3))),
    )


def configure_scene(obj, view_direction: tuple[float, float, float]):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x, scene.render.resolution_y = RENDER_RESOLUTION
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 20
    scene.render.film_transparent = False
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.curvature_ridge_factor = 1.4
    scene.display.shading.curvature_valley_factor = 1.1
    scene.display.shading.background_type = "VIEWPORT"
    scene.display.shading.background_color = (0.025, 0.035, 0.055)

    material = bpy.data.materials.get("Horn_Review_Blue")
    if material is None:
        material = bpy.data.materials.new("Horn_Review_Blue")
    material.diffuse_color = (0.055, 0.42, 0.72, 1.0)
    obj.data.materials.clear()
    obj.data.materials.append(material)

    bounds_min, bounds_max = object_bounds(obj)
    center = (bounds_min + bounds_max) / 2.0
    diagonal = (bounds_max - bounds_min).length
    direction = Vector(view_direction).normalized()

    camera_data = bpy.data.cameras.new("Review_Camera")
    camera = bpy.data.objects.new("Review_Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = diagonal * 1.35
    camera.data.lens = 55.0
    camera.location = center + direction * max(4.0 * diagonal, 1.0)
    aim_at(camera, center)
    scene.camera = camera
    return scene


def render_configuration(
    horn,
    inlet_size: int,
    outlet_size: int,
    filename: str,
    view_direction: tuple[float, float, float],
) -> None:
    horn["INLET_FAN_SIZE_MM"] = inlet_size
    horn["OUTLET_FAN_SIZE_MM"] = outlet_size
    obj = horn["build_horn"]()
    scene = configure_scene(obj, view_direction)
    scene.render.filepath = str(RENDER_DIRECTORY / filename)
    bpy.ops.render.render(write_still=True)
    print(
        f"Rendered {inlet_size} -> {outlet_size} mm standard-fan horn: "
        f"{scene.render.filepath}"
    )


def main() -> None:
    RENDER_DIRECTORY.mkdir(parents=True, exist_ok=True)
    horn = load_horn_generator()
    render_configuration(
        horn,
        40,
        40,
        "horn_standard_40_to_40.png",
        (-1.65, -2.15, 1.30),
    )
    render_configuration(
        horn,
        40,
        80,
        "horn_standard_40_to_80.png",
        (1.70, -2.20, 1.35),
    )


if __name__ == "__main__":
    main()
