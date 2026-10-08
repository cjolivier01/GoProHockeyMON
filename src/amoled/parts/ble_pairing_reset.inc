// Pairing may select a different camera, so dispose of the framework-owned
// client and its GATT cache instead of losing its non-owning application handle.
void resetBleClientForPairing() {
  shutdownBleForWifi();
  bleClient = nullptr;
  bleConnected = false;
  if (bleIndicator) {
    lv_obj_set_style_text_color(bleIndicator, lv_color_hex(0x5a6472), 0);
  }
  clearBleScanDevices();
}

void disconnectCurrentCameraForPairing() {
  setAction("Disconnecting current camera");
  setHomeCameraConnected(false);
  previewStreamRequested = false;
  previewUdpListening = false;
  snapshotPreviewPrepared = false;
  previewUdp.stop();

  resetBleClientForPairing();

  if (WiFi.getMode() != WIFI_MODE_NULL || WiFi.status() == WL_CONNECTED) {
    WiFi.disconnect(true, true);
    WiFi.mode(WIFI_OFF);
    delay(250);
  }
  if (wifiLabel) {
    lv_label_set_text(wifiLabel, "WiFi: disconnected");
  }
  if (wifiIndicator) {
    lv_label_set_text(wifiIndicator, LV_SYMBOL_WIFI);
    lv_obj_set_style_text_color(wifiIndicator, lv_color_hex(0x5a6472), 0);
  }
}
