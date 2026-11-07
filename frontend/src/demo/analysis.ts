/**
 * DEMO statistics derived from the demo script. Shapes match what the real
 * scoring stage will provide, but every value here is synthetic.
 */
import { EMPTY_STATS } from "../model/analysis";
import type { Assignment, PersonId, Side, StatsView, TimelineEvent } from "../model/analysis";
import { DEMO_DURATION_S, LEFT, RIGHT, SCRIPT_EVENTS, phaseAt, pressureDriver } from "./script";

const SECONDS = DEMO_DURATION_S + 1;
const PRESS_THRESHOLD = 0.15;
const MIN_SAMPLE_S = 5;

interface PersonSeries {
  activity: Float32Array; // 0..100 per second
  pressing: Uint8Array; // 1 = pressing forward this second
  advancing: Uint8Array;
  retreating: Uint8Array;
  control: Uint8Array;
}

function seriesFor(who: PersonId): PersonSeries {
  const sign = who === LEFT ? 1 : -1;
  const s: PersonSeries = {
    activity: new Float32Array(SECONDS),
    pressing: new Uint8Array(SECONDS),
    advancing: new Uint8Array(SECONDS),
    retreating: new Uint8Array(SECONDS),
    control: new Uint8Array(SECONDS),
  };
  const strikes = SCRIPT_EVENTS.filter((e) => e.actor === who && ["punch", "kick", "knee"].includes(e.type));
  for (let i = 0; i < SECONDS; i++) {
    const phase = phaseAt(i);
    const standing = phase.left === "stand" && phase.right === "stand";
    const p = pressureDriver(i) * sign;
    if (standing) {
      s.pressing[i] = p > PRESS_THRESHOLD ? 1 : 0;
      s.advancing[i] = p > PRESS_THRESHOLD ? 1 : 0;
      s.retreating[i] = p < -PRESS_THRESHOLD ? 1 : 0;
    }
    const nearby = strikes.filter((e) => Math.abs(e.start - i) <= 2).length;
    const base = standing ? 38 : 26;
    s.activity[i] = Math.min(100, base + nearby * 11 + 6 * Math.sin(i * 0.31 + sign));
    s.control[i] = SCRIPT_EVENTS.some(
      (e) => e.type === "ground_control" && e.actor === who && i >= e.start && i < e.end,
    ) ? 1 : 0;
  }
  return s;
}

const SERIES: Record<PersonId, PersonSeries> = { [LEFT]: seriesFor(LEFT), [RIGHT]: seriesFor(RIGHT) };

// Experimental momentum: decaying points per fighter, shown as a share.
const HALF_LIFE_S = 20;
const PRIOR = 4;
const WEIGHTS: Record<string, number> = { punch: 1, knee: 1.1, kick: 1.3, takedown: 3, clinch: 0 };

/** Left fighter's momentum share (0..1) for every second. */
const LEFT_MOMENTUM: Float32Array = (() => {
  const out = new Float32Array(SECONDS);
  const decay = Math.pow(0.5, 1 / HALF_LIFE_S);
  let mL = 0;
  let mR = 0;
  for (let i = 0; i < SECONDS; i++) {
    mL *= decay;
    mR *= decay;
    for (const e of SCRIPT_EVENTS) {
      if (e.start >= i - 1 && e.start < i) {
        const w = (WEIGHTS[e.type] ?? 0) + (e.significant ? 8 : 0);
        if (e.actor === LEFT) mL += w;
        else if (e.actor === RIGHT) mR += w;
      }
    }
    mL += 0.5 * SERIES[LEFT]!.pressing[i]! + 0.8 * SERIES[LEFT]!.control[i]!;
    mR += 0.5 * SERIES[RIGHT]!.pressing[i]! + 0.8 * SERIES[RIGHT]!.control[i]!;
    out[i] = (mL + PRIOR) / (mL + mR + 2 * PRIOR);
  }
  return out;
})();

export function sideOf(person: PersonId | null, assignment: Assignment): Side | null {
  if (person === null) return null;
  if (assignment.red === person) return "red";
  if (assignment.blue === person) return "blue";
  return null;
}

export function demoEvents(assignment: Assignment): TimelineEvent[] {
  return SCRIPT_EVENTS.map((e) => ({
    id: e.id,
    type: e.type,
    side: sideOf(e.actor, assignment),
    startS: e.start,
    endS: e.end,
    confidence: e.confidence,
    significant: e.significant,
    note: e.note,
    origin: "demo" as const,
  }));
}

/** Red side's momentum share at time t (0..1). */
export function demoMomentum(t: number, assignment: Assignment): number {
  const i = Math.min(SECONDS - 1, Math.max(0, Math.floor(t)));
  const left = LEFT_MOMENTUM[i]!;
  return assignment.red === RIGHT ? 1 - left : left;
}

/** Downsampled red share for the timeline sparkline. */
export function demoMomentumSeries(assignment: Assignment, points = 150): number[] {
  return Array.from({ length: points }, (_, k) => demoMomentum((k / (points - 1)) * DEMO_DURATION_S, assignment));
}

export function demoStats(person: PersonId | null, t: number): StatsView {
  const series = person ? SERIES[person] : undefined;
  if (!person || !series) return EMPTY_STATS;
  const upto = Math.min(SECONDS, Math.max(1, Math.floor(t) + 1));
  const mine = SCRIPT_EVENTS.filter((e) => e.actor === person && e.start <= t);
  let activity = 0;
  let pressing = 0;
  let adv = 0;
  let ret = 0;
  let control = 0;
  let standingSeconds = 0;
  for (let i = 0; i < upto; i++) {
    activity += series.activity[i]!;
    pressing += series.pressing[i]!;
    adv += series.advancing[i]!;
    ret += series.retreating[i]!;
    control += series.control[i]!;
    const phase = phaseAt(i);
    if (phase.left === "stand" && phase.right === "stand") standingSeconds++;
  }
  const moving = adv + ret;
  // Shares from a handful of seconds are noise; show "—" until enough samples.
  const share = (part: number, whole: number) =>
    whole >= MIN_SAMPLE_S ? Math.round((part / whole) * 100) : null;
  return {
    strikeAttempts: mine.filter((e) => e.type === "punch" || e.type === "knee").length,
    kicks: mine.filter((e) => e.type === "kick").length,
    activity: upto >= MIN_SAMPLE_S ? Math.round(activity / upto) : null,
    pressure: share(pressing, standingSeconds),
    advance: share(adv, moving),
    retreat: share(ret, moving),
    controlS: Math.min(control, t),
    significant: mine.filter((e) => e.significant).length,
  };
}
