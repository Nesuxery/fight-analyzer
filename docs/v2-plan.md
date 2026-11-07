# Fight Analyzer v2 — Claude Code Prompt Paketi

Nov 6, 2026 · @Berkay

## Nasıl kullanılır

Bu paket Fight Analyzer'ı yedi adımda v2'ye taşır: roundları ABC'nin 2025 kriterlerine göre puanlayan bir hakem motoru, kayıt bitince kazananı açıklayan bir karar ekranı ve aydınlık, minimalist bir arayüz.

1. Bölüm 0'ı bir kez çalıştır. Kuralları CLAUDE.md'ye yazar; Claude Code bu dosyayı her oturumda okuduğu için sonraki bölümler kısa kalır.
2. Her bölüme temiz bir oturumla başla (/clear) ve bölümü başlığıyla birlikte olduğu gibi yapıştır.
3. Claude Code önce bir plan çıkarıp onayını bekleyecek. Planı oku, gerekirse düzelt, sonra onayla.
4. Bölüm bitince testleri çalıştır, uygulamayı örnek videoyla dene ve commit at. Sonra sıradakine geç.
5. Alternatif: Dokümanı Markdown olarak dışa aktarıp repoya `docs/v2-plan.md` olarak koy. O zaman "docs/v2-plan.md içindeki Bölüm 3'ü uygula" demen yeterli.

| Bölüm | Sonuç | Önce gereken |
| --- | --- | --- |
| 0 — Proje kuralları | CLAUDE.md'de puanlama ilkeleri ve çalışma düzeni | — |
| 1 — Tasarım sistemi | Aydınlık tema, tokenlar, bileşenler; Yükleme, İşlem ve Seçim ekranları yenilenmiş | 0 |
| 2 — Veri temeli | Otomatik round tespiti, replay ayıklama, daha az kimlik karışması | 0 |
| 3 — Olaylar ve metrikler | İsabet tahmini, önemli vuruş, hasar sinyalleri, knockdown, grappling durumları, round bazlı istatistik | 2 |
| 4 — Hakem motoru | Üç sanal hakem, 10-9 / 10-8 / 10-7, karar türleri, bitiş ve puan kesintisi | 3 |
| 5 — Sonuç deneyimi | Skor tablosu, canlı round kartı, video sonunda karar ekranı, gerekçeler | 1, 4 |
| 6 — Doğrulama | Resmi sonuçlarla kıyas, doğruluk raporu, kalibre edilmiş ağırlıklar | 4, 5 |

Mevcut "Hakem kartları (AI)" modülü ve onu kuran önceki prompt'un gereksinimleri korunur. Bölüm 4 yalnızca 2025 kurallarıyla çelişen dört noktayı değiştirir; ikinci bir puanlama sistemi kurulmaz.

## Mevcut paneller yeterli mi?

Hayır. Paneller dövüşçülerin ne kadar denediğini ve hareket ettiğini gösteriyor; ABC'nin 2025 kriterlerinde ise roundu isabet eden ve hasar veren eylemler kazandırıyor.

| Paneldeki metrik | 2025 kriterlerindeki yeri | Öneri |
| --- | --- | --- |
| Vuruş denemeleri, Tekmeler | Deneme puan getirmez; sonuç sayılır | İsabet, blok, ıska ve önemli vuruş ayrımı; hedef bölge (Bölüm 3) |
| Olası büyük olaylar | Doğru yön: hasar en değerli bileşen | Knockdown, sarsılma, ağır kafa vuruşu ve çıktı düşüşü olarak ayrıştır |
| Tahmini kontrol süresi | Yalnızca pozisyon tutmak baskınlık sayılmaz | Vuruş veya submission tehdidiyle geçen aktif kontrolü ayrı ölç |
| Baskı, İlerleme / Geri çekilme | Yalnızca etkili tekniklerde hiç fark yoksa bakılır | Saldırganlık ve alan kontrolü altına al, İstatistikler sekmesine taşı |
| Aktivite /100 | Kriterlerde karşılığı yok | Kaldır ya da "dakikada önemli deneme" ile değiştir |
| Momentum (deneysel) | Puanlamaya girmemesi doğru; ama üstte büyük yüzdeyle durunca kazanma olasılığı gibi okunabiliyor | Formülü koru; skor şeridiyle karışmasın diye "Olaylar ve momentum" sekmesine ve zaman çizelgesine taşı (Bölüm 5) |
| Kimlik takibi | Puanlamanın ön koşulu; yanlış sahiplik skoru bozar | Veri kalitesi sekmesine taşı; 124 ve 87 geçici numara değişimini azalt (Bölüm 2) |

Tamamen eksik olanlar: round ayrımı, takedown, submission ve ters çevirme, puan kesintisi, bitiş tespiti, resmi sonuçla kıyas. Ayrıca Volkanovski panelinde "00:00 – 01:06 arası" başlığı altında 42 sn ölçülebilir ve 59 sn belirsiz süre görünüyor. Toplam 101 sn ettiği için kimlik metrikleri başka bir aralıktan hesaplanıyor olabilir.

## Bölüm 0 — Proje kuralları (CLAUDE.md)

Görev: Aşağıdaki kuralları projenin kökündeki CLAUDE.md dosyasına "Fight Analyzer v2" başlığıyla ekle. Mevcut içeriği koru; çelişen bir kural görürsen değiştirmeden önce bana sor. Bu görevde başka kod değişikliği yapma.

### Hedef

Fight Analyzer kayıtlı MMA videolarını tamamen yerelde analiz eder. v2 hedefi: roundları ABC kurallarına göre puanlayan bir hakem motoru, kayıt bitince kazananı açıklayan bir karar ekranı ve aydınlık, minimalist bir arayüz.

### Puanlama ilkeleri

