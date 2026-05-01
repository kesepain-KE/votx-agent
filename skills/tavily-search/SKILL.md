---
name: tavily-search
description: Tavily 网络搜索 — 专为 AI Agent 设计的搜索引擎，返回结构化结果（标题、URL、摘要）。当 Agent 需要搜索最新信息、查资料时使用。
compatibility: 需要 TAVILY_API_KEY 环境变量 + tavily-python (pip install tavily-python)
---

# Tavily 网络搜索

使用 Tavily API 进行网络搜索，返回结构化结果。

## 工具

| 工具 | 用途 |
|------|------|
| `tavily_search` | 搜索网络，返回标题/URL/摘要列表 |

## 参数说明

- **query**: 搜索关键词
- **max_results**: 最多返回条数（默认 5，上限 10）
- **search_depth**: `basic`（快速）或 `advanced`（深度搜索，较慢）

## 前置条件

需要 TAVILY_API_KEY 环境变量（在 .env 中配置）。
