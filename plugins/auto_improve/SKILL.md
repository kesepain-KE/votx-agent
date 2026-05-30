---
name: Auto_Improve
slug: auto_improve
version: 1.0.0
description: "双模式记忆管理：被动（自动触发）只读临时层、只写临时层，禁止触碰永久层；主动（用户触发审阅）读临时+永久、写永久+review_log.jsonl，禁止直接改临时层。"
---

## 用途

管理用户的三类持久数据，存储在 `users/<name>/improve/`：

| 类别 | 子目录 | 内容 |
|------|--------|------|
| 记忆 | `memory` | 事实、偏好、身份、知识 |
| 规则 | `self-improving` | 纠正记录、行为模式、改进规则 |
| 知识图谱 | `ontology` | 实体、关系、概念 |

## 层级

- **permanent**：用户主动触发审阅后写入，跨会话持久化，注入 system prompt
- **temporary**：消息达上限时自动触发写入，不注入 system prompt，作为待审阅暂存区

## 权限边界

### 被动模式（自动触发：消息达上限 / cron）

| 操作 | 临时层 | 永久层 |
|------|--------|--------|
| 读取 | 允许（已有临时内容，用于去重） | **禁止** |
| 写入 | 允许 | **禁止** |

### 主动模式（用户触发：调用 auto_improve_review / 说"审阅记忆"）

| 操作 | 临时层 | 永久层 |
|------|--------|--------|
| 读取 | 允许（待审阅 vs 已固化） | 允许（已固化内容，用于去重合并） |
| 写入 | **禁止** | 允许（创建/更新/删除）+ review_log.jsonl |

## 工具

| 工具 | 用途 | 触发 |
|------|------|------|
| `auto_improve_save` | 直接写入 permanent | 用户说"记住" |
| `auto_improve_get` | 读取（先查 permanent，再查 temporary） | 查询 |
| `auto_improve_search` | 关键词搜索全部记忆 | 查询 |
| `auto_improve_delete` | 删除记忆（两层都可） | 用户说"忘记" |
| `auto_improve_review` | 读 temporary + 对话 → 分析 → 晋升 permanent | 用户说"审阅记忆" |

## 两种触发流程

```
被动（消息达上限 / cron）
  → agents/auto_improve 读 temporary → 分析对话 → 写 temporary
  → 禁止读取或写入 permanent

主动（用户调用 auto_improve_review）
  → agents/auto_improve 读 temporary + permanent → 分析对话 → 写 permanent + review_log.jsonl
  → 禁止直接修改 temporary
```
