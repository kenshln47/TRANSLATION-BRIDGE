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
    MAX_CUSTOM_RULES_CHARS,
    MODEL_OPTIONS, GEMINI_25_FLASH_LITE_MODEL,
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


def _protect_text(value: str, description: str) -> str:
    """Encrypt text for the current Windows user with DPAPI."""
    data = value.encode("utf-8")
    if not data:
        return ""
    buffer = ctypes.create_string_buffer(data)
    source = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    encrypted = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    if not crypt32.CryptProtectData(
        ctypes.byref(source), description, None, None, None, 0,
        ctypes.byref(encrypted),
    ):
        raise ctypes.WinError()
    try:
        raw = ctypes.string_at(encrypted.pbData, encrypted.cbData)
        return "DPAPI:" + base64.b64encode(raw).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(encrypted.pbData)


def _unprotect_text(value: str) -> str:
    """Decrypt DPAPI-protected text for the current Windows user."""
    if not value.startswith("DPAPI:"):
        return value  # Legacy plaintext value; callers decide whether to migrate it.
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


def _protect_key(value: str) -> str:
    return _protect_text(value, "Translation Bridge API key")


def _unprotect_key(value: str) -> str:
    return _unprotect_text(value)


# ─────────────────────────────────────────────────────────────
# MIGRATION (from old portable format)
# ─────────────────────────────────────────────────────────────

def _migrate_old_files():
    """Migrate config files from old portable layout to APPDATA."""
    old_api = os.path.join(APP_DIR, ".api_key")
    old_cfg = os.path.join(APP_DIR, ".config.json")

    if os.path.exists(old_api) and os.path.abspath(old_api) != os.path.abspath(API_KEY_FILE):
        try:
            with open(old_api, "r", encoding="utf-8") as source:
                legacy_stored = source.read().strip()
            legacy_key = _unprotect_key(legacy_stored)
            if legacy_key and not os.path.exists(API_KEY_FILE):
                _atomic_write_text(API_KEY_FILE, _protect_key(legacy_key))

            # Never delete the only copy.  Remove the portable plaintext only
            # after the DPAPI destination exists, decrypts, and matches it.
            with open(API_KEY_FILE, "r", encoding="utf-8") as destination:
                migrated_stored = destination.read().strip()
            if legacy_key and _unprotect_key(migrated_stored) == legacy_key:
                os.remove(old_api)
                logger.info("Migrated API key to DPAPI storage and removed the portable copy.")
            elif legacy_key:
                logger.warning("Portable API key differs from APPDATA; leaving it untouched.")
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
                if save_api_key(key):
                    logger.info("Migrated API key to Windows DPAPI storage.")
                else:
                    logger.warning("Failed to migrate API key encryption.")
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
    # Chat reading is always explicit opt-in. Regions use normalized window
    # coordinates so one profile works across resolutions and DPI scales.
    "chat_context_enabled": False,
    "chat_regions": {},
    "chat_context_max_lines": 4,
}

_LEGACY_MODEL_LABELS = {
    "⚡ Gemini 2.5 Flash-Lite — fastest & cheapest (default)": next(
        label for label, slug in MODEL_OPTIONS.items()
        if slug == GEMINI_25_FLASH_LITE_MODEL
    ),
    # A short-lived development build used a model name OpenRouter never
    # published. Preserve the user's quality-first choice on upgrade.
    "✨ Gemini 3.5 Flash-Lite — recommended quality": DEFAULT_MODEL_LABEL,
}


def _default_config_copy() -> dict:
    """Return defaults without sharing mutable region dictionaries."""
    return {
        key: dict(value) if isinstance(value, dict) else value
        for key, value in _DEFAULT_CONFIG.items()
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
                    **_default_config_copy(),
                    **{key: value for key, value in loaded.items() if key in _DEFAULT_CONFIG},
                }
                # Pre-privacy-release configurations defaulted to automatic
                # Send. Move them to the safe mode once; users can opt back in.
                if "history_enabled" not in loaded:
                    merged["mode"] = MODE_COPY
                for key, default in _DEFAULT_CONFIG.items():
                    value = merged[key]
                    # bool is a subclass of int, so check it first.
                    if isinstance(default, bool):
                        if not isinstance(value, bool):
                            merged[key] = default
                    elif isinstance(default, int):
                        if not isinstance(value, int) or isinstance(value, bool):
                            merged[key] = default
                    elif isinstance(default, dict):
                        if not isinstance(value, dict):
                            merged[key] = dict(default)
                    elif not isinstance(value, str):
                        merged[key] = default
                if merged["mode"] not in (MODE_COPY, MODE_PASTE, MODE_SEND):
                    merged["mode"] = MODE_COPY
                merged["model"] = _LEGACY_MODEL_LABELS.get(
                    merged["model"], merged["model"]
                )
                if merged["model"] not in MODEL_OPTIONS:
                    merged["model"] = DEFAULT_MODEL_LABEL
                merged["chat_context_max_lines"] = max(
                    1, min(8, merged["chat_context_max_lines"])
                )
                if len(merged["custom_rules"]) > MAX_CUSTOM_RULES_CHARS:
                    merged["custom_rules"] = merged["custom_rules"][:MAX_CUSTOM_RULES_CHARS]
                return merged
        except Exception as e:
            logger.warning(f"Failed to load config, using defaults: {e}")
    return _default_config_copy()


