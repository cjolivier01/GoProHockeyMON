#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEScan.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiUdp.h>

#include "LinkProtocol.h"

#ifndef LED_BUILTIN
#define LED_BUILTIN 2
#endif

#ifndef GOPRO_LOCAL_WIFI_SSID
#define GOPRO_LOCAL_WIFI_SSID ""
#endif

#ifndef GOPRO_LOCAL_WIFI_PASSWORD
#define GOPRO_LOCAL_WIFI_PASSWORD ""
#endif

#ifndef GOPRO_CAMERA_NAME_FILTER
#define GOPRO_CAMERA_NAME_FILTER "GoPro,MISSION,GP"
#endif

#ifndef GOPRO_AUTO_START
#define GOPRO_AUTO_START 1
#endif

#ifndef GOPRO_BUTTON_PIN
#define GOPRO_BUTTON_PIN 0
#endif

#ifndef GOPRO_LINK_BAUD
#define GOPRO_LINK_BAUD 921600
#endif

#ifndef GOPRO_LINK_RX_PIN
#define GOPRO_LINK_RX_PIN 16
#endif

#ifndef GOPRO_LINK_TX_PIN
#define GOPRO_LINK_TX_PIN 17
#endif

namespace {

const BLEUUID kControlService("0000fea6-0000-1000-8000-00805f9b34fb");
const BLEUUID kWifiService("b5f90001-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kCameraManagementService("b5f90090-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kWifiSsid("b5f90002-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kWifiPassword("b5f90003-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kCommand("b5f90072-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kCommandResponse("b5f90073-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kCameraManagementCommand("b5f90091-aa8d-11e3-9046-0002a5d5c51b");
const BLEUUID kCameraManagementResponse("b5f90092-aa8d-11e3-9046-0002a5d5c51b");

const IPAddress kDefaultGoProIp(10, 5, 5, 9);
const uint16_t kGoProHttpPort = 8080;
const uint16_t kStreamUdpPort = 8554;
const uint32_t kBleScanSeconds = 7;
const uint32_t kWifiTimeoutMs = 25000;
const uint32_t kHttpTimeoutMs = 6000;
const uint32_t kStreamReportIntervalMs = 2000;
const uint32_t kButtonDebounceMs = 35;
const uint32_t kButtonMediumPressMs = 800;
const uint32_t kButtonLongPressMs = 3000;

BLEAdvertisedDevice *g_bestDevice = nullptr;
BLEClient *g_bleClient = nullptr;
WiFiUDP g_streamUdp;
RemoteLink::Parser g_linkParser;

String g_lastBleName;
String g_goProSsid;
String g_goProPassword;
IPAddress g_goProIp = kDefaultGoProIp;
IPAddress g_forwardIp;
uint16_t g_forwardPort = 0;
bool g_bleConnected = false;
bool g_streamListening = false;
uint32_t g_streamPackets = 0;
uint32_t g_streamBytes = 0;
uint32_t g_lastStreamReportMs = 0;
uint8_t g_udpBuffer[1472];
bool g_buttonLast = HIGH;
bool g_buttonStable = HIGH;
uint32_t g_buttonLastChangeMs = 0;
uint32_t g_buttonPressedAtMs = 0;
uint16_t g_linkSequence = 1;

void linkText(RemoteLink::MsgType type, const String &text) {
  RemoteLink::sendText(Serial2, type, text, g_linkSequence++);
}

void linkLog(const String &text) {
  linkText(RemoteLink::MsgType::Log, text);
}

String payloadToString(const RemoteLink::Packet &packet) {
  String text;
  text.reserve(packet.length);
  for (uint16_t i = 0; i < packet.length; ++i) {
    text += static_cast<char>(packet.payload[i]);
  }
  return text;
}

void setLed(bool on) {
  digitalWrite(LED_BUILTIN, on ? HIGH : LOW);
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

void printStatus() {
  Serial.println();
  Serial.println(F("Status"));
  Serial.print(F("  BLE: "));
  Serial.println(g_bleConnected ? F("connected") : F("disconnected"));
  Serial.print(F("  Camera: "));
  Serial.println(g_lastBleName.isEmpty() ? F("(none)") : g_lastBleName);
  Serial.print(F("  GoPro AP SSID: "));
  Serial.println(g_goProSsid.isEmpty() ? F("(unknown)") : g_goProSsid);
  Serial.print(F("  WiFi: "));
  Serial.print(WiFi.status() == WL_CONNECTED ? F("connected ") : F("disconnected "));
  Serial.print(WiFi.SSID());
  Serial.print(F(" ip="));
  Serial.println(WiFi.localIP());
  Serial.print(F("  Camera IP: "));
  Serial.println(g_goProIp);
  Serial.print(F("  Stream UDP: "));
  Serial.print(g_streamListening ? F("listening ") : F("stopped "));
  Serial.print(g_streamPackets);
  Serial.print(F(" packets, "));
  Serial.print(g_streamBytes);
  Serial.println(F(" bytes"));
}

String buildStatusJson() {
  String json = "{";
  json += "\"ble\":";
  json += g_bleConnected ? "true" : "false";
  json += ",\"camera\":\"";
  json += g_lastBleName;
  json += "\",\"goproSsid\":\"";
  json += g_goProSsid;
  json += "\",\"wifi\":";
  json += WiFi.status() == WL_CONNECTED ? "true" : "false";
  json += ",\"wifiSsid\":\"";
  json += WiFi.SSID();
  json += "\",\"localIp\":\"";
  json += WiFi.localIP().toString();
  json += "\",\"cameraIp\":\"";
  json += g_goProIp.toString();
  json += "\",\"stream\":";
  json += g_streamListening ? "true" : "false";
  json += ",\"streamPackets\":";
  json += g_streamPackets;
  json += ",\"streamBytes\":";
  json += g_streamBytes;
  json += "}";
  return json;
}

void sendLinkStatus() {
  linkText(RemoteLink::MsgType::Status, buildStatusJson());
}

void printHelp() {
  Serial.println(F("Commands:"));
  Serial.println(F("  help                  show commands"));
  Serial.println(F("  status                print state"));
  Serial.println(F("  scan                  scan for GoPro BLE advertisements"));
  Serial.println(F("  connect               BLE connect to first matching GoPro/MISSION device"));
  Serial.println(F("  pair                  finish BLE pairing while camera is in pairing mode"));
  Serial.println(F("  wake                  BLE connect, read GoPro AP credentials, enable WiFi"));
  Serial.println(F("  goproap               join camera AP read over BLE"));
  Serial.println(F("  cameraap SSID PASS    set camera AP credentials, e.g. LEFTCAM password"));
  Serial.println(F("  localwifi             join configured local WiFi"));
  Serial.println(F("  ip 10.5.5.9           set camera HTTP IP"));
  Serial.println(F("  stream                start GoPro preview stream and listen on UDP/8554"));
  Serial.println(F("  stop                  stop GoPro preview stream"));
  Serial.println(F("  shutter on|off        start or stop recording over HTTP"));
  Serial.println(F("  proxy 192.168.1.50 8554  forward received stream UDP packets"));
  Serial.println(F("  autostart             run wake, goproap, stream"));
  Serial.println(F("Button: short=stream toggle, 1s=wake/start, 3s=pair"));
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

    if (g_bestDevice == nullptr || device.getRSSI() > g_bestDevice->getRSSI()) {
      delete g_bestDevice;
      g_bestDevice = new BLEAdvertisedDevice(device);
    }
  }
};

bool scanForCamera() {
  delete g_bestDevice;
  g_bestDevice = nullptr;

  Serial.println(F("Scanning for GoPro BLE device..."));
  BLEScan *scan = BLEDevice::getScan();
  ScanCallbacks callbacks;
  scan->setAdvertisedDeviceCallbacks(&callbacks, false);
  scan->setActiveScan(true);
  scan->setInterval(100);
  scan->setWindow(99);
  scan->start(kBleScanSeconds, false);
  scan->clearResults();

  if (g_bestDevice == nullptr) {
    Serial.println(F("No GoPro BLE device found."));
    return false;
  }

  g_lastBleName = g_bestDevice->haveName() ? String(g_bestDevice->getName().c_str()) : "";
  Serial.print(F("Selected BLE device: "));
  Serial.print(g_lastBleName.isEmpty() ? F("(no name)") : g_lastBleName);
  Serial.print(F(" addr="));
  Serial.println(g_bestDevice->getAddress().toString().c_str());
  return true;
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
}

bool connectBle() {
  if (g_bleConnected && g_bleClient != nullptr && g_bleClient->isConnected()) {
    return true;
  }

  if (g_bestDevice == nullptr && !scanForCamera()) {
    return false;
  }

  if (g_bleClient == nullptr) {
    g_bleClient = BLEDevice::createClient();
  }

  Serial.println(F("Connecting BLE..."));
  if (!g_bleClient->connect(g_bestDevice)) {
    Serial.println(F("BLE connect failed."));
    g_bleConnected = false;
    return false;
  }

  g_bleConnected = true;
  Serial.println(F("BLE connected."));

  BLERemoteService *control = g_bleClient->getService(kControlService);
  if (control != nullptr) {
    BLERemoteCharacteristic *response = control->getCharacteristic(kCommandResponse);
    if (response != nullptr && response->canNotify()) {
      response->registerForNotify(commandResponseNotify);
    }
  }
  return true;
}

bool readGoProWifiCredentials() {
  if (!connectBle()) {
    return false;
  }

  BLERemoteService *wifi = g_bleClient->getService(kWifiService);
  if (wifi == nullptr) {
    Serial.println(F("GoPro WiFi BLE service not found."));
    return false;
  }

  BLERemoteCharacteristic *ssid = wifi->getCharacteristic(kWifiSsid);
  BLERemoteCharacteristic *password = wifi->getCharacteristic(kWifiPassword);
  if (ssid == nullptr || password == nullptr || !ssid->canRead() || !password->canRead()) {
    Serial.println(F("GoPro WiFi credential characteristics are unavailable."));
    return false;
  }

  g_goProSsid = bytesToString(ssid->readValue());
  g_goProPassword = bytesToString(password->readValue());

  Serial.print(F("GoPro AP SSID: "));
  Serial.println(g_goProSsid);
  Serial.print(F("GoPro AP password length: "));
  Serial.println(g_goProPassword.length());
  return !g_goProSsid.isEmpty() && !g_goProPassword.isEmpty();
}

bool sendBleCommand(const uint8_t *payload, size_t length) {
  if (!connectBle()) {
    return false;
  }

  BLERemoteService *control = g_bleClient->getService(kControlService);
  if (control == nullptr) {
    Serial.println(F("GoPro control BLE service not found."));
    return false;
  }

  BLERemoteCharacteristic *command = control->getCharacteristic(kCommand);
  if (command == nullptr || !command->canWrite()) {
    Serial.println(F("GoPro command characteristic is unavailable."));
    return false;
  }

  command->writeValue(const_cast<uint8_t *>(payload), length, true);
  delay(300);
  return true;
}

bool sendCameraManagementCommand(const uint8_t *payload, size_t length) {
  if (!connectBle()) {
    return false;
  }

  BLERemoteService *management = g_bleClient->getService(kCameraManagementService);
  if (management == nullptr) {
    Serial.println(F("GoPro camera-management BLE service not found."));
    return false;
  }

  BLERemoteCharacteristic *response = management->getCharacteristic(kCameraManagementResponse);
  if (response != nullptr && response->canNotify()) {
    response->registerForNotify(commandResponseNotify);
  }

  BLERemoteCharacteristic *command = management->getCharacteristic(kCameraManagementCommand);
  if (command == nullptr || !command->canWrite()) {
    Serial.println(F("GoPro camera-management command characteristic is unavailable."));
    return false;
  }

  command->writeValue(const_cast<uint8_t *>(payload), length, true);
  delay(500);
  return true;
}

bool pairGoPro() {
  Serial.println(F("Pairing: put the GoPro in Bluetooth pairing mode first."));
  const char phoneName[] = "ESP32";
  uint8_t request[1 + 2 + 2 + 2 + sizeof(phoneName) - 1] = {
      0x0B,  // Open GoPro BLE packet length: 11 payload bytes follow.
      0x03,  // FeatureId.WIRELESS_MANAGEMENT
      0x01,  // ActionId.SET_PAIRING_STATE
      0x08,  // protobuf field 1, varint: result
      0x00,  // EnumPairingFinishState.SUCCESS
      0x12,  // protobuf field 2, length-delimited: phoneName
      static_cast<uint8_t>(sizeof(phoneName) - 1),
      'E',
      'S',
      'P',
      '3',
      '2',
  };
  return sendCameraManagementCommand(request, sizeof(request));
}

bool enableGoProWifiAp() {
  const uint8_t enableWifi[] = {0x03, 0x17, 0x01, 0x01};
  Serial.println(F("Enabling GoPro WiFi AP over BLE..."));
  return sendBleCommand(enableWifi, sizeof(enableWifi));
}

bool wakeGoPro() {
  bool ok = connectBle();
  ok = readGoProWifiCredentials() && ok;
  ok = enableGoProWifiAp() && ok;
  return ok;
}

bool connectWifi(const char *ssid, const char *password, uint32_t timeoutMs = kWifiTimeoutMs) {
  if (ssid == nullptr || ssid[0] == '\0') {
    Serial.println(F("No WiFi SSID configured."));
    return false;
  }

  if (WiFi.status() == WL_CONNECTED && WiFi.SSID() == ssid) {
    return true;
  }

  Serial.print(F("Connecting WiFi: "));
  Serial.println(ssid);
  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true, true);
  delay(250);
  WiFi.begin(ssid, password);

  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < timeoutMs) {
    delay(250);
    Serial.print('.');
  }
  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(F("WiFi connect failed."));
    return false;
  }

  Serial.print(F("WiFi connected: "));
  Serial.println(WiFi.localIP());
  return true;
}

bool connectGoProAp() {
  if (g_goProSsid.isEmpty() && !readGoProWifiCredentials()) {
    return false;
  }
  g_goProIp = kDefaultGoProIp;
  return connectWifi(g_goProSsid.c_str(), g_goProPassword.c_str());
}

bool connectLocalWifi() {
  return connectWifi(GOPRO_LOCAL_WIFI_SSID, GOPRO_LOCAL_WIFI_PASSWORD);
}

bool httpGetGoPro(const String &path) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(F("WiFi is not connected."));
    return false;
  }

  String url = String("http://") + g_goProIp.toString() + ":" + kGoProHttpPort + path;
  Serial.print(F("HTTP GET "));
  Serial.println(url);

  HTTPClient http;
  http.setTimeout(kHttpTimeoutMs);
  if (!http.begin(url)) {
    Serial.println(F("HTTP begin failed."));
    return false;
  }

  int code = http.GET();
  String body = http.getString();
  http.end();

  Serial.print(F("HTTP status: "));
  Serial.println(code);
  if (!body.isEmpty()) {
    Serial.println(body);
  }
  return code >= 200 && code < 300;
}

