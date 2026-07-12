"""Tavily 网络搜索 / 提取 / 爬取 / 网站地图 / 深度研究 — 完整 Agent Skills。

基于 tavily-python SDK v0.7+，提供 5 个工具：
  tavily_search    — 网络搜索，返回结构化结果
  tavily_extract   — 提取 URL 正文（Markdown/纯文本）
  tavily_crawl     — 网站深度爬取 + 提取
  tavily_map       — 发现网站 URL 地图
  tavily_research  — AI 深度研究，多源收集→分析→生成带引用报告
"""
from __future__ import annotations

import os
from run.tool import register_tool
from plugins._common import err, truncate, get_effective_tool_timeout


try:
    from tavily import TavilyClient
    HAS_TAVILY = True
except ImportError:
    HAS_TAVILY = False

_SEARCH_DEPTHS = {"basic", "advanced", "fast", "ultra-fast"}
_TOPICS = {"general", "news", "finance"}
_TIME_RANGES = {"day", "week", "month", "year"}
_EXTRACT_DEPTHS = {"basic", "advanced"}
_FORMATS = {"markdown", "text"}
_MODELS = {"mini", "pro", "auto"}
_CITATION_FORMATS = {"numbered", "mla", "apa", "chicago"}
_RESULT_TRUNCATE = int(os.environ.get("TAVILY_RESULT_TRUNCATE", "0"))


def _tool_timeout(default: int) -> int:
    """读取统一工具超时配置，供 Tavily SDK 内部请求使用。"""
    return get_effective_tool_timeout(default)


def _get_client() -> TavilyClient:
    """获取 TavilyClient 实例（前置校验）。"""
    if not HAS_TAVILY:
        raise RuntimeError("tavily-python 未安装，请执行: pip install tavily-python")
    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("缺少 TAVILY_API_KEY 环境变量。请在 .env 中添加 TAVILY_API_KEY=xxx")
    return TavilyClient(api_key=api_key)


# ──────────────────────────── tavily_search ────────────────────────────

