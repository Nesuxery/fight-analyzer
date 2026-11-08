import type { EventType, Job, JobStatus, PipelineStage } from "./contracts/generated";
import type { Side } from "./model/analysis";

/** Corner names ("Kırmızı köşe", "Mavi köşe" in full). */
export const SIDE_LABEL: Record<Side, string> = { red: "Kırmızı", blue: "Mavi" };

/** Texts drawn on the video overlay (browser canvas). */
export const OVERLAY_LABELS = {
  possibleContact: "olası temas",
  distance: (torsoLengths: string) => `${torsoLengths} gövde boyu`,
} as const;

export const DEMO_LABELS = {
  tag: "DEMO",
  banner: "Tasarım önizlemesi: tüm görüntü, istatistik ve olaylar örnektir; gerçek analiz değildir.",
  watermark: "DEMO · SENTETİK SAHNE",
} as const;

export const COMMON_LABELS = {
  notFoundTitle: "Sayfa bulunamadı",
  notFoundText: "adresinde bir ekran yok.",
  backToUpload: "Yükleme ekranına dön",
} as const;

/** System status panel in the top bar (API health). */
export const SYSTEM_LABELS = {
  region: "Sistem durumu",
  api: "API",
  apiConnecting: "Bağlanıyor…",
  apiUnreachable: "Ulaşılamıyor",
  apiRunning: "Çalışıyor",
  database: "Veritabanı",
  ready: "Hazır",
  error: "Hata",
  worker: "Analiz işçisi",
  notRunning: "Çalışmıyor",
  device: "İşlem birimi",
  unknown: "Bilinmiyor",
  ffmpeg: "FFmpeg",
  notFound: "Bulunamadı",
  model: "Poz modeli",
  modelReady: "hazır",
  modelMissing: "indirilmedi",
  schema: "Şema",
  schemaBuiltWith: (version: string) => `Arayüz şema v${version} ile derlendi`,
} as const;

/** Texts of the shared ui/ components. */
export const UI_LABELS = {
  notifications: "Bildirimler",
  closeNotification: "Bildirimi kapat",
  uncertain: "belirsiz",
  noValue: "—",
} as const;

// Record<Union, string> makes the compiler flag any status/stage/event type
// added to the backend contract without a Turkish label.
export const JOB_STATUS_LABELS: Record<JobStatus, string> = {
  queued: "Sırada",
  running: "İşleniyor",
  awaiting_selection: "Seçim bekliyor",
  completed: "Tamamlandı",
  failed: "Başarısız",
  cancelled: "İptal edildi",
};

export const STAGE_LABELS: Record<PipelineStage, string> = {
  video_prep: "Video hazırlama",
  pose: "Poz tespiti",
  tracking_prep: "Takip hazırlığı",
  tracking: "Kimlik takibi",
  events: "Olay tespiti",
  scoring: "Puanlama",
  export: "Dışa aktarma",
};

export const EVENT_LABELS: Record<EventType, string> = {
  punch: "Yumruk denemesi",
  kick: "Tekme denemesi",
  knee: "Diz denemesi",
  clinch: "Klinç",
  takedown: "Olası takedown",
  ground_control: "Yer kontrolü (tahmini)",
  knockdown: "Olası knockdown",
  stance_change: "Duruş değişimi",
  other: "Diğer",
};

/** Known job error codes shown in plain language; others show the message. */
export const ERROR_LABELS: Record<string, string> = {
  stage_not_implemented: "Bu analiz aşaması bu sürümde henüz uygulanmadı.",
  worker_lost: "Analiz işçisi iş sırasında durdu.",
  internal_error: "Analiz sırasında beklenmeyen bir hata oluştu.",
  unsupported_job_type: "Bu iş türü desteklenmiyor.",
  invalid_job: "Analiz kaydı eksik; kaynak video bulunamadı.",
  source_missing: "Yüklenen kaynak video artık diskte yok.",
  invalid_video: "Dosya çözümlenebilir bir video değil.",
  no_video_stream: "Dosyada video akışı yok.",
  undecodable_video: "Video kareleri çözülemedi; dosya bozuk olabilir.",
  transcode_failed: "Video analiz kopyasına dönüştürülemedi.",
  ffmpeg_unavailable: "FFmpeg bulunamadı.",
  missing_video: "Analiz videosu hazırlanmamış.",
  model_unavailable: "Poz modeli hazırlanamadı.",
  decode_failed: "Analiz videosundan kare okunamadı.",
  pose_failed: "Poz tespiti sırasında hata oluştu.",
  missing_poses: "Takip için poz verisi bulunamadı.",
  missing_tracking_prep: "Takip hazırlığı bulunamadı.",
  missing_tracking: "Kimlik takibi sonucu bulunamadı; dövüşçüleri yeniden seçin.",
  missing_events: "Olay analizi sonucu bulunamadı; hareket analizini yeniden çalıştırın.",
  // model_missing: the server message names the download command, so it is shown as is.
  invalid_selection: "Seçilen kişi bu karede bulunamadı.",
  invalid_export: "Dışa aktarma kaydı eksik ya da bozuk.",
  export_source_missing: "Analiz sonuçları önbellekte bulunamadı; analizi yeniden çalıştırıp tekrar deneyin.",
  encode_failed: "Video dosyası yazılamadı (FFmpeg hatası).",
  export_not_ready: "Dışa aktarmak için analiz tamamlanmış olmalı.",
};

/** Processing steps shown to the user and the backend stages they cover.
 * Fighter selection is a user step between pose detection and tracking. */
export type StepId = "prep" | "pose" | "select" | "motion" | "results";

export const PROCESS_STEPS: readonly { id: StepId; label: string; stages: PipelineStage[] }[] = [
  { id: "prep", label: "Video hazırlama", stages: ["video_prep"] },
  { id: "pose", label: "Poz tespiti", stages: ["pose", "tracking_prep"] },
  { id: "select", label: "Dövüşçü seçimi", stages: [] },
  { id: "motion", label: "Hareket analizi", stages: ["tracking", "events", "scoring"] },
  { id: "results", label: "Sonuç hazırlama", stages: ["export"] },
];

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" });
}

export function formatBytes(bytes: number): string {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = bytes;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toLocaleString("tr-TR", { maximumFractionDigits: i === 0 ? 0 : 1 })} ${units[i]}`;
}

/** Screen a job should open on from the history list. */
export function jobScreen(job: Job): "processing" | "result" {
  return job.status === "completed" ? "result" : "processing";
}

const nf = (digits: number) => new Intl.NumberFormat("tr-TR", { maximumFractionDigits: digits });

export function formatNumber(value: number, digits = 0): string {
  return nf(digits).format(value);
}

/** "42 sn", "3 dk 05 sn", "1 sa 02 dk". */
export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} sn`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} dk ${String(s % 60).padStart(2, "0")} sn`;
  return `${Math.floor(m / 60)} sa ${String(m % 60).padStart(2, "0")} dk`;
}
