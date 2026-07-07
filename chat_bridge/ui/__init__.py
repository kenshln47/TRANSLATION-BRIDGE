# UI Package

import os


def apply_app_icon(win):
    """Set the app icon on a Toplevel window.

    customtkinter's CTkToplevel schedules its own default (blue) icon at
    ~200ms after creation, so a single early iconbitmap call gets overridden.
    We set ours immediately (no flash) and again at 300ms to have the last word.
    """
    from ..config import ICON_FILE

    if not os.path.exists(ICON_FILE):
        return

    def _set():
        try:
            if win.winfo_exists():
                win.iconbitmap(ICON_FILE)
        except Exception:
            pass

    _set()
    win.after(300, _set)
