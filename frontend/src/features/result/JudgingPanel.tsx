import { useState } from "react";
import type {
  ConfidenceLevel,
  Criterion,
  DecisionType,
  FighterId,
  Job,
  RoundAssessment,
  Scorecards,
  VerdictStatus,
} from "../../contracts/generated";
import type { Clock } from "../../player/clock";
import { formatClock } from "../../player/clock";
import { FINISH_LABELS, MatchEditor } from "./MatchEditor";

const CRITERION_LABELS: Record<Criterion, string> = {
  effective_striking_grappling: "Etkili vuruş / grappling",
  effective_aggressiveness: "Etkili agresiflik",
  cage_control: "Alan kontrolü",
};
const DECISION_LABELS: Record<DecisionType, string> = {
  unanimous: "Oybirliğiyle karar (UD)",
  split: "Bölünmüş karar (SD)",
  majority: "Çoğunluk kararı (MD)",
  unanimous_draw: "Oybirliğiyle beraberlik",
  majority_draw: "Çoğunluk beraberliği",
  split_draw: "Bölünmüş beraberlik",
};
const STATUS_LABELS: Record<VerdictStatus, string> = {
  decision: "AI karar tahmini",
  finish: "Bitiş (kullanıcı girdisi)",
  no_contest: "No contest (kullanıcı girdisi)",
  not_computed: "Sonuç hesaplanmadı",
};
const LEVEL_LABELS: Record<ConfidenceLevel, string> = { low: "Düşük", medium: "Orta", high: "Yüksek" };

function Confidence({ value, level }: { value: number | null | undefined; level: ConfidenceLevel | null | undefined }) {
  if (value == null || !level) return <span className="conf conf--none">—</span>;
  return (
    <span className={`conf conf--${level}`} title="Ölçüm kapsamı, kimlik takibi, kanıt türü ve hakem uyumundan hesaplanır">
      {LEVEL_LABELS[level]} <small className="num">%{Math.round(value * 100)}</small>
    </span>
  );
}

