# 部署手册

votx-agent 支持 Windows 打包、Linux 原生安装和 Docker 部署。Web UI 默认端口统一为 `1478`，可通过 `--port` 或环境变量 `PORT` 修改。

## Windows 打包

```cmd
build_windows.bat
```

脚本会安装 `requirements.txt` 依赖、构建 React 前端、执行 PyInstaller，并生成 `dist\votx-agent-windows.zip`。

打包时不会把 `message/config.json`、`message/config.local.json`、`message/push_queue` 和 `message/identity/identity_map.json` 放进发布包，避免把本机 token 或运行时队列带入交付物。发布包内会保留 `message-runtime\config.example.json` 作为配置模板。

## Linux 原生安装

```bash
bash install.sh
```

脚本会完成：

1. 检查 Python 3.10+
2. 创建 `.venv`
3. 安装 `requirements.txt`
4. 构建 Web UI
5. 创建 `.env`、`message/config.local.json` 模板和运行时目录
6. 注册 `/usr/local/bin/votx`
7. 可选交互式创建用户

常用启动：

```bash
votx web --port=1478
votx cli
```

## Docker 部署

```bash
bash install_docker.sh
```

脚本会创建：

- `users/`
- `message-runtime/`
- `.env`
- `message-runtime/config.example.json`

然后执行 `docker compose build` 和 `docker compose up -d`。

手动方式：

```bash
docker compose build
docker compose up -d
docker exec -it votx-agent python set_user.py add
```

访问：

```text
http://localhost:1478
```

## 外部 NapCat 连接

NapCat 不由 votx-agent 管理。Docker 部署时，在 `message-runtime/config.json` 中配置可从 votx-agent 容器访问的地址：

| NapCat 位置 | `ws_url` 示例 |
|---|---|
| 宿主机 | `ws://host.docker.internal:3001` |
| 同一 Docker 网络服务名 | `ws://napcat:3001` |
| 远程服务器 | `ws://<ip-or-domain>:3001` |

Linux 原生或 Windows 本机部署通常使用：

```json
"ws_url": "ws://127.0.0.1:3001"
```