def tavily_search(
    query: str,
    search_depth: str = "basic",
    topic: str = "general",
    time_range: str = "",
    max_results: int = 5,
    include_domains: str = "",
    exclude_domains: str = "",
    include_answer: str = "basic",
    include_raw_content: str = "",
    include_images: bool = False,
    include_image_descriptions: bool = False,
    chunks_per_source: int = 0,
    days: int = 0,
    start_date: str = "",
    end_date: str = "",
    country: str = "",
    include_favicon: bool = False,
    auto_parameters: bool = False,
) -> str:
    """使用 Tavily API 搜索网络，返回结构化结果。

    支持基础/高级/快速/极速搜索，可按话题、时间范围、域名过滤、含 AI 摘要等。
    """
    query = (query or "").strip()
    if not query:
        return err("搜索关键词不能为空")

    try:
        client = _get_client()
    except RuntimeError as e:
        return err(str(e))

    # 构建参数
    kwargs: dict = {
        "query": query,
        "max_results": max(1, int(max_results)),
        "include_images": bool(include_images),
        "timeout": float(_tool_timeout(60)),
    }

    # search_depth: basic / advanced / fast / ultra-fast
    sd = (search_depth or "basic").strip().lower()
    if sd in _SEARCH_DEPTHS:
        kwargs["search_depth"] = sd

    if topic in _TOPICS:
        kwargs["topic"] = topic

    if time_range in _TIME_RANGES:
        kwargs["time_range"] = time_range

    # include_answer: True/False 或 "basic"/"advanced"
    ia = include_answer
    if isinstance(ia, bool):
        kwargs["include_answer"] = ia
    elif isinstance(ia, str) and ia.strip().lower() in ("basic", "advanced"):
        kwargs["include_answer"] = ia.strip().lower()
    elif isinstance(ia, str) and ia.strip().lower() in ("true", "1", "yes"):
        kwargs["include_answer"] = True
    elif isinstance(ia, str) and ia.strip().lower() in ("false", "0", "no", ""):
        kwargs["include_answer"] = False
    else:
        kwargs["include_answer"] = True

    # include_raw_content: True/False 或 "markdown"/"text"
    irc = include_raw_content
    if isinstance(irc, bool):
        kwargs["include_raw_content"] = irc
    elif isinstance(irc, str) and irc.strip().lower() in ("markdown", "text"):
        kwargs["include_raw_content"] = irc.strip().lower()
    elif isinstance(irc, str) and irc.strip().lower() in ("true", "1", "yes"):
        kwargs["include_raw_content"] = True
    elif isinstance(irc, str) and irc.strip().lower() in ("false", "0", "no", ""):
        kwargs["include_raw_content"] = False

    if include_image_descriptions:
        kwargs["include_image_descriptions"] = True

    if include_favicon:
        kwargs["include_favicon"] = True

    if auto_parameters:
        kwargs["auto_parameters"] = True

    # chunks_per_source: 仅 advanced 深度可用，范围 1-3
    cps = int(chunks_per_source) if chunks_per_source else 0
    if cps > 0 and kwargs.get("search_depth") == "advanced":
        kwargs["chunks_per_source"] = max(1, min(cps, 3))

    if days > 0:
        kwargs["days"] = int(days)

    start = (start_date or "").strip()
    end = (end_date or "").strip()
    if start:
        kwargs["start_date"] = start
    if end:
        kwargs["end_date"] = end

    country = (country or "").strip().lower()
    if country:
        kwargs["country"] = country

    def _parse_domains(raw: str) -> list[str] | None:
        raw = (raw or "").strip()
        if not raw:
            return None
        parts = [d.strip() for d in raw.replace(";", ",").split(",") if d.strip()]
        return parts if parts else None

    inc = _parse_domains(include_domains)
    if inc:
        kwargs["include_domains"] = inc
    exc = _parse_domains(exclude_domains)
    if exc:
        kwargs["exclude_domains"] = exc

    try:
        result = client.search(**kwargs)
    except Exception as e:
        return err(f"搜索失败: {e}")

    lines = [f"🔍 搜索: {query}"]
    lines.append(f"结果数: {len(result.get('results', []))}")

    # AI 摘要
    answer = result.get("answer")
    if answer:
        lines.append(f"\n📝 AI 摘要:\n{answer}")

    # 图片结果
    images = result.get("images", [])
    if images:
        lines.append(f"\n🖼️ 图片 ({len(images)} 张):")
        for img in images[:6]:
            desc = img.get("description", "") if isinstance(img, dict) else str(img)
            url = img.get("url", "") if isinstance(img, dict) else str(img)
            lines.append(f"  - {url}" + (f" — {desc}" if desc else ""))

    # 网页结果
    lines.append(f"\n📄 网页结果:" if images or answer else "\n📄 网页结果:")
    for i, r in enumerate(result.get("results", [])):
        title = r.get("title", "无标题")
        url = r.get("url", "")
        content = r.get("content", "")
        score = r.get("score")
        score_str = f" (相关度: {score:.2f})" if score is not None else ""
        lines.append(f"\n{i+1}. **{title}**{score_str}")
        if url:
            lines.append(f"   🔗 {url}")
        if content:
            lines.append(f"   {content[:2000]}")

    # token 用量
    usage = result.get("usage")
    if usage:
        lines.append(f"\n📊 Token: {usage}")

    return truncate("\n".join(lines), _RESULT_TRUNCATE)


# ──────────────────────────── tavily_extract ────────────────────────────

