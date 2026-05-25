bool initPowerExpander() {
  if (!expander.begin(0x20, &Wire)) {
    Serial.println("XCA9554 expander not found");
    return false;
  }

  const uint8_t rails[] = {0, 1, 2, 6};
  for (uint8_t pin : rails) {
    expander.pinMode(pin, OUTPUT);
    expander.digitalWrite(pin, LOW);
  }
  delay(20);
  for (uint8_t pin : rails) {
    expander.digitalWrite(pin, HIGH);
  }
  delay(120);

  expander.pinMode(kExpanderActionButtonPin, INPUT);
  expander.pinMode(4, INPUT);
  return true;
}

void initPowerKey() {
  pmuOnline = power.begin(Wire, AXP2101_SLAVE_ADDRESS, IIC_SDA, IIC_SCL);
  if (!pmuOnline) {
    Serial.println("AXP2101 PMU not found; battery/shutdown disabled");
    return;
  }

  power.disableIRQ(XPOWERS_AXP2101_ALL_IRQ);
  power.clearIrqStatus();
  power.setPowerKeyPressOnTime(XPOWERS_POWERON_1S);
  power.setPowerKeyPressOffTime(XPOWERS_POWEROFF_4S);
  power.setLongPressPowerOFF();
  power.enableLongPressShutdown();
  power.enableIRQ(XPOWERS_AXP2101_PKEY_SHORT_IRQ);
  power.enableBattDetection();
  power.enableBattVoltageMeasure();
  power.enableVbusVoltageMeasure();
  Serial.println("AXP2101 PMU initialized; lower/action key IRQs enabled");
}

void handleBootButtonRelease(uint32_t durationMs, bool pressStartedRecording) {
  if (durationMs < kActionButtonMinPressMs) {
    return;
  }
  if (pairingUiActive()) {
    Serial.println("Top button ignored during Pair New");
    return;
  }
  if (pressStartedRecording) {
    if (!recording) {
      Serial.println("Top button release ignored; recording already stopped");
      return;
    }
    if (durationMs < kBootLongPressMs) {
      Serial.println("Top button: hold to stop recording");
      setAction("Hold top button to stop recording");
      return;
    }
    Serial.println("Top button: long stop recording on release fallback");
    if (goproActionBusy) {
      setAction("GoPro action already running");
      return;
    }
    blinkTopRightButtonMarker();
    runRecordAction();
    return;
  }
  if (recording && durationMs < kBootLongPressMs) {
    Serial.println("Top button: hold to stop recording");
    setAction("Hold top button to stop recording");
    return;
  }
  Serial.println(recording ? "Top button: long stop recording" : "Top button: start recording");
  runRecordAction();
}

void handleBootButtonHold(uint32_t now) {
  if (bootPressedAtMs == 0 || bootLongHandled || bootStable != LOW) {
    return;
  }
  if (now - bootPressedAtMs < kBootLongPressMs) {
    return;
  }
  if (pairingUiActive()) {
    Serial.println("Top button hold ignored during Pair New");
    bootLongHandled = true;
    return;
  }
  if (!bootPressStartedRecording) {
    return;
  }
  if (!recording) {
    Serial.println("Top button hold ignored; recording already stopped");
    return;
  }
  if (goproActionBusy) {
    return;
  }
  Serial.println("Top button: long stop recording threshold reached");
  blinkTopRightButtonMarker();
  bootLongHandled = runRecordAction();
}

void clearPendingLowerClick() {
  actionButtonShortClickCount = 0;
  actionButtonShortClickDueMs = 0;
}

void runLowerSingleClickAction(const char *source) {
  if (lowerButtonSuppressed() || goproActionBusy) {
    Serial.printf("%s single click ignored after recent/busy action\n",
                  source == nullptr ? "Lower button" : source);
    return;
  }
  if (exitFullscreenPreview(source == nullptr ? "Lower button" : source)) {
    suppressLowerButtonDuplicates(kPreviewExitButtonSuppressMs, "preview exit");
    return;
  }
  Serial.printf("%s single click: display toggle\n",
                source == nullptr ? "Lower button" : source);
  setDisplayOn(!displayOn);
}

