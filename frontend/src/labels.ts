// All interface texts (Turkish). Components keep no text of their own; texts of
// components not reworked yet move here when they are touched.
import type { Screen } from "./app/router";
import type {
  BroadcastNoteCode,
  EventType,
  FinishMethod,
  Job,
  JobStatus,
  PipelineStage,
  RoundNoteCode,
  RoundSource,
} from "./contracts/generated";
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
  // steps before the open screen get a check mark; the shell does not know the job's real state
  stepDone: "önceki adım",
  modeLabel: "Mod",
  modeAnalysis: "Analiz",
  modeDemo: "Demo",
  system: { pending: "Bağlanıyor", bad: "API'ye ulaşılamıyor", ok: "Sistem hazır", warn: "Sistemde sorun var" },
  systemTitle: "Sistem durumu",
  /** Theme menu in the top bar. */
  theme: {
    menu: "Tema",
    button: (current: string) => `Tema: ${current}`,
    light: "Açık",
    dark: "Koyu",
    system: "Sistem",
    /** The computer's own setting, shown next to "Sistem". */
    now: { light: "şu an açık", dark: "şu an koyu" },
  },
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
    // the demo result has no scorecards
    resultDemo: { title: "Sonuç", text: "Olaylar, istatistikler ve zaman çizelgesi açılır." },
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
    broadcast: "Scorebug'daki saat ve raunt sınırları okunuyor…",
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
  roundsSummary: (rounds: number, fromClock: boolean) =>
    rounds === 0 ? " · raunt bulunamadı" : ` · ${rounds} raunt bulundu${fromClock ? " (saatten)" : ""}`,
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
  broadcast: "Raunt tespiti",
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

/**
 * Result screen: fighter card, side panels, momentum card, export tab. The
 * "help" texts are the "?" explanations; each one is written from the
 * computation it describes (backend/fight_analyzer/motion and tracking,
 * model/measured.ts) and says what the number does not show.
 */
