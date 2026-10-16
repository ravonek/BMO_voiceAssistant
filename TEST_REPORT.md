# Test report

## Local automated checks

Run on 2026-10-16 on macOS arm64 / Python 3.11.6:

| Check | Result |
|---|---|
| `ruff check bmo tests` | passed, no findings |
| `pytest -q` | 25 passed in 0.48 s, including follow-up and camera failure |
| `bmo --help` | passed; all expected commands present |
| `bmo doctor --json` | passed; correctly reported missing Pi USB hardware |
| Secret-pattern scan | passed; no project key pattern in ZIP |
| Piper asset SHA256 RU/EN | passed |
| Piper RU synthesis | valid mono WAV, 22050 Hz, 39168 frames |
| Piper EN synthesis | valid mono WAV, 22050 Hz, 48384 frames |
| Clean install from release ZIP | passed; tests and CLI help |

No OpenAI endpoint was called and no API cost was incurred.

## Raspberry Pi hardware checks

| Check | Status | Evidence |
|---|---|---|
| Bookworm ARM64 / Python 3.11 | pending | run `bmo doctor --json` on Pi |
| UGREEN `31b2:5075` | pending | hardware unavailable locally |
| Mirfak recording | pending | hardware unavailable locally |
| Defender playback | pending | hardware unavailable locally |
| Piper RU/EN playback | pending | hardware unavailable locally |
| Camera YUYV `0bda:5842` | pending | hardware unavailable locally |
| Five RU + five EN cloud turns | pending | user-authorized paid test on Pi only |
| Follow-up 5 seconds | pending | hardware acceptance required |
| USB replug / two-hour soak | pending | phase H |

No hardware or paid API test is marked passed without actual evidence.
