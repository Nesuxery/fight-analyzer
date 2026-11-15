"""Data quality of the identities: what lowers the confidence of a frame, and the summary
of a frame range (v2 Bölüm 2.4 / 2.5). All material is synthetic."""

from __future__ import annotations

import json

import numpy as np

from fight_analyzer.config import IdentitySettings, TrackingSettings
from fight_analyzer.contracts import ExcludedSegment, FighterAnchor, QualityCause
from fight_analyzer.tracking import prep as prep_mod
from fight_analyzer.tracking import quality, results
from fight_analyzer.tracking.identity import OCCLUDED, TRACKED, UNCERTAIN, assign, build_context
from tests.support import quality_fixture
from tests.support.scenes import FPS, Actor, Scene, det_id_of, render

S, I = TrackingSettings(), IdentitySettings()
RED = Actor("A", shorts=(30, 30, 200), pattern="stripes")
BLUE = Actor("B", shorts=(160, 60, 20), pattern="solid")
FLOOR, HEIGHT = 330, 230
BIT = quality.BIT


def identities(scene: Scene, frame_height: int = 360):
    r = render(scene)
    prep = prep_mod.compute(iter(r.frames), r.arrays, FPS, frame_height, S)
    result = assign(build_context(r.arrays, prep, S, FPS, I),
                    [FighterAnchor(frame_index=3, red_detection_id=det_id_of(r, 3, "A"),
                                   blue_detection_id=det_id_of(r, 3, "B"))])
    mask = quality.frame_quality(r.arrays, prep, result.state, result.det, result.reason, frame_height, I)
    return result, mask


def test_clean_frames_are_measurable_without_a_cause():
    scene = Scene(actors={"A": RED, "B": BLUE}, frames=60)
    scene.path("A", [(0, 150, FLOOR, HEIGHT), (59, 170, FLOOR, HEIGHT)])
    scene.path("B", [(0, 470, FLOOR, HEIGHT), (59, 450, FLOOR, HEIGHT)])
    result, mask = identities(scene)
    assert (result.state == TRACKED).all() and not mask.any()
    assert quality.quality_runs(mask[:, 0]) == []


def test_a_lost_fighter_is_missing_footage_and_a_long_overlap_is_overlap():
    # B is not detected for 3 s (longer than the short gap): first "occluded" without a
    # detection, then "uncertain"; either way he cannot be measured
    scene = Scene(actors={"A": RED, "B": BLUE}, frames=150)
    scene.path("A", [(0, 150, FLOOR, HEIGHT), (149, 170, FLOOR, HEIGHT)])
    scene.path("B", [(0, 470, FLOOR, HEIGHT), (149, 450, FLOOR, HEIGHT)])
    scene.hide_detection("B", range(30, 120))
    result, mask = identities(scene)
    assert (result.state[30:120, 1] != TRACKED).all()
    assert (mask[30:120, 1] & quality.UNMEASURABLE).all()
    assert (mask[30:120, 1] & BIT[QualityCause.no_footage]).all()
    assert not mask[:, 0].any()  # the other fighter is untouched
    (run,) = quality.quality_runs(mask[:, 1])  # one stretch, until he is found again
    assert (run.start_frame, run.measurable, run.causes) == (30, False, [QualityCause.no_footage])
    assert 119 <= run.end_frame <= 125


def test_a_small_fighter_in_the_frame_is_a_far_camera():
    scene = Scene(actors={"A": RED, "B": BLUE}, frames=40)
    scene.path("A", [(0, 150, FLOOR, HEIGHT), (39, 170, FLOOR, HEIGHT)])
    scene.path("B", [(0, 470, FLOOR, HEIGHT), (39, 450, FLOOR, HEIGHT)])
    # the same poses on a frame four times as high: the fighters fill a fifth of it
    result, mask = identities(scene, frame_height=1440)
    assert (result.state == TRACKED).all()
    assert (mask & BIT[QualityCause.camera]).all() and not (mask & quality.UNMEASURABLE).any()


