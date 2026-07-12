# 部署与运行

更新时间：2026-07-12

## 首次运行

需要 Python 3.10+、Git；构建 Web 前端需要 Node.js/npm。

```text
python setup.py
python set_user.py add
python start_web.py
```

默认访问 `http://localhost:1478`。

CLI：

```text
python start.py
python start.py --user <用户名> --prompt "<内容>" --once
```

## 配置职责

| 文件 | 用途 |
|---|---|
| `config/config_core.json` | 全局默认值 |
| `users/<name>/config.json` | 用户 Provider、历史、工具、技能和任务计划配置 |
| `.env` | 启动级参数与兼容兜底 |
| `message/config.local.json` | 外部消息私有配置 |

常规模型配置应写入用户 `config.json`。`.env.example` 当前保留的变量类别：

- `KEMO_API_KEY`、`KEMO_BASE_URL`：Provider 兜底。
- `TAVILY_API_KEY`、`TAVILY_RESULT_TRUNCATE`：Tavily。
- `PORT`、`VOTX_HOST`、`VOTX_SESSION_COOKIE_NAME`：Web 启动和 Cookie。
- `VOTX_SECRET_KEY`、`VOTX_ACCESS_TOKEN`：Web 会话/API 认证。
- `VOTX_SKIP_VERSION_CHECK`、`VOTX_VERSION_URL`：启动版本检查。
- `VOTX_MESSAGE_CONFIG`：消息配置路径。
- `HTTP_PROXY`、`HTTPS_PROXY`、`SSL_CERT_FILE`、`HTTP_VERIFY_SSL`：HTTP 兼容设置。
- `HTTP_TIMEOUT`、`DOWNLOAD_TIMEOUT`、`DOWNLOAD_VIDEO_TIMEOUT`：兼容默认值；工具最终优先服从 JSON 的 `tool.tool_timeout`。

不再使用旧文件、下载和网络范围环境变量。

## Web 参数

```text
python start_web.py --port=8080
python start_web.py --host=0.0.0.0 --port=1478
```

或：

```env
PORT=1478
VOTX_HOST=0.0.0.0
VOTX_SESSION_COOKIE_NAME=votx_agent_session
```

同一 IP 运行多个实例时使用不同 Cookie 名。

## 外部消息

配置优先级：

```text
VOTX_MESSAGE_CONFIG
message/config.local.json
message/config.json
```

复制 `message/config.example.json` 为 `message/config.local.json` 后修改。OneBot/NapCat 使用正向 WebSocket，Telegram 使用长轮询。

- 附件：`users/<name>/history/file/`
- 推送队列：`message/push_queue/`

## Windows 打包

```cmd
build_windows.bat
```

输出：`dist\votx-agent-windows.zip`。实际包含/排除规则以 `build_windows.bat` 和 `votx-agent.spec` 为准；`tests/` 已从源码移除，`使用手册-AI/` 只保留文档入口且不属于运行依赖。

## 更新

```text
python update.py --check
python update.py --dry-run
python update.py --yes
```

更新前备份：

```text
users/
skills/
.env
message/config.local.json
message/identity/
message/push_queue/
```

启动流程会补齐用户目录骨架，不应覆盖已有 `config.json`、`self_soul.md` 和用户文件。

## 常见问题

- Web 无法访问：检查 host、port、防火墙和端口占用。
- 外部消息不生效：检查平台开关、连接地址和 `bound_users`。
- 附件找不到：检查 `users/<name>/history/file/`。
- 登录态互相覆盖：更换 `VOTX_SESSION_COOKIE_NAME`。
- 多模态不可用：检查用户 Provider 能力和专用模型配置。