def tavily_extract(
    urls: str,
    query: str = "",
    extract_depth: str = "basic",
    format: str = "markdown",
    chunks_per_source: int = 0,
    include_images: bool = False,
    include_favicon: bool = False,
) -> str:
    """从指定 URL 提取正文，返回 Markdown 或纯文本。

    urls 可以是单个 URL 或多个 URL（逗号/换行分隔）。
    """
    urls = (urls or "").strip()
    if not urls:
        return err("URL 不能为空")

    # 支持逗号或换行分隔多个 URL
    urls_list = [u.strip() for u in urls.replace("\n", ",").split(",") if u.strip()]
    if not urls_list:
        return err("未解析到有效 URL")

    try:
        client = _get_client()
    except RuntimeError as e:
        return err(str(e))

    kwargs: dict = {}
    kwargs["urls"] = urls_list if len(urls_list) > 1 else urls_list[0]
    kwargs["timeout"] = float(_tool_timeout(30))

    if extract_depth in _EXTRACT_DEPTHS:
        kwargs["extract_depth"] = extract_depth
    if format in _FORMATS:
        kwargs["format"] = format
    if chunks_per_source > 0:
        kwargs["chunks_per_source"] = int(chunks_per_source)
    if include_images:
        kwargs["include_images"] = True
    if include_favicon:
        kwargs["include_favicon"] = True

    query = (query or "").strip()
    if query:
        kwargs["query"] = query

    try:
        result = client.extract(**kwargs)
    except Exception as e:
        return err(f"提取失败: {e}")

    # 检查失败
    failed = result.get("failed_results", [])
    success = result.get("results", [])
    lines = [f"📄 提取完成: {len(success)} 成功" + (f", {len(failed)} 失败" if failed else "")]

    for r in success:
        raw_url = r.get("url", "")
        title = r.get("title", "") or raw_url
        raw_content = r.get("raw_content", "")
        content_len = len(raw_content) if raw_content else 0
        lines.append(f"\n── {title} ({content_len} 字符) ──")
        if raw_content:
            lines.append(raw_content[:10000])

    for f in failed:
        lines.append(f"\n❌ 失败: {f.get('url', '?')} — {f.get('error', '未知错误')}")

    # token 用量
    usage = result.get("usage")
    if usage:
        lines.append(f"\n📊 Token: {usage}")

    return truncate("\n".join(lines), _RESULT_TRUNCATE)


# ──────────────────────────── tavily_crawl ────────────────────────────

def tavily_crawl(
    url: str,
    max_depth: int = 0,
    max_breadth: int = 0,
    limit: int = 0,
    instructions: str = "",
    select_paths: str = "",
    exclude_paths: str = "",
    select_domains: str = "",
    exclude_domains: str = "",
    allow_external: bool = False,
    extract_depth: str = "basic",
    format: str = "markdown",
    chunks_per_source: int = 0,
    include_images: bool = False,
    include_favicon: bool = False,
) -> str:
    """对指定网站进行深度爬取，沿链接发现并提取所有匹配页面的正文。

    适合「把整个文档站/知识库全部抓下来」的场景。
    """
    url = (url or "").strip()
    if not url:
        return err("URL 不能为空")

    try:
        client = _get_client()
    except RuntimeError as e:
        return err(str(e))

    kwargs: dict = {}
    kwargs["url"] = url
    kwargs["timeout"] = float(_tool_timeout(150))

    if max_depth > 0:
        kwargs["max_depth"] = int(max_depth)
    if max_breadth > 0:
        kwargs["max_breadth"] = int(max_breadth)
    if limit > 0:
        kwargs["limit"] = int(limit)

    instructions = (instructions or "").strip()
    if instructions:
        kwargs["instructions"] = instructions

    def _parse_paths(raw: str) -> list[str] | None:
        raw = (raw or "").strip()
        if not raw:
            return None
        return [p.strip() for p in raw.replace("\n", ",").split(",") if p.strip()]

    sel = _parse_paths(select_paths)
    if sel:
        kwargs["select_paths"] = sel
    exc = _parse_paths(exclude_paths)
    if exc:
        kwargs["exclude_paths"] = exc

    sel_d = _parse_paths(select_domains)
    if sel_d:
        kwargs["select_domains"] = sel_d
    exc_d = _parse_paths(exclude_domains)
    if exc_d:
        kwargs["exclude_domains"] = exc_d

    if allow_external:
        kwargs["allow_external"] = True

    if extract_depth in _EXTRACT_DEPTHS:
        kwargs["extract_depth"] = extract_depth
    if format in _FORMATS:
        kwargs["format"] = format
    if chunks_per_source > 0:
        kwargs["chunks_per_source"] = int(chunks_per_source)
    if include_images:
        kwargs["include_images"] = True
    if include_favicon:
        kwargs["include_favicon"] = True

    try:
        result = client.crawl(**kwargs)
    except Exception as e:
        return err(f"爬取失败: {e}")

    # 结果
    results = result.get("results", [])
    failed = result.get("failed_results", [])
    lines = [f"🕸️ 爬取: {url}"]
    lines.append(f"成功: {len(results)} 页" + (f", 失败: {len(failed)} 页" if failed else ""))

    # 按 source_url 分组展示
    for r in results:
        title = r.get("title", "") or r.get("url", "")
        source = r.get("url", "")
        raw_content = r.get("raw_content", "")
        content_len = len(raw_content) if raw_content else 0
        lines.append(f"\n── {title} ({content_len} 字符)")
        lines.append(f"   🔗 {source}")
        if raw_content:
            lines.append(raw_content[:10000])

    for f in failed:
        lines.append(f"\n❌ 失败: {f.get('url', '?')} — {f.get('error', '未知错误')}")

    # token 用量
    usage = result.get("usage")
    if usage:
        lines.append(f"\n📊 Token: {usage}")

    return truncate("\n".join(lines), _RESULT_TRUNCATE)


