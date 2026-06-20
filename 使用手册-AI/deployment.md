# 部署与运行

本页说明 VOTX Agent 的普通 Python 启动、环境变量、局域网访问、消息配置和 Windows 打包边界。

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

## 局域网访问

```text
python start_web.py --host=0.0.0.0 --port=1478
```

或在 `.env` 中设置：

```env
PORT=1478
VOTX_HOST=0.0.0.0
VOTX_SESSION_COOKIE_NAME=votx_agent_session
```

同一 IP 下运行多个 Web 项目时，为每个项目设置不同的 `VOTX_SESSION_COOKIE_NAME`。

## 环境变量

推荐优先写入 `users/<name>/config.json`；`.env` 只作为兜底。

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

## 源码更新

### 自动更新（推荐）

```bash
python update.py --check      # 检查版本
python update.py --yes        # 全自动更新
python update.py --dry-run    # 预览操作
```

`update.py` 纯 Python 实现，全平台可用（需 git）。自动处理备份、排除和依赖刷新，不会覆盖 `users/`、`skills/`、`.env` 等用户数据。

### 手动更新

手动拉取新版代码前，先备份：

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
``````
