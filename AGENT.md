# AGENT.md — kesepain-Agent 项目指南

## 这是什么

多用户 AI Agent 框架。Python 项目，调用 OpenAI 兼容 API，实现 **角色扮演 + 工具调用 + 对话持久化** 的完整 Agent 闭环。

- **入口**: `start.py` → 选择用户 → `main.py` 主循环（CLI）/ `start.py --web` → Web UI（端口 13579）
- **LLM**: DeepSeek API (OpenAI 兼容)，可替换任意 provider
- **平台**: Windows / WSL2 双环境

## 目录结构

```
kesepain-Agent/
├── start.py                  # 入口：扫描 users/ → 选择 → subprocess 启动 main.py / --web 启动 Web UI
├── main.py                   # CLI 核心：命令分发 + 对话循环（委托 run/engine.py）
│
├── config/
│   ├── config_core.json      # 全局配置（历史/工具限制）
│   └── soul.md               # 全局人设（可选，HTML注释占位则跳过）
│
├── provider/
│   └── openai_api.py         # DeepSeekProvider（流式/重试/.env加载/SSL_CERT_FILE修复）
│
├── run/
│   ├── engine.py             # 【共用引擎】build_system_prompt() + run_chat_turn() generator，CLI/Web 共用
│   ├── chat.py               # ChatManager：消息管理/历史CRUD/归档/清除
│   └── tool.py               # ToolRunner：注册表/权限校验/限流/日志
│
├── web/                      # 【Web UI】Flask + SSE 流式聊天
│   ├── server.py             # Flask 后端：20 个 /api 端点 + SSE 事件流
│   └── templates/
│       └── index.html        # 单页聊天界面（glassmorphism 设计，工具卡片/文件上传/Token 统计）
│
├── tmp/                      # 临时文件目录（测试脚本、转换中间件等，随时可删，已 gitignore）
│   └── README.md
│
├── skills/                   # 【agentskills.io 标准骨架】
│   ├── __init__.py           # register_all()：扫描 SKILL.md → 加载 tool.py
│   ├── _common/              # 公共模块（err/truncate/safe_path/log_tool_call）
│   ├── file/                    # 文件操作（read/write/list/delete + 路径沙箱）
│   ├── network/                 # HTTP 请求（http_get/http_post + SSRF防护）
│   ├── self-improving-agent/    # 自主学习（log_learning/log_error/log_feature_request）
│   ├── shell/                   # 系统命令（run_command + 危险参数拦截）
│   ├── tavily-search/           # 网络搜索（需 TAVILY_API_KEY）
│   ├── time/                    # 时间工具（get_time/sleep）
│   ├── uapi-hotboard-reporter/  # 热榜查询（需 UAPI_API_KEY）
│   ├── video-download/          # 视频下载（yt-dlp 封装）
│   ├── word-docx/               # Word 文档（python-docx 封装）
│   ├── agent-memory/            # 持久记忆（mem_remember/mem_recall 等 7 工具，/clear 不丢）
│   ├── vision/                  # [纯指令] 图像识别（GPT-4o-mini，通过 run_command 调用脚本）
│   ├── download-anything/       # [纯指令] 下载任意数字资源（yt-dlp/aria2/gallery-dl/网盘搜索）
│   ├── find-skills/             # [纯指令] 发现并安装 Agent Skills（npx skills CLI）
│   ├── pdf-tools/               # [纯指令] PDF 操作（提取/合并/拆分/旋转/编辑文字）
│   ├── skill-creator/           # [纯指令] 创建 agentskills.io 规范的新 Skill
│   ├── skill-vetter/            # [纯指令] Skill 质量审查
│   ├── web-content-fetcher/     # [纯指令] 网页内容获取
│   └── web-tools-guide/         # [纯指令] Web 开发工具指南
│
├── users/
│   ├── <name>/config.json    # 用户配置：provider/历史/工具权限
│   ├── <name>/self_soul.md   # 角色人设（system prompt，核心）
│   └── <name>/history/       # chat/ log/ archive/ file/
│
├── .env                      # 环境变量（API Key 等）
├── AGENT.md                  # 本文件
├── 开发文档.md               # 全文开发文档
└── 开发文档/                 # 分章节文档
```

## 核心架构

### 启动流

