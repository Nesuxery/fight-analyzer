import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { navigate } from "../../app/router";
import { EmptyState } from "../../ui";
import { demoEvents, demoMomentum, demoMomentumSeries, demoStats } from "../../demo/analysis";
import { useDemo } from "../../demo/DemoContext";
import type { DemoState } from "../../demo/DemoContext";
import { renderDemo } from "../../demo/render";
import { DEMO_DURATION_S, DEMO_FPS, DEMO_FRAME } from "../../demo/script";
import { useJob } from "../../hooks/useJob";
import { JOB_STATUS_LABELS, RESULT_LABELS } from "../../labels";
import { EMPTY_STATS } from "../../model/analysis";
import { PlaybackClock, formatClock, useClock, useDisposeClock } from "../../player/clock";
import { DEFAULT_LAYERS } from "../../player/draw";
import type { Layers } from "../../player/draw";
import { VideoStage } from "../../player/VideoStage";
import { EventList } from "./EventList";
import { FighterHeader } from "./FighterHeader";
import { PlaybackBar } from "./PlaybackBar";
import { StatPanel } from "./StatPanel";
import { Timeline } from "./Timeline";
import { TrackingResult } from "./TrackingResult";
import type { FighterActions, ResultData } from "./types";

export function ResultScreen({ demo, jobId }: { demo: boolean; jobId?: string }) {
  return demo ? <DemoResult /> : <JobResult jobId={jobId!} />;
}

function buildDemoResult(state: DemoState): ResultData {
  const { assignment, names } = state;
  return {
    origin: "demo",
    durationS: DEMO_DURATION_S,
    fps: DEMO_FPS,
    frame: DEMO_FRAME,
    names,
    events: demoEvents(assignment),
    momentumAt: (t) => demoMomentum(t, assignment),
    momentumSeries: demoMomentumSeries(assignment),
    statsAt: (side, t) => demoStats(assignment[side], t),
    draw: (ctx, t, layers) => renderDemo(ctx, t, { layers, assignment }),
  };
}

function DemoResult() {
  const { state, rename, swapSides } = useDemo();
  const data = useMemo(() => buildDemoResult(state), [state]);
  const [clock] = useState(() => new PlaybackClock(DEMO_DURATION_S, DEMO_FPS));
  useDisposeClock(clock);
  return (
    <ResultView
      data={data}
      clock={clock}
      actions={{
        onRename: rename,
        onSwap: swapSides,
        onReselect: () => navigate({ mode: "demo", screen: "select" }),
      }}
    />
  );
}

function JobResult({ jobId }: { jobId: string }) {
  // `updated_at` of the job when a recalculation (side swap) was requested: until a newer
  // version arrives, the old result must not be shown as if it were current.
  const [waitFor, setWaitFor] = useState<string | null>(null);
  const job = useJob(jobId, waitFor ? 1000 : 3000);
  const data = job.data;
  const running = data?.status === "queued" || data?.status === "running";
  const stale = waitFor !== null && (!data || data.updated_at === waitFor || running);
  useEffect(() => {
    if (waitFor && data && data.updated_at !== waitFor && !running) setWaitFor(null);
  }, [waitFor, data, running]);
  if (data?.status === "completed" && data.outputs.tracking && data.outputs.analysis_video && !stale) {
    return <TrackingResult job={data} onRecalculate={() => setWaitFor(data.updated_at)} />;
  }
  if (stale || (running && data?.selection)) {
    return (
      <EmptyState tone="loading" title="Sonuçlar yeniden hesaplanıyor…"
                 action={<a className="btn btn--ghost" href={`#/analyses/${jobId}/processing`}>İşlem ekranını aç</a>}>
        {data?.message ?? "Taraflar, seçim ya da dışlanan bölümler değişti."} Pozlar yeniden çıkarılmaz;
        etkilenen sonuçlar önbellekten birlikte yeniden üretilir, eski sonuç güncelmiş gibi gösterilmez.
        {data && <> (%{Math.round(data.progress * 100)})</>}
      </EmptyState>
    );
  }
  return <JobResultEmpty jobId={jobId} job={job} />;
}

