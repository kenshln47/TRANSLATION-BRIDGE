import re
import unittest

from chat_bridge.version import VERSION_TUPLE, __version__


class ReleaseVersionTests(unittest.TestCase):
    def test_release_version_is_valid_and_matches_windows_tuple(self):
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")
        parsed = tuple(int(part) for part in __version__.split("."))
        self.assertEqual(VERSION_TUPLE, (*parsed, 0))
        self.assertEqual(len(VERSION_TUPLE), 4)


if __name__ == "__main__":
    unittest.main()
