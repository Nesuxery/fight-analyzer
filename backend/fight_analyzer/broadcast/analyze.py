"""Broadcast analysis of one video: scorebug clock, rounds, name suggestions,
replays and stoppages.

Two passes over the analysis video:
1. `roi_frames` frames spread over the video (random access) to find the
   clock area (or to read the names next to the user's rectangle) and to
   learn what the scorebug strip around the clock looks like;
2. one sequential pass, `sample_hz` samples per second of video: at every
   sample the strip is compared with its usual look (is the scorebug on
   screen?); `ocr_hz` times per second the clock area is read and, while the
   clock does not advance, the top and bottom bands are searched for a replay
   label.
Without the OCR model or a readable clock, rounds come from round-break
detection on the poses (low confidence), or not at all. Replays and stoppages
come from these signals plus the frame changes of the cut detection and the
poses (broadcast/replay.py).
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from fight_analyzer.config import BroadcastSettings, RulesetSettings
from fight_analyzer.contracts import (
    BroadcastNote,
    BroadcastNoteCode,
    ExcludedSegment,
    NameSuggestion,
    RoiSource,
    RoundSegment,
    ScorebugRoi,
    ScreenRect,
    VideoInfo,
)
from fight_analyzer.pose.cache import PoseArrays

from . import breaks, clock, replay, roi
from .text import parse_clock, parse_round, title_case

Reader = Callable[[np.ndarray], tuple[str, float]]
STRIP_HEIGHT = 24  # the scorebug strip is compared at this height
STRIP_MAX_WIDTH = 320


@dataclass
class BroadcastData:
    reads: list[clock.Read]
    roi: ScorebugRoi | None
    names: NameSuggestion | None
    rounds: list[RoundSegment]
    notes: list[BroadcastNote] = field(default_factory=list)
    clock_share: float = 0.0
    processing_s: float = 0.0
    segments: list[ExcludedSegment] = field(default_factory=list)  # replays, stoppages, intro / post-fight
    scorebug_frame: int | None = None
    signals: replay.Signals | None = None  # kept in the cache for checking


@dataclass
class Scan:
    """What the sequential pass saw."""

    reads: list[clock.Read]
    t: np.ndarray  # sample times, seconds
    bug: np.ndarray  # scorebug strip match per sample (NaN without a template)
    label: np.ndarray  # replay label read (held until the next read)


@dataclass
class BugTemplate:
    """The usual look of the scorebug strip: the per-pixel median over frames in which
    the clock was read. The digits change, the bar, logo and separators do not."""

    area: roi.Box
    ref: np.ndarray

    def match(self, frame: np.ndarray) -> float:
        """Zero-mean normalized correlation with the strip of `frame` (1 = the same look)."""
        a = strip_descriptor(frame, self.area)
        a = a - a.mean()
        b = self.ref - self.ref.mean()
        norm = float(np.sqrt((a * a).sum() * (b * b).sum()))
        return float((a * b).sum() / norm) if norm > 1e-6 else 0.0


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


def strip_descriptor(frame: np.ndarray, area: roi.Box) -> np.ndarray:
    gray = cv2.cvtColor(area.crop(frame), cv2.COLOR_BGR2GRAY)
    width = min(STRIP_MAX_WIDTH, max(8, round(STRIP_HEIGHT * area.w / max(1, area.h))))
    return cv2.resize(gray, (width, STRIP_HEIGHT), interpolation=cv2.INTER_AREA).astype(np.float32)


def bug_template(frames: list[np.ndarray], area: roi.ClockArea, reader: Reader,
                 s: BroadcastSettings) -> BugTemplate | None:
    """Learned from the search frames whose clock reads; None with too few of them."""
    height, width = frames[0].shape[:2]
    c = area.clock
    x = max(0, round(c.x - s.bug_strip * c.w))
    strip = roi.Box(x, c.y, min(width, round(c.x2 + s.bug_strip * c.w)) - x, min(height, c.y2) - c.y)
    if strip.w < 8 or strip.h < 4:
        return None
    seen = []
    for frame in frames:
        text, conf = reader(c.crop(frame))
        if conf >= s.min_read_conf and parse_clock(text, bare=True) is not None:
            seen.append(strip_descriptor(frame, strip))
    if len(seen) < s.bug_min_frames:
        return None
    return BugTemplate(strip, np.median(np.stack(seen), axis=0))


def replay_label(frame: np.ndarray, reader: Reader, s: BroadcastSettings) -> bool:
    """A replay label ("REPLAY", "TEKRAR"...) among the largest text boxes of the top and bottom bands."""
    height, width = frame.shape[:2]
    boxes = sorted((b for b in roi.text_boxes(frame, s) if b.w >= 2 * b.h), key=lambda b: -b.w * b.h)
    for box in boxes[:s.label_max_boxes]:
        text, conf = reader(box.padded(0.5, 0.25, width, height).crop(frame))
        if conf >= s.min_read_conf and replay.has_replay_label(text, s.replay_words):
            return True
    return False


def scan(path: Path, frame_count: int, fps: float, area: roi.ClockArea | None, template: BugTemplate | None,
         reader: Reader | None, s: BroadcastSettings, on_progress: Callable[[int], None] | None = None) -> Scan:
    """One sequential pass at `sample_hz`: scorebug strip at every sample; clock area (and
    the round box next to it) and, while the clock does not advance, the replay label at
    `ocr_hz` (the same frames as before the scorebug check existed)."""
    reads: list[clock.Read] = []
    times: list[float] = []
    bug: list[float] = []
    label: list[bool] = []
    step = fps / s.sample_hz
    if reader is None and template is None:  # nothing to look at: the sample times alone, no decoding
        count = math.ceil(frame_count / step - 1e-6) if frame_count else 0
        t = np.array([round(math.ceil(k * step - 1e-6) / fps, 4) for k in range(count)], np.float64)
        return Scan(reads=[], t=t, bug=np.full(count, np.nan, np.float32), label=np.zeros(count, bool))
    every = max(1, round(s.sample_hz / s.ocr_hz))
    next_f = 0.0
    previous: float | None = None
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
            k = len(times)
            times.append(round(f / fps, 4))
            bug.append(template.match(frame) if template is not None else float("nan"))
            seen = label[-1] if label else False
            if k % every == 0:
                value = None
                if area is not None and reader is not None:
                    text, conf = reader(area.clock.crop(frame))
                    value = parse_clock(text, bare=True) if conf >= s.min_read_conf else None
                    if value is not None:
                        number = parse_round(text)
                        if area.round is not None:
                            rtext, rconf = reader(area.round.crop(frame))
                            number = (parse_round(rtext) if rconf >= s.min_round_conf else None) or number
                        reads.append(clock.Read(t=times[-1], clock=value, round=number, conf=round(conf, 3)))
                advancing = value is not None and previous is not None and value < previous
                seen = reader is not None and not advancing and replay_label(frame, reader, s)
                previous = value
            label.append(seen)
            if on_progress and f % 300 == 0:
                on_progress(f)
    finally:
        cap.release()
    return Scan(reads=reads, t=np.asarray(times, np.float64), bug=np.asarray(bug, np.float32),
                label=np.asarray(label, bool))


def scorebug_frame(reads: list[clock.Read], found: list[clock.ClockRound], fps: float, frame_count: int,
                   s: BroadcastSettings) -> int | None:
    """A frame that certainly shows the scorebug: the clock read nearest the middle of
    the first round (of all reads without a round)."""
    usable = [r for r in reads if r.conf >= s.min_read_conf]
    if not usable:
        return None
    middle = (found[0].start_t + found[0].end_t) / 2 if found else usable[len(usable) // 2].t
    best = min(usable, key=lambda r: abs(r.t - middle))
    return min(frame_count - 1, max(0, round(best.t * fps)))


def analyze(path: Path, video: VideoInfo, load_poses: Callable[[], PoseArrays], reader: Reader | None,
            s: BroadcastSettings, ruleset: RulesetSettings, manual: ScreenRect | None = None,
            on_progress: Callable[[int], None] | None = None, *, cut_step: np.ndarray | None = None,
            cuts: Sequence[int] = (), track_id: np.ndarray | None = None) -> BroadcastData:
    """`cut_step`, `cuts` and `track_id` come from the tracking preparation (frame changes
    for the logo transitions, temporary tracks for the limb speeds); without them those
    two signals are simply not there."""
    started = time.monotonic()
    fps, frames_n, width, height = video.fps, video.frame_count, video.width, video.height
    duration = frames_n / fps
    notes: list[BroadcastNote] = []
    area: roi.ClockArea | None = None
    template: BugTemplate | None = None
    if reader is None:
        notes.append(BroadcastNote(code=BroadcastNoteCode.ocr_unavailable))
    else:
        frames, times = sample_frames(path, frames_n, fps, s.roi_frames)
        manual_box = to_box(manual, width, height) if manual else None
        area = roi.find_clock(frames, times, reader, s, manual_box) if frames else None
        if area is None:
            notes.append(BroadcastNote(code=BroadcastNoteCode.clock_not_found))
        else:
            template = bug_template(frames, area, reader, s)
    seen = scan(path, frames_n, fps, area, template, reader, s, on_progress)
    reads = seen.reads
    if manual and area is not None and not reads:
        notes.append(BroadcastNote(code=BroadcastNoteCode.roi_unreadable))
    rounds: list[RoundSegment] = []
    found: list[clock.ClockRound] = []
    if reads:
        found, inferred = clock.infer(reads, duration, s, ruleset)
        notes += inferred
        rounds = [clock.to_segment(r, fps, frames_n) for r in found]
        if not rounds:
            notes.append(BroadcastNote(code=BroadcastNoteCode.no_rounds))
    poses: PoseArrays | None = None
    if not rounds:
        poses = load_poses()
        rounds = breaks.rounds_between(breaks.break_spans(poses, fps, height, s), duration, fps,
                                       frames_n, s, ruleset)
        if rounds:
            notes.append(BroadcastNote(code=BroadcastNoteCode.rounds_from_breaks))
    samples = int(seen.t.size)
    limb_speed = np.full(samples, np.nan, np.float32)
    if track_id is not None and samples:
        limb_speed = replay.activity(poses if poses is not None else load_poses(), track_id, fps, s.sample_hz, samples)
    wipes = replay.wipe_events(cut_step, cuts, fps, s) if cut_step is not None else []
    signals = replay.Signals(t=seen.t, bug=seen.bug, label=seen.label,
                             clock=replay.clock_states(seen.t, found, s), activity=limb_speed,
                             wipes=[(a / fps, (b + 1) / fps) for a, b in wipes])
    segments = replay.detect(signals, found, fps, frames_n, s)
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
                         clock_share=clock_share, processing_s=round(time.monotonic() - started, 2),
                         segments=segments, scorebug_frame=scorebug_frame(reads, found, fps, frames_n, s),
                         signals=signals)
