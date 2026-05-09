"""对话摘要子代理 — CLI 和 Web 共用，独立 LLM 调用生成一句话摘要"""
import json
import os
import re

from run.io_utils import atomic_write_json


def index_path(user_dir: str) -> str:
    return os.path.join(user_dir, "history", "history_save_data.json")


def load_index(user_dir: str) -> dict:
    path = index_path(user_dir)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_index(user_dir: str, index: dict):
    path = index_path(user_dir)
    atomic_write_json(path, index, indent=2)


def generate_summary(provider, messages: list[dict]) -> str:
    """子代理：用独立 LLM 调用生成一句话对话摘要（不超过 30 字）

    取最近 12 条核心 user/assistant 消息（跳过 tool_calls 和 tool 结果），
    使用简短 system prompt 约束输出。
    """
    core = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if role in ("user", "assistant") and content and not m.get("tool_calls"):
            core.append({"role": role, "content": content[:300]})

    if not core:
        return ""

    conv_text = "\n".join(f"{m['role']}: {m['content']}" for m in core[-12:])
    prompt = [
        {"role": "system", "content": "你是一个中文对话摘要工具。必须用中文输出，总结以下对话讨论的主题，不超过30字。只输出中文摘要文本，不要引号、标点、前缀、解释、英文。"},
        {"role": "user", "content": f"用一句中文总结以下对话（30字内）：\n\n{conv_text}"},
    ]

    try:
        response = provider.respond(prompt, tools=None)
        summary = response.text.strip()
        summary = re.sub(r'^["\'\`「]|["\'\`」]$', '', summary).strip()
        summary = re.sub(r'^(摘要[：:]?\s*)', '', summary)
        return summary[:50]
    except Exception:
        return ""


def summarize_and_store(provider, messages: list[dict], user_dir: str) -> str:
    """生成摘要并存入索引，返回摘要文本。

    即使 LLM 摘要失败，也会写入 msg_count，确保归档同步链路不中断。
    """
    if not messages:
        return ""
    summary = generate_summary(provider, messages)
    if not summary:
        summary = f"{len(messages)} 条消息"

    index = load_index(user_dir)
    index["chat_data.json"] = {
        "summary": summary,
        "msg_count": len(messages),
    }
    save_index(user_dir, index)
    return summary


def sync_to_new_archives(user_dir: str, before: set = None):
    """将当前对话摘要同步到 /clear 或 /archive 新生成的归档文件"""
    archive_dir = os.path.join(user_dir, "history", "archive")
    if not os.path.isdir(archive_dir):
        return
    if before is None:
        before = set()

    index = load_index(user_dir)
    current_meta = index.pop("chat_data.json", None)
    if not current_meta:
        return

    after = set(os.listdir(archive_dir))
    for name in after - before:
        if name.endswith(".json.gz") or name.endswith(".json"):
            index[name] = current_meta
    save_index(user_dir, index)
