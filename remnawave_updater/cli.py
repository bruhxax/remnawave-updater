from __future__ import annotations

import argparse
import getpass
import shutil
import sys
import time
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
    node_status_detail,
    panel_status_detail,
    sub_status_local_detail,
    sub_status_remote_detail,
    update_node,
    update_panel,
    update_sub_local,
    update_sub_remote,
)
from .utils import require_root
from .versions import LatestVersions, clean_version, get_latest_versions, is_update_available, version_tuple
from . import ui

_dashboard_cache: tuple[float, dict] | None = None


def _header(lang: str) -> None:
    ui.header(f"🌊 {tr(lang, 'app_title')}", tr(lang, "app_subtitle"), badge=f"v{__version__}")


def _pause(lang: str) -> None:
    ui.pause(tr(lang, "press_enter"))


def _select_language(current: str | None = None) -> str:
    ui.clear()
    ui.header("Language / Язык", "Remnawave Updater")
    ui.menu(["🇷🇺 Русский", "🇬🇧 English"])
    default = "2" if current == "en" else "1"
    choice = ui.choose(">", ["1", "2"], default=default)
    return "ru" if choice == "1" else "en"


def _api_from(config: dict) -> RemnawaveAPI:
    panel = config["panel"]
    return RemnawaveAPI(panel["url"], panel["token"], bool(panel.get("verify_ssl", True)))


def _version_text(value: str | None) -> str:
    version = clean_version(value)
    return f"v{version}" if version else "—"


def _update_badge(current: str | None, latest: str | None, lang: str) -> str:
    state = is_update_available(current, latest)
    if state is True:
        return ui.yellow("↑ Доступно обновление" if lang == "ru" else "↑ Update available")
    if state is False:
        return ui.green("✓ Актуально" if lang == "ru" else "✓ Up to date")
    return ui.dim("? Версия неизвестна" if lang == "ru" else "? Version unknown")


def _node_version_summary(nodes: list[NodeInfo]) -> str:
    versions = sorted(
        {clean_version(node.node_version) for node in nodes if clean_version(node.node_version)},
        key=lambda value: version_tuple(value) or (0, 0, 0),
    )
    if not versions:
        return "—"
    if len(versions) == 1:
        return f"v{versions[0]}"
    return f"v{versions[0]} … v{versions[-1]}"


def _invalidate_dashboard() -> None:
    global _dashboard_cache
    _dashboard_cache = None


def _get_dashboard(config: dict, lang: str, force: bool = False) -> dict:
    global _dashboard_cache
    now = time.monotonic()
    if not force and _dashboard_cache and now - _dashboard_cache[0] < 15:
        return _dashboard_cache[1]

    text = "Проверяю состояние и версии..." if lang == "ru" else "Checking status and versions..."
    spinner = ui.Spinner(text).start()
    data: dict = {
        "panel_version": None,
        "panel_online": False,
        "nodes": [],
        "sub_version": None,
        "sub_online": False,
        "latest": LatestVersions(),
    }
    try:
        api = _api_from(config)
        try:
            data["panel_version"] = api.get_panel_version()
            data["nodes"] = api.get_nodes()
            data["panel_online"] = True
        except Exception:
            pass

        try:
            data["latest"] = get_latest_versions(force=force)
        except Exception:
            pass

        sub = config.get("subscription", {})
        try:
            if sub.get("mode") == "local":
                status = sub_status_local_detail()
                data["sub_version"] = status.version
                data["sub_online"] = status.running
            elif sub.get("mode") == "remote":
                target = SSHHost(sub["host"], sub.get("user", "root"), int(sub.get("port", 22)))
                status = sub_status_remote_detail(target)
                data["sub_version"] = status.version
                data["sub_online"] = status.running
        except Exception:
            pass
        spinner.stop(True, "Готово" if lang == "ru" else "Ready")
    except Exception:
        spinner.stop(False, "Не удалось получить часть данных" if lang == "ru" else "Some status data unavailable")

    _dashboard_cache = (now, data)
    return data


