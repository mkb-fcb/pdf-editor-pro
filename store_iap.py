"""Microsoft Store in-app purchase of the full version (a durable add-on).

The add-on is created in Partner Center with the product ID FULL_TOKEN; the Store reports that
ID as the add-on's in-app offer token. Everything here is best effort: outside the Store package,
or when the add-on cannot be found, callers fall back to the Gumroad license key flow.
"""
import asyncio
import ctypes
import os
import sys
import threading

FULL_TOKEN = 'pdfeditorpro_full'
IS_STORE_PACKAGE = 'windowsapps' in sys.executable.lower()

# Windows.Services.Store.StorePurchaseStatus
SUCCEEDED, ALREADY_PURCHASED, NOT_PURCHASED, NETWORK_ERROR, SERVER_ERROR = range(5)


def _run(coro_fn, timeout):
    """Runs an async WinRT call on its own thread and event loop; None on error or timeout."""
    box = {}

    def worker():
        try:
            box['v'] = asyncio.run(coro_fn())
        except Exception as e:
            box['e'] = e

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout)
    return box.get('v')


def _values(m):
    try:
        return list(m.values())
    except Exception:
        return [kv.value for kv in m]


def _context():
    from winrt.windows.services.store import StoreContext
    return StoreContext.get_default()


def owns_full() -> bool:
    """True if the current Windows user bought the full-version add-on."""
    if not IS_STORE_PACKAGE:
        return False

    async def check():
        lic = await _context().get_app_license_async()
        return any(l.in_app_offer_token == FULL_TOKEN and l.is_active
                   for l in _values(lic.add_on_licenses))

    return bool(_run(check, 8))


def full_product():
    """(store_id, formatted_price) of the full-version add-on, or None."""
    if not IS_STORE_PACKAGE:
        return None

    async def find():
        res = await _context().get_associated_store_products_async(['Durable'])
        for p in _values(res.products):
            if p.in_app_offer_token == FULL_TOKEN:
                return p.store_id, p.price.formatted_price
        return None

    return _run(find, 15)


def _app_window():
    """Handle of this process's main window, which owns the Store purchase dialog."""
    user32 = ctypes.windll.user32
    pid = ctypes.c_ulong()
    hwnd = user32.GetForegroundWindow()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if hwnd and pid.value == os.getpid():
        return hwnd
    return user32.FindWindowW(None, 'PDF Editor Pro') or hwnd


def purchase(store_id: str):
    """Shows the Store purchase dialog. Returns a StorePurchaseStatus value, or None on failure."""
    async def buy():
        import winrt._winrt as rt
        ctx = _context()
        rt.initialize_with_window(ctx, _app_window())   # desktop apps must give the dialog an owner
        res = await ctx.request_purchase_async(store_id)
        return int(res.status)

    return _run(buy, 600)
