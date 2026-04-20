"""
Translation Bridge v8.0
Multi-language translator via OpenRouter (Grok 4.1 Fast)

Main Application — ties together all modules.
"""

import ctypes
import logging
import os
import sys
import threading
import time

import customtkinter as ctk
import pyperclip

from .config import (
    load_api_key, load_config, save_config,
    load_history, add_history_entry,
    LOGO_FILE, ICON_FILE, ASSETS_DIR,
)
from .constants import (
    DEFAULT_HOTKEY, MODE_COPY, MODE_PASTE, MODE_SEND,
    WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_OPACITY, MAX_HISTORY_ITEMS,
    DEFAULT_SOURCE, DEFAULT_TARGET,
)
from .translator import Translator
from .hotkey import NativeHotkey
from .tray import TrayManager
from .ui.theme import C
from .ui.setup_screen import SetupScreen
from .ui.settings import SettingsDialog
from .ui.toast import Toast
from .ui.history import HistoryPanel

logger = logging.getLogger(__name__)

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

user32 = ctypes.windll.user32


# ─────────────────────────────────────────────────────────────
# WIN32 HELPERS
# ─────────────────────────────────────────────────────────────

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]


def _get_monitor_from_point(x, y):
    pt = POINT(x, y)
    hmon = user32.MonitorFromPoint(pt, 2)  # MONITOR_DEFAULTTONEAREST
    if hmon:
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            return mi.rcMonitor.left, mi.rcMonitor.top, mi.rcMonitor.right, mi.rcMonitor.bottom
    return None


# ─────────────────────────────────────────────────────────────
# APPLICATION
# ─────────────────────────────────────────────────────────────

