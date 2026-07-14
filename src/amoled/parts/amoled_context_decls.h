#pragma once

// Declarations used when clangd opens a .inc file as a standalone source file.
// The firmware build includes these .inc files from main.cpp after the real
// definitions, so main.cpp defines GOPRO_AMOLED_MAIN_CONTEXT to skip this file.

#include <Arduino.h>
#include <ArduinoJson.h>
#include <BLEDevice.h>
#include <BLEScan.h>
#include <HTTPClient.h>
#include <JPEGDEC.h>
#include <Preferences.h>
#include <WiFi.h>
#include <Wire.h>
#include <lvgl.h>

#include "../pin_config.h"

#include <Adafruit_XCA9554.h>
#include <Arduino_DriveBus_Library.h>
#include <Arduino_GFX_Library.h>
#include <XPowersLib.h>

#include "esp_heap_caps.h"
#include "esp_sleep.h"
#include "esp_system.h"
#include "esp_timer.h"

extern "C" {
#include "h264bsd_decoder.h"
}

#include <memory>
#include <stddef.h>
#include <stdint.h>

#include "amoled_constants.h"

extern const BLEUUID kControlService;
extern const BLEUUID kWifiService;
extern const BLEUUID kCameraManagementService;
extern const BLEUUID kWifiSsid;
extern const BLEUUID kWifiPassword;
extern const BLEUUID kCommand;
extern const BLEUUID kCommandResponse;
extern const BLEUUID kSettings;
extern const BLEUUID kSettingsResponse;
extern const BLEUUID kQuery;
extern const BLEUUID kQueryResponse;
extern const BLEUUID kCameraManagementCommand;
extern const BLEUUID kCameraManagementResponse;

struct SettingDefinition {
  const char *name;
  uint16_t id;
};

struct SettingValue {
  uint16_t id;
  int option;
};

struct SnapshotVideoFraming {
  bool valid = false;
  uint16_t aspectW = 16;
  uint16_t aspectH = 9;
  uint8_t visiblePercent = 100;
  uint8_t previewVisiblePercent = kSnapshotPreviewVisiblePercent;
  int aspectSettingId = -1;
  int aspectOption = -1;
  int resolutionOption = -1;
  int lensOption = -1;
  int hypersmoothOption = -1;
  int horizonOption = -1;
  int maxLensOption = -1;
};

enum class PendingHomeAction : uint8_t {
  None,
  Connect,
  Pair,
  Forget,
};

enum class SidePage : uint8_t {
  None,
  Maintenance,
  ButtonGuide,
};

extern Preferences preferences;
extern Adafruit_XCA9554 expander;
extern XPowersPMU power;
extern JPEGDEC jpeg;
extern Arduino_SH8601 *gfx;
extern std::unique_ptr<Arduino_IIC> touch;

extern lv_indev_t *touchInput;
extern BLEAdvertisedDevice *bestBleDevice;
extern BLEAdvertisedDevice *fallbackBleDevice;
extern BLEClient *bleClient;
extern BLESecurityCallbacks *bleSecurityCallbacks;
extern BLESecurity *bleSecurity;
extern lv_obj_t *statusLabel;
extern lv_obj_t *wifiLabel;
extern lv_obj_t *cameraLabel;
extern lv_obj_t *previewBox;
extern lv_obj_t *previewImageCanvas;
extern lv_obj_t *previewLabel;
extern lv_obj_t *recordingOverlay;
extern lv_obj_t *recordingOverlayLabel;
extern lv_obj_t *fullscreenHint;
extern lv_obj_t *actionLabel;
extern lv_obj_t *batteryLabel;
extern lv_obj_t *wifiIndicator;
extern lv_obj_t *bleIndicator;
extern lv_obj_t *goproBatteryLabel;
extern lv_obj_t *tileView;
extern lv_obj_t *captureModeLabel;
extern lv_obj_t *captureSettingLabel;
extern lv_obj_t *recordPill;
extern lv_obj_t *timeRemainingLabel;
extern lv_obj_t *pairButton;
extern lv_obj_t *wakeButton;
extern lv_obj_t *forgetButton;
extern lv_obj_t *pairingPopup;
extern lv_obj_t *pairingPopupTitle;
extern lv_obj_t *pairingPopupMessage;
extern lv_obj_t *forgetConfirmPopup;
extern lv_obj_t *maintenancePage;
extern lv_obj_t *buttonGuidePage;
extern lv_obj_t *settingSheet;
extern lv_obj_t *settingSheetTitle;
extern lv_obj_t *settingOptionButtons[kVisibleSettingOptions];
extern lv_obj_t *settingOptionLabels[kVisibleSettingOptions];
extern lv_obj_t *settingPagerLabel;
extern lv_obj_t *captureTileObj;
extern lv_obj_t *pairButtonLabel;
extern lv_obj_t *wakeButtonLabel;
extern lv_obj_t *topRightButtonMarker;

