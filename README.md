# MMA Fight Analyzer

Kayıtlı MMA maç videolarını **yerelde** analiz eden tek kullanıcılı uygulama:
video yükleme, iki dövüşçü seçimi, video üzerinde renkli iskeletler, hareket
istatistikleri, deneysel momentum yüzdeleri ve olay zaman çizelgesi.

> **Mevcut durum: Aşama 9 – MMA hakemlik motoru (AI tahmini).** Unified Rules
> 10-Point Must ile raund bazında puanlama, üç sanal hakem, karar türleri ve
> güven seviyesi; bitişler (KO/TKO/submission/DQ/durdurma) kullanıcı girdisiyle,
> puan kararından ayrı (bkz. "AI hakemlik"). Resmi sonuç değildir.
> Aşama 8 – gerçek kliplerle doğrulama ve kullanıma hazırlık: Elle etiketli küçük örnekle doğrulama aracı ve raporu (bkz.
> "Doğrulama ve dayanıklılık"), tekrar/ağır çekim için bölüm dışlama,
> dayanıklılık ve yerel güvenlik sıkılaştırmaları, kısa kullanım kılavuzu
> ([docs/KULLANIM.md](docs/KULLANIM.md)). Aşama 7: videonun altında
> kırmızı/mavi momentum eğrisi ve olay işaretleri, filtrelenebilir olay listesi,
> video zamanına bağlı ölçülü efektler, iskelet + göstergeler işlenmiş MP4,
> kare bazlı CSV ve olay/ayar JSON'u. Önceki aşamalar: sonuç ekranında gerçek analiz verisi videoyla kare kare
> eşleşir (Canvas katmanı, `requestVideoFrameCallback`).
> Video yüklenir, analiz kopyasına dönüştürülür, herkesin pozu çıkarılır;
> kullanıcı kırmızı ve mavi dövüşçüyü seçer, kimlikler video boyunca korunur.
> Doğrulanmış dövüşçülerden kamera hareketi çıkarılmış hareket sinyalleri,
> vuruş/tekme denemeleri, olası temas, ilerleme/geri çekilme, sınırlı kontrol
> tahmini, olası knockdown/takedown ve her puanı açıklanabilen **deneysel**
> momentum üretilir. Tasarımın tamamı ayrıca
> **Demo** modunda gezilebilir; normal ekranlarda ölçülmemiş hiçbir değer
> gösterilmez.

## Hızlı başlangıç

Gereksinimler: Windows 10/11 x64, [Python 3.14](https://www.python.org/downloads/),
[Node.js](https://nodejs.org) ≥ 22.12.

```bash
start.cmd
```

- İlk çalıştırmada kurulum (`scripts/setup.ps1`) otomatik yapılır.
- API, analiz işçisi ve arayüz birlikte başlar; sağlık kontrolü `ok` olunca
  tarayıcı açılır. **Ctrl+C** hepsini düzgünce kapatır.
- Arayüz: <http://127.0.0.1:5173> · Sağlık: <http://127.0.0.1:8000/api/v1/health> ·
  API şeması: <http://127.0.0.1:8000/api/openapi.json> (Swagger sayfası kapalı: CDN'den
  betik yüklerdi)
- Kullanım kılavuzu: [docs/KULLANIM.md](docs/KULLANIM.md) (model indirme, çıktıların
  yeri, momentumun anlamı, bilinen sınırlamalar, sorun giderme).
- `start.cmd --no-browser` tarayıcı açmaz. Portlar doluysa başlatıcı bunu
  söyler; `FA_API_PORT` / `FA_WEB_PORT` ile değiştirilebilir.

Diğer komutlar: `setup.cmd` (kurulumu yeniden yap, örn. `setup.cmd -Torch cpu`),
`check.cmd` (tüm kontroller).

## Mimari

```
start.cmd → scripts/launch.py  (alt süreçleri bir Windows Job Object'e bağlar)
   ├─ API      uvicorn + FastAPI   127.0.0.1:8000   yalnızca iş durumunu okur/yazar
   ├─ Worker   python -m fight_analyzer.jobs         ağır analiz burada (ayrı süreç)
   └─ Web      Vite + React        127.0.0.1:5173   /api → API'ye proxy
                    API ⇄ data/jobs.sqlite3 (WAL) ⇄ Worker
```

Analiz ayrı bir süreçte çalıştığı için API, uzun video analizi sırasında da
yanıt verir. Bu, tüm CPU çekirdeklerini meşgul eden bir işle uçtan uca test
edilir (`backend/tests/test_responsiveness.py`).

### İş yaşam döngüsü

`queued → running → awaiting_selection → queued → running → completed` (her an `failed` / `cancelled`)

- İşçi kuyruktaki en eski işi tek bir atomik SQL ifadesiyle alır.
- İlerleme (aşama, 0–1 oran, mesaj) ve kalp atışı veritabanına yazılır.
- İptal: sıradaki iş hemen iptal olur; çalışan iş bir sonraki ilerleme
  bildiriminde durur.
- İşçi Ctrl+C/Ctrl+Break ile durursa çalışan iş kuyruğa geri döner.
  İşçi çökerse 30 sn kalp atışı gelmeyen iş yeniden kuyruğa alınır; 2 denemeden
  sonra `worker_lost` hatasıyla başarısız sayılır.
- Poz çıkarımı, takip hazırlığı ve yayın analizi (scorebug saati, rauntlar;
  `broadcast`) bitince iş `awaiting_selection` olur ve işçiyi serbest bırakır; bu durumdaki iş de iptal edilebilir. Seçim gönderilince
  iş yeniden kuyruğa girer; video, poz ve hazırlık önbellekten okunur; kimlik
  takibi, hareket/olay analizi ve momentum çalışır. Tamamlanmış işte yeniden
  seçim/düzeltme de aynı yolu izler.
- Veritabanı şeması `PRAGMA user_version` ile göç (migration) edilir.

### Klasörler

```
backend/fight_analyzer/
  contracts/   sürümlü veri sözleşmeleri (Pydantic) + JSON Schema dışa aktarımı
  api/         FastAPI uygulaması ve rotalar
  jobs/        store.py (SQLite iş kaydı), worker.py (arka plan işçisi)
  pipeline/    video_prep · pose · tracking_prep · tracking · events · scoring;
               export.py (dışa aktarma işi)
  tracking/    cuts.py (kesim), tracklets.py (OC-SORT parçaları), appearance.py,
               candidates.py, prep.py (önbellek), identity.py (kalıcı kimlik), results.py
  motion/      camera.py (kamera hareketi), kinematics.py (eklemler, ölçek, hız, duruş),
               events.py (sinyaller ve olaylar), momentum.py (puan defteri), store.py (önbellek)
  export/      frames.py (tarayıcıyla aynı kare değerleri ve efekt zamanları), render.py
               (MP4 çizimi), video.py (FFmpeg'e ham kare + ses kopyası), files.py (CSV/JSON)
  media/       probe.py (FFmpeg ile doğrulama), transcode.py, analysis_video.py (önbellekli kopya)
  pose/        models.py (resmi ağırlıklar + SHA-256), engine.py, cache.py, preview.py
  system/      compute.py (CPU/CUDA seçimi), ffmpeg.py (FFmpeg bulma)
backend/requirements/   sabitlenmiş Python bağımlılıkları ve tam kilit dosyası
backend/tests/          pytest testleri
frontend/src/
  app/         hash yönlendirici ve uygulama kabuğu (üst çubuk, adımlar, mod)
  features/    upload · processing · selection · result ekranları
  player/      oynatma saati, tuval sahnesi ve katman çizimleri
  demo/        Demo modunun sentetik sahnesi ve örnek verileri
  model/       ekran görünüm modelleri (null = ölçüm yok)
  contracts/   generated.ts (şemadan), overlayStyle.ts (stil dosyasından) üretilir
  styles/      tasarım belirteçleri ve ekran stilleri
shared/schemas/         fight-analyzer.v1.schema.json (tek doğruluk kaynağı)
shared/overlay-style.json  tarayıcı ve MP4 için renkler, eşik, uzuvlar, efekt süreleri
shared/fixtures/        frame-metrics.json (tarayıcı ↔ dışa aktarma ortak test dosyası)
validation/             labels/ (elle etiketler), reports/ (doğrulama raporları)
docs/KULLANIM.md        kısa kullanım kılavuzu
scripts/                launch.py, setup.ps1, check.ps1
data/                   çalışma verisi (git dışı):
  jobs.sqlite3            iş kaydı
  uploads/<sha256>/       yüklenen kaynak dosya (içerik adresli, tekrarlar tek kopya)
  cache/video/<anahtar>/  analysis.mp4 + video.json
  cache/pose/<anahtar>/   manifest.json + *.npy
  cache/tracking_prep/<anahtar>/  kesimler, iz parçaları, görünüm, aday kareler
  cache/identity/<anahtar>/       seçimlere göre kimlik sonucu
  cache/camera/<anahtar>/         kamera hareketi (video başına)
  cache/events/<anahtar>/         olaylar, hareket aralıkları, 10 Hz sinyaller
  cache/momentum/<anahtar>/       momentum defteri ve paylar
  jobs/<iş>/              canlı önizleme kareleri; dışa aktarmada overlay.mp4,
                          metrics.csv, analysis.json
  models/                 resmi pose ağırlıkları
```

## Ekranlar

| Ekran | Adres (Analiz / Demo) | İçerik |
|---|---|---|
| 1 Yükleme | `#/` · `#/demo` | Sürükle-bırak alanı, dosya seçme, yerel dosya doğrulama (tür, boyut, süre, çözünürlük tarayıcıda okunur), geçmiş analizler (16:9 önizleme karesi, tarih · çözünürlük · süre, durum rozeti) |
| 2 İşlem | `#/analyses/<id>/processing` · `#/demo/processing` | Solda işlenen kare önizlemesi; sağda dikey aşama listesi (durum ikonu, ilerleme), toplam ilerleme, o anki aşamanın tahmini kalan süresi ve onay penceresiyle "İptal" |
| 3 Seçim | `#/analyses/<id>/select[?frame=N&keep=1]` · `#/demo/select` | Analiz videosunun karesi üzerinde tıklanabilir kişi kutuları ve altında her kişinin büyük kırpılmış karesi (klavyeyle seçim de buradan); önce kırmızı, sonra mavi köşe; seçili aday köşe renginde çerçeve ve köşe rozeti alır; dövüşçü adları köşe satırlarında yerinde düzenlenir; aday kareler ve ±1/±10 kare adımları; düzeltmede önceki seçimleri koruma ve "Bu karede görünmüyor" |
| 4 Sonuç | `#/analyses/<id>/result` · `#/demo/result` | Üstte isimler ve deneysel momentum çubuğu ("kazanma olasılığı değildir"); ortada video ve kare kare eşleşen Canvas katmanı (iskeletler, olay efektleri, mesafe); iki yanda o ana kadarki ölçümler ve kimlik takibi özeti; videonun hemen altında oynatma ve kompakt zaman çizelgesi (momentum eğrisi, olay işaretleri, oynatma çizgisi); altta "Olaylar ve momentum", "Kimlik takibi" (takip şeritleri + kayıt) ve "Dışa aktar" sekmeleri |

- **Demo modu** (üst çubukta "Demo"): kalıcı DEMO şeridi, sahnede "DEMO · SENTETİK
  SAHNE" damgası ve panellerde DEMO etiketi. Örnek veriler `data_origin: "demo"`
  ile tiplenir; normal moda hiçbir zaman taşınmaz.
- **Normal mod**: gerçek iş durumları ve ölçümler API'den okunur; ölçülemeyen
  değerler "—" gösterir. Hareket analizinden önce tamamlanmış analizlerde
  "Hareket analizini çalıştır" düğmesi çıkar (önbellek sayesinde hızlıdır).
  Boş, yükleniyor, hata ve "bulunamadı" durumları her ekranda vardır.
- **Katmanlar**: İskelet, Olay efektleri, Mesafe ayrı ayrı açılıp kapanır.
- **Dışlanan bölümler**: giriş, raunt araları, maç sonrası, tekrarlar ve
  duraklamalar otomatik dışlanır ("otomatik" etiketi, neden, güven, dayanak;
  "Geri al" / "Yeniden dışla" tek tıkla). "Bölüm dışla…" ile elle de işaretlenir
  (bkz. "Yayın kesmeleri ve tekrar ayıklama").
- **Dövüşçüler**: ad değiştirme (kalem simgesi), "Tarafları değiştir",
  "Dövüşçüleri yeniden seç".
- **Klavye (Sonuç)**: Boşluk oynat/duraklat · ←/→ 1 sn (Shift ile 5 sn) ·
  `,` / `.` bir kare · S iskelet · E olay efektleri · D mesafe ·
  O diğer kişiler · F tam ekran (gerçek analiz; videoya çift tıklama da).
- **Görsel dil (v2, Bölüm 1)**: aydınlık sayfa üzerinde siyah-beyaz-kırmızı
  kimlik; tek kaynak `frontend/src/styles/tokens.css` (renk, yazı, boşluk, köşe
  yarıçapı, gölge, hareket). Siyah (`#0e0e10`): üst bar, koyu bantlar, ana
  butonlar, aktif sekme çizgisi. Tek kırmızı (`#d0142c`) hem marka hem kırmızı
  köşedir: logo, üst bardaki aktif adım, ilerleme çubukları, bölüm başlığı
  çizgileri, sürükle-bırak vurgusu, Yükleme ekranının giriş bandındaki not
  ikonları ve Yükleme ekranının ana eylemleri ("Dosya seç", "Analizi başlat",
  "Demo analizini başlat"; başka ekranda kırmızı buton yok). Siyah zeminde kırmızı
  yalnızca dolgu, çizgi ve ikondur, metin değil. Mavi (`#2457c5`) yalnızca mavi
  köşe verisinde. Seçim ve Sonuç ekranlarında kırmızı yalnızca kırmızı köşeyi
  anlatır; oralarda buton, sekme, çubuk ve bölüm çizgileri siyahtır. Durum
  renkleri (başarı, uyarı, hata) ayrıdır ve hata her zaman ikon ve metinle
  gösterilir. Kartlar beyaz, 1 px kenarlıklı ve çok hafif gölgeli; bölüm
  başlıkları tek satır açıklama, metrikler "?" ile açılan tanım taşır (tanımlar
  `frontend/src/labels.ts`). Arayüz **Inter**, başlıklar ve skor rakamları
  **Inter Tight** (yerel `@fontsource-variable` paketleri; internetten font
  yüklenmez); tüm sayılarda eşit genişlikli rakamlar. Video sahnesi koyu ve
  yuvarlak köşeli kalır; üzerindeki iskelet ve efektler canlı tonlardadır
  (kırmızı `#ff2e4d`, mavi `#3d8bff`, diğer kişiler gri; `shared/overlay-style.json`,
  MP4 dışa aktarmayla ortak). Ortak bileşenler `frontend/src/ui/`; bir test
  token dosyaları dışında renk kodu kalmadığını, bir test de metin
  kontrastının WCAG AA'yı geçtiğini denetler.
- **Tema**: üst bardaki menüden Açık · Koyu · Sistem (varsayılan Sistem;
  işletim sisteminin temasına uyar). Seçim tarayıcıda saklanır ve sayfa açılırken
  ilk boyamadan önce uygulanır. Koyu temada zemin `#0b0b0d`, kartlar `#151518`;
  kırmızı ve mavi yazılar açık tonlarda (`#ff6b7a`, `#7aa5ff`), beyaz yazılı
  kırmızı butonlar ve video sahnesi iki temada aynıdır. Kontrast testleri iki
  tema için çalışır.
- **Sayfa genişliği**: en fazla 1440 px ve 24 px kenar boşluğu; sonuç ekranı
  düzeni Bölüm 5'te yenilenene kadar 1640 px.
- **Duyarlı yerleşim**: ≥1100 px'de üç sütun (panel · video ve altında zaman
  çizelgesi · panel); daha dar ekranda video ve zaman çizelgesi üstte, paneller
  altta iki sütun; telefonda tek sütun.

