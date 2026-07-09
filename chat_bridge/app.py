"""
Translation Bridge v8.4
Multi-language translator via OpenRouter (selectable model)

Main Application — ties together all modules.
"""

import ctypes
import logging
import os
import queue
import sys
import threading
import time
from dataclasses import dataclass

import customtkinter as ctk
import pyperclip

from .config import (
    load_api_key, load_config, save_config,
    load_history, add_history_entry,
    LOGO_FILE, ICON_FILE, ASSETS_DIR,
)
from .constants import (
    DEFAULT_HOTKEY, MODE_COPY, MODE_PASTE, MODE_SEND,
    WINDOW_WIDTH, WINDOW_HEIGHT, MAX_HISTORY_ITEMS,
    DEFAULT_SOURCE, DEFAULT_TARGET,
    MODEL_OPTIONS, OPENROUTER_MODEL, DEFAULT_MODEL_LABEL,
    CONTEXT_MAX_EXCHANGES, CONTEXT_IDLE_MINUTES, CONTEXT_MAX_CHARS,
    MAX_INPUT_CHARS, SOURCE_LANGUAGES,
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


@dataclass(frozen=True)
class TranslationRequest:
    """Everything a background translation needs, frozen at submit time."""

    request_id: int
    text: str
    source_text: str
    custom_rules: str
    game_mode: str
    ai_tone: str
    source_key: str
    target_key: str
    context: tuple[tuple[str, str], ...]
    mode: str
    target_hwnd: int | None
    history_enabled: bool
    cache_enabled: bool
    cancel: threading.Event


def _monitor_rect_from_handle(hmon):
    if hmon:
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            return mi.rcMonitor.left, mi.rcMonitor.top, mi.rcMonitor.right, mi.rcMonitor.bottom
    return None


def _get_monitor_from_point(x, y):
    pt = POINT(x, y)
    return _monitor_rect_from_handle(user32.MonitorFromPoint(pt, 2))  # DEFAULTTONEAREST


def _get_monitor_from_window(hwnd):
    """Monitor rect of the window the user was just in (the game)."""
    if hwnd and user32.IsWindow(hwnd):
        return _monitor_rect_from_handle(user32.MonitorFromWindow(hwnd, 2))  # DEFAULTTONEAREST
    return None


# ─────────────────────────────────────────────────────────────
# APPLICATION
# ─────────────────────────────────────────────────────────────

class App(ctk.CTk):

    def __init__(self):
        super().__init__()
        self._ui_events = queue.Queue()
        self._closing = False
        self._main_cancel = None
        self._request_sequence = 0
        self._active_request_id = 0
        self.translator = Translator()
        self.is_busy = False
        self.cfg = load_config()
        # Model labels change across versions — a stale label in config would
        # show as an out-of-list entry in Settings while silently falling back.
        if self.cfg.get("model") not in MODEL_OPTIONS:
            self.cfg["model"] = DEFAULT_MODEL_LABEL
        self.translator.set_model(
            MODEL_OPTIONS.get(self.cfg.get("model", DEFAULT_MODEL_LABEL), OPENROUTER_MODEL)
        )
        self.send_mode = ctk.StringVar(value=self.cfg.get("mode", MODE_COPY))
        self._timer_id = None
        self._last_hwnd = None
        self._t0 = 0
        self._hotkey_popup = None
        self._popup_cancel = None
        self._history = load_history()
        self._history_panel = HistoryPanel(self)
        # In-game session memory: recent (source, translation) pairs sent as context
        self._session_pairs = []
        self._session_ts = 0.0

        # Hotkey & Tray
        self._hotkey = NativeHotkey()
        self._tray = TrayManager(
            on_restore=lambda: self._post_ui(self._show_window),
            on_quit=lambda: self._post_ui(self.destroy),
        )

        self._setup_window()

        key = load_api_key()
        if key:
            self.translator.configure_api_key(key)
            self._build_main()
            self._check_api()
        else:
            SetupScreen(self).build()

        self._poll_window()
        self.after(25, self._drain_ui_events)
        self._register_hotkey(self.cfg.get("hotkey", DEFAULT_HOTKEY))

        self.protocol("WM_DELETE_WINDOW", self._hide_window)

        # Launched by Windows autostart: start hidden in the tray, not as a
        # window popping over whatever the user is doing at login.
        if "--tray" in sys.argv:
            self.after(300, self._hide_window)

        logger.info("Application initialized.")

    def destroy(self):
        if self._closing:
            return
        self._closing = True
        if self._main_cancel is not None:
            self._main_cancel.set()
        if self._popup_cancel is not None:
            self._popup_cancel.set()
        self._hotkey.unregister()
        self._tray.stop()
        self.translator.close()
        super().destroy()

    def _post_ui(self, callback, *args):
        """Safely transfer a worker result to Tk's main thread."""
        if not self._closing:
            self._ui_events.put((callback, args))

    def _drain_ui_events(self):
        """Run all queued worker results from the Tk event loop only."""
        if self._closing:
            return
        while True:
            try:
                callback, args = self._ui_events.get_nowait()
            except queue.Empty:
                break
            try:
                callback(*args)
            except Exception:
                logger.exception("Unhandled UI event")
        if not self._closing:
            self.after(25, self._drain_ui_events)

    # ── SYSTEM TRAY ──

    def _hide_window(self):
        self.withdraw()
        self._tray.show()

    def _show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    # ── HOTKEY ──

    def _register_hotkey(self, hk_str: str):
        """Single place that binds the global hotkey and surfaces failures in the UI."""
        self._hotkey.register(
            hk_str,
            lambda: self._post_ui(self._show_quick_popup),
            on_fail=lambda msg: self._post_ui(self._hotkey_failed, msg),
        )

    def _hotkey_failed(self, msg: str):
        """Registration failed — tell the user instead of failing silently."""
        Toast.show(self, f"Hotkey failed: {msg}", style="error")
        if hasattr(self, "stat"):
            self._status("Hotkey inactive — set a new one in Settings", C.ERROR)

    # ── WINDOW ──

    def _setup_window(self):
        self.title("Translation Bridge")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.resizable(False, False)
        # NOTE: the main window is deliberately NOT topmost and NOT layered (-alpha).
        # A persistent always-on-top, semi-transparent window forces fullscreen games
        # out of exclusive mode into composited rendering, which drops FPS. The only
        # surface that goes over the game is the transient quick-popup (Ctrl+Shift+T),
        # which destroys itself the moment you're done.
        self.configure(fg_color=C.BG)

        if HAS_PIL and os.path.exists(LOGO_FILE):
            try:
                # Regenerate the .ico only when missing or older than the logo —
                # not on every launch.
                if (not os.path.exists(ICON_FILE)
                        or os.path.getmtime(ICON_FILE) < os.path.getmtime(LOGO_FILE)):
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
                if t and not self._is_own_window(h):
                    self._last_hwnd = h
        except Exception:
            pass
        if not self._closing:
            self.after(500, self._poll_window)

    @staticmethod
    def _is_own_window(hwnd) -> bool:
        """True for any window belonging to this process, including dialogs."""
        if not hwnd or not user32.IsWindow(hwnd):
            return False
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value == os.getpid()

    def _load_logo(self, size=(64, 64)):
        if HAS_PIL and os.path.exists(LOGO_FILE):
            try:
                img = Image.open(LOGO_FILE)
                return ctk.CTkImage(light_image=img, dark_image=img, size=size)
            except Exception as e:
                logger.warning(f"Failed to load logo: {e}")
        return None

    def _source_input_options(self):
        """Return the right placeholder and direction for the selected source."""
        source_key = self.cfg.get("source_lang", DEFAULT_SOURCE)
        info = SOURCE_LANGUAGES.get(source_key)
        placeholder = info[1] if info else "Type your message..."
        return placeholder, "right" if "العربية" in source_key else "left"

    # ── QUICK POPUP (Hotkey) ──

    def _show_quick_popup(self):
        if self._hotkey_popup and self._hotkey_popup.winfo_exists():
            # Toggling the popup away also aborts any in-flight translation
            if self._popup_cancel is not None:
                self._popup_cancel.set()
            self._hotkey_popup.destroy()
            self._hotkey_popup = None
            return

        # Fresh cancel token for this popup's lifetime
        self._popup_cancel = cancel_flag = threading.Event()
        # The hotkey was pressed while this was the active non-app window.
        # Keep that exact target; never infer a new target after translating.
        target_hwnd = self._last_hwnd

        # Warm the API connection while the user types (zero-token, best-effort)
        threading.Thread(target=self.translator.warm, daemon=True).start()

        p = ctk.CTkToplevel(self)
        p.title("Quick Translate")
        p.geometry("460x68")
        p.resizable(False, False)
        p.attributes("-topmost", True)
        p.overrideredirect(True)
        p.configure(fg_color=C.BG_CARD)
        self._hotkey_popup = p

        # Always appear at the SAME predictable spot — bottom-center of the monitor
        # the game is on — so it doesn't matter where the mouse is. Falls back to the
        # mouse's monitor, then the primary monitor.
        p.update_idletasks()
        mon_rect = (
            _get_monitor_from_window(target_hwnd)
            or _get_monitor_from_point(self.winfo_pointerx(), self.winfo_pointery())
        )
        if mon_rect:
            m_left, m_top, m_right, m_bottom = mon_rect
            x = m_left + ((m_right - m_left) - 460) // 2
            y = m_bottom - 140
        else:
            x = (self.winfo_screenwidth() - 460) // 2
            y = self.winfo_screenheight() - 140
        p.geometry(f"+{x}+{y}")

        # Border effect
        border = ctk.CTkFrame(p, fg_color=C.BORDER, corner_radius=10)
        border.pack(fill="both", expand=True, padx=1, pady=1)
        inner = ctk.CTkFrame(border, fg_color=C.BG_CARD, corner_radius=9)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        logo = self._load_logo(size=(30, 30))
        if logo:
            ctk.CTkLabel(inner, text="", image=logo).pack(side="left", padx=(10, 4), pady=8)

        placeholder, justify = self._source_input_options()
        entry = ctk.CTkEntry(
            inner, placeholder_text=placeholder,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            height=42, corner_radius=7,
            border_color=C.BORDER, border_width=1,
            fg_color=C.BG_INPUT, text_color=C.TEXT,
            justify=justify,
        )
        entry.pack(side="left", fill="x", expand=True, padx=4, pady=8)

        p.focus_force()
        entry.focus_force()
        p.after(10, entry.focus_force)
        p.after(50, entry.focus_force)

        status_lbl = ctk.CTkLabel(
            inner, text="", font=ctk.CTkFont(size=10), text_color=C.ACCENT,
        )

        busy = {"v": False}

        def _close(e=None):
            # Esc (or any close) aborts an in-flight translation: nothing gets
            # pasted, sent, copied, or saved after this point.
            cancel_flag.set()
            if p.winfo_exists():
                p.destroy()
            self._hotkey_popup = None

        def _go(e=None):
            if busy["v"]:
                return
            txt = entry.get().strip()
            if not txt:
                _close()
                return
            if len(txt) > MAX_INPUT_CHARS:
                status_lbl.pack(side="right", padx=(0, 10))
                status_lbl.configure(
                    text=f"❌ Text is too long (max {MAX_INPUT_CHARS} characters)",
                    text_color=C.ERROR,
                )
                p.after(2000, _close)
                Toast.show(self, f"Translation failed: text is too long", style="error")
                return
            busy["v"] = True
            entry.configure(state="disabled")
            status_lbl.pack(side="right", padx=(0, 10))
            status_lbl.configure(text="WORKING", text_color=C.ACCENT)

            def _handle_error(msg):
                if cancel_flag.is_set():
                    return
                if p.winfo_exists():
                    status_lbl.configure(text=f"❌ {msg}", text_color=C.ERROR)
                    p.after(2000, _close)
                Toast.show(self, f"Translation failed: {msg}", style="error")

            original_text = txt
            # Snapshot session context on the main thread (Tk event handler)
            ctx = tuple(self._session_context())
            request_cfg = {
                "custom_rules": self.cfg.get("custom_rules", ""),
                "game": self.cfg.get("game", "General"),
                "tone": self.cfg.get("tone", "Gamer (Default)"),
                "source_lang": self.cfg.get("source_lang", DEFAULT_SOURCE),
                "target_lang": self.cfg.get("target_lang", DEFAULT_TARGET),
                "history_enabled": self.cfg.get("history_enabled", False),
                "cache_enabled": self.cfg.get("performance_cache_enabled", True),
            }
            mode = self.send_mode.get()

            started = {"v": False}

            def _show_token(tok):
                # Live-stream the translation into the entry so the popup never
                # feels stuck — first token replaces the source text.
                if cancel_flag.is_set() or not p.winfo_exists():
                    return
                entry.configure(state="normal")
                if not started["v"]:
                    entry.delete(0, "end")
                    started["v"] = True
                entry.insert("end", tok)
                entry.configure(state="disabled")

            def _finish(result):
                if cancel_flag.is_set():
                    return
                if result.startswith("["):
                    _handle_error(result.strip("[]"))
                    return
                # Never paste after a clipboard failure: Ctrl+V might otherwise
                # send the user's previous, possibly sensitive clipboard value.
                if not self._safe_copy(result):
                    _handle_error("Could not copy translation to clipboard")
                    return
                if request_cfg["history_enabled"]:
                    self._history = add_history_entry(
                        original_text, result, self._history, MAX_HISTORY_ITEMS
                    )
                self._session_add(original_text, result)
                _paste_and_close(result, mode)

            def _do():
                def on_token(tok):
                    self._post_ui(_show_token, tok)

                def on_done(result):
                    self._post_ui(_finish, result)

                def on_error(msg):
                    self._post_ui(_handle_error, msg)

                self.translator.stream(
                    txt,
                    custom_rules=request_cfg["custom_rules"],
                    game_mode=request_cfg["game"],
                    ai_tone=request_cfg["tone"],
                    source_key=request_cfg["source_lang"],
                    target_key=request_cfg["target_lang"],
                    context=ctx, cancel=cancel_flag,
                    cache_enabled=bool(request_cfg["cache_enabled"]),
                    on_token=on_token, on_done=on_done, on_error=on_error
                )

            threading.Thread(target=_do, daemon=True).start()

        def _paste_and_close(result, mode):
            if not p.winfo_exists():
                # Closing the popup means the user cancelled the action.
                return
            p.destroy()
            self._hotkey_popup = None

            if mode == MODE_COPY:
                # Return focus to the previously active window
                self._focus_target_window(target_hwnd)
                Toast.show(self, "Copied to clipboard ✅", style="success")
                return

            def _do_paste_send():
                # Let the destroyed popup relinquish focus, then verify the exact
                # target captured when the hotkey was pressed before injecting keys.
                time.sleep(0.06)
                if not self._focus_target_window(target_hwnd):
                    self._post_ui(self._paste_failed, "Target window is no longer available")
                    return
                self._release_all_modifiers()
                time.sleep(0.03)
                self._kb_ctrl_v()
                if mode == MODE_SEND:
                    time.sleep(0.06)
                    self._kb_enter()
                label = "Sent ✅" if mode == MODE_SEND else "Pasted ✅"
                self._post_ui(Toast.show, self, label, "success")

            threading.Thread(target=_do_paste_send, daemon=True).start()

        entry.bind("<Return>", _go)
        entry.bind("<Escape>", _close)
        # Also on the toplevel: the entry is disabled while translating, so Esc
        # must still reach us to cancel.
        p.bind("<Escape>", _close)
        p.bind("<FocusOut>", lambda e: None)

    # ═══════════════════════════════════════════════════════════
    # MAIN UI
    # ═══════════════════════════════════════════════════════════

    def _build_main(self):
        page = ctk.CTkFrame(self, fg_color="transparent")
        page.pack(fill="both", expand=True, padx=18, pady=18)
        self.main = page

        shell = ctk.CTkFrame(
            page, fg_color=C.BG_CARD, corner_radius=20,
            border_width=1, border_color=C.BORDER,
        )
        shell.pack(fill="both", expand=True)

        # The rail contains the persistent controls. It keeps the work area calm
        # and makes the app feel like a focused tool rather than a busy dashboard.
        rail = ctk.CTkFrame(shell, width=210, fg_color=C.BG_RAISED, corner_radius=18)
        rail.pack(side="left", fill="y", padx=(1, 10), pady=1)
        rail.pack_propagate(False)

        brand = ctk.CTkFrame(rail, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(22, 18))
        logo = self._load_logo(size=(42, 42))
        if logo:
            ctk.CTkLabel(brand, text="", image=logo).pack(side="left", padx=(0, 10))
        brand_words = ctk.CTkFrame(brand, fg_color="transparent")
        brand_words.pack(side="left", fill="y")
        ctk.CTkLabel(
            brand_words, text="BRIDGE",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=C.TEXT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            brand_words, text="LIVE TRANSLATION",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=C.PRIMARY,
        ).pack(anchor="w", pady=(1, 0))

        ctk.CTkFrame(rail, height=1, fg_color=C.SEP).pack(fill="x", padx=20)
        ctk.CTkLabel(
            rail, text="AUTO ACTION",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=C.TEXT_DIM,
        ).pack(anchor="w", padx=20, pady=(22, 8))

        self.mode_map = [MODE_COPY, MODE_PASTE, MODE_SEND]
        self.seg_btn = ctk.CTkSegmentedButton(
            rail, values=["Copy", "Paste", "Send"],
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            height=34, corner_radius=7, fg_color=C.BG, selected_color=C.PRIMARY,
            selected_hover_color=C.PRIMARY_H, unselected_color=C.BG,
            unselected_hover_color=C.BG_CARD, text_color=C.TEXT,
            command=self._seg_changed,
        )
        self.seg_btn.pack(fill="x", padx=20)
        try:
            init_idx = self.mode_map.index(self.cfg.get("mode", MODE_COPY))
            self.seg_btn.set(["Copy", "Paste", "Send"][init_idx])
        except ValueError:
            self.seg_btn.set("Copy")

        initial_mode_notes = {
            MODE_COPY: "Copies the result only.",
            MODE_PASTE: "Pastes into the saved game window.",
            MODE_SEND: "Pastes and sends to the saved game window.",
        }
        self._mode_note = ctk.CTkLabel(
            rail, text=initial_mode_notes.get(self.send_mode.get(), "Copies the result only."),
            wraplength=166, justify="left",
            font=ctk.CTkFont(family="Segoe UI", size=10), text_color=C.TEXT_DIM,
        )
        self._mode_note.pack(anchor="w", padx=20, pady=(8, 22))

        quick = ctk.CTkFrame(
            rail, fg_color=C.BG, corner_radius=10, border_width=1, border_color=C.BORDER,
        )
        quick.pack(fill="x", padx=20)
        ctk.CTkLabel(
            quick, text="QUICK TRANSLATE",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"), text_color=C.TEXT_DIM,
        ).pack(anchor="w", padx=12, pady=(11, 2))
        self._hotkey_label = ctk.CTkLabel(
            quick, text=self.cfg.get("hotkey", DEFAULT_HOTKEY).upper(),
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=C.TEXT,
        )
        self._hotkey_label.pack(anchor="w", padx=12, pady=(0, 11))

        utility = ctk.CTkFrame(rail, fg_color="transparent")
        utility.pack(side="bottom", fill="x", padx=20, pady=20)
        ctk.CTkButton(
            utility, text="HISTORY", height=34, corner_radius=7,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color="transparent", hover_color=C.BG_CARD, text_color=C.TEXT_SOFT,
            border_width=1, border_color=C.BORDER, command=self._history_panel.toggle,
        ).pack(fill="x", pady=(0, 7))
        ctk.CTkButton(
            utility, text="SETTINGS", height=34, corner_radius=7,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color="transparent", hover_color=C.BG_CARD, text_color=C.TEXT_SOFT,
            border_width=1, border_color=C.BORDER, command=lambda: SettingsDialog(self).show(),
        ).pack(fill="x")

        work = ctk.CTkFrame(shell, fg_color="transparent")
        work.pack(side="left", fill="both", expand=True, padx=(14, 22), pady=22)

        top = ctk.CTkFrame(work, fg_color="transparent")
        top.pack(fill="x", pady=(0, 14))
        heading = ctk.CTkFrame(top, fg_color="transparent")
        heading.pack(side="left")
        ctk.CTkLabel(
            heading, text="TRANSLATION DESK",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=C.PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            heading, text="Write it once. Keep playing.",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"), text_color=C.TEXT,
        ).pack(anchor="w", pady=(2, 0))

        state = ctk.CTkFrame(top, fg_color=C.PRIMARY_DIM, corner_radius=999)
        state.pack(side="right", pady=(5, 0))
        ctk.CTkLabel(
            state, text="  READY  ", font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=C.ACCENT,
        ).pack(padx=8, pady=5)

        language_card = ctk.CTkFrame(
            work, fg_color=C.BG_RAISED, corner_radius=10,
            border_width=1, border_color=C.BORDER,
        )
        language_card.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            language_card, text="LANGUAGE ROUTE",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"), text_color=C.TEXT_DIM,
        ).pack(anchor="w", padx=14, pady=(10, 0))
        src = self.cfg.get("source_lang", DEFAULT_SOURCE)
        tgt = self.cfg.get("target_lang", DEFAULT_TARGET)
        self._lang_label = ctk.CTkLabel(
            language_card, text=f"{src}  →  {tgt}",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=C.TEXT,
        )
        self._lang_label.pack(anchor="w", padx=14, pady=(1, 10))

        composer = ctk.CTkFrame(
            work, fg_color=C.BG, corner_radius=12, border_width=1, border_color=C.BORDER,
        )
        composer.pack(fill="x", pady=(0, 12))
        source_head = ctk.CTkFrame(composer, fg_color="transparent")
        source_head.pack(fill="x", padx=14, pady=(13, 6))
        self._input_label = ctk.CTkLabel(
            source_head, text=f"INPUT · {src}",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=C.TEXT_DIM,
        )
        self._input_label.pack(side="left")
        ctk.CTkLabel(
            source_head, text="ENTER TO TRANSLATE",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"), text_color=C.TEXT_DIM,
        ).pack(side="right")

        input_row = ctk.CTkFrame(composer, fg_color="transparent")
        input_row.pack(fill="x", padx=14, pady=(0, 10))
        placeholder, justify = self._source_input_options()
        self.inp = ctk.CTkEntry(
            input_row, placeholder_text=placeholder,
            font=ctk.CTkFont(family="Segoe UI", size=15), height=46, corner_radius=8,
            border_color=C.BORDER, border_width=1, fg_color=C.BG_INPUT,
            text_color=C.TEXT, justify=justify,
        )
        self.inp.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.inp.bind("<Return>", lambda e: self._translate())
        ctk.CTkButton(
            input_row, text="PASTE", width=66, height=46, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=C.BG_RAISED, hover_color=C.PRIMARY_DIM, border_width=1,
            border_color=C.BORDER, text_color=C.TEXT, command=self._paste_translate,
        ).pack(side="right")
        self._translate_idle_label = "TRANSLATE"
        self.tr_btn = ctk.CTkButton(
            composer, text=self._translate_idle_label,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            height=42, corner_radius=8, fg_color=C.PRIMARY, hover_color=C.PRIMARY_H,
            text_color=C.BG, command=self._translate,
        )
        self.tr_btn.pack(fill="x", padx=14, pady=(0, 14))

        result = ctk.CTkFrame(
            work, fg_color=C.BG, corner_radius=12, border_width=1, border_color=C.BORDER,
        )
        result.pack(fill="both", expand=True)
        result_head = ctk.CTkFrame(result, fg_color="transparent")
        result_head.pack(fill="x", padx=14, pady=(13, 6))
        self._output_label = ctk.CTkLabel(
            result_head, text=f"OUTPUT · {tgt}",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=C.TEXT_DIM,
        )
        self._output_label.pack(side="left")
        self.cp_lbl = ctk.CTkLabel(
            result_head, text="", font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=C.SUCCESS,
        )
        self.cp_lbl.pack(side="right")
        self.preview = ctk.CTkTextbox(
            result, height=102, font=ctk.CTkFont(family="Segoe UI", size=14),
            corner_radius=8, fg_color=C.BG_INPUT, text_color=C.TEXT_SOFT,
            border_color=C.BORDER, border_width=1, state="disabled", wrap="word",
        )
        self.preview.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        self.send_btn = ctk.CTkButton(
            result, text="PASTE RESULT TO GAME",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), height=38,
            corner_radius=8, fg_color=C.BG_RAISED, hover_color=C.PRIMARY_DIM,
            border_color=C.BORDER, border_width=1, text_color=C.TEXT,
            command=self._manual_send, state="disabled",
        )
        self.send_btn.pack(fill="x", padx=14, pady=(0, 14))

        self.stat = ctk.CTkLabel(
            work, text=f"Ready · hotkey {self.cfg.get('hotkey', DEFAULT_HOTKEY).upper()}",
            font=ctk.CTkFont(family="Segoe UI", size=10), text_color=C.TEXT_DIM,
        )
        self.stat.pack(anchor="w", pady=(10, 0))

    def _seg_changed(self, value):
        idx = ["Copy", "Paste", "Send"].index(value)
        self.send_mode.set(self.mode_map[idx])
        self.cfg["mode"] = self.send_mode.get()
        save_config(self.cfg)
        notes = {
            MODE_COPY: "Copies the result only.",
            MODE_PASTE: "Pastes into the saved game window.",
            MODE_SEND: "Pastes and sends to the saved game window.",
        }
        if hasattr(self, "_mode_note"):
            self._mode_note.configure(text=notes[self.send_mode.get()])

    # ── API CHECK ──

    def _check_api(self):
        self.stat.configure(text="Checking connection", text_color=C.WARN)

        def _c():
            ok, msg = self.translator.test()
            self._post_ui(self._api_ok, ok, msg)

        threading.Thread(target=_c, daemon=True).start()

    def _api_ok(self, ok, msg):
        hk = self.cfg.get('hotkey', DEFAULT_HOTKEY).upper()
        if ok:
            self.stat.configure(text=f"Ready · hotkey {hk}", text_color=C.TEXT_DIM)
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
                self._status("Clipboard is empty", C.WARN)
        except Exception as e:
            logger.warning(f"Failed to paste: {e}")
            self._status("Could not read the clipboard", C.WARN)

    # ── TRANSLATE ──

    def _translate(self):
        if self.is_busy:
            return
        text = self.inp.get().strip()
        if not text:
            self._status("Write something to translate", C.WARN)
            return
        if len(text) > MAX_INPUT_CHARS:
            self._status(f"Text is too long (max {MAX_INPUT_CHARS} characters)", C.WARN)
            return
        self._request_sequence += 1
        request = TranslationRequest(
            request_id=self._request_sequence,
            text=text,
            source_text=text,
            custom_rules=self.cfg.get("custom_rules", ""),
            game_mode=self.cfg.get("game", "General"),
            ai_tone=self.cfg.get("tone", "Gamer (Default)"),
            source_key=self.cfg.get("source_lang", DEFAULT_SOURCE),
            target_key=self.cfg.get("target_lang", DEFAULT_TARGET),
            context=tuple(self._session_context()),
            mode=self.send_mode.get(),
            target_hwnd=self._last_hwnd,
            history_enabled=bool(self.cfg.get("history_enabled", False)),
            cache_enabled=bool(self.cfg.get("performance_cache_enabled", True)),
            cancel=threading.Event(),
        )
        self._main_cancel = request.cancel
        self._active_request_id = request.request_id
        self.is_busy = True
        self.tr_btn.configure(state="disabled", text="TRANSLATING")
        self.send_btn.configure(state="disabled")
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.configure(state="disabled")
        self._t0 = time.time()
        self._tick()

        threading.Thread(target=self._do_tr, args=(request,), daemon=True).start()

    def _tick(self):
        if not self.is_busy:
            return
        self._status(f"Translating · {time.time()-self._t0:.1f}s", C.ACCENT)
        self._timer_id = self.after(200, self._tick)

    def _stop_tick(self):
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None

    def _do_tr(self, request: TranslationRequest):
        self.translator.stream(
            request.text,
            custom_rules=request.custom_rules,
            game_mode=request.game_mode,
            ai_tone=request.ai_tone,
            source_key=request.source_key,
            target_key=request.target_key,
            context=request.context,
            cancel=request.cancel,
            cache_enabled=request.cache_enabled,
            on_token=lambda t: self._post_ui(self._add_tok, request.request_id, t),
            on_done=lambda r: self._post_ui(self._done, r, request),
            on_error=lambda e: self._post_ui(self._fail, e, request.request_id),
        )

    def _add_tok(self, request_id, t):
        if request_id != self._active_request_id or not self.is_busy:
            return
        self.preview.configure(state="normal")
        self.preview.insert("end", t)
        self.preview.see("end")
        self.preview.configure(state="disabled")

    def _done(self, result, request: TranslationRequest):
        if request.request_id != self._active_request_id or request.cancel.is_set():
            return
        self._stop_tick()
        self.is_busy = False
        self._main_cancel = None
        self.tr_btn.configure(state="normal", text=self._translate_idle_label)
        elapsed = time.time() - self._t0

        if result.startswith("["):
            self._status(result, C.ERROR)
            return

        self._show_preview(result)
        if not self._safe_copy(result):
            self._fail("Could not copy translation to clipboard", request.request_id)
            return
        self.send_btn.configure(state="normal")

        # Save to history + session memory
        if request.history_enabled and request.source_text:
            self._history = add_history_entry(
                request.source_text, result, self._history, MAX_HISTORY_ITEMS
            )
        if request.source_text:
            self._session_add(request.source_text, result)

        mode = request.mode
        if mode == MODE_COPY:
            self._status(f"Ready in {elapsed:.1f}s · copied to clipboard", C.SUCCESS)
        elif mode == MODE_PASTE:
            self._status(f"Ready in {elapsed:.1f}s · pasting", C.SUCCESS)
            self.iconify()
            self.update()
            threading.Thread(target=self._do_paste, args=(result, False, request.target_hwnd), daemon=True).start()
        elif mode == MODE_SEND:
            self._status(f"Ready in {elapsed:.1f}s · sending", C.SUCCESS)
            self.iconify()
            self.update()
            threading.Thread(target=self._do_paste, args=(result, True, request.target_hwnd), daemon=True).start()

    def _fail(self, msg, request_id=None):
        if request_id is not None and request_id != self._active_request_id:
            return
        self._stop_tick()
        self.is_busy = False
        self._main_cancel = None
        self.tr_btn.configure(state="normal", text=self._translate_idle_label)
        self._status(msg, C.ERROR)
        self._show_preview(f"[{msg}]")

    # ── AUTO-PASTE ──

    def _do_paste(self, text, enter, target_hwnd):
        time.sleep(0.05)
        if not self._focus_target_window(target_hwnd):
            self._post_ui(self._paste_failed, "Target window changed; translation is only in your clipboard")
            return
        self._release_all_modifiers()
        time.sleep(0.03)
        self._kb_ctrl_v()
        if enter:
            time.sleep(0.05)
            self._kb_enter()
        time.sleep(0.05)
        self._post_ui(self._restore, enter)

    def _focus_target_window(self, target_hwnd) -> bool:
        """Focus one captured external window; never use unsafe Alt+Tab guessing."""
        if not target_hwnd or self._is_own_window(target_hwnd):
            return False
        k32 = ctypes.windll.kernel32
        try:
            if not user32.IsWindow(target_hwnd):
                return False
            if user32.GetForegroundWindow() == target_hwnd:
                return True
            if user32.IsIconic(target_hwnd):
                user32.ShowWindow(target_hwnd, 9)  # SW_RESTORE
            target_thread = user32.GetWindowThreadProcessId(target_hwnd, None)
            current_thread = k32.GetCurrentThreadId()
            user32.AttachThreadInput(current_thread, target_thread, True)
            try:
                user32.BringWindowToTop(target_hwnd)
                user32.SetForegroundWindow(target_hwnd)
            finally:
                user32.AttachThreadInput(current_thread, target_thread, False)
            time.sleep(0.05)
            return user32.GetForegroundWindow() == target_hwnd
        except Exception as e:
            logger.warning(f"Failed to focus target window: {e}")
            return False

    def _paste_failed(self, reason):
        self.deiconify()
        self.lift()
        self.send_btn.configure(state="normal", text="PASTE RESULT TO GAME")
        self._status(reason, C.WARN)
        self.inp.focus_set()

    def _restore(self, enter):
        self.deiconify()
        self.lift()
        self._status("Sent to game" if enter else "Pasted to game", C.SUCCESS)
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
        target_hwnd = self._last_hwnd
        if not self._safe_copy(text):
            self._status("Could not copy the translation to clipboard", C.WARN)
            return
        self.send_btn.configure(state="disabled", text="PREPARING")
        self._status("Switch to the game chat", C.WARN)
        self.iconify()
        self.update()

        def _s():
            time.sleep(0.3)
            if not self._focus_target_window(target_hwnd):
                self._post_ui(self._paste_failed, "Target window changed; translation is only in your clipboard")
                return
            time.sleep(1.5)
            self._release_all_modifiers()
            time.sleep(0.05)
            self._kb_ctrl_v()
            if enter:
                time.sleep(0.2)
                self._kb_enter()
            time.sleep(0.4)
            self._post_ui(self._manual_done, enter)

        threading.Thread(target=_s, daemon=True).start()

    def _manual_done(self, enter):
        self.deiconify()
        self.lift()
        self.send_btn.configure(state="normal", text="PASTE RESULT TO GAME")
        self._status("Sent to game" if enter else "Pasted to game", C.SUCCESS)
        self.inp.delete(0, "end")
        self.cp_lbl.configure(text="")
        self.send_btn.configure(state="disabled")
        self.inp.focus_set()

    # ── SESSION CONTEXT ──

    def _session_context(self):
        """Recent exchanges from the current game session (main thread only).
        Silence longer than CONTEXT_IDLE_MINUTES means the game/session changed,
        so we start fresh instead of dragging in stale context."""
        if self._session_pairs and (time.time() - self._session_ts) > CONTEXT_IDLE_MINUTES * 60:
            logger.info("Session idle timeout — context reset.")
            self._session_pairs = []
        return list(self._session_pairs)

    def _session_add(self, src: str, dst: str):
        """Remember an exchange for context (main thread only). Caps keep cost flat."""
        self._session_pairs.append((src[:CONTEXT_MAX_CHARS], dst[:CONTEXT_MAX_CHARS]))
        self._session_pairs = self._session_pairs[-CONTEXT_MAX_EXCHANGES:]
        self._session_ts = time.time()

    def reset_session(self):
        """Drop session context (e.g. after language/model change in settings)."""
        self._session_pairs = []
        self._session_ts = 0.0

    def cancel_active_translation(self, reason="Cancelled"):
        """Cancel a main-window request and ignore any late worker callbacks."""
        if self._main_cancel is None:
            return
        self._main_cancel.set()
        self._main_cancel = None
        self._active_request_id += 1
        if self.is_busy:
            self._stop_tick()
            self.is_busy = False
            self.tr_btn.configure(state="normal", text=self._translate_idle_label)
            self._status(reason, C.WARN)

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
