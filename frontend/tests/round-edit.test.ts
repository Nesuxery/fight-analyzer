// Round edits on the timeline and the scorebug name suggestion (pure functions).
import assert from "node:assert/strict";
import { test } from "node:test";
import type { RoundSegment } from "../src/contracts/generated.ts";
import {
  addRound,
  applyNameSuggestion,
  editsOf,
  moveEdge,
  removeRound,
  revertToAuto,
  suggestionTargets,
} from "../src/features/match/roundEdit.ts";

const FPS = 30;
const FRAMES = 16215;
const seg = (index: number, start: number, end: number, source: RoundSegment["source"] = "ocr"): RoundSegment => ({
  index, start_frame: start, end_frame: end, video_start_s: start / FPS, video_end_s: (end + 1) / FPS,
  clock_start: 300, clock_end: 0, source, confidence: 0.99, partial: false,
});
const AUTO = [seg(1, 315, 9314), seg(2, 9525, 15914)];
const NONE = editsOf(null);

test("dragging an automatic edge makes that round a manual mark", () => {
  const e = moveEdge(NONE, AUTO, 2, "start", 9600, FPS, FRAMES);
  assert.deepEqual(e, { rounds: [{ number: 2, start_frame: 9600, end_frame: 15914 }], cleared_rounds: [] });
});

test("an edge never crosses the neighbouring round or the round's other edge", () => {
  assert.equal(moveEdge(NONE, AUTO, 2, "start", 9000, FPS, FRAMES).rounds[0]!.start_frame, 9315);
  assert.equal(moveEdge(NONE, AUTO, 1, "end", 9999, FPS, FRAMES).rounds[0]!.end_frame, 9524);
  assert.equal(moveEdge(NONE, AUTO, 1, "end", 0, FPS, FRAMES).rounds[0]!.end_frame, 315 + 10 * FPS);
});

test("removing an automatic round keeps it removed; reverting brings it back", () => {
  const removed = removeRound(NONE, 2, AUTO);
  assert.deepEqual(removed, { rounds: [], cleared_rounds: [2] });
  assert.deepEqual(revertToAuto(removed, 2), NONE);
  const manual = moveEdge(NONE, AUTO, 1, "end", 9000, FPS, FRAMES);
  assert.deepEqual(revertToAuto(manual, 1), NONE);
});

test("a new round takes the lowest free number and stops before the next round", () => {
  const e = addRound(NONE, [AUTO[1]!], 300, FPS, FRAMES, 300, 3);
  assert.deepEqual(e?.rounds, [{ number: 1, start_frame: 300, end_frame: 300 + 300 * FPS - 1 }]);
  const tight = addRound(NONE, [AUTO[1]!], 9000, FPS, FRAMES, 300, 3);
  assert.equal(tight?.rounds[0]!.end_frame, 9524);
  assert.equal(addRound(NONE, AUTO, 16000, FPS, FRAMES, 300, 3), null); // R3 would end in under 10 s
  assert.equal(addRound(NONE, AUTO, 5000, FPS, FRAMES, 300, 3), null); // inside R1
  assert.equal(addRound(NONE, [AUTO[0]!, AUTO[1]!, seg(3, 15950, 16100)], 16150, FPS, FRAMES, 300, 3), null);
});

test("the name suggestion fills only placeholder names, never a typed one", () => {
  const placeholders = { red: "Dövüşçü 1", blue: "Dövüşçü 2" };
  const suggestion = { left: "VOLKANOVSKI", right: "TOPURIA", red: "Volkanovski", blue: "Topuria", confidence: 0.4 };
  assert.deepEqual(applyNameSuggestion(placeholders, placeholders, suggestion), { red: "Volkanovski", blue: "Topuria" });
  const typed = { red: "Alexander Volkanovski", blue: "Dövüşçü 2" };
  assert.deepEqual(applyNameSuggestion(typed, placeholders, suggestion), { red: "Alexander Volkanovski", blue: "Topuria" });
  assert.deepEqual(suggestionTargets(typed, placeholders, suggestion), ["blue"]);
  assert.deepEqual(suggestionTargets({ red: "A", blue: "B" }, placeholders, suggestion), []);
  assert.deepEqual(suggestionTargets(placeholders, placeholders, null), []);
});
