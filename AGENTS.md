# AGENTS.md

votx-agent 项目智能体的操作手册。应以当前源码和配置为准，不把旧版本文档当作事实。

> 冲突优先级：用户明确指令 > 本文件 > `config/soul.md` > Skill 说明。

## 1. 配置权威

运行行为主要由两层 JSON 配置决定：

1. `config/config_core.json`：框架全局默认值。
2. `users/<name>/config.json`：用户 Provider、历史、工具权限、超时、技能和任务计划配置；用户值覆盖全局默认值。

`.env` 只承载源码仍直接读取的启动级参数和兼容兜底，不应重新承担工具沙箱、命令黑名单或网络范围策略。可用变量以 `.env.example` 和源码为准。

必须遵守：

- 不读取、打印或记录真实 API Key、token、password。
- 不用 `.env` 中的真实内容作示例。
- 不擅自修改其他用户配置或数据。
- 配置和文档冲突时先核对源码，不猜。

## 2. 工作方式

1. **先读**：修改前读取目标文件、相邻实现和对应 Skill 的 `SKILL.md`。
2. **再判**：确认目标、配置来源、数据范围和最小修改面。
3. **后动**：能用专用工具就不用 shell；没有等价工具时才使用短小、可解释的命令。
4. **验证**：Python 改动做语法检查；前端改动构建；文档改动检查路径和源码一致性。
5. **交付**：说明做了什么、依据、仍存在的限制和未完成项。

复杂请求满足以下任一条件时优先创建任务计划：3 个以上独立步骤、跨多文件、批量操作、存在依赖关系，或用户明确要求计划。

同一命令连续失败 3 次必须停止，说明目标、错误和继续条件。

### 时间与时效问题

凡问题或任务涉及当前时间、日期、星期、时区、期限、相对时间（如“今天”“明天”“多久后”）、定时任务执行时间或信息时效判断，必须先调用 `time` Skill 的 `get_time` 获取真实的 UTC 与本地时间，再进行回答、换算或创建任务。不得仅依赖 system prompt、历史消息中的时间戳或自行推算当前时间；用户明确提供的目标时区或绝对时间仍应与工具结果核对。

## 3. 项目结构

```text
provider/          Kemo Provider 适配层
run/               对话引擎、历史、ToolRunner、摘要和 prompt 缓存
web/               Flask + React/TypeScript/Vite
plugins/           内置 Skills
skills/            用户拓展 Skills
agents/            auto_improve、task_plan 子智能体
message/           OneBot/NapCat、Telegram、附件和推送队列
cron/              定时任务调度
config/            config_core.json 与全局基座人格
knowledge/         全局共享知识和框架说明
users/<name>/      用户配置、历史、文件、任务和记忆
tmp/               临时中间产物
```

默认目录职责：

| 路径 | 用途 |
|---|---|
| `users/<name>/history/file/` | 用户上传和外部附件 |
| `users/<name>/download/` | 智能体生成、导出和下载的产物 |
| `users/<name>/knowledge/` | 用户私有知识库 |
| `users/<name>/task-plan/` | 任务计划 |
| `users/<name>/tasks/` | 定时任务 |
| `users/<name>/improve/` | memory/self-improving/ontology |
| `knowledge/` | 全局共享知识库 |
| `tmp/` | 临时工作文件 |

这些是数据分类和默认落点，不是“只能访问这些目录”的路径沙箱。文件工具当前使用 `safe_path()` 统一解析相对/绝对路径，不做旧版目录白名单判断。

## 4. Skill 与工具

收到请求先判断是否命中 Skill，并读取：

```text
plugins/<name>/SKILL.md
skills/<name>/SKILL.md
```

优先级：专用 Skill/工具 > 文件或网络基础工具 > shell。

当前内置插件：

```text
audio_universal  auto_improve       download_anything
file             image_edit         image_generation
kb_retriever     network            qq_file
qq_send          shell              skill_creator
speech_generation speech_to_speech  task_plan
task_time        tavily_search      time
video_generation vision_universal
```

当前源码不包含 旧版内置文档转换、PDF 与 DOCX 插件。不要调用不存在的工具，也不要把 PDF/Office 处理能力写入提示词。二进制文档需要用户安装的拓展 Skill、外部程序或独立服务。

### ToolRunner 中仍真实存在的控制

`run/tool.py` 保留以下配置级机制：

- `tool.enabled`
- `tool.deny`（优先）
- `skills.disabled_builtin`
- `tool.tool_timeout`
- 用户取消工具执行

这些由 `config_core.json` 和用户 `config.json` 控制，不是硬编码沙箱，不应绕过。工具 schema 过滤和执行层会进行双重技能禁用检查。

### 已解除的旧限制口径

当前实现中：

- 文件路径只做解析和存在/类型检查，不做项目根/用户目录白名单限制。
- shell 没有硬编码危险命令黑名单或工作目录沙箱，支持 cwd、env、stdin 和会话状态。
- network 没有 `network_scope` 或内网/回环/SSRF 地址拦截参数，仅保留请求超时、代理和可选 SSL 验证。
- download 可使用调用方给出的输出目录。
- 旧文件、下载和网络范围环境变量不再是有效控制面。

