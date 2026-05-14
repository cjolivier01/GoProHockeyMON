# GoPro Remote User Manual

This manual covers the current single-device ESP32-S3 AMOLED remote firmware.

The remote uses Bluetooth Low Energy first. After pairing, it reads the GoPro camera Wi-Fi SSID and password over BLE, enables the camera Wi-Fi AP, then connects the ESP32-S3 to that GoPro AP for HTTP camera control and low-rate JPEG preview.

The screenshots below are generated UI reference images based on the current LVGL screen layout and app states. They are not photos from the physical AMOLED panel.

## Hardware

- ESP32-S3 Touch AMOLED 1.8 board
- GoPro with Open GoPro BLE/Wi-Fi support
- USB cable for flashing/debugging
- Battery connected to the board PMU for portable use

## Flashing The Remote

From the project root:

```sh
pio run -e esp32s3_amoled_ui -t upload --upload-port /dev/ttyACM0
```

Open a serial monitor if you want boot diagnostics:

```sh
pio device monitor -e esp32s3_amoled_ui
```

Normal boot output ends with:

```text
GoPro AMOLED UI boot
AXP2101 PWR button enabled
AMOLED UI ready
```

## Main Screen

The default screen is now the capture/preview screen, matching the basic GoPro rear-screen flow. Swipe left or right to move between pages. The battery and Wi-Fi cluster stays visible at the top on every page.

![Home idle screen](images/ui/01-home-idle.svg)

Top-right indicators:

- Battery bar and percent: read from the AXP2101 PMU.
- `USB`: shown if USB power is present but no battery percentage is available.
- `WIFI --`: Wi-Fi disconnected.
- `WIFI ..`: Wi-Fi connecting.
- `WIFI ON`: connected to the GoPro AP.

## Touch Controls

- `Connect`: scan/connect BLE, read GoPro Wi-Fi credentials, enable GoPro AP, and join it.
- `Pair`: finish BLE pairing while the GoPro is in pairing mode.
- `WiFi`: read BLE Wi-Fi credentials if needed, enable the GoPro AP, and connect Wi-Fi.
- `REC`: start or stop GoPro video recording over HTTP.

Swipe pages:

- Capture: preview, remaining time, record state, mode, aspect, resolution, FPS, lens, camera connection, and REC.
- Modes: Video, Photo, and TimeWarp mode cards.
- Capture Settings: aspect ratio, resolution, frame rate, digital lens, HyperSmooth, scheduled capture, duration, and HindSight.
- Pro Controls: bit depth, bit rate, shutter, EV comp, white balance, ISO, sharpness, color, audio, RAW audio, and wind.
- Dashboard: connect, pair, camera state, and physical button reference.

## Side Buttons

The board has two side buttons:

- BOOT short press: start/stop recording.
- BOOT long press: enter GoPro BLE pairing flow.
- PWR short press: turn AMOLED display off/on.
- PWR long press: enter low-power shutdown through the AXP2101 PMU.

Do not hold BOOT while resetting or powering the ESP32-S3. Holding BOOT at reset can put the ESP32 into flashing mode.

## Pairing A GoPro

1. On the GoPro, open the Bluetooth pairing screen.
2. On the remote, tap `Pair`, or long-press BOOT.
3. The remote scans for GoPro BLE devices and sends the Open GoPro pairing finish command.
4. After pairing, use `Connect` or `WiFi` to connect to the GoPro camera AP.

![Pairing screen](images/ui/02-pairing.svg)

During BLE scanning, the remote searches for nearby devices matching GoPro/Open GoPro service names, including `GoPro`, `MISSION`, and `GP`.

![BLE scan screen](images/ui/03-ble-scan.svg)

After the BLE connection succeeds, the remote reads the GoPro AP SSID and password from the camera over BLE.

![BLE credentials screen](images/ui/04-ble-credentials.svg)

## Connecting To GoPro Wi-Fi

Tap `Connect` or `WiFi`.

The remote does the full Wi-Fi setup automatically:

1. Connects to the GoPro over BLE.
2. Reads the GoPro AP SSID and password from BLE.
3. Enables the GoPro Wi-Fi AP over BLE.
4. Connects ESP32-S3 Wi-Fi to the GoPro AP.
5. Uses `http://10.5.5.9:8080` for GoPro HTTP commands and JPEG preview.

