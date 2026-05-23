void configureBleSecurity() {
  if (bleSecurityCallbacks == nullptr) {
    bleSecurityCallbacks = new BLESecurityCallbacks();
  }
  if (bleSecurity == nullptr) {
    bleSecurity = new BLESecurity();
  }
  BLEDevice::setSecurityCallbacks(bleSecurityCallbacks);
  bleSecurity->setAuthenticationMode(true, false, true);
  bleSecurity->setCapability(ESP_IO_CAP_NONE);
  bleSecurity->setForceAuthentication(false);
}

void initBleStack() {
  if (BLEDevice::getInitialized()) {
    bleStackReady = true;
    configureBleSecurity();
    return;
  }
  if (WiFi.getMode() != WIFI_MODE_NULL) {
    WiFi.disconnect(true, true);
    WiFi.mode(WIFI_OFF);
    delay(250);
    logMemory("After WiFi shutdown for BLE");
  }
  BLEDevice::init("ESP32-GoPro-Remote");
  configureBleSecurity();
  bleStackReady = true;
  Serial.println("BLE security bonding enabled");
  logMemory("After BLE init");
}

void shutdownBleForWifi() {
  if (!BLEDevice::getInitialized()) {
    return;
  }
  logMemory("Before BLE shutdown");
  if (bleClient != nullptr && bleClient->isConnected()) {
    bleClient->disconnect();
    delay(150);
  }
  bleClient = nullptr;
  bleConnected = false;
  if (bleIndicator) {
    lv_obj_set_style_text_color(bleIndicator, lv_color_hex(0x5a6472), 0);
  }
  clearBleScanDevices();
  BLEDevice::deinit(false);
  bleStackReady = false;
  delay(250);
  logMemory("After BLE shutdown");
}

String trimCopy(String value) {
  value.trim();
  return value;
}

bool containsIgnoreCase(const String &text, const String &needle) {
  String lowerText = text;
  String lowerNeedle = needle;
  lowerText.toLowerCase();
  lowerNeedle.toLowerCase();
  return lowerText.indexOf(lowerNeedle) >= 0;
}

bool nameMatchesFilter(const String &name) {
  if (name.isEmpty()) {
    return false;
  }

  String filters = GOPRO_CAMERA_NAME_FILTER;
  int start = 0;
  while (start < filters.length()) {
    int comma = filters.indexOf(',', start);
    if (comma < 0) {
      comma = filters.length();
    }
    String token = trimCopy(filters.substring(start, comma));
    if (!token.isEmpty() && containsIgnoreCase(name, token)) {
      return true;
    }
    start = comma + 1;
  }
  return false;
}

void loadCameraBinding() {
  preferences.begin("gopro", false);
  boundBleAddress = preferences.getString("ble_addr", "");
  boundBleName = preferences.getString("ble_name", "");
  boundGoProSsid = preferences.getString("wifi_ssid", "");
  goProPassword = preferences.getString("wifi_pass", "");
  if (!boundGoProSsid.isEmpty()) {
    goProSsid = boundGoProSsid;
  }
  if (!boundBleAddress.isEmpty()) {
    boundBleAddress.toLowerCase();
    Serial.print(F("Bound GoPro BLE address: "));
    Serial.println(boundBleAddress);
    if (!boundBleName.isEmpty()) {
      Serial.print(F("Bound GoPro BLE name: "));
      Serial.println(boundBleName);
    }
    if (!boundGoProSsid.isEmpty()) {
      Serial.print(F("Bound GoPro AP SSID: "));
      Serial.println(boundGoProSsid);
      Serial.print(F("Bound GoPro AP password length: "));
      Serial.println(goProPassword.length());
    }
  } else {
    Serial.println(F("No saved GoPro BLE binding"));
  }
}

void saveCameraBindingValues(String address, const String &name) {
  address.toLowerCase();
  if (address.isEmpty()) {
    return;
  }
  bool changed = address != boundBleAddress ||
                 (!name.isEmpty() && name != boundBleName) ||
                 (!goProSsid.isEmpty() && goProSsid != boundGoProSsid) ||
                 (!goProPassword.isEmpty() &&
                  goProPassword != preferences.getString("wifi_pass", ""));
  boundBleAddress = address;
  if (!name.isEmpty()) {
    boundBleName = name;
  }
  if (!goProSsid.isEmpty()) {
    boundGoProSsid = goProSsid;
  }
  preferences.putString("ble_addr", boundBleAddress);
  preferences.putString("ble_name", boundBleName);
  preferences.putString("wifi_ssid", boundGoProSsid);
  if (!goProPassword.isEmpty()) {
    preferences.putString("wifi_pass", goProPassword);
  }
  if (changed) {
    clearSnapshotPreviewState("Double-click lower for snapshot");
  }
  setConnectRetryAvailable(false);
  Serial.print(F("Saved GoPro BLE binding: addr="));
  Serial.println(boundBleAddress);
  Serial.print(F("Saved GoPro BLE name: "));
  if (boundBleName.isEmpty()) {
    Serial.println(F("(unknown)"));
  } else {
    Serial.println(boundBleName);
  }
  Serial.print(F("Saved GoPro AP SSID: "));
  if (boundGoProSsid.isEmpty()) {
    Serial.println(F("(unknown)"));
  } else {
    Serial.println(boundGoProSsid);
  }
  Serial.print(F("Saved GoPro AP password length: "));
  Serial.println(goProPassword.length());
}

void saveCameraBinding(BLEAdvertisedDevice &device) {
  String address = device.getAddress().toString().c_str();
  String name = device.haveName() ? String(device.getName().c_str()) : "";
  saveCameraBindingValues(address, name);
}

int clearBleBondStore() {
  int removed = 0;
  initBleStack();
#if defined(CONFIG_BLUEDROID_ENABLED)
  int devCount = esp_ble_get_bond_device_num();
  if (devCount > 0) {
    esp_ble_bond_dev_t *devices =
        static_cast<esp_ble_bond_dev_t *>(calloc(devCount, sizeof(esp_ble_bond_dev_t)));
    if (devices != nullptr) {
      int listCount = devCount;
      if (esp_ble_get_bond_device_list(&listCount, devices) == ESP_OK) {
        for (int i = 0; i < listCount; ++i) {
          if (esp_ble_remove_bond_device(devices[i].bd_addr) == ESP_OK) {
            removed++;
          }
        }
      }
      free(devices);
    }
  }
#elif defined(CONFIG_NIMBLE_ENABLED)
  int count = 0;
  ble_store_util_count(BLE_STORE_OBJ_TYPE_PEER_SEC, &count);
  if (ble_store_clear() == 0) {
    removed = count;
  }
#endif
  return removed;
}

