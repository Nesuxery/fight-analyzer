import { useCallback, useMemo, useState } from "react";
import { navigate } from "../../app/router";
import type { SelectParams } from "../../app/router";
import { DemoTag } from "../../components/ui";
import { useDemo } from "../../demo/DemoContext";
import { renderDemo } from "../../demo/render";
import { CANDIDATE_TIMES, detectionsAt } from "../../demo/scene";
import { DEMO_FRAME, REFEREE } from "../../demo/script";
import type { Assignment } from "../../model/analysis";
import { formatClock } from "../../player/clock";
import { VideoStage } from "../../player/VideoStage";
import { JobSelection } from "./JobSelection";
import { SelectionLayout } from "./SelectionLayout";

const NO_LAYERS = { skeleton: false, strikes: false, distance: false };

export function SelectionScreen({ demo, jobId, params }: { demo: boolean; jobId?: string; params?: SelectParams }) {
  return demo ? <DemoSelection /> : <JobSelection jobId={jobId!} params={params} />;
}

function DemoSelection() {
  const { confirmSelection } = useDemo();
  const [candidate, setCandidate] = useState(0);
  const [picks, setPicks] = useState<Assignment>({ red: null, blue: null });
  const [problem, setProblem] = useState<string | null>(null);
  const t = CANDIDATE_TIMES[candidate]!;
  const detections = useMemo(() => detectionsAt(t), [t]);
  const draw = useCallback(
    (ctx: CanvasRenderingContext2D, time: number) => renderDemo(ctx, time, { layers: NO_LAYERS, assignment: null }),
    [],
  );

  const confirm = () => {
    if (picks.red === REFEREE || picks.blue === REFEREE) {
      setProblem("Bu demo sahnesinde seçtiğiniz kişilerden biri hakem. Demo sonuçları yalnızca iki dövüşçü için üretilir; lütfen dövüşçüleri seçin.");
      return;
    }
    confirmSelection(picks);
    navigate({ mode: "demo", screen: "processing" });
  };

  return (
    <SelectionLayout
      title={<>Dövüşçüleri seçin <DemoTag small /></>}
      picks={picks}
      onPick={(next) => {
        setProblem(null);
        setPicks(next);
      }}
      detections={detections}
      frame={DEMO_FRAME}
      stage={(boxes) => (
        <VideoStage frame={DEMO_FRAME} getTime={() => t} draw={draw} label="Aday kare (demo)">{boxes}</VideoStage>
      )}
      candidateLabel={`Aday kare ${candidate + 1} / ${CANDIDATE_TIMES.length} · ${formatClock(t, true)}`}
      onPrev={candidate > 0 ? () => setCandidate(candidate - 1) : undefined}
      onNext={candidate < CANDIDATE_TIMES.length - 1 ? () => setCandidate(candidate + 1) : undefined}
      onConfirm={confirm}
      problem={problem}
    />
  );
}
