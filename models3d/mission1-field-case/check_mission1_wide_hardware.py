"""Regress wide hardware fit, complete motion envelopes and interior compatibility.

Run in background Blender; uses the focused hardware checks for the complete
latch/handle mechanics. This check also verifies the unchanged compact profile.
"""
import math
from pathlib import Path
import subprocess
import sys

from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission1_field_case_blender as case
from check_mission1_field_case_handle import must_reject


# The merged rounded-shell design is the compatibility baseline for this PR.
BASELINE_REVISION = "e1e8d596f6d496957e9bcc17d8d6893bc4d61105"


def canonical_faces(obj):
    """Compare geometry without depending on Boolean vertex allocation order."""
    coordinates = [tuple(round(float(x), 5) for x in vertex.co)
                   for vertex in obj.data.vertices]
    return sorted(tuple(sorted(coordinates[i] for i in polygon.vertices))
                  for polygon in obj.data.polygons)


def main():
    case.clear_scene()
    case.set_units()
    material = case.make_material('Width_Check', (.4, .4, .4))
    parts = {'base': case.create_base(material)}
    parts['lid'], _ = case.create_lid(material, material)
    parts['latch_lever'], parts['latch_hook'] = case.create_pelican_latch_parts(material)
    parts['handle_bar'] = case.create_pivoting_handle_bar(material)
    assert (case.CASE_WIDTH, case.CASE_DEPTH, case.BASE_HEIGHT,
            case.WALL_THICKNESS, case.BASE_FLOOR_THICKNESS) == (234, 180, 160, 4.5, 3.2)
    for key, width in (('latch_lever', 40.96), ('latch_hook', 40.96), ('handle_bar', 119.8)):
        coordinates = [v.co.x for v in parts[key].data.vertices]
        assert math.isclose(max(coordinates) - min(coordinates), width, abs_tol=.0001)
    case.validate_wide_hardware_clearance(parts)
    # Catch a local protrusion even when all configured dimensions still pass.
    obstructed = parts['handle_bar'].copy()
    obstructed.data = parts['handle_bar'].data.copy()
    case.bpy.context.collection.objects.link(obstructed)
    obstructed.location = (0, 0, 0)
    tab = case.add_rounded_box('Regression_Handle_Protrusion', (5, 5, 6),
                              (0, -32, 20.5), bevel=0)
    case.union_into(obstructed, tab)
    try:
        must_reject(lambda: case.validate_wide_hardware_clearance(
            {**parts, 'handle_bar': obstructed}), 'vertical clearance')
    finally:
        case.bpy.data.objects.remove(obstructed, do_unlink=True)
    height = case.HANDLE_PIVOT_Z
    try:
        case.HANDLE_PIVOT_Z += 5
        must_reject(lambda: case.validate_wide_hardware_clearance(parts), 'vertical clearance')
    finally:
        case.HANDLE_PIVOT_Z = height
    bolt = case.LATCH_FIXED_M3_BOLT_LENGTH
    try:
        case.LATCH_FIXED_M3_BOLT_LENGTH = 30
        must_reject(case.validate_configuration, 'fully engage')
    finally:
        case.LATCH_FIXED_M3_BOLT_LENGTH = bolt

    # Check the rounded-shell baseline everywhere except the exterior front
    # hardware attachment strip. This includes the entire interior wall/floor,
    # gasket rim and hinge geometry, not just the outer bounding box.
    source = subprocess.check_output(
        ['git', 'show', f'{BASELINE_REVISION}:models3d/mission1-field-case/mission1_field_case_blender.py'],
        cwd=Path(case.__file__).parent, text=True)
    old = {'__name__': 'old_field_case', '__file__': case.__file__}
    exec(compile(source, case.__file__, 'exec'), old)
    # Compare complete fork solids after translation, including the formerly
    # relieved outboard corners. Only the central grip span may grow.
    old_handle = old['create_pivoting_handle_bar'](material)

    def fork_copy(source, side, shift):
        obj = source.copy()
        obj.data = source.data.copy()
        case.bpy.context.collection.objects.link(obj)
        obj.location = (0, 0, 0)
        obj.rotation_euler = (0, 0, 0)
        for vertex in obj.data.vertices:
            vertex.co.x += side * shift
        obj.data.update()
        grip = case.add_rounded_box('Remove_Grip', (500, 200, 200),
                                     (0, -124, 0), bevel=0)
        case.difference_from(obj, grip)
        opposite = case.add_rounded_box('Remove_Opposite_Fork', (200, 200, 200),
                                         (-side * 100, 0, 0), bevel=0)
        case.difference_from(obj, opposite)
        return obj

    for side in (-1, 1):
        original = fork_copy(old_handle, side, case.HANDLE_WIDTH_INCREASE / 2)
        current = fork_copy(parts['handle_bar'], side, 0)
        # Match vertices and face connectivity directly: subtracting nearly
        # coincident Boolean surfaces is unstable at float mesh precision.
        assert len(original.data.vertices) == len(current.data.vertices)
        tree = KDTree(len(original.data.vertices))
        for vertex in original.data.vertices:
            tree.insert(vertex.co, vertex.index)
        tree.balance()
        mapping = {}
        for vertex in current.data.vertices:
            _, index, distance = tree.find(vertex.co)
            assert distance < .0001, 'Fork vertex changed'
            mapping[vertex.index] = index
        assert len(set(mapping.values())) == len(mapping), 'Fork vertices collapsed'
        original_faces = sorted(tuple(sorted(p.vertices)) for p in original.data.polygons)
        current_faces = sorted(tuple(sorted(mapping[i] for i in p.vertices))
                               for p in current.data.polygons)
        assert original_faces == current_faces, 'Fork faces changed'
        for obj in (original, current):
            case.bpy.data.objects.remove(obj, do_unlink=True)
    case.bpy.data.objects.remove(old_handle, do_unlink=True)
    print('FIELD_CASE_HANDLE_FORKS_UNCHANGED translations=+/-10.3mm', flush=True)

    old_base = old['create_base'](material)
    # The outer mounts follow the rounded wall, so the excluded attachment
    # strip must follow that same cavity boundary. Leave a 0.2 mm exterior-side
    # margin before the nominal inner face and require every other base feature,
    # including the hinges, to match.
    for first, second in ((parts['base'], old_base), (old_base, parts['base'])):
        delta = first.copy()
        delta.data = first.data.copy()
        case.bpy.context.collection.objects.link(delta)
        cutter = second.copy()
        cutter.data = second.data.copy()
        case.bpy.context.collection.objects.link(cutter)
        case.difference_from(delta, cutter)
        front = case.add_rounded_box(
            'Remove_Exterior_Hardware', (400, 400, 400),
            (0, -200, 100), bevel=0,
        )
        cavity_margin = 0.2
        cavity_keepout = case.add_rounded_prism(
            'Preserve_Rounded_Cavity',
            case.CASE_WIDTH - 2 * case.WALL_THICKNESS + 2 * cavity_margin,
            case.CASE_DEPTH - 2 * case.WALL_THICKNESS + 2 * cavity_margin,
            -100, 300,
            case.CASE_CORNER_RADIUS - case.WALL_THICKNESS + cavity_margin,
        )
        case.difference_from(front, cavity_keepout)
        case.difference_from(delta, front)
        assert case.mesh_object_volume(delta) < .001, 'Interior or hinge changed'
        case.bpy.data.objects.remove(delta, do_unlink=True)
    print('FIELD_CASE_INTERIOR_COMPATIBLE', flush=True)

    # The compact case has insufficient height for this layout, so keep every
    # printable hardware and shell mesh identical to the rounded-shell baseline.
    compact = {'__name__': 'compact_width_check', '__file__': case.__file__,
               'EXPANDED_ACCESSORY_STORAGE': False}
    exec(compile(Path(case.__file__).read_bytes(), case.__file__, 'exec'), compact)
    compact['validate_configuration']()
    assert compact['LATCH_WIDTH'] == 20.48 and compact['HANDLE_WIDTH_INCREASE'] == 0
    baseline_compact = {'__name__': 'baseline_compact', '__file__': case.__file__,
                        'EXPANDED_ACCESSORY_STORAGE': False}
    exec(compile(source, case.__file__, 'exec'), baseline_compact)
    baseline_compact['validate_configuration']()
    baseline_lid, _ = baseline_compact['create_lid'](material, material)
    current_lid, _ = compact['create_lid'](material, material)
    baseline_parts = (
        baseline_compact['create_base'](material), baseline_lid,
        *baseline_compact['create_pelican_latch_parts'](material),
        baseline_compact['create_pivoting_handle_bar'](material),
    )
    current_parts = (
        compact['create_base'](material), current_lid,
        *compact['create_pelican_latch_parts'](material),
        compact['create_pivoting_handle_bar'](material),
    )
    for baseline_part, current_part in zip(baseline_parts, current_parts):
        assert len(baseline_part.data.vertices) == len(current_part.data.vertices)
        assert canonical_faces(baseline_part) == canonical_faces(current_part)
        assert tuple(baseline_part.location) == tuple(current_part.location)
        assert tuple(baseline_part.rotation_euler) == tuple(current_part.rotation_euler)
    compact['validate_handle_closed_latch_full_rotation']({
        'latch_lever': current_parts[2], 'latch_hook': current_parts[3],
        'handle_bar': current_parts[4]})
    print('FIELD_CASE_WIDE_HARDWARE_REGRESSION_PASS compact_shells_and_hardware=unchanged', flush=True)


if __name__ == '__main__':
    main()
