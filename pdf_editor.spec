# -*- mode: python ; coding: utf-8 -*-
import certifi

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        (certifi.where(), 'certifi'),
    ],
    hiddenimports=[
        'epub_export',
        'kindle_usb',
        'flask',
        'werkzeug',
        'werkzeug.serving',
        'werkzeug.debug',
        'jinja2',
        'click',
        'pymupdf',
        'pymupdf.mupdf',
        'tkinter',
        'tkinter.filedialog',
        'pdf2docx',
        'docx',
        'cv2',
        'fontTools',
        'numpy',
        'certifi',
        'webview',
        'webview.platforms.winforms',
        'clr',
        'System',
        'System.Windows.Forms',
        'pptx',
        'pptx.util',
        'pptx.enum.text',
        'docx2pdf',
        'openpyxl',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'pandas', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PDFEditor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='PDFEditor',
)
