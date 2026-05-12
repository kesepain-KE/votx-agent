"""会话管理 — 支持多用户并发"""
import json
import os
from flask import session as flask_session
from run.chat import ChatManager
from run.prompt_cache import build_cached_system_prompt
from run.tool import ToolRunner, load_tool_schemas
from provider.factory import create_provider
from paths import get_project_root

_root = get_project_root()

_sessions: dict[str, dict] = {}  # user_name -> session dict
_active_user: str | None = None


def get_session(user_name: str = None) -> dict | None:
    """获取指定用户的 session"""
    name = user_name or _active_user
    if name is None:
        return None
    return _sessions.get(name)


def set_active_user(user_name: str):
    """设置当前活跃用户"""
    global _active_user
    _active_user = user_name


def get_active_user() -> str | None:
    """获取当前活跃用户"""
    return _active_user


def clear_session(user_name: str = None):
    """清除指定用户的 session"""
    global _active_user
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
    import skills.auto_improve.tool as ai_tool
    ai_tool.set_auto_improve_context(provider=provider, chat=chat, user_name=user_name)
    # 注入 task_plan 上下文（供 task_plan_create 工具使用）
    import skills.task_plan.tool as tp_tool
    tp_tool.set_task_plan_context(provider=provider, chat=chat, user_name=user_name)
    try:
        chat.load_history()
    except Exception:
        pass
    system_prompt = build_cached_system_prompt(root, user_dir)
    # tools 必须在 system_prompt 之后加载 —— register_all() 在 build_system_prompt 内部执行
    tools = load_tool_schemas()
    tool_runner = ToolRunner(core_config, user_config)
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
    _sessions[user_name] = session_data
    set_active_user(user_name)
    os.environ["VOTX_USER_DIR"] = user_dir
    return session_data