# ──────────────────────────── tavily_map ────────────────────────────

def tavily_map(
    url: str,
    max_depth: int = 0,
    max_breadth: int = 0,
    limit: int = 0,
    instructions: str = "",
    select_paths: str = "",
    exclude_paths: str = "",
    select_domains: str = "",
    exclude_domains: str = "",
    allow_external: bool = False,
    include_favicon: bool = False,
) -> str:
    """发现网站 URL 地图，列出站内所有可访问页面链接。

    适合「先看看这个网站有哪些页面，然后再决定抓哪些」的场景。
    常用于 crawl 之前的信息侦察。
    """
    url = (url or "").strip()
    if not url:
        return err("URL 不能为空")

    try:
        client = _get_client()
    except RuntimeError as e:
        return err(str(e))

    kwargs: dict = {}
    kwargs["url"] = url
    kwargs["timeout"] = float(_tool_timeout(150))

    if max_depth > 0:
        kwargs["max_depth"] = int(max_depth)
    if max_breadth > 0:
        kwargs["max_breadth"] = int(max_breadth)
    if limit > 0:
        kwargs["limit"] = int(limit)

    instructions = (instructions or "").strip()
    if instructions:
        kwargs["instructions"] = instructions

    def _parse_paths(raw: str) -> list[str] | None:
        raw = (raw or "").strip()
        if not raw:
            return None
        return [p.strip() for p in raw.replace("\n", ",").split(",") if p.strip()]

    sel = _parse_paths(select_paths)
    if sel:
        kwargs["select_paths"] = sel
    exc = _parse_paths(exclude_paths)
    if exc:
        kwargs["exclude_paths"] = exc

    sel_d = _parse_paths(select_domains)
    if sel_d:
        kwargs["select_domains"] = sel_d
    exc_d = _parse_paths(exclude_domains)
    if exc_d:
        kwargs["exclude_domains"] = exc_d

    if allow_external:
        kwargs["allow_external"] = True

    if include_favicon:
        kwargs["include_favicon"] = True

    try:
        result = client.map(**kwargs)
    except Exception as e:
        return err(f"网站地图生成失败: {e}")

    urls = result.get("results", [])
    lines = [f"🗺️ 网站地图: {url}"]
    lines.append(f"发现 {len(urls)} 个 URL\n")

    for i, u in enumerate(urls):
        lines.append(f"  {i+1}. {u}")

    # token 用量
    usage = result.get("usage")
    if usage:
        lines.append(f"\n📊 Token: {usage}")

    return truncate("\n".join(lines), _RESULT_TRUNCATE)


# ──────────────────────────── tavily_research ────────────────────────────

