"""Provider 工厂 — 根据用户配置创建 Kemo LLM Adapter Provider 实例

唯一接口协议:
  type: "kemo"      → Kemo LLM Adapter 本地网关

所有多模态能力通过 llm-adapter-kemo 统一路由。
"""

import os

from provider.base import BaseProvider


def create_provider(user_config: dict, core_config: dict | None = None) -> BaseProvider:
    """读取 user_config["provider"]["type"] 返回对应 provider 实例。

    唯一支持的类型: "kemo" — Kemo LLM Adapter 本地网关

    也支持 VOTX_PROVIDER 环境变量覆盖（仅 "kemo"）。
    """
    cfg = user_config.get("provider", {})
    provider_type = os.environ.get("VOTX_PROVIDER", "") or cfg.get("type", "kemo")
    provider_type = provider_type.lower()

    if provider_type != "kemo":
        raise ValueError(
            f"不支持的 provider type: {provider_type}。"
            f"votx-agent 仅支持 type: \"kemo\"（Kemo LLM Adapter 本地网关）。"
        )

    from provider.kemo_adapter import KemoProvider
    return KemoProvider(user_config, core_config)
