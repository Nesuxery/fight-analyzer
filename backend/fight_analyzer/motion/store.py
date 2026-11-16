"""Caches of the motion stages (JSON manifest + .npy arrays, no pickle).

cache/camera/<key>/    camera track of the analysis video (independent of the selection)
cache/events/<key>/    events, movement runs and sampled signals for one identity result
cache/momentum/<key>/  momentum ledger and sampled shares for one parameter set
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from fight_analyzer.config import MomentumSettings, MotionSettings
from fight_analyzer.contracts import (
    SCHEMA_VERSION,
    DamageSignal,
    ExcludedSegment,
    FighterId,
    FighterSignals,
    FightEvent,
    MomentumContribution,
    MomentumParameters,
    MomentumTimeline,
    MotionTimeline,
    Movement,
    Posture,
)
from fight_analyzer.contracts.common import DataOrigin, utcnow
from fight_analyzer.fsutil import cache_key, staging_dir

from . import exclusions as excl
from . import momentum as momentum_mod
from .camera import CAMERA_VERSION, CameraTrack
from .events import ADVANCING, NEUTRAL, RETREATING, Analysis, MovementRun
from .kinematics import GROUNDED, STANDING, TRANSITION

# 2: possible impact (head jolt) on contact strikes; 3: attribution confidence; 4: strike outcome, target zone,
# significant strikes, elbows and ground strikes, falls from the hip height (sitting), knockdowns with an
# inferred identity, damage signals
EVENTS_VERSION = 4
# 2: excluded parts; 3: events of uncertain attribution earn nothing; 4: elbows and ground strikes earn the
# strike attempt weight
MOMENTUM_VERSION = 4
MANIFEST = "manifest.json"
CAMERA_ARRAYS = ("to_ref", "segment", "known", "inliers")
SIGNAL_ARRAYS = ("sample_ms", "valid", "activity", "hand_speed", "foot_speed", "approach", "movement", "posture",
                 "camera_known", "distance")
MOVEMENTS = {ADVANCING: Movement.advancing, RETREATING: Movement.retreating, NEUTRAL: Movement.neutral}
POSTURES = {STANDING: Posture.standing, GROUNDED: Posture.grounded, TRANSITION: Posture.transition}


@dataclass
class EventsData:
    events: list[FightEvent]
    runs: list[MovementRun]
    stats: list[dict[str, float]]
    camera_known_share: float
    signals: dict[str, np.ndarray]  # SIGNAL_ARRAYS, sampled at MotionSettings.sample_hz
    damage: list[DamageSignal] = field(default_factory=list)  # events version 4 on


@dataclass
class MomentumData:
    contributions: list[MomentumContribution]
    sample_ms: np.ndarray
    m: np.ndarray  # [2, S]
    red_share: np.ndarray  # [S]
    insufficient: np.ndarray  # [S] bool
    unattributed: list[str] = field(default_factory=list)  # event ids left out: uncertain whose they are


def _entry(cache_root: Path, kind: str, key: str) -> Path:
    return cache_root / kind / key


def _write(stage: Path, inputs: dict, arrays: dict[str, np.ndarray], extra: dict) -> None:
    for name, arr in arrays.items():
        np.save(stage / f"{name}.npy", np.ascontiguousarray(arr), allow_pickle=False)
    manifest = {"schema_version": SCHEMA_VERSION, "key_inputs": inputs, "created_at": utcnow().isoformat(),
                "arrays": sorted(arrays), **extra}
    (stage / MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def _read(d: Path, names: tuple[str, ...]) -> tuple[dict, dict[str, np.ndarray]] | None:
    try:
        manifest = json.loads((d / MANIFEST).read_text(encoding="utf-8"))
        return manifest, {name: np.load(d / f"{name}.npy", allow_pickle=False) for name in names}
    except (OSError, ValueError, KeyError):
        return None


def key_inputs(cache_root: Path, kind: str, key: str) -> dict | None:
    """Inputs (versions, settings) an entry was computed from, as stored in its manifest."""
    try:
        return json.loads((_entry(cache_root, kind, key) / MANIFEST).read_text(encoding="utf-8"))["key_inputs"]
    except (OSError, ValueError, KeyError):
        return None


# ---- camera ------------------------------------------------------------------

def camera_key(video_key: str, prep_key: str, s: MotionSettings) -> tuple[str, dict]:
    inputs = {"kind": "camera", "version": CAMERA_VERSION, "video_key": video_key, "prep_key": prep_key,
              "settings": {"width": s.camera_width, "features": s.camera_features, "min_inliers": s.camera_min_inliers}}
    return cache_key(inputs), inputs


def write_camera(cache_root: Path, key: str, inputs: dict, track: CameraTrack) -> None:
    with staging_dir(_entry(cache_root, "camera", key)) as stage:
        _write(stage, inputs, {name: getattr(track, name) for name in CAMERA_ARRAYS}, {})


def read_camera(cache_root: Path, key: str) -> CameraTrack | None:
    got = _read(_entry(cache_root, "camera", key), CAMERA_ARRAYS)
    if got is None:
        return None
    a = got[1]
    n = a["segment"].shape[0]
    if a["to_ref"].shape != (n, 2, 3) or any(a[k].shape != (n,) for k in ("known", "inliers")):
        return None
    return CameraTrack(**a)


# ---- events ------------------------------------------------------------------

def events_key(identity_key: str, camera: str, s: MotionSettings) -> tuple[str, dict]:
    inputs = {"kind": "events", "version": EVENTS_VERSION, "identity_key": identity_key, "camera_key": camera, "settings": asdict(s)}
    return cache_key(inputs), inputs


def sample(analysis: Analysis, ts_ms: np.ndarray, camera: CameraTrack, hz: float) -> dict[str, np.ndarray]:
    """Per-frame signals aggregated on a fixed time grid: numbers are averaged over the
    valid frames of each interval, states take the most common value, a sample is
    valid when most of its frames are."""
    duration = float(ts_ms[-1] + (ts_ms[-1] - ts_ms[-2] if ts_ms.size > 1 else 0)) if ts_ms.size else 0.0
    count = max(1, int(np.ceil(duration * hz / 1000 - 1e-6))) if ts_ms.size else 0
    grid = np.arange(count) * 1000 / hz
    which = np.clip(np.searchsorted(grid, ts_ms, side="right") - 1, 0, max(count - 1, 0))
    out = {"sample_ms": grid, "valid": np.zeros((2, count), bool), "camera_known": np.zeros(count, bool),
           "distance": np.full(count, np.nan)}
    for name in ("activity", "hand_speed", "foot_speed", "approach"):
        out[name] = np.full((2, count), np.nan, np.float32)
    out["movement"] = np.full((2, count), -1, np.int8)
    out["posture"] = np.full((2, count), -1, np.int8)
    for k in range(count):
        frames = np.flatnonzero(which == k)
        if frames.size == 0:  # frame rate below the grid: use the nearest frame
            frames = np.array([int(np.argmin(np.abs(ts_ms - grid[k])))])
        out["camera_known"][k] = bool(camera.known[frames].mean() >= 0.5)
        d = analysis.distance[frames]
        if np.isfinite(d).any():
            out["distance"][k] = float(np.nanmean(d))
        for i in range(2):
            ok = analysis.valid[i, frames]
            out["valid"][i, k] = ok.mean() >= 0.5
            if not ok.any():
                continue
            fr = frames[ok]
            for name, src in (("activity", analysis.activity), ("hand_speed", analysis.hand_speed),
                              ("foot_speed", analysis.foot_speed), ("approach", analysis.approach)):
                v = src[i, fr]
                if np.isfinite(v).any():
                    out[name][i, k] = float(np.nanmean(v))
            for name, src in (("movement", analysis.movement), ("posture", analysis.posture)):
                v = src[i, fr]
                v = v[v >= 0]
                if v.size:
                    out[name][i, k] = int(np.bincount(v).argmax())
    return out


def events_data(analysis: Analysis, ts_ms: np.ndarray, camera: CameraTrack, s: MotionSettings) -> EventsData:
    return EventsData(events=analysis.events, runs=analysis.runs, stats=analysis.stats,
                      camera_known_share=round(camera.known_share, 3),
                      signals=sample(analysis, ts_ms, camera, s.sample_hz), damage=analysis.damage)


def write_events(cache_root: Path, key: str, inputs: dict, data: EventsData) -> None:
    with staging_dir(_entry(cache_root, "events", key)) as stage:
        _write(stage, inputs, data.signals, {
            "events": [e.model_dump(mode="json") for e in data.events],
            "damage": [d.model_dump(mode="json") for d in data.damage],
            "runs": [asdict(r) for r in data.runs], "stats": data.stats,
            "camera_known_share": data.camera_known_share})


def read_events(cache_root: Path, key: str) -> EventsData | None:
    got = _read(_entry(cache_root, "events", key), SIGNAL_ARRAYS)
    if got is None:
        return None
    manifest, signals = got
    try:
        return EventsData(events=[FightEvent.model_validate(e) for e in manifest["events"]],
                          runs=[MovementRun(**r) for r in manifest["runs"]], stats=manifest["stats"],
                          camera_known_share=float(manifest["camera_known_share"]), signals=signals,
                          damage=[DamageSignal.model_validate(d) for d in manifest.get("damage", [])])
    except (KeyError, TypeError, ValueError):
        return None


def _num(x: float) -> float | None:
    return round(float(x), 3) if np.isfinite(x) else None


def motion_timeline(job_id: str, data: EventsData, s: MotionSettings) -> MotionTimeline:
    sig = data.signals
    fighters = []
    for i, fid in enumerate((FighterId.fighter_a, FighterId.fighter_b)):
        fighters.append(FighterSignals(
            fighter_id=fid, valid=[bool(v) for v in sig["valid"][i]],
            activity=[_num(v) for v in sig["activity"][i]], hand_speed=[_num(v) for v in sig["hand_speed"][i]],
            foot_speed=[_num(v) for v in sig["foot_speed"][i]], approach_speed=[_num(v) for v in sig["approach"][i]],
            movement=[MOVEMENTS.get(int(v)) for v in sig["movement"][i]],
            posture=[POSTURES.get(int(v)) for v in sig["posture"][i]]))
    return MotionTimeline(job_id=job_id, data_origin=DataOrigin.measured, sample_hz=s.sample_hz,
                          sample_ms=[round(float(t), 1) for t in sig["sample_ms"]],
                          camera_known=[bool(v) for v in sig["camera_known"]],
                          distance=[_num(v) for v in sig["distance"]], fighters=fighters)


# ---- momentum ----------------------------------------------------------------

def momentum_key(events: str, s: MomentumSettings, segments: list[ExcludedSegment] = (),
                 fps: float = 30.0) -> tuple[str, dict]:
    inputs = {"kind": "momentum", "version": MOMENTUM_VERSION, "events_key": events, "settings": asdict(s),
              "exclusions": [[x.start_frame, x.end_frame] for x in segments], "fps": fps}
    return cache_key(inputs), inputs


def compute_momentum(data: EventsData, s: MomentumSettings, segments: list[ExcludedSegment] = (),
                     fps: float = 30.0) -> MomentumData:
    contributions = momentum_mod.ledger(data.events, data.runs, s, segments, fps)
    t = data.signals["sample_ms"].astype(np.float64)
    m = momentum_mod.totals(contributions, t, s.half_life_s, excl.intervals(segments, fps))
    red = momentum_mod.red_share(m[0], m[1], s.prior)
    insufficient = ~(data.signals["valid"][0] & data.signals["valid"][1])
    return MomentumData(contributions=contributions, sample_ms=t, m=m, red_share=red, insufficient=insufficient,
                        unattributed=momentum_mod.unattributed(data.events, segments))


def write_momentum(cache_root: Path, key: str, inputs: dict, data: MomentumData) -> None:
    with staging_dir(_entry(cache_root, "momentum", key)) as stage:
        _write(stage, inputs, {"sample_ms": data.sample_ms, "m": data.m, "red_share": data.red_share,
                               "insufficient": data.insufficient},
               {"contributions": [c.model_dump(mode="json") for c in data.contributions],
                "unattributed": list(data.unattributed)})


def momentum_timeline(job_id: str, parameters: MomentumParameters, data: MomentumData,
                      sample_hz: float, exclusions: list[ExcludedSegment] = ()) -> MomentumTimeline:
    """Contract form served to the browser (and used by the export, so both show the same numbers)."""
    return MomentumTimeline(
        job_id=job_id, data_origin=DataOrigin.measured, parameters=parameters, sample_hz=sample_hz,
        sample_ms=[round(float(t), 1) for t in data.sample_ms],
        red_share=[round(float(v), 3) for v in data.red_share], m_red=[round(float(v), 4) for v in data.m[0]],
        m_blue=[round(float(v), 4) for v in data.m[1]], insufficient=[bool(v) for v in data.insufficient],
        contributions=data.contributions, exclusions=list(exclusions),
        unattributed_event_ids=list(data.unattributed))


def read_momentum(cache_root: Path, key: str) -> MomentumData | None:
    got = _read(_entry(cache_root, "momentum", key), ("sample_ms", "m", "red_share", "insufficient"))
    if got is None:
        return None
    manifest, a = got
    try:
        return MomentumData(contributions=[MomentumContribution.model_validate(c) for c in manifest["contributions"]],
                            sample_ms=a["sample_ms"], m=a["m"], red_share=a["red_share"], insufficient=a["insufficient"],
                            unattributed=[str(i) for i in manifest.get("unattributed", [])])
    except (KeyError, ValueError):
        return None
