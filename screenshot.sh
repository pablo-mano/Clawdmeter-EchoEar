#!/bin/bash
# Take a screenshot from the Waveshare AMOLED display via LVGL snapshot.
# Usage: ./screenshot.sh [output.png] [port]

OUTPUT="${1:-screenshot.png}"
PORT="${2:-/dev/ttyACM0}"

TMPRAW=$(mktemp /tmp/screenshot_XXXXXX.raw)
trap "rm -f '$TMPRAW'" EXIT

echo "Taking screenshot from $PORT..."

python3 - "$PORT" "$TMPRAW" << 'PYEOF'
import serial, sys

port_path, raw_path = sys.argv[1], sys.argv[2]

port = serial.Serial(port_path, 115200, timeout=10)
port.reset_input_buffer()
port.write(b"screenshot\n")
port.flush()

while True:
    line = port.readline().decode("utf-8", errors="replace").strip()
    if line.startswith("SCREENSHOT_START"):
        parts = line.split()
        w, h, raw_size = int(parts[1]), int(parts[2]), int(parts[3])
        break
    if line == "SCREENSHOT_ERR":
        print("Device reported screenshot error", file=sys.stderr)
        sys.exit(1)

data = b""
while len(data) < raw_size:
    chunk = port.read(min(4096, raw_size - len(data)))
    if not chunk:
        print(f"Timeout: got {len(data)} of {raw_size} bytes", file=sys.stderr)
        sys.exit(1)
    data += chunk

with open(raw_path, "wb") as f:
    f.write(data)

for _ in range(10):
    line = port.readline().decode("utf-8", errors="replace").strip()
    if line == "SCREENSHOT_END":
        break

port.close()
print(f"Captured {w}x{h} ({len(data)} bytes)")
PYEOF

if [ $? -ne 0 ]; then
    echo "Screenshot capture failed"
    exit 1
fi

# Convert RGB565LE raw → PNG using Python/Pillow (no ffmpeg needed)
python3 - "$TMPRAW" "$OUTPUT" << 'CONVEOF'
import sys, struct
from PIL import Image

raw_path, out_path = sys.argv[1], sys.argv[2]
data = open(raw_path, "rb").read()
n = len(data) // 2
side = int(n ** 0.5)
pixels = []
for i in range(n):
    v = struct.unpack_from("<H", data, i * 2)[0]
    r = ((v >> 11) & 0x1F) << 3
    g = ((v >> 5)  & 0x3F) << 2
    b = (v         & 0x1F) << 3
    pixels.append((r, g, b))
img = Image.new("RGB", (side, side))
img.putdata(pixels)
img.save(out_path)
CONVEOF


if [ -f "$OUTPUT" ]; then
    echo "Saved: $OUTPUT"
else
    echo "Error: conversion failed"
    exit 1
fi
