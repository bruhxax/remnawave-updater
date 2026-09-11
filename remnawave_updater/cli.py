from __future__ import annotations

import argparse
import getpass
import os
import shutil
import sys
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

from . import __version__
from .api import APIError, NodeInfo, RemnawaveAPI
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
from .utils import require_root, run_local

console = Console()


def _header(lang: str) -> None:
    title = Text(tr(lang, "app_title"), style="bold cyan")
    subtitle = tr(lang, "app_subtitle")
    console.print(Panel.fit(Text.assemble(title, "\n", subtitle), border_style="cyan"))


def _pause(lang: str) -> None:
    Prompt.ask(tr(lang, "press_enter"), default="")


def _select_language(current: str | None = None) -> str:
    console.print(Panel.fit("[bold]1[/]  Русский\n[bold]2[/]  English", title=tr("en", "language_title"), border_style="cyan"))
    default = "1" if current != "en" else "2"
    choice = Prompt.ask(">", choices=["1", "2"], default=default)
    return "ru" if choice == "1" else "en"


def _api_from(config: dict) -> RemnawaveAPI:
    p = config["panel"]
    return RemnawaveAPI(p["url"], p["token"], bool(p.get("verify_ssl", True)))


def _configure_panel(config: dict, lang: str) -> RemnawaveAPI:
    while True:
        default_url = config.get("panel", {}).get("url") or ""
        url = Prompt.ask(tr(lang, "panel_url"), default=default_url or None).strip()
        token = getpass.getpass(f"{tr(lang, 'panel_token')}: ").strip()
        if not token and config.get("panel", {}).get("token"):
            token = config["panel"]["token"]
        verify = Confirm.ask(tr(lang, "verify_ssl"), default=True)
        api = RemnawaveAPI(url, token, verify)
        console.print(f"[dim]{tr(lang, 'testing_api')}[/]")
        try:
            api.health()
            nodes = api.get_nodes()
            console.print(f"[green]✓[/] {tr(lang, 'api_ok')} · {tr(lang, 'nodes_found', count=len(nodes))}")
            config["panel"] = {"url": url.rstrip("/"), "token": token, "verify_ssl": verify}
            save_config(config)
            console.print(f"[dim]{tr(lang, 'token_saved')}[/]")
            return api
        except Exception as e:
            console.print(f"[red]✗[/] {tr(lang, 'api_fail', error=e)}")
            if not Confirm.ask("Retry? / Повторить?", default=True):
                raise SystemExit(1)


def _try_key(target: SSHHost) -> bool:
    try:
        code, _, _ = ssh_run(target, "true", timeout=15)
        return code == 0
    except Exception:
        return False


def _configure_one_node(config: dict, lang: str, node: NodeInfo) -> bool:
    if not Confirm.ask(tr(lang, "node_configure", name=node.name, host=node.host), default=True):
        console.print(f"[yellow]↷[/] {tr(lang, 'node_skipped')}")
        return False

    while True:
        user = Prompt.ask(tr(lang, "ssh_user"), default="root").strip() or "root"
        port = IntPrompt.ask(tr(lang, "ssh_port"), default=22)
        target = SSHHost(node.host, user, port)
        console.print(f"[dim]{tr(lang, 'ssh_connecting', host=node.host)}[/]")
        try:
            if not _try_key(target):
                password = getpass.getpass(f"{tr(lang, 'ssh_password')}: ")
                install_key(target, password)
            # Verify Remnanode location now, so a typo doesn't become a surprise during update.
            code, _, err = ssh_run(target, f"test -f {NODE_DIR}/docker-compose.yml", timeout=20)
            if code != 0:
                raise SSHError(err.strip() or f"{NODE_DIR}/docker-compose.yml not found")
            entry = {"uuid": node.uuid, "name": node.name, "host": node.host, "user": user, "port": port}
            config.setdefault("nodes", [])
            config["nodes"] = [n for n in config["nodes"] if n.get("uuid") != node.uuid]
            config["nodes"].append(entry)
            save_config(config)
            console.print(f"[green]✓[/] {tr(lang, 'ssh_ok')}")
            return True
        except Exception as e:
            console.print(f"[red]✗[/] {tr(lang, 'ssh_fail', error=e)}")
            if not Confirm.ask(tr(lang, "retry_node"), default=True):
                console.print(f"[yellow]↷[/] {tr(lang, 'node_skipped')}")
                return False


