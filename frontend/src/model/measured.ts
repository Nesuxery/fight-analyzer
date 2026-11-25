/**
 * Measured analysis results (events, motion signals, experimental momentum)
 * turned into what the result screen shows at a playback time.
 *
 * The momentum math mirrors backend/fight_analyzer/motion/momentum.py exactly:
 * every ledger entry decays with the half-life (time-based entries are
 * integrated), and red share = 100 x (m_red + prior) / (m_red + m_blue + 2 x prior).
 * Because the same ledger is used, the share at any moment can be split into
 * its sources and the effect of one event can be shown precisely.
 *
 * Statistics refer to the presented frame: t = frame * 1000 / fps ms, and an
 * event counts from its peak frame on. backend/fight_analyzer/export/frames.py
 * mirrors these functions operation by operation, so the exported MP4 and CSV
 * show the same numbers; both are checked against shared/fixtures/frame-metrics.json.
 *
 * Excluded parts (replays etc., marked by the user; backend motion/exclusions.py)
 * are not fight time: their events are listed but not counted, their samples are
 * not measurements, and the momentum decays on fight time, so it holds its value
 * through them. The ledger from the API already leaves their points out.
 */
import type {
  DamageSignal,
  ExcludedSegment,
  FightEvent,
  MomentumContribution,
  MomentumParameters,
  MomentumSource,
  MotionTimeline,
  TrackingTimeline,
  TrackState,
} from "../contracts/generated";
import type { DamageView, EventTag, Side, StatsView, TimelineEvent } from "./analysis";

export const SOURCE_LABELS: Record<MomentumSource, string> = {
  strike_attempt: "Vuruş denemesi (yumruk, diz, dirsek, yerde vuruş)",
  kick_attempt: "Tekme denemesi",
  contact_bonus: "Olası temas eki",
  advance: "İlerleme süresi",
  control: "Tahmini yer kontrolü",
  knockdown: "Olası knockdown",
  takedown: "Olası takedown",
};

export const SOURCE_ORDER: MomentumSource[] = [
  "strike_attempt", "kick_attempt", "contact_bonus", "advance", "control", "knockdown", "takedown",
];

const LN2 = Math.log(2);
const MIN_SHARE_SAMPLES_S = 3; // shares from fewer measured seconds are noise -> "—"

export const sideOfFighter = (id: string | null | undefined): Side | null =>
  id === "fighter_a" ? "red" : id === "fighter_b" ? "blue" : null;

/** Excluded parts as [start, end) in ms of video time, sorted. */
export type Intervals = [number, number][];

export function exclusionIntervals(segments: readonly ExcludedSegment[], fps: number): Intervals {
  return segments.map((x) => [x.start_frame * 1000 / fps, (x.end_frame + 1) * 1000 / fps]);
}

export const isFrameExcluded = (frame: number, segments: readonly ExcludedSegment[]): boolean =>
  segments.some((x) => x.start_frame <= frame && frame <= x.end_frame);

/** Video time -> fight time (excluded time before t removed). */
export function fightMs(tMs: number, iv: Intervals): number {
  let total = 0;
  for (const [a, b] of iv) {
    if (tMs <= a) break;
    total += Math.min(tMs, b) - a;
  }
  return tMs - total;
}

/** Length of [a, b] outside the excluded parts (0 when b <= a). */
export function outsideMs(a: number, b: number, iv: Intervals): number {
  if (b <= a) return 0;
  let length = b - a;
  for (const [x, y] of iv) {
    const lo = Math.max(a, x);
    const hi = Math.min(b, y);
    if (hi > lo) length -= hi - lo;
  }
  return length;
}

const inIntervals = (tMs: number, iv: Intervals) => iv.some(([a, b]) => a <= tMs && tMs < b);

/** Value of one ledger entry at time tMs (0 before it starts), on fight time. */
export function decayed(c: MomentumContribution, tMs: number, halfLifeS: number, iv: Intervals = []): number {
  const t = fightMs(tMs, iv) / 1000;
  const start = fightMs(c.start_ms, iv) / 1000;
  const end = fightMs(c.end_ms, iv) / 1000;
  if (t < start) return 0;
  const lam = LN2 / halfLifeS;
  if (end <= start) return c.points * Math.exp(-lam * (t - start));
  const rate = c.points / (end - start);
  const upto = Math.min(Math.max(t, start), end);
  return (rate / lam) * (Math.exp(-lam * (t - upto)) - Math.exp(-lam * (t - start)));
}

export function totals(contribs: MomentumContribution[], tMs: number, p: MomentumParameters,
                       iv: Intervals = []): Record<Side, number> {
  const m = { red: 0, blue: 0 };
  for (const c of contribs) m[sideOfFighter(c.fighter_id)!] += decayed(c, tMs, p.half_life_s, iv);
  return m;
}

