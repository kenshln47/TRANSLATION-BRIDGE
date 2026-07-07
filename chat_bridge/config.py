"""
Translation Bridge — Configuration & API Key Manager
"""

import json
import logging
import os
import shutil
import sys
import time

from .constants import (
    DEFAULT_HOTKEY, MODE_SEND, DEFAULT_SOURCE, DEFAULT_TARGET, DEFAULT_MODEL_LABEL,
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
            with open(API_KEY_FILE, "r") as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"Failed to read API key file: {e}")
    return ""


def save_api_key(k: str):
    try:
        with open(API_KEY_FILE, "w") as f:
            f.write(k.strip())
        logger.info("API key saved.")
    except Exception as e:
        logger.error(f"Failed to save API key: {e}")


# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

_DEFAULT_CONFIG = {
    "hotkey": DEFAULT_HOTKEY,
    "mode": MODE_SEND,
    "source_lang": DEFAULT_SOURCE,
    "target_lang": DEFAULT_TARGET,
    "game": "General",
    "tone": "Gamer (Default)",
    "custom_rules": "",
    "model": DEFAULT_MODEL_LABEL,
}


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                # Merge with defaults so new keys are always present
                merged = {**_DEFAULT_CONFIG, **loaded}
                return merged
        except Exception as e:
            logger.warning(f"Failed to load config, using defaults: {e}")
    return dict(_DEFAULT_CONFIG)


def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save config: {e}")


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
                    return data
        except Exception as e:
            logger.warning(f"Failed to load history: {e}")
    return []


def save_history(history: list):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save history: {e}")


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
