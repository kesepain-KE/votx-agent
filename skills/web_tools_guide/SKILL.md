---
name: web_tools_guide
description: "网页获取决策指南 — 当前项目可用的网页获取路径：1) tavily_search（搜索信息）2) http_get（直接获取网页内容）3) web_content_fetcher 技能（r.jina.ai 等转码服务兜底）。当用户要求搜索、查资料、获取网页内容时读取本指南，按决策流程选择最佳路径。"
---

# Web 工具策略 — 本项目适配版

当前项目实际可用的工具有：
- **`tavily_search`** — 搜索信息（需 TAVILY_API_KEY）
- **`http_get`** — 直接获取网页内容
- **`web_content_fetcher`** 技能 — 通过 r.jina.ai 等服务转码获取

## 决策流程

```
有明确 URL？
├─ YES → http_get 直接获取
│        失败（空白/403/CAPTCHA）？
│        → web_content_fetcher（r.jina.ai 转码）
│
└─ NO  → tavily_search
         ├─ 成功 → 对结果 URL 用 http_get 获取
         └─ 失败（API 未配置）→ 告知用户需要配置 TAVILY_API_KEY
```

## 各工具说明

### tavily_search
- **何时用**：没有明确 URL，需要搜索
- **需配置**：`.env` 中 `TAVILY_API_KEY`
- **未配置时**：告知用户需配置，或改用 `http_get` 直接请求已知网站

### http_get
- **何时用**：有明确的 URL，获取静态网页内容
- **限制**：可能被目标网站 403/CAPTCHA 拦截
- **失败时**：降级到 web_content_fetcher

### web_content_fetcher
- **何时用**：http_get 被拦截时
- **做法**：通过 `http_get` 调用 `https://r.jina.ai/{url}` 等第三方转码服务
