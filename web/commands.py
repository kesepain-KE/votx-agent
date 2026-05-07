"""命令分发 — /clear /history /archive /retry /help 等"""
import os

from run.summarize import (generate_summary, load_index, save_index,
                           summarize_and_store, sync_to_new_archives)


def _web_summarize(session_data=None) -> str:
    """Web 会话摘要：从 session_data 取 provider/messages/user_dir"""
    if session_data is None:
        from web.session import get_session
        session_data = get_session()
    if not session_data:
        return "没有可摘要的内容"
    chat = session_data.get("chat")
    provider = session_data.get("provider")
    user_dir = session_data.get("user_dir")
    if not chat or not provider or not user_dir or not chat.messages:
        return "没有可摘要的内容"
    return summarize_and_store(provider, chat.messages, user_dir)


def _archive_current_with_summary(session_data, clear_after: bool = False) -> dict:
    """归档当前对话并同步摘要索引，可选归档后清空当前对话。"""
    chat = session_data.get("chat")
    user_dir = session_data.get("user_dir")
    if not chat or not user_dir or not chat.messages:
        return {"type": "command_result", "content": "没有可归档的历史记录。", "summary": ""}

    before = set()
    archive_dir = os.path.join(user_dir, "history", "archive")
    if os.path.isdir(archive_dir):
        before = set(os.listdir(archive_dir))

    summary = _web_summarize(session_data)
    msg = chat.archive_now()
    sync_to_new_archives(user_dir, before)

    if clear_after:
        count = len(chat.messages)
        chat.messages = []
        try:
            if os.path.exists(chat.data_path):
                os.remove(chat.data_path)
        except Exception:
            pass
        _clear_tool_logs(chat)
        msg = f"已归档并开启新对话，共保存 {count} 条历史消息。"

    content = msg
    if summary and summary != "没有可摘要的内容":
        content += f" 摘要：{summary}"
    return {"type": "command_result", "content": content, "summary": summary}


def _clear_tool_logs(chat) -> int:
    """清理新旧工具日志，返回删除的日志行数。"""
    tl_count = 0
    old_log_path = os.path.join(os.path.dirname(chat.tool_log_path), "tool_log.json")
    for log_path in (chat.tool_log_path, old_log_path):
        try:
            if os.path.exists(log_path):
                with open(log_path, encoding="utf-8") as f:
                    tl_count += sum(1 for _ in f)
                os.remove(log_path)
        except Exception:
            pass
    return tl_count


def _dispatch(cmd: str, session_data=None) -> dict | None:
    """处理斜杠命令，返回 JSON 结果。None 表示不是命令"""
    if session_data is None:
        from web.session import get_session
        session_data = get_session()
    if session_data is None:
        return {"type": "error", "content": "未选择用户"}

    chat = session_data.get("chat")
    if not chat:
        return {"type": "error", "content": "未选择用户"}

    cmd = cmd.strip().lower()
    if cmd in ("/exit", "/quit", "/q"):
        return {"type": "command_result", "content": "Web UI 中请使用侧栏「断开」按钮退出会话。"}
    if cmd == "/clear":
        count = len(chat.messages)
        chat.messages = []
        try:
            if os.path.exists(chat.data_path):
                os.remove(chat.data_path)
        except Exception:
            pass
        tl_count = _clear_tool_logs(chat)
        extra = f"，{tl_count} 条工具日志已清空" if tl_count else ""
        return {"type": "command_result", "content": f"已清除 {count} 条历史消息{extra}。"}
    if cmd in ("/history", "/stats"):
        return {"type": "command_result", "content": chat.history_stats()}
    if cmd == "/archive":
        return _archive_current_with_summary(session_data, clear_after=False)
    if cmd in ("/new", "/newchat", "/new-chat", "/新对话"):
        return _archive_current_with_summary(session_data, clear_after=True)
    if cmd in ("/summarize", "/summary", "/总结"):
        summary = _web_summarize(session_data)
        return {"type": "command_result", "content": f"对话摘要: {summary}"}
    if cmd == "/retry":
        if not chat.messages:
            return {"type": "command_result", "content": "没有可重试的消息", "retry": False}
        last_user_idx = -1
        for i in range(len(chat.messages) - 1, -1, -1):
            if chat.messages[i].get("role") == "user":
                last_user_idx = i
                break
        if last_user_idx == -1:
            return {"type": "command_result", "content": "没有可重试的消息", "retry": False}
        user_msg = chat.messages[last_user_idx].get("content", "")
        chat.messages = chat.messages[:last_user_idx]
        chat.save_history()
        return {"type": "command_result", "content": user_msg, "retry": True}
    if cmd == "/help":
        return {"type": "command_result", "content": (
            "可用命令:\n"
            "  /clear — 清除当前对话历史及工具日志\n"
            "  /archive — 保存当前对话并生成摘要\n"
            "  /new — 保存当前对话摘要后开启新对话\n"
            "  /summarize — 生成当前对话摘要\n"
            "  /history 或 /stats — 查看当前会话统计\n"
            "  /retry — 移除上一条 AI 回复并重新生成\n"
            "  /help — 显示本帮助信息"
        )}
    return None
