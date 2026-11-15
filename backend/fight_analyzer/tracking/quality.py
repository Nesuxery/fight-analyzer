"""Data quality of the identities: per frame what lowers the confidence, and a summary
for any frame range (the whole bout, a round, up to the playhead).

Per frame and fighter a small bit mask is stored with the identity result:

- not measurable: the identity is not verified with a detection, or fewer than
  `min_body_joints` body joints are measured;
- causes (a frame can have several):
  - no_footage: the fighter is not found in the picture (lost, tracker gap);
  - camera: a far camera (his box is small in the frame), or a view in which he
    could not be told apart (after a camera cut, look-alike candidates);
  - overlap: the fighters overlap and the frame could not be verified by its own
    appearance (the identity is carried by tracker continuity), or the identity
    was lost in an overlap;
  - image: low image quality: few pixels, blur (little gradient energy on shorts
    and torso), low keypoint confidence.

`summarize` is the one definition of the numbers shown per scope. The browser
computes the same from the run-length form (frontend/src/model/quality.ts) for the
scope that follows the playhead; shared/fixtures/track-quality.json is checked on
both sides. Excluded parts are not fight time: their frames are left out and break
an uncertain stretch.

The thresholds are starting values (IdentitySettings); the sample broadcast is
sharp and close, so the blur and resolution limits were not exercised by it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from fight_analyzer.config import IdentitySettings
from fight_analyzer.contracts import (
    CauseShare,
    ExcludedSegment,
    QualityCause,
    QualityRun,
    TrackQuality,
    UncertainReason,
)
from fight_analyzer.pose.cache import PoseArrays

from .appearance import SLICES
from .identity import FIGHTERS, OCCLUDED, REASONS, UNCERTAIN
from .prep import PrepData

CAUSES = list(QualityCause)
BIT = {cause: 1 << k for k, cause in enumerate(CAUSES)}
UNMEASURABLE = 1 << 7
BODY = slice(5, 17)
# Why the identity is unknown -> what that says about the footage.
UNCERTAIN_CAUSE = {
    UncertainReason.lost: QualityCause.no_footage,
    UncertainReason.camera_cut: QualityCause.camera,
    UncertainReason.ambiguous: QualityCause.camera,
    UncertainReason.anchor_conflict: QualityCause.camera,
    UncertainReason.overlap: QualityCause.overlap,
}


def frame_quality(arrays: PoseArrays, prep: PrepData, state: np.ndarray, det: np.ndarray, reason: np.ndarray,
                  frame_height: int, i: IdentitySettings) -> np.ndarray:
    """[F, 2] uint8 bit mask (see the module text)."""
    out = np.zeros(state.shape, np.uint8)
    energy_cols = [SLICES["shorts_energy"].start, SLICES["torso_energy"].start]
    for f in (0, 1):
        present = (state[:, f] != UNCERTAIN) & (det[:, f] >= 0)
        mask = np.zeros(state.shape[0], np.uint8)
        if present.any():
            d = det[present, f]
            conf = np.asarray(arrays.keypoints[d][:, BODY, 2])
            height = arrays.boxes[d, 3] - arrays.boxes[d, 1]
            energy = np.asarray(prep.feat[d][:, energy_cols]).mean(axis=1)
            part = np.zeros(d.size, np.uint8)
            part[(conf >= i.joint_min_conf).sum(axis=1) < i.min_body_joints] |= UNMEASURABLE
            part[height < i.far_height_share * frame_height] |= BIT[QualityCause.camera]
            poor = ((conf.mean(axis=1) < i.low_keypoint_conf) | (height < i.low_resolution_px * frame_height / 1080)
                    | ((prep.feat_q[d] > 0) & (energy < i.blur_energy)))
            part[poor] |= BIT[QualityCause.image]
            part[state[present, f] == OCCLUDED] |= BIT[QualityCause.overlap]
            mask[present] = part
        gap = (state[:, f] == OCCLUDED) & (det[:, f] < 0)  # the tracker skipped the frame
        mask[gap] = UNMEASURABLE | BIT[QualityCause.no_footage]
        unknown = state[:, f] == UNCERTAIN
        mask[unknown] = UNMEASURABLE | BIT[QualityCause.no_footage]
        for why, cause in UNCERTAIN_CAUSE.items():
            mask[unknown & (reason[:, f] == REASONS.index(why))] = UNMEASURABLE | BIT[cause]
        out[:, f] = mask
    return out


def quality_runs(mask: np.ndarray) -> list[QualityRun]:
    """Run-length form of one fighter's mask; frames without a bit are left out."""
    out: list[QualityRun] = []
    if mask.size == 0:
        return out
    edges = np.flatnonzero(np.diff(mask)) + 1
    for a, b in zip([0, *edges.tolist()], [*(edges - 1).tolist(), mask.size - 1]):
        value = int(mask[a])
        if value:
            out.append(QualityRun(start_frame=a, end_frame=b, measurable=not value & UNMEASURABLE,
                                  causes=[c for c in CAUSES if value & BIT[c]]))
    return out


def excluded_mask(segments: Sequence[ExcludedSegment], frame_count: int) -> np.ndarray:
    out = np.zeros(frame_count, bool)
    for x in segments:
        out[x.start_frame:x.end_frame + 1] = True
    return out


def _share(count: int, total: int) -> float:
    """count / total to four decimals, halves rounded up: the browser's Math.round, not
    Python's round-half-to-even, so both show the same number on an exact tie."""
    return math.floor(count / total * 1e4 + 0.5) / 1e4 if total else 0.0


def summarize(state: np.ndarray, quality: np.ndarray, change: np.ndarray, start: int, end: int, fps: float,
              excluded: np.ndarray | None = None) -> list[TrackQuality]:
    """Quality of both fighters over the frames [start, end] (inclusive) that are fight time."""
    n = state.shape[0]
    inside = np.zeros(n, bool)
    first, last = max(0, start), min(n - 1, end)
    if last >= first:
        inside[first:last + 1] = True
    if excluded is not None:
        inside &= ~excluded
    count = int(inside.sum())
    out = []
    for f in (0, 1):
        st, mask = state[inside, f], quality[inside, f]
        unknown = inside & (state[:, f] == UNCERTAIN)
        edges = np.diff(np.concatenate(([0], unknown.astype(np.int8), [0])))
        lengths = np.flatnonzero(edges == -1) - np.flatnonzero(edges == 1)
        # ordered by the rounded share, equal shares in the order of the causes (as the browser does)
        shares = [(c, _share(int((mask & BIT[c] != 0).sum()), count)) for c in CAUSES]
        out.append(TrackQuality(
            fighter_id=FIGHTERS[f], frames=count,
            measurable_share=_share(int((mask & UNMEASURABLE == 0).sum()), count),
            occluded_share=_share(int((st == OCCLUDED).sum()), count),
            uncertain_ms=round(float(unknown.sum()) * 1000.0 / fps, 1),
            longest_uncertain_ms=round(float(lengths.max()) * 1000.0 / fps, 1) if lengths.size else 0.0,
            identity_changes=int(change[inside, f].sum()),
            causes=[CauseShare(cause=c, share=v) for c, v in sorted(shares, key=lambda x: -x[1]) if v > 0]))
    return out
