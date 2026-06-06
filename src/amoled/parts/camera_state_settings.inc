#pragma once

#include <Arduino.h>
#include <ArduinoJson.h>
#include <lvgl.h>

#include <ctype.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

#if !defined(GOPRO_AMOLED_MAIN_CONTEXT)
#include "amoled_context_decls.h"
#endif

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
  const char *name =
      object["display_name"] | object["displayName"] | object["name"] | nullptr;
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
               (object["display_name"].is<const char *>() ||
                object["name"].is<const char *>())) {
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

bool jsonVariantToInt(JsonVariantConst value, int32_t &out) {
  if (value.isNull()) {
    return false;
  }
  if (value.is<int32_t>()) {
    out = value.as<int32_t>();
    return true;
  }
  if (value.is<bool>()) {
    out = value.as<bool>() ? 1 : 0;
    return true;
  }
  const char *text = value.as<const char *>();
  if (text != nullptr) {
    const char *trimmed = text;
    while (isspace(static_cast<unsigned char>(*trimmed))) {
      ++trimmed;
    }
    const char *trimmedEnd = trimmed + strlen(trimmed);
    while (trimmedEnd > trimmed &&
           isspace(static_cast<unsigned char>(*(trimmedEnd - 1)))) {
      --trimmedEnd;
    }
    size_t trimmedLen = trimmedEnd - trimmed;
    if (trimmedLen == 4 && strncasecmp(trimmed, "true", trimmedLen) == 0) {
      out = 1;
      return true;
    }
    if (trimmedLen == 5 && strncasecmp(trimmed, "false", trimmedLen) == 0) {
      out = 0;
      return true;
    }
    char *end = nullptr;
    long parsed = strtol(trimmed, &end, 10);
    if (end != trimmed) {
      while (end < trimmedEnd && isspace(static_cast<unsigned char>(*end))) {
        ++end;
      }
    }
    if (end != trimmed && end == trimmedEnd) {
      out = static_cast<int32_t>(parsed);
      return true;
    }
  }
  if (value["value"].is<int32_t>()) {
    out = value["value"].as<int32_t>();
    return true;
  }
  if (value["option"].is<int32_t>()) {
    out = value["option"].as<int32_t>();
    return true;
  }
  if (value["id"].is<int32_t>()) {
    out = value["id"].as<int32_t>();
    return true;
  }
  return false;
}

bool readStatusInt(JsonObjectConst status, const char *idKey,
                   const char *sdkKey, const char *nameKey, int32_t &out) {
  return jsonVariantToInt(status[idKey], out) ||
         jsonVariantToInt(status[sdkKey], out) ||
         jsonVariantToInt(status[nameKey], out);
}

void applyGoProBatteryStatus(JsonObjectConst status) {
  if (status.isNull()) {
    return;
  }

  int32_t percent = 0;
  int32_t bars = 0;
  int32_t usbConnected = 0;
  bool percentKnown =
      readStatusInt(status, "70", "StatusId.INTERNAL_BATTERY_PERCENTAGE",
                    "internal_battery_percentage", percent);
  bool barsKnown = readStatusInt(status, "2", "StatusId.INTERNAL_BATTERY_BARS",
                                 "internal_battery_bars", bars);
  bool usbKnown = readStatusInt(status, "115", "StatusId.USB_CONNECTED",
                                "usb_connected", usbConnected);

  if (percentKnown) {
    goProBatteryPercent = constrain(static_cast<int>(percent), 0, 100);
  }
  if (barsKnown || usbKnown) {
    goProBatteryChargingOrPlugged =
        (barsKnown && bars == 4) || (usbKnown && usbConnected != 0);
  }
  if (percentKnown || barsKnown || usbKnown) {
    updateGoProBatteryIndicator();
    Serial.printf(
        "GoPro battery synced: percent=%d plugged=%u bars=%ld usb=%ld\n",
        goProBatteryPercent, goProBatteryChargingOrPlugged ? 1 : 0,
        barsKnown ? static_cast<long>(bars) : -1L,
        usbKnown ? static_cast<long>(usbConnected) : -1L);
  }
}

void applyCameraStatusState(JsonObjectConst status) {
  if (status.isNull()) {
    return;
  }

  applyGoProBatteryStatus(status);

  int32_t encoding = 0;
  int32_t duration = 0;
  bool encodingKnown =
      readStatusInt(status, "10", "StatusId.ENCODING", "encoding", encoding);
  bool durationKnown =
      readStatusInt(status, "13", "StatusId.VIDEO_ENCODING_DURATION",
                    "video_encoding_duration", duration);
  if (!encodingKnown && !durationKnown) {
    return;
  }

  bool cameraRecording = encodingKnown ? encoding != 0 : duration > 0;
  if (duration < 0) {
    duration = 0;
  }
  applyRecordingUiState(cameraRecording, static_cast<uint32_t>(duration),
                        durationKnown);
  Serial.printf(
      "Camera recording state synced: recording=%u duration=%ld known=%u\n",
      cameraRecording ? 1 : 0, static_cast<long>(duration),
      durationKnown ? 1 : 0);
}

bool parseCameraState(const String &body) {
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, body);
  if (error) {
    setAction("Camera state JSON parse failed");
    return false;
  }

  JsonObjectConst status = doc["status"].as<JsonObjectConst>();
  if (status.isNull()) {
    status = doc["statuses"].as<JsonObjectConst>();
  }
  applyCameraStatusState(status);

  JsonObject settings = doc["settings"].as<JsonObject>();
  if (settings.isNull()) {
    settings = doc["setting"].as<JsonObject>();
  }
  if (settings.isNull()) {
    if (status.isNull()) {
      setAction("Camera state has no settings/status object");
      return false;
    }
    setAction("Camera status synced");
    return true;
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

bool aspectFromSettingOption(int settingId, int option, uint16_t &aspectW,
                             uint16_t &aspectH) {
  switch (settingId) {
  case 108:
  case 192:
  case 232:
  case 233:
    switch (option) {
    case 0:
      aspectW = 4;
      aspectH = 3;
      return true;
    case 1:
      aspectW = 16;
      aspectH = 9;
      return true;
    case 3:
      aspectW = 8;
      aspectH = 7;
      return true;
    case 4:
      aspectW = 9;
      aspectH = 16;
      return true;
    case 5:
      aspectW = 21;
      aspectH = 9;
      return true;
    case 6:
      aspectW = 1;
      aspectH = 1;
      return true;
    }
    break;
  case 193:
    switch (option) {
    case 0:
    case 101:
      aspectW = 16;
      aspectH = 9;
      return true;
    case 1:
    case 104:
      aspectW = 9;
      aspectH = 16;
      return true;
    case 2:
    case 103:
      aspectW = 8;
      aspectH = 7;
      return true;
    case 100:
      aspectW = 4;
      aspectH = 3;
      return true;
    case 105:
      aspectW = 21;
      aspectH = 9;
      return true;
    case 106:
      aspectW = 1;
      aspectH = 1;
      return true;
    }
    break;
  }
  return false;
}

bool aspectFromResolutionOption(int option, uint16_t &aspectW,
                                uint16_t &aspectH) {
  switch (option) {
  case 1:
  case 4:
  case 9:
  case 12:
  case 24:
  case 100:
    aspectW = 16;
    aspectH = 9;
    return true;
  case 6:
  case 18:
  case 25:
  case 111:
  case 112:
  case 113:
  case 152:
  case 153:
  case 154:
  case 155:
  case 156:
  case 157:
  case 158:
  case 159:
    aspectW = 4;
    aspectH = 3;
    return true;
  case 26:
  case 27:
  case 28:
  case 107:
  case 108:
  case 122:
  case 123:
  case 124:
  case 125:
  case 136:
  case 137:
    aspectW = 8;
    aspectH = 7;
    return true;
  case 109:
  case 110:
  case 118:
  case 119:
  case 120:
  case 121:
  case 132:
  case 133:
  case 134:
  case 135:
    aspectW = 9;
    aspectH = 16;
    return true;
  case 35:
  case 36:
  case 142:
  case 143:
  case 144:
  case 145:
  case 146:
  case 147:
  case 148:
  case 149:
  case 150:
  case 151:
    aspectW = 21;
    aspectH = 9;
    return true;
  case 37:
  case 138:
  case 139:
  case 140:
  case 141:
    aspectW = 1;
    aspectH = 1;
    return true;
  }
  return false;
}

uint8_t estimateVideoVisiblePercent(int hypersmooth, int lens, int horizon,
                                    int maxLens) {
  uint8_t percent = 100;
  switch (hypersmooth) {
  case 1:
  case 100:
    percent = 96;
    break;
  case 2:
    percent = 93;
    break;
  case 3:
    percent = 88;
    break;
  case 4:
    percent = 90;
    break;
  }

  if (lens == 8 || lens == 10 || horizon == 2) {
    percent = min<uint8_t>(percent, 90);
  }
  if (lens == 7 || lens == 11 || maxLens > 0) {
    percent = min<uint8_t>(percent, 92);
  }
  return constrain(percent, 82, 100);
}

constexpr size_t kSnapshotPreviewModeCount = 2;
constexpr size_t kSnapshotPreviewAspectCount = 6;
constexpr size_t kSnapshotPreviewResolutionCount = 3;

struct SnapshotPreviewModeCrop {
  char mode;
  uint8_t visiblePercent;
};

struct SnapshotPreviewAspectCrop {
  const char *aspectRatio;
  SnapshotPreviewModeCrop modes[kSnapshotPreviewModeCount];
};

struct SnapshotPreviewResolutionCrop {
  const char *resolution;
  SnapshotPreviewAspectCrop aspectRatios[kSnapshotPreviewAspectCount];
};

struct SnapshotPreviewModelCrop {
  const char *modelName;
  SnapshotPreviewResolutionCrop resolutions[kSnapshotPreviewResolutionCount];
};

#define SNAPSHOT_PREVIEW_MODE_DEFAULTS                                         \
  {                                                                            \
    {'W', kSnapshotPreviewVisiblePercent}, {                                   \
      'L', kSnapshotPreviewVisiblePercent                                      \
    }                                                                          \
  }

#define SNAPSHOT_PREVIEW_ASPECT_DEFAULTS                                       \
  {                                                                            \
      {"16:9", SNAPSHOT_PREVIEW_MODE_DEFAULTS},                                \
      {"4:3", SNAPSHOT_PREVIEW_MODE_DEFAULTS},                                 \
      {"8:7", SNAPSHOT_PREVIEW_MODE_DEFAULTS},                                 \
      {"9:16", SNAPSHOT_PREVIEW_MODE_DEFAULTS},                                \
      {"21:9", SNAPSHOT_PREVIEW_MODE_DEFAULTS},                                \
      {"1:1", SNAPSHOT_PREVIEW_MODE_DEFAULTS},                                 \
  }

#define SNAPSHOT_PREVIEW_RESOLUTION_DEFAULTS                                   \
  {                                                                            \
      {"4k", SNAPSHOT_PREVIEW_ASPECT_DEFAULTS},                                \
      {"5k", SNAPSHOT_PREVIEW_ASPECT_DEFAULTS},                                \
      {"8k", SNAPSHOT_PREVIEW_ASPECT_DEFAULTS},                                \
  }

#define SNAPSHOT_PREVIEW_MODE_MISSION_1_PRO {{'W', 79}, {'L', 79}}

#define SNAPSHOT_PREVIEW_ASPECT_MISSION_1_PRO                                  \
  {                                                                            \
      {"16:9", SNAPSHOT_PREVIEW_MODE_MISSION_1_PRO},                           \
      {"4:3", SNAPSHOT_PREVIEW_MODE_MISSION_1_PRO},                            \
      {"8:7", SNAPSHOT_PREVIEW_MODE_MISSION_1_PRO},                            \
      {"9:16", SNAPSHOT_PREVIEW_MODE_MISSION_1_PRO},                           \
      {"21:9", SNAPSHOT_PREVIEW_MODE_MISSION_1_PRO},                           \
      {"1:1", SNAPSHOT_PREVIEW_MODE_MISSION_1_PRO},                            \
  }

#define SNAPSHOT_PREVIEW_RESOLUTION_MISSION_1_PRO                              \
  {                                                                            \
      {"4k", SNAPSHOT_PREVIEW_ASPECT_MISSION_1_PRO},                           \
      {"5k", SNAPSHOT_PREVIEW_ASPECT_MISSION_1_PRO},                           \
      {"8k", SNAPSHOT_PREVIEW_ASPECT_MISSION_1_PRO},                           \
  }

const SnapshotPreviewModelCrop kSnapshotPreviewVisiblePercentTable[] = {
    {"MISSION 1 PRO", SNAPSHOT_PREVIEW_RESOLUTION_MISSION_1_PRO},
    {"HERO11 Black", SNAPSHOT_PREVIEW_RESOLUTION_DEFAULTS},
};

#undef SNAPSHOT_PREVIEW_RESOLUTION_DEFAULTS
#undef SNAPSHOT_PREVIEW_ASPECT_DEFAULTS
#undef SNAPSHOT_PREVIEW_MODE_DEFAULTS

#undef SNAPSHOT_PREVIEW_RESOLUTION_MISSION_1_PRO
#undef SNAPSHOT_PREVIEW_ASPECT_MISSION_1_PRO
#undef SNAPSHOT_PREVIEW_MODE_MISSION_1_PRO

const char *snapshotResolutionKey(int resolutionOption) {
  switch (resolutionOption) {
  case 1:
  case 18:
  case 28:
  case 36:
  case 37:
  case 39:
  case 108:
  case 109:
  case 112:
    return "4k";
  case 21:
  case 24:
  case 25:
  case 26:
  case 27:
  case 35:
  case 100:
  case 107:
  case 113:
    return "5k";
  case 31:
    return "8k";
  }
  return "";
}

const char *snapshotAspectRatioKey(uint16_t aspectW, uint16_t aspectH) {
  if (aspectW == 16 && aspectH == 9)
    return "16:9";
  if (aspectW == 4 && aspectH == 3)
    return "4:3";
  if (aspectW == 8 && aspectH == 7)
    return "8:7";
  if (aspectW == 9 && aspectH == 16)
    return "9:16";
  if (aspectW == 21 && aspectH == 9)
    return "21:9";
  if (aspectW == 1 && aspectH == 1)
    return "1:1";
  return "";
}

char snapshotModeKey(int lens, int horizon, int maxLens) {
  switch (lens) {
  case 4:
  case 8:
  case 10:
  case 14:
  case 30:
  case 32:
  case 44:
  case 102:
    return 'L';
  }
  return (horizon == 2 || maxLens > 0) ? 'L' : 'W';
}

uint8_t
lookupSnapshotPreviewVisiblePercent(const SnapshotVideoFraming &framing) {
  const char *resolution = snapshotResolutionKey(framing.resolutionOption);
  const char *aspectRatio =
      snapshotAspectRatioKey(framing.aspectW, framing.aspectH);
  char mode = snapshotModeKey(framing.lensOption, framing.horizonOption,
                              framing.maxLensOption);
  if (cameraModelName.isEmpty()) {
    return kSnapshotPreviewVisiblePercent;
  }

  for (const SnapshotPreviewModelCrop &model :
       kSnapshotPreviewVisiblePercentTable) {
    if (strcasecmp(cameraModelName.c_str(), model.modelName) != 0) {
      continue;
    }
    uint8_t modelFallback = model.resolutions[0].aspectRatios[0].modes[0].visiblePercent;
    for (const SnapshotPreviewModeCrop &modeEntry :
         model.resolutions[0].aspectRatios[0].modes) {
      if (modeEntry.mode == mode) {
        modelFallback = modeEntry.visiblePercent;
        break;
      }
    }
    if (resolution[0] == '\0' || aspectRatio[0] == '\0') {
      return modelFallback;
    }
    for (const SnapshotPreviewResolutionCrop &resolutionEntry :
         model.resolutions) {
      if (strcasecmp(resolution, resolutionEntry.resolution) != 0) {
        continue;
      }
      uint8_t resolutionFallback = resolutionEntry.aspectRatios[0].modes[0].visiblePercent;
      for (const SnapshotPreviewModeCrop &modeEntry :
           resolutionEntry.aspectRatios[0].modes) {
        if (modeEntry.mode == mode) {
          resolutionFallback = modeEntry.visiblePercent;
          break;
        }
      }
      for (const SnapshotPreviewAspectCrop &aspectEntry :
           resolutionEntry.aspectRatios) {
        if (strcasecmp(aspectRatio, aspectEntry.aspectRatio) != 0) {
          continue;
        }
        for (const SnapshotPreviewModeCrop &modeEntry : aspectEntry.modes) {
          if (modeEntry.mode == mode) {
            return modeEntry.visiblePercent;
          }
        }
      }
      return resolutionFallback;
    }
    return modelFallback;
  }
  return kSnapshotPreviewVisiblePercent;
}

SnapshotVideoFraming currentSnapshotVideoFraming() {
  SnapshotVideoFraming framing;
  const uint16_t aspectIds[] = {232, 108, 193};
  int aspectSettingId = -1;
  int aspectOption = firstStoredSettingValue(
      aspectIds, sizeof(aspectIds) / sizeof(aspectIds[0]), &aspectSettingId);
  if (aspectOption >= 0 &&
      aspectFromSettingOption(aspectSettingId, aspectOption, framing.aspectW,
                              framing.aspectH)) {
    framing.valid = true;
    framing.aspectSettingId = aspectSettingId;
    framing.aspectOption = aspectOption;
  }

  framing.resolutionOption = getStoredSettingValue(2);
  if (!framing.valid &&
      aspectFromResolutionOption(framing.resolutionOption, framing.aspectW,
                                 framing.aspectH)) {
    framing.valid = true;
  }
  if (!framing.valid) {
    framing.valid = true;
    framing.aspectW = 16;
    framing.aspectH = 9;
  }

  framing.lensOption = getStoredSettingValue(121);
  framing.hypersmoothOption = getStoredSettingValue(135);
  framing.horizonOption = getStoredSettingValue(150);
  const uint16_t maxLensIds[] = {162, 189, 190};
  framing.maxLensOption = firstStoredSettingValue(
      maxLensIds, sizeof(maxLensIds) / sizeof(maxLensIds[0]));
  framing.visiblePercent =
      estimateVideoVisiblePercent(framing.hypersmoothOption, framing.lensOption,
                                  framing.horizonOption, framing.maxLensOption);
  framing.previewVisiblePercent = lookupSnapshotPreviewVisiblePercent(framing);
  return framing;
}

void logSnapshotVideoFraming(const SnapshotVideoFraming &framing) {
  const char *resolution = snapshotResolutionKey(framing.resolutionOption);
  const char *aspectRatio =
      snapshotAspectRatioKey(framing.aspectW, framing.aspectH);
  char mode = snapshotModeKey(framing.lensOption, framing.horizonOption,
                              framing.maxLensOption);
  Serial.printf(
      "Snapshot video framing: model='%s' resolution=%s aspect=%s mode=%c "
      "aspectDims=%u:%u cameraVisible=%u%% previewVisible=%u%% "
      "aspectSetting=%d option=%d "
      "resolutionOption=%d lens=%d hypersmooth=%d horizon=%d maxLens=%d\n",
      cameraModelName.isEmpty() ? "(unknown)" : cameraModelName.c_str(),
      resolution[0] == '\0' ? "(unknown)" : resolution,
      aspectRatio[0] == '\0' ? "(unknown)" : aspectRatio, mode, framing.aspectW,
      framing.aspectH, framing.visiblePercent, framing.previewVisiblePercent,
      framing.aspectSettingId, framing.aspectOption, framing.resolutionOption,
      framing.lensOption, framing.hypersmoothOption, framing.horizonOption,
      framing.maxLensOption);
}

int photoLensOptionForVideoLens(int videoLens) {
  switch (videoLens) {
  case 0:
  case 19:
  case 101:
    return 0; // Wide
  case 2:
    return 2; // Narrow
  case 4:
  case 30:
  case 102:
    return 4; // Linear
  case 8:
  case 32:
    return 8; // Linear + Horizon Leveling
  case 10:
    return 10; // Linear + Horizon Lock
  case 13:
  case 41:
    return 13; // Ultra Wide
  case 14:
  case 44:
    return 14; // Ultra Linear
  case 3:
  case 7:
  case 9:
  case 11:
  case 12:
  case 31:
  case 100:
  case 104:
    return 0; // Photo mode cannot reliably match these; choose Wide, not a
              // narrower lens.
  default:
    return -1;
  }
}

void alignTemporaryPhotoPresetForSnapshot() {
  int photoLens = photoLensOptionForVideoLens(snapshotVideoFraming.lensOption);
  if (photoLens < 0) {
    Serial.printf("Temporary photo lens unchanged; video lens option=%d\n",
                  snapshotVideoFraming.lensOption);
    return;
  }

  String path = "/gopro/camera/setting?setting=122&option=";
  path += photoLens;
  if (httpGetGoPro(path)) {
    storeSettingValue(122, photoLens);
    Serial.printf("Temporary photo lens aligned to option %d\n", photoLens);
  } else {
    Serial.printf("Temporary photo lens align failed option=%d\n", photoLens);
  }
}

int32_t readPresetInt(JsonObjectConst object, const char *camelKey,
                      const char *snakeKey, int32_t fallback = -1) {
  int32_t value = fallback;
  if (jsonVariantToInt(object[camelKey], value)) {
    return value;
  }
  if (jsonVariantToInt(object[snakeKey], value)) {
    return value;
  }
  return fallback;
}

JsonArrayConst readPresetArray(JsonObjectConst object, const char *camelKey,
                               const char *snakeKey) {
  JsonArrayConst value = object[camelKey].as<JsonArrayConst>();
  if (!value.isNull()) {
    return value;
  }
  return object[snakeKey].as<JsonArrayConst>();
}

JsonArrayConst readPresetSettingsArray(JsonObjectConst preset) {
  JsonArrayConst settings =
      readPresetArray(preset, "settingArray", "setting_array");
  if (!settings.isNull()) {
    return settings;
  }
  settings = preset["settings"].as<JsonArrayConst>();
  if (!settings.isNull()) {
    return settings;
  }
  return preset["setting"].as<JsonArrayConst>();
}

const char *presetObjectName(JsonObjectConst object) {
  const char *name = object["display_name"] | object["displayName"] |
                     object["name"] | object["title"] | nullptr;
  return name;
}

bool stringContainsIgnoreCase(const char *text, const char *needle) {
  if (text == nullptr || needle == nullptr || *needle == '\0') {
    return false;
  }
  size_t needleLen = strlen(needle);
  for (const char *cursor = text; *cursor != '\0'; ++cursor) {
    if (strncasecmp(cursor, needle, needleLen) == 0) {
      return true;
    }
  }
  return false;
}

bool storePresetSettings(JsonArrayConst settings, const char *context) {
  if (settings.isNull()) {
    return false;
  }
  uint16_t count = 0;
  for (JsonObjectConst setting : settings) {
    int32_t id = readPresetInt(setting, "id", "id");
    if (id <= 0) {
      id = readPresetInt(setting, "settingId", "setting_id");
    }
    int32_t value = readPresetInt(setting, "value", "value");
    if (value < 0) {
      value = readPresetInt(setting, "option", "option");
    }
    if (value < 0) {
      value = readPresetInt(setting, "optionId", "option_id");
    }
    if (id <= 0 || value < 0) {
      continue;
    }
    storeSettingValue(static_cast<uint16_t>(id), static_cast<int>(value));
    ++count;
  }
  if (count == 0) {
    return false;
  }
  refreshCaptureOverlayFromState();
  Serial.printf("Stored %u settings from %s\n", count, context);
  return true;
}

bool presetMarkedActive(JsonObjectConst preset) {
  int32_t active = 0;
  return jsonVariantToInt(preset["active"], active)
             ? active != 0
             : (jsonVariantToInt(preset["isActive"], active)
                    ? active != 0
                    : (jsonVariantToInt(preset["is_active"], active)
                           ? active != 0
                           : false));
}

int32_t readPresetGroupId(JsonObjectConst group) {
  int32_t id = readPresetInt(group, "id", "id");
  if (id < 0) {
    id = readPresetInt(group, "presetGroupId", "preset_group_id");
  }
  if (id < 0) {
    id = readPresetInt(group, "groupId", "group_id");
  }
  return id;
}

int32_t readPresetId(JsonObjectConst preset) {
  int32_t id = readPresetInt(preset, "id", "id");
  if (id < 0) {
    id = readPresetInt(preset, "presetId", "preset_id");
  }
  return id;
}

int32_t readActivePresetId(JsonObjectConst group) {
  int32_t id = readPresetInt(group, "activePresetId", "active_preset_id");
  if (id < 0) {
    id = readPresetInt(group, "activePresetID", "active_preset");
  }
  if (id < 0) {
    id = readPresetInt(group, "activePreset", "activePreset");
  }
  return id;
}

bool tryStoreActivePresetFromGroup(JsonObjectConst group, const char *context) {
  int32_t activePresetId = readActivePresetId(group);
  JsonArrayConst presets =
      readPresetArray(group, "presetArray", "preset_array");
  if (presets.isNull()) {
    presets = group["presets"].as<JsonArrayConst>();
  }

  JsonObjectConst fallbackPreset;
  for (JsonObjectConst preset : presets) {
    int32_t presetId = readPresetId(preset);
    bool active = (activePresetId >= 0 && presetId == activePresetId) ||
                  (activePresetId < 0 && presetMarkedActive(preset));
    if (!active) {
      if (fallbackPreset.isNull() &&
          !readPresetSettingsArray(preset).isNull()) {
        fallbackPreset = preset;
      }
      continue;
    }
    JsonArrayConst settings = readPresetSettingsArray(preset);
    if (storePresetSettings(settings, context)) {
      setAction("Video preset settings synced");
      return true;
    }
  }

  if (activePresetId < 0 && !fallbackPreset.isNull()) {
    return storePresetSettings(readPresetSettingsArray(fallbackPreset),
                               context);
  }

  Serial.printf("Active preset settings not found in %s: activePresetId=%ld\n",
                context, static_cast<long>(activePresetId));
  return false;
}

bool syncActiveVideoPresetSettings() {
  String body;
  const char *paths[] = {
      "/gopro/camera/presets/get?include-hidden=1",
      "/gopro/camera/presets/get?include-hidden=0",
      "/gopro/camera/presets/get",
  };
  int status = -1;
  const char *usedPath = nullptr;
  for (const char *path : paths) {
    status = httpGetGoProBody(path, body);
    if (status == 200) {
      usedPath = path;
      break;
    }
    if (status < 0) {
      break;
    }
  }
  if (status != 200) {
    setAction("Preset sync failed");
    return false;
  }
  Serial.printf("Preset sync response from %s\n",
                usedPath == nullptr ? "(unknown)" : usedPath);
  JsonDocument doc;
  if (deserializeJson(doc, body)) {
    setAction("Preset JSON parse failed");
    return false;
  }

  JsonArrayConst groups = readPresetArray(
      doc.as<JsonObjectConst>(), "presetGroupArray", "preset_group_array");
  if (groups.isNull()) {
    setAction("Preset JSON has no groups");
    return false;
  }

  JsonObjectConst firstPresetGroup;
  JsonObjectConst namedVideoGroup;
  for (JsonObjectConst group : groups) {
    int32_t groupId = readPresetGroupId(group);
    JsonArrayConst presets =
        readPresetArray(group, "presetArray", "preset_array");
    if (presets.isNull()) {
      presets = group["presets"].as<JsonArrayConst>();
    }
    const char *groupName = presetObjectName(group);
    Serial.printf("Preset group id=%ld name=%s presets=%u\n",
                  static_cast<long>(groupId),
                  groupName == nullptr ? "(none)" : groupName,
                  static_cast<unsigned>(presets.size()));

    if (firstPresetGroup.isNull() && !presets.isNull() && presets.size() > 0) {
      firstPresetGroup = group;
    }
    if (namedVideoGroup.isNull() &&
        stringContainsIgnoreCase(groupName, "video")) {
      namedVideoGroup = group;
    }

    if (groupId == kGoProVideoPresetGroup &&
        tryStoreActivePresetFromGroup(group, "active video preset")) {
      return true;
    }
  }

  if (!namedVideoGroup.isNull() &&
      tryStoreActivePresetFromGroup(namedVideoGroup,
                                    "named video preset group")) {
    return true;
  }
  if (!firstPresetGroup.isNull() &&
      tryStoreActivePresetFromGroup(firstPresetGroup,
                                    "first preset group fallback")) {
    return true;
  }

  setAction("Preset settings not found");
  return false;
}

bool syncCameraPresets() { return syncActiveVideoPresetSettings(); }

const char *knownOptionName(uint16_t settingId, int option) {
  switch (settingId) {
  case 108:
  case 192:
  case 193:
  case 232:
  case 233:
    switch (option) {
    case 0:
      return "4:3";
    case 1:
      return "16:9";
    case 3:
      return "8:7";
    case 4:
      return "9:16";
    case 5:
      return "21:9";
    case 6:
      return "1:1";
    }
    break;
  case 2:
    switch (option) {
    case 1:
      return "4K";
    case 4:
      return "2.7K";
    case 6:
      return "2.7K 4:3";
    case 7:
      return "1440";
    case 9:
      return "1080";
    case 12:
      return "720";
    case 18:
      return "4K 4:3";
    case 21:
      return "5.6K";
    case 24:
      return "5K";
    case 25:
      return "5K 4:3";
    case 26:
      return "5.3K 8:7";
    case 27:
      return "5.3K 4:3";
    case 28:
      return "4K 8:7";
    case 31:
      return "8K";
    case 35:
      return "5.3K 21:9";
    case 36:
      return "4K 21:9";
    case 37:
      return "4K 1:1";
    case 38:
      return "900";
    case 39:
      return "4K SPH";
    case 100:
      return "5.3K";
    case 107:
      return "5.3K 8:7";
    case 108:
      return "4K 8:7";
    case 109:
      return "4K 9:16";
    case 110:
      return "1080 9:16";
    case 111:
      return "2.7K 4:3";
    case 112:
      return "4K 4:3";
    case 113:
      return "5.3K 4:3";
    }
    break;
  case 3:
  case 234:
    switch (option) {
    case 0:
      return "240";
    case 1:
      return "120";
    case 2:
      return "100";
    case 5:
      return "60";
    case 6:
      return "50";
    case 8:
      return "30";
    case 9:
      return "25";
    case 10:
      return "24";
    case 13:
      return "200";
    case 15:
      return "400";
    }
    break;
  case 121:
  case 122:
  case 123:
    switch (option) {
    case 0:
      return "Wide";
    case 2:
      return "Narrow";
    case 3:
      return "Superview";
    case 4:
      return "Linear";
    case 7:
      return "Max SuperView";
    case 8:
      return "Linear+HL";
    case 9:
      return "HyperView";
    case 10:
      return "Linear+Lock";
    case 11:
      return "Max HyperView";
    case 12:
      return "Ultra SuperView";
    case 13:
      return "Ultra Wide";
    case 14:
      return "Ultra Linear";
    case 19:
      return "Wide";
    case 30:
      return "Linear";
    case 31:
      return "Superview";
    case 32:
      return "Linear+HL";
    case 41:
      return "Ultra Wide";
    case 44:
      return "Ultra Linear";
    case 100:
      return "Max SuperView";
    case 101:
      return "Wide";
    case 102:
      return "Linear";
    case 104:
      return "Ultra HyperView";
    }
    break;
  case 135:
    switch (option) {
    case 0:
      return "Off";
    case 1:
      return "Low";
    case 2:
      return "High";
    case 3:
      return "Boost";
    case 4:
      return "Auto Boost";
    case 100:
      return "Standard";
    }
    break;
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
    case 0:
      return "Off";
    case 1:
      return "On";
    case 2:
      return "Auto";
    }
    break;
  case 182:
    switch (option) {
    case 0:
      return "Standard";
    case 1:
      return "High";
    }
    break;
  case 216:
    switch (option) {
    case 70:
      return "Low";
    case 85:
      return "Medium";
    case 100:
      return "High";
    }
    break;
  case 178:
    switch (option) {
    case 0:
      return "2.4 GHz";
    case 1:
      return "5 GHz";
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

String firstStoredOptionDisplay(const uint16_t *settingIds, size_t count,
                                bool *found = nullptr) {
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
  appendCaptureSettingPart(
      setting, firstStoredOptionDisplay(aspectIds, sizeof(aspectIds) /
                                                       sizeof(aspectIds[0])));
  appendCaptureSettingPart(setting, storedOptionDisplay(2));
  appendCaptureSettingPart(
      setting,
      firstStoredOptionDisplay(fpsIds, sizeof(fpsIds) / sizeof(fpsIds[0])));
  appendCaptureSettingPart(
      setting,
      firstStoredOptionDisplay(lensIds, sizeof(lensIds) / sizeof(lensIds[0])));

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
    for (int value : values)
      addSettingOption(value);
    break;
  }
  case 2: {
    const int values[] = {1, 4, 6, 7, 9, 24, 25, 26, 27};
    for (int value : values)
      addSettingOption(value);
    break;
  }
  case 3:
  case 234: {
    const int values[] = {0, 1, 2, 5, 6, 8, 9, 10, 13, 15};
    for (int value : values)
      addSettingOption(value);
    break;
  }
  case 121:
  case 122:
  case 123: {
    const int values[] = {0,  2,  3,  4,  8,  9,   10,  12,  13,
                          14, 19, 30, 31, 32, 100, 101, 102, 104};
    for (int value : values)
      addSettingOption(value);
    break;
  }
  case 182:
  case 183:
  case 178: {
    const int values[] = {0, 1, 2};
    for (int value : values)
      addSettingOption(value);
    break;
  }
  case 216: {
    const int values[] = {70, 85, 100};
    for (int value : values)
      addSettingOption(value);
    break;
  }
  default: {
    const int values[] = {0, 1, 2, 3, 4, 5};
    for (int value : values)
      addSettingOption(value);
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
