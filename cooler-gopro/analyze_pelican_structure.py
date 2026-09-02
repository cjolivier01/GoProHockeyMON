#!/usr/bin/env python3
"""Analyze pelican case STL to understand its structure."""

import bpy
import bmesh
import sys
import mathutils

# Clear existing objects
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Import STL (Blender 5.x uses wm.stl_import)
bpy.ops.wm.stl_import(filepath='pelican-case.stl')

# Get the imported object
obj = bpy.context.active_object

print(f"\n=== Object Analysis ===")
print(f"Name: {obj.name}")
print(f"Vertices: {len(obj.data.vertices)}")
print(f"Edges: {len(obj.data.edges)}")
print(f"Faces: {len(obj.data.polygons)}")

# Get bounding box
bbox = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
min_x = min(v.x for v in bbox)
max_x = max(v.x for v in bbox)
min_y = min(v.y for v in bbox)
max_y = max(v.y for v in bbox)
min_z = min(v.z for v in bbox)
max_z = max(v.z for v in bbox)

print(f"\n=== Bounding Box ===")
print(f"X: {min_x:.2f} to {max_x:.2f} (width: {max_x - min_x:.2f})")
print(f"Y: {min_y:.2f} to {max_y:.2f} (depth: {max_y - min_y:.2f})")
print(f"Z: {min_z:.2f} to {max_z:.2f} (height: {max_z - min_z:.2f})")

# Analyze mesh structure
bm = bmesh.new()
bm.from_mesh(obj.data)

print(f"\n=== BMesh Analysis ===")
print(f"Vertices: {len(bm.verts)}")
print(f"Edges: {len(bm.edges)}")
print(f"Faces: {len(bm.faces)}")

# Check if it's a solid (manifold)
non_manifold_edges = [e for e in bm.edges if not e.is_manifold]
print(f"Non-manifold edges: {len(non_manifold_edges)}")

# Sample vertices to understand structure
print(f"\n=== Sample Vertices (first 20) ===")
for i, v in enumerate(bm.verts[:20]):
    print(f"V{i}: ({v.co.x:.2f}, {v.co.y:.2f}, {v.co.z:.2f})")

bm.free()

print("\n=== Analysis complete ===")