def _configure_nodes(config: dict, lang: str, api: RemnawaveAPI, only_new: bool = False) -> None:
    nodes = api.get_nodes()
    existing = {n.get("uuid"): n for n in config.get("nodes", [])}

    # Refresh names/addresses for already configured nodes; SSH credentials stay unchanged.
    changed = False
    for node in nodes:
        old = existing.get(node.uuid)
        if old:
            if old.get("name") != node.name or old.get("host") != node.host:
                old["name"] = node.name
                old["host"] = node.host
                changed = True
    if changed:
        config["nodes"] = list(existing.values())
        save_config(config)

    pending = [n for n in nodes if n.uuid not in existing]
    if only_new:
        if not pending:
            console.print(f"[green]✓[/] {tr(lang, 'sync_none')}")
            return
        console.print(tr(lang, "sync_new", count=len(pending)))
        nodes = pending
    else:
        console.print(tr(lang, "nodes_found", count=len(nodes)))
        nodes = pending if existing else nodes
        if existing and not pending:
            return

    for node in nodes:
        _configure_one_node(config, lang, node)


def _configure_subscription(config: dict, lang: str) -> None:
    detected = Path(f"{SUB_DIR}/docker-compose.yml").exists()
    if detected:
        console.print(f"[green]✓[/] {tr(lang, 'sub_detected_local')}")
    console.print(f"\n[bold]{tr(lang, 'sub_where')}[/]")
    console.print(f"  [cyan]1[/] {tr(lang, 'sub_local')}" + ("  [green](detected)[/]" if detected else ""))
    console.print(f"  [cyan]2[/] {tr(lang, 'sub_remote')}")
    console.print(f"  [cyan]3[/] {tr(lang, 'sub_none')}")
    default = "1" if detected else "3"
    choice = Prompt.ask(tr(lang, "choose"), choices=["1", "2", "3"], default=default)
    if choice == "3":
        config["subscription"] = {"mode": "disabled"}
        save_config(config)
        return
    if choice == "1":
        if not Path(f"{SUB_DIR}/docker-compose.yml").exists():
            console.print(f"[yellow]! {SUB_DIR}/docker-compose.yml not found[/]")
            if not Confirm.ask("Save anyway? / Всё равно сохранить?", default=False):
                return
        config["subscription"] = {"mode": "local"}
        save_config(config)
        return

    host = Prompt.ask(tr(lang, "sub_host")).strip()
    user = Prompt.ask(tr(lang, "ssh_user"), default="root").strip() or "root"
    port = IntPrompt.ask(tr(lang, "ssh_port"), default=22)
    target = SSHHost(host, user, port)
    try:
        if not _try_key(target):
            password = getpass.getpass(f"{tr(lang, 'ssh_password')}: ")
            install_key(target, password)
        code, _, err = ssh_run(target, f"test -f {SUB_DIR}/docker-compose.yml", timeout=20)
        if code != 0:
            raise SSHError(err.strip() or f"{SUB_DIR}/docker-compose.yml not found")
        config["subscription"] = {"mode": "remote", "host": host, "user": user, "port": port}
        save_config(config)
        console.print(f"[green]✓[/] {tr(lang, 'ssh_ok')}")
    except Exception as e:
        console.print(f"[red]✗[/] {tr(lang, 'ssh_fail', error=e)}")


def setup(config: dict | None = None) -> dict:
    config = config or load_config()
    lang = _select_language(config.get("language"))
    config["language"] = lang
    save_config(config)
    _header(lang)
    console.print(Panel(tr(lang, "major_warning"), border_style="yellow"))
    console.print(f"\n[bold]{tr(lang, 'setup_title')}[/]\n")
    ensure_keypair()
    api = _configure_panel(config, lang)
    _configure_nodes(config, lang, api)
    _configure_subscription(config, lang)
    save_config(config)
    console.print(f"\n[green]✓[/] [bold]{tr(lang, 'setup_done')}[/]")
    return config


