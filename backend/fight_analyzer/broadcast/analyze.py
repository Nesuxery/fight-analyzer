"""Broadcast analysis of one video: scorebug clock, rounds and name suggestions.

Two passes over the analysis video:
1. `roi_frames` frames spread over the video (random access) to find the
   clock area (or to read the names next to the user's rectangle);
2. one sequential pass that reads only the clock area, `ocr_hz` times per
   second of video.
Without the OCR model or a readable clock, rounds come from round-break
detection on the poses (low confidence), or not at all.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from fight_analyzer.config import BroadcastSettings, RulesetSettings
from fight_analyzer.contracts import (
    BroadcastNote,
    BroadcastNoteCode,
    NameSuggestion,
    RoiSource,
    RoundSegment,
    ScorebugRoi,
    ScreenRect,
    VideoInfo,
)
from fight_analyzer.pose.cache import PoseArrays

from . import breaks, clock, roi
from .text import parse_clock, parse_round, title_case

Reader = Callable[[np.ndarray], tuple[str, float]]


@dataclass
class BroadcastData:
    reads: list[clock.Read]
    roi: ScorebugRoi | None
    names: NameSuggestion | None
    rounds: list[RoundSegment]
    notes: list[BroadcastNote] = field(default_factory=list)
    clock_share: float = 0.0
    processing_s: float = 0.0


def to_rect(box: roi.Box, width: int, height: int) -> ScreenRect:
    return ScreenRect(x=round(box.x / width, 4), y=round(box.y / height, 4),
                      w=round(min(box.w / width, 1 - box.x / width), 4),
                      h=round(min(box.h / height, 1 - box.y / height), 4))


def to_box(rect: ScreenRect, width: int, height: int) -> roi.Box:
    x, y = round(rect.x * width), round(rect.y * height)
    return roi.Box(x, y, max(4, min(width - x, round(rect.w * width))), max(4, min(height - y, round(rect.h * height))))


def sample_frames(path: Path, frame_count: int, fps: float, n: int) -> tuple[list[np.ndarray], list[float]]:
    """`n` frames spread over the video (2 % .. 98 %), with their times."""
    frames, times = [], []
    cap = cv2.VideoCapture(str(path))
    try:
        for i in range(n):
            f = round((frame_count - 1) * (0.02 + 0.96 * i / max(1, n - 1)))
            cap.set(cv2.CAP_PROP_POS_FRAMES, f)
            ok, frame = cap.read()
            if ok:
                frames.append(frame)
                times.append(f / fps)
    finally:
        cap.release()
    return frames, times


def read_clock(path: Path, frame_count: int, fps: float, area: roi.ClockArea, reader: Reader,
               s: BroadcastSettings, on_progress: Callable[[int], None] | None = None) -> list[clock.Read]:
    """One sequential pass: the clock area (and the round box next to it) at `ocr_hz`."""
    reads: list[clock.Read] = []
    step = fps / s.ocr_hz
    next_f = 0.0
    cap = cv2.VideoCapture(str(path))
    try:
        for f in range(frame_count):
            if f + 1e-6 < next_f:
                if not cap.grab():
                    break
                continue
            ok, frame = cap.read()
            if not ok:
                break
            next_f += step
            text, conf = reader(area.clock.crop(frame))
            value = parse_clock(text, bare=True) if conf >= s.min_read_conf else None
            if value is not None:
                number = parse_round(text)
                if area.round is not None:
                    rtext, rconf = reader(area.round.crop(frame))
                    number = (parse_round(rtext) if rconf >= s.min_round_conf else None) or number
                reads.append(clock.Read(t=round(f / fps, 4), clock=value, round=number, conf=round(conf, 3)))
            if on_progress and f % 300 == 0:
                on_progress(f)
    finally:
        cap.release()
    return reads


def analyze(path: Path, video: VideoInfo, load_poses: Callable[[], PoseArrays], reader: Reader | None,
            s: BroadcastSettings, ruleset: RulesetSettings, manual: ScreenRect | None = None,
            on_progress: Callable[[int], None] | None = None) -> BroadcastData:
    started = time.monotonic()
    fps, frames_n, width, height = video.fps, video.frame_count, video.width, video.height
    duration = frames_n / fps
    notes: list[BroadcastNote] = []
    reads: list[clock.Read] = []
    area: roi.ClockArea | None = None
    if reader is None:
        notes.append(BroadcastNote(code=BroadcastNoteCode.ocr_unavailable))
    else:
        frames, times = sample_frames(path, frames_n, fps, s.roi_frames)
        manual_box = to_box(manual, width, height) if manual else None
        area = roi.find_clock(frames, times, reader, s, manual_box) if frames else None
        if area is None:
            notes.append(BroadcastNote(code=BroadcastNoteCode.clock_not_found))
        else:
            reads = read_clock(path, frames_n, fps, area, reader, s, on_progress)
            if manual and not reads:
                notes.append(BroadcastNote(code=BroadcastNoteCode.roi_unreadable))
    rounds: list[RoundSegment] = []
    if reads:
        found, inferred = clock.infer(reads, duration, s, ruleset)
        notes += inferred
        rounds = [clock.to_segment(r, fps, frames_n) for r in found]
        if not rounds:
            notes.append(BroadcastNote(code=BroadcastNoteCode.no_rounds))
    if not rounds:
        rounds = breaks.rounds_between(breaks.break_spans(load_poses(), fps, height, s), duration, fps,
                                       frames_n, s, ruleset)
        if rounds:
            notes.append(BroadcastNote(code=BroadcastNoteCode.rounds_from_breaks))
    usable = sum(1 for r in reads if r.conf >= s.min_read_conf)
    clock_share = round(min(1.0, usable / max(1.0, duration * s.ocr_hz)), 3)
    roi_out = None
    if area is not None:  # the user's rectangle: share of seconds it read as a clock
        roi_out = ScorebugRoi(clock=to_rect(area.clock, width, height),
                              source=RoiSource.manual if manual else RoiSource.auto,
                              confidence=clock_share if manual else min(1.0, area.confidence))
    names = None
    if area is not None and (area.left_name or area.right_name):
        names = NameSuggestion(left=area.left_name, right=area.right_name,
                               red=title_case(area.left_name) if area.left_name else None,
                               blue=title_case(area.right_name) if area.right_name else None,
                               confidence=min(1.0, area.names_confidence))
    return BroadcastData(reads=reads, roi=roi_out, names=names, rounds=rounds, notes=notes,
                         clock_share=clock_share, processing_s=round(time.monotonic() - started, 2))
