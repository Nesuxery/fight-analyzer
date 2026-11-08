/**
 * Canvas drawing cannot use var(); it reads the same custom properties from
 * tokens.css here, so colours still have a single source. Values are cached:
 * tokens do not change while the app runs (a future theme switch would call
 * clearTokenCache).
 */
const cache = new Map<string, string>();

export function cssToken(name: `--${string}`): string {
  const hit = cache.get(name);
  if (hit !== undefined) return hit;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  if (value) cache.set(name, value);
  return value;
}

export function clearTokenCache(): void {
  cache.clear();
}

/** "#rrggbb" with an alpha (0..1) as an rgba() string for canvas styles. */
export function withAlpha(hex: string, alpha: number): string {
  const n = Number.parseInt(hex.replace("#", ""), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}
