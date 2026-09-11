from __future__ import annotations

import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

_GITHUB_API = "https://api.github.com/repos"
_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")
_CACHE_TTL = 300
_cache_at = 0.0
_cache: "LatestVersions | None" = None


@dataclass(frozen=True)
class LatestVersions:
    panel: str | None = None
    node: str | None = None
    subscription: str | None = None


def clean_version(value: str | None) -> str | None:
    if not value:
        return None
    value = str(value).strip()
    if value.lower().startswith("v"):
        value = value[1:]
    match = re.search(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", value)
    return match.group(0) if match else None


def version_tuple(value: str | None) -> tuple[int, int, int] | None:
    value = clean_version(value)
    if not value:
        return None
    match = _SEMVER_RE.match(value)
    if not match:
        base = value.split("-", 1)[0].split("+", 1)[0]
        try:
            a, b, c = base.split(".")
            return int(a), int(b), int(c)
        except (ValueError, TypeError):
            return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def is_update_available(current: str | None, latest: str | None) -> bool | None:
    cur = version_tuple(current)
    lat = version_tuple(latest)
    if cur is None or lat is None:
        return None
    return cur < lat


def _request_json(url: str, timeout: int = 4) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "remnawave-updater",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _latest_release(repo: str) -> str | None:
    try:
        payload = _request_json(f"{_GITHUB_API}/{repo}/releases/latest")
        if isinstance(payload, dict):
            return clean_version(payload.get("tag_name") or payload.get("name"))
    except Exception:
        return None
    return None


def _latest_tag(repo: str) -> str | None:
    try:
        payload = _request_json(f"{_GITHUB_API}/{repo}/tags?per_page=20")
        versions: list[tuple[tuple[int, int, int], str]] = []
        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                version = clean_version(item.get("name"))
                parsed = version_tuple(version)
                if version and parsed:
                    versions.append((parsed, version))
        if versions:
            versions.sort(reverse=True)
            return versions[0][1]
    except Exception:
        return None
    return None


def get_latest_versions(force: bool = False) -> LatestVersions:
    global _cache, _cache_at
    now = time.monotonic()
    if not force and _cache is not None and now - _cache_at < _CACHE_TTL:
        return _cache

    with ThreadPoolExecutor(max_workers=3) as pool:
        panel_future = pool.submit(_latest_release, "remnawave/backend")
        node_future = pool.submit(_latest_release, "remnawave/node")
        sub_future = pool.submit(_latest_tag, "remnawave/subscription-page")
        result = LatestVersions(
            panel=panel_future.result(),
            node=node_future.result(),
            subscription=sub_future.result(),
        )

    _cache = result
    _cache_at = now
    return result
