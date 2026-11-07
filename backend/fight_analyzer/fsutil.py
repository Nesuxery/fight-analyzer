"""Small filesystem helpers: hashing, cache keys, atomic publishing."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


def inside(root: Path, *parts: str) -> Path:
    """root/parts, refusing anything that would resolve outside root (.., absolute
    parts, drive letters, links pointing elsewhere)."""
    base = root.resolve()
    path = base.joinpath(*parts).resolve()
    if path != base and base not in path.parents:
        raise ValueError(f"path escapes {base}: {'/'.join(parts)}")
    return path


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def cache_key(inputs: dict[str, Any]) -> str:
    """Stable key from canonical JSON of everything that affects a result."""
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:40]


def write_json_atomic(path: Path, data: str) -> None:
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def write_bytes_atomic(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


@contextmanager
def staging_dir(final: Path) -> Iterator[Path]:
    """Build a directory next to `final`; on success it is renamed into place
    in one step, so readers never see a half-written cache entry. If another
    writer published `final` first, the staged copy is discarded."""
    final.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{final.name}.", dir=final.parent))
    try:
        yield stage
        try:
            os.replace(stage, final)
        except OSError:
            if not final.exists():
                raise
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
