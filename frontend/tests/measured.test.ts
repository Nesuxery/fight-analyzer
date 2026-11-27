// Statistics and momentum shown at a video time are precomputed values for that time:
// watching a part again, seeking or changing the playback rate must not change them.
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  eventEffect, eventMoment, frameMs, measuredStats, motionSums, redShare, sampleAt, toTimelineEvents, totals,
} from "../src/model/measured.ts";

const HZ = 10;
const FPS = 30;
const N = 100; // 10 s
const motion = {
  schema_version: "1.3.0", job_id: "0".repeat(32), data_origin: "measured", sample_hz: HZ,
  sample_ms: Array.from({ length: N }, (_, i) => i * 100),
  camera_known: Array(N).fill(true), distance: Array(N).fill(2),
  fighters: [
    { fighter_id: "fighter_a", valid: Array(N).fill(true), activity: Array(N).fill(0.5),
      hand_speed: Array(N).fill(1), foot_speed: Array(N).fill(1), approach_speed: Array(N).fill(0),
      movement: Array.from({ length: N }, (_, i) => (i < 50 ? "advancing" : "neutral")),
      posture: Array(N).fill("standing") },
    { fighter_id: "fighter_b", valid: Array(N).fill(true), activity: Array(N).fill(0.2),
      hand_speed: Array(N).fill(1), foot_speed: Array(N).fill(1), approach_speed: Array(N).fill(0),
      movement: Array.from({ length: N }, (_, i) => (i < 20 ? "retreating" : "neutral")),
      posture: Array(N).fill("standing") },
  ],
};

const ev = (id: string, type: string, actor: string, at: number) => ({
  event_id: id, type, actor, target: actor === "fighter_a" ? "fighter_b" : "fighter_a",
  start_frame: Math.round(at * FPS / 1000) - 1, end_frame: Math.round(at * FPS / 1000) + 3,
  start_ms: at - 50, end_ms: at + 100, peak_frame: Math.round(at * FPS / 1000), peak_ms: at, limb: null,
  possible_contact: false, location: null, measures: {}, confidence: 0.8, data_origin: "measured", note: null,
});
const events = [
  ev("p1", "punch", "fighter_a", 1000), ev("p2", "punch", "fighter_a", 2500), ev("k1", "kick", "fighter_b", 4000),
  ev("p3", "punch", "fighter_a", 6000), ev("kd", "knockdown", "fighter_a", 7000),
];
const params = {
  half_life_s: 20, prior: 4, strike_attempt: 1, kick_attempt: 1.3, contact_bonus: 0.3, advance_per_s: 0.2,
  control_per_s: 0.5, knockdown: 4, takedown: 2.5, min_major_confidence: 0.5,
};
const point = (id: string, fighter: string, source: string, at: number, pts: number, event: string | null) => ({
  contribution_id: id, fighter_id: fighter, source, event_id: event, start_ms: at, end_ms: at, quantity: 1, points: pts,
});
const contribs = [
  { contribution_id: "adv", fighter_id: "fighter_a", source: "advance", event_id: null, start_ms: 0, end_ms: 5000,
    quantity: 5, points: 1 },
  point("s1", "fighter_a", "strike_attempt", 1000, 1, "p1"),
  point("s2", "fighter_a", "strike_attempt", 2500, 1, "p2"),
  point("k1", "fighter_b", "kick_attempt", 4000, 1.3, "k1"),
  point("s3", "fighter_a", "strike_attempt", 6000, 1, "p3"),
  point("kd", "fighter_a", "knockdown", 7000, 4, "kd"),
];

