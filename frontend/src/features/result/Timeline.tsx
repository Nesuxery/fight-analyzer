import { useId, useRef } from "react";
import type { KeyboardEvent, PointerEvent } from "react";
import { EVENT_LABELS } from "../../labels";
import type { TimelineEvent } from "../../model/analysis";
import type { Clock } from "../../player/clock";
import { formatClock } from "../../player/clock";
import { ticks as makeTicks, useWidth } from "./ticks";

const W = 1000; // SVG user units across the whole duration
const H = 44;

/** Red share over time for the curve: times in seconds, shares 0..1. */
export interface MomentumSeries {
  t: number[];
  red: number[];
  /** Samples where a fighter could not be measured (drawn hatched as "veri yetersiz"). */
  insufficient?: boolean[];
}

/** Spans [startS, endS) where the flag is set. */
function spans(t: number[], flags: boolean[], end: number): [number, number][] {
  const out: [number, number][] = [];
  let from: number | null = null;
  flags.forEach((f, i) => {
    if (f && from === null) from = t[i]!;
    if (!f && from !== null) {
      out.push([from, t[i]!]);
      from = null;
    }
  });
  if (from !== null) out.push([from, end]);
  return out;
}

function curvePaths(m: MomentumSeries, duration: number) {
  const x = (t: number) => (t / duration) * W;
  const pts = m.t.map((t, i) => `${x(t).toFixed(1)},${((1 - m.red[i]!) * H).toFixed(2)}`);
  const last = x(m.t[m.t.length - 1] ?? 0).toFixed(1);
  const first = x(m.t[0] ?? 0).toFixed(1);
  return {
    line: `M${pts.join("L")}`,
    // red fills from the top down to the curve, blue from the curve to the bottom:
    // the vertical split at any time is the red/blue share
    red: `M${first},0L${pts.join("L")}L${last},0Z`,
    blue: `M${first},${H}L${pts.join("L")}L${last},${H}Z`,
  };
}

const MARK_TITLE = (e: TimelineEvent, names: Record<"red" | "blue", string> | null) =>
  `${formatClock(e.startS, true)} · ${e.side && names ? `${names[e.side]} · ` : ""}${EVENT_LABELS[e.type]}` +
  (e.tags?.length ? ` (${e.tags.map((t) => t.label).join(", ")})` : "");

function Mark({ e, pct, names }: { e: TimelineEvent; pct: (t: number) => string; names: Record<"red" | "blue", string> | null }) {
  const span = e.type === "clinch" || e.type === "ground_control";
  const style = span
    ? { left: pct(e.startS), width: `max(3px, ${pct(e.endS - e.startS)})` }
    : { left: pct(e.startS) };
  const contact = e.tags?.some((t) => t.label === "Olası temas");
  return (
    <span className={`tl__mark tl__mark--${e.type}${contact ? " tl__mark--contact" : ""}${e.excluded ? " is-excluded" : ""}`}
          style={style} title={MARK_TITLE(e, names)} />
  );
}

