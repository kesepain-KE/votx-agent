# -*- coding: utf-8 -*-
"""
Speech Generation Skill - 文生语音工具
使用当前会话的 provider（通过 plugins._common 统一 ContextVar 注入）。
音频自动保存到本地文件。
"""

import os
import uuid

from plugins._common import err, get_current_user_dir, get_multimodal_context
from plugins._common.artifacts import make_file_artifact, make_tool_result
from run.tool import register_tool


def speech_generate(
    text: str,
    voice: str = "alloy",
    format: str = "mp3",
    speed: float = 1.0,
    output_dir: str = ""
) -> str:
    """文生语音，将文字转换为语音文件并保存到本地。"""
    ctx = get_multimodal_context()
    if not ctx or not ctx.get("provider"):
        return err("speech_generate: 缺少 provider 上下文，请重新进入会话")

    provider = ctx["provider"]

    if "speech_generation" not in provider.capabilities():
        return err(
            f"当前 provider 不支持语音生成 (speech_generation)。"
            f"请切换到支持 TTS 的 provider 后再试。"
        )

    if not output_dir:
        user_dir = get_current_user_dir()
        if user_dir:
            output_dir = os.path.join(user_dir, "download")
        else:
            return err("无法确定输出目录：缺少用户目录且未指定 output_dir")

    os.makedirs(output_dir, exist_ok=True)

    try:
        filepath = provider.generate_speech(
            text=text,
            voice=voice,
            format=format,
            speed=speed,
            output_dir=output_dir,
            filename=f"speech_{uuid.uuid4().hex[:8]}.{format}",
        )
        return make_tool_result(True, "语音生成完成", [make_file_artifact(filepath)])
    except NotImplementedError as e:
        return err(str(e))
    except Exception as e:
        return err(f"语音生成失败: {e}")


SCHEMA = {
    "type": "function",
    "function": {
        "name": "speech_generate",
        "description": "文生语音，将文字转换为语音文件并保存到本地。当用户要求语音合成、TTS、文字转语音、朗读文字、生成音频时使用。原生 TTS 端点优先，失败自动降级为 chat completions（适配 kokoro/MiMo 等非标准模型）。支持多种音色和格式，音色 ID 取决于当前 provider 配置的 TTS 模型。",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要转换的文字（必填）"},
                "voice": {"type": "string", "description": "语音风格/音色 ID。不同厂商的音色 ID 完全不同（如 OpenAI: alloy/echo/fable/onyx/nova/shimmer；StepFun: ruanmengnvsheng/tianmeinvsheng 等）。请根据当前 provider 配置的 TTS 模型选择对应音色，留空使用默认"},
                "format": {"type": "string", "description": "输出音频格式，如 mp3/opus/aac/flac/wav/pcm。默认 mp3。不同厂商支持的格式不同，请根据当前 provider 支持的格式传入"},
                "speed": {"type": "number", "description": "语速倍率，默认 1.0。不同厂商支持的范围不同，通常 0.25-4.0"},
                "output_dir": {"type": "string", "description": "输出目录（默认 users/<user>/download/）"}
            },
            "required": ["text"]
        }
    }
}


def register():
    register_tool(SCHEMA, speech_generate)