void handleLowerActionShortClick(const char *source) {
  if (pairingUiActive()) {
    requestPairingCancel();
    return;
  }
  if (!displayOn) {
    setDisplayOn(true);
    return;
  }
  if (lowerButtonSuppressed()) {
    consumeActionButtonPress();
    Serial.printf("%s short click ignored after recent action\n",
                  source == nullptr ? "Lower button" : source);
    return;
  }
  if (goproActionBusy) {
    consumeActionButtonPress();
    Serial.printf("%s short click ignored while GoPro action is busy\n",
                  source == nullptr ? "Lower button" : source);
    return;
  }
  if (exitFullscreenPreview(source)) {
    clearPendingLowerClick();
    suppressLowerButtonDuplicates(kPreviewExitButtonSuppressMs, "preview exit");
    return;
  }
  if (isMaintenancePageShowing() || isButtonGuidePageShowing()) {
    clearPendingLowerClick();
    Serial.printf("%s single click: return to preview\n", source);
    closeSidePages();
    return;
  }

  uint32_t now = millis();
  if (actionButtonShortClickCount == 1 && actionButtonShortClickDueMs != 0 &&
      static_cast<int32_t>(actionButtonShortClickDueMs - now) >= 0) {
    clearPendingLowerClick();
    if (!displayOn) {
      setDisplayOn(true);
      return;
    }
    if (recording) {
      setAction("Snapshot disabled while recording");
      return;
    }
    Serial.printf("%s double click: snapshot\n", source);
    runSnapshotAction();
    return;
  }

  actionButtonShortClickCount = 1;
  actionButtonShortClickDueMs = now + kActionButtonDoubleClickMs;
  Serial.printf("%s single click pending for %u ms\n", source,
                static_cast<unsigned>(kActionButtonDoubleClickMs));
}

void handleLowerActionLongPress(const char *source) {
  actionButtonShortClickCount = 0;
  actionButtonShortClickDueMs = 0;
  if (pairingUiActive()) {
    requestPairingCancel();
    return;
  }
  Serial.printf("%s long press: low-power shutdown\n", source);
  enterLowPowerShutdown();
}

void clearDuplicatePmuActionIrq(const char *source) {
  if (!pmuOnline) {
    return;
  }
  power.getIrqStatus();
  bool shortPress = power.isPekeyShortPressIrq();
  bool longPress = power.isPekeyLongPressIrq();
  power.clearIrqStatus();
  if (shortPress || longPress) {
    lastPmuActionHandledMs = millis();
    Serial.printf("Cleared duplicate PMU action IRQ after %s short=%u long=%u\n",
                  source == nullptr ? "expander button" : source,
                  shortPress ? 1 : 0, longPress ? 1 : 0);
  }
}

void handleActionButtonRelease(uint32_t durationMs) {
  if (actionButtonLongHandled) {
    return;
  }
  if (durationMs < kActionButtonMinPressMs) {
    return;
  }
  if (happenedRecently(lastPmuActionHandledMs, kPmuDuplicateSuppressMs)) {
    Serial.println("Expander lower/action release ignored after PMU event");
    return;
  }
  lastExpanderActionHandledMs = millis();
  handleLowerActionShortClick("Lower button");
  lastExpanderActionHandledMs = millis();
  clearDuplicatePmuActionIrq("lower release");
}

void handlePendingActionButtonClick() {
  if (actionButtonShortClickCount == 1 && actionButtonShortClickDueMs != 0 &&
      millis() >= actionButtonShortClickDueMs) {
    clearPendingLowerClick();
    runLowerSingleClickAction("Lower button");
  }
}

void handleBootButton() {
  bool reading = digitalRead(kBootButtonPin);
  uint32_t now = millis();

  if (reading != bootLast) {
    bootLastChangeMs = now;
    bootLast = reading;
  }

  if ((now - bootLastChangeMs) < kButtonDebounceMs || reading == bootStable) {
    handleBootButtonHold(now);
    return;
  }

  bootStable = reading;
  if (bootStable == LOW) {
    bootPressedAtMs = now;
    bootLongHandled = false;
    bootPressStartedRecording = recording;
    if (!displayOn) {
      Serial.println("Top button press: display wake");
      setDisplayOn(true);
    }
  } else if (bootPressedAtMs != 0) {
    if (!bootLongHandled) {
      handleBootButtonRelease(now - bootPressedAtMs, bootPressStartedRecording);
    }
    bootPressedAtMs = 0;
    bootLongHandled = false;
    bootPressStartedRecording = false;
  }
}

