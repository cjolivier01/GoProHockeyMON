"""Exercise fan-angle limits, complete assemblies, and canonical adapter export.

    blender --background --factory-startup --threads 8 --python-exit-code 1 \
        --python models3d/fan-case/check_fan_angles.py
"""

from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import math
import sys
import tempfile

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gopro_fan_case_parametric_blender as case


def check_cli():
    case.apply_command_line_arguments([])
    assert (case.FAN_ANGLE_HORIZONTAL_DEG, case.FAN_ANGLE_VERTICAL_DEG) == (0, 0)
    for option in ("--fan-angle-horizontal", "--fan-angle-vertical"):
        for value in ("-45.01", "45.01", "nan", "inf", "-inf", "nonsense"):
            try:
                with redirect_stderr(StringIO()):
                    case.apply_command_line_arguments([f"{option}={value}"])
            except SystemExit as error:
                assert error.code == 2
            else:
                raise AssertionError(f"Accepted invalid argument: {option}={value}")
    case.apply_command_line_arguments(["--fan-angle-horizontal", "-45", "--fan-angle-vertical", "45"])
    assert (case.FAN_ANGLE_HORIZONTAL_DEG, case.FAN_ANGLE_VERTICAL_DEG) == (-45, 45)
    case.BACK_DOME_ENABLED = False
    try:
        case.validate_config()
    except ValueError as error:
        assert "BACK_DOME_ENABLED" in str(error)
    else:
        raise AssertionError("Accepted nonzero angles without the dome")
    finally:
        case.BACK_DOME_ENABLED = True
    case.REAR_FAN_ADAPTER_SOURCE_CAPTIVE_NUTS_ENABLED = True
    try:
        case.validate_config()
    except ValueError as error:
        assert "SOURCE_CAPTIVE_NUTS_ENABLED=False" in str(error)
    else:
        raise AssertionError("Accepted an inaccessible angled source captive nut")
    finally:
        case.REAR_FAN_ADAPTER_SOURCE_CAPTIVE_NUTS_ENABLED = False
    saved_size, saved_offset = case.REAR_FAN_SIZE_MM, case.REAR_FAN_OFFSET_X_MM
    case.REAR_FAN_SIZE_MM, case.REAR_FAN_OFFSET_X_MM = 40, 0
    try:
        case.validate_config()
    except ValueError as error:
        assert "overlaps target fan hardware" in str(error)
    else:
        raise AssertionError("Accepted source access through the target screw pilots")
    finally:
        case.REAR_FAN_SIZE_MM, case.REAR_FAN_OFFSET_X_MM = saved_size, saved_offset
    saved_flange = case.REAR_FAN_ADAPTER_FLANGE_THICKNESS_Y
    case.REAR_FAN_SIZE_MM, case.REAR_FAN_OFFSET_X_MM = 40, 11
    case.REAR_FAN_ADAPTER_TARGET_CAPTIVE_NUTS_ENABLED = True
    case.REAR_FAN_ADAPTER_FLANGE_THICKNESS_Y = 4.5
    try:
        case.validate_config()
    except ValueError as error:
        assert "captive-nut insertion path" in str(error)
    else:
        raise AssertionError("Accepted a sleeve blocking nut insertion outside the flange")
    finally:
        case.REAR_FAN_SIZE_MM, case.REAR_FAN_OFFSET_X_MM = saved_size, saved_offset
        case.REAR_FAN_ADAPTER_TARGET_CAPTIVE_NUTS_ENABLED = False
        case.REAR_FAN_ADAPTER_FLANGE_THICKNESS_Y = saved_flange
    print("FAN_ANGLE_CLI PASS", flush=True)


def capture_cavity_wall_samples(back):
    """Record material behind the original cavity, away from intentional holes.

    Sample triangle interiors and edge midpoints at two wall depths. Keeping
    these points solid catches a cavity breaking through an otherwise manifold
    shell, including the flat sealing land around the fan opening.
    """
    reference = case.mesh_bvh(back)
    cavity = case.create_back_dome_cavity(case.socket_corner_radius())
    samples = []
    try:
        cavity.data.calc_loop_triangles()
        for triangle in cavity.data.loop_triangles:
            a, b, c = (cavity.data.vertices[index].co for index in triangle.vertices)
            for point in ((a + b + c) / 3.0, (a + b) / 2.0, (b + c) / 2.0, (c + a) / 2.0):
                if point.y >= case.dome_inner_transition_y():
                    continue
                for depth in (0.25, case.BACK_FACE_THICKNESS / 2.0):
                    sample = point + triangle.normal * depth
                    # Avoid points on another surface (groove datums, bore
                    # edges, etc.), whose inside result depends on rounding.
                    nearest = reference.find_nearest(sample)
                    if nearest[3] > 0.05 and case.bvh_point_is_inside(reference, sample):
                        samples.append(sample)
    finally:
        mesh = cavity.data
        bpy.data.objects.remove(cavity, do_unlink=True)
        bpy.data.meshes.remove(mesh)
    assert len(samples) > 1000, "Insufficient protected cavity-wall coverage"
    return samples


