## v1.2.3

**Ücretsiz tam sürüm denemesi** ve **8 dilde tarama okuma**.

- **Tam sürüm denemesi:** demo kullanıcıları lisans almadan önce 7 gün içinde 3 belgede programın tüm özelliklerini kullanabiliyor: sayfa sınırı ve filigran yok. Deneme, demo sınırına ilk takılınca teklif ediliyor; 7 gün ilk kullanımdan itibaren sayılıyor. Okuma ve yazdırma denemeden düşmüyor, aynı belgeyi süre içinde yeniden açmak ek hak harcamıyor
- **Taramalar 8 dilde okunuyor:** Türkçe, İngilizce, Almanca, İspanyolca, Fransızca, İtalyanca, Portekizce ve Rusça (Kiril) Tesseract modelleri pakete eklendi. Program dilindeki metin otomatik tanınıyor; farklı dildeki bir tarama için Düzenle > Tarama Dili
- **Düzeltme:** Gezgin'den açılan uzun bir belge, açılış sırasında yapılan fiyat sorgusu yüzünden demoda 3 sayfaya kısalabiliyordu

(1.2.2 Store'a gönderildi ama yayınlanmadan geri çekildi; içeriği bu sürümdedir.)

**Dosyalar**
- `PDFEditorPro_Kurulum_v1.2.3.exe`: tam sürüm kurulumu
- `PDFEditorPro_Demo_v1.2.3.exe`: demo sürüm (tam okuma ve yazdırma, 7 günde 3 belgelik tam sürüm denemesi; sonra düzenleme ilk 3 sayfada, kayıtta filigran); lisans anahtarı girilince aynı kurulum tam sürüme geçer

Önerilen kurulum yolu Microsoft Store'dur (imzalı paket, otomatik güncelleme): https://apps.microsoft.com/detail/9PJJ019JKTP9

Kaynak kodu: bu etiketteki depo içeriği (AGPL-3.0, bkz. LICENSE). Pakete eklenen Tesseract OCR ve kütüphanelerinin lisansları `static/THIRD_PARTY_LICENSES.txt` dosyasındadır; `get_tesseract.py` bu dosyaların nasıl hazırlandığını gösterir.
