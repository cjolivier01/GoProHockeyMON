#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>
#include "src/amoled/parts/camera_presets.h"

// Hardware/HTTP boundary doubles. The transaction below is the production code.
class String : public std::string {
public:
  using std::string::string;
  using std::string::operator=;
  using std::string::operator+=;
  String(const std::string &s) : std::string(s) {}
  bool isEmpty() const { return empty(); }
  String &operator+=(int32_t value) { append(std::to_string(value)); return *this; }
};
struct SerialMock {
  template<class... Args> void printf(const char *, Args...) {}
  void println(const char *) {}
} Serial;
struct UdpMock { void stop() {} } previewUdp;
struct SnapshotVideoFraming { bool valid = false; } snapshotVideoFraming;
constexpr int32_t kGoProVideoPresetGroup = 1000;
constexpr int LV_OBJ_FLAG_HIDDEN = 1, MALLOC_CAP_SPIRAM = 1, MALLOC_CAP_8BIT = 2;
constexpr size_t kMaxJpegBytes = 4096;
int labels[3];
int *previewLabel = &labels[0], *actionLabel = &labels[1], *recordingOverlay = &labels[2];
bool actionHidden;
bool recording, snapshotPreviewBusy, previewUdpListening, previewStreamRequested;
bool previewHasImage, snapshotPreviewPrepared, previewFullscreen;
uint8_t *previewJpegCache;
size_t previewJpegCacheLen;
int32_t activeCameraPresetId, activeCameraPresetGroup;
String captureMode, lastSnapshotMediaPath, action;
uint32_t now;
std::vector<std::string> commands;
int32_t cameraPreset, originalPreset, originalGroup;
bool stateOk, identityKnown, photoOk, shutterOk, mediaFound, allocationOk;
bool downloadOk, decodeOk, cacheOk, deleteOk, restoreOk, restoreApplied, restoreStateOk;
int stateReads, mediaReads, alignCalls;
bool restoredFraming;

