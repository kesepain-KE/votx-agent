"""会话管理 — 支持多用户并发"""
import json
import os
import threading
from flask import jsonify, session as flask_session
from run.chat import ChatManager
from run.prompt_cache import build_cached_system_prompt
from run.tool import ToolRunner, load_tool_schemas
from provider.factory import create_provider
from paths import get_project_root

_root = get_project_root()

_sessions: dict[str, dict] = {}  # user_name -> session dict
_active_user: str | None = None
_session_lock = threading.RLock()


def get_session(user_name: str = None) -> dict | None:
    """获取指定用户的 session（不再回退到 active_user，防止串号）"""
    with _session_lock:
        if user_name is None:
            return None
        return _sessions.get(user_name)


def restore_user_session(user_name: str | None) -> dict | None:
    """根据 Flask cookie 中的用户名，从磁盘重新初始化进程内 session。"""
    if not user_name:
        return None
    user_name = user_name.strip()
    if not user_name or "/" in user_name or "\\" in user_name or ".." in user_name:
        return None

    users_root = os.path.realpath(os.path.join(_root, "users"))
    user_dir = os.path.realpath(os.path.join(users_root, user_name))
    if not user_dir.startswith(users_root + os.sep) and user_dir != users_root:
        return None
    if not os.path.isdir(user_dir):
        return None

    try:
        with open(os.path.join(_root, "config", "config_core.json"), encoding="utf-8") as f:
            core_config = json.load(f)
        with open(os.path.join(user_dir, "config.json"), encoding="utf-8") as f:
            user_config = json.load(f)
        return init_user_session(_root, user_dir, user_name, user_config, core_config)
    except Exception:
        return None


def get_or_restore_session(user_name: str | None) -> dict | None:
    """优先读取内存 session；服务重启后可按 cookie 用户名懒恢复。"""
    if not user_name:
        return None
    session_data = get_session(user_name)
    if session_data and session_data.get("chat"):
        return session_data
    return restore_user_session(user_name)


def require_session():
    """从 Flask session 获取当前用户并校验登录状态。

    无有效 session 时返回 (None, error_response, 401)，
    有 session 时返回 (session_data, None, None)。
    用于所有 Web API 端点替代 or get_active_user() fallback。
    """
    user_name = flask_session.get("user_name")
    if not user_name:
        return None, jsonify({"error": "未登录，请先选择用户"}), 401
    session_data = get_or_restore_session(user_name)
    if not session_data or not session_data.get("chat"):
        return None, jsonify({"error": "用户会话无效，请重新选择用户"}), 401
    return session_data, None, None


def start_active_run(session_data: dict, run_id: str):
    """Register the currently active run and return its cancel event."""
    lock = session_data.setdefault("run_lock", threading.RLock())
    cancel_event = threading.Event()
    with lock:
        session_data["run_id"] = run_id
        session_data["run_cancel_event"] = cancel_event
    return cancel_event


def cancel_active_run(session_data: dict, run_id: str | None = None) -> bool:
    """Cancel the currently active run if the run_id matches."""
    lock = session_data.setdefault("run_lock", threading.RLock())
    with lock:
        current_run_id = session_data.get("run_id")
        if run_id and current_run_id != run_id:
            return False
        cancel_event = session_data.get("run_cancel_event")
        if isinstance(cancel_event, threading.Event):
            cancel_event.set()
            return True
        return False


def clear_active_run(session_data: dict, run_id: str | None = None) -> None:
    """Clear the active run state after the turn finishes."""
    lock = session_data.setdefault("run_lock", threading.RLock())
    with lock:
        current_run_id = session_data.get("run_id")
        if run_id and current_run_id != run_id:
            return
        session_data["run_id"] = ""
        session_data["run_cancel_event"] = threading.Event()


def set_active_user(user_name: str):
    """设置当前活跃用户"""
    global _active_user
    with _session_lock:
        _active_user = user_name


def get_active_user() -> str | None:
    """获取当前活跃用户"""
    with _session_lock:
        return _active_user


def clear_session(user_name: str = None):
    """清除指定用户的 session"""
    global _active_user
    with _session_lock:
        name = user_name or _active_user
        if name and name in _sessions:
            del _sessions[name]
        if _active_user == name:
            _active_user = None


def init_user_session(root: str, user_dir: str, user_name: str, user_config: dict, core_config: dict):
    """初始化或重建用户的会话数据"""
    # 兼容旧用户迁移：只补目录和缺省模板，不覆盖已有用户文件。
    try:
        from pathlib import Path
        from set_user import ensure_user_skeleton
        ensure_user_skeleton(Path(user_dir))
    except Exception:
        os.makedirs(os.path.join(user_dir, "knowledge"), exist_ok=True)

    provider = create_provider(user_config, core_config)
    chat = ChatManager(user_dir, core_config, user_config)
    chat.set_provider(provider)

    # 注入 auto_improve 上下文（供 auto_improve_review 工具使用）
    import plugins.auto_improve.tool as ai_tool
    ai_tool.set_auto_improve_context(provider=provider, chat=chat, user_name=user_name)
    # 注入 task_plan 上下文（供 task_plan_create 工具使用）
    import plugins.task_plan.tool as tp_tool
    tp_tool.set_task_plan_context(provider=provider, chat=chat, user_name=user_name)
    # 注入多模态上下文（供 vision/audio/image/speech 所有 multimodal plugin 共用）
    from plugins._common import set_multimodal_context
    set_multimodal_context(provider=provider, chat=chat, user_name=user_name)
    try:
        chat.load_history()
    except Exception:
        pass
    system_prompt = build_cached_system_prompt(root, user_dir)
    # tools 必须在 system_prompt 之后加载 —— register_all() 在 build_system_prompt 内部执行
    from skills import load_disabled_skills
    disabled = load_disabled_skills(user_dir)
    tools = load_tool_schemas(disabled_skills=disabled)
    tool_runner = ToolRunner(core_config, user_config, user_dir=user_dir, disabled_skills=disabled)
    chat.set_system_prompt(system_prompt)

    session_data = {
        "root": root,
        "user_dir": user_dir,
        "user_name": user_name,
        "user_config": user_config,
        "core_config": core_config,
        "provider": provider,
        "chat": chat,
        "tools": tools,
        "tool_runner": tool_runner,
        "system_prompt": system_prompt,
        "run_lock": threading.RLock(),
        "run_id": "",
        "run_cancel_event": threading.Event(),
    }
    with _session_lock:
        _sessions[user_name] = session_data
    set_active_user(user_name)
    os.environ["VOTX_USER_DIR"] = user_dir

    # 会话初始化时自动清理过期临时文件（默认保留 7 天）
    try:
        from plugins.auto_improve.tool import cleanup_temp_files
        count, _ = cleanup_temp_files(user_name, retention_days=7)
        if count > 0:
            print(f"[auto_improve] 已清理 {user_name} 的 {count} 个过期临时文件")
    except Exception:
        pass

    return session_data
