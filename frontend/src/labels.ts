// All interface texts (Turkish). Components keep no text of their own; texts of
// components not reworked yet move here when they are touched.
import type { Screen } from "./app/router";
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
  /** Accessible name of the "?" next to a metric or term. */
  help: (term: string) => `${term}: açıklama`,
} as const;

/** Top bar. */
export const SHELL_LABELS = {
  brand: "Fight Analyzer",
  home: "Fight Analyzer, yükleme ekranı",
  stepsLabel: "Ekranlar",
  steps: { upload: "Yükleme", processing: "İşlem", select: "Seçim", result: "Sonuç" } satisfies Record<Screen, string>,
  stepDisabled: "Önce bir analiz seç veya video yükle",
  stepDone: "tamamlandı",
  modeLabel: "Mod",
  modeAnalysis: "Analiz",
  modeDemo: "Demo",
  system: { pending: "Bağlanıyor", bad: "API'ye ulaşılamıyor", ok: "Sistem hazır", warn: "Sistemde sorun var" },
  systemTitle: "Sistem durumu",
} as const;

export const UPLOAD_LABELS = {
  title: "Maç videosunu yükle",
  lead: "Kayıtlı bir maçı yükle, iki dövüşçüyü seç; iskeletler, hareket istatistikleri ve olay zaman çizelgesi videoyla eş zamanlı görünsün.",
  /** The three notes of the intro band. */
  notes: {
    local: "Bilgisayarında işlenir",
    offline: "İnternet gerekmez",
    private: "Video dışarı çıkmaz",
  },
  /** "Nasıl çalışır" strip under the drop area. */
  how: {
    title: "Nasıl çalışır",
    description: "Videodan sonuca dört adım; hepsi bu bilgisayarda.",
    step: (n: number) => `${n}. adım`,
    upload: { title: "Yükle", text: "Kayıtlı maç videosunu seç ya da sürükleyip bırak." },
    process: { title: "İşlenir", text: "Her karede görünen kişilerin iskelet noktaları çıkarılır." },
    select: { title: "Dövüşçüleri seç", text: "Kırmızı ve mavi köşedeki dövüşçüleri işaretle." },
    result: { title: "Sonuç ve hakem kartları", text: "Olaylar, istatistikler ve AI tahmini hakem kartları açılır." },
  },
  dropLead: "Videoyu buraya sürükleyip bırak",
  chooseFile: "Dosya seç",
  formats: "MP4, MOV, MKV, WEBM, AVI",
  limits: (size: string, minutes: string) => `en fazla ${size} · ${minutes} dk`,
  size: "Boyut",
  duration: "Süre",
  resolution: "Çözünürlük",
  reading: "okunuyor…",
  metaUnreadable: "Tarayıcı bu dosyanın bilgilerini okuyamadı; sunucu FFmpeg ile yine de doğrulayacak.",
  start: "Analizi başlat",
  otherFile: "Başka dosya",
  cancelUpload: "Yüklemeyi iptal et",
  uploadProgress: "Yükleme ilerlemesi",
  verifying: "sunucu doğruluyor…",
  tooLarge: (limit: string) => `Dosya ${limit} sınırını aşıyor.`,
  tooLong: (minutes: string) => `Video çok uzun (sınır ${minutes} dk).`,
  tooShort: (seconds: string) => `Video çok kısa (en az ${seconds} sn).`,
  resolutionTooHigh: (long: number, short: number) => `Çözünürlük çok yüksek (sınır ${long}×${short}).`,
  resolutionTooLow: (short: number) => `Çözünürlük çok düşük (kısa kenar en az ${short} px).`,
  notVideo: (name: string, formats: string) =>
    `“${name}” bir video dosyası gibi görünmüyor. Desteklenen biçimler: ${formats}.`,
  emptyFile: "Dosya boş görünüyor.",
  overMax: "Dosya 20 GB sınırını aşıyor.",
  demoLead: "Demo modunda dosya yüklenmez",
  demoHint: "Sentetik bir örnek sahneyle işlem, seçim ve sonuç ekranlarının tamamını incele.",
  demoStart: "Demo analizini başlat",
} as const;

