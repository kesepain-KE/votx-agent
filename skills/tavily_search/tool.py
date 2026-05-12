"""Tavily 网络搜索工具"""
import os
from run.tool import register_tool
from skills._common import err, truncate

try:
    from tavily import TavilyClient
    HAS_TAVILY = True
except ImportError:
    HAS_TAVILY = False


def tavily_search(query: str, max_results: int = 5, search_depth: str = "basic") -> str:
    """使用 Tavily 搜索网络，返回结构化结果"""
    if not HAS_TAVILY:
        return err("tavily-python 未安装，请执行: pip install tavily-python")

    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        return err("缺少 TAVILY_API_KEY 环境变量。请在 .env 中添加 TAVILY_API_KEY=xxx")

    query = query.strip()
    if not query:
        return err("搜索关键词为空")

    max_results = min(max(max_results, 1), 10)
    if search_depth not in ("basic", "advanced"):
        search_depth = "basic"

    try:
        client = TavilyClient(api_key=api_key)
        result = client.search(
            query=query,
            max_results=max_results,
            search_depth=search_depth,
        )

        lines = [f"搜索: {query}"]
        lines.append(f"结果数: {len(result.get('results', []))}")
        answer = result.get("answer")
        if answer:
            lines.append(f"AI 摘要: {answer}")
        lines.append("")

        for i, r in enumerate(result.get("results", [])):
            title = r.get("title", "无标题")
            url = r.get("url", "")
            content = r.get("content", "")
            lines.append(f"{i+1}. **{title}**")
            if url:
                lines.append(f"   {url}")
            if content:
                lines.append(f"   {content[:300]}")

        return truncate("\n".join(lines))
    except Exception as e:
        return err(f"搜索失败: {e}")


SCHEMA = {
    "type": "function",
    "function": {
        "name": "tavily_search",
        "description": (
            "使用 Tavily API 搜索网络信息。适合查找最新新闻、实时数据、资料查询。"
            "返回结构化结果（标题、URL、摘要）。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "max_results": {"type": "integer", "description": "最多返回条数（1-10，默认 5）"},
                "search_depth": {"type": "string", "description": "搜索深度: basic（快速）或 advanced（深度）"},
            },
            "required": ["query"],
        },
    },
}


def register():
    register_tool(SCHEMA, tavily_search)
