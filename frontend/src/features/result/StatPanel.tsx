import type { ReactNode } from "react";
import { RESULT_LABELS, SIDE_LABEL, UI_LABELS } from "../../labels";
import type { Side, StatsView } from "../../model/analysis";
import { formatClock } from "../../player/clock";
import { DemoTag, HelpTip } from "../../ui";
import { IconMove, IconSignal, IconTimer, IconZap } from "../../ui/icons";

const L = RESULT_LABELS.stats;
const dash = UI_LABELS.noValue;

/** Value with a unit suffix; the unit is omitted when there is no value. */
function V({ value, unit }: { value: number | null; unit: string }) {
  return value === null ? <>{dash}</> : <>{value}<small>{unit}</small></>;
}

function Meter({ value, side }: { value: number | null; side: Side }) {
  return (
    <span className={`meter meter--${side}`} aria-hidden="true">
      <span className="meter__fill" style={{ width: `${value ?? 0}%` }} />
    </span>
  );
}

/** A group of metrics with a small heading and icon. */
export function StatGroup({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <div className="statgroup">
      <h3 className="statgroup__title">{icon}{title}</h3>
      {children}
    </div>
  );
}

/** Name of a metric with its "?"; the explanation opens towards the middle of the page. */
export function StatTerm({ term, side }: { term: { label: string; help: string }; side: Side }) {
  return (
    <>
      {term.label}
      <HelpTip label={UI_LABELS.help(term.label)} align={side === "red" ? "start" : "end"}>{term.help}</HelpTip>
    </>
  );
}

/**
 * Side panel of one corner. Metrics are grouped: striking, movement and
 * pressure, control, and (real analyses only) data quality.
 */
export function StatPanel({ side, name, stats, untilS, demo, emptyNote = L.empty, quality }: {
  side: Side;
  name: string | null;
  stats: StatsView;
  untilS: number | null;
  demo: boolean;
  emptyNote?: string;
  /** Rows of the "Veri kalitesi" group; left out when there is no tracking data (Demo). */
  quality?: ReactNode;
}) {
  const s = stats;
  const hasData = Object.values(s).some((v) => v !== null);
  return (
    <section className={`stats stats--${side}`} aria-label={L.region(SIDE_LABEL[side])}>
      <header className="stats__head">
        <span className="stats__corner">{SIDE_LABEL[side]}</span>
        <span className="stats__name display" title={name ?? undefined}>{name ?? dash}</span>
        {demo && <DemoTag small />}
      </header>
      <StatGroup icon={<IconZap size={16} />} title={L.groups.striking}>
        <dl className="stats__list">
          <div className="stat">
            <dt><StatTerm term={L.strikeAttempts} side={side} /></dt>
            <dd className="stat__big num">{s.strikeAttempts ?? dash}</dd>
          </div>
          <div className="stat">
            <dt><StatTerm term={L.kicks} side={side} /></dt>
            <dd className="stat__big num">{s.kicks ?? dash}</dd>
          </div>
        </dl>
      </StatGroup>
      <StatGroup icon={<IconMove size={16} />} title={L.groups.movement}>
        <dl className="stats__list">
          <div className="stat stat--meter">
            <dt><StatTerm term={L.activity} side={side} /></dt>
            <dd className="num"><V value={s.activity} unit={L.outOf100} /></dd>
            <Meter value={s.activity} side={side} />
          </div>
          <div className="stat stat--meter">
            <dt><StatTerm term={L.pressure} side={side} /></dt>
            <dd className="num"><V value={s.pressure} unit={L.percent} /></dd>
            <Meter value={s.pressure} side={side} />
          </div>
          <div className="stat stat--split">
            <dt><StatTerm term={L.advanceRetreat} side={side} /></dt>
            <dd className="num">
              <V value={s.advance} unit={L.percent} /> <span className="stat__sep">/</span> <V value={s.retreat} unit={L.percent} />
            </dd>
            <span className={`split split--${side}`} aria-hidden="true">
              <span className="split__adv" style={{ width: `${s.advance ?? 0}%` }} />
              <span className="split__ret" style={{ width: `${s.retreat ?? 0}%` }} />
            </span>
          </div>
        </dl>
      </StatGroup>
      <StatGroup icon={<IconTimer size={16} />} title={L.groups.control}>
        <dl className="stats__list">
          <div className="stat">
            <dt><StatTerm term={L.controlTime} side={side} /></dt>
            <dd className="num">{s.controlS === null ? dash : formatClock(s.controlS)}</dd>
          </div>
          <div className="stat stat--amber">
            <dt><StatTerm term={L.majorEvents} side={side} /></dt>
            <dd className="stat__big num">{s.significant ?? dash}</dd>
          </div>
        </dl>
      </StatGroup>
      <footer className="stats__foot">
        {hasData && untilS !== null ? L.interval(formatClock(untilS)) : emptyNote}
      </footer>
      {quality && <StatGroup icon={<IconSignal size={16} />} title={L.groups.quality}>{quality}</StatGroup>}
    </section>
  );
}
