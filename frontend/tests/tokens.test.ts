// Design tokens of both themes: the specified values are in tokens.css, every
// text/background pair the interface uses passes WCAG AA (4.5:1) and every mark
// (bars, lines, borders, focus rings) reaches 3:1, in the light and the dark theme.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { DARK_BLOCK, LIGHT_BLOCK, THEMES, TOKENS, TOKENS_CSS, blend, contrast, hex, tokenContrast } from "./support/tokens.ts";

const overlay = JSON.parse(readFileSync(new URL("../../shared/overlay-style.json", import.meta.url), "utf8")) as {
  colors: Record<string, string>;
};

test("contrast helper matches known WCAG values", () => {
  assert.equal(Math.round(contrast("#000000", "#ffffff") * 10) / 10, 21);
  assert.equal(contrast("#777777", "#777777"), 1);
  assert.ok(Math.abs(contrast("#767676", "#ffffff") - 4.54) < 0.01);
  assert.equal(blend("rgba(255, 255, 255, 0.5)", "#000000"), "#808080");
});

test("light theme: colour tokens keep the Bölüm 1 values", () => {
  const spec: Record<string, string> = {
    "--ink": "#0e0e10",
    "--ink-2": "#1c1c20",
    "--on-ink": "#ffffff",
    "--bg": "#f2f2f0",
    "--surface": "#ffffff",
    "--surface-muted": "#f1f1ee",
    "--surface-raised": "#ffffff",
    // a step darker than before so white cards stand out from --bg
    "--border": "#deded9",
    // darker than #8f8f8a, which fell to 2.9:1 on the new --bg
    "--border-strong": "#858580",
    // the same black as --ink
    "--text-1": "#0e0e10",
    "--text-2": "#52524c",
    "--text-3": "#6e6e68",
    "--red": "#d0142c",
    "--red-soft": "#fdeef0",
    "--red-strong": "#b01025",
    "--blue": "#2457c5",
    "--blue-soft": "#edf2fc",
    "--success": "#1f7a4d",
    "--warning": "#9a6100",
    "--stage": "#0b0b0c",
    // light theme: corner text and marks are the fills themselves; only the blue
    // of the dark momentum box is lighter (the fill is 2.6:1 on --ink-2)
    "--red-fg": "#d0142c",
    "--blue-fg": "#2457c5",
    "--red-on-ink": "#d0142c",
    "--blue-on-ink": "#5b8cff",
    "--primary": "#0e0e10",
    "--on-primary": "#ffffff",
  };
  for (const [name, value] of Object.entries(spec)) assert.equal(hex("light", name), value, name);
});

test("dark theme: page, cards and raised surfaces have the specified values", () => {
  const spec: Record<string, string> = {
    "--bg": "#0b0b0d",
    "--surface": "#151518",
    "--surface-raised": "#1e1e22",
    // hover and muted fills: different from the raised surface, or hover in menus disappears
    "--surface-muted": "#242428",
    // ink is a tone above the page; the edge token draws its hairline
    "--ink": "#141417",
    "--text-1": "#f4f4f2",
    "--on-ink": "#ffffff",
    "--red-fg": "#ff6b7a",
    "--blue-fg": "#7aa5ff",
    // white primary buttons with black text
    "--primary": "#f4f4f2",
    "--on-primary": "#0e0e10",
  };
  for (const [name, value] of Object.entries(spec)) assert.equal(hex("dark", name), value, name);
  assert.notEqual(TOKENS.dark.get("--ink-edge"), "transparent");
  for (const theme of THEMES) {
    for (const bg of ["--surface", "--surface-raised"]) {
      assert.ok(contrast(hex(theme, "--surface-muted"), hex(theme, bg)) >= 1.05, `hover on ${bg} is visible (${theme})`);
    }
  }
  assert.equal(TOKENS.light.get("--ink-edge"), "transparent");
});

