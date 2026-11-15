// The data quality shown for a scope must be the same in the browser and from the API.
// shared/fixtures/track-quality.json holds a synthetic tracking timeline and the summaries
// the backend computes for a list of frame ranges (backend/fight_analyzer/tracking/quality.py);
// model/quality.ts must produce the same from the timeline.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import type { TrackingTimeline } from "../src/contracts/generated.ts";
import { qualityIn, qualityIndex } from "../src/model/quality.ts";

const fixture = JSON.parse(readFileSync(new URL("../../shared/fixtures/track-quality.json", import.meta.url), "utf8"));
const timeline: TrackingTimeline = {
  schema_version: "1.0.0", job_id: "f".repeat(32), frame_count: fixture.frame_count, fps: fixture.fps, cuts: [],
  fighters: fixture.fighters,
};

test("browser data quality equals the backend's for every checked range", () => {
  const index = qualityIndex(timeline, fixture.exclusions);
  assert.ok(index);
  assert.ok(fixture.cases.length >= 14 && fixture.exclusions.length > 0);
  // the fixture holds exact ties (e.g. 29/160 = 0.18125 -> 0.1813)
  assert.ok(fixture.cases.some((c: { fighters: { frames: number }[] }) => c.fighters[0]!.frames === 32));
  let withCauses = 0;
  for (const c of fixture.cases) {
    for (const [k, side] of (["red", "blue"] as const).entries()) {
      const want = c.fighters[k];
      const got = qualityIn(index, side, { start: c.start, end: c.end });
      const where = `frames ${c.start}-${c.end} ${side}`;
      assert.equal(got.frames, want.frames, where);
      assert.equal(got.identityChanges, want.identity_changes, where);
      // the very same numbers, exact ties included (both round halves up)
      assert.equal(got.measurableShare, want.measurable_share, where);
      assert.equal(got.occludedShare, want.occluded_share, where);
      assert.ok(Math.abs(got.uncertainMs - want.uncertain_ms) < 0.11, where);
      assert.ok(Math.abs(got.longestUncertainMs - want.longest_uncertain_ms) < 0.11, where);
      // and the same order: largest first, equal shares in the order of the causes
      assert.deepEqual(got.causes, want.causes, where);
      withCauses += want.causes.length;
    }
  }
  assert.ok(withCauses > 10);
});

test("a range without fight time has no shares, and an older analysis has no index", () => {
  const index = qualityIndex(timeline, fixture.exclusions)!;
  const inside = fixture.exclusions[1];
  const empty = qualityIn(index, "red", { start: inside.start_frame, end: inside.end_frame });
  assert.deepEqual([empty.frames, empty.measurableShare, empty.uncertainMs, empty.causes.length], [0, 0, 0, 0]);
  const old = { ...timeline, fighters: timeline.fighters.map((f) => ({ ...f, quality: null })) };
  assert.equal(qualityIndex(old, []), null);
});
