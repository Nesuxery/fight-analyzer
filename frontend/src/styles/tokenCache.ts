/**
 * Cache of custom property values for canvas drawing (styles/tokens.ts). Kept
 * free of DOM types so the unit tests can run it: `read` is the lookup.
 * clear() empties it when the theme changes, and version() counts the clears,
 * so caches built from tokens (the demo backdrop) and canvas loops can tell
 * that their colours are stale.
 */
export interface TokenCache {
  get(name: `--${string}`): string;
  clear(): void;
  version(): number;
}

export function createTokenCache(read: (name: `--${string}`) => string): TokenCache {
  const cache = new Map<string, string>();
  let version = 0;
  return {
    get(name) {
      const hit = cache.get(name);
      if (hit !== undefined) return hit;
      const value = read(name);
      if (value) cache.set(name, value);
      return value;
    },
    clear() {
      cache.clear();
      version += 1;
    },
    version: () => version,
  };
}
