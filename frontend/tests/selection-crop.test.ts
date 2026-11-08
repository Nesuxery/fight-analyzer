// Candidate tiles on the selection screen show a square cut of the frame around each person.
import assert from "node:assert/strict";
import { test } from "node:test";
import { cropRect } from "../src/features/selection/crop.ts";

const FRAME = { width: 1920, height: 1080 };
const near = (actual: number, expected: number) =>
  assert.ok(Math.abs(actual - expected) < 1e-9, `${actual} != ${expected}`);

test("the square is centred on the person with some room around", () => {
  // 100 x 300 box: the taller side plus 8 % on both sides
  const r = cropRect({ x1: 900, y1: 400, x2: 1000, y2: 700 }, FRAME);
  near(r.size, 348);
  near(r.x + r.size / 2, 950);
  near(r.y + r.size / 2, 550);
});

test("near an edge the square moves inside the frame instead of shrinking", () => {
  const left = cropRect({ x1: 0, y1: 10, x2: 80, y2: 210 }, FRAME);
  near(left.x, 0);
  near(left.y, 0);
  near(left.size, 232);
  const right = cropRect({ x1: 1880, y1: 900, x2: 1920, y2: 1080 }, FRAME);
  near(right.x + right.size, FRAME.width);
  near(right.y + right.size, FRAME.height);
});

test("a person taller than the frame gets the full frame height", () => {
  const r = cropRect({ x1: 500, y1: -50, x2: 900, y2: 1100 }, FRAME);
  near(r.size, FRAME.height);
  near(r.y, 0);
  assert.ok(r.x >= 0 && r.x + r.size <= FRAME.width);
});

test("a degenerate box still gives a valid square inside the frame", () => {
  const r = cropRect({ x1: 10, y1: 10, x2: 10, y2: 10 }, FRAME);
  assert.ok(r.size > 0 && r.x >= 0 && r.y >= 0);
});