```
CLI:  start.py → 扫描users/ → 用户选择 → KESEPAIN_USER_DIR → main.py (子进程) → engine
Web:  start.py --web → Flask(端口13579) → 浏览器选择用户 → engine
engine: 加载配置 + .env → Provider → register_all() → ToolRunner → Skill 摘要 → 持久记忆注入 → run_chat_turn() generator
```

### Web UI / SSE 流式 API 端点

| 端点 | 说明 |
|------|------|
| `GET /` | 聊天界面 (index.html) |
| `GET /api/users` | 列出 users/ 目录下用户 |
| `POST /api/select-user` | 初始化会话（加载配置/provider/tool_runner/tools/chat） |
| `GET /api/session` | 当前会话状态（刷新恢复） |
| `POST /api/chat` | SSE 流式聊天；斜杠命令直接返回 JSON（支持 /retry） |
| `POST /api/upload` | 文件上传 → users/<name>/history/file/ |
| `GET /api/files` | 列出当前用户已上传文件 |
| `GET /api/files/view/<filename>` | 文件原始内容（图片预览等） |
| `DELETE /api/files/<filename>` | 删除单个文件 |
| `DELETE /api/files` | 批量/全部删除文件 |
| `POST /api/disconnect` | 保存历史并断开当前 Web 会话 |
| `GET /api/conversations` | 列出当前对话和归档对话（摘要优先） |
| `POST /api/load-conversation` | 加载归档对话替换当前对话 |
| `DELETE /api/conversations/<id>` | 删除指定归档对话 |
| `POST /api/conversations/<id>/rename` | 重命名归档对话 |
| `DELETE /api/conversations` | 删除全部归档对话 |
| `GET /api/config` | 获取用户配置 |
| `POST /api/config` | 更新用户配置（调试面板保存） |
| `GET /api/system-prompt` | 获取 system prompt（分段 soul/agent/other） |
| `GET /api/tool-logs` | 读取工具调用 JSON Lines 日志 |
| `GET /api/messages` | 当前会话消息列表 |
| `GET /api/export-markdown` | 导出当前对话为 Markdown |

### 对话循环内层（run/engine.py → run_chat_turn）

```python
# Generator yielding typed event dicts — CLI 和 Web 共用
for event in run_chat_turn(chat, tool_runner, provider, tools):
    # {"type": "tool_call", "name": str, "icon": str, "args": dict, "elapsed": float, "success": bool}
    # {"type": "text", "content": str}
    # {"type": "usage", "data": {"prompt_tokens": N, "completion_tokens": N, ...}}
    # {"type": "error", "content": str}
    # {"type": "deadlock_warning"}   # 同命令连败 3 次
    # {"type": "max_rounds"}         # 超过 MAX_TOOL_ROUNDS(20)
```

核心循环：
```
while tool_round < MAX_TOOL_ROUNDS(20):
    messages = chat.build_messages()     # system + history
    response = provider.chat(messages, tools)
    yield usage event
    if has_tool_calls(response):
        执行 → 逐工具 yield tool_call event → 死循环检测
    else:
        yield text event → break
```

### 持久记忆

### 命令分发 (`/` 开头走分发，否则走 LLM)

| 命令 | 行为 |
|------|------|
| `/exit` `/quit` `/q` | 退出 + 自动保存 |
| `/clear` | CLI: 先归档再清空 / Web: 仅清除历史和日志（不归档） |
| `/history` `/stats` | 显示消息数/大小/归档数/工具日志条数 |
| `/archive` | 仅归档不清空 |
| `/retry` | 移除上一条 AI 回复，重新生成 |
| `/summarize` `/总结` | 生成当前对话摘要 |
| `/help` | 帮助 |

### 工具调用链

```
LLM tool_calls → ToolRunner.execute()
  → _check_limit()        # deny黑名单 > enabled开关 > 全局/单工具上限
  → json.loads(args)      # 解析参数
  → handler(**kwargs)     # 执行
  → log_tool_call()       # JSON Lines 日志
  → 返回 [{"role":"tool", "tool_call_id":..., "content":...}]
```

### Token 统计

`provider.last_usage` 存储最近一次 API 调用用量：
```python
{"prompt_tokens": N, "completion_tokens": N, "total_tokens": N, "cached_tokens": N}
```
每轮工具调用后显示，对话结束后输出累计值。

## Skill 规范

