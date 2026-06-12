# 项目简介

[![standard-readme compliant](https://img.shields.io/badge/readme%20style-standard-brightgreen.svg?style=flat-square)](https://github.com/RichardLitt/standard-readme)

<p align="center"><img src="votx-agent.png" width="160" alt="votx-agent"></p>

# votx-agent

[![License](https://img.shields.io/badge/license-MIT-orange)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![LLM](https://img.shields.io/badge/LLM-OpenAI%20compatible%20%7C%20Anthropic-brightgreen)](https://platform.openai.com/)
[![Web](https://img.shields.io/badge/web-Flask%20%2B%20React%20%2B%20TypeScript-lightgrey)](https://flask.palletsprojects.com/)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](https://www.docker.com/)

中文 | [English](./README_EN.md)

## 目录

- [背景](#背景)
- [安装](#安装)
- [模型配置](#模型配置)
- [多模态](#多模态)
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

VOTX Agent 是一个本地多用户 AI Agent 框架，支持 Web UI、CLI、工具调用、任务计划、持久记忆、自我改进、外部消息路由和多模态能力。当前版本见 [version.json](./version.json)。

### 特性

- **多 Provider**：OpenAI 兼容接口、Responses API、Chat Completions、Anthropic Messages API。
- **多用户隔离**：每个用户独立 `config.json`、`self_soul.md`、历史、文件、记忆和知识库。
- **Web + CLI 共用引擎**：`run/engine.py` 统一处理 system prompt、tool_calls、历史保存。
- **Skills/Plugins 架构**：`plugins/` 为内置技能，`skills/` 为用户拓展技能。
- **工具优先工作流**：文件、网络、下载、PDF、DOCX、知识库等任务优先走专用 Skill/工具，shell 作为最后的诊断和构建手段。
- **任务计划**：复杂请求可生成计划，Web UI 批准后执行，支持暂停、继续、终止。
- **auto_improve**：临时记忆与永久记忆分层，支持主动审阅与清理。
- **外部消息路由**：QQ/NapCat/OneBot 与 Telegram，可接收图片、语音、文件。
- **多模态能力**：图像识别、语音识别、图像生成、语音生成按 Provider 能力启用。
- **全局/用户知识库**：`knowledge/` 全局共享，`users/<name>/knowledge/` 用户私有。
- **Linux/Docker 更新脚本**：`update.py` 更新框架代码并保留用户数据。

![VOTX Agent Web UI](votx-agent-web-UI.png)

## 安装

### Docker

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
bash install_docker.sh
```

或手动启动：

```bash
docker compose up -d
```

访问：

```text
http://localhost:1478
```

创建用户：

```bash
docker exec -it votx-agent python set_user.py add
```

Docker 外部消息配置建议放在：

```text
message-runtime/config.json
```

并设置：

```env
VOTX_MESSAGE_CONFIG=/app/message-runtime/config.json
```

### Linux 原生

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
bash install.sh
votx
```

### Windows

开发运行：

```powershell
python start_web.py
```

Windows 打包：

```cmd
build_windows.bat
```

构建完成后生成：

```text
dist\votx-agent-windows.zip
```

Windows 特供版不执行自动更新脚本，只在启动 Web 时提示本地/远程版本。

### 手动安装

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
python setup.py
python set_user.py add
python start_web.py
```

## 模型配置

推荐在用户配置中填写模型和 API Key：

```text
users/<用户名>/config.json
```

OpenAI 兼容示例：

```json
{
  "provider": {
    "type": "openai",
    "api_style": "chat",
    "model": "deepseek-chat",
    "api_key": "<your-api-key>",
    "base_url": "https://api.deepseek.com",
    "stream": true,
    "think": false
  }
}
```

Anthropic 示例：

```json
{
  "provider": {
    "type": "anthropic",
    "model": "claude-3-5-sonnet-latest",
    "api_key": "<your-api-key>",
    "stream": true
  }
}
```

环境变量只作为兜底：

```env
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
TAVILY_API_KEY=tvly-xxx
```

优先级：

```text
users/<name>/config.json > 环境变量 > 程序默认值
```

## 多模态

能力名：

```text
vision
audio_transcription
image_generation
speech_generation
```

高级配置：

```json
{
  "provider": {
    "capabilities_override": [
      "vision",
      "audio_transcription",
      "image_generation",
      "speech_generation"
    ],
    "audio_transcription_model": "whisper-1",
    "image_generation_model": "dall-e-3",
    "speech_generation_model": "tts-1"
  }
}
```

调用优先级：

```text
专用模型配置 > 默认聊天模型
```

常用工具：

| 工具 | 说明 |
|---|---|
| `vision_analyze` | 图片识别，支持多图 |
| `audio_transcribe` | 语音转文字 |
| `image_generate` | 文生图，默认输出到 `users/<name>/download/` |
| `speech_generate` | 文生语音，默认输出到 `users/<name>/download/` |

## 用法

```bash
python start_web.py
python start_web.py --port=8080
python start.py
python start.py --user <用户名> --prompt "<内容>" --once
```

Ubuntu 安装后：

```bash
votx
votx cli
votx web --port=8080
```

常用斜杠命令：

| 命令 | 说明 |
|---|---|
| `/clear` | 清空当前对话 |
| `/new` | 归档当前对话并开启新对话 |
| `/archive` | 手动归档 |
| `/summarize` | 生成摘要 |
| `/retry` | 重试上一轮 |
| `/stats` | 查看统计 |
| `/help` | 查看帮助 |

## 外部消息路由

配置文件优先级：

```text
VOTX_MESSAGE_CONFIG
message/config.local.json
message/config.json
```

Docker 推荐：

```text
message-runtime/config.json
```

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
        "qq:123456789": "kesepain"
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
        "tg:987654321": "kesepain"
      }
    }
  }
}
```

外部附件统一保存到：

```text
users/<用户名>/history/file/
```

附件日志：

```text
users/<用户名>/history/log/external_attachments.jsonl
```

支持：

- OneBot/NapCat：image、record、video、file
- Telegram：photo、document、voice、audio、video
- 外部命令：`/cron list|add|update|delete`、`/plan list|view|approve|abort`

## 文件与知识库

| 路径 | 用途 |
|---|---|
| `users/<name>/history/file/` | Web 上传文件、外部消息附件、用户原始材料 |
| `users/<name>/download/` | 智能体生成、导出、下载的默认输出（报告、文档、表格、图片、语音、视频、压缩包等） |
| `users/<name>/knowledge/` | 用户私有知识库 |
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

核心内置技能不可禁用：

```text
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

`network_scope` 支持 `public` / `local` / `private` / `all`。云元数据地址始终应被拦截。

## 项目结构

```text
votx-agent/
├── agents/             # 子智能体：auto_improve、task_plan
├── config/             # 全局配置与基座人格
├── cron/               # 定时任务调度
├── knowledge/          # 全局知识库
├── message/            # OneBot/NapCat、Telegram、推送队列
├── message-runtime/    # Docker 外部消息运行配置
├── plugins/            # 内置技能
├── provider/           # OpenAI 兼容、Anthropic、多模态能力层
├── run/                # 对话引擎、历史、工具调度
├── skills/             # 用户拓展技能
├── users/              # 用户数据
├── web/                # Flask + React + TypeScript + Vite
├── AGENTS.md           # 智能体操作手册
├── update.py           # Linux/Docker 更新脚本
├── version.json        # 当前版本
└── build_windows.bat   # Windows 打包脚本
```

## 更新

Linux 原生：

```bash
python update.py --check
python update.py --native
```

Docker：

```bash
python update.py --check
python update.py --docker
```

更新会覆盖框架代码和 `plugins/`，保留 `users/`、`skills/`、`.env`、`message-runtime/` 和消息运行队列。`knowledge/` 更新时会询问合并、跳过或全量覆盖。

## Windows 打包内容

Windows 压缩包包含：

```text
agents/ config/ cron/ message/ message-runtime/ plugins/ provider/ run/
skills/ web/ users/ tmp/ knowledge/
paths.py AGENTS.md set_user.py setup.py version.json .env.example
```

不包含：

```text
update.py tests/ 使用手册-AI/ tools/ web/node_modules/
message/config.json message/config.local.json message/identity/identity_map.json
message/push_queue/ .env .session_secret *.pyc *.pyo __pycache__/
```

## 开发

```bash
python -m py_compile <file.py>
python -m compileall -q .

cd web
npm install
npm run dev
npm run build
npx tsc --noEmit
```

维护者文档：

```text
开发文档.md
开发文档/
AGENTS.md
knowledge/
使用手册-AI/
```

## 相关项目

- [OpenAI API](https://platform.openai.com/docs)
- [Anthropic API](https://docs.anthropic.com/)
- [NapCat](https://github.com/NapNeko/NapCatQQ)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

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
