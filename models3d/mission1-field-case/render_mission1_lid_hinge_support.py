"""Compare expanded-lid hinge sections from actual before/after STL exports.

Run with Python (matplotlib, numpy, shapely, trimesh)::

    python render_mission1_lid_hinge_support.py --baseline /path/to/old/stls

Keep the baseline exports before rebuilding with ``make mission1-field-case``.
The dimension reader requires current exports. Both inputs must use the current
expanded case datums; the compact lid does not have this shoulder web.
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Patch
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union
import trimesh

from generate_mission1_field_case_config_dimension_pdf import CONFIG_BY_NAME


DIRECTORY = Path(__file__).resolve().parent


def config(name):
    return CONFIG_BY_NAME[name].value


def section(path):
    mesh = trimesh.load_mesh(path)
    # First TPU clip midpoint; the rigid bank spans the same station.
    bank_start = config("HINGE_LID_SEGMENTS")[0][0] + config("HINGE_LID_SEGMENT_END_TRIM")
    bank_end = config("HINGE_LID_SEGMENTS")[0][1] - config("HINGE_LID_SEGMENT_END_TRIM")
    clips = config("TPU_HINGE_CLIPS_PER_SEGMENT")
    clip_width = (bank_end - bank_start - (clips - 1) * config("TPU_HINGE_CLIP_RELIEF_GAP")) / clips
    x = config("LID_DISPLAY_OFFSET_X") + bank_start + clip_width / 2
    cut = mesh.section(plane_origin=(x, 0, 0), plane_normal=(1, 0, 0))
    if cut is None:
        raise ValueError(f"Missing hinge section: {path}")
    # Show the installed lid, with the crown above the hinge and outside right.
    axis_z = config("LID_DOME_RISE") + config("LID_WALL_HEIGHT")
    polygons = [Polygon(np.column_stack((
        -loop[:, 1] - config("CASE_DEPTH") / 2,
        axis_z - loop[:, 2],
    ))) for loop in cut.discrete]
    if any(not polygon.is_valid for polygon in polygons):
        raise ValueError(f"Invalid section polygon: {path}")
    return unary_union(polygons)


def fill(ax, geometry, color):
    polygons = geometry.geoms if hasattr(geometry, "geoms") else (geometry,)
    for polygon in polygons:
        if polygon.is_empty or polygon.geom_type != "Polygon":
            continue
        ax.fill(*polygon.exterior.xy, color=color, linewidth=0)
        for hole in polygon.interiors:
            ax.fill(*hole.xy, color="white", linewidth=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--current", type=Path, default=DIRECTORY)
    parser.add_argument("--output", type=Path, default=DIRECTORY / "docs/images/mission1_lid_hinge_shoulder_support.png")
    args = parser.parse_args()
    fig, axes = plt.subplots(1, 2, figsize=(10, 7), sharey=True)
    for ax, title, filename in zip(axes, ("Rigid PETG lid", "TPU snap-on lid"),
            ("mission1_field_case_lid.stl", "mission1_field_case_lid_tpu_68d_snap.stl")):
        old, new = section(args.baseline / filename), section(args.current / filename)
        fill(ax, new, "#c5d0dd")
        fill(ax, new.difference(old), "#e87924")
        for poly in old.geoms if hasattr(old, "geoms") else (old,):
            ax.plot(*poly.exterior.xy, color="#435267", linewidth=1, linestyle="--")
        axis_y = config("HINGE_AXIS_Y") - config("CASE_DEPTH") / 2
        ax.add_patch(Circle((axis_y, 0), config("HINGE_ROD_DIAMETER") / 2,
                            color="#5391b5", zorder=3))
        ax.annotate("Continuous support\ninto hinge barrel", xy=(5.0, 8),
                    xytext=(-20, 15), fontsize=10,
                    arrowprops={"arrowstyle": "->", "color": "#9d460b"})
        ax.set(title=title, xlim=(-23, 11), ylim=(-6, 37),
               xlabel="Distance outside rear wall (mm)")
        ax.set_aspect("equal", adjustable="box")
        ax.grid(alpha=.15)
    axes[0].set_ylabel("Height above hinge pin (mm) — installed orientation")
    fig.suptitle("Mission 1 lid: shoulder support extended into hinge", fontsize=15)
    fig.legend(handles=[Patch(color="#c5d0dd", label="Existing lid"),
                        Patch(color="#e87924", label="Added material"),
                        Patch(color="#5391b5", label=f"Unchanged {config('HINGE_ROD_DIAMETER'):g} mm rod")],
               loc="lower center", ncol=3, bbox_to_anchor=(.5, .045))
    fig.text(.5, .02, "Actual STL sections • dashed line: previous outline • base, hinge axis and lid height unchanged",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .15, 1, .95))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=180)
    plt.close(fig)
    print(args.output)


if __name__ == "__main__":
    main()
