# 外部消息路由配置

本页说明如何让 VOTX Agent 接收 QQ/NapCat/OneBot 和 Telegram 的外部消息，并把图片、语音、文件等附件交给智能体处理。

## 配置文件位置

优先读取：

```text
message/config.local.json
```

如果不存在，则读取：

```text
message/config.json
```

也可以通过环境变量指定：

```env
VOTX_MESSAGE_CONFIG=message/config.local.json
```

`message/config.example.json` 可作为初始模板。建议复制为 `message/config.local.json` 后再修改。

## 最小配置结构

```json
{
  "enabled": true,
  "platforms": {
    "onebot": {
      "enabled": true,
      "url": "ws://127.0.0.1:3001",
      "access_token": "",
      "reconnect_interval": 5,
      "api_timeout": 15,
      "bound_users": {
        "qq:123456789": "alice"
      }
    },
    "telegram": {
      "enabled": false,
      "bot_token": "<telegram-bot-token>",
      "poll_interval": 2,
      "api_timeout": 20,
      "bound_users": {
        "tg:987654321": "alice"
      }
    }
  }
}
```

顶层 `enabled` 控制整个外部消息路由。各平台下的 `enabled` 分别控制 OneBot 和 Telegram。

## OneBot / NapCat

VOTX Agent 作为 WebSocket 客户端连接 NapCat 的正向 WebSocket。

常见地址：

```text
本机运行 NapCat: ws://127.0.0.1:3001
```

关键字段：

```json
{
  "enabled": true,
  "url": "ws://127.0.0.1:3001",
  "access_token": "",
  "reconnect_interval": 5,
  "api_timeout": 15,
  "bound_users": {
    "qq:123456789": "alice"
  }
}
```

`bound_users` 把外部账号绑定到内部用户目录。上例表示 QQ 号 `123456789` 的消息会进入：

```text
users/alice/
```

NapCat 如果开启了 access token，这里的 `access_token` 必须一致。

NapCat 返回的本地附件路径会复制到 `users/<name>/history/file/`，并写入 `external_attachments.jsonl` 日志。

## Telegram

Telegram 使用长轮询，不需要公网 webhook。

关键字段：

```json
{
  "enabled": true,
  "bot_token": "<telegram-bot-token>",
  "poll_interval": 2,
  "api_timeout": 20,
  "proxy": "http://127.0.0.1:7890",
  "bound_users": {
    "tg:987654321": "alice"
  }
}
```

`bot_token` 从 BotFather 获取。`proxy` 可选，用于被墙环境访问 Telegram API（优先级：`platforms.telegram.proxy` > 环境变量 `HTTPS_PROXY` / `HTTP_PROXY`）。`bound_users` 中的 Telegram 用户 ID 可以通过日志或 Telegram bot 的消息来源确认。

如果启动日志出现 `getMe 失败`，优先检查：

- `bot_token` 是否正确。
- 当前网络是否能访问 Telegram API。
- 是否已配置 `proxy` 字段或环境变量 `HTTPS_PROXY`。

## 群聊控制

群聊建议开启 at 触发，避免智能体响应所有群消息。

```json
{
  "group_mode": {
    "qq": {
      "enabled": true,
      "require_at_bot": true,
      "allow_agent_chat": true,
      "max_message_length": 4000
    },
    "telegram": {
      "enabled": true,
      "require_at_bot": true,
      "allow_agent_chat": true,
      "max_message_length": 4000
    }
  }
}
```

建议：

- 私聊通常直接响应。
- 群聊建议 `require_at_bot: true`。
- 如果群里完全不希望智能体回复，设置 `allow_agent_chat: false`。

## 附件接收

外部消息收到的图片、语音、视频、文件会统一保存到用户文件池：

```text
users/<用户名>/history/file/
```

这和 Web 上传文件使用同一个目录，因此 Web 右侧文件栏可以直接看到外部消息附件。

支持类型：

```text
OneBot / NapCat: image, record, video, file
Telegram: photo, document, voice, audio, video
```

智能体收到的消息会被整理为类似格式：

```text
[外部消息附件]
- image: <project-root>/users/<name>/history/file/xxx.jpg （如需识别图片内容，请调用 vision_analyze）
- voice: <project-root>/users/<name>/history/file/yyy.ogg （如需转写语音内容，请调用 audio_transcribe）

用户消息:
帮我看看这张图
```

常见处理方式：

- 图片：调用 `vision_analyze`。
- 语音：调用 `audio_transcribe`。
- 文档/PDF/Office：调用 `markdown_converter` 或文件读取相关工具。
- 普通文本文件：调用 `read_file`。

附件日志位置：

```text
users/<用户名>/history/log/external_attachments.jsonl
```

## 主动推送

智能体可以通过内置工具把消息或文件推送回 QQ/Telegram。

相关工具：

```text
qq_send
qq_file
```

推送队列默认目录：

```text
message/push_queue/
```

## 常见问题

### OneBot 显示 did not receive a valid HTTP response

通常是连接地址不是正向 WebSocket 地址，或 NapCat 没有开启对应服务。检查：

- `url` 是否为 `ws://...`。
- NapCat 正向 WebSocket 端口是否正确。
- `access_token` 是否一致。

### 群聊没有响应

检查：

- 是否绑定了发送者账号。
- 是否开启 `group_mode.<平台>.enabled`。
- 是否需要 at 机器人。
- 消息是否超过 `max_message_length`。

### 附件没有出现在文件栏

检查：

- 文件是否保存到 `users/<用户名>/history/file/`。
- 外部账号是否绑定到了正确的内部用户名。
- Web 右侧文件栏是否正在查看对应用户和文件目录。

### Telegram getMe 失败

检查：

- `bot_token` 是否正确。
- 本机是否能访问 Telegram。
- 代理是否配置：优先检查 `platforms.telegram.proxy` 字段，其次检查环境变量 `HTTPS_PROXY` / `HTTP_PROXY`。
