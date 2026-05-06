"""UAPI 热榜数据获取与处理 (v2 - uapis.cn)"""
import json
import time
import urllib.request
import urllib.error

# UAPI 热榜 API 地址
UAPI_BASE = "https://uapis.cn"
HOTBOARD_URL = f"{UAPI_BASE}/api/v1/misc/hotboard"

# 平台定义（基于 uapis.cn 最新接口）
AREA_PLATFORMS = {
    "video": [
        "bilibili", "acfun", "douyin", "kuaishou",
        "douban-movie", "douban-group",
        "lol", "genshin", "honkai", "starrail",
        "netease-music", "qq-music",
    ],
    "news": [
        "weibo", "zhihu", "zhihu-daily", "baidu", "toutiao",
        "thepaper", "sina", "sina-news", "qq-news", "netease-news",
    ],
    "tech": [
        "v2ex", "hupu", "ngabbs", "52pojie", "hostloc", "coolapk",
        "huxiu", "ifanr", "sspai", "ithome", "ithome-xijiayi",
        "juejin", "jianshu", "guokr", "36kr", "51cto", "csdn",
        "nodeseek", "hellogithub",
    ],
}

PLATFORM_LABELS = {
    "bilibili": "B站",
    "acfun": "A站",
    "douyin": "抖音",
    "kuaishou": "快手",
    "douban-movie": "豆瓣电影",
    "douban-group": "豆瓣小组",
    "lol": "英雄联盟",
    "genshin": "原神",
    "honkai": "崩坏3",
    "starrail": "星穹铁道",
    "netease-music": "网易云音乐",
    "qq-music": "QQ音乐",
    "weibo": "微博",
    "zhihu": "知乎",
    "zhihu-daily": "知乎日报",
    "baidu": "百度",
    "toutiao": "头条",
    "thepaper": "澎湃",
    "sina": "新浪",
    "sina-news": "新浪新闻",
    "qq-news": "腾讯新闻",
    "netease-news": "网易新闻",
    "v2ex": "V2EX",
    "hupu": "虎扑",
    "ngabbs": "NGA",
    "52pojie": "吾爱破解",
    "hostloc": "全球主机",
    "coolapk": "酷安",
    "huxiu": "虎嗅",
    "ifanr": "爱范儿",
    "sspai": "少数派",
    "ithome": "IT之家",
    "ithome-xijiayi": "IT之家喜加一",
    "juejin": "掘金",
    "jianshu": "简书",
    "guokr": "果壳",
    "36kr": "36氪",
    "51cto": "51CTO",
    "csdn": "CSDN",
    "nodeseek": "NodeSeek",
    "hellogithub": "HelloGitHub",
    "tieba": "贴吧",
    "weread": "微信读书",
    "weatheralarm": "天气预警",
    "earthquake": "地震速报",
    "history": "历史上的今天",
}

ALL_PLATFORMS = []
for _plats in AREA_PLATFORMS.values():
    ALL_PLATFORMS.extend(_plats)
ALL_PLATFORMS = list(dict.fromkeys(ALL_PLATFORMS))


def normalize_platforms(area: str, platforms_str: str) -> list[str]:
    """解析平台参数，返回标准化平台 ID 列表"""
    available = AREA_PLATFORMS.get(area, ALL_PLATFORMS)
    if not platforms_str.strip():
        return list(available)
    requested = [p.strip().lower() for p in platforms_str.split(",") if p.strip()]
    result = []
    for r in requested:
        if r in available:
            result.append(r)
            continue
        for pid, label in PLATFORM_LABELS.items():
            if r == label and pid in available:
                result.append(pid)
                break
    return result if result else list(available)


def fetch_hotboard(api_key: str, platform: str, keyword: str = "",
                   time_start: int = 0, time_end: int = 0) -> dict:
    """从 UAPI (uapis.cn) 拉取指定平台热榜数据"""
    params = f"?type={platform}"
    if keyword:
        from urllib.parse import quote
        params += f"&keyword={quote(keyword)}"
    if time_start:
        params += f"&time_start={time_start}"
    if time_end:
        params += f"&time_end={time_end}"

    url = f"{HOTBOARD_URL}{params}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "votx-agent/1.0")
    if api_key:
        req.add_header("X-API-Key", api_key)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data if isinstance(data, dict) else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return {"error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        return {"error": str(e)}


def build_entries(platform: str, raw: dict, keywords: list[str],
                  max_items: int) -> list[dict]:
    """从 UAPI v2 响应提取热榜条目"""
    if "error" in raw:
        return [{"title": f"[错误] {raw['error']}", "rank": 0, "hot": "",
                 "url": "", "desc": "", "platform": platform}]

    items = raw.get("list") or raw.get("results") or raw.get("data") or []
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

        if keywords:
            title_lower = title.lower()
            if not any(kw.lower() in title_lower for kw in keywords):
                continue

        rank = item.get("index") or item.get("rank") or (i + 1)
        hot_score = item.get("hot_value") or item.get("hot") or item.get("score") or ""
        url = item.get("url") or item.get("link") or ""
        desc = item.get("description") or item.get("desc") or ""

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


def build_markdown(area: str, platforms: list[str], keywords: list[str],
                   results: dict) -> str:
    """生成 Markdown 格式热榜报告"""
    area_labels = {"video": "视频/社区", "news": "新闻资讯", "tech": "技术/开发者"}
    area_label = area_labels.get(area, area)
    lines = [
        "# 全网热榜报告",
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
            rank_str = f"#{e.get('rank', '')}" if e.get('rank') else ""
            hot_str = f" [热{e.get('hot', '')}]" if e.get('hot') else ""
            url_str = f" [链接]({e.get('url', '')})" if e.get('url') else ""
            lines.append(f"- {rank_str} **{e.get('title', '')}**{hot_str}{url_str}")
            if e.get('desc'):
                lines.append(f"  > {e.get('desc', '')}")
        lines.append("")

    return "\n".join(lines)
