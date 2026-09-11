from __future__ import annotations

import datetime as dt
import shlex
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .api import RemnawaveAPI
from .config import BACKUP_DIR
from .ssh import SSHHost, run as ssh_run
from .utils import CommandError, must_run, run_local


@dataclass
class UpdateResult:
    ok: bool
    name: str
    details: str = ""
    backup: str | None = None


Progress = Callable[[str], None]

PANEL_DIR = "/opt/remnawave"
NODE_DIR = "/opt/remnanode"
SUB_DIR = "/opt/remnawave/subscription"


def _stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _container_info_local(container: str) -> str:
    code, out, _ = run_local(
        "docker inspect -f '{{.Config.Image}} | {{.State.Status}} | {{if .State.Health}}{{.State.Health.Status}}{{end}}' "
        + shlex.quote(container)
    )
    return out.strip() if code == 0 else "not running"


def _container_info_remote(target: SSHHost, container: str) -> str:
    cmd = (
        "docker inspect -f '{{.Config.Image}} | {{.State.Status}} | "
        "{{if .State.Health}}{{.State.Health.Status}}{{end}}' " + shlex.quote(container)
    )
    code, out, _ = ssh_run(target, cmd, timeout=30)
    return out.strip() if code == 0 else "not running"


def panel_status() -> str:
    return _container_info_local("remnawave")


def node_status(target: SSHHost) -> str:
    return _container_info_remote(target, "remnanode")


def sub_status_local() -> str:
    return _container_info_local("remnawave-subscription-page")


def sub_status_remote(target: SSHHost) -> str:
    return _container_info_remote(target, "remnawave-subscription-page")


def backup_panel() -> str:
    path = BACKUP_DIR / _stamp() / "panel"
    path.mkdir(parents=True, exist_ok=True)
    # Configuration backup.
    must_run(
        f"cd {PANEL_DIR} && "
        f"tar -czf {shlex.quote(str(path / 'config.tar.gz'))} "
        "--ignore-failed-read docker-compose.yml .env 2>/dev/null || true"
    )
    # Database dump using the DB container's own environment variables.
    code, _, err = run_local(
        "docker exec remnawave-db sh -lc 'pg_dump -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" -Fc' "
        f"> {shlex.quote(str(path / 'database.dump'))}",
        timeout=180,
    )
    if code != 0:
        # Keep config backup even if database dump is unavailable.
        (path / "DATABASE_BACKUP_FAILED.txt").write_text(err or "pg_dump failed\n", encoding="utf-8")
    return str(path)


def backup_remote(target: SSHHost, component: str, source_dir: str) -> str:
    remote = f"/var/backups/remnawave-updater/{_stamp()}/{component}"
    cmd = (
        f"mkdir -p {shlex.quote(remote)} && "
        f"cd {shlex.quote(source_dir)} && "
        f"tar -czf {shlex.quote(remote + '/config.tar.gz')} --ignore-failed-read docker-compose.yml .env 2>/dev/null || true"
    )
    code, _, err = ssh_run(target, cmd, timeout=60)
    if code != 0:
        raise CommandError(err.strip() or "remote backup failed")
    return f"{target.host}:{remote}"


def backup_sub_local() -> str:
    path = BACKUP_DIR / _stamp() / "subscription"
    path.mkdir(parents=True, exist_ok=True)
    must_run(
        f"cd {SUB_DIR} && "
        f"tar -czf {shlex.quote(str(path / 'config.tar.gz'))} "
        "--ignore-failed-read docker-compose.yml .env 2>/dev/null || true"
    )
    return str(path)


def _wait_local_container(container: str, timeout: int) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        code, out, _ = run_local(f"docker inspect -f '{{{{.State.Running}}}}' {shlex.quote(container)}")
        if code == 0 and out.strip().lower() == "true":
            return True
        time.sleep(2)
    return False


def _wait_remote_container(target: SSHHost, container: str, timeout: int) -> bool:
    deadline = time.time() + timeout
    cmd = f"docker inspect -f '{{{{.State.Running}}}}' {shlex.quote(container)}"
    while time.time() < deadline:
        try:
            code, out, _ = ssh_run(target, cmd, timeout=20)
            if code == 0 and out.strip().lower() == "true":
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def _wait_api(api: RemnawaveAPI, timeout: int) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if api.health():
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


