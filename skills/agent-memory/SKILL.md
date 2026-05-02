---
name: agent-memory
description: "持久记忆系统 — 记住事实(mem_remember)、回忆信息(mem_recall)、记录经验教训(mem_learn)、追踪人/项目/实体(mem_track_entity)。当你需要主动存储或查询跨会话信息时使用——比如用户告诉你个人信息、偏好，或者你想回顾之前学到的教训。"
---

# AgentMemory Skill

Persistent memory system for AI agents. Remember facts, learn from experience, and track entities across sessions.

## 工具

| 工具 | 用途 |
|------|------|
| `mem_remember` | 记住一条事实，跨会话持久化 |
| `mem_recall` | 搜索回忆已记住的信息 |
| `mem_learn` | 记录经验教训（成功/失败） |
| `mem_get_lessons` | 获取已记录的经验教训 |
| `mem_track_entity` | 追踪人/项目/公司/工具及其属性 |
| `mem_get_entity` | 查询已追踪实体的信息 |
| `mem_stats` | 查看记忆系统统计信息 |

## 使用时机

- 用户告诉你个人信息、偏好、重要事项 → `mem_remember`
- 需要回忆之前的信息 → `mem_recall`
- 操作失败或用户纠正时 → `mem_learn`
- 用户介绍自己、团队、项目时 → `mem_track_entity`
