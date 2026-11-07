import { api } from "../../api/client";
import { navigate } from "../../app/router";
import { IconUpload } from "../../components/icons";
import { DemoTag, ProgressBar, StateView } from "../../components/ui";
import type { Job } from "../../contracts/generated";
import { DEMO_POST_SELECTION_S, DEMO_PRE_SELECTION_S, useDemo } from "../../demo/DemoContext";
import { DEMO_DURATION_S, DEMO_FPS, DEMO_FRAME } from "../../demo/script";
import { useNow } from "../../hooks/useNow";
import { usePolling } from "../../hooks/usePolling";
import { ERROR_LABELS, JOB_STATUS_LABELS, STAGE_LABELS, formatDateTime, jobScreen } from "../../labels";
import { formatClock } from "../../player/clock";
import { DropZone } from "./DropZone";

export function UploadScreen({ demo }: { demo: boolean }) {
  return (
    <div className="upload">
      <section className="upload__hero" aria-labelledby="upload-title">
        <h1 id="upload-title" className="display display--xl">Maç videosunu yükle</h1>
        <p className="upload__sub">
          Kayıtlı bir maçı yükleyin, iki dövüşçüyü seçin; iskeletler, hareket istatistikleri ve olay
          zaman çizelgesi video ile senkron görünsün.
        </p>
        {demo ? <DemoDropZone /> : <DropZone />}
      </section>
      <section className="history" aria-labelledby="history-title">
        <div className="section-head">
          <h2 id="history-title" className="display display--sm">Geçmiş analizler</h2>
        </div>
        {demo ? <DemoHistory /> : <History />}
      </section>
    </div>
  );
}

function DemoDropZone() {
  const { start } = useDemo();
  return (
    <div className="dropzone dropzone--demo">
      <IconUpload size={34} className="dropzone__icon" />
      <p className="dropzone__lead">Demo modunda dosya yüklenmez</p>
      <p className="dropzone__hint">
        Sentetik bir örnek sahneyle işlem, seçim ve sonuç ekranlarının tamamını inceleyin.
      </p>
      <button type="button" className="btn btn--primary"
              onClick={() => {
                start();
                navigate({ mode: "demo", screen: "processing" });
              }}>
        Demo analizini başlat
      </button>
    </div>
  );
}

function History() {
  const jobs = usePolling(api.jobs, 5000);
  if (jobs.loading) {
    return (
      <ul className="history__list" aria-busy="true" aria-label="Yükleniyor">
        {[0, 1, 2].map((i) => <li key={i} className="history__row history__row--skeleton" />)}
      </ul>
    );
  }
  if (!jobs.data) {
    return (
      <StateView tone="error" title="Geçmiş analizler alınamadı" compact>
        API'ye ulaşılamıyor. Uygulamayı <code>start.cmd</code> ile başlattığınızdan emin olun;
        bağlantı otomatik olarak yeniden denenecek.
      </StateView>
    );
  }
  if (jobs.data.jobs.length === 0) {
    return (
      <StateView tone="empty" title="Henüz analiz yok" compact>
        Analiz ettiğiniz maçlar burada listelenir ve yeniden işlemeden açılabilir.
      </StateView>
    );
  }
  return (
    <>
      {jobs.error && <p className="inline-warn">Bağlantı kesildi; son bilinen liste gösteriliyor.</p>}
      <ul className="history__list">
        {jobs.data.jobs.map((job) => <HistoryRow key={job.job_id} job={job} />)}
      </ul>
    </>
  );
}

function HistoryRow({ job }: { job: Job }) {
  const open = () => navigate({ mode: "analysis", screen: jobScreen(job), jobId: job.job_id });
  const v = job.video ?? job.source;
  const video = v ? `${v.width}×${v.height} · ${formatClock(v.duration_ms / 1000)}` : "Video bilgisi yok";
  return (
    <li>
      <button type="button" className="history__row" onClick={open}>
        <span className="history__name">
          <span className="history__title" title={job.source?.filename}>
            {job.source?.filename ?? `Analiz ${job.job_id.slice(0, 8)}`}
          </span>
          <span className="history__sub">{formatDateTime(job.created_at)} · {video}</span>
        </span>
        <span className="history__stage">
          {job.status === "running" && job.stage ? STAGE_LABELS[job.stage] : ""}
          {job.status === "awaiting_selection" && job.outputs.pose
            ? `${job.outputs.pose.frame_count} kare · pozlar hazır` : ""}
          {job.status === "failed" && job.error ? (ERROR_LABELS[job.error.code] ?? job.error.message) : ""}
        </span>
        <span className="history__progress">
          <ProgressBar value={job.progress} label="İlerleme"
                       tone={job.status === "failed" ? "error" : "default"} />
        </span>
        <span className={`badge badge--${job.status}`}>{JOB_STATUS_LABELS[job.status]}</span>
      </button>
    </li>
  );
}

function DemoHistory() {
  const { state } = useDemo();
  const now = useNow(1000);
  const elapsedPost = state.selectedAt ? (now - state.selectedAt) / 1000 : 0;
  const done = state.selectedAt !== null && elapsedPost >= DEMO_POST_SELECTION_S;
  const running = state.startedAt !== null && !done;
  const screen = running ? "processing" : "result";
  const progress = done ? 1 : state.startedAt
    ? Math.min(0.7, (now - state.startedAt) / 1000 / (DEMO_PRE_SELECTION_S + DEMO_POST_SELECTION_S))
    : 1;
  return (
    <ul className="history__list">
      <li>
        <button type="button" className="history__row" onClick={() => navigate({ mode: "demo", screen })}>
          <span className="history__name">
            <span className="history__title">Örnek maç <DemoTag small /></span>
            <span className="history__sub">
              Sentetik sahne · {DEMO_FRAME.width}×{DEMO_FRAME.height} · {DEMO_FPS} fps ·{" "}
              {formatClock(DEMO_DURATION_S)}
            </span>
          </span>
          <span className="history__stage">{running ? "Demo işleniyor" : ""}</span>
          <span className="history__progress"><ProgressBar value={progress} label="İlerleme" /></span>
          <span className={`badge badge--${running ? "running" : "completed"}`}>
            {running ? "İşleniyor" : "Tamamlandı"}
          </span>
        </button>
      </li>
    </ul>
  );
}
