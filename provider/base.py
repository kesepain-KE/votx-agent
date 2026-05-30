"""抽象 Provider 接口 — 所有 LLM Provider 必须实现"""

from abc import ABC, abstractmethod
from typing import Generator

from provider.schema import ProviderResponse

# 合法能力名常量（所有 provider 复用，避免拼写漂移）
VALID_CAPABILITIES = {
    "vision",
    "audio_transcription",
    "image_generation",
    "speech_generation",
}


class BaseProvider(ABC):
    """LLM Provider 抽象基类

    子类必须实现 respond() 和 respond_stream()。
    engine 通过 last_response / last_usage 获取最终结果。
    """

    last_response: ProviderResponse | None = None
    last_usage: dict | None = None
    stream: bool = False

    @abstractmethod
    def respond(self, messages: list[dict], tools: list[dict] | None = None, model: str | None = None) -> ProviderResponse:
        """非流式调用，返回统一响应。model 为 None 时使用默认聊天模型。"""
        ...

    @abstractmethod
    def respond_stream(self, messages: list[dict], tools: list[dict] | None = None, model: str | None = None) -> Generator[dict, None, None]:
        """流式调用，yield 事件 dict:
            {"type": "thinking_chunk", "content": str}
            {"type": "text_chunk", "content": str}
        生成器耗尽后 self.last_response 可用。
        """
        ...

    def capabilities(self) -> set[str]:
        """返回当前 provider 支持的能力集合。
        可能的值: "vision", "audio_transcription", "image_generation", "speech_generation"
        """
        return set()

    def transcribe_audio(self, file_path: str, **kwargs) -> str:
        """语音转文字。返回转录文本。"""
        raise NotImplementedError("当前 provider 不支持语音识别 (audio_transcription)")

    def generate_image(self, prompt: str, **kwargs) -> list[dict]:
        """文生图。返回 [{"url": str, "b64_json": str|None, "revised_prompt": str}, ...]"""
        raise NotImplementedError("当前 provider 不支持图像生成 (image_generation)")

    def generate_speech(self, text: str, **kwargs) -> str:
        """文生语音。保存到文件并返回路径。"""
        raise NotImplementedError("当前 provider 不支持语音生成 (speech_generation)")
