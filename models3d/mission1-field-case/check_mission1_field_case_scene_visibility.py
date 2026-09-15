"""Check both case profiles and both lid variants in the generated scene.

Run from the repository root with::

    blender --background --factory-startup --python-exit-code 1 \
      --python models3d/mission1-field-case/check_mission1_field_case_scene_visibility.py
"""

import hashlib
from array import array
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


SCRIPT_PATH = Path(__file__).resolve().with_name("mission1_field_case_blender.py")


def linked_mesh_object(name, collection):
    mesh = bpy.data.meshes.new(name + "_MESH")
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    return obj


def mesh_fingerprint(obj):
    mesh = obj.data
    digest = hashlib.sha256()
    coordinates = array("f", [0.0]) * (len(mesh.vertices) * 3)
    mesh.vertices.foreach_get("co", coordinates)
    digest.update(coordinates.tobytes())
    loop_vertices = array("i", [0]) * len(mesh.loops)
    mesh.loops.foreach_get("vertex_index", loop_vertices)
    digest.update(loop_vertices.tobytes())
    polygon_starts = array("i", [0]) * len(mesh.polygons)
    polygon_totals = array("i", [0]) * len(mesh.polygons)
    mesh.polygons.foreach_get("loop_start", polygon_starts)
    mesh.polygons.foreach_get("loop_total", polygon_totals)
    digest.update(polygon_starts.tobytes())
    digest.update(polygon_totals.tobytes())
    return digest.digest()


# Model Text Editor reruns after objects and collections were hidden or excluded.
bpy.ops.mesh.primitive_cube_add(size=1.0)
hidden_rerun_sentinel_name = bpy.context.object.name
bpy.context.object.hide_set(True)
bpy.context.object.hide_render = True

hidden_collection = bpy.data.collections.new("FIELD_CASE_STALE_HIDDEN_COLLECTION")
bpy.context.scene.collection.children.link(hidden_collection)
hidden_collection_sentinel = linked_mesh_object(
    "FIELD_CASE_STALE_HIDDEN_COLLECTION_OBJECT", hidden_collection
)
hidden_collection.hide_viewport = True
hidden_collection.hide_render = True
hidden_collection_name = hidden_collection.name
hidden_collection_sentinel_name = hidden_collection_sentinel.name

excluded_collection = bpy.data.collections.new("FIELD_CASE_STALE_EXCLUDED_COLLECTION")
bpy.context.scene.collection.children.link(excluded_collection)
excluded_collection_sentinel = linked_mesh_object(
    "FIELD_CASE_STALE_EXCLUDED_COLLECTION_OBJECT", excluded_collection
)
bpy.context.view_layer.update()
excluded_layer_collection = bpy.context.view_layer.layer_collection.children.get(
    excluded_collection.name
)
if excluded_layer_collection is None:
    raise AssertionError("Could not create the excluded-collection rerun fixture")
excluded_layer_collection.exclude = True
excluded_collection_name = excluded_collection.name
excluded_collection_sentinel_name = excluded_collection_sentinel.name

other_scene = bpy.data.scenes.new("FIELD_CASE_OTHER_SCENE_SENTINEL")
other_scene_object = linked_mesh_object(
    "FIELD_CASE_OTHER_SCENE_SENTINEL", other_scene.collection
)
other_scene_sentinel_pointer = other_scene_object.as_pointer()

shared_object = linked_mesh_object(
    "FIELD_CASE_SHARED_OBJECT_SENTINEL", bpy.context.scene.collection
)
other_scene.collection.objects.link(shared_object)
shared_object_pointer = shared_object.as_pointer()

foreign_case_collection = bpy.data.collections.new(
    "Generated - Fan Case Assembly"
)
other_scene.collection.children.link(foreign_case_collection)
foreign_case_object = linked_mesh_object(
    "FIELD_CASE_FOREIGN_ASSEMBLY_SENTINEL", foreign_case_collection
)
foreign_case_collection_pointer = foreign_case_collection.as_pointer()
foreign_case_object_pointer = foreign_case_object.as_pointer()

