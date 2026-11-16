"""End-to-end with the real pose model: upload -> analysis copy -> poses ->
cache reuse -> reading results back after a restart. Uses a short clip made
from the two-person photo bundled with Ultralytics (not a fight video, so
this checks plumbing and data shapes, not accuracy)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fight_analyzer.api.app import create_app
from fight_analyzer.config import PoseSettings, Settings
from fight_analyzer.contracts import ComputeInfo, JobStatus
from fight_analyzer.jobs.store import JobStore
from fight_analyzer.jobs.worker import Worker, default_handlers
from tests.support.media import make_person_clip, make_video

PROJECT_MODELS = Path(__file__).resolve().parents[2] / "data" / "models"
MODEL = "yolo26n-pose.pt"
HEADERS = {"X-Fight-Analyzer": "1", "Content-Type": "application/octet-stream"}
JSON = {"X-Fight-Analyzer": "1"}

pytestmark = pytest.mark.skipif(
    not (PROJECT_MODELS / MODEL).is_file(),
    reason=f"{MODEL} not downloaded (python -m fight_analyzer.pose.models {MODEL})",
)

CPU = ComputeInfo(device="cpu", device_name="test", requested="auto", cuda_available=False,
                  torch_version="test", cpu_threads=1)


class Env:
    def __init__(self, root: Path) -> None:
        self.settings = Settings(data_dir=root / "data", pose_model=MODEL,
                                 models_dir_override=PROJECT_MODELS,
                                 pose=PoseSettings(preview_interval_s=0))
        self.client = TestClient(create_app(self.settings), base_url="http://127.0.0.1")
        self.store = JobStore(self.settings.db_path)
        self.worker = Worker(self.settings, self.store, default_handlers(), compute=CPU)

    def upload(self, data: bytes, name: str = "people.mp4") -> str:
        resp = self.client.post("/api/v1/jobs", params={"filename": name}, content=data,
                                headers=HEADERS)
        assert resp.status_code == 201, resp.text
        return resp.json()["job_id"]

    def process(self, data: bytes) -> dict:
        job_id = self.upload(data)
        assert self.worker.run_once()
        return self.client.get(f"/api/v1/jobs/{job_id}").json()


@pytest.fixture(scope="module")
def env(tmp_path_factory) -> Env:
    return Env(tmp_path_factory.mktemp("e2e"))


@pytest.fixture(scope="module")
def clip(tmp_path_factory) -> bytes:
    return make_person_clip(tmp_path_factory.mktemp("clip") / "people.mp4").read_bytes()


@pytest.fixture(scope="module")
def first(env: Env, clip: bytes) -> dict:
    return env.process(clip)


def test_poses_extracted_and_job_waits_for_selection(first: dict):
    assert first["status"] == "awaiting_selection", first["error"]
    video = first["outputs"]["analysis_video"]["video"]
    pose = first["outputs"]["pose"]
    assert (video["fps_num"], video["fps_den"], video["frame_count"]) == (5, 1, 5)
    assert not pose["cache_hit"] and pose["frame_count"] == 5
    assert pose["max_persons"] >= 2 and pose["detection_count"] >= 10
    assert pose["model"]["name"] == MODEL and len(pose["model"]["weights_sha256"]) == 64
    detail = first["progress_detail"]  # the broadcast analysis is the last stage before the selection
    assert detail["stage"] == "broadcast" and detail["unit"] == "frames"
    assert detail["done"] == detail["total"] == 5
    assert first["progress"] == pytest.approx(0.74)
    prep = first["outputs"]["tracking_prep"]
    assert prep["shots"] == 1 and prep["cuts"] == [] and prep["candidates"] >= 1
    assert "ocsort" in prep["tracker"]
    broadcast = first["outputs"]["broadcast"]  # no scorebug in this clip: nothing claimed
    assert broadcast["rounds"] == [] and broadcast["roi"] is None
    assert first["rounds"] == [] and first["outdated"] == []


def test_pose_chunks_have_everyone_without_identities(env: Env, first: dict):
    chunk = env.client.get(f"/api/v1/jobs/{first['job_id']}/poses",
                           params={"start": 1, "count": 10}).json()
    assert chunk["start_frame"] == 1 and len(chunk["frames"]) == 4
    assert chunk["keypoint_names"][0] == "nose" and chunk["keypoint_names"][16] == "right_ankle"
    frame = chunk["frames"][0]
    assert frame["frame_index"] == 1 and frame["timestamp_ms"] == pytest.approx(200)
    assert len(frame["detections"]) >= 2
    for det in frame["detections"]:
        assert det["fighter_id"] is None  # nobody is a fighter before the selection
        assert len(det["keypoints"]) == 17
        assert 0 <= det["confidence"] <= 1


def test_video_range_and_preview(env: Env, first: dict):
    job_id = first["job_id"]
    ranged = env.client.get(f"/api/v1/jobs/{job_id}/video", headers={"Range": "bytes=0-99"})
    assert ranged.status_code == 206 and len(ranged.content) == 100
    assert ranged.headers["content-type"] == "video/mp4"
    preview = env.client.get(f"/api/v1/jobs/{job_id}/preview").json()
    image = env.client.get(f"/api/v1/jobs/{job_id}/preview.jpg", params={"seq": preview["seq"]})
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    assert preview["width"] == 640 and preview["frame"]["detections"]


def test_history_thumbnail(env: Env, first: dict, clip: bytes):
    job_id = first["job_id"]
    image = env.client.get(f"/api/v1/jobs/{job_id}/thumbnail.jpg")
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    assert image.headers["cache-control"] == "no-cache" and len(image.content) > 1000
    assert len(list((env.settings.jobs_dir / job_id).glob("thumb-*.jpg"))) == 1
    queued = env.upload(clip, "queued.mp4")  # no analysis copy yet
    missing = env.client.get(f"/api/v1/jobs/{queued}/thumbnail.jpg")
    assert missing.status_code == 404 and missing.json()["code"] == "thumbnail_unavailable"
    assert env.worker.run_once()  # leave the queue empty for the next tests


def test_same_video_reuses_both_caches(env: Env, first: dict, clip: bytes):
    second = env.process(clip)
    assert second["status"] == "awaiting_selection"
    assert second["outputs"]["analysis_video"]["cache_hit"]
    assert second["outputs"]["pose"]["cache_hit"]
    assert second["outputs"]["pose"]["cache_key"] == first["outputs"]["pose"]["cache_key"]


def test_results_survive_restart(env: Env, first: dict):
    reopened = Env(env.settings.data_dir.parent)  # new app + store + worker on the same data
    job = reopened.client.get(f"/api/v1/jobs/{first['job_id']}").json()
    assert job["status"] == "awaiting_selection"
    chunk = reopened.client.get(f"/api/v1/jobs/{first['job_id']}/poses").json()
    assert len(chunk["frames"]) == 5


def test_cancel_during_pose_writes_no_cache(env: Env, tmp_path: Path, monkeypatch):
    data = make_video(tmp_path / "other.mp4", seconds=2, rate="10").read_bytes()
    job_id = env.upload(data, "other.mp4")
    before = set((env.settings.cache_dir / "pose").iterdir())
    import fight_analyzer.pipeline.pose as pose_stage

    real = pose_stage.write_preview

    def cancel_on_preview(*args, **kwargs):
        real(*args, **kwargs)
        env.store.request_cancel(job_id)

    monkeypatch.setattr(pose_stage, "write_preview", cancel_on_preview)
    env.worker.run_once()
    job = env.store.get_job(job_id)
    assert job.status is JobStatus.cancelled
    assert set((env.settings.cache_dir / "pose").iterdir()) == before


def test_analysis_errors_are_reported(env: Env, tmp_path: Path, monkeypatch):
    data = make_video(tmp_path / "boom.mp4", seconds=1, rate="10").read_bytes()
    job_id = env.upload(data, "boom.mp4")
    from fight_analyzer.pose.engine import PoseEngine

    def boom(self, frames):
        raise RuntimeError("simulated inference failure")

    monkeypatch.setattr(PoseEngine, "infer", boom)
    env.worker.run_once()
    job = env.store.get_job(job_id)
    assert job.status is JobStatus.failed and job.error.code == "pose_failed"
    assert job.error.stage == "pose"

    job_id = env.upload(make_video(tmp_path / "gone.mp4", seconds=1, rate="12").read_bytes())
    source = env.store.get_job(job_id).source
    (env.settings.uploads_dir / source.sha256 / "source.mp4").unlink()
    env.worker.run_once()
    job = env.store.get_job(job_id)
    assert job.status is JobStatus.failed and job.error.code == "source_missing"


def test_selection_runs_identity_tracking(env: Env, first: dict):
    job_id = first["job_id"]
    cands = env.client.get(f"/api/v1/jobs/{job_id}/candidates").json()
    frame = cands["frames"][0]
    assert len(frame["detections"]) >= 2
    order = sorted(frame["detections"], key=lambda d: d["bbox"]["x1"])
    left, right = order[0]["detection_id"], order[-1]["detection_id"]
    anchor = {"frame_index": frame["frame_index"], "red_detection_id": left, "blue_detection_id": right}

    same = {"anchors": [{**anchor, "blue_detection_id": left}]}
    resp = env.client.post(f"/api/v1/jobs/{job_id}/selection", json=same, headers=JSON)
    assert resp.status_code == 422 and "same person" in resp.text  # validation, not a parsing error
    ghost = {"anchors": [{**anchor, "blue_detection_id": 99}]}
    resp = env.client.post(f"/api/v1/jobs/{job_id}/selection", json=ghost, headers=JSON)
    assert resp.status_code == 422 and resp.json()["code"] == "invalid_selection"

    resp = env.client.post(f"/api/v1/jobs/{job_id}/selection", json={"anchors": [anchor]}, headers=JSON)
    assert resp.status_code == 202, resp.text
    assert resp.json()["status"] == "queued"
    busy = env.client.post(f"/api/v1/jobs/{job_id}/selection", json={"anchors": [anchor]}, headers=JSON)
    assert busy.status_code == 409  # queued: wait until it is done
    assert env.worker.run_once()
    job = env.client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "completed", job["error"]
    tracking = job["outputs"]["tracking"]
    assert tracking["anchors"] == [anchor]
    red, blue = tracking["fighters"]
    # The two people in this photo overlap in every frame: identity is kept by
    # continuity and reported as "occluded" (only the selected frame is "tracked").
    for stats in (red, blue):
        assert stats["tracked_frames"] + stats["occluded_frames"] == 5 and stats["uncertain_ms"] == 0
    assert red["fighter_id"] == "fighter_a" and tracking["identity_switches"] == 0
    assert [f["display_name"] for f in job["fighters"]] == ["Dövüşçü 1", "Dövüşçü 2"]

    chunk = env.client.get(f"/api/v1/jobs/{job_id}/poses").json()
    for record in chunk["frames"]:
        states = {s["fighter_id"]: s for s in record["fighters"]}
        assert states["fighter_a"]["state"] in ("tracked", "occluded")
        assert states["fighter_a"]["detection_id"] == left
        dets = {d["detection_id"]: d for d in record["detections"]}
        assert dets[states["fighter_a"]["detection_id"]]["fighter_id"] == "fighter_a"
        assert dets[states["fighter_b"]["detection_id"]]["fighter_id"] == "fighter_b"
        assert all(d["track_id"] is not None for d in dets.values() if d["fighter_id"])
    timeline = env.client.get(f"/api/v1/jobs/{job_id}/tracking/timeline").json()
    assert all(run["state"] != "uncertain" for f in timeline["fighters"] for run in f["runs"])
    # since identity version 6 the result says how it was made, and carries the data quality
    assert tracking["version"] == 7 and tracking["extra_cuts"] == [] and job["outdated"] == []
    assert all(f["quality"] is not None for f in timeline["fighters"])
    report = env.client.get(f"/api/v1/jobs/{job_id}/tracking/quality").json()
    (bout,) = report["scopes"]  # no rounds on this clip: the whole video only
    assert bout["round"] is None and (bout["start_frame"], bout["end_frame"]) == (0, 4)
    for q in bout["fighters"]:
        assert q["frames"] == 5 and q["uncertain_ms"] == 0 and 0 <= q["measurable_share"] <= 1

    # Motion analysis on a still photo (real model output): measured, and nothing is invented.
    assert job["outputs"]["events"]["camera_known_share"] >= 0 and job["outputs"]["scoring"] is not None
    events = env.client.get(f"/api/v1/jobs/{job_id}/events").json()
    assert not [e for e in events["events"] if e["type"] in ("punch", "kick", "knee", "knockdown", "takedown")]
    assert all(e["attribution_confidence"] is not None for e in events["events"])
    assert job["outputs"]["events"]["version"] == 4 and events["damage"] == []  # nothing landed on a photo
    assert job["outputs"]["scoring"]["unattributed_events"] == 0
    motion = env.client.get(f"/api/v1/jobs/{job_id}/motion").json()
    assert len(motion["fighters"]) == 2 and len(motion["sample_ms"]) == len(motion["fighters"][0]["valid"]) >= 1
    momentum = env.client.get(f"/api/v1/jobs/{job_id}/momentum").json()
    assert momentum["experimental"] and momentum["parameters"]["half_life_s"] == 20
    assert momentum["contributions"] == [] and all(abs(v - 50) < 1e-9 for v in momentum["red_share"])
    assert momentum["unattributed_event_ids"] == []

    named = env.client.put(f"/api/v1/jobs/{job_id}/names", json={"red": "Sol", "blue": "Sağ"}, headers=JSON)
    assert [f["display_name"] for f in named.json()["fighters"]] == ["Sol", "Sağ"]

    # Swapping corners: selection and names change together in one request, everything is
    # derived again from the swapped ids (fast: poses and tracking preparation are cached).
    resp = env.client.post(f"/api/v1/jobs/{job_id}/swap", headers=JSON)
    assert resp.status_code == 202 and resp.json()["status"] == "queued"
    assert [f["display_name"] for f in resp.json()["fighters"]] == ["Sağ", "Sol"]
    assert resp.json()["selection"]["anchors"] == [{**anchor, "red_detection_id": right, "blue_detection_id": left}]
    assert env.client.post(f"/api/v1/jobs/{job_id}/swap", headers=JSON).status_code == 409  # busy until done
    assert env.worker.run_once()
    again = env.client.get(f"/api/v1/jobs/{job_id}").json()
    assert again["status"] == "completed"
    assert again["outputs"]["pose"]["cache_hit"] and again["outputs"]["tracking_prep"]["cache_hit"]
    assert again["outputs"]["events"] is not None and again["outputs"]["scoring"] is not None
    rec = env.client.get(f"/api/v1/jobs/{job_id}/poses", params={"count": 1}).json()["frames"][0]
    red_det = next(s for s in rec["fighters"] if s["fighter_id"] == "fighter_a")["detection_id"]
    assert red_det == right
    dets = {d["detection_id"]: d for d in rec["detections"]}
    assert dets[right]["fighter_id"] == "fighter_a" and dets[left]["fighter_id"] == "fighter_b"


def test_export_of_finished_analysis(env: Env, first: dict, clip: bytes):
    """MP4 + CSV + JSON as a separate job, from the same data the result screen reads."""
    job_id = first["job_id"]
    job = env.client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "completed" and job["outputs"]["scoring"] is not None
    options = {"skeleton": True, "effects": True, "momentum": True, "counters": True, "distance": True, "others": True}
    resp = env.client.post(f"/api/v1/jobs/{job_id}/exports", json={"options": options}, headers=JSON)
    assert resp.status_code == 202, resp.text
    exp = resp.json()
    assert exp["job_type"] == "export" and exp["status"] == "queued"
    again = env.client.post(f"/api/v1/jobs/{job_id}/exports", json={"options": options}, headers=JSON)
    assert again.status_code == 409 and again.json()["code"] == "export_running"  # one at a time per analysis
    assert [f["display_name"] for f in exp["fighters"]] == [f["display_name"] for f in job["fighters"]]
    # exports are listed per analysis, not among the analyses
    assert all(j["job_type"] == "analysis" for j in env.client.get("/api/v1/jobs").json()["jobs"])
    assert [j["job_id"] for j in env.client.get(f"/api/v1/jobs/{job_id}/exports").json()["jobs"]] == [exp["job_id"]]
    assert env.client.get(f"/api/v1/jobs/{exp['job_id']}/files/video").status_code == 409  # not done yet
    assert env.client.get(f"/api/v1/jobs/{exp['job_id']}/events").status_code == 404  # not an analysis

    assert env.worker.run_once()
    done = env.client.get(f"/api/v1/jobs/{exp['job_id']}").json()
    assert done["status"] == "completed", done["error"]
    summary = done["outputs"]["export"]
    frames = job["outputs"]["analysis_video"]["video"]["frame_count"]
    assert summary["frames"] == frames and summary["options"] == options
    assert summary["source_keys"]["events"] == job["outputs"]["events"]["cache_key"]

    mp4 = env.client.get(f"/api/v1/jobs/{exp['job_id']}/files/video")
    assert mp4.status_code == 200 and mp4.headers["content-type"] == "video/mp4" and mp4.content[4:8] == b"ftyp"
    assert "attachment" in mp4.headers["content-disposition"]
    rows = env.client.get(f"/api/v1/jobs/{exp['job_id']}/files/metrics").text.strip().splitlines()
    assert len(rows) == frames + 1 and rows[0].startswith("frame,time_s,red_share,blue_share")
    bundle = env.client.get(f"/api/v1/jobs/{exp['job_id']}/files/bundle").json()
    browser_events = env.client.get(f"/api/v1/jobs/{job_id}/events").json()["events"]
    browser_momentum = env.client.get(f"/api/v1/jobs/{job_id}/momentum").json()
    assert bundle["events"] == browser_events
    assert bundle["momentum_contributions"] == browser_momentum["contributions"]
    assert bundle["settings"]["motion"] and bundle["settings"]["overlay_style"]["kp_min_conf"] == 0.5
    assert bundle["scorecards"]["ai_estimate"] is True and len(bundle["scorecards"]["judges"]) == 3

    # not ready: an analysis that has not finished cannot be exported
    waiting = env.upload(clip, name="queued.mp4")
    assert env.client.post(f"/api/v1/jobs/{waiting}/exports", json={"options": options},
                           headers=JSON).status_code == 409
    assert env.client.post(f"/api/v1/jobs/{waiting}/cancel", headers=JSON).json()["status"] == "cancelled"


def test_excluded_parts_recompute_momentum_only(env: Env, first: dict):
    """A replay marked by the user: events stay, momentum is computed again with the exclusion,
    in the request itself (no trip through the worker)."""
    job_id = first["job_id"]
    before = env.client.get(f"/api/v1/jobs/{job_id}").json()
    bad = {"segments": [{"start_frame": 3, "end_frame": 1}]}
    assert env.client.put(f"/api/v1/jobs/{job_id}/exclusions", json=bad, headers=JSON).status_code == 422
    body = {"segments": [{"start_frame": 3, "end_frame": 999, "reason": "replay"}, {"start_frame": 0, "end_frame": 0}]}
    resp = env.client.put(f"/api/v1/jobs/{job_id}/exclusions", json=body, headers=JSON)
    assert resp.status_code == 200 and resp.json()["status"] == "completed", resp.text
    frames = before["outputs"]["analysis_video"]["video"]["frame_count"]
    # clipped to the video and sorted
    assert [(x["start_frame"], x["end_frame"]) for x in resp.json()["exclusions"]] == [(0, 0), (3, frames - 1)]
    assert env.worker.run_once() is False  # nothing was queued
    after = env.client.get(f"/api/v1/jobs/{job_id}").json()
    assert after["status"] == "completed", after["error"]
    assert after["outputs"]["events"]["cache_key"] == before["outputs"]["events"]["cache_key"]  # events reused
    assert after["outputs"]["scoring"]["cache_key"] != before["outputs"]["scoring"]["cache_key"]
    momentum = env.client.get(f"/api/v1/jobs/{job_id}/momentum").json()
    assert [(x["start_frame"], x["end_frame"]) for x in momentum["exclusions"]] == [(0, 0), (3, frames - 1)]
    # clearing them restores the previous result from the cache
    cleared = env.client.put(f"/api/v1/jobs/{job_id}/exclusions", json={"segments": []}, headers=JSON).json()
    assert cleared["exclusions"] == [] and cleared["outputs"]["scoring"]["cache_hit"]
    assert cleared["outputs"]["scoring"]["cache_key"] == before["outputs"]["scoring"]["cache_key"]
    # while the analysis is being processed the parts cannot be changed
    queued = env.client.post(f"/api/v1/jobs/{job_id}/reprocess", headers=JSON)
    assert queued.status_code == 202
    assert env.client.put(f"/api/v1/jobs/{job_id}/exclusions", json=body, headers=JSON).status_code == 409
    assert env.worker.run_once()
    assert env.client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "completed"


def test_validation_tool_reports_against_labels(env: Env, first: dict):
    """Sheets + label template, and a report that counts identity and strike outcomes."""
    import json

    from fight_analyzer import validation

    job_id = first["job_id"]
    out = validation.sheet(job_id, 2, env.settings)
    template = json.loads((out / "labels.template.json").read_text(encoding="utf-8"))
    assert len(list(out.glob("frame_*.jpg"))) == len(template["identity"]) == 3
    job = env.client.get(f"/api/v1/jobs/{job_id}").json()
    frames = env.client.get(f"/api/v1/jobs/{job_id}/poses", params={"count": 3}).json()["frames"]
    ours = [{s["fighter_id"]: s["detection_id"] for s in f["fighters"]} for f in frames]
    labels = {"role": "tuning",
              "identity": [{"frame": 0, "red": ours[0]["fighter_a"], "blue": ours[0]["fighter_b"], "referee": None},
                           # labelled the other way round: both corners count as an identity swap
                           {"frame": 2, "red": ours[2]["fighter_b"], "blue": ours[2]["fighter_a"], "referee": None}],
              "strike_window": [0, 4], "strikes": [{"frame": 2, "actor": "red", "kind": "punch"}]}
    report = validation.compare(job_id, labels, env.settings)
    assert report["identity"]["by_scenario"]["toplam"] == {"doğru kişi": 2, "kimlik karışması": 2}
    assert report["strikes"]["labelled"] == 1 and len(report["strikes"]["missed"]) == 1  # a still photo: no attempts
    assert job["status"] == "completed"


def test_match_setup_and_ai_scorecards(env: Env, first: dict):
    """Rounds/ending are user input; scorecards are an AI estimate that refuses to score too little data."""
    job_id = first["job_id"]
    bad = {"scheduled_rounds": 3, "rounds": [{"number": 1, "start_frame": 999, "end_frame": 1000}]}
    assert env.client.put(f"/api/v1/jobs/{job_id}/match", json=bad, headers=JSON).status_code == 422
    finish_without_winner = {"scheduled_rounds": 3, "ending": {"method": "ko"}}
    assert env.client.put(f"/api/v1/jobs/{job_id}/match", json=finish_without_winner, headers=JSON).status_code == 422
    setup = {"scheduled_rounds": 1, "rounds": [{"number": 1, "start_frame": 0, "end_frame": 4}],
             "ending": {"method": "decision"}}
    job = env.client.put(f"/api/v1/jobs/{job_id}/match", json=setup, headers=JSON).json()
    assert job["match"]["rounds"][0]["end_frame"] == 4 and job["status"] == "completed"  # nothing recomputed
    sc = env.client.get(f"/api/v1/jobs/{job_id}/scorecards").json()
    assert sc["ai_estimate"] is True and "resmi" in sc["disclaimer"] and len(sc["judges"]) == 3
    assert sc["rounds"][0]["scorable"] is False  # one second of a still photo is not a round
    assert sc["verdict"]["status"] == "not_computed" and sc["verdict"]["winner"] is None
    ko = {**setup, "ending": {"method": "tko", "winner": "fighter_b", "round": 1, "time_s": 1}}
    env.client.put(f"/api/v1/jobs/{job_id}/match", json=ko, headers=JSON)
    v = env.client.get(f"/api/v1/jobs/{job_id}/scorecards").json()["verdict"]
    assert v["status"] == "finish" and v["winner"] == "fighter_b" and v["source"] == "user_input"


def test_time_outside_the_rounds_is_excluded_at_once_and_can_be_turned_off(env: Env, first: dict):
    """Rounds and an early ending decide what is not fight time: the momentum follows in the
    same request (no trip through the worker), and one request turns an automatic part off."""
    job_id = first["job_id"]
    url = f"/api/v1/jobs/{job_id}"
    setup = {"rounds": [{"number": 1, "start_frame": 0, "end_frame": 2}],
             "ending": {"method": "ko", "winner": "fighter_a", "round": 1, "time_s": 1}}
    job = env.client.put(f"{url}/match", json=setup, headers=JSON).json()
    frames = job["outputs"]["analysis_video"]["video"]["frame_count"]
    assert job["status"] == "completed"  # computed in the request
    (auto,) = job["auto_exclusions"]
    assert (auto["reason"], auto["source"], auto["start_frame"], auto["end_frame"], auto["dismissed"]) ==         ("post_fight", "auto", 3, frames - 1, False)
    assert auto["signals"] == ["outside_rounds"] and auto["confidence"] == 1
    applied = job["outputs"]["scoring"]["exclusions"]
    assert [(x["start_frame"], x["end_frame"], x["source"]) for x in applied] == [(3, frames - 1, "auto")]
    momentum = env.client.get(f"{url}/momentum").json()
    assert [(x["start_frame"], x["reason"]) for x in momentum["exclusions"]] == [(3, "post_fight")]
    assert job["exclusions"] == []  # the user's own list is untouched

    off = env.client.put(f"{url}/exclusions/auto", json={"dismissed": [auto["auto_id"]]}, headers=JSON)
    assert off.status_code == 200 and off.json()["status"] == "completed"
    assert off.json()["auto_exclusions"][0]["dismissed"] is True and off.json()["outputs"]["scoring"]["exclusions"] == []
    assert env.client.put(f"{url}/exclusions/auto", json={"dismissed": ["replay-1-2"]}, headers=JSON).status_code == 409
    # a small round edit moves the part: it stays off; a large one makes it a new part
    moved = env.client.put(f"{url}/rounds", json={"rounds": [{"number": 1, "start_frame": 0, "end_frame": 1}]},
                           headers=JSON).json()
    assert [(a["start_frame"], a["dismissed"]) for a in moved["auto_exclusions"]] == [(2, True)]
    back = env.client.put(f"{url}/exclusions/auto", json={"dismissed": []}, headers=JSON).json()
    assert [(x["start_frame"], x["end_frame"]) for x in back["outputs"]["scoring"]["exclusions"]] == [(2, frames - 1)]
    # without the early ending nothing says the bout is over after round 1 of 3
    plain = env.client.put(f"{url}/match", json={"rounds": setup["rounds"]}, headers=JSON).json()
    assert plain["auto_exclusions"] == [] and plain["outputs"]["scoring"]["exclusions"] == []
    assert plain["outputs"]["scoring"]["cache_hit"] is True and env.worker.run_once() is False  # nothing was queued
