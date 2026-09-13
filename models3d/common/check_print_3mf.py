"""Exercise 3MF placement and reject unsafe or incomplete STL inputs."""
from pathlib import Path
import json
import shutil
import subprocess
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

from print_3mf import export_print_project, tag, validate_print_project


def write_tetra(path, width=20, z=0):
    points = ((-width/2,-5,z),(width/2,-5,z),(0,5,z),(0,0,z+15))
    faces = ((0,2,1),(0,1,3),(1,2,3),(2,0,3))
    data = bytearray(80) + struct.pack('<I',len(faces))
    for face in faces:
        data.extend(struct.pack('<12fH',0,0,0,*(v for i in face for v in points[i]),0))
    path.write_bytes(data)
    return path


class PrintProjectTests(unittest.TestCase):
    def test_explicit_parts_on_separate_beds(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parts = [write_tetra(root/f'part_{i}.stl',width=249.9 if i==0 else 20) for i in range(5)]
            write_tetra(root/'stale_reference.stl')
            project = export_print_project(root/'print.3mf',parts)
            validate_print_project(project,parts)
            with zipfile.ZipFile(project) as archive:
                model = ET.fromstring(archive.read('3D/3dmodel.model'))
                items = model.find(tag('build')).findall(tag('item'))
                assert len(items) == 5
                translations = [list(map(float,item.get('transform').split()))[9:] for item in items]
                assert translations == [[125,125,0],[425,125,0],[725,125,0],[125,-175,0],[425,-175,0]]
                assert b'stale_reference' not in archive.read('Metadata/print_manifest.json')

    @unittest.skipUnless(shutil.which('bambu-studio'), 'Bambu Studio CLI not installed')
    def test_bambu_preserves_plate_layout(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parts = [write_tetra(root/f'part_{i}.stl',width=249.9 if i==0 else 20) for i in range(5)]
            project = export_print_project(root/'print.3mf',parts)
            output = root/'roundtrip.3mf'
            result = subprocess.run([shutil.which('bambu-studio'),'--arrange','0','--orient','0',
                                     '--export-3mf',str(output),str(project)],
                                    cwd=root,capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            with zipfile.ZipFile(output) as archive:
                settings = json.loads(archive.read('Metadata/project_settings.config'))
                config = ET.fromstring(archive.read('Metadata/model_settings.config'))
                self.assertEqual(settings['printable_area'],['0x0','250x0','250x250','0x250'])
                self.assertEqual(len(config.findall('object')),5)
                self.assertEqual([len(p.findall('model_instance')) for p in config.findall('plate')],[1]*5)
                names = [{m.get('key'):m.get('value') for m in p.findall('metadata')}['plater_name']
                         for p in config.findall('plate')]
                self.assertEqual(names,[f'part {i}' for i in range(5)])

    def test_invalid_input_preserves_previous_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root/'print.3mf'
            project.write_bytes(b'previous project')
            valid = write_tetra(root/'valid.stl')
            for parts in ([],[valid,valid],[write_tetra(root/'oversize.stl',250.1)],
                          [write_tetra(root/'floating.stl',z=0.1)]):
                with self.assertRaises(ValueError):
                    export_print_project(project,parts)
                self.assertEqual(project.read_bytes(),b'previous project')
            valid.write_bytes(valid.read_bytes()[:-1])
            with self.assertRaisesRegex(ValueError,'Invalid binary STL'):
                export_print_project(project,[valid])


if __name__ == '__main__':
    unittest.main()
