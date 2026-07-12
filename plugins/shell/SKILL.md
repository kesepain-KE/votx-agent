---
name: shell
version: "1.2.0"
description: "VOTX Agent run_command tool usage guide for safe local command execution."
author: "BytesAgain"
homepage: "https://bytesagain.com"
source: "https://github.com/bytesagain/ai-skills"
tags: [run_command, votx, agent, sandbox, automation, devtools]
category: "devtools"
---

# run_command 使用指南

本技能说明如何在 VOTX Agent 中安全调用 `run_command`。优先使用专用工具；只有诊断、构建、测试或没有等价工具时才调用系统命令。

## 基本用法

```text
run_command(command: "python --version")
run_command(command: "python start_web.py", working_dir: "E:\\code\\votx-agent")
run_command(command: "python -c \"import sys; print(sys.stdin.read())\"", stdin: "hello")
run_command(command: "python -c \"import os; print(os.environ['FOO'])\"", env: {"FOO": "bar"})
run_command(command: "export FOO=\"bar baz\" && env", session_id: "dev")
run_command(command: "cd E:\\code\\votx-agent && python --version")
run_command(command: "python -c \"import sys; sys.exit(1)\" || python -c \"print(42)\"")
run_command(command: "python -c \"print(1)\" ; python -c \"print(2)\"")
run_command(command: "pwd")
run_command(session_id: "dev", command: "cd E:\\code\\votx-agent && export FOO=bar && pwd")
run_command(session_id: "dev", command: "history")
run_command(session_id: "dev", reset_session: true, command: "pwd")
```

`run_command` 每次都是独立子进程，不保留上一次命令的目录、临时环境变量或标准输入。多步任务优先使用 `working_dir`；如果要临时切目录，可以在同一条命令里用受限的 `cd/chdir/pwd` 片段，或用 `&&` / `||` / `;` 连接多个步骤。
`session_id` 会让 `cwd`、会话环境变量和历史记录在多次调用间保持一致；`reset_session` 可清空指定会话。`export/set/env` 现在支持带空格的赋值值，比如 `FOO="bar baz"`。

## 可用参数

- `working_dir`：工作目录，默认使用当前用户目录。
- `timeout`：单次命令超时，`0` 表示使用配置值。
- `stdin`：传给子进程的标准输入文本。
- `env`：附加环境变量，只接受普通键名，敏感键会被拒绝。
- `session_id`：同一会话共享 `cwd/env/history`。
- `reset_session`：重置指定 `session_id` 的会话状态。
- `cd/chdir`：只在当前调用内生效；可以写成 `cd 目录 && 命令`。
- `&&` / `||` / `;`：顶层命令链连接符，按顺序执行。
- `pwd`：返回当前调用的工作目录。
- `export/set/env`：设置或查看会话环境变量。
- `unset`：删除会话环境变量。
- `history`：查看会话历史。

## 跨平台兼容性

`run_command` 使用 `subprocess` 安全模式（`shell=False`），不经过系统 shell 解析，因此跨平台行为一致。但需要注意以下差异：

### 路径分隔符

| 平台 | 路径分隔符 | 示例 |
|------|-----------|------|
| Windows | `\` | `E:\code\votx-agent` |
| Linux/macOS | `/` | `/home/user/votx-agent` |

- `working_dir` 参数支持原生路径分隔符，也接受 `/`（Windows 上 Python 会自动转换）。
- 命令中的路径参数需要使用对应平台的分隔符，或在 Python 命令中使用 `os.path.join`。

### 命令差异速查

| 场景 | Windows | Linux/macOS |
|------|---------|-------------|
| 列目录 | `dir /b` (cmd) | `ls` |
| 查看文件内容 | `type file.txt` (cmd) | `cat file.txt` |
| 查看环境变量 | `set` (cmd) 或 `env | sort` (PowerShell) | `env \| sort` |
| 查找进程 | `tasklist` | `ps aux` |
| 终止进程 | `taskkill /PID xxx` | `kill xxx` |
| 查看端口 | `netstat -ano` | `ss -tlnp` 或 `netstat -tlnp` |
| 查找文件 | `where xxx` (cmd) | `which xxx` 或 `find / -name xxx` |
| 查看磁盘 | `wmic logicaldisk get` | `df -h` |
| 系统信息 | `systeminfo` | `uname -a` |

### Windows 专属

```text
run_command(command: "cmd.exe /c \"dir /b\"")
run_command(command: "cmd.exe /c \"build_windows.bat\"")
run_command(command: "powershell -NoProfile -Command \"Get-ChildItem -File\"")
run_command(command: "powershell -NoProfile -Command \"Get-Content .\\version.json\"")
run_command(command: "powershell -NoProfile -Command \"Get-Process | Select-Object -First 10\"")
```

Windows 下 `run_command` 自带 UTF-8 编码处理：
- 自动设置 `chcp 65001`（通过 `PYTHONUTF8=1` 环境变量）
- 命令输出自动按 UTF-8 优先解码，回退 GBK
- `cmd /c` 和 `cmd /k` 命令会自动注入 `chcp 65001 > nul` 前缀

### Linux/macOS 专属

```text
run_command(command: "ls -la", working_dir: "/home/user/votx-agent")
run_command(command: "cat /etc/os-release")
run_command(command: "ps aux | grep python")
run_command(command: "df -h")
run_command(command: "uname -a")
run_command(command: "systemctl status votx-agent")
```

Linux/macOS 下编码默认 UTF-8，无需特殊处理。

### 通用跨平台写法

优先使用 Python 命令代替平台特定命令：

```text
# 获取文件列表（跨平台）
run_command(command: "python -c \"import os; print('\\n'.join(os.listdir('.')))\"")

