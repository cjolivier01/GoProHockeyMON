#include <atomic>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <new>
#include <string>
#include <vector>
#include "src/amoled/parts/camera_presets.h"

class String : public std::string {
public:
  using std::string::string;
  using std::string::operator=;
  String(const std::string &s) : std::string(s) {}
  bool isEmpty() const { return empty(); }
};
DeserializationError deserializeJson(JsonDocument &doc, const String &body) {
  return ArduinoJson::deserializeJson(doc, body.c_str());
}
bool readStatusInt(JsonObjectConst status, const char *key, const char *sdk,
                   const char *name, int32_t &out) {
  return CameraPresets::integer(status[key], out) ||
         CameraPresets::integer(status[sdk], out) ||
         CameraPresets::integer(status[name], out);
}
enum class PendingHomeAction { None, Connect };
PendingHomeAction pendingHomeAction = PendingHomeAction::None;
bool goproActionBusy, snapshotPreviewBusy, pairingInProgress, touchActive, navSwipeActive;
bool displayOn = true, homeCameraConnected = true, recording, wifiConnected = true;
uint8_t actionButtonShortClickCount;
String boundBleAddress = "camera-a";
uint32_t now;
uint32_t millis() { return now; }
bool isLikelyGoProWifiConnected() { return wifiConnected; }
String cameraBaseUrl() { return "http://10.5.5.9"; }
int applyStateCount, applyCatalogCount, handoffCount;
bool workerRunning;
String stateResponse = R"({"status":{"10":0,"96":1000,"97":7}})";
String catalogResponse = R"({"presetGroupArray":[]})";
bool httpOk = true, taskOk = true;
std::vector<std::string> requests;
bool parseCameraState(const String &body, bool *, bool quiet) {
  assert(!workerRunning && quiet && goproActionBusy);
  ++applyStateCount;
  JsonDocument doc;
  if (deserializeJson(doc, body)) return false;
  recording = doc["status"]["10"].as<int>() != 0;
  if (recording) { ++handoffCount; wifiConnected = false; }
  return true;
}
bool applyCameraPresetCatalog(const String &) {
  assert(!workerRunning && goproActionBusy);
  ++applyCatalogCount;
  return true;
}
struct HTTPClient {
  std::string path;
  void setConnectTimeout(int timeout) { assert(timeout == 800); }
  void setTimeout(int timeout) { assert(timeout == 800); }
  bool begin(const String &url) { path = url; return true; }
  int GET() { assert(workerRunning); requests.push_back(path); return httpOk ? 200 : -1; }
  String getString() { return path.find("/state") != std::string::npos ? stateResponse : catalogResponse; }
  void end() {}
};
using Task = void (*)(void *);
Task pendingTask;
void *pendingArgument;
constexpr int pdPASS = 1;
int xTaskCreate(Task task, const char *, int, void *argument, int, void *) {
  assert(!pendingTask);
  if (!taskOk) return 0;
  pendingTask = task; pendingArgument = argument;
  return pdPASS;
}
void vTaskDelete(void *) {}
struct SerialStub { void println(const char *) {} } Serial;
int uiServiceCount = 0;
bool finishOnDelay = false;
void finishWorker();
void serviceLvgl() { ++uiServiceCount; }
void delay(uint32_t milliseconds) {
  now += milliseconds;
  if (finishOnDelay && pendingTask) finishWorker();
}
#include "src/amoled/parts/camera_preset_poll.inc"