## Video yükleme ve poz çıkarma

1. **Yükleme** (`POST /api/v1/jobs?filename=…`, gövde = ham dosya): akış halinde
   diske yazılır, SHA-256 hesaplanır, boyut sınırı anında uygulanır. Ardından
   FFmpeg başlığı okunur **ve ilk kareler gerçekten çözülür**; uzantısı doğru olsa
   bile video olmayan veya bozuk dosya reddedilir. Süre ve çözünürlük sınırları
   döndürme uygulanmış boyuta göre denetlenir. Hata yanıtları `{code, message}`
   biçimindedir ve arayüz Türkçe mesajı gösterir.
2. **Analiz kopyası** (`video_prep`): H.264 (B-kare yok) + AAC, `faststart` MP4.
   Döndürme uygulanır ve etiketi silinir, kare olmayan pikseller kareye
   çevrilir, en-boy oranı korunur, kısa kenar en fazla 1080 px, ses varsa korunur.
   Kare hızı **sabittir**: kaynağı tam bölen yaygın bir hız seçilir (59,94→29,97,
   50→25), yoksa kaynak hız ya da sınır (36,13 fps sosyal medya klibi→30).
   Motor ve tarayıcı **aynı dosyayı** kullanır; kare N her yerde N/fps anındadır
   (tarayıcıda `requestVideoFrameCallback` ile kare kare doğrulandı).
