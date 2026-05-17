#include <Arduino.h>
#include "esp_heap_caps.h"

extern "C" {
#include "h264bsd_decoder.h"
}

#include "baseline_h264.h"
#include "baseline1280x720_h264.h"
#include "baseline320x192_h264.h"
#include "baseline640x368_h264.h"
#include "high_h264.h"

namespace {

#ifndef GOPRO_P4_DECODE_OUT_W
#define GOPRO_P4_DECODE_OUT_W 240
#endif

#ifndef GOPRO_P4_DECODE_OUT_H
#define GOPRO_P4_DECODE_OUT_H 320
#endif

constexpr uint32_t kOutputWidth = GOPRO_P4_DECODE_OUT_W;
constexpr uint32_t kOutputHeight = GOPRO_P4_DECODE_OUT_H;
constexpr uint32_t kTileRows = 16;

const char *decodeReturnName(uint32_t ret) {
  switch (ret) {
    case H264BSD_RDY:
      return "RDY";
    case H264BSD_PIC_RDY:
      return "PIC_RDY";
    case H264BSD_HDRS_RDY:
      return "HDRS_RDY";
    case H264BSD_ERROR:
      return "ERROR";
    case H264BSD_PARAM_SET_ERROR:
      return "PARAM_SET_ERROR";
    case H264BSD_MEMALLOC_ERROR:
      return "MEMALLOC_ERROR";
    default:
      return "UNKNOWN";
  }
}

uint8_t clamp8(int value) {
  if (value < 0) {
    return 0;
  }
  if (value > 255) {
    return 255;
  }
  return static_cast<uint8_t>(value);
}

uint16_t yuvToRgb565(uint8_t y, uint8_t u, uint8_t v) {
  const int c = static_cast<int>(y) - 16;
  const int d = static_cast<int>(u) - 128;
  const int e = static_cast<int>(v) - 128;
  const uint8_t r = clamp8((298 * c + 409 * e + 128) >> 8);
  const uint8_t g = clamp8((298 * c - 100 * d - 208 * e + 128) >> 8);
  const uint8_t b = clamp8((298 * c + 516 * d + 128) >> 8);
  return static_cast<uint16_t>(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3));
}

uint32_t fnv1a32(const uint8_t *data, uint32_t len) {
  uint32_t hash = 2166136261UL;
  for (uint32_t i = 0; i < len; ++i) {
    hash ^= data[i];
    hash *= 16777619UL;
  }
  return hash;
}

bool convertI420ToRgb565Frame(const uint8_t *pic, uint32_t srcW, uint32_t srcH,
                              uint16_t *out, uint32_t outW, uint32_t outH,
                              uint32_t *drawW, uint32_t *drawH,
                              uint32_t *drawX, uint32_t *drawY) {
  if (!pic || !out || srcW == 0 || srcH == 0 || outW == 0 || outH == 0) {
    return false;
  }

  const uint32_t fitByWidthH = (outW * srcH) / srcW;
  if (fitByWidthH <= outH) {
    *drawW = outW;
    *drawH = fitByWidthH;
  } else {
    *drawH = outH;
    *drawW = (outH * srcW) / srcH;
  }
  *drawW = max<uint32_t>(1, *drawW);
  *drawH = max<uint32_t>(1, *drawH);
  *drawX = (outW - *drawW) / 2;
  *drawY = (outH - *drawH) / 2;

  const uint16_t black = 0x0000;
  for (uint32_t i = 0; i < outW * outH; ++i) {
    out[i] = black;
  }

  const uint8_t *yPlane = pic;
  const uint8_t *uPlane = yPlane + (srcW * srcH);
  const uint8_t *vPlane = uPlane + ((srcW * srcH) / 4);
  const uint32_t chromaW = srcW / 2;

  for (uint32_t oy = 0; oy < *drawH; ++oy) {
    const uint32_t sy = min<uint32_t>((oy * srcH) / *drawH, srcH - 1);
    uint16_t *dst = out + ((*drawY + oy) * outW) + *drawX;
    for (uint32_t ox = 0; ox < *drawW; ++ox) {
      const uint32_t sx = min<uint32_t>((ox * srcW) / *drawW, srcW - 1);
      const uint8_t y = yPlane[(sy * srcW) + sx];
      const uint32_t uvIndex = ((sy / 2) * chromaW) + (sx / 2);
      dst[ox] = yuvToRgb565(y, uPlane[uvIndex], vPlane[uvIndex]);
    }
  }
  return true;
}

