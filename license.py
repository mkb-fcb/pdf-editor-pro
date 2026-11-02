"""License validation for PDF Editör Pro."""
import hashlib
import json
import os
import platform
import subprocess
import time
import urllib.request

WORKER_URL = "https://license.mkbsoft.net"
LICENSE_FILE = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'PDFEditorPro', 'license.json')
VERIFY_EVERY_DAYS = 7
GRACE_DAYS = 30  # Sunucuya ulaşılamazsa bu kadar gün offline çalışır


def get_machine_id() -> str:
    parts = []
    try:
        r = subprocess.run(['wmic', 'csproduct', 'get', 'UUID'],
                           capture_output=True, text=True, timeout=5)
        lines = [l.strip() for l in r.stdout.strip().splitlines() if l.strip()]
        if len(lines) > 1:
            parts.append(lines[-1])
    except Exception:
        pass
    try:
        import uuid
        parts.append(hex(uuid.getnode()))
    except Exception:
        pass
    parts.append(platform.node())
    return hashlib.sha256('|'.join(parts).encode()).hexdigest()[:32]


def _load() -> dict | None:
    try:
        with open(LICENSE_FILE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _save(data: dict):
    os.makedirs(os.path.dirname(LICENSE_FILE), exist_ok=True)
    with open(LICENSE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f)


def _post(path: str, body: dict) -> dict:
    import ssl
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f'{WORKER_URL}{path}', data=data,
        headers={'Content-Type': 'application/json', 'User-Agent': 'PDFEditorPro/1.0'},
        method='POST')
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
        return json.loads(r.read())


def activate(license_key: str) -> tuple[bool, str]:
    """Activate license key on this machine. Returns (success, message)."""
    machine_id = get_machine_id()
    try:
        result = _post('/activate', {'license_key': license_key, 'machine_id': machine_id})
        if result.get('ok'):
            _save({
                'key': license_key,
                'machine_id': machine_id,
                'token': result['token'],
                'plan': result.get('plan', 'individual'),
                'verified_at': time.time(),
            })
            return True, result.get('message', 'Aktivasyon başarılı')
        return False, result.get('error', 'Aktivasyon başarısız')
    except Exception as e:
        return False, f'Sunucuya ulaşılamadı: {e}'


def is_licensed() -> bool:
    """Check if this machine has a valid license. Uses cached result + periodic server check."""
    lic = _load()
    if not lic:
        return False

    now = time.time()
    last_verified = lic.get('verified_at', 0)

    # Within weekly check interval → trust local cache
    if now - last_verified < VERIFY_EVERY_DAYS * 86400:
        return True

    # Re-verify with server
    try:
        result = _post('/verify', {
            'license_key': lic['key'],
            'machine_id': lic['machine_id'],
            'token': lic['token'],
        })
        if result.get('ok'):
            lic['verified_at'] = now
            _save(lic)
            return True
        # Server says invalid → revoked
        return False
    except Exception:
        # Network error → grace period
        if now - last_verified < GRACE_DAYS * 86400:
            return True
        return False


def get_plan() -> str:
    lic = _load()
    return (lic or {}).get('plan', 'individual')
