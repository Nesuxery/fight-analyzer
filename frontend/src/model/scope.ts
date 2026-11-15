/**
 * Time scope of a group of metrics (v2 Bölüm 2.5): every group knows and shows which
 * stretch of the bout its numbers belong to.
 *
 * - "playhead": from the start of the video up to the presented frame (what the
 *   panels always showed, and what the MP4 export burns in);
 * - "round": one round in effect (Job.rounds);
 * - "bout": the whole video.
 *
 * Excluded parts are not fight time in any scope: the metric functions leave them out
 * themselves. `scopeRange` is the one place that turns a scope into frames; the
 * statistics (model/measured.ts) and the data quality (model/quality.ts) take that range.
 */

export type Scope = { kind: "playhead" } | { kind: "bout" } | { kind: "round"; index: number };
export type ScopeKind = Scope["kind"];

/** Frames [start, end], both inclusive. */
export interface FrameRange {
  start: number;
  end: number;
}

export interface RoundSpan {
  index: number;
  start_frame: number;
  end_frame: number;
}

/** The frames a scope covers; null when it has none (no such round, empty video). */
export function scopeRange(scope: Scope, rounds: readonly RoundSpan[], frame: number,
                           frameCount: number): FrameRange | null {
  const last = frameCount - 1;
  if (last < 0) return null;
  if (scope.kind === "bout") return { start: 0, end: last };
  if (scope.kind === "playhead") return { start: 0, end: Math.min(Math.max(frame, 0), last) };
  const round = rounds.find((r) => r.index === scope.index);
  if (!round) return null;
  const start = Math.max(0, round.start_frame);
  const end = Math.min(last, round.end_frame);
  return end >= start ? { start, end } : null;
}

/** Number of the round the frame lies in, else of the last round that started before it,
 * else of the first round; null without rounds. The round a "Raunt" scope starts with. */
export function roundNear(rounds: readonly RoundSpan[], frame: number): number | null {
  if (rounds.length === 0) return null;
  const ordered = [...rounds].sort((a, b) => a.start_frame - b.start_frame);
  let pick = ordered[0]!;
  for (const r of ordered) if (r.start_frame <= frame) pick = r;
  return pick.index;
}

/** A scope that still exists for these rounds (a removed round falls back to the playhead). */
export function validScope(scope: Scope, rounds: readonly RoundSpan[]): Scope {
  return scope.kind === "round" && !rounds.some((r) => r.index === scope.index) ? { kind: "playhead" } : scope;
}
