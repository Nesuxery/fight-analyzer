import { useCallback, useEffect, useLayoutEffect, useRef } from "react";
import { useTheme } from "../app/useTheme";
import type { VideoClock } from "./clock";
import { backingSize, canvasTransform, containFit } from "./geometry";
import { drawOverlay } from "./overlay";
import type { OverlayLayers, OverlayScene } from "./overlay";

/**
 * Canvas over a <video> (same box, `object-fit: contain` geometry). It draws
 * the scene of the presented frame once per frame callback of the clock, and
 * again only when the data, the layers, the theme, the size or the pixel density change:
 * a paused video gives a still overlay.
 */
export function OverlayCanvas({ clock, width, height, sceneAt, layers, version }: {
  clock: VideoClock;
  /** Video size in pixels (the coordinate system of the scene). */
  width: number;
  height: number;
  sceneAt: (time: number) => OverlayScene | null;
  layers: OverlayLayers;
  /** Changes when the underlying data changes (e.g. pose chunks arrived). */
  version: unknown;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sceneRef = useRef(sceneAt);
  const layersRef = useRef(layers);
  useLayoutEffect(() => {
    sceneRef.current = sceneAt;
    layersRef.current = layers;
  });

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const box = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const size = backingSize(box.width, box.height, dpr);
    if (canvas.width !== size.width || canvas.height !== size.height) {
      canvas.width = size.width;
      canvas.height = size.height;
    }
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const fit = containFit(box.width, box.height, width, height);
    if (fit.scale <= 0) return;
    ctx.setTransform(...canvasTransform(fit, dpr));
    const scene = sceneRef.current(clock.time);
    if (scene) drawOverlay(ctx, scene, fit, dpr, layersRef.current, { width, height });
  }, [clock, width, height]);

  // Once per presented video frame.
  useEffect(() => clock.onFrame(draw), [clock, draw]);
  // Data, layers or the theme (colours read from tokens) changed while paused.
  const { theme } = useTheme();
  useEffect(draw, [draw, sceneAt, layers, version, theme]);
  // Size, fullscreen and pixel density changes.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const observer = new ResizeObserver(() => draw());
    observer.observe(canvas);
    let media: MediaQueryList | null = null;
    const watchDpr = () => {
      media?.removeEventListener("change", onDpr);
      media = window.matchMedia(`(resolution: ${window.devicePixelRatio || 1}dppx)`);
      media.addEventListener("change", onDpr);
    };
    const onDpr = () => {
      watchDpr();
      draw();
    };
    watchDpr();
    window.addEventListener("resize", draw);
    document.addEventListener("fullscreenchange", draw);
    return () => {
      observer.disconnect();
      media?.removeEventListener("change", onDpr);
      window.removeEventListener("resize", draw);
      document.removeEventListener("fullscreenchange", draw);
    };
  }, [draw]);

  return <canvas ref={canvasRef} className="overlay" aria-hidden="true" />;
}
