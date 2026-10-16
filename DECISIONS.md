# Decisions

| Решение | Значение | Статус |
|---|---|---|
| Рабочая база | upstream SHA `5fb755809583c8338b1205075b2d465baa9b49ef` | зафиксировано |
| Основной ввод MVP | keyboard PTT, Enter toggle, Esc cancel | принято |
| LLM/Vision | `gpt-6-luna`, Responses API, `store=False` | принято |
| STT | `gpt-transcribe`, завершённый WAV | принято |
| TTS | локальный Piper RU/EN | принято, hardware pending |
| Локальная память | RAM-only, максимум 12 turn | принято |
| Изображения/аудио | не сохранять по умолчанию | принято |
| Камера | Realtek YUYV 640×480@30 on-demand | hardware pending |
| Wake word | выключен до модели `Hey BMO` с SHA/лицензией | pending |
| Дисплей | headless до проверки Waveshare revision/touch | pending |
| Публикация | личный некоммерческий прототип | принято |

Открытые аппаратные факты должны быть заполнены выводом `bmo doctor` на реальной
Pi до systemd activation.

