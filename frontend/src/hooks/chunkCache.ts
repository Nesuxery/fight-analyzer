/** Bounded cache of loaded pose chunks (pure helpers, used by usePoseFrames). */

/** Chunks kept in memory (~6000 frames); the least recently used ones are dropped
 * and loaded again when needed, so long videos do not fill the browser's memory. */
export const MAX_CHUNKS = 40;

/** Move a chunk to the most recently used end of the map. */
export function touch<V>(map: Map<number, V>, i: number) {
  const value = map.get(i);
  if (value === undefined) return;
  map.delete(i);
  map.set(i, value);
}

/** Drop least recently used chunks beyond MAX_CHUNKS, never the ones in `keep`. */
export function evict<V>(map: Map<number, V>, keep: readonly number[], max = MAX_CHUNKS) {
  for (const key of map.keys()) { // deleting while iterating a Map is safe
    if (map.size <= max) break;
    if (!keep.includes(key)) map.delete(key);
  }
}