test("statistics depend only on the presented frame, not on how playback got there", () => {
  const sums = motionSums(motion as never);
  const at = (side: "red" | "blue", s: number) => {
    const frame = Math.floor(s * FPS + 1e-3);
    return measuredStats(side, frame, frameMs(frame, FPS), events as never, sums);
  };
  const at5 = at("red", 5);
  // watch all of it at 2x, seek back and watch the start again at 0.25x, then seek around
  for (let t = 0; t <= 10; t += 2 / 30) at("red", t);
  for (let t = 0; t <= 5; t += 0.25 / 30) at("red", t);
  for (const t of [9.3, 0.2, 7.7, 3.1]) at("red", t);
  assert.deepEqual(at("red", 5), at5);
  assert.equal(at5.strikeAttempts, 2);
  assert.equal(at("red", 0.5).strikeAttempts, 0); // back before the first one
  assert.equal(at("red", 10).strikeAttempts, 3);
  assert.equal(at("red", 10).significant, 1);
  assert.equal(at("blue", 10).kicks, 1);
  assert.equal(at("blue", 3.9).kicks, 0);
  assert.equal(at("blue", 4).kicks, 1); // counts from its peak frame on
  assert.equal(at5.activity, 50);
  assert.equal(at("red", 10).pressure, 50); // advancing in 50 of 100 samples
  assert.equal(at("red", 1).pressure, null); // too little measured time yet
});

test("momentum shares always sum to 100 and are a function of the time only", () => {
  for (let t = 0; t <= 12000; t += 37) {
    const red = redShare(totals(contribs as never, t, params as never), params.prior);
    assert.ok(red > 0 && red < 100);
    assert.equal(Math.round(red) + Math.round(100 - red), 100);
  }
  assert.equal(redShare(totals(contribs as never, -1, params as never), params.prior), 50); // nothing yet
  const at7 = totals(contribs as never, 7000, params as never);
  for (const t of [12000, 100, 3333, 7000]) totals(contribs as never, t, params as never);
  assert.deepEqual(totals(contribs as never, 7000, params as never), at7);
});

test("the effect of one event is the share with it minus the share without it", () => {
  const t = 9000;
  const effect = eventEffect(contribs as never, "kd", t, params as never)!;
  const m = totals(contribs as never, t, params as never);
  const kdNow = 4 * Math.pow(0.5, 2 / 20);
  assert.ok(Math.abs(effect.now - kdNow) < 1e-9);
  const without = redShare({ red: m.red - kdNow, blue: m.blue }, 4);
  assert.ok(Math.abs(effect.redDelta - (redShare(m, 4) - without)) < 1e-9);
  assert.equal(eventEffect(contribs as never, "nothing", t, params as never), null);
});

test("a hidden-opponent estimate is listed with its own tag and never counted as control", () => {
  // red on top carried over a stretch in which blue was not measured (gizli rakip çıkarımı)
  const hidden = { ...ev("h1", "hidden_grappling", "fighter_a", 3000), peak_frame: null, peak_ms: null,
                   start_frame: 60, end_frame: 240, start_ms: 2000, end_ms: 8000, confidence: 0.3,
                   measures: { seconds: 6 }, evidence: ["opponent_hidden", "close_contact", "top_position"] };
  const control = { ...ev("gc", "ground_control", "fighter_a", 1000), peak_frame: null, peak_ms: null,
                    start_frame: 30, end_frame: 59, start_ms: 1000, end_ms: 1990, measures: { seconds: 1 } };
  const sums = motionSums(motion as never);
  const stats = measuredStats("red", 299, frameMs(299, FPS), [...events, hidden, control] as never, sums);
  const without = measuredStats("red", 299, frameMs(299, FPS), [...events, control] as never, sums);
  assert.deepEqual(stats, without);
  assert.equal(stats.controlS, 1); // the measured control only
  const [view] = toTimelineEvents([hidden] as never);
  assert.equal(view!.hidden, true);
  assert.ok(!view!.inferred);
  assert.equal(view!.startS, 2); // a stretch: from its start
  assert.equal(eventMoment(hidden as never), 8000); // timed by its end, like control
});

test("sample lookup covers every time", () => {
  assert.equal(sampleAt(motion.sample_ms, 0), 0);
  assert.equal(sampleAt(motion.sample_ms, 99.9), 0);
  assert.equal(sampleAt(motion.sample_ms, 100), 1);
  assert.equal(sampleAt(motion.sample_ms, 1e9), N - 1);
});
