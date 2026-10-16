# Release package manifest

Included:

- modular `bmo/` Python package and CLI;
- offline mock/unit tests;
- Pi installation, hardware diagnostics and systemd templates;
- upstream `faces/` and `sounds/` for personal prototype use;
- configuration examples without secrets;
- licenses, decisions and third-party register.

Intentionally excluded from release ZIP:

- `.git`, `.venv`, caches and local state;
- `.env` and all API keys;
- downloaded Piper voice binaries (installer retrieves and verifies them);
- upstream `agent.py`/`config.json` tied to Ollama and Whisper.cpp;
- unverified upstream `wakeword.onnx`;
- obsolete upstream desktop launcher.

The excluded upstream files remain recoverable from commit
`5fb755809583c8338b1205075b2d465baa9b49ef`.
