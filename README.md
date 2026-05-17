# ESP32 / P4 Open GoPro Remote

PlatformIO firmware for a GoPro remote that uses the current Open GoPro BLE and Wi-Fi control flow.

The project now has two primary firmware roles:

- `s3_ui`: ESP32-S3 display/touch remote UI. This is the product UI path.
- `radio`: ESP32 / ESP32-S3 BLE, Wi-Fi, GoPro HTTP control, and UDP stream receive/proxy.

The ESP32-P4 is optional worker hardware for experiments such as Wi-Fi/video buffering and decoder capability tests. It is not the UI/display owner.

## What It Does

- Scans for BLE devices advertising GoPro/Open GoPro service names, including `GoPro`, `MISSION`, and `GP`.
- Connects over BLE and reads the camera Wi-Fi AP SSID/password from Open GoPro characteristics.
- Sends the BLE Wi-Fi enable command `03:17:01:01`.
- Joins the camera AP and starts the preview stream with:
  - `http://10.5.5.9:8080/gopro/camera/stream/start?port=8554`
- Listens for the camera's UDP preview stream on ESP32 UDP port `8554`.
- Can proxy received stream packets to another host on the network.
- Connects to the GoPro camera Wi-Fi AP using credentials read over BLE.

## Build Targets

- `esp32dev`: radio firmware for the currently attached ESP32 dev board.
- `esp32s3_radio`: radio firmware for an ESP32-S3 dev board.
- `esp32s3_amoled_ui`: primary touch UI firmware for the ESP32-S3 AMOLED board.
- `ui_esp32dev_sim`: UI-host simulator build. It uses serial text as the display/touch stand-in and talks to the radio firmware over `Serial2`.
- `esp32p4_ui`: optional P4 serial worker/shell build for the DFRobot ESP32-P4 board on `/dev/ttyACM1`.
- `dfrobot_p4_decode_probe`: hardware H.264 decoder capability probe for the DFRobot ESP32-P4 board.

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
pio run -e esp32s3_amoled_ui
pio run -e ui_esp32dev_sim
pio run -e esp32p4_ui
pio run -e dfrobot_p4_decode_probe
```

## S3 UI + Optional P4 Worker Architecture

The S3 board owns the LCD, touch, buttons, battery UI, GoPro menu, and normal user interaction. If the P4 is added, it should be treated as a worker behind the S3 UI.

```text
GoPro <-- BLE/Wi-Fi --> ESP32-S3 UI/radio/display
ESP32-S3 UI <-- SPI/UART framed protocol --> optional ESP32-P4 worker
```

Legacy UART wiring diagram: [docs/p4_s3_uart_wiring.svg](docs/p4_s3_uart_wiring.svg)
Legacy P4 display wiring concept: [docs/p4_watch_display_wiring.svg](docs/p4_watch_display_wiring.svg)
Alternate P4-WiFi + Waveshare S3 display split: [docs/p4_wifi_s3_display_design.md](docs/p4_wifi_s3_display_design.md)
Waveshare S3 wiring diagram: [docs/p4_wifi_s3_display_wiring.svg](docs/p4_wifi_s3_display_wiring.svg)

Default UART pins for the optional DFRobot P4 worker shell:

- S3 `TX` GPIO17 -> DFRobot P4 header `RX / GPIO38`
- S3 `RX` GPIO16 <- DFRobot P4 header `TX / GPIO37`
- Common ground
- Baud: `921600`

Do not use the P4 `GPIO14-19` pins for this link on the DFRobot board; they are reserved for the onboard ESP32-C6 Wi-Fi/BLE SDIO interface. Avoid `GPIO39-45` if the TF card slot is in use.

This is intentionally UART first because it is easy to debug. For production preview data, SPI or SDIO is a better transport. The packet protocol is isolated in `src/common/LinkProtocol.*`, so the physical transport can be moved from UART to SPI without changing GoPro commands.

The S3 UI should own:

- LCD output
- Touch input
- Side buttons and power behavior
- UI/menu rendering
- BLE pairing/wake
- Normal GoPro HTTP controls
- JPEG snapshot preview display

P4 H.264 status: the DFRobot ESP32-P4 probe decodes simple constrained-baseline frames at 80x80, 320x192, 640x368, and 1280x720, then converts them to a 240x320 RGB565 framebuffer. The 640x368 test decoded in about 16 ms and converted in about 10 ms; the 1280x720 test decoded in about 55 ms and converted in about 11 ms. The same probe rejects high-profile H.264 at SPS parsing, so a GoPro stream that is high-profile still needs JPEG snapshot preview, a host-class decoder, or a camera stream mode that can be forced to constrained baseline.

The optional P4 should own only worker tasks that are worth offloading:

- Wi-Fi connection to the GoPro or home network, if that proves better than the S3 path
- UDP preview stream receive/proxy
- JPEG/constrained-baseline H.264 decode experiments
- RGB565 frame tile transfer back to the S3 UI

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

The real LCD/touch path is the ESP32-S3 UI target. The current P4 target is only a serial-rendered worker shell and decoder bring-up environment.

Recommended display paths:

- Lowest-risk P4 EV-board bring-up: Espressif's supported MIPI-DSI LCD adapter. It is not watch-sized, but the BSP path is known.
- Watch-style prototype: 1.43-inch round 466x466 AMOLED with CO5300-class QSPI display interface and CST820-class I2C capacitive touch. This is close to a smartwatch face, but it will need a custom display/touch driver.

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
