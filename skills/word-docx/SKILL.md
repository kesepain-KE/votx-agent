---
name: word-docx
description: Word 文档工具 — 创建和读取 .docx 文件。支持标题、正文、表格。当 Agent 需要生成 Word 文档或读取 .docx 文件内容时使用。
---

# Word 文档

创建和读取 Microsoft Word (.docx) 文档。

## 工具

| 工具 | 用途 |
|------|------|
| `create_docx` | 创建 .docx 文档（标题 + 正文） |
| `read_docx` | 读取 .docx 文件内容（段落 + 表格） |

## 前置条件

需要 python-docx 库：`pip install python-docx`
