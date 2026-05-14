#!/usr/bin/env bash
set -euo pipefail

repo="${1:-$HOME/src/ESP32-S3-Touch-AMOLED-1.8}"
gfx="$repo/examples/Arduino-v3.3.5/libraries/GFX_Library_for_Arduino/src/databus"

if [[ ! -d "$gfx" ]]; then
  echo "Waveshare AMOLED Arduino libraries not found at: $repo" >&2
  echo "Clone https://github.com/waveshareteam/ESP32-S3-Touch-AMOLED-1.8 into ~/src first." >&2
  exit 1
fi

python3 - "$gfx" <<'PY'
from pathlib import Path
import sys

gfx = Path(sys.argv[1])
spi = gfx / "Arduino_ESP32SPI.cpp"
spidma = gfx / "Arduino_ESP32SPIDMA.cpp"

replacements = {
    spi: {
        "spiFrequencyToClockDiv(old_apb / ((_spi->dev->clock.clkdiv_pre + 1) * (_spi->dev->clock.clkcnt_n + 1)))":
            "spiFrequencyToClockDiv(_spi, old_apb / ((_spi->dev->clock.clkdiv_pre + 1) * (_spi->dev->clock.clkcnt_n + 1)))",
        "spiFrequencyToClockDiv(_speed)": "spiFrequencyToClockDiv(_spi, _speed)",
    },
    spidma: {
        "spiFrequencyToClockDiv(_speed)": "1",
    },
}

for path, mapping in replacements.items():
    text = path.read_text()
    original = text
    for old, new in mapping.items():
        text = text.replace(old, new)
    if text != original:
        path.write_text(text)
        print(f"patched {path}")
    else:
        print(f"already patched {path}")
PY
