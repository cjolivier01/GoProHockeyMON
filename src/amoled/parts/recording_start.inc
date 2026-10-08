// Refresh the selected preset before recording hands WiFi over to BLE.
bool startRecordingOverWifiAndVerify(bool &commandAccepted) {
  commandAccepted = false;
  // The camera's profile may have changed since the last idle refresh. Resolve
  // its name before capture disables WiFi, so recording retains that name.
  {
    String beforeStart;
    bool beforeStartHandoffOk = false;
    if (httpGetGoProBodyWithTimeout("/gopro/camera/state", beforeStart,
                                  kRecordingStartVerifyRequestTimeoutMs) == 200 &&
        parseCameraState(beforeStart, &beforeStartHandoffOk)) {
      if (recording) {
        // A capture started at the camera already satisfies the requested start.
        // Do not issue another shutter command or fetch presets during capture.
        if (!beforeStartHandoffOk && !setGoProWifiApBle(false)) {
          setAction("Recording; BLE reconnect failed");
        }
        return true;
      }
      syncCameraPresetsWithTimeout(kRecordingStartVerifyRequestTimeoutMs);
    }
  } // Release the preflight response before Bluetooth initialization.
  setAction("Starting recording over WiFi");
  int shutterStatus = httpGetGoProStatusWithTimeout(
      "/gopro/camera/shutter/start", kRecordingStartCommandTimeoutMs);
  if (shutterStatus < 200 || shutterStatus >= 300) {
    Serial.printf("WiFi shutter start failed: status=%d\n", shutterStatus);
    setAction("WiFi recording command failed");
    return false;
  }
  commandAccepted = true;

  Serial.println("WiFi shutter start accepted; waiting for recording state");
  uint32_t verifyStartedMs = millis();
  while (isLikelyGoProWifiConnected()) {
    uint32_t elapsedMs = millis() - verifyStartedMs;
    if (elapsedMs >= kRecordingStartVerifyTimeoutMs) {
      break;
    }
    serviceLvgl();

    String body;
    uint32_t remainingMs = kRecordingStartVerifyTimeoutMs - elapsedMs;
    uint32_t requestTimeoutMs = min(remainingMs, kRecordingStartVerifyRequestTimeoutMs);
    int stateStatus = httpGetGoProBodyWithTimeout(
        "/gopro/camera/state", body, requestTimeoutMs);
    bool wifiHandoffOk = false;
    if (stateStatus == 200 && parseCameraState(body, &wifiHandoffOk) && recording) {
      if (!wifiHandoffOk) {
        Serial.println("Recording verified; retrying incomplete BLE handoff");
        wifiHandoffOk = setGoProWifiApBle(false);
        if (!wifiHandoffOk) {
          setAction("Recording; BLE reconnect failed");
        }
      }
      Serial.printf("Recording verified over WiFi; BLE handoff=%u connected=%u\n",
                    wifiHandoffOk ? 1 : 0, bleConnected ? 1 : 0);
      return true;
    }

    delay(kRecordingStartVerifyPollMs);
  }

  Serial.println("WiFi recording start was not verified; BLE reconciliation required");
  setAction("Reconciling recording over BLE");
  return false;
}
