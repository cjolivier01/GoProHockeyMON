#include <cassert>
#include <cstdint>
#include <functional>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <vector>

// Only the BLE transport and owned characteristic are mocked. Service methods
// below are extracted from the installed framework by test_ble_discovery.py.
constexpr int BLE_HS_ENOTCONN = 7, BLE_HS_EDONE = 14, BLE_NPL_TIME_FOREVER = -1;
#define log_v(...) do {} while (0)
#define log_d(...) do {} while (0)
#define log_e(...) do {} while (0)
struct BLEUUID {
  std::string value;
  std::string toString() const { return value; }
};
struct ble_gatt_error { int status; };
struct ble_gatt_chr { uint16_t val_handle; BLEUUID uuid; };
struct BLEClient { uint16_t getConnId() const { return 42; } } client;
struct BLETaskData {
  explicit BLETaskData(void *instance) : m_pInstance(instance) {}
  void *m_pInstance;
  int m_flags = 0;
};
std::function<void()> onRelease;
struct BLEUtils {
  static void taskRelease(BLETaskData &data, int status) {
    data.m_flags = status;
    // Deterministically schedule the other core at the notification boundary.
    // Move the hook first, so nested discovery cannot run it recursively.
    auto callback = std::move(onRelease);
    onRelease = nullptr;
    if (callback) callback();
  }
  static void taskWait(BLETaskData &, int) {}
};
struct BLERemoteService;
struct BLERemoteCharacteristic {
  static std::set<BLERemoteCharacteristic *> live;
  BLEUUID uuid;
  BLERemoteCharacteristic(BLERemoteService *, const ble_gatt_chr *chr) : uuid(chr->uuid) { live.insert(this); }
  ~BLERemoteCharacteristic() { assert(live.erase(this) == 1); }
  BLEUUID getUUID() const { return uuid; }
};
std::set<BLERemoteCharacteristic *> BLERemoteCharacteristic::live;
struct BLERemoteService {
  ~BLERemoteService();
  BLERemoteCharacteristic *getCharacteristic(BLEUUID uuid);
  void retrieveCharacteristics();
  void removeCharacteristics();
  BLEClient *getClient() const { return m_pClient; }
  static int characteristicDiscCB(uint16_t, const ble_gatt_error *, const ble_gatt_chr *, void *);
  std::map<std::string, BLERemoteCharacteristic *> m_characteristicMap;
  std::map<uint16_t, BLERemoteCharacteristic *> m_characteristicMapByHandle;
  bool m_haveCharacteristics = false;
  BLEClient *m_pClient = &client;
  uint16_t m_startHandle = 1, m_endHandle = 100;
};
std::vector<ble_gatt_chr> discovered;
int discoveryCalls = 0, terminalStatus = BLE_HS_EDONE;
int ble_gattc_disc_all_chrs(uint16_t connection, uint16_t, uint16_t,
                          int (*callback)(uint16_t, const ble_gatt_error *, const ble_gatt_chr *, void *), void *arg) {
  ++discoveryCalls;
  ble_gatt_error success{0};
  for (const auto &chr : discovered) callback(connection, &success, &chr, arg);
  ble_gatt_error done{terminalStatus};
  callback(connection, &done, nullptr, arg);
  return 0;
}

#include "ble_discovery_under_test.inc"

void reset() {
  assert(BLERemoteCharacteristic::live.empty());
  discoveryCalls = 0;
  terminalStatus = BLE_HS_EDONE;
  discovered = {{2, {"command"}}, {4, {"settings"}}, {6, {"query"}}};
  onRelease = nullptr;
}

void releaseBoundary() {
  reset();
  bool publishedAtWake = false;
  {
    BLERemoteService service;
    onRelease = [&] {
      publishedAtWake = service.m_haveCharacteristics;
      assert(service.getCharacteristic({"settings"}));
    };
    assert(service.getCharacteristic({"command"}));
    assert(service.m_characteristicMapByHandle.size() == 3);
  }
#if EXPECT_FIXED
  assert(publishedAtWake);
  assert(discoveryCalls == 1);
  assert(BLERemoteCharacteristic::live.empty());
#else
  assert(!publishedAtWake);
  assert(discoveryCalls == 2);
  assert(BLERemoteCharacteristic::live.size() == 3);
  // Reclaim deliberately demonstrated leaks so the baseline also runs with ASAN.
  while (!BLERemoteCharacteristic::live.empty()) delete *BLERemoteCharacteristic::live.begin();
#endif
}

#if EXPECT_FIXED
void repeatedDiscovery() {
  reset();
  {
    BLERemoteService service;
    service.retrieveCharacteristics();
    for (int i = 0; i < 20; ++i) service.retrieveCharacteristics();
    assert(BLERemoteCharacteristic::live.size() == 3);
    assert(service.m_characteristicMapByHandle.size() == 3);
  }
  assert(BLERemoteCharacteristic::live.empty());
}

void partialFailureRetry() {
  reset();
  {
    BLERemoteService service;
    terminalStatus = 13;
    discovered.resize(1);
    service.retrieveCharacteristics();
    assert(!service.m_haveCharacteristics);
    terminalStatus = BLE_HS_EDONE;
    discovered.push_back({4, {"settings"}});
    assert(service.getCharacteristic({"settings"}));
    assert(service.m_haveCharacteristics);
    assert(discoveryCalls == 2);
    assert(BLERemoteCharacteristic::live.size() == 2);
  }
  assert(BLERemoteCharacteristic::live.empty());
}

void sameUuidDifferentHandles() {
  reset();
  discovered = {{2, {"shared"}}, {4, {"shared"}}};
  {
    BLERemoteService service;
    assert(service.getCharacteristic({"shared"}));
    assert(service.m_characteristicMap.size() == 1);
    assert(service.m_characteristicMapByHandle.size() == 2);
    assert(BLERemoteCharacteristic::live.size() == 2);
  }
  assert(BLERemoteCharacteristic::live.empty());
}

void disconnectedAndForeignResults() {
  reset();
  {
    BLERemoteService service;
    BLETaskData data(&service);
    ble_gatt_error disconnected{BLE_HS_ENOTCONN};
    bool resumed = false;
    onRelease = [&] { resumed = true; };
    assert(service.characteristicDiscCB(42, &disconnected, nullptr, &data) == BLE_HS_ENOTCONN);
    assert(resumed && !service.m_haveCharacteristics);
    ble_gatt_error success{0};
    service.characteristicDiscCB(99, &success, &discovered.front(), &data);
    assert(service.m_characteristicMap.empty());
    assert(BLERemoteCharacteristic::live.empty());
  }
}
#endif

int main() {
  releaseBoundary();
#if EXPECT_FIXED
  repeatedDiscovery();
  partialFailureRetry();
  sameUuidDifferentHandles();
  disconnectedAndForeignResults();
  for (int cycle = 0; cycle < 50; ++cycle) releaseBoundary();
  std::cout << "BLE discovery: completion, duplicate handles, retry, teardown and 50 cycles passed\n";
#else
  std::cout << "BLE discovery: original callback reproduced premature wake and three leaked objects\n";
#endif
}
