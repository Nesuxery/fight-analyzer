import { useCallback, useEffect, useState } from "react";
import { api, urls } from "../../api/client";
import type { ExportFileKind, ExportOptions, Job } from "../../contracts/generated";
import { ERROR_LABELS, JOB_STATUS_LABELS, formatBytes, formatDateTime, formatDuration } from "../../labels";

const OPTION_LABELS: { key: keyof ExportOptions; label: string; hint: string }[] = [
  { key: "skeleton", label: "İskeletler", hint: "Kırmızı ve mavi köşenin eklem ve uzuvları" },
  { key: "effects", label: "Olay efektleri", hint: "Vuruş vurgusu, olası temas halkası, olası knockdown/takedown uyarısı" },
  { key: "momentum", label: "Momentum çubuğu", hint: "Üstte isimler ve deneysel momentum yüzdeleri" },
  { key: "counters", label: "Sayaçlar", hint: "İsimlerin altında vuruş ve tekme denemeleri" },
  { key: "distance", label: "Mesafe", hint: "Dövüşçüler arası mesafe çizgisi (gövde boyu)" },
  { key: "others", label: "Diğer kişiler", hint: "Hakem ve seyirciler gri, ince çizgiyle" },
];
const DEFAULT_OPTIONS: ExportOptions = {
  skeleton: true, effects: true, momentum: true, counters: true, distance: false, others: false,
};
const FILE_LABELS: Record<ExportFileKind, string> = {
  video: "MP4 video",
  metrics: "Kare metrikleri (CSV)",
  bundle: "Olaylar ve ayarlar (JSON)",
};
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
        <span className={`tag ${exp.status === "failed" ? "tag--danger" : exp.status === "completed" ? "tag--ok" : "tag--muted"}`}>
          {JOB_STATUS_LABELS[exp.status]}
        </span>
        {exp.fighters.length === 2 && (
          <span className="xrow__names">{exp.fighters[0]!.display_name} – {exp.fighters[1]!.display_name}</span>
        )}
        {outdated && (
          <span className="tag tag--amber" title="Bu dosyalar, taraflar ya da seçim değişmeden önceki sonuçlardan üretildi.">
            Önceki sonuçlardan
          </span>
        )}
        {active && (
          <button type="button" className="btn btn--sm btn--ghost" onClick={() => onCancel(exp.job_id)}>İptal</button>
        )}
      </div>
      {active && (
        <div className="xrow__progress">
          <span className="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100}
                aria-valuenow={Math.round(exp.progress * 100)} aria-label="Dışa aktarma ilerlemesi">
            <span className="bar__fill" style={{ width: `${exp.progress * 100}%` }} />
          </span>
          <span className="xrow__msg">
            {exp.status === "queued" ? "Sırada: işçi boşalınca başlar (önceki işler bitince)." : exp.message}
            {eta != null && <> · kalan ~{formatDuration(eta)}</>}
          </span>
        </div>
      )}
      {exp.status === "failed" && exp.error && (
        <p className="xrow__error">{ERROR_LABELS[exp.error.code] ?? exp.error.message}</p>
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
            {summary.frames} kare · {summary.events} olay · son karede kırmızı %{summary.final_red_share.toFixed(0)}
            {" "}· {summary.has_audio ? "ses korundu" : "kaynakta ses yok"}
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
    <section className="xpanel" aria-label="Dışa aktarma">
      <div className="xpanel__form">
        <h2 className="display display--sm">Paylaşılabilir çıktı</h2>
        <p className="xpanel__lead">
          Videonun analiz kopyası, seçilen göstergeler işlenerek MP4 olarak yazılır; ses varsa olduğu gibi korunur.
          Kare bazlı metrikler (CSV) ile olaylar, momentum kayıtları ve ayarlar (JSON) her zaman eklenir. Sayılar bu
          ekrandakiyle aynı analiz verisinden hesaplanır. Dosyalar bu bilgisayarda kalır.
        </p>
        <fieldset className="xpanel__options" disabled={!ready}>
          <legend>Videoya işlenecekler</legend>
          {OPTION_LABELS.map((o) => (
            <label key={o.key} className="xopt" title={o.hint}>
              <input type="checkbox" checked={options[o.key]}
                     onChange={(e) => setOptions((v) => ({ ...v, [o.key]: e.target.checked }))} />
              <span>{o.label}<small>{o.hint}</small></span>
            </label>
          ))}
        </fieldset>
        <p className="xpanel__note">
          Kimlik örtüşmesi/belirsizliği ve “veri yetersiz” uyarıları seçeneklerden bağımsız olarak videoda gösterilir.
        </p>
        <button type="button" className="btn btn--primary" onClick={start} disabled={!ready || busy}>
          {busy ? "Kuyruğa alınıyor…" : "Dışa aktarmayı başlat"}
        </button>
        {!ready && <p className="inline-note">Önce hareket analizi ve momentum tamamlanmalı.</p>}
        {problem && <p className="inline-warn">{problem}</p>}
      </div>
      <div className="xpanel__list">
        <h3 className="xpanel__title">Dışa aktarmalar</h3>
        <p className="xpanel__lead">
          Dışa aktarma ayrı bir iş olarak arka planda çalışır; bu sırada videoyu izlemeye devam edebilirsiniz.
        </p>
        {exportsList === null ? (
          <p className="xpanel__empty">Yükleniyor…</p>
        ) : exportsList.length === 0 ? (
          <p className="xpanel__empty">Henüz dışa aktarma yok.</p>
        ) : (
          <ul className="xpanel__rows">
            {exportsList.map((exp) => <ExportRow key={exp.job_id} exp={exp} current={job} onCancel={cancel} />)}
          </ul>
        )}
      </div>
    </section>
  );
}
