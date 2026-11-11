# PDF Editor Pro (MKBSoft) — Claude çalışma notları

Bu dosya, aynı proje üzerinde çalışan Claude Code ve Claude masaüstü uygulamasının ortak bilgi kaynağıdır.
Son doğrulama: 2026-11-11 (klasör dosyaları + git geçmişi).
Bu dosyaya gizli anahtar, parola veya lisans anahtarı yazılmaz. Repo herkese açık.

## 1. Proje
- Windows için PDF düzenleyici. Python + PyMuPDF; arayüz WebView2 içinde (Flask, `templates/`, `static/`).
- Ana dosyalar: `app.py` (uygulama, `APP_VERSION`), `license.py` (lisans doğrulama), `scan_ocr.py` (taranmış PDF / OCR), `store_iap.py` (Store uygulama içi satın alma), `epub_export.py`, `kindle_usb.py`.
- Paketleme: PyInstaller (`pdf_editor.spec`), Inno Setup (`installer.iss`, `installer_demo.iss`), MSIX (`build_msix.py`, `msix/AppxManifest.xml`).
- Web sitesi: `website/` (mkbsoft.net, 8 dil). PAD dosyası: `pad.xml`.

## 2. Lisans ve kaynak kod
- Lisans: AGPL-3.0 (`LICENSE`). PyMuPDF bunu zorunlu kılıyor.
- Kaynak kod herkese açık GitHub deposunda: https://github.com/mkb-fcb/pdf-editor-pro
- `app.py` ve `license.py` depoda.
- Dağıtılan her sürümün `vX.Y.Z` etiketi ve GitHub release'i var (v1.0.0 → v1.2.3). 1.2.0 ve 1.2.2 hiç dağıtılmadığı için etiketleri yok. Hakkında penceresindeki kaynak bağlantısı `/tree/vX.Y.Z` adresine gider, bu yüzden her sürümde etiket şart.
- `worker.js` ve `wrangler.toml` (Cloudflare lisans sunucusu) depoda yok. `.gitignore` içindeler; ayrı bir program oldukları için AGPL kapsamında değiller.
- Artifex (PyMuPDF): 2026-11-11 tarihli cevaplarında OEM lisansının en az 5.000 $ olduğunu bildirdiler. Lisans alınmadı, AGPL ile devam ediliyor.
- **AGPL'yi bozacak değişiklik yapma:** kaynak kodu özel tutma ve kapalı kaynak dağıtım yapma. Her sürümün kaynağı etiketli ve herkese açık olmalı.
- Bağımlılık değişirse `python make_third_party.py` çalıştır (`static/THIRD_PARTY_LICENSES.txt` güncellenir).

## 3. Fiyat ve lisans sunucusu
- Bireysel lisans 9,99 $ (1 PC), kurumsal lisans 29,99 $ (5 PC). Kaynaklar: `pad.xml`, `msix/store_metinleri*.txt`, `msix/gumroad_metinleri.txt`.
- `worker.js` kurumsal eşiği 2000 sent: `price >= 2000 ? 'corporate' : 'individual'`.
- Store eklentisi `pdfeditorpro_full` (Durable, 9,99 $) uygulama içinden satılıyor. Anahtarlar ayrıca Gumroad'da satılıyor.
- **Fiyat değişirse şunlar birlikte güncellenir:** `worker.js` eşiği (deploy'u kullanıcı yapar), `pad.xml`, Gumroad, `website/` (8 dil) ve Store metinleri (`msix/store_metinleri*.txt` + Partner Center).

## 4. Güncel durum (2026-11-11)
- Mevcut sürüm 1.2.3: `app.py` APP_VERSION, `installer.iss`, `pad.xml`.
- Son git etiketi v1.2.3. GitHub release v1.2.3 "Latest" olarak işaretli (Kurulum + Demo exe).
- Store: 1.2.3 sertifikadan geçti (2026-11-09, "Update in publishing"). Şu an yayında olduğu **Partner Center'dan teyit edilmeli**.
- Sertifikasyonda bekleyen sürüm bilinmiyor. Partner Center'dan teyit edilmeli.
- Ayrıntılı geçmiş `msix/STORE_ILERLEME.md` dosyasında; 2026-11-11 itibarıyla güncel.
- Store ürünü: "PDF Editor Pro - MKBSoft", Store ID 9PJJ019JKTP9.

## 5. Açık işler
- [x] Store listelerine DE/ES/FR/IT/PT-BR/RU eklenmesi. Metinler `msix/store_metinleri_diller.txt` dosyasında; 1.2.0/1.2.1 güncellemesinde 8 dil girildi. Partner Center'da canlı olduğu doğrulanmadı.
- [x] Store açıklamalarında fiyatların 9,99 / 29,99 olması. Dosyalarda eski fiyat yok; Partner Center'daki canlı metin doğrulanmadı.
- [x] Gumroad kurulum dosyasının Kurulum_v1.2.3.exe ile değiştirilmesi. Kullanıcı yaptığını bildirdi (2026-11-09); klasörden doğrulanamaz.
- [ ] GitHub iki faktörlü doğrulama (17 Kasım 2026'dan önce). Durumu doğrulanmadı; API cevap vermedi.
- [ ] Eski, reddedilmiş EXE Store kaydı "PDF Editor Pro - MKBSoftware" silinecek. Silindiğine dair kayıt yok; doğrulanmadı.

## 6. Çalışma kuralları
- Partner Center'da "Submit for certification" butonuna her zaman kullanıcı basar.
- Cloudflare worker deploy, GitHub push, GitHub release ve herkese açık yayınlar kullanıcı onayı olmadan yapılmaz.
- Kullanıcının çalıştıracağı komutlar kısa, tek satırlık ve göreli yollu verilir. Uzun komutlar terminalde bölünüyor.
- Sürüm çıkarırken `APP_VERSION` (`app.py`), `installer.iss`, `installer_demo.iss`, `pad.xml` ve website softwareVersion birlikte güncellenir.
- Yanıtlar Türkçe ve doğrudan olur.

## 7. Senkron notu
- Claude masaüstündeki "pdf editör" projesinde `claude/DURUM_PC_2026-11-11.md` adlı bir özet doküman var. Bu klasörden doğrulanmadı.
- Kaynaklar çelişirse bu klasördeki dosyalar ve git geçmişi esas alınır.
