/**
 * Procedural DEMO scene: COCO-17 poses for two synthetic fighters and a
 * referee at any time t, driven by the demo script. Used to preview the
 * skeleton / strike / distance layers without a real video.
 */
import type { Detection, PersonId } from "../model/analysis";
import {
  DEMO_DURATION_S,
  DEMO_FRAME,
  LEFT,
  PHASES,
  REFEREE,
  RIGHT,
  SCRIPT_EVENTS,
  type Posture,
  type ScriptEvent,
  pressureDriver,
} from "./script";

export type Point = [number, number];
/** 17 keypoints in COCO order (frame pixels). */
export type Pose = Point[];

// Templates in body-height units, origin between the feet, facing +x (right),
// y negative upwards. Order: nose, eyes(l,r), ears(l,r), shoulders, elbows,
// wrists, hips, knees, ankles (left/right pairs). Left side leads (orthodox).
type Template = readonly (readonly [number, number])[];

const STAND: Template = [
  [0.1, -0.93], [0.11, -0.95], [0.08, -0.95], [0.03, -0.94], [0.0, -0.94],
  [0.06, -0.8], [-0.04, -0.79], [0.16, -0.7], [0.06, -0.68], [0.2, -0.84], [0.13, -0.86],
  [0.03, -0.5], [-0.05, -0.5], [0.13, -0.27], [-0.1, -0.26], [0.17, 0], [-0.17, 0],
];

const CLINCH: Template = [
  [0.2, -0.86], [0.21, -0.88], [0.18, -0.88], [0.13, -0.88], [0.1, -0.87],
  [0.13, -0.75], [0.03, -0.74], [0.25, -0.76], [0.18, -0.7], [0.34, -0.82], [0.3, -0.8],
  [0.02, -0.48], [-0.06, -0.48], [0.12, -0.26], [-0.12, -0.25], [0.15, 0], [-0.2, 0],
];

const GROUND_TOP: Template = [
  [0.36, -0.6], [0.37, -0.62], [0.34, -0.62], [0.3, -0.62], [0.28, -0.61],
  [0.24, -0.52], [0.16, -0.5], [0.34, -0.36], [0.28, -0.33], [0.42, -0.2], [0.36, -0.18],
  [-0.02, -0.36], [-0.08, -0.35], [0.12, -0.05], [0.02, -0.04], [-0.22, -0.02], [-0.28, -0.02],
];

const GROUND_BOTTOM: Template = [
  [0.5, -0.12], [0.51, -0.15], [0.49, -0.15], [0.47, -0.11], [0.46, -0.11],
  [0.34, -0.1], [0.32, -0.08], [0.42, -0.26], [0.36, -0.24], [0.5, -0.36], [0.44, -0.34],
  [0.0, -0.08], [-0.02, -0.07], [-0.2, -0.3], [-0.24, -0.27], [-0.42, -0.06], [-0.46, -0.05],
];

const REF_STAND: Template = [
  [0.04, -0.94], [0.05, -0.96], [0.02, -0.96], [0.0, -0.95], [-0.03, -0.95],
  [0.04, -0.8], [-0.05, -0.8], [0.07, -0.63], [-0.07, -0.63], [0.08, -0.48], [-0.08, -0.48],
  [0.03, -0.5], [-0.04, -0.5], [0.04, -0.26], [-0.05, -0.26], [0.06, 0], [-0.07, 0],
];

const TEMPLATES: Record<Posture, Template> = {
  stand: STAND,
  clinch: CLINCH,
  groundTop: GROUND_TOP,
  groundBottom: GROUND_BOTTOM,
};

// Limb overrides (index -> point) blended in while a strike is active.
const STRIKES: Record<string, Record<number, readonly [number, number]>> = {
  "punch:lead": { 5: [0.1, -0.8], 7: [0.32, -0.8], 9: [0.5, -0.84] },
  "punch:rear": { 6: [0.06, -0.8], 8: [0.26, -0.8], 10: [0.46, -0.83] },
  "kick:rear": { 12: [0.0, -0.52], 14: [0.24, -0.52], 16: [0.48, -0.66] },
  "kick:lead": { 11: [0.06, -0.52], 13: [0.28, -0.5], 15: [0.5, -0.6] },
  "knee:rear": { 14: [0.22, -0.46], 16: [0.06, -0.3] },
  "knee:lead": { 13: [0.24, -0.46], 15: [0.08, -0.3] },
  "ground:rear": { 8: [0.4, -0.44], 10: [0.5, -0.12] },
  "ground:lead": { 7: [0.42, -0.42], 9: [0.52, -0.1] },
};

