# ESP32 / P4 Open GoPro Remote

PlatformIO firmware for a GoPro remote that uses the current Open GoPro BLE and Wi-Fi control flow.

The project now has two firmware roles:

- `radio`: ESP32 / ESP32-S3 radio coprocessor for BLE, Wi-Fi, GoPro HTTP control, and UDP stream receive/proxy.
- `ui`: P4-style display/touch host. The current buildable target is `ui_esp32dev_sim`, a serial UI simulator, because this PlatformIO install does not yet include ESP32-P4 boards and the exact LCD/touch controller is not specified.

## What It Does

- Scans for BLE devices advertising GoPro/Open GoPro service names, including `GoPro`, `MISSION`, and `GP`.
- Connects over BLE and reads the camera Wi-Fi AP SSID/password from Open GoPro characteristics.
- Sends the BLE Wi-Fi enable command `03:17:01:01`.
- Joins the camera AP and starts the preview stream with:
  - `http://10.5.5.9:8080/gopro/camera/stream/start?port=8554`
- Listens for the camera's UDP preview stream on ESP32 UDP port `8554`.
- Can proxy received stream packets to another host on the network.
- Can connect to the local/home Wi-Fi configured in `platformio.ini` as `razor`.

## Build Targets

- `esp32dev`: radio firmware for the currently attached ESP32 dev board.
- `esp32s3_radio`: radio firmware for an ESP32-S3 dev board.
- `ui_esp32dev_sim`: UI-host simulator build. It uses serial text as the display/touch stand-in and talks to the radio firmware over `Serial2`.

Build everything:

```sh
pio run
```

Install / verify ESP32-P4 Arduino support through the community PlatformIO fork:

```sh
scripts/install_pioarduino_p4.sh
```

Build one environment:

```sh
pio run -e esp32s3_radio
pio run -e ui_esp32dev_sim
```

## P4 + S3 Architecture

Recommended wiring is a UART link to start:

```text
GoPro <-- BLE/Wi-Fi --> ESP32-S3 radio <-- UART framed protocol --> ESP32-P4 UI/display
```

Wiring diagram: [docs/p4_s3_uart_wiring.svg](docs/p4_s3_uart_wiring.svg)

Default UART pins:

- Radio `TX` GPIO17 -> UI `RX` GPIO16
- Radio `RX` GPIO16 <- UI `TX` GPIO17
- Common ground
- Baud: `921600`

This is intentionally UART first because it is easy to debug. For production preview data, SPI or SDIO is a better transport. The packet protocol is isolated in `src/common/LinkProtocol.*`, so the physical transport can be moved from UART to SPI without changing GoPro commands.

The P4 should own:

- LCD output
- Touch input
- UI/menu rendering
- Any low-rate preview/decode/display work

The S3 should own:

- BLE pairing/wake
- Wi-Fi connection to the GoPro or home network
- GoPro HTTP commands
- UDP preview stream receive/proxy

## Serial Commands

Open the serial monitor at `115200`.

- `help` - show commands
- `status` - print current BLE/Wi-Fi/stream state
- `scan` - scan for GoPro BLE advertisements
- `connect` - connect to the first matching BLE camera
- `pair` - finish BLE pairing while the camera is in Bluetooth pairing mode
- `wake` - BLE connect, read camera AP credentials, enable camera Wi-Fi
- `goproap` - join the camera AP read over BLE
- `cameraap LEFTCAM password` - manually set camera AP credentials for renamed cameras such as `LEFTCAM`, `RIGHTCAM`, or `MIDCAM`
- `localwifi` - join the configured home/infrastructure Wi-Fi
- `ip 10.5.5.9` - set the camera HTTP IP
- `stream` - start GoPro preview stream and listen on UDP/8554
- `stop` - stop preview stream
- `shutter on` / `shutter off` - start or stop recording over HTTP
- `proxy 192.168.1.50 8554` - forward received preview UDP packets to another machine
- `autostart` - run `wake`, `goproap`, and `stream`

## UI Host Simulator

The UI simulator presents a text menu over USB serial and sends framed commands to the radio over `Serial2`.

Controls:

- `u` / `d` - move selection
- `s` - select
- `pair`, `wake`, `stream`, `stop`, `state`, `presets`
- `cameraap LEFTCAM password`
- `ip 10.5.5.9`
- `preset ID`
- `raw /gopro/camera/state`

The simulator receives:

- ACK / error / log messages
- radio status JSON
- camera JSON responses
- preview stream packet chunks and byte counters

## LCD / Touch Driver Slot

The current UI target is a serial simulator. To turn it into the real P4 firmware, replace the serial rendering/input in `src/ui/main.cpp` with the actual P4 LCD/touch backend once the panel is known.

Needed hardware details:

- LCD controller/model
- resolution
- bus type: RGB, MIPI-DSI, SPI, or parallel
- touch controller/model
- pin map
- whether the board has PSRAM and how much

## Physical Controls

The ESP32 `EN` button is reset-only, so firmware cannot read a long press on it. The built-in `BOOT` button is usually GPIO0 and is used as the default remote button after the board has booted.

- Short BOOT press: start/stop preview stream
- About 1 second BOOT press: wake camera, join camera AP, start stream
- About 3 seconds BOOT press: finish BLE pairing

To pair, put the GoPro into its Bluetooth pairing screen, then hold BOOT for about 3 seconds or send `pair` over serial. Do not hold BOOT while resetting/powering the ESP32, because GPIO0 held low at reset enters the ESP32 bootloader.

## Notes

`GOPRO_AUTO_START=1` is enabled in `platformio.ini`, so the ESP32 tries to wake/connect/start streaming on boot. Disable it in `platformio.ini` if you want purely manual serial control.

GoPro MISSION 1 was announced in April 2026. GoPro's public Open GoPro compatibility page had not yet listed Mission 1 when this firmware was created, so this targets the current Open GoPro BLE/Wi-Fi contract used by newer supported GoPros and scans for `MISSION` names as well.
