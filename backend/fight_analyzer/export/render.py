"""Draws the analysis overlay onto video frames for the MP4 export.

The drawing follows the browser overlay (frontend/src/player/overlay.ts):
fighters' skeletons in the corner colours with a dark under-stroke and a
modest glow, dashed while the identity is kept through an overlap, other
people thin and grey, joints below the confidence threshold not drawn. The
effects and their timing come from frames.effects_at (shared style file).
The top band shows the experimental momentum and counters with the same
numbers as the browser; identity problems and "insufficient data" are always
shown and never covered by an effect.

Text goes through Pillow (Turkish characters) and is cached as small RGBA
patches that are alpha-blended into the frame.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from fight_analyzer.contracts import EventType, ExportOptions, FighterId, FrameRecord

from .frames import Effects, FrameMetrics
from .style import OverlayStyle

BONES = ((5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16))
FACE = (0, 1, 2, 3, 4)
SHIFT = 4  # sub-pixel precision of OpenCV drawing (1/16 px)
ONE = 1 << SHIFT
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
MUTED = (189, 178, 166)  # BGR of #a6b2bd
STATE_TEXT = {"occluded": "Örtüşme", "uncertain": "Takip belirsiz"}
MAJOR_TEXT = {EventType.knockdown: "OLASI KNOCKDOWN", EventType.takedown: "OLASI TAKEDOWN"}
CAPTION = "Deneysel momentum — kazanma olasılığı değildir"
FOOTNOTE = "Fight Analyzer · 2B poz tahmini: vuruşlar deneme; temas, knockdown ve takedown olasıdır"
FONT_DIR = Path(r"C:\Windows\Fonts")
BOLD_FONTS = ("bahnschrift.ttf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf")
REGULAR_FONTS = ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf")


@lru_cache(maxsize=64)
def _font(size: int, bold: bool) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in BOLD_FONTS if bold else REGULAR_FONTS:
        for path in (FONT_DIR / name, Path(name)):
            try:
                font = ImageFont.truetype(str(path), size)
            except OSError:
                continue
            if bold and name == "bahnschrift.ttf":
                try:
                    font.set_variation_by_name("Bold")
                except (OSError, ValueError):
                    pass
            return font
    return ImageFont.load_default(size)


@dataclass
class _Patch:
    bgr: np.ndarray  # [h, w, 3] float32
    alpha: np.ndarray  # [h, w, 1] float32 0..1


@dataclass
class _TextCache:
    patches: dict[tuple, _Patch] = field(default_factory=dict)

    def get(self, text: str, size: int, color: tuple[int, int, int], bold: bool = True,
            outline: int = 0) -> _Patch:
        key = (text, size, color, bold, outline)
        patch = self.patches.get(key)
        if patch is None:
            font = _font(size, bold)
            box = font.getbbox(text, stroke_width=outline)
            w, h = max(1, box[2] - box[0]), max(1, box[3] - box[1])
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ImageDraw.Draw(img).text((-box[0], -box[1]), text, font=font, fill=(*color[::-1], 255),
                                     stroke_width=outline, stroke_fill=(0, 0, 0, 230))
            rgba = np.asarray(img, dtype=np.float32)
            patch = _Patch(bgr=rgba[..., 2::-1].copy(), alpha=rgba[..., 3:4] / 255)
            if len(self.patches) > 2000:
                self.patches.clear()
            self.patches[key] = patch
        return patch


def _blit(frame: np.ndarray, patch: _Patch, x: float, y: float, opacity: float = 1.0) -> None:
    h, w = patch.alpha.shape[:2]
    x0, y0 = int(round(x)), int(round(y))
    fx0, fy0 = max(0, x0), max(0, y0)
    fx1, fy1 = min(frame.shape[1], x0 + w), min(frame.shape[0], y0 + h)
    if fx0 >= fx1 or fy0 >= fy1:
        return
    a = patch.alpha[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0] * opacity
    src = patch.bgr[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    roi = frame[fy0:fy1, fx0:fx1]
    roi[:] = (src * a + roi * (1 - a)).astype(np.uint8)


def _pt(x: float, y: float) -> tuple[int, int]:
    return int(round(x * ONE)), int(round(y * ONE))


def _thick(v: float) -> int:
    return max(1, int(round(v)))


def _mix(color: tuple[int, int, int], other: tuple[int, int, int], k: float) -> tuple[int, int, int]:
    return tuple(int(round(c + (o - c) * k)) for c, o in zip(color, other))  # type: ignore[return-value]


def _dashed(img: np.ndarray, a: tuple[float, float], b: tuple[float, float], color, thickness: int,
            dash: float, gap: float) -> None:
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    if length < 1e-6:
        return
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    s = 0.0
    while s < length:
        e = min(length, s + dash)
        cv2.line(img, _pt(a[0] + ux * s, a[1] + uy * s), _pt(a[0] + ux * e, a[1] + uy * e), color, thickness,
                 cv2.LINE_AA, SHIFT)
        s = e + gap


def _blend_region(frame: np.ndarray, layer: np.ndarray, x0: int, y0: int, x1: int, y1: int, alpha: float) -> None:
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(frame.shape[1], x1), min(frame.shape[0], y1)
    if x0 < x1 and y0 < y1 and alpha > 0:
        cv2.addWeighted(layer[y0:y1, x0:x1], alpha, frame[y0:y1, x0:x1], 1 - alpha, 0, dst=frame[y0:y1, x0:x1])


@dataclass
class _Person:
    kp: np.ndarray  # [17, 3] x, y, confidence (rounded as served to the browser)
    role: str  # "red" | "blue" | "other"
    state: str  # tracked | occluded
    label: str | None


class Renderer:
    def __init__(self, width: int, height: int, names: dict[str, str], options: ExportOptions,
                 style: OverlayStyle) -> None:
        self.w, self.h = width, height
        self.names = names
        self.options = options
        self.style = style
        self.px = max(1.0, min(width, height) / 540)  # one "CSS pixel" of the browser overlay
        self.text = _TextCache()

    # ---- people ----------------------------------------------------------

    def people(self, record: FrameRecord | None) -> list[_Person]:
        if record is None:
            return []
        states = {s.fighter_id: s.state for s in record.fighters}
        out = []
        for d in record.detections:
            kp = np.array([(k.x, k.y, k.confidence) for k in d.keypoints], dtype=np.float64)
            if d.fighter_id is not None:
                side = "red" if d.fighter_id == FighterId.fighter_a else "blue"
                state = "occluded" if states.get(d.fighter_id) == "occluded" else "tracked"
                out.append(_Person(kp, side, state, self.names[side]))
            else:
                out.append(_Person(kp, "other", "tracked", None))
        return out

    def _ok(self, kp: np.ndarray, i: int) -> bool:
        return i < kp.shape[0] and kp[i, 2] >= self.style.kp_min_conf

    def _bounds(self, kp: np.ndarray, pad: float) -> tuple[int, int, int, int] | None:
        ok = kp[:, 2] >= self.style.kp_min_conf
        if not ok.any():
            return None
        xs, ys = kp[ok, 0], kp[ok, 1]
        return (int(xs.min() - pad), int(ys.min() - pad), int(xs.max() + pad) + 1, int(ys.max() + pad) + 1)

    def _bones(self, img: np.ndarray, kp: np.ndarray, color, thickness: int, dashed: bool) -> None:
        px = self.px
        for a, b in BONES:
            if not (self._ok(kp, a) and self._ok(kp, b)):
                continue
            pa, pb = (kp[a, 0], kp[a, 1]), (kp[b, 0], kp[b, 1])
            if dashed:
                _dashed(img, pa, pb, color, thickness, 7 * px, 5 * px)
            else:
                cv2.line(img, _pt(*pa), _pt(*pb), color, thickness, cv2.LINE_AA, SHIFT)

    def _person(self, frame: np.ndarray, p: _Person) -> None:
        px, kp = self.px, p.kp
        box = self._bounds(kp, 40 * px)
        if box is None:
            return
        color = self.style.colors[p.role]
        dashed = p.state == "occluded"
        x0, y0, x1, y1 = self._clip(box)
        if x0 >= x1 or y0 >= y1:
            return
        local = kp - np.array([x0, y0, 0])
        roi = frame[y0:y1, x0:x1]
        if p.role == "other":  # thin, grey, translucent
            layer = roi.copy()
            self._bones(layer, local, color, _thick(1.5 * px), dashed)
            cv2.addWeighted(layer, 0.55, roi, 0.45, 0, dst=roi)
            return
        # dark under-stroke for contrast, then a modest glow, then the coloured bones
        under = roi.copy()
        self._bones(under, local, BLACK, _thick(5.5 * px), dashed)
        cv2.addWeighted(under, 0.55, roi, 0.45, 0, dst=roi)
        glow = np.zeros_like(roi)
        self._bones(glow, local, color, _thick(5 * px), dashed)
        glow = cv2.GaussianBlur(glow, (0, 0), 3 * px)
        cv2.add(roi, (glow * 0.6).astype(np.uint8), dst=roi)
        self._bones(roi, local, color, _thick(2.6 * px), dashed)
        for i in range(5, kp.shape[0]):
            if self._ok(kp, i):
                c = _pt(local[i, 0], local[i, 1])
                cv2.circle(roi, c, int(3.2 * px * ONE), color, -1, cv2.LINE_AA, SHIFT)
                cv2.circle(roi, c, int(3.2 * px * ONE), BLACK, _thick(1.2 * px), cv2.LINE_AA, SHIFT)
        # head ring from the face points, as in the browser
        face = [kp[i] for i in FACE if self._ok(kp, i)]
        top = None
        if len(face) >= 2:
            cx = sum(f[0] for f in face) / len(face)
            cy = sum(f[1] for f in face) / len(face)
            spread = max(math.hypot(f[0] - cx, f[1] - cy) for f in face)
            torso = self._torso(kp)
            r = max(spread * 1.7, torso * 0.22 if torso else 0, 9 * px)
            cv2.circle(frame, _pt(cx, cy), int(r * ONE), color, _thick(2 * px), cv2.LINE_AA, SHIFT)
            top = (cx, cy - r - 4 * px)
        else:
            ok = kp[:, 2] >= self.style.kp_min_conf
            if ok.any():
                j = int(np.argmin(np.where(ok, kp[:, 1], np.inf)))
                top = (kp[j, 0], kp[j, 1] - 10 * px)
        if p.label and top:
            patch = self.text.get(p.label, _thick(13 * px), color, outline=_thick(2 * px))
            _blit(frame, patch, top[0] - patch.alpha.shape[1] / 2, top[1] - patch.alpha.shape[0])

    def _torso(self, kp: np.ndarray) -> float | None:
        if not all(self._ok(kp, i) for i in (5, 6, 11, 12)):
            return None
        return math.hypot((kp[5, 0] + kp[6, 0] - kp[11, 0] - kp[12, 0]) / 2,
                          (kp[5, 1] + kp[6, 1] - kp[11, 1] - kp[12, 1]) / 2)

    def _clip(self, box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        return max(0, box[0]), max(0, box[1]), min(self.w, box[2]), min(self.h, box[3])

    def body_center(self, kp: np.ndarray) -> tuple[float, float] | None:
        for a, b in ((11, 12), (5, 6)):
            if self._ok(kp, a) and self._ok(kp, b):
                return (kp[a, 0] + kp[b, 0]) / 2, (kp[a, 1] + kp[b, 1]) / 2
        return None

    # ---- effects ---------------------------------------------------------

    def _effects(self, frame: np.ndarray, effects: Effects, people: list[_Person]) -> None:
        px, style = self.px, self.style
        by_side = {p.role: p for p in people if p.role != "other"}
        for fl in effects.flashes:
            e = fl.event
            side = "red" if e.actor == FighterId.fighter_a else "blue" if e.actor == FighterId.fighter_b else None
            color = style.colors[side] if side else WHITE
            bright = _mix(color, WHITE, 0.45)
            person = by_side.get(side) if side else None
            joints = style.limbs.get(e.limb.value) if e.limb else None
            layer = frame.copy()
            drawn = False
            if person is not None and joints:
                kp = person.kp
                for a, b in zip(joints, joints[1:]):
                    if self._ok(kp, a) and self._ok(kp, b):
                        cv2.line(layer, _pt(kp[a, 0], kp[a, 1]), _pt(kp[b, 0], kp[b, 1]), bright, _thick(6 * px),
                                 cv2.LINE_AA, SHIFT)
                        drawn = True
                end = joints[-1]
                if self._ok(kp, end):
                    cv2.circle(layer, _pt(kp[end, 0], kp[end, 1]), int(6 * px * ONE), bright, -1, cv2.LINE_AA, SHIFT)
                    drawn = True
            if not drawn and e.location is not None:
                cv2.circle(layer, _pt(e.location.x, e.location.y), int(6 * px * ONE), bright, _thick(2.5 * px),
                           cv2.LINE_AA, SHIFT)
            cv2.addWeighted(layer, 0.75 * fl.strength, frame, 1 - 0.75 * fl.strength, 0, dst=frame)
        for ring in effects.rings:
            loc = ring.event.location
            layer = frame.copy()
            r = style.contact_radius_px * px
            cv2.circle(layer, _pt(loc.x, loc.y), int(r * ONE), style.colors["amber"], _thick(2.5 * px), cv2.LINE_AA,
                       SHIFT)
            cv2.addWeighted(layer, ring.strength, frame, 1 - ring.strength, 0, dst=frame)
            if ring.labelled:
                patch = self.text.get("olası temas", _thick(12 * px), style.colors["amber"], outline=_thick(2 * px))
                _blit(frame, patch, loc.x + r + 6 * px, loc.y - r - patch.alpha.shape[0], ring.strength)

    def _warnings(self, frame: np.ndarray, effects: Effects, top: float) -> None:
        px, style = self.px, self.style
        y = top
        for w in effects.warnings:
            e = w.event
            side = "red" if e.actor == FighterId.fighter_a else "blue" if e.actor == FighterId.fighter_b else None
            who = f" · {self.names[side]}" if side else ""
            text = self.text.get(f"{MAJOR_TEXT[e.type]}{who}", _thick(15 * px), (20, 20, 20))
            th, tw = text.alpha.shape[:2]
            icon = 14 * px
            pad = 8 * px
            bw, bh = tw + icon + 3 * pad, max(th, icon) + 2 * pad
            x = (self.w - bw) / 2
            layer = frame.copy()
            cv2.rectangle(layer, _pt(x, y), _pt(x + bw, y + bh), style.colors["warning"], -1, cv2.LINE_AA, SHIFT)
            cx, cy = x + pad + icon / 2, y + bh / 2
            tri = np.array([_pt(cx, cy - icon / 2), _pt(cx + icon / 2, cy + icon / 2), _pt(cx - icon / 2, cy + icon / 2)])
            cv2.fillPoly(layer, [tri], (20, 20, 20), cv2.LINE_AA, SHIFT)
            cv2.line(layer, _pt(cx, cy - icon * 0.15), _pt(cx, cy + icon * 0.2), style.colors["warning"], _thick(2 * px),
                     cv2.LINE_AA, SHIFT)
            cv2.circle(layer, _pt(cx, cy + icon * 0.34), int(1.2 * px * ONE), style.colors["warning"], -1, cv2.LINE_AA,
                       SHIFT)
            a = 0.92 * w.strength
            cv2.addWeighted(layer, a, frame, 1 - a, 0, dst=frame)
            _blit(frame, text, x + 2 * pad + icon, y + (bh - th) / 2, w.strength)
            y += bh + 6 * px

    def _distance(self, frame: np.ndarray, people: list[_Person], value: float | None) -> None:
        red = next((p for p in people if p.role == "red"), None)
        blue = next((p for p in people if p.role == "blue"), None)
        a = self.body_center(red.kp) if red else None
        b = self.body_center(blue.kp) if blue else None
        if not (a and b):
            return
        px = self.px
        _dashed(frame, a, b, (235, 235, 235), _thick(2 * px), 8 * px, 6 * px)
        for p in (a, b):
            cv2.circle(frame, _pt(*p), int(4 * px * ONE), WHITE, -1, cv2.LINE_AA, SHIFT)
        if value is not None:
            patch = self.text.get(f"{value:.1f}".replace(".", ",") + " gövde boyu", _thick(12 * px), WHITE,
                                  outline=_thick(2 * px))
            _blit(frame, patch, (a[0] + b[0]) / 2 - patch.alpha.shape[1] / 2,
                  (a[1] + b[1]) / 2 - 8 * px - patch.alpha.shape[0])

    # ---- top band, badges, footnote --------------------------------------

    def _band(self, frame: np.ndarray, metrics: FrameMetrics, i: int) -> float:
        o = self.options
        if not (o.momentum or o.counters):
            return 8 * self.px
        px, style = self.px, self.style
        band = _thick((62 if o.counters else 50) * px)
        frame[:band] = (frame[:band] * 0.3).astype(np.uint8)
        margin = 14 * px
        for side in ("red", "blue"):
            color = style.colors[side]
            name = self.text.get(self.names[side], _thick(19 * px), color)
            nx = margin if side == "red" else self.w - margin - name.alpha.shape[1]
            _blit(frame, name, nx, 8 * px)
            if o.counters:
                st = metrics.stats[side]
                text = f"Vuruş {st['strike_attempts'][i]} · Tekme {st['kick_attempts'][i]}"
                if st["significant"][i]:
                    text += f" · Olası büyük olay {st['significant'][i]}"
                small = self.text.get(text, _thick(12 * px), (225, 220, 214), bold=False)
                sx = margin if side == "red" else self.w - margin - small.alpha.shape[1]
                _blit(frame, small, sx, 8 * px + name.alpha.shape[0] + 7 * px)
        if o.momentum:
            red = int(metrics.red_shown[i])
            bar_w = min(self.w * 0.34, 400 * px)
            bar_h = 12 * px
            x0 = (self.w - bar_w) / 2
            y0 = 12 * px
            split = x0 + bar_w * red / 100
            cv2.rectangle(frame, _pt(x0, y0), _pt(split, y0 + bar_h), style.colors["red"], -1, cv2.LINE_AA, SHIFT)
            cv2.rectangle(frame, _pt(split, y0), _pt(x0 + bar_w, y0 + bar_h), style.colors["blue"], -1, cv2.LINE_AA,
                          SHIFT)
            cv2.line(frame, _pt(x0 + bar_w / 2, y0 - 3 * px), _pt(x0 + bar_w / 2, y0 + bar_h + 3 * px), WHITE,
                     _thick(1.5 * px), cv2.LINE_AA, SHIFT)
            for value, side in ((red, "red"), (100 - red, "blue")):
                num = self.text.get(f"{value}%", _thick(17 * px), style.colors[side])
                nx = x0 - 8 * px - num.alpha.shape[1] if side == "red" else x0 + bar_w + 8 * px
                _blit(frame, num, nx, y0 + bar_h / 2 - num.alpha.shape[0] / 2)
            cap = self.text.get(CAPTION, _thick(11 * px), MUTED, bold=False)
            cy = y0 + bar_h + 7 * px
            tag_text = "Dışlanan bölüm" if metrics.excluded[i] else "Veri yetersiz" if metrics.insufficient[i] else None
            if tag_text:
                tag = self.text.get(tag_text, _thick(11 * px), (20, 20, 20))
                tw = tag.alpha.shape[1] + 10 * px
                total = cap.alpha.shape[1] + 8 * px + tw
                cx = (self.w - total) / 2
                _blit(frame, cap, cx, cy)
                tx = cx + cap.alpha.shape[1] + 8 * px
                cv2.rectangle(frame, _pt(tx, cy - 2 * px), _pt(tx + tw, cy + tag.alpha.shape[0] + 3 * px),
                              (200, 196, 190) if metrics.excluded[i] else style.colors["amber"], -1, cv2.LINE_AA,
                              SHIFT)
                _blit(frame, tag, tx + 5 * px, cy)
            else:
                _blit(frame, cap, (self.w - cap.alpha.shape[1]) / 2, cy)
        return band + 8 * px

    def _badges(self, frame: np.ndarray, record: FrameRecord | None) -> None:
        if record is None:
            return
        px = self.px
        y = self.h - 30 * px
        x = 12 * px
        for st in record.fighters:
            if st.state not in STATE_TEXT:
                continue
            side = "red" if st.fighter_id == FighterId.fighter_a else "blue"
            text = self.text.get(f"{self.names[side]}: {STATE_TEXT[st.state]}", _thick(12 * px), WHITE)
            w, h = text.alpha.shape[1] + 14 * px, text.alpha.shape[0] + 10 * px
            layer = frame.copy()
            cv2.rectangle(layer, _pt(x, y), _pt(x + w, y + h), (20, 18, 16), -1, cv2.LINE_AA, SHIFT)
            _blend_region(frame, layer, int(x), int(y), int(x + w) + 1, int(y + h) + 1, 0.8)
            cv2.rectangle(frame, _pt(x, y), _pt(x + 4 * px, y + h), self.style.colors[side], -1, cv2.LINE_AA, SHIFT)
            _blit(frame, text, x + 9 * px, y + 5 * px)
            x += w + 8 * px

    def _footnote(self, frame: np.ndarray) -> None:
        px = self.px
        patch = self.text.get(FOOTNOTE, _thick(10 * px), (230, 230, 230), bold=False, outline=_thick(1.5 * px))
        _blit(frame, patch, self.w - patch.alpha.shape[1] - 10 * px, self.h - patch.alpha.shape[0] - 8 * px, 0.8)

    # ---- frame -----------------------------------------------------------

    def draw(self, frame: np.ndarray, i: int, record: FrameRecord | None, metrics: FrameMetrics,
             effects: Effects, distance: float | None) -> None:
        o = self.options
        people = self.people(record)
        if o.skeleton:
            if o.others:
                for p in people:
                    if p.role == "other":
                        self._person(frame, p)
            for p in people:
                if p.role != "other":
                    self._person(frame, p)
        if o.distance:
            self._distance(frame, people, distance)
        if o.effects:
            self._effects(frame, effects, people)
        top = self._band(frame, metrics, i)
        if o.effects:
            self._warnings(frame, effects, top)
        self._badges(frame, record)
        self._footnote(frame)
