/** Client-side checks on a chosen video file. Nothing leaves the computer. */
import { UPLOAD_LABELS as L } from "../../labels";

export const ACCEPTED_EXTENSIONS = ["mp4", "mov", "m4v", "mkv", "webm", "avi"] as const;
export const ACCEPT_ATTR = ["video/*", ...ACCEPTED_EXTENSIONS.map((e) => `.${e}`)].join(",");
export const MAX_FILE_BYTES = 20 * 1024 ** 3; // 20 GB

export interface LocalVideoMeta {
  /** null when the container does not state a duration (e.g. some WebM). */
  durationS: number | null;
  width: number;
  height: number;
}

export function validateVideoFile(file: File): string | null {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  const extOk = (ACCEPTED_EXTENSIONS as readonly string[]).includes(ext);
  if (!extOk && !file.type.startsWith("video/")) {
    // toUpperCase follows no locale: "avi" becomes "AVI" (Turkish rules would give "AVİ")
    return L.notVideo(file.name, ACCEPTED_EXTENSIONS.map((e) => e.toUpperCase()).join(", "));
  }
  if (file.size === 0) return L.emptyFile;
  if (file.size > MAX_FILE_BYTES) return L.overMax;
  return null;
}

/** Read duration and resolution with the browser's own decoder. Resolves
 * null when the browser cannot decode the container/codec (FFmpeg on the
 * server may still handle it). */
export function readLocalMetadata(file: File, timeoutMs = 8000): Promise<LocalVideoMeta | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    const done = (meta: LocalVideoMeta | null) => {
      window.clearTimeout(timer);
      video.removeAttribute("src");
      video.load();
      URL.revokeObjectURL(url);
      resolve(meta);
    };
    const timer = window.setTimeout(() => done(null), timeoutMs);
    video.preload = "metadata";
    video.muted = true;
    video.onloadedmetadata = () =>
      done(video.videoWidth > 0
        ? {
            durationS: Number.isFinite(video.duration) ? video.duration : null,
            width: video.videoWidth,
            height: video.videoHeight,
          }
        : null);
    video.onerror = () => done(null);
    video.src = url;
  });
}
