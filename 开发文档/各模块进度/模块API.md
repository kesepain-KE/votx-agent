# 模块 API

最后更新：2026-05-04

## Provider — `provider/openai_api.py`

`DeepSeekProvider(user_config, core_config=None)`:

- API Key: 用户配置 → `DEEPSEEK_API_KEY` → `OPENAI_API_KEY`
- base_url: 用户配置 → `DEEPSEEK_BASE_URL` → `https://api.deepseek.com`
- 默认模型: `deepseek-v4-flash`
- 支持 think / stream / timeout
- `last_usage` 保存最近 Token 用量
- `chat()` — 非流式，自动提取 `reasoning_content`
- `chat_stream()` — 逐块 yield `thinking_chunk` / `text_chunk`，`_stream_result` 含 `reasoning_content`

## 对话引擎 — `run/engine.py`

- `build_system_prompt(root, user_dir)`: self_soul.md → soul.md → AGENTS.md → Skill 摘要 → 持久记忆 → .learnings
- `run_chat_turn(chat, tool_runner, provider, tools)`: 事件生成器
- `MAX_TOOL_ROUNDS = 20`
- tool_calls 路径已修复: `reasoning_content` 从 response 提取后传入 `chat.add_tool_call_message()`，确保 DeepSeek thinking 模式下一轮请求不报错

事件类型: `thinking_chunk` `thinking_done` `thinking` `text_chunk` `text_done` `text` `tool_call` `usage` `error` `deadlock_warning` `max_rounds`

## 历史 — `run/chat.py`

`ChatManager`:
- 消息追加 (user/assistant/tool)
- `add_tool_call_message()` 支持 `reasoning_content` 参数
- 历史读取/保存/裁剪
- tool_calls 断链修复（前向+后向检查）
- 中断时补齐未完成 tool 调用
- 归档

## 工具 — `run/tool.py`

- `register_tool(schema, handler)` — 注册
- `load_tool_schemas()` — 返回 OpenAI tools 格式
- `ToolRunner.execute()` — 权限 → 限流 → 解析 → 执行 → 日志
- deny 优先于 enabled
- 工具日志写入 `tool_log.json` (每行一个 JSON)

## 当前工具清单 (25)

```
create_docx       delete_file       download_video    get_time
http_get          http_post         list_dir          log_error
log_feature_request  log_learning   mem_get_entity    mem_get_lessons
mem_learn         mem_recall        mem_remember      mem_stats
mem_track_entity  query_hotboard    read_docx         read_file
read_learnings    run_command       sleep             tavily_search
write_file
```

## Web API — 22 端点

| 路由 | 模块 | 说明 |
|---|---|---|
| `GET /` | `routes/chat.py` | Web UI (Vue 3) |
| `GET /api/users` | `chat.py` | 用户列表 |
| `POST /api/select-user` | `chat.py` | 初始化会话 |
| `GET /api/session` | `chat.py` | 会话状态 |
| `POST /api/chat` | `chat.py` | SSE 流式聊天 |
| `POST /api/command` | `chat.py` | 非流式命令 |
| `POST /api/disconnect` | `chat.py` | 保存并断开 |
| `POST /api/upload` | `files.py` | 上传文件 |
| `GET /api/files` | `files.py` | 文件列表 |
| `GET /api/files/download/<name>` | `files.py` | 下载文件 |
| `GET /api/files/view/<name>` | `files.py` | 预览文件 |
| `DELETE /api/files/<name>` | `files.py` | 删除单文件 |
| `DELETE /api/files` | `files.py` | 批量删除 |
| `GET /api/conversations` | `conversations.py` | 对话列表 |
| `POST /api/load-conversation` | `conversations.py` | 加载归档 |
| `DELETE /api/conversations/<id>` | `conversations.py` | 删除归档 |
| `POST /api/conversations/<id>/rename` | `conversations.py` | 重命名归档 |
| `DELETE /api/conversations` | `conversations.py` | 删除全部归档 |
| `GET /api/config` | `config.py` | 读取配置 |
| `POST /api/config` | `config.py` | 保存配置 |
| `GET /api/messages` | `system.py` | 当前消息 |
| `GET /api/system-prompt` | `system.py` | system prompt 分段（每次重建） |
| `GET /api/export-markdown` | `system.py` | 导出 Markdown |
| `GET /api/stats` | `system.py` | 统计 |
| `GET /api/tool-logs` | `system.py` | 工具日志 |

## 命令注册

CLI: `/exit` `/quit` `/q` `/clear` `/retry` `/history` `/stats` `/archive` `/summarize` `/summary` `/总结` `/help`

Web 注册命令: `/clear` `/history` `/retry` `/help`（`/exit` 仅 CLI 可用；`/archive` `/summarize` 通过保存按钮触发，不在快捷芯片中）

命令分发: `_dispatch(cmd)` → dict (Web) / True|False|None (CLI)
