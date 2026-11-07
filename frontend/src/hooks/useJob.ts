import { useCallback } from "react";
import { ApiError, api } from "../api/client";
import type { Job } from "../contracts/generated";
import { usePolling } from "./usePolling";
import type { PollState } from "./usePolling";

export type JobState = PollState<Job> & { notFound: boolean };

/** Poll one job; `notFound` distinguishes a missing job from a network error. */
export function useJob(jobId: string, intervalMs = 2000): JobState {
  const fetcher = useCallback((signal: AbortSignal) => api.job(jobId, signal), [jobId]);
  const state = usePolling(fetcher, intervalMs);
  const notFound = state.error instanceof ApiError && state.error.status === 404;
  return { ...state, notFound };
}
