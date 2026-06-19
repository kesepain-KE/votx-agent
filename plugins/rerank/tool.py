# -*- coding: utf-8 -*-
"""Rerank Skill - 文档重排工具。"""

import json

from plugins._common import err, get_multimodal_context
from run.tool import register_tool


def rerank_documents(
    query: str,
    documents: list[str],
    top_n: int = 0,
    return_documents: bool = True,
    model: str = "",
) -> str:
    """对候选文档重新排序。"""
    ctx = get_multimodal_context()
    if not ctx or not ctx.get("provider"):
        return err("rerank_documents: 缺少 provider 上下文，请重新进入会话")

    provider = ctx["provider"]
    if "rerank" not in provider.capabilities():
        return err("当前 provider 不支持文档重排 (rerank)。请配置 rerank_model 后再试。")

    if not query.strip():
        return err("query 不能为空")
    if not isinstance(documents, list) or not all(isinstance(x, str) for x in documents) or not documents:
        return err("documents 必须是非空字符串数组")

    try:
        result = provider.rerank_documents(
            query=query,
            documents=documents,
            top_n=top_n or None,
            return_documents=return_documents,
            model=model,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)
    except NotImplementedError as e:
        return err(str(e))
    except Exception as e:
        return err(f"文档重排失败: {e}")


SCHEMA = {
    "type": "function",
    "function": {
        "name": "rerank_documents",
        "description": "根据 query 对候选 documents 重新排序。需要 provider 支持 rerank 能力。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "查询语句"},
                "documents": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "候选文档数组"
                },
                "top_n": {"type": "integer", "description": "返回前 N 条，0 表示由 provider 决定"},
                "return_documents": {"type": "boolean", "description": "是否在结果中返回文档内容，默认 true"},
                "model": {"type": "string", "description": "可选模型 ID；留空使用 provider.rerank_model"}
            },
            "required": ["query", "documents"]
        }
    }
}


def register():
    register_tool(SCHEMA, rerank_documents)
