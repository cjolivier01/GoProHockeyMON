#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

// The framework owns its client, including after connect() fails. Native ASAN
// catches the prior double free when this owner later deinitializes the stack.
class String : public std::string {
public:
  using std::string::string;
  bool isEmpty() const { return empty(); }
};
struct BLEAdvertisedDevice {};
struct BLEScan {} scanner;
struct BLERemoteCharacteristic {
  bool canNotify() { return false; }
  template <typename T> void registerForNotify(T) {}
};
struct BLERemoteService {
  BLERemoteCharacteristic *getCharacteristic(int) { return nullptr; }
};
int createdClients, deletedClients, connectCalls, scanCalls;
bool connectSucceeds, initSucceeds, clientAvailable, pollStopped, cancelled;
struct BLEClient {
  bool connected = false;
  BLEClient() { ++createdClients; }
  ~BLEClient() { ++deletedClients; }
  bool isConnected() const { return connected; }
  bool connectTimeout(BLEAdvertisedDevice *device, uint32_t) {
    assert(device); ++connectCalls; connected = connectSucceeds; return connected;
  }
  void disconnect() { connected = false; }
  BLERemoteService *getService(int) { return nullptr; }
};
BLEClient *bleClient;
BLEAdvertisedDevice *bestBleDevice;
bool recording, bleConnected, bleStackReady, stackInitialized;
bool pairingInProgress, cameraWakeInProgress, selectedBleFallback, allowAnyCameraScan;
bool connectRetryAvailable, wakeAvailable;
String boundBleAddress;
int label;
int *statusLabel = &label, *cameraLabel = &label, *bleIndicator = &label;
constexpr int kControlService = 1, kCommandResponse = 2, kSettingsResponse = 3, kQueryResponse = 4;
constexpr uint32_t kPairBleConnectTimeoutMs = 30000, kBleWakeConnectTimeoutMs = 5000, kBleConnectTimeoutMs = 15000;
constexpr int WIFI_MODE_NULL = 0, WIFI_OFF = 0;
struct WifiMock {
  int getMode() { return WIFI_MODE_NULL; }
  void disconnect(bool, bool) {}
  void mode(int) {}
} WiFi;
struct SerialMock { void println(const char *) {} } Serial;
std::string action;
void setAction(const char *message) { action = message; }
void logMemory(const char *) {}
void delay(uint32_t) {}
void serviceLvgl() {}
void serviceConnectionUi() {}
void configureBleSecurity() {}
bool stopCameraPresetPoll() { return pollStopped; }
bool operationCancelled() { return cancelled; }
void lv_label_set_text(int *, const char *) {}
void lv_obj_set_style_text_color(int *, uint32_t, int) {}
uint32_t lv_color_hex(uint32_t value) { return value; }
void showPairingPopup(const char *) {}
void setCameraWakeAvailable(bool available) { wakeAvailable = available; }
void setConnectRetryAvailable(bool available) { connectRetryAvailable = available; }
void commandResponseNotify() {}
void clearBleScanDevices() { delete bestBleDevice; bestBleDevice = nullptr; }
bool scanForCamera() {
  ++scanCalls; bestBleDevice = new BLEAdvertisedDevice; return true;
}
namespace BLEDevice {
BLEClient *ownedClient;
bool getInitialized() { return stackInitialized; }
bool init(const char *) { stackInitialized = initSucceeds; return stackInitialized; }
BLEScan *getScan() { return stackInitialized ? &scanner : nullptr; }
BLEClient *createClient() {
  assert(stackInitialized && !ownedClient);
  ownedClient = clientAvailable ? new BLEClient : nullptr;
  return ownedClient;
}
void deinit(bool) {
  // Matches BLEDevice.cpp: the framework deletes its owned client. It cannot
  // know about an application deleting the object without clearing this owner.
  delete ownedClient;
  ownedClient = nullptr;
  stackInitialized = false;
}
}

#include "src/amoled/parts/ble_initialization.inc"
#include "src/amoled/parts/ble_connection.inc"

void deinit() {
  // Same ownership ordering used by shutdownBleForWifi: the application drops
  // its non-owning handle before asking BLEDevice to dispose of the client.
  bleClient = nullptr;
  bleConnected = false;
  BLEDevice::deinit(false);
  bleStackReady = false;
}
void reset() {
  deinit(); clearBleScanDevices();
  createdClients = deletedClients = connectCalls = scanCalls = 0;
  initSucceeds = clientAvailable = pollStopped = true;
  connectSucceeds = cancelled = recording = false;
  pairingInProgress = cameraWakeInProgress = selectedBleFallback = allowAnyCameraScan = false;
  connectRetryAvailable = wakeAvailable = false;
  boundBleAddress = "aa:bb:cc:dd:ee:ff";
  action.clear();
}
int main() {
  // Original regression: a failed connect followed by shutdown double-deleted
  // the same client through the application and BLEDevice ownership paths.
  reset(); assert(!connectBle());
  assert(bleClient && bleClient == BLEDevice::ownedClient && deletedClients == 0);
  assert(!bleClient->isConnected() && connectRetryAvailable && wakeAvailable);
  deinit(); assert(createdClients == 1 && deletedClients == 1);

  // Retry keeps the exact client alive, including for late stack callbacks.
  reset(); assert(!connectBle()); BLEClient *failedClient = bleClient;
  assert(!BLEDevice::ownedClient->isConnected());
  connectSucceeds = true; assert(connectBle());
  assert(bleClient == failedClient && createdClients == 1 && connectCalls == 2 && scanCalls == 2);
  assert(bleConnected && !wakeAvailable && !connectRetryAvailable);
  deinit(); assert(deletedClients == 1);

  reset(); assert(!connectBle()); deinit();
  connectSucceeds = true; assert(connectBle());
  assert(createdClients == 2 && deletedClients == 1);
  deinit(); assert(deletedClients == 2);

  reset(); recording = true; assert(!connectBle());
  assert(recording && !bleConnected && deletedClients == 0);
  deinit(); assert(recording && deletedClients == 1);

  reset(); initSucceeds = false; assert(!connectBle());
  assert(createdClients == 0 && scanCalls == 0 && connectCalls == 0 && !bleStackReady);
  reset(); clientAvailable = false; assert(!connectBle());
  assert(createdClients == 0 && connectCalls == 0 && !bleConnected);
  reset(); pollStopped = false; assert(!connectBle());
  assert(createdClients == 0 && scanCalls == 0 && connectCalls == 0);

  reset(); connectSucceeds = true; assert(connectBle());
  assert(connectBle()); assert(createdClients == 1 && connectCalls == 1);
  deinit(); clearBleScanDevices(); assert(deletedClients == 1);
  std::cout << "BLE connection ownership tests passed (8 scenarios)\n";
}
