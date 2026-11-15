"""Persistent fighter identities from the user's selection(s).

Each selection ("anchor") fixes which detection is the red and the blue
fighter on one frame. From every anchor the identities are propagated
forwards and backwards over tracklet segments:

- While a fighter's segment continues, the identity follows it.
- When it ends (occlusion, overlap, tracker gap) the next segment is chosen
  jointly for both fighters, scoring appearance (similarity to this fighter
  minus similarity to the other one), position/velocity and size. Motion is
  only used inside the same camera shot and for short gaps.
- After a camera cut nothing carries over from the old shot: only appearance
  counts, with stricter thresholds, and a near-tie between "A,B" and "B,A"
  leaves both fighters `uncertain` instead of guessing.
- Overlap ("contact") segments are followed only by tracker continuity and
  are provisional: if appearance does not confirm the same person afterwards
  those frames become `uncertain`.
- Appearance references change only after confident, clean matches.
- One detection is never given to both fighters.
- Third persons: a segment seen in the same frame as a fighter's confirmed
  detection is not that fighter; one seen with both (referee, spectators)
  becomes a negative reference, and a candidate must look more like the
  fighter than like any of them. People much smaller than the largest person
  in view (spectators behind the cage) never take a fighter's identity.

Appearance references are shot-local: inside a shot where the user picked a
fighter, only those picks are used (a close-up looks different from a wide
shot); elsewhere all picks are. Results of neighbouring anchors are merged:
where they disagree, the pass that crossed fewer camera cuts wins; with equal
cuts the frame is `uncertain` (anchor_conflict) rather than picking one.

Since version 6 (v2 Bölüm 2c):

- Camera cuts the preparation missed are found from the stored frame-to-frame
  colour change (`refine_cuts`) and split the tracker's segments and ids: the
  tracker runs through such a cut and can hand a fighter's id to whoever
  stands there in the new shot.
- Appearance model: the propagation runs twice. The first run uses the
  user's picks only; from its confident, clean stretches a model is built:
  samples of each fighter spread over the whole video, and of the third
  persons seen next to both fighters (referee, corner staff). The second run
  uses the model as references everywhere, so a fighter is found again after
  a cut from how he looks in many shots, not in the picked one alone.
- Third persons become references only after being seen next to the
  fighters for several frames (a stray box does not poison them).
- Inside an overlap every frame is checked on its own appearance: a frame
  that looks clearly like this fighter is `tracked` (verified), the others
  stay `occluded` (carried by tracker continuity) with a lower confidence
  the longer no frame could be verified. Nothing is re-assigned backwards:
  where a swap inside an overlap cannot be timed, the frames are `uncertain`.
- The number of temporary-id changes is counted on the final result (once
  per change, whatever the number of selections).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from fight_analyzer.config import IdentitySettings, TrackingSettings
from fight_analyzer.contracts import (
    FighterAnchor,
    FighterId,
    FighterTrackStats,
    ReviewPoint,
    UncertainReason,
    UncertainSegment,
)
from fight_analyzer.pose.cache import PoseArrays

from .appearance import mean_descriptor, similarity
from .prep import PrepData
from .tracklets import Segment, segments_from

IDENTITY_VERSION = 6  # 6: missed cuts, appearance model (two runs), verified overlap frames
TRACKED, OCCLUDED, UNCERTAIN = 0, 1, 2
REASONS = list(UncertainReason)
FIGHTERS = (FighterId.fighter_a, FighterId.fighter_b)
MIN_WEIGHT = 0.5  # summed descriptor quality needed to trust a segment's appearance
MIN_FRAME_QUALITY = 0.4  # descriptor quality needed to use a single overlapping detection
MIN_REL_SCALE = 0.35  # box size (longer side) relative to the largest person in the frame
THIRD_MARGIN = 0.03  # how much more like the fighter than like a known third person
MAX_THIRD_REFS = 48
LONE_AFTER_CUT_DISC = 0.15  # appearance lead needed when one person is placed alone after a cut
ACQUIRE_MIN_WEIGHT = 2.0  # clean appearance evidence (summed quality) to place a fighter without position


@dataclass
class _Seg:
    base: Segment
    desc: np.ndarray
    weight: float
    det_at: dict[int, int]
    centers: np.ndarray  # [k, 2]
    heights: np.ndarray  # [k]
    rel: float = 1.0  # median size relative to the largest person in view

    @property
    def id(self) -> int:
        return self.base.id

    @property
    def track(self) -> int:
        return self.base.track

    @property
    def shot(self) -> int:
        return self.base.shot

    @property
    def contact(self) -> bool:
        return self.base.contact


@dataclass
class _Context:
    arrays: PoseArrays
    prep: PrepData
    segs: dict[int, _Seg]
    frame_segs: list[list[int]]
    rel_scale: np.ndarray  # per detection: longer box side / largest one in its frame
    det_shot: np.ndarray  # per detection: camera shot index
    s: TrackingSettings
    fps: float
    i: IdentitySettings = field(default_factory=IdentitySettings)
    shot_id: np.ndarray = field(default_factory=lambda: np.zeros(0, np.int32))  # [F] shots incl. the extra cuts
    seg_of: np.ndarray = field(default_factory=lambda: np.zeros(0, np.int64))  # per detection: segment id
    track_of: np.ndarray = field(default_factory=lambda: np.zeros(0, np.int64))  # per detection: track id or -1
    det_frame: np.ndarray = field(default_factory=lambda: np.zeros(0, np.int64))  # per detection: its frame
    cuts: list[int] = field(default_factory=list)  # all camera cuts
    extra_cuts: list[int] = field(default_factory=list)  # those the preparation missed

    @property
    def frames(self) -> int:
        return self.arrays.frame_count


def refine_cuts(cut_step: np.ndarray, cuts: list[int], i: IdentitySettings, min_shot: int,
                window: int = 15) -> list[int]:
    """Camera cuts including the ones the preparation missed: a frame whose colour change
    is far above the level around it and stands alone (the frames next to a flash or inside
    a logo transition change a lot too). Cheap on purpose: the change per frame is stored."""
    step = np.asarray(cut_step, np.float64)
    known = np.asarray(sorted(cuts), np.int64)
    found: list[int] = []
    for t in np.flatnonzero(step >= i.extra_cut_floor).tolist():
        if t == 0 or (known.size and int(np.abs(known - t).min()) < min_shot):
            continue
        around = np.concatenate([step[max(1, t - window):t], step[t + 1:t + window + 1]])
        if around.size and step[t] < i.extra_cut_relative * (float(np.median(around)) + 0.002):
            continue
        near = np.concatenate([step[max(1, t - 3):t], step[t + 1:t + 4]])
        if near.size and float(near.max()) >= i.extra_cut_isolation * step[t]:
            continue
        if found and t - found[-1] < min_shot:
            continue
        found.append(t)
    return sorted({*known.tolist(), *found})


def _split(ids: np.ndarray, det_shot: np.ndarray) -> np.ndarray:
    """Ids made unique per camera shot (-1 stays -1)."""
    out = np.full(ids.shape, -1, np.int64)
    ok = ids >= 0
    if ok.any():
        pairs = np.stack([ids[ok].astype(np.int64), det_shot[ok]], axis=1)
        out[ok] = np.unique(pairs, axis=0, return_inverse=True)[1].reshape(-1)
    return out


def build_context(arrays: PoseArrays, prep: PrepData, s: TrackingSettings, fps: float,
                  i: IdentitySettings | None = None) -> _Context:
    i = i or IdentitySettings()
    det_frame = np.repeat(np.arange(arrays.frame_count), np.diff(arrays.det_offsets)).astype(np.int64)
    contact = prep.contact.astype(bool)
    cuts = refine_cuts(prep.cut_step, list(prep.cuts), i, s.min_shot_frames)
    extra = sorted(set(cuts) - set(prep.cuts))
    shot_id = np.zeros(arrays.frame_count, np.int32)
    for c in cuts:
        if 0 < c < arrays.frame_count:
            shot_id[c:] += 1
    det_shot = shot_id[det_frame].astype(np.int64)
    # The tracker ran through the missed cuts: its ids and segments end there.
    seg_of = _split(prep.seg_id, det_shot) if extra else prep.seg_id.astype(np.int64)
    track_of = _split(prep.track_id, det_shot) if extra else prep.track_id.astype(np.int64)
    segs: dict[int, _Seg] = {}
    frame_segs: list[list[int]] = [[] for _ in range(arrays.frame_count)]
    boxes = arrays.boxes
    for seg in segments_from(seg_of, det_frame, track_of, contact, shot_id):
        good = (~contact[seg.dets]) & (prep.feat_q[seg.dets] > 0)
        dets_good = seg.dets[good]
        desc = mean_descriptor(prep.feat[dets_good], prep.feat_q[dets_good])
        b = boxes[seg.dets]
        centers = np.stack([(b[:, 0] + b[:, 2]) / 2, (b[:, 1] + b[:, 3]) / 2], axis=1)
        segs[seg.id] = _Seg(base=seg, desc=desc, weight=float(prep.feat_q[dets_good].sum()),
                            det_at={int(f): int(d) for f, d in zip(seg.frames, seg.dets)},
                            centers=centers, heights=b[:, 3] - b[:, 1])
        for f in seg.frames:
            frame_segs[int(f)].append(seg.id)
    scale = np.maximum(boxes[:, 2] - boxes[:, 0], boxes[:, 3] - boxes[:, 1]).astype(np.float32)
    largest = np.zeros(arrays.frame_count, np.float32)
    np.maximum.at(largest, det_frame, scale)
    rel_scale = scale / np.maximum(largest[det_frame], 1.0)
    for seg in segs.values():
        seg.rel = float(np.median(rel_scale[seg.base.dets]))
    return _Context(arrays=arrays, prep=prep, segs=segs, frame_segs=frame_segs, rel_scale=rel_scale,
                    det_shot=det_shot, s=s, fps=fps, i=i, shot_id=shot_id, seg_of=seg_of, track_of=track_of,
                    det_frame=det_frame,
                    cuts=cuts, extra_cuts=extra)


@dataclass
class AppearanceModel:
    """How the fighters and the third persons look, sampled from the first run."""

    refs: list[list[tuple[int, np.ndarray]]]  # per fighter: (shot, descriptor)
    third: list[np.ndarray]
    height_ratio: float | None = None  # red / blue box height while both stand apart (reported, not used)
    # Per fighter: how much like the model he must look to be placed without a position (after
    # a cut or a long gap). His own samples all look like another one of them at least this
    # much, less a tolerance; someone in a crowd shot who merely looks more like him than
    # like the other fighter stays below it.
    floor: list[float] = field(default_factory=lambda: [0.0, 0.0])

    @property
    def usable(self) -> bool:
        return bool(self.refs[0]) and bool(self.refs[1])


@dataclass
class _RunOutput:
    state: np.ndarray
    det: np.ndarray
    conf: np.ndarray
    reason: np.ndarray
    reacquisitions: list[int] = field(default_factory=lambda: [0, 0])
    swap_corrections: int = 0
    identity_switches: int = 0
    review: list[ReviewPoint] = field(default_factory=list)


class _Propagation:
    def __init__(self, ctx: _Context, refs: list[list[tuple[int, np.ndarray]]], direction: int,
                 out: _RunOutput, model: AppearanceModel | None = None) -> None:
        self.ctx = ctx
        self.s = ctx.s
        self.dir = direction
        self.anchor_refs = refs
        self.model_refs = model.refs if model else [[], []]
        self.own_floor = [max(ctx.s.min_similarity + 0.1, v) for v in (model.floor if model else [0.0, 0.0])]
        self.static_third = list(model.third) if model else []
        self.co_seen: dict[int, int] = {}  # segment -> frames seen next to a confirmed fighter
        self._ref_cache: dict[tuple, np.ndarray] = {}
        self.adaptive: list[tuple[int, np.ndarray] | None] = [None, None]  # (shot, descriptor)
        self.ref_version = [0, 0]
        self.out = out
        self._sim_cache: dict[tuple, tuple[float, float]] = {}
        # Segments known not to be fighter f (seen in the same frame as f's confirmed box),
        # and descriptors of people known to be neither fighter.
        self.excluded: list[set[int]] = [set(), set()]
        self.third_ids: set[int] = set()
        self.third_refs: list[np.ndarray] = []
        self.third_version = 0
        self._third_cache: dict[tuple, float] = {}
        fps = ctx.fps
        self.short_gap = max(1, round(self.s.short_gap_s * fps))
        self.motion_gap = max(1, round(self.s.motion_gap_s * fps))

    # ---- helpers --------------------------------------------------------
    def _refs(self, f: int, shot: int) -> np.ndarray:
        """The user's picks of fighter f in this shot if any (with the model's samples from
        that shot), otherwise all picks and the whole model; the adaptive reference only
        inside the shot it was learned in."""
        key = (f, shot, self.ref_version[f])
        if key not in self._ref_cache:
            same = [d for sh, d in self.anchor_refs[f] if sh == shot]
            if same:
                refs = same + [d for sh, d in self.model_refs[f] if sh == shot]
            else:
                refs = [d for _, d in self.anchor_refs[f]] + [d for _, d in self.model_refs[f]]
            adaptive = self.adaptive[f]
            if adaptive is not None and adaptive[0] == shot:
                refs = [*refs, adaptive[1]]
            self._ref_cache[key] = np.stack(refs)
        return self._ref_cache[key]

    def _sims(self, f: int, seg: _Seg) -> tuple[float, float]:
        key = (f, seg.id, self.ref_version[0], self.ref_version[1])
        if key not in self._sim_cache:
            own = float(similarity(self._refs(f, seg.shot), seg.desc).max())
            other = float(similarity(self._refs(1 - f, seg.shot), seg.desc).max())
            self._sim_cache[key] = (own, other)
        return self._sim_cache[key]

    def _det_sims(self, f: int, d: int) -> tuple[float, float] | None:
        """Appearance of one detection (used inside overlaps, where segment averages mix people)."""
        prep = self.ctx.prep
        if prep.feat_q[d] < MIN_FRAME_QUALITY:
            return None
        key = ("det", f, d, self.ref_version[0], self.ref_version[1])
        if key not in self._sim_cache:
            shot = int(self.ctx.det_shot[d])
            own = float(similarity(self._refs(f, shot), prep.feat[d]).max())
            other = float(similarity(self._refs(1 - f, shot), prep.feat[d]).max())
            self._sim_cache[key] = (own, other)
        return self._sim_cache[key]

    def _third(self, key: tuple, desc: np.ndarray) -> float:
        """Similarity to the closest known third person (0 when none is known yet)."""
        refs = self.static_third + self.third_refs
        if not refs:
            return 0.0
        key = (*key, self.third_version)
        if key not in self._third_cache:
            self._third_cache[key] = float(similarity(np.stack(refs), desc).max())
        return self._third_cache[key]

    def _verified(self, f: int, d: int, margin: float | None = None) -> bool:
        """This detection on its own looks clearly like fighter f (used inside overlaps), and
        no box overlapping it looks like him as well: with one fighter in front of the other
        both boxes show the one in front, and which skeleton is his cannot be told."""
        sims = self._det_sims(f, d)
        if sims is None:
            return False
        own, other = sims
        margin = self.ctx.i.verify_margin if margin is None else margin
        third = self._third(("det", d), self.ctx.prep.feat[d])
        if own < self.s.min_similarity or own - max(other, third) < margin:
            return False
        key = ("alone", f, d, self.ref_version[0], self.ref_version[1])
        if key not in self._sim_cache:
            self._sim_cache[key] = self._alone(f, d, own)
        return bool(self._sim_cache[key])

    def _alone(self, f: int, d: int, own: float) -> bool:
        ctx = self.ctx
        boxes = ctx.arrays.boxes
        t = int(ctx.det_frame[d])
        x1, y1, x2, y2 = boxes[d]
        for other in range(int(ctx.arrays.det_offsets[t]), int(ctx.arrays.det_offsets[t + 1])):
            if other == d or ctx.rel_scale[other] < MIN_REL_SCALE:
                continue
            ox1, oy1, ox2, oy2 = boxes[other]
            if min(x2, ox2) <= max(x1, ox1) or min(y2, oy2) <= max(y1, oy1):
                continue  # the boxes do not touch
            sims = self._det_sims(f, other)
            if sims is not None and sims[0] >= own - ctx.i.verify_margin:
                return False
        return True

    def _contradicts(self, f: int, d: int) -> bool:
        sims = self._det_sims(f, d)
        if sims is None:
            return False
        own, other = sims
        third = self._third(("det", d), self.ctx.prep.feat[d])
        return own < self.s.min_similarity or own < other - 0.05 or own < third

    def _note_cooccurrence(self, t: int, cur: list[_Seg | None]) -> None:
        """Whoever is in view next to a fighter's confirmed (non-overlapping) box is someone else."""
        confirmed = [f for f in (0, 1) if cur[f] is not None and not cur[f].contact
                     and cur[f].det_at.get(t) is not None]
        if not confirmed:
            return
        mine = {seg.id for seg in cur if seg is not None}
        for sid in self.ctx.frame_segs[t]:
            if sid in mine:
                continue
            for f in confirmed:
                self.excluded[f].add(sid)
            seg = self.ctx.segs[sid]
            self.co_seen[sid] = self.co_seen.get(sid, 0) + 1
            # People far smaller than the fighters (spectators) never take an identity; as
            # references their coarse look only blocks the fighter who resembles them.
            if (sid not in self.third_ids and not seg.contact and seg.weight >= MIN_WEIGHT
                    and seg.rel >= MIN_REL_SCALE and self.co_seen[sid] >= self.ctx.i.third_min_frames
                    and sid in self.excluded[0] and sid in self.excluded[1]):
                self.third_ids.add(sid)
                self.third_refs = (self.third_refs + [seg.desc])[-MAX_THIRD_REFS:]
                self.third_version += 1

    def _exit_motion(self, seg: _Seg, t: int) -> tuple[np.ndarray, np.ndarray, float]:
        """Centre, per-frame velocity (in travel direction) and height where the fighter was last seen."""
        frames = seg.base.frames
        idx = int(np.searchsorted(frames, t))
        idx = min(max(idx, 0), len(frames) - 1)
        lo = max(0, idx - 4) if self.dir > 0 else idx
        hi = idx if self.dir > 0 else min(len(frames) - 1, idx + 4)
        dt = float(frames[hi] - frames[lo])
        vel = (seg.centers[hi] - seg.centers[lo]) / dt if dt > 0 else np.zeros(2)
        return seg.centers[idx], vel * self.dir, float(seg.heights[idx])

    # ---- main loop ------------------------------------------------------
    def run(self, anchor_frame: int, anchor_dets: tuple[int, int], stop: int) -> None:
        ctx, s, out = self.ctx, self.s, self.out
        seg_of = ctx.seg_of
        cur: list[_Seg | None] = [ctx.segs[int(seg_of[d])] if d >= 0 else None for d in anchor_dets]
        conf = [1.0, 1.0]
        last: list[tuple[_Seg, int] | None] = [(seg, anchor_frame) if seg else None for seg in cur]
        lost_since = [anchor_frame, anchor_frame]
        lost_reason = [UncertainReason.lost, UncertainReason.lost]
        # A fighter marked "not in the picture" has no position to continue from,
        # and nobody on the anchor frame is that fighter.
        after_cut = [seg is None for seg in cur]
        for f in (0, 1):
            if cur[f] is None:
                self.excluded[f].update(ctx.frame_segs[anchor_frame])
        provisional: list[list[int]] = [[], []]
        prov_track = [-2, -2]
        track_owner: dict[int, tuple[int, int]] = {}
        frames = range(anchor_frame, stop + self.dir, self.dir)
        for t in frames:
            if t != anchor_frame and ctx.shot_id[t] != ctx.shot_id[t - self.dir]:
                for f in (0, 1):  # camera cut: positions mean nothing in the new shot
                    cur[f] = None
                    lost_since[f] = t
                    lost_reason[f] = UncertainReason.camera_cut
                    after_cut[f] = True
            for f in (0, 1):
                seg = cur[f]
                if seg is None:
                    continue
                ended = (self.dir > 0 and t > seg.base.end) or (self.dir < 0 and t < seg.base.start)
                # Inside an overlap the tracker may hand the box to someone else (e.g. the
                # referee stepping in front): check every frame's own appearance.
                d = seg.det_at.get(t)
                if not ended and seg.contact and d is not None and self._contradicts(f, d):
                    ended = True
                if ended:
                    last[f] = (seg, t - self.dir)
                    cur[f] = None
                    lost_since[f] = t
                    lost_reason[f] = UncertainReason.overlap if seg.contact else UncertainReason.lost
            free = [f for f in (0, 1) if cur[f] is None]
            if free:
                owned = {seg.id for seg in cur if seg is not None}
                cands = [sid for sid in ctx.frame_segs[t] if sid not in owned]
                if cands:
                    self._decide(t, free, cands, cur, conf, last, lost_since, lost_reason, after_cut,
                                 provisional, prov_track, track_owner)
            for f in (0, 1):
                seg = cur[f]
                if seg is not None:
                    track_owner[seg.track] = (f, t)
                    d = seg.det_at.get(t)
                    if d is None:  # tracker skipped this frame inside the segment
                        out.state[t, f], out.conf[t, f] = OCCLUDED, 0.0
                    elif not seg.contact:
                        out.det[t, f], out.state[t, f], out.conf[t, f] = d, TRACKED, conf[f]
                    elif self._verified(f, d):
                        # the frame's own appearance confirms the fighter: so do the overlap
                        # frames the tracker carried him through up to here
                        out.det[t, f], out.state[t, f] = d, TRACKED
                        out.conf[t, f] = conf[f] * ctx.i.confidence_verified
                        provisional[f] = []
                    else:  # carried by continuity; the confidence is set once all frames are known
                        out.det[t, f], out.state[t, f], out.conf[t, f] = d, OCCLUDED, conf[f]
                        provisional[f].append(t)
                    continue
                gap = abs(t - lost_since[f])
                if not after_cut[f] and gap < self.short_gap and lost_reason[f] != UncertainReason.ambiguous:
                    out.state[t, f], out.conf[t, f] = OCCLUDED, 0.0
                else:
                    if provisional[f]:  # never confirmed after the overlap
                        self._drop_provisional(f, provisional)
                    out.state[t, f], out.conf[t, f] = UNCERTAIN, 0.0
                    out.reason[t, f] = REASONS.index(lost_reason[f])
            self._note_cooccurrence(t, cur)
        for f, d in enumerate(anchor_dets):
            present = d >= 0
            out.state[anchor_frame, f] = TRACKED if present else UNCERTAIN
            out.conf[anchor_frame, f] = 1.0 if present else 0.0
            out.reason[anchor_frame, f] = -1 if present else REASONS.index(UncertainReason.lost)
            out.det[anchor_frame, f] = d

    def _drop_provisional(self, f: int, provisional: list[list[int]]) -> None:
        for pt in provisional[f]:
            self.out.state[pt, f] = UNCERTAIN
            self.out.det[pt, f] = -1
            self.out.conf[pt, f] = 0.0
            self.out.reason[pt, f] = REASONS.index(UncertainReason.overlap)
        provisional[f] = []

    def _score(self, f: int, seg: _Seg, t: int, last, after_cut) -> tuple[float, bool, float, float, bool]:
        """total, feasible, threshold, appearance discrimination, appearance usable"""
        s = self.s
        d_t = seg.det_at[t]
        if seg.id in self.excluded[f] or self.ctx.rel_scale[d_t] < MIN_REL_SCALE:
            return 0.0, False, s.accept, 0.0, False
        if seg.contact:  # judge the detection in this frame, not the mixed segment average
            sims = self._det_sims(f, d_t)
            app_valid = sims is not None
            own, other = sims if sims else (0.0, 0.0)
            third = self._third(("det", d_t), self.ctx.prep.feat[d_t]) if app_valid else 0.0
        else:
            app_valid = seg.weight >= MIN_WEIGHT
            own, other = self._sims(f, seg) if app_valid else (0.0, 0.0)
            third = self._third(("seg", seg.id), seg.desc) if app_valid else 0.0
        disc = own - other
        app_term = min(1.0, max(0.0, 0.5 + 2.0 * disc)) if app_valid else 0.5
        prev = last[f]
        gap = abs(t - prev[1]) if prev else 10**9
        use_motion = prev is not None and not after_cut[f] and prev[0].shot == seg.shot and gap <= self.motion_gap
        if use_motion:
            center, vel, height = self._exit_motion(prev[0], prev[1])
            d = seg.det_at[t]
            box = self.ctx.arrays.boxes[d]
            c = np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2])
            dist = float(np.linalg.norm(center + vel * gap - c)) / max(height, 1.0)
            sigma = 0.35 + 0.03 * gap
            motion = math.exp(-0.5 * (dist / sigma) ** 2)
            size = math.exp(-abs(math.log(max(box[3] - box[1], 1.0) / max(height, 1.0))) / 0.3)
            same_track = 0.1 if seg.track >= 0 and seg.track == prev[0].track else 0.0
            total = 0.5 * app_term + 0.35 * motion + 0.15 * size + same_track
            feasible = motion >= 0.25 and (not app_valid or (own >= s.min_similarity and disc >= -0.03
                                                             and own >= third + THIRD_MARGIN))
            return total, feasible, s.accept, disc, app_valid
        # New shot or long gap: appearance only, stricter. Never from a segment with too little
        # clean evidence. An overlapping box mixes two people, so there the frame's own
        # appearance must be far clearer than what verifies a frame the tracker carried
        # (fighters at striking range overlap for most of a shot: waiting for a clean
        # stretch leaves them unknown long after every cut).
        if seg.contact:
            feasible = (app_valid and own >= self.own_floor[f]
                        and self._verified(f, d_t, 2 * self.ctx.i.verify_margin))
        else:
            feasible = (app_valid and seg.weight >= ACQUIRE_MIN_WEIGHT and own >= self.own_floor[f]
                        and disc >= 0.04 and own >= third + 2 * THIRD_MARGIN)
        return app_term, feasible, s.accept_after_cut, disc, app_valid

    def _decide(self, t, free, cands, cur, conf, last, lost_since, lost_reason, after_cut,
                provisional, prov_track, track_owner) -> None:
        s, ctx, out = self.s, self.ctx, self.out
        scores: dict[tuple[int, int], tuple[float, bool, float, float, bool]] = {}
        for f in free:
            for sid in cands:
                scores[(f, sid)] = self._score(f, ctx.segs[sid], t, last, after_cut)

        def ok(f, sid):
            total, feasible, thr, _, _ = scores[(f, sid)]
            return feasible and total >= thr

        # Best joint assignment (each fighter gets one segment or none, never the same one).
        options: list[dict[int, int]] = [{}]
        for f in free:
            options = [{**o, f: sid} for o in options for sid in cands
                       if ok(f, sid) and sid not in o.values()] + options
        best = max(options, key=lambda o: sum(scores[(f, sid)][0] for f, sid in o.items()))
        if not best:
            return
        # After a cut with a single person to place there is no joint "A,B vs B,A" check:
        # that person must look clearly more like this fighter than like the other one.
        if len(best) == 1 and len(free) == 2:
            ((f, sid),) = best.items()
            if after_cut[f] and scores[(f, sid)][3] < LONE_AFTER_CUT_DISC:
                lost_reason[f] = UncertainReason.ambiguous
                return
        # Ambiguity: the swapped assignment must be clearly worse.
        if len(best) == 2:
            (fa, sa), (fb, sb) = best.items()
            swapped = scores[(fa, sb)][0] + scores[(fb, sa)][0]
            if sum(scores[(f, sid)][0] for f, sid in best.items()) - swapped < s.margin:
                for f in (fa, fb):
                    lost_reason[f] = UncertainReason.ambiguous
                return
        for f, sid in best.items():
            total = scores[(f, sid)][0]
            taken = set(best.values())
            alternatives = [scores[(f, o)][0] for o in cands if o not in taken and scores[(f, o)][1]]
            margin = total - max(alternatives) if alternatives else 1.0
            if margin < s.margin:
                lost_reason[f] = UncertainReason.ambiguous
                continue
            self._accept(t, f, ctx.segs[sid], total, margin, scores[(f, sid)], cands, cur, conf, last,
                         lost_since, after_cut, provisional, prov_track, track_owner)

    def _accept(self, t, f, seg: _Seg, total, margin, score, cands, cur, conf, last, lost_since,
                after_cut, provisional, prov_track, track_owner) -> None:
        s, out, ctx = self.s, self.out, self.ctx
        _, _, _, disc, app_valid = score
        prev = last[f][0] if last[f] else None
        long_loss = after_cut[f] or abs(t - lost_since[f]) >= self.short_gap
        fighter = FIGHTERS[f]
        swap_corrected = False
        if prev is not None and seg.track != prev.track:
            continuing = [c for c in cands if ctx.segs[c].track == prev.track and prev.track >= 0]
            if continuing and not after_cut[f]:
                # The tracker continued this fighter's track, but appearance says it is someone else.
                swap_corrected = True
                out.swap_corrections += 1
                out.review.append(ReviewPoint(frame_index=t, fighter_id=fighter, kind="swap_corrected",
                                              margin=round(margin, 3)))
        if long_loss:
            out.reacquisitions[f] += 1
        owner = track_owner.get(seg.track)
        if seg.track >= 0 and owner and owner[0] != f and abs(t - owner[1]) <= self.short_gap:
            out.identity_switches += 1
            out.review.append(ReviewPoint(frame_index=t, fighter_id=fighter, kind="identity_switch",
                                          margin=round(margin, 3)))
        if margin < 2 * s.margin or (after_cut[f] and margin < 3 * s.margin):
            out.review.append(ReviewPoint(frame_index=t, fighter_id=fighter,
                                          kind="after_cut" if after_cut[f] else "reacquired_low_margin",
                                          margin=round(margin, 3)))
        if provisional[f]:
            # Overlap frames were followed by continuity only. Keep them when the
            # person found afterwards is verified as this fighter and no tracker
            # swap was detected; otherwise we cannot tell when the swap happened.
            if swap_corrected or (app_valid and disc < 0):
                self._drop_provisional(f, provisional)
            else:
                provisional[f] = []
        cur[f] = seg
        conf[f] = float(min(1.0, max(0.05, total * min(1.0, 0.5 + margin / 0.3))))
        after_cut[f] = False
        if seg.contact:
            prov_track[f] = seg.track
        elif (total >= s.update_confidence and margin >= 2 * s.margin and seg.weight >= 2.0):
            prev_ref = self.adaptive[f]
            if prev_ref is None or prev_ref[0] != seg.shot:
                self.adaptive[f] = (seg.shot, seg.desc.copy())
            else:
                self.adaptive[f] = (seg.shot, 0.8 * prev_ref[1] + 0.2 * seg.desc)
            self.ref_version[f] += 1