![Wi-Fi joining screen](images/ui/05-wifi-joining.svg)

When connected, the top-right Wi-Fi indicator turns green and the `WiFi:` line shows the ESP32 address on the GoPro AP.

![Wi-Fi connected preview screen](images/ui/06-wifi-preview.svg)

## GoPro-Style Settings

The UI is organized after the GoPro rear screen:

- Default capture page first.
- Swipe left/right to change pages.
- Capture overlay shows mode and capture format like `16:9 | 4K | 60 | W`.
- Capture settings and Pro Controls are separate pages.
- Dashboard-style connection and physical-button controls live on their own page.

The settings list is based on the Open GoPro setting groups available over BLE/Wi-Fi. Because legal options vary by camera model, firmware, current preset, and whether the camera is recording, the current firmware exposes the setting groups and has `Sync State` / `Sync Presets` controls. The next step is to populate exact option pickers from the synced camera capabilities before sending individual setting changes.

See [gopro_ui_research.md](gopro_ui_research.md).

## JPEG Preview

The preview area is a low-rate JPEG preview path, not full real-time video decode.

Current behavior:

- When Wi-Fi is connected and not recording, the remote requests GoPro media/thumbnail data.
- The preview is sized for the small AMOLED screen.
- While recording, preview is paused.

Common preview messages:

- `Connect WiFi for JPEG preview`
- `No GoPro JPEG media found`
- `JPEG fetch failed`
- `JPEG decode failed`
- `Preview paused while recording`

## Recording

Tap `REC` or short-press BOOT.

When recording starts:

- The remote sends `/gopro/camera/shutter/start`.
- Status changes to `Recording`.
- JPEG preview pauses.

Tap `REC` or short-press BOOT again to stop recording. The remote sends `/gopro/camera/shutter/stop`.

![Recording screen](images/ui/07-recording.svg)

## Display Sleep And Power Off

Short-press PWR to blank the display. This saves display power but does not fully shut down the ESP32-S3.

![Display sleeping screen](images/ui/08-display-sleeping.svg)

Long-press PWR to enter low-power shutdown:

- Recording state is cleared locally.
- Wi-Fi is disconnected and turned off.
- The AMOLED is dimmed.
- The firmware asks the AXP2101 PMU to shut down.
- If PMU shutdown is unavailable, the ESP32-S3 enters deep sleep as a fallback.

![Powering off screen](images/ui/09-powering-off.svg)

On USB power, the board may not appear fully off because USB continues to supply power. Test battery drain while running from battery.

## Normal Use Checklist

1. Power on the ESP32-S3 remote.
2. Confirm the main screen appears.
3. Put the GoPro into pairing mode if this is the first connection.
4. Tap `Pair`.
5. Tap `Connect` or `WiFi`.
6. Wait for `WIFI ON`.
7. Use `REC` to start/stop recording.
8. Short-press PWR to blank the screen between uses.
9. Long-press PWR for low-power shutdown.

## Troubleshooting

`Camera: BLE not found`

The GoPro is not advertising nearby, is already connected to another controller, or is not in the expected pairing/advertising state. Wake the GoPro and put it back into pairing mode if needed.

`GoPro WiFi credentials unreadable`

BLE connected, but the Wi-Fi service or characteristics were not readable. Re-pair the camera from the GoPro pairing screen.

`GoPro WiFi connect failed`

The remote read credentials but could not join the camera AP. Wait a few seconds and tap `WiFi` again. The camera AP can take a moment to become visible after the BLE enable command.

`Connect WiFi for JPEG preview`

The remote has not joined the GoPro AP yet. Tap `Connect` or `WiFi`.

`Preview paused while recording`

This is expected in the current firmware. The preview path uses still JPEG fetch/decode, and it is intentionally paused while video recording.

## Build Verification

The current codebase has been built for:

- `esp32dev`
- `esp32s3_radio`
- `esp32s3_amoled_ui`
- `ui_esp32dev_sim`
- `esp32p4_ui`

Run the same build matrix:

```sh
pio run -e esp32dev -e esp32s3_radio -e esp32s3_amoled_ui -e ui_esp32dev_sim -e esp32p4_ui
```
