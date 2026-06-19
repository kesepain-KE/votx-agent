# -*- coding: utf-8 -*-
"""Embeddings Skill - 文本向量工具。"""

import json

from plugins._common import err, get_multimodal_context
from run.tool import register_tool


def embedding_create(input, encoding_format: str = "float", model: str = "") -> str:
    """生成文本嵌入。input 可以是字符串或字符串数组。"""
    ctx = get_multimodal_context()
    if not ctx or not ctx.get("provider"):
        return err("embedding_create: 缺少 provider 上下文，请重新进入会话")

    provider = ctx["provider"]
    if "embedding" not in provider.capabilities():
        return err("当前 provider 不支持文本嵌入 (embedding)。请配置 embedding_model 后再试。")

    if isinstance(input, str):
        texts = input
    elif isinstance(input, list) and all(isinstance(x, str) for x in input):
        texts = input
    else:
        return err("input 必须是字符串或字符串数组")

    try:
        result = provider.create_embeddings(texts=texts, encoding_format=encoding_format, model=model)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except NotImplementedError as e:
        return err(str(e))
    except Exception as e:
        return err(f"文本嵌入失败: {e}")


SCHEMA = {
    "type": "function",
    "function": {
        "name": "embedding_create",
        "description": "生成文本向量，适用于 RAG。需要 provider 支持 embedding 能力。",
        "parameters": {
            "type": "object",
            "properties": {
                "input": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}}
                    ],
                    "description": "待嵌入文本，支持字符串或字符串数组"
                },
                "encoding_format": {
                    "type": "string",
                    "enum": ["float", "base64"],
                    "description": "向量编码格式，默认 float"
                },
                "model": {
                    "type": "string",
                    "description": "可选模型 ID；留空使用 provider.embedding_model"
                }
            },
            "required": ["input"]
        }
    }
}


def register():
    register_tool(SCHEMA, embedding_create)
