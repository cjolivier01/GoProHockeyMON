// BLE connection transaction; BLEDevice retains ownership of its client.
bool connectBle() {
  if (!initBleStack()) {
    return false;
  }
  if (operationCancelled()) {
    return false;
  }
  if (bleConnected && bleClient != nullptr && bleClient->isConnected()) {
    return true;
  }

  if (bestBleDevice == nullptr && !scanForCamera()) {
    return false;
  }
  if (operationCancelled()) {
    return false;
  }

  if (!ensureGoProBleClient()) {
    return false;
  }

  lv_label_set_text(statusLabel, "Connecting BLE");
  if (pairingInProgress) {
    showPairingPopup("Pairing New Camera\n\nConnecting GoPro BLE...\nPress lower button to cancel.");
  }
  setAction("Connecting GoPro BLE");
  serviceConnectionUi();
  logMemory("Before BLE connect");
  uint32_t connectTimeoutMs = pairingInProgress ? kPairBleConnectTimeoutMs
                                                : (cameraWakeInProgress
                                                       ? kBleWakeConnectTimeoutMs
                                                       : kBleConnectTimeoutMs);
  if (!bleClient->connectTimeout(bestBleDevice, connectTimeoutMs)) {
    bool savedCameraFound = !selectedBleFallback && !allowAnyCameraScan && !boundBleAddress.isEmpty();
    bleConnected = false;
    if (bleIndicator) {
      lv_obj_set_style_text_color(bleIndicator, lv_color_hex(0x5a6472), 0);
    }
    // BLEDevice owns this client and deletes it during deinit. Keep the
    // disconnected object for retry; deleting it here leaves its owner and
    // any pending stack callbacks pointing to freed memory.
    clearBleScanDevices();
    lv_label_set_text(cameraLabel,
                      savedCameraFound ? "Camera: found, power may be off"
                                       : "Camera: BLE connect failed");
    if (selectedBleFallback) {
      setCameraWakeAvailable(false);
      setAction("No GoPro BLE advertisement found");
    } else if (!boundBleAddress.isEmpty() && !allowAnyCameraScan) {
      setConnectRetryAvailable(true);
      setCameraWakeAvailable(true);
      setAction("GoPro found; tap ON to wake");
    } else {
      setCameraWakeAvailable(false);
      setAction("BLE connect failed");
    }
    return false;
  }
  if (operationCancelled()) {
    if (bleClient != nullptr && bleClient->isConnected()) {
      bleClient->disconnect();
    }
    bleConnected = false;
    setAction("Pairing cancelled");
    return false;
  }

  bleConnected = true;
  connectRetryAvailable = false;
  setCameraWakeAvailable(false);
  if (bleIndicator) {
    lv_obj_set_style_text_color(bleIndicator, lv_color_hex(0x2c7be5), 0);
  }
  logMemory("After BLE connect");
  BLERemoteService *control = bleClient->getService(kControlService);
  if (control != nullptr) {
    BLERemoteCharacteristic *response = control->getCharacteristic(kCommandResponse);
    if (response != nullptr && response->canNotify()) {
      response->registerForNotify(commandResponseNotify);
    }
    BLERemoteCharacteristic *settingsResponse = control->getCharacteristic(kSettingsResponse);
    if (settingsResponse != nullptr && settingsResponse->canNotify()) {
      settingsResponse->registerForNotify(commandResponseNotify);
    }
    BLERemoteCharacteristic *queryResponse = control->getCharacteristic(kQueryResponse);
    if (queryResponse != nullptr && queryResponse->canNotify()) {
      queryResponse->registerForNotify(commandResponseNotify);
    }
  }

  logMemory("After BLE service discovery");
  lv_label_set_text(statusLabel, "BLE connected");
  setAction("BLE connected");
  serviceLvgl();
  return true;
}
