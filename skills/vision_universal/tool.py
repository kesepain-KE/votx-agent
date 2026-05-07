# -*- coding: utf-8 -*-
"""
Vision Universal Skill - 原生多模态识图工具
适用场景：模型原生支持多模态（GPT-4o、MiMo、Claude 等），直接通过 Chat Completions API 传图。
"""

import base64
import json
from pathlib import Path
from typing import Optional

from run.tool import register_tool


def _load_user_config() -> dict:
    """加载当前用户配置，自动探测活跃用户目录。"""
    from paths import get_project_root
    root = Path(get_project_root())
    users_dir = root / 'users'

    configs = sorted(users_dir.glob('*/config.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    for cfg_path in configs:
        try:
            cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
            if cfg.get('provider', {}).get('api_key'):
                return cfg
        except Exception:
            continue

    # 回退：读第一个 config
    for cfg_path in configs:
        try:
            return json.loads(cfg_path.read_text(encoding='utf-8'))
        except Exception:
            continue
    return {}


def _detect_mime(suffix: str) -> str:
    return {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.png': 'image/png', '.gif': 'image/gif',
        '.webp': 'image/webp', '.bmp': 'image/bmp',
    }.get(suffix.lower(), 'image/jpeg')


def analyze_image(
    image_path: str,
    prompt: str = "描述这张图片的内容",
    model: Optional[str] = None,
    max_tokens: int = 1500
) -> str:
    """分析图片内容，使用原生多模态模型。"""
    from openai import OpenAI

    config = _load_user_config()
    provider = config.get('provider', {})
    api_key = provider.get('api_key')
    base_url = provider.get('base_url', 'https://api.openai.com/v1')
    model = model or provider.get('model', 'gpt-4o-mini')

    if not api_key:
        return "ERROR: 未找到 API 密钥，请在 config.json 中配置 provider.api_key"

    # 准备图片
    if image_path.startswith(('http://', 'https://')):
        image_content = {'type': 'image_url', 'image_url': {'url': image_path}}
    else:
        image_file = Path(image_path)
        if not image_file.exists():
            return f"ERROR: 图片文件不存在: {image_path}"
        data = base64.b64encode(image_file.read_bytes()).decode('utf-8')
        mime = _detect_mime(image_file.suffix)
        image_content = {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{data}'}}

    client = OpenAI(api_key=api_key, base_url=base_url)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{'role': 'user', 'content': [{'type': 'text', 'text': prompt}, image_content]}],
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"ERROR: {e}"


SCHEMA = {
    "type": "function",
    "function": {
        "name": "analyze_image",
        "description": "分析图片内容，支持本地图片和远程URL。使用OpenAI格式的多模态API（如MiMo、GPT-4o等）进行图片识别。",
        "parameters": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "图片路径（本地文件路径或http/https URL）"
                },
                "prompt": {
                    "type": "string",
                    "description": "分析提示词，默认为'描述这张图片的内容'"
                },
                "model": {
                    "type": "string",
                    "description": "模型名称（可选，默认使用配置中的模型）"
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "最大输出token数（可选，默认1500）"
                }
            },
            "required": ["image_path"]
        }
    }
}

HANDLERS = {"analyze_image": analyze_image}


def register():
    register_tool(SCHEMA, HANDLERS["analyze_image"])
