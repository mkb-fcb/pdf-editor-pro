"""Builds the 8 "send PDF to Kindle" guide pages under website/ and adds them to sitemap.xml.

Run: python site_kindle.py
"""
import html
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, 'website')
SITE = 'https://mkbsoft.net'
STORE = 'https://apps.microsoft.com/detail/9PJJ019JKTP9'
BUY = 'https://kamilicious12.gumroad.com/l/qxshwx'
LASTMOD = '2026-10-27'

SLUGS = {
    'en': '/send-pdf-to-kindle/',
    'tr': '/tr/pdf-kindle-gonderme/',
    'de': '/de/pdf-an-kindle-senden/',
    'es': '/es/enviar-pdf-a-kindle/',
    'fr': '/fr/envoyer-pdf-sur-kindle/',
    'it': '/it/inviare-pdf-a-kindle/',
    'pt': '/pt/enviar-pdf-para-kindle/',
    'ru': '/ru/otpravit-pdf-na-kindle/',
}
NAMES = {'en': 'English', 'tr': 'Türkçe', 'de': 'Deutsch', 'es': 'Español', 'fr': 'Français',
         'it': 'Italiano', 'pt': 'Português', 'ru': 'Русский'}
OG_LOCALE = {'en': 'en_US', 'tr': 'tr_TR', 'de': 'de_DE', 'es': 'es_ES', 'fr': 'fr_FR', 'it': 'it_IT',
             'pt': 'pt_BR', 'ru': 'ru_RU'}

