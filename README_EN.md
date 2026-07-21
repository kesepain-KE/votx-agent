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

`run/engine.py` is the single execution entry point for all conversational workloads.

Web, CLI, and external messaging modules do not implement separate Agent logic. They convert input into a unified request, invoke the same engine, and render the resulting event stream.

Core execution flow:

```text
User input
→ ChatManager.add_user_message()
→ engine.run_chat_turn()
→ Build system prompt and conversation history
→ Stream Provider response
→ Detect and execute tool calls
→ Persist tool calls and tool results
→ Continue the model loop
→ Commit the final response and history
```

The model can enter multiple tool-call rounds until it produces a final response or reaches the configured `MAX_TOOL_ROUNDS` limit.

### Local Multi-User Isolation

Each user has an independent data workspace:

```text
users/<name>/
├── config.json
├── self_soul.md
├── avatar/
├── history/
├── knowledge/
├── download/
├── task-plan/
├── tasks/
└── improve/
```

The following data is isolated per user:

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

votx-agent integrates with VOTX LLM Adapter through plain HTTP and does not depend on the OpenAI SDK.

The same Provider layer can expose:

- Text generation
- Tool calling
- Image understanding
- Audio transcription
- Image generation
- Image editing
- Text-to-speech
- Speech-to-speech
- Video generation

When `base_url` points to a standard OpenAI-compatible endpoint, text, tool calling, and some multimodal features may still work. Advanced capabilities such as image editing, video generation, and specific ASR routes depend on whether the target endpoint implements the required APIs.

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

`auto_improve` organizes long-term data into three domains:

```text
memory
self-improving
ontology
```

The system supports temporary and permanent memory layers, with operations for:

- Save
- Search
- Review
- Promote
- Delete
- Cleanup

Passive mode primarily works on temporary memory. Active review can inspect both temporary and permanent memory, promoting information that has durable value.

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

### Request Lifecycle

```text
Request received
→ Load user configuration and persona
→ Build the system prompt
→ Load current conversation history
→ Invoke the Provider
→ Stream text and reasoning events
→ Detect tool calls
→ Execute tools and append results
→ Continue the model loop
→ Persist the final response
→ Update history, tasks, and memory state
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

### Provider Structure

```text
provider/
├── base.py          # BaseProvider abstraction
├── schema.py        # ToolCall and ProviderResponse models
├── factory.py       # create_provider()
└── votx_adapter.py  # Pure urllib HTTP Provider
```

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

### User Configuration Example

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

<p align="center"><img src="votx-agent-web-UI.png" width="720" alt="votx-agent Web UI"></p>
```

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

Full example:

```text
message/config.example.json
```

### OneBot / NapCat

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

### Telegram

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

| Path | Purpose |
|---|---|
| `users/<name>/config.json` | User model, API key, timeout, tool, and Skill configuration |
| `users/<name>/self_soul.md` | User persona layered into the system prompt |
| `users/<name>/avatar/` | User avatar |
| `users/<name>/history/file/` | Uploaded files and external attachments |
| `users/<name>/download/` | Generated, exported, and downloaded artifacts |
| `users/<name>/knowledge/` | Private user knowledge base |
| `users/<name>/task-plan/` | Task plans |
| `users/<name>/tasks/` | Scheduled jobs |
| `users/<name>/improve/` | Memory, self-improvement, and ontology data |
| `knowledge/` | Global knowledge base and framework documentation |
| `tmp/` | Temporary scripts and intermediate caches |

### Knowledge Indexes

After adding, modifying, deleting, moving, or renaming a user knowledge file, update:

```text
users/<name>/knowledge/data_structure.md
```

After changing the global knowledge base, update:

```text
knowledge/data_structure.md
```

Retrieval priority:

```text
user knowledge > global knowledge
```

---

## Skills and Plugins

The framework uses two extension directories:

| Directory | Role |
|---|---|
| `plugins/` | Built-in framework capabilities that may be overwritten by updates |
| `skills/` | User extensions that are preserved across updates |

The current source tree contains 20 plugin directories:

- 18 tool-oriented Skills
- 2 instruction-only Skills

### Built-In Capabilities

