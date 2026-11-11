import type { ReactNode } from "react";
import { cx } from "./cx";

/**
 * Heading of a page section: a 4 × 16 px bar, the title and one line that says
 * what the section is for. The bar takes --accent: brand red, or ink on the
 * Selection and Result screens where red only means the red corner.
 */
export function SectionHeading({ title, description, aside, level = 2, id, className }: {
  title: ReactNode;
  description?: ReactNode;
  /** Shown after the title, e.g. a count. */
  aside?: ReactNode;
  level?: 2 | 3;
  id?: string;
  className?: string;
}) {
  return (
    <header className={cx("sechead", className)}>
      <div className="sechead__row">
        {level === 2
          ? <h2 id={id} className="sechead__title">{title}</h2>
          : <h3 id={id} className="sechead__title sechead__title--sm">{title}</h3>}
        {aside && <span className="sechead__aside num">{aside}</span>}
      </div>
      {description && <p className="sechead__desc">{description}</p>}
    </header>
  );
}
