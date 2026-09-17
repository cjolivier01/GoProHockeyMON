"""Check sliced lid support volume and complete extrusion footprint.

Usage: python check_mission1_support_gcode.py plate_2.gcode plate_3.gcode
Slice the generated 3MF at its supplied placement on the 250 x 250 mm bed,
using 0.20 mm layers, 0.4 mm nozzle, four walls, and the lid support overrides.
Machine startup/purge paths are excluded; Support and Support interface paths
include arc extrema and half the extrusion width, not just nozzle endpoints.
"""
import argparse
import json
import math
from pathlib import Path
import re

PARAMETER = re.compile(r'([XYZEFIJ])([-+]?(?:\d+(?:\.\d*)?|\.\d+))')


def check(path):
    role, position = '', {}
    absolute_e, extrusion, width = False, 0.0, 0.5
    support_length, other_length = 0.0, 0.0
    minimum, maximum = [math.inf, math.inf], [-math.inf, -math.inf]
    for line in path.open():
        if line.startswith('; FEATURE: '):
            role = line.split(': ', 1)[1].strip()
        if line.startswith('; LINE_WIDTH: '):
            width = float(line.split(': ', 1)[1])
        command = line.split(';', 1)[0].strip()
        if command in ('M82', 'M83'):
            absolute_e = command == 'M82'
        values = {key: float(value) for key, value in PARAMETER.findall(command)}
        if command.startswith('G92 ') and 'E' in values:
            extrusion = values['E']
        if not re.match(r'^G[0123] ', command):
            continue
        previous = position.copy()
        position.update({key: value for key, value in values.items() if key in 'XYZ'})
        delta = values.get('E', extrusion if absolute_e else 0) - (extrusion if absolute_e else 0)
        if 'E' in values:
            extrusion = values['E'] if absolute_e else extrusion + values['E']
        arc_move = command.startswith(('G2 ', 'G3 ')) and ('I' in values or 'J' in values)
        if delta <= 0 or not ('X' in values or 'Y' in values or arc_move):
            continue
        if not role.startswith('Support'):
            if role != 'Custom':
                other_length += delta
            continue
        support_length += delta
        points = [previous, position]
        if command.startswith(('G2 ', 'G3 ')) and all(key in previous and key in position for key in 'XY'):
            cx, cy = previous['X'] + values.get('I', 0), previous['Y'] + values.get('J', 0)
            start = math.atan2(previous['Y'] - cy, previous['X'] - cx)
            end = math.atan2(position['Y'] - cy, position['X'] - cx)
            direction = -1 if command.startswith('G2 ') else 1
            sweep = ((end - start) * direction) % math.tau
            if math.isclose(start, end, abs_tol=1e-10):
                sweep = math.tau  # A closed G2/G3 move is a full circle.
            radius = math.hypot(previous['X'] - cx, previous['Y'] - cy)
            for angle in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
                if ((angle - start) * direction) % math.tau <= sweep + 1e-6:
                    points.append(dict(X=cx + radius * math.cos(angle), Y=cy + radius * math.sin(angle)))
        for point in points:
            if not all(key in point for key in 'XY'):
                raise ValueError('Support path has unknown position')
            for index, axis in enumerate('XY'):
                minimum[index] = min(minimum[index], point[axis] - width / 2)
                maximum[index] = max(maximum[index], point[axis] + width / 2)
    volume_cm3 = support_length * math.pi * (1.75 / 2) ** 2 / 1000
    if not 0 < volume_cm3 <= 30:
        raise ValueError(f'Missing support or excessive support volume: {volume_cm3:.3f} cm3')
    if min(minimum) < 0 or max(maximum) > 250:
        raise ValueError(f'Support extrusion exceeds the 250 mm bed: {minimum}, {maximum}')
    # A conservative bounding-box test includes every connecting segment/arc.
    if minimum[0] < 18 and minimum[1] < 28:
        raise ValueError('Support footprint reaches the excluded bed corner')
    print('FIELD_CASE_SLICED_SUPPORT_VALID', path.name, json.dumps({
        'support_cm3': round(volume_cm3, 3),
        'support_percent_of_deposition': round(100 * support_length / (support_length + other_length), 2),
        'extrusion_xy_min': minimum, 'extrusion_xy_max': maximum,
    }), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gcode', type=Path, nargs='+')
    for path in parser.parse_args().gcode:
        check(path)
