"""Check fixed handed storage, live source geometry, and bad loadout poses.

    blender --background --factory-startup --threads 8 --python-exit-code 1 \
        --python models3d/mission1-field-case/check_mission1_field_case_fan_angles.py
"""

from pathlib import Path
import math
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
    """Build once, reusing profiles and forbidding a hidden source rebuild."""
    extraction_geometry = case.fan_case_pair_extraction_profiles(
        references,
        return_rear_reliefs=True,
    )

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
            side_effect=AssertionError("Lower insert rebuilt supplied profiles"),
        ):
            insert = case.create_fan_case_pair_insert(
                material,
                references,
                extraction_geometry=extraction_geometry,
            )
    finally:
        case.BUILD_REFERENCE_MOCKUPS = previous_preview
    return insert, *extraction_geometry


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


def profile_projection_limits(profile, direction):
    """Return min/max coordinates along a world-XY direction."""
    polygons = list(profile.geoms) if profile.geom_type == "MultiPolygon" else [profile]
    projections = []
    for polygon in polygons:
        for ring in (polygon.exterior, *polygon.interiors):
            projections.extend(
                x * direction.x + y * direction.y for x, y in ring.coords
            )
    return min(projections), max(projections)


def check_rear_fan_depth_allowance(references, nominal_profiles, rear_reliefs):
    """Prove only each rectangular slot's back edge gains exactly 1.5 mm."""
    from shapely import union_all

    assert math.isclose(case.FAN_CASE_REAR_DEPTH_ALLOWANCE, 1.5, abs_tol=1e-9)
    measured = []
    for index, (nominal, rear_relief) in enumerate(
        zip(nominal_profiles, rear_reliefs), start=1
    ):
        group = [
            obj for obj in references
            if obj.name.startswith(f"REFERENCE_ONLY_Fan_Case_Assembly_{index}_")
        ]
        rebuilt_nominal = case.fan_case_assembly_extraction_profile(group)
        if nominal.symmetric_difference(rebuilt_nominal).area > 1e-7:
            raise AssertionError(f"Assembly {index} nominal profile was modified")
        relieved = union_all((nominal, rear_relief))
        outward = (
            case.FAN_CASE_PAIR_STORAGE["fan_transforms"][index - 1].to_3x3()
            @ case.Vector((0.0, -1.0, 0.0))
        ).normalized()
        nominal_rear = profile_projection_limits(nominal, outward)[1]
        relieved_rear = profile_projection_limits(relieved, outward)[1]
        allowance = relieved_rear - nominal_rear
        assert math.isclose(
            allowance, case.FAN_CASE_REAR_DEPTH_ALLOWANCE, abs_tol=0.01
        ), (
            f"Assembly {index} rear relief is {allowance:.6f} mm, expected "
            f"{case.FAN_CASE_REAR_DEPTH_ALLOWANCE:.6f} mm"
        )
        slot_band = case.fan_case_rear_slot_relief_region(index)
        added = relieved.difference(nominal)
        unexpected_added_area = added.difference(slot_band).area
        removed_area = nominal.difference(relieved).area
        if unexpected_added_area > 1e-7 or removed_area > 1e-7:
            raise AssertionError(
                f"Assembly {index} changed outside its rectangular rear slot: "
                f"unexpected_added={unexpected_added_area:.9f} "
                f"removed={removed_area:.9f}"
            )
        lateral = (
            case.FAN_CASE_PAIR_STORAGE["fan_transforms"][index - 1].to_3x3()
            @ case.Vector((1.0, 0.0, 0.0))
        ).normalized()
        transform = case.FAN_CASE_PAIR_STORAGE["fan_transforms"][index - 1]
        placement = case.Vector(
            case.FAN_CASE_PAIR_STORAGE["placements"][index - 1]
        )
        cover_x0, cover_x1 = (
            case.FAN_CASE_PAIR_STORAGE["straight_cover_bounds"][:2]
        )
        expected_clearance = case.FAN_CASE_STORAGE_CLEARANCE + 0.01
        expected_local_sides = (
            cover_x0 - expected_clearance,
            cover_x1 + expected_clearance,
        )
        expected_sides = []
        for x in expected_local_sides:
            point = transform @ case.Vector((x, 0.0, 0.0)) + placement
            expected_sides.append(point.x * lateral.x + point.y * lateral.y)
        expected_sides = tuple(sorted(expected_sides))
        actual_sides = profile_projection_limits(slot_band, lateral)
        if any(
            not math.isclose(expected, actual, abs_tol=0.001)
            for expected, actual in zip(expected_sides, actual_sides)
        ):
            raise AssertionError(
                f"Assembly {index} rectangular slot width or side walls changed: "
                f"expected={expected_sides} actual={actual_sides}"
            )
        measured.append(allowance)
    return measured