export const RESULT_LABELS = {
  header: {
    region: "Dövüşçüler ve momentum",
    corner: (side: string) => `${side} köşe`,
    rename: (side: string) => `${side} köşe adını değiştir`,
    renameTitle: "Adı değiştir",
    nameInput: (side: string) => `${side} köşe dövüşçü adı`,
    swap: "Tarafları değiştir",
    reselect: "Dövüşçüleri yeniden seç",
    export: "Dışa aktar",
  },
  momentum: {
    title: "Momentum",
    help: "Vuruş denemeleri, rakibe doğru ilerleme, tahmini yer kontrolü ve olası büyük olaylardan toplanan, zamanla sönen puanların iki köşe arasındaki payıdır. Deneysel bir göstergedir; kazanma olasılığı ya da hakem puanı değildir.",
    experimental: "Deneysel",
    excluded: "Dışlanan bölüm",
    excludedHelp: "Bu an dışlanan bir bölümde (ör. tekrar): olay sayılmaz, momentum donar.",
    insufficient: "Veri yetersiz",
    insufficientHelp: "Bu anda dövüşçülerden en az biri ölçülemiyor; yeni olay üretilmiyor.",
    meter: "Momentum, kırmızı köşe payı",
    noData: "Veri yok",
    shares: (red: number, blue: number) => `Kırmızı %${red}, mavi %${blue}`,
    caption: "Deneysel momentum — kazanma olasılığı değildir",
  },
  stats: {
    region: (side: string) => `${side} köşe istatistikleri`,
    empty: "Ölçüm verisi yok",
    loading: "Ölçüm verisi yükleniyor…",
    noMotion: "Hareket analizi yapılmadı",
    interval: (until: string) => `Bu değerler 00:00 – ${until} arası içindir`,
    groups: { striking: "Vuruş", movement: "Hareket ve baskı", control: "Kontrol", quality: "Veri kalitesi" },
    outOf100: "/100",
    percent: "%",
    strikeAttempts: {
      label: "Vuruş denemeleri",
      help: "Bu ana kadar tespit edilen yumruk ve diz denemelerinin sayısı; tekmeler ayrı sayılır. Deneme, vuruşun isabet ettiği anlamına gelmez.",
    },
    kicks: {
      label: "Tekmeler",
      help: "Bu ana kadar tespit edilen tekme denemelerinin sayısı. Deneme, tekmenin isabet ettiği anlamına gelmez.",
    },
    activity: {
      label: "Aktivite",
      help: "El ve ayak bileklerinin gövdeye göre ortalama hızından türetilen 0–100 arası hareketlilik endeksi; bu ana kadarki ortalamadır. İsabet ya da etki ölçmez.",
    },
    pressure: {
      label: "Baskı",
      help: "İki dövüşçü de ayaktayken ölçülebilen sürenin yüzde kaçında bu dövüşçünün rakibine doğru ilerlediğini gösterir.",
    },
    advanceRetreat: {
      label: "İlerleme / geri çekilme",
      help: "Dövüşçünün rakibe yaklaştığı ya da ondan uzaklaştığı sürenin yüzde kaçında ilerlediğini, kaçında geri çekildiğini gösterir. Yerinde durduğu süre sayılmaz.",
    },
    controlTime: {
      label: "Tahmini kontrol süresi",
      help: "Rakip yerdeyken bu dövüşçünün ona yakın ve üstünde göründüğü toplam süre. Yalnızca duruş ve yakınlıktan çıkarılan bir tahmindir; gerçek pozisyon kontrolünü doğrulamaz.",
    },
    majorEvents: {
      label: "Olası büyük olaylar",
      help: "Bu dövüşçüye yazılan olası knockdown ve olası takedown sayısı. Duruş ve konum değişiminden çıkarılır; doğrulanmış değildir ve düşük güvenli olanlar da sayıya dahildir.",
    },
  },
  quality: {
    scope: "Durum ve ölçülebilen süre şu ana kadar; diğer satırlar tüm video içindir.",
    stateTerm: "Kimlik durumu",
    state: { tracked: "Takipte", occluded: "Örtüşme", uncertain: "Takip belirsiz" },
    stateHelp: "Takipte: kimlik bu karede doğrulandı. Örtüşme: dövüşçü başka biriyle üst üste ya da kısa süre görünmüyor; kimlik önceki karelerden taşınıyor. Takip belirsiz: kimlik doğrulanamadı; tahmin edilmez ve ölçüm yapılmaz.",
    measured: {
      label: "Ölçülebilen süre",
      help: "Bu ana kadar dövüşçünün kimliğinin doğrulandığı ve vücudunun yeterince göründüğü toplam süre. Bunun dışındaki sürede ölçüm yapılmaz ve olay üretilmez.",
    },
    tracked: {
      label: "Takipte",
      help: "Tüm videodaki karelerin yüzde kaçında bu dövüşçünün kimliği doğrulanmış olarak izlendi.",
    },
    occluded: {
      label: "Örtüşme",
      help: "Tüm videodaki karelerin yüzde kaçında dövüşçü başka biriyle üst üste bindi ya da kısa süre (1 saniyeden az) görünmedi. Bu karelerde kimlik önceki karelerden taşınır.",
    },
    uncertain: {
      label: "Belirsiz",
      help: "Tüm videoda bu dövüşçünün kimliğinin doğrulanamadığı toplam süre. Bu sürede kimlik tahmin edilmez ve ölçüm yapılmaz.",
    },
    longestUncertain: {
      label: "En uzun belirsiz",
      help: "Kimliğin kesintisiz olarak doğrulanamadığı en uzun aralığın süresi.",
    },
    reacquisitions: {
      label: "Yeniden bulma",
      help: "Dövüşçünün bir kamera kesiminden ya da 1 saniyeden uzun bir kayıptan sonra yeniden tanındığı durumların sayısı. İleri ve geri takip geçişleri toplanır; birden fazla seçim noktası varsa aynı durum iki kez sayılabilir.",
    },
    trackChanges: {
      label: "Geçici numara değişimi",
      help: "İzleyicinin bu dövüşçüye verdiği geçici iz numarasının kaç kez değiştiği. Kimliğin değiştiği anlamına gelmez; kimlik her seferinde yeniden eşlenir. İleri ve geri takip geçişleri toplanır.",
    },
  },
  /** The momentum card of the "Olaylar ve momentum" tab. */
  mpanel: {
    region: "Momentum açıklaması",
    title: "Momentum",
    intro: (halfLife: string) =>
      `Momentum; vuruş denemeleri, ilerleme, tahmini yer kontrolü ve olası büyük olaylardan toplanan, her ${halfLife} saniyede yarıya inen puanların iki köşe arasındaki payını gösteren deneysel bir göstergedir; kazanma olasılığı ya da hakem puanı değildir.`,
    now: "Şu an",
    points: "puan",
    howTitle: "Nasıl hesaplanır?",
    formula: (prior: string, twicePrior: string, halfLife: string) =>
      `Kırmızı payı = 100 × (m₁ + ${prior}) / (m₁ + m₂ + ${twicePrior}), mavi = 100 − kırmızı. m₁ ve m₂ iki köşenin şu anki puan toplamıdır; her puan ${halfLife} saniyede yarıya iner.`,
    paramsTitle: "Model parametreleri (başlangıç tasarım değerleri; doğrulanmış ağırlıklar değildir)",
    params: {
      strike_attempt: "Vuruş denemesi (yumruk, diz)",
      kick_attempt: "Tekme denemesi (ayrıca yumruk sayılmaz)",
      contact_bonus: "Olası temas eki",
      advance_per_s: "İlerleme (saniye başına)",
      control_per_s: "Tahmini yer kontrolü (saniye başına)",
      knockdown: "Olası knockdown",
      takedown: "Olası takedown",
      min_major_confidence: "Büyük olay için en düşük güven",
      half_life_s: "Yarı ömür",
      prior: "Başlangıç payı (iki tarafa)",
    },
    seconds: "sn",
    noPoints: "Henüz puan yok",
    source: "Kaynak",
    earned: "Kazanılan",
    current: "Şu an",
    columnsTerm: "Kazanılan ve şu an",
    columnsHelp: "Kazanılan: bu kaynaktan şu ana kadar toplanan puan. Şu an: aynı puanların zamanla sönmüş güncel değeri.",
    pickEvent: "Olay listesinden bir olay seç: bu olayın puanı ve şu anki etkisi burada açıklanır.",
    possibleContact: "Olası temas",
    belowThreshold: (confidence: number, threshold: number) =>
      `Puan yok: kanıt yeterli değil (güven %${confidence}, eşik %${threshold}).`,
    noPointsType: "Bu olay momentum puanı üretmez.",
    // the effect sentence is assembled around bold numbers
    totalFor: (name: string) => `${name} için toplam`,
    atEvent: (name: string) => `puan. Olay anında ${name} payını`,
    raised: "yüzde puan artırdı.",
    nowValue: (time: string) => `Şu an (${time}) değeri`,
    affects: "puan; payı",
    affectsEnd: "yüzde puan etkiliyor.",
    notReached: "Oynatma henüz bu olaya gelmedi.",
    /** Measures the detector stored with an event; unknown keys show as they are. */
    measures: {
      peak_speed: "Tepe hız (gövde boyu/sn)",
      extension: "Rakibe uzanma (uzuv boyu)",
      toward: "Rakibe yönelim (kosinüs)",
      distance: "Mesafe (gövde boyu)",
      duration_s: "Süre (sn)",
      raise: "Ayak yüksekliği (gövde boyu)",
      knee_height: "Diz yüksekliği (gövde boyu)",
      seconds: "Süre (sn)",
      fall_s: "Düşüş süresi (sn)",
      strike_before_s: "Vuruştan sonra (sn)",
      possible_contact: "Öncesinde olası temas",
      close_s: "Yakın temas (sn)",
      on_top_after: "Sonrasında üstte",
      head_jolt: "Rakibin baş hareketi (gövde boyu)",
      impact: "Olası etkili vuruş",
    } as Record<string, string>,
  },
  /** Real-analysis result screen (TrackingResult). */
  screen: {
    majorWarning: { knockdown: "Olası knockdown", takedown: "Olası takedown" } as Record<string, string>,
    posesLoading: "Poz verisi yükleniyor…",
    noMotionNote: "Bu analiz hareket ve olay analizi eklenmeden önce tamamlanmış.",
    runMotion: "Hareket analizini çalıştır",
    syncFallback: "Bu tarayıcıda kare geri çağrısı yok; çizimler video zamanından izleniyor (oynarken bir kare sapabilir).",
    others: "Diğer kişiler",
    othersTitle: "Diğer kişiler (O)",
    fullscreen: "Tam ekran",
    fullscreenTitle: "Tam ekran (F)",
    tabsLabel: "Sonuç ayrıntıları",
    tabs: { events: "Olaylar ve momentum", tracking: "Kimlik takibi", judging: "Hakem kartları (AI)", export: "Dışa aktar" },
    noEvents: "Bu videoda ölçülen olay yok.",
    noMotion: "Hareket analizi yapılmadı.",
  },
  export: {
    region: "Dışa aktarma",
    options: {
      skeleton: { label: "İskeletler", hint: "Kırmızı ve mavi köşenin eklem ve uzuvları" },
      effects: { label: "Olay efektleri", hint: "Vuruş vurgusu, olası temas halkası, olası knockdown/takedown uyarısı" },
      momentum: { label: "Momentum çubuğu", hint: "Üstte isimler ve deneysel momentum yüzdeleri" },
      counters: { label: "Sayaçlar", hint: "İsimlerin altında vuruş ve tekme denemeleri" },
      distance: { label: "Mesafe", hint: "Dövüşçüler arası mesafe çizgisi (gövde boyu)" },
      others: { label: "Diğer kişiler", hint: "Hakem ve seyirciler gri, ince çizgiyle" },
    },
    files: { video: "MP4 video", metrics: "Kare metrikleri (CSV)", bundle: "Olaylar ve ayarlar (JSON)" },
    outdated: "Önceki sonuçlardan",
    outdatedHelp: "Bu dosyalar, taraflar ya da seçim değişmeden önceki sonuçlardan üretildi.",
    cancel: "İptal",
    progress: "Dışa aktarma ilerlemesi",
    queued: "Sırada: işçi boşalınca başlar (önceki işler bitince).",
    remaining: (eta: string) => ` · kalan ~${eta}`,
    summary: (frames: number, events: number, redShare: string, hasAudio: boolean) =>
      `${frames} kare · ${events} olay · son karede kırmızı %${redShare} · ${hasAudio ? "ses korundu" : "kaynakta ses yok"}`,
    title: "Paylaşılabilir çıktı",
    lead: "Videonun analiz kopyası, seçilen göstergeler işlenerek MP4 olarak yazılır; ses varsa olduğu gibi korunur. Kare bazlı metrikler (CSV) ile olaylar, momentum kayıtları ve ayarlar (JSON) her zaman eklenir. Sayılar bu ekrandakiyle aynı analiz verisinden hesaplanır. Dosyalar bu bilgisayarda kalır.",
    optionsLegend: "Videoya işlenecekler",
    alwaysShown: "Kimlik örtüşmesi/belirsizliği ve “veri yetersiz” uyarıları seçeneklerden bağımsız olarak videoda gösterilir.",
    queueing: "Kuyruğa alınıyor…",
    start: "Dışa aktarmayı başlat",
    notReady: "Önce hareket analizi ve momentum tamamlanmalı.",
    listTitle: "Dışa aktarmalar",
    listLead: "Dışa aktarma ayrı bir iş olarak arka planda çalışır; bu sırada videoyu izlemeye devam edebilirsin.",
    loading: "Yükleniyor…",
    empty: "Henüz dışa aktarma yok.",
  },
} as const;

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
  { id: "pose", label: "Poz tespiti", stages: ["pose", "tracking_prep", "broadcast"] },
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
  pose: "Her karede görünen herkesin iskelet noktaları bulunuyor; ardından kamera kesimleri, aday kareler ve scorebug'daki raunt saati hazırlanıyor.",
  select: "Kırmızı ve mavi köşedeki dövüşçüleri sen işaretlersin; analiz bu seçimle sürer.",
  motion: "Seçilen dövüşçüler video boyunca izleniyor; olaylar ve deneysel momentum hesaplanıyor.",
  results: "Zaman çizelgesi, istatistikler ve AI tahmini hakem kartları sonuç ekranında açılır.",
};

