"""Check fixed handed storage, live source geometry, and bad loadout poses.

    blender --background --factory-startup --threads 8 --python-exit-code 1 \
        --python models3d/mission1-field-case/check_mission1_field_case_fan_angles.py
"""

from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission1_field_case_blender as case


EXPECTED_STORAGE_ANGLES = ((-15.0, 0.0), (15.0, 0.0))


def source_config():
    names = (
        "CLEAR_SCENE", "EXPORT_STL", "LAYOUT_MODE", "REAR_FAN_ADAPTER_ENABLED",
        "SHOW_BACK_SHELL", "SHOW_HOLLOW_INSERT", "SHOW_BUTTONS",
        "SHOW_FRONT_RETAINER", "SHOW_BAFFLE_CARTRIDGE",
        "FAN_ANGLE_HORIZONTAL_DEG", "FAN_ANGLE_VERTICAL_DEG",
    )
    return {
        name: getattr(case.fan_case, name)
        for name in names if hasattr(case.fan_case, name)
    }


def restore_source_config(config):
    for name, value in config.items():
        setattr(case.fan_case, name, value)


def remove_objects(objects):
    for obj in objects:
        if obj.name in case.bpy.data.objects:
            case.bpy.data.objects.remove(obj, do_unlink=True)


def build_references_from_source_default(material, horizontal, vertical):
    """Build real sources and prove storage yaw does not inherit source yaw."""
    previous = source_config()
    case.fan_case.FAN_ANGLE_HORIZONTAL_DEG = horizontal
    case.fan_case.FAN_ANGLE_VERTICAL_DEG = vertical
    configured = source_config()
    observed_build_angles = []
    real_builder = case.fan_case.build_gopro_fan_case

    def capture_real_build():
        observed_build_angles.append((
            case.fan_case.FAN_ANGLE_HORIZONTAL_DEG,
            case.fan_case.FAN_ANGLE_VERTICAL_DEG,
        ))
        return real_builder()

    try:
        with patch.object(
                case.fan_case, "build_gopro_fan_case", side_effect=capture_real_build):
            references = case.create_fan_case_pair_reference_mockups(*([material] * 7))
        assert tuple(observed_build_angles) == EXPECTED_STORAGE_ANGLES, (
            "Fan-case source builder did not receive the explicit -15/+15 storage "
            f"poses: source_default={(horizontal, vertical)!r} "
            f"observed={observed_build_angles!r}"
        )
        assert source_config() == configured, (
            "Successful source builds did not restore the companion configuration"
        )
        return references
    finally:
        restore_source_config(previous)


def check_failed_source_build_restores_config(material):
    previous = source_config()
    case.fan_case.FAN_ANGLE_HORIZONTAL_DEG = 23.0
    case.fan_case.FAN_ANGLE_VERTICAL_DEG = -7.0
    configured = source_config()
    observed_build_angles = []

    def fail_at_builder():
        observed_build_angles.append((
            case.fan_case.FAN_ANGLE_HORIZONTAL_DEG,
            case.fan_case.FAN_ANGLE_VERTICAL_DEG,
        ))
        raise RuntimeError("test failure")

    try:
        with patch.object(
                case.fan_case, "build_gopro_fan_case", side_effect=fail_at_builder):
            try:
                case.create_fan_case_source_reference_mockups(
                    *([material] * 7), assembly_index=2)
            except RuntimeError as error:
                assert str(error) == "test failure"
            else:
                raise AssertionError("The injected source-build failure was not propagated")
        assert observed_build_angles == [EXPECTED_STORAGE_ANGLES[1]], (
            "A failed source build did not use the explicit +15-degree storage pose"
        )
        assert source_config() == configured, (
            "Failed source build leaked its temporary companion configuration"
        )
    finally:
        restore_source_config(previous)


class PreviewModeMustNotBeRead:
    """Sentinel proving lower-insert geometry does not branch on preview mode."""

    def __bool__(self):
        raise AssertionError("Fan-case insert geometry read BUILD_REFERENCE_MOCKUPS")


