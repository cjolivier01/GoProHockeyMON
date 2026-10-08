#include <algorithm>
#include <cassert>
#include <cctype>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>
#include "src/amoled/parts/camera_presets.h"

// Only the hardware/transport boundaries are doubled; both connection entry
// points and the HTTP-first reuse decision below are production code.
class String : public std::string {
public:
  using std::string::string;
  using std::string::operator=;
  String(const std::string &s) : std::string(s) {}
  bool isEmpty() const { return empty(); }
  void toLowerCase() {
    std::transform(begin(), end(), begin(), [](unsigned char c) { return std::tolower(c); });
  }
};
DeserializationError deserializeJson(JsonDocument &doc, const String &body) {
  return ArduinoJson::deserializeJson(doc, body.c_str());
}
bool readStatusInt(JsonObjectConst status, const char *id, const char *sdk,
                   const char *name, int32_t &out) {
  return CameraPresets::integer(status[id], out) ||
         CameraPresets::integer(status[sdk], out) ||
         CameraPresets::integer(status[name], out);
}

bool associated, recording, goProWifiSuspendedForRecording, allowAnyCameraScan;
bool cancelled, cancelAfterHttp, cancelAfterParse, bleIdle, credentialsOk, apOk, parseOk;
int httpStatus, httpCalls, parseCalls, bleChecks, joins, credentialReads, apEnables;
int disconnects, handoffs, hardwareReads, presetReads, pollCancellations;
String boundBleAddress, goProSsid, goProPassword, response, action;
std::vector<std::string> events;
std::vector<bool> joinResults;
int *cameraLabel = nullptr, *wifiLabel = nullptr;
struct SerialMock { void println(const char *) {} } Serial;
struct AddressMock { std::string toString() const { return "aa:bb:cc:dd:ee:ff"; } };
struct BleDeviceMock {
  AddressMock getAddress() const { return {}; }
  bool haveName() const { return true; }
  std::string getName() const { return "GoPro"; }
} *bestBleDevice = nullptr;
struct WifiMock {
  void disconnect(bool, bool) { ++disconnects; associated = false; events.push_back("disconnect"); }
} WiFi;
bool operationCancelled() { return cancelled; }
void cancelCameraPresetPoll() { ++pollCancellations; }
bool isLikelyGoProWifiConnected() { return associated; }
void setAction(const char *message) { action = message; }
void delay(uint32_t) {}
void lv_label_set_text(int *, const char *) {}
void setHomeCameraConnected(bool) {}
void setConnectRetryAvailable(bool) {}
void markExistingGoProWifiConnected() { events.push_back("reuse"); }
void saveCameraBindingValues(const String &, const String &) {}
bool suspendGoProWifiForRecording(const char *) {
  ++handoffs; associated = false; goProWifiSuspendedForRecording = true;
  events.push_back("recording handoff"); return true;
}
int httpGetGoProBody(const String &path, String &body) {
  assert(path == "/gopro/camera/state");
  ++httpCalls; events.push_back("http state"); body = response;
  if (cancelAfterHttp) cancelled = true;
  return httpStatus;
}
bool parseCameraState(const String &body, bool *, bool) {
  ++parseCalls; events.push_back("parse state");
  if (!parseOk) return false;
  JsonDocument doc; assert(!deserializeJson(doc, body));
  JsonObjectConst status = doc["status"].as<JsonObjectConst>();
  if (status.isNull()) status = doc["statuses"].as<JsonObjectConst>();
  int32_t encoding = 0, duration = 0;
  bool hasEncoding = readStatusInt(status, "10", "StatusId.ENCODING", "encoding", encoding);
  readStatusInt(status, "13", "StatusId.VIDEO_ENCODING_DURATION", "video_encoding_duration", duration);
  recording = hasEncoding ? encoding != 0 : duration > 0;
  if (recording) suspendGoProWifiForRecording("camera state recording");
  if (cancelAfterParse) cancelled = true;
  return true;
}
bool ensureNotRecordingForWifi(const char *) {
  ++bleChecks; events.push_back("ble check");
  // Model the radio handoff responsible for the original regression.
  associated = false;
  return bleIdle;
}
bool readGoProWifiCredentials() { ++credentialReads; return credentialsOk; }
bool enableGoProWifiAp() { ++apEnables; return apOk; }
bool connectGoProWifiWithCurrentCredentials(const char *) {
  events.push_back("join");
  bool ok = static_cast<size_t>(joins) < joinResults.size() ? joinResults[joins] : false;
  ++joins; associated = ok; return ok;
}
bool syncCameraPresets() { ++presetReads; return true; }
bool refreshCameraHardwareInfoHttp() { ++hardwareReads; return true; }

#include "src/amoled/parts/wifi_connection.inc"

