"""
Translation Bridge — Translation History Panel
"""

import logging

import customtkinter as ctk

from . import apply_app_icon
from .scrolling import SmoothScrollableFrame
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
        w.geometry("480x560")
        w.resizable(False, True)
        w.attributes("-topmost", True)
        w.configure(fg_color=C.BG)
        self._window = w

        apply_app_icon(w)

        # Center on screen
        w.update_idletasks()
        x = (w.winfo_screenwidth() - 480) // 2
        y = (w.winfo_screenheight() - 560) // 2
        w.geometry(f"+{x}+{y}")

        # Header
        hdr = ctk.CTkFrame(w, fg_color="transparent")
        hdr.pack(fill="x", padx=22, pady=(20, 10))

        ctk.CTkLabel(
            hdr, text="TRANSLATION HISTORY",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=C.PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            hdr, text=f"{len(history)} SAVED",
            font=ctk.CTkFont(size=11), text_color=C.TEXT_DIM,
        ).pack(side="right")

        ctk.CTkLabel(
            w, text="Optional history is encrypted for your Windows account and never uploaded.",
            font=ctk.CTkFont(family="Segoe UI", size=10), text_color=C.TEXT_DIM,
        ).pack(anchor="w", padx=22, pady=(0, 12))

        if not history:
            ctk.CTkLabel(
                w, text="Nothing saved yet.\nHistory is off by default and stays encrypted locally.",
                font=ctk.CTkFont(family="Segoe UI", size=13), text_color=C.TEXT_DIM,
            ).pack(expand=True)
            return

        # Scrollable list
        scroll = SmoothScrollableFrame(
            w, fg_color="transparent",
            scrollbar_button_color=C.BORDER,
            scrollbar_button_hover_color=C.PRIMARY,
        )
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        for i, entry in enumerate(history):
            self._build_entry(scroll, entry, i)

    def _build_entry(self, parent, entry: dict, index: int):
        """Build a single history entry card."""
        import pyperclip

        card = ctk.CTkFrame(parent, fg_color=C.BG_CARD, corner_radius=9,
                             border_width=1, border_color=C.BORDER)
        card.pack(fill="x", pady=4)

        source_text = entry.get("source_text", "")
        target_text = entry.get("target_text", "")
        source_lang = entry.get("source_lang", "Unknown")
        target_lang = entry.get("target_lang", "Unknown")

        # Language route and timestamp.
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(8, 2))

        ctk.CTkLabel(
            top, text=f"{source_lang}  →  {target_lang}",
            font=ctk.CTkFont(size=9, weight="bold"), text_color=C.PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            top, text=entry.get("ts", ""),
            font=ctk.CTkFont(size=9), text_color=C.TEXT_DIM,
        ).pack(side="right")

        if len(source_text) > 80:
            source_text = source_text[:80] + "…"
        ctk.CTkLabel(
            card, text=source_text,
            font=ctk.CTkFont(size=10), text_color=C.TEXT_DIM,
            wraplength=430, justify="left", anchor="w",
        ).pack(fill="x", padx=10, pady=(2, 4))

        # Translation and a compact copy action.
        bot = ctk.CTkFrame(card, fg_color="transparent")
        bot.pack(fill="x", padx=10, pady=(0, 8))

        ctk.CTkLabel(
            bot, text=target_text,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=C.TEXT_SOFT,
            wraplength=330, justify="left",
        ).pack(side="left", fill="x", expand=True)

        def _copy(text=target_text):
            try:
                pyperclip.copy(text)
                logger.info("Copied a translation from history.")
            except Exception as e:
                logger.warning(f"Failed to copy from history: {e}")

        ctk.CTkButton(
            bot, text="COPY", width=48, height=28, corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            fg_color=C.BG_INPUT, hover_color=C.PRIMARY_DIM,
            text_color=C.TEXT, command=_copy,
        ).pack(side="right", padx=(4, 0))
