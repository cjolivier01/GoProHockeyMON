"""Check both bottom-corner fan cables and live wrapping-cover notches.

Fast cached-scene run from the repository root::

    blender --background --factory-startup --threads 8 --python-exit-code 1 \
        --python models3d/mission1-field-case/check_mission1_field_case_bottom_cables.py \
        -- --scene /path/to/validated-field-case.blend

Omit ``--scene`` to build the focused parts and references from source.
Neither mode exports STL or 3MF files.
"""

import argparse
import json
import math
from pathlib import Path
import sys
from unittest.mock import patch

from mathutils import Vector


sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission1_field_case_blender as case


PART_OBJECT_NAMES = {
    "base": "Field_Case_Base",
    "fan_case_pair_insert": "Field_Case_Fan_Case_Pair_Lower_TPU_Insert",
    "fan_case_pair_carrier": "Field_Case_Fan_Case_Pair_Rear_Shallow_Tray",
    "fan_case_pair_storage_bin": "Field_Case_Fan_Case_Pair_Front_Deep_Tray",
    "fan_case_pair_lid_pad": "Field_Case_Fan_Case_Pair_TPU_Lid_Pad",
}


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", type=Path)
    script_arguments = (
        sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    )
    return parser.parse_args(script_arguments)


def wrapping_cover_config():
    return {
        name: getattr(case.wrapping_fan_cover, name)
        for name in ("CLEAR_SCENE", "CABLE_NOTCH_SIDE", "CABLE_NOTCH_OFFSET")
    }


def restore_wrapping_cover_config(config):
    for name, value in config.items():
        setattr(case.wrapping_fan_cover, name, value)


def remove_object(obj):
    if obj.name in case.bpy.data.objects:
        case.bpy.data.objects.remove(obj, do_unlink=True)


def load_or_build_loadout(scene_path):
    if scene_path is not None:
        resolved = scene_path.expanduser().resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"Cached field-case scene does not exist: {resolved}")
        case.bpy.ops.wm.open_mainfile(filepath=str(resolved))
        if "cached_field_case_parts" in case.bpy.context.scene:
            names = json.loads(case.bpy.context.scene["cached_field_case_parts"])
        else:
            names = PART_OBJECT_NAMES
        parts = {key: case.bpy.data.objects[names[key]] for key in PART_OBJECT_NAMES}
        references = [
            obj for obj in case.bpy.context.scene.objects
            if obj.name.startswith("REFERENCE_ONLY_")
        ]
        source = str(resolved)
    else:
        case.clear_scene()
        case.set_units()
        material = case.make_material("Bottom_Cable_Check", (0.5, 0.5, 0.5))
        parts = {
            "base": case.create_base(material),
            "fan_case_pair_carrier": case.create_fan_case_pair_overhead_carrier(
                material
            ),
            "fan_case_pair_storage_bin": case.create_fan_case_pair_storage_bin(
                material
            ),
            "fan_case_pair_lid_pad": case.create_fan_case_pair_lid_pad(material),
        }
        references = case.create_fan_case_pair_reference_mockups(*([material] * 7))
        parts["fan_case_pair_insert"] = case.create_fan_case_pair_insert(
            material, references
        )
        source = "fresh"

    assembly_groups = [[
        obj for obj in references
        if obj.name.startswith(
            f"REFERENCE_ONLY_Fan_Case_Assembly_{assembly_index}_"
        )
    ] for assembly_index in range(1, case.FAN_CASE_STORAGE_COUNT + 1)]
    if any(not group for group in assembly_groups):
        raise AssertionError("Focused scene lacks a complete fan-case assembly pair")
    return parts, references, assembly_groups, source


