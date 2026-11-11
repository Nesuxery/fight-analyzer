import type { FighterTrackStats } from "../../contracts/generated";
import { RESULT_LABELS, UI_LABELS, formatDuration } from "../../labels";
import type { Side } from "../../model/analysis";
import { HelpTip } from "../../ui";
import { StatTerm } from "./StatPanel";

const L = RESULT_LABELS.quality;

/**
 * Rows of the "Veri kalitesi" group of a side panel: how well this fighter's
 * identity was followed. The state and the measurable time follow the
 * playhead; the other rows are totals of the whole video.
 */
export function TrackQuality({ side, stats, frames, now, measuredS }: {
  side: Side;
  stats: FighterTrackStats | undefined;
  frames: number;
  now: "tracked" | "occluded" | "uncertain" | undefined;
  measuredS: number | null;
}) {
  if (!stats) return null;
  const pct = (n: number) => `%${Math.round((n / Math.max(1, frames)) * 100)}`;
  const align = side === "red" ? "start" : "end";
  return (
    <div className="tq">
      {now && (
        <p className="tq__state">
          <span className={`tq__now tq__now--${now}`}>{L.state[now]}</span>
          <HelpTip label={UI_LABELS.help(L.stateTerm)} align={align}>{L.stateHelp}</HelpTip>
        </p>
      )}
      <dl className="tq__list">
        {measuredS !== null && (
          <div><dt><StatTerm term={L.measured} side={side} /></dt><dd className="num">{formatDuration(measuredS)}</dd></div>
        )}
        <div><dt><StatTerm term={L.tracked} side={side} /></dt><dd className="num">{pct(stats.tracked_frames)}</dd></div>
        <div><dt><StatTerm term={L.occluded} side={side} /></dt><dd className="num">{pct(stats.occluded_frames)}</dd></div>
        <div>
          <dt><StatTerm term={L.uncertain} side={side} /></dt>
          <dd className="num">{formatDuration(stats.uncertain_ms / 1000)}</dd>
        </div>
        <div>
          <dt><StatTerm term={L.longestUncertain} side={side} /></dt>
          <dd className="num">{formatDuration(stats.longest_uncertain_ms / 1000)}</dd>
        </div>
        <div><dt><StatTerm term={L.reacquisitions} side={side} /></dt><dd className="num">{stats.reacquisitions}</dd></div>
        <div><dt><StatTerm term={L.trackChanges} side={side} /></dt><dd className="num">{stats.track_changes}</dd></div>
      </dl>
      <p className="tq__scope">{L.scope}</p>
    </div>
  );
}
