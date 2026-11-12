# Proje notları: önemli kararlar ve kalan işler

Son güncelleme: 12 Kasım 2026 (v2 Bölüm 1: siyah-beyaz-kırmızı kimlik). Ayrıntılı
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
  ya da mavi eklenmedi.
- **Sonuç üst kartındaki momentum (geçici):** koyu (`--ink-2`) kutuda, küçük beyaz
  yüzdelerle; büyük ve beyaz bir kutu sayfanın odağı oluyor ve kazanma olasılığı
  gibi okunuyordu. Dikkat dövüşçü adlarında kalsın diye orta sütun daraltıldı.
  Payı metin olarak yüzdeler verir; çubuktaki kırmızı ve mavi yalnızca görseldir
  (mavi `--ink-2` üstünde 2,6:1, kırmızı 3,1:1). Momentum hesabı değişmedi; bu
  alanı Bölüm 5 yeniden kurar.
- **Kenarlık:** `--border-strong` `#8f8f8a` yeni zeminde 2,9:1'e düştüğü için
  `#858580` (3,3:1). `--border` `#deded9`; kartlara `--shadow-card` eklendi.
- **Üst bar adımları:** "tamamlandı" işareti, açık ekrandan önceki adımlar
  demektir; kabuk işin gerçek durumunu sorgulamaz.
- **Geçmiş satırı:** satır artık `<button>` değil; tek bağlantı "Aç"tır ve
  tıklama alanı satırın tamamını kaplar. Olay sayısı olay aşaması çalışana kadar
  boştur.
- **Tanımlar ("?"):** her biri hesaplamadan çıkarıldı ve `labels.ts`'te durur.
  "Diğer" olay türü üretilmediği için tanımı yok. "Yeniden bulma" ve "Geçici
  numara değişimi" ileri ve geri takip geçişlerinin toplamıdır; tanım bunu
  söyler. "Hakem kartları (AI)" sekmesine tanım eklenmedi; Bölüm 3–5'te yeniden
  kurulacak.
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
