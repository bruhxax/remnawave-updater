from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path


class CommandError(RuntimeError):
    pass


def run_local(command: str, timeout: int = 300) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["bash", "-lc", command],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def must_run(command: str, timeout: int = 300) -> str:
    code, out, err = run_local(command, timeout=timeout)
    if code != 0:
        raise CommandError((err or out).strip() or f"Command failed: {command}")
    return out


def shell_quote(value: str | Path) -> str:
    return shlex.quote(str(value))


def require_root() -> bool:
    return os.geteuid() == 0
