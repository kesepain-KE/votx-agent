"""UAPI 热榜数据获取与处理"""
import json
import time
import urllib.request
import urllib.error

# UAPI 热榜 API 地址
UAPI_BASE = "https://uapi.run"

# 平台定义
AREA_PLATFORMS = {
    "video": [
        "bilibili", "douyin", "kuaishou", "zhihu",
        "weibo", "xiaohongshu", "baidu", "toutiao",
    ],
    "news": [
        "zhihu", "weibo", "baidu", "toutiao",
        "sina", "163", "sohu", "thepaper",
    ],
}

PLATFORM_LABELS = {
    "bilibili": "B站",
    "douyin": "抖音",
    "kuaishou": "快手",
    "zhihu": "知乎",
    "weibo": "微博",
    "xiaohongshu": "小红书",
    "baidu": "百度",
    "toutiao": "头条",
    "sina": "新浪",
    "163": "网易",
    "sohu": "搜狐",
    "thepaper": "澎湃",
}


def normalize_platforms(area: str, platforms_str: str) -> list[str]:
    """解析平台参数，返回标准化平台 ID 列表"""
    available = AREA_PLATFORMS.get(area, [])
    if not platforms_str.strip():
        return list(available)
    requested = [p.strip().lower() for p in platforms_str.split(",") if p.strip()]
    result = []
    for r in requested:
        # 先精确匹配 ID
        if r in available:
            result.append(r)
            continue
        # 再根据中文名匹配
        for pid, label in PLATFORM_LABELS.items():
            if r == label and pid in available:
                result.append(pid)
                break
    return result if result else list(available)


def fetch_hotboard(api_key: str, platform: str) -> dict:
    """从 UAPI 拉取指定平台热榜数据"""
    url = f"{UAPI_BASE}/hotboard/{platform}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("User-Agent", "votx-agent/1.0")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data if isinstance(data, dict) else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return {"error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        return {"error": str(e)}


def build_entries(platform: str, raw: dict, keywords: list[str], max_items: int) -> list[dict]:
    """从原始响应中提取热榜条目，支持关键词筛选"""
    if "error" in raw:
        return [{"title": f"[错误] {raw['error']}", "rank": 0, "platform": platform}]

    # 尝试从不同字段提取数据
    items = raw.get("data") or raw.get("items") or raw.get("list") or []
    if isinstance(items, dict):
        items = list(items.values())
    if not isinstance(items, list):
        return []

    entries = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("name") or item.get("word") or ""
        if not title:
            continue

        # 关键词筛选
        if keywords:
            title_lower = title.lower()
            if not any(kw.lower() in title_lower for kw in keywords):
                continue

        rank = item.get("rank") or item.get("index") or (i + 1)
        hot_score = item.get("hot") or item.get("score") or item.get("heat") or ""
        url = item.get("url") or item.get("link") or ""
        desc = item.get("description") or item.get("desc") or item.get("summary") or ""

        entries.append({
            "title": str(title),
            "rank": int(rank) if rank else i + 1,
            "hot": str(hot_score) if hot_score else "",
            "url": str(url) if url else "",
            "desc": str(desc)[:100] if desc else "",
            "platform": platform,
        })

        if len(entries) >= max_items:
            break

    return entries


def build_markdown(area: str, platforms: list[str], keywords: list[str], results: dict) -> str:
    """生成 Markdown 格式热榜报告"""
    area_label = "视频/社区" if area == "video" else "新闻资讯"
    lines = [
        f"# 全网热榜报告",
        f"**区域**: {area_label}",
        f"**生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    if keywords:
        lines.append(f"**关键词筛选**: {', '.join(keywords)}")
    lines.append("")

    for plat in platforms:
        label = PLATFORM_LABELS.get(plat, plat)
        entries = results.get(plat, [])
        lines.append(f"## {label} ({len(entries)} 条)")
        if not entries:
            lines.append("(无数据)\n")
            continue
        for e in entries:
            rank_str = f"#{e['rank']}" if e['rank'] else ""
            hot_str = f" 🔥{e['hot']}" if e['hot'] else ""
            url_str = f" [链接]({e['url']})" if e['url'] else ""
            lines.append(f"- {rank_str} **{e['title']}**{hot_str}{url_str}")
            if e.get('desc'):
                lines.append(f"  > {e['desc']}")
        lines.append("")

    return "\n".join(lines)
