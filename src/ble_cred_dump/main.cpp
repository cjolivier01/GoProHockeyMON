#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEScan.h>
#include <WiFi.h>

#ifndef GOPRO_CAMERA_NAME_FILTER
#define GOPRO_CAMERA_NAME_FILTER "GoPro,MISSION,GP"
#endif

#ifndef GOPRO_DEBUG_PRINT_CAMERA_PASSWORD
#define GOPRO_DEBUG_PRINT_CAMERA_PASSWORD 0
#endif

namespace {
constexpr uint32_t kBleScanSeconds = 8;
constexpr uint32_t kBleConnectTimeoutMs = 12000;

const BLEUUID kControlService("0000fea6-0000-1000-8000-00805f9b34fb");
const BLEUUID kWifiService("b5f90001-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kWifiSsid("b5f90002-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kWifiPassword("b5f90003-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kCommand("b5f90072-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kCommandResponse("b5f90073-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kSettings("b5f90074-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kSettingsResponse("b5f90075-aa8d-11e3-9046-0002a5d5c51b");

BLEAdvertisedDevice *bestBleDevice = nullptr;
BLEClient *bleClient = nullptr;
BLESecurityCallbacks *bleSecurityCallbacks = nullptr;
BLESecurity *bleSecurity = nullptr;
volatile bool bleResponseSeen = false;
volatile uint8_t bleResponseStatus = 0xff;

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
    configureBleSecurity();
    return;
  }
  WiFi.disconnect(true, true);
  WiFi.mode(WIFI_OFF);
  delay(250);
  BLEDevice::init("ESP32-GoPro-Dump");
  configureBleSecurity();
  Serial.println("BLE security bonding enabled");
}

class ScanCallbacks : public BLEAdvertisedDeviceCallbacks {
 public:
  void onResult(BLEAdvertisedDevice device) override {
    String name = device.haveName() ? String(device.getName().c_str()) : "";
    bool hasControlService = device.haveServiceUUID() && device.isAdvertisingService(kControlService);
    if (!hasControlService && !nameMatchesFilter(name)) {
      return;
    }

    Serial.print(F("BLE candidate: "));
    Serial.print(name.isEmpty() ? F("(no name)") : name);
    Serial.print(F(" rssi="));
    Serial.print(device.getRSSI());
    Serial.print(F(" addr="));
    Serial.println(device.getAddress().toString().c_str());

    if (bestBleDevice == nullptr || device.getRSSI() > bestBleDevice->getRSSI()) {
      delete bestBleDevice;
      bestBleDevice = new BLEAdvertisedDevice(device);
    }
  }
};

bool scanForCamera() {
  delete bestBleDevice;
  bestBleDevice = nullptr;

  Serial.println("Scanning for GoPro BLE...");
  BLEScan *scan = BLEDevice::getScan();
  ScanCallbacks callbacks;
  scan->setAdvertisedDeviceCallbacks(&callbacks, false);
  scan->setActiveScan(true);
  scan->setInterval(100);
  scan->setWindow(99);
  scan->start(kBleScanSeconds, false);
  scan->clearResults();

  if (bestBleDevice == nullptr) {
    Serial.println("No GoPro BLE device found");
    return false;
  }

  Serial.print(F("Selected BLE device: "));
  Serial.print(bestBleDevice->haveName() ? bestBleDevice->getName().c_str() : "(no name)");
  Serial.print(F(" addr="));
  Serial.println(bestBleDevice->getAddress().toString().c_str());
  return true;
}

bool waitForBleResponse(uint32_t timeoutMs) {
  uint32_t start = millis();
  while (!bleResponseSeen && millis() - start < timeoutMs) {
    delay(20);
  }
  if (!bleResponseSeen) {
    Serial.println("BLE command response timeout");
    return false;
  }
  Serial.print(F("BLE response status=0x"));
  Serial.println(bleResponseStatus, HEX);
  return true;
}

bool connectBle() {
  initBleStack();
  if (bleClient != nullptr && bleClient->isConnected()) {
    return true;
  }
  if (bestBleDevice == nullptr && !scanForCamera()) {
    return false;
  }

  delete bleClient;
  bleClient = BLEDevice::createClient();
  Serial.println("Connecting GoPro BLE...");
  if (!bleClient->connectTimeout(bestBleDevice, kBleConnectTimeoutMs)) {
    Serial.println("BLE connect failed");
    delete bleClient;
    bleClient = nullptr;
    delete bestBleDevice;
    bestBleDevice = nullptr;
    return false;
  }

  Serial.println("BLE connected");
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
  return true;
}

bool sendBleCommand(const uint8_t *payload, size_t length) {
  if (!connectBle()) {
    return false;
  }
  BLERemoteService *control = bleClient->getService(kControlService);
  if (control == nullptr) {
    Serial.println("GoPro control BLE service missing");
    return false;
  }
  BLERemoteCharacteristic *command = control->getCharacteristic(kCommand);
  if (command == nullptr || !command->canWrite()) {
    Serial.println("GoPro command characteristic missing");
    return false;
  }

  bleResponseSeen = false;
  bleResponseStatus = 0xff;
  command->writeValue(const_cast<uint8_t *>(payload), length, true);
  return waitForBleResponse(3000);
}

bool sendBleSetting(uint8_t settingId, uint8_t optionId) {
  if (!connectBle()) {
    return false;
  }
  BLERemoteService *control = bleClient->getService(kControlService);
  if (control == nullptr) {
    Serial.println("GoPro control BLE service missing");
    return false;
  }
  BLERemoteCharacteristic *settings = control->getCharacteristic(kSettings);
  if (settings == nullptr || !settings->canWrite()) {
    Serial.println("GoPro settings characteristic missing");
    return false;
  }

  uint8_t payload[] = {settingId, 0x01, optionId};
  bleResponseSeen = false;
  bleResponseStatus = 0xff;
  settings->writeValue(payload, sizeof(payload), true);
  return waitForBleResponse(3000);
}

bool readAndEnableGoProWifi() {
  if (!connectBle()) {
    return false;
  }

  BLERemoteService *wifi = bleClient->getService(kWifiService);
  if (wifi == nullptr) {
    Serial.println("GoPro WiFi BLE service missing");
    return false;
  }

  BLERemoteCharacteristic *ssid = wifi->getCharacteristic(kWifiSsid);
  BLERemoteCharacteristic *password = wifi->getCharacteristic(kWifiPassword);
  if (ssid == nullptr || password == nullptr || !ssid->canRead() || !password->canRead()) {
    Serial.println("GoPro WiFi credentials unreadable");
    return false;
  }

  String goProSsid = bytesToString(ssid->readValue());
  String goProPassword = bytesToString(password->readValue());

  Serial.print(F("GoPro AP SSID: "));
  Serial.println(goProSsid);
#if GOPRO_DEBUG_PRINT_CAMERA_PASSWORD
  Serial.print(F("GoPro AP password: "));
  Serial.println(goProPassword);
#endif
  Serial.print(F("GoPro AP password length: "));
  Serial.println(goProPassword.length());

  Serial.println("Forcing GoPro WiFi band to 2.4GHz...");
  sendBleSetting(178, 0);
  delay(300);
  Serial.println("Enabling GoPro WiFi AP...");
  const uint8_t enableWifi[] = {0x03, 0x17, 0x01, 0x01};
  sendBleCommand(enableWifi, sizeof(enableWifi));
  Serial.println("Credential dump complete.");
  return !goProSsid.isEmpty() && !goProPassword.isEmpty();
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("GoPro BLE credential dumper boot");
  initBleStack();
}

void loop() {
  if (readAndEnableGoProWifi()) {
    Serial.println("GoPro WiFi should be available now. Holding BLE connection open.");
    while (true) {
      delay(1000);
    }
  }
  Serial.println("Retrying in 5 seconds. Put the GoPro in pairing mode if this is not bonded.");
  delay(5000);
}
