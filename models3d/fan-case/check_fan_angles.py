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
    for coordinates in case.deform_fan_points(samples):
        point = Vector(coordinates)
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


def check_compact_pad(back):
    """Measure the pad pose without using the model's transform or deformation.

    Bore-wall raycasts locate the four actual hole centers. Together with the
    measured outer face, they locate the mounting square and its hinge depth;
    an oversized or sideways-shifted pad cannot pass by moving its own probes.
    """
    tolerance = 0.002
    outward = Vector((
        math.tan(math.radians(case.FAN_ANGLE_HORIZONTAL_DEG)), -1.0,
        math.tan(math.radians(case.FAN_ANGLE_VERTICAL_DEG)),
    )).normalized()
    # Closed-form shortest-arc axes, independent of fan_mount_transform().
    denominator = 1.0 - outward.y
    cross_term = -outward.x * outward.z / denominator
    axis_x = Vector((1.0 - outward.x ** 2 / denominator, outward.x, cross_term))
    axis_z = Vector((cross_term, outward.z, 1.0 - outward.z ** 2 / denominator))
    half_width = case.BACK_DOME_FAN_PAD_WIDTH / 2.0
    half_height = case.BACK_DOME_FAN_PAD_HEIGHT / 2.0
    shift = abs(outward.x) * half_width + abs(outward.z) * half_height
    original_y = -case.BACK_DOME_DEPTH if case.BACK_DOME_ENABLED else 0.0
    expected_center = Vector((case.FAN_CENTER_X, original_y - shift, case.FAN_CENTER_Z))
    bvh = case.mesh_bvh(back)
    face_normals = []
    for x_sign in (-1, 1):
        for z_sign in (-1, 1):
            expected = (expected_center + axis_x * x_sign * (half_width - 1.0)
                        + axis_z * z_sign * (half_height - 1.0))
            hit, normal, _face, _distance = bvh.ray_cast(expected + outward, -outward, 2.0)
            assert hit is not None and (hit - expected).length < tolerance, (
                f"Compact mounting face is missing or displaced at corner {x_sign}, {z_sign}"
            )
            assert normal.dot(outward) > 0.99999, "Compact mounting face has the wrong normal"
            face_normals.append(normal)
    measured_normal = sum(face_normals, Vector()).normalized()

    bore_centers = {}
    half_thickness = case.BACK_FACE_THICKNESS / 2.0
    radius = case.FAN_HOLE_DIAMETER / 2.0
    for x_sign in (-1, 1):
        for z_sign in (-1, 1):
            origin = (expected_center - outward * half_thickness
                      + axis_x * x_sign * case.FAN_HOLE_SPACING_X / 2.0
                      + axis_z * z_sign * case.FAN_HOLE_SPACING_Z / 2.0)
            measured = origin.copy()
            for axis in (axis_x, axis_z):
                distances = []
                for sign in (1, -1):
                    hit, _normal, _face, distance = bvh.ray_cast(origin, axis * sign, radius * 2.0)
                    if hit is None:
                        # At tiny angles a ray can fall exactly between the
                        # triangles meeting at an axial subdivision. Require
                        # matching wall witnesses on both sides of that seam;
                        # the bore radius/position tolerance stays unchanged.
                        adjacent = [bvh.ray_cast(origin + outward * offset,
                                                 axis * sign, radius * 2.0)
                                    for offset in (-0.013, 0.013)]
                        assert all(sample[0] is not None
                                   and abs(sample[3] - radius) < tolerance
                                   for sample in adjacent), (
                            f"Compact pad bore {x_sign}, {z_sign} has no matching walls beside its middle seam"
                        )
                        hit = adjacent[0][0]
                        distance = sum(sample[3] for sample in adjacent) / len(adjacent)
                    assert hit is not None and abs(distance - radius) < tolerance, (
                        f"Compact pad bore {x_sign}, {z_sign} is displaced or resized"
                    )
                    distances.append(distance)
                measured += axis * (distances[0] - distances[1]) / 2.0
            bore_centers[x_sign, z_sign] = measured
    center = sum(bore_centers.values(), Vector()) / 4.0 + measured_normal * half_thickness
    assert (center - expected_center).length < tolerance, (
        f"Pad center drifted: measured={tuple(center)}, expected={tuple(expected_center)}"
    )
    measured_x = sum((bore_centers[1, z] - bore_centers[-1, z] for z in (-1, 1)), Vector()) / (2.0 * case.FAN_HOLE_SPACING_X)
    measured_z = sum((bore_centers[x, 1] - bore_centers[x, -1] for x in (-1, 1)), Vector()) / (2.0 * case.FAN_HOLE_SPACING_Z)
    assert (measured_x - axis_x).length < 0.0001 and (measured_z - axis_z).length < 0.0001, (
        "Mounting square has added roll or changed screw spacing"
    )
    corners = [center + measured_x * x * half_width + measured_z * z * half_height
               for x in (-1, 1) for z in (-1, 1)]
    for corner in corners:
        assert bvh.find_nearest(corner)[3] < tolerance, "Measured mounting-square corner is absent"
    assert abs(max(point.y for point in corners) - original_y) < tolerance, "Pad hinge moved from its original depth"
    assert abs(min(point.y for point in corners) - (original_y - 2.0 * shift)) < tolerance, "Pad exceeds its compact depth budget"
    print(f"ANGLE_COMPACT_PAD PASS center={tuple(round(value, 4) for value in center)} "
          f"hinge_y={original_y:.4f} rear_corner_y={original_y - 2.0 * shift:.4f}", flush=True)


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
    # Boolean polygon tessellation can produce facets whose shortest altitude
    # is below the mesh cleanup distance. Their float32 coordinates cannot
    # define a stable plane for proving a crossing. Exclude only those facets;
    # the ordinary intersection tolerance above remains unchanged.
    def has_stable_plane(indices):
        a, b, c = (vertices[index] for index in indices)
        edges = (sub(b, a), sub(c, b), sub(a, c))
        normal = cross(edges[0], sub(c, a))
        longest_edge_squared = max(dot(edge, edge) for edge in edges)
        return dot(normal, normal) > case.BOOLEAN_CLEANUP_DISTANCE ** 2 * longest_edge_squared

    triangles = [triangle for triangle in triangles if has_stable_plane(triangle)]
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
    check_compact_pad(back)
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
