# 部署、环境变量与更新

本页说明 VOTX Agent 的原生运行、Docker 运行、环境变量和更新脚本行为。

## 推荐目录

项目根目录示例：

```text
E:\code\votx-agent
```

Linux/Docker 示例：

```text
/opt/votx-agent
```

重要目录：

```text
users/              用户数据，更新不覆盖
skills/             用户拓展技能，更新不覆盖
plugins/            内置技能，更新会覆盖
knowledge/          全局知识库，更新时单独询问
message-runtime/    Docker 外部消息运行配置，更新不强制覆盖
.env                环境变量文件，更新不覆盖
```

## Windows 启动

开发环境：

```powershell
python start_web.py
```

启动后访问：

```text
http://localhost:1478
```

Windows 特供版暂不执行自动更新脚本。启动 Web 时会在终端提示本地版本和远程版本情况。

如果不想检查版本：

```powershell
$env:VOTX_SKIP_VERSION_CHECK="1"
python start_web.py
```

## Linux 原生启动

首次安装：

```bash
bash install.sh
```

启动 Web：

```bash
python start_web.py
```

或使用项目提供的启动命令：

```bash
votx web --port=1478
```

更新后会执行：

```bash
bash install.sh --skip-user
```

含义：只补装或更新框架依赖，不重新创建用户，不覆盖 `users/`。

## Docker 启动

首次安装：

```bash
bash install_docker.sh
```

启动：

```bash
docker compose up -d
```

查看日志：

```bash
docker compose logs -f
```

Docker 更新后会执行：

```bash
docker compose build
docker compose up -d
```

含义：

- `docker compose build`：用更新后的源码重新构建本地镜像。
- `docker compose up -d`：后台重启服务并使用新镜像。

当前项目不依赖远程 Docker 镜像仓库。

## 环境变量文件

项目根目录可以放置：

```text
.env
```

`.env` 不会被更新脚本覆盖。

示例：

```env
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com

OPENAI_API_KEY=sk-xxx

ANTHROPIC_API_KEY=sk-ant-xxx
ANTHROPIC_BASE_URL=

TAVILY_API_KEY=tvly-xxx

VOTX_MESSAGE_CONFIG=message/config.local.json
VOTX_SKIP_VERSION_CHECK=0
```

不要把 `.env` 提交到公开仓库。

## 常用环境变量

### 服务启动

```text
PORT                  Web 端口
VOTX_HOST             Web 监听地址
VOTX_USER_DIR         用户目录根路径，默认 users/
VOTX_PROVIDER         临时指定 provider 类型
```

### 模型服务

```text
DEEPSEEK_API_KEY      DeepSeek 或 OpenAI 兼容服务 Key
DEEPSEEK_BASE_URL     DeepSeek 或 OpenAI 兼容服务 base_url
OPENAI_API_KEY        OpenAI Key
ANTHROPIC_API_KEY     Anthropic Key
ANTHROPIC_BASE_URL    Anthropic base_url
```

优先级通常是：

```text
用户 config.json > 环境变量 > 程序默认值
```

因此，多用户部署时建议把模型配置写在各自的 `users/<用户名>/config.json` 中。

### 外部消息

```text
VOTX_MESSAGE_CONFIG   外部消息路由配置文件路径
```

Docker 推荐：

```env
VOTX_MESSAGE_CONFIG=/app/message-runtime/config.json
```

### 版本检查

```text
VOTX_SKIP_VERSION_CHECK=1
VOTX_VERSION_URL=https://example.com/version.json
```

`VOTX_SKIP_VERSION_CHECK=1` 会关闭启动时版本提示。

`VOTX_VERSION_URL` 可指定自定义版本文件地址。

### 网络代理

```text
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

Telegram、网络搜索、网页获取、更新检查等可能需要代理。

## Docker 配置建议

典型挂载：

```yaml
services:
  votx-agent:
    ports:
      - "1478:1478"
    volumes:
      - ./users:/app/users
      - ./skills:/app/skills
      - ./knowledge:/app/knowledge
      - ./message-runtime:/app/message-runtime
    environment:
      - VOTX_MESSAGE_CONFIG=/app/message-runtime/config.json
```

建议：

- `users/` 必须挂载，避免容器重建后丢失用户数据。
- `skills/` 建议挂载，保留用户拓展技能。
- `message-runtime/` 建议挂载，保存外部消息私有配置。
- `plugins/` 不建议挂载为用户数据，因为它属于框架内置技能，更新会覆盖。

## 更新脚本

更新脚本：

```text
update.py
```

检查版本：

```bash
python update.py --check
```

Linux 原生更新：

```bash
python update.py --native
```

Docker 更新：

```bash
python update.py --docker
```

强制更新：

```bash
python update.py --force
```

自动确认：

```bash
python update.py --yes
```

试运行，不实际修改：

```bash
python update.py --dry-run
```

## 更新会覆盖什么

会覆盖更新框架代码和内置能力：

```text
agents/
config/
cron/
message/
plugins/
provider/
run/
web/
*.py
*.sh
*.json
*.toml
*.md
Dockerfile
docker-compose.yml
requirements.txt
```

`config/` 如果和新版不同，脚本会提示，用户可以选择覆盖或保留。

## 更新不会覆盖什么

```text
users/
skills/
.env
.session_secret
.venv/
message-runtime/
message/config.local.json
message/config.json
message/identity/identity_map.json
message/push_queue/
```

含义：

- `users/`：用户数据、聊天记录、文件、记忆全部保留。
- `skills/`：用户拓展技能全部保留。
- `.env`：密钥环境变量保留。
- `message-runtime/`：Docker 外部消息配置保留或按用户选择处理。
- `message/push_queue/`：运行队列不比较、不覆盖，避免误动未发送任务。

## knowledge/ 更新策略

`knowledge/` 是全局知识库。更新时会提供三个选择：

```text
1 合并更新：新增/覆盖内置知识库文件，保留用户额外文件（推荐）
2 跳过：完全不更新 knowledge/
3 全量覆盖：删除本地 knowledge/ 后复制新版
```

默认建议选择 `1`。

## 备份

每次更新前会备份到：

```text
.backups/update-YYYYmmdd-HHMMSS/
```

默认只保留最近两个旧备份。

## 常见问题

### 本地版本高于远程版本

脚本会提示版本差异。用户确认后可以回退覆盖。

### Windows 能不能用 update.py

不建议。Windows 特供版只做版本提示，不做自动覆盖更新。

### 更新后依赖缺失

Linux 原生运行：

```bash
bash install.sh --skip-user
```

Docker 运行：

```bash
docker compose build
docker compose up -d
```

### 更新后外部消息配置失效

检查：

- `VOTX_MESSAGE_CONFIG` 是否指向正确文件。
- Docker 是否挂载了 `message-runtime/`。
- `message-runtime/config.json` 是否和新版模板差异过大，需要手动合并。
