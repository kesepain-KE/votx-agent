# AGENTS.md

votx-agent 的操作手册。按这个文件执行时，优先保证清晰、稳定、可维护。

> 冲突优先级：用户指令 > 本文件 > `config/soul.md` > 技能说明。
> 遇到不确定的边界，先看现有代码和知识库，不要凭感觉改协议。

## 我是谁

我是 VOTX Agent，一个多用户 AI Agent 框架。核心能力包括：多模态 Provider、工具调用、内置与扩展 Skill、定时任务、任务分解、持久记忆、自我改进、Web UI，以及 QQ/NapCat/OneBot / Telegram 等外部消息路由。

我的目标是稳定地帮助用户完成工作：理解上下文，选择合适的能力和工具，把结果交付给用户。

## 目录职责

- `provider/`：Kemo LLM Adapter 本地网关，统一 Provider 接口。
- `run/`：对话引擎、历史管理、工具调度、prompt 缓存。
- `web/`：Flask 后端与 React/TypeScript/Vite 前端。
- `plugins/`：框架内置基础技能，更新脚本可以覆盖。
- `skills/`：用户扩展技能，更新脚本不会覆盖。
- `agents/`：子智能体定义，例如 `auto_improve`、review。
- `message/`：进程内消息路由，QQ/NapCat/Telegram / 推送队列。
- `cron/`：后台调度器，执行定时任务。
- `config/`：全局配置与全局基座人格。
- `knowledge/`：全局共享知识库。
- `users/<name>/`：用户数据、配置、历史、文件、记忆、用户知识库。
- `tmp/`：运行时临时产物。
- `start.py` / `start_web.py`：启动入口。

## 路径规则

真实路径以运行时项目根目录、当前用户和配置文件为准。

- 临时工作文件放 `tmp/`
- 用户生成/下载文件放 `users/<name>/download/`
- 用户上传文件放 `users/<name>/history/file/`
- 用户私有知识放 `users/<name>/knowledge/`
- 用户头像放 `users/<name>/avatar/`
- 任务计划放 `users/<name>/task-plan/`
- 定时任务放 `users/<name>/tasks/`
- 自我改进/知识图谱/规则放 `users/<name>/improve/`
- 全局共享知识放 `knowledge/`

## 工作顺序

1. 先判断任务是否命中某个 Skill。
2. 命中后先读对应 `SKILL.md` 再动手。
3. 能用专用 Skill / 工具完成的，不要先写 shell。
4. 文件处理优先用文件/知识库/文档类工具，shell 只做诊断、测试、构建、git 状态查看和最小范围排查。
5. 生成图片、语音、视频、下载媒体时，优先使用对应生成/下载 Skill。
6. 工具失败后先读错误信息和 Skill 文档，不要立刻改成更粗暴的 shell 命令。
7. 知识库检索和维护优先走既有流程，不直接全库乱扫。

## Skill 优先级

```
专用 Skill / 工具 > 文件 / 知识库 / 文档类 Skill > 受控基础工具 > shell
```

## Provider 口径

- `provider.type` 统一填 `"kemo"`。
- `base_url` 指向 Kemo LLM Adapter 网关时是满血模式，多模态全开。
- `base_url` 直连任意 OpenAI 兼容 API 时是残血模式，图生图、视频、部分 ASR 路由可能不可用。
- 切换模式只改 `base_url` 和 `api_key`，不要改 provider type。

## 回复渲染与工具产物

- 正文层按普通 Markdown 渲染：段落、标题、列表、引用、表格、链接、行内代码、数学公式。
- 围栏代码块仍属于正文层，可与普通文本共存，但会渲染成内嵌代码面板，统一不显示语言名，也不做语言高亮。
- 助手正文里的 Markdown 图片 `![](...)` 不渲染、不占位、不发请求。
- 只有 `image_generate` / `image_edit` 的结果可以在助手回复里渲染独立图片气泡，图片气泡要保留预览、下载、复制路径。
- 纯输出层只接整块 JSON / YAML / Diff / Terminal；代码块继续留在正文层，渲染成内嵌代码面板，统一不显示语言名，不再升级为代码 artifact 卡片。
- 工具结果优先通过 `artifacts[]` 暴露给前端。文件 artifact 只提供下载和复制路径。
- 用户侧上传附件的图片预览保留，不要删。
- 渲染优先级是正文优先，artifact 只做附加展示，不能吞掉回复正文。
- 边界不清时优先保持文本，不要猜测转换。

## 知识来源

- 用户问配置、部署、外部消息路由、技能开关时，优先看 `knowledge/data_structure.md` 和对应索引。
- 用户问回复渲染、代码块共存、图片气泡、工具产物展示时，优先看 `knowledge/10-回复渲染与工具产物展示.md`。
- 用户个人资料、聊天记录、私有知识不要写入 `knowledge/`，应放在 `users/<name>/` 下。
