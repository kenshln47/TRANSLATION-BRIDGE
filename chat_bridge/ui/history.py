"""
Translation Bridge — Translation History Panel
"""

import logging
import customtkinter as ctk

from .theme import C

logger = logging.getLogger(__name__)


class HistoryPanel:
    """A scrollable panel showing past translations with one-click copy."""

    def __init__(self, parent_app):
        self._app = parent_app
        self._window = None

    def toggle(self):
        """Toggle the history panel visibility."""
        if self._window and self._window.winfo_exists():
            self._window.destroy()
            self._window = None
            return
        self._show()

    def _show(self):
        from ..config import load_history

        history = load_history()

        w = ctk.CTkToplevel(self._app)
        w.title("Translation History")
        w.geometry("440x520")
        w.resizable(False, True)
        w.attributes("-topmost", True)
        w.configure(fg_color=C.BG)
        self._window = w

        # Center on screen
        w.update_idletasks()
        x = (w.winfo_screenwidth() - 440) // 2
        y = (w.winfo_screenheight() - 520) // 2
        w.geometry(f"+{x}+{y}")

        # Header
        hdr = ctk.CTkFrame(w, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(12, 8))

        ctk.CTkLabel(
            hdr, text="📜 TRANSLATION HISTORY",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=C.ACCENT,
        ).pack(side="left")

        ctk.CTkLabel(
            hdr, text=f"{len(history)} translations",
            font=ctk.CTkFont(size=11), text_color=C.TEXT_DIM,
        ).pack(side="right")

        ctk.CTkFrame(w, height=1, fg_color=C.SEP).pack(fill="x", padx=16)

        if not history:
            ctk.CTkLabel(
                w, text="No translations yet.\nUse the app to start translating!",
                font=ctk.CTkFont(size=13), text_color=C.TEXT_DIM,
            ).pack(expand=True)
            return

        # Scrollable list
        scroll = ctk.CTkScrollableFrame(
            w, fg_color="transparent",
            scrollbar_button_color=C.BORDER,
            scrollbar_button_hover_color=C.PRIMARY,
        )
        scroll.pack(fill="both", expand=True, padx=12, pady=8)

        for i, entry in enumerate(history):
            self._build_entry(scroll, entry, i)

    def _build_entry(self, parent, entry: dict, index: int):
        """Build a single history entry card."""
        import pyperclip

        card = ctk.CTkFrame(parent, fg_color=C.BG_CARD, corner_radius=10,
                             border_width=1, border_color=C.BORDER)
        card.pack(fill="x", pady=3)

        # Top row: Arabic text + timestamp
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(8, 2))

        ctk.CTkLabel(
            top, text=entry.get("ts", ""),
            font=ctk.CTkFont(size=9), text_color=C.TEXT_DIM,
        ).pack(side="left")

        ar_text = entry.get("ar", "")
        if len(ar_text) > 40:
            ar_text = ar_text[:40] + "..."
        ctk.CTkLabel(
            top, text=ar_text,
            font=ctk.CTkFont(size=10), text_color=C.TEXT_DIM,
            justify="right",
        ).pack(side="right")

        # Bottom row: English translation + copy button
        bot = ctk.CTkFrame(card, fg_color="transparent")
        bot.pack(fill="x", padx=10, pady=(0, 8))

        en_text = entry.get("en", "")
        ctk.CTkLabel(
            bot, text=en_text,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=C.ACCENT,
            wraplength=300, justify="left",
        ).pack(side="left", fill="x", expand=True)

        def _copy(text=en_text):
            try:
                pyperclip.copy(text)
                logger.info(f"Copied from history: {text[:30]}")
            except Exception as e:
                logger.warning(f"Failed to copy from history: {e}")

        ctk.CTkButton(
            bot, text="📋", width=32, height=28, corner_radius=6,
            font=ctk.CTkFont(size=12),
            fg_color=C.BG_INPUT, hover_color=C.PRIMARY,
            text_color=C.TEXT, command=_copy,
        ).pack(side="right", padx=(4, 0))
