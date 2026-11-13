"""Scorebug text recognition model: pinned source, size and SHA-256.

PaddleOCR "en_PP-OCRv5_mobile_rec" (ONNX, Apache-2.0, PaddlePaddle Authors),
from the PaddlePaddle organisation on Hugging Face, pinned to one commit. It is
downloaded only by setup or by this command, never during an analysis; without
it the scorebug clock is not read and rounds come from break detection or the
user.

    python -m fight_analyzer.broadcast.ocr_model   # fetch both files
"""

from __future__ import annotations

import sys
from pathlib import Path

from fight_analyzer import download

NAME = "en_PP-OCRv5_mobile_rec"
REPO = "https://huggingface.co/PaddlePaddle/en_PP-OCRv5_mobile_rec_onnx"
COMMIT = "3fafbc3b5dcf93dd72add9f48368be8a3a2cd33b"
LICENSE = "Apache-2.0"
FOLDER = "ocr"  # inside the models folder


def _pinned(remote: str, local: str, size: int, sha256: str) -> download.PinnedFile:
    return download.PinnedFile(local, f"{REPO}/resolve/{COMMIT}/{remote}", size, sha256)


MODEL = _pinned("inference.onnx", f"{NAME}.onnx", 7848423,
                "b5f833dfc5d0eb71da397b4efa06ebeee9b431b690a47d6af40d77d8eabc557f")
CONFIG = _pinned("inference.yml", f"{NAME}.yml", 3964,
                 "27e91d0582f40168aa218303c76e184bc78fa7a5d105aad0cfbad8458b441067")
FILES = (MODEL, CONFIG)


def folder(models_dir: Path) -> Path:
    return models_dir / FOLDER


def installed(models_dir: Path) -> bool:
    return all(download.verify(folder(models_dir) / f.name, f) for f in FILES)


def model_id() -> str:
    """Identity of the recognizer for cache keys."""
    return f"{NAME}@{MODEL.sha256[:16]}"


def main(argv: list[str]) -> int:
    from fight_analyzer.config import load_settings

    target = folder(load_settings().models_dir)
    for f in FILES:
        path = download.fetch(f, target, lambda d, t, n=f.name: print(f"\r{n}: {d * 100 // t}%", end="", flush=True))
        print(f"\r{f.name}: OK  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