def _wait_node_connected(api: RemnawaveAPI, uuid: str, timeout: int) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            node = api.get_node(uuid)
            if node and node.is_connected is True:
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


def update_panel(api: RemnawaveAPI, timeout: int = 90, do_backup: bool = True, progress: Progress | None = None) -> UpdateResult:
    name = "Panel"
    backup = None
    try:
        if do_backup:
            if progress:
                progress("backup")
            backup = backup_panel()
        if progress:
            progress("pull")
        must_run(f"cd {PANEL_DIR} && docker compose pull", timeout=600)
        if progress:
            progress("restart")
        must_run(f"cd {PANEL_DIR} && docker compose down && docker compose up -d", timeout=300)
        if progress:
            progress("health")
        if not _wait_local_container("remnawave", timeout):
            raise CommandError("remnawave container did not become running")
        if not _wait_api(api, timeout):
            raise CommandError("Panel API health check timed out")
        return UpdateResult(True, name, panel_status(), backup)
    except Exception as e:
        return UpdateResult(False, name, str(e), backup)


def update_node(
    api: RemnawaveAPI,
    node: dict,
    timeout: int = 90,
    do_backup: bool = True,
    progress: Progress | None = None,
) -> UpdateResult:
    name = node.get("name", node.get("host", "Node"))
    target = SSHHost(node["host"], node.get("user", "root"), int(node.get("port", 22)))
    backup = None
    try:
        if do_backup:
            if progress:
                progress("backup")
            backup = backup_remote(target, "node", NODE_DIR)
        if progress:
            progress("pull")
        code, _, err = ssh_run(target, f"cd {NODE_DIR} && docker compose pull", timeout=600)
        if code != 0:
            raise CommandError(err.strip() or "docker compose pull failed")
        if progress:
            progress("restart")
        code, _, err = ssh_run(
            target,
            f"cd {NODE_DIR} && docker compose down && docker compose up -d",
            timeout=300,
        )
        if code != 0:
            raise CommandError(err.strip() or "docker compose restart failed")
        if progress:
            progress("health")
        if not _wait_remote_container(target, "remnanode", timeout):
            raise CommandError("remnanode container did not become running")
        connected = _wait_node_connected(api, node["uuid"], timeout)
        detail = node_status(target)
        if not connected:
            detail += " | panel connection: not confirmed"
        return UpdateResult(True, name, detail, backup)
    except Exception as e:
        return UpdateResult(False, name, str(e), backup)


def update_sub_local(timeout: int = 90, do_backup: bool = True, progress: Progress | None = None) -> UpdateResult:
    name = "Subscription Page"
    backup = None
    try:
        if do_backup:
            if progress:
                progress("backup")
            backup = backup_sub_local()
        if progress:
            progress("pull")
        must_run(f"cd {SUB_DIR} && docker compose pull", timeout=600)
        if progress:
            progress("restart")
        must_run(f"cd {SUB_DIR} && docker compose down && docker compose up -d", timeout=300)
        if progress:
            progress("health")
        if not _wait_local_container("remnawave-subscription-page", timeout):
            raise CommandError("subscription container did not become running")
        return UpdateResult(True, name, sub_status_local(), backup)
    except Exception as e:
        return UpdateResult(False, name, str(e), backup)


def update_sub_remote(
    target: SSHHost,
    timeout: int = 90,
    do_backup: bool = True,
    progress: Progress | None = None,
) -> UpdateResult:
    name = "Subscription Page"
    backup = None
    try:
        if do_backup:
            if progress:
                progress("backup")
            backup = backup_remote(target, "subscription", SUB_DIR)
        if progress:
            progress("pull")
        code, _, err = ssh_run(target, f"cd {SUB_DIR} && docker compose pull", timeout=600)
        if code != 0:
            raise CommandError(err.strip() or "docker compose pull failed")
        if progress:
            progress("restart")
        code, _, err = ssh_run(
            target,
            f"cd {SUB_DIR} && docker compose down && docker compose up -d",
            timeout=300,
        )
        if code != 0:
            raise CommandError(err.strip() or "docker compose restart failed")
        if progress:
            progress("health")
        if not _wait_remote_container(target, "remnawave-subscription-page", timeout):
            raise CommandError("subscription container did not become running")
        return UpdateResult(True, name, sub_status_remote(target), backup)
    except Exception as e:
        return UpdateResult(False, name, str(e), backup)
