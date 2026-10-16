# Test report

## Local automated checks

Run on 2026-10-16 on macOS arm64 / Python 3.11.6:

| Check | Result |
|---|---|
| `ruff check bmo tests` | passed, no findings |
| `pytest -q` | 32 passed in 0.44 s, including stdin-free service/socket tests |
| `bash -n scripts/*.sh start_agent.sh setup.sh` | passed |
| `bmo run --help` | passed; interactive and service modes are separate |
| `bmo control --help` | passed; PTT/status/cancel/shutdown commands present |
| `git diff --check` | passed |
| Installer/systemd assertions | passed; dev extra and stdin-free service command present |
| Secret-pattern scan | passed; no project key pattern in repository files |

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
