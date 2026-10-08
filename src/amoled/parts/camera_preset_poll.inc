// Network polling runs independently of LVGL and physical-button handling.
// Only the main loop applies the completed result to camera/UI state.
struct CameraPresetPoll {
  String baseUrl;
  String cameraBinding;
  String stateBody;
  String catalogBody;
  std::atomic<bool> cancelled{false};
  std::atomic<bool> complete{false};
};
CameraPresetPoll *cameraPresetPoll = nullptr;
uint32_t lastCameraPresetPollMs = 0;

void cancelCameraPresetPoll() {
  if (cameraPresetPoll) {
    cameraPresetPoll->cancelled.store(true);
    if (cameraPresetPoll->complete.load(std::memory_order_acquire)) {
      CameraPresetPoll *poll = cameraPresetPoll;
      cameraPresetPoll = nullptr;
      delete poll;
      lastCameraPresetPollMs = millis();
    }
  }
}

bool stopCameraPresetPoll() {
  // A cancelled HTTP request still owns a task stack, socket and response
  // buffers. Join it before radio shutdown/BLE allocation; never kill a task
  // while it owns the network client's resources.
  cancelCameraPresetPoll();
  uint32_t started = millis();
  while (cameraPresetPoll) {
    if (millis() - started >= 2500) {
      Serial.println("Camera preset poll has not stopped; deferring radio handoff");
      return false;
    }
    serviceLvgl();
    delay(1);
    cancelCameraPresetPoll();
  }
  return true;
}

void fetchCameraPresetPoll(void *argument) {
  auto *poll = static_cast<CameraPresetPoll *>(argument);
  // This worker must not use the normal HTTP helpers: those touch LVGL and
  // recording state. Each request owns its client and has bounded I/O waits.
  auto get = [poll](const char *path, String &body) {
    if (poll->cancelled.load()) return false;
    HTTPClient http;
    http.setConnectTimeout(800);
    http.setTimeout(800);
    if (!http.begin(poll->baseUrl + path)) return false;
    int status = http.GET();
    if (status == 200 && !poll->cancelled.load()) {
      body = http.getString();
    }
    http.end();
    return status == 200 && !poll->cancelled.load();
  };
  if (get("/gopro/camera/state", poll->stateBody)) {
    JsonDocument doc;
    if (!deserializeJson(doc, poll->stateBody)) {
      JsonObjectConst status = doc["status"].as<JsonObjectConst>();
      if (status.isNull()) status = doc["statuses"].as<JsonObjectConst>();
      int32_t encoding = -1;
      if (readStatusInt(status, "10", "StatusId.ENCODING", "encoding", encoding) &&
          encoding == 0) {
        get("/gopro/camera/presets/get?include-hidden=1", poll->catalogBody);
      }
    }
  }
  // Ownership returns to the main loop. Do not access poll after publishing.
  poll->complete.store(true, std::memory_order_release);
  vTaskDelete(nullptr);
}

void refreshCameraPresetWhileIdle() {
  bool idle = !goproActionBusy && !snapshotPreviewBusy && !pairingInProgress &&
              !touchActive && !navSwipeActive && actionButtonShortClickCount == 0 &&
              pendingHomeAction == PendingHomeAction::None;
  if (cameraPresetPoll) {
    if (!cameraPresetPoll->complete.load(std::memory_order_acquire)) return;
    if (!idle) return;
    CameraPresetPoll *poll = cameraPresetPoll;
    cameraPresetPoll = nullptr;
    if (!poll->cancelled.load() && homeCameraConnected && !recording &&
        isLikelyGoProWifiConnected() && poll->cameraBinding == boundBleAddress &&
        poll->baseUrl == cameraBaseUrl() && !poll->stateBody.isEmpty()) {
      goproActionBusy = true;
      // parseCameraState applies external recording detection and the existing
      // Wi-Fi-to-BLE handoff. Never keep polling HTTP during recording.
      if (parseCameraState(poll->stateBody, nullptr, true) && !recording && !poll->catalogBody.isEmpty()) {
        applyCameraPresetCatalog(poll->catalogBody);
      }
      goproActionBusy = false;
    }
    delete poll;
    lastCameraPresetPollMs = millis();
  }
  if (millis() - lastCameraPresetPollMs < 5000 || !idle || !displayOn ||
      !homeCameraConnected || recording || !isLikelyGoProWifiConnected()) return;
  lastCameraPresetPollMs = millis();
  auto *poll = new (std::nothrow) CameraPresetPoll;
  if (!poll) return;
  poll->baseUrl = cameraBaseUrl();
  poll->cameraBinding = boundBleAddress;
  cameraPresetPoll = poll;
  if (xTaskCreate(fetchCameraPresetPoll, "camera-preset", 8192, poll, 1, nullptr) != pdPASS) {
    cameraPresetPoll = nullptr;
    delete poll;
  }
}
