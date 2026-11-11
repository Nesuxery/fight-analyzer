import { cx } from "./cx";
import { IconCheck } from "./icons";
import { stepState } from "./stepState";

export interface StepItem {
  id: string;
  label: string;
  /** null: the step cannot be opened yet. */
  href: string | null;
  /** Why a disabled step cannot be opened (read by screen readers). */
  disabledReason?: string;
}

/**
 * Numbered steps across the black top bar. The current step has a red number
 * badge and a red underline; the steps before it show a check mark.
 */
export function Stepper({ label, steps, current, doneLabel }: {
  label: string;
  steps: readonly StepItem[];
  current: string | null;
  /** Read after the name of a finished step (screen readers). */
  doneLabel: string;
}) {
  const currentIndex = steps.findIndex((s) => s.id === current);
  return (
    <nav className="stepper" aria-label={label}>
      <ol className="stepper__list">
        {steps.map((step, i) => {
          const state = stepState(i, currentIndex);
          const body = (
            <>
              <span className="stepper__num">{state === "done" ? <IconCheck size={16} /> : i + 1}</span>
              <span className="stepper__label">{step.label}</span>
              {state === "done" && <span className="sr-only"> ({doneLabel})</span>}
            </>
          );
          return (
            <li key={step.id}>
              {step.href ? (
                <a className={cx("stepper__item", `is-${state}`)} href={step.href}
                   aria-current={state === "active" ? "step" : undefined}>
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
