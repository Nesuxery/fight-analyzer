import { useEffect, useRef, useState } from "react";
import { urls } from "../../api/client";
import type { VideoInfo } from "../../contracts/generated";
import { usePoseFrames } from "../../hooks/usePoseFrames";
import { PROCESSING_LABELS as L, formatNumber } from "../../labels";
import { formatClock } from "../../player/clock";
import { PoseSvg } from "../../player/PoseSvg";
import type { PoseLayers } from "../../player/PoseSvg";
import { Button, Chip } from "../../ui";

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
        <Button size="sm" onClick={() => step(-1)}>{L.framePrev}</Button>
        <Button size="sm" onClick={() => step(1)}>{L.frameNext}</Button>
        <span className="num review__info">
          {L.frameOf(formatNumber(frame), formatNumber(lastFrame))} · {formatClock(frame / fps, true)} ·{" "}
          {record && record !== "loading" ? L.people(record.detections.length) : record === "loading" ? L.loadingShort : "—"}
        </span>
        <div className="review__toggles" role="group" aria-label={L.layers}>
          <Chip pressed={layers.skeleton} onPressedChange={(on) => setLayers({ ...layers, skeleton: on })}>{L.skeleton}</Chip>
          <Chip pressed={layers.boxes} onPressedChange={(on) => setLayers({ ...layers, boxes: on })}>{L.boxes}</Chip>
        </div>
      </div>
      {poses.error && <p className="inline-warn">{L.posesFailed(poses.error)}</p>}
    </div>
  );
}
