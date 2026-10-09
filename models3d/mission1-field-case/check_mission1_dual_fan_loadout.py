"""Reject mount collisions, misaligned forks and shell growth in a saved scene.

blender --background --factory-startup --python-exit-code 1 \
  --python check_mission1_dual_fan_loadout.py -- --scene /path/to/complete.blend
The normal generator already runs the positive geometry and print-layer checks.
"""

import argparse
from pathlib import Path
from types import SimpleNamespace
import sys

import bpy
from mathutils import Vector


parser = argparse.ArgumentParser()
parser.add_argument("--scene", required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
bpy.ops.wm.open_mainfile(filepath=str(Path(args.scene).resolve()))
source = Path(__file__).with_name("mission1_field_case_blender.py")
ns = {"__name__": "dual_fan_regression", "__file__": str(source)}
exec(compile(source.read_bytes(), str(source), "exec"), ns)
f = SimpleNamespace(**ns)
module, _directory = f.import_companion_module("mission1_dual_fan_loadout", "mission1-field-case")
parts = {key: bpy.data.objects[name] for key, name in {
    "base": "Field_Case_Base", "lid": "Field_Case_Lid",
    "tpu_snap_lid": "Field_Case_Lid_TPU_68D_Snap_Hinge",
    "accessory_organizer": "Field_Case_Coil_And_Remote_Organizer",
    "fan_cradle": "Field_Case_Expanded_Dual_Fan_Cradle",
    "equipment_tray": "Field_Case_Removable_Upper_TPU_Equipment_Tray",
    "dual_fan_riser": "Field_Case_Dual_Fan_Tray_Riser",
    "dual_fan_spacer": "Field_Case_Dual_Fan_Storage_Spacer",
}.items()}


def one(prefix):
    matches = [o for o in bpy.data.objects if o.name.startswith(prefix)]
    assert len(matches) == 1, (prefix, [o.name for o in matches])
    return matches[0]


holder = one("REFERENCE_ONLY_Stored_Dual_Fan_Holder")
adapter = one("REFERENCE_ONLY_Stored_Dual_Fan_Three_Prong_Adapter")
mate = one("REFERENCE_ONLY_Stored_Dual_Fan_Attached_Two_Prong_Mount")
extension = one("REFERENCE_ONLY_Stored_Dual_Fan_Mount_Clearance")
fans = [o for o in bpy.data.objects if o.name.startswith("REFERENCE_ONLY_Installed_80mm_Fan_")]
refs = [o for o in bpy.data.objects if o != extension and o.name.startswith(
    ("REFERENCE_ONLY_Stored_Dual_Fan_", "REFERENCE_ONLY_Installed_80mm_Fan_",
     "REFERENCE_ONLY_MISSION1_", "REFERENCE_ONLY_Enduro2_"))]
assert len([o for o in refs if o.name.startswith("REFERENCE_ONLY_Enduro2_")]) == 6
assert "lid_retainer" not in parts

# Validate the unmodified scene before relying on its negative checks.
module.validate_loadout(f, parts, refs, extension, holder, adapter, mate, fans)


def reject(label, expected):
    try:
        module.validate_loadout(f, parts, refs, extension, holder, adapter, mate, fans)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(f"{label}: unexpected rejection: {error}") from error
        print(f"FIELD_CASE_DUAL_FAN_REJECTED {label}: {error}", flush=True)
    else:
        raise AssertionError("Invalid dual-fan configuration accepted: " + label)


# A full 2-inch straight reach crosses the fixed front wall in this packing.
minimum, maximum = f.object_world_bounds(extension)
center = (minimum + maximum) / 2
long_extension = f.add_rounded_prism("TEMPORARY_Two_Inch_Mount_Clearance",
    f.DUAL_FAN_MOUNT_CLEARANCE_WIDTH, 50.8, minimum.z, maximum.z, 1,
    (center.x, maximum.y - 25.4))
original_extension = extension
extension = long_extension
try:
    reject("two_inch_straight_mount", "intersects case")
finally:
    extension = original_extension
    bpy.data.objects.remove(long_extension, do_unlink=True)

saved_location = mate.location.copy()
try:
    mate.location.x += 1
    bpy.context.view_layer.update()
    reject("misaligned_adapter_fingers", "do not interleave")
finally:
    mate.location = saved_location
    bpy.context.view_layer.update()

saved_depth = f.CASE_DEPTH
try:
    f.CASE_DEPTH += 1
    reject("larger_shell", "shared shell dimensions")
finally:
    f.CASE_DEPTH = saved_depth

# Removing the riser's bearing must fail even if its outer mesh is valid.
riser = parts["dual_fan_riser"]
location = riser.location.copy()
try:
    riser.location.z -= .5
    bpy.context.view_layer.update()
    reject("displaced_tray_bearing", "intersects shared shell")
finally:
    riser.location = location
    bpy.context.view_layer.update()

# Reintroduce the two previously blocked extraction paths. Both modifications
# fit when seated, so the removal sweep itself must reject them.
for key, dimensions, center, expected in (
        ("equipment_tray", (16.0, 23.0, 35.0), (-16.6, -47.355, 68.5),
         "equipment_tray extraction blocked"),
        ("dual_fan_riser", (30.0, 4.0, 12.0), (15.0, -82.5, 45.0),
         "dual_fan_riser extraction blocked")):
    original = parts[key]
    blocked = original.copy()
    blocked.data = original.data.copy()
    bpy.context.collection.objects.link(blocked)
    f.union_into(blocked, f.add_rounded_box("TEMPORARY_Blocked_Mount_Passage",
                                          dimensions, center, bevel=0))
    parts[key] = blocked
    try:
        reject("blocked_" + key + "_removal", expected)
    finally:
        parts[key] = original
        bpy.data.objects.remove(blocked, do_unlink=True)
print("FIELD_CASE_DUAL_FAN_REGRESSION_VALID negative_cases=6 batteries=6 shared_organizer=yes", flush=True)
