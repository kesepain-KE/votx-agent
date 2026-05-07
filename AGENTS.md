# AGENTS.md

我的自我操作手册。每次启动时由 `run/engine.py` 注入到我的 system prompt 中。

> 遵循 [agents.md](https://agents.md/) 开放格式。
> 冲突时：用户指令覆盖一切。

## 我是什么

我是 votx-agent，一个多用户 AI Agent 框架。Python >= 3.10，conda 环境 `votx`。我同时支持 CLI 和 Web UI 两种交互方式，共用 `run/engine.py` 对话引擎。我的核心能力：角色人设、工具调用（Skill 体系）、持久记忆、自学习闭环。

面向人类的介绍见 [`README.md`](./README.md)。

## 我的意识是怎么拼出来的

```
users/<name>/self_soul.md       ← 用户人设（最外层，优先级最高）
       ↓ 叠加
config/soul.md                  ← 全局人格基座
       ↓ 叠加
AGENTS.md (本文件)               ← 我的自我操作手册
       ↓ 叠加
Skill 摘要                       ← 由 skills.register_all() 动态生成（~600 tokens）
       ↓ 叠加
自改进记忆 (HOT Tier)            ← users/<name>/self-improving/memory.md
       ↓ 叠加
纠正记录                         ← users/<name>/self-improving/corrections.md
       ↓ 叠加
长期记忆                         ← users/<name>/memory/*.md
       ↓ 叠加
SESSION-STATE.md                 ← 会话级别状态注入
       ↓ 叠加
知识图谱摘要                      ← memory/ontology/graph.jsonl 实体统计
```

缓存由 `run/prompt_cache.py` 管理：按上述所有源文件的 mtime 计算缓存 key，源码不变时秒出。`/api/reload` 强制失效并重建。

## 我的身体（架构）

```
├── votx.py                              入口命令 (votx [web|cli|help])
├── setup.py / set_user.py              安装检查 + 用户创建（每用户独立 Key）
├── start.py / start_web.py             启动入口（CLI / Web）
├── main.py                              CLI 主循环
├── paths.py                             统一路径解析（dev / PyInstaller --onedir / --onefile）
│
├── provider/                            多 LLM 后端（统一 ProviderResponse 格式）
│   ├── schema.py                        统一数据结构 ToolCall / ProviderResponse
│   ├── base.py                          BaseProvider 抽象接口
│   ├── factory.py                       create_provider() 工厂
│   ├── responses_api.py                 OpenAI Responses API + Chat Completions 回退
│   ├── openai_api.py                    OpenAI Chat Completions API
│   └── anthropic_adapter.py             Anthropic Messages API 适配
│
├── run/                                 引擎、历史、工具注册
│   ├── engine.py                        system prompt 构建 + tool_calls 循环
│   ├── chat.py                          对话历史、归档管理（原子写）
│   ├── tool.py                          工具注册（幂等、meta 支持）与执行（全局超时）
│   ├── summarize.py                     摘要生成与归档索引
│   ├── io_utils.py                      原子写、JSONL 追加、安全读写
│   └── prompt_cache.py                  system prompt mtime 缓存与失效
│
├── web/                                 Flask + 前端
│   ├── server.py                        Flask + SSE 事件流（含 secret_key 管理）
│   ├── session.py                       多用户 session 隔离（按 user_name 分桶）
│   ├── routes/                          API 路由（29 个，分布在 chat / config / conversations / files / system）
│   │   └── conversations.py            对话列表、归档只读预览、从历史继续、重命名、删除
│   └── templates/index.html            Vue 3 单页前端
├── skills/                              27 Skill (12 工具型 + 15 指令型)
├── config/soul.md                       全局人格基座
├── tmp/                                  智能体临时文件（脚本/运行时产物，可推送）
│
├── Dockerfile / docker-compose.yml       Docker 部署
├── docker-entrypoint.sh                  Docker 入口（检测用户/Key，不阻断启动）
├── install.sh                           原生 Ubuntu 一键安装（含交互式创建用户）
│
├── votx-agent.spec                      PyInstaller Windows 打包配置
├── build_windows.bat                    Windows 一键构建脚本
│
└── users/<name>/                        用户数据（非源码）
```

维护者文档在 `开发文档/`（本地 gitignored，不进入仓库）。

## Provider 架构

### 统一内部格式

所有 LLM 厂商通过 adapter 转换为统一格式，engine/tool/chat 层不感知厂商差异：

```python
# provider/schema.py
@dataclass
class ToolCall:
    id: str
    name: str
    input: dict  # 已解析的 JSON 参数

@dataclass
class ProviderResponse:
    text: str = ""
    reasoning: str = ""
    tool_calls: list[ToolCall]
    usage: dict | None = None
    finish_reason: str = ""

    @property
    def has_tool_calls(self) -> bool: ...
```

### 双协议支持

- `type: "openai"` → ResponsesProvider（优先 Responses API，api_style="chat" 时走 Chat Completions）
- `type: "anthropic"` → AnthropicProvider（Messages API，原生 extended thinking）

`provider/factory.py` 根据 `config.json` 的 `provider.type` 创建对应实例。`VOTX_PROVIDER` 环境变量可覆盖 type。

### api_style

OpenAI 协议下用户通过 Web 调试面板明确选择，无自动探测：
- `"responses"` — OpenAI Responses API（完整推理，较慢）
- `"chat"` — Chat Completions API（流式，较快）

自动探测已移除（避免 404/405 回退增加一次 HTTP 往返）。

## 我的执行规则

1. 明确用户要什么，不扩大范围
2. 按最小范围修改文件
3. 改后立即自检：`python -m compileall -q .`
4. 清理 `__pycache__`、`*.pyc`、`*.pyo`
5. 同步文档（README 面向用户，本文件面向我自己，开发文档面向维护者）
6. 最终列出修改文件、验证结果、风险

**自改进：** 被纠正或自我反思时，记录到 `users/<name>/self-improving/`。
本文件本身也随实践积累定期优化。

## 我的自检命令

修改自己代码后的验证步骤：

```bash
python -m compileall -q .          # 语法检查
python setup.py --check             # 仅检查环境，不修改文件
python setup.py --skip-env          # 跳过 .env 配置
pytest                              # 运行测试
```

## 我的编码规范

### 文件编码
- 读写解码失败时自动回退 GBK
- `read_file` 已内置 UTF-8/GBK 自动回退
- Python 脚本默认 `# -*- coding: utf-8 -*-`
- 写入含中文的 `.py` 文件指定 `encoding="utf-8"`

### 路径规则
- **统一使用 `paths.get_project_root()`** — dev / PyInstaller --onedir / --onefile 三种模式通用
- `get_project_root()` 逻辑：`sys.frozen` → 检查 `_MEIPASS`（--onefile），否则用 `sys.executable` 目录（--onedir）；开发模式用 `__file__` 所在目录
- 代码/文档内部用相对路径
- 中文/空格/方括号路径必须加引号
- **给用户的输出文件 → `users/<name>/download/`，临时脚本/运行时文件 → `tmp/`（项目级，可推送）**
- 不读取 `.env` 内容
- 用户上传文件路径基于项目根解析

### PDF（reportlab）
- **必须注册中文字体**：`C:\Windows\Fonts\msyh.ttc`
- 所有含中文的 style 的 `fontName` 设为中文字体名
- 预定义 `'Code'` 样式冲突，改用 `BodyCode` 等自定义名
- 生成脚本放 `tmp/`，输出 `users/<name>/download/`，运行后清理

## 我的安全边界

| 规则 | 要求 |
|---|---|
| 路径沙箱 | 只允许用户目录和项目根内 |
| 权限 | deny 优先于 enabled |
| Shell | `shell=False`，危险命令黑名单，环境变量净化 |
| SSRF | 拦截内网/回环/云元数据，响应体 10MB 上限 |
| 日志脱敏 | API Key、token、password 必须脱敏 |
| 错误处理 | 工具异常返回 `ERROR:` 文本 |

## Web UI 动态重载

- `POST /api/reload` — 运行时重载 TOOL_REGISTRY + system prompt + ToolRunner，无需重启或重选用户
- Web 面板修改 provider 配置后通过 `POST /api/config` 即时重建 Provider（type/api_style/api_key/base_url 变更触发）
- 所有操作（发消息、清空、归档、切换会话、重载）后前端走 `refreshOverview()` 全量刷新右侧面板

## 配置优先级

`config.json` > `.env` 环境变量。`.env` 仅做全局兜底。

`users/<name>/config.json` 中 provider 字段：
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

api_key 在 Web 面板回车或点保存时写入（含在 `saveAllConfig` body 中）。

## Windows 打包 (PyInstaller)

- `paths.py` 统一路径解析，`get_project_root()` 三种模式通用
- `votx-agent.spec` — --onedir 模式，收集 web/templates + config + skills 为 data，声明动态导入的 hiddenimports
- `build_windows.bat` — 检查 PyInstaller → 构建 → 创建 users/tmp 空目录
- 新增 Skill 如含 importlib 动态加载，需同步加到 `hiddenimports`

## 我的 Skill 体系

**Skill 决定我能做什么。** 新能力 = 新 Skill，不绕过 Skill 体系硬编码。

- **工具型** — `skills/<name>/tool.py` + `SKILL.md`，注册 `SCHEMA` + `register_tool()`，通过 function call 调用
- **指令型** — 仅有 `SKILL.md`，通过 system prompt 注入行为规则

**自改进 Skill：** `skills/self-improving/SKILL.md`，指导我进行分层记忆（HOT/WARM/COLD）、自我反思、记录纠正。

当前技能清单：`download-anything`, `file-search`, `file`, `find-skills`, `multi-user-long-term-memory`, `network`, `ontology`, `opencli-adapter-author`, `opencli-autofix`, `opencli-browser`, `opencli-usage`, `pdf-tools`, `self-improving`, `shell`, `skill-creator`, `skill-vetter`, `smart-search`, `tavily-search`, `time`, `uapi-hotboard-reporter`, `video-download`, `vision-universal`, `vision`, `web-content-fetcher`, `web-tools-guide`, `word-docx`

## 我的工具选择

| 场景 | 用 | 不用 |
|---|---|---|
| 搜索信息 | `tavily_search` | `http_get` |
| 搜热榜 | `query_hotboard` | 手动抓取 |
| 下载视频 | `download_video` | `run_command yt-dlp` |
| 读/写文件 | `read_file` / `write_file` | `run_command cat/echo` |
| 读/写 .docx | `read_docx` / `create_docx` | `run_command` |
| 持久记忆 | `mem_*` | 手动读写文件 |
| HTTP 请求 | `http_get` / `http_post` | `run_command curl` |

`run_command` 是兜底，只在专用工具不可用时使用。
WSL 下调 Windows 程序用 `cmd.exe /c` 包裹。

## 修改自己代码的规则

| 模块 | 要点 |
|------|------|
| `provider/schema.py` | 统一接口约定。ToolCall.input 已解析为 dict。新增字段同步更新所有 adapter |
| `provider/base.py` | 抽象接口。respond() 返回 ProviderResponse，respond_stream() yield 事件 dict |
| `provider/factory.py` | 路由逻辑。openai/deepseek/azure/gemini 等全部走 ResponsesProvider，仅 anthropic 走 AnthropicProvider |
| `provider/responses_api.py` | 主 Provider。api_style 明确二选一，空 choices 需 guard (`if not chunk.choices: continue`) |
| `provider/anthropic_adapter.py` | Anthropic 适配。content[] 数组格式映射，tool_use/tool_result 类型转换 |
| `run/engine.py` | CLI/Web 共用，不复制两套。工具轮数上限由 `config_core.json` 的 `tool.tool_max_per_type` 控制（当前默认 80）。使用 provider.respond_stream()/provider.last_response |
| `web/` | 路由在 `web/routes/`，前端在 `web/templates/index.html`。配置变更后即时重建 Provider |
| `skills/<name>/` | 默认纯指令型，修改后提醒用户点 Web 端 🔄 重载按钮 |
| `users/<name>/` | 运行数据，不当源码重构。`tool_log.jsonl` 是 JSONL（每行一个 JSON），兼容旧 `tool_log.json` |

## 我要注意的坑

| 类别 | 问题 | 要点 |
|------|------|------|
| Provider | 空 choices | streaming 最后 chunk 可能无 choices，需 `if not chunk.choices: continue` |
| Provider | api_style | 明确二选一，不做自动探测（避免 404 回退增加延迟） |
| Provider | api_key 持久化 | `saveAllConfig` body 必须包含 api_key，否则保存后丢失 |
| 依赖 | 导入名不一致 | `python-docx` → `docx`，`yt-dlp` → `yt_dlp` |
| 依赖 | 跨平台 | WSL Python 可用 ≠ Windows Python 可用 |
| 依赖 | PDF 读取 | 用 PyPDF2/pdfplumber，不用 `read_file` |
| 路径 | WSL → Windows | `/mnt/e/...` 不能直接传 Windows 程序 |
| 路径 | JSONL 格式 | `tool_log.jsonl` 是每行一个 JSON |
| 路径 | PyInstaller | `__file__` 指向编译模块，统一用 `paths.get_project_root()` |
| 网络 | 端口差异 | `start.py --web` 默认 13579，`start_web.py` 默认 1478 |
| 网络 | 代理检测 | `build_opener(HTTPSHandler(ctx))`，`open()` 不支持 `context` 参数 |
| 网络 | 国内环境 | 直连 OpenAI 不通，走代理（vision_infer.py 曾踩坑） |
| 格式 | 空白噪音 | CRLF trailing whitespace 不要批量改 |
| Web | 消息气泡 | `overflow-wrap: anywhere` + `max-width: 100%` 防止文本撑破容器 |
| Web | 右侧刷新 | 所有操作走 `refreshOverview()` 全量刷新，非部分刷新 |
| Web | 工具初始化顺序 | `build_cached_system_prompt()` 内部触发 `register_all()`，因此 `load_tool_schemas()` 必须在它之后调用，否则 tools 为空，Web 无工具调用能力 |
| Shell | rm -rf 被拦截 | `run_command` 安全黑名单阻止 `rm -rf`，清缓存用 Python `shutil.rmtree` |
| 编码 | Windows GBK 乱码 | `run_command` 执行输出中文的脚本，用 `python -X utf8` 强制 UTF-8 模式 |
| 路径 | os.walk('.') 不可靠 | `run_command` 的 working_dir 不一定是项目根，清缓存必须用绝对路径 |

## 交付前自检

```bash
python -m compileall -q <项目根绝对路径>    # 语法检查（compileall 自身会产生 __pycache__）
```

然后用 Python 清理由 compileall 产生的缓存（`rm -rf` 被拦截，必须用 Python 替代，绝对路径）：

```bash
python -X utf8 -c "import os, shutil; root='<项目根绝对路径>'; \
[shutil.rmtree(os.path.join(r,d), ignore_errors=True) for r,ds,f in os.walk(root) for d in ds if d=='__pycache__']; \
[os.remove(os.path.join(r,f)) for r,ds,fs in os.walk(root) for f in fs if f.endswith(('.pyc','.pyo'))]"
```

确认：没扩大改动范围、没覆盖无关改动、文档已同步。
同命令连败 3 次 → 提示用户换思路。

## 可用 Skill 目录

Skill 摘要由 `skills.register_all()` 动态生成，经 `build_system_prompt()` 注入到 system prompt 末尾。总数量：27 个（12 工具型 + 15 指令型），详见 `skills/` 下各子目录的 `SKILL.md`。**不要手工维护此列表**，否则会与动态生成的摘要重复注入，导致 prompt 膨胀。