def check_finished_rear_fan_depth_relief(insert, rear_reliefs):
    """Ensure no later insert operation refills the added rear cavity bands."""
    maximum_overlap = 0.0
    for index, added_relief in enumerate(rear_reliefs, start=1):
        if added_relief.area <= 1.0:
            raise AssertionError(
                f"Assembly {index} has no substantial rear depth relief"
            )
        # Stay 0.01 mm off the Boolean's coincident walls and top/bottom faces;
        # the separate directional check above owns the exact 1.500 mm extent.
        probe_region = added_relief.buffer(-0.01)
        if probe_region.is_empty:
            raise AssertionError(f"Assembly {index} rear depth relief is too narrow")
        probe = case.extrude_planar_region(
            f"TEST_Finished_Insert_Rear_Fan_Relief_{index}",
            probe_region,
            case.fan_case_rear_slot_relief_bottom_z(index) + 0.01,
            case.FAN_CASE_PAIR_CARRIER_SUPPORT["web_top_z"] + 0.99,
        )
        probe.location.z = case.FAN_CASE_PAIR_INSERT_INSTALLED_Z
        try:
            _faces, overlap = case.exact_transformed_intersection(
                insert,
                probe,
                first_location=insert.location.copy(),
                first_rotation=insert.rotation_euler.copy(),
                second_location=probe.location.copy(),
                second_rotation=probe.rotation_euler.copy(),
            )
        finally:
            case.bpy.data.objects.remove(probe, do_unlink=True)
        if overlap > 1e-5:
            raise AssertionError(
                f"Finished insert refills assembly {index} rear relief: "
                f"overlap={overlap:.6f} mm^3"
            )
        maximum_overlap = max(maximum_overlap, overlap)
    return maximum_overlap


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


def check_blocked_complete_assembly_lift(parts, references, profiles):
    assembly_groups = [[
        obj for obj in references
        if obj.name.startswith(
            f"REFERENCE_ONLY_Fan_Case_Assembly_{assembly_index}_"
        )
    ] for assembly_index in range(1, case.FAN_CASE_STORAGE_COUNT + 1)]
    assembly_top = max(
        case.object_world_bounds(obj)[1].z for obj in assembly_groups[0]
    )
    xmin, ymin, xmax, ymax = profiles[0].bounds
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
            case.validate_fan_case_contoured_cradle(
                parts,
                assembly_groups,
                profiles,
            )
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

    insert, profiles, rear_reliefs = create_insert_from_existing_references(
        material, references
    )
    parts = {
        "base": case.create_base(material),
        "fan_case_pair_insert": insert,
        "fan_case_pair_carrier": case.create_fan_case_pair_overhead_carrier(material),
        "fan_case_pair_storage_bin": case.create_fan_case_pair_storage_bin(material),
        "fan_case_pair_lid_pad": case.create_fan_case_pair_lid_pad(material),
    }
    parts["lid"], inlay = case.create_lid(material, material)
    case.bpy.data.objects.remove(inlay, do_unlink=True)
    if case.EXPANDED_ACCESSORY_STORAGE:
        parts["tpu_snap_lid"], inlay = case.create_lid(
            material,
            material,
            hinge_profile=case.HINGE_PROFILE_TPU_68D_SNAP,
        )
        case.bpy.data.objects.remove(inlay, do_unlink=True)
        parts["accessory_organizer"] = case.create_accessory_organizer(material)
        references.extend(case.create_accessory_reference_mockups(material))
    profile_delta = check_profile_tracks_runtime_mesh(references, profiles[0])
    rear_depth_allowances = check_rear_fan_depth_allowance(
        references, profiles, rear_reliefs
    )
    finished_relief_overlap = check_finished_rear_fan_depth_relief(
        insert, rear_reliefs
    )

    for name, obj in parts.items():
        case.validate_built_part(name, obj)
    with patch.object(
        case,
        "fan_case_assembly_extraction_profile",
        side_effect=AssertionError("Loadout validation rebuilt supplied profiles"),
    ):
        case.validate_fan_case_pair_loadout(
            parts,
            references,
            extraction_profiles=profiles,
        )
    check_blocked_complete_assembly_lift(parts, references, profiles)
    check_blocked_door(references)
    check_bad_fan_pose(references)
    check_failed_source_build_restores_config(material)

    assert source_config() == original_config, "Regression leaked source configuration"
    assert (case.CASE_WIDTH, case.CASE_DEPTH, case.BASE_HEIGHT) == ((234.0, 180.0, 160.0) if case.EXPANDED_ACCESSORY_STORAGE else (234.0, 158.0, 97.8))
    print(
        "FIELD_CASE_FAN_ANGLE_REGRESSION_PASS "
        "storage_yaws=-15,+15 source_defaults=0,31 "
        f"runtime_profile_delta={profile_delta:.3f} "
        "rear_depth_allowances="
        + ",".join(f"{value:.3f}" for value in rear_depth_allowances)
        + " "
        f"finished_relief_overlap={finished_relief_overlap:.6f} "
        f"synthetic_broad_gap_clearance={broad_gap_clearance:.3f} "
        "preview_independent=True references_reused=True bad_pose_rejected=True "
        "blocked_door_lift_rejected=True blocked_assembly_lift_rejected=True "
        "source_config_restored=True",
        flush=True,
    )


if __name__ == "__main__":
    check_loadout()
