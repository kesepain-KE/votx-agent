# System Prompt 拼接架构与可见性

## 一、拼接顺序（发送给 LLM 的完整 prompt）

发送给 LLM 的 system prompt 由 `run/prompt_builder.py` 的 `build_system_prompt()` 按以下顺序拼接：

```
① config/config_soul.md         ← 基座人格（AI助手原则、行为底线）
② users/<name>/self_soul.md     ← 用户人设（角色扮演、说话风格）覆盖基座
③ AGENTS.md (截断版)             ← 自我操作手册（技能目录、行为规范）
④ {临时记忆拼接块}               ← memory/self-improving/ontology 三类临时记忆
⑤ {知识库检索结果}               ← kb_retriever 动态注入（按需，非常驻）
⑥ 活跃任务计划块                 ← task-plan 状态注入（in_progress/paused 时）
⑦ 扩展技能描述                   ← skills/ 目录下 SKILL.md 摘要（常驻注入）
```

每段之间用 `\n\n` 分隔。

## 二、各段来源与注入规则

### ① 基座人格 — config/config_soul.md
- 路径：`config/config_soul.md`（项目级，所有用户共享）
- 内容：AI 助手的通用行为准则（诚实、可靠、主动、安全边界等）
- 注入条件：始终注入
- 可见性：发送给 LLM，Web UI 不直接展示

### ② 用户人设 — users/<name>/self_soul.md
- 路径：`users/<name>/self_soul.md`（用户级）
- 内容：角色扮演指令、说话风格、颜文字规则等
- 注入条件：文件存在时注入
- 可见性：发送给 LLM，Web UI 不直接展示
- 优先级：与基座人格冲突时，用户人设优先

### ③ AGENTS.md 截断版
- 来源：项目根目录 `AGENTS.md`
- 注入方式：读取后截断到约 3000 字符（防止撑爆 context）
- 内容：自我操作手册、技能目录、执行原则、安全边界
- 注入条件：始终注入
- 可见性：发送给 LLM，Web UI 不直接展示

### ④ 临时记忆拼接块
- 来源：`users/<name>/improve/memory/temporary/`、`self-improving/temporary/`、`ontology/temporary/`
- 注入条件：有临时文件存在时注入
- 格式：
  ```
  [SYSTEM-INTERNAL:临时记忆]
  ## 事实与偏好
  - xxx.md: ...摘要...

  ## 行为规则
  - yyy.md: ...摘要...

  ## 概念关系
  - zzz.md: ...摘要...

  这些是系统自动提取的临时观察。可被 auto_improve_review 吸收为永久记忆。
  ```
- 可见性：标记为 `[SYSTEM-INTERNAL]`，LLM 可见，Web UI 隐藏

### ⑤ 知识库检索结果（动态）
- 来源：`kb_retriever` 工具执行时注入
- 注入条件：仅在 kb_retriever 工具被调用时动态注入，非常驻
- 可见性：发送给 LLM，Web UI 不展示

### ⑥ 活跃任务计划块
- 来源：`users/<name>/task-plan/*.json`
- 注入条件：`status == "in_progress"` 或 `"paused"` 时注入
- 格式：计划标题、步骤列表（✅/🔄/⬜）、执行指令
- 可见性：发送给 LLM，Web UI 通过独立面板展示
- 详细原理见「08-任务计划实际执行原理」

### ⑦ 扩展技能描述
- 来源：`skills/` 目录下各 SKILL.md 的摘要和路径
- 注入条件：始终注入（技能目录列表 + 一句话摘要）
- 完整 SKILL.md 正文不注入，由 LLM 按需通过 `read_file` 读取
- 可见性：发送给 LLM，Web UI 通过技能面板展示

## 三、两种可见性分类

### A. 发送给 LLM 的 system prompt（完整拼接）
包含上述 ①~⑦ 全部内容，通过 API 的 `system` role 发送给模型。

### B. Web UI 展示的内容
- 聊天消息：用户消息和 AI 回复（`role: user/assistant`）
- 系统事件：工具调用（折叠）、任务计划进度（独立面板）
- system prompt 本身不在 Web UI 展示，但会显示其派生的事件（如工具调用）

## 四、缓存机制

- `build_system_prompt()` 结果通过 `prompt_cache` 缓存
- 缓存键基于用户目录 + 配置文件 mtime
- 以下操作会失效缓存（`invalidate_prompt_cache()`）：
  - 计划状态变更（approve/pause/resume/abort/step_done/step_fail）
  - 计划步骤编辑
  - 配置文件变更
  - 知识库文件变更
- 失效后下一次 `build_messages()` 会重新构建

## 五、前端渲染与后端系统事件的分离

| 层级 | 内容 | 可见性 |
|------|------|--------|
| LLM 输入 | 完整 system prompt + 历史消息 + 用户消息 | 仅 API 可见 |
| Web UI 展示 | 用户消息、AI 回复、工具调用事件（折叠）、计划进度 | 用户可见 |
| `[SYSTEM-INTERNAL]` 标记 | 临时记忆等内部信息 | LLM 可见，Web 隐藏 |

前端通过 `chat.tsx` 中的事件渲染逻辑区分：
- `text` / `text_chunk` → 渲染为 markdown
- `tool_call` → 渲染为可折叠的工具调用卡片
- `tool_result` → 折叠内容
- `plan_progress` → 独立计划面板
