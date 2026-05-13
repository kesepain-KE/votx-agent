---
name: network
description: HTTP 网络请求工具 — GET/POST。内置 SSRF 防护（拦截内网/回环地址，DNS 二次解析校验）。当 Agent 需要访问外部 API 或网页时使用。
---

# 网络请求

安全的 HTTP 客户端，带完整的 SSRF 防护。

## 工具

| 工具 | 用途 |
|------|------|
| `http_get` | 发送 HTTP GET 请求 |
| `http_post` | 发送 HTTP POST 请求 |

## 安全约束

- 仅允许 http/https 协议
- 拦截所有内网地址（10.x, 172.16.x, 192.168.x, 127.x 等）
- DNS 解析后二次校验 IP（防 DNS rebinding）
- 响应截断上限 8000 字符
- 超时可通过 `HTTP_TIMEOUT` 环境变量配置（默认 15s）
