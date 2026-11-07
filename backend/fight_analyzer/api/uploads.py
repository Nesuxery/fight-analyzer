"""Receiving and validating uploaded videos.

The request body is the raw file (no multipart). It is streamed to disk
while hashed, size-limited on the fly, probed with FFmpeg (header + real
frame decoding), checked against the configured limits and finally stored
by content hash in uploads/<sha256>/source.<ext>.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from pathlib import Path

import anyio
from fastapi import Request
from starlette.requests import ClientDisconnect

from fight_analyzer.config import ACCEPTED_EXTENSIONS, Settings
from fight_analyzer.contracts import SourceVideo
from fight_analyzer.media.probe import ProbeError, ProbeResult, check_decodable, probe_video

from .errors import ApiProblem

_FLUSH = 4 * 1024 * 1024


def _mb(n: float) -> str:
    return f"{n / 1024**2:,.0f} MB".replace(",", ".")


def check_extension(filename: str) -> str:
    name = Path(filename).name
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ACCEPTED_EXTENSIONS:
        raise ApiProblem(415, "unsupported_extension",
                         f"Desteklenmeyen dosya türü. İzin verilenler: "
                         f"{', '.join(e.upper() for e in ACCEPTED_EXTENSIONS)}.")
    return ext


def check_limits(probe: ProbeResult, settings: Settings) -> None:
    lim = settings.upload
    if probe.duration_s is None:
        raise ApiProblem(422, "unknown_duration", "Videonun süresi okunamadı.")
    if probe.duration_s < lim.min_duration_s:
        raise ApiProblem(422, "too_short", f"Video çok kısa (en az {lim.min_duration_s:g} sn).")
    if probe.duration_s > lim.max_duration_s:
        raise ApiProblem(422, "too_long",
                         f"Video çok uzun: {probe.duration_s / 60:.1f} dk "
                         f"(sınır {lim.max_duration_s / 60:g} dk).")
    long_side, short_side = max(probe.width, probe.height), min(probe.width, probe.height)
    if long_side > lim.max_long_side or short_side > lim.max_short_side:
        raise ApiProblem(422, "resolution_too_high",
                         f"Çözünürlük çok yüksek: {probe.width}×{probe.height} "
                         f"(sınır {lim.max_long_side}×{lim.max_short_side}).")
    if short_side < lim.min_short_side:
        raise ApiProblem(422, "resolution_too_low",
                         f"Çözünürlük çok düşük: {probe.width}×{probe.height} "
                         f"(kısa kenar en az {lim.min_short_side} px).")


async def receive_upload(request: Request, filename: str, settings: Settings) -> tuple[SourceVideo, Path]:
    """Store the request body and return the probed source + its stored path
    (relative to the data dir). Raises ApiProblem for invalid uploads."""
    ext = check_extension(filename)
    limit = settings.upload.max_bytes
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise ApiProblem(413, "file_too_large", f"Dosya {_mb(limit)} sınırını aşıyor.")
    # source + analysis copy + caches: refuse early instead of filling the disk
    expected = int(declared) if declared and declared.isdigit() else 0
    need = 2 * expected + settings.min_free_disk_bytes
    free = shutil.disk_usage(settings.data_dir).free
    if free < need:
        raise ApiProblem(507, "insufficient_storage",
                         f"Diskte yeterli boş alan yok: {_mb(free)} boş, bu yükleme için en az {_mb(need)} gerekir.")

    incoming = settings.uploads_dir / ".incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    tmp = incoming / f"{uuid.uuid4().hex}.{ext}"
    digest = hashlib.sha256()
    size = 0
    try:
        with open(tmp, "wb") as out:
            buf = bytearray()
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    raise ApiProblem(413, "file_too_large", f"Dosya {_mb(limit)} sınırını aşıyor.")
                buf += chunk
                if len(buf) >= _FLUSH:
                    data, buf = bytes(buf), bytearray()
                    await anyio.to_thread.run_sync(_write, out, digest, data)
            if buf:
                await anyio.to_thread.run_sync(_write, out, digest, bytes(buf))
        if size == 0:
            raise ApiProblem(400, "empty_file", "Dosya boş.")
        try:
            probe = await anyio.to_thread.run_sync(probe_video, tmp)
            await anyio.to_thread.run_sync(check_decodable, tmp)
        except ProbeError as exc:
            raise ApiProblem(400, exc.code, exc.message) from exc
        check_limits(probe, settings)

        sha = digest.hexdigest()
        target_dir = settings.uploads_dir / sha
        target = target_dir / f"source.{ext}"
        if target.is_file() and target.stat().st_size == size:
            tmp.unlink()  # identical content already stored
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
            os.replace(tmp, target)
    except ClientDisconnect:
        raise ApiProblem(400, "upload_aborted", "Yükleme yarıda kesildi.") from None
    finally:
        tmp.unlink(missing_ok=True)

    source = SourceVideo(
        filename=Path(filename).name[:255],
        size_bytes=size,
        sha256=sha,
        container=probe.container,
        codec=probe.codec,
        width=probe.width,
        height=probe.height,
        fps=probe.fps,
        duration_ms=(probe.duration_s or 0) * 1000,
        rotation_deg=probe.rotation_deg,  # type: ignore[arg-type]
        has_audio=probe.has_audio,
    )
    return source, target.relative_to(settings.data_dir)


def _write(out, digest, data: bytes) -> None:
    out.write(data)
    digest.update(data)


def clear_incoming(settings: Settings) -> None:
    """Remove partial uploads left by a crash (called at API start)."""
    shutil.rmtree(settings.uploads_dir / ".incoming", ignore_errors=True)
