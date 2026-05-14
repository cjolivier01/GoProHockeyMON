# GoPro UI Research Notes

These notes summarize the UI/API references used for the AMOLED remote layout.

## Rear Screen Interaction Model

GoPro's HERO13 manual describes the rear touch screen around a default capture screen with current mode, capture settings, and battery state. It also describes swiping left or right to change modes, swiping down for the Dashboard, and Pro Controls for resolution, frame rate, lens, aspect, and advanced settings.

Reference:

- https://www.manualslib.com/manual/3596681/Gopro-Hero-13-Black.html

Applied in this firmware:

- Default page is the capture/preview page.
- Left/right swipes move between capture, modes, capture settings, Pro Controls, and dashboard.
- Header status cluster stays visible outside the swipeable tile area.
- Capture overlay shows remaining time, record state, mode, aspect ratio, resolution, FPS, and lens.
- `Wake` was renamed to `Connect` because physical PWR wakes the ESP32 display; the UI action connects/wakes the GoPro camera.

## Open GoPro API Surface

Open GoPro documents BLE, Wi-Fi, and USB interfaces. BLE is required for wireless connection setup because camera Wi-Fi must be enabled through BLE. Wi-Fi/HTTP is used for higher-throughput control, streaming, and media access.

Reference:

- https://gopro.github.io/OpenGoPro/docs/
- https://gopro.github.io/OpenGoPro/ble/

Relevant Open GoPro capabilities:

- Retrieve camera state over BLE, Wi-Fi, or USB.
- Change settings/modes over BLE, Wi-Fi, or USB.
- Start/stop capture over BLE, Wi-Fi, or USB.
- Wake/connect over BLE.
- Stream video and manage media over Wi-Fi/USB.

The BLE documentation lists the major configurable setting IDs, including:

- Video Resolution `2`
- Frames Per Second `3`
- Video Aspect Ratio `108`
- Video Lens `121`
- Photo Lens `122`
- Time Lapse Digital Lenses `123`
- Photo Output `125`
- Media Format `128`
- Anti-Flicker `134`
- HyperSmooth `135`
- Horizon Leveling `150`/`151`
- Video Duration `156`
- Max Lens `162`
- HindSight `167`
- Scheduled Capture `168`
- Video Performance Mode `173`
- Control Mode `175`
- Wireless Band `178`
- System Video Mode `180`
- Video Bit Rate `182`
- Bit Depth `183`
- Profiles `184`
- Camera Mode `194`
- Beep Volume `216`
- Screen Saver `219`
- Language `223`
- Frame Rate `234`
- Automatic Wi-Fi AP `236`
- Auto Power On USB `237`

Current firmware status:

- The UI exposes these settings as GoPro-style groups and buttons.
- `Sync State` calls `/gopro/camera/state`.
- `Sync Presets` calls `/gopro/camera/presets/get?include-hidden=1`.
- Individual setting buttons currently use a shared selection handler. The next step is to populate per-camera option IDs from the synced preset/capability response before sending `/gopro/camera/setting?setting=<id>&option=<option>`.

This is intentional because Open GoPro warns that setting availability and legal option combinations vary by camera model, firmware, current preset, and whether the camera is encoding.
