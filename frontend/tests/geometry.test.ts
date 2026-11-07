// Overlay geometry: video pixels must land on the same screen pixels as the picture.
import assert from "node:assert/strict";
import { test } from "node:test";
import { backingSize, canvasTransform, containFit, frameAt, frameTime, toBox } from "../src/player/geometry.ts";

const close = (a: number, b: number) => assert.ok(Math.abs(a - b) < 1e-9, `${a} != ${b}`);

test("same aspect ratio: the picture fills the box", () => {
  assert.deepEqual(containFit(640, 360, 1280, 720), { scale: 0.5, offsetX: 0, offsetY: 0 });
});

test("fullscreen on a 16:10 screen: bars top and bottom, keypoints follow the picture", () => {
  const fit = containFit(1920, 1200, 1280, 720);
  assert.deepEqual(fit, { scale: 1.5, offsetX: 0, offsetY: 60 });
  assert.deepEqual(toBox(fit, 0, 0), { x: 0, y: 60 });
  assert.deepEqual(toBox(fit, 1280, 720), { x: 1920, y: 1140 });
  assert.deepEqual(toBox(fit, 640, 360), { x: 960, y: 600 }); // centre stays centre
});

test("narrow box: bars left and right", () => {
  const fit = containFit(500, 600, 1280, 720);
  close(fit.scale, 500 / 1280);
  close(fit.offsetX, 0);
  close(fit.offsetY, (600 - 720 * fit.scale) / 2);
});

test("pixel density changes the backing store, not where things are drawn", () => {
  const fit = containFit(801.5, 450.3, 1280, 720);
  for (const dpr of [1, 1.25, 1.5, 2, 3]) {
    const [a, , , d, e, f] = canvasTransform(fit, dpr);
    for (const [x, y] of [[0, 0], [640, 360], [1280, 720], [17.25, 701.5]]) {
      const box = toBox(fit, x!, y!);
      close((a * x! + e) / dpr, box.x); // device pixels / dpr = CSS pixels
      close((d * y! + f) / dpr, box.y);
    }
  }
  assert.deepEqual(backingSize(801.5, 450.3, 1.25), { width: 1002, height: 563 });
  assert.deepEqual(backingSize(0, 0, 2), { width: 1, height: 1 });
});

test("presented frame from media time, at common frame rates", () => {
  for (const fps of [25, 30000 / 1001, 30, 60]) {
    for (let i = 0; i < 400; i++) {
      assert.equal(frameAt(i / fps, fps, 1000), i); // requestVideoFrameCallback mediaTime (frame start)
      assert.equal(frameAt(frameTime(i, fps), fps, 1000), i); // after a seek to the middle of the frame
      assert.equal(frameAt((i + 0.97) / fps, fps, 1000), i); // fallback currentTime late in the frame
    }
  }
  assert.equal(frameAt(-1, 30, 10), 0);
  assert.equal(frameAt(100, 30, 10), 9);
});
