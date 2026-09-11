import os
from pathlib import Path


def test_placeholder():
    # Runtime config is deliberately outside the project and root-only.
    assert Path("/etc/remnawave-updater").is_absolute()
