# -*- coding: utf-8 -*-
"""
Vision Universal Skill - 多模态识图工具
使用当前会话的 provider（通过 plugins._common 统一 ContextVar 注入）。
支持多图 + 旧单图参数兼容 + 能力检查。
"""

import base64
import copy

from plugins._common import err, safe_path, check_sandbox, get_multimodal_context
from run.tool import register_tool


def _detect_mime(suffix: str) -> str:
    """根据文件后缀返回 MIME 类型。"""
    return {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.png': 'image/png', '.gif': 'image/gif',
        '.webp': 'image/webp', '.bmp': 'image/bmp',
    }.get(suffix.lower(), 'image/jpeg')


def vision_analyze(
    images: list[str] = None,
    image: str = None,
    prompt: str = "描述这些图片的内容",
    detail: str = "auto"
) -> str:
    """分析图片内容，使用当前会话的 provider（支持 OpenAI/Anthropic/所有 provider）。

    Args:
        images: 图片路径列表（优先使用）
        image:  单张图片路径（兼容旧参数，无 images 时启用）
        prompt: 分析提示词
        detail: 图片解析精度 auto/low/high（仅 OpenAI 系列支持）
    """
    ctx = get_multimodal_context()
    if not ctx or not ctx.get("provider"):
        return err("vision_universal: 缺少 provider 上下文，请重新进入会话")

    provider = ctx["provider"]

    # 能力检查
    if "vision" not in provider.capabilities():
        return err(
            f"当前 provider 不支持视觉/多模态能力 (vision)。"
            f"请切换到支持多模态的模型（如 GPT-4o、Claude 3+、Gemini Vision 等）后再试。"
        )

    # 兼容旧参数：有 images 用 images，没有则 fallback 到 image
    image_list = images or []
    if not image_list and image:
        image_list = [image]
    if not image_list:
        return err("至少需要一张图片（images 或 image 参数）")

    # 构造 multimodal content blocks
    content_blocks = []
    for img in image_list:
        if img.startswith(("http://", "https://")):
            content_blocks.append({
                "type": "image_url",
                "image_url": {"url": img, "detail": detail}
            })
        else:
            # 沙箱校验
            p = safe_path(img)
            if p is None:
                return err(f"无效的图片路径: {img}")
            sandboxed = check_sandbox(p)
            if sandboxed is None:
                return err(f"图片路径不在允许范围内: {img}")
            if not sandboxed.exists():
                return err(f"图片文件不存在: {img}")
            data = base64.b64encode(sandboxed.read_bytes()).decode("utf-8")
            mime = _detect_mime(sandboxed.suffix)
            content_blocks.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{data}", "detail": detail}
            })

    if prompt.strip():
        content_blocks.append({"type": "text", "text": prompt})

    messages = [{"role": "user", "content": content_blocks}]

    try:
        model = getattr(provider, 'vision_model', None) or None  # 专用模型 > 默认聊天模型
        response = provider.respond(messages, tools=None, model=model)
        return response.text
    except Exception as e:
        return err(str(e))


SCHEMA_VISION_ANALYZE = {
    "type": "function",
    "function": {
        "name": "vision_analyze",
        "description": "使用多模态模型分析图片内容，支持多图和单图。vision_model 优先于默认聊天模型。适配所有 OpenAI 兼容多模态 API。",
        "parameters": {
            "type": "object",
            "properties": {
                "images": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "图片路径列表（本地文件路径或 http/https URL）"
                },
                "image": {
                    "type": "string",
                    "description": "单张图片路径（兼容旧参数，优先使用 images）"
                },
                "prompt": {
                    "type": "string",
                    "description": "分析提示词，默认为'描述这些图片的内容'"
                },
                "detail": {
                    "type": "string",
                    "enum": ["auto", "low", "high"],
                    "description": "图片解析精度（仅 OpenAI 系列支持，默认 auto）"
                }
            },
            "required": []
        }
    }
}


def register():
    """注册 vision_analyze + vision_universal(兼容旧名) 两个工具。"""
    register_tool(SCHEMA_VISION_ANALYZE, vision_analyze)
    # 兼容旧名：deep copy 避免共享内部 function dict
    SCHEMA_OLD = copy.deepcopy(SCHEMA_VISION_ANALYZE)
    SCHEMA_OLD["function"]["name"] = "vision_universal"
    register_tool(SCHEMA_OLD, vision_analyze)
