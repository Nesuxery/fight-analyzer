/**
 * Data quality of a fighter in a frame range, from the tracking timeline.
 *
 * Mirrors backend/fight_analyzer/tracking/quality.py `summarize` (the API serves
 * that for the whole bout and the rounds; the browser needs the same for the scope
 * that follows the playhead). Both are checked against
 * shared/fixtures/track-quality.json. Excluded parts are not fight time: their
 * frames are left out and break an uncertain stretch.
 */
import type { ExcludedSegment, QualityCause, TrackingTimeline } from "../contracts/generated";
import type { Side } from "./analysis";
import type { FrameRange } from "./scope";

export const QUALITY_CAUSES: readonly QualityCause[] = ["no_footage", "camera", "overlap", "image"];

interface SideIndex {
  measurable: Uint32Array;
  occluded: Uint32Array;
  uncertain: Uint32Array;
  changes: Uint32Array;
  causes: Uint32Array[]; // in QUALITY_CAUSES order
  /** Uncertain stretches of fight time, [start, end] inclusive. */
  uncertainRuns: [number, number][];
}

/** Prefix sums over the frames, so a summary of any range is cheap (it follows the playhead). */
export interface QualityIndex {
  frameCount: number;
  fps: number;
  fight: Uint32Array; // frames that are fight time
  sides: Record<Side, SideIndex>;
}

export interface QualitySummary {
  frames: number;
  measurableShare: number;
  occludedShare: number;
  uncertainMs: number;
  longestUncertainMs: number;
  identityChanges: number;
  /** Largest first; a frame can have several causes. */
  causes: { cause: QualityCause; share: number }[];
}

const UNCERTAIN = 2;
const OCCLUDED = 1;

/** null when the analysis has no quality data (made before identity version 6). */
export function qualityIndex(timeline: TrackingTimeline, segments: readonly ExcludedSegment[] = []): QualityIndex | null {
  const n = timeline.frame_count;
  if (timeline.fighters.some((f) => f.quality === null)) return null;
  const excluded = new Uint8Array(n);
  for (const x of segments) excluded.fill(1, Math.max(0, x.start_frame), Math.min(n, x.end_frame + 1));
  const fight = new Uint32Array(n + 1);
  for (let t = 0; t < n; t++) fight[t + 1] = fight[t]! + (excluded[t] ? 0 : 1);
  const build = (fighterId: string): SideIndex => {
    const f = timeline.fighters.find((x) => x.fighter_id === fighterId);
    const state = new Uint8Array(n).fill(UNCERTAIN);
    for (const r of f?.runs ?? []) {
      state.fill(r.state === "tracked" ? 0 : r.state === "occluded" ? OCCLUDED : UNCERTAIN,
                 r.start_frame, Math.min(n, r.end_frame + 1));
    }
    const unmeasurable = new Uint8Array(n);
    const cause = QUALITY_CAUSES.map(() => new Uint8Array(n));
    for (const r of f?.quality ?? []) {
      const end = Math.min(n, r.end_frame + 1);
      if (!r.measurable) unmeasurable.fill(1, r.start_frame, end);
      for (const c of r.causes) cause[QUALITY_CAUSES.indexOf(c)]?.fill(1, r.start_frame, end);
    }
    const change = new Uint8Array(n);
    for (const t of f?.changes ?? []) if (t >= 0 && t < n) change[t] = 1;
    const sum = (pick: (t: number) => number) => {
      const out = new Uint32Array(n + 1);
      for (let t = 0; t < n; t++) out[t + 1] = out[t]! + (excluded[t] ? 0 : pick(t));
      return out;
    };
    const uncertainRuns: [number, number][] = [];
    let start = -1;
    for (let t = 0; t <= n; t++) {
      const on = t < n && state[t] === UNCERTAIN && !excluded[t];
      if (on && start < 0) start = t;
      if (!on && start >= 0) {
        uncertainRuns.push([start, t - 1]);
        start = -1;
      }
    }
    return {
      measurable: sum((t) => (unmeasurable[t] ? 0 : 1)),
      occluded: sum((t) => (state[t] === OCCLUDED ? 1 : 0)),
      uncertain: sum((t) => (state[t] === UNCERTAIN ? 1 : 0)),
      changes: sum((t) => change[t]!),
      causes: cause.map((c) => sum((t) => c[t]!)),
      uncertainRuns,
    };
  };
  return { frameCount: n, fps: timeline.fps, fight, sides: { red: build("fighter_a"), blue: build("fighter_b") } };
}

const round4 = (v: number) => Math.round(v * 1e4) / 1e4;
const round1 = (v: number) => Math.round(v * 10) / 10;

/** Quality of one side over the frames of the range that are fight time. */
export function qualityIn(index: QualityIndex, side: Side, range: FrameRange): QualitySummary {
  const a = Math.max(0, range.start);
  const b = Math.min(index.frameCount - 1, range.end);
  const s = index.sides[side];
  const count = (sums: Uint32Array) => (b >= a ? sums[b + 1]! - sums[a]! : 0);
  const frames = count(index.fight);
  const share = (sums: Uint32Array) => (frames ? round4(count(sums) / frames) : 0);
  let longest = 0;
  for (const [x, y] of s.uncertainRuns) {
    if (y < a) continue;
    if (x > b) break;
    longest = Math.max(longest, Math.min(y, b) - Math.max(x, a) + 1);
  }
  const causes = QUALITY_CAUSES.map((cause, k) => ({ cause, share: share(s.causes[k]!) }))
    .filter((c) => c.share > 0)
    .sort((p, q) => q.share - p.share); // stable: equal shares keep the cause order
  return {
    frames,
    measurableShare: share(s.measurable),
    occludedShare: share(s.occluded),
    uncertainMs: round1(count(s.uncertain) * 1000 / index.fps),
    longestUncertainMs: round1(longest * 1000 / index.fps),
    identityChanges: count(s.changes),
    causes,
  };
}
