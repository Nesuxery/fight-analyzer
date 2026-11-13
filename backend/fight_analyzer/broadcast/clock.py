"""Fight clock runs and round boundaries from scorebug reads.

A read is (video time t, seconds left c, round number or None). While the
clock runs, t + c stays constant: the "zero time" when it would show 0:00.
A pause (stoppage, the clock frozen while the video goes on) moves the zero
time later; the clock jumping up is a new round. A countdown display shows
whole seconds rounded up, so a read c means c - 1 < seconds left <= c.

Rules (all thresholds in BroadcastSettings):
- up to three reads that break the clock while the reads around them agree
  with each other are OCR errors and are dropped;
- a run ends where the clock jumps up (a read round number alone never
  splits a run: one misread digit must not cut a round in two);
- runs shorter than `min_round_s` of clock time are not rounds;
- start: if the first running read is within `start_snap_s` of the round
  length, the round started when the clock left the top (extrapolated);
  otherwise the recording starts inside the round (partial);
- end: a last running read within `end_snap_s` of 0:00 means the round ran
  out (zero time); a clock that freezes above 0:00 stopped early (finish,
  partial); a clock that disappears is cut off at the last read (partial).
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from fight_analyzer.config import BroadcastSettings, RulesetSettings
from fight_analyzer.contracts import BroadcastNote, BroadcastNoteCode, RoundSegment, RoundSource

HEAD = 10  # reads used for the start / end zero-time estimates


@dataclass(frozen=True)
class Read:
    t: float  # video seconds
    clock: float  # seconds left as displayed
    round: int | None
    conf: float


@dataclass
class Run:
    reads: list[Read] = field(default_factory=list)

    @property
    def elapsed(self) -> float:
        return self.reads[0].clock - self.reads[-1].clock


@dataclass
class ClockRound:
    index: int
    start_t: float
    end_t: float
    clock_start: float
    clock_end: float
    partial: bool
    confidence: float
    reads: list[Read]


def _consistent(a: Read, b: Read, tol: float) -> bool:
    """b can follow a on one running/paused clock: it did not go up, and it did not
    run faster than the video."""
    dc, dt = a.clock - b.clock, b.t - a.t
    return -tol <= dc <= dt + tol


MAX_MISREAD_BLOCK = 3  # consecutive OCR errors that can be told apart from a real reset


def drop_misreads(reads: list[Read], tol: float) -> list[Read]:
    """Drop up to MAX_MISREAD_BLOCK consecutive reads that break the clock while the
    reads around them agree with each other. A real reset (new round) is followed by
    reads that agree with it, never with the read before it, so it stays."""
    keep = list(reads)
    i = 1
    while i < len(keep) - 1:
        a = keep[i - 1]
        block = 0
        if not _consistent(a, keep[i], tol):
            block = next((n for n in range(1, MAX_MISREAD_BLOCK + 1)
                          if i + n < len(keep) and _consistent(a, keep[i + n], tol)), 0)
        if block:
            del keep[i:i + block]
            i = max(1, i - 1)
        else:
            i += 1
    return keep


def split_runs(reads: list[Read], tol: float) -> list[Run]:
    runs: list[Run] = []
    for r in reads:
        cur = runs[-1] if runs else None
        if cur is not None:
            if r.clock <= cur.reads[-1].clock + tol:  # no jump up: same round (read numbers may be wrong)
                cur.reads.append(r)
                continue
        runs.append(Run([r]))
    return runs


def _round_length(top: float, ruleset: RulesetSettings) -> float:
    for length in sorted(ruleset.standard_round_lengths_s):
        if top <= length:
            return length
    return top


def _running(reads: list[Read]) -> list[Read]:
    """Reads during which the clock ran: drop the frozen display before the start
    (e.g. 5:00 shown before the bell) and after a stop."""
    if len(reads) < 2:
        return list(reads)
    lo = 0
    while lo + 1 < len(reads) and reads[lo + 1].clock >= reads[lo].clock:
        lo += 1
    hi = len(reads) - 1
    while hi - 1 > lo and reads[hi - 1].clock <= reads[hi].clock:
        hi -= 1
    return reads[lo:hi + 1]


def _trim_ends(reads: list[Read], tol: float) -> list[Read]:
    """Drop reads at the start and end of a run whose zero time disagrees with the
    reads next to them (an OCR error at the edge has no neighbour on one side)."""
    out = list(reads)
    for _ in range(MAX_MISREAD_BLOCK):
        if len(out) > HEAD and abs(out[0].t + out[0].clock - _median_zero(out[1:HEAD + 1])) > tol + 1:
            out.pop(0)
        if len(out) > HEAD and abs(out[-1].t + out[-1].clock - _median_zero(out[-HEAD - 1:-1])) > tol + 1:
            out.pop()
    return out


def _median_zero(reads: list[Read]) -> float:
    return float(np.median([r.t + r.clock for r in reads]))


def _zero_time(reads: list[Read]) -> float:
    """Median moment the clock would show 0:00 (display rounded up: half a second earlier)."""
    return float(np.median([r.t + r.clock for r in reads])) - 0.5


def rounds_from_runs(runs: list[Run], duration_s: float, s: BroadcastSettings,
                     ruleset: RulesetSettings) -> tuple[list[ClockRound], list[BroadcastNote]]:
    notes: list[BroadcastNote] = []
    out: list[ClockRound] = []
    for run in runs:
        reads = run.reads
        running = _trim_ends(_running(reads), s.run_tolerance_s)
        if len(reads) < s.min_run_reads or len(running) < 2 or run.elapsed < s.min_round_s:
            continue
        length = _round_length(max(r.clock for r in running), ruleset)
        first, last = running[0], running[-1]
        z_start, z_end = _zero_time(running[:HEAD]), _zero_time(running[-HEAD:])
        partial = False
        if length - first.clock <= s.start_snap_s and z_start - length >= 0:
            start_t, clock_start = z_start - length, length
        else:
            # inside the round from the first evidence (from the video start if that is right there)
            start_t, clock_start, partial = (0.0 if first.t <= 2.0 else first.t - 0.5), first.clock, True
        stopped = [r for r in reads[reads.index(last) + 1:] if r.clock == last.clock]
        if last.clock <= s.end_snap_s:
            end_t, clock_end = z_end, 0.0
        elif stopped and stopped[-1].t - last.t >= 1.5:  # frozen above 0:00: stopped early
            end_t, clock_end, partial = z_end - last.clock + 0.5, last.clock, True
        else:  # disappeared while running: cut off at the last evidence
            end_t, clock_end, partial = last.t + 0.5, last.clock, True
        end_t = min(end_t, duration_s)
        if end_t - start_t < s.min_round_s:
            continue
        votes = Counter(r.round for r in reads if r.round is not None)
        index, agree = (votes.most_common(1)[0] if votes else (None, 0))
        share = agree / max(1, sum(votes.values()))
        expected = s.ocr_hz * (end_t - start_t)
        density = min(1.0, len(reads) / max(1.0, expected))
        index_factor = 1.0 if share >= 0.7 and agree >= 2 else 0.8 if share >= 0.5 and agree >= 2 else 0.6
        if index_factor == 0.6:
            index = None
        out.append(ClockRound(index=index or 0, start_t=start_t, end_t=end_t, clock_start=clock_start,
                              clock_end=clock_end, partial=partial,
                              confidence=round(min(1.0, (0.25 + 0.75 * density) * index_factor), 2), reads=reads))
    # Round numbers: as read; unreadable ones follow their predecessor.
    for i, r in enumerate(out):
        if r.index == 0:
            r.index = (out[i - 1].index + 1) if i > 0 else 1
            notes.append(BroadcastNote(code=BroadcastNoteCode.round_number_inferred, round=r.index))
    best: dict[int, ClockRound] = {}
    for r in out:  # the same number twice (e.g. a restarted clock): keep the better supported one
        if r.index not in best or len(r.reads) > len(best[r.index].reads):
            best[r.index] = r
    kept = sorted((r for r in best.values() if 1 <= r.index <= 5), key=lambda r: r.start_t)
    return kept, notes


def to_segment(r: ClockRound, fps: float, frame_count: int) -> RoundSegment:
    start = min(frame_count - 1, max(0, round(r.start_t * fps)))
    end = min(frame_count - 1, max(start, math.ceil(r.end_t * fps) - 1))
    return RoundSegment(index=r.index, start_frame=start, end_frame=end, video_start_s=round(start / fps, 3),
                        video_end_s=round((end + 1) / fps, 3), clock_start=r.clock_start, clock_end=r.clock_end,
                        source=RoundSource.ocr, confidence=r.confidence, partial=r.partial)


def timeline(rounds: list[ClockRound], duration_s: float, hz: float,
             max_gap_s: float) -> tuple[list[float], list[int | None], list[float | None], list[float]]:
    """Fight clock sampled at `hz`: a read at the sample, or a straight line between
    two reads of the same round at most `max_gap_s` apart (lower confidence)."""
    n = int(math.floor(duration_s * hz)) + 1
    ts = [round(i / hz, 3) for i in range(n)]
    rnd: list[int | None] = [None] * n
    rem: list[float | None] = [None] * n
    conf = [0.0] * n
    for r in rounds:
        times = np.array([x.t for x in r.reads])
        for i, t in enumerate(ts):
            if not r.start_t <= t < r.end_t:
                continue
            k = int(np.searchsorted(times, t))
            near = [j for j in (k - 1, k) if 0 <= j < len(times) and abs(times[j] - t) <= 0.5 / hz]
            if near:
                rnd[i], rem[i], conf[i] = r.index, r.reads[near[0]].clock, r.confidence
            elif 0 < k < len(times) and times[k] - times[k - 1] <= max_gap_s:
                a, b = r.reads[k - 1], r.reads[k]
                rnd[i] = r.index
                rem[i] = float(max(b.clock, min(a.clock, a.clock - (t - a.t))))
                conf[i] = round(0.5 * r.confidence, 2)
    return ts, rnd, rem, conf


def infer(reads: list[Read], duration_s: float, s: BroadcastSettings,
          ruleset: RulesetSettings) -> tuple[list[ClockRound], list[BroadcastNote]]:
    usable = [r for r in sorted(reads, key=lambda r: r.t) if r.conf >= s.min_read_conf]
    runs = split_runs(drop_misreads(usable, s.run_tolerance_s), s.run_tolerance_s)
    return rounds_from_runs(runs, duration_s, s, ruleset)
