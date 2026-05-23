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
- Retrieve media screennails/thumbnails over Wi-Fi/HTTP for photo media.
- Start capture over Wi-Fi/HTTP when already connected, or over BLE when Wi-Fi is not connected.
- Disable the camera Wi-Fi AP over BLE during recording to reduce battery use.

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
- `Sync State` calls `/gopro/camera/state` and parses the returned `settings` object into the current setting cache.
- `Sync Presets` calls `/gopro/camera/presets/get?include-hidden=1` to refresh the camera's current preset tree.
- Individual setting buttons open a dynamic option sheet. The firmware queries `/gopro/camera/setting?setting=<id>` for the current option, intentionally probes `/gopro/camera/setting?setting=<id>&option=65535` to let the camera return its currently valid options, and then sends `/gopro/camera/setting?setting=<id>&option=<option>` for the selected option.
- If the camera cannot return an option list, the sheet falls back to common documented option IDs for that setting so the UI remains usable while still reporting command success/failure from the camera.
- Snapshot preview uses the photo screennail endpoint because the S3 does not decode the H.264 preview stream. Before taking the temporary photo, the firmware switches to Video, reads `/gopro/camera/state`, then reads `/gopro/camera/presets/get` with `include-hidden` fallbacks and applies the active Video preset's `settingArray` for aspect/framing, resolution, digital lens, HyperSmooth, horizon, and Max Lens settings. The downloaded photo screennail is then center-cropped to that target video frame and an estimated stabilization crop before being drawn. Open GoPro exposes the relevant settings but not an exact per-frame electronic-stabilization crop rectangle, so fast camera motion or Auto Boost can still differ slightly from the recorded frame.
- Recording does not require an active Wi-Fi connection after the shutter command has succeeded. The current firmware starts recording over Wi-Fi if the GoPro AP is already joined because that is fastest, falls back to BLE otherwise, then shuts down ESP32-S3 Wi-Fi and disables the GoPro AP over BLE. Stopping recording uses BLE so the remote does not need to wake the AP just to stop capture.

This is intentional because Open GoPro warns that setting availability and legal option combinations vary by camera model, firmware, current preset, and whether the camera is encoding.
