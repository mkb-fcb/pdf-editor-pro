from flask import Flask, render_template, request, jsonify, send_file, redirect, make_response
import pymupdf as fitz
import base64
import io
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path
import threading
import webbrowser
import time
import atexit

# PyInstaller frozen bundle support
if getattr(sys, 'frozen', False):
    _BASE_DIR = sys._MEIPASS
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__,
            template_folder=os.path.join(_BASE_DIR, 'templates'),
            static_folder=os.path.join(_BASE_DIR, 'static'))
state = {'doc': None, 'path': None, 'history': []}

import license as _lic

MAX_HISTORY = 15

# Lisans girilmemişse uygulama demo modunda çalışır (3 sayfa, filigranlı kayıt)
DEMO_MAX_PAGES = 3
DEMO_LIMIT_MSG = (f'Demo sürümünde en fazla {DEMO_MAX_PAGES} sayfa desteklenir. '
                  'Tam sürüm için lisans anahtarı girin veya mkbsoft.net adresinden satın alın.')
DEMO_FEATURE_MSG = ('Bu özellik yalnızca tam sürümde kullanılabilir. '
                    'Lisans anahtarı girin veya mkbsoft.net adresinden satın alın.')
_licensed_cache = None


# ── Güvenlik: API'ye yalnızca bu bilgisayardaki uygulama penceresi erişebilir ──
@app.before_request
def _local_only_guard():
    from urllib.parse import urlparse
    host = (request.host or '').lower()
    hn = urlparse('//' + host).hostname or ''
    if hn not in ('localhost', '127.0.0.1', '::1'):
        return ('Forbidden', 403)          # DNS rebinding koruması
    origin = request.headers.get('Origin')
    if origin and origin.lower() != f'http://{host}':
        return ('Forbidden', 403)          # başka web sitelerinden gelen istekler
    if request.headers.get('Sec-Fetch-Site') == 'cross-site':
        return ('Forbidden', 403)


from werkzeug.exceptions import HTTPException


@app.errorhandler(Exception)
def _api_errors(e):
    """API hataları HTML yerine JSON döner; arayüz takılıp kalmaz."""
    if isinstance(e, HTTPException):
        if not request.path.startswith('/api/'):
            return e
        code, msg = e.code or 500, e.description
    else:
        code = 500
        if isinstance(e, (IndexError, KeyError)):
            msg = 'Geçersiz istek veya sayfa numarası.'
        elif 'closed or encrypted' in str(e):
            msg = 'Belge açık değil veya şifreli.'
        else:
            msg = f'İşlem tamamlanamadı: {e}'
        app.logger.exception('API hatası')
    return jsonify({'ok': False, 'error': msg}), code


# ── Geçici dosyalar ve çıktı konumu ────────────────────────────────────────────
_TMP_FILES = []   # bu oturumda oluşturulan geçici dosyalar (çıkışta/yeni yüklemede silinir)


def _tmp_path(suffix='.pdf'):
    fd, p = tempfile.mkstemp(suffix=suffix, prefix='pdfeditor_')
    os.close(fd)
    _TMP_FILES.append(p)
    return p


def _cleanup_tmp(keep=None):
    for p in list(_TMP_FILES):
        if p == keep:
            continue
        try:
            os.unlink(p)
            _TMP_FILES.remove(p)
        except Exception:
            pass


atexit.register(_cleanup_tmp)


def _doc_name() -> str:
    """Kullanıcının gördüğü dosya adı (sürükle-bırakta geçici dosya adı değil)."""
    n = state.get('name')
    if n:
        return n
    p = state.get('path')
    return Path(p).name if p else 'belge.pdf'


def _doc_stem() -> str:
    return Path(_doc_name()).stem


def _out_dir() -> Path:
    """Çıktı klasörü: orijinal dosyanın klasörü; geçici (sürükle-bırak) belgelerde İndirilenler."""
    p = state.get('path')
    if p:
        try:
            parent = Path(p).resolve().parent
            tmp_root = Path(tempfile.gettempdir()).resolve()
            if parent.exists() and parent != tmp_root and tmp_root not in parent.parents:
                return parent
        except Exception:
            pass
    d = Path.home() / 'Downloads'
    return d if d.exists() else Path.home()


def _default_out(suffix_text: str) -> str:
    """<ad><sonek>.pdf — mevcut dosyanın üzerine yazmamak için (2), (3) ekler."""
    d = _out_dir()
    stem = _doc_stem()
    cand = d / f'{stem}{suffix_text}.pdf'
    n = 2
    while cand.exists():
        cand = d / f'{stem}{suffix_text} ({n}).pdf'
        n += 1
    return str(cand)


def _swap_doc(new_doc, path, name=None, reset_history=True):
    """Yeni belgeyi etkinleştir; eskisini ancak yenisi başarıyla açıldıktan sonra kapat."""
    old = state['doc']
    state['doc'] = new_doc
    state['path'] = path
    state['name'] = name or Path(path).name
    if reset_history:
        state['history'] = []
    if old is not None:
        try:
            old.close()
        except Exception:
            pass



def is_demo() -> bool:
    # is_licensed() may hit the license server, so check once per run
    global _licensed_cache
    if _licensed_cache is None:
        _licensed_cache = _lic.is_licensed()
    return not _licensed_cache


def _demo_truncate(doc) -> bool:
    """Demo modunda belgeyi ilk DEMO_MAX_PAGES sayfaya indir. Kırpıldıysa True."""
    if is_demo() and len(doc) > DEMO_MAX_PAGES:
        doc.select(list(range(DEMO_MAX_PAGES)))
        return True
    return False


def _apply_demo_watermark(doc):
    """Tüm sayfalara çapraz DEMO filigranı ekle."""
    text = 'PDF Editör Pro — DEMO'
    for page in doc:
        w, h = page.rect.width, page.rect.height
        try:
            font = fitz.Font(fontfile=UNICODE_FONT) if UNICODE_FONT else fitz.Font('helv')
            tw = fitz.TextWriter(page.rect)
            tw.append(fitz.Point(w * 0.08, h * 0.62), text, font=font, fontsize=44)
            pivot = fitz.Point(w / 2, h / 2)
            tw.write_text(page, color=(0.55, 0.55, 0.55), opacity=0.28,
                          morph=(pivot, fitz.Matrix(45)))
        except Exception:
            kw = {'fontsize': 44, 'color': (0.55, 0.55, 0.55)}
            if UNICODE_FONT:
                kw['fontfile'] = UNICODE_FONT
                kw['fontname'] = UNICODE_FONTNAME
            page.insert_text(fitz.Point(w * 0.15, h * 0.55), text, **kw)


def _save_with_watermark(doc, path):
    """Dokümanın filigranlı bir kopyasını kaydet. Orijinal değişmez."""
    wm_doc = fitz.open(stream=doc.tobytes(garbage=1), filetype='pdf')
    _apply_demo_watermark(wm_doc)
    strip_signatures(wm_doc)
    clean_metadata(wm_doc)
    wm_doc.save(path, garbage=4, deflate=True)
    wm_doc.close()

def push_history():
    doc = state['doc']
    if not doc:
        return
    buf = doc.tobytes(garbage=1)
    state['history'].append(buf)
    if len(state['history']) > MAX_HISTORY:
        state['history'].pop(0)


def find_unicode_font():
    candidates = [
        'C:/Windows/Fonts/calibri.ttf',
        'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/segoeui.ttf',
        'C:/Windows/Fonts/tahoma.ttf',
        'C:/Windows/Fonts/verdana.ttf',
    ]
    for f in candidates:
        if os.path.exists(f):
            name = os.path.splitext(os.path.basename(f))[0]
            return f, name
    return None, None


UNICODE_FONT, UNICODE_FONTNAME = find_unicode_font()

_FONT_RATIO_CACHE = {}  # fontfile → (ascender - descender) per em


def _sys_font_ratio(fontfile):
    """Return ascender-descender ratio for the given font file (cached)."""
    if fontfile not in _FONT_RATIO_CACHE:
        try:
            f = fitz.Font(fontfile=fontfile)
            ratio = f.ascender - f.descender
            _FONT_RATIO_CACHE[fontfile] = ratio if ratio > 0.1 else 1.2
        except Exception:
            _FONT_RATIO_CACHE[fontfile] = 1.2
    return _FONT_RATIO_CACHE[fontfile]


