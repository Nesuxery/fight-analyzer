import { OVERLAY_STYLE } from "../contracts/overlayStyle";
import { DEMO_LABELS } from "../labels";
import type { Assignment, PersonId } from "../model/analysis";
import { drawBackdrop, drawBody, drawDistance, drawSkeleton, drawStrike, drawWatermark } from "../player/draw";
import type { Layers } from "../player/draw";
import { cssToken } from "../styles/tokens";
import { sideOf } from "./analysis";
import { hipDistanceM, sceneAt } from "./scene";
import { DEMO_FRAME, LEFT, REFEREE, RIGHT } from "./script";

export interface DemoRenderOptions {
  layers: Layers;
  /** Colour skeletons by corner; null draws every person in neutral white
   * (before fighters are chosen). */
  assignment: Assignment | null;
}

/** Synthetic "footage" colours of each person (tokens.css, --scene-*). */
const BODY_TOKENS: Record<PersonId, { skin: `--${string}`; shorts: `--${string}` }> = {
  [LEFT]: { skin: "--scene-left-skin", shorts: "--scene-left-shorts" },
  [RIGHT]: { skin: "--scene-right-skin", shorts: "--scene-right-shorts" },
  [REFEREE]: { skin: "--scene-referee-skin", shorts: "--scene-referee-shorts" },
};

const bodyStyle = (id: PersonId) => {
  const t = BODY_TOKENS[id]!;
  return { skin: cssToken(t.skin), shorts: cssToken(t.shorts) };
};

export function renderDemo(ctx: CanvasRenderingContext2D, t: number, opts: DemoRenderOptions) {
  const { width, height } = DEMO_FRAME;
  drawBackdrop(ctx, width, height);
  const scene = sceneAt(t);
  for (const id of [REFEREE, LEFT, RIGHT]) drawBody(ctx, scene.poses[id]!, bodyStyle(id));

  const neutral = cssToken("--stage-text");
  const colorOf = (id: PersonId): string | null => {
    if (!opts.assignment) return neutral;
    const side = sideOf(id, opts.assignment);
    return side ? OVERLAY_STYLE.colors[side] : null;
  };

  if (opts.layers.distance) {
    const a = scene.poses[LEFT]!;
    const b = scene.poses[RIGHT]!;
    const hip = (p: typeof a) => [(p[11]![0] + p[12]![0]) / 2, (p[11]![1] + p[12]![1]) / 2] as [number, number];
    const meters = hipDistanceM(a, b).toFixed(1).replace(".", ",");
    drawDistance(ctx, hip(a), hip(b), `≈ ${meters} m`);
  }
  if (opts.layers.skeleton) {
    for (const id of [REFEREE, LEFT, RIGHT]) {
      const color = colorOf(id);
      if (color) drawSkeleton(ctx, scene.poses[id]!, color, id === REFEREE ? 0.6 : 1);
    }
  }
  if (opts.layers.strikes) {
    for (const s of scene.strikes) {
      const color = s.event.actor ? colorOf(s.event.actor) : null;
      drawStrike(ctx, s.tip, s.progress, color ?? neutral, s.event.significant);
    }
  }
  drawWatermark(ctx, DEMO_LABELS.watermark);
}