class App(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.translator = Translator()
        self.is_busy = False
        self.cfg = load_config()
        self.send_mode = ctk.StringVar(value=self.cfg.get("mode", MODE_SEND))
        self._timer_id = None
        self._last_hwnd = None
        self._t0 = 0
        self._hotkey_popup = None
        self._history = load_history()
        self._history_panel = HistoryPanel(self)

        # Hotkey & Tray
        self._hotkey = NativeHotkey()
        self._tray = TrayManager(
            on_restore=lambda: self.after(0, self._show_window),
            on_quit=lambda: self.after(0, self.destroy),
        )

        self._setup_window()

        key = load_api_key()
        if key:
            self.translator._init(key)
            self._build_main()
            self._check_api()
        else:
            SetupScreen(self).build()

        self._poll_window()
        self._hotkey.register(
            self.cfg.get("hotkey", DEFAULT_HOTKEY),
            lambda: self.after(0, self._show_quick_popup)
        )

        self.protocol("WM_DELETE_WINDOW", self._hide_window)
        logger.info("Application initialized.")

    def destroy(self):
        self._hotkey.unregister()
        self._tray.stop()
        super().destroy()

    # ── SYSTEM TRAY ──

    def _hide_window(self):
        self.withdraw()
        self._tray.show()

    def _show_window(self):
        self.deiconify()
        self.attributes("-topmost", True)

    # ── WINDOW ──

    def _setup_window(self):
        self.title("Translation Bridge")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.attributes("-alpha", WINDOW_OPACITY)
        self.configure(fg_color=C.BG)

        if HAS_PIL and os.path.exists(LOGO_FILE):
            try:
                os.makedirs(ASSETS_DIR, exist_ok=True)
                img = Image.open(LOGO_FILE).resize((64, 64), Image.LANCZOS)
                img.save(ICON_FILE, format="ICO", sizes=[(64, 64)])
                self.iconbitmap(ICON_FILE)
            except Exception as e:
                logger.warning(f"Failed to set window icon: {e}")

        self.update_idletasks()
        x = self.winfo_screenwidth() - WINDOW_WIDTH - 20
        self.geometry(f"+{x}+{40}")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

    def _poll_window(self):
        try:
            h = user32.GetForegroundWindow()
            if h:
                buf = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(h, buf, 256)
                t = buf.value
                if "Translation Bridge" not in t and "Quick Translate" not in t and t:
                    self._last_hwnd = h
        except Exception:
            pass
        self.after(500, self._poll_window)

    def _load_logo(self, size=(64, 64)):
        if HAS_PIL and os.path.exists(LOGO_FILE):
            try:
                img = Image.open(LOGO_FILE)
                return ctk.CTkImage(light_image=img, dark_image=img, size=size)
            except Exception as e:
                logger.warning(f"Failed to load logo: {e}")
        return None

    # ── QUICK POPUP (Hotkey) ──

    def _show_quick_popup(self):
        if self._hotkey_popup and self._hotkey_popup.winfo_exists():
            self._hotkey_popup.destroy()
            self._hotkey_popup = None
            return

        p = ctk.CTkToplevel(self)
        p.title("Quick Translate")
        p.geometry("420x60")
        p.resizable(False, False)
        p.attributes("-topmost", True)
        p.overrideredirect(True)
        p.configure(fg_color=C.BG_CARD)
        self._hotkey_popup = p

        # Position on the monitor where the mouse is
        p.update_idletasks()
        mx = self.winfo_pointerx()
        my = self.winfo_pointery()
        mon_rect = _get_monitor_from_point(mx, my)
        if mon_rect:
            m_left, m_top, m_right, m_bottom = mon_rect
            x = m_left + ((m_right - m_left) - 420) // 2
            y = m_bottom - 120
        else:
            x = mx - 210
            y = my - 100
        p.geometry(f"+{x}+{y}")

        # Border effect
        border = ctk.CTkFrame(p, fg_color=C.PRIMARY, corner_radius=12)
        border.pack(fill="both", expand=True, padx=1, pady=1)
        inner = ctk.CTkFrame(border, fg_color=C.BG_CARD, corner_radius=11)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        logo = self._load_logo(size=(28, 28))
        if logo:
            ctk.CTkLabel(inner, text="", image=logo).pack(side="left", padx=(10, 4), pady=8)

        entry = ctk.CTkEntry(
            inner, placeholder_text="...اكتب عربي واضغط Enter",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            height=36, corner_radius=8,
            border_color=C.PRIMARY, border_width=2,
            fg_color=C.BG_INPUT, text_color=C.TEXT,
            justify="right",
        )
        entry.pack(side="left", fill="x", expand=True, padx=4, pady=8)

        p.focus_force()
        entry.focus_force()
        p.after(10, entry.focus_force)
        p.after(50, entry.focus_force)

        status_lbl = ctk.CTkLabel(
            inner, text="", font=ctk.CTkFont(size=10), text_color=C.ACCENT,
        )

        def _close(e=None):
            if p.winfo_exists():
                p.destroy()
            self._hotkey_popup = None

        def _go(e=None):
            txt = entry.get().strip()
            if not txt:
                _close()
                return
            entry.configure(state="disabled")
            status_lbl.pack(side="right", padx=(0, 10))
            status_lbl.configure(text="⏳")

            def _handle_error(msg):
                if p.winfo_exists():
                    status_lbl.configure(text=f"❌ {msg}", text_color=C.ERROR)
                    p.after(2000, _close)
                Toast.show(self, f"Translation failed: {msg}", style="error")

            original_text = txt

            def _do():
                def on_done(result):
                    self._safe_copy(result)
                    # Save to history
                    self._history = add_history_entry(
                        original_text, result, self._history, MAX_HISTORY_ITEMS
                    )
                    self.after(0, _paste_and_close, result)

                def on_error(msg):
                    self.after(0, lambda: _handle_error(msg))

                self.translator.stream(
                    txt,
                    custom_rules=self.cfg.get("custom_rules", ""),
                    game_mode=self.cfg.get("game", "General"),
                    ai_tone=self.cfg.get("tone", "Gamer (Default)"),
                    source_key=self.cfg.get("source_lang", DEFAULT_SOURCE),
                    target_key=self.cfg.get("target_lang", DEFAULT_TARGET),
                    on_done=on_done, on_error=on_error
                )

            threading.Thread(target=_do, daemon=True).start()

        def _paste_and_close(result):
            mode = self.send_mode.get()
            if not p.winfo_exists():
                # Still show toast even if popup already closed
                Toast.show(self, f"✅ {result[:40]}", style="success")
                return
            p.destroy()
            self._hotkey_popup = None

            if mode == MODE_COPY:
                # Return focus to the previously active window
                if self._last_hwnd and user32.IsWindow(self._last_hwnd):
                    user32.SetForegroundWindow(self._last_hwnd)
                Toast.show(self, "Copied to clipboard ✅", style="success")
                return

            def _do_paste_send():
                time.sleep(0.1)
                self._release_all_modifiers()
                time.sleep(0.05)
                self._kb_ctrl_v()
                if mode == MODE_SEND:
                    time.sleep(0.08)
                    self._kb_enter()
                # Show toast after paste/send
                self.after(0, lambda: Toast.show(self, "Sent ✅", style="success"))

            threading.Thread(target=_do_paste_send, daemon=True).start()

        entry.bind("<Return>", _go)
        entry.bind("<Escape>", _close)
        p.bind("<FocusOut>", lambda e: None)

    # ═══════════════════════════════════════════════════════════
    # MAIN UI
    # ═══════════════════════════════════════════════════════════

    def _build_main(self):
        m = ctk.CTkFrame(self, fg_color="transparent")
        m.pack(fill="both", expand=True, padx=24, pady=24)
        self.main = m

        # ── HEADER ──
        hdr = ctk.CTkFrame(m, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 20))

        logo = self._load_logo(size=(42, 42))
        if logo:
            ctk.CTkLabel(hdr, text="", image=logo).pack(side="left", padx=(0, 12))

        title_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        title_frame.pack(side="left", fill="y")
        ctk.CTkLabel(
            title_frame, text="Translation Bridge",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=C.ACCENT,
        ).pack(anchor="w")
        src = self.cfg.get("source_lang", DEFAULT_SOURCE)
        tgt = self.cfg.get("target_lang", DEFAULT_TARGET)
        self._lang_label = ctk.CTkLabel(
            title_frame, text=f"{src} → {tgt}",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C.TEXT_DIM,
        )
        self._lang_label.pack(anchor="w", pady=(0, 0))

        # Header buttons
        btn_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_frame.pack(side="right")

        ctk.CTkButton(
            btn_frame, text="📜", width=40, height=40, corner_radius=9999,
            font=ctk.CTkFont(size=16), fg_color=C.BG_CARD,
            hover_color=C.BORDER, text_color=C.TEXT,
            border_width=1, border_color=C.BORDER,
            command=self._history_panel.toggle,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_frame, text="SETTINGS", width=40, height=40, corner_radius=9999,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=C.BG_CARD, hover_color=C.BORDER, text_color=C.TEXT,
            border_width=1, border_color=C.BORDER,
            command=lambda: SettingsDialog(self).show(),
        ).pack(side="left")

        # ── MAIN CARD ──
        card = ctk.CTkFrame(m, fg_color=C.BG_CARD, corner_radius=16,
                             border_width=1, border_color=C.BORDER)
        card.pack(fill="both", expand=True, pady=(0, 20))

        # ── INPUT ──
        src = self.cfg.get("source_lang", DEFAULT_SOURCE)
        self._input_label = ctk.CTkLabel(
            card, text=f"INPUT — {src}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=C.TEXT_DIM,
        )
        self._input_label.pack(anchor="w", padx=20, pady=(20, 8))

        irow = ctk.CTkFrame(card, fg_color="transparent")
        irow.pack(fill="x", padx=20, pady=(0, 16))

        self.inp = ctk.CTkEntry(
            irow, placeholder_text="اكتب جملتك هنا...",
            font=ctk.CTkFont(family="Segoe UI", size=16),
            height=54, corner_radius=12,
            border_color=C.BORDER, border_width=1,
            fg_color=C.BG_INPUT, text_color=C.TEXT, justify="right",
        )
        self.inp.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.inp.bind("<Return>", lambda e: self._translate())

        ctk.CTkButton(
            irow, text="PASTE", width=54, height=54, corner_radius=12,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=C.BG_INPUT, hover_color=C.PRIMARY,
            border_color=C.BORDER, border_width=1, text_color=C.TEXT,
            command=self._paste_translate,
        ).pack(side="right")

        self.tr_btn = ctk.CTkButton(
            card, text="TRANSLATE",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            height=50, corner_radius=9999,
            fg_color=C.PRIMARY, hover_color=C.PRIMARY_H,
            text_color=C.BG, command=self._translate,
        )
        self.tr_btn.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkFrame(card, height=1, fg_color=C.BORDER).pack(fill="x")

        # ── PREVIEW ──
        tgt = self.cfg.get("target_lang", DEFAULT_TARGET)
        self._output_label = ctk.CTkLabel(
            card, text=f"OUTPUT — {tgt}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=C.TEXT_DIM,
        )
        self._output_label.pack(anchor="w", padx=20, pady=(16, 8))

        self.preview = ctk.CTkTextbox(
            card, height=90, font=ctk.CTkFont(family="Segoe UI", size=15),
            corner_radius=12, fg_color=C.BG_INPUT, text_color=C.ACCENT,
            border_color=C.BORDER, border_width=1,
            state="disabled", wrap="word",
        )
        self.preview.pack(fill="x", padx=20, pady=(0, 20))

        # Clipboard confirmation label
        self.cp_lbl = ctk.CTkLabel(
            card, text="", font=ctk.CTkFont(size=10), text_color=C.SUCCESS,
        )
        self.cp_lbl.pack(anchor="w", padx=20, pady=(0, 4))

        # ── SEND MODE & MANUAL SEND ──
        mode_frame = ctk.CTkFrame(m, fg_color="transparent")
        mode_frame.pack(fill="x")

        ctk.CTkLabel(
            mode_frame, text="AUTO ACTION",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=C.TEXT_DIM,
        ).pack(anchor="w", pady=(0, 8))

        self.mode_map = ["copy", "paste", "paste_send"]
        self.seg_btn = ctk.CTkSegmentedButton(
            mode_frame, values=["Copy", "Paste", "Send"],
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=40, corner_radius=9999,
            fg_color=C.BG_CARD, selected_color=C.PRIMARY,
            selected_hover_color=C.PRIMARY_H,
            unselected_color=C.BG_CARD, unselected_hover_color=C.BG_INPUT,
            command=self._seg_changed,
        )
        self.seg_btn.pack(fill="x", pady=(0, 16))

        try:
            init_idx = self.mode_map.index(self.cfg.get("mode", MODE_SEND))
            self.seg_btn.set(["Copy", "Paste", "Send"][init_idx])
        except Exception:
            self.seg_btn.set("Send")

        self.send_btn = ctk.CTkButton(
            m, text="COPY & PASTE TO GAME",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            height=46, corner_radius=9999,
            fg_color=C.BG_INPUT, hover_color=C.PRIMARY,
            border_color=C.BORDER, border_width=1,
            text_color=C.TEXT, command=self._manual_send, state="disabled",
        )
        self.send_btn.pack(fill="x", pady=(0, 16))

        # ── STATUS BAR ──
        self.stat = ctk.CTkLabel(
            m, text=f"Ready • Hotkey: {self.cfg.get('hotkey', DEFAULT_HOTKEY).upper()}",
            font=ctk.CTkFont(family="Source Code Pro", size=11),
            text_color=C.TEXT_DIM,
        )
        self.stat.pack(anchor="center")

    def _seg_changed(self, value):
        idx = ["Copy", "Paste", "Send"].index(value)
        self.send_mode.set(self.mode_map[idx])
        self.cfg["mode"] = self.send_mode.get()
        save_config(self.cfg)

    # ── API CHECK ──

    def _check_api(self):
        self.stat.configure(text="🟡 Testing Connection...", text_color=C.WARN)

        def _c():
            ok, msg = self.translator.test()
            self.after(0, self._api_ok, ok, msg)

        threading.Thread(target=_c, daemon=True).start()

    def _api_ok(self, ok, msg):
        hk = self.cfg.get('hotkey', DEFAULT_HOTKEY).upper()
        if ok:
            self.stat.configure(text=f"🟢 Ready • Hotkey: {hk}", text_color=C.TEXT_DIM)
        else:
            self.stat.configure(text=msg, text_color=C.ERROR)

    # ── PASTE + TRANSLATE ──

    def _paste_translate(self):
        try:
            t = pyperclip.paste()
            if t and t.strip():
                self.inp.delete(0, "end")
                self.inp.insert(0, t.strip())
                self._translate()
            else:
                self._status("⚠️ Clipboard empty", C.WARN)
        except Exception as e:
            logger.warning(f"Failed to paste: {e}")
            self._status("⚠️ Can't read clipboard", C.WARN)

    # ── TRANSLATE ──

    def _translate(self):
        if self.is_busy:
            return
        text = self.inp.get().strip()
        if not text:
            self._status("⚠️ Type something", C.WARN)
            return
        self.is_busy = True
        self.tr_btn.configure(state="disabled", text="⏳ Translating...")
        self.send_btn.configure(state="disabled")
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.configure(state="disabled")
        self._t0 = time.time()
        self._tick()

        original_text = text
        threading.Thread(target=self._do_tr, args=(text, original_text), daemon=True).start()

    def _tick(self):
        if not self.is_busy:
            return
        self._status(f"⏳ Translating... ({time.time()-self._t0:.1f}s)", C.ACCENT)
        self._timer_id = self.after(200, self._tick)

    def _stop_tick(self):
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None

    def _do_tr(self, text, original_text):
        self.translator.stream(
            text,
            custom_rules=self.cfg.get("custom_rules", ""),
            game_mode=self.cfg.get("game", "General"),
            ai_tone=self.cfg.get("tone", "Gamer (Default)"),
            source_key=self.cfg.get("source_lang", DEFAULT_SOURCE),
            target_key=self.cfg.get("target_lang", DEFAULT_TARGET),
            on_token=lambda t: self.after(0, self._add_tok, t),
            on_done=lambda r: self.after(0, self._done, r, original_text),
            on_error=lambda e: self.after(0, self._fail, e),
        )

    def _add_tok(self, t):
        self.preview.configure(state="normal")
        self.preview.insert("end", t)
        self.preview.see("end")
        self.preview.configure(state="disabled")

    def _done(self, result, original_text=""):
        self._stop_tick()
        self.is_busy = False
        self.tr_btn.configure(state="normal", text="🔄  Translate")
        elapsed = time.time() - self._t0

        if result.startswith("["):
            self._status(f"❌ {result}", C.ERROR)
            return

        self._show_preview(result)
        self._safe_copy(result)
        self.send_btn.configure(state="normal")

        # Save to history
        if original_text:
            self._history = add_history_entry(
                original_text, result, self._history, MAX_HISTORY_ITEMS
            )

        mode = self.send_mode.get()
        if mode == MODE_COPY:
            self._status(f"✅ Done ({elapsed:.1f}s) — clipboard", C.SUCCESS)
        elif mode == MODE_PASTE:
            self._status(f"✅ Done ({elapsed:.1f}s) — pasting...", C.SUCCESS)
            self.iconify()
            self.update()
            threading.Thread(target=self._do_paste, args=(result, False), daemon=True).start()
        elif mode == MODE_SEND:
            self._status(f"✅ Done ({elapsed:.1f}s) — sending...", C.SUCCESS)
            self.iconify()
            self.update()
            threading.Thread(target=self._do_paste, args=(result, True), daemon=True).start()

    def _fail(self, msg):
        self._stop_tick()
        self.is_busy = False
        self.tr_btn.configure(state="normal", text="🔄  Translate")
        self._status(f"❌ {msg}", C.ERROR)
        self._show_preview(f"[{msg}]")

    # ── AUTO-PASTE ──

    def _do_paste(self, text, enter):
        time.sleep(0.05)
        self._switch_win()
        time.sleep(0.12)
        self._release_all_modifiers()
        time.sleep(0.03)
        self._safe_copy(text)
        self._kb_ctrl_v()
        if enter:
            time.sleep(0.05)
            self._kb_enter()
        time.sleep(0.05)
        self.after(0, self._restore)

    def _switch_win(self):
        ok = False
        k32 = ctypes.windll.kernel32
        if self._last_hwnd:
            try:
                if user32.IsWindow(self._last_hwnd):
                    if user32.IsIconic(self._last_hwnd):
                        user32.ShowWindow(self._last_hwnd, 9)
                        time.sleep(0.1)
                    tt = user32.GetWindowThreadProcessId(self._last_hwnd, None)
                    ct = k32.GetCurrentThreadId()
                    user32.AttachThreadInput(ct, tt, True)
                    try:
                        user32.BringWindowToTop(self._last_hwnd)
                        user32.SetForegroundWindow(self._last_hwnd)
                    finally:
                        user32.AttachThreadInput(ct, tt, False)
                    time.sleep(0.1)
                    if user32.GetForegroundWindow() == self._last_hwnd:
                        ok = True
            except Exception as e:
                logger.warning(f"Failed to switch to target window: {e}")

        if not ok:
            UP = 0x0002
            EXT = 0x0001
            try:
                user32.keybd_event(0x12, 0, EXT, 0)
                user32.keybd_event(0x09, 0, 0, 0)
                time.sleep(0.05)
                user32.keybd_event(0x09, 0, UP, 0)
                user32.keybd_event(0x12, 0, UP | EXT, 0)
            except Exception as e:
                logger.warning(f"Alt-Tab fallback failed: {e}")
            finally:
                user32.keybd_event(0x12, 0, UP | EXT, 0)
            time.sleep(0.5)

    def _restore(self):
        self.deiconify()
        self.attributes("-topmost", True)
        m = self.send_mode.get()
        self._status("✅ Sent!" if m == MODE_SEND else "✅ Pasted!", C.SUCCESS)
        self.inp.delete(0, "end")
        self.cp_lbl.configure(text="")
        self.send_btn.configure(state="disabled")
        self.inp.focus_set()

    # ── MANUAL SEND ──

    def _manual_send(self):
        text = self.preview.get("1.0", "end").strip()
        if not text:
            return
        enter = self.send_mode.get() == MODE_SEND
        self.send_btn.configure(state="disabled", text="⏳...")
        self._status("🔴 Switch to chat... 2s", C.ERROR)
        self.iconify()
        self.update()

        def _s():
            time.sleep(0.3)
            self._switch_win()
            time.sleep(1.5)
            self._release_all_modifiers()
            time.sleep(0.05)
            self._safe_copy(text)
            self._kb_ctrl_v()
            if enter:
                time.sleep(0.2)
                self._kb_enter()
            time.sleep(0.4)
            self.after(0, self._manual_done)

        threading.Thread(target=_s, daemon=True).start()

    def _manual_done(self):
        self.deiconify()
        self.attributes("-topmost", True)
        self.send_btn.configure(state="normal", text="📋  Copy & Paste to Chat")
        self._status("✅ Done!", C.SUCCESS)
        self.inp.delete(0, "end")
        self.cp_lbl.configure(text="")
        self.send_btn.configure(state="disabled")
        self.inp.focus_set()

    # ── HELPERS ──

    def _show_preview(self, t):
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", t)
        self.preview.configure(state="disabled")

    def _status(self, msg, color=C.TEXT_DIM):
        self.stat.configure(text=msg, text_color=color)

    @staticmethod
    def _release_all_modifiers():
        """Force-release all modifier keys to prevent stuck keys."""
        UP = 0x0002
        EXT = 0x0001
        user32.keybd_event(0x10, 0, UP, 0)          # Shift
        user32.keybd_event(0x11, 0, UP, 0)          # Ctrl
        user32.keybd_event(0x12, 0, UP | EXT, 0)    # Alt
        user32.keybd_event(0xA0, 0, UP, 0)          # LShift
        user32.keybd_event(0xA1, 0, UP, 0)          # RShift
        user32.keybd_event(0xA2, 0, UP, 0)          # LCtrl
        user32.keybd_event(0xA3, 0, UP, 0)          # RCtrl
        user32.keybd_event(0xA4, 0, UP | EXT, 0)    # LAlt
        user32.keybd_event(0xA5, 0, UP | EXT, 0)    # RAlt
        user32.keybd_event(0x5B, 0, UP | EXT, 0)    # LWin
        user32.keybd_event(0x5C, 0, UP | EXT, 0)    # RWin

    @staticmethod
    def _safe_copy(text):
        """Safely copy text to clipboard, retrying if locked."""
        for _ in range(3):
            try:
                pyperclip.copy(text)
                return True
            except Exception as e:
                logger.warning(f"Clipboard locked, retrying: {e}")
                time.sleep(0.1)
        logger.error("Failed to copy to clipboard after 3 retries.")
        return False

    @staticmethod
    def _kb_ctrl_v():
        UP = 0x0002
        try:
            user32.keybd_event(0x11, 0, 0, 0)
            user32.keybd_event(0x56, 0, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(0x56, 0, UP, 0)
        finally:
            user32.keybd_event(0x11, 0, UP, 0)

    @staticmethod
    def _kb_enter():
        UP = 0x0002
        user32.keybd_event(0x0D, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(0x0D, 0, UP, 0)