# Each language: title, desc, h1, lead, toc, then sections. Plain text; <b>/<code> allowed in bodies.
T = {
'en': dict(
    title='How to Send a PDF to Kindle: 3 Easy Ways (2026 Guide)',
    desc='Send a PDF to your Kindle by email, through Amazon\'s Send to Kindle page, or over USB, and make small PDF text readable by converting it to EPUB.',
    h1='How to send a PDF to Kindle',
    lead='There are three ways to get a PDF onto a Kindle: by email, through Amazon\'s Send to Kindle page, or by copying it over a USB cable. All three work, but a PDF page keeps its fixed layout, so on a 6-inch screen the text is often too small to read. This guide shows each method and how to turn the PDF into a real e-book whose text fits the screen.',
    toc='In this guide',
    s_email='Method 1: Send the PDF by email',
    email=[
        'Find your Kindle\'s email address: on amazon.com open <b>Account &amp; Lists → Content Library → Devices</b>, choose your Kindle and look for the address ending in <code>@kindle.com</code>.',
        'Add your own email address to the approved list: <b>Preferences → Personal Document Settings → Approved Personal Document E-mail List</b>. Amazon ignores mail from addresses that are not on this list.',
        'Write a new email to your <code>@kindle.com</code> address and attach the PDF (up to 25 files, 50 MB in total). The subject and body can stay empty.',
        'Wait a few minutes with the Kindle connected to Wi-Fi. The document appears in your library.',
    ],
    email_tip='Tip: Send an EPUB instead of a PDF and Amazon converts it into a Kindle book whose text you can resize.',
    s_web='Method 2: Use Amazon\'s Send to Kindle page',
    web=[
        'Open <code>amazon.com/sendtokindle</code> in your browser and sign in with the Amazon account your Kindle uses.',
        'Drag the PDF or EPUB onto the page (up to 200 MB per file).',
        'Choose the device and click <b>Send</b>. The file also stays in your Amazon library, so it reaches every Kindle and the Kindle app.',
    ],
    s_usb='Method 3: Copy the PDF over USB',
    usb=[
        'Connect the Kindle to your PC with its USB cable. It shows up in File Explorer as <b>Kindle</b>.',
        'Open its <code>documents</code> folder and copy the PDF into it.',
        'Eject the Kindle safely. The PDF appears in the library straight away, with no internet connection needed.',
    ],
    usb_note='Over USB a Kindle opens PDF and AZW3 files, but not EPUB. To read a book with resizable text over USB, convert it to AZW3 first.',
    s_small='Why the text of a PDF is so small on Kindle',
    small='A PDF is a printed page: every line has a fixed position. The Kindle shrinks the whole page to fit the screen, so you have to zoom and scroll. An e-book format such as EPUB or AZW3 has no fixed pages. The text flows to the screen, and you choose the font and size. Converting the PDF to EPUB before sending it fixes the problem.',
    cap_pdf='PDF page on a Kindle',
    cap_ebook='The same page as an e-book',
    s_app='The one-click way: PDF Editor Pro',
    app_lead='PDF Editor Pro is a Windows PDF editor with a built-in Send to Kindle button. It converts the PDF into an e-book and delivers it for you:',
    app=[
        'Open the PDF in PDF Editor Pro and click <b>Send to Kindle</b> on the <b>Convert</b> tab.',
        'If a Kindle is connected by USB, the program finds it and copies the book onto it in one click. With the free Calibre app installed it is sent as a resizable AZW3 book, otherwise as a PDF.',
        'No cable? The program creates an EPUB and sends it with your email program or opens Amazon\'s Send to Kindle page.',
    ],
    app_keeps='Chapters, headings, images, charts and tables are kept; page numbers and running headers are removed. Scanned PDFs have no text to reflow, so their pages are kept as images.',
    cap_app='The Send to Kindle window in PDF Editor Pro',
    app_price='Send to Kindle and EPUB export are part of the full version ($9.99 one-time, no subscription). The free demo lets you try the editor first.',
    cta_demo='Get the free demo',
    cta_buy='Buy full version — $9.99',
    s_faq='Frequently asked questions',
    faq=[
        ('Can a Kindle open PDF files?', 'Yes. Every Kindle opens PDFs sent by email, by the Send to Kindle page or over USB. The page layout stays fixed, though, so the text is often small on the screen.'),
        ('Why can\'t I copy an EPUB to my Kindle over USB?', 'Kindles do not open EPUB files copied over USB. Send the EPUB by email or through the Send to Kindle page, and Amazon converts it for you, or convert it to AZW3 for USB.'),
        ('How big can the file be?', 'By email, up to 50 MB in total per message. On the Send to Kindle web page, up to 200 MB per file.'),
        ('Why did my email never reach the Kindle?', 'Usually the sender\'s address is missing from the Approved Personal Document E-mail List in your Amazon settings. Add it and send again.'),
        ('Do I need Calibre?', 'Only to send a resizable book over USB (AZW3). For email and the Send to Kindle page, PDF Editor Pro creates the EPUB itself.'),
    ],
    back='← PDF Editor Pro home',
    other='This guide in other languages',
),
'tr': dict(
    title='PDF Kindle\'a Nasıl Gönderilir? 3 Kolay Yöntem (2026 Rehberi)',
    desc='PDF\'i Kindle\'a e-postayla, Amazon\'un Send to Kindle sayfasıyla veya USB ile gönderin; küçük yazıları okunur hale getirmek için PDF\'i EPUB\'a çevirin.',
    h1='PDF Kindle\'a nasıl gönderilir?',
    lead='Bir PDF\'i Kindle\'a atmanın üç yolu var: e-posta, Amazon\'un Send to Kindle sayfası ve USB kablosu. Üçü de çalışır; ama PDF sayfasının düzeni sabit olduğu için 6 inçlik ekranda yazılar çoğu zaman okunamayacak kadar küçük kalır. Bu rehber her yöntemi ve PDF\'i yazısı ekrana göre akan gerçek bir e-kitaba nasıl çevireceğinizi anlatıyor.',
    toc='Bu rehberde',
    s_email='1. yöntem: PDF\'i e-postayla gönderin',
    email=[
        'Kindle\'ınızın e-posta adresini bulun: amazon.com\'da <b>Hesap ve Listeler (Account &amp; Lists) → İçerik Kitaplığı (Content Library) → Cihazlar (Devices)</b> bölümünde Kindle\'ınızı seçin, <code>@kindle.com</code> ile biten adresi görürsünüz.',
        'Kendi e-posta adresinizi onaylı listeye ekleyin: <b>Tercihler (Preferences) → Kişisel Belge Ayarları (Personal Document Settings) → Onaylı Kişisel Belge E-posta Listesi</b>. Amazon bu listede olmayan adreslerden gelen postaları yok sayar.',
        '<code>@kindle.com</code> adresinize yeni bir e-posta yazıp PDF\'i ekleyin (en fazla 25 dosya, toplam 50 MB). Konu ve metin boş kalabilir.',
        'Kindle Wi-Fi\'ye bağlıyken birkaç dakika bekleyin; belge kitaplığınızda görünür.',
    ],
    email_tip='İpucu: PDF yerine EPUB gönderirseniz Amazon onu yazı boyutu ayarlanabilen bir Kindle kitabına çevirir.',
    s_web='2. yöntem: Amazon\'un Send to Kindle sayfası',
    web=[
        'Tarayıcıda <code>amazon.com/sendtokindle</code> adresini açın ve Kindle\'ınızın bağlı olduğu Amazon hesabıyla giriş yapın.',
        'PDF\'i veya EPUB\'ı sayfaya sürükleyin (dosya başına en fazla 200 MB).',
        'Cihazı seçip <b>Gönder</b>\'e basın. Dosya Amazon kitaplığınızda da kalır; tüm Kindle\'larınıza ve Kindle uygulamasına ulaşır.',
    ],
    s_usb='3. yöntem: PDF\'i USB ile kopyalayın',
    usb=[
        'Kindle\'ı USB kablosuyla bilgisayara bağlayın. Dosya Gezgini\'nde <b>Kindle</b> olarak görünür.',
        'İçindeki <code>documents</code> klasörünü açıp PDF\'i oraya kopyalayın.',
        'Kindle\'ı güvenle çıkarın. PDF hemen kitaplıkta görünür; internet gerekmez.',
    ],
    usb_note='Kindle USB ile kopyalanan PDF ve AZW3 dosyalarını açar, EPUB\'ı açmaz. USB üzerinden yazısı büyütülebilen bir kitap okumak için önce AZW3\'e çevirmeniz gerekir.',
    s_small='PDF\'in yazıları Kindle\'da neden bu kadar küçük?',
    small='PDF basılı bir sayfadır; her satırın yeri sabittir. Kindle sayfanın tamamını ekrana sığdırmak için küçültür, siz de yakınlaştırıp kaydırmak zorunda kalırsınız. EPUB veya AZW3 gibi e-kitap biçimlerinde sabit sayfa yoktur: metin ekrana göre akar, yazı tipini ve boyutunu siz seçersiniz. PDF\'i göndermeden önce EPUB\'a çevirmek sorunu çözer.',
    cap_pdf='Kindle\'da PDF sayfası',
    cap_ebook='Aynı sayfa e-kitap olarak',
    s_app='Tek tıkla yöntem: PDF Editor Pro',
    app_lead='PDF Editor Pro, içinde Kindle\'a Gönder düğmesi olan yerli bir Windows PDF düzenleyicisidir. PDF\'i e-kitaba çevirip sizin yerinize ulaştırır:',
    app=[
        'PDF\'i PDF Editor Pro\'da açın ve <b>Dönüştür</b> sekmesindeki <b>Kindle\'a Gönder</b> düğmesine tıklayın.',
        'Kindle USB ile bağlıysa program onu bulur ve kitabı tek tıkla içine kopyalar. Ücretsiz Calibre programı kuruluysa yazısı büyütülebilen AZW3 olarak, değilse PDF olarak gönderir.',
        'Kablo yok mu? Program bir EPUB oluşturur ve e-posta programınızla gönderir ya da Amazon\'un Send to Kindle sayfasını açar.',
    ],
    app_keeps='Bölümler, başlıklar, resimler, grafikler ve tablolar korunur; sayfa numaraları ve sayfa üstü yazılar atılır. Taranmış PDF\'lerde akacak metin olmadığı için sayfalar resim olarak korunur.',
    cap_app='PDF Editor Pro\'daki Kindle\'a Gönder penceresi',
    app_price='Kindle\'a Gönder ve EPUB dönüştürme tam sürümde var (tek seferlik 9,99 $, abonelik yok). Ücretsiz demo ile önce düzenleyiciyi deneyebilirsiniz.',
    cta_demo='Ücretsiz demoyu indir',
    cta_buy='Tam sürümü al — 9,99 $',
    s_faq='Sık sorulan sorular',
    faq=[
        ('Kindle PDF dosyalarını açabilir mi?', 'Evet. Her Kindle e-postayla, Send to Kindle sayfasıyla veya USB ile gönderilen PDF\'leri açar. Ancak sayfa düzeni sabit kaldığı için yazılar ekranda çoğu zaman küçük görünür.'),
        ('EPUB\'ı neden USB ile Kindle\'a kopyalayamıyorum?', 'Kindle USB ile kopyalanan EPUB dosyalarını açmaz. EPUB\'ı e-postayla veya Send to Kindle sayfasıyla gönderin, Amazon sizin için çevirir; ya da USB için AZW3\'e çevirin.'),
        ('Dosya en fazla ne kadar büyük olabilir?', 'E-postayla ileti başına toplam 50 MB, Send to Kindle web sayfasında dosya başına 200 MB.'),
        ('E-postam neden Kindle\'a ulaşmadı?', 'Çoğu zaman gönderen adres Amazon ayarlarındaki Onaylı Kişisel Belge E-posta Listesi\'nde değildir. Adresi ekleyip yeniden gönderin.'),
        ('Calibre gerekli mi?', 'Yalnızca USB ile yazısı büyütülebilen kitap (AZW3) göndermek için. E-posta ve Send to Kindle sayfası için PDF Editor Pro EPUB\'ı kendisi oluşturur.'),
    ],
    back='← PDF Editor Pro ana sayfa',
    other='Bu rehber diğer dillerde',
),
'de': dict(
    title='PDF an Kindle senden: 3 einfache Wege (Anleitung 2026)',
    desc='Senden Sie ein PDF per E-Mail, über Amazons Send-to-Kindle-Seite oder per USB an Ihren Kindle und machen Sie kleine PDF-Schrift lesbar, indem Sie es in EPUB umwandeln.',
    h1='PDF an Kindle senden',
    lead='Es gibt drei Wege, ein PDF auf einen Kindle zu bringen: per E-Mail, über Amazons Send-to-Kindle-Seite oder per USB-Kabel. Alle drei funktionieren, aber eine PDF-Seite hat ein festes Layout, daher ist der Text auf einem 6-Zoll-Bildschirm oft zu klein. Diese Anleitung zeigt jede Methode und wie Sie das PDF in ein echtes E-Book verwandeln, dessen Text sich dem Bildschirm anpasst.',
    toc='In dieser Anleitung',
    s_email='Methode 1: PDF per E-Mail senden',
    email=[
        'Finden Sie die E-Mail-Adresse Ihres Kindle: Öffnen Sie auf amazon.de <b>Konto und Listen → Inhalte und Geräte → Geräte</b>, wählen Sie Ihren Kindle und suchen Sie die Adresse mit <code>@kindle.com</code>.',
        'Fügen Sie Ihre eigene Adresse zur Liste hinzu: <b>Einstellungen → Einstellungen für persönliche Dokumente → Liste genehmigter E-Mail-Adressen</b>. Amazon ignoriert E-Mails von Adressen, die nicht in dieser Liste stehen.',
        'Schreiben Sie eine neue E-Mail an Ihre <code>@kindle.com</code>-Adresse und hängen Sie das PDF an (bis zu 25 Dateien, insgesamt 50 MB). Betreff und Text können leer bleiben.',
        'Warten Sie einige Minuten, während der Kindle mit dem WLAN verbunden ist. Das Dokument erscheint in Ihrer Bibliothek.',
    ],
    email_tip='Tipp: Senden Sie statt eines PDFs ein EPUB. Amazon wandelt es in ein Kindle-Buch um, dessen Schriftgröße Sie ändern können.',
    s_web='Methode 2: Amazons Send-to-Kindle-Seite',
    web=[
        'Öffnen Sie <code>amazon.de/sendtokindle</code> im Browser und melden Sie sich mit dem Amazon-Konto Ihres Kindle an.',
        'Ziehen Sie das PDF oder EPUB auf die Seite (bis zu 200 MB pro Datei).',
        'Wählen Sie das Gerät und klicken Sie auf <b>Senden</b>. Die Datei bleibt auch in Ihrer Amazon-Bibliothek und erreicht alle Kindles und die Kindle-App.',
    ],
    s_usb='Methode 3: PDF per USB kopieren',
    usb=[
        'Verbinden Sie den Kindle per USB-Kabel mit dem PC. Er erscheint im Datei-Explorer als <b>Kindle</b>.',
        'Öffnen Sie den Ordner <code>documents</code> und kopieren Sie das PDF hinein.',
        'Werfen Sie den Kindle sicher aus. Das PDF erscheint sofort in der Bibliothek, ganz ohne Internet.',
    ],
    usb_note='Per USB öffnet ein Kindle PDF- und AZW3-Dateien, aber keine EPUB-Dateien. Für ein Buch mit anpassbarer Schrift per USB wandeln Sie es zuerst in AZW3 um.',
    s_small='Warum die Schrift eines PDFs auf dem Kindle so klein ist',
    small='Ein PDF ist eine gedruckte Seite: Jede Zeile hat eine feste Position. Der Kindle verkleinert die ganze Seite auf den Bildschirm, also müssen Sie zoomen und scrollen. E-Book-Formate wie EPUB oder AZW3 haben keine festen Seiten: Der Text fließt auf den Bildschirm, und Sie wählen Schriftart und -größe. Das PDF vor dem Senden in EPUB umzuwandeln löst das Problem.',
    cap_pdf='PDF-Seite auf dem Kindle',
    cap_ebook='Dieselbe Seite als E-Book',
    s_app='Mit einem Klick: PDF Editor Pro',
    app_lead='PDF Editor Pro ist ein PDF-Editor für Windows mit eingebauter Schaltfläche „An Kindle senden“. Er wandelt das PDF in ein E-Book um und liefert es für Sie aus:',
    app=[
        'Öffnen Sie das PDF in PDF Editor Pro und klicken Sie im Reiter <b>Konvertieren</b> auf <b>An Kindle senden</b>.',
        'Ist ein Kindle per USB verbunden, findet das Programm ihn und kopiert das Buch mit einem Klick darauf. Mit der kostenlosen Calibre-App wird es als AZW3 mit anpassbarer Schrift gesendet, sonst als PDF.',
        'Kein Kabel? Das Programm erstellt ein EPUB und sendet es mit Ihrem E-Mail-Programm oder öffnet Amazons Send-to-Kindle-Seite.',
    ],
    app_keeps='Kapitel, Überschriften, Bilder, Diagramme und Tabellen bleiben erhalten; Seitenzahlen und Kopfzeilen werden entfernt. Gescannte PDFs enthalten keinen fließenden Text, ihre Seiten bleiben als Bilder erhalten.',
    cap_app='Das Fenster „An Kindle senden“ in PDF Editor Pro',
    app_price='„An Kindle senden“ und der EPUB-Export gehören zur Vollversion (einmalig 9,99 $, kein Abo). Mit der kostenlosen Demo können Sie den Editor zuerst ausprobieren.',
    cta_demo='Kostenlose Demo holen',
    cta_buy='Vollversion kaufen — 9,99 $',
    s_faq='Häufige Fragen',
    faq=[
        ('Kann ein Kindle PDF-Dateien öffnen?', 'Ja. Jeder Kindle öffnet PDFs, die per E-Mail, über die Send-to-Kindle-Seite oder per USB gesendet werden. Das Seitenlayout bleibt aber fest, daher ist die Schrift oft klein.'),
        ('Warum kann ich ein EPUB nicht per USB auf den Kindle kopieren?', 'Kindles öffnen keine per USB kopierten EPUB-Dateien. Senden Sie das EPUB per E-Mail oder über die Send-to-Kindle-Seite, dann wandelt Amazon es um, oder wandeln Sie es für USB in AZW3 um.'),
        ('Wie groß darf die Datei sein?', 'Per E-Mail bis zu 50 MB pro Nachricht, auf der Send-to-Kindle-Webseite bis zu 200 MB pro Datei.'),
        ('Warum ist meine E-Mail nie auf dem Kindle angekommen?', 'Meist fehlt die Absenderadresse in der Liste genehmigter E-Mail-Adressen in Ihren Amazon-Einstellungen. Fügen Sie sie hinzu und senden Sie erneut.'),
        ('Brauche ich Calibre?', 'Nur, um ein Buch mit anpassbarer Schrift per USB (AZW3) zu senden. Für E-Mail und die Send-to-Kindle-Seite erstellt PDF Editor Pro das EPUB selbst.'),
    ],
    back='← Startseite PDF Editor Pro',
    other='Diese Anleitung in anderen Sprachen',
),
'es': dict(
    title='Cómo enviar un PDF a Kindle: 3 formas fáciles (guía 2026)',
    desc='Envía un PDF a tu Kindle por correo, con la página Send to Kindle de Amazon o por USB, y haz legible el texto pequeño convirtiéndolo a EPUB.',
    h1='Cómo enviar un PDF a Kindle',
    lead='Hay tres formas de pasar un PDF a un Kindle: por correo electrónico, con la página Send to Kindle de Amazon o copiándolo por cable USB. Las tres funcionan, pero una página PDF tiene un diseño fijo y en una pantalla de 6 pulgadas el texto suele quedar demasiado pequeño. Esta guía explica cada método y cómo convertir el PDF en un libro electrónico real cuyo texto se adapta a la pantalla.',
    toc='En esta guía',
    s_email='Método 1: enviar el PDF por correo',
    email=[
        'Busca la dirección de correo de tu Kindle: en amazon.es abre <b>Cuenta y listas → Contenido y dispositivos → Dispositivos</b>, elige tu Kindle y busca la dirección que termina en <code>@kindle.com</code>.',
        'Añade tu propio correo a la lista aprobada: <b>Preferencias → Configuración de documentos personales → Lista de correos electrónicos de documentos personales aprobados</b>. Amazon ignora el correo de direcciones que no están en la lista.',
        'Escribe un correo nuevo a tu dirección <code>@kindle.com</code> y adjunta el PDF (hasta 25 archivos, 50 MB en total). El asunto y el texto pueden quedar vacíos.',
        'Espera unos minutos con el Kindle conectado a la wifi. El documento aparece en tu biblioteca.',
    ],
    email_tip='Consejo: envía un EPUB en lugar de un PDF y Amazon lo convertirá en un libro de Kindle con texto de tamaño ajustable.',
    s_web='Método 2: la página Send to Kindle de Amazon',
    web=[
        'Abre <code>amazon.es/sendtokindle</code> en el navegador e inicia sesión con la cuenta de Amazon de tu Kindle.',
        'Arrastra el PDF o el EPUB a la página (hasta 200 MB por archivo).',
        'Elige el dispositivo y pulsa <b>Enviar</b>. El archivo también queda en tu biblioteca de Amazon y llega a todos tus Kindle y a la app Kindle.',
    ],
    s_usb='Método 3: copiar el PDF por USB',
    usb=[
        'Conecta el Kindle al PC con el cable USB. Aparece en el Explorador de archivos como <b>Kindle</b>.',
        'Abre la carpeta <code>documents</code> y copia el PDF dentro.',
        'Expulsa el Kindle de forma segura. El PDF aparece en la biblioteca al instante, sin necesidad de internet.',
    ],
    usb_note='Por USB, el Kindle abre archivos PDF y AZW3, pero no EPUB. Para leer por USB un libro con texto ajustable, conviértelo antes a AZW3.',
    s_small='Por qué el texto de un PDF se ve tan pequeño en Kindle',
    small='Un PDF es una página impresa: cada línea tiene una posición fija. El Kindle reduce la página entera para que quepa en la pantalla, así que tienes que ampliar y desplazarte. Los formatos de libro electrónico como EPUB o AZW3 no tienen páginas fijas: el texto se adapta a la pantalla y tú eliges la fuente y el tamaño. Convertir el PDF a EPUB antes de enviarlo resuelve el problema.',
    cap_pdf='Página PDF en un Kindle',
    cap_ebook='La misma página como libro electrónico',
    s_app='En un clic: PDF Editor Pro',
    app_lead='PDF Editor Pro es un editor de PDF para Windows con un botón Enviar a Kindle integrado. Convierte el PDF en un libro electrónico y lo entrega por ti:',
    app=[
        'Abre el PDF en PDF Editor Pro y haz clic en <b>Enviar a Kindle</b> en la pestaña <b>Convertir</b>.',
        'Si hay un Kindle conectado por USB, el programa lo detecta y copia el libro en un clic. Con la app gratuita Calibre instalada se envía como AZW3 con texto ajustable; si no, como PDF.',
        '¿Sin cable? El programa crea un EPUB y lo envía con tu programa de correo o abre la página Send to Kindle de Amazon.',
    ],
    app_keeps='Se conservan capítulos, títulos, imágenes, gráficos y tablas; se eliminan los números de página y los encabezados repetidos. Los PDF escaneados no tienen texto que adaptar, así que sus páginas se conservan como imágenes.',
    cap_app='La ventana Enviar a Kindle de PDF Editor Pro',
    app_price='Enviar a Kindle y la exportación a EPUB forman parte de la versión completa (9,99 $ en un único pago, sin suscripción). La demo gratuita te permite probar antes el editor.',
    cta_demo='Descargar la demo gratis',
    cta_buy='Comprar versión completa — 9,99 $',
    s_faq='Preguntas frecuentes',
    faq=[
        ('¿Puede un Kindle abrir archivos PDF?', 'Sí. Todos los Kindle abren los PDF enviados por correo, con la página Send to Kindle o por USB. Pero el diseño de la página queda fijo y el texto suele verse pequeño.'),
        ('¿Por qué no puedo copiar un EPUB al Kindle por USB?', 'Los Kindle no abren archivos EPUB copiados por USB. Envía el EPUB por correo o con la página Send to Kindle y Amazon lo convertirá, o conviértelo a AZW3 para usar USB.'),
        ('¿Qué tamaño puede tener el archivo?', 'Por correo, hasta 50 MB en total por mensaje; en la web Send to Kindle, hasta 200 MB por archivo.'),
        ('¿Por qué mi correo no llegó al Kindle?', 'Normalmente la dirección del remitente no está en la lista de correos aprobados de tu configuración de Amazon. Añádela y vuelve a enviarlo.'),
        ('¿Necesito Calibre?', 'Solo para enviar por USB un libro con texto ajustable (AZW3). Para el correo y la página Send to Kindle, PDF Editor Pro crea el EPUB por sí mismo.'),
    ],
    back='← Inicio de PDF Editor Pro',
    other='Esta guía en otros idiomas',
),
'fr': dict(
    title='Envoyer un PDF sur Kindle : 3 méthodes simples (guide 2026)',
    desc='Envoyez un PDF sur votre Kindle par e-mail, avec la page Send to Kindle d\'Amazon ou par USB, et rendez le petit texte lisible en le convertissant en EPUB.',
    h1='Comment envoyer un PDF sur Kindle',
    lead='Il existe trois façons de mettre un PDF sur une Kindle : par e-mail, avec la page Send to Kindle d\'Amazon ou en le copiant par câble USB. Les trois fonctionnent, mais une page PDF a une mise en page fixe : sur un écran de 6 pouces, le texte est souvent trop petit. Ce guide présente chaque méthode et explique comment transformer le PDF en véritable livre numérique dont le texte s\'adapte à l\'écran.',
    toc='Dans ce guide',
    s_email='Méthode 1 : envoyer le PDF par e-mail',
    email=[
        'Trouvez l\'adresse e-mail de votre Kindle : sur amazon.fr, ouvrez <b>Compte et listes → Contenu et appareils → Appareils</b>, choisissez votre Kindle et repérez l\'adresse se terminant par <code>@kindle.com</code>.',
        'Ajoutez votre propre adresse à la liste approuvée : <b>Préférences → Paramètres des documents personnels → Liste des adresses e-mail approuvées</b>. Amazon ignore les e-mails des adresses absentes de cette liste.',
        'Écrivez un nouvel e-mail à votre adresse <code>@kindle.com</code> et joignez le PDF (jusqu\'à 25 fichiers, 50 Mo au total). L\'objet et le texte peuvent rester vides.',
        'Patientez quelques minutes, Kindle connectée au Wi-Fi. Le document apparaît dans votre bibliothèque.',
    ],
    email_tip='Astuce : envoyez un EPUB plutôt qu\'un PDF, Amazon le convertit en livre Kindle dont vous pouvez agrandir le texte.',
    s_web='Méthode 2 : la page Send to Kindle d\'Amazon',
    web=[
        'Ouvrez <code>amazon.fr/sendtokindle</code> dans le navigateur et connectez-vous avec le compte Amazon de votre Kindle.',
        'Faites glisser le PDF ou l\'EPUB sur la page (jusqu\'à 200 Mo par fichier).',
        'Choisissez l\'appareil et cliquez sur <b>Envoyer</b>. Le fichier reste aussi dans votre bibliothèque Amazon et arrive sur toutes vos Kindle et dans l\'application Kindle.',
    ],
    s_usb='Méthode 3 : copier le PDF par USB',
    usb=[
        'Branchez la Kindle au PC avec son câble USB. Elle apparaît dans l\'Explorateur de fichiers sous le nom <b>Kindle</b>.',
        'Ouvrez son dossier <code>documents</code> et copiez-y le PDF.',
        'Éjectez la Kindle en toute sécurité. Le PDF apparaît aussitôt dans la bibliothèque, sans connexion internet.',
    ],
    usb_note='Par USB, une Kindle ouvre les fichiers PDF et AZW3, mais pas les EPUB. Pour lire par USB un livre au texte ajustable, convertissez-le d\'abord en AZW3.',
    s_small='Pourquoi le texte d\'un PDF est si petit sur Kindle',
    small='Un PDF est une page imprimée : chaque ligne a une position fixe. La Kindle réduit la page entière pour l\'adapter à l\'écran, vous devez donc zoomer et faire défiler. Les formats de livre numérique comme EPUB ou AZW3 n\'ont pas de pages fixes : le texte s\'adapte à l\'écran et vous choisissez la police et la taille. Convertir le PDF en EPUB avant de l\'envoyer règle le problème.',
    cap_pdf='Page PDF sur une Kindle',
    cap_ebook='La même page en livre numérique',
    s_app='En un clic : PDF Editor Pro',
    app_lead='PDF Editor Pro est un éditeur PDF pour Windows doté d\'un bouton Envoyer au Kindle. Il convertit le PDF en livre numérique et le livre pour vous :',
    app=[
        'Ouvrez le PDF dans PDF Editor Pro et cliquez sur <b>Envoyer au Kindle</b> dans l\'onglet <b>Convertir</b>.',
        'Si une Kindle est branchée en USB, le programme la détecte et y copie le livre en un clic. Avec l\'application gratuite Calibre installée, il est envoyé en AZW3 au texte ajustable, sinon en PDF.',
        'Pas de câble ? Le programme crée un EPUB et l\'envoie avec votre logiciel de messagerie ou ouvre la page Send to Kindle d\'Amazon.',
    ],
    app_keeps='Les chapitres, titres, images, graphiques et tableaux sont conservés ; les numéros de page et les en-têtes répétés sont supprimés. Les PDF numérisés n\'ont pas de texte à adapter : leurs pages sont conservées sous forme d\'images.',
    cap_app='La fenêtre Envoyer au Kindle de PDF Editor Pro',
    app_price='L\'envoi vers Kindle et l\'export EPUB font partie de la version complète (9,99 $ en paiement unique, sans abonnement). La démo gratuite permet d\'essayer d\'abord l\'éditeur.',
    cta_demo='Télécharger la démo gratuite',
    cta_buy='Acheter la version complète — 9,99 $',
    s_faq='Questions fréquentes',
    faq=[
        ('Une Kindle peut-elle ouvrir des fichiers PDF ?', 'Oui. Toutes les Kindle ouvrent les PDF envoyés par e-mail, par la page Send to Kindle ou par USB. Mais la mise en page reste fixe, le texte est donc souvent petit.'),
        ('Pourquoi ne puis-je pas copier un EPUB sur ma Kindle par USB ?', 'Les Kindle n\'ouvrent pas les EPUB copiés par USB. Envoyez l\'EPUB par e-mail ou par la page Send to Kindle, Amazon le convertira, ou convertissez-le en AZW3 pour l\'USB.'),
        ('Quelle taille peut avoir le fichier ?', 'Par e-mail, jusqu\'à 50 Mo au total par message ; sur la page Send to Kindle, jusqu\'à 200 Mo par fichier.'),
        ('Pourquoi mon e-mail n\'est-il jamais arrivé sur la Kindle ?', 'Le plus souvent, l\'adresse de l\'expéditeur ne figure pas dans la liste des adresses approuvées de vos paramètres Amazon. Ajoutez-la et renvoyez.'),
        ('Ai-je besoin de Calibre ?', 'Seulement pour envoyer par USB un livre au texte ajustable (AZW3). Pour l\'e-mail et la page Send to Kindle, PDF Editor Pro crée lui-même l\'EPUB.'),
    ],
    back='← Accueil PDF Editor Pro',
    other='Ce guide dans d\'autres langues',
),
'it': dict(
    title='Come inviare un PDF a Kindle: 3 metodi semplici (guida 2026)',
    desc='Invia un PDF al tuo Kindle via e-mail, con la pagina Send to Kindle di Amazon o tramite USB, e rendi leggibile il testo piccolo convertendolo in EPUB.',
    h1='Come inviare un PDF a Kindle',
    lead='Ci sono tre modi per mettere un PDF su un Kindle: via e-mail, con la pagina Send to Kindle di Amazon o copiandolo con il cavo USB. Funzionano tutti e tre, ma una pagina PDF ha un layout fisso e su uno schermo da 6 pollici il testo è spesso troppo piccolo. Questa guida mostra ogni metodo e come trasformare il PDF in un vero ebook il cui testo si adatta allo schermo.',
    toc='In questa guida',
    s_email='Metodo 1: inviare il PDF via e-mail',
    email=[
        'Trova l\'indirizzo e-mail del tuo Kindle: su amazon.it apri <b>Account e liste → Contenuti e dispositivi → Dispositivi</b>, scegli il tuo Kindle e cerca l\'indirizzo che termina con <code>@kindle.com</code>.',
        'Aggiungi il tuo indirizzo all\'elenco approvato: <b>Preferenze → Impostazioni documenti personali → Elenco indirizzi e-mail approvati</b>. Amazon ignora la posta da indirizzi non presenti nell\'elenco.',
        'Scrivi una nuova e-mail al tuo indirizzo <code>@kindle.com</code> e allega il PDF (fino a 25 file, 50 MB in totale). Oggetto e testo possono restare vuoti.',
        'Attendi qualche minuto con il Kindle connesso al Wi-Fi. Il documento compare nella tua libreria.',
    ],
    email_tip='Suggerimento: invia un EPUB invece di un PDF e Amazon lo convertirà in un libro Kindle con testo ridimensionabile.',
    s_web='Metodo 2: la pagina Send to Kindle di Amazon',
    web=[
        'Apri <code>amazon.it/sendtokindle</code> nel browser e accedi con l\'account Amazon del tuo Kindle.',
        'Trascina il PDF o l\'EPUB sulla pagina (fino a 200 MB per file).',
        'Scegli il dispositivo e fai clic su <b>Invia</b>. Il file resta anche nella tua libreria Amazon e arriva su tutti i tuoi Kindle e nell\'app Kindle.',
    ],
    s_usb='Metodo 3: copiare il PDF tramite USB',
    usb=[
        'Collega il Kindle al PC con il cavo USB. Compare in Esplora file come <b>Kindle</b>.',
        'Apri la cartella <code>documents</code> e copiaci il PDF.',
        'Espelli il Kindle in modo sicuro. Il PDF compare subito nella libreria, senza bisogno di internet.',
    ],
    usb_note='Tramite USB il Kindle apre file PDF e AZW3, ma non EPUB. Per leggere via USB un libro con testo ridimensionabile, convertilo prima in AZW3.',
    s_small='Perché il testo di un PDF è così piccolo su Kindle',
    small='Un PDF è una pagina stampata: ogni riga ha una posizione fissa. Il Kindle rimpicciolisce l\'intera pagina per farla stare sullo schermo, quindi devi ingrandire e scorrere. I formati ebook come EPUB o AZW3 non hanno pagine fisse: il testo si adatta allo schermo e scegli tu carattere e dimensione. Convertire il PDF in EPUB prima di inviarlo risolve il problema.',
    cap_pdf='Pagina PDF su un Kindle',
    cap_ebook='La stessa pagina come ebook',
    s_app='Con un clic: PDF Editor Pro',
    app_lead='PDF Editor Pro è un editor PDF per Windows con un pulsante Invia a Kindle integrato. Converte il PDF in ebook e lo consegna al posto tuo:',
    app=[
        'Apri il PDF in PDF Editor Pro e fai clic su <b>Invia a Kindle</b> nella scheda <b>Converti</b>.',
        'Se un Kindle è collegato via USB, il programma lo trova e ci copia il libro con un clic. Con l\'app gratuita Calibre installata viene inviato come AZW3 con testo ridimensionabile, altrimenti come PDF.',
        'Niente cavo? Il programma crea un EPUB e lo invia con il tuo programma di posta oppure apre la pagina Send to Kindle di Amazon.',
    ],
    app_keeps='Capitoli, titoli, immagini, grafici e tabelle vengono mantenuti; numeri di pagina e intestazioni ripetute vengono rimossi. I PDF scansionati non hanno testo da adattare, quindi le loro pagine restano immagini.',
    cap_app='La finestra Invia a Kindle di PDF Editor Pro',
    app_price='Invia a Kindle e l\'esportazione EPUB fanno parte della versione completa (9,99 $ una tantum, nessun abbonamento). Con la demo gratuita puoi provare prima l\'editor.',
    cta_demo='Scarica la demo gratuita',
    cta_buy='Acquista versione completa — 9,99 $',
    s_faq='Domande frequenti',
    faq=[
        ('Un Kindle può aprire file PDF?', 'Sì. Ogni Kindle apre i PDF inviati via e-mail, con la pagina Send to Kindle o via USB. Il layout però resta fisso, quindi il testo è spesso piccolo.'),
        ('Perché non posso copiare un EPUB sul Kindle via USB?', 'I Kindle non aprono file EPUB copiati via USB. Invia l\'EPUB via e-mail o con la pagina Send to Kindle e Amazon lo convertirà, oppure convertilo in AZW3 per l\'USB.'),
        ('Quanto può essere grande il file?', 'Via e-mail fino a 50 MB in totale per messaggio; sulla pagina Send to Kindle fino a 200 MB per file.'),
        ('Perché la mia e-mail non è arrivata al Kindle?', 'Di solito l\'indirizzo del mittente non è nell\'elenco degli indirizzi approvati nelle impostazioni Amazon. Aggiungilo e invia di nuovo.'),
        ('Mi serve Calibre?', 'Solo per inviare via USB un libro con testo ridimensionabile (AZW3). Per e-mail e pagina Send to Kindle, PDF Editor Pro crea da solo l\'EPUB.'),
    ],
    back='← Home di PDF Editor Pro',
    other='Questa guida in altre lingue',
),
'pt': dict(
    title='Como enviar um PDF para o Kindle: 3 jeitos fáceis (guia 2026)',
    desc='Envie um PDF para o seu Kindle por e-mail, pela página Send to Kindle da Amazon ou por USB, e deixe o texto pequeno legível convertendo para EPUB.',
    h1='Como enviar um PDF para o Kindle',
    lead='Há três jeitos de colocar um PDF no Kindle: por e-mail, pela página Send to Kindle da Amazon ou copiando pelo cabo USB. Os três funcionam, mas a página do PDF tem layout fixo e, numa tela de 6 polegadas, o texto costuma ficar pequeno demais. Este guia mostra cada método e como transformar o PDF num e-book de verdade, com texto que se ajusta à tela.',
    toc='Neste guia',
    s_email='Método 1: enviar o PDF por e-mail',
    email=[
        'Encontre o e-mail do seu Kindle: em amazon.com.br abra <b>Contas e Listas → Conteúdo e dispositivos → Dispositivos</b>, escolha o seu Kindle e procure o endereço que termina em <code>@kindle.com</code>.',
        'Adicione o seu e-mail à lista aprovada: <b>Preferências → Configurações de documentos pessoais → Lista de e-mails aprovados</b>. A Amazon ignora mensagens de endereços que não estão na lista.',
        'Escreva um novo e-mail para o seu endereço <code>@kindle.com</code> e anexe o PDF (até 25 arquivos, 50 MB no total). Assunto e texto podem ficar vazios.',
        'Aguarde alguns minutos com o Kindle conectado ao Wi-Fi. O documento aparece na sua biblioteca.',
    ],
    email_tip='Dica: envie um EPUB em vez de um PDF e a Amazon o converte num livro do Kindle com texto de tamanho ajustável.',
    s_web='Método 2: a página Send to Kindle da Amazon',
    web=[
        'Abra <code>amazon.com.br/sendtokindle</code> no navegador e entre com a conta Amazon do seu Kindle.',
        'Arraste o PDF ou o EPUB para a página (até 200 MB por arquivo).',
        'Escolha o dispositivo e clique em <b>Enviar</b>. O arquivo também fica na sua biblioteca da Amazon e chega a todos os seus Kindles e ao app Kindle.',
    ],
    s_usb='Método 3: copiar o PDF por USB',
    usb=[
        'Conecte o Kindle ao PC com o cabo USB. Ele aparece no Explorador de Arquivos como <b>Kindle</b>.',
        'Abra a pasta <code>documents</code> e copie o PDF para dentro dela.',
        'Ejete o Kindle com segurança. O PDF aparece na biblioteca na hora, sem precisar de internet.',
    ],
    usb_note='Pelo USB, o Kindle abre arquivos PDF e AZW3, mas não EPUB. Para ler pelo USB um livro com texto ajustável, converta-o antes para AZW3.',
    s_small='Por que o texto do PDF fica tão pequeno no Kindle',
    small='Um PDF é uma página impressa: cada linha tem posição fixa. O Kindle reduz a página inteira para caber na tela, então você precisa dar zoom e rolar. Formatos de e-book como EPUB ou AZW3 não têm páginas fixas: o texto se ajusta à tela e você escolhe a fonte e o tamanho. Converter o PDF para EPUB antes de enviar resolve o problema.',
    cap_pdf='Página de PDF no Kindle',
    cap_ebook='A mesma página como e-book',
    s_app='Em um clique: PDF Editor Pro',
    app_lead='O PDF Editor Pro é um editor de PDF para Windows com um botão Enviar para Kindle. Ele converte o PDF em e-book e faz a entrega por você:',
    app=[
        'Abra o PDF no PDF Editor Pro e clique em <b>Enviar para Kindle</b> na guia <b>Converter</b>.',
        'Se houver um Kindle conectado por USB, o programa o encontra e copia o livro com um clique. Com o app gratuito Calibre instalado, ele vai como AZW3 com texto ajustável; senão, como PDF.',
        'Sem cabo? O programa cria um EPUB e o envia pelo seu programa de e-mail ou abre a página Send to Kindle da Amazon.',
    ],
    app_keeps='Capítulos, títulos, imagens, gráficos e tabelas são mantidos; números de página e cabeçalhos repetidos são removidos. PDFs escaneados não têm texto para ajustar, então suas páginas ficam como imagens.',
    cap_app='A janela Enviar para Kindle do PDF Editor Pro',
    app_price='Enviar para Kindle e a exportação para EPUB fazem parte da versão completa (US$ 9,99 em pagamento único, sem assinatura). A demo gratuita permite testar o editor antes.',
    cta_demo='Baixar a demo grátis',
    cta_buy='Comprar versão completa — US$ 9,99',
    s_faq='Perguntas frequentes',
    faq=[
        ('O Kindle abre arquivos PDF?', 'Sim. Todo Kindle abre PDFs enviados por e-mail, pela página Send to Kindle ou por USB. Mas o layout da página fica fixo, então o texto costuma ficar pequeno.'),
        ('Por que não consigo copiar um EPUB para o Kindle por USB?', 'O Kindle não abre arquivos EPUB copiados por USB. Envie o EPUB por e-mail ou pela página Send to Kindle e a Amazon o converte, ou converta-o para AZW3 para usar o USB.'),
        ('Qual o tamanho máximo do arquivo?', 'Por e-mail, até 50 MB no total por mensagem; na página Send to Kindle, até 200 MB por arquivo.'),
        ('Por que meu e-mail não chegou ao Kindle?', 'Normalmente o endereço do remetente não está na lista de e-mails aprovados nas configurações da Amazon. Adicione-o e envie de novo.'),
        ('Preciso do Calibre?', 'Só para enviar por USB um livro com texto ajustável (AZW3). Para e-mail e a página Send to Kindle, o PDF Editor Pro cria o EPUB sozinho.'),
    ],
    back='← Início do PDF Editor Pro',
    other='Este guia em outros idiomas',
),
'ru': dict(
    title='Как отправить PDF на Kindle: 3 простых способа (руководство 2026)',
    desc='Отправьте PDF на Kindle по электронной почте, через страницу Send to Kindle от Amazon или по USB и сделайте мелкий текст читаемым, преобразовав PDF в EPUB.',
    h1='Как отправить PDF на Kindle',
    lead='Есть три способа перенести PDF на Kindle: по электронной почте, через страницу Send to Kindle от Amazon или по USB-кабелю. Все три работают, но у страницы PDF фиксированная вёрстка, поэтому на 6-дюймовом экране текст часто слишком мелкий. В этом руководстве описан каждый способ и показано, как превратить PDF в настоящую электронную книгу, текст которой подстраивается под экран.',
    toc='В этом руководстве',
    s_email='Способ 1: отправить PDF по почте',
    email=[
        'Узнайте адрес электронной почты Kindle: на amazon.com откройте <b>Account &amp; Lists → Content Library → Devices</b>, выберите свой Kindle и найдите адрес, оканчивающийся на <code>@kindle.com</code>.',
        'Добавьте свой адрес в список разрешённых: <b>Preferences → Personal Document Settings → Approved Personal Document E-mail List</b>. Письма с адресов не из этого списка Amazon игнорирует.',
        'Напишите новое письмо на адрес <code>@kindle.com</code> и прикрепите PDF (до 25 файлов, всего до 50 МБ). Тему и текст можно оставить пустыми.',
        'Подождите несколько минут, пока Kindle подключён к Wi-Fi. Документ появится в библиотеке.',
    ],
    email_tip='Совет: отправьте EPUB вместо PDF, и Amazon преобразует его в книгу Kindle с изменяемым размером шрифта.',
    s_web='Способ 2: страница Send to Kindle от Amazon',
    web=[
        'Откройте в браузере <code>amazon.com/sendtokindle</code> и войдите в учётную запись Amazon, к которой привязан Kindle.',
        'Перетащите PDF или EPUB на страницу (до 200 МБ на файл).',
        'Выберите устройство и нажмите <b>Send</b>. Файл также остаётся в библиотеке Amazon и попадает на все ваши Kindle и в приложение Kindle.',
    ],
    s_usb='Способ 3: скопировать PDF по USB',
    usb=[
        'Подключите Kindle к компьютеру USB-кабелем. В Проводнике он появится как <b>Kindle</b>.',
        'Откройте папку <code>documents</code> и скопируйте в неё PDF.',
        'Безопасно извлеките Kindle. PDF сразу появится в библиотеке, интернет не нужен.',
    ],
    usb_note='По USB Kindle открывает файлы PDF и AZW3, но не EPUB. Чтобы читать по USB книгу с изменяемым шрифтом, сначала преобразуйте её в AZW3.',
    s_small='Почему текст PDF на Kindle такой мелкий',
    small='PDF — это напечатанная страница: у каждой строки фиксированное место. Kindle уменьшает всю страницу под размер экрана, и приходится увеличивать и прокручивать. В форматах электронных книг, таких как EPUB или AZW3, нет фиксированных страниц: текст подстраивается под экран, а шрифт и размер выбираете вы. Преобразование PDF в EPUB перед отправкой решает проблему.',
    cap_pdf='Страница PDF на Kindle',
    cap_ebook='Та же страница как электронная книга',
    s_app='В один клик: PDF Editor Pro',
    app_lead='PDF Editor Pro — редактор PDF для Windows со встроенной кнопкой «Отправить на Kindle». Он превращает PDF в электронную книгу и доставляет её за вас:',
    app=[
        'Откройте PDF в PDF Editor Pro и нажмите <b>Отправить на Kindle</b> на вкладке <b>Конвертация</b>.',
        'Если Kindle подключён по USB, программа найдёт его и скопирует книгу в один клик. С бесплатной программой Calibre книга отправляется в формате AZW3 с изменяемым шрифтом, без неё — как PDF.',
        'Нет кабеля? Программа создаст EPUB и отправит его через ваш почтовый клиент или откроет страницу Send to Kindle от Amazon.',
    ],
    app_keeps='Главы, заголовки, изображения, диаграммы и таблицы сохраняются; номера страниц и колонтитулы удаляются. В отсканированных PDF нет текста, который можно перекомпоновать, поэтому их страницы сохраняются как изображения.',
    cap_app='Окно «Отправить на Kindle» в PDF Editor Pro',
    app_price='Отправка на Kindle и экспорт в EPUB входят в полную версию (9,99 $ один раз, без подписки). Бесплатная демоверсия позволяет сначала попробовать редактор.',
    cta_demo='Скачать бесплатную демоверсию',
    cta_buy='Купить полную версию — 9,99 $',
    s_faq='Частые вопросы',
    faq=[
        ('Может ли Kindle открывать PDF?', 'Да. Любой Kindle открывает PDF, отправленные по почте, через страницу Send to Kindle или по USB. Но вёрстка страницы остаётся фиксированной, поэтому текст часто мелкий.'),
        ('Почему нельзя скопировать EPUB на Kindle по USB?', 'Kindle не открывает файлы EPUB, скопированные по USB. Отправьте EPUB по почте или через страницу Send to Kindle — Amazon его преобразует — или преобразуйте его в AZW3 для USB.'),
        ('Какого размера может быть файл?', 'По почте — до 50 МБ на письмо, на странице Send to Kindle — до 200 МБ на файл.'),
        ('Почему письмо так и не пришло на Kindle?', 'Обычно адреса отправителя нет в списке разрешённых адресов в настройках Amazon. Добавьте его и отправьте снова.'),
        ('Нужен ли Calibre?', 'Только чтобы отправить по USB книгу с изменяемым шрифтом (AZW3). Для почты и страницы Send to Kindle PDF Editor Pro сам создаёт EPUB.'),
    ],
    back='← Главная PDF Editor Pro',
    other='Это руководство на других языках',
),
}

