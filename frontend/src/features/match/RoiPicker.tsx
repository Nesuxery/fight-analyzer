import { useRef } from "react";
import type { KeyboardEvent, PointerEvent } from "react";
import type { ScreenRect } from "../../contracts/generated";
import { MATCH_LABELS as L } from "../../labels";

const MIN = 0.01;
const DEFAULT: ScreenRect = { x: 0.45, y: 0.86, w: 0.1, h: 0.05 };
const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi);

/** Keep a rectangle (shares of the frame) inside the frame and not smaller than 1 %. */
export function fitRect(r: ScreenRect): ScreenRect {
  const w = clamp(r.w, MIN, 1);
  const h = clamp(r.h, MIN, 1);
  const round = (v: number) => Math.round(v * 10000) / 10000;
  return { x: round(clamp(r.x, 0, 1 - w)), y: round(clamp(r.y, 0, 1 - h)), w: round(w), h: round(h) };
}

/** Keyboard step for the clock rectangle: arrows move it, Alt+arrows resize it, Shift is faster. */
export function nudgeRect(r: ScreenRect | null, key: string, shift: boolean, alt: boolean): ScreenRect | null {
  const step = shift ? 0.02 : 0.005;
  const d = ({ ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] } as
    Record<string, [number, number]>)[key];
  if (!d) return null;
  const base = r ?? DEFAULT;
  return fitRect(alt ? { ...base, w: base.w + d[0], h: base.h + d[1] } : { ...base, x: base.x + d[0], y: base.y + d[1] });
}

/**
 * Drawing surface over the frame: drag to draw the rectangle around the
 * scorebug clock; with the keyboard, arrows move it and Alt+arrows resize it.
 */
export function RoiPicker({ value, onChange }: { value: ScreenRect | null; onChange: (r: ScreenRect) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const start = useRef<{ x: number; y: number } | null>(null);
  const at = (e: PointerEvent) => {
    const b = ref.current?.getBoundingClientRect();
    if (!b || b.width <= 0 || b.height <= 0) return null;
    return { x: clamp((e.clientX - b.left) / b.width, 0, 1), y: clamp((e.clientY - b.top) / b.height, 0, 1) };
  };
  const onDown = (e: PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    start.current = at(e);
  };
  const onMove = (e: PointerEvent<HTMLDivElement>) => {
    const s = start.current;
    const p = at(e);
    if (!s || !p || !e.currentTarget.hasPointerCapture(e.pointerId)) return;
    onChange(fitRect({ x: Math.min(s.x, p.x), y: Math.min(s.y, p.y), w: Math.abs(p.x - s.x), h: Math.abs(p.y - s.y) }));
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const next = nudgeRect(value, e.key, e.shiftKey, e.altKey);
    if (!next) return;
    e.preventDefault();
    onChange(next);
  };
  const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
  return (
    <div ref={ref} className="roi" tabIndex={0} onPointerDown={onDown} onPointerMove={onMove}
         onPointerUp={() => { start.current = null; }} onKeyDown={onKey}
         aria-label={`${L.roi.area}. ${L.roi.hint}`}>
      {value && (
        <span className="roi__rect" aria-hidden="true"
              style={{ left: pct(value.x), top: pct(value.y), width: pct(value.w), height: pct(value.h) }} />
      )}
    </div>
  );
}
