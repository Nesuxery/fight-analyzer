"""Bout format and effective rounds: the user's marks over the automatic ones.

- A user mark (MatchSetup.rounds) replaces the automatic round of the same number.
- An automatic round the user removed (MatchSetup.cleared_rounds) is not used.
- An automatic round that overlaps a user mark, or is out of time order with
  one, is not used (noted); so are numbers above the scheduled rounds.
- The result is in time order by round number; anything else is dropped (noted).
Nothing here changes a stored user input.
"""

from __future__ import annotations

from typing import Any

from fight_analyzer.config import RulesetSettings
from fight_analyzer.contracts import (
    BoutConfig,
    FighterNames,
    MatchSetup,
    RoundMark,
    RoundNote,
    RoundNoteCode,
    RoundSegment,
    RoundSource,
    Ruleset,
)

PARTIAL_SLACK_S = 5.0  # a manual round this much shorter than the round length is partial


def bout_config(params: dict[str, Any], ruleset: RulesetSettings, names: dict[str, str]) -> BoutConfig:
    """The stored bout format, else one derived from an older MatchSetup or the ruleset."""
    stored = params.get("bout")
    if stored:
        base = BoutConfig.model_validate({**stored, "names": None})
    else:
        match = params.get("match") or {}
        base = BoutConfig(scheduled_rounds=match.get("scheduled_rounds", ruleset.default_rounds),
                          round_length_s=match.get("round_length_s", ruleset.round_length_s),
                          rest_s=ruleset.rest_s, ruleset=Ruleset(ruleset.name))
    return base.model_copy(update={"names": FighterNames(red=names["red"], blue=names["blue"])})


def manual_segment(mark: RoundMark, fps: float, round_length_s: float) -> RoundSegment:
    length = (mark.end_frame - mark.start_frame + 1) / fps
    return RoundSegment(index=mark.number, start_frame=mark.start_frame, end_frame=mark.end_frame,
                        video_start_s=round(mark.start_frame / fps, 3), video_end_s=round((mark.end_frame + 1) / fps, 3),
                        source=RoundSource.manual, confidence=1.0, partial=length < round_length_s - PARTIAL_SLACK_S)


def _overlap(a: RoundSegment, b: RoundSegment) -> bool:
    return a.start_frame <= b.end_frame and b.start_frame <= a.end_frame


def _out_of_order(a: RoundSegment, b: RoundSegment) -> bool:
    """a and b cannot both be rounds: they overlap, or the lower number comes later."""
    if _overlap(a, b):
        return True
    first, second = (a, b) if a.index < b.index else (b, a)
    return first.start_frame > second.start_frame


def effective(auto: list[RoundSegment], setup: MatchSetup | None, scheduled: int, fps: float,
              round_length_s: float) -> tuple[list[RoundSegment], list[RoundNote]]:
    manual = {m.number: manual_segment(m, fps, round_length_s) for m in (setup.rounds if setup else [])}
    cleared = set(setup.cleared_rounds) if setup else set()
    notes: list[RoundNote] = []
    chosen = dict(manual)
    for a in sorted(auto, key=lambda r: r.index):
        if a.index in manual or a.index in cleared:
            continue
        if a.index > scheduled:
            notes.append(RoundNote(code=RoundNoteCode.beyond_scheduled, round=a.index))
            continue
        clash = next((m for m in manual.values() if _out_of_order(a, m)), None)
        if clash is not None:
            notes.append(RoundNote(code=RoundNoteCode.auto_conflicts_manual, round=a.index, other=clash.index))
            continue
        chosen[a.index] = a
    out: list[RoundSegment] = []
    for r in sorted(chosen.values(), key=lambda r: r.index):
        if out and _out_of_order(out[-1], r):  # automatic rounds that disagree with each other
            notes.append(RoundNote(code=RoundNoteCode.out_of_order, round=r.index, other=out[-1].index))
            continue
        out.append(r)
    return out, notes


def judging_setup(setup: MatchSetup | None, bout: BoutConfig, rounds: list[RoundSegment]) -> MatchSetup:
    """The MatchSetup the AI judges work with: bout format and effective rounds."""
    base = setup or MatchSetup()
    marks = [RoundMark(number=r.index, start_frame=r.start_frame, end_frame=r.end_frame)
             for r in rounds if r.index <= bout.scheduled_rounds]
    return MatchSetup.model_validate({**base.model_dump(mode="json"), "scheduled_rounds": bout.scheduled_rounds,
                                      "round_length_s": bout.round_length_s,
                                      "rounds": [m.model_dump(mode="json") for m in marks], "cleared_rounds": []})
