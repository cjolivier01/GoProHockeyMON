#!/usr/bin/env python3
"""Build a .blend project file from a Blender generator script.

Run outside Blender, this launches `blender --background --factory-startup`
and re-runs itself inside that instance; inside Blender it optionally opens an
existing project, optionally clears it, executes the generator, and saves the
result with `bpy.ops.wm.save_as_mainfile`.

    cli/build_blend.py horn/horn_parametric_blender.py
    cli/build_blend.py mission1-field-case/mission1_field_case_blender.py \
        --clear -o mission1-field-case/mission1_field_case.blend
    cli/build_blend.py horn/horn_parametric_blender.py -i base.blend -o combined.blend

Without `--input` the generator runs on Blender's factory startup scene, so the
default cube, camera, and light are saved alongside the model; `--clear` first
deletes every object and collection. The generator runs as `__main__`, so its
normal entry point builds the model just as `blender --python <generator>`
would, and arguments after a bare `--` reach it through `sys.argv`.

The Blender executable is taken from `--blender`, else the BLENDER_EXECUTABLE
environment variable, else `blender` on PATH.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Matches the Makefile's fallback when Blender is not installed on PATH.
FALLBACK_BLENDER = "/home/colivier/Apps/Blender/blender"

DEFAULT_OUTPUT = "blender.blend"

# Marks the re-invocation of this file inside Blender. The arguments that
# follow it are: <generator> <output> <input|-> <clear|keep> [generator args...]
INSIDE_BLENDER_FLAG = "--inside-blender"
NO_INPUT = "-"


def resolve_blender(explicit: str | None) -> str:
    """Return the Blender executable to run."""
    candidate = explicit or os.environ.get("BLENDER_EXECUTABLE")
    if candidate:
        resolved = shutil.which(candidate) or (candidate if Path(candidate).is_file() else None)
        if resolved is None:
            source = "--blender" if explicit else "BLENDER_EXECUTABLE"
            raise SystemExit(f"{source} is not an executable Blender: {candidate}")
        return resolved
    return shutil.which("blender") or FALLBACK_BLENDER


def clear_blend_data() -> None:
    """Delete every object and collection; unused data is dropped on save."""
    import bpy

    bpy.data.batch_remove(list(bpy.data.objects))
    bpy.data.batch_remove(list(bpy.data.collections))


def build_inside_blender(
    script: Path, output: Path, blend_input: Path | None, clear: bool, script_args: list[str]
) -> None:
    """Load, clear, run the generator, and save the .blend file."""
    import bpy

    if blend_input is not None:
        bpy.ops.wm.open_mainfile(filepath=str(blend_input))
    if clear:
        clear_blend_data()

    # Generators import their siblings and read the arguments after `--`.
    sys.path.insert(0, str(script.parent))
    sys.argv = [str(script), "--", *script_args]

    namespace = {"__name__": "__main__", "__file__": str(script)}
    exec(compile(script.read_bytes(), str(script), "exec"), namespace)

    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    print(f"BLEND_SAVED {output} objects={len(bpy.data.objects)}", flush=True)


def launch_blender(
    blender: str,
    script: Path,
    output: Path,
    blend_input: Path | None,
    clear: bool,
    script_args: list[str],
) -> int:
    """Run Blender in the background on this file and return its exit code."""
    command = [
        blender,
        "--background",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "--python",
        str(Path(__file__).resolve()),
        "--",
        INSIDE_BLENDER_FLAG,
        str(script),
        str(output),
        str(blend_input) if blend_input else NO_INPUT,
        "clear" if clear else "keep",
        *script_args,
    ]
    return subprocess.call(command)


def main() -> int:
    argv = sys.argv[1:]

    if INSIDE_BLENDER_FLAG in argv:
        script, output, blend_input, clear, *script_args = argv[
            argv.index(INSIDE_BLENDER_FLAG) + 1:
        ]
        build_inside_blender(
            Path(script),
            Path(output),
            None if blend_input == NO_INPUT else Path(blend_input),
            clear == "clear",
            script_args,
        )
        return 0

    separator = argv.index("--") if "--" in argv else len(argv)
    script_args = argv[separator + 1:]

    parser = argparse.ArgumentParser(
        description="Build a .blend project file from a Blender generator script.",
        epilog="Arguments after a bare -- are forwarded to the generator.",
    )
    parser.add_argument("script", type=Path, help="Blender Python generator to run")
    parser.add_argument(
        "-o", "--output", type=Path, default=Path(DEFAULT_OUTPUT),
        help=f"output .blend path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "-i", "--input", type=Path,
        help="existing .blend to open before running the generator",
    )
    parser.add_argument(
        "--clear", action="store_true",
        help="delete every object and collection before running the generator",
    )
    parser.add_argument(
        "--blender",
        help="Blender executable (default: $BLENDER_EXECUTABLE, then blender on PATH)",
    )
    args = parser.parse_args(argv[:separator])

    script = args.script.resolve()
    if not script.is_file():
        raise SystemExit(f"Generator script not found: {args.script}")
    blend_input = args.input.resolve() if args.input else None
    if blend_input is not None and not blend_input.is_file():
        raise SystemExit(f"Input project not found: {args.input}")
    output = args.output.resolve()

    status = launch_blender(
        resolve_blender(args.blender), script, output, blend_input, args.clear, script_args
    )
    if status != 0:
        return status
    if not output.is_file() or output.stat().st_size == 0:
        raise SystemExit(f"Blender exited cleanly but wrote no project file: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
