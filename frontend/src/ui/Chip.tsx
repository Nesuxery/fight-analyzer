import type { ButtonHTMLAttributes } from "react";
import { cx } from "./cx";

/** On/off chip for layers and filters (İskelet, Olay efektleri…): a toggle button. */
export function Chip({ pressed, onPressedChange, className, children, ...rest }: {
  pressed: boolean;
  onPressedChange: (next: boolean) => void;
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "type" | "onClick" | "aria-pressed">) {
  return (
    <button type="button" {...rest} className={cx("toggle", className)} aria-pressed={pressed}
            onClick={() => onPressedChange(!pressed)}>
      <span className="toggle__dot" aria-hidden="true" />
      {children}
    </button>
  );
}
