"""PDF -> EPUB 3 (reflowable) for e-readers / Send to Kindle.

Text is re-flowed from PyMuPDF's text dict: running headers/footers and page
numbers are dropped, lines are joined into paragraphs (also across page
breaks), larger text becomes headings, bold/italic is kept and images are
embedded. Pages without text (scans) are embedded as page images so nothing
is lost. Chapters follow the PDF bookmarks, else the large headings.
"""
import collections
import hashlib
import html
import io
import re
import uuid
import zipfile
from datetime import datetime, timezone

import pymupdf as fitz

SENTENCE_END = tuple('.!?:;…"”’»)')
BULLETS = ('•', '●', '▪', '◦', '-', '–', '—', '*')
TR_CHARS = set('ğĞışİŞçÇöÖüÜ')
XML_BAD = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]')


def _norm(text):
    """Header/footer fingerprint: digits vary between pages."""
    return re.sub(r'\d+', '#', text.strip().lower())


def _block_text(block):
    return ' '.join(''.join(s['text'] for s in l['spans']) for l in block.get('lines', [])).strip()


def _body_size(pages):
    sizes = collections.Counter()
    for pd in pages:
        for b in pd['blocks']:
            for l in b.get('lines', []):
                for s in l['spans']:
                    if s['text'].strip():
                        sizes[round(s['size'], 1)] += len(s['text'])
    return sizes.most_common(1)[0][0] if sizes else 11.0


def _in_margin(bbox, h):
    return bbox[3] < h * 0.09 or bbox[1] > h * 0.91


def _line_text(line):
    return ''.join(s['text'] for s in line['spans']).strip()


def _furniture(pages, heights):
    """Lines that repeat in the top/bottom margin of many pages (running headers, page numbers).
    Line-level, because a header can share a text block with the page's first heading."""
    if len(pages) < 3:
        return set()
    seen = collections.Counter()
    for pd, h in zip(pages, heights):
        keys = set()
        for b in pd['blocks']:
            for l in b.get('lines', []):
                if _in_margin(l['bbox'], h):
                    t = _norm(_line_text(l))
                    if t:
                        keys.add(t)
        seen.update(keys)
    # 3 pages is enough: running headers often change per chapter ("Chapter 4. Functions")
    need = 3 if len(pages) >= 6 else 2
    return {k for k, n in seen.items() if n >= need}


# "Chapter 3", "Bölüm IV: ...", "Глава 2" on a short line of its own -> chapter start
CHAPTER_RE = re.compile(r'(?i)^(chapter|part|book|prologue|epilogue|bölüm|kısım|kitap|önsöz|kapitel|teil|chapitre|'
                        r'partie|cap[ií]tulo|parte|capitolo|глава|часть)\b.{0,50}$')


def _spans_html(line_spans):
    out = []
    for s in line_spans:
        t = html.escape(XML_BAD.sub('', s['text']))
        if not t:
            continue
        bold = bool(s['flags'] & 16) or 'bold' in s['font'].lower()
        italic = bool(s['flags'] & 2) or 'italic' in s['font'].lower() or 'oblique' in s['font'].lower()
        if bold and t.strip():
            t = f'<b>{t}</b>'
        if italic and t.strip():
            t = f'<i>{t}</i>'
        out.append(t)
    return ''.join(out).replace('</b><b>', '').replace('</i><i>', '')


def _join_lines(lines):
    """Joins a block's lines into one paragraph, removing end-of-line hyphenation."""
    text = ''
    for ln in lines:
        part = _spans_html(ln['spans']).strip()
        if not part:
            continue
        if text.endswith('-') and part[:1].islower():
            text = text[:-1] + part
        elif text:
            text += ' ' + part
        else:
            text = part
    return text


def _plain(h):
    return html.unescape(re.sub(r'<[^>]+>', '', h))


class _Book:
    def __init__(self):
        self.items = []          # ('h1'|'h2'|'p'|'li'|'img', payload)
        self.images = {}         # sha1 -> (name, media_type, bytes)
        self.cover = None        # JPEG bytes

    def add_image(self, data, ext, max_side=1200):
        """Stores an image at e-reader size: at most 1200 px, JPEG unless it has transparency."""
        ext = (ext or 'png').lower()
        try:
            pix = fitz.Pixmap(data)
        except Exception:
            return None
        small = max(pix.width, pix.height) <= max_side
        if small and ext in ('jpg', 'jpeg') and len(data) < 400_000:
            mt, ext = 'image/jpeg', 'jpg'  # already a reasonable JPEG: keep as-is
        else:
            if pix.n - pix.alpha not in (1, 3):
                pix = fitz.Pixmap(fitz.csRGB, pix)
            if not small:
                k = max_side / max(pix.width, pix.height)
                pix = fitz.Pixmap(pix, max(1, int(pix.width * k)), max(1, int(pix.height * k)), None)
            if pix.alpha:
                data, mt, ext = pix.tobytes('png'), 'image/png', 'png'
            else:
                data, mt, ext = pix.tobytes('jpeg', jpg_quality=80), 'image/jpeg', 'jpg'
        key = hashlib.sha1(data).hexdigest()
        if key not in self.images:
            self.images[key] = (f'img{len(self.images) + 1:03d}.{ext}', mt, data)
        return self.images[key][0]


