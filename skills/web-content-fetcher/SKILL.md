---
name: web-content-fetcher
description: "网页内容获取工具 | 当 http_get 无法获取内容时（空白、403、CAPTCHA），使用替代服务获取网页 Markdown。通过 http_get 调用 r.jina.ai / markdown.new / defuddle.md 等第三方转码服务。触发词：获取网页内容、网页转markdown、内容抓取、fetch webpage、bypass cloudflare"
---

# 网页内容获取工具

当 `http_get` 无法获取网页内容时，使用替代服务获取网页 Markdown 格式内容。

## 支持的服务

| 优先级 | 服务 | 用法 | 适用场景 |
|--------|------|------|----------|
| 1 | **r.jina.ai** | `http_get("https://r.jina.ai/{url}")` | 最稳定，通用性强 |
| 2 | **markdown.new** | `http_get("https://markdown.new/{url}")` | Cloudflare 保护网站 |
| 3 | **defuddle.md** | `http_get("https://defuddle.md/{url}")` | 备用方案 |

## 使用方法

当 `http_get` 直接请求目标 URL 失败时，按顺序尝试：

```bash
# 1. 首选 jina.ai
http_get("https://r.jina.ai/https://example.com")

# 2. Cloudflare 专用
http_get("https://markdown.new/https://example.com")

# 3. 备用
http_get("https://defuddle.md/https://example.com")
```

## 示例

用户说"帮我获取 https://news.example.com/article/123 的内容"
→ 先 `http_get("https://news.example.com/article/123")`
→ 如果失败，试 `http_get("https://r.jina.ai/https://news.example.com/article/123")`

---

*让网页内容获取不再受限 🌐*
