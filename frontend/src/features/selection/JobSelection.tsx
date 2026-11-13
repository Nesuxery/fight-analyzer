import { useEffect, useMemo, useRef, useState } from "react";
import { api, urls } from "../../api/client";
import { navigate } from "../../app/router";
import type { SelectParams } from "../../app/router";
import type { FighterAnchor, Job, PersonDetection, ScreenRect, SelectionCandidates } from "../../contracts/generated";
import { useJob } from "../../hooks/useJob";
import { COMMON_LABELS, MATCH_LABELS, SELECTION_LABELS as L, formatNumber } from "../../labels";
import { MatchSettings } from "../match/MatchSettings";
import { RoiPicker } from "../match/RoiPicker";
import { applyNameSuggestion, suggestionTargets } from "../match/roundEdit";
import { NOT_IN_VIEW } from "../../model/analysis";
import type { Assignment, Detection, Side } from "../../model/analysis";
import { formatClock } from "../../player/clock";
import { Button, ButtonLink, EmptyState } from "../../ui";
import { SelectionLayout } from "./SelectionLayout";
import type { CropSource } from "./SelectionLayout";

const toDetection = (d: PersonDetection): Detection => ({
  personId: String(d.detection_id), x1: d.bbox.x1, y1: d.bbox.y1, x2: d.bbox.x2, y2: d.bbox.y2,
  confidence: d.confidence,
});

function savedNames(job: Job): Record<Side, string> {
  const red = job.fighters.find((f) => f.fighter_id === "fighter_a")?.display_name;
  const blue = job.fighters.find((f) => f.fighter_id === "fighter_b")?.display_name;
  // same defaults the API uses until names are set
  return { red: red ?? L.defaultNames.red, blue: blue ?? L.defaultNames.blue };
}

/**
 * Pick the red and then the blue fighter on a frame of the real analysis
 * video. Candidate frames come from the tracking preparation; any other frame
 * can be reached with the frame steps (used for "fix at this frame"). With
 * `keep`, earlier selections stay and this one is added as a correction.
 * Names are edited in the corner rows and saved with the selection.
 */
