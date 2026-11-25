import { useMemo, useState } from "react";
import { DemoTag, EmptyState } from "../../ui";
import type { EventType, StrikeOutcome } from "../../contracts/generated";
import {
  DAMAGE_LABELS as D,
  EVENT_LABELS,
  EVENT_LIST_LABELS as L,
  EVENT_TAG_LABELS,
  EXCLUSION_LABELS,
  SIDE_LABEL,
  STRIKE_LABELS as S,
} from "../../labels";
import type { DamageView, Side, TimelineEvent } from "../../model/analysis";
import type { Clock } from "../../player/clock";
import { formatClock } from "../../player/clock";

/** Selecting an event jumps this long before its moment, so the build-up is visible. */
export const EVENT_PRE_ROLL_S = 1;

type SideFilter = "all" | Side;
type Row = { kind: "event"; at: number; e: TimelineEvent } | { kind: "damage"; at: number; d: DamageView };

const TYPE_ORDER = Object.keys(L.chips) as EventType[];
const OUTCOMES: StrikeOutcome[] = ["landed", "blocked", "missed", "unknown"];
const OUTCOME_TONE: Record<StrikeOutcome, string> = { landed: "ok", blocked: "muted", missed: "muted", unknown: "muted" };

function StrikeTags({ e }: { e: TimelineEvent }) {
  if (!e.outcome) return null;
  return (
    <>
      <span className={`tag tag--${OUTCOME_TONE[e.outcome]}`} title={S.outcomeHelp[e.outcome]}>{S.outcome[e.outcome]}</span>
      {e.zone && <span className="tag tag--plain" title={S.zoneHelp}>{S.zone[e.zone]}</span>}
      {e.significantStrike && <span className="tag tag--plain" title={S.significantHelp}>{S.significant}</span>}
    </>
  );
}

