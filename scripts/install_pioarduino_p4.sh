#!/usr/bin/env bash
set -euo pipefail

PLATFORM_URL="https://github.com/pioarduino/platform-espressif32.git"
P4_BOARD_ID="${P4_BOARD_ID:-esp32-p4_r3-evboard}"

if ! command -v pio >/dev/null 2>&1; then
  echo "error: PlatformIO CLI 'pio' is not installed or not on PATH" >&2
  exit 1
fi

echo "Installing pioarduino Espressif platform:"
echo "  ${PLATFORM_URL}"
pio pkg install -g -p "${PLATFORM_URL}"

echo
echo "Checking for ESP32-P4 board support..."
if pio boards espressif32 | grep -q "${P4_BOARD_ID}"; then
  echo "Found ${P4_BOARD_ID}"
else
  echo "error: ${P4_BOARD_ID} was not found after installing pioarduino" >&2
  echo "Available P4 boards:" >&2
  pio boards espressif32 | grep -i 'esp32.*p4\|p4' >&2 || true
  exit 1
fi

echo
echo "Building ESP32-P4 UI target..."
pio run -e esp32p4_ui

echo
echo "P4 Arduino/PlatformIO setup is ready."