bool httpGetGoProBody(const String &path, String &body) {
  body = "";
  if (WiFi.status() != WL_CONNECTED) {
    body = "{\"error\":\"wifi not connected\"}";
    return false;
  }

  String url = String("http://") + g_goProIp.toString() + ":" + kGoProHttpPort + path;
  HTTPClient http;
  http.setTimeout(kHttpTimeoutMs);
  if (!http.begin(url)) {
    body = "{\"error\":\"http begin failed\"}";
    return false;
  }

  int code = http.GET();
  body = http.getString();
  http.end();

  if (body.isEmpty()) {
    body = String("{\"status\":") + code + "}";
  }
  return code >= 200 && code < 300;
}

bool startUdpListener() {
  if (g_streamListening) {
    return true;
  }

  if (!g_streamUdp.begin(kStreamUdpPort)) {
    Serial.println(F("Failed to bind UDP stream port."));
    return false;
  }

  g_streamPackets = 0;
  g_streamBytes = 0;
  g_lastStreamReportMs = millis();
  g_streamListening = true;
  Serial.print(F("Listening for GoPro stream UDP on port "));
  Serial.println(kStreamUdpPort);
  return true;
}

bool startStream() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(F("WiFi is not connected; not starting UDP stream listener."));
    return false;
  }

  if (!startUdpListener()) {
    return false;
  }
  return httpGetGoPro(String("/gopro/camera/stream/start?port=") + kStreamUdpPort);
}

