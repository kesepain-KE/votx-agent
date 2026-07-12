# -*- coding: utf-8 -*-
"""
Audio Universal Skill - 语音识别/转录工具
使用当前会话的 provider（通过 plugins._common 统一 ContextVar 注入）。
支持多种语言、引导词、时间戳粒度。
"""

import os
from plugins._common import err, get_multimodal_context
from run.tool import register_tool


def audio_transcribe(
    audio: str,
    language: str = "",
    prompt: str = "",
    timestamp_granularity: str = "segment"
) -> str:
    """语音转文字，将音频文件转录为文本。

    Args:
        audio:                 音频文件路径（本地文件）
        language:              语言代码（如 zh, en），留空自动检测
        prompt:                引导词，帮助模型适应特定风格或上下文
        timestamp_granularity: 时间戳粒度 — none(无), segment(段落级), word(单词级)
    """
    ctx = get_multimodal_context()
    if not ctx or not ctx.get("provider"):
        return err("audio_transcribe: 缺少 provider 上下文，请重新进入会话")

    provider = ctx["provider"]

    # 能力检查
    if "audio_transcription" not in provider.capabilities():
        return err(
            f"当前 provider 不支持语音识别 (audio_transcription)。"
            f"请切换到支持语音转录的 provider 后再试。"
        )

    if not os.path.exists(audio):
        return err(f"音频文件不存在: {audio}")

    try:
        return provider.transcribe_audio(
            file_path=audio,
            language=language,
            prompt=prompt,
            timestamp_granularity=timestamp_granularity,
        )
    except NotImplementedError as e:
        return err(str(e))
    except Exception as e:
        return err(f"语音转录失败: {e}")


SCHEMA = {
    "type": "function",
    "function": {
        "name": "audio_transcribe",
        "description": "语音转文字，将音频文件转录为带可选时间戳的文本。当用户要求语音识别、转录、听写、音频转文字、ASR 时使用。原生端点优先，失败自动降级为 chat completions。支持多语言和引导词。",
        "parameters": {
            "type": "object",
            "properties": {
                "audio": {
                    "type": "string",
                    "description": "音频文件路径（本地文件）"
                },
                "language": {
                    "type": "string",
                    "description": "音频语言代码，留空自动检测。由智能体自行传入合适的语言代码即可。"
                },
                "prompt": {
                    "type": "string",
                    "description": "引导词，帮助模型适应特定风格或上下文词汇"
                },
                "timestamp_granularity": {
                    "type": "string",
                    "enum": ["none", "segment", "word"],
                    "description": "时间戳粒度：none=纯文本、segment=段落级时间戳、word=单词级时间戳"
                }
            },
            "required": ["audio"]
        }
    }
}


def register():
    """注册 audio_transcribe 工具。"""
    register_tool(SCHEMA, audio_transcribe)
