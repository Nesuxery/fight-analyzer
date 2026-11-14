import { useState } from "react";
import { api } from "../../api/client";
import type { AutoExclusion, ExcludedSegment, ExclusionReason, Job } from "../../contracts/generated";
import { EXCLUSION_LABELS as L, UI_LABELS } from "../../labels";
import type { Clock } from "../../player/clock";
import { formatClock } from "../../player/clock";
import { Badge, Button, HelpTip, cx } from "../../ui";
import { excludedEventCounts, exclusionRows, toggledDismissed } from "./exclusionView";

/** Confidence below this is called out as low (the part is still applied until the user turns it off). */
const LOW_CONFIDENCE = 0.7;

/**
 * Parts that are not live fight time. Automatic parts (time outside the rounds,
 * detected replays and stoppages) are listed with why and how sure; one click
 * turns one off or on again. The user can also mark parts by hand.
 */
export function ExclusionEditor({ jobId, frame, fps, frameCount, saved, auto, eventFrames, clock, onSaved, onJob }: {
  jobId: string;
  /** Presented frame. */
  frame: number;
  fps: number;
  frameCount: number;
  /** The user's own excluded parts. */
  saved: ExcludedSegment[];
  /** Automatic parts, including the ones the user turned off. */
  auto: AutoExclusion[];
  /** Frames the events count from (their peak, else their start). */
  eventFrames: number[];
  clock: Clock;
  /** The user's parts changed: the analysis is computed again by the worker. */
  onSaved: () => void;
  /** An automatic part was switched: the updated job (already recomputed). */
  onJob: (job: Job) => void;
}) {
  const [open, setOpen] = useState(false);
  const [start, setStart] = useState<number | null>(null);
  const [end, setEnd] = useState<number | null>(null);
  const [reason, setReason] = useState<ExclusionReason>("replay");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const at = (f: number) => formatClock(f / fps, true);
  const rows = exclusionRows(saved, auto, eventFrames);
  const counts = excludedEventCounts(rows, eventFrames);
  const fail = (e: unknown) => setProblem(e instanceof Error ? e.message : String(e));

  const save = (segments: ExcludedSegment[]) => {
    setBusy(true);
    setProblem(null);
    api.setExclusions(jobId, { segments })
      .then(() => {
        setStart(null);
        setEnd(null);
        setOpen(false);
        onSaved();
      }, fail)
      .finally(() => setBusy(false));
  };
  const add = () => {
    if (start === null || end === null) return;
    save([...saved, { start_frame: Math.min(start, end), end_frame: Math.min(Math.max(start, end), frameCount - 1),
                      reason, note: null, source: "manual", auto_id: null, confidence: null, signals: [] }]);
  };
  const toggle = (autoId: string) => {
    setBusy(true);
    setProblem(null);
    api.setAutoExclusions(jobId, { dismissed: toggledDismissed(auto, autoId) }).then(onJob, fail)
      .finally(() => setBusy(false));
  };

  return (
    <section className="excl" aria-label={L.title}>
      <div className="excl__row">
        <span className="excl__title">{L.title}</span>
        <HelpTip label={UI_LABELS.help(L.title)} align="start">{L.help}</HelpTip>
        {rows.length === 0 && <span className="excl__none">{L.none}</span>}
        <Button size="sm" variant="ghost" className="excl__toggle" aria-expanded={open}
                onClick={() => setOpen((v) => !v)}>
          {open ? L.close : L.open}
        </Button>
      </div>
      {rows.length > 0 && (
        <ul className="excl__list">
          {rows.map((r) => {
            const x = r.segment;
            const low = x.confidence !== null && x.confidence < LOW_CONFIDENCE;
            return (
              <li key={r.key} className={cx("excl__item", r.dismissed && "is-dismissed")}>
                <Badge tone="neutral" className="excl__kind">
                  {r.kind === "auto" ? L.auto : L.manual}{r.dismissed && ` · ${L.dismissed}`}
                </Badge>
                <button type="button" className="linkbtn num" title={L.seek}
                        onClick={() => clock.seek((x.start_frame + 0.5) / fps)}>
                  {at(x.start_frame)}–{at(x.end_frame + 1)}
                </button>
                <span className="excl__reason-text">{L.reasons[x.reason]}</span>
                <span className="excl__meta">
                  {x.confidence !== null && (
                    <>
                      <span className={cx("num", low && "excl__low")}>
                        {L.confidence(Math.round(x.confidence * 100))}{low && ` (${L.lowConfidence})`}
                      </span>
                      {" · "}
                    </>
                  )}
                  <span className="num">{L.events(r.events)}</span>
                  {x.signals.length > 0 && <> · {L.evidence(x.signals.map((s) => L.signals[s]).join(", "))}</>}
                </span>
                <span className="excl__actions">
                  {r.kind === "auto" && x.auto_id !== null ? (
                    <Button size="sm" variant="ghost" disabled={busy} title={r.dismissed ? L.restoreTitle : L.dismissTitle}
                            onClick={() => toggle(x.auto_id!)}>
                      {r.dismissed ? L.restore : L.dismiss}
                    </Button>
                  ) : r.kind === "manual" ? (
                    <button type="button" className="excl__remove" aria-label={L.remove} title={L.remove}
                            disabled={busy} onClick={() => save(saved.filter((_, k) => k !== r.index))}>×</button>
                  ) : null}
                </span>
              </li>
            );
          })}
        </ul>
      )}
      {rows.length > 0 && <p className="excl__summary">{L.summary(counts.total, counts.auto, counts.manual)}</p>}
      {open && (
        <div className="excl__form">
          <p className="excl__help">{L.formHelp}</p>
          <div className="excl__fields">
            <Button size="sm" onClick={() => setStart(frame)}>{L.startNow}</Button>
            <span className="excl__value num">{start === null ? UI_LABELS.noValue : L.frameValue(at(start), start)}</span>
            <Button size="sm" onClick={() => setEnd(frame)}>{L.endNow}</Button>
            <span className="excl__value num">{end === null ? UI_LABELS.noValue : L.frameValue(at(end + 1), end)}</span>
            <label className="excl__reason">
              {L.reason}
              <select value={reason} onChange={(e) => setReason(e.target.value as ExclusionReason)}>
                {(Object.keys(L.reasons) as ExclusionReason[]).map((r) => (
                  <option key={r} value={r}>{L.reasons[r]}</option>
                ))}
              </select>
            </label>
            <Button size="sm" variant="primary" onClick={add} disabled={busy || start === null || end === null}>
              {busy ? L.saving : L.save}
            </Button>
          </div>
        </div>
      )}
      {problem && <p className="inline-warn" role="alert">{problem}</p>}
    </section>
  );
}
