"""Provider 工厂 — 根据用户配置创建对应的 LLM Provider 实例

两种接口协议:
  type: "openai"    → OpenAI 接口协议（优先 Responses API，自动回退 Chat Completions）
  type: "anthropic" → Anthropic Messages API

所有 OpenAI 兼容厂商通过同一个 Provider + 自定义 base_url 接入。
"""

import os

from provider.base import BaseProvider


def create_provider(user_config: dict, core_config: dict | None = None) -> BaseProvider:
    """读取 user_config["provider"]["type"] 返回对应 provider 实例。

    type 可选值:
      "openai"    — OpenAI 接口协议（默认）
      "anthropic" — Anthropic Messages 协议

    OpenAI 协议下可通过 api_style 指定:
      "responses" — 强制 Responses API（仅 OpenAI 官方支持）
      "chat"      — 强制 Chat Completions API
      未设置      — 自动探测：OpenAI 官方端点 → Responses，其他 → Chat

    也支持 VOTX_PROVIDER 环境变量覆盖。
    """
    cfg = user_config.get("provider", {})
    provider_type = os.environ.get("VOTX_PROVIDER", "") or cfg.get("type", "openai")
    provider_type = provider_type.lower()

    # 兼容旧值
    if provider_type in ("openai", "deepseek", "openai_compatible", "azure_openai", "google_gemini", ""):
        from provider.responses_api import ResponsesProvider
        return ResponsesProvider(user_config, core_config)
    elif provider_type == "anthropic":
        from provider.anthropic_adapter import AnthropicProvider
        return AnthropicProvider(user_config, core_config)
    else:
        raise ValueError(f"未知 provider type: {provider_type}。可选: openai, anthropic")
