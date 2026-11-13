/**
 * Where a floating bubble (HelpTip) goes in the viewport. DOM-free so the node
 * tests can run it: the caller passes the measured rectangles.
 *
 * The bubble is position: fixed, so it never widens the page or gets clipped
 * by a panel; this keeps it inside the viewport instead.
 */

export interface Box { left: number; top: number; width: number; height: number }

export type BubbleSide = "top" | "bottom";
/** Which edge of the bubble sits on the anchor: start = the bubble grows to the right. */
export type BubbleAlign = "start" | "center" | "end";

export interface BubblePlacement { left: number; top: number; side: BubbleSide }

export interface PlaceOptions {
  side: BubbleSide;
  align: BubbleAlign;
  /** Space between the anchor and the bubble. */
  gap: number;
  /** How far the bubble's edge sits outside the anchor for start and end. */
  inset: number;
  /** Smallest distance from the viewport edges. */
  margin: number;
}

function clamp(value: number, min: number, max: number): number {
  // max < min when the bubble is wider than the viewport: keep its start edge visible
  return Math.max(min, Math.min(value, max));
}

export function placeBubble(anchor: Box, bubble: { width: number; height: number },
                            viewport: { width: number; height: number }, o: PlaceOptions): BubblePlacement {
  const right = anchor.left + anchor.width;
  const preferred = o.align === "start" ? anchor.left - o.inset
    : o.align === "end" ? right + o.inset - bubble.width
    : anchor.left + anchor.width / 2 - bubble.width / 2;
  const left = clamp(preferred, o.margin, viewport.width - o.margin - bubble.width);

  const above = anchor.top - o.gap - bubble.height;
  const below = anchor.top + anchor.height + o.gap;
  const fitsAbove = above >= o.margin;
  const fitsBelow = below + bubble.height <= viewport.height - o.margin;
  let side = o.side;
  if (side === "top" && !fitsAbove && fitsBelow) side = "bottom";
  else if (side === "bottom" && !fitsBelow && fitsAbove) side = "top";
  const top = clamp(side === "top" ? above : below, o.margin, viewport.height - o.margin - bubble.height);
  return { left, top, side };
}
