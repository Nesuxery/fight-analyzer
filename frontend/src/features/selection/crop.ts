/** Square part of the frame shown in a candidate tile (video pixels). */
export interface CropRect {
  x: number;
  y: number;
  size: number;
}

/**
 * Square around a detection box with some room around the person, moved
 * inside the frame; never larger than the frame's shorter side.
 */
export function cropRect(box: { x1: number; y1: number; x2: number; y2: number },
                         frame: { width: number; height: number }, pad = 0.08): CropRect {
  const w = Math.max(1, box.x2 - box.x1);
  const h = Math.max(1, box.y2 - box.y1);
  const size = Math.min(Math.max(w, h) * (1 + 2 * pad), frame.width, frame.height);
  const cx = (box.x1 + box.x2) / 2;
  const cy = (box.y1 + box.y2) / 2;
  return {
    x: Math.min(Math.max(cx - size / 2, 0), frame.width - size),
    y: Math.min(Math.max(cy - size / 2, 0), frame.height - size),
    size,
  };
}
