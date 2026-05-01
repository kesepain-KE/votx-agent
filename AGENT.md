# AGENT.md — kesepain-Agent 项目指南

## 这是什么

多用户 AI Agent 框架。Python 项目，调用 OpenAI 兼容 API，实现 **角色扮演 + 工具调用 + 对话持久化** 的完整 Agent 闭环。

- **入口**: `start.py` → 选择用户 → `main.py` 主循环
- **LLM**: DeepSeek API (OpenAI 兼容)，可替换任意 provider
- **平台**: Windows / WSL2 双环境

## 目录结构

```
kesepain-Agent/
├── start.py                  # 入口：扫描 users/ → 选择 → subprocess 启动 main.py
├── main.py                   # 核心：对话循环 + 命令分发 + Token 统计
│
├── config/
│   ├── config_core.json      # 全局配置（历史/工具限制）
│   └── soul.md               # 全局人设（可选，HTML注释占位则跳过）
│
├── provider/
│   └── openai_api.py         # DeepSeekProvider（流式/重试/.env加载）
│
├── run/
│   ├── chat.py               # ChatManager：消息管理/历史CRUD/归档/清除
│   └── tool.py               # ToolRunner：注册表/权限校验/限流/日志
│
├── skills/                   # 【agentskills.io 标准骨架】
│   ├── __init__.py           # register_all()：扫描 SKILL.md → 加载 tool.py
│   ├── _common/              # 公共模块（err/truncate/safe_path/log_tool_call）
│   ├── file/                 # 文件操作（read/write/list/delete + 路径沙箱）
│   ├── network/              # HTTP 请求（http_get/http_post + SSRF防护）
│   ├── shell/                # 系统命令（run_command + 危险参数拦截）
│   ├── time/                 # 时间工具（get_time/sleep）
│   ├── uapi-hotboard-reporter/  # 热榜查询（需 UAPI_API_KEY）
│   ├── video-download/       # 视频下载（yt-dlp 封装）
│   ├── word-docx/            # Word 文档（python-docx 封装）
│   └── tavily-search/        # 网络搜索（需 TAVILY_API_KEY）
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
start.py → 扫描users/ → 用户选择 → KESEPAIN_USER_DIR → main.py (子进程)
main.py → 加载配置 + .env → ChatManager → Provider → register_all() → 对话循环
```

### 对话循环内层

```
while tool_round < MAX_TOOL_ROUNDS(20):
    messages = chat.build_messages()     # system + history
    response = provider.chat(messages, tools)
    if has_tool_calls(response):
        执行 → 记录token → 继续
    else:
        输出 → 统计token → break
```

### 命令分发 (`/` 开头走分发，否则走 LLM)

| 命令 | 行为 |
|------|------|
| `/exit` `/quit` `/q` | 退出 + 自动保存 |
| `/clear` | 归档当前历史 → 清空 |
| `/history` `/stats` | 显示消息数/大小/归档数 |
| `/archive` | 仅归档不清空 |
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

遵循 **agentskills.io** 标准：

```
skills/<skill-name>/
├── SKILL.md      # 必需：YAML frontmatter(name+description) + Markdown 指引
├── tool.py       # 必需：含 register()，注册 OpenAI function schema + handler
├── scripts/      # 可选：内部脚本（不被自动发现）
└── references/   # 可选：参考文档
```

**SKILL.md 最小模板**:
```markdown
---
name: my-skill
description: 当用户需要 xxx 时使用
---

# 使用指引
...
```

**tool.py 最小模板**:
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
在 `skills/` 下创建目录（含 SKILL.md + tool.py），重启自动生效。

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
- **路径优先级**: 相对路径 > 绝对路径 > 容器/WSL 路径。引用文件优先用相对路径（如 `users/kesepain/self_soul.md`），绝对路径仅当用户明确给出时才用，WSL 路径（`/mnt/e/...`）只在确认是 WSL 环境时使用

## 启动

```bash
# 安装依赖
pip install openai requests yt-dlp tavily-python python-docx

# 设置 Key（任选一种）
echo "DEEPSEEK_API_KEY=sk-your-key" > .env

# 启动
python start.py
```

## 注意事项

- Windows 中文环境 subprocess 编码问题已修复（`encoding="utf-8", errors="replace"`）
- 热榜查询需额外配置 `UAPI_API_KEY`
- 网络搜索需配置 `TAVILY_API_KEY`：`pip install tavily-python`
- 视频下载依赖 yt-dlp：`pip install yt-dlp`
- Word 文档依赖 python-docx：`pip install python-docx`
- 历史文件损坏时自动重命名为 `.corrupt` 并重置
- 归档文件名精确到微秒避免冲突
- WSL2 下开发，Windows 下运行——两环境依赖可能不同
