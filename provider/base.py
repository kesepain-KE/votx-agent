"""抽象 Provider 接口 — 所有 LLM Provider 必须实现"""

from abc import ABC, abstractmethod
from typing import Generator

from provider.schema import ProviderResponse


class BaseProvider(ABC):
    """LLM Provider 抽象基类

    子类必须实现 respond() 和 respond_stream()。
    engine 通过 last_response / last_usage 获取最终结果。
    """

    last_response: ProviderResponse | None = None
    last_usage: dict | None = None
    stream: bool = False

    @abstractmethod
    def respond(self, messages: list[dict], tools: list[dict] | None = None) -> ProviderResponse:
        """非流式调用，返回统一响应"""
        ...

    @abstractmethod
    def respond_stream(self, messages: list[dict], tools: list[dict] | None = None) -> Generator[dict, None, None]:
        """流式调用，yield 事件 dict:
            {"type": "thinking_chunk", "content": str}
            {"type": "text_chunk", "content": str}
        生成器耗尽后 self.last_response 可用。
        """
        ...
