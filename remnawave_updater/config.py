from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(os.environ.get("REMNAWAVE_UPDATER_CONFIG_DIR", "/etc/remnawave-updater"))
CONFIG_FILE = CONFIG_DIR / "config.json"
KEY_DIR = CONFIG_DIR / "keys"
KEY_FILE = KEY_DIR / "id_ed25519"
BACKUP_DIR = Path(os.environ.get("REMNAWAVE_UPDATER_BACKUP_DIR", "/var/backups/remnawave-updater"))

DEFAULT_CONFIG: dict[str, Any] = {
    "language": "ru",
    "panel": {"url": "", "token": "", "verify_ssl": True},
    "nodes": [],
    "subscription": {"mode": "disabled"},
    "settings": {
        "stop_on_failure": True,
        "healthcheck_timeout": 90,
        "backup_before_update": True,
    },
}


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)
    os.chmod(KEY_DIR, 0o700)


def load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))
    with CONFIG_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    merged.update(data)
    merged["panel"].update(data.get("panel", {}))
    merged["settings"].update(data.get("settings", {}))
    return merged


def save_config(config: dict[str, Any]) -> None:
    ensure_dirs()
    tmp = CONFIG_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.chmod(tmp, 0o600)
    tmp.replace(CONFIG_FILE)
    os.chmod(CONFIG_FILE, 0o600)


def is_configured(config: dict[str, Any]) -> bool:
    return bool(config.get("panel", {}).get("url") and config.get("panel", {}).get("token"))
