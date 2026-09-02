#!/usr/bin/env python3
"""Analyze the pelican case STL to extract key dimensions"""

import struct
import numpy as np
from collections import defaultdict

def read_stl(filename):
    """Read binary STL file"""
    with open(filename, 'rb') as f:
        header = f.read(80)
        num_triangles = struct.unpack('I', f.read(4))[0]

        vertices = []
        normals = []

        for i in range(num_triangles):
            normal = struct.unpack('fff', f.read(12))
            v1 = struct.unpack('fff', f.read(12))
            v2 = struct.unpack('fff', f.read(12))
            v3 = struct.unpack('fff', f.read(12))
            attr = struct.unpack('H', f.read(2))

            normals.append(normal)
            vertices.extend([v1, v2, v3])

        return np.array(vertices), np.array(normals), num_triangles

def analyze_geometry(vertices, normals):
    """Analyze geometry to extract case features"""

    print(f"Total vertices: {len(vertices)}")
    print(f"\nBounding box:")
    print(f"  X: {vertices[:,0].min():.3f} to {vertices[:,0].max():.3f} (size: {vertices[:,0].max()-vertices[:,0].min():.3f})")
    print(f"  Y: {vertices[:,1].min():.3f} to {vertices[:,1].max():.3f} (size: {vertices[:,1].max()-vertices[:,1].min():.3f})")
    print(f"  Z: {vertices[:,2].min():.3f} to {vertices[:,2].max():.3f} (size: {vertices[:,2].max()-vertices[:,2].min():.3f})")

    # Find unique Z levels (layers)
    z_values = np.unique(np.round(vertices[:,2], decimals=1))
    print(f"\nUnique Z levels (rounded to 0.1mm): {len(z_values)}")

    # Analyze normals to identify features
    print(f"\nNormal distribution:")
    for i, axis in enumerate(['X', 'Y', 'Z']):
        axis_normals = normals[:, i]
        pos = np.sum(axis_normals > 0.9)
        neg = np.sum(axis_normals < -0.9)
        print(f"  {axis}: +{pos} -{neg}")

    # Find center
    center = vertices.mean(axis=0)
    print(f"\nGeometric center: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")

    # Analyze cross-sections at different Z heights
    print(f"\nCross-section analysis:")
    z_min, z_max = vertices[:,2].min(), vertices[:,2].max()
    for z_fraction in [0.0, 0.25, 0.5, 0.75, 1.0]:
        z_height = z_min + (z_fraction * (z_max - z_min))
        z_slice = vertices[np.abs(vertices[:,2] - z_height) < 0.5]
        if len(z_slice) > 0:
            x_range = z_slice[:,0].max() - z_slice[:,0].min()
            y_range = z_slice[:,1].max() - z_slice[:,1].min()
            print(f"  Z={z_fraction*100:.0f}% (Z={z_height:.2f}): X-range={x_range:.3f}, Y-range={y_range:.3f}")

if __name__ == '__main__':
    vertices, normals, num_triangles = read_stl('pelican-case.stl')
    analyze_geometry(vertices, normals)
