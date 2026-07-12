---
name: Task_Plan
slug: task_plan
version: "1.1"
description: "将复杂用户请求自动分解为可执行步骤计划，可视化进度，支持暂停/继续/中止。受用户 config.json 中 task_plan.accept_task 控制。"
category: task
enabled: true
tags: ["task", "plan", "scheduler"]
---

# 任务计划 (Task Plan)

管理复杂任务的分解、执行和追踪。存储在 `users/<name>/task-plan/`。

## 插件路径

`plugins/task_plan/`

## 注册工具

| 工具 | 用途 |
|------|------|
| `task_plan_create` | 调用子代理分析对话 → 生成结构化执行计划 |
| `task_plan_list` | 列出当前用户的所有计划及进度 |
| `task_plan_view` | 查看计划详情（含所有步骤、状态、结果）。不传 plan_id 时查看活跃计划 |
| `task_plan_step_done` | 标记步骤完成并记录结果 |
| `task_plan_step_fail` | 标记步骤失败并记录错误，计划自动暂停 |
| `task_plan_abort` | 中止计划，未完成步骤标记为跳过 |
| `task_plan_edit` | 编辑计划步骤的描述或参数 |

## 参数

### task_plan_create

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `description` | string | 是 | 用户请求的简要描述，用于生成计划标题和上下文 |

### task_plan_view

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `plan_id` | string | 否 | 计划 ID（如 `plan_a1b2c3d4`），不传时查看当前活跃计划 |

### task_plan_step_done

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `plan_id` | string | 是 | 计划 ID |
| `step_id` | string | 是 | 步骤 ID |
| `result` | string | 否 | 步骤执行结果摘要（建议 200 字以内） |

### task_plan_step_fail

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `plan_id` | string | 是 | 计划 ID |
| `step_id` | string | 是 | 步骤 ID |
| `error` | string | 是 | 错误描述 |

### task_plan_edit

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `plan_id` | string | 是 | 计划 ID |
| `step_id` | string | 否 | 步骤 ID（编辑特定步骤时必填） |
| `description` | string | 否 | 新的描述文本 |
| `params` | string | 否 | 新的工具参数（JSON 字符串） |

## 状态枚举

| 计划状态 | 说明 | 步骤状态 |
|----------|------|----------|
| `pending` | 等待批准 | `pending` |
| `in_progress` | 执行中 | `in_progress` |
| `completed` | 已完成 | `completed` |
| `paused` | 已暂停（失败或手动暂停） | `failed` |
| `aborted` | 已中止 | `skipped` |

## 子代理

`agents/task_plan/agent.py::generate_plan()` — 同步 LLM 调用，无流式无工具。
`generate_plan_stream()` — 流式版本，逐 chunk 推送到 Web SSE。

输入：完整对话 + 可用工具列表 + 技能目录 + system prompt
输出：`{plan: {title, description, steps[{id, description, tool_calls, status}]}}`

## 配置控制

| 配置 | 位置 | 效果 |
|------|------|------|
| `task_plan.accept_task: true` | `users/<name>/config.json` | 计划创建后自动批准并执行 |
| `task_plan.accept_task: false` | 同上 | 需用户在 Web UI 手动批准 |
| `task_plan.max_steps` | `config/config_core.json` | 子代理生成计划的最大步骤数（默认 10） |

## 存储路径

```text
users/<name>/task-plan/plan_<uuid8hex>.json
```

## 常见规范

- 计划创建后强制刷新 system prompt，使计划信息立即注入 LLM 上下文
- 同一时间只允许一个活跃计划（in_progress 或 pending）
- 每步执行完成后必须调用 `task_plan_step_done`，失败调用 `task_plan_step_fail`
- 步骤失败后计划自动暂停，等待用户介入或修改后继续

## 常见处理办法

- **已有活跃计划**：先 `task_plan_view` 查看当前计划，完成或 `task_plan_abort` 后再创建新计划
- **计划已暂停**：用户修改步骤后调用 `task_plan_edit`，计划自动恢复为 `in_progress`
- **用户未启用**：检查 `config.json` 中的 `task_plan.accept_task` 配置
- **计划生成失败**：检查子代理的 provider 配置是否可用

## 常见教训

- 防覆写机制：磁盘上已为 `aborted` 状态的计划不会被覆盖
- 计划原子写入：先写临时文件再 rename，防止写一半被读到
- 路径穿越校验：plan_id 通过 `validate_plan_filepath()` 统一校验，tool 层和 web 层共用
- `accept_task: false` 时计划仅为 `pending` 状态，不会自动执行