# 获取环境变量（跨平台）
run_command(command: "python -c \"import os; print('\\n'.join(f'{k}={v}' for k,v in sorted(os.environ.items())))\"")

# 查找命令路径（跨平台）
run_command(command: "python -c \"import shutil; print(shutil.which('git'))\"")

# 获取系统信息（跨平台）
run_command(command: "python -c \"import platform; print(platform.platform())\"")
```

## 安全规则

- 使用明确路径，避免破坏性通配符。
- 不用系统命令替代文件、网络、文档、知识库等专用工具。
- 不打印密钥、token、`.env` 内容或用户隐私文件。
- 长任务要设置合理工作目录，并关注超时。

## 常用模式

### Python 优先

```text
run_command(command: "python -m py_compile main.py", working_dir: "E:\\code\\votx-agent")
run_command(command: "python -m compileall -q .", working_dir: "E:\\code\\votx-agent")
run_command(command: "python setup.py", working_dir: "E:\\code\\votx-agent")
```

### Git 操作

```text
run_command(command: "git status", working_dir: "E:\\code\\votx-agent")
run_command(command: "git log --oneline -10", working_dir: "E:\\code\\votx-agent")
run_command(command: "git diff --stat", working_dir: "E:\\code\\votx-agent")
```

### 环境检查

```text
run_command(command: "python --version")
run_command(command: "node --version")
run_command(command: "pip list")
```

### 会话模式

```text
run_command(session_id: "dev", command: "cd /home/user/project && export PATH=$PATH:/usr/local/bin && pwd")
run_command(session_id: "dev", command: "python --version")
run_command(session_id: "dev", command: "history")
run_command(session_id: "dev", reset_session: true, command: "pwd")
```

## 输出与错误

工具优先返回单一输出流；当标准输出和标准错误同时存在时，会同时返回两者并标注 `STDOUT:` / `STDERR:`。非零退出码会附带 `(exit=<code>)`。需要稳定解析时，让命令输出 JSON、CSV 或固定格式文本。

## 配置

| 变量 | 说明 |
|------|------|
| `tool.tool_timeout` | 命令超时，读取优先级为用户配置 > 全局配置 > 工具内默认值 |

## 插件路径

`plugins/shell/`

## 注册工具

| 工具 | 用途 |
|------|------|
| `run_command` | 以受控 subprocess 模式执行本地命令，支持工作目录、stdin、环境变量、超时和会话状态 |

## 结果说明

- 成功：返回标准输出；同时存在标准错误时标记 `STDOUT:` / `STDERR:`。
- 非零退出：附带 `(exit=<code>)`。
- 超时或校验失败：返回 `ERROR:` 前缀的错误信息。

## 常见规范

- 专用 Skill 或文件/网络工具能完成时，不使用 shell。
- 命令保持短、可解释、范围明确；构建和测试设置正确的 `working_dir`。
- 需要跨调用保留目录和环境变量时使用固定 `session_id`。
- 不读取或输出密钥、token、密码和 `.env` 内容。

## 常见处理办法

- **工作目录越权或不存在**：核对实际路径；必要时在命令参数中使用绝对路径，不盲目重复。
- **Windows 命令不兼容**：显式调用 `cmd.exe /c` 或 `powershell -NoProfile -Command`。
- **编码乱码**：优先使用 Python UTF-8 模式或工具内置的 UTF-8/GBK 回退。
- **命令超时**：调大 `timeout` 或拆分任务；连续失败时停止重试并分析原因。

## 常见教训

- `run_command` 默认不经过系统 shell，管道、重定向和平台内建命令可能需要显式 shell 入口。
- 独立调用不会保留 cwd/env；需要持久状态时必须使用 `session_id`。
- shell 不应替代已有专用工具，否则会降低可控性和可移植性。
