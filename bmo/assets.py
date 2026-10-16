from __future__ import annotations

import hashlib
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class Asset:
    name: str
    url: str
    sha256: str


VOICE_ASSETS = (
    Asset(
        "ru_RU-dmitri-medium.onnx",
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/dmitri/medium/ru_RU-dmitri-medium.onnx",
        "f073356ebc4bd0f80c5af58df2953a5988bd5bdab1eb38635ce960b071fbefcb",
    ),
    Asset(
        "ru_RU-dmitri-medium.onnx.json",
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/dmitri/medium/ru_RU-dmitri-medium.onnx.json",
        "667ef3117bc642c2892dff7690d8bdc8ca4228aeaa783b2dc1416df632855e0d",
    ),
    Asset(
        "en_US-kristin-medium.onnx",
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/kristin/medium/en_US-kristin-medium.onnx",
        "5849957f929cbf720c258f8458692d6103fff2f0e3d3b19c8259474bb06a18d4",
    ),
    Asset(
        "en_US-kristin-medium.onnx.json",
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/kristin/medium/en_US-kristin-medium.onnx.json",
        "5681426d4aead22195de70531eeeeddb46493cfaffc5764b2ea3db73428b651c",
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_voices(directory: Path) -> list[str]:
    problems = []
    for asset in VOICE_ASSETS:
        path = directory / asset.name
        if not path.exists():
            problems.append(f"missing: {path}")
        elif sha256_file(path) != asset.sha256:
            problems.append(f"checksum mismatch: {path}")
    return problems


def install_voices(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for asset in VOICE_ASSETS:
        target = directory / asset.name
        if target.exists() and sha256_file(target) == asset.sha256:
            continue
        temporary = target.with_suffix(target.suffix + ".part")
        response = urllib.request.urlopen(asset.url, timeout=120)
        with response, temporary.open("wb") as out:
            while chunk := response.read(1024 * 1024):
                out.write(chunk)
        actual = sha256_file(temporary)
        if actual != asset.sha256:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(f"checksum mismatch for {asset.name}: {actual}")
        temporary.replace(target)
