"""Automatic excluded parts: rounds first, detected parts where they add something,
and what the user turned off stays off."""

from __future__ import annotations

from fastapi.testclient import TestClient

from fight_analyzer import nonfight
from fight_analyzer.contracts import (
    AnalysisVideo,
    BroadcastSummary,
    ExcludedSegment,
    ExclusionReason,
    ExclusionSignal,
    JobStatus,
    MatchEnding,
    RoundSegment,
    RoundSource,
    TrackingPrepSummary,
    TranscodeInfo,
    VideoInfo,
)
from fight_analyzer.jobs.store import JobStore

JSON = {"X-Fight-Analyzer": "1"}
FPS = 30.0
FRAMES = 16215


def rnd(index: int, start: int, end: int, source: RoundSource = RoundSource.ocr, partial: bool = False,
        confidence: float = 0.99) -> RoundSegment:
    return RoundSegment(index=index, start_frame=start, end_frame=end, video_start_s=start / FPS,
                        video_end_s=(end + 1) / FPS, source=source, confidence=confidence, partial=partial)


R1, R2 = rnd(1, 315, 9314), rnd(2, 9525, 15914, partial=True)


def spans(parts, reason: ExclusionReason | None = None) -> list[tuple[int, int]]:
    return [(p.start_frame, p.end_frame) for p in parts if reason is None or p.reason == reason]


def detected(start: int, end: int, reason: ExclusionReason, conf: float = 0.6) -> ExcludedSegment:
    return nonfight.auto_segment(start, end, reason, [ExclusionSignal.scorebug_missing], conf)


# ---- from the rounds ------------------------------------------------------------------------------

def test_intro_and_break_are_certain_the_end_of_the_bout_is_not():
    parts = nonfight.from_rounds([R1, R2], 5, None, FRAMES)
    assert [(p.reason, p.start_frame, p.end_frame) for p in parts] == [
        (ExclusionReason.intro, 0, 314), (ExclusionReason.break_, 9315, 9524)]
    assert all(p.source == "auto" and p.signals == [ExclusionSignal.outside_rounds] and p.confidence == 0.99
               for p in parts)
    assert parts[0].auto_id == "intro-0-314"
    # round 2 of 5 without an ending: a third round may follow, so nothing after it is claimed
    assert spans(parts, ExclusionReason.post_fight) == []


def test_post_fight_needs_the_last_scheduled_round_or_an_early_ending():
    assert spans(nonfight.from_rounds([R1, R2], 2, None, FRAMES), ExclusionReason.post_fight) == [(15915, FRAMES - 1)]
    ko = MatchEnding(method="ko", winner="fighter_b", round=2)
    assert spans(nonfight.from_rounds([R1, R2], 5, ko, FRAMES), ExclusionReason.post_fight) == [(15915, FRAMES - 1)]
    # a finish entered for another round, or a decision (which needs all rounds), claims nothing here
    assert spans(nonfight.from_rounds([R1, R2], 5, MatchEnding(method="ko", winner="fighter_b", round=3), FRAMES),
                 ExclusionReason.post_fight) == []
    assert spans(nonfight.from_rounds([R1, R2], 5, MatchEnding(method="decision"), FRAMES),
                 ExclusionReason.post_fight) == []
    # a finish without its round: only when the last round found ended early in the recording
    no_round = MatchEnding(method="tko", winner="fighter_a")
    assert spans(nonfight.from_rounds([R1, R2], 5, no_round, FRAMES), ExclusionReason.post_fight) == [(15915, FRAMES - 1)]
    assert spans(nonfight.from_rounds([R1], 5, no_round, FRAMES), ExclusionReason.post_fight) == []


def test_a_missing_round_number_is_not_called_a_break_or_an_intro():
    r3 = rnd(3, 9525, 15914)
    assert spans(nonfight.from_rounds([R1, r3], 5, None, FRAMES)) == [(0, 314)]  # R2 may be in the gap
    assert spans(nonfight.from_rounds([R2], 5, None, FRAMES)) == []  # R1 may be before it
    assert nonfight.from_rounds([], 3, None, FRAMES) == []
    assert spans(nonfight.from_rounds([rnd(1, 0, 9000)], 3, None, FRAMES)) == []  # recording starts inside R1


