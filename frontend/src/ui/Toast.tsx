import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { UI_LABELS } from "../labels";
import { Button } from "./Button";
import { cx } from "./cx";
import { IconAlert, IconCheck, IconClose } from "./icons";

export type ToastTone = "neutral" | "success" | "danger";

interface ToastItem {
  id: number;
  tone: ToastTone;
  message: string;
}

type Push = (toast: { tone?: ToastTone; message: string }) => void;

const ToastContext = createContext<Push | null>(null);
const SHOW_MS = 6000;
const MAX_VISIBLE = 3;

/** Short notifications in a floating stack; errors are announced at once (role="alert"). */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => setItems((list) => list.filter((t) => t.id !== id)), []);
  const push = useCallback<Push>(({ tone = "neutral", message }) => {
    const id = nextId.current++;
    setItems((list) => [...list.slice(-(MAX_VISIBLE - 1)), { id, tone, message }]);
    window.setTimeout(() => dismiss(id), SHOW_MS);
  }, [dismiss]);
  const value = useMemo(() => push, [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toasts" role="region" aria-label={UI_LABELS.notifications} aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={cx("toast", `toast--${t.tone}`)} role={t.tone === "danger" ? "alert" : undefined}>
            {t.tone === "danger" ? <IconAlert size={20} className="toast__icon" />
              : t.tone === "success" ? <IconCheck size={20} className="toast__icon" /> : null}
            <p className="toast__text">{t.message}</p>
            <Button variant="ghost" size="sm" className="btn--icon toast__close" aria-label={UI_LABELS.closeNotification}
                    onClick={() => dismiss(t.id)}>
              <IconClose size={16} />
            </Button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): Push {
  const push = useContext(ToastContext);
  if (!push) throw new Error("useToast must be used inside ToastProvider");
  return push;
}