test("one black and one red: text is ink, the accent is the red (light); fills keep their colour (both)", () => {
  assert.equal(hex("light", "--text-1"), hex("light", "--ink"));
  assert.equal(hex("light", "--accent"), hex("light", "--red"), "--accent is brand red by default");
  assert.equal(hex("dark", "--accent"), hex("dark", "--red-fg"), "--accent is the light red on dark");
  assert.equal(TOKENS.light.get("--shadow-card"), "0 1px 2px rgba(0, 0, 0, 0.06)");
  for (const theme of THEMES) {
    const pattern = Number(TOKENS[theme].get("--band-pattern-opacity"));
    assert.ok(pattern > 0 && pattern <= 0.06, `--band-pattern-opacity = ${pattern}`);
    // white text on red buttons and corner badges stays the same
    for (const fill of ["--red", "--red-strong", "--blue", "--warning-fill", "--danger-fill", "--text-on-fill"]) {
      assert.equal(hex(theme, fill), hex("light", fill), `${fill} (${theme})`);
    }
  }
});

test("the dark block redefines only theme colours, never the video layer, the fills or sizes", () => {
  const kept = /^--(stage|scene-|overlay-|red$|red-strong$|blue$|text-on-fill$|warning-fill$|danger-fill$|font|fs-|fw-|lh-|tracking|space-|radius|control|motion|ease|focus-width|focus-offset|page|topbar)/;
  const bad = [...DARK_BLOCK.keys()].filter((name) => kept.test(name));
  assert.deepEqual(bad, [], `redefined in the dark theme: ${bad.join(", ")}`);
  const unknown = [...DARK_BLOCK.keys()].filter((name) => !LIGHT_BLOCK.has(name));
  assert.deepEqual(unknown, [], `dark-only tokens (define them in :root too): ${unknown.join(", ")}`);
  assert.match(TOKENS_CSS, /:root\[data-theme="dark"\]\s*\{\s*color-scheme:\s*dark;/, "the dark block sets color-scheme: dark");
});

const PAGE = ["--bg", "--surface", "--surface-muted", "--surface-raised"];

// [foreground, background]: every text colour on every background it is used on.
const TEXT_PAIRS: [string, string][] = [
  ...PAGE.flatMap((bg) => ["--text-1", "--text-2", "--text-3"].map((fg) => [fg, bg] as [string, string])),
  ["--on-primary", "--primary"], // primary and play buttons, tooltip, solid neutral badge, finished guide step
  ["--on-ink", "--ink"], ["--on-ink", "--ink-2"], // top bar, dark bands, the fighter card
  ["--ink", "--on-ink"], // the chosen mode in the top bar
  ["--text-on-fill", "--red"], // red corner badge, active step number, "Dosya seç"
  ["--text-on-fill", "--red-strong"], // its hover
  ["--text-on-fill", "--blue"], // blue corner badge
  ["--text-on-fill", "--warning-fill"], // DEMO tag
  ["--text-on-fill", "--danger-fill"], // delete button
  // corner colour as text: stat headings, event sides, corner cards, soft badges
  ...[...PAGE, "--red-soft"].map((bg) => ["--red-fg", bg] as [string, string]),
  ...[...PAGE, "--blue-soft"].map((bg) => ["--blue-fg", bg] as [string, string]),
  // the drop card while a file is dragged over it
  ["--text-1", "--red-soft"], ["--text-2", "--red-soft"], ["--text-3", "--red-soft"],
  ["--success", "--surface"], ["--success", "--surface-muted"], ["--success", "--success-soft"],
  ["--warning", "--surface"], ["--warning", "--bg"], ["--warning", "--surface-muted"], ["--warning", "--warning-soft"],
  ["--danger", "--surface"], ["--danger", "--surface-raised"], ["--danger", "--danger-soft"],
  ["--text-1", "--warning-soft"], ["--text-1", "--danger-soft"], ["--text-1", "--success-soft"],
  ["--text-2", "--warning-soft"], ["--text-2", "--danger-soft"],
  ["--stage-text", "--stage"], ["--stage-text-2", "--stage"],
  // the theme menu's panel and the system panel
  ["--text-1", "--surface-raised"], ["--text-3", "--surface-raised"],
];

for (const theme of THEMES) {
  test(`${theme} theme: text tokens pass WCAG AA (4.5:1) on their backgrounds`, () => {
    const failing = TEXT_PAIRS.map(([fg, bg]) => [fg, bg, tokenContrast(theme, fg, bg)] as const)
      .filter(([, , ratio]) => ratio < 4.5)
      .map(([fg, bg, ratio]) => `${fg} on ${bg}: ${ratio.toFixed(2)}:1`);
    assert.deepEqual(failing, []);
  });

  test(`${theme} theme: secondary text on ink passes AA although it is translucent`, () => {
    for (const bg of ["--ink", "--ink-2"]) {
      const ratio = tokenContrast(theme, "--on-ink-2", bg);
      assert.ok(ratio >= 4.5, `--on-ink-2 on ${bg}: ${ratio.toFixed(2)}:1`);
    }
  });

  // The brand red sits on --ink only (logo, active step, the intro band's icons, corner badges
  // on the fighter card). Corner marks inside --ink-2 boxes use --red-on-ink (tested below).
  test(`${theme} theme: red on ink is a mark, not text: 3:1 for the logo, the active step and its line`, () => {
    for (const bg of ["--ink"]) {
      const ratio = tokenContrast(theme, "--red", bg);
      assert.ok(ratio >= 3, `--red against ${bg}: ${ratio.toFixed(2)}:1`);
      // the reason the rule exists: it does not reach the 4.5:1 of normal text
      assert.ok(ratio < 4.5, `--red on ${bg} now passes as text (${ratio.toFixed(2)}:1): update the rule in tokens.css`);
    }
  });

  test(`${theme} theme: marks, inputs and focus rings reach 3:1 (non-text contrast)`, () => {
    const marks: [string, string][] = [
      // inputs and the drop zone
      ...PAGE.map((bg) => ["--border-strong", bg] as [string, string]),
      // focus ring
      ...PAGE.map((bg) => ["--text-1", bg] as [string, string]),
      ["--stage-text", "--stage"], ["--on-ink", "--ink"], ["--on-ink", "--ink-2"],
      // corner colours in graphics on the page: timeline marks and areas' lanes, stat bars and
      // their tracks, panel top lines, event dots, chosen tiles
      ...["--red-fg", "--blue-fg"].flatMap((fg) =>
        [...PAGE, "--border"].map((bg) => [fg, bg] as [string, string])),
      // the momentum bar in the dark box and its track
      ...["--red-on-ink", "--blue-on-ink"].flatMap((fg) =>
        ["--ink", "--ink-2"].map((bg) => [fg, bg] as [string, string])),
      // progress bars and section bars: the accent on its track and on cards
      ["--accent", "--border"], ["--accent", "--surface"], ["--accent", "--bg"],
      // the accent of the Selection and Result screens (base.css)
      ["--text-1", "--border"],
      // state marks: dots, the possible-event line of the timeline, error bars
      ...["--success", "--warning", "--danger"].flatMap((fg) =>
        ["--surface", "--surface-muted", "--border"].map((bg) => [fg, bg] as [string, string])),
      // selected candidate frames over the video
      ["--red", "--stage"], ["--blue", "--stage"],
    ];
    const failing = marks.map(([fg, bg]) => [fg, bg, tokenContrast(theme, fg, bg)] as const)
      .filter(([, , ratio]) => ratio < 3)
      .map(([fg, bg, ratio]) => `${fg} against ${bg}: ${ratio.toFixed(2)}:1`);
    assert.deepEqual(failing, []);
  });
}

test("the momentum bar's blue was 2.6:1 on the dark box; both corners now reach 3:1 in both themes", () => {
  assert.ok(contrast(hex("light", "--blue"), hex("light", "--ink-2")) < 3, "the reason for --blue-on-ink");
  for (const theme of THEMES) {
    for (const fg of ["--red-on-ink", "--blue-on-ink"]) {
      assert.ok(tokenContrast(theme, fg, "--ink-2") >= 3, `${fg} on --ink-2 (${theme})`);
    }
  }
});

test("video overlay colours read on the dark stage and the warning banner text reads on its colour", () => {
  const stage = hex("light", "--stage");
  for (const name of ["red", "blue", "other", "amber", "warning", "light"]) {
    const ratio = contrast(overlay.colors[name]!, stage);
    assert.ok(ratio >= 4.5, `overlay ${name} on the stage: ${ratio.toFixed(2)}:1`);
  }
  for (const theme of THEMES) {
    assert.ok(contrast(hex(theme, "--stage-on-bright"), overlay.colors.warning!) >= 4.5);
    assert.ok(contrast(hex(theme, "--stage-on-bright"), overlay.colors.amber!) >= 4.5);
  }
});

test("motion, radius and type tokens follow the spec", () => {
  const T = TOKENS.light;
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
  assert.deepEqual(colours, [hex("light", "--red")]);
});
