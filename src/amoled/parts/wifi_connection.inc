// Reuse an existing Wi-Fi association before invoking any BLE operation: BLE
// connection setup tears down Wi-Fi on this single-radio remote.
bool parseCameraState(const String &body, bool *wifiHandoffOk, bool quiet);
bool readStatusInt(JsonObjectConst status, const char *idKey,
                   const char *sdkKey, const char *nameKey, int32_t &out);
int httpGetGoProBody(const String &path, String &body);
bool syncCameraPresets();

enum class ExistingGoProWifi { Unavailable, Ready, Blocked };

ExistingGoProWifi reuseExistingGoProWifi(const char *reason) {
  cancelCameraPresetPoll();
  if (!isLikelyGoProWifiConnected()) {
    return ExistingGoProWifi::Unavailable;
  }
  if (recording) {
    suspendGoProWifiForRecording("recording active");
    return ExistingGoProWifi::Blocked;
  }

  String body;
  int statusCode = httpGetGoProBody("/gopro/camera/state", body);
  if (operationCancelled()) {
    return ExistingGoProWifi::Blocked;
  }
  if (statusCode != 200) {
    setAction("GoPro HTTP stale; reconnecting WiFi");
    Serial.println("GoPro WiFi association is stale; reconnecting");
    WiFi.disconnect(false, false);
    delay(300);
    setHomeCameraConnected(false);
    return ExistingGoProWifi::Unavailable;
  }

  // HTTP success alone does not establish that capture is idle. A partial or
  // malformed state response must not let a snapshot change modes while the
  // recording state is unknown.
  {
    JsonDocument doc;
    if (deserializeJson(doc, body)) {
      setAction("Camera state JSON parse failed");
      return ExistingGoProWifi::Blocked;
    }
    JsonObjectConst status = doc["status"].as<JsonObjectConst>();
    if (status.isNull()) {
      status = doc["statuses"].as<JsonObjectConst>();
    }
    int32_t encoding = 0;
    int32_t duration = 0;
    if (!readStatusInt(status, "10", "StatusId.ENCODING", "encoding", encoding) &&
        !readStatusInt(status, "13", "StatusId.VIDEO_ENCODING_DURATION",
                       "video_encoding_duration", duration)) {
      setAction("Recording check failed");
      return ExistingGoProWifi::Blocked;
    }
  } // Release the preliminary JSON pools before parsing can initialize BLE.
  // This applies the same recording UI and Wi-Fi suspension as a full sync,
  // using the response we already have instead of another HTTP/BLE round trip.
  if (!parseCameraState(body, nullptr, false) || recording || operationCancelled()) {
    return ExistingGoProWifi::Blocked;
  }
  goProWifiSuspendedForRecording = false;
  markExistingGoProWifiConnected();
  setAction(reason == nullptr ? "Using existing GoPro WiFi" : reason);
  return ExistingGoProWifi::Ready;
}

bool connectGoProWifiFromBle() {
  if (operationCancelled()) {
    return false;
  }
  if (boundBleAddress.isEmpty() && !allowAnyCameraScan) {
    if (cameraLabel) {
      lv_label_set_text(cameraLabel, "Camera: not paired");
    }
    if (wifiLabel) {
      lv_label_set_text(wifiLabel, "WiFi: idle");
    }
    setHomeCameraConnected(false);
    setConnectRetryAvailable(false);
    setAction("No saved camera; tap Pair New");
    Serial.println("GoPro WiFi connect blocked: no saved camera binding");
    return false;
  }
  ExistingGoProWifi existing = reuseExistingGoProWifi(nullptr);
  if (existing != ExistingGoProWifi::Unavailable) {
    if (existing == ExistingGoProWifi::Ready) {
      syncCameraPresets();
    }
    return existing == ExistingGoProWifi::Ready;
  }
  if (!ensureNotRecordingForWifi("camera already recording")) {
    return false;
  }
  if (!readGoProWifiCredentials()) {
    return false;
  }
  String verifiedBleAddress;
  String verifiedBleName;
  if (bestBleDevice != nullptr) {
    verifiedBleAddress = bestBleDevice->getAddress().toString().c_str();
    verifiedBleAddress.toLowerCase();
    verifiedBleName = bestBleDevice->haveName() ? String(bestBleDevice->getName().c_str()) : "";
  }
  if (!verifiedBleAddress.isEmpty()) {
    saveCameraBindingValues(verifiedBleAddress, verifiedBleName);
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
  return connectGoProWifiWithCurrentCredentials("BLE handoff");
}

bool ensureGoProWifiReady(const char *reason) {
  if (operationCancelled()) {
    return false;
  }
  ExistingGoProWifi existing = reuseExistingGoProWifi(reason);
  if (existing != ExistingGoProWifi::Unavailable) {
    return existing == ExistingGoProWifi::Ready;
  }
  if (!ensureNotRecordingForWifi("recording active")) {
    return false;
  }
  if (!goProWifiSuspendedForRecording && !goProSsid.isEmpty() && !goProPassword.isEmpty() &&
      connectGoProWifiWithCurrentCredentials("known credentials")) {
    return true;
  }
  return connectGoProWifiFromBle();
}
