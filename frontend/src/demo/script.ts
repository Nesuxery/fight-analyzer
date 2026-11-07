/**
 * Deterministic DEMO fight script: a synthetic 5-minute round used only for
 * the design preview. Nothing here is measured; every event carries
 * origin "demo" and the UI labels the whole mode as Demo.
 */
import type { EventType } from "../contracts/generated";
import type { PersonId } from "../model/analysis";

export const DEMO_DURATION_S = 300;
export const DEMO_FPS = 30;
export const DEMO_FRAME = { width: 1280, height: 720 } as const;

/** Two fighters and the referee in the synthetic scene. */
export const LEFT: PersonId = "p1";
export const RIGHT: PersonId = "p2";
export const REFEREE: PersonId = "ref";

export type Posture = "stand" | "clinch" | "groundTop" | "groundBottom";

interface Phase {
  from: number;
  to: number;
  left: Posture;
  right: Posture;
}

export const PHASES: readonly Phase[] = [
  { from: 0, to: 120, left: "stand", right: "stand" },
  { from: 120, to: 138.5, left: "clinch", right: "clinch" },
  { from: 138.5, to: 141, left: "stand", right: "clinch" }, // takedown entry
  { from: 141, to: 188, left: "groundBottom", right: "groundTop" },
  { from: 188, to: 233.8, left: "stand", right: "stand" },
  { from: 233.8, to: 237.5, left: "stand", right: "groundBottom" }, // possible knockdown
  { from: 237.5, to: DEMO_DURATION_S, left: "stand", right: "stand" },
];

export interface ScriptEvent {
  id: string;
  type: EventType;
  actor: PersonId | null;
  target: PersonId | null;
  start: number;
  end: number;
  confidence: number;
  significant: boolean;
  note: string | null;
  /** Which limb animates the strike (alternates lead/rear). */
  limb: "lead" | "rear";
}

/** Small seeded PRNG (mulberry32) so the demo is identical on every load. */
function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function phaseAt(t: number): Phase {
  return PHASES.find((p) => t >= p.from && t < p.to) ?? PHASES[PHASES.length - 1]!;
}

/** Positive: left fighter presses forward; negative: right fighter presses. */
export function pressureDriver(t: number): number {
  let bias = 0;
  if (t >= 55 && t < 118) bias = 0.55;
  else if (t >= 192 && t < 222) bias = -0.45;
  else if (t >= 222) bias = 0.5;
  const wobble = 0.45 * Math.sin(t * 0.21 + 1.3) + 0.25 * Math.sin(t * 0.53 + 0.4);
  return Math.max(-1, Math.min(1, bias + wobble));
}

/** Strike rate (per second) for each fighter in standing exchanges. */
function strikeRate(t: number, who: PersonId): number {
  const left = who === LEFT;
  if (t < 55) return 0.16;
  if (t < 118) return left ? 0.42 : 0.2;
  if (t < 222) return left ? 0.22 : 0.34;
  return left ? 0.4 : 0.24;
}

function buildEvents(): ScriptEvent[] {
  const rand = rng(20261011);
  const events: ScriptEvent[] = [];
  let n = 0;
  const add = (e: Omit<ScriptEvent, "id">) => events.push({ ...e, id: `demo-${++n}` });

  for (const actor of [LEFT, RIGHT]) {
    const target = actor === LEFT ? RIGHT : LEFT;
    let t = 2 + rand() * 3;
    let limb: ScriptEvent["limb"] = "lead";
    while (t < DEMO_DURATION_S - 2) {
      const phase = phaseAt(t);
      const posture = actor === LEFT ? phase.left : phase.right;
      const otherPosture = actor === LEFT ? phase.right : phase.left;
      if (posture === "stand" && otherPosture === "stand") {
        const kick = rand() < 0.14;
        const duration = kick ? 0.62 : 0.34;
        add({
          type: kick ? "kick" : "punch",
          actor,
          target,
          start: t,
          end: t + duration,
          confidence: 0.55 + rand() * 0.4,
          significant: false,
          note: null,
          limb: kick ? "rear" : limb,
        });
        limb = limb === "lead" ? "rear" : "lead";
        t += duration + 0.35 + (-Math.log(1 - rand()) / strikeRate(t, actor));
      } else {
        t += 0.5;
      }
    }
  }

  // Knees in the clinch.
  for (const [start, actor] of [
    [123.2, RIGHT], [126.9, LEFT], [129.4, RIGHT], [133.1, RIGHT], [135.8, LEFT],
  ] as const) {
    add({ type: "knee", actor, target: actor === LEFT ? RIGHT : LEFT, start, end: start + 0.45,
          confidence: 0.5 + rand() * 0.3, significant: false, note: null, limb: "rear" });
  }
  add({ type: "clinch", actor: RIGHT, target: LEFT, start: 120, end: 138.5, confidence: 0.81,
        significant: false, note: null, limb: "lead" });
  add({ type: "takedown", actor: RIGHT, target: LEFT, start: 138.5, end: 141, confidence: 0.74,
        significant: false, note: null, limb: "lead" });
  add({ type: "ground_control", actor: RIGHT, target: LEFT, start: 141, end: 188,
        confidence: 0.68, significant: false, note: null, limb: "lead" });
  // Ground strikes from top position.
  for (const start of [146.5, 151.2, 158.8, 163.0, 171.4, 179.9]) {
    add({ type: "punch", actor: RIGHT, target: LEFT, start, end: start + 0.4,
          confidence: 0.45 + rand() * 0.25, significant: false, note: null, limb: "rear" });
  }
  // Possible significant events (amber).
  add({ type: "kick", actor: RIGHT, target: LEFT, start: 77.4, end: 78.0, confidence: 0.62,
        significant: true, note: "Olası yüksek tekme isabeti", limb: "rear" });
  add({ type: "punch", actor: LEFT, target: RIGHT, start: 233.3, end: 233.7, confidence: 0.71,
        significant: true, note: "Olası nakavt (knockdown)", limb: "rear" });

  // Drop standing strikes that overlap the scripted ones above.
  const scripted = events.filter((e) => e.significant || (e.type !== "punch" && e.type !== "kick"));
  const clean = events.filter(
    (e) =>
      scripted.includes(e) ||
      !scripted.some((s) => s.significant && e.actor === s.actor && Math.abs(e.start - s.start) < 1.2),
  );
  return clean.sort((a, b) => a.start - b.start);
}

export const SCRIPT_EVENTS: readonly ScriptEvent[] = buildEvents();
