# message 配置手册

`message-router` 已并入 Agent 进程，随 Web 服务启动和停止。NapCat 是外部容器或外部进程，votx-agent 只负责通过 WebSocket 连接它；Telegram 使用 Bot API 长轮询，不需要公网 webhook。

## 配置文件路径

| 环境 | 路径 |
|---|---|
| Windows / Linux 原生 | `message/config.local.json`，由 `message/config.example.json` 复制 |
| Docker | `message-runtime/config.json`，由 `message-runtime/config.example.json` 复制 |
| 临时覆盖 | `VOTX_MESSAGE_CONFIG=/path/to/config.json` |

示例文件默认关闭外部消息路由。启用时需要同时打开顶层 `enabled` 和目标平台 `enabled`。

## 顶层配置

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `enabled` | bool | false | 总开关；任一平台启用时也会自动视为启用 |
| `admins` | string[] | [] | 内部管理员用户名，对应 `users/<name>/config.json` |

## OneBot / NapCat / QQ

```json
{
  "enabled": true,
  "platforms": {
    "onebot": {
      "enabled": true,
      "ws_url": "ws://127.0.0.1:3001",
      "access_token": "",
      "reconnect_interval": 5,
      "api_timeout": 15,
      "bound_users": {
        "qq:123456789": "alice"
      }
    }
  }
}
```

| 字段 | 说明 |
|---|---|
| `ws_url` | NapCat 正向 WebSocket 地址。本机用 `ws://127.0.0.1:3001` |
| `access_token` | NapCat OneBot token；未设置就留空 |
| `bound_users` | 外部 QQ 号到内部用户的绑定 |

Docker 连接示例：

- NapCat 在宿主机：`ws://host.docker.internal:3001`
- NapCat 与 votx-agent 在同一 Docker 网络：`ws://napcat:3001`
- 远程服务器：`ws://<服务器或内网IP>:3001`

NapCat 侧只需要开启正向 WebSocket。不要配置反向 WebSocket 给 votx-agent。

## Telegram

```json
{
  "enabled": true,
  "platforms": {
    "telegram": {
      "enabled": true,
      "bot_token": "123456:ABC",
      "poll_interval": 2,
      "api_timeout": 30,
      "bound_users": {
        "tg:987654321": "alice"
      }
    }
  }
}
```

| 字段 | 说明 |
|---|---|
| `bot_token` | 从 `@BotFather` 获取 |
| `poll_interval` | 异常后的重试间隔，正常长轮询 timeout 固定由路由控制 |
| `bound_users` | Telegram user id 到内部用户的绑定 |

## 命令系统

| 命令 | 说明 |
|---|---|
| `/cron list` | 列出定时任务 |
| `/cron add daily|once HH:MM <命令>` | 创建定时任务 |
| `/cron update <task_id> time|command|type <新值>` | 更新定时任务 |
| `/cron delete <task_id>` | 删除定时任务 |
| `/plan list` | 列出任务计划 |
| `/plan view <plan_id>` | 查看计划详情 |
| `/plan approve <plan_id>` | 批准执行计划 |
| `/plan abort <plan_id>` | 中止计划 |

群聊默认需要 @bot 才响应；管理员用户在 `admins` 中配置。

## 主动推送

`send_qq_message` 和 `upload_qq_file` 不直接调用平台 API，而是写入 `push.queue_dir`：

```json
"push": {
  "enabled": true,
  "queue_dir": "message/push_queue",
  "retry_times": 3,
  "retry_interval": 5
}
```

路由就绪后后台循环会发送 pending 任务；如果路由正在重连，任务会保持 pending，避免启动顺序导致推送丢失。

## 快速启用

Windows / Linux 原生：

```bash
cp message/config.example.json message/config.local.json
```

Docker：

```bash
bash install_docker.sh
cp message-runtime/config.example.json message-runtime/config.json
```

然后修改：

1. `enabled: true`
2. 对应平台 `enabled: true`
3. `ws_url` 或 `bot_token`
4. `bound_users`
5. 重启 Web 服务或 Docker 容器
