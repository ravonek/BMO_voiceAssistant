# Troubleshooting

## UGREEN или Mirfak не обнаружены

- Mirfak MC1P: средний чёрный combo TRRS, без дополнительного переходника.
- Defender SPK-22: зелёный аудиовыход; USB-кабель колонок подаёт питание.
- Выполните `lsusb`, `arecord -l`, `aplay -l`, `.venv/bin/bmo doctor`.
- Не фиксируйте в конфиге `card 2`: номер меняется после перезагрузки/replug.

## ALSA Device busy

Закройте Guvcview, браузерные вкладки и другие программы записи. Посмотрите
`fuser -v /dev/snd/*`. Приложение выбирает PortAudio-устройство по имени и не
открывает параллельно два capture stream.

## Голос слишком быстрый или низкий

Sample rate берётся из соседнего `.onnx.json`. Проверьте целостность файлов:

```bash
.venv/bin/bmo assets verify
```

Не задавайте вручную 22050 для неизвестной модели.

## Камера даёт полосы или странные цвета

Штатный режим — YUYV 640×480@30. MJPEG для Realtek `0bda:5842` не используется.

```bash
v4l2-ctl --device /dev/video0 --list-formats-ext
./scripts/test_camera.sh /dev/video0
```

Если устройство занято, закройте Guvcview. Ошибка камеры не должна выключать
голосовой режим.

## API 401, quota или model_not_found

- `doctor` показывает только `set/not set`, но никогда не значение ключа.
- Проверьте новый project key и права файла: `chmod 600 ~/.config/bmo/.env`.
- Не используйте ключ из чата.
- Приложение не переключается автоматически на более дорогую модель.

## Piper-модель отсутствует

```bash
.venv/bin/bmo assets install-voices
.venv/bin/bmo assets verify
```

До появления проверенных файлов приложение остаётся в диагностическом режиме и
не заменяет Piper платным облачным TTS.

## SSH и клавиши PTT

Запускайте интерактивно: `.venv/bin/bmo run --headless`. Enter — toggle записи,
Esc — cancel, `q` — выход. Для systemd потребуется физическая кнопка/GUI или
отдельный управляющий socket; keyboard PTT предназначен для интерактивного MVP.

