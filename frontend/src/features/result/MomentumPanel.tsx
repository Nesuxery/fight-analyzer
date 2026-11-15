import { useMemo } from "react";
import type { FightEvent, MomentumContribution, MomentumParameters } from "../../contracts/generated";
import { EVENT_LABELS, RESULT_LABELS, SIDE_LABEL, UI_LABELS, formatNumber } from "../../labels";
import type { Side } from "../../model/analysis";
import { SOURCE_LABELS, breakdown, eventEffect, eventMoment, redShare, totals } from "../../model/measured";
import type { Intervals } from "../../model/measured";
import { formatClock } from "../../player/clock";
import { HelpTip, SectionHeading } from "../../ui";

const L = RESULT_LABELS.mpanel;
const pts = (v: number) => formatNumber(v, v >= 10 ? 1 : 2);

/**
 * Why the momentum is where it is: one plain sentence, the current points,
 * each side's points by source, and what the selected event contributes right
 * now. The formula and the model parameters are under "Nasıl hesaplanır?".
 */
export function MomentumPanel({ contribs, params, tMs, names, selected, iv = [], unattributed = 0 }: {
  /** Events left out of the ledger because it is uncertain whose they are. */
  unattributed?: number;
  contribs: MomentumContribution[];
  params: MomentumParameters;
  tMs: number;
  /** Excluded parts: the momentum runs on fight time. */
  iv?: Intervals;
  names: Record<Side, string>;
  selected: FightEvent | null;
}) {
  const m = totals(contribs, tMs, params, iv);
  const red = redShare(m, params.prior);
  const parts = useMemo(() => breakdown(contribs, tMs, params, iv), [contribs, tMs, params, iv]);
  // Effect when it happened, and what is left of it now (points decay).
  const moment = selected ? eventMoment(selected) : 0;
  const effect = selected ? eventEffect(contribs, selected.event_id, moment, params, iv) : null;
  const effectNow = selected && tMs >= moment ? eventEffect(contribs, selected.event_id, tMs, params, iv) : null;
  const halfLife = formatNumber(params.half_life_s, 0);

  return (
    <section className="mpanel" aria-label={L.region}>
      <SectionHeading level={3} title={L.title} />
      <p className="mpanel__intro">{L.intro(halfLife)}</p>
      <p className="mpanel__now">
        {L.now}: {names.red} <b className="num">{pts(m.red)}</b> {L.points}, {names.blue}{" "}
        <b className="num">{pts(m.blue)}</b> {L.points} → <b className="num">%{Math.round(red)}</b> /{" "}
        <b className="num">%{100 - Math.round(red)}</b>
      </p>

      {unattributed > 0 && (
        <p className="mpanel__unattributed">
          {L.unattributed(unattributed)}
          <HelpTip label={UI_LABELS.help(L.unattributedTerm)} align="start">{L.unattributedHelp}</HelpTip>
        </p>
      )}

      <details className="mpanel__how">
        <summary>{L.howTitle}</summary>
        <p className="mpanel__formula">
          {L.formula(formatNumber(params.prior, 0), formatNumber(params.prior * 2, 0), halfLife)}
        </p>
        <p className="mpanel__paramstitle">{L.paramsTitle}</p>
        <dl className="mpanel__params">
          <div><dt>{L.params.strike_attempt}</dt><dd className="num">{pts(params.strike_attempt)}</dd></div>
          <div><dt>{L.params.kick_attempt}</dt><dd className="num">{pts(params.kick_attempt)}</dd></div>
          <div><dt>{L.params.contact_bonus}</dt><dd className="num">{pts(params.contact_bonus)}</dd></div>
          <div><dt>{L.params.advance_per_s}</dt><dd className="num">{pts(params.advance_per_s)}</dd></div>
          <div><dt>{L.params.control_per_s}</dt><dd className="num">{pts(params.control_per_s)}</dd></div>
          <div><dt>{L.params.knockdown}</dt><dd className="num">{pts(params.knockdown)}</dd></div>
          <div><dt>{L.params.takedown}</dt><dd className="num">{pts(params.takedown)}</dd></div>
          <div>
            <dt>{L.params.min_major_confidence}</dt>
            <dd className="num">%{Math.round(params.min_major_confidence * 100)}</dd>
          </div>
          <div><dt>{L.params.half_life_s}</dt><dd className="num">{halfLife} {L.seconds}</dd></div>
          <div><dt>{L.params.prior}</dt><dd className="num">{pts(params.prior)}</dd></div>
        </dl>
      </details>

      <div className="mpanel__sides">
        {(["red", "blue"] as const).map((side) => (
          <div key={side} className={`mpanel__side mpanel__side--${side}`}>
            <p className="mpanel__name">{names[side]} <span className="mpanel__corner">{SIDE_LABEL[side]}</span></p>
            {parts[side].length === 0 ? (
              <p className="mpanel__none">{L.noPoints}</p>
            ) : (
              <table className="mpanel__table">
                <thead>
                  <tr>
                    <th>{L.source}</th>
                    <th className="num">{L.earned}</th>
                    <th className="num">
                      {L.current}
                      <HelpTip label={UI_LABELS.help(L.columnsTerm)} align="end">{L.columnsHelp}</HelpTip>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {parts[side].map((p) => (
                    <tr key={p.source}>
                      <td>{SOURCE_LABELS[p.source]}</td>
                      <td className="num">{pts(p.earned)}</td>
                      <td className="num">{pts(p.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ))}
      </div>

      <div className="mpanel__event">
        {selected === null ? (
          <p className="mpanel__hint">{L.pickEvent}</p>
        ) : (
          <>
            <p className="mpanel__evtitle">
              <span className="num">{formatClock((selected.peak_ms ?? selected.start_ms) / 1000, true)}</span>{" "}
              {EVENT_LABELS[selected.type]}
              {selected.possible_contact && <span className="tag tag--amber">{L.possibleContact}</span>}
            </p>
            {effect === null ? (
              <p className="mpanel__none">
                {selected.type === "knockdown" || selected.type === "takedown"
                  ? L.belowThreshold(Math.round(selected.confidence * 100), Math.round(params.min_major_confidence * 100))
                  : L.noPointsType}
              </p>
            ) : (
              <>
                <ul className="mpanel__entries">
                  {effect.entries.map((c) => (
                    <li key={c.contribution_id}>
                      {SOURCE_LABELS[c.source]}: <b className="num">+{pts(c.points)}</b> {L.points}
                    </li>
                  ))}
                </ul>
                <p>
                  {L.totalFor(names[effect.side])} <b className="num">{pts(effect.points)}</b>{" "}
                  {L.atEvent(names[effect.side])} <b className="num">{formatNumber(Math.abs(effect.redDelta), 1)}</b>{" "}
                  {L.raised}{" "}
                  {effectNow ? (
                    <>
                      {L.nowValue(formatClock(tMs / 1000, true))} <b className="num">{pts(effectNow.now)}</b> {L.affects}{" "}
                      <b className="num">{formatNumber(Math.abs(effectNow.redDelta), 1)}</b> {L.affectsEnd}
                    </>
                  ) : (
                    <>{L.notReached}</>
                  )}
                </p>
              </>
            )}
            {Object.keys(selected.measures).length > 0 && (
              <dl className="mpanel__measures">
                {Object.entries(selected.measures).map(([k, v]) => (
                  <div key={k}><dt>{L.measures[k] ?? k}</dt><dd className="num">{formatNumber(v, 2)}</dd></div>
                ))}
              </dl>
            )}
          </>
        )}
      </div>
    </section>
  );
}
