# knowledge/ 目录结构

VOTX Agent 全局知识库索引。此目录存放所有用户共享的框架说明；用户私有资料应放入 `users/<name>/knowledge/`。

更新时间：2026-07-12

## 配置与部署

| 文件 | 用途 | 检索关键词 |
|---|---|---|
| `data_structure.md` | 全局知识库索引（本文件） | 索引、知识库 |
| `deployment.md` | 安装、启动、Web host/port、环境变量、消息配置、打包、update.py | 部署、环境变量、更新 |
| `message-config.md` | OneBot/NapCat、Telegram、账号绑定、附件、推送队列 | QQ、Telegram、附件 |
| `users-config.md` | 用户目录、`config.json`、Provider、多模态、历史、工具权限、技能禁用 | 用户配置、Provider、tool |

## 架构原理

| 文件 | 用途 | 检索关键词 |
|---|---|---|
| `01-system-prompt拼接架构.md` | 当前 Prompt 拼接顺序、Skill/知识索引注入、mtime 缓存 | system prompt、缓存 |
| `02-对话历史保留与压缩原理.md` | ChatManager、历史持久化、条数/Token 压缩和手动 `/compress` | 历史、压缩、Token |
| `03-工具调用原理.md` | Skill 注册、ToolRunner、调用循环、JSON 配置控制、当前插件边界 | tool_calls、ToolRunner、Skill |
| `04-memory生命周期执行原理.md` | memory/self-improving/ontology 与主动/被动模式 | 记忆、review |
| `05-临时记忆生命周期执行原理.md` | 临时记忆创建、注入、过期清理和转永久 | temporary、cleanup |
| `06-定时任务执行位置.md` | CLI/Web 调度、任务上下文和结果推送 | cron、定时任务 |
| `07-消息路由编号原理.md` | 外部身份映射、OneBot/Telegram 路由、推送队列状态 | 消息路由、编号 |
| `08-任务计划实际执行原理.md` | 计划生成、审批、状态机、磁盘文件和执行驱动 | task plan、审批 |
| `09-智能体工作规范.md` | 双 JSON 配置权威、目录职责、当前已解除/保留的控制、文档工具边界 | 工作规范、限制、路径 |
| `10-回复渲染与工具产物展示.md` | Markdown 正文、工具卡片、artifacts 和媒体展示 | 渲染、artifact |

## 当前文档口径

- 配置以 `config/config_core.json` 与 `users/<name>/config.json` 为主。
- `.env` 仅用于源码仍读取的启动参数和兼容兜底。
- 当前源码不包含 旧版内置文档转换、PDF 与 DOCX 插件。
- file/shell/network/download 不再使用旧路径白名单、命令黑名单或 network_scope 环境变量；ToolRunner 仍执行 JSON 配置中的 enabled/deny/禁用 Skill/tool_timeout。
- `knowledge/` 文件发生增删改移后必须同步本索引。

## 检索规则

1. 先查 `users/<name>/knowledge/`，再查本目录。
2. 用户私有信息默认写入用户级知识库。
3. 全局库只存共享说明或用户明确要求的资料。
4. 不把大段正文复制到索引。
