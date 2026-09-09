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
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gopro_fan_case_parametric_blender as case


def check_cli():
    configured = (case.FAN_ANGLE_HORIZONTAL_DEG, case.FAN_ANGLE_VERTICAL_DEG)
    case.apply_command_line_arguments([])
    assert (case.FAN_ANGLE_HORIZONTAL_DEG, case.FAN_ANGLE_VERTICAL_DEG) == configured
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
    # Inside fastening supports the same adapter/nut choices at all angles.
    case.REAR_FAN_ADAPTER_SOURCE_CAPTIVE_NUTS_ENABLED = True
    original_flange = case.REAR_FAN_ADAPTER_FLANGE_THICKNESS_Y
    case.REAR_FAN_ADAPTER_FLANGE_THICKNESS_Y = 4.5
    case.validate_config()
    case.REAR_FAN_ADAPTER_FLANGE_THICKNESS_Y = original_flange
    case.REAR_FAN_ADAPTER_SOURCE_CAPTIVE_NUTS_ENABLED = False
    assert not case.BAFFLE_CARTRIDGE_ENABLED
    print("FAN_ANGLE_CLI PASS", flush=True)


def capture_cavity_wall_samples(back):
    """Record material behind the original cavity, away from intentional holes.

    Sample triangle interiors and edge midpoints at two wall depths. Keeping
    these points solid catches a cavity breaking through an otherwise manifold
    shell, including the complete tilted inner mounting face. Samples follow the
    deformation instead of requiring the former inner square to stay fixed.
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
    protected = []
    for original in samples:
        point = case.deform_fan_point(original)
        # The existing three perimeter screws retain straight access while
        # the dome bends. These deliberate cuts are checked separately.
        in_access = False
        if case.CASE_FASTENERS_ENABLED and point.y <= case.BOOLEAN_OVERLAP:
            for x, z in case.CASE_FASTENER_POSITIONS_XZ:
                if case.BACK_FASTENER_HEX_RETENTION_ENABLED:
                    in_access |= case.point_in_polygon_xz((point.x - x, point.z - z), case.back_fastener_hex_loop())
                else:
                    in_access |= math.hypot(point.x - x, point.z - z) < case.BACK_FASTENER_HOLE_DIAMETER / 2.0
        if not in_access:
            protected.append(point)
    missing = [point for point in protected if not case.bvh_point_is_inside(bvh, point)]
    assert not missing, (
        f"Angled dome lost {len(missing)} of {len(samples)} protected cavity-wall samples; "
        f"first={tuple(round(value, 3) for value in missing[0])}"
    )
    print(f"ANGLE_CAVITY_WALLS PASS protected_material_samples={len(protected)}", flush=True)


def check_no_self_intersections(obj):
    """Reject crossings between non-adjacent triangles, using double precision.

    A closed manifold mesh can still fold through itself at a bent camera
    stop. BVH narrows candidate pairs; segment/triangle intersections use strict
    interior coordinates so shared boundaries do not count as crossings.
    """
    def sub(a, b):
        return tuple(x - y for x, y in zip(a, b))

    def cross(a, b):
        return (a[1] * b[2] - a[2] * b[1],
                a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0])

    def dot(a, b):
        return sum(x * y for x, y in zip(a, b))

    def edge_crosses_triangle(triangle, start, end):
        e1, e2, direction = sub(triangle[1], triangle[0]), sub(triangle[2], triangle[0]), sub(end, start)
        h = cross(direction, e2)
        determinant = dot(e1, h)
        if abs(determinant) < 1e-12:
            return False
        relative = sub(start, triangle[0])
        u = dot(relative, h) / determinant
        q = cross(relative, e1)
        v, fraction = dot(direction, q) / determinant, dot(e2, q) / determinant
        if min(u, v, 1.0 - u - v, fraction, 1.0 - fraction) <= 1e-7:
            return False
        normal = cross(e1, e2)
        length = math.sqrt(dot(normal, normal))
        distances = (dot(normal, sub(point, triangle[0])) / length for point in (start, end))
        first, second = distances
        # Vertex coordinates are float32. Ignore only excursions below the
        # same 0.0001 mm tolerance already used for Boolean mesh cleanup.
        return min(abs(first), abs(second)) > case.BOOLEAN_CLEANUP_DISTANCE

    obj.data.calc_loop_triangles()
    vertices = [tuple(vertex.co) for vertex in obj.data.vertices]
    triangles = [tuple(triangle.vertices) for triangle in obj.data.loop_triangles]
    vertex_sets = [set(triangle) for triangle in triangles]
    bvh = BVHTree.FromPolygons(vertices, triangles, all_triangles=True)
    for first, second in bvh.overlap(bvh):
        if first >= second or vertex_sets[first] & vertex_sets[second]:
            continue
        for i, j in ((first, second), (second, first)):
            triangle = [vertices[k] for k in triangles[i]]
            edges = [vertices[k] for k in triangles[j]]
            for k in range(3):
                assert not edge_crosses_triangle(triangle, edges[k], edges[(k + 1) % 3]), (
                    f"Back shell self-intersection between triangles {i} and {j}"
                )
    print("ANGLE_SELF_INTERSECTIONS PASS", flush=True)


def check_assembly(horizontal, vertical, wall_samples=()):
    case.FAN_ANGLE_HORIZONTAL_DEG = horizontal
    case.FAN_ANGLE_VERTICAL_DEG = vertical
    print(f"ANGLE_ASSEMBLY horizontal={horizontal} vertical={vertical}", flush=True)
    back, _insert = case.build_gopro_fan_case()
    assert not any("Baffle" in obj.name for obj in bpy.context.scene.objects)
    bvh = case.mesh_bvh(back)
    # Former top/bottom retaining toes must be absent from the case interior.
    for side in (-1, 1):
        point = (0.0, case.baffle_tpu_back_tab_toe_rear_y() + 0.1,
                 side * (case.baffle_tpu_back_tab_toe_tip_abs_z() + 0.3))
        assert not case.bvh_point_is_inside(bvh, point), "Baffle retaining toe remains"
    check_no_self_intersections(back)
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
        (.01, .01), (1, 0), (0, 1), (15, 0), (30, -20),
        (-45, 0), (45, 0), (0, -45), (0, 45),
        (-45, -45), (-45, 45), (45, -45), (45, 45),
    ):
        adapter = check_assembly(*angles, wall_samples=wall_samples)
    check_export_and_layout(adapter)
    case.LAYOUT_MODE = "assembled"
    case.set_back_material_mode("RIGID")
    # Compare each material against its own straight reference.
    check_assembly(0, 0)
    wall_samples = capture_cavity_wall_samples(bpy.data.objects["GoPro_Fan_Case_Back"])
    check_assembly(-30, 20, wall_samples=wall_samples)
    print("FAN_ANGLE_CHECKS PASS", flush=True)


if __name__ == "__main__":
    main()
