// Name labels over the video never overlap and stay inside the picture. The MP4
// export follows the same rule; both suites check the same shared fixture.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { placeLabels } from "../src/player/labelLayout.ts";

type Quad = [number, number, number, number];
const fixture = JSON.parse(readFileSync(new URL("../../shared/fixtures/label-layout.json", import.meta.url), "utf8")) as {
  cases: { name: string; bounds: Quad; gap: number; labels: Quad[]; expected: [number, number][] }[];
};

const near = (a: number, b: number) => Math.abs(a - b) < 1e-9;

for (const c of fixture.cases) {
  test(`label layout: ${c.name}`, () => {
    const [left, top, right, bottom] = c.bounds;
    const labels = c.labels.map(([ax, ay, w, h]) => ({ ax, ay, w, h }));
    const got = placeLabels(labels, { left, top, right, bottom }, c.gap);
    assert.equal(got.length, c.expected.length);
    got.forEach((p, i) => {
      const [x, y] = c.expected[i]!;
      assert.ok(near(p.x, x) && near(p.y, y), `label ${i}: got (${p.x}, ${p.y}), want (${x}, ${y})`);
    });
    // the rule itself: inside the bounds (when it fits) and apart by at least the gap
    got.forEach((p, i) => {
      const l = labels[i]!;
      if (l.w <= right - left) assert.ok(p.x >= left - 1e-9 && p.x + l.w <= right + 1e-9, `label ${i} leaves the bounds`);
      assert.ok(p.y >= top - 1e-9 && p.y + l.h <= bottom + 1e-9, `label ${i} leaves the bounds`);
    });
    for (let i = 0; i < got.length; i++) {
      for (let j = i + 1; j < got.length; j++) {
        const [a, b, la, lb] = [got[i]!, got[j]!, labels[i]!, labels[j]!];
        const apart = a.x + la.w + c.gap <= b.x + 1e-6 || b.x + lb.w + c.gap <= a.x + 1e-6 ||
          a.y + la.h + c.gap <= b.y + 1e-6 || b.y + lb.h + c.gap <= a.y + 1e-6;
        assert.ok(apart, `labels ${i} and ${j} overlap`);
      }
    }
  });
}
