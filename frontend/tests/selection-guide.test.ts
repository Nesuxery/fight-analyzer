// The numbered guide of the selection screen is derived from the picks alone.
import assert from "node:assert/strict";
import { test } from "node:test";
import { selectionGuide } from "../src/features/selection/guide.ts";

const states = (red: string | null, blue: string | null, ready: boolean) =>
  selectionGuide({ red, blue }, ready).map((s) => `${s.id}:${s.state}`);

test("nothing picked: the red corner is the step to do", () => {
  assert.deepEqual(states(null, null, false), ["red:active", "blue:upcoming", "confirm:upcoming"]);
});

test("red picked: blue is next, confirming is not possible yet", () => {
  assert.deepEqual(states("p1", null, false), ["red:done", "blue:active", "confirm:upcoming"]);
});

test("both picked: the last step is active and never done", () => {
  assert.deepEqual(states("p1", "p2", true), ["red:done", "blue:done", "confirm:active"]);
});

test("red removed again while blue stays: step 1 is active, step 2 is still done", () => {
  assert.deepEqual(states(null, "p2", false), ["red:active", "blue:done", "confirm:upcoming"]);
});

test("both marked as not in view: corners are set but the selection cannot be confirmed", () => {
  assert.deepEqual(states("not_in_view", "not_in_view", false), ["red:done", "blue:done", "confirm:upcoming"]);
});
