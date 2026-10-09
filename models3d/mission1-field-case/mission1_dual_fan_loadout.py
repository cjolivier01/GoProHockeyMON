"""Dual-fan inserts for the unchanged expanded Mission 1 shell.

The upper cable/five-remote organizer is shared with the fan-case loadout.
The two-prong mount mates with the arm's three-prong adapter and extends in
the fork direction toward the front wall. Dimensions come from the parent
generator; this module never changes its shell or companion configuration.
"""

import math
from types import SimpleNamespace

import bpy
from mathutils import Matrix, Vector


def build_loadout(namespace, parts, material):
    f = SimpleNamespace(**namespace)
    lift, shift = f.DUAL_FAN_STORAGE_LIFT, f.DUAL_FAN_STORAGE_Y_SHIFT
    tray_z = f.DUAL_FAN_TRAY_INSTALLED_Z
    floor_z = f.FAN_CRADLE_FLOOR_THICKNESS + lift
    height = f.FAN_CRADLE_HEIGHT + lift
    profile = f.printable_insert_profile()
    for (z0, inset0), (z1, inset1) in f.pairwise(profile):
        if z0 <= height <= z1:
            inset = inset0 + (inset1 - inset0) * (height - z0) / (z1 - z0)
            break
    cradle = f.rounded_profile_prism("Field_Case_Expanded_Dual_Fan_Cradle",
        (*((z, inset) for z, inset in profile if z < height), (height, inset)))
    x0, x1, y0, y1 = f.DUAL_FAN_STORAGE["cavity_bounds"]
    pocket = f.add_rounded_prism("Dual_Fan_Rear_Contact_Pocket",
        x1 - x0, y1 - y0, floor_z, height + .2, 3.0,
        ((x0 + x1) / 2, (y0 + y1) / 2 + shift))
    f.difference_from(cradle, pocket)
    f.translate_object(cradle, (0, 0, f.FAN_CRADLE_INSTALLED_Z))

    # Reuse the proven camera, door, battery and storage-pocket molds. Move
    # their complete layout into the extra 22 mm of shell depth together.
    changes = {
        "CAMERA_PLACEMENTS": f.DUAL_FAN_CAMERA_PLACEMENTS,
        "BATTERY_CENTERS": f.DUAL_FAN_BATTERY_CENTERS,
        "SIDE_STORAGE_POCKET_CENTERS": tuple((x, y + shift)
                                            for x, y in f.SIDE_STORAGE_POCKET_CENTERS),
        "BATTERY_DOOR_SLOT_CENTERS": tuple((x, y + shift)
                                          for x, y in f.BATTERY_DOOR_SLOT_CENTERS),
        # Open through the front edge so a bolted mount passes during lifting.
        # The 30 mm thumb head ends 7.6 mm left of the pivot. Include
        # its entire outside face, with 2 mm clearance during extraction.
        "FAN_ARM_PASSAGE_BOUNDS": (
            min(-8.0, f.DUAL_FAN_STORAGE["placement"][0] - 7.6 - 30.0 - 2.0),
            31.5, -86.0, -19.0 + shift),
    }
    old = {key: namespace[key] for key in changes}
    namespace.update(changes)
    try:
        tray = f.create_equipment_tray(material)
        f.translate_object(tray, (0, 0, tray_z))
        refs = []
        for index, placement in enumerate(changes["CAMERA_PLACEMENTS"], 1):
            obj = f.build_placed_camera(f"REFERENCE_ONLY_MISSION1_{index}", placement)
            f.translate_object(obj, (0, 0, tray_z))
            # The bounds-expanded mold can shift small control protrusions
            # while anchoring its floor. Include the exact seated mesh too.
            cutter = obj.copy()
            cutter.data = obj.data.copy()
            bpy.context.collection.objects.link(cutter)
            f.difference_from(tray, cutter)
            # Sweep the camera silhouette upward so its side controls cannot
            # catch the pocket rim when removing the camera from the TPU tray.
            minimum, _maximum = f.object_world_bounds(obj)
            silhouette = f.fan_case_assembly_extraction_profile((obj,), clearance=.2)
            cutter = f.extrude_planar_region("Camera_Upward_Extraction_Relief",
                silhouette, minimum.z, tray_z + f.TRAY_HEIGHT + .4)
            f.difference_from(tray, cutter)
            refs.append(obj)
        for index, center in enumerate(changes["BATTERY_CENTERS"], 1):
            obj = f.add_rounded_prism(f"REFERENCE_ONLY_Enduro2_{index}",
                f.BATTERY_THICKNESS, f.BATTERY_WIDTH,
                tray_z + f.BATTERY_FLOOR_Z,
                tray_z + f.BATTERY_FLOOR_Z + f.BATTERY_HEIGHT, 1.6, center)
            refs.append(obj)
        for index, center in enumerate(changes["BATTERY_DOOR_SLOT_CENTERS"], 1):
            obj = f.add_rounded_prism(f"REFERENCE_ONLY_MISSION1_Battery_Cage_Door_{index}",
                f.BATTERY_DOOR_SIZE[0], f.BATTERY_DOOR_SIZE[1],
                tray_z + f.BATTERY_DOOR_SLOT_FLOOR_Z,
                tray_z + f.BATTERY_DOOR_SLOT_FLOOR_Z + f.BATTERY_DOOR_SIZE[2], 1.3, center)
            refs.append(obj)
    finally:
        namespace.update(old)

    width = f.CASE_WIDTH - 2 * (f.WALL_THICKNESS + f.EQUIPMENT_TRAY_SIDE_CLEARANCE)
    depth = f.CASE_DEPTH - 2 * (f.WALL_THICKNESS + f.EQUIPMENT_TRAY_SIDE_CLEARANCE)

    def stack_ring(name, bottom, top):
        return f.rounded_ring(name, (width, depth), (width - 8, depth - 8),
            bottom, top, f.EQUIPMENT_TRAY_CORNER_RADIUS,
            f.EQUIPMENT_TRAY_CORNER_RADIUS - 4)

    riser = stack_ring("Field_Case_Dual_Fan_Tray_Riser", f.DUAL_FAN_RISER_BOTTOM_Z, f.DUAL_FAN_RISER_TOP_Z)
    spacer = stack_ring("Field_Case_Dual_Fan_Storage_Spacer",
                        f.DUAL_FAN_SPACER_BOTTOM_Z, f.DUAL_FAN_SPACER_TOP_Z)
    for ring, bottom, top in ((riser, f.DUAL_FAN_RISER_BOTTOM_Z, f.DUAL_FAN_RISER_TOP_Z),
                              (spacer, f.DUAL_FAN_SPACER_BOTTOM_Z, f.DUAL_FAN_SPACER_TOP_Z)):
        f.difference_from(ring, f.add_rounded_prism("Open_Attached_Mount_Passage",
            f.DUAL_FAN_MOUNT_CLEARANCE_WIDTH + 2.0, 9.0,
            bottom - .2, top + .2, 1.0,
            (f.DUAL_FAN_STORAGE["placement"][0], -depth / 2)))
    added = {"fan_cradle": cradle, "equipment_tray": tray,
             "dual_fan_riser": riser, "dual_fan_spacer": spacer}
    for key, origin in (("fan_cradle", f.FAN_CRADLE_INSTALLED_Z),
                        ("equipment_tray", tray_z),
                        ("dual_fan_riser", f.DUAL_FAN_RISER_BOTTOM_Z),
                        ("dual_fan_spacer", f.DUAL_FAN_SPACER_BOTTOM_Z)):
        added[key]["print_origin_z"] = origin
        f.assign_material(added[key], material)

    dual = f.dual_fan
    saved = {key: getattr(dual, key) for key in
             ("CLEAR_SCENE", "EXPORT_STL", "GOPRO_ADAPTER_PRONG_COUNTS", "GOPRO_ADAPTER_PRONG_COUNT")}
    try:
        dual.CLEAR_SCENE = False
        dual.EXPORT_STL = False
        dual.GOPRO_ADAPTER_PRONG_COUNTS = (3,)
        dual.GOPRO_ADAPTER_PRONG_COUNT = None
        before = {o.as_pointer() for o in bpy.data.objects}
        holder = dual.build_dual_fan()
        adapter = next(o for o in bpy.data.objects if o.as_pointer() not in before
                       and o.name.startswith("Detachable_GoPro_Adapter_3_Prong"))
        mate = dual.create_gopro_adapter(2)
    finally:
        for key, value in saved.items():
            setattr(dual, key, value)
    px, py = f.DUAL_FAN_STORAGE["placement"]
    py += shift
    translation_z = f.FAN_STORAGE_TRANSLATION_Z + lift
    mating_y = dual.mount_stalk_center_y() - dual.MOUNT_BLOCK_DEPTH_Y / 2 - dual.GOPRO_ADAPTER_MATING_GAP
    joint = Vector((px, py + mating_y - dual.GOPRO_PIVOT_FROM_MATING_FACE_Y,
                    translation_z - dual.mount_block_center_z() + dual.GOPRO_PIVOT_BELOW_MOUNT_HOLES_Z))
    for label, obj in (("Holder", holder), ("Three_Prong_Adapter", adapter), ("Attached_Two_Prong_Mount", mate)):
        f.select_only(obj)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        obj.rotation_euler.y = math.pi
        obj.location = (px, py, translation_z)
        bpy.context.view_layer.update()
        if obj == mate:
            # Keep the fork planes parallel and interleave the two fingers
            # between the three. The plate continues outward along -Y.
            obj.matrix_world = (Matrix.Translation(joint) @ Matrix.Rotation(math.pi, 4, "Z")
                                @ Matrix.Translation(-joint) @ obj.matrix_world)
        obj.name = "REFERENCE_ONLY_Stored_Dual_Fan_" + label
        refs.append(obj)
    # The stored nut boss is on +X after the storage rotation, so the screw
    # enters from -X. Reserve a 20 mm diameter, 30 mm long thumb head there.
    screw = f.add_cylinder_x("REFERENCE_ONLY_Stored_Dual_Fan_Mount_Screw",
        2.45, 20.0, (joint.x + 1.15, joint.y, joint.z))
    head = f.add_cylinder_x("GoPro_Thumb_Head_Clearance", 10.0, 30.0,
        (joint.x - 22.6, joint.y, joint.z))
    # Head ends at joint.x - 7.6, just outside the leftmost fork face.
    f.union_into(screw, head)
    refs.append(screw)
    fan_refs = []
    for fan in f.DUAL_FAN_STORAGE["fan_specs"]:
        installed_depth = fan["depth"] + f.FAN_STORAGE_PAD_ALLOWANCE_MM
        obj = f.add_rounded_box(f"REFERENCE_ONLY_Installed_80mm_Fan_{fan['index']}",
            (80, 80, installed_depth),
            (-fan["center_x"] + px, py,
             translation_z - (dual.fan_grill_z_bounds()[0] - installed_depth / 2)), bevel=2)
        fan_refs.append(obj)
        refs.append(obj)
    extension = f.add_rounded_prism("REFERENCE_ONLY_Stored_Dual_Fan_Mount_Clearance",
        f.DUAL_FAN_MOUNT_CLEARANCE_WIDTH, f.DUAL_FAN_MOUNT_REACH,
        joint.z - f.DUAL_FAN_MOUNT_CLEARANCE_HEIGHT / 2,
        joint.z + f.DUAL_FAN_MOUNT_CLEARANCE_HEIGHT / 2, 1.0,
        (joint.x, joint.y - f.DUAL_FAN_MOUNT_REACH / 2))
    for obj in refs:
        f.assign_material(obj, material)
    f.assign_material(extension, material)
    parts.update(added)
    validate_loadout(f, parts, refs, extension, holder, adapter, mate, fan_refs)
    refs.append(extension)
    return added, refs


