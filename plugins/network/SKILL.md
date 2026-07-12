---
name: network
description: HTTP 网络请求与网页正文读取工具。提供 http_get/http_post 原始请求，以及 web_read 网页文字/Markdown 读取；支持 public/local/private/all 网络作用域控制。
version: "1.1"
category: core
enabled: true
tags: ["network", "http", "web", "core"]
---

# 网络请求与网页读取 (Network)

`network` 提供原始 HTTP 请求和网页正文读取能力。

## 插件路径

`plugins/network/`

## 注册工具

| 工具 | 用途 | 返回内容 |
|------|------|----------|
| `http_get` | API、JSON、源码、状态调试 | 原始响应 |
| `http_post` | 调用接口、提交 JSON、提交表单 | 原始响应 |
| `web_read` | 读文章、博客、新闻、文档、本地 Web 页面 | 可读正文文本或 Markdown |

## 工具边界

用户明确要 HTTP 原始响应、API 返回、JSON、源码、状态码、响应头、接口调试时，使用 `http_get`。

用户要向接口发送 POST 请求、提交 JSON、提交表单、调用 API 时，使用 `http_post`。

用户要阅读网页正文、总结网页、提取文章内容、读取本地 Web 页面或网页转 Markdown 时，使用 `web_read`。

## web_read

`web_read` 返回给人阅读的正文内容，不返回网页源码。优先 direct 抓取并在本地解析 HTML；公网 URL 在 direct 失败、内容为空或疑似 403/CAPTCHA/Cloudflare 时，按需尝试第三方 reader 服务。

### 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `url` | string | 是 | — | 要读取的网页 URL，仅支持 http/https |
| `strategy` | string (enum) | 否 | `"auto"` | `auto` 先 direct 后 reader / `direct` 只本地解析 / `reader` 只用 reader 服务 |
| `reader_service` | string (enum) | 否 | `"auto"` | `auto` / `jina` (r.jina.ai) / `markdown_new` (markdown.new) / `defuddle` (defuddle.md) |
| `network_scope` | string | 否 | `"public"` | 网络作用域：public / local / private / all |
| `max_chars` | integer | 否 | 12000 | 返回正文最大字符数，上限 30000 |
| `headers` | string | 否 | — | JSON 格式请求头，仅 direct 抓取时使用 |

### 结果说明

- 成功：返回网页正文文本或 Markdown
- 失败：返回 `ERROR:` 前缀的错误信息

## network_scope

`http_get`、`http_post`、`web_read` 都支持 `network_scope`：

| network_scope | 允许访问 |
|---------------|----------|
| `public` | 仅公网 |
| `local` | `localhost`、`127.0.0.1`、`::1` |
| `private` | 局域网地址，如 `192.168.x.x`、`10.x.x.x`、`172.16.x.x`、`.lan` 解析出的内网地址 |
| `all` | 公网 + local + private |

未显式传入时读取用户配置或环境变量，默认 `public`。

## 安全约束

- 仅允许 http/https 协议
- DNS 解析后二次校验 IP，防 DNS rebinding
- 云元数据地址始终禁止访问，即使 `network_scope=all`
- local/private 地址只能 direct 读取，禁止通过第三方 reader 服务转发
- 超时遵循 `tool.tool_timeout` 配置优先级

## 常见规范

- 读网页正文用 `web_read`，不用 `http_get`（后者返回原始 HTML 源码）
- 调用 API 获取 JSON 数据用 `http_get`/`http_post`，不用 `web_read`
- `headers` 参数为 JSON 字符串格式，如 `{"Authorization": "Bearer xxx"}`

## 常见处理办法

- **403/CAPTCHA/Cloudflare**：切换 `strategy="reader"` 使用第三方 reader 服务
- **内网访问被拒**：显式传入 `network_scope="local"` 或 `"private"` 或 `"all"`
- **内容截断**：增大 `max_chars`（上限 30000）
- **请求超时**：检查 `tool.tool_timeout` 配置

## 常见教训

- `web_read` 不返回网页源码，只返回正文；需要源码时用 `http_get`
- local/private 地址禁止通过第三方 reader 服务转发，会泄露内网信息
- `network_scope` 未配置时默认 `public`，访问内网需显式指定