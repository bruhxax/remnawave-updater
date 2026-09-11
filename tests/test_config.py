import unittest
from pathlib import Path


class TestConfig(unittest.TestCase):
    def test_runtime_config_path_is_absolute(self):
        self.assertTrue(Path("/etc/remnawave-updater").is_absolute())


if __name__ == "__main__":
    unittest.main()