def validate_loadout(f, parts, refs, extension, holder, adapter, mate, fan_refs):
    """Check physical packing, bearings, shared cord/remote tray and both roofs."""
    if (f.CASE_WIDTH, f.CASE_DEPTH, f.BASE_HEIGHT) != (234.0, 180.0, 160.0):
        raise ValueError("Dual-fan inserts changed the shared shell dimensions")
    if f.dual_fan.MATERIAL_MODE != "TPU":
        raise ValueError("The dual-fan holder must default to TPU")
    if not 0 < f.DUAL_FAN_MOUNT_REACH <= 50.8:
        raise ValueError("Sideways mount reach must be positive and no more than two inches")

    def volume(a, b, shift=0):
        return f.exact_transformed_intersection(a, b,
            first_location=a.location.copy(), first_rotation=a.rotation_euler.copy(),
            second_location=b.location + Vector((0, 0, shift)),
            second_rotation=b.rotation_euler.copy())[1]

    keys = ("fan_cradle", "dual_fan_riser", "equipment_tray", "dual_fan_spacer", "accessory_organizer")
    for index, key in enumerate(keys):
        obj = parts[key]
        if volume(parts["base"], obj, shift=.001) > 1e-5:
            raise ValueError("Dual-fan insert intersects shared shell: " + key)
        for other_key in keys[index + 1:]:
            if volume(obj, parts[other_key], shift=.001) > 1e-5:
                raise ValueError(f"Dual-fan inserts overlap: {key}/{other_key}")
        for reference in (*refs, extension):
            overlap = volume(obj, reference, shift=.001)
            # Exact subtraction of the true camera leaves coincident sloped
            # faces; float32 Boolean noise is under 0.01 cubic millimeters.
            tolerance = .01 if reference.name.startswith("REFERENCE_ONLY_MISSION1_") else 1e-5
            if overlap > tolerance:
                raise ValueError(f"Dual-fan loadout intersects {key}: {reference.name} volume={overlap}")
    for obj in (*refs, extension):
        if volume(parts["base"], obj) > 1e-5:
            raise ValueError("Stored dual-fan equipment intersects case: " + obj.name)
        for lid_key in ("lid", "tpu_snap_lid"):
            overlap = f.exact_transformed_intersection(parts[lid_key], obj,
                first_location=f.installed_lid_pose(0)[0],
                first_rotation=f.installed_lid_pose(0)[1],
                second_location=obj.location.copy(), second_rotation=obj.rotation_euler.copy())[1]
            if overlap > 1e-5:
                raise ValueError("Stored dual-fan equipment intersects closed lid: " + obj.name)
    # The mount clearance overlaps its own adapter; all other equipment must
    # remain outside it. Forks themselves must mate without mesh interference.
    screws = [obj for obj in refs if obj.name.startswith("REFERENCE_ONLY_Stored_Dual_Fan_Mount_Screw")]
    assembly_refs = (holder, adapter, mate, *screws)
    for obj in refs:
        if obj not in assembly_refs and volume(extension, obj) > 1e-5:
            raise ValueError("Attached mount clearance blocked by stored equipment: " + obj.name)
    if volume(adapter, mate) > 1e-5:
        raise ValueError("Two-prong and three-prong adapter fingers do not interleave")
    for screw in screws:
        for obj in (holder, adapter, mate):
            if volume(obj, screw) > 1e-5:
                raise ValueError("GoPro mount screw/head clearance blocked: " + obj.name)
    equipment = [r for r in refs if r not in (*assembly_refs, *fan_refs)]
    for index, obj in enumerate(equipment):
        for other in (*equipment[index + 1:], *assembly_refs, *fan_refs):
            if volume(obj, other) > 1e-5:
                raise ValueError(f"Stored dual-fan equipment overlaps: {obj.name}/{other.name}")
    for support, supported in (("base", "fan_cradle"), ("base", "dual_fan_riser"),
                               ("dual_fan_riser", "equipment_tray"),
                               ("equipment_tray", "dual_fan_spacer"),
                               ("dual_fan_spacer", "accessory_organizer")):
        if volume(parts[support], parts[supported], shift=-.05) < 1.0:
            raise ValueError("Dual-fan stack lacks a bearing: " + supported)
    if sum(volume(parts["fan_cradle"], obj, shift=-.05) for obj in (holder, *fan_refs)) < 1.0:
        raise ValueError("Dual-fan assembly does not seat on its cradle")
    validate_extraction_paths(f, parts, refs, extension, assembly_refs, fan_refs)
    for key in keys[:-1]:
        f.validate_built_part(key, parts[key])
        f.validate_print_layer_connectivity(parts[key])
    print("FIELD_CASE_EXPANDED_DUAL_FAN_VALID shell=234x180x160 batteries=6 "
          f"shared_cable_remote_organizer=yes mount_reach={f.DUAL_FAN_MOUNT_REACH:.1f}mm "
          "forks=parallel_and_interleaved lid=glued_foam", flush=True)


