import { cx } from "./cx";

export interface StepItem {
  id: string;
  label: string;
  /** null: the step cannot be opened yet. */
  href: string | null;
  /** Why a disabled step cannot be opened (read by screen readers). */
  disabledReason?: string;
}

/** Numbered steps across the top bar; the current one is underlined in black. */
export function Stepper({ label, steps, current }: { label: string; steps: readonly StepItem[]; current: string | null }) {
  return (
    <nav className="stepper" aria-label={label}>
      <ol className="stepper__list">
        {steps.map((step, i) => {
          const active = step.id === current;
          const body = (
            <>
              <span className="stepper__num">{i + 1}</span>
              <span className="stepper__label">{step.label}</span>
            </>
          );
          return (
            <li key={step.id}>
              {step.href ? (
                <a className={cx("stepper__item", active && "is-active")} href={step.href}
                   aria-current={active ? "step" : undefined}>
                  {body}
                </a>
              ) : (
                <span className="stepper__item is-disabled" aria-disabled="true" title={step.disabledReason}>
                  {body}
                  {step.disabledReason && <span className="sr-only"> ({step.disabledReason})</span>}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
