#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>
#include "src/amoled/parts/camera_presets.h"

// The preset parser and recording transaction are production code. Doubles
// model camera HTTP responses and the recording-status WiFi-to-BLE handoff.
class String : public std::string {
public:
  using std::string::string;
  using std::string::operator=;
  using std::string::operator+=;
  String(const std::string &value) : std::string(value) {}
  String &operator+=(int32_t value) { append(std::to_string(value)); return *this; }
};
using std::min;
struct SerialMock {
  template<class... Args> void printf(const char *, Args...) {}
  void println(const char *) {}
} Serial;
constexpr uint32_t kHttpTimeoutMs = 6500;
constexpr uint32_t kRecordingStartCommandTimeoutMs = 2500;
constexpr uint32_t kRecordingStartVerifyTimeoutMs = 5000;
constexpr uint32_t kRecordingStartVerifyRequestTimeoutMs = 1000;
constexpr uint32_t kRecordingStartVerifyPollMs = 200;
bool recording, bleConnected, wifiConnected;
int32_t activeCameraPresetId, activeCameraPresetGroup;
String captureMode, action, nameAtShutter;
uint32_t now;
int stateReads, catalogReads, shutterCalls, handoffs, handoffRetries;
int preflightStatus, verifyStatus, catalogStatus, shutterStatus;
bool preflightMalformed, catalogMalformed, cameraAlreadyRecording;
bool cameraStartsRecording, handoffOk, handoffRetryOk;
std::vector<std::string> requests;

void setAction(const char *message) { action = message; }
void applyCaptureLabels() {}
void storeSettingValue(uint16_t, int) {}
void refreshCaptureOverlayFromState() {}
void serviceLvgl() {}
uint32_t millis() { return now; }
void delay(uint32_t ms) { now += ms; }
bool isLikelyGoProWifiConnected() { return wifiConnected; }
bool readStatusInt(JsonObjectConst status, const char *idKey, const char *sdkKey,
                   const char *nameKey, int32_t &out) {
  return CameraPresets::integer(status[idKey], out) ||
         CameraPresets::integer(status[sdkKey], out) ||
         CameraPresets::integer(status[nameKey], out);
}
DeserializationError deserializeJson(JsonDocument &doc, const String &body) {
  return ArduinoJson::deserializeJson(doc, body.c_str());
}
int httpGetGoProBodyWithTimeout(const String &path, String &body, uint32_t timeout) {
  assert(wifiConnected && !recording);
  assert(timeout > 0 && timeout <= kRecordingStartVerifyRequestTimeoutMs);
  requests.push_back(path);
  now += 20;
  if (path == "/gopro/camera/state") {
    ++stateReads;
    if (stateReads == 1 && preflightMalformed) {
      body = "invalid JSON";
      return preflightStatus;
    }
    bool encoding = stateReads == 1 ? cameraAlreadyRecording : cameraStartsRecording;
    body = "{\"status\":{\"96\":1000,\"97\":7,\"10\":" +
           std::to_string(encoding ? 1 : 0) + "}}";
    return stateReads == 1 ? preflightStatus : verifyStatus;
  }
  assert(path.find("/gopro/camera/presets/get") == 0);
  ++catalogReads;
  body = catalogMalformed ? "invalid JSON" :
      R"({"presetGroupArray":[{"id":"PRESET_GROUP_ID_VIDEO","presetArray":[
        {"id":0,"titleId":"PRESET_TITLE_VIDEO"},
        {"id":7,"titleId":"PRESET_TITLE_USER_DEFINED_CUSTOM_NAME","customName":"Hockey"}
      ]}]})";
  return catalogStatus;
}

#include "src/amoled/parts/camera_presets.inc"

constexpr int WL_CONNECTED = 3;
struct WiFiMock { int status() { return wifiConnected ? WL_CONNECTED : 0; } } WiFi;
void applyGoProBatteryStatus(JsonObjectConst) {}
void applyRecordingUiState(bool active, uint32_t, bool) { recording = active; }
bool suspendGoProWifiForRecording(const char *) {
  ++handoffs;
  wifiConnected = false;
  bleConnected = handoffOk;
  return handoffOk;
}
#include "src/amoled/parts/camera_state_parse.inc"
bool setGoProWifiApBle(bool enabled) {
  assert(!enabled && recording);
  ++handoffRetries;
  bleConnected = handoffRetryOk;
  return handoffRetryOk;
}
int httpGetGoProStatusWithTimeout(const String &path, uint32_t timeout) {
  assert(path == "/gopro/camera/shutter/start");
  assert(timeout == kRecordingStartCommandTimeoutMs);
  assert(wifiConnected && !recording);
  ++shutterCalls;
  requests.push_back(path);
  nameAtShutter = captureMode;
  return shutterStatus;
}

