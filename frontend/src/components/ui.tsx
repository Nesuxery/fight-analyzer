import type { ReactNode } from "react";
import { IconAlert } from "./icons";

type StateTone = "empty" | "loading" | "error";

/** Shared empty / loading / error presentation. */
export function StateView({ tone, title, children, action, compact = false }: {
  tone: StateTone;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div className={`state state--${tone}${compact ? " state--compact" : ""}`}
         role={tone === "error" ? "alert" : "status"}>
      {tone === "loading" && <span className="spinner" aria-hidden="true" />}
      {tone === "error" && <IconAlert className="state__icon" size={26} />}
      {tone === "empty" && <span className="state__mark" aria-hidden="true" />}
      <p className="state__title">{title}</p>
      {children && <div className="state__text">{children}</div>}
      {action && <div className="state__action">{action}</div>}
    </div>
  );
}

export function DemoBanner() {
  return (
    <div className="demo-banner" role="note">
      <span className="demo-banner__tag">DEMO</span>
      <span>Tasarım önizlemesi: tüm görüntü, istatistik ve olaylar örnektir; gerçek analiz değildir.</span>
    </div>
  );
}

export function DemoTag({ small = false }: { small?: boolean }) {
  return <span className={`demo-tag${small ? " demo-tag--small" : ""}`}>DEMO</span>;
}

export function ProgressBar({ value, tone = "default", label }: {
  value: number | null;
  tone?: "default" | "red" | "blue" | "error";
  label: string;
}) {
  const pct = value === null ? 0 : Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <div className={`bar bar--${tone}`} role="progressbar" aria-label={label}
         aria-valuemin={0} aria-valuemax={100} aria-valuenow={value === null ? undefined : pct}>
      <span className="bar__fill" style={{ width: `${pct}%` }} />
    </div>
  );
}
