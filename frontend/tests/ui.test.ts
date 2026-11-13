// Pure helpers behind the shared ui/ components.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { cx } from "../src/ui/cx.ts";
import { placeBubble } from "../src/ui/placeBubble.ts";
import { statPairShares } from "../src/ui/statPairShares.ts";
import { stepState } from "../src/ui/stepState.ts";

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

test("Stepper: steps before the open one are done, the rest are upcoming", () => {
  assert.deepEqual([0, 1, 2, 3].map((i) => stepState(i, 2)), ["done", "done", "active", "upcoming"]);
  assert.deepEqual([0, 1, 2, 3].map((i) => stepState(i, 0)), ["active", "upcoming", "upcoming", "upcoming"]);
  // no screen open (page not found): nothing is done or active
  assert.deepEqual([0, 1].map((i) => stepState(i, -1)), ["upcoming", "upcoming"]);
});

// ---------- HelpTip bubble ----------
const VIEW = { width: 1024, height: 768 };
const OPTS = { gap: 4, inset: 8, margin: 8 } as const;
const BUBBLE = { width: 260, height: 60 };

test("HelpTip: the bubble sits on its preferred side and edge when there is room", () => {
  const anchor = { left: 500, top: 300, width: 20, height: 20 };
  assert.deepEqual(placeBubble(anchor, BUBBLE, VIEW, { ...OPTS, side: "top", align: "start" }),
                   { left: 492, top: 236, side: "top" });
  assert.deepEqual(placeBubble(anchor, BUBBLE, VIEW, { ...OPTS, side: "bottom", align: "end" }),
                   { left: 268, top: 324, side: "bottom" });
  assert.equal(placeBubble(anchor, BUBBLE, VIEW, { ...OPTS, side: "top", align: "center" }).left, 380);
});

test("HelpTip: near the right edge the bubble stays inside the viewport", () => {
  // "Toplam ilerleme" at 1024 px: align start, close to the right edge
  const anchor = { left: 900, top: 300, width: 20, height: 20 };
  const p = placeBubble(anchor, BUBBLE, VIEW, { ...OPTS, side: "top", align: "start" });
  assert.equal(p.left + BUBBLE.width, VIEW.width - OPTS.margin);
  const left = placeBubble({ ...anchor, left: 2 }, BUBBLE, VIEW, { ...OPTS, side: "top", align: "end" });
  assert.equal(left.left, OPTS.margin);
});

test("HelpTip: the bubble flips when its side has no room, and a too-wide bubble keeps its start edge", () => {
  const top = { left: 500, top: 10, width: 20, height: 20 };
  assert.equal(placeBubble(top, BUBBLE, VIEW, { ...OPTS, side: "top", align: "center" }).side, "bottom");
  const bottom = { left: 500, top: 740, width: 20, height: 20 };
  assert.equal(placeBubble(bottom, BUBBLE, VIEW, { ...OPTS, side: "bottom", align: "center" }).side, "top");
  const phone = { width: 200, height: 600 };
  assert.equal(placeBubble(top, BUBBLE, phone, { ...OPTS, side: "top", align: "start" }).left, OPTS.margin);
});

test("HelpTip: the closed bubble is out of the layout and the open one is fixed", () => {
  const css = readFileSync(new URL("../src/ui/ui.css", import.meta.url), "utf8");
  const rule = (selector: string) => {
    const at = css.indexOf(`${selector} {`);
    assert.notEqual(at, -1, selector);
    return css.slice(at, css.indexOf("}", at));
  };
  assert.match(rule(".helptip__bubble"), /position: fixed;/);
  assert.match(rule(".helptip__bubble"), /display: none;/);
  assert.match(rule(".helptip__bubble.is-open"), /display: block;/);
  // no other rule may give the bubble a place in the page again
  assert.doesNotMatch(css.replace(rule(".helptip__bubble"), ""), /\.helptip__bubble[^{]*\{[^}]*position:/);
});
