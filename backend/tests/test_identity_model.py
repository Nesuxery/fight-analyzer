"""Identity layer version 6 (v2 Bölüm 2c) on synthetic scenes with known ground truth:
camera cuts the preparation missed, the appearance model, third persons, frames
verified inside an overlap, and the count of temporary-id changes."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from fight_analyzer.config import IdentitySettings, TrackingSettings
from fight_analyzer.contracts import FighterAnchor
from fight_analyzer.tracking import identity, tracklets
from fight_analyzer.tracking import prep as prep_mod
from fight_analyzer.tracking.identity import OCCLUDED, TRACKED, UNCERTAIN, assign, build_context
from tests.support.scenes import FPS, Actor, Scene, det_id_of, evaluate, render

S, I = TrackingSettings(), IdentitySettings()
RED = Actor("A", shorts=(30, 30, 200), pattern="stripes")
BLUE = Actor("B", shorts=(160, 60, 20), pattern="solid")
REF = Actor("R", shorts=(60, 60, 60), torso=(25, 25, 25))
FLOOR, HEIGHT = 330, 230


def run(scene: Scene, anchors, settings: IdentitySettings = I, prepare=None):
    r = render(scene)
    prep = prep_mod.compute(iter(r.frames), r.arrays, FPS, 360, S)
    if prepare:
        prepare(r, prep)
    ctx = build_context(r.arrays, prep, S, FPS, settings)
    result = assign(ctx, [FighterAnchor(frame_index=f, red_detection_id=det_id_of(r, f, red),
                                        blue_detection_id=det_id_of(r, f, blue)) for f, red, blue in anchors])
    return r, prep, ctx, result, evaluate(r, result.det, result.state)


def moved(scene: Scene, pid: str, start: int, keys) -> None:
    """Replace a person's path from frame `start` on."""
    other = Scene(actors={}, frames=scene.frames)
    other.path(pid, keys)
    scene.place[pid][start:] = other.place[pid][start:]


# ---- camera cuts the preparation missed ----------------------------------------------------------------------

def test_missed_cuts_are_found_from_the_colour_change():
    rng = np.random.default_rng(1)
    step = rng.uniform(0.002, 0.008, 400).astype(np.float32)
    step[0] = 0.0
    step[100] = 0.08  # a cut between two shots of the same canvas: small, but alone and far above its surroundings
    step[150] = step[151] = 0.3  # a flash: into it and out again
    step[200:206] = 0.1  # a logo transition changes several frames in a row
    step[250:280] = np.linspace(0.01, 0.05, 30)  # a pan building up
    step[303] = 0.09  # right after a cut the preparation found
    assert identity.refine_cuts(step, [300], I, S.min_shot_frames) == [100, 300]
    assert identity.refine_cuts(step, [300], replace(I, extra_cut_floor=1.0), S.min_shot_frames) == [300]


def missed_cut_scene() -> Scene:
    """At frame 45 the camera changes without the picture changing much: the referee now stands
    where the red corner stood, the red corner where the referee stood."""
    scene = Scene(actors={"A": RED, "B": BLUE, "R": REF}, frames=100, shots={0: (70, 90, 60)})
    scene.path("A", [(0, 520, FLOOR, HEIGHT), (99, 520, FLOOR, HEIGHT)])
    scene.path("B", [(0, 320, FLOOR, HEIGHT), (99, 320, FLOOR, HEIGHT)])
    scene.path("R", [(0, 110, FLOOR, HEIGHT), (99, 110, FLOOR, HEIGHT)])
    moved(scene, "A", 45, [(45, 110, FLOOR, HEIGHT), (99, 110, FLOOR, HEIGHT)])
    moved(scene, "R", 45, [(45, 520, FLOOR, HEIGHT), (99, 520, FLOOR, HEIGHT)])
    return scene