void forgetCameraBinding(bool preserveCancel = false) {
  pendingHomeAction = PendingHomeAction::None;
  pendingHomeActionDueMs = 0;
  if (pairingInProgress) {
    requestPairingCancel();
  }
  disconnectCurrentCameraForPairing();
  boundBleAddress = "";
  boundBleName = "";
  boundGoProSsid = "";
  goProSsid = "";
  goProPassword = "";
  goProWifiSuspendedForRecording = false;
  lastBleName = "";
  setHomeCameraConnected(false);
  setConnectRetryAvailable(false);
  clearSnapshotPreviewState("Pair New to connect camera");
  bool cleared = preferences.clear();
  int removed = clearBleBondStore();
  resetBleClientForPairing();
  if (!preserveCancel) {
    pairingLastCancelled = false;
    pairingCancelRequested = false;
    connectionCancelRequested = false;
    allowAnyCameraScan = false;
  }
  if (cameraLabel) {
    lv_label_set_text(cameraLabel, "Camera: not paired");
  }
  if (wifiLabel) {
    lv_label_set_text(wifiLabel, "WiFi: idle");
  }
  char label[72];
  snprintf(label, sizeof(label), "Forgot camera; NVS=%s BLE bonds=%d",
           cleared ? "cleared" : "clear failed", removed);
  setAction(label);
  Serial.println(label);
}

void requestPairingCancel() {
  consumeActionButtonPress();
  if (pendingHomeAction == PendingHomeAction::Pair) {
    pendingHomeAction = PendingHomeAction::None;
    pendingHomeActionDueMs = 0;
    hidePairingPopup();
    setAction("Pairing cancelled");
    Serial.println("Pending Pair New cancelled by lower button");
    return;
  }
  if (!pairingInProgress || pairingCancelRequested) {
    return;
  }
  pairingCancelRequested = true;
  setAction("Pairing cancel requested");
  hidePairingPopup();
  Serial.println("Pairing cancel requested by lower button");
}

void requestConnectionCancel(const char *message) {
  connectionCancelRequested = true;
  if (pairingInProgress) {
    pairingCancelRequested = true;
  }
  previewStreamRequested = false;
  if (previewUdpListening) {
    previewUdp.stop();
    previewUdpListening = false;
  }
  goProWifiSuspendedForRecording = false;
  WiFi.scanDelete();
  WiFi.disconnect(false, false);
  if (bleClient != nullptr && bleClient->isConnected()) {
    bleClient->disconnect();
  }
  bleConnected = false;
  if (bleIndicator) {
    lv_obj_set_style_text_color(bleIndicator, lv_color_hex(0x5a6472), 0);
  }
  setHomeCameraConnected(false);
  setAction(message == nullptr ? "Connection cancelled" : message);
}

void pollPairingCancelButton() {
  if (!pairingInProgress || pairingCancelRequested) {
    return;
  }

  if (expanderOnline &&
      expander.digitalRead(kExpanderActionButtonPin) == kExpanderActionPressedLevel) {
    requestPairingCancel();
  }
}

bool pairingCancelled() {
  if (!pairingCancelRequested) {
    return false;
  }
  setAction("Pairing cancelled");
  return true;
}

bool operationCancelled() {
  if (connectionCancelRequested) {
    return true;
  }
  return pairingCancelled();
}

