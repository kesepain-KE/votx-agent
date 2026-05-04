<p align="center"><img src="votx-agent.png" width="160" alt="votx-agent"></p>

# votx-agent

[![License](https://img.shields.io/badge/license-MIT-orange)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek-brightgreen)](https://platform.deepseek.com/)
[![Flask](https://img.shields.io/badge/web-Flask%20%2B%20Vue%203-lightgrey)](https://flask.palletsprojects.com/)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](https://www.docker.com/)

多用户 AI Agent 框架 —— 角色人设、工具调用、持久记忆、自学习闭环。同时提供 CLI 和 Web UI，共享同一对话引擎。

## 目录

- [背景](#背景)
- [安装](#安装)
  - [Docker 部署](#docker-部署)
  - [Ubuntu 原生部署](#ubuntu-原生部署)
  - [手动安装](#手动安装)
- [用法](#用法)
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

- **多用户隔离**：每个用户独立人设（`self_soul.md`）、对话历史、长期记忆、工具日志和文件空间
- **双端支持**：Vue 3 Web UI + CLI 终端，共用 `run/engine.py` 对话引擎，行为完全一致
- **自学习**：工具调用失败自动记录教训，下次对话前注入为规则，越用越聪明
- **长对话友好**：自动摘要归档，上下文不膨胀

> 本项目是 [kesepain-KE](https://github.com/kesepain-KE) 仓库的一部分，持续迭代中。

## 安装

### 环境要求

- Python 3.10 及以上版本（Docker 部署无需安装）

### 获取 API Key

注册 [DeepSeek 开放平台](https://platform.deepseek.com/api_keys) 获取 API Key（免费额度可用）。

可选：
- [Tavily Search](https://tavily.com/) —— 联网搜索 Skill 需要
- [UAPI](https://uapi.icu/) —— 热榜查询 Skill 需要

### Docker 部署

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent

# 首次启动会自动创建 .env 模板并提示配置
docker compose up
# 编辑 .env 填入 DEEPSEEK_API_KEY 后重新启动
docker compose up -d
# 访问 http://localhost:1478
```

### Ubuntu 原生部署

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
bash install.sh
# 按提示编辑 .env 填入 DEEPSEEK_API_KEY
votx        # 启动 Web UI → http://localhost:1478
```

`install.sh` 会完成：虚拟环境创建 → 依赖安装 → 注册 `votx` 系统命令。

### 手动安装

如果你不想使用上述方式：

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
python setup.py          # 安装依赖 + 引导配置 .env
python set_user.py       # 创建用户（至少一个）
```

`setup.py` 会引导填写 API Key，写入 `.env` 文件：

```bash
DEEPSEEK_API_KEY=sk-your-key-here      # 必填
# DEEPSEEK_BASE_URL=https://api.deepseek.com
# UAPI_API_KEY=your-uapi-key            # 可选
# TAVILY_API_KEY=your-tavily-key        # 可选
# HTTP_TIMEOUT=15
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
| `/clear` | CLI + Web | 清空当前对话及工具日志 |
| `/history` | CLI + Web | 查看会话统计 |
| `/retry` | CLI + Web | 撤回上一轮 AI 回复，重新生成 |
| `/help` | CLI + Web | 显示帮助信息 |
| `/exit` `/quit` `/q` | 仅 CLI | 退出（自动保存历史） |

Web 端额外提供：会话归档、对话导出 Markdown、工具调用日志查看。

### 对话示例

```
您: 帮我查下今天的热榜，然后把标题保存到文件
  [tavily_search] → 获取热榜数据...
  [write_file] → 已写入 hotboard.txt
助手: 今日热榜已保存到 hotboard.txt，共 50 条。
[Token: 输入 2100 (缓存命中 1950) | 输出 180 | 总计 2280]
```

## 项目结构

```text
votx-agent/
├── votx.py                     # 入口命令（votx web/cli/help）
├── start.py / start_web.py     # 启动入口（CLI / Web）
├── setup.py / set_user.py      # 安装与用户配置向导
├── install.sh                  # Ubuntu 一键安装脚本
├── requirements.txt
├── Dockerfile                  # Docker 镜像
├── docker-compose.yml          # Docker Compose 配置
├── docker-entrypoint.sh        # Docker 入口（检测 API Key）
│
├── provider/                 # LLM 后端
│   └── openai_api.py         # DeepSeek / OpenAI 兼容 Provider
│
├── run/                      # 对话引擎（CLI & Web 共用）
│   ├── engine.py             # system prompt 构建 + tool_calls 循环
│   ├── chat.py               # 对话历史、归档管理
│   ├── tool.py               # 工具注册与执行
│   └── summarize.py          # 摘要生成与归档索引
│
├── web/                      # Web UI
│   ├── server.py             # Flask + SSE 事件流
│   ├── routes/               # API 路由
│   └── templates/index.html  # Vue 3 单页前端
│
├── skills/                   # 20 个 Skill（工具型 + 指令型）
├── config/                   # 全局配置与 AI 执行规则
├── users/                    # 用户数据（人设、历史、记忆、文件）
└── 开发文档/                  # 维护者文档（本地 gitignored）
```

## Skill 与工具

| 类别 | 数量 | 说明 |
|---|---|---|
| 工具型 Skill | 10 个 | 注册 function calling：文件读写、HTTP 请求、Shell 执行、时间、Word 文档、视频下载、联网搜索、热榜查询、长期记忆、知识图谱 |
| 指令型 Skill | 10 个 | 注入 system prompt 行为指南：视觉识别、文件搜索、PDF 处理、网页抓取、自改进记忆等 |

所有 Skill 位于 `skills/` 目录，可自行扩展。

## 核心设计

**对话流程**

```
用户输入 → 构建 system prompt → LLM 推理 → 解析 tool_calls
  → 执行工具 → 结果回传 → 继续推理
  → 无 tool_calls 或达到上限（20 轮）→ 保存历史
```

- system prompt 由用户人设、Skill 目录、自改进记忆、长期记忆等组件动态拼接
- Web UI 通过 SSE 事件流实时推送思考过程和回复内容
- 工具调用链路自动修复断链，支持多轮连续 reasoning

**自学习**

工具执行成功/失败均生成学习记录，下次对话自动注入相关教训，形成正向迭代。

**长对话管理**

历史保存为结构化 JSON，超长时自动触发摘要归档，后续按需检索。

## 配置

用户创建后，在 `users/<name>/` 下拥有独立的人设、配置和数据目录。

> `.gitignore` 已排除运行时数据（`users/*/history/`、`memory/`、`tmp/`、`logs/` 等）、私密文件（`.env`、`*.key`）、构建缓存（`__pycache__/`）以及 `开发文档/`。详见 [`.gitignore`](./.gitignore)。

## 依赖

- Python 3.10+ · Flask ≥ 3.0 · openai ≥ 1.0
- requests · yt-dlp · python-docx · pyyaml 等

完整清单见 [requirements.txt](./requirements.txt)。

## 开发

```bash
python setup.py --check    # 仅检查环境
python setup.py --skip-env # 跳过 .env 配置
pytest                     # 运行测试
```

维护者文档（`开发文档/`）已 gitignored，不进入公开仓库。[`AGENTS.md`](./AGENTS.md) 是面向 AI 编码 Agent 的操作手册。

## 相关项目

- [DeepSeek API](https://platform.deepseek.com/) —— 默认 LLM 后端
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
