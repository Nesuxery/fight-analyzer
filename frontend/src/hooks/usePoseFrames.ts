import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { FrameRecord } from "../contracts/generated";
import { evict, touch } from "./chunkCache";

const CHUNK = 150;

/**
 * Lazily loads per-frame poses (with identities once tracking ran) in chunks
 * of 150 frames around the frames asked for. `version` (e.g. the tracking
 * cache key) resets the cache when the identity data changes.
 */
export function usePoseFrames(jobId: string, frameCount: number, version: string) {
  const chunks = useRef(new Map<number, FrameRecord[] | "loading">());
  const [loaded, setLoaded] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    chunks.current = new Map();
    setLoaded((n) => n + 1);
  }, [jobId, version]);

  const ensure = useCallback((frame: number) => {
    const index = Math.floor(frame / CHUNK);
    for (const i of [index, index + 1]) {
      if (i < 0 || i * CHUNK >= frameCount) continue;
      if (chunks.current.has(i)) {
        touch(chunks.current, i);
        continue;
      }
      const map = chunks.current;
      map.set(i, "loading");
      api.poses(jobId, i * CHUNK, CHUNK).then(
        (chunk) => {
          if (chunks.current !== map) return; // reset meanwhile
          map.set(i, chunk.frames);
          evict(map, [i, Math.floor(frame / CHUNK), Math.floor(frame / CHUNK) + 1]);
          setLoaded((n) => n + 1);
        },
        (err: unknown) => {
          map.delete(i);
          setError(err instanceof Error ? err.message : String(err));
        },
      );
    }
  }, [jobId, frameCount]);

  const get = (frame: number): FrameRecord | "loading" | undefined => {
    const cached = chunks.current.get(Math.floor(frame / CHUNK));
    if (cached === "loading") return "loading";
    return cached?.[frame % CHUNK];
  };

  /** `loaded` changes whenever a chunk arrives (to redraw a paused frame). */
  return { ensure, get, error, loaded };
}
