// The "Dışlanan bölümler" list: manual and automatic parts together, events left out, one-click switch.
import assert from "node:assert/strict";
import { test } from "node:test";
import type { AutoExclusion, ExcludedSegment } from "../src/contracts/generated.ts";
import { excludedEventCounts, exclusionRows, toggledDismissed } from "../src/features/result/exclusionView.ts";

const manual = (start: number, end: number): ExcludedSegment => ({
  start_frame: start, end_frame: end, reason: "replay", note: null, source: "manual", auto_id: null, confidence: null,
  signals: [],
});
const auto = (start: number, end: number, reason: AutoExclusion["reason"], dismissed = false): AutoExclusion => ({
  start_frame: start, end_frame: end, reason, note: null, source: "auto", auto_id: `${reason}-${start}-${end}`,
  confidence: 0.99, signals: ["outside_rounds"], dismissed,
});

const AUTO = [auto(0, 314, "intro"), auto(9315, 9524, "break"), auto(15915, 16214, "post_fight", true)];
const MANUAL = [manual(3000, 3600), manual(200, 400)];
// events at: intro, the overlap of intro and a manual part, live time, a manual part, the dismissed end
const EVENTS = [100, 300, 1000, 3100, 16000];

test("manual and automatic parts are listed together by time with their event counts", () => {
  const rows = exclusionRows(MANUAL, AUTO, EVENTS);
  assert.deepEqual(rows.map((r) => [r.kind, r.segment.start_frame, r.events, r.dismissed]), [
    ["auto", 0, 2, false], ["manual", 200, 1, false], ["manual", 3000, 1, false], ["auto", 9315, 0, false],
    ["auto", 15915, 1, true],
  ]);
  // a manual row keeps its place in the user's list, so removing it removes the right one
  assert.deepEqual(rows.filter((r) => r.kind === "manual").map((r) => r.index), [1, 0]);
});

test("events left out are counted once, and not at all in a part that was turned off", () => {
  const rows = exclusionRows(MANUAL, AUTO, EVENTS);
  assert.deepEqual(excludedEventCounts(rows, EVENTS), { total: 3, auto: 2, manual: 1 });
  assert.deepEqual(excludedEventCounts(exclusionRows([], [], EVENTS), EVENTS), { total: 0, auto: 0, manual: 0 });
});

test("one click turns an automatic part off or on and leaves the others as they are", () => {
  assert.deepEqual(toggledDismissed(AUTO, "break-9315-9524"), ["break-9315-9524", "post_fight-15915-16214"]);
  assert.deepEqual(toggledDismissed(AUTO, "post_fight-15915-16214"), []);
});
