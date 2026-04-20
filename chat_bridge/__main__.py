"""
Translation Bridge v8.0 — Entry Point
Multi-language translator via OpenRouter (Grok 4.1 Fast)

Run with: python -m chat_bridge
"""

import ctypes
import logging
import os
import sys

from .constants import MUTEX_NAME

# ─────────────────────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────────────────────

def _setup_logging():
    """Configure application-wide logging."""
    log_dir = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        "TranslationBridge"
    )
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "app.log")

    # Rotate: keep last 500KB
    if os.path.exists(log_file):
        try:
            if os.path.getsize(log_file) > 500_000:
                os.remove(log_file)
        except Exception:
            pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger(__name__).info("=== Translation Bridge starting ===")


# ─────────────────────────────────────────────────────────────
# SINGLE INSTANCE
# ─────────────────────────────────────────────────────────────

def _enforce_single_instance():
    """Prevent multiple instances using a Windows named mutex."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        hwnd = user32.FindWindowW(None, "Translation Bridge")
        if hwnd:
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
        sys.exit(0)
    return mutex


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    _setup_logging()
    _mutex = _enforce_single_instance()

    from .app import App
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
