"""Helpers for decorating assistant tool calls with persisted log ids."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any


def _build_tool_call_log_map(user_dir: str) -> dict[str, str]:
    log_path = os.path.join(user_dir, "history", "log", "tool_log.jsonl")
    if not os.path.exists(log_path):
        return {}

    mapping: dict[str, str] = {}
    try:
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue
                tcid = entry.get("tool_call_id", "")
                lid = entry.get("id", "")
                if tcid and lid:
                    mapping[str(tcid)] = str(lid)
    except Exception:
        return {}
    return mapping


def decorate_tool_calls_with_log_ids(user_dir: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a deep-copied message list with assistant tool_calls decorated by log_id."""
    decorated = deepcopy(messages)
    tc_to_log = _build_tool_call_log_map(user_dir)
    if not tc_to_log:
        return decorated

    for msg in decorated:
        if msg.get("role") != "assistant" or not msg.get("tool_calls"):
            continue
        for tc in msg["tool_calls"]:
            tc_id = tc.get("id", "")
            if tc_id in tc_to_log:
                tc["log_id"] = tc_to_log[tc_id]

    return decorated
