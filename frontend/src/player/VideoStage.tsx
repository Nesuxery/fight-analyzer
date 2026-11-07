import { useEffect, useLayoutEffect, useRef } from "react";
import type { ReactNode } from "react";

export type DrawFn = (ctx: CanvasRenderingContext2D, t: number) => void;

interface Props {
  /** Logical frame size the draw function works in (video pixels). */
  frame: { width: number; height: number };
  /** Current time source, read every animation frame. */
  getTime: () => number;
  draw: DrawFn;
  label: string;
  className?: string;
  /** DOM overlays (selection boxes, badges) positioned over the frame. */
  children?: ReactNode;
}

/**
 * 16:9 frame that redraws a canvas whenever the time or the draw function
 * changes. The canvas backing store follows the element size and DPR so
 * overlays stay sharp at any layout width.
 */
export function VideoStage({ frame, getTime, draw, label, className, children }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drawRef = useRef(draw);
  const timeRef = useRef(getTime);
  useLayoutEffect(() => {
    drawRef.current = draw;
    timeRef.current = getTime;
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    let raf = 0;
    let lastT = Number.NaN;
    let lastDraw: DrawFn | null = null;
    let lastW = 0;

    const loop = () => {
      const dpr = window.devicePixelRatio || 1;
      const w = Math.max(1, Math.round(canvas.clientWidth * dpr));
      const h = Math.max(1, Math.round((w * frame.height) / frame.width));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
      const t = timeRef.current();
      if (t !== lastT || drawRef.current !== lastDraw || w !== lastW) {
        ctx.setTransform(w / frame.width, 0, 0, h / frame.height, 0, 0);
        drawRef.current(ctx, t);
        lastT = t;
        lastDraw = drawRef.current;
        lastW = w;
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [frame.width, frame.height]);

  return (
    <div className={`stage ${className ?? ""}`} style={{ aspectRatio: `${frame.width} / ${frame.height}` }}>
      <canvas ref={canvasRef} className="stage__canvas" role="img" aria-label={label} />
      {children}
    </div>
  );
}