def _table_html(rows):
    out = ['<table>']
    for r, row in enumerate(rows):
        cells = ''.join(f'<{"th" if r == 0 else "td"}>{html.escape(XML_BAD.sub("", c or "")).replace(chr(10), " ")}'
                        f'</{"th" if r == 0 else "td"}>' for c in row)
        out.append(f'<tr>{cells}</tr>')
    out.append('</table>')
    return ''.join(out)


def _reading_order(elems, width):
    """Orders (bbox, kind, value) elements for reading. Two-column pages are read left
    column then right column; full-width items (titles, wide images) split the page
    into bands that are read top to bottom."""
    by_pos = sorted(elems, key=lambda e: (round(e[0][1] / 3), e[0][0]))
    mid = width / 2
    left = [e for e in elems if e[0][2] <= mid + 15]
    right = [e for e in elems if e[0][0] >= mid - 15]
    text_len = lambda es: sum(len(_block_text(v)) for _, k, v in es if k == 'block')  # noqa: E731
    if len(left) < 2 or len(right) < 2 or min(text_len(left), text_len(right)) < 200:
        return by_pos  # single column
    full = sorted((e for e in elems if e not in left and e not in right), key=lambda e: e[0][1])
    out, top = [], float('-inf')
    for f in full + [None]:
        bottom = f[0][1] if f else float('inf')
        band = lambda col: sorted((e for e in col if top <= e[0][1] < bottom), key=lambda e: e[0][1])  # noqa: E731
        out += band(left) + band(right)
        if f:
            out.append(f)
            top = f[0][1]
    return out


def _merge_near(rects, dx, dy):
    """Joins drawing clusters that sit close together (e.g. the separate bars of one chart)."""
    rects = [r for r in rects if r.height >= 2 or r.width >= 2]
    merged = True
    while merged:
        merged = False
        for a in range(len(rects)):
            for b in range(a + 1, len(rects)):
                if (rects[a] + (-dx, -dy, dx, dy)).intersects(rects[b]):
                    rects[a] |= rects[b]
                    del rects[b]
                    merged = True
                    break
            if merged:
                break
    return rects


def _page_regions(page, pd, book):
    """Areas that don't reflow as text: ruled tables (-> HTML table) and vector drawings
    such as charts (-> rendered image). Returns [(rect, 'table'|'img', payload)]."""
    regions = []
    area = page.rect.get_area()
    try:
        for t in page.find_tables().tables:
            if t.row_count >= 2 and t.col_count >= 2:
                regions.append((fitz.Rect(t.bbox), 'table', _table_html(t.extract())))
    except Exception:
        pass
    try:
        clusters = _merge_near([fitz.Rect(r) for r in page.cluster_drawings()], dx=70, dy=30)
    except Exception:
        clusters = []
    texts = [(fitz.Rect(b['bbox']), len(_block_text(b))) for b in pd['blocks'] if b['type'] == 0]
    for r in map(fitz.Rect, clusters):
        if r.width < 60 or r.height < 40 or not (area * 0.01 <= r.get_area() <= area * 0.85):
            continue  # rules, bars, page frames, backgrounds
        if any((r & t).get_area() > 0.5 * r.get_area() for t, _, _ in regions):
            continue  # table borders
        near = [(tr, n) for tr, n in texts if tr.intersects(r + (-20, -20, 20, 20))]
        if sum(n for _, n in near) > 250:
            continue  # a box around normal text: keep it as reflowable text
        clip = r
        for tr, _ in near:  # take the chart's labels with it
            clip |= tr
        pix = page.get_pixmap(clip=clip, dpi=150)
        if pix.alpha:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        name = book.add_image(pix.tobytes('png'), 'png')
        if name:
            regions.append((clip, 'img', name))
    return regions


def _detect_lang(doc):
    sample = ''.join(doc[i].get_text() for i in range(min(len(doc), 5)))
    return 'tr' if sum(c in TR_CHARS for c in sample) > 5 else 'en'


