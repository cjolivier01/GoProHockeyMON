"""Regress the raised roof, preserved packing plane, and limited support demand.

Run in background Blender. Optional -- --scene /path/to/validated-case.blend
reuses a complete source-built scene. The full export build checks all lower
inserts and both lid variants' complete installed closing paths separately.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission1_field_case_blender as case
from check_mission1_field_case_latch import validate_fixed_part_compatibility


def must_reject(action, expected):
    try:
        action()
    except ValueError as error:
        assert expected in str(error), str(error)
        print('DOMED_LID_REGRESSION_REJECTED', error, flush=True)
    else:
        raise AssertionError(f'Regression accepted: {expected}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scene', type=Path)
    parser.add_argument('--project', type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    if args.scene:
        case.bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
        names = json.loads(case.bpy.context.scene['cached_field_case_parts'])
        parts = {key: case.bpy.data.objects[name] for key, name in names.items()}
    else:
        case.clear_scene()
        case.set_units()
        material = case.make_material('Dome_Check', (.4, .4, .4))
        parts = {'base': case.create_base(material)}
        for key, profile in (('lid', case.HINGE_PROFILE_RIGID_SLIDE),
                             ('tpu_snap_lid', case.HINGE_PROFILE_TPU_68D_SNAP)):
            parts[key], _ = case.create_lid(material, material, profile)
        parts['fan_case_pair_lid_pad'] = case.create_fan_case_pair_lid_pad(material)
    assert (case.CASE_WIDTH, case.CASE_DEPTH, case.BASE_HEIGHT,
            case.WALL_THICKNESS, case.BASE_FLOOR_THICKNESS) == (234, 180, 160, 4.5, 3.2)
    validate_fixed_part_compatibility('base', parts['base'])
    case.validate_built_domed_lid(parts)
    for key in ('lid', 'tpu_snap_lid', 'fan_case_pair_lid_pad'):
        case.validate_built_part(key, parts[key])

    def copy_part(key):
        obj = parts[key].copy()
        obj.data = parts[key].data.copy()
        case.bpy.context.collection.objects.link(obj)
        return obj

    for key in ('lid', 'tpu_snap_lid'):
        invalid = copy_part(key)
        for vertex in invalid.data.vertices:
            if vertex.co.z < 0:
                vertex.co.z = 0
        invalid.data.update()
        try:
            must_reject(lambda: case.validate_built_domed_lid(
                {**parts, key: invalid}), 'flat or incorrectly curved crown')
        finally:
            case.bpy.data.objects.remove(invalid, do_unlink=True)
        invalid = copy_part(key)
        block = case.add_rounded_box('REGRESSION_Unsupported_Wide_Fin', (2,180,30),
            (case.LID_DISPLAY_OFFSET_X+130,0,15), bevel=0)
        case.union_into(invalid, block)
        try:
            must_reject(lambda: case.validate_built_domed_lid(
                {**parts, key: invalid}), 'tilted support area budget')
        finally:
            case.bpy.data.objects.remove(invalid, do_unlink=True)

    pad_key = 'fan_case_pair_lid_pad'
    for low_face, expected in ((True, 'original packing height'),
                               (False, 'does not reach the roof')):
        invalid = copy_part(pad_key)
        for vertex in invalid.data.vertices:
            if (abs(vertex.co.z) < 1e-5 if low_face else vertex.co.z > 25):
                vertex.co.z -= 1
        invalid.data.update()
        try:
            must_reject(lambda: case.validate_built_domed_lid(
                {**parts, pad_key: invalid}), expected)
        finally:
            case.bpy.data.objects.remove(invalid, do_unlink=True)

    invalid = copy_part(pad_key)
    cutter = case.add_rounded_box('REGRESSION_Missing_Spacer_Rim', (200, 8, 30),
        (case.LID_DISPLAY_OFFSET_X,
         case.FAN_CASE_PAIR_LID_PAD_DISPLAY_Y + case.LID_DOME_PAD_FRAME_SIZE[1] / 2,
         19), bevel=0)
    case.difference_from(invalid, cutter)
    try:
        must_reject(lambda: case.validate_built_domed_lid(
            {**parts, pad_key: invalid}), 'does not follow the curved roof')
    finally:
        case.bpy.data.objects.remove(invalid, do_unlink=True)
    invalid = copy_part(pad_key)
    cutter = case.add_rounded_box('REGRESSION_Missing_Spacer_Rib', (100, 8, 30),
        (case.LID_DISPLAY_OFFSET_X, case.FAN_CASE_PAIR_LID_PAD_DISPLAY_Y, 19), bevel=0)
    case.difference_from(invalid, cutter)
    try:
        must_reject(lambda: case.validate_built_domed_lid(
            {**parts, pad_key: invalid}), 'does not reach the roof clearance')
    finally:
        case.bpy.data.objects.remove(invalid, do_unlink=True)

    if args.project:
        case.validate_3mf_project(args.project)
        with zipfile.ZipFile(args.project) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        for add_to_base in (False, True):
            config = ET.fromstring(members['Metadata/model_settings.config'])
            if add_to_base:
                case.add_config_metadata(config.find('object'), 'enable_support', '1')
            else:
                lid_node = next(node for node in config.findall('object')
                    if case.config_metadata(node).get('enable_support') == '1')
                lid_node.remove(next(node for node in lid_node.findall('metadata')
                    if node.get('key') == 'enable_support'))
            with tempfile.TemporaryDirectory() as temporary:
                invalid_project = Path(temporary) / 'invalid-supports.3mf'
                with zipfile.ZipFile(invalid_project, 'w') as archive:
                    for name, payload in members.items():
                        archive.writestr(name, ET.tostring(config)
                            if name == 'Metadata/model_settings.config' else payload)
                must_reject(lambda: case.validate_3mf_project(invalid_project),
                            'incorrect local lid support settings')
        # An angled compound must retain its curved material interfaces.
        # Translate one complete component without damaging its topology.
        object_path = '3D/Objects/object_2.model'
        for part_index, expected in ((1, 'inlay island lacks shell bonding'),
                                     (2, 'gasket has an incorrect Z alignment')):
            model = ET.fromstring(members[object_path])
            meshes = model.findall(f'./{case.three_mf_tag("resources")}/{case.three_mf_tag("object")}')
            for vertex in meshes[part_index].iter(case.three_mf_tag('vertex')):
                vertex.set('z', str(float(vertex.get('z')) + .5))
            with tempfile.TemporaryDirectory() as temporary:
                invalid_project = Path(temporary) / 'misregistered-lid.3mf'
                with zipfile.ZipFile(invalid_project, 'w') as archive:
                    for name, payload in members.items():
                        archive.writestr(name, ET.tostring(model) if name == object_path else payload)
                must_reject(lambda: case.validate_3mf_project(invalid_project), expected)
    print('FIELD_CASE_DOMED_LID_REGRESSION_PASS', flush=True)


if __name__ == '__main__':
    main()