export const HISTORY_LABELS = {
  title: "Geçmiş analizler",
  description: "Daha önce analiz ettiğin maçlar; yeniden işlemeden açılır.",
  count: (total: string) => `${total} analiz`,
  events: (count: string) => `${count} olay`,
  open: "Aç",
  openNamed: (name: string) => `Aç: ${name}`,
  loading: "Geçmiş analizler yükleniyor",
  errorTitle: "Geçmiş analizler alınamadı",
  errorBefore: "API'ye ulaşılamıyor. Uygulamayı",
  errorAfter: "ile başlattığından emin ol; bağlantı otomatik olarak yeniden denenecek.",
  emptyTitle: "Henüz analiz yok",
  emptyText: "Yukarıdan bir maç videosu yüklediğinde analiz burada listelenir. Tamamlanan analizler yeniden işlenmeden açılır.",
  stale: "Bağlantı kesildi; son bilinen liste gösteriliyor.",
  untitled: (id: string) => `Analiz ${id}`,
  noVideoInfo: "Video bilgisi yok",
  posesReady: (frames: string) => `${frames} kare · pozlar hazır`,
  progress: "İlerleme",
  demoName: "Örnek maç",
  demoMeta: "Sentetik sahne",
  demoRunning: "Demo işleniyor",
} as const;

export const PROCESSING_LABELS = {
  previewTitle: "İşlenen kare",
  previewDescription: "Analiz sürerken üzerinde çalışılan kare.",
  previewPoses: "Poz önizleme · tüm kişiler",
  previewPosesDescription: "Bulunan herkesin iskeleti; dövüşçüler henüz seçilmedi.",
  stepsLabel: "Analiz aşamaları",
  panelDescription: "Analiz aşamaları ve toplam ilerleme",
  overall: "Toplam ilerleme",
  overallHelp: "Bütün aşamaların birlikte ne kadar ilerlediğini gösterir; her aşamanın toplamdaki payı farklıdır.",
  eta: "Tahmini kalan süre",
  etaHelp: "Yalnızca şu an süren aşama için, ölçülen hızdan hesaplanır; sonraki aşamaları kapsamaz.",
  etaStage: (stage: string) => `${stage} aşaması için`,
  etaUnknown: "Hesaplanıyor…",
  stale: "Bağlantı kesildi; son bilinen durum gösteriliyor.",
  queued: "Analiz sırada; işçi boşaldığında başlayacak.",
  videoInfo: "Video bilgileri",
  status: { waiting: "Bekliyor", active: "Sürüyor", done: "Tamamlandı", error: "Hata", stopped: "İptal edildi", action: "Seni bekliyor" },
  running: {
    video_prep: "Video analiz kopyasına dönüştürülüyor…",
    pose: "Poz modeli hazırlanıyor…",
    tracking_prep: "Kamera kesimleri ve iz parçaları hazırlanıyor…",
    tracking: "Dövüşçü kimlikleri video boyunca eşleniyor…",
    events: "Hareketler ve olaylar ölçülüyor…",
    scoring: "Deneysel momentum hesaplanıyor…",
    export: "Dışa aktarılıyor…",
  } satisfies Record<PipelineStage, string>,
  queuedPreview: "Analiz sırada bekliyor.",
  cancelledPreview: "Analiz iptal edildi.",
  failedPreview: "Analiz tamamlanamadı.",
  noPreview: "Önizleme yok.",
  preparing: "Video hazırlanıyor…",
  meta: { status: "Durum", source: "Kaynak", sourceVideo: "Kaynak video", analysisCopy: "Analiz kopyası", model: "Model", video: "Video", duration: "Süre" },
  rotated: (deg: number) => ` · ${deg}° döndürüldü`,
  withAudio: " · sesli",
  silent: " · sessiz",
  constantFps: (num: number | null, den: number | null) => `${num ?? "?"}/${den ?? "?"} fps sabit`,
  frames: (n: string) => `${n} kare`,
  frameOf: (n: string, total: string) => `Kare ${n} / ${total}`,
  untitled: (id: string) => `Analiz ${id}`,
  openResults: "Sonuçları aç",
  selectFighters: "Dövüşçüleri seç",
  prepareCandidates: "Aday kareleri hazırla",
  reselect: "Yeniden seç",
  restart: "Analizi yeniden başlat",
  cancel: "İptal",
  uploadScreen: "Yükleme ekranı",
  newUpload: "Yeni video yükle",
  cancelTitle: "Analiz iptal edilsin mi?",
  cancelBody: "Analiz bu aşamada durdurulur. İstediğinde yeniden başlatabilirsin.",
  cancelKeep: "Vazgeç",
  cancelConfirm: "Analizi iptal et",
  cancelled: "Analiz iptal edildi.",
  restartFailed: (message: string) => `Analiz yeniden başlatılamadı: ${message}`,
  loading: "Analiz bilgisi yükleniyor…",
  notFoundTitle: "Analiz bulunamadı",
  notFoundText: "kimlikli bir analiz kaydı yok.",
  unreachableTitle: "Analiz durumu alınamadı",
  unreachableText: "API'ye ulaşılamıyor; bağlantı otomatik olarak yeniden denenecek.",
  demoNotStartedTitle: "Demo analizi henüz başlatılmadı",
  demoNotStartedText: "Örnek sahne üzerinde işlem adımlarının nasıl ilerlediğini izle.",
  demoStart: "Demo analizini başlat",
  demoRestart: "Demo'yu baştan başlat",
  demoSource: "Sentetik demo sahnesi",
  demoPreview: "İşlenen kare önizlemesi (demo)",
  // pose review player
  framePrev: "‹ Kare",
  frameNext: "Kare ›",
  people: (n: number) => `${n} kişi`,
  loadingShort: "yükleniyor…",
  layers: "Katmanlar",
  skeleton: "İskelet",
  boxes: "Kutular",
  posesFailed: (message: string) => `Poz verisi alınamadı: ${message}`,
  previewFrame: (frame: string, people: number) => `Kare ${frame} · ${people} kişi`,
} as const;

