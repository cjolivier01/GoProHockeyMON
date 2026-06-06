#pragma once

#include <Arduino.h>
#include <JPEGDEC.h>
#include <WiFi.h>
#include <lvgl.h>

#include "esp_heap_caps.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#if !defined(GOPRO_AMOLED_MAIN_CONTEXT)
#include "amoled_context_decls.h"
#endif

void setPairingMode() {
  if (!displayOn) {
    setDisplayOn(true);
  }
  bool ok = pairGoPro();
  setAction(ok ? "GoPro BLE pairing requested"
               : (pairingLastCancelled ? "Pairing cancelled" : "GoPro BLE pairing failed"));
  if (ok) {
    delay(300);
    setAction("Pair complete; connecting WiFi");
    showPairingPopup("Pairing Complete\n\nConnecting camera WiFi...");
    bool wifiOk = connectGoProWifiFromBle();
    finishPairingPopup(wifiOk ? "Pairing Complete\n\nCamera connected."
                              : "Pairing Complete\n\nWiFi connect failed.");
  }
}

bool beginGoproAction(const char *name) {
  if (goproActionBusy) {
    setAction("GoPro action already running");
    return false;
  }
  goproActionBusy = true;
  connectionCancelRequested = false;
  pendingHomeAction = PendingHomeAction::None;
  pendingHomeActionDueMs = 0;
  Serial.print(F("Action start: "));
  Serial.println(name);
  return true;
}

void endGoproAction() {
  goproActionBusy = false;
}

void runConnectAction() {
  if (!beginGoproAction("connect")) {
    return;
  }
  setHomeCameraConnected(false);
  setConnectRetryAvailable(false);
  serviceLvgl();
  bool ok = connectGoProWifiFromBle();
  if (!ok && !boundBleAddress.isEmpty() && !allowAnyCameraScan && !operationCancelled()) {
    setConnectRetryAvailable(true);
  }
  endGoproAction();
}

void runPairNewAction() {
  if (!beginGoproAction("pair-new")) {
    return;
  }
  setAction("Pair New");
  serviceLvgl();
  delay(100);
  setPairingMode();
  endGoproAction();
}

void runForgetCameraAction() {
  if (recording) {
    setAction("Stop recording before forgetting");
    return;
  }
  if (!beginGoproAction("forget-camera")) {
    return;
  }
  setAction("Forgetting saved camera");
  serviceLvgl();
  delay(100);
  forgetCameraBinding();
  endGoproAction();
}

void runWakeCameraAction() {
  if (recording) {
    setAction("Stop recording before wake");
    return;
  }
  if (!beginGoproAction("wake-camera")) {
    return;
  }
  setHomeCameraConnected(false);
  setConnectRetryAvailable(false);
  cameraWakeInProgress = true;
  bool ok = wakeGoProBle();
  if (ok) {
    setAction("Wake sent; connecting");
    ok = delayWithConnectionUi(1500) && connectGoProWifiFromBle();
  }
  cameraWakeInProgress = false;
  if (!ok && !boundBleAddress.isEmpty() && !operationCancelled()) {
    bool retryWake = cameraWakeAvailable;
    setConnectRetryAvailable(true);
    if (retryWake) {
      setCameraWakeAvailable(true);
      setAction("Wake failed; tap ON again");
    } else {
      setAction("GoPro not found; scan again");
    }
  }
  endGoproAction();
}

bool runRecordAction() {
  if (!beginGoproAction("record")) {
    return false;
  }
  setAction("REC pressed");
  serviceLvgl();
  delay(100);
  bool ok = toggleRecording();
  endGoproAction();
  return ok;
}

void runSnapshotAction() {
  if (!beginGoproAction("snapshot")) {
    return;
  }
  if (!displayOn) {
    setDisplayOn(true);
  }
  if (recording) {
    setAction("Snapshot disabled while recording");
    endGoproAction();
    return;
  }
  setAction("Checking GoPro WiFi");
  if (!ensureGoProWifiReady("Taking snapshot over GoPro WiFi")) {
    setAction("Camera WiFi not connected");
    endGoproAction();
    return;
  }
  fetchSnapshotPreview();
  consumeActionButtonPress();
  clearDuplicatePmuActionIrq("snapshot complete");
  suppressLowerButtonDuplicates(900, "snapshot complete");
  if (!displayOn) {
    setDisplayOn(true);
  }
  endGoproAction();
}