extern uint32_t lastPreviewUpdate;
extern uint32_t lastPmuPollMs;
extern uint32_t lastBatteryUpdate;
extern bool recording;
extern bool displayOn;
extern bool pmuOnline;
extern bool expanderOnline;
extern bool bleConnected;
extern bool bleStackReady;
extern bool previewStreamRequested;
extern bool previewUdpListening;
extern bool previewFullscreen;
extern bool h264DecoderReady;
extern bool h264StreamUnsupported;
extern bool h264UnsupportedNotified;
extern bool goProWifiSuspendedForRecording;
extern int goProBatteryPercent;
extern bool goProBatteryChargingOrPlugged;
extern bool snapshotPreviewPrepared;
extern bool snapshotPreviewBusy;
extern bool previewHasImage;
extern bool maintenancePageVisible;
extern bool buttonGuidePageVisible;
extern uint32_t recordingStartedMs;
extern uint32_t recordingElapsedBaseMs;
extern uint32_t recordingElapsedBaseAtMs;
extern uint32_t lastRecordingOverlayMs;
extern uint32_t previewBytesThisWindow;
extern uint32_t previewPacketsThisWindow;
extern uint32_t lastPreviewStatsMs;
extern uint32_t lastH264DecodeMs;
extern uint32_t h264FramesDecoded;
extern uint32_t h264DecodeFailures;
extern String lastBleName;
extern String boundBleAddress;
extern String boundBleName;
extern String boundGoProSsid;
extern String goProSsid;
extern String goProPassword;
extern String cameraModelNumber;
extern String cameraModelName;
extern String cameraFirmwareVersion;
extern String cameraSerialNumber;
extern String cameraApSsid;
extern String cameraApMacAddress;
extern String lastSnapshotMediaPath;
extern String captureMode;
extern String captureSetting;
extern IPAddress cameraIp;
extern WiFiUDP previewUdp;
extern h264bsd_hd_t h264Decoder;
extern uint8_t *h264AccessUnit;
extern size_t h264AccessUnitLen;
extern int32_t goProWifiChannel;
extern uint8_t goProWifiBssid[6];
extern bool goProWifiBssidValid;
extern const SettingDefinition *activeSetting;
extern SettingValue settingValues[48];
extern size_t settingValueCount;
extern int settingOptions[kMaxSettingOptions];
extern String settingOptionNames[kMaxSettingOptions];
extern size_t settingOptionCount;
extern size_t settingOptionOffset;
extern int jpegDrawX;
extern int jpegDrawY;
extern int jpegDrawW;
extern int jpegDrawH;
extern int jpegDecodeW;
extern int jpegDecodeH;
extern int jpegCropX;
extern int jpegCropY;
extern int jpegCropW;
extern int jpegCropH;
extern uint8_t *previewJpegCache;
extern size_t previewJpegCacheLen;
extern lv_color_t *previewCanvasBuffer;
extern size_t previewCanvasBufferBytes;
extern int previewCanvasW;
extern int previewCanvasH;
extern SnapshotVideoFraming snapshotVideoFraming;
extern bool redrawingCachedPreview;
extern bool bootLast;
extern bool bootStable;
extern uint32_t bootLastChangeMs;
extern uint32_t bootPressedAtMs;
extern bool bootLongHandled;
extern bool bootPressStartedRecording;
extern bool actionButtonLast;
extern bool actionButtonStable;
extern uint32_t actionButtonLastChangeMs;
extern uint32_t actionButtonPressedAtMs;
extern uint32_t lastExpanderActionHandledMs;
extern uint32_t lastPmuActionHandledMs;
extern uint32_t suppressLowerButtonUntilMs;
extern uint8_t actionButtonShortClickCount;
extern uint32_t actionButtonShortClickDueMs;
extern bool actionButtonLongHandled;
extern lv_point_t lastTouchPoint;
extern lv_point_t touchStartPoint;
extern uint32_t lastTouchMs;
extern uint32_t touchStartMs;
extern bool touchActive;
extern volatile bool bleResponseSeen;
extern volatile uint8_t bleResponseStatus;
extern volatile bool bleResponseOverflow;
extern volatile bool bleResponseAccumulating;
extern uint8_t bleResponsePayload[kBleResponsePayloadCapacity];
extern size_t bleResponsePayloadLength;
extern size_t bleResponsePayloadExpected;
extern bool allowAnyCameraScan;
extern bool pairingInProgress;
extern bool pairingCancelRequested;
extern bool connectionCancelRequested;
extern bool pairingLastCancelled;
extern bool connectRetryAvailable;
extern bool cameraWakeAvailable;
extern bool cameraWakeInProgress;
extern bool homeCameraConnected;
extern bool selectedBleFallback;
extern bool rawSwipeHandled;
extern bool navSwipeActive;
extern bool navSwipeStartedVisible;
extern SidePage navSwipePage;
extern uint32_t pairingPopupHideDueMs;
extern PendingHomeAction pendingHomeAction;
extern uint32_t pendingHomeActionDueMs;
extern uint32_t lastHomeTouchMs;
extern bool expanderActionPinLast;
extern bool goproActionBusy;
extern String serialCommandLine;
extern uint16_t bleScanCandidateCount;
extern uint16_t bleScanSkippedCount;
extern uint16_t bleScanAddressMatchCount;
extern uint16_t bleScanNameMatchCount;
extern uint16_t bleScanSeenCount;
extern bool serialPointerActive;
extern lv_point_t serialPointerStart;
extern lv_point_t serialPointerEnd;
extern uint32_t serialPointerStartMs;
extern uint32_t serialPointerDurationMs;
extern bool serialFingerActive;
extern bool serialFingerPressLogged;
extern bool serialFingerReleaseSent;
extern lv_point_t serialFingerPoint;
extern uint32_t serialFingerStartMs;
extern uint32_t serialFingerHoldMs;
extern bool serialFingerManualActive;
extern bool serialFingerManualPressed;
extern bool serialFingerManualLogged;
extern bool serialTouchReplayActive;
extern uint8_t serialTouchReplayIndex;
extern uint32_t serialTouchReplayStartMs;
extern bool serialTouchReplayReleaseSent;
extern bool lvglTimerHandlerActive;
extern bool lvglTimerHandlerDeferred;

