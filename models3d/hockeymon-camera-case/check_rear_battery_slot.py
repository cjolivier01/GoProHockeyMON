"""Check a flat internal battery and two-screw bar, closed-case containment and cooling clearance.

Run with Blender --background --factory-startup --python-exit-code 1 --python.
The normal camera-case build also checks the complete assembled hardware.
"""

from copy import deepcopy
from pathlib import Path
import tempfile

import bpy

source = Path(__file__).with_name("hockeymom_cam_case_blender.py")
model = {"__name__": "battery_regression", "__file__": str(source)}
exec(compile(source.read_bytes(), str(source), "exec"), model)


def expect_error(error_type, callback, message):
    try:
        callback()
    except error_type as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError(f"Expected rejection: {message}")


def check_configuration():
    model["validate_rear_battery_config"]()
    original = model["FAN_MOUNT_MODE"]
    model["FAN_MOUNT_MODE"] = "rear_wall_pair"
    expect_error(ValueError, model["validate_rear_battery_config"], "rear-wall fans")
    model["REAR_BATTERY_SLOT_ENABLED"] = False
    model["validate_rear_battery_config"]()
    original_footprint = ((-80,-115),(80,-115),(80,115),(-80,115))
    assert model["extend_rear_battery_bay"](original_footprint,(),None) == (original_footprint,None)
    model["REAR_BATTERY_SLOT_ENABLED"] = True
    model["FAN_MOUNT_MODE"] = original
    for name,value,message in (
        ("REAR_BATTERY_FIT_CLEARANCE",-0.1,"finite and positive"),
        ("REAR_BATTERY_USB_CLEARANCE",float("nan"),"finite and positive"),
        ("REAR_BATTERY_THICKNESS",95.0,"closed lid"),
        ("REAR_BATTERY_FLOOR_THICKNESS",2.0,"case floor"),
        ("REAR_BATTERY_BRACKET_SCREW_LENGTH",8.0,"full insert engagement"),
        ("REAR_BATTERY_BRACKET_RECEIVER_DEPTH",5.0,"blind-hole tip clearance"),
        ("REAR_BATTERY_BRACKET_POST_DIAMETER",8.0,"2 mm around"),
        ("REAR_BATTERY_BRACKET_SCREW_HOLE_DIAMETER",2.5,"M3 clearance"),
        ("REAR_BATTERY_BRACKET_SCREW_HOLE_DIAMETER",5.4,"head bearing"),
        ("REAR_BATTERY_BRACKET_SCREW_LENGTH",10.6,"blind-hole tip clearance"),
    ):
        original = model[name]
        model[name] = value
        expect_error(ValueError,model["validate_rear_battery_config"],message)
        model[name] = original


