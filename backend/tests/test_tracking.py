"""Identity tracking on synthetic scenes with known ground truth.

Acceptance cases: fighters crossing, the referee stepping between them, a
short clinch (one detection missing), a camera cut with swapped positions,
look-alike fighters across a cut (must become uncertain, not guess), a
selection in the middle of the video (backward pass), correction by a second
selection, and a long overlap (must turn into "Takip belirsiz").
"""

from __future__ import annotations

import numpy as np
import pytest

from fight_analyzer.config import TrackingSettings
from fight_analyzer.contracts import FighterAnchor, FighterSelection, UncertainReason
from fight_analyzer.tracking import identity
from fight_analyzer.tracking import prep as prep_mod
from fight_analyzer.tracking.candidates import pick
from fight_analyzer.tracking.cuts import CutScorer, detect_cuts, signature
from fight_analyzer.tracking.identity import OCCLUDED, REASONS, TRACKED, UNCERTAIN, assign, build_context
from tests.support.scenes import FPS, Actor, Scene, det_id_of, evaluate, render

S = TrackingSettings()
RED = Actor("A", shorts=(30, 30, 200), pattern="stripes")  # red shorts, white stripes
BLUE = Actor("B", shorts=(160, 60, 20), pattern="solid")  # blue shorts
REF = Actor("R", shorts=(60, 60, 60), torso=(25, 25, 25))  # referee: dark shirt, grey trousers
FLOOR, HEIGHT = 330, 230


def run(scene: Scene, anchors: list[tuple[int, str | None, str | None]]):
    """Anchors are (frame, red person, blue person); None = not in the picture."""
    r = render(scene)
    prep = prep_mod.compute(iter(r.frames), r.arrays, FPS, 360, S)
    ctx = build_context(r.arrays, prep, S, FPS)

    def det(f, pid):
        return None if pid is None else det_id_of(r, f, pid)

    result = assign(ctx, [FighterAnchor(frame_index=f, red_detection_id=det(f, red), blue_detection_id=det(f, blue))
                          for f, red, blue in anchors])
    return r, prep, result, evaluate(r, result.det, result.state)


def test_cut_detection_ignores_motion_and_flashes():
    scene = Scene(actors={"A": RED, "B": BLUE}, frames=90, shots={0: (70, 90, 60), 45: (40, 40, 120)})
    scene.path("A", [(0, 100, FLOOR, HEIGHT), (89, 500, FLOOR, HEIGHT)])  # lots of motion
    scene.path("B", [(0, 500, FLOOR, HEIGHT), (89, 140, FLOOR, HEIGHT)])
    frames = render(scene).frames
    frames[20] = np.full_like(frames[20], 255)  # one-frame flash
    scorer = CutScorer()
    for frame in frames:
        scorer.add(signature(frame))
    assert detect_cuts(*scorer.finish(), S) == [45]


def test_cut_between_shots_of_the_same_canvas_is_found():
    # Same octagon canvas before and after: the histogram jump is modest but far above
    # the level of camera motion around it. A slow pan building up to 0.05 is not a cut.
    rng = np.random.default_rng(0)
    step = rng.uniform(0.002, 0.012, 200).astype(np.float32)
    step[0] = 0.0
    step[60:90] = np.linspace(0.01, 0.05, 30)
    step[140] = 0.19
    skip = step.copy()
    skip[139:141] = 0.19  # d(t-1, t+1) spans the cut for frames 139 and 140
    assert detect_cuts(step, skip, S) == [140]


def test_candidates_are_plain_ints_and_prep_round_trips(tmp_path):
    scores = np.linspace(0.5, 1.0, 400)  # every stretch has a clear frame
    picked = pick(scores, 8)
    assert len(picked) == 8 and all(type(f) is int for f in picked)
    scene = Scene(actors={"A": RED, "B": BLUE}, frames=40)
    scene.path("A", [(0, 150, FLOOR, HEIGHT), (39, 160, FLOOR, HEIGHT)])
    scene.path("B", [(0, 490, FLOOR, HEIGHT), (39, 480, FLOOR, HEIGHT)])
    r = render(scene)
    data = prep_mod.compute(iter(r.frames), r.arrays, FPS, 360, S)
    data.candidates = [np.int64(c) for c in data.candidates] or [np.int64(3)]
    prep_mod.write(tmp_path, "k", {}, data)
    back = prep_mod.read(tmp_path, "k")
    assert back is not None and back.candidates == [int(c) for c in data.candidates]


