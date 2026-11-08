import { cloneElement, useEffect, useId, useState } from "react";
import type { ReactElement, ReactNode } from "react";
import { cx } from "./cx";

/**
 * Short hint shown on hover and on keyboard focus; Esc hides it (WCAG 1.4.13).
 * With `describes` the hint is the trigger's accessible description; turn it
 * off when the hint only repeats the trigger's name (icon buttons).
 */
export function Tooltip({ content, children, side = "top", describes = true }: {
  content: ReactNode;
  children: ReactElement<{ "aria-describedby"?: string }>;
  side?: "top" | "bottom";
  describes?: boolean;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <span className="tooltip" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}
          onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}>
      {describes ? cloneElement(children, { "aria-describedby": id }) : children}
      <span id={id} role={describes ? "tooltip" : undefined} aria-hidden={describes ? undefined : true}
            className={cx("tooltip__bubble", `tooltip__bubble--${side}`, open && "is-open")}>
        {content}
      </span>
    </span>
  );
}
