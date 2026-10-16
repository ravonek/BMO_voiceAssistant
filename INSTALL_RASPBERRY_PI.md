# Установка на Raspberry Pi 5

Цель: Raspberry Pi OS Bookworm 64-bit, Python 3.11, пользователь `bmo`.

## 1. Проверить платформу

```bash
cat /etc/os-release
uname -a
python3 --version
lsusb
```

Ожидаются `aarch64`, Python 3.11, UGREEN `31b2:5075` и камера `0bda:5842`.
Если идентификаторы отличаются, сначала сохраните вывод `bmo doctor`; не
подменяйте устройство случайным номером `card 2`.

## 2. Установить проект

```bash
cd ~/be-more-agent
chmod +x scripts/*.sh start_agent.sh setup.sh
./scripts/install_bmo_cloud.sh
```

Скрипт устанавливает PortAudio/V4L2/FFmpeg, создаёт `.venv`, устанавливает
Python-пакет и Piper, скачивает RU/EN-модели и проверяет SHA256. Ollama не
устанавливается и не запускается.

## 3. Внести новый API-ключ только на Pi

```bash
install -m 600 /dev/null ~/.config/bmo/.env
nano ~/.config/bmo/.env
```

```dotenv
OPENAI_API_KEY=NEW_PROJECT_KEY
```

Не копируйте ключ в `config.yaml`, историю shell или архив. Если ключ был
отправлен в чат, отзовите его и создайте другой.

## 4. Локальные проверки без API

```bash
cd ~/be-more-agent
.venv/bin/bmo doctor --json
.venv/bin/pytest
.venv/bin/bmo test-audio --seconds 7
.venv/bin/bmo test-tts --language ru
.venv/bin/bmo test-tts --language en
./scripts/test_camera.sh /dev/video0
```

Для микрофона используйте средний чёрный TRRS UGREEN; для Defender — зелёный
выход. Камера должна перечислять YUYV 640x480@30.

## 5. Единственная первоначальная API-проверка

После успешных mock/audio/Piper тестов:

```bash
.venv/bin/bmo budget status
.venv/bin/bmo test-api --confirm-paid
```

Команда делает один короткий Responses-вызов. Она не проверяет STT и никогда не
запускается pytest автоматически.

## 6. Запуск

```bash
.venv/bin/bmo run --headless
```

Проверьте по пять коротких RU и EN фраз. Сохраните фактические результаты, не
помещая речь или ключ в лог.

## 7. Автозапуск после ручной приёмки

```bash
./scripts/install_systemd.sh
systemctl --user start bmo-headless.service
systemctl --user status bmo-headless.service
journalctl --user -u bmo-headless.service -f
```

Откат:

```bash
systemctl --user disable --now bmo-headless.service
rm ~/.config/systemd/user/bmo-headless.service
systemctl --user daemon-reload
```

