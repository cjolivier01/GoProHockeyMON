"""Blender regression for the swept fan shell and its retained service paths."""
from pathlib import Path
import bpy

source = Path(__file__).with_name('hockeymom_cam_case_blender.py')
model = {'__name__':'fan_cover_regression','__file__':str(source)}
exec(compile(source.read_bytes(),str(source),'exec'),model)


def check_pod(mode,size,material):
    model['clear_scene']()
    model['FAN_MOUNT_MODE'],model['LID_FAN_SIZE_MM'] = mode,size
    model['LID_FAN_COVER_MATERIAL_MODE'] = material
    footprint = ((-120,-110),(120,-110),(120,110),(-120,110))
    positions = ((105,-85),(105,85),(-105,0))
    lid = model['polygon_prism_z']('Fixture_Lid',footprint,model['BASE_HEIGHT'],model['BODY_HEIGHT'])
    model['add_lid_fan_mount'](lid,footprint,positions)
    pod = model['create_lid_fan_pod'](lid,positions)
    for part in pod.values():
        model['triangulate_mesh'](part)
        model['validate_object'](part)
        model['validate_print_bed_fit']([part])
    model['validate_lid_fan_pod_printability'](pod)
    model['validate_lid_fan_pod_fit_and_service'](lid,pod)
    model['validate_lid_fan_grille_positive_retention'](pod['fairing'],pod['grille'])
    model['validate_lid_fan_fairing_positive_retention'](lid,pod['fairing'])
    model['validate_lid_fan_cable_route'](lid,pod['fairing'],pod['grille'])
    dimensions = model['lid_fan_reference_dimensions']()
    z0 = model['BODY_HEIGHT']+2*model['LID_FAN_COVER_RETENTION_PAD_HEIGHT']+0.2
    z1 = model['BODY_HEIGHT']+dimensions['depth']-0.1
    for x,y in model['lid_fan_unit_centers']():
        # Outside the deliberate low friction ribs, the complete bought fan
        # frame must fit inside the swept shell, not merely its airflow hole.
        half = dimensions['frame']/2
        witness = model['rear_battery_box']('Fan_Frame_Clearance',((x-half,x+half),(y-half,y+half),(z0,z1)))
        assert model['intersection_metrics'](pod['fairing'],witness,'fan_frame')[2] < 0.001
        bpy.data.objects.remove(witness,do_unlink=True)
        opening = model['add_cylinder_z']('Full_Airflow_Column',dimensions['opening']/2,
                                          model['BASE_HEIGHT'],z1+5,x,y)
        assert model['intersection_metrics'](pod['fairing'],opening,'fan_airflow')[2] < 0.001
        bpy.data.objects.remove(opening,do_unlink=True)
    print(f'STREAMLINED_FAN_PASS {mode} {size} {material}')


for configuration in (('lid_single',120,'TPU'),('lid_single',120,'RIGID'),
                      ('lid_pair',60,'TPU'),('lid_pair',40,'TPU')):
    check_pod(*configuration)