bool stopStream() {
  bool ok = httpGetGoPro("/gopro/camera/stream/stop");
  if (g_streamListening) {
    g_streamUdp.stop();
    g_streamListening = false;
  }
  return ok;
}

bool toggleStream() {
  if (g_streamListening) {
    return stopStream();
  }
  return startStream();
}

bool setShutter(bool enabled) {
  return httpGetGoPro(String("/gopro/camera/shutter/") + (enabled ? "start" : "stop"));
}

void handleUdpStream() {
  if (!g_streamListening) {
    return;
  }

  int packetSize = g_streamUdp.parsePacket();
  while (packetSize > 0) {
    int readLen = g_streamUdp.read(g_udpBuffer, min(packetSize, static_cast<int>(sizeof(g_udpBuffer))));
    if (readLen > 0) {
      g_streamPackets++;
      g_streamBytes += static_cast<uint32_t>(readLen);

      if (g_forwardPort != 0 && g_forwardIp != IPAddress()) {
        g_streamUdp.beginPacket(g_forwardIp, g_forwardPort);
        g_streamUdp.write(g_udpBuffer, readLen);
        g_streamUdp.endPacket();
      }

      RemoteLink::sendPacket(
          Serial2,
          RemoteLink::MsgType::StreamChunk,
          g_udpBuffer,
          static_cast<uint16_t>(readLen),
          g_linkSequence++);
    }
    packetSize = g_streamUdp.parsePacket();
  }

  uint32_t now = millis();
  if (now - g_lastStreamReportMs >= kStreamReportIntervalMs) {
    Serial.print(F("Stream packets="));
    Serial.print(g_streamPackets);
    Serial.print(F(" bytes="));
    Serial.println(g_streamBytes);
    g_lastStreamReportMs = now;
  }
}

