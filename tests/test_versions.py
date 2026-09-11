import unittest

from remnawave_updater.versions import clean_version, is_update_available, version_tuple


class TestVersions(unittest.TestCase):
    def test_clean_version(self):
        self.assertEqual(clean_version("v3.4.3"), "3.4.3")
        self.assertEqual(clean_version("Remnawave v8.0.0"), "8.0.0")
        self.assertIsNone(clean_version("latest"))

    def test_version_tuple(self):
        self.assertEqual(version_tuple("3.4.1"), (3, 4, 1))
        self.assertEqual(version_tuple("v8.0.0"), (8, 0, 0))

    def test_update_available(self):
        self.assertIs(is_update_available("3.4.0", "3.4.1"), True)
        self.assertIs(is_update_available("3.4.1", "3.4.1"), False)
        self.assertIsNone(is_update_available(None, "3.4.1"))


if __name__ == "__main__":
    unittest.main()
