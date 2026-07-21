<p align="center">
  <img src="votx-agent.png" width="168" alt="votx-agent logo">
</p>

<h1 align="center">votx-agent</h1>

<p align="center">
  <strong>面向个人部署与跨终端自动化的本地多用户 Agent Framework。</strong>
</p>

<p align="center">
  以统一对话引擎与 VOTX 多模态网关为核心，集成工具调用、任务计划、持久记忆、知识库、外部消息路由与全栈多模态能力，<br>
  为个人智能助手、自动化工作流和多终端智能服务提供可部署、可扩展、可迁移的运行框架。
</p>

<p align="center">
  <a href="./LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-orange" alt="license">
  </a>
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="python">
  </a>
  <a href="https://github.com/kesepain-KE/llm-adapter-votx">
    <img src="https://img.shields.io/badge/provider-VOTX%20LLM%20Adapter-brightgreen" alt="provider">
  </a>
  <a href="https://flask.palletsprojects.com/">
    <img src="https://img.shields.io/badge/web-Flask%20%2B%20React%20%2B%20TypeScript-lightgrey" alt="web">
  </a>
</p>

<p align="center">
  中文 · <a href="./README_EN.md">English</a>
</p>

> [!NOTE]
> votx-agent 面向个人与小规模多用户部署，强调本地运行、统一工具链、多模态接入和跨平台消息交互。它与 kemo-agent 独立开发、独立维护，不存在继承关系。

---

## 项目定位

votx-agent 是一个本地优先、面向个人部署的多用户 AI Agent 框架。

它不是单纯的聊天前端，也不是只负责转发模型请求的 API 封装，而是一套能够长期运行、持续接收任务并连接多种终端的完整 Agent 系统。

框架围绕统一对话引擎构建，将以下能力整合到同一运行链路中：

- Web 与 CLI 交互
- 模型调用与流式事件输出
- 工具发现、调度与执行
- 任务计划与定时任务
- 临时记忆、永久记忆与自我改进
- 用户知识库与共享知识库
- QQ、Telegram 等外部消息入口
- 图像、语音、视频等多模态能力
- 用户级配置、历史与文件隔离

votx-agent 适合作为：

- 个人长期运行的本地智能助手
- 局域网内可访问的多终端 Agent 服务
- QQ、Telegram 等消息平台的智能处理核心
- 自动化任务、定时任务与多模态工作流的统一入口
- VOTX LLM Adapter 的上层 Agent 应用框架

---

## 核心特性

### 统一对话引擎

`run/engine.py` 是系统唯一的对话执行入口。

Web、CLI 和外部消息模块不重复实现 Agent 逻辑，只负责将输入转换为统一请求，并消费引擎输出的事件流。

核心运行链路：

```text
用户输入
→ ChatManager.add_user_message()
→ engine.run_chat_turn()
→ 构建 system prompt 与历史消息
→ Provider 流式响应
→ 检测并执行 tool_calls
→ 写入工具调用与工具结果
→ 继续模型循环
→ 提交最终回复与历史
```

模型与工具可以进行多轮循环，直至得到最终结果或达到 `MAX_TOOL_ROUNDS` 上限。

### 本地多用户隔离

每个用户拥有独立的数据空间：

```text
users/<name>/
├── config.json
├── self_soul.md
├── avatar/
├── history/
├── knowledge/
├── download/
├── task-plan/
├── tasks/
└── improve/
```

用户之间的以下资源相互隔离：

- Provider 配置
- 系统人格
- 对话历史
- 上传文件
- 下载文件
- 私有知识库
- 任务计划
- 定时任务
- 记忆与自我改进数据

### VOTX 多模态 Provider

votx-agent 通过纯 HTTP 方式接入 VOTX LLM Adapter，不依赖 OpenAI SDK。

同一 Provider 层可以统一承载：

- 文本生成
- 工具调用
- 图片识别
- 语音识别
- 图像生成
- 图像编辑
- 语音生成
- 语音生语音
- 视频生成

当 `base_url` 指向普通 OpenAI 兼容接口时，文本、工具调用和部分多模态能力仍可工作；图像编辑、视频生成和部分 ASR 路由等高级能力取决于目标接口是否实现对应端点。

### 工具优先工作流

框架优先使用专用 Skill 完成任务，例如：

- 文件操作
- 网络请求
- 下载
- 网页搜索
- 知识库检索
- 多模态处理
- 任务计划
- 定时任务
- 外部消息推送

