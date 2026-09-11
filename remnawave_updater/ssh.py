from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import CONFIG_DIR, KEY_FILE, ensure_dirs


class SSHError(RuntimeError):
    pass


@dataclass
class SSHHost:
    host: str
    user: str = "root"
    port: int = 22


def _known_hosts() -> Path:
    ensure_dirs()
    path = CONFIG_DIR / "known_hosts"
    path.touch(exist_ok=True)
    os.chmod(path, 0o600)
    return path


def ensure_keypair() -> Path:
    ensure_dirs()
    pub = Path(f"{KEY_FILE}.pub")
    if KEY_FILE.exists() and pub.exists():
        os.chmod(KEY_FILE, 0o600)
        return KEY_FILE
    if shutil.which("ssh-keygen") is None:
        raise SSHError("ssh-keygen not found")
    result = subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(KEY_FILE), "-C", "remnawave-updater"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SSHError(result.stderr.strip() or "ssh-keygen failed")
    os.chmod(KEY_FILE, 0o600)
    os.chmod(pub, 0o644)
    return KEY_FILE


def _target(target: SSHHost) -> str:
    return f"{target.user}@{target.host}"


def install_key(target: SSHHost, timeout: int = 90) -> None:
    """Install the updater key using the system OpenSSH client.

    The ssh process inherits the terminal, so a password (if required) is entered
    directly into OpenSSH. Python never receives or stores the password.
    """
    ensure_keypair()
    ssh = shutil.which("ssh")
    if ssh is None:
        raise SSHError("ssh not found (install openssh-client)")

    pubkey = Path(f"{KEY_FILE}.pub").read_text(encoding="utf-8").strip()
    quoted_key = shlex.quote(pubkey)
    remote_command = (
        "umask 077; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; "
        f"grep -qxF {quoted_key} ~/.ssh/authorized_keys || printf '%s\\n' {quoted_key} >> ~/.ssh/authorized_keys; "
        "chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys"
    )
    known_hosts = _known_hosts()
    connect_timeout = max(3, min(timeout, 20))
    cmd = [
        ssh,
        "-p",
        str(target.port),
        "-o",
        f"UserKnownHostsFile={known_hosts}",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        f"ConnectTimeout={connect_timeout}",
        "-o",
        "PubkeyAuthentication=no",
        "-o",
        "PreferredAuthentications=keyboard-interactive,password",
        "-o",
        "NumberOfPasswordPrompts=3",
        _target(target),
        remote_command,
    ]
    try:
        result = subprocess.run(cmd, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise SSHError("SSH key installation timed out") from exc
    except OSError as exc:
        raise SSHError(str(exc)) from exc
    if result.returncode != 0:
        raise SSHError(f"SSH key installation exited with code {result.returncode}")

    code, _, err = run(target, "true", timeout=20)
    if code != 0:
        raise SSHError(err.strip() or "SSH key authentication failed")


def _ssh_command(target: SSHHost, command: str, timeout: int) -> list[str]:
    ensure_keypair()
    known_hosts = _known_hosts()
    connect_timeout = max(3, min(timeout, 20))
    return [
        "ssh",
        "-i",
        str(KEY_FILE),
        "-p",
        str(target.port),
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "BatchMode=yes",
        "-o",
        f"UserKnownHostsFile={known_hosts}",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        f"ConnectTimeout={connect_timeout}",
        "-o",
        "ServerAliveInterval=15",
        "-o",
        "ServerAliveCountMax=2",
        _target(target),
        command,
    ]


def run(target: SSHHost, command: str, timeout: int = 120) -> tuple[int, str, str]:
    if shutil.which("ssh") is None:
        raise SSHError("ssh not found")
    try:
        proc = subprocess.run(
            _ssh_command(target, command, timeout),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        raise SSHError(f"SSH command timed out after {timeout}s") from exc
    except OSError as exc:
        raise SSHError(str(exc)) from exc
