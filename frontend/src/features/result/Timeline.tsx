import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent, RefObject } from "react";
import type { EventType, RoundSource } from "../../contracts/generated";
import { EVENT_LABELS, MATCH_LABELS, ROUND_EDIT_LABELS, TIMELINE_LABELS as T } from "../../labels";
import type { TimelineEvent } from "../../model/analysis";
import type { Clock } from "../../player/clock";
import { formatClock } from "../../player/clock";
import { ticks as makeTicks, useWidth } from "./ticks";

const W = 1000; // SVG user units across the whole duration
const H = 44;
const KEY_COMMIT_MS = 600; // keyboard nudges are saved once the keys rest
const DRAG_PX = 3; // pointer travel before an edge starts to move (a click only focuses it)

/** A round band on the timeline (effective rounds: the user's marks over automatic ones). */
export interface TimelineRound {
  index: number;
  startS: number;
  endS: number;
  source: RoundSource;
}

/** Round editing: an edge moved to a time (seconds), or a round removed. */
export interface RoundEditing {
  onEdge: (index: number, edge: "start" | "end", seconds: number) => void;
  onRemove: (index: number) => void;
}

/**
 * One draggable edge of a round. Pointer: drag along the timeline. Keyboard:
 * arrows move it by 1 s (Shift: 5 s), saved when the keys rest; Delete removes
 * the round. The shown position follows the draft until new rounds arrive.
 */
function EdgeHandle({ r, edge, duration, trackRef, editing }: {
  r: TimelineRound;
  edge: "start" | "end";
  duration: number;
  trackRef: RefObject<HTMLDivElement | null>;
  editing: RoundEditing;
}) {
  const saved = edge === "start" ? r.startS : r.endS;
  const [draft, setDraft] = useState<number | null>(null);
  const timer = useRef<number | null>(null);
  const downX = useRef(0);
  const dragging = useRef(false);
  useEffect(() => setDraft(null), [saved]);
  useEffect(() => () => { if (timer.current !== null) window.clearTimeout(timer.current); }, []);
  const t = draft ?? saved;
  const commit = (value: number) => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = null;
    if (Math.abs(value - saved) > 1e-3) editing.onEdge(r.index, edge, value);
  };
  const fromPointer = (e: PointerEvent) => {
    const b = trackRef.current?.getBoundingClientRect();
    if (!b || b.width <= 0) return t;
    return Math.min(Math.max((e.clientX - b.left) / b.width, 0), 1) * duration;
  };
  const onKey = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      editing.onRemove(r.index);
      return;
    }
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = Math.min(Math.max(t + step * (e.shiftKey ? 5 : 1), 0), duration);
    setDraft(next);
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => commit(next), KEY_COMMIT_MS);
  };
  return (
    <button type="button" className={`tl__edge tl__edge--${edge} tl__edge--${r.source}`}
            style={{ left: `${(Math.min(Math.max(t, 0), duration) / duration) * 100}%` }}
            aria-label={ROUND_EDIT_LABELS.handle(r.index, edge, formatClock(t, true))}
            title={ROUND_EDIT_LABELS.handle(r.index, edge, formatClock(t, true))}
            onPointerDown={(e) => {
              e.stopPropagation();
              e.currentTarget.setPointerCapture(e.pointerId);
              downX.current = e.clientX;
              dragging.current = false;
            }}
            onPointerMove={(e) => {
              if (!e.currentTarget.hasPointerCapture(e.pointerId)) return;
              // a click only focuses the edge: it moves once the pointer really travels
              if (!dragging.current && Math.abs(e.clientX - downX.current) < DRAG_PX) return;
              dragging.current = true;
              setDraft(fromPointer(e));
            }}
            onPointerUp={(e) => {
              if (e.currentTarget.hasPointerCapture(e.pointerId) && dragging.current) commit(fromPointer(e));
              dragging.current = false;
            }}
            onKeyDown={onKey}
            onBlur={() => { if (timer.current !== null && draft !== null) commit(draft); }} />
  );
}

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

/** Grappling transitions (v2 Bölüm 3b): small hollow marks in the lane of the fighter who made them. */
const GRAPPLING_MARKS: EventType[] = ["takedown_attempt", "reversal", "get_up", "submission_attempt"];

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

