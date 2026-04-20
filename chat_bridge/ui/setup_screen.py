"""
Translation Bridge — Setup Screen (First-time API key entry)
"""

import logging
import threading

import customtkinter as ctk
import pyperclip

from .theme import C

logger = logging.getLogger(__name__)


class SetupScreen:
    """First-run screen for entering the OpenRouter API key."""

    def __init__(self, parent_app):
        self._app = parent_app
        self.frame = None
        self.entry = None
        self.status = None
        self.btn = None

    def build(self):
        self.frame = ctk.CTkFrame(self._app, fg_color="transparent")
        self.frame.pack(fill="both", expand=True, padx=20, pady=20)

        logo = self._app._load_logo(size=(80, 80))
        if logo:
            ctk.CTkLabel(self.frame, text="", image=logo).pack(pady=(20, 8))
        else:
            ctk.CTkLabel(self.frame, text="🌐", font=ctk.CTkFont(size=48)).pack(pady=(20, 8))

        ctk.CTkLabel(
            self.frame, text="Translation Bridge",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=C.ACCENT,
        ).pack(pady=(0, 2))

        ctk.CTkLabel(
            self.frame, text="Multi-language • Grok 4.1 Fast",
            font=ctk.CTkFont(size=11), text_color=C.TEXT_DIM,
        ).pack(pady=(0, 20))

        ctk.CTkFrame(self.frame, height=1, fg_color=C.SEP).pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            self.frame, text="🔑  OpenRouter API Key",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=C.TEXT,
        ).pack(anchor="w", pady=(0, 2))

        ctk.CTkLabel(
            self.frame, text="openrouter.ai/keys",
            font=ctk.CTkFont(size=10), text_color=C.TEXT_DIM,
        ).pack(anchor="w", pady=(0, 8))

        self.entry = ctk.CTkEntry(
            self.frame, placeholder_text="sk-or-v1-...",
            font=ctk.CTkFont(size=12), height=42, corner_radius=8,
            border_color=C.PRIMARY, border_width=1,
            fg_color=C.BG_INPUT, text_color=C.TEXT,
        )
        self.entry.pack(fill="x", pady=(0, 6))

        ctk.CTkButton(
            self.frame, text="Paste from clipboard",
            height=30, corner_radius=9999, font=ctk.CTkFont(size=11),
            fg_color=C.BG_CARD, hover_color=C.PRIMARY, text_color=C.ACCENT,
            border_color=C.BORDER, border_width=1,
            command=self._paste_key,
        ).pack(fill="x", pady=(0, 12))

        self.status = ctk.CTkLabel(
            self.frame, text="", font=ctk.CTkFont(size=10), text_color=C.TEXT_DIM,
        )
        self.status.pack(pady=(0, 6))

        self.btn = ctk.CTkButton(
            self.frame, text="Connect & Start",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=46, corner_radius=9999,
            fg_color=C.PRIMARY, hover_color=C.PRIMARY_H, text_color=C.BG,
            command=self._on_connect,
        )
        self.btn.pack(fill="x")

    def _paste_key(self):
        try:
            key = pyperclip.paste().strip()
            self.entry.delete(0, "end")
            self.entry.insert(0, key)
        except Exception as e:
            logger.warning(f"Failed to paste from clipboard: {e}")

    def _on_connect(self):
        key = self.entry.get().strip()
        if not key:
            self.status.configure(text="⚠️ Enter a key", text_color=C.WARN)
            return

        self.btn.configure(state="disabled", text="⏳ Testing...")
        self.status.configure(text="Connecting...", text_color=C.ACCENT)
        logger.info("Testing API key...")

        def _test():
            self._app.translator._init(key)
            ok, msg = self._app.translator.test()
            self._app.after(0, self._on_result, ok, msg, key)

        threading.Thread(target=_test, daemon=True).start()

    def _on_result(self, ok: bool, msg: str, key: str):
        if ok:
            from ..config import save_api_key
            save_api_key(key)
            self.frame.destroy()
            self._app._build_main()
            self._app._check_api()
            logger.info("Setup complete — API key validated.")
        else:
            self.btn.configure(state="normal", text="Connect & Start")
            self.status.configure(text=f"Error: {msg}", text_color=C.ERROR)
            logger.warning(f"Setup failed: {msg}")
