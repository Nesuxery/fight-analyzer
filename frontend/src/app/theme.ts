/**
 * Theme choice (Açık · Koyu · Sistem). The choice is stored in localStorage
 * (every read and write may throw: private windows, blocked storage), resolved
 * against the operating system's colour scheme and written to <html> as
 * data-theme, which tokens.css reads. The inline script in index.html applies
 * the same rules before the first paint, so the page never shows the wrong
 * theme while it loads; tests/theme.test.ts keeps the two in step.
 *
 * No DOM types here, so the unit tests can drive it with fakes; the browser
 * wiring is app/useTheme.ts.
 */

export type ThemeChoice = "light" | "dark" | "system";
export type Theme = "light" | "dark";

export const THEME_CHOICES = ["light", "dark", "system"] as const satisfies readonly ThemeChoice[];
export const THEME_STORAGE_KEY = "fight-analyzer.theme";
export const DARK_SCHEME_QUERY = "(prefers-color-scheme: dark)";

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

/** The part of MediaQueryList the controller uses. */
export interface MediaLike {
  readonly matches: boolean;
  addEventListener(type: "change", listener: () => void): void;
  removeEventListener(type: "change", listener: () => void): void;
}

export interface AttributeTarget {
  setAttribute(name: string, value: string): void;
}

export interface ThemeState {
  choice: ThemeChoice;
  /** The theme on screen. */
  theme: Theme;
  /** The operating system's scheme ("Sistem" follows it). */
  system: Theme;
}

export function parseChoice(value: unknown): ThemeChoice {
  return value === "light" || value === "dark" || value === "system" ? value : "system";
}

/** The stored choice; "system" when there is none, it is invalid or storage throws. */
export function readChoice(storage: () => StorageLike | null | undefined): ThemeChoice {
  try {
    return parseChoice(storage()?.getItem(THEME_STORAGE_KEY));
  } catch {
    return "system";
  }
}

/** Stores the choice; false when storage is missing or throws (the choice then lasts until reload). */
export function writeChoice(storage: () => StorageLike | null | undefined, choice: ThemeChoice): boolean {
  try {
    const s = storage();
    if (!s) return false;
    s.setItem(THEME_STORAGE_KEY, choice);
    return true;
  } catch {
    return false;
  }
}

export function resolveTheme(choice: ThemeChoice, systemDark: boolean): Theme {
  if (choice === "system") return systemDark ? "dark" : "light";
  return choice;
}

export interface ThemeEnv {
  /** A getter, because reading window.localStorage itself can throw. */
  storage: () => StorageLike | null | undefined;
  /** matchMedia(DARK_SCHEME_QUERY), or null where it is not available. */
  media: MediaLike | null;
  /** <html>: gets data-theme. */
  root: AttributeTarget;
  /** <meta name="color-scheme">: scrollbars, form controls and the page before the CSS loads follow it. */
  meta?: AttributeTarget | null;
  /** Runs before subscribers when the theme on screen changes (clears the canvas token cache). */
  onThemeChange?: (theme: Theme) => void;
}

export interface ThemeController {
  get(): ThemeState;
  setChoice(choice: ThemeChoice): void;
  /** Re-reads the stored choice (another tab changed it). */
  reload(): void;
  subscribe(listener: () => void): () => void;
  dispose(): void;
}

export function createThemeController(env: ThemeEnv): ThemeController {
  const listeners = new Set<() => void>();
  const systemTheme = (): Theme => {
    try {
      return env.media?.matches ? "dark" : "light";
    } catch {
      return "light";
    }
  };
  const compute = (choice: ThemeChoice): ThemeState => {
    const system = systemTheme();
    return { choice, theme: resolveTheme(choice, system === "dark"), system };
  };
  const apply = (theme: Theme) => {
    env.root.setAttribute("data-theme", theme);
    env.meta?.setAttribute("content", theme);
  };

  let state = compute(readChoice(env.storage));
  apply(state.theme);

  const update = (choice: ThemeChoice) => {
    const next = compute(choice);
    if (next.choice === state.choice && next.theme === state.theme && next.system === state.system) return;
    const changed = next.theme !== state.theme;
    state = next;
    if (changed) {
      apply(state.theme);
      env.onThemeChange?.(state.theme);
    }
    for (const listener of listeners) listener();
  };
  const onSystemChange = () => update(state.choice);
  env.media?.addEventListener("change", onSystemChange);

  return {
    get: () => state,
    setChoice(choice) {
      writeChoice(env.storage, choice);
      update(choice);
    },
    reload() {
      update(readChoice(env.storage));
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    dispose() {
      env.media?.removeEventListener("change", onSystemChange);
      listeners.clear();
    },
  };
}
