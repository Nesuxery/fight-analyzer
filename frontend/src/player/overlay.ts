/**
 * Canvas drawing of the analysis overlay for one video frame: fighters'
 * skeletons (joints, limbs, head ring, name), other people (thin, grey),
 * event effects (a short highlight of the striking limb, a small ring for a
 * possible contact) and the distance between the fighters. Colours, the
 * confidence threshold and effect timings come from shared/overlay-style.json,
 * which the MP4 export (backend/fight_analyzer/export/render.py) uses too.
 *
 * Coordinates are video pixels (the caller sets the letterbox transform);
 * line widths, glow and text are given in CSS pixels and converted, so the
 * overlay looks the same at any size and pixel density. Nothing is invented:
 * joints below KP_MIN and bones touching them are not drawn, and only people
 * whose identity is verified get a fighter colour. Name labels are drawn after
 * all skeletons and placed by labelLayout.ts: never over each other, always
 * inside the picture (the MP4 export uses the same rule).
 */
import { OVERLAY_STYLE } from "../contracts/overlayStyle";
import { OVERLAY_LABELS } from "../labels";
import { cssToken, withAlpha } from "../styles/tokens";
import type { Fit } from "./geometry";
import { placeLabels } from "./labelLayout";

/** Same threshold as the motion analysis (MotionSettings.kp_min_conf). */
export const KP_MIN = OVERLAY_STYLE.kp_min_conf;

export const OVERLAY_COLORS = OVERLAY_STYLE.colors;

