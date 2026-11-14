import type { Job, StageProgress } from "../../contracts/generated";
import { DEMO_POST_SELECTION_S, DEMO_PRE_SELECTION_S } from "../../demo/DemoContext";
import type { DemoState } from "../../demo/DemoContext";
import { ERROR_LABELS, PROCESS_STEPS, STEP_LABELS as L, formatBytes, formatDuration, formatNumber } from "../../labels";
import type { StepId } from "../../labels";

/** "stopped": cancelled by the user (not an error). */
export type StepStatus = "waiting" | "active" | "done" | "error" | "stopped" | "action";

export interface StepView {
  id: StepId;
  label: string;
  status: StepStatus;
  /** 0..1 within the step, null when unknown. */
  progress: number | null;
  detail: string | null;
}

export interface ProcessView {
  steps: StepView[];
  overall: number;
  /** Seconds of video processed so far (pose detection), null if unknown. */
  previewTimeS: number | null;
  phase: "notStarted" | "running" | "awaitingSelection" | "done" | "failed" | "queued" | "cancelled";
  errorText: string | null;
  /** Estimated seconds left, measured for the running step only (null: not known). */
  etaS: number | null;
  /** Label of the step the estimate refers to. */
  etaStep: string | null;
}

const steps = (status: (id: StepId) => Omit<StepView, "id" | "label">): StepView[] =>
  PROCESS_STEPS.map((s) => ({ id: s.id, label: s.label, ...status(s.id) }));

const labelOf = (id: StepId) => PROCESS_STEPS.find((s) => s.id === id)?.label ?? null;

// Demo timeline (seconds): prep 0-2, pose 2-PRE, [selection], motion 0-3.5, results 3.5-POST.
const PREP_S = 2;
const MOTION_S = 3.5;

export function demoProcess(state: DemoState, now: number, durationS: number): ProcessView {
  if (state.startedAt === null) {
    return { steps: steps(() => ({ status: "waiting", progress: null, detail: null })), overall: 0,
             previewTimeS: null, phase: "notStarted", errorText: null, etaS: null, etaStep: null };
  }
  const pre = (now - state.startedAt) / 1000;
  const post = state.selectedAt === null ? null : (now - state.selectedAt) / 1000;
  const poseP = Math.min(1, Math.max(0, (pre - PREP_S) / (DEMO_PRE_SELECTION_S - PREP_S)));
  const motionP = post === null ? 0 : Math.min(1, post / MOTION_S);
  const resultP = post === null ? 0 : Math.min(1, Math.max(0, (post - MOTION_S) / (DEMO_POST_SELECTION_S - MOTION_S)));
  const awaiting = post === null && pre >= DEMO_PRE_SELECTION_S;
  const done = resultP >= 1;

  const view = steps((id) => {
    switch (id) {
      case "prep": {
        const p = Math.min(1, pre / PREP_S);
        return { status: p >= 1 ? "done" : "active", progress: p, detail: p >= 1 ? L.demoPrepDone : L.demoPrepActive };
      }
      case "pose":
        if (pre < PREP_S) return { status: "waiting", progress: null, detail: null };
        return { status: poseP >= 1 ? "done" : "active", progress: poseP,
                 detail: L.demoPoseFrames(Math.round(poseP * durationS * 30).toLocaleString("tr-TR")) };
      case "select":
        if (post !== null) return { status: "done", progress: 1, detail: L.demoSelected };
        return awaiting
          ? { status: "action", progress: null, detail: L.demoSelect }
          : { status: "waiting", progress: null, detail: null };
      case "motion":
        if (post === null) return { status: "waiting", progress: null, detail: null };
        return { status: motionP >= 1 ? "done" : "active", progress: motionP, detail: L.demoMotion };
      case "results":
        if (post === null || post < MOTION_S) return { status: "waiting", progress: null, detail: null };
        return { status: resultP >= 1 ? "done" : "active", progress: resultP, detail: L.demoResults };
    }
  });
  const overall = post === null
    ? 0.6 * Math.min(1, pre / DEMO_PRE_SELECTION_S)
    : 0.6 + 0.4 * Math.min(1, post / DEMO_POST_SELECTION_S);
  const active = view.find((s) => s.status === "active");
  // the simulated timeline is known exactly: time left in the running step
  const etaS = !active ? null
    : active.id === "prep" ? PREP_S - pre
      : active.id === "pose" ? DEMO_PRE_SELECTION_S - pre
        : active.id === "motion" ? MOTION_S - (post ?? 0)
          : DEMO_POST_SELECTION_S - (post ?? 0);
  return {
    steps: view,
    overall,
    previewTimeS: pre < PREP_S ? 0 : poseP * durationS,
    phase: done ? "done" : awaiting ? "awaitingSelection" : "running",
    errorText: null,
    etaS: etaS === null ? null : Math.max(0, etaS),
    etaStep: active ? active.label : null,
  };
}

