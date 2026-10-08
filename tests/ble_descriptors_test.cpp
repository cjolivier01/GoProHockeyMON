#include <cassert>
#include <cstdint>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <utility>
#include <vector>

constexpr int BLE_HS_EDONE = 14, BLE_NPL_TIME_FOREVER = -1;
#define log_d(...) do {} while (0)
#define log_e(...) do {} while (0)
struct NativeUuid { unsigned u; };
struct BLEUUID {
  NativeUuid uuid;
  std::string toString() const { return std::to_string(uuid.u); }
  const NativeUuid *getNative() const { return &uuid; }
};
int ble_uuid_cmp(const unsigned *left, const unsigned *right) { return *left != *right; }
struct ble_gatt_error { int status; };
struct ble_gatt_dsc { uint16_t handle; NativeUuid uuid; };
struct BLEClient { uint16_t getConnId() const { return 42; } } client;
struct BLETaskData {
  explicit BLETaskData(void *instance) : m_pInstance(instance) {}
  void *m_pInstance;
  int m_flags = 0;
};
struct BLEUtils {
  static void taskRelease(BLETaskData &data, int status) { data.m_flags = status; }
  static void taskWait(BLETaskData &, int) {}
};
struct desc_filter_t { const BLEUUID *uuid; void *task_data; };
struct BLERemoteCharacteristic;
struct BLERemoteDescriptor {
  static std::set<BLERemoteDescriptor *> live;
  uint16_t handle;
  BLEUUID uuid;
  BLERemoteDescriptor(BLERemoteCharacteristic *, const ble_gatt_dsc *dsc) : handle(dsc->handle), uuid{dsc->uuid} { live.insert(this); }
  ~BLERemoteDescriptor() { assert(live.erase(this) == 1); }
  BLEUUID getUUID() const { return uuid; }
};
std::set<BLERemoteDescriptor *> BLERemoteDescriptor::live;
struct BLERemoteService {
  std::map<uint16_t, BLERemoteCharacteristic *> m_characteristicMapByHandle;
  uint16_t endHandle = 18;
  uint16_t getEndHandle() const { return endHandle; }
  BLEClient *getClient() const { return &client; }
};
struct BLERemoteCharacteristic {
  BLERemoteService *service;
  uint16_t m_handle, m_defHandle;
  std::map<std::string, BLERemoteDescriptor *> m_descriptorMap;
  bool m_descriptorsRetrieved = false;
  BLERemoteCharacteristic(BLERemoteService &owner, uint16_t definition, uint16_t value)
      : service(&owner), m_handle(value), m_defHandle(definition) { owner.m_characteristicMapByHandle[value] = this; }
  ~BLERemoteCharacteristic() { removeDescriptors(); }
  BLERemoteService *getRemoteService() const { return service; }
  uint16_t getHandle() const { return m_handle; }
  bool retrieveDescriptors(const BLEUUID *filter = nullptr);
  void removeDescriptors();
  static int descriptorDiscCB(uint16_t, const ble_gatt_error *, uint16_t, const ble_gatt_dsc *, void *);
};

std::vector<ble_gatt_dsc> attributes;
std::vector<std::pair<uint16_t, uint16_t>> requestedRanges;
int failAfter = -1;
int ble_gattc_disc_all_dscs(uint16_t connection, uint16_t start, uint16_t end,
                          int (*callback)(uint16_t, const ble_gatt_error *, uint16_t, const ble_gatt_dsc *, void *), void *arg) {
  requestedRanges.emplace_back(start, end);
  ble_gatt_error success{0};
  int delivered = 0;
  for (const auto &attribute : attributes) {
    if (attribute.handle <= start || attribute.handle > end) continue;
    if (delivered == failAfter) {
      ble_gatt_error error{13};
      callback(connection, &error, start, nullptr, arg);
      return 0;
    }
    ++delivered;
    // NimBLE's chr_val_handle is the original start for EVERY result. Find
    // Information returns all attribute kinds in the requested range, including
    // later declarations and values when the caller sets an overbroad end.
    if (callback(connection, &success, start, &attribute, arg)) return 0;
  }
  ble_gatt_error done{BLE_HS_EDONE};
  callback(connection, &done, start, nullptr, arg);
  return 0;
}

#include "ble_descriptors_under_test.inc"

void reset() {
  assert(BLERemoteDescriptor::live.empty());
  requestedRanges.clear();
  failAfter = -1;
  attributes = {
      {3, {0x2902}}, {4, {0x2901}}, {5, {0x2803}}, {6, {0xa001}},
      {7, {0x2902}}, {8, {0x2901}}, {9, {0x2803}}, {10, {0xa002}},
      {11, {0x2902}}, {12, {0x2901}}, {14, {0x2803}}, {15, {0xa003}},
      {16, {0x2902}}, {17, {0x2901}}, {18, {0x2904}},
  };
}

