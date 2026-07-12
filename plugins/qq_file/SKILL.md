---
name: qq_file
description: 通用文件上传 — 通过 PushQueue 向 QQ（OneBot）或 Telegram 上传文件。当 Agent 需要分享文档、图片、PDF 等文件到外部平台时使用。
version: "1.1"
category: messaging
enabled: true
tags: ["qq", "telegram", "file", "upload", "push"]
---

# 上传文件 (QQ File)

通过消息路由的 PushQueue 机制，向 QQ 或 Telegram 上传文件。文件通过异步队列发送，支持私聊和群聊。

## 插件路径

`plugins/qq_file/`

## 注册工具

| 工具 | 用途 |
|------|------|
| `upload_qq_file` | 向 QQ（OneBot）或 Telegram 上传文件 |

## 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `target` | string | 是 | — | 目标 ID：QQ 号 / TG 用户 ID / 群号 |
| `chat_type` | string | 是 | — | `private`（私聊）或 `group`（群聊） |
| `file_path` | string | 是 | — | 要上传的本地文件绝对路径 |
| `platform` | string | 否 | `"onebot"` | 平台：`onebot`（QQ）或 `telegram`。由智能体根据用户消息来源或用户指令决定 |

## 结果说明

- 成功：返回 `OK: 文件上传任务已入队, ID: <task_id>` + 平台/文件/目标信息
- 失败：返回 `ERROR:` 前缀的错误信息

## 平台差异

| 特性 | QQ (OneBot) | Telegram |
|------|-------------|----------|
| 私聊文件 | `upload_private_file` | `sendDocument` |
| 群聊文件 | `upload_group_file` | `sendDocument` |
| 最大文件 | NapCat 限制 | 50MB (Bot API) |

## 典型场景

- 分享生成的报告/文档到 QQ/Telegram
- 发送下载的文件给用户
- 群聊共享文件

## 常见规范

- `file_path` 需为本地存在的文件绝对路径
- 智能体生成的文件默认在 `users/<user>/download/`，上传时使用该路径
- `platform` 由智能体根据用户消息来源判断

## 常见处理办法

- **文件不存在**：检查 `file_path` 路径是否正确，文件是否已生成
- **上传失败**：检查文件大小是否超过平台限制
- **平台不支持**：确认 `platform` 为 `onebot` 或 `telegram`

## 常见教训

- Telegram Bot API 限制文件大小 50MB，超过会失败
- QQ 的文件上传能力取决于 OneBot/NapCat 实现，不同版本限制不同
- 文件上传是异步操作，入队成功不代表对方已收到