from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import wave
from dataclasses import asdict
from io import BytesIO
from pathlib import Path

import numpy as np

from bmo.assets import install_voices, verify_voices
from bmo.audio.io import SoundDeviceAudioInput, SoundDeviceAudioOutput
from bmo.budget import BudgetGuard
from bmo.config import Settings, load_settings
from bmo.core.controller import AssistantController
from bmo.doctor import collect_diagnostics, render_diagnostics
from bmo.headless import run_interactive
from bmo.providers.openai_api import OpenAIProviders
from bmo.providers.piper_tts import PiperTTSProvider
from bmo.security import load_dotenv_secure
from bmo.service import CONTROL_COMMANDS, run_background_service, send_control_command
from bmo.vision.camera import OpenCVCameraProvider


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bmo", description="BMO Cloud Assistant")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--env-file", type=Path, default=Path.home() / ".config/bmo/.env")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="inspect configuration and hardware")
    doctor.add_argument("--json", action="store_true")

    run = sub.add_parser("run", help="run the assistant")
    mode = run.add_mutually_exclusive_group()
    mode.add_argument(
        "--interactive",
        dest="run_mode",
        action="store_const",
        const="interactive",
        help="keyboard PTT using interactive stdin",
    )
    mode.add_argument(
        "--service",
        dest="run_mode",
        action="store_const",
        const="service",
        help="background mode controlled through a local Unix socket",
    )
    mode.add_argument(
        "--headless",
        dest="run_mode",
        action="store_const",
        const="interactive",
        help=argparse.SUPPRESS,
    )
    mode.add_argument(
        "--gui",
        dest="run_mode",
        action="store_const",
        const="gui",
        help="reserved for the display phase",
    )
    run.set_defaults(run_mode="interactive")

    control = sub.add_parser("control", help="control a running background service")
    control.add_argument("action", choices=sorted(CONTROL_COMMANDS))
    control.add_argument("--socket", type=Path)

    test_audio = sub.add_parser("test-audio", help="record and replay a local sample")
    test_audio.add_argument("--seconds", type=float, default=5.0)

    test_tts = sub.add_parser("test-tts", help="synthesize locally with Piper")
    test_tts.add_argument("--language", choices=["ru", "en"], default="ru")
    test_tts.add_argument("--text")

    test_api = sub.add_parser("test-api", help="run one explicitly paid text request")
    test_api.add_argument("--confirm-paid", action="store_true")

    assets = sub.add_parser("assets", help="install or verify local assets")
    assets.add_argument("action", choices=["install-voices", "verify"])
    assets.add_argument("--directory", type=Path, default=Path("voices"))

    budget = sub.add_parser("budget", help="show or temporarily override local budget")
    budget.add_argument("action", choices=["status", "override"])
    budget.add_argument("--minutes", type=int, default=15)
    budget.add_argument("--confirm", action="store_true")
    return parser


def _budget(settings: Settings) -> BudgetGuard:
    return BudgetGuard(
        settings.state_dir / "budget.sqlite3",
        timezone=settings.app.timezone,
        daily_hard_limit_usd=settings.cloud.daily_hard_limit_usd,
        monthly_hard_limit_usd=settings.cloud.monthly_hard_limit_usd,
    )


def _runtime(settings: Settings) -> tuple[AssistantController, SoundDeviceAudioInput]:
    audio_input = SoundDeviceAudioInput(settings.audio)
    audio_output = SoundDeviceAudioOutput(settings.audio)
    cloud = OpenAIProviders(settings.cloud, _budget(settings))
    tts = PiperTTSProvider(settings.speech, audio_output)
    camera = OpenCVCameraProvider(settings.camera)
    controller = AssistantController(
        settings,
        stt=cloud,
        llm=cloud,
        tts=tts,
        camera=camera,
        audio_input=audio_input,
    )
    return controller, audio_input


async def _run_interactive(settings: Settings) -> None:
    controller, audio_input = _runtime(settings)
    await run_interactive(controller, audio_input)


async def _run_service(settings: Settings) -> None:
    controller, audio_input = _runtime(settings)
    await run_background_service(controller, audio_input, settings.state_dir / "control.sock")


async def _test_audio(settings: Settings, seconds: float) -> None:
    if not 1 <= seconds <= 30:
        raise ValueError("--seconds must be between 1 and 30")
    capture = SoundDeviceAudioInput(settings.audio)
    output = SoundDeviceAudioOutput(settings.audio)
    print(f"Recording {seconds:.1f} seconds...")
    capture.start()
    await asyncio.sleep(seconds)
    clip = capture.stop()
    if clip is None:
        raise RuntimeError("recording was empty")
    with wave.open(BytesIO(clip.wav_bytes), "rb") as wav:
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
    print("Playing the recording through the selected UGREEN output...")
    await output.play(samples, clip.sample_rate)


async def _test_tts(settings: Settings, language: str, text: str | None) -> None:
    output = SoundDeviceAudioOutput(settings.audio)
    tts = PiperTTSProvider(settings.speech, output)
    phrase = text or (
        "Привет! Локальный голос Бимо работает без облачного TTS."
        if language == "ru"
        else "Hello! BMO local speech works without cloud TTS."
    )
    await tts.speak(phrase, language, 1)


async def _test_api(settings: Settings, confirmed: bool) -> None:
    if not confirmed:
        raise RuntimeError("paid smoke test refused: add --confirm-paid after mock tests pass")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")
    cloud = OpenAIProviders(settings.cloud, _budget(settings))
    response = await cloud.respond("Reply with exactly: OK", [])
    print(response.text)
    print(f"estimated_cost_usd={response.usage.estimated_cost_usd:.8f}")


def main() -> None:
    args = _parser().parse_args()
    if args.env_file.exists():
        load_dotenv_secure(args.env_file)
    settings = load_settings(args.config)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    try:
        if args.command == "doctor":
            print(render_diagnostics(collect_diagnostics(settings), args.json))
        elif args.command == "assets":
            if args.action == "install-voices":
                install_voices(args.directory)
            problems = verify_voices(args.directory)
            if problems:
                raise RuntimeError("; ".join(problems))
            print("Voice assets verified.")
        elif args.command == "budget":
            guard = _budget(settings)
            if args.action == "override":
                if not args.confirm:
                    raise RuntimeError("budget override requires --confirm")
                until = guard.enable_override(args.minutes)
                print(f"Local budget override active until {until.isoformat()}")
            else:
                print(json.dumps(asdict(guard.status()), default=str, indent=2))
        elif args.command == "test-audio":
            asyncio.run(_test_audio(settings, args.seconds))
        elif args.command == "test-tts":
            asyncio.run(_test_tts(settings, args.language, args.text))
        elif args.command == "test-api":
            asyncio.run(_test_api(settings, args.confirm_paid))
        elif args.command == "control":
            socket_path = args.socket or settings.state_dir / "control.sock"
            response = asyncio.run(send_control_command(socket_path, args.action))
            print(json.dumps(response, ensure_ascii=False, indent=2))
            if not response.get("ok"):
                raise RuntimeError(response.get("message") or response.get("error"))
        elif args.command == "run":
            if args.run_mode == "gui":
                raise RuntimeError("GUI is staged after headless hardware acceptance")
            if args.run_mode == "service":
                asyncio.run(_run_service(settings))
            else:
                asyncio.run(_run_interactive(settings))
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
