import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { SHELL_LABELS } from "../labels";
import { IconCheck, IconMonitor, IconMoon, IconSun } from "../ui/icons";
import { THEME_CHOICES } from "./theme";
import type { ThemeChoice } from "./theme";
import { setThemeChoice, useTheme } from "./useTheme";

const L = SHELL_LABELS.theme;
const ICON = { light: IconSun, dark: IconMoon, system: IconMonitor } as const;

/**
 * Açık · Koyu · Sistem in the top bar: an icon button (sun, moon or screen for
 * the current choice) opening a small radio menu. Arrow keys, Home and End move
 * in the menu, Enter or Space picks, Esc or a click outside closes it.
 */
export function ThemeMenu() {
  const { choice, system } = useTheme();
  const [open, setOpen] = useState(false);
  const [focus, setFocus] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const menuId = useId();
  const checked = THEME_CHOICES.indexOf(choice);

  useEffect(() => {
    if (open) itemRefs.current[focus]?.focus();
  }, [open, focus]);

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    return () => document.removeEventListener("pointerdown", onPointer);
  }, [open]);

  const openAt = (index: number) => {
    setFocus(index);
    setOpen(true);
  };
  const close = () => {
    setOpen(false);
    buttonRef.current?.focus();
  };
  const pick = (next: ThemeChoice) => {
    setThemeChoice(next);
    close();
  };

  const onButtonKey = (e: KeyboardEvent) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    openAt(checked);
  };
  const onMenuKey = (e: KeyboardEvent) => {
    const n = THEME_CHOICES.length;
    const moves: Record<string, number> = { ArrowDown: focus + 1, ArrowUp: focus - 1 + n, Home: 0, End: n - 1 };
    const move = moves[e.key];
    if (move !== undefined) {
      e.preventDefault();
      setFocus(move % n);
    } else if (e.key === "Escape") {
      e.preventDefault();
      close();
    } else if (e.key === "Tab") {
      setOpen(false);
    }
  };

  const Current = ICON[choice];
  const label = L.button(choice === "system" ? `${L.system} (${L.now[system]})` : L[choice]);
  return (
    <div ref={rootRef} className="thememenu">
      <button ref={buttonRef} type="button" className="thememenu__button" aria-haspopup="menu"
              aria-expanded={open} aria-controls={open ? menuId : undefined} aria-label={label} title={label}
              onClick={() => (open ? setOpen(false) : openAt(checked))} onKeyDown={onButtonKey}>
        <Current size={20} />
      </button>
      {open && (
        <div id={menuId} role="menu" aria-label={L.menu} className="thememenu__panel" onKeyDown={onMenuKey}>
          {THEME_CHOICES.map((c, i) => {
            const Icon = ICON[c];
            return (
              <button key={c} ref={(el) => { itemRefs.current[i] = el; }} type="button" role="menuitemradio"
                      aria-checked={c === choice} tabIndex={i === focus ? 0 : -1}
                      className={`thememenu__item${c === choice ? " is-checked" : ""}`} onClick={() => pick(c)}>
                <Icon size={16} className="thememenu__icon" />
                <span>{L[c]}</span>
                {c === "system" && <span className="thememenu__hint">{L.now[system]}</span>}
                {c === choice && <IconCheck size={16} className="thememenu__check" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
