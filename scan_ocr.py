"""OCR for scanned pages (copier / scanner PDFs).

Scanners such as Canon's write the page as one big picture with their own OCR as invisible text
(render mode 3) on top. That text is often garbage ("L�lltllk �� Dlg T�ca��t"), its lines merge
across columns and whole fields are missing, so editing it fails. For pages that are mostly a
picture we read the picture again with the OCR engine built into Windows (Windows.Media.Ocr: no
download, works in the Store package) and edit those lines instead.
"""
import asyncio
import csv
import difflib
import hashlib
import io
import os
import subprocess
import sys
import threading

import pymupdf as fitz

try:
    import numpy as np
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import SoftwareBitmap, BitmapPixelFormat, BitmapAlphaMode
    from winrt.windows.storage.streams import DataWriter
    _AVAILABLE = True
except Exception:
    _AVAILABLE = False

_CACHE = {}          # page fingerprint → list of lines
_CACHE_MAX = 64
_LOCK = threading.Lock()
_TARGET_PX = 4200    # longest side of the image given to the OCR engine (engine max is 10000)
_DESCENDERS = set('gjpqyşçğŞÇ,;()[]{}|/\\')


def available():
    return _AVAILABLE


def invisible_rects(page):
    """Boxes of invisible text (scanner OCR layers): such text is never what the reader sees."""
    try:
        return [fitz.Rect(t['bbox']) for t in page.get_texttrace() if t.get('type') == 3]
    except Exception:
        return []


def is_scan_page(page):
    """True when one picture covers most of the page (a scan or photo of a document)."""
    area = abs(page.rect) or 1
    try:
        for img in page.get_images(full=True):
            for r in page.get_image_rects(img[0]):
                if abs(r & page.rect) / area > 0.6:
                    return True
    except Exception:
        pass
    return False


def _fingerprint(page):
    h = hashlib.md5(page.read_contents())
    doc = page.parent
    for img in page.get_images(full=True):
        try:
            h.update(doc.xref_stream_raw(img[0]) or b'')
        except Exception:
            pass
    h.update(repr(page.rect).encode())
    h.update(str(page.rotation).encode())
    return h.hexdigest()


def _engine():
    eng = None
    try:
        eng = OcrEngine.try_create_from_user_profile_languages()
    except Exception:
        pass
    if eng is None:
        langs = list(OcrEngine.available_recognizer_languages)
        if langs:
            eng = OcrEngine.try_create_from_language(langs[0])
    return eng


async def _recognize(pix):
    eng = _engine()
    if eng is None:
        return None
    w = DataWriter()
    w.write_bytes(bytes(pix.samples))
    sb = SoftwareBitmap.create_copy_from_buffer(w.detach_buffer(), BitmapPixelFormat.RGBA8,
                                                pix.width, pix.height, BitmapAlphaMode.PREMULTIPLIED)
    return await eng.recognize_async(sb)