instanced_collection = bpy.data.collections.new(
    "FIELD_CASE_INSTANCED_COLLECTION_SENTINEL"
)
bpy.context.scene.collection.children.link(instanced_collection)
instanced_collection_object = linked_mesh_object(
    "FIELD_CASE_INSTANCED_COLLECTION_OBJECT", instanced_collection
)
collection_instancer = bpy.data.objects.new(
    "FIELD_CASE_OTHER_SCENE_COLLECTION_INSTANCE", None
)
collection_instancer.instance_type = "COLLECTION"
collection_instancer.instance_collection = instanced_collection
other_scene.collection.objects.link(collection_instancer)
instanced_collection_pointer = instanced_collection.as_pointer()
instanced_collection_object_pointer = instanced_collection_object.as_pointer()
collection_instancer_pointer = collection_instancer.as_pointer()

namespace = {
    "__name__": "mission1_field_case_scene_visibility_check",
    "__file__": str(SCRIPT_PATH),
    "VISIBLE_CASE_ASSEMBLY": "FAN_CASE",
    "VISIBLE_LID_VARIANT": "RIGID",
    "ASSEMBLE_VISIBLE_SCENE_AFTER_BUILD": True,
    "GENERATE_ALL_CASE_ASSEMBLIES": True,
    "EXPANDED_ACCESSORY_STORAGE": True,
}
exec(compile(SCRIPT_PATH.read_bytes(), str(SCRIPT_PATH), "exec"), namespace)


def check_separate_gasket_assembly_pose():
    previous_gasket_mode = namespace["PRINT_TPU_GASKET_WITH_LID"]
    namespace["PRINT_TPU_GASKET_WITH_LID"] = False
    material = namespace["make_material"](
        "FIELD_CASE_SEPARATE_GASKET_CHECK", (0.8, 0.2, 0.05)
    )
    gasket = namespace["create_gasket"](material)
    tpu_gasket = namespace["duplicate_reference_part"](
        gasket,
        namespace["TPU_LID_GASKET_REFERENCE_PREFIX"] + "_CHECK",
        material,
    )
    objects = (gasket, tpu_gasket)
    meshes = tuple(obj.data for obj in objects)
    fingerprints = {obj.as_pointer(): mesh_fingerprint(obj) for obj in objects}
    try:
        for angle in (0.0, 47.0, 110.0):
            lid_location, lid_rotation = namespace["installed_lid_pose"](angle)
            lid_matrix = Matrix.Translation(Vector(lid_location)) @ Matrix.Rotation(
                lid_rotation[0], 4, "X"
            )
            for obj in objects:
                namespace["pose_gasket_with_lid"](
                    obj, lid_location, lid_rotation
                )
                bpy.context.view_layer.update()
                gasket_to_lid = lid_matrix.inverted() @ obj.matrix_world
                coordinates = [
                    gasket_to_lid @ vertex.co for vertex in obj.data.vertices
                ]
                minimum = Vector(
                    tuple(
                        min(coordinate[axis] for coordinate in coordinates)
                        for axis in range(3)
                    )
                )
                maximum = Vector(
                    tuple(
                        max(coordinate[axis] for coordinate in coordinates)
                        for axis in range(3)
                    )
                )
                center = (minimum + maximum) / 2.0
                expected_center = Vector(
                    (
                        namespace["LID_DISPLAY_OFFSET_X"],
                        0.0,
                        namespace["GASKET_INSTALLED_Z"]
                        + namespace["GASKET_HEIGHT"] / 2.0,
                    )
                )
                if (center - expected_center).length > 1e-4:
                    raise AssertionError(
                        f"Separate gasket is displaced at {angle} degrees: "
                        f"actual={tuple(center)} expected={tuple(expected_center)}"
                    )
                actual_height = maximum.z - minimum.z
                if abs(actual_height - namespace["GASKET_HEIGHT"]) >= 1e-4:
                    raise AssertionError(
                        f"Separate gasket height is incorrect at {angle} degrees: "
                        f"actual={actual_height} "
                        f"expected={namespace['GASKET_HEIGHT']}"
                    )
        current_fingerprints = {
            obj.as_pointer(): mesh_fingerprint(obj) for obj in objects
        }
        if current_fingerprints != fingerprints:
            raise AssertionError("Posing a separate gasket modified its mesh")
    finally:
        namespace["PRINT_TPU_GASKET_WITH_LID"] = previous_gasket_mode
        for obj in objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in meshes:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)


