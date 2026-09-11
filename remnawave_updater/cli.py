from __future__ import annotations

import argparse
import getpass
import shutil
import sys
from pathlib import Path

from . import __version__
from .api import NodeInfo, RemnawaveAPI
from .config import CONFIG_FILE, KEY_FILE, is_configured, load_config, save_config
from .i18n import tr
from .ssh import SSHError, SSHHost, ensure_keypair, install_key, run as ssh_run
from .updater import (
    NODE_DIR,
    PANEL_DIR,
    SUB_DIR,
    node_status,
    panel_status,
    sub_status_local,
    sub_status_remote,
    update_node,
    update_panel,
    update_sub_local,
    update_sub_remote,
)
from .utils import require_root
from . import ui


def _header(lang: str) -> None:
    ui.header(f"🌊 {tr(lang, 'app_title')}", tr(lang, "app_subtitle"))


def _pause(lang: str) -> None:
    ui.pause(tr(lang, "press_enter"))


def _select_language(current: str | None = None) -> str:
    ui.header("Language / Язык")
    ui.menu(["🇷🇺 Русский", "🇬🇧 English"])
    default = "2" if current == "en" else "1"
    choice = ui.choose(">", ["1", "2"], default=default)
    return "ru" if choice == "1" else "en"


def _api_from(config: dict) -> RemnawaveAPI:
    panel = config["panel"]
    return RemnawaveAPI(panel["url"], panel["token"], bool(panel.get("verify_ssl", True)))


def _configure_panel(config: dict, lang: str) -> RemnawaveAPI:
    while True:
        default_url = config.get("panel", {}).get("url") or None
        url = ui.prompt(tr(lang, "panel_url"), default=default_url).strip()
        old_token = config.get("panel", {}).get("token", "")
        token = getpass.getpass(f"{tr(lang, 'panel_token')}: ").strip() or old_token
        verify = ui.confirm(tr(lang, "verify_ssl"), default=True)
        api = RemnawaveAPI(url, token, verify)
        ui.info(tr(lang, "testing_api"))
        try:
            api.health()
            nodes = api.get_nodes()
            ui.ok(f"{tr(lang, 'api_ok')} · {tr(lang, 'nodes_found', count=len(nodes))}")
            config["panel"] = {"url": url.rstrip("/"), "token": token, "verify_ssl": verify}
            save_config(config)
            print(ui.dim(tr(lang, "token_saved")))
            return api
        except Exception as exc:
            ui.error(tr(lang, "api_fail", error=exc))
            if not ui.confirm("Retry? / Повторить?", default=True):
                raise SystemExit(1)


def _try_key(target: SSHHost) -> bool:
    try:
        code, _, _ = ssh_run(target, "true", timeout=15)
        return code == 0
    except Exception:
        return False


def _provision_key(target: SSHHost, lang: str) -> None:
    ui.notice(tr(lang, "ssh_copy_notice"), level="info")
    install_key(target)


def _configure_one_node(config: dict, lang: str, node: NodeInfo) -> bool:
    if not ui.confirm(tr(lang, "node_configure", name=node.name, host=node.host), default=True):
        ui.warn(tr(lang, "node_skipped"))
        return False

    while True:
        user = ui.prompt(tr(lang, "ssh_user"), default="root").strip() or "root"
        port = ui.prompt_int(tr(lang, "ssh_port"), default=22)
        target = SSHHost(node.host, user, port)
        ui.info(tr(lang, "ssh_connecting", host=node.host))
        try:
            if not _try_key(target):
                _provision_key(target, lang)
            code, _, err = ssh_run(target, f"test -f {NODE_DIR}/docker-compose.yml", timeout=20)
            if code != 0:
                raise SSHError(err.strip() or f"{NODE_DIR}/docker-compose.yml not found")
            entry = {"uuid": node.uuid, "name": node.name, "host": node.host, "user": user, "port": port}
            config.setdefault("nodes", [])
            config["nodes"] = [item for item in config["nodes"] if item.get("uuid") != node.uuid]
            config["nodes"].append(entry)
            save_config(config)
            ui.ok(tr(lang, "ssh_ok"))
            return True
        except Exception as exc:
            ui.error(tr(lang, "ssh_fail", error=exc))
            if not ui.confirm(tr(lang, "retry_node"), default=True):
                ui.warn(tr(lang, "node_skipped"))
                return False