bool toggleRecording() {
  if (!displayOn) {
    setDisplayOn(true);
  }
  bool nextRecording = !recording;
  lv_label_set_text(statusLabel, nextRecording ? "Starting recording" : "Stopping recording");
  bool ok = false;
  if (nextRecording) {
    bool wifiReady = isLikelyGoProWifiConnected();
    if (previewFullscreen) {
      setPreviewFullscreen(false);
    }
    if (previewLabel) {
      lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    }
    setAction("Starting recording");
    snapshotPreviewPrepared = false;
    if (wifiReady && httpGetGoPro("/gopro/camera/presets/set_group?id=1000")) {
      captureMode = "Video";
      syncCameraState();
    }

    if (wifiReady) {
      setAction("Starting recording over WiFi");
      ok = httpGetGoPro("/gopro/camera/shutter/start");
      if (!ok) {
        Serial.println("HTTP shutter start failed; trying BLE fallback");
        ok = setGoProShutterBle(true);
      }
    } else {
      ok = setGoProShutterBle(true);
    }
  } else {
    ok = setGoProShutterBle(false);
    if (!ok && isLikelyGoProWifiConnected()) {
      Serial.println("BLE shutter stop failed; trying HTTP fallback");
      ok = httpGetGoPro("/gopro/camera/shutter/stop");
    }
  }
  if (!ok) {
    lv_label_set_text(statusLabel, recording ? "Recording" : "Standby");
    setAction("Recording command failed");
    return false;
  }
  applyRecordingUiState(nextRecording, 0, nextRecording);
  if (recording) {
    blinkTopRightButtonMarker();
    suspendGoProWifiForRecording("recording started");
  } else {
    setAction("Recording stopped; WiFi idle");
  }
  return true;
}

bool beginLivePreviewUdp() {
  if (previewUdpListening) {
    return true;
  }
  previewUdp.stop();
  if (!previewUdp.begin(kPreviewStreamPort)) {
    Serial.println("Preview UDP bind failed");
    return false;
  }
  previewUdpListening = true;
  previewBytesThisWindow = 0;
  previewPacketsThisWindow = 0;
  lastPreviewStatsMs = millis();
  Serial.printf("Preview UDP listening on %u\n", kPreviewStreamPort);
  return true;
}

int startGoProStreamPath(const String &path, const char *stopPath, const char *label) {
  int status = httpGetGoProStatus(path);
  if (status == 409) {
    Serial.printf("%s already active; stopping stale stream\n", label);
    httpGetGoProStatus(stopPath);
    delay(500);
    status = httpGetGoProStatus(path);
  }
  Serial.printf("%s start status=%d path=%s\n", label, status, path.c_str());
  return status;
}

bool startGoProLivePreview() {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }
  if (!beginLivePreviewUdp()) {
    lv_label_set_text(previewLabel, "Preview UDP bind failed");
    return false;
  }
  if (previewStreamRequested) {
    return true;
  }

  h264StreamUnsupported = false;
  h264UnsupportedNotified = false;
  h264DecodeFailures = 0;
  h264FramesDecoded = 0;
  h264AccessUnitLen = 0;
  httpGetGoProStatus("/gopro/camera/stream/stop");
  httpGetGoProStatus("/gopro/webcam/stop");
  delay(300);

  String streamName = "GoPro webcam 480p";
  int status = startGoProStreamPath("/gopro/webcam/start?res=4&fov=0",
                                    "/gopro/webcam/stop", streamName.c_str());
  if (status < 200 || status >= 300) {
    streamName = "GoPro webcam 720p";
    status = startGoProStreamPath("/gopro/webcam/start?res=7&fov=0",
                                  "/gopro/webcam/stop", streamName.c_str());
  }
  if (status < 200 || status >= 300) {
    Serial.println("Webcam stream failed; falling back to preview stream");
    streamName = "GoPro preview";
    String path = "/gopro/camera/stream/start?port=";
    path += kPreviewStreamPort;
    status = startGoProStreamPath(path, "/gopro/camera/stream/stop", streamName.c_str());
  }
  bool ok = status >= 200 && status < 300;
  previewStreamRequested = ok;
  if (ok) {
    lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    String label = streamName + " starting";
    lv_label_set_text(previewLabel, label.c_str());
    setPreviewFullscreen(true);
    String action = streamName + " started";
    setAction(action.c_str());
  } else {
    lv_label_set_text(previewLabel, "Preview start failed");
  }
  return ok;
}

void pollLivePreviewUdp() {
  if (!previewUdpListening) {
    return;
  }

  for (uint8_t packets = 0; packets < 12; ++packets) {
    int packetSize = previewUdp.parsePacket();
    if (packetSize <= 0) {
      break;
    }
    previewPacketsThisWindow++;
    previewBytesThisWindow += static_cast<uint32_t>(packetSize);
    while (packetSize > 0) {
      uint8_t scratch[kTsPacketBytes];
      int toRead = min(packetSize, static_cast<int>(sizeof(scratch)));
      int readLen = previewUdp.read(scratch, toRead);
      if (readLen <= 0) {
        break;
      }
      if (readLen == static_cast<int>(kTsPacketBytes)) {
        processTsPacket(scratch);
      }
      packetSize -= readLen;
    }
  }

  if (millis() - lastPreviewStatsMs < kLivePreviewStatsMs) {
    return;
  }

  uint32_t elapsed = max<uint32_t>(1, millis() - lastPreviewStatsMs);
  uint32_t kbps = (previewBytesThisWindow * 8UL) / elapsed;
  lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
  if (h264StreamUnsupported) {
    lv_label_set_text(previewLabel, "Stream connected\nHost decoder required");
  } else {
    const char *label = previewPacketsThisWindow > 0
                            ? "GoPro preview\ntrying decoder"
                            : "GoPro preview\nwaiting for packets";
    lv_label_set_text(previewLabel, label);
  }
  Serial.printf("Preview UDP: %u packets, %u bytes, %u kbps\n", previewPacketsThisWindow,
                previewBytesThisWindow, kbps);
  previewBytesThisWindow = 0;
  previewPacketsThisWindow = 0;
  lastPreviewStatsMs = millis();
}

