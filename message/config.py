"""Configuration loading for the in-process message router."""
from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


def default_config() -> dict[str, Any]:
    return {
        "enabled": False,
        "admins": [],
        "platforms": {
            "onebot": {
                "enabled": False,
                "ws_url": "ws://127.0.0.1:3001",
                "access_token": "",
                "reconnect_interval": 5,
                "ping_interval": 60,
                "ping_timeout": 30,
                "api_timeout": 15,
                "bound_users": {},
            },
            "telegram": {
                "enabled": False,
                "bot_token": "",
                "poll_interval": 2,
                "api_timeout": 30,
                "bound_users": {},
            },
        },
        "commands": {
            "enabled": True,
            "prefix": "/",
            "allow_in_group": True,
        },
        "group_mode": {
            "qq": {
                "enabled": True,
                "require_at_bot": True,
                "admin_full_access": True,
                "allow_agent_chat": True,
                "max_message_length": 4096,
            },
            "telegram": {
                "enabled": True,
                "require_at_bot": True,
                "admin_full_access": True,
                "allow_agent_chat": True,
                "max_message_length": 4096,
            },
        },
        "push": {
            "enabled": True,
            "queue_dir": "message/push_queue",
            "retry_times": 3,
            "retry_interval": 5,
        },
        "task_integration": {
            "notify_on_task_complete": True,
            "notify_on_plan_update": True,
            "notify_on_step_done": False,
        },
    }


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def _candidate_paths(root: str, explicit_path: str | None = None) -> list[Path]:
    if explicit_path:
        return [Path(explicit_path)]

    env_path = os.environ.get("VOTX_MESSAGE_CONFIG", "").strip()
    if env_path:
        return [Path(env_path)]

    message_dir = Path(root) / "message"
    return [
        message_dir / "config.local.json",
        message_dir / "config.json",
    ]


def load_config(root: str, explicit_path: str | None = None) -> dict[str, Any]:
    cfg = default_config()
    used_path = None

    for path in _candidate_paths(root, explicit_path):
        if not path.is_absolute():
            path = Path(root) / path
        if not path.is_file() or path.stat().st_size == 0:
            continue
        used_path = path
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[message] 配置读取失败: {path} — {e}")
            cfg["_config_path"] = str(path)
            cfg["enabled"] = False
            return cfg
        if not isinstance(data, dict):
            print(f"[message] 配置格式错误: {path} 不是 JSON object")
            cfg["_config_path"] = str(path)
            cfg["enabled"] = False
            return cfg
        _merge(cfg, data)
        break

    any_platform = (
        bool(cfg.get("platforms", {}).get("onebot", {}).get("enabled"))
        or bool(cfg.get("platforms", {}).get("telegram", {}).get("enabled"))
    )
    cfg["enabled"] = bool(cfg.get("enabled") or any_platform)
    cfg["_config_path"] = str(used_path) if used_path else ""
    return cfg


def sanitized_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return a copy safe for logs."""
    clone = deepcopy(config)
    onebot = clone.get("platforms", {}).get("onebot", {})
    if onebot.get("access_token"):
        onebot["access_token"] = "***"
    telegram = clone.get("platforms", {}).get("telegram", {})
    if telegram.get("bot_token"):
        telegram["bot_token"] = "***"
    return clone
