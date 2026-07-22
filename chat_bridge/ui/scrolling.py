"""Responsive, leak-free scrolling for CustomTkinter surfaces."""

from __future__ import annotations

import sys

import customtkinter as ctk


class SmoothScrollableFrame(ctk.CTkScrollableFrame):
    """CTkScrollableFrame with bounded Windows wheel work and clean teardown.

    CustomTkinter 6 registers every scrollable frame with ``bind_all`` but does
    not remove those Tcl bindings when the frame is destroyed. Reopening a
    dialog therefore adds another wheel callback each time. This subclass
    records the binding ids created by the base class and removes only its own
    callbacks during teardown.
    """

    _FRAME_MS = 12
    _PIXELS_PER_NOTCH = 44.0
    _MAX_PIXELS_PER_FRAME = 96

    def __init__(self, *args, **kwargs):
        self._managed_global_bindings: list[tuple[object, str, str]] = []
        self._pending_scroll_pixels = 0.0
        self._scroll_job = None
        self._scroll_destroyed = False
        super().__init__(*args, **kwargs)

    def bind_all(self, sequence=None, func=None, add=None):
        """Capture ids for the global bindings installed by CustomTkinter."""
        func_id = super().bind_all(sequence, func, add)
        if sequence and func is not None and func_id:
            # tkinter registers bind_all callbacks on the root object, so the
            # root must also own their deletion bookkeeping.
            self._managed_global_bindings.append((self._root(), sequence, func_id))
        return func_id

    @staticmethod
    def _is_descendant(widget, ancestor) -> bool:
        current = widget
        while current is not None:
            if current is ancestor:
                return True
            current = getattr(current, "master", None)
        return False

    @staticmethod
    def _textbox_ancestor(widget):
        current = widget
        while current is not None:
            if isinstance(current, ctk.CTkTextbox):
                return current
            current = getattr(current, "master", None)
        return None

    def _check_if_valid_scroll(self, widget):
        """Scroll the page across controls unless an active textbox owns it."""
        if widget is self._parent_canvas or self._is_descendant(widget, self):
            textbox = self._textbox_ancestor(widget)
            if textbox is not None:
                focus = self.focus_get()
                if focus is not None and self._is_descendant(focus, textbox):
                    return False
            return True
        return False

    def _mouse_wheel_all(self, event):
        if not self._check_if_valid_scroll(event.widget):
            return None
        if not sys.platform.startswith("win"):
            return super()._mouse_wheel_all(event)

        delta = float(getattr(event, "delta", 0) or 0)
        if not delta:
            return "break"

        if self._shift_pressed:
            if self._parent_canvas.xview() != (0.0, 1.0):
                self._parent_canvas.xview_scroll(-int(delta / 120) or (-1 if delta > 0 else 1), "units")
            return "break"

        if self._parent_canvas.yview() == (0.0, 1.0):
            return "break"

        # Preserve precision-trackpad deltas instead of truncating each event,
        # and coalesce bursts into at most one canvas move per display frame.
        self._pending_scroll_pixels += -(delta / 120.0) * self._PIXELS_PER_NOTCH
        if self._scroll_job is None:
            self._scroll_job = self.after(self._FRAME_MS, self._flush_scroll)
        return "break"

    def _flush_scroll(self):
        self._scroll_job = None
        if self._scroll_destroyed:
            return

        pending = self._pending_scroll_pixels
        if abs(pending) < 0.5:
            self._pending_scroll_pixels = 0.0
            return

        pixels = max(
            -self._MAX_PIXELS_PER_FRAME,
            min(self._MAX_PIXELS_PER_FRAME, int(round(pending))),
        )
        self._pending_scroll_pixels -= pixels
        self._parent_canvas.yview_scroll(pixels, "units")

        if abs(self._pending_scroll_pixels) >= 0.5:
            self._scroll_job = self.after(self._FRAME_MS, self._flush_scroll)

    def destroy(self):
        if self._scroll_destroyed:
            return
        self._scroll_destroyed = True
        if self._scroll_job is not None:
            try:
                self.after_cancel(self._scroll_job)
            except Exception:
                pass
            self._scroll_job = None

        # tkinter has no public per-callback unbind_all API. Its private helper
        # is the same path used by unbind(), and lets us remove only our ids
        # without disturbing other windows' keyboard or wheel bindings.
        for owner, sequence, func_id in self._managed_global_bindings:
            try:
                owner._unbind(("bind", "all", sequence), func_id)
            except Exception:
                pass
        self._managed_global_bindings.clear()
        super().destroy()