void reset() {
  associated = true; recording = goProWifiSuspendedForRecording = allowAnyCameraScan = false;
  cancelled = cancelAfterHttp = cancelAfterParse = false;
  bleIdle = credentialsOk = apOk = parseOk = true;
  httpStatus = 200;
  httpCalls = parseCalls = bleChecks = joins = credentialReads = apEnables = 0;
  disconnects = handoffs = hardwareReads = presetReads = pollCancellations = 0;
  boundBleAddress = "aa:bb:cc:dd:ee:ff"; goProSsid = "GoPro"; goProPassword = "password";
  response = R"({"status":{"10":0,"13":0,"96":1000,"97":7}})";
  action.clear(); events.clear(); joinResults = {true};
}
void expectReused() {
  assert(associated && !goProWifiSuspendedForRecording);
  assert(httpCalls == 1 && parseCalls == 1);
  assert(pollCancellations == 1);
  assert(bleChecks == 0 && joins == 0 && credentialReads == 0 && apEnables == 0);
  assert(disconnects == 0 && handoffs == 0 && hardwareReads == 0);
  assert(events == std::vector<std::string>({"http state", "parse state", "reuse"}));
}
void expectBlockedWithoutRadioChange() {
  assert(associated && bleChecks == 0 && joins == 0 && disconnects == 0);
  assert(credentialReads == 0 && apEnables == 0);
}
int main() {
  reset(); assert(ensureGoProWifiReady("Taking snapshot")); expectReused();
  assert(action == "Taking snapshot" && presetReads == 0);
  reset(); assert(connectGoProWifiFromBle()); expectReused(); assert(presetReads == 1);
  reset(); goProWifiSuspendedForRecording = true;
  assert(ensureGoProWifiReady(nullptr)); expectReused();
  assert(action == "Using existing GoPro WiFi");
  reset(); goProSsid.clear(); goProPassword.clear();
  assert(ensureGoProWifiReady(nullptr)); expectReused();
  reset(); response = R"({"statuses":{"encoding":0}})";
  assert(ensureGoProWifiReady(nullptr)); expectReused();
  reset(); response = R"({"status":{"StatusId.VIDEO_ENCODING_DURATION":0}})";
  assert(ensureGoProWifiReady(nullptr)); expectReused();
  reset(); response = R"({"status":{"10":1,"13":2}})";
  assert(!ensureGoProWifiReady(nullptr));
  assert(recording && handoffs == 1 && bleChecks == 0 && joins == 0);
  reset(); response = R"({"statuses":{"video_encoding_duration":3}})";
  assert(!connectGoProWifiFromBle());
  assert(recording && handoffs == 1 && presetReads == 0 && joins == 0);
  reset(); recording = true; assert(!ensureGoProWifiReady(nullptr));
  assert(httpCalls == 0 && handoffs == 1 && joins == 0);
  reset(); response = R"({"status":{"97":7},"settings":{"2":1}})";
  assert(!ensureGoProWifiReady(nullptr)); expectBlockedWithoutRadioChange();
  assert(parseCalls == 0 && action == "Recording check failed");
  reset(); response = "bad JSON";
  assert(!connectGoProWifiFromBle()); expectBlockedWithoutRadioChange(); assert(parseCalls == 0);
  reset(); parseOk = false;
  assert(!ensureGoProWifiReady(nullptr)); expectBlockedWithoutRadioChange();
  reset(); cancelled = true;
  assert(!ensureGoProWifiReady(nullptr)); expectBlockedWithoutRadioChange(); assert(httpCalls == 0);
  reset(); cancelAfterHttp = true;
  assert(!ensureGoProWifiReady(nullptr)); expectBlockedWithoutRadioChange(); assert(parseCalls == 0);
  reset(); cancelAfterParse = true;
  assert(!ensureGoProWifiReady(nullptr)); expectBlockedWithoutRadioChange();
  reset(); httpStatus = -1;
  assert(ensureGoProWifiReady(nullptr));
  assert(httpCalls == 1 && bleChecks == 1 && joins == 1 && disconnects == 1);
  assert(events == std::vector<std::string>({"http state", "disconnect", "ble check", "join"}));
  reset(); httpStatus = 503;
  assert(connectGoProWifiFromBle());
  assert(httpCalls == 1 && bleChecks == 1 && credentialReads == 1 && apEnables == 1 && joins == 1);
  reset(); httpStatus = -1; bleIdle = false;
  assert(!ensureGoProWifiReady(nullptr)); assert(bleChecks == 1 && joins == 0);
  reset(); associated = false;
  assert(ensureGoProWifiReady(nullptr)); assert(httpCalls == 0 && bleChecks == 1 && joins == 1);
  reset(); associated = false; joinResults = {false, true};
  assert(ensureGoProWifiReady(nullptr));
  assert(joins == 2 && credentialReads == 1 && apEnables == 1 && bleChecks == 2);
  reset(); associated = false; goProPassword.clear();
  assert(ensureGoProWifiReady(nullptr));
  assert(credentialReads == 1 && apEnables == 1 && joins == 1);
  reset(); boundBleAddress.clear();
  assert(!connectGoProWifiFromBle()); assert(httpCalls == 0 && bleChecks == 0);
  std::cout << "Wi-Fi connection tests passed (22 scenarios)\n";
}