def _configure_nodes(config: dict, lang: str, api: RemnawaveAPI, only_new: bool = False) -> None:
    nodes = api.get_nodes()
    existing = {item.get("uuid"): item for item in config.get("nodes", [])}

    changed = False
    for node in nodes:
        old = existing.get(node.uuid)
        if old and (old.get("name") != node.name or old.get("host") != node.host):
            old["name"] = node.name
            old["host"] = node.host
            changed = True
    if changed:
        config["nodes"] = list(existing.values())
        save_config(config)

    pending = [node for node in nodes if node.uuid not in existing]
    if only_new:
        if not pending:
            ui.ok(tr(lang, "sync_none"))
            return
        print(tr(lang, "sync_new", count=len(pending)))
        nodes = pending
    else:
        print(tr(lang, "nodes_found", count=len(nodes)))
        nodes = pending if existing else nodes
        if existing and not pending:
            return

    for node in nodes:
        _configure_one_node(config, lang, node)


def _configure_subscription(config: dict, lang: str) -> None:
    detected = Path(f"{SUB_DIR}/docker-compose.yml").exists()
    if detected:
        ui.ok(tr(lang, "sub_detected_local"))

    ui.heading(tr(lang, "sub_where"))
    labels = [tr(lang, "sub_local"), tr(lang, "sub_remote"), tr(lang, "sub_none")]
    if detected:
        labels[0] += "  ✓"
    ui.menu(labels)
    default = "1" if detected else "3"
    choice = ui.choose(tr(lang, "choose"), ["1", "2", "3"], default=default)

    if choice == "3":
        config["subscription"] = {"mode": "disabled"}
        save_config(config)
        return

    if choice == "1":
        if not detected:
            ui.warn(f"{SUB_DIR}/docker-compose.yml not found")
            if not ui.confirm("Save anyway? / Всё равно сохранить?", default=False):
                return
        config["subscription"] = {"mode": "local"}
        save_config(config)
        return

    host = ui.prompt(tr(lang, "sub_host")).strip()
    user = ui.prompt(tr(lang, "ssh_user"), default="root").strip() or "root"
    port = ui.prompt_int(tr(lang, "ssh_port"), default=22)
    target = SSHHost(host, user, port)
    try:
        if not _try_key(target):
            _provision_key(target, lang)
        code, _, err = ssh_run(target, f"test -f {SUB_DIR}/docker-compose.yml", timeout=20)
        if code != 0:
            raise SSHError(err.strip() or f"{SUB_DIR}/docker-compose.yml not found")
        config["subscription"] = {"mode": "remote", "host": host, "user": user, "port": port}
        save_config(config)
        ui.ok(tr(lang, "ssh_ok"))
    except Exception as exc:
        ui.error(tr(lang, "ssh_fail", error=exc))


def setup(config: dict | None = None) -> dict:
    config = config or load_config()
    lang = _select_language(config.get("language"))
    config["language"] = lang
    save_config(config)
    _header(lang)
    ui.notice(tr(lang, "major_warning"), level="warning")
    ui.heading(tr(lang, "setup_title"))
    ensure_keypair()
    api = _configure_panel(config, lang)
    _configure_nodes(config, lang, api)
    _configure_subscription(config, lang)
    save_config(config)
    ui.ok(ui.bold(tr(lang, "setup_done")))
    return config


def _progress_printer(lang: str):
    mapping = {
        "backup": tr(lang, "backup_creating"),
        "pull": tr(lang, "step_pull"),
        "restart": tr(lang, "step_restart"),
        "health": tr(lang, "step_health"),
    }

    def emit(step: str) -> None:
        ui.info(mapping.get(step, step))

    return emit


def _print_result(lang: str, result) -> None:
    if result.backup:
        print(ui.dim(f"  {tr(lang, 'backup_ok', path=result.backup)}"))
    if result.ok:
        ui.ok(ui.bold(tr(lang, "updated_ok", name=result.name)))
        if result.details:
            print(ui.dim(f"  {result.details}"))
    else:
        ui.error(ui.bold(tr(lang, "updated_fail", name=result.name, error=result.details)))


def _update_panel_interactive(config: dict, lang: str) -> None:
    ui.notice(tr(lang, "major_warning"), level="warning")
    if not ui.confirm(tr(lang, "confirm_update"), default=False):
        return
    result = update_panel(
        _api_from(config),
        timeout=int(config["settings"]["healthcheck_timeout"]),
        do_backup=bool(config["settings"]["backup_before_update"]),
        progress=_progress_printer(lang),
    )
    _print_result(lang, result)
    _pause(lang)


