<p align="center"><img src="votx-agent.png" width="160" alt="votx-agent"></p>

# votx-agent

[![License](https://img.shields.io/badge/license-MIT-orange)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![VOTX](https://img.shields.io/badge/LLM-VOTX%20LLM%20Adapter-brightgreen)](https://github.com/kesepain-KE/llm-adapter-votx)
[![Web](https://img.shields.io/badge/web-Flask%20%2B%20React%20%2B%20TypeScript-lightgrey)](https://flask.palletsprojects.com/)

[中文](./README.md) | English

## Table of Contents

- [Overview](#overview)
- [Install](#install)
- [Provider Configuration](#provider-configuration)
- [Multimodal Capabilities](#multimodal-capabilities)
- [Usage](#usage)
- [External Message Router](#external-message-router)
- [Files and Knowledge](#files-and-knowledge)
- [Skills / Plugins](#skills--plugins)
- [Project Structure](#project-structure)
- [Updates](#updates)
- [Windows Package](#windows-package)
- [Development](#development)
- [Related Efforts](#related-efforts)
- [Maintainers](#maintainers)
- [Contributing](#contributing)
  - [Contributors](#contributors)
- [License](#license)

## Overview

votx-agent is a local-first, multi-user AI Agent framework for personal deployments. It provides a Web UI, CLI, tool calling, task plans, scheduled tasks, persistent memory, self-improvement, QQ/Telegram routing, and full-stack multimodal Provider integration.

### Architecture Overview

```text
User Input → ChatManager.add_user_message()
  → engine.run_chat_turn()
    → Loop:
      1. chat.build_messages() → system prompt + history
      2. provider.respond_stream() → yields SSE events
      3. If tool_calls → tool_runner.execute()
      4. chat.add_tool_call_message() + add_tool_results()
      5. Back to step 1 (max MAX_TOOL_ROUNDS)
    → Final text → chat.add_assistant_message()
```

`run/engine.py` is the single conversation engine that both CLI (`main.py`) and Web (`web/routes/`) consume, only differing in how they render the event stream. Both CLI (`main.py`) and Web (`web/routes/`) consume it, only differing in how they render the event stream. Web backend is Flask + SSE; frontend is React + TypeScript + Vite.

### Features

- **Single Provider (VOTX LLM Adapter)**: Pure HTTP local multimodal gateway, no OpenAI SDK dependency — all models and capabilities are routed through VOTX.
- **Multi-user data isolation**: Each user has independent `config.json`, `self_soul.md`, history, files, memory, and knowledge base.
- **Shared Web/CLI engine**: `run/engine.py` handles system prompts, tool calls, and history persistence.
- **Skills/Plugins architecture**: `plugins/` for built-in skills, `skills/` for user extensions.
- **Tool-first workflow**: File, network, download, and knowledge-base tasks use dedicated skills/tools first; shell is a last-resort diagnostic and build tool.
- **Task plans**: Complex requests can be decomposed into plans, approved from Web UI, paused, resumed, or aborted.
- **auto_improve**: Temporary/permanent memory layers with active review and cleanup.
- **External message routing**: QQ/NapCat/OneBot and Telegram with image, voice, file attachments, and push queue.
- **Full-stack multimodal**: Image understanding, audio transcription, image generation, image editing, speech generation, speech-to-speech, and video generation.
- **Global/user knowledge bases**: Shared `knowledge/` plus per-user `users/<name>/knowledge/`.

<p align="center"><img src="votx-agent-web-UI.png" width="720" alt="votx-agent Web UI"></p>

## Install

Requires Python 3.10+ and Git. Building the frontend also requires Node.js 18+/npm.

### Plain Python

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
python setup.py
python set_user.py add
python start_web.py
```

Open:

```
http://localhost:1478
```

### Windows Package

Download `votx-agent-windows.zip`, extract, and double-click `votx-agent-web.exe` to launch the Web UI or `votx-agent-cli.exe` for CLI mode. No Python installation required.

Build from source:

```cmd
build_windows.bat
```

Output: `dist\votx-agent-windows.zip` containing two EXEs sharing a single runtime.

## Provider Configuration

votx-agent offers two Provider modes:

- **Recommended mode** → pair with the VOTX LLM Adapter gateway for full multimodal support.
- **Compatible mode** → point `base_url` at any OpenAI-compatible API (`base_url` determines the target); some endpoints (such as image generation, video, or parts of ASR routing) may be unavailable.

Switch modes by changing only `base_url` and `api_key`; keep `provider.type` set to `"votx"`.

### Direct OpenAI-Compatible API

Change `base_url` to the third-party endpoint and fill `api_key` with that platform's key. Keep `provider.type` as `"votx"`.

### Configuration Priority

```text
users/<name>/config.json > environment variables > program defaults
```

Environment variables are fallback only (see `.env.example` for full details):

```env
VOTX_API_KEY=your-api-key
VOTX_BASE_URL=http://127.0.0.1:8741/v1
TAVILY_API_KEY=tvly-xxx
```

### Configuration Files

| File | Responsibility |
|---|---|
| `config/config_core.json` | Framework defaults (history, tool timeout, output, improvement, task plans, context window) |
| `users/<name>/config.json` | User Provider, history, tool permissions, Skills, and task-plan settings; overrides global defaults |
| `.env` | A small set of startup options and compatibility fallbacks, not the main application configuration |
| `message/config.local.json` | Private external-message configuration; falls back to `message/config.json` |

### Provider Architecture

```text
provider/
├── base.py          # BaseProvider abstract interface (respond / respond_stream + all multimodal capability stubs)
├── schema.py        # ToolCall + ProviderResponse unified data structures
├── factory.py       # create_provider() → only supports type: "votx"
└── votx_adapter.py  # VOTX LLM Adapter Provider — pure urllib HTTP, no OpenAI SDK dependency
```

VotxProvider communicates with the configured `base_url` via pure `urllib` HTTP. `type` stays `votx`, while `base_url` can target either the VOTX LLM Adapter gateway (recommended mode) or any OpenAI-compatible API (compatible mode); image generation, video, and some ASR routes may only be available on the VOTX gateway.

## Multimodal Capabilities

Capability names:

```text
vision
audio_transcription
image_generation
image_edit
speech_generation
speech_to_speech
video_generation
```

Advanced configuration (in `users/<name>/config.json` under `provider`):

```json
{
  "provider": {
    "capabilities_override": [
      "vision",
      "audio_transcription",
      "image_generation",
      "image_edit",
      "speech_generation",
      "speech_to_speech",
      "video_generation"
    ],
    "audio_transcription_model": "stepfun-stepaudio-2.5-asr",
    "image_generation_model": "",
    "image_edit_model": "stepfun-step-image-edit-2",
    "speech_generation_model": "stepfun-stepaudio-2.5-tts",
    "speech_to_speech_model": "",
    "video_generation_model": ""
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
| `audio_transcribe` | Audio to text, multilingual with timestamp support |
| `image_generate` | Text to image, defaults to `users/<name>/download/` |
| `image_edit` | Image editing (requires Provider support), defaults to `users/<name>/download/` |
| `speech_generate` | Text to speech, defaults to `users/<name>/download/` |
| `speech_to_speech` | Speech-to-speech (requires Provider support), defaults to `users/<name>/download/` |
| `video_generate` / `video_status` / `video_download` | Video generation, status, and download (requires Provider support) |

A capability is unavailable if the target Provider does not implement its endpoint.

## Usage

```bash
# Start Web UI
python start_web.py
python start_web.py --port=8080
python start_web.py --host=0.0.0.0 --port=1478

# CLI interactive mode
python start.py

# One-shot mode
python start.py --user <username> --prompt "<message>" --once
```

LAN access:

```env
VOTX_HOST=0.0.0.0
PORT=1478
VOTX_SESSION_COOKIE_NAME=votx_agent_session
```

After startup, devices on the same LAN can open `http://<server-lan-ip>:1478`. If multiple Web projects run on the same IP with different ports, give each project a different `VOTX_SESSION_COOKIE_NAME` to avoid browser cookie-name conflicts causing sessions to overwrite each other.

Slash commands (shared between Web UI and CLI):

| Command | Description |
|---|---|
| `/clear` | Clear current conversation history and tool logs |
| `/archive` | Archive current conversation with summary |
| `/new` | Archive current conversation, then start a new one |
| `/summarize` | Generate a summary of the current conversation |
| `/compress` | Manually compress older history while keeping recent messages |
| `/retry` | Remove the last AI reply and regenerate |
| `/history` or `/stats` | Show conversation statistics |
| `/help` | Show available commands |

CLI-only commands:

| Command | Description |
|---|---|
| `/exit` / `/quit` / `/q` | Exit CLI (auto-summarize + save) |

## External Message Router

Config file priority:

```text
VOTX_MESSAGE_CONFIG environment variable
message/config.local.json (if exists)
message/config.json (default)
```

Full configuration example at `message/config.example.json`.

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

See [knowledge/message-config.md](./knowledge/message-config.md).

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
| `knowledge/` | Global shared knowledge base and framework documentation |
| `tmp/` | Temporary scripts, intermediate caches; clean up after use |

Knowledge-base changes must update indexes:

- After adding, modifying, deleting, renaming, or moving user knowledge files, update `users/<name>/knowledge/data_structure.md`.
- After adding, modifying, deleting, renaming, or moving global knowledge files, update `knowledge/data_structure.md`.
- Retrieval prefers user knowledge first, then falls back to global knowledge.

## Skills / Plugins

The current source tree contains 20 plugin directories: 18 tool Skills and 2 instruction-only Skills.

| Directory | Description |
|---|---|
| `plugins/` | Built-in framework skills, can be overwritten by updates |
| `skills/` | User extension skills, never overwritten by updates |

| Skill | Main capabilities |
|---|---|
| `file` | File reading, range reading, writing, appending, precise editing, directory trees, search, copy, move, mkdir, file deletion |
| `shell` | Cross-platform commands, cwd/env, stdin, and session state |
| `network` | `http_get`, `http_post`, `web_read`, with `network_scope` for public/local/private network access |
| `download_anything` | URL inspection, direct-file downloads, video/audio downloads, download listing |
| `tavily_search` | Tavily search, extraction, crawling, site maps, and deep research |
| `time` | Current time and sleep up to 30 minutes |
| `audio_universal` | Audio transcription with multilingual and timestamp support |
| `vision_universal` | Image understanding for local files and remote URLs |
| `image_generation` | Text to image with various sizes and quality |
| `image_edit` | Image editing (requires Provider support) |
| `speech_generation` | Text to speech with multiple voice styles |
| `speech_to_speech` | Speech-to-speech (requires Provider support) |
| `video_generation` | Video generation, status, download (requires Provider support) |
| `auto_improve` | Memory save, review, search, and cleanup |
| `task_plan` | Complex task planning and progress tracking |
| `task_time` | Cron-based scheduled task management |
| `qq_send` / `qq_file` | QQ/Telegram text and file push |
| `kb_retriever` | Two-layer knowledge retrieval workflow (instruction-only) |
| `skill_creator` | Skill authoring guidance (instruction-only) |

Core built-ins cannot be disabled:

```text
file shell time network task_plan auto_improve skill_creator task_time kb_retriever
```

User skills can override same-name built-ins with `override: true`.

The current source does not contain the removed built-in document-conversion, PDF, and DOCX plugins. Binary documents require a user-installed Skill, external utility, or separate service.

Tool availability, execution timeout, and disabled Skills are controlled by `config/config_core.json` and `users/<name>/config.json`.

## Project Structure

```text
votx-agent/
├── agents/             # Sub-agents: auto_improve, task_plan
├── config/             # Global config (config_core.json) and base persona (soul.md)
├── cron/               # Scheduler
├── knowledge/          # Global knowledge base (includes architecture docs)
├── message/            # External message routing: OneBot/NapCat, Telegram, push queue, identity mapping
├── plugins/            # Built-in skills (18 tool + 2 instruction-only Skills)
├── provider/           # VOTX LLM Adapter Provider — pure HTTP local gateway adapter
├── run/                # Conversation engine, history management, tool runner, summarizer, prompt cache
├── skills/             # User extension skills
├── users/              # User data (config, history, files, knowledge, memory)
├── web/                # Flask + React + TypeScript + Vite
├── AGENTS.md           # Agent operation manual
├── main.py             # CLI entry point
├── start.py            # CLI/Web entry (user selection)
├── start_web.py        # Web-only entry point
├── windows_entry.py    # Windows dual-EXE unified entry (dispatches Web/CLI by name)
├── setup.py            # Environment setup script
├── set_user.py         # User management script
├── update.py           # Cross-platform update script
├── paths.py            # Path resolution (dev/PyInstaller compatible)
├── version.json        # Current version
├── requirements.txt    # Python dependency manifest
├── votx-agent.spec     # PyInstaller spec (dual-EXE onedir)
├── build_windows.bat   # Windows packaging script
└── LICENSE             # MIT License
```

## Updates

```bash
# Check version
python update.py --check

# Run update (backup → sync framework → handle config/knowledge → refresh deps)
python update.py --yes

# Preview what will happen
python update.py --dry-run
```

`update.py` works on all platforms (Linux / macOS / Windows with git), written in pure Python with no rsync dependency. It:

1. Compares local version against GitHub main's `version.json`
2. Shallow-clones the latest source into a temp directory
3. Backs up the current project (`users/`, `skills/`, `.env`, etc. not included in backup)
4. Syncs framework code while skipping user data and build artifacts
5. Interactively handles `config/` and `knowledge/` (overwrite / keep / merge)
6. Patches user directory skeletons
7. Refreshes dependencies (`python setup.py --skip-env`)

For manual updates, pull the new revision and back up `users/`, `skills/`, `.env`, `message/config.local.json`, and unsent push-queue entries before overwriting. `update.py` handles these exclusions automatically.

## Windows Package

### Dual-EXE Architecture

`votx-agent.spec` uses PyInstaller onedir mode to produce two EXEs sharing a single `_internal` runtime:

- **`votx-agent-web.exe`** → launches the Web UI
- **`votx-agent-cli.exe`** → launches CLI interactive mode

Entry files (`start.py`, `start_web.py`, etc.) are copied by `build_windows.bat` to the EXE's directory and located at runtime via `paths.get_project_root()`. Plugin and skill directories are placed alongside the EXEs for hot-swappable updates.

### Build Command

```cmd
build_windows.bat
```

### Package Contents

Included:

```text
votx-agent-web.exe  votx-agent-cli.exe  _internal/
agents/ config/ cron/ message/ plugins/ provider/ run/
skills/ web/ users/ tmp/ knowledge/
paths.py AGENTS.md set_user.py setup.py start.py start_web.py
main.py update.py windows_entry.py requirements.txt version.json .env.example
```

Excluded:

```text
使用手册-AI/ tools/ web/node_modules/
message/config.json message/config.local.json message/identity/identity_map.json
message/push_queue/ .env .session_secret *.pyc *.pyo __pycache__/
```

## Development

```bash
# Syntax check
python -m py_compile <file.py>
python -m compileall -q .

# Web frontend
cd web
npm install
npm run dev      # Development mode
npm run build    # Production build
npx tsc --noEmit # TypeScript check
```

Maintainer docs:

```text
AGENTS.md
knowledge/
使用手册-AI/
```

## Related Efforts

- [VOTX LLM Adapter](https://github.com/kesepain-KE/llm-adapter-votx) — Local multimodal LLM gateway, the provider backend for votx-agent
- [NapCat](https://github.com/NapNeko/NapCatQQ) — QQ bot framework
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — Video download engine

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
