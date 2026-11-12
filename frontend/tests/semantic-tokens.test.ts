// Components use only semantic tokens, and the stylesheets hold in both themes:
// - every var(--x) is a token of tokens.css / overlay-tokens.css or a local property
//   the stylesheets declare themselves (--tone, --side…);
// - every rule that sets both a text colour and a background from tokens passes AA
//   in the light and the dark theme;
// - the video stage (and what is drawn on it) uses only colours that are the same in
//   both themes.
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { DARK_BLOCK, RGBA, THEMES, TOKENS, tokenContrast } from "./support/tokens.ts";

const SRC = fileURLToPath(new URL("../src/", import.meta.url));
const TOKEN_FILES = new Set(["styles/tokens.css", "styles/overlay-tokens.css"]);

function files(dir: string, ext: RegExp): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) return files(full, ext);
    return ext.test(e.name) ? [full] : [];
  });
}

const rel = (file: string) => path.relative(SRC, file).split(path.sep).join("/");
const stripComments = (text: string) => text.replace(/\/\*[\s\S]*?\*\//g, (c) => c.replace(/[^\n]/g, " "));
const SOURCES = files(SRC, /\.(css|ts|tsx)$/).filter((f) => !TOKEN_FILES.has(rel(f)))
  .map((f) => ({ rel: rel(f), text: readFileSync(f, "utf8") }));
const STYLES = SOURCES.filter((s) => s.rel.endsWith(".css")).map((s) => ({ ...s, code: stripComments(s.text) }));

/** Rules of a stylesheet: selector and declarations (nested @media blocks give their inner rules). */
function rules(code: string): { selector: string; body: string }[] {
  return [...code.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((m) => ({
    selector: m[1]!.replace(/@media[^{]*$/, "").trim(),
    body: m[2]!,
  }));
}

test("every var() names a token or a property the stylesheets declare", () => {
  const global = TOKENS.light;
  const local = new Set(STYLES.flatMap((s) => [...s.code.matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1]!)));
  const unknown = SOURCES.flatMap((s) => [...s.text.matchAll(/var\((--[\w-]+)/g)]
    .filter((m) => !global.has(m[1]!) && !local.has(m[1]!))
    .map((m) => `${s.rel}: ${m[1]}`));
  assert.deepEqual(unknown, []);
});

test("canvas code reads only tokens that exist", () => {
  const names = SOURCES.flatMap((s) => [...s.text.matchAll(/cssToken\("(--[\w-]+)"\)|"(--scene-[\w-]+)"/g)]
    .map((m) => ({ file: s.rel, name: (m[1] ?? m[2])! })));
  assert.ok(names.length > 5, "the search finds the canvas tokens");
  const missing = names.filter((n) => !TOKENS.light.has(n.name)).map((n) => `${n.file}: ${n.name}`);
  assert.deepEqual(missing, []);
});

const colourOf = (body: string, prop: RegExp) => {
  const m = new RegExp(`(?:^|;)\\s*(?:${prop.source})\\s*:\\s*var\\((--[\\w-]+)\\)\\s*(?:;|$)`).exec(body);
  return m?.[1];
};

test("text and background set by the same rule pass AA in both themes", () => {
  const checked: string[] = [];
  const failing: string[] = [];
  for (const sheet of STYLES) {
    for (const { selector, body } of rules(sheet.code)) {
      const fg = colourOf(body, /color/);
      const bg = colourOf(body, /background(?:-color)?/);
      if (!fg || !bg || !TOKENS.light.has(fg) || !TOKENS.light.has(bg)) continue; // local tones: TEXT_PAIRS in tokens.test.ts
      if (RGBA.test(TOKENS.light.get(bg)!)) continue; // translucent backgrounds over the picture
      checked.push(`${selector} (${fg} on ${bg})`);
      for (const theme of THEMES) {
        const ratio = tokenContrast(theme, fg, bg);
        if (ratio < 4.5) failing.push(`${sheet.rel} ${selector}: ${fg} on ${bg} ${ratio.toFixed(2)}:1 (${theme})`);
      }
    }
  }
  assert.ok(checked.length >= 20, `the search finds the rules (${checked.length})`);
  assert.deepEqual(failing, []);
});

test("the video stage and what is drawn over it look the same in both themes", () => {
  // --ink-edge is the hairline around the stage on the dark page, outside the picture
  const themed = new Set([...DARK_BLOCK.keys()].filter((name) => name !== "--ink-edge"));
  // classes of the stage and the overlays on it
  const onStage = /(^|[\s,>+~(])\.(stage|majorwarn|idbadge|pick|strikes|pose-svg)(?![\w])(?:__[\w-]+|--[\w-]+)*/;
  const found = STYLES.flatMap((s) => rules(s.code)
    .filter((r) => onStage.test(r.selector))
    .flatMap((r) => [...r.body.matchAll(/var\((--[\w-]+)/g)]
      .filter((m) => themed.has(m[1]!))
      .map((m) => `${s.rel} ${r.selector}: ${m[1]}`)));
  assert.deepEqual(found, []);
  // canvas drawing of the demo scene and the video overlay
  const canvas = SOURCES.filter((s) => /^(player|demo)\//.test(s.rel)).flatMap((s) =>
    [...s.text.matchAll(/cssToken\("(--[\w-]+)"\)|"(--[\w-]+)"/g)]
      .map((m) => (m[1] ?? m[2])!)
      .filter((name) => themed.has(name))
      .map((name) => `${s.rel}: ${name}`));
  assert.deepEqual(canvas, []);
});
