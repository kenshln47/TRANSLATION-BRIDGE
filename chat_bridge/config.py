"""
Translation Bridge — Configuration & API Key Manager
"""

import json
import logging
import os
import shutil
import sys
import tempfile
import time
import base64
import ctypes

from .constants import (
    DEFAULT_HOTKEY, MODE_COPY, MODE_PASTE, MODE_SEND,
    DEFAULT_SOURCE, DEFAULT_TARGET, DEFAULT_MODEL_LABEL,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
    ASSETS_DIR = os.path.join(sys._MEIPASS, "assets")
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ASSETS_DIR = os.path.join(APP_DIR, "assets")

APP_DATA_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "TranslationBridge"
)
os.makedirs(APP_DATA_DIR, exist_ok=True)

API_KEY_FILE = os.path.join(APP_DATA_DIR, ".api_key")
CONFIG_FILE = os.path.join(APP_DATA_DIR, ".config.json")
HISTORY_FILE = os.path.join(APP_DATA_DIR, "history.json")

LOGO_FILE = os.path.join(ASSETS_DIR, "logo.png")
ICON_FILE = os.path.join(ASSETS_DIR, "icon.ico")


def _atomic_write_text(path: str, content: str) -> None:
    """Write a text file atomically so an interrupted save keeps the old file."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".tmp-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_uint32),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _protect_key(value: str) -> str:
    """Encrypt an API key for the current Windows user with DPAPI."""
    data = value.encode("utf-8")
    if not data:
        return ""
    buffer = ctypes.create_string_buffer(data)
    source = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    encrypted = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    if not crypt32.CryptProtectData(
        ctypes.byref(source), "Translation Bridge API key", None, None, None, 0,
        ctypes.byref(encrypted),
    ):
        raise ctypes.WinError()
    try:
        raw = ctypes.string_at(encrypted.pbData, encrypted.cbData)
        return "DPAPI:" + base64.b64encode(raw).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(encrypted.pbData)


def _unprotect_key(value: str) -> str:
    """Decrypt a DPAPI protected API key for the current Windows user."""
    if not value.startswith("DPAPI:"):
        return value  # Legacy plaintext key; it will be migrated on next load.
    data = base64.b64decode(value[6:].encode("ascii"), validate=True)
    buffer = ctypes.create_string_buffer(data)
    source = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    decrypted = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    if not crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None, 0, ctypes.byref(decrypted),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(decrypted.pbData, decrypted.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(decrypted.pbData)


# ─────────────────────────────────────────────────────────────
# MIGRATION (from old portable format)
# ─────────────────────────────────────────────────────────────

def _migrate_old_files():
    """Migrate config files from old portable layout to APPDATA."""
    old_api = os.path.join(APP_DIR, ".api_key")
    old_cfg = os.path.join(APP_DIR, ".config.json")

    if os.path.exists(old_api) and not os.path.exists(API_KEY_FILE):
        try:
            shutil.copy(old_api, API_KEY_FILE)
            logger.info("Migrated API key from portable layout to APPDATA.")
        except Exception as e:
            logger.warning(f"Failed to migrate old API key: {e}")

    if os.path.exists(old_cfg) and not os.path.exists(CONFIG_FILE):
        try:
            shutil.copy(old_cfg, CONFIG_FILE)
            logger.info("Migrated config from portable layout to APPDATA.")
        except Exception as e:
            logger.warning(f"Failed to migrate old config: {e}")


_migrate_old_files()


# ─────────────────────────────────────────────────────────────
# API KEY
# ─────────────────────────────────────────────────────────────

def load_api_key() -> str:
    if os.path.exists(API_KEY_FILE):
        try:
            with open(API_KEY_FILE, "r", encoding="utf-8") as f:
                stored = f.read().strip()
            key = _unprotect_key(stored)
            # Transparently migrate the portable plaintext format after a
            # successful read.  A failed migration must never prevent startup.
            if key and not stored.startswith("DPAPI:"):
                try:
                    save_api_key(key)
                    logger.info("Migrated API key to Windows DPAPI storage.")
                except Exception as e:
                    logger.warning(f"Failed to migrate API key encryption: {e}")
            return key
        except Exception as e:
            logger.error(f"Failed to read API key file: {e}")
    return ""


def save_api_key(k: str):
    try:
        key = k.strip()
        if not key:
            try:
                os.remove(API_KEY_FILE)
            except FileNotFoundError:
                pass
            logger.info("API key removed.")
            return True
        _atomic_write_text(API_KEY_FILE, _protect_key(key))
        logger.info("API key saved with Windows DPAPI protection.")
        return True
    except Exception as e:
        logger.error(f"Failed to save API key: {e}")
        return False


# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

_DEFAULT_CONFIG = {
    "hotkey": DEFAULT_HOTKEY,
    # Auto-sending an LLM response into whichever window has focus is unsafe.
    # Users can still opt into Paste or Send explicitly in the main UI.
    "mode": MODE_COPY,
    "source_lang": DEFAULT_SOURCE,
    "target_lang": DEFAULT_TARGET,
    "game": "General",
    "tone": "Gamer (Default)",
    "custom_rules": "",
    "model": DEFAULT_MODEL_LABEL,
    "history_enabled": False,
    "performance_cache_enabled": True,
}


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if not isinstance(loaded, dict):
                    raise ValueError("Configuration root must be an object")
                # Merge with defaults so new keys are always present
                merged = {
                    **_DEFAULT_CONFIG,
                    **{key: value for key, value in loaded.items() if key in _DEFAULT_CONFIG},
                }
                # Pre-privacy-release configurations defaulted to automatic
                # Send. Move them to the safe mode once; users can opt back in.
                if "history_enabled" not in loaded:
                    merged["mode"] = MODE_COPY
                for key, default in _DEFAULT_CONFIG.items():
                    if key in ("history_enabled", "performance_cache_enabled"):
                        if not isinstance(merged[key], bool):
                            merged[key] = default
                    elif not isinstance(merged[key], str):
                        merged[key] = default
                if merged["mode"] not in (MODE_COPY, MODE_PASTE, MODE_SEND):
                    merged["mode"] = MODE_COPY
                return merged
        except Exception as e:
            logger.warning(f"Failed to load config, using defaults: {e}")
    return dict(_DEFAULT_CONFIG)


def save_config(cfg: dict):
    try:
        safe_cfg = {key: cfg.get(key, default) for key, default in _DEFAULT_CONFIG.items()}
        _atomic_write_text(CONFIG_FILE, json.dumps(safe_cfg, ensure_ascii=False, indent=2))
        return True
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False


# ─────────────────────────────────────────────────────────────
# TRANSLATION HISTORY
# ─────────────────────────────────────────────────────────────

def load_history() -> list:
    """Load translation history. Returns list of {ar, en, ts} dicts."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    cleaned = []
                    for entry in data[:50]:
                        if not isinstance(entry, dict):
                            continue
                        src, dst, ts = entry.get("ar"), entry.get("en"), entry.get("ts")
                        if isinstance(src, str) and isinstance(dst, str) and isinstance(ts, str):
                            cleaned.append({"ar": src, "en": dst, "ts": ts})
                    return cleaned
        except Exception as e:
            logger.warning(f"Failed to load history: {e}")
    return []


