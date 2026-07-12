# -*- coding: utf-8 -*-
"""Video Generation Skill - 视频生成任务工具。"""

import base64
import json
import mimetypes
import os

from plugins._common import err, get_current_user_dir, get_multimodal_context
from plugins._common.artifacts import make_file_artifact, make_tool_result
from run.tool import register_tool


def _media_payload(value: str) -> str:
    if not value:
        return ""
    if value.startswith(("http://", "https://", "data:")):
        return value
    if not os.path.isfile(value):
        raise FileNotFoundError(f"媒体文件不存在: {value}")
    mime = mimetypes.guess_type(value)[0] or "application/octet-stream"
    with open(value, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
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

    try:
        filepath = provider.download_video(job_id=job_id, output_dir=output_dir, filename=filename)
        return make_tool_result(True, "视频下载完成", [make_file_artifact(filepath)])
    except NotImplementedError as e:
        return err(str(e))
    except Exception as e:
        return err(f"视频结果下载失败: {e}")


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "video_generate",
            "description": "创建视频生成任务。只传 prompt 为文生视频，传 image 为图生视频，传 video 为视频生视频。当用户要求生成视频、AI 视频、创建动画、图生视频时使用。",
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
    },
    {
        "type": "function",
        "function": {
            "name": "video_status",
            "description": "查询视频生成任务状态。当用户询问视频生成进度、是否完成、任务状态时使用。需要先使用过 video_generate 创建任务。",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "视频任务 ID"}
                },
                "required": ["job_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "video_download",
            "description": "下载视频生成任务结果到本地。当视频生成任务完成后，用户要求下载视频、保存视频时使用。需要先用 video_status 确认任务已完成。",
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
    },
]


def register():
    for s in SCHEMAS:
        register_tool(s, {"video_generate": video_generate, "video_status": video_status, "video_download": video_download}[s["function"]["name"]])
