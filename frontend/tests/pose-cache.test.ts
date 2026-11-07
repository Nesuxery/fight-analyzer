// Long videos: the browser keeps a bounded number of pose chunks.
import assert from "node:assert/strict";
import { test } from "node:test";
import { MAX_CHUNKS, evict } from "../src/hooks/chunkCache.ts";

test("least recently used pose chunks are dropped, the needed ones kept", () => {
  const map = new Map<number, string>();
  for (let i = 0; i < MAX_CHUNKS + 25; i++) map.set(i, "frames");
  evict(map, [0, 1]); // chunks 0 and 1 are on screen even though they are the oldest
  assert.equal(map.size, MAX_CHUNKS);
  assert.ok(map.has(0) && map.has(1) && map.has(MAX_CHUNKS + 24));
  assert.ok(!map.has(2) && !map.has(26));
});
