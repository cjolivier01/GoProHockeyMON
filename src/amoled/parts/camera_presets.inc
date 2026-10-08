// Camera preset state and catalog synchronization.
void applyCameraPresetStatus(JsonObjectConst status) {
  int32_t presetId = -1;
  int32_t groupId = -1;
  readStatusInt(status, "97", "StatusId.PRESET", "preset", presetId);
  readStatusInt(status, "96", "StatusId.PRESET_GROUP", "preset_group", groupId);
  if (presetId != activeCameraPresetId || groupId != activeCameraPresetGroup) {
    captureMode = CameraPresets::groupName(groupId);
  }
  activeCameraPresetId = presetId;
  activeCameraPresetGroup = groupId;
  applyCaptureLabels();
}

bool storePresetSettings(JsonArrayConst settings, const char *context) {
  if (settings.isNull()) {
    return false;
  }
  uint16_t count = 0;
  for (JsonObjectConst setting : settings) {
    int32_t id = CameraPresets::readPresetInt(setting, "id", "id");
    if (id <= 0) {
      id = CameraPresets::readPresetInt(setting, "settingId", "setting_id");
    }
    int32_t value = CameraPresets::readPresetInt(setting, "value", "value");
    if (value < 0) {
      value = CameraPresets::readPresetInt(setting, "option", "option");
    }
    if (value < 0) {
      value = CameraPresets::readPresetInt(setting, "optionId", "option_id");
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

bool applyCameraPresetCatalog(const String &body) {
  JsonDocument doc;
  if (deserializeJson(doc, body)) {
    Serial.println("Preset JSON parse failed");
    return false;
  }

  int32_t groupId = activeCameraPresetGroup;
  JsonObjectConst preset = CameraPresets::findActivePreset(
      doc.as<JsonObjectConst>(), activeCameraPresetId, groupId);
  if (preset.isNull()) {
    Serial.println("Current camera preset not found in preset catalog");
    return false;
  }
  activeCameraPresetId = CameraPresets::readPresetId(preset);
  activeCameraPresetGroup = groupId;
  captureMode = CameraPresets::presetTitle(preset, groupId);
  int32_t number = CameraPresets::readPresetInt(preset, "titleNumber", "title_number", 0);
  if (!CameraPresets::presetObjectName(preset) && number > 0) {
    captureMode += " ";
    captureMode += number;
  }
  applyCaptureLabels();
  storePresetSettings(CameraPresets::readPresetSettingsArray(preset), "active camera preset");
  Serial.printf("Camera preset synced: id=%ld group=%ld name=%s\n",
                static_cast<long>(activeCameraPresetId),
                static_cast<long>(activeCameraPresetGroup), captureMode.c_str());
  return true;
}

bool syncCameraPresetsWithTimeout(uint32_t timeoutMs) {
  String body;
  const char *paths[] = {
      "/gopro/camera/presets/get?include-hidden=1",
      "/gopro/camera/presets/get?include-hidden=0",
      "/gopro/camera/presets/get",
  };
  int status = -1;
  const char *usedPath = nullptr;
  for (const char *path : paths) {
    status = httpGetGoProBodyWithTimeout(path, body, timeoutMs);
    if (status == 200) {
      usedPath = path;
      break;
    }
    if (status < 0) {
      break;
    }
  }
  if (status != 200) {
    Serial.println("Preset sync failed");
    return false;
  }
  Serial.printf("Preset sync response from %s\n",
                usedPath == nullptr ? "(unknown)" : usedPath);
  return applyCameraPresetCatalog(body);
}

bool syncCameraPresets() { return syncCameraPresetsWithTimeout(kHttpTimeoutMs); }
