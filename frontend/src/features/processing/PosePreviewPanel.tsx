import { useEffect, useState } from "react";
import { api, urls } from "../../api/client";
import type { PosePreview } from "../../contracts/generated";
import { PROCESSING_LABELS as L, formatNumber } from "../../labels";
import { PoseSvg } from "../../player/PoseSvg";
import { IconSpinner } from "../../ui/icons";

const LAYERS = { skeleton: true, boxes: true };

/** Latest processed frame with its detections. The worker writes a new one
 * only every ~1.5 s; `seq` comes from the job's progress detail. */
export function PosePreviewPanel({ jobId, seq, fallbackAspect }: {
  jobId: string;
  seq: number;
  fallbackAspect: string;
}) {
  const [preview, setPreview] = useState<PosePreview | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    api.preview(jobId, controller.signal).then(setPreview, () => undefined);
    return () => controller.abort();
  }, [jobId, seq]);

  if (!preview) {
    return (
      <div className="stage stage--empty" style={{ aspectRatio: fallbackAspect }}>
        <IconSpinner className="icon-spin" />
      </div>
    );
  }
  const { width, height, frame } = preview;
  return (
    <div className="stage" style={{ aspectRatio: `${width} / ${height}` }}>
      <img className="stage__img" src={urls.previewImage(jobId, preview.seq)} alt={L.previewTitle} />
      <PoseSvg width={width} height={height} detections={frame.detections} layers={LAYERS} />
      <span className="stage__badge num">{L.previewFrame(formatNumber(frame.frame_index), frame.detections.length)}</span>
    </div>
  );
}
