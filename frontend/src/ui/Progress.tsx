import { cx } from "./cx";

/** Thin progress bar in the accent colour; value 0..1, or null when the amount is unknown. */
export function Progress({ value, label, tone = "default", className }: {
  value: number | null;
  label: string;
  tone?: "default" | "danger";
  className?: string;
}) {
  const v = value === null ? null : Math.min(1, Math.max(0, value));
  return (
    <div className={cx("bar", tone === "danger" && "bar--error", className)} role="progressbar" aria-label={label}
         aria-valuemin={0} aria-valuemax={100} aria-valuenow={v === null ? undefined : Math.round(v * 100)}>
      <span className="bar__fill" style={{ transform: `scaleX(${v ?? 0})` }} />
    </div>
  );
}
