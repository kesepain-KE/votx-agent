---
name: markdown-converter
description: 文档转 Markdown 工具。使用 markitdown 将 PDF/Word/PPT/Excel/HTML/图片/音频/ZIP 等转为 Markdown 文本。当需要提取文档内容、转换文件格式、对二进制文件做文本检索时使用。
---

# Markdown Converter

Convert documents and files to Markdown using `markitdown`. Supports PDF, Word (.docx), PowerPoint (.pptx), Excel (.xlsx, .xls), HTML, CSV, JSON, XML, images (EXIF+OCR), audio (transcription), ZIP archives, YouTube URLs, EPubs.

## Usage

```
markitdown input.pdf                    # stdout
markitdown input.pdf -o output.md       # 保存到文件
markitdown input.docx > output.md       # 管道方式
```

## Options

- `-o OUTPUT`: 输出文件
- `-x EXTENSION`: 文件类型提示（stdin 时用）
- `-m MIME_TYPE`: MIME 类型提示
- `-c CHARSET`: 字符集提示
- `-d`: 使用 Azure Document Intelligence
- `-e ENDPOINT`: Document Intelligence 端点
- `-p`: 启用第三方插件
- `--list-plugins`: 列出已安装插件

## Notes

- 首次运行会缓存依赖，后续更快
- 输出保留文档结构（标题、表格、列表、链接）
- 复杂 PDF 可用 `-d` 配合 Azure Document Intelligence
