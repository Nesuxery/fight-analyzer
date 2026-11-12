import { useCallback, useId, useState } from "react";
import type { ComponentType, ReactNode } from "react";
import { api } from "../../api/client";
import { navigate } from "../../app/router";
import { useDemo } from "../../demo/DemoContext";
import { renderDemo } from "../../demo/render";
import { DEMO_DURATION_S, DEMO_FPS, DEMO_FRAME } from "../../demo/script";
import { useJob } from "../../hooks/useJob";
import { useNow } from "../../hooks/useNow";
import {
  COMMON_LABELS, DEMO_STEP_DESCRIPTIONS, ERROR_LABELS, HISTORY_LABELS, JOB_STATUS_LABELS, PROCESSING_LABELS as L,
  PROCESS_STEP_DESCRIPTIONS, UI_LABELS, formatBytes, formatDateTime, formatDuration, formatNumber,
} from "../../labels";
import { formatClock } from "../../player/clock";
import { VideoStage } from "../../player/VideoStage";
import {
  Button, ButtonLink, Card, CardHeader, DemoTag, Dialog, EmptyState, HelpTip, Progress, SectionHeading, cx, useToast,
} from "../../ui";
import { IconAlert, IconCheck, IconCircle, IconSpinner, IconStop, IconTarget } from "../../ui/icons";
import type { IconProps } from "../../ui/icons";
import { PosePreviewPanel } from "./PosePreviewPanel";
import { PoseReview } from "./PoseReview";
import { demoProcess, jobProcess } from "./steps";
import type { ProcessView, StepStatus, StepView } from "./steps";
import type { StepId } from "../../labels";

const NO_LAYERS = { skeleton: false, strikes: false, distance: false };
const SKELETON_ONLY = { skeleton: true, strikes: false, distance: false };

const messageOf = (e: unknown) => (e instanceof Error ? e.message : String(e));

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
      <EmptyState tone="empty" title={L.demoNotStartedTitle}
                  action={<Button variant="primary" onClick={start}>{L.demoStart}</Button>}>
        {L.demoNotStartedText}
      </EmptyState>
    );
  }

  return (
    <ProcessLayout
      view={view}
      descriptions={DEMO_STEP_DESCRIPTIONS}
      title={<>{HISTORY_LABELS.demoName} <DemoTag small /></>}
      meta={[
        [L.meta.source, L.demoSource],
        [L.meta.video, `${DEMO_FRAME.width}×${DEMO_FRAME.height} · ${DEMO_FPS} fps`],
        [L.meta.duration, formatClock(DEMO_DURATION_S)],
      ]}
      preview={
        <VideoStage frame={DEMO_FRAME} getTime={() => previewT} draw={draw} label={L.demoPreview}>
          {view.steps[0]!.status === "active" && <div className="stage__veil">{L.preparing}</div>}
        </VideoStage>
      }
      frameLabel={L.frameOf(frame.toLocaleString("tr-TR"), (DEMO_DURATION_S * DEMO_FPS).toLocaleString("tr-TR"))}
      actions={
        <>
          {view.phase === "awaitingSelection" && (
            <Button variant="primary" icon={<IconTarget />} onClick={() => navigate({ mode: "demo", screen: "select" })}>
              {L.selectFighters}
            </Button>
          )}
          {view.phase === "done" && (
            <Button variant="primary" onClick={() => navigate({ mode: "demo", screen: "result" })}>{L.openResults}</Button>
          )}
          <Button variant="ghost" onClick={start}>{L.demoRestart}</Button>
        </>
      }
    />
  );
}

