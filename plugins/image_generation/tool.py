# -*- coding: utf-8 -*-
"""
Image Generation Skill - 文生图工具
使用当前会话的 provider（通过 plugins._common 统一 ContextVar 注入）。
图片自动保存到本地，支持 URL 和 base64 两种返回格式。
"""

import base64
import json
import os
import uuid
from urllib.request import urlretrieve

from plugins._common import err, safe_path, check_sandbox, get_current_user_dir, get_multimodal_context
from run.tool import register_tool


def image_generate(
    prompt: str,
    size: str = "1024x1024",
    quality: str = "standard",
    n: int = 1,
    output_dir: str = "",
    filename: str = ""
) -> str:
    """文生图，根据文字描述生成图片并保存到本地。

    Args:
        prompt:     图片描述（必填）
        size:       图片尺寸 1024x1024 / 1792x1024 / 1024x1792
        quality:    图片质量 standard / hd
        n:          生成数量 1-4
        output_dir: 输出目录（默认 users/<user>/download/）
        filename:   自定义文件名前缀（自动追加序号和 .png）
    """
    ctx = get_multimodal_context()
    if not ctx or not ctx.get("provider"):
        return err("image_generate: 缺少 provider 上下文，请重新进入会话")

    provider = ctx["provider"]

    # 能力检查
    if "image_generation" not in provider.capabilities():
        return err(
            f"当前 provider 不支持图像生成 (image_generation)。"
            f"请切换到支持图像生成的 provider（如 OpenAI 官方 API）后再试。"
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
        # 同时支持 URL 下载和 base64 解码
        if r.get("url"):
            filepath = os.path.join(str(sandboxed), f"{fname}.png")
            urlretrieve(r["url"], filepath)
            saved.append({
                "path": filepath,
                "url": r["url"],
                "revised_prompt": r.get("revised_prompt", prompt),
            })
        elif r.get("b64_json"):
            filepath = os.path.join(str(sandboxed), f"{fname}.png")
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(r["b64_json"]))
            saved.append({
                "path": filepath,
                "url": None,
                "revised_prompt": r.get("revised_prompt", prompt),
            })

    if not saved:
        return err("图像生成未返回可保存的结果")
    return json.dumps(saved, ensure_ascii=False, indent=2)


SCHEMA = {
    "type": "function",
    "function": {
        "name": "image_generate",
        "description": "文生图，根据文字描述生成图片并保存到本地。原生 images 端点优先，失败自动降级为 chat completions。支持多种尺寸和质量。",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "图片描述（必填）"
                },
                "size": {
                    "type": "string",
                    "enum": ["1024x1024", "1792x1024", "1024x1792"],
                    "description": "图片尺寸，默认 1024x1024"
                },
                "quality": {
                    "type": "string",
                    "enum": ["standard", "hd"],
                    "description": "图片质量：standard 标准、hd 高清（仅 DALL-E 3 支持 hd）"
                },
                "n": {
                    "type": "integer",
                    "description": "生成数量，1-4，默认 1"
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
            "required": ["prompt"]
        }
    }
}


def register():
    """注册 image_generate 工具。"""
    register_tool(SCHEMA, image_generate)
