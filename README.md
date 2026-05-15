<p align="center"><img src="votx-agent.png" width="160" alt="votx-agent"></p>

# votx-agent

[![License](https://img.shields.io/badge/license-MIT-orange)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Multi-LLM](https://img.shields.io/badge/LLM-OpenAI%20%7C%20Anthropic-brightgreen)](https://platform.deepseek.com/)
[![Flask](https://img.shields.io/badge/web-Flask%20%2B%20React%20%2B%20TypeScript-lightgrey)](https://flask.palletsprojects.com/)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](https://www.docker.com/)

中文 | [English](./README_EN.md)

多用户 AI Agent 框架 —— 角色人设、工具调用、持久记忆、自学习闭环。同时提供 CLI 和 Web UI，共享同一对话引擎。

## 目录

- [背景](#背景)
- [安装](#安装)
  - [Docker 部署](#docker-部署)
  - [Ubuntu 原生部署](#ubuntu-原生部署)
  - [手动安装](#手动安装)
- [用法](#用法)
- [外部消息路由](#外部消息路由)
- [项目结构](#项目结构)
- [Skill 与工具](#skill-与工具)
- [核心设计](#核心设计)
- [配置](#配置)
- [依赖](#依赖)
- [开发](#开发)
- [相关项目](#相关项目)
- [主要项目负责人](#主要项目负责人)
- [参与贡献方式](#参与贡献方式)
- [开源协议](#开源协议)

## 背景

Github 上现有的 AI Agent 框架大多面向单用户、英文场景，交互停留在命令行或 API。votx-agent 面向中文用户，提供：

- **双协议支持**：OpenAI 协议（Responses API / Chat Completions）和 Anthropic 协议（Messages API），统一内部格式
- **多厂商接入**：DeepSeek / Anthropic / Azure / 硅基流动 / Groq / 小米 mimo 等，改 base_url 即切
- **多用户隔离**：每个用户独立人设（`self_soul.md`）、对话历史、长期记忆、知识库和文件空间
- **双层知识库**：用户级（默认读写）+ 全局级（只读共享），分层索引导航，支持 PDF/Excel 检索
- **双端支持**：React Web UI + CLI 终端，共用 `run/engine.py` 对话引擎，行为完全一致
- **任务计划**：复杂请求自动分解为分步计划，Web UI 进度气泡实时追踪，支持批准/暂停/中止
- **自学习**：工具调用成功/失败均生成学习记录，下次对话自动注入相关教训，形成正向迭代
- **定时任务**：cron 定时调度、遗忘曲线管理，Web UI 状态面板集成
- **长对话友好**：自动 token 压缩 + 摘要归档，上下文不超限

> 本项目是 [kesepain-KE](https://github.com/kesepain-KE) 仓库的一部分，持续迭代中。

## 安装

### 环境要求

- Python 3.10 及以上版本（Docker 部署无需安装）

### 获取 API Key

支持以下任意厂商（通过 Web 调试面板或 `config.json` 切换）：

- [DeepSeek](https://platform.deepseek.com/api_keys) — 免费额度可用
- [Anthropic Claude](https://console.anthropic.com/) — Messages API
- [OpenAI](https://platform.openai.com/) — Responses API / Chat Completions
- 其他兼容 OpenAI 协议的厂商（硅基流动、Groq、小米 mimo 等）

可选：
- [Tavily Search](https://tavily.com/) —— 联网搜索 Skill 需要
- [UAPI](https://uapi.icu/) —— 热榜查询 Skill 需要

### Docker 部署

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
docker compose up -d
```

也可以使用辅助脚本完成目录初始化、镜像构建和启动：

```bash
bash install_docker.sh
```

容器启动后，选择一种方式配置 Key：

**方式 A：创建用户（推荐，每用户独立 Key）**

```bash
docker exec -it votx-agent python set_user.py add
# 交互式输入用户名、模型、API Key 等
```

**方式 B：配置全局 .env**

编辑项目目录下的 `.env`，填入 Key 后重启：

```bash
docker compose restart
```

配置完成后访问 `http://localhost:1478`。

如果要从 Docker 连接外部 NapCat 容器，请在 `message-runtime/config.json` 中填写可从 votx-agent 容器访问的正向 WebSocket 地址，例如 `ws://host.docker.internal:3001`（NapCat 在宿主机）或 `ws://napcat:3001`（同一 Docker 网络内的 NapCat 服务名）。

### Ubuntu 原生部署

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
bash install.sh
```

`install.sh` 会依次完成：虚拟环境创建 → 依赖安装 → 注册 `votx` 命令 → **交互式创建用户**（可当场填写独立 API Key）。

安装完成后直接启动：

```bash
votx        # 启动 Web UI → http://localhost:1478
```

### 手动安装

如果你不想使用上述方式：

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
python setup.py          # 安装依赖 + 引导配置 .env（可选）
python set_user.py add   # 创建用户（可在此填写独立 API Key，.env 可跳过）
```

### Windows 打包构建 (PyInstaller)

如果你希望在 Windows 下将本项目打包为单个独立目录的可执行应用，可以使用提供的构建脚本：

```cmd
build_windows.bat
```

脚本会安装 Python 依赖、检查并安装 `pyinstaller`、构建前端并执行打包。完成后生成 `dist\votx-agent-windows.zip`，解压后双击 `votx-agent.exe` 即可运行 Web UI（也可通过命令行附加 `--port=1478` 等参数启动）。

`.env` 模板参考（兜底，`config.json` 优先）：

```bash
# OpenAI 协议（兜底，Web/CLI 中 config.json 的 api_key 优先）
DEEPSEEK_API_KEY=sk-your-key-here
# DEEPSEEK_BASE_URL=https://api.deepseek.com

# Anthropic 协议（兜底）
# ANTHROPIC_API_KEY=sk-ant-your-key-here

# 可选工具 Key
# UAPI_API_KEY=your-uapi-key
# TAVILY_API_KEY=your-tavily-key
```

## 用法

### 启动

```bash
# Ubuntu（install.sh 安装后）
votx              # Web UI → http://localhost:1478
votx web          # 同上
votx cli          # 终端对话模式
votx help         # 查看帮助
votx web --port=8080  # 自定义端口

# 手动 / Windows
python start_web.py              # Web UI → http://localhost:1478
python start_web.py --port=8080  # 自定义端口（冲突自动轮询）
python start.py                  # CLI 模式
```

Web UI 打开浏览器访问 `http://localhost:1478`，左侧选择用户即可开始对话。

### 斜杠命令

| 命令 | 环境 | 说明 |
|---|---|---|
| `/clear` | CLI + Web | 清空当前对话、工具日志及已完成的任务计划 |
| `/new` `/新对话` | CLI + Web | 保存摘要后开启新对话 |
| `/history` `/stats` | CLI + Web | 查看会话统计 |
| `/archive` | CLI + Web | 手动归档当前对话（不清空） |
| `/summarize` `/summary` `/总结` | CLI + Web | 生成对话摘要并存入索引 |
| `/retry` | CLI + Web | 撤回上一轮 AI 回复，重新生成 |
| `/help` | CLI + Web | 显示帮助信息 |
| `/exit` `/quit` `/q` | 仅 CLI | 退出（自动保存历史） |

Web 端额外提供：多用户 session 隔离、对话列表、归档只读预览、从历史对话继续、对话重命名与删除、对话导出 Markdown、工具调用日志查看。

### 对话示例

```
您: 帮我查下今天的热榜，然后把标题保存到文件
  [tavily_search] → 获取热榜数据...
  [write_file] → 已写入 hotboard.txt
助手: 今日热榜已保存到 hotboard.txt，共 50 条。
[Token: 输入 2100 (缓存命中 1950) | 输出 180 | 总计 2280]
```

![Web UI 界面](votx-agent-web-UI.png)

## 外部消息路由

`message-router` 已并入 Agent 进程，随 Web 服务启动和停止，不需要 nginx/caddy，也不再启动独立网关。当前支持：

- QQ/NapCat：votx-agent 作为 WebSocket 客户端连接 NapCat 正向 WebSocket，NapCat 仍是外部容器或外部进程。
- Telegram：使用 Bot API `getUpdates` 长轮询，不要求公网 webhook。
- 外部命令：支持 `/cron list|add|update|delete` 和 `/plan list|view|approve|abort`。
- 主动推送：`send_qq_message`、`upload_qq_file` 通过文件队列异步投递到 OneBot 或 Telegram。

配置文件按环境区分：

| 环境 | 配置路径 |
|---|---|
| Windows / Linux 原生 | `message/config.local.json`（优先），其次 `message/config.json` |
| Docker | 宿主机 `./message-runtime/config.json`，容器内 `/app/message-runtime/config.json` |
| 临时覆盖 | 环境变量 `VOTX_MESSAGE_CONFIG=/path/to/config.json` |

首次启用时复制 `message/config.example.json`，把顶层 `enabled` 和目标平台的 `enabled` 改为 `true`，再配置 `bound_users` 把外部账号绑定到 `users/<name>/config.json` 已存在的内部用户。

## 项目结构

```text
votx-agent/
├── votx.py                     # 入口命令（votx web/cli/help）
├── start.py / start_web.py     # 启动入口（CLI / Web）
├── setup.py / set_user.py      # 安装与用户配置向导
├── install.sh                  # Ubuntu 一键安装脚本
├── install_docker.sh           # Docker 构建/启动辅助脚本
├── requirements.txt
├── Dockerfile                  # Docker 镜像
├── docker-compose.yml          # Docker Compose 配置
├── docker-entrypoint.sh        # Docker 入口（检测用户/Key，不阻断启动）
├── message/                    # 进程内消息路由（OneBot/NapCat、Telegram、推送队列）
├── message-runtime/            # Docker 外挂的消息路由配置和运行时目录（本地生成，不提交）
│
├── provider/                   # 多 LLM 后端（统一 ProviderResponse 格式）
│   ├── schema.py               # 统一数据结构 ToolCall / ProviderResponse
│   ├── base.py                 # BaseProvider 抽象接口
│   ├── factory.py              # create_provider() 工厂
│   ├── responses_api.py        # OpenAI Responses API + Chat Completions 回退
│   ├── openai_api.py           # OpenAI Chat Completions API
│   └── anthropic_adapter.py    # Anthropic Messages API 适配
│
├── run/                        # 对话引擎（CLI & Web 共用）
│   ├── engine.py               # system prompt 构建 + tool_calls 循环
│   ├── chat.py                 # 对话历史、归档管理
│   ├── tool.py                 # 工具注册与执行
│   ├── summarize.py            # 摘要生成与归档索引
│   ├── io_utils.py             # 原子写、JSONL、安全读写工具
│   └── prompt_cache.py         # system prompt 缓存与失效
│
├── web/                        # Web UI
│   ├── server.py               # Flask + SSE 事件流
│   ├── session.py              # 多用户 session 隔离（按 user_name 分桶）
│   ├── routes/                 # API 路由（chat / config / conversations / files / system / task_plan）
│   ├── index.html              # Vite 入口
│   ├── vite.config.ts          # Vite 构建配置
│   ├── package.json            # npm 依赖
│   └── src/                    # React 前端源码（TypeScript + Zustand）
│       ├── App.tsx             # 主应用（薄壳，组合布局）
│       ├── main.tsx            # React 入口
│       ├── api/client.ts       # HTTP 封装
│       ├── types/index.ts      # TypeScript 类型定义
│       ├── utils/format.ts     # Markdown / KaTeX 格式化
│       ├── store/useAppStore.ts# Zustand 全局状态
│       ├── hooks/useAppActions.ts # 业务逻辑 hook
│       ├── styles/global.css   # 全局样式（15 种主题）
│       └── components/         # 组件（Sidebar / Chat / RightPanel / Shared）
│
├── skills/                     # 28 个 Skill（13 工具型 + 15 指令型）
├── agents/                     # 子代理（task_plan 任务规划 / auto_improve 记忆审阅）
├── cron/                       # 定时任务调度（cron 表达式 + 遗忘曲线）
├── config/                     # 全局配置与 AI 执行规则
├── tmp/                        # 智能体临时文件（脚本、运行时产物，可推送）
├── users/                      # 用户数据（人设、历史、记忆、文件）
└── 开发文档/                    # 维护者文档（本地 gitignored）
```

## Skill 与工具

| 类别 | 数量 | 说明 |
|---|---|---|
| 工具型 Skill | 13 个 | 注册 function calling：文件读写、HTTP 请求、Shell 执行、时间、Word 文档、视频下载、联网搜索、热榜查询、长期记忆、知识图谱、通用识图、Markdown 转换、任务计划 |
| 指令型 Skill | 15 个 | 注入 system prompt 行为指南：视觉识别、文件搜索、PDF 处理、网页抓取、自改进记忆、知识库检索、OpenCLI 适配器编写与自动修复、浏览器自动化、智能搜索路由等 |

所有 Skill 位于 `skills/` 目录，可自行扩展。

## 核心设计

**对话流程**

```
用户输入 → build_system_prompt() → create_provider(config)
  → respond_stream(messages, tools) → ProviderResponse
  → 解析 tool_calls → 执行工具 → 结果回传 → 继续推理
  → 无 tool_calls 或达到配置上限（默认 80 轮）→ 保存历史
```

- system prompt 由用户人设、Skill 目录、自改进记忆、长期记忆、知识库路径、活跃任务计划等组件动态拼接
- Web UI 通过 SSE 事件流实时推送思考过程、回复内容和任务计划进度
- 工具调用链路自动修复断链，支持多轮连续 reasoning
- 任务计划：子代理分析对话 → 生成分步计划 → Web 端进度气泡实时追踪 → 自动/手动推进

**自学习**

工具执行成功/失败均生成学习记录，下次对话自动注入相关教训，形成正向迭代。

**上下文管理**

自动 token 估算（CJK 感知），超限前触发压缩：system prompt 截断 + 旧消息摘要替换，确保不超过模型上下文窗口。

## 配置

用户创建后，在 `users/<name>/` 下拥有独立的人设、配置和数据目录。

### Provider 配置（`users/<name>/config.json`）

```json
{
  "provider": {
    "type": "openai",
    "api_style": "chat",
    "model": "deepseek-v4-pro",
    "api_key": "sk-xxx",
    "base_url": "https://api.deepseek.com",
    "think": true,
    "stream": true
  }
}
```

- `type`: `"openai"`（OpenAI 协议）或 `"anthropic"`（Anthropic 协议）
- `api_style`: `"responses"`（Responses API）或 `"chat"`（Chat Completions），仅 OpenAI 协议有效
- 修改后 Web 面板点"保存"即生效（即时重建 Provider）
- `POST /api/reload` 使 prompt 缓存失效，重新加载 system prompt、tools、ToolRunner

### 配置优先级

`config.json` > `.env` 环境变量。`.env` 仅做全局兜底。

> `.gitignore` 已排除运行时数据（`users/*/history/`、`users/*/tmp/`、`memory/`、`logs/` 等）、私密文件（`.env`、`*.key`）、构建缓存（`__pycache__/`）以及 `开发文档/`。`tmp/`（项目级）为智能体临时文件目录，可推送。详见 [`.gitignore`](./.gitignore)。

## 依赖

- Python 3.10+ · Flask ≥ 3.0 · openai ≥ 1.0 · anthropic ≥ 0.30
- Node.js ≥ 18（前端开发/构建）
- requests · yt-dlp · python-docx · pyyaml 等

完整清单见 [requirements.txt](./requirements.txt)。

## 开发

```bash
# 后端
python setup.py --check    # 仅检查环境
python setup.py --skip-env # 跳过 .env 配置
pytest                     # 运行测试

# 前端
cd web
npm install                # 安装依赖
npm run dev                # Vite 开发服务器（localhost:5173，代理 Flask 后端）
npm run build              # 生产构建 → dist/
npx tsc --noEmit           # TypeScript 类型检查
```

维护者文档（`开发文档/`）已 gitignored，不进入公开仓库。[`AGENTS.md`](./AGENTS.md) 是面向 AI 编码 Agent 的操作手册。

## 相关项目

- [OpenAI Responses API](https://platform.openai.com/docs/guides/responses) —— 优先协议，自动回退 Chat Completions
- [Anthropic Messages API](https://docs.anthropic.com/) —— 扩展思维原生支持
- [standard-readme](https://github.com/RichardLitt/standard-readme) —— 英文 README 标准
- [ChineseREADME](https://sunyctf.github.io/ChineseREADME/) —— 本文档参考的中文标准
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) —— 视频下载引擎

## 主要项目负责人

[@kesepain](https://github.com/kesepain-KE) —— 项目发起者与主要维护者

## 参与贡献方式

欢迎提交 [Pull Request](https://github.com/kesepain-KE/votx-agent/pulls) 或 [Issue](https://github.com/kesepain-KE/votx-agent/issues)。

贡献前请阅读 [`AGENTS.md`](./AGENTS.md)。大改动请先开 Issue 讨论，避免重复劳动。

### 贡献人员

感谢所有参与贡献的人。

## 开源协议

[MIT](./LICENSE) © kesepain