def check_profile_minimum_feature_closing():
    """Close a skinny TPU finger while retaining a broad synthetic side gap."""
    from shapely.geometry import Point

    blocks = [
        case.add_rounded_box(
            f"TEST_Runtime_Profile_Block_{index}",
            (20.0, 30.0, 2.0),
            (center_x, 0.0, 1.0),
            bevel=0.0,
        )
        for index, center_x in enumerate((0.0, 24.0, 64.0), start=1)
    ]
    try:
        profile = case.fan_case_assembly_extraction_profile(blocks, clearance=0.0)
        narrow_gap_center = Point(12.0, 0.0)
        broad_gap_center = Point(44.0, 0.0)
        assert profile.covers(narrow_gap_center), (
            "Runtime profile left a 4 mm TPU finger between source meshes"
        )
        broad_gap_clearance = profile.distance(broad_gap_center)
        assert broad_gap_clearance > 8.0, (
            "Runtime profile erased the intended broad 20 mm dome-side gap: "
            f"center_clearance={broad_gap_clearance:.6f}"
        )
    finally:
        remove_objects(blocks)
    return broad_gap_clearance


def create_insert_from_existing_references(material, references):
    """Build once, capturing its profiles and forbidding a hidden source rebuild."""
    real_profile_builder = case.fan_case_pair_extraction_profiles
    captured = {}

    def capture_profiles(received):
        assert received is references, "Lower insert did not reuse supplied references"
        profiles = real_profile_builder(received)
        captured["profiles"] = profiles
        return profiles

    previous_preview = case.BUILD_REFERENCE_MOCKUPS
    case.BUILD_REFERENCE_MOCKUPS = PreviewModeMustNotBeRead()
    try:
        with patch.object(
                case,
                "create_fan_case_pair_reference_mockups",
                side_effect=AssertionError("Lower insert rebuilt supplied references"),
        ), patch.object(
                case,
                "fan_case_pair_extraction_profiles",
                side_effect=capture_profiles,
        ):
            insert = case.create_fan_case_pair_insert(material, references)
    finally:
        case.BUILD_REFERENCE_MOCKUPS = previous_preview
    assert "profiles" in captured, "Lower insert did not derive runtime extraction profiles"
    return insert, captured["profiles"]


def check_profile_tracks_runtime_mesh(references, baseline_profile):
    group = [
        obj for obj in references
        if obj.name.startswith("REFERENCE_ONLY_Fan_Case_Assembly_1_")
    ]
    back = next(obj for obj in group if "GoPro_Fan_Case_Back" in obj.name)
    original_coordinates = [vertex.co.copy() for vertex in back.data.vertices]
    local_x = [coordinate.x for coordinate in original_coordinates]
    center_x = (min(local_x) + max(local_x)) / 2.0
    try:
        # Alter the actual generated mesh, rather than any analytic case envelope.
        # A large but valid width change makes this regression insensitive to the
        # cover's projected outline while retaining the shell's curved topology.
        for vertex, coordinate in zip(back.data.vertices, original_coordinates):
            vertex.co.x = center_x + (coordinate.x - center_x) * 1.5
        back.data.update()
        case.bpy.context.view_layer.update()
        changed_profile = case.fan_case_assembly_extraction_profile(group)
        changed_area = baseline_profile.symmetric_difference(changed_profile).area
        bounds_changed = any(
            abs(before - after) > 0.5
            for before, after in zip(baseline_profile.bounds, changed_profile.bounds)
        )
        assert changed_area > 1.0 and bounds_changed, (
            "Extraction profile ignored altered runtime source mesh dimensions: "
            f"symmetric_difference={changed_area:.6f}"
        )
    finally:
        for vertex, coordinate in zip(back.data.vertices, original_coordinates):
            vertex.co = coordinate
        back.data.update()
        case.bpy.context.view_layer.update()
    return changed_area


def check_blocked_door(references):
    door = next(obj for obj in references
                if obj.name.startswith("REFERENCE_ONLY_Fan_Case_Battery_Door_1"))
    minimum, maximum = case.object_world_bounds(door)
    blocker = case.add_rounded_box("TEST_Blocked_Door_Extraction", (4.0, 8.0, 2.0),
        ((minimum.x + maximum.x) / 2.0, (minimum.y + maximum.y) / 2.0,
         maximum.z + 10.0), bevel=0.0)
    try:
        try:
            case.validate_fan_case_accessory_lift_paths((door,), (blocker,))
        except ValueError:
            pass
        else:
            raise AssertionError("An obstruction above a seated door escaped lift validation")
    finally:
        case.bpy.data.objects.remove(blocker, do_unlink=True)


