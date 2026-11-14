"""Synthetic broadcast frames with a scorebug (Pillow; no real footage in the repo).

The background moves like a panning camera and carries a decoy clock (an
"arena screen") that moves with it; the scorebug stays at the bottom of the
screen: NAME | UFC m:ss | Rn | NAME. A countdown display shows whole seconds
rounded up, as broadcast clocks do. A script can hold a replay inside round 1:
the scorebug leaves, a "REPLAY" label is shown and the fight clock waits.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 640, 360


def clock_text(seconds_left: float) -> str:
    s = max(0, math.ceil(seconds_left - 1e-9))
    return f"{s // 60}:{s % 60:02d}"


@dataclass(frozen=True)
class Bug:
    clock: float | None  # seconds left; None = no clock shown
    round: int
    left: str = "VOLKANOVSKI"
    right: str = "3 TOPURIA"


def frame(t: float, bug: Bug | None, decoy: float | None = None, label: str | None = None) -> np.ndarray:
    img = Image.new("RGB", (W, H), (70, 110, 150))
    d = ImageDraw.Draw(img)
    shift = int(40 * t) % W
    for i in range(9):  # "arena" blocks moving with the camera
        x = (i * 83 + shift) % (W + 80) - 80
        d.rectangle([x, 60 + (i % 3) * 70, x + 50, 100 + (i % 3) * 70], fill=(30 + i * 20, 160 - i * 10, 90))
    if decoy is not None:  # arena screen clock: same kind of text, but it moves with the camera
        dx = (int(25 * t) % 300) + 40
        d.rectangle([dx - 6, 30, dx + 70, 62], fill=(10, 10, 10))
        d.text((dx, 34), clock_text(decoy), font=ImageFont.load_default(24), fill=(255, 230, 120))
    if label is not None:  # replay label: fixed on screen, top left
        d.rectangle([20, 14, 150, 50], fill=(15, 15, 18))
        d.text((28, 18), label, font=ImageFont.load_default(24), fill=(250, 250, 250))
    if bug is not None:
        y0 = int(H * 0.86)
        d.rectangle([110, y0, 530, y0 + 30], fill=(22, 22, 26))
        font = ImageFont.load_default(20)
        d.text((118, y0 + 4), bug.left, font=font, fill=(240, 240, 240))
        d.text((262, y0 + 4), "UFC", font=font, fill=(240, 240, 240))
        if bug.clock is not None:
            d.text((308, y0 + 4), clock_text(bug.clock), font=font, fill=(255, 255, 255))
        d.rectangle([362, y0 + 5, 392, y0 + 25], fill=(170, 140, 60))
        d.text((366, y0 + 6), f"R{bug.round}", font=ImageFont.load_default(16), fill=(20, 20, 20))
        d.text((420, y0 + 4), bug.right, font=font, fill=(240, 240, 240))
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


@dataclass(frozen=True)
class Script:
    """A bout as seen on a broadcast, with round length `length` (seconds)."""

    fps: float = 2.0
    length: float = 120.0
    intro: float = 5.0  # no scorebug
    break_s: float = 10.0  # between R1 and R2, scorebug hidden
    r2_stop_left: float = 70.0  # R2 stopped early (finish) with this many seconds left
    frozen: float = 5.0  # the stopped clock stays on screen
    outro: float = 6.0
    replay: tuple[float, float] | None = None  # (video time, seconds) of a replay inside round 1

    @property
    def r1(self) -> tuple[float, float]:
        return self.intro, self.intro + self.length + (self.replay[1] if self.replay else 0.0)

    @property
    def r2(self) -> tuple[float, float]:
        a = self.r1[1] + self.break_s
        return a, a + self.length - self.r2_stop_left

    @property
    def duration(self) -> float:
        return self.r2[1] + self.frozen + self.outro

    def at(self, t: float) -> np.ndarray:
        (a1, b1), (a2, b2) = self.r1, self.r2
        bug: Bug | None = None
        clock = None
        if self.replay and self.replay[0] <= t < self.replay[0] + self.replay[1]:
            return frame(t, None, label="REPLAY")
        if a1 <= t < b1:
            paused = self.replay[1] if self.replay and t >= self.replay[0] else 0.0
            clock = self.length - (t - a1 - paused)
            bug = Bug(clock, 1)
        elif a2 <= t < b2:
            clock = self.length - (t - a2)
            bug = Bug(clock, 2)
        elif b2 <= t < b2 + self.frozen:
            clock = self.r2_stop_left
            bug = Bug(clock, 2)
        return frame(t, bug, decoy=clock)


def write_video(path: Path, script: Script) -> Path:
    n = int(round(script.duration * script.fps))
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), script.fps, (W, H))
    try:
        for i in range(n):
            out.write(script.at(i / script.fps))
    finally:
        out.release()
    return path
