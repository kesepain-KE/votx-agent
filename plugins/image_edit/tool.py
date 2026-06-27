# -*- coding: utf-8 -*-
"""
Image Edit Skill - 图像编辑工具
使用当前会话的 provider（通过 plugins._common 统一 ContextVar 注入）。
图片自动保存到本地，支持 URL 和 base64 两种返回格式。
"""

import base64
import os
import uuid
from urllib.request import urlretrieve

from plugins._common import err, safe_path, check_sandbox, get_current_user_dir, get_multimodal_context
from plugins._common.artifacts import make_image_artifact, make_tool_result
from run.tool import register_tool


def image_edit(
    image: str,
    prompt: str,
    response_format: str = "url",
    output_dir: str = "",
    filename: str = "",
) -> str:
    """图像编辑，根据输入图片和文字要求编辑图片并保存到本地。

    Args:
        image:           本地图片路径（必填）
        prompt:          编辑要求（必填）
        response_format: 返回格式 url / b64_json
        output_dir:      输出目录（默认 users/<user>/download/）
        filename:        自定义文件名前缀（自动追加序号和 .png）
    """
    ctx = get_multimodal_context()
    if not ctx or not ctx.get("provider"):
        return err("image_edit: 缺少 provider 上下文，请重新进入会话")

    provider = ctx["provider"]

    if "image_edit" not in provider.capabilities():
        return err(
            "当前 provider 不支持图像编辑 (image_edit)。"
            "请切换到支持图像编辑的 provider（如 Kemo LLM Adapter）后再试。"
        )

    image_path = safe_path(image)
    if image_path is None:
        return err(f"无效的图片路径: {image}")
    sandboxed_image = check_sandbox(image_path)
    if sandboxed_image is None:
        return err(f"图片路径不在允许范围内: {image}")
    if not sandboxed_image.is_file():
        return err(f"图片文件不存在: {sandboxed_image}")

    if response_format not in ("url", "b64_json"):
        return err("response_format 只能是 url 或 b64_json")

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
    os.makedirs(str(sandboxed_output), exist_ok=True)

    try:
        results = provider.edit_image(
            image_path=str(sandboxed_image),
            prompt=prompt,
            response_format=response_format,
        )
    except NotImplementedError as e:
        return err(str(e))
    except Exception as e:
        return err(f"图像编辑失败: {e}")

    saved = []
    for i, item in enumerate(results):
        fname = filename or f"edited_{uuid.uuid4().hex[:8]}"
        if len(results) > 1:
            fname = f"{fname}_{i + 1}"
        filepath = os.path.join(str(sandboxed_output), f"{fname}.png")

        try:
            if item.get("url"):
                urlretrieve(item["url"], filepath)
                artifact = make_image_artifact(
                    filepath,
                    source_url=item["url"],
                    revised_prompt=item.get("revised_prompt", prompt),
                    finish_reason=item.get("finish_reason"),
                    seed=item.get("seed"),
                )
                saved.append(artifact)
            elif item.get("b64_json"):
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(item["b64_json"]))
                artifact = make_image_artifact(
                    filepath,
                    source_url=None,
                    revised_prompt=item.get("revised_prompt", prompt),
                    finish_reason=item.get("finish_reason"),
                    seed=item.get("seed"),
                )
                saved.append(artifact)
        except Exception as e:
            return err(f"保存编辑结果失败: {e}")

    if not saved:
        return err("图像编辑未返回可保存的结果")
    return make_tool_result(True, "图片编辑完成", saved)


SCHEMA = {
    "type": "function",
    "function": {
        "name": "image_edit",
        "description": "图像编辑，根据输入图片和文字要求编辑图片并保存到本地。需要 provider 支持 image_edit 能力。",
        "parameters": {
            "type": "object",
            "properties": {
                "image": {
                    "type": "string",
                    "description": "本地图片路径（必填）"
                },
                "prompt": {
                    "type": "string",
                    "description": "编辑要求（必填）"
                },
                "response_format": {
                    "type": "string",
                    "enum": ["url", "b64_json"],
                    "description": "返回格式，默认 url"
                },
                "output_dir": {
                    "type": "string",
                    "description": "输出目录（默认 users/<user>/download/）"
                },
                "filename": {
                    "type": "string",
                    "description": "自定义文件名前缀（自动追加序号和 .png 扩展名）"
                }
            },
            "required": ["image", "prompt"]
        }
    }
}


def register():
    """注册 image_edit 工具。"""
    register_tool(SCHEMA, image_edit)
