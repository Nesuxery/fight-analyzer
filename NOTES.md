# Proje notları: önemli kararlar ve kalan işler

Son güncelleme: 14 Kasım 2026 (v2 Bölüm 2b: yayın kesmeleri ve tekrar ayıklama). Ayrıntılı
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
- Sürümlü Pydantic sözleşmeleri tek doğruluk kaynağı (şema şu an **1.8.0**);
  JSON Schema ve TS tipleri bundan üretilir, `check.cmd` güncelliğini denetler.
  Üretilen dosyalar (şema, TS tipleri, overlay dosyaları) `.gitattributes` ile her
  checkout'ta LF; denetim bayt bayt karşılaştırır ve gevşetilmedi.
- Önbellekler içerik adresli (anahtar = girdilerin özeti), pickle yok
  (JSON + `allow_pickle=False` .npy). Her önbelleğin kendi sürüm sabiti var
  (`KEY_SCHEMA "1.2.0"`, `IDENTITY_VERSION 5`, `CAMERA_VERSION 2`,
  `EVENTS_VERSION 2`, `MOMENTUM_VERSION 2`, `BROADCAST_VERSION 3`); mantık değişince
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
  omuzlarına göre ≥0,3 gövde boyu savrulması (eşik doğrulanmadı).
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
- Kullanıcının 9 dk Topuria–Volkanovski analizinde (yalnızca kopyada denendi) kartlar
  iki raundu Volkanovski'ye verdi (yalnızca olası temas farkıyla); 2. rauntaki
  nakavt knockdown olarak tespit edilmedi.

## Kalan işler

### Doğruluk (öncelikli)
- [ ] Ayar için kullanılmamış, doğrudan maç görüntüleriyle değerlendirme seti
  oluşturmak ve `python -m fight_analyzer.validation` ile raporlamak (benzer şort,
  tekrar/ağır çekim, uzun klinç ve yer mücadelesi içeren klipler dahil).
- [ ] Nakavt tespiti: düşen dövüşçünün kimliği belirsizleştiğinde/örtüştüğünde
  knockdown kaçıyor (Volkanovski KO'su, Oliveira KO'su).
- [ ] Uzak/örtülü koldan atılan vuruşlar ve yerde üstten vuruşlar (ground and
  pound) büyük ölçüde sayılmıyor.
- [ ] "Olası temas" yakın mesafede çok sık çıkıyor; "olası etki" eşiği (0,3) ve
  ölçüsü gerçek etiketli verilerle ayarlanmalı.
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
- [ ] Submission girişimi, pozisyon geçişleri ve kafes konumu ölçülmüyor.
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
