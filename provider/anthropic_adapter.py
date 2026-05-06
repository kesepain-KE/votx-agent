"""Anthropic Messages API adepter

将 Anthropic Messages API 格式转换为统一内部格式 (ProviderResponse)。

与 Chat Completions API 的主要差异:
- 消息格式: content[] 数组，每项有 type (text/tool_use/tool_result/thinking)
- 工具定义: 顶层的 name/description/input_schema 结构
- system prompt: 作为顶层参数传入，不在 messages 中
- streaming: content_block_start/delta/stop 事件，非 delta 流
- thinking: 原生 extended thinking 功能

依赖: pip install anthropic
"""

import json
import os
import time as _time
import uuid
from typing import Any, Generator

from provider.base import BaseProvider
from provider.schema import ProviderResponse, ToolCall

MAX_RETRIES = 2
RETRY_DELAY = 1.0


class AnthropicProvider(BaseProvider):
    """Anthropic Claude Provider — Messages API"""

    def __init__(self, user_config: dict, core_config: dict | None = None):
        core = core_config or {}
        cfg = user_config.get("provider", {})

        api_key = (
            cfg.get("api_key", "").strip()
            or os.environ.get("ANTHROPIC_API_KEY", "")
        )
        if not api_key:
            raise ValueError(
                "Anthropic API Key 未设置。请通过以下方式之一提供:\n"
                "  1. 在 users/<name>/config.json 的 provider.api_key 中填写\n"
                "  2. 设置环境变量: export ANTHROPIC_API_KEY=sk-ant-xxx"
            )

        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError(
                "Anthropic adapter 需要 anthropic 包。请运行: pip install anthropic"
            )

        self.client = Anthropic(api_key=api_key)
        self.model = cfg.get("model", "claude-sonnet-4-20250514")
        self.max_tokens = cfg.get("max_tokens", 8192)
        self.stream = cfg.get("stream", core.get("output", {}).get("stream", True))
        self.timeout = cfg.get("timeout", 120)
        self.last_usage: dict | None = None
        self.last_response: ProviderResponse | None = None

        # extended thinking 配置
        thinking_cfg = cfg.get("thinking", None)
        if thinking_cfg is None:
            thinking_cfg = {"type": "enabled", "budget_tokens": 4000}
        self.thinking = thinking_cfg

    # ── BaseProvider 接口 ──

    def respond(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> ProviderResponse:
        """非流式调用，返回统一 ProviderResponse"""
        system_prompt, anthropic_messages = _to_anthropic_messages(messages)
        anthropic_tools = _to_anthropic_tools(tools) if tools else None

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": anthropic_messages,
            "timeout": self.timeout,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools
        if self.thinking:
            kwargs["thinking"] = self.thinking

        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self.client.messages.create(**kwargs)
                break
            except Exception as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    _time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise RuntimeError(f"Anthropic API 调用失败（已重试 {MAX_RETRIES} 次）: {e}") from e

        self.last_usage = _extract_anthropic_usage(response)
        result = _from_anthropic_response(response)
        self.last_response = result
        return result

    def respond_stream(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> Generator[dict, None, None]:
        """流式调用，yield engine-compatible 事件 dict"""
        system_prompt, anthropic_messages = _to_anthropic_messages(messages)
        anthropic_tools = _to_anthropic_tools(tools) if tools else None

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": anthropic_messages,
            "timeout": self.timeout,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools
        if self.thinking:
            kwargs["thinking"] = self.thinking

        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                with self.client.messages.stream(**kwargs) as stream:
                    text_parts: list[str] = []
                    thinking_parts: list[str] = []
                    tool_calls_acc: dict[int, dict] = {}

                    for event in stream:
                        if event.type == "content_block_start":
                            block = event.content_block
                            if block.type == "thinking":
                                thinking_text = getattr(block, "thinking", "")
                                if thinking_text:
                                    thinking_parts.append(thinking_text)
                                    yield {"type": "thinking_chunk", "content": thinking_text}
                            elif block.type == "tool_use":
                                idx = len(tool_calls_acc)
                                tool_calls_acc[idx] = {
                                    "id": block.id,
                                    "name": block.name,
                                    "input": "",
                                }

                        elif event.type == "content_block_delta":
                            delta = event.delta
                            if delta.type == "thinking_delta":
                                thinking_text = getattr(delta, "thinking", "")
                                if thinking_text:
                                    thinking_parts.append(thinking_text)
                                    yield {"type": "thinking_chunk", "content": thinking_text}
                            elif delta.type == "text_delta":
                                text = getattr(delta, "text", "")
                                if text:
                                    text_parts.append(text)
                                    yield {"type": "text_chunk", "content": text}
                            elif delta.type == "input_json_delta":
                                partial = getattr(delta, "partial_json", "")
                                idx = event.index
                                if idx in tool_calls_acc:
                                    tool_calls_acc[idx]["input"] += partial

                        elif event.type == "message_delta":
                            usage = getattr(event, "usage", None)
                            if usage:
                                self.last_usage = {
                                    "prompt_tokens": getattr(usage, "input_tokens", 0) or 0,
                                    "completion_tokens": getattr(usage, "output_tokens", 0) or 0,
                                    "total_tokens": (
                                        (getattr(usage, "input_tokens", 0) or 0)
                                        + (getattr(usage, "output_tokens", 0) or 0)
                                    ),
                                    "cached_tokens": getattr(
                                        usage, "cache_read_input_tokens", 0
                                    ) or 0,
                                }

                    # 构建最终响应
                    final_text = "".join(text_parts)
                    final_thinking = "".join(thinking_parts)

                    final_tool_calls = []
                    for idx in sorted(tool_calls_acc):
                        tc = tool_calls_acc[idx]
                        try:
                            args = json.loads(tc["input"]) if tc["input"] else {}
                        except json.JSONDecodeError:
                            args = {}
                        final_tool_calls.append(
                            ToolCall(id=tc["id"], name=tc["name"], input=args)
                        )

                    self.last_response = ProviderResponse(
                        text=final_text,
                        reasoning=final_thinking,
                        tool_calls=final_tool_calls,
                    )
                break
            except Exception as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    _time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise RuntimeError(f"Anthropic API 调用失败（已重试 {MAX_RETRIES} 次）: {e}") from e

        return


# ── 格式转换 ──

def _to_anthropic_messages(messages: list[dict]) -> tuple[str, list[dict]]:
    """将内部 dict 格式转换为 Anthropic Messages 格式。

    Returns:
        (system_prompt, anthropic_messages)
        其中 system_prompt 是字符串，anthropic_messages 不含 system 角色。
    """
    system_prompt = ""
    result: list[dict] = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "system":
            system_prompt += content + "\n"
            continue

        if role == "user":
            result.append({"role": "user", "content": content or ""})
            continue

        if role == "assistant":
            parts: list[dict] = []
            if content:
                parts.append({"type": "text", "text": content})
            if msg.get("reasoning_content"):
                parts.append({"type": "thinking", "thinking": msg["reasoning_content"]})
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    try:
                        inp = json.loads(tc["function"]["arguments"])
                    except (json.JSONDecodeError, KeyError, TypeError):
                        inp = {}
                    parts.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": inp,
                    })
            result.append({"role": "assistant", "content": parts})
            continue

        if role == "tool":
            result.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id", ""),
                    "content": str(content),
                }],
            })
            continue

    system_prompt = system_prompt.strip()
    return system_prompt, result


