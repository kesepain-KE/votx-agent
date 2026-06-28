# -*- coding: utf-8 -*-
"""Speech-to-Speech Skill - 语音生语音工具。"""

import os
import uuid

from plugins._common import err, safe_path, check_sandbox, get_current_user_dir, get_multimodal_context
from plugins._common.artifacts import make_file_artifact, make_tool_result
from run.tool import register_tool


def speech_to_speech(
    audio: str,
    prompt: str = "",
    instruction: str = "",
    voice: str = "",
    format: str = "mp3",
    output_dir: str = "",
) -> str:
    """语音生语音，将本地音频转换为新的音频文件。"""
    ctx = get_multimodal_context()
    if not ctx or not ctx.get("provider"):
        return err("speech_to_speech: 缺少 provider 上下文，请重新进入会话")

    provider = ctx["provider"]
    if "speech_to_speech" not in provider.capabilities():
        return err("当前 provider 不支持语音生语音 (speech_to_speech)。请配置 speech_to_speech_model 后再试。")

    audio_path = safe_path(audio)
    if audio_path is None:
        return err(f"无效的音频路径: {audio}")
    sandboxed_audio = check_sandbox(audio_path)
    if sandboxed_audio is None:
        return err(f"音频路径不在允许范围内: {audio}")
    if not sandboxed_audio.is_file():
        return err(f"音频文件不存在: {sandboxed_audio}")

    if not output_dir:
        user_dir = get_current_user_dir()
        if user_dir:
            output_dir = os.path.join(user_dir, "download")
        else:
            return err("无法确定输出目录：缺少用户目录且未指定 output_dir")

    output_path = safe_path(output_dir)
    if output_path is None:
        return err(f"无效的输出目录: {output_dir}")
    sandboxed_output = check_sandbox(output_path)
    if sandboxed_output is None:
        return err(f"输出目录不在允许范围内: {output_dir}")

    try:
        filepath = provider.speech_to_speech(
            audio_path=str(sandboxed_audio),
            prompt=prompt,
            instruction=instruction,
            voice=voice,
            format=format,
            output_dir=str(sandboxed_output),
            filename=f"speech_to_speech_{uuid.uuid4().hex[:8]}.{format}",
        )
        return make_tool_result(True, "语音转换完成", [make_file_artifact(filepath)])
    except NotImplementedError as e:
        return err(str(e))
    except Exception as e:
        return err(f"语音生语音失败: {e}")


SCHEMA = {
    "type": "function",
    "function": {
        "name": "speech_to_speech",
        "description": "语音生语音，输入本地音频并保存转换后的音频文件。需要 provider 支持 speech_to_speech。",
        "parameters": {
            "type": "object",
            "properties": {
                "audio": {"type": "string", "description": "本地音频路径"},
                "prompt": {"type": "string", "description": "转换要求，可选"},
                "instruction": {"type": "string", "description": "语气、风格等全局指令，可选"},
                "voice": {"type": "string", "description": "目标音色，可选"},
                "format": {
                    "type": "string",
                    "enum": ["mp3", "wav", "flac", "opus", "pcm"],
                    "description": "输出音频格式，默认 mp3"
                },
                "output_dir": {"type": "string", "description": "输出目录，默认 users/<user>/download/"}
            },
            "required": ["audio"]
        }
    }
}


def register():
    register_tool(SCHEMA, speech_to_speech)
