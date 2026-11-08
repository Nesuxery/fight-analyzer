import type { HTMLAttributes, ReactNode } from "react";
import { cx } from "./cx";

type CardTag = "section" | "div" | "aside" | "article";

/** White panel separated by a 1 px line (no shadow). */
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

export function CardHeader({ title, aside, actions, level = 2, id }: {
  title: ReactNode;
  aside?: ReactNode;
  actions?: ReactNode;
  level?: 2 | 3;
  id?: string;
}) {
  return (
    <header className="card__head">
      {level === 2 ? <h2 id={id} className="card__title">{title}</h2> : <h3 id={id} className="card__title">{title}</h3>}
      {aside && <span className="card__aside">{aside}</span>}
      {actions && <div className="card__actions">{actions}</div>}
    </header>
  );
}

export function Divider({ className }: { className?: string }) {
  return <hr className={cx("divider", className)} />;
}
