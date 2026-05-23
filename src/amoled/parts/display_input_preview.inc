bool pointInRect(int16_t x, int16_t y, int16_t rx, int16_t ry, int16_t rw, int16_t rh) {
  return x >= rx && x < rx + rw && y >= ry && y < ry + rh;
}

lv_point_t ignoredTouchPoint() {
  return {0, 0};
}

void consumeLvglPointer(lv_indev_data_t *data) {
  if (touchInput) {
    lv_indev_reset(touchInput, nullptr);
  }
  data->state = LV_INDEV_STATE_REL;
  data->point = ignoredTouchPoint();
}

bool pointInPairButtonRaw(int16_t x, int16_t y) {
  if (previewFullscreen) {
    return false;
  }
  return pointInRect(x, y, kPreviewX, kTopBarH + kHomeButtonY, kPreviewW, kHomeButtonH) ||
         pointInRect(x, y, kPreviewX, kHomeButtonY, kPreviewW, kHomeButtonH);
}

bool pairingUiActive() {
  return pairingInProgress || pendingHomeAction == PendingHomeAction::Pair ||
         (pairingPopup && !lv_obj_has_flag(pairingPopup, LV_OBJ_FLAG_HIDDEN));
}

bool modalUiActive() {
  return (settingSheet && !lv_obj_has_flag(settingSheet, LV_OBJ_FLAG_HIDDEN)) ||
         (forgetConfirmPopup && !lv_obj_has_flag(forgetConfirmPopup, LV_OBJ_FLAG_HIDDEN));
}

int clampMaintenanceX(int x) {
  if (x < -LCD_WIDTH) {
    return -LCD_WIDTH;
  }
  if (x > 0) {
    return 0;
  }
  return x;
}

void setMaintenancePageX(int x) {
  if (!maintenancePage) {
    return;
  }
  lv_obj_clear_flag(maintenancePage, LV_OBJ_FLAG_HIDDEN);
  lv_obj_set_pos(maintenancePage, clampMaintenanceX(x), kTopBarH);
}

void maintenancePageAnimExec(void *obj, int32_t value) {
  lv_obj_set_x(static_cast<lv_obj_t *>(obj), value);
}

void animateMaintenancePageTo(int targetX) {
  if (!maintenancePage) {
    return;
  }
  lv_obj_clear_flag(maintenancePage, LV_OBJ_FLAG_HIDDEN);
  lv_anim_del(maintenancePage, maintenancePageAnimExec);
  lv_anim_t anim;
  lv_anim_init(&anim);
  lv_anim_set_var(&anim, maintenancePage);
  lv_anim_set_values(&anim, lv_obj_get_x(maintenancePage), clampMaintenanceX(targetX));
  lv_anim_set_time(&anim, kNavPageAnimMs);
  lv_anim_set_path_cb(&anim, lv_anim_path_ease_out);
  lv_anim_set_exec_cb(&anim, maintenancePageAnimExec);
  lv_anim_start(&anim);
}

bool isMaintenancePageShowing() {
  return maintenancePageVisible || navSwipeActive ||
         (maintenancePage && !lv_obj_has_flag(maintenancePage, LV_OBJ_FLAG_HIDDEN) &&
          lv_obj_get_x(maintenancePage) > -LCD_WIDTH);
}

void consumeActionButtonPress() {
  actionButtonShortClickCount = 0;
  actionButtonShortClickDueMs = 0;
  actionButtonPressedAtMs = 0;
  actionButtonLongHandled = true;
}

bool lowerButtonSuppressed() {
  uint32_t now = millis();
  return suppressLowerButtonUntilMs != 0 &&
         static_cast<int32_t>(suppressLowerButtonUntilMs - now) > 0;
}

void suppressLowerButtonDuplicates(uint32_t durationMs, const char *source) {
  suppressLowerButtonUntilMs = millis() + durationMs;
  consumeActionButtonPress();
  Serial.printf("Suppressing lower/action duplicates for %u ms after %s\n",
                static_cast<unsigned>(durationMs),
                source == nullptr ? "action" : source);
}

