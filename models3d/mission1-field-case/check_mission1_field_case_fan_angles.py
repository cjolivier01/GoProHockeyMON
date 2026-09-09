"""Check straight/handed storage, source-config restoration, and bad fan poses.

    blender --background --factory-startup --threads 8 --python-exit-code 1 \
        --python models3d/mission1-field-case/check_mission1_field_case_fan_angles.py
"""

from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission1_field_case_blender as case


def configure_yaw(yaw):
    case.FAN_CASE_STORAGE_FAN_YAW_DEGREES = abs(yaw)
    case.FAN_CASE_STORAGE_FAN_ANGLES = ((-abs(yaw), 0.0), (abs(yaw), 0.0))
    case.FAN_CASE_PAIR_STORAGE = case.fan_case_pair_storage_geometry()
    case.FAN_CASE_PAIR_OVERHEAD_STORAGE = case.fan_case_pair_overhead_storage_geometry()
    case.FAN_CASE_PAIR_CARRIER_SUPPORT = case.fan_case_pair_carrier_support_geometry()
    case.FAN_CASE_PAIR_PWM_DOCK_SUPPORT = case.fan_case_pair_pwm_dock_support_geometry()


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


def check_loadout(yaw):
    case.clear_scene()
    original_config = source_config()
    configure_yaw(yaw)
    assert source_config() == original_config
    case.validate_configuration()
    material = case.make_material("Angle_Check", (0.5, 0.5, 0.5))
    parts = {
        "base": case.create_base(material),
        "fan_case_pair_insert": case.create_fan_case_pair_insert(material),
        "fan_case_pair_carrier": case.create_fan_case_pair_overhead_carrier(material),
        "fan_case_pair_storage_bin": case.create_fan_case_pair_storage_bin(material),
        "fan_case_pair_lid_pad": case.create_fan_case_pair_lid_pad(material),
    }
    references = case.create_fan_case_pair_reference_mockups(*([material] * 7))
    assert source_config() == original_config, "Reference build changed source configuration"
    for name, obj in parts.items():
        case.validate_built_part(name, obj)
    case.validate_fan_case_pair_loadout(parts, references)

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

    with patch.object(case.fan_case, "build_gopro_fan_case", side_effect=RuntimeError("test failure")):
        try:
            case.create_fan_case_source_reference_mockups(*([material] * 7), 1)
        except RuntimeError as error:
            assert str(error) == "test failure"
        else:
            raise AssertionError("The injected source-build failure was not propagated")
    assert source_config() == original_config, "Failed source build leaked configuration"
    assert (case.CASE_WIDTH, case.CASE_DEPTH, case.BASE_HEIGHT) == (234.0, 158.0, 97.8)
    print(f"FIELD_CASE_FAN_ANGLE_REGRESSION_PASS yaw={yaw:g} bad_pose_rejected=True "
          "blocked_door_lift_rejected=True source_config_restored=True", flush=True)


if __name__ == "__main__":
    for angle in ((0.0, 15.0) if hasattr(case.fan_case, "fan_mount_transform") else (0.0,)):
        check_loadout(angle)
