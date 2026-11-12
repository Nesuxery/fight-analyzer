import { useCallback, useMemo, useState } from "react";
import { navigate } from "../../app/router";
import { useTheme } from "../../app/useTheme";
import type { SelectParams } from "../../app/router";
import { useDemo } from "../../demo/DemoContext";
import { renderDemo } from "../../demo/render";
import { CANDIDATE_TIMES, detectionsAt } from "../../demo/scene";
import { DEMO_FRAME, REFEREE } from "../../demo/script";
import { SELECTION_LABELS as L } from "../../labels";
import type { Assignment } from "../../model/analysis";
import { formatClock } from "../../player/clock";
import { VideoStage } from "../../player/VideoStage";
import { DemoTag } from "../../ui";
import { JobSelection } from "./JobSelection";
import { SelectionLayout } from "./SelectionLayout";
import type { CropSource } from "./SelectionLayout";

const NO_LAYERS = { skeleton: false, strikes: false, distance: false };

export function SelectionScreen({ demo, jobId, params }: { demo: boolean; jobId?: string; params?: SelectParams }) {
  return demo ? <DemoSelection /> : <JobSelection jobId={jobId!} params={params} />;
}

function DemoSelection() {
  const { state, confirmSelection, rename } = useDemo();
  const [candidate, setCandidate] = useState(0);
  const [picks, setPicks] = useState<Assignment>({ red: null, blue: null });
  const [problem, setProblem] = useState<string | null>(null);
  const t = CANDIDATE_TIMES[candidate]!;
  const detections = useMemo(() => detectionsAt(t), [t]);
  const draw = useCallback(
    (ctx: CanvasRenderingContext2D, time: number) => renderDemo(ctx, time, { layers: NO_LAYERS, assignment: null }),
    [],
  );
  // The synthetic frame, drawn once per candidate and theme: the tiles are cut from it.
  const { theme } = useTheme();
  const source = useMemo<CropSource>(() => {
    const canvas = document.createElement("canvas");
    canvas.width = DEMO_FRAME.width;
    canvas.height = DEMO_FRAME.height;
    const ctx = canvas.getContext("2d");
    if (ctx) renderDemo(ctx, t, { layers: NO_LAYERS, assignment: null });
    return { version: `${t}:${theme}`, draw: (c, r, size) => c.drawImage(canvas, r.x, r.y, r.size, r.size, 0, 0, size, size) };
  }, [t, theme]);

  const confirm = () => {
    if (picks.red === REFEREE || picks.blue === REFEREE) {
      setProblem(L.refereePicked);
      return;
    }
    confirmSelection(picks);
    navigate({ mode: "demo", screen: "processing" });
  };

  return (
    <SelectionLayout
      title={<>{L.title} <DemoTag small /></>}
      picks={picks}
      onPick={(next) => {
        setProblem(null);
        setPicks(next);
      }}
      detections={detections}
      frame={DEMO_FRAME}
      source={source}
      names={state.names}
      onRename={rename}
      stage={(boxes) => (
        <VideoStage frame={DEMO_FRAME} getTime={() => t} draw={draw} label={L.demoStage}>{boxes}</VideoStage>
      )}
      candidateLabel={L.candidateOf(candidate + 1, CANDIDATE_TIMES.length, formatClock(t, true))}
      onPrev={candidate > 0 ? () => setCandidate(candidate - 1) : undefined}
      onNext={candidate < CANDIDATE_TIMES.length - 1 ? () => setCandidate(candidate + 1) : undefined}
      onConfirm={confirm}
      problem={problem}
    />
  );
}
