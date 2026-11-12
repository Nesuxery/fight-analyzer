// The page is lang="tr", so CSS capitals follow Turkish rules (i becomes İ). That is
// right for Turkish interface words and wrong for everything else: file extensions,
// abbreviations, English terms and fighter names are shown as written.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const SRC = fileURLToPath(new URL("../src/", import.meta.url));

function files(dir: string, ext: RegExp): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) return files(full, ext);
    return ext.test(e.name) ? [full] : [];
  });
}

const rel = (file: string) => path.relative(SRC, file).split(path.sep).join("/");

test("the code upper-cases nothing with a locale", () => {
  const found = files(SRC, /\.(ts|tsx)$/).flatMap((file) => {
    const text = readFileSync(file, "utf8");
    return [...text.matchAll(/\.toLocale(?:Upper|Lower)Case\(/g)]
      .map((m) => `${rel(file)}:${text.slice(0, m.index).split("\n").length}`);
  });
  assert.deepEqual(found, [], `locale-dependent case conversion:\n${found.join("\n")}`);
  // why: "avi" in Turkish capitals is "AVİ"; toUpperCase keeps "AVI"
  assert.equal("avi".toLocaleUpperCase("tr-TR"), "AVİ");
  assert.equal("avi".toUpperCase(), "AVI");
});

// Selectors that put text in capitals. Each holds fixed Turkish interface words only;
// a new one must not hold names, English terms or abbreviations with a lower-case i.
const UPPERCASE_ALLOWED = [
  ".how__num", // "1. adım"
  ".label", // small Turkish labels ("Toplam ilerleme")
  ".majorwarn__type", // "Olası knockdown" (the fighter name after it is a separate element)
  ".mpanel__corner", // "Kırmızı" / "Mavi"
  ".stat dt", // metric names
  ".statpair__label", // metric names
  ".stats__corner", // "Kırmızı" / "Mavi"
  ".sys__title", // "Sistem durumu"
  ".tag", // short Turkish tags; .tag--plain turns capitals off for scorecard terms
];

test("capitals are only used on Turkish interface labels", () => {
  const found = files(SRC, /\.css$/).flatMap((file) => {
    const css = readFileSync(file, "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
    return [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
      .filter((m) => /text-transform\s*:\s*uppercase/.test(m[2]!))
      .flatMap((m) => m[1]!.split(",").map((s) => s.trim().replace(/\s+/g, " ")));
  });
  assert.deepEqual([...new Set(found)].sort(), [...UPPERCASE_ALLOWED].sort());
});
