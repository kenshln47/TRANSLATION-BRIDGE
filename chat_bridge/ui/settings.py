"""
Translation Bridge — Settings Dialog
"""

import logging
import threading

import customtkinter as ctk
import pyperclip

from . import apply_app_icon
from .scrolling import SmoothScrollableFrame
from .theme import C
from ..config import (
    load_api_key, save_api_key, save_config,
    is_autostart_enabled, set_autostart, clear_history,
)
from ..constants import (
    GAME_LIST, TONE_LIST, ARABIC_TO_ENGLISH,
    SOURCE_LIST, TARGET_LIST, DEFAULT_SOURCE, DEFAULT_TARGET,
    MODEL_LABELS, MODEL_OPTIONS, OPENROUTER_MODEL, DEFAULT_MODEL_LABEL,
    MAX_CUSTOM_RULES_CHARS,
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
        d.resizable(False, False)
        d.attributes("-topmost", True)
        d.grab_set()
        d.configure(fg_color=C.BG)
        self._dialog = d
        d.protocol("WM_DELETE_WINDOW", self._close)

        apply_app_icon(d)

        # Fit small screens: cap the height and let the body scroll instead of
        # pushing SAVE below the edge of 768p laptop displays.
        d.update_idletasks()
        scr_w, scr_h = d.winfo_screenwidth(), d.winfo_screenheight()
        w, h = 480, min(860, scr_h - 80)
        d.geometry(f"{w}x{h}+{(scr_w - w) // 2}+{max(0, (scr_h - h) // 2)}")

        header = ctk.CTkFrame(d, fg_color=C.BG_RAISED, corner_radius=10)
        header.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(
            header, text="SETTINGS",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=C.PRIMARY,
        ).pack(anchor="w", padx=14, pady=(11, 0))
        ctk.CTkLabel(
            header, text="Control the translation desk, without the clutter.",
            font=ctk.CTkFont(family="Segoe UI", size=10), text_color=C.TEXT_DIM,
        ).pack(anchor="w", padx=14, pady=(1, 11))

        # Buttons pinned to the bottom so they are always reachable;
        # everything else lives in a scrollable body.
        btn_row = ctk.CTkFrame(d, fg_color="transparent")
        btn_row.pack(side="bottom", fill="x", padx=16, pady=(6, 12))
        self._save_status = ctk.CTkLabel(
            btn_row, text="", font=ctk.CTkFont(size=9), text_color=C.WARN,
        )
        self._save_status.pack(fill="x", pady=(0, 3))
        action_row = ctk.CTkFrame(btn_row, fg_color="transparent")
        action_row.pack(fill="x")

        body = SmoothScrollableFrame(
            d, fg_color="transparent",
            scrollbar_button_color=C.BORDER,
            scrollbar_button_hover_color=C.PRIMARY,
        )
        body.pack(fill="both", expand=True, padx=(4, 0))
        d = body  # sections below attach to the scrollable body

        # ── API Key ──
        ctk.CTkLabel(d, text="API KEY",
                      font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                      text_color=C.TEXT).pack(anchor="w", padx=16)

        self._key_entry = ctk.CTkEntry(
            d, placeholder_text="sk-or-v1-...",
            font=ctk.CTkFont(size=11), height=36, corner_radius=8,
            border_color=C.PRIMARY, border_width=2,
            fg_color=C.BG_INPUT, text_color=C.TEXT, show="•",
        )
        self._key_entry.pack(fill="x", padx=16, pady=(2, 4))
        self._key_entry.focus_set()
        cur = load_api_key()
        if cur:
            self._key_entry.insert(0, cur)

        ctk.CTkButton(
            d, text="PASTE KEY", height=28, corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=C.BG_RAISED, hover_color=C.PRIMARY_DIM, text_color=C.TEXT_SOFT,
            command=self._paste_key,
        ).pack(fill="x", padx=16, pady=(0, 10))

        # ── Model ──
        self._model_var = ctk.StringVar(
            value=self._app.cfg.get("model", DEFAULT_MODEL_LABEL)
        )
        ctk.CTkLabel(d, text="MODEL",
                      font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                      text_color=C.TEXT).pack(anchor="w", padx=16)

        ctk.CTkOptionMenu(
            d, variable=self._model_var, values=MODEL_LABELS,
            font=ctk.CTkFont(size=11), fg_color=C.BG_INPUT, button_color=C.PRIMARY,
        ).pack(fill="x", padx=16, pady=(2, 10))

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
            hk_frame, text="RECORD", width=70, height=36,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=C.BG_RAISED, hover_color=C.ERROR,
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
            cr_row, text="IMPORT PROFILE", width=118, height=24, corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=C.BG_RAISED, hover_color=C.PRIMARY_DIM, text_color=C.TEXT_SOFT,
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

        # ── Start with Windows ──
        self._autostart_var = ctk.BooleanVar(value=is_autostart_enabled())
        auto_row = ctk.CTkFrame(d, fg_color="transparent")
        auto_row.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(auto_row, text="START WITH WINDOWS",
                      font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                      text_color=C.TEXT).pack(side="left")

        ctk.CTkSwitch(
            auto_row, text="", variable=self._autostart_var,
            onvalue=True, offvalue=False, width=48,
            progress_color=C.PRIMARY,
        ).pack(side="right")

        ctk.CTkLabel(d, text="يفتح تلقائياً مع الويندوز ويقعد بالخلفية جاهز",
                      font=ctk.CTkFont(size=9), text_color=C.TEXT_DIM,
                      ).pack(anchor="w", padx=16, pady=(0, 8))

        # ── Privacy / History ──
        privacy_row = ctk.CTkFrame(d, fg_color="transparent")
        privacy_row.pack(fill="x", padx=16, pady=(4, 6))
        self._history_enabled_var = ctk.BooleanVar(
            value=bool(self._app.cfg.get("history_enabled", False))
        )
        ctk.CTkLabel(
            privacy_row, text="SAVE TRANSLATION HISTORY",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=C.TEXT,
        ).pack(side="left")
        ctk.CTkSwitch(
            privacy_row, text="", variable=self._history_enabled_var,
            onvalue=True, offvalue=False, width=48, progress_color=C.PRIMARY,
        ).pack(side="right")
        ctk.CTkLabel(
            d, text="Off by default. When enabled, entries are DPAPI-encrypted for your Windows account.",
            font=ctk.CTkFont(size=9), text_color=C.TEXT_DIM,
        ).pack(anchor="w", padx=16)
        ctk.CTkButton(
            d, text="CLEAR SAVED HISTORY", height=28, corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=C.BG_RAISED, hover_color=C.ERROR, text_color=C.TEXT,
            border_width=1, border_color=C.BORDER, command=self._clear_history,
        ).pack(fill="x", padx=16, pady=(4, 12))

        cache_row = ctk.CTkFrame(d, fg_color="transparent")
        cache_row.pack(fill="x", padx=16, pady=(0, 6))
        self._cache_enabled_var = ctk.BooleanVar(
            value=bool(self._app.cfg.get("performance_cache_enabled", True))
        )
        ctk.CTkLabel(
            cache_row, text="INSTANT REPEAT CACHE",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=C.TEXT,
        ).pack(side="left")
        ctk.CTkSwitch(
            cache_row, text="", variable=self._cache_enabled_var,
            onvalue=True, offvalue=False, width=48, progress_color=C.PRIMARY,
        ).pack(side="right")
        ctk.CTkLabel(
            d, text="Keeps repeated translations in memory for 10 minutes; never writes them to disk.",
            font=ctk.CTkFont(size=9), text_color=C.TEXT_DIM,
        ).pack(anchor="w", padx=16, pady=(0, 12))

        # —— One-shot game chat context ——
        chat_row = ctk.CTkFrame(d, fg_color="transparent")
        chat_row.pack(fill="x", padx=16, pady=(2, 6))
        self._chat_context_enabled_var = ctk.BooleanVar(
            value=bool(self._app.cfg.get("chat_context_enabled", False))
        )
        ctk.CTkLabel(
            chat_row, text="GAME CHAT CONTEXT (BETA)",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=C.TEXT,
        ).pack(side="left")
        ctk.CTkSwitch(
            chat_row, text="", variable=self._chat_context_enabled_var,
            onvalue=True, offvalue=False, width=48, progress_color=C.PRIMARY,
        ).pack(side="right")
        ctk.CTkLabel(
            d,
            text="Off by default. Reads the visible chat once when Quick Translate opens, keeps text in memory, and saves no screenshots.",
            font=ctk.CTkFont(size=9), text_color=C.TEXT_DIM,
            wraplength=430, justify="left",
        ).pack(anchor="w", padx=16)
        ctk.CTkButton(
            d, text="CALIBRATE CHAT AREA", height=28, corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=C.BG_RAISED, hover_color=C.PRIMARY_DIM,
            text_color=C.TEXT, border_width=1, border_color=C.BORDER,
            command=self._start_chat_calibration,
        ).pack(fill="x", padx=16, pady=(4, 12))

        # ── Buttons (pinned row created before the scrollable body) ──
        ctk.CTkButton(
            action_row, text="SAVE", width=150, height=36,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=C.PRIMARY, hover_color=C.PRIMARY_H, text_color=C.BG, command=self._save,
        ).pack(side="left", expand=True, padx=(0, 4))

        ctk.CTkButton(
            action_row, text="CANCEL", width=150, height=36,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=C.BG_RAISED, hover_color=C.BORDER, text_color=C.TEXT, command=self._close,
        ).pack(side="right", expand=True, padx=(4, 0))

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

            self._app._post_ui(self._on_recorded)

        threading.Thread(target=_wait, daemon=True).start()

    def _on_recorded(self):
        if not self._dialog.winfo_exists():
            return
        self._hk_btn.configure(text=self._pending_hotkey.upper(), text_color=C.ACCENT)
        self._rec_btn.configure(state="normal")
        # Re-register hotkey immediately so it's not lost during settings
        self._app._register_hotkey(self._pending_hotkey)

    def _import_profile(self):
        file_path = ctk.filedialog.askopenfilename(
            title="Import Community Profile",
            filetypes=(("Text Files", "*.txt"), ("All Files", "*.*"))
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    profile = f.read(MAX_CUSTOM_RULES_CHARS + 1)
                if len(profile) > MAX_CUSTOM_RULES_CHARS:
                    self._show_save_error(
                        f"Profile is too long (maximum {MAX_CUSTOM_RULES_CHARS:,} characters)."
                    )
                    return
                self._rules_box.delete("1.0", "end")
                self._rules_box.insert("1.0", profile)
                self._save_status.configure(
                    text="Profile imported. Save to apply it.", text_color=C.ACCENT
                )
                logger.info(f"Imported profile from: {file_path}")
            except Exception as e:
                logger.error(f"Failed to import profile: {e}")
                self._show_save_error("Could not read that profile file.")

    def _clear_history(self):
        if clear_history():
            self._app._history = []
            self._save_status.configure(
                text="Encrypted local history cleared.", text_color=C.ACCENT
            )
            logger.info("History cleared from Settings.")
        else:
            self._show_save_error("Could not clear local history.")

    def _start_chat_calibration(self):
        start = getattr(self._app, "start_chat_calibration", None)
        if not callable(start):
            self._show_save_error("Chat calibration is unavailable in this build.")
            return
        # The full-screen selector must receive mouse input. Temporarily release
        # this modal's Tk grab; restore it when App reveals Settings again.
        binding_id = None

        def _restore_grab(_event=None):
            nonlocal binding_id
            if not self._dialog.winfo_exists() or self._dialog.state() == "withdrawn":
                return
            try:
                self._dialog.grab_set()
            except Exception:
                pass
            if binding_id:
                self._dialog.unbind("<Map>", binding_id)
                binding_id = None

        try:
            self._dialog.grab_release()
            binding_id = self._dialog.bind("<Map>", _restore_grab, add="+")
            start()
            _restore_grab()
        except Exception as e:
            _restore_grab()
            logger.error(f"Failed to start chat calibration: {e}")
            self._show_save_error("Could not start chat-area calibration.")

    def _show_save_error(self, message: str):
        logger.error(message)
        if hasattr(self, "_save_status"):
            self._save_status.configure(text=message, text_color=C.ERROR)

    def _save(self):
        k = self._key_entry.get().strip()
        previous_key = load_api_key()
        rules = self._rules_box.get("1.0", "end").strip()
        if len(rules) > MAX_CUSTOM_RULES_CHARS:
            self._show_save_error(
                f"Override rules are too long (maximum {MAX_CUSTOM_RULES_CHARS:,} characters)."
            )
            return

        new_cfg = dict(self._app.cfg)
        new_cfg["model"] = self._model_var.get()
        hk = self._pending_hotkey.strip().lower()
        if hk:
            new_cfg["hotkey"] = hk
        new_cfg["source_lang"] = self._src_var.get()
        new_cfg["target_lang"] = self._tgt_var.get()
        new_cfg["game"] = self._game_var.get()
        new_cfg["tone"] = self._tone_var.get()
        new_cfg["custom_rules"] = rules
        new_cfg["history_enabled"] = bool(self._history_enabled_var.get())
        new_cfg["performance_cache_enabled"] = bool(self._cache_enabled_var.get())
        new_cfg["chat_context_enabled"] = bool(self._chat_context_enabled_var.get())

        key_changed = k != previous_key
        if key_changed and not save_api_key(k):
            self._show_save_error("Could not securely save the API key. Nothing was changed.")
            return
        if not save_config(new_cfg):
            rollback_ok = not key_changed or save_api_key(previous_key)
            suffix = "" if rollback_ok else " The previous API key could not be restored."
            self._show_save_error("Could not save settings. Nothing was applied." + suffix)
            return

        # Persistence succeeded. Cancel every in-flight request before closing
        # or replacing the translator's HTTP client/model configuration.
        cancel_all = getattr(self._app, "cancel_all_translations", None)
        if callable(cancel_all):
            cancel_all("Settings changed — translation cancelled")
        else:
            self._app.cancel_active_translation("Settings changed — translation cancelled")
            popup_cancel = getattr(self._app, "_popup_cancel", None)
            if popup_cancel is not None:
                popup_cancel.set()

        self._app.cfg.clear()
        self._app.cfg.update(new_cfg)
        if key_changed:
            self._app.translator.configure_api_key(k)
        self._app.translator.set_model(
            MODEL_OPTIONS.get(new_cfg["model"], OPENROUTER_MODEL)
        )
        if not new_cfg["performance_cache_enabled"]:
            self._app.translator.clear_cache()

        # Start-with-Windows switch (HKCU Run registry value)
        autostart_ok = set_autostart(bool(self._autostart_var.get()))

        # Language/model may have changed — old session context would mislead
        # the model (turns in the wrong language), so start fresh.
        self._app.reset_session()

        # Update main UI subtitle to reflect language
        if hasattr(self._app, '_lang_label'):
            self._app._lang_label.configure(
                text="{src} → {tgt}".format(src=self._src_var.get(), tgt=self._tgt_var.get())
            )
        if hasattr(self._app, '_hotkey_label'):
            self._app._hotkey_label.configure(text=self._app.cfg["hotkey"].upper())
        # Update dynamic input/output labels
        if hasattr(self._app, '_input_label'):
            self._app._input_label.configure(
                text="INPUT — {src}".format(src=self._src_var.get())
            )
        if hasattr(self._app, '_output_label'):
            self._app._output_label.configure(
                text="OUTPUT — {tgt}".format(tgt=self._tgt_var.get())
            )
        if hasattr(self._app, 'inp'):
            placeholder, justify = self._app._source_input_options()
            self._app.inp.configure(placeholder_text=placeholder, justify=justify)

        if self._app.translator.ready():
            self._app._check_api()
        elif hasattr(self._app, "stat"):
            self._app._api_ok(False, "No API key")
        if not autostart_ok and hasattr(self._app, "stat"):
            self._app._status("⚠️ Could not update Windows startup setting", C.WARN)

        logger.info("Settings saved. {src} → {tgt}".format(src=self._src_var.get(), tgt=self._tgt_var.get()))
        self._close()

    def _close(self):
        # register() tears down any previous registration itself
        self._app._register_hotkey(self._app.cfg.get("hotkey", "ctrl+shift+t"))
        if self._dialog.winfo_exists():
            self._dialog.destroy()
