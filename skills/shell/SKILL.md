---
name: shell
description: 系统命令执行工具。shell=False 安全执行，参数级黑名单拦截危险操作。Agent 需要运行系统命令时使用。
---

# 系统命令

命令执行工具，默认对新用户禁用。

## 工具

| 工具 | 用途 |
|------|------|
| `run_command` | 执行系统命令（参数黑名单过滤） |

## 安全约束

- `shell=False` + `shlex.split` 解析
- 参数级黑名单拦截危险模式（rm -rf /, chmod 777 /, shutdown 等）
- 120 秒超时
- UTF-8 编码，errors=replace
- 默认对新用户禁用（deny: ["run_command"]）