`shell` 保留为诊断、构建和系统级操作能力，而不是所有任务的默认入口。

### 任务计划与定时任务

复杂请求可以先转换为结构化任务计划，再由用户批准后执行。

任务计划支持：

- 创建
- 查看
- 批准
- 暂停
- 继续
- 终止
- 进度记录

Cron 定时任务支持：

- 创建
- 查询
- 修改
- 删除
- 暂停
- 恢复
- 立即执行

### 分层记忆与自我改进

`auto_improve` 提供三类长期数据：

```text
memory
self-improving
ontology
```

系统支持临时记忆与永久记忆分层，并提供：

- 保存
- 搜索
- 审阅
- 晋升
- 删除
- 清理

被动模式主要处理临时层；主动审阅可以读取临时层与永久层，并将具有长期价值的内容晋升到永久层。

### 外部消息路由

消息模块可以将 QQ、Telegram 等平台接入同一 Agent 引擎。

支持：

- OneBot / NapCat
- Telegram Bot
- 用户身份绑定
- 图片、语音、视频和文件接收
- 外部命令
- 主动消息推送
- 推送队列
- 附件统一归档

### 本地优先与开放文件格式

主要数据以本地文件形式保存：

- JSON：配置与状态
- JSONL：历史与附件日志
- Markdown：知识库、人格、技能与操作手册
- 普通目录：上传文件、下载文件与媒体资源

用户可以直接查看、编辑、备份和迁移数据，不依赖封闭云端存储。

---

## 功能概览

| 子系统 | 主要能力 |
|---|---|
| 对话引擎 | Prompt 构建、流式响应、模型与工具多轮循环、历史提交 |
| Provider | VOTX LLM Adapter 与 OpenAI 兼容接口接入 |
| 多用户 | 配置、人格、历史、文件、知识库和任务独立隔离 |
| 工具系统 | 内置 Plugins 与用户 Skills 自动发现、加载与执行 |
| 多模态 | 识图、ASR、文生图、图像编辑、TTS、语音生语音、视频生成 |
| 任务计划 | 计划生成、审批、执行、暂停、恢复和终止 |
| 定时任务 | Cron 创建、更新、暂停、恢复、删除和立即执行 |
| 记忆系统 | 临时记忆、永久记忆、主动审阅与清理 |
| 知识库 | 用户私有知识库与全局共享知识库 |
| 消息路由 | OneBot、NapCat、Telegram、身份映射与附件处理 |
| Web 管理端 | Flask 后端、SSE 流式输出、React + TypeScript 前端 |
| Windows 打包 | PyInstaller 双 EXE，共享运行时，插件与技能外置 |

---

## 系统架构

```text
                        ┌──────────────────────────┐
                        │       User Inputs        │
                        │ Web / CLI / QQ / TG / Cron│
                        └─────────────┬────────────┘
                                      │
                        ┌─────────────▼────────────┐
                        │   Unified Chat Engine    │
                        │      run/engine.py       │
                        └───────┬─────────┬────────┘
                                │         │
                   ┌────────────▼─┐   ┌──▼─────────────┐
                   │   Provider   │   │ Tool / Skill   │
                   │ VOTX Adapter │   │   Execution    │
                   └──────┬───────┘   └──┬─────────────┘
                          │              │
                 ┌────────▼──────┐  ┌────▼─────────────┐
                 │ Text / Media  │  │ File / Network   │
                 │ Model Services│  │ Search / Tasks   │
                 └───────────────┘  └──────────────────┘
                                      │
                        ┌─────────────▼────────────┐
                        │  History / Memory / KB   │
                        │    Local User Storage    │
                        └──────────────────────────┘
```

### 对话执行链路

```text
请求进入
→ 读取用户配置与人格
→ 构建 system prompt
→ 加载当前会话历史
→ 调用 Provider
→ 输出文本与推理事件
→ 检测工具调用
→ 执行工具并写入结果
→ 继续模型循环
→ 保存最终回复
→ 更新历史、任务和记忆状态
```

---

## 快速开始

### 环境要求

- Python 3.10+
- Git
- Node.js 18+ 与 npm，仅在开发或重新构建 Web 前端时需要

