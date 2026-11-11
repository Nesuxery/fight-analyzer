import type { ReactNode } from "react";
import { cx } from "./cx";
import { IconAlert, IconSpinner } from "./icons";

export type EmptyStateTone = "empty" | "loading" | "error";

/** Empty, loading and error presentation of a screen or panel. */
export function EmptyState({ tone = "empty", title, icon, children, action, compact = false }: {
  tone?: EmptyStateTone;
  title: string;
  /** Icon of an empty state (loading and error bring their own). */
  icon?: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div className={cx("state", `state--${tone}`, compact && "state--compact")} role={tone === "error" ? "alert" : "status"}>
      {tone === "loading" && <IconSpinner className="state__icon icon-spin" />}
      {tone === "error" && <IconAlert className="state__icon" />}
      {tone === "empty" && icon && <span className="state__icon state__icon--badge">{icon}</span>}
      <p className="state__title">{title}</p>
      {children && <div className="state__text">{children}</div>}
      {action && <div className="state__action">{action}</div>}
    </div>
  );
}

/** Placeholder block while content loads (pulses gently; still with reduced motion). */
export function Skeleton({ className }: { className?: string }) {
  return <span className={cx("skeleton", className)} aria-hidden="true" />;
}
