import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { api } from "../api/client";
import { usePolling } from "../hooks/usePolling";
import { SHELL_LABELS as L } from "../labels";
import { DemoBanner, SegmentedControl, Stepper } from "../ui";
import type { StepItem } from "../ui";
import { IconOctagon } from "../ui/icons";
import { href } from "./router";
import type { Route, Screen } from "./router";
import { StatusBar } from "./StatusBar";

const SCREENS: readonly Screen[] = ["upload", "processing", "select", "result"];

function stepHref(route: Route, screen: Screen): string | null {
  if (route.mode === "demo") return href({ mode: "demo", screen });
  if (route.mode !== "analysis") return screen === "upload" ? "#/" : null;
  if (screen === "upload") return "#/";
  return route.screen === "upload" ? null : href({ mode: "analysis", screen, jobId: route.jobId });
}

/** "Sistem hazır" with a status dot; the details open in a floating panel (Esc or a click outside closes it). */
function SystemStatus() {
  const health = usePolling(api.health, 10000);
  const ref = useRef<HTMLDetailsElement>(null);
  const state = health.loading ? "pending" : health.error ? "bad"
    : health.data?.status === "ok" ? "ok" : "warn";

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const details = ref.current;
      if (e.key !== "Escape" || !details?.open) return;
      details.open = false;
      details.querySelector("summary")?.focus();
    };
    const onPointer = (e: PointerEvent) => {
      const details = ref.current;
      if (details?.open && !details.contains(e.target as Node)) details.open = false;
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, []);

  return (
    <details ref={ref} className="sys">
      <summary className={`sys__summary sys__summary--${state}`}>
        <span className="sys__dot" aria-hidden="true" />
        <span className="sys__text">{L.system[state]}</span>
      </summary>
      <div className="sys__panel">
        <p className="sys__title">{L.systemTitle}</p>
        <StatusBar health={health} />
      </div>
    </details>
  );
}

export function AppShell({ route, children }: { route: Route; children: ReactNode }) {
  const demo = route.mode === "demo";
  const current = route.mode === "notFound" ? null : route.screen;
  const steps: StepItem[] = SCREENS.map((screen) => ({
    id: screen, label: L.steps[screen], href: stepHref(route, screen), disabledReason: L.stepDisabled,
  }));
  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href={demo ? "#/demo" : "#/"} aria-label={L.home}>
          <IconOctagon className="brand__mark" />
          <span className="brand__name">{L.brand}</span>
        </a>
        <Stepper label={L.stepsLabel} steps={steps} current={current} />
        <div className="topbar__end">
          <SegmentedControl label={L.modeLabel} value={demo ? "demo" : "analysis"} options={[
            { value: "analysis", label: L.modeAnalysis, href: "#/" },
            { value: "demo", label: L.modeDemo, href: "#/demo" },
          ]} />
          <SystemStatus />
        </div>
      </header>
      {demo && <DemoBanner />}
      <main className={`shell__main${current === "result" ? " shell__main--wide" : ""}`}>{children}</main>
    </div>
  );
}