| Skill | Main Capabilities |
|---|---|
| `file` | Read, write, append, edit, search, copy, move, and delete files |
| `shell` | Cross-platform commands, cwd, environment variables, stdin, and sessions |
| `network` | HTTP requests, page reading, and network-scope control |
| `download_anything` | URL inspection and file or media downloads |
| `tavily_search` | Search, extraction, crawling, site maps, and deep research |
| `time` | Current time and waits up to 30 minutes |
| `audio_universal` | Audio transcription |
| `vision_universal` | Local and remote image understanding |
| `image_generation` | Text-to-image generation |
| `image_edit` | Image editing |
| `speech_generation` | Text-to-speech generation |
| `speech_to_speech` | Speech-to-speech transformation |
| `video_generation` | Video generation, status, and download |
| `auto_improve` | Memory saving, search, review, and cleanup |
| `task_plan` | Complex task planning and progress management |
| `task_time` | Scheduled task management |
| `qq_send` / `qq_file` | QQ and Telegram message or file delivery |
| `kb_retriever` | Two-layer knowledge retrieval workflow |
| `skill_creator` | Skill authoring specification |

### Core Skills

The following Skills are required by the framework and cannot be disabled:

```text
file
shell
time
network
task_plan
auto_improve
skill_creator
task_time
kb_retriever
```

A user Skill can override a built-in Skill with:

```yaml
override: true
```

Legacy PDF, DOCX, and document-conversion plugins are no longer bundled. Binary document processing must be provided by a user Skill, an external utility, or another service.

---

## Project Structure

```text
votx-agent/
├── agents/             # Sub-agents: auto_improve and task_plan
├── config/             # Global configuration and base persona
├── cron/               # Scheduled task engine
├── knowledge/          # Global knowledge base and architecture docs
├── message/            # OneBot, Telegram, push queue, and identity mapping
├── plugins/            # Built-in Skills
├── provider/           # VOTX Provider and unified response models
├── run/                # Conversation engine, history, tools, summaries, prompt cache
├── skills/             # User extension Skills
├── users/              # User config, history, files, knowledge, and memory
├── web/                # Flask + React + TypeScript + Vite
├── AGENTS.md           # Agent operation manual
├── main.py             # CLI entry point
├── start.py            # CLI / Web selection entry
├── start_web.py        # Web entry point
├── windows_entry.py    # Windows dual-EXE dispatcher
├── setup.py            # Setup script
├── set_user.py         # User management script
├── update.py           # Cross-platform updater
├── paths.py            # Development and PyInstaller path resolution
├── version.json        # Version information
├── requirements.txt    # Python dependencies
├── votx-agent.spec     # PyInstaller specification
├── build_windows.bat   # Windows build script
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

Update flow:

1. Compare the local `version.json` with the remote version
2. Shallow-clone the latest source into a temporary directory
3. Back up the current framework files
4. Synchronize code while excluding user data and build artifacts
5. Process `config/` and `knowledge/`
6. Repair missing user directory structures
7. Refresh Python dependencies

Back up the following before manual updates:

```text
users/
skills/
.env
message/config.local.json
message/push_queue/
```

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

### Main Package Contents

```text
votx-agent-web.exe
votx-agent-cli.exe
_internal/

agents/
config/
cron/
message/
plugins/
provider/
run/
skills/
web/
users/
tmp/
knowledge/

paths.py
AGENTS.md
set_user.py
setup.py
start.py
start_web.py
main.py
update.py
windows_entry.py
requirements.txt
version.json
.env.example
```

Secrets, caches, and local runtime state are excluded from release packages.

---

## Development

### Python Validation

```bash
python -m py_compile <file.py>
python -m compileall -q .
```

### Web Frontend

```bash
cd web
npm install
npm run dev
npm run build
npx tsc --noEmit
```

### Maintainer Documentation

```text
AGENTS.md
knowledge/
使用手册-AI/
```

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

## Maintainer

[@kesepain](https://github.com/kesepain-KE)

---

## Contributing

Issues and Pull Requests are welcome:

- [Issues](https://github.com/kesepain-KE/votx-agent/issues)
- [Pull Requests](https://github.com/kesepain-KE/votx-agent/pulls)

For major architectural changes, open an Issue before implementation.

Recommended workflow:

```bash
git checkout -b feature/your-feature
git commit -m "feat: describe your change"
git push origin feature/your-feature
```

Read before contributing:

```text
AGENTS.md
```

---

## Contributors

Thanks to everyone who contributes to development, testing, and documentation.

[@kesepain](https://github.com/kesepain-KE)

---

## License

This project is licensed under the [MIT License](./LICENSE).

Copyright © kesepain