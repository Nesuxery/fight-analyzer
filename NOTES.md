# Proje notları: önemli kararlar ve kalan işler

Son güncelleme: 27 Kasım 2026 (v2 Bölüm 3b kararları uygulandı: gizli rakip çıkarımı, raunt başının
saatten geriye hesaplanması, büyük poz modeli denemesi, Bölüm 4 notu plana işlendi). Ayrıntılı
teknik açıklama [README.md](README.md), kullanım [docs/KULLANIM.md](docs/KULLANIM.md).
v2 kuralları kökteki [CLAUDE.md](CLAUDE.md) dosyasında; bu notlarla çeliştiği yerde
CLAUDE.md geçerlidir.

## Değişmeyen kurallar

- Her aşamada yalnızca istenen aşama yapılır; sonraki aşamalara kendiliğinden geçilmez.
- Ölçülmemiş değer gerçek analiz gibi gösterilmez. Örnek veri yalnızca Demo
  modunda ve "Demo" etiketiyle (`data_origin: "demo"`).
- Videolar ve sonuçlar bilgisayardan çıkmaz; analiz sırasında dış bağlantı yok.
- Referans depo (`odhabit-sys/ufc-fight-analyzer`) yalnızca ürün davranışı için
  incelenir; kod kopyalanmaz.
- Hakem kartları ve karar her zaman "AI tahmini, resmi sonuç değildir" olarak
  etiketlenir; momentum hiçbir zaman kazanma olasılığı ya da hakem puanı olarak
  kullanılmaz.

## Önemli kararlar

### Mimari
- Üç süreç: FastAPI (yalnız iş durumu), ayrı analiz işçisi (`python -m
  fight_analyzer.jobs`), Vite/React arayüzü. Hepsi `127.0.0.1`; `start.cmd` tek komut.
- İş kaydı SQLite (WAL); işçi kalp atışı, 30 sn sonra yarım iş yeniden kuyruğa,
  2 denemeden sonra `worker_lost`.
- Sürümlü Pydantic sözleşmeleri tek doğruluk kaynağı (şema şu an **1.13.0**);
  JSON Schema ve TS tipleri bundan üretilir, `check.cmd` güncelliğini denetler.
  Üretilen dosyalar (şema, TS tipleri, overlay dosyaları) `.gitattributes` ile her
  checkout'ta LF; denetim bayt bayt karşılaştırır ve gevşetilmedi.
- Önbellekler içerik adresli (anahtar = girdilerin özeti), pickle yok
  (JSON + `allow_pickle=False` .npy). Her önbelleğin kendi sürüm sabiti var
  (`KEY_SCHEMA "1.2.0"`, `IDENTITY_VERSION 7`, `CAMERA_VERSION 2`,
  `EVENTS_VERSION 6`, `MOMENTUM_VERSION 4`, `BROADCAST_VERSION 4`); mantık değişince
  ilgili sürüm artırılır, şema sürümü saatler süren poz çıkarımını yeniden yaptırmaz.

### Video ve poz
- Yüklenen video sabit kare hızlı, tarayıcıda oynatılabilir bir analiz kopyasına
  dönüştürülür (en fazla 1080p/30 fps, ses korunur); her şey bu kopyanın kare
  numaralarına bağlıdır.
- Poz: resmi Ultralytics YOLO26 pose (varsayılan `yolo26s`), SHA-256 sabitli,
  `ULTRALYTICS_SAFE_LOAD`, `YOLO_OFFLINE`. Model yalnızca kurulumda / açık komutla
  indirilir, analiz sırasında indirilmez.

### Kimlik takibi
- Çekim içi OC-SORT parçaları + görünüme (şort/gövde) dayalı kalıcı kimlik; kesimden
  sonra yalnızca görünüm. Kullanıcı birden çok karede seçim/düzeltme ve "bu karede
  görünmüyor" işareti ekleyebilir; yeniden seçim pozları yeniden çıkarmaz.
- Emin olunamayan yerde kimlik "belirsiz" kalır (yanlış atamak yerine).
- "Tarafları değiştir" seçim noktalarını ve adları takas eder; kişiye ait kullanıcı
  girdileri (bitişte kazanan, puan kesintileri) kişiyle birlikte taşınır. 8 Kasım
  2026'daki düzeltmeye kadar bu girdiler köşede kalıyor, yani diğer dövüşçüye geçiyordu.

### Hareket, olaylar, momentum
- Kamera hareketi arka plandan (LK + RANSAC, grafik maskesi) çıkarılır; hızlar gövde
  boyu/sn, fps'ten bağımsız. Düşük güvenli eklemler geçersiz.
- Vuruş = "deneme"; 2B örtüşme = "olası temas"; knockdown/takedown "olası".
  Aşama 9'da **olası etki** eklendi: temasın hemen ardından rakibin başının
  omuzlarına göre ≥0,3 gövde boyu savrulması (eşik doğrulanmadı). v2 Bölüm 3a'dan
  beri her vuruş ayrıca hedef bölge, tahmini sonuç (isabet/blok/ıska/belirsiz) ve
  önemli vuruş bilgisi taşır; hasar sinyalleri ayrı bir listedir (aşağıda). v2 Bölüm
  3b'den beri kare bazlı grappling durumu (mesafe, klinç, yerde kırmızı/mavi üstte,
  karmaşa) ve geçişlerinden takedown, deneme, ters çevirme, kalkma, olası submission.
- Momentum: açıklanabilir puan defteri, 20 sn yarı ömür,
  kırmızı % = 100·(m₁+4)/(m₁+m₂+8). Deneysel; "kazanma olasılığı değildir".

### Senkron ve dışa aktarma
- Tarayıcı `requestVideoFrameCallback` ile gösterilen kareye bağlı; istatistikler
  kare zamanının saf fonksiyonu (t = kare·1000/fps), biriktirilmez.
- Dışa aktarma ayrı bir iş (MP4 + CSV + JSON); tarayıcı ile aynı formüller
  (`export/frames.py` ↔ `model/measured.ts`), ortak test dosyası
  `shared/fixtures/frame-metrics.json` iki tarafta da denetlenir. Efekt süreleri ve
  renkler `shared/overlay-style.json` içinde tek kaynak.
- Videodaki ad etiketleri (12 Kasım 2026): tüm iskeletlerden sonra çizilir ve
  hiçbir zaman üst üste binmez, çerçevenin içinde kalır. Önce kafanın üstünde
  ortalanır ve çerçeveye sıkıştırılır; çakışan iki etiket, her biri kendi
  kafasının hizasını örtmeye devam edecek kadar yana itilir; yetmezse üst üste
  dizilir (kafası yüksekte olan üstte; yukarıda yer yoksa diğeri alta). MP4'te
  etiketler üst bandın altında kalır. Aynı kural ve aritmetik
  `frontend/src/player/labelLayout.ts` ↔ `backend/fight_analyzer/export/label_layout.py`;
  ortak test dosyası `shared/fixtures/label-layout.json` iki tarafta da denetlenir.

### Dışlanan bölümler (tekrar / ağır çekim)
- Dışlanan bölüm maç süresi değildir: olaylar sayılmaz/puanlanmaz, süreye bağlı
  puan ve ölçüm birikmez, momentum donar (maç zamanıyla söner). Otomatik ve elle
  dışlanan bölüm için anlam aynıdır.
- v2 Bölüm 2b'den beri otomatik de bulunur (aşağıdaki bölüm); kullanıcı ayrıca
  elle işaretleyebilir.

### Maç ayarları ve raunt tespiti (v2 Bölüm 2a, 13 Kasım 2026)
Bölüm 2 üç aşamada yapılıyor (a: maç ayarları ve raunt tespiti, b: yayın
kesmeleri ve replay ayıklama, c: kimlik takibi); bu kararlar (a) içindir.
- **Raunt kaynağı ve önceliği:** elle > scorebug saati (OCR) > raunt arası
  (pozlar). Elle girilen raunt (`MatchSetup.rounds`) aynı numaralı otomatiği ezer
  ve otomatik tespit onu asla değiştirmez; silinen otomatik raunt
  `cleared_rounds`'ta tutulur; elle rauntla çakışan ya da sırası tutmayan otomatik
  raunt notla dışarıda kalır. Birleştirme tek yerde: `fight_analyzer/rounds.py`;
  sonuç `Job.rounds`, hakem kartları da bunu kullanır. Raunt işaretleri kişiye ait
  değildir; taraf değiştirmede dokunulmaz.
- **Maç ayarları (`BoutConfig`):** raunt sayısı ve süresinin kaynağı artık burası;
  `MatchSetup`'taki aynı alanlar kopyalanır (eski analizlerde varsayılan olarak
  oradan okunur). Adlar tek kaynak olarak `params.names`'te kalır. Raunt
  seçenekleri ve süreler `RulesetSettings`'te (koda gömülü değil).
- **Saat alanı:** model kullanılmadan, ekranda sabit kalan ve videoyla geri sayan
  metin kutusu seçilir (arena ekranlarındaki saat kamerayla kaydığı için elenir).
  Raunt kutusunun okuma alanı saatten uzağa doğru genişletildi: örnek yayında
  R2'de "R2"nin önüne çubuk geliyor ve yazı kayıyordu (dar kutu boş okuyordu).
  Kısa "R1" kutusu düşük güvenle okunduğu için ayrı eşik (0,3) ve raunt başına oy.
- **Saat okuma kuralları:** okuma = (video zamanı, kalan saniye; ekran yukarı
  yuvarlar). Koşu yalnızca saat yukarı sıçrayınca biter (okunan raunt numarası
  tek başına bölmez); üç okumaya kadar tutarsız blok ve koşu kenarındaki tutarsız
  okuma atılır; 20 sn'den kısa koşu raunt değildir. Başlangıç tepeden geriye
  hesaplanır; 0:00'da biten tam, üstünde donan erken biten (`partial`), kaybolan
  son okumada kesilen sayılır.
- **OCR:** PaddleOCR `en_PP-OCRv5_mobile_rec` + `onnxruntime` 1.31.1 (kullanıcı
  onayıyla). OpenCV 4.14 DNN modeli yükleyemedi (dinamik `Reshape`). Model yalnızca
  kurulumda/açık komutla, sabit commit ve SHA-256 ile iner; yoksa saat okunmaz,
  analiz durmaz. Kaynak ve lisans README'de.
- **OCR'sız raunt arası tespiti:** pozlardan, düşük güvenle (≤ 0,5); ara
  bulunamazsa raunt iddia edilmez. Gerçek raunt arası içeren görüntü olmadığı için
  yalnızca kurallar sentetik testlerle denendi.
- **Ad önerisi:** yalnızca öneri; onaysız uygulanmaz ve dolu bir adın üstüne
  yazmaz (scorebug çoğunlukla soyadını gösterir); soldaki ad kırmızıya önerilir;
  büyük harften dönüşüm yerelden bağımsız (`ILIA` → `Ilia`).
- **Eski analizler:** açılır; `Job.outdated` doluysa "Bu analiz eski sürümle
  yapıldı — yeniden işle" bandı. Yeniden işleme kaynak video dosyasını ister
  (`video_prep` onu denetler).
