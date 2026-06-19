# -*- coding: utf-8 -*-
"""Video Generation Skill - 视频生成任务工具。"""

import base64
import json
import mimetypes
import os

from plugins._common import err, safe_path, check_sandbox, get_current_user_dir, get_multimodal_context
from run.tool import register_tool


def _media_payload(value: str) -> str:
    if not value:
        return ""
    if value.startswith(("http://", "https://", "data:")):
        return value
    path = safe_path(value)
    if path is None:
        raise ValueError(f"无效的媒体路径: {value}")
    sandboxed = check_sandbox(path)
    if sandboxed is None:
        raise ValueError(f"媒体路径不在允许范围内: {value}")
    if not sandboxed.is_file():
        raise FileNotFoundError(f"媒体文件不存在: {sandboxed}")
    mime = mimetypes.guess_type(sandboxed.name)[0] or "application/octet-stream"
    data = base64.b64encode(sandboxed.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{data}"


def _default_download_dir() -> str:
    user_dir = get_current_user_dir()
    if not user_dir:
        raise ValueError("无法确定输出目录：缺少用户目录且未指定 output_dir")
    return os.path.join(user_dir, "download")


def video_generate(
    prompt: str = "",
    image: str = "",
    video: str = "",
    duration: int = 0,
    size: str = "",
    negative_prompt: str = "",
    seed: int = 0,
    model: str = "",
) -> str:
    """创建视频生成任务。提供 image 即图生视频，提供 video 即视频生视频，否则文生视频。"""
    ctx = get_multimodal_context()
    if not ctx or not ctx.get("provider"):
        return err("video_generate: 缺少 provider 上下文，请重新进入会话")

    provider = ctx["provider"]
    if "video_generation" not in provider.capabilities():
        return err("当前 provider 不支持视频生成 (video_generation)。请配置 video_generation_model 后再试。")

    try:
        result = provider.generate_video(
            prompt=prompt,
            image=_media_payload(image),
            video=_media_payload(video),
            duration=duration or None,
            size=size,
            negative_prompt=negative_prompt,
            seed=seed or None,
            model=model,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except NotImplementedError as e:
        return err(str(e))
    except Exception as e:
        return err(f"视频生成任务创建失败: {e}")


def video_status(job_id: str) -> str:
    """查询视频生成任务状态。"""
    ctx = get_multimodal_context()
    if not ctx or not ctx.get("provider"):
        return err("video_status: 缺少 provider 上下文，请重新进入会话")

    provider = ctx["provider"]
    if "video_generation" not in provider.capabilities():
        return err("当前 provider 不支持视频生成 (video_generation)。请配置 video_generation_model 后再试。")
    if not job_id.strip():
        return err("job_id 不能为空")

    try:
        result = provider.get_video(job_id=job_id)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except NotImplementedError as e:
        return err(str(e))
    except Exception as e:
        return err(f"视频任务查询失败: {e}")


def video_download(job_id: str, output_dir: str = "", filename: str = "") -> str:
    """下载视频生成任务结果。"""
    ctx = get_multimodal_context()
    if not ctx or not ctx.get("provider"):
        return err("video_download: 缺少 provider 上下文，请重新进入会话")

    provider = ctx["provider"]
    if "video_generation" not in provider.capabilities():
        return err("当前 provider 不支持视频生成 (video_generation)。请配置 video_generation_model 后再试。")
    if not job_id.strip():
        return err("job_id 不能为空")

    output_dir = output_dir or _default_download_dir()
    output_path = safe_path(output_dir)
    if output_path is None:
        return err(f"无效的输出目录: {output_dir}")
    sandboxed_output = check_sandbox(output_path)
    if sandboxed_output is None:
        return err(f"输出目录不在允许范围内: {output_dir}")

    try:
        return provider.download_video(job_id=job_id, output_dir=str(sandboxed_output), filename=filename)
    except NotImplementedError as e:
        return err(str(e))
    except Exception as e:
        return err(f"视频结果下载失败: {e}")


SCHEMA_GENERATE = {
    "type": "function",
    "function": {
        "name": "video_generate",
        "description": "创建视频生成任务。只传 prompt 为文生视频，传 image 为图生视频，传 video 为视频生视频。",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "视频描述或编辑要求"},
                "image": {"type": "string", "description": "可选图片路径、URL 或 data URL，用于图生视频"},
                "video": {"type": "string", "description": "可选视频路径、URL 或 data URL，用于视频生视频"},
                "duration": {"type": "integer", "description": "可选时长"},
                "size": {"type": "string", "description": "可选尺寸"},
                "negative_prompt": {"type": "string", "description": "可选负向提示词"},
                "seed": {"type": "integer", "description": "可选随机种子"},
                "model": {"type": "string", "description": "可选模型 ID；留空使用 provider.video_generation_model"}
            },
            "required": []
        }
    }
}

SCHEMA_STATUS = {
    "type": "function",
    "function": {
        "name": "video_status",
        "description": "查询视频生成任务状态。",
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "视频任务 ID"}
            },
            "required": ["job_id"]
        }
    }
}

SCHEMA_DOWNLOAD = {
    "type": "function",
    "function": {
        "name": "video_download",
        "description": "下载视频生成任务结果到本地。",
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "视频任务 ID"},
                "output_dir": {"type": "string", "description": "输出目录，默认 users/<user>/download/"},
                "filename": {"type": "string", "description": "可选输出文件名"}
            },
            "required": ["job_id"]
        }
    }
}


def register():
    register_tool(SCHEMA_GENERATE, video_generate)
    register_tool(SCHEMA_STATUS, video_status)
    register_tool(SCHEMA_DOWNLOAD, video_download)
