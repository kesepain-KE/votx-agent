<p align="center">
  <img src="votx-agent.png" width="168" alt="votx-agent logo">
</p>

<h1 align="center">votx-agent</h1>

<p align="center">
  <strong>A local-first, multi-user Agent Framework for personal deployment and cross-device automation.</strong>
</p>

<p align="center">
  Built around a unified conversation engine and the VOTX multimodal gateway, integrating tool execution, task planning, persistent memory, knowledge bases, external message routing, and full-stack multimodal capabilities.<br>
  Designed as a deployable, extensible, and portable foundation for personal AI assistants, automated workflows, and multi-endpoint intelligent services.
</p>

<p align="center">
  <a href="./LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-orange" alt="license">
  </a>
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="python">
  </a>
  <a href="https://github.com/kesepain-KE/llm-adapter-votx">
    <img src="https://img.shields.io/badge/provider-VOTX%20LLM%20Adapter-brightgreen" alt="provider">
  </a>
  <a href="https://flask.palletsprojects.com/">
    <img src="https://img.shields.io/badge/web-Flask%20%2B%20React%20%2B%20TypeScript-lightgrey" alt="web">
  </a>
</p>

<p align="center">
  <a href="./README.md">中文</a> · English
</p>

> [!NOTE]
> votx-agent is intended for personal and small-scale multi-user deployments, with an emphasis on local execution, a unified toolchain, multimodal integration, and cross-platform messaging. It is developed and maintained independently from kemo-agent and does not inherit from it.

## Table of Contents

