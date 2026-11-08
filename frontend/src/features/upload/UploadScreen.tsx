import { useEffect, useRef, useState } from "react";
import { api, urls } from "../../api/client";
import { navigate } from "../../app/router";
import type { Job, JobStatus } from "../../contracts/generated";
import { DEMO_POST_SELECTION_S, DEMO_PRE_SELECTION_S, useDemo } from "../../demo/DemoContext";
import { renderDemo } from "../../demo/render";
import { DEMO_DURATION_S, DEMO_FPS, DEMO_FRAME } from "../../demo/script";
import { useNow } from "../../hooks/useNow";
import { usePolling } from "../../hooks/usePolling";
import {
  ERROR_LABELS, HISTORY_LABELS as H, JOB_STATUS_LABELS, STAGE_LABELS, UPLOAD_LABELS as L,
  formatDateTime, formatNumber, jobScreen,
} from "../../labels";
import { formatClock } from "../../player/clock";
import { Badge, Button, DemoTag, EmptyState, Progress, Skeleton } from "../../ui";
import type { BadgeTone } from "../../ui";
import { DropZone } from "./DropZone";

/** Colour only for states: done, needs the user, failed. */
const STATUS_TONE: Record<JobStatus, BadgeTone> = {
  queued: "neutral",
  running: "neutral",
  awaiting_selection: "warning",
  completed: "success",
  failed: "danger",
  cancelled: "neutral",
};

export function UploadScreen({ demo }: { demo: boolean }) {
  return (
    <div className="upload">
      <section className="upload__hero" aria-labelledby="upload-title">
        <h1 id="upload-title" className="upload__title">{L.title}</h1>
        <p className="upload__lead">{L.lead}</p>
        {demo ? <DemoDropZone /> : <DropZone />}
      </section>
      <section className="history" aria-labelledby="history-title">
        <h2 id="history-title" className="section-title">{H.title}</h2>
        {demo ? <DemoHistory /> : <History />}
      </section>
    </div>
  );
}

function DemoDropZone() {
  const { start } = useDemo();
  return (
    <div className="dropzone dropzone--demo">
      <p className="dropzone__lead">{L.demoLead}</p>
      <Button variant="primary" onClick={() => {
        start();
        navigate({ mode: "demo", screen: "processing" });
      }}>
        {L.demoStart}
      </Button>
      <p className="dropzone__hint">{L.demoHint}</p>
    </div>
  );
}

function History() {
  const jobs = usePolling(api.jobs, 5000);
  if (jobs.loading) {
    return (
      <ul className="history__list" aria-busy="true" aria-label={H.loading}>
        {[0, 1, 2].map((i) => (
          <li key={i} className="history__row history__row--loading">
            <Skeleton className="history__thumb" />
            <span className="history__main">
              <Skeleton className="skeleton--line" />
              <Skeleton className="skeleton--line skeleton--short" />
            </span>
          </li>
        ))}
      </ul>
    );
  }
  if (!jobs.data) {
    return (
      <EmptyState tone="error" title={H.errorTitle} compact>
        {H.errorBefore} <code>start.cmd</code> {H.errorAfter}
      </EmptyState>
    );
  }
  if (jobs.data.jobs.length === 0) {
    return <EmptyState tone="empty" title={H.emptyTitle} compact>{H.emptyText}</EmptyState>;
  }
  return (
    <>
      {jobs.error && <p className="inline-warn history__stale">{H.stale}</p>}
      <ul className="history__list">
        {jobs.data.jobs.map((job) => <HistoryRow key={job.job_id} job={job} />)}
      </ul>
    </>
  );
}

/** 16:9 frame of the analysis copy; a dark empty box until there is one. */
function Thumb({ job }: { job: Job }) {
  const av = job.outputs.analysis_video;
  const [failed, setFailed] = useState(false);
  const version = av ? `${av.cache_key.slice(0, 12)}-${job.selection?.anchors[0]?.frame_index ?? "x"}` : null;
  return (
    <span className="history__thumb" aria-hidden="true">
      {version && !failed && (
        <img src={urls.thumbnail(job.job_id, version)} alt="" loading="lazy" decoding="async"
             onError={() => setFailed(true)} />
      )}
    </span>
  );
}

function HistoryRow({ job }: { job: Job }) {
  const open = () => navigate({ mode: "analysis", screen: jobScreen(job), jobId: job.job_id });
  const v = job.video ?? job.source;
  const meta = [formatDateTime(job.created_at),
                ...(v ? [`${v.width}×${v.height}`, formatClock(v.duration_ms / 1000)] : [H.noVideoInfo])].join(" · ");
  const detail = job.status === "running" && job.stage ? STAGE_LABELS[job.stage]
    : job.status === "awaiting_selection" && job.outputs.pose ? H.posesReady(formatNumber(job.outputs.pose.frame_count))
      : job.status === "failed" && job.error ? (ERROR_LABELS[job.error.code] ?? job.error.message) : null;
  const active = job.status === "running" || job.status === "queued";
  const thumbKey = `${job.outputs.analysis_video?.cache_key ?? ""}-${job.selection?.anchors[0]?.frame_index ?? ""}`;
  return (
    <li>
      <button type="button" className="history__row" onClick={open}>
        <Thumb key={thumbKey} job={job} />
        <span className="history__main">
          <span className="history__name" title={job.source?.filename}>
            {job.source?.filename ?? H.untitled(job.job_id.slice(0, 8))}
          </span>
          <span className="history__meta num">{meta}</span>
          {detail && <span className="history__detail">{detail}</span>}
          {active && <Progress value={job.progress} label={H.progress} className="history__progress" />}
        </span>
        <Badge tone={STATUS_TONE[job.status]}>{JOB_STATUS_LABELS[job.status]}</Badge>
      </button>
    </li>
  );
}

const DEMO_THUMB_T = 12;
const NO_LAYERS = { skeleton: false, strikes: false, distance: false };

/** The demo has no video file: its preview frame is drawn from the synthetic scene. */
function DemoThumb() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    ctx.setTransform(canvas.width / DEMO_FRAME.width, 0, 0, canvas.height / DEMO_FRAME.height, 0, 0);
    renderDemo(ctx, DEMO_THUMB_T, { layers: NO_LAYERS, assignment: null });
  }, []);
  return (
    <span className="history__thumb" aria-hidden="true">
      <canvas ref={ref} width={224} height={126} />
    </span>
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
  const meta = [H.demoMeta, `${DEMO_FRAME.width}×${DEMO_FRAME.height}`, `${DEMO_FPS} fps`, formatClock(DEMO_DURATION_S)].join(" · ");
  return (
    <ul className="history__list">
      <li>
        <button type="button" className="history__row" onClick={() => navigate({ mode: "demo", screen })}>
          <DemoThumb />
          <span className="history__main">
            <span className="history__name">{H.demoName} <DemoTag small /></span>
            <span className="history__meta num">{meta}</span>
            {running && <span className="history__detail">{H.demoRunning}</span>}
            {running && <Progress value={progress} label={H.progress} className="history__progress" />}
          </span>
          <Badge tone={running ? "neutral" : "success"}>
            {JOB_STATUS_LABELS[running ? "running" : "completed"]}
          </Badge>
        </button>
      </li>
    </ul>
  );
}
