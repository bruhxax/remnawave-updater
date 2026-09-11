from __future__ import annotations

import datetime as dt
import json
import re
import shlex
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .api import RemnawaveAPI
from .config import BACKUP_DIR
from .ssh import SSHHost, run as ssh_run
from .utils import CommandError, must_run, run_local
from .versions import clean_version


@dataclass
class UpdateResult:
    ok: bool
    name: str
    details: str = ""
    backup: str | None = None


@dataclass
class ContainerStatus:
    image: str = "unknown"
    state: str = "unknown"
    health: str = ""
    version: str | None = None

    @property
    def running(self) -> bool:
        return self.state.lower() == "running"

    def summary(self) -> str:
        values = [self.image, self.state]
        if self.health:
            values.append(self.health)
        if self.version:
            values.append(f"v{self.version}")
        return " | ".join(values)


Progress = Callable[[str], None]

PANEL_DIR = "/opt/remnawave"
NODE_DIR = "/opt/remnanode"
SUB_DIR = "/opt/remnawave/subscription"

_VERSION_RE = re.compile(r"v?(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)")


def _stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _image_tag_version(image: str) -> str | None:
    if ":" not in image:
        return None
    tag = image.rsplit(":", 1)[-1]
    if re.fullmatch(r"v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", tag):
        return clean_version(tag)
    return None


def _status_from_inspect(raw: str, version: str | None = None) -> ContainerStatus:
    try:
        data = json.loads(raw)
        if not isinstance(data, list) or not data:
            return ContainerStatus()
        item = data[0]
        config = item.get("Config") or {}
        state = item.get("State") or {}
        image = str(config.get("Image") or "unknown")
        health_obj = state.get("Health") or {}
        env = config.get("Env") or []
        env_map: dict[str, str] = {}
        for entry in env:
            if isinstance(entry, str) and "=" in entry:
                key, value = entry.split("=", 1)
                env_map[key] = value
        detected = version or env_map.get("__RW_METADATA_VERSION") or _image_tag_version(image)
        return ContainerStatus(
            image=image,
            state=str(state.get("Status") or "unknown"),
            health=str(health_obj.get("Status") or ""),
            version=clean_version(detected),
        )
    except Exception:
        return ContainerStatus()


def _container_status_local(container: str, version: str | None = None) -> ContainerStatus:
    code, out, _ = run_local(f"docker inspect {shlex.quote(container)}", timeout=20)
    if code != 0:
        return ContainerStatus(state="not running", version=clean_version(version))
    return _status_from_inspect(out, version=version)


def _container_status_remote(target: SSHHost, container: str, version: str | None = None) -> ContainerStatus:
    code, out, _ = ssh_run(target, f"docker inspect {shlex.quote(container)}", timeout=30)
    if code != 0:
        return ContainerStatus(state="not running", version=clean_version(version))
    return _status_from_inspect(out, version=version)


def _version_from_logs_local(container: str, product: str) -> str | None:
    code, out, _ = run_local(f"docker logs --tail 250 {shlex.quote(container)} 2>&1", timeout=15)
    if code != 0:
        return None
    match = re.findall(re.escape(product) + r"\s+v(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)", out)
    return match[-1] if match else None


def _version_from_logs_remote(target: SSHHost, container: str, product: str) -> str | None:
    code, out, _ = ssh_run(target, f"docker logs --tail 250 {shlex.quote(container)} 2>&1", timeout=20)
    if code != 0:
        return None
    match = re.findall(re.escape(product) + r"\s+v(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)", out)
    return match[-1] if match else None


def panel_status_detail(version: str | None = None) -> ContainerStatus:
    return _container_status_local("remnawave", version=version)


def node_status_detail(target: SSHHost, version: str | None = None) -> ContainerStatus:
    return _container_status_remote(target, "remnanode", version=version)


def sub_status_local_detail() -> ContainerStatus:
    status = _container_status_local("remnawave-subscription-page")
    if not status.version and status.running:
        status.version = _version_from_logs_local("remnawave-subscription-page", "Remnawave Subscription Page")
    return status


def sub_status_remote_detail(target: SSHHost) -> ContainerStatus:
    status = _container_status_remote(target, "remnawave-subscription-page")
    if not status.version and status.running:
        status.version = _version_from_logs_remote(target, "remnawave-subscription-page", "Remnawave Subscription Page")
    return status


def panel_status() -> str:
    return panel_status_detail().summary()


def node_status(target: SSHHost) -> str:
    return node_status_detail(target).summary()


def sub_status_local() -> str:
    return sub_status_local_detail().summary()


def sub_status_remote(target: SSHHost) -> str:
    return sub_status_remote_detail(target).summary()


def backup_panel() -> str:
    path = BACKUP_DIR / _stamp() / "panel"
    path.mkdir(parents=True, exist_ok=True)
    must_run(
        f"cd {PANEL_DIR} && "
        f"tar -czf {shlex.quote(str(path / 'config.tar.gz'))} "
        "--ignore-failed-read docker-compose.yml .env 2>/dev/null || true"
    )
    code, _, err = run_local(
        "docker exec remnawave-db sh -lc 'pg_dump -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" -Fc' "
        f"> {shlex.quote(str(path / 'database.dump'))}",
        timeout=180,
    )
    if code != 0:
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
        version = None
        try:
            version = api.get_panel_version()
        except Exception:
            pass
        return UpdateResult(True, name, panel_status_detail(version).summary(), backup)
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
        code, _, err = ssh_run(target, f"cd {NODE_DIR} && docker compose down && docker compose up -d", timeout=300)
        if code != 0:
            raise CommandError(err.strip() or "docker compose restart failed")
        if progress:
            progress("health")
        if not _wait_remote_container(target, "remnanode", timeout):
            raise CommandError("remnanode container did not become running")
        connected = _wait_node_connected(api, node["uuid"], timeout)
        current = api.get_node(node["uuid"])
        detail = node_status_detail(target, current.node_version if current else None).summary()
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
        return UpdateResult(True, name, sub_status_local_detail().summary(), backup)
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
        code, _, err = ssh_run(target, f"cd {SUB_DIR} && docker compose down && docker compose up -d", timeout=300)
        if code != 0:
            raise CommandError(err.strip() or "docker compose restart failed")
        if progress:
            progress("health")
        if not _wait_remote_container(target, "remnawave-subscription-page", timeout):
            raise CommandError("subscription container did not become running")
        return UpdateResult(True, name, sub_status_remote_detail(target).summary(), backup)
    except Exception as e:
        return UpdateResult(False, name, str(e), backup)