void handleExpanderActionButton() {
  if (!expanderOnline) {
    return;
  }

  bool reading = expander.digitalRead(kExpanderActionButtonPin);
  uint32_t now = millis();

  if (reading != actionButtonLast) {
    actionButtonLastChangeMs = now;
    actionButtonLast = reading;
  }

  if ((now - actionButtonLastChangeMs) < kActionButtonDebounceMs || reading == actionButtonStable) {
    return;
  }

  actionButtonStable = reading;
  if (actionButtonStable == kExpanderActionPressedLevel) {
    if (pairingUiActive()) {
      requestPairingCancel();
      return;
    }
    actionButtonPressedAtMs = now;
    actionButtonLongHandled = false;
  } else if (actionButtonPressedAtMs != 0) {
    handleActionButtonRelease(now - actionButtonPressedAtMs);
    actionButtonPressedAtMs = 0;
  }
}

void handleActionButtonHold() {
  if (!expanderOnline || actionButtonPressedAtMs == 0 || actionButtonLongHandled ||
      actionButtonStable != kExpanderActionPressedLevel) {
    return;
  }
  if (millis() - actionButtonPressedAtMs < kActionButtonLongPressMs) {
    return;
  }
  actionButtonLongHandled = true;
  if (happenedRecently(lastPmuActionHandledMs, kPmuDuplicateSuppressMs)) {
    Serial.println("Expander lower/action hold ignored after PMU event");
    return;
  }
  lastExpanderActionHandledMs = millis();
  handleLowerActionLongPress("Lower button");
  lastExpanderActionHandledMs = millis();
  clearDuplicatePmuActionIrq("lower hold");
}

void handlePmuActionButton() {
  if (!pmuOnline || millis() - lastPmuPollMs < kPmuPollMs) {
    return;
  }

  lastPmuPollMs = millis();
  power.getIrqStatus();
  bool shortPress = power.isPekeyShortPressIrq();
  bool longPress = power.isPekeyLongPressIrq();
  if (!shortPress && !longPress) {
    power.clearIrqStatus();
    return;
  }

  power.clearIrqStatus();
  if (longPress) {
    Serial.println("PMU lower/action long IRQ ignored; PMU handles hardware shutdown");
    return;
  }
  if (happenedRecently(lastExpanderActionHandledMs, kPmuDuplicateSuppressMs)) {
    Serial.println("PMU lower/action IRQ ignored after expander event");
    return;
  }
  if (shortPress) {
    lastPmuActionHandledMs = millis();
    Serial.println("PMU lower/action short IRQ");
    handleLowerActionShortClick("Lower PMU button");
  }
}

void handleExpanderDiagnostics() {
  if (!expanderOnline) {
    return;
  }
  bool pin = expander.digitalRead(kExpanderActionButtonPin);
  if (pin != expanderActionPinLast) {
    expanderActionPinLast = pin;
    Serial.printf("Action pin p%u=%u\n", kExpanderActionButtonPin, pin);
  }
}

void handlePendingHomeAction() {
  PendingHomeAction action = pendingHomeAction;
  if (action == PendingHomeAction::None) {
    return;
  }
  if (goproActionBusy) {
    pendingHomeAction = PendingHomeAction::None;
    return;
  }
  if (millis() < pendingHomeActionDueMs) {
    return;
  }
  pendingHomeAction = PendingHomeAction::None;
  pendingHomeActionDueMs = 0;
  lv_timer_handler();
  switch (action) {
    case PendingHomeAction::Connect:
      Serial.println("Raw touch fallback: Connect");
      runConnectAction();
      break;
    case PendingHomeAction::Pair:
      Serial.println("Raw touch fallback: Pair");
      runPairNewAction();
      break;
    case PendingHomeAction::None:
      break;
  }
}

