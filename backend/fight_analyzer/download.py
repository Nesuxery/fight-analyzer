"""Pinned downloads for setup: a file comes only from its pinned URL and is kept
only when its size and SHA-256 match. Analysis never downloads anything.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fight_analyzer.fsutil import sha256_file


@dataclass(frozen=True)
class PinnedFile:
    name: str  # file name in the target folder
    url: str  # immutable source (release asset or a commit-pinned URL)
    size: int
    sha256: str


class DownloadError(RuntimeError):
    pass


def verify(path: Path, f: PinnedFile) -> bool:
    return path.is_file() and path.stat().st_size == f.size and sha256_file(path) == f.sha256


def fetch(f: PinnedFile, folder: Path, on_progress: Callable[[int, int], None] | None = None) -> Path:
    """Return the verified local file, downloading it if needed (never replaced by a
    file that does not match the pin)."""
    target = folder / f.name
    if verify(target, f):
        return target
    folder.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{f.name}.", suffix=".part", dir=folder)
    tmp = Path(tmp_name)
    try:
        h = hashlib.sha256()
        done = 0
        with os.fdopen(fd, "wb") as out, urllib.request.urlopen(f.url, timeout=60) as resp:
            while block := resp.read(1 << 20):
                out.write(block)
                h.update(block)
                done += len(block)
                if done > f.size:
                    raise DownloadError(f"{f.name}: download larger than expected")
                if on_progress:
                    on_progress(done, f.size)
        if done != f.size or h.hexdigest() != f.sha256:
            raise DownloadError(f"{f.name}: downloaded file does not match the pinned SHA-256")
        os.replace(tmp, target)
        return target
    except OSError as exc:
        raise DownloadError(f"{f.name}: download failed ({exc})") from exc
    finally:
        tmp.unlink(missing_ok=True)
