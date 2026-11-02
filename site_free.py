"""Builds the 8 "free PDF editor instead of a crack" pages under website/ and adds them to sitemap.xml.

People search for cracked / "full download" PDF editors. These pages explain the risks of cracks
and point to the free, legal Microsoft Store version (full reading and printing, editing demo).

Run: python site_free.py
"""
import html
import json
import os

from site_kindle import WEB, SITE, STORE, BUY, NAMES, OG_LOCALE, CSS, li, write_sitemap

LASTMOD = '2026-11-02'

SLUGS = {
    'en': '/free-pdf-editor-no-crack/',
    'tr': '/tr/pdf-editor-full-ucretsiz/',
    'de': '/de/pdf-editor-kostenlos-ohne-crack/',
    'es': '/es/editor-pdf-gratis-sin-crack/',
    'fr': '/fr/editeur-pdf-gratuit-sans-crack/',
    'it': '/it/editor-pdf-gratis-senza-crack/',
    'pt': '/pt/editor-pdf-gratis-sem-crack/',
    'ru': '/ru/pdf-redaktor-besplatno-bez-kryaka/',
}

# Each language: plain text; <b> allowed in list items.
T = {
'en': dict(
    title='PDF Editor Crack or Full Download? A Free, Safe Alternative (2026)',
    desc='Cracked PDF editors often hide malware and password stealers. PDF Editor Pro is free on the Microsoft Store: read and print any PDF, try every editing tool, and unlock the full version for $9.99 once.',
    h1='Looking for a cracked PDF editor? Read this first',
    lead='"PDF editor crack", "full version free download" and "license key" are some of the most common searches for PDF software. It makes sense: popular PDF editors cost a monthly subscription. But a crack usually costs more than it saves. Here is what the risks are, and how to get a PDF editor for free, legally and safely.',
    toc='On this page',
    s_risk='What a crack really installs',
    risk=[
        '<b>Malware and trojans.</b> Cracks, keygens and "patchers" are one of the most common ways malware spreads. The file is modified by an unknown person, and you run it with administrator rights.',
        '<b>Password and bank stealers.</b> Many cracks carry "infostealers" that copy saved browser passwords, cookies, e-mail and banking logins, and crypto wallets.',
        '<b>Ransomware.</b> Some infected installers encrypt your documents and ask for money to unlock them.',
        '<b>"Turn off your antivirus first".</b> Almost every crack asks for this. That alone tells you what the antivirus would have found.',
        '<b>No updates.</b> A cracked program never gets security fixes, and an update can break it at any time.',
        '<b>Legal risk.</b> Using unlicensed software breaks copyright law. For companies, a software audit can lead to fines.',
    ],
    s_free='The free and legal way: PDF Editor Pro',
    free_lead='PDF Editor Pro is a Windows PDF editor by MKBSoft, published on the Microsoft Store. The free version is not a 7-day trial; it keeps working:',
    free=[
        '<b>Read and print any PDF in full, free and forever</b>: reading mode, zoom, page navigation, every printer setting.',
        'Use it as your <b>default PDF viewer</b>: double-click a PDF and it opens in reading mode.',
        '<b>Try every editing tool</b>: edit text, find &amp; replace, highlight, stamps, signatures, merge, split, compress, convert to Word/Excel/EPUB. In the free version editing works on the first 3 pages and saved files get a watermark.',
        'Installed from the <b>Microsoft Store</b>: checked by Microsoft, no installer warnings, automatic updates.',
    ],
    s_cmp='Crack vs. free vs. full version',
    cmp_head=['', 'Cracked editor', 'PDF Editor Pro (free)', 'PDF Editor Pro (full)'],
    cmp_rows=[
        ('Price', 'Free — paid with your data', 'Free', '$9.99 once, no subscription'),
        ('Malware risk', 'High', 'None (Microsoft Store)', 'None (Microsoft Store)'),
        ('Read &amp; print', 'Yes', 'Yes, full documents', 'Yes'),
        ('Editing', 'Yes', 'First 3 pages, watermark', 'Unlimited, no watermark'),
        ('Updates', 'No', 'Yes, automatic', 'Yes, automatic'),
        ('Legal', 'No', 'Yes', 'Yes'),
    ],
    s_how='Get it in one minute',
    how=[
        'Open PDF Editor Pro on the Microsoft Store and click <b>Get</b> (or <b>Install</b>).',
        'Start the program and open a PDF, or drag one into the window.',
        'Optional: right-click any PDF → <b>Open with</b> → <b>Choose another app</b> → PDF Editor Pro → <b>Always</b>, to make it your default PDF viewer.',
        'When you need unlimited editing, click <b>Buy</b> in the program and enter your license key. No reinstall.',
    ],
    cta_free='Download free from Microsoft Store',
    cta_buy='Full version — $9.99 once',
    s_faq='Frequently asked questions',
    faq=[
        ('Is PDF Editor Pro really free?', 'Yes. Reading and printing complete PDFs is free with no time limit, and you can try all editing tools on the first 3 pages. Only unlimited editing and watermark-free saving need the full version.'),
        ('Is there a free full version download?', 'Not legally. Sites that offer a "full version free download" or a license key generator are distributing modified files. Use the free Microsoft Store version instead; it works without time limit.'),
        ('Why does my antivirus delete cracks and keygens?', 'Because many of them contain malware, and the ones that don\'t behave the same way: they modify program files and hide from security software. A detection is not a "false positive" you should ignore.'),
        ('How much is the full version?', '$9.99 once for one PC, or $29.99 for 5 PCs. No subscription, and updates are included.'),
        ('Is the Microsoft Store version safe?', 'Yes. Apps on the Microsoft Store are reviewed by Microsoft before they are published, and updates arrive automatically.'),
    ],
    back='← PDF Editor Pro home',
    other='This page in other languages',
),
'tr': dict(
    title='PDF Editör Crack / Full İndir Yerine Ücretsiz ve Güvenli Alternatif (2026)',
    desc='Crack\'li PDF editörleri çoğu zaman virüs ve şifre çalan yazılım taşır. PDF Editor Pro Microsoft Store\'da ücretsiz: her PDF\'i okuyun ve yazdırın, tüm düzenleme araçlarını deneyin, tam sürüm tek seferlik 9,99 $.',
    h1='Crack\'li PDF editör mü arıyorsunuz? Önce bunu okuyun',
    lead='"PDF editör crack", "full indir", "ücretsiz full sürüm" ve "lisans anahtarı" PDF programları için en çok yapılan aramalar arasında. Anlaşılır bir durum: popüler PDF editörleri aylık abonelik istiyor. Ama crack çoğu zaman kazandırdığından fazlasını kaybettirir. Bu sayfada riskleri ve bir PDF editörünü ücretsiz, yasal ve güvenli şekilde nasıl kullanabileceğinizi bulacaksınız.',
    toc='Bu sayfada',
    s_risk='Crack aslında bilgisayarınıza ne kurar?',
    risk=[
        '<b>Virüs ve truva atı.</b> Crack, keygen ve "patch" dosyaları zararlı yazılımların en çok yayıldığı yollardan biridir. Dosyayı kimin değiştirdiği belli değildir ve siz onu yönetici yetkisiyle çalıştırırsınız.',
        '<b>Şifre ve banka bilgisi çalan yazılımlar.</b> Birçok crack, tarayıcıda kayıtlı şifreleri, çerezleri, e-posta ve internet bankacılığı girişlerini, kripto cüzdanlarını kopyalayan "infostealer" yazılımlar taşır.',
        '<b>Fidye yazılımı.</b> Bazı virüslü kurulumlar belgelerinizi şifreler ve açmak için para ister.',
        '<b>"Önce antivirüsü kapatın".</b> Neredeyse her crack bunu ister. Bu bile antivirüsün ne bulacağını gösterir.',
        '<b>Güncelleme yok.</b> Crack\'li program güvenlik güncellemesi almaz, bir güncelleme onu her an bozabilir.',
        '<b>Hukuki risk.</b> Lisanssız yazılım kullanmak telif hakları mevzuatına aykırıdır. Şirketlerde yazılım denetimi para cezasıyla sonuçlanabilir.',
    ],
    s_free='Ücretsiz ve yasal yol: PDF Editor Pro',
    free_lead='PDF Editor Pro, MKBSoft\'un geliştirdiği ve Microsoft Store\'da yayınlanan bir Windows PDF editörüdür. Ücretsiz sürüm 7 günlük deneme değildir, süresiz çalışır:',
    free=[
        '<b>Her PDF\'i tamamen okuyun ve yazdırın, ücretsiz ve süresiz</b>: okuma modu, yakınlaştırma, sayfa gezintisi, tüm yazıcı ayarları.',
        '<b>Varsayılan PDF görüntüleyiciniz</b> yapın: PDF\'e çift tıklayınca okuma modunda açılır.',
        '<b>Tüm düzenleme araçlarını deneyin</b>: metin düzenleme, bul ve değiştir, vurgulama, damga, imza, birleştirme, bölme, küçültme, Word/Excel/EPUB\'a dönüştürme. Ücretsiz sürümde düzenleme ilk 3 sayfada çalışır, kaydedilen dosyaya filigran eklenir.',
        '<b>Microsoft Store\'dan</b> kurulur: Microsoft tarafından incelenir, kurulum uyarısı çıkmaz, otomatik güncellenir.',
    ],
    s_cmp='Crack, ücretsiz sürüm ve tam sürüm karşılaştırması',
    cmp_head=['', 'Crack\'li editör', 'PDF Editor Pro (ücretsiz)', 'PDF Editor Pro (tam)'],
    cmp_rows=[
        ('Fiyat', 'Ücretsiz — bedelini verilerinizle ödersiniz', 'Ücretsiz', 'Tek seferlik 9,99 $, abonelik yok'),
        ('Virüs riski', 'Yüksek', 'Yok (Microsoft Store)', 'Yok (Microsoft Store)'),
        ('Okuma ve yazdırma', 'Var', 'Var, belgenin tamamı', 'Var'),
        ('Düzenleme', 'Var', 'İlk 3 sayfa, filigranlı', 'Sınırsız, filigransız'),
        ('Güncelleme', 'Yok', 'Var, otomatik', 'Var, otomatik'),
        ('Yasal', 'Hayır', 'Evet', 'Evet'),
    ],
    s_how='Bir dakikada kurun',
    how=[
        'Microsoft Store\'da PDF Editor Pro sayfasını açın ve <b>Al</b> (veya <b>Yükle</b>) düğmesine basın.',
        'Programı başlatın ve bir PDF açın ya da pencereye sürükleyin.',
        'İsterseniz: herhangi bir PDF\'e sağ tıklayın → <b>Birlikte aç</b> → <b>Başka bir uygulama seçin</b> → PDF Editor Pro → <b>Her zaman</b>. Böylece varsayılan PDF görüntüleyiciniz olur.',
        'Sınırsız düzenleme gerektiğinde programdaki <b>Satın Al</b> düğmesine basın ve lisans anahtarınızı girin. Yeniden kurmanız gerekmez.',
    ],
    cta_free='Microsoft Store\'dan Ücretsiz İndir',
    cta_buy='Tam sürüm — tek seferlik 9,99 $',
    s_faq='Sık sorulan sorular',
    faq=[
        ('PDF Editor Pro gerçekten ücretsiz mi?', 'Evet. PDF\'lerin tamamını okumak ve yazdırmak süre sınırı olmadan ücretsizdir, tüm düzenleme araçlarını da ilk 3 sayfada deneyebilirsiniz. Yalnızca sınırsız düzenleme ve filigransız kayıt için tam sürüm gerekir.'),
        ('Ücretsiz full sürüm indirebilir miyim?', 'Yasal olarak hayır. "Full indir" veya lisans anahtarı üreteci sunan siteler değiştirilmiş dosyalar dağıtır. Bunun yerine Microsoft Store\'daki ücretsiz sürümü kullanın; süre sınırı olmadan çalışır.'),
        ('Antivirüs neden crack ve keygen dosyalarını siliyor?', 'Çünkü bunların birçoğu zararlı yazılım içerir; içermeyenler de aynı şekilde davranır: program dosyalarını değiştirir ve güvenlik yazılımından saklanır. Bu uyarı, görmezden gelinecek bir "yanlış alarm" değildir.'),
        ('Tam sürüm ne kadar?', 'Tek bilgisayar için tek seferlik 9,99 $, 5 bilgisayar için 29,99 $. Abonelik yok, güncellemeler dahil.'),
        ('Microsoft Store sürümü güvenli mi?', 'Evet. Microsoft Store\'daki uygulamalar yayınlanmadan önce Microsoft tarafından incelenir ve güncellemeler otomatik gelir.'),
    ],
    back='← PDF Editor Pro ana sayfa',
    other='Bu sayfa diğer dillerde',
),
'de': dict(
    title='PDF-Editor Crack oder Vollversion gratis? Die sichere, kostenlose Alternative (2026)',
    desc='Gecrackte PDF-Editoren enthalten oft Schadsoftware und Passwort-Diebe. PDF Editor Pro ist kostenlos im Microsoft Store: jede PDF lesen und drucken, alle Werkzeuge testen, Vollversion einmalig 9,99 $.',
    h1='Sie suchen einen gecrackten PDF-Editor? Lesen Sie zuerst das',
    lead='„PDF Editor Crack", „Vollversion kostenlos" und „Lizenzschlüssel" gehören zu den häufigsten Suchen nach PDF-Software. Verständlich: Bekannte PDF-Editoren kosten ein monatliches Abo. Doch ein Crack kostet meist mehr, als er spart. Hier lesen Sie, welche Risiken es gibt und wie Sie einen PDF-Editor kostenlos, legal und sicher nutzen.',
    toc='Auf dieser Seite',
    s_risk='Was ein Crack wirklich installiert',
    risk=[
        '<b>Viren und Trojaner.</b> Cracks, Keygens und „Patcher" gehören zu den häufigsten Verbreitungswegen von Schadsoftware. Die Datei wurde von Unbekannten verändert, und Sie starten sie mit Administratorrechten.',
        '<b>Passwort- und Bankdaten-Diebe.</b> Viele Cracks enthalten „Infostealer", die gespeicherte Browser-Passwörter, Cookies, E-Mail- und Banking-Zugänge sowie Krypto-Wallets kopieren.',
        '<b>Ransomware.</b> Manche infizierten Installer verschlüsseln Ihre Dokumente und verlangen Lösegeld.',
        '<b>„Schalten Sie zuerst den Virenschutz aus".</b> Das verlangt fast jeder Crack. Schon das zeigt, was der Virenschutz finden würde.',
        '<b>Keine Updates.</b> Ein gecracktes Programm erhält keine Sicherheitsupdates und kann durch ein Update jederzeit unbrauchbar werden.',
        '<b>Rechtliches Risiko.</b> Unlizenzierte Software verstößt gegen das Urheberrecht. In Unternehmen kann eine Software-Prüfung zu Strafen führen.',
    ],
    s_free='Der kostenlose und legale Weg: PDF Editor Pro',
    free_lead='PDF Editor Pro ist ein Windows-PDF-Editor von MKBSoft, veröffentlicht im Microsoft Store. Die kostenlose Version ist keine 7-Tage-Testversion; sie funktioniert dauerhaft:',
    free=[
        '<b>Jede PDF vollständig lesen und drucken, kostenlos und unbegrenzt</b>: Lesemodus, Zoom, Seitennavigation, alle Druckereinstellungen.',
        'Als <b>Standard-PDF-Anzeige</b> nutzen: Doppelklick auf eine PDF öffnet sie im Lesemodus.',
        '<b>Alle Bearbeitungswerkzeuge testen</b>: Text bearbeiten, Suchen und Ersetzen, Markieren, Stempel, Signaturen, Zusammenführen, Teilen, Komprimieren, Umwandeln in Word/Excel/EPUB. In der kostenlosen Version gilt die Bearbeitung für die ersten 3 Seiten, gespeicherte Dateien erhalten ein Wasserzeichen.',
        'Installation über den <b>Microsoft Store</b>: von Microsoft geprüft, keine Installer-Warnungen, automatische Updates.',
    ],
    s_cmp='Crack, kostenlose Version und Vollversion im Vergleich',
    cmp_head=['', 'Gecrackter Editor', 'PDF Editor Pro (kostenlos)', 'PDF Editor Pro (Vollversion)'],
    cmp_rows=[
        ('Preis', 'Gratis — bezahlt mit Ihren Daten', 'Kostenlos', 'Einmalig 9,99 $, kein Abo'),
        ('Malware-Risiko', 'Hoch', 'Keins (Microsoft Store)', 'Keins (Microsoft Store)'),
        ('Lesen und Drucken', 'Ja', 'Ja, ganze Dokumente', 'Ja'),
        ('Bearbeiten', 'Ja', 'Erste 3 Seiten, Wasserzeichen', 'Unbegrenzt, ohne Wasserzeichen'),
        ('Updates', 'Nein', 'Ja, automatisch', 'Ja, automatisch'),
        ('Legal', 'Nein', 'Ja', 'Ja'),
    ],
    s_how='In einer Minute installiert',
    how=[
        'Öffnen Sie PDF Editor Pro im Microsoft Store und klicken Sie auf <b>Herunterladen</b> (oder <b>Installieren</b>).',
        'Starten Sie das Programm und öffnen Sie eine PDF oder ziehen Sie sie ins Fenster.',
        'Optional: Rechtsklick auf eine PDF → <b>Öffnen mit</b> → <b>Andere App auswählen</b> → PDF Editor Pro → <b>Immer</b>, damit es Ihre Standard-PDF-Anzeige wird.',
        'Für unbegrenztes Bearbeiten klicken Sie im Programm auf <b>Kaufen</b> und geben Ihren Lizenzschlüssel ein. Keine Neuinstallation nötig.',
    ],
    cta_free='Kostenlos im Microsoft Store',
    cta_buy='Vollversion — einmalig 9,99 $',
    s_faq='Häufige Fragen',
    faq=[
        ('Ist PDF Editor Pro wirklich kostenlos?', 'Ja. Vollständige PDFs lesen und drucken ist ohne Zeitlimit kostenlos, und alle Bearbeitungswerkzeuge lassen sich auf den ersten 3 Seiten testen. Nur unbegrenztes Bearbeiten und Speichern ohne Wasserzeichen erfordern die Vollversion.'),
        ('Gibt es eine kostenlose Vollversion zum Download?', 'Legal nicht. Seiten mit „Vollversion gratis" oder Keygens verbreiten veränderte Dateien. Nutzen Sie stattdessen die kostenlose Version aus dem Microsoft Store; sie läuft ohne Zeitlimit.'),
        ('Warum löscht mein Virenschutz Cracks und Keygens?', 'Weil viele davon Schadsoftware enthalten, und die übrigen sich genauso verhalten: Sie verändern Programmdateien und verstecken sich vor Sicherheitssoftware. Eine solche Meldung ist kein „Fehlalarm", den man ignorieren sollte.'),
        ('Was kostet die Vollversion?', 'Einmalig 9,99 $ für einen PC oder 29,99 $ für 5 PCs. Kein Abo, Updates inklusive.'),
        ('Ist die Microsoft-Store-Version sicher?', 'Ja. Apps im Microsoft Store werden vor der Veröffentlichung von Microsoft geprüft, und Updates kommen automatisch.'),
    ],
    back='← PDF Editor Pro Startseite',
    other='Diese Seite in anderen Sprachen',
),
'es': dict(
    title='¿Editor PDF crack o versión completa gratis? Una alternativa gratuita y segura (2026)',
    desc='Los editores PDF crackeados suelen esconder malware y ladrones de contraseñas. PDF Editor Pro es gratis en Microsoft Store: lea e imprima cualquier PDF, pruebe todas las herramientas y desbloquee la versión completa por 9,99 $ una vez.',
    h1='¿Busca un editor PDF crackeado? Lea esto primero',
    lead='«Editor PDF crack», «versión completa gratis» y «clave de licencia» están entre las búsquedas más comunes de programas PDF. Es comprensible: los editores PDF más conocidos cobran una suscripción mensual. Pero un crack suele costar más de lo que ahorra. Aquí verá cuáles son los riesgos y cómo usar un editor PDF gratis, legal y seguro.',
    toc='En esta página',
    s_risk='Lo que realmente instala un crack',
    risk=[
        '<b>Virus y troyanos.</b> Los cracks, keygens y «parches» son una de las vías más comunes de propagación de malware. Alguien desconocido modificó el archivo y usted lo ejecuta con permisos de administrador.',
        '<b>Robo de contraseñas y datos bancarios.</b> Muchos cracks llevan «infostealers» que copian las contraseñas guardadas en el navegador, cookies, accesos al correo y a la banca, y monederos de criptomonedas.',
        '<b>Ransomware.</b> Algunos instaladores infectados cifran sus documentos y piden un rescate.',
        '<b>«Primero desactive el antivirus».</b> Casi todos los cracks lo piden. Eso ya indica lo que el antivirus encontraría.',
        '<b>Sin actualizaciones.</b> Un programa crackeado no recibe parches de seguridad y una actualización puede romperlo en cualquier momento.',
        '<b>Riesgo legal.</b> Usar software sin licencia infringe la ley de propiedad intelectual. En empresas, una auditoría de software puede acabar en multas.',
    ],
    s_free='La forma gratuita y legal: PDF Editor Pro',
    free_lead='PDF Editor Pro es un editor PDF para Windows de MKBSoft, publicado en Microsoft Store. La versión gratuita no es una prueba de 7 días; sigue funcionando:',
    free=[
        '<b>Lea e imprima cualquier PDF completo, gratis y para siempre</b>: modo lectura, zoom, navegación por páginas, todos los ajustes de impresora.',
        'Úselo como <b>visor de PDF predeterminado</b>: haga doble clic en un PDF y se abre en modo lectura.',
        '<b>Pruebe todas las herramientas de edición</b>: editar texto, buscar y reemplazar, resaltar, sellos, firmas, unir, dividir, comprimir, convertir a Word/Excel/EPUB. En la versión gratuita la edición funciona en las 3 primeras páginas y los archivos guardados llevan marca de agua.',
        'Se instala desde <b>Microsoft Store</b>: revisado por Microsoft, sin avisos de instalación, actualizaciones automáticas.',
    ],
    s_cmp='Crack, versión gratuita y versión completa',
    cmp_head=['', 'Editor crackeado', 'PDF Editor Pro (gratis)', 'PDF Editor Pro (completo)'],
    cmp_rows=[
        ('Precio', 'Gratis — lo paga con sus datos', 'Gratis', '9,99 $ una vez, sin suscripción'),
        ('Riesgo de malware', 'Alto', 'Ninguno (Microsoft Store)', 'Ninguno (Microsoft Store)'),
        ('Leer e imprimir', 'Sí', 'Sí, documentos completos', 'Sí'),
        ('Edición', 'Sí', '3 primeras páginas, marca de agua', 'Ilimitada, sin marca de agua'),
        ('Actualizaciones', 'No', 'Sí, automáticas', 'Sí, automáticas'),
        ('Legal', 'No', 'Sí', 'Sí'),
    ],
    s_how='Instálelo en un minuto',
    how=[
        'Abra PDF Editor Pro en Microsoft Store y pulse <b>Obtener</b> (o <b>Instalar</b>).',
        'Inicie el programa y abra un PDF, o arrástrelo a la ventana.',
        'Opcional: clic derecho en un PDF → <b>Abrir con</b> → <b>Elegir otra aplicación</b> → PDF Editor Pro → <b>Siempre</b>, para que sea su visor de PDF predeterminado.',
        'Cuando necesite edición ilimitada, pulse <b>Comprar</b> en el programa e introduzca su clave de licencia. Sin reinstalar.',
    ],
    cta_free='Descargar gratis de Microsoft Store',
    cta_buy='Versión completa — 9,99 $ una vez',
    s_faq='Preguntas frecuentes',
    faq=[
        ('¿PDF Editor Pro es realmente gratis?', 'Sí. Leer e imprimir PDF completos es gratis sin límite de tiempo, y puede probar todas las herramientas de edición en las 3 primeras páginas. Solo la edición ilimitada y el guardado sin marca de agua requieren la versión completa.'),
        ('¿Hay una versión completa gratis para descargar?', 'Legalmente no. Los sitios que ofrecen «versión completa gratis» o generadores de claves distribuyen archivos modificados. Use en su lugar la versión gratuita de Microsoft Store; funciona sin límite de tiempo.'),
        ('¿Por qué mi antivirus borra cracks y keygens?', 'Porque muchos contienen malware, y los que no se comportan igual: modifican archivos del programa y se ocultan del software de seguridad. Esa alerta no es un «falso positivo» que deba ignorar.'),
        ('¿Cuánto cuesta la versión completa?', '9,99 $ una vez para un PC, o 29,99 $ para 5 PC. Sin suscripción y con actualizaciones incluidas.'),
        ('¿Es segura la versión de Microsoft Store?', 'Sí. Microsoft revisa las aplicaciones de Microsoft Store antes de publicarlas, y las actualizaciones llegan automáticamente.'),
    ],
    back='← Inicio de PDF Editor Pro',
    other='Esta página en otros idiomas',
),
'fr': dict(
    title='Éditeur PDF crack ou version complète gratuite ? Une alternative gratuite et sûre (2026)',
    desc='Les éditeurs PDF crackés cachent souvent des malwares et des voleurs de mots de passe. PDF Editor Pro est gratuit sur le Microsoft Store : lisez et imprimez tout PDF, essayez tous les outils, version complète 9,99 $ une seule fois.',
    h1='Vous cherchez un éditeur PDF cracké ? Lisez ceci d\'abord',
    lead='« Éditeur PDF crack », « version complète gratuite » et « clé de licence » font partie des recherches les plus fréquentes pour les logiciels PDF. C\'est compréhensible : les éditeurs PDF connus coûtent un abonnement mensuel. Mais un crack coûte souvent plus qu\'il ne fait économiser. Voici les risques, et comment utiliser un éditeur PDF gratuitement, légalement et en toute sécurité.',
    toc='Sur cette page',
    s_risk='Ce qu\'un crack installe vraiment',
    risk=[
        '<b>Virus et chevaux de Troie.</b> Les cracks, keygens et « patchs » sont l\'un des moyens les plus courants de diffuser des malwares. Le fichier a été modifié par un inconnu et vous l\'exécutez avec les droits administrateur.',
        '<b>Vol de mots de passe et de données bancaires.</b> Beaucoup de cracks contiennent des « infostealers » qui copient les mots de passe enregistrés dans le navigateur, les cookies, les accès e-mail et bancaires, et les portefeuilles crypto.',
        '<b>Rançongiciel.</b> Certains installateurs infectés chiffrent vos documents et exigent une rançon.',
        '<b>« Désactivez d\'abord votre antivirus ».</b> Presque tous les cracks le demandent. Cela en dit long sur ce que l\'antivirus trouverait.',
        '<b>Aucune mise à jour.</b> Un logiciel cracké ne reçoit pas de correctifs de sécurité, et une mise à jour peut le casser à tout moment.',
        '<b>Risque juridique.</b> Utiliser un logiciel sans licence enfreint le droit d\'auteur. En entreprise, un audit logiciel peut entraîner des amendes.',
    ],
    s_free='La voie gratuite et légale : PDF Editor Pro',
    free_lead='PDF Editor Pro est un éditeur PDF pour Windows créé par MKBSoft et publié sur le Microsoft Store. La version gratuite n\'est pas un essai de 7 jours ; elle continue de fonctionner :',
    free=[
        '<b>Lisez et imprimez n\'importe quel PDF en entier, gratuitement et sans limite</b> : mode lecture, zoom, navigation par page, tous les réglages d\'impression.',
        'Utilisez-le comme <b>lecteur PDF par défaut</b> : un double-clic sur un PDF l\'ouvre en mode lecture.',
        '<b>Essayez tous les outils d\'édition</b> : modifier le texte, rechercher et remplacer, surligner, tampons, signatures, fusionner, scinder, compresser, convertir en Word/Excel/EPUB. Dans la version gratuite, l\'édition porte sur les 3 premières pages et les fichiers enregistrés reçoivent un filigrane.',
        'Installation depuis le <b>Microsoft Store</b> : vérifié par Microsoft, aucun avertissement à l\'installation, mises à jour automatiques.',
    ],
    s_cmp='Crack, version gratuite et version complète',
    cmp_head=['', 'Éditeur cracké', 'PDF Editor Pro (gratuit)', 'PDF Editor Pro (complet)'],
    cmp_rows=[
        ('Prix', 'Gratuit — payé avec vos données', 'Gratuit', '9,99 $ une fois, sans abonnement'),
        ('Risque de malware', 'Élevé', 'Aucun (Microsoft Store)', 'Aucun (Microsoft Store)'),
        ('Lecture et impression', 'Oui', 'Oui, documents entiers', 'Oui'),
        ('Édition', 'Oui', '3 premières pages, filigrane', 'Illimitée, sans filigrane'),
        ('Mises à jour', 'Non', 'Oui, automatiques', 'Oui, automatiques'),
        ('Légal', 'Non', 'Oui', 'Oui'),
    ],
    s_how='Installé en une minute',
    how=[
        'Ouvrez PDF Editor Pro sur le Microsoft Store et cliquez sur <b>Obtenir</b> (ou <b>Installer</b>).',
        'Lancez le programme et ouvrez un PDF, ou faites-le glisser dans la fenêtre.',
        'Facultatif : clic droit sur un PDF → <b>Ouvrir avec</b> → <b>Choisir une autre application</b> → PDF Editor Pro → <b>Toujours</b>, pour en faire votre lecteur PDF par défaut.',
        'Pour une édition illimitée, cliquez sur <b>Acheter</b> dans le programme et saisissez votre clé de licence. Pas de réinstallation.',
    ],
    cta_free='Télécharger gratuitement sur le Microsoft Store',
    cta_buy='Version complète — 9,99 $ une fois',
    s_faq='Questions fréquentes',
    faq=[
        ('PDF Editor Pro est-il vraiment gratuit ?', 'Oui. Lire et imprimer des PDF complets est gratuit sans limite de durée, et vous pouvez essayer tous les outils d\'édition sur les 3 premières pages. Seules l\'édition illimitée et l\'enregistrement sans filigrane nécessitent la version complète.'),
        ('Existe-t-il une version complète gratuite à télécharger ?', 'Pas légalement. Les sites qui proposent une « version complète gratuite » ou un générateur de clés diffusent des fichiers modifiés. Utilisez plutôt la version gratuite du Microsoft Store ; elle fonctionne sans limite de durée.'),
        ('Pourquoi mon antivirus supprime-t-il les cracks et keygens ?', 'Parce que beaucoup contiennent des malwares, et que les autres se comportent de la même façon : ils modifient les fichiers du programme et se cachent des logiciels de sécurité. Cette alerte n\'est pas un « faux positif » à ignorer.'),
        ('Combien coûte la version complète ?', '9,99 $ une fois pour un PC, ou 29,99 $ pour 5 PC. Sans abonnement, mises à jour incluses.'),
        ('La version du Microsoft Store est-elle sûre ?', 'Oui. Les applications du Microsoft Store sont vérifiées par Microsoft avant leur publication, et les mises à jour arrivent automatiquement.'),
    ],
    back='← Accueil PDF Editor Pro',
    other='Cette page dans d\'autres langues',
),
'it': dict(
    title='Editor PDF crack o versione completa gratis? Un\'alternativa gratuita e sicura (2026)',
    desc='Gli editor PDF crackati spesso nascondono malware e ladri di password. PDF Editor Pro è gratis sul Microsoft Store: leggi e stampa qualsiasi PDF, prova tutti gli strumenti, versione completa 9,99 $ una tantum.',
    h1='Cerchi un editor PDF crackato? Leggi prima questo',
    lead='«Editor PDF crack», «versione completa gratis» e «chiave di licenza» sono tra le ricerche più comuni per i programmi PDF. È comprensibile: gli editor PDF più noti costano un abbonamento mensile. Ma un crack di solito costa più di quanto fa risparmiare. Ecco quali sono i rischi e come usare un editor PDF gratis, in modo legale e sicuro.',
    toc='In questa pagina',
    s_risk='Cosa installa davvero un crack',
    risk=[
        '<b>Virus e trojan.</b> Crack, keygen e «patch» sono tra i canali più comuni di diffusione del malware. Il file è stato modificato da uno sconosciuto e lo esegui con i diritti di amministratore.',
        '<b>Furto di password e dati bancari.</b> Molti crack contengono «infostealer» che copiano le password salvate nel browser, i cookie, gli accessi alla posta e alla banca, e i portafogli di criptovalute.',
        '<b>Ransomware.</b> Alcuni installer infetti cifrano i tuoi documenti e chiedono un riscatto.',
        '<b>«Prima disattiva l\'antivirus».</b> Quasi ogni crack lo chiede. Già questo dice cosa troverebbe l\'antivirus.',
        '<b>Nessun aggiornamento.</b> Un programma crackato non riceve patch di sicurezza e un aggiornamento può romperlo in qualsiasi momento.',
        '<b>Rischio legale.</b> Usare software senza licenza viola la legge sul diritto d\'autore. Nelle aziende, un controllo del software può portare a sanzioni.',
    ],
    s_free='La via gratuita e legale: PDF Editor Pro',
    free_lead='PDF Editor Pro è un editor PDF per Windows di MKBSoft, pubblicato sul Microsoft Store. La versione gratuita non è una prova di 7 giorni; continua a funzionare:',
    free=[
        '<b>Leggi e stampa qualsiasi PDF per intero, gratis e per sempre</b>: modalità lettura, zoom, navigazione tra le pagine, tutte le impostazioni della stampante.',
        'Usalo come <b>visualizzatore PDF predefinito</b>: con un doppio clic il PDF si apre in modalità lettura.',
        '<b>Prova tutti gli strumenti di modifica</b>: modifica del testo, trova e sostituisci, evidenziazione, timbri, firme, unione, divisione, compressione, conversione in Word/Excel/EPUB. Nella versione gratuita la modifica riguarda le prime 3 pagine e i file salvati hanno una filigrana.',
        'Si installa dal <b>Microsoft Store</b>: verificato da Microsoft, nessun avviso in fase di installazione, aggiornamenti automatici.',
    ],
    s_cmp='Crack, versione gratuita e versione completa',
    cmp_head=['', 'Editor crackato', 'PDF Editor Pro (gratis)', 'PDF Editor Pro (completo)'],
    cmp_rows=[
        ('Prezzo', 'Gratis — lo paghi con i tuoi dati', 'Gratis', '9,99 $ una tantum, nessun abbonamento'),
        ('Rischio malware', 'Alto', 'Nessuno (Microsoft Store)', 'Nessuno (Microsoft Store)'),
        ('Lettura e stampa', 'Sì', 'Sì, documenti interi', 'Sì'),
        ('Modifica', 'Sì', 'Prime 3 pagine, filigrana', 'Illimitata, senza filigrana'),
        ('Aggiornamenti', 'No', 'Sì, automatici', 'Sì, automatici'),
        ('Legale', 'No', 'Sì', 'Sì'),
    ],
    s_how='Installalo in un minuto',
    how=[
        'Apri PDF Editor Pro sul Microsoft Store e fai clic su <b>Ottieni</b> (o <b>Installa</b>).',
        'Avvia il programma e apri un PDF, oppure trascinalo nella finestra.',
        'Facoltativo: clic destro su un PDF → <b>Apri con</b> → <b>Scegli un\'altra app</b> → PDF Editor Pro → <b>Sempre</b>, per renderlo il visualizzatore PDF predefinito.',
        'Quando ti serve la modifica illimitata, fai clic su <b>Acquista</b> nel programma e inserisci la chiave di licenza. Nessuna reinstallazione.',
    ],
    cta_free='Scarica gratis dal Microsoft Store',
    cta_buy='Versione completa — 9,99 $ una tantum',
    s_faq='Domande frequenti',
    faq=[
        ('PDF Editor Pro è davvero gratis?', 'Sì. Leggere e stampare PDF completi è gratis senza limiti di tempo, e puoi provare tutti gli strumenti di modifica sulle prime 3 pagine. Solo la modifica illimitata e il salvataggio senza filigrana richiedono la versione completa.'),
        ('Esiste una versione completa gratis da scaricare?', 'Legalmente no. I siti che offrono la «versione completa gratis» o generatori di chiavi distribuiscono file modificati. Usa invece la versione gratuita del Microsoft Store; funziona senza limiti di tempo.'),
        ('Perché il mio antivirus elimina crack e keygen?', 'Perché molti contengono malware, e quelli che non lo contengono si comportano allo stesso modo: modificano i file del programma e si nascondono al software di sicurezza. Quell\'avviso non è un «falso positivo» da ignorare.'),
        ('Quanto costa la versione completa?', '9,99 $ una tantum per un PC, oppure 29,99 $ per 5 PC. Nessun abbonamento, aggiornamenti inclusi.'),
        ('La versione del Microsoft Store è sicura?', 'Sì. Le app del Microsoft Store vengono verificate da Microsoft prima della pubblicazione e gli aggiornamenti arrivano automaticamente.'),
    ],
    back='← Home di PDF Editor Pro',
    other='Questa pagina in altre lingue',
),
'pt': dict(
    title='Editor de PDF crack ou versão completa grátis? Uma alternativa gratuita e segura (2026)',
    desc='Editores de PDF crackeados costumam esconder malware e ladrões de senhas. O PDF Editor Pro é grátis na Microsoft Store: leia e imprima qualquer PDF, teste todas as ferramentas e libere a versão completa por US$ 9,99 uma única vez.',
    h1='Procurando um editor de PDF crackeado? Leia isto antes',
    lead='"Editor de PDF crack", "versão completa grátis" e "chave de licença" estão entre as buscas mais comuns por programas de PDF. É compreensível: os editores de PDF mais conhecidos cobram assinatura mensal. Mas um crack costuma custar mais do que economiza. Veja quais são os riscos e como usar um editor de PDF de graça, de forma legal e segura.',
    toc='Nesta página',
    s_risk='O que um crack realmente instala',
    risk=[
        '<b>Vírus e cavalos de Troia.</b> Cracks, keygens e "patches" são um dos meios mais comuns de espalhar malware. O arquivo foi modificado por um desconhecido e você o executa com permissão de administrador.',
        '<b>Roubo de senhas e dados bancários.</b> Muitos cracks trazem "infostealers" que copiam senhas salvas no navegador, cookies, acessos de e-mail e banco, e carteiras de criptomoedas.',
        '<b>Ransomware.</b> Alguns instaladores infectados criptografam seus documentos e pedem resgate.',
        '<b>"Desative o antivírus primeiro".</b> Quase todo crack pede isso. Só isso já mostra o que o antivírus encontraria.',
        '<b>Sem atualizações.</b> Um programa crackeado não recebe correções de segurança, e uma atualização pode quebrá-lo a qualquer momento.',
        '<b>Risco jurídico.</b> Usar software sem licença viola a lei de direitos autorais. Em empresas, uma auditoria de software pode resultar em multas.',
    ],
    s_free='O caminho gratuito e legal: PDF Editor Pro',
    free_lead='O PDF Editor Pro é um editor de PDF para Windows da MKBSoft, publicado na Microsoft Store. A versão gratuita não é um teste de 7 dias; ela continua funcionando:',
    free=[
        '<b>Leia e imprima qualquer PDF inteiro, de graça e para sempre</b>: modo de leitura, zoom, navegação entre páginas, todas as configurações da impressora.',
        'Use como <b>visualizador de PDF padrão</b>: clique duas vezes em um PDF e ele abre no modo de leitura.',
        '<b>Teste todas as ferramentas de edição</b>: editar texto, localizar e substituir, destacar, carimbos, assinaturas, juntar, dividir, compactar, converter para Word/Excel/EPUB. Na versão gratuita a edição funciona nas 3 primeiras páginas e os arquivos salvos recebem marca d\'água.',
        'Instalado pela <b>Microsoft Store</b>: verificado pela Microsoft, sem avisos de instalação, atualizações automáticas.',
    ],
    s_cmp='Crack, versão gratuita e versão completa',
    cmp_head=['', 'Editor crackeado', 'PDF Editor Pro (grátis)', 'PDF Editor Pro (completo)'],
    cmp_rows=[
        ('Preço', 'Grátis — pago com seus dados', 'Grátis', 'US$ 9,99 uma vez, sem assinatura'),
        ('Risco de malware', 'Alto', 'Nenhum (Microsoft Store)', 'Nenhum (Microsoft Store)'),
        ('Ler e imprimir', 'Sim', 'Sim, documentos inteiros', 'Sim'),
        ('Edição', 'Sim', '3 primeiras páginas, marca d\'água', 'Ilimitada, sem marca d\'água'),
        ('Atualizações', 'Não', 'Sim, automáticas', 'Sim, automáticas'),
        ('Legal', 'Não', 'Sim', 'Sim'),
    ],
    s_how='Instale em um minuto',
    how=[
        'Abra o PDF Editor Pro na Microsoft Store e clique em <b>Obter</b> (ou <b>Instalar</b>).',
        'Inicie o programa e abra um PDF, ou arraste-o para a janela.',
        'Opcional: clique com o botão direito em um PDF → <b>Abrir com</b> → <b>Escolher outro aplicativo</b> → PDF Editor Pro → <b>Sempre</b>, para torná-lo seu visualizador de PDF padrão.',
        'Quando precisar de edição ilimitada, clique em <b>Comprar</b> no programa e digite sua chave de licença. Sem reinstalar.',
    ],
    cta_free='Baixar grátis na Microsoft Store',
    cta_buy='Versão completa — US$ 9,99 uma vez',
    s_faq='Perguntas frequentes',
    faq=[
        ('O PDF Editor Pro é mesmo grátis?', 'Sim. Ler e imprimir PDFs completos é grátis, sem limite de tempo, e você pode testar todas as ferramentas de edição nas 3 primeiras páginas. Só a edição ilimitada e salvar sem marca d\'água exigem a versão completa.'),
        ('Existe versão completa grátis para baixar?', 'Legalmente, não. Sites que oferecem "versão completa grátis" ou geradores de chave distribuem arquivos modificados. Use a versão gratuita da Microsoft Store; ela funciona sem limite de tempo.'),
        ('Por que meu antivírus apaga cracks e keygens?', 'Porque muitos contêm malware, e os que não contêm se comportam da mesma forma: modificam arquivos do programa e se escondem do software de segurança. Esse alerta não é um "falso positivo" para ignorar.'),
        ('Quanto custa a versão completa?', 'US$ 9,99 uma vez para um PC, ou US$ 29,99 para 5 PCs. Sem assinatura, com atualizações incluídas.'),
        ('A versão da Microsoft Store é segura?', 'Sim. Os aplicativos da Microsoft Store são verificados pela Microsoft antes de serem publicados, e as atualizações chegam automaticamente.'),
    ],
    back='← Início do PDF Editor Pro',
    other='Esta página em outros idiomas',
),
'ru': dict(
    title='PDF-редактор: кряк или полная версия бесплатно? Бесплатная и безопасная альтернатива (2026)',
    desc='Взломанные PDF-редакторы часто содержат вирусы и программы для кражи паролей. PDF Editor Pro бесплатен в Microsoft Store: читайте и печатайте любые PDF, пробуйте все инструменты, полная версия — 9,99 $ один раз.',
    h1='Ищете взломанный PDF-редактор? Сначала прочитайте это',
    lead='«PDF редактор кряк», «полная версия бесплатно» и «ключ активации» — одни из самых частых запросов о PDF-программах. Это понятно: известные PDF-редакторы требуют ежемесячную подписку. Но кряк обычно обходится дороже, чем экономит. Здесь описаны риски и то, как пользоваться PDF-редактором бесплатно, легально и безопасно.',
    toc='На этой странице',
    s_risk='Что на самом деле устанавливает кряк',
    risk=[
        '<b>Вирусы и трояны.</b> Кряки, кейгены и «патчи» — один из самых распространённых способов заражения. Файл изменён неизвестным человеком, а вы запускаете его с правами администратора.',
        '<b>Кража паролей и банковских данных.</b> Многие кряки содержат «инфостилеры», которые копируют сохранённые в браузере пароли, cookie, доступ к почте и онлайн-банку, криптокошельки.',
        '<b>Программы-вымогатели.</b> Некоторые заражённые установщики шифруют ваши документы и требуют выкуп.',
        '<b>«Сначала отключите антивирус».</b> Этого требует почти любой кряк. Уже это говорит о том, что нашёл бы антивирус.',
        '<b>Нет обновлений.</b> Взломанная программа не получает исправлений безопасности, а любое обновление может её сломать.',
        '<b>Юридический риск.</b> Использование нелицензионных программ нарушает авторское право. Для компаний проверка ПО может закончиться штрафом.',
    ],
    s_free='Бесплатный и легальный путь: PDF Editor Pro',
    free_lead='PDF Editor Pro — PDF-редактор для Windows от MKBSoft, опубликованный в Microsoft Store. Бесплатная версия — не пробный период на 7 дней, она работает постоянно:',
    free=[
        '<b>Читайте и печатайте любой PDF целиком — бесплатно и без ограничения срока</b>: режим чтения, масштаб, переход по страницам, все настройки принтера.',
        'Сделайте его <b>программой для PDF по умолчанию</b>: двойной щелчок по PDF открывает его в режиме чтения.',
        '<b>Попробуйте все инструменты редактирования</b>: правка текста, поиск и замена, выделение, штампы, подписи, объединение, разделение, сжатие, конвертация в Word/Excel/EPUB. В бесплатной версии редактировать можно первые 3 страницы, а на сохранённые файлы добавляется водяной знак.',
        'Устанавливается из <b>Microsoft Store</b>: проверено Microsoft, без предупреждений при установке, автоматические обновления.',
    ],
    s_cmp='Кряк, бесплатная и полная версия',
    cmp_head=['', 'Взломанный редактор', 'PDF Editor Pro (бесплатно)', 'PDF Editor Pro (полная)'],
    cmp_rows=[
        ('Цена', 'Бесплатно — платите своими данными', 'Бесплатно', '9,99 $ один раз, без подписки'),
        ('Риск заражения', 'Высокий', 'Нет (Microsoft Store)', 'Нет (Microsoft Store)'),
        ('Чтение и печать', 'Да', 'Да, документ целиком', 'Да'),
        ('Редактирование', 'Да', 'Первые 3 страницы, водяной знак', 'Без ограничений, без водяного знака'),
        ('Обновления', 'Нет', 'Да, автоматически', 'Да, автоматически'),
        ('Легально', 'Нет', 'Да', 'Да'),
    ],
    s_how='Установка за минуту',
    how=[
        'Откройте PDF Editor Pro в Microsoft Store и нажмите <b>Получить</b> (или <b>Установить</b>).',
        'Запустите программу и откройте PDF или перетащите его в окно.',
        'По желанию: щёлкните правой кнопкой по PDF → <b>Открыть с помощью</b> → <b>Выбрать другое приложение</b> → PDF Editor Pro → <b>Всегда</b>, чтобы сделать его программой для PDF по умолчанию.',
        'Когда понадобится редактирование без ограничений, нажмите в программе <b>Купить</b> и введите лицензионный ключ. Переустановка не нужна.',
    ],
    cta_free='Скачать бесплатно в Microsoft Store',
    cta_buy='Полная версия — 9,99 $ один раз',
    s_faq='Частые вопросы',
    faq=[
        ('PDF Editor Pro действительно бесплатный?', 'Да. Чтение и печать PDF целиком бесплатны без ограничения срока, а все инструменты редактирования можно попробовать на первых 3 страницах. Полная версия нужна только для редактирования без ограничений и сохранения без водяного знака.'),
        ('Можно ли скачать полную версию бесплатно?', 'Легально — нет. Сайты, предлагающие «полную версию бесплатно» или генераторы ключей, распространяют изменённые файлы. Используйте бесплатную версию из Microsoft Store — она работает без ограничения срока.'),
        ('Почему антивирус удаляет кряки и кейгены?', 'Потому что многие из них содержат вредоносный код, а остальные ведут себя так же: изменяют файлы программы и прячутся от защитного ПО. Такое предупреждение — не «ложное срабатывание», которое можно игнорировать.'),
        ('Сколько стоит полная версия?', '9,99 $ один раз за один ПК или 29,99 $ за 5 ПК. Без подписки, обновления включены.'),
        ('Безопасна ли версия из Microsoft Store?', 'Да. Приложения в Microsoft Store проверяются Microsoft перед публикацией, а обновления приходят автоматически.'),
    ],
    back='← Главная PDF Editor Pro',
    other='Эта страница на других языках',
),
}

