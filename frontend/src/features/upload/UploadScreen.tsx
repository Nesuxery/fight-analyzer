import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api, urls } from "../../api/client";
import { href, navigate } from "../../app/router";
import type { Job, JobStatus } from "../../contracts/generated";
import { DEMO_POST_SELECTION_S, DEMO_PRE_SELECTION_S, useDemo } from "../../demo/DemoContext";
import { renderDemo } from "../../demo/render";
import { DEMO_DURATION_S, DEMO_FPS, DEMO_FRAME, SCRIPT_EVENTS } from "../../demo/script";
import { useNow } from "../../hooks/useNow";
import { usePolling } from "../../hooks/usePolling";
import {
  ERROR_LABELS, HISTORY_LABELS as H, JOB_STATUS_LABELS, STAGE_LABELS, UPLOAD_LABELS as L,
  formatDateTime, formatNumber, jobScreen,
} from "../../labels";
import { formatClock } from "../../player/clock";
import { Badge, Button, ButtonLink, DemoTag, EmptyState, Progress, SectionHeading, Skeleton } from "../../ui";
import type { BadgeTone } from "../../ui";
import {
  IconAlert, IconArrowRight, IconCpu, IconFilm, IconLock, IconMonitor, IconScorecard, IconUpload, IconUsers, IconWifiOff,
} from "../../ui/icons";
import { OctagonPattern } from "../../ui/OctagonPattern";
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

const NOTES = [
  { icon: <IconMonitor />, text: L.notes.local },
  { icon: <IconWifiOff />, text: L.notes.offline },
  { icon: <IconLock />, text: L.notes.private },
];

const howSteps = (demo: boolean) => [
  { icon: <IconUpload />, ...L.how.upload },
  { icon: <IconCpu />, ...L.how.process },
  { icon: <IconUsers />, ...L.how.select },
  { icon: <IconScorecard />, ...(demo ? L.how.resultDemo : L.how.result) },
];

export function UploadScreen({ demo }: { demo: boolean }) {
  const steps = howSteps(demo);
  return (
    <div className="upload">
      {/* black intro band; the drop card overlaps its bottom edge */}
      <section className="upband on-ink" aria-labelledby="upload-title">
        <OctagonPattern className="upband__pattern upband__pattern--left" />
        <OctagonPattern className="upband__pattern upband__pattern--right" />
        <div className="upband__inner">
          <h1 id="upload-title" className="upband__title">{L.title}</h1>
          <p className="upband__lead">{L.lead}</p>
          <ul className="upband__notes">
            {NOTES.map((n) => <li key={n.text}>{n.icon}{n.text}</li>)}
          </ul>
        </div>
      </section>
      <div className="upload__body">
        <div className="upload__drop">{demo ? <DemoDropZone /> : <DropZone />}</div>
        <section className="how" aria-labelledby="how-title">
          <SectionHeading id="how-title" title={L.how.title} description={L.how.description} />
          <ol className="how__list">
            {steps.map((step, i) => (
              <li key={step.title} className="how__step">
                <span className="how__icon" aria-hidden="true">{step.icon}</span>
                <span className="how__num num">{L.how.step(i + 1)}</span>
                <h3 className="how__title">{step.title}</h3>
                <p className="how__text">{step.text}</p>
                {i < steps.length - 1 && <IconArrowRight className="how__arrow" size={16} />}
              </li>
            ))}
          </ol>
        </section>
        {demo ? <DemoHistory /> : <History />}
      </div>
    </div>
  );
}

function DemoDropZone() {
  const { start } = useDemo();
  return (
    <div className="dropzone dropzone--demo">
      <p className="dropzone__lead">{L.demoLead}</p>
      <Button variant="brand" onClick={() => {
        start();
        navigate({ mode: "demo", screen: "processing" });
      }}>
        {L.demoStart}
      </Button>
      <p className="dropzone__hint">{L.demoHint}</p>
    </div>
  );
}

/** "Geçmiş analizler" with the total in the heading. */
function HistorySection({ total, children }: { total: number | null; children: ReactNode }) {
  return (
    <section className="history" aria-labelledby="history-title">
      <SectionHeading id="history-title" title={H.title} description={H.description}
                      aside={total === null ? undefined : H.count(formatNumber(total))} />
      {children}
    </section>
  );
}

