from flask import Flask, render_template, request, jsonify, send_file, make_response
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
import time

# PyInstaller frozen bundle support
if getattr(sys, 'frozen', False):
    _BASE_DIR = sys._MEIPASS
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__,
            template_folder=os.path.join(_BASE_DIR, 'templates'),
            static_folder=os.path.join(_BASE_DIR, 'static'))
state = {'doc': None, 'path': None, 'history': []}


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
        else:
            msg = f'İşlem tamamlanamadı: {e}'
        app.logger.exception('API hatası')
    return jsonify({'ok': False, 'error': msg}), code

DEMO_MAX_PAGES = 3
MAX_HISTORY = 15


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

_FONT_RATIO_CACHE = {}


def _sys_font_ratio(fontfile):
    if fontfile not in _FONT_RATIO_CACHE:
        try:
            f = fitz.Font(fontfile=fontfile)
            ratio = f.ascender - f.descender
            _FONT_RATIO_CACHE[fontfile] = ratio if ratio > 0.1 else 1.2
        except Exception:
            _FONT_RATIO_CACHE[fontfile] = 1.2
    return _FONT_RATIO_CACHE[fontfile]


def resolve_font(pdf_fontname, flags=0):
    name = pdf_fontname or ''
    is_bold   = bool(flags & 16) or any(k in name.lower() for k in ['bold','heavy','black','demi'])
    is_italic = bool(flags & 2)  or any(k in name.lower() for k in ['italic','oblique','slant'])

    base = name.lower()
    for tok in ['bolditalic','bold','italic','oblique','regular','medium',
                '-mt','mt','-ps','ps','narrow','condensed','+']:
        base = base.replace(tok, '')
    base = base.strip(' -_').replace(' ', '')

    FONTS = 'C:/Windows/Fonts/'
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
    return round(rect.height * 0.82, 1)


def _get_baseline_y(page, rect, page_dict=None):
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
    return rect.y1


def _has_underline(bbox, drawings):
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


def _apply_demo_watermark(doc):
    """Tüm sayfalara çapraz DEMO filigranı ekle (kayıt öncesi kopya üzerinde çalışır)."""
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
    """Dokümanın bir kopyasını al, filigran ekle, kaydet. Orijinal değişmez."""
    buf = doc.tobytes(garbage=1)
    wm_doc = fitz.open(stream=buf, filetype='pdf')
    _apply_demo_watermark(wm_doc)
    strip_signatures(wm_doc)
    clean_metadata(wm_doc)
    wm_doc.save(path, garbage=4, deflate=True)
    wm_doc.close()


@app.route('/')
def index():
    resp = make_response(render_template('index.html', demo_mode=True))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route('/api/open', methods=['POST'])
def api_open():
    path = request.json.get('path', '').strip().strip('"')
    try:
        if state['doc']:
            state['doc'].close()
        doc = fitz.open(path)
        truncated = False
        if len(doc) > DEMO_MAX_PAGES:
            doc.select(list(range(DEMO_MAX_PAGES)))
            truncated = True
        state['doc'] = doc
        state['path'] = path
        state['history'] = []
        sigs   = detect_signatures(doc)
        fields = detect_form_fields(doc)
        return jsonify({'ok': True, 'pages': len(doc), 'name': Path(path).name,
                        'signatures': sigs, 'form_fields': fields,
                        'demo_truncated': truncated})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


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
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    i = request.json.get('i', -1)
    if i < 0 or i >= len(doc):
        return jsonify({'ok': False, 'error': 'Geçersiz sayfa'})
    push_history()
    doc.delete_page(i)
    return jsonify({'ok': True, 'pages': len(doc)})