def check_route_geometry_uses_live_notch_offset():
    original_offset = case.wrapping_fan_cover.CABLE_NOTCH_OFFSET
    original_storage = case.FAN_CASE_PAIR_STORAGE
    original_starts = tuple(
        Vector(route[0])
        for options in original_storage["cable_route_options"]
        for route in options
    )
    try:
        case.wrapping_fan_cover.CABLE_NOTCH_OFFSET = -13.25
        case.FAN_CASE_PAIR_STORAGE = case.fan_case_pair_storage_geometry()
        expected_separation = 2.0 * 13.25
        separations = []
        changed_starts = []
        for placement, notch_options, route_options in zip(
            case.FAN_CASE_PAIR_STORAGE["placements"],
            case.FAN_CASE_PAIR_STORAGE["cover_notch_options"],
            case.FAN_CASE_PAIR_STORAGE["cable_route_options"],
        ):
            notch_separation = (
                Vector(notch_options[1]) - Vector(notch_options[0])
            ).length
            route_separation = (
                Vector(route_options[1][0]) - Vector(route_options[0][0])
            ).length
            assert abs(notch_separation - expected_separation) < 1e-5
            assert abs(route_separation - expected_separation) < 1e-5
            for notch, route in zip(notch_options, route_options):
                installed_notch = Vector(notch) + Vector(placement)
                # mathutils.Vector stores float32 values; these installed
                # points are around 70 mm from the origin.
                assert (installed_notch - Vector(route[0])).length < 1e-4
                assert len(route) == 5
                changed_starts.append(Vector(route[0]))
            separations.append(route_separation)
        assert any(
            (before - after).length > 1.0
            for before, after in zip(original_starts, changed_starts)
        ), "Recomputed cable routes ignored the changed live notch offset"
        return min(separations)
    finally:
        case.wrapping_fan_cover.CABLE_NOTCH_OFFSET = original_offset
        case.FAN_CASE_PAIR_STORAGE = original_storage


def check_shared_cable_mouths():
    """Require one printable mouth that fully contains both 8 mm throats."""
    from shapely.geometry import LineString

    radius = case.FAN_CASE_CABLE_THROAT_WIDTH / 2.0
    faceted_minimum_diameter = (
        case.FAN_CASE_CABLE_THROAT_WIDTH * math.cos(math.pi / 48.0)
    )
    minimum_radial_clearance = float("inf")
    for assembly_index, (well_center, routes) in enumerate(zip(
        case.FAN_CASE_CABLE_WELL_CENTERS,
        case.FAN_CASE_PAIR_STORAGE["cable_route_options"],
    ), start=1):
        relief = case.fan_case_cable_relief_region(well_center, routes)
        assert relief.geom_type == "Polygon" and not relief.is_empty, (
            f"Assembly {assembly_index} cable relief is not one connected mouth"
        )
        center_points = []
        for route in routes:
            x, y0, y1 = case.fan_case_cable_throat_bounds(well_center, route)
            centerline = LineString(((x, y0 + radius), (x, y1 - radius)))
            footprint = centerline.buffer(radius, quad_segs=12)
            missing_area = footprint.difference(relief).area
            assert missing_area < 1e-6, (
                f"Assembly {assembly_index} shared mouth clips a corner throat: "
                f"missing_area={missing_area:.9f}"
            )
            clearance = centerline.distance(relief.boundary)
            measured_diameter = 2.0 * clearance
            # A quad_segs=12 circle is a 48-gon: its flat-to-flat width is
            # nominal_diameter*cos(pi/48), while every polygon vertex remains
            # on the nominal 8 mm circle. Require that exact faceted minimum
            # and independently preserve more than 0.5 mm cable clearance per
            # side; finished-mesh collision checks remain exact below.
            assert measured_diameter >= faceted_minimum_diameter - 1e-6, (
                f"Assembly {assembly_index} cable mouth is narrower than its "
                f"faceted 8 mm minimum: diameter={measured_diameter:.6f}"
            )
            assert measured_diameter >= case.FAN_CASE_CABLE_DIAMETER + 1.0, (
                f"Assembly {assembly_index} cable mouth lacks 0.5 mm clearance "
                f"per side: diameter={measured_diameter:.6f}"
            )
            minimum_radial_clearance = min(minimum_radial_clearance, clearance)
            center_points.append((x, (y0 + y1) / 2.0))
        connector = LineString(center_points)
        assert relief.buffer(1e-6).covers(connector), (
            f"Assembly {assembly_index} shared mouth does not join both corners"
        )
    return 2.0 * minimum_radial_clearance