def save_config(cfg: dict):
    try:
        safe_cfg = {key: cfg.get(key, default) for key, default in _DEFAULT_CONFIG.items()}
        rules = safe_cfg.get("custom_rules", "")
        if not isinstance(rules, str) or len(rules) > MAX_CUSTOM_RULES_CHARS:
            raise ValueError(
                f"Custom rules must be at most {MAX_CUSTOM_RULES_CHARS} characters"
            )
        # Validate through the same path used at startup before replacing the
        # user's current configuration.
        for key, default in _DEFAULT_CONFIG.items():
            value = safe_cfg[key]
            if isinstance(default, bool) and not isinstance(value, bool):
                raise ValueError(f"{key} must be a boolean")
            if isinstance(default, int) and not isinstance(default, bool):
                if not isinstance(value, int) or isinstance(value, bool):
                    raise ValueError(f"{key} must be an integer")
            if isinstance(default, dict) and not isinstance(value, dict):
                raise ValueError(f"{key} must be an object")
            if isinstance(default, str) and not isinstance(value, str):
                raise ValueError(f"{key} must be a string")
        safe_cfg["chat_context_max_lines"] = max(
            1, min(8, safe_cfg["chat_context_max_lines"])
        )
        _atomic_write_text(CONFIG_FILE, json.dumps(safe_cfg, ensure_ascii=False, indent=2))
        return True
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False


# ─────────────────────────────────────────────────────────────
# TRANSLATION HISTORY
# ─────────────────────────────────────────────────────────────

def _clean_history_entries(data) -> list:
    """Normalize current and pre-8.6 history entries to language-neutral keys."""
    if not isinstance(data, list):
        return []
    cleaned = []
    for entry in data[:50]:
        if not isinstance(entry, dict):
            continue
        source_text = entry.get("source_text", entry.get("ar"))
        target_text = entry.get("target_text", entry.get("en"))
        timestamp = entry.get("ts")
        # Old versions called the fields `ar` and `en` even when the user had
        # selected another language pair, so their true direction is unknown.
        source_lang = entry.get("source_lang", "Unknown")
        target_lang = entry.get("target_lang", "Unknown")
        if not all(isinstance(item, str) for item in (
            source_text, target_text, timestamp, source_lang, target_lang
        )):
            continue
        cleaned.append({
            "source_text": source_text,
            "target_text": target_text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "ts": timestamp,
        })
    return cleaned


def load_history() -> list:
    """Load and migrate the optional, DPAPI-encrypted local history."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                stored = json.load(f)
            if isinstance(stored, dict) and stored.get("protection") == "DPAPI":
                payload = _unprotect_text(stored.get("payload", ""))
                return _clean_history_entries(json.loads(payload))
            # Pre-8.6 files were plaintext JSON lists. Rewrite them immediately
            # after a successful parse so chat text is no longer left readable.
            cleaned = _clean_history_entries(stored)
            if isinstance(stored, list) and save_history(cleaned):
                logger.info("Migrated translation history to DPAPI encryption.")
            return cleaned
        except Exception as e:
            logger.warning(f"Failed to load history: {e}")
    return []


def save_history(history: list):
    try:
        cleaned = _clean_history_entries(history)
        payload = json.dumps(cleaned, ensure_ascii=False, separators=(",", ":"))
        envelope = {
            "version": 2,
            "protection": "DPAPI",
            "payload": _protect_text(payload, "Translation Bridge local history"),
        }
        _atomic_write_text(
            HISTORY_FILE, json.dumps(envelope, ensure_ascii=False, indent=2)
        )
        return True
    except Exception as e:
        logger.error(f"Failed to save history: {e}")
        return False


def add_history_entry(
    source_text: str,
    target_text: str,
    history: list,
    max_items: int = 50,
    source_lang: str = None,
    target_lang: str = None,
) -> list:
    """Add a language-neutral entry and trim to ``max_items``.

    Language arguments are optional for backward compatibility. Callers should
    pass the request snapshot when possible; otherwise current settings are used.
    """
    if source_lang is None or target_lang is None:
        cfg = load_config()
        source_lang = source_lang or cfg.get("source_lang", "Unknown")
        target_lang = target_lang or cfg.get("target_lang", "Unknown")
    entry = {
        "source_text": source_text,
        "target_text": target_text,
        "source_lang": source_lang,
        "target_lang": target_lang,
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