/** Index of the striking end-effector for impact effects. */
const STRIKE_TIP: Record<string, number> = {
  "punch:lead": 9, "punch:rear": 10, "kick:rear": 16, "kick:lead": 15,
  "knee:rear": 14, "knee:lead": 13, "ground:rear": 10, "ground:lead": 9,
};

const BODY_PX = 330; // body height of the fighters in frame pixels
const FLOOR_Y = 640;

function smoothstep(x: number) {
  const c = Math.min(1, Math.max(0, x));
  return c * c * (3 - 2 * c);
}

/** Posture weights with a short cross-fade around phase boundaries. */
function postureMix(t: number, who: "left" | "right"): [Posture, number][] {
  const fade = 0.6;
  const idx = PHASES.findIndex((p) => t >= p.from && t < p.to);
  const phase = PHASES[idx === -1 ? PHASES.length - 1 : idx]!;
  const prev = PHASES[idx - 1];
  const current = phase[who];
  if (prev && prev[who] !== current && t - phase.from < fade) {
    const w = smoothstep((t - phase.from) / fade);
    return [[prev[who], 1 - w], [current, w]];
  }
  return [[current, 1]];
}

// Fighter centre line: integrate the pressure driver at 10 Hz, softly pulled
// back to the middle of the frame.
const CENTER_HZ = 10;
const CENTER: Float32Array = (() => {
  const n = DEMO_DURATION_S * CENTER_HZ + 1;
  const out = new Float32Array(n);
  let c = DEMO_FRAME.width / 2;
  for (let i = 0; i < n; i++) {
    const t = i / CENTER_HZ;
    c += (pressureDriver(t) * 55 - (c - DEMO_FRAME.width / 2) * 0.12) / CENTER_HZ;
    out[i] = c;
  }
  return out;
})();

function centerAt(t: number): number {
  const x = Math.min(Math.max(t, 0), DEMO_DURATION_S) * CENTER_HZ;
  const i = Math.floor(x);
  const a = CENTER[i] ?? CENTER[CENTER.length - 1]!;
  const b = CENTER[i + 1] ?? a;
  return a + (b - a) * (x - i);
}

/** Gap between the fighters' feet centres in body heights. */
function gapAt(t: number, left: Posture, right: Posture): number {
  if (left === "groundBottom" && right === "groundTop") return 0.6;
  if (right === "groundBottom") return 1.05;
  if (left === "clinch" || right === "clinch") return 0.42;
  return 0.95 + 0.22 * Math.sin(t * 0.9 + 0.3 * Math.sin(t * 0.37)) - 0.12 * Math.abs(pressureDriver(t));
}

export interface ActiveStrike {
  event: ScriptEvent;
  /** 0..1 progress through the strike. */
  progress: number;
  /** Impact point in frame pixels. */
  tip: Point;
}

export interface SceneState {
  t: number;
  poses: Record<PersonId, Pose>;
  strikes: ActiveStrike[];
}

function build(template: Template, overrides: Record<number, readonly [number, number]>[],
               weights: number[]): [number, number][] {
  return template.map(([x, y], i) => {
    let px = x;
    let py = y;
    overrides.forEach((o, k) => {
      const p = o[i];
      if (p) {
        px += (p[0] - px) * weights[k]!;
        py += (p[1] - py) * weights[k]!;
      }
    });
    return [px, py];
  });
}

