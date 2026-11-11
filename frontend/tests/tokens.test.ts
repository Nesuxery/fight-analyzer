// Design tokens (Bölüm 1, black-white-red identity): the specified values are
// in tokens.css, and every text/background pair the interface uses passes WCAG AA.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const css = readFileSync(new URL("../src/styles/tokens.css", import.meta.url), "utf8");
const overlay = JSON.parse(readFileSync(new URL("../../shared/overlay-style.json", import.meta.url), "utf8")) as {
  colors: Record<string, string>;
};

/** Custom properties of tokens.css, var() references resolved. */
function tokens(): Map<string, string> {
  const raw = new Map<string, string>();
  for (const m of css.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)) raw.set(m[1]!, m[2]!.trim());
  const resolve = (value: string, depth = 0): string => {
    const ref = /^var\((--[a-z0-9-]+)\)$/.exec(value);
    if (!ref || depth > 5) return value;
    const next = raw.get(ref[1]!);
    assert.ok(next, `${ref[1]} is not defined`);
    return resolve(next, depth + 1);
  };
  return new Map([...raw].map(([k, v]) => [k, resolve(v)]));
}

const T = tokens();
const hex = (name: string): string => {
  const v = T.get(name);
  assert.ok(v, `${name} missing from tokens.css`);
  assert.match(v, /^#[0-9a-f]{6}$/i, `${name} should be a #rrggbb colour, got ${v}`);
  return v.toLowerCase();
};

function luminance(color: string): number {
  const n = Number.parseInt(color.slice(1), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const s = v / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

/** A translucent token (rgba) as the opaque colour it shows over `bg`. */
function over(name: string, bg: string): string {
  const v = T.get(name);
  assert.ok(v, `${name} missing from tokens.css`);
  const m = /^rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)$/.exec(v);
  assert.ok(m, `${name} should be an rgba() colour, got ${v}`);
  const alpha = Number(m[4]);
  const base = Number.parseInt(bg.slice(1), 16);
  const mix = (fg: number, shift: number) => Math.round(fg * alpha + ((base >> shift) & 255) * (1 - alpha));
  const [r, g, b] = [mix(Number(m[1]), 16), mix(Number(m[2]), 8), mix(Number(m[3]), 0)];
  return `#${[r, g, b].map((c) => c.toString(16).padStart(2, "0")).join("")}`;
}

test("contrast helper matches known WCAG values", () => {
  assert.equal(Math.round(contrast("#000000", "#ffffff") * 10) / 10, 21);
  assert.equal(contrast("#777777", "#777777"), 1);
  assert.ok(Math.abs(contrast("#767676", "#ffffff") - 4.54) < 0.01);
});

test("colour tokens have the specified values", () => {
  const spec: Record<string, string> = {
    "--ink": "#0e0e10",
    "--ink-2": "#1c1c20",
    "--on-ink": "#ffffff",
    "--bg": "#f2f2f0",
    "--surface": "#ffffff",
    "--surface-muted": "#f1f1ee",
    // a step darker than before so white cards stand out from --bg
    "--border": "#deded9",
    // darker than #8f8f8a, which fell to 2.9:1 on the new --bg
    "--border-strong": "#858580",
    // the same black as --ink
    "--text-1": "#0e0e10",
    "--text-2": "#52524c",
    "--text-3": "#6e6e68",
    "--red": "#d0142c",
    "--red-soft": "#fdecee",
    "--red-strong": "#b01025",
    "--blue": "#2457c5",
    "--blue-soft": "#edf2fc",
    "--success": "#1f7a4d",
    "--warning": "#9a6100",
    "--stage": "#0b0b0c",
  };
  for (const [name, value] of Object.entries(spec)) assert.equal(hex(name), value, name);
});

test("one black and one red: text is ink, the accent is the red", () => {
  assert.equal(hex("--text-1"), hex("--ink"));
  assert.equal(hex("--accent"), hex("--red"), "--accent is brand red by default");
  assert.equal(T.get("--shadow-card"), "0 1px 2px rgba(0, 0, 0, 0.06)");
  const pattern = Number(T.get("--band-pattern-opacity"));
  assert.ok(pattern > 0 && pattern <= 0.06, `--band-pattern-opacity = ${T.get("--band-pattern-opacity")}`);
});

// [foreground, background]: every text colour on every background it is used on.
const TEXT_PAIRS: [string, string][] = [
  ...["--bg", "--surface", "--surface-muted"].flatMap((bg) =>
    ["--text-1", "--text-2", "--text-3"].map((fg) => [fg, bg] as [string, string])),
  ["--text-on-fill", "--text-1"], // primary button, play button
  ["--on-ink", "--ink"], ["--on-ink", "--ink-2"], // top bar, dark bands, the fighter card
  ["--text-on-fill", "--red"], // red corner badge, active step number, "Dosya seç"
  ["--text-on-fill", "--red-strong"], // its hover
  ["--text-on-fill", "--blue"], // blue corner badge
  ["--text-on-fill", "--warning"], // DEMO tag
  ["--text-on-fill", "--danger"],
  ["--red", "--surface"], ["--red", "--bg"], ["--red", "--red-soft"],
  ["--blue", "--surface"], ["--blue", "--bg"], ["--blue", "--blue-soft"],
  ["--success", "--surface"], ["--success", "--success-soft"],
  ["--warning", "--surface"], ["--warning", "--bg"], ["--warning", "--warning-soft"],
  ["--danger", "--surface"], ["--danger", "--danger-soft"],
  ["--text-1", "--warning-soft"], ["--text-1", "--danger-soft"],
  ["--stage-text", "--stage"], ["--stage-text-2", "--stage"],
];

test("text tokens pass WCAG AA for normal text (4.5:1) on their backgrounds", () => {
  for (const [fg, bg] of TEXT_PAIRS) {
    const ratio = contrast(hex(fg), hex(bg));
    assert.ok(ratio >= 4.5, `${fg} on ${bg}: ${ratio.toFixed(2)}:1`);
  }
});

test("secondary text on ink passes AA although it is translucent", () => {
  for (const bg of ["--ink", "--ink-2"]) {
    const ratio = contrast(over("--on-ink-2", hex(bg)), hex(bg));
    assert.ok(ratio >= 4.5, `--on-ink-2 on ${bg}: ${ratio.toFixed(2)}:1`);
  }
});

test("red on ink is a mark, not text: 3:1 for the logo, the active step and its line", () => {
  for (const bg of ["--ink", "--ink-2"]) {
    const ratio = contrast(hex("--red"), hex(bg));
    assert.ok(ratio >= 3, `--red against ${bg}: ${ratio.toFixed(2)}:1`);
    // the reason the rule exists: it does not reach the 4.5:1 of normal text
    assert.ok(ratio < 4.5, `--red on ${bg} now passes as text (${ratio.toFixed(2)}:1): update the rule in tokens.css`);
  }
});

test("inputs, focus rings and corner marks on the video reach 3:1 (non-text contrast)", () => {
  const pairs: [string, string][] = [
    ["--border-strong", "--surface"], ["--border-strong", "--bg"],
    ["--text-1", "--bg"], ["--text-1", "--surface"], ["--text-1", "--surface-muted"], // focus ring
    ["--stage-text", "--stage"], // focus ring on the stage
    ["--on-ink", "--ink"], ["--on-ink", "--ink-2"], // focus ring on ink
    ["--red", "--stage"], ["--blue", "--stage"], // selected candidate frames over the video
  ];
  for (const [fg, bg] of pairs) {
    const ratio = contrast(hex(fg), hex(bg));
    assert.ok(ratio >= 3, `${fg} against ${bg}: ${ratio.toFixed(2)}:1`);
  }
});

test("video overlay colours read on the dark stage and the warning banner text reads on its colour", () => {
  const stage = hex("--stage");
  for (const name of ["red", "blue", "other", "amber", "warning", "light"]) {
    const ratio = contrast(overlay.colors[name]!, stage);
    assert.ok(ratio >= 4.5, `overlay ${name} on the stage: ${ratio.toFixed(2)}:1`);
  }
  assert.ok(contrast(hex("--text-1"), overlay.colors.warning!) >= 4.5);
});

test("motion, radius and type tokens follow the spec", () => {
  assert.equal(T.get("--ease"), "cubic-bezier(0.2, 0.8, 0.2, 1)");
  for (const name of ["--motion-fast", "--motion", "--motion-slow"]) {
    const ms = Number.parseInt(T.get(name) ?? "", 10);
    assert.ok(ms >= 160 && ms <= 220, `${name} = ${T.get(name)}`);
  }
  assert.deepEqual(["--radius-control", "--radius-card", "--radius-stage", "--radius-pill"].map((n) => T.get(n)),
                   ["8px", "12px", "16px", "999px"]);
  assert.deepEqual(["--fs-12", "--fs-13", "--fs-14", "--fs-16", "--fs-20", "--fs-24", "--fs-32", "--fs-44"]
    .map((n) => T.get(n)), ["12px", "13px", "14px", "16px", "20px", "24px", "32px", "44px"]);
  assert.deepEqual(["--fw-regular", "--fw-medium", "--fw-semibold"].map((n) => T.get(n)), ["400", "500", "600"]);
  assert.equal(T.get("--shadow-float"), "0 8px 24px rgba(17, 17, 17, 0.08)");
  assert.equal(T.get("--page-max"), "1440px");
  assert.equal(T.get("--page-gutter"), "24px");
  assert.equal(T.get("--focus-width"), "2px");
  assert.equal(T.get("--focus-offset"), "2px");
});

test("the favicon is the brand mark in the one red", () => {
  const favicon = readFileSync(new URL("../public/octagon.svg", import.meta.url), "utf8");
  const colours = [...favicon.matchAll(/#[0-9a-f]{6}\b/gi)].map((m) => m[0].toLowerCase());
  assert.deepEqual(colours, [hex("--red")]);
});
