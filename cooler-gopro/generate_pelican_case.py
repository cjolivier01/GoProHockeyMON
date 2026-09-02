#!/usr/bin/env python3
"""
Generate a Pelican/Storm case model parametrically in Blender.
Creates a complete hard case with lid, base, latches, hinges, and handle.
Outputs STL files for 3D printing with separate files for different materials.
"""

import bpy
import bmesh
import mathutils
import os
from math import radians, sin, cos, pi

# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# ============================================================================
# PARAMETERS (based on analyzed pelican-case.stl)
# ============================================================================

# Target build volume constraints
BUILD_VOLUME_X = 250.0  # mm
BUILD_VOLUME_Y = 250.0  # mm
BUILD_VOLUME_Z = 220.0  # mm

# Calculate scale factor to fit within build volume
# Original dimensions: 346.71 x 153.06 x 345.54 mm
# The height (Z) is the limiting dimension
SCALE_FACTOR_X = BUILD_VOLUME_X / 346.71  # 0.7211
SCALE_FACTOR_Y = BUILD_VOLUME_Y / 153.06  # 1.6333 (not limiting)
SCALE_FACTOR_Z = BUILD_VOLUME_Z / 345.54  # 0.6369
SCALE_FACTOR = min(SCALE_FACTOR_X, SCALE_FACTOR_Y, SCALE_FACTOR_Z)
# Scaled dimensions: 220.83 x 97.49 x 220.00 mm (fits within limits)

# Overall case dimensions (mm) - these are the original full-size dimensions
# Actual output will be scaled by SCALE_FACTOR
CASE_WIDTH = 346.71
CASE_DEPTH = 153.06
CASE_HEIGHT = 345.54

# Wall thickness
WALL_THICKNESS = 3.0
LID_THICKNESS = 3.0
BOTTOM_THICKNESS = 4.0

# Lip and seal dimensions
LIP_DEPTH = 8.0
LIP_HEIGHT = 12.0
SEAL_WIDTH = 4.0
SEAL_HEIGHT = 6.0

# Latch dimensions
LATCH_WIDTH = 25.0
LATCH_HEIGHT = 40.0
LATCH_DEPTH = 15.0
LATCH_HOOK_LENGTH = 20.0

# Hinge dimensions
HINGE_WIDTH = 30.0
HINGE_BARREL_DIAMETER = 8.0
HINGE_COUNT = 3

# Handle dimensions
HANDLE_WIDTH = 120.0
HANDLE_HEIGHT = 80.0
HANDLE_THICKNESS = 20.0
HANDLE_GRIP_DIAMETER = 25.0

# Corner radius
CORNER_RADIUS = 8.0

