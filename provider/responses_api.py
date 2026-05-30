"""OpenAI Responses API Provider — 优先使用新 Responses API，自动回退 Completions API

Responses API 是 OpenAI 2025 年推出的统一 API:
- POST /v1/responses
- input 传对话内容，tools 用扁平格式
- 流式事件类型: response.output_text.delta / response.function_call_arguments.delta
- 与 Chat Completions API 的主要差异: input 格式、tool schema、output 结构

当接口不支持时自动回退到 Chat Completions API。
"""

import json
import os
import time as _time
from pathlib import Path
from typing import Any, Generator

# 修复 Windows SSL_CERT_FILE
if "SSL_CERT_FILE" in os.environ and not os.path.isfile(os.environ["SSL_CERT_FILE"]):
    del os.environ["SSL_CERT_FILE"]

from openai import OpenAI, APIError, APITimeoutError, APIConnectionError

from provider.base import BaseProvider
from provider.schema import ProviderResponse, ToolCall

# 加载 .env
def _load_dotenv():
    """执行 load_dotenv 内部辅助逻辑。"""
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


class ResponsesProvider(BaseProvider):
    """OpenAI Responses API Provider — 自动回退到 Chat Completions"""

    def __init__(self, user_config: dict, core_config: dict | None = None):
        """执行 init 内部辅助逻辑。"""
        core = core_config or {}
        cfg = user_config.get("provider", {})

        api_key = (
            cfg.get("api_key", "").strip()
            or os.environ.get("DEEPSEEK_API_KEY", "")
            or os.environ.get("OPENAI_API_KEY", "")
        )
        if not api_key:
            raise ValueError("API Key 未设置")

        base_url = (
            cfg.get("base_url", "").strip()
            or os.environ.get("DEEPSEEK_BASE_URL", "")
            or "https://api.deepseek.com"
        )

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = cfg.get("model", "deepseek-v4-flash")
        self.think = cfg.get("think", False)
        self.stream = cfg.get("stream", core.get("output", {}).get("stream", True))
        self.timeout = cfg.get("timeout", 120)
        self.last_usage: dict | None = None
        self.last_response: ProviderResponse | None = None

        # api 风格：仅两种选一，默认 chat
        api_style = cfg.get("api_style", "")
        if api_style == "responses":
            self._use_responses = True
        else:
            self._use_responses = False
        self._user_config = user_config
        self._responses_available = None  # None=未探测, True/False

    # ── BaseProvider 接口 ──

    def respond(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> ProviderResponse:
        """处理 respond 相关逻辑。"""
        if self._use_responses and self._responses_available is not False:
            try:
                return self._respond_via_responses(messages, tools)
            except _ResponsesNotSupported:
                self._responses_available = False
                # 回退到 Chat Completions
        return self._respond_via_chat(messages, tools)

    def respond_stream(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> Generator[dict, None, None]:
        """处理 respond_stream 相关逻辑。"""
        if self._use_responses and self._responses_available is not False:
            try:
                yield from self._respond_stream_via_responses(messages, tools)
                return
            except _ResponsesNotSupported:
                self._responses_available = False
        yield from self._respond_stream_via_chat(messages, tools)

    # ── Responses API 路径 ──

    def _respond_via_responses(
        self, messages: list[dict], tools: list[dict] | None
    ) -> ProviderResponse:
        """执行 respond_via_responses 内部辅助逻辑。"""
        instructions, inp = _to_responses_input(messages)
        resp_tools = _to_responses_tools(tools) if tools else None

        kwargs: dict[str, Any] = {
            "model": self.model,
            "input": inp,
            "stream": False,
            "timeout": self.timeout,
        }
        if instructions:
            kwargs["instructions"] = instructions
        if resp_tools:
            kwargs["tools"] = resp_tools
        if self.think:
            kwargs["reasoning"] = {"effort": "high"}

        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self.client.responses.create(**kwargs)
                break
            except APIError as e:
                if _is_not_supported(e):
                    raise _ResponsesNotSupported from e
                raise RuntimeError(f"Responses API 错误: {e}") from e
            except (APITimeoutError, APIConnectionError) as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    _time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise RuntimeError(f"API 调用失败（已重试 {MAX_RETRIES} 次）: {e}") from e

        self.last_usage = _extract_responses_usage(resp)
        result = _from_responses_output(resp)
        self.last_response = result
        return result

    def _respond_stream_via_responses(
        self, messages: list[dict], tools: list[dict] | None
    ) -> Generator[dict, None, None]:
        """执行 respond_stream_via_responses 内部辅助逻辑。"""
        instructions, inp = _to_responses_input(messages)
        resp_tools = _to_responses_tools(tools) if tools else None

        kwargs: dict[str, Any] = {
            "model": self.model,
            "input": inp,
            "stream": True,
            "timeout": self.timeout,
        }
        if instructions:
            kwargs["instructions"] = instructions
        if resp_tools:
            kwargs["tools"] = resp_tools
        if self.think:
            kwargs["reasoning"] = {"effort": "high"}

        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                stream = self.client.responses.create(**kwargs)
                break
            except APIError as e:
                if _is_not_supported(e):
                    raise _ResponsesNotSupported from e
                raise RuntimeError(f"Responses API 错误: {e}") from e
            except (APITimeoutError, APIConnectionError) as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    _time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise RuntimeError(f"API 调用失败（已重试 {MAX_RETRIES} 次）: {e}") from e

        text_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_calls_acc: dict[str, dict] = {}  # call_id → {name, arguments}
        usage = None

        for event in stream:
            etype = getattr(event, "type", "")

            if etype == "response.output_text.delta":
                delta = getattr(event, "delta", "") or ""
                if delta:
                    text_parts.append(delta)
                    yield {"type": "text_chunk", "content": delta}

            elif etype == "response.reasoning_text.delta":
                delta = getattr(event, "delta", "") or ""
                if delta:
                    thinking_parts.append(delta)
                    yield {"type": "thinking_chunk", "content": delta}

            elif etype == "response.function_call_arguments.delta":
                delta = getattr(event, "delta", "") or ""
                call_id = getattr(event, "call_id", "")
                if call_id not in tool_calls_acc:
                    tool_calls_acc[call_id] = {"name": getattr(event, "name", ""), "arguments": ""}
                tool_calls_acc[call_id]["arguments"] += delta

            elif etype == "response.completed":
                resp = getattr(event, "response", None)
                if resp and hasattr(resp, "usage"):
                    self.last_usage = _extract_responses_usage(resp)

        self.last_response = ProviderResponse(
            text="".join(text_parts),
            reasoning="".join(thinking_parts),
            tool_calls=[
                ToolCall(id=cid, name=info["name"], input=_safe_json_parse(info["arguments"]))
                for cid, info in tool_calls_acc.items()
            ],
        )

    # ── Chat Completions 回退路径 ──

    def _respond_via_chat(
        self, messages: list[dict], tools: list[dict] | None
    ) -> ProviderResponse:
        """执行 respond_via_chat 内部辅助逻辑。"""
        from provider.openai_api import DeepSeekProvider
        # 传递用户的真实 provider 配置，避免丢失 api_key/base_url
        p = DeepSeekProvider(self._user_config, {})
        p.client = self.client
        p.model = self.model
        p.think = self.think
        p.stream = False
        p.timeout = self.timeout
        p.last_usage = None
        p.last_response = None
        return p.respond(messages, tools)

    def _respond_stream_via_chat(
        self, messages: list[dict], tools: list[dict] | None
    ) -> Generator[dict, None, None]:
        """执行 respond_stream_via_chat 内部辅助逻辑。"""
        from provider.openai_api import DeepSeekProvider
        # 传递用户的真实 provider 配置，避免丢失 api_key/base_url
        p = DeepSeekProvider(self._user_config, {})
        p.client = self.client
        p.model = self.model
        p.think = self.think
        p.stream = True
        p.timeout = self.timeout
        p.last_usage = None
        p.last_response = None

        # 调用 stream 方法
        kwargs = {
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

        response = p.client.chat.completions.create(**kwargs)
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls_map: dict[int, dict] = {}
        usage = None

        from provider.openai_api import _extract_usage
        for chunk in response:
            if hasattr(chunk, "usage") and chunk.usage:
                usage = _extract_usage(chunk)
                p.last_usage = usage
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
                        tool_calls_map[idx] = {"id": tc.id or "", "function": {"name": "", "arguments": ""}}
                    if tc.id:
                        tool_calls_map[idx]["id"] = tc.id
                    if tc.function and tc.function.name:
                        tool_calls_map[idx]["function"]["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_calls_map[idx]["function"]["arguments"] += tc.function.arguments

        if usage:
            p.last_usage = usage

        from openai.types.chat import ChatCompletionMessage
        from provider.openai_api import _to_provider_response
        content = "".join(content_parts)
        tool_calls = None
        if tool_calls_map:
            from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall
            tool_calls = []
            for idx in sorted(tool_calls_map):
                tc = tool_calls_map[idx]
                tool_calls.append(ChatCompletionMessageToolCall(
                    id=tc["id"], type="function",
                    function={"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]},
                ))
        reasoning = "".join(reasoning_parts) if reasoning_parts else ""
        msg = ChatCompletionMessage(role="assistant", content=content or None, tool_calls=tool_calls)
        if reasoning:
            msg.reasoning_content = reasoning

        result = _to_provider_response(msg)
        p.last_response = result
        self.last_response = result
        self.last_usage = p.last_usage


# ── 格式转换 ──

def _to_responses_user_content(content: Any):
    """Convert internal user content, including OpenAI multimodal blocks."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")

    parts: list[dict] = []
    for part in content:
        if not isinstance(part, dict):
            parts.append({"type": "input_text", "text": str(part)})
            continue

        ptype = part.get("type")
        if ptype == "text":
            parts.append({"type": "input_text", "text": str(part.get("text", ""))})
        elif ptype == "image_url":
            image_url = part.get("image_url", {})
            url = image_url.get("url", "") if isinstance(image_url, dict) else str(image_url or "")
            parts.append({"type": "input_image", "image_url": url})
        elif ptype in ("input_text", "input_image"):
            parts.append(part)
        else:
            parts.append({"type": "input_text", "text": json.dumps(part, ensure_ascii=False)})
    return parts


def _to_responses_input(messages: list[dict]) -> tuple[str, list[dict]]:
    """内部 dict 格式 → Responses API input + instructions"""
    instructions = ""
    items: list[dict] = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system":
            instructions += content + "\n"
            continue
        if role == "user":
            items.append({"role": "user", "content": _to_responses_user_content(content)})
        elif role == "assistant":
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    args = tc.get("function", {}).get("arguments", "{}")
                    items.append({
                        "type": "function_call",
                        "call_id": tc["id"],
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": args,
                    })
            elif content:
                items.append({"role": "assistant", "content": content})
        elif role == "tool":
            items.append({
                "type": "function_call_output",
                "call_id": msg.get("tool_call_id", ""),
                "output": str(content),
            })
    return instructions.strip(), items


def _to_responses_tools(tools: list[dict]) -> list[dict]:
    """Chat Completions tool schema → Responses API tool schema (扁平格式)"""
    result = []
    for t in tools:
        func = t.get("function", {})
        item = {
            "type": "function",
            "name": func.get("name", ""),
            "parameters": func.get("parameters", {"type": "object", "properties": {}}),
        }
        if "description" in func:
            item["description"] = func["description"]
        result.append(item)
    return result


def _from_responses_output(response) -> ProviderResponse:
    """Responses API 响应 → ProviderResponse"""
    text = ""
    reasoning = ""
    tool_calls: list[ToolCall] = []

    for item in getattr(response, "output", []):
        itype = getattr(item, "type", "")
        if itype == "message":
            for c in getattr(item, "content", []):
                if getattr(c, "type", "") == "output_text":
                    text += getattr(c, "text", "") or ""
        elif itype == "reasoning":
            for c in getattr(item, "content", []):
                if getattr(c, "type", "") == "reasoning_text":
                    reasoning += getattr(c, "text", "") or ""
        elif itype == "function_call":
            tool_calls.append(ToolCall(
                id=getattr(item, "call_id", ""),
                name=getattr(item, "name", ""),
                input=_safe_json_parse(getattr(item, "arguments", "{}")),
            ))

    return ProviderResponse(
        text=text,
        reasoning=reasoning,
        tool_calls=tool_calls,
    )


def _extract_responses_usage(response) -> dict | None:
    """从 Responses API 响应提取 token 用量"""
    try:
        u = response.usage
        if not u:
            return None
        return {
            "prompt_tokens": u.input_tokens or 0,
            "completion_tokens": u.output_tokens or 0,
            "total_tokens": u.total_tokens or 0,
            "cached_tokens": getattr(u, "input_tokens_details", {}).get("cached_tokens", 0) or 0,
        }
    except Exception:
        return None


# ── 辅助 ──

class _ResponsesNotSupported(Exception):
    """端点不支持 Responses API 时抛出"""
    pass


def _is_not_supported(error: APIError) -> bool:
    """判断是否是不支持 Responses API 的错误 (404/405)"""
    status = getattr(error, "status_code", 0) or getattr(error, "status", 0)
    if status in (404, 405):
        return True
    msg = str(error).lower()
    return any(kw in msg for kw in ["not found", "not supported", "unknown endpoint", "unrecognized"])


def _safe_json_parse(s: str) -> dict:
    """执行 safe_json_parse 内部辅助逻辑。"""
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return {}