def _to_anthropic_tools(tools: list[dict]) -> list[dict]:
    """OpenAI tool schema → Anthropic tool schema"""
    result = []
    for t in tools:
        func = t.get("function", {})
        item: dict[str, Any] = {
            "name": func.get("name", ""),
            "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
        }
        if "description" in func:
            item["description"] = func["description"]
        result.append(item)
    return result


def _from_anthropic_response(response) -> ProviderResponse:
    """Anthropic Messages 响应 → ProviderResponse"""
    text = ""
    reasoning = ""
    tool_calls: list[ToolCall] = []

    for block in response.content:
        if block.type == "text":
            text += block.text
        elif block.type == "thinking":
            reasoning += getattr(block, "thinking", "")
        elif block.type == "tool_use":
            tool_calls.append(ToolCall(
                id=block.id,
                name=block.name,
                input=dict(block.input) if block.input else {},
            ))

    return ProviderResponse(
        text=text,
        reasoning=reasoning,
        tool_calls=tool_calls,
    )


def _extract_anthropic_usage(response) -> dict | None:
    """从 Anthropic 响应提取 token 用量"""
    try:
        u = response.usage
        return {
            "prompt_tokens": u.input_tokens or 0,
            "completion_tokens": u.output_tokens or 0,
            "total_tokens": (u.input_tokens + u.output_tokens) or 0,
            "cached_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
        }
    except Exception:
        return None
