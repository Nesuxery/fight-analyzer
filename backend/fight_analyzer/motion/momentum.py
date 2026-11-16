"""Experimental momentum: a ledger of points with exponential decay.

Every point has a source in the ledger (a strike attempt - punch, knee, elbow
or ground strike, or a kick -, its possible contact, time spent advancing,
estimated ground control, a possible knockdown or takedown with enough
evidence), so the score at any moment can be split
into its parts and the effect of a single event can be shown exactly.

    m(t) = sum of points earned before t, each halved every `half_life_s`
    red share = 100 x (m_red + prior) / (m_red + m_blue + 2 x prior)
    blue share = 100 - red share

Time-based sources earn `rate` points per second over their stretch; their
decayed value is integrated exactly. The weights are starting design
parameters, not validated sport-science weights, and the index is not a win
probability.

Excluded parts (replays etc., see exclusions.py) earn nothing and are not fight
time: time runs on fight time, so the momentum holds its value through them.

Events of which it is uncertain whose they are ("Kime ait belirsiz",
`attribution_uncertain`) earn nothing either: points for the wrong fighter
would move the share twice. The formula and the weights are unchanged; the
events left out are reported (`unattributed`).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

import numpy as np

from fight_analyzer.config import MomentumSettings
from fight_analyzer.contracts import (
    EventType,
    ExcludedSegment,
    FighterId,
    FightEvent,
    MomentumContribution,
    MomentumParameters,
    MomentumSource,
)

from . import exclusions as excl
from .events import FIGHTERS, HAND_STRIKES, STRIKE_TYPES, MovementRun


def parameters(s: MomentumSettings) -> MomentumParameters:
    return MomentumParameters(**{name: getattr(s, name) for name in MomentumParameters.model_fields})


def ledger(events: Iterable[FightEvent], runs: Iterable[MovementRun], s: MomentumSettings,
           segments: Sequence[ExcludedSegment] = (), fps: float = 30.0) -> list[MomentumContribution]:
    """Points of every source. Events in excluded parts earn nothing; time-based
    sources earn only for their stretches outside excluded parts."""
    out: list[MomentumContribution] = []
    iv = excl.intervals(segments, fps)

    def add(fighter: FighterId, source: MomentumSource, event_id: str | None, start: float, end: float,
            quantity: float, weight: float) -> None:
        if weight <= 0 or quantity <= 0:
            return
        out.append(MomentumContribution(
            contribution_id=f"{source.value}-{len(out)}", fighter_id=fighter, source=source, event_id=event_id,
            start_ms=round(start, 1), end_ms=round(end, 1), quantity=round(quantity, 3),
            points=round(weight * quantity, 4)))

    def add_span(fighter: FighterId, source: MomentumSource, event_id: str | None, start: float, end: float,
                 seconds: float, per_s: float) -> None:
        parts = excl.outside_parts(start, end, iv)
        whole = end - start
        for a, b in parts:  # points shared out by duration
            add(fighter, source, event_id, a, b, seconds * (b - a) / whole if whole > 0 else 0, per_s)

    for e in events:
        if e.actor is None or e.attribution_uncertain or excl.frame_excluded(excl.event_frame(e), segments):
            continue
        at = e.peak_ms if e.peak_ms is not None else e.start_ms
        if e.type in HAND_STRIKES:  # elbows and ground strikes weigh as much as a punch
            add(e.actor, MomentumSource.strike_attempt, e.event_id, at, at, 1, s.strike_attempt)
        elif e.type == EventType.kick:  # never also a punch
            add(e.actor, MomentumSource.kick_attempt, e.event_id, at, at, 1, s.kick_attempt)
        if e.type in STRIKE_TYPES and e.possible_contact:
            add(e.actor, MomentumSource.contact_bonus, e.event_id, at, at, 1, s.contact_bonus)
        if e.type == EventType.ground_control:
            add_span(e.actor, MomentumSource.control, e.event_id, e.start_ms, e.end_ms,
                     e.measures.get("seconds", (e.end_ms - e.start_ms) / 1000), s.control_per_s)
        if e.type in (EventType.knockdown, EventType.takedown) and e.confidence >= s.min_major_confidence:
            source = MomentumSource.knockdown if e.type == EventType.knockdown else MomentumSource.takedown
            add(e.actor, source, e.event_id, at, at, 1, s.knockdown if e.type == EventType.knockdown else s.takedown)
    for r in runs:
        if r.advancing:
            add_span(FIGHTERS[r.fighter], MomentumSource.advance, None, r.start_ms, r.end_ms, r.seconds,
                     s.advance_per_s)
    out.sort(key=lambda c: (c.start_ms, c.contribution_id))
    return out


def unattributed(events: Iterable[FightEvent], segments: Sequence[ExcludedSegment] = ()) -> list[str]:
    """Ids of the events the ledger leaves out because it is uncertain whose they are
    (events in excluded parts are out for that reason and not listed here)."""
    return [e.event_id for e in events
            if e.actor is not None and e.attribution_uncertain
            and not excl.frame_excluded(excl.event_frame(e), segments)]


def decayed(c: MomentumContribution, t_ms: np.ndarray | float, half_life_s: float,
            iv: excl.Intervals = ()) -> np.ndarray:
    """Value of one contribution at time(s) t (0 before it starts), on fight time."""
    t = excl.fight_ms_array(np.asarray(t_ms, np.float64), list(iv)) / 1000.0
    start, end = excl.fight_ms(c.start_ms, list(iv)) / 1000.0, excl.fight_ms(c.end_ms, list(iv)) / 1000.0
    lam = math.log(2) / half_life_s
    if end <= start:  # one-off points
        return np.where(t >= start, c.points * np.exp(-lam * (t - start)), 0.0)
    rate = c.points / (end - start)
    upto = np.clip(t, start, end)
    # integral of rate * exp(-lam (t - u)) du over [start, upto]
    value = rate / lam * (np.exp(-lam * (t - upto)) - np.exp(-lam * (t - start)))
    return np.where(t >= start, value, 0.0)


def totals(contribs: Iterable[MomentumContribution], t_ms: np.ndarray, half_life_s: float,
           iv: excl.Intervals = ()) -> np.ndarray:
    """[2, len(t)] decayed sums for red and blue."""
    t = np.asarray(t_ms, np.float64)
    m = np.zeros((2, t.size))
    for c in contribs:
        m[0 if c.fighter_id == FighterId.fighter_a else 1] += decayed(c, t, half_life_s, iv)
    return m


def red_share(m_red: np.ndarray | float, m_blue: np.ndarray | float, prior: float) -> np.ndarray:
    return 100.0 * (np.asarray(m_red) + prior) / (np.asarray(m_red) + np.asarray(m_blue) + 2 * prior)
