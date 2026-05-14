#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEScan.h>
#include <HTTPClient.h>
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

namespace {
constexpr uint32_t kLvglTickMs = 2;
constexpr uint8_t kDisplayBrightness = 210;
constexpr uint32_t kPreviewRefreshMs = 2500;
constexpr uint32_t kHttpTimeoutMs = 6500;
constexpr uint32_t kButtonDebounceMs = 35;
constexpr uint32_t kBootLongPressMs = 1200;
constexpr uint32_t kPmuPollMs = 150;
constexpr uint32_t kBatteryRefreshMs = 5000;
constexpr uint32_t kBleScanSeconds = 7;
constexpr uint32_t kWifiTimeoutMs = 25000;
constexpr size_t kMaxJpegBytes = 220 * 1024;
constexpr int kPreviewX = 20;
constexpr int kPreviewY = 76;
constexpr int kPreviewW = 328;
constexpr int kPreviewH = 150;
constexpr int kBootButtonPin = 0;

const BLEUUID kControlService("0000fea6-0000-1000-8000-00805f9b34fb");
const BLEUUID kWifiService("b5f90001-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kCameraManagementService("b5f90090-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kWifiSsid("b5f90002-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kWifiPassword("b5f90003-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kCommand("b5f90072-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kCommandResponse("b5f90073-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kCameraManagementCommand("b5f90091-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kCameraManagementResponse("b5f90092-aa8d-11e3-9046-0002a5d5c51b");

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

lv_obj_t *statusLabel = nullptr;
lv_obj_t *wifiLabel = nullptr;
lv_obj_t *cameraLabel = nullptr;
lv_obj_t *previewBox = nullptr;
lv_obj_t *previewLabel = nullptr;
lv_obj_t *actionLabel = nullptr;
lv_obj_t *batteryBar = nullptr;
lv_obj_t *batteryLabel = nullptr;
lv_obj_t *wifiIndicator = nullptr;
lv_obj_t *tileView = nullptr;
lv_obj_t *captureModeLabel = nullptr;
lv_obj_t *captureSettingLabel = nullptr;
lv_obj_t *recordPill = nullptr;
uint32_t lastPreviewUpdate = 0;
uint32_t lastPmuPollMs = 0;
uint32_t lastBatteryUpdate = 0;
bool recording = false;
bool displayOn = true;
bool pmuOnline = false;
bool bleConnected = false;
String latestPreviewPath;
String lastBleName;
String goProSsid;
String goProPassword;
String captureMode = "Video";
String captureSetting = "16:9 | 4K | 60 | W";
IPAddress cameraIp;
int jpegDrawX = kPreviewX;
int jpegDrawY = kPreviewY;
bool bootLast = HIGH;
bool bootStable = HIGH;
uint32_t bootLastChangeMs = 0;
uint32_t bootPressedAtMs = 0;

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
  if (touch->IIC_Interrupt_Flag) {
    touch->IIC_Interrupt_Flag = false;
    data->state = LV_INDEV_STATE_PR;
    data->point.x = touch->IIC_Read_Device_Value(
        Arduino_IIC_Touch::Value_Information::TOUCH_COORDINATE_X);
    data->point.y = touch->IIC_Read_Device_Value(
        Arduino_IIC_Touch::Value_Information::TOUCH_COORDINATE_Y);
  } else {
    data->state = LV_INDEV_STATE_REL;
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

lv_obj_t *makeButton(lv_obj_t *parent, const char *text, lv_color_t color) {
  lv_obj_t *button = lv_btn_create(parent);
  styleButton(button, color);
  lv_obj_t *label = lv_label_create(button);
  lv_label_set_text(label, text);
  lv_obj_center(label);
  return button;
}

lv_obj_t *makeChip(lv_obj_t *parent, const char *text, int x, int y, int w, lv_color_t color) {
  lv_obj_t *chip = makeButton(parent, text, color);
  lv_obj_set_size(chip, w, 34);
  lv_obj_set_pos(chip, x, y);
  return chip;
}

void setAction(const char *message) {
  if (actionLabel) {
    lv_label_set_text(actionLabel, message);
  }
  Serial.println(message);
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
  if (!batteryBar || !batteryLabel || (!force && millis() - lastBatteryUpdate < kBatteryRefreshMs)) {
    return;
  }
  lastBatteryUpdate = millis();

  if (!pmuOnline) {
    lv_bar_set_value(batteryBar, 0, LV_ANIM_OFF);
    lv_obj_set_style_bg_color(batteryBar, lv_color_hex(0x5a6472), LV_PART_INDICATOR);
    lv_label_set_text(batteryLabel, "--%");
    return;
  }

  int percent = power.getBatteryPercent();
  if (percent < 0) {
    lv_bar_set_value(batteryBar, 0, LV_ANIM_OFF);
    lv_obj_set_style_bg_color(batteryBar, lv_color_hex(0x5a6472), LV_PART_INDICATOR);
    lv_label_set_text(batteryLabel, power.isVbusIn() ? "USB" : "--%");
    return;
  }

  percent = constrain(percent, 0, 100);
  lv_bar_set_value(batteryBar, percent, LV_ANIM_OFF);
  if (percent <= 15) {
    lv_obj_set_style_bg_color(batteryBar, lv_color_hex(0xf03e3e), LV_PART_INDICATOR);
  } else if (percent <= 35) {
    lv_obj_set_style_bg_color(batteryBar, lv_color_hex(0xf0b429), LV_PART_INDICATOR);
  } else {
    lv_obj_set_style_bg_color(batteryBar, lv_color_hex(0x47d16c), LV_PART_INDICATOR);
  }

  char text[8];
  snprintf(text, sizeof(text), "%d%%", percent);
  lv_label_set_text(batteryLabel, text);
}

void enterLowPowerShutdown() {
  recording = false;
  WiFi.disconnect(true, true);
  WiFi.mode(WIFI_OFF);

  if (statusLabel) {
    lv_label_set_text(statusLabel, "Powering off");
  }
  if (actionLabel) {
    lv_label_set_text(actionLabel, "Hold PWR to wake");
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
}

class ScanCallbacks : public BLEAdvertisedDeviceCallbacks {
 public:
  void onResult(BLEAdvertisedDevice device) override {
    String name = device.haveName() ? String(device.getName().c_str()) : "";
    bool hasControlService = device.haveServiceUUID() && device.isAdvertisingService(kControlService);

    if (!hasControlService && !nameMatchesFilter(name)) {
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
  delete bestBleDevice;
  bestBleDevice = nullptr;

  lv_label_set_text(statusLabel, "Scanning BLE");
  setAction("Scanning for GoPro BLE");

  BLEScan *scan = BLEDevice::getScan();
  ScanCallbacks callbacks;
  scan->setAdvertisedDeviceCallbacks(&callbacks, false);
  scan->setActiveScan(true);
  scan->setInterval(100);
  scan->setWindow(99);
  scan->start(kBleScanSeconds, false);
  scan->clearResults();

  if (bestBleDevice == nullptr) {
    lv_label_set_text(cameraLabel, "Camera: BLE not found");
    setAction("No GoPro BLE device found");
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
  if (bleConnected && bleClient != nullptr && bleClient->isConnected()) {
    return true;
  }

  if (bestBleDevice == nullptr && !scanForCamera()) {
    return false;
  }

  if (bleClient == nullptr) {
    bleClient = BLEDevice::createClient();
  }

  lv_label_set_text(statusLabel, "Connecting BLE");
  setAction("Connecting GoPro BLE");
  if (!bleClient->connect(bestBleDevice)) {
    bleConnected = false;
    lv_label_set_text(cameraLabel, "Camera: BLE connect failed");
    setAction("BLE connect failed");
    return false;
  }

  bleConnected = true;
  BLERemoteService *control = bleClient->getService(kControlService);
  if (control != nullptr) {
    BLERemoteCharacteristic *response = control->getCharacteristic(kCommandResponse);
    if (response != nullptr && response->canNotify()) {
      response->registerForNotify(commandResponseNotify);
    }
  }

  lv_label_set_text(statusLabel, "BLE connected");
  setAction("BLE connected");
  return true;
}

bool readGoProWifiCredentials() {
  if (!connectBle()) {
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

  Serial.print(F("GoPro AP SSID: "));
  Serial.println(goProSsid);
  Serial.print(F("GoPro AP password length: "));
  Serial.println(goProPassword.length());

  if (goProSsid.isEmpty() || goProPassword.isEmpty()) {
    setAction("GoPro WiFi credentials empty");
    return false;
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

  command->writeValue(const_cast<uint8_t *>(payload), length, true);
  delay(300);
  return true;
}

bool sendCameraManagementCommand(const uint8_t *payload, size_t length) {
  if (!connectBle()) {
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

  command->writeValue(const_cast<uint8_t *>(payload), length, true);
  delay(500);
  return true;
}

bool pairGoPro() {
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
  setAction("Pairing with GoPro BLE");
  return sendCameraManagementCommand(request, sizeof(request));
}

bool enableGoProWifiAp() {
  const uint8_t enableWifi[] = {0x03, 0x17, 0x01, 0x01};
  lv_label_set_text(statusLabel, "Enabling GoPro AP");
  setAction("Enabling GoPro WiFi AP over BLE");
  return sendBleCommand(enableWifi, sizeof(enableWifi));
}

bool connectGoProWifiFromBle() {
  if (goProSsid.isEmpty() && !readGoProWifiCredentials()) {
    return false;
  }
  if (!enableGoProWifiAp()) {
    return false;
  }

  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true, true);
  delay(250);
  WiFi.begin(goProSsid.c_str(), goProPassword.c_str());

  String label = "Joining ";
  label += goProSsid;
  lv_label_set_text(statusLabel, label.c_str());
  setAction(label.c_str());

  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < kWifiTimeoutMs) {
    lv_timer_handler();
    delay(100);
  }

  if (WiFi.status() != WL_CONNECTED) {
    lv_label_set_text(wifiLabel, "WiFi: GoPro AP failed");
    setAction("GoPro WiFi connect failed");
    return false;
  }

  String text = "WiFi: ";
  text += WiFi.localIP().toString();
  lv_label_set_text(wifiLabel, text.c_str());
  lv_label_set_text(statusLabel, "GoPro WiFi connected");
  setAction("Connected to GoPro WiFi");
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

bool setGoProSetting(uint16_t settingId, uint16_t optionId, const char *label) {
  String path = "/gopro/camera/setting?setting=";
  path += settingId;
  path += "&option=";
  path += optionId;
  bool ok = httpGetGoPro(path);
  setAction(ok ? label : "Setting command failed");
  return ok;
}

void setPairingMode() {
  if (!displayOn) {
    setDisplayOn(true);
  }
  bool ok = pairGoPro();
  setAction(ok ? "GoPro BLE pairing requested" : "GoPro BLE pairing failed");
}

void toggleRecording() {
  if (!displayOn) {
    setDisplayOn(true);
  }
  recording = !recording;
  lv_label_set_text(statusLabel, recording ? "Recording" : "Standby");
  if (recording) {
    lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    lv_label_set_text(previewLabel, "Preview paused while recording");
    httpGetGoPro("/gopro/camera/shutter/start");
  } else {
    httpGetGoPro("/gopro/camera/shutter/stop");
  }
  setAction(recording ? "Recording; preview paused" : "Recording stopped");
}

bool getLatestJpegPath(String &path) {
  path = "";
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  HTTPClient http;
  http.setTimeout(kHttpTimeoutMs);
  String url = cameraBaseUrl() + "/gopro/media/list";
  if (!http.begin(url)) {
    return false;
  }

  int status = http.GET();
  if (status < 200 || status >= 300) {
    http.end();
    Serial.printf("media/list failed: %d\n", status);
    return false;
  }

  String body = http.getString();
  http.end();

  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, body);
  if (error) {
    Serial.printf("media/list JSON parse failed: %s\n", error.c_str());
    return false;
  }

  uint32_t newest = 0;
  for (JsonObject directory : doc["media"].as<JsonArray>()) {
    const char *dir = directory["d"] | "";
    for (JsonObject file : directory["fs"].as<JsonArray>()) {
      const char *name = file["n"] | "";
      String lower = name;
      lower.toLowerCase();
      if (!lower.endsWith(".jpg")) {
        continue;
      }

      uint32_t modified = file["mod"] | file["cre"] | 0;
      if (path.isEmpty() || modified >= newest) {
        newest = modified;
        path = String(dir) + "/" + name;
      }
    }
  }
  return !path.isEmpty();
}

uint8_t *fetchGoProThumbnail(const String &path, size_t &length) {
  length = 0;
  HTTPClient http;
  http.setTimeout(kHttpTimeoutMs);
  String url = cameraBaseUrl() + "/gopro/media/thumbnail?path=" + path;
  if (!http.begin(url)) {
    return nullptr;
  }

  int status = http.GET();
  if (status < 200 || status >= 300) {
    http.end();
    Serial.printf("thumbnail failed: %d\n", status);
    return nullptr;
  }

  int expected = http.getSize();
  if (expected <= 0 || static_cast<size_t>(expected) > kMaxJpegBytes) {
    http.end();
    Serial.printf("thumbnail size rejected: %d\n", expected);
    return nullptr;
  }

  uint8_t *buffer = static_cast<uint8_t *>(
      heap_caps_malloc(expected, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  if (!buffer) {
    buffer = static_cast<uint8_t *>(heap_caps_malloc(expected, MALLOC_CAP_8BIT));
  }
  if (!buffer) {
    http.end();
    setAction("No RAM for JPEG");
    return nullptr;
  }

  WiFiClient *stream = http.getStreamPtr();
  size_t offset = 0;
  uint32_t start = millis();
  while (offset < static_cast<size_t>(expected) && millis() - start < kHttpTimeoutMs) {
    int available = stream->available();
    if (available <= 0) {
      delay(2);
      continue;
    }
    int readLen = stream->readBytes(buffer + offset,
                                    min(available, expected - static_cast<int>(offset)));
    if (readLen > 0) {
      offset += readLen;
    }
  }
  http.end();

  if (offset == 0) {
    free(buffer);
    return nullptr;
  }
  length = offset;
  return buffer;
}

int drawJpegBlock(JPEGDRAW *draw) {
  int x = jpegDrawX + draw->x;
  int y = jpegDrawY + draw->y;
  int w = draw->iWidthUsed > 0 ? draw->iWidthUsed : draw->iWidth;
  int h = draw->iHeight;
  if (x >= kPreviewX + kPreviewW || y >= kPreviewY + kPreviewH) {
    return 1;
  }
  if (x + w > kPreviewX + kPreviewW) {
    w = kPreviewX + kPreviewW - x;
  }
  if (y + h > kPreviewY + kPreviewH) {
    h = kPreviewY + kPreviewH - y;
  }
  if (w > 0 && h > 0) {
    gfx->draw16bitRGBBitmap(x, y, draw->pPixels, w, h);
  }
  return 1;
}

bool drawJpegPreview(uint8_t *buffer, size_t length) {
  if (!jpeg.openRAM(buffer, static_cast<int>(length), drawJpegBlock)) {
    return false;
  }

  int scale = 0;
  if (jpeg.getWidth() > kPreviewW * 4 || jpeg.getHeight() > kPreviewH * 4) {
    scale = JPEG_SCALE_EIGHTH;
  } else if (jpeg.getWidth() > kPreviewW * 2 || jpeg.getHeight() > kPreviewH * 2) {
    scale = JPEG_SCALE_QUARTER;
  } else if (jpeg.getWidth() > kPreviewW || jpeg.getHeight() > kPreviewH) {
    scale = JPEG_SCALE_HALF;
  }

  int outW = scale == JPEG_SCALE_EIGHTH ? jpeg.getWidth() / 8
             : scale == JPEG_SCALE_QUARTER ? jpeg.getWidth() / 4
             : scale == JPEG_SCALE_HALF ? jpeg.getWidth() / 2
             : jpeg.getWidth();
  int outH = scale == JPEG_SCALE_EIGHTH ? jpeg.getHeight() / 8
             : scale == JPEG_SCALE_QUARTER ? jpeg.getHeight() / 4
             : scale == JPEG_SCALE_HALF ? jpeg.getHeight() / 2
             : jpeg.getHeight();
  jpegDrawX = kPreviewX + max(0, (kPreviewW - outW) / 2);
  jpegDrawY = kPreviewY + max(0, (kPreviewH - outH) / 2);

  gfx->fillRect(kPreviewX, kPreviewY, kPreviewW, kPreviewH, 0x0000);
  jpeg.setPixelType(RGB565_LITTLE_ENDIAN);
  bool ok = jpeg.decode(0, 0, scale) != 0;
  jpeg.close();
  return ok;
}

void onWake(lv_event_t *) {
  connectGoProWifiFromBle();
}

void onPair(lv_event_t *) {
  setPairingMode();
}

void onWifi(lv_event_t *) {
  connectGoProWifiFromBle();
}

void onRecord(lv_event_t *) {
  toggleRecording();
}

void selectMode(const char *mode, const char *setting, const char *endpoint) {
  captureMode = mode;
  captureSetting = setting;
  if (captureModeLabel) {
    lv_label_set_text(captureModeLabel, captureMode.c_str());
  }
  if (captureSettingLabel) {
    lv_label_set_text(captureSettingLabel, captureSetting.c_str());
  }
  lv_label_set_text(statusLabel, captureMode.c_str());
  if (WiFi.status() == WL_CONNECTED && endpoint && endpoint[0]) {
    httpGetGoPro(endpoint);
  }
  setAction(captureSetting.c_str());
}

void onModeVideo(lv_event_t *) {
  selectMode("Video", "16:9 | 4K | 60 | W", "");
}

void onModePhoto(lv_event_t *) {
  selectMode("Photo", "8:7 | 27MP | Wide", "");
}

void onModeTimeWarp(lv_event_t *) {
  selectMode("TimeWarp", "16:9 | 4K | Auto", "");
}

void onDashboardConnect(lv_event_t *) {
  connectGoProWifiFromBle();
}

void onSettingSync(lv_event_t *) {
  httpGetGoPro("/gopro/camera/state");
}

void onPresetSync(lv_event_t *) {
  httpGetGoPro("/gopro/camera/presets/get?include-hidden=1");
}

void onSettingPlaceholder(lv_event_t *event) {
  const char *label = static_cast<const char *>(lv_event_get_user_data(event));
  String message = "Select ";
  message += label ? label : "setting";
  message += " after camera state sync";
  setAction(message.c_str());
}

lv_obj_t *makePanelLabel(lv_obj_t *parent, const char *text, int x, int y, int size = 14,
                         lv_color_t color = lv_color_hex(0xf4f7fb)) {
  lv_obj_t *label = lv_label_create(parent);
  lv_label_set_text(label, text);
  lv_obj_set_style_text_font(label, size >= 18 ? &lv_font_montserrat_18 : &lv_font_montserrat_14, 0);
  lv_obj_set_style_text_color(label, color, 0);
  lv_obj_set_pos(label, x, y);
  return label;
}

void createUi() {
  lv_obj_t *screen = lv_scr_act();
  lv_obj_set_style_bg_color(screen, lv_color_hex(0x090b10), 0);
  lv_obj_set_style_text_color(screen, lv_color_hex(0xf4f7fb), 0);
  lv_obj_set_style_text_font(screen, &lv_font_montserrat_14, 0);

  lv_obj_t *title = lv_label_create(screen);
  lv_label_set_text(title, "GoPro");
  lv_obj_set_style_text_font(title, &lv_font_montserrat_24, 0);
  lv_obj_align(title, LV_ALIGN_TOP_LEFT, 18, 14);

  statusLabel = lv_label_create(screen);
  lv_label_set_text(statusLabel, "Ready");
  lv_obj_set_style_text_color(statusLabel, lv_color_hex(0x96a2b4), 0);
  lv_obj_align(statusLabel, LV_ALIGN_TOP_LEFT, 20, 48);

  batteryBar = lv_bar_create(screen);
  lv_obj_set_size(batteryBar, 52, 9);
  lv_obj_align(batteryBar, LV_ALIGN_TOP_RIGHT, -64, 24);
  lv_bar_set_range(batteryBar, 0, 100);
  lv_bar_set_value(batteryBar, 0, LV_ANIM_OFF);
  lv_obj_set_style_bg_color(batteryBar, lv_color_hex(0x28303c), LV_PART_MAIN);
  lv_obj_set_style_bg_color(batteryBar, lv_color_hex(0x47d16c), LV_PART_INDICATOR);

  batteryLabel = lv_label_create(screen);
  lv_label_set_text(batteryLabel, "--%");
  lv_obj_set_style_text_color(batteryLabel, lv_color_hex(0xc3ccd8), 0);
  lv_obj_align(batteryLabel, LV_ALIGN_TOP_RIGHT, -20, 18);

  wifiIndicator = lv_label_create(screen);
  lv_label_set_text(wifiIndicator, "WIFI --");
  lv_obj_set_style_text_color(wifiIndicator, lv_color_hex(0x5a6472), 0);
  lv_obj_align(wifiIndicator, LV_ALIGN_TOP_RIGHT, -20, 38);

  tileView = lv_tileview_create(screen);
  lv_obj_set_size(tileView, LCD_WIDTH, LCD_HEIGHT - 70);
  lv_obj_align(tileView, LV_ALIGN_BOTTOM_MID, 0, 0);
  lv_obj_set_style_bg_color(tileView, lv_color_hex(0x090b10), 0);
  lv_obj_set_style_border_width(tileView, 0, 0);
  lv_obj_set_style_pad_all(tileView, 0, 0);
  lv_obj_clear_flag(tileView, LV_OBJ_FLAG_SCROLL_ELASTIC);
  lv_obj_set_scrollbar_mode(tileView, LV_SCROLLBAR_MODE_OFF);

  lv_obj_t *captureTile = lv_tileview_add_tile(tileView, 0, 0, LV_DIR_RIGHT);
  lv_obj_set_style_bg_color(captureTile, lv_color_hex(0x090b10), 0);

  previewBox = lv_obj_create(captureTile);
  lv_obj_set_size(previewBox, kPreviewW, kPreviewH);
  lv_obj_set_pos(previewBox, kPreviewX, 6);
  lv_obj_set_style_radius(previewBox, 8, 0);
  lv_obj_set_style_bg_color(previewBox, lv_color_hex(0x101827), 0);
  lv_obj_set_style_border_color(previewBox, lv_color_hex(0x2b3a52), 0);
  lv_obj_set_style_border_width(previewBox, 1, 0);
  lv_obj_clear_flag(previewBox, LV_OBJ_FLAG_SCROLLABLE);

  previewLabel = lv_label_create(previewBox);
  lv_label_set_text(previewLabel, "JPEG preview standby");
  lv_obj_set_style_text_color(previewLabel, lv_color_hex(0xdde7f5), 0);
  lv_obj_center(previewLabel);

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

  makePanelLabel(captureTile, "9H:59", 22, 14, 18, lv_color_hex(0xf4f7fb));
  captureModeLabel = makePanelLabel(captureTile, captureMode.c_str(), 22, 170, 18);
  captureSettingLabel = makePanelLabel(captureTile, captureSetting.c_str(), 22, 194, 14,
                                       lv_color_hex(0xc3ccd8));

  cameraLabel = lv_label_create(captureTile);
  lv_label_set_text(cameraLabel, "Camera: not paired");
  lv_obj_set_style_text_color(cameraLabel, lv_color_hex(0xc3ccd8), 0);
  lv_obj_set_pos(cameraLabel, 20, 224);

  wifiLabel = lv_label_create(captureTile);
  lv_label_set_text(wifiLabel, "WiFi: idle");
  lv_obj_set_style_text_color(wifiLabel, lv_color_hex(0x96a2b4), 0);
  lv_obj_set_pos(wifiLabel, 20, 246);

  lv_obj_t *connect = makeChip(captureTile, "Connect", 20, 284, 96, lv_color_hex(0x2c7be5));
  lv_obj_add_event_cb(connect, onWifi, LV_EVENT_CLICKED, nullptr);
  lv_obj_t *rec = makeChip(captureTile, "REC", 252, 284, 96, lv_color_hex(0xe03131));
  lv_obj_add_event_cb(rec, onRecord, LV_EVENT_CLICKED, nullptr);

  actionLabel = lv_label_create(captureTile);
  lv_label_set_text(actionLabel, "Swipe for modes and settings");
  lv_obj_set_style_text_color(actionLabel, lv_color_hex(0x96a2b4), 0);
  lv_obj_align(actionLabel, LV_ALIGN_BOTTOM_MID, 0, -20);

  lv_obj_t *modeTile = lv_tileview_add_tile(tileView, 1, 0, LV_DIR_LEFT | LV_DIR_RIGHT);
  lv_obj_set_style_bg_color(modeTile, lv_color_hex(0x090b10), 0);
  makePanelLabel(modeTile, "Modes", 20, 18, 18);
  makePanelLabel(modeTile, "Swipe left/right like the GoPro rear screen", 20, 44, 14,
                 lv_color_hex(0x96a2b4));
  lv_obj_t *video = makeChip(modeTile, "Video", 20, 84, 328, lv_color_hex(0x2c7be5));
  lv_obj_add_event_cb(video, onModeVideo, LV_EVENT_CLICKED, nullptr);
  lv_obj_t *photo = makeChip(modeTile, "Photo", 20, 132, 328, lv_color_hex(0x009a88));
  lv_obj_add_event_cb(photo, onModePhoto, LV_EVENT_CLICKED, nullptr);
  lv_obj_t *timeWarp = makeChip(modeTile, "TimeWarp", 20, 180, 328, lv_color_hex(0x7c4dff));
  lv_obj_add_event_cb(timeWarp, onModeTimeWarp, LV_EVENT_CLICKED, nullptr);
  makePanelLabel(modeTile, "Main overlay shows mode, aspect, resolution, fps, lens", 20, 242, 14,
                 lv_color_hex(0xc3ccd8));

  lv_obj_t *captureSettingsTile = lv_tileview_add_tile(tileView, 2, 0, LV_DIR_LEFT | LV_DIR_RIGHT);
  lv_obj_set_style_bg_color(captureSettingsTile, lv_color_hex(0x090b10), 0);
  makePanelLabel(captureSettingsTile, "Capture Settings", 20, 18, 18);
  makePanelLabel(captureSettingsTile, "Resolution, frame rate, lens, and aspect", 20, 44, 14,
                 lv_color_hex(0x96a2b4));
  const char *captureSettings[] = {"Aspect Ratio", "Resolution", "Frame Rate", "Digital Lens",
                                   "HyperSmooth", "Scheduled Capture", "Duration", "HindSight"};
  for (int i = 0; i < 8; ++i) {
    int x = 20 + (i % 2) * 168;
    int y = 82 + (i / 2) * 48;
    lv_obj_t *button = makeChip(captureSettingsTile, captureSettings[i], x, y, 156,
                                lv_color_hex(0x1b2638));
    lv_obj_add_event_cb(button, onSettingPlaceholder, LV_EVENT_CLICKED,
                        const_cast<char *>(captureSettings[i]));
  }
  lv_obj_t *syncState = makeChip(captureSettingsTile, "Sync State", 20, 288, 156,
                                 lv_color_hex(0x2c7be5));
  lv_obj_add_event_cb(syncState, onSettingSync, LV_EVENT_CLICKED, nullptr);
  lv_obj_t *syncPresets = makeChip(captureSettingsTile, "Sync Presets", 192, 288, 156,
                                   lv_color_hex(0x2c7be5));
  lv_obj_add_event_cb(syncPresets, onPresetSync, LV_EVENT_CLICKED, nullptr);

  lv_obj_t *protuneTile = lv_tileview_add_tile(tileView, 3, 0, LV_DIR_LEFT | LV_DIR_RIGHT);
  lv_obj_set_style_bg_color(protuneTile, lv_color_hex(0x090b10), 0);
  makePanelLabel(protuneTile, "Pro Controls", 20, 18, 18);
  makePanelLabel(protuneTile, "Advanced settings exposed by Open GoPro", 20, 44, 14,
                 lv_color_hex(0x96a2b4));
  const char *protune[] = {"Bit Depth", "Bit Rate", "Shutter", "EV Comp", "White Balance",
                           "ISO Min", "ISO Max", "Sharpness", "Color", "Audio", "RAW Audio",
                           "Wind"};
  for (int i = 0; i < 12; ++i) {
    int x = 20 + (i % 2) * 168;
    int y = 82 + (i / 2) * 40;
    lv_obj_t *button = makeChip(protuneTile, protune[i], x, y, 156, lv_color_hex(0x1b2638));
    lv_obj_add_event_cb(button, onSettingPlaceholder, LV_EVENT_CLICKED,
                        const_cast<char *>(protune[i]));
  }

  lv_obj_t *dashboardTile = lv_tileview_add_tile(tileView, 4, 0, LV_DIR_LEFT);
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
  makePanelLabel(dashboardTile, "PWR short: display off/on", 20, 206, 14, lv_color_hex(0xc3ccd8));
  makePanelLabel(dashboardTile, "PWR long: PMU shutdown", 20, 230, 14, lv_color_hex(0xc3ccd8));
  makePanelLabel(dashboardTile, "BOOT short: record", 20, 254, 14, lv_color_hex(0xc3ccd8));
  makePanelLabel(dashboardTile, "BOOT long: pair", 20, 278, 14, lv_color_hex(0xc3ccd8));
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
    lv_label_set_text(wifiIndicator, "WIFI ON");
    lv_obj_set_style_text_color(wifiIndicator, lv_color_hex(0x47d16c), 0);
  } else if (status == WL_IDLE_STATUS) {
    lv_label_set_text(wifiLabel, "WiFi: connecting");
    lv_label_set_text(wifiIndicator, "WIFI ..");
    lv_obj_set_style_text_color(wifiIndicator, lv_color_hex(0xf0b429), 0);
  } else {
    lv_label_set_text(wifiLabel, "WiFi: disconnected");
    lv_label_set_text(wifiIndicator, "WIFI --");
    lv_obj_set_style_text_color(wifiIndicator, lv_color_hex(0x5a6472), 0);
  }
}

void updatePreview() {
  if (!displayOn || recording || millis() - lastPreviewUpdate < kPreviewRefreshMs) {
    return;
  }
  lastPreviewUpdate = millis();

  if (WiFi.status() != WL_CONNECTED) {
    lv_label_set_text(previewLabel, "Connect WiFi for JPEG preview");
    return;
  }

  String path;
  if (!getLatestJpegPath(path)) {
    lv_label_set_text(previewLabel, "No GoPro JPEG media found");
    return;
  }
  latestPreviewPath = path;

  size_t jpegLength = 0;
  uint8_t *jpegData = fetchGoProThumbnail(path, jpegLength);
  if (!jpegData) {
    lv_label_set_text(previewLabel, "JPEG fetch failed");
    return;
  }

  lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
  bool ok = drawJpegPreview(jpegData, jpegLength);
  free(jpegData);
  if (!ok) {
    lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    lv_label_set_text(previewLabel, "JPEG decode failed");
    return;
  }

  String label = "JPEG: ";
  label += latestPreviewPath;
  lv_label_set_text(statusLabel, label.c_str());
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

  expander.pinMode(4, INPUT);
  expander.pinMode(5, INPUT);
  return true;
}

void initPowerKey() {
  pmuOnline = power.begin(Wire, AXP2101_SLAVE_ADDRESS, IIC_SDA, IIC_SCL);
  if (!pmuOnline) {
    Serial.println("AXP2101 PMU not found; PWR button disabled");
    return;
  }

  power.disableIRQ(XPOWERS_AXP2101_ALL_IRQ);
  power.clearIrqStatus();
  power.setPowerKeyPressOnTime(XPOWERS_POWERON_1S);
  power.setPowerKeyPressOffTime(XPOWERS_POWEROFF_4S);
  power.setLongPressPowerOFF();
  power.enableBattDetection();
  power.enableBattVoltageMeasure();
  power.enableVbusVoltageMeasure();
  power.enableIRQ(XPOWERS_AXP2101_PKEY_SHORT_IRQ | XPOWERS_AXP2101_PKEY_LONG_IRQ);
  Serial.println("AXP2101 PWR button enabled");
}

void handleBootButtonRelease(uint32_t durationMs) {
  if (durationMs >= kBootLongPressMs) {
    setPairingMode();
  } else {
    toggleRecording();
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
  } else if (bootPressedAtMs != 0) {
    handleBootButtonRelease(now - bootPressedAtMs);
    bootPressedAtMs = 0;
  }
}

void handlePowerButton() {
  uint32_t now = millis();
  if (!pmuOnline || now - lastPmuPollMs < kPmuPollMs) {
    return;
  }
  lastPmuPollMs = now;

  power.getIrqStatus();
  if (power.isPekeyLongPressIrq()) {
    power.clearIrqStatus();
    enterLowPowerShutdown();
    return;
  }
  if (power.isPekeyShortPressIrq()) {
    setDisplayOn(!displayOn);
  }
  power.clearIrqStatus();
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("GoPro AMOLED UI boot");
  cameraIp.fromString(GOPRO_CAMERA_IP);
  BLEDevice::init("ESP32-GoPro-Remote");

  Wire.begin(IIC_SDA, IIC_SCL);
  Wire.setClock(400000);
  initPowerExpander();
  initPowerKey();

  pinMode(kBootButtonPin, INPUT_PULLUP);
  bootLast = digitalRead(kBootButtonPin);
  bootStable = bootLast;

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
  const uint32_t pixels = LCD_WIDTH * 48;
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
}

void loop() {
  lv_timer_handler();
  handleBootButton();
  handlePowerButton();
  updateBatteryStatus();
  updateWifiStatus();
  updatePreview();
  delay(5);
}
