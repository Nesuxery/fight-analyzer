"""Golden file shared/fixtures/track-quality.json: a synthetic identity result in the
form the browser gets it (tracking timeline) and the data quality of both fighters for
a list of frame ranges.

The backend test checks that tracking/quality.py reproduces the file; the frontend
test (frontend/tests/quality.test.ts) checks that model/quality.ts computes the same
from the timeline. Together they guarantee that the API (whole bout, rounds) and the
browser (scope that follows the playhead) show the same numbers.

Regenerate after an intended change of the definition:
    python -m tests.support.quality_fixture
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from fight_analyzer.contracts import ExcludedSegment
from fight_analyzer.tracking import quality, results

FIXTURE = Path(__file__).resolve().parents[3] / "shared" / "fixtures" / "track-quality.json"
FPS = 30000 / 1001
FRAMES = 1200
EXCLUSIONS = [ExcludedSegment(start_frame=0, end_frame=89, reason="intro", source="auto"),
              ExcludedSegment(start_frame=600, end_frame=659, reason="replay"),
              ExcludedSegment(start_frame=1150, end_frame=1199, reason="post_fight", source="auto")]
# whole video, a "round", up to a playhead, a range inside an excluded part, single frames
RANGES = [(0, FRAMES - 1), (90, 599), (0, 433), (610, 650), (700, 700), (1100, 1199), (0, 0), (300, 1150)]


def arrays() -> dict[str, np.ndarray]:
    """State, quality mask and id changes of two fighters, in stretches of random length."""
    rng = np.random.default_rng(11)
    state = np.zeros((FRAMES, 2), np.int8)
    mask = np.zeros((FRAMES, 2), np.uint8)
    change = np.zeros((FRAMES, 2), bool)
    bits = [quality.BIT[c] for c in quality.CAUSES]
    for f in (0, 1):
        t = 0
        while t < FRAMES:
            length = int(rng.integers(3, 70))
            kind = rng.choice(["clean", "clean", "overlap", "uncertain", "poor", "gap"])
            part = slice(t, t + length)
            if kind == "overlap":
                state[part, f], mask[part, f] = 1, bits[2]
            elif kind == "uncertain":
                state[part, f] = 2
                mask[part, f] = quality.UNMEASURABLE | int(rng.choice(bits[:3]))
            elif kind == "poor":
                mask[part, f] = int(rng.choice([bits[1], bits[3], bits[1] | bits[3], bits[3] | quality.UNMEASURABLE]))
            elif kind == "gap":
                state[part, f], mask[part, f] = 1, quality.UNMEASURABLE | bits[0]
            if rng.random() < 0.5:
                change[t, f] = True
            t += length
    return {"state": state, "quality": mask, "change": change}


def build() -> dict:
    a = arrays()
    excluded = quality.excluded_mask(EXCLUSIONS, FRAMES)
    return {
        "description": "Data quality per frame range; see backend/tests/support/quality_fixture.py",
        "fps": FPS, "frame_count": FRAMES,
        "exclusions": [x.model_dump(mode="json") for x in EXCLUSIONS],
        "fighters": [f.model_dump(mode="json") for f in results.timeline(a)],
        "cases": [{"start": start, "end": end,
                   "fighters": [q.model_dump(mode="json")
                                for q in quality.summarize(a["state"], a["quality"], a["change"], start, end, FPS,
                                                           excluded)]}
                  for start, end in RANGES],
    }


if __name__ == "__main__":
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(build(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {FIXTURE}")