const BONES: readonly [number, number][] = [
  [5, 7], [7, 9], [6, 8], [8, 10], [5, 6], [5, 11], [6, 12], [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
];
const FACE = [0, 1, 2, 3, 4];

export interface OverlayPoint { x: number; y: number; confidence: number }

export interface OverlayPerson {
  keypoints: OverlayPoint[];
  role: "red" | "blue" | "other";
  /** Fighters only: "occluded" = identity kept through a short overlap (drawn dashed). */
  state?: "tracked" | "occluded";
  label?: string;
}

/** Highlight of the striking limb around the peak of an attempt. */
export interface OverlayFlash {
  /** Joints of the limb (shoulder/hip to wrist/ankle) in the actor's current skeleton, if drawn. */
  limb: OverlayPoint[] | null;
  /** Striking joint at the peak: used when the limb is not visible now. */
  at: { x: number; y: number } | null;
  side: "red" | "blue" | null;
  /** 1 at the peak, fading to 0 (effects.ts). */
  strength: number;
}

/** Small ring where the striking limb overlapped the opponent (possible contact). */
export interface OverlayRing {
  x: number;
  y: number;
  strength: number;
  /** Show the "olası temas" text (only the most recent ring, so labels never pile up). */
  labelled: boolean;
}

export interface OverlayDistance {
  a: { x: number; y: number };
  b: { x: number; y: number };
  /** Precomputed distance in torso lengths at this time, if measured. */
  value: number | null;
}

export interface OverlayScene {
  people: OverlayPerson[];
  flashes: OverlayFlash[];
  rings: OverlayRing[];
  distance: OverlayDistance | null;
}

export interface OverlayLayers {
  skeleton: boolean;
  strikes: boolean;
  distance: boolean;
  others: boolean;
}

const ok = (p: OverlayPoint | undefined): p is OverlayPoint => !!p && p.confidence >= KP_MIN;

function centerOf(points: OverlayPoint[]): { x: number; y: number } {
  return { x: points.reduce((s, p) => s + p.x, 0) / points.length, y: points.reduce((s, p) => s + p.y, 0) / points.length };
}

function torsoLength(k: OverlayPoint[]): number | null {
  const [ls, rs, lh, rh] = [k[5], k[6], k[11], k[12]];
  if (!ok(ls) || !ok(rs) || !ok(lh) || !ok(rh)) return null;
  return Math.hypot((ls.x + rs.x - lh.x - rh.x) / 2, (ls.y + rs.y - lh.y - rh.y) / 2);
}

function label(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, color: string, px: number,
               align: CanvasTextAlign = "center") {
  ctx.font = `600 ${12 * px}px ${cssToken("--font-sans")}`;
  ctx.textAlign = align;
  ctx.textBaseline = "bottom";
  ctx.lineWidth = 3 * px;
  ctx.strokeStyle = withAlpha(OVERLAY_COLORS.outline, 0.8);
  ctx.strokeText(text, x, y);
  ctx.fillStyle = color;
  ctx.fillText(text, x, y);
}

/** A fighter's name, wanted centred above the head (ax, ay: centre x, bottom y). */
interface NameLabel {
  text: string;
  color: string;
  ax: number;
  ay: number;
}

/** Draws one person; returns the fighter's name label to place once all skeletons are drawn. */
function drawPerson(ctx: CanvasRenderingContext2D, person: OverlayPerson, px: number, dpr: number): NameLabel | null {
  const k = person.keypoints;
  let name: NameLabel | null = null;
  const fighter = person.role !== "other";
  const color = OVERLAY_COLORS[person.role];
  const path = new Path2D();
  for (const [a, b] of BONES) {
    if (!ok(k[a]) || !ok(k[b])) continue;
    path.moveTo(k[a]!.x, k[a]!.y);
    path.lineTo(k[b]!.x, k[b]!.y);
  }
  ctx.save();
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.setLineDash(person.state === "occluded" ? [7 * px, 5 * px] : []);
  if (fighter) {
    ctx.strokeStyle = withAlpha(OVERLAY_COLORS.outline, 0.55); // contrast on bright canvas
    ctx.lineWidth = 5.5 * px;
    ctx.stroke(path);
    ctx.shadowColor = `${color}99`; // modest glow (shadowBlur is in device pixels)
    ctx.shadowBlur = 6 * dpr;
  } else {
    ctx.globalAlpha = 0.55;
  }
  ctx.strokeStyle = color;
  ctx.lineWidth = (fighter ? 2.6 : 1.5) * px;
  ctx.stroke(path);
  ctx.shadowBlur = 0;
  ctx.setLineDash([]);
  if (fighter) {
    for (let i = 5; i < k.length; i++) {
      if (!ok(k[i])) continue;
      ctx.beginPath();
      ctx.arc(k[i]!.x, k[i]!.y, 3.2 * px, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.lineWidth = 1.2 * px;
      ctx.strokeStyle = withAlpha(OVERLAY_COLORS.outline, 0.7);
      ctx.stroke();
    }
    // Head ring when the face is visible: centred on the face points, sized from
    // their spread and the torso so it stays plausible when the face is small.
    const face = FACE.map((i) => k[i]).filter(ok);
    let top: { x: number; y: number } | null = null;
    if (face.length >= 2) {
      const c = centerOf(face);
      const spread = Math.max(...face.map((p) => Math.hypot(p.x - c.x, p.y - c.y)));
      const torso = torsoLength(k);
      const r = Math.max(spread * 1.7, torso ? torso * 0.22 : 0, 9 * px);
      ctx.beginPath();
      ctx.arc(c.x, c.y, r, 0, Math.PI * 2);
      ctx.lineWidth = 2 * px;
      ctx.strokeStyle = color;
      ctx.stroke();
      top = { x: c.x, y: c.y - r - 4 * px };
    } else {
      const visible = k.filter(ok);
      if (visible.length) {
        const highest = visible.reduce((m, p) => (p.y < m.y ? p : m));
        top = { x: highest.x, y: highest.y - 10 * px };
      }
    }
    if (person.label && top) name = { text: person.label, color, ax: top.x, ay: top.y };
  }
  ctx.restore();
  return name;
}

const NAME_FONT_PX = 12;
/** label() strokes a 3 px outline around the letters. */
const NAME_OUTLINE_PX = 3;
const NAME_MARGIN_PX = 4;
const NAME_GAP_PX = 4;

/** Fighters' names: apart from each other and inside the picture (labelLayout.ts). */
function drawNameLabels(ctx: CanvasRenderingContext2D, names: NameLabel[], px: number,
                        frame: { width: number; height: number }) {
  if (!names.length) return;
  ctx.save();
  ctx.font = `600 ${NAME_FONT_PX * px}px ${cssToken("--font-sans")}`;
  const outline = NAME_OUTLINE_PX * px;
  const h = NAME_FONT_PX * px + outline;
  const sized = names.map((n) => ({ ...n, w: ctx.measureText(n.text).width + outline, h }));
  const margin = NAME_MARGIN_PX * px;
  const spots = placeLabels(sized, { left: margin, top: margin, right: frame.width - margin, bottom: frame.height - margin },
                            NAME_GAP_PX * px);
  sized.forEach((n, i) => {
    const spot = spots[i]!;
    label(ctx, n.text, spot.x + n.w / 2, spot.y + n.h - outline / 2, n.color, px);
  });
  ctx.restore();
}

/** Colour moved toward white by k (0..1). */
function tint(hex: string, k: number): string {
  const n = parseInt(hex.slice(1), 16);
  const ch = (shift: number) => Math.round(((n >> shift) & 255) + (255 - ((n >> shift) & 255)) * k);
  return `rgb(${ch(16)}, ${ch(8)}, ${ch(0)})`;
}

function drawFlash(ctx: CanvasRenderingContext2D, f: OverlayFlash, px: number) {
  const color = tint(f.side ? OVERLAY_COLORS[f.side] : OVERLAY_COLORS.light, 0.45);
  ctx.save();
  ctx.globalAlpha = 0.75 * f.strength;
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineCap = "round";
  let drawn = false;
  const k = f.limb ?? [];
  ctx.lineWidth = 6 * px;
  for (let i = 0; i + 1 < k.length; i++) {
    if (!ok(k[i]) || !ok(k[i + 1])) continue;
    ctx.beginPath();
    ctx.moveTo(k[i]!.x, k[i]!.y);
    ctx.lineTo(k[i + 1]!.x, k[i + 1]!.y);
    ctx.stroke();
    drawn = true;
  }
  const end = k[k.length - 1];
  if (ok(end)) {
    ctx.beginPath();
    ctx.arc(end.x, end.y, 6 * px, 0, Math.PI * 2);
    ctx.fill();
    drawn = true;
  }
  if (!drawn && f.at) {
    ctx.beginPath();
    ctx.arc(f.at.x, f.at.y, 6 * px, 0, Math.PI * 2);
    ctx.lineWidth = 2.5 * px;
    ctx.stroke();
  }
  ctx.restore();
}

function drawRing(ctx: CanvasRenderingContext2D, r: OverlayRing, px: number) {
  const radius = OVERLAY_STYLE.contact_ring.radius_px * px;
  ctx.save();
  ctx.globalAlpha = r.strength;
  ctx.beginPath();
  ctx.arc(r.x, r.y, radius, 0, Math.PI * 2);
  ctx.lineWidth = 2.5 * px;
  ctx.strokeStyle = OVERLAY_COLORS.amber;
  ctx.stroke();
  if (r.labelled) {
    label(ctx, OVERLAY_LABELS.possibleContact, r.x + radius + 6 * px, r.y - radius, OVERLAY_COLORS.amber, px, "left");
  }
  ctx.restore();
}

function drawDistance(ctx: CanvasRenderingContext2D, d: OverlayDistance, px: number) {
  ctx.save();
  ctx.setLineDash([8 * px, 6 * px]);
  ctx.lineWidth = 2 * px;
  ctx.strokeStyle = withAlpha(OVERLAY_COLORS.light, 0.85);
  ctx.beginPath();
  ctx.moveTo(d.a.x, d.a.y);
  ctx.lineTo(d.b.x, d.b.y);
  ctx.stroke();
  ctx.setLineDash([]);
  for (const p of [d.a, d.b]) {
    ctx.beginPath();
    ctx.arc(p.x, p.y, 4 * px, 0, Math.PI * 2);
    ctx.fillStyle = OVERLAY_COLORS.light;
    ctx.fill();
  }
  if (d.value !== null) {
    const text = OVERLAY_LABELS.distance(
      d.value.toLocaleString("tr-TR", { maximumFractionDigits: 1, minimumFractionDigits: 1 }));
    label(ctx, text, (d.a.x + d.b.x) / 2, (d.a.y + d.b.y) / 2 - 8 * px, OVERLAY_COLORS.light, px);
  }
  ctx.restore();
}

/**
 * Draw a scene; the context must already map video pixels to the canvas (see geometry).
 * `frame`: the video size in pixels, the area name labels are kept in.
 */
export function drawOverlay(ctx: CanvasRenderingContext2D, scene: OverlayScene, fit: Fit, dpr: number,
                            layers: OverlayLayers, frame: { width: number; height: number }) {
  const px = 1 / fit.scale; // one CSS pixel in video pixels
  if (layers.skeleton) {
    if (layers.others) for (const p of scene.people) if (p.role === "other") drawPerson(ctx, p, px, dpr);
    const names: NameLabel[] = [];
    for (const p of scene.people) {
      if (p.role === "other") continue;
      const name = drawPerson(ctx, p, px, dpr);
      if (name) names.push(name);
    }
    drawNameLabels(ctx, names, px, frame);
  }
  if (layers.distance && scene.distance) drawDistance(ctx, scene.distance, px);
  if (layers.strikes) {
    for (const f of scene.flashes) drawFlash(ctx, f, px);
    for (const r of scene.rings) drawRing(ctx, r, px);
  }
}

/** Centre between the hips (else the shoulders) if both points are measured. */
export function bodyCenter(k: OverlayPoint[]): { x: number; y: number } | null {
  for (const [a, b] of [[11, 12], [5, 6]] as const) {
    if (ok(k[a]) && ok(k[b])) return { x: (k[a]!.x + k[b]!.x) / 2, y: (k[a]!.y + k[b]!.y) / 2 };
  }
  return null;
}
