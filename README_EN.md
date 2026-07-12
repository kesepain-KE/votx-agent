# votx-agent

[![License](https://img.shields.io/badge/license-MIT-orange)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Kemo](https://img.shields.io/badge/LLM-Kemo%20LLM%20Adapter-brightgreen)](https://github.com/kesepain-KE/llm-adapter-kemo)
[![Web](https://img.shields.io/badge/web-Flask%20%2B%20React%20%2B%20TypeScript-lightgrey)](https://flask.palletsprojects.com/)

<p align="center"><img src="votx-agent.png" width="160" alt="votx-agent logo"></p>

[中文](./README.md) | English

## Overview

votx-agent is a local-first, multi-user AI Agent framework for personal deployments. It provides a Web UI, CLI, tool calling, task plans, scheduled tasks, persistent memory, self-improvement, QQ/Telegram routing, and multimodal Provider integration.

Core flow:

```text
User input → ChatManager → run_chat_turn()
  → streamed Provider response
  → ToolRunner executes tool_calls
  → tool results return to the context
  → final response and history are persisted
```

`run/engine.py` is shared by Web and CLI. The Web backend uses Flask + SSE; the frontend uses React, TypeScript, and Vite.

Main capabilities:

- Per-user configuration, persona, history, files, memory, and knowledge
- A unified `kemo` Provider type for Kemo LLM Adapter or OpenAI-compatible APIs
- Built-in and extension Skills with configurable tool permissions and timeouts
- Task-plan approval, pause, resume, and abort
- Cron-based scheduled tasks
- Temporary/permanent auto_improve memory lifecycle
- OneBot/NapCat and Telegram routing
- Vision, audio, image, and video capabilities

<p align="center"><img src="votx-agent-web-UI.png" width="720" alt="votx-agent Web UI"></p>

## Installation

Requires Python 3.10+ and Git. Building the frontend also requires Node.js/npm.

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
python setup.py
python set_user.py add
python start_web.py
```

Open `http://localhost:1478`.

Common launch commands:

```bash
python start_web.py
python start_web.py --host=0.0.0.0 --port=1478
python start.py
python start.py --user <username> --prompt "<message>" --once
```

Windows package build:

```cmd
build_windows.bat
```

## Configuration

Authoritative configuration sources:

| File | Responsibility |
|---|---|
| `config/config_core.json` | Framework defaults, including default tool switches and timeout |
| `users/<name>/config.json` | User Provider, history, tool permissions, Skills, and task-plan settings; overrides global defaults |
| `.env` | A small set of startup options and compatibility fallbacks, not the main application configuration |
| `message/config.local.json` | Private external-message configuration; falls back to `message/config.json` |

Provider example:

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

To switch between Kemo LLM Adapter and another OpenAI-compatible endpoint, change `base_url`, `api_key`, and the model name. Keep `provider.type` as `"kemo"`.

`.env.example` only lists environment variables still read by the source: Web host/port, session credentials, Provider fallback, Tavily, proxies, version checks, and message-config path. Model and tool behavior belong in JSON configuration.

## Slash Commands

| Command | Description |
|---|---|
| `/clear` | Clear current history and tool logs |
| `/archive` | Archive the current conversation with a summary |
| `/new` | Archive and start a new conversation |
| `/summarize` | Summarize the current conversation |
| `/compress` | Manually compress older history while keeping recent messages |
| `/retry` | Remove the last assistant reply and regenerate |
| `/history`, `/stats` | Show conversation statistics |
| `/help` | Show command help |
| `/exit`, `/quit`, `/q` | Exit the CLI |

## Multimodal Capabilities

Provider capability names:

```text
vision
 audio_transcription
 image_generation
 image_edit
 speech_generation
 speech_to_speech
 video_generation
```

Common tools: `vision_analyze`, `audio_transcribe`, `image_generate`, `image_edit`, `speech_generate`, `speech_to_speech`, `video_generate`, `video_status`, and `video_download`.

A dedicated capability model takes precedence over the default chat model. A capability is unavailable if the target Provider does not implement its endpoint.

## Current Built-in Skills

The current source tree contains 20 plugin directories: 18 tool Skills and 2 instruction-only Skills.

| Skill | Main capability |
|---|---|
| `file` | Read, write, edit, search, copy, move, directory operations, file deletion |
| `shell` | Cross-platform commands, cwd/env, stdin, and session state |
| `network` | HTTP GET/POST and readable Web-page extraction |
| `download_anything` | URL inspection, direct downloads, video/audio downloads, download history |
| `tavily_search` | Search, extraction, crawling, site maps, and deep research |
| `time` | Current time and controlled sleep |
| `audio_universal` | Audio transcription |
| `vision_universal` | Local or remote image understanding |
| `image_generation` / `image_edit` | Image generation and editing |
| `speech_generation` / `speech_to_speech` | Speech generation and conversion |
| `video_generation` | Video jobs, status, and download |
| `auto_improve` | Memory save, review, search, and cleanup |
| `task_plan` | Complex task planning and progress tracking |
| `task_time` | Scheduled-task management |
| `qq_send` / `qq_file` | QQ/Telegram text and file push |
| `kb_retriever` | Two-layer knowledge retrieval workflow (instruction-only) |
| `skill_creator` | Skill authoring guidance (instruction-only) |

The current source does not contain the removed built-in document conversion, PDF, and DOCX plugins. Binary documents require a user-installed Skill, external utility, or separate service; do not call the removed tools described by older documentation.

Tool availability, execution timeout, and disabled Skills are controlled by `config/config_core.json` and `users/<name>/config.json`. File, shell, and network plugins no longer use the legacy file and network-scope environment variables as extra sandbox switches.

## External Messaging

OneBot/NapCat uses a forward WebSocket connection. Telegram uses Bot API long polling. External accounts map to internal users through `bound_users`.

- Attachments: `users/<name>/history/file/`
- Attachment log: `users/<name>/history/log/external_attachments.jsonl`
- Push queue: `message/push_queue/`
- Example configuration: `message/config.example.json`

See [knowledge/message-config.md](./knowledge/message-config.md).

## User Data and Knowledge

| Path | Purpose |
|---|---|
| `users/<name>/history/file/` | User uploads and external attachments |
| `users/<name>/download/` | Generated, exported, and downloaded artifacts |
| `users/<name>/knowledge/` | Private user knowledge |
| `knowledge/` | Shared knowledge and framework documentation |
| `users/<name>/task-plan/` | Task plans |
| `users/<name>/tasks/` | Scheduled tasks |
| `users/<name>/improve/` | memory/self-improving/ontology |
| `tmp/` | Temporary working files |

After changing a knowledge directory, update its `data_structure.md` index. User-specific information belongs in the user knowledge base; the global directory is for shared material.

## Project Structure

```text
agents/       sub-agents
config/       global configuration and base persona
cron/         scheduled-task runtime
knowledge/    global knowledge and maintainer documentation
message/      QQ/Telegram routing
plugins/      built-in Skills
provider/     Kemo Provider adapter
run/          conversation engine, history, and ToolRunner
skills/       user extension Skills
users/        user data
web/          Flask + React/TypeScript/Vite
tmp/          temporary files
```

## Updates and Development

```bash
python update.py --check
python update.py --dry-run
python update.py --yes
```

Before updating, back up `users/`, `skills/`, `.env`, private message configuration, and unsent queue entries.

Minimal checks:

```bash
python -m py_compile <changed.py>
cd web
npm run build
```

Maintainer entry points:

- [AGENTS.md](./AGENTS.md)
- [knowledge/data_structure.md](./knowledge/data_structure.md)
- `使用手册-AI/README.md`

## Related Projects

- [Kemo LLM Adapter](https://github.com/kesepain-KE/llm-adapter-kemo)
- [NapCat](https://github.com/NapNeko/NapCatQQ)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

## Maintainer and License

Maintainer: [@kesepain](https://github.com/kesepain-KE)

Pull requests and [issues](https://github.com/kesepain-KE/votx-agent/issues) are welcome. Licensed under the [MIT License](./LICENSE).