bool isCaptureTileActive() {
  if (previewFullscreen || tileView == nullptr || captureTileObj == nullptr) {
    return true;
  }
  lv_obj_t *activeTile = lv_tileview_get_tile_act(tileView);
  return activeTile == nullptr || activeTile == captureTileObj;
}

int jpegScaleDivisor(int scale) {
  if (scale == JPEG_SCALE_EIGHTH) {
    return 8;
  }
  if (scale == JPEG_SCALE_QUARTER) {
    return 4;
  }
  if (scale == JPEG_SCALE_HALF) {
    return 2;
  }
  return 1;
}

int jpegScaledDim(int dim, int scale) {
  return max(1, dim / jpegScaleDivisor(scale));
}

void computeJpegContainRect(int imageW, int imageH, int frameX, int frameY, int frameW, int frameH,
                            int &outX, int &outY, int &outW, int &outH) {
  if (imageW <= 0 || imageH <= 0 || frameW <= 0 || frameH <= 0) {
    outX = frameX;
    outY = frameY;
    outW = max(1, frameW);
    outH = max(1, frameH);
    return;
  }

  int64_t widthLimitedH = (static_cast<int64_t>(frameW) * imageH + imageW / 2) / imageW;
  if (widthLimitedH <= frameH) {
    outW = frameW;
    outH = max(1, static_cast<int>(widthLimitedH));
  } else {
    int64_t heightLimitedW = (static_cast<int64_t>(frameH) * imageW + imageH / 2) / imageH;
    outW = max(1, static_cast<int>(heightLimitedW));
    outH = frameH;
  }

  outW = min(outW, frameW);
  outH = min(outH, frameH);
  outX = frameX + (frameW - outW) / 2;
  outY = frameY + (frameH - outH) / 2;
}

int chooseJpegContainDecodeScale(int width, int height, int targetW, int targetH) {
  const int scales[] = {JPEG_SCALE_EIGHTH, JPEG_SCALE_QUARTER, JPEG_SCALE_HALF, 0};
  for (int scale : scales) {
    if (jpegScaledDim(width, scale) >= targetW && jpegScaledDim(height, scale) >= targetH) {
      return scale;
    }
  }
  return 0;
}

void computeVideoFramedSourceRect(int imageW, int imageH, int &outX, int &outY, int &outW,
                                  int &outH) {
  outX = 0;
  outY = 0;
  outW = max(1, imageW);
  outH = max(1, imageH);
  if (imageW <= 0 || imageH <= 0 || !snapshotVideoFraming.valid ||
      snapshotVideoFraming.aspectW == 0 || snapshotVideoFraming.aspectH == 0) {
    return;
  }

  int cropW = imageW;
  int cropH = imageH;
  int64_t sourceScaled = static_cast<int64_t>(cropW) * snapshotVideoFraming.aspectH;
  int64_t targetScaled = static_cast<int64_t>(cropH) * snapshotVideoFraming.aspectW;
  if (sourceScaled > targetScaled) {
    cropW = max(1, static_cast<int>((static_cast<int64_t>(cropH) *
                                      snapshotVideoFraming.aspectW) /
                                     snapshotVideoFraming.aspectH));
  } else if (sourceScaled < targetScaled) {
    cropH = max(1, static_cast<int>((static_cast<int64_t>(cropW) *
                                      snapshotVideoFraming.aspectH) /
                                     snapshotVideoFraming.aspectW));
  }

  cropW = imageW - ((imageW - cropW) * kSnapshotAspectCropStrengthPercent) / 100;
  cropH = imageH - ((imageH - cropH) * kSnapshotAspectCropStrengthPercent) / 100;

  uint8_t visiblePercent = min<uint8_t>(
      constrain(snapshotVideoFraming.visiblePercent, 1, 100),
      constrain(snapshotVideoFraming.previewVisiblePercent, 1, 100));
  cropW = max(1, (cropW * visiblePercent) / 100);
  cropH = max(1, (cropH * visiblePercent) / 100);
  outW = min(cropW, imageW);
  outH = min(cropH, imageH);
  outX = max(0, (imageW - outW) / 2);
  outY = max(0, (imageH - outH) / 2);
}

void computeScaledJpegCrop(int sourceX, int sourceY, int sourceW, int sourceH, int scale) {
  int div = jpegScaleDivisor(scale);
  int cropX0 = sourceX / div;
  int cropY0 = sourceY / div;
  int cropX1 = (sourceX + sourceW + div - 1) / div;
  int cropY1 = (sourceY + sourceH + div - 1) / div;
  cropX0 = constrain(cropX0, 0, jpegDecodeW - 1);
  cropY0 = constrain(cropY0, 0, jpegDecodeH - 1);
  cropX1 = constrain(cropX1, cropX0 + 1, jpegDecodeW);
  cropY1 = constrain(cropY1, cropY0 + 1, jpegDecodeH);
  jpegCropX = cropX0;
  jpegCropY = cropY0;
  jpegCropW = cropX1 - cropX0;
  jpegCropH = cropY1 - cropY0;
}

