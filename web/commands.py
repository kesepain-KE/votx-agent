"""命令分发 — /clear /history /archive /retry /help 等"""
import os

from run.summarize import (generate_summary, load_index, save_index,
                           summarize_and_store, sync_to_new_archives)
from web.session import _session


def _web_summarize() -> str:
    """Web 会话摘要：从 _session 取 provider/messages/user_dir"""
    chat = _session.get("chat")
    provider = _session.get("provider")
    user_dir = _session.get("user_dir")
    if not chat or not provider or not user_dir or not chat.messages:
        return "没有可摘要的内容"
    return summarize_and_store(provider, chat.messages, user_dir)


def _dispatch(cmd: str) -> dict | None:
    """处理斜杠命令，返回 JSON 结果。None 表示不是命令"""
    chat = _session.get("chat")
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
        tl_count = 0
        try:
            if os.path.exists(chat.tool_log_path):
                with open(chat.tool_log_path, encoding="utf-8") as f:
                    tl_count = sum(1 for _ in f)
                os.remove(chat.tool_log_path)
        except Exception:
            pass
        extra = f"，{tl_count} 条工具日志已清空" if tl_count else ""
        return {"type": "command_result", "content": f"已清除 {count} 条历史消息{extra}。"}
    if cmd in ("/history", "/stats"):
        return {"type": "command_result", "content": chat.history_stats()}
    if cmd == "/archive":
        _web_summarize()
        before = set()
        archive_dir = os.path.join(_session["user_dir"], "history", "archive")
        if os.path.isdir(archive_dir):
            before = set(os.listdir(archive_dir))
        msg = chat.archive_now()
        sync_to_new_archives(_session["user_dir"], before)
        return {"type": "command_result", "content": msg}
    if cmd in ("/summarize", "/summary", "/总结"):
        summary = _web_summarize()
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
            "  /history — 查看当前会话统计（消息数/文件大小/工具调用次数）\n"
            "  /retry — 移除上一条 AI 回复并重新生成\n"
            "  /help — 显示本帮助信息"
        )}
    return None
