---
name: network
description: HTTP 网络请求与网页正文读取工具。提供 http_get/http_post 原始请求，以及 web_read 网页文字/Markdown 读取；支持 public/local/private/all 网络作用域控制。
---

# 网络请求与网页读取

`network` 提供原始 HTTP 请求和网页正文读取能力。

## 工具边界

| 工具 | 用途 | 返回内容 |
|------|------|----------|
| `http_get` | API、JSON、源码、状态调试 | 原始响应 |
| `http_post` | 调用接口、提交 JSON、提交表单 | 原始响应 |
| `web_read` | 读文章、博客、新闻、文档、本地 Web 页面 | 可读正文文本或 Markdown |

## web_read

当用户要读取网页内容、提取网页文字、总结网页、网页转 Markdown、获取文章正文、读取新闻、博客、在线文档或本地 Web 页面时，优先使用 `web_read`。

`web_read` 返回给人阅读的正文内容，不返回网页源码。它会优先 direct 抓取并在本地解析 HTML；只有公网 URL 在 direct 失败、内容为空或疑似 403/CAPTCHA/Cloudflare 时，才会按需尝试第三方 reader 服务。

支持策略：

| strategy | 行为 |
|----------|------|
| `auto` | 先 direct 本地解析，公网失败后尝试 reader |
| `direct` | 只直接抓取并本地解析 |
| `reader` | 只使用 reader 服务；仅公网 URL 可用 |

支持 reader 服务：

| reader_service | 服务 |
|----------------|------|
| `auto` | 按顺序尝试 jina、markdown_new、defuddle |
| `jina` | `r.jina.ai` |
| `markdown_new` | `markdown.new` |
| `defuddle` | `defuddle.md` |

## network_scope

`http_get`、`http_post`、`web_read` 都支持 `network_scope`：

| network_scope | 允许访问 |
|---------------|----------|
| `public` | 仅公网 |
| `local` | `localhost`、`127.0.0.1`、`::1` |
| `private` | 局域网地址，如 `192.168.x.x`、`10.x.x.x`、`172.16.x.x`、`.lan` 解析出的内网地址 |
| `all` | 公网 + local + private |

未显式传入时会读取用户配置或环境变量：

```json
{
  "network": {
    "default_network_scope": "all"
  }
}
```

也支持 `tool.default_network_scope`、顶层 `default_network_scope`，以及环境变量 `VOTX_NETWORK_SCOPE` / `HTTP_NETWORK_SCOPE` / `NETWORK_SCOPE`。未配置时默认 `public`。

## 安全约束

- 仅允许 http/https 协议。
- DNS 解析后二次校验 IP，防 DNS rebinding。
- 云元数据地址始终禁止访问，即使 `network_scope=all`。
- local/private 地址只能 direct 读取，禁止通过 `r.jina.ai`、`markdown.new`、`defuddle.md` 等第三方 reader 服务转发。
- 响应体上限由 `MAX_RESPONSE_BYTES` 控制，当前为 10MB。
- 超时遵循 `tool.tool_timeout` 配置优先级：用户配置 > 全局配置 > `HTTP_TIMEOUT` 环境变量默认值（未设置时 15 秒）。

## 调用选择

用户明确要 HTTP 原始响应、API 返回、JSON、源码、状态码、响应头、接口调试时，使用 `http_get`。

用户要向接口发送 POST 请求、提交 JSON、提交表单、调用 API 时，使用 `http_post`。

用户要阅读网页正文、总结网页、提取文章内容、读取本地 Web 页面或网页转 Markdown 时，使用 `web_read`。
