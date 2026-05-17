#include <Arduino.h>

#include "LinkProtocol.h"

#ifndef GOPRO_UI_LINK_BAUD
#define GOPRO_UI_LINK_BAUD 921600
#endif

#ifndef GOPRO_UI_LINK_RX_PIN
#define GOPRO_UI_LINK_RX_PIN 16
#endif

#ifndef GOPRO_UI_LINK_TX_PIN
#define GOPRO_UI_LINK_TX_PIN 17
#endif

namespace {

RemoteLink::Parser g_parser;
uint16_t g_sequence = 1;
uint8_t g_selected = 0;
uint32_t g_lastRenderMs = 0;
uint32_t g_streamChunks = 0;
uint32_t g_streamBytes = 0;
String g_status = "{}";
String g_lastJson = "";
String g_lastMessage = "booting";
String g_serialLine;

struct MenuItem {
  const char *label;
  RemoteLink::MsgType type;
  const char *payload;
};

MenuItem g_menu[] = {
    {"Pair BLE", RemoteLink::MsgType::Pair, ""},
    {"Wake Camera", RemoteLink::MsgType::Wake, ""},
    {"Join GoPro AP", RemoteLink::MsgType::ConnectGoProAp, ""},
    {"Join Home WiFi", RemoteLink::MsgType::ConnectLocalWifi, ""},
    {"Start Preview", RemoteLink::MsgType::StartStream, ""},
    {"Stop Preview", RemoteLink::MsgType::StopStream, ""},
    {"Shutter On", RemoteLink::MsgType::Shutter, "on"},
    {"Shutter Off", RemoteLink::MsgType::Shutter, "off"},
    {"Camera State", RemoteLink::MsgType::GetCameraState, ""},
    {"Preset List", RemoteLink::MsgType::GetPresets, ""},
    {"Keep Alive", RemoteLink::MsgType::KeepAlive, ""},
};

constexpr uint8_t kMenuCount = sizeof(g_menu) / sizeof(g_menu[0]);

String packetText(const RemoteLink::Packet &packet) {
  String text;
  text.reserve(packet.length);
  for (uint16_t i = 0; i < packet.length; ++i) {
    text += static_cast<char>(packet.payload[i]);
  }
  return text;
}

void sendCommand(RemoteLink::MsgType type, const String &payload = "") {
  RemoteLink::sendText(Serial2, type, payload, g_sequence++);
}

void render() {
  Serial.println();
  Serial.println(F("=== GoPro Remote P4 Worker Shell ==="));
  Serial.println(F("Display/touch owner: ESP32-S3. This P4 build is a serial worker/simulator."));
  Serial.print(F("Radio status: "));
  Serial.println(g_status);
  Serial.print(F("Preview chunks: "));
  Serial.print(g_streamChunks);
  Serial.print(F(" bytes: "));
  Serial.println(g_streamBytes);
  Serial.print(F("Last message: "));
  Serial.println(g_lastMessage);
  Serial.println(F("Menu:"));
  for (uint8_t i = 0; i < kMenuCount; ++i) {
    Serial.print(i == g_selected ? F("> ") : F("  "));
    Serial.println(g_menu[i].label);
  }
  Serial.println(F("Controls: u/d/s, number, pair, wake, stream, stop, state, presets"));
  Serial.println(F("Extra: cameraap SSID PASS | ip 10.5.5.9 | preset ID | raw /path"));
}

void handlePacket(const RemoteLink::Packet &packet) {
  switch (packet.type) {
    case RemoteLink::MsgType::Ack:
      g_lastMessage = "ack: " + packetText(packet);
      break;
    case RemoteLink::MsgType::Error:
      g_lastMessage = "error: " + packetText(packet);
      break;
    case RemoteLink::MsgType::Log:
      g_lastMessage = "log: " + packetText(packet);
      break;
    case RemoteLink::MsgType::Status:
      g_status = packetText(packet);
      break;
    case RemoteLink::MsgType::CameraJson:
      g_lastJson = packetText(packet);
      g_lastMessage = "camera json received";
      Serial.println();
      Serial.println(F("--- Camera JSON ---"));
      Serial.println(g_lastJson);
      break;
    case RemoteLink::MsgType::StreamChunk:
      g_streamChunks++;
      g_streamBytes += packet.length;
      break;
    default:
      g_lastMessage = "unhandled packet";
      break;
  }
}

void pollLink() {
  RemoteLink::Packet packet;
  while (Serial2.available() > 0) {
    if (g_parser.push(static_cast<uint8_t>(Serial2.read()), packet)) {
      handlePacket(packet);
    }
  }
}

void selectMenu() {
  MenuItem &item = g_menu[g_selected];
  sendCommand(item.type, item.payload);
  g_lastMessage = String("sent: ") + item.label;
}

void handleInput(String line) {
  line.trim();
  if (line.isEmpty()) {
    return;
  }

  if (line == "u") {
    g_selected = (g_selected == 0) ? kMenuCount - 1 : g_selected - 1;
  } else if (line == "d") {
    g_selected = (g_selected + 1) % kMenuCount;
  } else if (line == "s") {
    selectMenu();
  } else if (line.length() == 1 && isDigit(line[0])) {
    uint8_t index = static_cast<uint8_t>(line.toInt());
    if (index < kMenuCount) {
      g_selected = index;
      selectMenu();
    }
  } else if (line == "pair") {
    sendCommand(RemoteLink::MsgType::Pair);
  } else if (line == "wake") {
    sendCommand(RemoteLink::MsgType::Wake);
  } else if (line == "stream") {
    sendCommand(RemoteLink::MsgType::StartStream);
  } else if (line == "stop") {
    sendCommand(RemoteLink::MsgType::StopStream);
  } else if (line == "state") {
    sendCommand(RemoteLink::MsgType::GetCameraState);
  } else if (line == "presets") {
    sendCommand(RemoteLink::MsgType::GetPresets);
  } else if (line.startsWith("cameraap ")) {
    int space = line.indexOf(' ', 9);
    if (space > 0) {
      sendCommand(RemoteLink::MsgType::SetCameraAp, line.substring(9, space) + "\n" + line.substring(space + 1));
    }
  } else if (line.startsWith("ip ")) {
    sendCommand(RemoteLink::MsgType::SetCameraIp, line.substring(3));
  } else if (line.startsWith("preset ")) {
    sendCommand(RemoteLink::MsgType::LoadPreset, line.substring(7));
  } else if (line.startsWith("raw ")) {
    sendCommand(RemoteLink::MsgType::RawHttpGet, line.substring(4));
  } else {
    g_lastMessage = "unknown input";
  }

  render();
}

void pollSerialInput() {
  while (Serial.available() > 0) {
    char c = static_cast<char>(Serial.read());
    if (c == '\r') {
      continue;
    }
    if (c == '\n') {
      handleInput(g_serialLine);
      g_serialLine = "";
    } else if (g_serialLine.length() < 160) {
      g_serialLine += c;
    }
  }
}

}  // namespace

void setup() {
  Serial.begin(115200);
  Serial2.begin(GOPRO_UI_LINK_BAUD, SERIAL_8N1, GOPRO_UI_LINK_RX_PIN, GOPRO_UI_LINK_TX_PIN);
  delay(500);
  Serial.println();
  render();
  sendCommand(RemoteLink::MsgType::Ping);
}

void loop() {
  pollLink();
  pollSerialInput();

  uint32_t now = millis();
  if (now - g_lastRenderMs > 3000) {
    g_lastRenderMs = now;
    sendCommand(RemoteLink::MsgType::Ping);
    render();
  }
  delay(2);
}
