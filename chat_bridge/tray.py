"""
Translation Bridge — System Tray Integration
"""

import logging
import os
import threading

import pystray

from .config import LOGO_FILE

logger = logging.getLogger(__name__)

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class TrayManager:
    """Manages the system tray icon lifecycle."""

    def __init__(self, on_restore, on_quit):
        self._icon: pystray.Icon | None = None
        self._on_restore = on_restore
        self._on_quit = on_quit

    @property
    def active(self) -> bool:
        return self._icon is not None

    def show(self):
        """Show the tray icon in a background thread."""
        if self._icon:
            return
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        """Stop and remove the tray icon."""
        if self._icon:
            try:
                self._icon.stop()
            except Exception as e:
                logger.warning(f"Error stopping tray icon: {e}")
            self._icon = None

    def _run(self):
        icon_image = self._load_icon()
        menu = pystray.Menu(
            pystray.MenuItem('Show', self._handle_restore, default=True),
            pystray.MenuItem('Quit', self._handle_quit),
        )
        self._icon = pystray.Icon("TranslationBridge", icon_image, "Translation Bridge", menu)
        logger.info("System tray icon started.")
        self._icon.run()

    def _handle_restore(self, icon, item=None):
        self.stop()
        self._on_restore()

    def _handle_quit(self, icon, item):
        self.stop()
        self._on_quit()

    @staticmethod
    def _load_icon():
        """Load the app icon for the tray, with fallback."""
        if HAS_PIL and os.path.exists(LOGO_FILE):
            try:
                return Image.open(LOGO_FILE)
            except Exception as e:
                logger.warning(f"Failed to load tray icon from {LOGO_FILE}: {e}")

        # Fallback: generate a simple green square
        if HAS_PIL:
            try:
                return Image.new('RGB', (64, 64), color=(62, 207, 142))
            except Exception as e:
                logger.warning(f"Failed to create fallback tray icon: {e}")
        return None
