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
