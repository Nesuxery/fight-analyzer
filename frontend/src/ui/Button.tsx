import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";
import { cx } from "./cx";
import { Tooltip } from "./Tooltip";

export type ButtonVariant = "primary" | "secondary" | "ghost";
export type ButtonSize = "sm" | "md";

interface Look {
  /** primary: black fill; secondary: outlined; ghost: no frame. */
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Leading icon (16 px in small buttons, 20 px otherwise). */
  icon?: ReactNode;
}

const classes = (variant: ButtonVariant, size: ButtonSize, extra?: string) =>
  cx("btn", `btn--${variant}`, size === "sm" && "btn--sm", extra);

export function Button({ variant = "secondary", size = "md", icon, className, children, ...rest }:
  Look & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "type"> & { type?: "button" | "submit" }) {
  return (
    <button type="button" {...rest} className={classes(variant, size, className)}>
      {icon}{children}
    </button>
  );
}

/** A link that looks like a button (navigation between screens). */
export function ButtonLink({ variant = "secondary", size = "md", icon, className, children, ...rest }:
  Look & AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) {
  return (
    <a {...rest} className={classes(variant, size, className)}>
      {icon}{children}
    </a>
  );
}

/** Square button with only an icon; the label is its accessible name and its tooltip. */
export function IconButton({ label, icon, variant = "ghost", size = "md", className, tooltipSide = "top", ...rest }: {
  label: string;
  icon: ReactNode;
  variant?: Exclude<ButtonVariant, "primary">;
  size?: ButtonSize;
  tooltipSide?: "top" | "bottom";
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "type" | "children" | "aria-label">) {
  return (
    <Tooltip content={label} side={tooltipSide} describes={false}>
      <button type="button" {...rest} aria-label={label} className={classes(variant, size, cx("btn--icon", className))}>
        {icon}
      </button>
    </Tooltip>
  );
}
