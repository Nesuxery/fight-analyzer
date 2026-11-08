import type { HealthResponse } from "../contracts/generated";
import { SCHEMA_VERSION } from "../contracts/generated";
import type { PollState } from "../hooks/usePolling";
import { SYSTEM_LABELS as L } from "../labels";

type Tone = "ok" | "warn" | "bad" | "info" | "pending";

interface Item {
  key: string;
  label: string;
  value: string;
  tone: Tone;
  title?: string;
}

function majorOf(version: string): string {
  return version.split(".")[0] ?? version;
}

function itemsFor(health: HealthResponse): Item[] {
  const { worker, ffmpeg, pose_model: model, database } = health;
  const compute = worker.compute;
  const items: Item[] = [
    {
      key: "db",
      label: L.database,
      value: database.status === "ok" ? L.ready : L.error,
      tone: database.status === "ok" ? "ok" : "bad",
      title: database.detail ?? undefined,
    },
    {
      key: "worker",
      label: L.worker,
      value: worker.status === "ok" ? L.ready : L.notRunning,
      tone: worker.status === "ok" ? "ok" : "bad",
    },
    {
      key: "device",
      label: L.device,
      value: compute ? `${compute.device.toUpperCase()} · ${compute.device_name}` : L.unknown,
      tone: compute ? (compute.note ? "warn" : "info") : "pending",
      title: compute
        ? [`PyTorch ${compute.torch_version}`, compute.note].filter(Boolean).join(" · ")
        : undefined,
    },
    {
      key: "ffmpeg",
      label: L.ffmpeg,
      // "7.1-essentials_build-www.gyan.dev" -> "7.1"; full build string in the tooltip.
      value: ffmpeg.status === "ok" ? (ffmpeg.version?.split("-")[0] ?? L.ready) : L.notFound,
      tone: ffmpeg.status === "ok" ? "ok" : "bad",
      title: [ffmpeg.version, ffmpeg.path].filter(Boolean).join(" · ") || undefined,
    },
    {
      key: "model",
      label: L.model,
      value: `${model.name} · ${model.present ? L.modelReady : L.modelMissing}`,
      tone: model.present ? "ok" : "info",
    },
  ];
  const schemaMatches = majorOf(health.schema_version) === majorOf(SCHEMA_VERSION);
  items.push({
    key: "schema",
    label: L.schema,
    value: `v${health.schema_version}`,
    tone: schemaMatches ? "info" : "warn",
    title: schemaMatches ? undefined : L.schemaBuiltWith(SCHEMA_VERSION),
  });
  return items;
}

/** API, worker, FFmpeg, model and schema status (inside the top bar's system panel). */
export function StatusBar({ health }: { health: PollState<HealthResponse> }) {
  const apiItem: Item = health.loading
    ? { key: "api", label: L.api, value: L.apiConnecting, tone: "pending" }
    : health.error
      ? { key: "api", label: L.api, value: L.apiUnreachable, tone: "bad" }
      : { key: "api", label: L.api, value: L.apiRunning, tone: "ok" };
  const stale = Boolean(health.error);
  const items = [apiItem, ...(health.data ? itemsFor(health.data) : [])];

  return (
    <section className="status" aria-label={L.region}>
      <ul className={stale ? "status__list status__list--stale" : "status__list"} aria-live="polite">
        {items.map((item) => (
          <li key={item.key} className={`status__item status__item--${item.tone}`} title={item.title}>
            <span className="status__dot" aria-hidden="true" />
            <span className="status__label">{item.label}</span>
            <span className="status__value">{item.value}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
