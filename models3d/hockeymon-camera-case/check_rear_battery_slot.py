"""Exercise rear battery fit, airflow isolation and obstruction detection.

Run: blender --background --factory-startup --python-exit-code 1 \
    --python models3d/hockeymon-camera-case/check_rear_battery_slot.py

Uses a small closed rectangular shell for fast regression checks. The normal
camera-case build separately validates the complete assembled model.
"""

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
    assert model["add_rear_battery_slot"](None, (), ()) is None
    model["REAR_BATTERY_SLOT_ENABLED"] = True
    model["FAN_MOUNT_MODE"] = original
    for name, value, message in (
        ("REAR_BATTERY_FIT_CLEARANCE", -0.1, "finite and positive"),
        ("REAR_BATTERY_USB_CLEARANCE", float("nan"), "finite and positive"),
        ("REAR_BATTERY_ROOT_EMBED", 3.2, "inner wall"),
        ("REAR_BATTERY_STRAP_SPACING", 30.0, "solid webs"),
    ):
        original = model[name]
        model[name] = value
        expect_error(ValueError, model["validate_rear_battery_config"], message)
        model[name] = original


def check_mesh():
    model["clear_scene"]()
    box = model["rear_battery_box"]
    footprint = ((-80, -115), (80, -115), (80, 115), (-80, 115))
    base = box("Fixture_Base", ((-80, 80), (-115, 115), (0, 68)))
    model["boolean_difference"](base, [box(
        "Fixture_Cavity", ((-76.8, 76.8), (-111.8, 111.8), (3.2, 69)),
    )])
    lid = box("Fixture_Lid", ((-80, 80), (-115, 115), (68, 72.653)))
    layout = model["add_rear_battery_slot"](base, footprint, (base, lid))
    model["triangulate_mesh"](base)
    model["validate_object"](base)
    model["validate_rear_battery_slot"](base, layout, (lid,))
    bx, by, bz = layout["pack_bounds"]
    assert tuple(round(high - low, 3) for low, high in (bx, by, bz)) == (26.3, 138.0, 70.0)
    assert bx[0] > 80 + 8
    # Independent interior witness: the holder must add no material anywhere
    # inside this fixture's original chamber, including below the strap seat.
    witnesses = [
        box("Unchanged_Chamber", ((-76.79, 76.79), (-111.79, 111.79), (3.21, 67.99))),
        *(box("Strap_Threading_Path", (
            (layout["x0"] - 4, layout["x1"] + 4), (y - 7.5, y + 7.5), (3.3, 5.6),
        )) for y in (-40, 40)),
    ]
    for witness in witnesses:
        assert model["intersection_metrics"](base, witness, "independent_witness")[2] < 0.0001
        bpy.data.objects.remove(witness, do_unlink=True)
    # A real obstruction in either the loading path or the full USB face must
    # be rejected, even when the seated battery itself still fits.
    for name, bounds, message in (
        ("Blocked_USB", (bx, (by[1] + 10, by[1] + 15), bz), "usb_plugs intersects"),
        ("Blocked_Loading", (bx, by, (bz[1] + 10, bz[1] + 15)), "top_loading intersects"),
    ):
        obstruction = box(name, bounds)
        expect_error(RuntimeError, lambda: model["validate_rear_battery_slot"](
            base, layout, (lid, obstruction),
        ), message)
        bpy.data.objects.remove(obstruction, do_unlink=True)
    # A rearward fan still pushes the slot beyond its frame without a cover.
    original = model["LID_FAN_CENTER_X"]
    model["LID_FAN_CENTER_X"] = 90
    shifted = model["rear_battery_layout"](footprint, (lid,))
    assert shifted["x0"] - model["REAR_BATTERY_WALL_THICKNESS"] >= 158
    model["LID_FAN_CENTER_X"] = original


check_configuration()
check_mesh()
print("REAR_BATTERY_REGRESSION PASS configuration, manifold, fit, chamber, straps, USB, loading, fan")
