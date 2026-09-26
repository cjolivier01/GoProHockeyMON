"""Render the actual HockeyMON 250 × 255 mm 3MF plates as a labeled PNG."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
SHARED = HERE.parent / "mission1-field-case" / "render_3mf_plate_overview.py"
spec = importlib.util.spec_from_file_location("print_plate_overview_shared", SHARED)
overview = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = overview
spec.loader.exec_module(overview)

overview.PLATE_SIZE = 250.0
overview.PLATE_DEPTH = 255.0
overview.PLATE_STRIDE_X = 300.0
overview.PLATE_STRIDE_Y = 306.0
overview.BED_EXCLUDE_SIZE = None
overview.PROJECT_TITLE = "HOCKEYMON CAMERA CASE"
overview.PROJECT_NOTICE = "ONE PRINTABLE PART PER PLATE  •  FLAT INTERNAL BATTERY BAY"
overview.MATERIAL_LEGEND = "LIGHT = PRINTABLE PART  •  SET YOUR PRINTER AND MATERIAL PROFILE BEFORE SLICING"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=HERE / "hockeymom_cam_case.3mf")
    parser.add_argument("--output", type=Path, default=HERE / "docs/images/flat_battery_print_plates.png")
    parser.add_argument("--width", type=int, default=2400)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if args.width < 800:
        parser.error("--width must be at least 800 pixels")
    project = overview.ThreeMFProject(args.input.expanduser().resolve())
    overview.render_overview(project, args.output.expanduser().resolve(), args.width)


if __name__ == "__main__":
    main()
