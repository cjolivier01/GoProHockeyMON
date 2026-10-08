// Snapshot transaction: preserve the camera preset across temporary photo capture.
bool syncVideoFramingForSnapshot() {
  setAction("Syncing camera profile");
  serviceLvgl();
  // Read the selected preset before any mode command. Selecting the Video group
  // here can replace a custom preset before we have a chance to save it.
  if (!syncCameraState() || recording || activeCameraPresetId < 0) {
    setAction(recording ? "Snapshot disabled while recording"
                        : "Cannot read camera profile");
    return false;
  }
  snapshotVideoFraming = activeCameraPresetGroup == kGoProVideoPresetGroup
                             ? currentSnapshotVideoFraming()
                             : SnapshotVideoFraming{};
  logSnapshotVideoFraming(snapshotVideoFraming);
  return true;
}

void showSnapshotRestoreFailure(const char *message) {
  // Fullscreen preview hides both the profile and action labels. Make a failed
  // restore visible before the user tries to record while still in Photo mode.
  setPreviewFullscreen(false);
  setObjHidden(actionLabel, false);
  setAction(message);
}

bool restorePresetAfterSnapshot(int32_t presetId, const String &presetName) {
  String path = "/gopro/camera/presets/load?id=";
  path += presetId;
  bool ok = httpGetGoPro(path);
  snapshotPreviewPrepared = false;
  if (ok) {
    captureMode = presetName;
    applyCaptureLabels();
    delay(150);
    // Confirm the camera actually selected the saved preset; do not claim a
    // successful restore on an HTTP acknowledgement alone.
    ok = syncCameraState() && activeCameraPresetId == presetId;
  }
  if (!ok) {
    Serial.printf("Camera profile restore failed: preset=%ld\n", static_cast<long>(presetId));
    showSnapshotRestoreFailure("Camera profile restore failed");
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

  if (!syncVideoFramingForSnapshot()) {
    if (previewLabel && !previewHasImage) {
      lv_label_set_text(previewLabel, "Snapshot unavailable");
    }
    snapshotPreviewBusy = false;
    return false;
  }
  const int32_t originalPresetId = activeCameraPresetId;
  const String originalPresetName = captureMode;
  httpGetGoProStatus("/gopro/webcam/stop");
  httpGetGoProStatus("/gopro/camera/stream/stop");
  if (!httpGetGoPro("/gopro/camera/presets/set_group?id=1001")) {
    if (previewLabel && !previewHasImage) {
      lv_label_set_text(previewLabel, "Photo preset failed");
    }
    // A timeout may mean the mode changed but its reply was lost.
    if (restorePresetAfterSnapshot(originalPresetId, originalPresetName)) {
      setAction("Photo preset failed");
    }
    snapshotPreviewBusy = false;
    return false;
  }
  captureMode = "Photo";
  applyCaptureLabels();
  if (snapshotVideoFraming.valid) {
    alignTemporaryPhotoPresetForSnapshot();
  }
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
    if (restorePresetAfterSnapshot(originalPresetId, originalPresetName)) {
      setAction("Snapshot failed");
    }
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
    if (restorePresetAfterSnapshot(originalPresetId, originalPresetName)) {
      setAction("Snapshot media not found");
    }
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
    bool restored = restorePresetAfterSnapshot(originalPresetId, originalPresetName);
    if (previewLabel && !previewHasImage) {
      lv_label_set_text(previewLabel, "JPEG buffer allocation failed");
    }
    if (restored) {
      setAction("JPEG buffer allocation failed");
    }
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
  bool presetRestored = restorePresetAfterSnapshot(originalPresetId, originalPresetName);
  snapshotPreviewBusy = false;

  if (drawn) {
    previewHasImage = true;
    if (previewLabel) {
      lv_obj_add_flag(previewLabel, LV_OBJ_FLAG_HIDDEN);
    }
    setObjHidden(actionLabel, true);
    setObjHidden(recordingOverlay, true);
    if (!presetRestored) {
      showSnapshotRestoreFailure("Preview shown; profile restore failed");
    } else if (!deleted) {
      setAction("Preview JPEG delete failed");
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
  if (presetRestored) {
    setAction(deleted ? "Deleted failed preview JPEG" : "Preview failed; delete failed");
  }
  return false;
}