- Referans metin: ABC "MMA Bout Scoring — Judging Criteria Clarification" (Temmuz 2025, Ağustos 2025'te onaylandı). 2017 metnindeki "önce saldırganlık, sonra alan kontrolü" sırası ve "üç kriterden ikisi varsa 10-8" kuralı artık geçerli değil.
- Skoru deterministik bir kural motoru üretir. Aynı girdi ve aynı seed her zaman aynı sonucu verir.
- Gerekçe metinleri şablondan üretilir. Metin katmanı skoru asla değiştirmez.
- Yalnızca ofansif eylemlerin sonucu puanlanır; savunma puanlanmaz. Round kazananı yalnızca deneme veya aktivite sayısıyla belirlenmez.
- Her türetilmiş metrik bir güven değeri (0–1) taşır. Düşük güvenli veri arayüzde öyle gösterilir, kesinmiş gibi sunulmaz.
- Kesin tespit edilemeyen bir olay gerçekmiş gibi kaydedilmez; `unknown` ya da "belirsiz" olarak işaretlenir. Eksik görüntü, kamera açısı, örtüşme veya düşük görüntü kalitesi güveni düşürüyorsa nedeniyle birlikte gösterilir.
- Bitişler (KO, TKO, submission, diskalifiye, hakem durdurması) puan kararıyla karıştırılmaz; onaylı bitiş kartlardan önce gelir.
- Mevcut momentum sistemi korunur. Puanlamaya girmez; kazanma olasılığı ya da hakem puanı gibi gösterilmez.
- Kullanıcı düzeltmeleri (olay, sahiplik, round sınırı, puan kesintisi, bitiş) ham tespitten ayrı saklanır ve puanlamayı yeniden tetikler.
- Kural seti sürümlüdür (`abc_2025`). Komisyona göre değişen eşikler ve tüm ağırlıklar koda gömülmez, config'ten okunur.
- Sonuç arayüzün her yerinde "AI tahmini" olarak etiketlenir; resmi sonuç değildir.

### Çalışma düzeni

- v2 görevlerinde önce ilgili kodu oku, mevcut yapıyı kısaca özetle ve bir uygulama planı çıkar. Onayımı almadan kod yazma.
- Mevcut özellikleri bozma: yükleme, iş kuyruğu, seçim, overlay oynatıcı, zaman çizelgesi, olay listesi, dışlanan bölümler, MP4/CSV/JSON dışa aktarma, geçmiş analizler, Demo modu.
- Veri sözleşmeleri Pydantic modellerinde tanımlanır. JSON Schema ve TypeScript tipleri mevcut üretim akışıyla yeniden üretilir; elle TS tipi yazma.
- Analiz şeması değişirse sürümünü artır. Eski analizler açılabilir kalsın; gerekiyorsa "Bu analiz eski sürümle yapıldı — yeniden işle" uyarısı göster.
- Ağır işler (OCR, tespit, puanlama) analiz worker'ında çalışır. Yeni bağımlılıklar CPU'da ve çevrimdışı çalışmalı; eklemeden önce gerekçesini yaz.
- Kod tanımlayıcıları İngilizce. Arayüz metinleri Türkçe ve tek bir metin dosyasında toplanır. `<html lang="tr">` korunur, böylece büyük harfte İ ve I doğru çıkar.
- Bitirmeden önce pytest, node --test ve oxlint çalıştır. Hepsi geçmeden "bitti" deme.
- Teslim raporu: değişen dosyalar, nasıl test edildiği, bilinen sınırlamalar, açık sorular.

### Terimler

| Arayüz (TR) | Kod (EN) |
| --- | --- |
| Kırmızı köşe / Mavi köşe | red / blue corner |
| Hasar · Baskınlık · Süre | damage · dominance · duration |
| Başarılı vuruş / grappling | successful striking / grappling |
| Saldırganlık · Alan kontrolü | aggressiveness · fighting area control |
| Önemli vuruş · Yere düşürme | significant strike · knockdown |
| Kontrol süresi · Aktif kontrol | control time · active control |
| Submission denemesi · Ters çevirme | submission attempt · reversal |
| Puan kesintisi | point deduction |
| Oybirliği · Bölünmüş · Oy çokluğu kararı | unanimous · split · majority decision |
| Teknik karar · Sonuçsuz · Diskalifiye | technical decision · no contest · disqualification |

## Bölüm 1 — Aydınlık premium tasarım sistemi

Görev: Arayüzü koyu temadan aydınlık, minimalist ve premium bir görünüme taşı. Bu bölümde tasarım sistemini kur ve Yükleme, İşlem, Seçim ekranlarını yenile. Sonuç ekranına yalnızca yeni renkleri ve tipografiyi uygula; düzenini Bölüm 5'te yeniden kuracağız. Koyu tema seçeneği kapsam dışı, ama tokenları ileride eklenebilecek şekilde kur.

### İlkeler

- Renk yalnızca köşeleri (kırmızı, mavi) ve durumları anlatır; geri kalan her şey nötr.
- Ayrım gölgeyle değil, 1 px ince çizgiyle yapılır. Gölge yalnızca açılır menü, diyalog ve bildirim gibi yüzen katmanlarda.
- Rakamlar öne çıkar: istatistikler büyük ve eşit genişlikli rakamlarla, etiketler küçük ve sakin.
- Video sahnesi koyu kalır. Aydınlık sayfada koyu, köşeleri yuvarlatılmış bir video kapsayıcısı görüntüyü öne çıkarır.
- Neon, parlama, degrade ve süs ikonu yok. Başlıklar cümle düzeninde ("Maç videosunu yükle"); büyük harf yalnızca küçük etiketlerde.

### Renk tokenları

Tek kaynak CSS değişkenleridir; Tailwind kullanılıyorsa config bu değişkenleri okur. Bileşenlerde sabit renk kodu yazılmaz.

| Token | Değer | Kullanım |
| --- | --- | --- |
| --bg | #F7F7F5 | Sayfa zemini |
| --surface | #FFFFFF | Kartlar, paneller, üst bar |
| --surface-muted | #F1F1EE | Seçili satır, ikincil zemin, hover |
| --border | #E6E6E1 | Kenarlıklar, ayırıcılar |
| --border-strong | #D4D4CE | Giriş alanları, sürükle-bırak çerçevesi |
| --text-1 | #111111 | Ana metin, ana buton zemini |
| --text-2 | #52524C | İkincil metin |
| --text-3 | #6E6E68 | Etiketler, yardımcı metin |
| --red | #C62B3B | Kırmızı köşe |
| --red-soft | #FBEEF0 | Kırmızı köşe zemin tonu |
| --blue | #2457C5 | Mavi köşe |
| --blue-soft | #EDF2FC | Mavi köşe zemin tonu |
| --success | #1F7A4D | Tamamlandı, iyi veri kalitesi |
| --warning | #9A6100 | Düşük güven, veri yetersiz |
| --stage | #0B0B0C | Video sahnesi |

Video üstündeki iskelet ve olay efektleri koyu görüntüde okunmalı. Mevcut canlı tonları koru; arayüzdeki köşe renkleriyle aynı aileden olsunlar.

### Tipografi

- Arayüz: Inter (variable), taban 14 px, satır yüksekliği 1.5, ağırlıklar 400, 500, 600.
- Başlıklar ve skor rakamları: Inter Tight 600. 700 üstü ağırlık kullanma.
- Ölçek: 12, 13, 14, 16, 20, 24, 32, 44 px.
- Etiketler: 11–12 px, büyük harf, harf aralığı 0.06em, renk --text-3.
- Tüm istatistik ve saatlerde `font-variant-numeric: tabular-nums`.
- Fontlar yerel paketlerle gelir (@fontsource). Uygulama çevrimdışı çalıştığı için CDN kullanma.

### Boşluk, şekil, hareket

- 4 px ızgara; yaygın aralıklar 8, 12, 16, 24, 32, 48.
- Köşe yarıçapı: 8 (buton, giriş), 12 (kart), 16 (video sahnesi, büyük panel), 999 (hap).
- Yüzen katman gölgesi: `0 8px 24px rgba(17,17,17,0.08)`. Kartlarda gölge yok.
- Sayfa en fazla 1440 px genişlikte, 24 px kenar boşluğuyla; 1024 px'e kadar bozulmamalı.
- Hareket: 160–220 ms, `cubic-bezier(0.2, 0.8, 0.2, 1)`, yalnızca opaklık ve transform. `prefers-reduced-motion` açıksa animasyon yok.
- Odak halkası: tüm etkileşimli öğelerde 2 px --text-1, 2 px ofset.

### Bileşenler

Ortak bir `ui/` klasöründe topla ve mevcut bileşenleri bunlara taşı:

- Button (ana: siyah zemin, beyaz metin; ikincil: kenarlıklı; hayalet) ve IconButton
- SegmentedControl (Analiz / Demo) ve Stepper (üst adımlar)
- Card, Divider, Badge (nötr, başarı, uyarı, kırmızı, mavi), Tooltip, Tabs (alt çizgili)
- Chip: İskelet, Olay efektleri gibi aç/kapa düğmeleri
- Dialog, Toast, Skeleton (yükleniyor), EmptyState
- StatPair: ayna karşılaştırma satırı. Solda kırmızı değer ve çubuk, ortada etiket, sağda mavi. Bölüm 5'te çok kullanılacak.
- İkonlar: tek set (Lucide varsa koru), 1.5 px çizgi, 16 ve 20 px.

### Ekranlar

1. Üst bar: beyaz, alt kenarlıklı. Solda tek renk (--text-1) oktagon işareti ve "Fight Analyzer", ortada adımlar (numara ve etiket; aktif adımda siyah alt çizgi), sağda Analiz/Demo seçici ve küçük bir durum noktasıyla "Sistem hazır".
2. Yükleme: ortada 44 px başlık, altında --text-2 açıklama. Sürükle-bırak alanı beyaz, 1.5 px kesikli --border-strong çerçeveli, 16 px yarıçaplı. Sürüklerken çerçeve --text-1, zemin --surface-muted olur. "Dosya seç" ana buton; biçimler ve sınırlar tek satır, --text-3.
3. Geçmiş analizler: küçük 16:9 önizleme, dosya adı, tarih · çözünürlük · süre ve durum rozeti. Hover'da --surface-muted. Sonuç özetini Bölüm 5 ekleyecek.
4. İşlem: aşamalar dikey bir listede (ad, durum ikonu, ilerleme), altında toplam ilerleme, tahmini kalan süre ve "İptal" ikincil butonu.
5. Seçim: dövüşçü adayları büyük karelerle. Seçili aday köşe renginde 2 px çerçeve ve köşe rozeti alır; isimler satır içinde düzenlenir.
6. Sonuç: yalnızca tokenlar ve tipografi. Video sahnesi koyu, paneller beyaz.

### Kabul ölçütleri

- Token dosyası dışında hiçbir bileşende sabit renk kodu kalmadı; aramayla kontrol et.
- Metin kontrastı WCAG AA'yı geçiyor: normal metin 4.5:1, büyük metin 3:1. Token çiftlerini küçük bir testle doğrula.
- Fontlar internet olmadan yükleniyor.
- Tüm akış (yükle, seç, sonuç) klavyeyle yapılabiliyor ve odak her zaman görünüyor.
- Testler ve oxlint geçiyor. Raporda kontrol etmem gereken ekranları ve durumları listele.

## Bölüm 2 — Veri temeli: round'lar, yayın kesmeleri, kimlik takibi

Görev: Puanlamanın dayanacağı zemini kur. Videoyu roundlara böl, replay ve dövüş dışı bölümleri ayıkla, kimlik karışmasını azalt. Bu bölümde puanlama mantığı yazma.

Neden: Örnek videoda (topuria-volkanovski.mp4) iki dövüşçü için 124 ve 87 geçici numara değişimi ve %23–25 örtüşme görünüyor. Vuruşlar yanlış dövüşçüye yazılırsa ya da replay'ler iki kez sayılırsa hiçbir puanlama doğru olamaz.

### 2.1 Maç ayarları

- Yeni sözleşme `BoutConfig`: planlanan round sayısı (3 veya 5), round süresi (300 sn), dinlenme (60 sn), şampiyonluk maçı mı, kural seti (`abc_2025`), kırmızı ve mavi dövüşçü adları.
- Seçim adımına bir "Maç ayarları" kartı ekle: round sayısı, şampiyonluk anahtarı ve bulunan round sınırlarının önizlemesi.
- Scorebug'dan okunabiliyorsa dövüşçü adlarını ve round bilgisini öner; kullanıcı onaylar.

### 2.2 Round tespiti

Üç kaynak var, öncelik sırasıyla. Elle girilen her zaman otomatiği ezer.

1. Scorebug OCR: yayın grafiğindeki round numarasını ve geri sayım saatini oku.
   - ROI'yi otomatik bul: her 2 sn'de bir kare örnekle, alt ve üst bantta `\d:\d\d` desenini ara. Kullanıcı ROI'yi Seçim ekranında bir dikdörtgenle düzeltebilsin.
   - OCR'ı yalnızca ROI'de ve saniyede 1 karede çalıştır. CPU'da hızlı bir yöntem seç (rakam şablonu eşleştirme, RapidOCR/ONNX veya Tesseract) ve seçimini gerekçelendir.
   - Saat 5:00'a dönüp round numarası artıyorsa yeni round başlar. Video ilerlerken saat duruyorsa mola, faul arası, replay ya da round arası vardır.
   - Çıktı: her video zamanı için dövüş saati (round, kalan süre) ve güveni.
2. Round arası tespiti (OCR yoksa): yaklaşık 60 sn'lik etkileşimsiz bölüm, köşelerde oturan dövüşçüler, kafese giren çok sayıda kişi.
3. Elle düzenleme: zaman çizelgesinde round sınırı ekle, sürükle, sil.

`RoundSegment` alanları: index, video\_start\_s, video\_end\_s, clock\_start, clock\_end, source (`ocr` | `break` | `manual`), confidence ve partial (round tamamlanmadan bitti mi).

### 2.3 Yayın kesmeleri ve dövüş dışı bölümler

- Mevcut kamera kesmesi ve optik akış modülünü kullan; eksikse sahne sınırı tespiti ekle.
- Replay tespiti için sinyaller: scorebug kaybolur ya da "REPLAY" benzeri bir ibare çıkar, dövüş saati donar, logo geçişi (wipe) olur, hareket ağır çekim gibi yavaşlar. En az iki sinyal varsa segmenti `replay` olarak işaretle.
- Dövüş dışı bölümler: girişler, tanıtımlar, round araları, maç sonrası.
- Hepsi mevcut "Dışlanan bölümler" listesine nedeniyle ve "otomatik" etiketiyle düşer; kullanıcı tek tıkla geri alabilir. Dışlanan bölümlerdeki olaylar hiçbir metriğe ve puana girmez.

### 2.4 Kimlik takibi

- Seçim adımında her dövüşçü için bir görünüm modeli kur: şort rengi ve deseni (kalça-uyluk bölgesinde HSV histogramı), gövde bölgesi histogramı, boy oranı. Videonun farklı yerlerinden en az 20 kesit kullan.
- Kamera kesmesinden sonra izleri görünüm benzerliği ve konumla yeniden eşle. Kimlik, eşleşme güveni eşiğin üstündeyken kilitli kalır.
- Klinçte ve yerde yoğun örtüşmede kimliği dondur. Ayrıldıklarında görünümle yeniden doğrula; yanlışsa örtüşme boyunca atanan olayların sahibini düzelt.
- Hakemi ve diğer kişileri ayrı sınıfla (hakem genelde tek renk gömlek ve eldivenlidir) ve dövüşçü adaylığından çıkar.
- Her olaya `attribution_confidence` ekle. Eşiğin altındaki olaylar "Kime ait belirsiz" etiketi alır; puanlamadaki ağırlıklarını Bölüm 4 belirler.
- Round bazında kalite özeti çıkar: ölçülebilir süre oranı, kimlik değişimi sayısı, en uzun belirsiz aralık ve güveni düşüren nedenler (eksik görüntü, uzak ya da kötü kamera açısı, örtüşen dövüşçüler, düşük görüntü kalitesi: çözünürlük, bulanıklık, düşük keypoint güveni). Bu metrikler Bölüm 5'te dövüşçü panellerinden "Veri kalitesi" sekmesine taşınacak.

### 2.5 Zaman kapsamı

- Her metrik grubu hangi aralığa ait olduğunu bilsin ve göstersin: tüm maç, seçili round veya oynatma anına kadar.
- Şu an "00:00 – 01:06 arası" başlığı altında 42 sn ölçülebilir ve 59 sn belirsiz süre görünüyor. Kimlik metriklerinin hangi aralıktan hesaplandığını bul ve tutarlı hale getir.

### Kabul ölçütleri

- Örnek videoda round sınırları ±2 sn içinde bulunuyor; OCR çalışmazsa elle düzeltme bir dakikadan kısa sürüyor.
- Replay bölümleri otomatik dışlanıyor ve raporda kaç olayın dışlandığı yazıyor.
- Geçici numara değişimi, örtüşme ve en uzun belirsiz süre için öncesi/sonrası tablosu var.
- OCR saat çözümlemesi ve round sınırı mantığı için örnek kare fixture'larıyla birim testleri var.
- Analiz süresindeki artış ölçülüp raporlanıyor; %30'u aşarsa nedeni ve seçenekler yazıyor.

## Bölüm 3 — Olaylar ve metrikler: isabet, hasar, grappling

Görev: Hakem motorunun ihtiyaç duyduğu olayları ve round bazlı özellikleri üret. Puanlama kurallarını bu bölümde yazma; yalnızca ölç.

Neden: Şu anki paneller çoğunlukla deneme ve hareket ölçüyor. ABC'nin 2025 kriterlerinde ise round, sonucu olan eylemlerle kazanılır: hasar veren vuruşlar ve hasarla üretkenliği kanıtlanan grappling. İlerleme ve baskı yalnızca son çare kriterlerine (saldırganlık, alan kontrolü) girer.

Not: Tek kameradan 2B iskeletle isabet ve hasar tahmini kesin olamaz. Hedef, her sinyali güveniyle birlikte üretmek ve kullanıcının düzeltmesini kolaylaştırmak.

### 3.1 Vuruş olayları

Mevcut yumruk, tekme ve diz tespitini genişlet:

- Tür: punch, elbow, knee, kick, ground\_strike (yerde üstten vuruş).
- Hedef: head, body, leg. Vuran uzvun ucunun rakibin kafa, gövde veya bacak bölgesine en yakın geçtiği noktaya göre belirlenir.
- Sonuç: landed, blocked, missed, unknown. İsabet kanıtı: uzuv ucunun hedef bölgeye teması ve 100–300 ms içinde rakibin kafasında ani ivme (head snap) ya da gövdesinde geri itilme. Temas kolda veya eldivende kalıyorsa blocked.
- Önemli vuruş (significant): mesafede atılan tüm vuruşlar ile klinçte ve yerde atılan güçlü vuruşlar. Klinçte ve yerdeki hafif dokunuşlar önemsiz sayılır.
- Her olayda confidence, attribution\_confidence ve evidence (hangi sinyallerin tetiklediği) alanları olsun.

### 3.2 Hasar sinyalleri

`DamageSignal` alanları: type, time, target\_fighter, severity (0–1), confidence, kind (`immediate` | `cumulative`), linked\_event\_id. Türler ABC'nin hasar tanımını izler:

- knockdown: geçerli bir isabetten sonra rakibin kalçası veya gövdesi zemine iner. Kaymadan (öncesinde isabet yok) ve takedown'dan (grappling teması var) ayır.
- heavy\_head\_strike: kafaya isabette yüksek kafa ivmesi.
- wobble: denge kaybı. Taban genişliğinde ani değişim, düzensiz adımlar, diz bükülmesi, eldivenin zemine değmesi.
- forced\_retreat: isabetten sonra rakip geri çekilir, döner ya da sonraki 2–3 sn boyunca yalnızca savunma yapar.
- output\_drop: ağır isabetlerden sonra rakibin vuruş hızında ve hareketliliğinde round içinde kalıcı düşüş (kümülatif hasar).
- submission\_danger: eklem kilidinin veya boğmanın tutulma süresi ve rakibin kaçış hareketlerindeki azalma (düşük güvenle).
- visible\_injury: otomatik tespit etme. Kullanıcı round kartından "görünür hasar" bayrağı ekleyebilsin.

### 3.3 Grappling durumları

Her kare için bir durum makinesi kur: DISTANCE, CLINCH, GROUND\_RED\_TOP, GROUND\_BLUE\_TOP, SCRAMBLE. Geçişlerden olay üret:

- takedown\_attempt ve takedown\_landed: ayakta durumdan yere geçiş; saldıran üstte ve en az 3 sn kalıcı. Hemen kalkılırsa `brief` olarak işaretle.
- reversal (alttaki üste geçer) ve get\_up (yerden ayağa kalkış).
- submission\_attempt: boyun çevresinde kol, üçgen, kol uzatma gibi konfigürasyonlar. Güven düşükse yine "olası" olarak kaydet.
- Pozisyon (guard, half guard, side, mount, back) yalnızca güvenilir ayırt edilebiliyorsa. Değilse üst/alt ayrımı yeterli.
- control\_time: yerde üstte ve klinçte rakibi kafese yaslayarak geçen süre.
- active\_control\_time: kontrol sırasında vuruş veya submission tehdidinin sürdüğü süre. 2025 kriterlerine göre yalnızca pozisyon tutmak baskınlık sayılmaz; motor bu ayrımı kullanacak.

### 3.4 Baskınlık, süre ve son çare kriterleri

- one\_sided\_time: rakibin açıklık olduğu halde karşılık vermeden yalnızca savunduğu süre.
- offensive\_pace: dakikadaki önemli deneme ve kombinasyon sayısı.
- effective\_time\_share: dövüşçünün etkili teknik dayattığı sürenin round süresine oranı (ABC'deki "süre").
- aggressiveness: istikrarlı ofansif çaba. Deneme sıklığı, kombinasyon başlatma, mesafe kapatıp deneme yapma.
- area\_control: tempoyu, yeri ve pozisyonu kimin belirlediği. Oktagon merkezini tutma, rakibi kafese yaslama süresi, değişimleri kimin başlattığı. Mevcut "Baskı" ve "İlerleme / Geri çekilme" buraya taşınır.

### 3.5 Round özellikleri

`RoundFeatures` dövüşçü başına hesaplanır ve zaman kapsamı parametrelidir (round, tüm maç, oynatma anına kadar):

- Vuruş: önemli isabet ve deneme (kafa, gövde, bacak), toplam isabet ve deneme, isabet oranı, knockdown sayısı.
- Hasar: sinyal listesi, anlık hasar skoru ve ayrı olarak kümülatif hasar skoru.
- Grappling: takedown isabet ve deneme, kontrol süresi, aktif kontrol süresi, tehlike skorlu submission denemeleri, ters çevirme, ayağa kalkma.
- Baskınlık ve süre: one\_sided\_time, offensive\_pace, effective\_time\_share.
- Son çare: aggressiveness ve area\_control skorları.
- Faz dağılımı: mesafe, klinç ve yer süreleri.
- Veri kalitesi: ölçülebilir süre oranı, ortalama olay güveni, belirsiz sahiplik oranı.

### 3.6 Düzeltme katmanı

- Kullanıcı olay listesinden bir olayı silebilir, sahibini değiştirebilir, sonucunu (isabet, blok, ıska) ve hedefini düzeltebilir, eksik olay ekleyebilir.
- Düzeltmeler ayrı tabloda saklanır; ham tespit değişmez.
- Bir düzeltmeden sonra yalnızca etkilenen roundun özellikleri ve puanı yeniden hesaplanır; bu bir saniyeden kısa sürmeli.

### Kabul ölçütleri

- Durum makinesi geçişleri, önemli vuruş sınıflaması ve knockdown / kayma / takedown ayrımı için sentetik keypoint dizileriyle birim testleri var.
- Örnek video için round bazlı bir tablo yazdırılıyor: önemli isabet ve deneme, knockdown, takedown, kontrol süresi. Bölüm 6'da resmi istatistiklerle karşılaştırılacak.
- Sözleşmeler yeniden üretildi ve eski analizler hâlâ açılıyor.
- Analiz süresindeki artış raporlandı.

## Bölüm 4 — Hakem motoru: ABC 2025 kriterleri ve 10 puan sistemi

Görev: Mevcut "Hakem kartları (AI)" modülünü ABC'nin 2025 puanlama kriterlerine göre yükselt. Önce mevcut modülü incele ve aşağıdaki kurallarla farkını madde madde raporla; onayımdan sonra uygula. Sonunda tek bir puanlama sistemi kalmalı.

### 4.0 Önceki hakem prompt'uyla farklar

Mevcut modülü kuran prompt, 2017 metnindeki kriter sırasını izliyordu. Fark raporunda şu dört noktayı özellikle kontrol et ve 2025 kurallarına göre değiştir:

1. Saldırganlık ve alan kontrolü artık sıralı değil. Etkili tekniklerde fark yoksa, roundu hangisi daha çok etkilediyse o belirler (4.2, adım 4). "Etkili agresiflik" adı "Saldırganlık" olur.
2. 10-8 için önemli hasar şart. Hasarsız baskınlık, "üç kriterden ikisi" gibi bir kuralla 10-8'e dönmemeli.
3. 10-10 tamamlanmış rounda verilmez; yalnızca yarım kalan roundlarda verilebilir.
4. Pozisyon geliştirme ve kontrol tek başına puan getirmez; hasar ya da bitirici tehditle birleşince değer kazanır. Rakibin savunma durumu yalnızca ofansın etkisi olarak sayılır, çünkü savunma puanlanmaz.

Önceki prompt'tan aynen korunacaklar:

- Üç bağımsız hakem profili, her birinin kendi skor kartı ve birleşik karar türü.
- Round çıktıları: iki köşenin puanı, kazanan, gerekçe, en etkili saldırılar, hasar üstünlüğü, güreş ve yer oyunu üstünlüğü, güven seviyesi.
- Maç sonunda round skorları, toplamlar, üç hakem kartı, kazanan, karar türü, kazanma gerekçesi ve güven.
- Bitişlerin puan kararından ayrı tutulması ve "AI tahmini" etiketi.
- Round kazananının yalnızca deneme veya aktivite sayısıyla belirlenmemesi.
- Momentumun puanlamadan ayrı kalması.

### 4.1 Kural özeti (ABC, Temmuz 2025)

- En az üç hakem vardır; her round ayrı puanlanır ve daha etkili dövüşçü kazanır.
- Üç kavram önem sırasıyla: hasar, baskınlık, süre. Hasar en değerli bileşendir; round içinde anlık hasar kümülatif hasardan önce gelir.
- Hasar: rakibin dövüşme kapasitesini veya isteğini azaltan geçerli tekniklerin sonucu. Knockdown, hayati bölgelere ağır vuruşlar, rakibi geri çekilmeye ya da yalnızca savunmaya zorlayan vuruşlar, görünür yaralanma, eklemi zorlayan submission denemeleri ve görünür sıkıntı yaratan boğmalar.
- Baskınlık: pozisyon, eylem veya hacimde sürekli üstünlük. Yalnızca dominant pozisyonu tutmak baskınlık sayılmaz.
- Süre: dövüşçünün etkili tekniği dayattığı zamanın round içindeki payı.
- Ana kriter etkili dövüş teknikleridir: başarılı vuruş (hasarla sonuçlanan geçerli vuruşlar) ve başarılı grappling (takedown, ters çevirme, submission denemesi ve avantajlı pozisyonla gelen hasar). İkisi eşit ağırlıktadır.
- Hakem ikisinde de en küçük bir avantaj göremezse saldırganlığa (istikrarlı ofansif çaba) veya alan kontrolüne (tempo, yer ve pozisyonu belirleme) bakar; hangisi roundu daha çok etkilediyse. Aralarında sıra yoktur.
- Savunma puanlanmaz.
- 10-10: hiçbir taraf avantaj kuramadıysa. Genelde yarım kalan roundlar içindir; tamamlanmış bir rounda 10-10 vermek puanlayamama sayılır.
- 10-9: daha üstün ofansif eylemler.
- 10-8: önemli hasar şarttır. Önemli hasar tek başına yeter. Ciddi baskınlık, bir miktar hasar ve kaybedenin neredeyse hiç ofansif eylemi olmaması yetebilir. Hasarsız pozisyonel üstünlük yetmez. Kümülatif hasar (enerji, özgüven, dayanıklılık kaybı) önemli hasar sayılabilir.
- 10-7: round boyunca hem hasarda hem baskınlıkta ezici üstünlük.
- Ring hakeminin puan kesintileri hakem kartlarından o roundda düşülür. Teknik kararda yarım kalan round da puanlanır.

### 4.2 Round puanlama algoritması

Her sanal hakem her round için şu adımları uygular:

1. Uygunluk: round dışlanmamış olmalı ve ölçülebilir süresi config'teki eşiği (ör. %50) geçmeli. Geçmiyorsa yine en olası skor üretilir, ama `insufficient_data` bayrağı ve düşük güven gösterilir. Round kayıtta hiç yoksa "puanlanamadı" olur.
2. Etkinlik skoru, her dövüşçü için: `E = w1·D_imm + w2·D_cum + w3·Dom`.
   - D\_imm, anlık hasar: knockdown, wobble, ağır kafa vuruşu, zorunlu geri çekilme (forced\_retreat), submission tehlikesi; şiddet × güven toplamı.
   - D\_cum, kümülatif hasar: isabetli önemli vuruşlar azalan getiriyle (ör. karekök ölçek), çıktı düşüşü ve kullanıcının eklediği görünür hasar bayrağı.
   - Dom, baskınlık × süre: aktif kontrol, one\_sided\_time ve ezici tempo (offensive\_pace); effective\_time\_share ile ölçeklenir. Hasar üretmeyen pozisyon tutma çok düşük ağırlık alır.
   - Vuruş ve grappling aynı ölçekte toplanır, ayrı ağırlıkları yoktur. Başlangıç değerleri w1 = 1.0, w2 = 0.6, w3 = 0.35 ve daima w1 > w2 > w3. Bölüm 6'da kalibre edilecek.
   - Olaylar `attribution_confidence` ile ağırlıklandırılır.
3. Kazanan: `margin = (E_red − E_blue) / max(E_red + E_blue, ε)`. |margin| ≥ τ\_marginal (ör. 0.03) ise kazanan E'ye göre belirlenir ve `decided_by = effective_techniques` olur.
4. Etkili tekniklerde fark yoksa saldırganlık ve alan kontrolü farklarını normalize et. Mutlak değeri büyük olan kriter kazananı belirler (`decided_by` = `aggressiveness` veya `area_control`).
5. O da yoksa tamamlanmış roundda 10-10 verilmez. Küçük de olsa farkı olan ilk değere göre karar verilir: önce E, sonra saldırganlık ve alan kontrolünden büyük olanı, en son isabetli önemli vuruş sayısı. Round "çok yakın" olarak, yaklaşık %50 güvenle işaretlenir. Yarım roundda 10-10 verilebilir.
6. Fark büyüklüğü:
   - Önemli hasar: knockdown varsa ya da D\_imm veya D\_cum config eşiğini geçiyorsa.
   - 10-8 iki yoldan biriyle verilir: (a) kazananın önemli hasarı var; (b) ciddi baskınlık (Dom ve effective\_time\_share yüksek), bir miktar hasar ve kaybedenin ofansif çıktısı çok düşük. Hasar yoksa 10-8 asla verilmez.
   - 10-7: hasar ve baskınlık ezici, effective\_time\_share en az %70 (eşikler config'te). Çok nadir olmalı.
7. Puan kesintisi: o roundda cezalı dövüşçünün skorundan düşülür. Kazanana 1 puanlık kesinti 10-9'u 9-9 yapar; kaybedene kesinti 10-8 yapar.
8. Gerekçe: her round ve hakem için 2–4 gerekçe üret. Hangi kriterin karar verdiği, ilgili sayılar ve zaman damgalı kanıt olayları. Şablon örneği: "Hasar: Kırmızı 2 ağır kafa vuruşu ve 1 sarsılma (01:42, 02:10); Mavi'de anlık hasar yok."

### 4.3 Üç sanal hakem

Gerçek panellerdeki görüş farkını modellemek için aynı kurallar farklı ağırlık profilleriyle çalışır:

| Hakem | Profil | Ağırlık değişimi |
| --- | --- | --- |
| A | Kural metni | Başlangıç ağırlıkları |
| B | Hasar odaklı | w1 +%20, w2 −%10 |
| C | Hacim ve kontrol | w1 −%10, w2 +%15, w3 +%15 |

Profiller config'te durur. Mevcut modülde hakem profilleri varsa yeni bir set ekleme; onları bu üç profile dönüştür. Her profil w1 > w2 > w3 sırasını ve 10-8 kurallarını korur.

### 4.4 Belirsizlik

- Güveni Monte Carlo ile hesapla: 300 örnek, sabit seed. Her örnekte olaylar kendi güven olasılığıyla dahil edilir, sahiplik `attribution_confidence` olasılığıyla korunur ya da karşı tarafa geçer, hasar şiddeti güven aralığında örneklenir.
- Çıktı: round başına P(kırmızı kazanır) ve P(10-8 veya üstü), ayrıca maç sonucu olasılıkları.
- Kartlardaki skor, deterministik nokta tahminidir. Olasılık yalnızca güven olarak gösterilir.

### 4.5 Maç sonucu

- Bitiş türleri: KO, TKO (hakem, doktor veya köşe durdurması) ve submission. Otomatik tespit sinyalleri: knockdown ve ardından takip vuruşları, hakemin araya girmesi, sonraki 20 sn'de dövüşün sürmemesi, kutlama. Submission için tekrarlı el veya ayak vurma (tap); güven düşükse "olası".
- Bitiş tespit edilince kullanıcıya her zaman sor: "Bitiş tespit edildi: R2 3:32, KO/TKO. Onayla / Düzelt". Yayının sonuç grafiği OCR ile okunabiliyorsa öneri olarak kullan.
- Bitiş zamanı scorebug saatinden (round ve geçen süre) türetilir; saat yoksa round başlangıcından itibaren video süresi kullanılır.
- Bitiş yoksa ve planlanan roundlar tamamlandıysa karar verilir. Her hakemin toplamı o hakemin kazananını ya da beraberliğini belirler:
  - 3-0 oybirliği kararı, 2-1 bölünmüş karar; iki hakem aynı dövüşçü ve bir beraberlik oy çokluğu kararı.
  - Üç beraberlik oybirliğiyle beraberlik, iki beraberlik oy çokluğuyla beraberlik, 1-1-1 bölünmüş beraberlik.
- Kayıt planlanan mesafeden önce bitiyor ve bitiş yoksa resmi kazanan gösterme. "Kayıt tamamlanmadı — R2 sonunda kartlarda önde: X" yaz.
- Faul kaynaklı sonuçlar (diskalifiye, sonuçsuz, teknik karar) yalnızca kullanıcının girdiği hakem kararıyla uygulanır; motor tahmin etmez. Kasıtsız faulle durdurmada roundların çoğunluğu tamamlandıysa teknik karar verilir ve yarım round da puanlanır; tamamlanmadıysa sonuçsuz olur. Eşik komisyona göre değişebildiği için config'te dursun (varsayılan: 3 roundluk maçta 2, 5 roundlukta 3 tamamlanmış round).

### 4.6 Çıktı sözleşmesi

`JudgingResult` (Pydantic):

- Üst bilgi: schema\_version, ruleset, engine\_version, weights\_version, seed.
- rounds\[\]: index, status (`complete` | `partial` | `excluded` | `no_data`), phase\_split, decided\_by, margin, dövüşçü başına significant\_damage ve dominance\_level, effective\_time\_share, damage\_edge ve grappling\_edge (üstün taraf ve farkın gücü), top\_attacks (en etkili 3–5 saldırının olay kimlikleri), judges\[\] (judge\_id, red, blue, reasons\[\]), deductions\[\], confidence (p\_red, p\_ten\_eight), data\_quality.
- outcome: type (`finish` | `decision` | `technical_decision` | `no_contest` | `dq` | `incomplete`), winner (`red` | `blue` | null), method, round, time, judge\_totals\[\], decision\_type, summary\_reasons\[\] (kazananın neden kazandığı), confidence, user\_confirmed.
- Reason: code (enum), params (sayılar), evidence\_event\_ids. Metni arayüz şablondan üretir.

### 4.7 Testler

pytest ile tablo bazlı:

- Belirgin vuruş üstünlüğü, hasar sinyali yok: üç hakemde 10-9.
- Knockdown ve belirgin hasar: 10-8.
- Uzun üst kontrol, hasar yok, rakip ofansif değil: 10-9, asla 10-8.
- Ciddi baskınlık, bir miktar hasar, kaybeden neredeyse hiç ofansif değil: 10-8.
- Ezici hasar ve baskınlık, effective\_time\_share %70 üstü: 10-7.
- Etkili tekniklerde fark yok ve saldırganlık farkı alan kontrolü farkından büyük: saldırganlık belirler. Tersi durumda alan kontrolü belirler.
- Tamamlanmış round, her şey eşit: 10-10 verilmez, düşük güvenli eşitlik bozma uygulanır.
- Yarım round, kimse avantaj kurmamış: 10-10.
- Kazanana kesinti 9-9, kaybedene kesinti 10-8.
- Karar türleri: 29-28 ×3 oybirliği; 29-28, 29-28, 28-29 bölünmüş; 29-28, 29-28, 28-28 oy çokluğu; 28-28, 28-28, 29-28 oy çokluğuyla beraberlik; 29-28, 28-29, 28-28 bölünmüş beraberlik.
- Onaylı bitiş kartlardan önce gelir. Eksik kayıtta resmi kazanan yoktur.
- Aynı girdi ve seed ile Monte Carlo aynı sonucu verir. Momentum değerleri değişse de skorlar değişmez.

### Kabul ölçütleri

- Eski modülle yeni kurallar arasındaki fark raporu teslim edildi ve onaylandı.
- Tüm testler geçiyor; eski "AI tahmini" kartları yeni motorla yeniden üretiliyor.
- Örnek videoda round skorları, gerekçeler ve bitiş önerisi JSON dışa aktarmada görünüyor.

## Bölüm 5 — Sonuç deneyimi: skor kartları ve karar ekranı

Görev: Sonuç ekranını hakem motorunun çıktısı etrafında, Bölüm 1'in tasarım sistemiyle yeniden kur. Kayıt bittiğinde ya da onaylı bitiş anına gelindiğinde kazanan açıkça gösterilsin.

### 5.1 Yerleşim

1280 px ve üstü için:

- Üstte skor şeridi: solda kırmızı köşe adı, sağda mavi, ortada round sütunları (R1, R2, R3…). Her hücrede üç hakemin skoru küçük yazılır; round kazananı köşe renginde bir noktayla gösterilir. En sağda hakem toplamları durur.
- Sonuç açıklandıysa şeridin altında karar satırı çıkar: "Ilia Topuria kazandı · KO/TKO · R2 3:32" ya da "Kırmızı kazandı · Bölünmüş karar · 29-28, 28-29, 29-28".
- Ortada koyu video sahnesi, sağında 360 px genişliğinde "Round kartı" paneli.
- Videonun altında zaman çizelgesi: R1, R2 etiketli round ayırıcıları, taralı dışlanan bölümler, olay işaretleri ve altta mevcut deneysel momentum eğrisi.
- En altta sekmeler: Özet · Hakem kartları (AI) · İstatistikler · Olaylar ve momentum · Veri kalitesi · Dışa aktar. Mevcut sekme adları korunur; "Kimlik takibi" sekmesi "Veri kalitesi" olur.
- Sol ve sağdaki dövüşçü panelleri kalkar. Yerlerine İstatistikler sekmesinde StatPair ayna karşılaştırmaları gelir; zaman kapsamı seçicisi: Tüm maç, R1, R2…, Oynatma anına kadar.

### 5.2 Round kartı (oynatmayla canlı)

- Oynatılan round ve kalan süre (scorebug saatinden).
- "Şu an önde: X" ve olasılığı.
- Hasar, baskınlık ve süre için iki taraflı üç ince çubuk; 10-8 eşiği çubukta işaretli.
- Round bitince üç hakemin skoru belirir (ör. 10-9 · 10-9 · 10-8) ve kararı veren kriter yazılır.
- "Neden?" bağlantısı gerekçeleri açar. Bir kanıta tıklanınca video o saniyeye gider.

### 5.3 Sonucu gizle

- Varsayılan olarak açık. Açıkken skor şeridi yalnızca oynatmanın geçtiği roundları doldurur; diğer hücreler boş kalır.
- Kapalıyken her şey baştan görünür. "Sonucu göster" butonu her zaman erişilebilir.
- Tercih analiz başına hatırlanır.
- Açıkken sonuç hiçbir yerden sızmaz: sekmeler, geçmiş analizler listesi, sayfa başlığı, dışa aktarma önizlemeleri.

### 5.4 Karar ekranı

- Video bittiğinde ya da onaylı bitiş anına gelindiğinde video üstünde, ortada beyaz bir kart açılır.
- Kartta: kazananın köşe renginde ince üst çizgi, "KAZANAN" etiketi, dövüşçü adı (Inter Tight 32–44 px), yöntem ve zaman, üç hakem kartı (ör. 29-28 · 29-28 · 28-29) ya da bitiş bilgisi, 2–3 cümlelik "Neden kazandı?" özeti (summary\_reasons alanından şablonla üretilir), tahmin güveni (ör. "Yüksek · %82") ve "AI tahmini — resmi sonuç değildir" notu.
- Butonlar: "Kartları incele", "Tekrar izle", "Dışa aktar".
- Animasyon: 200 ms opaklık ve hafif ölçek, skorlar sayarak gelir. Azaltılmış hareket tercihinde animasyon yok.
- Beraberlik ve sonuçsuz için nötr renkli kart. Eksik kayıtta "Kayıt tamamlanmadı — R2 sonunda kartlarda önde: X" yazar ve kazanan rozeti çıkmaz.

### 5.5 Hakem kartları (AI) sekmesi

Her round için bir bölüm:

- Faz dağılımı çubuğu: mesafe, klinç, yer.
- Ayna istatistikler: önemli isabet ve deneme, kafa / gövde / bacak, knockdown, takedown, kontrol ve aktif kontrol, submission denemesi.
- Kararı veren kriter, üç hakemin skoru ve gerekçeleri. Hasar üstünlüğü ile güreş ve yer oyunu üstünlüğü ayrı satırlarda, üstün taraf ve farkın gücüyle.
- Önemli anlar: en etkili 3–5 olay, küçük kare görüntüsüyle; tıklayınca videoya gider.
- Veri kalitesi rozeti (İyi / Orta / Düşük) ve düşükse nedeni (eksik görüntü, kamera açısı, örtüşme, düşük görüntü kalitesi), ör. "Roundun %40'ı ölçülemedi".

### 5.6 Kullanıcı kartı, resmi sonuç, kesintiler

- Kendi kartın: kullanıcı her roundu 10-10, 10-9, 10-8 veya 10-7 olarak puanlar. AI hakemlerle yan yana gösterilir; farklı roundlar vurgulanır.
- Resmi sonuç: yöntem, round, zaman ve isteğe bağlı üç resmi hakem kartı girilebilir. Girildiyse AI ile uyum özeti görünür; Bölüm 6 bu verileri toplar.
- Puan kesintisi ve faul kararları round kartındaki "Kesinti ekle" ile girilir (dövüşçü, round, puan, not). Görünür hasar bayrağı da buradan eklenir.

### 5.7 Mevcut öğelerin dönüşümü

- Momentum sistemi formülüyle aynen korunur ve puanlamaya girmez. Üstte skor şeridi olacağı için momentum çubuğu, kazanma olasılığı gibi okunmasın diye "Olaylar ve momentum" sekmesine taşınır; eğri zaman çizelgesinde kalır. "Deneysel — kazanma olasılığı değildir" etiketi iki yerde de görünür.
- "Aktivite /100" kalkar ya da "dakikada önemli deneme" olur.
- Kimlik takibi metrikleri "Veri kalitesi" sekmesine taşınır.
- Olay listesine sonuç (isabet, blok, ıska), hedef bölge ve düzeltme menüsü eklenir.
- Geçmiş analizlerde her satır sonuç özetini gösterir: köşe renginde kazanan ve yöntem. "Sonucu gizle" açıksa "Sonuç gizli" yazar.

### 5.8 Dışa aktarma

- Skor kartı PNG ve PDF: aydınlık ve baskıya uygun. Dövüşçüler, round skorları, hakem toplamları, sonuç ve "AI tahmini" notu.
- JSON: JudgingResult'ın tamamı. CSV: round bazlı istatistikler.
- MP4 dışa aktarmaya isteğe bağlı skor şeridi katmanı.

### Kabul ölçütleri

- Örnek videoda kayıt sonunda karar kartı açılıyor; R2'deki bitiş tespit ediliyor ya da onay akışıyla girilebiliyor.
- "Sonucu gizle" açıkken sonuç hiçbir yerden sızmıyor.
- Klavye: boşluk oynat/durdur, sol ve sağ ok 5 sn, Esc karar kartını kapatır.
- Tüm bileşenler token kullanıyor; 1280 ve 1024 px genişlikte düzen bozulmuyor.
- Mevcut dışa aktarmalar çalışmaya devam ediyor.

## Bölüm 6 — Doğrulama ve kalibrasyon

Görev: Hakem motorunun ne kadar doğru olduğunu gerçek maçlarla ölç ve ağırlıkları kalibre et. Sonuçları README'de dürüstçe raporla.

### 6.1 Referans veri seti

- `calibration/` klasöründe her maç için bir JSON tut: video dosya adı, resmi sonuç (yöntem, round, zaman), varsa round bazında resmi hakem kartları ve round bazlı resmi istatistikler (önemli isabet ve deneme, knockdown, takedown, kontrol süresi).
- Videolar repoya girmez; `.gitignore`'a ekle.
- Veri elle girilir ya da JSON olarak içe aktarılır. Uygulama çevrimdışı kalır, scraping yapma. Kaynak örnekleri: round bazlı istatistik için UFCStats, resmi hakem kartları için MMADecisions.
- Hedef en az 10 maç ve karışık profil: vuruş ağırlıklı, grappling ağırlıklı, yakın kararlar ve bitişler. Topuria–Volkanovski (UFC 298, R2 KO) bitiş testi olarak girer.

### 6.2 Ölçümler

Tek komutla çalışan bir değerlendirme scripti (ör. `python -m fight_analyzer.eval`) şunları ölçer:

- Algılama: round başına önemli isabette ortalama mutlak hata ve korelasyon; knockdown ve takedown için precision ve recall; kontrol süresi hatası.
- Puanlama: AI hakem çoğunluğunun round kazananıyla resmi hakem çoğunluğunun uyum oranı; 10-8 precision ve recall; maç sonucu ve karar türü doğruluğu.
- Kalibrasyon: "%70 güven" denen roundların gerçekten yaklaşık %70'inde doğru çıkıp çıkmadığı (güvenilirlik tablosu).
- Çıktı: Markdown rapor ve JSON.

### 6.3 Ağırlık ayarı

- Ağırlıklar ve eşikler sürümlü bir dosyada durur, ör. `judging/weights/abc_2025_v2.json`.
- Ayarı maç bazında dışarıda bırakarak yap (leave-one-fight-out). Basit ızgara arama yeterli.
- Kısıtlar korunur: w1 > w2 > w3 sırası ve 10-8 kuralları değişmez; yalnızca sayısal ağırlıklar ve eşikler aranır.
- Yeni ağırlıkları yalnızca doğrulamada eskisinden iyiyse kaydet ve farkı raporla. Az veriyle aşırı uyuma dikkat et.

### 6.4 Regresyon testleri

- Her kalibrasyon maçının `RoundFeatures` çıktısını fixture olarak kaydet.
- Golden testler, motor değişikliklerinde skorların beklenmedik biçimde değişmesini yakalasın.

### 6.5 README ve model kartı

- "Nasıl puanlar?" bölümü: kural kaynağı (ABC 2025), algoritmanın özeti ve üç hakem profili.
- Doğruluk tablosu: 6.2'nin son sonuçları, kaç maçla ölçüldüğüyle birlikte.
- Bilinen sınırlamalar: tek kamera, yerde örtüşme, yayın grafiği olmayan amatör kayıtlar, görünür yaranın otomatik tespit edilmemesi ve sonucun resmi olmaması.

### Kabul ölçütleri

- `eval` komutu tek seferde çalışıp raporu üretiyor.
- Rapor ve doğruluk tablosu README'de.
- Golden testler yerel test komutuna dahil.

## Kaynaklar

- [ABC — MMA Bout Scoring, Judging Criteria Clarification (Temmuz 2025)](https://www.abcboxing.com/wp-content/uploads/2025/08/ABC-MMA-Scoring-Criteira-Clarification-7.2025.pdf): hasar, baskınlık ve süre tanımları; 10-10, 10-9, 10-8 ve 10-7 ölçütleri; puan kesintisi ve teknik kararda yarım roundun puanlanması.
- [Combat Sports Law — Damage! Brand New MMA Judging Criteria Approved (6 Ağustos 2025)](https://combatsportslaw.com/2025/08/06/damage-brand-new-mma-judging-criteria-approved/): kriterlerin ABC'nin 37. konferansında onaylandığı, 10-8 için hasarın zorunlu olduğu ve saldırganlık ile alan kontrolü arasındaki sıranın kalktığı.

ABC metni bir model kuraldır; her atletik komisyon kendi yetki alanında ayrıca kabul eder. Eşiklerin config'te tutulmasının nedeni bu.
