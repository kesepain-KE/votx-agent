"""Identity mapping between external accounts and internal users."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class IdentityStore:
    def __init__(self, root: str, config: dict[str, Any]):
        self.root = Path(root)
        self.config = config
        self.mappings = self._load_mappings()

    def _load_mappings(self) -> dict[str, dict[str, Any]]:
        path_text = self.config.get("identity_map_path") or "message/identity/identity_map.json"
        path = Path(path_text)
        if not path.is_absolute():
            path = self.root / path
        if not path.is_file() or path.stat().st_size == 0:
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[message] identity_map 读取失败: {path} — {e}")
            return {}
        mappings = data.get("mappings", data)
        return mappings if isinstance(mappings, dict) else {}

    def resolve_onebot(self, user_id: str | int) -> dict[str, Any] | None:
        external_id = str(user_id)
        for key in (f"qq:{external_id}", f"onebot:{external_id}", external_id):
            identity = self.mappings.get(key)
            if identity:
                return self._normalize(identity, "onebot", external_id)

        bound = self.config.get("platforms", {}).get("onebot", {}).get("bound_users", {})
        internal_user = (
            bound.get(f"qq:{external_id}")
            or bound.get(f"onebot:{external_id}")
            or bound.get(external_id)
        )
        if not internal_user:
            return None
        role = "admin" if internal_user in set(self.config.get("admins", [])) else "user"
        return {
            "platform": "onebot",
            "external_id": external_id,
            "internal_user": internal_user,
            "display_name": internal_user,
            "role": role,
        }

    def _normalize(self, identity: dict[str, Any], platform: str, external_id: str) -> dict[str, Any]:
        item = dict(identity)
        item.setdefault("platform", platform)
        item.setdefault("external_id", external_id)
        if not item.get("internal_user"):
            item["internal_user"] = item.get("user") or item.get("username") or ""
        item.setdefault("display_name", item["internal_user"])
        item.setdefault("role", "admin" if item["internal_user"] in set(self.config.get("admins", [])) else "user")
        return item if item.get("internal_user") else {}