void handlePairingPopupTimeout() {
  if (pairingPopupHideDueMs != 0 && millis() >= pairingPopupHideDueMs) {
    hidePairingPopup();
  }
}

size_t splitSerialCommand(String line, String tokens[], size_t maxTokens) {
  line.trim();
  size_t count = 0;
  while (line.length() > 0 && count < maxTokens) {
    int space = line.indexOf(' ');
    if (space < 0) {
      tokens[count++] = line;
      break;
    }
    if (space > 0) {
      tokens[count++] = line.substring(0, space);
    }
    line = line.substring(space + 1);
    line.trim();
  }
  for (size_t i = 0; i < count; ++i) {
    tokens[i].toLowerCase();
  }
  return count;
}

bool parseSerialInt(const String &token, int &value) {
  if (token.isEmpty()) {
    return false;
  }
  char *end = nullptr;
  long parsed = strtol(token.c_str(), &end, 10);
  if (end == token.c_str() || *end != '\0') {
    return false;
  }
  value = static_cast<int>(parsed);
  return true;
}

void printSerialHelp() {
  Serial.println("Serial UI test commands:");
  Serial.println("  help");
  Serial.println("  status");
  Serial.println("  touch X Y [hold_ms]");
  Serial.println("  swipe X1 Y1 X2 Y2 [duration_ms]");
  Serial.println("  lower [single|double|shutdown]");
  Serial.println("  top [short|long]");
  Serial.println("  pair | cancel | connect | rescan | snapshot | record");
  Serial.println("  page home|maintenance|buttons");
  Serial.println("  fullscreen on|off");
  Serial.println("  forget show|confirm|cancel");
  Serial.println("  display on|off");
}

void printSerialStatus() {
  String ssid = WiFi.SSID();
  String ip = WiFi.localIP().toString();
  Serial.println("SERIAL STATUS");
  Serial.printf("  displayOn=%u recording=%u fullscreen=%u maintenance=%u buttons=%u previewImage=%u\n",
                displayOn ? 1 : 0, recording ? 1 : 0, previewFullscreen ? 1 : 0,
                maintenancePageVisible ? 1 : 0, buttonGuidePageVisible ? 1 : 0,
                previewHasImage ? 1 : 0);
  Serial.printf("  pairingInProgress=%u pairingCancel=%u pendingHome=%u busy=%u\n",
                pairingInProgress ? 1 : 0, pairingCancelRequested ? 1 : 0,
                static_cast<unsigned>(pendingHomeAction), goproActionBusy ? 1 : 0);
  Serial.printf("  bleConnected=%u bound='%s' boundName='%s' lastName='%s' retry=%u homeConnected=%u\n",
                bleConnected ? 1 : 0, boundBleAddress.c_str(), boundBleName.c_str(),
                lastBleName.c_str(), connectRetryAvailable ? 1 : 0,
                homeCameraConnected ? 1 : 0);
  Serial.printf("  wifiStatus=%u ssid='%s' ip=%s goproSsid='%s' passLen=%u boundAp='%s' channel=%d bssid=%s likelyGoPro=%u\n",
                static_cast<unsigned>(WiFi.status()), ssid.c_str(), ip.c_str(),
                goProSsid.c_str(), static_cast<unsigned>(goProPassword.length()),
                boundGoProSsid.c_str(), static_cast<int>(goProWifiChannel),
                goProWifiBssidValid ? formatBssid(goProWifiBssid).c_str() : "(none)",
                isLikelyGoProWifiConnected() ? 1 : 0);
  Serial.printf("  wifiSuspendedForRecording=%u\n", goProWifiSuspendedForRecording ? 1 : 0);
  Serial.printf("  goproBattery=%d plugged=%u\n", goProBatteryPercent,
                goProBatteryChargingOrPlugged ? 1 : 0);
  Serial.printf("  capture='%s' setting='%s' actionClicks=%u due=%u\n",
                captureMode.c_str(), captureSetting.c_str(), actionButtonShortClickCount,
                actionButtonShortClickDueMs);
  Serial.printf("  snapshotFrame valid=%u aspect=%u:%u aspectCrop=%u%% previewVisible=%u%% cameraVisible=%u%% lens=%d hs=%d crop=%d,%d %dx%d\n",
                snapshotVideoFraming.valid ? 1 : 0, snapshotVideoFraming.aspectW,
                snapshotVideoFraming.aspectH,
                static_cast<unsigned>(kSnapshotAspectCropStrengthPercent),
                static_cast<unsigned>(kSnapshotPreviewVisiblePercent),
                snapshotVideoFraming.visiblePercent,
                snapshotVideoFraming.lensOption, snapshotVideoFraming.hypersmoothOption,
                jpegCropX, jpegCropY, jpegCropW, jpegCropH);
}