@dataclass
class IdentityResult:
    state: np.ndarray  # [F, 2] int8
    det: np.ndarray  # [F, 2] int64, -1 = none
    conf: np.ndarray  # [F, 2] float32
    reason: np.ndarray  # [F, 2] int8, -1 = none
    fighters: list[FighterTrackStats]
    uncertain_segments: list[UncertainSegment]
    review_points: list[ReviewPoint]
    identity_switches: int
    swap_corrections: int
    anchor_conflicts: int
    change: np.ndarray | None = None  # [F, 2] bool: the temporary id under the fighter changed at this frame
    shot_id: np.ndarray | None = None  # [F] camera shots, the extra cuts included
    extra_cuts: list[int] = field(default_factory=list)
    model: AppearanceModel | None = None


def _empty(frames: int) -> _RunOutput:
    return _RunOutput(state=np.full((frames, 2), UNCERTAIN, np.int8), det=np.full((frames, 2), -1, np.int64),
                      conf=np.zeros((frames, 2), np.float32), reason=np.full((frames, 2), -1, np.int8))


def _anchor_refs(ctx: _Context, anchors: list[tuple[int, int, int]]) -> list[list[tuple[int, np.ndarray]]]:
    refs: list[list[tuple[int, np.ndarray]]] = [[], []]
    for frame, red, blue in anchors:
        for f, d in enumerate((red, blue)):
            if d < 0:  # marked as not in the picture on this frame
                continue
            seg = ctx.segs[int(ctx.seg_of[d])]
            refs[f].append((int(ctx.shot_id[frame]),
                            seg.desc if seg.weight >= MIN_WEIGHT else ctx.prep.feat[d]))
    return refs