def test_crossing_keeps_identities():
    scene = Scene(actors={"A": RED, "B": BLUE}, frames=90)
    scene.path("A", [(0, 150, FLOOR, HEIGHT), (20, 150, FLOOR, HEIGHT), (70, 490, FLOOR, HEIGHT), (89, 490, FLOOR, HEIGHT)])
    scene.path("B", [(0, 490, FLOOR - 4, HEIGHT), (20, 490, FLOOR - 4, HEIGHT), (70, 150, FLOOR - 4, HEIGHT), (89, 150, FLOOR - 4, HEIGHT)])
    scene.hide_detection("B", range(42, 49))  # B hidden behind A while crossing
    _, _, result, ev = run(scene, [(5, "A", "B")])
    assert ev.wrong == [0, 0] and ev.switches == 0
    assert (result.state[75:, :] == TRACKED).all()  # both re-verified after the crossing
    assert ev.uncertain == [0, 0]  # short occlusion stays "occluded", not "uncertain"
    assert (result.state[42:49, 1] != TRACKED).all()


def test_referee_between_fighters_is_never_assigned():
    scene = Scene(actors={"A": RED, "B": BLUE, "R": REF}, frames=90)
    scene.path("A", [(0, 200, FLOOR, HEIGHT), (89, 210, FLOOR, HEIGHT)])
    scene.path("B", [(0, 440, FLOOR, HEIGHT), (89, 430, FLOOR, HEIGHT)])
    scene.path("R", [(0, 600, FLOOR + 6, HEIGHT * 1.05), (10, 600, FLOOR + 6, HEIGHT * 1.05),
                     (80, 50, FLOOR + 6, HEIGHT * 1.05), (89, 50, FLOOR + 6, HEIGHT * 1.05)])
    r, _, result, ev = run(scene, [(5, "A", "B")])
    assert ev.wrong == [0, 0] and ev.switches == 0
    assert (result.state[85:, :] == TRACKED).all()


def test_short_clinch_with_merged_detection():
    scene = Scene(actors={"A": RED, "B": BLUE}, frames=100)
    scene.path("A", [(0, 180, FLOOR, HEIGHT), (30, 290, FLOOR, HEIGHT), (55, 290, FLOOR, HEIGHT), (85, 180, FLOOR, HEIGHT), (99, 180, FLOOR, HEIGHT)])
    scene.path("B", [(0, 460, FLOOR, HEIGHT), (30, 345, FLOOR, HEIGHT), (55, 345, FLOOR, HEIGHT), (85, 460, FLOOR, HEIGHT), (99, 460, FLOOR, HEIGHT)])
    scene.hide_detection("B", range(38, 50))  # detector sees one blob for 12 frames
    _, _, result, ev = run(scene, [(3, "A", "B")])
    assert ev.wrong == [0, 0] and ev.switches == 0
    assert (result.state[90:, :] == TRACKED).all()
    assert ev.uncertain[1] == 0  # 0.4 s is a short overlap: identity kept


