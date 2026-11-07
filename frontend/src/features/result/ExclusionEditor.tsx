import { useState } from "react";
import { api } from "../../api/client";
import type { ExcludedSegment, ExclusionReason } from "../../contracts/generated";
import type { Clock } from "../../player/clock";
import { formatClock } from "../../player/clock";

export const REASON_LABELS: Record<ExclusionReason, string> = {
  replay: "Tekrar",
  slow_motion: "Ağır çekim",
  break: "Ara / grafik",
  other: "Diğer",
};

/** Marking parts that are not live fight time (replays cannot be detected automatically). */
export function ExclusionEditor({ jobId, frame, fps, frameCount, saved, clock, onSaved }: {
  jobId: string;
  /** Presented frame. */
  frame: number;
  fps: number;
  frameCount: number;
  /** Excluded parts stored for the analysis. */
  saved: ExcludedSegment[];
  clock: Clock;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [start, setStart] = useState<number | null>(null);
  const [end, setEnd] = useState<number | null>(null);
  const [reason, setReason] = useState<ExclusionReason>("replay");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const at = (f: number) => formatClock(f / fps, true);

  const save = (segments: ExcludedSegment[]) => {
    setBusy(true);
    setProblem(null);
    api.setExclusions(jobId, { segments })
      .then(() => {
        setStart(null);
        setEnd(null);
        setOpen(false);
        onSaved();
      }, (e: unknown) => setProblem(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  };
  const add = () => {
    if (start === null || end === null) return;
    save([...saved, { start_frame: Math.min(start, end), end_frame: Math.min(Math.max(start, end), frameCount - 1),
                      reason, note: null }]);
  };

  return (
    <section className="excl" aria-label="Dışlanan bölümler">
      <div className="excl__row">
        <span className="excl__title">Dışlanan bölümler</span>
        {saved.length === 0 && <span className="excl__none">Yok</span>}
        {saved.map((x, i) => (
          <span key={`${x.start_frame}-${x.end_frame}`} className="excl__chip">
            <button type="button" className="excl__seek" title="Bölümün başına git"
                    onClick={() => clock.seek((x.start_frame + 0.5) / fps)}>
              {at(x.start_frame)}–{at(x.end_frame + 1)} · {REASON_LABELS[x.reason]}
            </button>
            <button type="button" className="excl__remove" aria-label="Dışlamayı kaldır" title="Dışlamayı kaldır"
                    disabled={busy} onClick={() => save(saved.filter((_, k) => k !== i))}>×</button>
          </span>
        ))}
        <button type="button" className="btn btn--sm btn--ghost excl__toggle" aria-expanded={open}
                onClick={() => setOpen((v) => !v)}>
          {open ? "Kapat" : "Bölüm dışla…"}
        </button>
      </div>
      {open && (
        <div className="excl__form">
          <p className="excl__help">
            Tekrar ve ağır çekim görüntüleri otomatik ayırt edilemez; burada işaretleyin. Dışlanan bölümdeki olaylar
            listede “Dışlandı” etiketiyle kalır ama sayılmaz ve momentuma puan eklemez; ilerleme/kontrol süresi ve
            ölçülen süre birikmez; momentum bölüm boyunca donar. Pozlar ve kimlikler değişmez.
          </p>
          <div className="excl__fields">
            <button type="button" className="btn btn--sm" onClick={() => setStart(frame)}>
              Başlangıç = şimdiki kare
            </button>
            <span className="excl__value num">{start === null ? "—" : `${at(start)} (kare ${start})`}</span>
            <button type="button" className="btn btn--sm" onClick={() => setEnd(frame)}>Bitiş = şimdiki kare</button>
            <span className="excl__value num">{end === null ? "—" : `${at(end + 1)} (kare ${end})`}</span>
            <label className="excl__reason">
              Neden
              <select value={reason} onChange={(e) => setReason(e.target.value as ExclusionReason)}>
                {(Object.keys(REASON_LABELS) as ExclusionReason[]).map((r) => (
                  <option key={r} value={r}>{REASON_LABELS[r]}</option>
                ))}
              </select>
            </label>
            <button type="button" className="btn btn--sm btn--primary" onClick={add}
                    disabled={busy || start === null || end === null}>
              {busy ? "Kaydediliyor…" : "Dışla ve yeniden hesapla"}
            </button>
          </div>
        </div>
      )}
      {problem && <p className="inline-warn">{problem}</p>}
    </section>
  );
}
