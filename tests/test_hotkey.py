import unittest

from chat_bridge.hotkey import MOD_CONTROL, MOD_SHIFT, parse_hotkey


class HotkeyParserTests(unittest.TestCase):
    def test_parses_default_hotkey(self):
        modifiers, key = parse_hotkey("ctrl+shift+t")
        self.assertEqual(modifiers, MOD_CONTROL | MOD_SHIFT)
        self.assertEqual(key, ord("T"))

    def test_only_accepts_supported_function_key_range(self):
        _, f24 = parse_hotkey("ctrl+f24")
        _, f25 = parse_hotkey("ctrl+f25")
        self.assertEqual(f24, 0x87)
        self.assertEqual(f25, 0)


if __name__ == "__main__":
    unittest.main()