check_separate_gasket_assembly_pose()
namespace["build_all_case_assemblies"]()
profiles = namespace["_LAST_CASE_ASSEMBLIES"]
fan_case = namespace["CASE_ASSEMBLY_FAN_CASE"]
original = namespace["CASE_ASSEMBLY_ORIGINAL"]
rigid_lid = namespace["LID_VARIANT_RIGID"]
tpu_lid = namespace["LID_VARIANT_TPU_68D"]
object_pointers = {obj.as_pointer() for obj in bpy.context.scene.objects}
data_object_pointers = {obj.as_pointer() for obj in bpy.data.objects}
data_collection_pointers = {
    collection.as_pointer() for collection in bpy.data.collections
}
stale_object_names = {
    hidden_rerun_sentinel_name,
    hidden_collection_sentinel_name,
    excluded_collection_sentinel_name,
}
surviving_stale_objects = sorted(
    name for name in stale_object_names if bpy.data.objects.get(name) is not None
)
if surviving_stale_objects:
    raise AssertionError(
        "Hidden or excluded current-scene objects survived clear_scene: "
        f"{surviving_stale_objects}"
    )
stale_collection_names = {
    hidden_collection_name,
    excluded_collection_name,
}
surviving_stale_collections = sorted(
    name
    for name in stale_collection_names
    if bpy.data.collections.get(name) is not None
)
if surviving_stale_collections:
    raise AssertionError(
        "Hidden or excluded current-scene collections survived clear_scene: "
        f"{surviving_stale_collections}"
    )

other_scene_pointers = {obj.as_pointer() for obj in other_scene.objects}
required_other_scene_pointers = {
    other_scene_sentinel_pointer,
    shared_object_pointer,
    foreign_case_object_pointer,
    collection_instancer_pointer,
}
if not required_other_scene_pointers <= other_scene_pointers:
    raise AssertionError("clear_scene removed an object used by another scene")
current_collection_pointers = {
    collection.as_pointer()
    for collection in bpy.context.scene.collection.children_recursive
}
other_collection_pointers = {
    collection.as_pointer()
    for collection in other_scene.collection.children_recursive
}
if foreign_case_collection_pointer not in other_collection_pointers:
    raise AssertionError("clear_scene removed the other scene's assembly collection")
if foreign_case_collection_pointer in current_collection_pointers:
    raise AssertionError("The other scene's assembly collection leaked into this scene")
if {obj.as_pointer() for obj in foreign_case_collection.objects} != {
    foreign_case_object_pointer
}:
    raise AssertionError("Generation mutated the other scene's assembly collection")
if (
    instanced_collection_pointer not in data_collection_pointers
    or instanced_collection_object_pointer not in data_object_pointers
    or instanced_collection_pointer in current_collection_pointers
):
    raise AssertionError("clear_scene damaged or retained an externally instanced collection")

generated_pointers = {
    obj.as_pointer()
    for profile in profiles.values()
    for obj in profile["objects"]
}
if generated_pointers & other_scene_pointers:
    raise AssertionError("Generated current-scene objects leaked into another scene")
if generated_pointers != object_pointers:
    objects_by_pointer = {
        obj.as_pointer(): obj.name for obj in bpy.context.scene.objects
    }
    generated_objects_by_pointer = {
        obj.as_pointer(): obj.name
        for profile in profiles.values()
        for obj in profile["objects"]
    }
    missing = sorted(
        generated_objects_by_pointer[pointer]
        for pointer in generated_pointers - object_pointers
    )
    extra = sorted(
        objects_by_pointer[pointer]
        for pointer in object_pointers - generated_pointers
    )
    raise AssertionError(
        "Generated profile inventories differ from the current scene: "
        f"missing={missing} extra={extra}"
    )

