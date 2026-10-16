#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR"
sed "s|@PROJECT_DIR@|$PROJECT_DIR|g" deploy/bmo-headless.service > "$UNIT_DIR/bmo-headless.service"
systemctl --user daemon-reload
systemctl --user enable bmo-headless.service
echo "Installed but did not start bmo-headless.service."
echo "After hardware/API checks: systemctl --user start bmo-headless.service"