NAME_RE = re.compile(r"^[^\W\d_][\w.'’-]*(\s+[^\W\d_][\w.'’-]*){1,3}$")
NAME_PARTICLES = {'de', 'da', 'di', 'du', 'van', 'von', 'der', 'den', 'la', 'le', 'bin', 'ibn', 'al', 'el', 'y'}


def _looks_like_name(t):
    """'Allen Downey', 'Ursula K. Le Guin', 'Ahmet Hamdi Tanpınar' - not 'Casual wear' or 'MAJOR THEME'."""
    if len(t) > 40 or t.isupper() or not NAME_RE.match(t):
        return False
    return all(w[0].isupper() or w.lower() in NAME_PARTICLES for w in t.split())


def _meaningful(text):
    """Metadata titles like 'SS27_REPORT-2' or 'Microsoft Word - x.docx' are file names, not titles."""
    t = (text or '').strip()
    return bool(t) and '_' not in t and not re.search(r'(?i)microsoft|\.docx?$|\.pdf$|untitled|adsız', t)


def _page_lines(pd, furniture, height):
    out = []
    for b in pd['blocks']:
        for l in b.get('lines', []):
            t = _line_text(l)
            sizes = [s['size'] for s in l['spans'] if s['text'].strip()]
            if t and sizes and not (_in_margin(l['bbox'], height) and _norm(t) in furniture):
                out.append((max(sizes), t))
    return out


def _cover_title_author(pages, body, furniture, heights):
    """Title = largest line on page 1. Author = a name-like line in a large font on the first
    three pages (cover / title page) that is not followed by body text, i.e. not a heading."""
    first = _page_lines(pages[0], furniture, heights[0])
    if not first:
        return None, None
    top = max(s for s, _ in first)
    if top < body * 1.5:
        return None, None
    title = ' '.join(t for s, t in first if s >= top - 0.5)
    if not 2 <= len(title) <= 120:
        return None, None
    title_key = _norm(title)
    for pd, h in zip(pages[:3], heights[:3]):
        lines = _page_lines(pd, furniture, h)
        # only on a cover/title page (one that shows the title), a few lines below the title
        at = next((k for k, (_, t) in enumerate(lines) if _norm(t) and _norm(t) in title_key), None)
        if at is None:
            continue
        for k, (s, t) in enumerate(lines[at + 1:at + 6], start=at + 1):
            nxt = lines[k + 1] if k + 1 < len(lines) else None
            if body * 1.2 <= s < top - 0.5 and _looks_like_name(t) \
                    and t.lower() not in title.lower() \
                    and (nxt is None or nxt[0] > body * 1.1 or '@' in nxt[1] or '://' in nxt[1]):
                return title, t
    return title, None


