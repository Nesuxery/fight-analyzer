"""Finding the scorebug clock on screen.

Broadcast graphics stay at one place on screen while the camera moves, so the
clock is a text box that (1) appears at the same position in many of the
frames searched, (2) reads as m:ss and (3) counts down with the video. Clocks
on the arena screens move with the camera and fail (1). Text boxes on the
same row left and right of the clock are the name slots (name suggestions);
a box next to it reading "R1" is the round number.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

import cv2
import numpy as np

from fight_analyzer.config import BroadcastSettings

from .text import clean_name, parse_clock, parse_round

Reader = Callable[[np.ndarray], tuple[str, float]]
MAX_READS = 16  # OCR reads per persistent box


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h

    def iou(self, o: Box) -> float:
        ix = max(0, min(self.x2, o.x2) - max(self.x, o.x))
        iy = max(0, min(self.y2, o.y2) - max(self.y, o.y))
        inter = ix * iy
        return inter / float(self.w * self.h + o.w * o.h - inter) if inter else 0.0

    def padded(self, fx: float, fy: float, width: int, height: int) -> Box:
        px, py = round(self.h * fx), round(self.h * fy)
        x, y = max(0, self.x - px), max(0, self.y - py)
        return Box(x, y, min(width, self.x2 + px) - x, min(height, self.y2 + py) - y)

    def crop(self, frame: np.ndarray) -> np.ndarray:
        return frame[self.y:self.y2, self.x:self.x2]


def union(boxes: list[Box]) -> Box:
    x, y = min(b.x for b in boxes), min(b.y for b in boxes)
    return Box(x, y, max(b.x2 for b in boxes) - x, max(b.y2 for b in boxes) - y)


def text_boxes(frame: np.ndarray, s: BroadcastSettings) -> list[Box]:
    """Text line candidates in the top and bottom bands of one frame."""
    height, width = frame.shape[:2]
    scale = height / 1080.0
    band = max(8, round(height * s.band_share))
    out: list[Box] = []
    grad_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    join = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, round(9 * scale)), 1))
    for y0 in (0, height - band):
        gray = cv2.cvtColor(frame[y0:y0 + band], cv2.COLOR_BGR2GRAY)
        grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, grad_kernel)
        _, bw = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        joined = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, join)
        n, _, stats, _ = cv2.connectedComponentsWithStats(joined, connectivity=8)
        for i in range(1, n):
            x, y, w, h, area = (int(v) for v in stats[i])
            if not s.min_text_px * scale <= h <= s.max_text_px * scale:
                continue
            if w < 0.8 * h or w > 0.5 * width or not 0.15 <= area / (w * h) <= 0.95:
                continue
            out.append(Box(x, y + y0, w, h))
    return out


@dataclass
class Track:
    """One screen position across the searched frames."""

    members: list[tuple[int, Box]] = field(default_factory=list)  # (frame number in the search, box)

    @property
    def box(self) -> Box:
        b = [m[1] for m in self.members]
        return Box(*(int(np.median([getattr(x, k) for x in b])) for k in ("x", "y", "w", "h")))

    def frames(self) -> list[int]:
        return sorted({k for k, _ in self.members})


def persistent(per_frame: list[list[Box]], min_share: float) -> list[Track]:
    tracks: list[Track] = []
    for k, boxes in enumerate(per_frame):
        for b in boxes:
            best, score = None, 0.5
            for tr in tracks:
                ref = tr.members[-1][1]
                iou = ref.iou(b)
                if iou >= score and 0.7 <= b.h / ref.h <= 1.4:
                    best, score = tr, iou
            if best is None:
                tracks.append(Track([(k, b)]))
            else:
                best.members.append((k, b))
    need = max(3, int(np.ceil(min_share * len(per_frame))))
    return [tr for tr in tracks if len(tr.frames()) >= need]


@dataclass
class TrackReads:
    track: Track
    area: Box
    texts: list[tuple[int, str, float]]  # (frame number in the search, text, confidence)


def read_tracks(tracks: list[Track], frames: list[np.ndarray], reader: Reader) -> list[TrackReads]:
    out = []
    for tr in tracks:
        height, width = frames[0].shape[:2]
        area = union([b for _, b in tr.members]).padded(0.5, 0.25, width, height)
        ks = tr.frames()
        if len(ks) > MAX_READS:
            ks = [ks[round(i * (len(ks) - 1) / (MAX_READS - 1))] for i in range(MAX_READS)]
        texts = []
        for k in ks:
            text, conf = reader(area.crop(frames[k]))
            texts.append((k, text, conf))
        out.append(TrackReads(tr, area, texts))
    return out


@dataclass
class ClockArea:
    clock: Box
    round: Box | None
    confidence: float  # share of reads there that parsed as a clock
    left_name: str | None = None
    right_name: str | None = None
    names_confidence: float = 0.0


def _round_reading_area(clock_box: Box, found: Box, width: int) -> Box:
    """The round box widened away from the clock: its text moves when an indicator
    (e.g. a bar before 'R2') appears, so the box learned from the frames searched
    can be too tight for later rounds."""
    slack = round(1.5 * found.h)
    if found.x >= clock_box.x2 - found.h:  # right of the clock
        x = max(clock_box.x2, found.x - found.h)
        return Box(x, found.y, min(width, found.x2 + slack) - x, found.h)
    x2 = min(clock_box.x, found.x2 + found.h)
    x = max(0, found.x - slack)
    return Box(x, found.y, x2 - x, found.h)


def _same_row(a: Box, b: Box) -> bool:
    overlap = min(a.y2, b.y2) - max(a.y, b.y)
    return overlap >= 0.5 * min(a.h, b.h)


def _countdown_share(reads: list[tuple[float, float]], tol: float) -> float:
    """Share of consecutive (time, clock) pairs that fit a running/paused clock or a reset."""
    pts = sorted(reads)
    if len(pts) < 2:
        return 0.0
    ok = sum(1 for (t0, c0), (t1, c1) in zip(pts, pts[1:]) if c0 - c1 <= (t1 - t0) + tol)
    return ok / (len(pts) - 1)


def _vote(texts: list[str]) -> tuple[str | None, float]:
    names = [n for n in (clean_name(t) for t in texts) if n]
    if not names:
        return None, 0.0
    name, count = Counter(names).most_common(1)[0]
    if count < 2:
        return None, 0.0
    return name, count / len(texts)


def find_clock(frames: list[np.ndarray], times: list[float], reader: Reader, s: BroadcastSettings,
               manual: Box | None = None) -> ClockArea | None:
    """Clock (and round number / name slots next to it) from frames spread over the video."""
    per_frame = [text_boxes(f, s) for f in frames]
    reads = read_tracks(persistent(per_frame, s.min_presence), frames, reader)
    usable = lambda txt: [(k, t) for k, t, c in txt.texts if c >= s.min_read_conf]  # noqa: E731
    clock_area: Box | None = manual
    confidence = 0.0
    best = None
    if manual is None:
        best_score = 0.0
        for tr in reads:
            got = usable(tr)
            clocks = [(times[k], v) for k, t in got if (v := parse_clock(t)) is not None]
            share = len(clocks) / max(1, len(tr.texts))
            if share < s.min_clock_share:
                continue
            score = share * _countdown_share(clocks, s.run_tolerance_s) * len(tr.track.frames()) / len(frames)
            if score > best_score:
                best, best_score, confidence = tr, score, share
        if best is None:
            return None
        clock_area = best.area
    assert clock_area is not None
    row = [tr for tr in reads if tr is not best and _same_row(tr.area, clock_area)]
    round_box = None
    near = sorted((tr for tr in row if abs(tr.area.x - clock_area.x2) <= 6 * clock_area.h
                   or abs(clock_area.x - tr.area.x2) <= 6 * clock_area.h),
                  key=lambda tr: min(abs(tr.area.x - clock_area.x2), abs(clock_area.x - tr.area.x2)))
    for tr in near:
        got = [(k, t) for k, t, c in tr.texts if c >= s.min_round_conf]
        if got and sum(parse_round(t) is not None for _, t in got) >= 0.5 * len(got):
            round_box = _round_reading_area(clock_area, tr.area, frames[0].shape[1])
            break
    left = [t for tr in row if tr.area.x2 <= clock_area.x for _, t in usable(tr)]
    right = [t for tr in row if tr.area.x >= clock_area.x2 for _, t in usable(tr)]
    left_name, lc = _vote(left)
    right_name, rc = _vote(right)
    return ClockArea(clock=clock_area, round=round_box, confidence=round(confidence, 3) if manual is None else 0.0,
                     left_name=left_name, right_name=right_name,
                     names_confidence=round(min(lc, rc) if left_name and right_name else max(lc, rc) / 2, 2))
