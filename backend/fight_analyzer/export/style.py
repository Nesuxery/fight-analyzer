"""Overlay style shared with the browser (shared/overlay-style.json).

The browser overlay (frontend/src/player/overlay.ts, through the generated
src/contracts/overlayStyle.ts) and the MP4 export read the same colours,
confidence threshold, limb joints and effect durations, so an effect is on
screen over the same video times in both.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

STYLE_PATH = Path(__file__).resolve().parents[3] / "shared" / "overlay-style.json"


def _bgr(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)


@dataclass(frozen=True)
class OverlayStyle:
    kp_min_conf: float
    colors: dict[str, tuple[int, int, int]]  # BGR
    strike_before_s: float
    strike_after_s: float
    contact_after_s: float
    contact_radius_px: float
    major_after_s: float
    major_fade_s: float
    limbs: dict[str, tuple[int, ...]]


def corner_hex_colors(path: Path = STYLE_PATH) -> dict[str, str]:
    """Corner colours as "#rrggbb" (the `Fighter.color` value in jobs and exports)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {side: raw["colors"][side] for side in ("red", "blue")}


@lru_cache(maxsize=1)
def load_style(path: Path = STYLE_PATH) -> OverlayStyle:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return OverlayStyle(
        kp_min_conf=float(raw["kp_min_conf"]),
        colors={name: _bgr(value) for name, value in raw["colors"].items()},
        strike_before_s=float(raw["strike_flash"]["before_s"]),
        strike_after_s=float(raw["strike_flash"]["after_s"]),
        contact_after_s=float(raw["contact_ring"]["after_s"]),
        contact_radius_px=float(raw["contact_ring"]["radius_px"]),
        major_after_s=float(raw["major_warning"]["after_s"]),
        major_fade_s=float(raw["major_warning"]["fade_s"]),
        limbs={name: tuple(int(j) for j in joints) for name, joints in raw["limbs"].items()},
    )
