/**
 * Where video pixels land on screen. The <video> element is drawn with
 * `object-fit: contain`: the picture keeps its aspect ratio and is centred,
 * leaving bars on the sides (pillarbox) or top and bottom (letterbox) when the
 * box has another shape (fullscreen, resized window). The overlay canvas covers
 * the same box and uses the same fit, so a keypoint at video pixel (x, y) is
 * drawn exactly over that pixel of the picture.
 *
 * No imports on purpose: tests run this file directly with Node.
 */

export interface Fit {
  /** CSS pixels per video pixel. */
  scale: number;
  /** Left/top of the picture inside the box, CSS pixels. */
  offsetX: number;
  offsetY: number;
}

export function containFit(boxW: number, boxH: number, videoW: number, videoH: number): Fit {
  if (boxW <= 0 || boxH <= 0 || videoW <= 0 || videoH <= 0) return { scale: 0, offsetX: 0, offsetY: 0 };
  const scale = Math.min(boxW / videoW, boxH / videoH);
  return { scale, offsetX: (boxW - videoW * scale) / 2, offsetY: (boxH - videoH * scale) / 2 };
}

/** Canvas transform (device pixels) for drawing in video pixel coordinates. */
export function canvasTransform(fit: Fit, dpr: number): [number, number, number, number, number, number] {
  const s = fit.scale * dpr;
  return [s, 0, 0, s, fit.offsetX * dpr, fit.offsetY * dpr];
}

/** Backing-store size of a canvas covering a box, sharp at the device pixel ratio. */
export function backingSize(boxW: number, boxH: number, dpr: number): { width: number; height: number } {
  return { width: Math.max(1, Math.round(boxW * dpr)), height: Math.max(1, Math.round(boxH * dpr)) };
}

/** Video pixel -> CSS pixel inside the box (for DOM labels over the picture). */
export function toBox(fit: Fit, x: number, y: number): { x: number; y: number } {
  return { x: fit.offsetX + x * fit.scale, y: fit.offsetY + y * fit.scale };
}

/**
 * Frame shown at a media time. The analysis copy has a constant frame rate and
 * frame i covers [i / fps, (i + 1) / fps): the presented frame's mediaTime is
 * its start, while `currentTime` (fallback, or after a seek to the middle of a
 * frame) can be anywhere inside it. Flooring with a small tolerance for the
 * decoder's floating-point timestamps gives i in both cases; rounding would
 * jump to the next frame from the middle of an interval.
 */
export function frameAt(mediaTime: number, fps: number, frameCount: number): number {
  const i = Math.floor(mediaTime * fps + 1e-3);
  return Math.min(Math.max(0, i), Math.max(0, frameCount - 1));
}

/** Time that shows frame i: the middle of its interval, robust to rounding in seeks. */
export function frameTime(i: number, fps: number): number {
  return (i + 0.5) / fps;
}
