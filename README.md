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

## 目录

- [项目定位](#项目定位)
- [核心特性](#核心特性)
- [功能概览](#功能概览)
- [系统架构](#系统架构)
- [快速开始](#快速开始)
- [Provider 配置](#provider-配置)
- [多模态能力](#多模态能力)
- [Web 与 CLI](#web-与-cli)
- [外部消息路由](#外部消息路由)
- [文件与知识库](#文件与知识库)
- [Skills 与 Plugins](#skills-与-plugins)
- [项目结构](#项目结构)
- [更新](#更新)
- [Windows 打包](#windows-打包)
- [开发](#开发)
- [与相邻项目的关系](#与相邻项目的关系)
- [当前边界](#当前边界)
- [参与贡献](#参与贡献)
- [开源协议](#开源协议)

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

Web、CLI 和外部消息模块共用同一对话引擎，不重复实现 Agent 逻辑。

引擎负责构建 system prompt、管理对话历史、调用模型、检测并执行工具调用，支持模型与工具的多轮循环直至得到最终结果。

### 本地多用户隔离

每个用户拥有独立的数据空间，以下资源在用户之间相互隔离：

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

同一 Provider 层统一承载多项能力：

- 文本生成
- 工具调用
- 图片识别
- 语音识别
- 图像生成
- 图像编辑
- 语音生成
- 语音生语音
- 视频生成

接入 VOTX LLM Adapter 可获得完整多模态能力；也可直连任意 OpenAI 兼容接口，此时部分高级能力取决于目标是否实现对应端点。

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

系统支持临时记忆与永久记忆分层管理，提供保存、搜索、审阅、晋升、删除和清理能力。

被动模式主要处理临时层；主动审阅可读取双层层数据，将具有长期价值的内容晋升到永久层。

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

<p align="center"><img src="votx-agent-web-UI.png" width="720" alt="votx-agent Web UI"></p>

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

### 接入方式

支持 OneBot/NapCat（QQ）和 Telegram Bot 两种平台，通过配置文件绑定用户身份，支持图片、语音、视频和文件接收，以及外部命令和主动消息推送。完整配置示例见 `message/config.example.json`。

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

每个用户拥有独立的配置、人格、上传文件、下载文件、私有知识库、任务计划和记忆存储空间。

双层知识库设计：用户私有知识库优先，全局共享知识库兜底。知识库变动时需同步更新对应索引文件。

---

## Skills 与 Plugins

框架包含两类扩展目录：`plugins/`（内置基础能力）和 `skills/`（用户扩展能力）。更新脚本覆盖前者，保留后者。

当前内置 20 个 Skill，覆盖文件操作、命令执行、网络请求、下载、搜索、多模态处理（识图/ASR/文生图/图像编辑/TTS/语音转换/视频生成）、记忆管理、任务计划、定时任务、消息推送、知识库检索等场景。其中部分核心技能不可禁用以确保框架基础运行。

用户 Skill 可通过 `override: true` 覆盖同名内置 Skill。二进制文档处理由用户 Skill 或外部工具承担。

---

## 项目结构

```text
votx-agent/
├── agents/             # 子智能体
├── config/             # 全局配置与基座人格
├── cron/               # 定时任务调度
├── knowledge/          # 全局知识库与架构文档
├── message/            # 外部消息路由与推送
├── plugins/            # 内置 Skills
├── provider/           # Provider 适配层
├── run/                # 对话引擎与工具调度
├── skills/             # 用户扩展 Skills
├── users/              # 用户数据空间
├── web/                # Web 管理端
├── setup.py            # 环境安装
├── set_user.py         # 用户管理
├── update.py           # 全平台更新
├── start_web.py        # Web 启动
├── start.py            # CLI 启动
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

更新前建议手动备份 `users/`、`skills/`、`.env` 和消息私有配置。

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

敏感配置、缓存和本地状态不会进入发行包。

---

## 开发

Web 前端基于 React + TypeScript + Vite，Python 代码使用标准工具链。维护者可参考 `AGENTS.md` 及 `knowledge/` 下的架构文档。贡献前建议先阅读 `AGENTS.md`。

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

## 参与贡献

欢迎提交 [Issue](https://github.com/kesepain-KE/votx-agent/issues) 或 [Pull Request](https://github.com/kesepain-KE/votx-agent/pulls)。涉及核心架构的大规模改动，建议先创建 Issue 讨论。贡献前建议阅读 `AGENTS.md`。

**维护者**: [@kesepain](https://github.com/kesepain-KE)

感谢所有参与项目开发、测试与文档维护的贡献者。

---

## 开源协议

本项目基于 [MIT License](./LICENSE) 开源。

Copyright © kesepain