export function Timeline({ clock, time, events, momentum, names = null, disabled, excluded = [], rounds = [],
                          roundEditing }: {
  clock: Clock;
  time: number;
  events: TimelineEvent[];
  momentum: MomentumSeries | null;
  names?: Record<"red" | "blue", string> | null;
  disabled: boolean;
  /** Excluded parts in effect: [start, end) in seconds and, if known, why. */
  excluded?: [number, number, string?][];
  /** Effective rounds (automatic or marked by the user). */
  rounds?: TimelineRound[];
  /** Given: round edges can be dragged or moved with the keyboard. */
  roundEditing?: RoundEditing;
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
  // a clinch belongs to both fighters: drawn in both lanes, in a neutral tone
  const lane = (side: "red" | "blue") =>
    events.filter((e) => (e.side === side || (e.side === null && e.type === "clinch")) && !e.significant);
  const kinds = new Set(events.map((e) => e.type));

  return (
    <section className="tl" aria-label={T.region}>
      <div className="tl__track">
      <div
        ref={ref}
        className={`tl__body${disabled ? " is-disabled" : ""}`}
        role="slider"
        tabIndex={disabled ? -1 : 0}
        aria-label={T.slider}
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
          ) : <span className="tl__empty">{T.noMomentum}</span>}
          <span className="tl__axis tl__axis--top">{T.axisTop}</span>
          <span className="tl__axis tl__axis--mid">{T.axisMid}</span>
          <span className="tl__axis tl__axis--bottom">{T.axisBottom}</span>
        </div>
        <div className="tl__lane tl__lane--blue">
          {lane("blue").map((e) => <Mark key={e.id} e={e} pct={pct} names={names} />)}
        </div>
        {events.filter((e) => e.significant).map((e) => (
          <span key={e.id} className={`tl__big tl__big--${e.side ?? "none"}${e.excluded ? " is-excluded" : ""}`}
                style={{ left: pct(e.startS) }} title={MARK_TITLE(e, names)} />
        ))}
        {rounds.map((r) => (
          <span key={r.index} className={`tl__round tl__round--${r.source === "manual" ? "manual" : "auto"}`}
                style={{ left: pct(r.startS), width: pct(r.endS - r.startS) }}
                title={T.roundTitle(r.index, formatClock(r.startS), formatClock(r.endS), MATCH_LABELS.source[r.source])}>
            <span className="tl__round-label">R{r.index}</span>
          </span>
        ))}
        {excluded.map(([a, b, reason]) => (
          <span key={a} className="tl__excluded" style={{ left: pct(a), width: pct(b - a) }}
                title={T.excludedTitle(formatClock(a, true), formatClock(b, true), reason ?? null)} />
        ))}
        {!disabled && <span className="tl__head" style={{ left: pct(time) }} aria-hidden="true" />}
      </div>
      {roundEditing && !disabled && (
        <div className="tl__edges">
          {rounds.flatMap((r) => (["start", "end"] as const).map((edge) => (
            <EdgeHandle key={`${r.index}-${edge}`} r={r} edge={edge} duration={duration} trackRef={ref}
                        editing={roundEditing} />
          )))}
        </div>
      )}
      </div>
      <div ref={scaleRef} className="tl__scale num" aria-hidden="true">
        {ticks.map((t) => <span key={t} style={{ left: pct(t) }}>{formatClock(t)}</span>)}
      </div>
      <ul className="tl__legend" aria-label={T.legend}>
        {(kinds.has("elbow") || kinds.has("ground_strike")) ? (
          <li><span className="tl__key tl__key--punch" />{T.handStrikes}</li>
        ) : kinds.has("punch") && <li><span className="tl__key tl__key--punch" />{T.punch}</li>}
        {kinds.has("kick") && <li><span className="tl__key tl__key--kick" />{T.kick}</li>}
        {kinds.has("knee") && <li><span className="tl__key tl__key--knee" />{T.knee}</li>}
        {events.some((e) => e.tags?.some((t) => t.label === "Olası temas")) && (
          <li><span className="tl__key tl__key--contact" />{T.contact}</li>
        )}
        {(kinds.has("knockdown") || kinds.has("takedown")) && <li><span className="tl__key tl__key--big" />{T.big}</li>}
        {(kinds.has("clinch") || kinds.has("ground_control")) && <li><span className="tl__key tl__key--span" />{T.span}</li>}
        {GRAPPLING_MARKS.some((k) => kinds.has(k)) && <li><span className="tl__key tl__key--grappling" />{T.grappling}</li>}
        {gaps.length > 0 && <li><span className="tl__key tl__key--gap" />{T.gap}</li>}
        {excluded.length > 0 && <li><span className="tl__key tl__key--excluded" />{T.excluded}</li>}
        {rounds.some((r) => r.source !== "manual") && <li><span className="tl__key tl__key--round-auto" />{T.roundAuto}</li>}
        {rounds.some((r) => r.source === "manual") && <li><span className="tl__key tl__key--round-manual" />{T.roundManual}</li>}
        <li className="tl__legend-note">{T.curve}</li>
      </ul>
    </section>
  );
}
