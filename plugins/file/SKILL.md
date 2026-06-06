---
name: file
description: 文件操作工具集 — 读取、写入、精确编辑、列出目录、删除文件。默认受沙箱保护。设置 VOTX_FILE_READ_OUTSIDE_SANDBOX=1 后允许读取任意路径，VOTX_FILE_EDIT_OUTSIDE_SANDBOX=1 后允许编辑任意路径。当 Agent 需要读写文件、精确编辑、浏览目录或删除文件时使用。
---

# 文件操作

提供安全的文件系统操作，所有路径默认受沙箱保护。

## 工具

| 工具 | 用途 |
|------|------|
| `read_file` | 读取文件内容（UTF-8 / GBK 自动回退，20MB 限制） |
| `write_file` | 将内容完整覆盖写入文件 |
| `edit_file` | 精确编辑：insert / replace_line / replace_range，自动备份 |
| `list_dir` | 列出目录内容 |
| `delete_file` | 删除文件（禁止删目录） |

## 安全约束

- 所有路径默认限定在用户目录 (`VOTX_USER_DIR`) 和项目根目录内。
- `VOTX_FILE_READ_OUTSIDE_SANDBOX=1` 允许 read_file 读取任意路径。
- `VOTX_FILE_EDIT_OUTSIDE_SANDBOX=1` 允许 edit_file 编辑任意路径（write_file / delete_file 不受此开关影响）。
- write_file 越权时自动回退到用户目录下的 basename。
- delete_file 拒绝删除目录。
- edit_file 默认创建 `.bak` 备份，所有校验通过后才写备份和正文。