/** Human-readable measured progress, e.g. "120 / 327 kare · 14,8 kare/sn". */
export function progressText(d: StageProgress): string {
  const parts: string[] = [];
  if (d.note) parts.push(d.note);
  const total = (format: (v: number) => string) => (d.total != null ? format(d.total) : null);
  if (d.unit === "frames") {
    parts.push(L.frames(formatNumber(d.done), total((v) => formatNumber(v))));
    if (d.rate_per_s) parts.push(L.framesPerSecond(formatNumber(d.rate_per_s, 1)));
  } else if (d.unit === "seconds") {
    parts.push(L.seconds(formatNumber(d.done, 1), total((v) => formatNumber(v, 1))));
    if (d.rate_per_s) parts.push(L.speed(formatNumber(d.rate_per_s, 1)));
  } else {
    parts.push(L.bytes(formatBytes(d.done), total(formatBytes)));
  }
  return parts.join(" · ");
}

function doneDetail(job: Job, id: StepId): string | null {
  const av = job.outputs.analysis_video;
  const pose = job.outputs.pose;
  if (id === "prep" && av) {
    const v = av.video;
    return L.prepDone(v.width, v.height, formatNumber(v.fps, 2), formatNumber(v.frame_count)) +
      (av.cache_hit ? L.fromCache : "");
  }
  if (id === "pose" && pose) {
    const prep = job.outputs.tracking_prep;
    return L.poseDone(formatNumber(pose.detection_count), pose.max_persons) +
      (pose.cache_hit ? L.fromCache : pose.processing_s != null ? ` · ${formatDuration(pose.processing_s)}` : "") +
      (prep ? L.prepSummary(prep.cuts.length, prep.candidates) : "") +
      (job.outputs.broadcast
        ? L.roundsSummary(job.outputs.broadcast.rounds.length,
                          job.outputs.broadcast.rounds.some((r) => r.source === "ocr")) +
          L.autoPartsSummary(job.auto_exclusions.filter((x) => !x.dismissed).length)
        : "");
  }
  if (id === "select" && job.selection) {
    return L.anchors(job.selection.anchors.length);
  }
  if (id === "motion" && job.outputs.tracking) {
    const [r, b] = job.outputs.tracking.fighters;
    const ev = job.outputs.events;
    return L.trackingDone(formatDuration((r?.uncertain_ms ?? 0) / 1000), formatDuration((b?.uncertain_ms ?? 0) / 1000),
                          job.outputs.tracking.identity_switches) +
      (ev ? L.eventsDone(ev.events, Math.round(ev.camera_known_share * 100)) : "");
  }
  if (id === "results" && job.outputs.tracking) {
    const sc = job.outputs.scoring;
    return sc ? L.momentumReady(sc.contributions) : L.trackingReady;
  }
  return null;
}

/** Steps whose results already exist (e.g. a job queued again after a new selection). */
function produced(job: Job, id: StepId): boolean {
  switch (id) {
    case "prep": return !!job.outputs.analysis_video;
    case "pose": return !!job.outputs.pose && !!job.outputs.tracking_prep;
    case "select": return !!job.selection;
    default: return false;
  }
}

/** Map a real job onto the user-facing steps. */
export function jobProcess(job: Job): ProcessView {
  const stepOfStage = (stage: Job["stage"]) =>
    stage === null ? -1 : PROCESS_STEPS.findIndex((s) => s.stages.includes(stage));
  const current = stepOfStage(job.stage);
  const selectIndex = PROCESS_STEPS.findIndex((s) => s.id === "select");
  const errorText = job.error ? (ERROR_LABELS[job.error.code] ?? job.error.message) : null;
  const detail = job.progress_detail;

  const view = steps((id) => {
    const index = PROCESS_STEPS.findIndex((s) => s.id === id);
    if (job.status === "completed") return { status: "done", progress: 1, detail: doneDetail(job, id) };
    if (job.status === "awaiting_selection") {
      if (index < selectIndex) return { status: "done", progress: 1, detail: doneDetail(job, id) };
      if (index === selectIndex) return { status: "action", progress: null, detail: L.awaitingSelection };
      return { status: "waiting", progress: null, detail: null };
    }
    const pending = (): Omit<StepView, "id" | "label"> => produced(job, id)
      ? { status: "done", progress: 1, detail: doneDetail(job, id) }
      : { status: "waiting", progress: null, detail: null };
    if (job.status === "queued" || current === -1) return pending();
    if (index < current) return { status: "done", progress: 1, detail: doneDetail(job, id) };
    if (index === current) {
      if (job.status === "failed") return { status: "error", progress: null, detail: L.stopped };
      if (job.status === "cancelled") return { status: "stopped", progress: null, detail: L.cancelledByUser };
      const measured = detail && detail.total ? Math.min(1, detail.done / detail.total) : null;
      return { status: "active", progress: measured, detail: detail ? progressText(detail) : job.message };
    }
    return pending();
  });
  const phase = ({ queued: "queued", running: "running", awaiting_selection: "awaitingSelection",
                   completed: "done", failed: "failed", cancelled: "cancelled" } as const)[job.status];
  const runningStep = job.status === "running" && current >= 0 ? PROCESS_STEPS[current]!.id : null;
  return {
    steps: view, overall: job.progress, previewTimeS: null, phase, errorText,
    etaS: runningStep && detail?.eta_s != null ? detail.eta_s : null,
    etaStep: runningStep ? labelOf(runningStep) : null,
  };
}
