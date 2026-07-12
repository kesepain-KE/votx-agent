# votx-agent

[![License](https://img.shields.io/badge/license-MIT-orange)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Kemo](https://img.shields.io/badge/LLM-Kemo%20LLM%20Adapter-brightgreen)](https://github.com/kesepain-KE/llm-adapter-kemo)
[![Web](https://img.shields.io/badge/web-Flask%20%2B%20React%20%2B%20TypeScript-lightgrey)](https://flask.palletsprojects.com/)

<p align="center"><img src="votx-agent.png" width="160" alt="votx-agent logo"></p>

中文 | [English](./README_EN.md)

## 简介

votx-agent 是一个本地优先、面向个人部署的多用户 AI Agent 框架。它提供 Web UI、CLI、工具调用、任务计划、定时任务、持久记忆、自我改进、QQ/Telegram 消息路由和多模态 Provider 接入。

核心链路：

```text
用户输入 → ChatManager → run_chat_turn()
  → Provider 流式响应
  → 有 tool_calls 时交给 ToolRunner
  → 工具结果回填上下文并继续循环
  → 保存最终回复与历史
```

`run/engine.py` 是 Web 与 CLI 共用的对话引擎。Web 后端使用 Flask + SSE，前端使用 React + TypeScript + Vite。

主要能力：

- 每个用户独立配置、人格、历史、文件、记忆和知识库
- Provider type 统一为 `kemo`，可连接 Kemo LLM Adapter 或 OpenAI 兼容 API
- 内置/拓展 Skill、工具权限与超时配置
- 任务计划审批、暂停、继续与中止
- cron 定时任务
- auto_improve 临时/永久记忆生命周期
- OneBot/NapCat 与 Telegram 消息和附件路由
- 视觉、语音、图像和视频多模态能力

<p align="center"><img src="votx-agent-web-UI.png" width="720" alt="votx-agent Web UI"></p>

## 安装

需要 Python 3.10+、Git；构建 Web 前端还需要 Node.js/npm。

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
python setup.py
python set_user.py add
python start_web.py
```

访问 `http://localhost:1478`。

常用启动方式：

```bash
python start_web.py
python start_web.py --host=0.0.0.0 --port=1478
python start.py
python start.py --user <用户名> --prompt "<内容>" --once
```

Windows 打包：

```cmd
build_windows.bat
```

## 配置

配置权威来源：

| 配置 | 职责 |
|---|---|
| `config/config_core.json` | 框架全局默认值、工具默认开关和超时等 |
| `users/<name>/config.json` | 用户 Provider、历史、工具权限、技能和任务计划设置；覆盖全局默认值 |
| `.env` | 少量启动级参数和兼容兜底，不作为主要业务配置 |
| `message/config.local.json` | 外部消息私有配置；不存在时回退 `message/config.json` |

Provider 示例：

```json
{
  "provider": {
    "type": "kemo",
    "model": "your-model",
    "api_key": "your-api-key",
    "base_url": "http://127.0.0.1:8741/v1",
    "stream": true,
    "timeout": 240
  }
}
```

切换 Kemo LLM Adapter 与其他 OpenAI 兼容服务时，只需调整 `base_url`、`api_key` 和模型名，`provider.type` 保持 `"kemo"`。

`.env.example` 只列出源码仍读取的可选变量，包括 Web host/port、会话密钥、Provider 兜底、Tavily、代理、版本检查和消息配置路径。模型和工具配置优先写入 JSON。

## 斜杠命令

| 命令 | 说明 |
|---|---|
| `/clear` | 清空当前对话历史及工具日志 |
| `/archive` | 归档当前对话并生成摘要 |
| `/new` | 归档后开启新对话 |
| `/summarize` | 生成当前对话摘要 |
| `/compress` | 手动压缩较早历史，保留近期对话 |
| `/retry` | 移除上一条 AI 回复并重新生成 |
| `/history`、`/stats` | 查看会话统计 |
| `/help` | 查看命令帮助 |
| `/exit`、`/quit`、`/q` | 退出 CLI |

## 多模态能力

Provider 能力名：

```text
vision
 audio_transcription
 image_generation
 image_edit
 speech_generation
 speech_to_speech
 video_generation
```

常用工具：`vision_analyze`、`audio_transcribe`、`image_generate`、`image_edit`、`speech_generate`、`speech_to_speech`、`video_generate`、`video_status`、`video_download`。

专用模型配置优先于默认聊天模型。目标 Provider 不支持某个端点时，对应能力不可用。

## 当前内置 Skills

源码当前包含 20 个插件目录：18 个工具型 Skill 和 2 个指令型 Skill。

| Skill | 主要能力 |
|---|---|
| `file` | 文件读写、编辑、搜索、复制、移动、目录操作和文件删除 |
| `shell` | 跨平台命令执行、cwd/env、stdin 和会话状态 |
| `network` | HTTP GET/POST 与网页正文读取 |
| `download_anything` | 直链检查/下载、视频或音频下载、下载记录 |
| `tavily_search` | 搜索、提取、爬取、站点地图和深度研究 |
| `time` | 当前时间和可控等待 |
| `audio_universal` | 语音转文字 |
| `vision_universal` | 本地或远程图片识别 |
| `image_generation` / `image_edit` | 图像生成与编辑 |
| `speech_generation` / `speech_to_speech` | 语音生成与转换 |
| `video_generation` | 视频生成任务、状态和下载 |
| `auto_improve` | 记忆保存、审阅、搜索和清理 |
| `task_plan` | 复杂任务计划与进度管理 |
| `task_time` | 定时任务管理 |
| `qq_send` / `qq_file` | QQ/Telegram 主动消息和文件推送 |
| `kb_retriever` | 双层知识库检索流程（指令型） |
| `skill_creator` | Skill 创建规范（指令型） |

当前源码不包含 旧版内置文档转换、PDF 与 DOCX 插件。二进制文档需由已安装的用户 Skill、外部工具或其他服务处理，不能按旧 README 调用已删除工具。

工具是否可用、执行超时和技能禁用由 `config/config_core.json` 与 `users/<name>/config.json` 决定。文件、shell 和网络插件不再通过旧文件与网络范围环境变量实现额外沙箱开关。

## 外部消息

支持 OneBot/NapCat 正向 WebSocket 与 Telegram Bot API 长轮询。外部账号通过 `bound_users` 映射到内部用户。

- 外部附件：`users/<name>/history/file/`
- 附件日志：`users/<name>/history/log/external_attachments.jsonl`
- 推送队列：`message/push_queue/`
- 示例配置：`message/config.example.json`

详见 [knowledge/message-config.md](./knowledge/message-config.md)。

## 用户数据与知识库

| 路径 | 用途 |
|---|---|
| `users/<name>/history/file/` | 用户上传和外部附件 |
| `users/<name>/download/` | 智能体生成、导出和下载的产物 |
| `users/<name>/knowledge/` | 用户私有知识库 |
| `knowledge/` | 全局共享知识库和框架说明 |
| `users/<name>/task-plan/` | 任务计划 |
| `users/<name>/tasks/` | 定时任务 |
| `users/<name>/improve/` | memory/self-improving/ontology |
| `tmp/` | 临时中间产物 |

知识库文件变更后应同步对应的 `data_structure.md` 索引。用户级资料默认写入用户知识库，全局知识库只存共享说明。

## 项目结构

```text
agents/       子智能体
config/       全局配置与基座人格
cron/         定时任务调度
knowledge/    全局知识库与维护文档
message/      QQ/Telegram 消息路由
plugins/      内置 Skills
provider/     Kemo Provider 适配层
run/          对话引擎、历史和 ToolRunner
skills/       用户拓展 Skills
users/        用户数据
web/          Flask + React/TypeScript/Vite
tmp/          临时文件
```

## 更新与开发

```bash
python update.py --check
python update.py --dry-run
python update.py --yes
```

更新前仍建议备份 `users/`、`skills/`、`.env`、消息私有配置和未发送队列。

最小检查：

```bash
python -m py_compile <changed.py>
cd web
npm run build
```

维护者入口：

- [AGENTS.md](./AGENTS.md)
- [knowledge/data_structure.md](./knowledge/data_structure.md)
- `使用手册-AI/README.md`

## 相关项目

- [Kemo LLM Adapter](https://github.com/kesepain-KE/llm-adapter-kemo)
- [NapCat](https://github.com/NapNeko/NapCatQQ)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

## 维护者与协议

维护者：[@kesepain](https://github.com/kesepain-KE)

欢迎提交 [Pull Request](https://github.com/kesepain-KE/votx-agent/pulls) 或 [Issue](https://github.com/kesepain-KE/votx-agent/issues)。项目采用 [MIT License](./LICENSE)。
