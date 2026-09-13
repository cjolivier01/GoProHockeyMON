"""Check visible eye fillers against the real shell, aperture and U-slot."""
from pathlib import Path
import bpy

source = Path(__file__).with_name('hockeymom_cam_case_blender.py')
model = {'__name__':'eye_closure_regression','__file__':str(source)}
exec(compile(source.read_bytes(),str(source),'exec'),model)
model['clear_scene']()
model['validate_config']()
cameras,footprint = model['resolve_camera_layout']()
footprint = model['radially_expand_loop'](footprint,model['CAMERA_CARTRIDGE_SHELL_EXPANSION'])
footprint,mechanism = model['resolve_rear_envelope_converged'](footprint,cameras)
footprint,_ = model['extend_rear_battery_bay'](footprint,cameras,mechanism)
model['refresh_camera_eye_recesses'](cameras,footprint)

for material,visors in (('RIGID',False),('TPU',False),('RIGID',True),('TPU',True)):
    model['CASE_BODY_MATERIAL_MODE'] = material
    model['VISORS_ENABLED'] = visors
    model['clear_scene']()
    outer = tuple((z,model['scale_loop'](footprint,scale)) for z,scale in model['BODY_SECTIONS'])
    inner = tuple((z,model['inset_footprint_loop'](
        model['scale_loop'](footprint,model['body_scale_at_z'](z)),model['BODY_WALL_THICKNESS']))
        for z in (model['BOTTOM_THICKNESS'],6,12,model['BASE_HEIGHT']))
    base = model['hollow_loft_solid']('Fixture_Base',outer,inner)
    model['add_camera_openings_and_visors'](base,cameras,footprint)
    lid = model['polygon_prism_z']('Fixture_Lid',footprint,model['BASE_HEIGHT'],model['BODY_HEIGHT'])
    model['add_lid_eye_closures'](lid,cameras,footprint)
    model['validate_lid_eye_closure_faces'](lid,cameras,footprint)
    model['triangulate_mesh'](lid)
    model['validate_object'](lid)
    for lift in (0,0.25,1,10,27):
        lid.location.z = lift
        assert model['intersection_metrics'](base,lid,'eye_insertion')[2] < 0.0001, lift
    lid.location.z = 0
    for camera in cameras:
        # The internal lead-in must leave the visible exterior cheeks intact.
        for sign in (-1,1):
            local_camera = dict(camera)
            local_camera['eye_tangent'] += sign*(model['EYE_TOP_LOADING_SLOT_WIDTH']/2+0.3)
            radial = model['radial_surface_distance'](camera['angle'],local_camera['eye_tangent'],footprint)
            witness = model['eye_axis_box']('Exterior_Cheek_Witness',local_camera,
                (radial-0.19,radial-0.03),0.1,model['BASE_HEIGHT']-2,model['BASE_HEIGHT']-1.8)
            assert model['intersection_metrics'](base,witness,'retained_front_land')[2] > 0.0025
            bpy.data.objects.remove(witness,do_unlink=True)
        # The eye aperture must remain open through the full new filler depth.
        probe = model['eye_axis_box']('Eye_Aperture_Probe',camera,
            model['eye_mouth_cutter_radial_bounds'](camera),4,
            model['camera_eye_center_z']()+1,model['camera_eye_center_z']()+5)
        assert model['intersection_metrics'](lid,probe,'open_eye_aperture')[2] < 0.0001
        bpy.data.objects.remove(probe,do_unlink=True)
    # Reproduce a recessed face without changing the camera or outside shell.
    camera = cameras[0]
    expected = model['radial_surface_distance'](camera['angle'],camera['eye_tangent'],footprint)
    cut = model['eye_axis_box']('Recessed_Filler_Regression',camera,
        (expected-4,expected+4),8,model['BASE_HEIGHT']-15,model['BASE_HEIGHT']-0.01)
    model['boolean_difference'](lid,[cut])
    try:
        model['validate_lid_eye_closure_faces'](lid,cameras,footprint)
    except RuntimeError as error:
        assert 'not flush' in str(error) or 'does not reach' in str(error),str(error)
    else:
        raise AssertionError('Recessed eye filler was accepted')
    print('LID_EYE_CLOSURE_REGRESSION PASS',material,'visors=',visors)
