"""Prepares the tesseract\\ folder bundled into PDF Editor Pro: tesseract.exe, the DLLs it loads and
the Turkish model. Run before PyInstaller:  python get_tesseract.py

The binaries come from the UB Mannheim build (winget install UB-Mannheim.TesseractOCR); only the
files tesseract.exe actually needs are copied, found by following its DLL imports. The model is
tessdata_fast's tur.traineddata (as accurate as tessdata_best on scans in tests, half the size).
"""
import os
import re
import shutil
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'tesseract')
SRC = os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'), 'Tesseract-OCR')
MODEL_URL = 'https://github.com/tesseract-ocr/tessdata_fast/raw/main/tur.traineddata'


def imports(path):
    """DLL names a PE file refers to (read from its import strings)."""
    data = open(path, 'rb').read()
    return {m.decode().lower() for m in re.findall(rb'([A-Za-z0-9_\-+.]+\.dll)', data)}


def strip_debug(path):
    """Cut the DWARF debug sections (.debug_*) and the COFF symbol table off a MinGW-built PE file,
    as `strip` does: they sit after every loaded section, are never mapped, and make up ~95% of
    libtesseract-5.dll. Returns the bytes saved."""
    import struct
    d = bytearray(open(path, 'rb').read())
    pe = struct.unpack_from('<I', d, 0x3c)[0]
    nsec, = struct.unpack_from('<H', d, pe + 6)
    symptr, nsym = struct.unpack_from('<II', d, pe + 12)
    optsz, = struct.unpack_from('<H', d, pe + 20)
    opt = pe + 24
    if struct.unpack_from('<H', d, opt)[0] != 0x20b:      # PE32+ only (64-bit build)
        return 0
    sec_align, = struct.unpack_from('<I', d, opt + 32)
    table = opt + optsz
    strtab = symptr + nsym * 18 if symptr else 0
    secs = []
    for i in range(nsec):
        o = table + i * 40
        name = bytes(d[o:o + 8]).rstrip(b'\0').decode('latin-1')
        if name.startswith('/') and strtab:
            off = strtab + int(name[1:])
            name = bytes(d[off:d.index(b'\0', off)]).decode('latin-1')
        vsize, va, rawsize, rawptr = struct.unpack_from('<IIII', d, o + 8)
        secs.append((name, vsize, va, rawsize, rawptr))
    keep = [s for s in secs if not s[0].startswith('.debug')]
    gone = [s for s in secs if s[0].startswith('.debug')]
    if not gone or secs[:len(keep)] != keep:
        return 0          # debug sections not all at the end: leave the file alone
    end = max(s[4] + s[3] for s in keep)
    if any(s[4] < end for s in gone if s[3]):
        return 0
    last = max(keep, key=lambda s: s[2])
    size_img = (last[2] + max(last[1], last[3]) + sec_align - 1) // sec_align * sec_align
    struct.pack_into('<H', d, pe + 6, len(keep))
    struct.pack_into('<II', d, pe + 12, 0, 0)            # no COFF symbol table any more
    struct.pack_into('<I', d, opt + 56, size_img)
    struct.pack_into('<I', d, opt + 64, 0)               # checksum: not checked for user DLLs
    for i in range(len(keep), nsec):
        d[table + i * 40:table + i * 40 + 40] = bytes(40)
    saved = len(d) - end
    open(path, 'wb').write(bytes(d[:end]))
    return saved


def main():
    exe = os.path.join(SRC, 'tesseract.exe')
    if not os.path.exists(exe):
        sys.exit(f'{exe} not found: winget install UB-Mannheim.TesseractOCR')
    local = {f.lower(): f for f in os.listdir(SRC) if f.lower().endswith('.dll')}
    need, todo = set(), ['tesseract.exe']
    while todo:
        for d in imports(os.path.join(SRC, todo.pop())):
            if d in local and d not in need:
                need.add(d)
                todo.append(local[d])
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, 'tessdata'))
    shutil.copy2(exe, OUT)
    for d in sorted(need):
        shutil.copy2(os.path.join(SRC, local[d]), OUT)
    for name in ('LICENSE', 'COPYING', 'AUTHORS'):
        if os.path.exists(os.path.join(SRC, name)):
            shutil.copy2(os.path.join(SRC, name), OUT)
    saved = sum(strip_debug(os.path.join(OUT, f)) for f in os.listdir(OUT) if f.lower().endswith(('.dll', '.exe')))
    print(f'debug info removed: {saved / 1e6:.1f} MB')
    model = os.path.join(OUT, 'tessdata', 'tur.traineddata')
    cached = os.path.join(ROOT, 'tessdata', 'tur.traineddata')
    if os.path.exists(cached):
        shutil.copy2(cached, model)
    else:
        urllib.request.urlretrieve(MODEL_URL, model)

    # It must run on its own, without the installed copy on PATH
    env = {'SystemRoot': os.environ['SystemRoot'], 'PATH': os.path.join(os.environ['SystemRoot'], 'System32')}
    p = subprocess.run([os.path.join(OUT, 'tesseract.exe'), '--list-langs', '--tessdata-dir',
                        os.path.join(OUT, 'tessdata')], capture_output=True, text=True, env=env)
    if p.returncode != 0 or 'tur' not in p.stdout:
        sys.exit('tesseract does not run from the copied folder:\n' + p.stdout + p.stderr)
    size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(OUT) for f in fs)
    print(f'tesseract\\: {len(need)} DLLs, {size / 1e6:.1f} MB, runs on its own')


if __name__ == '__main__':
    main()
