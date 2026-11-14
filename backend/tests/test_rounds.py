"""Bout format and effective rounds: the user's marks always win over automatic ones."""

from __future__ import annotations

from fastapi.testclient import TestClient

from fight_analyzer import rounds as rounds_mod
from fight_analyzer.config import RulesetSettings
from fight_analyzer.contracts import (
    AnalysisVideo,
    BroadcastSummary,
    JobStatus,
    MatchSetup,
    RoundMark,
    RoundNoteCode,
    RoundSegment,
    RoundSource,
    TrackingPrepSummary,
    TranscodeInfo,
    VideoInfo,
)
from fight_analyzer.jobs.store import JobStore

JSON = {"X-Fight-Analyzer": "1"}
FPS = 30


def auto_round(index: int, start: int, end: int, partial: bool = False) -> RoundSegment:
    return RoundSegment(index=index, start_frame=start, end_frame=end, video_start_s=start / FPS,
                        video_end_s=(end + 1) / FPS, clock_start=300, clock_end=88 if partial else 0,
                        source=RoundSource.ocr, confidence=0.99, partial=partial)


AUTO = [auto_round(1, 315, 9314), auto_round(2, 9525, 15914, partial=True)]


def analysis(store: JobStore, *, broadcast: bool = True, params: dict | None = None) -> str:
    job = store.create_job(params={
        "selection": {"anchors": [{"frame_index": 0, "red_detection_id": 0, "blue_detection_id": 1}]},
        "names": {"red": "Alexander Volkanovski", "blue": "Ilia Topuria"}, **(params or {})})
    store.claim_next("w")
    video = VideoInfo(width=1920, height=1080, fps=FPS, frame_count=16215, duration_ms=540500)
    store.set_video(job.job_id, "w", video.model_dump_json())
    transcode = TranscodeInfo(version=2, max_short_side=1080, max_fps=FPS, crf=20, preset="veryfast",
                              audio_bitrate_k=128)
    parts = {"analysis_video": AnalysisVideo(video=video, sha256="0" * 64, size_bytes=1, cache_key="v",
                                             transcode=transcode),
             "tracking_prep": TrackingPrepSummary(cache_key="p", cache_hit=False, shots=1, cuts=[], tracklets=2,
                                                  candidates=1, tracker="ocsort")}
    if broadcast:
        parts["broadcast"] = BroadcastSummary(cache_key="b", cache_hit=False, version=2, method="test",
                                              ocr_available=True, clock_share=0.9, rounds=AUTO, processing_s=1.0)
    store.merge_outputs(job.job_id, "w", **parts)
    store.finish(job.job_id, "w", JobStatus.completed)
    return job.job_id


def get(client: TestClient, job_id: str) -> dict:
    return client.get(f"/api/v1/jobs/{job_id}").json()


def test_automatic_rounds_are_used_until_the_user_edits(client: TestClient, store: JobStore):
    job = get(client, analysis(store))
    assert [(r["index"], r["source"], r["start_frame"]) for r in job["rounds"]] == [(1, "ocr", 315), (2, "ocr", 9525)]
    assert job["round_notes"] == [] and job["outdated"] == []


def test_a_manual_mark_replaces_the_automatic_round_of_its_number(client: TestClient, store: JobStore):
    job_id = analysis(store)
    r = client.put(f"/api/v1/jobs/{job_id}/rounds", headers=JSON,
                   json={"rounds": [{"number": 2, "start_frame": 9600, "end_frame": 15000}], "cleared_rounds": []})
    assert r.status_code == 200, r.text
    rounds = r.json()["rounds"]
    assert [(x["index"], x["source"], x["start_frame"], x["end_frame"]) for x in rounds] == \
        [(1, "ocr", 315, 9314), (2, "manual", 9600, 15000)]
    assert rounds[1]["confidence"] == 1 and rounds[1]["clock_start"] is None


