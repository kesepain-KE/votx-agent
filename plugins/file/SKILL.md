---
name: file
description: 文件操作工具集 — 读取、按行读取、写入、追加、精确编辑、列目录、目录树、文件信息、搜索、复制、移动、创建目录、删除文件。默认受沙箱保护，环境变量可放开沙箱外路径。
---

# 文件操作

`file` 提供本地文件系统操作。默认路径限定在项目根目录和当前用户目录内；如需操作沙箱外路径，通过环境变量显式放开。

## 工具

| 工具 | 用途 |
|------|------|
| `read_file` | 读取整个文件，支持 UTF-8 / UTF-8 BOM / GBK 回退，20MB 限制 |
| `read_file_range` | 按行读取，支持 `start_line/end_line` 或 `tail` 读取日志尾部 |
| `write_file` | 完整覆盖写入文件，不会越权回退到其他路径 |
| `append_file` | 追加写入文件，不存在则创建 |
| `edit_file` | 精确编辑：`insert` / `replace_line` / `replace_range` / `replace_text`，默认创建 `.bak` 备份 |
| `list_dir` | 列出目录内容，文件夹置前排序 |
| `tree_dir` | 输出目录树，默认跳过 `.git`、`node_modules`、`.venv`、`dist`、`build` 等大目录 |
| `stat_file` | 查看文件或目录类型、大小、创建时间、修改时间 |
| `search_files` | 搜索文件名、文件内容或代码定义，支持 `scope`、`context_lines` 和 `fd/rg` 加速 |
| `copy_file` | 复制文件，目标必须是完整文件路径，默认不覆盖 |
| `move_file` | 移动或重命名文件，目标必须是完整文件路径，默认不覆盖 |
| `make_dir` | 创建目录，默认递归创建父目录 |
| `delete_file` | 删除文件，严格禁止删除目录 |

## 沙箱环境变量

默认所有工具只能操作项目根目录和当前用户目录内的路径。

| 环境变量 | 效果 |
|----------|------|
| `VOTX_FILE_OUTSIDE_SANDBOX=1` | 允许所有 file 工具操作沙箱外路径 |
| `VOTX_FILE_READ_OUTSIDE_SANDBOX=1` | 允许 `read_file`、`read_file_range`、`list_dir`、`tree_dir`、`stat_file`、`search_files` 访问沙箱外路径 |
| `VOTX_FILE_EDIT_OUTSIDE_SANDBOX=1` | 允许 `write_file`、`append_file`、`edit_file`、`copy_file`、`move_file`、`make_dir` 操作沙箱外路径 |
| `VOTX_FILE_WRITE_OUTSIDE_SANDBOX=1` | 同上，作为写入类操作的别名 |
| `VOTX_FILE_DELETE_OUTSIDE_SANDBOX=1` | 允许 `delete_file` 删除沙箱外文件 |

## 行为约束

- `write_file` 不再在路径越权时自动回退到用户目录；越权时要么环境变量允许真实目标路径，要么明确报错。
- `delete_file` 只删除文件，拒绝删除目录。
- `copy_file` 和 `move_file` 的目标路径必须是完整文件路径；目标是目录时会报错。
- `copy_file` 和 `move_file` 默认不覆盖已有目标文件，需显式设置 `overwrite=true`。
- `edit_file` 默认创建 `.bak` 备份，所有校验通过后才写入。
- `search_files` 支持 `mode=file/text/code`、`scope=workspace/user/both`、`context_lines`、`file_glob`。
- `search_files` 内容搜索默认跳过大于 2MB 的文件，避免误扫大型二进制文件。

## 使用建议

- 读大文件或日志时优先用 `read_file_range` 的 `tail` 或行号范围。
- 小片段修改优先用 `edit_file` 的 `replace_text`，并设置 `expected_count=1`。
- 文件名、内容或代码定义检索统一使用 `search_files`。