/** Red corner share in percent (blue = 100 - red). */
export function redShare(m: Record<Side, number>, prior: number): number {
  return (100 * (m.red + prior)) / (m.red + m.blue + 2 * prior);
}

/** Displayed red share: whole percent (Math.round; the export rounds the same way). */
export const shownShare = (redSharePct: number): number => Math.round(redSharePct);

/** Media time of a frame in ms, the time all statistics refer to. */
export const frameMs = (frame: number, fps: number): number => frame * 1000 / fps;

/** Frame from which an event counts (its peak; the start when it has none). */
export const eventFrame = (e: FightEvent): number => e.peak_frame ?? e.start_frame;

export interface SourceValue { source: MomentumSource; value: number; earned: number }

/** Current (decayed) value and total earned points per source, for each side. */
export function breakdown(contribs: MomentumContribution[], tMs: number, p: MomentumParameters,
                          iv: Intervals = []): Record<Side, SourceValue[]> {
  const out: Record<Side, Map<MomentumSource, SourceValue>> = { red: new Map(), blue: new Map() };
  for (const c of contribs) {
    if (c.start_ms > tMs) continue;
    const side = sideOfFighter(c.fighter_id)!;
    const entry = out[side].get(c.source) ?? { source: c.source, value: 0, earned: 0 };
    entry.value += decayed(c, tMs, p.half_life_s, iv);
    entry.earned += c.end_ms > c.start_ms
      ? c.points * Math.min(1, (Math.min(tMs, c.end_ms) - c.start_ms) / (c.end_ms - c.start_ms))
      : c.points;
    out[side].set(c.source, entry);
  }
  const order = (m: Map<MomentumSource, SourceValue>) =>
    SOURCE_ORDER.filter((s) => m.has(s)).map((s) => m.get(s)!);
  return { red: order(out.red), blue: order(out.blue) };
}

export interface EventEffect {
  side: Side;
  entries: MomentumContribution[];
  points: number; // earned, before decay
  now: number; // decayed value at t
  /** Change of the red share caused by this event, in percentage points. */
  redDelta: number;
}

/** What one event contributes to the momentum at time t (null if it earns nothing). */
export function eventEffect(contribs: MomentumContribution[], eventId: string, tMs: number,
                            p: MomentumParameters, iv: Intervals = []): EventEffect | null {
  const entries = contribs.filter((c) => c.event_id === eventId);
  if (entries.length === 0) return null;
  const side = sideOfFighter(entries[0]!.fighter_id)!;
  const m = totals(contribs, tMs, p, iv);
  const now = entries.reduce((sum, c) => sum + decayed(c, tMs, p.half_life_s, iv), 0);
  const without = { ...m, [side]: m[side] - now };
  return {
    side, entries, now,
    points: entries.reduce((sum, c) => sum + c.points, 0),
    redDelta: redShare(m, p.prior) - redShare(without, p.prior),
  };
}

/** Index of the sample covering time t (grid starting at 0 ms). */
export function sampleAt(sampleMs: number[], tMs: number): number {
  let lo = 0;
  let hi = sampleMs.length - 1;
  if (hi < 0) return -1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (sampleMs[mid]! <= tMs) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}

const MAJOR = new Set(["knockdown", "takedown"]);
/** Counted as "Vuruş denemeleri" (kicks are counted apart); the export counts the same (frames.py). */
export const HAND_STRIKES: ReadonlySet<string> = new Set(["punch", "knee", "elbow", "ground_strike"]);

/** Seen only by inferring the opponent's identity and below the attribution threshold: listed with
 * its tag, kept out of the counts (the export does the same, frames.py). */
export const inferredOnly = (e: FightEvent): boolean =>
  e.attribution_uncertain && (e.evidence ?? []).includes("identity_inferred");

/** When an event happens (its peak; the end for time-based ones such as control). */
export function eventMoment(e: FightEvent): number {
  return e.type === "ground_control" || e.type === "clinch" ? e.end_ms : (e.peak_ms ?? e.start_ms);
}

/** Detector confidence below this is labelled "Düşük güven". */
export const LOW_CONFIDENCE = 0.6;

/** Identity state of a fighter at a frame from the tracking timeline (null = unknown). */
export function identityAt(timeline: TrackingTimeline | null, fighterId: string, frame: number): TrackState | null {
  const runs = timeline?.fighters.find((f) => f.fighter_id === fighterId)?.runs ?? [];
  let lo = 0;
  let hi = runs.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const r = runs[mid]!;
    if (frame < r.start_frame) hi = mid - 1;
    else if (frame > r.end_frame) lo = mid + 1;
    else return r.state;
  }
  return null;
}

