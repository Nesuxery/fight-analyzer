import { useState } from "react";
import { api } from "../../api/client";
import type { FighterId, FinishMethod, MatchSetup, PointDeduction, RoundMark } from "../../contracts/generated";
import type { Clock } from "../../player/clock";
import { formatClock } from "../../player/clock";

export const FINISH_LABELS: Record<FinishMethod, string> = {
  unknown: "Bilinmiyor / girilmedi",
  decision: "Puan kararı (maç süresini tamamladı)",
  ko: "Nakavt (KO)",
  tko: "Teknik nakavt (TKO)",
  submission: "Submission",
  disqualification: "Diskalifiye",
  referee_stoppage: "Hakem / doktor durdurması",
  no_contest: "No contest",
};
const FINISHES = new Set<FinishMethod>(["ko", "tko", "submission", "disqualification", "referee_stoppage"]);
const EMPTY: MatchSetup = {
  scheduled_rounds: 3, round_length_s: 300, rounds: [], deductions: [],
  ending: { method: "unknown", winner: null, round: null, time_s: null },
};

/** Rounds, how the bout ended and point deductions: official information the video cannot give. */
export function MatchEditor({ jobId, saved, frame, fps, frameCount, clock, names, onSaved }: {
  jobId: string;
  saved: MatchSetup | null;
  frame: number;
  fps: number;
  frameCount: number;
  clock: Clock;
  names: Record<"red" | "blue", string>;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState<MatchSetup>(saved ?? EMPTY);
  const [pending, setPending] = useState<{ number: number; start: number | null }>({ number: 1, start: null });
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  // The job is polled: reset the draft only when the stored setup really changes, so
  // unsaved edits survive a refresh that brings the same data.
  const savedKey = JSON.stringify(saved ?? EMPTY);
  const [base, setBase] = useState(savedKey);
  if (savedKey !== base) {
    setBase(savedKey);
    setDraft(saved ?? EMPTY);
  }
  const at = (f: number) => formatClock(f / fps, true);
  const fighterName = (id: FighterId) => (id === "fighter_a" ? names.red : names.blue);
  const dirty = JSON.stringify(draft) !== savedKey;

  const setRound = (mark: RoundMark) => setDraft((d) => ({
    ...d, rounds: [...d.rounds.filter((r) => r.number !== mark.number), mark].sort((a, b) => a.number - b.number),
  }));
  const endRound = () => {
    if (pending.start === null) return;
    const [a, b] = [Math.min(pending.start, frame), Math.max(pending.start, frame)];
    setRound({ number: pending.number, start_frame: a, end_frame: Math.min(b, frameCount - 1) });
    setPending({ number: Math.min(draft.scheduled_rounds, pending.number + 1), start: null });
  };
  const save = () => {
    setBusy(true);
    setProblem(null);
    api.setMatch(jobId, draft).then(onSaved, (e: unknown) => setProblem(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  };
  const ending = draft.ending;
  const setEnding = (patch: Partial<MatchSetup["ending"]>) => setDraft((d) => {
    const next = { ...d.ending, ...patch };
    if (!FINISHES.has(next.method)) next.winner = null;
    else if (!next.winner) next.winner = "fighter_a";
    return { ...d, ending: next };
  });
  const addDeduction = () => setDraft((d) => ({
    ...d, deductions: [...d.deductions, { round: 1, fighter_id: "fighter_a", points: 1, note: null }],
  }));
  const setDeduction = (i: number, patch: Partial<PointDeduction>) => setDraft((d) => ({
    ...d, deductions: d.deductions.map((x, k) => (k === i ? { ...x, ...patch } : x)),
  }));

  return (
    <section className="medit" aria-label="Maç bilgileri">
      <header className="medit__head">
        <h3 className="medit__title">Maç bilgileri <span className="tag tag--muted">Kullanıcı girdisi</span></h3>
        <p className="medit__help">
          Raund sınırları, bitiş şekli ve puan kesintileri videodan güvenilir biçimde çıkarılamaz; buraya girdiğiniz
          resmi bilgiler olduğu gibi kullanılır. Raundlar işaretlenmezse tüm video tek raund sayılır.
        </p>
      </header>
      <div className="medit__grid">
        <label className="medit__field">
          Planlanan raund
          <select value={draft.scheduled_rounds}
                  onChange={(e) => setDraft((d) => ({ ...d, scheduled_rounds: Number(e.target.value),
                                                       rounds: d.rounds.filter((r) => r.number <= Number(e.target.value)) }))}>
            {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <label className="medit__field">
          Raund süresi (dk)
          <select value={draft.round_length_s} onChange={(e) => setDraft((d) => ({ ...d, round_length_s: Number(e.target.value) }))}>
            {[180, 240, 300].map((s) => <option key={s} value={s}>{s / 60}</option>)}
          </select>
        </label>
      </div>

      <div className="medit__rounds">
        {Array.from({ length: draft.scheduled_rounds }, (_, k) => k + 1).map((n) => {
          const r = draft.rounds.find((x) => x.number === n);
          return (
            <div key={n} className="medit__round">
              <span className="medit__rno">R{n}</span>
              {r ? (
                <button type="button" className="excl__seek" onClick={() => clock.seek((r.start_frame + 0.5) / fps)}>
                  {at(r.start_frame)}–{at(r.end_frame + 1)}
                </button>
              ) : <span className="medit__none">işaretlenmedi</span>}
              {r && (
                <button type="button" className="excl__remove" aria-label={`${n}. raund işaretini kaldır`}
                        onClick={() => setDraft((d) => ({ ...d, rounds: d.rounds.filter((x) => x.number !== n) }))}>×</button>
              )}
            </div>
          );
        })}
      </div>
      <div className="medit__mark">
        <label className="medit__field">
          Raund
          <select value={pending.number} onChange={(e) => setPending({ number: Number(e.target.value), start: null })}>
            {Array.from({ length: draft.scheduled_rounds }, (_, k) => k + 1).map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <button type="button" className="btn btn--sm" onClick={() => setPending((p) => ({ ...p, start: frame }))}>
          Başlangıç = şimdiki kare
        </button>
        <span className="excl__value num">{pending.start === null ? "—" : at(pending.start)}</span>
        <button type="button" className="btn btn--sm" disabled={pending.start === null} onClick={endRound}>
          Bitiş = şimdiki kare
        </button>
      </div>

      <div className="medit__grid">
        <label className="medit__field">
          Maç nasıl bitti?
          <select value={ending.method} onChange={(e) => setEnding({ method: e.target.value as FinishMethod })}>
            {(Object.keys(FINISH_LABELS) as FinishMethod[]).map((m) => <option key={m} value={m}>{FINISH_LABELS[m]}</option>)}
          </select>
        </label>
        {FINISHES.has(ending.method) && (
          <>
            <label className="medit__field">
              Kazanan
              <select value={ending.winner ?? "fighter_a"} onChange={(e) => setEnding({ winner: e.target.value as FighterId })}>
                <option value="fighter_a">{names.red}</option>
                <option value="fighter_b">{names.blue}</option>
              </select>
            </label>
            <label className="medit__field">
              Raund
              <select value={ending.round ?? ""} onChange={(e) => setEnding({ round: e.target.value ? Number(e.target.value) : null })}>
                <option value="">—</option>
                {Array.from({ length: draft.scheduled_rounds }, (_, k) => k + 1).map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
            <label className="medit__field">
              Süre (dk:sn)
              <input type="text" inputMode="numeric" placeholder="3:32" defaultValue={ending.time_s != null
                ? `${Math.floor(ending.time_s / 60)}:${String(Math.floor(ending.time_s % 60)).padStart(2, "0")}` : ""}
                     onBlur={(e) => {
                       const m = /^(\d{1,2}):(\d{2})$/.exec(e.target.value.trim());
                       setEnding({ time_s: m ? Number(m[1]) * 60 + Number(m[2]) : null });
                     }} />
            </label>
          </>
        )}
      </div>

      <div className="medit__deds">
        <span className="medit__sub">Puan kesintileri</span>
        {draft.deductions.length === 0 && <span className="medit__none">yok</span>}
        {draft.deductions.map((d, i) => (
          <div key={i} className="medit__ded">
            <select value={d.round} onChange={(e) => setDeduction(i, { round: Number(e.target.value) })} aria-label="Raund">
              {Array.from({ length: draft.scheduled_rounds }, (_, k) => k + 1).map((n) => <option key={n} value={n}>R{n}</option>)}
            </select>
            <select value={d.fighter_id} onChange={(e) => setDeduction(i, { fighter_id: e.target.value as FighterId })} aria-label="Dövüşçü">
              <option value="fighter_a">{fighterName("fighter_a")}</option>
              <option value="fighter_b">{fighterName("fighter_b")}</option>
            </select>
            <select value={d.points} onChange={(e) => setDeduction(i, { points: Number(e.target.value) })} aria-label="Puan">
              <option value={1}>−1</option>
              <option value={2}>−2</option>
            </select>
            <button type="button" className="excl__remove" aria-label="Kesintiyi kaldır"
                    onClick={() => setDraft((x) => ({ ...x, deductions: x.deductions.filter((_, k) => k !== i) }))}>×</button>
          </div>
        ))}
        <button type="button" className="btn btn--sm btn--ghost" onClick={addDeduction}>Kesinti ekle</button>
      </div>

      <div className="medit__actions">
        <button type="button" className="btn btn--primary btn--sm" disabled={!dirty || busy} onClick={save}>
          {busy ? "Kaydediliyor…" : "Kaydet ve kartları yenile"}
        </button>
        {dirty && <button type="button" className="btn btn--ghost btn--sm" onClick={() => setDraft(saved ?? EMPTY)}>Vazgeç</button>}
      </div>
      {problem && <p className="inline-warn">{problem}</p>}
    </section>
  );
}
