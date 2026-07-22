import os
import tempfile
import unittest
import json

# config.py creates its application-data directory at import time. Keep all
# test data in a temporary directory instead of the developer's real profile.
_APPDATA = tempfile.TemporaryDirectory()
os.environ["APPDATA"] = _APPDATA.name

from chat_bridge import config


class ConfigStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous_paths = (
            config.API_KEY_FILE,
            config.CONFIG_FILE,
            config.HISTORY_FILE,
        )
        config.API_KEY_FILE = os.path.join(self.temp.name, ".api_key")
        config.CONFIG_FILE = os.path.join(self.temp.name, ".config.json")
        config.HISTORY_FILE = os.path.join(self.temp.name, "history.json")

    def tearDown(self):
        config.API_KEY_FILE, config.CONFIG_FILE, config.HISTORY_FILE = self.previous_paths
        self.temp.cleanup()

    def test_api_key_round_trip_uses_protected_storage(self):
        self.assertTrue(config.save_api_key("test-secret"))
        with open(config.API_KEY_FILE, encoding="utf-8") as stored:
            self.assertTrue(stored.read().startswith("DPAPI:"))
        self.assertEqual(config.load_api_key(), "test-secret")
        self.assertTrue(config.save_api_key(""))
        self.assertFalse(os.path.exists(config.API_KEY_FILE))

    def test_portable_api_key_is_encrypted_then_removed(self):
        old_app_dir = config.APP_DIR
        portable_dir = tempfile.TemporaryDirectory()
        try:
            config.APP_DIR = portable_dir.name
            portable_key = os.path.join(portable_dir.name, ".api_key")
            with open(portable_key, "w", encoding="utf-8") as stored:
                stored.write("legacy-secret")

            config._migrate_old_files()

            self.assertFalse(os.path.exists(portable_key))
            with open(config.API_KEY_FILE, encoding="utf-8") as stored:
                self.assertTrue(stored.read().startswith("DPAPI:"))
            self.assertEqual(config.load_api_key(), "legacy-secret")
        finally:
            config.APP_DIR = old_app_dir
            portable_dir.cleanup()

    def test_config_and_history_round_trip(self):
        cfg = config.load_config()
        self.assertEqual(cfg["mode"], "copy")
        self.assertFalse(cfg["history_enabled"])
        self.assertTrue(cfg["performance_cache_enabled"])
        self.assertFalse(cfg["chat_context_enabled"])
        self.assertEqual(cfg["chat_regions"], {})
        self.assertEqual(cfg["chat_context_max_lines"], 4)
        cfg["tone"] = "Chill"
        self.assertTrue(config.save_config(cfg))
        self.assertEqual(config.load_config()["tone"], "Chill")

        history = config.add_history_entry(
            "مرحبا", "hello", [], source_lang="Arabic", target_lang="English"
        )
        loaded_history = config.load_history()
        self.assertEqual(len(loaded_history), 1)
        self.assertEqual(loaded_history[0]["source_text"], "مرحبا")
        self.assertEqual(loaded_history[0]["target_text"], "hello")
        self.assertEqual(loaded_history[0]["source_lang"], "Arabic")
        with open(config.HISTORY_FILE, encoding="utf-8") as stored:
            on_disk = stored.read()
        self.assertNotIn("مرحبا", on_disk)
        self.assertNotIn("hello", on_disk)
        self.assertIn('"protection": "DPAPI"', on_disk)
        self.assertTrue(config.clear_history())
        self.assertEqual(config.load_history(), [])

    def test_legacy_config_is_migrated_to_safe_send_mode(self):
        with open(config.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"mode": "paste_send"}, f)
        self.assertEqual(config.load_config()["mode"], "copy")

    def test_legacy_gemini_label_preserves_the_users_25_choice(self):
        old_label = "⚡ Gemini 2.5 Flash-Lite — fastest & cheapest (default)"
        with open(config.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"model": old_label, "history_enabled": False}, f)
        loaded = config.load_config()
        self.assertIn(loaded["model"], config.MODEL_OPTIONS)
        self.assertEqual(
            config.MODEL_OPTIONS[loaded["model"]], config.GEMINI_25_FLASH_LITE_MODEL
        )

    def test_legacy_plaintext_history_is_migrated_and_encrypted(self):
        legacy = [{"ar": "مرحبا", "en": "hello", "ts": "2026-01-01 00:00:00"}]
        with open(config.HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(legacy, f, ensure_ascii=False)

        loaded = config.load_history()
        self.assertEqual(loaded[0]["source_text"], "مرحبا")
        self.assertEqual(loaded[0]["source_lang"], "Unknown")
        self.assertEqual(loaded[0]["target_lang"], "Unknown")
        with open(config.HISTORY_FILE, encoding="utf-8") as f:
            migrated = json.load(f)
        self.assertEqual(migrated["version"], 2)
        self.assertEqual(migrated["protection"], "DPAPI")
        self.assertNotIn("مرحبا", migrated["payload"])

    def test_invalid_new_config_values_fall_back_to_safe_defaults(self):
        with open(config.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "chat_context_enabled": "yes",
                "chat_regions": [],
                "chat_context_max_lines": 100,
            }, f)
        loaded = config.load_config()
        self.assertFalse(loaded["chat_context_enabled"])
        self.assertEqual(loaded["chat_regions"], {})
        self.assertEqual(loaded["chat_context_max_lines"], 8)

    def test_mutable_defaults_are_not_shared_between_loads(self):
        first = config.load_config()
        first["chat_regions"]["General"] = [0.1, 0.2, 0.3, 0.4]
        self.assertEqual(config.load_config()["chat_regions"], {})

    def test_oversized_custom_rules_are_rejected(self):
        cfg = config.load_config()
        cfg["custom_rules"] = "x" * (config.MAX_CUSTOM_RULES_CHARS + 1)
        self.assertFalse(config.save_config(cfg))
        self.assertFalse(os.path.exists(config.CONFIG_FILE))


if __name__ == "__main__":
    unittest.main()
