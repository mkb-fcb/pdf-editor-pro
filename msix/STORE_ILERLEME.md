# Microsoft Store Gönderimi — İlerleme Günlüğü

Son güncelleme: 2026-10-09 (ara verildi)

## Ürün
- Partner Center ürünü: **PDF Editor Pro - MKBSoft** (MSIX), Store ID **9PJJ019JKTP9**
  https://partner.microsoft.com/dashboard/products/9PJJ019JKTP9/overview
- Kimlik: Name `MKBSoft.PDFEditorPro-MKBSoft`, Publisher `CN=DD0C354B-7BDC-4028-90B6-AFBA79355DDA`, PublisherDisplayName `MKBSoft`
- Yüklenecek paket: `installer_output\PDFEditorPro_Store_v1.0.2.msix` (v1.0.2.0, x64)
- Metinler: `msix\store_metinleri.txt`
- Sertifikasyon test lisansı: `BILIR-G5SP-XCRG-KDKM` (Cloudflare KV, corporate, 10 makine, 1'i test aktivasyonunda kullanıldı)

## Partner Center adımları
- [x] 1. Pricing and availability — Free, tüm pazarlar, public
- [x] 2. Properties — Productivity; privacy URL; "purchases outside Store commerce" işaretli; Display mode PC işareti kaldırıldı; Memory 4 GB
- [x] 3. Age ratings — IARC anketi; "purchase digital goods" = Yes, loot box = No
- [x] 4. Packages — MSIX v1.0.2.0 x64 yüklendi (2026-10-14), Desktop işaretli; runFullTrust uyarısı normal
- [ ] 5. **Store listings**  ← KALINAN YER (2026-10-14)
  - [~] English (United States) — hemen hemen bitti; Save edilip "Complete" durumu kontrol edilecek
  - [ ] Turkish (Türkiye) — store_metinleri.txt "3) TÜRKÇE" bölümü, görseller İngilizceyle aynı
  - Görseller: images\screenshot_01..04 (1366x768), store_logo_1080x1080, store_logo_300x300, store_poster_720x1080 — English (United States) + Türkçe (metinler store_metinleri.txt)
- [ ] 6. Submission options — Notes for certification (runFullTrust gerekçesi + test lisansı)
- [ ] 7. Submit for certification

## Sonra yapılacaklar
- Web sitesini (`website/`) yeniden yayınla (softwareVersion 1.0.2 sadece lokalde).
- MSIX onaylanınca eski reddedilen "PDF Editor Pro - MKBSoftware" (EXE, e911bd33-…) kaydını sil.
- Store onayı sonrası istenirse test lisansını iptal et (worker `/admin/revoke`).

## Tamamlananlar (2026-10-09)
- Şekil çizme modundan çıkamama hatası düzeltildi (Esc + Şekil Çiz butonu).
- Tam sürüme demo modu eklendi (lisanssız: 3 sayfa, filigran, bazı özellikler kapalı, "Lisans Gir" butonu).
- v1.0.2 GitHub'da yayınlandı (demo + kurulum), pad.xml güncellendi.
- Gumroad dosyaları kullanıcı tarafından v1.0.2 ile değiştirildi.
- MSIX derleme: `python build_msix.py <sürüm> <makeappx yolu>` (Windows SDK veya NuGet Microsoft.Windows.SDK.BuildTools gerekir).

## 2026-10-18 (son durum)
- v1.0.3 paketi yuklendi, TR + EN listeler tamam (4 gercek ekran goruntusu), Submission Options + sertifikasyon notlari + runFullTrust gerekcesi kaydedildi.
- Tum bolumler Complete. Kalan: "Submit for certification" butonuna kullanici basacak.

## 2026-10-23
- v1.0.3 Store'da YAYINDA (ücretsiz + demo; lisans Gumroad'dan). Temiz kurulumda demo modu doğrulandı.
- v1.0.4 derlendi (yeniden, 17:37): kalite seçenekli sıkıştırma + paylaşım seçenekleri, sekmeli şerit arayüz, Sayfaları Düzenle ızgarası, tekerlekle sayfa geçişi, yeni küçük-boy simgeler (resources.pri), pencere simgesi/başlık logosu. Paketler: installer_output\PDFEditorPro_Store_v1.0.4.msix, PDFEditorPro_Kurulum_v1.0.4.exe, PDFEditorPro_Demo_v1.0.4.exe
- [ ] Partner Center → Update → Packages: 1.0.3'ü kaldır, 1.0.4'ü yükle → Store listings (TR+EN) "What's new" güncelle (store_metinleri.txt) + ekran görüntülerini images\store_v104\ (tr_*/en_* 01–06) ile değiştir → Submit
- [ ] Gumroad: kurulum dosyasını v1.0.4 ile değiştir
- [ ] GitHub release v1.0.4 (demo + kurulum), website yeniden yayınla

## 2026-10-24
- v1.0.4 Store'a sertifikaya gönderildi (onay bekleniyor). GitHub release v1.0.4 + site yayında; demo kurulumu artık tam sürümle aynı program (app_demo.py kaldırıldı).
- v1.0.5 derlendi: PDF→EPUB, Kindle'a Gönder, Calibre varsa AZW3. Paketler: installer_output\PDFEditorPro_*_v1.0.5.*
- [x] Kullanıcı test etti (gerçek Kindle ile USB gönderim + çıkarma doğrulandı)
- [ ] v1.0.4 onaylanınca Partner Center → Update → 1.0.5 paketi + "What's new" (store_metinleri.txt)
- [x] GitHub release v1.0.5, push, site yayında (2026-10-24)
- [ ] Gumroad: kurulum dosyasını v1.0.5 ile değiştir
- [ ] Store 1.0.5: ekran görüntülerine images\store_v104	r_07_kindle / en_07_kindle eklenebilir

## 2026-10-24 (akşam)
- Fiyat: bireysel $9.99 (1 PC), kurumsal $29.99 (5 PC). Lisans sunucusu eşiği 2000 sent (kullanıcı deploy etti), Gumroad fiyat/metin/kapak/dosya güncellendi.
- v1.0.6 yayında: GitHub release, site (8 dil, yeni fiyatlar), pad.xml. Dosya adları arayüz dilinde; MSIX 8 dil bildiriyor.
- [ ] Store: v1.0.4 onaylanınca Update → PDFEditorPro_Store_v1.0.6.msix (1.0.5 atlanır) + What's new (store_metinleri.txt)
- [ ] Store: Add/remove languages → DE, ES, FR, IT, PT-BR, RU; metinler msix/store_metinleri_diller.txt, görseller images/site_shots/<dil>_*.png
- [ ] Store listing açıklamalarındaki fiyatlar 9.99/29.99 (store_metinleri.txt EN/TR güncel)
