#!/usr/bin/env python3
"""Native unit and simulated camera transaction tests; no ESP32 required."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
json_include = root / ".pio/libdeps/esp32s3_amoled_ui/ArduinoJson/src"
if not json_include.is_dir():
    raise SystemExit("Install firmware dependencies first: pio pkg install -e esp32s3_amoled_ui")
with tempfile.TemporaryDirectory(prefix="camera-preset-tests-") as tmp:
    for name in ("camera_presets", "snapshot_capture", "camera_preset_poll", "recording_presets", "wifi_connection", "ble_initialization", "ble_connection", "recording_radio_handoff"):
        binary = Path(tmp) / name
        subprocess.run([
            os.environ.get("CXX", "g++"), "-std=c++17", "-Wall", "-Wextra", "-Werror",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-g",
            "-I", str(root), "-I", str(json_include),
            str(root / "tests" / f"{name}_test.cpp"), "-o", str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True)
subprocess.run([os.environ.get("PYTHON", "python3"), str(root / "tests/test_ble_discovery.py")], check=True)
