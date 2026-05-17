# ESP32-P4 WiFi Worker + Waveshare ESP32-S3-Touch-LCD-2.8 Display Design

This design targets the Waveshare `ESP32-S3-Touch-LCD-2.8` as the user-facing display/touch controller instead of the earlier 368x448 AMOLED board.

```text
GoPro <-- BLE wake/pair --> Waveshare ESP32-S3-Touch-LCD-2.8
GoPro <-- WiFi/HTTP/UDP --> ESP32-P4 WiFi/video worker
ESP32-P4 <-- SPI frame/touch link --> Waveshare ESP32-S3-Touch-LCD-2.8
```

The S3 board owns the 240x320 ST7789 LCD, CST328 capacitive touch, battery ADC, power key, and local UI. The P4 owns the expensive video path: GoPro WiFi, HTTP commands, UDP stream receive, supported preview decode, scaling, and RGB565 conversion.

Hardware source references:

- Waveshare wiki: <https://www.waveshare.com/wiki/ESP32-S3-Touch-LCD-2.8>
- Waveshare schematic: <https://files.waveshare.com/wiki/ESP32-S3-Touch-LCD-2.8/ESP32-S3-Touch-LCD-2.8.pdf>
- Waveshare demo package: <https://files.waveshare.com/wiki/ESP32-S3-Touch-LCD-2.8/ESP32-S3-Touch-LCD-2.8-Demo.zip>
- DFRobot P4 wiki: <https://wiki.dfrobot.com/dfr1172/>

## Board Pinout Summary

### LCD And Touch

| Function | GPIO | Notes |
| --- | ---: | --- |
| LCD controller | ST7789 | 240x320 SPI TFT |
| LCD MOSI | 45 | Dedicated LCD SPI write data |
| LCD SCLK | 40 | Dedicated LCD SPI clock |
| LCD CS | 42 | Dedicated LCD chip select |
| LCD DC | 41 | Dedicated LCD data/command |
| LCD RST | 39 | Dedicated LCD reset |
| LCD backlight PWM | 5 | Active high |
| Touch controller | CST328 | I2C address `0x1A` |
| Touch SDA | 1 | Dedicated touch I2C |
| Touch SCL | 3 | Dedicated touch I2C |
| Touch INT | 4 | Touch interrupt |
| Touch RST | 2 | Touch reset |

### Power, Battery, And Onboard Devices

| Function | GPIO / Address | Notes |
| --- | ---: | --- |
| Power key input | 6 | Active low in Waveshare demo |
| Power hold/control | 7 | Must be driven high to keep battery-powered board on |
| Battery ADC | 8 | ADC1 channel 7 |
| Shared onboard I2C SCL | 10 | QMI8658 / PCF85063 / battery charger path |
| Shared onboard I2C SDA | 11 | QMI8658 / PCF85063 / battery charger path |
| Onboard I2C addresses | `0x51`, `0x6B`, `0x7E` | Do not treat GPIO10/11 as spare GPIO |
| QMI8658 INT1 | 13 | IMU interrupt |
| QMI8658 INT2 | 12 | IMU interrupt |
| RTC INT | 9 | PCF85063 interrupt |
| Speaker I2S LRCK | 38 | PCM5101 |
| Speaker I2S DIN | 47 | PCM5101 |
| Speaker I2S BCK | 48 | PCM5101 |

### TF Card

| Function | GPIO | Notes |
| --- | ---: | --- |
| SD MISO | 16 | TF card SPI |
| SD MOSI | 17 | TF card SPI |
| SD SCLK | 14 | TF card SPI |
| SD CS | 21 | TF card SPI |

### Exposed Header Pins For P4 Link

The useful exposed pins for the P4 link are:

- `GPIO15`
- `GPIO18`
- `GPIO43` / UART TXD
- `GPIO44` / UART RXD
- `GND`
- Optional 3.3 V logic reference only; do not back-power either board from it.

Avoid using `GPIO19/20` from the header if native USB is used. Avoid using `GPIO10/11` as arbitrary link pins because they are the onboard shared I2C bus.

## Responsibilities

### Waveshare ESP32-S3-Touch-LCD-2.8

- Owns the ST7789 240x320 LCD and CST328 touch controller.
- Draws status chrome, menus, overlays, and received preview frames.
- Sends touch events, power-key events, and UI commands to the P4.
- Handles GoPro BLE wake/pair and reads GoPro AP credentials if the P4 board does not expose a known-good BLE path.
- Sends the discovered GoPro SSID/password to the P4 over the private inter-board link.
- Controls LCD backlight, battery gauge, and power-hold behavior.

### ESP32-P4 WiFi/Video Worker

