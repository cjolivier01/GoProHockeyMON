#include <Arduino.h>
#include <ctype.h>
#include <strings.h>
#include <BLEDevice.h>
#include <BLEScan.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <Wire.h>
#include <WiFi.h>

#include "pin_config.h"

#include <Adafruit_XCA9554.h>
#include <ArduinoJson.h>
#include <Arduino_DriveBus_Library.h>
#include <Arduino_GFX_Library.h>
#include <JPEGDEC.h>
#include <XPowersLib.h>
#include <lvgl.h>

#include "esp_heap_caps.h"
#include "esp_system.h"
#include "esp_sleep.h"
#include "esp_timer.h"
extern "C" {
#if defined(CONFIG_BLUEDROID_ENABLED)
#include "esp_gap_ble_api.h"
#endif
#if defined(CONFIG_NIMBLE_ENABLED)
#include "host/ble_store.h"
#endif
#include "h264bsd_decoder.h"
}

#ifndef GOPRO_LOCAL_WIFI_SSID
#define GOPRO_LOCAL_WIFI_SSID ""
#endif

#ifndef GOPRO_LOCAL_WIFI_PASSWORD
#define GOPRO_LOCAL_WIFI_PASSWORD ""
#endif

#ifndef GOPRO_CAMERA_WIFI_SSID
#define GOPRO_CAMERA_WIFI_SSID ""
#endif

#ifndef GOPRO_CAMERA_WIFI_PASSWORD
#define GOPRO_CAMERA_WIFI_PASSWORD ""
#endif

#ifndef GOPRO_CAMERA_NAME_FILTER
#define GOPRO_CAMERA_NAME_FILTER "GoPro,MISSION,GP"
#endif

#ifndef GOPRO_CAMERA_IP
#define GOPRO_CAMERA_IP "10.5.5.9"
#endif

#ifndef GOPRO_DEBUG_PRINT_CAMERA_PASSWORD
#define GOPRO_DEBUG_PRINT_CAMERA_PASSWORD 0
#endif

#ifndef GOPRO_AUTO_CONNECT_ON_BOOT
#define GOPRO_AUTO_CONNECT_ON_BOOT 0
#endif

