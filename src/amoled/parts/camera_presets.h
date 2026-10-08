#pragma once

#include <ArduinoJson.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

// Open GoPro status 96/97 identify the current group/preset. Group-local
// active_preset_id values also describe inactive groups, so they are not enough
// to identify the camera's current preset on their own.
namespace CameraPresets {

inline bool integer(JsonVariantConst value, int32_t &out) {
  if (value.is<int32_t>() || value.is<bool>()) {
    out = value.as<int32_t>();
    return true;
  }
  const char *text = value.as<const char *>();
  if (text && *text) {
    char *end = nullptr;
    errno = 0;
    long parsed = strtol(text, &end, 10);
    if (errno != ERANGE && end != text && *end == '\0' && parsed >= INT32_MIN && parsed <= INT32_MAX) {
      out = static_cast<int32_t>(parsed);
      return true;
    }
  }
  if (value.is<JsonObjectConst>()) {
    return integer(value["value"], out) || integer(value["option"], out) ||
           integer(value["id"], out);
  }
  return false;
}

inline int32_t readPresetInt(JsonObjectConst object, const char *camelKey,
                      const char *snakeKey, int32_t fallback = -1) {
  int32_t value = fallback;
  if (integer(object[camelKey], value)) {
    return value;
  }
  if (integer(object[snakeKey], value)) {
    return value;
  }
  return fallback;
}

inline JsonArrayConst readPresetArray(JsonObjectConst object, const char *camelKey,
                               const char *snakeKey) {
  JsonArrayConst value = object[camelKey].as<JsonArrayConst>();
  if (!value.isNull()) {
    return value;
  }
  return object[snakeKey].as<JsonArrayConst>();
}

inline JsonArrayConst readPresetSettingsArray(JsonObjectConst preset) {
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

inline const char *presetObjectName(JsonObjectConst object) {
  const char *keys[] = {"custom_name", "customName", "display_name",
                        "displayName", "name", "title"};
  for (const char *key : keys) {
    const char *name = object[key].as<const char *>();
    if (name && *name) {
      return name;
    }
  }
  return nullptr;
}

inline bool presetMarkedActive(JsonObjectConst preset) {
  int32_t active = 0;
  return integer(preset["active"], active)
             ? active != 0
             : (integer(preset["isActive"], active)
                    ? active != 0
                    : (integer(preset["is_active"], active)
                           ? active != 0
                           : false));
}

inline int32_t readPresetGroupId(JsonObjectConst group) {
  const char *keys[] = {"id", "presetGroupId", "preset_group_id", "groupId", "group_id"};
  for (const char *key : keys) {
    int32_t id = -1;
    if (integer(group[key], id) && id >= 0) {
      return id;
    }
    const char *name = group[key].as<const char *>();
    if (!name) continue;
    if (strcmp(name, "PRESET_GROUP_ID_VIDEO") == 0) return 1000;
    if (strcmp(name, "PRESET_GROUP_ID_PHOTO") == 0) return 1001;
    if (strcmp(name, "PRESET_GROUP_ID_TIMELAPSE") == 0) return 1002;
    if (strcmp(name, "PRESET_GROUP_ID_GENERAL") == 0) return 2000;
  }
  return -1;
}

inline int32_t readPresetId(JsonObjectConst preset) {
  int32_t id = readPresetInt(preset, "id", "id");
  if (id < 0) {
    id = readPresetInt(preset, "presetId", "preset_id");
  }
  return id;
}

inline int32_t readActivePresetId(JsonObjectConst group) {
  int32_t id = readPresetInt(group, "activePresetId", "active_preset_id");
  if (id < 0) {
    id = readPresetInt(group, "activePresetID", "active_preset");
  }
  if (id < 0) {
    id = readPresetInt(group, "activePreset", "activePreset");
  }
  return id;
}

inline const char *groupName(int32_t groupId) {
  switch (groupId) {
  case 1000: return "Video";
  case 1001: return "Photo";
  case 1002: return "Time Lapse";
  default: return "Camera";
  }
}

inline JsonObjectConst findActivePreset(JsonObjectConst catalog, int32_t presetId,
                                        int32_t &groupId) {
  JsonArrayConst groups = readPresetArray(catalog, "presetGroupArray", "preset_group_array");
  for (JsonObjectConst group : groups) {
    int32_t candidateGroup = readPresetGroupId(group);
    if (groupId >= 0 && candidateGroup != groupId) {
      continue;
    }
    JsonArrayConst presets = readPresetArray(group, "presetArray", "preset_array");
    if (presets.isNull()) {
      presets = group["presets"].as<JsonArrayConst>();
    }
    int32_t selected = presetId >= 0 ? presetId : readActivePresetId(group);
    // Never guess a current group or use its first preset as a fallback.
    if (presetId < 0 && groupId < 0) {
      continue;
    }
    for (JsonObjectConst preset : presets) {
      int32_t id = readPresetId(preset);
      if (id >= 0 && ((selected >= 0 && id == selected) ||
                     (selected < 0 && presetMarkedActive(preset)))) {
        groupId = candidateGroup;
        return preset;
      }
    }
  }
  return JsonObjectConst();
}

inline const char *presetTitle(JsonObjectConst preset, int32_t groupId) {
  if (const char *name = presetObjectName(preset)) {
    return name;
  }
  // HTTP serializes protobuf enums as names on current cameras; accept numeric
  // values too. Keep both representations mapped to the same user-facing label.
  struct Title { int32_t id; const char *symbol; const char *label; };
  static constexpr Title titles[] = {
      {0, "ACTIVITY", "Activity"},
      {1, "STANDARD", "Standard"},
      {2, "CINEMATIC", "Cinematic"},
      {3, "PHOTO", "Photo"},
      {4, "LIVE_BURST", "Live Burst"},
      {5, "BURST", "Burst"},
      {6, "NIGHT", "Night"},
      {7, "TIME_WARP", "TimeWarp"},
      {8, "TIME_LAPSE", "Time Lapse"},
      {9, "NIGHT_LAPSE", "Night Lapse"},
      {10, "VIDEO", "Video"},
      {11, "SLOMO", "Slo-Mo"},
      {13, "PHOTO_2", "Photo"},
      {14, "PANORAMA", "Panorama"},
      {16, "TIME_WARP_2", "TimeWarp"},
      {18, "CUSTOM", "Custom"},
      {19, "AIR", "Air"},
      {20, "BIKE", "Bike"},
      {21, "EPIC", "Epic"},
      {22, "INDOOR", "Indoor"},
      {23, "MOTOR", "Motor"},
      {24, "MOUNTED", "Mounted"},
      {25, "OUTDOOR", "Outdoor"},
      {26, "POV", "POV"},
      {27, "SELFIE", "Selfie"},
      {28, "SKATE", "Skate"},
      {29, "SNOW", "Snow"},
      {30, "TRAIL", "Trail"},
      {31, "TRAVEL", "Travel"},
      {32, "WATER", "Water"},
      {33, "LOOPING", "Looping"},
      {34, "STARS", "Stars"},
      {35, "ACTION", "Action"},
      {36, "FOLLOW_CAM", "Follow Cam"},
      {37, "SURF", "Surf"},
      {38, "CITY", "City"},
      {39, "SHAKY", "Shaky"},
      {40, "CHESTY", "Chesty"},
      {41, "HELMET", "Helmet"},
      {42, "BITE", "Bite"},
      {43, "CUSTOM_CINEMATIC", "Cinematic"},
      {44, "VLOG", "Vlog"},
      {45, "FPV", "FPV"},
      {46, "HDR", "HDR"},
      {47, "LANDSCAPE", "Landscape"},
      {48, "LOG", "Log"},
      {49, "CUSTOM_SLOMO", "Slo-Mo"},
      {50, "TRIPOD", "Tripod"},
      {58, "BASIC", "Basic"},
      {59, "ULTRA_SLO_MO", "Ultra Slo-Mo"},
      {60, "STANDARD_ENDURANCE", "Standard Endurance"},
      {61, "ACTIVITY_ENDURANCE", "Activity Endurance"},
      {62, "CINEMATIC_ENDURANCE", "Cinematic Endurance"},
      {63, "SLOMO_ENDURANCE", "Slo-Mo Endurance"},
      {64, "STATIONARY_1", "Stationary 1"},
      {65, "STATIONARY_2", "Stationary 2"},
      {66, "STATIONARY_3", "Stationary 3"},
      {67, "STATIONARY_4", "Stationary 4"},
      {68, "SIMPLE_VIDEO", "Simple Video"},
      {69, "SIMPLE_TIME_WARP", "Simple TimeWarp"},
      {70, "SIMPLE_SUPER_PHOTO", "Simple Super Photo"},
      {71, "SIMPLE_NIGHT_PHOTO", "Simple Night Photo"},
      {72, "SIMPLE_VIDEO_ENDURANCE", "Simple Video Endurance"},
      {73, "HIGHEST_QUALITY", "Highest Quality"},
      {74, "EXTENDED_BATTERY", "Extended Battery"},
      {75, "LONGEST_BATTERY", "Longest Battery"},
      {76, "STAR_TRAIL", "Star Trail"},
      {77, "LIGHT_PAINTING", "Light Painting"},
      {78, "LIGHT_TRAIL", "Light Trail"},
      {79, "FULL_FRAME", "Full Frame"},
      {82, "STANDARD_QUALITY_VIDEO", "Standard Quality Video"},
      {83, "BASIC_QUALITY_VIDEO", "Basic Quality Video"},
      {93, "HIGHEST_QUALITY_VIDEO", "Highest Quality Video"},
      {94, "USER_DEFINED_CUSTOM_NAME", "Custom"},
      {99, "EASY_STANDARD_PROFILE", "Easy Standard Profile"},
      {100, "EASY_HDR_PROFILE", "Easy HDR Profile"},
      {106, "BURST_SLOMO", "Burst Slo-Mo"},
      {125, "4_3_VIDEO", "4:3 Video"},
      {126, "16_9_VIDEO", "16:9 Video"},
      {127, "16_9_SLOMO", "16:9 Slo-Mo"},
      {131, "TIME_LAPSE_VIDEO", "Time Lapse Video"},
      {132, "TIME_LAPSE_PHOTO", "Time Lapse Photo"},
      {133, "NIGHT_LAPSE_VIDEO", "Night Lapse Video"},
      {134, "NIGHT_LAPSE_PHOTO", "Night Lapse Photo"},
  };
  int32_t id = readPresetInt(preset, "titleId", "title_id");
  const char *symbol = preset["titleId"].as<const char *>();
  if (!symbol) symbol = preset["title_id"].as<const char *>();
  constexpr const char *prefix = "PRESET_TITLE_";
  if (symbol && strncmp(symbol, prefix, strlen(prefix)) == 0) {
    symbol += strlen(prefix);
  } else {
    symbol = nullptr;
  }
  for (const Title &title : titles) {
    if (title.id == id || (symbol && strcmp(title.symbol, symbol) == 0)) {
      return title.label;
    }
  }
  return groupName(groupId);
}

} // namespace CameraPresets
