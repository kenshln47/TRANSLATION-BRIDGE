import ctypes
import unittest

from chat_bridge.app import App, INPUT, WindowTarget


class AppHelperTests(unittest.TestCase):
    def test_sendinput_structure_matches_windows_abi(self):
        expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
        self.assertEqual(ctypes.sizeof(INPUT), expected)
        self.assertTrue(App._send_key_events([]))

    def test_window_identity_requires_handle_and_process(self):
        original = WindowTarget(100, 200, "Game")
        self.assertTrue(App._same_target(original, WindowTarget(100, 200, "Renamed")))
        self.assertFalse(App._same_target(original, WindowTarget(100, 201, "Other process")))
        self.assertFalse(App._same_target(original, WindowTarget(101, 200, "Other window")))


if __name__ == "__main__":
    unittest.main()
