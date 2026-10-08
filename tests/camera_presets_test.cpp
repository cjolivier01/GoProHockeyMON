#include <cassert>
#include <cstring>
#include <iostream>
#include "src/amoled/parts/camera_presets.h"
using namespace CameraPresets;

int main() {
  JsonDocument doc;
  assert(!deserializeJson(doc, R"({"presetGroupArray":[
    {"id":1001,"activePresetId":65536,"presetArray":[{"id":65536,"titleId":3}]},
    {"id":1000,"activePresetId":0,"presetArray":[
      {"id":0,"titleId":10,"settingArray":[{"id":2,"value":9}]},
      {"id":7,"titleId":94,"customName":"Hockey","settingArray":[{"id":2,"value":1}]}]},
    {"id":1002,"activePresetId":131072,"presetArray":[{"id":131072,"titleId":7}]}
  ]})"));
  int32_t group = 1000;
  auto preset = findActivePreset(doc.as<JsonObjectConst>(), 7, group);
  assert(readPresetId(preset) == 7);
  assert(group == 1000);
  assert(std::strcmp(presetTitle(preset, group), "Hockey") == 0);
  assert(readPresetSettingsArray(preset)[0]["value"] == 1);
  // Camera status wins over a stale group-local active ID and catalog order.
  group = -1;
  assert(readPresetId(findActivePreset(doc.as<JsonObjectConst>(), 7, group)) == 7);
  assert(group == 1000);
  group = 1001;
  assert(readPresetId(findActivePreset(doc.as<JsonObjectConst>(), -1, group)) == 65536);
  group = 1002;
  preset = findActivePreset(doc.as<JsonObjectConst>(), 131072, group);
  assert(std::strcmp(presetTitle(preset, group), "TimeWarp") == 0);
  group = 1000;
  preset = findActivePreset(doc.as<JsonObjectConst>(), 0, group);
  assert(readPresetId(preset) == 0); // Zero is a valid preset ID.
  assert(std::strcmp(presetTitle(preset, group), "Video") == 0);
  group = -1;
  assert(findActivePreset(doc.as<JsonObjectConst>(), -1, group).isNull());
  group = 1000;
  assert(findActivePreset(doc.as<JsonObjectConst>(), 42, group).isNull());
  group = 1001;
  assert(findActivePreset(doc.as<JsonObjectConst>(), 7, group).isNull());

  assert(!deserializeJson(doc, R"({"preset_group_array":[
    {"preset_group_id":"1000","active_preset_id":"8","preset_array":[
      {"preset_id":"8","custom_name":"Hockey","display_name":"Video","setting_array":[]},
      {"id":9,"custom_name":"Practice"}]}]})"));
  group = 1000;
  preset = findActivePreset(doc.as<JsonObjectConst>(), -1, group);
  assert(readPresetId(preset) == 8);
  assert(std::strcmp(presetTitle(preset, group), "Hockey") == 0);
  // Name selection is independent of optional preset settings.
  assert(readPresetSettingsArray(preset).size() == 0);
  preset = findActivePreset(doc.as<JsonObjectConst>(), 9, group);
  assert(std::strcmp(presetTitle(preset, group), "Practice") == 0);
  assert(readPresetSettingsArray(preset).isNull());

  assert(!deserializeJson(doc, R"({"presetGroupArray":[{"id":1000,"presetArray":[
    {"id":0,"titleId":10},{"id":3,"isActive":true,"customName":"Hockey"}]}]})"));
  group = 1000;
  assert(readPresetId(findActivePreset(doc.as<JsonObjectConst>(), -1, group)) == 3);
  doc["presetGroupArray"][0]["presetArray"][1]["isActive"] = false;
  assert(findActivePreset(doc.as<JsonObjectConst>(), -1, group).isNull());
  // Empty custom names should not hide a real display name.
  assert(!deserializeJson(doc, R"({"customName":"","display_name":"Training"})"));
  assert(std::strcmp(presetTitle(doc.as<JsonObjectConst>(), 1000), "Training") == 0);
  assert(!deserializeJson(doc, R"({"id":"bad","titleId":999})"));
  assert(readPresetId(doc.as<JsonObjectConst>()) == -1);
  assert(std::strcmp(presetTitle(doc.as<JsonObjectConst>(), 1001), "Photo") == 0);
  // Actual protobuf JSON representation used by GoPro's HTTP preset API.
  assert(!deserializeJson(doc, R"({"presetGroupArray":[
    {"id":"PRESET_GROUP_ID_PHOTO","presetArray":[{"id":65536,"titleId":"PRESET_TITLE_PHOTO"}]},
    {"id":"PRESET_GROUP_ID_VIDEO","presetArray":[
      {"id":0,"titleId":"PRESET_TITLE_VIDEO"},
      {"id":7,"titleId":"PRESET_TITLE_USER_DEFINED_CUSTOM_NAME","customName":"Hockey"},
      {"id":8,"titleId":"PRESET_TITLE_INDOOR"}]}]})"));
  group = 1000;
  preset = findActivePreset(doc.as<JsonObjectConst>(), 7, group);
  assert(!preset.isNull() && std::strcmp(presetTitle(preset, group), "Hockey") == 0);
  preset = findActivePreset(doc.as<JsonObjectConst>(), 8, group);
  assert(std::strcmp(presetTitle(preset, group), "Indoor") == 0);
  assert(!deserializeJson(doc, R"({"title_id":"PRESET_TITLE_LOOPING"})"));
  assert(std::strcmp(presetTitle(doc.as<JsonObjectConst>(), 1000), "Looping") == 0);
  assert(!deserializeJson(doc, R"({"titleId":22})"));
  assert(std::strcmp(presetTitle(doc.as<JsonObjectConst>(), 1000), "Indoor") == 0);
  std::cout << "Preset parser tests passed\n";
}
