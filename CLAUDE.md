# Fight Analyzer v2

## Hedef

Fight Analyzer kayıtlı MMA videolarını tamamen yerelde analiz eder. v2 hedefi: roundları ABC kurallarına göre puanlayan bir hakem motoru, kayıt bitince kazananı açıklayan bir karar ekranı ve aydınlık, minimalist bir arayüz.

## Puanlama ilkeleri

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

## Çalışma düzeni

- v2 görevlerinde önce ilgili kodu oku, mevcut yapıyı kısaca özetle ve bir uygulama planı çıkar. Onayımı almadan kod yazma.
- Mevcut özellikleri bozma: yükleme, iş kuyruğu, seçim, overlay oynatıcı, zaman çizelgesi, olay listesi, dışlanan bölümler, MP4/CSV/JSON dışa aktarma, geçmiş analizler, Demo modu.
- Veri sözleşmeleri Pydantic modellerinde tanımlanır. JSON Schema ve TypeScript tipleri mevcut üretim akışıyla yeniden üretilir; elle TS tipi yazma.
- Analiz şeması değişirse sürümünü artır. Eski analizler açılabilir kalsın; gerekiyorsa "Bu analiz eski sürümle yapıldı — yeniden işle" uyarısı göster.
- Ağır işler (OCR, tespit, özellik çıkarımı) worker'da çalışır. Puanlama motoru, önbellekteki round özelliklerinden bir saniyenin altında hesaplanabildiği sürece API'de istek anında çalışabilir. Sonuç girdilerine göre (özellik sürümü, düzeltmeler, ağırlık sürümü, seed) önbelleğe alınır. Yeni bağımlılıklar CPU'da ve çevrimdışı çalışmalı; eklemeden önce gerekçesini yaz.
- Kod tanımlayıcıları İngilizce. Arayüz metinleri Türkçe ve tek bir metin dosyasında toplanır. `<html lang="tr">` korunur, böylece büyük harfte İ ve I doğru çıkar.
- Yeni arayüz iki temada da kontrol edilir ve yalnızca anlamsal tokenlar kullanır. Skor kartı PNG/PDF dışa aktarımı her zaman açık temada üretilir.
- Bitirmeden önce pytest, node --test ve oxlint çalıştır. Hepsi geçmeden "bitti" deme.
- Teslim raporu: değişen dosyalar, nasıl test edildiği, bilinen sınırlamalar, açık sorular.

## Terimler

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
| Raunt (R1, R2…) | round |

## Mevcut kodla bağlantı

