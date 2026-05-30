---
name: qq_send
description: 通用消息发送 — 通过 PushQueue 向 QQ（OneBot）或 Telegram 发送文本消息。当 Agent 需要主动推送通知、回复或提醒到外部平台时使用。
---

# 发送消息

通过消息路由的 PushQueue 机制，向 QQ 或 Telegram 发送文本消息。

## 工具

| 工具 | 用途 |
|------|------|
| `send_qq_message` | 向 QQ 或 Telegram 发送文本消息 |

## 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `target` | string | 是 | QQ 号 / TG 用户 ID / 群号 |
| `chat_type` | string | 是 | `private`（私聊）或 `group`（群聊） |
| `message` | string | 是 | 要发送的文本内容 |
| `platform` | string | 否 | `onebot`（QQ，默认）或 `telegram` |

## 示例

- 给 QQ 好友发消息: `send_qq_message("123456789", "private", "你好")`
- 给 QQ 群发消息: `send_qq_message("987654321", "group", "大家好")`
- 给 Telegram 用户发消息: `send_qq_message("6481508324", "private", "你好", "telegram")`

## 安全约束

- 仅支持 private / group 两种 chat_type
- 仅支持 onebot / telegram 两种 platform
- 消息通过文件队列异步发送，有重试机制（默认 3 次）