void rangeAndOwnership() {
  reset();
  {
    BLERemoteService service;
    BLERemoteCharacteristic first(service, 1, 2), second(service, 5, 6), third(service, 9, 10), last(service, 14, 15);
    assert(first.retrieveDescriptors());
#if EXPECT_FIXED
    assert(requestedRanges.back() == std::make_pair(uint16_t(2), uint16_t(4)));
    assert(first.m_descriptorMap.size() == 2);
    assert(first.m_descriptorMap.count(std::to_string(0x2803)) == 0);
    assert(second.retrieveDescriptors());
    assert(requestedRanges.back() == std::make_pair(uint16_t(6), uint16_t(8)));
    assert(third.retrieveDescriptors());
    assert(requestedRanges.back() == std::make_pair(uint16_t(10), uint16_t(13)));
    assert(last.retrieveDescriptors());
    assert(requestedRanges.back() == std::make_pair(uint16_t(15), uint16_t(18)));
    assert(first.m_descriptorMap.at(std::to_string(0x2902))->handle == 3);
    assert(second.m_descriptorMap.at(std::to_string(0x2902))->handle == 7);
    assert(third.m_descriptorMap.at(std::to_string(0x2902))->handle == 11);
    assert(last.m_descriptorMap.at(std::to_string(0x2902))->handle == 16);
#else
    assert(requestedRanges.back() == std::make_pair(uint16_t(2), uint16_t(18)));
    assert(first.m_descriptorMap.count(std::to_string(0x2803)) == 1);
#endif
  }
#if EXPECT_FIXED
  assert(BLERemoteDescriptor::live.empty());
#else
  assert(BLERemoteDescriptor::live.size() == 8);
  // Recover deliberately demonstrated baseline leaks before sanitizer shutdown.
  while (!BLERemoteDescriptor::live.empty()) delete *BLERemoteDescriptor::live.begin();
#endif
}

#if EXPECT_FIXED
void emptyRanges() {
  reset();
  {
    BLERemoteService service;
    service.endHandle = 4;
    BLERemoteCharacteristic first(service, 1, 2), last(service, 3, 4);
    assert(first.retrieveDescriptors());
    assert(last.retrieveDescriptors());
    assert(first.m_descriptorsRetrieved && last.m_descriptorsRetrieved);
    assert(requestedRanges.empty());
  }
}

void duplicateUuidsAndRetries() {
  reset();
  attributes = {{3, {0x2902}}, {4, {0x2902}}};
  {
    BLERemoteService service;
    service.endHandle = 4;
    BLERemoteCharacteristic characteristic(service, 1, 2);
    assert(characteristic.retrieveDescriptors());
    assert(characteristic.m_descriptorMap.size() == 1);
    assert(BLERemoteDescriptor::live.size() == 1);
    assert(characteristic.m_descriptorMap.begin()->second->handle == 3);
    for (int attempt = 0; attempt < 20; ++attempt) assert(characteristic.retrieveDescriptors());
    assert(BLERemoteDescriptor::live.size() == 1);
  }
  assert(BLERemoteDescriptor::live.empty());

  reset();
  {
    BLERemoteService service;
    service.endHandle = 4;
    BLERemoteCharacteristic characteristic(service, 1, 2);
    failAfter = 1;
    assert(!characteristic.retrieveDescriptors());
    assert(!characteristic.m_descriptorsRetrieved);
    assert(BLERemoteDescriptor::live.size() == 1);
    failAfter = -1;
    assert(characteristic.retrieveDescriptors());
    assert(characteristic.m_descriptorsRetrieved);
    assert(BLERemoteDescriptor::live.size() == 2);
  }
  assert(BLERemoteDescriptor::live.empty());
}

void filterAndForeignResults() {
  reset();
  {
    BLERemoteService service;
    service.endHandle = 4;
    BLERemoteCharacteristic characteristic(service, 1, 2);
    BLEUUID uuid{{0x2901}};
    assert(characteristic.retrieveDescriptors(&uuid));
    assert(characteristic.m_descriptorMap.size() == 1);
    assert(characteristic.m_descriptorMap.begin()->second->handle == 4);
    BLETaskData data(&characteristic);
    desc_filter_t filter{nullptr, &data};
    ble_gatt_error success{0};
    assert(characteristic.descriptorDiscCB(99, &success, 2, &attributes.front(), &filter) == 0);
    assert(characteristic.descriptorDiscCB(42, &success, 7, &attributes.front(), &filter) == 0);
    assert(BLERemoteDescriptor::live.size() == 1);
  }
  assert(BLERemoteDescriptor::live.empty());
}
#endif

int main() {
  rangeAndOwnership();
#if EXPECT_FIXED
  emptyRanges();
  duplicateUuidsAndRetries();
  filterAndForeignResults();
  for (int cycle = 0; cycle < 50; ++cycle) rangeAndOwnership();
  std::cout << "BLE descriptors: bounds, empty ranges, duplicate UUIDs, retries and 50 cycles passed\n";
#else
  std::cout << "BLE descriptors: original methods scanned downstream attributes and leaked eight objects\n";
#endif
}