def test_summary_of_a_range_leaves_excluded_parts_out():
    state = np.zeros((100, 2), np.int8)
    mask = np.zeros((100, 2), np.uint8)
    change = np.zeros((100, 2), bool)
    state[10:30, 0] = UNCERTAIN  # 20 frames unknown after a cut ...
    mask[10:30, 0] = quality.UNMEASURABLE | BIT[QualityCause.camera]
    state[50:60, 0] = OCCLUDED  # ... and 10 carried through an overlap
    mask[50:60, 0] = BIT[QualityCause.overlap]
    change[[5, 30, 60], 0] = True
    whole = quality.summarize(state, mask, change, 0, 99, 10.0)[0]
    assert (whole.frames, whole.measurable_share, whole.occluded_share) == (100, 0.8, 0.1)
    assert (whole.uncertain_ms, whole.longest_uncertain_ms, whole.identity_changes) == (2000.0, 2000.0, 3)
    assert [(c.cause, c.share) for c in whole.causes] == [(QualityCause.camera, 0.2), (QualityCause.overlap, 0.1)]
    # frames 20-39 are a replay: not fight time, and they cut the unknown stretch short
    excluded = quality.excluded_mask([ExcludedSegment(start_frame=20, end_frame=39)], 100)
    part = quality.summarize(state, mask, change, 0, 99, 10.0, excluded)[0]
    assert (part.frames, part.uncertain_ms, part.longest_uncertain_ms, part.identity_changes) == (80, 1000.0, 1000.0, 2)
    assert part.measurable_share == 0.875
    # a range of its own (a round, up to the playhead)
    first = quality.summarize(state, mask, change, 0, 14, 10.0)[0]
    assert (first.frames, first.uncertain_ms, first.identity_changes) == (15, 500.0, 1)
    # the other fighter, and a range with no fight time at all
    assert quality.summarize(state, mask, change, 0, 99, 10.0)[1].causes == []
    empty = quality.summarize(state, mask, change, 20, 39, 10.0, excluded)[0]
    assert (empty.frames, empty.measurable_share, empty.causes) == (0, 0.0, [])
    assert quality.summarize(state, mask, change, 40, 10, 10.0)[0].frames == 0  # a range that ends before it starts
    # an exact tie rounds up, as Math.round does in the browser (Python's round would give 0.1812)
    assert quality._share(29, 160) == 0.1813 and quality._share(1, 32) == 0.0313


def test_golden_file_matches_the_summary():
    # frontend/tests/quality.test.ts checks the browser against the same file
    stored = json.loads(quality_fixture.FIXTURE.read_text(encoding="utf-8"))
    assert quality_fixture.build() == stored, "regenerate with python -m tests.support.quality_fixture"


def test_quality_survives_the_cache_and_older_entries_stay_readable(tmp_path):
    scene = Scene(actors={"A": RED, "B": BLUE}, frames=40)
    scene.path("A", [(0, 150, FLOOR, HEIGHT), (39, 170, FLOOR, HEIGHT)])
    scene.path("B", [(0, 470, FLOOR, HEIGHT), (39, 450, FLOOR, HEIGHT)])
    scene.hide_detection("B", range(10, 14))
    result, mask = identities(scene)
    from fight_analyzer.contracts import TrackingSummary
    summary = TrackingSummary(cache_key="k", cache_hit=False, method="m", anchors=[], shots=[], fighters=result.fighters,
                              identity_switches=0, swap_corrections=0, anchor_conflicts=0, uncertain_segments=[],
                              review_points=[])
    results.write(tmp_path, "new", result, summary, mask)
    loaded = results.read_arrays(tmp_path, "new")
    assert (loaded["quality"] == mask).all() and (loaded["change"] == result.change).all()
    blue = results.timeline(loaded)[1]
    assert blue.quality and blue.quality[0].start_frame == 10 and not blue.quality[0].measurable
    # an entry written before version 6 has neither array: it opens, without quality
    result.change = None
    results.write(tmp_path, "old", result, summary)
    old = results.read_arrays(tmp_path, "old")
    assert old is not None and "quality" not in old and "change" not in old
    assert results.timeline(old)[1].quality is None and results.timeline(old)[1].changes == []
