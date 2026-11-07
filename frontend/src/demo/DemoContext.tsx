import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { Assignment, Side } from "../model/analysis";
import { LEFT, RIGHT } from "./script";

/** Simulated pipeline timing for the demo processing screen (seconds). */
export const DEMO_PRE_SELECTION_S = 9;
export const DEMO_POST_SELECTION_S = 5;

export interface DemoState {
  names: Record<Side, string>;
  assignment: Assignment;
  /** Epoch ms when the demo "analysis" started; null = not started. */
  startedAt: number | null;
  /** Epoch ms when fighters were confirmed; null = waiting for selection. */
  selectedAt: number | null;
}

const DEFAULT_STATE: DemoState = {
  // Neutral names: they follow the fighter when sides are swapped.
  names: { red: "Dövüşçü 1", blue: "Dövüşçü 2" },
  assignment: { red: LEFT, blue: RIGHT },
  startedAt: null,
  selectedAt: null,
};

const STORAGE_KEY = "fa-demo-state-v2";

function load(): DemoState {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (raw) return { ...DEFAULT_STATE, ...(JSON.parse(raw) as Partial<DemoState>) };
  } catch {
    // storage unavailable: fall back to defaults
  }
  return DEFAULT_STATE;
}

interface DemoApi {
  state: DemoState;
  start: () => void;
  confirmSelection: (assignment: Assignment) => void;
  rename: (side: Side, name: string) => void;
  swapSides: () => void;
  reset: () => void;
}

const DemoContext = createContext<DemoApi | null>(null);

export function DemoProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<DemoState>(load);

  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // ignore: demo state is a convenience only
    }
  }, [state]);

  const start = useCallback(
    () => setState((s) => ({ ...s, startedAt: Date.now(), selectedAt: null })),
    [],
  );
  const confirmSelection = useCallback(
    (assignment: Assignment) =>
      setState((s) => ({
        ...s,
        assignment,
        startedAt: s.startedAt ?? Date.now() - DEMO_PRE_SELECTION_S * 1000,
        selectedAt: Date.now(),
      })),
    [],
  );
  const rename = useCallback(
    (side: Side, name: string) => setState((s) => ({ ...s, names: { ...s.names, [side]: name } })),
    [],
  );
  const swapSides = useCallback(
    () =>
      setState((s) => ({
        ...s,
        names: { red: s.names.blue, blue: s.names.red },
        assignment: { red: s.assignment.blue, blue: s.assignment.red },
      })),
    [],
  );
  const reset = useCallback(() => setState(DEFAULT_STATE), []);

  const api = useMemo(
    () => ({ state, start, confirmSelection, rename, swapSides, reset }),
    [state, start, confirmSelection, rename, swapSides, reset],
  );
  return <DemoContext.Provider value={api}>{children}</DemoContext.Provider>;
}

export function useDemo(): DemoApi {
  const ctx = useContext(DemoContext);
  if (!ctx) throw new Error("useDemo must be used inside DemoProvider");
  return ctx;
}
