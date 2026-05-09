"""UAPI 热榜查询工具 — Agent tool_call 接口 (v2)"""
import os
import sys
from run.tool import register_tool
from skills._common import err, truncate

_script_dir = os.path.dirname(__file__)
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from scripts.generate_uapi_hotboard_report import (
    fetch_hotboard,
    build_entries,
    build_markdown,
    normalize_platforms,
    AREA_PLATFORMS,
    PLATFORM_LABELS,
)


def query_hotboard(
    area: str = "news",
    platforms: str = "",
    keywords: str = "",
    max_items: int = 10,
) -> str:
    """查询全网热榜并返回 Markdown 报告"""
    area = area.strip().lower()
    if area not in ("video", "news", "tech"):
        return err(f"无效的 area: {area}。可选: video / news / tech")

    platform_list = normalize_platforms(area, platforms)
    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]

    api_key = os.environ.get("UAPI_API_KEY", "")
    results = {}
    errors = []

    for plat in platform_list:
        try:
            raw = fetch_hotboard(api_key, plat)
            results[plat] = build_entries(plat, raw, keyword_list, max_items)
        except Exception as e:
            errors.append(f"{plat}: {e}")
            results[plat] = [{"title": f"[错误] {e}", "rank": 0, "platform": plat}]

    md = build_markdown(area, platform_list, keyword_list, results)
    return truncate(md, 8000)


SCHEMA = {
    "type": "function",
    "function": {
        "name": "query_hotboard",
        "description": (
            "查询全网热榜。area: video(视频/社区平台)或news(新闻资讯平台)或tech(技术/开发者平台)。"
            "platforms: 逗号分隔平台名（如 知乎,微博,bilibili,百度），留空查全部。"
            "keywords: 逗号分隔关键词筛选，留空不筛选。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "area": {
                    "type": "string",
                    "description": "热榜区域: video（视频/社区平台）、news（新闻资讯平台）、tech（技术/开发者平台）",
                },
                "platforms": {
                    "type": "string",
                    "description": "逗号分隔的平台名，如 知乎,微博,百度。留空则查询该区域全部平台",
                },
                "keywords": {
                    "type": "string",
                    "description": "逗号分隔的关键词，只返回包含关键词的热搜条目。留空不筛选",
                },
                "max_items": {
                    "type": "integer",
                    "description": "每个平台最多返回条数，默认 10",
                },
            },
            "required": ["area"],
        },
    },
}


def register():
    register_tool(SCHEMA, query_hotboard)