def _render_dashboard(config: dict, lang: str) -> None:
    data = _get_dashboard(config, lang)
    latest: LatestVersions = data["latest"]
    nodes: list[NodeInfo] = data["nodes"]
    online_nodes = sum(1 for node in nodes if node.is_connected is True)
    known_versions = [node for node in nodes if clean_version(node.node_version)]
    latest_nodes = sum(
        1
        for node in known_versions
        if is_update_available(node.node_version, latest.node) is False
    )

    panel_dot = ui.green("●") if data["panel_online"] else ui.red("●")
    nodes_dot = ui.green("●") if nodes and online_nodes == len(nodes) else (ui.yellow("●") if online_nodes else ui.red("●"))
    sub_mode = config.get("subscription", {}).get("mode")
    sub_dot = ui.green("●") if data["sub_online"] else (ui.dim("●") if sub_mode == "disabled" else ui.red("●"))

    if lang == "ru":
        panel_line = (
            f"{panel_dot} Panel       {_version_text(data['panel_version']):<12}  "
            f"актуальная {_version_text(latest.panel):<10}  {_update_badge(data['panel_version'], latest.panel, lang)}"
        )
        node_extra = f"{latest_nodes}/{len(known_versions)} на актуальной" if known_versions and latest.node else "версия через Panel API"
        nodes_line = (
            f"{nodes_dot} Nodes       {online_nodes}/{len(nodes)} online · {_node_version_summary(nodes):<18}  "
            f"актуальная {_version_text(latest.node):<10}  {node_extra}"
        )
        sub_line = (
            f"{sub_dot} Sub Page    {_version_text(data['sub_version']):<12}  "
            f"актуальная {_version_text(latest.subscription):<10}  {_update_badge(data['sub_version'], latest.subscription, lang)}"
            if sub_mode != "disabled"
            else f"{sub_dot} Sub Page    не используется"
        )
        title = "Система"
    else:
        panel_line = (
            f"{panel_dot} Panel       {_version_text(data['panel_version']):<12}  "
            f"latest {_version_text(latest.panel):<10}  {_update_badge(data['panel_version'], latest.panel, lang)}"
        )
        node_extra = f"{latest_nodes}/{len(known_versions)} up to date" if known_versions and latest.node else "version via Panel API"
        nodes_line = (
            f"{nodes_dot} Nodes       {online_nodes}/{len(nodes)} online · {_node_version_summary(nodes):<18}  "
            f"latest {_version_text(latest.node):<10}  {node_extra}"
        )
        sub_line = (
            f"{sub_dot} Sub Page    {_version_text(data['sub_version']):<12}  "
            f"latest {_version_text(latest.subscription):<10}  {_update_badge(data['sub_version'], latest.subscription, lang)}"
            if sub_mode != "disabled"
            else f"{sub_dot} Sub Page    disabled"
        )
        title = "System"

    ui.card(title, [panel_line, nodes_line, sub_line])


def _configure_panel(config: dict, lang: str) -> RemnawaveAPI:
    while True:
        default_url = config.get("panel", {}).get("url") or None
        url = ui.prompt(tr(lang, "panel_url"), default=default_url).strip()
        old_token = config.get("panel", {}).get("token", "")
        token = getpass.getpass(f"{ui.primary('›')} {tr(lang, 'panel_token')}: ").strip() or old_token
        verify = ui.confirm(tr(lang, "verify_ssl"), default=True)
        api = RemnawaveAPI(url, token, verify)
        spinner = ui.Spinner(tr(lang, "testing_api")).start()
        try:
            api.health()
            nodes = api.get_nodes()
            version = api.get_panel_version()
            suffix = f" · v{clean_version(version)}" if clean_version(version) else ""
            spinner.stop(True, f"{tr(lang, 'api_ok')} · {tr(lang, 'nodes_found', count=len(nodes))}{suffix}")
            config["panel"] = {"url": url.rstrip("/"), "token": token, "verify_ssl": verify}
            save_config(config)
            print(ui.dim(f"  {tr(lang, 'token_saved')}"))
            _invalidate_dashboard()
            return api
        except Exception as exc:
            spinner.stop(False, tr(lang, "api_fail", error=exc))
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
        spinner = ui.Spinner(tr(lang, "ssh_connecting", host=node.host)).start()
        try:
            key_ok = _try_key(target)
            spinner.stop(True if key_ok else None, "SSH key уже работает" if key_ok and lang == "ru" else ("SSH key already works" if key_ok else ("Требуется пароль для первого входа" if lang == "ru" else "Password required for first login")))
            if not key_ok:
                _provision_key(target, lang)
            verify_spinner = ui.Spinner("Проверяю Remnanode..." if lang == "ru" else "Checking Remnanode...").start()
            code, _, err = ssh_run(target, f"test -f {NODE_DIR}/docker-compose.yml", timeout=20)
            if code != 0:
                verify_spinner.stop(False)
                raise SSHError(err.strip() or f"{NODE_DIR}/docker-compose.yml not found")
            verify_spinner.stop(True, tr(lang, "ssh_ok"))
            entry = {"uuid": node.uuid, "name": node.name, "host": node.host, "user": user, "port": port}
            config.setdefault("nodes", [])
            config["nodes"] = [item for item in config["nodes"] if item.get("uuid") != node.uuid]
            config["nodes"].append(entry)
            save_config(config)
            _invalidate_dashboard()
            return True
        except Exception as exc:
            ui.error(tr(lang, "ssh_fail", error=exc))
            if not ui.confirm(tr(lang, "retry_node"), default=True):
                ui.warn(tr(lang, "node_skipped"))
                return False


