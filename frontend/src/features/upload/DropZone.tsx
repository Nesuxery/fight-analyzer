import { useRef, useState } from "react";
import type { DragEvent, ReactNode } from "react";
import { ApiError, api, uploadVideo } from "../../api/client";
import { navigate } from "../../app/router";
import type { UploadLimits } from "../../contracts/generated";
import { usePolling } from "../../hooks/usePolling";
import { UI_LABELS, UPLOAD_LABELS as L, formatBytes, formatNumber } from "../../labels";
import { formatClock } from "../../player/clock";
import { Button, Progress, cx } from "../../ui";
import { IconFilm } from "../../ui/icons";
import { ACCEPT_ATTR, readLocalMetadata, validateVideoFile } from "./videoFile";
import type { LocalVideoMeta } from "./videoFile";

type FileState =
  | { kind: "idle" }
  | { kind: "reading"; file: File }
  | { kind: "ready"; file: File; meta: LocalVideoMeta | null }
  | { kind: "uploading"; file: File; meta: LocalVideoMeta | null; loaded: number; abort: () => void }
  | { kind: "processing"; file: File; meta: LocalVideoMeta | null }
  | { kind: "rejected"; reason: string };

/** Problems the server would reject, checked before uploading when the
 * browser could read the file. The server checks again with FFmpeg. */
function limitProblem(file: File, meta: LocalVideoMeta | null, limits: UploadLimits | undefined) {
  if (!limits) return null;
  if (file.size > limits.max_bytes) return L.tooLarge(formatBytes(limits.max_bytes));
  if (!meta) return null;
  if (meta.durationS !== null && meta.durationS > limits.max_duration_s) {
    return L.tooLong(formatNumber(limits.max_duration_s / 60, 1));
  }
  if (meta.durationS !== null && meta.durationS < limits.min_duration_s) {
    return L.tooShort(formatNumber(limits.min_duration_s, 1));
  }
  const long = Math.max(meta.width, meta.height);
  const short = Math.min(meta.width, meta.height);
  if (long > limits.max_long_side || short > limits.max_short_side) {
    return L.resolutionTooHigh(limits.max_long_side, limits.max_short_side);
  }
  if (short < limits.min_short_side) return L.resolutionTooLow(limits.min_short_side);
  return null;
}

/** White drop card with a dashed frame; while dragging the frame turns red and the card --red-soft. */
export function DropZone() {
  const [state, setState] = useState<FileState>({ kind: "idle" });
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const limits = usePolling(api.uploadLimits, 300000).data;
  const busy = state.kind === "uploading" || state.kind === "processing";

  const accept = async (file: File | undefined) => {
    if (!file || busy) return;
    const problem = validateVideoFile(file);
    if (problem) {
      setState({ kind: "rejected", reason: problem });
      return;
    }
    setState({ kind: "reading", file });
    const meta = await readLocalMetadata(file);
    setState((s) => (s.kind === "reading" && s.file === file ? { kind: "ready", file, meta } : s));
  };

  const start = (file: File, meta: LocalVideoMeta | null) => {
    const upload = uploadVideo(file, (loaded) =>
      setState((s) => (s.kind === "uploading" && s.file === file ? { ...s, loaded } : s)));
    setState({ kind: "uploading", file, meta, loaded: 0, abort: upload.abort });
    upload.promise.then(
      (job) => {
        setState({ kind: "processing", file, meta });
        navigate({ mode: "analysis", screen: "processing", jobId: job.job_id });
      },
      (err: unknown) => {
        const aborted = err instanceof ApiError && err.code === "upload_aborted";
        setState(aborted ? { kind: "ready", file, meta }
          : { kind: "rejected", reason: err instanceof Error ? err.message : String(err) });
      },
    );
  };

  const pick = () => inputRef.current?.click();
  const hint = [L.formats, limits && L.limits(formatBytes(limits.max_bytes), formatNumber(limits.max_duration_s / 60))]
    .filter(Boolean).join(" · ");

  let body: ReactNode;
  if (state.kind === "idle" || state.kind === "rejected") {
    body = (
      <>
        <p className="dropzone__lead">{L.dropLead}</p>
        <Button variant="brand" onClick={pick}>{L.chooseFile}</Button>
        <p className="dropzone__hint">{hint}</p>
        {state.kind === "rejected" && <p className="dropzone__error" role="alert">{state.reason}</p>}
      </>
    );
  } else {
    const { file } = state;
    const meta = state.kind === "reading" ? null : state.meta;
    const problem = state.kind === "ready" ? limitProblem(file, meta, limits) : null;
    const pct = Math.round((state.kind === "uploading" ? state.loaded / (file.size || 1) : 0) * 100);
    body = (
      <div className="filecard">
        <IconFilm className="filecard__icon" />
        <div className="filecard__info">
          <p className="filecard__name" title={file.name}>{file.name}</p>
          <dl className="filecard__meta">
            <div><dt>{L.size}</dt><dd className="num">{formatBytes(file.size)}</dd></div>
            <div><dt>{L.duration}</dt><dd className="num">
              {state.kind === "reading" ? L.reading : meta?.durationS != null ? formatClock(meta.durationS) : UI_LABELS.noValue}
            </dd></div>
            <div><dt>{L.resolution}</dt><dd className="num">
              {state.kind === "reading" ? L.reading : meta ? `${meta.width}×${meta.height}` : UI_LABELS.noValue}
            </dd></div>
          </dl>
          {state.kind === "ready" && !meta && <p className="filecard__note">{L.metaUnreadable}</p>}
        </div>
        <div className="filecard__actions">
          {state.kind === "uploading" ? (
            <Button onClick={state.abort}>{L.cancelUpload}</Button>
          ) : (
            <>
              <Button variant="primary" disabled={state.kind !== "ready" || !!problem}
                      onClick={() => state.kind === "ready" && start(file, meta)}>
                {L.start}
              </Button>
              <Button onClick={pick} disabled={busy}>{L.otherFile}</Button>
            </>
          )}
        </div>
        {problem && <p className="filecard__problem" role="alert">{problem}</p>}
        {state.kind === "uploading" && (
          <div className="filecard__upload">
            <Progress value={file.size ? state.loaded / file.size : null} label={L.uploadProgress} />
            <span className="num">
              {formatBytes(state.loaded)} / {formatBytes(file.size)} · %{pct}
              {state.loaded >= file.size && ` · ${L.verifying}`}
            </span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      className={cx("dropzone", dragging && "is-dragging", state.kind === "rejected" && "is-error",
                    state.kind !== "idle" && state.kind !== "rejected" && "has-file")}
      onDragOver={(e) => {
        e.preventDefault();
        if (!busy) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e: DragEvent) => {
        e.preventDefault();
        setDragging(false);
        void accept(e.dataTransfer.files[0]);
      }}
    >
      <input ref={inputRef} type="file" accept={ACCEPT_ATTR} hidden
             onChange={(e) => {
               void accept(e.target.files?.[0]);
               e.target.value = "";
             }} />
      {body}
    </div>
  );
}