export function EventList({ events, damage = [], clock, time, names, demo, selectedId = null, onSelect, emptyText }: {
  events: TimelineEvent[];
  /** Damage signals (real analyses only), listed in time order with the events. */
  damage?: DamageView[];
  clock: Clock;
  time: number;
  names: Record<Side, string> | null;
  demo: boolean;
  /** Selected event (its momentum effect is explained elsewhere). */
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  emptyText?: string;
}) {
  const [side, setSide] = useState<SideFilter>("all");
  // Types and outcomes the user switched off; new ones (e.g. after a recalculation) are shown.
  const [hidden, setHidden] = useState<ReadonlySet<EventType>>(new Set());
  const [hiddenOutcomes, setHiddenOutcomes] = useState<ReadonlySet<StrikeOutcome>>(new Set());
  const [hideDamage, setHideDamage] = useState(false);
  const present = useMemo(() => TYPE_ORDER.filter((t) => events.some((e) => e.type === t)), [events]);
  const outcomes = useMemo(() => OUTCOMES.filter((o) => events.some((e) => e.outcome === o)), [events]);
  const all = useMemo<Row[]>(() => [
    ...events.map((e) => ({ kind: "event" as const, at: e.startS, e })),
    ...damage.map((d) => ({ kind: "damage" as const, at: d.startS, d })),
  ].sort((a, b) => a.at - b.at), [events, damage]);
  const shown = useMemo(() => all.filter((r) => {
    if (r.kind === "damage") return !hideDamage && (side === "all" || r.d.side === side);
    const e = r.e;
    return !hidden.has(e.type) && (!e.outcome || !hiddenOutcomes.has(e.outcome)) && (side === "all" || e.side === side);
  }), [all, hidden, hiddenOutcomes, hideDamage, side]);
  const rowId = (r: Row) => (r.kind === "event" ? r.e.id : r.d.id);
  // Most recent row that has happened at the current time.
  const currentId = useMemo(() => {
    let id: string | null = null;
    for (const r of shown) if (r.at <= time) id = rowId(r);
    return id;
  }, [shown, time]);

  const toggle = <T,>(set: (f: (h: ReadonlySet<T>) => ReadonlySet<T>) => void, v: T) => set((h) => {
    const next = new Set(h);
    if (next.has(v)) next.delete(v);
    else next.add(v);
    return next;
  });
  const sides: { id: SideFilter; label: string }[] = [
    { id: "all", label: L.bothCorners },
    { id: "red", label: names?.red ?? SIDE_LABEL.red },
    { id: "blue", label: names?.blue ?? SIDE_LABEL.blue },
  ];
  const seek = (at: number, id: string) => {
    onSelect?.(id);
    clock.seek(Math.max(0, at - EVENT_PRE_ROLL_S));
  };
  const total = events.length + damage.length;

  return (
    <section className="events" aria-label={L.region}>
      <header className="events__head">
        <h2 className="display display--sm">
          {L.title} {demo && <DemoTag small />}
          <span className="events__count num">{shown.length}/{total}</span>
        </h2>
        <div className="events__filters">
          <div className="chips" role="group" aria-label={L.cornerFilter}>
            {sides.map((f) => (
              <button key={f.id} type="button" className={`chipbtn chipbtn--${f.id}`} aria-pressed={side === f.id}
                      onClick={() => setSide(f.id)} disabled={total === 0}>
                {f.label}
              </button>
            ))}
          </div>
          {(present.length > 1 || damage.length > 0) && (
            <div className="chips" role="group" aria-label={L.typeFilter}>
              {present.map((t) => (
                <button key={t} type="button" className={`chipbtn chipbtn--type chipbtn--${t}`}
                        aria-pressed={!hidden.has(t)} onClick={() => toggle(setHidden, t)}>
                  {L.chips[t]}
                  <span className="chipbtn__n num">{events.filter((e) => e.type === t).length}</span>
                </button>
              ))}
              {damage.length > 0 && (
                <button type="button" className="chipbtn chipbtn--type chipbtn--damage" aria-pressed={!hideDamage}
                        onClick={() => setHideDamage((v) => !v)}>
                  {L.damageChip}
                  <span className="chipbtn__n num">{damage.length}</span>
                </button>
              )}
            </div>
          )}
          {outcomes.length > 1 && (
            <div className="chips" role="group" aria-label={L.outcomeFilter}>
              {outcomes.map((o) => (
                <button key={o} type="button" className="chipbtn chipbtn--type" aria-pressed={!hiddenOutcomes.has(o)}
                        title={S.outcomeHelp[o]} onClick={() => toggle(setHiddenOutcomes, o)}>
                  {S.outcome[o]}
                  <span className="chipbtn__n num">{events.filter((e) => e.outcome === o).length}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </header>
      {total === 0 ? (
        <EmptyState tone="empty" title={L.emptyTitle} compact>
          {emptyText ?? L.emptyText}
        </EmptyState>
      ) : shown.length === 0 ? (
        <p className="events__none">{L.noneInFilter}</p>
      ) : (
        <ol className="events__list">
          {shown.map((r) => {
            const id = rowId(r);
            const state = `${id === currentId ? " is-current" : ""}${id === selectedId ? " is-selected" : ""}`;
            const title = L.seekTitle(formatClock(Math.max(0, r.at - EVENT_PRE_ROLL_S), true), EVENT_PRE_ROLL_S);
            if (r.kind === "damage") {
              const d = r.d;
              return (
                <li key={id}>
                  <button type="button" className={`evt evt--damage${state}${d.excluded ? " is-excluded" : ""}`}
                          aria-pressed={onSelect ? id === selectedId : undefined} title={title}
                          onClick={() => seek(d.startS, id)}>
                    <span className="evt__time num">{formatClock(d.startS, true)}</span>
                    <span className={`evt__side evt__side--${d.side}`}>{names ? names[d.side] : SIDE_LABEL[d.side]}</span>
                    <span className="evt__type">
                      {D.row(D.types[d.type], names ? names[d.target] : SIDE_LABEL[d.target])}
                      <span className="tag tag--amber" title={`${D.help[d.type]} ${D.estimateHelp}`}>{D.estimate}</span>
                      {d.kind === "cumulative" && <span className="tag tag--muted">{D.cumulative}</span>}
                      {d.inferred && <span className="tag tag--muted" title={D.inferredHelp}>{D.inferred}</span>}
                      {d.uncertain && <span className="tag tag--amber">{EVENT_TAG_LABELS.unattributed}</span>}
                      {d.excluded && <span className="tag tag--muted">{EXCLUSION_LABELS.excludedTag}</span>}
                    </span>
                    <span className="evt__conf num" title={D.confidenceTitle}>%{Math.round(d.confidence * 100)}</span>
                  </button>
                </li>
              );
            }
            const e = r.e;
            return (
              <li key={id}>
                <button type="button"
                        className={`evt${e.significant ? " evt--big" : ""}${state}${e.excluded ? " is-excluded" : ""}`}
                        aria-pressed={onSelect ? id === selectedId : undefined} title={title}
                        onClick={() => seek(e.startS, id)}>
                  <span className="evt__time num">{formatClock(e.startS, true)}</span>
                  <span className={`evt__side evt__side--${e.side ?? "none"}`}>
                    {e.side && names ? names[e.side] : "—"}
                  </span>
                  <span className="evt__type">
                    {EVENT_LABELS[e.type]}
                    <StrikeTags e={e} />
                    {e.inferred && <span className="tag tag--muted" title={EVENT_TAG_LABELS.inferredHelp}>{EVENT_TAG_LABELS.inferred}</span>}
                    {e.tags?.map((t) => (
                      <span key={t.label} className={`tag tag--${t.tone}`} title={t.title}>{t.label}</span>
                    ))}
                    {!e.tags && e.significant && <span className="tag tag--amber">{L.possible}</span>}
                    {e.note && <span className="evt__note">{e.note}</span>}
                  </span>
                  <span className="evt__conf num" title={L.confidenceTitle}>%{Math.round(e.confidence * 100)}</span>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