def tavily_research(
    input: str,
    model: str = "auto",
    citation_format: str = "numbered",
    output_schema: str = "",
    stream: bool = False,
) -> str:
    """AI 深度研究：收集多源资料 → 分析综合 → 生成带引用的报告。

    这是一个异步任务：提交后等待完成（最长 180 秒），完成后返回完整报告。
    适合需要多源交叉验证、深度分析的复杂问题。
    """
    input = (input or "").strip()
    if not input:
        return err("研究问题不能为空")

    try:
        client = _get_client()
    except RuntimeError as e:
        return err(str(e))

    if model not in _MODELS:
        model = "auto"
    if citation_format not in _CITATION_FORMATS:
        citation_format = "numbered"

    # 解析 output_schema JSON
    schema_obj = None
    output_schema = (output_schema or "").strip()
    if output_schema:
        import json as _json
        try:
            schema_obj = _json.loads(output_schema)
            if not isinstance(schema_obj, dict) or "properties" not in schema_obj:
                return err("output_schema 必须是包含 properties 字段的 JSON Schema 对象")
        except _json.JSONDecodeError as e:
            return err(f"output_schema 不是合法 JSON: {e}")

    max_wait = float(_tool_timeout(180))

    try:
        # 提交研究任务
        task_kwargs: dict = {
            "input": input,
            "model": model,
            "citation_format": citation_format,
            "stream": bool(stream),
            "timeout": max_wait,
        }
        if schema_obj:
            task_kwargs["output_schema"] = schema_obj
        task = client.research(**task_kwargs)
    except Exception as e:
        return err(f"研究任务提交失败: {e}")

    request_id = task.get("request_id", "")
    status = task.get("status", "")

    if stream:
        # 流式模式：task 本身就是 generator
        lines = [f"🔬 深度研究: {input}", f"模型: {model} | 状态: 进行中..."]
        try:
            # 流式消费
            for chunk in task:
                if isinstance(chunk, bytes):
                    lines.append(chunk.decode("utf-8", errors="replace"))
                elif isinstance(chunk, dict):
                    lines.append(str(chunk))
            return truncate("\n".join(lines), _RESULT_TRUNCATE)
        except Exception as e:
            return err(f"研究流式处理失败: {e}")

    # 轮询模式：等待完成
    import time as _time
    poll_interval = 2.0
    elapsed = 0.0

    while status not in ("completed", "failed", "cancelled"):
        if elapsed >= max_wait:
            return err(
                f"研究任务超时 ({max_wait}s)。当前状态: {status}。"
                f"可通过 request_id={request_id} 稍后查询。"
            )
        _time.sleep(poll_interval)
        elapsed += poll_interval
        try:
            result = client.get_research(request_id)
            status = result.get("status", status)
        except Exception as e:
            return err(f"查询研究状态失败: {e}")

    if status == "failed":
        return err(f"研究任务失败 (request_id={request_id})")
    if status == "cancelled":
        return err(f"研究任务已取消 (request_id={request_id})")

    # 任务完成，格式化输出
    content = result.get("content", "")
    sources = result.get("sources", [])
    lines = [f"🔬 深度研究: {input}"]
    lines.append(f"模型: {model} | 耗时: {elapsed:.0f}s\n")

    if content:
        lines.append(content)
    else:
        lines.append("(研究完成但未返回正文)")

    if sources:
        lines.append(f"\n📚 参考来源 ({len(sources)} 个):")
        for i, src in enumerate(sources):
            title = src.get("title", "") if isinstance(src, dict) else ""
            url = src.get("url", "") if isinstance(src, dict) else str(src)
            if title and url:
                lines.append(f"  [{i+1}] {title}: {url}")
            elif url:
                lines.append(f"  [{i+1}] {url}")
            else:
                lines.append(f"  [{i+1}] {title}")

    # token 用量
    usage = result.get("usage")
    if usage:
        lines.append(f"\n📊 Token: {usage}")

    return truncate("\n".join(lines), _RESULT_TRUNCATE)