def expect_configuration_failure(message_fragment):
    try:
        case.validate_configuration()
    except ValueError as error:
        assert message_fragment in str(error), (
            f"Unexpected configuration rejection: {error}"
        )
    else:
        raise AssertionError(
            f"Invalid cable configuration was accepted: {message_fragment}"
        )


def check_invalid_notch_offsets():
    original_offset = case.wrapping_fan_cover.CABLE_NOTCH_OFFSET
    original_storage = case.FAN_CASE_PAIR_STORAGE
    try:
        # This check intentionally uses the cached cover envelope: moving the
        # live notch outside that sleeve must fail before geometry is rebuilt.
        case.wrapping_fan_cover.CABLE_NOTCH_OFFSET = (
            original_storage["cover_values"][4] / 2.0
        )
        expect_configuration_failure(
            "Bottom fan cable notch must stay within the sleeve wall"
        )

        # Route distinctness is derived geometry, so recompute it at a nearly
        # centered live notch offset before asking configuration validation.
        case.wrapping_fan_cover.CABLE_NOTCH_OFFSET = 1.0
        case.FAN_CASE_PAIR_STORAGE = case.fan_case_pair_storage_geometry()
        expect_configuration_failure(
            "Both bottom fan-cable corner routes must remain distinct"
        )
    finally:
        case.wrapping_fan_cover.CABLE_NOTCH_OFFSET = original_offset
        case.FAN_CASE_PAIR_STORAGE = original_storage
    case.validate_configuration()


def check_cover_config_restoration():
    original = wrapping_cover_config()
    configured = {
        "CLEAR_SCENE": True,
        "CABLE_NOTCH_SIDE": "RIGHT",
        "CABLE_NOTCH_OFFSET": -11.75,
    }
    restore_wrapping_cover_config(configured)
    real_builder = case.wrapping_fan_cover.build_wrapping_fan_cover
    observed = []

    def capture_real_build():
        observed.append(wrapping_cover_config())
        return real_builder()

    covers = []
    try:
        with patch.object(
            case.wrapping_fan_cover,
            "build_wrapping_fan_cover",
            side_effect=capture_real_build,
        ):
            for assembly_index, corner in ((1, -1), (2, 1)):
                covers.append(
                    case.create_fan_case_storage_cover(assembly_index, corner)
                )
                assert wrapping_cover_config() == configured, (
                    "Successful storage-cover build leaked temporary notch config"
                )
        assert [item["CABLE_NOTCH_OFFSET"] for item in observed] == [-11.75, 11.75]
        assert all(item["CLEAR_SCENE"] is False for item in observed)
        assert all(item["CABLE_NOTCH_SIDE"] == "TOP" for item in observed)

        failure_observation = []

        def fail_during_build():
            failure_observation.append(wrapping_cover_config())
            raise RuntimeError("injected cover failure")

        with patch.object(
            case.wrapping_fan_cover,
            "build_wrapping_fan_cover",
            side_effect=fail_during_build,
        ):
            try:
                case.create_fan_case_storage_cover(1, 1)
            except RuntimeError as error:
                assert str(error) == "injected cover failure"
            else:
                raise AssertionError("Injected wrapping-cover failure was not propagated")
        assert failure_observation == [{
            "CLEAR_SCENE": False,
            "CABLE_NOTCH_SIDE": "TOP",
            "CABLE_NOTCH_OFFSET": 11.75,
        }]
        assert wrapping_cover_config() == configured, (
            "Failed storage-cover build leaked temporary notch config"
        )
    finally:
        for cover in covers:
            remove_object(cover)
        restore_wrapping_cover_config(original)