CSS = '''
:root { --bg:#fff; --bg2:#f8fafc; --text:#0f172a; --text2:#475569; --border:#e2e8f0; --blue:#2563eb;
        --blue-dark:#1d4ed8; --blue-light:#eff6ff; --teal:#0f766e; --teal-light:#f0fdfa; --radius:12px; }
*,*::before,*::after { box-sizing:border-box; margin:0; padding:0; }
body { font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:var(--bg); color:var(--text);
       line-height:1.65; -webkit-font-smoothing:antialiased; }
a { color:var(--blue); }
header { border-bottom:1px solid var(--border); background:#fff; position:sticky; top:0; z-index:10; }
.bar { max-width:880px; margin:0 auto; padding:12px 16px; display:flex; align-items:center; gap:12px; justify-content:space-between; }
.logo { display:flex; align-items:center; gap:10px; font-weight:800; color:var(--text); text-decoration:none; }
.btn { display:inline-block; padding:10px 18px; border-radius:10px; font-weight:700; text-decoration:none; font-size:15px; }
.btn-primary { background:var(--blue); color:#fff; } .btn-primary:hover { background:var(--blue-dark); }
.btn-ghost { border:1px solid var(--border); color:var(--text); background:#fff; }
main { max-width:880px; margin:0 auto; padding:32px 16px 64px; }
.crumb { font-size:14px; margin-bottom:18px; } .crumb a { text-decoration:none; }
h1 { font-size:clamp(28px,5vw,40px); line-height:1.15; letter-spacing:-.02em; margin-bottom:16px; }
.lead { font-size:18px; color:var(--text2); margin-bottom:24px; }
.toc { background:var(--bg2); border:1px solid var(--border); border-radius:var(--radius); padding:16px 20px; margin-bottom:36px; }
.toc b { display:block; margin-bottom:6px; } .toc ol { padding-left:20px; } .toc li { margin:3px 0; }
h2 { font-size:clamp(22px,3.5vw,28px); line-height:1.25; margin:44px 0 14px; letter-spacing:-.01em; scroll-margin-top:80px; }
ol.steps { list-style:none; counter-reset:s; }
ol.steps li { counter-increment:s; position:relative; padding:0 0 14px 44px; }
ol.steps li::before { content:counter(s); position:absolute; left:0; top:0; width:30px; height:30px; border-radius:50%;
                      background:var(--blue-light); color:var(--blue); font-weight:800; display:grid; place-items:center; font-size:15px; }
code { background:var(--bg2); border:1px solid var(--border); border-radius:6px; padding:1px 6px; font-size:.92em; }
.note { background:#fffbeb; border:1px solid #fde68a; border-radius:var(--radius); padding:12px 16px; margin:8px 0 0; color:#78350f; }
.compare { display:flex; gap:20px; align-items:center; justify-content:center; flex-wrap:wrap; margin:20px 0 4px; }
.compare figure { text-align:center; flex:1 1 220px; max-width:300px; }
.compare img { width:100%; height:auto; border:1px solid var(--border); border-radius:10px; background:#fff; }
figcaption { font-size:14px; color:var(--text2); margin-top:8px; }
.app { background:var(--teal-light); border:1px solid #99f6e4; border-radius:16px; padding:24px; margin-top:44px; }
.app h2 { margin-top:0; }
.app-grid { display:grid; grid-template-columns:1fr 260px; gap:24px; align-items:start; }
.app-grid figure img { width:100%; height:auto; border-radius:10px; border:1px solid var(--border); box-shadow:0 8px 30px rgba(15,23,42,.12); }
.app .keeps { color:var(--text2); font-size:15px; margin-top:4px; }
.price { margin:16px 0 14px; font-weight:600; }
.cta { display:flex; gap:10px; flex-wrap:wrap; }
.faq details { border:1px solid var(--border); border-radius:var(--radius); padding:14px 18px; margin-bottom:10px; }
.faq summary { font-weight:700; cursor:pointer; } .faq details p { margin-top:8px; color:var(--text2); }
.langs { margin-top:48px; border-top:1px solid var(--border); padding-top:20px; font-size:15px; }
.langs ul { list-style:none; display:flex; flex-wrap:wrap; gap:8px 16px; margin-top:8px; }
footer { border-top:1px solid var(--border); padding:20px 16px; text-align:center; font-size:14px; color:var(--text2); }
@media (max-width:700px) { .app-grid { grid-template-columns:1fr; } .app-grid figure { max-width:300px; margin:0 auto; }
  .bar .btn { padding:8px 12px; font-size:14px; } .hide-sm { display:none; } }
'''