- **Ölçüm (örnek yayın topuria-volkanovski.mp4, 9:00, ayar için kullanıldı;
  doğruluk değildir):** R1 10,5–310,5 sn (tam), R2 317,5–530,5 sn (kısmi, saat
  1:28'de durdu = resmi 3:32 KO); karelerden okunan saatle dört sınır da ±1 sn
  içinde. Yayın aşaması işçide 71,7 sn (tek başına 40–50 sn); poz 3091 sn'ye göre
  ≈ %2 ek süre. OCR'sız elle kurulum ≈ 6–8 etkileşim (bir dakikanın altında).
- **Yerel test malzemesi:** örnek videodan türetilen klip/kare ve karalama veri
  dizinleri yalnızca `local/` altında (`.gitignore`); repodaki testler tamamen
  sentetik (Pillow'un gömülü fontu ve Windows fontları).
- (a) onaylandı (14 Kasım 2026); `v2/bolum-2` dalında, merge/push kullanıcının
  sözüyle.

### Yayın kesmeleri ve tekrar ayıklama (v2 Bölüm 2b, 14 Kasım 2026)
- **Dört sinyal, en az ikisi dövüş dışı:** scorebug'ın kaybolması ya da tekrar yazısı;
  dövüş saatinin durması; logo geçişi; ağır çekim. "Tekrar" etiketi için tekrar
  yazısı, logo geçişi ya da ağır çekimden en az biri gerekir; yalnızca "scorebug
  yok + saat durdu" varsa bölüm tekrar değildir (kullanıcı kararı, 14 Kasım 2026):
  tek bir etkin rauntun tamamen içindeyse yerinde kalır ve **"mola"** (`timeout`)
  adını alır; **"ara" (`break`) yalnızca raunt dışındaki bölümdür** (kullanıcı
  kararı, 14 Kasım 2026; şema 1.9.0). Ad `nonfight.combine` içinde, istek anında
  verilir (etkin rauntları bilen tek yer); tespit önbelleği ve `BROADCAST_VERSION`
  (3) değişmedi, yeniden işleme gerekmez. Sinyaller yayın aşamasının
  aynı geçişinde (2 Hz) toplanır; logo geçişi takip hazırlığının kare değişim
  dizisinden, ağır çekim pozlardan gelir (yeni video okuması, yeni bağımlılık yok;
  hazırlık anahtarı değişmedi).
- **Saat çalışıyorsa görüntü canlıdır:** dövüş saatinin işlediği bilinen süre her
  adaydan çıkarılır. Raunt başında scorebug birkaç saniye geç geldiği (örnek
  yayında 3 sn) ve sponsor grafiği saati kapatabildiği için bu kural olmadan
  raundun ilk saniyeleri dışlanıyordu. Bilinmeyen sinyal kanıt sayılmaz.
- **Scorebug görünürlüğü OCR'sız ölçülür:** saatin çevresindeki şeridin, saatin
  okunduğu arama karelerinden öğrenilen medyan görünümüyle korelasyonu. Saat
  okuması tek başına yetmezdi (saniyede bir, OCR hatasına açık).
- **Ağır çekim yalnızca destekleyici:** eklem hızının canlı medyana oranı sakin
  dövüş anında da düşer; bu yüzden aday üretmez. Hız 0,1 sn'lik tabanla
  ölçülür (kare tekrarıyla yapılan ağır çekim tek kare farkında tam hızlı
  görünüyordu). Eşik 0,65: yarı hızdaki sentetik kopya 0,60 verdi, aynı görüntü
  canlıyken 0,99; canlı 6 sn'lik pencerelerin ≈ %1–3'ü bu eşiğin altında.
  **Sentetik veriyle ayarlandı, geçici:** bu eşik ve diğer tekrar eşikleri
  (`BroadcastSettings`) gerçek tekrar içeren bir kayıt gelene kadar geçicidir
  (kullanıcı kararı; kayıt bulursa verecek).
- **Dövüş dışı bölümler rauntlardan, yalnızca kesin olduğunda:** R1'den önce
  giriş, art arda numaralı rauntlar arası ara. Son raunttan sonrası yalnızca
  planlanan son rauntsa ya da kullanıcı o raunt için erken bitiş girdiyse "maç
  sonrası" sayılır; aksi halde orada bulunamamış bir raunt olabilir. Örnek yayın
  tam bu durumda (R2'de nakavt, 5 raunt planlı, saat durmadan kayboluyor):
  burada yayın sinyali devreye girer (son rauntten sonra scorebug hiç dönmüyorsa
  "maç sonrası", güven 0,6). Bu, plandaki "raunt içinde saat durursa stoppage"
  kuralına ek bir karardır.
- **Geri alınanlar aralık olarak saklanır** (`params.dismissed_auto`), kimlikle
  değil: otomatik bölüm, saklı aralıkla IoU ≥ 0,5 olduğu sürece kapalıdır. Raunt
  kenarı oynayınca kimlik değişir ama geri alma korunur; bölüm gerçekten
  değişince yeniden dışlanır. O an karşılığı olmayan aralıklar da saklanır
  (raunt geçici silinmişse geri gelince kapalı kalsın).
- **Tek etkin liste:** kullanıcının bölümleri + geri alınmamış otomatikler
  (`nonfight.effective`), her yerde `ScoringSummary.exclusions`.
- **Momentum API'de yenilenir:** raunt, maç ayarı, bitiş ve geri alma listeyi
  değiştirince momentum istek içinde yeniden hesaplanır (kullanıcının 9 dk'lık
  analizinde olayları okuma 0,06 sn + hesap 0,04 sn). İşçi üzerinden gitmek
  sonuç ekranını her raunt kenarı sürüklemesinde kapatıp açıyordu. İşçide olan
  ağır işler değişmedi; iş "tamamlandı" değilse liste işçinin momentum aşamasında
  uygulanır. Kullanıcının kendi bölümleri (`PUT /exclusions`) de aynı yoldan
  anında uygulanır (kullanıcı kararı): uç artık 202 yerine 200 döner, iş kuyruğa
  girmez; analiz işlenirken 409 `job_busy` verir.
- **Eski analizler:** yayın sürümü 2'den küçükse otomatik bölüm üretilmez (sonuç
  arkadan değişmesin) ve yeniden işleme bandı çıkar.
- **Saat alanı çizimi:** "Saat alanını düzelt" scorebug'ın göründüğü kareye geçer
  (`scorebug_frame`), bitince seçim karesi ve seçimler geri gelir.
- **Ölçüm (ayar seti; doğruluk değildir):** örnek yayın
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
- **Yerel malzeme:** sentetik klip `local/replay-clip/replay-synthetic.mp4`
  (git'e girmez); repodaki testler Pillow ile çizilen sentetik yayını kullanır
  (`tests/support/scorebug.py`, etiketli tekrar dahil).
- **Bilinen sınırlar:** gerçek tekrar içeren bağımsız kayıtla doğrulanmadı
  (kullanıcı bulursa verecek). Scorebug'sız ve saatsiz yayında yalnızca logo
  geçişi + ağır çekim birlikte tekrar sayılır. Raunt içinde scorebug kaybolur ve
  saat sonradan da okunamazsa tek sinyal kalır, bölüm dışlanmaz. Rauntlar yoksa
  köşe görüntüsü "ara" olarak dışlanır (scorebug yok + saat durdu).
- (b) onaylandı (14 Kasım 2026); `v2/bolum-2` dalında, merge/push kullanıcının
  sözüyle.

### Bölüm 2c için devam notları (14 Kasım 2026)
(c) 15 Kasım 2026'da yapıldı; kararlar bir sonraki başlıkta. Bu notlar o oturumun
girdisiydi. Sonraki oturum buradan başlar. Kurallar CLAUDE.md'de, plan docs/v2-plan.md
Bölüm 2.4–2.5'te; aşamadan sonra commit, notlar, kısa rapor, onay beklenir.

**(c) Kimlik takibi: kullanıcı kararları**
- "Kime ait belirsiz" olaylar momentuma girmez; formül ve ağırlıklar aynı kalır;
  momentum kartında bu yüzden dışarıda kalan olay sayısı gösterilir
  (`MOMENTUM_VERSION` 3).
- 2.5 kapsam seçicisi sade olur (yan paneller Bölüm 5'te kalkacak); kapsam hesabı
  Bölüm 5'in de kullanacağı yeniden kullanılabilir bir fonksiyon olarak yazılır.
- Önce/sonra tablosu: aynı video, aynı seçim (kare 3142, kırmızı det 0 / mavi
  det 1) karalama kopyasında; başlangıç değerleri: Volkanovski 124 numara
  değişimi / %23,4 örtüşme / 59,1 sn belirsiz / en uzun 22,1 sn; Topuria 87 /
  %24,9 / 21,3 sn / 4,3 sn. ~108 kare etiketleme tek tek değil, birkaç ızgara
  görselle yapılır. Sonuçlar "ayar seti" olarak etiketlenir.
- (b)'den kalan gözlem: sentetik tekrar klibinde (tek seçim noktası, kare 57)
  kırmızı köşe 83 saniyenin yalnızca 9,2'sinde ölçülebildi, mavi 79,5'inde; klipte
  2 olay çıktı. Kimlik iyileşmesini denemek için ikinci bir malzeme olarak
  kullanılabilir (karalama işi 45531e64).
- (b)'den kalan teknik not: dışlanan bölüm listesini değiştiren her uç
  `_refresh_momentum` çağırır; (c)'de "Kime ait belirsiz" olaylar momentumdan
  çıkınca `MOMENTUM_VERSION` 3 olur ve bu yol aynı kalır. Karalama kopyasındaki
  yayın önbelleği sürüm 3 anahtarıyla yeniden hesaplanır (≈ 60–70 sn).
- (c) sonunda yalnızca o aşamanın diff'ine tek, küçük bir inceleme ajanı açılabilir;
  kod okumak için ajan açılmaz (kullanım limiti dar).

**Çalışma ortamı**
- Karalama kopyası: `local/fa-data` (kullanıcının 80b67cce işi, önbellekler ve
  1,3 GB yükleme dosyası; yeniden işleme kaynak dosyayı ister; (b)'de eklenen
  sentetik tekrar klibinin işi 45531e64 de burada). `.claude/launch.json`
  "fa-scratch" yapılandırması buraya bakar (8010/5183). Kullanıcının gerçek işine
  dokunulmaz. `local/fa-data` ve `local/replay-clip` **Bölüm 3 bitene kadar
  kalır** (kullanıcı kararı, 16 Kasım 2026; önceki "Bölüm 2 bitince silinir"
  kararının yerine).

### Kimlik takibi ve veri kalitesi (v2 Bölüm 2c, 15 Kasım 2026)
Kod: `tracking/identity.py` (sürüm 7), `tracking/quality.py`, ayarlar
`IdentitySettings` (kimlik önbellek anahtarına girer; hazırlık anahtarına girmez).
- **Asıl kök neden kaçan kamera kesimleriydi.** Örnek yayında hazırlık 36 kesim
  bulmuş, 34'ünü kaçırmıştı (aynı kafes zeminine bakan iki kamera arasında renk
  histogramı 0,05–0,12 oynuyor, eşik 0,12; olağan değişim ≈ 0,004). İzleyici
  kaçan kesimden geçip dövüşçünün geçici numarasını yeni çekimde aynı yerde duran
  kişiye (ör. hakeme) veriyordu; karışık parça "üçüncü kişi" referansı oluyor ve
  dövüşçü bir daha bulunamıyordu (Volkanovski raundun ilk 12 saniyesinde açıkça
  görünürken belirsizdi). Hazırlık anahtarı ve önbelleği değiştirilmedi: kimlik
  katmanı saklı `cut_step` dizisinden tek başına duran tepeleri ek kesim sayar
  (`refine_cuts`: ≥ 0,03 ve çevre medyanının ≥ 6 katı; komşu karede yarısı kadar
  değişim varsa flaş/logo geçişidir) ve parça ile numaraları orada böler. Yeni
  video okuması yok.
- **Görünüm modeli iki geçişle kurulur** (plandaki "en az 20 kesit"): ilk geçiş
  yalnızca seçim karelerini kullanır; güvenli (≥ 0,75), temiz (örtüşmesiz)
  parçalardan dövüşçü başına videoya yayılmış en çok 40 örnek (kısa videoda daha
  azı çıkar, model olanla kullanılır; sentetik klipte 17 / 32) ve iki dövüşçünün
  yanında ≥ 5 kare görülen dövüşçü boyundaki kişilerden (hakem, köşe ekibi) en
  çok 60 "üçüncü kişi" örneği alınır; ikinci geçiş aynı kuralları bu modelle
  çalıştırır. Örnek yayında 38 / 40 örnek (34 / 36 çekimden) ve 52 üçüncü kişi.
- **Üçüncü kişi yalnızca dövüşçü boyundaysa referanstır.** Kafes arkasındaki
  küçük seyirciler kaba görünümleriyle kırmızı köşeye %92–94 benziyor ve onu
  eliyordu; zaten kimlik alamadıkları için (kutu < en büyüğün %35'i) referans da
  olmazlar.
- **Konumsuz yerleştirmede model tabanı:** kesimden ya da uzun kayıptan sonra
  aday, dövüşçünün en az tipik örneğinin diğer örneklerine benzerliği − 0,08
  kadar modele benzemelidir (örnek yayında ≈ 0,88). Bu eşik, maç sonrası seyirci
  çekiminde kırmızı-beyaz bayraklı bir seyircinin mavi köşe sanılmasını kapattı
  (yalnızca "diğer dövüşçüden daha çok benziyor" yetmez).
- **Örtüşmede kare bazında doğrulama:** karenin kendi görünümü dövüşçüye, diğer
  dövüşçü ve üçüncü kişilerden 0,08 daha çok benziyorsa kare "takipte" sayılır
  (vuruş mesafesinde kutular sürekli örtüşür; eskiden karelerin %23–25'i
  "örtüşme"ydi). Doğrulanamayan kare izleyici sürekliliğiyle taşınır ve güveni
  düşer (yakınında doğrulanmış kare varsa × 0,75, yoksa × 0,45). Kesimden sonra
  örtüşen kutudan da kimlik kurulabilir, ama iki kat farkla (0,16).
- **Örtüşen kutudan kurulan kimlik onaylanana kadar düşük güvenlidir** (sürüm 7,
  kullanıcı kararı 16 Kasım 2026: "tamamen kapatma"). Konum bilgisi yokken
  (kesim ya da uzun kayıp sonrası) kimlik örtüşen bir kutudan, yani tek karenin
  görünümüyle kurulduysa, dövüşçünün kareleri "örtüşme" durumunda ve × 0,45
  güvenle tutulur (`IdentityResult.held`); kareler ölçülebilir kalır. Dövüşçü
  **örtüşmesiz 5 karede** kendi görünümüyle doğrulanınca
  (`acquire_confirm_frames`; izleyici sürekliliği kopmadan) kimlik onaylanır:
  o ana kadar tutulan kareler ve sonrası olağan kurallara döner. Kamera kesimi
  ya da görünümle yeniden yerleştirme beklemeyi bitirir; tutulan kareler düşük
  güvenli kalır. İki seçim arasındaki bölgede diğer geçiş aynı kutuyu onaylı
  taşıdıysa onun sonucu geçerlidir. × 0,45 güven `attribution_min` (0,5)
  altındadır: bu karelerdeki olay "Kime ait belirsiz" olur. Örnek yayında
  örtüşen kutudan 44 kimlik kuruldu; 40'ı onaylandı (ortanca 10–13 kare
  sonra), 4'ü onaylanmadan kesime ya da kayba vardı: Volkanovski 49 kare
  (1,6 sn; 38'i nakavt anından hemen önce, 08:47,5–08:48,8), Topuria 5 kare.
  Belirsiz ve ölçülebilir süreler değişmedi; yalnızca "örtüşme" payı arttı
  (aşağıdaki tablo). Bu karelerde sahipliği eşiğin altına inen olay yok:
  "Kime ait belirsiz" olay yine çıkmadı (olay sayıları aynı: 131 ve 15). `IDENTITY_SINCE` 6'da kaldı: sürüm 6 sonuçları bantsız açılır
  (fark yalnızca bu karelerin güveni).
- **Bir dövüşçü diğerinin tam önündeyken iki kutu da öndekine benzer:** örtüşen
  başka bir kutu da aynı dövüşçüye benziyorsa kare doğrulanmış sayılmaz
  (sentetik testin yakaladığı açık: kimlik arkadaki iskelete geçiyordu). Görünümü
  ölçülemeyen, neredeyse aynı kutu (IoU ≥ 0,5) da aynı sonucu verir.
- **Kesimden önce taşınan kareler kesimde düşer:** kesimden sonraki eşleşme,
  kesimden önce izleyici sürekliliğiyle taşınan örtüşme karelerini doğrulayamaz;
  bu kareler "belirsiz" olur (eskiden kesim karesinde hemen eşleşme olursa
  kalıyordu).
- **Geriye dönük sahip düzeltmesi yapılmaz** (plandaki "örtüşme boyunca atanan
  olayların sahibini düzelt" yerine; kullanıcı 16 Kasım 2026'da onayladı):
  takasın hangi karede olduğu bilinemez;
  doğrulanamayan örtüşme kareleri "belirsiz" olur ve orada olay üretilmez,
  taşınan karelerdeki olayların `attribution_confidence` değeri düşer. Kesin
  olmayan olayı gerçekmiş gibi kaydetmeme kuralının gereği.
- **Boy oranı ölçülür, karar için kullanılmaz** (plandaki "boy oranı";
  kullanıcı 16 Kasım 2026'da onayladı). Neden: ölçülen şey boy değil, kutu
  yüksekliğidir ve duruşa (eğilme, çömelme, tekme) ve kameraya uzaklığa göre
  kareden kareye oynar. Örnek yayında iki dövüşçü ayrı dururken (9572 kare)
  kırmızı / mavi kutu yüksekliği oranının ortancası 0,985, ama karelerin %10'unda
  0,81'in altında, %10'unda 1,20'nin üstünde; kırmızı kutu karelerin %46'sında
  daha yüksek. Aynı sıklette gerçek boy farkı %1–3'tür: bu gürültünün çok
  altında kalır ve bir karede kimin kim olduğunu söyleyemez; karara girerse
  öne eğilen ya da uzakta duran dövüşçüyü yanlış kişiye iter. Bu yüzden yalnızca
  `AppearanceSummary.height_ratio` olarak raporlanır.
- **Geçici numara değişimi son sonuç üzerinden sayılır** (kesimlerde ve iz
  koptuğunda bir kez). Eski sayım ileri ve geri geçişleri topluyordu; tek
  seçimle 124 gösteriyordu, aynı sonuçta yeni tanımla 90'dır. Kesim sayısı
  arttığı (36 → 70) ve daha çok kare izlendiği için sayı düşmedi (90 → 102):
  bu bir izleyici ölçüsüdür, kimlik hatası değildir.
- **`attribution_confidence`:** olayın aktörünün (aktörsüz olayda iki dövüşçünün
  küçüğü) olay karelerindeki ortalama kimlik güveni; `attribution_min` (0,5,
  `MotionSettings`) altı "Kime ait belirsiz" (`attribution_uncertain`). Bu
  olaylar listede ve şimdilik sayımlarda kalır, momentuma girmez (kullanıcı
  kararı; `MOMENTUM_VERSION` 3, formül ve ağırlıklar aynı); momentum kartı kaç
  olayın dışarıda kaldığını yazar. Sayımlardan çıkmaları Bölüm 3'ün işidir
  (aşağıda "Bölüm 3 ve 4 için notlar"). Örnek yayında ve sentetik klipte böyle
  olay çıkmadı (en düşük 0,70 ve 0,75); davranış sentetik testlerle denendi.
- **Veri kalitesi kare başına bit maskesidir** (`quality.npy`): ölçülemez +
  dört neden (eksik görüntü, uzak/kötü kamera açısı, örtüşen dövüşçüler, düşük
  görüntü kalitesi). Özet tek fonksiyondur (`quality.summarize`: herhangi bir
  kare aralığı, dışlanan bölümler dövüş süresi değildir); API tüm maç ve etkin
  rauntlar için döner (`GET /jobs/{id}/tracking/quality`), tarayıcı aynı hesabı
  oynatma anına kadar olan kapsam için zaman çizelgesinden yapar
  (`model/quality.ts`); ikisi `shared/fixtures/track-quality.json` ile denetlenir
  (`python -m tests.support.quality_fixture`). Paylar iki tarafta da dört
  ondalığa, yarımlar yukarı yuvarlanır (Python'ın çifte yuvarlaması değil) ve
  nedenler yuvarlanmış paya göre sıralanır; dosyada tam yarım düşen değerler var.
  Bulanıklık ve çözünürlük eşikleri
  örnek yayında hiç tetiklenmedi (yayın net ve yakın): geçici değerlerdir.
- **Kapsam (2.5):** tutarsızlığın nedeni "ölçülebilen süre"nin oynatma anını,
  diğer kimlik satırlarının tüm videoyu izlemesiydi. Artık yan panellerin tümü
  tek kapsamı kullanır: Şu ana kadar · Raunt · Tüm maç (`model/scope.ts` →
  `scopeRange`, Bölüm 5 de bunu kullanacak). Momentum kapsamsızdır (oynatma
  anındaki değer). MP4/CSV dışa aktarma "şu ana kadar"ı yansıtmaya devam eder.
- **Eski analizler:** açılır; `TrackingSummary.version < 6` ise
  `identity_outdated` bandı çıkar, veri kalitesi satırları "tüm video" etiketiyle
  eski toplamları gösterir, kapsam yalnızca istatistiklere uygulanır.
- **Ölçüm (ayar seti; doğruluk değildir).** Aynı video, aynı seçim (kare 3142),
  karalama kopyası; "önce" = kimlik sürüm 5 sonucu, iki sütun da yeni tanımlarla
  hesaplandı:

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

  Sentetik tekrar klibi (83 sn, tek seçim): kırmızı köşe belirsiz 73,0 → 1,7 sn,
  ölçülebilir %11 → %97; olay 2 → 15; tekrarın içindeki 2 tekme dışlandı (aynı
  tekmeler canlı bölümde de sayılıyor). Örnek yayında olay 113 → 131, dışlanan 1.
  **Gözle denetim:** 108 kare (70 kesimin her birinden 20 kare sonrası + yeni
  kazanılan aralıklardan 38 kare, ızgara görsellerle): 107 doğru, 1 yanlış (maç
  sonrası seyirci çekimi; model tabanıyla kapatıldı, o kare artık belirsiz). Son
  sonuçta 26 kare yeniden bakıldı: hata yok. İnceleme düzeltmelerinden sonra
  denetlenen sonuca göre yeni ya da farklı atama yok (yalnızca 15 kare daha
  belirsiz oldu). Kalan belirsiz süre çoğunlukla bir
  dövüşçünün diğerinin arkasında kaldığı ya da sırtı dönük, şortu kadraj dışı
  yakın planlardır.
- **Süre:** kimlik adımı 2,7 → 6,4 sn (iki geçiş + doğrulama), kalite maskesi
  0,01 sn; 9 dakikalık videoda toplam analiz süresine etkisi ≈ %0,1 (poz 3091 sn).
- **Bilinen sınırlar:** tek yayın ve ondan türetilen kliple ayarlandı; şort
  renkleri çok farklı (siyah / kırmızı). Benzer şortlu dövüşçülerde model tabanı
  ve doğrulama payları yetmeyebilir; sistem o durumda belirsiz bırakır. Ek kesim
  kuralı yalnızca ani kesimi bulur (yumuşak geçişleri değil). Dışa aktarılan
  JSON'da raunt bazlı kalite özeti yok; Bölüm 4'te gelecek (aşağıdaki notlar).
- **İnceleme (tek küçük ajan, yalnızca kimlik/kalite diff'i):** yuvarlama ve
  neden sırası eşitliği, boş aralık, kullanılmayan `model_min_samples` ayarı
  (kaldırıldı), yukarıdaki iki uç durum düzeltildi. İncelemenin bilerek
  bıraktığı konu (kesimden sonra örtüşen kutudan tek karenin görünümüyle kimlik
  kurulması) kullanıcı kararıyla sürüm 7'de "onaylanana kadar düşük güvenli"
  oldu (yukarıda); benzer şortlu dövüşçülerde yeniden bakılmalı.
- **Sürüm 7 sonrası ekran denetimi (16 Kasım 2026):** karalama kopyasındaki iki
  iş yeniden işlendi (kimlik sürüm 7; inceleme düzeltmeleri de bu sonuçta).
  Kapsam (Şu ana kadar · Raunt · Tüm maç) ve veri kalitesi satırları API
  değerleriyle aynı, iki temada; tutulan karede (08:48) kırmızı köşe "Örtüşme"
  görünüyor ve iskelet doğru kişide. Takip kaydında aynı karede aynı dövüşçüye
  iki kontrol kaydı düşünce çıkan React anahtar uyarısı düzeltildi
  (`TrackingLog`: anahtara kayıt türü eklendi).
- (c) `v2/bolum-2` dalında; merge/push kullanıcının sözüyle.

### Bölüm 3 ve 4 için notlar (kullanıcı kararları, 16 Kasım 2026)
- **Bölüm 3, `RoundFeatures`:** "Kime ait belirsiz" olaylar
  (`FightEvent.attribution_uncertain`) dövüşçü sayımlarına girmez; raunt
  özelliklerinde ayrı bir "belirsiz" sayısı olarak tutulur ve arayüzde öyle
  gösterilir. Bugün yan paneldeki sayımlarda duruyorlar (yalnızca momentum
  dışında); `RoundFeatures` yazılırken yan panel sayımları da aynı ayrımı
  kullanır. Olay sahipliği düzeltmeleri (3.6) bu olayları bir dövüşçüye
  bağlayabilmelidir.
- **Bölüm 4, `JudgingResult.data_quality`:** raunt bazlı veri kalitesi özeti
  dışa aktarılan JSON'a bu alanla gelir; şimdi eklenmedi. Kaynak hazır:
  `tracking/quality.py` → `summarize` (herhangi bir kare aralığı) ve
  `GET /jobs/{id}/tracking/quality` (tüm maç + etkin rauntlar).
- **Karalama verisi:** `local/fa-data` ve `local/replay-clip` Bölüm 3 bitene
  kadar kalır.
- **Bölüm 3 planına kullanıcı yanıtları (17 Kasım 2026):** (1) dirsek ve yerde vuruş
  momentumda "vuruş denemesi" ağırlığıyla, formül aynı (3a'da yapıldı); (2) (c)'deki
  düzeltmeler momentumu da etkiler: sayımlar, kartlar ve momentum tek etkin olay
  listesini kullanır; (3) (b)'de klinç kontrolü ayrı bir alanda, düşük güvenli
  tahmin; merkez tutma "ölçülmedi" diye işaretlenir; (4) (c)'de oynatma anı kapsamı
  API'den gelir, hızlı sarmada eski istekler iptal edilir ve yalnızca son isteğin
  sonucu gösterilir; (5) grappling için kullanıcının Masaüstündeki
  `full-fights/khabib_vs_dustin` kaydı yalnızca yerelde kullanılır (repoya ve
  testlere girmez); (6) git akışı Bölüm 2'deki gibi (dal `v2/bolum-3`, aşama başına
  commit, merge/push kullanıcının sözüyle); (7) nakavt için kimlik çıkarımı (3a'da).

### Vuruş olayları ve hasar sinyalleri (v2 Bölüm 3a, 17 Kasım 2026)
Bölüm 3 üç aşamada yapılıyor (a: vuruş olayları ve hasar sinyalleri, b: grappling
durumları, kontrol ve baskınlık, c: `RoundFeatures` ve düzeltme katmanı); bu kararlar
(a) içindir. Kod: `motion/strikes.py` (hedef bölge, sonuç), `motion/damage.py`
(hasar sinyalleri, çıktı düşüşü), `motion/events.py`. Ayarlar `MotionSettings`'te
(olay önbellek anahtarına girer) ve `FeatureSettings`'te (istek anında; hiçbir
anahtara girmez). Şema 1.11.0, `EVENTS_VERSION` 4, `MOMENTUM_VERSION` 4. Poz,
takip hazırlığı, kimlik (7), kamera ve yayın önbellekleri değişmedi: mevcut
analizler `events_outdated` bandıyla açılır, "Yeniden işle" yalnızca olayları ve
momentumu hesaplar (örnek yayında 18 sn).
- **Sözleşme:** `FightEvent` + `target_zone`, `outcome`, `outcome_confidence`,
  `significant`, `phase`, `evidence`; yeni türler `elbow`, `ground_strike`;
  `DamageSignal` ve `EventTimeline.damage`; `EventsSummary.version` ve
  `damage_signals`; `FighterEventCounts` + `landed_strikes`, `significant_attempts`,
  `significant_landed`; `AnalysisExport.damage`. Eski olaylarda yeni alanlar boştur
  ve arayüzde görünmez (uydurulmaz).
- **Hedef bölge:** vuran yüzey (yumrukta bileğin 0,18 gövde boyu ötesi, tekmede ayak,
  bilek ve kaval ortası, diz ve dirsekte eklemin kendisi) tepe anından 0,05 sn önce
  ile 0,2 sn sonra arasında izlenir. Bölgeler: kafa çemberi, omuz ortası–kalça ortası
  çizgisinin çevresi, uyluk ve kaval. Yumruk ve dirsek yalnızca kafa ve gövdeye
  gider. Uzvun en çok yaklaştığı bölge hedeftir; temas anı uzvun bölgeye **ilk
  ulaştığı** karedir (en derin örtüşme değil: tekme geri dönerken en derindir).
- **Sonuç:** isabet = bölgeye ulaşma + hemen ardından net tepki (vuruş doğrultusunda
  baş savrulması ≥ 0,15, gövdenin vuruş yönünde itilmesi ≥ 3,0 gövde boyu/sn, vurulan
  bacağın diz ya da bileğinin oynaması ≥ 0,5); blok = korumaya (ön kol + eldiven,
  yarıçap 0,22) değdi, tepki yok; ıska = hiçbir bölgeye ve korumaya 0,3'ten yakın
  değil; gerisi "sonuç belirsiz". Belirsiz ıska değildir.
- **Neden bu eşikler (ayar seti; doğruluk değildir):** ilk eşiklerle (doğrultusuz baş
  hareketi 0,12, itilme 1,2, bacak 0,25) örnek yayında 26 isabet çıktı. Sistemin
  sonucunu görmeden yapılan 72 vuruşluk ızgara denetiminde (her sonuç sınıfından
  sabit seed'le; ≈ 34'ünde ben de karar veremedim, 8'i hiç vuruş değildi) isabet
  dediklerinin yalnızca yarısında isabet gördüm. Dövüşçüler sürekli hareket ediyor
  (gövde itilmesi ölçüsünün ortancası 0,84), kaçınan baş da oynuyor. Ayardan sonra
  örnek yayında 5 isabet: işaretledikleri gördüklerimle uyumlu (3/3), ama gördüğüm
  isabetlerin yalnızca 3/7'sini yakalıyor. **Temkinli tarafta bırakıldı.** Blok
  denetimde iyi tuttu (eğilim verebildiğim 15'in 12'si).
- **Önemli vuruş:** mesafede her vuruş; klinçte ve yerde yalnızca tepe hızı eşiğin
  1,4 katını geçenler. Faz şimdilik mevcut klinç ve "yerde" kurallarından gelir;
  (b)'de durum makinesine bağlanacak. Örnek yayında klinç yok: tüm vuruşlar mesafede.
- **Dirsek:** dirsek önde (bileğin hızının en az 0,8'i), kol katlı (≤ 0,55 kol boyu),
  omuz hizasına kalkar, rakibin üst gövdesine doğru 0,6 üst kol boyu uzanır ve kafa ya
  da gövde bölgesine 0,35 içinde yaklaşır; dövüşçüler arası ≤ 1,2. Sentetik "koruma
  kaldırma" klinç mesafesinde hâlâ dirsek görünebiliyor (bilinen sınır). Örnek yayında
  3 dirsek; gerçek görüntüyle doğrulanmadı.
- **Yerde vuruş:** rakip yerdeyken kol vuruşu; uzanma şartı yok, hız ≥ 4,0.
  "Vuruş denemeleri" sayısına ve momentumda "vuruş denemesi" ağırlığına girer
  (dirsek de; kullanıcı kararı). Momentum formülü aynı.
- **Deneme tespitinde doğrulamada bulunan iki düzeltme** (planda "eşikler aynı
  kalır" denmişti; bu ikisi eşik değil, hata): (1) tepe anı, uzvun rakibe doğru
  hareket ettiği karelerin en hızlısıdır. Vuruş ve geri dönüşü tek hız bölümü
  oluşturup geri dönüş daha hızlıysa deneme eleniyordu (nakavt kroşesi böyle
  kaçıyordu). (2) Kendi tekmesi sırasındaki kol savruluşu (tekme bulunamasa bile:
  hızlı ve yükselen bacak) ve ayaktaki rakibin kalça hizasının altına inen el
  (tekmeyi tutma ya da bloklama) deneme sayılmaz. Örnek yayında vuruş denemeleri
  129 → 126 (yumruk 107 → 99, tekme 19 → 20, diz 3 → 4, dirsek 0 → 3).
- **"Yerde":** duruş "yerde", ya da kalça ayaktayken ölçülen yüksekliğinin %65'ine
  indi (duvara yaslanıp oturan dövüşçü 2B'de dik görünür ve eski kural onu "geçiş"
  sayıyordu). Belden eğilip vuran (bacaklar düz) artık "yerde" sayılmaz (kinematikte
  düzeltme). Düşme = kararlı ayakta → kararlı yerde. Yere iniş, kontrol, "altında
  kalanın kolları sayılmaz" ve sinyallerdeki duruş aynı tanımı kullanır.
- **Knockdown / kayma / takedown:** öncesinde rakibin vuruşu varsa ve klinç yoksa
  knockdown, ama vuruşların hepsi net ıskaysa kayma ("Yere indi; öncesindeki vuruş
  isabet etmedi"); yakın temas varsa takedown; yoksa kayma.
- **Nakavt (kullanıcı önerisi):** bir dövüşçü yüksek güvenle (≥ 0,75) izlenip
  ayaktayken, diğerinin kimlikli bölümüne bitişik, aynı iz numarasındaki kişi 1,5 sn'ye
  kadar o dövüşçü sayılır (`infer_presence`; yalnızca düşmeler için, kinematik yalnızca
  çıkarım karelerinin ±4 sn çevresinde). Böyle bulunan knockdown "olası", güveni
  ≤ 0,40, kanıtında `identity_inferred`; momentum puanı almaz (eşik 0,5). Öncesindeki
  vuruş olay listesine eklenmez (kimlik o anda doğrulanmamıştı). **Örnek yayında:**
  527,9 sn'de Volkanovski için olası knockdown; öncesindeki vuruş 0,43 sn önceki sol
  kroşe (görüntüde yüze geliyor, sistem "olası temas" dedi). Görsel:
  `local/bolum3a/nakavt-knockdown.jpg` (git'e girmez).
- **Hasar sinyalleri:** knockdown, ağır kafa vuruşu (isabet + doğrultulu baş savrulması
  ≥ 0,3), sarsılma, zorunlu geri çekilme. Çıktı düşüşü (kümülatif) raunda ve dışlanan
  bölümlere bağlı olduğu için önbellekte değil, istek anında hesaplanır
  (`GET /events` ≈ 20 ms ve dışa aktarma). İlk kurallarla örnek yayında 15 sarsılma ve
  4 zorunlu geri çekilme çıktı; karelerle bakınca **19'u da** değişim sonrası normal
  hareketti. Artık yalnızca isabetten sonra; sarsılma için kendi denemesi olmadan ve
  kalça ≥ %30 çökerek. Örnek yayında yalnızca knockdown kalıyor. Sarsılma ve geri
  çekilme gerçek bir sarsılma görüntüsüyle doğrulanmadı. Submission tehlikesi (b)'de,
  görünür hasar bayrağı (c)'de.
- **Momentum:** formül ve ağırlıklar aynı; girdiler değiştiği için örnek yayında son
  pay kırmızı %54,4 → %52,0.
- **Kaçan vuruş (3 × 8 sn; R1, R2, nakavt öncesi; kabaca, 0,13 sn arayla kareler):**
  gözle ≈ 34 deneme, tespit ≈ 13 doğru (bir tekme iki kez sayıldı, bir kol tekmeyi
  blokluyordu): kabaca %35–40. Arkadan yakın çekimde ve iç içe değişimde çoğu kaçıyor.
- **Süre:** hareket aşaması 8,2 → 12,6 sn (kinematik 7,5, çıkarım kinematiği 3,8, olay
  0,8, örnekleme 0,5); poz 3091 sn'ye göre ≈ +%0,14.
- **Bilinen sınırlar:** tek yayınla ve aynı yayınla ayar; isabet temkinli (gerçek
  isabetlerin çoğu "blok" ya da "belirsiz" kalıyor); 2B'de eldivenle yüz ayrılamıyor;
  tekme kontrolü (check) ayrı bir sonuç değil; örnek yayında grappling yok (b için
  kullanıcının Khabib–Poirier kaydı, yalnızca yerelde).
- **(a) onayı ve ek işler (kullanıcı kararları, 25 Kasım 2026):**
  - *Kimlik çıkarımıyla görülen vuruşlar* listeye "Kimlik çıkarımı" etiketiyle
    girer (kanıtta `identity_inferred`); sahiplik güvenleri 0,40'la sınırlı olduğu
    için eşiğin altındadır ve **sayımlara, momentuma ve hakem kanıtına girmez**
    (`events.counted`, `export/frames.py`, `model/measured.ts` → `inferredOnly`,
    `judging/evidence.py`). "Kime ait belirsiz" etiketi bunlarda gösterilmez (kendi
    etiketleri var). Hasar sinyali üretmezler. Örnek yayında 3 vuruş (Topuria;
    nakavt kroşesi dahil, 527,43 sn).
  - *Temkinli isabet ayarı kalır* (yukarıdaki eşikler).
  - *Çift sayılan tekme düzeltildi:* aynı bacağın 0,3 sn'den yakın iki hız
    bölümü tek tekmedir (`kick_merge_s`; çift yumruk iki kalır). Örnek yayında
    519,4 / 519,6 sn: Volkanovski'nin tekmesi 16 → 15.
  - *Dirsekler gözle denetlendi:* üçü de (Topuria, 380,4 / 394,6 / 394,8 sn)
    sırtı kameraya dönükken yakın değişimde atılan bükük kollu kısa sol kroşeye
    benziyor; arkadan dirsekle kroşe 2B'de ayrılamıyor. Kural: dövüşçünün burnu ve
    gözleri ölçülemiyor, iki omzu ölçülüyorsa "dirsek" adayı **yumruk** olarak
    kalır (`from_behind` ölçüsü). Örnek yayında artık dirsek yok; 394,6 ile 394,8
    büyük olasılıkla aynı hareket (iki yumruk sayılıyor; bilinen sınır).
  - *Tekmeyi karşılayan kol:* rakip tekme atarken (hızlı ve yükselen bacak) eli
    tekme atan bacağın diz ya da bileğine 0,6 gövde boyu içinde olan "yumruk"
    blok sayılır (`block_reach`). Vuruş olmayan 8 tespitten artık 4'ü eleniyor
    (önce 2): kalanlar Volkanovski'nin kendi tekmesindeki kol savruluşu (2;
    tekme hızı/yüksekliği ölçülemediğinde) ve Topuria'nın yüksek tekmeyi
    karşılayan kolu (2; el bacağa yeterince yakın ölçülmüyor).
  - Örnek yayında (yeniden işlendi): vuruş denemeleri Volkanovski 64 yumruk/diz +
    15 tekme, Topuria 40 + 4 (+3 yalnızca çıkarımla görülen, sayılmayan); isabet
    3 / 3. Olay önbellek anahtarı yeni ayarlarla değişti; `EVENTS_VERSION` 4'te
    kaldı (dal henüz birleştirilmedi; 3a'nın ilk hâliyle işlenmiş bir analiz
    bantsız ama eski olaylarla açılır, karalama kopyası yeniden işlendi).
- **Kaçan vuruşlar dövüşçüye göre (aynı 3 × 8 sn pencere, kabaca):** Volkanovski
  gözle ≈ 20 deneme, ≈ 10 doğru tespit (≈ %50); Topuria ≈ 14, ≈ 3 (≈ %20).
  Vuruş olmayan 8 tespitin 5'i Topuria'da (hepsi Volkanovski'nin tekmesini
  karşılayan kol), 3'ü Volkanovski'de (kendi tekmesindeki kol savruluşu).
  **Topuria sistematik olarak daha çok kaçıyor. Nedeni kamera açısı:** ana kamera
  çoğunlukla Topuria'yı arkadan görüyor. Ölçülebildiği karelerin %35'inde sırtı
  kameraya dönük (Volkanovski %17; R2 penceresinde %62), bilekleri daha az
  ölçülüyor (%81 / %63; Volkanovski %89 / %83). Sırtı dönük dövüşçünün vuruşu
  görüş doğrultusunda gider: 2B'de uzanma ve hız kısalır, bilek kendi gövdesinin
  arkasında kalır. Topuria'nın kısa kroşeleri bu açıda deneme eşiklerine
  ulaşmıyor; Volkanovski'nin uzun jab'ları ulaşıyor.

### Bölüm 4 için notlar (kullanıcı kararları, 25 Kasım 2026)
- **"Belirsiz" vuruşlar sıfır değildir:** sonucu "belirsiz" olan vuruş
  `outcome_confidence` ile olasılıklı sayılsın (isabet "kesin" değil, "olasılıklı"
  katkı). Temkinli isabet ayarı (3a) bu yüzden kalıyor.
- **Hasar sinyalleri seyrek:** örnek yayında yalnızca knockdown (çıkarımla, güven
  0,40) var; sarsılma ve zorunlu geri çekilme 2B'de güvenilir değil. Hakem güveni
  buna göre düşük gösterilsin (D_imm'in çoğu raundda boş kalması "hasar yok"
  anlamına gelmez).
- **Deneme sayısı dövüşçüler arasında eşit ölçülmüyor:** bu yayında Topuria'nın
  denemelerinin ≈ %20'si, Volkanovski'ninkilerin ≈ %50'si yakalanıyor (kamera
  açısı, yukarıda). Ham hacim karşılaştırması (offensive_pace, isabet sayısı)
  kameraya dönük dövüşçüyü kayırır. Motor dövüşçü bazında görünürlüğü (sırtı
  dönük pay, bilek ölçülebilirliği; (b)/(c)'de raunt özelliklerine eklenebilir)
  hesaba katmalı ya da bu durumda güveni düşürmeli. Eski kartlar iki raundu da
  Volkanovski'ye veriyordu; bu yanlılık bunun bir nedeni olabilir.
- **Görünmeyen grappling (kullanıcı kararı, 27 Kasım 2026):** bir rauntta grappling durumu
  "bilinmiyor" payı yüksekse hakem güveni düşer ve raunt "grappling ölçülemedi" diye
  işaretlenir. Görünmeyen grappling, vuruşları görünen dövüşçünün lehine yorumlanmaz: ölçülen
  vuruşlar yalnızca görülebilen (çoğunlukla ayakta geçen) bölümü temsil eder. Khabib–Poirier'de
  "bilinmiyor" payı R1 %63, R2 %78, R3 %76 (3b). **docs/v2-plan.md'ye işlendi** (27 Kasım 2026:
  4.2 adım 1, 4.6 `data_quality`, 4.7 test); veri tarafı gizli rakip çıkarımıyla hazır (aşağıda
  "3b kararlarının uygulanması"): bilinmeyenin "sarılı" tahmin edilen kısmı ve o sırada hangi
  dövüşçünün görüldüğü (görülen dövüşçü üstünlük kanıtı değildir).

### Grappling durumları, kontrol ve baskınlık (v2 Bölüm 3b, 26 Kasım 2026)
Bölüm 3'ün (b) aşaması. Kod: `motion/grappling.py` (kare bazlı durum makinesi, geçiş
olayları, klinç ve aktif kontrol, submission girişimi), `motion/dominance.py` (3.4
ölçümleri, istek anında), `motion/damage.py` (submission tehlikesi), `motion/events.py`
(bağlantı), `motion/series.py` (ortak dizi yardımcıları). Ayarlar `MotionSettings`'te (olay
önbellek anahtarına girer) ve `FeatureSettings`'te (istek anında; hiçbir anahtara girmez).
Şema 1.12.0, `EVENTS_VERSION` 5; `MOMENTUM_VERSION` 4'te kaldı (formül ve ağırlıklar aynı;
olay anahtarı değiştiği için momentum da yeniden hesaplanır). Poz, takip hazırlığı, kimlik,
kamera ve yayın önbellekleri değişmedi: sürüm 4 analizleri `events_outdated` bandıyla
açılır, "Yeniden işle" yalnızca olayları ve momentumu hesaplar.
- **Durumlar:** her karede DISTANCE, CLINCH, GROUND_RED_TOP, GROUND_BLUE_TOP, SCRAMBLE; bir
  dövüşçü ölçülemiyorsa ya da iki dövüşçünün görünür boy oranı olağan oranının 2 katından
  fazla sapıyorsa (kimliklerden biri başka birinde, ör. seyircide) "bilinmiyor": tahmin
  edilmez. Yerde: biri ya da ikisi "yerde" (3a tanımı) ve yakınlar; gövde merkezi diğerininkinden
  0,25 gövde boyu yukarıda olan üsttedir, ayrılamıyorsa SCRAMBLE. Biri yerde, diğeri uzaktaysa
  kimse grappling yapmıyor: DISTANCE. Dik duran rakibinin bacaklarına eğilmiş (kalçası yerde
  değil) dövüşçü ayakta grappling'dir: CLINCH. Pozisyon yalnızca üst / alt; guard, mount, sırt
  ayrılmıyor.
- **Klinç ancak tutuşmayla:** yalnızca mesafe kuralı (≤ 1,3 gövde boyu) örnek yayında 18
  "klinç" (≈ 40 sn) buldu; karelerle bakınca biri hariç hepsi cep mesafesinde vuruş değişimi
  ya da 2B'de üst üste görünen (derinlikte ayrı) dövüşçülerdi. Artık ayrıca (1) ölçülebilen
  karelerin en az yarısında bir dövüşçünün bileği rakibin gövde çizgisinin 0,35 gövde boyu
  içinde (bilek ölçülemiyorsa kalçalar ≤ 0,9) ve (2) iki dövüşçünün görünür boy oranı videodaki
  olağan oranının %20 yakınında (aynı derinlik) olmalı. Dirsek, kafa ve uyluk hedefleri
  denendi: 2B'de korumadaki ve bel hizasındaki eller rakibe hep o kadar yakın görünüyor,
  ayırmıyor. Örnek yayında 2 klinç kaldı (4:38,8 ve 6:24,6; ilki karelerde açıkça boyun tutuşu).
- **Titreşime karşı:** klinç ancak 1,3 + 0,15 gövde boyunun ötesinde biter; aynı iki durum
  arasındaki ölçülemeyen bölüm o durum sayılır (ayakta 1 sn'ye, yerde 2,5 sn'ye kadar; güveni
  yarıya iner); 0,6 sn'den kısa bir durum komşularına katılır ya da iki yer durumu arasında
  SCRAMBLE olur; 1,5 sn'den kısa ve iki yanı mesafe olan klinç mesafedir.
- **Geçişler:**
  - *takedown:* ayakta durumdan 4 sn içinde yere, düşen alttayken, öncesinde yakın temas
    (klinç ya da ≤ 1,2 × klinç mesafesi, en az 0,5 sn) ve knockdown değilse. Saldıran ≥ 3 sn
    üstte kalırsa isabetli; rakip daha önce kalkar ya da üste çıkarsa `brief` (güven ≤ 0,45,
    momentum eşiğinin altında); kayıt/ölçüm 3 sn dolmadan biterse `brief` boştur. Kendi seviye
    değişimi altında biten dövüşçünün üstündeki rakip (sprawl) takedown yapmış sayılmaz. 3a'nın
    "yakın temastan sonra düşüş" kuralı yalnızca üst pozisyon ölçülemediğinde ve düşen
    gerçekten zemine (kalça) indiyse, düşük güvenle yedek olarak kalır.
  - *takedown_attempt:* rakibe yakınken omuzları rakibinkinin 0,3 gövde boyu altına iner,
    kalçası ayaktaki yüksekliğinin %85'ine iner ya da gövdesi 35° öne eğilir; en az 0,5 sn,
    ayaktan başlar, en az 0,2 sn klinç mesafesine ulaşır (mesafedeki eğilme/kaçış deneme
    değildir); rakip düşmezse "olası" deneme (güven ≤ 0,5). 1,5 sn'den yakın iki deneme
    birdir; yumrukla birlikte 0,6 sn'den kısa eğilme deneme değildir.
  - *reversal:* iki üst pozisyon da ≥ 1,5 sn, aradaki karmaşa ≤ 3 sn.
  - *get_up:* alttaki ayağa kalkar (`from_bottom`). 3a'nın "Ayağa kalktı" duruş değişimi artık
    yalnızca dövüşçü gerçekten zemine inmişse (kalça yerde, en az 0,3 sn) ve rakibi o sırada
    ölçülüyorsa `get_up` olur. Üstteki dövüşçünün doğrulması, klinçte derin eğilip doğrulma
    ve rakibi gizliyken kalkma kalkma değildir. Aynı nedenle sayılmayan "Yere indi" duruş
    değişimi de kalça zemine inmeden çıkmaz (knockdown kuralı değişmedi).
  - *submission_attempt:* bir kolun ön kolu (eldiven dahil) rakibin boynunun 0,25 gövde boyu
    içinde ve rakibin başı saldıranın omuz merkezinin 0,75 içinde, ayakta değilken (klinç ya
    da yer), en az 3 sn. "Olası", güven ≤ 0,4. Klinçteki boyun tutuşu aynı görünür (örnek
    yayında 4:40'ta 2 sn: 2 sn eşiğinde orada bir "submission" çıkıyordu, 3 sn'ye çıkarıldı).
    Üçgen ve eklem kilitleri üretilmiyor (2B'de ayrılamıyor).
- **Kontrol:** yer kontrolü = üstte geçen süre (`ground_control` olayları, en az 1 sn); klinç
  kontrolü ayrı alanda, düşük güvenli (≤ 0,35): klinçte ikiliyi rakibin sırtına doğru süren
  (≥ 0,3 gövde boyu/sn, ≥ 0,3 sn) son dövüşçü, diğeri geri sürene kadar (kafes ölçülmüyor;
  "rakibi kafese yaslama" böyle tahmin ediliyor); aktif kontrol = kontrol sırasında kontrol
  edenin vuruş denemesinin 1 sn öncesinden 2 sn sonrasına kadar ya da submission girişimi
  boyunca geçen süre (`ground_control.measures.active_s`, `FighterEventCounts.active_control_s`
  / `clinch_control_s`). Kalkarken kol hareketi (kendisi az önce yerdeyken ve üstte değilken)
  yerde vuruş sayılmaz.
- **3.4 ölçümleri** (`dominance.measure`, herhangi bir kare aralığı; dışlanan bölümler dövüş
  süresi değil; "Kime ait belirsiz" olaylar kimsenin değil; her biri değer + güven): tek taraflı
  süre (ofansta — deneme, takedown/submission girişimi ya da aktif kontrol — ve ölçülen rakip
  hiçbir şey denemiyor), ofansif tempo (önemli deneme + takedown/submission denemesi +
  kombinasyon, ölçülen dakikada), etkili süre payı (aktif kontrol, tek taraflı süre, isabetli
  vuruş çevresi / dövüş süresi), saldırganlık (dakikada deneme, kombinasyon, mesafe kapatıp
  saldırma; referans hızlara göre 0–1), alan kontrolü (Baskı, İlerleme / geri çekilme, klinç
  sürme, yerde üstte kalma, değişimleri başlatma; ölçülebilen bileşenler üzerinden ağırlıklı
  0–1; oktagon merkezi "ölçülmedi"). Ağırlıklar ve referans hızlar `FeatureSettings`'te,
  Bölüm 6'da kalibre edilecek. Güvenler ölçülen süre payıyla ve dedektörün kaçırdığı denemeler
  yüzünden ≤ 0,6 (alan kontrolü ≤ 0,5). Bir raunt birkaç milisaniyede hesaplanıyor. API ve
  arayüz (c)'de `RoundFeatures` ile.
- **Görünürlük sinyalleri (Bölüm 4 notu için):** 10 Hz'te dövüşçü başına sırtı kameraya dönük
  mü (`facing_away`) ve bileklerinin ölçülme payı (`wrists_measured`); (c)'de raunt
  özelliklerine girecek.
- **Sözleşme:** `EventType` + `takedown_attempt`, `reversal`, `get_up`, `submission_attempt`;
  `FightEvent.brief`; yeni kanıtlar (`close_contact`, `level_change`, `top_position`,
  `position_change`, `neck_wrap`, `escape_fade`); `GrapplingState` ve `MotionTimeline.phase`;
  `FighterSignals.facing_away` / `wrists_measured`; `FighterEventCounts` + takedown denemesi,
  kısa takedown, ters çevirme, kalkma, submission girişimi, klinç ve aktif kontrol;
  `EventsSummary.phases`. Kare dizileri (`grappling`, `grappling_conf`, `clinch_by`) olay
  önbelleğinde; eski girdiler onlarsız okunur (boş). Ortak `frame-metrics.json` yalnızca şema
  sürümü ve yeni boş alanlar için yeniden üretildi (sayılar aynı).
- **Arayüz (asgari; Bölüm 5 yeniden kuracak):** yeni olay adları ve filtre çipleri, zaman
  çizelgesinde küçük içi boş işaretler ve açıklaması, kısa takedown için "Kısa" etiketi. Durum
  bandı henüz gösterilmiyor (`MotionTimeline.phase`'de hazır).
- **Örnek yayında (Topuria–Volkanovski, karalama kopyası):** vuruş sayıları, isabetler, önemli
  vuruşlar, knockdown ve vuruş fazları sürüm 4 ile birebir aynı; yeni: 2 klinç (≈ 6 sn).
  Topuria'nın nakavttan sonra rakibinin üstüne diz çöküp kalkmasının iki bilgi olayı ("Yere
  indi (rakip zaten yerdeydi)", "Ayağa kalktı") artık çıkmıyor. Takedown, deneme, ters
  çevirme ve submission yok (ilk eşiklerle çıkan 3 deneme ve 1 submission karelerde vuruş
  değişimi ve klinç tutuşuydu).
- **Khabib–Poirier (kullanıcının kaydı, yalnızca yerelde; karalama işi 931d7565):** 15:46,
  1080p30, 28 359 kare; poz 5419 sn (≈ 90 dk). Raunt tespiti R1 ve R2'yi doğru buldu; R3'ün başı 11 sn
  geç (ilk 11 sn saati sponsor grafiği kapatıyor; tespit ilk okumayı (4:49) başlangıç sayıyor),
  karalama işinde elle düzeltildi (R3 başı kare 19720). **Bulgu: gerçek grappling ölçülemiyor.**
  Klinç ve yerde poz modeli iç içe geçmiş iki dövüşçüden yalnızca birini (çoğunlukla üstteki
  Khabib'i) buluyor; NMS 0,7 → 0,95 denendi (`local/bolum3b/tools/nms_probe.py`): ek kutular
  yalnızca aynı kişinin kopyası, alttaki dövüşçü hiç çıkmıyor (eşik değil, model sınırı).
  Kimlik katmanı bu yüzden Poirier'i raundlarda %43 / %69 / %73 "belirsiz" bırakıyor (R2'de
  115 sn kesintisiz); iki dövüşçünün birlikte ölçüldüğü kare payı %24–39. Sonuç: videonun
  %77'si "bilinmiyor"; ölçülen grappling ≈ 4,5 sn Khabib üstte (karelerde doğru) ve 2,6 sn
  klinç. 12 kontrol karesi (sistemin etiketini görmeden): 5 mesafe karesinin 4'ü doğru, 1'i
  "bilinmiyor"; grappling olan 7 karenin 6'sı "bilinmiyor", 1'i yanlış "mesafe" (kırmızı kimlik seyircideydi; boy
  oranı koruması bundan sonra eklendi, artık "bilinmiyor"). İlk kurallarla çıkan yanlış
  olaylar (Poirier'e takedown, Khabib'e 3 "kalkma" ve 2 "Yere indi") klinçte derin eğilen
  Khabib'in birleşik iskeletinden geliyordu; zemine inme ve rakibi ölçülme şartlarıyla
  kalktı. Kalan olaylar: 2 yer kontrolü (doğru), 1 olası takedown denemesi (Poirier'in alçak
  dalışı, makul), 1 klinç ve 12:48'de sırt alırken Khabib'in yere inmesi (doğru).
- **Süre (aynı makinede, eski ve yeni kodla; ölçümler bu oturumda gürültülü):** olay + örnekleme
  2,4 → 6,8 sn (örnek yayın), 4,9 → 6,6 sn (Khabib–Poirier); kinematik değişmedi. Poz süresine
  göre < %0,2.
- **Bilinen sınırlar:** grappling'de alttaki/arkadaki dövüşçü poz modelince görülmüyor (yukarıda);
  yerde pozisyon yalnızca üst / alt; kafes ve oktagon merkezi ölçülmüyor; submission yalnızca
  "olası" boyun sarma; 2B'de derinlik ayrımı boy oranıyla kaba; eşikler bir yayın ve sentetik
  sahnelerle ayarlandı.
- **(b) onayı ve kararlar (kullanıcı kararları, 27 Kasım 2026):** (b) onaylandı (commit
  `92d5a13`). Aşağıdakiler o oturumda uygulanmadı; ertesi oturumda uygulandı (bir sonraki başlık,
  "3b kararlarının uygulanması"):
  - *Gizli rakip çıkarımı:* evet. Bir dövüşçü görünmüyorken az önce rakibine sarılı olduğu
    biliniyorsa o an ayrı ve açıkça etiketli bir tahmin olur ("Kimlik çıkarımı" gibi), düşük
    güvenle işaretlenir ve ölçülmüş gibi gösterilmez. Sayımlara, kontrol süresine ve momentuma
    girip girmeyeceği o oturumda kararlaştırılır (3a'da kimlik çıkarımıyla görülen vuruşlar
    girmiyor).
  - *Büyük poz modeli:* indirme izni verildi, yalnızca hızlı bir deneme için. Aynı grappling
    karelerinde (≈ 50 kare; `local/bolum3b/tools/nms_probe.py`'deki karelerle başlanabilir)
    alttaki dövüşçü görünüyor mu, kare başına süre ne kadar artıyor. Tüm video yeniden
    işlenmez; varsayılan model (`yolo26s-pose`) ve `KEY_SCHEMA` değişmez. Sonuç iyiyse büyük
    modeli yalnızca "bilinmiyor" ve sarılma karelerinde çalıştırma fikri değerlendirilir.
  - *Raunt başlangıcı (Bölüm 2a kuralı):* evet. Saati grafik kapatınca raunt başı ilk saat
    okumasından geriye hesaplanır; kaynağı ayrı işaretlenir ve güveni biraz düşük olur
    (Khabib–Poirier R3: ilk okuma 4:49, gerçek başlangıç 11 sn önce).

### 3b kararlarının uygulanması (27 Kasım 2026)
Kod: `motion/grappling.py` (`hidden_opponent`, `hidden_events`), `motion/events.py`, `motion/store.py`,
`broadcast/clock.py`; ayarlar `MotionSettings.hidden_*` (olay anahtarına girer) ve
`BroadcastSettings.start_extrapolate_max_s` / `extrapolated_start_factor`. Şema 1.13.0,
`EVENTS_VERSION` 6 (`EVENTS_SINCE` 6: sürüm 5 analizleri bantla açılır, "Yeniden işle" olayları ve
yayın aşamasını yeniden hesaplar), `BROADCAST_VERSION` 4 (bant yok: fark yalnızca saati raunt başında
kapalı kalan rauntlar). Poz, takip hazırlığı, kimlik, kamera ve `KEY_SCHEMA` değişmedi; momentum
formülü aynı.
- **Gizli rakip çıkarımı (`hidden_grappling`):** sarılınca poz modeli iki dövüşçüye çoğunlukla tek
  iskelet veriyor; biri ölçülemiyor ve durum "bilinmiyor". Bilinmeyen bir bölümde yalnızca bir
  dövüşçünün ölçüldüğü karelerde ayrı bir tahmin yapılır. Kanıt: durum bilinmez olduğu anın ±1 sn
  çevresinde iki dövüşçü ≤ 2,2 gövde boyu yakın ya da hemen öncesinde sarılı (bir dalış ≈ 2 gövde
  boyundan başlıyor), ve görünen dövüşçünün yerde olduğu her kare (bir dövüşçü tek başına uzun süre
  yerde kalmaz). 10 sn hiçbir şey tahmin edilemezse (yakın çekim, ikisi de kayıp) bölüm bölünür;
  sonraki parça yalnızca "yerde" kanıtıyla sürer. Yakınlık görülen parçada ayaktaki kareler kanıta en
  çok 30 sn uzaklıkta tutulur; yakınlık görülmeyen parçada ayaktaki kareler tahmin edilmez. Her parça
  en az 4 sn sürmeli (örnek yayında canlı değişimlerde bir dövüşçünün diğerini kapatması en çok
  ≈ 3,4 sn). ≤ 2,5 sn'lik iki tarafı ölçülmeyen boşluklar köprülenir.
  - *Ayakta mı yerde mi söylenmez:* kör kare denetiminde (sistemin kararını görmeden, 36 kare)
    tahmin edilen 24 karenin **24'ünde dövüşçüler gerçekten sarılıydı**, ama birleşik iskeletin
    duruşundan çıkan "ayakta / yerde" ayrımı 24'ün 11'inde yanlıştı. Bu yüzden tahmin `tied_up`
    ("sarılı"; yeni `GrapplingState`); yalnızca bilinmeyen bölümün iki yanında aynı sarılı durum
    ölçüldüyse (ör. iki yanda "yerde kırmızı üstte") o durum taşınır. Görülen dövüşçü üstte sayılmaz
    (model bazen alttakini gösteriyor: R1 3:17'de görünen Poirier'di).
  - *Sayılmaz:* ayrı olay türü (`hidden_grappling`, kanıt `opponent_hidden`), ayrı kare dizileri
    (`grappling_hidden`, `_conf`, `_seen`), 10 Hz `MotionTimeline.phase_hidden`,
    `PhaseTimes.hidden_s`. Güven ≤ 0,35 × görünen dövüşçünün kimlik güveni. Sayımlara, kontrol
    süresine, momentuma, hakem kanıtına, 3.4 ölçümlerine girmez (tüketiciler olay türünü açık
    listelerle süzüyor; testler bunu sabitliyor). Ölçülen durum dizisi hiç değişmez. **Kullanıcı
    kararı bekliyor:** sayımlara / kontrol süresine / momentuma girsin mi (şimdilik girmiyor, 3a'daki
    kimlik çıkarımıyla aynı).
  - *Arayüz (asgari):* olay listesinde "Görünmeyen grappling (tahmini)" ve "Gizli rakip çıkarımı"
    etiketi (açıklamalı), zaman çizelgesinde iki şeritte kesikli çerçeve ve açıklaması.
  - *Khabib–Poirier (karalama işi 931d7565, yeniden hesap):* raunt içindeki "bilinmiyor" süresinin
    R1'de 102 / 183 sn'si (%55), R2'de 74 / 227 sn'si (%32), R3'te 13 / 96 sn'si (%13) "sarılı"
    tahmin edildi (R1'de 5 sn'si iki yandan taşınan "kırmızı üstte"); 13 parça. Kalan bilinmeyen
    çoğunlukla iki dövüşçünün de ölçülemediği yakın çekimler. Tahmin edilmeyen 12 bilinmeyen karenin
    6'sında da sarılıydılar, 5'i karar verilemeyen yakın çekim, 1'i ayrık: kural temkinli. Maç sonrası
    (dışlanan bölüm) 11,5 sn "sarılı" tahmini kalıyor (Khabib'in diz çöktüğü ve tekrarlarda yerde
    olduğu kareler); ilk kuralda kutlama boyunca ayakta tahmin sürüyordu, bölme ve 30 sn sınırı bunun
    için eklendi. Ölçülen sayımlar ve kontrol değişmedi (Khabib yer kontrolü 4,47 sn).
  - *Topuria–Volkanovski:* raunt içinde tahmin yok; raunt arasında (dışlanan bölüm, 5:13) 4,5 sn'lik
    tek parça.
  - *Bilinen sınırlar:* kimlik katmanı bir dövüşçüyü ayrık dururken uzun süre bulamazsa (benzer
    şort) yakınlıktan sonraki 30 sn içinde yanlış "sarılı" tahmini çıkabilir; sarılmanın bittiği an
    gecikmeli (rakip ayrılıp tekrar tanınana kadar). Tek kayıtla ayarlandı.
- **Raunt başı saatten geriye (Bölüm 2a kuralı):** ilk okuma tepeden 6 sn'den fazla, 20 sn'ye kadar
  aşağıdaysa başlangıç ilk okumadan geriye hesaplanır, `RoundSegment.start_extrapolated_s` (ilk okumaya
  kadar geçen süre) ile işaretlenir ve güveni × 0,85 olur (okuma yoğunluğu saatin okunabildiği kısım
  üzerinden). O an videodan önceyse (kayıt raunt içinde başlıyor), önceki rauntla çakışıyorsa ya da
  arada bir logo geçişi varsa (yayın rauntun içine dönmüş) geriye hesaplanmaz; o anın hemen önündeki
  (≤ 1 sn) logo geçişi rauntu başlatan geçiştir. Arayüzde raunt satırında "başı saatten geriye
  hesaplandı (N sn)" ve açıklaması. **Khabib–Poirier R3:** ilk okuma 670,0 sn'de 4:48; saat şeridi
  12 sn grafik altında (scorebug eşleşmesi ≈ 0), 655,9–657,3 sn'de logo geçişi. Yeni başlangıç
  657,5 sn = kare 19706 (elle düzeltilen kare 19720 = 658,0 sn; fark 0,47 sn, 14 kare), güven 0,60 → 0,51, işaret 12,5 sn. Örnek yayın ve
  sentetik tekrar klibinde rauntlar değişmedi. 20 sn sınırı: yayının bir rauntun içine sert kesimle
  (logo geçişsiz) geç dönmesini raunt başı sanmamak için; daha uzun kapalı saat kısmi raunt kalır.
- **Büyük poz modeli denemesi:** `yolo26x-pose.pt` (126 242 553 bayt, ultralytics/assets v8.4.0,
  GitHub'ın yayımladığı SHA-256 ile doğrulandı) yalnızca `local/bolum3b/models/` altına indirildi
  (git'e girmez, `local/` ile silinir); uygulamanın modeli (`yolo26s-pose`), model kayıt defteri ve
  `KEY_SCHEMA` değişmedi, hiçbir önbelleğe yazılmadı. 50 kare: `nms_probe.py`'nin 9 karesi + gizli rakip
  tahmininin karelerinden zamana yayılmış 41 kare; aynı ayarlar (imgsz 640, conf 0,25, iou 0,7,
  batch 4, CPU). Gözle sayım (`local/bolum3b/out/bigpose-*.jpg`, `bigpose-visual.json`): ikinci
  dövüşçüyü kullanılabilir iskeletle (≥ 6 gövde eklemi) yolo26x ≈ 15–17 karede, yolo26s ≈ 5–9 karede
  buluyor; x, s'nin bulduğu 4 karede kaybediyor; ikisi birden 3 karede. Kazanç çoğunlukla ayaktaki
  klinçte ve alttakinin bacakları göründüğünde; alttakinin gövdesi kapalı yer karelerinde ve yakın
  çekimlerde ikisi de bulamıyor; bulunan ikinci iskeletlerin çoğu kısmi (üst gövde ya da bacaklar).
  Otomatik sayım (s 28, x 34) seyircileri ve hakemi de saydığı için kullanılmadı. Süre: s 0,16, x 1,09
  sn/kare (6,6 kat). *Değerlendirme:* yalnızca bilinmeyen karelerde çalıştırmak Khabib–Poirier'de
  ≈ 15 200 kare × 1,09 sn ≈ 4,6 saat, yalnızca gizli rakip tahmini karelerinde ≈ 5 700 kare ≈ 1,7 saat
  ekler (tüm poz geçişi 1,5 saat); kazanç tahmin edilen karelerin ≈ üçte biri, kimlik katmanının o
  kısmi iskeletleri Poirier olarak tanıyıp tanımayacağı ayrıca belirsiz. **Önerim:** şimdi entegre
  edilmesin; GPU'lu bir makinede (x maliyeti küçük) ya da daha ucuz `yolo26l-pose` (58 MB) ile ikinci
  bir denemede yeniden bakılsın.

### Sonraki oturumlar için başlangıç notu (27 Kasım 2026)
(b) onaylandı; 3b kararları uygulandı (yukarıda) ve onaylandı (27 Kasım 2026); gizli rakip tahmini
şimdilik sayımlara, kontrol süresine ve momentuma girmiyor (kullanıcı ayrıca karar verirse
değişir); büyük poz modeli entegre edilmedi. Bölüm 3 (a, b ve 3b kararları) main'e birleştirildi;
repo aynı gün kullanıcının isteğiyle public yapıldı (AGPL-3.0, README başında İngilizce tanıtım,
Demo ekran görüntüleri `docs/images/`). (c) ayrıca başlar
(Bölüm 3.5–3.6: `RoundFeatures`, düzeltme katmanı, `python -m fight_analyzer.features` raunt
tablosu). Hazır olanlar: `dominance.measure` (3.4, herhangi bir aralık), olay önbelleğindeki kare
dizileri (`grappling`, `clinch_by`, `grappling_hidden` ve güveni / görülen dövüşçü),
`grappling.phase_seconds` (bilinmeyen ve "sarılı" tahmin edilen süre dahil; (c)'de raunt aralığıyla
çağrılacak), `grappling.active_control` (düzeltilmiş olay listesiyle yeniden hesaplanabilir), 10 Hz
`facing_away` / `wrists_measured`. Khabib–Poirier karalama işi `931d7565` (`local/fa-data`; adlar,
5 rauntluk unvan maçı ve elle düzeltilmiş R3 başı girili); karalama sunucusu kapalı, gerekince
"fa-scratch" yapılandırmasıyla açılır. Karelerle denetim yardımcıları `local/bolum3b/tools/`
altında (`run3b.py`, `grids3b.py`, `coverage.py`, `dets_at.py`, `nms_probe.py`, `gaps.py`, `pick.py`,
`frames_at.py`, `compare_sample.py`, `timing.py`; 3b kararları için `run_hidden.py`,
`hidden_probe.py`, `hidden_episodes.py`, `hidden_trace.py`, `hidden_blind.py`, `stretch_grid.py`,
`clock_probe.py`, `big_pose_test.py`, `fetch_big.py`).

- (a), (b) ve 3b kararları `v2/bolum-3` dalında yapıldı ve kullanıcının sözüyle main'e birleştirilip
  gönderildi (27 Kasım 2026). Repo public: geçmiş dahil herkes görebilir; `local/`, `data/`, videolar ve
  model ağırlıkları git dışında kalmalı.

### AI hakemlik (Aşama 9)
- Unified Rules 10-Point Must; kriter sırası katı: etkili vuruş/grappling →
  (eşitse) etkili agresiflik → (eşitse) alan kontrolü → 10-10.
- Deneme sayısı tek başına kazandırmaz (olası etki 1, yalnız temas 0,3, temassız
  ≈0,05). 10-8 etki şartı (knockdown ya da ≥5 olası etkili vuruş ve rakibin 3 katı).
- Üç sanal hakem aynı kanıtı farklı tartar (A vuruş, B grappling, C temkinli, 10-7 yok).
- Raund sınırları, bitiş şekli ve puan kesintileri **kullanıcı girdisi**
  (`MatchSetup`); sistem KO/TKO/submission'ı kendisi belirlemez. Bitiş girilmişse
  kartlar yalnızca bilgi amaçlıdır.
- Puan kararı yalnızca planlanan raundların hepsi işaretli ve puanlanabilirse;
  raunt için ≥30 sn kayıt ve dövüşçü başına ≥15 sn ölçüm gerekir.
- Güven en fazla "orta" (bağımsız doğrulama yok).

### Arayüz ve tasarım sistemi (v2 Bölüm 1)
Bölüm 1'de plana göre verilen kararlar (8 Kasım 2026):
- **Tokenlar:** Renk, yazı, boşluk, yarıçap, gölge ve hareket değerlerinin tek
  kaynağı `frontend/src/styles/tokens.css`; bileşenlerde renk kodu yok (bir test
  denetler). Koyu tema ileride aynı adları `:root[data-theme="dark"]` altında
  yeniden tanımlayarak eklenebilir. Hatalar için tabloda olmayan `--danger`
  eklendi (köşe kırmızısıyla karışmasın diye her zaman ikon ve metinle).
- **Kenarlık kontrastı:** `--border-strong` plandaki `#D4D4CE` yerine `#8f8f8a`.
  Giriş alanlarında ve sürükle-bırak çerçevesinde kullanıldığı için beyaz üstünde
  3:1'i geçmesi gerekiyordu (3,25:1; testle doğrulanır). Kart kenarlıkları ve
  ayırıcılar açık kalan `--border` ile çizilir.
- **Video katmanı (overlay) renkleri:** kırmızı `#ff2e4d` aynı kaldı; mavi
  `#19d6f0` (camgöbeği) yerine `#3d8bff` oldu, çünkü camgöbeği arayüzün
  `#2457c5` mavisiyle aynı aileden değildi; koyu sahnede 5,9:1 kontrast veriyor
  ve kırmızıyla benzer parlaklıkta. Diğer kişiler mavimsi gri yerine nötr gri
  (`#a8a8a2`). Tek kaynak `shared/overlay-style.json`; tarayıcı canvas'ı, MP4
  dışa aktarma ve `Fighter.color` (`store.py` → `CORNER_COLORS`) aynı dosyayı
  okur. `npm run gen:types` ayrıca DOM öğeleri için `overlay-tokens.css` üretir.
  Dışa aktarılmış eski MP4'ler eski renkte kalır.
- **Önizleme uç noktası:** geçmiş listesindeki 16:9 önizleme için
  `GET /jobs/{id}/thumbnail.jpg`. Analiz kopyasından 320 px JPEG üretir (seçim
  karesi, yoksa videonun %10'u) ve iş klasöründe `thumb-<anahtar>-<kare>.jpg`
  olarak önbelleğe alır; seçim ya da analiz kopyası değişince eski dosya
  silinir. Şema sürümü değişmedi. Analiz kopyası yoksa 404
  (`thumbnail_unavailable`); arayüz boş koyu kutu gösterir. Demo satırı
  önizlemeyi sentetik sahneden çizer.
- **Sayfa genişliği:** en fazla 1440 px (`--page-max`); **sonuç ekranı** Bölüm 5'e
  kadar eski 1640 px sınırını korur (`--page-max-wide`, `.shell__main--wide`).
  Sonuç ekranının genişliğine Bölüm 5'te karar verilecek.
- Fontlar yerel paket (Inter, Inter Tight); internetten font yüklenmez.
- Sonuç ekranına bu bölümde yalnızca renk ve yazı uygulandı; bileşen metinleri
  Bölüm 5'te `labels.ts`'e taşınacak. `StatPair` ve `Tabs` hazır ama o zamana
  kadar kullanılmıyor.

### Siyah-beyaz-kırmızı kimlik (v2 Bölüm 1 renk)
Bölüm 1'in aydınlık tasarımı üzerine verilen kararlar (12 Kasım 2026); yukarıdaki
Bölüm 1 kararlarıyla çeliştiği yerde bunlar geçerlidir:
- **Tek kırmızı:** `--red` `#c62b3b` yerine `#d0142c`; marka ve kırmızı köşe aynı
  ton. Siyah `--ink` `#0e0e10` (`--text-1` ile aynı), zemin `--bg` `#f2f2f0`.
  `--danger` (`#b42318`) ayrı kaldı ama kırmızıdan renkle ayırt edilemez (1,2:1);
  bu yüzden her zaman ikon ve metinle gösterilir.
- **`--accent`:** ilerleme çubukları, bölüm çizgileri ve aktif işlem adımı bu
  tokenı kullanır. Varsayılanı kırmızıdır; `AppShell` `<main>`'e `data-screen`
  yazar ve Seçim ile Sonuç ekranlarında `--accent` siyaha döner, çünkü orada
  kırmızı yalnızca kırmızı köşeyi anlatır. Üst bar ortak çerçeve olduğu için her
  ekranda kırmızı logo ve kırmızı aktif adım taşır.
- **Siyah üstünde kırmızı:** 3,5:1; yalnızca dolgu, çizgi ve ikon. Bir test,
  oran 4,5:1'i geçerse kuralın güncellenmesi için uyarır. İkinci bir açık kırmızı
  ya da mavi eklenmedi (koyu temayla değişti; aşağıdaki "Tema" bölümü).
- **Sonuç üst kartındaki momentum (geçici):** koyu (`--ink-2`) kutuda, küçük beyaz
  yüzdelerle; büyük ve beyaz bir kutu sayfanın odağı oluyor ve kazanma olasılığı
  gibi okunuyordu. Dikkat dövüşçü adlarında kalsın diye orta sütun daraltıldı.
  Payı metin olarak yüzdeler verir; çubuktaki kırmızı ve mavi yalnızca görseldir.
  Mavi `--ink-2` üstünde 2,6:1 kalıyordu; tema çalışmasında `--blue-on-ink` ile
  iki temada da 3:1'in üstüne çıktı. Momentum hesabı değişmedi; bu alanı Bölüm 5
  yeniden kurar.
- **Kenarlık:** `--border-strong` `#8f8f8a` yeni zeminde 2,9:1'e düştüğü için
  `#858580` (3,3:1). `--border` `#deded9`; kartlara `--shadow-card` eklendi.
- **Üst bar adımları:** onay işareti, açık ekrandan önceki adımlar demektir
  (ekran okuyucu "önceki adım" der); kabuk işin gerçek durumunu sorgulamaz.
- **Geçmiş satırı:** satır artık `<button>` değil; tek bağlantı "Aç"tır ve
  tıklama alanı satırın tamamını kaplar. Olay sayısı olay aşaması çalışana kadar
  boştur.
- **Tanımlar ("?"):** her biri hesaplamadan çıkarıldı ve `labels.ts`'te durur.
  "Diğer" olay türü üretilmediği için tanımı yok. "Yeniden bulma" ve "Geçici
  numara değişimi" ileri ve geri takip geçişlerinin toplamıdır; tanım bunu
  söyler. "Hakem kartları (AI)" sekmesine tanım eklenmedi; Bölüm 3–5'te yeniden
  kurulacak.
- **"?" balonu (v2/tema, 13 Kasım 2026):** kapalıyken `display: none`; görünmez
  olduğu halde sayfayı genişletiyordu (1024 px'te İşlem ekranı 7 px kayıyordu,
  telefonda sayfa genişliyordu). Açıkken `position: fixed` ve
  `ui/placeBubble.ts` onu ekranın içine yerleştirir: `align` tercih edilen kenar,
  ekran kenarına 8 px'ten fazla yaklaşmaz, yer yoksa alta/üste döner. Bu yüzden
  panelin kesmesi ya da sayfayı taşırması mümkün değil.
- **İşlem adımları:** "Sonuç hazırlama"nın analizde kendi backend aşaması yok;
  açıklaması yalnızca neyin açıldığını söyler. Momentum her yerde "deneysel"
  diye anılır, "puanlama" denmez.
- **Sonuç ekranı:** yerleşim değişmedi. Dokunulan bileşenlerin metinleri
  (`FighterHeader`, `StatPanel`, `TrackQuality`, `MomentumPanel`,
  `TrackingResult`, `ExportPanel`) `labels.ts`'e taşındı; diğerleri Bölüm 5'te.
  Demo'da "Veri kalitesi" grubu ve momentum kartı yok (veri yok).
- **Hitap:** yeni metinler ve dokunulan ekranlardaki yönergeler "sen" biçiminde.
- **Büyük harf:** sayfa `lang="tr"` olduğu için CSS büyük harfi Türkçe kurala göre
  çevirir (i → İ). Bu yalnızca sabit Türkçe arayüz etiketlerinde kullanılır; izinli
  seçiciler `frontend/tests/case-conversion.test.ts`'te. Dosya uzantıları,
  kısaltmalar, İngilizce terimler ("grappling", "Submission") ve dövüşçü adları
  yazıldığı gibi gösterilir; kodda yerele bağlı büyük harf dönüşümü yok (aynı test
  denetler). Adlar yalnızca baştaki ve sondaki boşluklar kırpılarak saklanır.

### Tema: Açık · Koyu · Sistem (v2/tema, 13 Kasım 2026)
Yukarıdaki iki bölümle çeliştiği yerde bunlar geçerlidir:
- **Seçim:** üst barda Analiz/Demo'nun yanındaki menü; varsayılan Sistem (işletim
  sisteminin teması, değişince sayfa yenilenmeden uyar). Seçim localStorage'da
  `fight-analyzer.theme` anahtarıyla saklanır; okuma ve yazma hata atarsa seçim o
  oturumda geçerli kalır. Mantık `frontend/src/app/theme.ts`; `index.html`
  içindeki küçük betik aynı kuralla `data-theme`'i ilk boyamadan önce yazar ve
  `<meta name="color-scheme">`'i günceller (dev sunucusunda CSS JS ile geldiği
  için stil yüklenmeden önceki ekran da doğru renkte). İkisini bir test aynı
  girdilerle karşılaştırır.
- **Renk rolleri:** aynı tokenın hem beyaz yazılı dolgu hem sayfadaki yazı/işaret
  olarak kullanılması koyu temada imkânsızdı (bir renk beyaza ve koyu karta aynı
  anda 4,5:1 veremez). Roller ayrıldı: dolgular (`--red`, `--red-strong`,
  `--blue`, `--warning-fill`, `--danger-fill`) iki temada aynı ve beyaz yazı
  taşır; sayfadaki köşe yazıları ve işaretleri `--red-fg` / `--blue-fg` (koyuda
  `#ff6b7a` / `#7aa5ff`); koyu yüzeydeki çubuklar `--red-on-ink` /
  `--blue-on-ink`; nötr dolgu `--primary` / `--on-primary` (açıkta siyah buton,
  koyuda beyaz buton ve siyah yazı); menü, diyalog ve bildirimler
  `--surface-raised`. Sürükle-bırak kartı da bant üstünde öne çıksın diye
  `--surface-raised`.
- **Koyu tema değerleri:** zemin `#0b0b0d`, kart `#151518`, yükseltilmiş yüzey
  `#1e1e22`, soluk dolgu ve hover `#242428` (yükseltilmiş yüzeyle aynı olunca
  menü ve diyaloglarda hover görünmüyordu); siyah bantlar (`--ink` `#141417`)
  zeminden bir ton açık ve `--ink-edge` kenarıyla ayrılır. Açık temada değişen tek renk momentum
  kutusundaki mavi (`#5b8cff`).
- **Video katmanı:** sahne, Demo sahnesi ve overlay renkleri iki temada aynıdır;
  koyu blok bunları tanımlamaz. Video üstündeki sarı uyarının ve Demo filigranının
  yazısı `--stage-on-bright`. Sahne koyu zeminle aynı renkte olduğu için
  resmin dışında `--ink-edge` kenarı alır. Boş sahnedeki dolgusuz bağlantılar
  ("Yükleme ekranına dön") sahne yazı rengini kullanır; açık temada siyah sahne
  üstünde siyah yazıydı (1,02:1). Tema değişince canvas token önbelleği temizlenir
  (`tokenVersion`) ve sahne, kırpıntılar ve önizleme sayfa yenilenmeden yeniden
  çizilir; zaman çizelgesi SVG ve CSS olduğu için kendiliğinden güncellenir.
- **Testler:** kontrast testleri iki tema için ayrı çalışır; yazı 4,5:1, köşe
  renkli grafikler (momentum çubuğu, zaman çizelgesi, ilerleme ve istatistik
  çubukları) 3:1. `tests/semantic-tokens.test.ts` aynı kuralda verilen yazı ve
  zemin çiftlerini iki temada, tanımsız `var()` kullanımını ve video sahnesinde
  temaya bağlı token kullanılmadığını denetler.
- **Zaman çizelgesi ekseni:** "%100 kırmızı", "%50", "%100 mavi" yazıları renkli
  alanın üstünde 4,5:1'in altına düşüyordu (açık temada da ≈3,3:1); kart renginde
  küçük bir zemin aldılar.
- **Skor kartı dışa aktarımı:** PNG/PDF henüz yok; geldiğinde her zaman açık
  temada üretilir (CLAUDE.md).

### Yerel güvenlik
- Yol sınırlama (`fsutil.inside`), en fazla 20 aktif analiz, analiz başına tek
  aktif dışa aktarma, yüklemeden önce boş disk denetimi, CDN'den yüklenen Swagger
  sayfası kapalı, Ultralytics telemetrisi kapalı.

## Doğrulama durumu

- Tek doğrudan maç klibi `topuria-oliveira.mp4` ayar için kullanıldı (ayar seti);
  sonuçları doğruluk değildir. Elle etiketli örnek: kimlik karışması 0, hakeme kayma
  0; vuruş denemesi 10 etiketten 4 eşleşti, 6 kaçtı, 1 yanlış
  (`validation/labels`, `validation/reports`).
- Bağımsız maç görüntüleriyle doğrulama **yapılmadı**.
- v2 3b: kullanıcının Khabib–Poirier kaydı yalnızca işlev denemesi için kullanıldı
  (yerelde): grappling'in çoğu ölçülemedi (yukarıda, "Grappling durumları...").
- Kullanıcının 9 dk Topuria–Volkanovski analizinde (yalnızca kopyada denendi) kartlar
  iki raundu Volkanovski'ye verdi (yalnızca olası temas farkıyla); 2. rauntaki
  nakavt knockdown olarak tespit edilmedi.

## Kalan işler

### Doğruluk (öncelikli)
- [ ] Ayar için kullanılmamış, doğrudan maç görüntüleriyle değerlendirme seti
  oluşturmak ve `python -m fight_analyzer.validation` ile raporlamak (benzer şort,
  tekrar/ağır çekim, uzun klinç ve yer mücadelesi içeren klipler dahil).
- [ ] Nakavt tespiti: düşen dövüşçünün kimliği belirsizleştiğinde/örtüştüğünde
  knockdown kaçıyor (Volkanovski KO'su, Oliveira KO'su). v2 3a: Volkanovski KO'su
  kimlik çıkarımıyla "olası, düşük güven" olarak bulunuyor; Oliveira klibinde
  denenmedi.
- [ ] Uzak/örtülü koldan atılan vuruşlar büyük ölçüde sayılmıyor (örnek yayında
  kabaca %35–40 yakalanıyor). Yerde üstten vuruş türü v2 3a'da eklendi; gerçek
  ground and pound görüntüsüyle denenmedi.
- [ ] Vuruş sonucu (v2 3a): isabet temkinli, gerçek isabetlerin çoğu "blok" ya da
  "belirsiz" kalıyor; eşikler tek yayınla ayarlandı. Sarsılma ve zorunlu geri
  çekilme gerçek bir sarsılma görüntüsüyle doğrulanmadı.
- [ ] "Olası temas" yakın mesafede çok sık çıkıyor; "olası etki" eşiği (0,3) ve
  ölçüsü gerçek etiketli verilerle ayarlanmalı.
- [ ] Grappling'de alttaki/arkadaki dövüşçü poz modelince bulunmuyor (iki dövüşçüye tek
  iskelet); Khabib–Poirier kaydında videonun %77'si "bilinmiyor" (v2 3b). 27 Kasım 2026: gizli
  rakip çıkarımı eklendi (raunt içi bilinmeyenin %13–55'i "sarılı" tahmini; ayakta / yerde
  ayrılmıyor); büyük poz modeli denendi (ikinci dövüşçü ≈ 1/3 karede, 6,6 kat süre; entegre
  edilmedi). Kalan: kullanıcı düzeltmesi ((c)); GPU'lu makinede ya da `yolo26l` ile yeniden deneme.
- [x] Raunt başı saatin ilk okumasından geriye hesaplanıyor (27 Kasım 2026; işaretli, güveni
  × 0,85; Khabib–Poirier R3 elle düzeltmeye 0,47 sn).
- [ ] Hakem profili ağırlıkları ve 10-8 eşikleri gerçek resmi skor kartlarıyla
  karşılaştırılarak ayarlanmalı (şu an tasarım değerleri).

### Ürün
- [x] Raunt sınırlarını önerme (scorebug saati / raunt arası tespiti), elle
  düzeltme her zaman geçerli (v2 Bölüm 2a).
- [ ] OCR'sız raunt arası tespitini gerçek bir yayın arasıyla denemek (örnek
  videoda aralar kesilmiş).
- [ ] Farklı yayıncıların scorebug'larıyla (üst bant, farklı saat biçimleri,
  onda bir saniye gösterimi) denemek; yalnızca UFC yayınıyla denendi.
- [ ] Tek seçimle kamera yakın çekime geçince kimlik uzun süre belirsiz kalıyor;
  uygulama bu durumda düzeltme noktası önermiyor.
- [ ] Submission girişimi yalnızca "olası" boyun sarma; yerde pozisyon yalnızca üst / alt
  (guard, mount, sırt yok); kafes konumu ölçülmüyor (v2 3b).
- [ ] Eski analizlerde "olası etki" ölçümü yok; yeniden seçim gerektiriyor — tek
  tıkla "hareket analizini yenile" düğmesi eklenebilir.
- [ ] Dışa aktarılan MP4'e raund skorları/hakem kartı katmanı (şu an yalnız JSON'da).
- [ ] Analiz ve dışa aktarmaları arayüzden silme.

### Bölüm 5 için arayüz notları (12 Kasım 2026)
- [ ] Yan paneldeki uzun metrik etiketleri ("İLERLEME / GERİ ÇEKİLME", "TAHMİNİ
  KONTROL SÜRESİ") büyük harf yerine cümle düzeninde yazılsın.
- [ ] Olay listesindeki % sütununa "Güven" başlığı gelsin (şu an başlıksız
  yüzde; açıklaması yalnızca fareyle üstüne gelince görünüyor).
- [ ] Zaman çizelgesinin sağındaki "%100 kırmızı", "%50", "%100 mavi" etiketleri
  üst üste biniyor.
- [ ] Sonuç üst kartındaki momentum kutusu geçici olarak koyu ve küçük; alan
  yeniden kurulurken dövüşçü adları odakta kalsın, pay kazanma olasılığı gibi
  okunmasın.

### Altyapı
- [ ] GPU (CUDA) yolu bu makinede denenemedi; NVIDIA kartlı bir makinede ölçülmeli.
- [ ] 60 dakikalık video uçtan uca çalıştırılmadı (CPU'da poz ≈5 saat).
- [ ] `httpx2` kurulmadı (Starlette test istemcisi uyarı veriyor; kurulum izni
  verilmemişti).
