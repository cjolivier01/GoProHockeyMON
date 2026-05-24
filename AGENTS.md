# Repository Agent Instructions

- Do not open GitHub pull requests as draft. Create ready-for-review PRs unless the user explicitly asks for a draft PR.
- For AMOLED side-screen navigation, use the raw-touch side-page overlay pattern in `src/amoled/parts/display_input_preview.inc`: keep LVGL tile scrolling disabled, track horizontal drag state from `readTouch`, move the off-screen `lv_obj_t` panel with `lv_obj_set_pos` as the finger moves, and snap it open/closed with `lv_anim_t` on release. This has tested as responsive, follows the finger, and remains easy to animate.
