export type StepState = "done" | "active" | "upcoming";

/** State of step `index` when the step at `currentIndex` is open (-1: none is). Steps before the open one count as done. */
export function stepState(index: number, currentIndex: number): StepState {
  if (currentIndex < 0) return "upcoming";
  if (index === currentIndex) return "active";
  return index < currentIndex ? "done" : "upcoming";
}