/** Uncertainty labels of an event: what it is not certain about, in plain words. */
export function eventTags(e: FightEvent, scored: Set<string> | null, timeline: TrackingTimeline | null,
                          segments: readonly ExcludedSegment[] = [],
                          unattributed?: (confidencePct: number) => EventTag): EventTag[] {
  const tags: EventTag[] = [];
  if (isFrameExcluded(eventFrame(e), segments)) {
    tags.push({ label: "Dışlandı", tone: "muted",
                title: "Dışlanan bölümde (ör. tekrar): sayılmaz ve momentuma puan eklemez." });
    return tags;
  }
  if (MAJOR.has(e.type)) {
    tags.push({ label: "Olası", tone: "amber",
                title: "Duruş ve konum değişiminden çıkarılan olası olay; doğrulanmış değildir." });
  }
  if (e.possible_contact) {
    tags.push({ label: "Olası temas", tone: "amber",
                title: "Vuran uzuv rakiple 2B görüntüde örtüştü; temasın gerçekleştiği kesin değildir." });
  }
  if (e.confidence < LOW_CONFIDENCE) {
    tags.push({ label: "Düşük güven", tone: "muted",
                title: `Dedektör güveni %${Math.round(e.confidence * 100)}; yanlış tespit olabilir.` });
  }
  // "Kime ait belirsiz": the text comes from the caller (labels.ts)
  // an inferred-only event carries its own tag ("Kimlik çıkarımı", EventList) instead
  if (e.attribution_uncertain && unattributed && !inferredOnly(e)) {
    tags.push(unattributed(Math.round((e.attribution_confidence ?? 0) * 100)));
  }
  if (e.actor && identityAt(timeline, e.actor, eventFrame(e)) === "occluded") {
    tags.push({ label: "Kimlik örtüşmede", tone: "muted",
                title: "Olay anında dövüşçüler üst üsteydi; kimlik önceki karelerden taşındı." });
  }
  if (scored && !scored.has(e.event_id)) {
    tags.push({ label: "Puan yok", tone: "muted",
                title: "Bu olay momentuma puan eklemiyor (puanlanmayan tür ya da eşik altı güven)." });
  }
  return tags;
}

export function toTimelineEvents(events: FightEvent[], contributions: MomentumContribution[] | null = null,
                                 timeline: TrackingTimeline | null = null,
                                 segments: readonly ExcludedSegment[] = [],
                                 unattributed?: (confidencePct: number) => EventTag): TimelineEvent[] {
  const scored = contributions ? new Set(contributions.map((c) => c.event_id).filter((id) => id !== null)) : null;
  return [...events].sort((a, b) => (a.peak_ms ?? a.start_ms) - (b.peak_ms ?? b.start_ms)).map((e) => ({
    id: e.event_id,
    type: e.type,
    side: sideOfFighter(e.actor),
    startS: (e.peak_ms ?? e.start_ms) / 1000,
    endS: e.end_ms / 1000,
    confidence: e.confidence,
    significant: MAJOR.has(e.type),
    note: e.note ?? null,
    origin: e.data_origin,
    tags: eventTags(e, scored, timeline, segments, unattributed),
    excluded: isFrameExcluded(eventFrame(e), segments),
    outcome: e.outcome ?? null,
    zone: e.target_zone ?? null,
    significantStrike: e.significant ?? null,
    inferred: inferredOnly(e),
  }));
}

/** Damage signals as list rows, in time order (signals in excluded parts are marked, not dropped). */
export function toDamageViews(signals: readonly DamageSignal[], segments: readonly ExcludedSegment[] = []): DamageView[] {
  return [...signals].sort((a, b) => a.time_ms - b.time_ms).map((d) => ({
    id: d.signal_id,
    type: d.type,
    kind: d.kind,
    side: sideOfFighter(d.by_fighter)!,
    target: sideOfFighter(d.target_fighter)!,
    startS: d.time_ms / 1000,
    endS: d.end_ms === null ? null : d.end_ms / 1000,
    severity: d.severity,
    confidence: d.confidence,
    inferred: d.evidence.includes("identity_inferred"),
    uncertain: d.attribution_uncertain,
    excluded: isFrameExcluded(d.frame, segments),
    note: d.note,
  }));
}

/** Prefix sums over the motion samples, so stats up to any time are O(1). */
export interface MotionSums {
  hz: number;
  count: number;
  act: Record<Side, Float64Array>; // sum of activity
  actN: Record<Side, Uint32Array>; // samples with activity
  adv: Record<Side, Uint32Array>;
  ret: Record<Side, Uint32Array>;
  moveN: Record<Side, Uint32Array>; // samples with a movement state (both standing, measured)
  valid: Record<Side, Uint32Array>;
}