void finishWorker() {
  assert(pendingTask);
  Task task = pendingTask; pendingTask = nullptr;
  workerRunning = true;
  task(pendingArgument);
  workerRunning = false;
}
void nextPoll() { now += 5001; refreshCameraPresetWhileIdle(); }
void reset() {
  assert(!pendingTask && !cameraPresetPoll);
  goproActionBusy = snapshotPreviewBusy = pairingInProgress = touchActive = navSwipeActive = false;
  recording = false; displayOn = homeCameraConnected = wifiConnected = httpOk = taskOk = true;
  pendingHomeAction = PendingHomeAction::None; actionButtonShortClickCount = 0;
  boundBleAddress = "camera-a"; applyStateCount = applyCatalogCount = handoffCount = 0;
  uiServiceCount = 0; finishOnDelay = false;
  requests.clear(); stateResponse = R"({"status":{"10":0,"96":1000,"97":7}})";
}
int main() {
  reset(); nextPoll();
  assert(pendingTask && requests.empty() && applyStateCount == 0);
  // UI loop remains free; another tick does not launch duplicate requests.
  refreshCameraPresetWhileIdle(); assert(requests.empty());
  finishWorker(); assert(requests.size() == 2 && applyStateCount == 0);
  refreshCameraPresetWhileIdle(); assert(applyStateCount == 1 && applyCatalogCount == 1);

  reset(); nextPoll(); finishWorker(); touchActive = true;
  refreshCameraPresetWhileIdle(); assert(cameraPresetPoll && applyStateCount == 0);
  touchActive = false; refreshCameraPresetWhileIdle(); assert(applyStateCount == 1);

  reset(); nextPoll(); cancelCameraPresetPoll(); finishWorker();
  refreshCameraPresetWhileIdle(); assert(requests.empty() && applyStateCount == 0);
  reset(); nextPoll(); finishWorker(); cancelCameraPresetPoll();
  refreshCameraPresetWhileIdle(); assert(applyStateCount == 0);
  reset(); nextPoll(); finishWorker(); boundBleAddress = "camera-b";
  refreshCameraPresetWhileIdle(); assert(applyStateCount == 0);
  reset(); nextPoll(); finishWorker(); homeCameraConnected = false;
  refreshCameraPresetWhileIdle(); assert(applyStateCount == 0);

  reset(); stateResponse = R"({"status":{"10":1,"96":1000,"97":7}})";
  nextPoll(); finishWorker(); assert(requests.size() == 1);
  refreshCameraPresetWhileIdle(); assert(recording && handoffCount == 1 && applyCatalogCount == 0);
  nextPoll(); assert(!pendingTask);

  reset(); httpOk = false; nextPoll(); finishWorker(); refreshCameraPresetWhileIdle();
  assert(applyStateCount == 0 && applyCatalogCount == 0);
  reset(); taskOk = false; nextPoll(); assert(!cameraPresetPoll && !pendingTask);
  reset(); recording = true; nextPoll(); assert(!pendingTask);
  reset(); goproActionBusy = true; nextPoll(); assert(!pendingTask);
  reset(); snapshotPreviewBusy = true; nextPoll(); assert(!pendingTask);
  reset(); pairingInProgress = true; nextPoll(); assert(!pendingTask);
  reset(); touchActive = true; nextPoll(); assert(!pendingTask);
  reset(); displayOn = false; nextPoll(); assert(!pendingTask);
  reset(); wifiConnected = false; nextPoll(); assert(!pendingTask);
  reset(); pendingHomeAction = PendingHomeAction::Connect; nextPoll(); assert(!pendingTask);
  // Completed results are freed immediately when a foreground action cancels,
  // rather than being retained through the recording/Bluetooth handoff.
  reset(); nextPoll(); finishWorker(); cancelCameraPresetPoll();
  assert(!cameraPresetPoll && !pendingTask && applyStateCount == 0);
  // An in-flight worker must finish and release its HTTP resources before the
  // caller is allowed to switch radios. UI servicing continues while waiting.
  reset(); nextPoll(); finishOnDelay = true;
  assert(stopCameraPresetPoll());
  assert(!cameraPresetPoll && !pendingTask && uiServiceCount > 0);
  assert(requests.empty()); // cancelled worker cannot start another GET
  // If the worker cannot finish promptly, keep ownership and refuse handoff.
  reset(); nextPoll(); uint32_t waitStarted = now;
  assert(!stopCameraPresetPoll());
  assert(cameraPresetPoll && pendingTask && now - waitStarted == 2500);
  finishWorker(); assert(stopCameraPresetPoll());
  assert(!cameraPresetPoll && !pendingTask);
  std::cout << "Background preset polling tests passed\n";
}
