#!/usr/bin/env bash
set -euo pipefail

device="${1:-/dev/video0}"
v4l2-ctl --device "$device" --list-formats-ext
ffmpeg -hide_banner -loglevel warning \
  -f v4l2 -input_format yuyv422 -video_size 640x480 -framerate 30 \
  -i "$device" -frames:v 1 -y /tmp/bmo-camera-test.jpg
echo "Saved one diagnostic frame to /tmp/bmo-camera-test.jpg"