def build_epub(doc, title=None, author=None, lang=None, fallback_title='Belge'):
    """Returns the EPUB file as bytes. Title/author: arguments, else meaningful PDF metadata,
    else read from the cover page, else fallback_title."""
    pages = [p.get_text('dict', flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_LIGATURES) for p in doc]
    heights = [p.rect.height for p in doc]
    body = _body_size(pages)
    furniture = _furniture(pages, heights)
    lang = lang or _detect_lang(doc)
    meta = doc.metadata or {}
    cover_title, cover_author = _cover_title_author(pages, body, furniture, heights) if pages else (None, None)
    title = (title or (meta.get('title') if _meaningful(meta.get('title')) else None)
             or cover_title or fallback_title.replace('_', ' ')).strip()
    author = (author or (meta.get('author') or '').strip() or cover_author or '').strip()

    # Chapter starts from bookmarks: page index -> title
    toc_starts = {}
    for lvl, ttl, pno in doc.get_toc(simple=True):
        if lvl == 1 and 1 <= pno <= len(doc) and (pno - 1) not in toc_starts:
            toc_starts[pno - 1] = ttl.strip()

    book = _Book()
    cover = doc[0].get_pixmap(matrix=fitz.Matrix(1, 1).prescale(*(2 * [900 / max(doc[0].rect.height, 1)])))
    if cover.alpha:
        cover = fitz.Pixmap(fitz.csRGB, cover)
    book.cover = cover.tobytes('jpeg', jpg_quality=80)
    for i, (page, pd) in enumerate(zip(doc, pages)):
        if i in toc_starts:
            book.items.append(('h1', html.escape(toc_starts[i])))
        text_blocks = [b for b in pd['blocks'] if b['type'] == 0 and _block_text(b)]
        if not text_blocks:
            # Scanned / image-only page: keep it as a picture
            pix = page.get_pixmap(dpi=110)
            if pix.alpha:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            name = book.add_image(pix.tobytes('jpeg', jpg_quality=75), 'jpg')
            if name:
                book.items.append(('img', name))
            continue
        regions = _page_regions(page, pd, book)
        inside = lambda bb: any(fitz.Rect(bb).intersect(r).get_area() > 0.6 * max(fitz.Rect(bb).get_area(), 1)  # noqa: E731
                                for r, _, _ in regions)
        elements = [(tuple(r), kind, val) for r, kind, val in regions]
        elements += [(tuple(b['bbox']), 'block', b) for b in pd['blocks'] if not inside(b['bbox'])]
        for _, kind, b in _reading_order(elements, page.rect.width):
            if kind != 'block':
                book.items.append((kind, b))  # 'img' (rendered chart/drawing) or 'table'
                continue
            if b['type'] == 1:
                x0, y0, x1, y1 = b['bbox']
                if (x1 - x0) < 40 or (y1 - y0) < 40:
                    continue  # icons, bullets, decorations
                name = book.add_image(b['image'], b.get('ext'))
                if name:
                    book.items.append(('img', name))
                continue
            h = page.rect.height
            lines = [l for l in b['lines']
                     if not (_in_margin(l['bbox'], h) and _norm(_line_text(l)) in furniture)]
            # A "Chapter N" line opens a chapter even when it is body-sized
            if lines and not _in_margin(lines[0]['bbox'], h) and len(_line_text(lines[0])) <= 60 \
                    and CHAPTER_RE.match(_line_text(lines[0])):
                book.items.append(('h1', html.escape(XML_BAD.sub('', _line_text(lines[0])))))
                lines = lines[1:]
            if not lines:
                continue
            b = dict(b, lines=lines)
            raw = _block_text(b)
            if re.fullmatch(r'[\d\s/\-–|]+|(sayfa|page)\s*\d+.*', raw.strip().lower()):
                continue
            sizes = [s['size'] for l in b['lines'] for s in l['spans'] if s['text'].strip()]
            size = max(sizes) if sizes else body
            content = _join_lines(b['lines'])
            if not content:
                continue
            plain = _plain(content)
            if size >= body * 1.25 and len(plain) < 160:
                tag = ('H', round(size, 1))  # level decided after all pages are read
                if i in toc_starts and book.items and book.items[-1][0] == 'h1' \
                        and _plain(book.items[-1][1]).lower() == plain.lower():
                    continue  # bookmark title already added
                book.items.append((tag, content))
                continue
            if plain[:1] in BULLETS and len(plain) > 2 and plain[1] == ' ':
                book.items.append(('li', content.lstrip('•●▪◦-–—* ')))
                continue
            prev = book.items[-1] if book.items else None
            if prev and prev[0] == 'p' and not _plain(prev[1]).rstrip().endswith(SENTENCE_END) \
                    and plain[:1].islower():
                joined = prev[1][:-1] + content if prev[1].endswith('-') else prev[1] + ' ' + content
                book.items[-1] = ('p', joined)  # paragraph continues across a block/page break
            else:
                book.items.append(('p', content))

    # Only the largest heading size, if it is rare, starts chapters (h1); other headings are h2
    hs = [k[1] for k, _ in book.items if isinstance(k, tuple)]
    top = max(hs) if hs else 0
    top_count = sum(1 for h in hs if h >= top - 0.5)
    h1_ok = top >= body * 1.4 and top_count <= max(3, len(doc) // 2)
    book.items = [(('h1' if h1_ok and k[1] >= top - 0.5 else 'h2') if isinstance(k, tuple) else k, v)
                  for k, v in book.items]
    return _package(book, title, author, lang)


def _chapters(items, title):
    """Splits at h1 headings (and every ~120 KB so readers stay fast)."""
    chapters, cur, size = [], [], 0
    for it in items:
        if (it[0] == 'h1' and size >= 2000) or size > 120_000:  # no tiny chapters
            chapters.append(cur)
            cur, size = [], 0
        cur.append(it)
        size += len(it[1])
    if cur:
        chapters.append(cur)
    out = []
    for n, ch in enumerate(chapters, 1):
        head = next((_plain(v) for k, v in ch if k in ('h1', 'h2')), None)
        out.append((head or (title if n == 1 else f'{title} ({n})'), ch))
    return out or [(title, [('p', '')])]


XHTML = '''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{lang}" lang="{lang}">
<head><meta charset="utf-8"/><title>{title}</title><link rel="stylesheet" type="text/css" href="style.css"/></head>
<body>
{body}
</body>
</html>
'''

CSS = '''body { margin: 0 4%; line-height: 1.5; font-family: serif; }
h1 { font-size: 1.6em; margin: 1.2em 0 .6em; line-height: 1.2; page-break-before: always; }
h2 { font-size: 1.25em; margin: 1em 0 .5em; line-height: 1.25; }
p { margin: 0 0 .7em; text-indent: 0; text-align: justify; }
ul { margin: 0 0 .8em 1.2em; padding: 0; }
li { margin: 0 0 .3em; }
div.img { text-align: center; margin: 1em 0; }
img { max-width: 100%; height: auto; }
table { border-collapse: collapse; width: 100%; margin: 0 0 1em; font-size: .9em; }
th, td { border: 1px solid #888; padding: .25em .4em; text-align: left; vertical-align: top; }
th { font-weight: bold; }
'''


def _render(items):
    out, in_list = [], False
    for kind, val in items:
        if kind == 'li' and not in_list:
            out.append('<ul>')
            in_list = True
        elif kind != 'li' and in_list:
            out.append('</ul>')
            in_list = False
        if kind == 'img':
            out.append(f'<div class="img"><img src="images/{val}" alt=""/></div>')
        elif kind == 'table':
            out.append(val)
        elif kind in ('h1', 'h2'):
            out.append(f'<{kind}>{val}</{kind}>')
        elif kind == 'li':
            out.append(f'<li>{val}</li>')
        elif val:
            out.append(f'<p>{val}</p>')
    if in_list:
        out.append('</ul>')
    return '\n'.join(out)


def _package(book, title, author, lang):
    chapters = _chapters(book.items, title)
    uid = f'urn:uuid:{uuid.uuid4()}'
    modified = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    esc = html.escape
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr(zipfile.ZipInfo('mimetype'), 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        zw = lambda name, data: z.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)  # noqa: E731
        zw('META-INF/container.xml', '''<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>
''')
        zw('OEBPS/style.css', CSS)
        for name, mt, data in book.images.values():
            zw(f'OEBPS/images/{name}', data)
        if book.cover:
            zw('OEBPS/images/cover.jpg', book.cover)
        for n, (ch_title, items) in enumerate(chapters, 1):
            zw(f'OEBPS/ch{n:03d}.xhtml', XHTML.format(lang=lang, title=esc(ch_title), body=_render(items)))

        nav_items = '\n'.join(f'      <li><a href="ch{n:03d}.xhtml">{esc(t)}</a></li>'
                              for n, (t, _) in enumerate(chapters, 1))
        zw('OEBPS/nav.xhtml', f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{lang}" lang="{lang}">
<head><meta charset="utf-8"/><title>{esc(title)}</title></head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>{'İçindekiler' if lang == 'tr' else 'Contents'}</h1>
    <ol>
{nav_items}
    </ol>
  </nav>
</body>
</html>
''')
        ncx_points = '\n'.join(f'''    <navPoint id="np{n}" playOrder="{n}"><navLabel><text>{esc(t)}</text></navLabel><content src="ch{n:03d}.xhtml"/></navPoint>'''
                               for n, (t, _) in enumerate(chapters, 1))
        zw('OEBPS/toc.ncx', f'''<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="{uid}"/></head>
  <docTitle><text>{esc(title)}</text></docTitle>
  <navMap>
{ncx_points}
  </navMap>
</ncx>
''')
        manifest = ['    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                    '    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
                    '    <item id="css" href="style.css" media-type="text/css"/>']
        manifest += [f'    <item id="ch{n:03d}" href="ch{n:03d}.xhtml" media-type="application/xhtml+xml"/>'
                     for n in range(1, len(chapters) + 1)]
        manifest += [f'    <item id="{name.split(".")[0]}" href="images/{name}" media-type="{mt}"/>'
                     for name, mt, _ in book.images.values()]
        cover_meta = ''
        if book.cover:
            manifest.append('    <item id="cover" href="images/cover.jpg" media-type="image/jpeg" properties="cover-image"/>')
            cover_meta = '\n    <meta name="cover" content="cover"/>'
        spine = '\n'.join(f'    <itemref idref="ch{n:03d}"/>' for n in range(1, len(chapters) + 1))
        creator = f'\n    <dc:creator>{esc(author)}</dc:creator>' if author else ''
        zw('OEBPS/content.opf', f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="{lang}">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">{uid}</dc:identifier>
    <dc:title>{esc(title)}</dc:title>
    <dc:language>{lang}</dc:language>{creator}
    <meta property="dcterms:modified">{modified}</meta>{cover_meta}
  </metadata>
  <manifest>
{chr(10).join(manifest)}
  </manifest>
  <spine toc="ncx">
{spine}
  </spine>
</package>
''')
    return buf.getvalue()
