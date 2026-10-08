#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

// Compile the production BLE initialization/resource guards against a BLE
// boundary that can fail exactly as Arduino's BLEDevice does during handoff.
struct BLEScan {} scanner;
struct BLEClient {} client;
BLEClient *bleClient;
bool bleStackReady, bleConnected, recording;
bool stackInitialized, initSucceeds, scannerAvailable, clientAvailable, pollStopped;
int initCalls, scanCalls, clientCalls, securityCalls, stopCalls, wifiMode;
std::string action;
std::vector<std::string> events;
constexpr int WIFI_MODE_NULL = 0, WIFI_OFF = 0, WIFI_STA = 1;
struct WifiMock {
  int getMode() { return wifiMode; }
  void disconnect(bool, bool) { events.push_back("wifi disconnect"); }
  void mode(int mode) { assert(mode == WIFI_OFF); wifiMode = mode; events.push_back("wifi off"); }
} WiFi;
struct SerialMock { void println(const char *) {} } Serial;
namespace BLEDevice {
bool getInitialized() { return stackInitialized; }
void init(const char *) {
  assert(pollStopped && wifiMode == WIFI_OFF);
  ++initCalls; events.push_back("ble init"); stackInitialized = initSucceeds;
}
BLEScan *getScan() {
  assert(stackInitialized);
  ++scanCalls; return scannerAvailable ? &scanner : nullptr;
}
BLEClient *createClient() {
  assert(stackInitialized);
  ++clientCalls; return clientAvailable ? &client : nullptr;
}
}
bool stopCameraPresetPoll() { ++stopCalls; events.push_back("stop poll"); return pollStopped; }
void configureBleSecurity() { assert(stackInitialized); ++securityCalls; events.push_back("security"); }
void logMemory(const char *) {}
void setAction(const char *message) { action = message; }
void delay(uint32_t) {}

#include "src/amoled/parts/ble_initialization.inc"

void reset() {
  bleClient = nullptr;
  bleStackReady = bleConnected = recording = stackInitialized = false;
  initSucceeds = scannerAvailable = clientAvailable = pollStopped = true;
  initCalls = scanCalls = clientCalls = securityCalls = stopCalls = 0;
  wifiMode = WIFI_STA;
  events.clear(); action.clear();
}
void expectInitFailure() {
  assert(!stackInitialized && !bleStackReady && !bleConnected);
  assert(initCalls == 1 && securityCalls == 0 && scanCalls == 0 && clientCalls == 0);
  assert(action == "BLE initialization failed");
}
int main() {
  reset(); assert(initBleStack());
  assert(stackInitialized && bleStackReady && initCalls == 1 && securityCalls == 1);
  assert(events == std::vector<std::string>({"stop poll", "wifi disconnect", "wifi off", "ble init", "security"}));

  reset(); stackInitialized = true; bleConnected = true; assert(initBleStack());
  assert(bleStackReady && bleConnected && initCalls == 0 && wifiMode == WIFI_STA);
  assert(events == std::vector<std::string>({"stop poll", "security"}));

  reset(); initSucceeds = false; bleStackReady = bleConnected = true;
  assert(!initBleStack()); expectInitFailure();
  reset(); initSucceeds = false; assert(!getGoProBleScanner()); expectInitFailure();
  reset(); initSucceeds = false; assert(!ensureGoProBleClient()); expectInitFailure();
  reset(); initSucceeds = false; recording = true;
  assert(!ensureGoProBleClient()); expectInitFailure(); assert(recording);

  reset(); scannerAvailable = false;
  assert(!getGoProBleScanner());
  assert(bleStackReady && !bleConnected && scanCalls == 1 && action == "BLE scanner unavailable");
  reset(); assert(getGoProBleScanner() == &scanner); assert(scanCalls == 1);

  reset(); clientAvailable = false; recording = true;
  assert(!ensureGoProBleClient());
  assert(bleStackReady && !bleConnected && recording && clientCalls == 1);
  assert(action == "BLE client unavailable");
  reset(); assert(ensureGoProBleClient()); assert(bleClient == &client && clientCalls == 1);
  assert(ensureGoProBleClient()); assert(clientCalls == 1);

  reset(); initSucceeds = false; assert(!initBleStack());
  initSucceeds = true; assert(initBleStack());
  assert(bleStackReady && initCalls == 2 && securityCalls == 1);

  reset(); pollStopped = false; bleStackReady = recording = true;
  assert(!initBleStack());
  assert(!bleStackReady && recording && wifiMode == WIFI_STA && initCalls == 0);
  assert(events == std::vector<std::string>({"stop poll"}));
  reset(); pollStopped = false; stackInitialized = true;
  assert(!getGoProBleScanner());
  assert(scanCalls == 0 && initCalls == 0 && securityCalls == 0 && wifiMode == WIFI_STA);

  std::cout << "BLE initialization tests passed (13 scenarios)\n";
}
