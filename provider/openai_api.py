"""LLM Provider - OpenAI 兼容接口封装"""
import os
import time as _time
from pathlib import Path
from typing import Any

# 修复 Windows SSL_CERT_FILE 指向不存在文件导致的 httpx 崩溃
if "SSL_CERT_FILE" in os.environ and not os.path.isfile(os.environ["SSL_CERT_FILE"]):
    del os.environ["SSL_CERT_FILE"]

from openai import OpenAI, APIError, APITimeoutError, APIConnectionError
from openai.types.chat import ChatCompletionMessage

# 加载 .env（不依赖 python-dotenv）
def _load_dotenv():
    """手动解析 .env 文件，写入 os.environ"""
    for candidate in [
        Path(__file__).resolve().parent.parent / ".env",  # 项目根
        Path.cwd() / ".env",
    ]:
        try:
            if candidate.is_file():
                for line in candidate.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

_load_dotenv()

MAX_RETRIES = 2
RETRY_DELAY = 1.0


class DeepSeekProvider:
    """LLM Provider - 支持 OpenAI 兼容接口"""

    def __init__(self, user_config: dict, core_config: dict | None = None):
        core = core_config or {}
        cfg = user_config.get("provider", {})
        # API Key: config > DEEPSEEK_API_KEY > OPENAI_API_KEY
        api_key = (
            cfg.get("api_key", "").strip()
            or os.environ.get("DEEPSEEK_API_KEY", "")
            or os.environ.get("OPENAI_API_KEY", "")
        )
        if not api_key:
            raise ValueError(
                "API Key 未设置。请通过以下方式之一提供:\n"
                "  1. 创建 .env 文件，写入 DEEPSEEK_API_KEY=sk-xxx\n"
                "  2. 设置环境变量: export DEEPSEEK_API_KEY=sk-xxx\n"
                "  3. 在 users/<name>/config.json 的 provider.api_key 中填写"
            )
        # base_url: config > DEEPSEEK_BASE_URL 环境变量 > DeepSeek 默认
        base_url = (
            cfg.get("base_url", "").strip()
            or os.environ.get("DEEPSEEK_BASE_URL", "")
            or "https://api.deepseek.com"
        )
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = cfg.get("model", "deepseek-v4-flash")
        self.think = cfg.get("think", False)
        # stream: 用户配置 > 全局配置 > False
        self.stream = cfg.get("stream", core.get("output", {}).get("stream", False))
        self.timeout = cfg.get("timeout", 120)
        self.last_usage: dict | None = None

    def chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> ChatCompletionMessage:
        """发送消息，支持超时 + 重试"""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": self.stream,
            "timeout": self.timeout,
        }
        if self.think:
            kwargs["reasoning_effort"] = "high"
        else:
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        if tools:
            kwargs["tools"] = tools

        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(**kwargs)
                break
            except (APITimeoutError, APIConnectionError) as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    _time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise RuntimeError(f"API 调用失败（已重试 {MAX_RETRIES} 次）: {e}") from e
            except APIError as e:
                raise RuntimeError(f"API 错误: {e}") from e

        if self.stream:
            msg, usage = self._collect_stream(response)
            self.last_usage = usage
            return msg
        else:
            self.last_usage = _extract_usage(response)
            return response.choices[0].message

    def chat_stream(self, messages, tools=None):
        """流式 LLM 调用 — yield 文本增量，完成后 self.last_usage + self._stream_result 可用

        用法:
            for delta_text in provider.chat_stream(messages, tools):
                ...  # delta_text 是 str，可能为空字符串
            # 流结束后:
            msg = provider._stream_result  # ChatCompletionMessage（含 tool_calls）
            usage = provider.last_usage
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "timeout": self.timeout,
        }
        if self.think:
            kwargs["reasoning_effort"] = "high"
        else:
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        if tools:
            kwargs["tools"] = tools

        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(**kwargs)
                break
            except (APITimeoutError, APIConnectionError) as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    _time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise RuntimeError(f"API 调用失败（已重试 {MAX_RETRIES} 次）: {e}") from e
            except APIError as e:
                raise RuntimeError(f"API 错误: {e}") from e

        content_parts: list[str] = []
        tool_calls_map: dict[int, dict] = {}
        usage = None

        for chunk in response:
            if hasattr(chunk, "usage") and chunk.usage:
                usage = _extract_usage(chunk)
                self.last_usage = usage
            delta = chunk.choices[0].delta
            if delta.content:
                content_parts.append(delta.content)
                yield delta.content
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_map:
                        tool_calls_map[idx] = {
                            "id": tc.id or "",
                            "function": {"name": "", "arguments": ""},
                        }
                    if tc.id:
                        tool_calls_map[idx]["id"] = tc.id
                    if tc.function and tc.function.name:
                        tool_calls_map[idx]["function"]["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_calls_map[idx]["function"]["arguments"] += tc.function.arguments

        if usage:
            self.last_usage = usage

        content = "".join(content_parts)
        tool_calls = None
        if tool_calls_map:
            from openai.types.chat.chat_completion_message_tool_call import (
                ChatCompletionMessageToolCall,
            )
            tool_calls = []
            for idx in sorted(tool_calls_map):
                tc = tool_calls_map[idx]
                tool_calls.append(ChatCompletionMessageToolCall(
                    id=tc["id"],
                    type="function",
                    function={
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                ))
        self._stream_result = ChatCompletionMessage(
            role="assistant", content=content or None, tool_calls=tool_calls
        )

    def _collect_stream(self, response) -> tuple[ChatCompletionMessage, dict | None]:
        """收集流式 chunk 拼接为完整 Message，同时提取 usage"""
        content_parts: list[str] = []
        tool_calls_map: dict[int, dict] = {}
        usage = None
        for chunk in response:
            if hasattr(chunk, "usage") and chunk.usage:
                usage = _extract_usage(chunk)
            delta = chunk.choices[0].delta
            if delta.content:
                content_parts.append(delta.content)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_map:
                        tool_calls_map[idx] = {
                            "id": tc.id or "",
                            "function": {"name": "", "arguments": ""},
                        }
                    if tc.id:
                        tool_calls_map[idx]["id"] = tc.id
                    if tc.function and tc.function.name:
                        tool_calls_map[idx]["function"]["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_calls_map[idx]["function"]["arguments"] += tc.function.arguments

        content = "".join(content_parts)
        tool_calls = None
        if tool_calls_map:
            from openai.types.chat.chat_completion_message_tool_call import (
                ChatCompletionMessageToolCall,
            )
            tool_calls = []
            for idx in sorted(tool_calls_map):
                tc = tool_calls_map[idx]
                tool_calls.append(ChatCompletionMessageToolCall(
                    id=tc["id"],
                    type="function",
                    function={
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                ))
        return ChatCompletionMessage(
            role="assistant", content=content or None, tool_calls=tool_calls
        ), usage


def _extract_usage(response) -> dict | None:
    """从 API 响应提取 token 用量，含缓存命中信息"""
    try:
        u = response.usage
        if u is None:
            return None
        info = {
            "prompt_tokens": u.prompt_tokens or 0,
            "completion_tokens": u.completion_tokens or 0,
            "total_tokens": u.total_tokens or 0,
        }
        # prompt 缓存命中量（DeepSeek 的 prompt_tokens_details.cached_tokens）
        cached = 0
        if hasattr(u, "prompt_tokens_details") and u.prompt_tokens_details:
            cached = getattr(u.prompt_tokens_details, "cached_tokens", 0) or 0
        info["cached_tokens"] = cached
        return info
    except Exception:
        return None
