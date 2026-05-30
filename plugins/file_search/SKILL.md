---
name: file_search
description: 文件搜索工具 — 使用 search_model 搜索文件名、文件内容或代码定义。当 Agent 需要在项目中查找文件、搜索代码或定位定义时使用。
---

# 文件搜索工具

使用 `search_model` 工具搜索文件系统中的文件名称、内容或代码定义。优先使用 `fd`/`rg` 命令行工具加速搜索，不可用时自动回退到 Python 实现。

## 工具

| 工具 | 用途 |
|------|------|
| `search_model` | 搜索文件系统中名称/内容/代码定义 |

## 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `query` | string | 是 | — | 搜索关键词或正则表达式 |
| `mode` | string | 否 | `"text"` | 搜索模式: `file`(文件名), `text`(文件内容), `code`(代码定义) |
| `scope` | string | 否 | `"workspace"` | 搜索范围: `workspace`(工作区), `user`(用户目录), `both`(两者) |
| `root` | string | 否 | `""` | 自定义根目录路径（空串使用默认工作区根目录） |
| `file_glob` | string | 否 | `""` | 文件名 glob 过滤，如 `*.py`、`*.js` |
| `max_results` | integer | 否 | `50` | 最大结果数 (1-500) |
| `context_lines` | integer | 否 | `3` | 匹配行的上下文行数 (0-20) |

## 使用示例

**搜索文件名:**
```
search_model(query="tool.py", mode="file")
search_model(query="test_", mode="file", file_glob="*.py")
```

**搜索文件内容:**
```
search_model(query="register_tool", mode="text")
search_model(query="TODO|FIXME", mode="text", context_lines=2)
```

**搜索代码定义:**
```
search_model(query="search_model", mode="code")
search_model(query="handle_", mode="code", file_glob="*.py")
```

**指定搜索范围:**
```
search_model(query="config", mode="text", scope="user")
search_model(query="setup", mode="file", scope="both", root="/home/user/projects")
```
