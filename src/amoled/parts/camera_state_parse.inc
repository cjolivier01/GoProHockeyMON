// Parse state completely before entering the Wi-Fi-to-BLE radio handoff.
bool applyCameraStatusState(JsonObjectConst status) {
  if (status.isNull()) {
    return false;
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
    return false;
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
  return true;
}

bool parseCameraStateValues(const String &body, bool &recordingStatusKnown, bool quiet) {
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, body);
  if (error) {
    if (!quiet) setAction("Camera state JSON parse failed");
    return false;
  }

  JsonObjectConst status = doc["status"].as<JsonObjectConst>();
  if (status.isNull()) {
    status = doc["statuses"].as<JsonObjectConst>();
  }
  applyCameraPresetStatus(status);
  recordingStatusKnown = applyCameraStatusState(status);

  JsonObject settings = doc["settings"].as<JsonObject>();
  if (settings.isNull()) {
    settings = doc["setting"].as<JsonObject>();
  }
  if (settings.isNull()) {
    if (status.isNull()) {
      if (!quiet) setAction("Camera state has no settings/status object");
      return false;
    }
    if (!quiet) setAction("Camera status synced");
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
  if (!quiet) setAction("Camera state synced");
  return true;
}

bool parseCameraState(const String &body, bool *wifiHandoffOk = nullptr, bool quiet = false) {
  if (wifiHandoffOk) *wifiHandoffOk = false;
  bool recordingStatusKnown = false;
  // The JSON document and its pools must be destroyed before BLE startup,
  // which needs a substantial contiguous allocation of internal RAM.
  if (!parseCameraStateValues(body, recordingStatusKnown, quiet)) return false;
  if (recordingStatusKnown && recording) {
    bool handoffOk = bleConnected;
    if (WiFi.status() == WL_CONNECTED) {
      serviceLvgl();
      handoffOk = suspendGoProWifiForRecording("camera state recording");
    }
    if (wifiHandoffOk) *wifiHandoffOk = handoffOk;
  }
  return true;
}
