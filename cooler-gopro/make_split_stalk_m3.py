#!/usr/bin/env python3
"""Generate repaired two-piece stalk STLs with M3 heat-insert fastening."""

from __future__ import annotations

import pathlib

import numpy as np
import trimesh
from trimesh.boolean import difference, intersection, union
from trimesh.transformations import rotation_matrix, translation_matrix


SOURCE = pathlib.Path("gopro-dual-fan-manifold-repaired-single-shell.stl")
BODY_OUT = pathlib.Path("gopro-dual-fan-manifold-fixed-body.stl")
STALK_OUT = pathlib.Path("gopro-dual-fan-manifold-fixed-stalk.stl")
PRINT_PLATE_OUT = pathlib.Path("gopro-dual-fan-manifold-fixed-print-plate.stl")

SPLIT_Y = -42.0
SCREW_X = 6.0
SCREW_Z = -56.0

COUPLER_X = 28.0
COUPLER_Z = 18.0
BODY_COUPLER_Y = 13.0
STALK_COUPLER_Y = 14.0

M3_CLEARANCE_D = 3.4
M3_HEAD_D = 6.4
M3_HEAD_DEPTH = 3.4
M3_INSERT_D = 4.8
M3_INSERT_DEPTH = 6.2
M3_PILOT_D = 2.8
M3_PILOT_DEPTH = 10.0


def box(extents: tuple[float, float, float], center: tuple[float, float, float]) -> trimesh.Trimesh:
    return trimesh.creation.box(
        extents=extents,
        transform=translation_matrix(center),
    )


def cylinder_y(
    diameter: float,
    y_min: float,
    y_max: float,
    x: float,
    z: float,
    sections: int = 72,
) -> trimesh.Trimesh:
    length = y_max - y_min
    mesh = trimesh.creation.cylinder(
        radius=diameter / 2.0,
        height=length,
        sections=sections,
    )
    # Trimesh cylinders are Z-aligned; rotate into the Y axis, then center.
    mesh.apply_transform(rotation_matrix(np.deg2rad(90.0), [1, 0, 0]))
    mesh.apply_transform(translation_matrix([x, (y_min + y_max) / 2.0, z]))
    return mesh


def screw_meshes(
    diameter: float,
    y_min: float,
    y_max: float,
    sections: int = 72,
) -> list[trimesh.Trimesh]:
    return [
        cylinder_y(diameter, y_min, y_max, x, SCREW_Z, sections=sections)
        for x in (-SCREW_X, SCREW_X)
    ]


def assert_mesh(name: str, mesh: trimesh.Trimesh) -> None:
    if not mesh.is_watertight:
        raise RuntimeError(f"{name} is not watertight")
    if not np.isfinite(mesh.vertices).all():
        raise RuntimeError(f"{name} has non-finite vertices")


def main() -> None:
    source = trimesh.load(SOURCE, force="mesh")
    assert_mesh("source", source)

    upper_half = box((440, 260, 440), (0, SPLIT_Y + 130, 0))
    lower_half = box((440, 220 + SPLIT_Y, 440), (0, (-220 + SPLIT_Y) / 2, 0))

    body_source = intersection([source, upper_half], engine="manifold")
    stalk_source = intersection([source, lower_half], engine="manifold")

    body_coupler = box(
        (COUPLER_X, BODY_COUPLER_Y, COUPLER_Z),
        (0, SPLIT_Y + BODY_COUPLER_Y / 2.0, SCREW_Z),
    )
    stalk_coupler = box(
        (COUPLER_X, STALK_COUPLER_Y, COUPLER_Z),
        (0, SPLIT_Y - STALK_COUPLER_Y / 2.0, SCREW_Z),
    )

    body_raw = union([body_source, body_coupler], engine="manifold")
    stalk_raw = union([stalk_source, stalk_coupler], engine="manifold")

    body_cuts = []
    body_cuts.extend(screw_meshes(M3_CLEARANCE_D, SPLIT_Y - 1.0, SPLIT_Y + BODY_COUPLER_Y + 0.8))
    body_cuts.extend(screw_meshes(M3_HEAD_D, SPLIT_Y + BODY_COUPLER_Y - M3_HEAD_DEPTH, SPLIT_Y + BODY_COUPLER_Y + 0.8))

    stalk_cuts = []
    stalk_cuts.extend(screw_meshes(M3_INSERT_D, SPLIT_Y - M3_INSERT_DEPTH, SPLIT_Y + 0.5))
    stalk_cuts.extend(screw_meshes(M3_PILOT_D, SPLIT_Y - M3_PILOT_DEPTH, SPLIT_Y + 0.5))

    body = difference([body_raw, *body_cuts], engine="manifold")
    stalk = difference([stalk_raw, *stalk_cuts], engine="manifold")

    assert_mesh("body", body)
    assert_mesh("stalk", stalk)

    body.export(BODY_OUT)
    stalk.export(STALK_OUT)

    plate_body = body.copy()
    plate_stalk = stalk.copy()
    plate_stalk.apply_translation([0, -52, 0])
    print_plate = trimesh.util.concatenate([plate_body, plate_stalk])
    print_plate.export(PRINT_PLATE_OUT)

    for name, mesh, path in [
        ("body", body, BODY_OUT),
        ("stalk", stalk, STALK_OUT),
        ("print_plate", print_plate, PRINT_PLATE_OUT),
    ]:
        print(
            f"{name}: wrote {path} | faces={len(mesh.faces)} "
            f"watertight={mesh.is_watertight} bounds={mesh.bounds.tolist()}"
        )


if __name__ == "__main__":
    main()
