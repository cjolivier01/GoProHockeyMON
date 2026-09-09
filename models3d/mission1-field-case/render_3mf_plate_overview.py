"""Render the generated field-case 3MF as a labeled print-plate overview.

This script does not import or run the field-case geometry generator.  It reads
the actual meshes, component relationships, build transforms, plate membership,
plate names, and material assignments from the packaged 3MF.

Run from any directory with::

    blender --background --factory-startup --python \
      mission1-field-case/render_3mf_plate_overview.py

Use arguments after ``--`` to override the defaults::

    --input path/to/project.3mf --output path/to/overview.png
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import math
from pathlib import Path, PurePosixPath
import sys
import textwrap
import zipfile
from xml.etree import ElementTree as ET

import bpy
from mathutils import Matrix, Vector


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIRECTORY / "mission1_field_case_ams_project.3mf"
DEFAULT_OUTPUT = (
    SCRIPT_DIRECTORY
    / "renderings"
    / "mission1_field_case_all_print_plates.png"
)
CORE_NAMESPACE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PRODUCTION_NAMESPACE = (
    "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
)
PLATE_SIZE = 250.0
PLATE_STRIDE = 300.0
BED_EXCLUDE_SIZE = (18.0, 28.0)


def core_tag(name: str) -> str:
    return f"{{{CORE_NAMESPACE}}}{name}"


def production_attribute(name: str) -> str:
    return f"{{{PRODUCTION_NAMESPACE}}}{name}"


def config_metadata(node) -> dict[str, str]:
    values = {}
    for metadata in node.findall("metadata"):
        key = metadata.get("key")
        value = metadata.get("value")
        if key is None and value is None and set(metadata.attrib) == {"face_count"}:
            # Bambu's model settings store this statistic as a direct
            # attribute rather than a key/value metadata entry.
            continue
        if key is None or value is None:
            raise ValueError("3MF config metadata must have key and value")
        if key in values:
            raise ValueError(f"Duplicate 3MF config metadata key: {key}")
        values[key] = value
    return values


def normalize_member_path(raw_path: str) -> str:
    path = PurePosixPath(raw_path.lstrip("/"))
    if ".." in path.parts:
        raise ValueError(f"Unsafe 3MF package path: {raw_path}")
    return str(path)


def transform_matrix(raw_value: str | None) -> Matrix:
    if raw_value is None:
        return Matrix.Identity(4)
    values = tuple(float(value) for value in raw_value.split())
    if len(values) != 12 or not all(math.isfinite(value) for value in values):
        raise ValueError(f"Invalid 3MF transform: {raw_value}")
    # 3MF stores a row-vector affine transform as
    # M00 M01 M02 M10 ... M22 M30 M31 M32.  Transpose its 3x3 portion into
    # Blender's column-vector matrix and place translation in the last column.
    return Matrix(
        (
            (values[0], values[3], values[6], values[9]),
            (values[1], values[4], values[7], values[10]),
            (values[2], values[5], values[8], values[11]),
            (0.0, 0.0, 0.0, 1.0),
        )
    )


@dataclass(frozen=True)
class MeshSource:
    model_path: str
    object_id: str
    name: str
    vertices: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]


@dataclass(frozen=True)
class ResolvedMesh:
    source: MeshSource
    component_transform: Matrix


@dataclass(frozen=True)
class BuildInstance:
    object_id: str
    instance_id: str
    plate_index: int
    build_transform: Matrix
    meshes: tuple[ResolvedMesh, ...]


@dataclass(frozen=True)
class Plate:
    name: str
    instance_keys: tuple[tuple[str, str], ...]


class ThreeMFProject:
    def __init__(self, path: Path):
        self.path = path
        self.models: dict[str, ET.Element] = {}
        self.mesh_cache: dict[tuple[str, str], MeshSource] = {}
        self.part_extruders: dict[str, int] = {}
        self.object_names: dict[str, str] = {}
        self.plates: tuple[Plate, ...] = ()
        self.instances: tuple[BuildInstance, ...] = ()
        self._read()

    def _read(self) -> None:
        if not self.path.is_file():
            raise FileNotFoundError(f"Generated 3MF not found: {self.path}")
        with zipfile.ZipFile(self.path, "r") as archive:
            bad_member = archive.testzip()
            if bad_member is not None:
                raise ValueError(f"Corrupt 3MF ZIP member: {bad_member}")
            root_path = "3D/3dmodel.model"
            settings_path = "Metadata/model_settings.config"
            members = set(archive.namelist())
            missing = {root_path, settings_path}.difference(members)
            if missing:
                raise ValueError(
                    f"3MF is missing required members: {sorted(missing)}"
                )
            for member in members:
                if member.endswith(".model"):
                    self.models[member] = ET.fromstring(archive.read(member))
            settings = ET.fromstring(archive.read(settings_path))

        for model_path, model in self.models.items():
            if model.get("unit", "millimeter") != "millimeter":
                raise ValueError(
                    f"Only millimeter 3MF models are supported: {model_path}"
                )

        for settings_object in settings.findall("object"):
            object_id = settings_object.get("id")
            if object_id is None:
                raise ValueError("3MF settings object has no ID")
            metadata = config_metadata(settings_object)
            self.object_names[object_id] = metadata.get(
                "name", f"Object {object_id}"
            )
            for part in settings_object.findall("part"):
                part_id = part.get("id")
                part_metadata = config_metadata(part)
                if part_id is None or "extruder" not in part_metadata:
                    raise ValueError("3MF settings part lacks ID or extruder")
                extruder = int(part_metadata["extruder"])
                if part_id in self.part_extruders:
                    raise ValueError(f"Duplicate 3MF mesh-part ID: {part_id}")
                self.part_extruders[part_id] = extruder

        plates = []
        instance_to_plate = {}
        for plate_index, plate_node in enumerate(settings.findall("plate")):
            metadata = config_metadata(plate_node)
            plate_name = metadata.get("plater_name", f"Plate {plate_index + 1}")
            keys = []
            for instance_node in plate_node.findall("model_instance"):
                instance_metadata = config_metadata(instance_node)
                key = (
                    instance_metadata.get("object_id"),
                    instance_metadata.get("instance_id"),
                )
                if None in key:
                    raise ValueError("3MF plate instance lacks object or instance ID")
                if key in instance_to_plate:
                    raise ValueError(f"3MF instance appears on two plates: {key}")
                instance_to_plate[key] = plate_index
                keys.append(key)
            plates.append(Plate(plate_name, tuple(keys)))
        if not plates:
            raise ValueError("3MF project has no labeled plates")
        self.plates = tuple(plates)

        root_model = self.models[root_path]
        occurrences: Counter[str] = Counter()
        build_instances = []
        build = root_model.find(core_tag("build"))
        if build is None:
            raise ValueError("3MF root model has no build section")
        for item in build.findall(core_tag("item")):
            object_id = item.get("objectid")
            if object_id is None:
                raise ValueError("3MF build item has no object ID")
            instance_id = str(occurrences[object_id])
            occurrences[object_id] += 1
            key = (object_id, instance_id)
            if key not in instance_to_plate:
                raise ValueError(f"3MF build item is not assigned to a plate: {key}")
            meshes = tuple(self._resolve_object(root_path, object_id, ()))
            if not meshes:
                raise ValueError(f"3MF build object {object_id} contains no meshes")
            build_instances.append(
                BuildInstance(
                    object_id=object_id,
                    instance_id=instance_id,
                    plate_index=instance_to_plate[key],
                    build_transform=transform_matrix(item.get("transform")),
                    meshes=meshes,
                )
            )
        if set(instance_to_plate) != {
            (instance.object_id, instance.instance_id)
            for instance in build_instances
        }:
            raise ValueError("3MF plate membership and build instances differ")
        self.instances = tuple(build_instances)

    def _model_objects(self, model_path: str) -> dict[str, ET.Element]:
        model = self.models.get(model_path)
        if model is None:
            raise ValueError(f"3MF component references missing model: {model_path}")
        resources = model.find(core_tag("resources"))
        if resources is None:
            raise ValueError(f"3MF model has no resources: {model_path}")
        objects = {
            node.get("id"): node for node in resources.findall(core_tag("object"))
        }
        if None in objects:
            raise ValueError(f"3MF model contains an object without ID: {model_path}")
        return objects

    def _mesh_source(self, model_path: str, object_node) -> MeshSource:
        object_id = object_node.get("id")
        key = (model_path, object_id)
        cached = self.mesh_cache.get(key)
        if cached is not None:
            return cached
        mesh = object_node.find(core_tag("mesh"))
        if mesh is None:
            raise ValueError(f"3MF object {key} has no mesh")
        vertices_node = mesh.find(core_tag("vertices"))
        triangles_node = mesh.find(core_tag("triangles"))
        if vertices_node is None or triangles_node is None:
            raise ValueError(f"3MF mesh {key} lacks vertices or triangles")
        vertices = tuple(
            tuple(float(vertex.get(axis)) for axis in ("x", "y", "z"))
            for vertex in vertices_node.findall(core_tag("vertex"))
        )
        triangles = tuple(
            tuple(int(triangle.get(axis)) for axis in ("v1", "v2", "v3"))
            for triangle in triangles_node.findall(core_tag("triangle"))
        )
        if not vertices or not triangles:
            raise ValueError(f"3MF mesh {key} is empty")
        if any(
            index < 0 or index >= len(vertices)
            for triangle in triangles
            for index in triangle
        ):
            raise ValueError(f"3MF mesh {key} has an invalid triangle index")
        source = MeshSource(
            model_path=model_path,
            object_id=object_id,
            name=object_node.get("name", f"Mesh {object_id}"),
            vertices=vertices,
            triangles=triangles,
        )
        self.mesh_cache[key] = source
        return source

    def _resolve_object(
        self,
        model_path: str,
        object_id: str,
        stack: tuple[tuple[str, str], ...],
    ):
        key = (model_path, object_id)
        if key in stack:
            raise ValueError(f"Cyclic 3MF component reference: {key}")
        objects = self._model_objects(model_path)
        object_node = objects.get(object_id)
        if object_node is None:
            raise ValueError(f"3MF references missing object: {key}")
        if object_node.find(core_tag("mesh")) is not None:
            yield ResolvedMesh(self._mesh_source(model_path, object_node), Matrix.Identity(4))
            return
        components = object_node.find(core_tag("components"))
        if components is None:
            raise ValueError(f"3MF object has neither mesh nor components: {key}")
        for component in components.findall(core_tag("component")):
            child_id = component.get("objectid")
            if child_id is None:
                raise ValueError(f"3MF component has no object ID: {key}")
            child_path = component.get(production_attribute("path"))
            child_model_path = (
                normalize_member_path(child_path) if child_path else model_path
            )
            component_matrix = transform_matrix(component.get("transform"))
            for resolved in self._resolve_object(
                child_model_path, child_id, stack + (key,)
            ):
                yield ResolvedMesh(
                    resolved.source,
                    component_matrix @ resolved.component_transform,
                )


def make_material(name: str, color: tuple[float, float, float, float]):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.diffuse_color = color
    return material


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials):
        for datablock in tuple(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def add_box(
    name: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    material,
):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    return obj


def add_text(
    name: str,
    body: str,
    location: tuple[float, float, float],
    size: float,
    material,
    *,
    align: str = "CENTER",
):
    curve = bpy.data.curves.new(name, type="FONT")
    curve.body = body
    curve.align_x = align
    curve.align_y = "CENTER"
    curve.size = size
    curve.space_line = 0.88
    curve.extrude = 0.035
    curve.materials.append(material)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    return obj


def concise_object_name(name: str) -> str:
    replacements = {
        "Pelican Latch Lever - Print Two": "latch lever",
        "Pelican Latch Hook - Print Two": "latch hook",
        "Pivoting Handle Bar": "handle",
        "Hinge Pin": "hinge pin",
        "Base Shell": "base shell",
        "TPU 68D Hinge Calibration Coupon": "hinge coupon",
    }
    if name in replacements:
        return replacements[name]
    for prefix in (
        "Rigid AMS ",
        "Optional 68D TPU ",
        "Default TPU ",
        "Alternate TPU ",
    ):
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break
    return name.lower()


def copy_summary(project: ThreeMFProject, plate_index: int) -> str:
    instances = [
        instance
        for instance in project.instances
        if instance.plate_index == plate_index
    ]
    counts = Counter(
        concise_object_name(project.object_names.get(instance.object_id, instance.object_id))
        for instance in instances
    )
    summary = "Copies: " + "  •  ".join(
        f"{count}× {name}" for name, count in counts.items()
    )
    return "\n".join(
        textwrap.wrap(
            summary,
            width=64,
            break_long_words=False,
            break_on_hyphens=False,
        )
    )


def create_project_meshes(project: ThreeMFProject, materials: dict[int, object]):
    mesh_data_cache = {}
    objects_by_plate = [[] for _plate in project.plates]
    for instance_index, instance in enumerate(project.instances, start=1):
        for component_index, resolved in enumerate(instance.meshes, start=1):
            source = resolved.source
            source_key = (source.model_path, source.object_id)
            mesh_data = mesh_data_cache.get(source_key)
            if mesh_data is None:
                mesh_data = bpy.data.meshes.new(f"3MF_Mesh_{source.object_id}")
                mesh_data.from_pydata(source.vertices, [], source.triangles)
                mesh_data.update(calc_edges=True)
                mesh_data_cache[source_key] = mesh_data
            obj = bpy.data.objects.new(
                f"Plate_{instance.plate_index + 1:02d}_Item_{instance_index:02d}_"
                f"Part_{component_index:02d}_{source.name}",
                mesh_data,
            )
            bpy.context.collection.objects.link(obj)
            obj.matrix_world = instance.build_transform @ resolved.component_transform
            extruder = project.part_extruders.get(source.object_id)
            if extruder is None:
                raise ValueError(
                    f"3MF mesh {source.object_id} has no material assignment"
                )
            obj.data.materials.clear()
            obj.data.materials.append(materials.get(extruder, materials[0]))
            objects_by_plate[instance.plate_index].append(obj)
    bpy.context.view_layer.update()
    return objects_by_plate


def object_bounds(objects) -> tuple[Vector, Vector]:
    corners = [
        obj.matrix_world @ Vector(corner)
        for obj in objects
        for corner in obj.bound_box
    ]
    if not corners:
        raise ValueError("Cannot calculate bounds for an empty object collection")
    return (
        Vector(tuple(min(corner[axis] for corner in corners) for axis in range(3))),
        Vector(tuple(max(corner[axis] for corner in corners) for axis in range(3))),
    )


def validate_plate_bounds(project: ThreeMFProject, objects_by_plate) -> None:
    columns = math.ceil(math.sqrt(len(project.plates)))
    for plate_index, objects in enumerate(objects_by_plate):
        minimum, maximum = object_bounds(objects)
        origin_x = (plate_index % columns) * PLATE_STRIDE
        origin_y = -(plate_index // columns) * PLATE_STRIDE
        if not (
            origin_x - 1e-4 <= minimum.x
            and maximum.x <= origin_x + PLATE_SIZE + 1e-4
            and origin_y - 1e-4 <= minimum.y
            and maximum.y <= origin_y + PLATE_SIZE + 1e-4
            and minimum.z >= -1e-4
            and maximum.z <= 250.0 + 1e-4
        ):
            raise ValueError(
                f"Plate {plate_index + 1} geometry lies outside its 250 mm "
                f"print volume: min={tuple(round(value, 3) for value in minimum)} "
                f"max={tuple(round(value, 3) for value in maximum)}"
            )


def configure_scene(project: ThreeMFProject, width: int):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 18
    scene.render.film_transparent = False
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.curvature_ridge_factor = 1.55
    scene.display.shading.curvature_valley_factor = 1.25
    scene.display.shading.background_type = "VIEWPORT"
    scene.display.shading.background_color = (0.018, 0.026, 0.043)
    scene.display.shading.show_specular_highlight = True
    scene.view_settings.look = "AgX - Medium High Contrast"

    columns = math.ceil(math.sqrt(len(project.plates)))
    rows = math.ceil(len(project.plates) / columns)
    left = -28.0
    right = (columns - 1) * PLATE_STRIDE + PLATE_SIZE + 28.0
    bottom = -(rows - 1) * PLATE_STRIDE - 52.0
    top = 350.0
    world_width = right - left
    world_height = top - bottom
    height = max(900, round(width * world_height / world_width))
    scene.render.resolution_x = width
    scene.render.resolution_y = height

    camera_data = bpy.data.cameras.new("Plate_Overview_Camera")
    camera = bpy.data.objects.new("Plate_Overview_Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = world_height
    camera_data.clip_start = 1.0
    camera_data.clip_end = 5000.0
    camera.location = ((left + right) / 2.0, (bottom + top) / 2.0, 2400.0)
    camera.rotation_euler = (0.0, 0.0, 0.0)
    scene.camera = camera
    return scene, columns, rows


def render_overview(project: ThreeMFProject, output_path: Path, width: int) -> None:
    clear_scene()
    materials = {
        0: make_material("Unassigned_3MF_Part", (0.72, 0.75, 0.80, 1.0)),
        1: make_material("Rigid_Black", (0.055, 0.075, 0.105, 1.0)),
        2: make_material("Rigid_Orange_Inlay", (1.0, 0.20, 0.025, 1.0)),
        3: make_material("TPU_68D", (0.94, 0.30, 0.045, 1.0)),
    }
    plate_material = make_material("250mm_Print_Plate", (0.18, 0.22, 0.29, 1.0))
    excluded_material = make_material("Excluded_Bed_Corner", (0.30, 0.11, 0.11, 1.0))
    label_material = make_material("Plate_Label", (0.88, 0.92, 0.98, 1.0))
    note_material = make_material("Choice_Note", (1.0, 0.55, 0.12, 1.0))
    objects_by_plate = create_project_meshes(project, materials)
    validate_plate_bounds(project, objects_by_plate)

    scene, columns, rows = configure_scene(project, width)
    for plate_index, plate in enumerate(project.plates):
        origin_x = (plate_index % columns) * PLATE_STRIDE
        origin_y = -(plate_index // columns) * PLATE_STRIDE
        add_box(
            f"Plate_{plate_index + 1:02d}_250mm",
            (origin_x + PLATE_SIZE / 2.0, origin_y + PLATE_SIZE / 2.0, -2.0),
            (PLATE_SIZE, PLATE_SIZE, 2.0),
            plate_material,
        )
        add_box(
            f"Plate_{plate_index + 1:02d}_Excluded_Corner",
            (
                origin_x + BED_EXCLUDE_SIZE[0] / 2.0,
                origin_y + BED_EXCLUDE_SIZE[1] / 2.0,
                -0.85,
            ),
            (BED_EXCLUDE_SIZE[0], BED_EXCLUDE_SIZE[1], 0.3),
            excluded_material,
        )
        header = plate.name
        if not header.lower().startswith(f"{plate_index + 1:02d}"):
            header = f"{plate_index + 1:02d} — {header}"
        add_text(
            f"Plate_{plate_index + 1:02d}_Name",
            header,
            (origin_x + PLATE_SIZE / 2.0, origin_y + 282.0, 1.0),
            6.3,
            label_material,
        )
        add_text(
            f"Plate_{plate_index + 1:02d}_Copies",
            copy_summary(project, plate_index),
            (origin_x + PLATE_SIZE / 2.0, origin_y + 263.0, 1.0),
            4.2,
            label_material,
        )

    full_width_center = ((columns - 1) * PLATE_STRIDE + PLATE_SIZE) / 2.0
    add_text(
        "Overview_Title",
        f"FIELD CASE — ALL {len(project.plates)} LABELED 250 × 250 mm PRINT PLATES",
        (full_width_center, 334.0, 1.0),
        10.0,
        label_material,
    )
    add_text(
        "Alternative_Notice",
        "CHOOSE ONE LID: 02 OR 03  •  DEFAULT AND FAN-CASE LOADOUT PLATES ARE ALTERNATIVES, NOT ONE ASSEMBLY",
        (full_width_center, 313.0, 1.0),
        6.0,
        note_material,
    )
    bottom_y = -(rows - 1) * PLATE_STRIDE - 30.0
    add_text(
        "Material_Legend",
        "DARK = RIGID  •  ORANGE = RIGID INLAY  •  CORAL = 68D TPU  •  RED CORNER = PRINTER EXCLUSION",
        (full_width_center, bottom_y, 1.0),
        5.0,
        label_material,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)
    print(
        "FIELD_CASE_3MF_PLATE_OVERVIEW "
        f"input={project.path} output={output_path} "
        f"plates={len(project.plates)} build_instances={len(project.instances)}"
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--width",
        type=int,
        default=2400,
        help="Output width in pixels; height follows the plate-grid aspect ratio.",
    )
    blender_arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    arguments = parser.parse_args(blender_arguments)
    if arguments.width < 800:
        parser.error("--width must be at least 800 pixels")
    arguments.input = arguments.input.expanduser().resolve()
    arguments.output = arguments.output.expanduser().resolve()
    return arguments


def main() -> None:
    arguments = parse_arguments()
    project = ThreeMFProject(arguments.input)
    render_overview(project, arguments.output, arguments.width)


if __name__ == "__main__":
    main()
