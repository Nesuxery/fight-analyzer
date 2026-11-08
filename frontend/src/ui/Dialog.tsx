import { useEffect, useId, useRef } from "react";
import type { ReactNode } from "react";

/**
 * Modal dialog on the native <dialog>: the browser keeps focus inside it,
 * Esc closes it and focus returns to where it was. A click on the backdrop
 * closes it too. Put the safe action first so it receives the focus.
 */
export function Dialog({ open, onClose, title, children, actions }: {
  open: boolean;
  onClose: () => void;
  title: string;
  children?: ReactNode;
  actions: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const bodyId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog ref={ref} className="dialog" aria-labelledby={titleId} aria-describedby={children ? bodyId : undefined}
            onCancel={(e) => {
              e.preventDefault();
              onClose();
            }}
            onClick={(e) => {
              if (e.target === e.currentTarget) onClose();
            }}>
      <div className="dialog__panel">
        <h2 id={titleId} className="dialog__title">{title}</h2>
        {children && <div id={bodyId} className="dialog__body">{children}</div>}
        <div className="dialog__actions">{actions}</div>
      </div>
    </dialog>
  );
}