def test_camera_cut_uses_appearance_not_position():
    scene = Scene(actors={"A": RED, "B": BLUE}, frames=120, shots={0: (70, 90, 60), 60: (110, 70, 40)})
    scene.path("A", [(0, 180, FLOOR, HEIGHT), (59, 200, FLOOR, HEIGHT)])
    scene.path("B", [(0, 450, FLOOR, HEIGHT), (59, 440, FLOOR, HEIGHT)])
    # new camera angle: zoomed in, fighters on the other sides
    scene.place["A"][60:] = [None] * 60
    scene.place["B"][60:] = [None] * 60
    a2, b2 = Scene(actors={}, frames=120), Scene(actors={}, frames=120)
    a2.path("A", [(60, 470, FLOOR + 20, HEIGHT * 1.3), (119, 460, FLOOR + 20, HEIGHT * 1.3)])
    b2.path("B", [(60, 170, FLOOR + 20, HEIGHT * 1.3), (119, 180, FLOOR + 20, HEIGHT * 1.3)])
    scene.place["A"][60:] = a2.place["A"][60:]
    scene.place["B"][60:] = b2.place["B"][60:]
    _, prep, result, ev = run(scene, [(10, "A", "B")])
    assert prep.cuts == [60]
    assert ev.wrong == [0, 0] and ev.switches == 0
    assert (result.state[70:, :] == TRACKED).all()  # re-identified right after the cut


def test_look_alike_fighters_after_cut_are_uncertain_not_guessed():
    twin = Actor("B", shorts=RED.shorts, pattern=RED.pattern)
    scene = Scene(actors={"A": RED, "B": twin}, frames=100, shots={0: (70, 90, 60), 50: (110, 70, 40)})
    scene.path("A", [(0, 180, FLOOR, HEIGHT), (49, 190, FLOOR, HEIGHT)])
    scene.path("B", [(0, 450, FLOOR, HEIGHT), (49, 445, FLOOR, HEIGHT)])
    other = Scene(actors={}, frames=100)
    other.path("A", [(50, 470, FLOOR + 20, HEIGHT * 1.3), (99, 470, FLOOR + 20, HEIGHT * 1.3)])
    other.path("B", [(50, 170, FLOOR + 20, HEIGHT * 1.3), (99, 170, FLOOR + 20, HEIGHT * 1.3)])
    scene.place["A"][50:] = other.place["A"][50:]
    scene.place["B"][50:] = other.place["B"][50:]
    r, _, result, ev = run(scene, [(10, "A", "B")])
    assert ev.wrong == [0, 0]
    assert (result.state[60:, :] == UNCERTAIN).all()
    assert (result.state[:45, :] == TRACKED).all()  # same shot: motion keeps them apart
    # ...and a second selection after the cut fixes it
    result2 = run(scene, [(10, "A", "B"), (70, "A", "B")])[2]
    ev2 = evaluate(r, result2.det, result2.state)
    assert ev2.wrong == [0, 0] and (result2.state[55:, :] == TRACKED).all()


def test_lone_look_alike_after_cut_waits_for_a_one_fighter_selection():
    # Seen on a real broadcast clip: after a cut to a close-up of one fighter the
    # appearance model found him only slightly more like the other fighter and gave him
    # the wrong identity. With one person on screen there is no joint A/B check, so he
    # stays uncertain; a selection there that marks the other fighter as "not in the
    # picture" fixes the shot.
    twin = Actor("B", shorts=RED.shorts, pattern=RED.pattern, torso=(110, 140, 190))
    scene = Scene(actors={"A": RED, "B": twin}, frames=100, shots={0: (70, 90, 60), 50: (110, 70, 40)})
    scene.path("A", [(0, 180, FLOOR, HEIGHT), (49, 190, FLOOR, HEIGHT)])
    scene.path("B", [(0, 450, FLOOR, HEIGHT), (49, 445, FLOOR, HEIGHT)])
    close = Scene(actors={}, frames=100)
    close.path("B", [(50, 320, 355, 330), (99, 330, 355, 330)])
    scene.place["A"][50:] = [None] * 50
    scene.place["B"][50:] = close.place["B"][50:]
    r, _, result, ev = run(scene, [(10, "A", "B")])
    assert ev.wrong == [0, 0]
    assert (result.state[50:, :] == UNCERTAIN).all()
    result2 = run(scene, [(10, "A", "B"), (70, None, "B")])[2]
    ev2 = evaluate(r, result2.det, result2.state)
    assert ev2.wrong == [0, 0]
    assert (result2.state[52:, 1] == TRACKED).all()
    assert (result2.state[50:, 0] == UNCERTAIN).all() and (result2.det[50:, 0] == -1).all()