- Öncelik: Bu dosya NOTES.md (oradaki "Değişmeyen kurallar" dahil), README.md ya da docs/KULLANIM.md ile çelişirse bu dosya geçerlidir; ör. Aşama 9'daki katı kriter sırası artık geçerli değil. Çelişmeyen "Değişmeyen kurallar" aynen geçerlidir. O belgeler ilgili v2 bölümü uygulanırken güncellenir.
- Köşeler: `FighterId.fighter_a` kırmızı, `fighter_b` mavi köşedir; bu eşleme sabittir (`backend/fight_analyzer/jobs/store.py` → `_fighters`, `backend/fight_analyzer/export/frames.py` → `FIGHTER`). Kimin hangi köşede olduğu, seçim çapalarındaki `red_detection_id` / `blue_detection_id` ile `names.red` / `names.blue` alanlarından okunur. "Tarafları değiştir" (`POST /jobs/{id}/swap`) bu alanları takas edip kimlik, olay ve momentum sonuçlarını yeniden üretir; eşlemeyi değiştirmez. Kişiye ait kullanıcı girdileri (kazanan, kesinti, sahiplik düzeltmesi) taraf değiştirilince kişiyle birlikte taşınır. Takas `backend/fight_analyzer/jobs/store.py` → `swap_corners` içinde `swap_fighter_ids` ile yapılır; kişiye ait yeni bir girdi eklenince oraya da eklenir. Kimlik değerleri eski analizlerde ve önbelleklerde kayıtlı olduğu için yeniden adlandırılmaz; köşeye göre adlandırılan yeni alanlar `red` / `blue` kullanır.
- Tema: Açık · Koyu · Sistem (`frontend/src/app/theme.ts`, ilk boyamadan önce `frontend/index.html` içindeki betik). Renk rolleri `frontend/src/styles/tokens.css` başındaki yorumda: beyaz yazılı dolgu (`--red`, `--blue`, `--warning-fill`…), sayfadaki yazı ve işaret (`--red-fg`, `--blue-fg`, `--warning`…), koyu yüzeydeki işaret (`--red-on-ink`, `--blue-on-ink`), nötr dolgu (`--primary` / `--on-primary`). Video sahnesi ve overlay renkleri iki temada aynıdır.
- Arayüz metinleri: `frontend/src/labels.ts`. Yeni ya da değişen metin oraya yazılır; bileşenlerdeki mevcut metinler o bileşene dokunuldukça taşınır.
- Raunt: Arayüzde TDK yazımı "Raunt" kullanılır; çekimli halleri raundu, raunda, raundun (ünsüzle başlayan eklerde t kalır: rauntlar, rauntta). R1, R2 kısaltmaları aynı kalır, kodda `round`. docs/v2-plan.md'deki arayüz metinlerinde geçen "round" da arayüzde "raunt" yazılır. Mevcut "Raund" yazıları ekranlar yenilenirken değişir.
- Puanlama yeri: Hakem kartları bugün API'de, `GET /jobs/{id}/scorecards` isteğinde önbellekteki analizden (olaylar, sinyaller, kimlik durumu) hesaplanıyor. Round özellikleri henüz yok, sonuç önbelleğe alınmıyor ve hesaplama süresi ölçülmedi. Önbellek girdileri (özellik sürümü, düzeltmeler, ağırlık sürümü, seed) Bölüm 3 ve 4'te geliyor; sonuç önbelleği de onlarla eklenir. Raunt sınırları ve raunt sayısı `Job.rounds` ile `Job.bout`'tan gelir (elle > scorebug saati > raunt arası; birleştirme tek yerde: `backend/fight_analyzer/rounds.py`); dışa aktarma da aynı kurulumu kullanır.
- Dışlanan bölümler: Etkin liste = kullanıcının bölümleri (`Job.exclusions`) + geri alınmamış otomatik bölümler (`Job.auto_exclusions`); birleştirme tek yerde: `backend/fight_analyzer/nonfight.py` (rauntlardan giriş / raunt arası / maç sonrası; yayın sinyallerinden tekrar ve duraklama: `backend/fight_analyzer/broadcast/replay.py`). İstatistik, kartlar, momentum ve dışa aktarma aynı listeyi `ScoringSummary.exclusions`'tan okur. Listeyi değiştirebilen her API ucu (raunt, maç ayarı, bitiş, elle bölüm dışlama, otomatik bölümü geri alma) `api/routes/jobs.py` → `_refresh_momentum` çağırır; yeni bir uç eklenince o da çağırır. Geri alınanlar `params.dismissed_auto`'da kare aralığı olarak durur; kişiye ait değildir, taraf değiştirmede dokunulmaz.
- Kontroller: `check.cmd` hepsini çalıştırır: pytest, şema ve TS tipi güncelliği, tsc, oxlint, node --test, derleme.
- Sözleşme değişince: `backend` içinde `python -m fight_analyzer.contracts.export`, ardından `frontend` içinde `npm run gen:types`. Şema sürümü: `backend/fight_analyzer/contracts/common.py` → `SCHEMA_VERSION`.
- Önbellek sürümleri: Kimlik, kamera, olay, momentum ya da yayın (scorebug saati, raunt tespiti) mantığı değişince ilgili sabiti artır (`IDENTITY_VERSION`, `CAMERA_VERSION`, `EVENTS_VERSION`, `MOMENTUM_VERSION`, `BROADCAST_VERSION`); yoksa eski sonuçlar önbellekten gelir. Kimlik ayarları `TrackingSettings`'e eklenmez: oradaki her alan takip hazırlığı anahtarına girer ve ~12 dk'lık hazırlığı yeniden çalıştırır; yeri `IdentitySettings`'tir (yalnızca kimlik anahtarına girer). `KEY_SCHEMA = "1.2.0"` sabit kalır; değişirse saatler süren poz çıkarımı baştan yapılır. Kare istatistiği formülü değişince `backend` içinde `python -m tests.support.frame_fixture`, veri kalitesi özeti değişince `python -m tests.support.quality_fixture` çalıştır.
- Zaman kapsamı ve veri kalitesi: yan panellerin kapsamı (Şu ana kadar · Raunt · Tüm maç) tek yerde kareye çevrilir: `frontend/src/model/scope.ts` → `scopeRange`; yeni bir metrik grubu aralığı oradan alır. Veri kalitesi özeti arka uçta `backend/fight_analyzer/tracking/quality.py` → `summarize`, tarayıcıda `frontend/src/model/quality.ts`; ikisi `shared/fixtures/track-quality.json` ile denetlenir. "Kime ait belirsiz" olaylar (`FightEvent.attribution_uncertain`) momentuma girmez; puanlamadaki ağırlıklarını Bölüm 4 belirler.
- Planın tamamı: `docs/v2-plan.md`.
