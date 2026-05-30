<p align="center"><img src="votx-agent.png" width="160" alt="votx-agent"></p>

# votx-agent

[![License](https://img.shields.io/badge/license-MIT-orange)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![LLM](https://img.shields.io/badge/LLM-OpenAI%20compatible%20%7C%20Anthropic-brightgreen)](https://platform.openai.com/)
[![Web](https://img.shields.io/badge/web-Flask%20%2B%20React%20%2B%20TypeScript-lightgrey)](https://flask.palletsprojects.com/)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](https://www.docker.com/)

[中文](./README.md) | English

VOTX Agent is a local multi-user AI Agent framework with Web UI, CLI, tool calling, task plans, persistent memory, self-improvement, external message routing, and multimodal capabilities. See [version.json](./version.json) for the current version.

## Features

- **Multiple providers**: OpenAI-compatible APIs, Responses API, Chat Completions, and Anthropic Messages API.
- **Multi-user isolation**: each user has independent `config.json`, `self_soul.md`, history, files, memory, and knowledge base.
- **Shared Web/CLI engine**: `run/engine.py` handles system prompts, tool calls, and history persistence.
- **Skills/Plugins architecture**: `plugins/` for built-in skills, `skills/` for user extensions.
- **Task plans**: complex requests can be decomposed into plans, approved from Web UI, paused, resumed, or aborted.
- **auto_improve**: temporary/permanent memory layers with active review and cleanup.
- **External message routing**: QQ/NapCat/OneBot and Telegram with image, voice, and file attachments.
- **Multimodal tools**: image understanding, audio transcription, image generation, and speech generation.
- **Global/user knowledge bases**: shared `knowledge/` plus per-user `users/<name>/knowledge/`.
- **Linux/Docker updater**: `update.py` updates framework code while preserving user data.

## Quick Start

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

OpenAI-compatible example:

```json
{
  "provider": {
    "type": "openai",
    "api_style": "chat",
    "model": "deepseek-chat",
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
python start.py
python start.py --user <username> --prompt "<message>" --once
```

After Linux installation:

```bash
votx
votx cli
votx web --port=8080
```

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
        "qq:123456789": "kesepain"
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
      "bound_users": {
        "tg:987654321": "kesepain"
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
| `users/<name>/history/file/` | Web uploads, external attachments, regular user files |
| `users/<name>/download/` | Image/speech generation defaults, downloader output, legacy downloads |
| `users/<name>/knowledge/` | User private knowledge base |
| `knowledge/` | Global shared knowledge base |
| `tmp/` | Temporary files |

After writing to global `knowledge/`, update:

```text
knowledge/data_structure.md
```

## Skills / Plugins

| Directory | Description |
|---|---|
| `plugins/` | Built-in framework skills, can be overwritten by updates |
| `skills/` | User extension skills, never overwritten by updates |

Current built-ins: 23 skills, including 19 tool skills and 4 instruction skills, registering 48 tools.

Core built-ins cannot be disabled:

```text
file shell time network task_plan auto_improve skill_creator task_time kb_retriever
```

User skills can override same-name built-ins with `override: true`.

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

## Related Projects

- [OpenAI API](https://platform.openai.com/docs)
- [Anthropic API](https://docs.anthropic.com/)
- [NapCat](https://github.com/NapNeko/NapCatQQ)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

## Maintainer

[@kesepain](https://github.com/kesepain-KE)

## Contributing

Pull Requests and Issues are welcome:

- [Pull Requests](https://github.com/kesepain-KE/votx-agent/pulls)
- [Issues](https://github.com/kesepain-KE/votx-agent/issues)

Please read [AGENTS.md](./AGENTS.md) before contributing. For large changes, open an Issue first to discuss the plan.

## License

[MIT](./LICENSE) © kesepain