bool ensurePreviewCanvasBuffer(int width, int height) {
  if (!previewImageCanvas || width <= 0 || height <= 0) {
    return false;
  }

  size_t requiredBytes = static_cast<size_t>(width) * static_cast<size_t>(height) *
                         sizeof(lv_color_t);
  if (!previewCanvasBuffer || previewCanvasBufferBytes < requiredBytes) {
    lv_color_t *newBuffer = static_cast<lv_color_t *>(
        heap_caps_malloc(requiredBytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    if (!newBuffer) {
      newBuffer = static_cast<lv_color_t *>(heap_caps_malloc(requiredBytes, MALLOC_CAP_8BIT));
    }
    if (!newBuffer) {
      Serial.printf("Preview canvas allocation failed: %dx%d %u bytes\n", width, height,
                    static_cast<unsigned>(requiredBytes));
      return false;
    }
    lv_color_t *oldBuffer = previewCanvasBuffer;
    previewCanvasBuffer = newBuffer;
    previewCanvasBufferBytes = requiredBytes;
    if (oldBuffer) {
      heap_caps_free(oldBuffer);
    }
    Serial.printf("Preview canvas allocated: %dx%d %u bytes\n", width, height,
                  static_cast<unsigned>(requiredBytes));
  }

  previewCanvasW = width;
  previewCanvasH = height;
  lv_canvas_set_buffer(previewImageCanvas, previewCanvasBuffer, width, height,
                       LV_IMG_CF_TRUE_COLOR);
  lv_obj_set_pos(previewImageCanvas, 0, 0);
  lv_obj_set_style_border_width(previewImageCanvas, 0, 0);
  lv_obj_set_style_pad_all(previewImageCanvas, 0, 0);
  lv_obj_clear_flag(previewImageCanvas, LV_OBJ_FLAG_HIDDEN);
  lv_canvas_fill_bg(previewImageCanvas, lv_color_black(), LV_OPA_COVER);
  return true;
}

int drawJpegBlock(JPEGDRAW *draw) {
  if (!isCaptureTileActive()) {
    return 0;
  }
  if (!draw || !draw->pPixels) {
    return 1;
  }

  int srcStride = draw->iWidth;
  int blockW = draw->iWidthUsed > 0 ? draw->iWidthUsed : draw->iWidth;
  int blockH = draw->iHeight;
  if (srcStride <= 0 || blockW <= 0 || blockH <= 0 ||
      jpegDecodeW <= 0 || jpegDecodeH <= 0 || jpegDrawW <= 0 || jpegDrawH <= 0 ||
      !previewCanvasBuffer || previewCanvasW <= 0 || previewCanvasH <= 0) {
    return 1;
  }

  int blockSrcX0 = draw->x;
  int blockSrcY0 = draw->y;
  int blockSrcX1 = blockSrcX0 + blockW;
  int blockSrcY1 = blockSrcY0 + blockH;
  int clipX0 = max(blockSrcX0, jpegCropX);
  int clipY0 = max(blockSrcY0, jpegCropY);
  int clipX1 = min(blockSrcX1, jpegCropX + jpegCropW);
  int clipY1 = min(blockSrcY1, jpegCropY + jpegCropH);
  if (clipX1 <= clipX0 || clipY1 <= clipY0) {
    return 1;
  }

  int destX0 = ((clipX0 - jpegCropX) * jpegDrawW) / jpegCropW;
  int destX1 = ((clipX1 - jpegCropX) * jpegDrawW + jpegCropW - 1) / jpegCropW;
  int destY0 = ((clipY0 - jpegCropY) * jpegDrawH) / jpegCropH;
  int destY1 = ((clipY1 - jpegCropY) * jpegDrawH + jpegCropH - 1) / jpegCropH;
  destX0 = max(0, min(destX0, jpegDrawW));
  destX1 = max(0, min(destX1, jpegDrawW));
  destY0 = max(0, min(destY0, jpegDrawH));
  destY1 = max(0, min(destY1, jpegDrawH));
  if (destX1 <= destX0 || destY1 <= destY0) {
    return 1;
  }

  for (int destY = destY0; destY < destY1; ++destY) {
    if ((destY & 0x0f) == 0) {
      yield();
    }
    int canvasY = jpegDrawY + destY;
    if (canvasY < 0 || canvasY >= previewCanvasH) {
      continue;
    }
    int srcY = jpegCropY + (destY * jpegCropH) / jpegDrawH - blockSrcY0;
    if (srcY < 0 || srcY >= blockH) {
      continue;
    }
    int lineLen = destX1 - destX0;
    for (int i = 0; i < lineLen; ++i) {
      int destX = destX0 + i;
      int canvasX = jpegDrawX + destX;
      if (canvasX < 0 || canvasX >= previewCanvasW) {
        continue;
      }
      int srcX = jpegCropX + (destX * jpegCropW) / jpegDrawW - blockSrcX0;
      if (srcX < 0) {
        srcX = 0;
      } else if (srcX >= blockW) {
        srcX = blockW - 1;
      }
      previewCanvasBuffer[canvasY * previewCanvasW + canvasX].full =
          draw->pPixels[srcY * srcStride + srcX];
    }
  }
  return 1;
}

bool drawJpegPreview(uint8_t *buffer, size_t length) {
  if (!isCaptureTileActive()) {
    Serial.printf("JPEG draw skipped: inactive tile active=%p capture=%p fullscreen=%u\n",
                  tileView ? lv_tileview_get_tile_act(tileView) : nullptr,
                  captureTileObj, previewFullscreen ? 1 : 0);
    return false;
  }
  if (!jpeg.openRAM(buffer, static_cast<int>(length), drawJpegBlock)) {
    Serial.printf("JPEG open failed: len=%u header=%02x %02x %02x %02x error=%d\n",
                  static_cast<unsigned>(length),
                  length > 0 ? buffer[0] : 0,
                  length > 1 ? buffer[1] : 0,
                  length > 2 ? buffer[2] : 0,
                  length > 3 ? buffer[3] : 0,
                  jpeg.getLastError());
    return false;
  }

  int frameX = 0;
  int frameY = 0;
  int frameW = previewFrameW();
  int frameH = previewFrameH();
  Serial.printf("JPEG opened: len=%u size=%dx%d type=%d bpp=%d subsample=%d\n",
                static_cast<unsigned>(length), jpeg.getWidth(), jpeg.getHeight(),
                jpeg.getJPEGType(), jpeg.getBpp(), jpeg.getSubSample());

  int sourceCropX = 0;
  int sourceCropY = 0;
  int sourceCropW = jpeg.getWidth();
  int sourceCropH = jpeg.getHeight();
  computeVideoFramedSourceRect(jpeg.getWidth(), jpeg.getHeight(), sourceCropX, sourceCropY,
                               sourceCropW, sourceCropH);

  computeJpegContainRect(sourceCropW, sourceCropH, frameX, frameY, frameW, frameH,
                         jpegDrawX, jpegDrawY, jpegDrawW, jpegDrawH);
  if (!ensurePreviewCanvasBuffer(frameW, frameH)) {
    jpeg.close();
    return false;
  }
  int scale = chooseJpegContainDecodeScale(sourceCropW, sourceCropH, jpegDrawW, jpegDrawH);
  jpegDecodeW = jpegScaledDim(jpeg.getWidth(), scale);
  jpegDecodeH = jpegScaledDim(jpeg.getHeight(), scale);
  computeScaledJpegCrop(sourceCropX, sourceCropY, sourceCropW, sourceCropH, scale);
  Serial.printf("JPEG video-frame contain: screen=%dx%d frame=%dx%d image=%dx%d "
                "sourceCrop=%d,%d %dx%d scale=%d decoded=%dx%d decodedCrop=%d,%d %dx%d "
                "out=%dx%d origin=%d,%d video=%u:%u cameraVisible=%u%% appliedVisible=%u%%\n",
                LCD_WIDTH, LCD_HEIGHT, frameW, frameH, jpeg.getWidth(), jpeg.getHeight(),
                sourceCropX, sourceCropY, sourceCropW, sourceCropH, scale,
                jpegDecodeW, jpegDecodeH, jpegCropX, jpegCropY, jpegCropW, jpegCropH,
                jpegDrawW, jpegDrawH, jpegDrawX, jpegDrawY,
                snapshotVideoFraming.aspectW, snapshotVideoFraming.aspectH,
                snapshotVideoFraming.visiblePercent,
                snapshotVideoFraming.previewVisiblePercent);

  jpeg.setPixelType(RGB565_LITTLE_ENDIAN);
  logMemory("Before JPEG decode");
  bool ok = jpeg.decode(0, 0, scale) != 0;
  if (!ok) {
    Serial.printf("JPEG decode failed: scale=%d error=%d\n", scale, jpeg.getLastError());
  } else {
    lv_obj_move_background(previewImageCanvas);
    if (recordingOverlay) {
      lv_obj_move_foreground(recordingOverlay);
    }
    if (fullscreenHint) {
      lv_obj_move_foreground(fullscreenHint);
    }
    lv_obj_invalidate(previewImageCanvas);
  }
  jpeg.close();
  logMemory("After JPEG decode");
  return ok;
}

bool redrawCachedPreviewJpeg() {
  if (!previewJpegCache || previewJpegCacheLen == 0 || redrawingCachedPreview) {
    return false;
  }
  redrawingCachedPreview = true;
  bool ok = drawJpegPreview(previewJpegCache, previewJpegCacheLen);
  redrawingCachedPreview = false;
  return ok;
}

bool canOpenPreviewJpeg(uint8_t *buffer, size_t length) {
  if (!jpeg.openRAM(buffer, static_cast<int>(length), drawJpegBlock)) {
    Serial.printf("JPEG open failed: len=%u header=%02x %02x %02x %02x error=%d\n",
                  static_cast<unsigned>(length),
                  length > 0 ? buffer[0] : 0,
                  length > 1 ? buffer[1] : 0,
                  length > 2 ? buffer[2] : 0,
                  length > 3 ? buffer[3] : 0,
                  jpeg.getLastError());
    return false;
  }
  jpeg.close();
  return true;
}

bool downloadPreviewJpeg(const String &path, uint8_t *buffer, size_t capacity,
                         size_t &jpegLength) {
  jpegLength = 0;
  if (!httpGetGoProBinary(path, buffer, capacity, jpegLength)) {
    return false;
  }
  if (jpegLength < 1024) {
    Serial.printf("JPEG response too small: %u bytes\n", static_cast<unsigned>(jpegLength));
    return false;
  }
  bool wasRedrawing = redrawingCachedPreview;
  redrawingCachedPreview = true;
  setPreviewFullscreen(true);
  redrawingCachedPreview = wasRedrawing;
  if (previewLabel) {
    lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
  }
  setObjHidden(actionLabel, true);
  setObjHidden(recordingOverlay, true);
  serviceLvgl();
  return canOpenPreviewJpeg(buffer, jpegLength);
}

bool syncVideoFramingForSnapshot() {
  setAction("Syncing video framing");
  serviceLvgl();
  bool videoPresetOk = httpGetGoPro("/gopro/camera/presets/set_group?id=1000");
  if (videoPresetOk) {
    captureMode = "Video";
    applyCaptureLabels();
    delay(250);
  } else {
    Serial.println("Video preset select failed before snapshot; using current cached framing");
  }

  if (!syncCameraState()) {
    Serial.println("Camera state sync failed before snapshot; using cached/default framing");
  }
  if (!syncActiveVideoPresetSettings()) {
    Serial.println("Video preset setting sync failed before snapshot; using cached/default framing");
  }
  snapshotVideoFraming = currentSnapshotVideoFraming();
  logSnapshotVideoFraming(snapshotVideoFraming);
  return videoPresetOk;
}

bool restoreVideoPresetAfterSnapshot() {
  bool ok = httpGetGoPro("/gopro/camera/presets/set_group?id=1000");
  if (ok) {
    captureMode = "Video";
    applyCaptureLabels();
    snapshotPreviewPrepared = false;
    delay(150);
    syncCameraState();
  } else {
    Serial.println("Video preset restore failed after snapshot");
  }
  return ok;
}

bool fetchSnapshotPreview() {
  if (snapshotPreviewBusy) {
    return false;
  }
  snapshotPreviewBusy = true;
  logMemory("Snapshot start");
  releaseH264PreviewResources("Snapshot released H264 buffers");

  if (previewUdpListening) {
    previewUdp.stop();
    previewUdpListening = false;
  }
  previewStreamRequested = false;

  if (previewLabel) {
    if (previewHasImage) {
      lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    } else {
      lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
      lv_label_set_text(previewLabel, "Preparing snapshot");
    }
  }
  setAction("Preparing snapshot");
  serviceLvgl();

  httpGetGoProStatus("/gopro/webcam/stop");
  httpGetGoProStatus("/gopro/camera/stream/stop");
  syncVideoFramingForSnapshot();
  if (!httpGetGoPro("/gopro/camera/presets/set_group?id=1001")) {
    if (previewLabel && !previewHasImage) {
      lv_label_set_text(previewLabel, "Photo preset failed");
    }
    snapshotPreviewBusy = false;
    return false;
  }
  captureMode = "Photo";
  applyCaptureLabels();
  alignTemporaryPhotoPresetForSnapshot();
  snapshotPreviewPrepared = true;
  delay(250);

  String beforePath;
  fetchLatestJpegPath(beforePath);
  if (previewLabel && !previewHasImage) {
    lv_label_set_text(previewLabel, "Capturing snapshot");
  }
  setAction("Capturing snapshot");
  serviceLvgl();

  if (!httpGetGoPro("/gopro/camera/shutter/start")) {
    if (previewLabel && !previewHasImage) {
      lv_label_set_text(previewLabel, "Snapshot failed");
    }
    restoreVideoPresetAfterSnapshot();
    setAction("Snapshot failed");
    snapshotPreviewBusy = false;
    return false;
  }

  String newPath;
  uint32_t pollStart = millis();
  while (millis() - pollStart < 12000) {
    delay(250);
    serviceLvgl();
    String latest;
    if (fetchLatestJpegPath(latest) && !latest.isEmpty() && latest != beforePath &&
        latest != lastSnapshotMediaPath) {
      newPath = latest;
      break;
    }
  }

  if (newPath.isEmpty()) {
    if (previewLabel && !previewHasImage) {
      lv_label_set_text(previewLabel, "Snapshot media not found");
    }
    restoreVideoPresetAfterSnapshot();
    setAction("Snapshot media not found");
    snapshotPreviewBusy = false;
    return false;
  }

  String encodedPath = urlEncodePathParam(newPath);
  previewHasImage = false;
  clearPreviewJpegCache();
  uint8_t *jpegBuffer = static_cast<uint8_t *>(heap_caps_malloc(kMaxJpegBytes, MALLOC_CAP_SPIRAM));
  if (jpegBuffer == nullptr) {
    jpegBuffer = static_cast<uint8_t *>(heap_caps_malloc(kMaxJpegBytes, MALLOC_CAP_8BIT));
  }
  if (jpegBuffer == nullptr) {
    deleteGoProMedia(newPath);
    restoreVideoPresetAfterSnapshot();
    if (previewLabel && !previewHasImage) {
      lv_label_set_text(previewLabel, "JPEG buffer allocation failed");
    }
    setAction("JPEG buffer allocation failed");
    snapshotPreviewBusy = false;
    return false;
  }
  Serial.printf("JPEG download buffer allocated: %u bytes\n", static_cast<unsigned>(kMaxJpegBytes));
  logMemory("After JPEG buffer allocation");

  size_t jpegLength = 0;
  String screenPath = "/gopro/media/screennail?path=" + encodedPath;
  bool downloaded = false;
  bool drawn = downloadPreviewJpeg(screenPath, jpegBuffer, kMaxJpegBytes, jpegLength);
  downloaded = jpegLength >= 1024;
  if (!drawn) {
    String thumbPath = "/gopro/media/thumbnail?path=" + encodedPath;
    size_t thumbLength = 0;
    drawn = downloadPreviewJpeg(thumbPath, jpegBuffer, kMaxJpegBytes, thumbLength);
    downloaded = downloaded || thumbLength >= 1024;
    if (drawn) {
      jpegLength = thumbLength;
    }
  }
  if (drawn) {
    if (!shrinkAndAdoptPreviewJpegCache(jpegBuffer, jpegLength)) {
      heap_caps_free(jpegBuffer);
      jpegBuffer = nullptr;
      drawn = false;
    }
  } else {
    heap_caps_free(jpegBuffer);
    jpegBuffer = nullptr;
  }
  logMemory("After JPEG draw/cache");

  bool deleted = deleteGoProMedia(newPath);
  lastSnapshotMediaPath = newPath;
  bool videoRestored = restoreVideoPresetAfterSnapshot();
  snapshotPreviewBusy = false;

  if (drawn) {
    previewHasImage = true;
    if (previewLabel) {
      lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    }
    setObjHidden(actionLabel, true);
    setObjHidden(recordingOverlay, true);
    if (!deleted) {
      setAction("Preview JPEG delete failed");
    } else if (!videoRestored) {
      setAction("Preview shown; video restore failed");
    } else {
      Serial.println("Video-framed preview ready");
    }
    serviceLvgl();
    if (previewFullscreen && previewJpegCache && previewJpegCacheLen > 0) {
      drawn = redrawCachedPreviewJpeg();
      if (!drawn) {
        previewHasImage = false;
        if (previewLabel) {
          lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
          lv_label_set_text(previewLabel, "JPEG decode failed");
        }
        setAction("JPEG decode failed");
        return false;
      }
    }
    return true;
  }

  if (previewLabel) {
    if (previewHasImage) {
      lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    } else {
      lv_obj_clear_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
      lv_label_set_text(previewLabel, downloaded ? "JPEG decode failed" : "JPEG download failed");
    }
  }
  setAction(deleted ? "Deleted failed preview JPEG" : "Preview failed; delete failed");
  return false;
}

void onPair(lv_event_t *event) {
  if (event && lv_event_get_target(event) == pairButton && homeCameraConnected) {
    setAction("Camera already connected");
    return;
  }
  if (event && lv_event_get_target(event) == pairButton && connectRetryAvailable) {
    setAction("Scanning again");
    runConnectAction();
    return;
  }
  queuePairNewAction("button");
}

void onWakeCamera(lv_event_t *) {
  runWakeCameraAction();
}

void onForgetCamera(lv_event_t *) {
  if (recording) {
    setAction("Stop recording before forgetting");
    return;
  }
  if (!hasSavedCameraBinding()) {
    setAction("No saved camera to forget");
    resetTouchInteractionState();
    return;
  }
  if (pendingHomeAction != PendingHomeAction::None) {
    Serial.printf("Forget Camera preempting pending home action %u\n",
                  static_cast<unsigned>(pendingHomeAction));
    pendingHomeAction = PendingHomeAction::None;
    pendingHomeActionDueMs = 0;
  }
  if (goproActionBusy || pairingInProgress) {
    markConnectionCancelRequested("Cancelling connection before forget");
  }
  showForgetConfirm();
}

void onForgetCancel(lv_event_t *) {
  hideForgetConfirm();
  setAction("Forget cancelled");
}

void onForgetConfirm(lv_event_t *) {
  hideForgetConfirm();
  if (recording) {
    setAction("Stop recording before forgetting");
    return;
  }
  if (!hasSavedCameraBinding()) {
    setAction("No saved camera to forget");
    return;
  }
  if (goproActionBusy || pairingInProgress) {
    markConnectionCancelRequested("Cancelling and forgetting camera");
  }
  pendingHomeAction = PendingHomeAction::Forget;
  pendingHomeActionDueMs = millis() + 50;
  setAction("Forgetting saved camera");
}

void selectMode(const char *mode, const char *setting, const char *endpoint) {
  captureMode = mode;
  captureSetting = setting;
  snapshotPreviewPrepared = false;
  applyCaptureLabels();
  lv_label_set_text(statusLabel, captureMode.c_str());
  if (WiFi.status() == WL_CONNECTED && endpoint && endpoint[0]) {
    if (httpGetGoPro(endpoint)) {
      delay(250);
      syncCameraState();
    }
  }
  setAction(captureSetting.c_str());
}

void onModeVideo(lv_event_t *) {
  selectMode("Video", "Sync camera state", "/gopro/camera/presets/set_group?id=1000");
}

void onModePhoto(lv_event_t *) {
  selectMode("Photo", "Sync camera state", "/gopro/camera/presets/set_group?id=1001");
}

void onModeTimeWarp(lv_event_t *) {
  selectMode("TimeWarp", "Sync camera state", "/gopro/camera/presets/set_group?id=1002");
}

void onDashboardConnect(lv_event_t *) {
  connectGoProWifiFromBle();
}

void onSettingSync(lv_event_t *) {
  syncCameraState();
}

void onPresetSync(lv_event_t *) {
  syncCameraPresets();
}

void refreshSettingSheet() {
  if (!settingSheet || !activeSetting) {
    return;
  }

  String title = activeSetting->name;
  int current = getStoredSettingValue(activeSetting->id);
  if (current >= 0) {
    title += " | current ";
    title += activeOptionDisplayName(activeSetting->id, current);
  }
  lv_label_set_text(settingSheetTitle, title.c_str());

  for (size_t i = 0; i < kVisibleSettingOptions; ++i) {
    size_t optionIndex = settingOptionOffset + i;
    if (optionIndex < settingOptionCount) {
      int option = settingOptions[optionIndex];
      String label = activeOptionDisplayName(activeSetting->id, option);
      if (option == current) {
        label += " *";
      }
      lv_label_set_text(settingOptionLabels[i], label.c_str());
      lv_obj_clear_flag(settingOptionButtons[i], LV_OBJ_FLAG_HIDDEN);
    } else {
      lv_obj_add_flag(settingOptionButtons[i], LV_OBJ_FLAG_HIDDEN);
    }
  }

  String pager = String(settingOptionOffset + 1) + "-";
  pager += min(settingOptionOffset + kVisibleSettingOptions, settingOptionCount);
  pager += " of ";
  pager += settingOptionCount;
  lv_label_set_text(settingPagerLabel, pager.c_str());
}

void closeSettingSheet() {
  if (settingSheet) {
    lv_obj_add_flag(settingSheet, LV_OBJ_FLAG_HIDDEN);
  }
}

void onSettingClose(lv_event_t *) {
  closeSettingSheet();
}

void onSettingNext(lv_event_t *) {
  if (settingOptionOffset + kVisibleSettingOptions < settingOptionCount) {
    settingOptionOffset += kVisibleSettingOptions;
    refreshSettingSheet();
  }
}

void onSettingPrev(lv_event_t *) {
  if (settingOptionOffset >= kVisibleSettingOptions) {
    settingOptionOffset -= kVisibleSettingOptions;
  } else {
    settingOptionOffset = 0;
  }
  refreshSettingSheet();
}

void onSettingOption(lv_event_t *event) {
  if (!activeSetting) {
    return;
  }
  uintptr_t visibleIndex = reinterpret_cast<uintptr_t>(lv_event_get_user_data(event));
  size_t optionIndex = settingOptionOffset + visibleIndex;
  if (optionIndex >= settingOptionCount) {
    return;
  }
  int option = settingOptions[optionIndex];
  String label = String(activeSetting->name) + " -> " +
                 activeOptionDisplayName(activeSetting->id, option);
  if (setGoProSetting(activeSetting->id, option, label.c_str())) {
    refreshSettingSheet();
  }
}

void onSettingOpen(lv_event_t *event) {
  const SettingDefinition *setting =
      static_cast<const SettingDefinition *>(lv_event_get_user_data(event));
  if (!setting) {
    return;
  }
  activeSetting = setting;
  if (!settingSheet) {
    return;
  }
  lv_obj_clear_flag(settingSheet, LV_OBJ_FLAG_HIDDEN);
  lv_label_set_text(settingSheetTitle, "Loading options...");
  serviceLvgl();

  if (!querySettingOptions(*setting)) {
    setAction("No options for setting");
  }
  refreshSettingSheet();
}

lv_obj_t *makePanelLabel(lv_obj_t *parent, const char *text, int x, int y, int size = 14,
                         lv_color_t color = lv_color_hex(0xf4f7fb)) {
  lv_obj_t *label = lv_label_create(parent);
  lv_label_set_text(label, text);
  lv_obj_set_style_text_font(label, fontForSize(size), 0);
  lv_obj_set_style_text_color(label, color, 0);
  lv_obj_set_pos(label, x, y);
  return label;
}