def resolve_font(pdf_fontname, flags=0):
    """PDF font adı + flags'ten Windows font dosyasını bul."""
    name = pdf_fontname or ''
    is_bold   = bool(flags & 16) or any(k in name.lower() for k in ['bold','heavy','black','demi'])
    is_italic = bool(flags & 2)  or any(k in name.lower() for k in ['italic','oblique','slant'])

    base = name.lower()
    for tok in ['bolditalic','bold','italic','oblique','regular','medium',
                '-mt','mt','-ps','ps','narrow','condensed','+']:
        base = base.replace(tok, '')
    base = base.strip(' -_').replace(' ', '')

    FONTS = 'C:/Windows/Fonts/'
    # (regular, bold, italic, bold+italic)
    MAP = {
        'calibri':       ('calibri.ttf',  'calibrib.ttf', 'calibrii.ttf', 'calibriz.ttf'),
        'arial':         ('arial.ttf',    'arialbd.ttf',  'ariali.ttf',   'arialbi.ttf'),
        'timesnewroman': ('times.ttf',    'timesbd.ttf',  'timesi.ttf',   'timesbi.ttf'),
        'times':         ('times.ttf',    'timesbd.ttf',  'timesi.ttf',   'timesbi.ttf'),
        'helvetica':     ('arial.ttf',    'arialbd.ttf',  'ariali.ttf',   'arialbi.ttf'),
        'verdana':       ('verdana.ttf',  'verdanab.ttf', 'verdanai.ttf', 'verdanaz.ttf'),
        'tahoma':        ('tahoma.ttf',   'tahomabd.ttf', 'tahoma.ttf',   'tahomabd.ttf'),
        'trebuchet':     ('trebuc.ttf',   'trebucbd.ttf', 'trebucit.ttf', 'trebucbi.ttf'),
        'georgia':       ('georgia.ttf',  'georgiab.ttf', 'georgiai.ttf', 'georgiaz.ttf'),
        'courier':       ('cour.ttf',     'courbd.ttf',   'couri.ttf',    'courbi.ttf'),
        'segoeui':       ('segoeui.ttf',  'segoeuib.ttf', 'segoeuii.ttf', 'segoeuiz.ttf'),
        'cambria':       ('cambria.ttc',  'cambriab.ttf', 'cambriai.ttf', 'cambriaz.ttf'),
        'garamond':      ('GARA.TTF',     'GARAB.TTF',    'GARAI.TTF',    'GARABI.TTF'),
    }

    idx = (1 if is_bold else 0) + (2 if is_italic else 0)
    for key, files in MAP.items():
        if key in base:
            for attempt_idx in [idx, 0]:
                f = FONTS + files[attempt_idx]
                if os.path.exists(f):
                    return f, os.path.splitext(os.path.basename(f))[0], is_bold, is_italic

    return UNICODE_FONT, UNICODE_FONTNAME, is_bold, is_italic


def size_at_rect(page, rect):
    """rect.height based geometric font size — more reliable than span['size']."""
    return round(rect.height * 0.82, 1)


def _get_baseline_y(page, rect, page_dict=None):
    """Return the baseline y of the span whose bbox contains the center of rect."""
    if page_dict is None:
        page_dict = page.get_text('dict')
    cy = (rect.y0 + rect.y1) / 2
    cx = (rect.x0 + rect.x1) / 2
    for b in page_dict['blocks']:
        if b.get('type') != 0:
            continue
        for line in b.get('lines', []):
            for span in line.get('spans', []):
                b0, b1, b2, b3 = span['bbox']
                if b1 <= cy <= b3 and b0 <= cx <= b2:
                    return span['origin'][1]
    # Fallback: for text without descenders the tight bbox bottom ≈ baseline.
    return rect.y1


def _has_underline(bbox, drawings):
    """Detect underline by checking pre-fetched drawings for a horizontal line below bbox."""
    x0, y0, x1, y1 = bbox
    margin = max((y1 - y0) * 0.4, 3)
    for path in drawings:
        for item in path.get('items', []):
            if item[0] != 'l':
                continue
            p1, p2 = item[1], item[2]
            if abs(p1.y - p2.y) > 1.5:
                continue
            ly = (p1.y + p2.y) / 2
            if not (y1 - 2 <= ly <= y1 + margin):
                continue
            lx0, lx1 = min(p1.x, p2.x), max(p1.x, p2.x)
            if lx0 < x1 and lx1 > x0:
                return True
    return False


@app.route('/')
def index():
    demo = is_demo()
    resp = make_response(render_template('index.html', demo_mode=demo, can_activate=demo))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route('/activate')
def activate_page():
    if not is_demo():
        return redirect('/')
    return render_template('activate.html')


@app.route('/api/activate', methods=['POST'])
def api_activate():
    global _licensed_cache
    key = request.json.get('license_key', '').strip().upper()
    if not key:
        return jsonify({'ok': False, 'error': 'Lisans anahtarı boş'})
    ok, msg = _lic.activate(key)
    if ok:
        _licensed_cache = True
    return jsonify({'ok': ok, 'message': msg if ok else None, 'error': msg if not ok else None})



@app.route('/api/open', methods=['POST'])
def api_open():
    data = request.json or {}
    path = (data.get('path') or '').strip().strip('"')
    password = data.get('password')
    if not path or not os.path.exists(path):
        return jsonify({'ok': False, 'error': f'Dosya bulunamadı: {path}'})
    try:
        doc = fitz.open(path)
        if doc.needs_pass:
            if password is None:
                doc.close()
                return jsonify({'ok': False, 'needs_password': True,
                                'error': 'Bu PDF şifreli. Açmak için şifreyi girin.'})
            if not doc.authenticate(password):
                doc.close()
                return jsonify({'ok': False, 'needs_password': True, 'wrong_password': True,
                                'error': 'Şifre yanlış.'})
        truncated = _demo_truncate(doc)
        _swap_doc(doc, path, data.get('name'))
        sigs   = detect_signatures(doc)
        fields = detect_form_fields(doc)
        return jsonify({'ok': True, 'pages': len(doc), 'name': _doc_name(),
                        'signatures': sigs, 'form_fields': fields,
                        'demo_truncated': truncated})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})



@app.route('/api/print')
def api_print():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Açık dosya yok'})
    if is_demo():
        return jsonify({'ok': False, 'error': DEMO_FEATURE_MSG})
    try:
        # Yapılan düzenlemeler yazdırılsın diye geçerli belge geçici dosyaya kaydedilir
        fd, tmp = tempfile.mkstemp(suffix='.pdf', prefix='pdfeditor_yazdir_')
        os.close(fd)
        doc.save(tmp, garbage=1, deflate=True)
        os.startfile(tmp, 'print')
        return jsonify({'ok': True})
    except AttributeError:
        return jsonify({'ok': False, 'error': 'Yazdırma yalnızca Windows\'ta desteklenir'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/text')
def api_text():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Açık dosya yok'})
    try:
        text = '\n\n'.join(doc[i].get_text() for i in range(len(doc)))
        return jsonify({'ok': True, 'text': text, 'chars': len(text)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/demo/open')
def demo_open():
    try:
        import io as _io
        doc = fitz.open()

        cyan = (0.03, 0.57, 0.7)
        dark = (0.08, 0.09, 0.15)
        gray = (0.40, 0.40, 0.40)

        def page1(d):
            p = d.new_page(width=595, height=842)
            p.insert_text((72, 80),  "Acme Corporation",                fontname="helv", fontsize=22, color=cyan)
            p.insert_text((72, 114), "Q3 2024 Project Summary Report",  fontname="helv",      fontsize=15, color=dark)
            p.draw_line(fitz.Point(72, 128), fitz.Point(523, 128), color=cyan, width=1.5)
            p.insert_text((72, 158), "Executive Summary",               fontname="helv", fontsize=13, color=dark)
            for i, line in enumerate([
                "This report provides a comprehensive overview of ACME Corporation's",
                "performance during Q3 2024. Key highlights include an 18% increase",
                "in revenue, 47 new client acquisitions, and 23 projects completed.",
            ]):
                p.insert_text((72, 183 + i*18), line, fontname="helv", fontsize=11)
            p.insert_text((72, 268), "Financial Overview",              fontname="helv", fontsize=13, color=dark)
            for i, line in enumerate([
                "Total Revenue:   $2,400,000",
                "Operating Costs: $1,560,000",
                "Net Profit:      $840,000",
                "Profit Margin:   35%",
            ]):
                p.insert_text((72, 293 + i*20), line, fontname="helv", fontsize=11)

        def page2(d):
            p = d.new_page(width=595, height=842)
            p.insert_text((72, 80), "Project Status Report", fontname="helv", fontsize=18, color=cyan)
            p.draw_line(fitz.Point(72, 100), fitz.Point(523, 100), color=cyan, width=1.5)
            p.insert_text((72, 130), "Completed Projects",   fontname="helv", fontsize=13, color=dark)
            for i, line in enumerate([
                "Alpha  - Web Platform Redesign      COMPLETE",
                "Beta   - Mobile App Launch          COMPLETE",
                "Gamma  - Database Migration         COMPLETE",
                "Delta  - API Integration            COMPLETE",
            ]):
                p.insert_text((72, 158 + i*22), f"• {line}", fontname="helv", fontsize=11)

        def page3(d):
            p = d.new_page(width=595, height=842)
            p.insert_text((72, 80), "Q4 2024 Outlook",      fontname="helv", fontsize=18, color=cyan)
            p.draw_line(fitz.Point(72, 100), fitz.Point(523, 100), color=cyan, width=1.5)
            p.insert_text((72, 130), "Strategic priorities for the upcoming quarter:", fontname="helv", fontsize=12)
            for i, line in enumerate([
                "Expand into European markets",
                "Launch 3 new product lines",
                "Hire 15 additional engineers",
                "Achieve ISO 27001 certification",
            ]):
                p.insert_text((72, 162 + i*24), f"  {i+1}. {line}", fontname="helv", fontsize=11)
            p.insert_text((72, 720), "Prepared by: Finance & Strategy Team", fontname="helv", fontsize=10, color=gray)
            p.insert_text((72, 738), "Date: October 2024",                   fontname="helv", fontsize=10, color=gray)

        page1(doc); page2(doc); page3(doc)

        buf = _io.BytesIO()
        doc.save(buf)
        doc.close()
        buf.seek(0)

        tf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', prefix='demo_')
        tf.write(buf.read()); tf.close()

        if state['doc']:
            state['doc'].close()
        _TMP_FILES.append(tf.name)
        state['doc'] = fitz.open(tf.name)
        state['path'] = tf.name
        state['name'] = 'Demo_Report.pdf'
        state['history'] = []
        return jsonify({'ok': True, 'pages': len(state['doc']), 'name': 'Demo_Report.pdf'})
    except Exception as e:
        import traceback as _tb
        return jsonify({'ok': False, 'error': str(e), 'trace': _tb.format_exc()})


@app.route('/api/thumb/<int:i>')
def api_thumb(i):
    doc = state['doc']
    if not doc or i >= len(doc):
        return ('', 404)
    mat = fitz.Matrix(0.25, 0.25)
    pix = doc[i].get_pixmap(matrix=mat)
    return app.response_class(pix.tobytes('png'), mimetype='image/png')


@app.route('/api/page/<int:i>')
def api_page(i):
    doc = state['doc']
    if not doc or i >= len(doc):
        return ('', 404)
    mat = fitz.Matrix(2.0, 2.0)
    pix = doc[i].get_pixmap(matrix=mat)
    data = base64.b64encode(pix.tobytes('png')).decode()
    return jsonify({
        'ok': True,
        'img': data,
        'pdf_w': doc[i].rect.width,
        'pdf_h': doc[i].rect.height,
        'zoom': 2.0
    })


@app.route('/api/delete', methods=['POST'])
def api_delete():
    """Deletes one page ({i}) or several ({pages: [...]}) as a single undo step."""
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    data = request.json or {}
    pages = data.get('pages')
    if pages is None:
        pages = [data.get('i', -1)]
    try:
        pages = sorted({int(i) for i in pages})
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'Geçersiz sayfa'})
    if not pages or pages[0] < 0 or pages[-1] >= len(doc):
        return jsonify({'ok': False, 'error': 'Geçersiz sayfa'})
    if len(pages) >= len(doc):
        return jsonify({'ok': False, 'error': 'Tüm sayfalar silinemez; en az bir sayfa kalmalı'})
    push_history()
    drop = set(pages)
    doc.select([i for i in range(len(doc)) if i not in drop])
    return jsonify({'ok': True, 'pages': len(doc), 'deleted': len(pages)})


@app.route('/api/rotate', methods=['POST'])
def api_rotate():
    """Rotates one page ({i}) or several ({pages: [...]}) as a single undo step."""
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    data = request.json or {}
    pages = data.get('pages')
    if pages is None:
        pages = [data.get('i', 0)]
    deg = data.get('deg', 90)
    try:
        pages = sorted({int(i) for i in pages})
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'Geçersiz sayfa'})
    if not pages or pages[0] < 0 or pages[-1] >= len(doc):
        return jsonify({'ok': False, 'error': 'Geçersiz sayfa'})
    push_history()
    for i in pages:
        page = doc[i]
        page.set_rotation((page.rotation + deg) % 360)
    return jsonify({'ok': True})