def _merge(fwd: _RunOutput, bwd: _RunOutput, anchor_frames: list[int], shot_id: np.ndarray):
    """Combine forward and backward passes. Before the first anchor only the backward
    pass exists, after the last only the forward one. In between both do: a verified
    result fills the other's uncertainty; on disagreement the pass that crossed fewer
    camera cuts (so relied less on appearance alone) wins, and equal cuts mean the
    frame stays uncertain (anchor_conflict)."""
    frames = fwd.state.shape[0]
    state, det, conf, reason = fwd.state.copy(), fwd.det.copy(), fwd.conf.copy(), fwd.reason.copy()
    first = anchor_frames[0]
    state[:first], det[:first], conf[:first], reason[:first] = (
        bwd.state[:first], bwd.det[:first], bwd.conf[:first], bwd.reason[:first])
    shot = shot_id.astype(np.int64)
    both = np.zeros(frames, bool)
    hops_f = np.zeros(frames, np.int64)
    hops_b = np.zeros(frames, np.int64)
    for a, b in zip(anchor_frames, anchor_frames[1:]):
        both[a + 1:b] = True
        hops_f[a + 1:b] = shot[a + 1:b] - shot[a]
        hops_b[a + 1:b] = shot[b] - shot[a + 1:b]
    conflicts = 0
    for f in (0, 1):
        fs, bs = fwd.state[:, f], bwd.state[:, f]
        f_known, b_known = fs != UNCERTAIN, bs != UNCERTAIN
        clash = (both & f_known & b_known & (fwd.det[:, f] != bwd.det[:, f])
                 & (fwd.det[:, f] >= 0) & (bwd.det[:, f] >= 0))
        take_b = (both & ~f_known & b_known) | (clash & (hops_b < hops_f))
        state[take_b, f], det[take_b, f], conf[take_b, f] = bs[take_b], bwd.det[take_b, f], bwd.conf[take_b, f]
        reason[take_b, f] = -1
        agree = both & f_known & b_known & ~clash
        conf[agree, f] = np.maximum(fwd.conf[agree, f], bwd.conf[agree, f])
        tie = clash & (hops_f == hops_b)
        state[tie, f], det[tie, f], conf[tie, f] = UNCERTAIN, -1, 0.0
        reason[tie, f] = REASONS.index(UncertainReason.anchor_conflict)
        conflicts += int(np.count_nonzero(np.diff(tie.astype(np.int8)) == 1) + int(tie[0]))
    return state, det, conf, reason, conflicts


