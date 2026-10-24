"""Find a Kindle connected over USB and copy a book onto it.

Most Kindles show up as a drive ("Kindle (E:)") with documents/ and system/
folders. Some newer models only appear as an MTP portable device without a
drive letter; those are reached through the Windows Shell (Explorer) API via
PowerShell, which needs no extra libraries.
"""
import ctypes
import os
import string
import subprocess

_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def _volume_label(root):
    buf = ctypes.create_unicode_buffer(261)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(ctypes.c_wchar_p(root), buf, 261, None, None, None, None, 0)
    return buf.value if ok else ''


def _find_drive():
    get_type = ctypes.windll.kernel32.GetDriveTypeW
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    for i, letter in enumerate(string.ascii_uppercase):
        if not mask & (1 << i) or letter in 'AB':
            continue
        root = f'{letter}:\\'
        if get_type(ctypes.c_wchar_p(root)) not in (2, 3):  # removable or fixed
            continue
        try:
            if not (os.path.isdir(os.path.join(root, 'documents')) and os.path.isdir(os.path.join(root, 'system'))):
                continue
        except OSError:
            continue
        label = _volume_label(root)
        if 'kindle' in label.lower() or os.path.isfile(os.path.join(root, 'system', 'version.txt')):
            return {'kind': 'drive', 'root': root, 'name': f'{label or "Kindle"} ({letter}:)'}
    return None


_PS_FIND_DOCS = r'''
$ErrorActionPreference = 'Stop'
$sh = New-Object -ComObject Shell.Application
$dev = $sh.Namespace(17).Items() | Where-Object { $_.Name -like '*Kindle*' } | Select-Object -First 1
if (-not $dev) { exit 3 }
$docs = $null
foreach ($st in $dev.GetFolder.Items()) {
  if ($st.IsFolder) {
    $d = $st.GetFolder.Items() | Where-Object { $_.Name -eq 'documents' } | Select-Object -First 1
    if ($d) { $docs = $d; break }
  }
}
if (-not $docs) { exit 4 }
'''


def _ps(script, env=None, timeout=30):
    e = dict(os.environ, **(env or {}))
    return subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                           '-Command', script], capture_output=True, text=True, timeout=timeout,
                          env=e, creationflags=_NO_WINDOW)


def _find_mtp():
    try:
        r = _ps(_PS_FIND_DOCS + "Write-Output $dev.Name", timeout=20)
    except Exception:
        return None
    if r.returncode == 0 and r.stdout.strip():
        return {'kind': 'mtp', 'name': r.stdout.strip().splitlines()[-1]}
    return None


def find_kindle():
    """{'kind': 'drive'|'mtp', 'name': ..., 'root'?: ...} or None."""
    return _find_drive() or _find_mtp()


def _unique(folder, filename):
    stem, ext = os.path.splitext(filename)
    cand, n = os.path.join(folder, filename), 2
    while os.path.exists(cand):
        cand = os.path.join(folder, f'{stem} ({n}){ext}')
        n += 1
    return cand


def copy_to_kindle(kindle, src):
    """Copies src into the Kindle's documents folder. Returns the name it got there."""
    name = os.path.basename(src)
    if kindle['kind'] == 'drive':
        dst = _unique(os.path.join(kindle['root'], 'documents'), name)
        with open(src, 'rb') as fi, open(dst, 'wb') as fo:
            while True:
                chunk = fi.read(1 << 20)
                if not chunk:
                    break
                fo.write(chunk)
            fo.flush()
            os.fsync(fo.fileno())
        return os.path.basename(dst)
    # MTP: Explorer's CopyHere is asynchronous, so wait until the file shows up on the device
    script = _PS_FIND_DOCS + r'''
$name = [IO.Path]::GetFileName($env:KINDLE_SRC)
$bare = [IO.Path]::GetFileNameWithoutExtension($env:KINDLE_SRC)
$docs.GetFolder.CopyHere($env:KINDLE_SRC, 16)
for ($i = 0; $i -lt 240; $i++) {
  Start-Sleep -Milliseconds 500
  if ($docs.GetFolder.Items() | Where-Object { $_.Name -eq $name -or $_.Name -eq $bare }) { Write-Output 'OK'; exit 0 }
}
exit 5
'''
    r = _ps(script, env={'KINDLE_SRC': src}, timeout=150)
    if r.returncode != 0 or 'OK' not in r.stdout:
        raise RuntimeError('Kindle cihazına kopyalanamadı')
    return name


def eject(kindle):
    """Safely removes a Kindle drive (same as Explorer's Eject)."""
    if kindle.get('kind') != 'drive':
        return False
    r = _ps(r"(New-Object -ComObject Shell.Application).Namespace(17).ParseName($env:KINDLE_ROOT).InvokeVerb('Eject')",
            env={'KINDLE_ROOT': kindle['root'].rstrip('\\')}, timeout=20)
    return r.returncode == 0