void handleLinkPacket(const RemoteLink::Packet &packet) {
  String text = payloadToString(packet);
  bool ok = false;
  String body;

  switch (packet.type) {
    case RemoteLink::MsgType::Ping:
      RemoteLink::sendText(Serial2, RemoteLink::MsgType::Ack, "pong", packet.sequence);
      return;
    case RemoteLink::MsgType::Pair:
      ok = pairGoPro();
      break;
    case RemoteLink::MsgType::Wake:
      ok = wakeGoPro();
      break;
    case RemoteLink::MsgType::ConnectGoProAp:
      ok = connectGoProAp();
      break;
    case RemoteLink::MsgType::ConnectLocalWifi:
      ok = connectLocalWifi();
      break;
    case RemoteLink::MsgType::StartStream:
      ok = startStream();
      break;
    case RemoteLink::MsgType::StopStream:
      ok = stopStream();
      break;
    case RemoteLink::MsgType::Shutter:
      text.trim();
      ok = setShutter(text == "on" || text == "1" || text == "true");
      break;
    case RemoteLink::MsgType::SetCameraAp: {
      int separator = text.indexOf('\n');
      if (separator > 0) {
        g_goProSsid = trimCopy(text.substring(0, separator));
        g_goProPassword = trimCopy(text.substring(separator + 1));
        g_goProIp = kDefaultGoProIp;
        ok = true;
      }
      break;
    }
    case RemoteLink::MsgType::SetCameraIp:
      ok = g_goProIp.fromString(trimCopy(text));
      break;
    case RemoteLink::MsgType::Proxy: {
      int separator = text.indexOf(':');
      IPAddress ip;
      if (separator > 0 && ip.fromString(text.substring(0, separator))) {
        g_forwardIp = ip;
        g_forwardPort = static_cast<uint16_t>(text.substring(separator + 1).toInt());
        ok = g_forwardPort != 0;
      }
      break;
    }
    case RemoteLink::MsgType::GetCameraState:
      ok = httpGetGoProBody("/gopro/camera/state", body);
      RemoteLink::sendText(Serial2, RemoteLink::MsgType::CameraJson, body, packet.sequence);
      sendLinkStatus();
      return;
    case RemoteLink::MsgType::GetPresets:
      ok = httpGetGoProBody("/gopro/camera/presets/get?include-hidden=1", body);
      RemoteLink::sendText(Serial2, RemoteLink::MsgType::CameraJson, body, packet.sequence);
      sendLinkStatus();
      return;
    case RemoteLink::MsgType::LoadPreset:
      ok = httpGetGoProBody(String("/gopro/camera/presets/load?id=") + trimCopy(text), body);
      break;
    case RemoteLink::MsgType::KeepAlive:
      ok = httpGetGoProBody("/gopro/camera/keep_alive", body);
      break;
    case RemoteLink::MsgType::RawHttpGet:
      ok = httpGetGoProBody(text, body);
      RemoteLink::sendText(Serial2, RemoteLink::MsgType::CameraJson, body, packet.sequence);
      sendLinkStatus();
      return;
    default:
      linkText(RemoteLink::MsgType::Error, "unsupported command");
      return;
  }

  RemoteLink::sendText(Serial2, ok ? RemoteLink::MsgType::Ack : RemoteLink::MsgType::Error, ok ? "ok" : "failed", packet.sequence);
  sendLinkStatus();
}

