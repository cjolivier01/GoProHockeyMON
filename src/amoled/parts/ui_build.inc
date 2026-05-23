const SettingDefinition kCaptureSettings[] = {
    {"Aspect Ratio", 108},
    {"Resolution", 2},
    {"Frame Rate", 234},
    {"Video FPS Legacy", 3},
    {"Digital Lens", 121},
    {"Photo Lens", 122},
    {"TimeWarp Lens", 123},
    {"HyperSmooth", 135},
    {"Horizon Level", 150},
    {"Scheduled", 168},
    {"Duration", 156},
    {"HindSight", 167},
};

const SettingDefinition kProSettings[] = {
    {"Bit Depth", 183},
    {"Bit Rate", 182},
    {"Max Lens", 162},
    {"Max Lens Mod", 189},
    {"Max Lens Enable", 190},
    {"Media Format", 128},
    {"Photo Output", 125},
    {"Anti-Flicker", 134},
    {"Performance", 173},
    {"Control Mode", 175},
    {"Video Mode", 180},
    {"Profiles", 184},
};

const SettingDefinition kSystemSettings[] = {
    {"Camera Mode", 194},
    {"Photo Mode", 227},
    {"Wireless Band", 178},
    {"Auto WiFi AP", 236},
    {"Beeps", 216},
    {"Screen Saver", 219},
    {"GPS", 83},
    {"LED", 91},
};