def _configure_nodes(config: dict, lang: str, api: RemnawaveAPI, only_new: bool = False) -> None:
    with ui.spinner("Получаю список нод..." if lang == "ru" else "Loading nodes..."):
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
        _invalidate_dashboard()
        return

    if choice == "1":
        if not detected:
            ui.warn(f"{SUB_DIR}/docker-compose.yml not found")
            if not ui.confirm("Save anyway? / Всё равно сохранить?", default=False):
                return
        config["subscription"] = {"mode": "local"}
        save_config(config)
        _invalidate_dashboard()
        return

    host = ui.prompt(tr(lang, "sub_host")).strip()
    user = ui.prompt(tr(lang, "ssh_user"), default="root").strip() or "root"
    port = ui.prompt_int(tr(lang, "ssh_port"), default=22)
    target = SSHHost(host, user, port)
    try:
        if not _try_key(target):
            _provision_key(target, lang)
        spinner = ui.Spinner("Проверяю Subscription Page..." if lang == "ru" else "Checking Subscription Page...").start()
        code, _, err = ssh_run(target, f"test -f {SUB_DIR}/docker-compose.yml", timeout=20)
        if code != 0:
            spinner.stop(False)
            raise SSHError(err.strip() or f"{SUB_DIR}/docker-compose.yml not found")
        spinner.stop(True, tr(lang, "ssh_ok"))
        config["subscription"] = {"mode": "remote", "host": host, "user": user, "port": port}
        save_config(config)
        _invalidate_dashboard()
    except Exception as exc:
        ui.error(tr(lang, "ssh_fail", error=exc))


def setup(config: dict | None = None) -> dict:
    config = config or load_config()
    lang = _select_language(config.get("language"))
    config["language"] = lang
    save_config(config)
    ui.clear()
    _header(lang)
    ui.notice(tr(lang, "major_warning"), level="warning")
    ui.heading(tr(lang, "setup_title"))
    ensure_keypair()
    api = _configure_panel(config, lang)
    _configure_nodes(config, lang, api)
    _configure_subscription(config, lang)
    save_config(config)
    _invalidate_dashboard()
    ui.ok(ui.bold(tr(lang, "setup_done")))
    time.sleep(0.6)
    return config


def _progress_spinner(lang: str) -> ui.StepSpinner:
    return ui.StepSpinner(
        {
            "backup": tr(lang, "backup_creating"),
            "pull": tr(lang, "step_pull"),
            "restart": tr(lang, "step_restart"),
            "health": tr(lang, "step_health"),
        }
    )


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
    ui.clear()
    _header(lang)
    ui.heading(tr(lang, "menu_panel"))
    ui.notice(tr(lang, "major_warning"), level="warning")
    if not ui.confirm(tr(lang, "confirm_update"), default=False):
        return
    progress = _progress_spinner(lang)
    result = update_panel(
        _api_from(config),
        timeout=int(config["settings"]["healthcheck_timeout"]),
        do_backup=bool(config["settings"]["backup_before_update"]),
        progress=progress,
    )
    progress.finish(result.ok)
    _invalidate_dashboard()
    _print_result(lang, result)
    _pause(lang)


