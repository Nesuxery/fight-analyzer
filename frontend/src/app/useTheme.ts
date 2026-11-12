/**
 * Browser wiring of app/theme.ts: one controller for the page, created when
 * the app loads (the boot script in index.html has already set data-theme).
 * A theme change clears the canvas token cache first, then re-renders the
 * components that use useTheme().
 */
import { useSyncExternalStore } from "react";
import { clearTokenCache } from "../styles/tokens";
import { DARK_SCHEME_QUERY, THEME_STORAGE_KEY, createThemeController } from "./theme";
import type { ThemeChoice, ThemeState } from "./theme";

function darkSchemeQuery(): MediaQueryList | null {
  try {
    return window.matchMedia(DARK_SCHEME_QUERY);
  } catch {
    return null;
  }
}

const controller = createThemeController({
  storage: () => window.localStorage,
  media: darkSchemeQuery(),
  root: document.documentElement,
  meta: document.querySelector('meta[name="color-scheme"]'),
  onThemeChange: clearTokenCache,
});

// a choice made in another tab of the app
window.addEventListener("storage", (e) => {
  if (e.key === THEME_STORAGE_KEY || e.key === null) controller.reload();
});

export function useTheme(): ThemeState {
  return useSyncExternalStore(controller.subscribe, controller.get);
}

export function setThemeChoice(choice: ThemeChoice): void {
  controller.setChoice(choice);
}
