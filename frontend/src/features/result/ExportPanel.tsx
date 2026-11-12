import { useCallback, useEffect, useState } from "react";
import { api, urls } from "../../api/client";
import type { ExportFileKind, ExportOptions, Job } from "../../contracts/generated";
import {
  ERROR_LABELS, JOB_STATUS_LABELS, RESULT_LABELS, formatBytes, formatDateTime, formatDuration,
} from "../../labels";
import { IconAlert } from "../../ui/icons";

const L = RESULT_LABELS.export;
const OPTION_KEYS: (keyof ExportOptions)[] = ["skeleton", "effects", "momentum", "counters", "distance", "others"];
const OPTION_LABELS: Record<keyof ExportOptions, { label: string; hint: string }> = L.options;
const DEFAULT_OPTIONS: ExportOptions = {
  skeleton: true, effects: true, momentum: true, counters: true, distance: false, others: false,
};
const FILE_LABELS: Record<ExportFileKind, string> = L.files;
const ACTIVE = new Set(["queued", "running"]);

function ExportRow({ exp, current, onCancel }: { exp: Job; current: Job; onCancel: (id: string) => void }) {
  const summary = exp.outputs.export;
  const active = ACTIVE.has(exp.status);
  const outdated = summary && (summary.source_keys.events !== current.outputs.events?.cache_key ||
    summary.source_keys.scoring !== current.outputs.scoring?.cache_key);
  const eta = exp.progress_detail?.eta_s;
  return (
    <li className={`xrow xrow--${exp.status}`}>
      <div className="xrow__head">
        <span className="xrow__when num">{formatDateTime(exp.created_at)}</span>
        {/* a failure is shown with an icon and text, so it is not read as the red corner */}
        <span className={`tag ${exp.status === "failed" ? "tag--danger" : exp.status === "completed" ? "tag--ok" : "tag--muted"}`}>
          {exp.status === "failed" && <IconAlert size={16} />}
          {JOB_STATUS_LABELS[exp.status]}
        </span>
        {exp.fighters.length === 2 && (
          <span className="xrow__names">{exp.fighters[0]!.display_name} – {exp.fighters[1]!.display_name}</span>
        )}
        {outdated && (
          <span className="tag tag--amber" title={L.outdatedHelp}>{L.outdated}</span>
        )}
        {active && (
          <button type="button" className="btn btn--sm btn--ghost" onClick={() => onCancel(exp.job_id)}>{L.cancel}</button>
        )}
      </div>
      {active && (
        <div className="xrow__progress">
          <span className="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100}
                aria-valuenow={Math.round(exp.progress * 100)} aria-label={L.progress}>
            <span className="bar__fill" style={{ width: `${exp.progress * 100}%` }} />
          </span>
          <span className="xrow__msg">
            {exp.status === "queued" ? L.queued : exp.message}
            {eta != null && L.remaining(formatDuration(eta))}
          </span>
        </div>
      )}
      {exp.status === "failed" && exp.error && (
        <p className="xrow__error">
          <IconAlert size={16} />
          <span>{ERROR_LABELS[exp.error.code] ?? exp.error.message}</span>
        </p>
      )}
      {exp.status === "completed" && summary && (
        <>
          <ul className="xrow__files">
            {summary.files.map((f) => (
              <li key={f.kind}>
                <a className="btn btn--sm btn--primary" href={urls.exportFile(exp.job_id, f.kind)} download={f.name}>
                  {FILE_LABELS[f.kind]}
                </a>
                <span className="xrow__size num">{formatBytes(f.bytes)}</span>
              </li>
            ))}
          </ul>
          <p className="xrow__meta">
            {L.summary(summary.frames, summary.events, summary.final_red_share.toFixed(0), summary.has_audio)}
          </p>
        </>
      )}
    </li>
  );
}

/** Export of the shown results: the files are written by the worker on this computer. */
export function ExportPanel({ job }: { job: Job }) {
  const [options, setOptions] = useState<ExportOptions>(DEFAULT_OPTIONS);
  const [exportsList, setExports] = useState<Job[] | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const ready = !!(job.outputs.events && job.outputs.scoring);

  const refresh = useCallback((signal?: AbortSignal) =>
    api.exports(job.job_id, signal).then((list) => setExports(list.jobs), (e: unknown) => {
      if (!signal?.aborted) setProblem(e instanceof Error ? e.message : String(e));
    }), [job.job_id]);

  const anyActive = exportsList?.some((e) => ACTIVE.has(e.status)) ?? false;
  useEffect(() => {
    const c = new AbortController();
    void refresh(c.signal);
    // poll only while something is being exported; finished lists do not change by themselves
    const timer = anyActive ? window.setInterval(() => void refresh(c.signal), 1000) : undefined;
    return () => {
      c.abort();
      window.clearInterval(timer);
    };
  }, [refresh, anyActive]);

  const start = () => {
    setBusy(true);
    setProblem(null);
    api.createExport(job.job_id, { options })
      .then((created) => setExports((list) => [created, ...(list ?? [])]),
            (e: unknown) => setProblem(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  };
  const cancel = (id: string) => {
    api.cancel(id).then(() => refresh(), (e: unknown) => setProblem(e instanceof Error ? e.message : String(e)));
  };

  return (
    <section className="xpanel" aria-label={L.region}>
      <div className="xpanel__form">
        <h2 className="display display--sm">{L.title}</h2>
        <p className="xpanel__lead">{L.lead}</p>
        <fieldset className="xpanel__options" disabled={!ready}>
          <legend>{L.optionsLegend}</legend>
          {OPTION_KEYS.map((key) => (
            <label key={key} className="xopt" title={OPTION_LABELS[key].hint}>
              <input type="checkbox" checked={options[key]}
                     onChange={(e) => setOptions((v) => ({ ...v, [key]: e.target.checked }))} />
              <span>{OPTION_LABELS[key].label}<small>{OPTION_LABELS[key].hint}</small></span>
            </label>
          ))}
        </fieldset>
        <p className="xpanel__note">{L.alwaysShown}</p>
        <button type="button" className="btn btn--primary" onClick={start} disabled={!ready || busy}>
          {busy ? L.queueing : L.start}
        </button>
        {!ready && <p className="inline-note">{L.notReady}</p>}
        {problem && <p className="inline-warn">{problem}</p>}
      </div>
      <div className="xpanel__list">
        <h3 className="xpanel__title">{L.listTitle}</h3>
        <p className="xpanel__lead">{L.listLead}</p>
        {exportsList === null ? (
          <p className="xpanel__empty">{L.loading}</p>
        ) : exportsList.length === 0 ? (
          <p className="xpanel__empty">{L.empty}</p>
        ) : (
          <ul className="xpanel__rows">
            {exportsList.map((exp) => <ExportRow key={exp.job_id} exp={exp} current={job} onCancel={cancel} />)}
          </ul>
        )}
      </div>
    </section>
  );
}