- [Positioning](#positioning)
- [Core Capabilities](#core-capabilities)
- [Capability Overview](#capability-overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Provider Configuration](#provider-configuration)
- [Multimodal Capabilities](#multimodal-capabilities)
- [Web and CLI](#web-and-cli)
- [External Message Router](#external-message-router)
- [Files and Knowledge](#files-and-knowledge)
- [Skills and Plugins](#skills-and-plugins)
- [Project Structure](#project-structure)
- [Updates](#updates)
- [Windows Packaging](#windows-packaging)
- [Development](#development)
- [Relationship to Adjacent Projects](#relationship-to-adjacent-projects)
- [Current Scope](#current-scope)
- [Contributing](#contributing)
- [License](#license)

---

## Positioning

votx-agent is a local-first, multi-user AI Agent framework designed for personal deployment.

It is neither a simple chat frontend nor a thin proxy around a model API. It is a complete Agent system capable of running continuously, receiving tasks from multiple endpoints, and coordinating tools, memory, files, knowledge, and multimodal services within one execution environment.

The framework unifies the following capabilities:

- Web and CLI interaction
- Model invocation and streaming event delivery
- Tool discovery, scheduling, and execution
- Task plans and scheduled jobs
- Temporary and permanent memory
- Self-improvement workflows
- User and shared knowledge bases
- QQ, Telegram, and other external message endpoints
- Image, audio, and video processing
- Per-user configuration, history, file, and memory isolation

votx-agent is suitable for:

- A continuously running local personal assistant
- A multi-device Agent service within a local network
- The intelligence core behind QQ or Telegram bots
- Unified automation, scheduled tasks, and multimodal workflows
- An Agent application layer built on top of VOTX LLM Adapter

---

## Core Capabilities

### Unified Conversation Engine

Web, CLI, and external messaging modules share a single conversation engine rather than duplicating Agent logic.

The engine builds the system prompt, manages conversation history, invokes the model, detects and executes tool calls, and supports multiple model-tool rounds until a final response is produced.

### Local Multi-User Isolation

Each user has an independent data workspace. The following data is isolated per user:

- Provider configuration
- System persona
- Conversation history
- Uploaded files
- Generated and downloaded files
- Private knowledge base
- Task plans
- Scheduled tasks
- Memory and self-improvement data

### VOTX Multimodal Provider

A single Provider layer exposes the following capabilities:

- Text generation
- Tool calling
- Image understanding
- Audio transcription
- Image generation
- Image editing
- Text-to-speech
- Speech-to-speech
- Video generation

When `base_url` points to a standard OpenAI-compatible endpoint, text, tool calling, and some multimodal features may still work. Advanced capabilities such as image editing, video generation, and specific ASR routes depend on endpoint support. VOTX LLM Adapter provides the complete capability surface.

### Tool-First Workflow

The framework prefers dedicated Skills for specialized work:

- File operations
- Network requests
- Downloads
- Web search
- Knowledge retrieval
- Multimodal processing
- Task planning
- Scheduled jobs
- External message delivery

`shell` remains available for diagnostics, builds, and system-level operations, but is not intended to be the default mechanism for every task.

### Task Plans and Scheduled Jobs

Complex requests can first be converted into structured task plans and then executed after user approval.

Task plans support:

- Creation
- Inspection
- Approval
- Pause
- Resume
- Abort
- Progress tracking

Scheduled jobs support:

- Creation
- Query
- Update
- Deletion
- Pause
- Resume
- Immediate execution

### Layered Memory and Self-Improvement

The system supports temporary and permanent memory layers with save, search, review, promote, delete, and cleanup operations.

Passive mode primarily handles temporary memory. Active review inspects both layers and promotes information with durable value to permanent storage.

### External Message Routing

The message subsystem connects platforms such as QQ and Telegram to the same Agent engine.

It supports:

- OneBot / NapCat
- Telegram Bot
- User identity binding
- Image, audio, video, and file attachments
- External commands
- Proactive message delivery
- Push queues
- Unified attachment archiving

### Local-First, Open Data Formats

Core data is stored as local files:

- JSON for configuration and state
- JSONL for history and attachment logs
- Markdown for personas, knowledge, Skills, and manuals
- Regular directories for uploads, downloads, and media assets

Users can inspect, edit, back up, migrate, and version their data without depending on a proprietary cloud storage layer.

---

## Capability Overview

| Subsystem | Capabilities |
|---|---|
| Conversation engine | Prompt construction, streaming responses, model-tool loops, history commits |
| Provider | VOTX LLM Adapter and OpenAI-compatible endpoints |
| Multi-user runtime | Isolated configuration, persona, history, files, knowledge, and tasks |
| Tool system | Built-in Plugins and user Skills with discovery, loading, and execution |
| Multimodal stack | Vision, ASR, image generation, image editing, TTS, speech-to-speech, video |
| Task planning | Draft, approval, execution, pause, resume, and abort |
| Scheduled tasks | Create, update, pause, resume, delete, and run immediately |
| Memory | Temporary memory, permanent memory, active review, and cleanup |
| Knowledge | Per-user and globally shared knowledge bases |
| Message routing | OneBot, NapCat, Telegram, identity mapping, and attachment processing |
| Web interface | Flask backend, SSE streaming, React + TypeScript frontend |
| Windows packaging | PyInstaller dual-EXE distribution with a shared runtime |

---

## Architecture

```text
                        ┌──────────────────────────────┐
                        │         User Inputs          │
                        │ Web / CLI / QQ / TG / Cron  │
                        └──────────────┬───────────────┘
                                       │
                        ┌──────────────▼───────────────┐
                        │   Unified Conversation Engine│
                        │        run/engine.py         │
                        └────────┬────────────┬────────┘
                                 │            │
                    ┌────────────▼───┐   ┌────▼────────────┐
                    │    Provider    │   │ Tool / Skill    │
                    │  VOTX Adapter  │   │    Execution    │
                    └────────┬───────┘   └────┬────────────┘
                             │                │
                  ┌──────────▼────────┐  ┌────▼─────────────┐
                  │ Text / Multimodal │  │ File / Network   │
                  │   Model Services  │  │ Search / Tasks   │
                  └───────────────────┘  └──────────────────┘
                                               │
                               ┌───────────────▼──────────────┐
                               │ History / Memory / Knowledge │
                               │       Local User Storage      │
                               └───────────────────────────────┘
```

---

## Quick Start

### Requirements

- Python 3.10+
- Git
- Node.js 18+ and npm, only for frontend development or rebuilding the Web client

### Clone the Repository

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
```

### Install and Initialize

```bash
python setup.py
python set_user.py add
```

### Start the Web Interface

```bash
python start_web.py
```

Default address:

```text
http://localhost:1478
```

### Start the CLI

```bash
python start.py
```

### Run a One-Shot Request

```bash
python start.py --user <username> --prompt "<message>" --once
```

---

## Provider Configuration

votx-agent uses a unified VOTX Provider implementation.

Keep `provider.type` set to:

```json
{
  "provider": {
    "type": "votx"
  }
}
```

The actual backend is determined by `base_url`.

### Recommended Mode

Point `base_url` to VOTX LLM Adapter:

```env
VOTX_BASE_URL=http://127.0.0.1:8741/v1
VOTX_API_KEY=your-api-key
```

This mode provides the complete VOTX multimodal capability surface.

### OpenAI-Compatible Mode

Point `base_url` to any service compatible with `/v1/chat/completions` and provide the corresponding API key.

In this mode:

- Text generation is usually available
- Tool calling depends on endpoint compatibility
- Image input depends on model capabilities
- Image editing, video generation, and some audio features may be unavailable

### Configuration Priority

```text
users/<name>/config.json
> environment variables
> program defaults
```

### Configuration Responsibilities

| File | Responsibility |
|---|---|
| `config/config_core.json` | Global defaults for history, tools, tasks, output, context, and improvement |
| `users/<name>/config.json` | User Provider, permissions, Skills, history, and task settings |
| `.env` | Startup parameters, secrets, and compatibility fallbacks |
| `message/config.local.json` | Private external-message configuration |
| `message/config.json` | Default external-message configuration |

---

## Multimodal Capabilities

### Capability Names

```text
vision
audio_transcription
image_generation
image_edit
speech_generation
speech_to_speech
video_generation
```

Model selection priority:

```text
dedicated capability model > default chat model
```

### Common Tools

| Tool | Purpose |
|---|---|
| `vision_analyze` | Analyze one or multiple images |
| `audio_transcribe` | Transcribe audio with multilingual and timestamp support |
| `image_generate` | Generate images from text |
| `image_edit` | Edit an input image |
| `speech_generate` | Generate speech from text |
| `speech_to_speech` | Transform speech into speech |
| `video_generate` | Create a video-generation job |
| `video_status` | Query video-generation status |
| `video_download` | Download the generated video |

Default output directory:

```text
users/<name>/download/
```

---

## Web and CLI

### Web Startup Options

```bash
python start_web.py
python start_web.py --port=8080
python start_web.py --host=0.0.0.0 --port=1478
```

### LAN Access

```env
VOTX_HOST=0.0.0.0
PORT=1478
VOTX_SESSION_COOKIE_NAME=votx_agent_session
```

Devices on the same network can then open:

```text
http://<server-lan-ip>:1478
```

<p align="center"><img src="votx-agent-web-UI.png" width="720" alt="votx-agent Web UI"></p>

When multiple Web applications run on the same IP with different ports, assign each one a unique `VOTX_SESSION_COOKIE_NAME` to prevent browser cookie collisions.

### Shared Slash Commands

| Command | Purpose |
|---|---|
| `/clear` | Clear the current conversation and tool logs |
| `/archive` | Archive the conversation and generate a summary |
| `/new` | Archive the current conversation and start a new one |
| `/summarize` | Generate a summary of the current conversation |
| `/compress` | Compress older history while keeping recent context |
| `/retry` | Remove the previous AI response and regenerate |
| `/history` | Show conversation statistics |
| `/stats` | Show conversation statistics |
| `/help` | Show available commands |

### CLI-Only Commands

```text
/exit
/quit
/q
```

Exiting the CLI triggers automatic summarization and persistence.

---

## External Message Router

### Configuration Priority

```text
VOTX_MESSAGE_CONFIG
> message/config.local.json
> message/config.json
```

### Supported Platforms

OneBot/NapCat (QQ) and Telegram Bot are supported, with user identity binding, media attachments, external commands, and proactive message delivery. Full configuration example available at `message/config.example.json`.

### Attachment Storage

External attachments:

```text
users/<username>/history/file/
```

Attachment log:

```text
users/<username>/history/log/external_attachments.jsonl
```

Supported media:

| Platform | Types |
|---|---|
| OneBot / NapCat | image, record, video, file |
| Telegram | photo, document, voice, audio, video |

External message commands:

```text
/cron list
/cron add
/cron update
/cron delete

/plan list
/plan view
/plan approve
/plan abort
```

Detailed configuration:

```text
knowledge/message-config.md
```

---

## Files and Knowledge

Each user has independent storage for configuration, persona, uploads, downloads, private knowledge base, task plans, and memory.

A two-tier knowledge base design prioritizes user-private knowledge, falling back to globally shared knowledge. Index files must be updated when knowledge bases change.

---

## Skills and Plugins

The framework uses two extension directories: `plugins/` for built-in capabilities and `skills/` for user extensions. Updates overwrite the former and preserve the latter.

Twenty built-in Skills cover file operations, command execution, networking, downloads, search, multimodal processing (vision, ASR, image generation/editing, TTS, speech-to-speech, video), memory management, task planning, scheduled jobs, message delivery, knowledge retrieval, and more. Core Skills cannot be disabled to ensure baseline functionality.

User Skills can override built-in Skills with `override: true`. Binary document processing relies on user Skills or external tools.

---

## Project Structure

```text
votx-agent/
├── agents/             # Sub-agents
├── config/             # Global configuration and base persona
├── cron/               # Scheduled task engine
├── knowledge/          # Global knowledge base and architecture docs
├── message/            # External message routing
├── plugins/            # Built-in Skills
├── provider/           # Provider adapter
├── run/                # Conversation engine and tool execution
├── skills/             # User extension Skills
├── users/              # User data workspace
├── web/                # Web management interface
├── setup.py            # Environment setup
├── set_user.py         # User management
├── update.py           # Cross-platform updater
├── start_web.py        # Web launcher
├── start.py            # CLI launcher
└── LICENSE             # MIT License
```

---

## Updates

### Check for Updates

```bash
python update.py --check
```

### Run the Update

```bash
python update.py --yes
```

### Preview the Update

```bash
python update.py --dry-run
```

Back up `users/`, `skills/`, `.env`, and private message configuration before manual updates.

---

## Windows Packaging

### Dual-EXE Architecture

PyInstaller uses `onedir` mode to generate two entry points:

```text
votx-agent-web.exe
votx-agent-cli.exe
```

Both executables share the same `_internal` runtime.

Plugins, Skills, configuration, and user directories remain outside the executables, preserving:

- Hot-swappable extensions
- Editable configuration
- Persistent user data
- Independent updates
- User-defined Skills

### Build Command

```cmd
build_windows.bat
```

Secrets, caches, and local runtime state are excluded from release packages.

---

## Development

The Web frontend uses React + TypeScript + Vite. Python code follows standard tooling conventions. Maintainers should refer to `AGENTS.md` and the architecture documentation in `knowledge/`. Read `AGENTS.md` before contributing.

---

## Relationship to Adjacent Projects

### VOTX LLM Adapter

[VOTX LLM Adapter](https://github.com/kesepain-KE/llm-adapter-votx) is the multimodal Provider gateway used by votx-agent.

It is responsible for:

- Normalizing heterogeneous model APIs
- Routing multimodal capabilities
- Adapting model, media, and endpoint protocols

votx-agent is responsible for:

- Conversation execution
- Tool invocation
- Task planning
- Memory and knowledge
- Web, CLI, and messaging endpoints
- User data management

### kemo-agent

kemo-agent is a separate Agent Runtime developed independently.

The projects have different priorities:

| Project | Positioning |
|---|---|
| votx-agent | A complete Agent framework for personal deployment, cross-device interaction, and multimodal services |
| kemo-agent | A multi-user Agent Runtime centered on lifecycle memory, structured orchestration, and long-running execution |

They do not share an inheritance relationship or internal implementation.

### Other Related Projects

- [NapCat](https://github.com/NapNeko/NapCatQQ) — QQ integration
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — Video and audio download engine

---

## Current Scope

votx-agent is currently intended for personal and small-scale multi-user environments.

Additional validation and hardening are required for:

- Large-scale public deployments
- High-concurrency multi-tenant services
- Enterprise-grade access control and audit
- Untrusted users with arbitrary code execution
- High-availability clusters
- Distributed scheduling
- Mission-critical production systems

`shell`, network access, file operations, and external message delivery are privileged capabilities. Deployers should configure tool allowlists, network scope, and user access controls according to their environment.

---

## Contributing

Issues and Pull Requests are welcome. For major architectural changes, open an Issue before implementation. Read `AGENTS.md` before contributing.

- [Issues](https://github.com/kesepain-KE/votx-agent/issues)
- [Pull Requests](https://github.com/kesepain-KE/votx-agent/pulls)

**Maintainer**: [@kesepain](https://github.com/kesepain-KE)

Thanks to everyone who contributes to development, testing, and documentation.

---

## License

This project is licensed under the [MIT License](./LICENSE).

Copyright © kesepain