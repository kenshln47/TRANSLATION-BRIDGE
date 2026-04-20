"""
Translation Bridge — Native Windows Hotkey System
Uses RegisterHotKey via user32 — zero CPU, zero FPS drops.
No dependency on the 'keyboard' package.
"""

import ctypes
import ctypes.wintypes
import logging
import threading

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32

# Modifier constants
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

# Virtual key codes for OEM keys
_OEM_MAP = {
    ' ': 0x20, ';': 0xBA, '=': 0xBB, ',': 0xBC, '-': 0xBD,
    '.': 0xBE, '/': 0xBF, '`': 0xC0, '[': 0xDB, '\\': 0xDC,
    ']': 0xDD, "'": 0xDE,
}


def parse_hotkey(hk: str) -> tuple[int, int]:
    """Parse a hotkey string like 'ctrl+shift+t' into (modifiers, vk_code)."""
    parts = hk.lower().split('+')
    mods = 0
    vk = 0
    for p in parts:
        p = p.strip()
        if p == 'ctrl':
            mods |= MOD_CONTROL
        elif p in ('shift', 'left shift', 'right shift'):
            mods |= MOD_SHIFT
        elif p in ('alt', 'left alt', 'right alt'):
            mods |= MOD_ALT
        elif p == 'windows':
            mods |= MOD_WIN
        elif len(p) == 1 and p.isalpha():
            vk = ord(p.upper())
        elif p.isdigit():
            vk = ord(p)
        elif p in _OEM_MAP:
            vk = _OEM_MAP[p]
        elif p.startswith('f') and p[1:].isdigit():
            vk = 0x6F + int(p[1:])
    return mods, vk


class NativeHotkey:
    """Manages a global hotkey via Windows RegisterHotKey API."""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._thread_id: int = 0
        self._callback = None

    def register(self, hotkey_str: str, callback):
        """Register a global hotkey. callback() is called from a background thread."""
        self._callback = callback
        self._thread = threading.Thread(
            target=self._message_loop, args=(hotkey_str,), daemon=True
        )
        self._thread.start()
        logger.info(f"Hotkey registered: {hotkey_str.upper()}")

    def unregister(self):
        """Unregister the hotkey by posting WM_QUIT to the message loop thread."""
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)  # WM_QUIT
            logger.info("Hotkey unregistered.")
            self._thread_id = 0

    def _message_loop(self, hk_str: str):
        """Blocking message loop that listens for the registered hotkey."""
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        mods, vk = parse_hotkey(hk_str)

        if not vk:
            logger.error(f"Failed to parse hotkey '{hk_str}': no valid key found.")
            return

        if not user32.RegisterHotKey(None, 1, mods, vk):
            logger.error(f"RegisterHotKey failed for '{hk_str}' (key may be in use).")
            return

        msg = ctypes.wintypes.MSG()
        while True:
            bRet = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if bRet <= 0:
                break
            if msg.message == 0x0312:  # WM_HOTKEY
                if self._callback:
                    self._callback()
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        user32.UnregisterHotKey(None, 1)


# ─────────────────────────────────────────────────────────────
# NATIVE HOTKEY RECORDER (replaces 'keyboard' package)
# ─────────────────────────────────────────────────────────────

# Virtual-key to readable name
_VK_NAMES = {
    0x08: 'backspace', 0x09: 'tab', 0x0D: 'enter', 0x1B: 'escape', 0x20: 'space',
    0x21: 'pageup', 0x22: 'pagedown', 0x23: 'end', 0x24: 'home',
    0x25: 'left', 0x26: 'up', 0x27: 'right', 0x28: 'down',
    0x2D: 'insert', 0x2E: 'delete',
    0xBA: ';', 0xBB: '=', 0xBC: ',', 0xBD: '-', 0xBE: '.', 0xBF: '/',
    0xC0: '`', 0xDB: '[', 0xDC: '\\', 0xDD: ']', 0xDE: "'",
}
# Add F1-F24
for _i in range(1, 25):
    _VK_NAMES[0x6F + _i] = f'f{_i}'
# Add 0-9
for _i in range(10):
    _VK_NAMES[0x30 + _i] = str(_i)
# Add A-Z
for _i in range(26):
    _VK_NAMES[0x41 + _i] = chr(0x41 + _i).lower()


def record_hotkey_native(timeout: float = 10.0) -> str | None:
    """
    Record a hotkey combination natively using GetAsyncKeyState.
    Waits for the user to press modifier(s) + a key, then returns a string like 'ctrl+shift+t'.
    Returns None on timeout.
    
    This replaces the 'keyboard' package's read_hotkey() function.
    """
    import time

    start = time.time()
    last_combo = None

    while time.time() - start < timeout:
        mods = []
        key = None

        # Check modifiers
        if user32.GetAsyncKeyState(0x11) & 0x8000:  # VK_CONTROL
            mods.append('ctrl')
        if user32.GetAsyncKeyState(0x10) & 0x8000:  # VK_SHIFT
            mods.append('shift')
        if user32.GetAsyncKeyState(0x12) & 0x8000:  # VK_MENU (Alt)
            mods.append('alt')
        if user32.GetAsyncKeyState(0x5B) & 0x8000 or user32.GetAsyncKeyState(0x5C) & 0x8000:
            mods.append('windows')

        # Check regular keys (skip modifier-only VKs)
        skip_vks = {0x10, 0x11, 0x12, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C}
        for vk, name in _VK_NAMES.items():
            if vk in skip_vks:
                continue
            if user32.GetAsyncKeyState(vk) & 0x8000:
                key = name
                break

        if mods and key:
            last_combo = '+'.join(mods + [key])

        # If we had a combo and all keys are now released, we're done
        if last_combo and not mods and not key:
            logger.info(f"Recorded hotkey: {last_combo}")
            return last_combo

        time.sleep(0.02)  # ~50Hz polling (low CPU)

    logger.warning("Hotkey recording timed out.")
    return None