void printHeap(const char *label) {
  Serial.printf("%s heap=%u internal=%u psram=%u\n",
                label,
                heap_caps_get_free_size(MALLOC_CAP_8BIT),
                heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
                heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
}

bool runDecodeCase(const char *name, const unsigned char *stream, uint32_t streamLen) {
  Serial.printf("\nCase: %s, input=%u bytes\n", name, streamLen);
  h264bsd_cfg_t cfg = H264BSD_CFG_DEFAULT();
  cfg.dualTaskEnable = 0;
  h264bsd_hd_t decoder = h264bsdAlloc(&cfg);
  if (!decoder) {
    Serial.println("decoder allocation failed");
    return false;
  }
  Serial.println("h264bsdInit=skipped");

  const uint32_t paddedLen = streamLen + 64;
  uint8_t *input = static_cast<uint8_t *>(
      heap_caps_aligned_alloc(32, paddedLen, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT));
  if (!input) {
    Serial.println("input allocation failed");
    h264bsdFree(decoder);
    return false;
  }
  memcpy(input, stream, streamLen);
  memset(input + streamLen, 0, paddedLen - streamLen);

  u32 offset = 0;
  bool pictureReady = false;
  uint32_t decodedWidth = 0;
  uint32_t decodedHeight = 0;
  uint32_t decodeMs = 0;
  for (uint8_t i = 0; i < 8 && offset < streamLen; ++i) {
    u32 len = streamLen - offset;
    uint8_t *picture = nullptr;
    u32 width = 0;
    u32 height = 0;
    u32 before = len;
    uint32_t startMs = millis();
    u32 ret = h264bsdDecode(decoder, input + offset, &len, &picture, &width, &height);
    uint32_t elapsed = millis() - startMs;
    u32 consumed = before - len;
    Serial.printf("  step=%u ret=%u(%s) consumed=%u remaining=%u size=%ux%u pic=%p time=%ums\n",
                  i, ret, decodeReturnName(ret), consumed, len, width, height, picture, elapsed);
    if (ret == H264BSD_PIC_RDY && picture && width > 0 && height > 0) {
      pictureReady = true;
      decodedWidth = width;
      decodedHeight = height;
      decodeMs = elapsed;

      const uint32_t framebufferBytes = kOutputWidth * kOutputHeight * sizeof(uint16_t);
      uint16_t *framebuffer = static_cast<uint16_t *>(
          heap_caps_malloc(framebufferBytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
      if (!framebuffer) {
        framebuffer = static_cast<uint16_t *>(
            heap_caps_malloc(framebufferBytes, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT));
      }
      if (!framebuffer) {
        Serial.println("  rgb565 framebuffer allocation failed");
      } else {
        uint32_t drawW = 0;
        uint32_t drawH = 0;
        uint32_t drawX = 0;
        uint32_t drawY = 0;
        const uint32_t convertStartMs = millis();
        const bool converted = convertI420ToRgb565Frame(picture, width, height, framebuffer,
                                                        kOutputWidth, kOutputHeight,
                                                        &drawW, &drawH, &drawX, &drawY);
        const uint32_t convertMs = millis() - convertStartMs;
        const uint32_t checksum = converted
                                      ? fnv1a32(reinterpret_cast<const uint8_t *>(framebuffer),
                                                framebufferBytes)
                                      : 0;
        const uint32_t tileCount = (kOutputHeight + kTileRows - 1) / kTileRows;
        const uint32_t tileBytes = kOutputWidth * kTileRows * sizeof(uint16_t);
        Serial.printf("  rgb565=%s out=%ux%u draw=%ux%u+%u,%u convert=%ums checksum=0x%08lx\n",
                      converted ? "ok" : "fail",
                      kOutputWidth, kOutputHeight, drawW, drawH, drawX, drawY,
                      convertMs, static_cast<unsigned long>(checksum));
        Serial.printf("  tile-plan rows=%u tiles=%u max_payload=%u bytes total=%u bytes\n",
                      kTileRows, tileCount, tileBytes, framebufferBytes);
        free(framebuffer);
      }
      break;
    }
    if (ret == H264BSD_ERROR || ret == H264BSD_PARAM_SET_ERROR || ret == H264BSD_MEMALLOC_ERROR) {
      break;
    }
    if (consumed == 0) {
      break;
    }
    offset += consumed;
  }

  free(input);
  h264bsdFree(decoder);
  Serial.printf("Result: %s %s decoded=%ux%u decode_time=%ums\n",
                name, pictureReady ? "DECODED" : "NOT_DECODED",
                decodedWidth, decodedHeight, decodeMs);
  return pictureReady;
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(2500);
  Serial.println();
  Serial.println("ESP32-P4 H.264 decode probe");
  Serial.printf("chip=%s rev=%u cores=%u cpu=%uMHz\n",
                ESP.getChipModel(), ESP.getChipRevision(), ESP.getChipCores(), ESP.getCpuFreqMHz());
  Serial.printf("tinyh264=%s\n", esp_tinyh264_get_version());
  printHeap("boot");

  bool baselineOk = runDecodeCase("constrained-baseline-80x80", baseline_h264, baseline_h264_len);
  printHeap("after 80x80");
  bool baseline320Ok = runDecodeCase("constrained-baseline-320x192-simple", baseline320x192_h264, baseline320x192_h264_len);
  printHeap("after 320x192");
  bool baseline640Ok = runDecodeCase("constrained-baseline-640x368-simple", baseline640x368_h264, baseline640x368_h264_len);
  printHeap("after 640x368");
  bool baseline720Ok = runDecodeCase("constrained-baseline-1280x720-simple", baseline1280x720_h264, baseline1280x720_h264_len);
  printHeap("after 1280x720");
  bool highOk = runDecodeCase("high-profile-64x64", high_h264, high_h264_len);
  printHeap("after high");

  Serial.println();
  Serial.printf("SUMMARY baseline80=%s baseline320=%s baseline640=%s baseline720=%s high_profile=%s\n",
                baselineOk ? "ok" : "fail",
                baseline320Ok ? "ok" : "fail",
                baseline640Ok ? "ok" : "fail",
                baseline720Ok ? "ok" : "fail",
                highOk ? "ok" : "fail");
  Serial.println("Probe complete.");
}

void loop() {
  delay(1000);
}