def _select_node_entries(config: dict, lang: str) -> list[dict]:
    nodes = config.get("nodes", [])
    if not nodes:
        ui.warn(tr(lang, "no_nodes"))
        return []
    rows = []
    for index, node in enumerate(nodes, 1):
        rows.append([
            str(index),
            node.get("name", "Node"),
            f"{node.get('user', 'root')}@{node.get('host')}:{node.get('port', 22)}",
        ])
    ui.table(["#", "Node", "SSH"], rows)
    raw = ui.prompt(tr(lang, "select_nodes")).strip()
    try:
        indexes = sorted({int(value.strip()) for value in raw.split(",") if value.strip()})
        if not indexes or any(index < 1 or index > len(nodes) for index in indexes):
            raise ValueError
        return [nodes[index - 1] for index in indexes]
    except ValueError:
        ui.error(tr(lang, "invalid_selection"))
        return []


def _update_nodes_interactive(config: dict, lang: str) -> None:
    nodes = config.get("nodes", [])
    if not nodes:
        ui.warn(tr(lang, "no_nodes"))
        _pause(lang)
        return

    ui.heading(tr(lang, "nodes_menu"))
    ui.menu([tr(lang, "nodes_all"), tr(lang, "nodes_select"), tr(lang, "nodes_back")])
    choice = ui.choose(tr(lang, "choose"), ["1", "2", "3"], default="1")
    if choice == "3":
        return
    selected = nodes if choice == "1" else _select_node_entries(config, lang)
    if not selected or not ui.confirm(tr(lang, "confirm_update"), default=False):
        return

    api = _api_from(config)
    timeout = int(config["settings"]["healthcheck_timeout"])
    do_backup = bool(config["settings"]["backup_before_update"])
    for index, node in enumerate(selected, 1):
        ui.heading(tr(lang, "node_progress", current=index, total=len(selected), name=node.get("name", "Node")))
        result = update_node(api, node, timeout, do_backup, _progress_printer(lang))
        _print_result(lang, result)
        if not result.ok:
            if bool(config["settings"].get("stop_on_failure", True)):
                ui.warn(tr(lang, "stop_after_fail"))
                break
            if not ui.confirm(tr(lang, "continue_after_fail"), default=False):
                break
    _pause(lang)


def _update_sub_interactive(config: dict, lang: str) -> None:
    sub = config.get("subscription", {"mode": "disabled"})
    if sub.get("mode") == "disabled":
        ui.warn(tr(lang, "sub_not_configured"))
        _pause(lang)
        return
    if not ui.confirm(tr(lang, "confirm_update"), default=False):
        return
    timeout = int(config["settings"]["healthcheck_timeout"])
    do_backup = bool(config["settings"]["backup_before_update"])
    if sub.get("mode") == "local":
        result = update_sub_local(timeout, do_backup, _progress_printer(lang))
    else:
        target = SSHHost(sub["host"], sub.get("user", "root"), int(sub.get("port", 22)))
        result = update_sub_remote(target, timeout, do_backup, _progress_printer(lang))
    _print_result(lang, result)
    _pause(lang)


def _status_running(info: str) -> bool:
    parts = [part.strip().lower() for part in info.split("|")]
    return len(parts) >= 2 and parts[1] == "running"


def _state(info: str) -> str:
    return ui.green("● Online") if _status_running(info) else ui.red("● Offline")


def _status_table(config: dict, lang: str) -> None:
    rows: list[list[str]] = []
    panel = panel_status()
    rows.append(["Panel", _state(panel), panel])

    for node in config.get("nodes", []):
        try:
            target = SSHHost(node["host"], node.get("user", "root"), int(node.get("port", 22)))
            info = node_status(target)
            state = _state(info)
        except Exception as exc:
            info = str(exc)
            state = ui.red("● Offline")
        rows.append([f"Node · {node.get('name', '')}", state, info])

    sub = config.get("subscription", {})
    if sub.get("mode") == "local":
        info = sub_status_local()
        rows.append(["Subscription Page", _state(info), info])
    elif sub.get("mode") == "remote":
        try:
            target = SSHHost(sub["host"], sub.get("user", "root"), int(sub.get("port", 22)))
            info = sub_status_remote(target)
            state = _state(info)
        except Exception as exc:
            info = str(exc)
            state = ui.red("● Offline")
        rows.append(["Subscription Page", state, info])
    else:
        rows.append(["Subscription Page", "—", tr(lang, "not_configured")])

    ui.heading(tr(lang, "status_title"))
    ui.table([tr(lang, "component"), tr(lang, "state"), tr(lang, "details")], rows)