def _progress_printer(lang: str):
    mapping = {
        "backup": tr(lang, "backup_creating"),
        "pull": tr(lang, "step_pull"),
        "restart": tr(lang, "step_restart"),
        "health": tr(lang, "step_health"),
    }

    def emit(step: str) -> None:
        console.print(f"  [cyan]›[/] {mapping.get(step, step)}")

    return emit


def _print_result(lang: str, result) -> None:
    if result.backup:
        console.print(f"  [dim]{tr(lang, 'backup_ok', path=result.backup)}[/]")
    if result.ok:
        console.print(f"[green]✓[/] [bold]{tr(lang, 'updated_ok', name=result.name)}[/]")
        if result.details:
            console.print(f"  [dim]{result.details}[/]")
    else:
        console.print(f"[red]✗[/] [bold]{tr(lang, 'updated_fail', name=result.name, error=result.details)}[/]")


def _update_panel_interactive(config: dict, lang: str) -> None:
    console.print(Panel(tr(lang, "major_warning"), border_style="yellow"))
    if not Confirm.ask(tr(lang, "confirm_update"), default=False):
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
        console.print(f"[yellow]![/] {tr(lang, 'no_nodes')}")
        return []
    table = Table(box=box.SIMPLE, show_header=True)
    table.add_column("#", style="cyan", width=4)
    table.add_column("Node")
    table.add_column("SSH")
    for i, n in enumerate(nodes, 1):
        table.add_row(str(i), n.get("name", "Node"), f"{n.get('user','root')}@{n.get('host')}:{n.get('port',22)}")
    console.print(table)
    raw = Prompt.ask(tr(lang, "select_nodes")).strip()
    try:
        indexes = sorted({int(x.strip()) for x in raw.split(",") if x.strip()})
        if not indexes or any(i < 1 or i > len(nodes) for i in indexes):
            raise ValueError
        return [nodes[i - 1] for i in indexes]
    except ValueError:
        console.print(f"[red]✗[/] {tr(lang, 'invalid_selection')}")
        return []


def _update_nodes_interactive(config: dict, lang: str) -> None:
    nodes = config.get("nodes", [])
    if not nodes:
        console.print(f"[yellow]![/] {tr(lang, 'no_nodes')}")
        _pause(lang)
        return
    console.print(f"\n[bold]{tr(lang, 'nodes_menu')}[/]")
    console.print(f"  [cyan]1[/] {tr(lang, 'nodes_all')}")
    console.print(f"  [cyan]2[/] {tr(lang, 'nodes_select')}")
    console.print(f"  [cyan]3[/] {tr(lang, 'nodes_back')}")
    choice = Prompt.ask(tr(lang, "choose"), choices=["1", "2", "3"], default="1")
    if choice == "3":
        return
    selected = nodes if choice == "1" else _select_node_entries(config, lang)
    if not selected:
        return
    if not Confirm.ask(tr(lang, "confirm_update"), default=False):
        return
    api = _api_from(config)
    timeout = int(config["settings"]["healthcheck_timeout"])
    do_backup = bool(config["settings"]["backup_before_update"])
    for index, node in enumerate(selected, 1):
        console.print(f"\n[bold cyan]{tr(lang, 'node_progress', current=index, total=len(selected), name=node.get('name','Node'))}[/]")
        result = update_node(api, node, timeout, do_backup, _progress_printer(lang))
        _print_result(lang, result)
        if not result.ok:
            if bool(config["settings"].get("stop_on_failure", True)):
                console.print(f"[yellow]![/] {tr(lang, 'stop_after_fail')}")
                break
            if not Confirm.ask(tr(lang, "continue_after_fail"), default=False):
                break
    _pause(lang)


def _update_sub_interactive(config: dict, lang: str) -> None:
    sub = config.get("subscription", {"mode": "disabled"})
    if sub.get("mode") == "disabled":
        console.print(f"[yellow]![/] {tr(lang, 'sub_not_configured')}")
        _pause(lang)
        return
    if not Confirm.ask(tr(lang, "confirm_update"), default=False):
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


