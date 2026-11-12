// Theme choice (Açık · Koyu · Sistem): stored choice, the operating system's scheme
// in "Sistem", the canvas token cache and the boot script that sets the theme before
// the first paint (index.html).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";
import {
  DARK_SCHEME_QUERY, THEME_CHOICES, THEME_STORAGE_KEY, createThemeController, parseChoice, readChoice, resolveTheme,
  writeChoice,
} from "../src/app/theme.ts";
import type { MediaLike, StorageLike, Theme, ThemeChoice } from "../src/app/theme.ts";
import { createTokenCache } from "../src/styles/tokenCache.ts";

function memoryStorage(initial: Record<string, string> = {}): StorageLike & { data: Map<string, string> } {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => void data.set(key, value),
  };
}

const throwingStorage: StorageLike = {
  getItem: () => { throw new Error("SecurityError"); },
  setItem: () => { throw new Error("QuotaExceededError"); },
};

/** A prefers-color-scheme query whose answer the test changes. */
function fakeMedia(dark: boolean): MediaLike & { set(dark: boolean): void; listeners: Set<() => void> } {
  const listeners = new Set<() => void>();
  let matches = dark;
  return {
    get matches() { return matches; },
    addEventListener: (_type, fn) => void listeners.add(fn),
    removeEventListener: (_type, fn) => void listeners.delete(fn),
    set(next) {
      matches = next;
      for (const fn of listeners) fn();
    },
    listeners,
  };
}

function fakeElement() {
  const attrs = new Map<string, string>();
  return { attrs, setAttribute: (name: string, value: string) => void attrs.set(name, value) };
}

function setup(opts: { stored?: string; dark?: boolean; storage?: StorageLike | null } = {}) {
  const storage = opts.storage !== undefined ? opts.storage
    : memoryStorage(opts.stored === undefined ? {} : { [THEME_STORAGE_KEY]: opts.stored });
  const media = fakeMedia(opts.dark ?? false);
  const root = fakeElement();
  const meta = fakeElement();
  const changes: Theme[] = [];
  const controller = createThemeController({
    storage: () => storage, media, root, meta, onThemeChange: (theme) => changes.push(theme),
  });
  let notified = 0;
  controller.subscribe(() => notified++);
  return { controller, storage, media, root, meta, changes, notified: () => notified };
}

test("a missing, unknown or unreadable choice is Sistem", () => {
  assert.equal(parseChoice(null), "system");
  assert.equal(parseChoice("blue"), "system");
  assert.equal(parseChoice("dark"), "dark");
  assert.equal(readChoice(() => memoryStorage()), "system");
  assert.equal(readChoice(() => memoryStorage({ [THEME_STORAGE_KEY]: "light" })), "light");
  assert.equal(readChoice(() => throwingStorage), "system");
  assert.equal(readChoice(() => null), "system");
  assert.equal(readChoice(() => { throw new Error("localStorage is not available"); }), "system");
});

test("writing the choice never throws; it reports whether it was stored", () => {
  const storage = memoryStorage();
  assert.equal(writeChoice(() => storage, "dark"), true);
  assert.equal(storage.data.get(THEME_STORAGE_KEY), "dark");
  assert.equal(writeChoice(() => throwingStorage, "dark"), false);
  assert.equal(writeChoice(() => null, "dark"), false);
  assert.equal(writeChoice(() => { throw new Error("no storage"); }, "light"), false);
});

test("Açık and Koyu are fixed; Sistem follows the operating system", () => {
  assert.deepEqual(THEME_CHOICES, ["light", "dark", "system"]);
  for (const systemDark of [false, true]) {
    assert.equal(resolveTheme("light", systemDark), "light");
    assert.equal(resolveTheme("dark", systemDark), "dark");
    assert.equal(resolveTheme("system", systemDark), systemDark ? "dark" : "light");
  }
});

test("the default is Sistem, applied to <html data-theme> and <meta name=color-scheme> at start", () => {
  const light = setup({ dark: false });
  assert.deepEqual(light.controller.get(), { choice: "system", theme: "light", system: "light" });
  assert.equal(light.root.attrs.get("data-theme"), "light");
  assert.equal(light.meta.attrs.get("content"), "light");
  const dark = setup({ dark: true });
  assert.deepEqual(dark.controller.get(), { choice: "system", theme: "dark", system: "dark" });
  assert.equal(dark.root.attrs.get("data-theme"), "dark");
  assert.equal(dark.meta.attrs.get("content"), "dark");
});

test("Sistem mode switches when the operating system's theme changes, without a reload", () => {
  const s = setup({ dark: false });
  s.media.set(true);
  assert.equal(s.root.attrs.get("data-theme"), "dark");
  assert.equal(s.meta.attrs.get("content"), "dark");
  assert.deepEqual(s.changes, ["dark"]);
  assert.equal(s.notified(), 1);
  s.media.set(false);
  assert.equal(s.root.attrs.get("data-theme"), "light");
  assert.deepEqual(s.changes, ["dark", "light"]);
});

test("Açık and Koyu ignore the operating system, but the menu still learns its scheme", () => {
  const s = setup({ dark: false });
  s.controller.setChoice("light");
  s.media.set(true);
  assert.equal(s.root.attrs.get("data-theme"), "light");
  assert.deepEqual(s.controller.get(), { choice: "light", theme: "light", system: "dark" });
  assert.deepEqual(s.changes, [], "the theme on screen did not change");
  s.controller.setChoice("dark");
  s.media.set(false);
  assert.equal(s.root.attrs.get("data-theme"), "dark");
  assert.deepEqual(s.changes, ["dark"]);
});

