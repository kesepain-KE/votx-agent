"""对话管理 - 消息组装、历史加载保存、压缩归档"""
import gzip
import json
import os
from datetime import datetime, timezone
from typing import Any


class ChatManager:
    """管理对话消息列表和历史记录"""

    def __init__(self, user_dir: str, core_config: dict[str, Any], user_config: dict[str, Any]):
        hist_cfg = core_config["history"]
        self.max_history = hist_cfg["history_max"]
        self.zip_history = hist_cfg["zip_history"]
        user_hist = user_config.get("history", {})
        data_file = user_hist.get("data", "chat_data.json")
        log_file = user_hist.get("log", "chat_log.json")
        self.data_path = os.path.join(user_dir, "history", "chat", data_file)
        self.log_path = os.path.join(user_dir, "history", "log", log_file)
        self.tool_log_path = os.path.join(user_dir, "history", "log", "tool_log.json")
        self.archive_dir = os.path.join(user_dir, "history", "archive")
        self.system_prompt = ""
        self.messages: list[dict[str, Any]] = []

        # 累计 Token 统计（跨轮会话累加）
        self.token_stats: dict[str, int] = {
            "prompt_tokens": 0,       # 累计输入
            "completion_tokens": 0,   # 累计输出（含思考）
            "cached_tokens": 0,       # 累计输入缓存命中
            "total_tokens": 0,        # 累计总量
            "task_tokens": 0,         # 工具调用轮消耗合计
            "rounds": 0,              # 对话轮数（用户发言次数）
            "total_elapsed_ms": 0,    # 累计耗时（毫秒）
        }

    def accumulate_usage(self, usage: dict, is_tool_round: bool, elapsed_ms: int):
        """累加一轮 LLM 调用的 token 消耗

        Args:
            usage: Provider 返回的 usage 字典（含 prompt_tokens 等）
            is_tool_round: 本次调用是否包含工具调用（非最终回复）
            elapsed_ms: 从本回合开始到现在的累计毫秒
        """
        if not usage:
            return
        s = self.token_stats
        inc = usage.get("total_tokens", 0)
        s["prompt_tokens"] += usage.get("prompt_tokens", 0)
        s["completion_tokens"] += usage.get("completion_tokens", 0)
        s["cached_tokens"] += usage.get("cached_tokens", 0)
        s["total_tokens"] += inc
        if is_tool_round:
            s["task_tokens"] += inc
        s["rounds"] += 1
        s["total_elapsed_ms"] += elapsed_ms

    # ---- system prompt ----

    def set_system_prompt(self, prompt: str):
        self.system_prompt = prompt

    # ---- 消息组装 ----

    def build_messages(self) -> list[dict[str, Any]]:
        """组装完整消息列表: system + history"""
        msgs: list[dict[str, Any]] = []
        if self.system_prompt:
            msgs.append({"role": "system", "content": self.system_prompt})
        msgs.extend(self.messages)
        return msgs

    # ---- 添加消息 ----

    def add_user_message(self, content: str):
        self._trim_if_needed()
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str, reasoning_content: str = ""):
        msg: dict[str, Any] = {"role": "assistant", "content": content}
        if reasoning_content:
            msg["reasoning_content"] = reasoning_content
        self.messages.append(msg)

    def add_tool_call_message(self, tool_calls, reasoning_content: str = ""):
        """将 SDK tool_calls 对象转为可序列化 dict 后追加"""
        tc_list = []
        for tc in tool_calls:
            tc_list.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            })
        msg: dict[str, Any] = {
            "role": "assistant",
            "content": None,
            "tool_calls": tc_list,
        }
        if reasoning_content:
            msg["reasoning_content"] = reasoning_content
        self.messages.append(msg)

    def add_tool_results(self, tool_outputs: list[dict[str, Any]]):
        self._trim_if_needed()
        self.messages.extend(tool_outputs)

    # ---- 持久化 ----

    def load_history(self):
        """从 JSON 文件恢复历史消息（损坏时自动修复 + tool_calls 链完整性检查）"""
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self.messages = data
                    self._repair_tool_chain()
            except (json.JSONDecodeError, Exception):
                # 损坏时备份并重置
                corrupt_path = self.data_path + ".corrupt"
                try:
                    os.rename(self.data_path, corrupt_path)
                except Exception:
                    pass
                self.messages = []

    def _repair_tool_chain(self):
        """修复历史中的 tool_calls 链断裂

        三种情况都会导致 Provider 400：
        1) assistant(tool_calls) 之后缺少对应的 tool 消息（前向断裂）
        2) tool 消息之前缺少对应的 assistant(tool_calls)（后向断裂，孤立 tool）
        3) tool 消息出现在其匹配的 assistant(tool_calls) 之前（乱序）
           — 常见于 _trim_if_needed 剪切历史后，剩余消息以 tool 开头
        """
        # 第一遍：收集所有 assistant(tool_calls) 声明的 tool_call_id 集合
        valid_ids: set[str] = set()
        for msg in self.messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    valid_ids.add(tc["id"])

        # 第二遍：按顺序扫描，维护"已出现过的 assistant(tc) ID"集合
        # tool 消息不仅需要 ID 存在于 valid_ids，还必须已见过其匹配的 assistant(tc)
        seen_tc_ids: set[str] = set()
        i = 0
        cut_at = None
        while i < len(self.messages):
            msg = self.messages[i]
            if msg.get("role") == "tool":
                tid = msg.get("tool_call_id", "")
                if tid not in valid_ids or tid not in seen_tc_ids:
                    cut_at = i
                    break
                i += 1
            elif msg.get("role") == "assistant" and msg.get("tool_calls"):
                tc_list = msg["tool_calls"]
                for tc in tc_list:
                    seen_tc_ids.add(tc["id"])
                needed = len(tc_list)
                expected_ids = {tc["id"] for tc in tc_list}
                j = i + 1
                found = 0
                while j < len(self.messages) and found < needed:
                    nxt = self.messages[j]
                    if nxt.get("role") == "tool":
                        tid = nxt.get("tool_call_id", "")
                        if tid in expected_ids:
                            found += 1
                        j += 1
                    else:
                        break
                if found < needed:
                    cut_at = i
                    break
                i = j
            else:
                i += 1

        if cut_at is not None:
            dropped = len(self.messages) - cut_at
            self.messages = self.messages[:cut_at]
            print(f"[历史修复] 检测到断裂的 tool_calls 链，已切除末尾 {dropped} 条消息")

    def save_history(self):
        """落盘历史消息（不含 system prompt）

        写入前自动闭合末尾未完成的 tool_calls 链——防止 Ctrl+C 中断后
        下次启动时 Provider 因断链而报 400 错误。
        """
        self._close_tool_chain()
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(self.messages, f, ensure_ascii=False, indent=2)

    def _close_tool_chain(self):
        """如果最后一条消息是未闭合的 assistant(tool_calls)，补上 tool 错误消息"""
        if not self.messages:
            return
        last = self.messages[-1]
        if last.get("role") != "assistant" or not last.get("tool_calls"):
            return
        # 检查是否已有 tool 响应（正常流程不会走到这）
        tc_list = last["tool_calls"]
        for tc in tc_list:
            self.messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": "ERROR: 程序中断，工具调用未完成",
            })

    def save_log(self, full_messages: list[dict[str, Any]]):
        """落盘完整日志（含 system prompt + 本次响应）"""
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        with open(self.log_path, "w", encoding="utf-8") as f:
            json.dump(full_messages, f, ensure_ascii=False, indent=2)

    # ---- 历史压缩归档 ----

    @staticmethod
    def _extract_digest(messages: list[dict[str, Any]], max_items: int = 6) -> list[str]:
        """从消息列表中提取关键用户/助手对话摘要。

        只取 user 和 assistant(非 tool_calls) 消息的 content，
        保留最先和最后各 max_items//2 条，中间截断。
        """
        lines: list[str] = []
        for m in messages:
            role = m.get("role", "")
            if role == "user":
                c = m.get("content", "")
                if c:
                    lines.append(f"  用户: {c}" if len(c) <= 80 else f"  用户: {c[:77]}...")
            elif role == "assistant" and not m.get("tool_calls"):
                c = m.get("content", "")
                if c:
                    lines.append(f"  助手: {c}" if len(c) <= 80 else f"  助手: {c[:77]}...")

        if len(lines) <= max_items:
            return lines

        half = max_items // 2
        return lines[:half] + ["  ..."] + lines[-half:]

    def _trim_if_needed(self):
        """超过最大条数时裁剪；确保不切断 tool_calls/tool_result 配对。

        裁剪后将旧消息归档，并插入一条摘要消息到历史开头，
        让 LLM 知道前面聊过什么、什么时候聊的。
        """
        if len(self.messages) < self.max_history:
            return

        keep = self.max_history // 2
        cut = len(self.messages) - keep

        # 向后扫描到安全切点：不在 tool_calls/tool 配对中间截断
        safe = cut
        for i in range(cut, len(self.messages)):
            role = self.messages[i].get("role", "")
            if role != "tool":
                safe = i
                break
        else:
            safe = cut  # fallback

        trimmed = self.messages[:safe]
        self.messages = self.messages[safe:]

        # 生成摘要并插入历史开头
        digest = self._extract_digest(trimmed)
        if digest:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            lines = [
                f"[历史压缩] 以下是之前 {len(trimmed)} 条对话的摘要（已归档保存）：",
                *digest,
                f"归档时间: {ts}",
            ]
            self.messages.insert(0, {
                "role": "user",
                "content": "\n".join(lines),
            })

        if self.zip_history and trimmed:
            self._archive(trimmed)

    def _archive(self, old_messages: list[dict[str, Any]]):
        """将旧消息归档到独立文件。

        zip_history=True → gzip 压缩 (.json.gz)，节省约 80% 空间
        zip_history=False → 纯 JSON
        """
        try:
            os.makedirs(self.archive_dir, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%f")
            payload = json.dumps(old_messages, ensure_ascii=False, indent=2).encode("utf-8")

            if self.zip_history:
                archive_path = os.path.join(self.archive_dir, f"history_{ts}.json.gz")
                with gzip.open(archive_path, "wb", compresslevel=6) as f:
                    f.write(payload)
            else:
                archive_path = os.path.join(self.archive_dir, f"history_{ts}.json")
                with open(archive_path, "wb") as f:
                    f.write(payload)
        except Exception:
            pass  # 归档失败不影响主流程

    # ---- 用户命令 ----

    def clear_history(self) -> str:
        """清除当前对话历史（先归档再清空），返回提示信息"""
        if not self.messages:
            return "没有可清除的历史记录。"
        count = len(self.messages)
        self._archive(self.messages)
        self.messages = []
        try:
            if os.path.exists(self.data_path):
                os.remove(self.data_path)
        except Exception:
            pass
        # 同时清空工具日志
        tl_count = 0
        try:
            if os.path.exists(self.tool_log_path):
                with open(self.tool_log_path, encoding="utf-8") as f:
                    tl_count = sum(1 for _ in f)
                os.remove(self.tool_log_path)
        except Exception:
            pass
        extra = f"，{tl_count} 条工具日志已清空" if tl_count else ""
        return f"已清除 {count} 条历史消息（归档备份已保存）{extra}。"

    def archive_now(self) -> str:
        """手动归档当前全部历史，不清空"""
        if not self.messages:
            return "没有可归档的历史记录。"
        count = len(self.messages)
        self._archive(list(self.messages))
        return f"已归档 {count} 条历史消息。"

    def history_stats(self) -> str:
        """返回当前历史状态摘要"""
        msg_count = len(self.messages)
        # 估算大小
        try:
            size = os.path.getsize(self.data_path) if os.path.exists(self.data_path) else 0
        except OSError:
            size = 0
        # 工具日志条数
        tool_log_count = 0
        try:
            if os.path.exists(self.tool_log_path):
                with open(self.tool_log_path, encoding="utf-8") as f:
                    tool_log_count = sum(1 for _ in f)
        except Exception:
            pass
        # 归档文件数（含 .json 和 .json.gz）
        archive_count = 0
        if os.path.isdir(self.archive_dir):
            try:
                archive_count = len([
                    f for f in os.listdir(self.archive_dir)
                    if (f.endswith(".json") or f.endswith(".json.gz"))
                    and os.path.isfile(os.path.join(self.archive_dir, f))
                ])
            except OSError:
                pass
        lines = [
            f"当前会话消息: {msg_count} 条（上限 {self.max_history}）",
            f"历史文件大小: {_fmt_bytes(size)}",
            f"工具调用日志: {tool_log_count} 条",
            f"归档备份数: {archive_count} 个",
            f"自动归档: {'开' if self.zip_history else '关'}",
        ]
        return "\n".join(lines)


def _fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    else:
        return f"{n / 1024 / 1024:.1f} MB"
