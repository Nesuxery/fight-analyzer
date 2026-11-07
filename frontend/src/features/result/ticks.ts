import { useEffect, useState } from "react";
import type { RefObject } from "react";

const NICE_STEPS = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600];
const MIN_LABEL_PX = 64; // room for one "00:00" label plus a gap

/** Smallest round step whose labels fit the axis width without overlapping. */
export function tickStep(seconds: number, widthPx: number): number {
  const fit = Math.max(2, Math.floor(widthPx / MIN_LABEL_PX));
  return NICE_STEPS.find((s) => Math.floor(seconds / s) + 1 <= fit) ?? NICE_STEPS[NICE_STEPS.length - 1]!;
}

export function ticks(seconds: number, widthPx: number): number[] {
  const step = tickStep(seconds, widthPx || 320);
  return Array.from({ length: Math.floor(seconds / step) + 1 }, (_, i) => i * step);
}

export function useWidth(ref: RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry?.contentRect.width ?? 0));
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}
