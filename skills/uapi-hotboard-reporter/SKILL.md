---
name: uapi-hotboard-reporter
description: UAPI 全网热榜查询 — 抓取多平台热搜并生成报告。支持视频区、新闻区和科技区，可按平台和关键词筛选。Agent 查询热搜、热榜、热点话题时使用。
compatibility: 免费接口无需 API Key，uapis.cn 直接调用
---

# UAPI 热榜查询

通过 UAPI (uapis.cn) 接口查询全网多平台热榜数据，覆盖 45+ 平台。

## 工具

| 工具 | 用途 |
|------|------|
| `query_hotboard` | 查询热榜，返回 Markdown 报告 |

## 参数说明

- **area**: `video`（视频/社区平台）、`news`（新闻资讯平台）、`tech`（技术/开发者平台）
- **platforms**: 逗号分隔平台名（中文或英文），留空查全部
- **keywords**: 逗号分隔关键词，只返回匹配的热搜条目
- **max_items**: 每平台最多返回条数（默认 10）

## 支持的平台

### 视频/社区 (video)
B站(bilibili)、A站(acfun)、抖音(douyin)、快手(kuaishou)、豆瓣电影(douban-movie)、豆瓣小组(douban-group)、英雄联盟(lol)、原神(genshin)、崩坏3(honkai)、星穹铁道(starrail)、网易云音乐(netease-music)、QQ音乐(qq-music)

### 新闻资讯 (news)
微博(weibo)、知乎(zhihu)、知乎日报(zhihu-daily)、百度(baidu)、头条(toutiao)、澎湃(thepaper)、新浪(sina)、新浪新闻(sina-news)、腾讯新闻(qq-news)、网易新闻(netease-news)

### 技术/开发者 (tech)
V2EX、虎扑(hupu)、NGA(ngabbs)、吾爱破解(52pojie)、全球主机(hostloc)、酷安(coolapk)、虎嗅(huxiu)、爱范儿(ifanr)、少数派(sspai)、IT之家(ithome)、掘金(juejin)、简书(jianshu)、果壳(guokr)、36氪(36kr)、51CTO、CSDN、NodeSeek、HelloGitHub

## API 来源

- 端点: `GET https://uapis.cn/api/v1/misc/hotboard?type={platform}`
- 免费接口，无需 API Key
