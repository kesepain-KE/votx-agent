---
name: Task_Plan
slug: task_plan
version: 1.0.0
description: "将复杂用户请求自动分解为可执行步骤计划，可视化进度，支持暂停/继续/中止。受用户 config.json 中 task_plan.accept_task 控制。"
---

## 用途

管理任务计划的完整生命周期，存储在 `users/<name>/task-plan/`。

| 阶段 | 工具 | 说明 |
|------|------|------|
| 创建 | `task_plan_create` | 调用子代理分析对话 → 生成结构化执行计划 |
| 查看 | `task_plan_list` / `task_plan_view` | 列出所有计划 / 查看单个详情 |
| 执行 | `task_plan_step_done` / `task_plan_step_fail` | 标记步骤完成或失败 |
| 控制 | `task_plan_abort` | 中止计划并跳过未完成步骤 |
| 编辑 | `task_plan_edit` | 修改步骤描述或参数 |

## 子代理

`agents/task_plan/agent.py::generate_plan()` — 同步 LLM 调用，无流式无工具。

输入：完整对话 + 可用工具列表 + 技能目录 + system prompt
输出：`{plan: {title, description, steps[{id, description, tool_calls[...], status}]}}`

## 状态枚举

| 计划 | 步骤 |
|------|------|
| pending | pending |
| in_progress | in_progress |
| completed | completed |
| paused | failed |
| aborted | skipped |

## 配置控制

用户 config.json 中 `task_plan.accept_task`:
- `true` → 允许 AI 自动创建计划
- `false` / 未设置 → task_plan_create 返回错误

## 存储

```
users/<name>/task-plan/plan_<uuid8hex>.json
```
