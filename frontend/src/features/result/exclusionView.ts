// What the "Dışlanan bölümler" list shows: the user's parts and the automatic
// ones in one list by time, and how many events each leaves out (pure functions).
import type { AutoExclusion, ExcludedSegment } from "../../contracts/generated";

export interface ExclusionRow {
  key: string;
  kind: "manual" | "auto";
  segment: ExcludedSegment;
  /** Automatic part the user turned off: listed, not applied. */
  dismissed: boolean;
  /** Events whose moment lies in the part. */
  events: number;
  /** Index in the user's list (manual rows). */
  index: number;
}

const inside = (frame: number, x: ExcludedSegment) => x.start_frame <= frame && frame <= x.end_frame;

/** Manual and automatic parts sorted by start; `eventFrames` are the frames the events count from. */
export function exclusionRows(manual: readonly ExcludedSegment[], auto: readonly AutoExclusion[],
                              eventFrames: readonly number[]): ExclusionRow[] {
  const count = (x: ExcludedSegment) => eventFrames.reduce((n, f) => n + (inside(f, x) ? 1 : 0), 0);
  const rows: ExclusionRow[] = [
    ...manual.map((x, index): ExclusionRow => ({
      key: `m-${x.start_frame}-${x.end_frame}`, kind: "manual", segment: x, dismissed: false, events: count(x), index,
    })),
    ...auto.map((x, index): ExclusionRow => ({
      key: `a-${x.auto_id ?? `${x.start_frame}-${x.end_frame}`}`, kind: "auto", segment: x, dismissed: x.dismissed,
      events: count(x), index,
    })),
  ];
  return rows.sort((a, b) => a.segment.start_frame - b.segment.start_frame || a.segment.end_frame - b.segment.end_frame);
}

/** Events left out by the parts in effect; one that lies in both kinds counts as automatic. */
export function excludedEventCounts(rows: readonly ExclusionRow[], eventFrames: readonly number[]):
  { total: number; auto: number; manual: number } {
  const active = rows.filter((r) => !r.dismissed);
  let auto = 0;
  let manual = 0;
  for (const f of eventFrames) {
    if (active.some((r) => r.kind === "auto" && inside(f, r.segment))) auto++;
    else if (active.some((r) => r.kind === "manual" && inside(f, r.segment))) manual++;
  }
  return { total: auto + manual, auto, manual };
}

/** Ids of the automatic parts that are off after switching the part `autoId`. */
export function toggledDismissed(auto: readonly AutoExclusion[], autoId: string): string[] {
  return auto.filter((x) => (x.auto_id === autoId ? !x.dismissed : x.dismissed))
    .map((x) => x.auto_id).filter((id): id is string => id !== null);
}