- Joins the GoPro AP using credentials from the S3.
- Calls Open GoPro HTTP endpoints for camera state, presets, settings, shutter, and stream start/stop.
- Receives the GoPro UDP MPEG-TS stream on port 8554.
- Decodes only supported preview formats. On the tested DFRobot ESP32-P4 board, Espressif tinyH264 decodes simple constrained-baseline streams but rejects high-profile H.264.
- Scales frames down to the S3 screen or preview region.
- Converts frames to RGB565.
- Sends frame tiles to the S3 over SPI DMA.
- Sends camera state JSON and stream status back to the S3.

## P4 Decode Test Result

The DFRobot FireBeetle 2 ESP32-P4 AI Vision board on `/dev/ttyACM1` was tested with `dfrobot_p4_decode_probe`.

- Board/toolchain that boots: pioarduino `54.03.21-2`, board id `esp32-p4-evboard`.
- Board/toolchain that boot-looped on this rev v1.3 P4: latest pioarduino with `esp32-p4_r3-evboard`.
- Decoded: constrained-baseline 80x80, 320x192, 640x368, and 1280x720 synthetic H.264 frames.
- Converted decoded I420/YUV420 frames to a 240x320 RGB565 framebuffer with aspect-fit letterboxing.
- 640x368 constrained-baseline decode time: about 16 ms for one simple I-frame.
- 640x368 to 240x320 RGB565 conversion time: about 10 ms.
- 1280x720 constrained-baseline decode time: about 55 ms for one simple I-frame.
- 1280x720 to 240x320 RGB565 conversion time: about 11 ms.
- RGB565 tile plan used by the probe: 16 rows per tile, 20 tiles, 7,680 byte max tile payload, 153,600 bytes per full 240x320 frame.
- Rejected: high-profile H.264, with `profile_idc is error` during SPS parsing.

Design consequence: do not plan on this P4 decoding the normal GoPro high-profile RTSP/UDP stream unless the camera can be forced into constrained-baseline output. For the current remote, JPEG snapshot preview remains the reliable low-rate display path.

## Inter-Board Link

Use SPI for frame data and commands. UART is useful for bring-up/debug, but it should not carry preview frames.

Recommended SPI direction is P4 master, S3 slave:

- P4 controls the clock rate and pushes frame tiles when they are ready.
- S3 receives DMA chunks and flushes them to the ST7789 LCD.
- Touch/button events flow back to P4 over MISO during short command/status polls.
- No extra IRQ line is required for the first revision because this Waveshare board exposes only a small set of free pins.

## Suggested Wiring

This table uses the header labels from the DFRobot FireBeetle 2 ESP32-P4 AI Vision board. The S3 side is unchanged.

| Signal | ESP32-P4 WiFi worker | Waveshare ESP32-S3-Touch-LCD-2.8 | Notes |
| --- | --- | --- | --- |
| GND | GND | GND | Required common ground. |
| 3V3 logic reference | 3V3 sense/reference | 3V3 header | Optional reference only; do not back-power either board. |
| SPI SCLK | DFRobot P4 `SCL / GPIO8` | S3 GPIO18 | Repurpose the P4 header pin as GPIO/SPI clock. |
| SPI MOSI | DFRobot P4 `TX / GPIO37` | S3 GPIO15 | P4-to-S3 frame/command data. |
| SPI MISO | DFRobot P4 `RX / GPIO38` | S3 GPIO43 | S3-to-P4 touch/button/status data. Conflicts with S3 UART header TXD. |
| SPI CS | DFRobot P4 `SDA / GPIO7` | S3 GPIO44 | Active-low transaction select. Conflicts with S3 UART header RXD. |

Optional UART bring-up link:

| Signal | DFRobot ESP32-P4 | ESP32-S3 side | Notes |
| --- | --- | --- | --- |
| P4 RX | `RX / GPIO38` | S3 TX GPIO17 | Cross TX to RX. |
| P4 TX | `TX / GPIO37` | S3 RX GPIO16 | Cross TX to RX. |
| GND | GND | GND | Required common ground. |

DFRobot P4 pins intentionally not used for the inter-board link:

- Onboard ESP32-C6 Wi-Fi/BLE SDIO: GPIO14, GPIO15, GPIO16, GPIO17, GPIO18, GPIO19, plus EN GPIO54 and WAKEUP GPIO6.
- TF card slot: GPIO39, GPIO40, GPIO41, GPIO42, GPIO43, GPIO44, GPIO45.
- PDM microphone: GPIO12 clock, GPIO9 data.
- Onboard LED and BOOT: GPIO3, GPIO35.

Default S3 firmware defines:

```cpp
#define GOPRO_P4_LINK_SCLK 18
#define GOPRO_P4_LINK_MOSI 15
#define GOPRO_P4_LINK_MISO 43
#define GOPRO_P4_LINK_CS   44
```

