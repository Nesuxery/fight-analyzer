"""Official Ultralytics pose weights: pinned source, size and SHA-256.

Weights come only from the official ultralytics/assets GitHub release and
are verified against the digest GitHub publishes for that asset before they
are moved into place. Nothing else is downloaded.

    python -m fight_analyzer.pose.models [name ...]   # fetch (default model if none)
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fight_analyzer import download

RELEASE = "v8.4.0"
_BASE = f"https://github.com/ultralytics/assets/releases/download/{RELEASE}"


@dataclass(frozen=True)
class PoseWeights:
    name: str
    size: int
    sha256: str

    @property
    def url(self) -> str:
        return f"{_BASE}/{self.name}"


# Digests from https://api.github.com/repos/ultralytics/assets/releases/tags/v8.4.0
REGISTRY: dict[str, PoseWeights] = {
    w.name: w
    for w in (
        PoseWeights("yolo26n-pose.pt", 7878574,
                    "eb3bb8268828aeaf515cec23a4bfafd793944a86fe9af94ba7823609c14522a9"),
        PoseWeights("yolo26s-pose.pt", 24151790,
                    "a083adb42303728ae14c4bd6bd56d80da46f82fb2564dbd6f31dcc92ea321646"),
        PoseWeights("yolo11n-pose.pt", 6255593,
                    "869e83fcdffdc7371fa4e34cd8e51c838cc729571d1635e5141e3075e9319dc0"),
        PoseWeights("yolo11s-pose.pt", 20373161,
                    "1060bda4a27012060eca246f9b2adeea22eabb045a1e58f8d229be29b7ebc2ba"),
    )
}


class ModelError(RuntimeError):
    pass


def weights_for(name: str) -> PoseWeights:
    try:
        return REGISTRY[name]
    except KeyError:
        raise ModelError(
            f"Unknown pose model {name!r}; supported: {', '.join(sorted(REGISTRY))}"
        ) from None


def _pinned(weights: PoseWeights) -> download.PinnedFile:
    return download.PinnedFile(weights.name, weights.url, weights.size, weights.sha256)


def verify(path: Path, weights: PoseWeights) -> bool:
    return download.verify(path, _pinned(weights))


def fetch(name: str, models_dir: Path,
          on_progress: Callable[[int, int], None] | None = None) -> Path:
    """Return the verified local weights file, downloading it if needed."""
    try:
        return download.fetch(_pinned(weights_for(name)), models_dir, on_progress)
    except download.DownloadError as exc:
        raise ModelError(str(exc)) from exc


def main(argv: list[str]) -> int:
    from fight_analyzer.config import load_settings

    settings = load_settings()
    for name in argv or [settings.pose_model]:
        path = fetch(name, settings.models_dir,
                     lambda d, t: print(f"\r{name}: {d * 100 // t}%", end="", flush=True))
        print(f"\r{name}: OK  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
