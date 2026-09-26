"""Draw the lens and old/new eye openings at the physical hard stops.

Run with Blender from the repository root::

    blender --background --factory-startup --python \
      models3d/hockeymon-camera-case/render_eye_clearance_diagram.py
    rsvg-convert -o models3d/hockeymon-camera-case/docs/images/eye_clearance_hard_stops.png \
      models3d/hockeymon-camera-case/docs/images/eye_clearance_hard_stops.svg
"""

from __future__ import annotations

import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "hockeymom_cam_case_blender.py"
model = {"__name__": "eye_clearance_diagram", "__file__": str(SOURCE)}
exec(compile(SOURCE.read_bytes(), str(SOURCE), "exec"), model)


def svg_polygon(points, center_x, center_y, scale):
    return " ".join(
        f"{center_x + x*scale:.2f},{center_y - z*scale:.2f}"
        for x, z in points
    )


def lens_points(camera, yaw):
    lens = model["rounded_rectangle_loop"](
        model["mission1"].LENS_FACE_WIDTH,
        model["mission1"].LENS_FACE_HEIGHT,
        model["mission1"].LENS_FACE_CORNER_RADIUS,
    )
    angle = math.radians(camera["angle"])
    tangent_axis = (-math.sin(angle), math.cos(angle))
    result = []
    for tangent, vertical in lens:
        point = model["adjustable_camera_local_point"](
            camera, 0.0, tangent,
            model["camera_eye_center_z"]() + vertical, yaw,
        )
        result.append((
            point.x*tangent_axis[0]
            + point.y*tangent_axis[1]
            - camera["eye_tangent"],
            vertical,
        ))
    return result


def gaps(lens, width, height, radius):
    opening = model["rounded_rectangle_loop"](width, height, radius)
    return (
        min(x for x, _ in lens) + width/2,
        width/2 - max(x for x, _ in lens),
        min(z for _, z in lens) + height/2,
        height/2 - max(z for _, z in lens),
        min(model["polygon_boundary_distance"](point, opening) for point in lens),
    )


def main():
    cameras, _ = model["resolve_camera_layout"]()
    camera = next(c for c in cameras if model["camera_is_adjustable"](c))
    hard_stop = model["adjustable_hard_stop_geometry"](camera)["hard_stop_limit_deg"]
    previous = (64.0, 52.0, 14.5)
    current = (
        model["EYE_MOUTH_WIDTH"],
        model["EYE_MOUTH_HEIGHT"],
        model["EYE_MOUTH_CORNER_RADIUS"],
    )
    if current == previous:
        raise ValueError("The camera eye has not been tightened")

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="560" viewBox="0 0 1200 560">',
        '<rect width="1200" height="560" fill="#f5f8fb"/>',
        '<text x="600" y="42" text-anchor="middle" font-family="sans-serif" font-size="25" font-weight="700" fill="#152b3b">Lens clearance at both physical gear stops</text>',
        '<text x="600" y="69" text-anchor="middle" font-family="sans-serif" font-size="15" fill="#435a69">Orange: 41.8 mm GoPro lens housing face · Dashed: previous 64 × 52 mm opening · Blue: new 62 × 51.5 mm opening</text>',
    ]
    scale = 5.1
    for index, yaw in enumerate((-hard_stop, hard_stop)):
        panel_x = 24 + index*584
        center_x = panel_x + 280
        center_y = 275
        lens = lens_points(camera, yaw)
        old = gaps(lens, *previous)
        new = gaps(lens, *current)
        lines.extend((
            f'<rect x="{panel_x}" y="90" width="568" height="442" rx="18" fill="#ffffff" stroke="#d5e2eb" stroke-width="2"/>',
            f'<text x="{center_x}" y="122" text-anchor="middle" font-family="sans-serif" font-size="22" font-weight="700" fill="#18394d">Camera yaw {yaw:+.0f}°</text>',
            f'<line x1="{center_x-185}" y1="{center_y}" x2="{center_x+185}" y2="{center_y}" stroke="#d6e2e8" stroke-dasharray="4 5"/>',
            f'<line x1="{center_x}" y1="{center_y-155}" x2="{center_x}" y2="{center_y+155}" stroke="#d6e2e8" stroke-dasharray="4 5"/>',
            f'<polygon points="{svg_polygon(model["rounded_rectangle_loop"](*previous),center_x,center_y,scale)}" fill="none" stroke="#82929e" stroke-width="2.5" stroke-dasharray="8 6"/>',
            f'<polygon points="{svg_polygon(model["rounded_rectangle_loop"](*current),center_x,center_y,scale)}" fill="#d8ecf7" fill-opacity="0.55" stroke="#0878b4" stroke-width="3"/>',
            f'<polygon points="{svg_polygon(lens,center_x,center_y,scale)}" fill="#f0a048" fill-opacity="0.85" stroke="#a94c10" stroke-width="2.5"/>',
            f'<text x="{center_x}" y="437" text-anchor="middle" font-family="sans-serif" font-size="15" fill="#435a69">Old: left {old[0]:.2f} · right {old[1]:.2f} · top/bottom {old[2]:.2f} · corner {old[4]:.2f} mm</text>',
            f'<text x="{center_x}" y="466" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="700" fill="#075e91">New: left {new[0]:.2f} · right {new[1]:.2f} · top/bottom {new[2]:.2f} · corner {new[4]:.2f} mm</text>',
            f'<text x="{center_x}" y="498" text-anchor="middle" font-family="sans-serif" font-size="13" fill="#667c8b">Left and right are viewed from outside, facing the camera.</text>',
        ))
    lines.append('</svg>')
    output = HERE / "docs/images/eye_clearance_hard_stops.svg"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"EYE_CLEARANCE_DIAGRAM {output}")


if __name__ == "__main__":
    main()
