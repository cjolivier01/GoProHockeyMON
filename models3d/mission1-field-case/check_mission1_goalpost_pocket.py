"""Check the loose asymmetric mount pocket and reject a generic/reversed fit.

Run in background Blender. Dimensions are estimated from the ruler photograph;
this checks the modeled clearance, not physical fit to an unmeasured mount.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission1_field_case_blender as case
from check_mission1_domed_lid import must_reject


def main():
    case.clear_scene()
    case.set_units()
    material = case.make_material('Mount_Pocket_Check', (.4,.4,.4))
    tray = case.create_fan_case_pair_overhead_carrier(material)
    parts = {'fan_case_pair_carrier': tray}
    case.validate_built_part('fan_case_pair_carrier', tray)
    case.validate_goalpost_mount_pocket(parts)
    minimum, maximum = case.object_world_bounds(tray)
    bounds = case.FAN_CASE_PAIR_OVERHEAD_STORAGE['carrier_bounds']
    for axis in range(3):
        assert abs(minimum[axis]-bounds[axis*2]) < 1e-4
        assert abs(maximum[axis]-bounds[axis*2+1]) < 1e-4
    plain = case.create_fan_case_pair_standalone_tray(material, 'carrier_bounds',
                                                   'REGRESSION_Unshaped_Mount_Tray')
    must_reject(lambda: case.validate_goalpost_mount_pocket(
        {'fan_case_pair_carrier': plain}), 'incorrect 180-degree orientation')
    # Add material into the reserved camera-attachment lobe, leaving the tray
    # and its other compartments intact. Nominal loading must now fail.
    floor = bounds[4]+case.FAN_CASE_PAIR_STORAGE_BIN_FLOOR
    block = case.add_rounded_box('REGRESSION_Blocked_Camera_Attachment',
        (16,16,10), (0,-55,floor+5), bevel=0)
    case.union_into(tray, block)
    must_reject(lambda: case.validate_goalpost_mount_pocket(parts),
                'clearance outline is obstructed')
    print('FIELD_CASE_GOALPOST_POCKET_REGRESSION_PASS', flush=True)


if __name__ == '__main__':
    main()
