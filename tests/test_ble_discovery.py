#!/usr/bin/env python3
"""Run native regressions against actual installed Arduino BLE service methods."""
from pathlib import Path
import importlib.util
import os
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("patch_ble_discovery", ROOT / "scripts/patch_ble_discovery.py")
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)


def extract_method(source, signature):
    # retrieveCharacteristics occurs for both stacks; NimBLE is the last one.
    start = source.rindex(signature)
    opening = source.index("{", start)
    depth = 1
    cursor = opening + 1
    while depth:
        depth += (source[cursor] == "{") - (source[cursor] == "}")
        cursor += 1
    return source[start:cursor]


def run():
    core = Path(os.environ.get("PLATFORMIO_CORE_DIR", Path.home() / ".platformio"))
    source_path = core / "packages/framework-arduinoespressif32/libraries/BLE/src/BLERemoteService.cpp"
    if not source_path.is_file():
        raise SystemExit("Install the AMOLED firmware dependencies before testing BLE discovery")
    source = source_path.read_text()
    characteristic_path = source_path.with_name("BLERemoteCharacteristic.cpp")
    characteristic_source = characteristic_path.read_text()
    characteristic_fixed = patch.patch_characteristic_source(characteristic_source)
    assert patch.patch_characteristic_source(characteristic_fixed) == characteristic_fixed
    fixed = patch.patch_source(source)
    assert patch.patch_source(fixed) == fixed
    try:
        patch.patch_source(source.replace("service->m_haveCharacteristics = true;", "unrecognized_upstream_change();"))
    except RuntimeError:
        pass
    else:
        raise AssertionError("Unexpected framework source must fail visibly")

    methods = (
        "BLERemoteService::~BLERemoteService()",
        "BLERemoteCharacteristic *BLERemoteService::getCharacteristic(BLEUUID uuid)",
        "void BLERemoteService::removeCharacteristics()",
        "void BLERemoteService::retrieveCharacteristics()",
        "int BLERemoteService::characteristicDiscCB(",
    )
    descriptor_methods = (
        "void BLERemoteCharacteristic::removeDescriptors()",
        "int BLERemoteCharacteristic::descriptorDiscCB(",
        "bool BLERemoteCharacteristic::retrieveDescriptors(const BLEUUID *uuid_filter)",
    )
    with tempfile.TemporaryDirectory(prefix="ble-discovery-tests-") as temporary:
        directory = Path(temporary)
        for suite, original, patched, signatures in (
            ("ble_discovery", source, fixed, methods),
            ("ble_descriptors", characteristic_source, characteristic_fixed, descriptor_methods),
        ):
            for is_fixed, implementation in ((False, original), (True, patched)):
                (directory / f"{suite}_under_test.inc").write_text(
                    "\n\n".join(extract_method(implementation, signature) for signature in signatures)
                )
                binary = directory / (suite + ("_fixed" if is_fixed else "_original"))
                subprocess.run([
                    os.environ.get("CXX", "g++"), "-std=c++17", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-g",
                    f"-DEXPECT_FIXED={int(is_fixed)}", "-I", str(directory),
                    str(ROOT / "tests" / f"{suite}_test.cpp"), "-o", str(binary),
                ], check=True)
                subprocess.run([str(binary)], check=True)
    assert source_path.read_text() == source, "Tests must not alter the shared framework"
    assert characteristic_path.read_text() == characteristic_source, "Tests must not alter the shared framework"


if __name__ == "__main__":
    run()