def li(items):
    return ''.join(f'<li>{x}</li>' for x in items)


def build(lang):
    t = T[lang]
    slug = SLUGS[lang]
    url = SITE + slug
    alt = ''.join(f'<link rel="alternate" hreflang="{l}" href="{SITE}{s}">\n' for l, s in SLUGS.items())
    alt += f'<link rel="alternate" hreflang="x-default" href="{SITE}{SLUGS["en"]}">\n'
    faq_ld = {'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
        {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in t['faq']]}
    howto_ld = {'@context': 'https://schema.org', '@type': 'HowTo', 'name': t['h1'], 'inLanguage': lang,
                'step': [{'@type': 'HowToStep', 'name': html.unescape(_strip(s)), 'text': html.unescape(_strip(s))}
                         for s in t['email']]}
    others = ''.join(f'<li><a href="{SLUGS[l]}" hreflang="{l}">{NAMES[l]}</a></li>' for l in SLUGS if l != lang)
    toc = ''.join(f'<li><a href="#{a}">{t[k]}</a></li>' for a, k in
                  (('email', 's_email'), ('web', 's_web'), ('usb', 's_usb'), ('small', 's_small'), ('app', 's_app'), ('faq', 's_faq')))
    faq = ''.join(f'<details><summary>{html.escape(q)}</summary><p>{html.escape(a)}</p></details>' for q, a in t['faq'])
    e = html.escape
    return f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(t['title'])}</title>
