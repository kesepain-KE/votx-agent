# votx-agent

多用户 AI Agent 框架。OpenAI 兼容接口，支持角色扮演、工具调用、对话持久化。

## 快速开始

```bash
pip install openai requests yt-dlp tavily-python python-docx
echo "DEEPSEEK_API_KEY=sk-your-key" > .env
python start.py
```

## 能力

| Skill | 工具 |
|-------|------|
| file | `read_file` `write_file` `list_dir` `delete_file` |
| network | `http_get` `http_post` |
| shell | `run_command` |
| time | `get_time` `sleep` |
| word-docx | `create_docx` `read_docx` |
| video-download | `download_video` |
| uapi-hotboard-reporter | `query_hotboard` |
| tavily-search | `tavily_search` |

## 命令

| 命令 | 功能 |
|------|------|
| `/exit` `/quit` | 退出 |
| `/clear` | 清除对话历史 |
| `/history` | 查看状态 |
| `/archive` | 归档历史 |
| `/help` | 帮助 |

## 项目结构

```
├── start.py         # 入口
├── main.py          # 核心循环
├── config/          # 全局配置 + 纪律规则
├── provider/        # LLM 调用封装
├── run/             # 对话管理 + 工具执行
├── skills/          # 8 个 Skill，14 个工具（agentskills.io 规范）
├── users/           # 用户目录（人设 + 历史）
└── 开发文档/        # 完整中文开发文档
```

## 安全

路径沙箱 / 权限系统 / 工具限流 / SSRF 防护 / 参数黑名单 / 敏感信息脱敏

## 添加用户

```bash
cp -r users/kesepain users/<新用户名>
# 编辑 config.json → 修改 provider 配置
# 编辑 self_soul.md → 自定义角色人设
```
