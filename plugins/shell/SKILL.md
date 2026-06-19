---
name: shell
version: "1.0.2"
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
```

`run_command` 每次都是独立子进程，不保留上一次命令的目录或临时环境变量。多步任务优先使用 `working_dir`，需要组合命令时使用 `cmd.exe /c` 或 `powershell -NoProfile -Command`。

## 安全规则

- 使用明确路径，避免破坏性通配符。
- 不用系统命令替代文件、网络、文档、知识库等专用工具。
- 不打印密钥、token、`.env` 内容或用户隐私文件。
- 长任务要设置合理工作目录，并关注超时。

会被拦截的高风险命令包括批量删除、关机、磁盘格式化、防火墙修改和权限批量改写。

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

工具返回标准输出；没有标准输出时返回标准错误；都为空时返回 `(exit=<code>)`。需要稳定解析时，让命令输出 JSON、CSV 或固定格式文本。

## 配置

| 变量 | 说明 |
|------|------|
| `tool.tool_timeout` | 命令超时，读取优先级为用户配置 > 全局配置 > 工具内默认值 |