# ──────────────────────────── 注册 ────────────────────────────

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "tavily_search",
            "description": (
                "使用 Tavily API 搜索网络，返回结构化结果（标题、URL、摘要、AI 回答、相关度评分）。"
                "支持话题过滤、时间范围、域名白名单/黑名单、图片搜索等。"
                "当需要搜索最新新闻、实时数据、事实核查、查找资料、技术调研、查最新信息、获取网页结果时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词（必填），不超过 400 字符"},
                    "search_depth": {
                        "type": "string",
                        "enum": ["basic", "advanced", "fast", "ultra-fast"],
                        "description": "搜索深度：ultra-fast 极速、fast 快速、basic 通用（默认）、advanced 深度高召回",
                    },
                    "topic": {
                        "type": "string",
                        "enum": ["general", "news", "finance"],
                        "description": "话题分类：general 通用，news 新闻，finance 财经。默认 general",
                    },
                    "time_range": {
                        "type": "string",
                        "enum": ["day", "week", "month", "year"],
                        "description": "时间范围（相对）：day/week/month/year。与 start_date/end_date 互斥",
                    },
                    "start_date": {"type": "string", "description": "起始日期 YYYY-MM-DD（需与 end_date 配合）"},
                    "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD（需与 start_date 配合）"},
                    "days": {"type": "integer", "description": "搜索最近 N 天的内容"},
                    "max_results": {"type": "integer", "description": "最多返回条数（默认 5）"},
                    "chunks_per_source": {
                        "type": "integer",
                        "description": "每源内容片段数（1-3，仅 advanced 深度可用，每段 ≤500 字符）。0=不使用",
                    },
                    "include_domains": {
                        "type": "string",
                        "description": "限定来源域名（≤300 个），多个用逗号分隔，如 github.com,stackoverflow.com",
                    },
                    "exclude_domains": {
                        "type": "string",
                        "description": "排除指定域名（≤150 个），多个用逗号分隔",
                    },
                    "include_answer": {
                        "type": "string",
                        "description": "AI 摘要：true/false 或 basic/advanced。默认 basic（true=开启，false=关闭，advanced=深度摘要）",
                    },
                    "include_raw_content": {
                        "type": "string",
                        "description": "页面原始正文：true/false 或 markdown/text。默认 false（不包含）",
                    },
                    "include_images": {
                        "type": "boolean",
                        "description": "是否包含相关图片结果。默认 false",
                    },
                    "include_image_descriptions": {
                        "type": "boolean",
                        "description": "是否包含图片的文字描述。默认 false",
                    },
                    "auto_parameters": {
                        "type": "boolean",
                        "description": "是否让 API 根据查询自动调优参数。默认 false",
                    },
                    "country": {
                        "type": "string",
                        "description": "限定来源国家/地区代码（小写），如 cn、us、jp。仅 general 话题可用",
                    },
                    "include_favicon": {
                        "type": "boolean",
                        "description": "是否包含网站图标 URL。默认 false",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tavily_extract",
            "description": (
                "从指定 URL 提取正文内容，返回 Markdown 或纯文本。"
                "支持单 URL 或多 URL（逗号/换行分隔）。"
                "当需要读取网页全文、获取文章完整内容、提取文档正文、读取在线文档时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "string",
                        "description": "要提取的 URL，支持多个（逗号或换行分隔）",
                    },
                    "query": {
                        "type": "string",
                        "description": "对提取内容进行聚焦查询，提取与问题相关的片段",
                    },
                    "extract_depth": {
                        "type": "string",
                        "enum": ["basic", "advanced"],
                        "description": "提取深度：basic 快速（默认），advanced 更深层抓取",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["markdown", "text"],
                        "description": "输出格式：markdown（默认）或 text 纯文本",
                    },
                    "chunks_per_source": {
                        "type": "integer",
                        "description": "每源返回的内容块数。0 表示自动。可选",
                    },
                    "include_images": {
                        "type": "boolean",
                        "description": "是否包含页面图片。默认 false",
                    },
                    "include_favicon": {
                        "type": "boolean",
                        "description": "是否包含网站图标 URL。默认 false",
                    },
                },
                "required": ["urls"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tavily_crawl",
            "description": (
                "对指定网站进行深度爬取，沿链接自动发现并提取所有匹配页面的正文。"
                "支持路径过滤、深度/数量限制、自定义指令。"
                "当需要抓取整个文档站、知识库、博客、教程系列等整站内容时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "爬取起始 URL（必填）"},
                    "max_depth": {
                        "type": "integer",
                        "description": "最大爬取深度。0 表示不限制。默认自动",
                    },
                    "max_breadth": {
                        "type": "integer",
                        "description": "每层最多爬取的页面数。0 表示不限制。默认自动",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最多爬取页面数。0 表示不限制。默认自动",
                    },
                    "instructions": {
                        "type": "string",
                        "description": "自然语言指令，描述爬取目标和内容过滤规则。如「只抓 API 文档」「提取所有教程」",
                    },
                    "select_paths": {
                        "type": "string",
                        "description": "限定路径模式（glob），多个用逗号分隔。如 /docs/**,/api/**",
                    },
                    "exclude_paths": {
                        "type": "string",
                        "description": "排除路径模式（glob），多个用逗号分隔。如 /blog/**,/changelog/**",
                    },
                    "select_domains": {
                        "type": "string",
                        "description": "限定域名，多个用逗号分隔。只爬取这些域名下的页面",
                    },
                    "exclude_domains": {
                        "type": "string",
                        "description": "排除域名，多个用逗号分隔。不爬取这些域名",
                    },
                    "allow_external": {
                        "type": "boolean",
                        "description": "是否允许爬取外部域名。默认 false（仅同域）",
                    },
                    "extract_depth": {
                        "type": "string",
                        "enum": ["basic", "advanced"],
                        "description": "提取深度：basic 快速，advanced 更深层。默认 basic",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["markdown", "text"],
                        "description": "输出格式：markdown（默认）或 text 纯文本",
                    },
                    "chunks_per_source": {
                        "type": "integer",
                        "description": "每源返回的内容块数。0 表示自动",
                    },
                    "include_images": {
                        "type": "boolean",
                        "description": "是否包含页面图片。默认 false",
                    },
                    "include_favicon": {
                        "type": "boolean",
                        "description": "是否包含网站图标 URL。默认 false",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tavily_map",
            "description": (
                "发现并列出网站所有可访问的页面 URL。"
                "支持路径过滤和深度限制。"
                "当需要先了解一个网站有哪些页面、做信息侦察、规划爬取策略时使用。"
                "通常先 map 发现 URL，再 extract/crawl 抓取内容。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要发现 URL 的网站地址（必填）"},
                    "max_depth": {
                        "type": "integer",
                        "description": "最大扫描深度。0 表示不限制。默认自动",
                    },
                    "max_breadth": {
                        "type": "integer",
                        "description": "每层最多扫描的页面数。0 表示不限制。默认自动",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最多发现的 URL 数。0 表示不限制。默认自动",
                    },
                    "instructions": {
                        "type": "string",
                        "description": "自然语言指令，描述要发现的目标页面。如「只列出 API 文档页面」",
                    },
                    "select_paths": {
                        "type": "string",
                        "description": "限定路径模式（glob），多个用逗号分隔。如 /docs/**,/reference/**",
                    },
                    "exclude_paths": {
                        "type": "string",
                        "description": "排除路径模式（glob），多个用逗号分隔。如 /assets/**,/cdn/**",
                    },
                    "select_domains": {
                        "type": "string",
                        "description": "限定域名，多个用逗号分隔。只发现这些域名下的 URL",
                    },
                    "exclude_domains": {
                        "type": "string",
                        "description": "排除域名，多个用逗号分隔。不发现这些域名",
                    },
                    "allow_external": {
                        "type": "boolean",
                        "description": "是否允许发现外部域名。默认 false（仅同域）",
                    },
                    "include_favicon": {
                        "type": "boolean",
                        "description": "是否包含网站图标 URL。默认 false",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tavily_research",
            "description": (
                "AI 深度研究：提交一个研究课题，Tavily 自动收集多源资料、分析综合、生成带完整引用的报告。"
                "这是一个异步任务，可能需要 30-180 秒。"
                "当需要多源交叉验证、竞品分析、行业调研、深度对比、综合分析等复杂研究时使用。"
                "支持结构化输出（output_schema），可要求返回 JSON 格式的结构化数据。"
                "不要用于简单搜索——简单搜索请用 tavily_search。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "input": {
                        "type": "string",
                        "description": "研究课题或问题（必填）。越具体越好，如「2025 年 AI Agent 框架对比分析」",
                    },
                    "model": {
                        "type": "string",
                        "enum": ["mini", "pro", "auto"],
                        "description": "研究模型：mini 快速（~30s，简单问题）、pro 深度（~60-120s，多角度复杂问题）、auto 自动选择。默认 auto",
                    },
                    "citation_format": {
                        "type": "string",
                        "enum": ["numbered", "mla", "apa", "chicago"],
                        "description": "引用格式。默认 numbered（数字编号）",
                    },
                    "output_schema": {
                        "type": "string",
                        "description": (
                            "结构化输出 JSON Schema（JSON 字符串）。"
                            "必须包含 properties 字段。如：{\"type\":\"object\",\"properties\":{\"name\":{\"type\":\"string\"}},\"required\":[\"name\"]}。"
                            "不传则返回 Markdown 格式的自由文本报告"
                        ),
                    },
                    "stream": {
                        "type": "boolean",
                        "description": "是否流式返回研究进度。默认 false（等待完成后一次性返回）",
                    },
                },
                "required": ["input"],
            },
        },
    },
]

HANDLERS = {
    "tavily_search": tavily_search,
    "tavily_extract": tavily_extract,
    "tavily_crawl": tavily_crawl,
    "tavily_map": tavily_map,
    "tavily_research": tavily_research,
}


def register():
    """注册所有 Tavily 工具。"""
    for schema in SCHEMAS:
        name = schema["function"]["name"]
        register_tool(schema, HANDLERS[name])
