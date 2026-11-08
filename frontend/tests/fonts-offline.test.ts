// Fonts ship with the app: Inter and Inter Tight come from local @fontsource
// packages and nothing in the page or its styles points at the internet.
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("../", import.meta.url));
const read = (rel: string) => readFileSync(path.join(ROOT, rel), "utf8");

function cssFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name);
    return e.isDirectory() ? cssFiles(full) : e.name.endsWith(".css") ? [full] : [];
  });
}

test("the page and its styles load nothing from the internet", () => {
  assert.doesNotMatch(read("index.html"), /https?:\/\//);
  for (const file of cssFiles(path.join(ROOT, "src"))) {
    const css = readFileSync(file, "utf8");
    assert.doesNotMatch(css, /url\(\s*["']?(https?:)?\/\//, file);
    assert.doesNotMatch(css, /@import\s+(url\()?["']?(https?:)?\/\//, file);
  }
});

test("Inter and Inter Tight are bundled from local packages", () => {
  const pkg = JSON.parse(read("package.json")) as { dependencies: Record<string, string> };
  const main = read("src/main.tsx");
  for (const [name, file] of [["inter", "inter"], ["inter-tight", "inter-tight"]] as const) {
    const id = `@fontsource-variable/${name}`;
    assert.ok(pkg.dependencies[id], `${id} is a dependency`);
    assert.match(main, new RegExp(`import "${id}/wght\\.css";`));
    // Turkish needs latin (ç ö ü ı) and latin-ext (ğ ş İ); both are local woff2 files
    for (const subset of ["latin", "latin-ext"]) {
      const woff = path.join(ROOT, "node_modules", id, "files", `${file}-${subset}-wght-normal.woff2`);
      assert.ok(existsSync(woff), woff);
    }
    const css = read(`node_modules/${id}/wght.css`);
    assert.doesNotMatch(css, /https?:\/\//);
  }
});

test("the type tokens name the bundled families first", () => {
  const tokens = read("src/styles/tokens.css");
  assert.match(tokens, /--font-sans:\s*"Inter Variable"/);
  assert.match(tokens, /--font-display:\s*"Inter Tight Variable"/);
});
