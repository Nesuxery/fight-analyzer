import type { ReactNode } from "react";
import { IconCheck, IconChevronLeft, IconChevronRight } from "../../components/icons";
import { NOT_IN_VIEW } from "../../model/analysis";
import type { Assignment, Detection, Side } from "../../model/analysis";
import { SIDE_LABEL } from "../../theme";

interface LayoutProps {
  title: ReactNode;
  picks: Assignment;
  onPick?: (next: Assignment) => void;
  detections: Detection[];
  frame: { width: number; height: number };
  stage: (boxes: ReactNode) => ReactNode;
  candidateLabel: string;
  onPrev?: () => void;
  onNext?: () => void;
  onConfirm?: () => void;
  problem?: string | null;
  /** Extra navigation (e.g. frame steps) next to the candidate arrows. */
  navExtra?: ReactNode;
  /** Extra content in the side panel (names, earlier selections...). */
  extra?: ReactNode;
  confirmLabel?: string;
  busy?: boolean;
  /** Offer "not in the picture on this frame" for a corner (corrections on close-ups). */
  allowNotInView?: boolean;
}

export function SelectionLayout(p: LayoutProps) {
  const next: Side | null = p.picks.red === null ? "red" : p.picks.blue === null ? "blue" : null;
  const sideOf = (id: string): Side | null =>
    p.picks.red === id ? "red" : p.picks.blue === id ? "blue" : null;

  const toggle = (id: string) => {
    if (!p.onPick) return;
    const side = sideOf(id);
    if (side) p.onPick({ ...p.picks, [side]: null });
    else if (next) p.onPick({ ...p.picks, [next]: id });
  };

  // Number people left to right; render larger boxes first so a smaller box
  // overlapping a larger one stays clickable on top.
  const number = new Map([...p.detections].sort((a, b) => a.x1 - b.x1).map((d, i) => [d.personId, i + 1]));
  const area = (d: Detection) => (d.x2 - d.x1) * (d.y2 - d.y1);
  const boxes = [...p.detections].sort((a, b) => area(b) - area(a)).map((d) => {
    const side = sideOf(d.personId);
    const style = {
      left: `${(d.x1 / p.frame.width) * 100}%`,
      top: `${(d.y1 / p.frame.height) * 100}%`,
      width: `${((d.x2 - d.x1) / p.frame.width) * 100}%`,
      height: `${((d.y2 - d.y1) / p.frame.height) * 100}%`,
    };
    const label = side ? SIDE_LABEL[side].toLocaleUpperCase("tr-TR") : `Kişi ${number.get(d.personId)}`;
    return (
      <button key={d.personId} type="button" style={style}
              className={`pick${side ? ` pick--${side}` : ""}${!side && next ? ` pick--next-${next}` : ""}`}
              aria-pressed={side !== null}
              aria-label={`${label}, tespit güveni yüzde ${Math.round(d.confidence * 100)}${side ? ", seçimi kaldırmak için tıklayın" : ""}`}
              disabled={!side && !next}
              onClick={() => toggle(d.personId)}>
        <span className="pick__tag">{label} <span className="num">{Math.round(d.confidence * 100)}%</span></span>
      </button>
    );
  });

  const ready = p.picks.red !== null && p.picks.blue !== null &&
    !(p.picks.red === NOT_IN_VIEW && p.picks.blue === NOT_IN_VIEW);
  return (
    <div className="select">
      <section className="card select__main" aria-label="Aday kare">
        <header className="card__head">
          <h2 className="display display--sm">{p.title}</h2>
          <div className="select__nav">
            <button type="button" className="btn btn--icon" onClick={p.onPrev} disabled={!p.onPrev}
                    aria-label="Önceki aday kare"><IconChevronLeft /></button>
            <span className="num card__aside">{p.candidateLabel}</span>
            <button type="button" className="btn btn--icon" onClick={p.onNext} disabled={!p.onNext}
                    aria-label="Sonraki aday kare"><IconChevronRight /></button>
            {p.navExtra}
          </div>
        </header>
        {p.stage(boxes)}
        <p className="select__hint">
          Dövüşçülerin net göründüğü bir kare seçin. Hakem ve seyirciler seçilmemelidir; seçimi kaldırmak için kutuya yeniden tıklayın.
        </p>
      </section>

      <aside className="card select__side" aria-label="Seçim adımları">
        <ol className="pickflow">
          {(["red", "blue"] as const).map((side, i) => {
            const chosen = p.picks[side] !== null;
            const absent = p.picks[side] === NOT_IN_VIEW;
            const active = next === side;
            return (
              <li key={side} className={`pickflow__item pickflow__item--${side}${active ? " is-active" : ""}${chosen ? " is-done" : ""}`}>
                <span className="pickflow__num">{chosen ? <IconCheck size={14} /> : i + 1}</span>
                <div>
                  <p className="pickflow__title">{SIDE_LABEL[side]} köşe</p>
                  <p className="pickflow__text">
                    {absent ? "Bu karede görüntüde yok" : chosen ? "Seçildi"
                      : active ? "Kare üzerinde dövüşçüye tıklayın" : "Sırada"}
                  </p>
                  {p.allowNotInView && p.onPick && (active || absent) && (
                    <button type="button" className="linkbtn pickflow__absent"
                            onClick={() => p.onPick?.({ ...p.picks, [side]: absent ? null : NOT_IN_VIEW })}>
                      {absent ? "Geri al" : "Bu karede görünmüyor"}
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
        {p.extra}
        {p.problem && <div className="alert" role="alert">{p.problem}</div>}
        <div className="select__actions">
          <button type="button" className="btn btn--primary" disabled={!ready || !p.onConfirm || p.busy}
                  onClick={p.onConfirm}>
            {p.busy ? "Gönderiliyor…" : (p.confirmLabel ?? "Onayla ve devam et")}
          </button>
          <button type="button" className="btn btn--ghost" disabled={!p.onPick || (!p.picks.red && !p.picks.blue)}
                  onClick={() => p.onPick?.({ red: null, blue: null })}>
            Seçimi sıfırla
          </button>
        </div>
      </aside>
    </div>
  );
}