### 获取源码

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
```

### 安装与初始化

```bash
python setup.py
python set_user.py add
```

### 启动 Web

```bash
python start_web.py
```

默认访问地址：

```text
http://localhost:1478
```

### 启动 CLI

```bash
python start.py
```

### 单次执行

```bash
python start.py --user <用户名> --prompt "<内容>" --once
```

---

## Provider 配置

votx-agent 使用统一的 VOTX Provider 实现。

配置中的 `provider.type` 保持为：

```json
{
  "provider": {
    "type": "votx"
  }
}
```

实际后端由 `base_url` 决定。

### 推荐模式

将 `base_url` 指向 VOTX LLM Adapter：

```env
VOTX_BASE_URL=http://127.0.0.1:8741/v1
VOTX_API_KEY=your-api-key
```

该模式可以获得完整的 VOTX 多模态能力。

### OpenAI 兼容模式

将 `base_url` 指向任意兼容 `/v1/chat/completions` 的服务，并填写对应 API Key。

此时：

- 文本能力通常可用
- 工具调用取决于目标服务兼容性
- 图片输入取决于目标模型能力
- 图像编辑、视频生成和部分音频能力可能不可用

### 配置优先级

```text
users/<name>/config.json
> 环境变量
> 程序默认值
```

### 配置职责

| 配置文件 | 职责 |
|---|---|
| `config/config_core.json` | 全局默认参数、历史、工具、任务、上下文窗口与改进配置 |
| `users/<name>/config.json` | 用户 Provider、权限、技能、历史和任务设置 |
| `.env` | 启动级参数、密钥与兼容兜底 |
| `message/config.local.json` | 外部消息私有配置 |
| `message/config.json` | 外部消息默认配置 |

### Provider 结构

```text
provider/
├── base.py          # BaseProvider 抽象接口
├── schema.py        # ToolCall 与 ProviderResponse
├── factory.py       # create_provider()
└── votx_adapter.py  # 纯 urllib HTTP Provider
```

---

## 多模态能力

### 能力声明

```text
vision
audio_transcription
image_generation
image_edit
speech_generation
speech_to_speech
video_generation
```

### 用户配置示例

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

模型选择优先级：

```text
专用能力模型 > 默认聊天模型
```

### 常用工具

| 工具 | 作用 |
|---|---|
| `vision_analyze` | 单图或多图识别 |
| `audio_transcribe` | 语音转文字、语言识别与时间戳 |
| `image_generate` | 文本生成图片 |
| `image_edit` | 基于输入图片执行编辑 |
| `speech_generate` | 文本生成语音 |
| `speech_to_speech` | 语音到语音转换 |
| `video_generate` | 创建视频生成任务 |
| `video_status` | 查询视频任务状态 |
| `video_download` | 下载生成结果 |

默认输出目录：

```text
users/<name>/download/
```

---

## Web 与 CLI

### Web 启动参数

```bash
python start_web.py
python start_web.py --port=8080
python start_web.py --host=0.0.0.0 --port=1478
```

### 局域网访问

```env
VOTX_HOST=0.0.0.0
PORT=1478
VOTX_SESSION_COOKIE_NAME=votx_agent_session
```

局域网设备访问：

```text
http://<服务器局域网IP>:1478
```

同一 IP 上运行多个 Web 项目时，应为每个项目设置不同的 `VOTX_SESSION_COOKIE_NAME`，避免 Cookie 冲突。

### 通用斜杠命令

| 命令 | 功能 |
|---|---|
| `/clear` | 清空当前会话历史与工具日志 |
| `/archive` | 归档当前会话并生成摘要 |
| `/new` | 归档当前会话后创建新会话 |
| `/summarize` | 生成当前会话摘要 |
| `/compress` | 压缩较早历史并保留近期上下文 |
| `/retry` | 删除上一条 AI 回复并重新生成 |
| `/history` | 查看会话统计 |
| `/stats` | 查看会话统计 |
| `/help` | 查看可用命令 |

### CLI 附加命令

```text
/exit
/quit
/q
```

退出 CLI 时会自动执行摘要与保存。

---

## 外部消息路由

### 配置优先级

```text
VOTX_MESSAGE_CONFIG
> message/config.local.json
> message/config.json
```

完整示例：

```text
message/config.example.json
```

### OneBot / NapCat

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

### Telegram

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

### 附件存储

外部附件：

```text
users/<用户名>/history/file/
```

附件日志：

```text
users/<用户名>/history/log/external_attachments.jsonl
```

支持的媒体类型：

| 平台 | 类型 |
|---|---|
| OneBot / NapCat | image、record、video、file |
| Telegram | photo、document、voice、audio、video |

外部消息命令：

```text
/cron list
/cron add
/cron update
/cron delete

