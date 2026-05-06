<p align="center"><img src="votx-agent.png" width="160" alt="votx-agent"></p>

# votx-agent

[![License](https://img.shields.io/badge/license-MIT-orange)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Multi-LLM](https://img.shields.io/badge/LLM-OpenAI%20%7C%20Anthropic-brightgreen)]()
[![Flask](https://img.shields.io/badge/web-Flask%20%2B%20Vue%203-lightgrey)](https://flask.palletsprojects.com/)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](https://www.docker.com/)

[中文](./README.md) | English

A multi-user AI Agent framework with role personas, tool calling, persistent memory, and a self-learning loop. Supports dual LLM protocols (OpenAI + Anthropic), multi-vendor access, with both CLI and Web UI sharing the same conversation engine.

## Table of Contents

- [Background](#background)
- [Installation](#installation)
  - [Docker Deployment](#docker-deployment)
  - [Native Ubuntu Deployment](#native-ubuntu-deployment)
  - [Manual Installation](#manual-installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Skills and Tools](#skills-and-tools)
- [Core Design](#core-design)
- [Configuration](#configuration)
- [Dependencies](#dependencies)
- [Development](#development)
- [Related Projects](#related-projects)
- [Maintainer](#maintainer)
- [Contributing](#contributing)
- [License](#license)

## Background

Most AI Agent frameworks on GitHub are built for single-user, English-first scenarios, and their interaction model often stops at a CLI or API. votx-agent is designed for Chinese users and provides:

- **Dual protocol support**: OpenAI protocol (Responses API / Chat Completions) and Anthropic protocol (Messages API) with a unified internal format
- **Multi-vendor access**: DeepSeek / Anthropic / Azure / SiliconFlow / Groq / Xiaomi Mimo — switch by changing `base_url`
- **Multi-user isolation**: each user has an independent persona (`self_soul.md`), conversation history, long-term memory, tool logs, and file space
- **Dual client support**: Vue 3 Web UI and CLI terminal share the same `run/engine.py` conversation engine with consistent behavior
- **Self-learning**: failed tool calls are automatically recorded as lessons and injected as rules before future conversations
- **Long-conversation friendly**: automatic summaries and archives keep context from growing without bound

> This project is part of the [kesepain-KE](https://github.com/kesepain-KE) repository family and is under active iteration.

## Installation

### Requirements

- Python 3.10 or later, not required for Docker deployment

### Get an API Key

Any of the following providers is supported (configure via the Web debug panel or `config.json`):

- [DeepSeek](https://platform.deepseek.com/api_keys) — free quota available
- [Anthropic Claude](https://console.anthropic.com/) — Messages API
- [OpenAI](https://platform.openai.com/) — Responses API / Chat Completions
- Other OpenAI-compatible providers (SiliconFlow, Groq, Xiaomi Mimo, etc.)

Optional services:

- [Tavily Search](https://tavily.com/) — required by the web search Skill
- [UAPI](https://uapi.icu/) — required by the hotboard query Skill

### Docker Deployment

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
docker compose up -d
```

After the container starts, configure your key in one of the following ways:

**Option A: Create a user, recommended for per-user keys**

```bash
docker exec -it votx-agent python set_user.py add
# Enter username, model, API key, and other settings interactively
```

**Option B: Configure the global .env file**

Edit `.env` in the project directory, add your key, then restart:

```bash
docker compose restart
```

After configuration, visit `http://localhost:1478`.

### Native Ubuntu Deployment

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
bash install.sh
```

`install.sh` completes virtual environment creation, dependency installation, `votx` command registration, and **interactive user creation** where you can enter a per-user API key.

Start after installation:

```bash
votx        # Start Web UI at http://localhost:1478
```

### Manual Installation

Use this path when you do not want to use the deployment methods above:

```bash
git clone https://github.com/kesepain-KE/votx-agent.git
cd votx-agent
python setup.py          # Install dependencies and optionally guide .env configuration
python set_user.py add   # Create a user and optionally enter a per-user API key
```

### Windows Build (PyInstaller)

If you wish to package this project as a standalone executable directory on Windows, use the provided build script:

```cmd
build_windows.bat
```

The script will automatically check for and install `pyinstaller`, and then bundle the project. After the build completes, find the `votx-agent.exe` application inside the `dist\votx-agent\` directory. Double-click it to start the Web UI (you can also pass startup parameters like `--port=1478` via command line).

`.env` template (fallback only, `config.json` takes priority):

```bash
# OpenAI protocol fallback, config.json api_key takes priority
DEEPSEEK_API_KEY=sk-your-key-here
# DEEPSEEK_BASE_URL=https://api.deepseek.com

# Anthropic protocol fallback
# ANTHROPIC_API_KEY=sk-ant-your-key-here

# Optional tool keys
# UAPI_API_KEY=***
# TAVILY_API_KEY=***
```

## Usage

### Start

```bash
# Ubuntu, after install.sh
votx                   # Web UI at http://localhost:1478
votx web               # Same as above
votx cli               # Terminal chat mode
votx help              # Show help
votx web --port=8080   # Custom port

# Manual / Windows
python start_web.py              # Web UI at http://localhost:1478
python start_web.py --port=8080  # Custom port, auto-increments on conflict
python start.py                  # CLI mode
```

Open `http://localhost:1478` in your browser and select a user from the left sidebar to start chatting.

### Slash Commands

| Command | Environment | Description |
|---|---|---|
| `/clear` | CLI + Web | Clear the current conversation and tool logs |
| `/history` | CLI + Web | View session statistics |
| `/retry` | CLI + Web | Revoke the previous AI response and regenerate |
| `/help` | CLI + Web | Show help information |
| `/exit` `/quit` `/q` | CLI only | Exit and automatically save history |

The Web client also provides conversation archives, Markdown export, and tool-call log viewing.

### Conversation Example

```text
You: Check today's hotboard and save the titles to a file
  [tavily_search] → Fetching hotboard data...
  [write_file] → Written to hotboard.txt
Assistant: Today's hotboard has been saved to hotboard.txt, 50 items in total.
[Token: input 2100 (cache hit 1950) | output 180 | total 2280]
```

![Web UI Screenshot](votx-agent-web-UI.png)

## Project Structure

```text
votx-agent/
├── votx.py                     # Entry command, votx web/cli/help
├── start.py / start_web.py     # Startup entry points, CLI / Web
├── setup.py / set_user.py      # Installation and user configuration wizards
├── install.sh                  # One-click Ubuntu installer
├── requirements.txt
├── Dockerfile                  # Docker image
├── docker-compose.yml          # Docker Compose configuration
├── docker-entrypoint.sh        # Docker entrypoint, checks users/keys without blocking startup
│
├── provider/                   # Multi-LLM backend, unified ProviderResponse format
│   ├── schema.py               # Unified data structures: ToolCall / ProviderResponse
│   ├── base.py                 # Abstract BaseProvider interface
│   ├── factory.py              # create_provider() factory
│   ├── responses_api.py        # OpenAI Responses API + Chat Completions fallback
│   ├── openai_api.py           # OpenAI Chat Completions API
│   └── anthropic_adapter.py    # Anthropic Messages API adapter
│
├── run/                        # Conversation engine shared by CLI and Web
│   ├── engine.py               # System prompt building and tool_calls loop
│   ├── chat.py                 # Conversation history and archive management
│   ├── tool.py                 # Tool registration and execution
│   └── summarize.py            # Summary generation and archive index
│
├── web/                        # Web UI
│   ├── server.py               # Flask + SSE event stream
│   ├── routes/                 # API routes
│   └── templates/index.html    # Vue 3 single-page frontend
│
├── skills/                     # 20 Skills, tool Skills and instruction Skills
├── config/                     # Global configuration and AI execution rules
├── tmp/                        # Agent temp files (scripts, runtime artifacts, pushable)
├── users/                      # User data, personas, history, memory, files
└── 开发文档/                    # Maintainer docs, local gitignored
```

## Skills and Tools

| Category | Count | Description |
|---|---:|---|
| Tool Skills | 10 | Register function calling tools: file read/write, HTTP requests, shell execution, time, Word documents, video download, web search, hotboard query, long-term memory, and ontology |
| Instruction Skills | 10 | Inject system prompt behavior guides: vision recognition, file search, PDF processing, web content fetching, self-improvement memory, and more |

All Skills are located in the `skills/` directory and can be extended as needed.

## Core Design

**Conversation flow**

```text
User input → build_system_prompt() → create_provider(config)
  → respond_stream(messages, tools) → ProviderResponse
  → Parse tool_calls → Execute tools → Return results → Continue reasoning
  → No tool_calls or round limit reached (20 rounds) → Save history
```

- The system prompt is dynamically assembled from the user's persona, Skill catalog, self-improvement memory, long-term memory, and other components
- The Web UI streams reasoning progress and response content in real time through SSE
- Tool-call chaining is automatically repaired when needed and supports multi-round continuous reasoning

**Self-learning**

Successful and failed tool executions both generate learning records. Relevant lessons are automatically injected into future conversations for continuous improvement.

**Long-conversation management**

History is saved as structured JSON. Very long sessions are automatically summarized and archived, then retrieved later on demand.

## Configuration

After a user is created, `users/<name>/` contains that user's independent persona, configuration, and data directories.

### Provider config (`users/<name>/config.json`)

```json
{
  "provider": {
    "type": "openai",
    "api_style": "chat",
    "model": "deepseek-v4-pro",
    "api_key": "sk-xxx",
    "base_url": "https://api.deepseek.com",
    "think": true,
    "stream": true
  }
}
```

- `type`: `"openai"` (OpenAI protocol) or `"anthropic"` (Anthropic protocol)
- `api_style`: `"responses"` (Responses API) or `"chat"` (Chat Completions), OpenAI protocol only
- Changes take effect immediately after clicking "Save" in the Web panel. No restart required.

### Priority

`config.json` > `.env` environment variables. `.env` serves as a global fallback only.

> `.gitignore` excludes runtime data such as `users/*/history/`, `users/*/tmp/`, `memory/`, and `logs/`, private files such as `.env` and `*.key`, build caches such as `__pycache__/`, and `开发文档/`. The project-level `tmp/` is the agent temporary file directory and is pushable. See [`.gitignore`](./.gitignore) for details.

## Dependencies

- Python 3.10+ · Flask ≥ 3.0 · openai ≥ 1.0 · anthropic ≥ 0.30
- requests · yt-dlp · python-docx · pyyaml, and more

See [requirements.txt](./requirements.txt) for the full list.

## Development

```bash
python setup.py --check     # Check environment only
python setup.py --skip-env  # Skip .env configuration
pytest                      # Run tests
```

Maintainer docs in `开发文档/` are gitignored and not included in the public repository. [`AGENTS.md`](./AGENTS.md) is the operation manual for AI coding agents.

## Related Projects

- [OpenAI Responses API](https://platform.openai.com/docs/guides/responses) — primary protocol, auto-fallback to Chat Completions
- [Anthropic Messages API](https://docs.anthropic.com/) — native extended thinking support
- [standard-readme](https://github.com/RichardLitt/standard-readme) — English README standard
- [ChineseREADME](https://sunyctf.github.io/ChineseREADME/) — reference for this Chinese README
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — video download engine

## Maintainer

[@kesepain](https://github.com/kesepain-KE) — project creator and main maintainer

## Contributing

Pull Requests and Issues are welcome:

- [Pull Requests](https://github.com/kesepain-KE/votx-agent/pulls)
- [Issues](https://github.com/kesepain-KE/votx-agent/issues)

Please read [`AGENTS.md`](./AGENTS.md) before contributing. For large changes, open an Issue first to discuss the plan and avoid duplicated work.

### Contributors

Thanks to everyone who contributes to this project.

## License

[MIT](./LICENSE) © kesepain