@app.route('/api/move', methods=['POST'])
def api_move():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    frm = int(request.json.get('from', 0))
    to = int(request.json.get('to', 0))
    n = len(doc)
    if not (0 <= frm < n and 0 <= to < n):
        return jsonify({'ok': False, 'error': 'Geçersiz sayfa'})
    if frm == to:
        return jsonify({'ok': True, 'pages': n})
    push_history()
    # PyMuPDF move_page(pno, to) sayfayı 'to' numaralı sayfanın ÖNÜNE koyar.
    # 'to' = sayfanın yeni konumu olacak şekilde çeviriyoruz.
    target = to if to < frm else (to + 1 if to + 1 < n else -1)
    doc.move_page(frm, target)
    return jsonify({'ok': True, 'pages': n})


@app.route('/api/findreplace', methods=['POST'])
def api_findreplace():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    find = request.json.get('find', '')
    repl = request.json.get('replace', '')
    if not find:
        return jsonify({'ok': False, 'error': 'Aranacak metin boş'})

    forced_size = float(request.json.get('size', 0))
    pdf_font    = request.json.get('pdf_font', None)
    font_flags  = int(request.json.get('flags', 0))

    # Inline-edit sends page_idx + block coords → replace only that one occurrence.
    page_idx       = request.json.get('page_idx', None)
    bx0            = request.json.get('bx0', None)
    by0            = request.json.get('by0', None)
    bx1            = request.json.get('bx1', None)
    by1            = request.json.get('by1', None)
    # Exact baseline and color captured from original span (only sent by inline-edit).
    provided_baseline = request.json.get('baseline_y', None)
    provided_color    = request.json.get('color', None)
    single_occurrence = page_idx is not None and bx0 is not None

    push_history()
    total = 0
    pages_to_search = [doc[page_idx]] if single_occurrence else list(doc)

    for page in pages_to_search:
        hits = page.search_for(find)
        if not hits:
            continue

        if single_occurrence:
            pdf_w = page.rect.width
            pdf_h = page.rect.height
            block_rect = fitz.Rect(bx0 * pdf_w, by0 * pdf_h, bx1 * pdf_w, by1 * pdf_h)

            def overlap(r):
                inter = r.intersect(block_rect)
                return inter.width * inter.height if not inter.is_empty else 0

            hits = [max(hits, key=overlap)]

        # Collect sizes and baselines BEFORE redaction removes the text.
        page_dict = page.get_text('dict')
        sizes     = [forced_size if forced_size else size_at_rect(page, r) for r in hits]
        baselines = [_get_baseline_y(page, r, page_dict) for r in hits]

        for rect in hits:
            page.add_redact_annot(rect, fill=(1, 1, 1))
        page.apply_redactions(graphics=0)

        if repl:
            for rect, sz, fallback_bl in zip(hits, sizes, baselines):
                bl_y  = provided_baseline if provided_baseline is not None else fallback_bl
                color = tuple(provided_color) if provided_color else (0, 0, 0)
                kw = {'fontsize': sz, 'color': color}
                if pdf_font:
                    ff, fn, _, _ = resolve_font(pdf_font, font_flags)
                    if ff:
                        kw['fontfile'] = ff
                        kw['fontname'] = fn
                    elif UNICODE_FONT:
                        kw['fontfile'] = UNICODE_FONT
                        kw['fontname'] = UNICODE_FONTNAME
                elif UNICODE_FONT:
                    kw['fontfile'] = UNICODE_FONT
                    kw['fontname'] = UNICODE_FONTNAME
                page.insert_text(fitz.Point(rect.x0, bl_y), repl, **kw)
        total += len(hits)

    return jsonify({'ok': True, 'count': total})


@app.route('/api/replaceblock', methods=['POST'])
def api_replaceblock():
    """Tüm bloğu sil, yeni metni sol kenardan yaz — gap ve font tutarsızlığını önler."""
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    data       = request.json
    page_idx   = data['page_idx']
    bx0, by0   = data['bx0'], data['by0']
    bx1, by1   = data['bx1'], data['by1']
    baseline_y = data['baseline_y']
    new_text   = data.get('replace', '')
    pdf_font   = data.get('pdf_font', None)
    # Kullanıcının UI'dan gönderdiği bold/italic override'ı varsa kullan,
    # yoksa flags'ten al ama bold bitini temizle — embed fontlar çoğunlukla
    # sistem bold fontundan daha ince göründüğü için.
    force_bold   = data.get('force_bold', None)   # None = otomatik
    force_italic = data.get('force_italic', None)  # None = flags'ten al
    underline    = bool(data.get('underline', False))
    font_flags   = int(data.get('flags', 0))
    if force_bold is None:
        effective_flags = font_flags
    else:
        effective_flags = (font_flags | 16) if force_bold else (font_flags & ~16)
    if force_italic is not None:
        effective_flags = (effective_flags | 2) if force_italic else (effective_flags & ~2)
    sz         = float(data.get('size', 12))
    color      = tuple(data.get('color', [0, 0, 0]))

    page = doc[page_idx]
    pdf_w, pdf_h = page.rect.width, page.rect.height
    block_rect = fitz.Rect(bx0 * pdf_w, by0 * pdf_h, bx1 * pdf_w, by1 * pdf_h)

    sz = max(sz, 5.0)

    push_history()
    page.add_redact_annot(block_rect, fill=(1, 1, 1))
    page.apply_redactions(graphics=0)

    if new_text:
        kw = {'fontsize': sz, 'color': color}
        if pdf_font:
            # When effective_flags has no bold bit, also strip "bold" from the
            # font name so resolve_font's name-based detection doesn't re-enable
            # bold. (e.g. "CalibriBold" with flags=0 → look up as "Calibri")
            lookup_font = pdf_font
            if not (effective_flags & 16):
                lookup_font = re.sub(r'(?i)(bold|heavy|black|demi)', '', lookup_font).strip(' -_') or lookup_font
            if not (effective_flags & 2):
                lookup_font = re.sub(r'(?i)(italic|oblique|slant)', '', lookup_font).strip(' -_') or lookup_font
            ff, fn, _, _ = resolve_font(lookup_font, effective_flags)
            if ff:
                kw['fontfile'] = ff
                kw['fontname'] = fn
            elif UNICODE_FONT:
                kw['fontfile'] = UNICODE_FONT
                kw['fontname'] = UNICODE_FONTNAME
        elif UNICODE_FONT:
            kw['fontfile'] = UNICODE_FONT
            kw['fontname'] = UNICODE_FONTNAME
        page.insert_text(fitz.Point(block_rect.x0, baseline_y), new_text, **kw)
        if underline:
            try:
                ff = kw.get('fontfile')
                font = fitz.Font(fontfile=ff) if ff else fitz.Font('helv')
                tw = font.text_length(new_text, fontsize=sz)
            except Exception:
                tw = block_rect.width
            ul_y = baseline_y + sz * 0.12
            page.draw_line(
                fitz.Point(block_rect.x0, ul_y),
                fitz.Point(block_rect.x0 + tw, ul_y),
                color=color, width=max(0.5, sz * 0.04)
            )

    return jsonify({'ok': True})