<meta name="description" content="{e(t['desc'])}">
<link rel="canonical" href="{url}">
{alt}<link rel="icon" href="/favicon.ico" sizes="any">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{e(t['title'])}">
<meta property="og:description" content="{e(t['desc'])}">
<meta property="og:image" content="{SITE}/img/shots/{lang}_ereader.webp">
<meta property="og:locale" content="{OG_LOCALE[lang]}">
<meta property="og:site_name" content="PDF Editor Pro by MKBSoft">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<script type="application/ld+json">{json.dumps(faq_ld, ensure_ascii=False)}</script>
<script type="application/ld+json">{json.dumps(howto_ld, ensure_ascii=False)}</script>
<style>{CSS}</style>
</head>
<body>
<header><div class="bar">
  <a class="logo" href="/"><img src="/img/app-icon.png" alt="" width="30" height="30">PDF Editor Pro</a>
  <a class="btn btn-primary" href="{STORE}">{e(t['cta_demo'])}</a>
</div></header>
<main>
  <div class="crumb"><a href="/">{e(t['back'])}</a></div>
  <h1>{e(t['h1'])}</h1>
  <p class="lead">{e(t['lead'])}</p>
  <nav class="toc" aria-label="{e(t['toc'])}"><b>{e(t['toc'])}</b><ol>{toc}</ol></nav>

  <h2 id="email">{e(t['s_email'])}</h2>
  <ol class="steps">{li(t['email'])}</ol>
  <p class="note">{e(t['email_tip'])}</p>

  <h2 id="web">{e(t['s_web'])}</h2>
  <ol class="steps">{li(t['web'])}</ol>

  <h2 id="usb">{e(t['s_usb'])}</h2>
  <ol class="steps">{li(t['usb'])}</ol>
  <p class="note">{e(t['usb_note'])}</p>

  <h2 id="small">{e(t['s_small'])}</h2>
  <p>{e(t['small'])}</p>
  <div class="compare">
    <figure><img src="/img/shots/{lang}_pdfpage.webp" alt="{e(t['cap_pdf'])}" width="794" height="1123" loading="lazy"><figcaption>{e(t['cap_pdf'])}</figcaption></figure>
    <figure><img src="/img/shots/{lang}_ereader.webp" alt="{e(t['cap_ebook'])}" width="630" height="900" loading="lazy"><figcaption>{e(t['cap_ebook'])}</figcaption></figure>
  </div>

  <section class="app" id="app">
    <h2>{e(t['s_app'])}</h2>
    <div class="app-grid">
      <div>
        <p>{e(t['app_lead'])}</p><br>
        <ol class="steps">{li(t['app'])}</ol>
        <p class="keeps">{e(t['app_keeps'])}</p>
      </div>
      <figure><img src="/img/shots/{lang}_07_kindle_crop.webp" alt="{e(t['cap_app'])}" width="520" height="572" loading="lazy"><figcaption>{e(t['cap_app'])}</figcaption></figure>
    </div>
    <p class="price">{e(t['app_price'])}</p>
    <div class="cta">
      <a class="btn btn-primary" href="{STORE}">{e(t['cta_demo'])}</a>
      <a class="btn btn-ghost" href="{BUY}">{e(t['cta_buy'])}</a>
    </div>
  </section>

  <h2 id="faq">{e(t['s_faq'])}</h2>
  <div class="faq">{faq}</div>

  <div class="langs"><b>{e(t['other'])}</b><ul>{others}</ul></div>