def _status_table(config: dict, lang: str) -> None:
    table = Table(title=tr(lang, "status_title"), box=box.ROUNDED)
    table.add_column(tr(lang, "component"), style="bold")
    table.add_column(tr(lang, "state"))
    table.add_column(tr(lang, "details"))

    p = panel_status()
    table.add_row("Panel", "[green]● Online[/]" if _status_running(p) else "[red]● Offline[/]", p)
    for node in config.get("nodes", []):
        try:
            target = SSHHost(node["host"], node.get("user", "root"), int(node.get("port", 22)))
            info = node_status(target)
            state = "[green]● Online[/]" if _status_running(info) else "[red]● Offline[/]"
        except Exception as e:
            info = str(e)
            state = "[red]● Offline[/]"
        table.add_row(f"Node · {node.get('name','')}", state, info)

    sub = config.get("subscription", {})
    if sub.get("mode") == "local":
        info = sub_status_local()
        table.add_row("Subscription Page", "[green]● Online[/]" if _status_running(info) else "[red]● Offline[/]", info)
    elif sub.get("mode") == "remote":
        try:
            target = SSHHost(sub["host"], sub.get("user", "root"), int(sub.get("port", 22)))
            info = sub_status_remote(target)
            state = "[green]● Online[/]" if _status_running(info) else "[red]● Offline[/]"
        except Exception as e:
            info = str(e)
            state = "[red]● Offline[/]"
        table.add_row("Subscription Page", state, info)
    else:
        table.add_row("Subscription Page", "[dim]—[/]", tr(lang, "not_configured"))
    console.print(table)


def _settings(config: dict, lang: str) -> None:
    while True:
        console.print(f"\n[bold]{tr(lang, 'settings_title')}[/]")
        options = [
            tr(lang, "settings_sync"),
            tr(lang, "settings_panel"),
            tr(lang, "settings_sub"),
            tr(lang, "settings_language"),
            tr(lang, "settings_back"),
        ]
        for i, item in enumerate(options, 1):
            console.print(f"  [cyan]{i}[/] {item}")
        choice = Prompt.ask(tr(lang, "choose"), choices=["1", "2", "3", "4", "5"], default="5")
        if choice == "1":
            try:
                _configure_nodes(config, lang, _api_from(config), only_new=True)
            except Exception as e:
                console.print(f"[red]✗[/] {e}")
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
    table = Table(title=tr(lang, "doctor_title"), box=box.ROUNDED)
    table.add_column("Check")
    table.add_column("Result")
    ok = True

    checks = [
        ("root", require_root()),
        ("docker", shutil.which("docker") is not None),
        ("ssh-keygen", shutil.which("ssh-keygen") is not None),
        (PANEL_DIR, Path(PANEL_DIR).exists()),
        (str(CONFIG_FILE), CONFIG_FILE.exists()),
        (str(KEY_FILE), KEY_FILE.exists()),
    ]
    for name, passed in checks:
        table.add_row(name, "[green]✓[/]" if passed else "[red]✗[/]")
        ok = ok and passed
    try:
        _api_from(config).health()
        table.add_row("Panel API", "[green]✓[/]")
    except Exception as e:
        table.add_row("Panel API", f"[red]✗[/] {e}")
        ok = False

    for node in config.get("nodes", []):
        try:
            target = SSHHost(node["host"], node.get("user", "root"), int(node.get("port", 22)))
            code, _, _ = ssh_run(target, "true", timeout=15)
            passed = code == 0
            table.add_row(f"SSH · {node.get('name')}", "[green]✓[/]" if passed else "[red]✗[/]")
            ok = ok and passed
        except Exception as e:
            table.add_row(f"SSH · {node.get('name')}", f"[red]✗[/] {e}")
            ok = False
    console.print(table)
    return 0 if ok else 1


def interactive(config: dict) -> None:
    lang = config.get("language", "ru")
    while True:
        _header(lang)
        console.print(f"\n[bold]{tr(lang, 'main_menu')}[/]")
        options = [
            tr(lang, "menu_panel"),
            tr(lang, "menu_nodes"),
            tr(lang, "menu_sub"),
            tr(lang, "menu_status"),
            tr(lang, "menu_settings"),
            tr(lang, "menu_exit"),
        ]
        for i, item in enumerate(options, 1):
            console.print(f"  [cyan]{i}[/] {item}")
        choice = Prompt.ask(tr(lang, "choose"), choices=[str(i) for i in range(1, 7)], default="6")
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
        console.print("[red]Run as root / Запустите через sudo.[/]")
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
