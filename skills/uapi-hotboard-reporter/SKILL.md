---
name: uapi-hotboard-reporter
description: UAPI 全网热榜查询 — 抓取多平台热搜并生成报告。支持视频区和新闻区，可按平台和关键词筛选。Agent 查询热搜、热榜、热点话题时使用。
---

# UAPI 热榜查询

通过 UAPI 接口查询全网多平台热榜数据。

## 工具

| 工具 | 用途 |
|------|------|
| `query_hotboard` | 查询热榜，返回 Markdown 报告 |

## 参数说明

- **area**: `video`（视频/社区平台，如 B站、抖音、知乎、微博）或 `news`（新闻资讯平台，如 百度、头条、网易）
- **platforms**: 逗号分隔平台名（中文或英文），留空查全部
- **keywords**: 逗号分隔关键词，只返回匹配的热搜条目
- **max_items**: 每平台最多返回条数（默认 10）

## 支持的平台

### 视频区 (video)
B站(bilibili)、抖音(douyin)、快手(kuaishou)、知乎(zhihu)、微博(weibo)、小红书(xiaohongshu)、百度(baidu)、头条(toutiao)

### 新闻区 (news)
知乎(zhihu)、微博(weibo)、百度(baidu)、头条(toutiao)、新浪(sina)、网易(163)、搜狐(sohu)、澎湃(thepaper)

## 前置条件

需要 UAPI_API_KEY 环境变量（在 .env 中配置）。