for case_variant, profile in profiles.items():
    function_globals = profile["configure"].__globals__
    tpu_only_references = tuple(
        obj
        for obj in profile["references"]
        if obj.name.startswith(
            (
                function_globals["TPU_LID_LOGO_REFERENCE_PREFIX"],
                function_globals["TPU_LID_GASKET_REFERENCE_PREFIX"],
                function_globals["TPU_LID_PAD_REFERENCE_PREFIX"],
            )
        )
    )
    if len(tpu_only_references) != 3:
        raise AssertionError(
            f"{case_variant} does not contain one complete TPU lid assembly"
        )
    has_stored_mockups = function_globals[
        "has_stored_dual_fan_reference_mockups"
    ]
    if has_stored_mockups(tpu_only_references):
        raise AssertionError("TPU lid references imply stored-equipment mockups")
    expected_stored_mockups = case_variant == original
    if has_stored_mockups(profile["references"]) != expected_stored_mockups:
        raise AssertionError(
            f"{case_variant} stored-equipment mockup detection is incorrect"
        )

geometry_objects = {}
for profile in profiles.values():
    for obj in profile["parts"].values():
        geometry_objects[obj.as_pointer()] = obj
    function_globals = profile["configure"].__globals__
    for prefix in (
        function_globals["TPU_LID_LOGO_REFERENCE_PREFIX"],
        function_globals["TPU_LID_GASKET_REFERENCE_PREFIX"],
        function_globals["TPU_LID_PAD_REFERENCE_PREFIX"],
    ):
        obj = next(
            candidate
            for candidate in profile["references"]
            if candidate.name.startswith(prefix)
        )
        geometry_objects[obj.as_pointer()] = obj
mesh_fingerprints = {
    pointer: mesh_fingerprint(obj) for pointer, obj in geometry_objects.items()
}


def assert_vector_close(actual, expected, label):
    if (Vector(actual) - Vector(expected)).length > 1e-5:
        raise AssertionError(
            f"{label}: actual={tuple(actual)} expected={tuple(expected)}"
        )


