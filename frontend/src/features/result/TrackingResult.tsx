import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, urls } from "../../api/client";
import { navigate } from "../../app/router";
import type {
  EventTimeline,
  Scorecards,
  Job,
  MomentumTimeline,
  MotionTimeline,
  RoundEdits,
  TrackingTimeline,
} from "../../contracts/generated";
import { usePoseFrames } from "../../hooks/usePoseFrames";
import {
  EVENT_TAG_LABELS,
  EXCLUSION_LABELS,
  OUTDATED_LABELS,
  RESULT_LABELS,
  ROUND_EDIT_LABELS,
  SCOPE_LABELS,
  SELECTION_LABELS,
} from "../../labels";
import { Button } from "../../ui";
import { IconAlert } from "../../ui/icons";
import { addRound, editsOf, moveEdge, removeRound } from "../match/roundEdit";
import { EMPTY_STATS } from "../../model/analysis";
import type { Side } from "../../model/analysis";
import { OVERLAY_STYLE } from "../../contracts/overlayStyle";
import {
  eventFrame,
  exclusionIntervals,
  frameMs,
  isFrameExcluded,
  measuredStats,
  motionSums,
  redShare,
  sampleAt,
  shownShare,
  sideOfFighter,
  toDamageViews,
  toTimelineEvents,
  totals,
} from "../../model/measured";
import { qualityIn, qualityIndex } from "../../model/quality";
import { scopeRange, validScope } from "../../model/scope";
import type { Scope } from "../../model/scope";
import { VideoClock, formatClock, useClock, useDisposeClock } from "../../player/clock";
import type { Layers } from "../../player/draw";
import { effectsAt } from "../../player/effects";
import { frameAt } from "../../player/geometry";
import { OverlayCanvas } from "../../player/OverlayCanvas";
import { bodyCenter } from "../../player/overlay";
import type { OverlayFlash, OverlayPerson, OverlayRing, OverlayScene } from "../../player/overlay";
import { EventList } from "./EventList";
import { ExclusionEditor } from "./ExclusionEditor";
import { ExportPanel } from "./ExportPanel";
import { JudgingPanel } from "./JudgingPanel";
import { FighterHeader } from "./FighterHeader";
import { MomentumPanel } from "./MomentumPanel";
import { PlaybackBar } from "./PlaybackBar";
import { ScopeBar } from "./ScopeBar";
import { StatPanel } from "./StatPanel";
import { Timeline } from "./Timeline";
import type { MomentumSeries, RoundEditing } from "./Timeline";
import { TrackingLanes } from "./TrackingLanes";
import { TrackingLog } from "./TrackingLog";
import { TrackQuality } from "./TrackQuality";

const R = RESULT_LABELS.screen;
const UNATTRIBUTED_TAG = (pct: number) => ({
  label: EVENT_TAG_LABELS.unattributed, tone: "amber" as const, title: EVENT_TAG_LABELS.unattributedHelp(pct),
});
const STATE_TEXT = RESULT_LABELS.quality.state;

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return ["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(target.tagName) ||
    target.isContentEditable || target.getAttribute("role") === "slider";
}

type Tab = "events" | "tracking" | "judging" | "export";

/** Fullscreen on the stage (video + overlay together), not on the bare <video>. */
function toggleFullscreen(el: HTMLElement | null) {
  if (document.fullscreenElement) void document.exitFullscreen();
  else void el?.requestFullscreen?.();
}

/** Result screen for a real analysis: identities, measured events, statistics and the
 * experimental momentum on the real video. Missing measurements show "—". */