@app.route('/api/rotate', methods=['POST'])
def api_rotate():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    i = request.json.get('i', 0)
    deg = request.json.get('deg', 90)
    page = doc[i]
    push_history()
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
    # PyMuPDF move_page(pno, to) sayfayı 'to' numaralı sayfanın ÖNÜNE koyar;
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

    page_idx       = request.json.get('page_idx', None)
    bx0            = request.json.get('bx0', None)
    by0            = request.json.get('by0', None)
    bx1            = request.json.get('bx1', None)
    by1            = request.json.get('by1', None)
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
    force_bold   = data.get('force_bold', None)
    force_italic = data.get('force_italic', None)
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
    # GERÇEK silme: alttaki metin/görsel PDF'ten kaldırılır (beyaz kutu metni silmezdi)
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
        combined = len(doc) + len(src)
        src.close()
        if combined > DEMO_MAX_PAGES:
            return jsonify({
                'ok': False,
                'error': f'Demo sürümünde en fazla {DEMO_MAX_PAGES} sayfa açılabilir. '
                         f'Tam sürümü satın almak için mkbsoft.net adresini ziyaret edin.'
            })
        src = fitz.open(path)
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
        orig = Path(state['path'])
        path = str(orig.parent / f"{orig.stem}_sayfa{start + 1}-{end + 1}_demo.pdf")
    try:
        new_doc = fitz.open()
        new_doc.insert_pdf(doc, from_page=start, to_page=end)
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
        orig = Path(state['path'])
        path = str(orig.parent / (orig.stem + '_demo.pdf'))
    try:
        _save_with_watermark(doc, path)
        return jsonify({'ok': True, 'path': path, 'stripped_signatures': 0})
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
            initialfile=orig.stem + '_demo.pdf',
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
    if ext not in ('.docx', '.xlsx', '.pptx', '.png', '.jpg', '.zip', '.txt'):
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
            initialdir=str((Path(state['path']).parent if state.get('path') and Path(state['path']).parent.exists() else Path.home() / 'Downloads')),
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
    tmp = tempfile.mktemp(suffix='.pdf')
    f.save(tmp)
    try:
        if state['doc']:
            state['doc'].close()
        doc = fitz.open(tmp)
        truncated = False
        if len(doc) > DEMO_MAX_PAGES:
            doc.select(list(range(DEMO_MAX_PAGES)))
            truncated = True
        state['doc'] = doc
        state['path'] = tmp
        state['history'] = []
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
        return jsonify({'ok': True, 'pages': len(state['doc']), 'name': Path(state['path']).name})
    return jsonify({'ok': False})


@app.route('/api/export/images')
def api_export_images():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    mat = fitz.Matrix(2.0, 2.0)
    stem = Path(state['path']).stem if state['path'] else 'belge'
    if len(doc) == 1:
        pix = doc[0].get_pixmap(matrix=mat)
        buf = io.BytesIO(pix.tobytes('png'))
        return send_file(buf, mimetype='image/png',
                         as_attachment=True,
                         download_name=f'{stem}_demo.png')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=mat)
            zf.writestr(f'sayfa_{i + 1:03d}.png', pix.tobytes('png'))
    buf.seek(0)
    return send_file(buf, mimetype='application/zip',
                     as_attachment=True,
                     download_name=f'{stem}_demo_sayfalar.zip')


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
    stem = Path(state['path']).stem if state['path'] else 'belge'
    return send_file(buf, mimetype='text/plain; charset=utf-8',
                     as_attachment=True,
                     download_name=f'{stem}_demo.txt')


@app.route('/api/compress', methods=['POST'])
def api_compress():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    path = request.json.get('path', '').strip().strip('"')
    if not path:
        orig = Path(state['path'])
        path = str(orig.parent / (orig.stem + '_demo_sikistirildi.pdf'))
    try:
        _save_with_watermark(doc, path)
        size_kb = Path(path).stat().st_size // 1024
        return jsonify({'ok': True, 'path': path, 'size_kb': size_kb})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


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
    if len(doc) >= DEMO_MAX_PAGES:
        return jsonify({
            'ok': False,
            'error': f'Demo sürümünde en fazla {DEMO_MAX_PAGES} sayfa desteklenir. '
                     'Tam sürümü satın almak için mkbsoft.net adresini ziyaret edin.'
        })
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

        truncated = False
        if len(new_doc) > DEMO_MAX_PAGES:
            new_doc.select(list(range(DEMO_MAX_PAGES)))
            truncated = True

        push_history()
        state['doc']  = new_doc
        state['path'] = os.path.splitext(src)[0] + '_converted.pdf'
        sigs = detect_signatures(new_doc)
        fields = detect_form_fields(new_doc)
        return jsonify({'ok': True, 'pages': len(new_doc),
                        'name': os.path.basename(state['path']),
                        'signatures': sigs, 'form_fields': fields,
                        'demo_truncated': truncated})

    except Exception as e:
        return jsonify({'ok': False, 'error': f'Dönüştürme hatası: {e}'})


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


if __name__ == '__main__':
    import socket
    import urllib.request
    import json as _json
    import webview

    filepath = sys.argv[1].strip().strip('"') if len(sys.argv) > 1 else ''

    PORT = 5151

    def port_in_use():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', PORT)) == 0

    if port_in_use():
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
            'PDF Editör Pro — Demo',
            f'http://localhost:{PORT}',
            width=1280, height=800,
            min_size=(900, 600),
        )
        webview.start()
    else:
        if filepath:
            try:
                doc = fitz.open(filepath)
                if len(doc) > DEMO_MAX_PAGES:
                    doc.select(list(range(DEMO_MAX_PAGES)))
                state['doc'] = doc
                state['path'] = filepath
            except Exception as e:
                print(f'Dosya acilamadi: {e}')

        def start_flask():
            app.run(port=PORT, debug=False, use_reloader=False, threaded=True)

        threading.Thread(target=start_flask, daemon=True).start()
        time.sleep(1.0)

        window = webview.create_window(
            'PDF Editör Pro — Demo',
            f'http://localhost:{PORT}',
            width=1280, height=800,
            min_size=(900, 600),
        )
        webview.start()
