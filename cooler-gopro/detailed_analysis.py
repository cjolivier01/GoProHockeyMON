#!/usr/bin/env python3
"""Detailed analysis of pelican case to extract parametric dimensions."""

import bpy
import bmesh
import mathutils
from collections import defaultdict

# Clear existing objects
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Import STL
bpy.ops.wm.stl_import(filepath='pelican-case.stl')
obj = bpy.context.active_object

print(f"\n=== Pelican Case Detailed Analysis ===\n")

# Dimensions
bbox = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
min_x = min(v.x for v in bbox)
max_x = max(v.x for v in bbox)
min_y = min(v.y for v in bbox)
max_y = max(v.y for v in bbox)
min_z = min(v.z for v in bbox)
max_z = max(v.z for v in bbox)

width = max_x - min_x
depth = max_y - min_y
height = max_z - min_z

print(f"Overall Dimensions:")
print(f"  Width (X):  {width:.2f} mm")
print(f"  Depth (Y):  {depth:.2f} mm")
print(f"  Height (Z): {height:.2f} mm")

# Analyze Z slices to understand structure
bm = bmesh.new()
bm.from_mesh(obj.data)

# Sample Z heights
z_samples = []
for v in bm.verts:
    z_samples.append(v.co.z)

z_samples.sort()
unique_z = []
tolerance = 0.5
for z in z_samples:
    if not unique_z or abs(z - unique_z[-1]) > tolerance:
        unique_z.append(z)

print(f"\n=== Z-level Analysis (key heights) ===")
print(f"Number of distinct Z levels: {len(unique_z)}")
print(f"Bottom: {unique_z[0]:.2f}")
print(f"Top: {unique_z[-1]:.2f}")

# Analyze vertices at specific Z levels
def analyze_z_level(z_target, tolerance=1.0):
    """Find vertices near a specific Z level."""
    verts_at_z = [v for v in bm.verts if abs(v.co.z - z_target) < tolerance]
    if not verts_at_z:
        return None

    xs = [v.co.x for v in verts_at_z]
    ys = [v.co.y for v in verts_at_z]

    return {
        'count': len(verts_at_z),
        'x_range': (min(xs), max(xs)),
        'y_range': (min(ys), max(ys)),
    }

# Check bottom, middle, and top
print(f"\nBottom level ({unique_z[0]:.2f}):")
bottom = analyze_z_level(unique_z[0])
if bottom:
    print(f"  Vertices: {bottom['count']}")
    print(f"  X range: {bottom['x_range'][0]:.2f} to {bottom['x_range'][1]:.2f}")
    print(f"  Y range: {bottom['y_range'][0]:.2f} to {bottom['y_range'][1]:.2f}")

mid_z = (unique_z[0] + unique_z[-1]) / 2
print(f"\nMid level ({mid_z:.2f}):")
mid = analyze_z_level(mid_z, tolerance=5.0)
if mid:
    print(f"  Vertices: {mid['count']}")
    print(f"  X range: {mid['x_range'][0]:.2f} to {mid['x_range'][1]:.2f}")
    print(f"  Y range: {mid['y_range'][0]:.2f} to {mid['y_range'][1]:.2f}")

print(f"\nTop level ({unique_z[-1]:.2f}):")
top = analyze_z_level(unique_z[-1])
if top:
    print(f"  Vertices: {top['count']}")
    print(f"  X range: {top['x_range'][0]:.2f} to {top['x_range'][1]:.2f}")
    print(f"  Y range: {top['y_range'][0]:.2f} to {top['y_range'][1]:.2f}")

# Analyze faces to find planar surfaces
print(f"\n=== Surface Analysis ===")
face_normals = defaultdict(int)
for face in bm.faces:
    # Round normal to identify planar surfaces
    n = face.normal
    normal_key = (round(n.x, 1), round(n.y, 1), round(n.z, 1))
    face_normals[normal_key] += 1

print(f"Major surface orientations:")
for normal, count in sorted(face_normals.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"  Normal {normal}: {count} faces")

bm.free()

print("\n=== Analysis Complete ===\n")