def test_a_removed_automatic_round_stays_removed_until_restored(client: TestClient, store: JobStore):
    job_id = analysis(store)
    url = f"/api/v1/jobs/{job_id}/rounds"
    assert [x["index"] for x in client.put(url, headers=JSON, json={"rounds": [], "cleared_rounds": [2]})
            .json()["rounds"]] == [1]
    assert [x["index"] for x in client.put(url, headers=JSON, json={"rounds": [], "cleared_rounds": []})
            .json()["rounds"]] == [1, 2]


def test_an_automatic_round_that_conflicts_with_a_manual_one_is_left_out_with_a_note(client: TestClient,
                                                                                     store: JobStore):
    job_id = analysis(store)
    job = client.put(f"/api/v1/jobs/{job_id}/rounds", headers=JSON,
                     json={"rounds": [{"number": 1, "start_frame": 9000, "end_frame": 9600}]}).json()
    assert [(x["index"], x["source"]) for x in job["rounds"]] == [(1, "manual")]
    assert job["round_notes"] == [{"code": "auto_conflicts_manual", "round": 2, "other": 1}]


def test_round_edits_keep_the_ending_and_deductions(client: TestClient, store: JobStore):
    job_id = analysis(store)
    setup = {"scheduled_rounds": 3, "round_length_s": 300, "rounds": [], "cleared_rounds": [],
             "ending": {"method": "ko", "winner": "fighter_b", "round": 2, "time_s": 212},
             "deductions": [{"round": 1, "fighter_id": "fighter_a", "points": 1, "note": None}]}
    assert client.put(f"/api/v1/jobs/{job_id}/match", headers=JSON, json=setup).status_code == 200
    job = client.put(f"/api/v1/jobs/{job_id}/rounds", headers=JSON, json={"cleared_rounds": [1]}).json()
    assert job["match"]["ending"]["method"] == "ko" and len(job["match"]["deductions"]) == 1
    assert job["match"]["cleared_rounds"] == [1]


def test_bout_format_names_and_its_limits(client: TestClient, store: JobStore):
    job_id = analysis(store)
    url = f"/api/v1/jobs/{job_id}/bout"
    job = client.put(url, headers=JSON, json={"scheduled_rounds": 5, "title_fight": True,
                                               "names": {"red": " Volkanovski ", "blue": "Topuria"}}).json()
    assert job["bout"]["scheduled_rounds"] == 5 and job["bout"]["title_fight"] is True
    assert job["bout"]["names"] == {"red": "Volkanovski", "blue": "Topuria"}
    assert [f["display_name"] for f in job["fighters"]] == ["Volkanovski", "Topuria"]
    assert client.put(url, headers=JSON, json={"scheduled_rounds": 4}).status_code == 422
    # without names in the request the stored names stay
    assert client.put(url, headers=JSON, json={"scheduled_rounds": 5}).json()["bout"]["names"]["red"] == "Volkanovski"
    setup = {"rounds": [], "deductions": [{"round": 5, "fighter_id": "fighter_a", "points": 1, "note": None}]}
    assert client.put(f"/api/v1/jobs/{job_id}/match", headers=JSON, json={**setup, "scheduled_rounds": 5})\
        .status_code == 200
    r = client.put(url, headers=JSON, json={"scheduled_rounds": 3})
    assert r.status_code == 409 and r.json()["code"] == "bout_conflict"


def test_match_takes_round_count_and_length_from_the_bout(client: TestClient, store: JobStore):
    job_id = analysis(store)
    client.put(f"/api/v1/jobs/{job_id}/bout", headers=JSON, json={"scheduled_rounds": 5, "round_length_s": 300})
    job = client.put(f"/api/v1/jobs/{job_id}/match", headers=JSON,
                     json={"scheduled_rounds": 1, "round_length_s": 180, "rounds": []}).json()
    assert (job["match"]["scheduled_rounds"], job["match"]["round_length_s"]) == (5, 300)


