import { useSyncExternalStore } from "react";

/** The four screens of the app. */
export type Screen = "upload" | "processing" | "select" | "result";

/** Optional selection-screen parameters: open on a frame, keep earlier selections (correction). */
export interface SelectParams {
  frame?: number;
  keep?: boolean;
}

/**
 * Hash routes:
 *   #/                              upload (analysis mode)
 *   #/analyses/<jobId>/<screen>     processing | select | result for a real job
 *   #/analyses/<jobId>/select?frame=N&keep=1   selection on frame N, keeping earlier anchors
 *   #/demo[/<screen>]               the same screens with clearly labelled demo data
 */
export type Route =
  | { mode: "analysis"; screen: "upload" }
  | { mode: "analysis"; screen: Exclude<Screen, "upload">; jobId: string; params?: SelectParams }
  | { mode: "demo"; screen: Screen }
  | { mode: "notFound"; path: string };

const JOB_ID = /^[0-9a-f]{32}$/;
const JOB_SCREENS = new Set<Screen>(["processing", "select", "result"]);

function parseParams(query: string): SelectParams | undefined {
  if (!query) return undefined;
  const q = new URLSearchParams(query);
  const frame = Number(q.get("frame"));
  return {
    frame: q.has("frame") && Number.isInteger(frame) && frame >= 0 ? frame : undefined,
    keep: q.get("keep") === "1",
  };
}

export function parseRoute(hash: string): Route {
  const raw = hash.replace(/^#/, "") || "/";
  const [path = "/", query = ""] = raw.split("?", 2);
  const parts = path.split("/").filter(Boolean);
  if (parts.length === 0) return { mode: "analysis", screen: "upload" };
  if (parts[0] === "demo") {
    const screen = (parts[1] ?? "upload") as Screen;
    if (parts.length <= 2 && (screen === "upload" || JOB_SCREENS.has(screen))) {
      return { mode: "demo", screen };
    }
  }
  if (parts[0] === "analyses" && parts.length === 3) {
    const [, jobId, screen] = parts as [string, string, Screen];
    if (JOB_ID.test(jobId) && JOB_SCREENS.has(screen)) {
      return { mode: "analysis", screen: screen as Exclude<Screen, "upload">, jobId,
               params: screen === "select" ? parseParams(query) : undefined };
    }
  }
  return { mode: "notFound", path: raw };
}

export function href(route: Exclude<Route, { mode: "notFound" }>): string {
  if (route.mode === "demo") return route.screen === "upload" ? "#/demo" : `#/demo/${route.screen}`;
  if (route.screen === "upload") return "#/";
  const base = `#/analyses/${route.jobId}/${route.screen}`;
  const p = route.params;
  if (!p || (p.frame === undefined && !p.keep)) return base;
  const q = new URLSearchParams();
  if (p.frame !== undefined) q.set("frame", String(p.frame));
  if (p.keep) q.set("keep", "1");
  return `${base}?${q.toString()}`;
}

export function navigate(route: Exclude<Route, { mode: "notFound" }>): void {
  window.location.hash = href(route);
}

function subscribe(onChange: () => void) {
  window.addEventListener("hashchange", onChange);
  return () => window.removeEventListener("hashchange", onChange);
}

export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribe, () => window.location.hash);
  return parseRoute(hash);
}
