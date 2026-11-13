import type { MatchSetup, NameSuggestion, RoundEdits, RoundMark, RoundSegment } from "../../contracts/generated";

/**
 * Round edits on the timeline, as pure functions over the stored user input
 * (`RoundEdits`: the user's marks and the automatic rounds they removed) and
 * the effective rounds the API derives from it (`Job.rounds`). Whatever the
 * user touches becomes a manual mark; manual always wins over automatic.
 */

export const MIN_ROUND_S = 10;

export function editsOf(match: MatchSetup | null | undefined): RoundEdits {
  return { rounds: match?.rounds ?? [], cleared_rounds: match?.cleared_rounds ?? [] };
}

/** Mark round `mark.number` by hand (replaces its automatic round). */
export function withMark(edits: RoundEdits, mark: RoundMark): RoundEdits {
  return {
    rounds: [...edits.rounds.filter((r) => r.number !== mark.number), mark].sort((a, b) => a.number - b.number),
    cleared_rounds: edits.cleared_rounds.filter((n) => n !== mark.number),
  };
}

/** Frames the round may span: between its neighbours, at least MIN_ROUND_S long. */
function limits(rounds: RoundSegment[], index: number, frameCount: number) {
  const sorted = [...rounds].sort((a, b) => a.index - b.index);
  const i = sorted.findIndex((r) => r.index === index);
  return {
    lo: i > 0 ? sorted[i - 1]!.end_frame + 1 : 0,
    hi: i >= 0 && i < sorted.length - 1 ? sorted[i + 1]!.start_frame - 1 : frameCount - 1,
  };
}

/** Move one edge of round `index` to `frame` (clamped); the round becomes a manual mark. */
export function moveEdge(edits: RoundEdits, rounds: RoundSegment[], index: number, edge: "start" | "end",
                         frame: number, fps: number, frameCount: number): RoundEdits {
  const r = rounds.find((x) => x.index === index);
  if (!r) return edits;
  const { lo, hi } = limits(rounds, index, frameCount);
  const min = Math.round(MIN_ROUND_S * fps);
  const f = Math.round(frame);
  const mark = edge === "start"
    ? { number: index, start_frame: Math.min(Math.max(f, lo), r.end_frame - min), end_frame: r.end_frame }
    : { number: index, start_frame: r.start_frame, end_frame: Math.max(Math.min(f, hi), r.start_frame + min) };
  if (mark.start_frame < lo || mark.end_frame > hi || mark.end_frame <= mark.start_frame) return edits;
  return withMark(edits, mark);
}

/** Remove round `index`: its manual mark goes and an automatic one is not used either. */
export function removeRound(edits: RoundEdits, index: number, auto: RoundSegment[]): RoundEdits {
  return {
    rounds: edits.rounds.filter((r) => r.number !== index),
    cleared_rounds: auto.some((a) => a.index === index)
      ? [...new Set([...edits.cleared_rounds, index])].sort((a, b) => a - b)
      : edits.cleared_rounds,
  };
}

/** Back to the automatic round (if there is one): the manual mark and the removal go. */
export function revertToAuto(edits: RoundEdits, index: number): RoundEdits {
  return {
    rounds: edits.rounds.filter((r) => r.number !== index),
    cleared_rounds: edits.cleared_rounds.filter((n) => n !== index),
  };
}

/**
 * A new round at `frame`: the lowest free number, one round length long but not
 * into the next round or past the video. Null when there is no room or no number left.
 */
export function addRound(edits: RoundEdits, rounds: RoundSegment[], frame: number, fps: number, frameCount: number,
                         roundLengthS: number, scheduled: number): RoundEdits | null {
  const used = new Set(rounds.map((r) => r.index));
  let number = 1;
  while (used.has(number)) number += 1;
  if (number > scheduled) return null;
  const start = Math.max(0, Math.round(frame));
  if (rounds.some((r) => start >= r.start_frame && start <= r.end_frame)) return null;
  const before = rounds.filter((r) => r.index < number).every((r) => r.end_frame < start);
  const after = rounds.filter((r) => r.index > number).every((r) => r.start_frame > start);
  if (!before || !after) return null;
  const next = rounds.filter((r) => r.start_frame > start).reduce((m, r) => Math.min(m, r.start_frame), frameCount);
  const end = Math.min(start + Math.round(roundLengthS * fps) - 1, next - 1, frameCount - 1);
  if (end - start < Math.round(MIN_ROUND_S * fps)) return null;
  return withMark(edits, { number, start_frame: start, end_frame: end });
}

export type Side = "red" | "blue";

/**
 * The scorebug name suggestion is applied only where the corner still has its
 * placeholder name: a name the user typed is never overwritten (the scorebug
 * usually shows the surname only).
 */
export function applyNameSuggestion(current: Record<Side, string>, placeholders: Record<Side, string>,
                                    suggestion: NameSuggestion | null | undefined): Record<Side, string> {
  const next = { ...current };
  for (const side of ["red", "blue"] as const) {
    const s = suggestion?.[side];
    const name = current[side].trim();
    if (s && (name === "" || name === placeholders[side])) next[side] = s;
  }
  return next;
}

/** Corners the suggestion would fill (empty: nothing to offer). */
export function suggestionTargets(current: Record<Side, string>, placeholders: Record<Side, string>,
                                  suggestion: NameSuggestion | null | undefined): Side[] {
  const next = applyNameSuggestion(current, placeholders, suggestion);
  return (["red", "blue"] as const).filter((side) => next[side] !== current[side]);
}
