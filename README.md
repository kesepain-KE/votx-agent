# votx-agent

[![License](https://img.shields.io/badge/license-MIT-orange)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek-brightgreen)](https://platform.deepseek.com/)
[![Flask](https://img.shields.io/badge/web-Flask%20%2B%20Vue%203-lightgrey)](https://flask.palletsprojects.com/)

多用户 AI Agent 框架 —— 角色人设、工具调用、持久记忆、自学习闭环。同时提供 CLI 和 Web UI，共享同一对话引擎。

## 目录

- [背景](#背景)
- [安装](#安装)
- [用法](#用法)
  - [启动](#启动)
  - [斜杠命令](#斜杠命令)
  - [对话示例](#对话示例)
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
- **Web 可视化**：Vue 3 单页应用 + Flask SSE 事件流，支持流式思考渲染、文件管理、会话切换、系统配置面板
- **CLI 极速模式**：纯文本终端交互，与 Web 端共享同一对话引擎（`run/engine.py`），行为完全一致
- **自学习闭环**：工具调用失败自动记录教训，下次对话前注入为规则，越用越聪明
- **长对话管理**：自动摘要归档 + 历史文件 JSON 结构化管理，上下文不膨胀

> 本项目是 [kesepain-KE](https://github.com/kesepain-KE) 仓库的一部分，持续迭代中。

## 安装

### 环境要求

- Python 3.10 及以上版本
- Windows / Linux / macOS（Windows 建议使用 WSL2）

### 获取 API Key

注册 [DeepSeek 开放平台](https://platform.deepseek.com/api_keys) 获取 API Key（免费额度可用）。

可选：
- [Tavily Search](https://tavily.com/) —— 联网搜索 Skill 需要
- [UAPI](https://uapi.icu/) —— 热榜查询 Skill 需要

### 安装步骤

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
python setup.py          # 安装依赖 + 引导配置 .env
python set_user.py       # 创建用户（至少一个）
```

`setup.py` 会引导你填写 API Key，写入 `.env` 文件：

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
python start_web.py              # Web UI → http://localhost:1478
python start_web.py --port=8080  # 自定义端口（冲突自动轮询）
python start.py                  # CLI 模式
```

Web UI 打开浏览器访问 `http://localhost:1478`，左侧选择用户即可开始对话。CLI 模式下：

```
>> 你好，帮我查今天的知乎热榜
[Agent 流式回复...]
```

### 斜杠命令

| 命令 | 环境 | 说明 |
|---|---|---|
| `/clear` | CLI + Web | 清空当前对话及工具日志 |
| `/history` | CLI + Web | 查看会话统计（消息数、工具调用数） |
| `/retry` | CLI + Web | 移除上一轮 AI 回复，重新生成 |
| `/help` | CLI + Web | 显示帮助信息 |
| `/exit` `/quit` `/q` | 仅 CLI | 退出（自动保存历史） |

Web 端额外功能：会话归档（顶部按钮）、对话导出 Markdown、工具调用日志查看。

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
├── start.py / start_web.py   # 启动入口（CLI / Web）
├── main.py                   # CLI 主循环
├── setup.py                  # 环境安装向导
├── set_user.py               # 用户创建向导
├── requirements.txt
│
├── provider/                 # LLM 后端
│   └── openai_api.py         # DeepSeek / OpenAI 兼容 Provider
│
├── run/                      # 核心引擎（CLI & Web 共用）
│   ├── engine.py             # 对话引擎：system prompt 构建 + tool_calls 循环
│   ├── chat.py               # 对话历史、归档、tool_calls 断链修复
│   ├── tool.py               # 工具注册与执行
│   └── summarize.py          # 摘要生成与归档索引
│
├── web/                      # Web UI 后端
│   ├── server.py             # Flask 应用入口 + SSE 事件流
│   ├── session.py            # 会话管理
│   ├── commands.py           # 斜杠命令分发
│   ├── routes/               # 路由模块
│   │   ├── chat.py           # 对话 SSE 流
│   │   ├── conversations.py  # 会话管理
│   │   ├── files.py          # 文件浏览
│   │   ├── system.py         # 系统状态
│   │   └── config.py         # 配置管理
│   └── templates/
│       └── index.html        # 单页前端（Vue 3）
│
├── skills/                   # 20 个 Skill（9 工具型 + 11 指令型）
├── config/
│   ├── config_core.json      # 核心配置
│   └── soul.md               # 运行时 AI 执行规则
├── users/                    # 用户数据（人设、历史、记忆、文件）
└── 开发文档/                  # 维护者文档
```

## Skill 与工具

### 工具型 Skill（9 个，可 function call）

| Skill | 工具 | 说明 |
|---|---|---|
| `file` | `read_file` `write_file` `list_dir` `delete_file` | 文件系统操作 |
| `network` | `http_get` `http_post` | HTTP 请求 |
| `shell` | `run_command` | Shell 命令执行 |
| `time` | `get_time` `sleep` | 时间查询与延时 |
| `word-docx` | `create_docx` `read_docx` | Word 文档读写 |
| `video-download` | `download_video` | 视频下载（基于 yt-dlp） |
| `tavily-search` | `tavily_search` | 联网搜索 |
| `uapi-hotboard-reporter` | `query_hotboard` | 热搜榜查询 |

### 指令型 Skill（11 个，注入行为指南）

`vision` · `download-anything` · `file-search` · `find-skills` · `pdf-tools` · `skill-creator` · `skill-vetter` · `web-content-fetcher` · `web-tools-guide` · `multi-user-long-term-memory` · `self-improving`

指令型 Skill 注入 system prompt 作为行为指南，不注册 function calling 工具。

## 核心设计

### 对话引擎 (`run/engine.py`)

CLI 和 Web 共用同一引擎。每轮对话流程：

```
用户输入 → 构建 system prompt → 发送 LLM → 解析 tool_calls
  → 执行工具 → 结果注入对话 → 继续发送 LLM
  → 直到无 tool_calls 或达到上限（20 轮）→ 保存历史
```

system prompt 由以下组件拼接：soul（用户人设 + 全局规则）+ AGENTS.md 操作手册 + Skill 目录 + 自改进记忆 + 纠正记录 + 长期记忆 + 知识图谱摘要 + 会话状态。

DeepSeek thinking 模式下，`reasoning_content` 在 tool_calls 链路中自动回传，确保多轮工具调用不报错。

### SSE 事件类型

Web UI 通过 SSE 接收事件：`thinking_chunk` / `thinking_done` / `thinking` / `text_chunk` / `text_done` / `text` / `tool_call` / `usage` / `error` / `done`，前端 Vue 3 实时响应渲染。

### 自学习闭环

工具的每次成功执行记录为 `learning`，每次失败记录为 `error`。下一次对话构建 system prompt 时自动注入相关教训，形成"越用越聪明"的正反馈。

### 长对话管理

- 对话历史保存为结构化 JSON，tool_calls 消息的 `tool_use`/`tool_result` 配对自动修复断链
- 对话过长时自动触发摘要，摘要存入归档索引，后续对话按需检索

## 配置

用户创建后，每个用户在 `users/<name>/` 下有独立的人设文件（`self_soul.md`）、配置（`config.json`）和数据目录。对话历史保存在 `users/<name>/history/`，工具日志保存在 `users/<name>/history/log/`，自改进记忆和纠正记录在 `users/<name>/self-improving/`。

## 依赖

- Python 3.10+
- Flask ≥ 3.0（Web UI）
- openai ≥ 1.0（LLM 调用）
- requests、yt-dlp、python-docx、pyyaml 等

完整清单见 [requirements.txt](./requirements.txt)。

## 开发

```bash
python setup.py --check    # 仅检查环境，不修改文件
python setup.py --skip-env # 跳过 .env 配置
pytest                     # 运行测试
```

维护者文档见 [`开发文档/`](./开发文档/)，包含模块 API、运行流程、扩展指南和待办事项。AGENTS.md 是 AI Agent 的操作手册，面向编码 Agent 而非人类用户。

## 相关项目

- [DeepSeek API](https://platform.deepseek.com/) —— 默认 LLM 后端
- [standard-readme](https://github.com/RichardLitt/standard-readme) —— 英文 README 标准
- [ChineseREADME](https://sunyctf.github.io/ChineseREADME/) —— 本文档参考的中文标准
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) —— 视频下载引擎

## 主要项目负责人

[@kesepain](https://github.com/kesepain-KE) —— 项目发起者与主要维护者

## 参与贡献方式

欢迎提交 [Pull Request](https://github.com/kesepain-KE/votx-agent/pulls) 或 [Issue](https://github.com/kesepain-KE/votx-agent/issues)。

贡献前请阅读：
- [`开发文档/`](./开发文档/) —— 模块 API 和架构说明
- [`AGENTS.md`](./AGENTS.md) —— AI Agent 操作手册（编码规范、安全边界等）

大改动请先开 Issue 讨论，避免重复劳动。

### 贡献人员

感谢所有参与贡献的人。

## 开源协议

[MIT](./LICENSE) © kesepain
