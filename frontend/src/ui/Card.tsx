import type { HTMLAttributes, ReactNode } from "react";
import { cx } from "./cx";

type CardTag = "section" | "div" | "aside" | "article";

/** White panel: a 1 px border and a very light shadow (--shadow-card). */
export function Card({ tag = "section", className, children, ...rest }:
  { tag?: CardTag } & HTMLAttributes<HTMLElement>) {
  const props = { ...rest, className: cx("card", className) };
  switch (tag) {
    case "div": return <div {...props}>{children}</div>;
    case "aside": return <aside {...props}>{children}</aside>;
    case "article": return <article {...props}>{children}</article>;
    default: return <section {...props}>{children}</section>;
  }
}

/** Header of a card; the line under it separates it from the content. */
export function CardHeader({ title, description, aside, actions, level = 2, id }: {
  title: ReactNode;
  /** One line under the title saying what the card shows. */
  description?: ReactNode;
  aside?: ReactNode;
  actions?: ReactNode;
  level?: 2 | 3;
  id?: string;
}) {
  return (
    <header className="card__head">
      <div className="card__heading">
        {level === 2 ? <h2 id={id} className="card__title">{title}</h2> : <h3 id={id} className="card__title">{title}</h3>}
        {description && <p className="card__desc">{description}</p>}
      </div>
      {aside && <span className="card__aside">{aside}</span>}
      {actions && <div className="card__actions">{actions}</div>}
    </header>
  );
}

export function Divider({ className }: { className?: string }) {
  return <hr className={cx("divider", className)} />;
}
