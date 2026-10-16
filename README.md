# BMO Cloud Assistant

Модульный двуязычный голосовой ассистент для Raspberry Pi 5. Основной путь:

```text
Mirfak -> UGREEN -> PTT/VAD -> gpt-transcribe -> gpt-6-luna
                                              -> Piper RU/EN -> Defender
USB Realtek camera -- only on request -------^
```

Проект не устанавливает и не использует Ollama, локальные LLM, облачный TTS,
Realtime API или постоянную передачу видео. Все Responses-вызовы выполняются с
`store=False`. Автотесты полностью mock-based и не расходуют API-баланс.

## Статус

- Этап A: модульный Python 3.11-каркас, CLI, state machine, mock-провайдеры,
  конфигурация, budget guard и документация.
- Этап B: обнаружение UGREEN по имени, terminal PTT, локальная запись/вывод,
  RU/EN Piper с проверяемыми моделями.
- Этап C: headless STT → Responses → Piper, локальный контекст, обработка ошибок
  и отдельный явно платный smoke test.
- Этапы D/E: follow-up VAD и on-demand YUYV camera реализованы программно, но
  требуют реальной приёмки на Raspberry Pi.
- Wake word, Waveshare GUI и systemd activation не считаются принятыми до
  аппаратных испытаний.

## Quick start на Raspberry Pi

```bash
unzip BMO_Cloud_Assistant_v1.2.zip
cd be-more-agent
chmod +x scripts/*.sh start_agent.sh setup.sh
./scripts/install_bmo_cloud.sh
```

Mirfak должен быть подключён к среднему чёрному combo-разъёму UGREEN, Defender —
к зелёному. Затем создайте новый ключ непосредственно на Pi:

```bash
install -m 600 /dev/null ~/.config/bmo/.env
nano ~/.config/bmo/.env
```

Содержимое файла:

```dotenv
OPENAI_API_KEY=PASTE_A_NEW_KEY_HERE
```

Ключ, когда-либо отправленный в чат, использовать нельзя. Проверки выполняются в
таком порядке:

```bash
.venv/bin/bmo doctor
.venv/bin/pytest
.venv/bin/bmo test-audio --seconds 7
.venv/bin/bmo test-tts --language ru
.venv/bin/bmo test-tts --language en
.venv/bin/bmo test-api --confirm-paid   # ровно один явный платный smoke test
.venv/bin/bmo run --headless
```

В headless-режиме Enter начинает и завершает запись, Esc отменяет текущую
операцию, `q` завершает приложение. После ответа микрофон открывается на пять
секунд для follow-up; во время TTS он не слушает.

## Команды

```text
bmo doctor [--json]
bmo run --headless
bmo test-audio [--seconds 5]
bmo test-tts --language ru|en
bmo test-api --confirm-paid
bmo assets install-voices|verify
bmo budget status
bmo budget override --minutes 15 --confirm
```

`budget override` применяется только локально, ограничен 60 минутами и не меняет
лимиты OpenAI Platform. Локальная оценка стоимости является дополнительным hard
stop, но не официальным биллингом.

## Архитектура

- `bmo/core/controller.py` — единственный владелец состояния и `operation_id`.
- `bmo/audio/` — выбор устройств, PTT, VAD, запись и воспроизведение.
- `bmo/providers/` — mockable OpenAI и Piper providers.
- `bmo/vision/` — on-demand YUYV USB camera capture.
- `bmo/budget.py` — атомарный SQLite-ledger резерва и фактических оценок.
- `tests/` — безсетевые unit/integration tests.

Сырые аудио, фото и транскрипты по умолчанию не сохраняются. На диске остаются
только локальные оценки расходов и служебные метрики без содержания разговора.

Подробные команды: [INSTALL_RASPBERRY_PI.md](INSTALL_RASPBERRY_PI.md). Решение
проблем: [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Upstream и лицензия

Основа: `brenpoly/be-more-agent`, SHA
`5fb755809583c8338b1205075b2d465baa9b49ef`, код MIT. Визуальный образ BMO,
звуки, голоса и 3D-модели имеют отдельные ограничения; см. `THIRD_PARTY.md`.
Проект пока предназначен только для личного некоммерческого прототипа.
