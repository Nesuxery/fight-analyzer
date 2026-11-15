import type { FighterTrackStats } from "../../contracts/generated";
import { RESULT_LABELS, UI_LABELS, formatDuration } from "../../labels";
import type { Side } from "../../model/analysis";
import type { QualitySummary } from "../../model/quality";
import { HelpTip } from "../../ui";
import { StatTerm } from "./StatPanel";

const L = RESULT_LABELS.quality;
/** Causes below this share of the scope are not listed. */
const MIN_CAUSE_SHARE = 0.01;

const pct = (share: number) => `%${Math.round(share * 100)}`;
/** Seconds as text; below a second one decimal, so a short gap does not read as "0 sn". */
const duration = (ms: number) => (ms > 0 && ms < 1000 ? `${(ms / 1000).toFixed(1).replace(".", ",")} sn` : formatDuration(ms / 1000));

/**
 * Rows of the "Veri kalitesi" group of a side panel: how well this fighter's
 * identity was followed in the selected scope, and what lowered the
 * confidence. Only the state badge refers to the presented frame. An analysis
 * made before the quality data existed shows its whole-video totals, labelled.
 */
export function TrackQuality({ side, quality, legacy, frames, now, scopeNote }: {
  side: Side;
  /** Summary for the scope in effect; null: the analysis has no quality data. */
  quality: QualitySummary | null;
  legacy: FighterTrackStats | undefined;
  frames: number;
  now: "tracked" | "occluded" | "uncertain" | undefined;
  scopeNote: string | null;
}) {
  const align = side === "red" ? "start" : "end";
  const state = now && (
    <p className="tq__state">
      <span className={`tq__now tq__now--${now}`}>{L.state[now]}</span>
      <HelpTip label={UI_LABELS.help(L.stateTerm)} align={align}>{L.stateHelp}</HelpTip>
    </p>
  );
  if (quality === null) {
    if (!legacy) return null;
    const share = (n: number) => `%${Math.round((n / Math.max(1, frames)) * 100)}`;
    return (
      <div className="tq">
        {state}
        <dl className="tq__list">
          <div><dt>{L.legacy.tracked}</dt><dd className="num">{share(legacy.tracked_frames)}</dd></div>
          <div><dt>{L.legacy.occluded}</dt><dd className="num">{share(legacy.occluded_frames)}</dd></div>
          <div><dt>{L.legacy.uncertain}</dt><dd className="num">{formatDuration(legacy.uncertain_ms / 1000)}</dd></div>
          <div>
            <dt>{L.legacy.longestUncertain}</dt>
            <dd className="num">{formatDuration(legacy.longest_uncertain_ms / 1000)}</dd>
          </div>
        </dl>
        <p className="tq__scope">{L.outdated}</p>
      </div>
    );
  }
  const causes = quality.causes.filter((c) => c.share >= MIN_CAUSE_SHARE);
  return (
    <div className="tq">
      {state}
      {quality.frames === 0 ? (
        <p className="tq__scope">{L.noFightTime}</p>
      ) : (
        <>
          <dl className="tq__list">
            <div>
              <dt><StatTerm term={L.measurable} side={side} /></dt>
              <dd className="num">{pct(quality.measurableShare)}</dd>
            </div>
            <div><dt><StatTerm term={L.occluded} side={side} /></dt><dd className="num">{pct(quality.occludedShare)}</dd></div>
            <div><dt><StatTerm term={L.uncertain} side={side} /></dt><dd className="num">{duration(quality.uncertainMs)}</dd></div>
            <div>
              <dt><StatTerm term={L.longestUncertain} side={side} /></dt>
              <dd className="num">{duration(quality.longestUncertainMs)}</dd>
            </div>
            <div>
              <dt><StatTerm term={L.identityChanges} side={side} /></dt>
              <dd className="num">{quality.identityChanges}</dd>
            </div>
          </dl>
          <div className="tq__causes">
            <p className="tq__causestitle">
              {L.causesTitle}
              <HelpTip label={UI_LABELS.help(L.causesTitle)} align={align}>{L.causesHelp}</HelpTip>
            </p>
            {causes.length === 0 ? (
              <p className="tq__scope">{L.noCauses}</p>
            ) : (
              <ul className="tq__causelist">
                {causes.map((c) => (
                  <li key={c.cause}><span>{L.causes[c.cause]}</span><span className="num">{pct(c.share)}</span></li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
      {scopeNote && <p className="tq__scope">{scopeNote}</p>}
    </div>
  );
}