function fighterPose(t: number, who: PersonId, active: ScriptEvent[]): {
  pose: Pose;
  strikes: ActiveStrike[];
} {
  const side = who === LEFT ? "left" : "right";
  const mix = postureMix(t, side);
  const phaseNow = mix[mix.length - 1]![0];
  const otherNow = postureMix(t, side === "left" ? "right" : "left").at(-1)![0];
  const facing = who === LEFT ? 1 : -1;
  const center = centerAt(t);
  const gap = gapAt(t, side === "left" ? phaseNow : otherNow, side === "right" ? phaseNow : otherNow);
  const rootX = center - (facing * gap * BODY_PX) / 2;
  const bounce = phaseNow === "stand" ? Math.sin(t * 2 * Math.PI * 1.5 + (who === LEFT ? 0 : 1.7)) * 0.01 : 0;

  // Strike overrides for this fighter.
  const mine = active.filter((e) => e.actor === who && e.type !== "clinch" &&
    e.type !== "takedown" && e.type !== "ground_control");
  const overrides: Record<number, readonly [number, number]>[] = [];
  const weights: number[] = [];
  const keys: string[] = [];
  for (const e of mine) {
    const p = (t - e.start) / (e.end - e.start);
    const kind = phaseNow === "groundTop" ? "ground" : e.type === "punch" ? "punch" : e.type;
    const key = `${kind}:${e.limb}`;
    const o = STRIKES[key];
    if (!o) continue;
    overrides.push(o);
    weights.push(Math.pow(Math.sin(Math.PI * p), 1.2));
    keys.push(key);
  }

  // Blend posture templates, then apply strike overrides.
  const blended: [number, number][] = TEMPLATES.stand.map(() => [0, 0]);
  for (const [posture, w] of mix) {
    build(TEMPLATES[posture], overrides, weights).forEach(([x, y], i) => {
      blended[i]![0] += x * w;
      blended[i]![1] += y * w;
    });
  }
  const pose: Pose = blended.map(([x, y]) => [rootX + facing * x * BODY_PX,
                                              FLOOR_Y + (y + bounce) * BODY_PX]);
  const strikes: ActiveStrike[] = mine.flatMap((event, k) => {
    const tipIndex = STRIKE_TIP[keys[k] ?? ""];
    if (tipIndex === undefined) return [];
    return [{ event, progress: (t - event.start) / (event.end - event.start), tip: pose[tipIndex]! }];
  });
  return { pose, strikes };
}

function refereePose(t: number): Pose {
  const x = DEMO_FRAME.width / 2 + 380 * Math.sin(t / 29 + 1.1);
  const facing = x > centerAt(t) ? -1 : 1;
  const scale = BODY_PX * 0.8;
  return REF_STAND.map(([px, py]) => [x + facing * px * scale, 585 + py * scale]);
}

let cache: SceneState | null = null;

export function sceneAt(t: number): SceneState {
  if (cache && cache.t === t) return cache;
  const active = SCRIPT_EVENTS.filter((e) => t >= e.start && t <= e.end);
  const left = fighterPose(t, LEFT, active);
  const right = fighterPose(t, RIGHT, active);
  cache = {
    t,
    poses: { [LEFT]: left.pose, [RIGHT]: right.pose, [REFEREE]: refereePose(t) },
    strikes: [...left.strikes, ...right.strikes],
  };
  return cache;
}

/** Person boxes as a pose detector would report them (demo confidences). */
export function detectionsAt(t: number): Detection[] {
  const { poses } = sceneAt(t);
  const conf: Record<PersonId, number> = { [LEFT]: 0.93, [RIGHT]: 0.91, [REFEREE]: 0.78 };
  return [REFEREE, LEFT, RIGHT].map((personId) => {
    const pts = poses[personId]!;
    const xs = pts.map((p) => p[0]);
    const ys = pts.map((p) => p[1]);
    const pad = 18;
    return {
      personId,
      x1: Math.min(...xs) - pad,
      y1: Math.min(...ys) - pad * 2.2,
      x2: Math.max(...xs) + pad,
      y2: Math.max(...ys) + pad * 0.6,
      confidence: conf[personId]!,
    };
  });
}

/** Approximate metres between the fighters' hips (assumes 1.8 m body height). */
export function hipDistanceM(pose: Pose, other: Pose): number {
  const mid = (p: Pose) => (p[11]![0] + p[12]![0]) / 2;
  return (Math.abs(mid(pose) - mid(other)) / BODY_PX) * 1.8;
}

/** Candidate frames for fighter selection: standing, separated moments. */
export const CANDIDATE_TIMES: readonly number[] = [6.2, 31.5, 48.9, 84.3, 101.7, 205.6, 262.4, 288.1];
