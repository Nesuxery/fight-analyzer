import type { DataOrigin } from "../../contracts/generated";
import type { Side, StatsView, TimelineEvent } from "../../model/analysis";
import type { Layers } from "../../player/draw";

/** Everything the result screen needs; produced by the demo today and by
 * the scoring/export stages later. */
export interface ResultData {
  origin: DataOrigin;
  durationS: number;
  fps: number;
  frame: { width: number; height: number };
  names: Record<Side, string>;
  events: TimelineEvent[];
  /** Red corner's momentum share (0..1) at time t. */
  momentumAt: (t: number) => number;
  /** Evenly spaced red share samples for the timeline sparkline. */
  momentumSeries: number[];
  statsAt: (side: Side, t: number) => StatsView;
  draw: (ctx: CanvasRenderingContext2D, t: number, layers: Layers) => void;
}

export interface FighterActions {
  onRename?: (side: Side, name: string) => void;
  onSwap?: () => void;
  onReselect?: () => void;
  /** Opens the export (MP4/CSV/JSON); absent where there is nothing to export (demo). */
  onExport?: () => void;
}