def as_missed(r, prep) -> None:
    """What the preparation stores when it misses the cut at 45: one shot, the tracker ran
    through, and a modest colour change on that frame."""
    assert prep.cuts == []  # the histogram of the picture did not change: no cut found
    prep.cut_step[45] = 0.08
    det_frame = np.repeat(np.arange(r.arrays.frame_count), np.diff(r.arrays.det_offsets)).astype(np.int64)
    ids = prep.track_id
    before, after = det_frame == 44, det_frame == 45
    # the tracker kept the id of whoever stood at each place
    assert {int(ids[d]) for d in np.flatnonzero(before)} == {int(ids[d]) for d in np.flatnonzero(after)}
    assert tracklets.build_segments(det_frame, ids, prep.contact.astype(bool), prep.shot_id, S).max() == prep.seg_id.max()


def test_a_missed_cut_does_not_hand_the_fighter_to_whoever_stands_there():
    r, _, ctx, result, ev = run(missed_cut_scene(), [(5, "A", "B")], prepare=as_missed)
    assert ctx.extra_cuts == [45] and result.extra_cuts == [45]
    assert ev.wrong == [0, 0] and ev.switches == 0
    assert (result.state[60:, :] == TRACKED).all()  # found again on the other side by appearance
    assert int(result.shot_id[44]) == 0 and int(result.shot_id[45]) == 1
    # without the extra cut the identity follows the tracker's id onto the referee
    _, _, ctx, _, blind = run(missed_cut_scene(), [(5, "A", "B")], replace(I, extra_cut_floor=1.0), prepare=as_missed)
    assert ctx.extra_cuts == [] and blind.wrong[0] > 0


# ---- appearance model ----------------------------------------------------------------------------------------

def three_shots(last=None) -> Scene:
    scene = Scene(actors={"A": RED, "B": BLUE, **(last or {})}, frames=180,
                  shots={0: (70, 90, 60), 60: (110, 70, 40), 120: (60, 60, 100)})
    scene.path("A", [(0, 160, FLOOR, HEIGHT), (59, 180, FLOOR, HEIGHT)])
    scene.path("B", [(0, 470, FLOOR, HEIGHT), (59, 450, FLOOR, HEIGHT)])
    moved(scene, "A", 60, [(60, 460, FLOOR, HEIGHT), (119, 440, FLOOR, HEIGHT)])
    moved(scene, "B", 60, [(60, 170, FLOOR, HEIGHT), (119, 190, FLOOR, HEIGHT)])
    return scene


def test_the_model_samples_both_fighters_from_every_shot():
    scene = three_shots()
    moved(scene, "A", 120, [(120, 200, FLOOR, HEIGHT), (179, 210, FLOOR, HEIGHT)])
    moved(scene, "B", 120, [(120, 430, FLOOR, HEIGHT), (179, 420, FLOOR, HEIGHT)])
    _, prep, _, result, ev = run(scene, [(10, "A", "B")])
    assert prep.cuts == [60, 120] and ev.wrong == [0, 0]
    model = result.model
    assert model is not None and [len({shot for shot, _ in refs}) for refs in model.refs] == [3, 3]
    assert model.third == [] and 0.9 <= model.height_ratio <= 1.1
    assert all(0.5 < v < 1.0 for v in model.floor)  # his own samples look alike; a tolerance below that


def test_a_referee_seen_next_to_the_fighters_becomes_a_third_person():
    scene = Scene(actors={"A": RED, "B": BLUE, "R": REF}, frames=90)
    scene.path("A", [(0, 200, FLOOR, HEIGHT), (89, 210, FLOOR, HEIGHT)])
    scene.path("B", [(0, 440, FLOOR, HEIGHT), (89, 430, FLOOR, HEIGHT)])
    scene.path("R", [(0, 600, FLOOR + 6, HEIGHT * 1.05), (89, 590, FLOOR + 6, HEIGHT * 1.05)])
    _, _, _, result, ev = run(scene, [(5, "A", "B")])
    assert ev.wrong == [0, 0] and len(result.model.third) >= 1
    # a spectator far smaller than the fighters is no reference: he never takes an identity anyway
    scene.path("R", [(0, 600, FLOOR - 120, HEIGHT * 0.3), (89, 590, FLOOR - 120, HEIGHT * 0.3)])
    _, _, _, small, ev = run(scene, [(5, "A", "B")])
    assert ev.wrong == [0, 0] and small.model.third == []


