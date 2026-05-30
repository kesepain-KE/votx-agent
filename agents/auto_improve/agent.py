# -*- coding: utf-8 -*-
"""Auto Improve 子代理 — 对话记忆提取与管理

两种触发模式 + 权限边界：

1. 被动触发 (消息达上限 / cron) — run_auto_improve()
   读: improve/*/temporary/  (已有临时内容，用于去重)
   写: improve/*/temporary/  (新发现的临时内容)
   禁止: 读取 permanent、写入 permanent

2. 主动触发 (用户调用 auto_improve_review) — run_auto_improve_active()
   读: improve/*/temporary/ + improve/*/permanent/
   写: improve/*/permanent/ (确认晋升)
   写: improve/review_log.jsonl (记录合并结果)
   禁止: 直接修改 temporary

临时文件清理由 auto_improve_cleanup_reviewed 工具独立处理。
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from run.io_utils import atomic_write_text

_VALID_SUBS = ("memory", "self-improving", "ontology")


def _improve_dir(user_dir: str) -> str:
    """执行 improve_dir 内部辅助逻辑。"""
    return os.path.join(user_dir, "improve")


def _safe_filename(name: str) -> str:
    """执行 safe_filename 内部辅助逻辑。"""
    safe = re.sub(r'[^\w\-.]', '_', name)
    return safe.strip("_") or "untitled"


def _extract_conversation_text(messages: list[dict], user_focused: bool = False) -> list[dict]:
    """提取纯对话（用户 + 助手回复，去除 tool_calls 和思考）

    Args:
        messages: 完整消息列表
        user_focused: True 时只提取用户消息（被动触发用）
    """
    core = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if user_focused:
            if role == "user" and content:
                core.append({"role": role, "content": content[:500]})
        else:
            if role in ("user", "assistant") and content and not m.get("tool_calls"):
                core.append({"role": role, "content": content[:500]})
    return core


def _read_files_by_tier(user_dir: str, tier: str) -> dict[str, str]:
    """读取指定 tier 下的所有记忆文件"""
    result = {}
    for sub in _VALID_SUBS:
        d = os.path.join(_improve_dir(user_dir), sub, tier)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.endswith(".md"):
                fp = os.path.join(d, name)
                try:
                    content = Path(fp).read_text(encoding="utf-8")
                    result[f"{sub}/{tier}/{name}"] = content
                except Exception:
                    pass
    return result


def _list_temp_files(user_dir: str) -> dict[str, list[str]]:
    """返回 temporary 层文件快照: {sub: [filename, ...]}"""
    result = {}
    for sub in _VALID_SUBS:
        temp_dir = os.path.join(_improve_dir(user_dir), sub, "temporary")
        if os.path.isdir(temp_dir):
            files = [f for f in os.listdir(temp_dir) if f.endswith(".md")]
            if files:
                result[sub] = files
    return result


def _ensure_dirs(user_dir: str):
    """执行 ensure_dirs 内部辅助逻辑。"""
    for sub in _VALID_SUBS:
        for tier in ("temporary", "permanent"):
            os.makedirs(os.path.join(_improve_dir(user_dir), sub, tier), exist_ok=True)


def _load_agent_md() -> str:
    """执行 load_agent_md 内部辅助逻辑。"""
    root = Path(__file__).resolve().parent.parent.parent
    agent_md_path = root / "agents" / "auto_improve" / "AGENT.md"
    if agent_md_path.exists():
        return agent_md_path.read_text(encoding="utf-8")
    return ""


def _build_agent_messages(
    conv_core: list[dict],
    reference_memory: dict[str, str],
    mode: str,
    reference_label: str,
    target_label: str,
) -> list[dict]:
    """构建子代理 LLM 调用 messages"""
    system_prompt = _load_agent_md()

    conv_text = "\n".join(
        f"[{m['role']}]: {m['content']}" for m in conv_core
    )

    ref_text = f"（无已有{reference_label}）\n"
    if reference_memory:
        parts = [f"## 已有{reference_label}\n"]
        for path, content in reference_memory.items():
            parts.append(f"### {path}\n{content}\n")
        ref_text = "\n".join(parts)

    user_message = (
        f"模式: {mode}\n"
        f"参考层: {reference_label}（已固化内容，避免重复）\n"
        f"写入层: {target_label}\n\n"
        f"## 当前对话\n\n{conv_text}\n\n"
        f"{ref_text}"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]


def _parse_response(response_text: str) -> list[dict]:
    """从 LLM 响应中解析 JSON 操作列表"""
    try:
        text = response_text.strip()
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                text = text[start:end]
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                text = text[start:end]
        ops = json.loads(text)
        if isinstance(ops, list):
            return ops
        return []
    except json.JSONDecodeError:
        return []


def _apply_operations(ops: list[dict], user_dir: str, target_tier: str) -> tuple[int, list]:
    """执行记忆操作列表，返回 (执行数, 错误列表)"""
    executed = 0
    errors = []

    for op in ops:
        action = op.get("action", "")
        sub = op.get("sub", "memory")
        filename = _safe_filename(op.get("filename", "untitled"))
        content = op.get("content", "")

        if sub not in _VALID_SUBS:
            errors.append(f"无效 sub: {sub}")
            continue
        if not content and action != "delete":
            continue

        target_dir = os.path.join(_improve_dir(user_dir), sub, target_tier)
        filepath = os.path.join(target_dir, f"{filename}.md")

        try:
            if action in ("create", "update"):
                atomic_write_text(filepath, content.strip() + "\n")
                executed += 1
            elif action == "delete":
                if os.path.exists(filepath):
                    os.remove(filepath)
                    executed += 1
            elif action == "append":
                existing = ""
                if os.path.exists(filepath):
                    existing = Path(filepath).read_text(encoding="utf-8")
                new_content = existing.rstrip() + "\n\n" + content.strip() + "\n"
                atomic_write_text(filepath, new_content)
                executed += 1
        except Exception as e:
            errors.append(f"{action} {filepath}: {e}")

    if executed > 0:
        from run.prompt_cache import invalidate_prompt_cache
        invalidate_prompt_cache(os.path.basename(user_dir))

    return executed, errors


# ──── review_log ────

def _review_log_path(user_dir: str) -> str:
    """返回 review_log.jsonl 的完整路径"""
    return os.path.join(_improve_dir(user_dir), "review_log.jsonl")


def _write_review_log(
    user_dir: str,
    ops: list[dict],
    temp_files_before: dict[str, list[str]],
    executed: int,
    errors: list,
):
    """将一次 active review 的结果写入 review_log.jsonl。

    每条记录:
      { ts, ops_count, ops_summary, files_absorbed, files_remaining, errors }
    """
    log_path = _review_log_path(user_dir)

    # 记录哪些临时文件被本次 review 覆盖了（作为 "absorbed" 候选）
    # 简化策略：所有 review 前存在的临时文件都标记为"已被审阅"
    files_absorbed = []
    for sub, filenames in temp_files_before.items():
        for fn in filenames:
            files_absorbed.append(f"{sub}/{fn}")

    ops_summary = []
    for op in ops:
        ops_summary.append({
            "action": op.get("action"),
            "sub": op.get("sub"),
            "filename": op.get("filename"),
        })

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ops_count": executed,
        "ops_summary": ops_summary[:50],  # 最多记录 50 个操作摘要
        "files_absorbed": files_absorbed,
        "errors": errors[:10],
    }

    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def get_review_log(user_dir: str, limit: int = 20) -> list[dict]:
    """读取最近 N 条 review 日志"""
    log_path = _review_log_path(user_dir)
    if not os.path.exists(log_path):
        return []
    entries = []
    try:
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    pass
    except Exception:
        pass
    return entries[-limit:]


def get_absorbed_temp_files(user_dir: str) -> set:
    """从 review_log 中提取所有已被标记为 absorbed 的临时文件路径"""
    absorbed = set()
    entries = get_review_log(user_dir, limit=100)
    for entry in entries:
        for f in entry.get("files_absorbed", []):
            absorbed.add(f)
    return absorbed


def cleanup_reviewed_temp_files(user_dir: str) -> tuple[int, list[str]]:
    """删除已被 review 标记为 absorbed 的临时文件。

    Returns:
        (deleted_count, deleted_paths)
    """
    absorbed = get_absorbed_temp_files(user_dir)
    if not absorbed:
        return 0, []

    deleted = []
    for absorbed_path in absorbed:
        # absorbed_path 格式: "memory/identity.md"
        full_path = os.path.join(_improve_dir(user_dir), absorbed_path)
        try:
            if os.path.isfile(full_path):
                os.remove(full_path)
                deleted.append(absorbed_path)
        except OSError:
            pass

    if deleted:
        from run.prompt_cache import invalidate_prompt_cache
        invalidate_prompt_cache(os.path.basename(user_dir))

    return len(deleted), deleted


# ──── 入口函数 ────


def run_auto_improve(provider, messages: list[dict], user_dir: str) -> dict:
    """被动触发 — 消息达上限或 cron 时调用。

    权限: 只读 temporary，只写 temporary。禁止访问 permanent。

    Args:
        provider: LLM provider
        messages: 被裁剪的旧消息（或当前消息）
        user_dir: 用户目录
    """
    _ensure_dirs(user_dir)

    conv_core = _extract_conversation_text(messages, user_focused=True)
    if len(conv_core) < 2:
        return {"operations": 0, "errors": [], "summary": "用户消息太少，跳过记忆提取"}

    # 被动模式: 只读 temporary，用于临时层内部去重
    reference = _read_files_by_tier(user_dir, "temporary")
    agent_messages = _build_agent_messages(
        conv_core, reference,
        mode="被动触发（消息达上限/cron）",
        reference_label="临时记忆/规则/知识图谱",
        target_label="临时记忆/规则/知识图谱",
    )

    try:
        response = provider.respond(agent_messages, tools=None)
        response_text = response.text
    except Exception as e:
        return {"operations": 0, "errors": [str(e)], "summary": f"LLM 调用失败: {e}"}

    ops = _parse_response(response_text)
    if not ops:
        return {"operations": 0, "errors": [], "summary": "未解析出记忆操作"}

    executed, errors = _apply_operations(ops, user_dir, "temporary")
    summary = f"[被动] 已执行 {executed} 个临时记忆操作"
    if errors:
        summary += f"，{len(errors)} 个失败"
    return {"operations": executed, "errors": errors, "summary": summary}


def run_auto_improve_active(provider, messages: list[dict], user_dir: str) -> dict:
    """主动触发 — 用户调用 auto_improve_review 时调用。

    权限: 读 temporary + permanent，只写 permanent + review_log。
    禁止直接修改 temporary。

    Args:
        provider: LLM provider
        messages: 当前全部消息
        user_dir: 用户目录
    """
    _ensure_dirs(user_dir)

    conv_core = _extract_conversation_text(messages, user_focused=False)
    if len(conv_core) < 2:
        return {"operations": 0, "errors": [], "summary": "对话太短，跳过记忆审阅"}

    # 快照：审阅前的临时文件列表
    temp_before = _list_temp_files(user_dir)

    # 同时读取 temporary + permanent 作为参考层
    ref_temp = _read_files_by_tier(user_dir, "temporary")
    ref_perm = _read_files_by_tier(user_dir, "permanent")
    reference = {**ref_temp, **ref_perm}  # temp 优先出现在 key 中（虽然不会冲突）

    agent_messages = _build_agent_messages(
        conv_core, reference,
        mode="主动触发（用户调用审阅）",
        reference_label="临时记忆 + 永久记忆（待审阅 vs 已固化）",
        target_label="永久记忆/规则/知识图谱",
    )

    try:
        response = provider.respond(agent_messages, tools=None)
        response_text = response.text
    except Exception as e:
        return {"operations": 0, "errors": [str(e)], "summary": f"LLM 调用失败: {e}"}

    ops = _parse_response(response_text)
    if not ops:
        return {"operations": 0, "errors": [], "summary": "未解析出记忆操作"}

    executed, errors = _apply_operations(ops, user_dir, "permanent")

    # 写入 review_log（用于后续 cleanup_reviewed）
    _write_review_log(user_dir, ops, temp_before, executed, errors)

    summary = f"[主动] 已执行 {executed} 个永久记忆操作，审阅日志已记录"
    if errors:
        summary += f"，{len(errors)} 个失败"
    return {"operations": executed, "errors": errors, "summary": summary}
