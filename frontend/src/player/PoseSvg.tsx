import type { PersonDetection } from "../contracts/generated";
import { COCO_EDGES } from "./draw";

export interface PoseLayers {
  skeleton: boolean;
  boxes: boolean;
}

export interface PersonStyle {
  color: string;
  label?: string;
  /** Faint drawing for people who are not one of the fighters. */
  dim?: boolean;
}

/** Joints below this confidence are not drawn (they are still stored). */
export const MIN_JOINT_CONFIDENCE = 0.3;

const NEUTRAL: PersonStyle = { color: "var(--stage-text)" };

/**
 * Detections drawn over a frame of `width`×`height` pixels. The viewBox
 * matches the analysis frame, so it scales with its container. Without
 * `styleFor` everyone is drawn in one neutral colour (no identity assumed).
 */
export function PoseSvg({ width, height, detections, layers, styleFor }: {
  width: number;
  height: number;
  detections: PersonDetection[];
  layers: PoseLayers;
  styleFor?: (d: PersonDetection) => PersonStyle | null;
}) {
  const fontSize = Math.max(11, height / 42);
  return (
    <svg className="pose-svg" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
      {detections.map((d) => {
        const style = styleFor ? styleFor(d) : NEUTRAL;
        if (!style) return null;
        const k = d.keypoints;
        const cls = style.dim ? " is-dim" : "";
        return (
          <g key={d.detection_id} style={{ color: style.color }}>
            {layers.boxes && (
              <>
                <rect className={`pose-svg__box${cls}`} x={d.bbox.x1} y={d.bbox.y1}
                      width={d.bbox.x2 - d.bbox.x1} height={d.bbox.y2 - d.bbox.y1} />
                <text className={`pose-svg__label${cls}`} x={d.bbox.x1 + 3} y={d.bbox.y1 - 5} fontSize={fontSize}>
                  {style.label ?? `%${Math.round(d.confidence * 100)}`}
                </text>
              </>
            )}
            {layers.skeleton && (
              <>
                {COCO_EDGES.map(([a, b]) => {
                  const p = k[a];
                  const q = k[b];
                  if (!p || !q || p.confidence < MIN_JOINT_CONFIDENCE || q.confidence < MIN_JOINT_CONFIDENCE) {
                    return null;
                  }
                  return <line key={`${a}-${b}`} className={`pose-svg__bone${cls}`} x1={p.x} y1={p.y} x2={q.x} y2={q.y} />;
                })}
                {k.map((p, i) =>
                  p.confidence >= MIN_JOINT_CONFIDENCE ? (
                    <circle key={i} className={`pose-svg__joint${cls}`} cx={p.x} cy={p.y} r={Math.max(2, height / 260)} />
                  ) : null,
                )}
              </>
            )}
          </g>
        );
      })}
    </svg>
  );
}
