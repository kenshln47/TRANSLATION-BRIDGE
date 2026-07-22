"""
Translation Bridge — Entry Point
Multi-language translator via OpenRouter (selectable model)

Run with: python -m chat_bridge
"""

import ctypes
import logging
import logging.handlers
import os
import sys

from .constants import MUTEX_NAME
from .version import __version__

# ─────────────────────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────────────────────

def _setup_logging():
    """Configure application-wide logging."""
    log_dir = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")),
        "TranslationBridge"
    )
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "app.log")

    # Rotate: keep last 500KB, 1 backup
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=500_000, backupCount=1, encoding="utf-8"
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            file_handler,
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger(__name__).info("=== Translation Bridge starting ===")


# ─────────────────────────────────────────────────────────────
# SINGLE INSTANCE
# ─────────────────────────────────────────────────────────────

def _enforce_single_instance():
    """Prevent multiple instances using a Windows named mutex."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        hwnd = user32.FindWindowW(None, "Translation Bridge")
        if hwnd:
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
        sys.exit(0)
    return mutex


def _enable_dpi_awareness():
    """Use physical window coordinates across mixed-DPI monitors when possible."""
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4. This must run
        # before CustomTkinter creates any HWNDs.
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

# Global reference to prevent garbage collection of the mutex handle
_mutex = None


def _run_packaged_smoke_test():
    """Load GUI/ONNX and prove every offline OCR model is in the bundle."""
    from pathlib import Path
    import tkinter

    import numpy as np
    import onnxruntime as ort
    import rapidocr

    from .app import App  # noqa: F401 - verifies the full GUI import graph

    # Exercise Tcl initialization, not merely the Python import.  This catches
    # missing _tcl_data/_tk_data files in one-file PyInstaller releases.
    tcl = tkinter.Tcl()
    if not tcl.eval("info patchlevel"):
        raise RuntimeError("Bundled Tcl runtime did not initialize")

    required_models = (
        "ch_PP-OCRv5_det_mobile.onnx",
        "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
        "latin_PP-OCRv5_rec_mobile.onnx",
        "arabic_PP-OCRv5_rec_mobile.onnx",
        "cyrillic_PP-OCRv5_rec_mobile.onnx",
        "devanagari_PP-OCRv5_rec_mobile.onnx",
        "japan_PP-OCRv4_rec_mobile.onnx",
        "korean_PP-OCRv5_rec_mobile.onnx",
        "ch_PP-OCRv5_rec_mobile.onnx",
    )
    models_dir = Path(rapidocr.__file__).resolve().parent / "models"
    missing = [
        name for name in required_models
        if not (models_dir / name).is_file() or (models_dir / name).stat().st_size <= 0
    ]
    if missing:
        raise RuntimeError(f"Missing bundled OCR models: {', '.join(missing)}")

    # Validate ONNX inside the *full* GUI bundle without creating a long-lived
    # RapidOCR object in this short process (Tk + ORT teardown can otherwise
    # keep a one-file smoke process alive on some Windows builds).
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    session = ort.InferenceSession(
        str(models_dir / "ch_PP-OCRv5_det_mobile.onnx"),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    input_name = session.get_inputs()[0].name
    session.run(None, {input_name: np.zeros((1, 3, 64, 256), dtype=np.float32)})


def main():
    global _mutex
    # Used by CI to verify that the packaged executable can load every runtime
    # dependency without creating a window or contacting an external service.
    if "--smoke-test" in sys.argv:
        _run_packaged_smoke_test()
        # Some frozen Windows builds keep Tk/ORT native worker state alive
        # during interpreter teardown. Checks have completed at this point;
        # let the one-file parent clean its extraction directory immediately.
        if getattr(sys, "frozen", False):
            os._exit(0)
        return

    if "--version" in sys.argv:
        print(__version__)
        return

    _setup_logging()
    _enable_dpi_awareness()
    _mutex = _enforce_single_instance()

    from .app import App
    app = App()
    app.mainloop()
    logging.shutdown()
    if getattr(sys, "frozen", False):
        os._exit(0)


if __name__ == "__main__":
    main()