#include "src/amoled/parts/recording_start.inc"

void reset() {
  now = 0;
  stateReads = catalogReads = shutterCalls = handoffs = handoffRetries = 0;
  recording = bleConnected = false;
  wifiConnected = true;
  // A camera-side switch to Hockey happened since the remote's last poll.
  activeCameraPresetId = 8;
  activeCameraPresetGroup = 1000;
  captureMode = "Practice";
  action.clear(); nameAtShutter.clear(); requests.clear();
  preflightStatus = verifyStatus = catalogStatus = shutterStatus = 200;
  preflightMalformed = catalogMalformed = cameraAlreadyRecording = false;
  cameraStartsRecording = handoffOk = handoffRetryOk = true;
}
void expectStarted() {
  assert(recording && !wifiConnected);
  assert(shutterCalls == 1 && handoffs == 1);
}

int main() {
  bool accepted = true;
  reset();
  assert(startRecordingOverWifiAndVerify(accepted));
  assert(accepted && captureMode == "Hockey" && nameAtShutter == "Hockey");
  assert(activeCameraPresetId == 7 && catalogReads == 1 && stateReads == 2);
  assert(requests[0] == "/gopro/camera/state");
  assert(requests[1].find("/gopro/camera/presets/get") == 0);
  assert(requests[2] == "/gopro/camera/shutter/start");
  expectStarted();

  reset(); preflightStatus = -1;
  assert(startRecordingOverWifiAndVerify(accepted));
  assert(accepted && catalogReads == 0); expectStarted();
  reset(); preflightMalformed = true;
  assert(startRecordingOverWifiAndVerify(accepted));
  assert(accepted && catalogReads == 0); expectStarted();
  reset(); catalogStatus = -1;
  assert(startRecordingOverWifiAndVerify(accepted));
  assert(accepted && catalogReads == 1); expectStarted();
  reset(); catalogMalformed = true;
  assert(startRecordingOverWifiAndVerify(accepted));
  assert(accepted && catalogReads == 1); expectStarted();

  reset(); cameraAlreadyRecording = true;
  assert(startRecordingOverWifiAndVerify(accepted));
  assert(!accepted && recording && !wifiConnected && bleConnected);
  assert(shutterCalls == 0 && catalogReads == 0 && stateReads == 1);
  reset(); cameraAlreadyRecording = true; handoffOk = false;
  assert(startRecordingOverWifiAndVerify(accepted));
  assert(!accepted && shutterCalls == 0 && handoffRetries == 1 && bleConnected);
  reset(); cameraAlreadyRecording = true; handoffOk = handoffRetryOk = false;
  assert(startRecordingOverWifiAndVerify(accepted));
  assert(!accepted && shutterCalls == 0 && handoffRetries == 1);
  assert(action == "Recording; BLE reconnect failed");

  reset(); shutterStatus = 500;
  assert(!startRecordingOverWifiAndVerify(accepted));
  assert(!accepted && !recording && shutterCalls == 1 && stateReads == 1);
  assert(captureMode == "Hockey");
  reset(); cameraStartsRecording = false;
  assert(!startRecordingOverWifiAndVerify(accepted));
  assert(accepted && !recording && shutterCalls == 1 && stateReads > 2);
  assert(now >= kRecordingStartVerifyTimeoutMs && handoffs == 0);
  reset(); verifyStatus = -1;
  assert(!startRecordingOverWifiAndVerify(accepted));
  assert(accepted && !recording && shutterCalls == 1);

  reset(); handoffOk = false;
  assert(startRecordingOverWifiAndVerify(accepted));
  expectStarted();
  assert(accepted && handoffRetries == 1 && bleConnected && captureMode == "Hockey");
  reset(); handoffOk = handoffRetryOk = false;
  assert(startRecordingOverWifiAndVerify(accepted));
  expectStarted();
  assert(accepted && handoffRetries == 1 && !bleConnected);
  assert(action == "Recording; BLE reconnect failed");
  std::cout << "Recording preset tests passed (13 scenarios)\n";
}
