"""Check cap geometry and packed cable space; optionally reuse a built scene.

blender -b --python-exit-code 1 --python this_file.py -- --scene case.blend
Without --scene, build the affected insert, trays, shell and references.
"""

import argparse
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission1_field_case_blender as case


def main():
    global case
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", type=Path)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if args.compact:
        source = Path(case.__file__)
        namespace = {"__name__": "compact_cap_check", "__file__": str(source),
                     "EXPANDED_ACCESSORY_STORAGE": False}
        exec(compile(source.read_bytes(), str(source), "exec"), namespace)
        case = SimpleNamespace(**namespace)
    if args.scene:
        case.bpy.ops.wm.open_mainfile(filepath=str(args.scene.resolve()))
        names = {
            "base": "Field_Case_Base",
            "fan_case_pair_insert": "Field_Case_Fan_Case_Pair_Lower_TPU_Insert",
            "fan_case_pair_carrier": ("Field_Case_Fan_Case_Pair_Rear_Shallow_Tray"
                                      if args.compact else "Field_Case_Fan_Case_Pair_Mount_Tray"),
            "fan_case_pair_storage_bin": "Field_Case_Fan_Case_Pair_Front_Deep_Tray",
        }
        parts = {key: case.bpy.data.objects[name] for key, name in names.items()}
        references = [obj for obj in case.bpy.data.objects if obj.name.startswith("REFERENCE_ONLY_")]
    else:
        case.clear_scene()
        case.set_units()
        material = case.make_material("Packing_Check", (.4, .5, .6))
        references = case.create_fan_case_pair_reference_mockups(*([material] * 7))
        parts = {
            "base": case.create_base(material),
            "fan_case_pair_insert": case.create_fan_case_pair_insert(material, references),
            "fan_case_pair_carrier": case.create_fan_case_pair_overhead_carrier(material),
            "fan_case_pair_storage_bin": case.create_fan_case_pair_storage_bin(material),
        }
    cap = case.lens_cap.build(vars(case))
    case.validate_built_part("lens_cap", cap)
    dimensions = case.object_world_dimensions(cap)
    if any(abs(value - expected) > .001 for value, expected in zip(dimensions, (48, 48, 11))):
        raise AssertionError("Cap no longer matches the measured reference envelope")
    # Independent solid/empty probes protect the fitting features even when
    # an omission would barely change the overall dimensions or volume.
    for name, size, center, solid in (
        ("floor", (10, 10, .5), (0, 0, .75), True),
        ("cavity", (20, 20, 4), (0, 0, 5), False),
        ("left seat", (.3, 8, .4), (-19.7, 0, 2.5), True),
        ("right seat", (.3, 8, .4), (19.7, 0, 2.5), True),
        ("retention rib", (.8, .05, 3), (0, -20.925, 5), True),
        ("entry flare", (.3, .05, .1), (0, 21.3, 10.5), False),
    ):
        probe = case.add_rounded_box("REGRESSION_Cap_Feature", size, center, bevel=0)
        try:
            overlap = case.static_objects_overlap(cap, probe)
            expected = size[0] * size[1] * size[2] if solid else 0
            if abs(overlap - expected) > max(1e-5, expected * .01):
                raise AssertionError(f"Cap fitting feature changed: {name}, fill={overlap}")
        finally:
            case.bpy.data.objects.remove(probe, do_unlink=True)
    case.validate_built_part("fan_case_pair_insert", parts["fan_case_pair_insert"])
    groups = [[obj for obj in references
               if obj.name.startswith(f"REFERENCE_ONLY_Fan_Case_Assembly_{index}_")]
              for index in (1, 2)]
    case.validate_caps_and_shared_cable(parts, references, groups)

    # Verify the packing check actually rejects a reintroduced center divider.
    divider = case.add_rounded_box("REGRESSION_Cable_Divider", (2, 36, 28),
        (0, -54, case.FAN_CASE_PAIR_INSERT_INSTALLED_Z + 16.5), bevel=0)
    original = parts["fan_case_pair_insert"]
    parts["fan_case_pair_insert"] = divider
    try:
        try:
            case.validate_caps_and_shared_cable(parts, references, groups)
        except ValueError as error:
            if "Shared cable storage obstructed" not in str(error):
                raise
        else:
            raise AssertionError("Packing check accepted a cable-bay divider")
    finally:
        parts["fan_case_pair_insert"] = original
        case.bpy.data.objects.remove(divider, do_unlink=True)
    print("FIELD_CASE_CAP_CABLE_REGRESSION_VALID", flush=True)


if __name__ == "__main__":
    main()
