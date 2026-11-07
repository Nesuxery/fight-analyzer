"""Golden file shared/fixtures/frame-metrics.json: synthetic analysis results and
what the result screen must show at each listed frame (statistics, momentum
and the visible event effects).

The backend test checks that export/frames.py reproduces the file; the
frontend test (frontend/tests/frame-metrics.test.ts) checks that the browser
functions in measured.ts produce the same numbers. Together they guarantee
that the exported MP4/CSV and the browser agree.

Regenerate after an intended change of the formulas:
    python -m tests.support.frame_fixture
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from fight_analyzer.contracts import (
    DataOrigin,
    ExcludedSegment,
    FightEvent,
    FighterSignals,
    MomentumContribution,
    MomentumParameters,
    MomentumTimeline,
    MotionTimeline,
)
from fight_analyzer.export import frames
from fight_analyzer.export.style import load_style
from fight_analyzer.motion import exclusions as excl

FIXTURE = Path(__file__).resolve().parents[3] / "shared" / "fixtures" / "frame-metrics.json"
JOB_ID = "f" * 32
FPS = 30000 / 1001
FRAME_COUNT = 900
HZ = 10.0
# a replay over a ground-control stretch and a short slow-motion part
EXCLUSIONS = [ExcludedSegment(start_frame=300, end_frame=389, reason="replay"),
              ExcludedSegment(start_frame=700, end_frame=730, reason="slow_motion")]
STATS = ("strikeAttempts", "kicks", "activity", "pressure", "advance", "retreat", "controlS", "significant")
COLUMNS = {"strikeAttempts": "strike_attempts", "kicks": "kick_attempts", "activity": "activity",
           "pressure": "pressure", "advance": "advance", "retreat": "retreat", "controlS": "control_s",
           "significant": "significant"}


def build_inputs() -> tuple[list[FightEvent], MotionTimeline, MomentumTimeline]:
    rng = random.Random(7)
    n = math.ceil(FRAME_COUNT / FPS * HZ - 1e-6)
    fighters = []
    for fid in ("fighter_a", "fighter_b"):
        valid = [rng.random() > 0.15 for _ in range(n)]
        fighters.append(FighterSignals(
            fighter_id=fid, valid=valid,
            activity=[round(rng.random(), 3) if v else None for v in valid],
            hand_speed=[round(rng.uniform(0, 8), 3) if v else None for v in valid],
            foot_speed=[round(rng.uniform(0, 8), 3) if v else None for v in valid],
            approach_speed=[round(rng.uniform(-2, 2), 3) if v else None for v in valid],
            movement=[rng.choice(["advancing", "retreating", "neutral", "neutral"]) if v else None for v in valid],
            posture=[rng.choice(["standing", "standing", "grounded"]) if v else None for v in valid]))
    motion = MotionTimeline(job_id=JOB_ID, data_origin=DataOrigin.measured, sample_hz=HZ,
                            sample_ms=[round(i * 1000 / HZ, 1) for i in range(n)],
                            camera_known=[rng.random() > 0.1 for _ in range(n)],
                            distance=[round(rng.uniform(0.8, 4), 3) for _ in range(n)], fighters=fighters)
    events: list[FightEvent] = []
    contribs: list[MomentumContribution] = []
    kinds = ["punch"] * 6 + ["kick"] * 2 + ["knee", "knockdown", "takedown", "ground_control", "stance_change"]
    for k in range(40):
        kind = rng.choice(kinds)
        actor = rng.choice(["fighter_a", "fighter_b"])
        start = rng.randrange(0, FRAME_COUNT - 60)
        length = rng.randrange(60, 200) if kind == "ground_control" else rng.randrange(1, 12)
        end = min(FRAME_COUNT - 1, start + length)
        peak = None if kind == "ground_control" else rng.randrange(start, end + 1)
        ms = lambda f: round(f * 1000 / FPS, 3)  # noqa: E731
        e = FightEvent(event_id=f"e{k}", type=kind, actor=actor, target="fighter_b" if actor == "fighter_a" else "fighter_a",
                       start_frame=start, end_frame=end, start_ms=ms(start), end_ms=ms(end),
                       peak_frame=peak, peak_ms=ms(peak) if peak is not None else None,
                       possible_contact=kind in ("punch", "kick", "knee") and rng.random() < 0.4,
                       confidence=round(rng.uniform(0.4, 0.95), 3), data_origin=DataOrigin.measured)
        events.append(e)
        if kind == "stance_change":
            continue
        at = e.peak_ms if e.peak_ms is not None else e.start_ms
        if kind == "ground_control":
            contribs.append(MomentumContribution(contribution_id=f"c{k}", fighter_id=actor, source="control",
                                                 event_id=e.event_id, start_ms=e.start_ms, end_ms=e.end_ms,
                                                 quantity=round((e.end_ms - e.start_ms) / 1000, 3),
                                                 points=round(0.5 * (e.end_ms - e.start_ms) / 1000, 4)))
            continue
        source = {"kick": "kick_attempt", "knockdown": "knockdown", "takedown": "takedown"}.get(kind, "strike_attempt")
        points = {"kick_attempt": 1.3, "knockdown": 4.0, "takedown": 2.5}.get(source, 1.0)
        contribs.append(MomentumContribution(contribution_id=f"c{k}", fighter_id=actor, source=source,
                                             event_id=e.event_id, start_ms=at, end_ms=at, quantity=1, points=points))
        if e.possible_contact:
            contribs.append(MomentumContribution(contribution_id=f"c{k}b", fighter_id=actor, source="contact_bonus",
                                                 event_id=e.event_id, start_ms=at, end_ms=at, quantity=1, points=0.3))
    for k in range(6):  # advance runs
        a = round(rng.uniform(0, 25000), 1)
        b = round(a + rng.uniform(400, 3000), 1)
        contribs.append(MomentumContribution(contribution_id=f"adv{k}", fighter_id=rng.choice(["fighter_a", "fighter_b"]),
                                             source="advance", start_ms=a, end_ms=b, quantity=round((b - a) / 1000, 3),
                                             points=round(0.2 * (b - a) / 1000, 4)))
    params = MomentumParameters(half_life_s=20, prior=4, strike_attempt=1, kick_attempt=1.3, contact_bonus=0.3,
                                advance_per_s=0.2, control_per_s=0.5, knockdown=4, takedown=2.5,
                                min_major_confidence=0.5)
    momentum = MomentumTimeline(job_id=JOB_ID, data_origin=DataOrigin.measured, parameters=params, sample_hz=HZ,
                                sample_ms=motion.sample_ms, red_share=[50.0] * n, m_red=[0.0] * n, m_blue=[0.0] * n,
                                insufficient=[not (a and b) for a, b in zip(fighters[0].valid, fighters[1].valid)],
                                contributions=contribs, exclusions=EXCLUSIONS)
    return events, motion, momentum


def checked_frames(events: list[FightEvent]) -> list[int]:
    picks = set(range(0, FRAME_COUNT, 7)) | {FRAME_COUNT - 1}
    for x in EXCLUSIONS:
        picks |= {x.start_frame - 1, x.start_frame, x.end_frame, x.end_frame + 1}
    for e in events:
        for f in (e.start_frame, e.end_frame, e.peak_frame):
            if f is not None:
                picks |= {max(0, f - 1), f, min(FRAME_COUNT - 1, f + 1)}
    return sorted(picks)


def expected(events, motion, momentum) -> list[dict]:
    m = frames.compute(FRAME_COUNT, FPS, events, motion, momentum)
    style = load_style()
    excluded = excl.excluded_event_ids(events, momentum.exclusions)
    out = []

    def val(v):
        f = float(v)
        return None if math.isnan(f) else (int(f) if f == int(f) else f)

    for f in checked_frames(events):
        row = {"frame": f, "red_share": float(m.red_share[f]), "red_shown": int(m.red_shown[f]),
               "insufficient": bool(m.insufficient[f]), "excluded": bool(m.excluded[f])}
        for side in frames.SIDES:
            st = m.stats[side]
            row[side] = {key: val(st[col][f]) for key, col in COLUMNS.items()}
            row[side]["measuredS"] = float(st["measured_s"][f])
        fx = frames.effects_at(events, frames.frame_ms(f, FPS) / 1000, style, excluded)
        row["effects"] = {"flashes": [[x.event.event_id, x.strength] for x in fx.flashes],
                          "rings": [[x.event.event_id, x.strength, x.labelled] for x in fx.rings],
                          "warnings": [[x.event.event_id, x.strength] for x in fx.warnings]}
        out.append(row)
    return out


def build() -> dict:
    events, motion, momentum = build_inputs()
    return {
        "description": "Synthetic analysis results and the values the result screen shows at each listed frame. "
                       "Checked by backend/tests/test_export.py and frontend/tests/frame-metrics.test.ts; "
                       "regenerate with python -m tests.support.frame_fixture (in backend/).",
        "fps": FPS,
        "frame_count": FRAME_COUNT,
        "events": [e.model_dump(mode="json") for e in events],
        "motion": motion.model_dump(mode="json"),
        "momentum": momentum.model_dump(mode="json"),
        "frames": expected(events, motion, momentum),
    }


if __name__ == "__main__":
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(build(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {FIXTURE}")
