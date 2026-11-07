import type { HealthResponse } from "../contracts/generated";
import { SCHEMA_VERSION } from "../contracts/generated";
import type { PollState } from "../hooks/usePolling";

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
      label: "Veritabanı",
      value: database.status === "ok" ? "Hazır" : "Hata",
      tone: database.status === "ok" ? "ok" : "bad",
      title: database.detail ?? undefined,
    },
    {
      key: "worker",
      label: "Analiz işçisi",
      value: worker.status === "ok" ? "Hazır" : "Çalışmıyor",
      tone: worker.status === "ok" ? "ok" : "bad",
    },
    {
      key: "device",
      label: "İşlem birimi",
      value: compute ? `${compute.device.toUpperCase()} · ${compute.device_name}` : "Bilinmiyor",
      tone: compute ? (compute.note ? "warn" : "info") : "pending",
      title: compute
        ? [`PyTorch ${compute.torch_version}`, compute.note].filter(Boolean).join(" · ")
        : undefined,
    },
    {
      key: "ffmpeg",
      label: "FFmpeg",
      // "7.1-essentials_build-www.gyan.dev" -> "7.1"; full build string in the tooltip.
      value: ffmpeg.status === "ok" ? (ffmpeg.version?.split("-")[0] ?? "Hazır") : "Bulunamadı",
      tone: ffmpeg.status === "ok" ? "ok" : "bad",
      title: [ffmpeg.version, ffmpeg.path].filter(Boolean).join(" · ") || undefined,
    },
    {
      key: "model",
      label: "Poz modeli",
      value: `${model.name} · ${model.present ? "hazır" : "indirilmedi"}`,
      tone: model.present ? "ok" : "info",
    },
  ];
  const schemaMatches = majorOf(health.schema_version) === majorOf(SCHEMA_VERSION);
  items.push({
    key: "schema",
    label: "Şema",
    value: `v${health.schema_version}`,
    tone: schemaMatches ? "info" : "warn",
    title: schemaMatches ? undefined : `Arayüz şema v${SCHEMA_VERSION} ile derlendi`,
  });
  return items;
}

export function StatusBar({ health }: { health: PollState<HealthResponse> }) {
  const apiItem: Item = health.loading
    ? { key: "api", label: "API", value: "Bağlanıyor…", tone: "pending" }
    : health.error
      ? { key: "api", label: "API", value: "Ulaşılamıyor", tone: "bad" }
      : { key: "api", label: "API", value: "Çalışıyor", tone: "ok" };
  const stale = Boolean(health.error);
  const items = [apiItem, ...(health.data ? itemsFor(health.data) : [])];

  return (
    <section className="status" aria-label="Sistem durumu">
      <ul className={stale ? "status__list status__list--stale" : "status__list"} aria-live="polite">
        {items.map((item) => (
          <li key={item.key} className={`chip chip--${item.tone}`} title={item.title}>
            <span className="chip__dot" aria-hidden="true" />
            <span className="chip__label">{item.label}</span>
            <span className="chip__value">{item.value}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
