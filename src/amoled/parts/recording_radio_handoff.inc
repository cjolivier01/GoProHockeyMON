// Coordinate radio ownership for recording and failed connection preflights.
bool markGoProWifiDisconnectedForRecording() {
  // All recording-related teardown paths, including failed BLE preflights,
  // must leave the radio alone until the HTTP worker has released its socket.
  if (!stopCameraPresetPoll()) {
    return false;
  }
  previewStreamRequested = false;
  snapshotPreviewPrepared = false;
  if (previewUdpListening) {
    previewUdp.stop();
    previewUdpListening = false;
  }
  if (WiFi.status() == WL_CONNECTED || WiFi.getMode() != WIFI_MODE_NULL) {
    WiFi.disconnect(false, false);
    WiFi.mode(WIFI_OFF);
    delay(250);
  }
  if (wifiLabel) {
    lv_label_set_text(wifiLabel, "WiFi: recording off");
  }
  if (wifiIndicator) {
    lv_label_set_text(wifiIndicator, LV_SYMBOL_WIFI);
    lv_obj_set_style_text_color(wifiIndicator, lv_color_hex(0x5a6472), 0);
  }
  setHomeCameraConnected(recording || bleConnected);
  goProWifiSuspendedForRecording = true;
  return true;
}

bool suspendGoProWifiForRecording(const char *reason) {
  Serial.print("Suspending GoPro WiFi for recording");
  if (reason != nullptr && reason[0]) {
    Serial.print(": ");
    Serial.print(reason);
  }
  Serial.println();

  if (!markGoProWifiDisconnectedForRecording()) {
    setAction("Recording; radio handoff pending");
    return false;
  }
  bool bleHandoffOk = setGoProWifiApBle(false);
  if (bleHandoffOk) {
    setAction("Recording; WiFi AP off");
  } else {
    setAction("Recording; local WiFi off");
  }
  serviceLvgl();
  return bleHandoffOk;
}

bool ensureNotRecordingForWifi(const char *reason) {
  if (!refreshRecordingStateBle()) {
    if (recording) {
      suspendGoProWifiForRecording(reason);
    } else {
      markGoProWifiDisconnectedForRecording();
      setAction("Recording check failed");
    }
    return false;
  }
  if (recording) {
    suspendGoProWifiForRecording(reason);
    return false;
  }
  return true;
}
