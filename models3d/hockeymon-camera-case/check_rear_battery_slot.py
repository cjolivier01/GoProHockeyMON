"""Check an INTERNAL flat battery, closed-case containment and cooling clearance.

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
        ("REAR_BATTERY_THICKNESS",65.0,"closed lid"),
        ("REAR_BATTERY_FLOOR_THICKNESS",2.0,"case floor"),
        ("REAR_BATTERY_STRAP_SPACING",130.0,"solid webs"),
    ):
        original = model[name]
        model[name] = value
        expect_error(ValueError,model["validate_rear_battery_config"],message)
        model[name] = original


def check_mesh(mode):
    model["clear_scene"]()
    model["FAN_MOUNT_MODE"] = mode
    if mode == "lid_pair":
        model["LID_FAN_SIZE_MM"] = 60
    box = model["rear_battery_box"]
    old_footprint = ((-80,-115),(80,-115),(80,115),(-80,115))
    footprint,layout = model["extend_rear_battery_bay"](old_footprint,(),None)
    outer = tuple((z,model["scale_loop"](footprint,scale)) for z,scale in model["BODY_SECTIONS"])
    inner = tuple((z,model["inset_footprint_loop"](
        model["scale_loop"](footprint,model["body_scale_at_z"](z)),3.2,
    )) for z in (3.2,6.0,12.0,68.0))
    base = model["hollow_loft_solid"]("Fixture_Base",outer,inner)
    lid = model["polygon_prism_z"]("Fixture_Lid",footprint,68,72.653)
    model["add_rear_battery_slot"](base,layout,(lid,))
    model["triangulate_mesh"](base)
    model["validate_object"](base)
    validate = lambda obstacles=(): model["validate_rear_battery_slot"](base,lid,layout,footprint,obstacles)
    validate()
    bx,by,bz = layout["pack_bounds"]
    assert tuple(round(high-low,3) for low,high in (bx,by,bz)) == (70.0,138.0,26.3)
    assert abs(layout["usb_bounds"][1][1]-layout["usb_bounds"][1][0]-40) < 1e-8
    assert bz[1] < 68.0
    # A fan cover fastened to the lid leaves with it during battery loading.
    lid_attachment = box("Lid_Attachment",(bx,by,(75.0,85.0)))
    model["validate_rear_battery_slot"](base,lid,layout,footprint,(lid_attachment,),lid_parts=(lid_attachment,))
    bpy.data.objects.remove(lid_attachment,do_unlink=True)
    # Independent full fan-opening prism: no holder material may enter the
    # vertical cooling column, even when a seated battery passes collision checks.
    opening = model["lid_fan_reference_dimensions"]()["opening"]
    for x,y in model["lid_fan_unit_centers"]():
        witness = box("Fan_Column",((x-opening/2,x+opening/2),(y-opening/2,y+opening/2),(3.21,67.99)))
        assert model["intersection_metrics"](base,witness,"fan_column")[2] < 0.0001
        bpy.data.objects.remove(witness,do_unlink=True)
    for name,bounds,message in (
        ("Blocked_USB",(bx,(by[1]+10,by[1]+15),bz),"usb_plugs intersects"),
        ("Blocked_Loading",(bx,by,(bz[1]+10,bz[1]+15)),"top_loading intersects"),
        ("Blocked_Cable",layout["cable_bounds"],"intersects"),
    ):
        obstruction = box(name,bounds)
        expect_error(RuntimeError,lambda: validate((obstruction,)),message)
        bpy.data.objects.remove(obstruction,do_unlink=True)
    outside = deepcopy(layout)
    outside["pack_bounds"] = ((bx[0]+500,bx[1]+500),by,bz)
    expect_error(RuntimeError,lambda: model["validate_rear_battery_slot"](base,lid,outside,footprint,()),"outside the closed case")
    intrusion = deepcopy(layout)
    intrusion["protected_x"] += 1.0
    expect_error(RuntimeError,lambda: model["validate_rear_battery_slot"](base,lid,intrusion,footprint,()),"protected cooling region")
    for target in layout["post_targets"]:
        assert not model["circular_feature_intersects_rear_battery"](target,5.25)
    assert model["circular_feature_intersects_rear_battery"]((sum(bx)/2,sum(by)/2),5.25)


check_configuration()
check_mesh("lid_single")
check_mesh("lid_pair")
print("REAR_BATTERY_REGRESSION PASS internal flat pack, closed lid, loading, USB, cable, cooling, posts, single/pair fans")
