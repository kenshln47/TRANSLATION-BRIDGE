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

    def test_config_and_history_round_trip(self):
        cfg = config.load_config()
        self.assertEqual(cfg["mode"], "copy")
        self.assertFalse(cfg["history_enabled"])
        self.assertTrue(cfg["performance_cache_enabled"])
        cfg["tone"] = "Chill"
        self.assertTrue(config.save_config(cfg))
        self.assertEqual(config.load_config()["tone"], "Chill")

        history = config.add_history_entry("مرحبا", "hello", [])
        self.assertEqual(len(config.load_history()), 1)
        self.assertTrue(config.clear_history())
        self.assertEqual(config.load_history(), [])

    def test_legacy_config_is_migrated_to_safe_send_mode(self):
        with open(config.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"mode": "paste_send"}, f)
        self.assertEqual(config.load_config()["mode"], "copy")


if __name__ == "__main__":
    unittest.main()
