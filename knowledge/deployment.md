# 部署与运行

本页说明 VOTX Agent 的普通 Python 启动、环境变量、局域网访问、消息配置和 Windows 打包边界。

## 推荐目录

```text
<project-root>/
  .env
  config/
  message/
  plugins/
  skills/
  users/
  web/
```

用户数据、下载文件、历史文件和知识库都在 `users/<name>/` 下。外部消息的本地配置建议使用 `message/config.local.json`。

## 首次运行

```text
python setup.py
python set_user.py add
python start_web.py
```

默认访问地址：

```text
http://localhost:1478
```

CLI 运行：

```text
python start.py
python start.py --user <用户名> --prompt "<内容>" --once
```

## Web 参数

```text
python start_web.py --port=8080
python start_web.py --host=0.0.0.0 --port=1478
```

也可以在 `.env` 中设置：

```env
PORT=1478
VOTX_HOST=0.0.0.0
VOTX_SESSION_COOKIE_NAME=votx_agent_session
```

同一 IP 下运行多个 Web 项目时，给每个项目设置不同的 `VOTX_SESSION_COOKIE_NAME`，避免浏览器 Cookie 名冲突。

## 环境变量

推荐优先写入 `users/<name>/config.json`；`.env` 只作为兜底。

常用变量：

```env
DEEPSEEK_API_KEY=sk-your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=sk-ant-your-key
ANTHROPIC_BASE_URL=https://api.anthropic.com
KEMO_API_KEY=sk-kemo-your-key
KEMO_BASE_URL=http://127.0.0.1:8741/v1
TAVILY_API_KEY=your-tavily-key
VOTX_MESSAGE_CONFIG=message/config.local.json
```

## 外部消息配置

配置文件优先级：

```text
VOTX_MESSAGE_CONFIG
message/config.local.json
message/config.json
```

建议复制模板后修改：

```text
message/config.example.json -> message/config.local.json
```

NapCat 正向 WebSocket 示例地址：

```text
ws://127.0.0.1:3001
```

附件保存到：

```text
users/<name>/history/file/
```

主动推送队列默认在：

```text
message/push_queue/
```

## Windows 打包

```cmd
build_windows.bat
```

产物：

```text
dist\votx-agent-windows.zip
```

打包包含：

```text
agents/ config/ cron/ message/ plugins/ provider/ run/
skills/ web/ users/ tmp/ knowledge/
paths.py AGENTS.md set_user.py setup.py version.json .env.example
```

打包排除：

```text
tests/ 使用手册-AI/ tools/ web/node_modules/
message/config.json message/config.local.json message/identity/identity_map.json
message/push_queue/ .env .session_secret *.pyc *.pyo __pycache__/
```

## 源码更新

当前项目不包含自动更新脚本。手动更新前先备份：

```text
users/
skills/
.env
message/config.local.json
message/identity/identity_map.json
message/push_queue/
```

更新后运行：

```text
python setup.py
python start_web.py
```

启动路径会无损补齐老用户目录骨架，不覆盖已有 `config.json`、`self_soul.md` 或用户文件。

## 常见问题

- Web 无法访问：确认 `PORT`、`VOTX_HOST` 和本机防火墙规则。
- 外部消息不生效：确认 `message/config.local.json` 已启用平台并绑定用户。
- 附件找不到：检查 `users/<name>/history/file/`。
- 多项目登录态互相影响：修改 `VOTX_SESSION_COOKIE_NAME`。
