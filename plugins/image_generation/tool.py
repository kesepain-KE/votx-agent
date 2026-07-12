# -*- coding: utf-8 -*-
"""
Image Generation Skill - 文生图工具
使用当前会话的 provider（通过 plugins._common 统一 ContextVar 注入）。
图片自动保存到本地，支持 URL 和 base64 两种返回格式。
"""

import base64
import os
import uuid
from urllib.request import urlretrieve

from plugins._common import err, get_current_user_dir, get_multimodal_context
from plugins._common.artifacts import make_image_artifact, make_tool_result
from run.tool import register_tool


def image_generate(
    prompt: str,
    size: str = "1024x1024",
    quality: str = "standard",
    n: int = 1,
    output_dir: str = "",
    filename: str = ""
) -> str:
    """文生图，根据文字描述生成图片并保存到本地。"""
    ctx = get_multimodal_context()
    if not ctx or not ctx.get("provider"):
        return err("image_generate: 缺少 provider 上下文，请重新进入会话")

    provider = ctx["provider"]

    if "image_generation" not in provider.capabilities():
        return err(
            f"当前 provider 不支持图像生成 (image_generation)。"
            f"请切换到支持图像生成的 provider 后再试。"
        )

    if not output_dir:
        user_dir = get_current_user_dir()
        if user_dir:
            output_dir = os.path.join(user_dir, "download")
        else:
            return err("无法确定输出目录：缺少用户目录且未指定 output_dir")

    os.makedirs(output_dir, exist_ok=True)

    try:
        results = provider.generate_image(prompt=prompt, size=size, quality=quality, n=n)
    except NotImplementedError as e:
        return err(str(e))
    except Exception as e:
        return err(f"图像生成失败: {e}")

    saved = []
    for i, r in enumerate(results):
        fname = filename or f"generated_{uuid.uuid4().hex[:8]}"
        if n > 1:
            fname = f"{fname}_{i + 1}"
        if r.get("url"):
            filepath = os.path.join(output_dir, f"{fname}.png")
            urlretrieve(r["url"], filepath)
            artifact = make_image_artifact(
                filepath,
                source_url=r["url"],
                revised_prompt=r.get("revised_prompt", prompt),
            )
            saved.append(artifact)
        elif r.get("b64_json"):
            filepath = os.path.join(output_dir, f"{fname}.png")
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(r["b64_json"]))
            artifact = make_image_artifact(
                filepath,
                source_url=None,
                revised_prompt=r.get("revised_prompt", prompt),
            )
            saved.append(artifact)

    if not saved:
        return err("图像生成未返回可保存的结果")
    return make_tool_result(True, "图片生成完成", saved)


SCHEMA = {
    "type": "function",
    "function": {
        "name": "image_generate",
        "description": "文生图，根据文字描述生成图片并保存到本地。当用户要求生成图片、画图、AI 绘画、创建图像时使用。原生 images 端点优先，失败自动降级为 chat completions。支持多种尺寸和质量，具体可用值取决于当前 provider 配置的图像生成模型。",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "图片描述（必填）"},
                "size": {"type": "string", "description": "图片尺寸，格式为 宽x高，如 1024x1024、1792x1024、1024x1792。默认 1024x1024。具体可选尺寸取决于厂商模型支持"},
                "quality": {"type": "string", "description": "图片质量。常见值：standard（标准）、hd（高清）。不同厂商支持的值不同，请根据当前 provider 传入"},
                "n": {"type": "integer", "description": "生成数量，默认 1。具体可生成的数量取决于厂商模型支持"},
                "output_dir": {"type": "string", "description": "输出目录（默认 users/<user>/download/）"},
                "filename": {"type": "string", "description": "自定义文件名前缀"}
            },
            "required": ["prompt"]
        }
    }
}


def register():
    register_tool(SCHEMA, image_generate)