def test_someone_who_only_looks_more_like_one_fighter_is_not_placed_after_a_cut():
    # third shot: a crowd shot with one person in bluish shorts of another pattern
    fan = Actor("C", shorts=(140, 90, 60), pattern="checker", torso=(200, 200, 200))
    scene = three_shots({"C": fan})
    scene.place["A"][120:] = [None] * 60
    scene.place["B"][120:] = [None] * 60
    scene.path("C", [(120, 320, FLOOR, HEIGHT), (179, 330, FLOOR, HEIGHT)])
    r, _, _, result, ev = run(scene, [(10, "A", "B")])
    assert ev.wrong == [0, 0] and (result.state[120:, :] == UNCERTAIN).all()
    assert result.fighters[1].tracked_frames == 120


# ---- frames verified inside an overlap ----------------------------------------------------------------------

def test_overlapping_boxes_with_both_fighters_visible_are_verified_frames():
    # at striking range the boxes overlap for a long time, but each fighter is fully visible
    scene = Scene(actors={"A": RED, "B": BLUE}, frames=120)
    scene.path("A", [(0, 180, FLOOR, HEIGHT), (30, 285, FLOOR, HEIGHT), (119, 285, FLOOR, HEIGHT)])
    scene.path("B", [(0, 460, FLOOR, HEIGHT), (30, 350, FLOOR, HEIGHT), (119, 350, FLOOR, HEIGHT)])
    r, prep, _, result, ev = run(scene, [(3, "A", "B")])
    assert ev.wrong == [0, 0]
    dets = result.det[40:110]
    assert prep.contact[dets].all()  # the preparation calls all of it an overlap
    assert (result.state[40:110] == TRACKED).all()  # every frame confirmed by its own appearance
    assert np.allclose(result.conf[40:110], I.confidence_verified)
    assert result.fighters[0].occluded_frames == 0 and result.fighters[0].uncertain_frames == 0


def test_one_fighter_in_front_of_the_other_is_verified_on_neither_box():
    # both boxes show the fighter in front: each looks like him, so neither frame is "verified"
    # and the identity never moves onto the other skeleton
    scene = Scene(actors={"A": RED, "B": BLUE}, frames=150)
    scene.path("A", [(0, 180, FLOOR, HEIGHT), (30, 300, FLOOR, HEIGHT), (110, 300, FLOOR, HEIGHT), (149, 180, FLOOR, HEIGHT)])
    scene.path("B", [(0, 460, FLOOR - 4, HEIGHT), (30, 312, FLOOR - 4, HEIGHT), (110, 312, FLOOR - 4, HEIGHT),
                     (149, 460, FLOOR - 4, HEIGHT)])
    _, _, _, result, ev = run(scene, [(3, "A", "B")])
    assert ev.wrong == [0, 0]
    assert (result.state[45:100] != TRACKED).all()
    # what the tracker carried through the overlap is less sure than a verified frame
    carried = (result.state == OCCLUDED) & (result.det >= 0)
    assert (result.conf[carried] <= I.confidence_recent + 1e-6).all()
    assert (result.state[140:] == TRACKED).all() and np.allclose(result.conf[140:], 1.0)


# ---- placed from an overlapping box after a cut -------------------------------------------------------------

