"""Where the fighters' name labels go over the video.

Same rule and same arithmetic as the browser overlay
(frontend/src/player/labelLayout.ts); both are checked against
shared/fixtures/label-layout.json.

A label wants to sit centred above its anchor (the top of the fighter's head).
1. Every label stays inside the bounds (the picture, less a margin; in the export
   also below the top band).
2. Labels never overlap. Two that would are pushed apart sideways, each as far as
   it can go while still covering its own anchor horizontally.
3. If that is not enough, they are stacked: the label with the higher anchor goes
   on top (the left one on a tie); without room above, the other one goes below it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

# Rounding slack, so labels exactly `gap` apart do not count as overlapping.
EPS = 1e-6


@dataclass(frozen=True)
class LabelRequest:
    ax: float  # anchor: centre x the label wants
    ay: float  # anchor: bottom y the label wants
    w: float  # size of the label, outline included
    h: float


@dataclass(frozen=True)
class LabelBounds:
    left: float
    top: float
    right: float
    bottom: float


@dataclass
class _Box:
    ax: float
    ay: float
    w: float
    h: float
    x: float
    y: float


def _clamp(v: float, lo: float, hi: float) -> float:
    """lo when the range is empty (a label larger than the bounds sticks to the left or top)."""
    return lo if hi < lo else min(max(v, lo), hi)


def _overlap(a: _Box, c: _Box, gap: float) -> bool:
    return (a.x < c.x + c.w + gap - EPS and c.x < a.x + a.w + gap - EPS
            and a.y < c.y + c.h + gap - EPS and c.y < a.y + a.h + gap - EPS)


def _separate(a: _Box, c: _Box, b: LabelBounds, gap: float) -> None:
    """a is the label with the left anchor, c the one with the right anchor."""
    need = a.x + a.w + gap - c.x
    room_a = max(0.0, min(a.x - b.left, a.x + a.w - a.ax))
    room_c = max(0.0, min(b.right - (c.x + c.w), c.ax - c.x))
    if need <= room_a + room_c:
        d_a = min(room_a, need / 2)
        d_c = need - d_a
        if d_c > room_c:
            d_c = room_c
            d_a = need - d_c
        a.x -= d_a
        c.x += d_c
        return
    upper, lower = (c, a) if c.ay < a.ay else (a, c)
    y = lower.y - gap - upper.h
    if y >= b.top:
        upper.y = y
        return
    upper.y = b.top
    lower.y = _clamp(upper.y + upper.h + gap, b.top, b.bottom - lower.h)


def place_labels(labels: Sequence[LabelRequest], bounds: LabelBounds, gap: float) -> list[tuple[float, float]]:
    """Top-left corners, in the order of `labels`."""
    boxes = [_Box(l.ax, l.ay, l.w, l.h,
                  _clamp(l.ax - l.w / 2, bounds.left, bounds.right - l.w),
                  _clamp(l.ay - l.h, bounds.top, bounds.bottom - l.h)) for l in labels]
    order = sorted(range(len(boxes)), key=lambda i: (boxes[i].ax, i))
    for _ in range(len(boxes)):
        moved = False
        for p in range(len(order)):
            for q in range(p + 1, len(order)):
                a, c = boxes[order[p]], boxes[order[q]]
                if not _overlap(a, c, gap):
                    continue
                _separate(a, c, bounds, gap)
                moved = True
        if not moved:
            break
    return [(box.x, box.y) for box in boxes]
