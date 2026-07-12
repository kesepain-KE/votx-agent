---
name: file
description: 文件操作工具集 — 读取、按行读取、写入、追加、精确编辑、列目录、目录树、文件信息、搜索、复制、移动、创建目录、删除文件。默认受沙箱保护，环境变量可放开沙箱外路径。
version: "1.1"
category: core
enabled: true
tags: ["file", "core", "filesystem"]
---

# 文件操作 (File)

`file` 提供本地文件系统操作。路径解析保留，可通过环境变量放开沙箱外路径。

## 插件路径

`plugins/file/`

## 注册工具

| 工具 | 用途 |
|------|------|
| `read_file` | 读取整个文件，支持 UTF-8 / UTF-8 BOM / GBK 回退，无大小限制 |
| `read_file_range` | 按行读取，支持 `start_line/end_line` 或 `tail` 读取日志尾部 |
| `write_file` | 完整覆盖写入文件，自动创建父目录 |
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

## 关键参数说明

### edit_file

| 参数 | 说明 |
|------|------|
| `mode` (enum) | `insert` / `replace_line` / `replace_range` / `replace_text` |
| `text` | 插入内容、新行内容或替换后的文本 |
| `line` / `column` | 起始行号 / 列号（1-based） |
| `end_line` / `end_column` | 结束行号 / 列号（replace_range 模式） |
| `old_text` | replace_text 模式下要替换的原文 |
| `expected_count` | 期望匹配次数，默认 1；设为 -1 跳过检查 |
| `create_backup` | 是否创建 `.bak` 备份，默认 true |

### read_file_range

| 参数 | 说明 |
|------|------|
| `start_line` / `end_line` | 行号范围（1-based），`end_line=0` 按 `max_lines` 截断 |
| `tail` | 读取末尾 N 行；大于 0 时优先于行号范围 |
| `max_lines` | 最大返回行数，默认 500，上限 50000 |

### search_files

| 参数 | 说明 |
|------|------|
| `mode` (enum) | `file` / `name`（文件名）/ `text` / `content`（内容）/ `code`（代码定义） |
| `scope` (enum) | `workspace` / `user` / `both` |
| `root` | 搜索根目录，非空时优先于 scope |
| `file_glob` | 文件名 glob 过滤，如 `*.py` |
| `max_results` | 最大结果数，默认 50，上限 5000 |
| `context_lines` | 匹配行上下文行数，默认 0，上限 100 |
| `regex` | query 是否按正则处理 |

## 路径解析环境变量

路径解析保留（兼容相对路径和绝对路径）。以下环境变量可选地控制路径访问范围：

| 环境变量 | 效果 |
|----------|------|
| `VOTX_FILE_OUTSIDE_SANDBOX=1` | 允许所有 file 工具操作沙箱外路径 |
| `VOTX_FILE_READ_OUTSIDE_SANDBOX=1` | 允许 `read_file`、`read_file_range`、`list_dir`、`tree_dir`、`stat_file`、`search_files` 访问沙箱外路径 |
| `VOTX_FILE_EDIT_OUTSIDE_SANDBOX=1` | 允许 `write_file`、`append_file`、`edit_file`、`copy_file`、`move_file`、`make_dir` 操作沙箱外路径 |
| `VOTX_FILE_WRITE_OUTSIDE_SANDBOX=1` | 同上，作为写入类操作的别名 |
| `VOTX_FILE_DELETE_OUTSIDE_SANDBOX=1` | 允许 `delete_file` 删除沙箱外文件 |

不设置时默认允许项目根和用户目录；设置后允许全路径访问。

## 结果说明

- `read_file` / `read_file_range`：返回文件内容文本（`read_file_range` 带行号前缀和文件头信息）
- `write_file` / `append_file` / `edit_file` / `copy_file` / `move_file`：返回工具结果 JSON（含文件 artifact）
- `list_dir` / `tree_dir`：返回目录列表/树形结构文本
- `stat_file`：返回文件/目录元信息（类型、大小、修改/创建时间）
- `delete_file` / `make_dir`：返回 `OK:` 前缀的成功消息
- `search_files`：返回匹配结果列表
- 失败：返回 `ERROR:` 前缀的错误信息

## 常见规范

- 读大文件或日志时优先用 `read_file_range` 的 `tail` 或行号范围，不用 `read_file` 全量读取
- 小片段修改优先用 `edit_file` 的 `replace_text`，并设置 `expected_count=1` 确保精准匹配
- 文件名、内容或代码定义检索统一使用 `search_files`
- `copy_file` 和 `move_file` 的目标路径必须是完整文件路径；目标是目录时会报错
- `delete_file` 只删除文件，拒绝删除目录

## 常见处理办法

- **路径越权**：设置对应的环境变量放开沙箱，或确认路径在项目根/用户目录内
- **编码错误**：`read_file` 支持 UTF-8 → UTF-8 BOM → GBK 自动回退；如仍失败，指定 `encoding="gbk"`
- **edit_file 匹配失败**：检查 `old_text` 是否与文件内容完全一致（包括空格、换行），调整 `expected_count`
- **search_files 无结果**：确认 `scope` 包含目标目录；尝试 `include_hidden=true` 或调整 `file_glob`

## 常见教训

- `write_file` 是完整覆盖写入，不是追加；追加用 `append_file`
- `edit_file` 的 `replace_text` 模式默认 `expected_count=1`，如果原文出现多次会报错；设为 `-1` 跳过检查
- `tree_dir` 默认跳过 `.git`、`node_modules` 等大目录，需要查看时设 `include_hidden=true` 或 `max_depth` 更大
- `search_files` 的 `max_results` 上限 5000，`context_lines` 上限 100，超限自动截断