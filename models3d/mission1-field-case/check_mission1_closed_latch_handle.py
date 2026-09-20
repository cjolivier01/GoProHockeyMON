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
    baseline_gap = case.validate_handle_closed_latch_full_rotation(parts)
    case.validate_built_part('handle_bar', handle)
    case.validate_built_handle_strength(handle)
    assert math.isclose(max(v.co.x for v in handle.data.vertices)
                        - min(v.co.x for v in handle.data.vertices), 119.8, abs_tol=.0001)
    assert math.isclose(baseline_gap, 6.02, abs_tol=.0001)

    def wider_handle(extra_width):
        obj = handle.copy()
        obj.data = handle.data.copy()
        case.bpy.context.collection.objects.link(obj)
        for vertex in obj.data.vertices:
            vertex.co.x += math.copysign(extra_width / 2.0, vertex.co.x)
        obj.data.update()
        return obj

    # A deliberately over-wide full-thickness handle physically intersects
    # the closed lever when rotated upward through -45 degrees.
    old = wider_handle(15.2)
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
        print(f'CLOSED_LATCH_OVERWIDE_HANDLE_REJECTED intersection={overlap:.6f}', flush=True)
    finally:
        case.bpy.data.objects.remove(old, do_unlink=True)

    # Positive clearance is insufficient: 0.98 mm must fail the 1 mm rule.
    marginal = wider_handle(2.0 * (baseline_gap - 0.98))
    try:
        must_reject(lambda: case.validate_handle_closed_latch_full_rotation(
            {**parts, 'handle_bar': marginal}), 'required=1.00')
    finally:
        case.bpy.data.objects.remove(marginal, do_unlink=True)

    # A marginal handle passes if either axial play is ignored, but fails when
    # both allowed movements toward the latch are included.
    marginal = wider_handle(2.0 * (baseline_gap - 0.87))
    for attribute in ('HANDLE_AXIAL_CLEARANCE', 'LATCH_BASE_EAR_AXIAL_CLEARANCE'):
        play = getattr(case, attribute)
        try:
            setattr(case, attribute, 0.0)
            case.validate_handle_closed_latch_full_rotation({**parts, 'handle_bar': marginal})
        finally:
            setattr(case, attribute, play)
    try:
        must_reject(lambda: case.validate_handle_closed_latch_full_rotation(
            {**parts, 'handle_bar': marginal}), 'closed latch moving part')
    finally:
        case.bpy.data.objects.remove(marginal, do_unlink=True)

    # A thin moving part at an arbitrary angle must fail for each latch side
    # and for either moving printed part. No sampled-angle collision loop is used.
    angle = math.radians(-44.37)
    local_y, local_z = -7.0, 9.0 - case.HANDLE_LOCAL_PIVOT_Z
    for latch_x in case.LATCH_X_CENTERS:
        global_x = math.copysign(58.9, latch_x)
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

    # An enclosing moving solid cannot pass just because its surface is far
    # from the handle. Complete axial bounds include the enclosed volume.
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

    # Check the moving metal linkage as well as the printed latch bodies.
    length = case.LATCH_LINK_ROD_LENGTH
    try:
        case.LATCH_LINK_ROD_LENGTH += 20.0
        must_reject(lambda: case.validate_handle_closed_latch_full_rotation(parts), 'part=link rod')
    finally:
        case.LATCH_LINK_ROD_LENGTH = length

    # This constraint expressly excludes protection walls, even a deliberately
    # overlarge one. Independent case-fit checks still validate the usable arc.
    guard = case.add_rounded_box('Regression_Contacting_Protection_Wall', (300, 300, 300),
                                 (0, case.HANDLE_PIVOT_Y, case.HANDLE_PIVOT_Z), bevel=0)
    try:
        case.validate_handle_closed_latch_full_rotation({**parts, 'base': guard})
    finally:
        case.bpy.data.objects.remove(guard, do_unlink=True)
    print('FIELD_CASE_CLOSED_LATCH_FULL_ROTATION_REGRESSION_PASS '
          'overwide_handle=reject thin_parts=reject enclosed_solid=reject '
          'submillimeter_gap=reject minimum_1mm=pass both_axial_plays=covered '
          'long_link_rod=reject guards=excluded', flush=True)


if __name__ == '__main__':
    main()
