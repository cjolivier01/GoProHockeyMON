#!/usr/bin/env bash
set -euo pipefail

PLATFORM_URL="${PLATFORM_URL:-https://github.com/pioarduino/platform-espressif32/releases/download/54.03.21-2/platform-espressif32.zip}"
P4_BOARD_ID="${P4_BOARD_ID:-esp32-p4-evboard}"
ESP_H264_DIR="${ESP_H264_DIR:-${HOME}/src/esp-h264-component}"

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
echo "Checking esp-h264 component for the optional P4 decoder probe..."
if [[ -d "${ESP_H264_DIR}/.git" ]]; then
  git -C "${ESP_H264_DIR}" fetch --depth=1 origin >/dev/null 2>&1 || true
elif [[ -d "${ESP_H264_DIR}" ]]; then
  echo "Using existing ${ESP_H264_DIR}"
else
  mkdir -p "$(dirname "${ESP_H264_DIR}")"
  git clone --depth=1 https://github.com/espressif/esp-h264-component.git "${ESP_H264_DIR}"
fi

echo
echo "Building optional ESP32-P4 serial worker shell..."
pio run -e esp32p4_ui

echo
echo "Building ESP32-P4 H.264 decode probe..."
pio run -e dfrobot_p4_decode_probe

echo
echo "P4 Arduino/PlatformIO setup is ready."
