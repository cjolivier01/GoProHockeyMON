"""Check an INTERNAL upright battery and two-screw bar, closed-case containment and cooling clearance.

Run with Blender --background --factory-startup --python-exit-code 1 --python.
The normal camera-case build also checks the complete assembled hardware.
"""

from copy import deepcopy
from pathlib import Path

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
        ("REAR_BATTERY_WIDTH",95.0,"closed lid"),
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
    outer = tuple((z,model["scale_loop"](footprint,scale)) for z,scale in model["BODY_SECTIONS"])
    inner = tuple((z,model["inset_footprint_loop"](
        model["scale_loop"](footprint,model["body_scale_at_z"](z)),3.2,
    )) for z in (3.2,6.0,12.0,model["BASE_HEIGHT"]))
    base = model["hollow_loft_solid"]("Fixture_Base",outer,inner)
    lid = model["polygon_prism_z"]("Fixture_Lid",footprint,model["BASE_HEIGHT"],model["BODY_HEIGHT"])
    model["add_rear_battery_slot"](base,layout,(lid,))
    bracket = model["create_rear_battery_bracket"](layout)
    record = model["rear_battery_bracket_layout"](layout)
    model["triangulate_mesh"](base)
    model["validate_object"](base)
    validate = lambda obstacles=(): model["validate_rear_battery_slot"](base,lid,layout,footprint,obstacles,bracket=bracket)
    validate()
    bx,by,bz = layout["pack_bounds"]
    assert tuple(round(high-low,3) for low,high in (bx,by,bz)) == (26.3,138.0,70.0)
    assert abs(layout["usb_bounds"][1][1]-layout["usb_bounds"][1][0]-40) < 1e-8
    assert bz[1] < model["BASE_HEIGHT"]
    assert tuple(round(high-low,3) for low,high in record["bounds"]) == (47.5,16.0,4.0)
    # A fan cover fastened to the lid leaves with it during battery loading.
    lid_attachment = box("Lid_Attachment",(bx,by,(model["BODY_HEIGHT"]+1,model["BODY_HEIGHT"]+8)))
    model["validate_rear_battery_slot"](base,lid,layout,footprint,(lid_attachment,),lid_parts=(lid_attachment,),bracket=bracket)
    bpy.data.objects.remove(lid_attachment,do_unlink=True)
    # Independent full fan-opening prism: no holder material may enter the
    # vertical cooling column, even when a seated battery passes collision checks.
    opening = model["lid_fan_reference_dimensions"]()["opening"]
    for x,y in model["lid_fan_unit_centers"]():
        witness = box("Fan_Column",((x-opening/2,x+opening/2),(y-opening/2,y+opening/2),(3.21,model["BASE_HEIGHT"]-0.01)))
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
    intrusion["protected_x"] += 1.0
    expect_error(RuntimeError,lambda: model["validate_rear_battery_slot"](base,lid,intrusion,footprint,(),bracket=bracket),"protected cooling region")
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
    oversize = box("Too_Large_To_Print",((0,250.1),(0,12),(0,4)))
    transform = oversize.matrix_world.copy()
    expect_error(ValueError,lambda: model["export_single_stl"](
        Path("/tmp/oversize-battery-regression.stl"),oversize,print_face_down=True),"exceeds 250")
    assert oversize.matrix_world == transform, "Failed export changed assembly pose"


check_configuration()
check_mesh("lid_single")
check_mesh("lid_pair")
check_mesh("lid_single", "TPU")
print("REAR_BATTERY_REGRESSION PASS upright pack, two-screw bracket, loading, USB, cable, cooling, rigid/TPU posts, single/pair fans, 250 mm exports")