export function TrackingResult({ job: polled, onRecalculate }: { job: Job; onRecalculate?: () => void }) {
  // A save (bout format, rounds) returns the updated job: shown at once, until polling brings it too.
  const [fresh, setFresh] = useState<Job | null>(null);
  const job = fresh && fresh.job_id === polled.job_id && Date.parse(fresh.updated_at) >= Date.parse(polled.updated_at)
    ? fresh : polled;
  const av = job.outputs.analysis_video!;
  const tracking = job.outputs.tracking!;
  const video = av.video;
  const [clock] = useState(() => new VideoClock(video.frame_count / video.fps, video.fps));
  useDisposeClock(clock);
  const snap = useClock(clock);
  const [layers, setLayers] = useState<Layers>({ skeleton: true, strikes: true, distance: false });
  const stageRef = useRef<HTMLDivElement>(null);
  const [others, setOthers] = useState(true);
  const [timeline, setTimeline] = useState<TrackingTimeline | null>(null);
  const [events, setEvents] = useState<EventTimeline | null>(null);
  const [motion, setMotion] = useState<MotionTimeline | null>(null);
  const [momentum, setMomentum] = useState<MomentumTimeline | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("events");
  // Which stretch of the bout the side panels refer to (the momentum is always the playhead value).
  const [wantedScope, setScope] = useState<Scope>({ kind: "playhead" });
  const [problem, setProblem] = useState<string | null>(null);
  const [scorecards, setScorecards] = useState<Scorecards | null>(null);
  const [scProblem, setScProblem] = useState<string | null>(null);
  const [scVersion, setScVersion] = useState(0);
  // Everything below refers to the presented frame: snap.time is its media time.
  const frame = frameAt(snap.time, video.fps, video.frame_count);
  const poses = usePoseFrames(job.job_id, video.frame_count, tracking.cache_key);
  const posesRef = useRef(poses);
  posesRef.current = poses;
  const names = useMemo(() => ({
    red: job.fighters[0]?.display_name ?? SELECTION_LABELS.defaultNames.red,
    blue: job.fighters[1]?.display_name ?? SELECTION_LABELS.defaultNames.blue,
  }), [job.fighters]);
  const eventsKey = job.outputs.events?.cache_key;
  const scoringKey = job.outputs.scoring?.cache_key;

  const { ensure } = poses;
  useEffect(() => ensure(frame), [ensure, frame]);
  useEffect(() => {
    const c = new AbortController();
    api.trackingTimeline(job.job_id, c.signal).then(setTimeline, () => undefined);
    return () => c.abort();
  }, [job.job_id, tracking.cache_key]);
  useEffect(() => {
    if (!eventsKey) return;
    const c = new AbortController();
    const fail = (e: unknown) => { if (!c.signal.aborted) setProblem(e instanceof Error ? e.message : String(e)); };
    api.events(job.job_id, c.signal).then(setEvents, fail);
    api.motion(job.job_id, c.signal).then(setMotion, fail);
    return () => c.abort();
  }, [job.job_id, eventsKey]);
  useEffect(() => {
    if (!scoringKey) return;
    const c = new AbortController();
    api.momentum(job.job_id, c.signal).then(setMomentum, (e: unknown) => {
      if (!c.signal.aborted) setProblem(e instanceof Error ? e.message : String(e));
    });
    return () => c.abort();
  }, [job.job_id, scoringKey]);

  // AI scorecards: computed by the server from the cached analysis, the match details and the rounds in effect
  const matchKey = JSON.stringify([job.match ?? null, job.bout.scheduled_rounds, job.bout.round_length_s,
                                   job.rounds.map((r) => [r.index, r.start_frame, r.end_frame])]);
  useEffect(() => {
    if (!eventsKey) return;
    const c = new AbortController();
    setScProblem(null);
    api.scorecards(job.job_id, c.signal).then(setScorecards, (e: unknown) => {
      if (!c.signal.aborted) setScProblem(e instanceof Error ? e.message : String(e));
    });
    return () => c.abort();
  }, [job.job_id, eventsKey, scoringKey, matchKey, scVersion]);

  useEffect(() => {
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
      else if (k === "o") setOthers((v) => !v);
      else if (k === "f") toggleFullscreen(stageRef.current);
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [clock]);

  // Excluded parts the momentum was computed with; statistics, effects and the list follow them.
  const segments = useMemo(() => momentum?.exclusions ?? [], [momentum]);
  const iv = useMemo(() => exclusionIntervals(segments, video.fps), [segments, video.fps]);
  const excludedIds = useMemo(() => new Set((events?.events ?? [])
    .filter((e) => isFrameExcluded(eventFrame(e), segments)).map((e) => e.event_id)), [events, segments]);
  const eventFrames = useMemo(() => (events?.events ?? []).map(eventFrame), [events]);
  const sums = useMemo(() => (motion ? motionSums(motion, iv) : null), [motion, iv]);
  const tEvents = useMemo(
    () => (events ? toTimelineEvents(events.events, momentum?.contributions ?? null, timeline, segments,
                                     UNATTRIBUTED_TAG) : []),
    [events, momentum, timeline, segments]);
  const damage = useMemo(() => (events ? toDamageViews(events.damage, segments) : []), [events, segments]);
  const series = useMemo<MomentumSeries | null>(() => (momentum ? {
    t: momentum.sample_ms.map((ms) => ms / 1000),
    red: momentum.red_share.map((v) => v / 100),
    insufficient: momentum.insufficient,
  } : null), [momentum]);
  // Statistics and momentum refer to the presented frame (the MP4 export computes the same).
  const tMs = frameMs(frame, video.fps);
  const red = momentum
    ? shownShare(redShare(totals(momentum.contributions, tMs, momentum.parameters, iv), momentum.parameters.prior))
    : null;
  const insufficient = momentum ? (momentum.insufficient[sampleAt(momentum.sample_ms, tMs)] ?? false) : false;
  // Scope of the side panels: one frame range for the statistics and the data quality of both sides.
  const scope = validScope(wantedScope, job.rounds);
  const range = scopeRange(scope, job.rounds, frame, video.frame_count);
  const clockOf = (f: number) => formatClock(f / video.fps);
  const rangeText = range ? SCOPE_LABELS.range(clockOf(range.start), clockOf(range.end)) : null;
  const scopeNote = !range ? null
    : scope.kind === "round" ? SCOPE_LABELS.note.round(scope.index, clockOf(range.start), clockOf(range.end))
      : SCOPE_LABELS.note[scope.kind](clockOf(range.start), clockOf(range.end));
  const quality = useMemo(() => (timeline ? qualityIndex(timeline, segments) : null), [timeline, segments]);
  const statsFor = (side: Side) =>
    (events && sums && range
      ? measuredStats(side, range.end, frameMs(range.end, video.fps), events.events, sums, segments, iv,
                      range.start, frameMs(range.start, video.fps))
      : EMPTY_STATS);
  const excludedNow = isFrameExcluded(frame, segments);
  const selected = events?.events.find((e) => e.event_id === selectedId) ?? null;
  const warnings = events && layers.strikes ? effectsAt(events.events, snap.time, excludedIds).warnings : [];

  // What the overlay draws for the frame presented at `time` (called per video frame).
  const sceneAt = useCallback((time: number): OverlayScene | null => {
    const f = frameAt(time, video.fps, video.frame_count);
    posesRef.current.ensure(f); // also prefetches the next chunk
    const rec = posesRef.current.get(f);
    if (!rec || rec === "loading") return null; // no data: draw nothing rather than guess
    const people: OverlayPerson[] = rec.detections.map((d) => {
      // fighter_id is only set when the identity is verified on this detection
      const side = sideOfFighter(d.fighter_id);
      const state = side ? rec.fighters.find((x) => x.fighter_id === d.fighter_id)?.state : undefined;
      return { keypoints: d.keypoints, role: side ?? "other", label: side ? names[side] : undefined,
               state: state === "occluded" ? "occluded" : "tracked" };
    });
    // Effects at this video time: the striking limb of the actor's current skeleton is
    // highlighted; without a visible limb only the measured joint position is marked.
    const fx = effectsAt(events?.events ?? [], time, excludedIds);
    const flashes: OverlayFlash[] = fx.flashes.map(({ event: e, strength }) => {
      const side = sideOfFighter(e.actor);
      const actor = side ? people.find((x) => x.role === side) : undefined;
      const joints = e.limb ? OVERLAY_STYLE.limbs[e.limb] : null;
      return { limb: actor && joints ? joints.map((j) => actor.keypoints[j]!).filter(Boolean) : null,
               at: e.location ?? null, side, strength };
    });
    const rings: OverlayRing[] = fx.rings.map(({ event: e, strength, labelled }) =>
      ({ x: e.location!.x, y: e.location!.y, strength, labelled }));
    const redP = people.find((x) => x.role === "red");
    const blueP = people.find((x) => x.role === "blue");
    const a = redP ? bodyCenter(redP.keypoints) : null;
    const b = blueP ? bodyCenter(blueP.keypoints) : null;
    const value = motion ? (motion.distance[sampleAt(motion.sample_ms, frameMs(f, video.fps))] ?? null) : null;
    return { people, flashes, rings, distance: a && b ? { a, b, value } : null };
  }, [video.fps, video.frame_count, names, events, motion, excludedIds]);
  const overlayLayers = useMemo(() => ({ ...layers, others }), [layers, others]);

  const record = poses.get(frame);
  const states = record && record !== "loading" ? record.fighters : [];
  const stateOf = (id: string) => states.find((s) => s.fighter_id === id)?.state;
  const anchors = tracking.anchors;

  const rename = (side: Side, name: string) => {
    const next = { ...names, [side]: name };
    api.setNames(job.job_id, next).catch((e: unknown) => setProblem(e instanceof Error ? e.message : String(e)));
  };
  const rerun = () => api.submitSelection(job.job_id, { anchors }).then(
    () => navigate({ mode: "analysis", screen: "processing", jobId: job.job_id }),
    (e: unknown) => setProblem(e instanceof Error ? e.message : String(e)));
  // One request: corners, names and selection change together on the server and every
  // result (identities, events, statistics, momentum) is derived again from the swapped
  // fighter ids, so no panel or drawing can disagree.
  // Rounds: the timeline edges and "add a round" save at once (manual always wins over automatic).
  const [roundBusy, setRoundBusy] = useState(false);
  const [roundProblem, setRoundProblem] = useState<string | null>(null);
  const [reprocessing, setReprocessing] = useState(false);
  const autoRounds = job.outputs.broadcast?.rounds ?? [];
  const saveRounds = (edits: RoundEdits) => {
    setRoundBusy(true);
    setRoundProblem(null);
    api.setRounds(job.job_id, edits).then((updated) => {
      setFresh(updated);
      setScVersion((n) => n + 1);
    }, (e: unknown) => setRoundProblem(e instanceof Error ? e.message : String(e))).finally(() => setRoundBusy(false));
  };
  const roundEditing: RoundEditing = {
    onEdge: (index, edge, seconds) => saveRounds(moveEdge(editsOf(job.match), job.rounds, index, edge,
                                                          edge === "end" ? seconds * video.fps - 1 : seconds * video.fps,
                                                          video.fps, video.frame_count)),
    onRemove: (index) => saveRounds(removeRound(editsOf(job.match), index, autoRounds)),
  };
  const addRoundHere = () => {
    const next = addRound(editsOf(job.match), job.rounds, frame, video.fps, video.frame_count, job.bout.round_length_s,
                          job.bout.scheduled_rounds);
    if (next) saveRounds(next);
    else setRoundProblem(ROUND_EDIT_LABELS.noRoom);
  };
  const reprocess = () => {
    setReprocessing(true);
    api.reprocess(job.job_id).then(() => onRecalculate?.(),
                                   (e: unknown) => setProblem(e instanceof Error ? e.message : String(e)))
      .finally(() => setReprocessing(false));
  };

  const swap = () => {
    api.swapCorners(job.job_id).then(() => onRecalculate?.(),
                                     (e: unknown) => setProblem(e instanceof Error ? e.message : String(e)));
  };
  const panel = (side: Side) => (
    <StatPanel side={side} name={names[side]} stats={statsFor(side)} scopeNote={events ? scopeNote : null} demo={false}
               emptyNote={eventsKey ? RESULT_LABELS.stats.loading : RESULT_LABELS.stats.noMotion}
               quality={tracking.fighters[side === "red" ? 0 : 1] && timeline && (
                 <TrackQuality side={side} quality={quality && range ? qualityIn(quality, side, range) : null}
                               legacy={tracking.fighters[side === "red" ? 0 : 1]} frames={video.frame_count}
                               now={stateOf(side === "red" ? "fighter_a" : "fighter_b")}
                               scopeNote={quality ? scopeNote : null} />
               )} />
  );

  return (
    <div className="result">
      <FighterHeader names={names} red={red} demo={false} insufficient={insufficient} excluded={excludedNow}
                     actions={{ onRename: rename, onSwap: swap,
                                onReselect: () => navigate({ mode: "analysis", screen: "select", jobId: job.job_id }),
                                onExport: eventsKey && scoringKey ? () => setTab("export") : undefined }} />
      <div className="result__left">{panel("red")}</div>
      <div className="result__stage">
        {job.outdated.length > 0 && (
          <div className="outdated" role="status">
            <IconAlert />
            <div className="outdated__text">
              <strong>{OUTDATED_LABELS.title}</strong>
              <span>{OUTDATED_LABELS.text}</span>
            </div>
            <Button size="sm" variant="primary" disabled={reprocessing} onClick={reprocess}>
              {reprocessing ? OUTDATED_LABELS.busy : OUTDATED_LABELS.action}
            </Button>
          </div>
        )}
        <div ref={stageRef} className="stage stage--synced" style={{ aspectRatio: `${video.width} / ${video.height}` }}>
          <video ref={clock.attach} className="stage__video stage__video--contain" src={urls.video(job.job_id)}
                 playsInline preload="auto" onClick={() => clock.toggle()}
                 onDoubleClick={() => toggleFullscreen(stageRef.current)} />
          <OverlayCanvas clock={clock} width={video.width} height={video.height} sceneAt={sceneAt}
                         layers={overlayLayers} version={poses.loaded} />
          {record === "loading" && layers.skeleton && <span className="stage__loading">{R.posesLoading}</span>}
          {warnings.length > 0 && (
            <div className="majorwarn" role="status">
              {warnings.map(({ event: e, strength }) => {
                const side = sideOfFighter(e.actor);
                return (
                  <span key={e.event_id} className="majorwarn__item" style={{ opacity: strength }}>
                    <span className="majorwarn__icon" aria-hidden="true">!</span>
                    <span className="majorwarn__type">{R.majorWarning[e.type]}</span>
                    {/* the name as written: it is not upper-cased with the warning */}
                    {side && <span>· {names[side]}</span>}
                  </span>
                );
              })}
            </div>
          )}
          <div className="idbadges">
            {(["fighter_a", "fighter_b"] as const).map((id) => {
              const st = stateOf(id);
              if (!st || st === "tracked") return null;
              return (
                <span key={id} className={`idbadge idbadge--${st} idbadge--${id === "fighter_a" ? "red" : "blue"}`}>
                  {id === "fighter_a" ? names.red : names.blue}: {STATE_TEXT[st]}
                </span>
              );
            })}
          </div>
        </div>
        <ScopeBar scope={scope} onScope={setScope} rounds={job.rounds} frame={frame} range={rangeText} />
        {!eventsKey && (
          <div className="inline-note">
            {R.noMotionNote}{" "}
            <button type="button" className="btn btn--sm btn--primary" onClick={() => void rerun()}>
              {R.runMotion}
            </button>
          </div>
        )}
        {problem && <p className="inline-warn">{problem}</p>}
      </div>
      <div className="result__right">{panel("blue")}</div>
      <div className="result__controls">
        <PlaybackBar clock={clock} snap={snap} layers={layers} onLayers={setLayers} disabled={false}
                     layerKeys={["skeleton", "strikes", "distance"]}
                     syncNote={clock.mode === "fallback" ? R.syncFallback : null}
                     extra={
                       <>
                         <button type="button" className="toggle" aria-pressed={others} title={R.othersTitle}
                                 onClick={() => setOthers((v) => !v)}>
                           <span className="toggle__dot" aria-hidden="true" />{R.others}
                         </button>
                         <button type="button" className="btn btn--sm btn--ghost" title={R.fullscreenTitle}
                                 onClick={() => toggleFullscreen(stageRef.current)}>{R.fullscreen}</button>
                       </>
                     } />
        <Timeline clock={clock} time={snap.time} events={tEvents} momentum={series} names={names} disabled={false}
                  excluded={segments.map((x) => [x.start_frame / video.fps, (x.end_frame + 1) / video.fps,
                                                 EXCLUSION_LABELS.reasons[x.reason]])}
                  rounds={job.rounds.map((r) => ({ index: r.index, startS: r.video_start_s, endS: r.video_end_s,
                                                   source: r.source }))}
                  roundEditing={roundBusy ? undefined : roundEditing} />
        <div className="roundbar">
          <button type="button" className="btn btn--sm" disabled={roundBusy} onClick={addRoundHere}>
            {roundBusy ? ROUND_EDIT_LABELS.saving : ROUND_EDIT_LABELS.add}
          </button>
          <span className="roundbar__help">{ROUND_EDIT_LABELS.help}</span>
          {roundProblem && <span className="inline-warn" role="alert">{roundProblem}</span>}
        </div>
        {eventsKey && (
          <ExclusionEditor jobId={job.job_id} frame={frame} fps={video.fps} frameCount={video.frame_count}
                           saved={job.exclusions} auto={job.auto_exclusions} eventFrames={eventFrames} clock={clock}
                           onJob={setFresh} />
        )}
      </div>
      <div className="result__events">
        <div className="rtabs" role="tablist" aria-label={R.tabsLabel}>
          <button type="button" role="tab" aria-selected={tab === "events"} className="rtabs__tab"
                  onClick={() => setTab("events")}>{R.tabs.events}</button>
          <button type="button" role="tab" aria-selected={tab === "tracking"} className="rtabs__tab"
                  onClick={() => setTab("tracking")}>{R.tabs.tracking}</button>
          <button type="button" role="tab" aria-selected={tab === "judging"} className="rtabs__tab"
                  onClick={() => setTab("judging")}>{R.tabs.judging}</button>
          <button type="button" role="tab" aria-selected={tab === "export"} className="rtabs__tab"
                  onClick={() => setTab("export")}>{R.tabs.export}</button>
        </div>
        {tab === "events" ? (
          <div className="evmom">
            <EventList events={tEvents} damage={damage} clock={clock} time={snap.time} names={names} demo={false}
                       selectedId={selectedId} onSelect={setSelectedId}
                       emptyText={eventsKey ? R.noEvents : R.noMotion} />
            {momentum && (
              <MomentumPanel contribs={momentum.contributions} params={momentum.parameters} tMs={tMs} iv={iv}
                             names={names} selected={selected}
                             unattributed={momentum.unattributed_event_ids.length} />
            )}
          </div>
        ) : tab === "tracking" ? (
          <div className="tracktab">
            <TrackingLanes clock={clock} time={snap.time} timeline={timeline} names={names}
                           review={tracking.review_points} />
            <TrackingLog jobId={job.job_id} tracking={tracking}
                         cuts={timeline?.cuts ?? job.outputs.tracking_prep?.cuts ?? []}
                         fps={video.fps} clock={clock} time={snap.time} names={names} />
          </div>
        ) : tab === "judging" ? (
          <JudgingPanel job={job} sc={scorecards} problem={scProblem} frame={frame} clock={clock}
                        onSaved={() => setScVersion((n) => n + 1)} onJob={setFresh} />
        ) : (
          <ExportPanel job={job} />
        )}
      </div>
    </div>
  );
}
