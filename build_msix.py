"""Builds the Microsoft Store MSIX package from dist\\PDFEditor.

Usage:  python build_msix.py 1.0.1 [path\\to\\makeappx.exe]

Run PyInstaller (pdf_editor.spec) first. The Store signs the package itself,
so the output is uploaded to Partner Center unsigned.
"""
import glob
import os
import shutil
import subprocess
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, 'dist', 'PDFEditor')
STAGE = os.path.join(ROOT, 'build', 'msix_stage')
OUT_DIR = os.path.join(ROOT, 'installer_output')
LOGO_SRC = os.path.join(ROOT, 'images', 'store_logo_1080x1080.png')

# name -> (width, height)
LOGOS = {
    'StoreLogo.png': (50, 50),
    'Square44x44Logo.png': (44, 44),
    'Square150x150Logo.png': (150, 150),
    'Wide310x150Logo.png': (310, 150),
}


def find_makeappx():
    if len(sys.argv) > 2:
        return sys.argv[2]
    found = shutil.which('makeappx')
    if found:
        return found
    kits = glob.glob(r'C:\Program Files (x86)\Windows Kits\10\bin\*\x64\makeappx.exe')
    if kits:
        return sorted(kits)[-1]
    sys.exit('makeappx.exe not found: install the Windows SDK or pass its path as the 2nd argument')


SCALES = [100, 125, 150, 200, 400]
# Taskbar, desktop shortcut, Start list, Alt+Tab and Explorer ask for these exact sizes
TARGET_SIZES = [16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 256]


def _detailed(src, w, h):
    """The full Store logo, centred — only used where it is shown large (tiles)."""
    side = min(w, h)
    icon = src.resize((side, side), Image.LANCZOS)
    canvas = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    canvas.paste(icon, ((w - side) // 2, (h - side) // 2), icon)
    return canvas


def make_logos(assets):
    """Writes scale-/targetsize-qualified logos. The detailed Store logo turns into a
    blur below ~64 px, so small sizes use the simplified icon from make_icon.py."""
    from make_icon import make_icon

    src = Image.open(LOGO_SRC).convert('RGBA')
    for name, (w, h) in LOGOS.items():
        base = name[:-4]
        for sc in SCALES:
            sw, sh = round(w * sc / 100), round(h * sc / 100)
            if base == 'Square44x44Logo' or base == 'StoreLogo':
                img = make_icon(sw)
            else:
                img = _detailed(src, sw, sh)
            img.save(os.path.join(assets, f'{base}.scale-{sc}.png'))

    for ts in TARGET_SIZES:
        img = make_icon(ts)
        for suffix in ('', '_altform-unplated', '_altform-lightunplated'):
            img.save(os.path.join(assets, f'Square44x44Logo.targetsize-{ts}{suffix}.png'))


def make_pri(makeappx, manifest_path, assets):
    """resources.pri lets Windows pick the qualified logo variants. Indexed from a
    small folder holding only the manifest + Assets, not the whole app."""
    makepri = os.path.join(os.path.dirname(makeappx), 'makepri.exe')
    if not os.path.isfile(makepri):
        sys.exit(f'makepri.exe not found next to {makeappx}')
    pri_root = os.path.join(ROOT, 'build', 'msix_pri')
    shutil.rmtree(pri_root, ignore_errors=True)
    shutil.copytree(assets, os.path.join(pri_root, 'Assets'))
    shutil.copy(manifest_path, os.path.join(pri_root, 'AppxManifest.xml'))
    cfg = os.path.join(pri_root, 'priconfig.xml')
    subprocess.run([makepri, 'createconfig', '/cf', cfg, '/dq', 'en-US', '/pv', '10.0.0', '/o'],
                   check=True, stdout=subprocess.DEVNULL)
    out = os.path.join(pri_root, 'resources.pri')
    subprocess.run([makepri, 'new', '/pr', pri_root, '/cf', cfg,
                    '/mn', os.path.join(pri_root, 'AppxManifest.xml'), '/of', out, '/o'],
                   check=True, stdout=subprocess.DEVNULL)
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    version = sys.argv[1]
    # Store requires 4-part versions with the last part 0
    parts = (version.split('.') + ['0', '0', '0'])[:3] + ['0']
    msix_version = '.'.join(parts)

    if not os.path.isfile(os.path.join(DIST, 'PDFEditor.exe')):
        sys.exit('dist\\PDFEditor\\PDFEditor.exe not found: run PyInstaller first')

    shutil.rmtree(STAGE, ignore_errors=True)
    # python-docx ships an unused source template containing [Content_Types].xml,
    # a file name reserved by MSIX; it reads default.docx at runtime instead
    shutil.copytree(DIST, STAGE, ignore=shutil.ignore_patterns('default-docx-template'))
    assets = os.path.join(STAGE, 'Assets')
    os.makedirs(assets, exist_ok=True)
    make_logos(assets)

    with open(os.path.join(ROOT, 'msix', 'AppxManifest.xml'), encoding='utf-8') as f:
        manifest = f.read().replace('{VERSION}', msix_version)
    manifest_path = os.path.join(STAGE, 'AppxManifest.xml')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write(manifest)

    makeappx = find_makeappx()
    shutil.copy(make_pri(makeappx, manifest_path, assets), os.path.join(STAGE, 'resources.pri'))

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f'PDFEditorPro_Store_v{version}.msix')
    subprocess.run([makeappx, 'pack', '/d', STAGE, '/p', out, '/o'], check=True)
    print('MSIX ready:', out)


if __name__ == '__main__':
    main()
