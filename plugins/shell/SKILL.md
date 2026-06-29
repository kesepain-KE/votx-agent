---
name: shell
version: "1.1.0"
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

## 安全规则

- 使用明确路径，避免破坏性通配符。
- 不用系统命令替代文件、网络、文档、知识库等专用工具。
- 不打印密钥、token、`.env` 内容或用户隐私文件。
- 长任务要设置合理工作目录，并关注超时。

会被拦截的高风险命令包括批量删除、关机、磁盘格式化、防火墙修改、权限批量改写，以及常见的 PowerShell / shell 危险删除变体。

## 常用模式

### Python 优先

```text
run_command(command: "python -m py_compile main.py", working_dir: "E:\\code\\votx-agent")
run_command(command: "python -m compileall -q .", working_dir: "E:\\code\\votx-agent")
run_command(command: "python setup.py", working_dir: "E:\\code\\votx-agent")
```

### PowerShell

```text
run_command(command: "powershell -NoProfile -Command \"Get-ChildItem -File\"")
run_command(command: "powershell -NoProfile -Command \"Get-Content .\\version.json\"")
run_command(command: "powershell -NoProfile -Command \"Get-Process | Select-Object -First 10\"")
```

### cmd.exe

```text
run_command(command: "cmd.exe /c \"dir /b\"")
run_command(command: "cmd.exe /c \"build_windows.bat\"")
```

## 输出与错误

工具优先返回单一输出流；当标准输出和标准错误同时存在时，会同时返回两者并标注 `STDOUT:` / `STDERR:`。非零退出码会附带 `(exit=<code>)`。需要稳定解析时，让命令输出 JSON、CSV 或固定格式文本。

## 配置

| 变量 | 说明 |
|------|------|
| `tool.tool_timeout` | 命令超时，读取优先级为用户配置 > 全局配置 > 工具内默认值 |
