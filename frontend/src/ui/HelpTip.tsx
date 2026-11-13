import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { cx } from "./cx";
import { IconHelp } from "./icons";
import { placeBubble } from "./placeBubble";
import type { BubbleAlign, BubbleSide } from "./placeBubble";

/** Matches --space-1 and --space-2 in tokens.css. */
const GAP = 4;
const INSET = 8;
const MARGIN = 8;

/**
 * "?" next to a metric or term. The explanation opens on hover, on keyboard
 * focus and on click (touch); Esc closes it (WCAG 1.4.13). It may run over
 * several lines.
 *
 * Closed, the bubble is display: none, so it never takes part in the page
 * layout at any width. Open, it is position: fixed and placed in the viewport
 * (placeBubble.ts): it cannot widen the page or be clipped by a panel.
 */
export function HelpTip({ label, children, side = "top", align = "center" }: {
  /** Accessible name of the button, e.g. "Baskı: açıklama". */
  label: string;
  children: ReactNode;
  /** Preferred side; the bubble flips when there is no room. */
  side?: BubbleSide;
  /** Which edge of the bubble sits on the button: start = the bubble grows to the right. */
  align?: BubbleAlign;
}) {
  const id = useId();
  const [hover, setHover] = useState(false);
  const [pinned, setPinned] = useState(false);
  const open = hover || pinned;
  const buttonRef = useRef<HTMLButtonElement>(null);
  const bubbleRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setHover(false);
      setPinned(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  // Placed before paint, and again while the page scrolls or resizes under it
  useLayoutEffect(() => {
    const button = buttonRef.current;
    const bubble = bubbleRef.current;
    if (!open || !button || !bubble) return;
    const place = () => {
      const a = button.getBoundingClientRect();
      const root = document.documentElement;
      const p = placeBubble(
        { left: a.left, top: a.top, width: a.width, height: a.height },
        { width: bubble.offsetWidth, height: bubble.offsetHeight },
        { width: root.clientWidth, height: root.clientHeight },
        { side, align, gap: GAP, inset: INSET, margin: MARGIN },
      );
      bubble.style.left = `${p.left}px`;
      bubble.style.top = `${p.top}px`;
    };
    place();
    window.addEventListener("scroll", place, { capture: true, passive: true });
    window.addEventListener("resize", place);
    return () => {
      window.removeEventListener("scroll", place, { capture: true });
      window.removeEventListener("resize", place);
    };
  }, [open, side, align]);

  return (
    <span className="helptip" onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
      <button ref={buttonRef} type="button" className="helptip__btn" aria-label={label} aria-describedby={id}
              onFocus={() => setHover(true)}
              onBlur={() => {
                setHover(false);
                setPinned(false);
              }}
              onClick={() => setPinned((v) => !v)}>
        <IconHelp size={16} />
      </button>
      <span ref={bubbleRef} id={id} role="tooltip" className={cx("helptip__bubble", open && "is-open")}>
        {children}
      </span>
    </span>
  );
}