def test_manual_rounds_count_like_any_other_with_full_confidence():
    manual = rnd(1, 400, 9314, RoundSource.manual, confidence=1.0)
    parts = nonfight.from_rounds([manual, R2], 5, None, FRAMES)
    assert [(p.start_frame, p.end_frame, p.confidence) for p in parts] == [(0, 399, 1.0), (9315, 9524, 0.99)]


# ---- rounds and detected parts together ---------------------------------------------------------------

def test_detected_parts_fill_what_the_rounds_leave():
    claims = nonfight.from_rounds([R1, R2], 5, None, FRAMES)
    found = [detected(0, 314, ExclusionReason.intro),  # same as the claim: adds nothing
             detected(3000, 3600, ExclusionReason.replay, 0.8),  # inside round 1: stays
             detected(9330, 9540, ExclusionReason.replay),  # in the break; the half second left inside R2 is dropped
             detected(15915, FRAMES - 1, ExclusionReason.post_fight)]  # no claim after R2: used
    parts = nonfight.combine(claims, found, [R1, R2], FPS, FRAMES)
    assert [(p.reason, p.start_frame, p.end_frame) for p in parts] == [
        (ExclusionReason.intro, 0, 314), (ExclusionReason.replay, 3000, 3600),
        (ExclusionReason.break_, 9315, 9524), (ExclusionReason.post_fight, 15915, FRAMES - 1)]
    assert parts[1].confidence == 0.8 and parts[1].auto_id == "replay-3000-3600"
    assert parts[3].signals == [ExclusionSignal.scorebug_missing]


def test_a_detected_end_never_reaches_into_a_round_in_effect():
    longer = rnd(2, 9525, 16000, RoundSource.manual, confidence=1.0)  # the user moved the end of R2
    parts = nonfight.combine([], [detected(15915, FRAMES - 1, ExclusionReason.post_fight)], [R1, longer], FPS, FRAMES)
    assert spans(parts) == [(16001, FRAMES - 1)]
    # a replay or stoppage keeps its place inside a round, manual or not
    inside = nonfight.combine([], [detected(15000, 15300, ExclusionReason.stoppage)], [R1, longer], FPS, FRAMES)
    assert spans(inside) == [(15000, 15300)]
    # so does a break found inside one round (scorebug away, clock standing still): there it is
    # a timeout ("mola"), "break" ("ara") is only used outside the rounds
    held = nonfight.combine([], [detected(15000, 15300, ExclusionReason.break_)], [R1, longer], FPS, FRAMES)
    assert [(p.reason, p.start_frame, p.end_frame, p.auto_id) for p in held] == [
        (ExclusionReason.timeout, 15000, 15300, "timeout-15000-15300")]
    # one that reaches out of the round is a break, and only its part outside the rounds
    across = nonfight.combine([], [detected(15900, 16100, ExclusionReason.break_)], [R1, longer], FPS, FRAMES)
    assert [(p.reason, p.start_frame, p.end_frame) for p in across] == [(ExclusionReason.break_, 16001, 16100)]
    # without rounds there is nothing to be inside of: a break
    alone = nonfight.combine([], [detected(15000, 15300, ExclusionReason.break_)], [], FPS, FRAMES)
    assert [p.reason for p in alone] == [ExclusionReason.break_]
    # without rounds the detected parts stand on their own
    assert spans(nonfight.combine([], [detected(100, 400, ExclusionReason.replay)], [], FPS, FRAMES)) == [(100, 400)]


# ---- turned off by the user -----------------------------------------------------------------------------

def test_a_part_stays_off_through_small_changes_and_comes_back_after_large_ones():
    off = [{"start_frame": 9315, "end_frame": 9524, "reason": "break"}]
    same, moved, grown = (detected(a, b, ExclusionReason.break_) for a, b in ((9315, 9524), (9300, 9530), (9000, 9524)))
    assert [nonfight.is_dismissed(x, off) for x in (same, moved, grown)] == [True, True, False]
    auto = nonfight.with_dismissed([same, detected(3000, 3600, ExclusionReason.replay)], off)
    assert [a.dismissed for a in auto] == [True, False]
    assert spans(nonfight.effective([], auto, FRAMES)) == [(3000, 3600)]