void createUi() {
  lv_obj_t *screen = lv_scr_act();
  lv_obj_set_style_bg_color(screen, lv_color_hex(0x090b10), 0);
  lv_obj_set_style_text_color(screen, lv_color_hex(0xf4f7fb), 0);
  lv_obj_set_style_text_font(screen, fontForSize(16), 0);
  lv_obj_add_event_cb(screen, onPageGesture, LV_EVENT_GESTURE, nullptr);

  lv_obj_t *topBar = lv_obj_create(screen);
  lv_obj_set_size(topBar, LCD_WIDTH, kTopBarH);
  lv_obj_set_pos(topBar, 0, 0);
  lv_obj_set_style_radius(topBar, 0, 0);
  lv_obj_set_style_bg_color(topBar, lv_color_hex(0x05070b), 0);
  lv_obj_set_style_border_width(topBar, 0, 0);
  lv_obj_set_style_pad_all(topBar, 0, 0);
  lv_obj_clear_flag(topBar, LV_OBJ_FLAG_SCROLLABLE);

  lv_obj_t *title = lv_label_create(screen);
  lv_label_set_text(title, "GoPro");
  lv_obj_set_style_text_font(title, fontForSize(20), 0);
  lv_obj_set_style_text_color(title, lv_color_hex(0xf4f7fb), 0);
  lv_obj_align(title, LV_ALIGN_TOP_LEFT, 22, 7);

  statusLabel = lv_label_create(screen);
  lv_label_set_text(statusLabel, "Ready");
  lv_obj_set_style_text_color(statusLabel, lv_color_hex(0x96a2b4), 0);
  lv_obj_add_flag(statusLabel, LV_OBJ_FLAG_HIDDEN);

  batteryLabel = lv_label_create(screen);
  lv_label_set_text(batteryLabel, LV_SYMBOL_BATTERY_EMPTY);
  lv_obj_set_style_text_color(batteryLabel, lv_color_hex(0xc3ccd8), 0);
  lv_obj_align(batteryLabel, LV_ALIGN_TOP_RIGHT, -24, 7);

  wifiIndicator = lv_label_create(screen);
  lv_label_set_text(wifiIndicator, LV_SYMBOL_WIFI);
  lv_obj_set_style_text_color(wifiIndicator, lv_color_hex(0x5a6472), 0);
  lv_obj_align(wifiIndicator, LV_ALIGN_TOP_RIGHT, -122, 7);

  bleIndicator = lv_label_create(screen);
  lv_label_set_text(bleIndicator, LV_SYMBOL_BLUETOOTH);
  lv_obj_set_style_text_color(bleIndicator, lv_color_hex(0x5a6472), 0);
  lv_obj_align(bleIndicator, LV_ALIGN_TOP_RIGHT, -148, 7);

  goproBatteryLabel = lv_label_create(screen);
  lv_obj_set_width(goproBatteryLabel, 64);
  lv_label_set_long_mode(goproBatteryLabel, LV_LABEL_LONG_CLIP);
  lv_obj_set_style_text_align(goproBatteryLabel, LV_TEXT_ALIGN_RIGHT, 0);
  lv_obj_set_style_text_font(goproBatteryLabel, fontForSize(16), 0);
  lv_obj_align(goproBatteryLabel, LV_ALIGN_TOP_RIGHT, -176, 8);
  updateGoProBatteryIndicator();

  tileView = lv_tileview_create(screen);
  lv_obj_set_size(tileView, LCD_WIDTH, LCD_HEIGHT - kTopBarH);
  lv_obj_align(tileView, LV_ALIGN_BOTTOM_MID, 0, 0);
  lv_obj_set_style_bg_color(tileView, lv_color_hex(0x090b10), 0);
  lv_obj_set_style_border_width(tileView, 0, 0);
  lv_obj_set_style_pad_all(tileView, 0, 0);
  lv_obj_clear_flag(tileView, LV_OBJ_FLAG_SCROLL_ELASTIC);
  lv_obj_clear_flag(tileView, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_scrollbar_mode(tileView, LV_SCROLLBAR_MODE_OFF);
  lv_obj_add_event_cb(tileView, onPageGesture, LV_EVENT_GESTURE, nullptr);

  lv_obj_t *captureTile = lv_tileview_add_tile(tileView, 0, 0, LV_DIR_NONE);
  captureTileObj = captureTile;
  lv_obj_set_style_bg_color(captureTile, lv_color_hex(0x090b10), 0);
  lv_obj_add_event_cb(captureTile, onPreviewGesture, LV_EVENT_GESTURE, nullptr);
  lv_obj_add_event_cb(captureTile, onPageGesture, LV_EVENT_GESTURE, nullptr);

  previewBox = lv_obj_create(captureTile);
  lv_obj_set_size(previewBox, kPreviewW, kPreviewH);
  lv_obj_set_pos(previewBox, kPreviewX, 6);
  lv_obj_set_style_radius(previewBox, 8, 0);
  lv_obj_set_style_bg_color(previewBox, lv_color_hex(0x101827), 0);
  lv_obj_set_style_border_color(previewBox, lv_color_hex(0x2b3a52), 0);
  lv_obj_set_style_border_width(previewBox, 1, 0);
  lv_obj_clear_flag(previewBox, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_add_event_cb(previewBox, onPreviewGesture, LV_EVENT_GESTURE, nullptr);

  previewImageCanvas = lv_canvas_create(previewBox);
  lv_obj_set_pos(previewImageCanvas, 0, 0);
  lv_obj_add_flag(previewImageCanvas, LV_OBJ_FLAG_HIDDEN);
  lv_obj_clear_flag(previewImageCanvas, LV_OBJ_FLAG_SCROLLABLE);

  previewLabel = lv_label_create(previewBox);
  lv_label_set_text(previewLabel, "Preview standby");
  lv_obj_set_style_text_color(previewLabel, lv_color_hex(0xdde7f5), 0);
  lv_obj_set_style_text_font(previewLabel, fontForSize(18), 0);
  lv_obj_center(previewLabel);

  recordingOverlay = lv_obj_create(previewBox);
  lv_obj_set_size(recordingOverlay, 186, 70);
  lv_obj_center(recordingOverlay);
  lv_obj_set_style_radius(recordingOverlay, 6, 0);
  lv_obj_set_style_bg_color(recordingOverlay, lv_color_hex(0xd71920), 0);
  lv_obj_set_style_bg_opa(recordingOverlay, LV_OPA_COVER, 0);
  lv_obj_set_style_border_width(recordingOverlay, 0, 0);
  lv_obj_set_style_pad_all(recordingOverlay, 0, 0);
  lv_obj_clear_flag(recordingOverlay, LV_OBJ_FLAG_SCROLLABLE);
  recordingOverlayLabel = lv_label_create(recordingOverlay);
  lv_label_set_text(recordingOverlayLabel, "RECORDING\n00:00");
  lv_obj_set_style_text_align(recordingOverlayLabel, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_set_style_text_color(recordingOverlayLabel, lv_color_hex(0xffffff), 0);
  lv_obj_set_style_text_font(recordingOverlayLabel, fontForSize(20), 0);
  lv_obj_center(recordingOverlayLabel);
  lv_obj_add_flag(recordingOverlay, LV_OBJ_FLAG_HIDDEN);

  fullscreenHint = lv_obj_create(previewBox);
  lv_obj_set_size(fullscreenHint, 78, 3);
  lv_obj_align(fullscreenHint, LV_ALIGN_BOTTOM_MID, 0, 4);
  lv_obj_set_style_radius(fullscreenHint, 2, 0);
  lv_obj_set_style_bg_color(fullscreenHint, lv_color_hex(0xf4f7fb), 0);
  lv_obj_set_style_bg_opa(fullscreenHint, LV_OPA_90, 0);
  lv_obj_set_style_border_width(fullscreenHint, 0, 0);
  lv_obj_clear_flag(fullscreenHint, LV_OBJ_FLAG_SCROLLABLE);

  recordPill = lv_obj_create(captureTile);
  lv_obj_set_size(recordPill, 76, 28);
  lv_obj_set_pos(recordPill, 272, 18);
  lv_obj_set_style_radius(recordPill, 8, 0);
  lv_obj_set_style_bg_color(recordPill, lv_color_hex(0x1b2638), 0);
  lv_obj_set_style_border_width(recordPill, 0, 0);
  lv_obj_t *recDot = lv_obj_create(recordPill);
  lv_obj_set_size(recDot, 10, 10);
  lv_obj_set_pos(recDot, 10, 9);
  lv_obj_set_style_radius(recDot, 5, 0);
  lv_obj_set_style_bg_color(recDot, lv_color_hex(0xe03131), 0);
  lv_obj_set_style_border_width(recDot, 0, 0);
  makePanelLabel(recordPill, "REC", 28, 7, 14, lv_color_hex(0xf4f7fb));
  lv_obj_add_flag(recordPill, LV_OBJ_FLAG_HIDDEN);

  timeRemainingLabel = makePanelLabel(captureTile, "9H:59", 22, 14, 18, lv_color_hex(0xf4f7fb));
  lv_obj_add_flag(timeRemainingLabel, LV_OBJ_FLAG_HIDDEN);
  captureModeLabel = makePanelLabel(captureTile, captureMode.c_str(), 22, 170, 18);
  captureSettingLabel = makePanelLabel(captureTile, captureSetting.c_str(), 22, 194, 14,
                                       lv_color_hex(0xc3ccd8));

  cameraLabel = lv_label_create(captureTile);
  lv_label_set_text(cameraLabel, "Camera: not paired");
  lv_obj_set_style_text_color(cameraLabel, lv_color_hex(0xc3ccd8), 0);
  lv_obj_set_style_text_font(cameraLabel, fontForSize(16), 0);
  lv_obj_set_pos(cameraLabel, 20, 224);

  wifiLabel = lv_label_create(captureTile);
  lv_label_set_text(wifiLabel, "WiFi: idle");
  lv_obj_set_style_text_color(wifiLabel, lv_color_hex(0x96a2b4), 0);
  lv_obj_set_style_text_font(wifiLabel, fontForSize(16), 0);
  lv_obj_set_pos(wifiLabel, 20, 246);
  lv_obj_add_flag(wifiLabel, LV_OBJ_FLAG_HIDDEN);

  pairButton = makeTouchButton(captureTile, "Pair New", kPreviewX, kHomeButtonY, kPreviewW,
                               kHomeButtonH,
                               lv_color_hex(0x2c7be5));
  pairButtonLabel = lv_obj_get_child(pairButton, 0);
  lv_obj_add_event_cb(pairButton, onPair, LV_EVENT_CLICKED, nullptr);
  lv_obj_add_flag(pairButton, LV_OBJ_FLAG_CLICKABLE);

  actionLabel = lv_label_create(captureTile);
  lv_label_set_text(actionLabel, "Auto-connect | tap Pair New to change camera");
  lv_obj_set_width(actionLabel, kPreviewW);
  lv_label_set_long_mode(actionLabel, LV_LABEL_LONG_DOT);
  lv_obj_set_style_text_color(actionLabel, lv_color_hex(0x96a2b4), 0);
  lv_obj_set_style_text_font(actionLabel, fontForSize(16), 0);
  lv_obj_set_style_text_align(actionLabel, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_align(actionLabel, LV_ALIGN_BOTTOM_MID, 0, -2);

  lv_obj_t *modeTile = lv_tileview_add_tile(tileView, 1, 0, LV_DIR_NONE);
  lv_obj_set_style_bg_color(modeTile, lv_color_hex(0x090b10), 0);
  makePanelLabel(modeTile, "Modes", 20, 18, 18);
  makePanelLabel(modeTile, "Mode controls stay on fixed pages", 20, 44, 14,
                 lv_color_hex(0x96a2b4));
  lv_obj_t *video = makeChip(modeTile, "Video", 20, 84, 328, lv_color_hex(0x2c7be5));
  lv_obj_add_event_cb(video, onModeVideo, LV_EVENT_CLICKED, nullptr);
  lv_obj_t *photo = makeChip(modeTile, "Photo", 20, 132, 328, lv_color_hex(0x009a88));
  lv_obj_add_event_cb(photo, onModePhoto, LV_EVENT_CLICKED, nullptr);
  lv_obj_t *timeWarp = makeChip(modeTile, "TimeWarp", 20, 180, 328, lv_color_hex(0x7c4dff));
  lv_obj_add_event_cb(timeWarp, onModeTimeWarp, LV_EVENT_CLICKED, nullptr);
  makePanelLabel(modeTile, "Main overlay shows mode, aspect, resolution, fps, lens", 20, 242, 14,
                 lv_color_hex(0xc3ccd8));

  lv_obj_t *captureSettingsTile = lv_tileview_add_tile(tileView, 2, 0, LV_DIR_NONE);
  lv_obj_set_style_bg_color(captureSettingsTile, lv_color_hex(0x090b10), 0);
  makePanelLabel(captureSettingsTile, "Capture Settings", 20, 18, 18);
  makePanelLabel(captureSettingsTile, "Resolution, frame rate, lens, and aspect", 20, 44, 14,
                 lv_color_hex(0x96a2b4));
  for (int i = 0; i < static_cast<int>(sizeof(kCaptureSettings) / sizeof(kCaptureSettings[0])); ++i) {
    int x = 20 + (i % 2) * 168;
    int y = 82 + (i / 2) * 48;
    lv_obj_t *button = makeChip(captureSettingsTile, kCaptureSettings[i].name, x, y, 156,
                                lv_color_hex(0x1b2638));
    lv_obj_add_event_cb(button, onSettingOpen, LV_EVENT_CLICKED,
                        const_cast<SettingDefinition *>(&kCaptureSettings[i]));
  }
  lv_obj_t *syncState = makeChip(captureSettingsTile, "Sync State", 20, 314, 156,
                                 lv_color_hex(0x2c7be5));
  lv_obj_add_event_cb(syncState, onSettingSync, LV_EVENT_CLICKED, nullptr);
  lv_obj_t *syncPresets = makeChip(captureSettingsTile, "Sync Presets", 192, 314, 156,
                                   lv_color_hex(0x2c7be5));
  lv_obj_add_event_cb(syncPresets, onPresetSync, LV_EVENT_CLICKED, nullptr);

  lv_obj_t *protuneTile = lv_tileview_add_tile(tileView, 3, 0, LV_DIR_NONE);
  lv_obj_set_style_bg_color(protuneTile, lv_color_hex(0x090b10), 0);
  makePanelLabel(protuneTile, "Pro Controls", 20, 18, 18);
  makePanelLabel(protuneTile, "Advanced settings exposed by Open GoPro", 20, 44, 14,
                 lv_color_hex(0x96a2b4));
  for (int i = 0; i < static_cast<int>(sizeof(kProSettings) / sizeof(kProSettings[0])); ++i) {
    int x = 20 + (i % 2) * 168;
    int y = 82 + (i / 2) * 40;
    lv_obj_t *button = makeChip(protuneTile, kProSettings[i].name, x, y, 156,
                                lv_color_hex(0x1b2638));
    lv_obj_add_event_cb(button, onSettingOpen, LV_EVENT_CLICKED,
                        const_cast<SettingDefinition *>(&kProSettings[i]));
  }

  lv_obj_t *dashboardTile = lv_tileview_add_tile(tileView, 4, 0, LV_DIR_NONE);
  lv_obj_set_style_bg_color(dashboardTile, lv_color_hex(0x090b10), 0);
  makePanelLabel(dashboardTile, "Dashboard", 20, 18, 18);
  makePanelLabel(dashboardTile, "Connection and remote power controls", 20, 44, 14,
                 lv_color_hex(0x96a2b4));
  lv_obj_t *dashConnect = makeChip(dashboardTile, "Connect Camera", 20, 84, 328,
                                   lv_color_hex(0x2c7be5));
  lv_obj_add_event_cb(dashConnect, onDashboardConnect, LV_EVENT_CLICKED, nullptr);
  lv_obj_t *dashPair = makeChip(dashboardTile, "Pair BLE", 20, 132, 156, lv_color_hex(0x7c4dff));
  lv_obj_add_event_cb(dashPair, onPair, LV_EVENT_CLICKED, nullptr);
  lv_obj_t *dashState = makeChip(dashboardTile, "Camera State", 192, 132, 156,
                                 lv_color_hex(0x009a88));
  lv_obj_add_event_cb(dashState, onSettingSync, LV_EVENT_CLICKED, nullptr);
  for (int i = 0; i < static_cast<int>(sizeof(kSystemSettings) / sizeof(kSystemSettings[0])); ++i) {
    int x = 20 + (i % 2) * 168;
    int y = 180 + (i / 2) * 40;
    lv_obj_t *button = makeChip(dashboardTile, kSystemSettings[i].name, x, y, 156,
                                lv_color_hex(0x1b2638));
    lv_obj_add_event_cb(button, onSettingOpen, LV_EVENT_CLICKED,
                        const_cast<SettingDefinition *>(&kSystemSettings[i]));
  }
  makePanelLabel(dashboardTile, "Top REC: start / long-stop | Lower: display / double preview", 20, 350, 14,
                 lv_color_hex(0xc3ccd8));

  maintenancePage = lv_obj_create(screen);
  lv_obj_set_size(maintenancePage, LCD_WIDTH, LCD_HEIGHT - kTopBarH);
  lv_obj_set_pos(maintenancePage, -LCD_WIDTH, kTopBarH);
  lv_obj_set_style_radius(maintenancePage, 0, 0);
  lv_obj_set_style_bg_color(maintenancePage, lv_color_hex(0x090b10), 0);
  lv_obj_set_style_border_width(maintenancePage, 0, 0);
  lv_obj_set_style_pad_all(maintenancePage, 0, 0);
  lv_obj_clear_flag(maintenancePage, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_add_event_cb(maintenancePage, onPageGesture, LV_EVENT_GESTURE, nullptr);
  makePanelLabel(maintenancePage, "Maintenance", 20, 22, 18);
  makePanelLabel(maintenancePage, "Swipe left to return", 20, 50, 14,
                 lv_color_hex(0x96a2b4));
  makePanelLabel(maintenancePage, "Pairing data", 20, 104, 14,
                 lv_color_hex(0xc3ccd8));
  forgetButton = makeTouchButton(maintenancePage, "Forget Camera", kPreviewX, 132,
                                 kPreviewW, kHomeButtonH, lv_color_hex(0x7f1d1d));
  lv_obj_add_event_cb(forgetButton, onForgetCamera, LV_EVENT_CLICKED, nullptr);
  makePanelLabel(maintenancePage,
                 "Removes saved BLE address and local bonds only after confirmation.",
                 20, 204, 14, lv_color_hex(0x96a2b4));

  settingSheet = lv_obj_create(screen);
  lv_obj_set_size(settingSheet, 332, 352);
  lv_obj_align(settingSheet, LV_ALIGN_CENTER, 0, 18);
  lv_obj_set_style_radius(settingSheet, 8, 0);
  lv_obj_set_style_bg_color(settingSheet, lv_color_hex(0x111827), 0);
  lv_obj_set_style_border_color(settingSheet, lv_color_hex(0x334155), 0);
  lv_obj_set_style_border_width(settingSheet, 1, 0);
  lv_obj_set_style_pad_all(settingSheet, 12, 0);
  lv_obj_clear_flag(settingSheet, LV_OBJ_FLAG_SCROLLABLE);

  settingSheetTitle = makePanelLabel(settingSheet, "Setting", 12, 12, 18);
  for (size_t i = 0; i < kVisibleSettingOptions; ++i) {
    settingOptionButtons[i] = makeChip(settingSheet, "", 12, 48 + i * 40, 308,
                                       lv_color_hex(0x1f2937));
    settingOptionLabels[i] = lv_obj_get_child(settingOptionButtons[i], 0);
    lv_obj_add_event_cb(settingOptionButtons[i], onSettingOption, LV_EVENT_CLICKED,
                        reinterpret_cast<void *>(i));
  }

  lv_obj_t *prev = makeChip(settingSheet, "Prev", 12, 294, 70, lv_color_hex(0x334155));
  lv_obj_add_event_cb(prev, onSettingPrev, LV_EVENT_CLICKED, nullptr);
  settingPagerLabel = makePanelLabel(settingSheet, "0 of 0", 112, 304, 14, lv_color_hex(0xc3ccd8));
  lv_obj_t *next = makeChip(settingSheet, "Next", 184, 294, 70, lv_color_hex(0x334155));
  lv_obj_add_event_cb(next, onSettingNext, LV_EVENT_CLICKED, nullptr);
  lv_obj_t *close = makeChip(settingSheet, "Close", 262, 294, 58, lv_color_hex(0x7f1d1d));
  lv_obj_add_event_cb(close, onSettingClose, LV_EVENT_CLICKED, nullptr);
  lv_obj_add_flag(settingSheet, LV_OBJ_FLAG_HIDDEN);

  pairingPopup = lv_obj_create(screen);
  lv_obj_set_size(pairingPopup, 320, 184);
  lv_obj_align(pairingPopup, LV_ALIGN_CENTER, 0, 20);
  lv_obj_set_style_radius(pairingPopup, 8, 0);
  lv_obj_set_style_bg_color(pairingPopup, lv_color_hex(0x111827), 0);
  lv_obj_set_style_bg_opa(pairingPopup, LV_OPA_COVER, 0);
  lv_obj_set_style_border_color(pairingPopup, lv_color_hex(0x7c4dff), 0);
  lv_obj_set_style_border_width(pairingPopup, 2, 0);
  lv_obj_set_style_pad_all(pairingPopup, 16, 0);
  lv_obj_clear_flag(pairingPopup, LV_OBJ_FLAG_SCROLLABLE);

  pairingPopupTitle = lv_label_create(pairingPopup);
  lv_obj_set_width(pairingPopupTitle, 288);
  lv_label_set_text(pairingPopupTitle, "Pairing New Camera");
  lv_obj_set_style_text_color(pairingPopupTitle, lv_color_hex(0xf4f7fb), 0);
  lv_obj_set_style_text_font(pairingPopupTitle, fontForSize(20), 0);
  lv_obj_set_style_text_align(pairingPopupTitle, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_align(pairingPopupTitle, LV_ALIGN_TOP_MID, 0, 0);

  pairingPopupMessage = lv_label_create(pairingPopup);
  lv_obj_set_width(pairingPopupMessage, 288);
  lv_label_set_long_mode(pairingPopupMessage, LV_LABEL_LONG_WRAP);
  lv_label_set_text(pairingPopupMessage, "Put the GoPro in pairing mode.\nPress lower button to cancel.");
  lv_obj_set_style_text_color(pairingPopupMessage, lv_color_hex(0xc3ccd8), 0);
  lv_obj_set_style_text_font(pairingPopupMessage, fontForSize(18), 0);
  lv_obj_set_style_text_align(pairingPopupMessage, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_align(pairingPopupMessage, LV_ALIGN_TOP_MID, 0, 42);
  lv_obj_add_flag(pairingPopup, LV_OBJ_FLAG_HIDDEN);

  forgetConfirmPopup = lv_obj_create(screen);
  lv_obj_set_size(forgetConfirmPopup, 320, 184);
  lv_obj_align(forgetConfirmPopup, LV_ALIGN_CENTER, 0, 20);
  lv_obj_set_style_radius(forgetConfirmPopup, 8, 0);
  lv_obj_set_style_bg_color(forgetConfirmPopup, lv_color_hex(0x111827), 0);
  lv_obj_set_style_bg_opa(forgetConfirmPopup, LV_OPA_COVER, 0);
  lv_obj_set_style_border_color(forgetConfirmPopup, lv_color_hex(0xd71920), 0);
  lv_obj_set_style_border_width(forgetConfirmPopup, 2, 0);
  lv_obj_set_style_pad_all(forgetConfirmPopup, 16, 0);
  lv_obj_clear_flag(forgetConfirmPopup, LV_OBJ_FLAG_SCROLLABLE);

  lv_obj_t *forgetTitle = lv_label_create(forgetConfirmPopup);
  lv_obj_set_width(forgetTitle, 288);
  lv_label_set_text(forgetTitle, "Forget Camera?");
  lv_obj_set_style_text_color(forgetTitle, lv_color_hex(0xf4f7fb), 0);
  lv_obj_set_style_text_font(forgetTitle, fontForSize(20), 0);
  lv_obj_set_style_text_align(forgetTitle, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_align(forgetTitle, LV_ALIGN_TOP_MID, 0, 0);

  lv_obj_t *forgetMessage = lv_label_create(forgetConfirmPopup);
  lv_obj_set_width(forgetMessage, 288);
  lv_label_set_long_mode(forgetMessage, LV_LABEL_LONG_WRAP);
  lv_label_set_text(forgetMessage, "This clears the saved BLE camera and local bond data.");
  lv_obj_set_style_text_color(forgetMessage, lv_color_hex(0xc3ccd8), 0);
  lv_obj_set_style_text_font(forgetMessage, fontForSize(18), 0);
  lv_obj_set_style_text_align(forgetMessage, LV_TEXT_ALIGN_CENTER, 0);
  lv_obj_align(forgetMessage, LV_ALIGN_TOP_MID, 0, 42);

  lv_obj_t *forgetCancel = makeChip(forgetConfirmPopup, "Cancel", 10, 104, 128,
                                    lv_color_hex(0x334155));
  lv_obj_add_event_cb(forgetCancel, onForgetCancel, LV_EVENT_CLICKED, nullptr);
  lv_obj_t *forgetConfirm = makeChip(forgetConfirmPopup, "Forget", 150, 104, 128,
                                     lv_color_hex(0x7f1d1d));
  lv_obj_add_event_cb(forgetConfirm, onForgetConfirm, LV_EVENT_CLICKED, nullptr);
  lv_obj_add_flag(forgetConfirmPopup, LV_OBJ_FLAG_HIDDEN);
}

void updateWifiStatus() {
  static wl_status_t lastStatus = WL_NO_SHIELD;
  wl_status_t status = WiFi.status();
  if (status == lastStatus) {
    return;
  }
  lastStatus = status;
  if (status == WL_CONNECTED) {
    String text = "WiFi: ";
    text += WiFi.localIP().toString();
    lv_label_set_text(wifiLabel, text.c_str());
    lv_label_set_text(statusLabel, "GoPro WiFi connected");
    lv_label_set_text(wifiIndicator, LV_SYMBOL_WIFI);
    lv_obj_set_style_text_color(wifiIndicator, lv_color_hex(0x47d16c), 0);
    if (isLikelyGoProWifiConnected()) {
      setHomeCameraConnected(true);
    }
  } else if (status == WL_IDLE_STATUS) {
    lv_label_set_text(wifiLabel, "WiFi: connecting");
    lv_label_set_text(wifiIndicator, LV_SYMBOL_WIFI);
    lv_obj_set_style_text_color(wifiIndicator, lv_color_hex(0xf0b429), 0);
  } else {
    previewStreamRequested = false;
    snapshotPreviewPrepared = false;
    if (previewUdpListening) {
      previewUdp.stop();
      previewUdpListening = false;
    }
    lv_label_set_text(wifiLabel,
                      (recording && goProWifiSuspendedForRecording)
                          ? "WiFi: recording off"
                          : "WiFi: disconnected");
    lv_label_set_text(wifiIndicator, LV_SYMBOL_WIFI);
    lv_obj_set_style_text_color(wifiIndicator, lv_color_hex(0x5a6472), 0);
    setHomeCameraConnected(recording && bleConnected);
  }
}

void updatePreview(bool force) {
  if (!displayOn) {
    if (force) {
      Serial.println("Preview skipped: display off");
    }
    return;
  }
  if (recording) {
    if (force) {
      Serial.println("Preview skipped: recording");
    }
    return;
  }
  if (!force && !isCaptureTileActive()) {
    return;
  }
  if (!force && millis() - lastPreviewUpdate < kPreviewRefreshMs) {
    return;
  }
  lastPreviewUpdate = millis();
  Serial.printf("Preview update force=%u wifi=%u\n", force ? 1 : 0, WiFi.status());

  if (previewHasImage) {
    lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    return;
  }

  if (WiFi.status() != WL_CONNECTED) {
    lv_label_set_text(previewLabel, "Connect WiFi for preview");
    if (force) {
      Serial.println("Preview skipped: WiFi not connected");
    }
    return;
  }

  lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
  lv_label_set_text(previewLabel, "Double-click lower for snapshot");
}
