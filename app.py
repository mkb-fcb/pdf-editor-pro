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
import store_iap as _iap
import scan_ocr

MAX_HISTORY = 15

# Keep in sync with installer.iss / installer_demo.iss (MyAppVersion) and build_msix.py's argument
APP_VERSION = '1.2.2'
SOURCE_URL = 'https://github.com/mkb-fcb/pdf-editor-pro'

# Lisans girilmemişse uygulama demo modunda çalışır (3 sayfa, filigranlı kayıt)
DEMO_MAX_PAGES = 3
DEMO_LIMIT_MSG = (f'Demo sürümünde en fazla {DEMO_MAX_PAGES} sayfa desteklenir. '
                  'Tam sürüm için lisans anahtarı girin veya mkbsoft.net adresinden satın alın.')
DEMO_WATERMARK_MSG = 'Demo sürümünde kaydedilen dosyalara filigran eklenir.'
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


# Output file name suffixes in the UI language (set by the page via /api/ui_lang)
FILE_SUFFIXES = {
    'en': dict(edited='_edited', compressed='_compressed', encrypted='_encrypted', unlocked='_unlocked',
               range='_pages{a}-{b}', page='page', pages='_pages', converted='_converted'),
    'tr': dict(edited='_duzenlendi', compressed='_sikistirildi', encrypted='_sifrelendi', unlocked='_sifresiz',
               range='_sayfa{a}-{b}', page='sayfa', pages='_sayfalar', converted='_donusturuldu'),
    'de': dict(edited='_bearbeitet', compressed='_komprimiert', encrypted='_verschlüsselt', unlocked='_entsperrt',
               range='_seiten{a}-{b}', page='seite', pages='_seiten', converted='_konvertiert'),
    'es': dict(edited='_editado', compressed='_comprimido', encrypted='_cifrado', unlocked='_desbloqueado',
               range='_páginas{a}-{b}', page='página', pages='_páginas', converted='_convertido'),
    'fr': dict(edited='_modifié', compressed='_compressé', encrypted='_chiffré', unlocked='_déverrouillé',
               range='_pages{a}-{b}', page='page', pages='_pages', converted='_converti'),
    'it': dict(edited='_modificato', compressed='_compresso', encrypted='_crittografato', unlocked='_sbloccato',
               range='_pagine{a}-{b}', page='pagina', pages='_pagine', converted='_convertito'),
    'pt': dict(edited='_editado', compressed='_comprimido', encrypted='_criptografado', unlocked='_desbloqueado',
               range='_páginas{a}-{b}', page='página', pages='_páginas', converted='_convertido'),
    'ru': dict(edited='_изменён', compressed='_сжатый', encrypted='_зашифрован', unlocked='_без_пароля',
               range='_стр{a}-{b}', page='стр', pages='_страницы', converted='_конвертирован'),
}


def _sfx(key, **kw):
    table = FILE_SUFFIXES.get(state.get('ui_lang') or 'tr', FILE_SUFFIXES['tr'])
    return table[key].format(**kw)


# ── Store rating prompt + buy link ──────────────────────
BUY_URL = 'https://kamilicious12.gumroad.com/l/qxshwx'
STORE_REVIEW_URL = 'ms-windows-store://review/?ProductId=9PJJ019JKTP9'
# MSIX installs live under ...\WindowsApps\; PDFEDITOR_FORCE_RATE=1 shows the prompt in dev/EXE builds
IS_STORE = 'windowsapps' in sys.executable.lower() or os.environ.get('PDFEDITOR_FORCE_RATE') == '1'
PROMPTS_FILE = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'PDFEditorPro', 'prompts.json')
_launch_counted = False


def _prompts_load() -> dict:
    try:
        import json
        with open(PROMPTS_FILE, encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    return {}


def _prompts_save(d: dict):
    try:
        import json
        os.makedirs(os.path.dirname(PROMPTS_FILE), exist_ok=True)
        with open(PROMPTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(d, f)
    except Exception:
        pass


def _count_launch():
    global _launch_counted
    if _launch_counted:
        return
    _launch_counted = True
    d = _prompts_load()
    d.setdefault('first', time.time())
    d['launches'] = d.get('launches', 0) + 1
    _prompts_save(d)


@app.route('/api/rate_prompt', methods=['POST'])
def api_rate_prompt():
    """event='saved' after a successful save → {show}; action='rate'|'later'|'never' from the dialog."""
    data = request.json or {}
    d = _prompts_load()
    action = data.get('action')
    if action == 'rate':
        d['rate'] = 'done'
        _prompts_save(d)
        try:
            os.startfile(STORE_REVIEW_URL)
        except Exception:
            webbrowser.open('https://apps.microsoft.com/detail/9PJJ019JKTP9')
        return jsonify({'ok': True})
    if action in ('later', 'never'):
        d['rate'] = 'never' if action == 'never' else 'pending'
        d['next_at'] = d.get('saves', 0) + 6
        _prompts_save(d)
        return jsonify({'ok': True})
    d['saves'] = d.get('saves', 0) + 1
    _prompts_save(d)
    # Ask only engaged users at a good moment: licensed after 3 saves, demo users after 5 saves and 3 launches
    need = d.get('next_at') or (5 if is_demo() else 3)
    show = (IS_STORE and d.get('rate', 'pending') == 'pending' and d['saves'] >= need
            and d.get('launches', 0) >= (3 if is_demo() else 2))
    return jsonify({'ok': True, 'show': show})


@app.route('/api/ui_lang', methods=['POST'])
def api_ui_lang():
    lang = (request.json or {}).get('lang')
    if lang in FILE_SUFFIXES:
        state['ui_lang'] = lang
        pref = _ocr_pref()     # the page sends this on start: the saved choice applies from then on
        scan_ocr.set_language(lang if pref == 'auto' else pref)
    return jsonify({'ok': True})


def _ocr_pref() -> str:
    """The language scans are read in: 'auto' (the UI language) or one the user picked."""
    pref = _prompts_load().get('ocr_lang', 'auto')
    return pref if pref == 'auto' or pref in scan_ocr.TESS_MODELS else 'auto'


@app.route('/api/ocr_lang', methods=['GET', 'POST'])
def api_ocr_lang():
    if request.method == 'POST':
        pref = (request.json or {}).get('lang')
        if pref != 'auto' and pref not in scan_ocr.TESS_MODELS:
            return jsonify({'ok': False}), 400
        d = _prompts_load()
        d['ocr_lang'] = pref
        _prompts_save(d)
        scan_ocr.set_language((state.get('ui_lang') or 'tr') if pref == 'auto' else pref)
    return jsonify({'ok': True, 'pref': _ocr_pref(), 'lang': scan_ocr.OCR_LANG})


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


def _make_writable(doc):
    """Some PDFs (seen from Word 2016) list objects in the xref that do not exist. They display fine,
    but MuPDF refuses to save them, so undo snapshots, edits and saving all failed. Such a document
    is copied page by page into a fresh PDF (the broken accessibility structure tree is dropped)."""
    if not doc.is_pdf or doc.needs_pass:
        return doc
    for x in range(1, doc.xref_length()):
        try:
            doc.xref_object(x, compressed=True)
        except Exception:
            break
    else:
        return doc
    try:
        doc.tobytes(garbage=1)
        return doc
    except Exception:
        pass
    try:
        fresh = fitz.open()
        fresh.insert_pdf(doc)
        toc = doc.get_toc(False)
        if toc:
            fresh.set_toc(toc)
        fresh.set_metadata({k: v for k, v in (doc.metadata or {}).items() if v and k != 'format' and k != 'encryption'})
        fresh.tobytes(garbage=1)
        app.logger.warning('Repaired a PDF with missing xref objects by copying its pages')
        doc.close()
        return fresh
    except Exception:
        return doc


def _swap_doc(new_doc, path, name=None, reset_history=True):
    """Yeni belgeyi etkinleştir; eskisini ancak yenisi başarıyla açıldıktan sonra kapat."""
    new_doc = _make_writable(new_doc)
    old = state['doc']
    state['doc'] = new_doc
    state['path'] = path
    state['name'] = name or Path(path).name
    if reset_history:
        clear_history()
        _trial_new_doc()
    if old is not None:
        try:
            old.close()
        except Exception:
            pass
    return new_doc



def is_demo() -> bool:
    # is_licensed() may hit the license server, so check once per run
    global _licensed_cache
    if _licensed_cache is None:
        # Gumroad license key, or the full-version add-on bought in the Microsoft Store
        _licensed_cache = _lic.is_licensed() or _iap.owns_full()
    return not _licensed_cache


# ── Full-version trial ───────────────────────────────────────────────────────
# A demo user may use the full version on TRIAL_DOCS documents within TRIAL_DAYS days, counted
# from the first one. Viewing, printing and what the demo already allows cost nothing; a document
# is spent when the user chooses the full version for it (longer than the demo limit, a save
# without the watermark, a full-version feature). The record is kept in three places so that
# reinstalling does not start over: the settings file and the registry (both removed with an
# MSIX uninstall) and a hidden file in the user profile.
TRIAL_DOCS = 3
TRIAL_DAYS = 7
_TRIAL_FILE = os.path.join(os.path.expanduser('~'), '.pdfeditorpro')
_TRIAL_REG = r'Software\MKBSoft\PDFEditorPro'


def _trial_read_all() -> list:
    import json
    found = [_prompts_load().get('trial')]
    try:
        with open(_TRIAL_FILE, encoding='utf-8') as f:
            found.append(json.load(f))
    except Exception:
        pass
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _TRIAL_REG) as k:
            found.append(json.loads(winreg.QueryValueEx(k, 'Trial')[0]))
    except Exception:
        pass
    return [t for t in found if isinstance(t, dict)]


def _trial_load() -> dict:
    """{'start': first use (epoch s) or None, 'docs': documents spent} merged from all copies:
    the earliest start and every document any copy knows."""
    start, docs = None, []
    for t in _trial_read_all():
        if isinstance(t.get('start'), (int, float)):
            start = t['start'] if start is None else min(start, t['start'])
        for d in t.get('docs') or []:
            if isinstance(d, str) and d not in docs:
                docs.append(d)
    return {'start': start, 'docs': docs}


def _trial_save(t: dict):
    import json
    d = _prompts_load()
    d['trial'] = t
    _prompts_save(d)
    data = json.dumps(t)
    try:
        if os.path.exists(_TRIAL_FILE):
            os.chmod(_TRIAL_FILE, 0o666)
        with open(_TRIAL_FILE, 'w', encoding='utf-8') as f:
            f.write(data)
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(_TRIAL_FILE, 0x2)     # hidden
    except Exception:
        pass
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _TRIAL_REG) as k:
            winreg.SetValueEx(k, 'Trial', 0, winreg.REG_SZ, data)
    except Exception:
        pass


def _trial_doc_key() -> str:
    """Identifies the open document: its file, or its name and size when it has none of its own."""
    doc, path = state.get('doc'), state.get('path') or ''
    if path and not os.path.basename(path).startswith(('demo_', 'tmp')):
        return os.path.normcase(os.path.abspath(path))
    return f"{state.get('name') or ''}:{len(doc) if doc else 0}"


