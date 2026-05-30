---
name: qq_file
description: 通用文件上传 — 通过 PushQueue 向 QQ（OneBot）或 Telegram 上传文件。当 Agent 需要分享文档、图片、PDF 等文件到外部平台时使用。
---

# 上传文件

通过消息路由的 PushQueue 机制，向 QQ 或 Telegram 上传文件。

## 工具

| 工具 | 用途 |
|------|------|
| `upload_qq_file` | 向 QQ 或 Telegram 上传文件 |

## 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `target` | string | 是 | QQ 号 / TG 用户 ID / 群号 |
| `chat_type` | string | 是 | `private`（私聊）或 `group`（群聊） |
| `file_path` | string | 是 | 要上传的本地文件绝对路径 |
| `platform` | string | 否 | `onebot`（QQ，默认）或 `telegram` |

## 平台差异

| 特性 | QQ (OneBot) | Telegram |
|------|-------------|----------|
| 私聊文件 | `upload_private_file` | `sendDocument` |
| 群聊文件 | `upload_group_file` | `sendDocument` |
| 最大文件 | NapCat 限制 | 50MB (Bot API) |

## 示例

- 给 QQ 好友发文件: `upload_qq_file("123456789", "private", "/path/to/file.pdf")`
- 给 QQ 群发文件: `upload_qq_file("987654321", "group", "/path/to/report.pdf")`
- 给 Telegram 用户发文件: `upload_qq_file("6481508324", "private", "/path/to/file.pdf", "telegram")`

## 安全约束

- file_path 需要在项目根目录或用户目录内（沙箱校验）
- 仅支持 private / group 两种 chat_type
- 仅支持 onebot / telegram 两种 platform
- 无法访问用户目录之外的文件
