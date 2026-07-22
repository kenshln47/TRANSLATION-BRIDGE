"""One-shot, in-memory game-chat capture and OCR.

The reader deliberately does *not* run a capture loop.  The foreground game's
chat region is grabbed once when Quick Translate opens, OCR runs on a worker,
and the pixels are released immediately.  No screenshots are written to disk.
"""

from __future__ import annotations

import ctypes
import gc
import logging
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageGrab, ImageOps, ImageStat


logger = logging.getLogger(__name__)
user32 = ctypes.windll.user32


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


@dataclass(frozen=True)
class ChatReadResult:
    lines: tuple[str, ...] = ()
    elapsed: float = 0.0
    error: str = ""


class ChatCaptureError(RuntimeError):
    """A safe, user-facing capture failure."""


# Normalized client-area rectangles.  They are useful first-run defaults; the
# calibration UI stores a precise rectangle per game and always wins.
DEFAULT_CHAT_REGIONS = {
    "General": (0.015, 0.42, 0.55, 0.90),
    "GTA V Roleplay": (0.015, 0.04, 0.54, 0.45),
    "Valorant / CS": (0.015, 0.48, 0.52, 0.90),
    "EA FC (FIFA)": (0.015, 0.45, 0.52, 0.90),
    "League of Legends / Dota 2": (0.01, 0.49, 0.52, 0.91),
    "Overwatch / Apex": (0.015, 0.40, 0.54, 0.90),
    "Fortnite": (0.015, 0.45, 0.52, 0.90),
    "Minecraft / Roblox": (0.01, 0.08, 0.56, 0.90),
}

_SPACE_RE = re.compile(r"\s+")
_VISIBLE_RE = re.compile(r"[\w\u0600-\u06ff\u0400-\u04ff\u0900-\u097f\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]", re.UNICODE)


def validate_normalized_region(value) -> tuple[float, float, float, float] | None:
    """Validate a JSON-loaded normalized crop rectangle."""
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        x1, y1, x2, y2 = (float(v) for v in value)
    except (TypeError, ValueError):
        return None
    if not (0.0 <= x1 < x2 <= 1.0 and 0.0 <= y1 < y2 <= 1.0):
        return None
    if x2 - x1 < 0.03 or y2 - y1 < 0.03:
        return None
    return x1, y1, x2, y2


def chat_region_for(config: dict, game_mode: str) -> tuple[float, float, float, float]:
    custom = config.get("chat_regions", {})
    if isinstance(custom, dict):
        validated = validate_normalized_region(custom.get(game_mode))
        if validated:
            return validated
    return DEFAULT_CHAT_REGIONS.get(game_mode, DEFAULT_CHAT_REGIONS["General"])


def client_bounds(hwnd: int) -> tuple[int, int, int, int]:
    """Return the visible client rectangle in physical screen coordinates."""
    if not hwnd or not user32.IsWindow(hwnd):
        raise ChatCaptureError("Game window is no longer available")
    rect = RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        raise ChatCaptureError("Could not read the game window")
    origin = POINT(rect.left, rect.top)
    if not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
        raise ChatCaptureError("Could not locate the game window")
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width < 160 or height < 120:
        raise ChatCaptureError("Game window is too small to read")
    return origin.x, origin.y, origin.x + width, origin.y + height


def region_bounds(
    window_bounds: tuple[int, int, int, int],
    normalized: tuple[float, float, float, float],
) -> tuple[int, int, int, int]:
    left, top, right, bottom = window_bounds
    width, height = right - left, bottom - top
    x1, y1, x2, y2 = normalized
    return (
        left + round(width * x1),
        top + round(height * y1),
        left + round(width * x2),
        top + round(height * y2),
    )


def clean_chat_lines(lines, max_lines: int = 4) -> tuple[str, ...]:
    """Normalize OCR output, remove noise/duplicates, and keep recent lines."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in lines or ():
        if not isinstance(raw, str):
            continue
        line = _SPACE_RE.sub(" ", raw).strip(" \t\r\n|")
        if len(line) < 2 or len(line) > 220 or not _VISIBLE_RE.search(line):
            continue
        key = line.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(line)
    return tuple(cleaned[-max(1, min(int(max_lines or 4), 8)):])


def _recognition_language(target_key: str):
    """Map the selected chat/target language to RapidOCR's script model."""
    from rapidocr import LangRec

    text = (target_key or "").casefold()
    if "العربية" in target_key or "arab" in text:
        return LangRec.ARABIC
    if "рус" in text or "russian" in text:
        return LangRec.CYRILLIC
    if "हिं" in target_key or "hindi" in text:
        return LangRec.DEVANAGARI
    if "日本" in target_key or "japan" in text:
        return LangRec.JAPAN
    if "한국" in target_key or "korean" in text:
        return LangRec.KOREAN
    if "中文" in target_key or "chinese" in text:
        return LangRec.CH
    # English, Turkish, Spanish, French, Portuguese, and German share one
    # compact Latin recognizer.
    return LangRec.LATIN


