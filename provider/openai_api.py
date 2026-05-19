"""LLM Provider - OpenAI 兼容接口封装 (Chat Completions API)

支持 OpenAI 兼容 API (DeepSeek 等)，提供:
- 自动重试 (超时/连接错误，最多 2 次)
- 流式和非流式两种调用路径
- 多来源 API Key 加载 (用户配置 > DEEPSEEK_API_KEY > OPENAI_API_KEY)
- Token 用量统计 (含缓存命中)
- 思考模式 (reasoning_effort) 控制

实现 BaseProvider 接口，返回统一 ProviderResponse。
"""
import json
import os
import time as _time
from pathlib import Path
from typing import Any, Generator

# 修复 Windows SSL_CERT_FILE 指向不存在文件导致的 httpx 崩溃
# 某些 Python 发行版设置了无效的 SSL_CERT_FILE 环境变量，httpx 检测到后会崩溃
if "SSL_CERT_FILE" in os.environ and not os.path.isfile(os.environ["SSL_CERT_FILE"]):
    del os.environ["SSL_CERT_FILE"]

from openai import OpenAI, APIError, APITimeoutError, APIConnectionError
from openai.types.chat import ChatCompletionMessage

from provider.base import BaseProvider
from provider.schema import ProviderResponse, ToolCall

# 加载 .env（不依赖 python-dotenv）
def _load_dotenv():
    """手动解析 .env 文件，写入 os.environ (不依赖 python-dotenv)"""
    try:
        from paths import get_project_root
        root = Path(get_project_root())
    except Exception:
        root = Path(__file__).resolve().parent.parent
    for candidate in [
        root / ".env",
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


class DeepSeekProvider(BaseProvider):
    """LLM Provider - 支持 OpenAI 兼容接口 (Chat Completions API)"""

    def __init__(self, user_config: dict, core_config: dict | None = None):
        """执行 init 内部辅助逻辑。"""
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
        self.last_response: ProviderResponse | None = None

    # ── BaseProvider 接口 ──

    def respond(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> ProviderResponse:
        """发送消息，支持超时 + 重试。返回统一 ProviderResponse。

        重试策略:
        - APITimeoutError / APIConnectionError: 指数退避重试 (1s, 2s)
        - APIError (4xx/5xx): 直接抛出，不重试 (避免重复扣费)
        """
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
        else:
            self.last_usage = _extract_usage(response)
            msg = response.choices[0].message
            reasoning = ""
            try:
                reasoning = getattr(msg, "reasoning_content", "") or ""
            except Exception:
                pass
            if not reasoning and hasattr(msg, "model_extra"):
                reasoning = msg.model_extra.get("reasoning_content", "") or ""
            if reasoning and not getattr(msg, "reasoning_content", None):
                msg.reasoning_content = reasoning  # type: ignore[attr-defined]

        result = _to_provider_response(msg)
        self.last_response = result
        return result

    def respond_stream(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> Generator[dict, None, None]:
        """流式 LLM 调用 — 逐 chunk yield，完成后 self.last_response 可用。

        用法:
            for event in provider.respond_stream(messages, tools):
                if event["type"] == "thinking_chunk":  ...
                if event["type"] == "text_chunk":       ...
            response = provider.last_response  # ProviderResponse
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
        reasoning_parts: list[str] = []
        tool_calls_map: dict[int, dict] = {}
        usage = None

        for chunk in response:
            if hasattr(chunk, "usage") and chunk.usage:
                usage = _extract_usage(chunk)
                self.last_usage = usage
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                reasoning_parts.append(delta.reasoning_content)
                yield {"type": "thinking_chunk", "content": delta.reasoning_content}
            if delta.content:
                content_parts.append(delta.content)
                yield {"type": "text_chunk", "content": delta.content}
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
        reasoning = "".join(reasoning_parts) if reasoning_parts else ""
        msg = ChatCompletionMessage(
            role="assistant", content=content or None, tool_calls=tool_calls
        )
        if reasoning:
            msg.reasoning_content = reasoning  # type: ignore[attr-defined]

        result = _to_provider_response(msg)
        self.last_response = result
        return result

    def _collect_stream(self, response) -> tuple[ChatCompletionMessage, dict | None]:
        """收集流式 chunk 拼接为完整 Message，同时提取 usage 和 reasoning"""
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls_map: dict[int, dict] = {}
        usage = None
        for chunk in response:
            if hasattr(chunk, "usage") and chunk.usage:
                usage = _extract_usage(chunk)
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                reasoning_parts.append(delta.reasoning_content)
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
        reasoning = "".join(reasoning_parts) if reasoning_parts else ""
        msg = ChatCompletionMessage(
            role="assistant", content=content or None, tool_calls=tool_calls
        )
        if reasoning:
            msg.reasoning_content = reasoning  # type: ignore[attr-defined]
        return msg, usage


def _to_provider_response(msg: ChatCompletionMessage) -> ProviderResponse:
    """将 ChatCompletionMessage 转为统一 ProviderResponse"""
    tool_calls = []
    if msg.tool_calls:
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, AttributeError):
                args = {}
            tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, input=args))
    reasoning = ""
    try:
        reasoning = getattr(msg, "reasoning_content", "") or ""
    except Exception:
        pass
    if not reasoning and hasattr(msg, "model_extra"):
        reasoning = (msg.model_extra or {}).get("reasoning_content", "") or ""
    finish_reason = ""
    return ProviderResponse(
        text=msg.content or "",
        reasoning=reasoning,
        tool_calls=tool_calls,
        finish_reason=finish_reason,
    )


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