export function JobSelection({ jobId, params }: { jobId: string; params?: SelectParams }) {
  const job = useJob(jobId, 2000);
  // A save returns the updated job: shown at once, until polling brings it too.
  const [fresh, setFresh] = useState<Job | null>(null);
  const [settingsBusy, setSettingsBusy] = useState(false);
  const [settingsProblem, setSettingsProblem] = useState<string | null>(null);
  const [roiEditing, setRoiEditing] = useState(false);
  const [roiDraft, setRoiDraft] = useState<ScreenRect | null>(null);
  const [rereading, setRereading] = useState(false);
  const [cands, setCands] = useState<SelectionCandidates | null>(null);
  const [candError, setCandError] = useState<string | null>(null);
  const [frame, setFrame] = useState<number | null>(params?.frame ?? null);
  const [dets, setDets] = useState<{ frame: number; list: PersonDetection[] } | null>(null);
  const [picks, setPicks] = useState<Assignment>({ red: null, blue: null });
  const [keep, setKeep] = useState(params?.keep ?? false);
  const [names, setNames] = useState<Record<Side, string> | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  /** Frame the <video> is showing (after the seek finished): the tiles are cut from it. */
  const [shown, setShown] = useState<number | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const polled = job.data;
  const data = polled && fresh && fresh.job_id === polled.job_id &&
    Date.parse(fresh.updated_at) >= Date.parse(polled.updated_at) ? fresh : polled;
  const prepKey = data?.outputs.tracking_prep?.cache_key;
  const video = data?.outputs.analysis_video?.video;

  useEffect(() => {
    if (!prepKey) return;
    const c = new AbortController();
    api.candidates(jobId, c.signal).then(setCands, (e: unknown) => {
      if (!c.signal.aborted) setCandError(e instanceof Error ? e.message : String(e));
    });
    return () => c.abort();
  }, [jobId, prepKey]);

  const current = frame ?? cands?.frames[0]?.frame_index ?? null;

  // Detections of the current frame: from the candidates, otherwise from the pose data.
  useEffect(() => {
    if (current === null) return;
    const fromCand = cands?.frames.find((f) => f.frame_index === current);
    if (fromCand) {
      setDets({ frame: current, list: fromCand.detections });
      return;
    }
    const c = new AbortController();
    api.poses(jobId, current, 1, c.signal).then(
      (chunk) => setDets({ frame: current, list: chunk.frames[0]?.detections ?? [] }),
      () => undefined,
    );
    return () => c.abort();
  }, [jobId, current, cands]);

  // Show exactly that frame of the analysis video.
  useEffect(() => {
    const el = videoRef.current;
    if (!el || current === null || !video) return;
    const target = current;
    const onSeeked = () => setShown(target);
    const seek = () => { el.currentTime = (target + 0.5) / video.fps; };
    el.addEventListener("seeked", onSeeked);
    if (el.readyState >= 1) seek();
    else el.addEventListener("loadedmetadata", seek, { once: true });
    return () => {
      el.removeEventListener("seeked", onSeeked);
      el.removeEventListener("loadedmetadata", seek);
    };
  }, [current, video]);

  const source = useMemo<CropSource | null>(() => {
    const el = videoRef.current;
    if (shown === null || shown !== current || !el) return null;
    return {
      version: shown,
      draw: (ctx, r, size) => ctx.drawImage(el, r.x, r.y, r.size, r.size, 0, 0, size, size),
    };
  }, [shown, current]);

  useEffect(() => {
    if (!names && data) setNames(savedNames(data));
  }, [data, names]);

  const existing = data?.selection?.anchors ?? [];
  const sortedCands = useMemo(() => (cands?.frames ?? []).map((f) => f.frame_index).sort((a, b) => a - b), [cands]);

  if (job.loading) return <EmptyState tone="loading" title={L.loading} />;
  if (job.notFound) {
    return <EmptyState tone="error" title={L.notFound}
                       action={<ButtonLink href="#/">{COMMON_LABELS.backToUpload}</ButtonLink>} />;
  }
  if (!data) return <EmptyState tone="error" title={L.unreachableTitle}>{L.unreachableText}</EmptyState>;
  if (data.status === "queued" || data.status === "running") {
    return (
      <EmptyState tone="loading" title={L.processingTitle}
                  action={<ButtonLink href={`#/analyses/${jobId}/processing`}>{L.openProcessing}</ButtonLink>}>
        {rereading ? MATCH_LABELS.roi.rereading : L.processingText}
      </EmptyState>
    );
  }
  if (!data.outputs.pose || !video) {
    return <EmptyState tone="empty" title={L.noPosesTitle}>{L.noPosesText}</EmptyState>;
  }
  if (!prepKey) {
    return (
      <EmptyState tone="empty" title={L.noCandidatesTitle}
                  action={
                    <Button variant="primary"
                            onClick={() => api.retry(jobId).then(() => navigate({ mode: "analysis", screen: "processing", jobId }))}>
                      {L.prepareCandidates}
                    </Button>
                  }>
        {L.noCandidatesText}
      </EmptyState>
    );
  }
  if (candError) return <EmptyState tone="error" title={L.candidatesFailed}>{candError}</EmptyState>;
  if (!cands || current === null) return <EmptyState tone="loading" title={L.candidatesLoading} />;

  const lastFrame = video.frame_count - 1;
  const goTo = (f: number) => {
    setFrame(Math.min(lastFrame, Math.max(0, f)));
    setPicks({ red: null, blue: null });
    setProblem(null);
  };
  const prevCand = [...sortedCands].reverse().find((f) => f < current);
  const nextCand = sortedCands.find((f) => f > current);
  const candIndex = sortedCands.indexOf(current);
  const time = formatClock(current / video.fps, true);
  const label = candIndex >= 0
    ? L.candidateOf(candIndex + 1, sortedCands.length, time)
    : L.frameAt(formatNumber(current), time);
  const detsLoaded = dets !== null && dets.frame === current;
  const frameDets = detsLoaded ? dets.list : [];
  const shownNames = names ?? savedNames(data);

  const confirm = async () => {
    if (picks.red === null || picks.blue === null) return;
    const detId = (pick: string) => (pick === NOT_IN_VIEW ? null : Number(pick));
    const anchor: FighterAnchor = { frame_index: current, red_detection_id: detId(picks.red),
                                    blue_detection_id: detId(picks.blue) };
    const anchors = keep ? [...existing.filter((a) => a.frame_index !== current), anchor] : [anchor];
    setBusy(true);
    setProblem(null);
    try {
      const saved = savedNames(data);
      if (shownNames.red !== saved.red || shownNames.blue !== saved.blue) await api.setNames(jobId, shownNames);
      await api.submitSelection(jobId, { anchors });
      navigate({ mode: "analysis", screen: "processing", jobId });
    } catch (e) {
      setProblem(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const saveSettings = (p: Promise<Job>, after?: () => void) => {
    setSettingsBusy(true);
    setSettingsProblem(null);
    p.then((updated) => { setFresh(updated); after?.(); },
           (e: unknown) => setSettingsProblem(e instanceof Error ? e.message : String(e)))
      .finally(() => setSettingsBusy(false));
  };
  const broadcast = data.outputs.broadcast ?? null;
  const suggestion = broadcast?.names ?? null;
  const settings = (
    <MatchSettings
      bout={data.bout} rounds={data.rounds} broadcast={broadcast} roundNotes={data.round_notes}
      busy={settingsBusy} problem={settingsProblem}
      onBout={(b) => saveSettings(api.setBout(jobId, { ...b, names: null }))}
      roi={broadcast ? {
        editing: roiEditing,
        source: broadcast.roi?.source ?? null,
        canSave: roiDraft !== null,
        busy: settingsBusy,
        onStart: () => {
          setRoiDraft(broadcast.roi?.clock ?? null);
          setRoiEditing(true);
        },
        onSave: () => saveSettings(api.setScorebug(jobId, { clock: roiDraft }), () => {
          setRoiEditing(false);
          setRereading(true);
        }),
        onCancel: () => setRoiEditing(false),
        onReset: () => saveSettings(api.setScorebug(jobId, { clock: null }), () => setRereading(true)),
      } : undefined}
      names={suggestion ? {
        suggestion,
        canApply: suggestionTargets(shownNames, L.defaultNames, suggestion).length > 0,
        onApply: () => setNames(applyNameSuggestion(shownNames, L.defaultNames, suggestion)),
      } : undefined} />
  );

  const step = (n: number) => (
    <Button size="sm" onClick={() => goTo(current + n)} aria-label={L.frameStep(n)} title={L.frameStep(n)}>
      {n > 0 ? `+${n}` : n}
    </Button>
  );

  return (
    <SelectionLayout
      title={data.source?.filename ?? L.title}
      picks={picks}
      onPick={(next) => {
        setProblem(null);
        setPicks(next);
      }}
      detections={frameDets.map(toDetection)}
      frame={{ width: video.width, height: video.height }}
      source={detsLoaded ? source : null}
      names={shownNames}
      onRename={(side, name) => setNames({ ...shownNames, [side]: name })}
      stage={(boxes) => (
        <div className="stage" style={{ aspectRatio: `${video.width} / ${video.height}` }}>
          <video ref={videoRef} className="stage__video" src={urls.video(jobId)} muted playsInline preload="auto" />
          {roiEditing ? <RoiPicker value={roiDraft} onChange={setRoiDraft} /> : boxes}
          {!roiEditing && !detsLoaded && <div className="stage__veil">{L.peopleLoading}</div>}
          {!roiEditing && detsLoaded && frameDets.length === 0 && <div className="stage__veil">{L.noPeople}</div>}
        </div>
      )}
      settings={settings}
      candidateLabel={label}
      onPrev={prevCand !== undefined ? () => goTo(prevCand) : undefined}
      onNext={nextCand !== undefined ? () => goTo(nextCand) : undefined}
      navExtra={<span className="select__steps">{step(-10)}{step(-1)}{step(1)}{step(10)}</span>}
      onConfirm={() => void confirm()}
      busy={busy}
      problem={problem}
      confirmLabel={keep && existing.length ? L.confirmCorrection : L.confirm}
      allowNotInView={keep && existing.length > 0}
      extra={existing.length > 0 && (
        <div className="anchors">
          <label className="anchors__keep">
            <input type="checkbox" checked={keep} onChange={(e) => setKeep(e.target.checked)} />
            {L.keepEarlier}
          </label>
          <ul className="anchors__list">
            {existing.map((a) => (
              <li key={a.frame_index}>
                <button type="button" className="linkbtn" onClick={() => goTo(a.frame_index)}>
                  {L.frameAt(formatNumber(a.frame_index), formatClock(a.frame_index / video.fps, true))}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    />
  );
}
