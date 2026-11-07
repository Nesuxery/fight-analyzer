import { useEffect, useState } from "react";

export interface PollState<T> {
  data: T | undefined;
  error: Error | undefined;
  /** True until the first request settles. */
  loading: boolean;
}

/** Calls `fetcher` now and then every `intervalMs` after each response settles.
 * On failure the last good data is kept alongside the error. */
export function usePolling<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  intervalMs: number,
): PollState<T> {
  const [state, setState] = useState<PollState<T>>({
    data: undefined,
    error: undefined,
    loading: true,
  });

  useEffect(() => {
    const controller = new AbortController();
    let timer: number | undefined;

    const tick = async () => {
      try {
        const data = await fetcher(controller.signal);
        setState({ data, error: undefined, loading: false });
      } catch (err) {
        if (controller.signal.aborted) return;
        setState((prev) => ({
          data: prev.data,
          error: err instanceof Error ? err : new Error(String(err)),
          loading: false,
        }));
      }
      if (!controller.signal.aborted) timer = window.setTimeout(tick, intervalMs);
    };
    void tick();

    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [fetcher, intervalMs]);

  return state;
}
