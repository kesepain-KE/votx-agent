"""抽象 Provider 接口 — 所有 LLM Provider 必须实现"""

from abc import ABC, abstractmethod
from typing import Generator

from provider.schema import ProviderResponse

# 合法能力名常量（所有 provider 复用，避免拼写漂移）
VALID_CAPABILITIES = {
    "vision",
    "audio_transcription",
    "image_generation",
    "image_edit",
    "speech_generation",
    "speech_to_speech",
    "video_generation",
    "embedding",
    "rerank",
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
        可能的值: "vision", "audio_transcription", "image_generation",
        "image_edit", "speech_generation", "speech_to_speech",
        "video_generation", "embedding", "rerank"
        """
        return set()

    def transcribe_audio(self, file_path: str, **kwargs) -> str:
        """语音转文字。返回转录文本。"""
        raise NotImplementedError("当前 provider 不支持语音识别 (audio_transcription)")

    def generate_image(self, prompt: str, **kwargs) -> list[dict]:
        """文生图。返回 [{"url": str, "b64_json": str|None, "revised_prompt": str}, ...]"""
        raise NotImplementedError("当前 provider 不支持图像生成 (image_generation)")

    def edit_image(self, image_path: str, prompt: str, **kwargs) -> list[dict]:
        """图像编辑。返回 [{"url": str, "b64_json": str|None, "revised_prompt": str}, ...]"""
        raise NotImplementedError("当前 provider 不支持图像编辑 (image_edit)")

    def generate_speech(self, text: str, **kwargs) -> str:
        """文生语音。保存到文件并返回路径。"""
        raise NotImplementedError("当前 provider 不支持语音生成 (speech_generation)")

    def speech_to_speech(self, audio_path: str, **kwargs) -> str:
        """语音生语音。保存到文件并返回路径。"""
        raise NotImplementedError("当前 provider 不支持语音生语音 (speech_to_speech)")

    def generate_video(self, prompt: str = "", **kwargs) -> dict:
        """生成视频任务。返回任务信息。"""
        raise NotImplementedError("当前 provider 不支持视频生成 (video_generation)")

    def get_video(self, job_id: str, **kwargs) -> dict:
        """查询视频任务状态。"""
        raise NotImplementedError("当前 provider 不支持视频生成 (video_generation)")

    def download_video(self, job_id: str, output_dir: str, **kwargs) -> str:
        """下载视频结果并返回本地路径。"""
        raise NotImplementedError("当前 provider 不支持视频生成 (video_generation)")

    def create_embeddings(self, texts: str | list[str], **kwargs) -> dict:
        """文本嵌入。返回 provider 原始兼容响应。"""
        raise NotImplementedError("当前 provider 不支持文本嵌入 (embedding)")

    def rerank_documents(self, query: str, documents: list[str], **kwargs) -> dict:
        """文档重排。返回 provider 原始兼容响应。"""
        raise NotImplementedError("当前 provider 不支持文档重排 (rerank)")