def check_all_four_routes(parts, references, assembly_groups):
    original = wrapping_cover_config()
    configured = dict(original)
    configured["CLEAR_SCENE"] = True
    configured["CABLE_NOTCH_SIDE"] = "LEFT"
    restore_wrapping_cover_config(configured)
    real_cover_builder = case.create_fan_case_storage_cover
    real_source_builder = case.wrapping_fan_cover.build_wrapping_fan_cover
    cover_calls = []
    source_configs = []

    def capture_cover(assembly_index, corner):
        cover_calls.append((assembly_index, corner))
        return real_cover_builder(assembly_index, corner)

    def capture_source():
        source_configs.append(wrapping_cover_config())
        return real_source_builder()

    try:
        with patch.object(
            case, "create_fan_case_storage_cover", side_effect=capture_cover
        ), patch.object(
            case.wrapping_fan_cover,
            "build_wrapping_fan_cover",
            side_effect=capture_source,
        ):
            maximum_overlap = case.validate_fan_case_bottom_cable_routes(
                parts, references, assembly_groups
            )
        expected_calls = [(1, -1), (1, 1), (2, -1), (2, 1)]
        assert cover_calls == expected_calls, (
            f"Bottom-cable validation did not exercise all four routes: {cover_calls}"
        )
        assert [
            item["CABLE_NOTCH_OFFSET"] for item in source_configs
        ] == [
            corner * abs(configured["CABLE_NOTCH_OFFSET"])
            for _assembly_index, corner in expected_calls
        ]
        assert all(item["CLEAR_SCENE"] is False for item in source_configs)
        assert all(item["CABLE_NOTCH_SIDE"] == "TOP" for item in source_configs)
        assert wrapping_cover_config() == configured
    finally:
        restore_wrapping_cover_config(original)
    return maximum_overlap


def check_alternate_route_obstruction(parts, references, assembly_groups):
    assembly_index = 1
    preview_corner = case.FAN_CASE_CABLE_PREVIEW_CORNERS[assembly_index - 1]
    alternate_corner = -preview_corner
    option_index = 0 if alternate_corner < 0 else 1
    route = case.FAN_CASE_PAIR_STORAGE["cable_route_options"][
        assembly_index - 1
    ][option_index]
    upper, lower = Vector(route[2]), Vector(route[3])
    center = (upper + lower) / 2.0
    blocker = case.add_rounded_box(
        "TEST_Alternate_Only_Bottom_Cable_Obstruction",
        (6.0, 6.0, max(3.0, abs(upper.z - lower.z) / 2.0)),
        center,
        bevel=0.0,
    )
    original_base = parts["base"]
    parts["base"] = blocker
    try:
        try:
            case.validate_fan_case_bottom_cable_routes(
                parts, references, assembly_groups
            )
        except ValueError as error:
            message = str(error)
            expected = (
                "Bottom-corner cable route is obstructed: "
                f"assembly={assembly_index} corner={alternate_corner:+d} "
                f"object={blocker.name}"
            )
            assert expected in message, f"Unexpected cable-route rejection: {message}"
        else:
            raise AssertionError(
                "An obstruction unique to the alternate cable route was accepted"
            )
    finally:
        parts["base"] = original_base
        remove_object(blocker)
    return assembly_index, alternate_corner


def check_bottom_cables(scene_path=None):
    case.validate_configuration()
    live_notch_separation = check_route_geometry_uses_live_notch_offset()
    shared_mouth_diameter = check_shared_cable_mouths()
    check_invalid_notch_offsets()
    check_cover_config_restoration()
    parts, references, assembly_groups, source = load_or_build_loadout(scene_path)
    maximum_overlap = check_all_four_routes(parts, references, assembly_groups)
    blocked_assembly, blocked_corner = check_alternate_route_obstruction(
        parts, references, assembly_groups
    )
    print(
        "FIELD_CASE_BOTTOM_CABLE_REGRESSION_PASS "
        f"source={source} routes=4 overlap_max={maximum_overlap:.6f} "
        f"live_notch_separation={live_notch_separation:.3f} "
        f"shared_mouth_min_diameter={shared_mouth_diameter:.3f} "
        "outside_offset_rejected=True collapsed_pair_rejected=True "
        "config_restore_success=True config_restore_failure=True "
        f"alternate_obstruction_rejected={blocked_assembly}/{blocked_corner:+d}",
        flush=True,
    )


if __name__ == "__main__":
    check_bottom_cables(arguments().scene)
