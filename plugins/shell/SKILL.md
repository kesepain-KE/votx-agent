---
name: shell
version: "1.0.1"
description: "VOTX Agent run_command tool usage guide — execute shell commands safely via the agent sandbox, with patterns for file ops, text processing, system info, and error handling."
author: "BytesAgain"
homepage: "https://bytesagain.com"
source: "https://github.com/bytesagain/ai-skills"
tags: [shell, bash, run_command, votx, agent, sandbox, automation, devtools]
category: "devtools"
---

# Shell — VOTX Agent run_command 使用指南

本技能指导如何在 VOTX Agent 中使用 `run_command` 工具安全执行 shell 命令。

`run_command` 是 VOTX Agent 提供的核心工具之一，它在受控沙箱环境中执行系统命令，agent 无需关心底层 Bash 语法细节即可完成文件操作、文本处理、系统查询等任务。

## 基本用法

调用 `run_command` 工具，传入要执行的命令字符串：

```
run_command(command: "<shell 命令>")
```

当前实现使用 `shell=False` 并按参数解析执行命令；管道、`&&`、重定向等 shell 语法需要显式调用 `cmd.exe /c` 或 `powershell -Command`。

工具返回 stdout 优先的文本结果；stdout 为空时返回 stderr，二者都为空时返回 `(exit=<code>)`。每次调用都是独立子进程，agent 无需手动管理 shell 会话状态。

## 安全性

`run_command` 在沙箱环境中执行，受以下安全约束：

### 沙箱限制

- 命令在受限的文件系统命名空间中运行，对主机文件系统的访问受白名单控制。
- 网络访问受策略控制，默认可能被限制或禁止。
- 资源使用（CPU 时间、内存）受超时和配额限制。

### 危险命令拦截

以下类型的命令会被拦截或要求确认：

- `rm -rf`、`dd` 等破坏性文件操作
- `curl`、`wget` 等网络下载命令（取决于沙箱策略）
- `sudo`、`su` 等提权命令
- 修改系统配置的命令（`systemctl`、`chmod 777` 等）
- 任意代码执行（`eval`、`bash -c` 嵌套调用）

**最佳实践：** 使用精确的文件路径，避免通配符在破坏性操作中的意外展开；优先使用工具提供的专用文件操作能力，而非直接调用 shell 命令。

## 工作目录与环境

### 工作目录

不传 `working_dir` 时默认使用当前用户目录；传入 `working_dir` 时建议使用绝对路径。使用绝对路径引用文件是最可靠的方式。

### 环境变量

沙箱环境继承一组受限的环境变量。由于当前实现不经过 shell，临时环境变量需要显式调用系统 shell：

```
# 在命令中设置环境变量
run_command(command: "powershell -NoProfile -Command \"$env:MY_VAR='value'; some-command\"")
```

可用的常见环境变量：`HOME`、`PATH`、`USER`、`PWD`。需要特定环境变量时应显式设置。

### 跨命令状态

每次 `run_command` 调用是独立的子进程，shell 状态（如 `cd` 后的目录、export 的环境变量）不会在调用之间保持。需要多步操作时，优先使用 `working_dir` 参数；确实需要 shell 语法时显式调用系统 shell：

```
# 使用 working_dir 执行单个命令
run_command(command: "python script.py", working_dir: "E:\\path\\to\\dir")

# 使用 shell 语法完成多步操作
run_command(command: "cmd.exe /c \"cd /d E:\\path\\to\\dir && script.bat && type result.txt\"")
```

## 常用模式

### 文件操作

```
# 读取文件
run_command(command: "cat /path/to/file.txt")

# 列出目录
run_command(command: "ls -la /path/to/dir")

# 查找文件
run_command(command: "find /path -name '*.log' -type f")

# 创建目录
run_command(command: "mkdir -p /path/to/new/dir")

# 写入文件（优先使用工具提供的 Write 能力）
# 如必须用 shell：使用重定向或 tee
```

### 文本处理

```
# 搜索内容
run_command(command: "grep -r 'pattern' /path/to/dir")

# 提取字段
run_command(command: "awk '{print $1, $3}' /path/to/file")

# 行数统计
run_command(command: "wc -l /path/to/file")

# 文本替换
run_command(command: "sed 's/old/new/g' /path/to/file")
```

### 系统信息

```
# 磁盘使用
run_command(command: "df -h")

# 内存信息
run_command(command: "free -m")

# 进程列表
run_command(command: "powershell -NoProfile -Command \"Get-Process | Select-Object -First 20\"")

# 当前用户和主机
run_command(command: "powershell -NoProfile -Command \"whoami; hostname\"")
```

### 管道与组合

`run_command` 本身不解析管道语法；需要管道、条件执行或重定向时，显式调用系统 shell：

```
# 多步过滤
run_command(command: "powershell -NoProfile -Command \"Get-Content log.txt | Select-String ERROR | Sort-Object | Group-Object\"")

# 结合多种工具
run_command(command: "cmd.exe /c \"dir /s /b *.go | findstr TODO\"")
```

## 错误处理与输出解读

### 退出码

`run_command` 默认返回 stdout 文本；stdout 为空时返回 stderr；二者都为空时返回 `(exit=<code>)`。如果需要稳定获取退出码，可显式调用 shell 并打印 `$LASTEXITCODE` 或 `%ERRORLEVEL%`。

### 解读输出

工具返回纯文本，不是结构化对象。需要解析结果时，优先让命令输出 JSON、CSV 或明确分隔符。

### 错误处理模式

```
# 条件执行：前一步失败则跳过后续
run_command(command: "cmd.exe /c \"if exist config.yaml type config.yaml\"")

# 错误时执行回退
run_command(command: "cmd.exe /c \"primary-command || fallback-command\"")

# 静默错误（stderr 重定向）
run_command(command: "cmd.exe /c \"command 2>nul\"")
```

### 常见问题排查

- **命令未找到：** 检查命令是否在沙箱的受限 `PATH` 中可用。
- **权限拒绝：** 检查文件路径是否在白名单内，操作是否被安全策略拦截。
- **超时：** 长时间运行的命令可能被超时机制终止；超时值遵循 `tool.tool_timeout` 配置优先级（用户配置 > 全局配置 > 工具内默认值）。
- **输出截断：** `run_command` 对输出大小有上限，超长输出应使用 `head`/`tail` 限制或输出到文件后分段读取。

## 配置

| 变量 | 说明 |
|------|------|
| `SHELL_DIR` | 数据目录（默认：~/.shell/） |
| `tool.tool_timeout` | 命令超时，读取优先级为用户配置 > 全局配置 > 工具内默认值 |

---

*Powered by BytesAgain | bytesagain.com | hello@bytesagain.com*