class GameChatReader:
    """Lazy, single-shot OCR service with at most one resident language model."""

    def __init__(self):
        self._engine = None
        self._engine_language = None
        self._lock = threading.Lock()

    @staticmethod
    def capture_region(
        hwnd: int,
        normalized_region: tuple[float, float, float, float],
    ) -> Image.Image:
        bounds = region_bounds(client_bounds(hwnd), normalized_region)
        try:
            # A single in-memory bitmap; ImageGrab does not create a file.
            image = ImageGrab.grab(bbox=bounds, all_screens=True)
        except Exception as exc:
            raise ChatCaptureError("Screen capture is unavailable for this game") from exc
        if image.width < 32 or image.height < 24:
            image.close()
            raise ChatCaptureError("The calibrated chat area is too small")
        return image

    @staticmethod
    def capture_window(hwnd: int) -> tuple[Image.Image, tuple[int, int, int, int]]:
        bounds = client_bounds(hwnd)
        try:
            return ImageGrab.grab(bbox=bounds, all_screens=True), bounds
        except Exception as exc:
            raise ChatCaptureError("Screen capture is unavailable for this game") from exc

    def prepare(self, target_key: str) -> None:
        """Load the selected OCR model once on a background thread."""
        try:
            self._get_engine(target_key)
        except Exception as exc:
            logger.warning("Game-chat OCR preparation failed: %s", str(exc)[:120])

    def _get_engine(self, target_key: str):
        import rapidocr
        from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

        language = _recognition_language(target_key)
        # RapidOCR does not publish a Japanese recognizer for PP-OCRv5 yet;
        # its supported Japanese mobile model is the PP-OCRv4 variant.
        version = (
            OCRVersion.PPOCRV4
            if language == LangRec.JAPAN
            else OCRVersion.PPOCRV5
        )
        model_files = {
            LangRec.LATIN: "latin_PP-OCRv5_rec_mobile.onnx",
            LangRec.ARABIC: "arabic_PP-OCRv5_rec_mobile.onnx",
            LangRec.CYRILLIC: "cyrillic_PP-OCRv5_rec_mobile.onnx",
            LangRec.DEVANAGARI: "devanagari_PP-OCRv5_rec_mobile.onnx",
            LangRec.JAPAN: "japan_PP-OCRv4_rec_mobile.onnx",
            LangRec.KOREAN: "korean_PP-OCRv5_rec_mobile.onnx",
            LangRec.CH: "ch_PP-OCRv5_rec_mobile.onnx",
        }
        models_dir = Path(rapidocr.__file__).resolve().parent / "models"
        detector_path = models_dir / "ch_PP-OCRv5_det_mobile.onnx"
        classifier_path = models_dir / "ch_ppocr_mobile_v2.0_cls_mobile.onnx"
        recognizer_path = models_dir / model_files[language]
        for model_path in (detector_path, classifier_path, recognizer_path):
            if not model_path.is_file() or model_path.stat().st_size <= 0:
                raise FileNotFoundError(f"Bundled OCR model is missing: {model_path.name}")
        with self._lock:
            if self._engine is not None and self._engine_language == language:
                return self._engine
            # Only one recognition session is kept resident.  This bounds RAM if
            # the player switches languages several times during a long session.
            self._engine = None
            self._engine_language = None
            gc.collect()
            self._engine = RapidOCR(params={
                "Global.log_level": "warning",
                "Global.use_cls": False,
                "EngineConfig.onnxruntime.intra_op_num_threads": 1,
                "EngineConfig.onnxruntime.inter_op_num_threads": 1,
                # The library default enlarges the *short* image side to 736px,
                # turning a wide chat strip into a multi-megapixel tensor.  A
                # mobile detector at native size (or capped at 960px) is much
                # faster and keeps CPU pressure away from the game.
                "Det.lang_type": LangRec.CH,
                "Det.model_type": ModelType.MOBILE,
                "Det.ocr_version": OCRVersion.PPOCRV5,
                "Det.limit_type": "max",
                "Det.limit_side_len": 960,
                "Det.model_path": str(detector_path),
                "Cls.model_path": str(classifier_path),
                "Rec.lang_type": language,
                "Rec.model_type": ModelType.MOBILE,
                "Rec.ocr_version": version,
                "Rec.model_path": str(recognizer_path),
            })
            self._engine_language = language
            return self._engine

    def read_image(self, image: Image.Image, target_key: str, max_lines: int = 4) -> ChatReadResult:
        """OCR one image, then eagerly release every pixel reference."""
        started = time.perf_counter()
        output = None
        try:
            # Reject an empty/black capture early (common with protected or
            # exclusive-fullscreen surfaces) without invoking the model.
            sample = ImageOps.grayscale(image).resize((32, 32))
            extrema = ImageStat.Stat(sample).extrema[0]
            sample.close()
            if extrema[1] - extrema[0] < 3:
                return ChatReadResult(error="Chat is not visible or capture is blocked")

            import numpy as np

            engine = self._get_engine(target_key)
            converted = image.convert("RGB")
            pixels = np.array(converted, copy=True)
            converted.close()
            with self._lock:
                output = engine(pixels, use_cls=False, text_score=0.52)
            texts = getattr(output, "txts", ()) or ()
            scores = getattr(output, "scores", ()) or ()
            accepted = [
                text for text, score in zip(texts, scores)
                if isinstance(score, (float, int)) and score >= 0.52
            ]
            return ChatReadResult(
                lines=clean_chat_lines(accepted, max_lines),
                elapsed=time.perf_counter() - started,
            )
        except ModuleNotFoundError:
            return ChatReadResult(error="Game chat reader is not included in this build")
        except Exception as exc:
            logger.warning("One-shot game-chat OCR failed: %s", str(exc)[:160])
            return ChatReadResult(error="Could not read the visible game chat")
        finally:
            output = None
            try:
                image.close()
            except Exception:
                pass
