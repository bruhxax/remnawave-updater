import unittest
from unittest.mock import patch

from remnawave_updater.ssh import SSHHost, _target


class TestSSH(unittest.TestCase):
    def test_target(self):
        self.assertEqual(_target(SSHHost("1.2.3.4", "root", 22)), "root@1.2.3.4")

    @patch("remnawave_updater.ssh.shutil.which")
    def test_missing_ssh_is_reported(self, which):
        which.return_value = None
        from remnawave_updater.ssh import SSHError, run
        with self.assertRaises(SSHError):
            run(SSHHost("example.invalid"), "true")


if __name__ == "__main__":
    unittest.main()
