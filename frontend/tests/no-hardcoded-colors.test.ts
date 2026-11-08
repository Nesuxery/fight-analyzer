// Acceptance check of Bölüm 1, kept as a test: no component or stylesheet has a
// colour of its own. Colours live in tokens.css (interface) and in
// shared/overlay-style.json (video layer, shared with the MP4 export), whose
// generated copies are the only other files allowed to contain colour codes.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const SRC = fileURLToPath(new URL("../src/", import.meta.url));
const TOKEN_FILES = new Set([
  "styles/tokens.css", // the token file
  "styles/overlay-tokens.css", // generated from shared/overlay-style.json
  "contracts/overlayStyle.ts", // generated from shared/overlay-style.json
  "contracts/generated.ts", // generated contract types
]);

function files(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) return files(full);
    return /\.(css|ts|tsx)$/.test(e.name) ? [full] : [];
  });
}

const HEX = /(?<![\w&#$])#(?:[0-9a-f]{8}|[0-9a-f]{6}|[0-9a-f]{3,4})(?![\w-])/gi;
// a colour written with numbers; rgba(${…}) built from a token (styles/tokens.ts) is not one
const FUNCTIONAL = /(?<![\w-])(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\(\s*[\d.]/gi;
const NAMED = /(?<![\w-])(white|black|red|blue|green|yellow|orange|purple|gr[ae]y|cyan|magenta|pink|brown|navy|teal|silver|gold|maroon|lime|olive|aqua|fuchsia)(?![\w-])/i;
// declarations that take a colour (custom properties included)
const COLOR_DECL = /(?:^|[;{\s])((?:--[\w-]+|color|background[\w-]*|border[\w-]*|outline[\w-]*|fill|stroke|box-shadow|text-shadow|caret-color|accent-color|text-decoration[\w-]*|column-rule[\w-]*))\s*:\s*([^;{}]+)/g;

function problems(rel: string, text: string): string[] {
  const out: string[] = [];
  const lineOf = (index: number) => text.slice(0, index).split("\n").length;
  for (const m of text.matchAll(HEX)) out.push(`${rel}:${lineOf(m.index)} ${m[0]}`);
  for (const m of text.matchAll(FUNCTIONAL)) out.push(`${rel}:${lineOf(m.index)} ${m[0]}…)`);
  if (rel.endsWith(".css")) {
    const code = text.replace(/\/\*[\s\S]*?\*\//g, (c) => c.replace(/[^\n]/g, " "));
    for (const m of code.matchAll(COLOR_DECL)) {
      const named = NAMED.exec(m[2]!.replace(/"[^"]*"|'[^']*'/g, ""));
      if (named) out.push(`${rel}:${lineOf(m.index)} ${m[1]}: ${named[1]}`);
    }
  }
  return out;
}

test("no colour code outside the token files", () => {
  const found = files(SRC).flatMap((file) => {
    const rel = path.relative(SRC, file).split(path.sep).join("/");
    return TOKEN_FILES.has(rel) ? [] : problems(rel, readFileSync(file, "utf8"));
  });
  assert.deepEqual(found, [], `hard-coded colours:\n${found.join("\n")}`);
});

test("the search itself finds colour codes", () => {
  assert.equal(problems("a.css", ".x { color: #fff; background: rgba(0, 0, 0, 0.5); }").length, 2);
  assert.equal(problems("a.css", ".x { border: 1px solid white; }").length, 1);
  assert.equal(problems("a.tsx", 'ctx.fillStyle = "#1a1203";').length, 1);
  assert.equal(problems("a.ts", 'ctx.strokeStyle = "rgba(0, 0, 0, 0.8)";').length, 1);
  assert.deepEqual(problems("a.ts", "return `rgba(${r}, ${g}, ${b}, ${alpha})`;"), []);
  // not colours: routes, element ids, grid areas, white-space, the corner token names
  assert.deepEqual(problems("a.tsx", 'href="#/" url(#hatch) fill={`url(#${id})`}'), []);
  assert.deepEqual(problems("a.css", '.a { grid-area: red; white-space: nowrap; color: var(--red); }'), []);
});
