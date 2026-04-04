"""
Translation Bridge v7.0
Arabic -> English via OpenRouter (Claude 3.5 Haiku)

Dependencies:
  pip install customtkinter pyperclip openai httpx Pillow keyboard pystray
"""

import ctypes
import json
import os
import threading
import time

import customtkinter as ctk
import httpx
import pyperclip
from openai import OpenAI
import pystray
from pystray import MenuItem as item

try:
    import keyboard as kb
    HAS_KB = True
except ImportError:
    HAS_KB = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

user32 = ctypes.windll.user32

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]

def get_monitor_from_point(x, y):
    pt = POINT(x, y)
    hmon = user32.MonitorFromPoint(pt, 2)  # MONITOR_DEFAULTTONEAREST
    if hmon:
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            return mi.rcMonitor.left, mi.rcMonitor.top, mi.rcMonitor.right, mi.rcMonitor.bottom
    return None

# ─────────────────────────────────────────────────────────────
# PATHS & CONFIG
# ─────────────────────────────────────────────────────────────

APP_DIR = os.path.dirname(os.path.abspath(__file__))
API_KEY_FILE = os.path.join(APP_DIR, ".api_key")
CONFIG_FILE = os.path.join(APP_DIR, ".config.json")
LOGO_FILE = os.path.join(APP_DIR, "logo.png")

DEFAULT_HOTKEY = "ctrl+shift+t"

# ─────────────────────────────────────────────────────────────
# ASTON MARTIN F1 COLORS
# ─────────────────────────────────────────────────────────────

class C:
    BG         = "#0B1A12"
    BG_CARD    = "#0F2318"
    BG_INPUT   = "#0A1E14"
    PRIMARY    = "#006F62"
    PRIMARY_H  = "#00897B"
    ACCENT     = "#C5E336"
    ACCENT_H   = "#D4ED4E"
    TEXT       = "#E0EBE4"
    TEXT_DIM   = "#4A7A5A"
    SUCCESS    = "#C5E336"
    ERROR      = "#FF6B6B"
    WARN       = "#FFD93D"
    BORDER     = "#1A4D30"
    SEP        = "#163D28"

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

OPENROUTER_MODEL = "anthropic/claude-3.5-haiku"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

WINDOW_WIDTH = 440
WINDOW_HEIGHT = 580
WINDOW_OPACITY = 0.97

SYSTEM_PROMPT = """
You are a translation API. Your ONLY job is to output the English translation of the Arabic text provided.

STRICT RULES:
1. Output ONLY the translated string.
2. DO NOT provide explanations.
3. DO NOT use brackets ( ) or notes.
4. DO NOT provide "context" or descriptions of the slang.
5. If the input is offensive or gaming slang, translate it directly to equivalent English slang without commenting on its nature.

Failure to follow these rules will break the system.
"""

MODE_COPY  = "copy"
MODE_PASTE = "paste"
MODE_SEND  = "paste_send"


# ─────────────────────────────────────────────────────────────
# HELPERS: API KEY + CONFIG
# ─────────────────────────────────────────────────────────────

def load_api_key():
    if os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE, "r") as f:
            return f.read().strip()
    return ""

def save_api_key(k):
    with open(API_KEY_FILE, "w") as f:
        f.write(k.strip())

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"hotkey": DEFAULT_HOTKEY, "mode": MODE_SEND}

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f)


# ─────────────────────────────────────────────────────────────
# TRANSLATOR
# ─────────────────────────────────────────────────────────────