/** Samples inside excluded parts count as not measured. */
export function motionSums(motion: MotionTimeline, iv: Intervals = []): MotionSums {
  const n = motion.sample_ms.length;
  const skip = motion.sample_ms.map((t) => inIntervals(t, iv));
  const make = () => ({ red: new Uint32Array(n + 1), blue: new Uint32Array(n + 1) });
  const sums: MotionSums = {
    hz: motion.sample_hz, count: n,
    act: { red: new Float64Array(n + 1), blue: new Float64Array(n + 1) },
    actN: make(), adv: make(), ret: make(), moveN: make(), valid: make(),
  };
  motion.fighters.forEach((f) => {
    const side = sideOfFighter(f.fighter_id)!;
    for (let i = 0; i < n; i++) {
      const a = skip[i] ? null : f.activity[i];
      const mv = skip[i] ? null : f.movement[i];
      const ok = skip[i] ? false : f.valid[i];
      sums.act[side][i + 1] = sums.act[side][i]! + (a ?? 0);
      sums.actN[side][i + 1] = sums.actN[side][i]! + (a === null || a === undefined ? 0 : 1);
      sums.adv[side][i + 1] = sums.adv[side][i]! + (mv === "advancing" ? 1 : 0);
      sums.ret[side][i + 1] = sums.ret[side][i]! + (mv === "retreating" ? 1 : 0);
      sums.moveN[side][i + 1] = sums.moveN[side][i]! + (mv ? 1 : 0);
      sums.valid[side][i + 1] = sums.valid[side][i]! + (ok ? 1 : 0);
    }
  });
  return sums;
}

const samplesUpTo = (tMs: number, sums: MotionSums): number =>
  Math.min(sums.count, Math.max(0, Math.floor(tMs / 1000 * sums.hz) + 1));

/** Samples that lie before time tMs (those a range starting there leaves out). */
const samplesBefore = (tMs: number, sums: MotionSums): number =>
  Math.min(sums.count, Math.max(0, Math.ceil(tMs / 1000 * sums.hz - 1e-9)));

/** Statistics of one side up to the presented frame (tMs = frameMs(frame)), from the start
 * of the video or, for a round scope, from `fromFrame` (see model/scope.ts).
 * Events in excluded parts are not counted and control time does not accrue in them.
 * The MP4 export mirrors the default (from the start). */
export function measuredStats(side: Side, frame: number, tMs: number, events: FightEvent[],
                              sums: MotionSums, segments: readonly ExcludedSegment[] = [],
                              iv: Intervals = [], fromFrame = 0, fromMs = 0): StatsView {
  const fighter = side === "red" ? "fighter_a" : "fighter_b";
  const upto = samplesUpTo(tMs, sums);
  const from = fromFrame > 0 ? Math.min(upto, samplesBefore(fromMs, sums)) : 0;
  const mine = events.filter((e) => e.actor === fighter && eventFrame(e) <= frame && eventFrame(e) >= fromFrame &&
    !isFrameExcluded(eventFrame(e), segments) && !inferredOnly(e));
  const enough = (samples: number) => samples / sums.hz >= MIN_SHARE_SAMPLES_S;
  const actN = sums.actN[side][upto]! - sums.actN[side][from]!;
  const moveN = sums.moveN[side][upto]! - sums.moveN[side][from]!;
  const adv = sums.adv[side][upto]! - sums.adv[side][from]!;
  const ret = sums.ret[side][upto]! - sums.ret[side][from]!;
  const moving = adv + ret;
  let control = 0;
  for (const e of events) {  // a control stretch that began before the range counts for its part inside
    if (e.type !== "ground_control" || e.actor !== fighter || isFrameExcluded(eventFrame(e), segments)) continue;
    if (eventFrame(e) > frame) continue;
    control += outsideMs(Math.max(e.start_ms, fromMs), Math.min(e.end_ms, tMs), iv) / 1000;
  }
  return {
    strikeAttempts: mine.filter((e) => HAND_STRIKES.has(e.type)).length,
    kicks: mine.filter((e) => e.type === "kick").length,
    activity: enough(actN) ? Math.round(((sums.act[side][upto]! - sums.act[side][from]!) / actN) * 100) : null,
    pressure: enough(moveN) ? Math.round((adv / moveN) * 100) : null,
    advance: enough(moveN) && moving > 0 ? Math.round((adv / moving) * 100) : enough(moveN) ? 0 : null,
    retreat: enough(moveN) && moving > 0 ? Math.round((ret / moving) * 100) : enough(moveN) ? 0 : null,
    controlS: Math.round(control),
    significant: mine.filter((e) => MAJOR.has(e.type)).length,
  };
}

/** Seconds of valid measurement of one side up to tMs. */
export function measuredSeconds(side: Side, tMs: number, sums: MotionSums): number {
  return sums.valid[side][samplesUpTo(tMs, sums)]! / sums.hz;
}
