#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>
constexpr int WL_CONNECTED = 3, WIFI_MODE_NULL = 0, WIFI_OFF = 0;
constexpr const char *LV_SYMBOL_WIFI = "wifi";
bool drainOk, drainChecked, recording, bleConnected, recordingReadOk, bleHandoffOk;
bool previewStreamRequested, snapshotPreviewPrepared, previewUdpListening;
bool goProWifiSuspendedForRecording, homeCameraConnected;
int wifiDisconnects, wifiOffs, bleCommands;
std::string action;
void *wifiLabel = nullptr, *wifiIndicator = nullptr;
struct SerialMock {
  void print(const char *) {}
  void println() {}
} Serial;
struct WifiMock {
  int status() { return wifiOffs ? 0 : WL_CONNECTED; }
  int getMode() { return wifiOffs ? WIFI_MODE_NULL : 1; }
  void disconnect(bool, bool) { assert(drainOk && drainChecked); ++wifiDisconnects; }
  void mode(int mode) { assert(mode == WIFI_OFF && drainOk && drainChecked); ++wifiOffs; }
} WiFi;
struct UdpMock { void stop() { assert(drainOk && drainChecked); } } previewUdp;
bool stopCameraPresetPoll() { drainChecked = true; return drainOk; }
void delay(uint32_t) {}
void serviceLvgl() {}
void setAction(const char *text) { action = text; }
void lv_label_set_text(void *, const char *) {}
void lv_obj_set_style_text_color(void *, int, int) {}
int lv_color_hex(int color) { return color; }
void setHomeCameraConnected(bool connected) { homeCameraConnected = connected; }
bool refreshRecordingStateBle() { return recordingReadOk; }
bool setGoProWifiApBle(bool enabled) {
  assert(!enabled && drainOk && drainChecked && wifiOffs == 1);
  ++bleCommands; return bleHandoffOk;
}
#include "src/amoled/parts/recording_radio_handoff.inc"
void reset() {
  drainOk = recordingReadOk = bleHandoffOk = true;
  drainChecked = recording = bleConnected = goProWifiSuspendedForRecording = false;
  previewStreamRequested = snapshotPreviewPrepared = previewUdpListening = true;
  homeCameraConnected = true;
  wifiDisconnects = wifiOffs = bleCommands = 0;
  action.clear();
}
void expectRadioUnchanged() {
  assert(wifiDisconnects == 0 && wifiOffs == 0 && bleCommands == 0);
  assert(!goProWifiSuspendedForRecording);
  assert(previewStreamRequested && previewUdpListening && snapshotPreviewPrepared);
}
int main() {
  reset(); drainOk = false;
  assert(!markGoProWifiDisconnectedForRecording()); expectRadioUnchanged();
  reset(); drainOk = false; recording = true;
  assert(!suspendGoProWifiForRecording("recording")); expectRadioUnchanged(); assert(recording);
  // Reproduce the review finding: a failed init/recording preflight must not
  // bypass the worker drain by calling the lower-level teardown directly.
  reset(); drainOk = recordingReadOk = false;
  assert(!ensureNotRecordingForWifi("preflight failed")); expectRadioUnchanged();
  reset(); drainOk = recordingReadOk = false; recording = true;
  assert(!ensureNotRecordingForWifi("recording")); expectRadioUnchanged(); assert(recording);
  reset(); recording = true;
  assert(suspendGoProWifiForRecording("recording"));
  assert(drainChecked && wifiOffs == 1 && bleCommands == 1 && goProWifiSuspendedForRecording);
  reset(); recording = true; bleHandoffOk = false;
  assert(!suspendGoProWifiForRecording("recording")); assert(recording && wifiOffs == 1);
  reset(); recordingReadOk = false;
  assert(!ensureNotRecordingForWifi("failed")); assert(drainChecked && wifiOffs == 1);
  reset(); assert(ensureNotRecordingForWifi("idle")); expectRadioUnchanged();
  std::cout << "Recording radio handoff tests passed (8 scenarios)\n";
}
