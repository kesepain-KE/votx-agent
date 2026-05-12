---
name: task-time
description: 管理 corn 定时任务 — 创建/查看/修改/删除每日或单次定时任务，由后台调度器自动执行
---

# 定时任务管理 (corn)

你可以帮用户管理 corn 定时任务系统。corn 是一个后台调度器，会在指定时间自动执行任务。

## 任务类型

| 类型 | 说明 |
|------|------|
| `daily` | 每天在指定时间执行一次 |
| `once` | 指定时间执行一次，过期自动删除 |

## 时间格式

- daily/recurring 任务: `HH:MM`（例如 `09:00`）
- once 任务: 也用 `HH:MM`，执行一次后当天过期

## 工作流程

1. 用户说"每天早上 8 点提醒我看新闻" → 用 `task_time_create` 创建 daily 任务
2. 用户说"帮我列出所有定时任务" → 用 `task_time_list` 查看
3. 用户说"把那个新闻任务改成 9 点" → 用 `task_time_update` 修改时间
4. 用户说"删除那个新闻任务" → 用 `task_time_delete` 删除

## 注意事项

- 任务的 `command` 字段是发送给 corn 的 prompt，corn 会用 `start.py --once` 执行
- 尽量用简洁明确的中文描述作为 command
- 创建前告知用户任务详情，获得确认后再创建
