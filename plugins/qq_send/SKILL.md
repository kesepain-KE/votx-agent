---
name: qq_send
description: 通用消息发送 — 通过 PushQueue 向 QQ（OneBot）或 Telegram 发送文本消息。当 Agent 需要主动推送通知、回复或提醒到外部平台时使用。
version: "1.1"
category: messaging
enabled: true
tags: ["qq", "telegram", "message", "push"]
---

# 发送消息 (QQ Send)

通过消息路由的 PushQueue 机制，向 QQ 或 Telegram 发送文本消息。消息通过异步队列发送，支持私聊和群聊。

## 插件路径

`plugins/qq_send/`

## 注册工具

| 工具 | 用途 |
|------|------|
| `send_qq_message` | 向 QQ（OneBot）或 Telegram 发送文本消息 |

## 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `target` | string | 是 | — | 目标 ID：QQ 号 / TG 用户 ID / 群号 |
| `chat_type` | string | 是 | — | `private`（私聊）或 `group`（群聊） |
| `message` | string | 是 | — | 要发送的文本内容 |
| `platform` | string | 否 | `"onebot"` | 平台：`onebot`（QQ）或 `telegram`。由智能体根据用户消息来源或用户指令决定 |

## 结果说明

- 成功：返回 `OK: 消息已入队, ID: <task_id>` + 平台/目标信息
- 失败：返回 `ERROR:` 前缀的错误信息

## 典型场景

- 定时任务结果推送到 QQ/Telegram
- 主动通知用户某事已完成
- 群聊消息推送

## 常见规范

- `platform` 由智能体根据用户消息来源判断：用户从 QQ 来则用 `onebot`，从 Telegram 来则用 `telegram`
- 消息通过文件队列异步发送，非实时
- `chat_type` 仅支持 `private` 和 `group`，其他值会报错

## 常见处理办法

- **消息未送达**：检查 PushQueue 是否正常运行，查看 `message/push_queue/` 目录
- **target 为空**：确认目标 ID 非空（QQ 号 / TG 用户 ID / 群号）
- **平台不支持**：确认 `platform` 为 `onebot` 或 `telegram`

## 常见教训

- 消息是异步入队，不代表对方已收到；实际投递依赖 OneBot/TG Bot 在线状态
- 发送群消息时 `target` 是群号，不是群名
- Telegram Bot 主动发起对话需要用户先 `/start` 过 Bot