def test_older_analysis_derives_its_bout_format_and_asks_for_reprocessing(client: TestClient, store: JobStore):
    job_id = analysis(store, broadcast=False, params={"match": MatchSetup(scheduled_rounds=5, round_length_s=240)
                                                      .model_dump(mode="json")})
    job = get(client, job_id)
    assert (job["bout"]["scheduled_rounds"], job["bout"]["round_length_s"]) == (5, 240)
    assert job["outdated"] == ["broadcast_missing"] and job["rounds"] == []
    assert client.get(f"/api/v1/jobs/{job_id}/broadcast").status_code == 409
    r = client.post(f"/api/v1/jobs/{job_id}/reprocess", headers=JSON)
    assert r.status_code == 202 and r.json()["status"] == "queued" and r.json()["outdated"] == []


def test_a_clock_rectangle_reads_the_clock_again(client: TestClient, store: JobStore):
    job_id = analysis(store)
    r = client.put(f"/api/v1/jobs/{job_id}/scorebug", headers=JSON,
                   json={"clock": {"x": 0.47, "y": 0.87, "w": 0.07, "h": 0.05}})
    assert r.status_code == 202 and r.json()["status"] == "queued"
    assert r.json()["outputs"]["broadcast"] is None
    assert store.get_params(job_id)["scorebug_roi"] == {"x": 0.47, "y": 0.87, "w": 0.07, "h": 0.05}
    bad = client.put(f"/api/v1/jobs/{job_id}/scorebug", headers=JSON,
                     json={"clock": {"x": 0.9, "y": 0.9, "w": 0.2, "h": 0.05}})
    assert bad.status_code == 422


def test_swapping_sides_keeps_the_bout_format_and_rounds(client: TestClient, store: JobStore):
    job_id = analysis(store)
    client.put(f"/api/v1/jobs/{job_id}/bout", headers=JSON, json={"scheduled_rounds": 5, "title_fight": True})
    client.put(f"/api/v1/jobs/{job_id}/rounds", headers=JSON,
               json={"rounds": [{"number": 2, "start_frame": 9600, "end_frame": 15000}], "cleared_rounds": [1]})
    job = client.post(f"/api/v1/jobs/{job_id}/swap", headers=JSON).json()
    assert job["bout"]["scheduled_rounds"] == 5 and job["bout"]["title_fight"] is True
    assert job["bout"]["names"] == {"red": "Ilia Topuria", "blue": "Alexander Volkanovski"}
    assert [(x["index"], x["source"]) for x in job["rounds"]] == [(2, "manual")]


def test_effective_rounds_rules():
    setup = MatchSetup(scheduled_rounds=3, rounds=[RoundMark(number=3, start_frame=16000, end_frame=16100)])
    beyond = auto_round(4, 16150, 16200)
    swapped = auto_round(2, 100, 200)  # read as R2 but before R1: out of order
    rounds, notes = rounds_mod.effective([AUTO[0], swapped, beyond], setup, 3, FPS, 300)
    assert [(r.index, r.source) for r in rounds] == [(1, RoundSource.ocr), (3, RoundSource.manual)]
    assert {(n.code, n.round) for n in notes} == {(RoundNoteCode.beyond_scheduled, 4),
                                                  (RoundNoteCode.out_of_order, 2)}
    assert rounds[1].partial  # 101 frames of a 300 s round


def test_judges_get_the_bout_format_and_effective_rounds():
    bout = rounds_mod.bout_config({"bout": {"scheduled_rounds": 5}}, RulesetSettings(), {"red": "A", "blue": "B"})
    setup = rounds_mod.judging_setup(MatchSetup(cleared_rounds=[2]), bout, AUTO)
    assert setup.scheduled_rounds == 5 and [(r.number, r.start_frame) for r in setup.rounds] == [(1, 315), (2, 9525)]
    assert setup.cleared_rounds == []