def _trial_status() -> dict:
    t = _trial_load()
    left_days = TRIAL_DAYS
    if t['start'] is not None:
        left_days = max(0.0, TRIAL_DAYS - (time.time() - t['start']) / 86400)
    expired = t['start'] is not None and left_days <= 0
    left_docs = max(0, TRIAL_DOCS - len(t['docs']))
    return {'demo': is_demo(), 'unlocked': bool(state.get('trial_doc')),
            'available': is_demo() and not expired and left_docs > 0,
            'started': t['start'] is not None, 'expired': expired,
            'docs_left': left_docs, 'days_left': int(-(-left_days // 1)),     # whole days, rounded up
            'docs_total': TRIAL_DOCS, 'days_total': TRIAL_DAYS}


def _trial_new_doc():
    """A document was opened: it runs in the demo unless the trial already covers it (reopening a
    spent document within the period is free)."""
    state['trial_doc'] = False
    if not is_demo() or not state.get('doc'):
        return
    t = _trial_load()
    if t['start'] is not None and time.time() - t['start'] < TRIAL_DAYS * 86400 \
            and _trial_doc_key() in t['docs']:
        state['trial_doc'] = True


def _limited() -> bool:
    """Demo limits apply to the open document: demo version and the trial not used on it."""
    return is_demo() and not state.get('trial_doc')


def _demo_block(msg, **extra):
    """A demo limit was hit. While the trial is available the page offers it first
    ('demo_limit'); otherwise it shows msg."""
    return jsonify({'ok': False, 'error': msg, 'demo_limit': _trial_status()['available'], **extra})


def _trial_offer() -> bool:
    """For actions that work in the demo but with less (watermark, first pages): ask first while
    the trial is available, unless the page already answered 'demo'."""
    answered = (request.get_json(silent=True) or {}).get('demo_ok') or request.args.get('demo_ok')
    return _limited() and not answered and _trial_status()['available']


@app.route('/api/trial', methods=['GET'])
def api_trial():
    return jsonify({'ok': True, **_trial_status()})


@app.route('/api/trial/use', methods=['POST'])
def api_trial_use():
    if not state.get('doc'):
        return jsonify({'ok': False, 'error': 'Açık dosya yok'})
    st = _trial_status()
    if not st['demo'] or st['unlocked']:
        return jsonify({'ok': True, **st})
    if not st['available']:
        return jsonify({'ok': False, **st})
    t = _trial_load()
    if t['start'] is None:
        t['start'] = time.time()
    key = _trial_doc_key()
    if key not in t['docs']:
        t['docs'].append(key)
    _trial_save(t)
    state['trial_doc'] = True
    return jsonify({'ok': True, **_trial_status()})


def _demo_truncate(doc) -> bool:
    """Demo modunda belgeyi ilk DEMO_MAX_PAGES sayfaya indir. Kırpıldıysa True."""
    if _limited() and len(doc) > DEMO_MAX_PAGES:
        doc.select(list(range(DEMO_MAX_PAGES)))
        return True
    return False


def _demo_over_limit() -> bool:
    """Demo modunda açık belge sayfa sınırını aşıyor mu (yalnızca okunabilir/yazdırılabilir)."""
    doc = state['doc']
    return bool(doc) and _limited() and len(doc) > DEMO_MAX_PAGES


# Demo modunda belgenin tamamı okunur ve yazdırılır; bunların dışındaki her API çağrısı
# (düzenleme, kaydetme, dışa aktarma...) belgeyi önce ilk DEMO_MAX_PAGES sayfaya indirir.
_DEMO_FULL_DOC_ENDPOINTS = {
    'api_status', 'api_page_sizes', 'api_view', 'api_print_page', 'api_thumb',
    'api_open', 'api_upload', 'api_browse', 'api_ui_lang', 'api_ocr_lang', 'api_rate_prompt',
    'api_activate', 'api_open_link', 'api_demo_edit', 'api_trial', 'api_trial_use',
    'api_store_price', 'api_scan_info',     # read-only; the price is fetched while a document opens
}


@app.before_request
def _demo_page_limit_guard():
    if (request.path.startswith('/api/') and request.endpoint not in _DEMO_FULL_DOC_ENDPOINTS
            and _demo_over_limit()):
        _demo_truncate(state['doc'])


@app.route('/api/demo_edit', methods=['POST'])
def api_demo_edit():
    """Okuma modundan düzenlemeye geçerken demo sayfa sınırını uygular."""
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Açık dosya yok'})
    if len(doc) > DEMO_MAX_PAGES and _trial_offer():
        return _demo_block(DEMO_LIMIT_MSG, pages=len(doc))
    truncated = _demo_truncate(doc)
    return jsonify({'ok': True, 'pages': len(doc), 'truncated': truncated})


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

# Undo snapshots are kept on disk, not in memory: a scanned document is tens of MB and 15 of
# them would hold hundreds of MB for nothing
_HISTORY_DIR = None


def _history_dir():
    global _HISTORY_DIR
    if _HISTORY_DIR is None or not os.path.isdir(_HISTORY_DIR):
        import shutil
        _HISTORY_DIR = tempfile.mkdtemp(prefix='pdfeditor_undo_')
        atexit.register(shutil.rmtree, _HISTORY_DIR, True)
    return _HISTORY_DIR


def _forget(snapshot):
    try:
        os.remove(snapshot)
    except Exception:
        pass


def clear_history():
    for snap in state['history']:
        _forget(snap)
    state['history'] = []


def push_history():
    doc = state['doc']
    if not doc:
        return
    import uuid
    snap = os.path.join(_history_dir(), uuid.uuid4().hex + '.pdf')
    doc.save(snap, garbage=1)
    state['history'].append(snap)
    if len(state['history']) > MAX_HISTORY:
        _forget(state['history'].pop(0))


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


def _span_at(page_dict, rect):
    """The text span that overlaps rect the most (font, flags, color, size), or None."""
    best, best_area = None, 0
    for b in page_dict.get('blocks', []):
        for l in b.get('lines', []):
            for s in l.get('spans', []):
                if not s.get('text', '').strip():
                    continue
                inter = fitz.Rect(s['bbox']) & rect
                area = inter.width * inter.height if not inter.is_empty else 0
                if area > best_area:
                    best, best_area = s, area
    return best


def _embedded_font(page, span_font):
    """Buffer of the page's embedded font that the span uses, or None."""
    if not span_font:
        return None
    for f in page.get_fonts(full=True):
        xref, ext, basefont = f[0], f[1], f[3]
        if span_font not in (basefont, basefont.split('+', 1)[-1]) or ext in ('', 'n/a'):
            continue
        try:
            buf = page.parent.extract_font(xref)[3]
        except Exception:
            continue
        if buf:
            return buf
    return None


# Look-alike families tried when a PDF font has no usable name (Chromium "Save as PDF" writes
# every font as a Type3 "Unnamed-T3" with no bold/italic flags). Keys are resolve_font() MAP keys;
# files are (regular, bold, italic, bold italic).
_LOOKALIKES = {
    'arial':   ('arial.ttf', 'arialbd.ttf', 'ariali.ttf', 'arialbi.ttf'),
    'calibri': ('calibri.ttf', 'calibrib.ttf', 'calibrii.ttf', 'calibriz.ttf'),
    'segoeui': ('segoeui.ttf', 'segoeuib.ttf', 'segoeuii.ttf', 'segoeuiz.ttf'),
    'times':   ('times.ttf', 'timesbd.ttf', 'timesi.ttf', 'timesbi.ttf'),
    'verdana': ('verdana.ttf', 'verdanab.ttf', 'verdanai.ttf', 'verdanaz.ttf'),
    'georgia': ('georgia.ttf', 'georgiab.ttf', 'georgiai.ttf', 'georgiaz.ttf'),
}


def _unknown_font(span_font):
    """True when resolve_font() cannot map the name to a real typeface."""
    name = (span_font or '').lower()
    if not name or 'unnamed' in name:
        return True
    return resolve_font(span_font)[0] == UNICODE_FONT and 'calibri' not in name


def _closest_lookalike(page, rect, text, size, baseline):
    """(score, family, bold, italic, size factor) of the look-alike whose rendering is closest to the original
    pixels in rect (each candidate fitted to the same width), plus the Arial regular/bold ink ratios."""
    clip = fitz.Rect(rect.x0 - 1, rect.y0 - 1, rect.x1 + 1, rect.y1 + 1)
    mat = fitz.Matrix(3, 3)
    try:
        ref = page.get_pixmap(matrix=mat, clip=clip, colorspace=fitz.csGRAY, alpha=False).samples
    except Exception:
        return None, {}
    ref_ink = sum(255 - b for b in ref) or 1

    def render(ff, sz):
        scratch = fitz.open()
        sp = scratch.new_page(width=page.rect.width, height=page.rect.height)
        sp.insert_text(fitz.Point(rect.x0, baseline), text, fontsize=sz, fontfile=ff, fontname='G', color=(0, 0, 0))
        img = sp.get_pixmap(matrix=mat, clip=clip, colorspace=fitz.csGRAY, alpha=False).samples
        scratch.close()
        return img

    best, ink = None, {}
    for fam, files in _LOOKALIKES.items():
        for style, fn in enumerate(files):
            ff = 'C:/Windows/Fonts/' + fn
            if not os.path.exists(ff):
                continue
            try:
                w = fitz.Font(fontfile=ff).text_length(text, fontsize=size)
                fit = min(1.3, max(0.77, rect.width / w)) if w else 1.0
                img = render(ff, size * fit)
            except Exception:
                continue
            if len(img) != len(ref):
                continue
            score = sum(abs(a - b) for a, b in zip(ref, img)) / ref_ink
            if best is None or score < best[0]:
                best = (score, fam, bool(style & 1), bool(style & 2), fit)
            if fam == 'arial' and style < 2:
                ink[style] = sum(255 - b for b in render(ff, size)) / ref_ink
    return best, ink


def _guess_font_visually(page, rect, text, size, baseline):
    """Look-alike Windows font for text whose PDF font has no usable name. Call BEFORE redaction.
    Returns (family, bold, italic, size factor at which it matched) or None."""
    text = (text or '').rstrip()
    if len(text.strip()) < 3 or rect.width < 5 or not size:
        return None
    best, ink = _closest_lookalike(page, rect, text, size, baseline)
    if best and best[0] < 0.9:
        return best[1:]
    # Justified or letter-spaced lines never line up glyph by glyph: compare the longest word alone
    try:
        words = [w for w in page.get_text('words', clip=rect) if len(w[4]) >= 4]
    except Exception:
        words = []
    if words:
        w = max(words, key=lambda w: len(w[4]))
        wbest, _ = _closest_lookalike(page, fitz.Rect(w[:4]), w[4], size, baseline)
        if wbest and wbest[0] < 0.9:
            return wbest[1:]
    # Last resort: the amount of ink still tells the weight
    if len(ink) == 2:
        return 'arial', abs(ink[1] - 1) < abs(ink[0] - 1), False, 1.0
    return None


def _match_font(page, span_font, flags, orig_text, orig_width, orig_size, new_text, keep_style=True,
                rect=None, baseline=None):
    """Font for re-typing a line so it looks like the original. Call BEFORE redaction.

    1. The PDF's own embedded font, if it reproduces the original line at its original width
       (proves the glyph mapping is usable) and has every character of the new text.
    2. Otherwise the closest Windows font. Fonts look bigger or smaller at the same point size
       (Calibri is much smaller than DejaVu or Roboto), so the size is scaled until the original
       text would have had its original width.
    Returns ({'buffer': bytes} | {'fontfile', 'fontname'}, size factor)."""
    orig = (orig_text or '').strip()
    if keep_style and orig and orig_width > 2:
        buf = _embedded_font(page, span_font)
        if buf:
            try:
                f = fitz.Font(fontbuffer=buf)
                if all(f.has_glyph(ord(ch)) for ch in set(new_text) - set(orig)):
                    w = f.text_length(orig, fontsize=orig_size)
                    if w and abs(w - orig_width) / orig_width < 0.04:
                        return {'buffer': buf}, 1.0
            except Exception:
                pass
    lookup = span_font or ''
    guess = None
    if rect is not None and baseline is not None and _unknown_font(span_font):
        guess = _guess_font_visually(page, rect, orig, orig_size, baseline)
    if guess:
        family, bold, italic, fit = guess
        if keep_style:
            flags = ((flags | 16) if bold else (flags & ~16))
            flags = ((flags | 2) if italic else (flags & ~2))
        lookup = family + (' bold' if flags & 16 else '') + (' italic' if flags & 2 else '')
    if not (flags & 16):
        lookup = re.sub(r'(?i)(bold|heavy|black|demi)', '', lookup).strip(' -_') or lookup
    if not (flags & 2):
        lookup = re.sub(r'(?i)(italic|oblique|slant)', '', lookup).strip(' -_') or lookup
    ff, fn, _, _ = resolve_font(lookup, flags) if lookup else (UNICODE_FONT, UNICODE_FONTNAME, 0, 0)
    if not ff:
        return {}, 1.0
    factor = 1.0
    if guess:
        # The look-alike already matched the original pixels at this size (on a single word for
        # justified lines, whose stretched gaps would otherwise make the text up to 30% too big)
        factor = guess[3]
    elif orig and orig_width > 5 and len(orig) >= 3:
        try:
            font = fitz.Font(fontfile=ff)
            w = font.text_length(orig, fontsize=orig_size)
            if w > 0:
                factor = min(1.3, max(0.77, orig_width / w))
            # A justified line's width includes stretched word gaps; if the longest word alone
            # needs a smaller size, the gaps were stretched and the word is the honest measure
            if rect is not None and len(orig.split()) > 1:
                words = [x for x in page.get_text('words', clip=rect) if len(x[4]) >= 4]
                if words:
                    word = max(words, key=lambda x: len(x[4]))
                    ww = font.text_length(word[4], fontsize=orig_size)
                    if ww > 0:
                        factor = min(factor, max(0.77, (word[2] - word[0]) / ww))
        except Exception:
            pass
    return {'fontfile': ff, 'fontname': fn}, factor


def _font_kwargs(page, spec):
    """insert_text keyword arguments for a _match_font() result (registers an embedded font)."""
    if 'buffer' in spec:
        name = 'E' + format(abs(hash(spec['buffer'])) % 10**8, 'd')
        page.insert_font(fontname=name, fontbuffer=spec['buffer'])
        return {'fontname': name}
    kw = dict(spec)
    # "cour", "helv", "tiro"... are PyMuPDF's built-in Base-14 fonts: with such a name the font
    # file is ignored and Turkish letters come out wrong (cour.ttf → İ printed as "·")
    if kw.get('fontname', '').lower() in _BASE14_NAMES:
        kw['fontname'] = 'F' + kw['fontname']
    return kw


_BASE14_NAMES = {'helv', 'heit', 'hebo', 'hebi', 'cour', 'coit', 'cobo', 'cobi',
                 'tiro', 'tibo', 'tiit', 'tibi', 'symb', 'zadb'}


def _text_width(spec, text, size):
    try:
        f = fitz.Font(fontbuffer=spec['buffer']) if 'buffer' in spec else \
            fitz.Font(fontfile=spec['fontfile']) if spec.get('fontfile') else fitz.Font('helv')
        return f.text_length(text, fontsize=size)
    except Exception:
        return 0


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
        # Fonts that are not installed: nearest look-alike (sans before serif: "sansserif")
        'sans':          ('arial.ttf',    'arialbd.ttf',  'ariali.ttf',   'arialbi.ttf'),
        'roboto':        ('arial.ttf',    'arialbd.ttf',  'ariali.ttf',   'arialbi.ttf'),
        'arimo':         ('arial.ttf',    'arialbd.ttf',  'ariali.ttf',   'arialbi.ttf'),
        'lato':          ('arial.ttf',    'arialbd.ttf',  'ariali.ttf',   'arialbi.ttf'),
        'serif':         ('times.ttf',    'timesbd.ttf',  'timesi.ttf',   'timesbi.ttf'),
        'tinos':         ('times.ttf',    'timesbd.ttf',  'timesi.ttf',   'timesbi.ttf'),
        'minion':        ('times.ttf',    'timesbd.ttf',  'timesi.ttf',   'timesbi.ttf'),
        'palatino':      ('pala.ttf',     'palab.ttf',    'palai.ttf',    'palabi.ttf'),
    }

    idx = (1 if is_bold else 0) + (2 if is_italic else 0)
    # Free font families shipped with the app (static/fonts): when a PDF embeds only a subset
    # of one of these, edits with new characters still use the very same typeface
    BUNDLED = {
        'dejavusansmono': ('DejaVuSansMono.ttf', 'DejaVuSansMono-Bold.ttf', 'DejaVuSansMono.ttf', 'DejaVuSansMono-Bold.ttf'),
        'dejavusans':     ('DejaVuSans.ttf', 'DejaVuSans-Bold.ttf', 'DejaVuSans-Oblique.ttf', 'DejaVuSans-BoldOblique.ttf'),
        'dejavuserif':    ('DejaVuSerif.ttf', 'DejaVuSerif-Bold.ttf', 'DejaVuSerif-Italic.ttf', 'DejaVuSerif-BoldItalic.ttf'),
    }
    font_dir = os.path.join(_BASE_DIR, 'static', 'fonts')
    for key, files in BUNDLED.items():
        if key in base:
            f = os.path.join(font_dir, files[idx])
            if os.path.exists(f):
                return f, os.path.splitext(files[idx])[0].replace('-', ''), is_bold, is_italic
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
    _count_launch()
    resp = make_response(render_template('index.html', demo_mode=demo, can_activate=demo,
                                         app_version=APP_VERSION))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route('/activate')
def activate_page():
    if not is_demo():
        return redirect('/')
    return render_template('activate.html', lang=state.get('ui_lang') or '')


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
        doc = _swap_doc(doc, path, data.get('name'))
        sigs   = detect_signatures(doc)
        fields = detect_form_fields(doc)
        return jsonify({'ok': True, 'pages': len(doc), 'name': _doc_name(),
                        'signatures': sigs, 'form_fields': fields,
                        'demo_full': _demo_over_limit()})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})