def check_bad_fan_pose(references):
    group = [
        obj for obj in references
        if obj.name.startswith("REFERENCE_ONLY_Fan_Case_Assembly_1_")
    ]
    fan = next(obj for obj in group if "Direct_40mm_Rear_Fan" in obj.name)
    location = fan.location.copy()
    try:
        fan.location.y += 1.0
        case.bpy.context.view_layer.update()
        try:
            case.validate_fan_case_mount_alignment(group, 1)
        except ValueError:
            pass
        else:
            raise AssertionError("An incorrectly seated fan escaped mount validation")
    finally:
        fan.location = location
        case.bpy.context.view_layer.update()
    case.validate_fan_case_mount_alignment(group, 1)


def check_blocked_complete_assembly_lift(parts, references, profile):
    assembly_groups = [[
        obj for obj in references
        if obj.name.startswith(
            f"REFERENCE_ONLY_Fan_Case_Assembly_{assembly_index}_"
        )
    ] for assembly_index in range(1, case.FAN_CASE_STORAGE_COUNT + 1)]
    assembly_top = max(
        case.object_world_bounds(obj)[1].z for obj in assembly_groups[0]
    )
    xmin, ymin, xmax, ymax = profile.bounds
    blocker = case.add_rounded_box(
        "TEST_Blocked_Complete_Assembly_Lift",
        (xmax - xmin, ymax - ymin, 3.0),
        (
            (xmin + xmax) / 2.0,
            (ymin + ymax) / 2.0,
            assembly_top + 6.5,
        ),
        bevel=0.0,
    )
    original_base = parts["base"]
    parts["base"] = blocker
    try:
        try:
            case.validate_fan_case_contoured_cradle(parts, assembly_groups)
        except ValueError as error:
            message = str(error)
            assert (
                "Contoured assembly lift is obstructed" in message
                and blocker.name in message
            ), f"Unexpected contoured-cradle rejection: {message}"
        else:
            raise AssertionError(
                "A broad obstruction above assembly 1 escaped continuous-lift validation"
            )
    finally:
        parts["base"] = original_base
        case.bpy.data.objects.remove(blocker, do_unlink=True)


def check_loadout():
    case.clear_scene()
    original_config = source_config()
    assert case.FAN_CASE_STORAGE_FAN_ANGLES == EXPECTED_STORAGE_ANGLES, (
        "Storage must retain explicit outward -15/+15-degree fan poses"
    )
    case.validate_configuration()
    broad_gap_clearance = check_profile_minimum_feature_closing()
    material = case.make_material("Angle_Check", (0.5, 0.5, 0.5))

    # Keep the angle-zero build for the loadout. Build and discard a second
    # nonzero/non-storage-default source to prove neither companion default is
    # inherited by the two storage assemblies.
    references = build_references_from_source_default(material, 0.0, 0.0)
    alternate_references = build_references_from_source_default(material, 31.0, -4.0)
    remove_objects(alternate_references)
    assert source_config() == original_config

    insert, profiles = create_insert_from_existing_references(material, references)
    parts = {
        "base": case.create_base(material),
        "fan_case_pair_insert": insert,
        "fan_case_pair_carrier": case.create_fan_case_pair_overhead_carrier(material),
        "fan_case_pair_storage_bin": case.create_fan_case_pair_storage_bin(material),
        "fan_case_pair_lid_pad": case.create_fan_case_pair_lid_pad(material),
    }
    profile_delta = check_profile_tracks_runtime_mesh(references, profiles[0])

    for name, obj in parts.items():
        case.validate_built_part(name, obj)
    case.validate_fan_case_pair_loadout(parts, references)
    check_blocked_complete_assembly_lift(parts, references, profiles[0])
    check_blocked_door(references)
    check_bad_fan_pose(references)
    check_failed_source_build_restores_config(material)

    assert source_config() == original_config, "Regression leaked source configuration"
    assert (case.CASE_WIDTH, case.CASE_DEPTH, case.BASE_HEIGHT) == (234.0, 158.0, 97.8)
    print(
        "FIELD_CASE_FAN_ANGLE_REGRESSION_PASS "
        "storage_yaws=-15,+15 source_defaults=0,31 "
        f"runtime_profile_delta={profile_delta:.3f} "
        f"synthetic_broad_gap_clearance={broad_gap_clearance:.3f} "
        "preview_independent=True references_reused=True bad_pose_rejected=True "
        "blocked_door_lift_rejected=True blocked_assembly_lift_rejected=True "
        "source_config_restored=True",
        flush=True,
    )


if __name__ == "__main__":
    check_loadout()