def test_turning_parts_off_keeps_ranges_of_parts_that_are_not_there_now():
    auto = nonfight.with_dismissed([detected(0, 314, ExclusionReason.intro), detected(3000, 3600, ExclusionReason.replay)],
                                   [{"start_frame": 0, "end_frame": 314, "reason": "intro"}])
    stored = [{"start_frame": 0, "end_frame": 314, "reason": "intro"},
              {"start_frame": 9315, "end_frame": 9524, "reason": "break"}]  # its round is removed right now
    ranges = nonfight.dismissed_ranges(auto, ["replay-3000-3600"], stored)
    assert [(d["start_frame"], d["end_frame"]) for d in ranges] == [(9315, 9524), (3000, 3600)]  # the intro is on again


def test_parts_in_effect_are_the_users_and_the_automatic_ones_merged():
    manual = [ExcludedSegment(start_frame=280, end_frame=500, reason="other")]
    auto = nonfight.with_dismissed([detected(0, 314, ExclusionReason.intro), detected(9315, 9524, ExclusionReason.break_)], [])
    parts = nonfight.effective(manual, auto, FRAMES)
    assert [(p.start_frame, p.end_frame, p.reason, p.source) for p in parts] == [
        (0, 500, ExclusionReason.intro, "auto"), (9315, 9524, ExclusionReason.break_, "auto")]
    assert not hasattr(parts[0], "dismissed")


# ---- on the job ---------------------------------------------------------------------------------------------

def analysis(store: JobStore, *, version: int = 2, segments: list[ExcludedSegment] | None = None,
             tracking=None, events=None) -> str:
    job = store.create_job(params={
        "selection": {"anchors": [{"frame_index": 0, "red_detection_id": 0, "blue_detection_id": 1}]}})
    store.claim_next("w")
    video = VideoInfo(width=1920, height=1080, fps=FPS, frame_count=FRAMES, duration_ms=540500)
    store.set_video(job.job_id, "w", video.model_dump_json())
    transcode = TranscodeInfo(version=2, max_short_side=1080, max_fps=FPS, crf=20, preset="veryfast",
                              audio_bitrate_k=128)
    store.merge_outputs(
        job.job_id, "w",
        analysis_video=AnalysisVideo(video=video, sha256="0" * 64, size_bytes=1, cache_key="v", transcode=transcode),
        tracking_prep=TrackingPrepSummary(cache_key="p", cache_hit=False, shots=1, cuts=[], tracklets=2, candidates=1,
                                          tracker="ocsort"),
        broadcast=BroadcastSummary(cache_key="b", cache_hit=False, version=version, method="test", ocr_available=True,
                                   clock_share=0.9, rounds=[R1, R2], segments=segments or [], scorebug_frame=4800,
                                   processing_s=1.0))
    if tracking is not None:
        store.merge_outputs(job.job_id, "w", tracking=tracking)
    if events is not None:
        store.merge_outputs(job.job_id, "w", events=events)
    store.finish(job.job_id, "w", JobStatus.completed)
    return job.job_id


def test_the_job_lists_automatic_parts_and_follows_round_edits(client: TestClient, store: JobStore):
    job_id = analysis(store, segments=[detected(15915, FRAMES - 1, ExclusionReason.post_fight)])
    url = f"/api/v1/jobs/{job_id}"
    job = client.get(url).json()
    assert [(a["reason"], a["start_frame"], a["end_frame"], a["dismissed"]) for a in job["auto_exclusions"]] == [
        ("intro", 0, 314, False), ("break", 9315, 9524, False), ("post_fight", 15915, FRAMES - 1, False)]
    assert job["exclusions"] == [] and job["outdated"] == []
    assert job["outputs"]["broadcast"]["scorebug_frame"] == 4800
    # the user moves the start of round 1: the intro follows the round in effect
    job = client.put(f"{url}/rounds", headers=JSON,
                     json={"rounds": [{"number": 1, "start_frame": 600, "end_frame": 9314}]}).json()
    assert (job["auto_exclusions"][0]["start_frame"], job["auto_exclusions"][0]["end_frame"]) == (0, 599)
    # removing round 2: no break is claimed any more, and the detected end gives way to nothing
    job = client.put(f"{url}/rounds", headers=JSON, json={"cleared_rounds": [2]}).json()
    assert [a["reason"] for a in job["auto_exclusions"]] == ["intro", "post_fight"]


