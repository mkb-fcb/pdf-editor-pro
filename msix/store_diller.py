"""Partner Center listing texts for DE, ES, FR, IT, PT-BR and RU.

    python msix/store_diller.py 19 80     # individual / corporate price in USD
writes msix/store_metinleri_diller.txt (EN and TR stay in store_metinleri.txt).
"""
import os
import sys

IND, CORP = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ('19', '80')

L = {
 'de': dict(
  title='GERMAN — Deutsch (Deutschland)',
  desc='''PDF Editor Pro ist ein schneller, schlanker PDF-Editor für Windows. Alles läuft lokal auf Ihrem PC — Ihre Dokumente werden nie in die Cloud hochgeladen.

BEARBEITEN
• Vorhandenen Text direkt auf der Seite bearbeiten, verschieben und löschen
• Neuen Text, Bilder, Rechtecke und Kreise hinzufügen
• Inhalte markieren, Stempel und Wasserzeichen hinzufügen
• Ausgewählte Bereiche schwärzen — der darunterliegende Text wird dauerhaft entfernt

ORGANISIEREN
• Mehrere PDFs zu einem zusammenführen
• Nach Seitenbereich teilen oder Seiten extrahieren
• Seiten in der Miniaturansicht drehen, sortieren, einfügen und löschen; mehrere Seiten auf einmal löschen

KONVERTIEREN & SCHÜTZEN
• Export nach Word (DOCX), Excel, PowerPoint, Bildern, Text und E-Book (EPUB) — und an den Kindle senden
• PDFs mit wählbarer Qualität verkleinern und per E-Mail, WhatsApp, Teams und mehr teilen
• Passwortschutz hinzufügen oder entfernen

Oberfläche in 8 Sprachen: Deutsch, Englisch, Türkisch, Französisch, Spanisch, Italienisch, Portugiesisch und Russisch.

KOSTENLOSE DEMO & VOLLVERSION
Ohne Lizenz läuft die App als kostenlose Demo: Dokumente bis 3 Seiten, gespeicherte Dateien mit „DEMO“-Wasserzeichen; Passwortschutz sowie Export nach Word/Excel/PowerPoint/JPG/EPUB sind deaktiviert. Für die Vollversion kaufen Sie einen Lizenzschlüssel auf https://mkbsoft.net und geben ihn über „Lizenz eingeben“ ein. Einzelplatzlizenz: ${IND} einmalig für 1 PC. Unternehmenslizenz: ${CORP} einmalig für bis zu 5 PCs. Kein Abo.''',
  new='''• PDF zu E-Book: PDFs in EPUB umwandeln — mit umfließendem Text, Überschriften, Kapiteln, Bildern, Diagrammen und Tabellen.
• An Kindle senden: direkt auf einen per USB verbundenen Kindle kopieren oder per E-Mail-Programm bzw. Amazon-Webseite senden.
• AZW3-Export für Kindle, wenn das kostenlose Calibre installiert ist.
• Lizenzaktivierung in Ihrer Sprache, mit direktem Kauflink.
• Suchen & Ersetzen behält Schriftart, Stärke, Größe und Farbe bei.
• Dateinamen gespeicherter Dateien in der gewählten Sprache.''',
  feat=['Vorhandenen Text direkt auf der PDF-Seite bearbeiten', 'Seiten zusammenführen, teilen, drehen und sortieren',
        'Text, Bilder, Formen, Markierungen, Stempel und Wasserzeichen hinzufügen', 'PDF nach Word, Excel, PowerPoint, Bilder oder Text exportieren',
        'PDF zu E-Book (EPUB) und an Kindle senden', 'PDFs verkleinern und per E-Mail oder WhatsApp teilen',
        'Passwortschutz hinzufügen oder entfernen', 'Funktioniert offline — Dateien verlassen nie Ihren PC'],
  short='PDFs unter Windows bearbeiten, zusammenführen, teilen, verkleinern und schützen — offline. Kostenlose Demo; Vollversion mit einmaliger Lizenz, kein Abo.',
  terms=['PDF Editor', 'PDF bearbeiten', 'PDF zusammenführen', 'PDF teilen', 'PDF verkleinern', 'PDF zu EPUB', 'PDF Kindle']),
 'es': dict(
  title='SPANISH — Español (España)',
  desc='''PDF Editor Pro es un editor de PDF rápido y ligero para Windows. Todo funciona en tu PC: tus documentos nunca se suben a la nube.

EDITAR
• Edita, mueve y elimina el texto existente directamente en la página
• Añade texto nuevo, imágenes, rectángulos y círculos
• Resalta contenido y añade sellos y marcas de agua
• Borra zonas seleccionadas: el texto subyacente se elimina de forma permanente

ORGANIZAR
• Une varios PDF en uno
• Divide por rango de páginas o extrae páginas
• Gira, reordena, inserta y elimina páginas con vista de miniaturas; elimina varias a la vez

CONVERTIR Y PROTEGER
• Exporta a Word (DOCX), Excel, PowerPoint, imágenes, texto y libro electrónico (EPUB), y envía a Kindle
• Reduce PDF con la calidad que elijas y compártelos por correo, WhatsApp, Teams y más
• Añade o quita la protección con contraseña

Interfaz en 8 idiomas: español, inglés, turco, alemán, francés, italiano, portugués y ruso.

DEMO GRATUITA Y VERSIÓN COMPLETA
Sin licencia, la app funciona como demo gratuita: documentos de hasta 3 páginas, archivos guardados con marca de agua «DEMO» y sin protección con contraseña ni exportación a Word/Excel/PowerPoint/JPG/EPUB. Para la versión completa, compra una clave de licencia en https://mkbsoft.net e introdúcela con el botón «Introducir licencia». Licencia individual: ${IND} pago único para 1 PC. Licencia empresa: ${CORP} pago único para hasta 5 PC. Sin suscripción.''',
  new='''• PDF a libro electrónico: convierte PDF a EPUB con texto adaptable, títulos, capítulos, imágenes, gráficos y tablas.
• Enviar a Kindle: copia directamente a un Kindle conectado por USB o envía el libro con tu programa de correo o la web de Amazon.
• Exportación AZW3 para Kindle si está instalado el programa gratuito Calibre.
• Pantalla de activación de licencia en tu idioma, con enlace de compra directo.
• Buscar y reemplazar conserva la fuente, el grosor, el tamaño y el color originales.
• Nombres de archivo guardados en el idioma elegido.''',
  feat=['Edita el texto existente directamente en la página', 'Une, divide, gira y reordena páginas',
        'Añade texto, imágenes, formas, resaltados, sellos y marcas de agua', 'Exporta PDF a Word, Excel, PowerPoint, imágenes o texto',
        'PDF a libro electrónico (EPUB) y envío a Kindle', 'Reduce PDF y compártelos por correo o WhatsApp',
        'Añade o quita contraseñas', 'Funciona sin conexión: los archivos no salen de tu PC'],
  short='Edita, une, divide, reduce y protege PDF en Windows, sin conexión. Demo gratuita incluida; versión completa con licencia de pago único, sin suscripción.',
  terms=['editor PDF', 'editar PDF', 'unir PDF', 'dividir PDF', 'comprimir PDF', 'PDF a EPUB', 'PDF Kindle']),
 'fr': dict(
  title='FRENCH — Français (France)',
  desc='''PDF Editor Pro est un éditeur PDF rapide et léger pour Windows. Tout fonctionne en local sur votre PC : vos documents ne sont jamais envoyés dans le cloud.

MODIFIER
• Modifiez, déplacez et supprimez le texte existant directement sur la page
• Ajoutez du texte, des images, des rectangles et des cercles
• Surlignez, ajoutez des tampons et des filigranes
• Effacez des zones sélectionnées : le texte sous-jacent est définitivement supprimé

ORGANISER
• Fusionnez plusieurs PDF en un seul
• Divisez par plage de pages ou extrayez des pages
• Pivotez, réorganisez, insérez et supprimez des pages en vignettes ; supprimez-en plusieurs d’un coup

CONVERTIR ET PROTÉGER
• Export vers Word (DOCX), Excel, PowerPoint, images, texte et livre numérique (EPUB) — et envoi au Kindle
• Réduisez vos PDF avec la qualité de votre choix et partagez-les par e-mail, WhatsApp, Teams et plus
• Ajoutez ou retirez une protection par mot de passe

Interface en 8 langues : français, anglais, turc, allemand, espagnol, italien, portugais et russe.

DÉMO GRATUITE ET VERSION COMPLÈTE
Sans licence, l’application fonctionne en démo gratuite : documents de 3 pages maximum, fichiers enregistrés avec un filigrane « DEMO », protection par mot de passe et export Word/Excel/PowerPoint/JPG/EPUB désactivés. Pour la version complète, achetez une clé de licence sur https://mkbsoft.net et saisissez-la via le bouton « Saisir la licence ». Licence individuelle : ${IND} en paiement unique pour 1 PC. Licence entreprise : ${CORP} en paiement unique pour 5 PC maximum. Sans abonnement.''',
  new='''• PDF en livre numérique : convertissez vos PDF en EPUB avec texte adaptable, titres, chapitres, images, graphiques et tableaux.
• Envoyer au Kindle : copie directe sur un Kindle branché en USB, ou envoi par votre messagerie ou le site d’Amazon.
• Export AZW3 pour Kindle lorsque le logiciel gratuit Calibre est installé.
• Écran d’activation de la licence dans votre langue, avec lien d’achat direct.
• Rechercher et remplacer conserve la police, la graisse, la taille et la couleur d’origine.
• Noms des fichiers enregistrés dans la langue choisie.''',
  feat=['Modifiez le texte existant directement sur la page', 'Fusionnez, divisez, pivotez et réorganisez les pages',
        'Ajoutez texte, images, formes, surlignages, tampons et filigranes', 'Exportez vers Word, Excel, PowerPoint, images ou texte',
        'PDF en livre numérique (EPUB) et envoi au Kindle', 'Réduisez vos PDF et partagez-les par e-mail ou WhatsApp',
        'Ajoutez ou retirez un mot de passe', 'Fonctionne hors ligne : vos fichiers restent sur votre PC'],
  short='Modifiez, fusionnez, divisez, réduisez et protégez vos PDF sous Windows, hors ligne. Démo gratuite ; version complète avec licence unique, sans abonnement.',
  terms=['éditeur PDF', 'modifier PDF', 'fusionner PDF', 'diviser PDF', 'compresser PDF', 'PDF en EPUB', 'PDF Kindle']),
 'it': dict(
  title='ITALIAN — Italiano (Italia)',
  desc='''PDF Editor Pro è un editor PDF veloce e leggero per Windows. Tutto funziona in locale sul tuo PC: i tuoi documenti non vengono mai caricati nel cloud.

MODIFICA
• Modifica, sposta ed elimina il testo esistente direttamente sulla pagina
• Aggiungi nuovo testo, immagini, rettangoli e cerchi
• Evidenzia contenuti, aggiungi timbri e filigrane
• Cancella aree selezionate: il testo sottostante viene rimosso definitivamente

ORGANIZZA
• Unisci più PDF in uno solo
• Dividi per intervallo di pagine o estrai pagine
• Ruota, riordina, inserisci ed elimina pagine nella vista miniature; eliminane più di una insieme

CONVERTI E PROTEGGI
• Esporta in Word (DOCX), Excel, PowerPoint, immagini, testo ed e-book (EPUB) e invia a Kindle
• Riduci i PDF con la qualità che preferisci e condividili via e-mail, WhatsApp, Teams e altro
• Aggiungi o rimuovi la protezione con password

Interfaccia in 8 lingue: italiano, inglese, turco, tedesco, francese, spagnolo, portoghese e russo.

DEMO GRATUITA E VERSIONE COMPLETA
Senza licenza l’app funziona come demo gratuita: documenti fino a 3 pagine, file salvati con filigrana «DEMO», protezione con password ed esportazione in Word/Excel/PowerPoint/JPG/EPUB disattivate. Per la versione completa acquista una chiave di licenza su https://mkbsoft.net e inseriscila con il pulsante «Inserisci licenza». Licenza singola: ${IND} una tantum per 1 PC. Licenza aziendale: ${CORP} una tantum per un massimo di 5 PC. Nessun abbonamento.''',
  new='''• Da PDF a e-book: converti i PDF in EPUB con testo adattabile, titoli, capitoli, immagini, grafici e tabelle.
• Invia a Kindle: copia direttamente su un Kindle collegato via USB, oppure invia l’e-book con il programma di posta o il sito di Amazon.
• Esportazione AZW3 per Kindle se è installato il programma gratuito Calibre.
• Schermata di attivazione della licenza nella tua lingua, con link d’acquisto diretto.
• Trova e sostituisci mantiene carattere, spessore, dimensione e colore originali.
• Nomi dei file salvati nella lingua scelta.''',
  feat=['Modifica il testo esistente direttamente sulla pagina', 'Unisci, dividi, ruota e riordina le pagine',
        'Aggiungi testo, immagini, forme, evidenziazioni, timbri e filigrane', 'Esporta PDF in Word, Excel, PowerPoint, immagini o testo',
        'Da PDF a e-book (EPUB) e invio a Kindle', 'Riduci i PDF e condividili via e-mail o WhatsApp',
        'Aggiungi o rimuovi la password', 'Funziona offline: i file non lasciano il tuo PC'],
  short='Modifica, unisci, dividi, riduci e proteggi i PDF su Windows, offline. Demo gratuita inclusa; versione completa con licenza una tantum, senza abbonamento.',
  terms=['editor PDF', 'modificare PDF', 'unire PDF', 'dividere PDF', 'comprimere PDF', 'PDF in EPUB', 'PDF Kindle']),
 'pt': dict(
  title='PORTUGUESE — Português (Brasil)',
  desc='''O PDF Editor Pro é um editor de PDF rápido e leve para Windows. Tudo roda localmente no seu PC — seus documentos nunca são enviados para a nuvem.

EDITAR
• Edite, mova e exclua o texto existente direto na página
• Adicione novo texto, imagens, retângulos e círculos
• Destaque conteúdo, adicione carimbos e marcas d’água
• Apague áreas selecionadas — o texto por baixo é removido de forma permanente

ORGANIZAR
• Una vários PDFs em um só
• Divida por intervalo de páginas ou extraia páginas
• Gire, reordene, insira e exclua páginas na visualização em miniaturas; exclua várias de uma vez

CONVERTER E PROTEGER
• Exporte para Word (DOCX), Excel, PowerPoint, imagens, texto e e-book (EPUB) — e envie para o Kindle
• Reduza PDFs com a qualidade que preferir e compartilhe por e-mail, WhatsApp, Teams e mais
• Adicione ou remova proteção por senha

Interface em 8 idiomas: português, inglês, turco, alemão, francês, espanhol, italiano e russo.

DEMO GRÁTIS E VERSÃO COMPLETA
Sem licença, o app funciona como demo grátis: documentos de até 3 páginas, arquivos salvos com marca d’água "DEMO" e proteção por senha e exportação para Word/Excel/PowerPoint/JPG/EPUB desativadas. Para a versão completa, compre uma chave de licença em https://mkbsoft.net e digite-a no botão "Inserir licença". Licença individual: US${IND} pagamento único para 1 PC. Licença empresarial: US${CORP} pagamento único para até 5 PCs. Sem assinatura.''',
  new='''• PDF para e-book: converta PDFs em EPUB com texto ajustável, títulos, capítulos, imagens, gráficos e tabelas.
• Enviar para Kindle: copia direto para um Kindle conectado por USB ou envia o e-book pelo seu programa de e-mail ou pelo site da Amazon.
• Exportação AZW3 para Kindle quando o programa gratuito Calibre está instalado.
• Tela de ativação da licença no seu idioma, com link de compra direto.
• Localizar e substituir mantém a fonte, o peso, o tamanho e a cor originais.
• Nomes dos arquivos salvos no idioma escolhido.''',
  feat=['Edite o texto existente direto na página', 'Una, divida, gire e reordene páginas',
        'Adicione texto, imagens, formas, destaques, carimbos e marcas d’água', 'Exporte PDF para Word, Excel, PowerPoint, imagens ou texto',
        'PDF para e-book (EPUB) e envio para o Kindle', 'Reduza PDFs e compartilhe por e-mail ou WhatsApp',
        'Adicione ou remova senhas', 'Funciona offline — os arquivos não saem do seu PC'],
  short='Edite, una, divida, reduza e proteja PDFs no Windows, offline. Demo grátis incluída; versão completa com licença de pagamento único, sem assinatura.',
  terms=['editor de PDF', 'editar PDF', 'juntar PDF', 'dividir PDF', 'comprimir PDF', 'PDF para EPUB', 'PDF Kindle']),
 'ru': dict(
  title='RUSSIAN — Русский (Россия)',
  desc='''PDF Editor Pro — быстрый и лёгкий редактор PDF для Windows. Всё работает локально на вашем компьютере: документы никогда не загружаются в облако.

РЕДАКТИРОВАНИЕ
• Правьте, перемещайте и удаляйте существующий текст прямо на странице
• Добавляйте текст, изображения, прямоугольники и круги
• Выделяйте фрагменты, добавляйте штампы и водяные знаки
• Стирайте выбранные области — текст под ними удаляется навсегда

УПОРЯДОЧИВАНИЕ
• Объединяйте несколько PDF в один
• Разделяйте по диапазону страниц или извлекайте страницы
• Поворачивайте, переставляйте, вставляйте и удаляйте страницы в виде миниатюр; удаляйте сразу несколько

КОНВЕРТАЦИЯ И ЗАЩИТА
• Экспорт в Word (DOCX), Excel, PowerPoint, изображения, текст и электронную книгу (EPUB) — и отправка на Kindle
• Сжатие PDF с выбором качества и отправка по почте, в WhatsApp, Teams и не только
• Установка и снятие пароля

Интерфейс на 8 языках: русский, английский, турецкий, немецкий, французский, испанский, итальянский и португальский.

БЕСПЛАТНАЯ ДЕМО И ПОЛНАЯ ВЕРСИЯ
Без лицензии приложение работает как бесплатная демо: документы до 3 страниц, сохранённые файлы с водяным знаком «DEMO», защита паролем и экспорт в Word/Excel/PowerPoint/JPG/EPUB отключены. Для полной версии купите лицензионный ключ на https://mkbsoft.net и введите его кнопкой «Ввести лицензию». Индивидуальная лицензия: ${IND} разово на 1 ПК. Корпоративная лицензия: ${CORP} разово до 5 ПК. Без подписки.''',
  new='''• PDF в электронную книгу: конвертация PDF в EPUB с переносом текста, заголовками, главами, изображениями, диаграммами и таблицами.
• Отправка на Kindle: копирование прямо на Kindle, подключённый по USB, или отправка книги через почтовую программу или сайт Amazon.
• Экспорт в AZW3 для Kindle, если установлена бесплатная программа Calibre.
• Экран активации лицензии на вашем языке с прямой ссылкой на покупку.
• Поиск и замена сохраняет исходный шрифт, начертание, размер и цвет.
• Имена сохранённых файлов на выбранном языке.''',
  feat=['Правка существующего текста прямо на странице', 'Объединение, разделение, поворот и порядок страниц',
        'Текст, изображения, фигуры, выделения, штампы и водяные знаки', 'Экспорт PDF в Word, Excel, PowerPoint, изображения или текст',
        'PDF в электронную книгу (EPUB) и отправка на Kindle', 'Сжатие PDF и отправка по почте или в WhatsApp',
        'Установка и снятие пароля', 'Работает офлайн — файлы не покидают ваш ПК'],
  short='Редактируйте, объединяйте, разделяйте, сжимайте и защищайте PDF в Windows — офлайн. Бесплатная демо; полная версия по разовой лицензии, без подписки.',
  terms=['редактор PDF', 'редактировать PDF', 'объединить PDF', 'разделить PDF', 'сжать PDF', 'PDF в EPUB', 'PDF Kindle']),
}
SHOTS = {'de': 'de', 'es': 'es', 'fr': 'fr', 'it': 'it', 'pt': 'pt', 'ru': 'ru'}

