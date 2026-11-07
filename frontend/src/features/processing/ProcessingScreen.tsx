import { useCallback, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../../api/client";
import type { PipelineStage } from "../../contracts/generated";
import { navigate } from "../../app/router";
import { IconAlert, IconCheck, IconTarget } from "../../components/icons";
import { DemoTag, ProgressBar, StateView } from "../../components/ui";
import { useDemo } from "../../demo/DemoContext";
import { renderDemo } from "../../demo/render";
import { DEMO_DURATION_S, DEMO_FPS, DEMO_FRAME } from "../../demo/script";
import { useJob } from "../../hooks/useJob";
import { useNow } from "../../hooks/useNow";
import { ERROR_LABELS, JOB_STATUS_LABELS, formatBytes, formatDateTime, formatNumber } from "../../labels";
import { formatClock } from "../../player/clock";
import { VideoStage } from "../../player/VideoStage";
import { PosePreviewPanel } from "./PosePreviewPanel";
import { PoseReview } from "./PoseReview";
import { demoProcess, jobProcess } from "./steps";
import type { ProcessView, StepView } from "./steps";

const NO_LAYERS = { skeleton: false, strikes: false, distance: false };
const SKELETON_ONLY = { skeleton: true, strikes: false, distance: false };

export function ProcessingScreen({ demo, jobId }: { demo: boolean; jobId?: string }) {
  return demo ? <DemoProcessing /> : <JobProcessing jobId={jobId!} />;
}

function DemoProcessing() {
  const { state, start } = useDemo();
  const now = useNow(200);
  const view = demoProcess(state, now, DEMO_DURATION_S);
  const assigned = state.selectedAt !== null;
  const draw = useCallback(
    (ctx: CanvasRenderingContext2D, t: number) =>
      renderDemo(ctx, t, { layers: t > 0 ? SKELETON_ONLY : NO_LAYERS, assignment: assigned ? state.assignment : null }),
    [assigned, state.assignment],
  );
  const previewT = view.previewTimeS ?? 0;
  const frame = Math.round(previewT * DEMO_FPS);

  if (view.phase === "notStarted") {
    return (
      <StateView tone="empty" title="Demo analizi henüz başlatılmadı"
                 action={<button type="button" className="btn btn--primary" onClick={start}>Demo analizini başlat</button>}>
        Örnek sahne üzerinde işlem adımlarının nasıl ilerlediğini izleyin.
      </StateView>
    );
  }

  return (
    <ProcessLayout
      view={view}
      title={<>Örnek maç <DemoTag small /></>}
      meta={[
        ["Kaynak", "Sentetik demo sahnesi"],
        ["Video", `${DEMO_FRAME.width}×${DEMO_FRAME.height} · ${DEMO_FPS} fps`],
        ["Süre", formatClock(DEMO_DURATION_S)],
      ]}
      preview={
        <VideoStage frame={DEMO_FRAME} getTime={() => previewT} draw={draw} label="İşlenen kare önizlemesi (demo)">
          {view.steps[0]!.status === "active" && <div className="stage__veil">Video hazırlanıyor…</div>}
        </VideoStage>
      }
      frameLabel={`Kare ${frame.toLocaleString("tr-TR")} / ${(DEMO_DURATION_S * DEMO_FPS).toLocaleString("tr-TR")}`}
      actions={
        <>
          {view.phase === "awaitingSelection" && (
            <button type="button" className="btn btn--primary" onClick={() => navigate({ mode: "demo", screen: "select" })}>
              <IconTarget /> Dövüşçüleri seç
            </button>
          )}
          {view.phase === "done" && (
            <button type="button" className="btn btn--primary" onClick={() => navigate({ mode: "demo", screen: "result" })}>
              Sonuçları aç
            </button>
          )}
          <button type="button" className="btn btn--ghost" onClick={start}>Demo'yu baştan başlat</button>
        </>
      }
    />
  );
}

function JobProcessing({ jobId }: { jobId: string }) {
  const job = useJob(jobId, 1000);
  if (job.loading) return <StateView tone="loading" title="Analiz bilgisi yükleniyor…" />;
  if (job.notFound) {
    return (
      <StateView tone="error" title="Analiz bulunamadı"
                 action={<a className="btn btn--ghost" href="#/">Yükleme ekranına dön</a>}>
        <span className="mono">{jobId}</span> kimlikli bir analiz kaydı yok.
      </StateView>
    );
  }
  if (!job.data) {
    return (
      <StateView tone="error" title="Analiz durumu alınamadı">
        API'ye ulaşılamıyor; bağlantı otomatik olarak yeniden denenecek.
      </StateView>
    );
  }
  const data = job.data;
  const view = jobProcess(data);
  const src = data.source;
  const av = data.outputs.analysis_video;
  const pose = data.outputs.pose;
  const video = av?.video ?? data.video;
  const detail = data.progress_detail;
  const aspect = video ? `${video.width} / ${video.height}` : src ? `${src.width} / ${src.height}` : "16 / 9";

  let preview: ReactNode;
  let previewTitle = "İşlenen kare";
  if (data.status === "awaiting_selection" && av && pose) {
    previewTitle = "Poz önizleme · tüm kişiler";
    preview = <PoseReview jobId={jobId} video={av.video} />;
  } else if (data.status === "running" && detail?.stage === "pose" && detail.preview_seq) {
    preview = <PosePreviewPanel jobId={jobId} seq={detail.preview_seq} fallbackAspect={aspect} />;
  } else {
    const text = data.status === "queued" ? "Analiz sırada bekliyor."
      : data.status === "running" ? RUNNING_TEXT[data.stage ?? "video_prep"]
        : data.status === "cancelled" ? "Analiz iptal edildi."
          : data.status === "failed" ? "Analiz tamamlanamadı." : "Önizleme yok.";
    preview = (
      <div className="stage stage--empty" style={{ aspectRatio: aspect }}>
        <StateView tone={data.status === "running" || data.status === "queued" ? "loading" : "empty"}
                   title={text} compact />
      </div>
    );
  }

  const meta: [string, string][] = [["Durum", JOB_STATUS_LABELS[data.status]]];
  if (src) {
    meta.push(["Kaynak", `${formatBytes(src.size_bytes)} · ${formatDateTime(data.created_at)}`]);
    meta.push(["Kaynak video", `${src.width}×${src.height}` +
      (src.fps ? ` · ${formatNumber(src.fps, 2)} fps` : "") + ` · ${formatClock(src.duration_ms / 1000, true)}` +
      (src.rotation_deg ? ` · ${src.rotation_deg}° döndürüldü` : "") + (src.has_audio ? " · sesli" : " · sessiz")]);
  }
  if (av) {
    const v = av.video;
    meta.push(["Analiz kopyası", `${v.width}×${v.height} · ${v.fps_num}/${v.fps_den} fps sabit · ` +
      `${formatNumber(v.frame_count)} kare · ${formatBytes(av.size_bytes)}`]);
  }
  if (pose) {
    meta.push(["Model", `${pose.model.name} · ${pose.model.device ?? "?"} · ${pose.settings.imgsz} px`]);
  }

  const cancellable = data.status === "queued" || data.status === "running" || data.status === "awaiting_selection";
  return (
    <ProcessLayout
      view={view}
      title={<span title={src?.filename}>{src?.filename ?? `Analiz ${data.job_id.slice(0, 8)}`}</span>}
      stale={Boolean(job.error)}
      meta={meta}
      preview={preview}
      previewTitle={previewTitle}
      errorDetail={data.error && ERROR_LABELS[data.error.code] ? data.error.message : null}
      frameLabel={video ? `${formatNumber(video.frame_count)} kare` : "—"}
      actions={
        <>
          {view.phase === "done" && (
            <button type="button" className="btn btn--primary"
                    onClick={() => navigate({ mode: "analysis", screen: "result", jobId })}>Sonuçları aç</button>
          )}
          {view.phase === "awaitingSelection" && data.outputs.tracking_prep && (
            <button type="button" className="btn btn--primary"
                    onClick={() => navigate({ mode: "analysis", screen: "select", jobId })}>
              <IconTarget /> Dövüşçüleri seç
            </button>
          )}
          {view.phase === "awaitingSelection" && !data.outputs.tracking_prep && (
            <button type="button" className="btn btn--primary"
                    onClick={() => void api.retry(jobId)}>
              Aday kareleri hazırla
            </button>
          )}
          {view.phase === "done" && data.outputs.tracking && (
            <button type="button" className="btn btn--ghost"
                    onClick={() => navigate({ mode: "analysis", screen: "select", jobId })}>
              <IconTarget /> Yeniden seç
            </button>
          )}
          {(data.status === "failed" || data.status === "cancelled") && (
            <button type="button" className="btn btn--primary"
                    onClick={() => void api.retry(jobId).catch(() => undefined)}>
              Analizi yeniden başlat
            </button>
          )}
          {cancellable && <CancelButton jobId={jobId} />}
          <a className="btn btn--ghost" href="#/">{cancellable ? "Yükleme ekranı" : "Yeni video yükle"}</a>
        </>
      }
    />
  );
}

/** Shown while no preview frame exists for the running stage. */
const RUNNING_TEXT: Record<PipelineStage, string> = {
  video_prep: "Video analiz kopyasına dönüştürülüyor…",
  pose: "Poz modeli hazırlanıyor…",
  tracking_prep: "Kamera kesimleri ve iz parçaları hazırlanıyor…",
  tracking: "Dövüşçü kimlikleri video boyunca eşleniyor…",
  events: "Hareketler ve olaylar ölçülüyor…",
  scoring: "Deneysel momentum hesaplanıyor…",
  export: "Dışa aktarılıyor…",
};

function CancelButton({ jobId }: { jobId: string }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!confirming) {
    return <button type="button" className="btn btn--ghost" onClick={() => setConfirming(true)}>İptal et</button>;
  }
  return (
    <span className="confirm" role="group" aria-label="İptali onayla">
      <span>Analiz iptal edilsin mi?</span>
      <button type="button" className="btn btn--danger btn--sm" disabled={busy}
              onClick={() => {
                setBusy(true);
                api.cancel(jobId).then(() => setConfirming(false),
                  (err: unknown) => setError(err instanceof Error ? err.message : String(err)))
                  .finally(() => setBusy(false));
              }}>
        Evet, iptal et
      </button>
      <button type="button" className="btn btn--ghost btn--sm" onClick={() => setConfirming(false)}>Vazgeç</button>
      {error && <span className="confirm__error">{error}</span>}
    </span>
  );
}

