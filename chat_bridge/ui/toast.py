"""
Translation Bridge — Toast Notification System
Lightweight, non-intrusive popup notifications for translation results.
"""

import logging
import customtkinter as ctk

from .theme import C

logger = logging.getLogger(__name__)


class Toast:
    """A small, auto-dismissing notification that appears at the bottom-right of the screen."""

    _active_toast = None  # Class-level reference to prevent overlapping toasts

    @classmethod
    def show(cls, parent, message: str, style: str = "success", duration: int = 2500):
        """
        Show a toast notification.
        
        Args:
            parent: The CTk root or toplevel to anchor to.
            message: Text to display.
            style: 'success', 'error', or 'info'.
            duration: How long to show (ms).
        """
        # Dismiss any existing toast
        if cls._active_toast and cls._active_toast.winfo_exists():
            try:
                cls._active_toast.destroy()
            except Exception:
                pass

        colors = {
            "success": (C.PRIMARY, C.BG),
            "error":   (C.ERROR, "#ffffff"),
            "info":    (C.BG_CARD, C.TEXT),
        }
        bg, fg = colors.get(style, colors["info"])

        icons = {
            "success": "✅",
            "error": "❌",
            "info": "ℹ️",
        }
        icon = icons.get(style, "")

        toast = ctk.CTkToplevel(parent)
        toast.withdraw()  # hide until positioned
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(fg_color=C.BG_CARD)

        # Outer border glow
        border = ctk.CTkFrame(toast, fg_color=bg, corner_radius=12)
        border.pack(fill="both", expand=True, padx=1, pady=1)

        inner = ctk.CTkFrame(border, fg_color=C.BG_CARD, corner_radius=11)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        label = ctk.CTkLabel(
            inner,
            text=f"  {icon}  {message}  ",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=bg,
        )
        label.pack(padx=16, pady=10)

        # Position bottom-right
        toast.update_idletasks()
        w = toast.winfo_reqwidth()
        h = toast.winfo_reqheight()
        sx = parent.winfo_screenwidth()
        sy = parent.winfo_screenheight()
        x = sx - w - 20
        y = sy - h - 60
        toast.geometry(f"+{x}+{y}")
        toast.deiconify()

        # Fade-in effect via alpha
        toast.attributes("-alpha", 0.0)
        cls._fade_in(toast, 0.0)

        cls._active_toast = toast

        # Auto-dismiss
        toast.after(duration, lambda: cls._fade_out(toast, 1.0))

        logger.debug(f"Toast shown: [{style}] {message}")

    @classmethod
    def _fade_in(cls, toast, alpha):
        if not toast.winfo_exists():
            return
        alpha = min(alpha + 0.15, 1.0)
        toast.attributes("-alpha", alpha)
        if alpha < 1.0:
            toast.after(20, lambda: cls._fade_in(toast, alpha))

    @classmethod
    def _fade_out(cls, toast, alpha):
        if not toast.winfo_exists():
            return
        alpha = max(alpha - 0.15, 0.0)
        toast.attributes("-alpha", alpha)
        if alpha > 0.0:
            toast.after(20, lambda: cls._fade_out(toast, alpha))
        else:
            toast.destroy()
            if cls._active_toast == toast:
                cls._active_toast = None
