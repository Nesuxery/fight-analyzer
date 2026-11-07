import { useEffect, useRef, useState } from "react";
import { urls } from "../../api/client";
import type { VideoInfo } from "../../contracts/generated";
import { usePoseFrames } from "../../hooks/usePoseFrames";
import { formatNumber } from "../../labels";
import { formatClock } from "../../player/clock";
import { PoseSvg } from "../../player/PoseSvg";
import type { PoseLayers } from "../../player/PoseSvg";

/**
 * Plays the analysis copy (the same file the engine read) with every
 * detected person drawn on the frame being shown. Frame index comes from the
 * presented frame's media time, so overlay and picture stay in sync.
 */
export function PoseReview({ jobId, video }: { jobId: string; video: VideoInfo }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [frame, setFrame] = useState(0);
  const [layers, setLayers] = useState<PoseLayers>({ skeleton: true, boxes: true });
  const fps = video.fps;
  const lastFrame = Math.max(0, video.frame_count - 1);
  const poses = usePoseFrames(jobId, video.frame_count, "neutral");

  // Follow the frame actually presented on screen.
  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    const toFrame = (t: number) => Math.min(lastFrame, Math.max(0, Math.round(t * fps)));
    let handle = 0;
    if (typeof el.requestVideoFrameCallback === "function") {
      const onFrame = (_now: number, meta: VideoFrameCallbackMetadata) => {
        setFrame(toFrame(meta.mediaTime));
        handle = el.requestVideoFrameCallback(onFrame);
      };
      handle = el.requestVideoFrameCallback(onFrame);
      return () => el.cancelVideoFrameCallback(handle);
    }
    const sync = () => setFrame(toFrame(el.currentTime));
    el.addEventListener("timeupdate", sync);
    el.addEventListener("seeked", sync);
    return () => {
      el.removeEventListener("timeupdate", sync);
      el.removeEventListener("seeked", sync);
    };
  }, [fps, lastFrame]);

  const { ensure } = poses;
  useEffect(() => ensure(frame), [ensure, frame]);
  const record = poses.get(frame);

  const step = (delta: number) => {
    const el = videoRef.current;
    if (!el) return;
    el.pause();
    const target = Math.min(lastFrame, Math.max(0, frame + delta));
    el.currentTime = (target + 0.5) / fps; // middle of the frame interval -> exactly that frame
  };

  return (
    <div className="review">
      <div className="stage" style={{ aspectRatio: `${video.width} / ${video.height}` }}>
        <video ref={videoRef} className="stage__video" src={urls.video(jobId)} controls playsInline preload="auto" />
        {record && record !== "loading" && (
          <PoseSvg width={video.width} height={video.height} detections={record.detections} layers={layers} />
        )}
      </div>
      <div className="review__bar">
        <button type="button" className="btn btn--sm btn--ghost" onClick={() => step(-1)}>‹ Kare</button>
        <button type="button" className="btn btn--sm btn--ghost" onClick={() => step(1)}>Kare ›</button>
        <span className="num review__info">
          Kare {formatNumber(frame)} / {formatNumber(lastFrame)} · {formatClock(frame / fps, true)} ·{" "}
          {record && record !== "loading" ? `${record.detections.length} kişi` : record === "loading" ? "yükleniyor…" : "—"}
        </span>
        <div className="review__toggles" role="group" aria-label="Katmanlar">
          {(["skeleton", "boxes"] as const).map((key) => (
            <button key={key} type="button" className="toggle" aria-pressed={layers[key]}
                    onClick={() => setLayers({ ...layers, [key]: !layers[key] })}>
              <span className="toggle__dot" aria-hidden="true" />{key === "skeleton" ? "İskelet" : "Kutular"}
            </button>
          ))}
        </div>
      </div>
      {poses.error && <p className="inline-warn">Poz verisi alınamadı: {poses.error}</p>}
    </div>
  );
}
