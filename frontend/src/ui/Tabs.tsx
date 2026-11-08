import { useRef } from "react";
import type { KeyboardEvent, ReactNode } from "react";
import { cx } from "./cx";

export interface TabItem<T extends string> {
  id: T;
  label: ReactNode;
}

const tabId = (base: string, id: string) => `${base}-tab-${id}`;
const panelId = (base: string, id: string) => `${base}-panel-${id}`;

/**
 * Underlined tabs (WAI-ARIA tabs pattern): Tab moves into the list, arrow keys,
 * Home and End move between tabs. `id` ties the tabs to their TabPanel.
 */
export function Tabs<T extends string>({ id, label, tabs, value, onChange, className }: {
  id: string;
  label: string;
  tabs: readonly TabItem<T>[];
  value: T;
  onChange: (id: T) => void;
  className?: string;
}) {
  const refs = useRef(new Map<T, HTMLButtonElement>());
  const go = (index: number) => {
    const next = tabs[(index + tabs.length) % tabs.length]!;
    onChange(next.id);
    refs.current.get(next.id)?.focus();
  };
  const onKey = (e: KeyboardEvent) => {
    const i = tabs.findIndex((t) => t.id === value);
    if (e.key === "ArrowRight") go(i + 1);
    else if (e.key === "ArrowLeft") go(i - 1);
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(tabs.length - 1);
    else return;
    e.preventDefault();
  };
  return (
    <div className={cx("tabs", className)} role="tablist" aria-label={label} onKeyDown={onKey}>
      {tabs.map((t) => (
        <button key={t.id} type="button" role="tab" id={tabId(id, t.id)} aria-controls={panelId(id, t.id)}
                aria-selected={t.id === value} tabIndex={t.id === value ? 0 : -1} className="tabs__tab"
                ref={(el) => {
                  if (el) refs.current.set(t.id, el);
                  else refs.current.delete(t.id);
                }}
                onClick={() => onChange(t.id)}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function TabPanel({ id, tab, children, className }: { id: string; tab: string; children: ReactNode; className?: string }) {
  return (
    <div role="tabpanel" id={panelId(id, tab)} aria-labelledby={tabId(id, tab)} tabIndex={0} className={className}>
      {children}
    </div>
  );
}