/** Demo differs where its synthetic result has less to show (no scorecards). */
export const DEMO_STEP_DESCRIPTIONS: Record<StepId, string> = {
  ...PROCESS_STEP_DESCRIPTIONS,
  results: "Zaman çizelgesi ve istatistikler sonuç ekranında açılır.",
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

/**
 * "Maç ayarları" (v2 Bölüm 2): bout format, rounds found on the scorebug and
 * the names read there. Rounds and names are AI estimates from a broadcast
 * graphic; the user's entries always win.
 */
export const MATCH_LABELS = {
  title: "Maç ayarları",
  description: "Raunt sayısı ve videoda bulunan raunt sınırları; puanlama bunlara dayanır.",
  roundsLabel: "Raunt sayısı",
  roundsOption: (n: number) => `${n} raunt`,
  titleFight: "Şampiyonluk maçı",
  titleFightHint: "Açınca raunt sayısı 5 olur; istersen değiştirebilirsin.",
  saving: "Kaydediliyor…",
  found: "Bulunan raunt sınırları",
  none: "Henüz raunt bulunamadı.",
  pending: "Raunt bilgisi bu analizde yok; yeniden işleyince hazırlanır.",
  round: (n: number) => `R${n}`,
  source: {
    ocr: "scorebug saatinden",
    break: "raunt aralarından (düşük güven)",
    manual: "elle girildi",
  } satisfies Record<RoundSource, string>,
  sourceShort: { ocr: "oto", break: "oto", manual: "elle" } satisfies Record<RoundSource, string>,
  confidence: (pct: number) => `güven %${pct}`,
  partial: "kısmi",
  partialHelp: "Raunt videoda tam süresiyle yok: erken bitti (ör. nakavt) ya da kayıt raunt içinde başlıyor veya bitiyor.",
  clockEnd: (clock: string) => `bitişte kalan süre ${clock}`,
  aiNote: "AI tahmini: raunt sınırları yayın grafiğinden okunur; resmi zamanlama değildir.",
  notes: {
    ocr_unavailable: () => "OCR modeli kurulu değil, saat okunmadı. setup.cmd'yi çalıştır ya da raunt sınırlarını elle gir.",
    clock_not_found: () => "Ekranda saat bulunamadı. Saatin etrafına dikdörtgen çizebilir ya da sınırları elle girebilirsin.",
    roi_unreadable: () => "Çizdiğin alanda saat okunamadı; alanı saatin etrafına daha dar çiz.",
    no_rounds: () => "Saat okundu ama raunt uzunluğunda bir geri sayım bulunamadı.",
    round_number_inferred: (n: number | null) => `R${n ?? "?"}: raunt numarası okunamadı, sırasından çıkarıldı.`,
    rounds_from_breaks: () => "Saat okunamadı; rauntlar pozlardan bulunan raunt aralarından çıkarıldı (düşük güven).",
  } satisfies Record<BroadcastNoteCode, (n: number | null) => string>,
  roundNotes: {
    auto_conflicts_manual: (n: number, other: number | null) =>
      `Otomatik R${n}, elle girdiğin R${other ?? "?"} ile çakıştığı için kullanılmadı.`,
    beyond_scheduled: (n: number) => `Otomatik R${n}, planlanan raunt sayısının dışında kaldı.`,
    out_of_order: (n: number, other: number | null) =>
      `Otomatik R${n}, R${other ?? "?"} ile zaman sırası tutmadığı için kullanılmadı.`,
  } satisfies Record<RoundNoteCode, (n: number, other: number | null) => string>,
  roi: {
    fix: "Saat alanını düzelt",
    auto: "Saat alanı otomatik bulundu.",
    manual: "Saat alanını sen çizdin.",
    hint: "Videodaki saatin etrafına sürükleyerek dar bir dikdörtgen çiz. Klavyeyle: ok tuşları alanı kaydırır (Shift ile daha hızlı), Alt ile boyutunu değiştirir.",
    area: "Saat alanı",
    save: "Kaydet ve saati yeniden oku",
    cancel: "Vazgeç",
    reset: "Otomatiğe dön",
    rereading: "Saat yeniden okunuyor; seçimlerin korunur.",
  },
  names: {
    title: "Scorebug'da okunan adlar",
    read: (left: string | null, right: string | null) => `Sol: ${left ?? "—"} · Sağ: ${right ?? "—"}`,
    apply: "Öneriyi uygula",
    hint: "Yalnızca adı girilmemiş köşeye yazılır; soldaki ad kırmızı köşeye önerilir. Yazdığın bir adın üstüne yazılmaz.",
    nothing: "İki köşenin adı da girilmiş; öneri uygulanmaz.",
  },
  demo: "Demo: örnek raunt verisi; ayarlar kaydedilmez.",
};

/** Result screen: round boundaries on the timeline and the round list. */
export const ROUND_EDIT_LABELS = {
  handle: (n: number, edge: "start" | "end", at: string) =>
    `R${n} ${edge === "start" ? "başlangıcı" : "bitişi"}, ${at}. Ok tuşlarıyla kaydır (Shift ile 5 sn), Delete ile rauntu sil.`,
  add: "Raunt ekle (şu andan)",
  remove: (n: number) => `R${n} rauntunu sil`,
  revert: (n: number) => `R${n}: otomatiğe dön`,
  removed: (n: number) => `Otomatik R${n} kaldırıldı.`,
  noRoom: "Oynatma anında yeni raunt için yer yok (başka bir raunt var ya da raunt sayısı dolu).",
  help: "Sınırları zaman çizelgesinde sürükleyerek ya da tutamacı seçip ok tuşlarıyla düzeltebilirsin; dokunduğun raunt elle girilmiş sayılır ve otomatiği ezer.",
  saving: "Kaydediliyor…",
};

/** Banner on analyses made before the current version (CLAUDE.md: "eski sürümle yapıldı"). */
export const OUTDATED_LABELS = {
  title: "Bu analiz eski sürümle yapıldı — yeniden işle",
  text: "Raunt tespiti gibi yeni adımlar bu analizde yok. Pozlar önbellekten gelir; yeniden işleme birkaç dakika sürer.",
  action: "Yeniden işle",
  busy: "Yeniden işleme başlatılıyor…",
};

/** The result timeline (texts moved here when it got round editing). */
export const TIMELINE_LABELS = {
  region: "Zaman çizelgesi",
  slider: "Video konumu",
  legend: "Zaman çizelgesi işaretleri",
  punch: "Yumruk",
  kick: "Tekme",
  knee: "Diz",
  contact: "Olası temas",
  big: "Olası büyük olay",
  span: "Klinç / yer kontrolü",
  gap: "Veri yetersiz",
  excluded: "Dışlanan bölüm",
  roundAuto: "Raunt (otomatik)",
  roundManual: "Raunt (elle)",
  curve: "Eğri: deneysel momentum payı (üst kırmızı, alt mavi)",
  noMomentum: "Momentum verisi yok",
  axisTop: "%100 kırmızı",
  axisMid: "%50",
  axisBottom: "%100 mavi",
  roundTitle: (n: number, a: string, b: string, source: string) => `${n}. raunt ${a}–${b} · ${source}`,
  excludedTitle: (a: string, b: string) => `Dışlanan bölüm ${a}–${b}`,
};

/** "Maç bilgileri": how the bout ended and point deductions (texts moved here in Bölüm 2). */
export const MATCH_EDITOR_LABELS = {
  region: "Maç bilgileri",
  title: "Maç bilgileri",
  userInput: "Kullanıcı girdisi",
  help: "Bitiş şekli ve puan kesintileri videodan güvenilir biçimde çıkarılamaz; buraya girdiğin resmi bilgiler olduğu gibi kullanılır. Raunt sayısı Maç ayarlarından, raunt sınırları zaman çizelgesinden gelir.",
  rounds: "Rauntlar",
  notMarked: "bulunmadı",
  markRound: "Raunt",
  markStart: "Başlangıç = şimdiki kare",
  markEnd: "Bitiş = şimdiki kare",
  ending: "Maç nasıl bitti?",
  winner: "Kazanan",
  endRound: "Raunt",
  endTime: "Süre (dk:sn)",
  deductions: "Puan kesintileri",
  noDeductions: "yok",
  deductionRound: "Raunt",
  deductionFighter: "Dövüşçü",
  deductionPoints: "Puan",
  removeDeduction: "Kesintiyi kaldır",
  addDeduction: "Kesinti ekle",
  saving: "Kaydediliyor…",
  save: "Kaydet ve kartları yenile",
  cancel: "Vazgeç",
  finish: {
    unknown: "Bilinmiyor / girilmedi",
    decision: "Puan kararı (maç süresini tamamladı)",
    ko: "Nakavt (KO)",
    tko: "Teknik nakavt (TKO)",
    submission: "Submission",
    disqualification: "Diskalifiye",
    referee_stoppage: "Hakem / doktor durdurması",
    no_contest: "No contest",
  } satisfies Record<FinishMethod, string>,
};