def _settings(config: dict, lang: str) -> None:
    while True:
        ui.heading(tr(lang, "settings_title"))
        options = [
            tr(lang, "settings_sync"),
            tr(lang, "settings_panel"),
            tr(lang, "settings_sub"),
            tr(lang, "settings_language"),
            tr(lang, "settings_back"),
        ]
        ui.menu(options)
        choice = ui.choose(tr(lang, "choose"), ["1", "2", "3", "4", "5"], default="5")
        if choice == "1":
            try:
                _configure_nodes(config, lang, _api_from(config), only_new=True)
            except Exception as exc:
                ui.error(str(exc))
        elif choice == "2":
            _configure_panel(config, lang)
        elif choice == "3":
            _configure_subscription(config, lang)
        elif choice == "4":
            lang = _select_language(lang)
            config["language"] = lang
            save_config(config)
        else:
            return


def doctor(config: dict, lang: str) -> int:
    rows: list[list[str]] = []
    ok = True
    checks = [
        ("root", require_root()),
        (f"Python >= 3.10 ({sys.version_info.major}.{sys.version_info.minor})", sys.version_info >= (3, 10)),
        ("docker", shutil.which("docker") is not None),
        ("docker compose", shutil.which("docker") is not None),
        ("ssh", shutil.which("ssh") is not None),
        ("ssh-keygen", shutil.which("ssh-keygen") is not None),
        (PANEL_DIR, Path(PANEL_DIR).exists()),
        (str(CONFIG_FILE), CONFIG_FILE.exists()),
        (str(KEY_FILE), KEY_FILE.exists()),
    ]
    for name, passed in checks:
        rows.append([name, ui.green("✓") if passed else ui.red("✗")])
        ok = ok and passed

    try:
        _api_from(config).health()
        rows.append(["Panel API", ui.green("✓")])
    except Exception as exc:
        rows.append(["Panel API", f"{ui.red('✗')} {exc}"])
        ok = False

    for node in config.get("nodes", []):
        try:
            target = SSHHost(node["host"], node.get("user", "root"), int(node.get("port", 22)))
            code, _, _ = ssh_run(target, "true", timeout=15)
            passed = code == 0
            rows.append([f"SSH · {node.get('name')}", ui.green("✓") if passed else ui.red("✗")])
            ok = ok and passed
        except Exception as exc:
            rows.append([f"SSH · {node.get('name')}", f"{ui.red('✗')} {exc}"])
            ok = False

    ui.heading(tr(lang, "doctor_title"))
    ui.table(["Check", "Result"], rows)
    return 0 if ok else 1


def interactive(config: dict) -> None:
    lang = config.get("language", "ru")
    while True:
        _header(lang)
        ui.heading(tr(lang, "main_menu"))
        options = [
            tr(lang, "menu_panel"),
            tr(lang, "menu_nodes"),
            tr(lang, "menu_sub"),
            tr(lang, "menu_status"),
            tr(lang, "menu_settings"),
            tr(lang, "menu_exit"),
        ]
        ui.menu(options)
        choice = ui.choose(tr(lang, "choose"), ["1", "2", "3", "4", "5", "6"], default="6")
        if choice == "1":
            _update_panel_interactive(config, lang)
        elif choice == "2":
            _update_nodes_interactive(config, lang)
        elif choice == "3":
            _update_sub_interactive(config, lang)
        elif choice == "4":
            _status_table(config, lang)
            _pause(lang)
        elif choice == "5":
            _settings(config, lang)
            lang = config.get("language", lang)
        else:
            return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="remnawave-updater", description="CLI update manager for Remnawave")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("setup", help="run setup wizard")
    sub.add_parser("status", help="show component status")
    sub.add_parser("sync-nodes", help="sync new nodes from Panel")
    sub.add_parser("doctor", help="check local environment and configured SSH access")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not require_root():
        ui.error("Run as root / Запустите через sudo.")
        return 1

    config = load_config()
    if args.command == "setup" or not is_configured(config):
        config = setup(config)
        if args.command == "setup":
            return 0

    lang = config.get("language", "ru")
    if args.command == "status":
        _status_table(config, lang)
        return 0
    if args.command == "sync-nodes":
        _configure_nodes(config, lang, _api_from(config), only_new=True)
        return 0
    if args.command == "doctor":
        return doctor(config, lang)

    interactive(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