void serviceConnectionUi() {
  if (pairingInProgress && !pairingCancelRequested && pairingPopup) {
    lv_obj_clear_flag(pairingPopup, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_foreground(pairingPopup);
  }
  handleSerialCommands();
  lv_timer_handler();
  pollPairingCancelButton();
  handlePmuActionButton();
}

void servicePairingUi() {
  serviceConnectionUi();
}

bool delayWithConnectionUi(uint32_t durationMs) {
  uint32_t start = millis();
  while (millis() - start < durationMs) {
    serviceConnectionUi();
    if (operationCancelled()) {
      return false;
    }
    delay(25);
  }
  return true;
}

void resetBleClientForPairing() {
  if (bleClient != nullptr && bleClient->isConnected()) {
    bleClient->disconnect();
    delay(150);
  }
  bleClient = nullptr;
  bleConnected = false;
  if (bleIndicator) {
    lv_obj_set_style_text_color(bleIndicator, lv_color_hex(0x5a6472), 0);
  }
  clearBleScanDevices();
}

void disconnectCurrentCameraForPairing() {
  setAction("Disconnecting current camera");
  setHomeCameraConnected(false);
  previewStreamRequested = false;
  previewUdpListening = false;
  snapshotPreviewPrepared = false;
  previewUdp.stop();

  if (bleClient != nullptr && bleClient->isConnected()) {
    bleClient->disconnect();
    delay(150);
  }
  bleClient = nullptr;
  bleConnected = false;
  if (bleIndicator) {
    lv_obj_set_style_text_color(bleIndicator, lv_color_hex(0x5a6472), 0);
  }
  clearBleScanDevices();

  if (WiFi.getMode() != WIFI_MODE_NULL || WiFi.status() == WL_CONNECTED) {
    WiFi.disconnect(true, true);
    WiFi.mode(WIFI_OFF);
    delay(250);
  }
  if (wifiLabel) {
    lv_label_set_text(wifiLabel, "WiFi: disconnected");
  }
  if (wifiIndicator) {
    lv_label_set_text(wifiIndicator, LV_SYMBOL_WIFI);
    lv_obj_set_style_text_color(wifiIndicator, lv_color_hex(0x5a6472), 0);
  }
}

String bytesToString(const String &bytes) {
  String value;
  value.reserve(bytes.length());
  for (size_t i = 0; i < bytes.length(); ++i) {
    char c = bytes.charAt(i);
    if (c != '\0') {
      value += c;
    }
  }
  return value;
}

String bytesToString(const std::string &bytes) {
  String value;
  value.reserve(bytes.length());
  for (char c : bytes) {
    if (c != '\0') {
      value += c;
    }
  }
  return value;
}

void applyCaptureLabels() {
  if (captureModeLabel) {
    lv_label_set_text(captureModeLabel, captureMode.c_str());
  }
  if (captureSettingLabel) {
    lv_label_set_text(captureSettingLabel, captureSetting.c_str());
  }
}

void storeSettingValue(uint16_t id, int option) {
  for (size_t i = 0; i < settingValueCount; ++i) {
    if (settingValues[i].id == id) {
      settingValues[i].option = option;
      return;
    }
  }
  if (settingValueCount < sizeof(settingValues) / sizeof(settingValues[0])) {
    settingValues[settingValueCount++] = {id, option};
  }
}

int getStoredSettingValue(uint16_t id) {
  for (size_t i = 0; i < settingValueCount; ++i) {
    if (settingValues[i].id == id) {
      return settingValues[i].option;
    }
  }
  return -1;
}

int firstStoredSettingValue(const uint16_t *ids, size_t count, int *matchedId = nullptr) {
  for (size_t i = 0; i < count; ++i) {
    int value = getStoredSettingValue(ids[i]);
    if (value >= 0) {
      if (matchedId) {
        *matchedId = ids[i];
      }
      return value;
    }
  }
  if (matchedId) {
    *matchedId = -1;
  }
  return -1;
}

bool addSettingOption(int option, const char *displayName = nullptr) {
  for (size_t i = 0; i < settingOptionCount; ++i) {
    if (settingOptions[i] == option) {
      if (displayName && displayName[0] && settingOptionNames[i].isEmpty()) {
        settingOptionNames[i] = displayName;
      }
      return true;
    }
  }
  if (settingOptionCount >= kMaxSettingOptions) {
    return false;
  }
  settingOptions[settingOptionCount] = option;
  settingOptionNames[settingOptionCount] = displayName ? displayName : "";
  settingOptionCount++;
  return true;
}

void setDisplayOn(bool enabled) {
  displayOn = enabled;
  gfx->setBrightness(enabled ? kDisplayBrightness : 0);
  if (enabled) {
    lv_obj_clear_flag(lv_scr_act(), LV_OBJ_FLAG_HIDDEN);
    lv_label_set_text(statusLabel, recording ? "Recording" : "Display awake");
    setAction("Display on");
  } else {
    lv_label_set_text(statusLabel, "Display sleeping");
    setAction("Display off");
  }
}

void updateBatteryStatus(bool force = false) {
  if (!batteryLabel || (!force && millis() - lastBatteryUpdate < kBatteryRefreshMs)) {
    return;
  }
  lastBatteryUpdate = millis();

  if (!pmuOnline) {
    lv_label_set_text(batteryLabel, LV_SYMBOL_BATTERY_EMPTY);
    lv_obj_set_style_text_color(batteryLabel, lv_color_hex(0x5a6472), 0);
    return;
  }

  int percent = power.getBatteryPercent();
  if (percent < 0) {
    lv_label_set_text(batteryLabel, power.isVbusIn() ? LV_SYMBOL_USB : LV_SYMBOL_BATTERY_EMPTY);
    lv_obj_set_style_text_color(batteryLabel, lv_color_hex(0xc3ccd8), 0);
    return;
  }

  percent = constrain(percent, 0, 100);
  if (percent <= 15) {
    lv_obj_set_style_text_color(batteryLabel, lv_color_hex(0xf03e3e), 0);
  } else if (percent <= 35) {
    lv_obj_set_style_text_color(batteryLabel, lv_color_hex(0xf0b429), 0);
  } else {
    lv_obj_set_style_text_color(batteryLabel, lv_color_hex(0x47d16c), 0);
  }

  if (percent <= 15) {
    lv_label_set_text(batteryLabel, LV_SYMBOL_BATTERY_1);
  } else if (percent <= 35) {
    lv_label_set_text(batteryLabel, LV_SYMBOL_BATTERY_2);
  } else if (percent <= 70) {
    lv_label_set_text(batteryLabel, LV_SYMBOL_BATTERY_3);
  } else {
    lv_label_set_text(batteryLabel, LV_SYMBOL_BATTERY_FULL);
  }
}

void enterLowPowerShutdown() {
  recording = false;
  WiFi.disconnect(true, true);
  WiFi.mode(WIFI_OFF);

  if (statusLabel) {
    lv_label_set_text(statusLabel, "Powering off");
  }
  if (actionLabel) {
    lv_label_set_text(actionLabel, "Low-power shutdown");
  }
  lv_timer_handler();
  gfx->setBrightness(0);
  Serial.println("Entering low-power shutdown");
  delay(200);

  if (pmuOnline) {
    power.setPowerKeyPressOnTime(XPOWERS_POWERON_1S);
    power.setPowerKeyPressOffTime(XPOWERS_POWEROFF_4S);
    power.setLongPressPowerOFF();
    power.enableLongPressShutdown();
    power.shutdown();
  }

  esp_sleep_enable_ext0_wakeup(GPIO_NUM_0, 0);
  esp_deep_sleep_start();
}

String cameraBaseUrl() {
  return String("http://") + cameraIp.toString() + ":8080";
}

void clearGoProWifiScanTarget() {
  goProWifiChannel = 0;
  memset(goProWifiBssid, 0, sizeof(goProWifiBssid));
  goProWifiBssidValid = false;
}

String formatBssid(const uint8_t *bssid) {
  if (bssid == nullptr) {
    return String("(none)");
  }
  char text[18];
  snprintf(text, sizeof(text), "%02X:%02X:%02X:%02X:%02X:%02X",
           bssid[0], bssid[1], bssid[2], bssid[3], bssid[4], bssid[5]);
  return String(text);
}

void prepareWifiSta(const char *reason) {
  Serial.print(F("Preparing WiFi STA"));
  if (reason != nullptr && reason[0] != '\0') {
    Serial.print(F(": "));
    Serial.print(reason);
  }
  Serial.println();
  WiFi.persistent(false);
  WiFi.setSleep(false);
  WiFi.mode(WIFI_OFF);
  delay(250);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
}

void commandResponseNotify(BLERemoteCharacteristic *, uint8_t *data, size_t length, bool) {
  Serial.print(F("BLE command response:"));
  for (size_t i = 0; i < length; ++i) {
    Serial.print(' ');
    if (data[i] < 0x10) {
      Serial.print('0');
    }
    Serial.print(data[i], HEX);
  }
  Serial.println();
  bleResponseStatus = length > 0 ? data[0] : 0x00;
  bleResponseSeen = true;
}

bool waitForBleResponse(uint32_t timeoutMs) {
  uint32_t start = millis();
  while (!bleResponseSeen && millis() - start < timeoutMs) {
    serviceConnectionUi();
    if (operationCancelled()) {
      return false;
    }
    delay(20);
  }
  if (!bleResponseSeen) {
    setAction("BLE command response timeout");
    return false;
  }
  return true;
}

class ScanCallbacks : public BLEAdvertisedDeviceCallbacks {
 public:
  void onResult(BLEAdvertisedDevice device) override {
    String name = device.haveName() ? String(device.getName().c_str()) : "";
    bool hasControlService = device.haveServiceUUID() && device.isAdvertisingService(kControlService);
    String address = device.getAddress().toString().c_str();
    address.toLowerCase();
    bleScanSeenCount++;

    if (allowAnyCameraScan) {
      bool logDevice = hasControlService || !name.isEmpty() || device.getRSSI() >= kPairScanLogMinRssi;
      if (logDevice) {
        Serial.print(F("BLE seen: "));
        Serial.print(name.isEmpty() ? F("(no name)") : name);
        Serial.print(F(" rssi="));
        Serial.print(device.getRSSI());
        Serial.print(F(" addr="));
        Serial.print(device.getAddress().toString().c_str());
        Serial.print(F(" goproService="));
        Serial.println(hasControlService ? 1 : 0);
      }
      if (device.getRSSI() >= kPairFallbackMinRssi &&
          (fallbackBleDevice == nullptr || device.getRSSI() > fallbackBleDevice->getRSSI())) {
        delete fallbackBleDevice;
        fallbackBleDevice = new BLEAdvertisedDevice(device);
      }
    }

    if (!hasControlService && !nameMatchesFilter(name)) {
      return;
    }
    bleScanCandidateCount++;
    bool addressMatches = !boundBleAddress.isEmpty() && address == boundBleAddress;
    bool nameMatchesSaved =
        !boundBleName.isEmpty() && !name.isEmpty() && name == boundBleName && hasControlService;
    if (addressMatches) {
      bleScanAddressMatchCount++;
    }
    if (nameMatchesSaved) {
      bleScanNameMatchCount++;
    }

    if (!allowAnyCameraScan && !addressMatches && !nameMatchesSaved) {
      bleScanSkippedCount++;
      Serial.print(F("Skipping unbound GoPro BLE addr="));
      Serial.print(address);
      if (!name.isEmpty()) {
        Serial.print(F(" name="));
        Serial.print(name);
      }
      Serial.println();
      return;
    }

    Serial.print(F("BLE candidate: "));
    Serial.print(name.isEmpty() ? F("(no name)") : name);
    Serial.print(F(" rssi="));
    Serial.print(device.getRSSI());
    Serial.print(F(" addr="));
    Serial.print(device.getAddress().toString().c_str());
    if (!addressMatches && nameMatchesSaved) {
      Serial.print(F(" saved-name-match"));
    }
    Serial.println();

    if (bestBleDevice == nullptr || device.getRSSI() > bestBleDevice->getRSSI()) {
      delete bestBleDevice;
      bestBleDevice = new BLEAdvertisedDevice(device);
    }
  }
};

bool scanForCamera() {
  if (boundBleAddress.isEmpty() && !allowAnyCameraScan) {
    lv_label_set_text(cameraLabel, "Camera: not paired");
    setAction("No saved camera; tap Pair New");
    Serial.println("BLE scan blocked: no saved camera binding");
    return false;
  }

  initBleStack();
  clearBleScanDevices();
  selectedBleFallback = false;
  bleScanCandidateCount = 0;
  bleScanSkippedCount = 0;
  bleScanAddressMatchCount = 0;
  bleScanNameMatchCount = 0;
  bleScanSeenCount = 0;

  lv_label_set_text(statusLabel, "Scanning BLE");
  setAction(boundBleAddress.isEmpty() || allowAnyCameraScan
                ? "Scanning for GoPro BLE"
                : "Scanning for bound GoPro");
  lv_timer_handler();

  BLEScan *scan = BLEDevice::getScan();
  ScanCallbacks callbacks;
  scan->setAdvertisedDeviceCallbacks(&callbacks, false);
  scan->setActiveScan(true);
  scan->setInterval(100);
  scan->setWindow(99);
  uint32_t scanSeconds = pairingInProgress ? kPairBleScanSeconds : kBleScanSeconds;
  for (uint32_t elapsed = 0; elapsed < scanSeconds; ++elapsed) {
    if (operationCancelled()) {
      scan->clearResults();
      return false;
    }
    scan->start(1, false);
    serviceConnectionUi();
    if (operationCancelled()) {
      scan->clearResults();
      return false;
    }
    if (bestBleDevice != nullptr) {
      Serial.println(F("BLE scan found matching GoPro; stopping scan early"));
      break;
    }
  }
  scan->clearResults();

  if (bestBleDevice == nullptr && allowAnyCameraScan && fallbackBleDevice != nullptr) {
    bestBleDevice = fallbackBleDevice;
    fallbackBleDevice = nullptr;
    selectedBleFallback = true;
    Serial.print(F("No named GoPro advertisement found; trying strongest nearby BLE device addr="));
    Serial.print(bestBleDevice->getAddress().toString().c_str());
    Serial.print(F(" rssi="));
    Serial.println(bestBleDevice->getRSSI());
    setAction("Trying nearest BLE device");
  }

  if (bestBleDevice == nullptr) {
    lv_label_set_text(cameraLabel, "Camera: BLE not found");
    Serial.printf("BLE scan finished: seen=%u candidates=%u skipped=%u addr_matches=%u name_matches=%u saved_addr='%s' saved_name='%s'\n",
                  bleScanSeenCount, bleScanCandidateCount, bleScanSkippedCount,
                  bleScanAddressMatchCount, bleScanNameMatchCount,
                  boundBleAddress.c_str(), boundBleName.c_str());
    if (boundBleAddress.isEmpty() || allowAnyCameraScan) {
      setAction("No GoPro BLE device found");
    } else {
      setConnectRetryAvailable(true);
      setAction("Bound GoPro BLE not found; tap Scan Again");
    }
    return false;
  }

  delete fallbackBleDevice;
  fallbackBleDevice = nullptr;
  lastBleName = bestBleDevice->haveName() ? String(bestBleDevice->getName().c_str()) : "";
  String label = "Camera: ";
  label += lastBleName.isEmpty() ? bestBleDevice->getAddress().toString().c_str() : lastBleName;
  lv_label_set_text(cameraLabel, label.c_str());
  Serial.print(F("Selected BLE device: "));
  Serial.println(label);
  return true;
}

bool connectBle() {
  initBleStack();
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

  if (bleClient == nullptr) {
    bleClient = BLEDevice::createClient();
  }

  lv_label_set_text(statusLabel, "Connecting BLE");
  setAction("Connecting GoPro BLE");
  serviceConnectionUi();
  logMemory("Before BLE connect");
  uint32_t connectTimeoutMs = pairingInProgress ? kPairBleConnectTimeoutMs : kBleConnectTimeoutMs;
  if (!bleClient->connectTimeout(bestBleDevice, connectTimeoutMs)) {
    bleConnected = false;
    if (bleIndicator) {
      lv_obj_set_style_text_color(bleIndicator, lv_color_hex(0x5a6472), 0);
    }
    delete bleClient;
    bleClient = nullptr;
    clearBleScanDevices();
    lv_label_set_text(cameraLabel, "Camera: BLE connect failed");
    if (selectedBleFallback) {
      setAction("No GoPro BLE advertisement found");
    } else if (!boundBleAddress.isEmpty() && !allowAnyCameraScan) {
      setConnectRetryAvailable(true);
      setAction("BLE connect failed; tap Scan Again");
    } else {
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
  }

  lv_label_set_text(statusLabel, "BLE connected");
  setAction("BLE connected");
  lv_timer_handler();
  return true;
}

bool readGoProWifiCredentials() {
  if (!connectBle()) {
    return false;
  }
  if (operationCancelled()) {
    return false;
  }

  BLERemoteService *wifi = bleClient->getService(kWifiService);
  if (wifi == nullptr) {
    setAction(selectedBleFallback ? "Nearest BLE device is not a GoPro"
                                  : "GoPro WiFi BLE service missing");
    return false;
  }

  BLERemoteCharacteristic *ssid = wifi->getCharacteristic(kWifiSsid);
  BLERemoteCharacteristic *password = wifi->getCharacteristic(kWifiPassword);
  if (ssid == nullptr || password == nullptr || !ssid->canRead() || !password->canRead()) {
    setAction("GoPro WiFi credentials unreadable");
    return false;
  }

  goProSsid = bytesToString(ssid->readValue());
  goProPassword = bytesToString(password->readValue());
  if (operationCancelled()) {
    return false;
  }

  Serial.print(F("GoPro AP SSID: "));
  Serial.println(goProSsid);
  Serial.print(F("GoPro AP password length: "));
  Serial.println(goProPassword.length());
#if GOPRO_DEBUG_PRINT_CAMERA_PASSWORD
  Serial.print(F("GoPro AP password: "));
  Serial.println(goProPassword);
#endif
  if (goProSsid.isEmpty() || goProPassword.isEmpty()) {
    setAction("GoPro WiFi credentials empty");
    return false;
  }
  String label = "Camera AP: ";
  label += goProSsid;
  lv_label_set_text(cameraLabel, label.c_str());
  setAction("Read GoPro WiFi over BLE");
  return true;
}

bool sendBleCommand(const uint8_t *payload, size_t length) {
  if (!connectBle()) {
    return false;
  }

  BLERemoteService *control = bleClient->getService(kControlService);
  if (control == nullptr) {
    setAction("GoPro control BLE service missing");
    return false;
  }

  BLERemoteCharacteristic *command = control->getCharacteristic(kCommand);
  if (command == nullptr || !command->canWrite()) {
    setAction("GoPro command characteristic missing");
    return false;
  }

  bleResponseSeen = false;
  bleResponseStatus = 0xFF;
  command->writeValue(const_cast<uint8_t *>(payload), length, true);
  return waitForBleResponse(2500);
}

bool setGoProShutterBle(bool enabled) {
  uint8_t payload[] = {0x03, 0x01, 0x01, static_cast<uint8_t>(enabled ? 0x01 : 0x00)};
  setAction(enabled ? "Starting recording over BLE" : "Stopping recording over BLE");
  return sendBleCommand(payload, sizeof(payload));
}

bool setGoProWifiApBle(bool enabled) {
  uint8_t payload[] = {0x03, 0x17, 0x01, static_cast<uint8_t>(enabled ? 0x01 : 0x00)};
  setAction(enabled ? "Enabling GoPro WiFi AP" : "Disabling GoPro WiFi AP");
  return sendBleCommand(payload, sizeof(payload));
}

bool sendBleSetting(uint8_t settingId, uint8_t optionId, const char *label) {
  if (!connectBle()) {
    return false;
  }

  BLERemoteService *control = bleClient->getService(kControlService);
  if (control == nullptr) {
    setAction("GoPro control BLE service missing");
    return false;
  }

  BLERemoteCharacteristic *response = control->getCharacteristic(kSettingsResponse);
  if (response != nullptr && response->canNotify()) {
    response->registerForNotify(commandResponseNotify);
  }

  BLERemoteCharacteristic *settings = control->getCharacteristic(kSettings);
  if (settings == nullptr || !settings->canWrite()) {
    setAction("GoPro settings characteristic missing");
    return false;
  }

  uint8_t payload[] = {0x03, settingId, 0x01, optionId};
  bleResponseSeen = false;
  bleResponseStatus = 0xFF;
  settings->writeValue(payload, sizeof(payload), true);
  bool ok = waitForBleResponse(2500);
  setAction(ok ? label : "BLE setting response timeout");
  return ok;
}

bool forceGoProWifi24GHz() {
  for (uint8_t attempt = 1; attempt <= 2; ++attempt) {
    if (operationCancelled()) {
      return false;
    }
    lv_label_set_text(statusLabel, "Setting WiFi 2.4GHz");
    setAction(attempt == 1 ? "Forcing GoPro WiFi to 2.4GHz"
                           : "Retrying GoPro WiFi 2.4GHz");
    if (sendBleSetting(kGoProWirelessBandSetting, kGoProWirelessBand24GHz,
                       "GoPro WiFi band: 2.4GHz")) {
      delayWithConnectionUi(500);
      return true;
    }
    if (operationCancelled()) {
      return false;
    }
    delayWithConnectionUi(500);
  }
  setAction("GoPro WiFi band set failed");
  return false;
}

bool sendCameraManagementCommand(const uint8_t *payload, size_t length) {
  if (!connectBle()) {
    return false;
  }
  if (operationCancelled()) {
    return false;
  }

  BLERemoteService *management = bleClient->getService(kCameraManagementService);
  if (management == nullptr) {
    setAction("GoPro pairing service missing");
    return false;
  }

  BLERemoteCharacteristic *response = management->getCharacteristic(kCameraManagementResponse);
  if (response != nullptr && response->canNotify()) {
    response->registerForNotify(commandResponseNotify);
  }

  BLERemoteCharacteristic *command = management->getCharacteristic(kCameraManagementCommand);
  if (command == nullptr || !command->canWrite()) {
    setAction("GoPro pairing command missing");
    return false;
  }

  bleResponseSeen = false;
  bleResponseStatus = 0xFF;
  command->writeValue(const_cast<uint8_t *>(payload), length, true);
  return waitForBleResponse(4000);
}

bool pairGoPro() {
  bool previousAllowAny = allowAnyCameraScan;
  String previousBoundBleAddress = boundBleAddress;
  String previousBoundBleName = boundBleName;
  String previousBoundGoProSsid = boundGoProSsid;
  String previousSsid = goProSsid;
  String previousPassword = goProPassword;
  allowAnyCameraScan = true;
  pairingInProgress = true;
  pairingCancelRequested = false;
  pairingLastCancelled = false;
  showPairingPopup("Pairing New Camera\n\nDisconnecting current camera...");
  disconnectCurrentCameraForPairing();
  resetBleClientForPairing();

  const char controllerName[] = "ESP32";
  uint8_t request[1 + 2 + 2 + 2 + sizeof(controllerName) - 1] = {
      0x0B,
      0x03,
      0x01,
      0x08,
      0x00,
      0x12,
      static_cast<uint8_t>(sizeof(controllerName) - 1),
      'E',
      'S',
      'P',
      '3',
      '2',
  };
  lv_label_set_text(statusLabel, "Pairing BLE");
  lv_label_set_text(cameraLabel, "Camera: use GoPro pairing mode");
  showPairingPopup("Pairing New Camera\n\nPut the GoPro in pairing mode.\nPress lower button to cancel.");
  setAction("Pairing with GoPro BLE");
  lv_timer_handler();

  bool ok = false;
  if (readGoProWifiCredentials() && !operationCancelled()) {
    setAction("Finishing GoPro pairing");
    ok = sendCameraManagementCommand(request, sizeof(request));
    if (ok && !operationCancelled() && bestBleDevice != nullptr) {
      saveCameraBinding(*bestBleDevice);
    }
  } else if (!operationCancelled()) {
    setAction(selectedBleFallback ? "No Open GoPro BLE device found"
                                  : "BLE security pairing failed");
  }

  if (operationCancelled()) {
    ok = false;
    setAction(connectionCancelRequested ? "Connection cancelled" : "Pairing cancelled");
  }
  if (!ok) {
    if (!connectionCancelRequested) {
      boundBleAddress = previousBoundBleAddress;
      boundBleName = previousBoundBleName;
      boundGoProSsid = previousBoundGoProSsid;
      goProSsid = previousSsid;
      goProPassword = previousPassword;
      setConnectRetryAvailable(!boundBleAddress.isEmpty());
    }
    resetBleClientForPairing();
    if (operationCancelled()) {
      hidePairingPopup();
    } else {
      finishPairingPopup("Pairing Failed\n\nSaved camera is unchanged.");
    }
  } else {
    finishPairingPopup("Pairing Complete\n\nSaved new camera.");
  }
  allowAnyCameraScan = previousAllowAny;
  pairingInProgress = false;
  pairingLastCancelled = pairingCancelRequested || connectionCancelRequested;
  pairingCancelRequested = false;
  return ok;
}

void markGoProWifiDisconnectedForRecording() {
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
}

void suspendGoProWifiForRecording(const char *reason) {
  Serial.print("Suspending GoPro WiFi for recording");
  if (reason != nullptr && reason[0]) {
    Serial.print(": ");
    Serial.print(reason);
  }
  Serial.println();

  markGoProWifiDisconnectedForRecording();
  if (setGoProWifiApBle(false)) {
    setAction("Recording; WiFi AP off");
  } else {
    setAction("Recording; local WiFi off");
  }
  lv_timer_handler();
}

bool enableGoProWifiAp() {
  if (!forceGoProWifi24GHz()) {
    if (operationCancelled()) {
      return false;
    }
    setAction("2.4GHz not confirmed; trying AP");
    if (!delayWithConnectionUi(500)) {
      return false;
    }
  }
  if (operationCancelled()) {
    return false;
  }
  lv_label_set_text(statusLabel, "Enabling GoPro AP");
  setAction("Enabling GoPro WiFi AP over BLE");
  bool ok = setGoProWifiApBle(true);
  if (ok) {
    goProWifiSuspendedForRecording = false;
  }
  return ok;
}

bool waitForGoProApVisible() {
  if (goProSsid.isEmpty()) {
    return false;
  }
  clearGoProWifiScanTarget();
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.disconnect(false, false);
  WiFi.scanDelete();
  if (!delayWithConnectionUi(500)) {
    return false;
  }
  lv_label_set_text(statusLabel, "Waiting for camera AP");
  setAction("Waiting for GoPro WiFi AP");
  Serial.printf("Waiting for GoPro AP ssid='%s' passwordLen=%u\n",
                goProSsid.c_str(), static_cast<unsigned>(goProPassword.length()));
  uint32_t start = millis();
  while (millis() - start < kWifiTimeoutMs) {
    if (operationCancelled()) {
      return false;
    }
    int count = WiFi.scanNetworks(false, true);
    if (operationCancelled()) {
      WiFi.scanDelete();
      return false;
    }
    bool found = false;
    Serial.printf("WiFi scan found %d networks\n", count);
    for (int i = 0; i < count; ++i) {
      Serial.printf("  ssid='%s' rssi=%d channel=%d bssid=%s auth=%d\n",
                    WiFi.SSID(i).c_str(), WiFi.RSSI(i), WiFi.channel(i),
                    WiFi.BSSIDstr(i).c_str(), static_cast<int>(WiFi.encryptionType(i)));
      if (WiFi.SSID(i) == goProSsid) {
        found = true;
        goProWifiChannel = WiFi.channel(i);
        uint8_t *bssid = WiFi.BSSID(i);
        if (bssid != nullptr) {
          memcpy(goProWifiBssid, bssid, sizeof(goProWifiBssid));
          goProWifiBssidValid = true;
        }
      }
    }
    WiFi.scanDelete();
    if (found) {
      Serial.printf("Matched GoPro AP channel=%d bssid=%s\n",
                    static_cast<int>(goProWifiChannel),
                    goProWifiBssidValid ? formatBssid(goProWifiBssid).c_str() : "(none)");
      return true;
    }
    if (!delayWithConnectionUi(1000)) {
      return false;
    }
  }
  setAction("GoPro WiFi AP not visible");
  return false;
}

bool tryJoinGoProWifi(uint32_t timeoutMs) {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.disconnect(false, false);
  if (!delayWithConnectionUi(500)) {
    return false;
  }
  logMemory("Before WiFi begin");
  Serial.printf("Joining GoPro WiFi ssid='%s' passwordLen=%u channel=%d bssid=%s\n",
                goProSsid.c_str(), static_cast<unsigned>(goProPassword.length()),
                static_cast<int>(goProWifiChannel),
                goProWifiBssidValid ? formatBssid(goProWifiBssid).c_str() : "(none)");
  if (goProWifiBssidValid && goProWifiChannel > 0) {
    WiFi.begin(goProSsid.c_str(), goProPassword.c_str(), goProWifiChannel, goProWifiBssid);
  } else if (goProWifiChannel > 0) {
    WiFi.begin(goProSsid.c_str(), goProPassword.c_str(), goProWifiChannel);
  } else {
    WiFi.begin(goProSsid.c_str(), goProPassword.c_str());
  }

  uint32_t start = millis();
  uint8_t lastStatus = 0xFF;
  while (millis() - start < timeoutMs) {
    serviceConnectionUi();
    if (operationCancelled()) {
      return false;
    }
    uint8_t status = WiFi.status();
    if (status != lastStatus) {
      lastStatus = status;
      Serial.printf("WiFi status=%u\n", status);
    }
    if (status == WL_CONNECTED) {
      return true;
    }
    delay(250);
  }
  Serial.printf("WiFi join timed out status=%u\n", WiFi.status());
  return false;
}

bool isLikelyGoProWifiConnected() {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }
  if (!goProSsid.isEmpty() && WiFi.SSID() == goProSsid) {
    return true;
  }
  IPAddress ip = WiFi.localIP();
  return ip[0] == 10 && ip[1] == 5 && ip[2] == 5;
}

bool goProHttpReachable() {
  int status = httpGetGoProStatus("/gopro/camera/state");
  bool ok = status == 200;
  Serial.printf("GoPro HTTP reachability status=%d\n", status);
  return ok;
}

void markExistingGoProWifiConnected() {
  if (wifiLabel) {
    String text = "WiFi: ";
    text += WiFi.localIP().toString();
    lv_label_set_text(wifiLabel, text.c_str());
  }
  if (statusLabel) {
    lv_label_set_text(statusLabel, "GoPro WiFi connected");
  }
  if (wifiIndicator) {
    lv_label_set_text(wifiIndicator, LV_SYMBOL_WIFI);
    lv_obj_set_style_text_color(wifiIndicator, lv_color_hex(0x47d16c), 0);
  }
  setHomeCameraConnected(true);
}

bool connectGoProWifiWithCurrentCredentials(const char *reason) {
  if (goProSsid.isEmpty() || goProPassword.isEmpty()) {
    Serial.println("No GoPro WiFi credentials available for direct join");
    return false;
  }

  shutdownBleForWifi();
  WiFi.useStaticBuffers(false);
  prepareWifiSta(reason == nullptr ? "known credentials" : reason);
  WiFi.disconnect(false, false);
  if (!delayWithConnectionUi(1000)) {
    return false;
  }

  if (!waitForGoProApVisible()) {
    lv_label_set_text(wifiLabel, "WiFi: GoPro AP not visible");
    return false;
  }

  String label = "Joining ";
  label += goProSsid;
  lv_label_set_text(statusLabel, label.c_str());
  setAction(label.c_str());

  if (!tryJoinGoProWifi(15000) && !operationCancelled() && !tryJoinGoProWifi(15000)) {
    lv_label_set_text(wifiLabel, "WiFi: GoPro AP failed");
    setAction("Direct GoPro WiFi join failed");
    waitForGoProApVisible();
    return false;
  }
  if (operationCancelled()) {
    return false;
  }

  markExistingGoProWifiConnected();
  setAction("Connected to GoPro WiFi");
  syncCameraState();
  lastPreviewUpdate = 0;
  if (recording) {
    suspendGoProWifiForRecording("camera already recording");
    return true;
  }
  if (previewLabel && !previewHasImage) {
    lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    lv_label_set_text(previewLabel, "Double-click lower for snapshot");
  }
  return true;
}

bool connectGoProWifiFromBle() {
  if (operationCancelled()) {
    return false;
  }
  if (isLikelyGoProWifiConnected()) {
    goProWifiSuspendedForRecording = false;
    markExistingGoProWifiConnected();
    setAction("Using existing GoPro WiFi");
    return true;
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

  if (!connectGoProWifiWithCurrentCredentials("BLE handoff")) {
    return false;
  }
  return true;
}

bool ensureGoProWifiReady(const char *reason) {
  if (isLikelyGoProWifiConnected()) {
    markExistingGoProWifiConnected();
    if (goProHttpReachable()) {
      setAction(reason == nullptr ? "Using existing GoPro WiFi" : reason);
      return true;
    }
    setAction("GoPro HTTP stale; reconnecting WiFi");
    Serial.println("GoPro WiFi association is stale; forcing BLE WiFi handoff");
    WiFi.disconnect(false, false);
    delay(300);
    setHomeCameraConnected(false);
  }
  if (!goProWifiSuspendedForRecording && !goProSsid.isEmpty() && !goProPassword.isEmpty() &&
      connectGoProWifiWithCurrentCredentials("known credentials")) {
    return true;
  }
  return connectGoProWifiFromBle();
}

bool httpGetGoPro(const String &path) {
  if (WiFi.status() != WL_CONNECTED) {
    setAction("WiFi not connected");
    return false;
  }

  HTTPClient http;
  http.setTimeout(kHttpTimeoutMs);
  String url = cameraBaseUrl() + path;
  if (!http.begin(url)) {
    setAction("HTTP begin failed");
    return false;
  }
  int status = http.GET();
  http.end();
  Serial.printf("GET %s -> %d\n", url.c_str(), status);
  return status >= 200 && status < 300;
}

int httpGetGoProStatus(const String &path) {
  if (WiFi.status() != WL_CONNECTED) {
    setAction("WiFi not connected");
    return -1;
  }

  HTTPClient http;
  http.setTimeout(kHttpTimeoutMs);
  String url = cameraBaseUrl() + path;
  if (!http.begin(url)) {
    setAction("HTTP begin failed");
    return -1;
  }
  int status = http.GET();
  http.end();
  Serial.printf("GET %s -> %d\n", url.c_str(), status);
  return status;
}

int httpGetGoProBody(const String &path, String &body) {
  body = "";
  if (WiFi.status() != WL_CONNECTED) {
    setAction("WiFi not connected");
    return -1;
  }

  HTTPClient http;
  http.setTimeout(kHttpTimeoutMs);
  String url = cameraBaseUrl() + path;
  if (!http.begin(url)) {
    setAction("HTTP begin failed");
    return -1;
  }
  int status = http.GET();
  body = http.getString();
  http.end();
  Serial.printf("GET %s -> %d, %u bytes\n", url.c_str(), status, body.length());
  return status;
}

String urlEncodePathParam(const String &value) {
  const char *hex = "0123456789ABCDEF";
  String encoded;
  encoded.reserve(value.length() + 8);
  for (size_t i = 0; i < value.length(); ++i) {
    uint8_t c = static_cast<uint8_t>(value[i]);
    bool safe = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
                (c >= '0' && c <= '9') || c == '/' || c == '.' ||
                c == '-' || c == '_' || c == '~';
    if (safe) {
      encoded += static_cast<char>(c);
    } else {
      encoded += '%';
      encoded += hex[c >> 4];
      encoded += hex[c & 0x0f];
    }
  }
  return encoded;
}

bool httpGetGoProBinary(const String &path, uint8_t *buffer, size_t capacity, size_t &length) {
  length = 0;
  if (WiFi.status() != WL_CONNECTED) {
    setAction("WiFi not connected");
    return false;
  }

  HTTPClient http;
  http.setTimeout(kHttpTimeoutMs);
  String url = cameraBaseUrl() + path;
  if (!http.begin(url)) {
    setAction("HTTP begin failed");
    return false;
  }

  int status = http.GET();
  Serial.printf("GET %s -> %d\n", url.c_str(), status);
  if (status < 200 || status >= 300) {
    http.end();
    return false;
  }

  WiFiClient *stream = http.getStreamPtr();
  int remaining = http.getSize();
  uint32_t start = millis();
  while (http.connected() && (remaining > 0 || remaining == -1)) {
    size_t available = stream->available();
    if (available == 0) {
      if (remaining == 0 || millis() - start > kHttpTimeoutMs) {
        break;
      }
      delay(5);
      continue;
    }

    size_t toRead = min(available, capacity - length);
    if (toRead == 0) {
      http.end();
      setAction("JPEG buffer full");
      return false;
    }
    int readLen = stream->readBytes(buffer + length, toRead);
    if (readLen <= 0) {
      break;
    }
    length += static_cast<size_t>(readLen);
    if (remaining > 0) {
      remaining -= readLen;
    }
    start = millis();
  }

  http.end();
  Serial.printf("Binary %s -> %u bytes\n", path.c_str(), length);
  return length > 0;
}

bool parseLatestJpegPath(const String &mediaList, String &path) {
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, mediaList);
  if (error) {
    Serial.print(F("media/list JSON parse failed: "));
    Serial.println(error.c_str());
    return false;
  }

  uint32_t bestCreated = 0;
  uint32_t bestModified = 0;
  String bestPath;
  JsonArray media = doc["media"].as<JsonArray>();
  for (JsonObject directory : media) {
    const char *folder = directory["d"] | "";
    JsonArray files = directory["fs"].as<JsonArray>();
    for (JsonObject file : files) {
      const char *name = file["n"] | "";
      String fileName(name);
      fileName.toUpperCase();
      if (!fileName.endsWith(".JPG")) {
        continue;
      }
      uint32_t created = strtoul(file["cre"] | "0", nullptr, 10);
      uint32_t modified = strtoul(file["mod"] | "0", nullptr, 10);
      String candidate = String(folder) + "/" + name;
      if (bestPath.isEmpty() || created > bestCreated ||
          (created == bestCreated && modified > bestModified) ||
          (created == bestCreated && modified == bestModified && candidate > bestPath)) {
        bestPath = candidate;
        bestCreated = created;
        bestModified = modified;
      }
    }
  }

  path = bestPath;
  return !path.isEmpty();
}

bool fetchLatestJpegPath(String &path) {
  String body;
  int status = httpGetGoProBody("/gopro/media/list", body);
  if (status < 200 || status >= 300) {
    return false;
  }
  return parseLatestJpegPath(body, path);
}

bool deleteGoProMedia(const String &path) {
  if (path.isEmpty()) {
    return false;
  }
  String endpoint = "/gopro/media/delete/file?path=" + urlEncodePathParam(path);
  return httpGetGoPro(endpoint);
}