def reference_with_prefix(profile, prefix):
    matches = [
        obj for obj in profile["references"] if obj.name.startswith(prefix)
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {prefix} reference, got {len(matches)}")
    return matches[0]


def assert_complete_lids_are_assembled(case_variant):
    profile = profiles[case_variant]
    function_globals = profile["configure"].__globals__
    lid_location, lid_rotation = function_globals["installed_lid_pose"](
        function_globals["ASSEMBLED_LID_OPEN_ANGLE_DEGREES"]
    )
    rigid_objects = (
        profile["parts"]["lid"],
        profile["parts"]["logo_orange_inlay"],
        profile["parts"]["gasket"],
    )
    tpu_objects = (
        profile["parts"]["tpu_snap_lid"],
        reference_with_prefix(
            profile, function_globals["TPU_LID_LOGO_REFERENCE_PREFIX"]
        ),
        reference_with_prefix(
            profile, function_globals["TPU_LID_GASKET_REFERENCE_PREFIX"]
        ),
    )
    for variant, objects in ((rigid_lid, rigid_objects), (tpu_lid, tpu_objects)):
        for obj in objects:
            assert_vector_close(
                obj.location, lid_location, f"{case_variant}/{variant}/{obj.name} location"
            )
            assert_vector_close(
                obj.rotation_euler,
                lid_rotation,
                f"{case_variant}/{variant}/{obj.name} rotation",
            )

    pad_location, pad_rotation = function_globals["installed_flat_lid_pad_pose"](
        function_globals["ASSEMBLED_LID_OPEN_ANGLE_DEGREES"]
    )
    rigid_pad_key = (
        "fan_case_pair_lid_pad" if case_variant == fan_case else "lid_retainer"
    )
    for variant, pad in (
        (rigid_lid, profile["parts"][rigid_pad_key]),
        (
            tpu_lid,
            reference_with_prefix(
                profile, function_globals["TPU_LID_PAD_REFERENCE_PREFIX"]
            ),
        ),
    ):
        assert_vector_close(
            pad.location, pad_location, f"{case_variant}/{variant}/pad location"
        )
        assert_vector_close(
            pad.rotation_euler, pad_rotation, f"{case_variant}/{variant}/pad rotation"
        )

    hinge_pin = profile["parts"]["hinge_pin"]
    assert_vector_close(
        hinge_pin.location,
        (
            0.0,
            function_globals["HINGE_AXIS_Y"],
            function_globals["BASE_HEIGHT"]
            + function_globals["HINGE_PIN_FLAT_CHORD_Z"],
        ),
        f"{case_variant}/hinge pin location",
    )


def hide_every_generated_object():
    for profile in profiles.values():
        for obj in profile["objects"]:
            namespace["set_scene_object_visibility"](obj, False)


def check_variant(
    case_variant,
    lid_variant,
    expected_loadout_parts,
    expected_reference_prefixes,
    *,
    configure_first=True,
):
    profile = profiles[case_variant]
    configure = profile["configure"]
    if configure_first:
        hide_every_generated_object()
        configure.__globals__["VISIBLE_LID_VARIANT"] = lid_variant
        configure(profile["parts"], profile["references"])

    if lid_variant == rigid_lid:
        expected_visible_parts = {
            "base",
            "hinge_pin",
            "lid",
            "logo_orange_inlay",
            "gasket",
            *expected_loadout_parts,
        }
        selected_reference_prefixes = expected_reference_prefixes
    else:
        expected_visible_parts = {
            "base",
            "hinge_pin",
            "tpu_snap_lid",
            *expected_loadout_parts,
        }
        function_globals = configure.__globals__
        selected_reference_prefixes = expected_reference_prefixes + (
            function_globals["TPU_LID_LOGO_REFERENCE_PREFIX"],
            function_globals["TPU_LID_GASKET_REFERENCE_PREFIX"],
            function_globals["TPU_LID_PAD_REFERENCE_PREFIX"],
        )

    actual_visible_parts = {
        key
        for key, obj in profile["parts"].items()
        if not obj.hide_get() and not obj.hide_render
    }
    if actual_visible_parts != expected_visible_parts:
        raise AssertionError(
            f"{case_variant}/{lid_variant} visible parts: "
            f"actual={sorted(actual_visible_parts)} "
            f"expected={sorted(expected_visible_parts)}"
        )

    actual_visible_references = {
        obj.name
        for obj in profile["references"]
        if not obj.hide_get() and not obj.hide_render
    }
    expected_visible_references = {
        obj.name
        for obj in profile["references"]
        if obj.name.startswith(selected_reference_prefixes)
    }
    if actual_visible_references != expected_visible_references:
        missing = sorted(expected_visible_references - actual_visible_references)
        extra = sorted(actual_visible_references - expected_visible_references)
        raise AssertionError(
            f"{case_variant}/{lid_variant} reference visibility: "
            f"missing={missing} extra={extra}"
        )

    classified_pointers = {
        obj.as_pointer()
        for obj in (*profile["parts"].values(), *profile["references"])
    }
    visible_hidden_alternatives = [
        obj.name
        for obj in profile["objects"]
        if obj.as_pointer() not in classified_pointers
        and (not obj.hide_get() or not obj.hide_render)
    ]
    if visible_hidden_alternatives:
        raise AssertionError(
            f"{case_variant}/{lid_variant} exposed hidden companion alternatives: "
            f"{visible_hidden_alternatives}"
        )

    other_variant = original if case_variant == fan_case else fan_case
    visible_other_objects = [
        obj.name
        for obj in profiles[other_variant]["objects"]
        if not obj.hide_get() or not obj.hide_render
    ]
    if visible_other_objects:
        raise AssertionError(
            f"{case_variant}/{lid_variant} exposed {other_variant} objects: "
            f"{visible_other_objects}"
        )

    current_pointers = {obj.as_pointer() for obj in bpy.context.scene.objects}
    if current_pointers != object_pointers:
        raise AssertionError("Changing visible assembly generated or deleted objects")
    assert_complete_lids_are_assembled(case_variant)


hardware_prefixes = (
    "REFERENCE_ONLY_CLOSED_Pelican_Source_",
    "REFERENCE_ONLY_Latch_",
    "REFERENCE_ONLY_Folded_Pivoting_Handle",
    "REFERENCE_ONLY_Handle_",
)
fan_case_parts = {
    "fan_case_pair_insert",
    "fan_case_pair_carrier",
    "fan_case_pair_storage_bin",
    "fan_case_pair_lid_pad",
    "accessory_organizer",
}
fan_case_prefixes = hardware_prefixes + (
    "REFERENCE_ONLY_Fan_Case_Assembly_",
    "REFERENCE_ONLY_Fan_Case_Cable_Lead_",
    "REFERENCE_ONLY_Fan_Case_Cable_Coil_",
    "REFERENCE_ONLY_Fan_Case_PWM_Plug_",
    "REFERENCE_ONLY_Fan_Case_Enduro_Battery_",
    "REFERENCE_ONLY_Fan_Case_Battery_Door_",
    "REFERENCE_ONLY_Field_Accessory_",
)
original_parts = {"fan_cradle", "equipment_tray", "lid_retainer"}
original_prefixes = hardware_prefixes + (
    "REFERENCE_ONLY_Stored_",
    "REFERENCE_ONLY_Installed_80mm_Fan_",
    "REFERENCE_ONLY_MISSION1_",
    "REFERENCE_ONLY_Enduro2_",
    "REFERENCE_ONLY_MISSION1_Battery_Cage_Door_",
)

# Both the selected and hidden profiles must already be fully posed by the
# top-level builder before any visibility switching below.
for case_variant in (fan_case, original):
    assert_complete_lids_are_assembled(case_variant)

# The first assertion checks build_all_case_assemblies' direct final state
# without repairing it through the lower-level visibility function.
check_variant(
    fan_case,
    rigid_lid,
    fan_case_parts,
    fan_case_prefixes,
    configure_first=False,
)
check_variant(fan_case, tpu_lid, fan_case_parts - {"fan_case_pair_lid_pad"}, fan_case_prefixes)
check_variant(original, rigid_lid, original_parts, original_prefixes)
check_variant(original, tpu_lid, original_parts - {"lid_retainer"}, original_prefixes)

current_mesh_fingerprints = {
    pointer: mesh_fingerprint(obj) for pointer, obj in geometry_objects.items()
}
if current_mesh_fingerprints != mesh_fingerprints:
    raise AssertionError("Changing visible assembly modified generated mesh geometry")

for case_variant in (fan_case, original):
    assert_complete_lids_are_assembled(case_variant)
    collection_name = (
        f"Generated - {case_variant.replace('_', ' ').title()} Assembly"
    )
    collection = profiles[case_variant]["collection"]
    if not (
        collection.name == collection_name
        or collection.name.startswith(collection_name + ".")
    ):
        raise AssertionError(
            f"{case_variant} generated collection has an unexpected name"
        )
    if collection not in tuple(bpy.context.scene.collection.children):
        raise AssertionError(
            f"{case_variant} generated collection is outside the current scene"
        )
    if collection.as_pointer() in other_collection_pointers:
        raise AssertionError(
            f"{case_variant} generated collection leaked into another scene"
        )
    expected_objects = {
        obj.as_pointer() for obj in profiles[case_variant]["objects"]
    }
    actual_objects = {obj.as_pointer() for obj in collection.objects}
    if actual_objects != expected_objects:
        raise AssertionError(f"{case_variant} generated collection is incomplete")

print(
    "FIELD_CASE_SCENE_VISIBILITY_VALID "
    f"fan_case_parts={len(profiles[fan_case]['parts'])} "
    f"original_parts={len(profiles[original]['parts'])} "
    f"objects={len(object_pointers)} cases=2 lids=2 combinations=4",
    flush=True,
)
