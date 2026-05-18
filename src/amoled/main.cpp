#include <Arduino.h>
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
constexpr uint32_t kPmuDuplicateSuppressMs = 350;
constexpr uint32_t kActionButtonDoubleClickMs = 450;
constexpr uint32_t kActionButtonLongPressMs = 1200;
constexpr uint32_t kBatteryRefreshMs = 5000;
constexpr uint32_t kBleScanSeconds = 7;
constexpr uint32_t kBleConnectTimeoutMs = 10000;
constexpr uint32_t kPairBleConnectTimeoutMs = 3000;
constexpr uint32_t kWifiTimeoutMs = 25000;
constexpr uint32_t kDrawBufferLines = 16;
constexpr uint16_t kPreviewStreamPort = 8554;
constexpr uint32_t kLivePreviewStatsMs = 1000;
constexpr size_t kTsPacketBytes = 188;
constexpr uint16_t kGoProVideoPid = 0x1011;
constexpr size_t kMaxH264AccessUnit = 512 * 1024;
constexpr uint32_t kMinDecodeIntervalMs = 1000;
constexpr size_t kMaxJpegBytes = 768 * 1024;
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
void refreshCaptureOverlayFromState();
void updatePreview(bool force = false);
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

std::unique_ptr<Arduino_IIC> touch(new Arduino_FT3x68(
    i2cBus, FT3168_DEVICE_ADDRESS, DRIVEBUS_DEFAULT_VALUE, TP_INT,
    touchInterrupt));

lv_disp_draw_buf_t drawBuffer;
lv_disp_drv_t displayDriver;
lv_indev_drv_t touchDriver;
lv_color_t *drawBuf1 = nullptr;
lv_color_t *drawBuf2 = nullptr;
BLEAdvertisedDevice *bestBleDevice = nullptr;
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
bool snapshotPreviewPrepared = false;
bool snapshotPreviewBusy = false;
bool previewHasImage = false;
bool maintenancePageVisible = false;
uint32_t recordingStartedMs = 0;
uint32_t lastRecordingOverlayMs = 0;
uint32_t previewBytesThisWindow = 0;
uint32_t previewPacketsThisWindow = 0;
uint32_t lastPreviewStatsMs = 0;
uint32_t lastH264DecodeMs = 0;
uint32_t h264FramesDecoded = 0;
uint32_t h264DecodeFailures = 0;
String lastBleName;
String boundBleAddress;
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
const SettingDefinition *activeSetting = nullptr;
SettingValue settingValues[48] = {};
size_t settingValueCount = 0;
int settingOptions[kMaxSettingOptions] = {};
String settingOptionNames[kMaxSettingOptions];
size_t settingOptionCount = 0;
size_t settingOptionOffset = 0;
int jpegDrawX = kPreviewX;
int jpegDrawY = kPreviewY;
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
bool deferBleBindingSave = false;
bool rawSwipeHandled = false;
uint32_t pairingPopupHideDueMs = 0;
PendingHomeAction pendingHomeAction = PendingHomeAction::None;
uint32_t pendingHomeActionDueMs = 0;
uint32_t lastHomeTouchMs = 0;
bool expanderActionPinLast = !kExpanderActionPressedLevel;
bool goproActionBusy = false;

bool pointInRect(int16_t x, int16_t y, int16_t rx, int16_t ry, int16_t rw, int16_t rh) {
  return x >= rx && x < rx + rw && y >= ry && y < ry + rh;
}

bool pointInPairButtonRaw(int16_t x, int16_t y) {
  if (previewFullscreen) {
    return false;
  }
  return pointInRect(x, y, kPreviewX, kTopBarH + kHomeButtonY, kPreviewW, kHomeButtonH) ||
         pointInRect(x, y, kPreviewX, kHomeButtonY, kPreviewW, kHomeButtonH);
}

bool pairingUiActive() {
  return pairingInProgress || pendingHomeAction == PendingHomeAction::Pair ||
         (pairingPopup && !lv_obj_has_flag(pairingPopup, LV_OBJ_FLAG_HIDDEN));
}

void consumeActionButtonPress() {
  actionButtonShortClickCount = 0;
  actionButtonShortClickDueMs = 0;
  actionButtonPressedAtMs = 0;
  actionButtonLongHandled = true;
}

bool exitFullscreenPreview(const char *source) {
  if (!displayOn || !previewFullscreen) {
    return false;
  }
  Serial.printf("%s: exit fullscreen preview\n", source);
  setPreviewFullscreen(false);
  if (previewLabel && previewHasImage) {
    lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
  }
  setAction("Preview minimized");
  lv_timer_handler();
  return true;
}

void queuePairNewAction(const char *source) {
  if (recording) {
    setAction("Stop recording before pairing");
    return;
  }
  if (goproActionBusy || pairingInProgress || pendingHomeAction == PendingHomeAction::Pair) {
    return;
  }
  pendingHomeAction = PendingHomeAction::Pair;
  pendingHomeActionDueMs = millis() + 50;
  lastHomeTouchMs = millis();
  showPairingPopup("Pairing New Camera\n\nStarting scan...\nPress lower button to cancel.");
  if (statusLabel) {
    lv_label_set_text(statusLabel, "Pair New");
  }
  if (actionLabel) {
    lv_label_set_text(actionLabel, "Opening Pair New");
  }
  Serial.print("Pair New queued");
  if (source && source[0]) {
    Serial.print(": ");
    Serial.print(source);
  }
  Serial.println();
}

bool handleRawPreviewSwipe(const lv_point_t &start, const lv_point_t &end, uint32_t durationMs) {
  if (durationMs > 1800) {
    return false;
  }
  int dx = end.x - start.x;
  int dy = end.y - start.y;
  if (start.y < kTopBarH || end.y < kTopBarH) {
    return false;
  }

  if (previewFullscreen) {
    if (abs(dy) < 45 || abs(dy) < abs(dx)) {
      return false;
    }
    if (dy < 0) {
      Serial.printf("Raw swipe up exits fullscreen: %d,%d -> %d,%d\n",
                    start.x, start.y, end.x, end.y);
      return exitFullscreenPreview("Raw swipe up");
    }
    return false;
  }

  if ((settingSheet && !lv_obj_has_flag(settingSheet, LV_OBJ_FLAG_HIDDEN)) ||
      (forgetConfirmPopup && !lv_obj_has_flag(forgetConfirmPopup, LV_OBJ_FLAG_HIDDEN))) {
    return false;
  }
  if (abs(dx) < 45 || abs(dx) * 10 < abs(dy) * 12) {
    return false;
  }
  if (dx > 0 && !maintenancePageVisible) {
    Serial.printf("Raw swipe right opens maintenance: %d,%d -> %d,%d\n",
                  start.x, start.y, end.x, end.y);
    setMaintenancePageVisible(true);
    return true;
  } else if (dx < 0 && maintenancePageVisible) {
    Serial.printf("Raw swipe left returns home: %d,%d -> %d,%d\n",
                  start.x, start.y, end.x, end.y);
    setMaintenancePageVisible(false);
    return true;
  }
  return false;
}

void onPageGesture(lv_event_t *) {
  lv_dir_t dir = lv_indev_get_gesture_dir(lv_indev_get_act());
  if (previewFullscreen) {
    if (dir == LV_DIR_TOP) {
      exitFullscreenPreview("LVGL swipe up");
    }
    return;
  }
  if (dir == LV_DIR_RIGHT && !maintenancePageVisible) {
    setMaintenancePageVisible(true);
  } else if (dir == LV_DIR_LEFT && maintenancePageVisible) {
    setMaintenancePageVisible(false);
  }
}

void onPreviewGesture(lv_event_t *) {
  lv_dir_t dir = lv_indev_get_gesture_dir(lv_indev_get_act());
  if (dir == LV_DIR_TOP && previewFullscreen) {
    Serial.printf("Raw swipe up exits fullscreen: %d,%d -> %d,%d\n",
                  touchStartPoint.x, touchStartPoint.y, lastTouchPoint.x, lastTouchPoint.y);
    exitFullscreenPreview("Preview swipe up");
  }
}

void touchInterrupt() {
  touch->IIC_Interrupt_Flag = true;
}

void lvTick(void *) {
  lv_tick_inc(kLvglTickMs);
}

void flushDisplay(lv_disp_drv_t *disp, const lv_area_t *area, lv_color_t *colorP) {
  const uint32_t w = area->x2 - area->x1 + 1;
  const uint32_t h = area->y2 - area->y1 + 1;
#if (LV_COLOR_16_SWAP != 0)
  gfx->draw16bitBeRGBBitmap(area->x1, area->y1,
                            reinterpret_cast<uint16_t *>(&colorP->full), w, h);
#else
  gfx->draw16bitRGBBitmap(area->x1, area->y1,
                          reinterpret_cast<uint16_t *>(&colorP->full), w, h);
#endif
  lv_disp_flush_ready(disp);
}

void readTouch(lv_indev_drv_t *, lv_indev_data_t *data) {
  uint32_t now = millis();
  bool pollTouch = touch->IIC_Interrupt_Flag || touchActive;
  if (pollTouch) {
    bool hadInterrupt = touch->IIC_Interrupt_Flag;
    touch->IIC_Interrupt_Flag = false;
    int16_t rawX = touch->IIC_Read_Device_Value(
        Arduino_IIC_Touch::Value_Information::TOUCH_COORDINATE_X);
    int16_t rawY = touch->IIC_Read_Device_Value(
        Arduino_IIC_Touch::Value_Information::TOUCH_COORDINATE_Y);
    uint8_t fingers = touch->IIC_Read_Device_Value(
        Arduino_IIC_Touch::Value_Information::TOUCH_FINGER_NUMBER);
    if (hadInterrupt) {
      Serial.printf("Touch raw x=%d y=%d fingers=%u\n", rawX, rawY, fingers);
    }

    if (fingers > 0) {
      if (!touchActive) {
        touchStartPoint.x = rawX;
        touchStartPoint.y = rawY;
        touchStartMs = now;
        touchActive = true;
        rawSwipeHandled = false;
      }
      lastTouchPoint.x = rawX;
      lastTouchPoint.y = rawY;
      lastTouchMs = now;
      data->state = LV_INDEV_STATE_PR;
      data->point = lastTouchPoint;
      if (!rawSwipeHandled &&
          handleRawPreviewSwipe(touchStartPoint, lastTouchPoint, now - touchStartMs)) {
        rawSwipeHandled = true;
      }
    } else {
      if (touchActive && !rawSwipeHandled) {
        rawSwipeHandled = handleRawPreviewSwipe(touchStartPoint, lastTouchPoint, now - touchStartMs);
      }
      touchActive = false;
      rawSwipeHandled = false;
      data->state = LV_INDEV_STATE_REL;
      data->point = lastTouchPoint;
      return;
    }

    if (statusLabel && now - lastHomeTouchMs > 300) {
      char label[40];
      snprintf(label, sizeof(label), "Touch %d,%d", rawX, rawY);
      lv_label_set_text(statusLabel, label);
    }
  } else if (now - lastTouchMs < 180) {
    data->state = LV_INDEV_STATE_PR;
    data->point = lastTouchPoint;
  } else {
    data->state = LV_INDEV_STATE_REL;
    data->point = lastTouchPoint;
  }
}

void styleButton(lv_obj_t *button, lv_color_t color) {
  lv_obj_set_style_radius(button, 8, 0);
  lv_obj_set_style_bg_color(button, color, 0);
  lv_obj_set_style_bg_opa(button, LV_OPA_COVER, 0);
  lv_obj_set_style_border_width(button, 0, 0);
  lv_obj_set_style_shadow_width(button, 10, 0);
  lv_obj_set_style_shadow_opa(button, LV_OPA_20, 0);
}

const lv_font_t *fontForSize(int size) {
  if (size >= 24) {
    return &lv_font_montserrat_24;
  }
  if (size >= 22) {
    return &lv_font_montserrat_22;
  }
  if (size >= 18) {
    return &lv_font_montserrat_20;
  }
  if (size >= 16) {
    return &lv_font_montserrat_18;
  }
  return &lv_font_montserrat_16;
}

lv_obj_t *makeButton(lv_obj_t *parent, const char *text, lv_color_t color) {
  lv_obj_t *button = lv_btn_create(parent);
  styleButton(button, color);
  lv_obj_t *label = lv_label_create(button);
  lv_label_set_text(label, text);
  lv_obj_set_style_text_font(label, fontForSize(18), 0);
  lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_center(label);
  return button;
}

lv_obj_t *makeChip(lv_obj_t *parent, const char *text, int x, int y, int w, lv_color_t color) {
  lv_obj_t *chip = makeButton(parent, text, color);
  lv_obj_set_size(chip, w, 40);
  lv_obj_set_pos(chip, x, y);
  return chip;
}

lv_obj_t *makeTouchButton(lv_obj_t *parent, const char *text, int x, int y, int w, int h,
                          lv_color_t color) {
  lv_obj_t *button = makeButton(parent, text, color);
  lv_obj_set_size(button, w, h);
  lv_obj_set_pos(button, x, y);
  return button;
}

void setAction(const char *message) {
  if (actionLabel) {
    lv_label_set_text(actionLabel, message);
  }
  if (pairingInProgress) {
    String popup = message;
    popup += "\n\nLower button cancels.";
    setPairingPopupMessage(popup.c_str());
  }
  Serial.println(message);
  if (tileView) {
    lv_timer_handler();
  }
}