/** Step details on the processing screen (features/processing/steps.ts). */
export const STEP_LABELS = {
  demoPrepDone: "H.264 · sabit 30 fps",
  demoPrepActive: "Video dönüştürülüyor",
  demoPoseFrames: (n: string) => `${n} kare işlendi`,
  demoSelected: "İki dövüşçü seçildi",
  demoSelect: "Kırmızı ve mavi dövüşçüyü seç",
  demoMotion: "Takip, olaylar ve sinyaller",
  demoResults: "Zaman çizelgesi ve istatistikler",
  frames: (done: string, total: string | null) => `${done}${total !== null ? ` / ${total}` : ""} kare`,
  framesPerSecond: (rate: string) => `${rate} kare/sn`,
  seconds: (done: string, total: string | null) => `${done}${total !== null ? ` / ${total}` : ""} sn video`,
  speed: (rate: string) => `${rate}× hız`,
  bytes: (done: string, total: string | null) => `${done}${total !== null ? ` / ${total}` : ""}`,
  fromCache: " · önbellekten",
  prepDone: (w: number, h: number, fps: string, frames: string) => `${w}×${h} · ${fps} fps · ${frames} kare`,
  poseDone: (detections: string, maxPersons: number) => `${detections} kişi tespiti · en fazla ${maxPersons} kişi/kare`,
  prepSummary: (cuts: number, candidates: number) => ` · ${cuts} kamera kesimi · ${candidates} aday kare`,
  anchors: (n: number) => `${n} seçim noktası`,
  trackingDone: (red: string, blue: string, switches: number) =>
    `Kimlik takibi: belirsiz ${red} / ${blue} · olası kimlik değişimi ${switches}`,
  eventsDone: (events: number, cameraPct: number) => ` · ${events} olay · kamera hareketi karelerin %${cameraPct}'inde ölçüldü`,
  momentumReady: (n: number) => `Deneysel momentum hazır · ${n} puan kaydı`,
  trackingReady: "Takip sonuçları hazır",
  awaitingSelection: "Pozlar hazır. Kırmızı ve mavi köşedeki dövüşçüleri seç.",
  stopped: "Analiz bu aşamada durdu.",
  cancelledByUser: "Kullanıcı iptal etti; yeniden başlatılabilir.",
} as const;

