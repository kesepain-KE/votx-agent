# 项目简介

[![standard-readme compliant](https://img.shields.io/badge/readme%20style-standard-brightgreen.svg?style=flat-square)](https://github.com/RichardLitt/standard-readme)

<p align="center"><img src="votx-agent.png" width="160" alt="votx-agent"></p>

# votx-agent

[![License](https://img.shields.io/badge/license-MIT-orange)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Kemo](https://img.shields.io/badge/LLM-Kemo%20LLM%20Adapter-brightgreen)](https://github.com/kesepain-KE/llm-adapter-kemo)
[![Web](https://img.shields.io/badge/web-Flask%20%2B%20React%20%2B%20TypeScript-lightgrey)](https://flask.palletsprojects.com/)

中文 | [English](./README_EN.md)

## 目录

- [背景](#背景)
- [安装](#安装)
- [Provider 配置](#provider-配置)
- [多模态能力](#多模态能力)
- [用法](#用法)
- [外部消息路由](#外部消息路由)
- [文件与知识库](#文件与知识库)
- [Skills / Plugins](#skills--plugins)
- [项目结构](#项目结构)
- [更新](#更新)
- [Windows 打包内容](#windows-打包内容)
- [开发](#开发)
- [相关项目](#相关项目)
- [主要项目负责人](#主要项目负责人)
- [参与贡献方式](#参与贡献方式)
  - [贡献人员](#贡献人员)
- [开源协议](#开源协议)

## 背景

votx-agent 是一个本地单用户（多用户数据隔离）AI Agent 框架，支持 Web UI、CLI、工具调用、任务计划、持久记忆、自我改进、外部消息路由和多模态能力。当前版本 v2.3.3。

### 架构概览

```
用户输入 → ChatManager.add_user_message()
  → engine.run_chat_turn()
    → 循环:
      1. chat.build_messages() → system prompt + 历史
      2. provider.respond_stream() → yield SSE 事件
      3. 如有 tool_calls → tool_runner.execute()
      4. chat.add_tool_call_message() + add_tool_results()
      5. 回到步骤 1（最多 MAX_TOOL_ROUNDS 轮）
    → 最终文本回复 → chat.add_assistant_message()
```

`run/engine.py` 是唯一对话引擎入口。CLI (`main.py`) 和 Web (`web/routes/`) 都调用它，只负责消费事件流并渲染。Web 后端是 Flask + SSE；前端是 React + TypeScript + Vite。

### 特性

- **单 Provider（Kemo LLM Adapter）**：纯 HTTP 本地多模态网关，不依赖 OpenAI SDK，所有模型和能力通过 Kemo 统一路由。
- **多用户数据隔离**：每个用户独立 `config.json`、`self_soul.md`、历史、文件、记忆和知识库。
- **Web + CLI 共用引擎**：`run/engine.py` 统一处理 system prompt、tool_calls、历史保存。
- **Skills/Plugins 架构**：`plugins/` 为内置技能，`skills/` 为用户拓展技能。
- **工具优先工作流**：文件、网络、下载、PDF、DOCX、知识库等任务优先走专用 Skill/工具，shell 作为最后的诊断和构建手段。
- **任务计划**：复杂请求可生成计划，Web UI 批准后执行，支持暂停、继续、终止。
- **auto_improve**：临时记忆与永久记忆分层，支持主动审阅与清理。
- **外部消息路由**：QQ/NapCat/OneBot 与 Telegram，可接收图片、语音、文件，支持推送队列。
- **全栈多模态能力**：图像识别、语音识别、图像生成、图像编辑、语音生成、语音生语音、视频生成，按 Provider 能力启用。
- **全局/用户知识库**：`knowledge/` 全局共享，`users/<name>/knowledge/` 用户私有。

![VOTX Agent Web UI](votx-agent-web-UI.png)

## 安装

### 普通 Python 运行

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
python setup.py
python set_user.py add
python start_web.py
```

访问：

```
http://localhost:1478
```

### Windows 打包

```cmd
build_windows.bat
```

构建完成后生成：

```
dist\votx-agent-windows.zip
```

启动 Web 时会提示本地/远程版本。

## Provider 配置

votx-agent 仅支持 Kemo LLM Adapter 作为 Provider。推荐在用户配置中填写：

```
users/<用户名>/config.json
```

创建用户时模型菜单可选 `stepfun-step-3.7-flash`、`deepseek-v4-flash` 等模型，也可手动输入其他模型名。

Kemo 配置示例：

```json
{
  "provider": {
    "type": "kemo",
    "model": "stepfun-step-3.7-flash",
    "api_key": "sk-kemo-deepseek",
    "base_url": "http://127.0.0.1:8741/v1",
    "stream": true,
    "timeout": 240
  }
}
```

环境变量只作为兜底：

```env
KEMO_API_KEY=sk-kemo-your-key-here
KEMO_BASE_URL=http://127.0.0.1:8741/v1
TAVILY_API_KEY=tvly-xxx
```

优先级：

```
users/<name>/config.json > 环境变量 > 程序默认值
```

### Provider 架构

```
provider/
├── base.py          # BaseProvider 抽象接口（respond / respond_stream + 全部多模态能力接口）
├── schema.py        # ToolCall + ProviderResponse 统一数据结构
├── factory.py       # create_provider() → 仅支持 type: "kemo"
└── kemo_adapter.py  # Kemo LLM Adapter Provider — 纯 urllib HTTP 实现，无 OpenAI SDK 依赖
```

KemoProvider 通过纯 `urllib` HTTP 直接调用 Kemo LLM Adapter 的端点，不依赖 OpenAI SDK 或任何第三方库。所有聊天、流式、多模态能力均通过此单一实现完成。

## 多模态能力

能力声明：

```
vision
audio_transcription
image_generation
image_edit
speech_generation
speech_to_speech
video_generation
```

高级配置（在 `users/<name>/config.json` 的 `provider` 中）：

```json
{
  "provider": {
    "capabilities_override": [
      "vision",
      "audio_transcription",
      "image_generation",
      "image_edit",
      "speech_generation",
      "speech_to_speech",
      "video_generation"
    ],
    "audio_transcription_model": "stepfun-stepaudio-2.5-asr",
    "image_generation_model": "",
    "image_edit_model": "stepfun-step-image-edit-2",
    "speech_generation_model": "stepfun-stepaudio-2.5-tts",
    "speech_to_speech_model": "",
    "video_generation_model": ""
  }
}
```

调用优先级：

```
专用模型配置 > 默认聊天模型
```

常用工具：

| 工具 | 说明 |
|---|---|
| `vision_analyze` / `vision_universal` | 图片识别，支持多图 |
| `audio_transcribe` | 语音转文字 |
| `image_generate` | 文生图，默认输出到 `users/<name>/download/` |
| `image_edit` | 图像编辑（需 Kemo 支持），默认输出到 `users/<name>/download/` |
| `speech_generate` | 文生语音，默认输出到 `users/<name>/download/` |
| `speech_to_speech` | 语音生语音，默认输出到 `users/<name>/download/` |
| `video_generate` / `video_status` / `video_download` | 视频生成、查询和下载（需 Kemo 支持） |

## 用法

```bash
# 启动 Web UI
python start_web.py
python start_web.py --port=8080
python start_web.py --host=0.0.0.0 --port=1478

# CLI 模式
python start.py

# 单次模式
python start.py --user <用户名> --prompt "<内容>" --once
```

局域网访问：

```env
VOTX_HOST=0.0.0.0
PORT=1478
VOTX_SESSION_COOKIE_NAME=votx_agent_session
```

启动后同一局域网设备访问 `http://<服务器局域网IP>:1478`。如果同一 IP 下部署多个不同 Web 项目，建议为每个项目配置不同的 `VOTX_SESSION_COOKIE_NAME`，避免浏览器 Cookie 名冲突导致登录态互相挤掉。

斜杠命令（Web UI 和 CLI 共用）：

| 命令 | 说明 |
|---|---|
| `/clear` | 清空当前对话历史及工具日志 |
| `/archive` | 归档当前对话并生成摘要 |
| `/new` | 归档当前对话摘要后开启新对话 |
| `/summarize` | 生成当前对话摘要 |
| `/retry` | 移除上一条 AI 回复并重新生成 |
| `/history` 或 `/stats` | 查看当前会话统计 |
| `/help` | 查看可用命令列表 |

CLI 额外支持：

| 命令 | 说明 |
|---|---|
| `/exit` / `/quit` / `/q` | 退出 CLI（自动摘要 + 保存） |

## 外部消息路由

配置文件优先级：

```text
VOTX_MESSAGE_CONFIG 环境变量
message/config.local.json（若存在）
message/config.json（默认）
```

完整配置示例见 `message/config.example.json`。

OneBot/NapCat 示例：

```json
{
  "enabled": true,
  "platforms": {
    "onebot": {
      "enabled": true,
      "ws_url": "ws://127.0.0.1:3001",
      "access_token": "",
      "bound_users": {
        "qq:123456789": "alice"
      }
    }
  }
}
```

Telegram 示例：

```json
{
  "enabled": true,
  "platforms": {
    "telegram": {
      "enabled": true,
      "bot_token": "<telegram-bot-token>",
      "proxy": "http://127.0.0.1:7890",
      "bound_users": {
        "tg:987654321": "alice"
      }
    }
  }
}
```

外部附件统一保存到：

```
users/<用户名>/history/file/
```

附件日志：

```
users/<用户名>/history/log/external_attachments.jsonl
```

支持：

- OneBot/NapCat：image、record、video、file
- Telegram：photo、document、voice、audio、video
- 外部命令：`/cron list|add|update|delete`、`/plan list|view|approve|abort`

## 文件与知识库

| 路径 | 用途 |
|---|---|
| `users/<name>/config.json` | 用户模型、Key、超时、工具和技能配置 |
| `users/<name>/self_soul.md` | 用户人设文件，作为 system prompt 叠加层 |
| `users/<name>/avatar/` | 用户头像 |
| `users/<name>/history/file/` | Web 上传文件、外部消息附件、用户原始材料 |
| `users/<name>/download/` | 智能体生成、导出、下载的默认输出（报告、文档、表格、图片、语音、视频、压缩包等） |
| `users/<name>/knowledge/` | 用户私有知识库 |
| `users/<name>/task-plan/` | 任务计划存储 |
| `users/<name>/tasks/` | 定时任务存储 |
| `users/<name>/improve/` | 自改进三层记忆：memory / self-improving / ontology |
| `knowledge/` | 全局共享知识库 |
| `tmp/` | 临时脚本、中间缓存、测试样本，用完清理 |

知识库变动必须同步索引：

- 用户知识库新增、修改、删除、重命名、移动后，更新 `users/<name>/knowledge/data_structure.md`。
- 全局知识库新增、修改、删除、重命名、移动后，更新 `knowledge/data_structure.md`。
- 查询时用户知识库优先，全局知识库兜底。

## Skills / Plugins

| 目录 | 说明 |
|---|---|
| `plugins/` | 框架内置基础技能，更新脚本可覆盖 |
| `skills/` | 用户拓展技能，更新脚本永不覆盖 |

常用内置工具能力：

| Skill | 主要能力 |
|---|---|
| `file` | 文件读取、范围读取、写入、追加、精确编辑、目录树、搜索、复制、移动、建目录、删除文件 |
| `network` | `http_get`、`http_post`、`web_read`，支持 `network_scope` 控制公网/本机/内网访问 |
| `download_anything` | 链接检查、直链下载、视频下载、下载列表 |
| `markdown_converter` | PDF/Office/HTML 等文档转 Markdown |
| `pdf_tools` | PDF 信息、提取、拆分、合并、旋转、盖字、水印、预览、OCR、脱敏、视觉对比 |
| `word_docx` | DOCX 创建和读取，支持排版、表格、图片、模板、页码、目录 |
| `tavily_search` | Tavily 搜索、网页提取、站点爬取、站点地图、深度研究 |
| `time` | 当前时间、最长 30 分钟等待 |
| `audio_universal` | 语音转文字，支持多语言和时间戳 |
| `vision_universal` | 通用识图，支持本地图片和远程 URL |
| `image_generation` | 文生图，支持多种尺寸和质量 |
| `speech_generation` | 文生语音，支持多种语音风格 |
| `image_edit` | 图像编辑（需 Provider 支持） |
| `video_generation` | 视频生成、查询和下载（需 Provider 支持） |
| `speech_to_speech` | 语音生语音（需 Provider 支持） |
| `task_time` | cron 定时任务管理 |
| `qq_send` / `qq_file` | 外部消息推送 |

核心内置技能不可禁用：

```
file shell time network task_plan auto_improve skill_creator task_time kb_retriever
```

用户技能可通过 `override: true` 覆盖同名内置技能。

已收口的旧插件：

| 旧插件 | 当前归属 |
|---|---|
| `file_search` | 已并入 `file.search_files` |
| `video_download` | 已并入 `download_anything.download_video` |
| `web_content_fetcher` | 已并入 `network.web_read` |

### 工具沙箱与网络范围

常用环境变量：

```env
VOTX_FILE_OUTSIDE_SANDBOX=1
VOTX_FILE_READ_OUTSIDE_SANDBOX=1
VOTX_FILE_EDIT_OUTSIDE_SANDBOX=1
VOTX_FILE_DELETE_OUTSIDE_SANDBOX=1
VOTX_DOWNLOAD_ANYTHING_OUTSIDE_SANDBOX=1
VOTX_NETWORK_SCOPE=public
HTTP_NETWORK_SCOPE=public
NETWORK_SCOPE=public
HTTP_TIMEOUT=30
HTTP_VERIFY_SSL=0
```

`network_scope` 支持 `public` / `local` / `private` / `all`。云元数据地址始终被拦截。

## 项目结构

```text
votx-agent/
├── agents/             # 子智能体：auto_improve、task_plan
├── config/             # 全局配置 (config_core.json) 与基座人格 (soul.md)
├── cron/               # 定时任务调度器
├── knowledge/          # 全局知识库（含架构原理文档）
├── message/            # 外部消息路由：OneBot/NapCat、Telegram、推送队列、身份映射
├── plugins/            # 内置技能（30+ 个工具型/指令型 Skill）
├── provider/           # Kemo LLM Adapter Provider — 纯 HTTP 本地网关适配层
├── run/                # 对话引擎、历史管理、工具调度、摘要、prompt 缓存
├── skills/             # 用户拓展技能
├── users/              # 用户数据（配置、历史、文件、知识库、记忆）
├── web/                # Flask + React + TypeScript + Vite
├── AGENTS.md           # 智能体操作手册
├── main.py             # CLI 入口
├── start.py            # CLI/Web 入口（用户选择）
├── start_web.py        # Web 专用入口
├── setup.py            # 环境安装脚本
├── set_user.py         # 用户管理脚本
├── paths.py            # 路径解析（开发/PyInstaller 通用）
├── version.json        # 当前版本
├── requirements.txt    # Python 依赖清单
├── build_windows.bat   # Windows 打包脚本
└── LICENSE             # MIT 许可证
```

## 更新

当前仓库不包含自动更新脚本。更新源码时请手动拉取新版代码，并在覆盖前备份 `users/`、`skills/`、`.env`、`message/config.local.json` 和消息队列。

## Windows 打包内容

Windows 压缩包包含：

```text
agents/ config/ cron/ message/ plugins/ provider/ run/
skills/ web/ users/ tmp/ knowledge/
paths.py AGENTS.md set_user.py setup.py version.json .env.example
```

不包含：

```text
tests/ 使用手册-AI/ tools/ web/node_modules/
message/config.json message/config.local.json message/identity/identity_map.json
message/push_queue/ .env .session_secret *.pyc *.pyo __pycache__/
```

## 开发

```bash
# 语法检查
python -m py_compile <file.py>
python -m compileall -q .

# Web 前端
cd web
npm install
npm run dev      # 开发模式
npm run build    # 生产构建
npx tsc --noEmit # TypeScript 检查
```

维护者文档：

```text
AGENTS.md
knowledge/
使用手册-AI/
```

## 相关项目

- [Kemo LLM Adapter](https://github.com/kesepain-KE/llm-adapter-kemo) — 本地多模态 LLM 网关，votx-agent 的 Provider 后端
- [NapCat](https://github.com/NapNeko/NapCatQQ) — QQ 机器人框架
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — 视频下载引擎

## 主要项目负责人

[@kesepain](https://github.com/kesepain-KE)

## 参与贡献方式

欢迎提交 [Pull Request](https://github.com/kesepain-KE/votx-agent/pulls) 或 [Issue](https://github.com/kesepain-KE/votx-agent/issues)。

大改动请先开 Issue 讨论。贡献前建议阅读 [AGENTS.md](./AGENTS.md)。

### 贡献人员

感谢所有贡献的人。
[@kesepain](https://github.com/kesepain-KE)

## 开源协议

[MIT](./LICENSE) © kesepain
