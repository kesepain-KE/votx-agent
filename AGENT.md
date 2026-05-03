# AGENTS.md

给编码 Agent 执行任务的操作手册。不面向人类用户。

> 格式: [agents.md](https://agents.md)。冲突时: 本文件优先，用户指令覆盖一切。

Python >= 3.10，conda 环境 `votx`。

## 执行优先级

1. 明确用户要改什么，不扩大范围
2. 先查看 `git status`，避免覆盖未提交改动
3. 按最小范围修改文件
4. 改后运行 `python -m compileall -q .`
5. 清理 `__pycache__`、`*.pyc`、`*.pyo`
6. 同步文档（README 面向用户，本文件面向 Agent，开发文档面向维护者）
7. 最终列出修改文件、验证结果、风险

不要擅自提交或推送。

## 路径规则

- 代码/文档内部用相对路径
- 中文/空格/方括号路径必须加引号
- 不读取 `.env` 内容，只检查是否存在
- 用户上传文件的路径是相对路径，基于项目根解析
- **给用户的输出文件 → `users/<name>/download/`，临时脚本 → `tmp/`，不要放到桌面或 E:\下载**

## 架构速览

```
├── setup.py                   环境安装
├── start.py / start_web.py   入口
├── main.py                    CLI 主循环
├── provider/openai_api.py     LLM Provider
├── run/
│   ├── engine.py              对话引擎 + system prompt 构建
│   ├── chat.py                历史/归档/tool_calls 修复
│   ├── tool.py                工具注册/权限/限流
│   └── summarize.py           摘要
├── web/
│   ├── server.py              Flask app 创建
│   ├── session.py             会话状态
│   ├── commands.py            斜杠命令
│   ├── routes/                API 端点 (chat/files/conversations/system/config)
│   └── templates/index.html   前端
├── skills/                    18 Skill (10 工具型 + 8 指令型)
├── config/soul.md             运行纪律
├── users/<name>/              用户数据（非源码，谨慎改动）
└── 开发文档/                  完整开发文档
```

## Skill 体系

**Skill 决定 Agent 能做什么。** 所有工具和指令型能力都来自 `skills/` 目录，没有 Skill 就没有对应能力。

- **工具型 Skill** — `skills/<name>/tool.py` + `SKILL.md`，定义 `SCHEMA` 并通过 `register_tool()` 注册
- **指令型 Skill** — 仅有 `SKILL.md`，通过 system prompt 注入行为规则

新增能力 = 新增 Skill，不要绕过 Skill 体系直接硬编码工具逻辑。

## 工具调用决策

| 场景 | 用 | 不用 |
|---|---|---|
| 搜索信息 | `tavily_search` | http_get |
| 搜热榜 | `query_hotboard` | 手动抓取 |
| 下载视频 | `download_video` | run_command yt-dlp |
| 读/写文件 | `read_file`/`write_file` | run_command cat/echo |
| 读 .docx | `read_docx` | run_command |
| 创建 .docx | `create_docx` | run_command |
| 持久记忆 | `mem_*` | 手动读写文件 |
| HTTP 请求 | `http_get`/`http_post` | run_command curl |

`run_command` 是兜底手段，只在专用工具无法完成时使用。WSL 下调 Windows 程序用 `cmd.exe /c` 包裹。

同命令连败 3 次 → 自动提示用户换思路。

## 修改规则

### 对话循环 → `run/engine.py`
CLI/Web 共用，不要复制两套。保持 `run_chat_turn()` 事件结构兼容。`MAX_TOOL_ROUNDS = 20`。

### Provider → `provider/openai_api.py`
不输出 API Key。保留 `last_usage`。网络失败返回可诊断错误。

### Web → `web/` 目录
后端路由在 `web/routes/`，前端在 `web/templates/index.html`。新增 route 后同步 `web/server.py` 导入和开发文档。

### Skill → `skills/<name>/`
- 默认做纯指令型 (SKILL.md)，不加 tool.py
- name = 目录名，小写字母/数字/连字符
- 显示指定安装到项目 `skills/`，不装到 `users/<name>/skills/`
- 修改后提醒用户重启 Agent

### 用户数据 → `users/<name>/`
运行数据，不要当源码重构。`tool_log.jsonl` 是 JSONL（每行一个 JSON），不是单个 JSON 文档。`/clear` 不清除持久记忆。

## 安全边界

| 规则 | 要求 |
|---|---|
| 路径沙箱 | 只允许用户目录和项目根内 |
| 权限 | deny 优先于 enabled |
| Shell | `shell=False`，危险命令黑名单，环境变量净化，工作目录校验，输出截断 |
| SSRF | 拦截内网/回环/云元数据，重定向校验，响应体 10MB 上限 |
| 日志脱敏 | API Key、token、password 等必须脱敏 |
| 错误处理 | 工具异常返回 `ERROR:` 文本，不抛异常 |

## 编码与字体规则

### 文件编码
- 读写文件时如遇解码失败，自动回退 GBK 编码
- `read_file` 已内置 UTF-8/GBK 自动回退
- Python 脚本默认用 `# -*- coding: utf-8 -*-` 声明
- 写入含中文内容的 `.py` 文件须指定 `encoding="utf-8"`

### PDF 生成（reportlab）
- **必须注册中文字体** — Windows 下优先用 `C:\Windows\Fonts\msyh.ttc`
  ```python
  from reportlab.pdfbase import pdfmetrics
  from reportlab.pdfbase.ttfonts import TTFont
  pdfmetrics.registerFont(TTFont("CNFont", "C:\\Windows\\Fonts\\msyh.ttc"))
  ```
- 所有含中文的 style 的 `fontName` 设为中文字体名
- 预定义 `'Code'` 样式冲突，改用 `BodyCode` 等自定义名
- 生成脚本放 `tmp/`，输出文件放 `users/<name>/download/`，运行后清临时脚本

## 常见坑

- `python-docx` 导入名是 `docx`，`yt-dlp` 导入名是 `yt_dlp`
- WSL Python 依赖可用 ≠ Windows Python 可用
- PDF 用 PyPDF2/pdfplumber 读，不要用 `read_file`
- 临时文件放到 `tmp/` 目录（已 gitignore），不要污染项目根
- WSL 路径 `/mnt/e/...` 不能直接传给 Windows 程序
- `tool_log.jsonl` 是 JSONL
- `start.py --web` 默认端口 13579，`start_web.py` 默认 1478
- CRLF trailing whitespace 噪音不要批量改
- 网络工具失败时，先问用户代理端口，不要盲目重试同一端口
- 国内网络环境直连 OpenAI 大概率不通，走代理；百度可直连不代表 API 可直连
- **代理检测注意** — Python 的 `urllib.request.build_opener` 返回的 `OpenerDirector.open()` 不支持 `context` 关键字参数。需要在 `build_opener` 时传入 `HTTPSHandler(context=ctx)`，而非在 `open()` 时传 `context`。vision_infer.py 曾踩过这个坑（2026-05-03 修复）。

## 交付前

```bash
python -m compileall -q .          # 语法检查
git diff --check                     # 空白检查
find . -name __pycache__ -exec rm -rf {} + 2>/dev/null  # 清理缓存
```

确认：没扩大改动范围、没覆盖无关改动、文档已同步。

---

项目完整信息（Web API 清单、启动流程、配置说明等）见 `开发文档/`。