def cut_into_striking_range(apart_from: int | None = None) -> Scene:
    """After the cut at 60 the fighters stand at striking range (their boxes overlap, both are
    visible); with `apart_from` they step apart from that frame on."""
    scene = Scene(actors={"A": RED, "B": BLUE}, frames=150, shots={0: (70, 90, 60), 60: (110, 70, 40)})
    scene.path("A", [(0, 160, FLOOR, HEIGHT), (59, 180, FLOOR, HEIGHT)])
    scene.path("B", [(0, 470, FLOOR, HEIGHT), (59, 450, FLOOR, HEIGHT)])
    stay = apart_from if apart_from is not None else 149
    a = [(60, 350, FLOOR, HEIGHT), (stay, 350, FLOOR, HEIGHT)]
    b = [(60, 285, FLOOR, HEIGHT), (stay, 285, FLOOR, HEIGHT)]
    if apart_from is not None:
        a += [(apart_from + 30, 470, FLOOR, HEIGHT), (149, 470, FLOOR, HEIGHT)]
        b += [(apart_from + 30, 170, FLOOR, HEIGHT), (149, 170, FLOOR, HEIGHT)]
    moved(scene, "A", 60, a)
    moved(scene, "B", 60, b)
    return scene


def test_an_identity_placed_from_an_overlapping_box_is_held_at_low_confidence():
    # never apart in the new shot: one frame's appearance placed them, nothing confirms it
    _, prep, _, result, ev = run(cut_into_striking_range(), [(10, "A", "B")])
    assert prep.cuts == [60] and ev.wrong == [0, 0]
    after = slice(60, 150)
    assert result.held[after].all() and not result.held[:60].any()
    assert (result.state[after] == OCCLUDED).all() and (result.det[after] >= 0).all()  # kept, not dropped
    assert (result.conf[after] <= I.confidence_unverified + 1e-6).all()
    assert [f.uncertain_frames for f in result.fighters] == [0, 0]


def test_a_few_verified_frames_without_overlap_confirm_the_held_identity():
    _, prep, _, result, ev = run(cut_into_striking_range(apart_from=90), [(10, "A", "B")])
    assert ev.wrong == [0, 0] and not result.held.any()
    # the frames held up to the confirmation count as any verified overlap frame
    assert (result.state[60:] == TRACKED).all()
    assert np.allclose(result.conf[60:90], I.confidence_verified) and np.allclose(result.conf[100:], 1.0)
    # with a count that is never reached the same frames stay held
    _, _, _, waiting, ev = run(cut_into_striking_range(apart_from=90), [(10, "A", "B")],
                               replace(I, acquire_confirm_frames=1000))
    assert ev.wrong == [0, 0] and waiting.held[60:].all()
    assert (waiting.conf[60:] <= I.confidence_unverified + 1e-6).all()


def test_a_selection_inside_the_shot_stands_in_for_the_confirmation():
    # the pass from the second selection follows both through the shot: its result counts
    _, _, _, result, ev = run(cut_into_striking_range(), [(10, "A", "B"), (140, "A", "B")])
    assert ev.wrong == [0, 0] and not result.held.any()
    assert (result.state[60:] == TRACKED).all()


# ---- temporary-id changes -----------------------------------------------------------------------------------

def test_id_changes_are_counted_once_on_the_final_result():
    scene = Scene(actors={"A": RED, "B": BLUE}, frames=90)
    scene.path("A", [(0, 150, FLOOR, HEIGHT), (20, 150, FLOOR, HEIGHT), (70, 490, FLOOR, HEIGHT), (89, 490, FLOOR, HEIGHT)])
    scene.path("B", [(0, 490, FLOOR - 4, HEIGHT), (20, 490, FLOOR - 4, HEIGHT), (70, 150, FLOOR - 4, HEIGHT),
                     (89, 150, FLOOR - 4, HEIGHT)])
    scene.hide_detection("B", range(42, 49))  # the tracker loses B behind A and starts a new id
    _, _, ctx, one, ev = run(scene, [(5, "A", "B")])
    assert ev.wrong == [0, 0]
    changes = [f.track_changes for f in one.fighters]
    assert changes == [int(one.change[:, 0].sum()), int(one.change[:, 1].sum())] and changes[1] >= 1
    # a second selection makes both passes cover the stretch between them: still counted once
    _, _, _, two, _ = run(scene, [(5, "A", "B"), (80, "A", "B")])
    assert [f.track_changes for f in two.fighters] == changes