void startSerialPointer(int x1, int y1, int x2, int y2, uint32_t durationMs) {
  if (x1 < 0 || x1 >= LCD_WIDTH || x2 < 0 || x2 >= LCD_WIDTH ||
      y1 < 0 || y1 >= LCD_HEIGHT || y2 < 0 || y2 >= LCD_HEIGHT) {
    Serial.printf("Serial pointer rejected: %d,%d -> %d,%d outside %dx%d\n",
                  x1, y1, x2, y2, LCD_WIDTH, LCD_HEIGHT);
    return;
  }
  if (durationMs < 50) {
    durationMs = 50;
  } else if (durationMs > 2500) {
    durationMs = 2500;
  }
  serialPointerStart = {static_cast<lv_coord_t>(x1), static_cast<lv_coord_t>(y1)};
  serialPointerEnd = {static_cast<lv_coord_t>(x2), static_cast<lv_coord_t>(y2)};
  serialPointerStartMs = millis();
  serialPointerDurationMs = durationMs;
  serialPointerActive = true;
  touchActive = false;
  rawSwipeHandled = false;
  Serial.printf("Serial pointer: %d,%d -> %d,%d over %u ms\n",
                x1, y1, x2, y2, durationMs);
}

bool serialActionBlocked(const String &command) {
  if (!goproActionBusy) {
    return false;
  }
  Serial.print("Serial command ignored while GoPro action is busy: ");
  Serial.println(command);
  return true;
}

