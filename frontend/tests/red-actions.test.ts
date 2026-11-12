// Red buttons are the main actions of the Upload screen only (Dosya seç, Analizi
// başlat, Demo analizini başlat). Elsewhere red means the red corner, so no other
// screen may use the red "brand" button.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const SRC = fileURLToPath(new URL("../src/", import.meta.url));

function files(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) return files(full);
    return /\.tsx?$/.test(e.name) ? [full] : [];
  });
}

test("red buttons appear on the Upload screen only", () => {
  const uses = files(SRC).flatMap((file) => {
    const rel = path.relative(SRC, file).split(path.sep).join("/");
    const text = readFileSync(file, "utf8");
    return [...text.matchAll(/variant="brand"|btn--brand/g)].map(() => rel);
  });
  assert.ok(uses.length >= 3, `expected the three upload actions, found ${uses.length}`);
  assert.deepEqual(uses.filter((rel) => !rel.startsWith("features/upload/")), []);
});
