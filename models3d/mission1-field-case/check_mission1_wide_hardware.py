"""Regress wide hardware fit, complete motion envelopes and interior compatibility.

Run in background Blender; uses the focused hardware checks for the complete
latch/handle mechanics. This check also verifies the unchanged compact profile.
"""
import hashlib
import math
import struct
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission1_field_case_blender as case
from check_mission1_field_case_handle import must_reject
from check_mission1_field_case_latch import COMPACT_FIXED_PART_BASELINES


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
    for key, width in (('latch_lever', 40.96), ('latch_hook', 40.96), ('handle_bar', 124.0)):
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

    # Check the original shell volume everywhere except the exterior front
    # hardware attachment strip. This includes the entire interior wall/floor,
    # gasket rim and hinge geometry, not just the outer bounding box.
    source = subprocess.check_output(
        ['git', 'show', '438c924:models3d/mission1-field-case/mission1_field_case_blender.py'],
        cwd=Path(case.__file__).parent, text=True)
    old = {'__name__': 'old_field_case', '__file__': case.__file__}
    exec(compile(source, case.__file__, 'exec'), old)
    old_base = old['create_base'](material)
    for first, second in ((parts['base'], old_base), (old_base, parts['base'])):
        delta = first.copy()
        delta.data = first.data.copy()
        case.bpy.context.collection.objects.link(delta)
        cutter = second.copy()
        cutter.data = second.data.copy()
        case.bpy.context.collection.objects.link(cutter)
        case.difference_from(delta, cutter)
        # Hardware roots reach only 0.8 mm into the exterior wall.
        front = case.add_rounded_box('Remove_Exterior_Hardware', (400, 200, 400),
                                     (0, -case.CASE_DEPTH / 2 - 99, 100), bevel=0)
        case.difference_from(delta, front)
        assert case.mesh_object_volume(delta) < .001, 'Interior or hinge changed'
        case.bpy.data.objects.remove(delta, do_unlink=True)
    print('FIELD_CASE_INTERIOR_COMPATIBLE', flush=True)

    # The compact case has insufficient height for this layout, so keep every
    # printable hardware and shell mesh identical to its previous revision.
    compact = {'__name__': 'compact_width_check', '__file__': case.__file__,
               'EXPANDED_ACCESSORY_STORAGE': False}
    exec(compile(Path(case.__file__).read_bytes(), case.__file__, 'exec'), compact)
    compact['validate_configuration']()
    base = compact['create_base'](material)
    lid, _ = compact['create_lid'](material, material)
    for key, obj in (('base', base), ('lid', lid)):
        count_v, count_p, expected = COMPACT_FIXED_PART_BASELINES[key]
        assert (len(obj.data.vertices), len(obj.data.polygons)) == (count_v, count_p)
        digest = hashlib.sha256()
        for coordinate in sorted(tuple(round(float(x), 5) for x in v.co) for v in obj.data.vertices):
            digest.update(struct.pack('<3q', *(round(x * 100000) for x in coordinate)))
        assert digest.hexdigest() == expected
    assert compact['LATCH_WIDTH'] == 20.48 and compact['HANDLE_WIDTH_INCREASE'] == 0
    old_compact = {'__name__': 'old_compact', '__file__': case.__file__,
                   'EXPANDED_ACCESSORY_STORAGE': False}
    exec(compile(source, case.__file__, 'exec'), old_compact)
    old_hardware = (*old_compact['create_pelican_latch_parts'](material),
                    old_compact['create_pivoting_handle_bar'](material))
    new_hardware = (*compact['create_pelican_latch_parts'](material),
                    compact['create_pivoting_handle_bar'](material))
    for old_part, new_part in zip(old_hardware, new_hardware):
        assert len(old_part.data.vertices) == len(new_part.data.vertices)
        assert canonical_faces(old_part) == canonical_faces(new_part)
        assert tuple(old_part.location) == tuple(new_part.location)
        assert tuple(old_part.rotation_euler) == tuple(new_part.rotation_euler)
    compact['validate_handle_closed_latch_full_rotation']({
        'latch_lever': new_hardware[0], 'latch_hook': new_hardware[1],
        'handle_bar': new_hardware[2]})
    print('FIELD_CASE_WIDE_HARDWARE_REGRESSION_PASS compact_shells_and_hardware=unchanged', flush=True)


if __name__ == '__main__':
    main()