def _spread(items: list[tuple[int, float, object]], frames: int, count: int) -> list:
    """Up to `count` items (frame, weight, value) spread over the video: the heaviest of each time bin."""
    best: dict[int, tuple[float, object]] = {}
    for frame, weight, value in items:
        k = min(count - 1, frame * count // max(1, frames))
        if k not in best or weight > best[k][0]:
            best[k] = (weight, value)
    return [best[k][1] for k in sorted(best)]


def build_model(ctx: _Context, state: np.ndarray, det: np.ndarray, conf: np.ndarray) -> AppearanceModel:
    """Appearance model from a first result: for each fighter, clean stretches he was followed
    through with confidence, spread over the video; for third persons, clean stretches of
    people of fighter size seen next to both fighters. Stretches inside overlaps are never
    used (their pixels mix two people)."""
    i, frames = ctx.i, ctx.frames
    seg_of = ctx.seg_of
    owner: dict[int, list[int]] = {}  # segment -> frames given to red / blue
    sure: dict[int, list[int]] = {}
    for f in (0, 1):
        ok = det[:, f] >= 0
        segs, counts = np.unique(seg_of[det[ok, f]], return_counts=True)
        for sid, n in zip(segs.tolist(), counts.tolist()):
            owner.setdefault(sid, [0, 0])[f] = n
        good = ok & (state[:, f] == TRACKED) & (conf[:, f] >= i.model_min_confidence)
        segs, counts = np.unique(seg_of[det[good, f]], return_counts=True)
        for sid, n in zip(segs.tolist(), counts.tolist()):
            sure.setdefault(sid, [0, 0])[f] = n
    refs: list[list[tuple[int, np.ndarray]]] = [[], []]
    for f in (0, 1):
        items = []
        for sid, counts in sure.items():
            seg = ctx.segs[sid]
            if (seg.contact or seg.weight < i.model_min_weight or owner[sid][1 - f]
                    or counts[f] < 0.8 * len(seg.base.frames)):
                continue
            items.append((seg.base.start, seg.weight, (seg.shot, seg.desc)))
        refs[f] = _spread(items, frames, i.model_samples)
    # Third persons: in view while both fighters are followed on other boxes.
    both = (state[:, 0] == TRACKED) & (state[:, 1] == TRACKED) & (det[:, 0] >= 0) & (det[:, 1] >= 0)
    seen: dict[int, int] = {}
    for t in np.flatnonzero(both).tolist():
        for sid in ctx.frame_segs[t]:
            if sid not in owner:
                seen[sid] = seen.get(sid, 0) + 1
    items = []
    for sid, n in seen.items():
        seg = ctx.segs[sid]
        if seg.contact or seg.weight < i.model_min_weight or n < i.third_min_frames:
            continue
        if seg.rel >= MIN_REL_SCALE:  # smaller people never take a fighter's identity anyway
            items.append((seg.base.start, seg.weight * seg.rel, seg.desc))
    third = _spread(items, frames, i.third_samples)
    apart = both & ~ctx.prep.contact[np.maximum(det[:, 0], 0)].astype(bool) \
        & ~ctx.prep.contact[np.maximum(det[:, 1], 0)].astype(bool)
    ratio = None
    if int(apart.sum()) >= 30:
        boxes = ctx.arrays.boxes
        h = [boxes[det[apart, f], 3] - boxes[det[apart, f], 1] for f in (0, 1)]
        ratio = round(float(np.median(h[0] / np.maximum(h[1], 1.0))), 3)
    floor = [0.0, 0.0]
    for f in (0, 1):
        if len(refs[f]) >= 2:
            sim = similarity(np.stack([d for _, d in refs[f]]), np.stack([d for _, d in refs[f]]))
            np.fill_diagonal(sim, 0.0)
            floor[f] = max(0.0, float(sim.max(axis=1).min()) - i.model_tolerance)
    return AppearanceModel(refs=refs, third=third, height_ratio=ratio, floor=floor)


def _propagate(ctx: _Context, resolved: list[tuple[int, int, int]], refs, model: AppearanceModel | None):
    frames = ctx.frames
    fwd, bwd = _empty(frames), _empty(frames)
    for k, (frame, red, blue) in enumerate(resolved):
        end = resolved[k + 1][0] - 1 if k + 1 < len(resolved) else frames - 1
        start = resolved[k - 1][0] + 1 if k > 0 else 0
        _Propagation(ctx, refs, +1, fwd, model).run(frame, (red, blue), end)
        _Propagation(ctx, refs, -1, bwd, model).run(frame, (red, blue), start)
    state, det, conf, reason, conflicts = _merge(fwd, bwd, [a[0] for a in resolved], ctx.shot_id)
    # Never one detection for both fighters.
    dup = (det[:, 0] >= 0) & (det[:, 0] == det[:, 1])
    loser = np.where(conf[:, 0] >= conf[:, 1], 1, 0)
    for t in np.flatnonzero(dup):
        f = int(loser[t])
        state[t, f], det[t, f], conf[t, f] = UNCERTAIN, -1, 0.0
        reason[t, f] = REASONS.index(UncertainReason.ambiguous)
    return state, det, conf, reason, conflicts, fwd, bwd


def _nearest(mask: np.ndarray) -> np.ndarray:
    """Per frame: distance in frames to the nearest True (a large number when there is none)."""
    n = mask.size
    idx = np.arange(n)
    far = 10**9
    last = np.maximum.accumulate(np.where(mask, idx, -far))
    nxt = np.minimum.accumulate(np.where(mask, idx, far)[::-1])[::-1]
    return np.minimum(idx - last, nxt - idx)


def track_change_frames(ctx: _Context, det: np.ndarray) -> np.ndarray:
    """[F, 2] bool: frames at which the temporary tracker id under a fighter differs from the
    one he had before (unconfirmed single detections have no id and are skipped)."""
    out = np.zeros(det.shape, bool)
    for f in (0, 1):
        present = np.flatnonzero(det[:, f] >= 0)
        ids = ctx.track_of[det[present, f]]
        known = ids >= 0
        frames, ids = present[known], ids[known]
        if ids.size > 1:
            out[frames[1:][ids[1:] != ids[:-1]], f] = True
    return out


def assign(ctx: _Context, anchors: list[FighterAnchor]) -> IdentityResult:
    """Anchors use per-frame detection ids; they are resolved to global indices here."""
    offsets = ctx.arrays.det_offsets
    resolved = sorted((a.frame_index, *(-1 if d is None else int(offsets[a.frame_index]) + d
                                        for d in a.detection_ids()))
                      for a in anchors)
    refs = _anchor_refs(ctx, resolved)
    state, det, conf, reason, conflicts, fwd, bwd = _propagate(ctx, resolved, refs, None)
    model = build_model(ctx, state, det, conf)
    if model.usable:  # second run: the same rules with the model as references
        state, det, conf, reason, conflicts, fwd, bwd = _propagate(ctx, resolved, refs, model)

    fps = ctx.fps
    # Overlap frames that could not be verified: the identity rests on tracker continuity,
    # the less so the longer nothing was verified.
    window = max(1, round(ctx.i.verify_window_s * fps))
    for f in (0, 1):
        carried = (state[:, f] == OCCLUDED) & (det[:, f] >= 0)
        recent = _nearest(state[:, f] == TRACKED) <= window
        conf[carried & recent, f] *= ctx.i.confidence_recent
        conf[carried & ~recent, f] *= ctx.i.confidence_unverified
    change = track_change_frames(ctx, det)
    stats, segments = [], []
    for f in (0, 1):
        st = state[:, f]
        unc = st == UNCERTAIN
        runs = _runs(unc)
        longest = max((b - a + 1 for a, b in runs), default=0)
        for a, b in runs:
            vals = reason[a:b + 1, f]
            vals = vals[vals >= 0]
            r = REASONS[int(np.bincount(vals).argmax())] if vals.size else UncertainReason.lost
            segments.append(UncertainSegment(fighter_id=FIGHTERS[f], start_frame=a, end_frame=b, reason=r))
        tracked = st == TRACKED
        stats.append(FighterTrackStats(
            fighter_id=FIGHTERS[f],
            tracked_frames=int(tracked.sum()),
            occluded_frames=int((st == OCCLUDED).sum()),
            uncertain_frames=int(unc.sum()),
            uncertain_ms=round(float(unc.sum()) * 1000.0 / fps, 1),
            longest_uncertain_ms=round(longest * 1000.0 / fps, 1),
            reacquisitions=fwd.reacquisitions[f] + bwd.reacquisitions[f],
            track_changes=int(change[:, f].sum()),
            mean_confidence=round(float(conf[tracked, f].mean()) if tracked.any() else 0.0, 3),
        ))
    review = sorted({(p.frame_index, p.fighter_id, p.kind): p for p in fwd.review + bwd.review}.values(),
                    key=lambda p: p.frame_index)[:300]
    segments.sort(key=lambda seg: seg.start_frame)
    return IdentityResult(state=state, det=det, conf=conf, reason=reason, fighters=stats,
                          uncertain_segments=segments, review_points=review,
                          identity_switches=fwd.identity_switches + bwd.identity_switches,
                          swap_corrections=fwd.swap_corrections + bwd.swap_corrections,
                          anchor_conflicts=conflicts, change=change, shot_id=ctx.shot_id,
                          extra_cuts=list(ctx.extra_cuts), model=model if model.usable else None)


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    if not mask.any():
        return []
    m = mask.astype(np.int8)
    starts = np.flatnonzero(np.diff(np.concatenate([[0], m])) == 1)
    ends = np.flatnonzero(np.diff(np.concatenate([m, [0]])) == -1)
    return list(zip(starts.tolist(), ends.tolist()))
