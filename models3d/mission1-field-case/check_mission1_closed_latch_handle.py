"""Prove full-turn closed-latch clearance and reject real contact regressions.

    blender --background --factory-startup --threads 8 --python-exit-code 1 \
      --python models3d/mission1-field-case/check_mission1_closed_latch_handle.py
"""
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission1_field_case_blender as case
from check_mission1_field_case_handle import must_reject


def main():
    case.clear_scene()
    case.set_units()
    material = case.make_material('Closed_Latch_Clearance_Check', (.4, .4, .4))
    lever, hook = case.create_pelican_latch_parts(material)
    handle = case.create_pivoting_handle_bar(material)
    parts = {'latch_lever': lever, 'latch_hook': hook, 'handle_bar': handle}
    case.validate_handle_closed_latch_full_rotation(parts)
    case.validate_built_part('handle_bar', handle)
    case.validate_built_handle_strength(handle)
    assert math.isclose(max(v.co.x for v in handle.data.vertices)
                        - min(v.co.x for v in handle.data.vertices), 124.0, abs_tol=.0001)

    # The former fork passed the normal 0-90 degree check but physically
    # intersected the closed lever when rotated upward through -45 degrees.
    taper = case.HANDLE_OUTER_FORK_TAPER_START
    taper_end = case.HANDLE_OUTER_FORK_TAPER_END
    try:
        case.HANDLE_OUTER_FORK_TAPER_START = 18.0
        case.HANDLE_OUTER_FORK_TAPER_END = 24.0
        old = case.create_pivoting_handle_bar(material)
    finally:
        case.HANDLE_OUTER_FORK_TAPER_START = taper
        case.HANDLE_OUTER_FORK_TAPER_END = taper_end
    try:
        old_parts = {**parts, 'handle_bar': old}
        case.validate_wide_hardware_clearance(old_parts)
        must_reject(lambda: case.validate_handle_closed_latch_full_rotation(old_parts),
                    'closed latch moving part')
        angle = math.radians(-45.0)
        _, overlap = case.exact_transformed_intersection(
            lever, old,
            first_location=(case.LATCH_X_CENTERS[1] - case.LATCH_BASE_EAR_AXIAL_CLEARANCE,
                            case.LATCH_BASE_PIVOT_Y, case.LATCH_BASE_PIVOT_Z),
            first_rotation=(math.radians(case.LATCH_LEVER_CLOSED_ANGLE), 0, 0),
            second_location=(0, case.HANDLE_PIVOT_Y + math.sin(angle) * case.HANDLE_LOCAL_PIVOT_Z,
                             case.HANDLE_PIVOT_Z - math.cos(angle) * case.HANDLE_LOCAL_PIVOT_Z),
            second_rotation=(angle, 0, 0))
        assert overlap > 1.0, overlap
        print(f'CLOSED_LATCH_PREVIOUS_FORK_REJECTED intersection={overlap:.6f}', flush=True)
    finally:
        case.bpy.data.objects.remove(old, do_unlink=True)

    # This intermediate shape clears at centered handle X, but loses the
    # guarantee at the permitted end of its 0.4 mm axial travel.
    try:
        case.HANDLE_OUTER_FORK_TAPER_END = 24.0
        marginal = case.create_pivoting_handle_bar(material)
    finally:
        case.HANDLE_OUTER_FORK_TAPER_END = taper_end
    axial_play = case.HANDLE_AXIAL_CLEARANCE
    try:
        case.HANDLE_AXIAL_CLEARANCE = 0.0
        case.validate_handle_closed_latch_full_rotation({**parts, 'handle_bar': marginal})
        case.HANDLE_AXIAL_CLEARANCE = axial_play
        must_reject(lambda: case.validate_handle_closed_latch_full_rotation(
            {**parts, 'handle_bar': marginal}), 'closed latch moving part')
    finally:
        case.HANDLE_AXIAL_CLEARANCE = axial_play
        case.bpy.data.objects.remove(marginal, do_unlink=True)

    # A thin moving part at an arbitrary angle must fail for each latch side
    # and for either moving printed part. No sampled-angle collision loop is used.
    angle = math.radians(-44.37)
    local_y, local_z = -7.0, 9.0 - case.HANDLE_LOCAL_PIVOT_Z
    for latch_x in case.LATCH_X_CENTERS:
        global_x = math.copysign(61.0, latch_x)
        global_y = case.HANDLE_PIVOT_Y + math.cos(angle) * local_y - math.sin(angle) * local_z
        global_z = case.HANDLE_PIVOT_Z + math.sin(angle) * local_y + math.cos(angle) * local_z
        for key in ('latch_lever', 'latch_hook'):
            if key == 'latch_lever':
                py, pz = case.LATCH_BASE_PIVOT_Y, case.LATCH_BASE_PIVOT_Z
                radians = math.radians(case.LATCH_LEVER_CLOSED_ANGLE)
            else:
                py, pz = case.latch_hook_origin_yz(case.LATCH_LEVER_CLOSED_ANGLE)
                radians = math.radians(case.latch_hook_global_angle_degrees(case.LATCH_LEVER_CLOSED_ANGLE))
            dy, dz = global_y - py, global_z - pz
            center = (global_x - latch_x,
                      math.cos(radians) * dy + math.sin(radians) * dz,
                      -math.sin(radians) * dy + math.cos(radians) * dz)
            obstruction = case.add_rounded_box('Regression_Thin_Moving_Part', (.1, .1, .1), center, bevel=0)
            case.select_only(obstruction)
            case.bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
            try:
                _, overlap = case.exact_transformed_intersection(
                    obstruction, handle,
                    first_location=(latch_x, py, pz), first_rotation=(radians, 0, 0),
                    second_location=(0, case.HANDLE_PIVOT_Y + math.sin(angle) * case.HANDLE_LOCAL_PIVOT_Z,
                                     case.HANDLE_PIVOT_Z - math.cos(angle) * case.HANDLE_LOCAL_PIVOT_Z),
                    second_rotation=(angle, 0, 0))
                assert overlap > .0005, (latch_x, key, overlap)
                must_reject(lambda: case.validate_handle_closed_latch_full_rotation(
                    {**parts, key: obstruction}), 'closed latch moving part')
            finally:
                case.bpy.data.objects.remove(obstruction, do_unlink=True)

    # A solid enclosing the pivot must fail even if its side faces are far
    # from the handle: the minimum-radius proof must include its end caps.
    enclosing = case.add_rounded_box('Regression_Enclosing_Latch', (600, 200, 200),
        (0, case.HANDLE_PIVOT_Y - case.LATCH_BASE_PIVOT_Y,
         case.HANDLE_PIVOT_Z - case.LATCH_BASE_PIVOT_Z), bevel=0)
    case.select_only(enclosing)
    case.bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    try:
        must_reject(lambda: case.validate_handle_closed_latch_full_rotation(
            {**parts, 'latch_lever': enclosing}), 'closed latch moving part')
    finally:
        case.bpy.data.objects.remove(enclosing, do_unlink=True)

    # Exact tangency has zero intersection volume, but must still fail. A
    # rotating square reaches sqrt(2) radius and touches the middle of a flat
    # latch face; testing only polygon vertices would miss this contact.
    square = case.add_rounded_box('Regression_Rotating_Square', (2, 2, 2),
                                   (82, 0, case.HANDLE_LOCAL_PIVOT_Z), bevel=0)
    case.select_only(square)
    case.bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    radians = math.radians(case.LATCH_LEVER_CLOSED_ANGLE)
    try:
        for gap in (0.0, 0.02):
            dy = case.HANDLE_PIVOT_Y + math.sqrt(2) + 1 + gap - case.LATCH_BASE_PIVOT_Y
            dz = case.HANDLE_PIVOT_Z - case.LATCH_BASE_PIVOT_Z
            face = case.add_rounded_box('Regression_Tangent_Latch_Face', (2, 2, 2),
                (0, math.cos(radians) * dy + math.sin(radians) * dz,
                 -math.sin(radians) * dy + math.cos(radians) * dz), bevel=0)
            face.rotation_euler.x = -radians
            case.select_only(face)
            case.bpy.ops.object.transform_apply(location=True, rotation=True, scale=False)
            fixture = {**parts, 'handle_bar': square, 'latch_lever': face}
            try:
                if gap == 0.0:
                    must_reject(lambda: case.validate_handle_closed_latch_full_rotation(fixture),
                                'closed latch moving part')
                else:
                    case.validate_handle_closed_latch_full_rotation(fixture)
            finally:
                case.bpy.data.objects.remove(face, do_unlink=True)
    finally:
        case.bpy.data.objects.remove(square, do_unlink=True)

    diameter = case.LATCH_LINK_ROD_DIAMETER
    try:
        case.LATCH_LINK_ROD_DIAMETER = 100.0
        must_reject(lambda: case.validate_handle_closed_latch_full_rotation(parts), 'part=link rod')
    finally:
        case.LATCH_LINK_ROD_DIAMETER = diameter

    # This constraint expressly excludes protection walls, even a deliberately
    # overlarge one. Independent case-fit checks still validate the usable arc.
    guard = case.add_rounded_box('Regression_Contacting_Protection_Wall', (300, 300, 300),
                                 (0, case.HANDLE_PIVOT_Y, case.HANDLE_PIVOT_Z), bevel=0)
    try:
        case.validate_handle_closed_latch_full_rotation({**parts, 'base': guard})
    finally:
        case.bpy.data.objects.remove(guard, do_unlink=True)
    print('FIELD_CASE_CLOSED_LATCH_FULL_ROTATION_REGRESSION_PASS '
          'old_fork=reject thin_parts=reject enclosed_solid=reject tangency=reject '
          'clear_gap=pass axial_play=covered link_rod=reject guards=excluded', flush=True)


if __name__ == '__main__':
    main()