void logMemory(const char *label) {
  Serial.printf("%s heap=%u internal=%u psram=%u\n", label,
                ESP.getFreeHeap(),
                heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
                heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
}

void setObjHidden(lv_obj_t *obj, bool hidden) {
  if (!obj) {
    return;
  }
  if (hidden) {
    lv_obj_add_flag(obj, LV_OBJ_FLAG_HIDDEN);
  } else {
    lv_obj_clear_flag(obj, LV_OBJ_FLAG_HIDDEN);
  }
}

void setPairingPopupMessage(const char *message) {
  if (!pairingPopupMessage) {
    return;
  }
  String status = message == nullptr ? "" : message;
  constexpr const char *heading = "Pairing New Camera";
  if (status.startsWith(heading)) {
    status.remove(0, strlen(heading));
    while (status.startsWith("\n")) {
      status.remove(0, 1);
    }
  }
  status.trim();
  if (status.isEmpty()) {
    status = "Starting...";
  }
  lv_label_set_text(pairingPopupMessage, status.c_str());
}

void showPairingPopup(const char *message) {
  pairingPopupHideDueMs = 0;
  setPairingPopupMessage(message);
  if (pairingPopup) {
    lv_obj_clear_flag(pairingPopup, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_foreground(pairingPopup);
    lv_timer_handler();
  }
}

void finishPairingPopup(const char *message) {
  setPairingPopupMessage(message);
  if (pairingPopup) {
    lv_obj_clear_flag(pairingPopup, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_foreground(pairingPopup);
    pairingPopupHideDueMs = millis() + 1800;
    lv_timer_handler();
  }
}

void hidePairingPopup() {
  pairingPopupHideDueMs = 0;
  if (pairingPopup) {
    lv_obj_add_flag(pairingPopup, LV_OBJ_FLAG_HIDDEN);
  }
}

void setMaintenancePageVisible(bool visible) {
  maintenancePageVisible = visible;
  if (!maintenancePage) {
    return;
  }
  if (visible) {
    lv_obj_clear_flag(maintenancePage, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_foreground(maintenancePage);
    hidePairingPopup();
    setAction("Maintenance");
  } else {
    hideForgetConfirm();
    lv_obj_add_flag(maintenancePage, LV_OBJ_FLAG_HIDDEN);
    setAction("Preview");
  }
  lv_timer_handler();
}

void showForgetConfirm() {
  if (!forgetConfirmPopup) {
    return;
  }
  lv_obj_clear_flag(forgetConfirmPopup, LV_OBJ_FLAG_HIDDEN);
  lv_obj_move_foreground(forgetConfirmPopup);
  setAction("Confirm forget camera");
  lv_timer_handler();
}

void hideForgetConfirm() {
  if (forgetConfirmPopup) {
    lv_obj_add_flag(forgetConfirmPopup, LV_OBJ_FLAG_HIDDEN);
  }
}

void clearSnapshotPreviewState(const char *message) {
  previewHasImage = false;
  snapshotPreviewBusy = false;
  snapshotPreviewPrepared = false;
  lastSnapshotMediaPath = "";
  if (previewFullscreen) {
    setPreviewFullscreen(false);
  }
  if (previewLabel) {
    lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    lv_label_set_text(previewLabel, message == nullptr ? "Double-click lower for snapshot" : message);
    lv_obj_center(previewLabel);
  }
}

int previewFrameX() {
  return previewFullscreen ? 0 : kPreviewX;
}

int previewFrameY() {
  return previewFullscreen ? kTopBarH : kTopBarH + 6;
}

int previewFrameW() {
  return previewFullscreen ? LCD_WIDTH : kPreviewW;
}

int previewFrameH() {
  return previewFullscreen ? LCD_HEIGHT - kTopBarH : kPreviewH;
}

void drawFullscreenSwipeHandle() {
  if (!previewFullscreen) {
    return;
  }
  constexpr int handleW = 112;
  constexpr int handleH = 5;
  int x = (LCD_WIDTH - handleW) / 2;
  int y = LCD_HEIGHT - 12;
  gfx->fillRoundRect(x, y, handleW, handleH, 2, 0xffff);
}

void setPreviewFullscreen(bool fullscreen) {
  previewFullscreen = fullscreen;
  if (!previewBox || !fullscreenHint) {
    return;
  }

  if (fullscreen) {
    hideForgetConfirm();
    if (maintenancePage) {
      lv_obj_add_flag(maintenancePage, LV_OBJ_FLAG_HIDDEN);
      maintenancePageVisible = false;
    }
    lv_obj_set_pos(previewBox, 0, 0);
    lv_obj_set_size(previewBox, LCD_WIDTH, LCD_HEIGHT - kTopBarH);
    lv_obj_set_style_radius(previewBox, 0, 0);
    lv_obj_set_style_border_width(previewBox, 0, 0);
    lv_obj_align(fullscreenHint, LV_ALIGN_BOTTOM_MID, 0, -4);
  } else {
    lv_obj_set_size(previewBox, kPreviewW, kPreviewH);
    lv_obj_set_pos(previewBox, kPreviewX, 6);
    lv_obj_set_style_radius(previewBox, 8, 0);
    lv_obj_set_style_border_width(previewBox, 1, 0);
    lv_obj_align(fullscreenHint, LV_ALIGN_BOTTOM_MID, 0, 4);
  }
  if (recordingOverlay) {
    lv_obj_center(recordingOverlay);
  }

  setObjHidden(recordPill, true);
  setObjHidden(timeRemainingLabel, true);
  setObjHidden(captureModeLabel, fullscreen);
  setObjHidden(captureSettingLabel, fullscreen);
  setObjHidden(cameraLabel, fullscreen);
  setObjHidden(wifiLabel, fullscreen);
  setObjHidden(pairButton, fullscreen);
  setObjHidden(forgetButton, fullscreen);
  setObjHidden(actionLabel, fullscreen);
  setObjHidden(recordingOverlay, !recording);
  lv_obj_move_foreground(previewBox);
  if (recordingOverlay) {
    lv_obj_move_foreground(recordingOverlay);
  }
  lv_obj_move_foreground(fullscreenHint);
}

String formatElapsed(uint32_t elapsedMs) {
  uint32_t totalSeconds = elapsedMs / 1000;
  uint32_t hours = totalSeconds / 3600;
  uint32_t minutes = (totalSeconds / 60) % 60;
  uint32_t seconds = totalSeconds % 60;
  char text[16];
  if (hours > 0) {
    snprintf(text, sizeof(text), "%lu:%02lu:%02lu",
             static_cast<unsigned long>(hours),
             static_cast<unsigned long>(minutes),
             static_cast<unsigned long>(seconds));
  } else {
    snprintf(text, sizeof(text), "%02lu:%02lu",
             static_cast<unsigned long>(minutes),
             static_cast<unsigned long>(seconds));
  }
  return String(text);
}

void updateRecordingOverlay(bool force = false) {
  if (!recordingOverlay || !recordingOverlayLabel) {
    return;
  }
  if (!recording) {
    lv_obj_add_flag(recordingOverlay, LV_OBJ_FLAG_HIDDEN);
    return;
  }

  uint32_t now = millis();
  if (!force && now - lastRecordingOverlayMs < 1000) {
    return;
  }
  lastRecordingOverlayMs = now;

  String text = "RECORDING\n";
  text += formatElapsed(recordingStartedMs == 0 ? 0 : now - recordingStartedMs);
  lv_label_set_text(recordingOverlayLabel, text.c_str());
  lv_obj_clear_flag(recordingOverlay, LV_OBJ_FLAG_HIDDEN);
  lv_obj_move_foreground(recordingOverlay);
}

bool initH264Decoder() {
  if (h264DecoderReady) {
    return true;
  }
  if (!h264AccessUnit) {
    h264AccessUnit = static_cast<uint8_t *>(
        heap_caps_malloc(kMaxH264AccessUnit, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    if (!h264AccessUnit) {
      h264AccessUnit = static_cast<uint8_t *>(
          heap_caps_malloc(kMaxH264AccessUnit, MALLOC_CAP_8BIT));
    }
  }
  if (!h264AccessUnit) {
    Serial.println("H264 access-unit allocation failed");
    return false;
  }

  h264bsd_cfg_t cfg = H264BSD_CFG_DEFAULT();
  cfg.dualTaskEnable = 0;
  h264Decoder = h264bsdAlloc(&cfg);
  if (!h264Decoder) {
    Serial.println("H264 decoder allocation failed");
    return false;
  }
  if (h264bsdInit(h264Decoder, 1) != 0) {
    Serial.println("H264 decoder init failed");
    h264bsdFree(h264Decoder);
    h264Decoder = nullptr;
    return false;
  }
  h264DecoderReady = true;
  Serial.printf("H264 decoder ready: %s\n", esp_tinyh264_get_version());
  return true;
}

bool h264AccessUnitHasIdr(const uint8_t *data, size_t len) {
  for (size_t i = 0; i + 5 < len; ++i) {
    size_t nal = 0;
    if (data[i] == 0 && data[i + 1] == 0 && data[i + 2] == 1) {
      nal = i + 3;
    } else if (data[i] == 0 && data[i + 1] == 0 && data[i + 2] == 0 && data[i + 3] == 1) {
      nal = i + 4;
    }
    if (nal > 0 && nal < len && (data[nal] & 0x1f) == 5) {
      return true;
    }
  }
  return false;
}

void drawI420Preview(const uint8_t *pic, uint32_t width, uint32_t height) {
  if (!pic || width == 0 || height == 0 || !previewBox) {
    return;
  }
  uint32_t outW = previewFullscreen ? LCD_WIDTH : kPreviewW;
  uint32_t outH = previewFullscreen ? (LCD_HEIGHT - kTopBarH) : kPreviewH;
  uint32_t drawH = min<uint32_t>(outH, (outW * height) / width);
  uint32_t drawY = previewFullscreen ? kTopBarH + ((outH - drawH) / 2) : (kTopBarH + 6);

  uint16_t *line = static_cast<uint16_t *>(heap_caps_malloc(outW * sizeof(uint16_t), MALLOC_CAP_DMA));
  if (!line) {
    line = static_cast<uint16_t *>(heap_caps_malloc(outW * sizeof(uint16_t), MALLOC_CAP_INTERNAL));
  }
  if (!line) {
    return;
  }

  const uint8_t *yPlane = pic;
  const uint8_t *uPlane = yPlane + width * height;
  const uint8_t *vPlane = uPlane + (width * height) / 4;
  for (uint32_t y = 0; y < drawH; ++y) {
    uint32_t srcY = (y * height) / drawH;
    for (uint32_t x = 0; x < outW; ++x) {
      uint32_t srcX = (x * width) / outW;
      int yy = yPlane[srcY * width + srcX];
      int uu = uPlane[(srcY / 2) * (width / 2) + (srcX / 2)] - 128;
      int vv = vPlane[(srcY / 2) * (width / 2) + (srcX / 2)] - 128;
      int r = constrain(yy + ((1436 * vv) >> 10), 0, 255);
      int g = constrain(yy - ((352 * uu + 731 * vv) >> 10), 0, 255);
      int b = constrain(yy + ((1814 * uu) >> 10), 0, 255);
      line[x] = ((r & 0xf8) << 8) | ((g & 0xfc) << 3) | (b >> 3);
    }
    gfx->draw16bitRGBBitmap(0, drawY + y, line, outW, 1);
  }
  free(line);
}

void decodeH264AccessUnit() {
  if (h264StreamUnsupported) {
    h264AccessUnitLen = 0;
    return;
  }
  if (h264AccessUnitLen == 0 || millis() - lastH264DecodeMs < kMinDecodeIntervalMs) {
    return;
  }
  if (!h264AccessUnitHasIdr(h264AccessUnit, h264AccessUnitLen)) {
    h264AccessUnitLen = 0;
    return;
  }
  lastH264DecodeMs = millis();
  if (!initH264Decoder()) {
    h264AccessUnitLen = 0;
    return;
  }

  u8 *pic = nullptr;
  u32 width = 0;
  u32 height = 0;
  u32 remaining = h264AccessUnitLen;
  uint32_t ret = h264bsdDecode(h264Decoder, h264AccessUnit, &remaining, &pic, &width, &height);
  Serial.printf("H264 decode AU len=%u ret=%u remaining=%u size=%ux%u\n",
                h264AccessUnitLen, ret, remaining, width, height);
  if (ret == H264BSD_PIC_RDY && pic && width > 0 && height > 0) {
    h264FramesDecoded++;
    lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    drawI420Preview(pic, width, height);
  } else if (ret == H264BSD_ERROR || ret == H264BSD_PARAM_SET_ERROR || ret == H264BSD_MEMALLOC_ERROR) {
    h264DecodeFailures++;
    if (h264DecodeFailures >= 3) {
      h264StreamUnsupported = true;
      if (!h264UnsupportedNotified) {
        h264UnsupportedNotified = true;
        setAction("Preview connected; decoder needs P4/host");
      }
    }
    lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    lv_label_set_text(previewLabel, h264StreamUnsupported
                                        ? "Stream connected\nP4/host decoder required"
                                        : "Trying H.264 decode");
  }
  h264AccessUnitLen = 0;
}

void appendH264Payload(const uint8_t *payload, size_t len, bool start) {
  if (start && h264AccessUnitLen > 0) {
    decodeH264AccessUnit();
    h264AccessUnitLen = 0;
  }
  if (!initH264Decoder()) {
    return;
  }
  if (len == 0 || h264AccessUnitLen + len > kMaxH264AccessUnit) {
    h264AccessUnitLen = 0;
    return;
  }
  memcpy(h264AccessUnit + h264AccessUnitLen, payload, len);
  h264AccessUnitLen += len;
}

void processTsPacket(const uint8_t *packet) {
  if (packet[0] != 0x47) {
    return;
  }
  bool payloadStart = packet[1] & 0x40;
  uint16_t pid = ((packet[1] & 0x1f) << 8) | packet[2];
  if (pid != kGoProVideoPid) {
    return;
  }
  uint8_t adaptation = (packet[3] >> 4) & 0x03;
  size_t offset = 4;
  if (adaptation == 0 || adaptation == 2) {
    return;
  }
  if (adaptation == 3) {
    offset += 1 + packet[offset];
    if (offset >= kTsPacketBytes) {
      return;
    }
  }

  if (payloadStart) {
    if (kTsPacketBytes - offset < 9 || packet[offset] != 0 || packet[offset + 1] != 0 ||
        packet[offset + 2] != 1) {
      return;
    }
    uint8_t flags = packet[offset + 7];
    uint8_t headerLen = packet[offset + 8];
    (void)flags;
    offset += 9 + headerLen;
    if (offset >= kTsPacketBytes) {
      appendH264Payload(nullptr, 0, true);
      return;
    }
  }
  appendH264Payload(packet + offset, kTsPacketBytes - offset, payloadStart);
}

void configureBleSecurity() {
  if (bleSecurityCallbacks == nullptr) {
    bleSecurityCallbacks = new BLESecurityCallbacks();
  }
  if (bleSecurity == nullptr) {
    bleSecurity = new BLESecurity();
  }
  BLEDevice::setSecurityCallbacks(bleSecurityCallbacks);
  bleSecurity->setAuthenticationMode(true, false, true);
  bleSecurity->setCapability(ESP_IO_CAP_NONE);
  bleSecurity->setForceAuthentication(false);
}

void initBleStack() {
  if (BLEDevice::getInitialized()) {
    bleStackReady = true;
    configureBleSecurity();
    return;
  }
  if (WiFi.getMode() != WIFI_MODE_NULL) {
    WiFi.disconnect(true, true);
    WiFi.mode(WIFI_OFF);
    delay(250);
    logMemory("After WiFi shutdown for BLE");
  }
  BLEDevice::init("ESP32-GoPro-Remote");
  configureBleSecurity();
  bleStackReady = true;
  Serial.println("BLE security bonding enabled");
  logMemory("After BLE init");
}

void shutdownBleForWifi() {
  if (!BLEDevice::getInitialized()) {
    return;
  }
  logMemory("Before BLE shutdown");
  if (bleClient != nullptr && bleClient->isConnected()) {
    bleClient->disconnect();
    delay(150);
  }
  bleClient = nullptr;
  bleConnected = false;
  if (bleIndicator) {
    lv_obj_set_style_text_color(bleIndicator, lv_color_hex(0x5a6472), 0);
  }
  delete bestBleDevice;
  bestBleDevice = nullptr;
  BLEDevice::deinit(false);
  bleStackReady = false;
  delay(250);
  logMemory("After BLE shutdown");
}

String trimCopy(String value) {
  value.trim();
  return value;
}

bool containsIgnoreCase(const String &text, const String &needle) {
  String lowerText = text;
  String lowerNeedle = needle;
  lowerText.toLowerCase();
  lowerNeedle.toLowerCase();
  return lowerText.indexOf(lowerNeedle) >= 0;
}

bool nameMatchesFilter(const String &name) {
  if (name.isEmpty()) {
    return false;
  }

  String filters = GOPRO_CAMERA_NAME_FILTER;
  int start = 0;
  while (start < filters.length()) {
    int comma = filters.indexOf(',', start);
    if (comma < 0) {
      comma = filters.length();
    }
    String token = trimCopy(filters.substring(start, comma));
    if (!token.isEmpty() && containsIgnoreCase(name, token)) {
      return true;
    }
    start = comma + 1;
  }
  return false;
}

void loadCameraBinding() {
  preferences.begin("gopro", false);
  boundBleAddress = preferences.getString("ble_addr", "");
  if (!boundBleAddress.isEmpty()) {
    boundBleAddress.toLowerCase();
    Serial.print(F("Bound GoPro BLE address: "));
    Serial.println(boundBleAddress);
  } else {
    Serial.println(F("No saved GoPro BLE binding"));
  }
}

void saveCameraBinding(BLEAdvertisedDevice &device) {
  String address = device.getAddress().toString().c_str();
  address.toLowerCase();
  if (address.isEmpty()) {
    return;
  }
  boundBleAddress = address;
  preferences.putString("ble_addr", boundBleAddress);
  clearSnapshotPreviewState("Double-click lower for snapshot");
  Serial.print(F("Saved GoPro BLE binding: "));
  Serial.println(boundBleAddress);
}

int clearBleBondStore() {
  int removed = 0;
  initBleStack();
#if defined(CONFIG_BLUEDROID_ENABLED)
  int devCount = esp_ble_get_bond_device_num();
  if (devCount > 0) {
    esp_ble_bond_dev_t *devices =
        static_cast<esp_ble_bond_dev_t *>(calloc(devCount, sizeof(esp_ble_bond_dev_t)));
    if (devices != nullptr) {
      int listCount = devCount;
      if (esp_ble_get_bond_device_list(&listCount, devices) == ESP_OK) {
        for (int i = 0; i < listCount; ++i) {
          if (esp_ble_remove_bond_device(devices[i].bd_addr) == ESP_OK) {
            removed++;
          }
        }
      }
      free(devices);
    }
  }
#elif defined(CONFIG_NIMBLE_ENABLED)
  int count = 0;
  ble_store_util_count(BLE_STORE_OBJ_TYPE_PEER_SEC, &count);
  if (ble_store_clear() == 0) {
    removed = count;
  }
#endif
  return removed;
}

void forgetCameraBinding(bool preserveCancel = false) {
  pendingHomeAction = PendingHomeAction::None;
  pendingHomeActionDueMs = 0;
  if (pairingInProgress) {
    requestPairingCancel();
  }
  disconnectCurrentCameraForPairing();
  boundBleAddress = "";
  goProSsid = "";
  goProPassword = "";
  lastBleName = "";
  clearSnapshotPreviewState("Pair New to connect camera");
  bool cleared = preferences.clear();
  int removed = clearBleBondStore();
  resetBleClientForPairing();
  if (!preserveCancel) {
    pairingLastCancelled = false;
    pairingCancelRequested = false;
    connectionCancelRequested = false;
    allowAnyCameraScan = false;
  }
  if (cameraLabel) {
    lv_label_set_text(cameraLabel, "Camera: not paired");
  }
  if (wifiLabel) {
    lv_label_set_text(wifiLabel, "WiFi: idle");
  }
  char label[72];
  snprintf(label, sizeof(label), "Forgot camera; NVS=%s BLE bonds=%d",
           cleared ? "cleared" : "clear failed", removed);
  setAction(label);
  Serial.println(label);
}

void requestPairingCancel() {
  consumeActionButtonPress();
  if (pendingHomeAction == PendingHomeAction::Pair) {
    pendingHomeAction = PendingHomeAction::None;
    pendingHomeActionDueMs = 0;
    hidePairingPopup();
    setAction("Pairing cancelled");
    Serial.println("Pending Pair New cancelled by lower button");
    return;
  }
  if (!pairingInProgress || pairingCancelRequested) {
    return;
  }
  pairingCancelRequested = true;
  setAction("Pairing cancel requested");
  hidePairingPopup();
  Serial.println("Pairing cancel requested by lower button");
}

void requestConnectionCancel(const char *message) {
  connectionCancelRequested = true;
  if (pairingInProgress) {
    pairingCancelRequested = true;
  }
  previewStreamRequested = false;
  if (previewUdpListening) {
    previewUdp.stop();
    previewUdpListening = false;
  }
  WiFi.scanDelete();
  WiFi.disconnect(false, false);
  if (bleClient != nullptr && bleClient->isConnected()) {
    bleClient->disconnect();
  }
  bleConnected = false;
  if (bleIndicator) {
    lv_obj_set_style_text_color(bleIndicator, lv_color_hex(0x5a6472), 0);
  }
  setAction(message == nullptr ? "Connection cancelled" : message);
}

void pollPairingCancelButton() {
  if (!pairingInProgress || pairingCancelRequested) {
    return;
  }

  if (expanderOnline &&
      expander.digitalRead(kExpanderActionButtonPin) == kExpanderActionPressedLevel) {
    requestPairingCancel();
  }
}

bool pairingCancelled() {
  if (!pairingCancelRequested) {
    return false;
  }
  setAction("Pairing cancelled");
  return true;
}

bool operationCancelled() {
  if (connectionCancelRequested) {
    return true;
  }
  return pairingCancelled();
}

void serviceConnectionUi() {
  if (pairingInProgress && !pairingCancelRequested && pairingPopup) {
    lv_obj_clear_flag(pairingPopup, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_foreground(pairingPopup);
  }
  lv_timer_handler();
  pollPairingCancelButton();
  handlePmuActionButton();
}

void servicePairingUi() {
  serviceConnectionUi();
}

bool delayWithConnectionUi(uint32_t durationMs) {
  uint32_t start = millis();
  while (millis() - start < durationMs) {
    serviceConnectionUi();
    if (operationCancelled()) {
      return false;
    }
    delay(25);
  }
  return true;
}

void resetBleClientForPairing() {
  if (bleClient != nullptr && bleClient->isConnected()) {
    bleClient->disconnect();
    delay(150);
  }
  bleClient = nullptr;
  bleConnected = false;
  if (bleIndicator) {
    lv_obj_set_style_text_color(bleIndicator, lv_color_hex(0x5a6472), 0);
  }
  delete bestBleDevice;
  bestBleDevice = nullptr;
}

void disconnectCurrentCameraForPairing() {
  setAction("Disconnecting current camera");
  previewStreamRequested = false;
  previewUdpListening = false;
  snapshotPreviewPrepared = false;
  previewUdp.stop();

  if (bleClient != nullptr && bleClient->isConnected()) {
    bleClient->disconnect();
    delay(150);
  }
  bleClient = nullptr;
  bleConnected = false;
  if (bleIndicator) {
    lv_obj_set_style_text_color(bleIndicator, lv_color_hex(0x5a6472), 0);
  }
  delete bestBleDevice;
  bestBleDevice = nullptr;

  if (WiFi.getMode() != WIFI_MODE_NULL || WiFi.status() == WL_CONNECTED) {
    WiFi.disconnect(true, true);
    WiFi.mode(WIFI_OFF);
    delay(250);
  }
  if (wifiLabel) {
    lv_label_set_text(wifiLabel, "WiFi: disconnected");
  }
  if (wifiIndicator) {
    lv_label_set_text(wifiIndicator, LV_SYMBOL_WIFI);
    lv_obj_set_style_text_color(wifiIndicator, lv_color_hex(0x5a6472), 0);
  }
}

String bytesToString(const String &bytes) {
  String value;
  value.reserve(bytes.length());
  for (size_t i = 0; i < bytes.length(); ++i) {
    char c = bytes.charAt(i);
    if (c != '\0') {
      value += c;
    }
  }
  return value;
}

String bytesToString(const std::string &bytes) {
  String value;
  value.reserve(bytes.length());
  for (char c : bytes) {
    if (c != '\0') {
      value += c;
    }
  }
  return value;
}

void applyCaptureLabels() {
  if (captureModeLabel) {
    lv_label_set_text(captureModeLabel, captureMode.c_str());
  }
  if (captureSettingLabel) {
    lv_label_set_text(captureSettingLabel, captureSetting.c_str());
  }
}

void storeSettingValue(uint16_t id, int option) {
  for (size_t i = 0; i < settingValueCount; ++i) {
    if (settingValues[i].id == id) {
      settingValues[i].option = option;
      return;
    }
  }
  if (settingValueCount < sizeof(settingValues) / sizeof(settingValues[0])) {
    settingValues[settingValueCount++] = {id, option};
  }
}

int getStoredSettingValue(uint16_t id) {
  for (size_t i = 0; i < settingValueCount; ++i) {
    if (settingValues[i].id == id) {
      return settingValues[i].option;
    }
  }
  return -1;
}

bool addSettingOption(int option, const char *displayName = nullptr) {
  for (size_t i = 0; i < settingOptionCount; ++i) {
    if (settingOptions[i] == option) {
      if (displayName && displayName[0] && settingOptionNames[i].isEmpty()) {
        settingOptionNames[i] = displayName;
      }
      return true;
    }
  }
  if (settingOptionCount >= kMaxSettingOptions) {
    return false;
  }
  settingOptions[settingOptionCount] = option;
  settingOptionNames[settingOptionCount] = displayName ? displayName : "";
  settingOptionCount++;
  return true;
}

void setDisplayOn(bool enabled) {
  displayOn = enabled;
  gfx->setBrightness(enabled ? kDisplayBrightness : 0);
  if (enabled) {
    lv_obj_clear_flag(lv_scr_act(), LV_OBJ_FLAG_HIDDEN);
    lv_label_set_text(statusLabel, recording ? "Recording" : "Display awake");
    setAction("Display on");
  } else {
    lv_label_set_text(statusLabel, "Display sleeping");
    setAction("Display off");
  }
}

void updateBatteryStatus(bool force = false) {
  if (!batteryLabel || (!force && millis() - lastBatteryUpdate < kBatteryRefreshMs)) {
    return;
  }
  lastBatteryUpdate = millis();

  if (!pmuOnline) {
    lv_label_set_text(batteryLabel, LV_SYMBOL_BATTERY_EMPTY);
    lv_obj_set_style_text_color(batteryLabel, lv_color_hex(0x5a6472), 0);
    return;
  }

  int percent = power.getBatteryPercent();
  if (percent < 0) {
    lv_label_set_text(batteryLabel, power.isVbusIn() ? LV_SYMBOL_USB : LV_SYMBOL_BATTERY_EMPTY);
    lv_obj_set_style_text_color(batteryLabel, lv_color_hex(0xc3ccd8), 0);
    return;
  }

  percent = constrain(percent, 0, 100);
  if (percent <= 15) {
    lv_obj_set_style_text_color(batteryLabel, lv_color_hex(0xf03e3e), 0);
  } else if (percent <= 35) {
    lv_obj_set_style_text_color(batteryLabel, lv_color_hex(0xf0b429), 0);
  } else {
    lv_obj_set_style_text_color(batteryLabel, lv_color_hex(0x47d16c), 0);
  }

  if (percent <= 15) {
    lv_label_set_text(batteryLabel, LV_SYMBOL_BATTERY_1);
  } else if (percent <= 35) {
    lv_label_set_text(batteryLabel, LV_SYMBOL_BATTERY_2);
  } else if (percent <= 70) {
    lv_label_set_text(batteryLabel, LV_SYMBOL_BATTERY_3);
  } else {
    lv_label_set_text(batteryLabel, LV_SYMBOL_BATTERY_FULL);
  }
}

void enterLowPowerShutdown() {
  recording = false;
  WiFi.disconnect(true, true);
  WiFi.mode(WIFI_OFF);

  if (statusLabel) {
    lv_label_set_text(statusLabel, "Powering off");
  }
  if (actionLabel) {
    lv_label_set_text(actionLabel, "Low-power shutdown");
  }
  lv_timer_handler();
  gfx->setBrightness(0);
  Serial.println("Entering low-power shutdown");
  delay(200);

  if (pmuOnline) {
    power.setPowerKeyPressOnTime(XPOWERS_POWERON_1S);
    power.setPowerKeyPressOffTime(XPOWERS_POWEROFF_4S);
    power.setLongPressPowerOFF();
    power.enableLongPressShutdown();
    power.shutdown();
  }

  esp_sleep_enable_ext0_wakeup(GPIO_NUM_0, 0);
  esp_deep_sleep_start();
}

String cameraBaseUrl() {
  return String("http://") + cameraIp.toString() + ":8080";
}

void commandResponseNotify(BLERemoteCharacteristic *, uint8_t *data, size_t length, bool) {
  Serial.print(F("BLE command response:"));
  for (size_t i = 0; i < length; ++i) {
    Serial.print(' ');
    if (data[i] < 0x10) {
      Serial.print('0');
    }
    Serial.print(data[i], HEX);
  }
  Serial.println();
  bleResponseStatus = length > 0 ? data[0] : 0x00;
  bleResponseSeen = true;
}

bool waitForBleResponse(uint32_t timeoutMs) {
  uint32_t start = millis();
  while (!bleResponseSeen && millis() - start < timeoutMs) {
    serviceConnectionUi();
    if (operationCancelled()) {
      return false;
    }
    delay(20);
  }
  if (!bleResponseSeen) {
    setAction("BLE command response timeout");
    return false;
  }
  return true;
}

class ScanCallbacks : public BLEAdvertisedDeviceCallbacks {
 public:
  void onResult(BLEAdvertisedDevice device) override {
    String name = device.haveName() ? String(device.getName().c_str()) : "";
    bool hasControlService = device.haveServiceUUID() && device.isAdvertisingService(kControlService);
    String address = device.getAddress().toString().c_str();
    address.toLowerCase();

    if (!hasControlService && !nameMatchesFilter(name)) {
      return;
    }
    if (!boundBleAddress.isEmpty() && !allowAnyCameraScan && address != boundBleAddress) {
      Serial.print(F("Skipping unbound GoPro BLE addr="));
      Serial.println(address);
      return;
    }

    Serial.print(F("BLE candidate: "));
    Serial.print(name.isEmpty() ? F("(no name)") : name);
    Serial.print(F(" rssi="));
    Serial.print(device.getRSSI());
    Serial.print(F(" addr="));
    Serial.println(device.getAddress().toString().c_str());

    if (bestBleDevice == nullptr || device.getRSSI() > bestBleDevice->getRSSI()) {
      delete bestBleDevice;
      bestBleDevice = new BLEAdvertisedDevice(device);
    }
  }
};

bool scanForCamera() {
  if (boundBleAddress.isEmpty() && !allowAnyCameraScan) {
    lv_label_set_text(cameraLabel, "Camera: not paired");
    setAction("No saved camera; tap Pair New");
    Serial.println("BLE scan blocked: no saved camera binding");
    return false;
  }

  initBleStack();
  delete bestBleDevice;
  bestBleDevice = nullptr;

  lv_label_set_text(statusLabel, "Scanning BLE");
  setAction(boundBleAddress.isEmpty() || allowAnyCameraScan
                ? "Scanning for GoPro BLE"
                : "Scanning for bound GoPro");
  lv_timer_handler();

  BLEScan *scan = BLEDevice::getScan();
  ScanCallbacks callbacks;
  scan->setAdvertisedDeviceCallbacks(&callbacks, false);
  scan->setActiveScan(true);
  scan->setInterval(100);
  scan->setWindow(99);
  for (uint32_t elapsed = 0; elapsed < kBleScanSeconds; ++elapsed) {
    if (operationCancelled()) {
      scan->clearResults();
      return false;
    }
    scan->start(1, false);
    serviceConnectionUi();
    if (operationCancelled()) {
      scan->clearResults();
      return false;
    }
  }
  scan->clearResults();

  if (bestBleDevice == nullptr) {
    lv_label_set_text(cameraLabel, "Camera: BLE not found");
    setAction(boundBleAddress.isEmpty() || allowAnyCameraScan
                  ? "No GoPro BLE device found"
                  : "Bound GoPro BLE not found");
    return false;
  }

  lastBleName = bestBleDevice->haveName() ? String(bestBleDevice->getName().c_str()) : "";
  String label = "Camera: ";
  label += lastBleName.isEmpty() ? bestBleDevice->getAddress().toString().c_str() : lastBleName;
  lv_label_set_text(cameraLabel, label.c_str());
  Serial.print(F("Selected BLE device: "));
  Serial.println(label);
  return true;
}

bool connectBle() {
  initBleStack();
  if (operationCancelled()) {
    return false;
  }
  if (bleConnected && bleClient != nullptr && bleClient->isConnected()) {
    return true;
  }

  if (bestBleDevice == nullptr && !scanForCamera()) {
    return false;
  }
  if (operationCancelled()) {
    return false;
  }

  if (bleClient == nullptr) {
    bleClient = BLEDevice::createClient();
  }

  lv_label_set_text(statusLabel, "Connecting BLE");
  setAction("Connecting GoPro BLE");
  serviceConnectionUi();
  logMemory("Before BLE connect");
  uint32_t connectTimeoutMs = pairingInProgress ? kPairBleConnectTimeoutMs : kBleConnectTimeoutMs;
  if (!bleClient->connectTimeout(bestBleDevice, connectTimeoutMs)) {
    bleConnected = false;
    if (bleIndicator) {
      lv_obj_set_style_text_color(bleIndicator, lv_color_hex(0x5a6472), 0);
    }
    delete bleClient;
    bleClient = nullptr;
    lv_label_set_text(cameraLabel, "Camera: BLE connect failed");
    setAction("BLE connect failed");
    return false;
  }
  if (operationCancelled()) {
    if (bleClient != nullptr && bleClient->isConnected()) {
      bleClient->disconnect();
    }
    bleConnected = false;
    setAction("Pairing cancelled");
    return false;
  }

  bleConnected = true;
  if (bleIndicator) {
    lv_obj_set_style_text_color(bleIndicator, lv_color_hex(0x2c7be5), 0);
  }
  logMemory("After BLE connect");
  BLERemoteService *control = bleClient->getService(kControlService);
  if (control != nullptr) {
    BLERemoteCharacteristic *response = control->getCharacteristic(kCommandResponse);
    if (response != nullptr && response->canNotify()) {
      response->registerForNotify(commandResponseNotify);
    }
    BLERemoteCharacteristic *settingsResponse = control->getCharacteristic(kSettingsResponse);
    if (settingsResponse != nullptr && settingsResponse->canNotify()) {
      settingsResponse->registerForNotify(commandResponseNotify);
    }
  }

  lv_label_set_text(statusLabel, "BLE connected");
  setAction("BLE connected");
  lv_timer_handler();
  return true;
}

bool readGoProWifiCredentials() {
  if (!connectBle()) {
    return false;
  }
  if (operationCancelled()) {
    return false;
  }

  BLERemoteService *wifi = bleClient->getService(kWifiService);
  if (wifi == nullptr) {
    setAction("GoPro WiFi BLE service missing");
    return false;
  }

  BLERemoteCharacteristic *ssid = wifi->getCharacteristic(kWifiSsid);
  BLERemoteCharacteristic *password = wifi->getCharacteristic(kWifiPassword);
  if (ssid == nullptr || password == nullptr || !ssid->canRead() || !password->canRead()) {
    setAction("GoPro WiFi credentials unreadable");
    return false;
  }

  goProSsid = bytesToString(ssid->readValue());
  goProPassword = bytesToString(password->readValue());
  if (operationCancelled()) {
    return false;
  }

  Serial.print(F("GoPro AP SSID: "));
  Serial.println(goProSsid);
  Serial.print(F("GoPro AP password length: "));
  Serial.println(goProPassword.length());
#if GOPRO_DEBUG_PRINT_CAMERA_PASSWORD
  Serial.print(F("GoPro AP password: "));
  Serial.println(goProPassword);
#endif
  if (goProSsid.isEmpty() || goProPassword.isEmpty()) {
    setAction("GoPro WiFi credentials empty");
    return false;
  }
  if (!deferBleBindingSave && boundBleAddress.isEmpty() && bestBleDevice != nullptr) {
    saveCameraBinding(*bestBleDevice);
  }

  String label = "Camera AP: ";
  label += goProSsid;
  lv_label_set_text(cameraLabel, label.c_str());
  setAction("Read GoPro WiFi over BLE");
  return true;
}

bool sendBleCommand(const uint8_t *payload, size_t length) {
  if (!connectBle()) {
    return false;
  }

  BLERemoteService *control = bleClient->getService(kControlService);
  if (control == nullptr) {
    setAction("GoPro control BLE service missing");
    return false;
  }

  BLERemoteCharacteristic *command = control->getCharacteristic(kCommand);
  if (command == nullptr || !command->canWrite()) {
    setAction("GoPro command characteristic missing");
    return false;
  }

  bleResponseSeen = false;
  bleResponseStatus = 0xFF;
  command->writeValue(const_cast<uint8_t *>(payload), length, true);
  return waitForBleResponse(2500);
}

bool sendBleSetting(uint8_t settingId, uint8_t optionId, const char *label) {
  if (!connectBle()) {
    return false;
  }

  BLERemoteService *control = bleClient->getService(kControlService);
  if (control == nullptr) {
    setAction("GoPro control BLE service missing");
    return false;
  }

  BLERemoteCharacteristic *response = control->getCharacteristic(kSettingsResponse);
  if (response != nullptr && response->canNotify()) {
    response->registerForNotify(commandResponseNotify);
  }

  BLERemoteCharacteristic *settings = control->getCharacteristic(kSettings);
  if (settings == nullptr || !settings->canWrite()) {
    setAction("GoPro settings characteristic missing");
    return false;
  }

  uint8_t payload[] = {0x03, settingId, 0x01, optionId};
  bleResponseSeen = false;
  bleResponseStatus = 0xFF;
  settings->writeValue(payload, sizeof(payload), true);
  bool ok = waitForBleResponse(2500);
  setAction(ok ? label : "BLE setting response timeout");
  return ok;
}

bool forceGoProWifi24GHz() {
  for (uint8_t attempt = 1; attempt <= 2; ++attempt) {
    if (operationCancelled()) {
      return false;
    }
    lv_label_set_text(statusLabel, "Setting WiFi 2.4GHz");
    setAction(attempt == 1 ? "Forcing GoPro WiFi to 2.4GHz"
                           : "Retrying GoPro WiFi 2.4GHz");
    if (sendBleSetting(kGoProWirelessBandSetting, kGoProWirelessBand24GHz,
                       "GoPro WiFi band: 2.4GHz")) {
      delayWithConnectionUi(500);
      return true;
    }
    if (operationCancelled()) {
      return false;
    }
    delayWithConnectionUi(500);
  }
  setAction("GoPro WiFi band set failed");
  return false;
}

bool sendCameraManagementCommand(const uint8_t *payload, size_t length) {
  if (!connectBle()) {
    return false;
  }
  if (operationCancelled()) {
    return false;
  }

  BLERemoteService *management = bleClient->getService(kCameraManagementService);
  if (management == nullptr) {
    setAction("GoPro pairing service missing");
    return false;
  }

  BLERemoteCharacteristic *response = management->getCharacteristic(kCameraManagementResponse);
  if (response != nullptr && response->canNotify()) {
    response->registerForNotify(commandResponseNotify);
  }

  BLERemoteCharacteristic *command = management->getCharacteristic(kCameraManagementCommand);
  if (command == nullptr || !command->canWrite()) {
    setAction("GoPro pairing command missing");
    return false;
  }

  bleResponseSeen = false;
  bleResponseStatus = 0xFF;
  command->writeValue(const_cast<uint8_t *>(payload), length, true);
  return waitForBleResponse(4000);
}

bool pairGoPro() {
  bool previousAllowAny = allowAnyCameraScan;
  bool previousDeferSave = deferBleBindingSave;
  String previousBoundBleAddress = boundBleAddress;
  String previousSsid = goProSsid;
  String previousPassword = goProPassword;
  allowAnyCameraScan = true;
  pairingInProgress = true;
  pairingCancelRequested = false;
  pairingLastCancelled = false;
  deferBleBindingSave = true;
  showPairingPopup("Pairing New Camera\n\nDisconnecting current camera...");
  disconnectCurrentCameraForPairing();
  resetBleClientForPairing();

  const char controllerName[] = "ESP32";
  uint8_t request[1 + 2 + 2 + 2 + sizeof(controllerName) - 1] = {
      0x0B,
      0x03,
      0x01,
      0x08,
      0x00,
      0x12,
      static_cast<uint8_t>(sizeof(controllerName) - 1),
      'E',
      'S',
      'P',
      '3',
      '2',
  };
  lv_label_set_text(statusLabel, "Pairing BLE");
  lv_label_set_text(cameraLabel, "Camera: use GoPro pairing mode");
  showPairingPopup("Pairing New Camera\n\nPut the GoPro in pairing mode.\nPress lower button to cancel.");
  setAction("Pairing with GoPro BLE");
  lv_timer_handler();

  bool ok = false;
  if (readGoProWifiCredentials() && !operationCancelled()) {
    setAction("Finishing GoPro pairing");
    ok = sendCameraManagementCommand(request, sizeof(request));
    if (ok && !operationCancelled() && bestBleDevice != nullptr) {
      saveCameraBinding(*bestBleDevice);
    }
  } else if (!operationCancelled()) {
    setAction("BLE security pairing failed");
  }

  if (operationCancelled()) {
    ok = false;
    setAction(connectionCancelRequested ? "Connection cancelled" : "Pairing cancelled");
  }
  if (!ok) {
    if (!connectionCancelRequested) {
      boundBleAddress = previousBoundBleAddress;
      goProSsid = previousSsid;
      goProPassword = previousPassword;
    }
    resetBleClientForPairing();
    if (operationCancelled()) {
      hidePairingPopup();
    } else {
      finishPairingPopup("Pairing Failed\n\nSaved camera is unchanged.");
    }
  } else {
    finishPairingPopup("Pairing Complete\n\nSaved new camera.");
  }
  allowAnyCameraScan = previousAllowAny;
  pairingInProgress = false;
  pairingLastCancelled = pairingCancelRequested || connectionCancelRequested;
  pairingCancelRequested = false;
  deferBleBindingSave = previousDeferSave;
  return ok;
}

bool enableGoProWifiAp() {
  const uint8_t enableWifi[] = {0x03, 0x17, 0x01, 0x01};
  if (!forceGoProWifi24GHz()) {
    if (operationCancelled()) {
      return false;
    }
    setAction("2.4GHz not confirmed; trying AP");
    if (!delayWithConnectionUi(500)) {
      return false;
    }
  }
  if (operationCancelled()) {
    return false;
  }
  lv_label_set_text(statusLabel, "Enabling GoPro AP");
  setAction("Enabling GoPro WiFi AP over BLE");
  return sendBleCommand(enableWifi, sizeof(enableWifi));
}

bool waitForGoProApVisible() {
  if (goProSsid.isEmpty()) {
    return false;
  }
  WiFi.disconnect(false, false);
  WiFi.scanDelete();
  if (!delayWithConnectionUi(500)) {
    return false;
  }
  lv_label_set_text(statusLabel, "Waiting for camera AP");
  setAction("Waiting for GoPro WiFi AP");
  uint32_t start = millis();
  while (millis() - start < kWifiTimeoutMs) {
    if (operationCancelled()) {
      return false;
    }
    int count = WiFi.scanNetworks(false, true);
    if (operationCancelled()) {
      WiFi.scanDelete();
      return false;
    }
    bool found = false;
    Serial.printf("WiFi scan found %d networks\n", count);
    for (int i = 0; i < count; ++i) {
      Serial.printf("  ssid='%s' rssi=%d channel=%d\n", WiFi.SSID(i).c_str(),
                    WiFi.RSSI(i), WiFi.channel(i));
      if (WiFi.SSID(i) == goProSsid) {
        found = true;
      }
    }
    WiFi.scanDelete();
    if (found) {
      return true;
    }
    if (!delayWithConnectionUi(1000)) {
      return false;
    }
  }
  setAction("GoPro WiFi AP not visible");
  return false;
}

bool tryJoinGoProWifi(uint32_t timeoutMs) {
  WiFi.disconnect(false, false);
  if (!delayWithConnectionUi(500)) {
    return false;
  }
  logMemory("Before WiFi begin");
  WiFi.begin(goProSsid.c_str(), goProPassword.c_str());

  uint32_t start = millis();
  uint8_t lastStatus = 0xFF;
  while (millis() - start < timeoutMs) {
    serviceConnectionUi();
    if (operationCancelled()) {
      return false;
    }
    uint8_t status = WiFi.status();
    if (status != lastStatus) {
      lastStatus = status;
      Serial.printf("WiFi status=%u\n", status);
    }
    if (status == WL_CONNECTED) {
      return true;
    }
    delay(250);
  }
  Serial.printf("WiFi join timed out status=%u\n", WiFi.status());
  return false;
}

bool isLikelyGoProWifiConnected() {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }
  if (!goProSsid.isEmpty() && WiFi.SSID() == goProSsid) {
    return true;
  }
  IPAddress ip = WiFi.localIP();
  return ip[0] == 10 && ip[1] == 5 && ip[2] == 5;
}

void markExistingGoProWifiConnected() {
  if (wifiLabel) {
    String text = "WiFi: ";
    text += WiFi.localIP().toString();
    lv_label_set_text(wifiLabel, text.c_str());
  }
  if (statusLabel) {
    lv_label_set_text(statusLabel, "GoPro WiFi connected");
  }
  if (wifiIndicator) {
    lv_label_set_text(wifiIndicator, LV_SYMBOL_WIFI);
    lv_obj_set_style_text_color(wifiIndicator, lv_color_hex(0x47d16c), 0);
  }
}

bool connectGoProWifiFromBle() {
  if (operationCancelled()) {
    return false;
  }
  if (isLikelyGoProWifiConnected()) {
    markExistingGoProWifiConnected();
    setAction("Using existing GoPro WiFi");
    return true;
  }
  if (boundBleAddress.isEmpty() && !allowAnyCameraScan) {
    if (cameraLabel) {
      lv_label_set_text(cameraLabel, "Camera: not paired");
    }
    if (wifiLabel) {
      lv_label_set_text(wifiLabel, "WiFi: idle");
    }
    setAction("No saved camera; tap Pair New");
    Serial.println("GoPro WiFi connect blocked: no saved camera binding");
    return false;
  }
  if (goProSsid.isEmpty() && !readGoProWifiCredentials()) {
    return false;
  }
  if (operationCancelled()) {
    return false;
  }
  if (!enableGoProWifiAp()) {
    return false;
  }
  if (operationCancelled()) {
    return false;
  }

  shutdownBleForWifi();
  WiFi.useStaticBuffers(false);
  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true, true);
  if (!delayWithConnectionUi(3000)) {
    return false;
  }

  if (!waitForGoProApVisible()) {
    lv_label_set_text(wifiLabel, "WiFi: GoPro AP not visible");
    return false;
  }

  String label = "Joining ";
  label += goProSsid;
  lv_label_set_text(statusLabel, label.c_str());
  setAction(label.c_str());

  if (!tryJoinGoProWifi(15000) && !operationCancelled() && !tryJoinGoProWifi(15000)) {
    lv_label_set_text(wifiLabel, "WiFi: GoPro AP failed");
    setAction("Direct GoPro WiFi join failed");
    waitForGoProApVisible();
    return false;
  }
  if (operationCancelled()) {
    return false;
  }

  String text = "WiFi: ";
  text += WiFi.localIP().toString();
  lv_label_set_text(wifiLabel, text.c_str());
  lv_label_set_text(statusLabel, "GoPro WiFi connected");
  setAction("Connected to GoPro WiFi");
  syncCameraState();
  lastPreviewUpdate = 0;
  if (previewLabel && !previewHasImage) {
    lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    lv_label_set_text(previewLabel, "Double-click lower for snapshot");
  }
  return true;
}

bool httpGetGoPro(const String &path) {
  if (WiFi.status() != WL_CONNECTED) {
    setAction("WiFi not connected");
    return false;
  }

  HTTPClient http;
  http.setTimeout(kHttpTimeoutMs);
  String url = cameraBaseUrl() + path;
  if (!http.begin(url)) {
    setAction("HTTP begin failed");
    return false;
  }
  int status = http.GET();
  http.end();
  Serial.printf("GET %s -> %d\n", url.c_str(), status);
  return status >= 200 && status < 300;
}

int httpGetGoProStatus(const String &path) {
  if (WiFi.status() != WL_CONNECTED) {
    setAction("WiFi not connected");
    return -1;
  }

  HTTPClient http;
  http.setTimeout(kHttpTimeoutMs);
  String url = cameraBaseUrl() + path;
  if (!http.begin(url)) {
    setAction("HTTP begin failed");
    return -1;
  }
  int status = http.GET();
  http.end();
  Serial.printf("GET %s -> %d\n", url.c_str(), status);
  return status;
}

int httpGetGoProBody(const String &path, String &body) {
  body = "";
  if (WiFi.status() != WL_CONNECTED) {
    setAction("WiFi not connected");
    return -1;
  }

  HTTPClient http;
  http.setTimeout(kHttpTimeoutMs);
  String url = cameraBaseUrl() + path;
  if (!http.begin(url)) {
    setAction("HTTP begin failed");
    return -1;
  }
  int status = http.GET();
  body = http.getString();
  http.end();
  Serial.printf("GET %s -> %d, %u bytes\n", url.c_str(), status, body.length());
  return status;
}

String urlEncodePathParam(const String &value) {
  const char *hex = "0123456789ABCDEF";
  String encoded;
  encoded.reserve(value.length() + 8);
  for (size_t i = 0; i < value.length(); ++i) {
    uint8_t c = static_cast<uint8_t>(value[i]);
    bool safe = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
                (c >= '0' && c <= '9') || c == '/' || c == '.' ||
                c == '-' || c == '_' || c == '~';
    if (safe) {
      encoded += static_cast<char>(c);
    } else {
      encoded += '%';
      encoded += hex[c >> 4];
      encoded += hex[c & 0x0f];
    }
  }
  return encoded;
}

bool httpGetGoProBinary(const String &path, uint8_t *buffer, size_t capacity, size_t &length) {
  length = 0;
  if (WiFi.status() != WL_CONNECTED) {
    setAction("WiFi not connected");
    return false;
  }

  HTTPClient http;
  http.setTimeout(kHttpTimeoutMs);
  String url = cameraBaseUrl() + path;
  if (!http.begin(url)) {
    setAction("HTTP begin failed");
    return false;
  }

  int status = http.GET();
  Serial.printf("GET %s -> %d\n", url.c_str(), status);
  if (status < 200 || status >= 300) {
    http.end();
    return false;
  }

  WiFiClient *stream = http.getStreamPtr();
  int remaining = http.getSize();
  uint32_t start = millis();
  while (http.connected() && (remaining > 0 || remaining == -1)) {
    size_t available = stream->available();
    if (available == 0) {
      if (remaining == 0 || millis() - start > kHttpTimeoutMs) {
        break;
      }
      delay(5);
      continue;
    }

    size_t toRead = min(available, capacity - length);
    if (toRead == 0) {
      http.end();
      setAction("JPEG buffer full");
      return false;
    }
    int readLen = stream->readBytes(buffer + length, toRead);
    if (readLen <= 0) {
      break;
    }
    length += static_cast<size_t>(readLen);
    if (remaining > 0) {
      remaining -= readLen;
    }
    start = millis();
  }

  http.end();
  Serial.printf("Binary %s -> %u bytes\n", path.c_str(), length);
  return length > 0;
}

bool parseLatestJpegPath(const String &mediaList, String &path) {
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, mediaList);
  if (error) {
    Serial.print(F("media/list JSON parse failed: "));
    Serial.println(error.c_str());
    return false;
  }

  uint32_t bestCreated = 0;
  uint32_t bestModified = 0;
  String bestPath;
  JsonArray media = doc["media"].as<JsonArray>();
  for (JsonObject directory : media) {
    const char *folder = directory["d"] | "";
    JsonArray files = directory["fs"].as<JsonArray>();
    for (JsonObject file : files) {
      const char *name = file["n"] | "";
      String fileName(name);
      fileName.toUpperCase();
      if (!fileName.endsWith(".JPG")) {
        continue;
      }
      uint32_t created = strtoul(file["cre"] | "0", nullptr, 10);
      uint32_t modified = strtoul(file["mod"] | "0", nullptr, 10);
      String candidate = String(folder) + "/" + name;
      if (bestPath.isEmpty() || created > bestCreated ||
          (created == bestCreated && modified > bestModified) ||
          (created == bestCreated && modified == bestModified && candidate > bestPath)) {
        bestPath = candidate;
        bestCreated = created;
        bestModified = modified;
      }
    }
  }

  path = bestPath;
  return !path.isEmpty();
}

bool fetchLatestJpegPath(String &path) {
  String body;
  int status = httpGetGoProBody("/gopro/media/list", body);
  if (status < 200 || status >= 300) {
    return false;
  }
  return parseLatestJpegPath(body, path);
}

bool deleteGoProMedia(const String &path) {
  if (path.isEmpty()) {
    return false;
  }
  String endpoint = "/gopro/media/delete/file?path=" + urlEncodePathParam(path);
  return httpGetGoPro(endpoint);
}

bool setGoProSetting(uint16_t settingId, uint16_t optionId, const char *label) {
  String path = "/gopro/camera/setting?setting=";
  path += settingId;
  path += "&option=";
  path += optionId;
  bool ok = httpGetGoPro(path);
  if (ok) {
    storeSettingValue(settingId, optionId);
    refreshCaptureOverlayFromState();
  }
  setAction(ok ? label : "Setting command failed");
  return ok;
}

const char *optionObjectName(JsonObject object) {
  const char *name = object["display_name"] | object["displayName"] | object["name"] | nullptr;
  return name;
}

void collectSettingOptions(JsonVariant value) {
  if (value.is<JsonArray>()) {
    bool numericArray = false;
    for (JsonVariant item : value.as<JsonArray>()) {
      if (item.is<int>()) {
        numericArray = true;
        addSettingOption(item.as<int>());
      }
    }
    if (numericArray) {
      return;
    }
  }

  if (value.is<JsonObject>()) {
    JsonObject object = value.as<JsonObject>();
    if (object["id"].is<int>()) {
      addSettingOption(object["id"].as<int>(), optionObjectName(object));
    } else if (object["option"].is<int>()) {
      addSettingOption(object["option"].as<int>(), optionObjectName(object));
    } else if (object["value"].is<int>() &&
               (object["display_name"].is<const char *>() || object["name"].is<const char *>())) {
      addSettingOption(object["value"].as<int>(), optionObjectName(object));
    }
    for (JsonPair pair : object) {
      collectSettingOptions(pair.value());
    }
  } else if (value.is<JsonArray>()) {
    for (JsonVariant item : value.as<JsonArray>()) {
      collectSettingOptions(item);
    }
  }
}

bool parseCameraState(const String &body) {
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, body);
  if (error) {
    setAction("Camera state JSON parse failed");
    return false;
  }

  JsonObject settings = doc["settings"].as<JsonObject>();
  if (settings.isNull()) {
    settings = doc["setting"].as<JsonObject>();
  }
  if (settings.isNull()) {
    setAction("Camera state has no settings object");
    return false;
  }

  for (JsonPair pair : settings) {
    const char *key = pair.key().c_str();
    if (!key) {
      continue;
    }
    int id = atoi(key);
    if (id <= 0) {
      continue;
    }
    if (pair.value().is<int>()) {
      storeSettingValue(id, pair.value().as<int>());
    } else if (pair.value()["option"].is<int>()) {
      storeSettingValue(id, pair.value()["option"].as<int>());
    }
  }
  refreshCaptureOverlayFromState();
  setAction("Camera state synced");
  return true;
}

bool syncCameraState() {
  String body;
  int status = httpGetGoProBody("/gopro/camera/state", body);
  if (status != 200) {
    setAction("Camera state sync failed");
    return false;
  }
  return parseCameraState(body);
}

bool syncCameraPresets() {
  String body;
  int status = httpGetGoProBody("/gopro/camera/presets/get?include-hidden=1", body);
  if (status != 200) {
    setAction("Preset sync failed");
    return false;
  }
  JsonDocument doc;
  if (deserializeJson(doc, body)) {
    setAction("Preset JSON parse failed");
    return false;
  }
  setAction("Presets synced");
  return true;
}

const char *knownOptionName(uint16_t settingId, int option) {
  switch (settingId) {
    case 108:
    case 192:
    case 193:
    case 232:
    case 233:
      switch (option) {
        case 0: return "4:3";
        case 1: return "16:9";
        case 3: return "8:7";
        case 4: return "9:16";
        case 5: return "1:1";
        case 6: return "21:9";
      }
      break;
    case 2:
      switch (option) {
        case 1: return "4K";
        case 4: return "2.7K";
        case 6: return "1080";
        case 7: return "720";
        case 9: return "5.3K";
        case 24: return "5K";
        case 25: return "4K 4:3";
        case 26: return "5.3K 8:7";
        case 27: return "4K 8:7";
      }
      break;
    case 3:
    case 234:
      switch (option) {
        case 0: return "240";
        case 1: return "120";
        case 2: return "100";
        case 5: return "60";
        case 6: return "50";
        case 8: return "30";
        case 9: return "25";
        case 10: return "24";
        case 13: return "200";
        case 15: return "400";
      }
      break;
    case 121:
    case 122:
    case 123:
      switch (option) {
        case 19: return "Wide";
        case 30: return "Linear";
        case 31: return "Superview";
        case 32: return "Linear+HL";
        case 100: return "HyperView";
        case 101: return "Wide";
        case 102: return "Linear";
      }
      break;
    case 135:
    case 167:
    case 168:
    case 173:
    case 175:
    case 177:
    case 180:
    case 183:
    case 186:
    case 187:
    case 190:
    case 194:
    case 236:
      switch (option) {
        case 0: return "Off";
        case 1: return "On";
        case 2: return "Auto";
      }
      break;
    case 182:
      switch (option) {
        case 0: return "Standard";
        case 1: return "High";
      }
      break;
    case 216:
      switch (option) {
        case 70: return "Low";
        case 85: return "Medium";
        case 100: return "High";
      }
      break;
    case 178:
      switch (option) {
        case 0: return "2.4 GHz";
        case 1: return "5 GHz";
      }
      break;
  }
  return nullptr;
}

String storedOptionDisplay(uint16_t settingId, bool *found = nullptr) {
  int option = getStoredSettingValue(settingId);
  if (option < 0) {
    if (found) {
      *found = false;
    }
    return "";
  }

  if (found) {
    *found = true;
  }
  const char *known = knownOptionName(settingId, option);
  if (known) {
    return known;
  }
  String label = "Opt ";
  label += option;
  return label;
}

String firstStoredOptionDisplay(const uint16_t *settingIds, size_t count, bool *found = nullptr) {
  for (size_t i = 0; i < count; ++i) {
    bool optionFound = false;
    String value = storedOptionDisplay(settingIds[i], &optionFound);
    if (optionFound) {
      if (found) {
        *found = true;
      }
      return value;
    }
  }
  if (found) {
    *found = false;
  }
  return "";
}

void appendCaptureSettingPart(String &text, const String &part) {
  if (part.isEmpty()) {
    return;
  }
  if (!text.isEmpty()) {
    text += " | ";
  }
  text += part;
}

void refreshCaptureOverlayFromState() {
  const uint16_t aspectIds[] = {108, 192, 193, 232, 233};
  const uint16_t fpsIds[] = {234, 3};
  const uint16_t lensIds[] = {121, 122, 123};

  String setting;
  appendCaptureSettingPart(setting, firstStoredOptionDisplay(aspectIds, sizeof(aspectIds) / sizeof(aspectIds[0])));
  appendCaptureSettingPart(setting, storedOptionDisplay(2));
  appendCaptureSettingPart(setting, firstStoredOptionDisplay(fpsIds, sizeof(fpsIds) / sizeof(fpsIds[0])));
  appendCaptureSettingPart(setting, firstStoredOptionDisplay(lensIds, sizeof(lensIds) / sizeof(lensIds[0])));

  if (!setting.isEmpty()) {
    captureSetting = setting;
    applyCaptureLabels();
    Serial.print(F("Capture overlay: "));
    Serial.println(captureSetting);
  }
}

String optionDisplayName(uint16_t settingId, int option) {
  const char *known = knownOptionName(settingId, option);
  if (known) {
    return String(known) + " (" + option + ")";
  }
  return String("Option ") + option;
}

String activeOptionDisplayName(uint16_t settingId, int option) {
  for (size_t i = 0; i < settingOptionCount; ++i) {
    if (settingOptions[i] == option && !settingOptionNames[i].isEmpty()) {
      return settingOptionNames[i] + " (" + option + ")";
    }
  }
  return optionDisplayName(settingId, option);
}

void addFallbackOptions(uint16_t settingId) {
  switch (settingId) {
    case 108:
    case 192:
    case 193:
    case 232:
    case 233: {
      const int values[] = {0, 1, 3, 4, 5, 6};
      for (int value : values) addSettingOption(value);
      break;
    }
    case 2: {
      const int values[] = {1, 4, 6, 7, 9, 24, 25, 26, 27};
      for (int value : values) addSettingOption(value);
      break;
    }
    case 3:
    case 234: {
      const int values[] = {0, 1, 2, 5, 6, 8, 9, 10, 13, 15};
      for (int value : values) addSettingOption(value);
      break;
    }
    case 121:
    case 122:
    case 123: {
      const int values[] = {19, 30, 31, 32, 100, 101, 102};
      for (int value : values) addSettingOption(value);
      break;
    }
    case 182:
    case 183:
    case 178: {
      const int values[] = {0, 1, 2};
      for (int value : values) addSettingOption(value);
      break;
    }
    case 216: {
      const int values[] = {70, 85, 100};
      for (int value : values) addSettingOption(value);
      break;
    }
    default: {
      const int values[] = {0, 1, 2, 3, 4, 5};
      for (int value : values) addSettingOption(value);
      break;
    }
  }
}

bool querySettingOptions(const SettingDefinition &setting) {
  settingOptionCount = 0;
  settingOptionOffset = 0;
  for (size_t i = 0; i < kMaxSettingOptions; ++i) {
    settingOptionNames[i] = "";
  }
  bool gotCameraOptionResponse = false;
  bool gotLegalOptions = false;

  String body;
  String path = "/gopro/camera/setting?setting=";
  path += setting.id;
  int status = httpGetGoProBody(path, body);
  if (status == 200) {
    JsonDocument doc;
    if (!deserializeJson(doc, body) && doc["option"].is<int>()) {
      int current = doc["option"].as<int>();
      storeSettingValue(setting.id, current);
      addSettingOption(current);
    }
  }

  path = "/gopro/camera/setting?setting=";
  path += setting.id;
  path += "&option=65535";
  body = "";
  status = httpGetGoProBody(path, body);
  if (status == 403 || status == 400) {
    gotCameraOptionResponse = true;
    size_t beforeOptions = settingOptionCount;
    JsonDocument doc;
    if (!deserializeJson(doc, body)) {
      collectSettingOptions(doc.as<JsonVariant>());
      gotLegalOptions = settingOptionCount > beforeOptions;
    } else {
      setAction("Option response JSON parse failed");
    }
  } else if (status < 0) {
    return false;
  }

  if (gotCameraOptionResponse && !gotLegalOptions) {
    addFallbackOptions(setting.id);
  }
  return settingOptionCount > 0;
}

void setPairingMode() {
  if (!displayOn) {
    setDisplayOn(true);
  }
  bool ok = pairGoPro();
  setAction(ok ? "GoPro BLE pairing requested"
               : (pairingLastCancelled ? "Pairing cancelled" : "GoPro BLE pairing failed"));
  if (ok) {
    delay(300);
    setAction("Pair complete; connecting WiFi");
    connectGoProWifiFromBle();
  } else if (pairingLastCancelled && !connectionCancelRequested) {
    delay(300);
    setAction("Pairing cancelled; reconnecting saved camera");
    connectGoProWifiFromBle();
  }
}

bool beginGoproAction(const char *name) {
  if (goproActionBusy) {
    setAction("GoPro action already running");
    return false;
  }
  goproActionBusy = true;
  connectionCancelRequested = false;
  pendingHomeAction = PendingHomeAction::None;
  pendingHomeActionDueMs = 0;
  Serial.print(F("Action start: "));
  Serial.println(name);
  return true;
}

void endGoproAction() {
  goproActionBusy = false;
}

void runConnectAction() {
  if (!beginGoproAction("connect")) {
    return;
  }
  setAction("Connect pressed");
  lv_timer_handler();
  delay(100);
  connectGoProWifiFromBle();
  endGoproAction();
}

void runPairNewAction() {
  if (!beginGoproAction("pair-new")) {
    return;
  }
  setAction("Pair New");
  lv_timer_handler();
  delay(100);
  setPairingMode();
  endGoproAction();
}

void runForgetCameraAction() {
  if (recording) {
    setAction("Stop recording before forgetting");
    return;
  }
  if (!beginGoproAction("forget-camera")) {
    return;
  }
  setAction("Forgetting saved camera");
  lv_timer_handler();
  delay(100);
  forgetCameraBinding();
  endGoproAction();
}

void runRecordAction() {
  if (!beginGoproAction("record")) {
    return;
  }
  setAction("REC pressed");
  lv_timer_handler();
  delay(100);
  toggleRecording();
  endGoproAction();
}

void runSnapshotAction() {
  if (!beginGoproAction("snapshot")) {
    return;
  }
  if (!displayOn) {
    setDisplayOn(true);
  }
  if (recording) {
    setAction("Snapshot disabled while recording");
    endGoproAction();
    return;
  }
  if (isLikelyGoProWifiConnected()) {
    markExistingGoProWifiConnected();
    setAction("Taking snapshot over GoPro WiFi");
  } else {
    setAction("Connecting for snapshot");
    if (!connectGoProWifiFromBle()) {
      setAction("Camera WiFi not connected");
      endGoproAction();
      return;
    }
  }
  fetchSnapshotPreview();
  endGoproAction();
}

void toggleRecording() {
  if (!displayOn) {
    setDisplayOn(true);
  }
  bool nextRecording = !recording;
  lv_label_set_text(statusLabel, nextRecording ? "Starting recording" : "Stopping recording");
  bool ok = false;
  if (nextRecording) {
    if (previewFullscreen) {
      setPreviewFullscreen(false);
    }
    if (previewLabel) {
      lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    }
    setAction("Starting recording");
    snapshotPreviewPrepared = false;
    if (httpGetGoPro("/gopro/camera/presets/set_group?id=1000")) {
      captureMode = "Video";
      syncCameraState();
    }
    delay(250);
    ok = httpGetGoPro("/gopro/camera/shutter/start");
  } else {
    ok = httpGetGoPro("/gopro/camera/shutter/stop");
  }
  if (!ok) {
    lv_label_set_text(statusLabel, recording ? "Recording" : "Standby");
    setAction("Recording command failed");
    return;
  }
  recording = nextRecording;
  if (recording) {
    recordingStartedMs = millis();
    lastRecordingOverlayMs = 0;
    if (pairButton) {
      lv_obj_add_state(pairButton, LV_STATE_DISABLED);
    }
  } else {
    recordingStartedMs = 0;
    lastRecordingOverlayMs = 0;
    if (pairButton) {
      lv_obj_clear_state(pairButton, LV_STATE_DISABLED);
    }
  }
  lv_label_set_text(statusLabel, recording ? "Recording" : "Standby");
  if (previewLabel) {
    if (previewHasImage || recording) {
      lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    } else {
      lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
      lv_label_set_text(previewLabel, "Double-click lower for snapshot");
    }
  }
  updateRecordingOverlay(true);
  setAction(recording ? "Recording; preview paused" : "Recording stopped");
}

bool beginLivePreviewUdp() {
  if (previewUdpListening) {
    return true;
  }
  previewUdp.stop();
  if (!previewUdp.begin(kPreviewStreamPort)) {
    Serial.println("Preview UDP bind failed");
    return false;
  }
  previewUdpListening = true;
  previewBytesThisWindow = 0;
  previewPacketsThisWindow = 0;
  lastPreviewStatsMs = millis();
  Serial.printf("Preview UDP listening on %u\n", kPreviewStreamPort);
  return true;
}

int startGoProStreamPath(const String &path, const char *stopPath, const char *label) {
  int status = httpGetGoProStatus(path);
  if (status == 409) {
    Serial.printf("%s already active; stopping stale stream\n", label);
    httpGetGoProStatus(stopPath);
    delay(500);
    status = httpGetGoProStatus(path);
  }
  Serial.printf("%s start status=%d path=%s\n", label, status, path.c_str());
  return status;
}

bool startGoProLivePreview() {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }
  if (!beginLivePreviewUdp()) {
    lv_label_set_text(previewLabel, "Preview UDP bind failed");
    return false;
  }
  if (previewStreamRequested) {
    return true;
  }

  h264StreamUnsupported = false;
  h264UnsupportedNotified = false;
  h264DecodeFailures = 0;
  h264FramesDecoded = 0;
  h264AccessUnitLen = 0;
  httpGetGoProStatus("/gopro/camera/stream/stop");
  httpGetGoProStatus("/gopro/webcam/stop");
  delay(300);

  String streamName = "GoPro webcam 480p";
  int status = startGoProStreamPath("/gopro/webcam/start?res=4&fov=0",
                                    "/gopro/webcam/stop", streamName.c_str());
  if (status < 200 || status >= 300) {
    streamName = "GoPro webcam 720p";
    status = startGoProStreamPath("/gopro/webcam/start?res=7&fov=0",
                                  "/gopro/webcam/stop", streamName.c_str());
  }
  if (status < 200 || status >= 300) {
    Serial.println("Webcam stream failed; falling back to preview stream");
    streamName = "GoPro preview";
    String path = "/gopro/camera/stream/start?port=";
    path += kPreviewStreamPort;
    status = startGoProStreamPath(path, "/gopro/camera/stream/stop", streamName.c_str());
  }
  bool ok = status >= 200 && status < 300;
  previewStreamRequested = ok;
  if (ok) {
    lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    String label = streamName + " starting";
    lv_label_set_text(previewLabel, label.c_str());
    setPreviewFullscreen(true);
    String action = streamName + " started";
    setAction(action.c_str());
  } else {
    lv_label_set_text(previewLabel, "Preview start failed");
  }
  return ok;
}

void pollLivePreviewUdp() {
  if (!previewUdpListening) {
    return;
  }

  for (uint8_t packets = 0; packets < 12; ++packets) {
    int packetSize = previewUdp.parsePacket();
    if (packetSize <= 0) {
      break;
    }
    previewPacketsThisWindow++;
    previewBytesThisWindow += static_cast<uint32_t>(packetSize);
    while (packetSize > 0) {
      uint8_t scratch[kTsPacketBytes];
      int toRead = min(packetSize, static_cast<int>(sizeof(scratch)));
      int readLen = previewUdp.read(scratch, toRead);
      if (readLen <= 0) {
        break;
      }
      if (readLen == static_cast<int>(kTsPacketBytes)) {
        processTsPacket(scratch);
      }
      packetSize -= readLen;
    }
  }

  if (millis() - lastPreviewStatsMs < kLivePreviewStatsMs) {
    return;
  }

  uint32_t elapsed = max<uint32_t>(1, millis() - lastPreviewStatsMs);
  uint32_t kbps = (previewBytesThisWindow * 8UL) / elapsed;
  lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
  if (h264StreamUnsupported) {
    lv_label_set_text(previewLabel, "Stream connected\nP4/host decoder required");
  } else {
    const char *label = previewPacketsThisWindow > 0
                            ? "GoPro preview\ntrying decoder"
                            : "GoPro preview\nwaiting for packets";
    lv_label_set_text(previewLabel, label);
  }
  Serial.printf("Preview UDP: %u packets, %u bytes, %u kbps\n", previewPacketsThisWindow,
                previewBytesThisWindow, kbps);
  previewBytesThisWindow = 0;
  previewPacketsThisWindow = 0;
  lastPreviewStatsMs = millis();
}

bool isCaptureTileActive() {
  if (previewFullscreen || tileView == nullptr || captureTileObj == nullptr) {
    return true;
  }
  lv_obj_t *activeTile = lv_tileview_get_tile_act(tileView);
  return activeTile == nullptr || activeTile == captureTileObj;
}

int jpegScaleDivisor(int scale) {
  if (scale == JPEG_SCALE_EIGHTH) {
    return 8;
  }
  if (scale == JPEG_SCALE_QUARTER) {
    return 4;
  }
  if (scale == JPEG_SCALE_HALF) {
    return 2;
  }
  return 1;
}

int jpegScaledDim(int dim, int scale) {
  return max(1, dim / jpegScaleDivisor(scale));
}

bool jpegScaleCovers(int width, int height, int scale, int frameW, int frameH) {
  return jpegScaledDim(width, scale) >= frameW && jpegScaledDim(height, scale) >= frameH;
}

int chooseJpegCoverScale(int width, int height, int frameW, int frameH) {
  const int scales[] = {JPEG_SCALE_EIGHTH, JPEG_SCALE_QUARTER, JPEG_SCALE_HALF, 0};
  for (int scale : scales) {
    if (jpegScaleCovers(width, height, scale, frameW, frameH)) {
      return scale;
    }
  }
  return 0;
}

int drawJpegBlock(JPEGDRAW *draw) {
  if (!isCaptureTileActive()) {
    return 0;
  }
  if (!draw || !draw->pPixels) {
    return 1;
  }
  int frameX = previewFrameX();
  int frameY = previewFrameY();
  int frameW = previewFrameW();
  int frameH = previewFrameH();
  int dstX = jpegDrawX + draw->x;
  int dstY = jpegDrawY + draw->y;
  int srcStride = draw->iWidth;
  int srcW = draw->iWidthUsed > 0 ? draw->iWidthUsed : draw->iWidth;
  int srcH = draw->iHeight;
  if (srcStride <= 0 || srcW <= 0 || srcH <= 0 ||
      dstX >= frameX + frameW || dstY >= frameY + frameH ||
      dstX + srcW <= frameX || dstY + srcH <= frameY) {
    return 1;
  }

  int clipLeft = max(0, frameX - dstX);
  int clipTop = max(0, frameY - dstY);
  int clipRight = max(0, (dstX + srcW) - (frameX + frameW));
  int clipBottom = max(0, (dstY + srcH) - (frameY + frameH));
  int drawW = srcW - clipLeft - clipRight;
  int drawH = srcH - clipTop - clipBottom;
  if (drawW <= 0 || drawH <= 0) {
    return 1;
  }

  int outX = dstX + clipLeft;
  int outY = dstY + clipTop;
  uint16_t *pixels = draw->pPixels + clipTop * srcStride + clipLeft;
  if (drawW == srcStride && drawH == srcH && clipLeft == 0 && clipTop == 0) {
    gfx->draw16bitRGBBitmap(outX, outY, pixels, drawW, drawH);
  } else {
    for (int row = 0; row < drawH; ++row) {
      gfx->draw16bitRGBBitmap(outX, outY + row, pixels + row * srcStride, drawW, 1);
    }
  }
  return 1;
}

bool drawJpegPreview(uint8_t *buffer, size_t length) {
  if (!isCaptureTileActive()) {
    Serial.printf("JPEG draw skipped: inactive tile active=%p capture=%p fullscreen=%u\n",
                  tileView ? lv_tileview_get_tile_act(tileView) : nullptr,
                  captureTileObj, previewFullscreen ? 1 : 0);
    return false;
  }
  if (!jpeg.openRAM(buffer, static_cast<int>(length), drawJpegBlock)) {
    Serial.printf("JPEG open failed: len=%u header=%02x %02x %02x %02x error=%d\n",
                  static_cast<unsigned>(length),
                  length > 0 ? buffer[0] : 0,
                  length > 1 ? buffer[1] : 0,
                  length > 2 ? buffer[2] : 0,
                  length > 3 ? buffer[3] : 0,
                  jpeg.getLastError());
    return false;
  }

  int frameX = previewFrameX();
  int frameY = previewFrameY();
  int frameW = previewFrameW();
  int frameH = previewFrameH();
  Serial.printf("JPEG opened: len=%u size=%dx%d type=%d bpp=%d subsample=%d\n",
                static_cast<unsigned>(length), jpeg.getWidth(), jpeg.getHeight(),
                jpeg.getJPEGType(), jpeg.getBpp(), jpeg.getSubSample());

  int scale = chooseJpegCoverScale(jpeg.getWidth(), jpeg.getHeight(), frameW, frameH);
  int outW = jpegScaledDim(jpeg.getWidth(), scale);
  int outH = jpegScaledDim(jpeg.getHeight(), scale);
  jpegDrawX = frameX + (frameW - outW) / 2;
  jpegDrawY = frameY + (frameH - outH) / 2;
  Serial.printf("JPEG cover: frame=%dx%d scale=%d out=%dx%d origin=%d,%d\n",
                frameW, frameH, scale, outW, outH, jpegDrawX, jpegDrawY);

  gfx->fillRect(frameX, frameY, frameW, frameH, 0x0000);
  jpeg.setPixelType(RGB565_LITTLE_ENDIAN);
  bool ok = jpeg.decode(0, 0, scale) != 0;
  if (!ok) {
    Serial.printf("JPEG decode failed: scale=%d error=%d\n", scale, jpeg.getLastError());
  } else {
    drawFullscreenSwipeHandle();
  }
  jpeg.close();
  return ok;
}

bool downloadAndDrawPreviewJpeg(const String &path, uint8_t *buffer, size_t capacity,
                                size_t &jpegLength) {
  jpegLength = 0;
  if (!httpGetGoProBinary(path, buffer, capacity, jpegLength)) {
    return false;
  }
  if (jpegLength < 1024) {
    Serial.printf("JPEG response too small: %u bytes\n", static_cast<unsigned>(jpegLength));
    return false;
  }
  setPreviewFullscreen(true);
  if (previewLabel) {
    lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
  }
  lv_timer_handler();
  return drawJpegPreview(buffer, jpegLength);
}

bool fetchSnapshotPreview() {
  if (snapshotPreviewBusy) {
    return false;
  }
  snapshotPreviewBusy = true;

  if (previewUdpListening) {
    previewUdp.stop();
    previewUdpListening = false;
  }
  previewStreamRequested = false;

  if (previewLabel) {
    if (previewHasImage) {
      lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    } else {
      lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
      lv_label_set_text(previewLabel, "Preparing snapshot");
    }
  }
  setAction("Preparing snapshot");
  lv_timer_handler();

  if (!snapshotPreviewPrepared) {
    httpGetGoProStatus("/gopro/webcam/stop");
    httpGetGoProStatus("/gopro/camera/stream/stop");
    if (!httpGetGoPro("/gopro/camera/presets/set_group?id=1001")) {
      if (previewLabel && !previewHasImage) {
        lv_label_set_text(previewLabel, "Photo preset failed");
      }
      snapshotPreviewBusy = false;
      return false;
    }
    captureMode = "Photo";
    applyCaptureLabels();
    snapshotPreviewPrepared = true;
    delay(250);
  }

  String beforePath;
  fetchLatestJpegPath(beforePath);
  if (previewLabel && !previewHasImage) {
    lv_label_set_text(previewLabel, "Capturing snapshot");
  }
  setAction("Capturing snapshot");
  lv_timer_handler();

  if (!httpGetGoPro("/gopro/camera/shutter/start")) {
    if (previewLabel && !previewHasImage) {
      lv_label_set_text(previewLabel, "Snapshot failed");
    }
    setAction("Snapshot failed");
    snapshotPreviewBusy = false;
    return false;
  }

  String newPath;
  uint32_t pollStart = millis();
  while (millis() - pollStart < 12000) {
    delay(250);
    lv_timer_handler();
    String latest;
    if (fetchLatestJpegPath(latest) && !latest.isEmpty() && latest != beforePath &&
        latest != lastSnapshotMediaPath) {
      newPath = latest;
      break;
    }
  }

  if (newPath.isEmpty()) {
    if (previewLabel && !previewHasImage) {
      lv_label_set_text(previewLabel, "Snapshot media not found");
    }
    setAction("Snapshot media not found");
    snapshotPreviewBusy = false;
    return false;
  }

  String encodedPath = urlEncodePathParam(newPath);
  uint8_t *jpegBuffer = static_cast<uint8_t *>(heap_caps_malloc(kMaxJpegBytes, MALLOC_CAP_SPIRAM));
  if (jpegBuffer == nullptr) {
    jpegBuffer = static_cast<uint8_t *>(heap_caps_malloc(kMaxJpegBytes, MALLOC_CAP_8BIT));
  }
  if (jpegBuffer == nullptr) {
    deleteGoProMedia(newPath);
    if (previewLabel && !previewHasImage) {
      lv_label_set_text(previewLabel, "JPEG buffer allocation failed");
    }
    setAction("JPEG buffer allocation failed");
    snapshotPreviewBusy = false;
    return false;
  }

  size_t jpegLength = 0;
  String screenPath = "/gopro/media/screennail?path=" + encodedPath;
  bool downloaded = false;
  bool drawn = downloadAndDrawPreviewJpeg(screenPath, jpegBuffer, kMaxJpegBytes, jpegLength);
  downloaded = jpegLength >= 1024;
  if (!drawn) {
    String thumbPath = "/gopro/media/thumbnail?path=" + encodedPath;
    size_t thumbLength = 0;
    drawn = downloadAndDrawPreviewJpeg(thumbPath, jpegBuffer, kMaxJpegBytes, thumbLength);
    downloaded = downloaded || thumbLength >= 1024;
  }
  heap_caps_free(jpegBuffer);

  bool deleted = deleteGoProMedia(newPath);
  lastSnapshotMediaPath = newPath;
  snapshotPreviewBusy = false;

  if (drawn) {
    previewHasImage = true;
    if (previewLabel) {
      lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    }
    lv_label_set_text(statusLabel, "Snapshot preview");
    setAction(deleted ? "Preview JPEG deleted" : "Preview JPEG delete failed");
    return true;
  }

  if (previewLabel) {
    if (previewHasImage) {
      lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    } else {
      lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
      lv_label_set_text(previewLabel, downloaded ? "JPEG decode failed" : "JPEG download failed");
    }
  }
  setAction(deleted ? "Deleted failed preview JPEG" : "Preview failed; delete failed");
  return false;
}

void onPair(lv_event_t *) {
  queuePairNewAction("button");
}

void onForgetCamera(lv_event_t *) {
  if (recording) {
    setAction("Stop recording before forgetting");
    return;
  }
  showForgetConfirm();
}

void onForgetCancel(lv_event_t *) {
  hideForgetConfirm();
  setAction("Forget cancelled");
}

void onForgetConfirm(lv_event_t *) {
  hideForgetConfirm();
  if (recording) {
    setAction("Stop recording before forgetting");
    return;
  }
  if (goproActionBusy || pairingInProgress) {
    requestConnectionCancel("Cancelling and forgetting camera");
    forgetCameraBinding(true);
    return;
  }
  runForgetCameraAction();
}

void selectMode(const char *mode, const char *setting, const char *endpoint) {
  captureMode = mode;
  captureSetting = setting;
  snapshotPreviewPrepared = false;
  applyCaptureLabels();
  lv_label_set_text(statusLabel, captureMode.c_str());
  if (WiFi.status() == WL_CONNECTED && endpoint && endpoint[0]) {
    if (httpGetGoPro(endpoint)) {
      delay(250);
      syncCameraState();
    }
  }
  setAction(captureSetting.c_str());
}

void onModeVideo(lv_event_t *) {
  selectMode("Video", "Sync camera state", "/gopro/camera/presets/set_group?id=1000");
}

void onModePhoto(lv_event_t *) {
  selectMode("Photo", "Sync camera state", "/gopro/camera/presets/set_group?id=1001");
}

void onModeTimeWarp(lv_event_t *) {
  selectMode("TimeWarp", "Sync camera state", "/gopro/camera/presets/set_group?id=1002");
}

void onDashboardConnect(lv_event_t *) {
  connectGoProWifiFromBle();
}

void onSettingSync(lv_event_t *) {
  syncCameraState();
}

void onPresetSync(lv_event_t *) {
  syncCameraPresets();
}

void refreshSettingSheet() {
  if (!settingSheet || !activeSetting) {
    return;
  }

  String title = activeSetting->name;
  int current = getStoredSettingValue(activeSetting->id);
  if (current >= 0) {
    title += " | current ";
    title += activeOptionDisplayName(activeSetting->id, current);
  }
  lv_label_set_text(settingSheetTitle, title.c_str());

  for (size_t i = 0; i < kVisibleSettingOptions; ++i) {
    size_t optionIndex = settingOptionOffset + i;
    if (optionIndex < settingOptionCount) {
      int option = settingOptions[optionIndex];
      String label = activeOptionDisplayName(activeSetting->id, option);
      if (option == current) {
        label += " *";
      }
      lv_label_set_text(settingOptionLabels[i], label.c_str());
      lv_obj_clear_flag(settingOptionButtons[i], LV_OBJ_FLAG_HIDDEN);
    } else {
      lv_obj_add_flag(settingOptionButtons[i], LV_OBJ_FLAG_HIDDEN);
    }
  }

  String pager = String(settingOptionOffset + 1) + "-";
  pager += min(settingOptionOffset + kVisibleSettingOptions, settingOptionCount);
  pager += " of ";
  pager += settingOptionCount;
  lv_label_set_text(settingPagerLabel, pager.c_str());
}

void closeSettingSheet() {
  if (settingSheet) {
    lv_obj_add_flag(settingSheet, LV_OBJ_FLAG_HIDDEN);
  }
}

void onSettingClose(lv_event_t *) {
  closeSettingSheet();
}

void onSettingNext(lv_event_t *) {
  if (settingOptionOffset + kVisibleSettingOptions < settingOptionCount) {
    settingOptionOffset += kVisibleSettingOptions;
    refreshSettingSheet();
  }
}

void onSettingPrev(lv_event_t *) {
  if (settingOptionOffset >= kVisibleSettingOptions) {
    settingOptionOffset -= kVisibleSettingOptions;
  } else {
    settingOptionOffset = 0;
  }
  refreshSettingSheet();
}

void onSettingOption(lv_event_t *event) {
  if (!activeSetting) {
    return;
  }
  uintptr_t visibleIndex = reinterpret_cast<uintptr_t>(lv_event_get_user_data(event));
  size_t optionIndex = settingOptionOffset + visibleIndex;
  if (optionIndex >= settingOptionCount) {
    return;
  }
  int option = settingOptions[optionIndex];
  String label = String(activeSetting->name) + " -> " +
                 activeOptionDisplayName(activeSetting->id, option);
  if (setGoProSetting(activeSetting->id, option, label.c_str())) {
    refreshSettingSheet();
  }
}

void onSettingOpen(lv_event_t *event) {
  const SettingDefinition *setting =
      static_cast<const SettingDefinition *>(lv_event_get_user_data(event));
  if (!setting) {
    return;
  }
  activeSetting = setting;
  if (!settingSheet) {
    return;
  }
  lv_obj_clear_flag(settingSheet, LV_OBJ_FLAG_HIDDEN);
  lv_label_set_text(settingSheetTitle, "Loading options...");
  lv_timer_handler();

  if (!querySettingOptions(*setting)) {
    setAction("No options for setting");
  }
  refreshSettingSheet();
}

lv_obj_t *makePanelLabel(lv_obj_t *parent, const char *text, int x, int y, int size = 14,
                         lv_color_t color = lv_color_hex(0xf4f7fb)) {
  lv_obj_t *label = lv_label_create(parent);
  lv_label_set_text(label, text);
  lv_obj_set_style_text_font(label, fontForSize(size), 0);
  lv_obj_set_style_text_color(label, color, 0);
  lv_obj_set_pos(label, x, y);
  return label;
}

const SettingDefinition kCaptureSettings[] = {
    {"Aspect Ratio", 108},
    {"Resolution", 2},
    {"Frame Rate", 234},
    {"Video FPS Legacy", 3},
    {"Digital Lens", 121},
    {"Photo Lens", 122},
    {"TimeWarp Lens", 123},
    {"HyperSmooth", 135},
    {"Horizon Level", 150},
    {"Scheduled", 168},
    {"Duration", 156},
    {"HindSight", 167},
};

const SettingDefinition kProSettings[] = {
    {"Bit Depth", 183},
    {"Bit Rate", 182},
    {"Max Lens", 162},
    {"Max Lens Mod", 189},
    {"Max Lens Enable", 190},
    {"Media Format", 128},
    {"Photo Output", 125},
    {"Anti-Flicker", 134},
    {"Performance", 173},
    {"Control Mode", 175},
    {"Video Mode", 180},
    {"Profiles", 184},
};

const SettingDefinition kSystemSettings[] = {
    {"Camera Mode", 194},
    {"Photo Mode", 227},
    {"Wireless Band", 178},
    {"Auto WiFi AP", 236},
    {"Beeps", 216},
    {"Screen Saver", 219},
    {"GPS", 83},
    {"LED", 91},
};

void createUi() {
  lv_obj_t *screen = lv_scr_act();
  lv_obj_set_style_bg_color(screen, lv_color_hex(0x090b10), 0);
  lv_obj_set_style_text_color(screen, lv_color_hex(0xf4f7fb), 0);
  lv_obj_set_style_text_font(screen, fontForSize(16), 0);
  lv_obj_add_event_cb(screen, onPageGesture, LV_EVENT_GESTURE, nullptr);

  lv_obj_t *topBar = lv_obj_create(screen);
  lv_obj_set_size(topBar, LCD_WIDTH, kTopBarH);
  lv_obj_set_pos(topBar, 0, 0);
  lv_obj_set_style_radius(topBar, 0, 0);
  lv_obj_set_style_bg_color(topBar, lv_color_hex(0x05070b), 0);
  lv_obj_set_style_border_width(topBar, 0, 0);
  lv_obj_set_style_pad_all(topBar, 0, 0);
  lv_obj_clear_flag(topBar, LV_OBJ_FLAG_SCROLLABLE);

  lv_obj_t *title = lv_label_create(screen);
  lv_label_set_text(title, "GoPro");
  lv_obj_set_style_text_font(title, fontForSize(20), 0);
  lv_obj_set_style_text_color(title, lv_color_hex(0xf4f7fb), 0);
  lv_obj_align(title, LV_ALIGN_TOP_LEFT, 12, 7);

  statusLabel = lv_label_create(screen);
  lv_label_set_text(statusLabel, "Ready");
  lv_obj_set_style_text_color(statusLabel, lv_color_hex(0x96a2b4), 0);
  lv_obj_add_flag(statusLabel, LV_OBJ_FLAG_HIDDEN);

  batteryLabel = lv_label_create(screen);
  lv_label_set_text(batteryLabel, LV_SYMBOL_BATTERY_EMPTY);
  lv_obj_set_style_text_color(batteryLabel, lv_color_hex(0xc3ccd8), 0);
  lv_obj_align(batteryLabel, LV_ALIGN_TOP_RIGHT, -24, 7);

  wifiIndicator = lv_label_create(screen);
  lv_label_set_text(wifiIndicator, LV_SYMBOL_WIFI);
  lv_obj_set_style_text_color(wifiIndicator, lv_color_hex(0x5a6472), 0);
  lv_obj_align(wifiIndicator, LV_ALIGN_TOP_RIGHT, -122, 7);

  bleIndicator = lv_label_create(screen);
  lv_label_set_text(bleIndicator, LV_SYMBOL_BLUETOOTH);
  lv_obj_set_style_text_color(bleIndicator, lv_color_hex(0x5a6472), 0);
  lv_obj_align(bleIndicator, LV_ALIGN_TOP_RIGHT, -148, 7);

  tileView = lv_tileview_create(screen);
  lv_obj_set_size(tileView, LCD_WIDTH, LCD_HEIGHT - kTopBarH);
  lv_obj_align(tileView, LV_ALIGN_BOTTOM_MID, 0, 0);
  lv_obj_set_style_bg_color(tileView, lv_color_hex(0x090b10), 0);
  lv_obj_set_style_border_width(tileView, 0, 0);
  lv_obj_set_style_pad_all(tileView, 0, 0);
  lv_obj_clear_flag(tileView, LV_OBJ_FLAG_SCROLL_ELASTIC);
  lv_obj_clear_flag(tileView, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_scrollbar_mode(tileView, LV_SCROLLBAR_MODE_OFF);
  lv_obj_add_event_cb(tileView, onPageGesture, LV_EVENT_GESTURE, nullptr);

  lv_obj_t *captureTile = lv_tileview_add_tile(tileView, 0, 0, LV_DIR_NONE);
  captureTileObj = captureTile;
  lv_obj_set_style_bg_color(captureTile, lv_color_hex(0x090b10), 0);
  lv_obj_add_event_cb(captureTile, onPreviewGesture, LV_EVENT_GESTURE, nullptr);
  lv_obj_add_event_cb(captureTile, onPageGesture, LV_EVENT_GESTURE, nullptr);

  previewBox = lv_obj_create(captureTile);
  lv_obj_set_size(previewBox, kPreviewW, kPreviewH);
  lv_obj_set_pos(previewBox, kPreviewX, 6);
  lv_obj_set_style_radius(previewBox, 8, 0);
  lv_obj_set_style_bg_color(previewBox, lv_color_hex(0x101827), 0);
  lv_obj_set_style_border_color(previewBox, lv_color_hex(0x2b3a52), 0);
  lv_obj_set_style_border_width(previewBox, 1, 0);
  lv_obj_clear_flag(previewBox, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_add_event_cb(previewBox, onPreviewGesture, LV_EVENT_GESTURE, nullptr);

  previewLabel = lv_label_create(previewBox);
  lv_label_set_text(previewLabel, "Preview standby");
  lv_obj_set_style_text_color(previewLabel, lv_color_hex(0xdde7f5), 0);
  lv_obj_set_style_text_font(previewLabel, fontForSize(18), 0);
  lv_obj_center(previewLabel);

  recordingOverlay = lv_obj_create(previewBox);
  lv_obj_set_size(recordingOverlay, 186, 70);
  lv_obj_center(recordingOverlay);
  lv_obj_set_style_radius(recordingOverlay, 6, 0);
  lv_obj_set_style_bg_color(recordingOverlay, lv_color_hex(0xd71920), 0);
  lv_obj_set_style_bg_opa(recordingOverlay, LV_OPA_COVER, 0);
  lv_obj_set_style_border_width(recordingOverlay, 0, 0);
  lv_obj_set_style_pad_all(recordingOverlay, 0, 0);
  lv_obj_clear_flag(recordingOverlay, LV_OBJ_FLAG_SCROLLABLE);
  recordingOverlayLabel = lv_label_create(recordingOverlay);
  lv_label_set_text(recordingOverlayLabel, "RECORDING\n00:00");
  lv_obj_set_style_text_align(recordingOverlayLabel, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_set_style_text_color(recordingOverlayLabel, lv_color_hex(0xffffff), 0);
  lv_obj_set_style_text_font(recordingOverlayLabel, fontForSize(20), 0);
  lv_obj_center(recordingOverlayLabel);
  lv_obj_add_flag(recordingOverlay, LV_OBJ_FLAG_HIDDEN);

  fullscreenHint = lv_obj_create(previewBox);
  lv_obj_set_size(fullscreenHint, 78, 3);
  lv_obj_align(fullscreenHint, LV_ALIGN_BOTTOM_MID, 0, 4);
  lv_obj_set_style_radius(fullscreenHint, 2, 0);
  lv_obj_set_style_bg_color(fullscreenHint, lv_color_hex(0xf4f7fb), 0);
  lv_obj_set_style_bg_opa(fullscreenHint, LV_OPA_90, 0);
  lv_obj_set_style_border_width(fullscreenHint, 0, 0);
  lv_obj_clear_flag(fullscreenHint, LV_OBJ_FLAG_SCROLLABLE);

  recordPill = lv_obj_create(captureTile);
  lv_obj_set_size(recordPill, 76, 28);
  lv_obj_set_pos(recordPill, 272, 18);
  lv_obj_set_style_radius(recordPill, 8, 0);
  lv_obj_set_style_bg_color(recordPill, lv_color_hex(0x1b2638), 0);
  lv_obj_set_style_border_width(recordPill, 0, 0);
  lv_obj_t *recDot = lv_obj_create(recordPill);
  lv_obj_set_size(recDot, 10, 10);
  lv_obj_set_pos(recDot, 10, 9);
  lv_obj_set_style_radius(recDot, 5, 0);
  lv_obj_set_style_bg_color(recDot, lv_color_hex(0xe03131), 0);
  lv_obj_set_style_border_width(recDot, 0, 0);
  makePanelLabel(recordPill, "REC", 28, 7, 14, lv_color_hex(0xf4f7fb));
  lv_obj_add_flag(recordPill, LV_OBJ_FLAG_HIDDEN);

  timeRemainingLabel = makePanelLabel(captureTile, "9H:59", 22, 14, 18, lv_color_hex(0xf4f7fb));
  lv_obj_add_flag(timeRemainingLabel, LV_OBJ_FLAG_HIDDEN);
  captureModeLabel = makePanelLabel(captureTile, captureMode.c_str(), 22, 170, 18);
  captureSettingLabel = makePanelLabel(captureTile, captureSetting.c_str(), 22, 194, 14,
                                       lv_color_hex(0xc3ccd8));

  cameraLabel = lv_label_create(captureTile);
  lv_label_set_text(cameraLabel, "Camera: not paired");
  lv_obj_set_style_text_color(cameraLabel, lv_color_hex(0xc3ccd8), 0);
  lv_obj_set_style_text_font(cameraLabel, fontForSize(16), 0);
  lv_obj_set_pos(cameraLabel, 20, 224);

  wifiLabel = lv_label_create(captureTile);
  lv_label_set_text(wifiLabel, "WiFi: idle");
  lv_obj_set_style_text_color(wifiLabel, lv_color_hex(0x96a2b4), 0);
  lv_obj_set_style_text_font(wifiLabel, fontForSize(16), 0);
  lv_obj_set_pos(wifiLabel, 20, 246);
  lv_obj_add_flag(wifiLabel, LV_OBJ_FLAG_HIDDEN);

  pairButton = makeTouchButton(captureTile, "Pair New", kPreviewX, kHomeButtonY, kPreviewW,
                               kHomeButtonH,
                               lv_color_hex(0x2c7be5));
  lv_obj_add_event_cb(pairButton, onPair, LV_EVENT_CLICKED, nullptr);
  lv_obj_add_flag(pairButton, LV_OBJ_FLAG_CLICKABLE);

  actionLabel = lv_label_create(captureTile);
  lv_label_set_text(actionLabel, "Auto-connect | tap Pair New to change camera");
  lv_obj_set_width(actionLabel, kPreviewW);
  lv_label_set_long_mode(actionLabel, LV_LABEL_LONG_DOT);
  lv_obj_set_style_text_color(actionLabel, lv_color_hex(0x96a2b4), 0);
  lv_obj_set_style_text_font(actionLabel, fontForSize(16), 0);
  lv_obj_set_style_text_align(actionLabel, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_align(actionLabel, LV_ALIGN_BOTTOM_MID, 0, -2);

  lv_obj_t *modeTile = lv_tileview_add_tile(tileView, 1, 0, LV_DIR_NONE);
  lv_obj_set_style_bg_color(modeTile, lv_color_hex(0x090b10), 0);
  makePanelLabel(modeTile, "Modes", 20, 18, 18);
  makePanelLabel(modeTile, "Mode controls stay on fixed pages", 20, 44, 14,
                 lv_color_hex(0x96a2b4));
  lv_obj_t *video = makeChip(modeTile, "Video", 20, 84, 328, lv_color_hex(0x2c7be5));
  lv_obj_add_event_cb(video, onModeVideo, LV_EVENT_CLICKED, nullptr);
  lv_obj_t *photo = makeChip(modeTile, "Photo", 20, 132, 328, lv_color_hex(0x009a88));
  lv_obj_add_event_cb(photo, onModePhoto, LV_EVENT_CLICKED, nullptr);
  lv_obj_t *timeWarp = makeChip(modeTile, "TimeWarp", 20, 180, 328, lv_color_hex(0x7c4dff));
  lv_obj_add_event_cb(timeWarp, onModeTimeWarp, LV_EVENT_CLICKED, nullptr);
  makePanelLabel(modeTile, "Main overlay shows mode, aspect, resolution, fps, lens", 20, 242, 14,
                 lv_color_hex(0xc3ccd8));

  lv_obj_t *captureSettingsTile = lv_tileview_add_tile(tileView, 2, 0, LV_DIR_NONE);
  lv_obj_set_style_bg_color(captureSettingsTile, lv_color_hex(0x090b10), 0);
  makePanelLabel(captureSettingsTile, "Capture Settings", 20, 18, 18);
  makePanelLabel(captureSettingsTile, "Resolution, frame rate, lens, and aspect", 20, 44, 14,
                 lv_color_hex(0x96a2b4));
  for (int i = 0; i < static_cast<int>(sizeof(kCaptureSettings) / sizeof(kCaptureSettings[0])); ++i) {
    int x = 20 + (i % 2) * 168;
    int y = 82 + (i / 2) * 48;
    lv_obj_t *button = makeChip(captureSettingsTile, kCaptureSettings[i].name, x, y, 156,
                                lv_color_hex(0x1b2638));
    lv_obj_add_event_cb(button, onSettingOpen, LV_EVENT_CLICKED,
                        const_cast<SettingDefinition *>(&kCaptureSettings[i]));
  }
  lv_obj_t *syncState = makeChip(captureSettingsTile, "Sync State", 20, 314, 156,
                                 lv_color_hex(0x2c7be5));
  lv_obj_add_event_cb(syncState, onSettingSync, LV_EVENT_CLICKED, nullptr);
  lv_obj_t *syncPresets = makeChip(captureSettingsTile, "Sync Presets", 192, 314, 156,
                                   lv_color_hex(0x2c7be5));
  lv_obj_add_event_cb(syncPresets, onPresetSync, LV_EVENT_CLICKED, nullptr);

  lv_obj_t *protuneTile = lv_tileview_add_tile(tileView, 3, 0, LV_DIR_NONE);
  lv_obj_set_style_bg_color(protuneTile, lv_color_hex(0x090b10), 0);
  makePanelLabel(protuneTile, "Pro Controls", 20, 18, 18);
  makePanelLabel(protuneTile, "Advanced settings exposed by Open GoPro", 20, 44, 14,
                 lv_color_hex(0x96a2b4));
  for (int i = 0; i < static_cast<int>(sizeof(kProSettings) / sizeof(kProSettings[0])); ++i) {
    int x = 20 + (i % 2) * 168;
    int y = 82 + (i / 2) * 40;
    lv_obj_t *button = makeChip(protuneTile, kProSettings[i].name, x, y, 156,
                                lv_color_hex(0x1b2638));
    lv_obj_add_event_cb(button, onSettingOpen, LV_EVENT_CLICKED,
                        const_cast<SettingDefinition *>(&kProSettings[i]));
  }

  lv_obj_t *dashboardTile = lv_tileview_add_tile(tileView, 4, 0, LV_DIR_NONE);
  lv_obj_set_style_bg_color(dashboardTile, lv_color_hex(0x090b10), 0);
  makePanelLabel(dashboardTile, "Dashboard", 20, 18, 18);
  makePanelLabel(dashboardTile, "Connection and remote power controls", 20, 44, 14,
                 lv_color_hex(0x96a2b4));
  lv_obj_t *dashConnect = makeChip(dashboardTile, "Connect Camera", 20, 84, 328,
                                   lv_color_hex(0x2c7be5));
  lv_obj_add_event_cb(dashConnect, onDashboardConnect, LV_EVENT_CLICKED, nullptr);
  lv_obj_t *dashPair = makeChip(dashboardTile, "Pair BLE", 20, 132, 156, lv_color_hex(0x7c4dff));
  lv_obj_add_event_cb(dashPair, onPair, LV_EVENT_CLICKED, nullptr);
  lv_obj_t *dashState = makeChip(dashboardTile, "Camera State", 192, 132, 156,
                                 lv_color_hex(0x009a88));
  lv_obj_add_event_cb(dashState, onSettingSync, LV_EVENT_CLICKED, nullptr);
  for (int i = 0; i < static_cast<int>(sizeof(kSystemSettings) / sizeof(kSystemSettings[0])); ++i) {
    int x = 20 + (i % 2) * 168;
    int y = 180 + (i / 2) * 40;
    lv_obj_t *button = makeChip(dashboardTile, kSystemSettings[i].name, x, y, 156,
                                lv_color_hex(0x1b2638));
    lv_obj_add_event_cb(button, onSettingOpen, LV_EVENT_CLICKED,
                        const_cast<SettingDefinition *>(&kSystemSettings[i]));
  }
  makePanelLabel(dashboardTile, "Top REC: start / long-stop | Lower: display / double preview", 20, 350, 14,
                 lv_color_hex(0xc3ccd8));

  maintenancePage = lv_obj_create(screen);
  lv_obj_set_size(maintenancePage, LCD_WIDTH, LCD_HEIGHT - kTopBarH);
  lv_obj_set_pos(maintenancePage, 0, kTopBarH);
  lv_obj_set_style_radius(maintenancePage, 0, 0);
  lv_obj_set_style_bg_color(maintenancePage, lv_color_hex(0x090b10), 0);
  lv_obj_set_style_border_width(maintenancePage, 0, 0);
  lv_obj_set_style_pad_all(maintenancePage, 0, 0);
  lv_obj_clear_flag(maintenancePage, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_add_event_cb(maintenancePage, onPageGesture, LV_EVENT_GESTURE, nullptr);
  makePanelLabel(maintenancePage, "Maintenance", 20, 22, 18);
  makePanelLabel(maintenancePage, "Swipe left to return", 20, 50, 14,
                 lv_color_hex(0x96a2b4));
  makePanelLabel(maintenancePage, "Pairing data", 20, 104, 14,
                 lv_color_hex(0xc3ccd8));
  forgetButton = makeTouchButton(maintenancePage, "Forget Camera", kPreviewX, 132,
                                 kPreviewW, kHomeButtonH, lv_color_hex(0x7f1d1d));
  lv_obj_add_event_cb(forgetButton, onForgetCamera, LV_EVENT_CLICKED, nullptr);
  makePanelLabel(maintenancePage,
                 "Removes saved BLE address and local bonds only after confirmation.",
                 20, 204, 14, lv_color_hex(0x96a2b4));
  lv_obj_add_flag(maintenancePage, LV_OBJ_FLAG_HIDDEN);

  settingSheet = lv_obj_create(screen);
  lv_obj_set_size(settingSheet, 332, 352);
  lv_obj_align(settingSheet, LV_ALIGN_CENTER, 0, 18);
  lv_obj_set_style_radius(settingSheet, 8, 0);
  lv_obj_set_style_bg_color(settingSheet, lv_color_hex(0x111827), 0);
  lv_obj_set_style_border_color(settingSheet, lv_color_hex(0x334155), 0);
  lv_obj_set_style_border_width(settingSheet, 1, 0);
  lv_obj_set_style_pad_all(settingSheet, 12, 0);
  lv_obj_clear_flag(settingSheet, LV_OBJ_FLAG_SCROLLABLE);

  settingSheetTitle = makePanelLabel(settingSheet, "Setting", 12, 12, 18);
  for (size_t i = 0; i < kVisibleSettingOptions; ++i) {
    settingOptionButtons[i] = makeChip(settingSheet, "", 12, 48 + i * 40, 308,
                                       lv_color_hex(0x1f2937));
    settingOptionLabels[i] = lv_obj_get_child(settingOptionButtons[i], 0);
    lv_obj_add_event_cb(settingOptionButtons[i], onSettingOption, LV_EVENT_CLICKED,
                        reinterpret_cast<void *>(i));
  }

  lv_obj_t *prev = makeChip(settingSheet, "Prev", 12, 294, 70, lv_color_hex(0x334155));
  lv_obj_add_event_cb(prev, onSettingPrev, LV_EVENT_CLICKED, nullptr);
  settingPagerLabel = makePanelLabel(settingSheet, "0 of 0", 112, 304, 14, lv_color_hex(0xc3ccd8));
  lv_obj_t *next = makeChip(settingSheet, "Next", 184, 294, 70, lv_color_hex(0x334155));
  lv_obj_add_event_cb(next, onSettingNext, LV_EVENT_CLICKED, nullptr);
  lv_obj_t *close = makeChip(settingSheet, "Close", 262, 294, 58, lv_color_hex(0x7f1d1d));
  lv_obj_add_event_cb(close, onSettingClose, LV_EVENT_CLICKED, nullptr);
  lv_obj_add_flag(settingSheet, LV_OBJ_FLAG_HIDDEN);

  pairingPopup = lv_obj_create(screen);
  lv_obj_set_size(pairingPopup, 320, 184);
  lv_obj_align(pairingPopup, LV_ALIGN_CENTER, 0, 20);
  lv_obj_set_style_radius(pairingPopup, 8, 0);
  lv_obj_set_style_bg_color(pairingPopup, lv_color_hex(0x111827), 0);
  lv_obj_set_style_bg_opa(pairingPopup, LV_OPA_COVER, 0);
  lv_obj_set_style_border_color(pairingPopup, lv_color_hex(0x7c4dff), 0);
  lv_obj_set_style_border_width(pairingPopup, 2, 0);
  lv_obj_set_style_pad_all(pairingPopup, 16, 0);
  lv_obj_clear_flag(pairingPopup, LV_OBJ_FLAG_SCROLLABLE);

  pairingPopupTitle = lv_label_create(pairingPopup);
  lv_obj_set_width(pairingPopupTitle, 288);
  lv_label_set_text(pairingPopupTitle, "Pairing New Camera");
  lv_obj_set_style_text_color(pairingPopupTitle, lv_color_hex(0xf4f7fb), 0);
  lv_obj_set_style_text_font(pairingPopupTitle, fontForSize(20), 0);
  lv_obj_set_style_text_align(pairingPopupTitle, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_align(pairingPopupTitle, LV_ALIGN_TOP_MID, 0, 0);

  pairingPopupMessage = lv_label_create(pairingPopup);
  lv_obj_set_width(pairingPopupMessage, 288);
  lv_label_set_long_mode(pairingPopupMessage, LV_LABEL_LONG_WRAP);
  lv_label_set_text(pairingPopupMessage, "Put the GoPro in pairing mode.\nPress lower button to cancel.");
  lv_obj_set_style_text_color(pairingPopupMessage, lv_color_hex(0xc3ccd8), 0);
  lv_obj_set_style_text_font(pairingPopupMessage, fontForSize(18), 0);
  lv_obj_set_style_text_align(pairingPopupMessage, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_align(pairingPopupMessage, LV_ALIGN_TOP_MID, 0, 42);
  lv_obj_add_flag(pairingPopup, LV_OBJ_FLAG_HIDDEN);

  forgetConfirmPopup = lv_obj_create(screen);
  lv_obj_set_size(forgetConfirmPopup, 320, 184);
  lv_obj_align(forgetConfirmPopup, LV_ALIGN_CENTER, 0, 20);
  lv_obj_set_style_radius(forgetConfirmPopup, 8, 0);
  lv_obj_set_style_bg_color(forgetConfirmPopup, lv_color_hex(0x111827), 0);
  lv_obj_set_style_bg_opa(forgetConfirmPopup, LV_OPA_COVER, 0);
  lv_obj_set_style_border_color(forgetConfirmPopup, lv_color_hex(0xd71920), 0);
  lv_obj_set_style_border_width(forgetConfirmPopup, 2, 0);
  lv_obj_set_style_pad_all(forgetConfirmPopup, 16, 0);
  lv_obj_clear_flag(forgetConfirmPopup, LV_OBJ_FLAG_SCROLLABLE);

  lv_obj_t *forgetTitle = lv_label_create(forgetConfirmPopup);
  lv_obj_set_width(forgetTitle, 288);
  lv_label_set_text(forgetTitle, "Forget Camera?");
  lv_obj_set_style_text_color(forgetTitle, lv_color_hex(0xf4f7fb), 0);
  lv_obj_set_style_text_font(forgetTitle, fontForSize(20), 0);
  lv_obj_set_style_text_align(forgetTitle, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_align(forgetTitle, LV_ALIGN_TOP_MID, 0, 0);

  lv_obj_t *forgetMessage = lv_label_create(forgetConfirmPopup);
  lv_obj_set_width(forgetMessage, 288);
  lv_label_set_long_mode(forgetMessage, LV_LABEL_LONG_WRAP);
  lv_label_set_text(forgetMessage, "This clears the saved BLE camera and local bond data.");
  lv_obj_set_style_text_color(forgetMessage, lv_color_hex(0xc3ccd8), 0);
  lv_obj_set_style_text_font(forgetMessage, fontForSize(18), 0);
  lv_obj_set_style_text_align(forgetMessage, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_align(forgetMessage, LV_ALIGN_TOP_MID, 0, 42);

  lv_obj_t *forgetCancel = makeChip(forgetConfirmPopup, "Cancel", 18, 122, 128,
                                    lv_color_hex(0x334155));
  lv_obj_add_event_cb(forgetCancel, onForgetCancel, LV_EVENT_CLICKED, nullptr);
  lv_obj_t *forgetConfirm = makeChip(forgetConfirmPopup, "Forget", 174, 122, 128,
                                     lv_color_hex(0x7f1d1d));
  lv_obj_add_event_cb(forgetConfirm, onForgetConfirm, LV_EVENT_CLICKED, nullptr);
  lv_obj_add_flag(forgetConfirmPopup, LV_OBJ_FLAG_HIDDEN);
}

void updateWifiStatus() {
  static wl_status_t lastStatus = WL_NO_SHIELD;
  wl_status_t status = WiFi.status();
  if (status == lastStatus) {
    return;
  }
  lastStatus = status;
  if (status == WL_CONNECTED) {
    String text = "WiFi: ";
    text += WiFi.localIP().toString();
    lv_label_set_text(wifiLabel, text.c_str());
    lv_label_set_text(statusLabel, "GoPro WiFi connected");
    lv_label_set_text(wifiIndicator, LV_SYMBOL_WIFI);
    lv_obj_set_style_text_color(wifiIndicator, lv_color_hex(0x47d16c), 0);
  } else if (status == WL_IDLE_STATUS) {
    lv_label_set_text(wifiLabel, "WiFi: connecting");
    lv_label_set_text(wifiIndicator, LV_SYMBOL_WIFI);
    lv_obj_set_style_text_color(wifiIndicator, lv_color_hex(0xf0b429), 0);
  } else {
    previewStreamRequested = false;
    snapshotPreviewPrepared = false;
    if (previewUdpListening) {
      previewUdp.stop();
      previewUdpListening = false;
    }
    lv_label_set_text(wifiLabel, "WiFi: disconnected");
    lv_label_set_text(wifiIndicator, LV_SYMBOL_WIFI);
    lv_obj_set_style_text_color(wifiIndicator, lv_color_hex(0x5a6472), 0);
  }
}

void updatePreview(bool force) {
  if (!displayOn) {
    if (force) {
      Serial.println("Preview skipped: display off");
    }
    return;
  }
  if (recording) {
    if (force) {
      Serial.println("Preview skipped: recording");
    }
    return;
  }
  if (!force && !isCaptureTileActive()) {
    return;
  }
  if (!force && millis() - lastPreviewUpdate < kPreviewRefreshMs) {
    return;
  }
  lastPreviewUpdate = millis();
  Serial.printf("Preview update force=%u wifi=%u\n", force ? 1 : 0, WiFi.status());

  if (previewHasImage) {
    lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    return;
  }

  if (WiFi.status() != WL_CONNECTED) {
    lv_label_set_text(previewLabel, "Connect WiFi for preview");
    if (force) {
      Serial.println("Preview skipped: WiFi not connected");
    }
    return;
  }

  lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
  lv_label_set_text(previewLabel, "Double-click lower for snapshot");
}

bool initPowerExpander() {
  if (!expander.begin(0x20, &Wire)) {
    Serial.println("XCA9554 expander not found");
    return false;
  }

  const uint8_t rails[] = {0, 1, 2, 6};
  for (uint8_t pin : rails) {
    expander.pinMode(pin, OUTPUT);
    expander.digitalWrite(pin, LOW);
  }
  delay(20);
  for (uint8_t pin : rails) {
    expander.digitalWrite(pin, HIGH);
  }
  delay(120);

  expander.pinMode(kExpanderActionButtonPin, INPUT);
  expander.pinMode(4, INPUT);
  return true;
}

void initPowerKey() {
  pmuOnline = power.begin(Wire, AXP2101_SLAVE_ADDRESS, IIC_SDA, IIC_SCL);
  if (!pmuOnline) {
    Serial.println("AXP2101 PMU not found; battery/shutdown disabled");
    return;
  }

  power.disableIRQ(XPOWERS_AXP2101_ALL_IRQ);
  power.clearIrqStatus();
  power.setPowerKeyPressOnTime(XPOWERS_POWERON_1S);
  power.setPowerKeyPressOffTime(XPOWERS_POWEROFF_4S);
  power.setLongPressPowerOFF();
  power.enableLongPressShutdown();
  power.enableIRQ(XPOWERS_AXP2101_PKEY_SHORT_IRQ);
  power.enableBattDetection();
  power.enableBattVoltageMeasure();
  power.enableVbusVoltageMeasure();
  Serial.println("AXP2101 PMU initialized; lower/action key IRQs enabled");
}

void handleBootButtonRelease(uint32_t durationMs) {
  if (durationMs < kActionButtonMinPressMs) {
    return;
  }
  if (pairingUiActive()) {
    Serial.println("Top button ignored during Pair New");
    return;
  }
  if (recording && durationMs < kBootLongPressMs) {
    Serial.println("Top button: hold to stop recording");
    setAction("Hold top button to stop recording");
    return;
  }
  Serial.println(recording ? "Top button: long stop recording" : "Top button: start recording");
  runRecordAction();
}

void handleLowerActionShortClick(const char *source) {
  if (pairingUiActive()) {
    requestPairingCancel();
    return;
  }
  if (!displayOn) {
    setDisplayOn(true);
    return;
  }
  if (exitFullscreenPreview(source)) {
    return;
  }

  actionButtonShortClickCount++;
  if (actionButtonShortClickCount >= 2 && millis() <= actionButtonShortClickDueMs) {
    actionButtonShortClickCount = 0;
    actionButtonShortClickDueMs = 0;
    if (!displayOn) {
      setDisplayOn(true);
      return;
    }
    if (recording) {
      setAction("Snapshot disabled while recording");
      return;
    }
    Serial.printf("%s double click: snapshot\n", source);
    runSnapshotAction();
  } else {
    actionButtonShortClickCount = 1;
    actionButtonShortClickDueMs = millis() + kActionButtonDoubleClickMs;
    Serial.printf("%s single click pending\n", source);
  }
}

void handleLowerActionLongPress(const char *source) {
  actionButtonShortClickCount = 0;
  actionButtonShortClickDueMs = 0;
  if (pairingUiActive()) {
    requestPairingCancel();
    return;
  }
  Serial.printf("%s long press: low-power shutdown\n", source);
  enterLowPowerShutdown();
}

void handleActionButtonRelease(uint32_t durationMs) {
  if (actionButtonLongHandled) {
    return;
  }
  if (durationMs < kActionButtonMinPressMs) {
    return;
  }
  if (millis() - lastPmuActionHandledMs < kPmuDuplicateSuppressMs) {
    Serial.println("Expander lower/action release ignored after PMU event");
    return;
  }
  lastExpanderActionHandledMs = millis();
  handleLowerActionShortClick("Lower button");
}

void handlePendingActionButtonClick() {
  if (actionButtonShortClickCount == 1 && actionButtonShortClickDueMs != 0 &&
      millis() >= actionButtonShortClickDueMs) {
    actionButtonShortClickCount = 0;
    actionButtonShortClickDueMs = 0;
    if (exitFullscreenPreview("Lower button")) {
      return;
    }
    Serial.println("Lower button single click: display toggle");
    setDisplayOn(!displayOn);
  }
}

void handleBootButton() {
  bool reading = digitalRead(kBootButtonPin);
  uint32_t now = millis();

  if (reading != bootLast) {
    bootLastChangeMs = now;
    bootLast = reading;
  }

  if ((now - bootLastChangeMs) < kButtonDebounceMs || reading == bootStable) {
    return;
  }

  bootStable = reading;
  if (bootStable == LOW) {
    bootPressedAtMs = now;
    if (!displayOn) {
      Serial.println("Top button press: display wake");
      setDisplayOn(true);
    }
  } else if (bootPressedAtMs != 0) {
    handleBootButtonRelease(now - bootPressedAtMs);
    bootPressedAtMs = 0;
  }
}

void handleExpanderActionButton() {
  if (!expanderOnline) {
    return;
  }

  bool reading = expander.digitalRead(kExpanderActionButtonPin);
  uint32_t now = millis();

  if (reading != actionButtonLast) {
    actionButtonLastChangeMs = now;
    actionButtonLast = reading;
  }

  if ((now - actionButtonLastChangeMs) < kActionButtonDebounceMs || reading == actionButtonStable) {
    return;
  }

  actionButtonStable = reading;
  if (actionButtonStable == kExpanderActionPressedLevel) {
    if (pairingUiActive()) {
      requestPairingCancel();
      return;
    }
    actionButtonPressedAtMs = now;
    actionButtonLongHandled = false;
  } else if (actionButtonPressedAtMs != 0) {
    handleActionButtonRelease(now - actionButtonPressedAtMs);
    actionButtonPressedAtMs = 0;
  }
}

void handleActionButtonHold() {
  if (!expanderOnline || actionButtonPressedAtMs == 0 || actionButtonLongHandled ||
      actionButtonStable != kExpanderActionPressedLevel) {
    return;
  }
  if (millis() - actionButtonPressedAtMs < kActionButtonLongPressMs) {
    return;
  }
  actionButtonLongHandled = true;
  if (millis() - lastPmuActionHandledMs < kPmuDuplicateSuppressMs) {
    Serial.println("Expander lower/action hold ignored after PMU event");
    return;
  }
  lastExpanderActionHandledMs = millis();
  handleLowerActionLongPress("Lower button");
}

void handlePmuActionButton() {
  if (!pmuOnline || millis() - lastPmuPollMs < kPmuPollMs) {
    return;
  }

  lastPmuPollMs = millis();
  power.getIrqStatus();
  bool shortPress = power.isPekeyShortPressIrq();
  bool longPress = power.isPekeyLongPressIrq();
  if (!shortPress && !longPress) {
    power.clearIrqStatus();
    return;
  }

  power.clearIrqStatus();
  if (longPress) {
    Serial.println("PMU lower/action long IRQ ignored; PMU handles hardware shutdown");
    return;
  }
  if (millis() - lastExpanderActionHandledMs < kPmuDuplicateSuppressMs) {
    Serial.println("PMU lower/action IRQ ignored after expander event");
    return;
  }
  if (shortPress) {
    lastPmuActionHandledMs = millis();
    handleLowerActionShortClick("Lower PMU button");
  }
}

void handleExpanderDiagnostics() {
  if (!expanderOnline) {
    return;
  }
  bool pin = expander.digitalRead(kExpanderActionButtonPin);
  if (pin != expanderActionPinLast) {
    expanderActionPinLast = pin;
    Serial.printf("Action pin p%u=%u\n", kExpanderActionButtonPin, pin);
    if (actionLabel) {
      char label[40];
      snprintf(label, sizeof(label), "Action p%u=%u", kExpanderActionButtonPin, pin);
      lv_label_set_text(actionLabel, label);
    }
  }
}

void handlePendingHomeAction() {
  PendingHomeAction action = pendingHomeAction;
  if (action == PendingHomeAction::None) {
    return;
  }
  if (goproActionBusy) {
    pendingHomeAction = PendingHomeAction::None;
    return;
  }
  if (millis() < pendingHomeActionDueMs) {
    return;
  }
  pendingHomeAction = PendingHomeAction::None;
  pendingHomeActionDueMs = 0;
  lv_timer_handler();
  switch (action) {
    case PendingHomeAction::Connect:
      Serial.println("Raw touch fallback: Connect");
      runConnectAction();
      break;
    case PendingHomeAction::Pair:
      Serial.println("Raw touch fallback: Pair");
      runPairNewAction();
      break;
    case PendingHomeAction::None:
      break;
  }
}

void handlePairingPopupTimeout() {
  if (pairingPopupHideDueMs != 0 && millis() >= pairingPopupHideDueMs) {
    hidePairingPopup();
  }
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("GoPro AMOLED UI boot");
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
  lv_indev_drv_register(&touchDriver);

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