def save_history(history: list):
    try:
        _atomic_write_text(HISTORY_FILE, json.dumps(history, ensure_ascii=False, indent=2))
        return True
    except Exception as e:
        logger.error(f"Failed to save history: {e}")
        return False


def add_history_entry(arabic: str, english: str, history: list, max_items: int = 50) -> list:
    """Add an entry and trim to max_items. Returns updated list."""
    entry = {
        "ar": arabic,
        "en": english,
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    history.insert(0, entry)
    history = history[:max_items]
    save_history(history)
    return history


def clear_history() -> bool:
    """Remove locally retained translations at the user's request."""
    try:
        os.remove(HISTORY_FILE)
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.error(f"Failed to clear history: {e}")
        return False
    logger.info("Translation history cleared.")
    return True


# ─────────────────────────────────────────────────────────────
# START WITH WINDOWS (HKCU Run key — per-user, no admin needed)
# ─────────────────────────────────────────────────────────────

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_NAME = "TranslationBridge"


def _autostart_command() -> str:
    """Command Windows should run at login. --tray starts hidden in the tray."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --tray'
    # Dev checkout: prefer pythonw so no console window flashes at login
    pyw = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pyw):
        pyw = sys.executable
    return f'"{pyw}" "{os.path.join(APP_DIR, "chat_bridge.py")}" --tray'


def is_autostart_enabled() -> bool:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _RUN_NAME)
            return True
    except OSError:
        return False


def set_autostart(enabled: bool) -> bool:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, _RUN_NAME, 0, winreg.REG_SZ, _autostart_command())
                logger.info("Autostart enabled.")
            else:
                try:
                    winreg.DeleteValue(key, _RUN_NAME)
                    logger.info("Autostart disabled.")
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        logger.error(f"Failed to update autostart: {e}")
        return False
