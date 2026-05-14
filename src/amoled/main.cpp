#include <Arduino.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <WiFi.h>

#include <Adafruit_XCA9554.h>
#include <ArduinoJson.h>
#include <Arduino_DriveBus_Library.h>
#include <Arduino_GFX_Library.h>
#include <JPEGDEC.h>
#include <lvgl.h>

#include "pin_config.h"
#include "esp_heap_caps.h"
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

#ifndef GOPRO_CAMERA_IP
#define GOPRO_CAMERA_IP "10.5.5.9"
#endif

namespace {
constexpr uint32_t kLvglTickMs = 2;
constexpr uint8_t kDisplayBrightness = 210;
constexpr uint32_t kPreviewRefreshMs = 2500;
constexpr uint32_t kHttpTimeoutMs = 6500;
constexpr size_t kMaxJpegBytes = 220 * 1024;
constexpr int kPreviewX = 20;
constexpr int kPreviewY = 76;
constexpr int kPreviewW = 328;
constexpr int kPreviewH = 150;

Adafruit_XCA9554 expander;
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

lv_obj_t *statusLabel = nullptr;
lv_obj_t *wifiLabel = nullptr;
lv_obj_t *cameraLabel = nullptr;
lv_obj_t *previewBox = nullptr;
lv_obj_t *previewLabel = nullptr;
lv_obj_t *actionLabel = nullptr;
lv_obj_t *batteryBar = nullptr;
lv_obj_t *modeRoller = nullptr;
uint32_t lastPreviewUpdate = 0;
bool recording = false;
String latestPreviewPath;
IPAddress cameraIp;
int jpegDrawX = kPreviewX;
int jpegDrawY = kPreviewY;

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
  lv_obj_set_style_radius(button, 14, 0);
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

void setAction(const char *message) {
  if (actionLabel) {
    lv_label_set_text(actionLabel, message);
  }
  Serial.println(message);
}

String cameraBaseUrl() {
  return String("http://") + cameraIp.toString() + ":8080";
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

bool connectConfiguredWifi() {
  const char *ssid = GOPRO_CAMERA_WIFI_SSID[0] ? GOPRO_CAMERA_WIFI_SSID : GOPRO_LOCAL_WIFI_SSID;
  const char *password = GOPRO_CAMERA_WIFI_SSID[0] ? GOPRO_CAMERA_WIFI_PASSWORD : GOPRO_LOCAL_WIFI_PASSWORD;
  if (!ssid || !ssid[0]) {
    setAction("No WiFi SSID configured");
    return false;
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  String label = "Joining ";
  label += ssid;
  lv_label_set_text(statusLabel, label.c_str());
  setAction(label.c_str());
  return true;
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
  lv_label_set_text(statusLabel, "BLE wake requested");
  setAction("Wake command placeholder: pair radio service next");
}

void onPair(lv_event_t *) {
  lv_label_set_text(statusLabel, "Pairing mode");
  lv_label_set_text(cameraLabel, "Camera: waiting for GoPro BLE");
  setAction("Pairing placeholder: open GoPro BLE pairing from radio module");
}

void onWifi(lv_event_t *) {
  connectConfiguredWifi();
}

void onRecord(lv_event_t *) {
  recording = !recording;
  lv_label_set_text(statusLabel, recording ? "Recording" : "Standby");
  if (recording) {
    lv_label_set_text(previewLabel, "Preview paused while recording");
    httpGetGoPro("/gopro/camera/shutter/start");
  } else {
    httpGetGoPro("/gopro/camera/shutter/stop");
  }
  setAction(recording ? "Recording; preview paused" : "Recording stopped");
}

void createUi() {
  lv_obj_t *screen = lv_scr_act();
  lv_obj_set_style_bg_color(screen, lv_color_hex(0x090b10), 0);
  lv_obj_set_style_text_color(screen, lv_color_hex(0xf4f7fb), 0);
  lv_obj_set_style_text_font(screen, &lv_font_montserrat_14, 0);

  lv_obj_t *title = lv_label_create(screen);
  lv_label_set_text(title, "GoPro Remote");
  lv_obj_set_style_text_font(title, &lv_font_montserrat_24, 0);
  lv_obj_align(title, LV_ALIGN_TOP_LEFT, 18, 14);

  statusLabel = lv_label_create(screen);
  lv_label_set_text(statusLabel, "Display online");
  lv_obj_set_style_text_color(statusLabel, lv_color_hex(0x96a2b4), 0);
  lv_obj_align(statusLabel, LV_ALIGN_TOP_LEFT, 20, 48);

  batteryBar = lv_bar_create(screen);
  lv_obj_set_size(batteryBar, 76, 9);
  lv_obj_align(batteryBar, LV_ALIGN_TOP_RIGHT, -20, 22);
  lv_bar_set_value(batteryBar, 74, LV_ANIM_OFF);
  lv_obj_set_style_bg_color(batteryBar, lv_color_hex(0x28303c), LV_PART_MAIN);
  lv_obj_set_style_bg_color(batteryBar, lv_color_hex(0x47d16c), LV_PART_INDICATOR);

  previewBox = lv_obj_create(screen);
  lv_obj_set_size(previewBox, kPreviewW, kPreviewH);
  lv_obj_align(previewBox, LV_ALIGN_TOP_MID, 0, 76);
  lv_obj_set_style_radius(previewBox, 18, 0);
  lv_obj_set_style_bg_color(previewBox, lv_color_hex(0x152033), 0);
  lv_obj_set_style_border_color(previewBox, lv_color_hex(0x2b3a52), 0);
  lv_obj_set_style_border_width(previewBox, 1, 0);
  lv_obj_clear_flag(previewBox, LV_OBJ_FLAG_SCROLLABLE);

  previewLabel = lv_label_create(previewBox);
  lv_label_set_text(previewLabel, "JPEG preview standby");
  lv_obj_set_style_text_color(previewLabel, lv_color_hex(0xdde7f5), 0);
  lv_obj_center(previewLabel);

  cameraLabel = lv_label_create(screen);
  lv_label_set_text(cameraLabel, "Camera: not paired");
  lv_obj_set_style_text_color(cameraLabel, lv_color_hex(0xc3ccd8), 0);
  lv_obj_align(cameraLabel, LV_ALIGN_TOP_LEFT, 20, 240);

  wifiLabel = lv_label_create(screen);
  lv_label_set_text(wifiLabel, "WiFi: idle");
  lv_obj_set_style_text_color(wifiLabel, lv_color_hex(0x96a2b4), 0);
  lv_obj_align(wifiLabel, LV_ALIGN_TOP_LEFT, 20, 262);

  modeRoller = lv_roller_create(screen);
  lv_roller_set_options(modeRoller, "Video\nPhoto\nTimeWarp\nPlayback\nSettings",
                        LV_ROLLER_MODE_NORMAL);
  lv_roller_set_visible_row_count(modeRoller, 3);
  lv_obj_set_size(modeRoller, 136, 86);
  lv_obj_align(modeRoller, LV_ALIGN_BOTTOM_LEFT, 18, -78);

  lv_obj_t *wake = makeButton(screen, "Wake", lv_color_hex(0x2c7be5));
  lv_obj_set_size(wake, 88, 48);
  lv_obj_align(wake, LV_ALIGN_BOTTOM_LEFT, 166, -116);
  lv_obj_add_event_cb(wake, onWake, LV_EVENT_CLICKED, nullptr);

  lv_obj_t *pair = makeButton(screen, "Pair", lv_color_hex(0x7c4dff));
  lv_obj_set_size(pair, 88, 48);
  lv_obj_align(pair, LV_ALIGN_BOTTOM_RIGHT, -20, -116);
  lv_obj_add_event_cb(pair, onPair, LV_EVENT_CLICKED, nullptr);

  lv_obj_t *wifi = makeButton(screen, "WiFi", lv_color_hex(0x009a88));
  lv_obj_set_size(wifi, 88, 48);
  lv_obj_align(wifi, LV_ALIGN_BOTTOM_LEFT, 166, -60);
  lv_obj_add_event_cb(wifi, onWifi, LV_EVENT_CLICKED, nullptr);

  lv_obj_t *rec = makeButton(screen, "REC", lv_color_hex(0xe03131));
  lv_obj_set_size(rec, 88, 48);
  lv_obj_align(rec, LV_ALIGN_BOTTOM_RIGHT, -20, -60);
  lv_obj_add_event_cb(rec, onRecord, LV_EVENT_CLICKED, nullptr);

  actionLabel = lv_label_create(screen);
  lv_label_set_text(actionLabel, "Touch controls ready");
  lv_obj_set_style_text_color(actionLabel, lv_color_hex(0x96a2b4), 0);
  lv_obj_align(actionLabel, LV_ALIGN_BOTTOM_MID, 0, -18);
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
    lv_label_set_text(statusLabel, "Local WiFi connected");
  } else if (status == WL_IDLE_STATUS) {
    lv_label_set_text(wifiLabel, "WiFi: connecting");
  } else {
    lv_label_set_text(wifiLabel, "WiFi: disconnected");
  }
}

void updatePreview() {
  if (recording || millis() - lastPreviewUpdate < kPreviewRefreshMs) {
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
  return true;
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("GoPro AMOLED UI boot");
  cameraIp.fromString(GOPRO_CAMERA_IP);

  Wire.begin(IIC_SDA, IIC_SCL);
  Wire.setClock(400000);
  initPowerExpander();

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
  Serial.println("AMOLED UI ready");
}

void loop() {
  lv_timer_handler();
  updateWifiStatus();
  updatePreview();
  delay(5);
}
