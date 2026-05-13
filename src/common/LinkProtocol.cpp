#include "LinkProtocol.h"

namespace RemoteLink {

uint16_t crc16Ccitt(const uint8_t *data, size_t length) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < length; ++i) {
    crc ^= static_cast<uint16_t>(data[i]) << 8;
    for (uint8_t bit = 0; bit < 8; ++bit) {
      crc = (crc & 0x8000) ? static_cast<uint16_t>((crc << 1) ^ 0x1021) : static_cast<uint16_t>(crc << 1);
    }
  }
  return crc;
}

bool sendPacket(Stream &stream, MsgType type, const uint8_t *payload, uint16_t length, uint16_t sequence) {
  if (length > kMaxPayload || (length > 0 && payload == nullptr)) {
    return false;
  }

  uint8_t header[] = {
      kSof0,
      kSof1,
      kVersion,
      static_cast<uint8_t>(type),
      static_cast<uint8_t>(sequence >> 8),
      static_cast<uint8_t>(sequence & 0xFF),
      static_cast<uint8_t>(length >> 8),
      static_cast<uint8_t>(length & 0xFF),
  };

  uint16_t crc = crc16Ccitt(&header[2], sizeof(header) - 2);
  crc = crc16Ccitt(payload, length) ^ crc;

  stream.write(header, sizeof(header));
  if (length > 0) {
    stream.write(payload, length);
  }
  stream.write(static_cast<uint8_t>(crc >> 8));
  stream.write(static_cast<uint8_t>(crc & 0xFF));
  return true;
}

bool sendText(Stream &stream, MsgType type, const String &text, uint16_t sequence) {
  return sendPacket(stream, type, reinterpret_cast<const uint8_t *>(text.c_str()), text.length(), sequence);
}

void Parser::reset() {
  state_ = State::Sof0;
  packet_ = Packet{};
  expectedCrc_ = 0;
  payloadIndex_ = 0;
}

bool Parser::push(uint8_t byte, Packet &packet) {
  switch (state_) {
    case State::Sof0:
      if (byte == kSof0) {
        state_ = State::Sof1;
      }
      break;
    case State::Sof1:
      state_ = (byte == kSof1) ? State::Version : State::Sof0;
      break;
    case State::Version:
      if (byte != kVersion) {
        reset();
        break;
      }
      crcBuffer_[0] = byte;
      state_ = State::Type;
      break;
    case State::Type:
      packet_.type = static_cast<MsgType>(byte);
      crcBuffer_[1] = byte;
      state_ = State::Seq0;
      break;
    case State::Seq0:
      packet_.sequence = static_cast<uint16_t>(byte) << 8;
      crcBuffer_[2] = byte;
      state_ = State::Seq1;
      break;
    case State::Seq1:
      packet_.sequence |= byte;
      crcBuffer_[3] = byte;
      state_ = State::Len0;
      break;
    case State::Len0:
      packet_.length = static_cast<uint16_t>(byte) << 8;
      crcBuffer_[4] = byte;
      state_ = State::Len1;
      break;
    case State::Len1:
      packet_.length |= byte;
      crcBuffer_[5] = byte;
      if (packet_.length > kMaxPayload) {
        reset();
      } else {
        payloadIndex_ = 0;
        state_ = packet_.length == 0 ? State::Crc0 : State::Payload;
      }
      break;
    case State::Payload:
      packet_.payload[payloadIndex_++] = byte;
      if (payloadIndex_ >= packet_.length) {
        state_ = State::Crc0;
      }
      break;
    case State::Crc0:
      expectedCrc_ = static_cast<uint16_t>(byte) << 8;
      state_ = State::Crc1;
      break;
    case State::Crc1: {
      expectedCrc_ |= byte;
      uint16_t crc = crc16Ccitt(crcBuffer_, sizeof(crcBuffer_));
      crc = crc16Ccitt(packet_.payload, packet_.length) ^ crc;
      if (crc == expectedCrc_) {
        packet = packet_;
        reset();
        return true;
      }
      reset();
      break;
    }
  }
  return false;
}

}  // namespace RemoteLink
