from __future__ import annotations

import os
import shlex
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path

import paramiko

from .config import CONFIG_DIR, KEY_FILE, ensure_dirs


class SSHError(RuntimeError):
    pass


@dataclass
class SSHHost:
    host: str
    user: str = "root"
    port: int = 22


def ensure_keypair() -> Path:
    ensure_dirs()
    pub = Path(f"{KEY_FILE}.pub")
    if KEY_FILE.exists() and pub.exists():
        return KEY_FILE
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


def _client() -> paramiko.SSHClient:
    ensure_dirs()
    known_hosts = CONFIG_DIR / "known_hosts"
    known_hosts.touch(exist_ok=True)
    os.chmod(known_hosts, 0o600)
    client = paramiko.SSHClient()
    # Trust on first use, then pin the key in our private known_hosts file.
    client.load_host_keys(str(known_hosts))
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    return client


def install_key(target: SSHHost, password: str, timeout: int = 15) -> None:
    ensure_keypair()
    pubkey = Path(f"{KEY_FILE}.pub").read_text(encoding="utf-8").strip()
    client = _client()
    try:
        client.connect(
            target.host,
            port=target.port,
            username=target.user,
            password=password,
            timeout=timeout,
            auth_timeout=timeout,
            banner_timeout=timeout,
            look_for_keys=False,
            allow_agent=False,
        )
        safe_key = shlex.quote(pubkey)
        command = (
            "umask 077; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; "
            f"grep -qxF {safe_key} ~/.ssh/authorized_keys || echo {safe_key} >> ~/.ssh/authorized_keys; "
            "chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys"
        )
        _, stdout, stderr = client.exec_command(command, timeout=timeout)
        code = stdout.channel.recv_exit_status()
        err = stderr.read().decode(errors="replace").strip()
        if code != 0:
            raise SSHError(err or f"remote command exited with {code}")
    except (paramiko.SSHException, socket.error, TimeoutError) as e:
        raise SSHError(str(e)) from e
    finally:
        client.close()
    # Validate key auth immediately.
    run(target, "true", timeout=timeout)


def run(target: SSHHost, command: str, timeout: int = 120) -> tuple[int, str, str]:
    ensure_keypair()
    client = _client()
    try:
        client.connect(
            target.host,
            port=target.port,
            username=target.user,
            key_filename=str(KEY_FILE),
            timeout=min(timeout, 20),
            auth_timeout=min(timeout, 20),
            banner_timeout=min(timeout, 20),
            look_for_keys=False,
            allow_agent=False,
        )
        _, stdout, stderr = client.exec_command(command, timeout=timeout, get_pty=False)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        code = stdout.channel.recv_exit_status()
        return code, out, err
    except (paramiko.SSHException, socket.error, TimeoutError) as e:
        raise SSHError(str(e)) from e
    finally:
        client.close()
