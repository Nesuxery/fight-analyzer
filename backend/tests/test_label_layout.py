"""Name labels over the video never overlap and stay inside the picture. The browser
overlay follows the same rule; both suites check the same shared fixture."""

import json
from pathlib import Path

import pytest

from fight_analyzer.export.label_layout import LabelBounds, LabelRequest, place_labels

FIXTURE = Path(__file__).resolve().parents[2] / "shared" / "fixtures" / "label-layout.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_label_layout_matches_the_shared_fixture(case):
    left, top, right, bottom = case["bounds"]
    labels = [LabelRequest(*q) for q in case["labels"]]
    got = place_labels(labels, LabelBounds(left, top, right, bottom), case["gap"])
    assert got == pytest.approx([tuple(p) for p in case["expected"]], abs=1e-9)
    gap = case["gap"]
    for (x, y), lab in zip(got, labels):
        if lab.w <= right - left:
            assert left - 1e-9 <= x and x + lab.w <= right + 1e-9
        assert top - 1e-9 <= y and y + lab.h <= bottom + 1e-9
    for i in range(len(got)):
        for j in range(i + 1, len(got)):
            (ax, ay), (bx, by), la, lb = got[i], got[j], labels[i], labels[j]
            assert (ax + la.w + gap <= bx + 1e-6 or bx + lb.w + gap <= ax + 1e-6
                    or ay + la.h + gap <= by + 1e-6 or by + lb.h + gap <= ay + 1e-6), f"labels {i} and {j} overlap"