function History() {
  const jobs = usePolling(api.jobs, 5000);
  if (jobs.loading) {
    return (
      <HistorySection total={null}>
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
      </HistorySection>
    );
  }
  if (!jobs.data) {
    return (
      <HistorySection total={null}>
        <div className="history__box">
          <EmptyState tone="error" title={H.errorTitle} compact>
            {H.errorBefore} <code>start.cmd</code> {H.errorAfter}
          </EmptyState>
        </div>
      </HistorySection>
    );
  }
  if (jobs.data.jobs.length === 0) {
    return (
      <HistorySection total={0}>
        <div className="history__box">
          <EmptyState tone="empty" title={H.emptyTitle} icon={<IconFilm />} compact>{H.emptyText}</EmptyState>
        </div>
      </HistorySection>
    );
  }
  return (
    <HistorySection total={jobs.data.total}>
      {jobs.error && <p className="inline-warn history__stale">{H.stale}</p>}
      <ul className="history__list">
        {jobs.data.jobs.map((job) => <HistoryRow key={job.job_id} job={job} />)}
      </ul>
    </HistorySection>
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

/** Number of detected events; empty until the events stage has run. */
function EventCount({ count }: { count: number | null }) {
  return <span className="history__events num">{count === null ? "" : H.events(formatNumber(count))}</span>;
}

/**
 * One analysis. "Aç" is the only link of the row, but its hit area covers the
 * whole row (.history__open::after), so clicking anywhere still opens it.
 */
function HistoryRow({ job }: { job: Job }) {
  const name = job.source?.filename ?? H.untitled(job.job_id.slice(0, 8));
  const v = job.video ?? job.source;
  const meta = [formatDateTime(job.created_at),
                ...(v ? [`${v.width}×${v.height}`, formatClock(v.duration_ms / 1000)] : [H.noVideoInfo])].join(" · ");
  const detail = job.status === "running" && job.stage ? STAGE_LABELS[job.stage]
    : job.status === "awaiting_selection" && job.outputs.pose ? H.posesReady(formatNumber(job.outputs.pose.frame_count))
      : job.status === "failed" && job.error ? (ERROR_LABELS[job.error.code] ?? job.error.message) : null;
  const active = job.status === "running" || job.status === "queued";
  const thumbKey = `${job.outputs.analysis_video?.cache_key ?? ""}-${job.selection?.anchors[0]?.frame_index ?? ""}`;
  return (
    <li className="history__row">
      <Thumb key={thumbKey} job={job} />
      <span className="history__main">
        <span className="history__name">{name}</span>
        <span className="history__meta num">{meta}</span>
        {detail && <span className="history__detail">{detail}</span>}
        {active && <Progress value={job.progress} label={H.progress} className="history__progress" />}
      </span>
      <EventCount count={job.outputs.events?.events ?? null} />
      {/* a failure carries an icon with its text, so it is not read as brand red */}
      <Badge tone={STATUS_TONE[job.status]} icon={job.status === "failed" ? <IconAlert size={16} /> : undefined}>
        {JOB_STATUS_LABELS[job.status]}
      </Badge>
      {/* the link covers the row, so the full file name is its tooltip */}
      <ButtonLink size="sm" className="history__open" aria-label={H.openNamed(name)} title={job.source?.filename}
                  href={href({ mode: "analysis", screen: jobScreen(job), jobId: job.job_id })}>
        {H.open}
      </ButtonLink>
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
    <HistorySection total={1}>
      <ul className="history__list">
        <li className="history__row">
          <DemoThumb />
          <span className="history__main">
            <span className="history__name">{H.demoName} <DemoTag small /></span>
            <span className="history__meta num">{meta}</span>
            {running && <span className="history__detail">{H.demoRunning}</span>}
            {running && <Progress value={progress} label={H.progress} className="history__progress" />}
          </span>
          {/* the scripted events of the synthetic scene, once its "analysis" is done */}
          <EventCount count={running ? null : SCRIPT_EVENTS.length} />
          <Badge tone={running ? "neutral" : "success"}>
            {JOB_STATUS_LABELS[running ? "running" : "completed"]}
          </Badge>
          <ButtonLink size="sm" className="history__open" aria-label={H.openNamed(H.demoName)}
                      href={href({ mode: "demo", screen })}>
            {H.open}
          </ButtonLink>
        </li>
      </ul>
    </HistorySection>
  );
}