void setConnectRetryAvailable(bool available) {
  connectRetryAvailable = available && !boundBleAddress.isEmpty();
  if (connectRetryAvailable) {
    homeCameraConnected = false;
  }
  if (pairButton) {
    if (!recording) {
      lv_obj_clear_state(pairButton, LV_STATE_DISABLED);
    }
    lv_obj_add_flag(pairButton, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_bg_color(pairButton, lv_color_hex(0x2c7be5), 0);
  }
  if (pairButtonLabel) {
    lv_label_set_text(pairButtonLabel, connectRetryAvailable ? "Scan Again" : "Pair New");
    lv_obj_center(pairButtonLabel);
  }
}

void setHomeCameraConnected(bool connected) {
  homeCameraConnected = connected;
  if (connected) {
    connectRetryAvailable = false;
  }
  if (pairButton) {
    if (connected) {
      lv_obj_clear_flag(pairButton, LV_OBJ_FLAG_CLICKABLE);
      lv_obj_set_style_bg_color(pairButton, lv_color_hex(0x136f46), 0);
    } else {
      if (!recording) {
        lv_obj_clear_state(pairButton, LV_STATE_DISABLED);
      }
      lv_obj_add_flag(pairButton, LV_OBJ_FLAG_CLICKABLE);
      lv_obj_set_style_bg_color(pairButton, lv_color_hex(0x2c7be5), 0);
    }
  }
  if (pairButtonLabel) {
    lv_label_set_text(pairButtonLabel,
                      connected ? "Camera Connected" : (connectRetryAvailable ? "Scan Again" : "Pair New"));
    lv_obj_center(pairButtonLabel);
  }
}

void clearBleScanDevices() {
  delete bestBleDevice;
  bestBleDevice = nullptr;
  delete fallbackBleDevice;
  fallbackBleDevice = nullptr;
}

bool happenedRecently(uint32_t timestampMs, uint32_t windowMs) {
  return timestampMs != 0 && millis() - timestampMs < windowMs;
}

bool exitFullscreenPreview(const char *source) {
  if (!displayOn || !previewFullscreen) {
    return false;
  }
  Serial.printf("%s: exit fullscreen preview\n", source);
  setPreviewFullscreen(false);
  if (previewLabel && previewHasImage) {
    lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
  }
  setAction("Preview minimized");
  lv_timer_handler();
  return true;
}

bool enterFullscreenPreview(const char *source) {
  if (!displayOn || previewFullscreen || maintenancePageVisible || navSwipeActive ||
      modalUiActive() || pairingUiActive()) {
    return false;
  }
  Serial.printf("%s: enter fullscreen preview\n", source);
  setPreviewFullscreen(true);
  if (previewLabel && previewHasImage) {
    lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
  }
  lv_timer_handler();
  return true;
}

void queuePairNewAction(const char *source) {
  if (recording) {
    setAction("Stop recording before pairing");
    return;
  }
  if (goproActionBusy || pairingInProgress || pendingHomeAction == PendingHomeAction::Pair) {
    return;
  }
  pendingHomeAction = PendingHomeAction::Pair;
  pendingHomeActionDueMs = millis() + 50;
  lastHomeTouchMs = millis();
  setHomeCameraConnected(false);
  setConnectRetryAvailable(false);
  showPairingPopup("Pairing New Camera\n\nStarting scan...\nPress lower button to cancel.");
  if (statusLabel) {
    lv_label_set_text(statusLabel, "Pair New");
  }
  if (actionLabel) {
    lv_label_set_text(actionLabel, "Opening Pair New");
  }
  Serial.print("Pair New queued");
  if (source && source[0]) {
    Serial.print(": ");
    Serial.print(source);
  }
  Serial.println();
}

bool handleRawPreviewSwipeMove(const lv_point_t &start, const lv_point_t &end, uint32_t durationMs) {
  int dx = end.x - start.x;
  int dy = end.y - start.y;
  if (start.y < kTopBarH || end.y < kTopBarH) {
    return false;
  }

  if (previewFullscreen) {
    if (abs(dy) < 45 || abs(dy) < abs(dx)) {
      return false;
    }
    if (dy < 0) {
      Serial.printf("Raw swipe up exits fullscreen: %d,%d -> %d,%d\n",
                    start.x, start.y, end.x, end.y);
      return exitFullscreenPreview("Raw swipe up");
    }
    return false;
  }

  if (modalUiActive()) {
    return false;
  }

  if (!maintenancePageVisible && !navSwipeActive) {
    bool verticalEnough = dy >= kFullscreenSwipePx && dy * 10 >= abs(dx) * 12;
    if (verticalEnough) {
      Serial.printf("Raw swipe down enters fullscreen: %d,%d -> %d,%d\n",
                    start.x, start.y, end.x, end.y);
      return enterFullscreenPreview("Raw swipe down");
    }
  }

  if (!navSwipeActive) {
    if (abs(dx) < kNavSwipeStartPx || abs(dx) * 10 < abs(dy) * 12) {
      return false;
    }
    if (!maintenancePageVisible && dx > 0) {
      navSwipeActive = true;
      navSwipeStartedVisible = false;
      hidePairingPopup();
      setMaintenancePageX(-LCD_WIDTH);
      lv_obj_move_foreground(maintenancePage);
    } else if (maintenancePageVisible && dx < 0) {
      navSwipeActive = true;
      navSwipeStartedVisible = true;
      lv_obj_move_foreground(maintenancePage);
    } else {
      return false;
    }
  }

  if (navSwipeStartedVisible) {
    setMaintenancePageX(dx < 0 ? dx : 0);
  } else {
    setMaintenancePageX(-LCD_WIDTH + (dx > 0 ? dx : 0));
  }
  (void)durationMs;
  return true;
}

bool finishRawPreviewSwipe(const lv_point_t &start, const lv_point_t &end, uint32_t durationMs) {
  if (!navSwipeActive) {
    if (!handleRawPreviewSwipeMove(start, end, durationMs)) {
      return false;
    }
  }

  int dx = end.x - start.x;
  int dy = end.y - start.y;
  bool horizontalEnough = abs(dx) * 10 >= abs(dy) * 12;
  bool flick = durationMs <= kNavSwipeFlickMs && abs(dx) >= kNavSwipeFlickPx;
  bool commit = horizontalEnough && (abs(dx) >= kNavSwipeCommitPx || flick);
  bool open = navSwipeStartedVisible ? !(commit && dx < 0) : (commit && dx > 0);
  navSwipeActive = false;

  if (open && !maintenancePageVisible) {
    Serial.printf("Raw swipe right opens maintenance: %d,%d -> %d,%d\n",
                  start.x, start.y, end.x, end.y);
    setMaintenancePageVisible(true);
  } else if (!open && maintenancePageVisible) {
    Serial.printf("Raw swipe left returns home: %d,%d -> %d,%d\n",
                  start.x, start.y, end.x, end.y);
    setMaintenancePageVisible(false);
  } else {
    animateMaintenancePageTo(open ? 0 : -LCD_WIDTH);
    lv_timer_handler();
  }
  return true;
}

bool handleRawPreviewSwipe(const lv_point_t &start, const lv_point_t &end, uint32_t durationMs) {
  return handleRawPreviewSwipeMove(start, end, durationMs);
}

bool finishRawPreviewSwipeIfNeeded(const lv_point_t &start, const lv_point_t &end,
                                   uint32_t durationMs) {
  if (previewFullscreen) {
    return handleRawPreviewSwipeMove(start, end, durationMs);
  }
  return finishRawPreviewSwipe(start, end, durationMs);
}

void onPageGesture(lv_event_t *) {
  lv_dir_t dir = lv_indev_get_gesture_dir(lv_indev_get_act());
  if (previewFullscreen) {
    if (dir == LV_DIR_TOP) {
      exitFullscreenPreview("LVGL swipe up");
    }
    return;
  }
  if (dir == LV_DIR_BOTTOM && !maintenancePageVisible) {
    enterFullscreenPreview("LVGL swipe down");
  } else if (dir == LV_DIR_RIGHT && !maintenancePageVisible) {
    setMaintenancePageVisible(true);
  } else if (dir == LV_DIR_LEFT && maintenancePageVisible) {
    setMaintenancePageVisible(false);
  }
}

void onPreviewGesture(lv_event_t *) {
  lv_dir_t dir = lv_indev_get_gesture_dir(lv_indev_get_act());
  if (dir == LV_DIR_TOP && previewFullscreen) {
    Serial.printf("Raw swipe up exits fullscreen: %d,%d -> %d,%d\n",
                  touchStartPoint.x, touchStartPoint.y, lastTouchPoint.x, lastTouchPoint.y);
    exitFullscreenPreview("Preview swipe up");
  } else if (dir == LV_DIR_BOTTOM && !previewFullscreen) {
    enterFullscreenPreview("Preview swipe down");
  }
}

void touchInterrupt() {
  touch->IIC_Interrupt_Flag = true;
}

void lvTick(void *) {
  lv_tick_inc(kLvglTickMs);
}

void flushDisplay(lv_disp_drv_t *disp, const lv_area_t *area, lv_color_t *colorP) {
  const uint32_t w = area->x2 - area->x1 + 1;
  const uint32_t h = area->y2 - area->y1 + 1;
#if (LV_COLOR_16_SWAP != 0)
  gfx->draw16bitBeRGBBitmap(area->x1, area->y1,
                            reinterpret_cast<uint16_t *>(&colorP->full), w, h);
#else
  gfx->draw16bitRGBBitmap(area->x1, area->y1,
                          reinterpret_cast<uint16_t *>(&colorP->full), w, h);
#endif
  lv_disp_flush_ready(disp);
}

void readTouch(lv_indev_drv_t *, lv_indev_data_t *data) {
  uint32_t now = millis();
  if (serialPointerActive) {
    uint32_t elapsed = now - serialPointerStartMs;
    if (elapsed <= serialPointerDurationMs) {
      lv_point_t point = serialPointerStart;
      if (serialPointerDurationMs > 0) {
        point.x = serialPointerStart.x +
                  ((serialPointerEnd.x - serialPointerStart.x) *
                   static_cast<int32_t>(elapsed)) /
                      static_cast<int32_t>(serialPointerDurationMs);
        point.y = serialPointerStart.y +
                  ((serialPointerEnd.y - serialPointerStart.y) *
                   static_cast<int32_t>(elapsed)) /
                      static_cast<int32_t>(serialPointerDurationMs);
      }
      if (!touchActive) {
        touchStartPoint = serialPointerStart;
        touchStartMs = serialPointerStartMs;
        touchActive = true;
        rawSwipeHandled = false;
        navSwipeActive = false;
      }
      lastTouchPoint = point;
      lastTouchMs = now;
      if (handleRawPreviewSwipe(touchStartPoint, lastTouchPoint, elapsed)) {
        rawSwipeHandled = true;
      }
      if (rawSwipeHandled) {
        consumeLvglPointer(data);
      } else {
        data->state = LV_INDEV_STATE_PR;
        data->point = lastTouchPoint;
      }
      return;
    }

    lastTouchPoint = serialPointerEnd;
    lastTouchMs = now;
    if (!touchActive) {
      touchStartPoint = serialPointerStart;
      touchStartMs = serialPointerStartMs;
      rawSwipeHandled = false;
      navSwipeActive = false;
      touchActive = true;
    }
    if (touchActive) {
      rawSwipeHandled = finishRawPreviewSwipeIfNeeded(touchStartPoint, lastTouchPoint, elapsed) ||
                        rawSwipeHandled;
    }
    bool consumedByRawSwipe = rawSwipeHandled;
    touchActive = false;
    rawSwipeHandled = false;
    serialPointerActive = false;
    if (consumedByRawSwipe) {
      consumeLvglPointer(data);
    } else {
      data->state = LV_INDEV_STATE_REL;
      data->point = lastTouchPoint;
    }
    return;
  }

  bool pollTouch = touch->IIC_Interrupt_Flag || touchActive;
  if (pollTouch) {
    bool hadInterrupt = touch->IIC_Interrupt_Flag;
    touch->IIC_Interrupt_Flag = false;
    int16_t rawX = touch->IIC_Read_Device_Value(
        Arduino_IIC_Touch::Value_Information::TOUCH_COORDINATE_X);
    int16_t rawY = touch->IIC_Read_Device_Value(
        Arduino_IIC_Touch::Value_Information::TOUCH_COORDINATE_Y);
    uint8_t fingers = touch->IIC_Read_Device_Value(
        Arduino_IIC_Touch::Value_Information::TOUCH_FINGER_NUMBER);
    if (hadInterrupt) {
      Serial.printf("Touch raw x=%d y=%d fingers=%u\n", rawX, rawY, fingers);
    }

    if (fingers > 0) {
      if (!touchActive) {
        touchStartPoint.x = rawX;
        touchStartPoint.y = rawY;
        touchStartMs = now;
        touchActive = true;
        rawSwipeHandled = false;
        navSwipeActive = false;
      }
      lastTouchPoint.x = rawX;
      lastTouchPoint.y = rawY;
      lastTouchMs = now;
      if (handleRawPreviewSwipe(touchStartPoint, lastTouchPoint, now - touchStartMs)) {
        rawSwipeHandled = true;
      }
      if (rawSwipeHandled) {
        consumeLvglPointer(data);
      } else {
        data->state = LV_INDEV_STATE_PR;
        data->point = lastTouchPoint;
      }
    } else {
      bool consumedByRawSwipe = rawSwipeHandled;
      if (touchActive) {
        rawSwipeHandled =
            finishRawPreviewSwipeIfNeeded(touchStartPoint, lastTouchPoint, now - touchStartMs) ||
            rawSwipeHandled;
        consumedByRawSwipe = rawSwipeHandled;
      }
      touchActive = false;
      rawSwipeHandled = false;
      if (consumedByRawSwipe) {
        consumeLvglPointer(data);
      } else {
        data->state = LV_INDEV_STATE_REL;
        data->point = lastTouchPoint;
      }
      return;
    }

    if (statusLabel && now - lastHomeTouchMs > 300) {
      char label[40];
      snprintf(label, sizeof(label), "Touch %d,%d", rawX, rawY);
      lv_label_set_text(statusLabel, label);
    }
  } else if (touchActive && now - lastTouchMs < 180) {
    data->state = LV_INDEV_STATE_PR;
    data->point = lastTouchPoint;
  } else {
    data->state = LV_INDEV_STATE_REL;
    data->point = lastTouchPoint;
  }
}

void styleButton(lv_obj_t *button, lv_color_t color) {
  lv_obj_set_style_radius(button, 8, 0);
  lv_obj_set_style_bg_color(button, color, 0);
  lv_obj_set_style_bg_opa(button, LV_OPA_COVER, 0);
  lv_color_t pressed = lv_color_make(
      static_cast<uint8_t>((lv_color_to32(color) >> 16 & 0xff) * 2 / 3),
      static_cast<uint8_t>((lv_color_to32(color) >> 8 & 0xff) * 2 / 3),
      static_cast<uint8_t>((lv_color_to32(color) & 0xff) * 2 / 3));
  lv_obj_set_style_bg_color(button, pressed, LV_STATE_PRESSED);
  lv_obj_set_style_bg_opa(button, LV_OPA_COVER, LV_STATE_PRESSED);
  lv_obj_set_style_border_width(button, 0, 0);
  lv_obj_set_style_shadow_width(button, 10, 0);
  lv_obj_set_style_shadow_opa(button, LV_OPA_20, 0);
  lv_obj_set_style_shadow_width(button, 2, LV_STATE_PRESSED);
  lv_obj_set_style_shadow_opa(button, LV_OPA_10, LV_STATE_PRESSED);
  lv_obj_set_style_translate_y(button, 2, LV_STATE_PRESSED);
}

const lv_font_t *fontForSize(int size) {
  if (size >= 24) {
    return &lv_font_montserrat_24;
  }
  if (size >= 22) {
    return &lv_font_montserrat_22;
  }
  if (size >= 18) {
    return &lv_font_montserrat_20;
  }
  if (size >= 16) {
    return &lv_font_montserrat_18;
  }
  return &lv_font_montserrat_16;
}

lv_obj_t *makeButton(lv_obj_t *parent, const char *text, lv_color_t color) {
  lv_obj_t *button = lv_btn_create(parent);
  styleButton(button, color);
  lv_obj_t *label = lv_label_create(button);
  lv_label_set_text(label, text);
  lv_obj_set_style_text_font(label, fontForSize(18), 0);
  lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_center(label);
  return button;
}

lv_obj_t *makeChip(lv_obj_t *parent, const char *text, int x, int y, int w, lv_color_t color) {
  lv_obj_t *chip = makeButton(parent, text, color);
  lv_obj_set_size(chip, w, 40);
  lv_obj_set_pos(chip, x, y);
  return chip;
}

lv_obj_t *makeTouchButton(lv_obj_t *parent, const char *text, int x, int y, int w, int h,
                          lv_color_t color) {
  lv_obj_t *button = makeButton(parent, text, color);
  lv_obj_set_size(button, w, h);
  lv_obj_set_pos(button, x, y);
  return button;
}

void setAction(const char *message) {
  if (actionLabel) {
    lv_label_set_text(actionLabel, message);
  }
  if (pairingInProgress) {
    String popup = message;
    popup += "\n\nLower button cancels.";
    setPairingPopupMessage(popup.c_str());
  }
  Serial.println(message);
  if (tileView) {
    lv_timer_handler();
  }
}

void logMemory(const char *label) {
  Serial.printf("%s heap=%u internal=%u psram=%u\n", label,
                ESP.getFreeHeap(),
                heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
                heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
}

const char *resetReasonName(esp_reset_reason_t reason) {
  switch (reason) {
    case ESP_RST_POWERON: return "power-on";
    case ESP_RST_EXT: return "external";
    case ESP_RST_SW: return "software";
    case ESP_RST_PANIC: return "panic";
    case ESP_RST_INT_WDT: return "interrupt-watchdog";
    case ESP_RST_TASK_WDT: return "task-watchdog";
    case ESP_RST_WDT: return "watchdog";
    case ESP_RST_DEEPSLEEP: return "deep-sleep";
    case ESP_RST_BROWNOUT: return "brownout";
    case ESP_RST_SDIO: return "sdio";
    default: return "unknown";
  }
}

void releaseH264PreviewResources(const char *reason) {
  bool released = false;
  if (h264Decoder) {
    h264bsdFree(h264Decoder);
    h264Decoder = nullptr;
    released = true;
  }
  if (h264AccessUnit) {
    heap_caps_free(h264AccessUnit);
    h264AccessUnit = nullptr;
    released = true;
  }
  h264AccessUnitLen = 0;
  h264DecoderReady = false;
  h264StreamUnsupported = false;
  h264UnsupportedNotified = false;
  h264DecodeFailures = 0;
  if (released) {
    logMemory(reason == nullptr ? "Released H264 preview resources" : reason);
  }
}

void setObjHidden(lv_obj_t *obj, bool hidden) {
  if (!obj) {
    return;
  }
  if (hidden) {
    lv_obj_add_flag(obj, LV_OBJ_FLAG_HIDDEN);
  } else {
    lv_obj_clear_flag(obj, LV_OBJ_FLAG_HIDDEN);
  }
}

void updateGoProBatteryIndicator() {
  if (!goproBatteryLabel) {
    return;
  }

  char text[16];
  if (goProBatteryPercent < 0) {
    snprintf(text, sizeof(text), "%s--%%",
             goProBatteryChargingOrPlugged ? LV_SYMBOL_CHARGE : "");
    lv_obj_set_style_text_color(goproBatteryLabel, lv_color_hex(0x5a6472), 0);
  } else {
    int percent = constrain(goProBatteryPercent, 0, 100);
    snprintf(text, sizeof(text), "%s%d%%",
             goProBatteryChargingOrPlugged ? LV_SYMBOL_CHARGE : "",
             percent);
    if (goProBatteryChargingOrPlugged) {
      lv_obj_set_style_text_color(goproBatteryLabel, lv_color_hex(0x47d16c), 0);
    } else if (percent <= 15) {
      lv_obj_set_style_text_color(goproBatteryLabel, lv_color_hex(0xf03e3e), 0);
    } else if (percent <= 35) {
      lv_obj_set_style_text_color(goproBatteryLabel, lv_color_hex(0xf0b429), 0);
    } else {
      lv_obj_set_style_text_color(goproBatteryLabel, lv_color_hex(0xc3ccd8), 0);
    }
  }
  lv_label_set_text(goproBatteryLabel, text);
}

void setPairingPopupMessage(const char *message) {
  if (!pairingPopupMessage) {
    return;
  }
  String status = message == nullptr ? "" : message;
  constexpr const char *heading = "Pairing New Camera";
  if (status.startsWith(heading)) {
    status.remove(0, strlen(heading));
    while (status.startsWith("\n")) {
      status.remove(0, 1);
    }
  }
  status.trim();
  if (status.isEmpty()) {
    status = "Starting...";
  }
  lv_label_set_text(pairingPopupMessage, status.c_str());
}

void showPairingPopup(const char *message) {
  pairingPopupHideDueMs = 0;
  setPairingPopupMessage(message);
  if (pairingPopup) {
    lv_obj_clear_flag(pairingPopup, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_foreground(pairingPopup);
    lv_timer_handler();
  }
}

void finishPairingPopup(const char *message) {
  setPairingPopupMessage(message);
  if (pairingPopup) {
    lv_obj_clear_flag(pairingPopup, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_foreground(pairingPopup);
    pairingPopupHideDueMs = millis() + 1800;
    lv_timer_handler();
  }
}

void hidePairingPopup() {
  pairingPopupHideDueMs = 0;
  if (pairingPopup) {
    lv_obj_add_flag(pairingPopup, LV_OBJ_FLAG_HIDDEN);
  }
}

void setMaintenancePageVisible(bool visible) {
  maintenancePageVisible = visible;
  if (!maintenancePage) {
    return;
  }
  navSwipeActive = false;
  if (visible) {
    lv_obj_clear_flag(maintenancePage, LV_OBJ_FLAG_HIDDEN);
    lv_obj_move_foreground(maintenancePage);
    animateMaintenancePageTo(0);
    hidePairingPopup();
    setAction("Maintenance");
  } else {
    hideForgetConfirm();
    animateMaintenancePageTo(-LCD_WIDTH);
    setAction("Preview");
  }
  lv_timer_handler();
}

void showForgetConfirm() {
  if (!forgetConfirmPopup) {
    return;
  }
  lv_obj_clear_flag(forgetConfirmPopup, LV_OBJ_FLAG_HIDDEN);
  lv_obj_move_foreground(forgetConfirmPopup);
  setAction("Confirm forget camera");
  lv_timer_handler();
}

void hideForgetConfirm() {
  if (forgetConfirmPopup) {
    lv_obj_add_flag(forgetConfirmPopup, LV_OBJ_FLAG_HIDDEN);
  }
}

void clearSnapshotPreviewState(const char *message) {
  previewHasImage = false;
  snapshotPreviewBusy = false;
  snapshotPreviewPrepared = false;
  lastSnapshotMediaPath = "";
  clearPreviewJpegCache();
  if (previewFullscreen) {
    setPreviewFullscreen(false);
  }
  if (previewLabel) {
    lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    lv_label_set_text(previewLabel, message == nullptr ? "Double-click lower for snapshot" : message);
    lv_obj_center(previewLabel);
  }
}

int previewFrameX() {
  return previewFullscreen ? 0 : kPreviewX;
}

int previewFrameY() {
  return previewFullscreen ? kTopBarH : kTopBarH + 6;
}

int previewFrameW() {
  return previewFullscreen ? LCD_WIDTH : kPreviewW;
}

int previewFrameH() {
  return previewFullscreen ? LCD_HEIGHT - kTopBarH : kPreviewH;
}

void clearPreviewJpegCache() {
  if (previewJpegCache) {
    heap_caps_free(previewJpegCache);
    previewJpegCache = nullptr;
  }
  previewJpegCacheLen = 0;
}

void adoptPreviewJpegCache(uint8_t *buffer, size_t length) {
  clearPreviewJpegCache();
  previewJpegCache = buffer;
  previewJpegCacheLen = length;
}

bool shrinkAndAdoptPreviewJpegCache(uint8_t *&buffer, size_t length) {
  if (buffer == nullptr || length == 0) {
    return false;
  }

  uint8_t *cacheBuffer = buffer;
  if (length < kMaxJpegBytes) {
    uint8_t *rightSized = static_cast<uint8_t *>(
        heap_caps_malloc(length, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    if (rightSized == nullptr) {
      rightSized = static_cast<uint8_t *>(heap_caps_malloc(length, MALLOC_CAP_8BIT));
    }
    if (rightSized != nullptr) {
      memcpy(rightSized, buffer, length);
      heap_caps_free(buffer);
      cacheBuffer = rightSized;
      Serial.printf("JPEG cache right-sized: %u bytes\n", static_cast<unsigned>(length));
    } else {
      Serial.printf("JPEG cache right-size allocation failed; keeping %u byte buffer\n",
                    static_cast<unsigned>(kMaxJpegBytes));
    }
  }

  adoptPreviewJpegCache(cacheBuffer, length);
  buffer = nullptr;
  return true;
}

bool redrawCachedPreviewJpeg();

void schedulePreviewRedraw(uint32_t delayMs = 80, uint8_t passes = 1) {
  if (!previewHasImage || !previewFullscreen || !previewJpegCache || previewJpegCacheLen == 0 ||
      redrawingCachedPreview) {
    return;
  }
  previewRedrawPending = true;
  previewRedrawDueMs = millis() + delayMs;
  previewRedrawPassesRemaining = max<uint8_t>(previewRedrawPassesRemaining, passes);
}

void servicePreviewRedraw() {
  if (!previewRedrawPending) {
    return;
  }
  if (!previewHasImage || !previewFullscreen || !previewJpegCache || previewJpegCacheLen == 0) {
    previewRedrawPending = false;
    previewRedrawPassesRemaining = 0;
    return;
  }
  if (static_cast<int32_t>(millis() - previewRedrawDueMs) < 0) {
    return;
  }
  bool ok = redrawCachedPreviewJpeg();
  if (!ok || previewRedrawPassesRemaining <= 1) {
    previewRedrawPending = false;
    previewRedrawPassesRemaining = 0;
    return;
  }
  previewRedrawPassesRemaining--;
  previewRedrawDueMs = millis() + 120;
}

void drawFullscreenSwipeHandle() {
  if (!previewFullscreen) {
    return;
  }
  constexpr int handleW = 112;
  constexpr int handleH = 5;
  int x = (LCD_WIDTH - handleW) / 2;
  int y = LCD_HEIGHT - 12;
  gfx->fillRoundRect(x, y, handleW, handleH, 2, 0xffff);
}

void setPreviewFullscreen(bool fullscreen) {
  previewFullscreen = fullscreen;
  if (!previewBox || !fullscreenHint) {
    return;
  }

  if (fullscreen) {
    hideForgetConfirm();
    if (maintenancePage) {
      lv_anim_del(maintenancePage, maintenancePageAnimExec);
      setMaintenancePageX(-LCD_WIDTH);
      maintenancePageVisible = false;
      navSwipeActive = false;
    }
    lv_obj_set_pos(previewBox, 0, 0);
    lv_obj_set_size(previewBox, LCD_WIDTH, LCD_HEIGHT - kTopBarH);
    lv_obj_set_style_radius(previewBox, 0, 0);
    lv_obj_set_style_border_width(previewBox, 0, 0);
    lv_obj_align(fullscreenHint, LV_ALIGN_BOTTOM_MID, 0, -4);
  } else {
    lv_obj_set_size(previewBox, kPreviewW, kPreviewH);
    lv_obj_set_pos(previewBox, kPreviewX, 6);
    lv_obj_set_style_radius(previewBox, 8, 0);
    lv_obj_set_style_border_width(previewBox, 1, 0);
    lv_obj_align(fullscreenHint, LV_ALIGN_BOTTOM_MID, 0, 4);
  }
  if (recordingOverlay) {
    lv_obj_center(recordingOverlay);
  }

  setObjHidden(recordPill, true);
  setObjHidden(timeRemainingLabel, true);
  setObjHidden(captureModeLabel, fullscreen);
  setObjHidden(captureSettingLabel, fullscreen);
  setObjHidden(cameraLabel, fullscreen);
  setObjHidden(wifiLabel, fullscreen);
  setObjHidden(pairButton, fullscreen);
  setObjHidden(forgetButton, fullscreen);
  setObjHidden(actionLabel, fullscreen);
  setObjHidden(recordingOverlay, !recording);
  lv_obj_move_foreground(previewBox);
  if (recordingOverlay) {
    lv_obj_move_foreground(recordingOverlay);
  }
  lv_obj_move_foreground(fullscreenHint);

  if (previewHasImage && previewJpegCache && previewJpegCacheLen > 0 && !redrawingCachedPreview) {
    lv_timer_handler();
    schedulePreviewRedraw(80, 2);
  }
}

String formatElapsed(uint32_t elapsedMs) {
  uint32_t totalSeconds = elapsedMs / 1000;
  uint32_t hours = totalSeconds / 3600;
  uint32_t minutes = (totalSeconds / 60) % 60;
  uint32_t seconds = totalSeconds % 60;
  char text[16];
  if (hours > 0) {
    snprintf(text, sizeof(text), "%lu:%02lu:%02lu",
             static_cast<unsigned long>(hours),
             static_cast<unsigned long>(minutes),
             static_cast<unsigned long>(seconds));
  } else {
    snprintf(text, sizeof(text), "%02lu:%02lu",
             static_cast<unsigned long>(minutes),
             static_cast<unsigned long>(seconds));
  }
  return String(text);
}

uint32_t currentRecordingElapsedMs() {
  if (!recording) {
    return 0;
  }
  uint32_t now = millis();
  return recordingElapsedBaseMs + (now - recordingElapsedBaseAtMs);
}

void applyRecordingUiState(bool cameraRecording, uint32_t elapsedSeconds = 0,
                           bool elapsedKnown = false) {
  uint32_t now = millis();
  bool wasRecording = recording;
  recording = cameraRecording;

  if (recording) {
    if (previewFullscreen) {
      setPreviewFullscreen(false);
    }
    if (!wasRecording || elapsedKnown) {
      uint64_t elapsedMs64 = static_cast<uint64_t>(elapsedSeconds) * 1000ULL;
      recordingElapsedBaseMs =
          elapsedMs64 > UINT32_MAX ? UINT32_MAX : static_cast<uint32_t>(elapsedMs64);
      recordingElapsedBaseAtMs = now;
      recordingStartedMs = now > recordingElapsedBaseMs ? now - recordingElapsedBaseMs : now;
    }
    lastRecordingOverlayMs = 0;
    if (pairButton) {
      lv_obj_add_state(pairButton, LV_STATE_DISABLED);
    }
  } else {
    goProWifiSuspendedForRecording = false;
    recordingStartedMs = 0;
    recordingElapsedBaseMs = 0;
    recordingElapsedBaseAtMs = 0;
    lastRecordingOverlayMs = 0;
    if (pairButton) {
      lv_obj_clear_state(pairButton, LV_STATE_DISABLED);
    }
  }

  if (statusLabel) {
    lv_label_set_text(statusLabel, recording ? "Recording" : "Standby");
  }
  if (previewLabel) {
    if (previewHasImage || recording) {
      lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    } else {
      lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
      lv_label_set_text(previewLabel, "Double-click lower for snapshot");
    }
  }
  updateRecordingOverlay(true);
}

void updateRecordingOverlay(bool force) {
  if (!recordingOverlay || !recordingOverlayLabel) {
    return;
  }
  if (!recording) {
    lv_obj_add_flag(recordingOverlay, LV_OBJ_FLAG_HIDDEN);
    return;
  }

  uint32_t now = millis();
  if (!force && now - lastRecordingOverlayMs < 1000) {
    return;
  }
  lastRecordingOverlayMs = now;

  String text = "RECORDING\n";
  text += formatElapsed(currentRecordingElapsedMs());
  lv_label_set_text(recordingOverlayLabel, text.c_str());
  lv_obj_clear_flag(recordingOverlay, LV_OBJ_FLAG_HIDDEN);
  lv_obj_move_foreground(recordingOverlay);
}

bool initH264Decoder() {
  if (h264DecoderReady) {
    return true;
  }
  if (!h264AccessUnit) {
    h264AccessUnit = static_cast<uint8_t *>(
        heap_caps_malloc(kMaxH264AccessUnit, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    if (!h264AccessUnit) {
      h264AccessUnit = static_cast<uint8_t *>(
          heap_caps_malloc(kMaxH264AccessUnit, MALLOC_CAP_8BIT));
    }
  }
  if (!h264AccessUnit) {
    Serial.println("H264 access-unit allocation failed");
    return false;
  }

  h264bsd_cfg_t cfg = H264BSD_CFG_DEFAULT();
  cfg.dualTaskEnable = 0;
  h264Decoder = h264bsdAlloc(&cfg);
  if (!h264Decoder) {
    Serial.println("H264 decoder allocation failed");
    return false;
  }
  if (h264bsdInit(h264Decoder, 1) != 0) {
    Serial.println("H264 decoder init failed");
    h264bsdFree(h264Decoder);
    h264Decoder = nullptr;
    return false;
  }
  h264DecoderReady = true;
  Serial.printf("H264 decoder ready: %s\n", esp_tinyh264_get_version());
  return true;
}

bool h264AccessUnitHasIdr(const uint8_t *data, size_t len) {
  for (size_t i = 0; i + 5 < len; ++i) {
    size_t nal = 0;
    if (data[i] == 0 && data[i + 1] == 0 && data[i + 2] == 1) {
      nal = i + 3;
    } else if (data[i] == 0 && data[i + 1] == 0 && data[i + 2] == 0 && data[i + 3] == 1) {
      nal = i + 4;
    }
    if (nal > 0 && nal < len && (data[nal] & 0x1f) == 5) {
      return true;
    }
  }
  return false;
}

void drawI420Preview(const uint8_t *pic, uint32_t width, uint32_t height) {
  if (!pic || width == 0 || height == 0 || !previewBox) {
    return;
  }
  uint32_t outW = previewFullscreen ? LCD_WIDTH : kPreviewW;
  uint32_t outH = previewFullscreen ? (LCD_HEIGHT - kTopBarH) : kPreviewH;
  uint32_t drawH = min<uint32_t>(outH, (outW * height) / width);
  uint32_t drawY = previewFullscreen ? kTopBarH + ((outH - drawH) / 2) : (kTopBarH + 6);

  uint16_t *line = static_cast<uint16_t *>(heap_caps_malloc(outW * sizeof(uint16_t), MALLOC_CAP_DMA));
  if (!line) {
    line = static_cast<uint16_t *>(heap_caps_malloc(outW * sizeof(uint16_t), MALLOC_CAP_INTERNAL));
  }
  if (!line) {
    return;
  }

  const uint8_t *yPlane = pic;
  const uint8_t *uPlane = yPlane + width * height;
  const uint8_t *vPlane = uPlane + (width * height) / 4;
  for (uint32_t y = 0; y < drawH; ++y) {
    uint32_t srcY = (y * height) / drawH;
    for (uint32_t x = 0; x < outW; ++x) {
      uint32_t srcX = (x * width) / outW;
      int yy = yPlane[srcY * width + srcX];
      int uu = uPlane[(srcY / 2) * (width / 2) + (srcX / 2)] - 128;
      int vv = vPlane[(srcY / 2) * (width / 2) + (srcX / 2)] - 128;
      int r = constrain(yy + ((1436 * vv) >> 10), 0, 255);
      int g = constrain(yy - ((352 * uu + 731 * vv) >> 10), 0, 255);
      int b = constrain(yy + ((1814 * uu) >> 10), 0, 255);
      line[x] = ((r & 0xf8) << 8) | ((g & 0xfc) << 3) | (b >> 3);
    }
    gfx->draw16bitRGBBitmap(0, drawY + y, line, outW, 1);
  }
  free(line);
}

void decodeH264AccessUnit() {
  if (h264StreamUnsupported) {
    h264AccessUnitLen = 0;
    return;
  }
  if (h264AccessUnitLen == 0 || millis() - lastH264DecodeMs < kMinDecodeIntervalMs) {
    return;
  }
  if (!h264AccessUnitHasIdr(h264AccessUnit, h264AccessUnitLen)) {
    h264AccessUnitLen = 0;
    return;
  }
  lastH264DecodeMs = millis();
  if (!initH264Decoder()) {
    h264AccessUnitLen = 0;
    return;
  }

  u8 *pic = nullptr;
  u32 width = 0;
  u32 height = 0;
  u32 remaining = h264AccessUnitLen;
  uint32_t ret = h264bsdDecode(h264Decoder, h264AccessUnit, &remaining, &pic, &width, &height);
  Serial.printf("H264 decode AU len=%u ret=%u remaining=%u size=%ux%u\n",
                h264AccessUnitLen, ret, remaining, width, height);
  if (ret == H264BSD_PIC_RDY && pic && width > 0 && height > 0) {
    h264FramesDecoded++;
    lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    drawI420Preview(pic, width, height);
  } else if (ret == H264BSD_ERROR || ret == H264BSD_PARAM_SET_ERROR || ret == H264BSD_MEMALLOC_ERROR) {
    h264DecodeFailures++;
    if (h264DecodeFailures >= 3) {
      h264StreamUnsupported = true;
      if (!h264UnsupportedNotified) {
        h264UnsupportedNotified = true;
        setAction("Preview connected; host decoder required");
      }
    }
    lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    lv_label_set_text(previewLabel, h264StreamUnsupported
                                        ? "Stream connected\nHost decoder required"
                                        : "Trying H.264 decode");
  }
  h264AccessUnitLen = 0;
}

void appendH264Payload(const uint8_t *payload, size_t len, bool start) {
  if (start && h264AccessUnitLen > 0) {
    decodeH264AccessUnit();
    h264AccessUnitLen = 0;
  }
  if (!initH264Decoder()) {
    return;
  }
  if (len == 0 || h264AccessUnitLen + len > kMaxH264AccessUnit) {
    h264AccessUnitLen = 0;
    return;
  }
  memcpy(h264AccessUnit + h264AccessUnitLen, payload, len);
  h264AccessUnitLen += len;
}

void processTsPacket(const uint8_t *packet) {
  if (packet[0] != 0x47) {
    return;
  }
  bool payloadStart = packet[1] & 0x40;
  uint16_t pid = ((packet[1] & 0x1f) << 8) | packet[2];
  if (pid != kGoProVideoPid) {
    return;
  }
  uint8_t adaptation = (packet[3] >> 4) & 0x03;
  size_t offset = 4;
  if (adaptation == 0 || adaptation == 2) {
    return;
  }
  if (adaptation == 3) {
    offset += 1 + packet[offset];
    if (offset >= kTsPacketBytes) {
      return;
    }
  }

  if (payloadStart) {
    if (kTsPacketBytes - offset < 9 || packet[offset] != 0 || packet[offset + 1] != 0 ||
        packet[offset + 2] != 1) {
      return;
    }
    uint8_t flags = packet[offset + 7];
    uint8_t headerLen = packet[offset + 8];
    (void)flags;
    offset += 9 + headerLen;
    if (offset >= kTsPacketBytes) {
      appendH264Payload(nullptr, 0, true);
      return;
    }
  }
  appendH264Payload(packet + offset, kTsPacketBytes - offset, payloadStart);
}
