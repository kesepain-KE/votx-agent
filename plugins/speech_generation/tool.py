# -*- coding: utf-8 -*-
"""
Speech Generation Skill - 文生语音工具
使用当前会话的 provider（通过 plugins._common 统一 ContextVar 注入）。
音频自动保存到本地文件。
"""

import os
import uuid

from plugins._common import err, safe_path, check_sandbox, get_current_user_dir, get_multimodal_context
from plugins._common.artifacts import make_file_artifact, make_tool_result
from run.tool import register_tool


def speech_generate(
    text: str,
    voice: str = "alloy",
    format: str = "mp3",
    speed: float = 1.0,
    output_dir: str = ""
) -> str:
    """文生语音，将文字转换为语音文件并保存到本地。

    Args:
        text:       要转换的文字（必填，最大 4096 字符）
        voice:      语音风格，支持 OpenAI 标准音色及各厂商自定义音色 ID，默认 alloy
        format:     输出音频格式 mp3/opus/aac/flac/wav/pcm
        speed:      语速 0.25-4.0，默认 1.0
        output_dir: 输出目录（默认 users/<user>/download/）
    """
    ctx = get_multimodal_context()
    if not ctx or not ctx.get("provider"):
        return err("speech_generate: 缺少 provider 上下文，请重新进入会话")

    provider = ctx["provider"]

    # 能力检查
    if "speech_generation" not in provider.capabilities():
        return err(
            f"当前 provider 不支持语音生成 (speech_generation)。"
            f"请切换到支持 TTS 的 provider（如 OpenAI 官方 API）后再试。"
        )

    # output_dir 默认值
    if not output_dir:
        user_dir = get_current_user_dir()
        if user_dir:
            output_dir = os.path.join(user_dir, "download")
        else:
            return err("无法确定输出目录：缺少用户目录且未指定 output_dir")

    p = safe_path(output_dir)
    if p is None:
        return err(f"无效的输出目录: {output_dir}")
    sandboxed = check_sandbox(p)
    if sandboxed is None:
        return err(f"输出目录不在允许范围内: {output_dir}")
    os.makedirs(str(sandboxed), exist_ok=True)

    try:
        filepath = provider.generate_speech(
            text=text,
            voice=voice,
            format=format,
            speed=speed,
            output_dir=str(sandboxed),
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
        "description": "文生语音，将文字转换为语音文件并保存到本地。原生 TTS 端点优先，失败自动降级为 chat completions（适配 kokoro/MiMo 等非标准模型）。",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "要转换的文字（必填，最大 4096 字符）"
                },
                "voice": {
                    "type": "string",
                    "description": "语音风格，支持 OpenAI 标准音色 (alloy/echo/fable/onyx/nova/shimmer) 及各厂商自定义音色 ID（如 StepFun: ruanmengnvsheng / tianmeinvsheng 等），默认 alloy"
                },
                "format": {
                    "type": "string",
                    "enum": ["mp3", "opus", "aac", "flac", "wav", "pcm"],
                    "description": "输出音频格式，默认 mp3"
                },
                "speed": {
                    "type": "number",
                    "description": "语速 0.25-4.0，默认 1.0"
                },
                "output_dir": {
                    "type": "string",
                    "description": "输出目录（默认 users/<user>/download/）"
                }
            },
            "required": ["text"]
        }
    }
}


def register():
    """注册 speech_generate 工具。"""
    register_tool(SCHEMA, speech_generate)
