"""对话管理 - 消息组装、历史加载保存、压缩归档"""
import json
import os
from datetime import datetime, timezone
from typing import Any

from run.io_utils import atomic_write_json, append_jsonl, read_json_safe, atomic_write_text


class ChatManager:
    """管理对话消息列表和历史记录"""

    def __init__(self, user_dir: str, core_config: dict[str, Any], user_config: dict[str, Any]):
        """执行 init 内部辅助逻辑。"""
        hist_cfg = core_config["history"]
        self.max_history = hist_cfg["history_max"]
        ctx_cfg = core_config.get("context_window", {})
        self.context_max = ctx_cfg.get("max_tokens", 900000)
        self.context_safe_ratio = ctx_cfg.get("safe_ratio", 0.85)
        user_hist = user_config.get("history", {})
        data_file = user_hist.get("data", "chat_data.json")
        log_file = user_hist.get("log", "chat_log.json")
        self.data_path = os.path.join(user_dir, "history", "chat", data_file)
        self.log_path = os.path.join(user_dir, "history", "log", log_file)
        self.tool_log_path = os.path.join(user_dir, "history", "log", "tool_log.jsonl")
        self.archive_dir = os.path.join(user_dir, "history", "archive")
        self.system_prompt = ""
        self.messages: list[dict[str, Any]] = []
        self.provider = None   # set_provider() 由引擎调用
        self.user_dir = user_dir
        self._prompt_valid = False  # system prompt 缓存有效性标记
        self._compress_occurred = False  # 本轮是否发生过上下文压缩（供 SSE 通知前端）

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
        """处理 set_system_prompt 相关逻辑。"""
        self.system_prompt = prompt
        self._prompt_valid = True

    def refresh_system_prompt(self, root: str):
        """重建 system prompt（带缓存：若 _prompt_valid 则跳过）"""
        if self._prompt_valid and self.system_prompt:
            return
        from run.prompt_cache import build_cached_system_prompt
        self.system_prompt = build_cached_system_prompt(root, self.user_dir)
        self._prompt_valid = True

    def invalidate_prompt(self):
        """标记 system prompt 缓存失效，下次 refresh 时重建"""
        self._prompt_valid = False

    def set_provider(self, provider):
        """设置 LLM provider（供 auto_improve 子代理使用）"""
        self.provider = provider

    # ---- 消息组装 ----

    def build_messages(self) -> list[dict[str, Any]]:
        """组装完整消息列表: system + history，自动确保不超上下文窗口。"""
        # 发送前最后一次按完整工具事务清理历史，避免任何孤立 tool
        # 或未闭合 assistant(tool_calls) 进入 Provider 请求体。
        self._repair_tool_chain()
        msgs: list[dict[str, Any]] = []
        if self.system_prompt:
            msgs.append({"role": "system", "content": self.system_prompt})
        msgs.extend(self.messages)
        return self._ensure_token_budget(msgs)

    # ---- token 估算 ----

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """估算文本 token 数。CJK 字符约 0.6 token/字，非 CJK 约 0.25 token/字。

        使用保守系数（略高估），确保实际 token 数不会超出模型上下文窗口。
        """
        if not text:
            return 0
        cjk = 0
        other = 0
        for ch in text:
            cp = ord(ch)
            if (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or
                0xF900 <= cp <= 0xFAFF or 0x20000 <= cp <= 0x2FFFF):
                cjk += 1
            elif cp > 127:
                other += 1  # 其他多字节字符（emoji, 符号等）
            else:
                other += 1
        # CJK: ~1.5 token/字（主流 tokenizer 对中文普遍 1-2.5 token/字）;
        # 非CJK多字节: ~1 token/字; ASCII: ~0.25 token/字
        # 保守估计使用略高系数
        return int(cjk * 1.5 + other * 0.3)

    @classmethod
    def _msg_tokens(cls, msg: dict[str, Any]) -> int:
        """估算单条消息的 token 数"""
        total = 0
        content = msg.get("content", "")
        if isinstance(content, str):
            total += cls._estimate_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and "text" in part:
                    total += cls._estimate_tokens(part["text"])
        for tc in msg.get("tool_calls", []):
            func = tc.get("function", {})
            total += cls._estimate_tokens(func.get("name", ""))
            total += cls._estimate_tokens(func.get("arguments", ""))
        if msg.get("reasoning_content"):
            total += cls._estimate_tokens(msg["reasoning_content"])
        return total

    def _ensure_token_budget(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """确保消息列表不超出 token 预算，超出时自动从历史前端裁剪。

        裁剪规则：
        1. system 消息保留但超大时截断
        2. 从索引 1 开始向后找安全切点（不切断 tool_calls/tool 配对）
        3. 裁剪后生成摘要插入 system 消息之后
        4. 循环裁剪直到 token 数低于 safe_budget
        """
        safe_budget = int(self.context_max * self.context_safe_ratio)

        # 快速路径
        total = sum(self._msg_tokens(m) for m in messages)
        if total <= safe_budget:
            return messages

        self._compress_occurred = True  # 真实压缩发生，通知 SSE 层

        sys_msg = messages[0] if messages and messages[0].get("role") == "system" else None
        body = messages[1:] if sys_msg else list(messages)

        # system prompt 超大时截断（极端情况，一般不会触发）
        if sys_msg:
            sys_tokens = self._msg_tokens(sys_msg)
            if sys_tokens > safe_budget:
                sys_msg = self._truncate_system_prompt(sys_msg, safe_budget)
                sys_tokens = self._msg_tokens(sys_msg)
        else:
            sys_tokens = 0

        trimmed_batches: list[list[dict]] = []

        while True:
            body_tokens = sum(self._msg_tokens(m) for m in body)
            if sys_tokens + body_tokens <= safe_budget:
                break
            if not body:
                break

            # 找事务边界：若目标落在 tool 结果中，向后移动到该事务之后。
            # 后面没有非 tool 消息时，移除整个末尾工具事务，绝不从中间切开。
            cut = 1
            for i in range(1, len(body)):
                if body[i].get("role") != "tool":
                    cut = i
                    break
            else:
                cut = len(body)

            trimmed_batches.append(body[:cut])
            body = body[cut:]

        # 生成摘要
        if trimmed_batches and body:
            all_trimmed = []
            for batch in trimmed_batches:
                all_trimmed.extend(batch)
            digest = self._extract_digest(all_trimmed)
            if digest:
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                lines = [
                    f"[上下文压缩] 以下 {len(all_trimmed)} 条消息因超出 token 上限被压缩：",
                    *digest,
                    f"压缩时间: {ts}",
                ]
                body.insert(0, {"role": "user", "content": "\n".join(lines)})

        self.messages = list(body)
        self._repair_tool_chain()
        result = [sys_msg] + self.messages if sys_msg else self.messages
        return result

    @staticmethod
    def _truncate_system_prompt(sys_msg: dict, max_tokens: int) -> dict:
        """截断 system prompt 到指定 token 预算内（极端情况应急）"""
        content = sys_msg.get("content", "")
        if not content:
            return sys_msg
        suffix = "\n\n[提示: system prompt 因超长被截断]"
        suffix_tokens = ChatManager._estimate_tokens(suffix)
        budget = max_tokens - suffix_tokens
        # 二分查找：找到最大的 safe_len 使得 estimate(content[:safe_len]) <= budget
        lo, hi = 0, len(content)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if ChatManager._estimate_tokens(content[:mid]) <= budget:
                lo = mid
            else:
                hi = mid - 1
        truncated = content[:lo]
        print(f"[上下文压缩] system prompt 过大({len(content)}字)，已截断到 {len(truncated)} 字")
        return {**sys_msg, "content": truncated + suffix}

    # ---- 添加消息 ----

    def add_user_message(self, content: str):
        """处理 add_user_message 相关逻辑。"""
        self._trim_if_needed()
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str, reasoning_content: str = ""):
        """处理 add_assistant_message 相关逻辑。"""
        msg: dict[str, Any] = {"role": "assistant", "content": content}
        if reasoning_content:
            msg["reasoning_content"] = reasoning_content
        self.messages.append(msg)

    def add_tool_call_message(self, tool_calls, reasoning_content: str = ""):
        """将 tool_calls 转为可序列化 dict 后追加（适配统一 ToolCall 和旧 SDK 对象）"""
        self._trim_if_needed()
        tc_list = []
        for tc in tool_calls:
            if hasattr(tc, "name"):
                # 统一 ToolCall 格式 (input 是 dict，需序列化回 JSON 字符串存储)
                tc_list.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.input, ensure_ascii=False),
                    },
                })
            else:
                # 旧 SDK 对象 (ChatCompletionMessageToolCall)
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
            "content": "",
            "tool_calls": tc_list,
        }
        if reasoning_content:
            msg["reasoning_content"] = reasoning_content
        self.messages.append(msg)

    def add_tool_results(self, tool_outputs: list[dict[str, Any]]):
        """处理 add_tool_results 相关逻辑。"""
        self.messages.extend(tool_outputs)

    # ---- 持久化 ----

    @staticmethod
    def read_history_file(path: str) -> list[dict[str, Any]]:
        """从 .json 或 .json.gz 读取消息列表"""
        if path.endswith(".gz"):
            import gzip
            with gzip.open(path, "rb") as f:
                data = json.loads(f.read().decode("utf-8"))
        else:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("历史文件格式错误：不是数组")
        return data

    def load_messages(self, messages: list[dict[str, Any]]) -> int:
        """替换当前消息列表并修复 tool_calls 链，返回消息数"""
        self.messages = list(messages)
        self._repair_tool_chain()
        return len(self.messages)

    def load_history(self):
        """从 JSON 文件恢复历史消息（损坏时自动修复 + tool_calls 链完整性检查）"""
        data = read_json_safe(self.data_path, default=None)
        if data is not None and isinstance(data, list):
            self.messages = data
            self._repair_tool_chain()
        elif data is None and os.path.exists(self.data_path):
            # 文件存在但损坏，备份并重置
            corrupt_path = self.data_path + ".corrupt"
            try:
                os.rename(self.data_path, corrupt_path)
            except Exception:
                pass
            self.messages = []
        else:
            self.messages = []

    def _repair_tool_chain(self) -> int:
        """按完整事务清理非法工具消息链，返回移除的消息数。

        合法事务必须是 ``assistant(tool_calls)``，后面紧跟且仅跟每个
        ``tool_call_id`` 对应的一条 ``tool`` 结果。孤立、重复、乱序、
        缺失结果或声明格式损坏的事务会被整体移除；事务之后的正常消息
        会保留，避免旧实现从异常点截断整个历史尾部。
        """
        repaired: list[dict[str, Any]] = []
        removed = 0
        normalized = False
        i = 0

        while i < len(self.messages):
            msg = self.messages[i]
            role = msg.get("role")

            # 没有 assistant(tool_calls) 声明的 tool 结果不能单独发送。
            if role == "tool":
                removed += 1
                i += 1
                continue

            tool_calls = msg.get("tool_calls") if role == "assistant" else None
            if not tool_calls:
                repaired.append(msg)
                i += 1
                continue

            ids: list[str] = []
            valid_declaration = isinstance(tool_calls, list) and bool(tool_calls)
            if valid_declaration:
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        valid_declaration = False
                        break
                    tool_id = tc.get("id")
                    function = tc.get("function")
                    if (not isinstance(tool_id, str) or not tool_id or
                            not isinstance(function, dict) or
                            not isinstance(function.get("name"), str) or
                            not function.get("name") or
                            not isinstance(function.get("arguments"), str)):
                        valid_declaration = False
                        break
                    ids.append(tool_id)
                if len(ids) != len(set(ids)):
                    valid_declaration = False

            # 收集紧随其后的所有 tool 消息，事务边界遇到非 tool 即结束。
            j = i + 1
            tool_results: list[dict[str, Any]] = []
            while j < len(self.messages) and self.messages[j].get("role") == "tool":
                tool_results.append(self.messages[j])
                j += 1

            expected = set(ids)
            seen: set[str] = set()
            valid_results = valid_declaration and len(tool_results) == len(ids)
            if valid_results:
                for result in tool_results:
                    tool_id = result.get("tool_call_id")
                    if (not isinstance(tool_id, str) or tool_id not in expected or
                            tool_id in seen or "content" not in result):
                        valid_results = False
                        break
                    seen.add(tool_id)
                valid_results = seen == expected

            if valid_results:
                # 统一旧历史中的 null content，避免兼容层拒绝工具调用消息。
                if msg.get("content") is None:
                    msg = {**msg, "content": ""}
                    normalized = True
                repaired.append(msg)
                repaired.extend(tool_results)
            else:
                removed += 1 + len(tool_results)
                content = msg.get("content")
                # 若损坏声明同时带有可见正文，只移除 tool_calls 字段并保留正文。
                if isinstance(content, str) and content:
                    clean_msg = {k: v for k, v in msg.items() if k != "tool_calls"}
                    repaired.append(clean_msg)
                    removed -= 1

            i = j

        if removed or normalized:
            self.messages = repaired
        if removed:
            print(f"[历史修复] 已移除 {removed} 条非法工具链消息")
        return removed

    def save_history(self):
        """落盘历史消息（不含 system prompt）

        写入前自动闭合末尾未完成的 tool_calls 链——防止 Ctrl+C 中断后
        下次启动时 Provider 因断链而报 400 错误。
        """
        self._close_tool_chain()
        atomic_write_json(self.data_path, self.messages, indent=2)

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
        atomic_write_json(self.log_path, full_messages, indent=2)

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

    def _trim_if_needed(self, force: bool = False) -> int:
        """按普通历史超限机制压缩消息，返回被压缩的消息数。

        自动模式仅在消息数达到 ``max_history`` 时执行；手动模式由
        ``compress_history`` 调用，强制压缩当前历史的前半段。两种模式
        共用安全切点、摘要、auto_improve 和历史结构修复逻辑。
        """
        message_count = len(self.messages)
        if not force and message_count < self.max_history:
            return 0
        # 过短对话压缩收益很低，还可能丢失最近一轮的必要上下文。
        if message_count < 4:
            return 0

        self._compress_occurred = True
        keep = max(2, message_count // 2) if force else max(2, self.max_history // 2)
        cut = message_count - keep
        if cut <= 0:
            return 0

        # 向后扫描到安全切点：不在 tool_calls/tool 配对中间截断。
        safe = cut
        for i in range(cut, message_count):
            if self.messages[i].get("role", "") != "tool":
                safe = i
                break
        if safe <= 0:
            return 0

        trimmed = self.messages[:safe]
        self.messages = self.messages[safe:]

        digest = self._extract_digest(trimmed)
        if digest:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            lines = [
                f"[历史压缩] 以下是之前 {len(trimmed)} 条对话的摘要：",
                *digest,
                f"压缩时间: {ts}",
            ]
            self.messages.insert(0, {
                "role": "user",
                "content": "\n".join(lines),
            })

        # 保持与自动历史超限压缩完全相同的被动记忆提取行为。
        if self.provider and self.user_dir and trimmed:
            try:
                from agents.auto_improve.agent import run_auto_improve
                result = run_auto_improve(self.provider, trimmed, self.user_dir)
                if result.get("summary"):
                    print(f"[auto_improve] {result['summary']}")
            except Exception:
                pass  # 记忆提取失败不影响主压缩流程

        self._repair_tool_chain()
        return len(trimmed)

    def compress_history(self) -> int:
        """手动触发普通历史超限压缩，返回被压缩的消息数。"""
        return self._trim_if_needed(force=True)



    # ---- 用户命令 ----

    def clear_history(self) -> str:
        """清除当前对话历史，返回提示信息"""
        if not self.messages:
            return "没有可清除的历史记录。"
        count = len(self.messages)
        self.messages = []
        try:
            if os.path.exists(self.data_path):
                os.remove(self.data_path)
        except Exception:
            pass
        # 同时清空工具日志（新旧格式）
        tl_count = 0
        old_log_path = os.path.join(os.path.dirname(self.tool_log_path), "tool_log.json")
        for log_path in (self.tool_log_path, old_log_path):
            try:
                if os.path.exists(log_path):
                    with open(log_path, encoding="utf-8") as f:
                        tl_count += sum(1 for _ in f)
                    os.remove(log_path)
            except Exception:
                pass
        extra = f"，{tl_count} 条工具日志已清空" if tl_count else ""
        return f"已清除 {count} 条历史消息（归档备份已保存）{extra}。"

    def archive_now(self) -> str:
        """保存当前消息到归档文件，同时触发 auto_improve 记忆提取"""
        if not self.messages:
            return "没有可处理的对话。"
        count = len(self.messages)

        # 写入归档文件
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        archive_dir = os.path.join(self.user_dir, "history", "archive")
        os.makedirs(archive_dir, exist_ok=True)
        archive_name = f"history_{ts}_{count}.json"
        archive_path = os.path.join(archive_dir, archive_name)
        atomic_write_json(archive_path, self.build_messages(), indent=2)

        # 同时触发 auto_improve
        if self.provider and self.user_dir:
            try:
                from agents.auto_improve.agent import run_auto_improve
                result = run_auto_improve(self.provider, list(self.messages), self.user_dir)
                if result.get("summary"):
                    print(f"[auto_improve] {result['summary']}")
            except Exception:
                pass

        return f"已归档 {count} 条消息到 {archive_name}"

    def history_stats(self) -> str:
        """返回当前历史状态摘要"""
        msg_count = len(self.messages)
        # 估算大小
        try:
            size = os.path.getsize(self.data_path) if os.path.exists(self.data_path) else 0
        except OSError:
            size = 0
        # 工具日志条数（新旧格式合并统计）
        tool_log_count = 0
        old_log_path = os.path.join(os.path.dirname(self.tool_log_path), "tool_log.json")
        for log_path in (self.tool_log_path, old_log_path):
            try:
                if os.path.exists(log_path):
                    with open(log_path, encoding="utf-8") as f:
                        tool_log_count += sum(1 for _ in f)
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
        est_tokens = sum(self._msg_tokens(m) for m in self.messages)
        sys_tokens = self._estimate_tokens(self.system_prompt) if self.system_prompt else 0
        safe_budget = int(self.context_max * self.context_safe_ratio)
        lines = [
            f"当前会话消息: {msg_count} 条（上限 {self.max_history}）",
            f"预估 Token: {est_tokens + sys_tokens} (system {sys_tokens} + 历史 {est_tokens}) / 安全上限 {safe_budget}",
            f"历史文件大小: {_fmt_bytes(size)}",
            f"工具调用日志: {tool_log_count} 条",
            f"归档备份数: {archive_count} 个",
        ]
        return "\n".join(lines)


def _fmt_bytes(n: int) -> str:
    """执行 fmt_bytes 内部辅助逻辑。"""
    if n < 1024:
        return f"{n} B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    else:
        return f"{n / 1024 / 1024:.1f} MB"
