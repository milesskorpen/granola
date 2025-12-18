#!/usr/bin/env bash
set -euo pipefail

# Generate macOS .icns from a source PNG using sips + iconutil
# Usage: scripts/make_icns.sh [source_png] [output_icns]

SRC_PNG="${1:-app_icon.png}"
OUT_ICNS="${2:-macos/Granola.icns}"
ICONSET_DIR="${OUT_ICNS%.icns}.iconset"
PYTHON_BIN="${PYTHON:-python3}"

if ! command -v sips >/dev/null 2>&1; then
  echo "Error: 'sips' not found. Install Xcode Command Line Tools: xcode-select --install" >&2
  exit 1
fi

if ! command -v iconutil >/dev/null 2>&1; then
  echo "Error: 'iconutil' not found. Install Xcode Command Line Tools: xcode-select --install" >&2
  exit 1
fi

if [[ ! -f "$SRC_PNG" ]]; then
  echo "Error: source PNG not found: $SRC_PNG" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUT_ICNS")"
rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"

# Generate required sizes
sizes=(
  16 32
  32 64
  128 256
  256 512
  512 1024
)

# Map sizes to filenames
names=(
  icon_16x16.png icon_16x16@2x.png
  icon_32x32.png icon_32x32@2x.png
  icon_128x128.png icon_128x128@2x.png
  icon_256x256.png icon_256x256@2x.png
  icon_512x512.png icon_512x512@2x.png
)

for i in $(seq 0 $(( ${#sizes[@]} / 2 - 1 ))); do
  size="${sizes[$((i*2))]}"
  size2x="${sizes[$((i*2+1))]}"
  name1="${names[$((i*2))]}"
  name2="${names[$((i*2+1))]}"
  if [[ "$size" == 512 ]]; then
    # 512@1x can be a direct copy if source is big enough
    sips -z 512 512 "$SRC_PNG" --out "$ICONSET_DIR/$name1" >/dev/null
  else
    sips -z "$size" "$size" "$SRC_PNG" --out "$ICONSET_DIR/$name1" >/dev/null
  fi
  sips -z "$size2x" "$size2x" "$SRC_PNG" --out "$ICONSET_DIR/$name2" >/dev/null
done

if iconutil -c icns "$ICONSET_DIR" -o "$OUT_ICNS" >/dev/null 2>&1; then
  echo "Wrote $OUT_ICNS"
  exit 0
fi

echo "iconutil failed, attempting Pillow fallback..." >&2

"$PYTHON_BIN" - <<PY
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    raise SystemExit("Pillow is required for icon fallback. Install with: pip install pillow")

src = Path("${SRC_PNG}").expanduser()
out = Path("${OUT_ICNS}").expanduser()
sizes = [(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)]

img = Image.open(src)
img.save(out, sizes=sizes)
print(f"Wrote {out}")
PY
