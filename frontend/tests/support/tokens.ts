// Token values of tokens.css per theme, for the contrast and semantic-token tests.
// Light: the :root block. Dark: :root with the :root[data-theme="dark"] block on top,
// as the browser applies them (both blocks match <html>, so var() references
// resolve against the merged set). overlay-tokens.css is the same in both themes.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

export type ThemeName = "light" | "dark";
export const THEMES: readonly ThemeName[] = ["light", "dark"];

const read = (rel: string) => readFileSync(new URL(rel, import.meta.url), "utf8");
export const TOKENS_CSS = read("../../src/styles/tokens.css");
const OVERLAY_CSS = read("../../src/styles/overlay-tokens.css");

const stripComments = (text: string) => text.replace(/\/\*[\s\S]*?\*\//g, "");

/** Declarations of the block with exactly this selector. */
function declarations(css: string, selector: string): Map<string, string> {
  const code = stripComments(css);
  const blocks = [...code.matchAll(/([^{}]+)\{([^{}]*)\}/g)].filter((m) => m[1]!.trim() === selector);
  assert.equal(blocks.length, 1, `exactly one "${selector}" block expected`);
  const out = new Map<string, string>();
  for (const m of blocks[0]![2]!.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)) out.set(m[1]!, m[2]!.trim());
  return out;
}

export const LIGHT_BLOCK = declarations(TOKENS_CSS, ":root");
export const DARK_BLOCK = declarations(TOKENS_CSS, ':root[data-theme="dark"]');
const OVERLAY_BLOCK = declarations(OVERLAY_CSS, ":root");

/** Every custom property of a theme, var() references resolved. */
export function themeTokens(theme: ThemeName): Map<string, string> {
  const raw = new Map([...OVERLAY_BLOCK, ...LIGHT_BLOCK, ...(theme === "dark" ? DARK_BLOCK : [])]);
  const resolve = (value: string, depth = 0): string => {
    const ref = /^var\((--[a-z0-9-]+)\)$/.exec(value);
    if (!ref || depth > 5) return value;
    const next = raw.get(ref[1]!);
    assert.ok(next, `${ref[1]} is not defined`);
    return resolve(next, depth + 1);
  };
  return new Map([...raw].map(([k, v]) => [k, resolve(v)]));
}

export const TOKENS: Record<ThemeName, Map<string, string>> = { light: themeTokens("light"), dark: themeTokens("dark") };

/** A #rrggbb token of a theme. */
export function hex(theme: ThemeName, name: string): string {
  const v = TOKENS[theme].get(name);
  assert.ok(v, `${name} missing from tokens.css (${theme})`);
  assert.match(v, /^#[0-9a-f]{6}$/i, `${name} should be a #rrggbb colour in the ${theme} theme, got ${v}`);
  return v.toLowerCase();
}

export function luminance(color: string): number {
  const n = Number.parseInt(color.slice(1), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const s = v / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

export const RGBA = /^rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)$/;

/** A translucent colour (rgba) as the opaque colour it shows over `bg` (#rrggbb). */
export function blend(rgba: string, bg: string): string {
  const m = RGBA.exec(rgba);
  assert.ok(m, `should be an rgba() colour, got ${rgba}`);
  const alpha = Number(m[4]);
  const base = Number.parseInt(bg.slice(1), 16);
  const mix = (fg: number, shift: number) => Math.round(fg * alpha + ((base >> shift) & 255) * (1 - alpha));
  const [r, g, b] = [mix(Number(m[1]), 16), mix(Number(m[2]), 8), mix(Number(m[3]), 0)];
  return `#${[r, g, b].map((c) => c.toString(16).padStart(2, "0")).join("")}`;
}

/** Contrast of two tokens in a theme; a translucent foreground is blended over the background. */
export function tokenContrast(theme: ThemeName, fg: string, bg: string): number {
  const back = hex(theme, bg);
  const fore = TOKENS[theme].get(fg) ?? "";
  return contrast(RGBA.test(fore) ? blend(fore, back) : hex(theme, fg), back);
}
