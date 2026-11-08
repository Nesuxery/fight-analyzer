import { useRef } from "react";
import type { KeyboardEvent } from "react";
import { cx } from "./cx";

export interface Segment<T extends string> {
  value: T;
  label: string;
  /** With links the control navigates (e.g. Analiz / Demo); without, it is a radio group. */
  href?: string;
}

export function SegmentedControl<T extends string>({ label, options, value, onChange }: {
  label: string;
  options: readonly Segment<T>[];
  value: T;
  onChange?: (value: T) => void;
}) {
  const refs = useRef(new Map<T, HTMLButtonElement>());

  if (options.every((o) => o.href)) {
    return (
      <nav className="segmented" aria-label={label}>
        {options.map((o) => (
          <a key={o.value} href={o.href} className={cx("segmented__item", o.value === value && "is-active")}
             aria-current={o.value === value ? "page" : undefined}>
            {o.label}
          </a>
        ))}
      </nav>
    );
  }

  const move = (e: KeyboardEvent) => {
    const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const i = options.findIndex((o) => o.value === value);
    const next = options[(i + step + options.length) % options.length]!;
    onChange?.(next.value);
    refs.current.get(next.value)?.focus();
  };

  return (
    <div className="segmented" role="radiogroup" aria-label={label} onKeyDown={move}>
      {options.map((o) => (
        <button key={o.value} type="button" role="radio" aria-checked={o.value === value}
                tabIndex={o.value === value ? 0 : -1}
                ref={(el) => {
                  if (el) refs.current.set(o.value, el);
                  else refs.current.delete(o.value);
                }}
                className={cx("segmented__item", o.value === value && "is-active")}
                onClick={() => onChange?.(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