def check_mesh(mode, material="RIGID"):
    model["CASE_BODY_MATERIAL_MODE"] = material
    model["clear_scene"]()
    model["FAN_MOUNT_MODE"] = mode
    model["LID_FAN_SIZE_MM"] = 60 if mode == "lid_pair" else 120
    box = model["rear_battery_box"]
    old_footprint = ((-80,-115),(80,-115),(80,115),(-80,115))
    footprint,layout = model["extend_rear_battery_bay"](old_footprint,(),None)
    model["validate_rear_battery_envelope_symmetry"](footprint)
    asymmetric = [(x,y+(1 if y>0 else 0)) for x,y in footprint]
    expect_error(ValueError,lambda: model["validate_rear_battery_envelope_symmetry"](asymmetric),"not symmetric")
    stops = model["rear_battery_end_stop_bounds"](layout)
    assert len(stops) == 4
    assert all((x,(-y[1],-y[0]),z) in stops for x,y,z in stops)
    outer = tuple((z,model["scale_loop"](footprint,scale)) for z,scale in model["BODY_SECTIONS"])
    inner = tuple((z,model["inset_footprint_loop"](
        model["scale_loop"](footprint,model["body_scale_at_z"](z)),3.2,
    )) for z in (3.2,6.0,12.0,model["BASE_HEIGHT"]))
    base = model["hollow_loft_solid"]("Fixture_Base",outer,inner)
    lid = model["polygon_prism_z"]("Fixture_Lid",footprint,model["BASE_HEIGHT"],model["BODY_HEIGHT"])
    # Measure the actual holder solid before it joins the case, independent
    # of its parameter layout. Equal-density plastic must balance around Y=0.
    original_union = model["boolean_union"]
    holder_centroids = []
    def check_holder_union(target,part,label="Union",**kwargs):
        if label == "Internal_Battery_Slot":
            part.data.calc_loop_triangles()
            volume6 = moment_y = 0.0
            for triangle in part.data.loop_triangles:
                a,b,c = (part.matrix_world @ part.data.vertices[i].co for i in triangle.vertices)
                signed = a.dot(b.cross(c))
                volume6 += signed
                moment_y += signed*(a.y+b.y+c.y)/4
            holder_centroids.append(moment_y/volume6)
        return original_union(target,part,label,**kwargs)
    model["boolean_union"] = check_holder_union
    try:
        model["add_rear_battery_slot"](base,layout,(lid,))
    finally:
        model["boolean_union"] = original_union
    assert len(holder_centroids) == 1 and abs(holder_centroids[0]) < 0.001, holder_centroids

    bracket = model["create_rear_battery_bracket"](layout)
    record = model["rear_battery_bracket_layout"](layout)
    model["triangulate_mesh"](base)
    model["validate_object"](base)
    validate = lambda obstacles=(): model["validate_rear_battery_slot"](base,lid,layout,footprint,obstacles,bracket=bracket)
    validate()
    bx,by,bz = layout["pack_bounds"]
    assert tuple(round(high-low,3) for low,high in (bx,by,bz)) == (70.0,138.0,26.3)
    assert abs(layout["usb_bounds"][1][1]-layout["usb_bounds"][1][0]-40) < 1e-8
    assert sum(by) == 0.0 and layout["center_y"] == 0.0
    assert abs(bx[0] - (layout["fan_rear_x"] - 70.0*model["REAR_BATTERY_FAN_OVERLAP_FRACTION"] + 3*model["REAR_BATTERY_FIT_CLEARANCE"])) < 1e-8
    assert bz == (5.7,32.0)
    shifted = deepcopy(layout)
    shifted["pack_bounds"] = (bx,(by[0]+1,by[1]+1),bz)
    expect_error(RuntimeError,lambda: model["validate_rear_battery_slot"](
        base,lid,shifted,footprint,(),bracket=bracket),"centered east-west")
    assert bz[1] < model["BASE_HEIGHT"]
    assert tuple(round(high-low,3) for low,high in record["bounds"]) == (91.2,16.0,4.0)
    # Stops survive the final union and block translation toward either end.
    for shift in (-0.9,0.9):
        sliding = box("Battery_Sliding_End_Check",(bx,(by[0]+shift,by[1]+shift),bz))
        assert model["intersection_metrics"](base,sliding,"battery_end_stop")[2] > 0.1
        bpy.data.objects.remove(sliding,do_unlink=True)
    for sign in (-1,1):
        x = bx[0]+1.5 if sign < 0 else bx[1]-1.5
        witness = box("Battery_End_Stop_Solid",((x-0.25,x+0.25),
            (by[1]+1.0,by[1]+2.0),(bz[0]+1,bz[0]+2)))
        assert model["intersection_metrics"](base,witness,"battery_stop_survival")[2] > 0.4
        bpy.data.objects.remove(witness,do_unlink=True)
    # A fan cover fastened to the lid leaves with it during battery loading.
    lid_attachment = box("Lid_Attachment",(bx,by,(model["BODY_HEIGHT"]+1,model["BODY_HEIGHT"]+8)))
    model["validate_rear_battery_slot"](base,lid,layout,footprint,(lid_attachment,),lid_parts=(lid_attachment,),bracket=bracket)
    bpy.data.objects.remove(lid_attachment,do_unlink=True)
    # Independent upper fan-opening prism: the low cradle and flat pack may
    # overlap in plan, while the fan-to-camera passage stays open above them.
    opening = model["lid_fan_reference_dimensions"]()["opening"]
    flow_floor = record["bounds"][2][1] + model["M3_SOCKET_HEAD_NOMINAL_HEIGHT"] + model["REAR_BATTERY_AIR_GAP"]
    for x,y in model["lid_fan_unit_centers"]():
        witness = box("Fan_Column",((x-opening/2,x+opening/2),(y-opening/2,y+opening/2),(flow_floor,model["BASE_HEIGHT"]-0.01)))
        assert model["intersection_metrics"](base,witness,"fan_column")[2] < 0.0001
        bpy.data.objects.remove(witness,do_unlink=True)
    for name,bounds,message in (
        ("Blocked_USB",(bx,(by[1]+10,by[1]+15),bz),"usb_plugs intersects"),
        ("Blocked_Loading",(bx,by,(model["BODY_HEIGHT"]+2,model["BODY_HEIGHT"]+6)),"top_loading intersects"),
        ("Blocked_Cable",layout["cable_bounds"],"intersects"),
        ("Blocked_Bar_Lift",((record["bounds"][0][0],bx[0]-0.5),record["bounds"][1],
                              (model["BASE_HEIGHT"]+1,model["BASE_HEIGHT"]+3)),"bracket_removal intersects"),
        ("Blocked_Screw_Access",(record["head_bounds"][0][0],record["head_bounds"][0][1],
                                  (model["BODY_HEIGHT"]+2,model["BODY_HEIGHT"]+6)),"screw_access_0 intersects"),
    ):
        obstruction = box(name,bounds)
        expect_error(RuntimeError,lambda: validate((obstruction,)),message)
        bpy.data.objects.remove(obstruction,do_unlink=True)
    outside = deepcopy(layout)
    outside["pack_bounds"] = ((bx[0]+500,bx[1]+500),by,bz)
    expect_error(RuntimeError,lambda: model["validate_rear_battery_slot"](base,lid,outside,footprint,(),bracket=bracket),"outside the closed case")
    intrusion = deepcopy(layout)
    intrusion["fan_rear_x"] = bx[0] + model["REAR_BATTERY_WIDTH"]/2 + 1.0
    expect_error(RuntimeError,lambda: model["validate_rear_battery_slot"](base,lid,intrusion,footprint,(),bracket=bracket),"50 percent overlap")
    for target in layout["post_targets"]:
        assert not model["circular_feature_intersects_rear_battery"](target,5.25)
    assert model["circular_feature_intersects_rear_battery"]((sum(bx)/2,sum(by)/2),5.25)

    # A mistakenly undersized bar must fail independently of the configured
    # clearance diameter, including when the base has smaller TPU pilots.
    original_diameter = model["REAR_BATTERY_BRACKET_SCREW_HOLE_DIAMETER"]
    model["REAR_BATTERY_BRACKET_SCREW_HOLE_DIAMETER"] = 2.5
    wrong_bar = model["create_rear_battery_bracket"](layout)
    model["REAR_BATTERY_BRACKET_SCREW_HOLE_DIAMETER"] = original_diameter
    expect_error(RuntimeError,lambda: model["validate_rear_battery_slot"](
        base,lid,layout,footprint,(),bracket=wrong_bar),"screw path is obstructed")
    bpy.data.objects.remove(wrong_bar,do_unlink=True)

    # Closing a bar hole must fail, even though the pack fits.
    x,y = record["centers"][0]
    plug = model["add_cylinder_z"]("Blocked_Screw_Hole",1.0,
                record["bounds"][2][0],record["bounds"][2][1],x,y)
    model["boolean_union"](bracket,plug)
    expect_error(RuntimeError,validate,"screw path is obstructed")
    for obj in (base,lid,bracket):
        model["validate_print_bed_fit"]([obj])
    oversize = box("Too_Large_To_Print",((0,255.1),(0,12),(0,4)))
    transform = oversize.matrix_world.copy()
    expect_error(ValueError,lambda: model["export_single_stl"](
        Path("/tmp/oversize-battery-regression.stl"),oversize,print_face_down=True),"exceeds 250")
    assert oversize.matrix_world == transform, "Failed export changed assembly pose"
    # The long axis may exceed 250 mm only along the 255 mm bed direction.
    from print_3mf import stl_payload
    with tempfile.TemporaryDirectory() as temporary:
        for x,y in ((249,254),(254,249)):
            part = box("Rectangular_Print_Bed",((0,x),(0,y),(0,4)))
            pose = part.matrix_world.copy()
            path = Path(temporary)/"rectangular.stl"
            model["export_single_stl"](path,part)
            vertices,_ = stl_payload(path)
            spans = tuple(max(v[a] for v in vertices)-min(v[a] for v in vertices) for a in (0,1))
            assert abs(spans[0]-249)<0.001 and abs(spans[1]-254)<0.001, spans
            assert part.matrix_world == pose
            bpy.data.objects.remove(part,do_unlink=True)
        too_square = box("Both_Axes_Too_Wide",((0,251),(0,251),(0,4)))
        expect_error(ValueError,lambda: model["export_single_stl"](
            Path(temporary)/"square.stl",too_square),"exceeds 250 x 255")


check_configuration()
check_mesh("lid_single")
check_mesh("lid_pair")
check_mesh("lid_single", "TPU")
print("REAR_BATTERY_REGRESSION PASS flat pack, two-screw bracket, loading, USB, cable, cooling, rigid/TPU posts, single/pair fans, 250 x 255 mm exports")
