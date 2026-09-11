from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class APIError(RuntimeError):
    pass


@dataclass
class NodeInfo:
    uuid: str
    name: str
    host: str
    is_connected: bool | None = None


class RemnawaveAPI:
    def __init__(self, base_url: str, token: str, verify_ssl: bool = True, timeout: int = 15):
        base = base_url.rstrip("/")
        self.base_url = base if base.endswith("/api") else f"{base}/api"
        self.token = token.removeprefix("Bearer ").strip()
        self.verify_ssl = verify_ssl
        self.timeout = timeout

    def _request(self, path: str) -> Any:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "User-Agent": "remnawave-updater/0.1",
            },
        )
        context = None
        if url.startswith("https://") and not self.verify_ssl:
            context = ssl._create_unverified_context()  # noqa: SLF001
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=context) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            raise APIError(f"HTTP {e.code}: {body}") from e
        except Exception as e:  # network / JSON / TLS
            raise APIError(str(e)) from e

    def health(self) -> bool:
        self._request("/system/health")
        return True

    @staticmethod
    def _pick(obj: dict[str, Any], keys: tuple[str, ...], default=None):
        for key in keys:
            if key in obj and obj[key] not in (None, ""):
                return obj[key]
        return default

    @classmethod
    def _extract_node_dicts(cls, payload: Any) -> list[dict[str, Any]]:
        candidates: list[list[dict[str, Any]]] = []

        def walk(value: Any) -> None:
            if isinstance(value, list):
                dicts = [x for x in value if isinstance(x, dict)]
                if dicts:
                    score = sum(
                        1
                        for x in dicts
                        if cls._pick(x, ("uuid", "id"))
                        and cls._pick(x, ("name", "remark"))
                        and cls._pick(x, ("address", "host", "ip", "nodeAddress"))
                    )
                    if score:
                        candidates.append(dicts)
                for item in value:
                    walk(item)
            elif isinstance(value, dict):
                for item in value.values():
                    walk(item)

        walk(payload)
        if not candidates:
            return []
        return max(candidates, key=len)

    @classmethod
    def _to_node(cls, obj: dict[str, Any]) -> NodeInfo | None:
        uuid = cls._pick(obj, ("uuid", "id"))
        name = cls._pick(obj, ("name", "remark"), "Unnamed node")
        host = cls._pick(obj, ("address", "host", "ip", "nodeAddress"))
        if not uuid or not host:
            return None
        connected = cls._pick(obj, ("isConnected", "is_connected", "connected"), None)
        if isinstance(connected, str):
            connected = connected.lower() in {"true", "1", "yes", "online"}
        return NodeInfo(str(uuid), str(name), str(host), connected if isinstance(connected, bool) else None)

    def get_nodes(self) -> list[NodeInfo]:
        payload = self._request("/nodes")
        nodes = []
        for obj in self._extract_node_dicts(payload):
            node = self._to_node(obj)
            if node:
                nodes.append(node)
        # Keep first occurrence by UUID
        unique: dict[str, NodeInfo] = {}
        for node in nodes:
            unique.setdefault(node.uuid, node)
        return list(unique.values())

    def get_node(self, uuid: str) -> NodeInfo | None:
        payload = self._request(f"/nodes/{uuid}")
        if isinstance(payload, dict):
            direct = self._to_node(payload)
            if direct:
                return direct
        dicts = self._extract_node_dicts(payload)
        for obj in dicts:
            node = self._to_node(obj)
            if node:
                return node
        # Some single-object responses are nested under response/data.
        stack = [payload]
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                node = self._to_node(value)
                if node:
                    return node
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)
        return None