不要在文档或回复中宣称仍存在上述旧沙箱。也不要把路径解析、超时、文件存在检查、非法文件名清理、日志和删除确认误删为“沙箱”。

## 5. 文件操作与数据保护

- 新文本使用 UTF-8；读取旧中文文件可回退 UTF-8 BOM/GBK。
- 小范围修改用精确编辑，大范围重写前先读原文件。
- 不覆盖、移动、删除与任务无关的数据。
- 删除、覆盖、批量移动等不可逆操作必须确认目标范围；用户已在任务计划中批准的明确步骤可直接执行。
- `delete_file` 只删除文件；目录清理由受控命令或文件 API 严格限定目标。
- 临时文件放 `tmp/`，任务完成后按需清理。

以上是数据保护和稳定性要求，不代表旧版路径沙箱。

## 6. 双层知识库

| 层级 | 路径 | 默认行为 |
|---|---|---|
| 用户级 | `users/<name>/knowledge/` | 优先检索、默认写入 |
| 全局级 | `knowledge/` | 兜底检索；仅共享资料或用户明确要求时写入 |

规则：

1. 检索时用户级优先、全局级兜底。
2. 用户私有资料不得写入全局库。
3. 任一知识库新增、修改、删除、移动或重命名后，同步最近的 `data_structure.md`。
4. 索引记录路径、用途、来源、更新时间和关键词，不复制大段正文。
5. 二进制资料的索引只描述格式和建议处理方式，不虚构不存在的文档工具。

配置、部署和框架行为优先查：

```text
knowledge/data_structure.md
knowledge/users-config.md
knowledge/deployment.md
knowledge/message-config.md
```

## 7. Provider 与多模态

`provider.type` 统一为 `"kemo"`。`base_url` 可以指向 Kemo LLM Adapter 或 OpenAI 兼容 API。

能力名：

```text
vision
audio_transcription
image_generation
image_edit
speech_generation
speech_to_speech
video_generation
```

专用模型配置优先于默认聊天模型。Provider 不支持某项能力时明确说明，不私自切换 Provider。

常用工具：`vision_analyze`、`audio_transcribe`、`image_generate`、`image_edit`、`speech_generate`、`speech_to_speech`、`video_generate`、`video_status`、`video_download`。

## 8. 外部消息

- OneBot/NapCat 使用正向 WebSocket。
- Telegram 使用 Bot API 长轮询。
- `bound_users` 将外部账号映射到内部用户。
- 外部附件保存到 `users/<name>/history/file/`。
- 附件日志位于 `users/<name>/history/log/external_attachments.jsonl`。
- 主动推送使用 `qq_send` / `qq_file`；对外发送前确认目标、平台和内容。
- 不手动改动未发送推送队列，除非用户明确要求。

## 9. 任务计划、定时任务与记忆

### 任务计划

- `task_plan.accept_task=true`：计划创建后自动批准。
- `false`：创建后等待 Web UI 批准。
- 每步完成/失败调用对应状态工具。
- 计划暂停后等待用户继续，不自动恢复。

### 定时任务

`task_time` 管理 `daily`、`once`、`recurring`。任务以所属用户配置和历史上下文执行。

### auto_improve

- 被动模式：读临时+永久，写临时。
- 主动审阅：读临时+永久，写永久与审阅日志。
- 永久记忆不自动删除；密钥和敏感凭据不得写入长期记忆。

## 10. 回复与工具产物

- 正文使用普通 Markdown。
- 工具结果自动进入下一轮 LLM 上下文。
- `artifacts[]` 只控制前端附加展示，不替代正文。
- 图片气泡由图像工具产物产生；正文 Markdown 图片不作为工具产物。
- 文件 artifact 提供下载和路径复制。
- 不确定是否应转成 artifact 时保留文本。

## 11. 部署与更新

项目包含 `update.py`：

```text
python update.py --check
python update.py --dry-run
python update.py --yes
```

更新前备份 `users/`、`skills/`、`.env`、消息私有配置和推送队列。启动过程会补齐用户目录骨架，不应覆盖已有用户配置和文件。

Web：

```text
python start_web.py --host=0.0.0.0 --port=1478
```

同一 IP 部署多个实例时，为每个实例设置不同的 `VOTX_SESSION_COOKIE_NAME`。

## 12. 最小自检

Python：

```text
python -m py_compile <changed_file.py>
```

前端：

```text
cd web
npm run build
```

文档：检查文件路径、Skill 名称、配置字段和中英文能力清单是否与源码一致。

## 13. 手册维护

源码行为变化时依次检查：

```text
README.md
README_EN.md
AGENTS.md
knowledge/data_structure.md
knowledge/*.md
使用手册-AI/*.md
```

知识库文件发生变化才需要更新知识库索引；只改代码或 AGENTS.md 不为形式额外改索引。任何文档都不得继续传播已删除插件、无效环境变量或不存在的安全限制。
