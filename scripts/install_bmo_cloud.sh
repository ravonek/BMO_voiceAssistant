#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

if command -v ollama >/dev/null 2>&1; then
  echo "NOTICE: Ollama is installed, but BMO Cloud does not use or modify it."
fi

sudo apt-get update
sudo apt-get install -y \
  python3.11 python3.11-venv python3-dev \
  libasound2-dev portaudio19-dev ffmpeg v4l-utils usbutils

python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[tts,vision]'

install -d -m 700 "$HOME/.config/bmo" "$HOME/.local/state/bmo"
if [[ ! -f "$HOME/.config/bmo/config.yaml" ]]; then
  install -m 600 config.example.yaml "$HOME/.config/bmo/config.yaml"
fi

.venv/bin/bmo assets install-voices --directory voices
.venv/bin/bmo doctor

echo
echo "Installation complete. Create the secret file locally:"
echo "  install -m 600 /dev/null ~/.config/bmo/.env"
echo "  nano ~/.config/bmo/.env"
echo "Then add a NEW key as OPENAI_API_KEY=..."