/plan list
/plan view
/plan approve
/plan abort
```

详细配置见：

```text
knowledge/message-config.md
```

---

## 文件与知识库

| 路径 | 用途 |
|---|---|
| `users/<name>/config.json` | 用户模型、API Key、超时、工具和技能配置 |
| `users/<name>/self_soul.md` | 用户人格与 system prompt 叠加层 |
| `users/<name>/avatar/` | 用户头像 |
| `users/<name>/history/file/` | 上传文件与外部消息附件 |
| `users/<name>/download/` | 智能体生成和导出的文件 |
| `users/<name>/knowledge/` | 用户私有知识库 |
| `users/<name>/task-plan/` | 任务计划 |
| `users/<name>/tasks/` | 定时任务 |
| `users/<name>/improve/` | 记忆、自我改进与本体数据 |
| `knowledge/` | 全局知识库与框架说明 |
| `tmp/` | 临时脚本与中间缓存 |

### 知识库索引

用户知识库发生新增、修改、删除、移动或重命名后，需要同步更新：

```text
users/<name>/knowledge/data_structure.md
```

全局知识库发生变动后，需要同步更新：

```text
knowledge/data_structure.md
```

检索优先级：

```text
用户知识库 > 全局知识库
```

---

## Skills 与 Plugins

框架包含两类扩展目录：

| 目录 | 定位 |
|---|---|
| `plugins/` | 内置基础能力，更新脚本可能覆盖 |
| `skills/` | 用户扩展能力，更新脚本不会覆盖 |

当前源码包含 20 个插件目录：

- 18 个工具型 Skill
- 2 个指令型 Skill

### 内置能力

| Skill | 主要能力 |
|---|---|
| `file` | 文件读取、写入、追加、编辑、搜索、复制、移动与删除 |
| `shell` | 跨平台命令执行、cwd、环境变量、stdin 与会话状态 |
| `network` | HTTP 请求、网页读取与网络范围控制 |
| `download_anything` | 链接检查、文件与媒体下载 |
| `tavily_search` | 搜索、提取、爬取、站点地图与深度研究 |
| `time` | 当前时间与最长 30 分钟等待 |
| `audio_universal` | 语音转文字 |
| `vision_universal` | 本地图片与远程图片识别 |
| `image_generation` | 文本生成图片 |
| `image_edit` | 图片编辑 |
| `speech_generation` | 文本生成语音 |
| `speech_to_speech` | 语音生语音 |
| `video_generation` | 视频生成、查询和下载 |
| `auto_improve` | 记忆保存、搜索、审阅与清理 |
| `task_plan` | 复杂任务计划与进度管理 |
| `task_time` | Cron 定时任务管理 |
| `qq_send` / `qq_file` | QQ 与 Telegram 消息和文件推送 |
| `kb_retriever` | 双层知识库检索流程 |
| `skill_creator` | Skill 创建规范 |

### 核心技能

以下技能属于框架基础运行能力，不可禁用：

```text
file
shell
time
network
task_plan
auto_improve
skill_creator
task_time
kb_retriever
```

用户 Skill 可以通过：

```yaml
override: true
```

覆盖同名内置 Skill。

当前源码不再内置旧版 PDF、DOCX 与文档转换插件。二进制文档处理由用户 Skill、外部程序或其他服务承担。

---

## 项目结构

```text
votx-agent/
├── agents/             # 子智能体：auto_improve、task_plan
├── config/             # 全局配置与基座人格
├── cron/               # 定时任务调度器
├── knowledge/          # 全局知识库与架构文档
├── message/            # OneBot、Telegram、推送队列与身份映射
├── plugins/            # 内置 Skills
├── provider/           # VOTX Provider 与统一响应结构
├── run/                # 对话引擎、历史、工具调度、摘要与 Prompt 缓存
├── skills/             # 用户扩展 Skills
├── users/              # 用户配置、历史、文件、知识库和记忆
├── web/                # Flask + React + TypeScript + Vite
├── AGENTS.md           # 智能体操作手册
├── main.py             # CLI 入口
├── start.py            # CLI / Web 选择入口
├── start_web.py        # Web 启动入口
├── windows_entry.py    # Windows 双 EXE 分发入口
├── setup.py            # 环境安装脚本
├── set_user.py         # 用户管理脚本
├── update.py           # 全平台更新脚本
├── paths.py            # 开发与 PyInstaller 路径解析
├── version.json        # 版本信息
├── requirements.txt    # Python 依赖
├── votx-agent.spec     # PyInstaller 打包规格
├── build_windows.bat   # Windows 构建脚本
└── LICENSE             # MIT License
```

---

## 更新

### 检查版本

```bash
python update.py --check
```

### 执行更新

```bash
python update.py --yes
```

### 预览更新

```bash
python update.py --dry-run
```

更新流程：

1. 比较本地与远程 `version.json`
2. 浅克隆最新源码到临时目录
3. 备份当前框架文件
4. 同步代码并跳过用户数据与构建产物
5. 处理 `config/` 与 `knowledge/`
6. 补齐用户目录结构
7. 刷新 Python 依赖

更新前建议手动备份：

```text
users/
skills/
.env
message/config.local.json
message/push_queue/
```

---

## Windows 打包

### 双 EXE 架构

PyInstaller 使用 `onedir` 模式生成两个入口：

```text
votx-agent-web.exe
votx-agent-cli.exe
```

两个 EXE 共享同一套 `_internal` 运行时。

插件、技能、配置和用户目录位于 EXE 外部，因此仍然支持：

- 热插拔
- 配置修改
- 用户数据持久化
- 独立更新
- Skill 扩展

### 构建命令

```cmd
build_windows.bat
```

### 主要打包内容

```text
votx-agent-web.exe
votx-agent-cli.exe
_internal/

