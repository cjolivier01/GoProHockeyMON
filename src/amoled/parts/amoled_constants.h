#pragma once

#include <Arduino.h>

#include <stddef.h>
#include <stdint.h>

// Display refresh and rendering cadence.
inline constexpr uint32_t kLvglTickMs = 2;
inline constexpr uint8_t kDisplayBrightness = 210;
inline constexpr uint32_t kDrawBufferLines = 16;
inline constexpr uint32_t kBatteryRefreshMs = 5000;

// Physical button and touch gesture timing.
inline constexpr uint8_t kExpanderActionButtonPin = 5;
inline constexpr bool kExpanderActionPressedLevel = LOW;
inline constexpr int kBootButtonPin = 0;
inline constexpr uint32_t kButtonDebounceMs = 35;
inline constexpr uint32_t kActionButtonDebounceMs = 90;
inline constexpr uint32_t kActionButtonMinPressMs = 120;
inline constexpr uint32_t kBootLongPressMs = 1200;
inline constexpr uint32_t kPmuPollMs = 150;
inline constexpr uint32_t kPmuDuplicateSuppressMs = 500;
inline constexpr uint32_t kActionButtonDoubleClickMs = 900;
inline constexpr uint32_t kActionButtonLongPressMs = 1200;
inline constexpr uint32_t kPreviewExitButtonSuppressMs = kActionButtonDoubleClickMs;
inline constexpr int kNavSwipeStartPx = 18;
inline constexpr int kNavSwipeCommitPx = 64;
inline constexpr uint32_t kNavSwipeFlickMs = 650;
inline constexpr int kNavSwipeFlickPx = 42;
inline constexpr uint32_t kNavPageAnimMs = 180;
inline constexpr int kFullscreenSwipePx = 45;

// BLE, WiFi, and GoPro network behavior.
inline constexpr uint32_t kPreviewRefreshMs = 1500;
inline constexpr uint32_t kHttpTimeoutMs = 6500;
inline constexpr uint32_t kRecordingStartCommandTimeoutMs = 2500;
inline constexpr uint32_t kRecordingStartVerifyTimeoutMs = 5000;
inline constexpr uint32_t kRecordingStartVerifyRequestTimeoutMs = 1000;
inline constexpr uint32_t kRecordingStartVerifyPollMs = 200;
inline constexpr uint32_t kBleScanSeconds = 7;
inline constexpr uint32_t kBleWakeScanSeconds = 18;
inline constexpr uint32_t kPairBleScanSeconds = 18;
inline constexpr uint32_t kBleConnectTimeoutMs = 10000;
inline constexpr uint32_t kBleWakeConnectTimeoutMs = 20000;
inline constexpr uint32_t kPairBleConnectTimeoutMs = 3000;
inline constexpr size_t kBleResponsePayloadCapacity = 256;
inline constexpr uint32_t kWifiTimeoutMs = 25000;
inline constexpr int kPairFallbackMinRssi = -50;
inline constexpr int kPairScanLogMinRssi = -75;
inline constexpr uint16_t kPreviewStreamPort = 8554;

// Live preview, snapshot, and camera setting limits.
inline constexpr uint32_t kLivePreviewStatsMs = 1000;
inline constexpr size_t kTsPacketBytes = 188;
inline constexpr uint16_t kGoProVideoPid = 0x1011;
inline constexpr int32_t kGoProVideoPresetGroup = 1000;
inline constexpr size_t kMaxH264AccessUnit = 512 * 1024;
inline constexpr uint32_t kMinDecodeIntervalMs = 1000;
inline constexpr size_t kMaxJpegBytes = 512 * 1024;
inline constexpr size_t kMaxSettingOptions = 40;
inline constexpr size_t kVisibleSettingOptions = 6;
inline constexpr uint8_t kGoProWirelessBandSetting = 178;
inline constexpr uint8_t kGoProWirelessBand24GHz = 0;

// Main-screen layout and hardware button markers.
inline constexpr int kHomeButtonY = 295;
inline constexpr int kHomeButtonH = 56;
inline constexpr int kForgetButtonY = kHomeButtonY + kHomeButtonH + 6;
inline constexpr int kForgetButtonH = 36;
inline constexpr int kPreviewX = 20;
inline constexpr int kPreviewY = 76;
inline constexpr int kPreviewW = 328;
inline constexpr int kPreviewH = 150;
// Y is relative to the main capture tile below the top status bar.
inline constexpr int kTopRightButtonMarkerW = 6;
inline constexpr int kTopRightButtonMarkerH = 39;
inline constexpr int kTopRightButtonMarkerY = 39;
inline constexpr int kTopBarH = 32;
inline constexpr uint8_t kSnapshotAspectCropStrengthPercent = 100;
inline constexpr uint8_t kSnapshotPreviewVisiblePercent = 50;