namespace {
constexpr uint32_t kLvglTickMs = 2;
constexpr uint8_t kDisplayBrightness = 210;
constexpr uint32_t kPreviewRefreshMs = 1500;
constexpr uint32_t kHttpTimeoutMs = 6500;
constexpr uint32_t kButtonDebounceMs = 35;
constexpr uint32_t kActionButtonDebounceMs = 90;
constexpr uint32_t kActionButtonMinPressMs = 120;
constexpr uint32_t kBootLongPressMs = 1200;
constexpr uint32_t kPmuPollMs = 150;
constexpr uint32_t kPmuDuplicateSuppressMs = 140;
constexpr uint32_t kActionButtonDoubleClickMs = 900;
constexpr uint32_t kActionButtonLongPressMs = 1200;
constexpr uint32_t kBatteryRefreshMs = 5000;
constexpr uint32_t kBleScanSeconds = 7;
constexpr uint32_t kPairBleScanSeconds = 18;
constexpr uint32_t kBleConnectTimeoutMs = 10000;
constexpr uint32_t kPairBleConnectTimeoutMs = 3000;
constexpr uint32_t kWifiTimeoutMs = 25000;
constexpr int kPairFallbackMinRssi = -50;
constexpr int kPairScanLogMinRssi = -75;
constexpr uint32_t kDrawBufferLines = 16;
constexpr uint16_t kPreviewStreamPort = 8554;
constexpr uint32_t kLivePreviewStatsMs = 1000;
constexpr size_t kTsPacketBytes = 188;
constexpr uint16_t kGoProVideoPid = 0x1011;
constexpr int32_t kGoProVideoPresetGroup = 1000;
constexpr size_t kMaxH264AccessUnit = 512 * 1024;
constexpr uint32_t kMinDecodeIntervalMs = 1000;
constexpr size_t kMaxJpegBytes = 512 * 1024;
constexpr size_t kMaxSettingOptions = 40;
constexpr size_t kVisibleSettingOptions = 6;
constexpr uint8_t kGoProWirelessBandSetting = 178;
constexpr uint8_t kGoProWirelessBand24GHz = 0;
constexpr uint8_t kExpanderActionButtonPin = 5;
constexpr bool kExpanderActionPressedLevel = LOW;
constexpr int kHomeButtonY = 295;
constexpr int kHomeButtonH = 56;
constexpr int kForgetButtonY = kHomeButtonY + kHomeButtonH + 6;
constexpr int kForgetButtonH = 36;
constexpr int kPreviewX = 20;
constexpr int kPreviewY = 76;
constexpr int kPreviewW = 328;
constexpr int kPreviewH = 150;
constexpr int kTopBarH = 32;
constexpr int kBootButtonPin = 0;
constexpr int kNavSwipeStartPx = 18;
constexpr int kNavSwipeCommitPx = 64;
constexpr uint32_t kNavSwipeFlickMs = 650;
constexpr int kNavSwipeFlickPx = 42;
constexpr uint32_t kNavPageAnimMs = 180;
constexpr int kFullscreenSwipePx = 45;
constexpr uint8_t kSnapshotAspectCropStrengthPercent = 100;

// GoPro 5k Wide with Hypersmooth on: 89
constexpr uint8_t kSnapshotPreviewVisiblePercent = 89;

const BLEUUID kControlService("0000fea6-0000-1000-8000-00805f9b34fb");
const BLEUUID kWifiService("b5f90001-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kCameraManagementService("b5f90090-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kWifiSsid("b5f90002-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kWifiPassword("b5f90003-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kCommand("b5f90072-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kCommandResponse("b5f90073-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kSettings("b5f90074-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kSettingsResponse("b5f90075-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kCameraManagementCommand("b5f90091-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kCameraManagementResponse("b5f90092-aa8d-11e3-9046-0002a5d5c51b");

Preferences preferences;
Adafruit_XCA9554 expander;
XPowersPMU power;
JPEGDEC jpeg;

Arduino_DataBus *bus = new Arduino_ESP32QSPI(
    LCD_CS, LCD_SCLK, LCD_SDIO0, LCD_SDIO1, LCD_SDIO2, LCD_SDIO3);
Arduino_SH8601 *gfx = new Arduino_SH8601(
    bus, GFX_NOT_DEFINED, 0, LCD_WIDTH, LCD_HEIGHT);

std::shared_ptr<Arduino_IIC_DriveBus> i2cBus =
    std::make_shared<Arduino_HWIIC>(IIC_SDA, IIC_SCL, &Wire);

void touchInterrupt();
void toggleRecording();
void runPairNewAction();
void runRecordAction();
void runSnapshotAction();
void initBleStack();
bool syncCameraState();
bool fetchSnapshotPreview();
int httpGetGoProStatus(const String &path);
void refreshCaptureOverlayFromState();
void updatePreview(bool force = false);
void updateRecordingOverlay(bool force = false);
void setPreviewFullscreen(bool fullscreen);
void setAction(const char *message);
void setPairingPopupMessage(const char *message);
void showPairingPopup(const char *message);
void hidePairingPopup();
void showForgetConfirm();
void hideForgetConfirm();
void setMaintenancePageVisible(bool visible);
void disconnectCurrentCameraForPairing();
void requestPairingCancel();
void resetBleClientForPairing();
void runForgetCameraAction();
void handlePmuActionButton();
void clearSnapshotPreviewState(const char *message = nullptr);
void clearPreviewJpegCache();
void releaseH264PreviewResources(const char *reason = nullptr);
void handleSerialCommands();
void clearDuplicatePmuActionIrq(const char *source);

std::unique_ptr<Arduino_IIC> touch(new Arduino_FT3x68(
    i2cBus, FT3168_DEVICE_ADDRESS, DRIVEBUS_DEFAULT_VALUE, TP_INT,
    touchInterrupt));

lv_disp_draw_buf_t drawBuffer;
lv_disp_drv_t displayDriver;
lv_indev_drv_t touchDriver;
lv_indev_t *touchInput = nullptr;
lv_color_t *drawBuf1 = nullptr;
lv_color_t *drawBuf2 = nullptr;
BLEAdvertisedDevice *bestBleDevice = nullptr;
BLEAdvertisedDevice *fallbackBleDevice = nullptr;
BLEClient *bleClient = nullptr;
BLESecurityCallbacks *bleSecurityCallbacks = nullptr;
BLESecurity *bleSecurity = nullptr;

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
};

lv_obj_t *statusLabel = nullptr;
lv_obj_t *wifiLabel = nullptr;
lv_obj_t *cameraLabel = nullptr;
lv_obj_t *previewBox = nullptr;
lv_obj_t *previewLabel = nullptr;
lv_obj_t *recordingOverlay = nullptr;
lv_obj_t *recordingOverlayLabel = nullptr;
lv_obj_t *fullscreenHint = nullptr;
lv_obj_t *actionLabel = nullptr;
lv_obj_t *batteryLabel = nullptr;
lv_obj_t *wifiIndicator = nullptr;
lv_obj_t *bleIndicator = nullptr;
lv_obj_t *goproBatteryLabel = nullptr;
lv_obj_t *tileView = nullptr;
lv_obj_t *captureModeLabel = nullptr;
lv_obj_t *captureSettingLabel = nullptr;
lv_obj_t *recordPill = nullptr;
lv_obj_t *timeRemainingLabel = nullptr;
lv_obj_t *pairButton = nullptr;
lv_obj_t *forgetButton = nullptr;
lv_obj_t *pairingPopup = nullptr;
lv_obj_t *pairingPopupTitle = nullptr;
lv_obj_t *pairingPopupMessage = nullptr;
lv_obj_t *forgetConfirmPopup = nullptr;
lv_obj_t *maintenancePage = nullptr;
lv_obj_t *settingSheet = nullptr;
lv_obj_t *settingSheetTitle = nullptr;
lv_obj_t *settingOptionButtons[kVisibleSettingOptions] = {};
lv_obj_t *settingOptionLabels[kVisibleSettingOptions] = {};
lv_obj_t *settingPagerLabel = nullptr;
lv_obj_t *captureTileObj = nullptr;
lv_obj_t *pairButtonLabel = nullptr;
uint32_t lastPreviewUpdate = 0;
uint32_t lastPmuPollMs = 0;
uint32_t lastBatteryUpdate = 0;
bool recording = false;
bool displayOn = true;
bool pmuOnline = false;
bool expanderOnline = false;
bool bleConnected = false;
bool bleStackReady = false;
bool previewStreamRequested = false;
bool previewUdpListening = false;
bool previewFullscreen = false;
bool h264DecoderReady = false;
bool h264StreamUnsupported = false;
bool h264UnsupportedNotified = false;
bool goProWifiSuspendedForRecording = false;
int goProBatteryPercent = -1;
bool goProBatteryChargingOrPlugged = false;
bool snapshotPreviewPrepared = false;
bool snapshotPreviewBusy = false;
bool previewHasImage = false;
bool maintenancePageVisible = false;
uint32_t recordingStartedMs = 0;
uint32_t recordingElapsedBaseMs = 0;
uint32_t recordingElapsedBaseAtMs = 0;
uint32_t lastRecordingOverlayMs = 0;
uint32_t previewBytesThisWindow = 0;
uint32_t previewPacketsThisWindow = 0;
uint32_t lastPreviewStatsMs = 0;
uint32_t lastH264DecodeMs = 0;
uint32_t h264FramesDecoded = 0;
uint32_t h264DecodeFailures = 0;
String lastBleName;
String boundBleAddress;
String boundBleName;
String boundGoProSsid;
String goProSsid;
String goProPassword;
String lastSnapshotMediaPath;
String captureMode = "Video";
String captureSetting = "Sync camera state";
IPAddress cameraIp;
WiFiUDP previewUdp;
h264bsd_hd_t h264Decoder = nullptr;
uint8_t *h264AccessUnit = nullptr;
size_t h264AccessUnitLen = 0;
int32_t goProWifiChannel = 0;
uint8_t goProWifiBssid[6] = {};
bool goProWifiBssidValid = false;
const SettingDefinition *activeSetting = nullptr;
SettingValue settingValues[48] = {};
size_t settingValueCount = 0;
int settingOptions[kMaxSettingOptions] = {};
String settingOptionNames[kMaxSettingOptions];
size_t settingOptionCount = 0;
size_t settingOptionOffset = 0;
int jpegDrawX = kPreviewX;
int jpegDrawY = kPreviewY;
int jpegDrawW = kPreviewW;
int jpegDrawH = kPreviewH;
int jpegDecodeW = 1;
int jpegDecodeH = 1;
int jpegCropX = 0;
int jpegCropY = 0;
int jpegCropW = 1;
int jpegCropH = 1;
uint8_t *previewJpegCache = nullptr;
size_t previewJpegCacheLen = 0;
SnapshotVideoFraming snapshotVideoFraming;
bool redrawingCachedPreview = false;
bool bootLast = HIGH;
bool bootStable = HIGH;
uint32_t bootLastChangeMs = 0;
uint32_t bootPressedAtMs = 0;
bool actionButtonLast = !kExpanderActionPressedLevel;
bool actionButtonStable = !kExpanderActionPressedLevel;
uint32_t actionButtonLastChangeMs = 0;
uint32_t actionButtonPressedAtMs = 0;
uint32_t lastExpanderActionHandledMs = 0;
uint32_t lastPmuActionHandledMs = 0;
uint32_t suppressLowerButtonUntilMs = 0;
uint8_t actionButtonShortClickCount = 0;
uint32_t actionButtonShortClickDueMs = 0;
bool actionButtonLongHandled = false;
lv_point_t lastTouchPoint = {0, 0};
lv_point_t touchStartPoint = {0, 0};
uint32_t lastTouchMs = 0;
uint32_t touchStartMs = 0;
bool touchActive = false;
volatile bool bleResponseSeen = false;
volatile uint8_t bleResponseStatus = 0xFF;
bool allowAnyCameraScan = false;
bool pairingInProgress = false;
bool pairingCancelRequested = false;
bool connectionCancelRequested = false;
bool pairingLastCancelled = false;
bool connectRetryAvailable = false;
bool homeCameraConnected = false;
bool selectedBleFallback = false;
bool rawSwipeHandled = false;
bool navSwipeActive = false;
bool navSwipeStartedVisible = false;
uint32_t pairingPopupHideDueMs = 0;
PendingHomeAction pendingHomeAction = PendingHomeAction::None;
uint32_t pendingHomeActionDueMs = 0;
uint32_t lastHomeTouchMs = 0;
bool expanderActionPinLast = !kExpanderActionPressedLevel;
bool goproActionBusy = false;
String serialCommandLine;
uint16_t bleScanCandidateCount = 0;
uint16_t bleScanSkippedCount = 0;
uint16_t bleScanAddressMatchCount = 0;
uint16_t bleScanNameMatchCount = 0;
uint16_t bleScanSeenCount = 0;
bool serialPointerActive = false;
lv_point_t serialPointerStart = {0, 0};
lv_point_t serialPointerEnd = {0, 0};
uint32_t serialPointerStartMs = 0;
uint32_t serialPointerDurationMs = 0;

// Keep these implementation parts in order; they share the anonymous namespace state above.
#include "parts/display_input_preview.inc"
#include "parts/ble_wifi_http.inc"
#include "parts/camera_state_settings.inc"
#include "parts/actions_snapshot.inc"
#include "parts/ui_build.inc"
#include "parts/buttons_serial.inc"
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("GoPro AMOLED UI boot");
  esp_reset_reason_t resetReason = esp_reset_reason();
  Serial.printf("Reset reason: %s (%u)\n", resetReasonName(resetReason),
                static_cast<unsigned>(resetReason));
  logMemory("Boot memory");
  cameraIp.fromString(GOPRO_CAMERA_IP);
  loadCameraBinding();
  initBleStack();

  Wire.begin(IIC_SDA, IIC_SCL);
  Wire.setClock(400000);
  expanderOnline = initPowerExpander();
  initPowerKey();

  pinMode(kBootButtonPin, INPUT_PULLUP);
  bootLast = digitalRead(kBootButtonPin);
  bootStable = bootLast;
  if (expanderOnline) {
    actionButtonLast = expander.digitalRead(kExpanderActionButtonPin);
    actionButtonStable = actionButtonLast;
    expanderActionPinLast = actionButtonLast;
    Serial.printf("Action pin p%u initial=%u pressed=%u\n", kExpanderActionButtonPin,
                  actionButtonLast, kExpanderActionPressedLevel);
  }

  while (!touch->begin()) {
    Serial.println("FT3168 touch init failed, retrying");
    delay(500);
  }
  touch->IIC_Write_Device_State(
      Arduino_IIC_Touch::Device::TOUCH_POWER_MODE,
      Arduino_IIC_Touch::Device_Mode::TOUCH_POWER_MONITOR);

  if (!gfx->begin()) {
    Serial.println("Display init returned false");
  }
  gfx->setBrightness(kDisplayBrightness);
  gfx->fillScreen(0x0000);

  lv_init();
  const uint32_t pixels = LCD_WIDTH * kDrawBufferLines;
  drawBuf1 = static_cast<lv_color_t *>(
      heap_caps_malloc(pixels * sizeof(lv_color_t), MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL));
  drawBuf2 = static_cast<lv_color_t *>(
      heap_caps_malloc(pixels * sizeof(lv_color_t), MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL));
  if (!drawBuf1 || !drawBuf2) {
    Serial.println("LVGL buffer allocation failed");
    while (true) {
      delay(1000);
    }
  }

  lv_disp_draw_buf_init(&drawBuffer, drawBuf1, drawBuf2, pixels);
  lv_disp_drv_init(&displayDriver);
  displayDriver.hor_res = LCD_WIDTH;
  displayDriver.ver_res = LCD_HEIGHT;
  displayDriver.flush_cb = flushDisplay;
  displayDriver.draw_buf = &drawBuffer;
  lv_disp_drv_register(&displayDriver);

  lv_indev_drv_init(&touchDriver);
  touchDriver.type = LV_INDEV_TYPE_POINTER;
  touchDriver.read_cb = readTouch;
  touchInput = lv_indev_drv_register(&touchDriver);

  const esp_timer_create_args_t tickArgs = {
      .callback = lvTick,
      .arg = nullptr,
      .dispatch_method = ESP_TIMER_TASK,
      .name = "lvgl_tick",
      .skip_unhandled_events = true,
  };
  esp_timer_handle_t tickTimer = nullptr;
  esp_timer_create(&tickArgs, &tickTimer);
  esp_timer_start_periodic(tickTimer, kLvglTickMs * 1000);

  createUi();
  updateBatteryStatus(true);
  Serial.println("AMOLED UI ready");
#if GOPRO_AUTO_CONNECT_ON_BOOT
  if (!boundBleAddress.isEmpty()) {
    pendingHomeAction = PendingHomeAction::Connect;
    pendingHomeActionDueMs = millis() + 1500;
    Serial.println("Auto-connect scheduled");
  } else {
    setAction("No saved camera; tap Pair New");
    Serial.println("Auto-connect skipped: no saved camera binding");
  }
#endif
}

void loop() {
  handleSerialCommands();
  lv_timer_handler();
  handlePendingHomeAction();
  handleBootButton();
  handleExpanderActionButton();
  handleActionButtonHold();
  handlePmuActionButton();
  handleExpanderDiagnostics();
  handlePendingActionButtonClick();
  handlePairingPopupTimeout();
  updateBatteryStatus();
  updateWifiStatus();
  updateRecordingOverlay();
  delay(5);
}
