/**
 * Canvas drawing cannot use var(); it reads the same custom properties from
 * tokens.css here, so colours still have a single source. Values are cached
 * until the theme changes: app/useTheme.ts calls clearTokenCache, and canvas
 * code compares tokenVersion() to redraw with the new colours.
 */
import { createTokenCache } from "./tokenCache.ts";

const tokens = createTokenCache((name) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim());

export function cssToken(name: `--${string}`): string {
  return tokens.get(name);
}

export function clearTokenCache(): void {
  tokens.clear();
}

/** Changes every time the token cache is cleared (theme change). */
export function tokenVersion(): number {
  return tokens.version();
}

/** "#rrggbb" with an alpha (0..1) as an rgba() string for canvas styles. */
export function withAlpha(hex: string, alpha: number): string {
  const n = Number.parseInt(hex.replace("#", ""), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}
