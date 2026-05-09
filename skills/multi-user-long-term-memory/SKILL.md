---
name: multi-user-long-term-memory
description: 多用户长期记忆工具。用户说"记住/保存/记录XX"时用 mem_save 存储，说"回忆/之前说过什么/帮我查下记忆"时用 mem_get/mem_search 检索。按用户隔离，跨会话持久化。
---

# Multi-User Long-Term Memory Skill

## 功能
为不同用户维护独立的长期记忆文件，记录用户的偏好、上下文、重要事项。

## 用户标识
用户名取自对话上下文中的用户身份信息。当 Agent 需要记忆某个用户的信息时，使用对应的 `mem_save`/`mem_append` 工具按用户 ID 存储。

## 使用场景
当用户主动或需要 Agent 记住以下内容时使用：
- 用户的个人信息、偏好设置
- 重要的事项或任务状态
- 跨会话需要保持的上下文信息

## 行为规则
1. 当用户表达「记住」「保存」「记录」等意图时，使用 `mem_save` 或 `mem_append` 存储
2. 当用户问「我之前说过什么」「帮我回忆」时，使用 `mem_get` 或 `mem_search` 检索
3. 不同用户的记忆天然隔离，无需额外区分
4. 记忆内容保存为纯文本 Markdown 格式
5. 响应与记忆相关的需求时，优先使用 `mem_*` 工具系列

## 底层实现
- 存储路径：`users/<username>/memory/<key>.md`
- 使用 `mem_save(user_id, key, content)` 保存
- 使用 `mem_get(user_id, key)` 读取
