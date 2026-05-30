---
name: Auto_Improve
slug: auto_improve
version: 1.0.0
description: "用户主动触发的永久记忆/规则/知识图谱管理。自动触发写入临时层。"
---

## 用途

管理用户的三类持久数据，存储在 `users/<name>/improve/`：

| 类别 | 子目录 | 内容 |
|------|--------|------|
| 记忆 | `memory` | 事实、偏好、身份、知识 |
| 规则 | `self-improving` | 纠正记录、行为模式、改进规则 |
| 知识图谱 | `ontology` | 实体、关系、概念 |

## 层级

- **permanent**：用户主动触发，跨会话持久化，注入 system prompt
- **temporary**：消息达上限时自动触发，不注入 system prompt

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
被动（消息达上限）
  → agents/auto_improve 读 permanent → 分析对话 → 写 temporary

主动（用户调用 auto_improve_review）
  → agents/auto_improve 读 temporary → 分析对话 → 写 permanent
```