Pins intentionally not used for the P4 link:

- LCD: GPIO5, GPIO39, GPIO40, GPIO41, GPIO42, GPIO45
- Touch: GPIO1, GPIO2, GPIO3, GPIO4
- Power/battery: GPIO6, GPIO7, GPIO8
- Onboard I2C: GPIO10, GPIO11
- IMU/RTC interrupts: GPIO9, GPIO12, GPIO13
- TF card: GPIO14, GPIO16, GPIO17, GPIO21
- Audio: GPIO38, GPIO47, GPIO48
- Native USB: GPIO19, GPIO20

## Bandwidth Budget

The Waveshare S3 screen is 240x320.

- Full RGB565 frame: `240 * 320 * 2 = 153,600 bytes`
- Full frame at 1 fps: about `1.23 Mbit/s` before protocol overhead
- Full frame at 5 fps: about `6.14 Mbit/s` before protocol overhead
- Preview area below a 28 px top bar: `240 * 292 * 2 = 140,160 bytes`

Recommended SPI clock:

- Bring-up: 5-10 MHz, small tiles, CRC enabled
- Normal preview: 20 MHz SPI DMA
- Target frame rate: 1-5 fps for full-screen remote preview

UART at `921600` baud only moves about 90 KB/s in ideal conditions, so it is too slow for responsive full-frame preview. It is fine for logs, commands, and camera state JSON.

## Frame Protocol

Use the existing framed protocol style from `src/common/LinkProtocol.*`, but add larger SPI-oriented message types:

- `FrameBegin`: frame id, width, height, pixel format, dirty rectangle count
- `FrameTile`: frame id, x, y, width, height, RGB565 payload, CRC32
- `FrameEnd`: frame id, total bytes, presentation timestamp
- `TouchEvent`: x, y, press/release, gesture id
- `ButtonEvent`: power key short/long press, BOOT if used
- `CameraState`: compact JSON or binary setting/status update
- `Command`: shutter, preset load, settings change, stream start/stop

Use full-width horizontal bands for video frames because they map cleanly to the ST7789 flush path.

## Preview Flow

1. S3 boots, asserts `PWR_Control_PIN` high, initializes LCD/touch/battery.
2. User taps Pair or Connect.
3. S3 wakes/pairs GoPro over BLE and reads GoPro AP SSID/password.
4. S3 sends credentials to P4 over SPI command transaction.
5. P4 joins the GoPro AP.
6. P4 calls the normal preview endpoint, or a webcam endpoint only if it can be configured to constrained-baseline H.264.
7. P4 receives UDP MPEG-TS on port 8554.
8. P4 decodes JPEG/constrained-baseline frames, or forwards unsupported high-profile stream status to the UI.
9. P4 sends RGB565 frame tiles to S3.
10. S3 draws the frame below the persistent top status bar.

## Why This Split Makes Sense

This split still helps with WiFi and buffering, but the P4 is not a magic high-profile H.264 decoder in the tested Arduino/tinyH264 path. The S3 and P4 both reject high-profile H.264 with the available tinyH264 decoder. Moving WiFi to the P4 can still reduce load on the display S3, but live video should use JPEG snapshots, constrained-baseline H.264 if available, or an external/host-class decoder.

The Waveshare 240x320 display also reduces inter-board bandwidth by more than half compared with the previous 368x448 AMOLED board.

## Firmware Work Items

1. Add a Waveshare-specific display backend for ST7789 + CST328.
2. Add a Waveshare board config with the pin map above.
3. Replace the old AMOLED 368x448 layout constants with responsive 240x320 layout constants.
4. Add S3 SPI-slave transport using GPIO18/15/43/44.
5. Add P4 WiFi worker firmware that owns Open GoPro HTTP and UDP stream receive.
6. Add P4 JPEG/constrained-baseline H.264 decode and RGB565 scaling path.
7. Keep BLE pairing on S3 unless the P4 board also exposes BLE and its BLE stack proves reliable.
8. Add diagnostics showing SPI throughput, dropped tiles, frame id, decode fps, and GoPro stream bitrate.

## Minimum Bring-Up Milestones

1. S3 boots on battery/USB, holds power via GPIO7, and displays a 240x320 test UI.
2. CST328 touch reports coordinates correctly.
3. P4 sends a synthetic RGB565 test pattern to S3 over SPI.
4. S3 sends touch events back to P4 over MISO.
5. P4 joins GoPro AP and fetches `/gopro/camera/state`.
6. P4 starts webcam 720 stream and logs UDP bitrate.
7. P4 decodes one supported frame per second and sends it to S3.
8. S3 overlays battery, WiFi, BLE, recording, and touch controls on top of received preview frames.
