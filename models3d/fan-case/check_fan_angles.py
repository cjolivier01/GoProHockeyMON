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
    print("FAN_ANGLE_CLI PASS", flush=True)


def check_assembly(horizontal, vertical):
    case.FAN_ANGLE_HORIZONTAL_DEG = horizontal
    case.FAN_ANGLE_VERTICAL_DEG = vertical
    print(f"ANGLE_ASSEMBLY horizontal={horizontal} vertical={vertical}", flush=True)
    back, _insert = case.build_gopro_fan_case()
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
    for angles in (
        (0, 0), (1, 0), (0, 1), (30, -20),
        (-45, 0), (45, 0), (0, -45), (0, 45),
        (-45, -45), (-45, 45), (45, -45), (45, 45),
    ):
        adapter = check_assembly(*angles)
    check_export_and_layout(adapter)
    case.LAYOUT_MODE = "assembled"
    case.set_back_material_mode("RIGID")
    case.set_baffle_cartridge_material_mode("RIGID")
    check_assembly(-30, 20)
    print("FAN_ANGLE_CHECKS PASS", flush=True)


if __name__ == "__main__":
    main()
