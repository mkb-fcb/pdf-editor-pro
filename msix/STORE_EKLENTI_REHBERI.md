# Microsoft Store'dan tam sürüm satışı (v1.1.0)

v1.1.0'dan itibaren Store sürümündeki **"Tam Sürümü Satın Al"** düğmesi Microsoft'un ödeme penceresini açar.
Bunun çalışması için Partner Center'da bir **eklenti (add-on)** oluşturulmalı. Eklenti yokken düğme eskisi
gibi Gumroad sayfasını açar, yani paket eklentiden önce de güvenle yayınlanabilir.

Gumroad'dan alınan lisans anahtarları çalışmaya devam eder. Kurumsal (5 PC) lisans Gumroad'da kalır.

## 0. Ödeme ve vergi profili (bir kez)
Partner Center → sağ üstte dişli (Settings) → **Account settings → Payout and tax**.
Banka hesabı ve vergi formunu doldurun (Türkiye için W-8BEN). Bu yapılmadan Store ödeme yapmaz.

## 1. Eklentiyi oluşturun
1. Partner Center → **Apps and games** → PDF Editor Pro - MKBSoft → soldan **Add-ons** → **Create a new add-on**.
2. Product type: **Durable** (Kalıcı).
3. Product ID: **`pdfeditorpro_full`** — birebir böyle yazın; program bu kimlikle arar. Sonradan değiştirilemez.
4. **Create**.

## 2. Eklenti ayarları
- **Properties**
  - Product lifetime: **Forever**
  - Content type: **Electronic software download**
  - Diğer alanlar boş kalabilir → Save
- **Pricing and availability**
  - Markets: tümü (varsayılan)
  - Pricing: **Base price 9.99 USD** (Microsoft her ülke için yerel fiyatı otomatik hesaplar; program o fiyatı gösterir)
  - Save
- **Store listings** → her dil için **Add/remove languages** ile 8 dili ekleyin, aşağıdaki başlık ve açıklamayı yapıştırın. Simge (300×300) olarak `images/store_logo_300x300.png` kullanılabilir.

| Dil | Title | Description |
|---|---|---|
| TR | Tam Sürüm | Tüm sayfalarda sınırsız düzenleme, filigransız kayıt, şifreleme ve Word/Excel/PowerPoint/JPG/EPUB dışa aktarma. Tek seferlik ödeme, abonelik yok. |
| EN | Full Version | Unlimited editing on every page, watermark-free saving, password protection and Word/Excel/PowerPoint/JPG/EPUB export. One-time payment, no subscription. |
| DE | Vollversion | Unbegrenztes Bearbeiten aller Seiten, Speichern ohne Wasserzeichen, Passwortschutz und Export nach Word/Excel/PowerPoint/JPG/EPUB. Einmalzahlung, kein Abo. |
| ES | Versión completa | Edición ilimitada en todas las páginas, guardado sin marca de agua, protección con contraseña y exportación a Word/Excel/PowerPoint/JPG/EPUB. Pago único, sin suscripción. |
| FR | Version complète | Édition illimitée sur toutes les pages, enregistrement sans filigrane, protection par mot de passe et export Word/Excel/PowerPoint/JPG/EPUB. Paiement unique, sans abonnement. |
| IT | Versione completa | Modifica illimitata su tutte le pagine, salvataggio senza filigrana, protezione con password ed esportazione in Word/Excel/PowerPoint/JPG/EPUB. Pagamento unico, nessun abbonamento. |
| PT-BR | Versão completa | Edição ilimitada em todas as páginas, salvamento sem marca d'água, proteção por senha e exportação para Word/Excel/PowerPoint/JPG/EPUB. Pagamento único, sem assinatura. |
| RU | Полная версия | Неограниченное редактирование всех страниц, сохранение без водяного знака, защита паролем и экспорт в Word/Excel/PowerPoint/JPG/EPUB. Разовая оплата, без подписки. |

5. **Submit to the Store** (eklenti ayrı bir gönderimdir, kendi sertifikasyonundan geçer).

## 3. Uygulama güncellemesi (v1.1.0)
1. Uygulama → **Update** → **Packages**: eski paketi kaldırın, `installer_output\PDFEditorPro_Store_v1.1.0.msix` yükleyin.
2. **Store listings** (her dil):
   - "What's new in this version" → `msix\yenilikler_v1.1.0.txt`
   - Description → `msix\store_metinleri.txt` (TR/EN) ve `msix\store_metinleri_diller.txt` (diğer diller) içindeki güncel açıklama
     (demo sınırları ve "uygulama içinden Microsoft Store ile satın alma" cümlesi değişti — sertifikasyon açıklama ile
     uygulamanın uyuşmasına bakıyor).
3. **Submission options → Notes for certification**: mevcut test anahtarı notunun yanına şunu ekleyin:
   "The full version can also be bought in-app through the Microsoft Store add-on 'pdfeditorpro_full' (Buy Full Version button). License keys from mkbsoft.net keep working as an alternative."
4. **Submit for certification**.

## 4. Test (yayınlandıktan sonra)
- Lisanssız bir Windows hesabında Store'dan kurun → demo bandındaki fiyat Store'un yerel fiyatına döner (ör. ₺).
- **Tam Sürümü Satın Al** → Microsoft ödeme penceresi açılmalı. Satın alınca program kendini tam sürüme açar.
- Not: Geliştirici bilgisayarında Gumroad test anahtarı etkin olduğu için program zaten tam sürüm açılır; testi başka
  bir Windows kullanıcısıyla veya `%APPDATA%\PDFEditorPro\license.json` dosyasını geçici olarak başka yere taşıyarak yapın.