uint32_t millis() { return now; }
void delay(uint32_t ms) { now += ms; }
void serviceLvgl() {}
void logMemory(const char *) {}
void releaseH264PreviewResources(const char *) {}
void applyCaptureLabels() {}
void logSnapshotVideoFraming(const SnapshotVideoFraming &) {}
void setAction(const char *message) { action = message; }
void lv_obj_add_flag(int *, int) {}
void lv_obj_clear_flag(int *, int) {}
void lv_label_set_text(int *, const char *) {}
void setObjHidden(int *object, bool hidden) {
  if (object == actionLabel) actionHidden = hidden;
}
void setPreviewFullscreen(bool fullscreen) { previewFullscreen = fullscreen; }
void clearPreviewJpegCache() {}
void alignTemporaryPhotoPresetForSnapshot() { ++alignCalls; }
SnapshotVideoFraming currentSnapshotVideoFraming() {
  // Framing must be sampled while Hockey is still selected.
  restoredFraming = cameraPreset == originalPreset;
  return {true};
}
constexpr uint32_t kHttpTimeoutMs = 4000;
std::vector<std::pair<uint16_t, int>> storedSettings;
void storeSettingValue(uint16_t id, int value) { storedSettings.emplace_back(id, value); }
void refreshCaptureOverlayFromState() {}
bool readStatusInt(JsonObjectConst status, const char *idKey, const char *sdkKey,
                   const char *nameKey, int32_t &out) {
  return CameraPresets::integer(status[idKey], out) ||
         CameraPresets::integer(status[sdkKey], out) ||
         CameraPresets::integer(status[nameKey], out);
}
DeserializationError deserializeJson(JsonDocument &doc, const String &body) {
  return ArduinoJson::deserializeJson(doc, body.c_str());
}
int httpGetGoProBodyWithTimeout(const String &path, String &body, uint32_t) {
  assert(path.find("/gopro/camera/presets/get") == 0);
  body = "{\"presetGroupArray\":[{\"id\":" + std::string("\"") +
         (originalGroup == 1000 ? "PRESET_GROUP_ID_VIDEO" :
          originalGroup == 1001 ? "PRESET_GROUP_ID_PHOTO" : "PRESET_GROUP_ID_TIMELAPSE") +
         "\"" + ",\"presetArray\":[{\"id\":999,\"titleId\":10},{\"id\":" +
         std::to_string(originalPreset) + ",\"customName\":\"Hockey\",\"settingArray\":[{\"id\":2,\"value\":1}]}]}]}";
  return 200;
}
#include "src/amoled/parts/camera_presets.inc"
bool syncCameraState() {
  ++stateReads;
  if (!stateOk || (stateReads > 1 && !restoreStateOk)) return false;
  JsonDocument state;
  if (identityKnown) {
    state["97"] = cameraPreset;
    state["96"] = cameraPreset == originalPreset ? originalGroup : 1001;
  }
  applyCameraPresetStatus(state.as<JsonObjectConst>());
  if (!recording) syncCameraPresets();
  return true;
}
int httpGetGoProStatus(const String &path) { commands.push_back(path); return 200; }
bool httpGetGoPro(const String &path) {
  commands.push_back(path);
  if (path == "/gopro/camera/presets/set_group?id=1001") {
    cameraPreset = 65536; // Simulate an applied command even if its reply is lost.
    return photoOk;
  }
  if (path == "/gopro/camera/shutter/start") return shutterOk;
  const std::string prefix = "/gopro/camera/presets/load?id=";
  if (path.rfind(prefix, 0) == 0) {
    assert(std::stoi(path.substr(prefix.size())) == originalPreset);
    if (restoreOk && restoreApplied) cameraPreset = originalPreset;
    return restoreOk;
  }
  assert(false && "Unexpected camera mutation");
  return false;
}
bool fetchLatestJpegPath(String &path) {
  ++mediaReads;
  path = mediaReads == 1 || !mediaFound ? "100GOPRO/OLD.JPG" : "100GOPRO/NEW.JPG";
  return true;
}
String urlEncodePathParam(const String &path) { return path; }
void *heap_caps_malloc(size_t size, int) { return allocationOk ? std::malloc(size) : nullptr; }
void heap_caps_free(void *buffer) { std::free(buffer); }
bool downloadPreviewJpeg(const String &, uint8_t *, size_t, size_t &length) {
  previewFullscreen = true;
  actionHidden = true;
  length = downloadOk ? 2048 : 0;
  return downloadOk && decodeOk;
}
bool shrinkAndAdoptPreviewJpegCache(uint8_t *buffer, size_t) {
  if (cacheOk) std::free(buffer);
  return cacheOk;
}
bool deleteGoProMedia(const String &path) {
  assert(path == "100GOPRO/NEW.JPG");
  commands.push_back("delete:" + path);
  return deleteOk;
}
bool redrawCachedPreviewJpeg() { return decodeOk; }

#include "src/amoled/parts/snapshot_capture.inc"

