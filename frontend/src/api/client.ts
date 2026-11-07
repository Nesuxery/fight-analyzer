import type {
  ErrorResponse,
  EventTimeline,
  ExportFileKind,
  ExportRequest,
  FighterNames,
  FighterSelection,
  HealthResponse,
  Job,
  JobList,
  MatchSetup,
  MomentumTimeline,
  MotionTimeline,
  PoseChunk,
  PosePreview,
  Scorecards,
  SegmentExclusions,
  SelectionCandidates,
  TrackingTimeline,
  UploadLimits,
} from "../contracts/generated";

const BASE = "/api/v1";
/** Required by the API on state-changing requests (blocks cross-site requests). */
const CLIENT_HEADER = { "X-Fight-Analyzer": "1" };

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(status: number, message: string, code: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function toError(res: Response): Promise<ApiError> {
  if (res.headers.get("content-type")?.includes("application/json")) {
    try {
      const body = (await res.json()) as Partial<ErrorResponse> & { detail?: unknown };
      if (body.message) return new ApiError(res.status, body.message, body.code ?? null);
    } catch {
      // fall through
    }
  }
  // The Vite proxy answers 5xx without JSON when the API process is down.
  return new ApiError(res.status, `API isteği başarısız: ${res.status} ${res.statusText}`);
}

async function request<T>(path: string, init: RequestInit & { acceptStatus?: number[] } = {}) {
  const { acceptStatus = [], ...rest } = init;
  const res = await fetch(`${BASE}${path}`, {
    ...rest,
    headers: { Accept: "application/json", ...rest.headers },
  });
  const isJson = res.headers.get("content-type")?.includes("application/json") ?? false;
  if ((!res.ok && !acceptStatus.includes(res.status)) || !isJson) throw await toError(res);
  return (await res.json()) as T;
}

export const api = {
  // 503 still carries a HealthResponse body (database unavailable).
  health: (signal: AbortSignal) => request<HealthResponse>("/health", { signal, acceptStatus: [503] }),
  jobs: (signal: AbortSignal) => request<JobList>("/jobs", { signal }),
  job: (jobId: string, signal: AbortSignal) =>
    request<Job>(`/jobs/${encodeURIComponent(jobId)}`, { signal }),
  uploadLimits: (signal: AbortSignal) => request<UploadLimits>("/upload-limits", { signal }),
  cancel: (jobId: string) =>
    request<Job>(`/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST", headers: CLIENT_HEADER }),
  preview: (jobId: string, signal: AbortSignal) =>
    request<PosePreview>(`/jobs/${encodeURIComponent(jobId)}/preview`, { signal }),
  poses: (jobId: string, start: number, count: number, signal?: AbortSignal) =>
    request<PoseChunk>(`/jobs/${encodeURIComponent(jobId)}/poses?start=${start}&count=${count}`, { signal }),
  candidates: (jobId: string, signal?: AbortSignal) =>
    request<SelectionCandidates>(`/jobs/${encodeURIComponent(jobId)}/candidates`, { signal }),
  events: (jobId: string, signal?: AbortSignal) =>
    request<EventTimeline>(`/jobs/${encodeURIComponent(jobId)}/events`, { signal }),
  motion: (jobId: string, signal?: AbortSignal) =>
    request<MotionTimeline>(`/jobs/${encodeURIComponent(jobId)}/motion`, { signal }),
  momentum: (jobId: string, signal?: AbortSignal) =>
    request<MomentumTimeline>(`/jobs/${encodeURIComponent(jobId)}/momentum`, { signal }),
  trackingTimeline: (jobId: string, signal?: AbortSignal) =>
    request<TrackingTimeline>(`/jobs/${encodeURIComponent(jobId)}/tracking/timeline`, { signal }),
  submitSelection: (jobId: string, selection: FighterSelection) =>
    request<Job>(`/jobs/${encodeURIComponent(jobId)}/selection`, {
      method: "POST", headers: { ...CLIENT_HEADER, "Content-Type": "application/json" },
      body: JSON.stringify(selection),
    }),
  setNames: (jobId: string, names: FighterNames) =>
    request<Job>(`/jobs/${encodeURIComponent(jobId)}/names`, {
      method: "PUT", headers: { ...CLIENT_HEADER, "Content-Type": "application/json" },
      body: JSON.stringify(names),
    }),
  retry: (jobId: string) =>
    request<Job>(`/jobs/${encodeURIComponent(jobId)}/retry`, { method: "POST", headers: CLIENT_HEADER }),
  /** Exchange red and blue (selection and names together); results are derived again. */
  swapCorners: (jobId: string) =>
    request<Job>(`/jobs/${encodeURIComponent(jobId)}/swap`, { method: "POST", headers: CLIENT_HEADER }),
  /** Rounds, ending and point deductions entered by the user (nothing is recomputed). */
  setMatch: (jobId: string, body: MatchSetup) =>
    request<Job>(`/jobs/${encodeURIComponent(jobId)}/match`, {
      method: "PUT", headers: { ...CLIENT_HEADER, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  /** AI round scoring by three virtual judges (an estimate, not an official result). */
  scorecards: (jobId: string, signal?: AbortSignal) =>
    request<Scorecards>(`/jobs/${encodeURIComponent(jobId)}/scorecards`, { signal }),
  /** Replace the excluded parts (replays etc.); the momentum is computed again. */
  setExclusions: (jobId: string, body: SegmentExclusions) =>
    request<Job>(`/jobs/${encodeURIComponent(jobId)}/exclusions`, {
      method: "PUT", headers: { ...CLIENT_HEADER, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  /** Queue an export (MP4 with overlay, CSV, JSON); it runs as its own job in the worker. */
  createExport: (jobId: string, body: ExportRequest) =>
    request<Job>(`/jobs/${encodeURIComponent(jobId)}/exports`, {
      method: "POST", headers: { ...CLIENT_HEADER, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  exports: (jobId: string, signal?: AbortSignal) =>
    request<JobList>(`/jobs/${encodeURIComponent(jobId)}/exports`, { signal }),
};

export const urls = {
  video: (jobId: string) => `${BASE}/jobs/${encodeURIComponent(jobId)}/video`,
  previewImage: (jobId: string, seq: number) =>
    `${BASE}/jobs/${encodeURIComponent(jobId)}/preview.jpg?seq=${seq}`,
  exportFile: (exportId: string, kind: ExportFileKind) =>
    `${BASE}/jobs/${encodeURIComponent(exportId)}/files/${kind}`,
};

export interface UploadHandle {
  promise: Promise<Job>;
  abort: () => void;
}

/** Stream the file as the raw request body; reports bytes sent. */
export function uploadVideo(file: File, onProgress: (loaded: number, total: number) => void): UploadHandle {
  const xhr = new XMLHttpRequest();
  const promise = new Promise<Job>((resolve, reject) => {
    xhr.open("POST", `${BASE}/jobs?filename=${encodeURIComponent(file.name)}`);
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.setRequestHeader("X-Fight-Analyzer", "1");
    xhr.setRequestHeader("Accept", "application/json");
    xhr.responseType = "json";
    xhr.upload.onprogress = (e) => onProgress(e.loaded, e.lengthComputable ? e.total : file.size);
    xhr.onload = () => {
      const body = xhr.response as (Job & Partial<ErrorResponse>) | null;
      if (xhr.status === 201 && body) resolve(body as Job);
      else reject(new ApiError(xhr.status, body?.message ?? `Yükleme başarısız (${xhr.status}).`, body?.code ?? null));
    };
    xhr.onerror = () => reject(new ApiError(0, "Sunucuya ulaşılamadı; yükleme tamamlanamadı."));
    xhr.onabort = () => reject(new ApiError(0, "Yükleme iptal edildi.", "upload_aborted"));
    xhr.send(file);
  });
  return { promise, abort: () => xhr.abort() };
}
