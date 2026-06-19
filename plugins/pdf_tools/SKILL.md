---
name: pdf_tools
description: PDF 工具集 — 13 个工具覆盖信息/提取/拆分/合并/旋转/盖字/水印/预览/压缩/OCR/选页/删页/涂黑。当 Agent 需要查看、编辑、操作 PDF 文件时使用。
compatibility: pypdf + reportlab（必装）；pdf2image + pytesseract（OCR/预览可选）；ghostscript（压缩优化可选）
---

# PDF 工具集

**14 个工具**，覆盖 PDF 全生命周期操作。版本 v2.1.0。

## 工具速查

| # | 工具 | 类型 | 用途 | 依赖 |
|---|------|------|------|------|
| 1 | `pdf_info` | 查看 | 页数/尺寸/加密/文本层/图片/书签/表单/元数据 | pypdf |
| 2 | `pdf_render_preview` | 查看 | 渲染页面为图片（PNG/JPG） | pypdf+pdf2image+Pillow |
| 3 | `pdf_compare` | 查看 | 视觉 diff，差异区域红色高亮 | pypdf+pdf2image+Pillow+numpy |
| 4 | `pdf_extract_text` | 提取 | 提取文本（layout 模式 + OCR fallback） | pypdf(+pytesseract) |
| 5 | `pdf_ocr` | 提取 | OCR 扫描件→含文本层 PDF，支持 force/skip/deskew | pypdf+pdf2image+pytesseract |
| 6 | `pdf_split` | 页面 | 拆分（固定页数 / 范围 `1-3,5,8-10`） | pypdf |
| 7 | `pdf_select_pages` | 页面 | 抽取指定页面 | pypdf |
| 8 | `pdf_delete_pages` | 页面 | 删除指定页面 | pypdf |
| 9 | `pdf_merge` | 页面 | 合并多 PDF（去空白页+跳过无效） | pypdf |
| 10 | `pdf_rotate` | 页面 | 旋转（90/180/270/-90，选页） | pypdf |
| 11 | `pdf_compress` | 编辑 | 压缩（screen/ebook/printer/prepress 等级） | pypdf(+ghostscript) |
| 12 | `pdf_stamp_text` | 编辑 | 盖字/标注（颜色/透明度/旋转） | pypdf+reportlab |
| 13 | `pdf_watermark` | 编辑 | 斜铺水印（草稿/机密） | pypdf+reportlab |
| 14 | `pdf_redact` | 编辑 | 涂黑脱敏（关键词/正则/坐标） | pypdf |

## 通用参数

所有会写文件的工具统一支持：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `output_path` | string | 自动生成 | 输出文件路径 |
| `overwrite` | bool | false | 是否覆盖已有文件 |
| `auto_rename` | bool | true | 重名时自动追加序号 |
| `pages` | string | `all` | 页码范围：`all` / `1,3,5` / `1-3,5-7` |
| `dry_run` | bool | false | 只预览参数和预估结果，不写文件 |

## 推荐工作流

```
# 安全编辑流程
pdf_info → pdf_render_preview → pdf_stamp_text/watermark/redact → pdf_compare

# OCR 流程
pdf_info(检查文本层) → pdf_ocr(force_ocr=false,skip_text=true) → pdf_extract_text

# 拆合流程
pdf_info → pdf_split(page_ranges) → pdf_merge → pdf_compress
```

## 输出结构

**成功：**
```
[SUCCESS]
  output: /path/to/file.pdf
  pages: 10
  rotated: 3/10 pages by 90°
```

**失败：**
```
ERROR: [FILE_NOT_FOUND] 文件不存在: /path/bad.pdf
ERROR: [PAGE_OUT_OF_RANGE] 页码 99 超出范围（共 10 页）
ERROR: [DEPENDENCY] pdf2image 未安装: pip install pdf2image
```

## 错误码

| 错误码 | 含义 |
|--------|------|
| `INVALID_PATH` | 路径无效或越权 |
| `FILE_NOT_FOUND` | 文件不存在 |
| `NOT_PDF` | 不是 PDF 文件 |
| `PAGE_OUT_OF_RANGE` | 页码超出范围 |
| `PDF_ENCRYPTED` | PDF 已加密 |
| `NO_TEXT_LAYER` | 无文本层（扫描件） |
| `OCR_FAILED` | OCR 处理失败 |
| `DEPENDENCY` | 依赖库未安装 |
| `SAVE_FAILED` | 保存/写入失败 |

## 安装

```text
# 必装
pip install pypdf reportlab

# 可选：预览 + OCR
pip install pdf2image pytesseract Pillow

# 可选：预览、OCR、压缩功能需要把对应可执行程序加入 PATH。
```

## 安全边界

1. 所有 `file_path` / `output_path` 均经 `safe_path + check_sandbox` 校验
2. 限制在用户目录和项目目录内，禁止路径穿越
3. 默认 `auto_rename=true`，不覆盖原文件
4. 不读取远程 URL

## 参考

- pypdf: https://pypdf.readthedocs.io/
- reportlab: https://www.reportlab.com/docs/
