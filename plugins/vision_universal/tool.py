# -*- coding: utf-8 -*-
"""
Vision Universal Skill - 原生多模态识图工具
使用当前会话的 provider（通过 ContextVar 注入），支持所有 provider 类型。
"""

import base64
from contextvars import ContextVar

from plugins._common import err, safe_path, check_sandbox
from run.tool import register_tool

# 已知支持多模态/视觉的模型名称关键词
_VISION_MODEL_KEYWORDS = [
    "gpt-5", "gpt-4.1", "gpt-4o", "gpt-4-vision", "gpt-4-turbo",
    "claude-3", "claude-4", "claude-sonnet", "claude-opus", "claude-haiku",
    "gemini", "gemma-3",
    "mimo", "minimax",
    "qwen-vl", "qwen2-vl", "qwen2.5-vl",
    "vision", "vl-", "-vl",
    "llava", "cogvlm", "cogview",
    "pixtral", "llama-3.2-vision", "llama-v",
    "internvl", "internlm-xcomposer",
    "glm-4v", "cogview",
    "step-1v", "step-1o",
    "yi-vision",
    "hunyuan-vision",
    "doubao-vision", "doubao-1.5-vision",
    "ernie-vilg", "ernie-4.0",
    "seed-oss", "seedream",
]

# 会话级 provider 上下文（由 web/session.py 注入，与 auto_improve/task_plan 同模式）
_vision_ctx: ContextVar = ContextVar("vision_ctx", default=None)


def set_vision_context(provider, chat=None, user_name: str = ""):
    """注入当前会话的 provider 上下文。由 web/session.py 在会话初始化时调用。"""
    _vision_ctx.set({"provider": provider, "chat": chat, "user_name": user_name})


def _detect_mime(suffix: str) -> str:
    """根据文件后缀返回 MIME 类型。"""
    return {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.png': 'image/png', '.gif': 'image/gif',
        '.webp': 'image/webp', '.bmp': 'image/bmp',
    }.get(suffix.lower(), 'image/jpeg')


def _supports_vision(model: str) -> bool:
    """检查模型名称是否命中已知的多模态/视觉关键词。"""
    model_lower = model.lower()
    return any(kw in model_lower for kw in _VISION_MODEL_KEYWORDS)


def analyze_image(
    image: str,
    prompt: str = "描述这张图片的内容",
    max_tokens: int = 1500
) -> str:
    """分析图片内容，使用当前会话的 provider（支持 OpenAI/Anthropic/所有 provider）。"""
    ctx = _vision_ctx.get()
    if not ctx or not ctx.get("provider"):
        return err("vision_universal: 缺少 provider 上下文，请重新进入会话")

    provider = ctx["provider"]

    # 检查模型是否支持多模态
    model = ""
    if hasattr(provider, 'model') and provider.model:
        model = provider.model
    if not model:
        model = getattr(provider, '_model', '') or ""

    if model and not _supports_vision(model):
        return err(
            f"当前模型 {model} 不支持多模态/视觉。"
            f"vision_universal 需要 GPT-4o、Claude 3+、Gemini Vision、MiMo 等原生多模态模型。"
            f"请切换到一个支持多模态的 provider 后再试。"
        )

    # 准备图片
    if image.startswith(("http://", "https://")):
        image_content = {"type": "image_url", "image_url": {"url": image}}
    else:
        # 沙箱校验
        p = safe_path(image)
        if p is None:
            return err(f"无效的图片路径: {image}")
        sandboxed = check_sandbox(p)
        if sandboxed is None:
            return err(f"图片路径不在允许范围内: {image}")
        if not sandboxed.exists():
            return err(f"图片文件不存在: {image}")
        data = base64.b64encode(sandboxed.read_bytes()).decode("utf-8")
        mime = _detect_mime(sandboxed.suffix)
        image_content = {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}

    # 使用 session provider 发起请求（non-streaming，与 auto_improve/task_plan 模式一致）
    messages = [
        {"role": "user", "content": [image_content] + ([{"type": "text", "text": prompt}] if prompt.strip() else [])}
    ]

    try:
        response = provider.respond(messages, tools=None)
        return response.text
    except Exception as e:
        return err(str(e))


SCHEMA = {
    "type": "function",
    "function": {
        "name": "vision_universal",
        "description": "使用当前会话的多模态模型分析图片内容，支持本地图片和远程URL。需要当前 provider 支持多模态/视觉（如 GPT-4o、Claude 3+、Gemini Vision、MiMo 等）。",
        "parameters": {
            "type": "object",
            "properties": {
                "image": {
                    "type": "string",
                    "description": "图片路径（本地文件路径或 http/https URL）"
                },
                "prompt": {
                    "type": "string",
                    "description": "分析提示词，默认为'描述这张图片的内容'"
                }
            },
            "required": ["image"]
        }
    }
}

HANDLERS = {"vision_universal": analyze_image}


def register():
    """注册 vision_universal 工具。"""
    register_tool(SCHEMA, HANDLERS["vision_universal"])