def test_turning_an_automatic_part_off_and_on(client: TestClient, store: JobStore):
    job_id = analysis(store)
    url = f"/api/v1/jobs/{job_id}/exclusions/auto"
    job = client.put(url, headers=JSON, json={"dismissed": ["break-9315-9524"]}).json()
    assert [(a["auto_id"], a["dismissed"]) for a in job["auto_exclusions"]] == [
        ("intro-0-314", False), ("break-9315-9524", True)]
    assert store.get_params(job_id)["dismissed_auto"] == [{"start_frame": 9315, "end_frame": 9524, "reason": "break"}]
    assert client.put(url, headers=JSON, json={"dismissed": ["break-1-2"]}).status_code == 409
    job = client.put(url, headers=JSON, json={"dismissed": []}).json()
    assert not any(a["dismissed"] for a in job["auto_exclusions"]) and store.get_params(job_id)["dismissed_auto"] == []


def test_an_analysis_from_before_replay_detection_asks_for_reprocessing(client: TestClient, store: JobStore):
    job = client.get(f"/api/v1/jobs/{analysis(store, version=1)}").json()
    assert job["outdated"] == ["broadcast_outdated"]
    assert job["auto_exclusions"] == [] and len(job["rounds"]) == 2  # opens as before; nothing is excluded behind its back


def test_identities_from_before_the_appearance_model_ask_for_reprocessing(client: TestClient, store: JobStore):
    from fight_analyzer.contracts import TrackingSummary

    def with_tracking(version: int) -> dict:
        summary = TrackingSummary(cache_key="i", cache_hit=False, method="m", version=version, anchors=[], shots=[],
                                  fighters=[], identity_switches=0, swap_corrections=0, anchor_conflicts=0,
                                  uncertain_segments=[], review_points=[])
        return client.get(f"/api/v1/jobs/{analysis(store, tracking=summary)}").json()

    assert with_tracking(0)["outdated"] == ["identity_outdated"]  # opens as before, with the banner
    assert with_tracking(6)["outdated"] == []
    old = with_tracking(5)
    assert client.get(f"/api/v1/jobs/{old['job_id']}/tracking/quality").status_code in (409, 410)


def test_events_from_before_strike_outcomes_ask_for_reprocessing(client: TestClient, store: JobStore):
    from fight_analyzer.contracts import EventsSummary

    def with_events(**version) -> dict:
        summary = EventsSummary(cache_key="e", cache_hit=False, method="m", events=0, camera_known_share=1.0,
                                fighters=[], **version)
        return client.get(f"/api/v1/jobs/{analysis(store, events=summary)}").json()

    assert with_events()["outdated"] == ["events_outdated"]  # stored before the version was kept: opens, with the banner
    assert with_events(version=3)["outdated"] == ["events_outdated"]
    assert with_events(version=4)["outdated"] == ["events_outdated"]  # before the grappling states
    assert with_events(version=5)["outdated"] == []


def test_the_users_own_parts_are_always_stored_as_manual(client: TestClient, store: JobStore):
    job_id = analysis(store)
    body = {"segments": [{"start_frame": 3000, "end_frame": 3600, "reason": "replay", "source": "auto",
                          "auto_id": "replay-3000-3600", "confidence": 0.9, "signals": ["wipe"]}]}
    job = client.put(f"/api/v1/jobs/{job_id}/exclusions", headers=JSON, json=body).json()
    (mine,) = job["exclusions"]
    assert (mine["source"], mine["auto_id"], mine["confidence"], mine["signals"]) == ("manual", None, None, [])
