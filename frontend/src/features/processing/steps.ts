import type { Job, StageProgress } from "../../contracts/generated";
import { DEMO_POST_SELECTION_S, DEMO_PRE_SELECTION_S } from "../../demo/DemoContext";
import type { DemoState } from "../../demo/DemoContext";
import { ERROR_LABELS, PROCESS_STEPS, formatBytes, formatDuration, formatNumber } from "../../labels";
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
}

const steps = (status: (id: StepId) => Omit<StepView, "id" | "label">): StepView[] =>
  PROCESS_STEPS.map((s) => ({ id: s.id, label: s.label, ...status(s.id) }));

// Demo timeline (seconds): prep 0-2, pose 2-PRE, [selection], motion 0-3.5, results 3.5-POST.
const PREP_S = 2;
const MOTION_S = 3.5;

export function demoProcess(state: DemoState, now: number, durationS: number): ProcessView {
  if (state.startedAt === null) {
    return { steps: steps(() => ({ status: "waiting", progress: null, detail: null })), overall: 0,
             previewTimeS: null, phase: "notStarted", errorText: null };
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
        return { status: p >= 1 ? "done" : "active", progress: p, detail: p >= 1 ? "H.264 · sabit 30 fps" : "Video dönüştürülüyor" };
      }
      case "pose":
        if (pre < PREP_S) return { status: "waiting", progress: null, detail: null };
        return { status: poseP >= 1 ? "done" : "active", progress: poseP,
                 detail: `${Math.round(poseP * durationS * 30).toLocaleString("tr-TR")} kare işlendi` };
      case "select":
        if (post !== null) return { status: "done", progress: 1, detail: "İki dövüşçü seçildi" };
        return awaiting
          ? { status: "action", progress: null, detail: "Kırmızı ve mavi dövüşçüyü seçin" }
          : { status: "waiting", progress: null, detail: null };
      case "motion":
        if (post === null) return { status: "waiting", progress: null, detail: null };
        return { status: motionP >= 1 ? "done" : "active", progress: motionP, detail: "Takip, olaylar ve sinyaller" };
      case "results":
        if (post === null || post < MOTION_S) return { status: "waiting", progress: null, detail: null };
        return { status: resultP >= 1 ? "done" : "active", progress: resultP, detail: "Zaman çizelgesi ve istatistikler" };
    }
  });
  const overall = post === null
    ? 0.6 * Math.min(1, pre / DEMO_PRE_SELECTION_S)
    : 0.6 + 0.4 * Math.min(1, post / DEMO_POST_SELECTION_S);
  return {
    steps: view,
    overall,
    previewTimeS: pre < PREP_S ? 0 : poseP * durationS,
    phase: done ? "done" : awaiting ? "awaitingSelection" : "running",
    errorText: null,
  };
}

/** Human-readable measured progress, e.g. "120 / 327 kare · 14,8 kare/sn · ~14 sn kaldı". */
export function progressText(d: StageProgress): string {
  const parts: string[] = [];
  if (d.note) parts.push(d.note);
  if (d.unit === "frames") {
    parts.push(`${formatNumber(d.done)}${d.total != null ? ` / ${formatNumber(d.total)}` : ""} kare`);
    if (d.rate_per_s) parts.push(`${formatNumber(d.rate_per_s, 1)} kare/sn`);
  } else if (d.unit === "seconds") {
    parts.push(`${formatNumber(d.done, 1)}${d.total != null ? ` / ${formatNumber(d.total, 1)}` : ""} sn video`);
    if (d.rate_per_s) parts.push(`${formatNumber(d.rate_per_s, 1)}× hız`);
  } else {
    parts.push(`${formatBytes(d.done)}${d.total != null ? ` / ${formatBytes(d.total)}` : ""}`);
  }
  if (d.eta_s != null) parts.push(`~${formatDuration(d.eta_s)} kaldı`);
  return parts.join(" · ");
}

function doneDetail(job: Job, id: StepId): string | null {
  const av = job.outputs.analysis_video;
  const pose = job.outputs.pose;
  if (id === "prep" && av) {
    const v = av.video;
    return `${v.width}×${v.height} · ${formatNumber(v.fps, 2)} fps · ${formatNumber(v.frame_count)} kare` +
      (av.cache_hit ? " · önbellekten" : "");
  }
  if (id === "pose" && pose) {
    const prep = job.outputs.tracking_prep;
    return `${formatNumber(pose.detection_count)} kişi tespiti · en fazla ${pose.max_persons} kişi/kare` +
      (pose.cache_hit ? " · önbellekten" : pose.processing_s != null ? ` · ${formatDuration(pose.processing_s)}` : "") +
      (prep ? ` · ${prep.cuts.length} kamera kesimi · ${prep.candidates} aday kare` : "");
  }
  if (id === "select" && job.selection) {
    return `${job.selection.anchors.length} seçim noktası`;
  }
  if (id === "motion" && job.outputs.tracking) {
    const [r, b] = job.outputs.tracking.fighters;
    const ev = job.outputs.events;
    return `Kimlik takibi: belirsiz ${formatDuration((r?.uncertain_ms ?? 0) / 1000)} / ${formatDuration((b?.uncertain_ms ?? 0) / 1000)}` +
      ` · olası kimlik değişimi ${job.outputs.tracking.identity_switches}` +
      (ev ? ` · ${ev.events} olay · kamera hareketi karelerin %${Math.round(ev.camera_known_share * 100)}'inde ölçüldü` : "");
  }
  if (id === "results" && job.outputs.tracking) {
    const sc = job.outputs.scoring;
    return sc ? `Deneysel momentum hazır · ${sc.contributions} puan kaydı` : "Takip sonuçları hazır";
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
      if (index === selectIndex) {
        return { status: "action", progress: null,
                 detail: "Pozlar hazır. Kırmızı ve mavi köşedeki dövüşçüleri seçin." };
      }
      return { status: "waiting", progress: null, detail: null };
    }
    const pending = (): Omit<StepView, "id" | "label"> => produced(job, id)
      ? { status: "done", progress: 1, detail: doneDetail(job, id) }
      : { status: "waiting", progress: null, detail: null };
    if (job.status === "queued" || current === -1) return pending();
    if (index < current) return { status: "done", progress: 1, detail: doneDetail(job, id) };
    if (index === current) {
      if (job.status === "failed") return { status: "error", progress: null, detail: "Analiz bu aşamada durdu." };
      if (job.status === "cancelled") {
        return { status: "stopped", progress: null, detail: "Kullanıcı iptal etti; yeniden başlatılabilir." };
      }
      const measured = detail && detail.total ? Math.min(1, detail.done / detail.total) : null;
      return { status: "active", progress: measured, detail: detail ? progressText(detail) : job.message };
    }
    return pending();
  });
  const phase = ({ queued: "queued", running: "running", awaiting_selection: "awaitingSelection",
                   completed: "done", failed: "failed", cancelled: "cancelled" } as const)[job.status];
  return { steps: view, overall: job.progress, previewTimeS: null, phase, errorText };
}
