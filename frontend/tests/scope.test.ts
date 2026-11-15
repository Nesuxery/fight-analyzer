// Time scope of the side panels (v2 Bölüm 2.5): one function turns a scope into frames, and the
// statistics of a round count only what happened in it.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { exclusionIntervals, frameMs, measuredStats, motionSums } from "../src/model/measured.ts";
import { roundNear, scopeRange, validScope } from "../src/model/scope.ts";

const ROUNDS = [{ index: 1, start_frame: 315, end_frame: 9314 }, { index: 2, start_frame: 9525, end_frame: 15914 }];
const FRAMES = 16215;

test("a scope becomes a frame range", () => {
  assert.deepEqual(scopeRange({ kind: "bout" }, ROUNDS, 5000, FRAMES), { start: 0, end: FRAMES - 1 });
  assert.deepEqual(scopeRange({ kind: "playhead" }, ROUNDS, 5000, FRAMES), { start: 0, end: 5000 });
  assert.deepEqual(scopeRange({ kind: "playhead" }, ROUNDS, 99999, FRAMES), { start: 0, end: FRAMES - 1 });
  assert.deepEqual(scopeRange({ kind: "round", index: 2 }, ROUNDS, 100, FRAMES), { start: 9525, end: 15914 });
  // a round that reaches past the video is clipped; one that does not exist has no range
  assert.deepEqual(scopeRange({ kind: "round", index: 2 }, ROUNDS, 100, 12000), { start: 9525, end: 11999 });
  assert.equal(scopeRange({ kind: "round", index: 3 }, ROUNDS, 100, FRAMES), null);
  assert.equal(scopeRange({ kind: "bout" }, ROUNDS, 0, 0), null);
});

test("the round scope starts with the round at the playhead", () => {
  assert.equal(roundNear(ROUNDS, 100), 1); // before the first round: the first
  assert.equal(roundNear(ROUNDS, 5000), 1);
  assert.equal(roundNear(ROUNDS, 9400), 1); // in the break: the round that just ended
  assert.equal(roundNear(ROUNDS, 12000), 2);
  assert.equal(roundNear([], 12000), null);
  assert.deepEqual(validScope({ kind: "round", index: 2 }, ROUNDS), { kind: "round", index: 2 });
  assert.deepEqual(validScope({ kind: "round", index: 2 }, ROUNDS.slice(0, 1)), { kind: "playhead" });
  assert.deepEqual(validScope({ kind: "bout" }, []), { kind: "bout" });
});

const fixture = JSON.parse(readFileSync(new URL("../../shared/fixtures/frame-metrics.json", import.meta.url), "utf8"));

test("statistics of a range are the difference of the statistics up to its ends", () => {
  const { fps, events, motion, momentum } = fixture;
  const segments = momentum.exclusions;
  const iv = exclusionIntervals(segments, fps);
  const sums = motionSums(motion, iv);
  const upTo = (frame: number, side: "red" | "blue") =>
    measuredStats(side, frame, frameMs(frame, fps), events, sums, segments, iv);
  for (const [from, to] of [[200, 650], [1, 899], [450, 451]] as const) {
    for (const side of ["red", "blue"] as const) {
      const part = measuredStats(side, to, frameMs(to, fps), events, sums, segments, iv, from, frameMs(from, fps));
      const before = upTo(from - 1, side);
      const whole = upTo(to, side);
      // counts add up exactly: nothing is lost or counted twice at the edge of the range
      assert.equal(part.strikeAttempts, whole.strikeAttempts! - before.strikeAttempts!, `${from}-${to} ${side}`);
      assert.equal(part.kicks, whole.kicks! - before.kicks!, `${from}-${to} ${side}`);
      assert.equal(part.significant, whole.significant! - before.significant!, `${from}-${to} ${side}`);
      assert.ok(part.controlS! <= whole.controlS!);
    }
  }
  // from the start of the video it is the old statistic (the one the MP4 export mirrors)
  assert.deepEqual(measuredStats("red", 650, frameMs(650, fps), events, sums, segments, iv, 0, 0), upTo(650, "red"));
});