EXTRA_CSS = '''
.risk li { padding: 0 0 12px 0; }
.risk { list-style: none; }
.risk li::before { content: "⚠️ "; }
.free { list-style: none; }
.free li { padding: 0 0 10px 0; }
.free li::before { content: "✅ "; }
.tbl { width: 100%; overflow-x: auto; margin-top: 8px; }
table { width: 100%; border-collapse: collapse; font-size: 15px; min-width: 560px; }
th, td { border: 1px solid var(--border); padding: 9px 12px; text-align: left; vertical-align: top; }
thead th { background: var(--bg2); }
td.bad { color: #b91c1c; } td.good { color: #047857; font-weight: 600; }
.hero-cta { display: flex; gap: 10px; flex-wrap: wrap; margin: 0 0 28px; }
'''


def build(lang):
    t = T[lang]
    slug = SLUGS[lang]
    url = SITE + slug
    e = html.escape
    alt = ''.join(f'<link rel="alternate" hreflang="{l}" href="{SITE}{s}">\n' for l, s in SLUGS.items())
    alt += f'<link rel="alternate" hreflang="x-default" href="{SITE}{SLUGS["en"]}">\n'
    faq_ld = {'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
        {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in t['faq']]}
    app_ld = {'@context': 'https://schema.org', '@type': 'SoftwareApplication', 'name': 'PDF Editor Pro',
              'operatingSystem': 'Windows 10, Windows 11', 'applicationCategory': 'BusinessApplication',
              'downloadUrl': STORE, 'publisher': {'@type': 'Organization', 'name': 'MKBSoft'},
              'offers': [{'@type': 'Offer', 'price': '0', 'priceCurrency': 'USD'},
                         {'@type': 'Offer', 'price': '9.99', 'priceCurrency': 'USD'}]}
    others = ''.join(f'<li><a href="{SLUGS[l]}" hreflang="{l}">{NAMES[l]}</a></li>' for l in SLUGS if l != lang)
    toc = ''.join(f'<li><a href="#{a}">{e(t[k])}</a></li>' for a, k in
                  (('risk', 's_risk'), ('free', 's_free'), ('compare', 's_cmp'), ('how', 's_how'), ('faq', 's_faq')))
    faq = ''.join(f'<details><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q, a in t['faq'])
    head = ''.join(f'<th>{h}</th>' for h in t['cmp_head'])
    rows = ''.join(f'<tr><th>{r[0]}</th><td class="bad">{r[1]}</td><td class="good">{r[2]}</td><td class="good">{r[3]}</td></tr>'
                   for r in t['cmp_rows'])
    cta = (f'<a class="btn btn-primary" href="{STORE}">{e(t["cta_free"])}</a>'
           f'<a class="btn btn-ghost" href="{BUY}">{e(t["cta_buy"])}</a>')
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
<meta property="og:image" content="{SITE}/img/shots/{lang}_01_main.webp">
<meta property="og:locale" content="{OG_LOCALE[lang]}">
<meta property="og:site_name" content="PDF Editor Pro by MKBSoft">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<script type="application/ld+json">{json.dumps(faq_ld, ensure_ascii=False)}</script>
<script type="application/ld+json">{json.dumps(app_ld, ensure_ascii=False)}</script>
<style>{CSS}{EXTRA_CSS}</style>
</head>
<body>
<header><div class="bar">
  <a class="logo" href="/"><img src="/img/app-icon.png" alt="" width="30" height="30">PDF Editor Pro</a>
  <a class="btn btn-primary" href="{STORE}">{e(t['cta_free'])}</a>
</div></header>
<main>
  <div class="crumb"><a href="/">{e(t['back'])}</a></div>
  <h1>{e(t['h1'])}</h1>
  <p class="lead">{e(t['lead'])}</p>
  <div class="hero-cta">{cta}</div>
  <nav class="toc" aria-label="{e(t['toc'])}"><b>{e(t['toc'])}</b><ol>{toc}</ol></nav>

  <h2 id="risk">{e(t['s_risk'])}</h2>
  <ul class="risk">{li(t['risk'])}</ul>

  <section class="app" id="free">
    <h2>{e(t['s_free'])}</h2>
    <p>{e(t['free_lead'])}</p><br>
    <ul class="free">{li(t['free'])}</ul>
    <div class="compare"><figure><img src="/img/shots/{lang}_01_main.webp" alt="PDF Editor Pro" loading="lazy" style="max-width:100%"></figure></div>
  </section>

  <h2 id="compare">{e(t['s_cmp'])}</h2>
  <div class="tbl"><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>

  <h2 id="how">{e(t['s_how'])}</h2>
  <ol class="steps">{li(t['how'])}</ol>
  <div class="cta">{cta}</div>

  <h2 id="faq">{e(t['s_faq'])}</h2>
  <div class="faq">{faq}</div>

  <div class="langs"><b>{e(t['other'])}</b><ul>{others}</ul></div>
</main>
<footer>© 2026 MKBSoft · <a href="/">mkbsoft.net</a> · <a href="mailto:destek@mkbsoft.net">destek@mkbsoft.net</a></footer>
</body>
</html>
'''


if __name__ == '__main__':
    keys = set(T['en'])
    for lang in SLUGS:
        missing = keys - set(T[lang])
        assert not missing, (lang, missing)
        assert len(T[lang]['faq']) == len(T['en']['faq']), lang
        assert len(T[lang]['cmp_rows']) == len(T['en']['cmp_rows']), lang
        d = os.path.join(WEB, SLUGS[lang].strip('/').replace('/', os.sep))
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, 'index.html'), 'w', encoding='utf-8', newline='\n').write(build(lang))
        print('wrote', SLUGS[lang])
    write_sitemap()
    print('sitemap updated')
