<div align="center">
<br>

# 🏛️ votx-agent Classic Edition

> **This branch is the classic archived release of votx-agent v2.3.3.**
> **Critical maintenance only. No automatic update detection. Suitable for long-term stable deployment.**

[![Classic](https://img.shields.io/badge/status-classic-8B4513?style=for-the-badge)](https://github.com/kesepain-KE/votx-agent/tree/votx-agent-classic)
[![version](https://img.shields.io/badge/version-2.3.3-blue?style=for-the-badge)](./version.json)
[![License](https://img.shields.io/badge/license-MIT-orange?style=for-the-badge)](./LICENSE)

<br>
</div>

---

<br>

# Project Introduction

[![standard-readme compliant](https://img.shields.io/badge/readme%20style-standard-brightgreen.svg?style=flat-square)](https://github.com/RichardLitt/standard-readme)

<p align="center"><img src="votx-agent.png" width="160" alt="votx-agent"></p>

# votx-agent

[![License](https://img.shields.io/badge/license-MIT-orange)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![LLM](https://img.shields.io/badge/LLM-OpenAI%20compatible%20%7C%20Anthropic-brightgreen)](https://platform.openai.com/)
[![Web](https://img.shields.io/badge/web-Flask%20%2B%20React%20%2B%20TypeScript-lightgrey)](https://flask.palletsprojects.com/)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](https://www.docker.com/)

[中文](./README.md) | English

## Table of Contents

- [Background](#background)
- [Install](#install)
- [Model Configuration](#model-configuration)
- [Multimodal](#multimodal)
- [Usage](#usage)
- [External Message Router](#external-message-router)
- [Files and Knowledge](#files-and-knowledge)
- [Skills / Plugins](#skills--plugins)
- [Project Structure](#project-structure)
- [Updates](#updates)
- [Windows Package Contents](#windows-package-contents)
- [Development](#development)
- [Related Efforts](#related-efforts)
- [Maintainers](#maintainers)
- [Contributing](#contributing)
  - [Contributors](#contributors)
- [License](#license)

## Background

VOTX Agent is a local multi-user AI Agent framework with Web UI, CLI, tool calling, task plans, persistent memory, self-improvement, external message routing, and multimodal capabilities. See [version.json](./version.json) for the current version.

### Features

- **Multiple providers**: OpenAI-compatible APIs, Responses API, Chat Completions, and Anthropic Messages API.
- **Multi-user isolation**: each user has independent `config.json`, `self_soul.md`, history, files, memory, and knowledge base.
- **Shared Web/CLI engine**: `run/engine.py` handles system prompts, tool calls, and history persistence.
- **Skills/Plugins architecture**: `plugins/` for built-in skills, `skills/` for user extensions.
- **Tool-first workflow**: file, network, download, PDF, DOCX, and knowledge-base tasks should use dedicated skills/tools first; shell is a last-resort diagnostic/build tool.
- **Task plans**: complex requests can be decomposed into plans, approved from Web UI, paused, resumed, or aborted.
- **auto_improve**: temporary/permanent memory layers with active review and cleanup.
- **External message routing**: QQ/NapCat/OneBot and Telegram with image, voice, and file attachments.
- **Multimodal tools**: image understanding, audio transcription, image generation, and speech generation.
- **Global/user knowledge bases**: shared `knowledge/` plus per-user `users/<name>/knowledge/`.
- **Linux/Docker updater**: `update.py` updates framework code while preserving user data.

![VOTX Agent Web UI](votx-agent-web-UI.png)

## Install

### Docker

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
bash install_docker.sh
```

Or start manually:

```bash
docker compose up -d
```

Open:

```text
http://localhost:1478
```

Create a user:

```bash
docker exec -it votx-agent python set_user.py add
```

For Docker external message routing, use:

```text
message-runtime/config.json
```

and set:

```env
VOTX_MESSAGE_CONFIG=/app/message-runtime/config.json
```

### Native Linux

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
bash install.sh
votx
```

### Windows

Development run:

```powershell
python start_web.py
```

Windows package build:

```cmd
build_windows.bat
```

Output:

```text
dist\votx-agent-windows.zip
```

The Windows special build does not run the automatic updater. It only prints local/remote version information when starting the Web server.

### Manual Install

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
python setup.py
python set_user.py add
python start_web.py
```

## Model Configuration

Recommended location:

```text
users/<username>/config.json
```

The setup model menu:

```text
1. deepseek-v4-flash   — fast and inexpensive
2. deepseek-v4-pro     — stronger reasoning
3. Other provider      — OpenAI-compatible API
4. Other provider      — Anthropic-compatible API
```

When choosing another provider, the script asks for `base_url` and `api_key`, then tries to fetch the provider's available model list. If the provider does not return a model list, you can manually add extra model names.

OpenAI-compatible example:

```json
{
  "provider": {
    "type": "openai",
    "api_style": "chat",
    "model": "deepseek-v4-flash",
    "api_key": "<your-api-key>",
    "base_url": "https://api.deepseek.com",
    "stream": true,
    "think": false
  }
}
```

Anthropic example:

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

Environment variables are fallback only:

```env
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
TAVILY_API_KEY=tvly-xxx
```

Priority:

```text
users/<name>/config.json > environment variables > defaults
```

## Multimodal

Capability names:

```text
vision
audio_transcription
image_generation
speech_generation
```

Advanced configuration:

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

Call priority:

```text
dedicated model > default chat model
```

Common tools:

| Tool | Description |
|---|---|
| `vision_analyze` | Image understanding, supports multiple images |
| `audio_transcribe` | Audio to text |
| `image_generate` | Text to image, defaults to `users/<name>/download/` |
| `speech_generate` | Text to speech, defaults to `users/<name>/download/` |

## Usage

```bash
python start_web.py
python start_web.py --port=8080
python start_web.py --host=0.0.0.0 --port=1478
python start.py
python start.py --user <username> --prompt "<message>" --once
```

After Linux installation:

```bash
votx
votx cli
votx web --port=8080
votx web --host=0.0.0.0 --port=1478
```

LAN access:

```env
VOTX_HOST=0.0.0.0
PORT=1478
VOTX_SESSION_COOKIE_NAME=votx_agent_session
```

After startup, devices on the same LAN can open `http://<server-lan-ip>:1478`. If multiple Web projects run on the same IP with different ports, give each project a different `VOTX_SESSION_COOKIE_NAME` to avoid browser cookie-name conflicts that can kick users out of other projects.

Slash commands:

| Command | Description |
|---|---|
| `/clear` | Clear current conversation |
| `/new` | Archive current conversation and start a new one |
| `/archive` | Archive manually |
| `/summarize` | Generate a summary |
| `/retry` | Retry the previous turn |
| `/stats` | Show statistics |
| `/help` | Show help |

## External Message Router

Config priority:

```text
VOTX_MESSAGE_CONFIG
message/config.local.json
message/config.json
```

Docker recommended path:

```text
message-runtime/config.json
```

OneBot/NapCat example:

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

Telegram example:

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

External attachments are saved to:

```text
users/<username>/history/file/
```

Attachment log:

```text
users/<username>/history/log/external_attachments.jsonl
```

Supported inputs:

- OneBot/NapCat: image, record, video, file
- Telegram: photo, document, voice, audio, video
- External commands: `/cron list|add|update|delete`, `/plan list|view|approve|abort`

## Files and Knowledge

| Path | Purpose |
|---|---|
| `users/<name>/config.json` | User model, key, timeout, tool, and skill configuration |
| `users/<name>/self_soul.md` | User persona file, layered into the system prompt |
| `users/<name>/avatar/` | User avatar |
| `users/<name>/history/file/` | Web uploads, external attachments, original user-provided files |
| `users/<name>/download/` | Default output for generated, exported, and downloaded artifacts: reports, documents, tables, images, speech, videos, archives |
| `users/<name>/knowledge/` | User private knowledge base |
| `users/<name>/task-plan/` | Task-plan storage |
| `users/<name>/tasks/` | Scheduled-task storage |
| `users/<name>/improve/` | Self-improvement memory layers: memory / self-improving / ontology |
| `knowledge/` | Global shared knowledge base |
| `tmp/` | Temporary scripts, intermediate caches, and test samples; clean up after use |

Knowledge-base changes must update indexes:

- After adding, modifying, deleting, renaming, or moving user knowledge files, update `users/<name>/knowledge/data_structure.md`.
- After adding, modifying, deleting, renaming, or moving global knowledge files, update `knowledge/data_structure.md`.
- Retrieval prefers user knowledge first, then falls back to global knowledge.

## Skills / Plugins

| Directory | Description |
|---|---|
| `plugins/` | Built-in framework skills, can be overwritten by updates |
| `skills/` | User extension skills, never overwritten by updates |

Common built-in capabilities:

| Skill | Main capabilities |
|---|---|
| `file` | File reading, range reading, writing, appending, precise editing, directory trees, search, copy, move, mkdir, file deletion |
| `network` | `http_get`, `http_post`, `web_read`, with `network_scope` for public/local/private network access |
| `download_anything` | URL inspection, direct-file downloads, video downloads, download listing |
| `markdown_converter` | Convert PDF/Office/HTML and other documents to Markdown |
| `pdf_tools` | PDF info, extraction, split, merge, rotate, stamp, watermark, preview, OCR, redaction, visual diff |
| `word_docx` | DOCX creation and reading with formatting, tables, images, templates, page numbers, and TOC |
| `tavily_search` | Tavily search, extraction, crawling, site maps, and deep research |
| `time` | Current time and sleep up to 30 minutes |

Core built-ins cannot be disabled:

```text
file shell time network task_plan auto_improve skill_creator task_time kb_retriever
```

User skills can override same-name built-ins with `override: true`.

Merged legacy plugins:

| Old plugin | Current home |
|---|---|
| `file_search` | Merged into `file.search_files` |
| `video_download` | Merged into `download_anything.download_video` |
| `web_content_fetcher` | Merged into `network.web_read` |

### Tool Sandboxing and Network Scope

Common environment variables:

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

`network_scope` supports `public` / `local` / `private` / `all`. Cloud metadata addresses should always be blocked.

## Project Structure

```text
votx-agent/
├── agents/             # Sub-agents: auto_improve, task_plan
├── config/             # Global config and base persona
├── cron/               # Scheduler
├── knowledge/          # Global knowledge base
├── message/            # OneBot/NapCat, Telegram, push queue
├── message-runtime/    # Docker external message runtime config
├── plugins/            # Built-in skills
├── provider/           # OpenAI-compatible, Anthropic, multimodal capability layer
├── run/                # Conversation engine, history, tool runner
├── skills/             # User extension skills
├── users/              # User data
├── web/                # Flask + React + TypeScript + Vite
├── AGENTS.md           # Agent operation manual
├── votx.py             # Linux votx command entry
├── start.py            # CLI/Web entry
├── start_web.py        # Web-only entry
├── update.py           # Linux/Docker updater
├── version.json        # Current version
└── build_windows.bat   # Windows package script
```

## Updates

Native Linux:

```bash
python update.py --check
python update.py --native
```

Docker:

```bash
python update.py --check
python update.py --docker
```

The updater overwrites framework code and `plugins/`, while preserving `users/`, `skills/`, `.env`, `message-runtime/`, and message queues. `knowledge/` update is interactive: merge, skip, or full overwrite.

After an update, existing user directories are repaired non-destructively. Missing directories such as `avatar/`, `task-plan/`, `tasks/`, `improve/*/permanent`, and `improve/*/temporary` are created, while existing `config.json`, `self_soul.md`, and user files are left untouched.

## Windows Package Contents

Included:

```text
agents/ config/ cron/ message/ message-runtime/ plugins/ provider/ run/
skills/ web/ users/ tmp/ knowledge/
paths.py AGENTS.md set_user.py setup.py version.json .env.example
```

Excluded:

```text
update.py tests/ 使用手册-AI/ tools/ web/node_modules/
message/config.json message/config.local.json message/identity/identity_map.json
message/push_queue/ .env .session_secret *.pyc *.pyo __pycache__/
```

## Development

```bash
python -m py_compile <file.py>
python -m compileall -q .

cd web
npm install
npm run dev
npm run build
npx tsc --noEmit
```

Maintainer docs:

```text
开发文档.md
开发文档/
AGENTS.md
knowledge/
使用手册-AI/
```

## Related Efforts

- [OpenAI API](https://platform.openai.com/docs)
- [Anthropic API](https://docs.anthropic.com/)
- [NapCat](https://github.com/NapNeko/NapCatQQ)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

## Maintainers

[@kesepain](https://github.com/kesepain-KE)

## Contributing

Pull Requests and Issues are welcome:

- [Pull Requests](https://github.com/kesepain-KE/votx-agent/pulls)
- [Issues](https://github.com/kesepain-KE/votx-agent/issues)

Please read [AGENTS.md](./AGENTS.md) before contributing. For large changes, open an Issue first to discuss the plan.

### Contributors

Thanks to all the people who contribute.
[@kesepain](https://github.com/kesepain-KE)

## License

[MIT](./LICENSE) © kesepain
