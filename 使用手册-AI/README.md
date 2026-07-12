# votx-agent AI 使用手册

更新时间：2026-07-12

本目录不再维护 `knowledge/` 的逐文件副本。重复文档过去经常出现两边内容不同步、已删除插件仍被引用的问题，因此已收口为单一入口。

## 权威文档

| 主题 | 文件 |
|---|---|
| 项目概览与安装 | `../README.md` |
| 英文说明 | `../README_EN.md` |
| 智能体操作规则 | `../AGENTS.md` |
| 全局知识库索引 | `../knowledge/data_structure.md` |
| 部署和环境变量 | `../knowledge/deployment.md` |
| 用户配置 | `../knowledge/users-config.md` |
| QQ/Telegram 路由 | `../knowledge/message-config.md` |
| System Prompt | `../knowledge/01-system-prompt拼接架构.md` |
| 历史与压缩 | `../knowledge/02-对话历史保留与压缩原理.md` |
| 工具调用 | `../knowledge/03-工具调用原理.md` |
| 记忆生命周期 | `../knowledge/04-memory生命周期执行原理.md`、`05-临时记忆生命周期执行原理.md` |
| 定时任务 | `../knowledge/06-定时任务执行位置.md` |
| 消息路由 | `../knowledge/07-消息路由编号原理.md` |
| 任务计划 | `../knowledge/08-任务计划实际执行原理.md` |
| 工作规范与限制现状 | `../knowledge/09-智能体工作规范.md` |
| 回复渲染 | `../knowledge/10-回复渲染与工具产物展示.md` |

## 当前关键口径

- 运行配置主要由 `config/config_core.json` 与 `users/<name>/config.json` 控制。
- `.env` 仅保留启动级参数和兼容兜底。
- 当前没有 旧版内置文档转换、PDF 与 DOCX 插件 内置插件。
- file/shell/network/download 的旧沙箱和 network_scope 开关已不再生效。
- ToolRunner 仍服从两层 JSON 中的工具开关、deny、禁用 Skill 和执行超时。

后续只更新权威文件，不再把整套文档复制到本目录。