test("the choice is stored and the next page load starts with it", () => {
  const s = setup({ dark: false });
  s.controller.setChoice("dark");
  assert.equal((s.storage as ReturnType<typeof memoryStorage>).data.get(THEME_STORAGE_KEY), "dark");
  const next = createThemeController({ storage: () => s.storage, media: fakeMedia(false), root: fakeElement() });
  assert.deepEqual(next.get(), { choice: "dark", theme: "dark", system: "light" });
});

test("blocked storage: the choice still applies for this session", () => {
  const s = setup({ storage: throwingStorage, dark: false });
  assert.equal(s.controller.get().choice, "system");
  assert.doesNotThrow(() => s.controller.setChoice("dark"));
  assert.equal(s.root.attrs.get("data-theme"), "dark");
});

test("a choice made in another tab is picked up by reload()", () => {
  const s = setup({ stored: "light", dark: true });
  assert.equal(s.controller.get().theme, "light");
  (s.storage as ReturnType<typeof memoryStorage>).data.set(THEME_STORAGE_KEY, "system");
  s.controller.reload();
  assert.deepEqual(s.controller.get(), { choice: "system", theme: "dark", system: "dark" });
});

test("picking the same choice again changes nothing; dispose stops following the system", () => {
  const s = setup({ stored: "system", dark: false });
  s.controller.setChoice("system");
  assert.equal(s.notified(), 0);
  s.controller.dispose();
  assert.equal(s.media.listeners.size, 0);
});

test("a theme change clears the canvas token cache before subscribers redraw", () => {
  const values: Record<Theme, string> = { light: "#ffffff", dark: "#151518" };
  let current: Theme = "light";
  const cache = createTokenCache(() => values[current]);
  const media = fakeMedia(false);
  const root = fakeElement();
  const controller = createThemeController({
    storage: () => memoryStorage(), media, root,
    onThemeChange: (theme) => {
      current = theme;
      cache.clear();
    },
  });
  const seen: string[] = [];
  controller.subscribe(() => seen.push(cache.get("--surface")));
  assert.equal(cache.get("--surface"), "#ffffff");
  assert.equal(cache.version(), 0);
  controller.setChoice("dark");
  assert.deepEqual(seen, ["#151518"], "subscribers read the new colour");
  assert.equal(cache.version(), 1);
  // choice changes that keep the theme on screen keep the cache
  media.set(true);
  controller.setChoice("system");
  assert.equal(cache.version(), 1);
});

// ---------- the boot script in index.html ----------

const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const head = html.slice(0, html.indexOf("</head>"));
const boot = /<script>([\s\S]*?)<\/script>/.exec(head);

test("index.html sets the theme in <head> before anything is drawn", () => {
  assert.ok(boot, "an inline <script> in <head>");
  const at = head.indexOf(boot[0]);
  assert.ok(head.indexOf('<meta name="color-scheme"') < at, "the meta tag comes first (the script updates it)");
  assert.ok(at < html.indexOf('<script type="module"'), "before the app module, which loads the CSS");
  const links = [...head.matchAll(/<link[^>]+rel="stylesheet"/g)].map((m) => m.index);
  assert.ok(links.every((i) => i > at), "before any stylesheet");
  assert.ok(boot[1]!.includes(THEME_STORAGE_KEY) && boot[1]!.includes(DARK_SCHEME_QUERY));
});

test("the boot script picks the same theme as app/theme.ts in every case", () => {
  const storedValues: (string | null | "THROW")[] = [null, "light", "dark", "system", "blue", "THROW"];
  const systems: (boolean | "THROW")[] = [false, true, "THROW"];
  for (const stored of storedValues) {
    for (const system of systems) {
      const attrs: Record<string, string> = {};
      const meta: Record<string, string> = {};
      const window = {
        get localStorage() {
          if (stored === "THROW") throw new Error("SecurityError");
          return { getItem: (key: string) => (key === THEME_STORAGE_KEY ? stored : null) };
        },
        matchMedia(query: string) {
          if (system === "THROW") throw new Error("matchMedia unavailable");
          return { matches: query === DARK_SCHEME_QUERY && system };
        },
      };
      const document = {
        documentElement: { setAttribute: (k: string, v: string) => { attrs[k] = v; } },
        querySelector: (sel: string) => (sel === 'meta[name="color-scheme"]'
          ? { setAttribute: (k: string, v: string) => { meta[k] = v; } } : null),
      };
      vm.runInNewContext(boot![1]!, { window, document });
      const choice: ThemeChoice = stored === "THROW" ? "system" : parseChoice(stored);
      const expected = resolveTheme(choice, system === true);
      const label = `stored=${stored} system=${system}`;
      assert.equal(attrs["data-theme"], expected, label);
      assert.equal(meta.content, expected, label);
      // and the controller agrees
      const controller = createThemeController({
        storage: () => (stored === "THROW" ? throwingStorage : memoryStorage(stored === null ? {} : { [THEME_STORAGE_KEY]: stored })),
        media: system === "THROW" ? null : fakeMedia(system),
        root: fakeElement(),
      });
      assert.equal(controller.get().theme, expected, `controller, ${label}`);
    }
  }
});
