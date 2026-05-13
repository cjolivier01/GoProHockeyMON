#pragma once

#include <Arduino.h>

namespace RemoteLink {

constexpr uint8_t kSof0 = 0xA5;
constexpr uint8_t kSof1 = 0x5A;
constexpr uint8_t kVersion = 1;
constexpr size_t kMaxPayload = 1024;

enum class MsgType : uint8_t {
  Ping = 0x01,
  Ack = 0x02,
  Error = 0x03,
  Log = 0x04,
  Status = 0x05,
  StreamChunk = 0x06,
  CameraJson = 0x07,

  Pair = 0x20,
  Wake = 0x21,
  ConnectGoProAp = 0x22,
  ConnectLocalWifi = 0x23,
  StartStream = 0x24,
  StopStream = 0x25,
  Shutter = 0x26,
  SetCameraAp = 0x27,
  SetCameraIp = 0x28,
  Proxy = 0x29,
  GetCameraState = 0x2A,
  GetPresets = 0x2B,
  LoadPreset = 0x2C,
  KeepAlive = 0x2D,
  RawHttpGet = 0x2E,
};

struct Packet {
  MsgType type = MsgType::Ping;
  uint16_t sequence = 0;
  uint16_t length = 0;
  uint8_t payload[kMaxPayload] = {};
};

uint16_t crc16Ccitt(const uint8_t *data, size_t length);
bool sendPacket(Stream &stream, MsgType type, const uint8_t *payload, uint16_t length, uint16_t sequence);
bool sendText(Stream &stream, MsgType type, const String &text, uint16_t sequence);

class Parser {
 public:
  bool push(uint8_t byte, Packet &packet);
  void reset();

 private:
  enum class State : uint8_t {
    Sof0,
    Sof1,
    Version,
    Type,
    Seq0,
    Seq1,
    Len0,
    Len1,
    Payload,
    Crc0,
    Crc1,
  };

  State state_ = State::Sof0;
  Packet packet_;
  uint16_t expectedCrc_ = 0;
  uint16_t payloadIndex_ = 0;
  uint8_t crcBuffer_[6] = {};
};

}  // namespace RemoteLink