@app.route('/api/redact', methods=['POST'])
def api_redact():
    """Seçili alanı GERÇEKTEN siler: alttaki metin ve görsel içerik PDF'ten kaldırılır.
    (Üstüne beyaz kutu çizmek metni silmez; kopyalanıp okunabilir kalırdı.)"""
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    data  = request.json
    page  = doc[data['page']]
    pdf_w, pdf_h = page.rect.width, page.rect.height
    rect  = fitz.Rect(
        data['x0'] * pdf_w, data['y0'] * pdf_h,
        data['x1'] * pdf_w, data['y1'] * pdf_h
    )
    push_history()
    page.add_redact_annot(rect, fill=(1, 1, 1))
    page.apply_redactions(images=getattr(fitz, 'PDF_REDACT_IMAGE_PIXELS', 2), graphics=0)
    return jsonify({'ok': True})


@app.route('/api/movetext', methods=['POST'])
def api_movetext():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    data   = request.json
    page   = doc[data['page']]
    pdf_w, pdf_h = page.rect.width, page.rect.height

    old_rect = fitz.Rect(
        data['bx0'] * pdf_w, data['by0'] * pdf_h,
        data['bx1'] * pdf_w, data['by1'] * pdf_h
    )
    new_x  = float(data['new_x'])
    new_bl = float(data['new_baseline_y'])
    text   = data['text']
    size   = float(data.get('size', 12))
    color  = tuple(data.get('color', [0, 0, 0]))

    push_history()
    page.add_redact_annot(old_rect, fill=(1, 1, 1))
    page.apply_redactions(graphics=0)

    kw = {'fontsize': size, 'color': color}
    if UNICODE_FONT:
        kw['fontfile'] = UNICODE_FONT
        kw['fontname'] = UNICODE_FONTNAME
    page.insert_text(fitz.Point(new_x, new_bl), text, **kw)
    return jsonify({'ok': True})


@app.route('/api/addtext', methods=['POST'])
def api_addtext():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    i       = request.json.get('page', 0)
    text    = request.json.get('text', '')
    x       = request.json.get('x', 72)
    y       = request.json.get('y', 72)
    size    = request.json.get('size', 12)
    pdf_font = request.json.get('pdf_font', None)
    flags   = int(request.json.get('flags', 0))
    raw_color = request.json.get('color', None)
    if not text:
        return jsonify({'ok': False, 'error': 'Metin boş'})
    page = doc[i]
    push_history()
    if pdf_font:
        font_file, font_name, _, _ = resolve_font(pdf_font, flags)
    else:
        font_file, font_name = UNICODE_FONT, UNICODE_FONTNAME
    kw = {'fontsize': float(size), 'color': tuple(raw_color) if raw_color else (0, 0, 0)}
    if font_file:
        kw['fontfile'] = font_file
        kw['fontname'] = font_name
    page.insert_text(fitz.Point(x, y), text, **kw)
    return jsonify({'ok': True})


