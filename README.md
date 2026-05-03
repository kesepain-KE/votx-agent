# votx-agent

[![License](https://img.shields.io/badge/license-MIT-orange)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek-brightgreen)](https://platform.deepseek.com/)

多用户 AI Agent 框架 — 角色人设、工具调用、持久记忆、自学习闭环。同时提供 CLI 和 Web UI，共享同一对话引擎。

## 一览

```
您: 帮我查下今天的热榜，然后把标题保存到文件
  [tavily_search] → 获取热榜数据...
  [write_file] → 已写入 hotboard.txt
助手: 今日热榜已保存到 hotboard.txt，共 50 条。
[Token: 输入 2100 (缓存命中 1950) | 输出 180 | 总计 2280]
```

- **多用户**：每个用户独立人设、历史、记忆、文件空间
- **25 个工具**：文件读写、网络请求、Shell 执行、视频下载、Word 文档、热榜查询、记忆系统等
- **自学习闭环**：工具调用失败自动记录教训，下次对话前注入为规则
- **长对话管理**：自动摘要归档 + tool_calls 断链修复，上下文不膨胀
- **双模式**：CLI 轻量极速，Web UI 可视化操作，行为完全一致

## 快速开始

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
python setup.py          # 安装依赖 + 配置 .env
python set_user.py       # 创建用户
```

获取 API Key：[platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys)

### 启动

```bash
python start_web.py              # Web UI → http://localhost:1478
python start_web.py --port=8080  # 自定义端口（冲突自动轮询）
python start.py                  # CLI 模式
```

Web UI 提供完整的对话界面、文件管理、会话切换和系统配置面板。

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
│       └── index.html        # 单页前端
│
├── skills/                   # 18 个 Skill（10 工具型 + 8 指令型）
├── tools/skillhub/           # 工具注册中心
├── config/
│   ├── config_core.json      # 核心配置
│   └── soul.md               # 运行时 AI 执行规则
├── users/                    # 用户数据（人设、历史、记忆、文件）
└── 开发文档/                  # 维护者文档
```

## Skill 与工具

### 工具型 Skill（10 个 / 25 工具）

| Skill | 工具 | 说明 |
|---|---|---|
| `file` | `read_file` `write_file` `list_dir` `delete_file` | 文件系统操作 |
| `network` | `http_get` `http_post` | HTTP 请求 |
| `shell` | `run_command` | Shell 命令执行 |
| `time` | `get_time` `sleep` | 时间查询与等待 |
| `word-docx` | `create_docx` `read_docx` | Word 文档读写 |
| `video-download` | `download_video` | 视频下载（基于 yt-dlp） |
| `tavily-search` | `tavily_search` | 联网搜索 |
| `uapi-hotboard-reporter` | `query_hotboard` | 热搜榜查询 |
| `self-improving-agent` | `log_learning` `log_error` `log_feature_request` `read_learnings` | 学习闭环：记录成功/失败/需求 |
| `agent-memory` | `mem_remember` `mem_recall` `mem_learn` `mem_get_lessons` `mem_track_entity` `mem_get_entity` `mem_stats` | 持久记忆：实体追踪、教训存储 |

### 指令型 Skill（8 个）

`vision` · `download-anything` · `find-skills` · `pdf-tools` · `skill-creator` · `skill-vetter` · `web-content-fetcher` · `web-tools-guide`

指令型 Skill 注入 system prompt 作为行为指南，不注册 function calling 工具。

## 斜杠命令

| 命令 | 说明 |
|---|---|
| `/clear` | 清空当前对话及工具日志 |
| `/history` `/stats` | 查看会话统计 |
| `/archive` | 归档当前对话 |
| `/retry` | 移除上一轮 AI 回复，重新生成 |
| `/summarize` | 生成对话摘要 |
| `/exit` `/quit` `/q` | 退出（自动摘要 + 保存） |
| `/help` | 显示帮助 |

## 核心设计

### 对话引擎 (`run/engine.py`)

CLI 和 Web 共用同一引擎。每轮对话流程：

```
用户输入 → 构建 system prompt → 发送 LLM → 解析 tool_calls
  → 执行工具 → 结果注入对话 → 继续发送 LLM
  → 直到无 tool_calls 或达到上限 → 保存历史
```

system prompt 由以下组件拼接：`soul.md` + `AGENT.md` + Skill 指令 + 用户人设 + 学习记录 + 记忆快照。

### 自学习闭环

工具的每次成功执行记录为 `learning`，每次失败记录为 `error`。下一次对话构建 system prompt 时自动注入相关教训，形成"越用越聪明"的正反馈。

### 长对话管理

- 对话历史保存为结构化 JSON，tool_calls 消息的 `tool_use`/`tool_result` 配对自动修复断链
- 对话过长时自动触发摘要，摘要存入归档索引，后续对话按需检索

## 配置

首次运行 `python setup.py` 会引导创建 `.env`：

```bash
DEEPSEEK_API_KEY=sk-your-key-here      # 必填
# DEEPSEEK_BASE_URL=https://api.deepseek.com
# UAPI_API_KEY=your-uapi-key            # 热榜 Skill 需要
# TAVILY_API_KEY=your-tavily-key        # 搜索 Skill 需要
# HTTP_TIMEOUT=15
```

用户创建后，每个用户在 `users/<name>/` 下有独立的人设文件 (`soul.md`)、配置 (`config.json`) 和数据目录。

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

维护者文档见 [`开发文档/`](./开发文档/)，包含模块 API、运行流程、扩展指南和待办事项。

## 相关项目

- [DeepSeek API](https://platform.deepseek.com/) — 默认 LLM 后端
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — 视频下载引擎

## 开源协议

[MIT](./LICENSE) © kesepain
