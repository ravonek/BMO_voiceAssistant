# Changelog

## Unreleased

- Installed pytest with the Raspberry Pi development dependencies.
- Split terminal PTT from the stdin-free systemd service and added local socket control.
- Moved Raspberry Pi installation instructions to the separate `~/bmo-cloud` directory.

## 0.1.0

- Replaced the Ollama/Whisper.cpp monolith with a typed modular cloud architecture.
- Added headless PTT, follow-up VAD, OpenAI Responses/STT providers and Piper RU/EN.
- Added local hard budget limits, on-demand YUYV camera capture and mock-only tests.
- Disabled the unsafe upstream installer and documented Raspberry Pi acceptance.

