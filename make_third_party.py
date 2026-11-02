"""Writes static/THIRD_PARTY_LICENSES.txt: the components bundled into PDF Editor Pro and their licenses.

License texts are read from each installed package's metadata, so run this in the build
environment before PyInstaller:  python make_third_party.py
"""
import importlib.metadata as md
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'static', 'THIRD_PARTY_LICENSES.txt')

# Python packages that end up in the PyInstaller bundle (direct and notable indirect dependencies)
PACKAGES = [
    'PyMuPDF', 'pdf2docx', 'python-docx', 'python-pptx', 'openpyxl', 'docx2pdf', 'fonttools',
    'opencv-python-headless', 'opencv-python', 'numpy', 'Pillow', 'lxml', 'Flask', 'Werkzeug', 'Jinja2',
    'MarkupSafe', 'itsdangerous', 'click', 'blinker', 'pywebview', 'proxy_tools', 'bottle', 'pythonnet',
    'clr_loader', 'cffi', 'pycparser', 'certifi', 'cryptography', 'winrt-runtime',
    'winrt-Windows.Services.Store', 'winrt-Windows.Foundation', 'winrt-Windows.Foundation.Collections',
    'XlsxWriter', 'et_xmlfile', 'fire', 'termcolor', 'tqdm', 'typing_extensions',
]

OTHER = [
    ('DejaVu fonts (static/fonts)', 'Bitstream Vera Fonts License / public domain (DejaVu changes)',
     open(os.path.join(ROOT, 'static', 'fonts', 'LICENSE_DEJAVU'), encoding='utf-8').read()),
    ('Lucide icons (user interface icons)', 'ISC License',
     'Copyright (c) Lucide Icons and Contributors\n\nPermission to use, copy, modify, and/or distribute this software '
     'for any purpose with or without fee is hereby granted, provided that the above copyright notice and this '
     'permission notice appear in all copies.\n\nTHE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL '
     'WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO '
     'EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES '
     'WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER '
     'TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.'),
    (f'Python {sys.version.split()[0]} runtime', 'Python Software Foundation License',
     'Copyright (c) 2001 Python Software Foundation. All rights reserved.\nFull text: https://docs.python.org/3/license.html'),
    ('PyInstaller bootloader', 'GPL-2.0 with the PyInstaller bootloader exception',
     'The bootloader may be used to run programs under any license. https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt'),
]

LICENSE_FILE_HINTS = ('license', 'licence', 'copying', 'notice', 'authors')


def license_of(meta):
    lic = meta.get('License-Expression') or ''
    if not lic:
        raw = (meta.get('License') or '').strip()
        lic = raw.splitlines()[0] if raw and len(raw) < 200 else ''
    if not lic:
        cls = [c.split('::')[-1].strip() for c in meta.get_all('Classifier') or [] if c.startswith('License')]
        lic = '; '.join(cls)
    return lic or 'see license text'


def license_texts(dist):
    texts = []
    for f in dist.files or []:
        name = os.path.basename(str(f)).lower()
        if any(h in name for h in LICENSE_FILE_HINTS) and not name.endswith(('.py', '.pyc', '.pyi', '.html')):
            try:
                with open(f.locate(), encoding='utf-8', errors='replace') as fh:
                    t = fh.read().strip()
            except Exception:
                continue
            if t and t not in texts:
                texts.append(t)
    return texts


def main():
    out = ['PDF Editor Pro — third-party components', '=' * 40, '',
           'PDF Editor Pro is free software licensed under the GNU Affero General Public License v3.0',
           '(see LICENSE). Source code: https://github.com/mkb-fcb/pdf-editor-pro',
           'It includes the following third-party components, each under its own license.', '']
    missing = []
    for p in PACKAGES:
        try:
            dist = md.distribution(p)
        except md.PackageNotFoundError:
            missing.append(p)
            continue
        meta = dist.metadata
        out += ['-' * 78, f"{meta['Name']} {dist.version}", f"License: {license_of(meta)}"]
        home = meta.get('Home-page') or next((u.split(',', 1)[-1].strip() for u in meta.get_all('Project-URL') or []), '')
        if home:
            out.append(f'Project: {home}')
        out.append('')
        out += license_texts(dist) or ['(No license file shipped in the package metadata; see the project page.)']
        out.append('')
    for name, lic, text in OTHER:
        out += ['-' * 78, name, f'License: {lic}', '', text, '']
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(out))
    print(f'{OUT}: {len(PACKAGES) - len(missing)} packages' + (f' (not installed: {", ".join(missing)})' if missing else ''))


if __name__ == '__main__':
    main()
