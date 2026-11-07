import { useMemo, useState } from "react";
import { DemoTag, StateView } from "../../components/ui";
import type { EventType } from "../../contracts/generated";
import { EVENT_LABELS } from "../../labels";
import type { Side, TimelineEvent } from "../../model/analysis";
import type { Clock } from "../../player/clock";
import { formatClock } from "../../player/clock";

/** Selecting an event jumps this long before its moment, so the build-up is visible. */
export const EVENT_PRE_ROLL_S = 1;

type SideFilter = "all" | Side;

/** Short chip names per event type (list rows use the full EVENT_LABELS). */
const TYPE_CHIPS: Record<EventType, string> = {
  punch: "Yumruk",
  kick: "Tekme",
  knee: "Diz",
  knockdown: "Olası knockdown",
  takedown: "Olası takedown",
  clinch: "Klinç",
  ground_control: "Yer kontrolü",
  stance_change: "Duruş değişimi",
  other: "Diğer",
};
const TYPE_ORDER = Object.keys(TYPE_CHIPS) as EventType[];

export function EventList({ events, clock, time, names, demo, selectedId = null, onSelect, emptyText }: {
  events: TimelineEvent[];
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
  // Types the user switched off; new types (e.g. after a recalculation) are shown.
  const [hidden, setHidden] = useState<ReadonlySet<EventType>>(new Set());
  const present = useMemo(() => TYPE_ORDER.filter((t) => events.some((e) => e.type === t)), [events]);
  const shown = useMemo(
    () => events.filter((e) => !hidden.has(e.type) && (side === "all" || e.side === side)),
    [events, hidden, side],
  );
  // Most recent event that has happened at the current time.
  const currentId = useMemo(() => {
    let id: string | null = null;
    for (const e of shown) if (e.startS <= time) id = e.id;
    return id;
  }, [shown, time]);

  const toggleType = (t: EventType) => setHidden((h) => {
    const next = new Set(h);
    if (next.has(t)) next.delete(t);
    else next.add(t);
    return next;
  });
  const sides: { id: SideFilter; label: string }[] = [
    { id: "all", label: "İki köşe" },
    { id: "red", label: names?.red ?? "Kırmızı" },
    { id: "blue", label: names?.blue ?? "Mavi" },
  ];

  return (
    <section className="events" aria-label="Olay listesi">
      <header className="events__head">
        <h2 className="display display--sm">
          Olaylar {demo && <DemoTag small />}
          <span className="events__count num">{shown.length}/{events.length}</span>
        </h2>
        <div className="events__filters">
          <div className="chips" role="group" aria-label="Köşe filtresi">
            {sides.map((f) => (
              <button key={f.id} type="button" className={`chipbtn chipbtn--${f.id}`} aria-pressed={side === f.id}
                      onClick={() => setSide(f.id)} disabled={events.length === 0}>
                {f.label}
              </button>
            ))}
          </div>
          {present.length > 1 && (
            <div className="chips" role="group" aria-label="Olay türü filtresi">
              {present.map((t) => (
                <button key={t} type="button" className={`chipbtn chipbtn--type chipbtn--${t}`}
                        aria-pressed={!hidden.has(t)} onClick={() => toggleType(t)}>
                  {TYPE_CHIPS[t]}
                  <span className="chipbtn__n num">{events.filter((e) => e.type === t).length}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </header>
      {events.length === 0 ? (
        <StateView tone="empty" title="Olay yok" compact>
          {emptyText ?? "Olay tespiti sonuçları geldiğinde burada zaman sırasıyla listelenir."}
        </StateView>
      ) : shown.length === 0 ? (
        <p className="events__none">Bu filtrede olay yok.</p>
      ) : (
        <ol className="events__list">
          {shown.map((e) => (
            <li key={e.id}>
              <button type="button"
                      className={`evt${e.id === currentId ? " is-current" : ""}${e.significant ? " evt--big" : ""}${e.id === selectedId ? " is-selected" : ""}${e.excluded ? " is-excluded" : ""}`}
                      aria-pressed={onSelect ? e.id === selectedId : undefined}
                      title={`${formatClock(Math.max(0, e.startS - EVENT_PRE_ROLL_S), true)} anına gider (olaydan ${EVENT_PRE_ROLL_S} sn önce)`}
                      onClick={() => {
                        onSelect?.(e.id);
                        clock.seek(Math.max(0, e.startS - EVENT_PRE_ROLL_S));
                      }}>
                <span className="evt__time num">{formatClock(e.startS, true)}</span>
                <span className={`evt__side evt__side--${e.side ?? "none"}`}>
                  {e.side && names ? names[e.side] : "—"}
                </span>
                <span className="evt__type">
                  {EVENT_LABELS[e.type]}
                  {e.tags?.map((t) => (
                    <span key={t.label} className={`tag tag--${t.tone}`} title={t.title}>{t.label}</span>
                  ))}
                  {!e.tags && e.significant && <span className="tag tag--amber">Olası</span>}
                  {e.note && <span className="evt__note">{e.note}</span>}
                </span>
                <span className="evt__conf num" title="Dedektör güveni; doğruluk garantisi değildir">
                  %{Math.round(e.confidence * 100)}
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
