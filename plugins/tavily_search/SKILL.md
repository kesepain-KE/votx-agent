---
name: tavily_search
description: Tavily 网络搜索 — 专为 AI Agent 设计的搜索引擎，提供 search/extract/crawl/map/research 五个工具。当 Agent 需要搜索最新信息、提取网页正文、爬取网站、发现站点 URL、深度研究时使用。
compatibility: 需要 TAVILY_API_KEY 环境变量 + tavily-python>=0.7.0 (pip install tavily-python)
---

# Tavily 网络搜索与内容提取

基于 [Tavily API](https://docs.tavily.com/) 的完整 Agent Skills 实现，提供 5 个工具：

## 工具

| 工具 | 用途 | 典型场景 |
|------|------|---------|
| `tavily_search` | 网络搜索，返回标题/URL/摘要/AI 回答/相关度 | 查资料、找最新信息、事实核查 |
| `tavily_extract` | 提取指定 URL 正文（Markdown/纯文本） | 读取网页全文、获取文档完整内容 |
| `tavily_crawl` | 网站深度爬取，沿链接发现并提取所有匹配页面 | 抓取文档站、知识库、整站归档 |
| `tavily_map` | 发现网站 URL 地图，列出所有可访问页面 | 信息侦察：先看有哪些页面，再决定抓哪些 |
| `tavily_research` | AI 深度研究，多源收集→分析→生成带引用报告 | 竞品分析、行业调研、需要多源交叉验证的复杂问题 |

## 推荐工作流

```
tavily_search  → 找到目标页面 → tavily_extract（全文提取）
tavily_map     → 了解站点结构 → tavily_crawl（批量爬取）
简单问题 → tavily_search    |    复杂问题 → tavily_research（30~180s）
```

## 工具详细说明

### 1. tavily_search — 网络搜索

```
tavily_search(query="2025 年 AI 发展", search_depth="advanced", topic="news", time_range="month")
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `query` | string | **必填**，搜索关键词 |
| `search_depth` | enum | `basic`（通用）/ `advanced`（深度高召回）/ `fast`（快速）/ `ultra-fast`（极速） |
| `topic` | enum | `general`（通用）/ `news`（新闻）/ `finance`（财经） |
| `time_range` | enum | `day` / `week` / `month` / `year`（相对时间） |
| `start_date` | string | 起始日期 `YYYY-MM-DD`（需与 `end_date` 配合） |
| `end_date` | string | 结束日期 `YYYY-MM-DD` |
| `days` | int | 搜索最近 N 天 |
| `max_results` | int | 1-20，默认 5 |
| `chunks_per_source` | int | 每源内容片段数（1-3，仅 `advanced` 深度可用，每段 ≤500 字符） |
| `include_domains` | string | 限定来源域名（≤300 个），逗号分隔（如 `github.com,stackoverflow.com`） |
| `exclude_domains` | string | 排除域名（≤150 个），逗号分隔 |
| `include_answer` | string | AI 摘要：`true`/`false` 或 `basic`/`advanced`。默认 `basic` |
| `include_raw_content` | string | 页面原始正文：`true`/`false` 或 `markdown`/`text`。默认 `false` |
| `include_images` | bool | 是否含图片结果，默认 false |
| `include_image_descriptions` | bool | 是否含图片文字描述，默认 false |
| `auto_parameters` | bool | 是否让 API 根据查询自动调优参数，默认 false |
| `country` | string | 限定来源国家/地区代码（`cn`/`us`/`jp` 等） |
| `include_favicon` | bool | 是否含网站图标 URL，默认 false |

### 2. tavily_extract — URL 正文提取

```
tavily_extract(urls="https://example.com/article", format="markdown", extract_depth="advanced")
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `urls` | string | **必填**，单 URL 或多 URL（逗号/换行分隔） |
| `query` | string | 聚焦查询，只提取相关内容片段 |
| `extract_depth` | enum | `basic`（快速）/ `advanced`（深层抓取） |
| `format` | enum | `markdown` / `text` |
| `chunks_per_source` | int | 每源内容块数，0 为自动 |
| `include_images` | bool | 是否包含页面图片 |
| `include_favicon` | bool | 是否包含网站图标 URL |

### 3. tavily_crawl — 网站爬取

```
tavily_crawl(url="https://docs.example.com", instructions="只抓 API 参考文档", select_paths="/api/**,/reference/**", max_depth=3)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `url` | string | **必填**，爬取起始 URL |
| `max_depth` | int | 最大爬取深度，0=不限制 |
| `max_breadth` | int | 每层最多爬取页面数，0=不限制 |
| `limit` | int | 最多爬取页面数，0=不限制 |
| `instructions` | string | 自然语言指令，描述爬取目标 |
| `select_paths` | string | 路径 glob 白名单，逗号分隔（如 `/docs/**`） |
| `exclude_paths` | string | 路径 glob 黑名单，逗号分隔 |
| `select_domains` | string | 限定域名白名单，逗号分隔 |
| `exclude_domains` | string | 排除域名黑名单，逗号分隔 |
| `allow_external` | bool | 是否允许爬取外部域名，默认 false |
| `extract_depth` | enum | `basic` / `advanced` |
| `format` | enum | `markdown` / `text` |
| `chunks_per_source` | int | 每源内容块数，0 为自动 |
| `include_images` | bool | 是否包含页面图片 |
| `include_favicon` | bool | 是否包含网站图标 URL |

### 4. tavily_map — 网站 URL 发现

```
tavily_map(url="https://docs.example.com", select_paths="/docs/**", limit=500)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `url` | string | **必填**，网站地址 |
| `max_depth` | int | 最大扫描深度，0=不限制 |
| `max_breadth` | int | 每层最多扫描页面数，0=不限制 |
| `limit` | int | 最多发现的 URL 数，0=不限制 |
| `instructions` | string | 自然语言指令，描述要发现的目标 |
| `select_paths` | string | 路径 glob 白名单，逗号分隔 |
| `exclude_paths` | string | 路径 glob 黑名单，逗号分隔 |
| `select_domains` | string | 限定域名白名单，逗号分隔 |
| `exclude_domains` | string | 排除域名黑名单，逗号分隔 |
| `allow_external` | bool | 是否允许发现外部域名，默认 false |
| `include_favicon` | bool | 是否包含网站图标 URL |

### 5. tavily_research — AI 深度研究

```
tavily_research(input="2025 年 AI Agent 框架对比分析", model="pro", citation_format="numbered")
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `input` | string | **必填**，研究课题或问题，越具体越好 |
| `model` | enum | `mini`（~30s，简单问题）/ `pro`（~60-120s，复杂多角度）/ `auto`（自动选择） |
| `citation_format` | enum | 引用格式：`numbered` / `mla` / `apa` / `chicago` |
| `output_schema` | string | 结构化输出 JSON Schema（JSON 字符串）。必须含 `properties` 字段。不传则返回 Markdown 报告 |
| `stream` | bool | 是否流式返回进度，默认 false（等待完成后一次性返回） |

> **注意**：这是一个异步任务，可能需要 30-180 秒。不要用于简单搜索——简单搜索请用 `tavily_search`。

## 前置条件

```text
pip install tavily-python
```

在 `.env` 中配置：

```env
TAVILY_API_KEY=tvly-xxx
```

获取 API Key: https://app.tavily.com

## 超时与截断

- 工具内部超时遵循统一优先级：`用户 config.json > config_core.json > SDK 默认值`
- `TAVILY_RESULT_TRUNCATE` 环境变量控制返回文本截断长度，默认 6000 字符

## Schema 参考

- Tavily Agent Skills: https://docs.tavily.com/documentation/agent-skills
- Tavily Python SDK: https://github.com/tavily-ai/tavily-python
