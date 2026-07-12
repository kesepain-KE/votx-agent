---
name: tavily_search
description: Tavily 网络搜索 — 专为 AI Agent 设计的搜索引擎，提供 search/extract/crawl/map/research 五个工具。当 Agent 需要搜索最新信息、提取网页正文、爬取网站、发现站点 URL、深度研究时使用。
version: "1.1"
category: search
enabled: true
tags: ["search", "tavily", "web", "research"]
compatibility: "需要 TAVILY_API_KEY 环境变量 + tavily-python>=0.7.0 (pip install tavily-python)"
---

# Tavily 网络搜索与内容提取 (Tavily Search)

基于 [Tavily API](https://docs.tavily.com/) 的完整 Agent Skills 实现，提供 5 个工具。

## 插件路径

`plugins/tavily_search/`

## 注册工具

| 工具 | 用途 | 典型场景 |
|------|------|---------|
| `tavily_search` | 网络搜索，返回标题/URL/摘要/AI 回答/相关度 | 查资料、找最新信息、事实核查 |
| `tavily_extract` | 提取指定 URL 正文（Markdown/纯文本） | 读取网页全文、获取文档完整内容 |
| `tavily_crawl` | 网站深度爬取，沿链接发现并提取所有匹配页面 | 抓取文档站、知识库、整站归档 |
| `tavily_map` | 发现网站 URL 地图，列出所有可访问页面 | 信息侦察：先看有哪些页面，再决定抓哪些 |
| `tavily_research` | AI 深度研究，多源收集→分析→生成带引用报告 | 竞品分析、行业调研、需要多源交叉验证的复杂问题 |

## 推荐工作流

```text
tavily_search  → 找到目标页面 → tavily_extract（全文提取）
tavily_map     → 了解站点结构 → tavily_crawl（批量爬取）
简单问题 → tavily_search    |    复杂问题 → tavily_research（30~180s）
```

## 参数详解

### 1. tavily_search

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `query` | string | 是 | — | 搜索关键词，不超过 400 字符 |
| `search_depth` | enum | 否 | `basic` | `basic`（通用）/ `advanced`（深度高召回）/ `fast`（快速）/ `ultra-fast`（极速） |
| `topic` | enum | 否 | `general` | `general`（通用）/ `news`（新闻）/ `finance`（财经） |
| `time_range` | enum | 否 | — | `day` / `week` / `month` / `year`（相对时间） |
| `start_date` | string | 否 | — | 起始日期 `YYYY-MM-DD`（需与 `end_date` 配合） |
| `end_date` | string | 否 | — | 结束日期 `YYYY-MM-DD` |
| `days` | int | 否 | 0 | 搜索最近 N 天 |
| `max_results` | int | 否 | 5 | 最多返回条数（1-20） |
| `chunks_per_source` | int | 否 | 0 | 每源内容片段数（1-3，仅 `advanced` 可用） |
| `include_domains` | string | 否 | — | 限定来源域名，逗号分隔 |
| `exclude_domains` | string | 否 | — | 排除域名，逗号分隔 |
| `include_answer` | string | 否 | `basic` | AI 摘要：`true`/`false` 或 `basic`/`advanced` |
| `include_raw_content` | string | 否 | `false` | 页面原始正文：`true`/`false` 或 `markdown`/`text` |
| `include_images` | bool | 否 | false | 是否含图片结果 |
| `country` | string | 否 | — | 限定来源国家代码（`cn`/`us`/`jp` 等） |
| `auto_parameters` | bool | 否 | false | 是否自动调优参数 |

### 2. tavily_extract

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `urls` | string | 是 | — | 单 URL 或多 URL（逗号/换行分隔） |
| `query` | string | 否 | — | 聚焦查询，只提取相关内容片段 |
| `extract_depth` | enum | 否 | `basic` | `basic`（快速）/ `advanced`（深层抓取） |
| `format` | enum | 否 | `markdown` | `markdown` / `text` |
| `chunks_per_source` | int | 否 | 0 | 每源内容块数，0 为自动 |
| `include_images` | bool | 否 | false | 是否包含页面图片 |

### 3. tavily_crawl

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `url` | string | 是 | — | 爬取起始 URL |
| `max_depth` | int | 否 | 0 | 最大爬取深度，0=不限制 |
| `max_breadth` | int | 否 | 0 | 每层最多爬取页面数 |
| `limit` | int | 否 | 0 | 最多爬取页面数 |
| `instructions` | string | 否 | — | 自然语言指令 |
| `select_paths` | string | 否 | — | 路径 glob 白名单，逗号分隔 |
| `exclude_paths` | string | 否 | — | 路径 glob 黑名单，逗号分隔 |
| `allow_external` | bool | 否 | false | 是否允许爬取外部域名 |
| `extract_depth` | enum | 否 | `basic` | `basic` / `advanced` |
| `format` | enum | 否 | `markdown` | `markdown` / `text` |

### 4. tavily_map

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `url` | string | 是 | — | 网站地址 |
| `max_depth` | int | 否 | 0 | 最大扫描深度 |
| `limit` | int | 否 | 0 | 最多发现的 URL 数 |
| `instructions` | string | 否 | — | 自然语言指令 |
| `select_paths` | string | 否 | — | 路径 glob 白名单 |
| `exclude_paths` | string | 否 | — | 路径 glob 黑名单 |
| `allow_external` | bool | 否 | false | 是否允许发现外部域名 |

### 5. tavily_research

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `input` | string | 是 | — | 研究课题或问题，越具体越好 |
| `model` | enum | 否 | `auto` | `mini`（~30s）/ `pro`（~60-120s）/ `auto`（自动选择） |
| `citation_format` | enum | 否 | `numbered` | `numbered` / `mla` / `apa` / `chicago` |
| `output_schema` | string | 否 | — | 结构化输出 JSON Schema（JSON 字符串），必须含 `properties` 字段 |
| `stream` | bool | 否 | false | 是否流式返回进度 |

## 结果说明

| 工具 | 成功返回 |
|------|----------|
| `tavily_search` | 搜索结果数 + AI 摘要 + 网页结果列表（标题/URL/摘要/相关度） |
| `tavily_extract` | 成功/失败计数 + 各 URL 正文内容 |
| `tavily_crawl` | 成功/失败计数 + 各页面正文内容 |
| `tavily_map` | 发现的 URL 数量 + URL 列表 |
| `tavily_research` | 研究报告正文 + 参考来源列表 + Token 用量 |

## 前置条件

```bash
pip install tavily-python
```

在 `.env` 中配置：

```env
TAVILY_API_KEY=tvly-xxx
```

获取 API Key: https://app.tavily.com

## 常见规范

- 简单搜索用 `tavily_search`，不要用 `tavily_research`（后者耗时 30-180 秒）
- 整站爬取前先用 `tavily_map` 了解结构，再用 `tavily_crawl` 精准爬取
- `include_domains` 和 `exclude_domains` 用逗号分隔多个域名
- `time_range` 与 `start_date`/`end_date` 互斥，不要同时使用

## 常见处理办法

- **API Key 缺失**：检查 `.env` 中的 `TAVILY_API_KEY` 配置
- **tavily-python 未安装**：执行 `pip install tavily-python`
- **搜索结果不相关**：尝试 `search_depth="advanced"` 或添加 `include_domains` 限定来源
- **研究任务超时**：增加 `tool.tool_timeout` 配置值，或使用 `model="mini"` 减少耗时
- **crawl 结果过多**：设置 `limit` 和 `max_depth` 控制爬取范围

## 常见教训

- `tavily_research` 是异步任务，不能用于简单搜索
- `output_schema` 必须是包含 `properties` 字段的 JSON Schema 对象，否则报错
- `time_range` 和 `start_date`/`end_date` 互斥，同时传入会冲突
- `chunks_per_source` 仅在 `advanced` 深度下生效，`basic` 深度下无效
- `country` 参数仅 `general` 话题可用，`news`/`finance` 话题忽略此参数