function JobResultEmpty({ jobId, job }: { jobId: string; job: ReturnType<typeof useJob> }) {
  const [clock] = useState(() => new PlaybackClock(0, 30));
  useDisposeClock(clock);

  let message: ReactNode;
  if (job.loading) {
    message = <EmptyState tone="loading" title="Analiz bilgisi yükleniyor…" compact />;
  } else if (job.notFound) {
    message = (
      <EmptyState tone="error" title="Analiz bulunamadı" compact
                 action={<a className="btn btn--ghost" href="#/">Yükleme ekranına dön</a>} />
    );
  } else if (!job.data) {
    message = <EmptyState tone="error" title="Analiz durumu alınamadı" compact>API'ye ulaşılamıyor; yeniden deneniyor.</EmptyState>;
  } else if (job.data.status !== "completed") {
    message = (
      <EmptyState tone="empty" title="Sonuç henüz yok" compact
                 action={<a className="btn btn--ghost" href={`#/analyses/${jobId}/processing`}>İşlem ekranını aç</a>}>
        Bu analizin durumu: <strong>{JOB_STATUS_LABELS[job.data.status]}</strong>. Sonuçlar analiz
        tamamlandığında burada görünür.
      </EmptyState>
    );
  } else {
    message = (
      <EmptyState tone="empty" title="Sonuç verisi okunamıyor" compact>
        Analiz tamamlandı ancak sonuç dosyalarını okuma bu sürümde henüz yok.
      </EmptyState>
    );
  }
  return <ResultView data={null} clock={clock} actions={{}} empty={message} />;
}

/** Keys typed into form controls (or handled by the timeline slider) are not shortcuts. */
function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return ["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(target.tagName) ||
    target.isContentEditable || target.getAttribute("role") === "slider";
}

function ResultView({ data, clock, actions, empty }: {
  data: ResultData | null;
  clock: PlaybackClock;
  actions: FighterActions;
  empty?: ReactNode;
}) {
  const snap = useClock(clock);
  const [layers, setLayers] = useState<Layers>(DEFAULT_LAYERS);
  const disabled = data === null;
  const demo = data?.origin === "demo";

  useEffect(() => {
    if (disabled) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === " " && !isTyping(e.target)) {
        e.preventDefault();
        clock.toggle();
        return;
      }
      if (isTyping(e.target)) return;
      const k = e.key.toLowerCase();
      if (e.key === "ArrowRight") clock.skip(e.shiftKey ? 5 : 1);
      else if (e.key === "ArrowLeft") clock.skip(e.shiftKey ? -5 : -1);
      else if (e.key === ".") clock.stepFrames(1);
      else if (e.key === ",") clock.stepFrames(-1);
      else if (k === "s") setLayers((l) => ({ ...l, skeleton: !l.skeleton }));
      else if (k === "e") setLayers((l) => ({ ...l, strikes: !l.strikes }));
      else if (k === "d") setLayers((l) => ({ ...l, distance: !l.distance }));
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [clock, disabled]);

  const draw = useCallback(
    (ctx: CanvasRenderingContext2D, t: number) => data?.draw(ctx, t, layers),
    [data, layers],
  );
  const getTime = useCallback(() => clock.time, [clock]);
  const statsFor = (side: "red" | "blue") => (data ? data.statsAt(side, snap.time) : EMPTY_STATS);
  const series = useMemo(() => {
    const red = data?.momentumSeries;
    if (!data || !red || red.length < 2) return null;
    return { t: red.map((_, i) => (i / (red.length - 1)) * data.durationS), red };
  }, [data]);

  return (
    <div className="result">
      <FighterHeader names={data?.names ?? null} red={data ? Math.round(data.momentumAt(snap.time) * 100) : null}
                     demo={demo} actions={actions} />
      <div className="result__left">
        <StatPanel side="red" name={data?.names.red ?? null} stats={statsFor("red")}
                   scopeNote={data ? RESULT_LABELS.stats.interval(formatClock(0), formatClock(snap.time)) : null}
                   demo={demo} />
      </div>
      <div className="result__stage">
        {data ? (
          <VideoStage frame={data.frame} getTime={getTime} draw={draw}
                      label={demo ? "Demo sahnesi ve analiz katmanları" : "Maç videosu ve analiz katmanları"} />
        ) : (
          <div className="stage stage--empty" style={{ aspectRatio: "16 / 9" }}>{empty}</div>
        )}
      </div>
      <div className="result__right">
        <StatPanel side="blue" name={data?.names.blue ?? null} stats={statsFor("blue")}
                   scopeNote={data ? RESULT_LABELS.stats.interval(formatClock(0), formatClock(snap.time)) : null}
                   demo={demo} />
      </div>
      <div className="result__controls">
        <PlaybackBar clock={clock} snap={snap} layers={layers} onLayers={setLayers} disabled={disabled} />
        <Timeline clock={clock} time={snap.time} events={data?.events ?? []} names={data?.names ?? null}
                  momentum={series} disabled={disabled} />
      </div>
      <div className="result__events">
        <EventList events={data?.events ?? []} clock={clock} time={snap.time} names={data?.names ?? null}
                   demo={demo} />
      </div>
    </div>
  );
}