@app.route('/api/merge', methods=['POST'])
def api_merge():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    path = request.json.get('path', '').strip().strip('"')
    pos = request.json.get('pos', 'end')
    try:
        src = fitz.open(path)
        if is_demo() and len(doc) + len(src) > DEMO_MAX_PAGES:
            src.close()
            return jsonify({'ok': False, 'error': DEMO_LIMIT_MSG})
        push_history()
        if pos == 'end':
            doc.insert_pdf(src)
        else:
            doc.insert_pdf(src, start_at=0)
        src.close()
        return jsonify({'ok': True, 'pages': len(doc)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/split', methods=['POST'])
def api_split():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    start = request.json.get('start', 0)
    end = request.json.get('end', len(doc) - 1)
    path = request.json.get('path', '').strip().strip('"')
    if not path:
        path = _default_out(f'_sayfa{start + 1}-{end + 1}')
    try:
        new_doc = fitz.open()
        new_doc.insert_pdf(doc, from_page=start, to_page=end)
        if is_demo():
            _apply_demo_watermark(new_doc)
        new_doc.save(path, garbage=4, deflate=True)
        new_doc.close()
        return jsonify({'ok': True, 'path': path})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/save', methods=['POST'])
def api_save():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    path = request.json.get('path', '').strip().strip('"')
    if not path:
        path = _default_out('_duzenlendi')
    try:
        if is_demo():
            _save_with_watermark(doc, path)
            return jsonify({'ok': True, 'path': path, 'stripped_signatures': 0})
        stripped = strip_signatures(doc)
        clean_metadata(doc)
        doc.save(path, garbage=4, deflate=True)
        return jsonify({'ok': True, 'path': path, 'stripped_signatures': stripped})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/browse')
def api_browse():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes('-topmost', 1)
        path = filedialog.askopenfilename(
            parent=root,
            title='PDF Seç',
            filetypes=[('PDF Dosyaları', '*.pdf')]
        )
        root.destroy()
        return jsonify({'path': path or ''})
    except Exception as e:
        return jsonify({'path': '', 'error': str(e)})


@app.route('/api/browse_save')
def api_browse_save():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes('-topmost', 1)
        orig = Path(state.get('path', 'belge.pdf'))
        downloads = Path.home() / 'Downloads'
        path = filedialog.asksaveasfilename(
            parent=root,
            title='PDF Olarak Kaydet',
            initialdir=str(downloads),
            initialfile=orig.stem + '_duzenlendi.pdf',
            defaultextension='.pdf',
            filetypes=[('PDF Dosyaları', '*.pdf')]
        )
        root.destroy()
        return jsonify({'path': path or ''})
    except Exception as e:
        return jsonify({'path': '', 'error': str(e)})



@app.route('/api/export_dest')
def api_export_dest():
    """Dışa aktarma için 'Kaydet' penceresi (kaydedilecek yeri kullanıcı seçer)."""
    name = Path(request.args.get('name', 'export')).name or 'export'
    ext = Path(name).suffix.lower()
    if ext not in ('.docx', '.xlsx', '.pptx', '.png', '.jpg', '.zip', '.txt', '.epub', '.azw3'):
        return jsonify({'path': '', 'error': 'Geçersiz dosya türü'})
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes('-topmost', 1)
        path = filedialog.asksaveasfilename(
            parent=root,
            title='Dışa Aktar - Kaydedilecek Yeri Seç',
            initialdir=str(_out_dir()),
            initialfile=name,
            defaultextension=ext,
            filetypes=[(ext[1:].upper() + ' dosyası', '*' + ext)]
        )
        root.destroy()
        state['export_dest'] = path or None
        return jsonify({'path': path or ''})
    except Exception as e:
        return jsonify({'path': '', 'error': str(e)})


@app.route('/api/export_write', methods=['POST'])
def api_export_write():
    """Kullanıcının seçtiği yola (yalnızca /api/export_dest ile seçilen) dışa aktarılan veriyi yazar."""
    dest = state.pop('export_dest', None)
    if not dest:
        return jsonify({'ok': False, 'error': 'Kayıt yeri seçilmedi'})
    try:
        with open(dest, 'wb') as f:
            f.write(request.get_data())
        return jsonify({'ok': True, 'path': dest})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/upload', methods=['POST'])
def api_upload():
    f = request.files.get('file')
    if not f:
        return jsonify({'ok': False, 'error': 'Dosya yok'})
    tmp = _tmp_path('.pdf')
    f.save(tmp)
    try:
        doc = fitz.open(tmp)
        if doc.needs_pass:
            pw = request.form.get('password')
            if pw is None or not doc.authenticate(pw):
                doc.close()
                return jsonify({'ok': False, 'needs_password': True, 'tmp_path': tmp,
                                'name': f.filename,
                                'error': 'Bu PDF şifreli. Açmak için şifreyi girin.'})
        truncated = _demo_truncate(doc)
        _swap_doc(doc, tmp, f.filename)
        _cleanup_tmp(keep=tmp)
        sigs   = detect_signatures(doc)
        fields = detect_form_fields(doc)
        return jsonify({'ok': True, 'pages': len(doc), 'name': f.filename,
                        'signatures': sigs, 'form_fields': fields,
                        'demo_truncated': truncated})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/textblocks/<int:i>')
def api_textblocks(i):
    doc = state['doc']
    if not doc or i >= len(doc):
        return jsonify({'ok': False})
    page = doc[i]
    pdf_w = page.rect.width
    pdf_h = page.rect.height
    result = []
    for b in page.get_text('dict')['blocks']:
        if b.get('type') != 0:
            continue
        for line in b.get('lines', []):
            spans = line.get('spans', [])
            if not spans:
                continue
            full_text = ''.join(s.get('text', '') for s in spans).strip()
            if not full_text:
                continue
            bbox = line['bbox']
            geo_size = round((bbox[3] - bbox[1]) * 0.82, 1)
            first_span = next((s for s in spans if s.get('text', '').strip()), spans[0])
            baseline_y = first_span['origin'][1]
            raw_color  = first_span.get('color', 0)
            text_color = [
                ((raw_color >> 16) & 0xFF) / 255,
                ((raw_color >> 8)  & 0xFF) / 255,
                (raw_color         & 0xFF) / 255,
            ]
            # span_size is the true PDF font size; geo_size is the visual estimate.
            # Use span_size for move/replace so it doesn't shrink each operation.
            span_size = first_span.get('size', geo_size)
            bbox_h = bbox[3] - bbox[1]
            ff_sys, _, _, _ = resolve_font(first_span.get('font', ''), first_span.get('flags', 0))
            if not ff_sys:
                ff_sys = UNICODE_FONT
            sys_size = round(bbox_h / _sys_font_ratio(ff_sys), 1) if ff_sys else geo_size
            result.append({
                'text': full_text,
                'x0': bbox[0] / pdf_w,
                'y0': bbox[1] / pdf_h,
                'x1': bbox[2] / pdf_w,
                'y1': bbox[3] / pdf_h,
                'size': geo_size,
                'span_size': span_size,
                'sys_size': sys_size,
                'baseline_y': baseline_y,
                'color': text_color,
                'font': first_span.get('font', ''),
                'flags': first_span.get('flags', 0),
                'underline': False,
            })
    return jsonify({'ok': True, 'blocks': result})


@app.route('/api/undo', methods=['POST'])
def api_undo():
    if not state['history']:
        return jsonify({'ok': False, 'error': 'Geri alınacak işlem yok'})
    buf = state['history'].pop()
    if state['doc']:
        state['doc'].close()
    state['doc'] = fitz.open(stream=buf, filetype='pdf')
    return jsonify({'ok': True, 'pages': len(state['doc'])})


@app.route('/api/status')
def api_status():
    if state['doc']:
        return jsonify({'ok': True, 'pages': len(state['doc']), 'name': _doc_name()})
    return jsonify({'ok': False})



@app.route('/api/export/images')
def api_export_images():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    mat = fitz.Matrix(2.0, 2.0)
    stem = _doc_stem()
    src = doc
    if is_demo():
        # Demo: dışa aktarılan görseller de filigranlı olsun
        src = fitz.open(stream=doc.tobytes(garbage=1), filetype='pdf')
        _apply_demo_watermark(src)
    try:
        if len(src) == 1:
            pix = src[0].get_pixmap(matrix=mat)
            buf = io.BytesIO(pix.tobytes('png'))
            return send_file(buf, mimetype='image/png',
                             as_attachment=True,
                             download_name=f'{stem}.png')
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for i, page in enumerate(src):
                pix = page.get_pixmap(matrix=mat)
                zf.writestr(f'sayfa_{i + 1:03d}.png', pix.tobytes('png'))
        buf.seek(0)
        return send_file(buf, mimetype='application/zip',
                         as_attachment=True,
                         download_name=f'{stem}_sayfalar.zip')
    finally:
        if src is not doc:
            src.close()


@app.route('/api/export/txt')
def api_export_txt():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    parts = []
    for i, page in enumerate(doc):
        parts.append(f'--- Sayfa {i + 1} ---')
        parts.append(page.get_text())
    buf = io.BytesIO('\n'.join(parts).encode('utf-8-sig'))
    stem = _doc_stem()
    return send_file(buf, mimetype='text/plain; charset=utf-8',
                     as_attachment=True,
                     download_name=f'{stem}.txt')


def _find_ebook_convert():
    """Calibre's converter, if Calibre is installed (needed only for AZW3)."""
    import shutil
    for base in (os.environ.get('ProgramFiles', r'C:\Program Files'),
                 os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'),
                 os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs')):
        for sub in ('Calibre2', 'Calibre'):
            exe = os.path.join(base, sub, 'ebook-convert.exe')
            if os.path.isfile(exe):
                return exe
    return shutil.which('ebook-convert')


def _epub_bytes(doc):
    from epub_export import build_epub
    return build_epub(doc, title=_doc_stem())


@app.route('/api/export/epub')
def api_export_epub():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    if is_demo():
        return jsonify({'ok': False, 'error': DEMO_FEATURE_MSG})
    return send_file(io.BytesIO(_epub_bytes(doc)), mimetype='application/epub+zip',
                     as_attachment=True, download_name=f'{_doc_stem()}.epub')


@app.route('/api/export/azw3')
def api_export_azw3():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    if is_demo():
        return jsonify({'ok': False, 'error': DEMO_FEATURE_MSG})
    exe = _find_ebook_convert()
    if not exe:
        return jsonify({'ok': False, 'error': 'AZW3 için ücretsiz Calibre programı gerekiyor (calibre-ebook.com). '
                                              "Kindle'a göndermek için EPUB yeterlidir."})
    import subprocess
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = os.path.join(tmp, 'book.epub'), os.path.join(tmp, 'book.azw3')
        with open(src, 'wb') as f:
            f.write(_epub_bytes(doc))
        r = subprocess.run([exe, src, dst], capture_output=True, timeout=600,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if r.returncode != 0 or not os.path.isfile(dst):
            return jsonify({'ok': False, 'error': 'Calibre dönüştürmesi başarısız oldu.'})
        with open(dst, 'rb') as f:
            data = f.read()
    return send_file(io.BytesIO(data), mimetype='application/octet-stream',
                     as_attachment=True, download_name=f'{_doc_stem()}.azw3')


@app.route('/api/kindle_prepare', methods=['POST'])
def api_kindle_prepare():
    """Saves the EPUB next to the other outputs so it can be mailed or uploaded to Kindle."""
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    if is_demo():
        return jsonify({'ok': False, 'error': DEMO_FEATURE_MSG})
    path = _default_out('')[:-4] + '.epub'
    n = 2
    while os.path.exists(path):
        path = _default_out('')[:-4] + f' ({n}).epub'
        n += 1
    data = _epub_bytes(doc)
    with open(path, 'wb') as f:
        f.write(data)
    return jsonify({'ok': True, 'path': path, 'size_kb': len(data) // 1024})


@app.route('/api/open_link', methods=['POST'])
def api_open_link():
    links = {
        'kindle_settings': 'https://www.amazon.com/hz/mycd/myx#/home/settings/pdoc',
        'calibre': 'https://calibre-ebook.com/download_windows',
    }
    url = links.get((request.json or {}).get('key'))
    if not url:
        return jsonify({'ok': False})
    webbrowser.open(url)
    return jsonify({'ok': True})


@app.route('/api/export/docx')
def api_export_docx():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    if is_demo():
        return jsonify({'ok': False, 'error': DEMO_FEATURE_MSG})
    try:
        from pdf2docx import Converter
    except ImportError:
        return jsonify({'ok': False, 'error': 'Word dönüştürücü yüklü değil. Kurmak için: pip install pdf2docx'})
    tmp_pdf = tempfile.mktemp(suffix='.pdf')
    tmp_docx = tempfile.mktemp(suffix='.docx')
    try:
        doc.save(tmp_pdf, garbage=4, deflate=True)
        cv = Converter(tmp_pdf)
        cv.convert(tmp_docx, start=0, end=None)
        cv.close()
        with open(tmp_docx, 'rb') as f:
            data = f.read()
        buf = io.BytesIO(data)
        stem = _doc_stem()
        return send_file(
            buf,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name=f'{stem}.docx')
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Dönüştürme hatası: {e}'})
    finally:
        for p in [tmp_pdf, tmp_docx]:
            try:
                os.unlink(p)
            except Exception:
                pass


_SIG_TYPE = getattr(fitz, 'PDF_WIDGET_TYPE_SIGNATURE', 7)


def detect_form_fields(doc) -> int:
    count = 0
    for page in doc:
        try:
            for w in page.widgets():
                if w.field_type != _SIG_TYPE:
                    count += 1
        except Exception:
            pass
    return count


def detect_signatures(doc) -> int:
    count = 0
    for page in doc:
        try:
            for w in page.widgets():
                if w.field_type == _SIG_TYPE:
                    count += 1
        except Exception:
            pass
    return count


def strip_signatures(doc) -> int:
    removed = 0
    for page in doc:
        try:
            to_del = [w for w in page.widgets() if w.field_type == _SIG_TYPE]
            for w in to_del:
                page.delete_widget(w)
                removed += 1
        except Exception:
            pass
    try:
        cat = doc.pdf_catalog()
        for key in ('Perms', 'DSS', 'SigFlags'):
            try:
                doc.xref_set_key(cat, key, 'null')
            except Exception:
                pass
    except Exception:
        pass
    return removed


def clean_metadata(doc):
    """Remove XMP stream and erase tool-identifying metadata fields."""
    try:
        doc.del_xml_metadata()
    except Exception:
        pass
    try:
        meta = dict(doc.metadata)
        meta['producer'] = ''
        meta['creator'] = ''
        meta['modDate'] = ''
        doc.set_metadata(meta)
    except Exception:
        pass


def _hex_to_rgb(h: str):
    h = h.lstrip('#')
    return int(h[0:2], 16)/255, int(h[2:4], 16)/255, int(h[4:6], 16)/255


@app.route('/api/reverse', methods=['POST'])
def api_reverse():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    push_history()
    doc.select(list(range(len(doc) - 1, -1, -1)))
    return jsonify({'ok': True, 'pages': len(doc)})


@app.route('/api/addblank', methods=['POST'])
def api_addblank():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    if is_demo() and len(doc) >= DEMO_MAX_PAGES:
        return jsonify({'ok': False, 'error': DEMO_LIMIT_MSG})
    pos = int(request.json.get('pos', len(doc)))
    pos = max(0, min(pos, len(doc)))
    push_history()
    doc.insert_page(pos)
    return jsonify({'ok': True, 'pages': len(doc)})


@app.route('/api/highlight', methods=['POST'])
def api_highlight():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    data = request.json
    page = doc[data['page']]
    pdf_w, pdf_h = page.rect.width, page.rect.height
    rect = fitz.Rect(
        data['x0'] * pdf_w, data['y0'] * pdf_h,
        data['x1'] * pdf_w, data['y1'] * pdf_h
    )
    r, g, b = _hex_to_rgb(data.get('color', '#FFD700'))
    push_history()
    shape = page.new_shape()
    shape.draw_rect(rect)
    shape.finish(color=None, fill=(r, g, b), fill_opacity=0.35, width=0)
    shape.commit()
    return jsonify({'ok': True})


@app.route('/api/shape', methods=['POST'])
def api_shape():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    data = request.json
    page = doc[data['page']]
    pdf_w, pdf_h = page.rect.width, page.rect.height
    rect = fitz.Rect(
        data['x0'] * pdf_w, data['y0'] * pdf_h,
        data['x1'] * pdf_w, data['y1'] * pdf_h
    )
    r, g, b = _hex_to_rgb(data.get('color', '#E53E3E'))
    push_history()
    shape = page.new_shape()
    if data.get('type') == 'circle':
        shape.draw_oval(rect)
    else:
        shape.draw_rect(rect)
    shape.finish(color=(r, g, b), fill=None, width=1.5)
    shape.commit()
    return jsonify({'ok': True})


@app.route('/api/stamp', methods=['POST'])
def api_stamp():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    data = request.json
    page = doc[data['page']]
    pdf_w, pdf_h = page.rect.width, page.rect.height
    x = float(data['x']) * pdf_w
    y = float(data['y']) * pdf_h
    stamp_type = data.get('stamp', 'check')
    size = float(data.get('size', 36))
    push_history()
    shape = page.new_shape()
    if stamp_type == 'check':
        p1 = fitz.Point(x, y + size * 0.5)
        p2 = fitz.Point(x + size * 0.38, y + size)
        p3 = fitz.Point(x + size, y + size * 0.05)
        shape.draw_polyline([p1, p2, p3])
        shape.finish(color=(0.06, 0.57, 0.12), width=3, closePath=False)
    elif stamp_type == 'cross':
        shape.draw_line(fitz.Point(x, y), fitz.Point(x + size, y + size))
        shape.finish(color=(0.86, 0.15, 0.15), width=3, closePath=False)
        shape.draw_line(fitz.Point(x + size, y), fitz.Point(x, y + size))
        shape.finish(color=(0.86, 0.15, 0.15), width=3, closePath=False)
    elif stamp_type == 'circle':
        cx, cy = x + size / 2, y + size / 2
        shape.draw_circle(fitz.Point(cx, cy), size / 2)
        shape.finish(color=(0.06, 0.39, 0.80), fill=None, width=2)
    elif stamp_type == 'date':
        from datetime import date as _date
        date_str = _date.today().strftime('%d.%m.%Y')
        kw = {'fontsize': size * 0.45, 'color': (0.06, 0.39, 0.80)}
        if UNICODE_FONT:
            kw['fontfile'] = UNICODE_FONT
            kw['fontname'] = UNICODE_FONTNAME
        shape.commit()
        page.insert_text(fitz.Point(x, y + size * 0.5), date_str, **kw)
        return jsonify({'ok': True})
    shape.commit()
    return jsonify({'ok': True})


@app.route('/api/addimage', methods=['POST'])
def api_addimage():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    data = request.json
    page = doc[data['page']]
    pdf_w, pdf_h = page.rect.width, page.rect.height
    rect = fitz.Rect(
        data['x0'] * pdf_w, data['y0'] * pdf_h,
        data['x1'] * pdf_w, data['y1'] * pdf_h
    )
    img_b64 = data.get('image', '')
    if ',' in img_b64:
        img_b64 = img_b64.split(',', 1)[1]
    img_bytes = base64.b64decode(img_b64)
    push_history()
    page.insert_image(rect, stream=img_bytes)
    return jsonify({'ok': True})


@app.route('/api/watermark', methods=['POST'])
def api_watermark():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    text = request.json.get('text', 'GİZLİ')
    opacity = float(request.json.get('opacity', 0.2))
    size = float(request.json.get('size', 48))
    push_history()
    for page in doc:
        pdf_w = page.rect.width
        pdf_h = page.rect.height
        try:
            font = fitz.Font(fontfile=UNICODE_FONT) if UNICODE_FONT else fitz.Font('helv')
            tw = fitz.TextWriter(page.rect)
            tw.append(fitz.Point(pdf_w * 0.1, pdf_h * 0.6), text, font=font, fontsize=size)
            pivot = fitz.Point(pdf_w / 2, pdf_h / 2)
            tw.write_text(page, color=(0.6, 0.6, 0.6), opacity=opacity,
                          morph=(pivot, fitz.Matrix(45)))
        except Exception:
            kw = {'fontsize': size, 'color': (0.6, 0.6, 0.6)}
            if UNICODE_FONT:
                kw['fontfile'] = UNICODE_FONT
                kw['fontname'] = UNICODE_FONTNAME
            page.insert_text(fitz.Point(pdf_w * 0.2, pdf_h * 0.55), text, **kw)
    return jsonify({'ok': True, 'pages': len(doc)})


@app.route('/api/removewatermark', methods=['POST'])
def api_removewatermark():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    text = request.json.get('text', '').strip()
    if not text:
        return jsonify({'ok': False, 'error': 'Silinecek metin boş'})
    push_history()
    total = 0
    for page in doc:
        hits = page.search_for(text)
        if hits:
            for rect in hits:
                expanded = rect + fitz.Rect(-6, -6, 6, 6)
                page.add_redact_annot(expanded, fill=(1, 1, 1))
            page.apply_redactions(graphics=0)
            total += len(hits)
        else:
            # search_for can miss rotated text; fall back to span scan
            found = []
            for block in page.get_text('dict')['blocks']:
                if block.get('type') != 0:
                    continue
                for line in block.get('lines', []):
                    for span in line.get('spans', []):
                        if text.lower() in span.get('text', '').lower():
                            found.append(fitz.Rect(span['bbox']) + fitz.Rect(-6, -6, 6, 6))
            for rect in found:
                page.add_redact_annot(rect, fill=(1, 1, 1))
            if found:
                page.apply_redactions(graphics=0)
                total += len(found)
    if total == 0:
        return jsonify({'ok': False, 'error': f'"{text}" metni sayfalarda bulunamadı'})
    return jsonify({'ok': True, 'pages': len(doc), 'count': total})


# Sıkıştırma seviyeleri: (hedef DPI, JPEG kalitesi). None = kayıpsız (resimlere dokunma)
COMPRESS_LEVELS = {
    'lossless': None,
    'high':     (200, 85),
    'medium':   (150, 72),
    'low':      (96, 55),
}


def _image_display_widths(doc):
    """xref -> sayfadaki en geniş gösterim genişliği (pt). Efektif DPI hesabı için.

    PyMuPDF aynı piksellere sahip resimleri birbirine karıştırabilir; en büyük değeri
    almak bu durumda resmi gereğinden fazla değil, en fazla daha az küçültür."""
    widths = {}
    for page in doc:
        for img in page.get_images(full=True):
            xref = img[0]
            for _rect, m in page.get_image_rects(xref, transform=True):
                w = (m.a ** 2 + m.b ** 2) ** 0.5  # resmin x ekseni boyunca genişlik (döndürmeye dayanıklı)
                widths[xref] = max(widths.get(xref, 0), w)
    return widths


def _recompress_images(doc, target_dpi, quality):
    """Resimleri hedef DPI'ya indirip JPEG olarak yeniden sıkıştırır. Değişen resim sayısını döndürür."""
    widths = _image_display_widths(doc)
    owner = {}  # xref -> resmi içeren bir sayfa (replace_image için)
    for page in doc:
        for img in page.get_images(full=True):
            owner.setdefault(img[0], page)

    changed = 0
    for xref, page in owner.items():
        try:
            if doc.xref_get_key(xref, 'Mask')[0] != 'null':
                continue  # renk anahtarlı maske — dokunma
            if doc.xref_get_key(xref, 'ImageMask')[1] == 'true':
                continue
            # extract_image() JPX'i PNG'ye çevirdiği için çok yavaş — sözlükten oku
            filt = doc.xref_get_key(xref, 'Filter')[1]
            bpc = doc.xref_get_key(xref, 'BitsPerComponent')[1]
            if (bpc.isdigit() and int(bpc) < 8) or 'JBIG2' in filt or 'CCITT' in filt:
                continue  # 1-bit taramalar zaten küçük, JPEG büyütür
            width = int(doc.xref_get_key(xref, 'Width')[1])
            old_len = len(doc.xref_stream_raw(xref) or b'')
            if old_len < 20 * 1024:
                continue

            disp_w = widths.get(xref, 0)
            needs_downscale = disp_w > 0 and width / (disp_w / 72) > target_dpi * 1.1
            if not needs_downscale and ('DCT' in filt or 'JPX' in filt) and quality > 60:
                continue  # zaten sıkıştırılmış; aynı çözünürlükte yeniden kodlamak kazandırmaz, sadece yavaşlatır

            pix = fitz.Pixmap(doc, xref)
            if pix.alpha:
                continue
            if pix.n not in (1, 3):
                pix = fitz.Pixmap(fitz.csRGB, pix)
            smask = doc.xref_get_key(xref, 'SMask')
            if smask[0] == 'xref':
                pix = fitz.Pixmap(pix, fitz.Pixmap(doc, int(smask[1].split()[0])))

            downscaled = False
            if needs_downscale:
                scale = target_dpi / (pix.width / (disp_w / 72))
                nw, nh = max(1, int(pix.width * scale)), max(1, int(pix.height * scale))
                pix = fitz.Pixmap(pix, nw, nh, None)
                downscaled = True

            if pix.alpha:
                # Şeffaf resim: JPEG şeffaflığı bozar — sadece küçült, kayıpsız sakla
                if downscaled:
                    page.replace_image(xref, pixmap=pix)
                    changed += 1
                continue

            data = pix.tobytes('jpeg', jpg_quality=quality)
            if len(data) < old_len * 0.9:
                page.replace_image(xref, stream=data)
                changed += 1
        except Exception:
            continue  # sorunlu tek bir resim tüm işlemi bozmasın
    return changed


@app.route('/api/compress', methods=['POST'])
def api_compress():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    data = request.json or {}
    path = (data.get('path') or '').strip().strip('"')
    level = data.get('quality', 'medium')
    if level not in COMPRESS_LEVELS:
        level = 'medium'
    if not path:
        path = _default_out('_sikistirildi')
    try:
        orig_kb = None
        if state.get('path') and os.path.exists(state['path']):
            orig_kb = os.path.getsize(state['path']) // 1024

        # Açık belgeye dokunmamak için kopya üzerinde çalış
        work = fitz.open('pdf', doc.tobytes())
        images = 0
        try:
            preset = COMPRESS_LEVELS[level]
            if preset:
                images = _recompress_images(work, *preset)
                try:
                    work.subset_fonts()
                except Exception:
                    pass
            if is_demo():
                _save_with_watermark(work, path)
            else:
                work.save(path, garbage=4, deflate=True, deflate_images=True,
                          deflate_fonts=True, clean=True)
        finally:
            work.close()
        size_kb = Path(path).stat().st_size // 1024
        return jsonify({'ok': True, 'path': path, 'size_kb': size_kb,
                        'orig_kb': orig_kb, 'images': images, 'quality': level})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


def _existing_file(path, exts=('.pdf',)):
    path = (path or '').strip().strip('"')
    if path and path.lower().endswith(exts) and os.path.isfile(path):
        return os.path.abspath(path)
    return None


def _existing_pdf(path):
    return _existing_file(path, ('.pdf', '.epub'))


def _reveal_in_explorer(path):
    import subprocess
    subprocess.Popen(['explorer', '/select,', path])


@app.route('/api/reveal', methods=['POST'])
def api_reveal():
    path = _existing_pdf((request.json or {}).get('path'))
    if not path:
        return jsonify({'ok': False, 'error': 'Dosya bulunamadı'})
    _reveal_in_explorer(path)
    return jsonify({'ok': True})


def _mapi_send_mail(path, subject, to=None):
    """Varsayılan e-posta programında (Outlook, Thunderbird…) eki hazır yeni bir posta açar.
    Pencere kapanana kadar bloklar. MAPI dönüş kodunu döndürür (0 = başarılı, 1 = kullanıcı iptal)."""
    import ctypes
    from ctypes import wintypes, POINTER, Structure, c_void_p, c_ulong

    class MapiRecipDescW(Structure):
        _fields_ = [('ulReserved', c_ulong), ('ulRecipClass', c_ulong),
                    ('lpszName', wintypes.LPWSTR), ('lpszAddress', wintypes.LPWSTR),
                    ('ulEIDSize', c_ulong), ('lpEntryID', c_void_p)]

    class MapiFileDescW(Structure):
        _fields_ = [('ulReserved', c_ulong), ('flFlags', c_ulong), ('nPosition', c_ulong),
                    ('lpszPathName', wintypes.LPWSTR), ('lpszFileName', wintypes.LPWSTR),
                    ('lpFileType', c_void_p)]

    class MapiMessageW(Structure):
        _fields_ = [('ulReserved', c_ulong), ('lpszSubject', wintypes.LPWSTR),
                    ('lpszNoteText', wintypes.LPWSTR), ('lpszMessageType', wintypes.LPWSTR),
                    ('lpszDateReceived', wintypes.LPWSTR), ('lpszConversationID', wintypes.LPWSTR),
                    ('flFlags', c_ulong), ('lpOriginator', POINTER(MapiRecipDescW)),
                    ('nRecipCount', c_ulong), ('lpRecips', POINTER(MapiRecipDescW)),
                    ('nFileCount', c_ulong), ('lpFiles', POINTER(MapiFileDescW))]

    MAPI_LOGON_UI, MAPI_DIALOG = 0x1, 0x8
    mapi = ctypes.WinDLL('mapi32.dll')
    send = mapi.MAPISendMailW
    send.argtypes = [ctypes.c_size_t, ctypes.c_size_t, POINTER(MapiMessageW), c_ulong, c_ulong]
    send.restype = c_ulong

    fd = MapiFileDescW(0, 0, 0xFFFFFFFF, path, os.path.basename(path), None)
    msg = MapiMessageW()
    msg.lpszSubject = subject
    msg.nFileCount = 1
    msg.lpFiles = ctypes.pointer(fd)
    if to:
        MAPI_TO = 1
        rcpt = MapiRecipDescW(0, MAPI_TO, to, 'SMTP:' + to, 0, None)
        msg.nRecipCount = 1
        msg.lpRecips = ctypes.pointer(rcpt)
    return send(0, 0, ctypes.byref(msg), MAPI_LOGON_UI | MAPI_DIALOG, 0)


@app.route('/api/send_mail', methods=['POST'])
def api_send_mail():
    data = request.json or {}
    path = _existing_file(data.get('path'), ('.pdf', '.epub'))
    to = (data.get('to') or '').strip()
    if to and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', to):
        return jsonify({'ok': False, 'error': 'Geçersiz e-posta adresi'})
    if not path:
        return jsonify({'ok': False, 'error': 'Dosya bulunamadı'})

    # MAPISendMail posta penceresi kapanana kadar döner; arka planda çalıştır.
    # E-posta programı yoksa hemen hata döner — kısa süre bekleyip bunu yakala.
    result = {}

    def worker():
        try:
            result['code'] = _mapi_send_mail(path, Path(path).stem, to)
        except Exception as e:
            result['code'] = -1
            result['error'] = str(e)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(4)
    code = result.get('code')
    if code is None or code in (0, 1):
        return jsonify({'ok': True, 'mode': 'mail'})
    # E-posta programı yok / desteklemiyor: dosyayı klasörde seçili göster
    _reveal_in_explorer(path)
    return jsonify({'ok': True, 'mode': 'folder'})


def _copy_file_to_clipboard(path):
    """Puts the file on the clipboard like Explorer's Ctrl+C (CF_HDROP), so it can be
    pasted with Ctrl+V into WhatsApp, Teams, Outlook, a browser tab, etc."""
    import ctypes
    from ctypes import wintypes
    k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
    k32.GlobalAlloc.restype = wintypes.HGLOBAL
    k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    u32.SetClipboardData.restype = wintypes.HANDLE
    u32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    GMEM_MOVEABLE, CF_HDROP = 0x0002, 15

    def global_bytes(data):
        h = k32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        ctypes.memmove(k32.GlobalLock(h), data, len(data))
        k32.GlobalUnlock(h)
        return h

    # DROPFILES header (20 bytes): pFiles offset, pt.x, pt.y, fNC, fWide=1; then a
    # double-NUL-terminated UTF-16 file list
    files = (os.path.abspath(path) + '\0\0').encode('utf-16-le')
    hdrop = global_bytes((20).to_bytes(4, 'little') + b'\0' * 12
                         + (1).to_bytes(4, 'little') + files)
    effect = global_bytes((1).to_bytes(4, 'little'))  # DROPEFFECT_COPY
    for _ in range(10):  # another app may hold the clipboard for a moment
        if u32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        raise RuntimeError('Pano kullanılamıyor')
    try:
        u32.EmptyClipboard()
        u32.SetClipboardData(CF_HDROP, hdrop)
        u32.SetClipboardData(u32.RegisterClipboardFormatW('Preferred DropEffect'), effect)
    finally:
        u32.CloseClipboard()


def _protocol_registered(scheme):
    import winreg
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, scheme))
        return True
    except OSError:
        return False


@app.route('/api/share', methods=['POST'])
def api_share():
    """Copies the file to the clipboard and opens the chosen app/site, where the user
    pastes it into a chat or email. Web services can't take a local file via a URL."""
    from urllib.parse import quote
    data = request.json or {}
    path = _existing_pdf(data.get('path'))
    if not path:
        return jsonify({'ok': False, 'error': 'Dosya bulunamadı'})
    subject = quote(Path(path).stem)
    target = data.get('target', 'copy')
    targets = {
        'whatsapp': ('whatsapp', 'whatsapp://', 'https://web.whatsapp.com/'),
        'telegram': ('tg', 'tg://', 'https://web.telegram.org/'),
        'teams':    ('msteams', 'msteams://', 'https://teams.microsoft.com/'),
        'gmail':    (None, None, f'https://mail.google.com/mail/?view=cm&fs=1&su={subject}'),
        'outlookweb': (None, None, f'https://outlook.live.com/mail/0/deeplink/compose?subject={subject}'),
        'linkedin': (None, None, 'https://www.linkedin.com/messaging/'),
        'copy':     (None, None, None),
    }
    if target == 'kindleweb':
        # The Send to Kindle page uploads a picked file; show the file so it can be dragged in
        webbrowser.open('https://www.amazon.com/sendtokindle')
        _reveal_in_explorer(path)
        return jsonify({'ok': True, 'opened': 'web'})
    if target not in targets:
        return jsonify({'ok': False, 'error': 'Geçersiz hedef'})
    try:
        _copy_file_to_clipboard(path)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})
    scheme, app_url, web_url = targets[target]
    opened = None
    if scheme and _protocol_registered(scheme):
        os.startfile(app_url)
        opened = 'app'
    elif web_url:
        webbrowser.open(web_url)
        opened = 'web'
    return jsonify({'ok': True, 'opened': opened})


@app.route('/api/encrypt', methods=['POST'])
def api_encrypt():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    if is_demo():
        return jsonify({'ok': False, 'error': DEMO_FEATURE_MSG})
    data = request.json or {}
    user_pw   = data.get('user_pw', '').strip()
    owner_pw  = data.get('owner_pw', '').strip()
    allow_print = data.get('allow_print', True)
    allow_copy  = data.get('allow_copy', False)
    if not user_pw and not owner_pw:
        return jsonify({'ok': False, 'error': 'En az bir şifre girilmeli'})
    out_path = _default_out('_sifrelendi')
    perms = fitz.PDF_PERM_ACCESSIBILITY
    if allow_print:
        perms |= fitz.PDF_PERM_PRINT | fitz.PDF_PERM_PRINT_HQ
    if allow_copy:
        perms |= fitz.PDF_PERM_COPY
    try:
        doc.save(out_path, encryption=fitz.PDF_ENCRYPT_AES_256,
                 user_pw=user_pw, owner_pw=owner_pw or user_pw,
                 permissions=perms, garbage=4, deflate=True)
        return jsonify({'ok': True, 'path': out_path})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/decrypt', methods=['POST'])
def api_decrypt():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    if is_demo():
        return jsonify({'ok': False, 'error': DEMO_FEATURE_MSG})
    data = request.json or {}
    password = data.get('password', '').strip()
    out_path = _default_out('_sifresiz')
    try:
        if doc.needs_pass:
            if not doc.authenticate(password):
                return jsonify({'ok': False, 'error': 'Yanlış şifre'})
        doc.save(out_path, encryption=fitz.PDF_ENCRYPT_NONE, garbage=4, deflate=True)
        return jsonify({'ok': True, 'path': out_path})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/export/excel')
def api_export_excel():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    if is_demo():
        return jsonify({'ok': False, 'error': DEMO_FEATURE_MSG})
    try:
        import openpyxl
    except ImportError:
        return jsonify({'ok': False, 'error': 'openpyxl yüklü değil: pip install openpyxl'})
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for i, page in enumerate(doc):
        ws = wb.create_sheet(f'Sayfa {i + 1}')
        for block in page.get_text('blocks'):
            if block[6] == 0:
                for line in block[4].strip().splitlines():
                    line = line.strip()
                    if line:
                        ws.append([line])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    stem = _doc_stem()
    return send_file(buf,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=f'{stem}.xlsx')


# ── PDF → PPT ────────────────────────────────────────────────────────────────
@app.route('/api/export/pptx')
def api_export_pptx():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    if is_demo():
        return jsonify({'ok': False, 'error': DEMO_FEATURE_MSG})
    try:
        from pptx import Presentation
        from pptx.util import Emu
    except ImportError:
        return jsonify({'ok': False, 'error': 'python-pptx yüklü değil'})
    try:
        prs = Presentation()
        blank = prs.slide_layouts[6]
        mat = fitz.Matrix(2.0, 2.0)
        for page in doc:
            r = page.rect
            # Slide boyutunu PDF sayfasıyla orantılı ayarla
            prs.slide_width  = Emu(int(r.width  * 914400 / 72))
            prs.slide_height = Emu(int(r.height * 914400 / 72))
            slide = prs.slides.add_slide(blank)
            pix = page.get_pixmap(matrix=mat)
            img_buf = io.BytesIO(pix.tobytes('png'))
            slide.shapes.add_picture(img_buf, 0, 0, prs.slide_width, prs.slide_height)
        buf = io.BytesIO()
        prs.save(buf)
        buf.seek(0)
        stem = _doc_stem()
        return send_file(buf,
                         mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
                         as_attachment=True,
                         download_name=f'{stem}.pptx')
    except Exception as e:
        return jsonify({'ok': False, 'error': f'PPT dönüştürme hatası: {e}'})


# ── PDF → JPG ─────────────────────────────────────────────────────────────────
@app.route('/api/export/jpg')
def api_export_jpg():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    if is_demo():
        return jsonify({'ok': False, 'error': DEMO_FEATURE_MSG})
    mat = fitz.Matrix(2.0, 2.0)
    stem = _doc_stem()
    if len(doc) == 1:
        pix = doc[0].get_pixmap(matrix=mat)
        if pix.alpha:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        buf = io.BytesIO(pix.tobytes('jpeg'))
        return send_file(buf, mimetype='image/jpeg',
                         as_attachment=True,
                         download_name=f'{stem}.jpg')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=mat)
            if pix.alpha:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            zf.writestr(f'sayfa_{i + 1:03d}.jpg', pix.tobytes('jpeg'))
    buf.seek(0)
    return send_file(buf, mimetype='application/zip',
                     as_attachment=True,
                     download_name=f'{stem}_jpg.zip')


# ── Dosya → PDF (dönüştür) ────────────────────────────────────────────────────
@app.route('/api/browse_convert')
def api_browse_convert():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
    path = filedialog.askopenfilename(
        title="PDF'e dönüştürülecek dosyayı seçin",
        filetypes=[
            ('Desteklenen Dosyalar', '*.docx *.doc *.xlsx *.xls *.pptx *.ppt *.jpg *.jpeg *.png *.bmp *.tiff *.gif *.webp'),
            ('Word Dosyaları',  '*.docx *.doc'),
            ('Excel Dosyaları', '*.xlsx *.xls'),
            ('PowerPoint',      '*.pptx *.ppt'),
            ('Görseller',       '*.jpg *.jpeg *.png *.bmp *.tiff *.gif *.webp'),
            ('Tüm Dosyalar',    '*.*'),
        ]
    )
    root.destroy()
    return jsonify({'path': path or ''})


@app.route('/api/convert_to_pdf', methods=['POST'])
def api_convert_to_pdf():
    data    = request.json or {}
    src     = (data.get('path') or '').strip().strip('"')
    if not src or not os.path.exists(src):
        return jsonify({'ok': False, 'error': 'Dosya bulunamadı'})

    ext = os.path.splitext(src)[1].lower()
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp'}
    OFFICE_EXTS = {'.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt'}

    try:
        if ext in IMAGE_EXTS:
            # Görsel → PDF (PyMuPDF)
            img_doc = fitz.open(src)
            pdf_bytes = img_doc.convert_to_pdf()
            img_doc.close()
            new_doc = fitz.open('pdf', pdf_bytes)

        elif ext in OFFICE_EXTS:
            from docx2pdf import convert as d2p
            tmp_pdf = tempfile.mktemp(suffix='.pdf')
            d2p(src, tmp_pdf)
            new_doc = fitz.open(tmp_pdf)
            pdf_bytes = new_doc.tobytes()
            new_doc.close()
            try: os.unlink(tmp_pdf)
            except Exception: pass
            new_doc = fitz.open('pdf', pdf_bytes)

        else:
            return jsonify({'ok': False, 'error': f'Desteklenmeyen format: {ext}'})

        truncated = _demo_truncate(new_doc)
        push_history()
        _swap_doc(new_doc, os.path.splitext(src)[0] + '_converted.pdf', reset_history=False)
        sigs = detect_signatures(new_doc)
        fields = detect_form_fields(new_doc)
        return jsonify({'ok': True, 'pages': len(new_doc),
                        'name': _doc_name(),
                        'signatures': sigs, 'form_fields': fields,
                        'demo_truncated': truncated})

    except Exception as e:
        return jsonify({'ok': False, 'error': f'Dönüştürme hatası: {e}'})


if __name__ == '__main__':
    import socket
    import urllib.request
    import json as _json
    import webview

    filepath = sys.argv[1].strip().strip('"') if len(sys.argv) > 1 else ''

    PORT = 5150

    def port_in_use():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', PORT)) == 0

    if port_in_use():
        # Uygulama zaten açık — dosyayı çalışan örneğe gönder, yeni pencere aç
        if filepath:
            try:
                data = _json.dumps({'path': filepath}).encode()
                req = urllib.request.Request(
                    f'http://localhost:{PORT}/api/open', data=data,
                    headers={'Content-Type': 'application/json'}, method='POST')
                urllib.request.urlopen(req, timeout=3)
            except Exception as e:
                print(f'Dosya gonderilemedi: {e}')
        window = webview.create_window(
            'PDF Editor Pro',
            f'http://localhost:{PORT}',
            width=1280, height=800,
            min_size=(900, 600),
        )
        webview.start(icon=os.path.join(_BASE_DIR, 'static', 'app-icon.ico'))
    else:
        if filepath:
            try:
                doc = fitz.open(filepath)
                _demo_truncate(doc)
                state['doc'] = doc
                state['path'] = filepath
            except Exception as e:
                print(f'Dosya acilamadi: {e}')

        def start_flask():
            app.run(port=PORT, debug=False, use_reloader=False, threaded=True)

        threading.Thread(target=start_flask, daemon=True).start()
        time.sleep(1.0)

        window = webview.create_window(
            'PDF Editor Pro',
            f'http://localhost:{PORT}',
            width=1280, height=800,
            min_size=(900, 600),
        )
        webview.start(icon=os.path.join(_BASE_DIR, 'static', 'app-icon.ico'))