void handleLink() {
  RemoteLink::Packet packet;
  while (Serial2.available() > 0) {
    if (g_linkParser.push(static_cast<uint8_t>(Serial2.read()), packet)) {
      handleLinkPacket(packet);
    }
  }
}

bool autostart() {
  setLed(true);
  bool ok = wakeGoPro();
  ok = ok && connectGoProAp();
  ok = ok && startStream();
  setLed(false);
  return ok;
}

void handleButtonRelease(uint32_t durationMs) {
  if (durationMs >= kButtonLongPressMs) {
    Serial.println(F("Button long press: pair"));
    pairGoPro();
  } else if (durationMs >= kButtonMediumPressMs) {
    Serial.println(F("Button medium press: wake/start"));
    autostart();
  } else {
    Serial.println(F("Button short press: stream toggle"));
    toggleStream();
  }
}

void handleButton() {
  bool reading = digitalRead(GOPRO_BUTTON_PIN);
  uint32_t now = millis();

  if (reading != g_buttonLast) {
    g_buttonLastChangeMs = now;
    g_buttonLast = reading;
  }

  if ((now - g_buttonLastChangeMs) < kButtonDebounceMs || reading == g_buttonStable) {
    return;
  }

  g_buttonStable = reading;
  if (g_buttonStable == LOW) {
    g_buttonPressedAtMs = now;
  } else if (g_buttonPressedAtMs != 0) {
    handleButtonRelease(now - g_buttonPressedAtMs);
    g_buttonPressedAtMs = 0;
  }
}

