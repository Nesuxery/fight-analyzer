import { useEffect, useId, useState } from "react";
import type { ReactNode } from "react";
import { cx } from "./cx";
import { IconHelp } from "./icons";

/**
 * "?" next to a metric or term. The explanation opens on hover, on keyboard
 * focus and on click (touch); Esc closes it (WCAG 1.4.13). It may run over
 * several lines; `align` keeps it inside narrow panels.
 */
export function HelpTip({ label, children, side = "top", align = "center" }: {
  /** Accessible name of the button, e.g. "Baskı: açıklama". */
  label: string;
  children: ReactNode;
  side?: "top" | "bottom";
  /** Which edge of the bubble sits on the button: start = the bubble grows to the right. */
  align?: "start" | "center" | "end";
}) {
  const id = useId();
  const [hover, setHover] = useState(false);
  const [pinned, setPinned] = useState(false);
  const open = hover || pinned;

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

  return (
    <span className="helptip" onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
      <button type="button" className="helptip__btn" aria-label={label} aria-describedby={id}
              onFocus={() => setHover(true)}
              onBlur={() => {
                setHover(false);
                setPinned(false);
              }}
              onClick={() => setPinned((v) => !v)}>
        <IconHelp size={16} />
      </button>
      <span id={id} role="tooltip"
            className={cx("helptip__bubble", `helptip__bubble--${side}`, `helptip__bubble--${align}`, open && "is-open")}>
        {children}
      </span>
    </span>
  );
}
