---
name: task_time
description: 管理 cron 定时任务 — 创建/查看/修改/删除每日、单次或重复定时任务，由后台调度器自动执行
version: "1.1"
category: task
enabled: true
tags: ["task", "cron", "scheduler", "timer"]
---

# 定时任务管理 (Task Time)

管理 cron 定时任务系统。cron 是后台调度器，在指定时间自动执行任务。

## 插件路径

`plugins/task_time/`

## 注册工具

| 工具 | 用途 |
|------|------|
| `task_time_create` | 创建定时任务（daily/once/recurring） |
| `task_time_list` | 列出当前用户的所有定时任务 |
| `task_time_update` | 修改定时任务的时间、命令或类型 |
| `task_time_delete` | 删除指定定时任务 |

## 参数

### task_time_create

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `type` | string (enum) | 是 | `daily`（每天执行）/ `once`（执行一次）/ `recurring`（重复执行） |
| `time` | string | 是 | 执行时间，`HH:MM` 格式（如 `09:00`） |
| `command` | string | 是 | 任务命令/prompt，cron 执行时发送给 AI 的消息内容 |

### task_time_list

无参数。

### task_time_update

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 要修改的任务 ID |
| `time` | string | 否 | 新的执行时间，`HH:MM` 格式 |
| `command` | string | 否 | 新的任务命令/prompt |
| `type` | string (enum) | 否 | 新的任务类型：`daily` / `once` / `recurring` |

### task_time_delete

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 要删除的任务 ID |

## 任务类型说明

| 类型 | 说明 | 示例 |
|------|------|------|
| `daily` | 每天在指定时间执行一次 | 每天早上 9:00 发送 AI 日报 |
| `once` | 指定时间执行一次后自动删除 | 下午 3:00 提醒开会 |
| `recurring` | 重复执行，每天在指定时间执行，直到手动删除 | 每小时检查一次服务器状态 |

## 结果说明

- `create`：返回任务 ID 和创建确认
- `list`：返回所有任务列表（含 ID、类型、时间、命令）
- `update`：返回修改确认
- `delete`：返回删除确认
- 失败：返回 `ERROR:` 前缀的错误信息

## 上下文绑定

- 以创建任务时所属的 `users/<name>/` 身份执行
- 享有该用户的完整对话历史和 system prompt 配置
- 遵循该用户的 `config.json` 工具白名单/黑名单
- 任务结果可通过 `qq_send` / `qq_file` 推送到外部消息平台

## 常见规范

- `command` 是发送给 cron 的 prompt，cron 会以用户消息形式注入对话流
- 尽量用简洁明确的中文描述作为 command
- 创建前告知用户任务详情，获得确认后再创建
- `once` 类型执行一次后自动删除，不需手动清理

## 常见处理办法

- **任务未执行**：检查 cron 调度器是否正常运行（CLI/Web 模式均随主进程启动）
- **时间格式错误**：必须为 `HH:MM` 格式（24 小时制），如 `09:00`、`14:30`
- **任务连续失败**：同一任务连续执行失败 3 次后记录错误，不会无限重试

## 常见教训

- `once` 类型执行后自动删除，如需持久提醒用 `daily` 或 `recurring`
- 定时任务的执行结果取决于当时 AI 的响应，不是命令行脚本
- 修改 `type` 可能改变任务的行为周期，谨慎操作