3. **Poz** (`pose`): resmi `yolo26s-pose.pt` (varsayılan), 640 px, güven ≥ 0,25,
   karede en fazla 20 kişi, 4'lü toplu çıkarım. Her kare için kare numarası,
   zaman damgası, kişi kutuları ve güveni, 17 eklemin x/y/güven değerleri
   kaydedilir. Bu aşamada kimlik atanmaz; hakem ve seyirciler de tespit
   edilir. Kimlikler seçimden sonra eklenir (bkz. "Dövüşçü seçimi ve kimlik
   takibi").
4. **Önbellek**: JSON manifest + NumPy `.npy` dizileri; pickle yok, yükleme
   `allow_pickle=False` ve dizi başına SHA-256 doğrulaması ile. Anahtar: analiz
   videosunun SHA-256'sı + model adı/ağırlık özeti/Ultralytics sürümü + analiz
   ayarları + şema sürümü. Aynı video tekrar yüklenince dönüştürme ve poz
   atlanır (10,9 sn'lik klipte 48 sn → 1,2 sn). Uygulama yeniden açıldığında
   işler ve pozlar önbellekten okunur.
5. **İlerleme**: dönüştürmede işlenen video saniyesi, pozda **gerçek işlenen kare
   sayısı**; hız ve tahmini süre ölçümden hesaplanır, tahmini süre yeterli ölçüm
   (≥ 10 kare ve ≥ 3 sn) olunca görünür. Önizleme ~1,5 sn'de bir kare (640 px JPEG
   + tespitler) olarak yazılır; her kare tarayıcıya gönderilmez.
6. **İptal / hata**: iptal bir sonraki ilerleme bildiriminde (pozda her 4 karede)
   işler; FFmpeg süreci öldürülür, yarım çıktılar önbelleğe yazılmaz. Hatalar
   kodlu iş hatası olarak (ör. `undecodable_video`, `model_unavailable`,
   `pose_failed`) arayüzde gösterilir.

**Poz modeli:** `scripts/setup.ps1` resmi `ultralytics/assets` v8.4.0
sürümünden indirir ve GitHub'ın yayımladığı SHA-256 ile doğrular
(`python -m fight_analyzer.pose.models [ad]`). Ağırlıklar `torch.load(weights_only=True)`
ile yüklenir (`ULTRALYTICS_SAFE_LOAD=1`). Bu makinedeki ölçüm (i5-12450H, CPU,
640 px): yolo26n-pose ~65 ms/kare, yolo26s-pose ~170 ms/kare; daha hızlı işlem
için `FA_POSE_MODEL=yolo26n-pose.pt`.

**API uç noktaları:** `GET /jobs` (yalnızca analizler) · `POST /jobs` (yükleme) ·
`POST /jobs/{id}/cancel` (analiz ya da dışa aktarma) ·
`GET /jobs/{id}/video` (Range destekli analiz kopyası) · `GET /jobs/{id}/preview`
ve `/preview.jpg?seq=` · `GET /jobs/{id}/thumbnail.jpg` (geçmiş listesi için 320 px
kare: seçim yapılan kare, yoksa videonun %10'u; iş klasöründe önbelleğe alınır)
· `GET /jobs/{id}/poses?start=&count=` (en fazla 600 kare)
· `GET /upload-limits` · `GET /jobs/{id}/candidates` (aday kareler) ·
`POST /jobs/{id}/selection` (seçim noktaları; takibi yeniden çalıştırır) ·
`PUT /jobs/{id}/names` · `POST /jobs/{id}/retry` · `GET /jobs/{id}/tracking/timeline` ·
`GET /jobs/{id}/events` (olaylar) · `GET /jobs/{id}/motion` (10 Hz sinyaller, `null` = ölçüm
yok) · `GET /jobs/{id}/momentum` (puan defteri, parametreler, paylar) ·
`POST /jobs/{id}/swap` (kırmızı/mavi tarafları tek işlemde değiştirir) ·
`PUT /jobs/{id}/exclusions` (kullanıcının dışladığı bölümler; momentum istek içinde yenilenir) ·
`PUT /jobs/{id}/exclusions/auto` (geri alınan otomatik bölümler; momentum istek içinde yenilenir) ·
`PUT /jobs/{id}/match` (raundlar, bitiş, kesintiler) · `GET /jobs/{id}/scorecards`
(AI hakem kartları) ·
`POST /jobs/{id}/exports` (dışa aktarma işi başlatır; gövde: `ExportRequest`; analiz
başına aynı anda bir tane) ·
`GET /jobs/{id}/exports` (analizin dışa aktarmaları) ·
`GET /jobs/{dışa_aktarma}/files/{video|metrics|bundle}` (indirme).
Seçimden sonra `poses` yanıtındaki tespitlerde `track_id` ve `fighter_id`, karede
de iki dövüşçünün durumu (`tracked` / `occluded` / `uncertain`) bulunur.
Durum değiştiren istekler `X-Fight-Analyzer: 1` başlığı
ister ve yabancı `Origin` reddedilir (başka sitelerin bu makinedeki API'yi
kullanması engellenir).

## Dövüşçü seçimi ve kimlik takibi

Poz çıkarımından sonra iş `awaiting_selection` durumunda bekler. Seçim ekranında
kullanıcı aday karelerde önce **kırmızı**, sonra **mavi** köşedeki dövüşçünün
kutusuna ya da karenin altındaki büyük kırpılmış karesine tıklar (kareler
klavyeyle de seçilir). Aynı kişi iki tarafa seçilemez, yeniden tıklamak seçimi
kaldırır, "Seçimi sıfırla" ikisini de temizler, ±1/±10 kare adımlarıyla aday
olmayan karelere de gidilebilir. Onaydan sonra kimlik takibi çalışır ve sonuç
ekranı açılır.

### Takip hazırlığı (seçimden önce, `tracking_prep`)

1. **Kamera kesimleri:** ardışık karelerin HSV renk histogramı farkı
   (8×4×4, 64×36 küçültülmüş kare). Kesim = mutlak büyük sıçrama (≥ 0,5) ya da
   son 15 karenin medyanının ≥ 4 katı ve ≥ 0,12. Tek karelik flaş (sonraki kare
   öncekine benziyorsa) kesim sayılmaz; 6 kareden kısa çekimler birleştirilir.
   Alt eşik bilerek düşüktür: oktagon yayınlarında iki çekim de çoğunlukla aynı
   zemindir; gerçek klipte bir sert kesim yalnızca 0,19 fark üretti (kamera
   hareketi en fazla 0,02).
2. **Geçici izler:** Ultralytics **OC-SORT** her çekimde **sıfırdan** başlatılır
   (izleyici tek başına, poz tespitleri üzerinde; `track_buffer` 0,5 sn).
   Geçici `track_id` yalnızca o çekimde anlamlıdır. İz parçaları kutu
   örtüşmesi başladığında/bittiğinde, 3 kareden uzun boşlukta ve kesimde
   bölünür: örtüşme sırasında izleyici kimlikleri karıştırabileceği için bir
   parçanın içinde tek kişi olduğu varsayılır.
3. **Görünüm tanımlayıcısı:** eklemlerden bulunan **şort** ve **gövde**
   bölgelerinde renk (ton×doygunluk + siyah/gri/beyaz kutuları), yön histogramı
   ve doku enerjisi (desen, logo, dövme). Yalnızca renge bakılmaz.
4. **Aday kareler:** iki büyük kişinin net, ayrık ve kesimden uzak göründüğü
   kareler videonun farklı bölümlerinden seçilir.

### Kalıcı kimlik (seçimden sonra, `tracking`)

Geçici `track_id` ile kalıcı `fighter_id` (`fighter_a` = kırmızı,
`fighter_b` = mavi) ayrıdır. Her seçim noktasından video **ileri ve geri**
işlenir; video ortasında seçim yapılınca baştaki bölüm de geriye doğru
işlenir. Kurallar:

- Bir dövüşçünün iz parçası sürdükçe kimlik onu izler. Parça bitince (örtüşme,
  kayıp) sonraki parça **iki dövüşçü için birlikte** seçilir: görünüm (bu
  dövüşçüye benzerlik eksi diğerine benzerlik), konum/hız tahmini ve boyut.
  "A,B" ile "B,A" atamaları arasında yeterli fark yoksa ikisi de belirsiz kalır.
- **Kamera kesiminden sonra** konum taşınmaz, yalnızca görünüm kullanılır ve
  eşikler sıkılaşır. Çekimde tek kişi yerleştirilecekse ortak "A,B / B,A"
  karşılaştırması yapılamadığı için görünüm farkı ≥ 0,15 olmalıdır. Konum
  bilgisi yokken kimlik **örtüşen kutudan** (iki kişiyi karıştırır) ya da çok az
  temiz kareden kurulmaz.
- **Hakem ve seyirciler:** bir dövüşçünün doğrulanmış kutusuyla aynı karede
  görülen parça o dövüşçü olamaz. İki dövüşçüyle birlikte görülen kişiler
  (hakem, seyirci) "üçüncü kişi" referansı olur; aday, dövüşçüye o kişilerden
  daha çok benzemelidir. Karedeki en büyük kişinin %35'inden küçük kutular
  (kafes arkasındaki seyirciler) dövüşçü kimliği alamaz.
- **Örtüşmeler** (klinç, çapraz geçiş, hakemin araya girmesi) yalnızca izleyici
  sürekliliğiyle izlenir ve geçicidir; kare kare görünüm o kişinin başkası
  olduğunu söylerse takip bırakılır. Kısa örtüşme "Örtüşme" (occluded) olarak,
  uzun belirsizlik **"Takip belirsiz"** olarak gösterilir; hiçbir kare rastgele
  atanmaz.
- **Görünüm referansı** yalnızca güvenli, temiz eşleşmelerden sonra ve yalnızca
  o çekimde güncellenir. Kullanıcının seçimleri **çekime özeldir**: bir çekimde
  o dövüşçü seçildiyse orada yalnızca o seçim kullanılır, yoksa tüm seçimler
  (yakın plan, geniş plandan çok farklı görünür).
- Bir tespit asla iki dövüşçüye birden verilmez.
- Birden çok seçim noktası varsa iki yönün sonuçları birleştirilir; çelişkide
  **daha az kamera kesimi geçmiş** sonuç kazanır, eşitse kare belirsiz kalır
  (`anchor_conflict`).

**OC-SORT'un kamera kesimlerindeki sınırları (ve bu yüzden yapılanlar):**
OC-SORT bir kare-kare hareket izleyicisidir. Kalman tahminleri, IoU
eşleştirmesi ve "gözlem merkezli" yeniden başlatma, kişilerin bir önceki
konumuna yakın olduğunu varsayar. Kesimde bu varsayım çöker: tahminler eski
çekimdeki konumları gösterir, `track_buffer` içinde kalan eski iz yeni çekimde
o konuma düşen **başka bir kişiye** bağlanabilir ve geçici numara sessizce yanlış
kişiye geçer. Kullanılan yapılandırmada görünüm (ReID) yoktur; kamera hareketi
düzeltmesi (GMC) de iki farklı kamera arasında anlamsızdır. Bu yüzden izleyici
her kesimde sıfırlanır, `track_id` hiçbir zaman kesimden geçirilmez ve kimlik yeni
çekimde yalnızca görünümle, daha katı eşiklerle yeniden bulunur. Kaçırılan bir
kesim, aynı çekim sanılan iki görüntü arasında konumun taşınması demektir; kesim
eşiği bu yüzden düşük tutulmuştur.

### Ölçümler ve düzeltme

- Dövüşçü başına: takipte / örtüşme / belirsiz kare sayısı, belirsiz süre ve en
  uzun belirsiz aralık, yeniden bulma, geçici numara değişimi (son sonuç
  üzerinden, her değişim bir kez), ortalama güven. Kapsamlı veri kalitesi için
  bkz. "Kimlik takibi ve veri kalitesi".
- **Olası kimlik değişimi:** bir dövüşçü, kısa süre önce diğer dövüşçüye ait
  olan geçici ize geçtiğinde sayılır. **Takas düzeltmesi:** izleyici izi
  sürdürdüğü hâlde görünüm başka kişi dediğinde. Bunlar doğruluk ölçüsü değil,
  sistemin **fark edebildiği** olaylardır; gerçek video için doğru cevap bilinmez.
- Sonuç ekranında iki şerit (takipte / örtüşme / belirsiz, kesim çizgileri,
  "kontrol önerilir" noktaları) ve takip kaydı. Her belirsiz aralıkta **"Bu
  karede düzelt"** seçim ekranını o karede açar; önceki seçimler korunur ve yeni
  seçim eklenir. Dövüşçülerden biri o karede görünmüyorsa **"Bu karede
  görünmüyor"** işaretlenebilir (yakın planlar için). "Tarafları değiştir"
  renkleri ve seçimleri takas edip yeniden eşler.
- Sonuçlar seçim noktalarına göre önbelleğe alınır (`cache/identity`); aynı
  seçim tekrar hesaplanmaz.

**Gerçek klip denemesi (`topuria-oliveira.mp4`, 10,9 sn, 327 kare, 3 çekim;
yalnızca işlev denemesi, doğruluk iddiası değildir):** iki kesim de bulundu,
yanlış kesim yok. Tek seçimle (kare 9) her iki dövüşçü ilk çekimde izlendi;
yakın plan çekimlerinde ikisi de "Takip belirsiz" kaldı (Topuria 6,8 sn,
Oliveira 6,9 sn). İki düzeltme seçimiyle (kare 124: yalnız Oliveira, kare 244:
yalnız Topuria) belirsizlik yalnızca dövüşçünün görüntüde olmadığı çekimde kaldı
(3,5 sn / 3,3 sn). Kareler tek tek incelendi: hakem, seyirciler ve diğer dövüşçü
hiçbir karede kimlik almadı. Sistemin saydığı kimlik değişimi 0, çelişki 0.
Geliştirme sırasında bu klipte bulunan hatalar (kaçırılan kesim, hakemin yere
düşen dövüşçünün kimliğini alması, kesim sonrası seyircinin dövüşçü sanılması,
yakın planda iki dövüşçünün karıştırılması, düzeltmenin diğer çekimi bozması)
sentetik sahnelerle regresyon testine dönüştürüldü.

**Sınırlar:** renk/doku görünümü, aynı tenli, dövmeli ve benzer şortlu iki
dövüşçüyü yakın planda ayıramayabilir; sistem bu durumda tahmin etmek yerine
belirsiz bırakır ve düzeltme ister. Yerde ve iç içe pozisyonlarda poz modeli tek
kutuya iki kişi koyabilir ya da bozuk iskelet üretebilir; bu kareler çoğunlukla
"örtüşme/belirsiz" olur. Tekrar (replay) çekimleri ayrı çekim olarak görülür ve
yeniden tanınmaları gerekir. Doğruluk etiketli gerçek veriyle ölçülmedi.

## Hareket sinyalleri, olaylar ve deneysel momentum

Kimlik takibinden sonra iki aşama daha çalışır: `events` (kamera hareketi,
sinyaller, olaylar) ve `scoring` (deneysel momentum). Ölçüm yalnızca kimliği
doğrulanmış karelerde yapılır (`tracked`, ya da tespiti olan `occluded`);
bunun dışında **veri yok** sayılır, yeni olay üretilmez ve arayüzde "—" /
"Veri yetersiz" gösterilir.

### Ölçüm

- **Kamera hareketi** arka plandan tahmin edilir: kişi kutuları ve kalıcı
  yayın grafikleri (skor çubuğu, logo; farklı çekimlerde aynı kalan ve çekim
  içinde değişmeyen pikseller) dışındaki köşe noktaları Lucas-Kanade optik
  akışıyla ileri-geri doğrulanarak izlenir, RANSAC ile benzerlik dönüşümü
  (kaydırma, yakınlaştırma, küçük dönme) bulunur ve çekim başına zincirlenir.
  Yeterli arka plan noktası uyuşmazsa zincir kırılır: önceki ve sonraki
  konumlar karşılaştırılmaz ("kamera hareketi bilinmiyor").
- **Ölçek:** her dövüşçünün gövde boyu (omuz ortası–kalça ortası), görünen tüm
  vücut parçalarından tipik oranlarla tahmin edilir. Mesafe ve hızlar bu
  "gövde boyu" biriminde verilir; kameraya uzaklık ve yakınlaştırma etkisi
  kalkar.
- **Geçerlilik:** güveni 0,5'in altındaki eklem ölçüm sayılmaz; tek karelik
  sıçramalar, sol/sağ eklem karışmaları ve fiziksel olarak imkânsız hızlar
  atılır.
- **Yumuşatma:** zaman tabanlı One-Euro filtresi; yavaş harekette titreşimi
  bastırır, hızlı harekette (vuruş) tepe değeri korur.
- **Hız:** sabit bir zaman penceresindeki (0,067 sn) yer değiştirme bölü süre;
  konumlar zaman ekseninde ara değerlenir. Aynı hareket 25, 30, 50 ve 60 fps'te
  aynı hızı verir; eşiklerin tamamı saniye ve gövde boyu cinsindendir.

### Sinyaller ve olaylar

- **El ve ayak hareketliliği:** bileklerin ve ayak bileklerinin kalçaya göre
  hızı; aktivite = bu hızın 4 gövde boyu/sn'ye oranı (0–100).
- **İlerleme / geri çekilme:** kalça merkezinin (kamera hareketi çıkarılmış)
  rakibe doğru hızı, 0,3 sn yumuşatılmış; iki dövüşçü de ayaktayken ≥ 0,5
  gövde boyu/sn ve en az 0,4 sn sürerse.
- **Vuruş denemeleri:** uzvun kalçaya göre hızı bir eşik üstünde kaldığı tek
  kesintisiz aralık **tek denemedir**; başlangıç, zirve (en hızlı an) ve bitiş
  kaydedilir. Ayrıca uzvun rakibe doğru açılması (yumrukta rakibin üst
  gövdesine uzanma), hareketin rakibe yönelmesi ve rakibin erişim mesafesinde
  olması gerekir. Tekme/diz sırasında kol hareketi ayrıca yumruk sayılmaz,
  aynı anda iki kolun zirvesi tek hareket sayılır, düşerken uzuvların savrulması
  ve **rakibin altında yatan** dövüşçünün kol/bacak hareketi (kapanma,
  itme; 2B'de vuruştan ayırt edilemez) deneme sayılmaz.
- **Olası temas:** zirveden sonra vuran eklem rakibin kutusunun içinde ve bir
  ekleminin yakınındaysa. 2B örtüşme kesin temas değildir; yalnızca "olası temas"
  olarak gösterilir.
- **Sınırlı kontrol tahmini:** klinç = ikisi ayakta ve çok yakın (≥ 1,5 sn);
  yer kontrolü = biri yerde, diğeri yakın ve üstünde (≥ 1 sn).
- **Duruş değişimi, olası knockdown / takedown:** kararlı ayakta duruştan
  kararlı yerde duruşa geçiş. Düşüş başlamadan hemen önce (1,2 sn) rakibin
  vuruş denemesi varsa ve klinç yoksa **olası knockdown**; öncesinde yakın temas
  varsa **olası takedown**; ikisi de yoksa yalnızca duruş değişimi (puansız).
  Rakip zaten yerdeyken üstüne inmek düşüş sayılmaz; yerdeki dövüşçüye
  knockdown/takedown yazılmaz. Her olayda karar verdiren ölçümler
  (`measures`: tepe hız, uzanma, yönelim, mesafe, düşüş süresi…) saklanır.

### Deneysel momentum

Başlangıç tasarım parametreleri (`MomentumSettings`; doğrulanmış spor bilimi
ağırlıkları değildir):

| Kaynak | Puan |
|---|---|
| Vuruş denemesi (yumruk, diz) | 1 |
| Tekme denemesi (aynı hareket ayrıca yumruk sayılmaz) | 1,3 |
| Olası temas eki | +0,3 |
| İlerleme | saniye başına 0,2 |
| Tahmini yer kontrolü | saniye başına 0,5 |
| Olası knockdown / takedown (güven ≥ %50) | 4 / 2,5 |

Her puan 20 saniyede yarıya iner (süreye bağlı puanlar tam integral alınarak).
Kırmızı payı = 100 × (m₁ + 4) / (m₁ + m₂ + 8), mavi payı = 100 − kırmızı, yani
toplam her zaman 100 ve veri yokken 50/50. Her puan bir "defter" kaydıdır
(kaynak, olay, zaman, miktar, puan); sonuç ekranı bir anki payı kaynaklara
ayırır ve seçilen olayın olay anındaki ve şu anki etkisini yüzde puan olarak
gösterir. Ekranda her zaman "Deneysel momentum — kazanma olasılığı değildir"
yazar; dövüşçülerden biri ölçülemiyorsa "Veri yetersiz" görünür.

**Sonuç ekranı:** üstte momentum çubuğu; yanlarda o ana kadarki ölçümler
(vuruş/tekme denemeleri, aktivite, baskı, ilerleme/geri çekilme, tahmini
kontrol süresi, olası büyük olaylar, ölçülebilen süre); videoda vuruş zirvesinde
vuran eklemde halka (olası temasta kehribar); zaman çizelgesinde olaylar ve
momentum eğrisi; "Olaylar ve momentum" sekmesinde olay listesi ve momentum
açıklaması, "Takip kaydı" sekmesinde kimlik kayıtları.

**Gerçek klip denemesi (`topuria-oliveira.mp4`; işlev denemesi, doğruluk
iddiası değildir):** kareler tek tek incelendi. Topuria'nın sol düz vuruşu
(0,2 sn), knockdown'u getiren sağ eli (0,4 sn, olası temas), Oliveira'nın
karşılıkları (0,3 ve 0,5 sn) ve Topuria'nın yerde vuruşu (2,5 sn) deneme olarak;
Oliveira'nın 1,3 sn'lik düşüşü, vuruştan 0,57 sn sonra başladığı için **olası
knockdown** (güven %70) olarak bulundu. Geliştirme sırasında bu klipte
görülen hatalar (sağ elin rakibin kalçasına göre ölçülüp kaçırılması, yerde
yatan Oliveira'nın kapanmasının "yumruk" sayılması, Topuria'nın Oliveira'nın
üstüne inmesinin Oliveira'ya yazılan bir knockdown sayılması) düzeltildi ve
sentetik testlere dönüştürüldü. Aynı klibin 9. karesinden yapılan 5 sn'lik
**hareketsiz video** uygulamanın tamamından geçirildi: 0 olay, 0 puan, momentum
baştan sona %50/%50 (ölçülen en yüksek el hızı 0,22 gövde boyu/sn; eşik 6).

**Sınırlar:** her şey 2B pozdan çıkarılır: derinlik yönündeki hareket ve
kameraya dik vuruşlar zayıf görünür, kanca/overhand gibi bükük kollu vuruşlar
eşiğe yakın kalabilir; temas ve vuruşun isabeti ölçülemez. Yerde ve iç içe
pozisyonlarda (klinç, ground and pound) poz modeli sık hata yapar ve kimlik
çoğu zaman belirsizdir; bu sürelerde olay az çıkar ve kontrol tahmini
ölçülemeyebilir. Kamera, kişilerin kareyi doldurduğu yakın planlarda
ölçülemez. Eşikler etiketli gerçek veriyle ayarlanmadı; olay sayıları
doğruluk ölçüsü değildir.

## Video ile iskeletlerin ve istatistiklerin senkronu

**Zaman kaynağı:** sonuç ekranında video öğesinin kendisi tek doğruluk
kaynağıdır. Tarayıcının `requestVideoFrameCallback` mekanizması her **ekrana
gelen karede** o karenin medya zamanını (`mediaTime`) verir; kare numarası
`floor(mediaTime × fps)` olarak bulunur (analiz kopyası sabit kare hızlı, kare i
[i/fps, (i+1)/fps) aralığını kaplar). Aynı zaman hem çizime hem de panellere
gider: iskelet, vuruş halkaları, kare sayacı, istatistikler ve momentum hep aynı
kareye aittir. Video durunca kare gelmez, çizim de durur.
**Yedek yol:** `requestVideoFrameCallback` yoksa oynatırken her animasyon
karesinde ve atlama/durdurma/yüklemede `currentTime` izlenir; oynatma çubuğunda
"Yedek senkron" görünür (oynarken en fazla bir kare sapabilir, durunca kesindir).
Kare adımları ve atlamalar karenin ortasına gider, böylece kesin o kareye düşer.

**Çizim (Canvas):** video `object-fit: contain` ile çizilir; tuval aynı kutuyu
kaplar ve aynı oran/boşluk hesabını kullanır (`player/geometry.ts`). Tuvalin
arka belleği kutu boyutu × cihaz piksel oranıdır ve pencere boyutu, tam ekran ya
da piksel yoğunluğu değişince yeniden ölçülür; tam ekran video + tuvali birlikte
kapsar. Kırmızı ve mavi iskeletlerde eklem noktaları, uzuv çizgileri, yüz
noktaları görünüyorsa kafa çevresi halkası ve isim; altında koyu kontür ve ölçülü
bir parlama vardır. **Uydurma yok:** güveni 0,5'in altındaki eklem ve ona bağlı
uzuv çizilmez; kimliği doğrulanmamış kişi dövüşçü rengiyle çizilmez (istenirse
gri "diğer kişi" olarak); kısa örtüşmedeki kimlik kesikli çizilir; o karenin poz
verisi henüz yüklenmediyse hiçbir şey çizilmez ("Poz verisi yükleniyor").
Katmanlar: iskelet, olay efektleri (aşağıda), mesafe (iki kalça merkezi
arası kesikli çizgi ve o anın önceden ölçülmüş mesafesi, gövde boyu cinsinden).

**İstatistikler biriktirilmez:** paneller ve momentum, ilgili video zamanı için
önceden hesaplanmış değerlerden (olay listesi, 10 Hz sinyallerin önek
toplamları, momentum defteri) o anda hesaplanır. Aynı bölümü tekrar izlemek,
oynatma hızını değiştirmek ya da ileri-geri atlamak sayıları değiştirmez.

**Kontroller:** oynat/duraklat; 0,25× · 0,5× · 1× · 2×; bir kare ve bir saniye
ileri/geri; iskelet, olay efekti, mesafe ve diğer kişiler katmanları; tam ekran;
isim düzenleme; **taraf değiştirme** (`POST /jobs/{id}/swap`: seçim noktaları ve
isimler tek işlemde yer değiştirir; kişiye ait girdiler, yani bitişte kazanan ve
puan kesintileri, kişiyle birlikte taşınır; kimlikler, olaylar, istatistikler ve
momentum yeni taraflara göre birlikte yeniden üretilir; bu sırada sonuç ekranı
"Sonuçlar yeniden hesaplanıyor" gösterir, eski sonuç güncelmiş gibi gösterilmez);
**dövüşçüleri yeniden seçme** (poz çıkarımı tekrar çalışmaz, önbellekten
okunur).

**Tarayıcıda denendi** (`topuria-oliveira.mp4`, piksel oranı 1,25):
- Tuvaldeki eklem pikselleri API'deki eklem konumlarıyla karşılaştırıldı:
  normal görünümde 9/10 ve 8/8, kutu kare yapılıp üst-alt boşluk oluşturulunca
  (tam ekran durumu) 9/10, 12/12, 8/9 eklem tam doğru renkteydi (eksik olanlar
  diğer dövüşçünün çizgisinin altında kalan noktalar).
- Rastgele atlamalarda (kare 250, 13, 300, 70, 8, 160), 2× ve 0,25× oynatmadan
  sonra ve aynı bölümü yeniden izleyince kare sayacı, iki paneldeki vuruş
  sayısı ve momentum yüzdesi bağımsız hesaplanan değerlerle 9/9 aynıydı; kare
  250'de yeniden izleme öncesi ve sonrası değerler aynı kaldı.
- Duraklatınca tuval değişmedi; oynatırken gelen her yeni karede yeni çizim
  yapıldı (39 karede 38 değişiklik) ve kare sayacı her karede medya zamanıyla
  uyuştu.
- Taraf değişiminde isimler, momentum (%63/%37 → %37/%63), iki panel ve
  tuvaldeki renkler (Oliveira kırmızı 7/8, Topuria camgöbeği 10/10) birlikte
  değişti; geri değiştirince ilk sonuç birebir geri geldi.
- `requestVideoFrameCallback` kaldırılarak yedek yol denendi: "Yedek senkron"
  göründü, atlamalarda kare sayacı ve sayaçlar doğruydu, duraklatınca çizim
  durdu.

## Zaman çizelgesi, olay efektleri ve dışa aktarma

**Zaman çizelgesi** (videonun altında, kompakt): ortadaki şeritte deneysel
momentum %100 kırmızı (üst) ile %100 mavi (alt) arasında çizilir; eğrinin
üstü kırmızı, altı mavi dolgudur, böylece her andaki dağılım dikey bölünmeden
okunur; %50 çizgisi kesiklidir. Dövüşçülerden biri ölçülemediği aralıklar
kehribar tarama ile "veri yetersiz" olarak gösterilir (gizlenmez). Üst şerit
kırmızı, alt şerit mavi köşenin olaylarıdır: yumruk ince çizgi, tekme eşkenar
dörtgen, diz kare, klinç/yer kontrolü süre çubuğu, duruş değişimi halka; olası
temaslı denemeler kehribar çerçeveli; olası knockdown/takedown tüm yüksekliği
kesen kehribar çizgi ve üçgendir. Beyaz dikey çizgi oynatma konumudur.
Tıklama ya da sürükleme videoyu o ana götürür (klavye: ←/→, Shift, Home/End).
Üzerine gelince olayın zamanı, dövüşçüsü, türü ve belirsizlik etiketleri görünür.

**Olay listesi:** zaman (olay anı = tepe karesi), dövüşçü, tür, güven ve
belirsizlik etiketleri: *Olası* (knockdown/takedown doğrulanmamıştır), *Olası
temas* (2B örtüşme, temas kesin değil), *Düşük güven* (dedektör güveni < %60),
*Kimlik örtüşmede* (olay anında dövüşçüler üst üsteydi), *Puan yok* (momentuma
katkısı yok). Köşe filtresi ve olay türü filtresi (türler tek tek açılıp
kapanır, sayılarıyla) vardır. Bir olay seçilince video olaydan **1 sn önceye**
gider (kare tam hizalanır) ve momentum panelinde o olayın etkisi açıklanır.

**Olay efektleri** (`shared/overlay-style.json` tarayıcı ve MP4 için tek
kaynaktır; `npm run gen:types` bunu `src/contracts/overlayStyle.ts` olarak
üretir):
- Vuruş denemesi: tepe anından 0,06 sn önce başlayıp 0,3 sn içinde sönen,
  vuran uzvun (omuz–dirsek–bilek ya da kalça–diz–ayak bileği) o anki iskelette
  açık tonla vurgulanması; uzuv görünmüyorsa yalnızca tepe anında ölçülen eklem
  konumunda küçük bir işaret.
- Olası temas: vuran eklemin konumunda 0,35 sn süren küçük kehribar halka;
  yalnızca en yeni halkada "olası temas" yazısı.
- Olası knockdown/takedown: videonun üstünde 2 sn kalan, son 0,3 sn'de sönen
  sarı uyarı ("OLASI KNOCKDOWN · ad").
- Süreler video zamanından hesaplanır (saf fonksiyon `effectsAt`): duraklatınca
  efekt donar, geri sarınca yeniden görünür, oynatma hızı süreyi değiştirmez.
  Kimlik örtüşmesi/belirsizliği rozetleri ve "veri yetersiz" etiketi efektlerin
  altında kalmaz ve efekt katmanı kapatılsa da gösterilir.

**Dışa aktarma** (Sonuç → "Dışa aktar" sekmesi ya da üstteki düğme):
- Ayrı bir iş olarak (`job_type: "export"`) işçide çalışır; analiz ekranı bu
  sırada kullanılmaya devam eder. İlerleme, kalan süre ve iptal sekmede görünür.
- İstek anında tarayıcının gösterdiği önbellek kayıtlarının anahtarları ve
  isimler işe kopyalanır; dışa aktarma bu kayıtları API'nin tarayıcıya verdiği
  aynı fonksiyonlarla okur. Taraflar sonradan değişirse eski dosyalar "Önceki
  sonuçlardan" etiketiyle kalır.
- **MP4** (`*-analiz.mp4`): analiz kopyasının kareleri sırayla çözülür, iskelet,
  olay efektleri, üstte isimler + deneysel momentum çubuğu + "kazanma olasılığı
  değildir" notu, sayaçlar, isteğe bağlı mesafe ve diğer kişiler çizilir;
  FFmpeg ile H.264'e kodlanır, ses akışı olduğu gibi kopyalanır. Kimlik
  durumu rozetleri, "veri yetersiz" etiketi ve "2B poz tahmini…" dipnotu her
  zaman vardır. Türkçe yazılar Pillow ile (Bahnschrift/Segoe UI) çizilir.
- **CSV** (`*-kareler.csv`): kare başına bir satır: zaman, gösterilen ve tam
  momentum payları, puanlar, veri yetersizliği, kamera/mesafe, her köşe için
  kimlik durumu, o ana kadarki deneme/olası temas/knockdown/takedown sayıları,
  aktivite/baskı/ilerleme/geri çekilme yüzdeleri, kontrol ve ölçülen süre,
  10 Hz sinyaller ve o karede tepe yapan olaylar. Sütun açıklamaları JSON'da.
- **JSON** (`*-analiz.json`, `AnalysisExport`): olaylar, momentum defteri ve
  parametreleri, sayılar, seçim, kullanılan poz modeli ve ayarları, hareket ve
  momentum ayarları (önbellek kayıtlarından), stil dosyası, dışa aktarma
  seçenekleri, kaynak önbellek anahtarları.
- Dosyalar `data/jobs/<dışa_aktarma>/` altında kalır; hiçbir yere gönderilmez.

**Tarayıcı ve MP4 aynı sayıları gösterir:** istatistikler ve momentum gösterilen
kareye bağlıdır (t = kare × 1000 / fps ms; bir olay tepe karesinden itibaren
sayılır) ve `export/frames.py`, `model/measured.ts` + `player/effects.ts`
fonksiyonlarını işlem sırasıyla birebir uygular (JavaScript yuvarlaması dahil).
`shared/fixtures/frame-metrics.json` sentetik bir analizde 325 karenin
beklenen değerlerini ve görünen efektlerini tutar; backend testi dosyanın
Python hesabıyla, ön yüz testi tarayıcı hesabıyla aynı olduğunu denetler.

**Tarayıcıda denendi** (`topuria-oliveira.mp4`, 327 kare, sesli):
- Olay listesinde olası knockdown'a (tepe karesi 68) tıklayınca video 38. kareye
  (1 sn önce) gitti; zaman çizelgesinin ortasına tıklama 5,45 sn'ye (süre
  10,9 sn), %25'ten %75'e sürükleme 8,18 sn'ye götürdü.
- Arayüzden başlatılan dışa aktarma ~6 sn sürdü; bu sırada video 6 sn'de 6 sn
  oynadı, sayfanın zamanlayıcı gecikmesi en fazla 21 ms oldu, ilerleme ve kalan
  süre canlı güncellendi.
- 31 karede (olay kareleri ve rastgele kareler) tarayıcıdaki momentum yüzdesi ve
  iki paneldeki tüm istatistikler dışa aktarılan CSV ile birebir aynıydı; "veri
  yetersiz" bayrağı da aynıydı. MP4'ten çıkarılan 70. ve 212. karelerde üst
  bantta tarayıcıdaki yüzdeler (%61/%39, %63/%37) ve sayaçlar vardı; 70. karede
  iki tarafta da "OLASI KNOCKDOWN · Topuria" uyarısı görüldü. Çıktıda 327 kare
  ve AAC ses akışı bulundu.

## Maç ayarları ve raunt tespiti (v2 Bölüm 2a)

`backend/fight_analyzer/broadcast/`, boru hattında `broadcast` aşaması (takip
hazırlığından sonra, seçimden önce), `GET /jobs/{id}/broadcast`. Seçim ekranında
ve "Hakem kartları (AI)" sekmesinde "Maç ayarları" kartı. Raunt sınırları ve
okunan adlar yayın grafiğinden çıkarılan **AI tahminidir**, resmi zamanlama değildir.

- **Maç ayarları (`BoutConfig`, `PUT /jobs/{id}/bout`):** raunt sayısı (3 / 5),
  raunt süresi (300 sn), dinlenme (60 sn), şampiyonluk, kural seti `abc_2025`,
  köşe adları. Varsayılanlar `config.py` → `RulesetSettings` içindedir (komisyona
  göre değişir, koda gömülü değildir). `MatchSetup.scheduled_rounds` ve
  `round_length_s` artık buradan kopyalanır; eski analizlerde varsayılan
  olarak `MatchSetup`'taki değerler okunur. Kaydetmek hiçbir şeyi yeniden hesaplatmaz.
- **Saat alanı (ROI):** videoya yayılmış 48 karede üst ve alt bantta metin
  satırı adayları bulunur (OpenCV, model yok). Ekranda aynı yerde kalan, `m:ss`
  okunan ve videoyla birlikte geri sayan kutu saattir; kamerayla kayan arena
  ekranları bu yüzden seçilmez. Yanındaki `R1` kutusu raunt numarası, saatin
  solu ve sağı ad önerisidir. Kullanıcı Seçim ekranında dikdörtgen çizerek alanı
  düzeltebilir (`PUT /jobs/{id}/scorebug`; yalnızca bu aşama yeniden çalışır).
- **Okuma:** tek sıralı geçişte yalnızca saat alanı (ve raunt kutusu) saniyede
  bir kez okunur. Geri sayım koşuları: saat yukarı sıçrarsa yeni raunt; video
  ilerlerken saat duruyorsa durma; üç okumaya kadar tutarsız okuma OCR hatası
  sayılıp atılır. Başlangıç, ilk okumalardan saatin tepeden (5:00) çıktığı ana
  geri çekilir; saat 0:00'a inerse raunt tamamdır, üstünde donarsa erken bitmiştir
  (ör. nakavt, `partial`), kaybolursa son okumada kesilir. İlk okuma tepeden 6 sn'den
  fazla, 20 sn'ye kadar aşağıdaysa saat raunt başında kapalıydı (sponsor grafiği,
  geç gelen scorebug): başlangıç ilk okumadan geriye hesaplanır, `start_extrapolated_s`
  ile işaretlenir ve güveni × 0,85 olur; o an videodan önceyse, önceki rauntla
  çakışıyorsa ya da arada yayının rauntun içine dönüşünü gösteren bir logo geçişi
  varsa geriye hesaplanmaz (kısmi raunt). Yayın sürümü 4.
- **OCR yoksa:** pozlardan raunt arası tespiti (≥45 sn dövüşsüz, oturan kişi ya
  da kafeste çok kişi). Güveni en fazla 0,5'tir; ara bulunamazsa raunt iddia
  edilmez (tüm video "R1" sayılmaz).
- **Elle düzenleme her zaman geçerlidir:** elle girilen raunt (`MatchSetup.rounds`)
  aynı numaralı otomatiği ezer; silinen otomatik raunt `cleared_rounds`'ta tutulur
  ve yeniden tespitte geri gelmez; çakışan otomatik raunt notla dışarıda kalır.
  Etkin liste `Job.rounds`'ta (`source: ocr | break | manual`, güven, `partial`),
  hakem kartları bu listeyi kullanır. Sonuç ekranında sınırlar zaman çizelgesinde
  sürüklenir ya da ok tuşlarıyla kaydırılır (`PUT /jobs/{id}/rounds`).
- **Eski analizler** açılır; "Bu analiz eski sürümle yapıldı — yeniden işle"
  bandı `POST /jobs/{id}/reprocess` çağırır (poz ve hazırlık önbellekten gelir;
  kaynak video dosyası gerekir).
- **OCR modeli:** PaddleOCR `en_PP-OCRv5_mobile_rec` (ONNX, 7,85 MB, Apache-2.0,
  © PaddlePaddle Authors). Kaynak:
  [huggingface.co/PaddlePaddle/en_PP-OCRv5_mobile_rec_onnx](https://huggingface.co/PaddlePaddle/en_PP-OCRv5_mobile_rec_onnx),
  commit `3fafbc3b5dcf93dd72add9f48368be8a3a2cd33b`; `inference.onnx` SHA-256
  `b5f833dfc5d0eb71da397b4efa06ebeee9b431b690a47d6af40d77d8eabc557f`,
  `inference.yml` (karakter sözlüğü) SHA-256
  `27e91d0582f40168aa218303c76e184bc78fa7a5d105aad0cfbad8458b441067`. Yalnızca
  kurulumda (`setup.cmd`) ya da `python -m fight_analyzer.broadcast.ocr_model`
  ile indirilir, boyut ve SHA-256 tutmazsa yerine konmaz; `data/models/ocr/`'da
  durur. Analiz sırasında indirme ve ağ bağlantısı yoktur (test denetler).
- **Çalıştırıcı:** `onnxruntime` 1.31.1 (MIT, yalnızca CPU; yan bağımlılıklar
  `protobuf` 7.36.2 BSD-3, `flatbuffers` 25.12.19 Apache-2.0). OpenCV 4.14'ün DNN
  modülü bu modeli yükleyemediği (dinamik `Reshape`) için eklendi. RapidOCR
  kullanılmadı: mevcut `opencv-python` ile çakışan `opencv-python-headless`
  getiriyor ve modelleri ilk çalıştırmada indiriyor.
- **Ölçüm (örnek yayın, 9 dk, 1080p, bu makinede CPU):** yayın aşaması ≈40–50 sn
  (rastgele 48 kare ≈3 sn, sıralı okuma ve OCR geri kalanı); raunt sınırları
  karelerden okunan saatle ±1 sn içinde. Bu video yöntem ayarlanırken kullanıldı;
  doğruluk değeri değildir.

## Yayın kesmeleri ve tekrar ayıklama (v2 Bölüm 2b)

`backend/fight_analyzer/broadcast/replay.py` (sinyaller ve kurallar),
`backend/fight_analyzer/nonfight.py` (rauntlarla birleştirme, geri alma, etkin
liste). Otomatik bölümler yayın grafiğinden ve raunt sınırlarından çıkarılan bir
**AI tahminidir**; her biri nedeni, güveni ve dayanağıyla gösterilir, tek tıkla
geri alınır.

- **Dört sinyal** (yayın aşamasında, saniyede 2 örnek; ayrı bir video okuması yok):
  1. *Scorebug*: saatin çevresindeki şerit, saatin okunduğu karelerden öğrenilen
     olağan görünümüyle karşılaştırılır (sıfır ortalamalı korelasyon; örnek
     yayında görünürken ≥ 0,83, yokken ≤ 0,25, eşik 0,5). Ya da saat ilerlemezken
     üst/alt bantta bir tekrar yazısı okunur ("REPLAY", "TEKRAR", "SLOW MO"…;
     liste `BroadcastSettings.replay_words`).
  2. *Saat*: dövüş saatinin durduğu biliniyor: ekranda donmuş, iki okuma arasında
     geçen sürenin en az %75'ini kaybetmiş, ya da art arda iki raunt arasında.
  3. *Logo geçişi*: takip hazırlığındaki kare değişim dizisinde 1 sn içinde en az
     0,2 sn'lik yüksek değişim (sert kesim tek karedir, kamera hareketi ≈ 10 kat
     düşük kalır) ya da 1,5 sn'den kısa çekim. Kesim tespiti ve hazırlık anahtarı
     değişmedi.
  4. *Ağır çekim*: görüntüdeki kişilerin el ve ayak bileği hızı (kalçaya göre,
     gövde boyu/sn, 0,1 sn'lik taban; kimlik gerekmez) canlı medyanın 0,65
     katının altında. Yalnızca destekleyicidir: sakin bir dövüş anı da yavaştır.
- **Kurallar:** aday bölümler scorebug'ın olmadığı ya da tekrar yazısının
  okunduğu aralıklar ile iki logo geçişi arasıdır. Dövüş saatinin **çalıştığı
  bilinen** süre her adaydan çıkarılır (saat işliyorsa görüntü canlıdır). Kalan
  bölümde dört sinyalden **en az ikisi** varsa bölüm dövüş dışıdır (güven 2/3/4
  sinyalle 0,6 / 0,8 / 0,9; tekrar yazısı +0,05). Etiketi `replay` olması için
  tekrar yazısı, logo geçişi ya da ağır çekimden en az biri gerekir; yalnızca
  "scorebug yok + saat durdu" varsa bölüm tekrar sayılmaz: etkin bir rauntun
  tamamen içindeyse `timeout` (mola), raunt dışındaysa `break` (ara) olur; "ara"
  yalnızca raunt dışındaki bölümler için kullanılır (ad, etkin rauntları bilen
  `nonfight.combine` içinde verilir). Raunt içinde saat ≥ 3 sn durur ve bölüm
  tekrar ya da mola değilse `stoppage` (duraklama: scorebug ekranda, saat donuk). İlk saat rauntundan önce ve sonuncusundan sonra
  görüntünün ≥ %90'ında scorebug yoksa `intro` ve `post_fight` (son raunt süresini
  doldurduysa `break`). Bilinmeyen sinyal kanıt sayılmaz: şablon yoksa "scorebug
  yok", saat okunmadıysa "saat durdu" denmez.
- **Dövüş dışı bölümler rauntlardan:** etkin rauntların (`Job.rounds`, elle >
  otomatik) dışında kalan süre, kesin olduğunda dışlanır: R1'den önce `intro`,
  art arda numaralı iki raunt arası `break`, son raunttan sonra `post_fight`
  (yalnızca son raunt planlanan son rauntsa ya da kullanıcı o raunt için erken
  bitiş girdiyse). Arada numarası eksik raunt varsa ya da son rauntun sonuncu
  olduğu bilinmiyorsa iddia edilmez: orada bir raunt olabilir. Raunt yoksa
  üretilmez. Tespit edilen bölümler rauntların bıraktığı yeri doldurur; tespit
  edilen giriş/son bölüm etkin bir rauntun içine giremez.
- **Geri alma:** `PUT /jobs/{id}/exclusions/auto` geri alınan bölümleri kare
  aralığı olarak saklar (`params.dismissed_auto`). Otomatik bölüm, saklı bir
  aralıkla örtüşmesi (IoU) ≥ 0,5 olduğu sürece kapalıdır: raunt kenarı birkaç
  saniye oynarsa kapalı kalır, bölüm gerçekten değişirse yeniden dışlanır.
- **Etkin liste** = kullanıcının bölümleri + geri alınmamış otomatik bölümler,
  birleştirilmiş (`nonfight.effective`). İstatistikler, hakem kartları, momentum
  ve dışa aktarma aynı listeyi (`ScoringSummary.exclusions`) kullanır. Raunt,
  maç ayarı ya da bitiş değişince liste değişiyorsa momentum **istek içinde**
  yeniden hesaplanır (önbellekteki olaylardan ≈ 0,1 sn; sonuç ekranı kapanmaz).
  Kullanıcının kendi bölümleri (`PUT /jobs/{id}/exclusions`) de aynı yoldan
  anında uygulanır; analiz işlenirken uç 409 döner.
- **Rapor:** Dışlanan bölümler listesinde her satırda bölümdeki olay sayısı ve
  altında toplam ("… olay sayılmadı: otomatik / elle"); dışa aktarılan JSON'da
  `exclusions` (kaynak, neden, güven, sinyaller) ve `excluded_event_ids`.
- **Saat alanı çizimi:** "Saat alanını düzelt" scorebug'ın kesin göründüğü kareye
  (`BroadcastSummary.scorebug_frame`, ilk rauntun ortasına en yakın okuma) geçer;
  bitince seçim karesine ve seçimlere döner.
- **Eski analizler:** `BroadcastSummary.version < 2` ise otomatik bölüm üretilmez
  (sonuçlar arkadan değişmez) ve "eski sürümle yapıldı — yeniden işle" bandı çıkar.
- **Ölçüm (ayar için kullanılan malzeme; doğruluk değeri değildir):**
  örnek yayın
  (topuria-volkanovski.mp4, 9:00): giriş 0–10,5 sn, raunt arası 310,5–317,5 sn,
  maç sonrası 530,5–540,5 sn (scorebug nakavttan hemen sonra kayboluyor; güven
  0,6); rauntlar değişmedi. Bu videoda tekrar yok. Kullanıcı kararıyla örnek
  videodan üretilen sentetik klip (83 sn; canlı bölümün ortasına logo geçişli,
  scorebug'sız, yarı hızda 16 sn'lik kopya; yalnızca `local/` altında): tekrar
  36,0–53,5 sn bulundu (eklenen 36,0–53,4 sn), dört sinyal birden, güven 0,9.
  Dışlanan olay: örnek yayında 113 olaydan 1'i (maç sonrası); klipte
  tespit edilen 2 olayın hiçbiri tekrarın içinde değil (tek seçim noktasıyla
  kırmızı köşenin kimliği klibin çoğunda belirsiz kaldı; kimlik (c)'nin konusu).
  Yayın aşaması örnek yayında 60,8–70,4 sn (üç koşu; 2a'da 61,1–71,7 sn),
  klipte 16,9 sn (poz 443,9 sn); analiz süresindeki artış ölçüm gürültüsünün
  içinde, ≈ %0 (örnek yayında poz 3091 sn).
- **Sınırlar:** tek bir örnek yayına ve sentetik malzemeye göre ayarlandı; gerçek
  tekrar içeren bağımsız bir kayıtla doğrulanmadı. Eşikler (ağır çekim oranı 0,65
  dahil) bu yüzden **geçicidir**. Scorebug'sız ve saatsiz
  yayında yalnızca logo geçişi + ağır çekim birlikte tekrar sayılır. Raunt
  içinde scorebug kaybolup saat de okunamazsa (tek sinyal) bölüm dışlanmaz.
  Köşe görüntüsü rauntlar bulunmuşsa "raunt arası", bulunamamışsa yine "ara"
  olarak dışlanır (raunt yokken "mola" adı verilemez).

## Kimlik takibi ve veri kalitesi (v2 Bölüm 2c, kimlik sürüm 7)

`backend/fight_analyzer/tracking/identity.py`, `tracking/quality.py`,
`frontend/src/model/scope.ts`, `model/quality.ts`. Ayarlar `IdentitySettings`
(yalnızca kimlik önbellek anahtarına girer). Kimlikler seçimden türetilen bir
**AI tahminidir**; emin olunamayan yerde "belirsiz" kalır.

- **Kaçan kamera kesimleri:** hazırlık, aynı zemine bakan iki kamera arasındaki
  kesimleri kaçırabilir (renk değişimi eşiğin altında kalır). Kimlik katmanı
  saklı kare değişim dizisinde tek başına duran tepeleri (≥ 0,03 ve çevre
  medyanının ≥ 6 katı; komşu karede yarısı kadar değişim yoksa) ek kesim sayar
  ve izleyicinin parça ile numaralarını orada böler. Hazırlık önbelleği ve
  anahtarı değişmez. `TrackingSummary.extra_cuts`, `shots` ve zaman çizelgesindeki
  kesimler bu kesimleri içerir.
- **Görünüm modeli (iki geçiş):** ilk geçiş yalnızca seçim karelerini kullanır.
  Güvenli ve temiz parçalardan dövüşçü başına videoya yayılmış en çok 40 örnek
  (şort ve gövde renk/doku tanımlayıcısı) ile iki dövüşçünün yanında en az 5 kare
  görülen dövüşçü boyundaki kişilerden en çok 60 "üçüncü kişi" örneği toplanır;
  ikinci geçiş aynı kuralları bu modelle çalıştırır. Konum bilgisi yokken
  (kesim, uzun kayıp) aday modele en az "en az tipik örnek − 0,08" kadar
  benzemelidir. Kutu yüksekliği oranı ölçülür ve raporlanır, karar için
  kullanılmaz (duruş ve kamera uzaklığıyla kareden kareye %20'ye varan
  oynama, aynı sıkletteki %1–3'lük boy farkını örter). Özet:
  `TrackingSummary.appearance`.
- **Örtüşmede doğrulama:** örtüşen kutudaki kare, kendi görünümü dövüşçüye diğer
  dövüşçüden ve üçüncü kişilerden 0,08 daha çok benziyorsa ve örtüşen başka bir
  kutu da aynı dövüşçüye benzemiyorsa "takipte"dir; değilse izleyici
  sürekliliğiyle taşınır ("örtüşme") ve kimlik güveni düşer (× 0,75 / × 0,45).
  Geriye dönük sahip değiştirme yapılmaz.
- **Örtüşen kutudan kurulan kimlik (sürüm 7):** kesimden ya da uzun kayıptan
  sonra kimlik örtüşen bir kutudan (tek karenin görünümüyle, iki kat farkla)
  kurulduysa, dövüşçü örtüşmesiz 5 karede (`acquire_confirm_frames`) kendi
  görünümüyle doğrulanana kadar kareleri "örtüşme" durumunda ve × 0,45 güvenle
  tutulur; ölçülebilir kalır, ama o karelerdeki olay "Kime ait belirsiz" olur.
  Doğrulanınca tutulan kareler olağan kurallara döner; önce kesim gelirse düşük
  güvenli kalır.
- **Olay sahipliği:** her olay `attribution_confidence` taşır (aktörün olay
  karelerindeki ortalama kimlik güveni). 0,5'in altı `attribution_uncertain`
  ("Kime ait belirsiz"): olay listede ve şimdilik sayımlarda kalır, momentuma
  puan eklemez; momentum kartı ve `MomentumTimeline.unattributed_event_ids` kaç
  olayın dışarıda kaldığını gösterir. Bölüm 3'te dövüşçü sayımlarından çıkıp
  ayrı bir "belirsiz" sayısı olacak; puanlamadaki ağırlığını Bölüm 4 belirleyecek.
- **Veri kalitesi:** kare başına "ölçülemez" ve dört neden (eksik görüntü, uzak
  ya da kötü kamera açısı, örtüşen dövüşçüler, düşük görüntü kalitesi:
  çözünürlük, bulanıklık, düşük eklem güveni). Bir aralığın özeti: ölçülebilir
  süre oranı, örtüşme oranı, belirsiz süre, en uzun belirsiz aralık, geçici
  numara değişimi ve nedenlerin payı; dışlanan bölümler dövüş süresi sayılmaz.
  `GET /jobs/{id}/tracking/quality` tüm maç ve her etkin raunt için döner;
  tarayıcı aynı hesabı `GET /jobs/{id}/tracking/timeline` verisinden
  (`quality`, `changes`) oynatma anına kadar olan kapsam için yapar. İki taraf
  `shared/fixtures/track-quality.json` ile denetlenir.
- **Zaman kapsamı:** sonuç ekranında videonun altındaki **Kapsam** seçici (Şu ana
  kadar · Raunt · Tüm maç) iki yan paneldeki istatistiklerin ve veri kalitesinin
  aralığını belirler; her grubun altında aralık yazar. Momentum her zaman
  oynatma anındaki değerdir. Kapsamı kareye çeviren tek fonksiyon
  `model/scope.ts` → `scopeRange`.
- **Eski analizler:** açılır; kimlik sürümü 6'dan küçükse "eski sürümle yapıldı
  — yeniden işle" bandı çıkar ve veri kalitesi "tüm video" etiketiyle eski
  toplamları gösterir.
- **Ölçüm (ayar için kullanılan malzeme; doğruluk değeri değildir).** Örnek yayın
  (topuria-volkanovski.mp4, 9:00), aynı seçim; "önce" kimlik sürüm 5:

| Kapsam | Dövüşçü | | Geçici numara değişimi | Örtüşme | Belirsiz | En uzun belirsiz | Ölçülebilir |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tüm video | Volkanovski (kırmızı) | önce | 90 (eski sayım: 124) | %23,4 | 59,1 sn | 22,1 sn | %82,9 |
| | | sonra | 102 | %6,5 | 31,0 sn | 8,2 sn | %89,3 |
| | Topuria (mavi) | önce | 87 | %24,9 | 21,3 sn | 4,3 sn | %90,8 |
| | | sonra | 89 | %4,5 | 19,8 sn | 4,3 sn | %92,4 |
| Dövüş süresi (R1+R2) | Volkanovski | önce | 89 | %24,5 | 35,5 sn | 11,6 sn | %86,7 |
| | | sonra | 99 | %6,4 | 12,2 sn | 1,6 sn | %92,7 |
| | Topuria | önce | 82 | %24,6 | 14,7 sn | 3,2 sn | %93,2 |
| | | sonra | 86 | %3,9 | 8,5 sn | 2,1 sn | %95,1 |
| R1 | Volkanovski | önce → sonra | 51 → 59 | %24,8 → %4,6 | 17,8 → 3,7 sn | 11,6 → 1,3 sn | %88,8 → %94,6 |
| | Topuria | önce → sonra | 51 → 54 | %23,8 → %4,2 | 11,0 → 8,1 sn | 3,2 → 2,1 sn | %91,8 → %93,6 |
| R2 | Volkanovski | önce → sonra | 38 → 40 | %24,2 → %9,0 | 17,7 → 8,5 sn | 4,4 → 1,6 sn | %83,7 → %90,0 |
| | Topuria | önce → sonra | 31 → 32 | %25,9 → %3,5 | 3,7 → 0,4 sn | 1,2 → 0,1 sn | %95,3 → %97,1 |

  Hazırlıkta 36 kesim bulunmuştu, 34 ek kesim bulundu. Sentetik tekrar klibinde
  (83 sn) kırmızı köşe belirsiz 73,0 → 1,7 sn, olay 2 → 15, tekrarın içindeki 2
  tekme dışlandı. 108 karelik gözle denetimde 107 kare doğru, 1 yanlış (maç
  sonrası seyirci çekimi; düzeltildi). Örtüşen kutudan 44 kimlik kuruldu, 40'ı
  onaylandı; onaylanmayan 4'ünün kareleri (toplam 1,8 sn) düşük güvenli.
  Kimlik adımı 2,7 → 6,4 sn (poz çıkarımı 3091 sn: toplam süreye etkisi ≈ %0,1).
- **Sınırlar:** tek yayınla ayarlandı; şort renkleri çok farklıydı. Geçici numara
  değişimi sayısı düşmedi (kesim sayısı arttı; bu bir izleyici ölçüsüdür).
  Bulanıklık/çözünürlük eşikleri bu yayında tetiklenmedi. Dışa aktarılan JSON'da
  raunt bazlı kalite özeti yok (Bölüm 4'te `JudgingResult.data_quality` ile
  gelecek).

## AI hakemlik (Aşama 9)

`backend/fight_analyzer/judging/`, `GET /jobs/{id}/scorecards`, sonuç ekranında
"Hakem kartları (AI)" sekmesi. Ayrıntılı kullanım: [docs/KULLANIM.md](docs/KULLANIM.md)
bölüm 4a. Her çıktı `ai_estimate: true` ve "resmi hakem kararı değildir" notunu taşır.

- **Kullanıcı girdisi (`PUT /jobs/{id}/match`, `MatchSetup`):** planlanan raund
  sayısı ve süresi, raund sınırları (kare), bitiş şekli (bilinmiyor, puan kararı,
  KO, TKO, submission, diskalifiye, hakem/doktor durdurması, no contest; bitişlerde
  kazanan zorunlu), puan kesintileri. Kaydetmek hiçbir şeyi yeniden hesaplatmaz;
  kartlar önbellekteki analizden istek anında hesaplanır.
- **Raund kanıtı** (dışlanan bölümler hariç): olası knockdown ve takedown (güven
  ≥ 0,5; altındakiler gösterilir, puanlanmaz), kontrole dönen takedown, üst
  kontrol süresi, vuruş denemeleri, olası temas ve **olası etki**, ilerleme/geri
  çekilme, ölçülebilen süre, kimlik belirsizliği. Olası etki yeni bir ölçüdür
  (`EVENTS_VERSION 2`): olası temaslı vuruşun tepe anından sonraki 0,25 sn içinde
  rakibin başı omuzlarına göre ≥ 0,3 gövde boyu savrulursa (hemen önceki hareketi
  düşülerek). Sentetik testte isabet/blok/erken baş hareketi ayrılıyor; 9 dakikalık
  gerçek maçta 60 ölçülebilir temasın 1'i eşiği geçti. Eşik doğrulanmadı.
- **Kriter sırası:** 1) etkili vuruş/grappling (etki 1, yalnız temas 0,3, temassız
  deneme ≈ 0,05, knockdown 4,5–5, takedown 2–3 + kontrole dönerse ek, kontrol
  saniyesi) — belirleyici farkı varsa raundu o belirler; 2) etkili agresiflik
  (baskı + deneme) yalnızca 1 denkse; 3) alan kontrolü (net ileri hareket + üst
  pozisyon) yalnızca 1–2 denkse; hiçbiri ayırmazsa 10-10. 10-8: etki şart
  (knockdown ya da ≥5 olası etkili vuruş ve rakibin 3 katı) + baskınlık/süre;
  10-7: etki, baskınlık, süre birlikte + çoklu knockdown. Momentum kullanılmaz.
- **Üç hakem:** A vuruş etkisine, B takedown/kontrole biraz daha ağırlık verir, A
  10-8 için iki koşulla yetinir; C daha büyük fark ister, 10-8 için üç koşul ve
  daha güçlü baskınlık arar, 10-7 vermez. Kartlar → oybirliği/bölünmüş/çoğunluk
  kararı ve beraberlik türleri. Puan kesintileri ilgili raunt puanından düşülür.
- **Ne zaman sonuç yok:** bitiş girilmişse sonuç kullanıcının bitişidir, kartlar
  bilgi amaçlıdır; puan kararı ancak planlanan raundların hepsi işaretli ve
  puanlanabilirse hesaplanır; aksi halde "hesaplanmadı" ve nedeni (kayıt sonunda
  olası knockdown varsa olası bitiş uyarısı). Raunt en az 30 sn kayıt ve dövüşçü
  başına 15 sn ölçüm ister; yoksa puanlanmaz, toplama girmez.
- **Güven:** ölçüm kapsamı, kimlik belirsizliği, eksik raund, yerde geçen süre
  (üstten vuruşlar sayılmıyor), kamera ölçümü, işaretsiz raund, kanıt türü ve
  hakem uyumundan; bağımsız doğrulama olmadığı için en fazla "orta".
- **Gerçek maçla deneme** (kullanıcının 9 dakikalık Topuria–Volkanovski analizinin
  kopyası; skor tabelası saatinden R1 00:11–05:11, R2 05:18–08:50 işaretlendi):
  bitiş girilmeden "hesaplanmadı: 2/3 raund"; KO (Topuria, R2 3:32) girilince
  sonuç "Topuria KO ile kazandı (kullanıcı girdisi)". Kartlar her iki raundu
  Volkanovski'ye 10-9 verdi (olası temas 22–17, 21–16; olası etki 0–0 ve 1–0) ve
  her hakem "etkili vuruş kanıtı zayıf" uyarısı ekledi; raund güveni %42–46.
  2. rauntaki nakavt knockdown olarak tespit edilmedi. Bu kartlar maçın gerçek
  akışını yansıtmayabilir; tek bir örnek doğruluk göstermez.

## Doğrulama ve dayanıklılık (Aşama 8)

### Klipler: ayar ve değerlendirme ayrımı

- **Görsel referans:** kullanıcının tanıttığı video (ekranı telefonla çekilmiş bir
  sosyal medya kaydı) yalnızca arayüz düzeni için kullanıldı: üstte momentum
  çubuğu, iki yanda istatistik panelleri, ortada iskeletli video, altta
  momentum zaman çizelgesi. Doğruluk ölçümü için kullanılamaz (maç görüntüsü değil).
- **Ayar seti:** `topuria-oliveira.mp4` (10,9 sn yayın kesiti). Kimlik takibi ve
  olay kuralları Aşama 4–5'te bu klipte görülen hatalara göre ayarlandı; bu yüzden
  aşağıdaki sayılar **iyimserdir** ve yeni görüntülerdeki doğruluğu göstermez.
- **Değerlendirme seti: yok.** Bilgisayarda bundan başka doğrudan maç görüntüsü
  bulunamadı (masaüstü, İndirilenler, Videolar, Belgeler tarandı). Bağımsız,
  gerçek maç doğrulaması **yapılmadı**; aşağıdaki hiçbir sayı doğruluk oranı
  değildir. Araç (`python -m fight_analyzer.validation`) yeni kliplerle aynı
  raporu üretmeye hazırdır (bkz. [docs/KULLANIM.md](docs/KULLANIM.md) bölüm 7).

### Elle etiketli küçük örnek (ayar seti)

Etiketler `validation/labels/topuria-oliveira.tuning.json`, rapor
`validation/reports/topuria-oliveira.tuning.json`. Kimlik: her 10 karede bir
(33 kare × 2 köşe = 66 durum), kişiler kimlik sonucu gösterilmeden numaralı
kutulardan etiketlendi. Vuruş: 0–110. kareler (ayakta mücadele, klinç mesafesi,
nakavt, yerde vuruşlar) kare kare izlenerek etiketlendi (±3 kare).

| Senaryo (klipte) | Sonuç |
|---|---|
| Net ayakta mücadele (kare 0–19) | 4/4 doğru kişi |
| Klinç / önden geçme, düşüş (20–39) | 4/4 doğru kişi |
| Yerde mücadele (40–79) | 7/8 doğru; kare 70'te mavi köşe, Topuria'nın kolu ile Oliveira'nın başını birlikte saran birleşik kutuya bağlı (“başka kişi”) |
| Hakemin araya girmesi (80–110) | 6/6 doğru kişi; Oliveira'nın ayrı kutusu olmayan 2 karede kimlik doğru şekilde “belirsiz” (hakeme kaymadı) |
| Kamera değişimi + yakın çekimler (120–320) | 21/21 doğru kişi, 21/21 görünmeyen dövüşçü doğru şekilde atanmadı |
| Kimlik karışması / hakeme kayma | 0 / 0 |
| Belirsiz takip süresi (tüm klip) | kırmızı 3,47 sn, mavi 3,30 sn; çoğu dövüşçünün gerçekten kadrajda olmadığı yakın çekimler |
| Vuruş denemeleri (10 etiket) | 4 eşleşti (kare 8, 11, 18, 74), 6 kaçırıldı, 1 yanlış tespit (kare 9, Oliveira) |

Kaçırılanlar: nakavt vuruşu (kare 27; vuran kol kameraya uzak tarafta,
Oliveira'nın gövdesinin arkasında), Oliveira'nın gövdeye vuruşu (24) ve yerdeki
dövüşçüye üstten atılan 5 vuruştan 4'ü (kurallar ayakta, üst gövdeye uzanan
denemelere göre). **Klipte olmayan senaryolar:** benzer şort renkleri, tekrar
ve ağır çekim (yalnızca son 3 kare donuk); bunlar denenmedi.

### Tekrar ve ağır çekim: bölüm dışlama

Tekrarlar tek kareye bakarak canlı görüntüden ayrılamaz (aynı dövüşçüler, aynı
kafes). v2 Bölüm 2b'den beri yayın sinyallerinden ve raunt sınırlarından otomatik
dışlanırlar (bkz. "Yayın kesmeleri ve tekrar ayıklama"); kullanıcı ayrıca sonuç
ekranında **"Bölüm dışla…"** ile başlangıç/bitiş karesi ve neden (tekrar, ağır
çekim, raunt arası/ara, giriş, maç sonrası, duraklama, mola, diğer) seçebilir. Dışlanan
bölümün anlamı otomatik ve elle için aynıdır; tanım tek yerde
(`motion/exclusions.py`) ve tarayıcıda aynısı (`model/measured.ts`):

- Dışlanan bölüm maç süresi değildir. Anı (tepe karesi, yoksa başlangıç) içinde
  kalan olay listede "Dışlandı" etiketiyle görünür ama sayılmaz, momentuma puan
  eklemez ve efekt çizilmez.
- Süreye bağlı puanlar (ilerleme, yer kontrolü) parçalara bölünür; dışlanan
  kısım puan getirmez. Kontrol süresi ve ölçülen süre orada birikmez; 10 Hz
  örnekler ölçüm sayılmaz.
- Momentum maç zamanıyla söner: dışlanan bölüm boyunca **donar**, sonra kaldığı
  yerden devam eder.
- Pozlar, kimlikler ve olay tespiti değişmez; yalnızca momentum yeniden
  hesaplanır (önbellekten, saniyeler içinde). Dışlama kaldırılınca önceki sonuç
  önbellekten birebir geri gelir. MP4'te "Dışlanan bölüm" etiketi, CSV'de
  `excluded` sütunu, JSON'da `exclusions` ve `excluded_event_ids` bulunur.
- Ortak test dosyası (`shared/fixtures/frame-metrics.json`) iki dışlanan bölüm
  içerir; tarayıcı ve dışa aktarma 330 karede aynı sonucu verir.

### Dayanıklılık (gerçekten yapılan kontroller)

Gerçek klip, temiz veri klasörü, gerçek işçi (i5-12450H, CPU, yolo26s):

| Kontrol | Sonuç |
|---|---|
| İlk analiz (327 kare: video hazırlama + poz + takip hazırlığı) | 63,4 sn; poz 148–172 ms/kare (5 koşu), yolo26n 68 ms/kare |
| Aynı videoyu yeniden yükleme | 0,1 sn; video kopyası ve pozlar önbellekten (aynı anahtar) |
| Poz ayarı değişince (`FA_POSE_CONF`) | yeni anahtar, pozlar yeniden çıkarıldı (56 sn), video kopyası yeniden kullanıldı |
| Önbellek dosyasında tek bayt bozulunca | SHA-256 uyuşmazlığı yakalandı, kayıt silindi, aynı anahtarla yeniden üretildi |
| Poz sırasında iptal (32. kare) | 0,6 sn'de durdu, "Kullanıcı tarafından iptal edildi", yarım önbellek yazılmadı |
| İptalden sonra yeniden başlatma | tamamlandı (2. deneme), video kopyası önbellekten |
| Çalışan işçi süreci zorla öldürüldü (`taskkill /F`) | iş "çalışıyor" kaldı; yeni işçi 30 sn kalp atışı sınırından sonra işi geri aldı ve bitirdi (toplam 88 sn) |
| CPU/GPU seçimi | bu makinede CUDA yok: `auto` ve `cpu` → CPU; `cuda` istenince CPU'ya geçip uyarı gösterir (durum çubuğu). GPU yolu bu makinede denenemedi. |
| Bozuk dosya, boyut/süre/çözünürlük, boş dosya, yanlış tür | testlerde (`test_upload_api.py`) anlaşılır Türkçe mesajlarla reddedilir; yeni: disk dolu (507), çok fazla aktif analiz (429) |

**Uzun video ve bellek:** klip 30 kez art arda eklenerek 5 dk 28 sn, 9842 kare,
1280×720 bir video yapıldı (sesli). Tüm akış (yükleme → poz → otomatik seçim →
kimlik/olay/momentum → MP4 dışa aktarma) bellek örneklenerek çalıştırıldı:

- İlk koşu: en yüksek RSS 1191 MB, olay aşamasında. Nedeni grafik maskesinin her
  kamera çekimi için iki tam çözünürlüklü dizi tutmasıydı (≈180 çekim). Düzeltme:
  maske en uzun 24 çekimden hesaplanır (`MAX_OVERLAY_SHOTS`, `CAMERA_VERSION 2`);
  `tracemalloc` ile maskenin payı +180 MB'ta sabit kalır, video uzadıkça büyümez.
  Aynı video yeniden ölçüldüğünde olay aşamasındaki artış +536 MB'tan +234 MB'a
  indi (o koşuda pozlar önbellekten geldiği için model yüklü değildi; en yüksek
  546 MB). Poz aşaması (model yüklü) 779 MB, dışa aktarma 451–706 MB.
- Video uzunluğuyla büyüyen kısımlar küçük: 5,5 dakikada poz dizileri ≈ 7 MB,
  görünüm özellikleri ≈ 18 MB, kinematik ≈ 19 MB.
- Süreler: poz 1805 sn (başka testler aynı anda çalışırken), kimlik + olay +
  momentum 140–164 sn, MP4 dışa aktarma 239–265 sn (sesli, 168 MB). Sonuç API'leri
  hafif: hareket 314 KB, momentum 104 KB, olaylar 25 KB, takip şeridi 63 KB; dördü
  0,09 sn'de okundu.
- Tarayıcı: poz parçaları artık en fazla 40 parça (≈6000 kare) tutulur, en eski
  kullanılan atılır (`hooks/chunkCache.ts`); önceden uzun bir videoyu baştan sona
  izlemek tüm kareleri bellekte biriktiriyordu.
- Bu koşuda seçim otomatik yapıldı (adaydaki en büyük iki kişi) ve mavi köşe
  olarak **hakem** seçildi; bu yüzden uzun videonun kimlik sayıları
  değerlendirilmedi, koşu yalnızca süre ve bellek içindir.
- 60 dakikalık video bu CPU'da poz için ≈ 5 saat süreceğinden çalıştırılmadı.

**İleri/geri sarma ve yeniden seçim:** sayaçlar ve momentum gösterilen karenin
saf fonksiyonudur (Aşama 6–7'de tarayıcıda 9/9 ve 31/31 karede doğrulandı);
Aşama 8'de kabul testinde yeniden denendi (aşağıda).

### Kabul testi: gerçek klip, baştan sona (tarayıcıda)

Temiz veri klasörü, `start.cmd` ile başlatılan uygulama (API + işçi + arayüz),
uygulama içi tarayıcı. Dosya, tarayıcının dosya penceresi kullanılamadığı için
yükleme alanına programla verildi; doğrulama ve gönderme arayüzün kendi yolundan geçti.

1. **Yükleme:** tarayıcı doğrulaması (2,1 MB, 00:10, 1280×720) → "Analizi başlat"
   → işlem ekranı; video hazırlandı, poz 8,5 kare/sn ile canlı önizlemeli ilerledi.
2. **İptal ve yeniden başlatma:** 168. karede "İptal et" → onay → iş iptal edildi
   ("Kullanıcı tarafından iptal edildi"); "Analizi yeniden başlat" → video kopyası
   önbellekten, poz yeniden (49,7 sn), 6 aday kare.
3. **Dövüşçü seçimi:** aday 1'de Topuria (kırmızı) ve Oliveira (mavi) kutularına
   tıklandı, isimler yazıldı, "Onayla ve takibi başlat".
4. **Analizi izleme:** kimlik, olaylar, momentum tamamlandı (7 olay, son kırmızı
   payı %62,39).
5. **Olaya atlama:** olay listesinde olası knockdown'a (tepe karesi 68) tıklandı →
   video 38. kareye (1 sn önce) gitti.
6. **Sarma tutarlılığı:** 6 karede (70, 212, 12, 38, 300, 99) momentum ve iki
   paneldeki tüm sayılar, 2× ve 0,25× oynatma ile ileri/geri sarmadan önce ve
   sonra birebir aynıydı.
7. **Bölüm dışlama:** 70–80. kareler "Tekrar" olarak dışlandı → 77. karedeki
   yumruk "Dışlandı" oldu, 100. karede kırmızı vuruş 3 → 2, aktivite 67 → 65,
   70–80 arasında "Dışlanan bölüm" etiketi ve momentum %61'de donuk, son pay
   %63 → %60; dışlama kaldırılınca önceki sonuç önbellekten birebir geldi.
8. **Yeniden seçim:** 150. karede kırmızı "görünmüyor", mavi Oliveira olarak
   düzeltme eklendi → pozlar ve hazırlık önbellekten, kimlik yeniden eşlendi;
   Oliveira'nın belirsiz süresi 6,9 → 3,3 sn (kalan kısım gerçekten kadraj dışı),
   sonuç ekranındaki paneller yeni değerleri gösterdi.
9. **MP4 dışa aktarma:** "Dışa aktar" → iş tamamlandı; indirme bağlantısı 200,
   `video/mp4`, `topuria-oliveira-analiz.mp4`, 4,4 MB, 327 kare, H.264 + AAC ses;
   160. karede düzeltilmiş mavi iskelet, momentum bandı ve "Takip belirsiz" rozeti.

Bu sırada bulunup düzeltilenler: iptal edilen adım kırmızı "Hata" yerine
"İptal edildi" gösteriyor; başarısız/iptal edilmiş analiz için "Analizi yeniden
başlat" düğmesi eklendi (önceden yalnızca API'de vardı); hareket analizi sırasında
önizleme alanı "Video analiz kopyasına dönüştürülüyor" yerine çalışan aşamayı
yazıyor; CUDA uyarısı Türkçe.

## Veri sözleşmeleri (şema v1.10.0)

1.10.0 (v2 Bölüm 2c): `TrackingSummary` + `version`, `appearance`
(`AppearanceSummary`), `extra_cuts`; `FighterTimeline` + `quality`
(`QualityRun`, `QualityCause`), `changes`; `TrackQuality`, `CauseShare`,
`QualityScope`, `TrackQualityReport`; `FightEvent` + `attribution_confidence`,
`attribution_uncertain`; `MomentumTimeline.unattributed_event_ids`,
`ScoringSummary.unattributed_events`; `OutdatedReason` + `identity_outdated`.
Yeni alanların hepsi varsayılanlı: eski analizler açılır.

1.9.0: `ExclusionReason` + `timeout` (mola: raunt içinde scorebug yok ve saat
durmuş, tekrar belirtisi yok). `break` artık yalnızca raunt dışındaki bölümdür.

1.8.0 (v2 Bölüm 2b): `ExcludedSegment` + `source` (manual/auto), `auto_id`,
`confidence`, `signals`; `ExclusionReason` + `intro`, `post_fight`, `stoppage`;
`AutoExclusion` (+ `dismissed`), `AutoExclusionEdits`; `Job.auto_exclusions`;
`BroadcastSummary.version`, `.segments`, `.scorebug_frame`; `OutdatedReason` +
`broadcast_outdated`. Yeni alanların hepsi varsayılanlı: eski analizler açılır.

1.7.0 (v2 Bölüm 2a): `BoutConfig`, `RoundSegment`, `RoundEdits`, `ScreenRect`,
`ScorebugRegion`, `BroadcastSummary`, `BroadcastTimeline`; `Job.bout`,
`Job.rounds`, `Job.round_notes`, `Job.outdated`; `MatchSetup.cleared_rounds`;
`PipelineStage.broadcast`.

Kaynak: `backend/fight_analyzer/contracts/`. JSON Schema
`python -m fight_analyzer.contracts.export` ile, TypeScript tipleri
`npm run gen:types` ile üretilir; testler ikisinin de güncel olduğunu denetler.

| Sözleşme | İçerik |
|---|---|
| `Job`, `JobList` | iş kimliği (uuid4 hex), tür (`analysis` / `export`), durum, aşama, ilerleme + `StageProgress` (birim, yapılan/toplam, hız, tahmini süre), kaynak video, çıktılar (analiz kopyası, poz özeti), hata, zamanlar |
| `SourceVideo`, `AnalysisVideo` | yüklenen dosya (ad, boyut, SHA-256, codec, boyutlar, fps, süre, döndürme, ses) ve analiz kopyası (VideoInfo, SHA-256, önbellek anahtarı, dönüştürme ayarları) |
| `VideoInfo` | genişlik, yükseklik, fps (tam değer `fps_num/fps_den`), kare sayısı, süre (ms), codec, uygulanan döndürme, ses |
| `KeypointName` | 17 COCO eklemi, model çıktı sırasıyla (0 = burun … 16 = sağ ayak bileği) |
| `PoseCacheManifest`, `PoseChunk`, `PosePreview` | önbellek manifesti (anahtar girdileri, model, ayarlar, dizi dosyaları ve özetleri), arayüze giden kare penceresi, canlı önizleme |
| `UploadLimits`, `ErrorResponse` | yükleme sınırları, API hata gövdesi |
| `PoseSequence` → `FrameRecord` → `PersonDetection` | kare numarası, zaman damgası (ms), kutu, tespit güveni, 17 COCO eklemi (`x`, `y`, `confidence`), ham `track_id`, `fighter_id` |
| `Fighter`, `FighterId` | `fighter_a` / `fighter_b`, ad, renk |
| `FighterSelection` → `FighterAnchor` | seçim noktaları: kare + kırmızı/mavi tespit numarası (`null` = o karede görünmüyor; her dövüşçü en az bir kez seçilmeli) |
| `SelectionCandidates`, `FighterNames` | aday kareler ve tespitleri; köşe adları |
| `TrackingPrepSummary`, `TrackingSummary`, `TrackingTimeline` | kesimler, çekimler, izleyici; dövüşçü başına takip ölçümleri, belirsiz aralıklar ve nedenleri, kontrol noktaları; şerit verisi |
| `FighterFrameState` | karede dövüşçü durumu: `tracked` / `occluded` / `uncertain`, tespit, güven |
| `EventTimeline`, `FightEvent` | olay türü (yumruk/tekme/diz denemesi, klinç, yer kontrolü, olası takedown/knockdown, duruş değişimi), yapan/hedef dövüşçü, başlangıç–zirve–bitiş karesi ve ms, uzuv, olası temas, vuran eklemin konumu, karar verdiren ölçümler, güven |
| `MotionTimeline`, `FighterSignals` | 10 Hz örnekler: geçerlilik, aktivite, el/ayak hızı, rakibe yaklaşma hızı, ilerleme/geri çekilme, duruş; kamera hareketinin bilindiği örnekler; dövüşçüler arası mesafe |
| `MomentumTimeline`, `MomentumContribution`, `MomentumParameters` | puan defteri (kaynak, olay, zaman, miktar, puan), tasarım parametreleri, kırmızı payı ve "veri yetersiz" örnekleri |
| `EventsSummary`, `ScoringSummary` | iş çıktısı özetleri (dövüşçü başına sayılar, kamera ölçüm oranı; parametreler, son pay) |
| `MatchSetup` → `RoundMark`, `MatchEnding`, `PointDeduction`; `Scorecards` → `RoundAssessment`, `FighterRoundEvidence`, `KeyMoment`, `JudgeScorecard`, `JudgeRoundScore`, `RoundSummary`, `MatchVerdict` | maç bilgileri (kullanıcı girdisi) ve AI hakem kartları: raund kanıtı, üç hakem, raund özetleri, karar/bitiş, güven, uyarılar (`ai_estimate: true`) |
| `SegmentExclusions`, `AutoExclusionEdits` → `ExcludedSegment`, `AutoExclusion` | dışlanan bölümler (başlangıç/bitiş karesi, neden, kaynak elle/otomatik, güven, sinyaller); kullanıcınınkiler `Job.exclusions`, otomatikler `Job.auto_exclusions` (geri alınanlar dahil), uygulanan liste `ScoringSummary.exclusions` ve `MomentumTimeline.exclusions` |
| `ExportRequest` → `ExportOptions`, `ExportSummary`, `ExportFile`, `SourceKeys`, `AnalysisExport` | videoya işlenecek göstergeler (iskelet, efektler, momentum, sayaçlar, mesafe, diğer kişiler); dışa aktarma işinin çıktısı (kare sayısı, ses, dosyalar, kaynak önbellek anahtarları); dışa aktarılan JSON |
| `HealthResponse` | veritabanı, işçi, işlem birimi, FFmpeg, poz modeli, iş sayıları |

- Üst düzey belgelerin hepsinde `schema_version` bulunur. Kural: yeni opsiyonel
  alan/enum üyesi → minor, alan silme/anlam değişikliği → major.
- Koordinatlar `VideoInfo` boyutundaki piksellerdir (sol üst köşe orijin).
- Analiz çıktılarında `data_origin: "measured" | "demo"` zorunludur; demo veri
  ölçüm gibi sunulamaz. Her olayın ayrıca kendi `confidence` değeri vardır.
- Önbellek anahtarları sözleşme şema sürümüne değil, saklanan verinin kendi
  biçim sürümüne bağlıdır (poz, takip hazırlığı, kimlik, kamera, olaylar,
  momentum): yeni bir sözleşme alanı saatler sürebilen poz çıkarımını
  yeniden yaptırmaz.

## Ortam ve sürüm kararları (11 Ekim 2026'da doğrulandı)

İncelenen makine: Intel Core i5-12450H (8 çekirdek / 12 iş parçacığı), 15,7 GB
RAM, yalnızca Intel UHD grafik (**NVIDIA GPU yok → CPU**), Python 3.14.5,
Node 24.16.0. Sistemde FFmpeg yoktu.

| Bileşen | Sürüm | Not |
|---|---|---|
| Python | 3.14.5 | 3.13.0 da kurulu ama ilk yama sürümü; tüm tekerlekler cp314 için mevcut |
| PyTorch / torchvision | 2.14.0 / 0.29.0 | resmi PyTorch dizininden; CPU, CUDA 13.0 veya 12.6 |
| Ultralytics | 8.4.163 | resmi pose modelleri (YOLO11/YOLO26 `-pose`) ve OC-SORT izleyicisi |
| lap | 0.5.13 | Ultralytics izleyicilerinin doğrusal atama kütüphanesi |
| onnxruntime | 1.31.1 | scorebug OCR (PP-OCRv5 ONNX); 13 Kasım 2026'da eklendi, cp314 Windows tekerleği var |
| OpenCV | 4.14.0.94 | 5.0 yerine olgun 4.x hattı (Ultralytics `opencv-python` ister) |
| NumPy | 2.5.3 | |
| FastAPI / uvicorn / Pydantic | 0.141.1 / 0.54.0 / 2.13.5 | |
| FFmpeg | 7.1 (imageio-ffmpeg 0.6.0) | sistem kurulumu gerekmez; PATH'teki veya `FA_FFMPEG` önceliklidir |
| React / Vite / TypeScript | 19.3.0 / 8.3.4 / 6.0.3 | Vite 8.3.4: 6 Ekim güvenlik yamalarını içerir; TS 6.0 resmi Vite şablonundaki sürüm |

Seçim kuralı: en az 14 gün önce yayımlanmış en yeni kararlı sürüm; güvenlik
yaması gerektiğinde istisna (Vite). Python tarafında tüm bağımlılıklar
`backend/requirements/lock.txt` içinde, frontend tarafında `package-lock.json`
ile sabitlidir. `pip check` ve `npm audit` temizdir.

**CUDA:** `setup.ps1` NVIDIA sürücüsü bulursa CUDA yapısını kurar (sürücü ≥ 580
→ cu130, ≥ 560 → cu126). İşçi başlangıçta cihazı PyTorch ile algılar;
`FA_DEVICE=cpu|cuda|auto` ile zorlanabilir. Bu makinede yalnızca CPU yolu test
edilebildi.

## Gizlilik

- Tüm sunucular yalnızca `127.0.0.1`'e bağlanır; API, loopback dışı `Host`
  başlıklarını reddeder (DNS rebinding koruması); durum değiştiren istekler özel
  başlık ister, yabancı `Origin` reddedilir.
- Videolar ve sonuçlar `data/` altında kalır. Dosya yolları kendi klasörünün
  dışına çıkamaz (`fsutil.inside`: `..`, mutlak yol, sürücü harfi reddedilir;
  saklı kaynak yolu yalnızca `data/uploads` içini gösterebilir); iş kimlikleri
  32 hane onaltılık, dışa aktarma dosya türü sabit bir listeden seçilir.
- Sınırlar: yükleme boyutu/süresi/çözünürlüğü, aynı anda en fazla 20 bekleyen
  veya çalışan analiz (`FA_MAX_ACTIVE_JOBS`), analiz başına tek aktif dışa
  aktarma, yüklemeden önce boş disk denetimi (dosyanın iki katı + 2 GB).
- Güvenilmeyen nesne serileştirmesi yok: önbellekler JSON + `allow_pickle=False`
  NumPy dizileri; poz modeli yalnızca SHA-256'sı sabitlenmiş resmi dosyadan,
  `ULTRALYTICS_SAFE_LOAD=1` (torch `weights_only`) ile yüklenir.
- Dış bağlantı yok: Ultralytics `YOLO_OFFLINE=1` ile çevrimdışıdır, telemetri
  ve eğitim entegrasyonları ayar dosyasında da kapatılır (`data/ultralytics/`);
  analiz sırasında model indirilmez (yalnızca kurulum ya da açık komut; poz ve
  scorebug OCR modelleri aynı sabitli, SHA-256 doğrulamalı yoldan gelir);
  Swagger sayfası (CDN) kapalıdır; arayüz harici font/betik yüklemez. Bir test,
  Ultralytics'i içe aktarıp modeli çalıştıran ayrı bir süreçte loopback dışı her
  bağlantı ve DNS denemesini yakalar ve sıfır deneme bekler (kontrol olarak
  çevrimdışı mod kapatılınca denemeyi yakaladığını da doğrular).

## Ayarlar

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `FA_API_PORT` / `FA_WEB_PORT` | 8000 / 5173 | portlar |
| `FA_DATA_DIR` | `data/` | veritabanı ve dosyalar |
| `FA_DEVICE` | `auto` | `auto`, `cpu`, `cuda` |
| `FA_POSE_MODEL` | `yolo26s-pose.pt` | resmi kayıttaki pose modeli (`yolo26n/s`, `yolo11n/s`) |
| `FA_MODELS_DIR` | `data/models/` | model ağırlıkları klasörü |
| `FA_POSE_IMGSZ` / `FA_POSE_CONF` / `FA_POSE_MAX_DET` / `FA_POSE_BATCH` | 640 / 0,25 / 20 / 4 | poz çıkarım ayarları (önbellek anahtarına girer) |
| `FA_MAX_UPLOAD_MB` | 8192 | yükleme boyut sınırı |
| `FA_MIN_DURATION_S` / `FA_MAX_DURATION_S` | 0,5 / 3600 | süre sınırları |
| `FA_MAX_LONG_SIDE` / `FA_MAX_SHORT_SIDE` / `FA_MIN_SHORT_SIDE` | 3840 / 2160 / 144 | çözünürlük sınırları |
| `FA_ANALYSIS_MAX_SHORT_SIDE` / `FA_ANALYSIS_MAX_FPS` | 1080 / 30 | analiz kopyası |
| `FA_FFMPEG` | – | belirli bir ffmpeg.exe yolu |
| `FA_MAX_ACTIVE_JOBS` | 20 | aynı anda bekleyen/çalışan analiz sınırı |
| `FA_MIN_FREE_DISK_MB` | 2048 | yükleme için gereken en az boş alan (+ dosyanın iki katı) |

Takip eşikleri (`TrackingSettings`), hareket ve olay eşikleri (`MotionSettings`)
ve momentum parametreleri (`MomentumSettings`) `backend/fight_analyzer/config.py`
içinde kodda tanımlıdır (ortam değişkeni yok); değiştirilen değer önbellek
anahtarına girdiği için ilgili aşama yeniden hesaplanır.

## Kontroller

`check.cmd` şunları çalıştırır: JSON Schema güncelliği, backend testleri (148
test; iş deposu, işçi, iptal/kurtarma, API, yükleme doğrulama ve sınırlar,
FFmpeg yoklama/dönüştürme/döndürme/zaman tabanı, poz önbelleği ve pickle
reddi, gerçek modelle uçtan uca poz + önbellek + yeniden açılış + seçim, kimlik
takibi ve hareketsiz fotoğrafta olay üretmeme, kamera hareketi, hareket ve
olaylar, momentum, yanıt verebilirlik, dışa aktarma: ortak test dosyası, efekt
zamanları, CSV, çizim, her karenin ve sesin korunması, iptal, API ile uçtan uca
MP4/CSV/JSON ve tarayıcı verisiyle eşleşme, dışlanan bölümler (defter, maç
zamanı, API), yerel güvenlik (yol sınırları, iş/disk sınırları, CDN sayfası yok,
analizde model indirme yok, ayrı süreçte dış bağlantı denemesi sıfır), sınırlı
grafik maskesi belleği, doğrulama aracı),
TS tiplerinin ve stil modülünün güncelliği, `tsc` (testler dahil), `oxlint`, ön yüz birim testleri
(`npm test`: Node'un yerleşik test çalıştırıcısı; oran/boşluk ve piksel
yoğunluğu hesabı, medya zamanından kare numarası 25/29,97/30/60 fps'te,
istatistiklerin ve momentumun yalnızca gösterilen kareye bağlı olması,
yüzdelerin toplamının 100 olması, ortak test dosyasında 325 karede istatistik,
momentum ve efektlerin dışa aktarmayla aynı olması — dışlanan bölümler dahil
330 kare —, poz parçası önbelleğinin sınırlı kalması) ve üretim derlemesi.

Kimlik takibi testleri (`backend/tests/test_tracking.py`) sentetik sahnelerde
gerçek doğruyu bilerek çalışır: kesim tespiti (hareket, flaş, aynı zeminli
kesim), dövüşçülerin çapraz geçmesi, hakemin araya girmesi ve bir dövüşçüyü
tamamen örtmesi, yere düşen dövüşçünün yanında diz çöken hakem, kısa klinç,
uzun örtüşme, kamera kesimi (konum değil görünüm), kesimden sonra tek dövüşçü,
benzer görünümlü dövüşçüler, kesim sonrası seyirci, örtüşen kutudan kimlik
kurmama, video ortasında seçim, düzeltme seçimi ve "görünmüyor" işareti,
seçimlerin birleştirilmesi. Her testte yanlış atama ve kimlik değişimi sayılır.

Hareket testleri (`test_motion.py`, `test_camera.py`) bilinen hareketlerle
çalışır: hareketsiz görüntü (titreşimli) → hiç olay yok ve %50/%50; tek yumruk
25/30/50/60 fps'te tam bir deneme ve fps'ten bağımsız tepe hız; kombinasyonda
her yumruk, aynı anda iki kolda tek deneme; geriye savrulan kol, erişim dışı ve
düşük güvenli eklem → deneme yok; tekme ayrıca yumruk sayılmaz; kamera kayması
hareket sayılmaz, hareketli kamerada ilerleme doğru; vuruştan sonra düşüş →
olası knockdown, vuruşsuz düşüş → puansız duruş değişimi, yakın temastan sonra
düşüş → olası takedown; alttaki dövüşçünün hareketi ve yerdeki rakibin üstüne
inmek puan getirmez; kimlik doğrulanmamışken olay yok; defter, yarı ömür,
formül, olay etkisi ve önbellek gidiş-dönüşü. Kamera testleri bilinen
kaydırma/yakınlaştırmayı skor çubuğu ve hareket eden kişiye rağmen ölçer,
ölçülemeyen karede zinciri kırar ve grafikleri çekimler arasında bulur.

## Bağımlılıkları güncelleme

1. `backend/requirements/base.in`, `dev.txt` ve `torch-*.txt` içindeki sabit
   sürümleri değiştirin.
2. Temiz bir ortamda `pip install -r torch-cpu.txt -r base.in -r dev.txt`,
   ardından `pip check`.
3. `pip freeze` çıktısından `torch`/`torchvision` satırlarını çıkarıp
   `lock.txt`'e yazın; `check.cmd` ile doğrulayın.