def _select_node_entries(config: dict, lang: str) -> list[dict]:
    nodes = config.get("nodes", [])
    if not nodes:
        ui.warn(tr(lang, "no_nodes"))
        return []
    rows = []
    for index, node in enumerate(nodes, 1):
        rows.append([str(index), node.get("name", "Node"), f"{node.get('user', 'root')}@{node.get('host')}:{node.get('port', 22)}"])
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

    ui.clear()
    _header(lang)
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
        progress = _progress_spinner(lang)
        result = update_node(api, node, timeout, do_backup, progress)
        progress.finish(result.ok)
        _print_result(lang, result)
        if not result.ok:
            if bool(config["settings"].get("stop_on_failure", True)):
                ui.warn(tr(lang, "stop_after_fail"))
                break
            if not ui.confirm(tr(lang, "continue_after_fail"), default=False):
                break
    _invalidate_dashboard()
    _pause(lang)


def _update_sub_interactive(config: dict, lang: str) -> None:
    sub = config.get("subscription", {"mode": "disabled"})
    if sub.get("mode") == "disabled":
        ui.warn(tr(lang, "sub_not_configured"))
        _pause(lang)
        return
    ui.clear()
    _header(lang)
    ui.heading(tr(lang, "menu_sub"))
    if not ui.confirm(tr(lang, "confirm_update"), default=False):
        return
    timeout = int(config["settings"]["healthcheck_timeout"])
    do_backup = bool(config["settings"]["backup_before_update"])
    progress = _progress_spinner(lang)
    if sub.get("mode") == "local":
        result = update_sub_local(timeout, do_backup, progress)
    else:
        target = SSHHost(sub["host"], sub.get("user", "root"), int(sub.get("port", 22)))
        result = update_sub_remote(target, timeout, do_backup, progress)
    progress.finish(result.ok)
    _invalidate_dashboard()
    _print_result(lang, result)
    _pause(lang)


def _status_state(running: bool, connected: bool | None = None) -> str:
    if running and connected is not False:
        return ui.green("● Online")
    if running:
        return ui.yellow("● Degraded")
    return ui.red("● Offline")


def _status_table(config: dict, lang: str) -> None:
    ui.clear()
    _header(lang)
    ui.heading(tr(lang, "status_title"))

    spinner = ui.Spinner("Получаю актуальные версии..." if lang == "ru" else "Fetching latest versions...").start()
    try:
        latest = get_latest_versions(force=True)
        api = _api_from(config)
        panel_version = api.get_panel_version()
        api_nodes = api.get_nodes()
        node_map = {node.uuid: node for node in api_nodes}
        spinner.stop(True, "Версии получены" if lang == "ru" else "Versions loaded")
    except Exception as exc:
        latest = LatestVersions()
        panel_version = None
        node_map = {}
        spinner.stop(False, f"API: {exc}")

    rows: list[list[str]] = []
    panel = panel_status_detail(panel_version)
    rows.append([
        "Panel",
        _status_state(panel.running),
        _version_text(panel.version),
        _version_text(latest.panel),
        _update_badge(panel.version, latest.panel, lang),
    ])

    check = ui.Spinner("Проверяю ноды..." if lang == "ru" else "Checking nodes...").start()
    for node in config.get("nodes", []):
        name = node.get("name", "Node")
        check.update((f"Проверяю ноду {name}..." if lang == "ru" else f"Checking node {name}..."))
        api_node = node_map.get(node.get("uuid"))
        try:
            target = SSHHost(node["host"], node.get("user", "root"), int(node.get("port", 22)))
            status = node_status_detail(target, api_node.node_version if api_node else None)
            current = status.version or (api_node.node_version if api_node else None)
            state = _status_state(status.running, api_node.is_connected if api_node else None)
        except Exception:
            current = api_node.node_version if api_node else None
            state = ui.red("● Offline")
        rows.append([
            f"Node · {name}",
            state,
            _version_text(current),
            _version_text(latest.node),
            _update_badge(current, latest.node, lang),
        ])
    check.stop(True, "Ноды проверены" if lang == "ru" else "Nodes checked")

    sub = config.get("subscription", {})
    if sub.get("mode") == "local":
        with ui.spinner("Проверяю Subscription Page..." if lang == "ru" else "Checking Subscription Page..."):
            status = sub_status_local_detail()
        rows.append([
            "Subscription Page",
            _status_state(status.running),
            _version_text(status.version),
            _version_text(latest.subscription),
            _update_badge(status.version, latest.subscription, lang),
        ])
    elif sub.get("mode") == "remote":
        try:
            target = SSHHost(sub["host"], sub.get("user", "root"), int(sub.get("port", 22)))
            with ui.spinner("Проверяю Subscription Page..." if lang == "ru" else "Checking Subscription Page..."):
                status = sub_status_remote_detail(target)
            rows.append([
                "Subscription Page",
                _status_state(status.running),
                _version_text(status.version),
                _version_text(latest.subscription),
                _update_badge(status.version, latest.subscription, lang),
            ])
        except Exception:
            rows.append(["Subscription Page", ui.red("● Offline"), "—", _version_text(latest.subscription), "—"])
    else:
        rows.append(["Subscription Page", "—", tr(lang, "not_configured"), _version_text(latest.subscription), "—"])

    headers = (
        ["Компонент", "Состояние", "Установлено", "Актуальная", "Обновление"]
        if lang == "ru"
        else ["Component", "State", "Installed", "Latest", "Update"]
    )
    ui.table(headers, rows)
    _invalidate_dashboard()


