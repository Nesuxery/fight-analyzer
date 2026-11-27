# MMA Fight Analyzer — Kısa kullanım kılavuzu

Kayıtlı bir MMA maç videosunu **bu bilgisayarda** analiz eder: iki dövüşçüyü
video boyunca izler, iskeletleri videonun üzerine çizer, vuruş denemelerini ve
olası büyük olayları işaretler, hareket istatistiklerini ve **deneysel**
momentumu gösterir, sonucu MP4/CSV/JSON olarak dışa aktarır.

## 1. Kurulum ve başlatma

Gerekenler: Windows 10/11 (64 bit), [Python 3.14](https://www.python.org/downloads/),
[Node.js](https://nodejs.org) 22.12 veya üstü. Disk: kurulum CPU sürümüyle
≈ 1,3 GB (ölçüldü; CUDA'lı PyTorch birkaç GB daha ister); ayrıca videolar ve
önbellek için yer — yükleme, dosyanın iki katı + 2 GB boş alan yoksa reddedilir.

1. Proje klasöründe **`start.cmd`** dosyasını çift tıklayın (ya da komut
   satırında çalıştırın).
2. İlk çalıştırmada kurulum kendiliğinden yapılır: Python paketleri, arayüz
   paketleri ve poz modeli indirilir. **İnternet yalnızca bu adımda gerekir.**
3. Hazır olunca tarayıcı <http://127.0.0.1:5173> adresinde açılır. Kapatmak
   için komut penceresinde **Ctrl+C**.

Sunucular yalnızca `127.0.0.1` üzerinde dinler; aynı ağdaki başka cihazlar
erişemez. Videolar, sonuçlar ve dışa aktarılan dosyalar bilgisayardan çıkmaz;
analiz sırasında hiçbir dış bağlantı kurulmaz (Ultralytics çevrimdışı modda
çalışır, telemetri kapalıdır).

### Poz modeli

- Varsayılan model: `yolo26s-pose.pt` (resmi Ultralytics sürümü, SHA-256 ile
  doğrulanır). Kurulum bunu `data/models/` klasörüne indirir.
- Raunt saatini okuyan OCR modeli (PaddleOCR PP-OCRv5, Apache-2.0) de kurulumda
  `data/models/ocr/` klasörüne indirilir; elle:
  `..\.venv\Scripts\python.exe -m fight_analyzer.broadcast.ocr_model`
  (`backend` klasöründe). Yoksa analiz durmaz; saat okunmaz ve raunt
  sınırlarını elle girersin.
- Model eksik ya da bozuksa analiz "Poz modeli … bulunamadı" hatasıyla durur;
  analiz sırasında kendiliğinden indirme yapılmaz. Elle indirmek için:

  ```bash
  cd backend
  ..\.venv\Scripts\python.exe -m fight_analyzer.pose.models yolo26s-pose.pt
  ```

- Daha hızlı ama daha az hassas model: `yolo26n-pose.pt` (aynı komutla indirin,
  sonra `FA_POSE_MODEL=yolo26n-pose.pt` ortam değişkeniyle başlatın).

### İşlem birimi (CPU/GPU)

Uyumlu bir NVIDIA ekran kartı ve sürücüsü varsa kurulum CUDA'lı PyTorch kurar
ve analiz GPU'da çalışır; yoksa CPU kullanılır. `FA_DEVICE=cpu` CPU'yu zorlar,
`FA_DEVICE=cuda` istenip GPU yoksa CPU'ya geçilir ve bu durum sağlık
ekranında ("Sistem hazır" düğmesi) yazar. Ölçülen hızlar için bölüm 6'ya bakın.

### Tema

Üst bardaki güneş/ay/ekran simgesi Açık, Koyu ve Sistem seçeneklerini açar.
Sistem (varsayılan) bilgisayarın açık/koyu ayarını izler. Seçim bu tarayıcıda
saklanır. Video ve üzerindeki iskelet ve efekt renkleri iki temada aynıdır.

## 2. Analiz adımları

1. **Yükleme:** Videoyu sürükleyip bırakın ya da seçin (MP4, MOV, MKV, AVI,
   WEBM, M4V; en fazla 8 GB ve 60 dakika, en çok 3840×2160). Dosya önce
   tarayıcıda, sonra sunucuda FFmpeg ile doğrulanır.
2. **İşlem:** Video analiz kopyasına dönüştürülür ve her karede tüm kişilerin
   pozu çıkarılır. Aşamalar alt alta durum ikonu ve ilerlemeyle görünür; altında
   toplam ilerleme ve o anki aşamanın tahmini kalan süresi yazar. "İptal" bir
   onay penceresi açar; başarısız/iptal edilmiş iş "Analizi yeniden başlat" ile
   sürdürülebilir (önbellekteki adımlar tekrar yapılmaz).
3. **Dövüşçü seçimi:** Önerilen bir karede önce kırmızı, sonra mavi köşedeki
   dövüşçüye tıklayın: karedeki kutuya ya da altındaki "Bu karedeki kişiler"
   listesinde kişinin büyük karesine (klavyede Tab ile karelere gelip Boşluk).
   Seçilen kare köşe renginde çerçeve ve rozet alır. Dövüşçü adlarını sağdaki
   köşe satırlarında adın üstüne tıklayarak değiştirin (Enter kaydeder, Esc
   vazgeçer); adlar seçimle birlikte kaydedilir. Kamera değişiminden sonra
   kimlik karışırsa o karede düzeltme seçimi ekleyin ("Bu karede görünmüyor"
   da seçilebilir).
   **Maç ayarları** kartı (kişilerin altında): raunt sayısını (3 / 5) ve
   şampiyonluk maçını seç. Kart, yayın grafiğindeki (scorebug) saatten bulunan
   raunt sınırlarını kaynağı ve güveniyle gösterir; bunlar AI tahminidir.
   Saat bulunamazsa ya da yanlış yer okunduysa "Saat alanını düzelt" ile karede
   saatin etrafına dar bir dikdörtgen çiz (klavyede ok tuşları kaydırır, Alt+ok
   boyutu değiştirir) ve kaydet; yalnızca saat yeniden okunur, seçimlerin
   korunur. Scorebug'da okunan adlar yalnızca öneridir: "Öneriyi uygula" yalnızca
   adı girilmemiş köşeyi doldurur, yazdığın adın üstüne yazmaz (soldaki ad
   kırmızı köşeye önerilir).
4. **Sonuç:** Üstte deneysel momentum, iki yanda istatistikler, ortada video ve
   iskeletler, altta zaman çizelgesi bulunur. Olay listesinde bir olaya
   tıklayınca video olaydan 1 sn önceye gider. Kısayollar: Boşluk oynat/duraklat,
   ←/→ 1 sn, `,` `.` bir kare, S iskelet, E olay efektleri, D mesafe, F tam ekran.
   Videonun altındaki **Kapsam** seçici yan panellerin hangi aralığı
   gösterdiğini belirler: **Şu ana kadar** (videonun başından oynatma anına),
   **Raunt** (seçtiğiniz rauntun tamamı) ya da **Tüm maç**. Her panelin altında
   aralık yazar. "Veri kalitesi" bölümü aynı aralık için dövüşçünün ne kadar
   ölçülebildiğini, belirsiz süreyi ve güveni düşüren nedenleri (eksik görüntü,
   uzak ya da kötü kamera açısı, örtüşen dövüşçüler, düşük görüntü kalitesi)
   gösterir. Momentum kapsamdan etkilenmez; her zaman oynatma anındaki değerdir.
   Olay listesinde **"Kime ait belirsiz"** etiketi, olay anında kimlik güveninin
   düşük olduğunu söyler: olay sayılır ama momentuma puan eklemez. Kamera
   kesiminden hemen sonra dövüşçüler iç içe görünüyorsa kimlik, dövüşçüler
   birkaç kare ayrı görülene kadar düşük güvenli ("Örtüşme") sayılır.
   **"Görünmeyen grappling (tahmini)"** satırları ve **"Gizli rakip çıkarımı"**
   etiketi: dövüşçüler sarılınca poz modeli çoğunlukla ikisine tek iskelet verir
   ve biri ölçülemez. Az önce yakın oldukları ya da görünen dövüşçü yerde olduğu
   için o sürede sarılı oldukları tahmin edilir (ayakta mı yerde mi olduğu
   söylenmez). Bu bir ölçüm değildir: sayımlara, kontrol süresine ve momentuma
   girmez; zaman çizelgesinde kesikli çerçeveyle gösterilir.
5. **Dışlanan bölümler (tekrar, raunt arası, giriş, maç sonrası):** Dövüş
   süresi olmayan bölümler otomatik dışlanır ve zaman çizelgesinin altındaki
   **"Dışlanan bölümler"** listesinde "otomatik" etiketi, nedeni, güveni ve
   dayanağıyla görünür (ör. "raunt sınırlarının dışında", "scorebug ekranda yok,
   dövüş saati durdu"). Yanlış olanı **"Geri al"** ile tek tıkla dövüş süresine
   geri katın; **"Yeniden dışla"** ile yeniden dışlayın. Otomatik bulunmayan bir
   bölümü **"Bölüm dışla…"** ile başlangıç ve bitiş karesini seçerek elle
   dışlayın. Dışlanan bölümdeki olaylar listede "Dışlandı" etiketiyle kalır ama
   sayılmaz ve puan üretmez; ilerleme/kontrol süresi ve ölçülen süre birikmez;
   momentum bölüm boyunca donar. Listenin altında kaç olayın sayılmadığı yazar.
   Raunt sınırını değiştirince dövüş dışı bölümler de onunla birlikte değişir.
   Bunlar AI tahminidir: maçın bittiği videodan kesin anlaşılamıyorsa (ör.
   nakavttan sonra scorebug kayboldu) "Maç sonrası" düşük güvenle gelir; maçın
   bitişini "Maç bilgileri"ne girerseniz kesinleşir.
6. **Dışa aktarma:** "Dışa aktar" sekmesinde videoya işlenecek göstergeleri
   seçip başlatın. İş arka planda çalışır; bu sırada videoyu izlemeye devam
   edebilirsiniz. Bitince MP4, CSV ve JSON indirme düğmeleri çıkar.

## 3. Çıktılar nerede?

| Ne | Konum |
|---|---|
| Yüklenen videolar | `data/uploads/<sha256>/` (aynı dosya bir kez saklanır) |
| Analiz kopyası, pozlar, kimlikler, olaylar, momentum | `data/cache/…` (yeniden kullanılır) |
| Dışa aktarılan MP4 / CSV / JSON | `data/jobs/<dışa-aktarma-no>/` (`overlay.mp4`, `metrics.csv`, `analysis.json`); indirince tarayıcının indirme klasörüne de kopyalanır |
| İş kayıtları | `data/jobs.sqlite3` |
| Poz modelleri | `data/models/` |

Tüm veriyi silmek için uygulamayı kapatıp `data` klasöründeki `uploads`,
`cache` ve `jobs` klasörlerini ve `jobs.sqlite3` dosyasını silebilirsiniz
(`models` kalabilir).

## 4. Momentum ne demek?

Momentum **deneysel bir göstergedir, kazanma olasılığı değildir.** Ölçülen
olaylardan puan toplanır, her puan 20 saniyede yarıya iner:

- vuruş denemesi (yumruk, diz) 1 · tekme denemesi 1,3 · olası temas +0,3
- rakibe doğru ilerlenen her saniye 0,2 · tahmini yer kontrolünün her saniyesi 0,5
- yeterli kanıtı olan olası knockdown 4 · olası takedown 2,5

Kırmızı payı = 100 × (kırmızı puan + 4) / (iki tarafın puanı + 8); mavi = 100 −
kırmızı. Veri yokken %50/%50 görünür. Ağırlıklar başlangıç tasarım
değerleridir, spor bilimiyle doğrulanmış değildir. "Olaylar ve momentum"
sekmesi her puanın nereden geldiğini ve seçili olayın payı ne kadar
değiştirdiğini gösterir. Dövüşçülerden biri ölçülemediğinde "Veri yetersiz"
yazar ve yeni olay üretilmez.

## 4a. Hakem kartları (AI tahmini)

Sonuç ekranındaki **"Hakem kartları (AI)"** sekmesi her raundu MMA Unified Rules'un
10-Point Must sistemine göre üç sanal hakemle puanlar. **Bu bir AI tahminidir;
resmi hakem kararı ya da resmi maç sonucu değildir.** Momentum puanlamada
kullanılmaz.

**Önce maç bilgilerini kontrol edin** (sekmenin altındaki "Maç ayarları" ve
"Maç bilgileri"):
- *Raunt sayısı* (çoğu maçta 3, şampiyonluk maçında 5): "Maç ayarları"nda.
- *Raunt sınırları:* scorebug saati okunabildiyse otomatik bulunur
  ("scorebug saatinden", güven yüzdesiyle). Raundun ilk saniyelerinde saat bir
  grafiğin altında kaldıysa başlangıç saatin ilk okunduğu andan geriye
  hesaplanır; satırda "başı saatten geriye hesaplandı" yazar ve güven biraz
  düşüktür. Düzeltmek için sınırı zaman
  çizelgesinde sürükle ya da tutamacı seçip ok tuşlarıyla kaydır (Shift ile
  5 sn, Delete rauntu siler); "Raunt ekle (şu andan)" oynatma anından bir
  raunt ekler. Dokunduğun raunt "elle girildi" olur ve **otomatiği her zaman
  ezer**; "Otomatiğe dön" geri alır. Saat okunamadıysa rauntları buradan ya da
  "Maç bilgileri"ndeki "Başlangıç / Bitiş = şimdiki kare" ile işaretle.
  Raunt yoksa tüm video tek raunt sayılır.
- Eski bir analiz açılınca "Bu analiz eski sürümle yapıldı — yeniden işle"
  bandı çıkar; "Yeniden işle" raunt tespitini ekler (pozlar önbellekten gelir,
  kaynak video dosyası gerekir).
- *Maç nasıl bitti?* KO, TKO, submission, diskalifiye, hakem/doktor durdurması,
  no contest ya da puan kararı. Sistem bitiş şeklini videodan belirlemez.
- *Puan kesintileri* (faul nedeniyle hakemin aldığı puanlar).

**Nasıl puanlanır?**
1. **Etkili vuruş ve etkili grappling** (birincil kriter): olası knockdown,
   *olası etkili vuruş* (temasın hemen ardından rakibin başı gövdesine göre
   savrulmuşsa), olası temaslı vuruş (daha düşük ağırlık), kontrole dönen
   takedown, üst kontrol süresi. Temassız denemeler çok az ağırlık taşır; deneme
   sayısı tek başına raund kazandırmaz.
2. **Etkili agresiflik:** yalnızca birinci kriter denkse; rakibe doğru baskı ve
   bitirmeye yönelik deneme.
3. **Müsabaka alanı kontrolü:** yalnızca ilk ikisi denkse; ileri-geri hareket ve
   üst pozisyon.
4. Hiçbir fark yoksa **10-10**. **10-8** için etki şarttır, buna baskınlık ve/veya
   süre eşlik etmelidir; **10-7** etki, baskınlık ve sürenin birlikte ezici olduğu
   durumlar içindir.

**Üç sanal hakem** aynı kanıtı kuralların izin verdiği aralıkta farklı tartar:
Hakem A vuruş etkisine, Hakem B takedown ve kontrole biraz daha ağırlık verir;
Hakem C daha net fark arar ve 10-8 için üç koşulu ister. Kartlar birleşince
**oybirliğiyle**, **bölünmüş** ya da **çoğunluk kararı** (ve beraberlik türleri)
hesaplanır.

**Sonuç ne zaman hesaplanır?**
- Bitiş girildiyse (KO, TKO vb.) kazanan sizin girdiğiniz bilgidir; kartlar
  yalnızca bilgi amaçlı gösterilir ve kararı belirlemez.
- Puan kararı için planlanan raundların hepsi işaretlenmiş ve puanlanabilmiş
  olmalıdır. Kayıt eksikse ya da bitiş bilinmiyorsa sonuç hesaplanmaz ve nedeni
  yazılır.
- Bir raundun en az 30 sn'si kayıtta değilse ya da dövüşçülerden biri 15 sn'den
  az ölçülebildiyse o raund puanlanmaz (veri uydurulmaz).

**Güven seviyesi** ölçüm kapsamından (dövüşçülerin ne kadar ölçülebildiği),
kimlik takibinden, kamera hareketinden, yerde geçen süreden, kanıtın türünden
(etki mi, yalnızca deneme mi) ve hakemlerin uyumundan hesaplanır. Tespit
sistemi bağımsız maç görüntüleriyle doğrulanmadığından güven en fazla "orta"
gösterilir. Raund ayrıntısında ölçülen kanıt, en etkili anlar (tıklayınca
videoda o ana gider), hasar ve güreş üstünlüğü özetleri ile ölçülemeyenler
(gerçek hasar, submission girişimleri, pozisyon geçişleri, kafes konumu) listelenir.

## 5. Bilinen sınırlamalar

Bu sonuçlar tek kameralı 2B poz tahminine dayanır; derinlik ve temas
doğrudan ölçülmez. Görülen sorunlar (ayar için kullanılan klipte elle etiketli
küçük örnekten; ayrıntı ve sayılar `validation/` klasöründe):

- **Uzak/örtülü kol:** Vuran kol diğer dövüşçünün arkasında kalırsa deneme
  kaçabilir (örnekteki nakavt vuruşu bulunamadı).
- **Yerde üstten vuruşlar:** Kurallar ayakta, rakibin üst gövdesine uzanan
  denemeler için ayarlı; yerdeki dövüşçüye üstten atılan vuruşların çoğu sayılmaz.
- **"Olası temas" vurulduğu anlamına gelmez:** Yalnızca uzvun görüntüde rakiple
  örtüştüğünü söyler.
- **Çok yakın temas ve hakem:** Dövüşçüler ve hakem üst üste binince poz
  modeli birleşik ya da eksik kutu üretebilir; kimlik kısa süre "belirsiz"
  olur ya da birleşik kutuya bağlanabilir. Zaman çizelgesi ve "Kimlik takibi"
  sekmesi bu aralıkları gösterir.
- **Kamera değişimleri ve yakın çekimler:** Kimlik görünüme göre kurulur; çok
  benzer görünen dövüşçüler (benzer şort rengi) bu klipte denenmedi.
- **Tekrar/ağır çekim** yayın sinyallerinden (scorebug'ın kaybolması, saatin
  durması, logo geçişi, ağır çekim; en az ikisi) otomatik dışlanır. Yöntem tek
  bir örnek yayın ve sentetik bir kliple ayarlandı, bağımsız kayıtla
  doğrulanmadı; scorebug'ı olmayan yayınlarda çoğu tekrar bulunamaz. Listeyi
  gözden geçirin, eksik olanı elle dışlayın.
- **Doğruluk:** Ayardan bağımsız, doğrudan maç görüntüleriyle doğruluk ölçümü
  henüz yapılmadı. Kendi kliplerinizde denemek için bölüm 7'ye bakın.

## 6. Ölçülen işlem süreleri (bu bilgisayar)

Ölçüm: Intel Core i5-12450H (8 iş parçacığı), yalnızca CPU, 1280×720 video,
model girişi 640 px. GPU bu bilgisayarda olmadığı için GPU süresi ölçülmedi.

| İş | Ölçülen |
|---|---|
| Poz, `yolo26s-pose.pt` (varsayılan) | 148–172 ms/kare (327 karelik klip, 5 koşu); 30 fps'lik 1 dakika ≈ 4,5–5 dk |
| Poz, `yolo26n-pose.pt` | 68 ms/kare; 30 fps'lik 1 dakika ≈ 2 dk |
| 5 dk 28 sn video (9842 kare), varsayılan model | poz ≈ 30 dk (başka işlerle aynı anda), kimlik + olaylar + momentum 2,3–2,7 dk, MP4 dışa aktarma 4–4,5 dk |
| Raunt tespiti ve tekrar ayıklama (scorebug, 9 dk 1080p yayın, 14 Kasım 2026) | ≈ 60–65 sn (poz süresinin ≈ %2'si; tekrar ayıklama eklenince artmadı); eski analizi yeniden işleme toplam ≈ 75 sn |
| Aynı videoyu yeniden yükleme | 0,1 sn (video kopyası ve pozlar önbellekten) |
| Dövüşçüleri yeniden seçme / taraf değiştirme | saniyeler (pozlar yeniden çıkarılmaz) |
| Bölüm dışlama, otomatik bölümü geri alma, raunt sınırı düzenleme (14 Kasım 2026) | anında (momentum ≈ 0,1 sn, sonuç ekranı açık kalır) |
| Bellek (5,5 dk video) | en yüksek ≈ 780 MB (poz aşaması, model yüklü) |

Süre video uzunluğuyla doğru orantılıdır; sayfadaki ilerleme çubuğu ölçülen
hızdan kalan süreyi tahmin eder.

## 7. Kendi klibinizle doğrulama

Bir analiz bittikten sonra (backend klasöründe):

```bash
..\.venv\Scripts\python.exe -m fight_analyzer.validation sheet <analiz-no> --every 10
```

`data/validation/<analiz-no>/` klasöründe numaralı kutulu kareler ve bir
etiket şablonu oluşur. Şablona her karede kırmızı/mavi dövüşçünün ve hakemin
kutu numarasını, vuruş denemelerinin karesini yazın; `role` alanını
klip ayar için hiç kullanılmadıysa `evaluation` bırakın. Sonra:

```bash
..\.venv\Scripts\python.exe -m fight_analyzer.validation report <analiz-no> etiketler.json
```

Rapor kimlik karışması, hakeme kayma, belirsiz takip, eşleşen/kaçırılan/yanlış
vuruş sayılarını verir. Küçük örneklerde yüzde değil sayı raporlanır.

## 8. Sorun giderme

| Mesaj | Ne yapmalı |
|---|---|
| "… portu kullanımda" | Uygulama zaten açık olabilir; kapatın ya da `FA_API_PORT` / `FA_WEB_PORT` ile başka port verin. |
| "Python 3.14 bulunamadı" / "Node.js bulunamadı" | İlgili programı kurun, `setup.cmd` çalıştırın. |
| "Poz modeli … bulunamadı ya da bozuk" | Bölüm 1'deki indirme komutunu çalıştırın. |
| "Dosya … sınırını aşıyor", "Video çok uzun", "Çözünürlük çok yüksek" | Videoyu kısaltın/küçültün ya da `FA_MAX_UPLOAD_MB`, `FA_MAX_DURATION_S` ile sınırı değiştirin. |
| "Diskte yeterli boş alan yok" | Yer açın ya da eski analizlerin `data/cache` içeriğini silin. |
| "Aynı anda en fazla 20 … analiz" | Bekleyen/seçim bekleyen analizleri tamamlayın veya iptal edin (`FA_MAX_ACTIVE_JOBS`). |
| "Dosya çözümlenebilir bir video değil", "Video kareleri çözülemedi" | Dosya bozuk ya da desteklenmeyen kodekte; başka bir kopyayı deneyin. |
| "Analiz işçisi iş sırasında durdu" | Uygulamayı yeniden başlatın; yarım kalan iş 30 sn sonra kendiliğinden kuyruğa döner. |
