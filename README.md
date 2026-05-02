# kesepain-Agent

多用户 AI Agent 框架。OpenAI 兼容接口，支持角色扮演、工具调用、对话持久化，内置多层安全机制。提供 CLI 和 Web UI 两种交互方式。

## 快速开始

```bash
python 快速配置.py         # 克隆后首次运行——一键安装依赖、配置 Key、创建用户
python start.py            # CLI 模式（日常使用）
python start.py --web       # Web UI 模式（默认端口 13579）
python start_web.py        # Web UI 专用入口（默认端口 1478，冲突自动轮询）
```

或手动设置：

```bash
pip install openai requests yt-dlp tavily-python python-docx pyyaml flask
cp .env.example .env   # 编辑填入 DEEPSEEK_API_KEY
python start.py
```

## 能力

**18 个 Skill，25 个工具**（[agentskills.io](https://agentskills.io/specification) 规范，放入即自动发现）

| Skill | 工具 | 说明 |
|-------|------|------|
| file | `read_file` `write_file` `list_dir` `delete_file` | 文件读写，路径沙箱保护 |
| network | `http_get` `http_post` | HTTP 请求，SSRF 防护 |
| shell | `run_command` | 系统命令，shell=False + 参数黑名单 |
| time | `get_time` `sleep` | 时间查询与延时 |
| word-docx | `create_docx` `read_docx` | Word 文档创建与读取 |
| video-download | `download_video` | yt-dlp 多平台视频下载 |
| uapi-hotboard-reporter | `query_hotboard` | 全网热榜查询（知乎/微博/B站等） |
| tavily-search | `tavily_search` | AI 搜索引擎 |
| self-improving-agent | `log_learning` `log_error` `log_feature_request` `read_learnings` | 自主学习：记录错误/纠正/功能请求 |
| agent-memory | `mem_remember` `mem_recall` `mem_learn` `mem_get_lessons` `mem_track_entity` `mem_get_entity` `mem_stats` | 持久记忆：记住/回忆/学习/实体追踪 |
| vision | —（纯指令） | 图像识别（GPT-4o-mini，通过 run_command 调用脚本） |
| download-anything | —（纯指令） | 下载任意数字资源（视频/电子书/音乐/软件/网盘） |
| find-skills | —（纯指令） | 发现并安装 Agent Skills（npx skills CLI） |
| pdf-tools | —（纯指令） | PDF 操作（提取/合并/拆分/旋转/编辑） |
| skill-creator | —（纯指令） | 创建 agentskills.io 规范的新 Skill |
| skill-vetter | —（纯指令） | Skill 质量审查（规范/安全/可用性） |
| web-content-fetcher | —（纯指令） | 网页内容获取（r.jina.ai 等服务） |
| web-tools-guide | —（纯指令） | Web 开发工具使用指南 |

## 对话命令

| 命令 | 功能 |
|------|------|
| `/exit` `/quit` `/q` | 退出（自动保存） |
| `/clear` | 清除对话历史 + 工具日志 |
| `/history` `/stats` | 消息数 / 工具日志条数 / 归档数 |
| `/archive` | 手动归档（不清空） |
| `/retry` | 移除上一条 AI 回复，重新生成 |
| `/summarize` `/总结` | 生成当前对话摘要 |
| `/help` | 显示帮助 |

## 项目结构

```
├── start.py              # CLI 入口：用户选择 → 启动 main.py
├── start_web.py          # Web UI 入口：端口 1478，冲突自动轮询
├── main.py               # CLI 核心：命令分发 + 对话循环（委托 run/engine.py）
├── config/
│   ├── config_core.json   # 全局配置（历史/限流）
│   └── soul.md            # 运行纪律规则（注入 system prompt）
├── provider/
│   └── openai_api.py      # DeepSeekProvider（流式/重试/Token统计/SSL修复）
├── run/
│   ├── engine.py           # 【共用引擎】build_system_prompt() + run_chat_turn() generator
│   ├── chat.py             # ChatManager：消息管理/历史归档/清除
│   └── tool.py             # ToolRunner：注册/权限校验/限流/日志
├── web/                    # 【Web UI】Flask + SSE 流式聊天
│   ├── __init__.py
│   ├── server.py           # Flask 后端：20 个 /api 端点 + SSE 事件流
│   └── templates/
│       └── index.html      # 单页聊天界面（高级黑/白 glassmorphism 主题）
├── skills/                 # agentskills.io 标准骨架（18 Skill）
│   ├── _common/            # 公共模块（err/truncate/safe_path/log）
│   ├── file/  network/  shell/  time/  video-download/
│   ├── word-docx/  tavily-search/  uapi-hotboard-reporter/
│   ├── self-improving-agent/  agent-memory/
│   ├── vision/  download-anything/  find-skills/  pdf-tools/
│   ├── skill-creator/  skill-vetter/  web-content-fetcher/  web-tools-guide/
├── AGENT.md               # 项目能力指南（注入 system prompt）
├── users/
│   └── kesepain/           # 用户目录（self_soul.md + config.json + history/）
└── requirements.txt
```

## 调用链

```
CLI: start.py → 扫描 users/ → 选择用户 → main.py → engine
Web: start.py --web / start_web.py → Flask → 浏览器选择用户 → engine
engine: self_soul.md + soul.md + AGENT.md + Skill 摘要 + 持久记忆 → system prompt
        → register_all() → 25 tools → run_chat_turn() generator → SSE/CLI 输出
        → tool_calls 链自动修复 → 同命令连败 3 次提示 → Token 累计
```

## 安全机制

| 机制 | 实现 |
|------|------|
| 路径沙箱 | `safe_path()` — 仅允许用户目录 + 项目根 |
| 权限系统 | deny 黑名单 > enabled 用户级 > enabled 全局级 |
| 工具限流 | 全局 100 次/单工具 50 次/往返 20 轮 |
| SSRF 防护 | 拦截内网地址 + DNS 二次校验 |
| Shell 安全 | `shell=False` + `shlex.split` + 危险参数黑名单 |
| 输出截断 | 8000 字符自动截断标注 |
| 日志脱敏 | 过滤 api_key/token/secret/password 等 8 类敏感字段 |
| 错误标准化 | 所有异常统一 `ERROR:` 前缀 |

## 配置

```bash
# .env（可选 Key）
DEEPSEEK_API_KEY=sk-xxx       # 必填
OPENAI_API_KEY=sk-xxx         # vision Skill 图像识别
UAPI_API_KEY=uapi-xxx         # 热榜查询
TAVILY_API_KEY=tvly-xxx       # 网络搜索
```

权限控制：`users/<name>/config.json` → `tool.deny` / `tool.enabled`

## 添加新用户

```bash
cp -r users/kesepain users/<name>
# 编辑 config.json → 配置 API / 模型 / 工具权限
# 编辑 self_soul.md → 自定义角色人设
```

## 添加新 Skill

在 `skills/` 下创建目录即可，无需修改任何注册代码：

```
# 工具型 Skill
skills/my-skill/
├── SKILL.md   # name + description + 使用指引
└── tool.py    # register() 注册 schema + handler

# 纯指令 Skill（同样生效，无 tool.py）
skills/my-skill/
└── SKILL.md   # 摘要自动注入 system prompt，正文按需读取
```
