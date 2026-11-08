import type { ReactNode } from "react";
import { api } from "../api/client";
import { StatusBar } from "../components/StatusBar";
import { DemoBanner } from "../components/ui";
import { usePolling } from "../hooks/usePolling";
import { href } from "./router";
import type { Route, Screen } from "./router";

const STEPS: { screen: Screen; label: string }[] = [
  { screen: "upload", label: "Yükleme" },
  { screen: "processing", label: "İşlem" },
  { screen: "select", label: "Seçim" },
  { screen: "result", label: "Sonuç" },
];

function stepHref(route: Route, screen: Screen): string | null {
  if (route.mode === "demo") return href({ mode: "demo", screen });
  if (route.mode !== "analysis") return screen === "upload" ? "#/" : null;
  if (screen === "upload") return "#/";
  return route.screen === "upload" ? null : href({ mode: "analysis", screen, jobId: route.jobId });
}

function SystemStatus() {
  const health = usePolling(api.health, 10000);
  const state = health.loading ? "pending" : health.error ? "bad"
    : health.data?.status === "ok" ? "ok" : "warn";
  const text = { pending: "Bağlanıyor", bad: "API'ye ulaşılamıyor", ok: "Sistem hazır",
                 warn: "Sistemde sorun var" }[state];
  return (
    <details className="sys">
      <summary className={`sys__summary sys__summary--${state}`}>
        <span className="sys__dot" aria-hidden="true" />
        <span className="sys__text">{text}</span>
      </summary>
      <div className="sys__panel">
        <p className="sys__title">Sistem durumu</p>
        <StatusBar health={health} />
      </div>
    </details>
  );
}

export function AppShell({ route, children }: { route: Route; children: ReactNode }) {
  const demo = route.mode === "demo";
  const current = route.mode === "notFound" ? null : route.screen;
  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href={demo ? "#/demo" : "#/"}>
          <img className="brand__mark" src="/octagon.svg" alt="" width={28} height={28} />
          <span className="brand__name">FIGHT ANALYZER</span>
        </a>

        <nav className="steps" aria-label="Ekranlar">
          <ol>
            {STEPS.map((step, i) => {
              const target = stepHref(route, step.screen);
              const active = current === step.screen;
              const content = (
                <>
                  <span className="steps__num">{i + 1}</span>
                  <span className="steps__label">{step.label}</span>
                </>
              );
              return (
                <li key={step.screen}>
                  {target ? (
                    <a className={`steps__item${active ? " is-active" : ""}`} href={target}
                       aria-current={active ? "page" : undefined}>{content}</a>
                  ) : (
                    <span className="steps__item is-disabled" aria-disabled="true"
                          title="Önce bir analiz seçin veya video yükleyin">{content}</span>
                  )}
                </li>
              );
            })}
          </ol>
        </nav>

        <div className="topbar__end">
          <div className="mode" role="group" aria-label="Mod">
            <a className={`mode__btn${demo ? "" : " is-active"}`} href="#/"
               aria-current={demo ? undefined : "true"}>Analiz</a>
            <a className={`mode__btn mode__btn--demo${demo ? " is-active" : ""}`} href="#/demo"
               aria-current={demo ? "true" : undefined}>Demo</a>
          </div>
          <SystemStatus />
        </div>
      </header>
      {demo && <DemoBanner />}
      <main className={`shell__main${current === "result" ? " shell__main--wide" : ""}`}>{children}</main>
    </div>
  );
}