void touchInterrupt();
bool toggleRecording();
void runPairNewAction();
bool runRecordAction();
void runSnapshotAction();
void initBleStack();
void shutdownBleForWifi();
bool syncCameraState();
bool syncCameraPresets();
bool fetchSnapshotPreview();
bool httpGetGoPro(const String &path);
int httpGetGoProStatus(const String &path);
int httpGetGoProBody(const String &path, String &body);
bool httpGetGoProBinary(const String &path, uint8_t *buffer, size_t capacity, size_t &length);
void updateCameraLabel();
bool refreshCameraHardwareInfoBle();
bool refreshCameraHardwareInfoHttp();
void refreshCaptureOverlayFromState();
void updatePreview(bool force);
void updateRecordingOverlay(bool force);
void setPreviewFullscreen(bool fullscreen);
void blinkTopRightButtonMarker();
void serviceLvgl();
void setAction(const char *message);
void setPairingPopupMessage(const char *message);
void showPairingPopup(const char *message);
void finishPairingPopup(const char *message);
void hidePairingPopup();
void showForgetConfirm();
void hideForgetConfirm();
void setMaintenancePageVisible(bool visible);
void setButtonGuidePageVisible(bool visible);
void disconnectCurrentCameraForPairing();
void requestPairingCancel();
void resetBleClientForPairing();
void runForgetCameraAction();
void markConnectionCancelRequested(const char *message);
void handlePmuActionButton();
void clearSnapshotPreviewState(const char *message);
void clearPreviewJpegCache();
void releaseH264PreviewResources(const char *reason);
void handleSerialCommands();
void clearDuplicatePmuActionIrq(const char *source);
void clearBleScanDevices();
void consumeActionButtonPress();
bool pairingUiActive();
void setHomeCameraConnected(bool connected);
void setConnectRetryAvailable(bool available);
void setCameraWakeAvailable(bool available);
bool operationCancelled();
bool connectBle();
bool readGoProWifiCredentials();
bool connectGoProWifiFromBle();
bool connectGoProWifiWithCurrentCredentials(const char *reason);
bool ensureGoProWifiReady(const char *reason);
bool pairGoPro();
bool wakeGoProBle();
bool setGoProShutterBle(bool enabled);
bool refreshRecordingStateBle();
void suspendGoProWifiForRecording(const char *reason);
bool setGoProSetting(uint16_t settingId, uint16_t optionId, const char *label);
bool sendBleSetting(uint8_t settingId, uint8_t optionId, const char *label);
void storeSettingValue(uint16_t id, int option);
int getStoredSettingValue(uint16_t id);
int firstStoredSettingValue(const uint16_t *ids, size_t count, int *matchedId);
bool addSettingOption(int option, const char *displayName);
void applyCaptureLabels();
String activeOptionDisplayName(uint16_t settingId, int option);
bool querySettingOptions(const SettingDefinition &setting);
void refreshSettingSheet();
void closeSettingSheet();
void applyRecordingUiState(bool cameraRecording, uint32_t elapsedSeconds, bool elapsedKnown);
void updateGoProBatteryIndicator();
void setDisplayOn(bool enabled);
bool exitFullscreenPreview(const char *source);
void pollLivePreviewUdp();
void processTsPacket(const uint8_t *packet);
void logMemory(const char *label);
String urlEncodePathParam(const String &value);
bool fetchLatestJpegPath(String &path);
bool deleteGoProMedia(const String &path);
SnapshotVideoFraming currentSnapshotVideoFraming();
void logSnapshotVideoFraming(const SnapshotVideoFraming &framing);
void alignTemporaryPhotoPresetForSnapshot();
String firstNonEmptyCameraName();
void setCameraHardwareInfo(const String &modelNumber, const String &modelName,
                           const String &firmwareVersion, const String &serialNumber,
                           const String &apSsid, const String &apMacAddress);
void persistCameraHardwareInfo();
void clearCameraHardwareInfo();