def validate_extraction_paths(f, parts, refs, extension, assembly_refs, fan_refs):
    """Sample upward removal at 1 mm intervals after removing the upper layers.

    Remove organizer, spacer, loaded camera tray, then riser before lifting
    the assembled fan. Keep the bolted mount, thumb screw and reserved longer
    continuation attached throughout. Bounds reject unrelated pairs cheaply.
    """
    def sweep(label, moving, obstacles, tolerance=1e-5):
        low, high = f.object_world_bounds(moving)
        bounds = [(obj, *f.object_world_bounds(obj)) for obj in obstacles]
        limit = max((b.z - low.z for _obj, _a, b in bounds), default=0)
        for lift in (.1, *range(1, math.ceil(limit) + 2)):
            for obstacle, obstacle_low, obstacle_high in bounds:
                if (high.x <= obstacle_low.x or low.x >= obstacle_high.x
                        or high.y <= obstacle_low.y or low.y >= obstacle_high.y
                        or high.z + lift <= obstacle_low.z or low.z + lift >= obstacle_high.z):
                    continue
                overlap = f.exact_transformed_intersection(moving, obstacle,
                    first_location=moving.location + Vector((0, 0, lift)),
                    first_rotation=moving.rotation_euler.copy(),
                    second_location=obstacle.location.copy(),
                    second_rotation=obstacle.rotation_euler.copy())[1]
                if overlap > tolerance:
                    raise ValueError(f"Dual-fan {label} extraction blocked by {obstacle.name} "
                                     f"at lift={lift}mm volume={overlap}")

    stationary = (*assembly_refs, *fan_refs, extension)
    for key in ("dual_fan_spacer", "equipment_tray", "dual_fan_riser"):
        sweep(key, parts[key], (parts["base"], *stationary))
    for obj in stationary:
        sweep("assembled fan", obj, (parts["base"], parts["fan_cradle"]))
    for camera in (o for o in refs if o.name.startswith("REFERENCE_ONLY_MISSION1_")):
        sweep("camera", camera, (parts["equipment_tray"],), tolerance=.01)
    print("FIELD_CASE_DUAL_FAN_EXTRACTION_VALID step=1mm layers=organizer,spacer,tray,riser,fan", flush=True)
