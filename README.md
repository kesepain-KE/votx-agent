# votx-agent

[![License](https://img.shields.io/badge/license-MIT-orange)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)

多用户 AI Agent 框架，支持 CLI 与 Web UI。核心能力：角色人设、工具调用、对话历史、Skill 扩展、持久记忆。

## 目录

- [背景](#背景)
- [安装](#安装)
- [用法](#用法)
- [Skill 与工具](#skill-与工具)
- [项目结构](#项目结构)
- [斜杠命令](#斜杠命令)
- [相关项目](#相关项目)
- [主要项目负责人](#主要项目负责人)
- [开源协议](#开源协议)

## 背景

日常需要 AI 辅助编码、文件管理、网络请求等任务，但市面上的 AI 工具缺乏统一的人设系统和持久记忆。本项目提供一个本地运行的、以用户为中心的 Agent 环境——你可以自定义角色人设，Agent 会记住你的偏好和过往教训，在 CLI 或 Web UI 中一致地工作。

## 安装

```bash
git clone <repo-url>
cd votx-agent
python setup.py          # 安装依赖 + 配置 .env
python set_user.py       # 创建用户
```

依赖：Python 3.10+、Flask、openai。

## 用法

**Web UI**（推荐）：

```bash
python start_web.py              # http://localhost:1478
python start_web.py --port=8080  # 自定义端口
```

端口冲突时自动轮询下一个可用端口。

**CLI**：

```bash
python start.py
```

Web 与 CLI 共用 `run/engine.py` 对话引擎，行为和工具调用完全一致。

## Skill 与工具

**工具型 Skill**（25 个 function calling 工具）：

| Skill | 工具 |
|---|---|
| file | `read_file` `write_file` `list_dir` `delete_file` |
| network | `http_get` `http_post` |
| shell | `run_command` |
| time | `get_time` `sleep` |
| word-docx | `create_docx` `read_docx` |
| video-download | `download_video` |
| tavily-search | `tavily_search` |
| uapi-hotboard-reporter | `query_hotboard` |
| self-improving-agent | `log_learning` `log_error` `log_feature_request` `read_learnings` |
| agent-memory | `mem_remember` `mem_recall` `mem_learn` `mem_get_lessons` `mem_track_entity` `mem_get_entity` `mem_stats` |

**纯指令型 Skill**（8 个）：vision、download-anything、find-skills、pdf-tools、skill-creator、skill-vetter、web-content-fetcher、web-tools-guide。

## 项目结构

```text
start.py / start_web.py    入口
main.py                     CLI 主循环
provider/openai_api.py      LLM Provider（OpenAI 兼容）
run/engine.py              共用对话引擎
run/chat.py                对话历史、归档、tool_calls 断链修复
run/tool.py                工具注册与执行
run/summarize.py           摘要与归档索引
web/server.py              Flask app 入口
web/routes/                路由模块（chat/files/conversations/system/config）
web/session.py             会话管理
web/commands.py            斜杠命令分发
web/templates/index.html   单页 Web 前端
skills/                    18 个 Skill
users/                     用户配置、人设、历史、文件、记忆
config/soul.md             运行规则
AGENT.md                   编码 Agent 手册
```

## 斜杠命令

| 命令 | 说明 |
|---|---|
| `/clear` | 清空当前对话及工具日志 |
| `/history` | 查看会话统计 |
| `/archive` | 归档当前对话 |
| `/retry` | 移除上一轮 AI 回复，重新生成 |
| `/help` | 显示帮助 |

## 相关项目

- [votx-agent](https://github.com/kesepain/votx-agent) — 上游项目
- [DeepSeek API](https://platform.deepseek.com/) — 默认 LLM 后端

## 主要项目负责人

[@kesepain](https://github.com/kesepain)

## 开源协议

[MIT](./LICENSE) © kesepain