function RoundDetails({ round, sc, names, clock }: {
  round: RoundAssessment;
  sc: Scorecards;
  names: Record<FighterId, string>;
  clock: Clock;
}) {
  const scores = sc.judges.map((j) => ({ judge: j.judge, score: j.rounds.find((r) => r.round === round.number)! }));
  return (
    <div className="jround__body">
      {!round.scorable && <p className="inline-warn">{round.unscorable_reason}</p>}
      <div className="jround__cols">
        <table className="jev">
          <caption>Ölçülen kanıt ({formatClock(round.recorded_s)} kayıt{round.partial ? ", eksik raund" : ""})</caption>
          <thead><tr><th /><th>{names.fighter_a}</th><th>{names.fighter_b}</th></tr></thead>
          <tbody>
            {([
              ["Olası knockdown", "possible_knockdowns"],
              ["Olası etkili vuruş", "possible_impact_strikes"],
              ["Olası temaslı vuruş", "possible_contact_strikes"],
              ["Yumruk/diz denemesi", "strike_attempts"],
              ["Tekme denemesi", "kick_attempts"],
              ["Olası takedown (kontrole dönen)", "possible_takedowns"],
              ["Üst kontrol (sn)", "control_s"],
              ["İlerleme / geri çekilme (sn)", "advance_s"],
              ["Ölçülebilen süre (sn)", "measured_s"],
              ["Kimlik belirsiz (sn)", "identity_uncertain_s"],
            ] as const).map(([label, key]) => (
              <tr key={key}>
                <th scope="row">{label}</th>
                {round.evidence.map((e) => {
                  const v = key === "possible_takedowns" ? `${e.possible_takedowns} (${e.takedowns_to_control})`
                    : key === "advance_s" ? `${Math.round(e.advance_s)} / ${Math.round(e.retreat_s)}`
                      : typeof e[key] === "number" && !Number.isInteger(e[key]) ? Math.round(e[key] as number) : e[key];
                  return <td key={e.fighter_id} className="num">{v}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <div className="jround__text">
          <p><strong>Hasar:</strong> {round.damage.text}</p>
          <p><strong>Güreş ve yer oyunu:</strong> {round.grappling.text}</p>
          {round.key_moments.length > 0 && (
            <div>
              <strong>En etkili anlar</strong>
              <ul className="jkeys">
                {round.key_moments.map((k) => (
                  <li key={k.event_id}>
                    <button type="button" className="excl__seek" onClick={() => clock.seek(Math.max(0, k.time_s - 1))}>
                      {formatClock(k.time_s, true)}
                    </button>
                    {k.label} {k.uncertain && <span className="tag tag--muted">Olası</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
      <div className="jjudges">
        {scores.map(({ judge, score }) => (
          <div key={judge.judge_id} className="jjudge">
            <div className="jjudge__head">
              <strong>{judge.name}</strong>
              <span className="num">{score.scored ? `${score.red}-${score.blue}` : "puanlanmadı"}</span>
              {score.deciding_criterion && (
                <span className="tag tag--muted tag--plain">{CRITERION_LABELS[score.deciding_criterion]}</span>
              )}
            </div>
            <ul>{score.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
          </div>
        ))}
      </div>
      <details className="jnotes">
        <summary>Güven notları ve ölçülemeyenler</summary>
        <ul>{round.confidence_notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        <ul>{round.not_measured.map((n, i) => <li key={i}>{n}</li>)}</ul>
      </details>
    </div>
  );
}

/** AI scorecards of three virtual judges and the decision estimate (never an official result). */
export function JudgingPanel({ job, sc, problem, frame, clock, onSaved }: {
  job: Job;
  sc: Scorecards | null;
  problem: string | null;
  frame: number;
  clock: Clock;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState<number | null>(null);
  const video = job.outputs.analysis_video!.video;
  const names: Record<FighterId, string> = {
    fighter_a: job.fighters[0]?.display_name ?? "Kırmızı", fighter_b: job.fighters[1]?.display_name ?? "Mavi",
  };
  const v = sc?.verdict;
  return (
    <section className="jpanel" aria-label="Hakem kartları">
      <p className="jpanel__disclaimer" role="note">
        <strong>AI tahmini.</strong> {sc?.disclaimer ?? "Resmi hakem kararı ya da resmi maç sonucu değildir."} Momentum
        puanlamada kullanılmaz.
      </p>
      {problem && <p className="inline-warn">{problem}</p>}
      {!sc ? <p className="xpanel__empty">Skor kartları hesaplanıyor…</p> : (
        <>
          <div className={`jverdict jverdict--${v!.status}`}>
            <div className="jverdict__row">
              <span className="tag tag--muted tag--plain">{STATUS_LABELS[v!.status]}</span>
              {v!.decision_type && <span className="tag tag--amber tag--plain">{DECISION_LABELS[v!.decision_type]}</span>}
              {v!.status === "finish" && <span className="tag tag--amber tag--plain">{FINISH_LABELS[v!.method]}</span>}
              <Confidence value={v!.confidence} level={v!.confidence_level} />
            </div>
            <p className="jverdict__summary">{v!.summary}</p>
            {v!.cards.length > 0 && <p className="jverdict__cards num">{v!.cards.join(" · ")}</p>}
            {v!.reasons.length > 0 && <ul className="jverdict__reasons">{v!.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>}
            {v!.notes.length > 0 && <ul className="jverdict__notes">{v!.notes.map((r, i) => <li key={i}>{r}</li>)}</ul>}
          </div>

          <table className="jtable">
            <thead>
              <tr>
                <th>Raund</th>
                {sc.judges.map((j) => <th key={j.judge.judge_id} title={j.judge.description}>{j.judge.name}</th>)}
                <th>Raund sonucu</th>
                <th>Güven</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {sc.rounds.map((r, k) => {
                const s = sc.round_summaries[k]!;
                return (
                  <tr key={r.number} className={open === r.number ? "is-open" : ""}>
                    <th scope="row">
                      R{r.number}{!r.marked && <small> (işaretsiz)</small>}
                      <small className="num"> {formatClock(r.start_s)}–{formatClock(r.end_s)}</small>
                    </th>
                    {sc.judges.map((j) => {
                      const js = j.rounds[k]!;
                      return <td key={j.judge.judge_id} className="num">{js.scored ? `${js.red}-${js.blue}` : "—"}</td>;
                    })}
                    <td>
                      {s.scored
                        ? <>{s.winner ? names[s.winner] : "10-10"} <span className="num">{s.red}-{s.blue}</span> <small>({s.judges_agree}/3)</small></>
                        : "Puanlanmadı"}
                    </td>
                    <td><Confidence value={s.scored ? s.confidence : null} level={s.scored ? s.confidence_level : null} /></td>
                    <td>
                      <button type="button" className="btn btn--sm btn--ghost" aria-expanded={open === r.number}
                              onClick={() => setOpen(open === r.number ? null : r.number)}>
                        {open === r.number ? "Kapat" : "Ayrıntı"}
                      </button>
                    </td>
                  </tr>
                );
              })}
              <tr className="jtable__total">
                <th scope="row">Toplam</th>
                {sc.judges.map((j) => (
                  <td key={j.judge.judge_id} className="num">
                    {j.total_red}-{j.total_blue} {j.winner ? `(${names[j.winner]})` : "(berabere)"}
                  </td>
                ))}
                <td colSpan={3} />
              </tr>
            </tbody>
          </table>
          {open !== null && (
            <RoundDetails round={sc.rounds.find((r) => r.number === open)!} sc={sc} names={names} clock={clock} />
          )}
          <ul className="jwarnings">{sc.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
          <details className="jnotes">
            <summary>Hakem profilleri ve yöntem</summary>
            <p>{sc.method}</p>
            <ul>{sc.judges.map((j) => <li key={j.judge.judge_id}><strong>{j.judge.name}:</strong> {j.judge.description}</li>)}</ul>
          </details>
        </>
      )}
      <MatchEditor jobId={job.job_id} saved={job.match ?? null} frame={frame} fps={video.fps}
                   frameCount={video.frame_count} clock={clock}
                   names={{ red: names.fighter_a, blue: names.fighter_b }} onSaved={onSaved} />
    </section>
  );
}
