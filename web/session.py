"""会话管理 — 全局会话状态与用户初始化"""
import json
import os
import traceback

from paths import get_project_root

# 项目根目录（dev / PyInstaller 通用）
_root = get_project_root()

# 会话状态
_session: dict = {}


def _init_session(user_name: str) -> dict:
    """初始化用户会话，返回会话状态"""
    from provider.factory import create_provider
    from run.chat import ChatManager
    from run.engine import build_system_prompt
    from run.tool import ToolRunner, load_tool_schemas

    root = _root
    user_dir = os.path.join(root, "users", user_name)

    if not os.path.isdir(user_dir):
        return {"error": f"用户目录不存在: {user_name}"}

    try:
        with open(os.path.join(root, "config", "config_core.json"), encoding="utf-8") as f:
            core_config = json.load(f)
        with open(os.path.join(user_dir, "config.json"), encoding="utf-8") as f:
            user_config = json.load(f)

        provider = create_provider(user_config, core_config)
        tool_runner = ToolRunner(core_config, user_config)
        system_prompt = build_system_prompt(root, user_dir)
        tools = load_tool_schemas()

        chat = ChatManager(user_dir, core_config, user_config)
        chat.set_system_prompt(system_prompt)
        chat.load_history()

        _session.update({
            "user_name": user_name,
            "user_dir": user_dir,
            "root": root,
            "core_config": core_config,
            "user_config": user_config,
            "provider": provider,
            "tool_runner": tool_runner,
            "tools": tools,
            "chat": chat,
        })
        os.environ["VOTX_USER_DIR"] = user_dir
        return {"ok": True, "user": user_name}
    except Exception as e:
        traceback.print_exc()
        return {"error": f"初始化失败: {e}"}
