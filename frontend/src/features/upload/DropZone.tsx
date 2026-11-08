import { useRef, useState } from "react";
import type { DragEvent, ReactNode } from "react";
import { ApiError, api, uploadVideo } from "../../api/client";
import { navigate } from "../../app/router";
import { IconFilm, IconUpload } from "../../ui/icons";
import { Progress } from "../../ui";
import type { UploadLimits } from "../../contracts/generated";
import { usePolling } from "../../hooks/usePolling";
import { formatBytes, formatNumber } from "../../labels";
import { formatClock } from "../../player/clock";
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
  if (file.size > limits.max_bytes) return `Dosya ${formatBytes(limits.max_bytes)} sınırını aşıyor.`;
  if (!meta) return null;
  if (meta.durationS !== null && meta.durationS > limits.max_duration_s) {
    return `Video çok uzun (sınır ${formatNumber(limits.max_duration_s / 60, 1)} dk).`;
  }
  if (meta.durationS !== null && meta.durationS < limits.min_duration_s) {
    return `Video çok kısa (en az ${formatNumber(limits.min_duration_s, 1)} sn).`;
  }
  const long = Math.max(meta.width, meta.height);
  const short = Math.min(meta.width, meta.height);
  if (long > limits.max_long_side || short > limits.max_short_side) {
    return `Çözünürlük çok yüksek (sınır ${limits.max_long_side}×${limits.max_short_side}).`;
  }
  if (short < limits.min_short_side) return `Çözünürlük çok düşük (kısa kenar en az ${limits.min_short_side} px).`;
  return null;
}

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

  let body: ReactNode;
  if (state.kind === "idle" || state.kind === "rejected") {
    body = (
      <>
        <IconUpload size={20} className="dropzone__icon" />
        <p className="dropzone__lead">Videoyu buraya sürükleyip bırakın</p>
        <p className="dropzone__hint">
          MP4, MOV, MKV, WEBM, AVI
          {limits && ` · en fazla ${formatBytes(limits.max_bytes)} · ${formatNumber(limits.max_duration_s / 60)} dk`}
          {" "}· video bu bilgisayarda işlenir
        </p>
        <button type="button" className="btn btn--primary" onClick={pick}>Dosya seç</button>
        {state.kind === "rejected" && <p className="dropzone__error" role="alert">{state.reason}</p>}
      </>
    );
  } else {
    const { file } = state;
    const meta = state.kind === "reading" ? null : state.meta;
    const problem = state.kind === "ready" ? limitProblem(file, meta, limits) : null;
    body = (
      <div className="filecard">
        <IconFilm size={20} className="filecard__icon" />
        <div className="filecard__info">
          <p className="filecard__name" title={file.name}>{file.name}</p>
          <dl className="filecard__meta">
            <div><dt>Boyut</dt><dd className="num">{formatBytes(file.size)}</dd></div>
            <div><dt>Süre</dt><dd className="num">
              {state.kind === "reading" ? "okunuyor…" : meta?.durationS != null ? formatClock(meta.durationS) : "—"}
            </dd></div>
            <div><dt>Çözünürlük</dt><dd className="num">
              {state.kind === "reading" ? "okunuyor…" : meta ? `${meta.width}×${meta.height}` : "—"}
            </dd></div>
          </dl>
          {state.kind === "ready" && !meta && (
            <p className="filecard__note">
              Tarayıcı bu dosyanın bilgilerini okuyamadı; sunucu FFmpeg ile yine de doğrulayacak.
            </p>
          )}
        </div>
        <div className="filecard__actions">
          {state.kind === "uploading" ? (
            <button type="button" className="btn btn--ghost" onClick={state.abort}>Yüklemeyi iptal et</button>
          ) : (
            <>
              <button type="button" className="btn btn--primary" disabled={state.kind !== "ready" || !!problem}
                      onClick={() => state.kind === "ready" && start(file, meta)}>
                Analizi başlat
              </button>
              <button type="button" className="btn btn--ghost" onClick={pick} disabled={busy}>Başka dosya</button>
            </>
          )}
        </div>
        {problem && <p className="filecard__problem" role="alert">{problem}</p>}
        {state.kind === "uploading" && (
          <div className="filecard__upload">
            <Progress value={file.size ? state.loaded / file.size : null} label="Yükleme ilerlemesi" />
            <span className="num">
              {formatBytes(state.loaded)} / {formatBytes(file.size)} · %{Math.round((state.loaded / (file.size || 1)) * 100)}
              {state.loaded >= file.size && " · sunucu doğruluyor…"}
            </span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      className={`dropzone${dragging ? " is-dragging" : ""}${state.kind === "rejected" ? " is-error" : ""}`}
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