function JobProcessing({ jobId }: { jobId: string }) {
  const job = useJob(jobId, 1000);
  const toast = useToast();
  if (job.loading) return <EmptyState tone="loading" title={L.loading} />;
  if (job.notFound) {
    return (
      <EmptyState tone="error" title={L.notFoundTitle}
                  action={<ButtonLink href="#/">{COMMON_LABELS.backToUpload}</ButtonLink>}>
        <span className="mono">{jobId}</span> {L.notFoundText}
      </EmptyState>
    );
  }
  if (!job.data) return <EmptyState tone="error" title={L.unreachableTitle}>{L.unreachableText}</EmptyState>;

  const data = job.data;
  const view = jobProcess(data);
  const src = data.source;
  const av = data.outputs.analysis_video;
  const pose = data.outputs.pose;
  const video = av?.video ?? data.video;
  const detail = data.progress_detail;
  const aspect = video ? `${video.width} / ${video.height}` : src ? `${src.width} / ${src.height}` : "16 / 9";
  const retry = () => {
    api.retry(jobId).catch((e: unknown) => toast({ tone: "danger", message: L.restartFailed(messageOf(e)) }));
  };

  let preview: ReactNode;
  let previewTitle: string = L.previewTitle;
  let previewDescription: string = L.previewDescription;
  if (data.status === "awaiting_selection" && av && pose) {
    previewTitle = L.previewPoses;
    previewDescription = L.previewPosesDescription;
    preview = <PoseReview jobId={jobId} video={av.video} />;
  } else if (data.status === "running" && detail?.stage === "pose" && detail.preview_seq) {
    preview = <PosePreviewPanel jobId={jobId} seq={detail.preview_seq} fallbackAspect={aspect} />;
  } else {
    const text = data.status === "queued" ? L.queuedPreview
      : data.status === "running" ? L.running[data.stage ?? "video_prep"]
        : data.status === "cancelled" ? L.cancelledPreview
          : data.status === "failed" ? L.failedPreview : L.noPreview;
    preview = (
      <div className="stage stage--empty" style={{ aspectRatio: aspect }}>
        <EmptyState tone={data.status === "running" || data.status === "queued" ? "loading" : "empty"} title={text} compact />
      </div>
    );
  }

  const meta: [string, string][] = [[L.meta.status, JOB_STATUS_LABELS[data.status]]];
  if (src) {
    meta.push([L.meta.source, `${formatBytes(src.size_bytes)} · ${formatDateTime(data.created_at)}`]);
    meta.push([L.meta.sourceVideo, `${src.width}×${src.height}` +
      (src.fps ? ` · ${formatNumber(src.fps, 2)} fps` : "") + ` · ${formatClock(src.duration_ms / 1000, true)}` +
      (src.rotation_deg ? L.rotated(src.rotation_deg) : "") + (src.has_audio ? L.withAudio : L.silent)]);
  }
  if (av) {
    const v = av.video;
    meta.push([L.meta.analysisCopy, `${v.width}×${v.height} · ${L.constantFps(v.fps_num, v.fps_den)} · ` +
      `${L.frames(formatNumber(v.frame_count))} · ${formatBytes(av.size_bytes)}`]);
  }
  if (pose) {
    meta.push([L.meta.model, `${pose.model.name} · ${pose.model.device ?? "?"} · ${pose.settings.imgsz} px`]);
  }

  const cancellable = data.status === "queued" || data.status === "running" || data.status === "awaiting_selection";
  return (
    <ProcessLayout
      view={view}
      title={<span title={src?.filename}>{src?.filename ?? L.untitled(data.job_id.slice(0, 8))}</span>}
      stale={Boolean(job.error)}
      meta={meta}
      preview={preview}
      previewTitle={previewTitle}
      previewDescription={previewDescription}
      errorDetail={data.error && ERROR_LABELS[data.error.code] ? data.error.message : null}
      frameLabel={video ? L.frames(formatNumber(video.frame_count)) : UI_LABELS.noValue}
      actions={
        <>
          {view.phase === "done" && (
            <Button variant="primary" onClick={() => navigate({ mode: "analysis", screen: "result", jobId })}>
              {L.openResults}
            </Button>
          )}
          {view.phase === "awaitingSelection" && data.outputs.tracking_prep && (
            <Button variant="primary" icon={<IconTarget />}
                    onClick={() => navigate({ mode: "analysis", screen: "select", jobId })}>
              {L.selectFighters}
            </Button>
          )}
          {view.phase === "awaitingSelection" && !data.outputs.tracking_prep && (
            <Button variant="primary" onClick={retry}>{L.prepareCandidates}</Button>
          )}
          {view.phase === "done" && data.outputs.tracking && (
            <Button icon={<IconTarget />} onClick={() => navigate({ mode: "analysis", screen: "select", jobId })}>
              {L.reselect}
            </Button>
          )}
          {(data.status === "failed" || data.status === "cancelled") && (
            <Button variant="primary" onClick={retry}>{L.restart}</Button>
          )}
          {cancellable && <CancelButton jobId={jobId} />}
          <ButtonLink variant="ghost" href="#/">{cancellable ? L.uploadScreen : L.newUpload}</ButtonLink>
        </>
      }
    />
  );
}

/** "İptal" asks first in a dialog; the job can be started again later. */
function CancelButton({ jobId }: { jobId: string }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();
  const close = () => {
    if (busy) return;
    setOpen(false);
    setError(null);
  };
  const confirm = () => {
    setBusy(true);
    setError(null);
    api.cancel(jobId).then(
      () => {
        setOpen(false);
        toast({ message: L.cancelled });
      },
      (e: unknown) => setError(messageOf(e)),
    ).finally(() => setBusy(false));
  };
  return (
    <>
      <Button onClick={() => setOpen(true)}>{L.cancel}</Button>
      <Dialog open={open} onClose={close} title={L.cancelTitle}
              actions={
                <>
                  <Button onClick={close} disabled={busy}>{L.cancelKeep}</Button>
                  <Button variant="primary" onClick={confirm} disabled={busy}>{L.cancelConfirm}</Button>
                </>
              }>
        <p>{L.cancelBody}</p>
        {error && <div className="alert" role="alert"><IconAlert /><span>{error}</span></div>}
      </Dialog>
    </>
  );
}