def _colors(arr, rect, z):
    """(paper colour, ink colour) inside rect, sampled from the rendered page (RGB 0..1)."""
    h, w = arr.shape[:2]
    x0, y0 = max(int(rect.x0 * z), 0), max(int(rect.y0 * z), 0)
    x1, y1 = min(int(rect.x1 * z) + 1, w), min(int(rect.y1 * z) + 1, h)
    if x1 <= x0 or y1 <= y0:
        return (1, 1, 1), (0, 0, 0)
    px = arr[y0:y1, x0:x1, :3].reshape(-1, 3).astype(np.float32)
    lum = px.mean(axis=1)
    order = np.argsort(lum)
    n = len(order)
    ink = px[order[:max(n // 20, 1)]].mean(axis=0)
    paper = np.median(px[order[n // 2:]], axis=0)
    return tuple(round(float(c) / 255, 3) for c in paper), tuple(round(float(c) / 255, 3) for c in ink)


# Letters whose capital is the small letter drawn bigger: OCR often gets their case wrong
# ("A.ş." for "A.Ş.", "örme" for "Örme", "v.D." for "V.D.")
_CASELESS = set('cosuvwxzçöşüCOSUVWXZÇÖŞÜ')
# No İ, Ğ: their dot or breve often blurs onto the letter and would raise the capital line
_CAPS = set('ABDEFGHIJKLMNPQRTY0123456789')
_SMALL = set('aemnr')


def _upper(ch):
    return {'i': 'İ'}.get(ch, ch.upper())


def _lower(ch):
    return {'I': 'ı', 'İ': 'i'}.get(ch, ch.lower())


def _fix_case(words, arr, z):
    """Correct the case of _CASELESS letters by where their ink starts in the scan: a letter
    whose top is level with the line's capitals and digits is a capital, one level with its
    'a e m n r' is not. The top, not the height, so a cedilla (ş, ç) does not count."""
    import cv2
    glyphs = []   # (word index, char index, top of the letter body in page pixels)
    for wi, (r, t) in enumerate(words):
        x0, y0 = max(int(r.x0 * z), 0), max(int(r.y0 * z) - 2, 0)
        x1, y1 = min(int(r.x1 * z) + 1, arr.shape[1]), min(int(r.y1 * z) + 3, arr.shape[0])
        if x1 - x0 < 3 or y1 - y0 < 3:
            continue
        g = arr[y0:y1, x0:x1, :3].mean(axis=2).astype(np.uint8)
        _, ink = cv2.threshold(g, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        n, _, st, _ = cv2.connectedComponentsWithStats(ink)
        pieces = sorted((tuple(int(v) for v in s) for s in st[1:] if s[4] >= 3), key=lambda s: s[0])
        # Dots, accents and cedillas join the letter they sit above or below; a full stop beside
        # a "V" shares its columns but not its rows, so it stays a character of its own
        letters = []   # [x0, y0, x1, y1, pieces]
        for x, y, w, h, a in pieces:
            if letters:
                L = letters[-1]
                over = min(x + w, L[2]) - max(x, L[0])
                apart = y >= L[3] or y + h <= L[1]
                if over >= min(w, L[2] - L[0]) * 0.3 and apart:
                    L[0], L[1], L[2], L[3] = min(L[0], x), min(L[1], y), max(L[2], x + w), max(L[3], y + h)
                    L[4].append((y, y + h, a))
                    continue
            letters.append([x, y, x + w, y + h, [(y, y + h, a)]])
        if len(letters) != len(t):
            continue   # touching letters: no reliable letter-by-letter match
        # The count can match by chance (a speck, two letters touching): punctuation must fall
        # on small pieces and letters on letter-sized ones, or the word is left alone
        areas = [sum(p[2] for p in L[4]) for L in letters]
        alnum = sorted(a for ch, a in zip(t, areas) if ch.isalnum())
        big = alnum[len(alnum) // 2] if alnum else 0
        if any((ch in '.,:;' and a > big * 0.35) or (ch.isalnum() and a < big * 0.35)
               for ch, a in zip(t, areas)):
            continue
        for ci, L in enumerate(letters):
            top, bottom, _ = max(L[4], key=lambda p: p[2])   # biggest piece: the letter, not its dots
            glyphs.append((wi, ci, y0 + top, y0 + bottom, len(L[4]), L[3] - L[1]))
    caps = [(t, b) for wi, ci, t, b, *_ in glyphs if words[wi][1][ci] in _CAPS]
    small = [(t, b) for wi, ci, t, b, *_ in glyphs if words[wi][1][ci] in _SMALL]
    if not caps and not small:
        return words
    # A line of capitals only (or small letters only) gives the other height by typical
    # proportions: the x-height is about 0.72 of the capital height
    if caps:
        cap_top = float(np.median([t for t, _ in caps]))
        base = float(np.median([b for _, b in caps]))
    if small:
        x_top = float(np.median([t for t, _ in small]))
        base = float(np.median([b for _, b in small])) if not caps else base
    if not small:
        x_top = base - (base - cap_top) * 0.72
    if not caps:
        cap_top = base - (base - x_top) / 0.72
    if x_top - cap_top < 2:
        return words
    gap = x_top - cap_top
    fixed = [list(t) for _, t in words]
    # A line in capitals ("VE DiŞ TİCARET"): letters that could be either lean to capitals
    plain = [ch for _, t in words for ch in t if ch.isalpha() and ch not in _CASELESS and ch not in 'iİIı']
    all_caps = len(plain) >= 3 and sum(ch.isupper() for ch in plain) >= len(plain) * 0.8
    for wi, ci, top, _, pieces, height in glyphs:
        ch = fixed[wi][ci]
        # Only a clear case: level with the capitals, or level with the small letters
        if ch in _CASELESS:
            if top < cap_top + gap * (0.5 if all_caps else 0.3):
                fixed[wi][ci] = _upper(ch)
            elif top > x_top - gap * 0.3:
                fixed[wi][ci] = _lower(ch)
        elif ch == 'i' and all_caps and top < cap_top + gap * 0.5:
            # A capital: dotted (a dot apart, or blurred onto it so the letter stands taller
            # than a capital) is İ, otherwise the I of "DIŞ" that OCR read as i
            dotted = pieces > 1 or height > (base - cap_top) * 1.15
            fixed[wi][ci] = 'İ' if dotted else 'I'
        elif ch == 'İ' and top > x_top - gap * 0.3:
            fixed[wi][ci] = 'i'
    return [(r, ''.join(f)) for (r, _), f in zip(words, fixed)]


def _gutters(found, width):
    """x positions of the gaps between text columns: where many lines have a gap and hardly any
    word crosses. A narrow gutter (a two-column contract) is then split even when it is narrower
    than a line's height; a wide word space in one justified line alone is not."""
    gaps = np.zeros(int(width) + 2, np.int32)
    inked = np.zeros(int(width) + 2, np.int32)
    for words in found:
        ws = sorted(words, key=lambda w: w[0].x0)
        for (r, _) in ws:
            inked[max(0, int(r.x0)):int(r.x1) + 1] += 1
        for (a, _), (b, _) in zip(ws, ws[1:]):
            if b.x0 - a.x1 >= 3:
                gaps[int(a.x1) + 1:int(b.x0)] += 1
    return set(np.nonzero((gaps >= 6) & (inked <= gaps * 0.1))[0].tolist())


def _split_words(words, gutters=()):
    """Split an OCR line where a wide gap or a column gutter separates two columns
    ("Müşteri V.D.   : ÇİĞLİ")."""
    groups, cur = [], [words[0]]
    for prev, wd in zip(words, words[1:]):
        hgt = max(prev[0].height, wd[0].height, 1)
        gap = range(int(prev[0].x1) + 1, int(wd[0].x0))
        if wd[0].x0 - prev[0].x1 > hgt * 2.2 or (len(gap) >= 3 and any(x in gutters for x in gap)):
            groups.append(cur)
            cur = []
        cur.append(wd)
    groups.append(cur)
    return groups


def _line_info(words, arr, z):
    rect = fitz.Rect(words[0][0])
    for r, _ in words[1:]:
        rect |= r
    text = ' '.join(t for _, t in words)
    heights = sorted(r.height for r, _ in words)
    h = heights[len(heights) // 2]
    plain = [r.y1 for r, t in words if not (set(t) & _DESCENDERS)]
    baseline = max(plain) if plain else rect.y1 - h * 0.2
    # Word boxes run from the tallest glyph to the lowest: about 0.72 em for capitals, ~0.95 em
    # with descenders. The editor recalibrates by width, this only has to be close.
    caps = text.upper() == text and not (set(text) & _DESCENDERS)
    size = round(h / (0.74 if caps else 0.85), 1)
    paper, ink = _colors(arr, rect, z)
    return {'text': text, 'bbox': tuple(rect), 'baseline': baseline, 'size': max(size, 4.0),
            'paper': paper, 'ink': ink, 'words': [(tuple(r), t) for r, t in words]}


def _missed_regions(arr, z, covered):
    """Line-shaped areas of ink (page coordinates) that no OCR word covers: small or blurred
    print the engine skipped when it read the whole page at once."""
    import cv2
    h, w = arr.shape[:2]
    s = 1400 / max(h, w)
    g = cv2.resize(arr[:, :, :3].mean(axis=2).astype(np.uint8), (int(w * s), int(h * s)),
                   interpolation=cv2.INTER_AREA)
    k = max(15, int(max(g.shape) / 40)) | 1
    bg = cv2.morphologyEx(g, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    ink = ((bg.astype(np.int16) - g) > 40).astype(np.uint8)
    f = z * s
    for r in covered:
        ink[max(0, int(r.y0 * f) - 2):int(r.y1 * f) + 3, max(0, int(r.x0 * f) - 2):int(r.x1 * f) + 3] = 0
    blobs = cv2.dilate(ink, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3)))
    n, _, st, _ = cv2.connectedComponentsWithStats(blobs)
    out = []
    for x, y, bw, bh, _a in st[1:]:
        hp = bh / f
        if not 4 <= hp <= 24 or bw < bh * 1.5:
            continue
        dens = float(ink[y:y + bh, x:x + bw].mean())
        if not 0.05 <= dens <= 0.6:
            continue
        out.append(fitz.Rect(x / f, y / f, (x + bw) / f, (y + bh) / f))
    return sorted(out, key=lambda r: -r.width)[:40]


_OK_CHARS = set('ABCÇDEFGĞHIİJKLMNOÖPQRSŞTUÜVWXYZabcçdefgğhıijklmnoöpqrsştuüvwxyz0123456789 .,:;/()-+&@%')


def _junk(text):
    """Share of a reading that cannot be right: stray symbols ("î!", "û", "$") and words with
    capitals scattered inside ("LojIstIk", "MtjŞTERf")."""
    t = text.strip()
    if not t:
        return 9.0
    bad = sum(ch not in _OK_CHARS for ch in t)
    mixed = sum(1 for w in t.split() if any(c.isupper() for c in w[1:]) and any(c.islower() for c in w[1:]))
    return (bad + mixed) / len(t)


_PAD = 40


def _read_enhanced(page, rect):
    """OCR of rect cut out, enlarged to ~60 px letters, contrast-stretched and darkened: faint,
    thin or small print the whole-page reading missed or garbled. Returns
    [(words, pixels, zoom, origin)] like ocr_page's first pass."""
    import cv2
    m = rect.height * 0.5
    clip = fitz.Rect(rect.x0 - m, rect.y0 - m * 0.6, rect.x1 + m, rect.y1 + m * 0.6) & page.rect
    zz = min(12.0, max(4.0, 60 / max(rect.height, 1)))
    pm = page.get_pixmap(matrix=fitz.Matrix(zz, zz), clip=clip, colorspace=fitz.csGRAY, alpha=False, annots=False)
    g = np.frombuffer(pm.samples, np.uint8).reshape(pm.height, pm.width)
    lo, hi = np.percentile(g, 1), np.percentile(g, 95)
    g = ((((g.astype(np.float32) - lo) / max(hi - lo, 1)).clip(0, 1) ** 2) * 255).astype(np.uint8)
    g = cv2.copyMakeBorder(g, _PAD, _PAD, _PAD, _PAD, cv2.BORDER_CONSTANT, value=255)
    px = np.ascontiguousarray(np.dstack([g, g, g, np.full(g.shape, 255, np.uint8)]))
    try:
        res = asyncio.run(_recognize(fitz.Pixmap(fitz.csRGB, g.shape[1], g.shape[0], px.tobytes(), True)))
    except Exception:
        return []
    if res is None:
        return []
    ox, oy = clip.x0 - _PAD / zz, clip.y0 - _PAD / zz
    out = []
    for ln in res.lines:
        words = []
        for wd in ln.words:
            b = wd.bounding_rect
            words.append((fitz.Rect(ox + b.x / zz, oy + b.y / zz, ox + (b.x + b.width) / zz,
                                    oy + (b.y + b.height) / zz), wd.text))
        if words:
            out.append((words, px, zz, (ox, oy)))
    return out


def _reread(page, found):
    """Read every line a second time, enhanced, and keep whichever reading is cleaner. Neither
    always wins: enhancing rescues faint thin print but can hurt heavy dot-matrix print."""
    out = []
    for entry in found:
        words = entry[0]
        rect = fitz.Rect(words[0][0])
        for r, _ in words[1:]:
            rect |= r
        base = ' '.join(t for _, t in words)
        best = entry
        alt = [e for e in _read_enhanced(page, rect)
               if any(abs(r & rect) > abs(r) * 0.5 for r, _ in e[0])]
        if alt:
            ws = [w for e in alt for w in e[0] if abs(w[0] & rect) > abs(w[0]) * 0.5]
            text = ' '.join(t for _, t in ws)
            if ws and _junk(text) < _junk(base) and                     difflib.SequenceMatcher(None, text.lower(), base.lower()).ratio() > 0.3:
                best = (ws,) + alt[0][1:]
        out.append(best)
    return out


def _second_pass(page, arr, z, covered):
    """Read the missed regions one by one, cut out and enhanced."""
    out = []
    for reg in _missed_regions(arr, z, covered):
        m = reg.height * 0.6
        for words, px, zz, origin in _read_enhanced(page, reg):
            words = [(r, t) for r, t in words
                     if fitz.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2) in reg + (-m, -m / 2, m, m / 2)
                     and not any(abs(r & k) > abs(r) * 0.3 for k in covered)]
            text = ''.join(t for _, t in words)
            # Stamps, handwriting and specks read as junk: keep what looks like words or numbers
            n = sum(ch.isalnum() for ch in text)
            if n >= 2 and n >= len(text) * 0.5:
                out.append((words, px, zz, origin))
                covered = covered + [r for r, _ in words]
    return out


# ── Tesseract (optional second engine) ───────────────────────────────────────
# Reads small, faint and Turkish capitals far better than Windows OCR, but loses its way in
# ruled tables. Where both read a line, the one Tesseract is confident about wins.

_TESS_CONF = 60
TESS_LANGS = 'tur'    # Tesseract model(s) to read with ("tur", "rus", "tur+eng" …)


def _tesseract():
    """(tesseract.exe, tessdata folder with tur.traineddata), or None."""
    # Bundled (PyInstaller puts data in _internal = sys._MEIPASS), next to the sources (after
    # get_tesseract.py), or an installed copy
    here = os.path.dirname(os.path.abspath(__file__))
    bases = [getattr(sys, '_MEIPASS', ''), os.path.dirname(sys.executable), here]
    exes = [os.path.join(b, 'tesseract', 'tesseract.exe') for b in bases if b]
    exes.append(os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'), 'Tesseract-OCR', 'tesseract.exe'))
    for exe in exes:
        if not os.path.exists(exe):
            continue
        for data in (os.path.join(os.path.dirname(exe), 'tessdata'), os.path.join(here, 'tessdata')):
            if all(os.path.exists(os.path.join(data, l + '.traineddata')) for l in TESS_LANGS.split('+')):
                return exe, data
    return None


def _tess_words(page):
    """Tesseract's words on the page: [(rect, text, confidence 0..100)]."""
    import cv2
    t = _tesseract()
    if not t:
        return None
    dpi = 400
    pm = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY, alpha=False, annots=False)
    g = np.frombuffer(pm.samples, np.uint8).reshape(pm.height, pm.width)
    lo, hi = np.percentile(g, 1), np.percentile(g, 95)
    g = ((((g.astype(np.float32) - lo) / max(hi - lo, 1)).clip(0, 1) ** 2) * 255).astype(np.uint8)
    ok, png = cv2.imencode('.png', g)
    try:
        p = subprocess.run([t[0], 'stdin', 'stdout', '--tessdata-dir', t[1], '-l', TESS_LANGS, '--psm', '11',
                            '-c', 'tessedit_create_tsv=1'], input=png.tobytes(), capture_output=True,
                           timeout=120, creationflags=0x08000000)
    except Exception:
        return None
    f = 72 / dpi
    out = []
    for r in csv.DictReader(io.StringIO(p.stdout.decode('utf-8', 'replace')), delimiter='	',
                            quoting=csv.QUOTE_NONE):
        if r.get('level') == '5' and (r.get('text') or '').strip():
            x, y, w, h = (int(r[k]) for k in ('left', 'top', 'width', 'height'))
            out.append((fitz.Rect(x * f, y * f, (x + w) * f, (y + h) * f), r['text'],
                        float(r['conf']), (r['block_num'], r['par_num'], r['line_num'])))
    return out


def _merge_tesseract(found, tw):
    """Lines read by Windows take Tesseract's words where Tesseract is confident; lines only
    Tesseract found (confidently) are added."""
    out, used = [], set()
    for entry in found:
        words = entry[0]
        box = fitz.Rect(words[0][0])
        for r, _ in words[1:]:
            box |= r
        inside = [i for i, w in enumerate(tw) if abs(w[0] & box) > abs(w[0]) * 0.5]
        if inside and sum(tw[i][2] for i in inside) / len(inside) >= _TESS_CONF:
            used.update(inside)
            ws = sorted(((tw[i][0], tw[i][1]) for i in inside), key=lambda w: w[0].x0)
            out.append((ws, None, None, None))      # no case fixing: Tesseract reads case well
        else:
            out.append(entry)
    covered = [r for e in out for r, _ in e[0]]
    rest = {}
    for i, w in enumerate(tw):
        if i not in used and w[2] >= _TESS_CONF and not any(abs(w[0] & c) > abs(w[0]) * 0.3 for c in covered):
            rest.setdefault(w[3], []).append((w[0], w[1]))
    for ws in rest.values():
        text = ''.join(t for _, t in ws)
        n = sum(ch.isalnum() for ch in text)
        if n >= 2 and n >= len(text) * 0.5:
            out.append((sorted(ws, key=lambda w: w[0].x0), None, None, None))
    return out


def ocr_page(page):
    """OCR lines of the page: [{'text', 'bbox', 'baseline', 'size', 'paper', 'ink'}], cached.
    Returns None when OCR is not available."""
    if not _AVAILABLE:
        return None
    key = _fingerprint(page)
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key]
    z = _TARGET_PX / max(page.rect.width, page.rect.height)
    pix = page.get_pixmap(matrix=fitz.Matrix(z, z), alpha=True, annots=False)
    try:
        res = asyncio.run(_recognize(pix))
    except Exception:
        res = None
    if res is None:
        return None
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    found = []   # (words of one OCR line, pixels they were read from, their zoom)
    for ln in res.lines:
        words = []
        for wd in ln.words:
            b = wd.bounding_rect
            words.append((fitz.Rect(b.x / z, b.y / z, (b.x + b.width) / z, (b.y + b.height) / z), wd.text))
        if words:
            found.append((words, arr, z, (0, 0)))
    tw = None
    try:
        tw = _tess_words(page)
    except Exception:
        tw = None
    if tw is not None:
        found = _merge_tesseract(found, tw)
    else:
        try:
            found = _reread(page, found)
        except Exception:
            pass
        try:
            found += _second_pass(page, arr, z, [r for ws, *_ in found for r, _ in ws])
        except Exception:
            pass
    lines = []
    gutters = _gutters([e[0] for e in found], page.rect.width)
    for words, px, zz, origin in found:
        if px is not None:
            ox, oy = origin
            try:
                # _fix_case looks at the pixels the words were read from
                local = [(fitz.Rect(r.x0 - ox, r.y0 - oy, r.x1 - ox, r.y1 - oy), t) for r, t in words]
                fixed = _fix_case(local, px, zz)
                words = [(r, t) for (r, _), (_, t) in zip(words, fixed)]
            except Exception:
                pass
        for grp in _split_words(sorted(words, key=lambda w: w[0].x0), gutters):
            info = _line_info(grp, arr, z)
            if info['text'].strip() and fitz.Rect(info['bbox']).height >= 3:
                lines.append(info)
    lines.sort(key=lambda l: (round(l['bbox'][1] / 4), l['bbox'][0]))
    with _LOCK:
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = lines
    return lines


def whiten(arr, mode='color'):
    """Scanned page pixels (H×W×3 RGB) with the paper turned white: copier grey, yellowed or
    tinted paper, uneven light and shaded cells go, the print stays. 'color' keeps stamps, logos
    and coloured ink; 'bw' returns a black-and-white H×W image (sharpest, smallest file).

    The page is worked through in strips: a 600 dpi A4 scan is 100 MB of pixels and every
    full-page floating-point copy would be 400 MB more."""
    import cv2
    h, w = arr.shape[:2]
    s = min(1.0, 1000 / max(h, w))
    small = cv2.resize(arr, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA)
    # Paper everywhere, letters included: a closing wider than any pen stroke (~1/30 of the page)
    k = max(15, int(max(small.shape[:2]) / 30)) | 1
    bg = cv2.morphologyEx(small, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    bg = cv2.medianBlur(bg, 5).astype(np.float32)
    # Only light shading counts as paper; anything darker (grey logos, solid areas, photos) is
    # print and must not be brightened away
    paper = np.percentile(bg.reshape(-1, 3), 90, axis=0)
    bg = np.maximum(bg, paper * 0.85)
    hs = bg.shape[0]
    out = np.empty((h, w) if mode == 'bw' else (h, w, 3), np.uint8)
    step, margin = 256, 48     # the margin keeps strokes that cross a strip edge whole
    for y0 in range(0, h, step):
        y1 = min(h, y0 + step)
        a0, a1 = max(0, y0 - margin), min(h, y1 + margin)
        # The paper estimate for these rows, interpolated from the small picture
        yy = (np.arange(a0, a1) + 0.5) * hs / h - 0.5
        lo = np.clip(np.floor(yy).astype(int), 0, hs - 1)
        hi = np.clip(lo + 1, 0, hs - 1)
        f = (yy - np.floor(yy)).astype(np.float32)[:, None, None]
        rows = bg[lo] * (1 - f) + bg[hi] * f
        strip_bg = cv2.resize(rows, (w, a1 - a0), interpolation=cv2.INTER_LINEAR)
        v = (arr[a0:a1].astype(np.float32) / np.maximum(strip_bg, 1) / 0.97).clip(0, 1)
        del strip_bg, rows
        # Faint pixels stay only where they touch clear ink: the soft edges of thin ribbon or
        # dot-matrix letters are kept, faint shading, form tint and specks on their own go white.
        # Whole connected strokes count, not a fixed distance: the light dots between the pins
        # of dot-matrix print would otherwise drop out and break the letters ("DIŞ" → "CIŞ")
        lum = v.min(axis=2)
        faint = (lum < 0.95).astype(np.uint8)
        n, labels = cv2.connectedComponents(cv2.dilate(faint, np.ones((2, 2), np.uint8)), connectivity=8)
        has_ink = np.zeros(n, bool)
        has_ink[np.unique(labels[lum < 0.82])] = True
        has_ink[0] = False
        near = has_ink[labels] & (faint > 0)
        del labels, lum, faint
        v = np.where(near[..., None], v ** 1.5, 1.0)   # the ink a little darker, never paler
        keep = slice(y0 - a0, y0 - a0 + (y1 - y0))
        if mode == 'bw':
            out[y0:y1] = (v[keep].mean(axis=2) * 255).astype(np.uint8)
        else:
            o = v[keep] * 255
            # Grey print stays neutral grey (no tint left from the paper); saturated colour is kept
            sat = o.max(axis=2) - o.min(axis=2)
            o = np.where((sat < 28)[..., None], o.mean(axis=2, keepdims=True), o)
            out[y0:y1] = o.clip(0, 255).astype(np.uint8)
        del v
    boxes = _light_boxes(arr, w, h)
    if mode == 'bw':
        t, _ = cv2.threshold(out, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        out = np.where(out > min(max(t, 170), 225), 255, 0).astype(np.uint8)
        if boxes:
            cv2.drawContours(out, boxes, -1, 140, max(1, round(max(h, w) / 1400)))
        return out
    if boxes:
        cv2.drawContours(out, boxes, -1, (175, 175, 175), max(1, round(max(h, w) / 1400)))
    return out


def _light_boxes(arr, w, h):
    """Outlines (full-size pixel contours) of white fields printed on tinted paper: the boxes of
    a form. Whitening the paper would make them vanish, so their outline is drawn back."""
    import cv2
    s = min(1.0, 2000 / max(h, w))       # fine enough to keep the thin gaps between boxes
    g = cv2.cvtColor(cv2.resize(arr, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_AREA),
                     cv2.COLOR_RGB2GRAY)
    # The paper from a wide window: rows of boxes must not outvote the tint around them
    sm = cv2.resize(g, (g.shape[1] // 4, g.shape[0] // 4), interpolation=cv2.INTER_AREA)
    k = min(255, max(15, int(max(sm.shape) / 10)) | 1)
    paper = cv2.resize(cv2.medianBlur(sm, k), (g.shape[1], g.shape[0]), interpolation=cv2.INTER_LINEAR).astype(np.int16)
    light = ((g.astype(np.int16) - paper > 14) & (paper < 238)).astype(np.uint8)
    light = cv2.morphologyEx(light, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    cs, _ = cv2.findContours(light, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    sx, sy = w / g.shape[1], h / g.shape[0]
    out = []
    for c in cs:
        x, y, bw, bh = cv2.boundingRect(c)
        # Box-like: not tiny, well filled by its own outline, not a whole page region
        if bw * bh < 30 or bw > g.shape[1] * 0.5 or bh > g.shape[0] * 0.3:
            continue
        if cv2.contourArea(c) < bw * bh * 0.7:
            continue
        out.append(np.array([[[int(x * sx), int(y * sy)]], [[int((x + bw) * sx), int(y * sy)]],
                             [[int((x + bw) * sx), int((y + bh) * sy)]], [[int(x * sx), int((y + bh) * sy)]]],
                            dtype=np.int32))
    return out


def clean_background(page, mode='color'):
    """Whiten the scan pictures of the page in place. Returns how many pictures were cleaned."""
    import cv2
    doc = page.parent
    area = abs(page.rect) or 1
    scan = None
    imgs = page.get_images(full=True)
    for img in imgs:
        try:
            if any(abs(r & page.rect) / area > 0.6 for r in page.get_image_rects(img[0])):
                scan = page.get_image_rects(img[0])[0]
        except Exception:
            pass
    if scan is None:
        return 0
    done = 0
    for img in imgs:
        xref, smask = img[0], img[1]
        try:
            rects = page.get_image_rects(xref)
        except Exception:
            continue
        # The scan itself and the patches earlier edits laid on it (those with a transparency
        # mask are moved ink only and have no paper to clean)
        if smask or not rects or not any(abs(r & scan) > abs(r) * 0.9 for r in rects):
            continue
        pix = fitz.Pixmap(doc, xref)
        if pix.alpha:
            pix = fitz.Pixmap(pix, 0)
        if pix.n != 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)
        out = whiten(arr, mode)
        del arr, pix
        if mode == 'bw':
            ok, data = cv2.imencode('.png', out)
        else:
            cv2.cvtColor(out, cv2.COLOR_RGB2BGR, dst=out)     # in place: no second full-page copy
            ok, data = cv2.imencode('.jpg', out, [cv2.IMWRITE_JPEG_QUALITY, 88])
        if ok:
            page.replace_image(xref, stream=data.tobytes())
            done += 1
    return done
