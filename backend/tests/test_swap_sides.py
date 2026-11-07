"""Swapping the corners ("Tarafları değiştir") moves every input that belongs to a person
with that person: the selection, the name, the finish winner and the point deductions.

Regression: the winner and the deductions are stored by fighter id and used to stay on the
corner, so after a swap they silently belonged to the other fighter."""

from __future__ import annotations

from fastapi.testclient import TestClient

from fight_analyzer.contracts import (
    AnalysisVideo,
    FighterId,
    FinishMethod,
    JobStatus,
    MatchEnding,
    MatchSetup,
    PointDeduction,
    TranscodeInfo,
    VideoInfo,
)
from fight_analyzer.contracts.fighters import swap_fighter_ids
from fight_analyzer.jobs.store import JobStore

JSON = {"X-Fight-Analyzer": "1"}
FPS = 30


def finished_analysis(store: JobStore) -> str:
    """A finished analysis with both fighters selected (no real video is needed to swap)."""
    job = store.create_job(params={
        "selection": {"anchors": [{"frame_index": 0, "red_detection_id": 0, "blue_detection_id": 1}]},
        "names": {"red": "Topuria", "blue": "Volkanovski"},
    })
    store.claim_next("w")
    video = VideoInfo(width=1280, height=720, fps=FPS, frame_count=9 * 60 * FPS, duration_ms=9 * 60 * 1000)
    transcode = TranscodeInfo(version=1, max_short_side=1080, max_fps=FPS, crf=20, preset="veryfast",
                              audio_bitrate_k=128)
    store.merge_outputs(job.job_id, "w", analysis_video=AnalysisVideo(
        video=video, sha256="0" * 64, size_bytes=1, cache_key="test", transcode=transcode))
    store.finish(job.job_id, "w", JobStatus.completed)
    return job.job_id


def recalculated(store: JobStore, job_id: str) -> None:
    """Stand-in for the worker: the swap queued the analysis again."""
    claimed = store.claim_next("w")
    assert claimed is not None and claimed.job_id == job_id
    store.finish(job_id, "w", JobStatus.completed)


def name_of(job: dict, fighter_id: str) -> str:
    return next(f["display_name"] for f in job["fighters"] if f["fighter_id"] == fighter_id)


def test_winner_and_deduction_stay_with_the_fighter_when_sides_are_swapped(client: TestClient, store: JobStore):
    job_id = finished_analysis(store)
    # Topuria (red corner) lost a point in round 1 and won by KO in round 2.
    setup = MatchSetup(ending=MatchEnding(method=FinishMethod.ko, winner=FighterId.fighter_a, round=2, time_s=212),
                       deductions=[PointDeduction(round=1, fighter_id=FighterId.fighter_a, points=1)])
    resp = client.put(f"/api/v1/jobs/{job_id}/match", json=setup.model_dump(mode="json"), headers=JSON)
    assert resp.status_code == 200
    before = store.get_params(job_id)

    resp = client.post(f"/api/v1/jobs/{job_id}/swap", headers=JSON)
    assert resp.status_code == 202
    job = resp.json()
    assert [f["display_name"] for f in job["fighters"]] == ["Volkanovski", "Topuria"]  # Topuria is blue now
    assert name_of(job, job["match"]["ending"]["winner"]) == "Topuria"
    assert [name_of(job, d["fighter_id"]) for d in job["match"]["deductions"]] == ["Topuria"]
    assert job["match"]["ending"]["round"] == 2 and job["match"]["deductions"][0]["round"] == 1

    # Swapping back restores every input exactly.
    recalculated(store, job_id)
    assert client.post(f"/api/v1/jobs/{job_id}/swap", headers=JSON).status_code == 202
    assert store.get_params(job_id) == before
    job = client.get(f"/api/v1/jobs/{job_id}").json()
    assert [f["display_name"] for f in job["fighters"]] == ["Topuria", "Volkanovski"]
    assert name_of(job, job["match"]["ending"]["winner"]) == "Topuria"
    assert [name_of(job, d["fighter_id"]) for d in job["match"]["deductions"]] == ["Topuria"]


def test_swapping_fighter_ids_changes_only_the_ids():
    setup = MatchSetup(
        ending=MatchEnding(method=FinishMethod.submission, winner=FighterId.fighter_b, round=3, time_s=95),
        deductions=[PointDeduction(round=1, fighter_id=FighterId.fighter_a, points=1, note="fighter_a"),
                    PointDeduction(round=2, fighter_id=FighterId.fighter_b, points=2)])
    swapped = swap_fighter_ids(setup)
    assert swapped.ending.winner is FighterId.fighter_a
    assert [d.fighter_id for d in swapped.deductions] == [FighterId.fighter_b, FighterId.fighter_a]
    assert swapped.deductions[0].note == "fighter_a"  # free text is not an id
    ids = {"ending": {"winner"}, "deductions": {"__all__": {"fighter_id"}}}
    assert swapped.model_dump(exclude=ids) == setup.model_dump(exclude=ids)
    assert MatchSetup.model_validate(swapped.model_dump()) == swapped  # still a valid setup
    assert setup.ending.winner is FighterId.fighter_b  # the original is left as it was
    assert swap_fighter_ids(swapped) == setup
