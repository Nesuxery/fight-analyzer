/**
 * Where the fighters' name labels go over the video. The MP4 export follows the
 * same rule with the same arithmetic (backend/fight_analyzer/export/label_layout.py);
 * both are checked against shared/fixtures/label-layout.json.
 *
 * A label wants to sit centred above its anchor (the top of the fighter's head).
 * 1. Every label stays inside the bounds (the picture, less a margin).
 * 2. Labels never overlap. Two that would are pushed apart sideways, each as far
 *    as it can go while still covering its own anchor horizontally.
 * 3. If that is not enough, they are stacked: the label with the higher anchor
 *    goes on top (the left one on a tie); without room above, the other one goes
 *    below it.
 */
export interface LabelRequest {
  /** Anchor: centre x and bottom y the label wants. */
  ax: number;
  ay: number;
  /** Size of the label, outline included. */
  w: number;
  h: number;
}

export interface LabelBounds {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

/** Top-left corner of a placed label. */
export interface LabelPosition {
  x: number;
  y: number;
}

interface Box extends LabelRequest {
  x: number;
  y: number;
}

/** Rounding slack, so labels exactly `gap` apart do not count as overlapping. */
const EPS = 1e-6;

/** lo when the range is empty (a label larger than the bounds sticks to the left or top). */
function clamp(v: number, lo: number, hi: number): number {
  return hi < lo ? lo : Math.min(Math.max(v, lo), hi);
}

function overlap(a: Box, c: Box, gap: number): boolean {
  return a.x < c.x + c.w + gap - EPS && c.x < a.x + a.w + gap - EPS &&
    a.y < c.y + c.h + gap - EPS && c.y < a.y + a.h + gap - EPS;
}

/** a is the label with the left anchor, c the one with the right anchor. */
function separate(a: Box, c: Box, b: LabelBounds, gap: number): void {
  const need = a.x + a.w + gap - c.x;
  const roomA = Math.max(0, Math.min(a.x - b.left, a.x + a.w - a.ax));
  const roomC = Math.max(0, Math.min(b.right - (c.x + c.w), c.ax - c.x));
  if (need <= roomA + roomC) {
    let dA = Math.min(roomA, need / 2);
    let dC = need - dA;
    if (dC > roomC) {
      dC = roomC;
      dA = need - dC;
    }
    a.x -= dA;
    c.x += dC;
    return;
  }
  const [upper, lower] = c.ay < a.ay ? [c, a] : [a, c];
  const y = lower.y - gap - upper.h;
  if (y >= b.top) {
    upper.y = y;
    return;
  }
  upper.y = b.top;
  lower.y = clamp(upper.y + upper.h + gap, b.top, b.bottom - lower.h);
}

/** Positions in the order of `labels`. */
export function placeLabels(labels: readonly LabelRequest[], bounds: LabelBounds, gap: number): LabelPosition[] {
  const boxes: Box[] = labels.map((l) => ({
    ...l,
    x: clamp(l.ax - l.w / 2, bounds.left, bounds.right - l.w),
    y: clamp(l.ay - l.h, bounds.top, bounds.bottom - l.h),
  }));
  const order = boxes.map((_, i) => i).sort((i, j) => boxes[i]!.ax - boxes[j]!.ax || i - j);
  for (let pass = 0; pass < boxes.length; pass++) {
    let moved = false;
    for (let p = 0; p < order.length; p++) {
      for (let q = p + 1; q < order.length; q++) {
        const a = boxes[order[p]!]!;
        const c = boxes[order[q]!]!;
        if (!overlap(a, c, gap)) continue;
        separate(a, c, bounds, gap);
        moved = true;
      }
    }
    if (!moved) break;
  }
  return boxes.map(({ x, y }) => ({ x, y }));
}