@app.route('/api/page_sizes')
def api_page_sizes():
    """Okuma modu ve yazdırma için sayfa boyutları (pt) ve yazdırma izni."""
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Açık dosya yok'})
    sizes = [[round(p.rect.width, 2), round(p.rect.height, 2)] for p in doc]
    return jsonify({'ok': True, 'sizes': sizes, 'name': _doc_name(), 'print_block': ''})


def _page_png(i, scale):
    pix = state['doc'][i].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    resp = app.response_class(pix.tobytes('png'), mimetype='image/png')
    resp.headers['Cache-Control'] = 'no-store'
    return resp


@app.route('/api/view/<int:i>')
def api_view(i):
    """Okuma modu: sayfa görüntüsü, istenen ölçekte (1.0 = 72 DPI)."""
    doc = state['doc']
    if not doc or not 0 <= i < len(doc):
        return ('', 404)
    scale = min(max(request.args.get('s', 1.5, type=float), 0.25), 5.0)
    return _page_png(i, scale)


@app.route('/api/print_page/<int:i>')
def api_print_page(i):
    """Yazdırma: sayfa görüntüsü. Düzenlemeler ve açıklamalar dahil, seçilen DPI'da."""
    doc = state['doc']
    if not doc or not 0 <= i < len(doc):
        return ('', 404)
    dpi = min(max(request.args.get('dpi', 150, type=int), 72), 600)
    return _page_png(i, dpi / 72)


