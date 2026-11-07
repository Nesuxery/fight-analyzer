import { useRef } from "react";
import type { KeyboardEvent, PointerEvent } from "react";
import type { ReviewPoint, TrackingTimeline } from "../../contracts/generated";
import type { Clock } from "../../player/clock";
import { formatClock } from "../../player/clock";
import { ticks as makeTicks, useWidth } from "./ticks";

const STATE_LABEL = { tracked: "Takipte", occluded: "Örtüşme", uncertain: "Takip belirsiz" } as const;


/** Identity state of both fighters over the whole video, with camera cuts. */
export function TrackingLanes({ clock, time, timeline, names, review }: {
  clock: Clock;
  time: number;
  timeline: TrackingTimeline | null;
  names: { red: string; blue: string };
  review: ReviewPoint[];
}) {
  const ref = useRef<HTMLDivElement>(null);
  const scaleRef = useRef<HTMLDivElement>(null);
  const width = useWidth(scaleRef);
  const frames = Math.max(1, timeline?.frame_count ?? Math.round(clock.duration * clock.fps));
  const pct = (frame: number) => `${(frame / frames) * 100}%`;
  const seekFromPointer = (e: PointerEvent) => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    clock.seek(((e.clientX - rect.left) / rect.width) * clock.duration);
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
  const ticks = makeTicks(clock.duration, width);
  const fighters = [
    { id: "fighter_a", side: "red", name: names.red },
    { id: "fighter_b", side: "blue", name: names.blue },
  ] as const;

  return (
    <section className="tl tlid" aria-label="Takip zaman çizelgesi">
      <div className="tlid__legend" aria-hidden="true">
        <span className="tlid__key tlid__key--tracked">Takipte</span>
        <span className="tlid__key tlid__key--occluded">Örtüşme</span>
        <span className="tlid__key tlid__key--uncertain">Takip belirsiz</span>
        <span className="tlid__key tlid__key--cut">Kamera kesimi</span>
        <span className="tlid__key tlid__key--review">Kontrol önerilir</span>
      </div>
      <div ref={ref} className="tlid__body" role="slider" tabIndex={0} aria-label="Video konumu"
           aria-valuemin={0} aria-valuemax={Math.round(clock.duration)} aria-valuenow={Math.round(time)}
           aria-valuetext={formatClock(time)} onKeyDown={onKey}
           onPointerDown={(e) => {
             e.currentTarget.setPointerCapture(e.pointerId);
             seekFromPointer(e);
           }}
           onPointerMove={(e) => {
             if (e.currentTarget.hasPointerCapture(e.pointerId)) seekFromPointer(e);
           }}>
        {fighters.map((f) => {
          const runs = timeline?.fighters.find((x) => x.fighter_id === f.id)?.runs ?? [];
          return (
            <div key={f.id} className={`tlid__lane tlid__lane--${f.side}`}>
              <span className="tlid__name">{f.name}</span>
              {runs.map((r) => (
                <span key={r.start_frame} className={`tlid__run tlid__run--${r.state}`}
                      style={{ left: pct(r.start_frame), width: pct(r.end_frame - r.start_frame + 1) }}
                      title={`${STATE_LABEL[r.state]} · ${formatClock(r.start_frame / clock.fps, true)}–${formatClock((r.end_frame + 1) / clock.fps, true)}`} />
              ))}
              {review.filter((p) => p.fighter_id === f.id).map((p) => (
                <span key={`${p.frame_index}-${p.kind}`} className="tlid__review" style={{ left: pct(p.frame_index) }} />
              ))}
            </div>
          );
        })}
        {(timeline?.cuts ?? []).map((c) => <span key={c} className="tlid__cut" style={{ left: pct(c) }} />)}
        <span className="tl__head" style={{ left: `${(time / Math.max(clock.duration, 1e-6)) * 100}%` }} aria-hidden="true" />
      </div>
      <div ref={scaleRef} className="tl__scale num" aria-hidden="true">
        {ticks.map((t) => <span key={t} style={{ left: `${(t / Math.max(clock.duration, 1e-6)) * 100}%` }}>{formatClock(t)}</span>)}
      </div>
    </section>
  );
}
