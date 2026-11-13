import { useState } from "react";
import { api } from "../../api/client";
import type { FighterId, FinishMethod, Job, MatchSetup, PointDeduction } from "../../contracts/generated";
import { MATCH_EDITOR_LABELS as L } from "../../labels";
import { formatClock } from "../../player/clock";
import { editsOf, withMark } from "../match/roundEdit";

export const FINISH_LABELS: Record<FinishMethod, string> = L.finish;
const FINISHES = new Set<FinishMethod>(["ko", "tko", "submission", "disqualification", "referee_stoppage"]);
const EMPTY: MatchSetup = {
  scheduled_rounds: 3, round_length_s: 300, rounds: [], cleared_rounds: [], deductions: [],
  ending: { method: "unknown", winner: null, round: null, time_s: null },
};

type Draft = Pick<MatchSetup, "ending" | "deductions">;
const draftOf = (m: MatchSetup | null): Draft => ({ ending: (m ?? EMPTY).ending, deductions: (m ?? EMPTY).deductions });

/**
 * "Maç bilgileri": marking a round by hand at the current frame (saved at once;
 * the rounds in effect are listed in "Maç ayarları"), and how the bout ended
 * and point deductions (official information the video cannot give; saved with
 * the button). Round count and length come from "Maç ayarları".
 */
export function MatchEditor({ jobId, saved, scheduled, frame, fps, frameCount, names, onSaved }: {
  jobId: string;
  saved: MatchSetup | null;
  scheduled: number;
  frame: number;
  fps: number;
  frameCount: number;
  names: Record<"red" | "blue", string>;
  onSaved: (job: Job) => void;
}) {
  const [draft, setDraft] = useState<Draft>(draftOf(saved));
  const [pending, setPending] = useState<{ number: number; start: number | null }>({ number: 1, start: null });
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  // The job is polled: reset the draft only when the stored ending/deductions really change,
  // so unsaved edits survive a refresh that brings the same data (or only new rounds).
  const savedKey = JSON.stringify(draftOf(saved));
  const [base, setBase] = useState(savedKey);
  if (savedKey !== base) {
    setBase(savedKey);
    setDraft(draftOf(saved));
  }
  const fighterName = (id: FighterId) => (id === "fighter_a" ? names.red : names.blue);
  const dirty = JSON.stringify(draft) !== savedKey;
  const roundNumbers = Array.from({ length: scheduled }, (_, k) => k + 1);

  const run = (p: Promise<Job>) => {
    setBusy(true);
    setProblem(null);
    p.then(onSaved, (e: unknown) => setProblem(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  };
  const endRound = () => {
    if (pending.start === null) return;
    const [a, b] = [Math.min(pending.start, frame), Math.max(pending.start, frame)];
    run(api.setRounds(jobId, withMark(editsOf(saved),
                                      { number: pending.number, start_frame: a, end_frame: Math.min(b, frameCount - 1) })));
    setPending({ number: Math.min(scheduled, pending.number + 1), start: null });
  };
  const save = () => run(api.setMatch(jobId, { ...(saved ?? EMPTY), ...draft }));
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
    <section className="medit" aria-label={L.region}>
      <header className="medit__head">
        <h3 className="medit__title">{L.title} <span className="tag tag--muted">{L.userInput}</span></h3>
        <p className="medit__help">{L.help}</p>
      </header>

      <div className="medit__mark">
        <span className="medit__sub">{L.rounds}</span>
        <label className="medit__field">
          {L.markRound}
          <select value={pending.number} onChange={(e) => setPending({ number: Number(e.target.value), start: null })}>
            {roundNumbers.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <button type="button" className="btn btn--sm" onClick={() => setPending((p) => ({ ...p, start: frame }))}>
          {L.markStart}
        </button>
        <span className="excl__value num">{pending.start === null ? "—" : formatClock(pending.start / fps, true)}</span>
        <button type="button" className="btn btn--sm" disabled={pending.start === null || busy} onClick={endRound}>
          {L.markEnd}
        </button>
      </div>

      <div className="medit__grid">
        <label className="medit__field">
          {L.ending}
          <select value={ending.method} onChange={(e) => setEnding({ method: e.target.value as FinishMethod })}>
            {(Object.keys(FINISH_LABELS) as FinishMethod[]).map((m) => <option key={m} value={m}>{FINISH_LABELS[m]}</option>)}
          </select>
        </label>
        {FINISHES.has(ending.method) && (
          <>
            <label className="medit__field">
              {L.winner}
              <select value={ending.winner ?? "fighter_a"} onChange={(e) => setEnding({ winner: e.target.value as FighterId })}>
                <option value="fighter_a">{names.red}</option>
                <option value="fighter_b">{names.blue}</option>
              </select>
            </label>
            <label className="medit__field">
              {L.endRound}
              <select value={ending.round ?? ""} onChange={(e) => setEnding({ round: e.target.value ? Number(e.target.value) : null })}>
                <option value="">—</option>
                {roundNumbers.map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
            <label className="medit__field">
              {L.endTime}
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
        <span className="medit__sub">{L.deductions}</span>
        {draft.deductions.length === 0 && <span className="medit__none">{L.noDeductions}</span>}
        {draft.deductions.map((d, i) => (
          <div key={i} className="medit__ded">
            <select value={d.round} onChange={(e) => setDeduction(i, { round: Number(e.target.value) })} aria-label={L.deductionRound}>
              {roundNumbers.map((n) => <option key={n} value={n}>R{n}</option>)}
            </select>
            <select value={d.fighter_id} onChange={(e) => setDeduction(i, { fighter_id: e.target.value as FighterId })}
                    aria-label={L.deductionFighter}>
              <option value="fighter_a">{fighterName("fighter_a")}</option>
              <option value="fighter_b">{fighterName("fighter_b")}</option>
            </select>
            <select value={d.points} onChange={(e) => setDeduction(i, { points: Number(e.target.value) })} aria-label={L.deductionPoints}>
              <option value={1}>−1</option>
              <option value={2}>−2</option>
            </select>
            <button type="button" className="excl__remove" aria-label={L.removeDeduction}
                    onClick={() => setDraft((x) => ({ ...x, deductions: x.deductions.filter((_, k) => k !== i) }))}>×</button>
          </div>
        ))}
        <button type="button" className="btn btn--sm btn--ghost" onClick={addDeduction}>{L.addDeduction}</button>
      </div>

      <div className="medit__actions">
        <button type="button" className="btn btn--primary btn--sm" disabled={!dirty || busy} onClick={save}>
          {busy ? L.saving : L.save}
        </button>
        {dirty && <button type="button" className="btn btn--ghost btn--sm" onClick={() => setDraft(draftOf(saved))}>{L.cancel}</button>}
      </div>
      {problem && <p className="inline-warn">{problem}</p>}
    </section>
  );
}