void handleCommand(String line) {
  line.trim();
  if (line.isEmpty()) {
    return;
  }

  if (line == "help" || line == "?") {
    printHelp();
  } else if (line == "status") {
    printStatus();
  } else if (line == "scan") {
    scanForCamera();
  } else if (line == "connect") {
    connectBle();
  } else if (line == "pair") {
    pairGoPro();
  } else if (line == "wake") {
    wakeGoPro();
  } else if (line == "goproap") {
    connectGoProAp();
  } else if (line.startsWith("cameraap ")) {
    int space = line.indexOf(' ', 9);
    if (space > 0) {
      g_goProSsid = trimCopy(line.substring(9, space));
      g_goProPassword = trimCopy(line.substring(space + 1));
      g_goProIp = kDefaultGoProIp;
      Serial.print(F("Camera AP SSID set to "));
      Serial.println(g_goProSsid);
    } else {
      Serial.println(F("Usage: cameraap LEFTCAM password"));
    }
  } else if (line == "localwifi") {
    connectLocalWifi();
  } else if (line == "stream") {
    startStream();
  } else if (line == "stop") {
    stopStream();
  } else if (line == "shutter on") {
    setShutter(true);
  } else if (line == "shutter off") {
    setShutter(false);
  } else if (line == "autostart") {
    autostart();
  } else if (line.startsWith("ip ")) {
    IPAddress ip;
    String value = trimCopy(line.substring(3));
    if (ip.fromString(value)) {
      g_goProIp = ip;
      Serial.print(F("Camera IP set to "));
      Serial.println(g_goProIp);
    } else {
      Serial.println(F("Invalid IP address."));
    }
  } else if (line.startsWith("proxy ")) {
    int space = line.indexOf(' ', 6);
    if (space > 0) {
      IPAddress ip;
      String ipText = trimCopy(line.substring(6, space));
      uint16_t port = static_cast<uint16_t>(trimCopy(line.substring(space + 1)).toInt());
      if (ip.fromString(ipText) && port != 0) {
        g_forwardIp = ip;
        g_forwardPort = port;
        Serial.print(F("UDP stream proxy set to "));
        Serial.print(g_forwardIp);
        Serial.print(':');
        Serial.println(g_forwardPort);
      } else {
        Serial.println(F("Usage: proxy 192.168.1.50 8554"));
      }
    } else {
      Serial.println(F("Usage: proxy 192.168.1.50 8554"));
    }
  } else {
    Serial.println(F("Unknown command. Type help."));
  }
}

