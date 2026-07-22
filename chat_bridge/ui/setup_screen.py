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
        self.frame.pack(fill="both", expand=True, padx=24, pady=24)

        card = ctk.CTkFrame(
            self.frame, width=430, fg_color=C.BG_CARD, corner_radius=18,
            border_width=1, border_color=C.BORDER,
        )
        card.place(relx=0.5, rely=0.5, anchor="center")

        logo = self._app._load_logo(size=(58, 58))
        if logo:
            ctk.CTkLabel(card, text="", image=logo).pack(pady=(28, 12))

        ctk.CTkLabel(
            card, text="WELCOME TO BRIDGE",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=C.PRIMARY,
        ).pack()
        ctk.CTkLabel(
            card, text="One quiet place\nfor every language.",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"), text_color=C.TEXT,
            justify="center",
        ).pack(pady=(4, 10))
        ctk.CTkLabel(
            card, text="Add an OpenRouter key to start translating in-game.",
            font=ctk.CTkFont(family="Segoe UI", size=11), text_color=C.TEXT_DIM,
        ).pack(pady=(0, 22))

        key_area = ctk.CTkFrame(card, fg_color=C.BG, corner_radius=10)
        key_area.pack(fill="x", padx=22)
        ctk.CTkLabel(
            key_area, text="OPENROUTER API KEY",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=C.TEXT_DIM,
        ).pack(anchor="w", padx=13, pady=(13, 4))
        self.entry = ctk.CTkEntry(
            key_area, placeholder_text="sk-or-v1-...", font=ctk.CTkFont(size=12),
            height=40, corner_radius=7, border_color=C.BORDER, border_width=1,
            fg_color=C.BG_INPUT, text_color=C.TEXT, show="•",
        )
        self.entry.pack(fill="x", padx=13, pady=(0, 8))
        ctk.CTkButton(
            key_area, text="PASTE FROM CLIPBOARD", height=30, corner_radius=7,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color="transparent", hover_color=C.BG_RAISED, text_color=C.TEXT_SOFT,
            border_color=C.BORDER, border_width=1, command=self._paste_key,
        ).pack(fill="x", padx=13, pady=(0, 13))

        self.status = ctk.CTkLabel(
            card, text="Your key is encrypted on this computer.",
            font=ctk.CTkFont(family="Segoe UI", size=10), text_color=C.TEXT_DIM,
        )
        self.status.pack(pady=(13, 8))
        self.btn = ctk.CTkButton(
            card, text="CONNECT AND START",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            height=42, corner_radius=7, fg_color=C.PRIMARY, hover_color=C.PRIMARY_H,
            text_color=C.BG, command=self._on_connect,
        )
        self.btn.pack(fill="x", padx=22, pady=(0, 12))
        ctk.CTkLabel(
            card, text="You can change the model, languages, and hotkey later.",
            font=ctk.CTkFont(family="Segoe UI", size=9), text_color=C.TEXT_DIM,
        ).pack(pady=(0, 26))

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
            self.status.configure(text="Enter an API key to continue", text_color=C.WARN)
            return

        self.btn.configure(state="disabled", text="CHECKING CONNECTION")
        self.status.configure(text="Connecting...", text_color=C.ACCENT)
        logger.info("Testing API key...")

        def _test():
            self._app.translator.configure_api_key(key)
            ok, msg = self._app.translator.test()
            self._app._post_ui(self._on_result, ok, msg, key)

        threading.Thread(target=_test, daemon=True).start()

    def _on_result(self, ok: bool, msg: str, key: str):
        if ok:
            from ..config import load_api_key, save_api_key
            if not save_api_key(key):
                # The test temporarily configures the in-memory translator.
                # Restore persisted state if secure storage was unavailable.
                self._app.translator.configure_api_key(load_api_key())
                self.btn.configure(state="normal", text="CONNECT AND START")
                self.status.configure(
                    text="Could not securely save the key. Check folder permissions.",
                    text_color=C.ERROR,
                )
                logger.error("Setup stopped because the API key could not be saved.")
                return
            self.frame.destroy()
            self._app._build_main()
            self._app._api_ok(True, msg)
            logger.info("Setup complete — API key validated.")
        else:
            self.btn.configure(state="normal", text="CONNECT AND START")
            self.status.configure(text=f"Error: {msg}", text_color=C.ERROR)
            logger.warning(f"Setup failed: {msg}")