export const SELECTION_LABELS = {
  title: "Dövüşçüleri seç",
  /** Numbered guide across the top of the screen. */
  guide: {
    label: "Seçim adımları",
    steps: {
      red: { title: "Kırmızı köşeyi seç", hint: "Karede ya da alttaki kutularda dövüşçüye tıkla." },
      blue: { title: "Mavi köşeyi seç", hint: "Karede ya da alttaki kutularda dövüşçüye tıkla." },
      confirm: { title: "Adları kontrol et ve onayla", hint: "Adı düzeltmek için kalem simgesine tıkla." },
    },
    state: { done: "Tamamlandı", active: "Şimdi", upcoming: "Sırada" },
  },
  candidateLabel: "Aday kare",
  prevCandidate: "Önceki aday kare",
  nextCandidate: "Sonraki aday kare",
  candidateOf: (i: number, n: number, time: string) => `Aday ${i} / ${n} · ${time}`,
  frameAt: (frame: string, time: string) => `Kare ${frame} · ${time}`,
  frameStep: (n: number) => `${n > 0 ? "+" : ""}${n} kare`,
  hint: "Dövüşçülerin net göründüğü bir kare seç. Hakem ve seyirciler seçilmemeli; seçimi kaldırmak için yeniden tıkla.",
  peopleTitle: "Bu karedeki kişiler",
  peopleDescription: "Soldan sağa numaralı. Yüzde, tespit güvenidir.",
  confidenceTerm: "Tespit güveni",
  confidenceHelp: "Poz modelinin bu kutuda bir kişi bulunduğuna duyduğu güven. Kişinin kim olduğunu ya da dövüşçü olup olmadığını göstermez.",
  cornersTitle: "Köşeler",
  cornersDescription: "Kimin hangi köşede olduğunu belirle.",
  person: (n: number) => `Kişi ${n}`,
  personAria: (name: string, confidence: number, side: string | null) =>
    `${name}, tespit güveni yüzde ${confidence}${side ? `, ${side} köşe olarak seçildi; kaldırmak için tıkla` : ""}`,
  cornersLabel: "Köşeler",
  corner: (side: string) => `${side} köşe`,
  stateAbsent: "Bu karede görüntüde yok",
  stateChosen: (person: string) => `Seçildi: ${person}`,
  stateActive: "Karede ya da aşağıda dövüşçüye tıkla",
  stateNext: "Sırada",
  notInView: "Bu karede görünmüyor",
  undo: "Geri al",
  nameLabel: (corner: string) => `${corner} köşe adı`,
  editName: (corner: string, name: string) => `${corner} köşe adı: ${name}. Düzenlemek için tıkla`,
  confirm: "Onayla ve takibi başlat",
  confirmCorrection: "Düzeltmeyi ekle ve yeniden eşle",
  confirmDemo: "Onayla ve devam et",
  sending: "Gönderiliyor…",
  reset: "Seçimi sıfırla",
  keepEarlier: "Önceki seçimleri koru (düzeltme olarak ekle)",
  peopleLoading: "Kişiler yükleniyor…",
  noPeople: "Bu karede kişi tespit edilmedi",
  refereePicked: "Bu demo sahnesinde seçtiğin kişilerden biri hakem. Demo sonuçları yalnızca iki dövüşçü için üretilir; lütfen dövüşçüleri seç.",
  demoStage: "Aday kare (demo)",
  // states of the screen
  loading: "Analiz bilgisi yükleniyor…",
  notFound: "Analiz bulunamadı",
  unreachableTitle: "Analiz durumu alınamadı",
  unreachableText: "API'ye ulaşılamıyor; yeniden deneniyor.",
  processingTitle: "Analiz işleniyor",
  processingText: "Seçim, poz tespiti ve takip hazırlığı bittiğinde yapılabilir.",
  openProcessing: "İşlem ekranını aç",
  noPosesTitle: "Seçim için poz verisi yok",
  noPosesText: "Bu analizde poz tespiti tamamlanmamış.",
  noCandidatesTitle: "Aday kareler hazırlanmamış",
  noCandidatesText: "Bu analiz, takip hazırlığı eklenmeden önce yapılmış. Önbellekteki pozlar kullanılarak hızlıca hazırlanabilir.",
  prepareCandidates: "Aday kareleri hazırla",
  candidatesFailed: "Aday kareler alınamadı",
  candidatesLoading: "Aday kareler yükleniyor…",
  defaultNames: { red: "Dövüşçü 1", blue: "Dövüşçü 2" } satisfies Record<Side, string>,
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

/**
 * What each step does, one line under its name. Written from the pipeline
 * (backend/fight_analyzer/pipeline): "results" has no stage of its own in an
 * analysis, so its line only says what opens; momentum is called experimental
 * and never scoring.
 */
export const PROCESS_STEP_DESCRIPTIONS: Record<StepId, string> = {
  prep: "Video, analiz için sabit kare hızlı bir kopyaya dönüştürülüyor.",
  pose: "Her karede görünen herkesin iskelet noktaları bulunuyor; ardından kamera kesimleri ve aday kareler hazırlanıyor.",
  select: "Kırmızı ve mavi köşedeki dövüşçüleri sen işaretlersin; analiz bu seçimle sürer.",
  motion: "Seçilen dövüşçüler video boyunca izleniyor; olaylar ve deneysel momentum hesaplanıyor.",
  results: "Zaman çizelgesi, istatistikler ve hakem kartları sonuç ekranında açılır.",
};

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
