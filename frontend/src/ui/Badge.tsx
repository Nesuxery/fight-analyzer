import type { HTMLAttributes, ReactNode } from "react";
import { cx } from "./cx";

/** Red and blue mean a corner; success, warning and danger a state; anything else is neutral. */
export type BadgeTone = "neutral" | "success" | "warning" | "danger" | "red" | "blue";

/** Small pill label. Soft tone by default; `solid` (white text on the tone) for corner badges over pictures. */
export function Badge({ tone = "neutral", solid = false, icon, className, children, ...rest }:
  { tone?: BadgeTone; solid?: boolean; icon?: ReactNode } & HTMLAttributes<HTMLSpanElement>) {
  return (
    <span {...rest} className={cx("badge", `badge--${tone}`, solid && "badge--solid", className)}>
      {icon}{children}
    </span>
  );
}