class Translator:
    def __init__(self, api_key=""):
        self.api_key = api_key
        self.model = OPENROUTER_MODEL
        self.client = None
        if api_key:
            self._init(api_key)

    def _init(self, key):
        self.api_key = key
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL, api_key=key,
            timeout=httpx.Timeout(15.0, connect=5.0),
        )

    def ready(self):
        return bool(self.api_key and self.client)

    def test(self):
        if not self.ready(): return False, "No API key"
        try:
            self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Say OK"}],
                max_tokens=3, temperature=0,
            )
            return True, "Connected"
        except Exception as e:
            err = str(e)
            if "401" in err: return False, "Invalid API key"
            if "timeout" in err.lower(): return False, "Timeout"
            return False, f"Error: {err[:60]}"

    def stream(self, text, on_token=None, on_done=None, on_error=None):
        if not text or not text.strip():
            if on_error: on_error("Empty"); return
        if not self.ready():
            if on_error: on_error("No API key"); return
        try:
            chunks = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text.strip()},
                ],
                max_tokens=100, temperature=0.3, stream=True,
            )
            full = ""
            for c in chunks:
                if c.choices and c.choices[0].delta.content:
                    t = c.choices[0].delta.content
                    full += t
                    if on_token: on_token(t)
            result = full.strip().split("(")[0].split("\n")[0].strip()
            if len(result) >= 2 and result[0] in ('"', "'", "\u201c") and result[-1] in ('"', "'", "\u201d"):
                result = result[1:-1].strip()
            if on_done: on_done(result or "[Empty]")
        except Exception as e:
            err = str(e)
            if "401" in err: msg = "Invalid API key"
            elif "429" in err: msg = "Rate limited"
            elif "timeout" in err.lower(): msg = "Timeout"
            else: msg = f"Error: {err[:60]}"
            if on_error: on_error(msg)


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
        self._hotkey_handle = None

        self._setup_window()

        key = load_api_key()
        if key:
            self.translator._init(key)
            self._build_main()
            self._check_api()
        else:
            self._build_setup()

        self._poll_window()
        self._register_hotkey()

        # Intercept window close (X button) to minimize to tray instead
        self.protocol("WM_DELETE_WINDOW", self._hide_window)
        self.tray_icon = None

    def destroy(self):
        self._unregister_hotkey()
        if self.tray_icon:
            self.tray_icon.stop()
        super().destroy()

    # ── SYSTEM TRAY ──

    def _hide_window(self):
        """Hide the window and show the system tray icon."""
        self.withdraw()
        # Start tray in a background thread
        threading.Thread(target=self._show_tray_icon, daemon=True).start()

    def _show_tray_icon(self):
        """Creates and runs the pystray icon."""
        if self.tray_icon:
            return

        icon_image = None
        if HAS_PIL and os.path.exists(LOGO_FILE):
            try:
                icon_image = Image.open(LOGO_FILE)
            except Exception:
                pass
        
        if not icon_image:
            # Create a simple fallback image if logo is missing
            try:
                icon_image = Image.new('RGB', (64, 64), color=(0, 111, 98))
            except Exception:
                pass

        menu = pystray.Menu(
            item('Show', self._restore_from_tray, default=True),
            item('Quit', self._quit_from_tray)
        )

        self.tray_icon = pystray.Icon("TranslationBridge", icon_image, "Translation Bridge", menu)
        self.tray_icon.run()

    def _restore_from_tray(self, icon, item=None):
        """Restore window from system tray."""
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        # Must restore window state in main thread
        self.after(0, self._show_window)
        
    def _show_window(self):
        self.deiconify()
        self.attributes("-topmost", True)

    def _quit_from_tray(self, icon, item):
        """Actually close the app."""
        if self.tray_icon:
            self.tray_icon.stop()
        self.after(0, self.destroy)

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
                ico = os.path.join(APP_DIR, "icon.ico")
                if not os.path.exists(ico):
                    img = Image.open(LOGO_FILE).resize((64, 64), Image.LANCZOS)
                    img.save(ico, format="ICO", sizes=[(64, 64)])
                self.iconbitmap(ico)
            except Exception:
                pass

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
            except Exception:
                pass
        return None

    # ── GLOBAL HOTKEY ──

    def _register_hotkey(self):
        if not HAS_KB:
            return
        hk = self.cfg.get("hotkey", DEFAULT_HOTKEY)
        try:
            self._hotkey_handle = kb.add_hotkey(hk, self._on_hotkey, suppress=False)
        except Exception:
            pass

    def _unregister_hotkey(self):
        if HAS_KB and self._hotkey_handle is not None:
            try:
                kb.remove_hotkey(self._hotkey_handle)
            except Exception:
                pass
            self._hotkey_handle = None

    def _on_hotkey(self):
        """Called from hotkey thread — schedule popup on main thread."""
        self.after(0, self._show_quick_popup)

    def _show_quick_popup(self):
        """Toggle the quick translation popup."""
        if self._hotkey_popup and self._hotkey_popup.winfo_exists():
            self._hotkey_popup.destroy()
            self._hotkey_popup = None
            return

        p = ctk.CTkToplevel(self)
        p.title("Quick Translate")
        p.geometry("420x60")
        p.resizable(False, False)
        p.attributes("-topmost", True)
        p.overrideredirect(True)  # borderless
        p.configure(fg_color=C.BG_CARD)
        self._hotkey_popup = p

        # Get the monitor where the mouse currently is
        p.update_idletasks()
        mx = self.winfo_pointerx()
        my = self.winfo_pointery()
        
        mon_rect = get_monitor_from_point(mx, my)
        if mon_rect:
            m_left, m_top, m_right, m_bottom = mon_rect
            # Position at the exact bottom center of this specific monitor
            x = m_left + ((m_right - m_left) - 420) // 2
            y = m_bottom - 120
        else:
            # Fallback
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
        
        # Force aggressive focus so the user can type immediately
        p.focus_force()
        entry.focus_force()
        p.after(10, entry.focus_force)
        p.after(50, entry.focus_force)

        # Status label (replaces entry after translation)
        status_lbl = ctk.CTkLabel(
            inner, text="", font=ctk.CTkFont(size=10),
            text_color=C.ACCENT,
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

            def _do():
                def on_done(result):
                    pyperclip.copy(result)
                    self.after(0, _paste_and_close, result)
                def on_error(msg):
                    self.after(0, lambda: _handle_error(msg))
                self.translator.stream(txt, on_done=on_done, on_error=on_error)

            threading.Thread(target=_do, daemon=True).start()

        def _paste_and_close(result):
            if not p.winfo_exists():
                return
            p.destroy()
            self._hotkey_popup = None
            mode = self.send_mode.get()
            if mode == MODE_COPY:
                return  # already in clipboard
            # Run paste/send in a background thread to avoid blocking the main thread
            def _do_paste_send():
                time.sleep(0.2)
                self._release_all_modifiers()
                time.sleep(0.05)
                self._kb_ctrl_v()
                if mode == MODE_SEND:
                    time.sleep(0.15)
                    self._kb_enter()
            threading.Thread(target=_do_paste_send, daemon=True).start()

        entry.bind("<Return>", _go)
        entry.bind("<Escape>", _close)
        p.bind("<FocusOut>", lambda e: None)  # keep alive

    # ═══════════════════════════════════════════════════════════
    # SETUP SCREEN
    # ═══════════════════════════════════════════════════════════

    def _build_setup(self):
        self.setup_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.setup_frame.pack(fill="both", expand=True, padx=20, pady=20)

        logo = self._load_logo(size=(80, 80))
        if logo:
            ctk.CTkLabel(self.setup_frame, text="", image=logo).pack(pady=(20, 8))
        else:
            ctk.CTkLabel(self.setup_frame, text="🌐", font=ctk.CTkFont(size=48)).pack(pady=(20, 8))

        ctk.CTkLabel(
            self.setup_frame, text="Translation Bridge",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=C.ACCENT,
        ).pack(pady=(0, 2))

        ctk.CTkLabel(
            self.setup_frame, text="Arabic → English • Claude Haiku",
            font=ctk.CTkFont(size=11), text_color=C.TEXT_DIM,
        ).pack(pady=(0, 20))

        ctk.CTkFrame(self.setup_frame, height=1, fg_color=C.SEP).pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            self.setup_frame, text="🔑  OpenRouter API Key",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=C.TEXT,
        ).pack(anchor="w", pady=(0, 2))

        ctk.CTkLabel(
            self.setup_frame, text="openrouter.ai/keys",
            font=ctk.CTkFont(size=10), text_color=C.TEXT_DIM,
        ).pack(anchor="w", pady=(0, 8))

        self.setup_entry = ctk.CTkEntry(
            self.setup_frame, placeholder_text="sk-or-v1-...",
            font=ctk.CTkFont(size=12), height=42, corner_radius=10,
            border_color=C.PRIMARY, border_width=2,
            fg_color=C.BG_INPUT, text_color=C.TEXT,
        )
        self.setup_entry.pack(fill="x", pady=(0, 6))

        ctk.CTkButton(
            self.setup_frame, text="📋 Paste from clipboard",
            height=30, corner_radius=8, font=ctk.CTkFont(size=11),
            fg_color=C.BG_CARD, hover_color=C.PRIMARY, text_color=C.ACCENT,
            command=lambda: (self.setup_entry.delete(0, "end"),
                             self.setup_entry.insert(0, pyperclip.paste().strip())),
        ).pack(fill="x", pady=(0, 12))

        self.setup_status = ctk.CTkLabel(
            self.setup_frame, text="", font=ctk.CTkFont(size=10), text_color=C.TEXT_DIM,
        )
        self.setup_status.pack(pady=(0, 6))

        self.setup_btn = ctk.CTkButton(
            self.setup_frame, text="🚀  Connect & Start",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=46, corner_radius=12,
            fg_color=C.PRIMARY, hover_color=C.PRIMARY_H, text_color=C.TEXT,
            command=self._on_setup_go,
        )
        self.setup_btn.pack(fill="x")

    def _on_setup_go(self):
        key = self.setup_entry.get().strip()
        if not key:
            self.setup_status.configure(text="⚠️ Enter a key", text_color=C.WARN)
            return
        self.setup_btn.configure(state="disabled", text="⏳ Testing...")
        self.setup_status.configure(text="Connecting...", text_color=C.ACCENT)
        def _t():
            self.translator._init(key)
            ok, msg = self.translator.test()
            self.after(0, self._on_setup_done, ok, msg, key)
        threading.Thread(target=_t, daemon=True).start()

    def _on_setup_done(self, ok, msg, key):
        if ok:
            save_api_key(key)
            self.setup_frame.destroy()
            self._build_main()
            self._check_api()
        else:
            self.setup_btn.configure(state="normal", text="🚀  Connect & Start")
            self.setup_status.configure(text=f"❌ {msg}", text_color=C.ERROR)

    # ═══════════════════════════════════════════════════════════
    # MAIN UI
    # ═══════════════════════════════════════════════════════════

    def _build_main(self):
        m = ctk.CTkFrame(self, fg_color="transparent")
        m.pack(fill="both", expand=True)
        self.main = m

        # ── HEADER ──
        hdr = ctk.CTkFrame(m, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(8, 2))

        logo = self._load_logo(size=(30, 30))
        if logo:
            ctk.CTkLabel(hdr, text="", image=logo).pack(side="left", padx=(0, 6))

        ctk.CTkLabel(
            hdr, text="Translation Bridge",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=C.ACCENT,
        ).pack(side="left")

        ctk.CTkButton(
            hdr, text="⚙", width=26, height=24,
            font=ctk.CTkFont(size=14), fg_color="transparent",
            hover_color=C.BG_CARD, text_color=C.TEXT_DIM,
            command=self._show_settings,
        ).pack(side="right")

        # ── API STATUS ──
        api_bar = ctk.CTkFrame(m, fg_color=C.BG_CARD, corner_radius=8)
        api_bar.pack(fill="x", padx=14, pady=(4, 6))

        self.api_dot = ctk.CTkLabel(
            api_bar, text="●", font=ctk.CTkFont(size=10), text_color=C.TEXT_DIM,
        )
        self.api_dot.pack(side="left", padx=(10, 4), pady=5)

        self.api_lbl = ctk.CTkLabel(
            api_bar, text="Checking...",
            font=ctk.CTkFont(size=10), text_color=C.TEXT_DIM,
        )
        self.api_lbl.pack(side="left", pady=5)

        # Hotkey indicator
        hk = self.cfg.get("hotkey", DEFAULT_HOTKEY)
        self.hk_lbl = ctk.CTkLabel(
            api_bar, text=f"⌨ {hk.upper()}",
            font=ctk.CTkFont(size=9), text_color=C.TEXT_DIM,
        )
        self.hk_lbl.pack(side="right", padx=(0, 10), pady=5)

        # ── INPUT ──
        ctk.CTkLabel(
            m, text="✏️  Arabic Text",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=C.TEXT,
        ).pack(anchor="w", padx=14, pady=(4, 1))

        irow = ctk.CTkFrame(m, fg_color="transparent")
        irow.pack(fill="x", padx=14, pady=(0, 4))

        self.inp = ctk.CTkEntry(
            irow, placeholder_text="...اكتب أو الصق هنا",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            height=40, corner_radius=10,
            border_color=C.PRIMARY, border_width=2,
            fg_color=C.BG_INPUT, text_color=C.TEXT, justify="right",
        )
        self.inp.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.inp.bind("<Return>", lambda e: self._translate())

        ctk.CTkButton(
            irow, text="📋", width=40, height=40, corner_radius=10,
            font=ctk.CTkFont(size=15),
            fg_color=C.BG_CARD, hover_color=C.PRIMARY,
            border_color=C.BORDER, border_width=1,
            command=self._paste_translate,
        ).pack(side="right")

        self.tr_btn = ctk.CTkButton(
            m, text="🔄  Translate",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34, corner_radius=10,
            fg_color=C.PRIMARY, hover_color=C.PRIMARY_H,
            text_color=C.TEXT, command=self._translate,
        )
        self.tr_btn.pack(fill="x", padx=14, pady=(0, 6))

        # ── PREVIEW ──
        phdr = ctk.CTkFrame(m, fg_color="transparent")
        phdr.pack(fill="x", padx=14, pady=(2, 1))

        ctk.CTkLabel(
            phdr, text="📝  Translation",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=C.TEXT,
        ).pack(side="left")

        self.cp_lbl = ctk.CTkLabel(
            phdr, text="", font=ctk.CTkFont(size=9), text_color=C.SUCCESS,
        )
        self.cp_lbl.pack(side="right")

        self.preview = ctk.CTkTextbox(
            m, height=60, font=ctk.CTkFont(size=12), corner_radius=8,
            fg_color=C.BG_INPUT, text_color=C.ACCENT,
            border_color=C.BORDER, border_width=1,
            state="disabled", wrap="word",
        )
        self.preview.pack(fill="x", padx=14, pady=(0, 6))

        # ── SEND MODE ──
        ctk.CTkFrame(m, height=1, fg_color=C.SEP).pack(fill="x", padx=14, pady=(2, 6))

        ctk.CTkLabel(
            m, text="⚡ After Translation:",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=C.TEXT,
        ).pack(anchor="w", padx=14, pady=(0, 3))

        mf = ctk.CTkFrame(m, fg_color=C.BG_CARD, corner_radius=10)
        mf.pack(fill="x", padx=14, pady=(0, 6))

        for lbl, val in [
            ("📋  Copy only", MODE_COPY),
            ("📋→📌  Paste only", MODE_PASTE),
            ("📋→📌→🚀  Paste & Send", MODE_SEND),
        ]:
            ctk.CTkRadioButton(
                mf, text=lbl, variable=self.send_mode, value=val,
                font=ctk.CTkFont(size=10), text_color=C.TEXT,
                fg_color=C.ACCENT, hover_color=C.PRIMARY,
                border_color=C.BORDER,
                command=self._save_mode,
            ).pack(anchor="w", padx=12, pady=3)

        # ── MANUAL SEND ──
        self.send_btn = ctk.CTkButton(
            m, text="📋  Copy & Paste to Chat",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=40, corner_radius=10,
            fg_color=C.PRIMARY, hover_color=C.ACCENT,
            text_color=C.BG, command=self._manual_send, state="disabled",
        )
        self.send_btn.pack(fill="x", padx=14, pady=(2, 2))

        # ── STATUS ──
        self.stat = ctk.CTkLabel(
            m, text=f"Ready • Hotkey: {self.cfg.get('hotkey', DEFAULT_HOTKEY).upper()}",
            font=ctk.CTkFont(size=10), text_color=C.TEXT_DIM, wraplength=400,
        )
        self.stat.pack(fill="x", padx=14, pady=(2, 6))

    def _save_mode(self):
        self.cfg["mode"] = self.send_mode.get()
        save_config(self.cfg)

    # ── SETTINGS DIALOG ──

    def _show_settings(self):
        d = ctk.CTkToplevel(self)
        d.title("⚙️ Settings")
        d.geometry("380x320")
        d.resizable(False, False)
        d.attributes("-topmost", True)
        d.grab_set()
        d.configure(fg_color=C.BG)

        d.update_idletasks()
        x = (d.winfo_screenwidth() - 380) // 2
        y = (d.winfo_screenheight() - 320) // 2
        d.geometry(f"+{x}+{y}")

        ctk.CTkLabel(
            d, text="⚙️  Settings",
            font=ctk.CTkFont(size=14, weight="bold"), text_color=C.ACCENT,
        ).pack(padx=16, pady=(12, 10))

        # ── API Key ──
        ctk.CTkLabel(d, text="🔑 API Key", font=ctk.CTkFont(size=11, weight="bold"),
                      text_color=C.TEXT).pack(anchor="w", padx=16)

        key_e = ctk.CTkEntry(
            d, placeholder_text="sk-or-v1-...",
            font=ctk.CTkFont(size=11), height=36, corner_radius=8,
            border_color=C.PRIMARY, border_width=2,
            fg_color=C.BG_INPUT, text_color=C.TEXT,
        )
        key_e.pack(fill="x", padx=16, pady=(2, 4))
        key_e.focus_set()
        cur = load_api_key()
        if cur: key_e.insert(0, cur)

        ctk.CTkButton(
            d, text="📋 Paste", height=26, corner_radius=6, font=ctk.CTkFont(size=10),
            fg_color=C.BG_CARD, hover_color=C.PRIMARY, text_color=C.ACCENT,
            command=lambda: (key_e.delete(0, "end"), key_e.insert(0, pyperclip.paste().strip())),
        ).pack(fill="x", padx=16, pady=(0, 10))

        # ── Hotkey ──
        ctk.CTkLabel(d, text="⌨️ Global Hotkey", font=ctk.CTkFont(size=11, weight="bold"),
                      text_color=C.TEXT).pack(anchor="w", padx=16)

        ctk.CTkLabel(d, text="Examples: ctrl+shift+t, alt+t, ctrl+alt+q",
                      font=ctk.CTkFont(size=9), text_color=C.TEXT_DIM).pack(anchor="w", padx=16)

        hk_e = ctk.CTkEntry(
            d, font=ctk.CTkFont(size=11), height=36, corner_radius=8,
            border_color=C.PRIMARY, border_width=2,
            fg_color=C.BG_INPUT, text_color=C.TEXT,
        )
        hk_e.pack(fill="x", padx=16, pady=(2, 12))
        hk_e.insert(0, self.cfg.get("hotkey", DEFAULT_HOTKEY))

        def _save():
            k = key_e.get().strip()
            if k:
                save_api_key(k)
                self.translator._init(k)
                self._check_api()
            hk = hk_e.get().strip().lower()
            if hk:
                self._unregister_hotkey()
                self.cfg["hotkey"] = hk
                save_config(self.cfg)
                self._register_hotkey()
                if hasattr(self, "hk_lbl"):
                    self.hk_lbl.configure(text=f"⌨ {hk.upper()}")
                self._status(f"Hotkey: {hk.upper()}", C.SUCCESS)
            d.destroy()

        row = ctk.CTkFrame(d, fg_color="transparent")
        row.pack(fill="x", padx=16)

        ctk.CTkButton(
            row, text="💾 Save", width=150, height=36,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=C.PRIMARY, hover_color=C.PRIMARY_H, command=_save,
        ).pack(side="left", expand=True, padx=(0, 4))

        ctk.CTkButton(
            row, text="Cancel", width=150, height=36,
            font=ctk.CTkFont(size=12),
            fg_color=C.BG_CARD, hover_color=C.BORDER, command=d.destroy,
        ).pack(side="right", expand=True, padx=(4, 0))

    # ── API CHECK ──

    def _check_api(self):
        self.api_dot.configure(text_color=C.WARN)
        self.api_lbl.configure(text="Testing...", text_color=C.WARN)
        def _c():
            ok, msg = self.translator.test()
            self.after(0, self._api_ok, ok, msg)
        threading.Thread(target=_c, daemon=True).start()

    def _api_ok(self, ok, msg):
        if ok:
            self.api_dot.configure(text_color=C.SUCCESS)
            self.api_lbl.configure(text="✓ Claude Haiku — Ready", text_color=C.SUCCESS)
        else:
            self.api_dot.configure(text_color=C.ERROR)
            self.api_lbl.configure(text=msg, text_color=C.ERROR)

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
        except Exception:
            self._status("⚠️ Can't read clipboard", C.WARN)

    # ── TRANSLATE ──

    def _translate(self):
        if self.is_busy: return
        text = self.inp.get().strip()
        if not text:
            self._status("⚠️ Type something", C.WARN)
            return
        self.is_busy = True
        self.tr_btn.configure(state="disabled", text="⏳ Translating...")
        self.send_btn.configure(state="disabled")
        self.cp_lbl.configure(text="")
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.configure(state="disabled")
        self._t0 = time.time()
        self._tick()
        threading.Thread(target=self._do_tr, args=(text,), daemon=True).start()

    def _tick(self):
        if not self.is_busy: return
        self._status(f"⏳ Translating... ({time.time()-self._t0:.1f}s)", C.ACCENT)
        self._timer_id = self.after(200, self._tick)

    def _stop_tick(self):
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None

    def _do_tr(self, text):
        self.translator.stream(
            text,
            on_token=lambda t: self.after(0, self._add_tok, t),
            on_done=lambda r: self.after(0, self._done, r),
            on_error=lambda e: self.after(0, self._fail, e),
        )

    def _add_tok(self, t):
        self.preview.configure(state="normal")
        self.preview.insert("end", t)
        self.preview.see("end")
        self.preview.configure(state="disabled")

    def _done(self, result):
        self._stop_tick()
        self.is_busy = False
        self.tr_btn.configure(state="normal", text="🔄  Translate")
        elapsed = time.time() - self._t0
        if result.startswith("["):
            self._status(f"❌ {result}", C.ERROR); return
        self._show_preview(result)
        pyperclip.copy(result)
        self.cp_lbl.configure(text="✓ Copied")
        self.send_btn.configure(state="normal")
        mode = self.send_mode.get()
        if mode == MODE_COPY:
            self._status(f"✅ Done ({elapsed:.1f}s) — clipboard", C.SUCCESS)
        elif mode == MODE_PASTE:
            self._status(f"✅ Done ({elapsed:.1f}s) — pasting...", C.SUCCESS)
            self.iconify(); self.update()
            threading.Thread(target=self._do_paste, args=(result, False), daemon=True).start()
        elif mode == MODE_SEND:
            self._status(f"✅ Done ({elapsed:.1f}s) — sending...", C.SUCCESS)
            self.iconify(); self.update()
            threading.Thread(target=self._do_paste, args=(result, True), daemon=True).start()

    def _fail(self, msg):
        self._stop_tick()
        self.is_busy = False
        self.tr_btn.configure(state="normal", text="🔄  Translate")
        self._status(f"❌ {msg}", C.ERROR)
        self._show_preview(f"[{msg}]")

    # ── AUTO-PASTE ──

    def _do_paste(self, text, enter):
        time.sleep(0.3)
        self._switch_win()
        time.sleep(0.5)
        self._release_all_modifiers()
        time.sleep(0.05)
        pyperclip.copy(text)
        self._kb_ctrl_v()
        if enter:
            time.sleep(0.2)
            self._kb_enter()
        time.sleep(0.4)
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
                    time.sleep(0.3)
                    if user32.GetForegroundWindow() == self._last_hwnd:
                        ok = True
            except Exception:
                pass
        if not ok:
            UP = 0x0002
            EXT = 0x0001
            try:
                user32.keybd_event(0x12, 0, EXT, 0)        # Alt down
                user32.keybd_event(0x09, 0, 0, 0)          # Tab down
                time.sleep(0.05)
                user32.keybd_event(0x09, 0, UP, 0)          # Tab up
                user32.keybd_event(0x12, 0, UP | EXT, 0)    # Alt up
            except Exception:
                pass
            finally:
                # Safety: ensure Alt is released
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
        if not text: return
        enter = self.send_mode.get() == MODE_SEND
        self.send_btn.configure(state="disabled", text="⏳...")
        self._status("🔴 Switch to chat... 2s", C.ERROR)
        self.iconify(); self.update()
        def _s():
            time.sleep(0.3); self._switch_win(); time.sleep(1.5)
            self._release_all_modifiers(); time.sleep(0.05)
            pyperclip.copy(text); self._kb_ctrl_v()
            if enter: time.sleep(0.2); self._kb_enter()
            time.sleep(0.4); self.after(0, self._manual_done)
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
    def _kb_ctrl_v():
        UP = 0x0002
        try:
            user32.keybd_event(0x11, 0, 0, 0)      # Ctrl down
            user32.keybd_event(0x56, 0, 0, 0)      # V down
            time.sleep(0.05)
            user32.keybd_event(0x56, 0, UP, 0)      # V up
        finally:
            user32.keybd_event(0x11, 0, UP, 0)      # Ctrl up (always)

    @staticmethod
    def _kb_enter():
        UP = 0x0002
        user32.keybd_event(0x0D, 0, 0, 0)          # Enter down
        time.sleep(0.05)
        user32.keybd_event(0x0D, 0, UP, 0)          # Enter up


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