# Colors for visualization (R, G, B, Alpha)
COLOR_CASE_BODY = (0.2, 0.2, 0.2, 1.0)    # Dark grey - PLA/PETG
COLOR_SEAL = (0.1, 0.1, 0.1, 1.0)          # Black - TPU
COLOR_LATCH = (0.3, 0.3, 0.3, 1.0)         # Grey - PETG-HF

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_material(name, color):
    """Create a material with specified color."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
    return mat

def add_rounded_box(width, depth, height, radius, name="Box"):
    """Create a box with rounded corners."""
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (width/2, depth/2, height/2)
    bpy.ops.object.transform_apply(scale=True)

    # Add bevel modifier for rounded edges
    bevel = obj.modifiers.new(name="Bevel", type='BEVEL')
    bevel.width = radius
    bevel.segments = 4
    bevel.limit_method = 'ANGLE'
    bevel.angle_limit = radians(30)

    return obj

def shell_object(obj, thickness):
    """Add a solidify modifier to create a shell."""
    solidify = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
    solidify.thickness = -thickness
    solidify.offset = 1
    return obj

# ============================================================================
# CREATE MATERIALS
# ============================================================================

mat_case = create_material("Material_Case_PLA_PETG", COLOR_CASE_BODY)
mat_seal = create_material("Material_Seal_TPU", COLOR_SEAL)
mat_latch = create_material("Material_Latch_PETG_HF", COLOR_LATCH)

# ============================================================================
# CREATE CASE BASE
# ============================================================================

def create_case_base():
    """Create the main case body."""
    # Outer shell
    outer = add_rounded_box(
        CASE_WIDTH,
        CASE_DEPTH,
        CASE_HEIGHT * 0.6,  # Base is 60% of total height
        CORNER_RADIUS,
        name="Case_Base_Outer"
    )
    outer.location.z = -CASE_HEIGHT * 0.2

    # Apply modifier
    bpy.ops.object.modifier_apply(modifier="Bevel")

    # Create inner cavity
    inner = add_rounded_box(
        CASE_WIDTH - WALL_THICKNESS * 2,
        CASE_DEPTH - WALL_THICKNESS * 2,
        CASE_HEIGHT * 0.6 - BOTTOM_THICKNESS,
        CORNER_RADIUS - WALL_THICKNESS,
        name="Case_Base_Inner"
    )
    inner.location.z = -CASE_HEIGHT * 0.2 + BOTTOM_THICKNESS/2
    bpy.ops.object.modifier_apply(modifier="Bevel")

    # Boolean difference to create hollow shell
    bpy.context.view_layer.objects.active = outer
    outer.select_set(True)
    bool_mod = outer.modifiers.new(name="Boolean", type='BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = inner
    bpy.ops.object.modifier_apply(modifier="Boolean")

    # Delete inner object
    bpy.data.objects.remove(inner)

    # Add lip for lid seal
    bpy.ops.mesh.primitive_cube_add(size=1)
    lip = bpy.context.active_object
    lip.name = "Case_Base_Lip"
    lip.scale = ((CASE_WIDTH - WALL_THICKNESS * 2 - 2) / 2,
                 (CASE_DEPTH - WALL_THICKNESS * 2 - 2) / 2,
                 LIP_HEIGHT / 2)
    lip.location.z = CASE_HEIGHT * 0.4 - CASE_HEIGHT * 0.2 - LIP_HEIGHT/2
    bpy.ops.object.transform_apply(scale=True)

    # Join lip to base
    bpy.ops.object.select_all(action='DESELECT')
    outer.select_set(True)
    lip.select_set(True)
    bpy.context.view_layer.objects.active = outer
    bpy.ops.object.join()

    outer.data.materials.append(mat_case)
    return outer

# ============================================================================
# CREATE LID
# ============================================================================

def create_lid():
    """Create the case lid."""
    # Outer shell
    outer = add_rounded_box(
        CASE_WIDTH,
        CASE_DEPTH,
        CASE_HEIGHT * 0.4,  # Lid is 40% of total height
        CORNER_RADIUS,
        name="Case_Lid_Outer"
    )
    outer.location.z = CASE_HEIGHT * 0.3
    bpy.ops.object.modifier_apply(modifier="Bevel")

    # Create inner cavity
    inner = add_rounded_box(
        CASE_WIDTH - WALL_THICKNESS * 2,
        CASE_DEPTH - WALL_THICKNESS * 2,
        CASE_HEIGHT * 0.4 - LID_THICKNESS,
        CORNER_RADIUS - WALL_THICKNESS,
        name="Case_Lid_Inner"
    )
    inner.location.z = CASE_HEIGHT * 0.3 - LID_THICKNESS/2
    bpy.ops.object.modifier_apply(modifier="Bevel")

    # Boolean difference
    bpy.context.view_layer.objects.active = outer
    outer.select_set(True)
    bool_mod = outer.modifiers.new(name="Boolean", type='BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = inner
    bpy.ops.object.modifier_apply(modifier="Boolean")

    bpy.data.objects.remove(inner)

    outer.data.materials.append(mat_case)
    return outer

# ============================================================================
# CREATE SEAL
# ============================================================================

def create_seal():
    """Create TPU seal gasket."""
    bpy.ops.mesh.primitive_torus_add(
        major_radius=(CASE_WIDTH + CASE_DEPTH) / 4,
        minor_radius=SEAL_HEIGHT / 2
    )
    seal = bpy.context.active_object
    seal.name = "Seal_TPU"
    seal.scale.x = CASE_WIDTH / ((CASE_WIDTH + CASE_DEPTH) / 2)
    seal.scale.y = CASE_DEPTH / ((CASE_WIDTH + CASE_DEPTH) / 2)
    seal.location.z = CASE_HEIGHT * 0.4 - CASE_HEIGHT * 0.2 - SEAL_HEIGHT
    bpy.ops.object.transform_apply(scale=True)

    seal.data.materials.append(mat_seal)
    return seal

# ============================================================================
# CREATE LATCHES
# ============================================================================

def create_latch(position, name_suffix):
    """Create a latch assembly."""
    # Latch body
    bpy.ops.mesh.primitive_cube_add(size=1)
    latch_body = bpy.context.active_object
    latch_body.name = f"Latch_Body_{name_suffix}"
    latch_body.scale = (LATCH_WIDTH/2, LATCH_DEPTH/2, LATCH_HEIGHT/2)
    latch_body.location = position
    bpy.ops.object.transform_apply(scale=True)

    # Latch hook
    bpy.ops.mesh.primitive_cube_add(size=1)
    hook = bpy.context.active_object
    hook.name = f"Latch_Hook_{name_suffix}"
    hook.scale = (LATCH_WIDTH/3/2, LATCH_HOOK_LENGTH/2, LATCH_HEIGHT/3/2)
    hook.location = (position[0], position[1] + LATCH_DEPTH/2 + LATCH_HOOK_LENGTH/2, position[2])
    bpy.ops.object.transform_apply(scale=True)

    # Join hook to body
    bpy.ops.object.select_all(action='DESELECT')
    latch_body.select_set(True)
    hook.select_set(True)
    bpy.context.view_layer.objects.active = latch_body
    bpy.ops.object.join()

    # Add cylinder for pivot
    bpy.ops.mesh.primitive_cylinder_add(
        radius=3,
        depth=LATCH_WIDTH,
        rotation=(0, radians(90), 0)
    )
    pivot = bpy.context.active_object
    pivot.name = f"Latch_Pivot_{name_suffix}"
    pivot.location = position

    # Join pivot
    bpy.ops.object.select_all(action='DESELECT')
    latch_body.select_set(True)
    pivot.select_set(True)
    bpy.context.view_layer.objects.active = latch_body
    bpy.ops.object.join()

    latch_body.data.materials.append(mat_latch)
    return latch_body

def create_latches():
    """Create latch pairs."""
    latches = []

    # Front center latch
    latch_z = CASE_HEIGHT * 0.1 - CASE_HEIGHT * 0.2
    latch1 = create_latch((0, CASE_DEPTH/2 + LATCH_DEPTH, latch_z), "Front")
    latches.append(latch1)

    # Front latches left and right
    latch2 = create_latch((-CASE_WIDTH/3, CASE_DEPTH/2 + LATCH_DEPTH, latch_z), "Front_L")
    latch3 = create_latch((CASE_WIDTH/3, CASE_DEPTH/2 + LATCH_DEPTH, latch_z), "Front_R")
    latches.extend([latch2, latch3])

    return latches

# ============================================================================
# CREATE HINGES
# ============================================================================

def create_hinge(position, name_suffix):
    """Create a hinge barrel."""
    bpy.ops.mesh.primitive_cylinder_add(
        radius=HINGE_BARREL_DIAMETER/2,
        depth=HINGE_WIDTH,
        rotation=(0, radians(90), 0)
    )
    hinge = bpy.context.active_object
    hinge.name = f"Hinge_{name_suffix}"
    hinge.location = position
    hinge.data.materials.append(mat_latch)
    return hinge

def create_hinges():
    """Create hinge array."""
    hinges = []
    hinge_y = -CASE_DEPTH/2 - HINGE_BARREL_DIAMETER
    hinge_z = CASE_HEIGHT * 0.4 - CASE_HEIGHT * 0.2

    for i in range(HINGE_COUNT):
        x_pos = -CASE_WIDTH/2 + CASE_WIDTH/(HINGE_COUNT+1) * (i+1)
        hinge = create_hinge((x_pos, hinge_y, hinge_z), f"{i}")
        hinges.append(hinge)

    return hinges

# ============================================================================
# CREATE HANDLE
# ============================================================================

def create_handle():
    """Create carrying handle."""
    # Handle bracket left
    bpy.ops.mesh.primitive_cube_add(size=1)
    bracket_l = bpy.context.active_object
    bracket_l.name = "Handle_Bracket_L"
    bracket_l.scale = (HANDLE_THICKNESS/2, HANDLE_THICKNESS/2, HANDLE_HEIGHT/2)
    bracket_l.location = (-HANDLE_WIDTH/2, 0, CASE_HEIGHT * 0.5 - HANDLE_HEIGHT/2)
    bpy.ops.object.transform_apply(scale=True)

    # Handle bracket right
    bpy.ops.mesh.primitive_cube_add(size=1)
    bracket_r = bpy.context.active_object
    bracket_r.name = "Handle_Bracket_R"
    bracket_r.scale = (HANDLE_THICKNESS/2, HANDLE_THICKNESS/2, HANDLE_HEIGHT/2)
    bracket_r.location = (HANDLE_WIDTH/2, 0, CASE_HEIGHT * 0.5 - HANDLE_HEIGHT/2)
    bpy.ops.object.transform_apply(scale=True)

    # Handle grip (cylinder)
    bpy.ops.mesh.primitive_cylinder_add(
        radius=HANDLE_GRIP_DIAMETER/2,
        depth=HANDLE_WIDTH,
        rotation=(0, radians(90), 0)
    )
    grip = bpy.context.active_object
    grip.name = "Handle_Grip"
    grip.location = (0, 0, CASE_HEIGHT * 0.5)

    # Join all handle parts
    bpy.ops.object.select_all(action='DESELECT')
    bracket_l.select_set(True)
    bracket_r.select_set(True)
    grip.select_set(True)
    bpy.context.view_layer.objects.active = bracket_l
    bpy.ops.object.join()

    bracket_l.data.materials.append(mat_latch)
    bracket_l.name = "Handle_Assembly"
    return bracket_l

# ============================================================================
# MAIN ASSEMBLY
# ============================================================================

print("\n" + "="*60)
print("GENERATING PELICAN CASE MODEL")
print("="*60 + "\n")

print("Creating case base...")
case_base = create_case_base()

print("Creating lid...")
lid = create_lid()

print("Creating seal gasket...")
seal = create_seal()

print("Creating latches...")
latches = create_latches()

print("Creating hinges...")
hinges = create_hinges()

print("Creating handle...")
handle = create_handle()

# ============================================================================
# ORGANIZE IN COLLECTIONS
# ============================================================================

print("\nOrganizing into collections...")

# Create collections
if "Case_PLA_PETG" not in bpy.data.collections:
    col_case = bpy.data.collections.new("Case_PLA_PETG")
    bpy.context.scene.collection.children.link(col_case)
else:
    col_case = bpy.data.collections["Case_PLA_PETG"]

if "Hardware_PETG_HF" not in bpy.data.collections:
    col_hardware = bpy.data.collections.new("Hardware_PETG_HF")
    bpy.context.scene.collection.children.link(col_hardware)
else:
    col_hardware = bpy.data.collections["Hardware_PETG_HF"]

if "Seal_TPU" not in bpy.data.collections:
    col_seal = bpy.data.collections.new("Seal_TPU")
    bpy.context.scene.collection.children.link(col_seal)
else:
    col_seal = bpy.data.collections["Seal_TPU"]

# Move objects to collections
for obj in [case_base, lid]:
    if obj.name in bpy.context.scene.collection.objects:
        col_case.objects.link(obj)
        bpy.context.scene.collection.objects.unlink(obj)
    elif obj not in col_case.objects.values():
        col_case.objects.link(obj)

for obj in latches + hinges + [handle]:
    if obj.name in bpy.context.scene.collection.objects:
        col_hardware.objects.link(obj)
        bpy.context.scene.collection.objects.unlink(obj)
    elif obj not in col_hardware.objects.values():
        col_hardware.objects.link(obj)

if seal.name in bpy.context.scene.collection.objects:
    col_seal.objects.link(seal)
    bpy.context.scene.collection.objects.unlink(seal)
elif seal not in col_seal.objects.values():
    col_seal.objects.link(seal)

# ============================================================================
# APPLY SCALE FACTOR
# ============================================================================

print(f"\nApplying scale factor: {SCALE_FACTOR:.4f}")
print(f"Original dimensions: {CASE_WIDTH:.2f} x {CASE_DEPTH:.2f} x {CASE_HEIGHT:.2f} mm")
print(f"Scaled dimensions: {CASE_WIDTH*SCALE_FACTOR:.2f} x {CASE_DEPTH*SCALE_FACTOR:.2f} x {CASE_HEIGHT*SCALE_FACTOR:.2f} mm")

# Scale all objects
all_objects = [case_base, lid, seal, handle] + latches + hinges
for obj in all_objects:
    obj.scale = (SCALE_FACTOR, SCALE_FACTOR, SCALE_FACTOR)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.ops.object.transform_apply(scale=True)

# ============================================================================
# EXPORT STL FILES
# ============================================================================

def validate_export(filepath, min_size=100):
    """Validate that export file was created successfully."""
    if not os.path.exists(filepath):
        raise RuntimeError(f"Export failed: file not created: {filepath}")
    if os.path.getsize(filepath) < min_size:
        raise RuntimeError(f"Export failed: file too small (possibly corrupt): {filepath}")

print("\nExporting STL files for 3D printing...")

output_dir = os.path.dirname(bpy.data.filepath) or os.getcwd()

# Export PLA/PETG parts (case body)
bpy.ops.object.select_all(action='DESELECT')
case_base.select_set(True)
lid.select_set(True)
export_path = os.path.join(output_dir, "pelican_case_body_PLA_PETG.stl")
bpy.ops.wm.stl_export(filepath=export_path, export_selected_objects=True)
validate_export(export_path)
print(f"  Exported: pelican_case_body_PLA_PETG.stl")

# Export PETG-HF parts (hardware)
bpy.ops.object.select_all(action='DESELECT')
for obj in latches + hinges + [handle]:
    obj.select_set(True)
export_path = os.path.join(output_dir, "pelican_case_hardware_PETG_HF.stl")
bpy.ops.wm.stl_export(filepath=export_path, export_selected_objects=True)
validate_export(export_path)
print(f"  Exported: pelican_case_hardware_PETG_HF.stl")

# Export TPU parts (seal)
bpy.ops.object.select_all(action='DESELECT')
seal.select_set(True)
export_path = os.path.join(output_dir, "pelican_case_seal_TPU.stl")
bpy.ops.wm.stl_export(filepath=export_path, export_selected_objects=True)
validate_export(export_path)
print(f"  Exported: pelican_case_seal_TPU.stl")

# Export complete assembly
bpy.ops.object.select_all(action='SELECT')
export_path = os.path.join(output_dir, "pelican_case_complete_assembly.stl")
bpy.ops.wm.stl_export(filepath=export_path, export_selected_objects=True)
validate_export(export_path)
print(f"  Exported: pelican_case_complete_assembly.stl")

# Save blend file
blend_path = os.path.join(output_dir, "pelican_case_parametric.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"  Saved: pelican_case_parametric.blend")

print("\n" + "="*60)
print("PELICAN CASE GENERATION COMPLETE!")
print("="*60)
print(f"\nFiles created:")
print(f"  - pelican_case_body_PLA_PETG.stl (Main case body - print with PLA or PETG)")
print(f"  - pelican_case_hardware_PETG_HF.stl (Latches, hinges, handle - print with PETG-HF)")
print(f"  - pelican_case_seal_TPU.stl (Gasket seal - print with TPU)")
print(f"  - pelican_case_complete_assembly.stl (Complete assembly for reference)")
print(f"  - pelican_case_parametric.blend (Editable Blender file)")
print("\n" + "="*60 + "\n")