agents/
config/
cron/
message/
plugins/
provider/
run/
skills/
web/
users/
tmp/
knowledge/

paths.py
AGENTS.md
set_user.py
setup.py
start.py
start_web.py
main.py
update.py
windows_entry.py
requirements.txt
version.json
.env.example
```

敏感配置、缓存和本地状态不会进入发行包。

---

## 开发

### Python 检查

```bash
python -m py_compile <file.py>
python -m compileall -q .
```

### Web 前端

```bash
cd web
npm install
npm run dev
npm run build
npx tsc --noEmit
```

### 维护者文档

```text
AGENTS.md
knowledge/
使用手册-AI/
```

---

## 与相邻项目的关系

### VOTX LLM Adapter

[VOTX LLM Adapter](https://github.com/kesepain-KE/llm-adapter-votx) 是 votx-agent 的多模态 Provider 网关。

它负责：

- 统一不同模型服务的接口
- 提供多模态能力路由
- 处理模型、媒体与端点适配

votx-agent 负责：

- 对话运行
- 工具调用
- 任务计划
- 记忆与知识库
- Web、CLI 和消息入口
- 用户数据管理

### kemo-agent

kemo-agent 是另一套独立开发的 Agent Runtime。

两者定位不同：

| 项目 | 定位 |
|---|---|
| votx-agent | 面向个人部署、跨终端交互和多模态服务的完整 Agent 框架 |
| kemo-agent | 面向生命周期记忆、结构化编排和长期运行的多用户 Agent Runtime |

两者不存在继承关系，也不共享内部实现。

### 其他相关项目

- [NapCat](https://github.com/NapNeko/NapCatQQ) — QQ 消息接入
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — 视频与音频下载引擎

---

## 当前边界

votx-agent 当前主要面向个人与小规模多用户环境。

在以下场景中应进行额外验证和加固：

- 大规模公网部署
- 高并发多租户服务
- 严格的企业级权限审计
- 不可信用户的任意代码执行环境
- 高可用集群与分布式调度
- 关键业务生产系统

`shell`、网络访问、文件操作与外部消息能力均具有较高权限，部署者应根据实际环境配置工具白名单、网络范围和用户访问控制。

---

## 主要维护者

[@kesepain](https://github.com/kesepain-KE)

---

## 参与贡献

欢迎提交：

- [Issue](https://github.com/kesepain-KE/votx-agent/issues)
- [Pull Request](https://github.com/kesepain-KE/votx-agent/pulls)

涉及核心架构的大规模改动，建议先创建 Issue 讨论。

推荐流程：

```bash
git checkout -b feature/your-feature
git commit -m "feat: describe your change"
git push origin feature/your-feature
```

贡献前建议阅读：

```text
AGENTS.md
```

---

## 贡献人员

感谢所有参与项目开发、测试与文档维护的贡献者。

[@kesepain](https://github.com/kesepain-KE)

---

## 开源协议

本项目基于 [MIT License](./LICENSE) 开源。

Copyright © kesepain