void reset(int32_t preset = 7, int32_t group = 1000) {
  commands.clear(); storedSettings.clear(); now = 0; stateReads = mediaReads = alignCalls = 0;
  originalPreset = cameraPreset = activeCameraPresetId = preset;
  originalGroup = activeCameraPresetGroup = group;
  captureMode = "Hockey"; action.clear(); lastSnapshotMediaPath.clear();
  actionHidden = false;
  recording = snapshotPreviewBusy = previewHasImage = previewFullscreen = false;
  snapshotPreviewPrepared = previewUdpListening = previewStreamRequested = false;
  previewJpegCache = nullptr; previewJpegCacheLen = 0;
  stateOk = identityKnown = photoOk = shutterOk = mediaFound = allocationOk = true;
  downloadOk = decodeOk = cacheOk = deleteOk = restoreOk = restoreApplied = restoreStateOk = true;
  restoredFraming = false;
}
void expectRestore() {
  assert(cameraPreset == originalPreset);
  assert(captureMode == "Hockey");
  assert(!snapshotPreviewBusy && !snapshotPreviewPrepared);
  auto restore = "/gopro/camera/presets/load?id=" + std::to_string(originalPreset);
  assert(std::count(commands.begin(), commands.end(), restore) == 1);
  assert(std::find(commands.begin(), commands.end(), "/gopro/camera/presets/set_group?id=1000") == commands.end());
}
void expectNoModeChange() {
  assert(cameraPreset == originalPreset);
  assert(commands.empty());
  for (const auto &command : commands) {
    assert(command.find("/presets/") == std::string::npos);
    assert(command.find("/shutter/") == std::string::npos);
  }
  assert(!snapshotPreviewBusy);
}
int main() {
  reset(); assert(fetchSnapshotPreview()); expectRestore();
  assert(restoredFraming && alignCalls == 1 && previewHasImage);
  assert(!storedSettings.empty() && storedSettings.back().first == 2 && storedSettings.back().second == 1);
  assert(std::count(commands.begin(), commands.end(), "delete:100GOPRO/NEW.JPG") == 1);
  reset(0); assert(fetchSnapshotPreview()); expectRestore();
  reset(65536, 1001); assert(fetchSnapshotPreview()); expectRestore(); assert(alignCalls == 0);
  reset(131072, 1002); assert(fetchSnapshotPreview()); expectRestore(); assert(alignCalls == 0);
  reset(); stateOk = false; assert(!fetchSnapshotPreview()); expectNoModeChange();
  reset(); identityKnown = false; assert(!fetchSnapshotPreview()); expectNoModeChange();
  reset(); recording = true; assert(!fetchSnapshotPreview()); expectNoModeChange();
  reset(); photoOk = false; assert(!fetchSnapshotPreview()); expectRestore();
  reset(); shutterOk = false; assert(!fetchSnapshotPreview()); expectRestore();
  reset(); mediaFound = false; assert(!fetchSnapshotPreview()); expectRestore();
  reset(); allocationOk = false; assert(!fetchSnapshotPreview()); expectRestore();
  reset(); downloadOk = false; assert(!fetchSnapshotPreview()); expectRestore();
  reset(); decodeOk = false; assert(!fetchSnapshotPreview()); expectRestore();
  reset(); cacheOk = false; assert(!fetchSnapshotPreview()); expectRestore();
  reset(); deleteOk = false; assert(fetchSnapshotPreview()); expectRestore();
  assert(action == "Preview JPEG delete failed");
  reset(); restoreOk = false; assert(fetchSnapshotPreview());
  assert(cameraPreset == 65536 && action == "Preview shown; profile restore failed");
  assert(!actionHidden && !previewFullscreen);
  reset(); restoreApplied = false; assert(fetchSnapshotPreview());
  assert(cameraPreset == 65536 && action == "Preview shown; profile restore failed");
  assert(!actionHidden && !previewFullscreen);
  reset(); restoreStateOk = false; assert(fetchSnapshotPreview());
  assert(action == "Preview shown; profile restore failed");
  reset(); shutterOk = restoreOk = false; assert(!fetchSnapshotPreview());
  assert(action == "Camera profile restore failed");
  assert(!actionHidden && !previewFullscreen);
  reset(); allocationOk = restoreOk = false; assert(!fetchSnapshotPreview());
  assert(action == "Camera profile restore failed");
  assert(!actionHidden && !previewFullscreen);
  reset(); downloadOk = restoreOk = false; assert(!fetchSnapshotPreview());
  assert(action == "Camera profile restore failed");
  assert(!actionHidden && !previewFullscreen);
  std::cout << "Snapshot transaction tests passed (21 scenarios)\n";
}