</main>
<footer>© 2026 MKBSoft · <a href="/">mkbsoft.net</a> · <a href="mailto:destek@mkbsoft.net">destek@mkbsoft.net</a><br>
Kindle is a trademark of Amazon.com, Inc. PDF Editor Pro is not affiliated with Amazon.</footer>
</body>
</html>
'''


def _strip(s):
    import re
    return re.sub(r'<[^>]+>', '', s)


def write_sitemap():
    p = os.path.join(WEB, 'sitemap.xml')
    urls = [('/', '1.0')] + [(s, '0.8') for s in SLUGS.values()]
    body = ''.join(f'''  <url>
    <loc>{SITE}{u}</loc>
    <lastmod>{LASTMOD}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>{pr}</priority>
  </url>
''' for u, pr in urls)
    open(p, 'w', encoding='utf-8', newline='\n').write(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}</urlset>\n')


if __name__ == '__main__':
    keys = set(T['en'])
    for lang in SLUGS:
        missing = keys - set(T[lang])
        assert not missing, (lang, missing)
        assert len(T[lang]['faq']) == len(T['en']['faq']), lang
        d = os.path.join(WEB, SLUGS[lang].strip('/').replace('/', os.sep))
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, 'index.html'), 'w', encoding='utf-8', newline='\n').write(build(lang))
        print('wrote', SLUGS[lang])
    write_sitemap()
    print('sitemap updated')