遵循 **[agentskills.io](https://agentskills.io/specification)** 标准：

```
skills/<skill-name>/
├── SKILL.md      # 必需：YAML frontmatter(name+description) + Markdown 指引
├── tool.py       # 可选（本项目扩展）：含 register()，注册 OpenAI function schema
├── scripts/      # 可选：内部脚本
├── references/   # 可选：参考文档
└── assets/       # 可选：模板/静态资源
```

- `SKILL.md` 是唯一必需文件（agentskills.io 规范）。启动时注入摘要（name+description）到 system prompt（渐进披露），详细正文由 LLM 按需通过 `read_file` 读取。
- **新 Skill 一律用 agentskills.io 标准框架（纯指令型）**：仅 SKILL.md + 可选的 scripts/、references/、assets/。不加 tool.py。LLM 通过 `run_command` 调用 scripts/ 下的脚本来完成具体操作。
- `tool.py` 是本项目的 **OpenAI function calling 扩展**（仅现存的 10 个核心基础设施 Skill 保留，不再新增工具型 Skill）。
- **前例**: vision Skill 初版用了 tool.py，不符合标准，已于 2026-05-02 重构为纯指令型（删除 tool.py → 创建 scripts/vision_infer.py + 更新 SKILL.md）。以后严禁再走此弯路。
- **Skill 安装路径硬规则**: 所有 Skill 必须放在项目根目录的 `skills/` 下。禁止安装到 `users/<name>/skills/` 或任何其他位置。用 skillhub 安装时必须指定 `--dir skills/`。
- `name` 必须与文件夹名完全一致，仅限小写字母+数字+连字符，64 字符内。
- `description` 需同时描述功能和使用时机，1024 字符内。

**SKILL.md 最小模板**:
```markdown
---
name: my-skill
description: 当用户需要 xxx 时使用。描述功能和使用时机。
compatibility: 需要 python-docx 和网络访问（可选）
---
# 使用指引
...
```

**tool.py 最小模板** (可选，仅当 Skill 需要工具调用时):
```python
from run.tool import register_tool
from skills._common import err, truncate

def my_func(param: str) -> str:
    try:
        return f"OK: {param}"
    except Exception as e:
        return err(f"失败: {e}")

SCHEMA = {"type":"function","function":{"name":"my_func",...}}

def register():
    register_tool(SCHEMA, my_func)
```

放入 `skills/` 后自动发现，无需改任何注册代码。

## 安全机制

| 机制 | 实现 |
|------|------|
| 路径沙箱 | `safe_path()` — 仅允许用户目录+项目根 |
| 权限系统 | deny(黑名单) > enabled(用户) > enabled(全局) |
| 工具限流 | tool_max(100) + tool_max_per_type(50) + MAX_TOOL_ROUNDS(20) |
| Shell 安全 | shell=False + shlex.split + 危险参数黑名单 |
| SSRF 防护 | 拦截内网/回环地址 + DNS 二次校验 |
| 输出截断 | 8000字符截断 + 标注 |
| 统一错误 | `err("msg")` → `"ERROR: msg"`，异常全捕获 |
| 工具日志 | JSON Lines → `history/log/tool_log.json`，过滤敏感参数 |

## 添加功能怎么做

### 添加 Skill
在 `skills/` 下创建目录含 SKILL.md，重启自动生效。如需工具调用再加 tool.py。纯指令 Skill（无 tool.py）同样生效——摘要注入 system prompt，正文按需读取。

### 添加命令
在 `main.py` 的 `_dispatch()` 里加 `elif` 分支。返回 True=退出，False=已处理，None=交给LLM。

### 修改配置
- 全局限制：`config/config_core.json`
- 用户级：`users/<name>/config.json`
- 环境变量：`.env`（手动解析，不依赖 python-dotenv）

### 替换 LLM
`provider/` 下新建类，实现 `__init__(user_config)` + `chat(messages, tools) -> Message`，main.py 替换 import。

## 代码约定

- Python 3.10+，无 `python-dotenv` 依赖（手动解 `.env`）
- 文件名避免与 stdlib 冲突（如 `http.py` 已改名 `network.py`）
- 模块导入失败不崩启动——`register_all()` 是尽力而为模式
- 工具返回 `ERROR:` 前缀直接交 LLM，不自动中断（LLM 能根据具体错误调整）
- `_` 开头的目录/文件视为内部模块，不被扫描为 Skill
- API Key 从 `.env` 加载时不覆盖已有环境变量
- 开发文档是所有细节的权威来源：`开发文档.md` + `开发文档/`
- **路径优先级**: 相对路径 > 绝对路径 > 容器/WSL 路径。引用文件优先用相对路径（如 `users/kesepain/self_soul.md`），绝对路径仅当用户明确给出时才用，WSL 路径（`/mnt/e/...`）只在确认环境是 WSL/容器时使用
- 路径中包含方括号 `[]`、空格、中文等特殊字符时，用引号包裹，优先用 `list_dir` 验证路径存在再操作

## 重要操作规范

### 临时文件管理

**所有临时文件**（一次性测试脚本、转换中间件、调试代码）必须放到 `tmp/` 目录下，严禁扔在工作区根目录。

```
tmp/
├── .gitkeep       # 占位
└── README.md      # 说明
```

- `tmp/` 已加入 `.gitignore`，随时可以清空
- 不要放重要数据
- Skill 内部转换中间件（如 ico→png）也优先往这里输出

### vision Skill 使用规范

`skills/vision/` 是纯指令型 Skill，通过 `run_command` 调用 `scripts/vision_infer.py`：

**路径规则**：始终优先用相对路径（相对项目根目录）
```cmd
# ✅ 正确
python skills/vision/scripts/vision_infer.py users/kesepain/history/file/photo.jpg

# ✅ 指定 python 解释器（当 run_command shell 默认不是 Anaconda 时）
D:\Anaconda\envs\kesepain\python.exe skills/vision/scripts/vision_infer.py users/kesepain/history/file/photo.jpg
```

**脚本特性**（已内建）：
- 相对路径自动解析到项目根（`resolve_image_path()`）
- 从 `.env` 自动加载环境变量（`load_env()`）
- 支持 ico/jpg/png/webp/gif/bmp 格式
- 自动检测 Windows 系统代理或环境变量代理
- 代理连通性用 `baidu.com` 测试（不消耗 API 额度）
- 代理不可用时自动回退直连

**调用失败排查**：
1. 确认 `.env` 中有 `OPENAI_API_KEY`
2. 如果 401 错误，检查 API Key 是否有效
3. 如果 400 错误且提示格式不支持，用 Pillow 转成 png → `tmp/` 目录下
4. 如果超时，检查代理是否开启

### 历史记录清理规范

根目录下的历史遗留测试脚本（如 `find_img.py`、`test_proxy.py`）发现后直接删除，功能已合并进对应 Skill 的不要保留副本。

## 注意事项

- Windows 中文环境 subprocess 编码问题已修复（`encoding="utf-8", errors="replace"`）
- Web UI 依赖 Flask：普通 Python 可用 `pip install -r requirements.txt`；MSYS2/MINGW64 Python 优先用 `pacman -S --needed mingw-w64-x86_64-python-flask`
- **工具加载顺序**：`build_system_prompt()` 必须在 `load_tool_schemas()` 之前调用（前者内部的 `register_all()` 填充 TOOL_REGISTRY）
- Windows SSL_CERT_FILE 环境变量指向不存在文件会导致 httpx 崩溃，`provider/openai_api.py` 和 `web/server.py` 已做防御
- 热榜查询需额外配置 `UAPI_API_KEY`
- 网络搜索需配置 `TAVILY_API_KEY`：`pip install tavily-python`
- 视频下载依赖 yt-dlp：`pip install yt-dlp`
- Word 文档依赖 python-docx：`pip install python-docx`
- 历史文件损坏时自动重命名为 `.corrupt` 并重置
- 归档文件名精确到微秒避免冲突
- WSL2 下开发，Windows 下运行——两环境依赖可能不同


## 可用 Skill 目录（详细指令用 read_file 读取 SKILL.md）

### 工具型 Skill（可 function call）
- **agent-memory** (🔧 工具型): 持久记忆系统 — 记住事实(mem_remember)、回忆信息(mem_recall)、记录经验教训(mem_learn)、追踪人/项目/实体(mem_track_entity)。当你需要主动存储或查询跨会话信息时使用——比如用户告诉你个人信息、偏好，或者你想回顾之前学到的教训。
- **file** (🔧 工具型): 文件操作工具集 — 读取、写入、列出目录、删除文件。所有操作限制在用户目录和项目目录的沙箱内。当 Agent 需要读写文件、浏览目录或删除文件时使用。
- **network** (🔧 工具型): HTTP 网络请求工具 — GET/POST。内置 SSRF 防护（拦截内网/回环地址，DNS 二次解析校验）。当 Agent 需要访问外部 API 或网页时使用。
- **self-improving-agent** (🔧 工具型): Captures learnings, errors, and corrections to enable continuous improvement. Use when: (1) A command or operation fails unexpectedly, (2) User corrects Claude, (3) User requests a capability that doesn't exist, (4) An external API or tool fails, (5) Claude realizes its knowledge is outdated or incorrect, (6) A better approach is discovered for a recurring task. Also review learnings before major tasks.
- **shell** (🔧 工具型): Shell scripting reference — Bash syntax, redirections, process substitution, signal handling, debugging techniques. Use when writing shell scripts, troubleshooting Bash behavior, or automating system tasks.
- **tavily-search** (🔧 工具型): Tavily 网络搜索 — 专为 AI Agent 设计的搜索引擎，返回结构化结果（标题、URL、摘要）。当 Agent 需要搜索最新信息、查资料时使用。
- **time** (🔧 工具型): 时间工具 — 获取当前 UTC/本地时间、可控延时。当 Agent 需要知道当前时间或等待时使用。
- **uapi-hotboard-reporter** (🔧 工具型): UAPI 全网热榜查询 — 抓取多平台热搜并生成报告。支持视频区和新闻区，可按平台和关键词筛选。Agent 查询热搜、热榜、热点话题时使用。
- **video-download** (🔧 工具型): 使用 yt-dlp 下载视频。用户提到下载视频、B站、YouTube、抖音等平台的视频时使用。支持指定输出目录、文件名、格式选择。
- **word-docx** (🔧 工具型): Word 文档工具 — 创建和读取 .docx 文件。支持标题、正文、表格。当 Agent 需要生成 Word 文档或读取 .docx 文件内容时使用。

### 指令型 Skill（正文引导）
- **download-anything** (📋 指令型): >
- **find-skills** (📋 指令型): Helps users discover and install agent skills when they ask questions like "how do I do X", "find a skill for X", "is there a skill that can...", or express interest in extending capabilities. This skill should be used when the user is looking for functionality that might exist as an installable skill.
- **pdf-tools** (📋 指令型): View, extract, edit, and manipulate PDF files. Supports text extraction, text editing (overlay and replacement), merging, splitting, rotating pages, and getting PDF metadata. Use when working with PDF documents for reading content, adding/editing text, reorganizing pages, combining files, or extracting information.
- **skill-creator** (📋 指令型): Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an existing skill) that extends Claude's capabilities with specialized knowledge, workflows, or tool integrations.
- **skill-vetter** (📋 指令型): Security-first skill vetting for AI agents. Use before installing any skill from ClawdHub, GitHub, or other sources. Checks for red flags, permission scope, and suspicious patterns.
- **vision** (📋 指令型): 图像识别与分析。使用 OpenAI GPT-4o-mini 多模态模型分析图片内容。当用户上传图片、需要识别图像内容、提取图片文字、分析截图时使用。
- **web-content-fetcher** (📋 指令型): 网页内容获取工具 | 当 http_get 无法获取内容时（空白、403、CAPTCHA），使用替代服务获取网页 Markdown。通过 http_get 调用 r.jina.ai / markdown.new / defuddle.md 等第三方转码服务。触发词：获取网页内容、网页转markdown、内容抓取、fetch webpage、bypass cloudflare
- **web-tools-guide** (📋 指令型): 网页获取决策指南 — 当前项目可用的网页获取路径：1) tavily_search（搜索信息）2) http_get（直接获取网页内容）3) web-content-fetcher 技能（r.jina.ai 等转码服务兜底）。当用户要求搜索、查资料、获取网页内容时读取本指南，按决策流程选择最佳路径。

## 持久记忆（跨会话保留，/clear 不清除）
以下是从持久记忆中加载的已知信息：
- 已安装 skillhub CLI，并安装了 file-search 技能到 skills/file-search/ [安装记录, skillhub]
- 用户的名字是 kesepain [用户信息, 名字]
- vision_infer.py 优化：支持相对路径 + .env 自动加载 + ico 格式 + 代理用百度测试 [best_practice, vision]

请在对话中直接使用这些信息，无需再次询问用户。如果用户修改了某项信息，用 mem_remember 更新并用 mem_recall 确认。