def _settings(config: dict, lang: str) -> None:
    while True:
        ui.clear()
        _header(lang)
        ui.heading(tr(lang, "settings_title"))
        options = [tr(lang, "settings_sync"), tr(lang, "settings_panel"), tr(lang, "settings_sub"), tr(lang, "settings_language"), tr(lang, "settings_back")]
        ui.menu(options)
        choice = ui.choose(tr(lang, "choose"), ["1", "2", "3", "4", "5"], default="5")
        if choice == "1":
            try:
                _configure_nodes(config, lang, _api_from(config), only_new=True)
                _pause(lang)
            except Exception as exc:
                ui.error(str(exc))
                _pause(lang)
        elif choice == "2":
            _configure_panel(config, lang)
            _pause(lang)
        elif choice == "3":
            _configure_subscription(config, lang)
            _pause(lang)
        elif choice == "4":
            lang = _select_language(lang)
            config["language"] = lang
            save_config(config)
        else:
            return


def doctor(config: dict, lang: str) -> int:
    ui.clear()
    _header(lang)
    ui.heading(tr(lang, "doctor_title"))
    rows: list[list[str]] = []
    ok_state = True
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
        ok_state = ok_state and passed

    spinner = ui.Spinner("Проверяю Panel API..." if lang == "ru" else "Checking Panel API...").start()
    try:
        _api_from(config).health()
        spinner.stop(True)
        rows.append(["Panel API", ui.green("✓")])
    except Exception as exc:
        spinner.stop(False)
        rows.append(["Panel API", f"{ui.red('✗')} {exc}"])
        ok_state = False

    spinner = ui.Spinner("Проверяю SSH нод..." if lang == "ru" else "Checking node SSH...").start()
    for node in config.get("nodes", []):
        spinner.update((f"SSH · {node.get('name')}"))
        try:
            target = SSHHost(node["host"], node.get("user", "root"), int(node.get("port", 22)))
            code, _, _ = ssh_run(target, "true", timeout=15)
            passed = code == 0
            rows.append([f"SSH · {node.get('name')}", ui.green("✓") if passed else ui.red("✗")])
            ok_state = ok_state and passed
        except Exception as exc:
            rows.append([f"SSH · {node.get('name')}", f"{ui.red('✗')} {exc}"])
            ok_state = False
    spinner.stop(ok_state, "SSH проверка завершена" if lang == "ru" else "SSH checks complete")

    ui.table(["Check", "Result"], rows)
    return 0 if ok_state else 1


def interactive(config: dict) -> None:
    lang = config.get("language", "ru")
    while True:
        ui.clear()
        _header(lang)
        _render_dashboard(config, lang)
        ui.heading(tr(lang, "main_menu"))
        options = [tr(lang, "menu_panel"), tr(lang, "menu_nodes"), tr(lang, "menu_sub"), tr(lang, "menu_status"), tr(lang, "menu_settings"), tr(lang, "menu_exit")]
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
            ui.clear()
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