out = ['PARTNER CENTER — EK DİLLER (DE, ES, FR, IT, PT-BR, RU)',
       'Partner Center > Store listings > "Add/remove languages" ile dilleri ekleyin; her dilde aşağıdaki kutuları doldurun.',
       f'Fiyatlar: bireysel ${IND}, kurumsal ${CORP} (python msix/store_diller.py <bireysel> <kurumsal> ile yeniden üretin).',
       'Ekran görüntüleri: images\\site_shots\\<dil>_01_main.png … <dil>_07_kindle.png (1366x768), her dilin kendi görüntüleri.', '']
for code, d in L.items():
    out += ['#' * 69, d['title'], '#' * 69, '', '--- Product name ---', 'PDF Editor Pro - MKBSoft', '',
            '--- Description ---', d['desc'].replace('${IND}', f'${IND}').replace('${CORP}', f'${CORP}')
            .replace('US$' + IND, 'US$ ' + IND).replace('US$' + CORP, 'US$ ' + CORP), '',
            "--- What's new in this version ---", d['new'], '',
            '--- Product features (her satır ayrı kutuya) ---', *d['feat'], '',
            '--- Short description ---', d['short'], '',
            '--- Search terms (her satır ayrı kutuya, en fazla 7) ---', *d['terms'], '',
            '--- Screenshots ---', f'images\\site_shots\\{SHOTS[code]}_01_main.png … {SHOTS[code]}_07_kindle.png (7 adet)', '', '']
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'store_metinleri_diller.txt')
open(path, 'w', encoding='utf-8').write('\n'.join(out))
print('wrote', path)
