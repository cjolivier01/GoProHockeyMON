# Repository Agent Instructions

- Do not open GitHub pull requests as draft. Create ready-for-review PRs unless the user explicitly asks for a draft PR.
- For AMOLED side-screen navigation, use the raw-touch side-page overlay pattern in `src/amoled/parts/display_input_preview.inc`: keep LVGL tile scrolling disabled, track horizontal drag state from `readTouch`, move the off-screen `lv_obj_t` panel with `lv_obj_set_pos` as the finger moves, and snap it open/closed with `lv_anim_t` on release. This has tested as responsive, follows the finger, and remains easy to animate.

## Project Handoff Notes

- Current hardware target is a single ESP32-S3 1.8-inch AMOLED remote. Do not reintroduce ESP32-P4/Pi/P4 wiring assumptions unless the user explicitly changes hardware again.
- The snapshot preview path intentionally uses a still JPEG workflow: take one temporary GoPro photo only when not recording, download/display the JPEG preview, restore Video mode, and delete the camera media file.
- The preview image is rendered through an LVGL canvas object inside the preview box. Avoid reverting this to direct `gfx->draw...` panel writes or timing-based redraw loops; those caused fullscreen/main-screen flicker and gray/black repaint bugs.
- The lower/action side button is exposed through both the GPIO expander and PMU power-key IRQ. Keep duplicate suppression in mind when changing single/double/long-click behavior.
- Avoid adding transient on-screen diagnostic text such as `Connect pressed` or `Action p...`; serial logs are acceptable for diagnostics, but the UI should stay user-facing.
- Before new work after a merged PR, sync from `master` first so changes start from the merged state.
