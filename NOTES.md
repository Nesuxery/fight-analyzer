# Proje notları: önemli kararlar ve kalan işler

Son güncelleme: 20 Ekim 2026 (Aşama 9 sonrası). Ayrıntılı teknik açıklama
[README.md](README.md), kullanım [docs/KULLANIM.md](docs/KULLANIM.md).

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
- Sürümlü Pydantic sözleşmeleri tek doğruluk kaynağı (şema şu an **1.6.0**);
  JSON Schema ve TS tipleri bundan üretilir, `check.cmd` güncelliğini denetler.
- Önbellekler içerik adresli (anahtar = girdilerin özeti), pickle yok
  (JSON + `allow_pickle=False` .npy). Her önbelleğin kendi sürüm sabiti var
  (`KEY_SCHEMA "1.2.0"`, `IDENTITY_VERSION 5`, `CAMERA_VERSION 2`,
  `EVENTS_VERSION 2`, `MOMENTUM_VERSION 2`); mantık değişince ilgili sürüm artırılır,
  şema sürümü saatler süren poz çıkarımını yeniden yaptırmaz.

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

### Dışlanan bölümler (tekrar / ağır çekim)
- Otomatik ayırt edilemediği için kullanıcı işaretler. Dışlanan bölüm maç süresi
  değildir: olaylar sayılmaz/puanlanmaz, süreye bağlı puan ve ölçüm birikmez,
  momentum donar (maç zamanıyla söner).

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
- [ ] Raund sınırlarını önerme (skor tabelası saati / raund arası tespiti), yine
  kullanıcı onayıyla.
- [ ] Tek seçimle kamera yakın çekime geçince kimlik uzun süre belirsiz kalıyor;
  uygulama bu durumda düzeltme noktası önermiyor.
- [ ] Submission girişimi, pozisyon geçişleri ve kafes konumu ölçülmüyor.
- [ ] Eski analizlerde "olası etki" ölçümü yok; yeniden seçim gerektiriyor — tek
  tıkla "hareket analizini yenile" düğmesi eklenebilir.
- [ ] Dışa aktarılan MP4'e raund skorları/hakem kartı katmanı (şu an yalnız JSON'da).
- [ ] Analiz ve dışa aktarmaları arayüzden silme.

### Altyapı
- [ ] GPU (CUDA) yolu bu makinede denenemedi; NVIDIA kartlı bir makinede ölçülmeli.
- [ ] 60 dakikalık video uçtan uca çalıştırılmadı (CPU'da poz ≈5 saat).
- [ ] `httpx2` kurulmadı (Starlette test istemcisi uyarı veriyor; kurulum izni
  verilmemişti).
