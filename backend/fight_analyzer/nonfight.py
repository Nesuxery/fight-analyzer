"""Automatic excluded parts: everything that is not live fight time.

Two sources, combined here and nowhere else:

1. The rounds in effect (Job.rounds: the user's marks over the automatic
   ones). Time outside them is not fight time when that is certain:
   - before round 1: intro;
   - between rounds n and n + 1: break;
   - after the last round found: post-fight, if it is the last scheduled
     round or the user entered an early ending in it.
   A gap with a missing round number in between (R1 and R3 found) or the time
   after a round that is not known to be the last one is claimed by nobody:
   a round may be hiding there.
2. Parts the broadcast analysis found from its signals (broadcast/replay.py):
   replays, stoppages, and the scorebug-less stretches before the first and
   after the last clock round. Rounds come first: a detected part gives way
   to what the rounds already claim, and a detected intro / break / post-fight
   part never reaches into a round in effect (the user's round always wins).
   The exception is a break that lies entirely inside one round: that is the
   scorebug away while the clock stands still, and it keeps its place there
   like a replay or a stoppage.

The user can turn any automatic part off ("Geri al"). What is turned off is
stored as frame ranges, not ids: an automatic part is off while a stored range
covers it (intersection over union >= DISMISS_IOU), so it stays off when a
round edit moves it by a few seconds and comes back when it changed for real.

Excluded parts in effect = the user's parts + the automatic parts not turned
off (`effective`); statistics, cards, the momentum and exports use that list.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from fight_analyzer.contracts import (
    FINISHES,
    AutoExclusion,
    ExcludedSegment,
    ExclusionReason,
    ExclusionSignal,
    ExclusionSource,
    FinishMethod,
    MatchEnding,
    RoundSegment,
)
from fight_analyzer.motion import exclusions as excl

DISMISS_IOU = 0.5
# Detected parts that only say "not a round" (not what happens inside one).
OUTSIDE_ROUND_REASONS = frozenset({ExclusionReason.intro, ExclusionReason.break_, ExclusionReason.post_fight})


def auto_segment(start: int, end: int, reason: ExclusionReason, signals: Sequence[ExclusionSignal],
                 confidence: float) -> ExcludedSegment:
    return ExcludedSegment(start_frame=start, end_frame=end, reason=reason, source=ExclusionSource.auto,
                           auto_id=f"{reason.value}-{start}-{end}", confidence=round(min(1.0, max(0.0, confidence)), 2),
                           signals=list(signals))


def from_rounds(rounds: Sequence[RoundSegment], scheduled: int, ending: MatchEnding | None,
                frame_count: int) -> list[ExcludedSegment]:
    """Time outside the rounds that is certainly not fight time (see the module text)."""
    ordered = sorted(rounds, key=lambda r: r.start_frame)
    out: list[ExcludedSegment] = []
    if not ordered:
        return out

    def claim(start: int, end: int, reason: ExclusionReason, confidence: float) -> None:
        end = min(end, frame_count - 1)
        if end >= start:
            out.append(auto_segment(start, end, reason, [ExclusionSignal.outside_rounds], confidence))

    first, last = ordered[0], ordered[-1]
    if first.index == 1:
        claim(0, first.start_frame - 1, ExclusionReason.intro, first.confidence)
    for a, b in zip(ordered, ordered[1:]):
        if b.index == a.index + 1:
            claim(a.end_frame + 1, b.start_frame - 1, ExclusionReason.break_, min(a.confidence, b.confidence))
    ended_early = ending is not None and (ending.method in FINISHES or ending.method == FinishMethod.no_contest) \
        and (ending.round == last.index or (ending.round is None and last.partial))
    if last.index >= scheduled or ended_early:
        claim(last.end_frame + 1, frame_count - 1, ExclusionReason.post_fight, last.confidence)
    return out


def _subtract(start: int, end: int, taken: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    """[start, end] (inclusive frames) without the `taken` ranges."""
    parts = [(start, end)]
    for a, b in taken:
        parts = [piece for x, y in parts
                 for piece in ((x, min(y, a - 1)), (max(x, b + 1), y)) if piece[1] >= piece[0]]
    return parts


def combine(claims: Sequence[ExcludedSegment], detected: Sequence[ExcludedSegment],
            rounds: Sequence[RoundSegment], fps: float, frame_count: int,
            min_s: float = 1.0) -> list[ExcludedSegment]:
    """All automatic parts: the claims from the rounds, and the detected parts where they
    add something (pieces shorter than `min_s` are dropped)."""
    claimed = [(c.start_frame, c.end_frame) for c in claims]
    in_rounds = [(r.start_frame, r.end_frame) for r in rounds]
    out = list(claims)
    for d in detected:
        if d.start_frame >= frame_count:
            continue
        end = min(d.end_frame, frame_count - 1)
        inside_one = d.reason == ExclusionReason.break_ and any(a <= d.start_frame and end <= b for a, b in in_rounds)
        taken = claimed + (in_rounds if d.reason in OUTSIDE_ROUND_REASONS and not inside_one else [])
        for a, b in _subtract(d.start_frame, end, taken):
            if (b - a + 1) / fps >= min_s:
                out.append(auto_segment(a, b, d.reason, d.signals, d.confidence or 0.0))
    return sorted(out, key=lambda x: (x.start_frame, x.end_frame))


def _iou(a_start: int, a_end: int, b_start: int, b_end: int) -> float:
    inter = min(a_end, b_end) - max(a_start, b_start) + 1
    if inter <= 0:
        return 0.0
    return inter / ((a_end - a_start + 1) + (b_end - b_start + 1) - inter)


def is_dismissed(segment: ExcludedSegment, dismissed: Iterable[dict[str, Any]]) -> bool:
    return any(_iou(segment.start_frame, segment.end_frame, int(d["start_frame"]), int(d["end_frame"])) >= DISMISS_IOU
               for d in dismissed)


def with_dismissed(auto: Sequence[ExcludedSegment], dismissed: Sequence[dict[str, Any]]) -> list[AutoExclusion]:
    return [AutoExclusion(**a.model_dump(), dismissed=is_dismissed(a, dismissed)) for a in auto]


def dismissed_ranges(auto: Sequence[AutoExclusion], ids: Iterable[str],
                     stored: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ranges to store when the user turns off exactly the parts `ids`: those parts, plus
    stored ranges that match no current part (they belong to a part that is not there now,
    e.g. while a round is removed, and must survive until it is back)."""
    wanted = set(ids)
    idle = [d for d in stored if not any(is_dismissed(a, [d]) for a in auto)]
    return idle + [{"start_frame": a.start_frame, "end_frame": a.end_frame, "reason": a.reason.value}
                   for a in auto if a.auto_id in wanted]


def effective(manual: Iterable[ExcludedSegment], auto: Iterable[AutoExclusion],
              frame_count: int) -> list[ExcludedSegment]:
    """Excluded parts in effect: the user's and the automatic ones not turned off, clipped,
    sorted and merged where they overlap or touch (the earlier part's reason wins)."""
    active = [ExcludedSegment(**a.model_dump(exclude={"dismissed"})) for a in auto if not a.dismissed]
    return excl.normalize([*manual, *active], frame_count)
