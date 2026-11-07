// The browser and the MP4/CSV export must show the same numbers on the same frame.
// shared/fixtures/frame-metrics.json holds synthetic results and the values the export
// computes (backend/fight_analyzer/export/frames.py); the browser functions must match.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import {
  eventFrame,
  exclusionIntervals,
  frameMs,
  isFrameExcluded,
  measuredSeconds,
  measuredStats,
  motionSums,
  redShare,
  sampleAt,
  shownShare,
  totals,
} from "../src/model/measured.ts";
import { effectsAt } from "../src/player/effects.ts";

const fixture = JSON.parse(readFileSync(new URL("../../shared/fixtures/frame-metrics.json", import.meta.url), "utf8"));

test("browser statistics and momentum equal the export's on every checked frame", () => {
  const { fps, events, motion, momentum } = fixture;
  const segments = momentum.exclusions;
  const iv = exclusionIntervals(segments, fps);
  const sums = motionSums(motion, iv);
  assert.ok(segments.length > 0 && fixture.frames.some((r: { excluded: boolean }) => r.excluded));
  assert.ok(fixture.frames.length > 100);
  for (const row of fixture.frames) {
    const tMs = frameMs(row.frame, fps);
    const red = redShare(totals(momentum.contributions, tMs, momentum.parameters, iv), momentum.parameters.prior);
    assert.ok(Math.abs(red - row.red_share) < 1e-9, `frame ${row.frame}: ${red} vs ${row.red_share}`);
    assert.equal(shownShare(red), row.red_shown, `frame ${row.frame}`);
    assert.equal(momentum.insufficient[sampleAt(momentum.sample_ms, tMs)], row.insufficient, `frame ${row.frame}`);
    assert.equal(isFrameExcluded(row.frame, segments), row.excluded, `frame ${row.frame}`);
    for (const side of ["red", "blue"] as const) {
      const { measuredS, ...stats } = row[side];
      assert.deepEqual(measuredStats(side, row.frame, tMs, events, sums, segments, iv), stats,
                       `frame ${row.frame} ${side}`);
      assert.equal(measuredSeconds(side, tMs, sums), measuredS, `frame ${row.frame} ${side}`);
    }
  }
});

test("event effects are visible over the same video times as in the export", () => {
  const { fps, events, momentum } = fixture;
  const excluded = new Set<string>(events.filter((e: never) => isFrameExcluded(eventFrame(e), momentum.exclusions))
    .map((e: { event_id: string }) => e.event_id));
  assert.ok(excluded.size > 0);
  let seen = 0;
  for (const row of fixture.frames) {
    const fx = effectsAt(events, frameMs(row.frame, fps) / 1000, excluded);
    const close = (a: number, b: number) => Math.abs(a - b) < 1e-9;
    const want = row.effects;
    assert.deepEqual(fx.flashes.map((x) => x.event.event_id), want.flashes.map((x: [string, number]) => x[0]));
    assert.ok(fx.flashes.every((x, i) => close(x.strength, want.flashes[i][1])), `frame ${row.frame}`);
    assert.deepEqual(fx.rings.map((x) => [x.event.event_id, x.labelled]),
                     want.rings.map((x: [string, number, boolean]) => [x[0], x[2]]));
    assert.ok(fx.rings.every((x, i) => close(x.strength, want.rings[i][1])), `frame ${row.frame}`);
    assert.deepEqual(fx.warnings.map((x) => x.event.event_id), want.warnings.map((x: [string, number]) => x[0]));
    assert.ok(fx.warnings.every((x, i) => close(x.strength, want.warnings[i][1])), `frame ${row.frame}`);
    seen += fx.flashes.length + fx.rings.length + fx.warnings.length;
  }
  assert.ok(seen > 50);
});