def test_merge_prefers_the_pass_that_crossed_fewer_cuts():
    def out(dets):
        o = identity._empty(len(dets))
        for t, d in enumerate(dets):
            if d >= 0:
                o.state[t, :], o.det[t, 0], o.det[t, 1], o.conf[t, :] = TRACKED, d, d + 100, 1.0
        return o

    # anchors at 0 and 9; shots: 0 0 0 0 0 | 1 1 1 1 1
    shots = np.array([0] * 5 + [1] * 5)
    fwd = out([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
    bwd = out([0, 1, 2, 30, 4, 5, 6, 70, 8, 9])
    state, det, _, reason, _, conflicts = identity._merge(fwd, bwd, [0, 9], shots)
    assert det[3, 0] == 3  # same shot as the first anchor: the forward pass wins
    assert det[7, 0] == 70  # same shot as the second anchor: the backward pass wins
    assert conflicts == 0
    # equal number of cuts crossed (anchor shots 0 and 2, frame in shot 1): undecided
    shots = np.array([0, 0, 0, 1, 1, 1, 1, 2, 2, 2])
    state, det, _, reason, _, conflicts = identity._merge(fwd, bwd, [0, 9], shots)
    assert state[3, 0] == UNCERTAIN and det[3, 0] == -1 and conflicts == 2  # one per fighter
    # Both passes agree on a frame, but one of them only holds the identity as unconfirmed
    # (placed from an overlapping box): the other one's result counts. Held by both: stays held.
    fwd, bwd = out(list(range(10))), out(list(range(10)))
    for o, frames in ((fwd, (4, 5, 6)), (bwd, (6, 7))):
        for t in frames:
            o.state[t, 0], o.conf[t, 0], o.held[t, 0] = identity.OCCLUDED, 0.6, True
    state, det, conf, _, held, _ = identity._merge(fwd, bwd, [0, 9], np.zeros(10, int))
    assert held[:, 0].tolist() == [t == 6 for t in range(10)] and not held[:, 1].any()
    assert (state[[4, 5, 7], 0] == TRACKED).all() and np.allclose(conf[[4, 5, 7], 0], 1.0)
    assert state[6, 0] == identity.OCCLUDED and np.isclose(conf[6, 0], 0.6) and (det[:, 0] == np.arange(10)).all()
    assert reason[3, 0] == REASONS.index(UncertainReason.anchor_conflict)


def test_close_up_correction_does_not_disturb_the_other_shot():
    # Seen on a real broadcast clip: a correction on a close-up (where B looked like A)
    # added B's close-up look to B's references everywhere, and the backward pass from
    # it argued with the first selection in the earlier shot -> "anchor conflicts".
    # References are shot-local, and the pass that did not cross a cut wins.
    twin = Actor("B", shorts=RED.shorts, pattern=RED.pattern, torso=(110, 140, 190))
    scene = Scene(actors={"A": RED, "B": BLUE}, frames=100, shots={0: (70, 90, 60), 50: (110, 70, 40)})
    scene.actors["B2"] = twin  # the same fighter B, looking like A in the close-up
    scene.path("A", [(0, 180, FLOOR, HEIGHT), (20, 300, FLOOR, HEIGHT), (35, 200, FLOOR, HEIGHT), (49, 190, FLOOR, HEIGHT)])
    scene.path("B", [(0, 450, FLOOR, HEIGHT), (20, 340, FLOOR - 4, HEIGHT), (35, 440, FLOOR, HEIGHT), (49, 445, FLOOR, HEIGHT)])
    close = Scene(actors={}, frames=100)
    close.path("B2", [(50, 320, 355, 330), (99, 330, 355, 330)])
    scene.place["A"][50:] = [None] * 50
    scene.place["B"][50:] = [None] * 50
    scene.place["B2"] = close.place["B2"]
    r, _, alone, _ = run(scene, [(5, "A", "B")])
    _, _, both, _ = run(scene, [(5, "A", "B"), (70, None, "B2")])
    truth = {"A": "A", "B": "B"}
    ev = evaluate(r, both.det[:50], both.state[:50], fighters=tuple(truth))
    assert ev.wrong == [0, 0] and ev.switches == 0
    assert (both.reason[:50] != REASONS.index(UncertainReason.anchor_conflict)).all()
    # whatever the first selection alone verified in the earlier shot stays as it was
    kept = alone.state[:50] == TRACKED
    assert (both.state[:50][kept] == TRACKED).all() and (both.det[:50][kept] == alone.det[:50][kept]).all()
    assert (both.state[52:, 1] == TRACKED).all() and (both.state[50:, 0] == UNCERTAIN).all()


def test_after_cut_identity_is_not_taken_from_an_overlapping_box():
    # Seen on a real broadcast clip: after a cut, one box over two overlapping people
    # (fighter + referee) looked like a fighter for a frame and started a wrong chain.
    # Without position information, identity needs a clean, non-overlapping view.
    scene = Scene(actors={"A": RED, "B": BLUE, "R": REF}, frames=100, shots={0: (70, 90, 60), 40: (110, 70, 40)})
    scene.path("A", [(0, 180, FLOOR, HEIGHT), (39, 185, FLOOR, HEIGHT)])
    scene.path("B", [(0, 450, FLOOR, HEIGHT), (39, 445, FLOOR, HEIGHT)])
    shot2 = Scene(actors={}, frames=100)
    shot2.path("A", [(40, 300, FLOOR, HEIGHT), (69, 300, FLOOR, HEIGHT), (90, 150, FLOOR, HEIGHT), (99, 150, FLOOR, HEIGHT)])
    shot2.path("R", [(40, 330, FLOOR + 6, HEIGHT), (99, 330, FLOOR + 6, HEIGHT)])
    scene.place["A"][40:] = shot2.place["A"][40:]
    scene.place["B"][40:] = [None] * 60
    scene.place["R"] = shot2.place["R"]
    _, prep, result, ev = run(scene, [(5, "A", "B")])
    assert prep.cuts == [40]
    assert ev.wrong == [0, 0]
    assert (result.state[40:66, 0] == UNCERTAIN).all()  # not claimed from the mixed box
    assert (result.state[92:, 0] == TRACKED).all()  # clean view later: found by appearance


def test_selection_in_the_middle_processes_earlier_part_backwards():
    scene = Scene(actors={"A": RED, "B": BLUE}, frames=90)
    scene.path("A", [(0, 150, FLOOR, HEIGHT), (20, 150, FLOOR, HEIGHT), (70, 490, FLOOR, HEIGHT), (89, 490, FLOOR, HEIGHT)])
    scene.path("B", [(0, 490, FLOOR - 4, HEIGHT), (20, 490, FLOOR - 4, HEIGHT), (70, 150, FLOOR - 4, HEIGHT), (89, 150, FLOOR - 4, HEIGHT)])
    _, _, result, ev = run(scene, [(80, "A", "B")])
    assert ev.wrong == [0, 0] and ev.switches == 0
    assert (result.state[:15, :] == TRACKED).all()


def test_long_overlap_turns_uncertain():
    scene = Scene(actors={"A": RED, "B": BLUE}, frames=150)
    scene.path("A", [(0, 200, FLOOR, HEIGHT), (20, 300, FLOOR, HEIGHT), (100, 300, FLOOR, HEIGHT), (120, 200, FLOOR, HEIGHT), (149, 200, FLOOR, HEIGHT)])
    scene.path("B", [(0, 440, FLOOR, HEIGHT), (20, 330, FLOOR, HEIGHT), (100, 330, FLOOR, HEIGHT), (120, 440, FLOOR, HEIGHT), (149, 440, FLOOR, HEIGHT)])
    scene.hide_detection("B", range(25, 95))  # ~2.3 s as a single blob
    _, _, result, ev = run(scene, [(3, "A", "B")])
    assert ev.wrong == [0, 0] and ev.switches == 0
    assert ev.uncertain[1] >= 25  # "Takip belirsiz" once the overlap lasts longer than ~1 s
    assert (result.state[130:, :] == TRACKED).all()  # re-found by appearance afterwards
    assert result.fighters[1].reacquisitions >= 1
    assert any(seg.fighter_id == "fighter_b" for seg in result.uncertain_segments)


def test_crossing_with_both_visible_never_swaps():
    scene = Scene(actors={"A": RED, "B": BLUE}, frames=90)
    scene.path("A", [(0, 150, FLOOR, HEIGHT), (15, 150, FLOOR, HEIGHT), (75, 490, FLOOR, HEIGHT), (89, 490, FLOOR, HEIGHT)])
    scene.path("B", [(0, 490, FLOOR - 2, HEIGHT), (15, 490, FLOOR - 2, HEIGHT), (75, 150, FLOOR - 2, HEIGHT), (89, 150, FLOOR - 2, HEIGHT)])
    _, _, result, ev = run(scene, [(5, "A", "B")])
    assert ev.wrong == [0, 0] and ev.switches == 0
    assert (result.state[80:, :] == TRACKED).all()


def test_referee_covering_a_fighter_does_not_take_his_identity():
    scene = Scene(actors={"A": RED, "B": BLUE, "R": REF}, frames=90)
    scene.path("A", [(0, 220, FLOOR - 10, HEIGHT), (89, 225, FLOOR - 10, HEIGHT)])
    scene.path("B", [(0, 470, FLOOR - 10, HEIGHT), (89, 465, FLOOR - 10, HEIGHT)])
    scene.path("R", [(0, 20, FLOOR + 10, HEIGHT * 1.1), (25, 20, FLOOR + 10, HEIGHT * 1.1),
                     (40, 222, FLOOR + 10, HEIGHT * 1.1), (60, 222, FLOOR + 10, HEIGHT * 1.1),
                     (75, 20, FLOOR + 10, HEIGHT * 1.1), (89, 20, FLOOR + 10, HEIGHT * 1.1)])
    scene.hide_detection("A", range(42, 58))  # completely hidden behind the referee
    r, _, result, ev = run(scene, [(5, "A", "B")])
    assert ev.wrong == [0, 0] and ev.switches == 0
    referee = {d for d, who in enumerate(r.truth) if who == "R"}
    assert not set(result.det[:, 0].tolist()) & referee
    assert (result.state[80:, :] == TRACKED).all()


DARK = Actor("B", shorts=(70, 35, 35), pattern="checker")  # dark navy shorts with a pattern
REF_DARK = Actor("R", shorts=(40, 40, 40), torso=(25, 25, 25))  # black trousers and shirt


def test_referee_next_to_a_downed_fighter_does_not_inherit_him():
    # Seen on a real broadcast clip: the fighter went down, the referee knelt over him and,
    # when the fighter's own box dropped out, the referee's track (dark trousers ~ dark
    # shorts) was taken for him. The referee was in view together with both fighters
    # before, so he is a known third person and must stay one.
    scene = Scene(actors={"A": RED, "B": DARK, "R": REF_DARK}, frames=100)
    scene.path("A", [(0, 160, FLOOR, HEIGHT), (99, 170, FLOOR, HEIGHT)])
    scene.path("B", [(0, 420, FLOOR, HEIGHT), (99, 420, FLOOR, HEIGHT)])
    scene.path("R", [(0, 620, FLOOR + 4, HEIGHT), (25, 560, FLOOR + 4, HEIGHT), (40, 470, FLOOR + 4, HEIGHT),
                     (75, 470, FLOOR + 4, HEIGHT), (90, 610, FLOOR + 4, HEIGHT), (99, 610, FLOOR + 4, HEIGHT)])
    scene.hide_detection("B", range(45, 75))  # down, hidden behind the referee
    r, _, result, ev = run(scene, [(5, "A", "B")])
    referee = {d for d, who in enumerate(r.truth) if who == "R"}
    assert not set(result.det[:, 1].tolist()) & referee
    assert ev.wrong == [0, 0] and ev.switches == 0
    assert (result.state[92:, 1] == TRACKED).all()  # found again once clearly visible


def test_small_spectator_after_a_cut_never_gets_the_missing_fighter():
    # Seen on a real broadcast clip: after a cut to a close-up of one fighter, a spectator
    # behind the cage was taken for the other fighter (who was not in the picture).
    spectator = Actor("C", shorts=(160, 60, 20))  # same colours as B
    scene = Scene(actors={"A": RED, "B": BLUE, "C": spectator}, frames=90,
                  shots={0: (70, 90, 60), 40: (40, 40, 120)})
    scene.path("A", [(0, 180, FLOOR, HEIGHT), (39, 185, FLOOR, HEIGHT)])
    scene.path("B", [(0, 450, FLOOR, HEIGHT), (39, 445, FLOOR, HEIGHT)])
    close = Scene(actors={}, frames=90)
    close.path("A", [(40, 300, 355, 330), (89, 310, 355, 330)])
    close.path("C", [(40, 560, 110, 70), (89, 560, 110, 70)])
    scene.place["A"][40:] = close.place["A"][40:]
    scene.place["B"][40:] = [None] * 50
    scene.place["C"] = close.place["C"]
    _, _, result, ev = run(scene, [(5, "A", "B")])
    assert ev.wrong == [0, 0]
    assert (result.det[40:, 1] == -1).all() and (result.state[45:, 1] == UNCERTAIN).all()
    assert (result.state[45:, 0] == TRACKED).all()


def test_after_cut_only_one_fighter_visible():
    scene = Scene(actors={"A": RED, "B": BLUE}, frames=100, shots={0: (70, 90, 60), 50: (110, 70, 40)})
    scene.path("A", [(0, 180, FLOOR, HEIGHT), (49, 190, FLOOR, HEIGHT)])
    scene.path("B", [(0, 450, FLOOR, HEIGHT), (49, 445, FLOOR, HEIGHT)])
    later = Scene(actors={}, frames=100)
    later.path("B", [(50, 320, FLOOR + 20, HEIGHT * 1.4), (99, 330, FLOOR + 20, HEIGHT * 1.4)])
    scene.place["A"][50:] = [None] * 50
    scene.place["B"][50:] = later.place["B"][50:]
    _, _, result, ev = run(scene, [(10, "A", "B")])
    assert ev.wrong == [0, 0]
    assert (result.state[60:, 0] == UNCERTAIN).all()  # A is not in the picture
    assert (result.state[60:, 1] == TRACKED).all()  # B found by appearance alone


def test_one_detection_never_has_two_fighters():
    scene = Scene(actors={"A": RED, "B": BLUE}, frames=100)
    scene.path("A", [(0, 180, FLOOR, HEIGHT), (30, 290, FLOOR, HEIGHT), (55, 290, FLOOR, HEIGHT), (85, 180, FLOOR, HEIGHT), (99, 180, FLOOR, HEIGHT)])
    scene.path("B", [(0, 460, FLOOR, HEIGHT), (30, 345, FLOOR, HEIGHT), (55, 345, FLOOR, HEIGHT), (85, 460, FLOOR, HEIGHT), (99, 460, FLOOR, HEIGHT)])
    scene.hide_detection("B", range(30, 60))
    _, _, result, _ = run(scene, [(3, "A", "B")])
    both = (result.det[:, 0] >= 0) & (result.det[:, 0] == result.det[:, 1])
    assert not both.any()
    assert set(np.unique(result.state)) <= {TRACKED, OCCLUDED, UNCERTAIN}


def test_anchor_validation():
    with pytest.raises(ValueError):
        FighterAnchor(frame_index=1, red_detection_id=0, blue_detection_id=0)
    FighterAnchor(frame_index=1, red_detection_id=0)  # blue not in the picture on this frame
    with pytest.raises(ValueError):
        FighterAnchor(frame_index=1)
    with pytest.raises(ValueError, match="blue corner"):
        FighterSelection(anchors=[FighterAnchor(frame_index=1, red_detection_id=0)])
    FighterSelection(anchors=[FighterAnchor(frame_index=1, red_detection_id=0, blue_detection_id=1),
                              FighterAnchor(frame_index=9, blue_detection_id=0)])
