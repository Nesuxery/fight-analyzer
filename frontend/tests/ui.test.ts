// Pure helpers behind the shared ui/ components.
import assert from "node:assert/strict";
import { test } from "node:test";
import { cx } from "../src/ui/cx.ts";
import { statPairShares } from "../src/ui/statPairShares.ts";

test("StatPair: the larger value fills its side, the other is in proportion", () => {
  assert.deepEqual(statPairShares(12, 6), { red: 1, blue: 0.5 });
  assert.deepEqual(statPairShares(0, 4), { red: 0, blue: 1 });
});

test("StatPair: a fixed scale is used as is and clamps out-of-range values", () => {
  assert.deepEqual(statPairShares(40, 25, 100), { red: 0.4, blue: 0.25 });
  assert.deepEqual(statPairShares(130, -5, 100), { red: 1, blue: 0 });
});

test("StatPair: missing values and an empty scale draw no bar", () => {
  assert.deepEqual(statPairShares(null, null), { red: 0, blue: 0 });
  assert.deepEqual(statPairShares(0, 0), { red: 0, blue: 0 });
  assert.deepEqual(statPairShares(null, 3), { red: 0, blue: 1 });
  assert.deepEqual(statPairShares(Number.NaN, 2), { red: 0, blue: 1 });
});

test("cx joins only the truthy class names", () => {
  assert.equal(cx("btn", false, "btn--sm", null, undefined, ""), "btn btn--sm");
});
