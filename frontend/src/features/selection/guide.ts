// The numbered guide above the selection screen: 1. red corner, 2. blue corner,
// 3. check the names and confirm. Derived from the picks alone.

export type GuideStepId = "red" | "blue" | "confirm";
export type GuideState = "done" | "active" | "upcoming";

export interface GuideStep {
  id: GuideStepId;
  state: GuideState;
}

/**
 * `ready`: both corners are set and the selection can be confirmed (it cannot
 * when both are marked "not in view"). Picks fill red first, then blue; a pick
 * can be removed again, so step 1 may be active while step 2 is done. The last
 * step is never "done": confirming leaves the screen.
 */
export function selectionGuide(picks: { red: string | null; blue: string | null }, ready: boolean): GuideStep[] {
  const red: GuideState = picks.red !== null ? "done" : "active";
  const blue: GuideState = picks.blue !== null ? "done" : picks.red !== null ? "active" : "upcoming";
  return [
    { id: "red", state: red },
    { id: "blue", state: blue },
    { id: "confirm", state: ready ? "active" : "upcoming" },
  ];
}