function ProcessLayout({ view, title, meta, preview, frameLabel, actions, stale = false,
                        previewTitle = L.previewTitle, previewDescription = L.previewDescription,
                        errorDetail = null, descriptions = PROCESS_STEP_DESCRIPTIONS }: {
  view: ProcessView;
  title: ReactNode;
  meta: [string, string][];
  preview: ReactNode;
  frameLabel: string;
  actions: ReactNode;
  stale?: boolean;
  previewTitle?: string;
  previewDescription?: string;
  errorDetail?: string | null;
  /** What each step does; the demo has its own where its result differs. */
  descriptions?: Record<StepId, string>;
}) {
  const previewId = useId();
  const pct = Math.round(view.overall * 100);
  const showEta = view.phase === "running";
  return (
    <div className="proc">
      <section className="proc__preview" aria-labelledby={previewId}>
        <SectionHeading id={previewId} title={previewTitle} description={previewDescription}
                        aside={<span className="proc__frame">{frameLabel}</span>} />
        {preview}
      </section>

      <Card tag="aside" className="proc__panel" aria-label={L.stepsLabel}>
        <CardHeader title={title} description={L.panelDescription} />
        <div className="proc__body">
          {stale && <p className="inline-warn">{L.stale}</p>}
          {view.phase === "failed" && view.errorText && (
            <div className="alert" role="alert">
              <IconAlert />
              <span>{view.errorText}{errorDetail && <small className="alert__detail">{errorDetail}</small>}</span>
            </div>
          )}
          {view.phase === "queued" && <p className="proc__note">{L.queued}</p>}
          <ol className="vsteps">
            {view.steps.map((s) => <StepRow key={s.id} step={s} description={descriptions[s.id]} />)}
          </ol>
          <div className="proc__overall">
            <div className="proc__overallhead">
              <span className="label proc__term">
                {L.overall}
                <HelpTip label={UI_LABELS.help(L.overall)} align="start">{L.overallHelp}</HelpTip>
              </span>
              <span className="proc__pct num"><small>%</small>{pct}</span>
            </div>
            <Progress value={view.overall} label={L.overall} tone={view.phase === "failed" ? "danger" : "default"} />
            {showEta && (
              <p className="proc__eta">
                <span className="label proc__term">
                  {L.eta}
                  <HelpTip label={UI_LABELS.help(L.eta)} align="start">{L.etaHelp}</HelpTip>
                </span>
                <span className="proc__etavalue num">
                  {view.etaS !== null ? `~${formatDuration(view.etaS)}` : L.etaUnknown}
                </span>
                {view.etaS !== null && view.etaStep && <span className="proc__etanote">{L.etaStage(view.etaStep)}</span>}
              </p>
            )}
          </div>
          <div className="proc__actions">{actions}</div>
          <dl className="kv" aria-label={L.videoInfo}>
            {meta.map(([k, v]) => (
              <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
            ))}
          </dl>
        </div>
      </Card>
    </div>
  );
}

const STEP_ICON: Record<StepStatus, ComponentType<IconProps>> = {
  waiting: IconCircle,
  active: IconSpinner,
  done: IconCheck,
  error: IconAlert,
  stopped: IconStop,
  action: IconTarget,
};

/** One stage: status icon, name, status or percentage, what the stage does, its own progress and details. */
function StepRow({ step, description }: { step: StepView; description: string }) {
  const Icon = STEP_ICON[step.status];
  const pct = step.status === "active" && step.progress !== null ? Math.round(step.progress * 100) : null;
  return (
    <li className={`vsteps__item is-${step.status}`}>
      <Icon className={cx("vsteps__icon", step.status === "active" && "icon-spin")} />
      <div className="vsteps__body">
        <div className="vsteps__row">
          <span className="vsteps__label">{step.label}</span>
          <span className="vsteps__status num">{pct !== null ? `%${pct}` : L.status[step.status]}</span>
        </div>
        <p className="vsteps__desc">{description}</p>
        {pct !== null && <Progress value={step.progress} label={step.label} />}
        {step.detail && <p className="vsteps__detail">{step.detail}</p>}
      </div>
    </li>
  );
}