export function Timeline({ clock, time, events, momentum, names = null, disabled, excluded = [], rounds = [] }: {
  clock: Clock;
  time: number;
  events: TimelineEvent[];
  momentum: MomentumSeries | null;
  names?: Record<"red" | "blue", string> | null;
  disabled: boolean;
  /** Parts excluded by the user, [start, end) in seconds. */
  excluded?: [number, number][];
  /** Rounds marked by the user. */
  rounds?: { number: number; startS: number; endS: number }[];
}) {
  const ref = useRef<HTMLDivElement>(null);
  const scaleRef = useRef<HTMLDivElement>(null);
  const hatchId = `tl-hatch-${useId().replace(/[^\w-]/g, "")}`;
  const width = useWidth(scaleRef);
  const duration = clock.duration || 1;
  const pct = (t: number) => `${(Math.min(Math.max(t, 0), duration) / duration) * 100}%`;

  const seekFromPointer = (e: PointerEvent) => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect || rect.width <= 0) return;
    const f = Math.min(Math.max((e.clientX - rect.left) / rect.width, 0), 1);
    clock.seek(f * clock.duration);
  };
  const onKey = (e: KeyboardEvent) => {
    const step = e.shiftKey ? 5 : 1;
    if (e.key === "ArrowRight") clock.skip(step);
    else if (e.key === "ArrowLeft") clock.skip(-step);
    else if (e.key === "Home") clock.seek(0);
    else if (e.key === "End") clock.seek(clock.duration);
    else return;
    e.preventDefault();
  };

  const curve = momentum && momentum.t.length > 1 ? curvePaths(momentum, duration) : null;
  const gaps = momentum?.insufficient ? spans(momentum.t, momentum.insufficient, duration) : [];
  const ticks = makeTicks(clock.duration, width);
  const lane = (side: "red" | "blue") => events.filter((e) => e.side === side && !e.significant);
  const kinds = new Set(events.map((e) => e.type));

  return (
    <section className="tl" aria-label="Zaman çizelgesi">
      <div
        ref={ref}
        className={`tl__body${disabled ? " is-disabled" : ""}`}
        role="slider"
        tabIndex={disabled ? -1 : 0}
        aria-label="Video konumu"
        aria-disabled={disabled}
        aria-valuemin={0}
        aria-valuemax={Math.round(clock.duration)}
        aria-valuenow={Math.round(time)}
        aria-valuetext={formatClock(time)}
        onKeyDown={disabled ? undefined : onKey}
        onPointerDown={disabled ? undefined : (e) => {
          e.currentTarget.setPointerCapture(e.pointerId);
          seekFromPointer(e);
        }}
        onPointerMove={disabled ? undefined : (e) => {
          if (e.currentTarget.hasPointerCapture(e.pointerId)) seekFromPointer(e);
        }}
      >
        <div className="tl__lane tl__lane--red">
          {lane("red").map((e) => <Mark key={e.id} e={e} pct={pct} names={names} />)}
        </div>
        <div className="tl__curve" aria-hidden="true">
          {curve ? (
            <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
              <defs>
                <pattern id={hatchId} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                  <rect width="2.5" height="6" className="tl__hatch" />
                </pattern>
              </defs>
              <path d={curve.red} className="tl__area tl__area--red" />
              <path d={curve.blue} className="tl__area tl__area--blue" />
              {gaps.map(([a, b]) => (
                <rect key={a} x={(a / duration) * W} width={Math.max(1, ((b - a) / duration) * W)} y="0" height={H}
                      fill={`url(#${hatchId})`} className="tl__gap" />
              ))}
              <line x1="0" x2={W} y1={H / 2} y2={H / 2} className="tl__midline" />
              <path d={curve.line} className="tl__line" />
            </svg>
          ) : <span className="tl__empty">Momentum verisi yok</span>}
          <span className="tl__axis tl__axis--top">%100 kırmızı</span>
          <span className="tl__axis tl__axis--mid">%50</span>
          <span className="tl__axis tl__axis--bottom">%100 mavi</span>
        </div>
        <div className="tl__lane tl__lane--blue">
          {lane("blue").map((e) => <Mark key={e.id} e={e} pct={pct} names={names} />)}
        </div>
        {events.filter((e) => e.significant).map((e) => (
          <span key={e.id} className={`tl__big tl__big--${e.side ?? "none"}${e.excluded ? " is-excluded" : ""}`}
                style={{ left: pct(e.startS) }} title={MARK_TITLE(e, names)} />
        ))}
        {rounds.map((r) => (
          <span key={r.number} className="tl__round" style={{ left: pct(r.startS), width: pct(r.endS - r.startS) }}
                title={`${r.number}. raund ${formatClock(r.startS)}–${formatClock(r.endS)}`}>
            <span className="tl__round-label">R{r.number}</span>
          </span>
        ))}
        {excluded.map(([a, b]) => (
          <span key={a} className="tl__excluded" style={{ left: pct(a), width: pct(b - a) }}
                title={`Dışlanan bölüm ${formatClock(a, true)}–${formatClock(b, true)}`} />
        ))}
        {!disabled && <span className="tl__head" style={{ left: pct(time) }} aria-hidden="true" />}
      </div>
      <div ref={scaleRef} className="tl__scale num" aria-hidden="true">
        {ticks.map((t) => <span key={t} style={{ left: pct(t) }}>{formatClock(t)}</span>)}
      </div>
      <ul className="tl__legend" aria-label="Zaman çizelgesi işaretleri">
        {kinds.has("punch") && <li><span className="tl__key tl__key--punch" />Yumruk</li>}
        {kinds.has("kick") && <li><span className="tl__key tl__key--kick" />Tekme</li>}
        {kinds.has("knee") && <li><span className="tl__key tl__key--knee" />Diz</li>}
        {events.some((e) => e.tags?.some((t) => t.label === "Olası temas")) && (
          <li><span className="tl__key tl__key--contact" />Olası temas</li>
        )}
        {(kinds.has("knockdown") || kinds.has("takedown")) && <li><span className="tl__key tl__key--big" />Olası büyük olay</li>}
        {(kinds.has("clinch") || kinds.has("ground_control")) && <li><span className="tl__key tl__key--span" />Klinç / yer kontrolü</li>}
        {gaps.length > 0 && <li><span className="tl__key tl__key--gap" />Veri yetersiz</li>}
        {excluded.length > 0 && <li><span className="tl__key tl__key--excluded" />Dışlanan bölüm</li>}
        <li className="tl__legend-note">Eğri: deneysel momentum payı (üst kırmızı, alt mavi)</li>
      </ul>
    </section>
  );
}