function ProcessLayout({ view, title, meta, preview, frameLabel, actions, stale = false,
                        previewTitle = "İşlenen kare", errorDetail = null }: {
  view: ProcessView;
  title: ReactNode;
  meta: [string, string][];
  preview: ReactNode;
  frameLabel: string;
  actions: ReactNode;
  stale?: boolean;
  previewTitle?: string;
  errorDetail?: string | null;
}) {
  const pct = Math.round(view.overall * 100);
  return (
    <div className="proc">
      <section className="card proc__preview" aria-label="İşlenen kare">
        <header className="card__head">
          <h2 className="display display--sm">{previewTitle}</h2>
          <span className="num card__aside">{frameLabel}</span>
        </header>
        {preview}
      </section>

      <aside className="card proc__side" aria-label="Analiz aşamaları">
        <header className="card__head">
          <h2 className="display display--sm">{title}</h2>
        </header>
        {stale && <p className="inline-warn">Bağlantı kesildi; son bilinen durum gösteriliyor.</p>}
        <div className="proc__overall">
          <span className="display display--num">{pct}<small>%</small></span>
          <ProgressBar value={view.overall} label="Toplam ilerleme" tone={view.phase === "failed" ? "error" : "default"} />
        </div>
        {view.phase === "failed" && view.errorText && (
          <div className="alert" role="alert">
            <IconAlert />
            <span>{view.errorText}{errorDetail && <small className="alert__detail">{errorDetail}</small>}</span>
          </div>
        )}
        {view.phase === "queued" && <p className="proc__note">Analiz sırada; işçi boşaldığında başlayacak.</p>}
        <ol className="vsteps">
          {view.steps.map((s, i) => <StepRow key={s.id} step={s} index={i} />)}
        </ol>
        <div className="proc__actions">{actions}</div>
        <dl className="kv">
          {meta.map(([k, v]) => (
            <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
          ))}
        </dl>
      </aside>
    </div>
  );
}

const STATUS_TEXT = {
  waiting: "Bekliyor", active: "Sürüyor", done: "Tamamlandı", error: "Hata", stopped: "İptal edildi", action: "Sizi bekliyor",
} as const;

function StepRow({ step, index }: { step: StepView; index: number }) {
  return (
    <li className={`vsteps__item is-${step.status}`}>
      <span className="vsteps__marker" aria-hidden="true">
        {step.status === "done" ? <IconCheck size={14} /> : step.status === "error" ? "!" : index + 1}
      </span>
      <div className="vsteps__body">
        <div className="vsteps__row">
          <span className="vsteps__label">{step.label}</span>
          <span className="vsteps__status">
            {step.status === "active" && step.progress !== null ? `${Math.round(step.progress * 100)}%` : STATUS_TEXT[step.status]}
          </span>
        </div>
        {step.status === "active" && step.progress !== null && <ProgressBar value={step.progress} label={step.label} />}
        {step.detail && <p className="vsteps__detail">{step.detail}</p>}
      </div>
    </li>
  );
}
