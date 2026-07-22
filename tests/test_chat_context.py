import unittest
from unittest.mock import patch

from rapidocr import LangRec, ModelType, OCRVersion

from chat_bridge.chat_context import (
    DEFAULT_CHAT_REGIONS,
    GameChatReader,
    chat_region_for,
    clean_chat_lines,
    region_bounds,
    validate_normalized_region,
)


class ChatContextTests(unittest.TestCase):
    def test_custom_region_wins_and_is_scaled_to_client(self):
        cfg = {"chat_regions": {"General": [0.1, 0.2, 0.6, 0.8]}}
        region = chat_region_for(cfg, "General")
        self.assertEqual(region, (0.1, 0.2, 0.6, 0.8))
        self.assertEqual(region_bounds((100, 50, 1100, 550), region), (200, 150, 700, 450))

    def test_invalid_custom_region_uses_safe_game_default(self):
        cfg = {"chat_regions": {"GTA V Roleplay": [0.8, 0.2, 0.1, 0.3]}}
        self.assertEqual(
            chat_region_for(cfg, "GTA V Roleplay"),
            DEFAULT_CHAT_REGIONS["GTA V Roleplay"],
        )
        self.assertIsNone(validate_normalized_region([0, 0, 0.01, 0.01]))

    def test_ocr_lines_are_bounded_deduplicated_and_normalized(self):
        lines = [
            "  Player1:   Rotate B  ",
            "Player1: Rotate B",
            "---",
            "Player2: wait",
            "Player3: go",
        ]
        self.assertEqual(
            clean_chat_lines(lines, max_lines=2),
            ("Player2: wait", "Player3: go"),
        )

    def test_japanese_uses_supported_recognizer_and_fast_detector(self):
        sentinel = object()
        with patch("rapidocr.RapidOCR", return_value=sentinel) as rapid:
            self.assertIs(GameChatReader()._get_engine("日本語"), sentinel)

        params = rapid.call_args.kwargs["params"]
        self.assertEqual(params["Rec.lang_type"], LangRec.JAPAN)
        self.assertEqual(params["Rec.ocr_version"], OCRVersion.PPOCRV4)
        self.assertEqual(params["Det.model_type"], ModelType.MOBILE)
        self.assertEqual(params["Det.ocr_version"], OCRVersion.PPOCRV5)
        self.assertEqual(params["Det.limit_type"], "max")


if __name__ == "__main__":
    unittest.main()