void readSerialCommands() {
  static String line;
  while (Serial.available() > 0) {
    char c = static_cast<char>(Serial.read());
    if (c == '\r') {
      continue;
    }
    if (c == '\n') {
      handleCommand(line);
      line = "";
    } else if (line.length() < 160) {
      line += c;
    }
  }
}

}  // namespace

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(GOPRO_BUTTON_PIN, INPUT_PULLUP);
  g_buttonLast = digitalRead(GOPRO_BUTTON_PIN);
  g_buttonStable = g_buttonLast;
  g_buttonLastChangeMs = millis();
  setLed(false);

  Serial.begin(115200);
  Serial2.begin(GOPRO_LINK_BAUD, SERIAL_8N1, GOPRO_LINK_RX_PIN, GOPRO_LINK_TX_PIN);
  delay(500);
  Serial.println();
  Serial.println(F("ESP32 Open GoPro remote"));
  Serial.println(F("Open GoPro BLE + WiFi preview stream controller"));
  printHelp();

  BLEDevice::init("ESP32-GoPro-Remote");
  linkLog("radio boot");

#if GOPRO_AUTO_START
  Serial.println(F("Autostart enabled."));
  autostart();
#endif
}

void loop() {
  handleLink();
  handleButton();
  readSerialCommands();
  handleUdpStream();
  delay(2);
}
