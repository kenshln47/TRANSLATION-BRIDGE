"""
Translation Bridge — Settings Dialog
"""

import logging
import os
import threading

import customtkinter as ctk
import pyperclip

from .theme import C
from ..config import load_api_key, save_api_key, save_config, ICON_FILE
from ..constants import (
    GAME_LIST, TONE_LIST, ARABIC_TO_ENGLISH,
    SOURCE_LIST, TARGET_LIST, DEFAULT_SOURCE, DEFAULT_TARGET,
)
from ..hotkey import record_hotkey_native

logger = logging.getLogger(__name__)


class SettingsDialog:
    """Modal settings dialog for configuring the app."""

    def __init__(self, parent_app):
        self._app = parent_app
        self._pending_hotkey = parent_app.cfg.get("hotkey", "ctrl+shift+t")

    def show(self):
        d = ctk.CTkToplevel(self._app)
        d.title("Settings")
        d.geometry("380x780")
        d.resizable(False, False)
        d.attributes("-topmost", True)
        d.grab_set()
        d.configure(fg_color=C.BG)
        self._dialog = d

        try:
            if os.path.exists(ICON_FILE):
                d.after(200, lambda: d.iconbitmap(ICON_FILE))
        except Exception as e:
            logger.warning(f"Failed to set settings icon: {e}")

        d.update_idletasks()
        x = (d.winfo_screenwidth() - 380) // 2
        y = (d.winfo_screenheight() - 780) // 2
        d.geometry(f"+{x}+{y}")

        ctk.CTkLabel(
            d, text="SETTINGS",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=C.ACCENT,
        ).pack(padx=16, pady=(12, 10))

        # ── API Key ──
        ctk.CTkLabel(d, text="API KEY",
                      font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                      text_color=C.TEXT).pack(anchor="w", padx=16)

        self._key_entry = ctk.CTkEntry(
            d, placeholder_text="sk-or-v1-...",
            font=ctk.CTkFont(size=11), height=36, corner_radius=8,
            border_color=C.PRIMARY, border_width=2,
            fg_color=C.BG_INPUT, text_color=C.TEXT,
        )
        self._key_entry.pack(fill="x", padx=16, pady=(2, 4))
        self._key_entry.focus_set()
        cur = load_api_key()
        if cur:
            self._key_entry.insert(0, cur)

        ctk.CTkButton(
            d, text="PASTE", height=26, corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=C.BG_CARD, hover_color=C.PRIMARY, text_color=C.ACCENT,
            command=self._paste_key,
        ).pack(fill="x", padx=16, pady=(0, 10))

        # ── Hotkey ──
        ctk.CTkLabel(d, text="GLOBAL HOTKEY",
                      font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                      text_color=C.TEXT).pack(anchor="w", padx=16)

        ctk.CTkLabel(d, text="Click 'Record', press your combo, release to capture",
                      font=ctk.CTkFont(size=9), text_color=C.TEXT_DIM).pack(anchor="w", padx=16)

        hk_frame = ctk.CTkFrame(d, fg_color="transparent")
        hk_frame.pack(fill="x", padx=16, pady=(2, 12))

        self._hk_btn = ctk.CTkButton(
            hk_frame, text=self._pending_hotkey.upper(),
            font=ctk.CTkFont(size=12, weight="bold"),
            height=36, corner_radius=8,
            fg_color=C.BG_INPUT, hover_color=C.BG_INPUT,
            border_color=C.PRIMARY, border_width=2, text_color=C.ACCENT,
            state="disabled"
        )
        self._hk_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self._rec_btn = ctk.CTkButton(
            hk_frame, text="⏺ Record", width=60, height=36,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=C.BG_CARD, hover_color=C.ERROR,
            command=self._on_record,
        )
        self._rec_btn.pack(side="right")

        # ── Source Language ──
        self._src_var = ctk.StringVar(value=self._app.cfg.get("source_lang", DEFAULT_SOURCE))
        self._tgt_var = ctk.StringVar(value=self._app.cfg.get("target_lang", DEFAULT_TARGET))

        ctk.CTkLabel(d, text="SOURCE LANGUAGE (أكتب بـ)",
                      font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                      text_color=C.TEXT).pack(anchor="w", padx=16, pady=(6, 0))

        ctk.CTkOptionMenu(
            d, variable=self._src_var, values=SOURCE_LIST,
            font=ctk.CTkFont(size=12), fg_color=C.BG_INPUT, button_color=C.PRIMARY,
        ).pack(fill="x", padx=16, pady=(2, 6))

        # ── Target Language ──
        ctk.CTkLabel(d, text="TARGET LANGUAGE (ترجم لـ)",
                      font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                      text_color=C.TEXT).pack(anchor="w", padx=16, pady=(0, 0))

        ctk.CTkOptionMenu(
            d, variable=self._tgt_var, values=TARGET_LIST,
            font=ctk.CTkFont(size=12), fg_color=C.BG_INPUT, button_color=C.PRIMARY,
        ).pack(fill="x", padx=16, pady=(2, 10))

        # ── Game Preset ──
        self._game_var = ctk.StringVar(value=self._app.cfg.get("game", "General"))
        self._tone_var = ctk.StringVar(value=self._app.cfg.get("tone", "Gamer (Default)"))

        ctk.CTkLabel(d, text="GAME PRESET (Auto Dictionary)",
                      font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                      text_color=C.TEXT).pack(anchor="w", padx=16, pady=(4, 0))

        ctk.CTkOptionMenu(
            d, variable=self._game_var, values=GAME_LIST,
            font=ctk.CTkFont(size=12), fg_color=C.BG_INPUT, button_color=C.PRIMARY,
        ).pack(fill="x", padx=16, pady=(2, 10))

        # ── Tone ──
        ctk.CTkLabel(d, text="AI TONE",
                      font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                      text_color=C.TEXT).pack(anchor="w", padx=16, pady=(0, 0))

        ctk.CTkSegmentedButton(
            d, variable=self._tone_var, values=TONE_LIST,
            selected_color=C.PRIMARY, selected_hover_color=C.PRIMARY_H,
            fg_color=C.BG_INPUT,
        ).pack(fill="x", padx=16, pady=(2, 10))

        # ── Custom Rules ──
        cr_row = ctk.CTkFrame(d, fg_color="transparent")
        cr_row.pack(fill="x", padx=16, pady=(6, 0))

        ctk.CTkLabel(cr_row, text="OVERRIDE RULES",
                      font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                      text_color=C.TEXT).pack(side="left")

        ctk.CTkButton(
            cr_row, text="📂 Import Profile", width=110, height=24, corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=C.BG_CARD, hover_color=C.PRIMARY, text_color=C.ACCENT,
            border_width=1, border_color=C.BORDER,
            command=self._import_profile,
        ).pack(side="right")

        hint = "(اختياري) اكتب قواعدك، أو انسخ ملف مجتمعي وارفعـه عبر الزر أعلاه"
        ctk.CTkLabel(d, text=hint, font=ctk.CTkFont(size=9),
                      text_color=C.TEXT_DIM).pack(anchor="w", padx=16)

        self._rules_box = ctk.CTkTextbox(
            d, font=ctk.CTkFont(size=11), height=80, corner_radius=8,
            border_color=C.PRIMARY, border_width=1,
            fg_color=C.BG_INPUT, text_color=C.TEXT,
        )
        self._rules_box.pack(fill="x", padx=16, pady=(2, 16))

        saved_rules = self._app.cfg.get("custom_rules", "")
        if saved_rules:
            self._rules_box.insert("1.0", saved_rules)

        # ── Buttons ──
        row = ctk.CTkFrame(d, fg_color="transparent")
        row.pack(fill="x", padx=16)

        ctk.CTkButton(
            row, text="SAVE", width=150, height=36,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=C.PRIMARY, hover_color=C.PRIMARY_H, command=self._save,
        ).pack(side="left", expand=True, padx=(0, 4))

        ctk.CTkButton(
            row, text="CANCEL", width=150, height=36,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=C.BG_CARD, hover_color=C.BORDER, command=self._close,
        ).pack(side="right", expand=True, padx=(4, 0))

        d.protocol("WM_DELETE_WINDOW", self._close)

    def _paste_key(self):
        try:
            self._key_entry.delete(0, "end")
            self._key_entry.insert(0, pyperclip.paste().strip())
        except Exception as e:
            logger.warning(f"Failed to paste key: {e}")

    def _on_record(self):
        self._hk_btn.configure(text="Press Keys...", text_color=C.WARN)
        self._rec_btn.configure(state="disabled")
        self._app._hotkey.unregister()

        def _wait():
            result = record_hotkey_native(timeout=10.0)
            if result:
                # Normalize arabic characters
                normalized = []
                for p in result.split('+'):
                    p = p.strip()
                    normalized.append(ARABIC_TO_ENGLISH.get(p, p))
                result = '+'.join(normalized)
                self._pending_hotkey = result

            self._app.after(0, self._on_recorded)

        threading.Thread(target=_wait, daemon=True).start()

    def _on_recorded(self):
        if not self._dialog.winfo_exists():
            return
        self._hk_btn.configure(text=self._pending_hotkey.upper(), text_color=C.ACCENT)
        self._rec_btn.configure(state="normal")

    def _import_profile(self):
        file_path = ctk.filedialog.askopenfilename(
            title="Import Community Profile",
            filetypes=(("Text Files", "*.txt"), ("All Files", "*.*"))
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self._rules_box.delete("1.0", "end")
                    self._rules_box.insert("1.0", f.read())
                logger.info(f"Imported profile from: {file_path}")
            except Exception as e:
                logger.error(f"Failed to import profile: {e}")

    def _save(self):
        k = self._key_entry.get().strip()
        if k:
            save_api_key(k)
            self._app.translator._init(k)
            self._app._check_api()

        hk = self._pending_hotkey.strip().lower()
        if hk:
            self._app.cfg["hotkey"] = hk
        self._app.cfg["source_lang"] = self._src_var.get()
        self._app.cfg["target_lang"] = self._tgt_var.get()
        self._app.cfg["game"] = self._game_var.get()
        self._app.cfg["tone"] = self._tone_var.get()
        self._app.cfg["custom_rules"] = self._rules_box.get("1.0", "end").strip()
        save_config(self._app.cfg)

        # Update main UI subtitle to reflect language
        if hasattr(self._app, '_lang_label'):
            self._app._lang_label.configure(
                text=f"{self._src_var.get()} → {self._tgt_var.get()}"
            )

        logger.info(f"Settings saved. {self._src_var.get()} → {self._tgt_var.get()}")
        self._close()

    def _close(self):
        self._app._hotkey.unregister()
        self._app._hotkey.register(
            self._app.cfg.get("hotkey", "ctrl+shift+t"),
            lambda: self._app.after(0, self._app._show_quick_popup)
        )
        if self._dialog.winfo_exists():
            self._dialog.destroy()
