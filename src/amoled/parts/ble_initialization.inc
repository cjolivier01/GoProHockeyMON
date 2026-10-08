// BLE initialization can fail during the Wi-Fi handoff. Keep the camera's
// confirmed recording state even if its control connection cannot be created.
bool initBleStack() {
  if (!stopCameraPresetPoll()) {
    bleStackReady = false;
    return false;
  }
  if (BLEDevice::getInitialized()) {
    bleStackReady = true;
    configureBleSecurity();
    return true;
  }
  bleStackReady = false;
  bleConnected = false;
  if (WiFi.getMode() != WIFI_MODE_NULL) {
    WiFi.disconnect(true, true);
    WiFi.mode(WIFI_OFF);
    delay(250);
    logMemory("After WiFi shutdown for BLE");
  }
  // Check the resulting state instead of depending on the return type: older
  // Arduino BLE versions expose a void init(), while current versions return bool.
  BLEDevice::init("ESP32-GoPro-Remote");
  if (!BLEDevice::getInitialized()) {
    setAction("BLE initialization failed");
    logMemory("BLE initialization failed");
    return false;
  }
  configureBleSecurity();
  bleStackReady = true;
  Serial.println("BLE security bonding enabled");
  logMemory("After BLE init");
  return true;
}

BLEScan *getGoProBleScanner() {
  if (!initBleStack()) {
    return nullptr;
  }
  BLEScan *scan = BLEDevice::getScan();
  if (!scan) {
    bleConnected = false;
    setAction("BLE scanner unavailable");
  }
  return scan;
}

bool ensureGoProBleClient() {
  if (!initBleStack()) {
    return false;
  }
  if (!bleClient) {
    bleClient = BLEDevice::createClient();
  }
  if (!bleClient) {
    bleConnected = false;
    setAction("BLE client unavailable");
    return false;
  }
  return true;
}