@app.route('/api/text')
def api_text():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Açık dosya yok'})
    try:
        text = '\n\n'.join(_page_text(doc[i]) for i in range(len(doc)))
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
        clear_history()
        _trial_new_doc()
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
    # z: görüntü ölçeği (1.0 = 72 DPI); düzenleme görünümü yakınlaştırınca daha net görüntü ister
    zoom = min(max(request.args.get('z', 2.0, type=float), 1.0), 6.0)
    mat = fitz.Matrix(zoom, zoom)
    pix = doc[i].get_pixmap(matrix=mat)
    data = base64.b64encode(pix.tobytes('png')).decode()
    return jsonify({
        'ok': True,
        'img': data,
        'pdf_w': doc[i].rect.width,
        'pdf_h': doc[i].rect.height,
        'zoom': zoom
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
    guess_cache = {}
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

        # Collect sizes, baselines and the original span style BEFORE redaction removes the text.
        page_dict = page.get_text('dict')
        spans     = [_span_at(page_dict, r) for r in hits]
        # The span's own size; the bbox-based estimate came out ~9% too large and overlapped neighbours
        sizes     = [forced_size or (s['size'] if s else 0) or size_at_rect(page, r) for r, s in zip(hits, spans)]
        baselines = [_get_baseline_y(page, r, page_dict) for r in hits]
        # Room to the right of each hit: up to the next word on the same line, else the page margin
        words = page.get_text('words')
        room = []
        for r in hits:
            right = [w[0] for w in words if w[0] >= r.x1 - 0.5 and min(w[3], r.y1) - max(w[1], r.y0) > r.height * 0.5]
            room.append((min(right) - 2 if right else page.rect.width - 36) - r.x0)
        # Unnamed fonts (Chromium PDFs): guess the look-alike from the whole span before it is redacted
        guesses = []
        for s in spans:
            g = None
            if s and _unknown_font(pdf_font or s['font']):
                key = (s['text'], round(s['size'], 1))
                if key not in guess_cache:
                    guess_cache[key] = _guess_font_visually(page, fitz.Rect(s['bbox']), s['text'], s['size'], s['origin'][1])
                g = guess_cache[key]
            guesses.append(g)

        for rect in hits:
            page.add_redact_annot(rect, fill=(1, 1, 1))
        page.apply_redactions(graphics=0)

        if repl:
            for rect, sz, fallback_bl, span, guess, space in zip(hits, sizes, baselines, spans, guesses, room):
                bl_y  = provided_baseline if provided_baseline is not None else fallback_bl
                # Global replace: keep each occurrence's own font, weight, style and colour
                hit_font, hit_flags = (pdf_font, font_flags) if pdf_font else \
                    ((span['font'], span['flags']) if span else (None, 0))
                if guess:
                    hit_flags = (hit_flags | 16) if guess[1] else (hit_flags & ~16)
                    hit_flags = (hit_flags | 2) if guess[2] else (hit_flags & ~2)
                    hit_font = guess[0] + (' bold' if guess[1] else '') + (' italic' if guess[2] else '')
                if provided_color:
                    color = tuple(provided_color)
                elif span:
                    c = span['color']
                    color = (((c >> 16) & 255) / 255, ((c >> 8) & 255) / 255, (c & 255) / 255)
                else:
                    color = (0, 0, 0)
                kw = {'fontsize': sz * (guess[3] if guess and not forced_size else 1.0), 'color': color}
                if hit_font:
                    ff, fn, _, _ = resolve_font(hit_font, hit_flags)
                    if ff:
                        kw['fontfile'] = ff
                        kw['fontname'] = fn
                    elif UNICODE_FONT:
                        kw['fontfile'] = UNICODE_FONT
                        kw['fontname'] = UNICODE_FONTNAME
                elif UNICODE_FONT:
                    kw['fontfile'] = UNICODE_FONT
                    kw['fontname'] = UNICODE_FONTNAME
                # Longer replacement: shrink it (to 75% at most) only if it would run into the next word
                try:
                    width = fitz.Font(fontfile=kw['fontfile']).text_length(repl, fontsize=kw['fontsize']) \
                        if kw.get('fontfile') else fitz.get_text_length(repl, fontsize=kw['fontsize'])
                    limit = max(space, rect.width)
                    if width > limit * 1.02:
                        kw['fontsize'] *= max(0.75, limit / width)
                except Exception:
                    pass
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
    orig_size  = float(data.get('orig_size') or sz)
    color      = tuple(data.get('color', [0, 0, 0]))

    page = doc[page_idx]
    if data.get('ocr'):
        page = _upright_scan(page)
    pdf_w, pdf_h = page.rect.width, page.rect.height
    block_rect = fitz.Rect(bx0 * pdf_w, by0 * pdf_h, bx1 * pdf_w, by1 * pdf_h)

    if data.get('ocr') and data.get('words'):
        _replace_scan_words(page, data, new_text, effective_flags, font_flags, sz, orig_size,
                            color, underline, block_rect, baseline_y)
        return jsonify({'ok': True})

    # Same font as the original (or a size-matched substitute); the user's size change is kept as a ratio
    style_kept = effective_flags == font_flags
    spec, factor = _match_font(page, pdf_font, effective_flags, data.get('original_text', ''),
                               block_rect.width, orig_size, new_text, keep_style=style_kept,
                               rect=block_rect, baseline=baseline_y)
    sz = max(sz * factor, 5.0)

    push_history()
    page.add_redact_annot(block_rect, fill=(1, 1, 1))
    page.apply_redactions(graphics=0)

    if new_text:
        kw = {'fontsize': sz, 'color': color}
        kw.update(_font_kwargs(page, spec))
        page.insert_text(fitz.Point(block_rect.x0, baseline_y), new_text, **kw)
        if underline:
            tw = _text_width(spec, new_text, sz) or block_rect.width
            ul_y = baseline_y + sz * 0.12
            page.draw_line(
                fitz.Point(block_rect.x0, ul_y),
                fitz.Point(block_rect.x0 + tw, ul_y),
                color=color, width=max(0.5, sz * 0.04)
            )

    return jsonify({'ok': True})



_SCAN_ZOOM = 4


def _scan_paper(px, letter_px):
    """The paper under every pixel.

    First a median over a square window a few letters wide: moved neither by the letters nor by
    a few bright boxes or dark rules. Then only the pixels that look like that paper (not ink,
    not white form fields, not a coloured bar) are averaged over a window wider than tall, so
    the paper is the one beside the letters at their own height."""
    import numpy as np
    import cv2
    k = min(255, max(15, int(letter_px * 1.5)) | 1)
    rough = cv2.medianBlur(px, k)
    gray = lambda a: a.astype(np.int16) if a.ndim == 2 else a.astype(np.int16).mean(axis=2)
    like = (np.abs(gray(px) - gray(rough)) < 22).astype(np.float32)
    win = (k, max(3, k // 3))
    den = cv2.blur(like, win)
    if px.ndim == 2:
        num = cv2.blur(px.astype(np.float32) * like, win)
        est = num / np.maximum(den, 1e-3)
    else:
        num = cv2.blur(px.astype(np.float32) * like[..., None], win)
        est = num / np.maximum(den, 1e-3)[..., None]
        den = den[..., None]
    return np.where(den > 0.05, est, rough).clip(0, 255).astype(np.uint8)


def _scan_ink(px, letter_px, paper=None):
    """How much darker than the paper around it each pixel is (0..255): print, handwriting, stamps."""
    import numpy as np
    bg = _scan_paper(px, letter_px) if paper is None else paper
    d = bg.astype(np.int16) - px.astype(np.int16)
    return (d.max(axis=2) if d.ndim == 3 else d).clip(0, 255).astype(np.uint8)


def _rebuild_paper(px, letter_px, scale):
    """px with every bit of ink replaced by the paper around it, grain included.
    scale is pixels per point."""
    import numpy as np
    import cv2
    paper = _scan_paper(px, letter_px)
    ink = _scan_ink(px, letter_px, paper)
    # Wide enough to take the light JPEG halo around the letters too
    mask = cv2.dilate((ink > 20).astype(np.uint8), np.ones((3, 3), np.uint8),
                      iterations=max(2, round(1.0 * scale) + 1)) > 0
    paper_px = ~mask
    filled = np.where(paper_px if px.ndim == 2 else paper_px[..., None], px, paper)
    # The rebuilt paper is smooth; give it the scan's grain so the letters do not show as blobs
    if paper_px.sum() > 50:
        smooth = cv2.GaussianBlur(px, (0, 0), 2).astype(np.float32)
        grain = float(np.std((px.astype(np.float32) - smooth)[paper_px]))
        noisy = (filled + np.random.normal(0, grain, px.shape)).clip(0, 255).astype(np.uint8)
        filled = np.where(paper_px if px.ndim == 2 else paper_px[..., None], filled, noisy)
    return filled


# ── Edits written into the scan picture itself ──────────────────────────────
# One picture stays one picture: no patches piling up on it, the erased text is really gone from
# its pixels, and "clean background" or the Word export later see the page as it looks.

def _upright_scan(page):
    """A scanned page stored turned (/Rotate) made upright for real: its picture's pixels are
    turned and the page set to 0°, looking exactly the same. What is shown (and read by OCR) and
    what is edited then share one coordinate system; on a turned page edits landed turned and in
    the wrong place. Returns the page to use from now on."""
    import numpy as np
    import cv2
    rot = page.rotation
    if not rot or not scan_ocr.is_scan_page(page):
        return page
    doc, i = page.parent, page.number
    full = abs(page.mediabox) or 1
    pic = None
    for img in page.get_images(full=True):
        try:
            rects = page.get_image_rects(img[0], transform=True)
        except Exception:
            continue
        if len(rects) == 1:
            r, m = rects[0]
            if abs(r & page.mediabox) / full > 0.9 and abs(m.b) < 1e-6 and abs(m.c) < 1e-6 and m.a > 0 and m.d > 0:
                pic = img
                break
    if pic is None:
        return page
    pix = fitz.Pixmap(doc, pic[0])
    if pix.alpha:
        pix = fitz.Pixmap(pix, 0)
    if pix.n not in (1, 3):
        pix = fitz.Pixmap(fitz.csRGB, pix)
    shape = (pix.height, pix.width) if pix.n == 1 else (pix.height, pix.width, 3)
    arr = np.frombuffer(pix.samples, np.uint8).reshape(shape)
    arr = np.ascontiguousarray(np.rot90(arr, -(rot // 90)))   # /Rotate turns clockwise
    del pix
    jpeg = 'DCT' in (doc.xref_get_key(pic[0], 'Filter')[1] or '')
    out = arr
    if arr.ndim == 3:
        cv2.cvtColor(arr, cv2.COLOR_RGB2BGR, dst=arr)
    ok, data = (cv2.imencode('.jpg', out, [cv2.IMWRITE_JPEG_QUALITY, 95]) if jpeg else cv2.imencode('.png', out))
    if not ok:
        return page
    w, h = page.rect.width, page.rect.height        # as shown
    new = doc.new_page(pno=i, width=w, height=h)
    new.insert_image(new.rect, stream=data.tobytes())
    doc.delete_page(i + 1)
    return doc[i]


def _scan_target(page):
    """(xref, matrix) of the scan picture when it is placed upright on an unrotated page."""
    if page.rotation:
        return None
    area = abs(page.rect) or 1
    for img in page.get_images(full=True):
        if img[1]:
            continue
        try:
            rects = page.get_image_rects(img[0], transform=True)
        except Exception:
            continue
        if len(rects) != 1:
            continue
        r, m = rects[0]
        if abs(r & page.rect) / area > 0.6 and abs(m.b) < 1e-6 and abs(m.c) < 1e-6 and m.a > 0 and m.d > 0:
            return img[0], m
    return None


class _ScanPixels:
    """The scan picture's own pixels, edited in place and written back with save()."""

    def __init__(self, page, xref, m):
        import numpy as np
        self.page, self.xref, self.m = page, xref, m
        pix = fitz.Pixmap(page.parent, xref)
        if pix.alpha:
            pix = fitz.Pixmap(pix, 0)
        if pix.n not in (1, 3):
            pix = fitz.Pixmap(fitz.csRGB, pix)
        shape = (pix.height, pix.width) if pix.n == 1 else (pix.height, pix.width, 3)
        self.arr = np.frombuffer(pix.samples, np.uint8).reshape(shape).copy()
        self.sx, self.sy = pix.width / m.a, pix.height / m.d     # pixels per point
        del pix      # a 600 dpi page is 100 MB: do not hold MuPDF's copy next to ours

    def box(self, rect):
        h, w = self.arr.shape[:2]
        return (max(0, round((rect.x0 - self.m.e) * self.sx)), max(0, round((rect.y0 - self.m.f) * self.sy)),
                min(w, round((rect.x1 - self.m.e) * self.sx)), min(h, round((rect.y1 - self.m.f) * self.sy)))

    def _crop(self, rect):
        x0, y0, x1, y1 = self.box(rect)
        mg = int(max(rect.height * self.sy * 0.6, 6))
        h, w = self.arr.shape[:2]
        return (x0, y0, x1, y1), (max(0, x0 - mg), max(0, y0 - mg), min(w, x1 + mg), min(h, y1 + mg))

    def erase(self, rect):
        import numpy as np
        (x0, y0, x1, y1), (cx0, cy0, cx1, cy1) = self._crop(rect)
        if x1 - x0 < 2 or y1 - y0 < 2:
            return
        filled = _rebuild_paper(np.ascontiguousarray(self.arr[cy0:cy1, cx0:cx1]), rect.height * self.sy, self.sy)
        self.arr[y0:y1, x0:x1] = filled[y0 - cy0:y1 - cy0, x0 - cx0:x1 - cx0]

    def ink(self, rect):
        """(pixels, alpha 0..1, box) of the ink inside rect."""
        import numpy as np
        (x0, y0, x1, y1), (cx0, cy0, cx1, cy1) = self._crop(rect)
        crop = np.ascontiguousarray(self.arr[cy0:cy1, cx0:cx1])
        a = ((_scan_ink(crop, rect.height * self.sy).astype(np.float32) - 12) * 4).clip(0, 255) / 255
        sl = (slice(y0 - cy0, y1 - cy0), slice(x0 - cx0, x1 - cx0))
        return crop[sl].astype(np.float32), a[sl], (x0, y0, x1, y1)

    def paste(self, px, a, x, y):
        import numpy as np
        h, w = self.arr.shape[:2]
        ph, pw = a.shape
        dx0, dy0, dx1, dy1 = max(0, x), max(0, y), min(w, x + pw), min(h, y + ph)
        if dx1 <= dx0 or dy1 <= dy0:
            return
        sp, sa = px[dy0 - y:dy1 - y, dx0 - x:dx1 - x], a[dy0 - y:dy1 - y, dx0 - x:dx1 - x]
        if self.arr.ndim == 3:
            sa = sa[..., None]
        dst = self.arr[dy0:dy1, dx0:dx1].astype(np.float32)
        self.arr[dy0:dy1, dx0:dx1] = (dst * (1 - sa) + sp * sa).clip(0, 255).astype(np.uint8)

    # ── Typing into the picture ──
    # Re-typed words drawn as crisp computer text never quite match a scan, however well the font,
    # size and colour are chosen: the scan's letters are soft, spread and toned. So the word is
    # drawn into the picture itself, looking the way the scan's own words were measured to look.

    def _clip(self, box):
        return fitz.Rect(self.m.e + box[0] / self.sx, self.m.f + box[1] / self.sy,
                         self.m.e + box[2] / self.sx, self.m.f + box[3] / self.sy)

    _HI = 4   # typing is shaped at 4× the picture's resolution: its strokes are only ~2 px wide

    def text_cover(self, spec, size, text, x, baseline, box):
        """How much of each picture pixel in box the text covers (0..1), on a grid _HI times finer
        than the picture's and aligned with it."""
        import numpy as np
        k = self._HI
        scratch = fitz.open()
        sp = scratch.new_page(width=self.page.rect.width, height=self.page.rect.height)
        sp.insert_text(fitz.Point(x, baseline), text, fontsize=size, color=(0, 0, 0), **_font_kwargs(sp, spec))
        mat = fitz.Matrix(self.sx * k, 0, 0, self.sy * k, -self.m.e * self.sx * k, -self.m.f * self.sy * k)
        pm = sp.get_pixmap(matrix=mat, clip=self._clip(box), colorspace=fitz.csGRAY, alpha=False)
        g = np.frombuffer(pm.samples, np.uint8).reshape(pm.height, pm.width)
        scratch.close()
        out = np.zeros(((box[3] - box[1]) * k, (box[2] - box[0]) * k), np.float32)
        oy, ox = pm.y - box[1] * k, pm.x - box[0] * k     # the pixmap may start a pixel off the box
        ys, xs = max(0, oy), max(0, ox)
        ye, xe = min(out.shape[0], oy + pm.height), min(out.shape[1], ox + pm.width)
        if ye > ys and xe > xs:
            out[ys:ye, xs:xe] = (255 - g[ys - oy:ye - oy, xs - ox:xe - ox]) / 255
        return out

    @classmethod
    def _shape(cls, cover, grow, blur):
        """The fine cover thickened/thinned by grow fine pixels and softened by blur picture
        pixels, brought down to the picture's grid."""
        import numpy as np
        import cv2
        k = cls._HI
        c = cover
        if grow > 0:
            c = cv2.dilate(c, np.ones((3, 3), np.uint8), iterations=grow)
        elif grow < 0:
            c = cv2.erode(c, np.ones((3, 3), np.uint8), iterations=-grow)
        if blur:
            c = cv2.GaussianBlur(c, (0, 0), blur * k)
        h, w = c.shape[0] // k, c.shape[1] // k
        return cv2.resize(c, (w, h), interpolation=cv2.INTER_AREA).clip(0, 1)

    @staticmethod
    def _shift(a, dx, dy):
        import numpy as np
        return np.roll(np.roll(a, dy, axis=0), dx, axis=1)

    def _ink_box(self, rect, size):
        return self.box(fitz.Rect(rect.x0 - size * 0.4, rect.y0 - size * 0.4, rect.x1 + size * 0.4, rect.y1 + size * 0.4))

    def measure_look(self, spec, size, words, baseline):
        """How the scan's own words differ from the same words typed in spec/size: size factor,
        stroke growth, softness, a small offset and tone. Measured on the longest words, before
        anything is erased. Also returns the ink colour."""
        import numpy as np
        sample = sorted((w for w in words if len(w[1]) >= 2), key=lambda w: -len(w[1]))[:2] or words[:1]
        inks, trials = [], []
        for r, t in sample:
            box = self._ink_box(r, size)
            if box[2] - box[0] < 4 or box[3] - box[1] < 4:
                continue
            crop = self.arr[box[1]:box[3], box[0]:box[2]].astype(np.float32)
            gray = crop if crop.ndim == 2 else crop.mean(axis=2)
            paper, dark = np.percentile(gray, 95), np.percentile(gray, 2)
            if paper - dark < 30:
                continue
            seen = ((paper - gray) / (paper - dark)).clip(0, 1)     # 1 where the ink is darkest
            inks.append(crop[seen > 0.85].mean(axis=0) if (seen > 0.85).any() else dark)
            covers = {s: self.text_cover(spec, size * s, t, r.x0, baseline, box) for s in (0.88, 0.94, 1.0, 1.06, 1.12)}
            # Ink is compared inside the word's own box only, not in the margin where
            # neighbouring letters and specks would count too
            wb = self.box(r)
            inner = (slice(max(0, wb[1] - box[1]), wb[3] - box[1]), slice(max(0, wb[0] - box[0]), wb[2] - box[0]))
            trials.append((seen, covers, inner))
        if not trials:
            return None
        import cv2

        def sharpness(a):
            # How steeply ink turns into paper, against how dark the ink gets: independent of
            # which letters are drawn, so a look-alike face cannot bias it the way a fit does
            gx, gy = cv2.Sobel(a, cv2.CV_32F, 1, 0), cv2.Sobel(a, cv2.CV_32F, 0, 1)
            mag = np.hypot(gx, gy)
            top = float(np.percentile(a, 99)) or 1.0
            return float(np.percentile(mag[a > 0.1], 90)) / top if (a > 0.1).any() else 0.0

        want = float(np.median([sharpness(seen[inner]) for seen, _, inner in trials]))
        blur = min((0, 0.3, 0.5, 0.7, 1.0, 1.4), key=lambda b: abs(float(np.median(
            [sharpness(self._shape(c[1.0], 0, b)[inner]) for _, c, inner in trials])) - want))
        best = None
        for s in (0.88, 0.94, 1.0, 1.06, 1.12):
            for blur in (blur,):
                shaped = [(seen, self._shape(c[s], 0, blur)) for seen, c, _ in trials]
                for dx in range(-5, 6):
                    for dy in range(-3, 4):
                        err = sum(float(np.abs(self._shift(a, dx, dy) - seen).mean()) for seen, a in shaped)
                        if best is None or err < best[0]:
                            best = (err, s, blur, dx, dy)
        _, s, blur, dx, dy = best
        # The weight from the amount of ink the scan's own words put down, in fine steps
        def ink_sum(a):
            return float(np.where(a > 0.35, a, 0).sum())   # paper grain is not ink

        def ratio(g):
            made = sum(ink_sum(self._shift(self._shape(c[s], g, blur), dx, dy)[inner]) for _, c, inner in trials)
            return sum(ink_sum(seen[inner]) for seen, _, inner in trials) / max(made, 1e-3)

        grow = min(range(-3, 5), key=lambda g: abs(np.log(max(ratio(g), 1e-3))))
        gain = float(np.clip(ratio(grow), 0.75, 1.25))   # what the steps cannot reach, the tone does
        return (s, grow, blur, dx, dy, gain), np.mean(inks, axis=0)

    def type_text(self, spec, size, text, x, baseline, look, ink):
        """Draw text into the picture with the measured look."""
        import numpy as np
        scale, grow, blur, dx, dy, gain = look
        w = _text_width(spec, text, size * scale)
        rect = fitz.Rect(x, baseline - size * 1.1, x + w, baseline + size * 0.4)
        box = self._ink_box(rect, size)
        if box[2] - box[0] < 2 or box[3] - box[1] < 2:
            return
        cover = self.text_cover(spec, size * scale, text, x, baseline, box)
        a = (self._shift(self._shape(cover, grow, blur), dx, dy) * gain).clip(0, 1)
        dst = self.arr[box[1]:box[3], box[0]:box[2]].astype(np.float32)
        ink = np.asarray(ink, np.float32)
        if dst.ndim == 3:
            a = a[..., None]
        self.arr[box[1]:box[3], box[0]:box[2]] = (dst * (1 - a) + ink * a).clip(0, 255).astype(np.uint8)

    def save(self):
        import cv2
        jpeg = 'DCT' in (self.page.parent.xref_get_key(self.xref, 'Filter')[1] or '')
        img = self.arr
        if img.ndim == 3:
            cv2.cvtColor(img, cv2.COLOR_RGB2BGR, dst=img)    # in place: no second full-page copy
        ok, data = (cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 92]) if jpeg
                    else cv2.imencode('.png', img))
        if ok:
            self.page.replace_image(self.xref, stream=data.tobytes())


def _remove_hidden_text(page, rect):
    """Drop the text under rect (the scanner's invisible OCR layer) and nothing else."""
    page.add_redact_annot(rect, fill=None)
    page.apply_redactions(images=0, graphics=0)


# ── Fallback for pictures placed rotated or shared: patch images laid on top ───

def _scan_pixmap(page, rect):
    """RGB pixels of rect plus a margin of paper around it, and rect in those pixels."""
    import numpy as np
    m = max(rect.height * 0.6, 3)
    clip = fitz.Rect(rect.x0 - m, rect.y0 - m, rect.x1 + m, rect.y1 + m) & page.rect
    pix = page.get_pixmap(matrix=fitz.Matrix(_SCAN_ZOOM, _SCAN_ZOOM), clip=clip, colorspace=fitz.csRGB,
                          alpha=False, annots=False)
    arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3).copy()
    box = [max(0, round((rect.x0 - clip.x0) * _SCAN_ZOOM)), max(0, round((rect.y0 - clip.y0) * _SCAN_ZOOM)),
           min(pix.width, round((rect.x1 - clip.x0) * _SCAN_ZOOM)),
           min(pix.height, round((rect.y1 - clip.y0) * _SCAN_ZOOM))]
    exact = fitz.Rect(clip.x0 + box[0] / _SCAN_ZOOM, clip.y0 + box[1] / _SCAN_ZOOM,
                      clip.x0 + box[2] / _SCAN_ZOOM, clip.y0 + box[3] / _SCAN_ZOOM)
    return arr, box, exact


def _erase_scan(page, rect, paper):
    """Remove the scanned print (and invisible OCR text) under rect.

    The hole is not painted in one flat colour: on grey copies, coloured forms or gradients that
    leaves a visible patch. Only the ink is taken out and rebuilt from the paper around it, so
    the paper between the letters stays the original picture."""
    t = _scan_target(page)
    if t:
        sp = _ScanPixels(page, *t)
        sp.erase(rect)
        _remove_hidden_text(page, rect)
        sp.save()
        return
    arr, (x0, y0, x1, y1), exact = _scan_pixmap(page, rect)
    patch = None
    if x1 - x0 >= 2 and y1 - y0 >= 2:
        filled = _rebuild_paper(arr, rect.height * _SCAN_ZOOM, _SCAN_ZOOM)
        # The redaction blanks whole scan pixels, which can reach a little past rect: the patch
        # overlaps it by a few pixels of untouched paper so no sliver of fill colour shows
        e = 2 * _SCAN_ZOOM
        h, w = arr.shape[:2]
        px0, py0, px1, py1 = max(0, x0 - e), max(0, y0 - e), min(w, x1 + e), min(h, y1 + e)
        patch = arr[py0:py1, px0:px1].copy()
        patch[y0 - py0:y1 - py0, x0 - px0:x1 - px0] = filled[y0:y1, x0:x1]
        cover = fitz.Rect(exact.x0 - (x0 - px0) / _SCAN_ZOOM, exact.y0 - (y0 - py0) / _SCAN_ZOOM,
                          exact.x1 + (px1 - x1) / _SCAN_ZOOM, exact.y1 + (py1 - y1) / _SCAN_ZOOM)
    page.add_redact_annot(exact, fill=tuple(paper or (1, 1, 1)))
    page.apply_redactions(images=getattr(fitz, 'PDF_REDACT_IMAGE_PIXELS', 2), graphics=0)
    if patch is not None:
        page.insert_image(cover, pixmap=fitz.Pixmap(fitz.csRGB, patch.shape[1], patch.shape[0],
                                                    patch.tobytes(), False))


def _move_scan(page, src, dx, dy, paper):
    """Move the scanned print inside src by (dx, dy) points. Only the ink moves: its own paper
    pasted onto tinted or gradient paper would show as a box."""
    import numpy as np
    t = _scan_target(page)
    if t:
        sp = _ScanPixels(page, *t)
        px, a, (x0, y0, _, _) = sp.ink(src)
        sp.erase(src)
        sp.paste(px, a, x0 + round(dx * sp.sx), y0 + round(dy * sp.sy))
        _remove_hidden_text(page, src)
        sp.save()
        return
    arr, (x0, y0, x1, y1), exact = _scan_pixmap(page, src)
    ink = _scan_ink(arr, src.height * _SCAN_ZOOM)
    alpha = ((ink.astype(np.int16) - 12) * 4).clip(0, 255).astype(np.uint8)
    rgba = np.ascontiguousarray(np.dstack([arr, alpha])[y0:y1, x0:x1])
    pix = fitz.Pixmap(fitz.csRGB, rgba.shape[1], rgba.shape[0], rgba.tobytes(), True)
    _erase_scan(page, exact, paper)
    page.insert_image(exact + (dx, dy, dx, dy), pixmap=pix)


# Typefaces tried on scans: office documents, receipts and typewriter / dot-matrix print
_SCAN_FONTS = {
    'arial':   ('arial.ttf', 'arialbd.ttf'),
    'times':   ('times.ttf', 'timesbd.ttf'),
    'courier': ('cour.ttf', 'courbd.ttf'),
    'calibri': ('calibri.ttf', 'calibrib.ttf'),
    'verdana': ('verdana.ttf', 'verdanab.ttf'),
    'tahoma':  ('tahoma.ttf', 'tahomabd.ttf'),
    'segoe':   ('segoeui.ttf', 'segoeuib.ttf'),
    'corbel':  ('corbel.ttf', 'corbelb.ttf'),
    'candara': ('Candara.ttf', 'Candarab.ttf'),
    'gothic':  ('GOTHIC.TTF', 'GOTHICB.TTF'),
}


_GRAY = {'key': None, 'img': None}


def _gray_clip(page, clip, zoom=4):
    """Grey pixels of clip at zoom 4, cut from one rendering of the whole page kept while the page
    is unchanged. On a 600 dpi scan every separate clip rendering decodes the whole 100 MB
    picture again (0.6 s each): reading a page's lines took minutes, one edit 10+ seconds."""
    import numpy as np
    if zoom != 4:
        pm = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, colorspace=fitz.csGRAY, alpha=False, annots=False)
        return np.frombuffer(pm.samples, np.uint8).reshape(pm.height, pm.width)
    key = (id(page.parent), page.number, scan_ocr._fingerprint(page))
    if _GRAY['key'] != key:
        _GRAY['img'] = None          # let the old one go first
        pm = page.get_pixmap(matrix=fitz.Matrix(4, 4), colorspace=fitz.csGRAY, alpha=False, annots=False)
        _GRAY['img'] = np.frombuffer(pm.samples, np.uint8).reshape(pm.height, pm.width).copy()
        _GRAY['key'] = key
    g = _GRAY['img']
    x0, y0 = max(0, int(clip.x0 * 4)), max(0, int(clip.y0 * 4))
    x1, y1 = min(g.shape[1], int(np.ceil(clip.x1 * 4))), min(g.shape[0], int(np.ceil(clip.y1 * 4)))
    return g[y0:max(y0, y1), x0:max(x0, x1)]


def _ink_baseline(page, rect, invert=False):
    """The baseline of the print in rect, read from the pixels: OCR word boxes often reach into
    the next line, and a baseline taken from their bottom puts re-typed words a line too low.
    The line's own band of ink is found in the row profile; its baseline is the lowest row still
    carrying a good share of the band's ink (descenders carry little)."""
    import numpy as np
    import cv2
    h = rect.height
    clip = fitz.Rect(rect.x0, rect.y0 - h * 0.6, rect.x1, rect.y1 + h * 0.6) & page.rect
    if clip.is_empty:
        return None
    z = 4
    g = _gray_clip(page, clip, z)
    if g.size == 0:
        return None
    if invert:
        g = 255 - g
    _, ink = cv2.threshold(g, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    prof = ink.sum(axis=1).astype(np.float32)
    if prof.max() <= 0:
        return None
    on = prof > prof.max() * 0.06
    runs, start = [], None
    for y, v in enumerate(list(on) + [False]):
        if v and start is None:
            start = y
        elif not v and start is not None:
            runs.append((start, y))
            start = None
    mid = ((rect.y0 + rect.y1) / 2 - clip.y0) * z
    # The band the word boxes are centred on (or nearest to it)
    a, b = min(runs, key=lambda r: 0 if r[0] <= mid <= r[1] else min(abs(r[0] - mid), abs(r[1] - mid)))
    band = prof[a:b]
    strong = np.nonzero(band > band.max() * 0.35)[0]
    if not len(strong):
        return None
    return clip.y0 + (a + strong[-1] + 1) / z


def _light_on_dark(page, rect):
    """True for light print on dark paper (white text in a coloured bar)."""
    import numpy as np
    clip = fitz.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2) & page.rect
    if clip.is_empty:
        return False
    g = _gray_clip(page, clip, 4).astype(np.float32)
    if g.size == 0:
        return False
    med, lo, hi = np.median(g), np.percentile(g, 5), np.percentile(g, 95)
    return med < 180 and (hi - med) > (med - lo) * 1.3


def _ink_crop(mask):
    """mask cut to the bounding box of its ink, with that box's (x0, y0, x1, y1) in pixels."""
    import numpy as np
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return None, None
    return mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1], (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)


_PIL_FONTS = {}


def _word_ink(fontfile, text, px=40):
    """Ink mask of text set in fontfile at px pixels (FreeType via Pillow: ~100× faster than a
    PDF page per trial, which made reading every line of a big scan take minutes)."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    font = _PIL_FONTS.get(fontfile)
    if font is None:
        font = _PIL_FONTS[fontfile] = ImageFont.truetype(fontfile, px)
    img = Image.new('L', (int(px * len(text)) + 2 * px, 2 * px + px // 2), 255)
    ImageDraw.Draw(img).text((px // 2, px // 2), text, font=font, fill=0)
    return np.asarray(img) < 128


def _guess_scan_font(page, words, baseline, only=None, samples=3, invert=False):
    """(fontfile, fontname, size, baseline) of the Windows font that looks most like the scanned words.

    OCR word boxes are a few pixels off and scanned ink is thicker and blurrier than any rendering,
    so each candidate is rendered, scaled onto the word's ink box and thinned / thickened to the
    same amount of ink before the shapes are compared; only then do Courier, Arial and Times differ
    by their letter shapes instead of by their weight."""
    import numpy as np
    import cv2
    sample = sorted((w for w in words if len(w[1]) >= 2), key=lambda w: -len(w[1]))[:samples] or words[:1]
    zoom = 4
    refs = []
    for r, t in sample:
        clip = fitz.Rect(r.x0 - 2, r.y0 - 2, r.x1 + 2, r.y1 + 2) & page.rect
        g = _gray_clip(page, clip, zoom).astype(np.int16)
        if g.size == 0:
            continue
        if invert:
            g = 255 - g
        lo, hi = np.percentile(g, 3), np.percentile(g, 90)
        if hi - lo < 40:
            continue
        mask = g < (lo + hi) / 2
        # OCR boxes can reach into the next line: keep the word's own band of rows (its accents
        # just above or below stay, the tops of the next line's letters past a gap go)
        rows = mask.sum(axis=1)
        on = rows > max(1, rows.max() * 0.08)
        runs, start = [], None
        for y, v in enumerate(list(on) + [False]):
            if v and start is None:
                start = y
            elif not v and start is not None:
                runs.append((start, y))
                start = None
        if runs:
            main = max(runs, key=lambda r: r[1] - r[0])
            keep = [r for r in runs if r == main or
                    min(abs(r[0] - main[1]), abs(main[0] - r[1])) <= (main[1] - main[0]) * 0.3]
            band = np.zeros_like(on)
            for a, b in keep:
                band[a:b] = True
            mask = mask & band[:, None]
        ref, box = _ink_crop(mask)
        if ref is not None and ref.shape[0] >= 6 and ref.shape[1] >= 6:
            refs.append((t, clip, ref, box))
    if not refs:
        return None
    kernel = np.ones((3, 3), np.uint8)
    best = None
    for fam, files in _SCAN_FONTS.items():
        for bold, fn in enumerate(files):
            ff = 'C:/Windows/Fonts/' + fn
            if not os.path.exists(ff) or (only and ff not in only):
                continue
            # Scanned ink always looks heavier: bold has to win clearly, not by a hair
            score, sizes, hsizes = 0.04 * len(refs) * bold, [], []
            for t, clip, ref, box in refs:
                cand, cbox = _ink_crop(_word_ink(ff, t))
                if cand is None:
                    score += 1
                    continue
                sizes.append(40 * (ref.shape[1] / zoom) / cand.shape[1])
                hsizes.append(40 * (ref.shape[0] / zoom) / cand.shape[0])
                c = cv2.resize(cand.astype(np.uint8), (ref.shape[1], ref.shape[0]),
                               interpolation=cv2.INTER_AREA)
                share = ref.mean()
                for _ in range(6):
                    if c.mean() < share * 0.85:
                        c2 = cv2.dilate(c, kernel)
                    elif c.mean() > share * 1.15:
                        c2 = cv2.erode(c, kernel)
                    else:
                        break
                    if not c2.any():
                        break
                    c = c2
                c = c.astype(bool)
                score += 1 - (c & ref).sum() / max((c | ref).sum(), 1)
            if sizes and (best is None or score < best[0]):
                # Size between what the word's width and its letter height say: a look-alike
                # face is rarely exactly as wide as the original, and the height is what the eye
                # compares (the rest of the line slides to absorb the width)
                w_size, h_size = sorted(sizes)[len(sizes) // 2], sorted(hsizes)[len(hsizes) // 2]
                best = (score, ff, os.path.splitext(fn)[0], (w_size * h_size) ** 0.5)
    if not best:
        return None
    # Baseline from the ink of words without descenders (OCR boxes are only roughly placed)
    bottoms = [clip.y0 + box[3] / zoom for t, clip, ref, box in refs
               if not (set(t) & set('gjpqyşçğŞÇQ,;()[]{}|/'))]
    _guess_scan_font.last_fit = 1 - best[0] / len(refs)   # how well the best font matched (0..1)
    return best[1], best[2], float(best[3]), float(sorted(bottoms)[len(bottoms) // 2] if bottoms else baseline)


def _scan_tone(page, words, spec, size, baseline, color):
    """color adjusted so re-typed text looks as dark as the scanned print around it.

    Solid computer text in the measured ink colour still looks heavier than dotted, grey or
    worn print (dot-matrix, ribbon, faint copies): match the line's average ink instead. Only
    grey/black is adjusted, a colour the user picked is kept."""
    import numpy as np
    if max(color) - min(color) > 0.15:
        return color
    line = fitz.Rect(words[0][0])
    for r, _ in words[1:]:
        line |= r
    clip = fitz.Rect(line.x0 - 1, line.y0 - 1, line.x1 + 1, line.y1 + 1) & page.rect
    if clip.is_empty:
        return color
    z = 4
    g = _gray_clip(page, clip, z).astype(np.float32)
    if g.size == 0:
        return color
    paper = float(np.percentile(g, 90))
    dark = float(np.clip(paper - g, 0, None).mean())
    # The same words typed in black, where they stand
    scratch = fitz.open()
    sp = scratch.new_page(width=page.rect.width, height=page.rect.height)
    kw = _font_kwargs(sp, spec)
    for r, t in words:
        sp.insert_text(fitz.Point(r.x0, baseline), t, fontsize=size, color=(0, 0, 0), **kw)
    pm = sp.get_pixmap(matrix=fitz.Matrix(z, z), clip=clip, colorspace=fitz.csGRAY, alpha=False)
    cover = float((255 - np.frombuffer(pm.samples, np.uint8).astype(np.float32)).mean() / 255)
    scratch.close()
    if cover < 1e-3 or dark < 1:
        return color
    level = (paper - dark / cover) / 255          # the grey that gives the same average ink
    cur = sum(color) / 3
    if level <= cur:
        return color                                # never darker than the measured ink
    level = min(level, 0.75)                        # and still clearly print, not a ghost
    return tuple(round(level, 3) for _ in range(3))


def _replace_scan_words(page, data, new_text, flags, orig_flags, sz, orig_size, color, underline,
                        line_rect, baseline):
    """Edit an OCR'd line of a scan word by word: only the words that changed are erased and
    re-typed, the rest stays the original scanned picture. Re-typing the whole line would also
    bake in every OCR misreading and swap the scanner's look for a computer font."""
    import difflib
    words = [(fitz.Rect(w[:4]), w[4]) for w in data['words']]
    old = [t for _, t in words]
    new = new_text.split()
    style_changed = flags != orig_flags or underline or abs(sz - orig_size) > 0.1
    ops = [o for o in difflib.SequenceMatcher(a=old, b=new, autojunk=False).get_opcodes() if o[0] != 'equal']
    if style_changed:
        spans = [(0, len(old), 0, len(new))]
    elif not ops:
        return
    else:
        # Each change on its own ("Aidat:" and "1120" in one line): the words between them stay
        # the scanned picture
        spans = []
        for _, i0, i1, j0, j1 in ops:
            if i0 == i1:  # pure insertion: re-type a neighbouring word with it so it has a place
                if i0 > 0:
                    i0, j0 = i0 - 1, j0 - 1
                else:
                    i1, j1 = i1 + 1, j1 + 1
            i1, j1 = min(i1, len(old)), min(j1, len(new))
            if spans and i0 <= spans[-1][1]:
                spans[-1] = (spans[-1][0], max(i1, spans[-1][1]), spans[-1][2], max(j1, spans[-1][3]))
            else:
                spans.append((i0, i1, j0, j1))

    # Font read from the scanned words themselves, before anything is erased
    # White print in a coloured bar is handled as its negative: everything below assumes ink
    # darker than the paper
    inverted = _light_on_dark(page, line_rect)
    guess = _guess_scan_font(page, words, baseline, invert=inverted)
    if guess and not any(ch.isalpha() for _, t in words for ch in t):
        # Digits alone barely tell typefaces apart: read the font off the nearest line with
        # letters in the same column ("TUTAR" above "2.885,50") and only measure the size here
        h = max(w.height for w, _ in words)
        near = [l for l in (scan_ocr.ocr_page(page) or [])
                if any(ch.isalpha() for ch in l['text'])
                and min(l['bbox'][2], line_rect.x1) > max(l['bbox'][0], line_rect.x0)
                and abs(l['bbox'][1] - line_rect.y0) < h * 5 and abs(l['bbox'][3] - l['bbox'][1] - h) < h * 0.4]
        if near:
            ln = min(near, key=lambda l: abs(l['bbox'][1] - line_rect.y0))
            other = _guess_scan_font(page, [(fitz.Rect(r), t) for r, t in ln['words']], ln['baseline'], invert=inverted)
            if other:
                guess = _guess_scan_font(page, words, baseline, only=(other[0],), invert=inverted) or guess
    if guess:
        ff, fn, size, baseline = guess
        try:
            seen_base = _ink_baseline(page, line_rect, inverted)
        except Exception:
            seen_base = None
        if seen_base is not None and abs(seen_base - baseline) > size * 0.12:
            baseline = seen_base
        look_spec, look_size = {'fontfile': ff, 'fontname': fn}, size   # the scan's own style
        if flags != orig_flags:  # the user switched bold on/off
            base = next((k for k, v in _SCAN_FONTS.items() if fn + '.ttf' in v), 'arial')
            alt = 'C:/Windows/Fonts/' + _SCAN_FONTS[base][1 if flags & 16 else 0]
            if os.path.exists(alt):
                ff, fn = alt, os.path.splitext(os.path.basename(alt))[0]
        spec = {'fontfile': ff, 'fontname': fn}
        size = max(size * sz / (orig_size or sz), 4.0)
    else:
        spec, factor = _match_font(page, '', flags, ' '.join(old), line_rect.width, orig_size,
                                   new_text, keep_style=not style_changed, rect=line_rect, baseline=baseline)
        size = max(sz * factor, 4.0)
        look_spec, look_size = spec, size
    try:
        color = _scan_tone(page, words, spec, size, baseline, tuple(color))
    except Exception:
        pass
    target = _scan_target(page)
    if not target:  # no sliding without the picture's own pixels: one span, as before
        spans = [(spans[0][0], spans[-1][1], spans[0][2], spans[-1][3])]
    h = max(w.height for w, _ in words)
    pad = fitz.Rect(-min(1.0, h * 0.12), -h * 0.18, min(1.0, h * 0.12), h * 0.12)

    def padded(r):
        return fitz.Rect(r.x0 + pad.x0, r.y0 + pad.y0, r.x1 + pad.x1, r.y1 + pad.y1)

    push_history()
    # With the picture's own pixels at hand every change is made in them, in one go: erase, slide,
    # and the new words typed in with the look measured on the scan's own words
    sp, look = (_ScanPixels(page, *target) if target else None), None
    band = None
    if sp is not None and inverted:
        # The line's strip of the picture, turned into its negative while it is edited
        lh = line_rect.height
        band = sp.box(fitz.Rect(page.rect.x0, line_rect.y0 - lh, page.rect.x1, line_rect.y1 + lh))
        sp.arr[band[1]:band[3], band[0]:band[2]] = 255 - sp.arr[band[1]:band[3], band[0]:band[2]]
    if sp is not None:
        try:
            look = sp.measure_look(look_spec, look_size, words, baseline)
        except Exception:
            look = None
    drawn = look[0][0] if look else 1.0   # the size factor the words will be drawn with
    drawn_dx = look[0][3] / sp.sx if look else 0.0   # and how far right of the OCR box they start
    off = 0.0   # how far the changes so far slid the rest of the line
    for a0, a1, b0, b1 in spans:
        W = [(r + (off, 0, off, 0), t) for r, t in words]

        def region(i, j):
            r = fitz.Rect(W[i][0])
            for w, _ in W[i + 1:j]:
                r |= w
            return r

        def clamp(r, i, j):
            # The erase follows the measured line, not the OCR boxes (which can reach into the
            # lines above and below): from a little over the capitals to under the descenders,
            # and sideways up to, never into, the neighbouring words
            if not guess:
                return r
            left = max(W[i - 1][0].x1 + 0.5, r.x0 - size * 0.3) if i > 0 else r.x0 - size * 0.4
            # At the end of the line nothing is near: OCR's last box often stops short of the ink
            right = min(W[j][0].x0 - 0.5, r.x1 + size * 0.3) if j < len(W) else r.x1 + size * 0.8
            top = max(baseline - size * 1.25, min(r.y0, baseline - size * 1.0))
            return fitz.Rect(left, top, right, baseline + size * 0.22)

        text = ' '.join(new[b0:b1])
        erase = region(a0, a1)
        # The unchanged rest of the line slides (as the scanned ink it is) so it keeps its usual
        # distance from the new text: no gap after a shorter word, no overlap after a longer one
        shift, rest, whole_rest = 0.0, None, False
        if a1 < len(W) and target:
            rest = clamp(padded(region(a1, len(W))), a1, len(W))
            if text:
                shift = W[a0][0].x0 + drawn_dx + _text_width(spec, text, size * drawn) - W[a1 - 1][0].x1
            else:
                shift = W[a0][0].x0 - W[a1][0].x0
            if abs(shift) < 0.5 or rest.x1 + shift > page.rect.x1 - 2:
                shift = 0.0 if abs(shift) < 0.5 else None
        if shift is None or (rest is None and a1 < len(W)):
            room = W[a1][0].x0 - erase.x0 - size * 0.3
            if _text_width(spec, text, size) > room:
                # Longer text would run into the next unchanged word: re-type the rest of the line too
                a1, b1, whole_rest = len(W), len(new), True
                erase = region(a0, a1)
                text = ' '.join(new[b0:b1])
            shift = 0.0
        if sp is not None:
            erase = clamp(padded(erase), a0, a1)
            sp.erase(erase)
            _remove_hidden_text(page, erase)
            if shift and rest is not None:
                px, al, (rx0, ry0, _, _) = sp.ink(rest)
                sp.erase(rest)
                sp.paste(px, al, rx0 + round(shift * sp.sx), ry0)
                _remove_hidden_text(page, rest)
                off += shift
            if text and look is not None:
                # User size changes scale the measured look; bold switched on uses the bold face
                (scale, grow, blur, dx, dy, gain), ink = look
                if style_changed and spec != look_spec:
                    grow, gain = max(grow, 0), max(gain, 1.0)
                sp.type_text(spec, size, text, W[a0][0].x0, baseline, (scale, grow, blur, dx, dy, gain), ink)
                # Invisible copy so the new words can still be found and copied
                kw = {'fontsize': size * scale, 'render_mode': 3}
                kw.update(_font_kwargs(page, spec))
                page.insert_text(fitz.Point(W[a0][0].x0 + dx / sp.sx, baseline + dy / sp.sy), text, **kw)
                if underline:
                    ul_y = baseline + size * 0.12
                    page.draw_line(fitz.Point(W[a0][0].x0, ul_y),
                                   fitz.Point(W[a0][0].x0 + _text_width(spec, text, size), ul_y),
                                   color=color, width=max(0.5, size * 0.04))
                text = ''
        else:
            _erase_scan(page, padded(erase), data.get('paper'))
        if text:
            x = W[a0][0].x0
            kw = {'fontsize': size, 'color': color}
            kw.update(_font_kwargs(page, spec))
            page.insert_text(fitz.Point(x, baseline), text, **kw)
            if underline:
                ul_y = baseline + size * 0.12
                page.draw_line(fitz.Point(x, ul_y), fitz.Point(x + _text_width(spec, text, size), ul_y),
                               color=color, width=max(0.5, size * 0.04))
        if whole_rest:
            break
    if sp is not None:
        if band is not None:
            sp.arr[band[1]:band[3], band[0]:band[2]] = 255 - sp.arr[band[1]:band[3], band[0]:band[2]]
        sp.save()


@app.route('/api/redact', methods=['POST'])
def api_redact():
    """Seçili alanı GERÇEKTEN siler: alttaki metin ve görsel içerik PDF'ten kaldırılır.
    (Üstüne beyaz kutu çizmek metni silmez; kopyalanıp okunabilir kalırdı.)"""
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    data  = request.json
    page  = _upright_scan(doc[data['page']])
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
    if data.get('ocr'):
        page = _upright_scan(page)
    pdf_w, pdf_h = page.rect.width, page.rect.height

    old_rect = fitz.Rect(
        data['bx0'] * pdf_w, data['by0'] * pdf_h,
        data['bx1'] * pdf_w, data['by1'] * pdf_h
    )
    new_x  = float(data['new_x'])
    new_bl = float(data['new_baseline_y'])
    text   = data['text']
    if data.get('ocr'):
        # A scanned line moves as the picture it is, with its exact look
        src = fitz.Rect(old_rect.x0 - 1, old_rect.y0 - 1.5, old_rect.x1 + 1, old_rect.y1 + 1)
        dx = new_x - old_rect.x0
        dy = new_bl - float(data.get('baseline_y') or old_rect.y1)
        push_history()
        _move_scan(page, src, dx, dy, data.get('paper'))
        return jsonify({'ok': True})
    size   = float(data.get('size', 12))
    color  = tuple(data.get('color', [0, 0, 0]))
    # Keep the original font when moving (it used to be rewritten in the default font)
    spec, factor = _match_font(page, data.get('font'), int(data.get('flags', 0)), text,
                               old_rect.width, size, text,
                               rect=old_rect, baseline=_get_baseline_y(page, old_rect))

    push_history()
    page.add_redact_annot(old_rect, fill=(1, 1, 1))
    page.apply_redactions(graphics=0)

    kw = {'fontsize': max(size * factor, 5.0), 'color': color}
    kw.update(_font_kwargs(page, spec))
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
        if _limited() and len(doc) + len(src) > DEMO_MAX_PAGES:
            src.close()
            return _demo_block(DEMO_LIMIT_MSG)
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
        path = _default_out(_sfx('range', a=start + 1, b=end + 1))
    if _trial_offer():
        return _demo_block(DEMO_WATERMARK_MSG, watermark=True)
    try:
        new_doc = fitz.open()
        new_doc.insert_pdf(doc, from_page=start, to_page=end)
        if _limited():
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
        path = _default_out(_sfx('edited'))
    if _trial_offer():
        return _demo_block(DEMO_WATERMARK_MSG, watermark=True)
    try:
        if _limited():
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
            initialfile=orig.stem + _sfx('edited') + '.pdf',
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
        doc = _swap_doc(doc, tmp, f.filename)
        _cleanup_tmp(keep=tmp)
        sigs   = detect_signatures(doc)
        fields = detect_form_fields(doc)
        return jsonify({'ok': True, 'pages': len(doc), 'name': f.filename,
                        'signatures': sigs, 'form_fields': fields,
                        'demo_full': _demo_over_limit()})
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
    # Scans: the scanner's invisible OCR layer is replaced by our own OCR of the picture
    ocr_lines = scan_ocr.ocr_page(page) if scan_ocr.is_scan_page(page) else None
    hidden = scan_ocr.invisible_rects(page) if ocr_lines is not None else []
    visible = []
    for b in page.get_text('dict')['blocks']:
        if b.get('type') != 0:
            continue
        for line in b.get('lines', []):
            spans = line.get('spans', [])
            if hidden:
                spans = [s for s in spans if not _mostly_inside(fitz.Rect(s['bbox']), hidden)]
            if not spans:
                continue
            full_text = ''.join(s.get('text', '') for s in spans).strip()
            if not full_text:
                continue
            bbox = fitz.Rect(spans[0]['bbox'])
            for s in spans[1:]:
                bbox |= fitz.Rect(s['bbox'])
            visible.append(fitz.Rect(bbox))
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
    for ln in ocr_lines or []:
        # Words already re-typed as real text are edited as that text, not as picture
        words = [(fitz.Rect(r), t) for r, t in ln['words']]
        keep = [not _mostly_inside(r, visible, 0.4) for r, _ in words]
        run = []
        for (r, t), k in zip(words + [(None, None)], keep + [False]):
            if k:
                run.append((r, t))
                continue
            if run:
                result.append(_ocr_block(ln, run, pdf_w, pdf_h))
                run = []
    return jsonify({'ok': True, 'blocks': result})


def _mostly_inside(rect, rects, share=0.5):
    """True when more than `share` of rect's area lies inside one of rects."""
    area = abs(rect)
    return area > 0 and any(abs(rect & r) > share * area for r in rects)


def _ocr_block(line, words, pdf_w, pdf_h):
    """Text block for an OCR'd line of a scan (words: [(Rect, text)])."""
    bbox = fitz.Rect(words[0][0])
    for r, _ in words[1:]:
        bbox |= r
    return {
        'text': ' '.join(t for _, t in words),
        'x0': bbox.x0 / pdf_w, 'y0': bbox.y0 / pdf_h,
        'x1': bbox.x1 / pdf_w, 'y1': bbox.y1 / pdf_h,
        'size': line['size'], 'span_size': line['size'], 'sys_size': line['size'],
        'baseline_y': line['baseline'],
        'color': list(line['ink']),
        'font': '', 'flags': 0, 'underline': False,
        'ocr': True, 'paper': list(line['paper']),
        'words': [[r.x0, r.y0, r.x1, r.y1, t] for r, t in words],
    }


@app.route('/api/undo', methods=['POST'])
def api_undo():
    if not state['history']:
        return jsonify({'ok': False, 'error': 'Geri alınacak işlem yok'})
    snap = state['history'].pop()
    with open(snap, 'rb') as f:
        buf = f.read()
    _forget(snap)
    if state['doc']:
        state['doc'].close()
    state['doc'] = fitz.open(stream=buf, filetype='pdf')
    return jsonify({'ok': True, 'pages': len(state['doc'])})


@app.route('/api/status')
def api_status():
    if state['doc']:
        return jsonify({'ok': True, 'pages': len(state['doc']), 'name': _doc_name(),
                        'demo_full': _demo_over_limit()})
    return jsonify({'ok': False})



@app.route('/api/export/images')
def api_export_images():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    if _trial_offer():
        return _demo_block(DEMO_WATERMARK_MSG, watermark=True)
    mat = fitz.Matrix(2.0, 2.0)
    stem = _doc_stem()
    src = doc
    if _limited():
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
                zf.writestr(f"{_sfx('page')}_{i + 1:03d}.png", pix.tobytes('png'))
        buf.seek(0)
        return send_file(buf, mimetype='application/zip',
                         as_attachment=True,
                         download_name=f"{stem}{_sfx('pages')}.zip")
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
        parts.append(_page_text(page))
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
        for sub in ('Calibre2', 'Calibre', os.path.join('Calibre Portable', 'Calibre')):
            exe = os.path.join(base, sub, 'ebook-convert.exe')
            if os.path.isfile(exe):
                return exe
    # Installed to a custom folder: ask Windows' list of installed programs
    import winreg
    for root, path in ((winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'),
                       (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'),
                       (winreg.HKEY_CURRENT_USER, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall')):
        try:
            key = winreg.OpenKey(root, path)
        except OSError:
            continue
        with key:
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    with winreg.OpenKey(key, winreg.EnumKey(key, i)) as sub:
                        name = str(winreg.QueryValueEx(sub, 'DisplayName')[0])
                        if 'calibre' not in name.lower():
                            continue
                        loc = str(winreg.QueryValueEx(sub, 'InstallLocation')[0])
                except OSError:
                    continue
                exe = os.path.join(loc, 'ebook-convert.exe')
                if os.path.isfile(exe):
                    return exe
    return shutil.which('ebook-convert')


def _epub_bytes(doc):
    from epub_export import build_epub
    return build_epub(doc, fallback_title=_doc_stem())


@app.route('/api/export/epub')
def api_export_epub():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    if _limited():
        return _demo_block(DEMO_FEATURE_MSG)
    return send_file(io.BytesIO(_epub_bytes(doc)), mimetype='application/epub+zip',
                     as_attachment=True, download_name=f'{_doc_stem()}.epub')


@app.route('/api/export/azw3')
def api_export_azw3():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    if _limited():
        return _demo_block(DEMO_FEATURE_MSG)
    exe = _find_ebook_convert()
    if not exe:
        return jsonify({'ok': False, 'code': 'no_calibre',
                        'error': 'AZW3 için ücretsiz Calibre programı gerekiyor (calibre-ebook.com). '
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
    if _limited():
        return _demo_block(DEMO_FEATURE_MSG)
    path = _default_out('')[:-4] + '.epub'
    n = 2
    while os.path.exists(path):
        path = _default_out('')[:-4] + f' ({n}).epub'
        n += 1
    data = _epub_bytes(doc)
    with open(path, 'wb') as f:
        f.write(data)
    return jsonify({'ok': True, 'path': path, 'size_kb': len(data) // 1024})


@app.route('/api/kindle_usb')
def api_kindle_usb():
    import kindle_usb
    k = kindle_usb.find_kindle()
    return jsonify({'ok': True, 'found': bool(k), 'name': (k or {}).get('name', ''),
                    'kind': (k or {}).get('kind', ''), 'calibre': bool(_find_ebook_convert())})


@app.route('/api/kindle_usb_send', methods=['POST'])
def api_kindle_usb_send():
    """Copies the open document to a USB-connected Kindle: AZW3 when Calibre is installed
    (reflowable), otherwise the PDF itself (Kindle can't open sideloaded EPUB)."""
    import kindle_usb
    import subprocess
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    if _limited():
        return _demo_block(DEMO_FEATURE_MSG)
    k = kindle_usb.find_kindle()
    if not k:
        return jsonify({'ok': False, 'code': 'no_kindle', 'error': 'Bağlı Kindle bulunamadı'})
    exe = _find_ebook_convert()
    stem = re.sub(r'[\\/:*?"<>|]+', '_', _doc_stem())
    with tempfile.TemporaryDirectory() as tmp:
        if exe:
            src, out = os.path.join(tmp, 'book.epub'), os.path.join(tmp, stem + '.azw3')
            with open(src, 'wb') as f:
                f.write(_epub_bytes(doc))
            r = subprocess.run([exe, src, out], capture_output=True, timeout=600,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if r.returncode != 0 or not os.path.isfile(out):
                return jsonify({'ok': False, 'error': 'Calibre dönüştürmesi başarısız oldu.'})
            fmt = 'azw3'
        else:
            out = os.path.join(tmp, stem + '.pdf')
            doc.save(out, garbage=3, deflate=True)
            fmt = 'pdf'
        try:
            name = kindle_usb.copy_to_kindle(k, out)
        except Exception as e:
            return jsonify({'ok': False, 'error': f'Kindle\'a kopyalanamadı: {e}'})
    state['kindle_usb'] = k
    return jsonify({'ok': True, 'name': k['name'], 'kind': k['kind'], 'file': name, 'format': fmt})


@app.route('/api/kindle_usb_eject', methods=['POST'])
def api_kindle_usb_eject():
    import kindle_usb
    k = state.get('kindle_usb') or kindle_usb.find_kindle()
    return jsonify({'ok': bool(k) and kindle_usb.eject(k)})


@app.route('/api/store/price')
def api_store_price():
    """Localized Store price of the full-version add-on (Store build only)."""
    if not is_demo():
        return jsonify({'ok': False})
    info = _iap.full_product()
    return jsonify({'ok': bool(info), 'price': info[1] if info else ''})


@app.route('/api/store/buy', methods=['POST'])
def api_store_buy():
    """Buys the full version through the Microsoft Store. {fallback: true} → use the Gumroad link."""
    global _licensed_cache
    info = _iap.full_product()
    if not info:
        return jsonify({'ok': False, 'fallback': True})
    status = _iap.purchase(info[0])
    if status in (_iap.SUCCEEDED, _iap.ALREADY_PURCHASED):
        _licensed_cache = True
        return jsonify({'ok': True, 'licensed': True})
    if status == _iap.NOT_PURCHASED:
        return jsonify({'ok': False, 'cancelled': True})
    return jsonify({'ok': False, 'error': 'Satın alma tamamlanamadı. İnternet bağlantınızı kontrol edip tekrar deneyin.'})


@app.route('/api/fullscreen', methods=['POST'])
def api_fullscreen():
    """Uygulama penceresini tam ekrana alır / çıkarır ({on: bool})."""
    try:
        import webview
        win = webview.windows[0]
    except Exception:
        return jsonify({'ok': False})
    on = bool((request.json or {}).get('on'))
    if on != state.get('fullscreen', False):
        win.toggle_fullscreen()
        state['fullscreen'] = on
    return jsonify({'ok': True})


@app.route('/api/open_link', methods=['POST'])
def api_open_link():
    links = {
        'kindle_settings': 'https://www.amazon.com/hz/mycd/myx#/home/settings/pdoc',
        'calibre': 'https://calibre-ebook.com/download_windows',
        'buy': BUY_URL,
        # AGPL-3.0: the source of exactly this version, and the license text
        'source': f'{SOURCE_URL}/tree/v{APP_VERSION}',
        'agpl': 'https://www.gnu.org/licenses/agpl-3.0.html',
    }
    url = links.get((request.json or {}).get('key'))
    if not url:
        return jsonify({'ok': False})
    webbrowser.open(url)
    return jsonify({'ok': True})


def _page_text(page):
    """Text of the page; scanned pages are read with OCR instead of the scanner's (often garbage)
    invisible text layer. Lines of one row are joined with a tab."""
    lines = scan_ocr.ocr_page(page) if scan_ocr.is_scan_page(page) else None
    if lines is None:
        return page.get_text()
    rows = []
    for ln in lines:
        b = ln['bbox']
        if rows and abs(rows[-1][0] - b[1]) < (b[3] - b[1]) * 0.5:
            rows[-1][1].append(ln['text'])
        else:
            rows.append([b[1], [ln['text']]])
    return '\n'.join('\t'.join(t) for _, t in rows) + '\n'


def _ocr_rebuild_page(page, out, layout=None):
    """Re-create a scanned page on a new page of out as real text in a look-alike font, with
    its table rules as lines and its logos, stamps and signatures as pictures, so Word gets
    editable text instead of one big photo of the page.

    With layout (a list) nothing is drawn: the page is appended to it as its size, a picture
    of everything but the text, and each text line's place and look (see _scan_docx)."""
    import numpy as np
    import cv2
    lines = scan_ocr.ocr_page(page)
    W, H = page.rect.width, page.rect.height
    if not lines:
        if layout is None:
            out.insert_pdf(page.parent, from_page=page.number, to_page=page.number)
        else:
            pm = page.get_pixmap(matrix=fitz.Matrix(3, 3), colorspace=fitz.csRGB, alpha=False, annots=False)
            a = np.frombuffer(pm.samples, np.uint8).reshape(pm.height, pm.width, 3)
            ok, data = cv2.imencode('.jpg', scan_ocr.whiten(a, 'color')[:, :, ::-1], [cv2.IMWRITE_JPEG_QUALITY, 85])
            layout.append({'w': W, 'h': H, 'bg': data.tobytes(), 'lines': []})
        return
    new = out.new_page(width=W, height=H) if layout is None else None
    # Each line's own look-alike font (letterheads, forms and printer output mix typefaces). A
    # line no font fits is not print OCR could read: handwriting, a logo, a stamp's lettering, or
    # print read as garbage. It stays a picture rather than becoming wrong text.
    heights = sorted(ln['bbox'][3] - ln['bbox'][1] for ln in lines)
    tall = heights[len(heights) // 2] * 1.6
    # A page uses few typefaces: find them on its longest lines with every candidate, then read
    # each line against those only (all candidates for every line made big pages take minutes)
    from collections import Counter
    seen = Counter()
    for ln in sorted(lines, key=lambda l: -len(l['text']))[:8]:
        g = _guess_scan_font(page, [(fitz.Rect(r), t) for r, t in ln['words']], ln['baseline'], samples=2)
        if g and getattr(_guess_scan_font, 'last_fit', 0) >= 0.22:
            seen[next((k for k, v in _SCAN_FONTS.items() if os.path.basename(g[0]) in v), 'arial')] += 1
    only = tuple('C:/Windows/Fonts/' + f for fam, _ in seen.most_common(3) for f in _SCAN_FONTS[fam]) or None
    kept = []
    for ln in lines:
        g = _guess_scan_font(page, [(fitz.Rect(r), t) for r, t in ln['words']], ln['baseline'], samples=2,
                             only=only)
        fit_ = getattr(_guess_scan_font, 'last_fit', 0) if g else 0
        short = sum(ch.isalnum() for ch in ln['text']) <= 3
        # A low fit alone is no reason: a typeface we do not have (a company font) fits badly too.
        # It takes a low fit and a reading that looks wrong to keep a line as a picture
        garbled = scan_ocr._junk(ln['text']) > 0.12
        if g is None or (fit_ < 0.22 and (garbled or short)) or                 (short and (fit_ < 0.3 or ln['bbox'][3] - ln['bbox'][1] > tall)):
            continue
        fam = next((k for k, v in _SCAN_FONTS.items() if os.path.basename(g[0]) in v), 'arial')
        # The baseline from the pixels: OCR boxes reaching into the next line put baselines a
        # few points off, which made neighbouring lines collide
        try:
            seen = _ink_baseline(page, fitz.Rect(ln['bbox']))
        except Exception:
            seen = None
        b = fitz.Rect(ln['bbox'])
        base = seen if seen is not None and b.y0 < seen <= b.y1 + b.height * 0.3 else ln['baseline']
        kept.append(dict(ln, family=fam, baseline=base, ocr_baseline=ln['baseline']))
    # Two lines whose boxes overlapped can both be read onto the same band of ink. The page's
    # usual line pitch puts the lower one (by OCR's order) back where it belongs
    def same_column(a, b2):
        ra, rb = fitz.Rect(a['bbox']), fitz.Rect(b2['bbox'])
        return min(ra.x1, rb.x1) - max(ra.x0, rb.x0) >= min(ra.width, rb.width) * 0.3

    nearest = []
    for a in kept:
        ds = [abs(a['ocr_baseline'] - b2['ocr_baseline']) for b2 in kept
              if b2 is not a and same_column(a, b2) and abs(a['ocr_baseline'] - b2['ocr_baseline']) > 3]
        if ds:
            nearest.append(min(ds))
    usual = float(np.median(nearest)) if nearest else 0     # the distance to the next line
    if usual:
        for a in sorted(kept, key=lambda l: l['ocr_baseline']):
            for b2 in kept:
                if b2 is a or not same_column(a, b2) or b2['ocr_baseline'] <= a['ocr_baseline']:
                    continue
                if abs(a['baseline'] - b2['baseline']) < usual * 0.4 and                         b2['ocr_baseline'] - a['ocr_baseline'] >= usual * 0.4:
                    b2['baseline'] = a['baseline'] + usual
    lines = kept
    z = 3
    pix = page.get_pixmap(matrix=fitz.Matrix(z, z), colorspace=fitz.csRGB, alpha=False, annots=False)
    arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)
    clean = scan_ocr.whiten(arr, 'color')
    ink = clean.min(axis=2) < 170
    core = clean.min(axis=2) < 128   # the stroke cores alone: soft edges would blur the weight

    def px(r, pad=0.0):
        p = (r[3] - r[1]) * pad
        return (max(0, int((r[0] - p) * z)), max(0, int((r[1] - p) * z)),
                min(pix.width, int((r[2] + p) * z) + 1), min(pix.height, int((r[3] + p) * z) + 1))

    # Pen stroke width of each line (twice the distance from the middle of a stroke to its edge):
    # set against the letter size it tells bold from regular. Ink coverage would depend on the
    # letters themselves.
    stroke = []
    for ln in lines:
        x0, y0, x1, y1 = px(ln['bbox'])
        m = core[y0:y1, x0:x1].astype(np.uint8)
        if m.size == 0 or not m.any():
            stroke.append(0.0)
            continue
        dt = cv2.distanceTransform(m, cv2.DIST_L2, 3)
        ridge = (dt >= cv2.dilate(dt, np.ones((3, 3), np.uint8))) & (m > 0)
        stroke.append(2 * float(np.median(dt[ridge])))
    graphics = ink.copy()
    pictures = clean.copy()
    for ln in lines:
        x0, y0, x1, y1 = px(ln['bbox'], 0.15)
        graphics[y0:y1, x0:x1] = False
        # The text becomes real text: take it out of any logo or stamp picture it sits in
        # (soft letter edges too: behind the real text they would show as a faint ghost)
        pictures[y0:y1, x0:x1][clean[y0:y1, x0:x1].min(axis=2) < 235] = 255
    if layout is not None:
        ok, data = cv2.imencode('.jpg', np.ascontiguousarray(pictures[:, :, ::-1]), [cv2.IMWRITE_JPEG_QUALITY, 85])
        page_layout = {'w': W, 'h': H, 'bg': data.tobytes(), 'lines': []}

    # Table rules and separators: long thin runs of ink
    g8 = graphics.astype(np.uint8) * 255
    hor = cv2.morphologyEx(g8, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, pix.width // 25), 1)))
    ver = cv2.morphologyEx(g8, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, pix.height // 40))))
    for m, horizontal in ((hor, True), (ver, False)):
        n, _, stats, _ = cv2.connectedComponentsWithStats(m)
        for x, y, w, h, _a in stats[1:]:
            if new is None:
                break
            if horizontal:
                new.draw_line(fitz.Point(x / z, (y + h / 2) / z), fitz.Point((x + w) / z, (y + h / 2) / z),
                              color=(0, 0, 0), width=max(0.4, h / z))
            else:
                new.draw_line(fitz.Point((x + w / 2) / z, y / z), fitz.Point((x + w / 2) / z, (y + h) / z),
                              color=(0, 0, 0), width=max(0.4, w / z))
    rest = graphics & ~cv2.dilate(hor | ver, np.ones((5, 5), np.uint8)).astype(bool)

    # Whatever ink is left (logos, stamps, signatures, handwriting OCR did not read) as pictures
    blobs = cv2.dilate(rest.astype(np.uint8), np.ones((int(4 * z), int(4 * z)), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(blobs)
    for x, y, w, h, _a in stats[1:]:
        if new is None:
            break
        if w < 6 * z or h < 6 * z or rest[y:y + h, x:x + w].sum() < 30 * z:
            continue
        crop = np.ascontiguousarray(pictures[y:y + h, x:x + w])
        ok, data = cv2.imencode('.png', crop[:, :, ::-1])
        if ok:
            new.insert_image(fitz.Rect(x / z, y / z, (x + w) / z, (y + h) / z), stream=data.tobytes())

    fonts = {}
    for fam, files in _SCAN_FONTS.items():
        reg = 'C:/Windows/Fonts/' + files[0]
        bld = 'C:/Windows/Fonts/' + files[1]
        if os.path.exists(reg):
            fonts[fam] = (reg, bld if os.path.exists(bld) else reg)

    def fit(ln, ff):
        # The line's width in the look-alike font is the better measure of its size: the box
        # height is swollen by accents (Ç, İ, Ğ) and descenders
        size = ln['size']
        if len(ln['text'].strip()) <= 2:
            return size     # one or two characters: their width says little about the size
        f = fitz.Font(fontfile=ff)
        by_width = fitz.Rect(ln['bbox']).width / (f.text_length(ln['text'], fontsize=1) or 1)
        return by_width if 0.55 * size < by_width < 1.6 * size else size

    for ln in lines:
        if ln['family'] not in fonts:
            ln['family'] = next(iter(fonts))
    sizes = [fit(ln, fonts[ln['family']][0]) for ln in lines]
    # A misread line (letters missing, words run together) fits its width with a huge size: no
    # line is set more than 1.6× the page's usual size, which still leaves headings their size
    if sizes:
        usual_size = float(np.median(sizes))
        sizes = [min(sz, usual_size * 1.6) for sz in sizes]
    ratios = [st / max(sz * z, 1) for st, sz in zip(stroke, sizes)]
    # Bold against the other lines in the same typeface: stroke widths differ between faces
    typical = {}
    for fam in {ln['family'] for ln in lines}:
        rs = [r for ln, r in zip(lines, ratios) if ln['family'] == fam and r > 0]
        all_rs = [r for r in ratios if r > 0]
        typical[fam] = float(np.median(rs if len(rs) >= 3 else all_rs or [0]))
    # How far each line is from the nearest line above or below it in the same column: a line
    # of text set taller than that overlaps its neighbour, and Word converters drop one of two
    # overlapping lines (dense contracts lost a line in ten)
    pitch = []
    for i, ln in enumerate(lines):
        b = fitz.Rect(ln['bbox'])
        best = None
        for j, other in enumerate(lines):
            if i == j:
                continue
            o = fitz.Rect(other['bbox'])
            if min(b.x1, o.x1) - max(b.x0, o.x0) < min(b.width, o.width) * 0.3:
                continue
            d = abs(other['baseline'] - ln['baseline'])
            if d > 2 and (best is None or d < best):
                best = d
        pitch.append(best)
    face = {}
    for ln, size, ratio, room in zip(lines, sizes, ratios, pitch):
        b = fitz.Rect(ln['bbox'])
        reg, bld = fonts[ln['family']]
        is_bold = typical[ln['family']] > 0 and ratio > typical[ln['family']] * 1.22
        if is_bold:
            size = fit(ln, bld)
        if room:
            ff = bld if is_bold else reg
            f = face.get(ff) or face.setdefault(ff, fitz.Font(fontfile=ff))
            # Never more than a fifth smaller: a neighbour much closer than that is a misread,
            # not a reason to shrink the text to nothing
            size = max(size * 0.8, min(size, room * 0.97 / max(f.ascender - f.descender, 0.8)))
        size = max(4.0, int(size * 2) / 2)
        ink_c = ln.get('ink') or (0, 0, 0)
        color = (0, 0, 0) if max(ink_c) - min(ink_c) < 0.15 else tuple(ink_c)
        ff = bld if is_bold else reg
        if new is None:
            f = face.get(ff) or face.setdefault(ff, fitz.Font(fontfile=ff))
            page_layout['lines'].append({'text': ln['text'], 'x': b.x0, 'baseline': ln['baseline'], 'size': size,
                                         'bold': is_bold, 'family': ln['family'], 'color': color,
                                         'width': f.text_length(ln['text'], fontsize=size),
                                         'ascender': f.ascender, 'descender': f.descender})
            continue
        name = ('B' if is_bold else 'R') + ln['family']
        new.insert_text(fitz.Point(b.x0, ln['baseline']), ln['text'], fontsize=size, color=color,
                        fontfile=ff, fontname=name)
    if layout is not None:
        layout.append(page_layout)


def _export_source(doc):
    """doc itself, or a copy with its scanned pages rebuilt as text (see _ocr_rebuild_page)."""
    scans = [p.number for p in doc if scan_ocr.is_scan_page(p)] if scan_ocr.available() else []
    if not scans:
        return doc
    out = fitz.open()
    for p in doc:
        if p.number in scans:
            _ocr_rebuild_page(p, out)
        else:
            out.insert_pdf(doc, from_page=p.number, to_page=p.number)
    return out


_WORD_FONTS = {'arial': 'Arial', 'times': 'Times New Roman', 'courier': 'Courier New', 'calibri': 'Calibri',
               'verdana': 'Verdana', 'tahoma': 'Tahoma', 'segoe': 'Segoe UI', 'corbel': 'Corbel',
               'candara': 'Candara', 'gothic': 'Century Gothic'}


def _scan_docx(layout, path):
    """A Word document of scanned pages laid out like the scans: each page the same size, its
    rules, logos, stamps and handwriting a picture behind the text, and each text line in a
    frame at its exact place, in its look-alike font, size, weight and colour. Nothing flows,
    so nothing spills onto another page or gets dropped for overlapping a neighbour, and the
    text stays editable."""
    import docx
    from docx.enum.section import WD_SECTION
    from docx.enum.text import WD_LINE_SPACING
    from docx.oxml import OxmlElement, parse_xml
    from docx.oxml.ns import qn, nsdecls
    from docx.shared import Pt, RGBColor

    d = docx.Document()
    normal = d.styles['Normal']
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(0)
    body = d.element.body
    for p in list(body.iterchildren(qn('w:p'))):
        body.remove(p)

    def twips(v):
        return str(int(round(v * 20)))

    for i, pg in enumerate(layout):
        sec = d.sections[0] if i == 0 else d.add_section(WD_SECTION.NEW_PAGE)
        sec.page_width, sec.page_height = Pt(pg['w']), Pt(pg['h'])
        for side in ('left_margin', 'right_margin', 'top_margin', 'bottom_margin'):
            setattr(sec, side, Pt(0))
        sec.header_distance = sec.footer_distance = Pt(0)
        # The page picture, behind the text and pinned to the page corner
        para = d.add_paragraph()
        para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        para.paragraph_format.line_spacing = Pt(1)
        inline = para.add_run().add_picture(io.BytesIO(pg['bg']), width=Pt(pg['w']), height=Pt(pg['h']))._inline
        anchor = parse_xml(
            f'<wp:anchor {nsdecls("wp", "a", "pic", "r")} distT="0" distB="0" distL="0" distR="0" simplePos="0" '
            f'relativeHeight="0" behindDoc="1" locked="1" layoutInCell="1" allowOverlap="1">'
            f'<wp:simplePos x="0" y="0"/>'
            f'<wp:positionH relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionH>'
            f'<wp:positionV relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionV>'
            f'</wp:anchor>')
        anchor.append(inline.find(qn('wp:extent')))
        anchor.append(parse_xml(f'<wp:effectExtent {nsdecls("wp")} l="0" t="0" r="0" b="0"/>'))
        anchor.append(parse_xml(f'<wp:wrapNone {nsdecls("wp")}/>'))
        for tag in ('wp:docPr', 'wp:cNvGraphicFramePr', 'a:graphic'):
            el = inline.find(qn(tag))
            if el is not None:
                anchor.append(el)
        inline.getparent().replace(inline, anchor)
        for ln in pg['lines']:
            size = ln['size']
            line_h = size * max(ln['ascender'] - ln['descender'], 1.0)
            para = d.add_paragraph()
            fmt = para.paragraph_format
            fmt.line_spacing_rule = WD_LINE_SPACING.EXACTLY
            fmt.line_spacing = Pt(line_h)
            frame = OxmlElement('w:framePr')
            frame.set(qn('w:w'), twips(ln['width'] * 1.15 + 6))
            frame.set(qn('w:h'), twips(line_h))
            frame.set(qn('w:hRule'), 'exact')
            frame.set(qn('w:x'), twips(ln['x']))
            frame.set(qn('w:y'), twips(ln['baseline'] - size * ln['ascender']))
            frame.set(qn('w:hAnchor'), 'page')
            frame.set(qn('w:vAnchor'), 'page')
            frame.set(qn('w:wrap'), 'none')
            para._p.get_or_add_pPr().insert(0, frame)
            run = para.add_run(ln['text'])
            font = run.font
            font.name = _WORD_FONTS.get(ln['family'], 'Arial')
            run._r.get_or_add_rPr().get_or_add_rFonts().set(qn('w:cs'), font.name)
            font.size = Pt(size)
            font.bold = bool(ln['bold'])
            font.color.rgb = RGBColor(*(int(round(c * 255)) for c in ln['color']))
    d.save(path)


@app.route('/api/export/docx')
def api_export_docx():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False, 'error': 'Dosya açık değil'})
    if _limited():
        return _demo_block(DEMO_FEATURE_MSG)
    tmp_pdf = tempfile.mktemp(suffix='.pdf')
    tmp_docx = tempfile.mktemp(suffix='.docx')
    try:
        if scan_ocr.available() and len(doc) and all(scan_ocr.is_scan_page(p) for p in doc):
            # Scans: laid out page by page ourselves (see _scan_docx)
            layout = []
            for p in doc:
                _ocr_rebuild_page(p, None, layout)
            _scan_docx(layout, tmp_docx)
        else:
            try:
                from pdf2docx import Converter
            except ImportError:
                return jsonify({'ok': False, 'error': 'Word dönüştürücü yüklü değil. Kurmak için: pip install pdf2docx'})
            _export_source(doc).save(tmp_pdf, garbage=4, deflate=True)
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


@app.route('/api/scan_info')
def api_scan_info():
    """How many pages of the open document are scans (their text comes from OCR)."""
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    return jsonify({'ok': True, 'scanned': sum(1 for p in doc if scan_ocr.is_scan_page(p)), 'pages': len(doc)})


@app.route('/api/clean_background', methods=['POST'])
def api_clean_background():
    """Whiten the paper of scanned pages (copier grey, yellowed or tinted paper, shading)."""
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    data = request.json or {}
    mode = 'bw' if data.get('mode') == 'bw' else 'color'
    if data.get('scope') == 'all':
        pages = range(len(doc))
    else:
        pages = [min(max(int(data.get('page_idx', 0)), 0), len(doc) - 1)]
    scans = [i for i in pages if scan_ocr.is_scan_page(doc[i])]
    if not scans:
        return jsonify({'ok': False, 'code': 'no_scan'})
    push_history()
    done = [i for i in scans if scan_ocr.clean_background(doc[i], mode)]
    return jsonify({'ok': True, 'pages': done})


@app.route('/api/addblank', methods=['POST'])
def api_addblank():
    doc = state['doc']
    if not doc:
        return jsonify({'ok': False})
    if _limited() and len(doc) >= DEMO_MAX_PAGES:
        return _demo_block(DEMO_LIMIT_MSG)
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
        path = _default_out(_sfx('compressed'))
    if _trial_offer():
        return _demo_block(DEMO_WATERMARK_MSG, watermark=True)
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
            if _limited():
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
    if _limited():
        return _demo_block(DEMO_FEATURE_MSG)
    data = request.json or {}
    user_pw   = data.get('user_pw', '').strip()
    owner_pw  = data.get('owner_pw', '').strip()
    allow_print = data.get('allow_print', True)
    allow_copy  = data.get('allow_copy', False)
    if not user_pw and not owner_pw:
        return jsonify({'ok': False, 'error': 'En az bir şifre girilmeli'})
    out_path = _default_out(_sfx('encrypted'))
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
    if _limited():
        return _demo_block(DEMO_FEATURE_MSG)
    data = request.json or {}
    password = data.get('password', '').strip()
    out_path = _default_out(_sfx('unlocked'))
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
    if _limited():
        return _demo_block(DEMO_FEATURE_MSG)
    try:
        import openpyxl
    except ImportError:
        return jsonify({'ok': False, 'error': 'openpyxl yüklü değil: pip install openpyxl'})
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for i, page in enumerate(doc):
        ws = wb.create_sheet(f'Sayfa {i + 1}')
        if scan_ocr.is_scan_page(page) and scan_ocr.available():
            # Scanned page: one row per printed row, its columns in separate cells
            for row in _page_text(page).splitlines():
                if row.strip():
                    ws.append([c.strip() for c in row.split('\t')])
            continue
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
    if _limited():
        return _demo_block(DEMO_FEATURE_MSG)
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
    if _limited():
        return _demo_block(DEMO_FEATURE_MSG)
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
            zf.writestr(f"{_sfx('page')}_{i + 1:03d}.jpg", pix.tobytes('jpeg'))
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

        state['trial_doc'] = False      # a new document: the trial of the previous one does not carry over
        truncated = _demo_truncate(new_doc)
        push_history()
        new_doc = _swap_doc(new_doc, os.path.splitext(src)[0] + _sfx('converted') + '.pdf', reset_history=False)
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

    # Varsayılan PDF görüntüleyici olarak bir dosyayla açıldıysa okuma modunda başla
    START_URL = f'http://localhost:{PORT}' + ('/?mode=read' if filepath else '')

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
            START_URL,
            width=1280, height=800,
            min_size=(900, 600),
        )
        webview.start(icon=os.path.join(_BASE_DIR, 'static', 'app-icon.ico'))
    else:
        if filepath:
            try:
                doc = _make_writable(fitz.open(filepath))
                state['doc'] = doc
                state['path'] = filepath
                _trial_new_doc()
            except Exception as e:
                print(f'Dosya acilamadi: {e}')

        def start_flask():
            app.run(port=PORT, debug=False, use_reloader=False, threaded=True)

        threading.Thread(target=start_flask, daemon=True).start()
        time.sleep(1.0)

        window = webview.create_window(
            'PDF Editor Pro',
            START_URL,
            width=1280, height=800,
            min_size=(900, 600),
        )
        webview.start(icon=os.path.join(_BASE_DIR, 'static', 'app-icon.ico'))
