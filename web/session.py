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


def require_session():
    """从 Flask session 获取当前用户并校验登录状态。

    无有效 session 时返回 (None, error_response, 401)，
    有 session 时返回 (session_data, None, None)。
    用于所有 Web API 端点替代 or get_active_user() fallback。
    """
    user_name = flask_session.get("user_name")
    if not user_name:
        return None, jsonify({"error": "未登录，请先选择用户"}), 401
    session_data = get_session(user_name)
    if not session_data or not session_data.get("chat"):
        return None, jsonify({"error": "用户会话无效，请重新选择用户"}), 401
    return session_data, None, None


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
    # 确保用户知识库目录存在（兼容旧用户迁移）
    kb_dir = os.path.join(user_dir, "knowledge")
    os.makedirs(kb_dir, exist_ok=True)

    provider = create_provider(user_config, core_config)
    chat = ChatManager(user_dir, core_config, user_config)
    chat.set_provider(provider)

    # 注入 auto_improve 上下文（供 auto_improve_review 工具使用）
    import plugins.auto_improve.tool as ai_tool
    ai_tool.set_auto_improve_context(provider=provider, chat=chat, user_name=user_name)
    # 注入 task_plan 上下文（供 task_plan_create 工具使用）
    import plugins.task_plan.tool as tp_tool
    tp_tool.set_task_plan_context(provider=provider, chat=chat, user_name=user_name)
    # 注入 vision_universal 上下文（供 vision_universal 使用 session provider）
    import plugins.vision_universal.tool as vu_tool
    vu_tool.set_vision_context(provider=provider, chat=chat, user_name=user_name)
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