void handleSerialCommand(String line) {
  line.trim();
  if (line.isEmpty()) {
    return;
  }

  String tokens[8];
  size_t count = splitSerialCommand(line, tokens, 8);
  if (count == 0) {
    return;
  }

  const String &cmd = tokens[0];
  if (cmd == "help" || cmd == "?") {
    printSerialHelp();
    return;
  }
  if (cmd == "status") {
    printSerialStatus();
    return;
  }
  if (cmd == "touch") {
    if (count < 3) {
      Serial.println("usage: touch X Y [hold_ms]");
      return;
    }
    int x = 0;
    int y = 0;
    int hold = 120;
    if (!parseSerialInt(tokens[1], x) || !parseSerialInt(tokens[2], y) ||
        (count >= 4 && !parseSerialInt(tokens[3], hold))) {
      Serial.println("touch requires numeric coordinates");
      return;
    }
    startSerialPointer(x, y, x, y, static_cast<uint32_t>(hold));
    return;
  }
  if (cmd == "swipe") {
    if (count < 5) {
      Serial.println("usage: swipe X1 Y1 X2 Y2 [duration_ms]");
      return;
    }
    int x1 = 0;
    int y1 = 0;
    int x2 = 0;
    int y2 = 0;
    int duration = 350;
    if (!parseSerialInt(tokens[1], x1) || !parseSerialInt(tokens[2], y1) ||
        !parseSerialInt(tokens[3], x2) || !parseSerialInt(tokens[4], y2) ||
        (count >= 6 && !parseSerialInt(tokens[5], duration))) {
      Serial.println("swipe requires numeric coordinates");
      return;
    }
    startSerialPointer(x1, y1, x2, y2, static_cast<uint32_t>(duration));
    return;
  }
  if (cmd == "lower") {
    String mode = count >= 2 ? tokens[1] : "single";
    if (mode == "single" || mode == "short") {
      Serial.println("Serial lower single");
      handleLowerActionShortClick("Serial lower");
    } else if (mode == "double") {
      Serial.println("Serial lower double");
      handleLowerActionShortClick("Serial lower");
      handleLowerActionShortClick("Serial lower");
    } else if (mode == "long") {
      Serial.println("Serial lower long ignored; use 'lower shutdown' to test shutdown");
    } else if (mode == "shutdown") {
      handleLowerActionLongPress("Serial lower");
    } else {
      Serial.println("usage: lower [single|double|shutdown]");
    }
    return;
  }
  if (cmd == "top") {
    String mode = count >= 2 ? tokens[1] : "short";
    if (!displayOn) {
      Serial.println("Serial top press: display wake");
      setDisplayOn(true);
    }
    if (mode == "short" || mode == "single") {
      handleBootButtonRelease(kActionButtonMinPressMs + 40, recording);
    } else if (mode == "long") {
      handleBootButtonRelease(kBootLongPressMs + 100, recording);
    } else {
      Serial.println("usage: top [short|long]");
    }
    return;
  }
  if (cmd == "cancel") {
    if (pairingUiActive()) {
      requestPairingCancel();
    } else if (goproActionBusy) {
      requestConnectionCancel("Serial cancel");
    } else {
      hidePairingPopup();
      hideForgetConfirm();
      setAction("Serial cancel");
    }
    return;
  }
  if (cmd == "pair") {
    if (!serialActionBlocked(cmd)) {
      queuePairNewAction("serial");
    }
    return;
  }
  if (cmd == "connect" || cmd == "rescan") {
    if (!serialActionBlocked(cmd)) {
      runConnectAction();
    }
    return;
  }
  if (cmd == "snapshot") {
    if (!serialActionBlocked(cmd)) {
      runSnapshotAction();
    }
    return;
  }
  if (cmd == "record") {
    if (!serialActionBlocked(cmd)) {
      runRecordAction();
    }
    return;
  }
  if (cmd == "page") {
    if (count < 2) {
      Serial.println("usage: page home|maintenance|buttons");
      return;
    }
    if (tokens[1] == "home") {
      closeSidePages();
    } else if (tokens[1] == "maintenance") {
      setMaintenancePageVisible(true);
    } else if (tokens[1] == "buttons" || tokens[1] == "button" || tokens[1] == "guide") {
      setButtonGuidePageVisible(true);
    } else {
      Serial.println("usage: page home|maintenance|buttons");
    }
    return;
  }
  if (cmd == "fullscreen") {
    if (count < 2) {
      Serial.println("usage: fullscreen on|off");
      return;
    }
    if (tokens[1] == "on") {
      setPreviewFullscreen(true);
    } else if (tokens[1] == "off") {
      setPreviewFullscreen(false);
    } else {
      Serial.println("usage: fullscreen on|off");
    }
    return;
  }
  if (cmd == "forget") {
    String mode = count >= 2 ? tokens[1] : "show";
    if (mode == "show") {
      showForgetConfirm();
    } else if (mode == "confirm") {
      onForgetConfirm(nullptr);
    } else if (mode == "cancel") {
      onForgetCancel(nullptr);
    } else {
      Serial.println("usage: forget show|confirm|cancel");
    }
    return;
  }
  if (cmd == "display") {
    if (count < 2) {
      Serial.println("usage: display on|off");
      return;
    }
    if (tokens[1] == "on") {
      setDisplayOn(true);
    } else if (tokens[1] == "off") {
      setDisplayOn(false);
    } else {
      Serial.println("usage: display on|off");
    }
    return;
  }

  Serial.print("Unknown serial command: ");
  Serial.println(line);
  printSerialHelp();
}

void handleSerialCommands() {
  while (Serial.available() > 0) {
    char ch = static_cast<char>(Serial.read());
    if (ch == '\r') {
      continue;
    }
    if (ch == '\n') {
      String line = serialCommandLine;
      serialCommandLine = "";
      handleSerialCommand(line);
    } else if (serialCommandLine.length() < 160) {
      serialCommandLine += ch;
    } else {
      serialCommandLine = "";
      Serial.println("Serial command too long; dropped");
    }
  }
}
