/** Canvas drawing primitives for the video stage overlays. */
import type { Point, Pose } from "../demo/scene";
import { COLORS } from "../theme";

/** COCO-17 limb connections. */
export const COCO_EDGES: readonly [number, number][] = [
  [5, 7], [7, 9], [6, 8], [8, 10], [5, 6], [5, 11], [6, 12], [11, 12],
  [11, 13], [13, 15], [12, 14], [14, 16], [0, 1], [0, 2], [1, 3], [2, 4],
];

export interface Layers {
  skeleton: boolean;
  strikes: boolean;
  distance: boolean;
}

export const DEFAULT_LAYERS: Layers = { skeleton: true, strikes: true, distance: false };

function line(ctx: CanvasRenderingContext2D, a: Point, b: Point) {
  ctx.beginPath();
  ctx.moveTo(a[0], a[1]);
  ctx.lineTo(b[0], b[1]);
  ctx.stroke();
}

/** Stylised body standing in for video pixels in the demo scene. */
export function drawBody(ctx: CanvasRenderingContext2D, pose: Pose,
                         style: { skin: string; shorts: string }) {
  ctx.save();
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.strokeStyle = style.skin;
  ctx.lineWidth = 22;
  // torso as a filled quad
  const [ls, rs, lh, rh] = [pose[5]!, pose[6]!, pose[11]!, pose[12]!];
  ctx.fillStyle = style.skin;
  ctx.beginPath();
  ctx.moveTo(ls[0], ls[1]);
  ctx.lineTo(rs[0], rs[1]);
  ctx.lineTo(rh[0], rh[1]);
  ctx.lineTo(lh[0], lh[1]);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  for (const [a, b] of [[5, 7], [7, 9], [6, 8], [8, 10], [11, 13], [13, 15], [12, 14], [14, 16]] as const) {
    line(ctx, pose[a]!, pose[b]!);
  }
  // shorts
  ctx.strokeStyle = style.shorts;
  ctx.lineWidth = 26;
  line(ctx, lh, rh);
  const mid = (p: Point, q: Point, k: number): Point => [p[0] + (q[0] - p[0]) * k, p[1] + (q[1] - p[1]) * k];
  line(ctx, lh, mid(lh, pose[13]!, 0.45));
  line(ctx, rh, mid(rh, pose[14]!, 0.45));
  // head
  const nose = pose[0]!;
  const ear = pose[3]!;
  ctx.fillStyle = style.skin;
  ctx.beginPath();
  ctx.arc((nose[0] + ear[0]) / 2, (nose[1] + ear[1]) / 2 - 4, 19, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

export function drawSkeleton(ctx: CanvasRenderingContext2D, pose: Pose, color: string, alpha = 1) {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 3.5;
  ctx.lineCap = "round";
  ctx.shadowColor = color;
  ctx.shadowBlur = 8;
  for (const [a, b] of COCO_EDGES) line(ctx, pose[a]!, pose[b]!);
  ctx.shadowBlur = 0;
  for (const [x, y] of pose) {
    ctx.beginPath();
    ctx.arc(x, y, 3.6, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

/** Expanding ring at the striking hand/foot; k = 0..1 through the strike. */
export function drawStrike(ctx: CanvasRenderingContext2D, tip: Point, k: number, color: string,
                           significant: boolean) {
  const peak = Math.max(0, 1 - Math.abs(k - 0.55) / 0.45);
  if (peak <= 0) return;
  const c = significant ? COLORS.amber : color;
  ctx.save();
  ctx.strokeStyle = c;
  ctx.globalAlpha = peak;
  ctx.lineWidth = significant ? 4 : 3;
  const r = (significant ? 26 : 14) + 26 * k;
  ctx.beginPath();
  ctx.arc(tip[0], tip[1], r, 0, Math.PI * 2);
  ctx.stroke();
  // short spark lines
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2 + 0.3;
    line(ctx, [tip[0] + Math.cos(a) * (r + 4), tip[1] + Math.sin(a) * (r + 4)],
         [tip[0] + Math.cos(a) * (r + 12), tip[1] + Math.sin(a) * (r + 12)]);
  }
  ctx.restore();
}

export function drawDistance(ctx: CanvasRenderingContext2D, a: Point, b: Point, label: string) {
  ctx.save();
  ctx.strokeStyle = COLORS.text;
  ctx.globalAlpha = 0.85;
  ctx.lineWidth = 2;
  ctx.setLineDash([8, 6]);
  line(ctx, a, b);
  ctx.setLineDash([]);
  for (const p of [a, b]) line(ctx, [p[0], p[1] - 9], [p[0], p[1] + 9]);
  const mx = (a[0] + b[0]) / 2;
  const my = Math.min(a[1], b[1]) - 16;
  ctx.font = "600 20px Bahnschrift, 'Segoe UI', sans-serif";
  const w = ctx.measureText(label).width + 16;
  ctx.globalAlpha = 1;
  ctx.fillStyle = "rgba(6, 10, 19, 0.85)";
  ctx.fillRect(mx - w / 2, my - 15, w, 26);
  ctx.fillStyle = COLORS.text;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(label, mx, my - 2);
  ctx.restore();
}

let backdrop: HTMLCanvasElement | null = null;

/** Dark arena backdrop with an octagon floor (cached). */
export function drawBackdrop(ctx: CanvasRenderingContext2D, w: number, h: number) {
  if (!backdrop || backdrop.width !== w || backdrop.height !== h) {
    backdrop = document.createElement("canvas");
    backdrop.width = w;
    backdrop.height = h;
    const g = backdrop.getContext("2d")!;
    const bg = g.createLinearGradient(0, 0, 0, h);
    bg.addColorStop(0, "#04070e");
    bg.addColorStop(0.55, "#0a1120");
    bg.addColorStop(1, "#0d1628");
    g.fillStyle = bg;
    g.fillRect(0, 0, w, h);
    const spot = g.createRadialGradient(w / 2, h * 0.25, 20, w / 2, h * 0.4, w * 0.6);
    spot.addColorStop(0, "rgba(120, 150, 210, 0.16)");
    spot.addColorStop(1, "rgba(0, 0, 0, 0)");
    g.fillStyle = spot;
    g.fillRect(0, 0, w, h);
    // octagon floor in perspective
    const cx = w / 2;
    const cy = h * 0.83;
    const rx = w * 0.47;
    const ry = h * 0.17;
    g.beginPath();
    for (let i = 0; i < 8; i++) {
      const a = Math.PI / 8 + (i * Math.PI) / 4;
      const x = cx + Math.cos(a) * rx;
      const y = cy + Math.sin(a) * ry;
      if (i === 0) g.moveTo(x, y);
      else g.lineTo(x, y);
    }
    g.closePath();
    g.fillStyle = "#0f1a2e";
    g.fill();
    g.strokeStyle = "#22314f";
    g.lineWidth = 3;
    g.stroke();
    // fence posts and mesh hint
    g.strokeStyle = "rgba(60, 80, 120, 0.35)";
    g.lineWidth = 2;
    for (let i = 0; i < 8; i++) {
      const a = Math.PI / 8 + (i * Math.PI) / 4;
      const x = cx + Math.cos(a) * rx;
      const y = cy + Math.sin(a) * ry;
      if (Math.sin(a) < 0) line(g, [x, y], [x, y - h * 0.42]);
    }
    g.strokeStyle = "rgba(60, 80, 120, 0.12)";
    for (let y = h * 0.22; y < h * 0.66; y += 14) line(g, [0, y], [w, y]);
    // centre logo ring
    g.strokeStyle = "rgba(255, 255, 255, 0.05)";
    g.lineWidth = 6;
    g.beginPath();
    g.ellipse(cx, cy, rx * 0.28, ry * 0.42, 0, 0, Math.PI * 2);
    g.stroke();
  }
  ctx.drawImage(backdrop, 0, 0);
}

export function drawWatermark(ctx: CanvasRenderingContext2D, text: string) {
  ctx.save();
  ctx.font = "700 22px Bahnschrift, 'Segoe UI', sans-serif";
  ctx.textBaseline = "top";
  const w = ctx.measureText(text).width + 20;
  ctx.fillStyle = "rgba(255, 176, 32, 0.92)";
  ctx.fillRect(18, 18, w, 32);
  ctx.fillStyle = "#1a1203";
  ctx.fillText(text, 28, 23);
  ctx.restore();
}