def check_cavity_walls(back, samples):
    bvh = case.mesh_bvh(back)
    missing = [point for point in samples if not case.bvh_point_is_inside(bvh, point)]
    assert not missing, (
        f"Angled dome lost {len(missing)} of {len(samples)} protected cavity-wall samples; "
        f"first={tuple(round(value, 3) for value in missing[0])}"
    )
    print(f"ANGLE_CAVITY_WALLS PASS protected_material_samples={len(samples)}", flush=True)


def check_assembly(horizontal, vertical, wall_samples=()):
    case.FAN_ANGLE_HORIZONTAL_DEG = horizontal
    case.FAN_ANGLE_VERTICAL_DEG = vertical
    print(f"ANGLE_ASSEMBLY horizontal={horizontal} vertical={vertical}", flush=True)
    back, _insert = case.build_gopro_fan_case()
    if wall_samples:
        check_cavity_walls(back, wall_samples)
    adapter = bpy.data.objects["GoPro_Fan_Case_Rear_Fan_Adapter"]
    bpy.context.view_layer.update()
    rotation = adapter.matrix_world.to_3x3()
    outward = rotation @ Vector((0, -1, 0))
    assert abs(math.degrees(math.atan2(outward.x, -outward.y)) - horizontal) < 0.001
    assert abs(math.degrees(math.atan2(outward.z, -outward.y)) - vertical) < 0.001
    # EXACT can report a spurious closed volume where these two broad faces
    # coincide. Separate them by 0.01 mm along the measured pad normal for
    # the penetration check, then restore the actual flush placement.
    saved = adapter.matrix_world.copy()
    try:
        adapter.location += outward * 0.01
        bpy.context.view_layer.update()
        intersection = case.mesh_intersection_volume(back, adapter, "Angled_Adapter_Clearance")
    finally:
        adapter.matrix_world = saved
        bpy.context.view_layer.update()
    assert intersection < 0.01, f"Adapter intersects shell by {intersection:.6f} mm3"
    print(f"ANGLE_ADAPTER_CLEARANCE PASS intersection={intersection:.6f}mm3", flush=True)
    return adapter


def check_export_and_layout(adapter):
    saved = adapter.matrix_world.copy()
    with tempfile.TemporaryDirectory(prefix="fan-angle-stl-") as directory:
        output = Path(directory) / "adapter.stl"
        case.export_canonical_rear_fan_adapter_stl(output, adapter)
        assert output.stat().st_size > 84
        assert all(abs(adapter.matrix_world[row][col] - saved[row][col]) < 1e-5
                   for row in range(4) for col in range(4))
        bpy.ops.wm.stl_import(filepath=str(output))
        exported = bpy.context.object
        assert abs(min(vertex.co.z for vertex in exported.data.vertices)) < 0.001
        assert case.world_bed_contact_area(exported) > 100
        case.validate_object(exported)
    case.LAYOUT_MODE = "print_bed"
    case.build_gopro_fan_case()
    adapter = bpy.data.objects["GoPro_Fan_Case_Rear_Fan_Adapter"]
    assert case.world_bed_contact_area(adapter) > 100
    assert abs(min((adapter.matrix_world @ vertex.co).z for vertex in adapter.data.vertices)) < 0.001
    print("FAN_ANGLE_EXPORT_AND_LAYOUT PASS", flush=True)


def main():
    check_cli()
    check_assembly(0, 0)
    wall_samples = capture_cavity_wall_samples(bpy.data.objects["GoPro_Fan_Case_Back"])
    for angles in (
        (1, 0), (0, 1), (30, -20),
        (-45, 0), (45, 0), (0, -45), (0, 45),
        (-45, -45), (-45, 45), (45, -45), (45, 45),
    ):
        adapter = check_assembly(*angles, wall_samples=wall_samples)
    check_export_and_layout(adapter)
    case.LAYOUT_MODE = "assembled"
    case.set_back_material_mode("RIGID")
    case.set_baffle_cartridge_material_mode("RIGID")
    # Rigid and TPU backs have different cartridge-retention details. Compare
    # each angled shell against material from its own straight profile.
    check_assembly(0, 0)
    wall_samples = capture_cavity_wall_samples(bpy.data.objects["GoPro_Fan_Case_Back"])
    check_assembly(-30, 20, wall_samples=wall_samples)
    print("FAN_ANGLE_CHECKS PASS", flush=True)


if __name__ == "__main__":
    main()
