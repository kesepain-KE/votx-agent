---
name: word_docx
description: Word 文档工具 — 创建和读取 .docx 文件。约 43 个实际入参覆盖 20 类排版/工程化能力，支持预设风格和目录。当 Agent 需要生成 Word 文档或读取 .docx 文件内容时使用。
compatibility: 需要 python-docx (pip install python-docx)。PDF 导出需 LibreOffice。
---

# Word 文档工具

约 **43 个实际入参**，覆盖 **20 类排版/工程化能力**。

## 工具

| 工具 | 入参 | 覆盖 |
|------|------|------|
| `create_docx` | ~43 | 20 类（输出/内容/字体/标题/页面/段落/页码/表格/图片/模板/工程化） |
| `read_docx` | 1 | 段落含格式 + 表格 + 图片 + 页面信息 |

## 快速上手

```json
// 学术论文
{"output_dir": "output/", "title": "...", "content": "...", "style_preset": "academic"}
// 中文报告 + 目录
{"output_dir": "output/", "title": "...", "content": "# ...\n\n## ...", "content_format": "markdown", "style_preset": "report", "toc": true}
// 合同
{"output_dir": "output/", "title": "...", "content": "...", "style_preset": "contract"}
```

---

## 参数优先级

| # | 冲突项 | 优先级规则 |
|---|--------|-----------|
| 1 | `output_dir` vs `output_path` | `output_dir` 优先；`output_path` 仅为兼容旧字段保留 |
| 2 | `style_preset` vs 显式参数 | `style_preset` 提供默认值，显式传入的参数覆盖预设 |
| 3 | `template_path` vs 页面/字体参数 | 模板提供基础样式，显式传入的参数覆盖模板 |
| 4 | `overwrite` vs `auto_rename` | `overwrite=true` → 直接覆盖；否则 `auto_rename=true` → 自动追加序号；两者皆 false 且文件存在 → `FILE_EXISTS` |
| 5 | `title` vs Markdown `#` | 若有 `title`，作为文档主标题（居中加粗）；Markdown `#` 渲染为一级标题，在 TOC 中生效 |
| 6 | `content_format` | `plain` → 全文为普通段落；`markdown` → 解析标题/加粗/斜体/列表/水平线 |
| 7 | `toc` | 仅在 `content_format=markdown` 且内容含 `#` 标题时有效；生成 TOC 域（Word 中右键更新） |
| 8 | `export_pdf` | 尝试转换 PDF；`strict_mode=false` 时失败不影响 DOCX 生成 |
| 9 | `render_check` | 生成后检测空文档/表格溢出；失败不影响文件保存 |
| 10 | `strict_mode` | `true` → 参数格式/值不合法时直接报错 `STRICT_MODE_ERROR`，不自动兜底 |

---

## 样式预设

| 预设 | 字体 | 字号 | 行距 | 缩进 | 页码 |
|------|------|------|------|------|------|
| `academic` | SimSun | 12pt | double | 0.74cm | 居中数字 |
| `report` | 微软雅黑 | 12pt | 1.5 | 0.74cm | 第 X 页 / 共 N 页 |
| `contract` | SimSun | 12pt | 1.5 | — | 居中数字 |

> `style_preset` 预设参数可被显式传入参数逐项覆盖。例如 `style_preset=academic` 同时传 `font_name=微软雅黑` → 正文用微软雅黑，其余保持学术论文预设。

---

## 核心参数速查

### 输出 & 文件（6 个）
`output_dir`, `output_path`（废弃）, `filename`, `overwrite`, `auto_rename`, `template_path`

### 内容 & 格式（5 个）
`title`, `content`, `content_format`, `text_align`, `toc`

### 字体（5 个）
`font_name`, `font_size`, `font_color`, `title_font_size`, `title_bold`, `title_spacing_after`

### 页面（6 个）
`page_size`, `orientation`, `margin_top`, `margin_bottom`, `margin_left`, `margin_right`

### 段落（4 个）
`line_spacing`, `paragraph_spacing`, `first_line_indent`, `text_align`

### 页码（3 个）
`page_number`, `page_number_format`, `page_number_align`

### 表格（4 个）
`table_data`, `table_style`, `table_autofit`, `table_repeat_header`

### 图片（2 个）
`images`, `keep_aspect_ratio`

### 工程化（5 个）
`export_pdf`, `render_check`, `strict_mode`, `style_preset`, `metadata`, `language`

---

## 默认值

| 参数 | 默认值 |
|------|--------|
| `filename` | `文档` |
| `font_size` | `12` |
| `page_size` | `a4` |
| `orientation` | `portrait` |
| `margin_*` | `2.54` cm |
| `line_spacing` | `1.5` |
| `text_align` | `justify` |
| `title_font_size` | `16` |
| `title_bold` | `true` |
| `keep_aspect_ratio` | `true` |
| `auto_rename` | `true` |
| `overwrite` | `false` |
| `table_autofit` | `true` |
| `table_repeat_header` | `true` |
| `content_format` | `plain` |

---

## 返回值结构

**成功：**
```
[SUCCESS]
  docx: users/name/download/报告.docx
  size: 12345 bytes (12.1 KB)
  pdf: users/name/download/报告.pdf          ← 仅有 export_pdf=true 且 LibreOffice 可用时
  render: passed                              ← 仅有 render_check=true 时
  warnings: none
```

**有警告：**
```
[SUCCESS]
  docx: users/name/download/报告.docx
  size: 12345 bytes (12.1 KB)
  render: FAILED (1 issues)
    - 表格 1 有 12 列，可能横向溢出
  warnings: 1
```

**失败：**
```
ERROR: [FILE_EXISTS] 文件已存在: 报告.docx（设置 overwrite=true 或 auto_rename=true）
ERROR: [INVALID_IMAGE_PATH] 图片路径不存在: bad/path.png
ERROR: [INVALID_TABLE_DATA] table_data 格式错误：应为数组或对象
ERROR: [STRICT_MODE_ERROR] page_size 不支持: A6，可选: a4, a3, a5, letter, legal, b5
```

---

## 错误码（13 个）

| 错误码 | 含义 |
|--------|------|
| `INVALID_OUTPUT_DIR` | 输出目录非法或不可写 |
| `FILE_EXISTS` | 文件已存在且 overwrite=false, auto_rename=false |
| `INVALID_COLOR` | 颜色格式不支持（仅 strict_mode） |
| `INVALID_PAGE_SIZE` | 纸张尺寸不支持（仅 strict_mode） |
| `INVALID_TABLE_DATA` | 表格数据格式错误（仅 strict_mode） |
| `INVALID_JSON` | metadata 等 JSON 解析失败（仅 strict_mode） |
| `INVALID_IMAGE_PATH` | 图片路径不存在或越权 |
| `INVALID_TEMPLATE_PATH` | 模板不存在或不是 .docx |
| `PATH_TRAVERSAL` | 路径越权（.. / 系统目录等） |
| `STRICT_MODE_ERROR` | strict_mode 下参数校验失败 |
| `RENDER_CHECK_FAILED` | 渲染检查发现问题 |
| `SAVE_FAILED` | DOCX 保存失败 |
| `DEPENDENCY` | python-docx 未安装 |

---

## 安全边界

1. `output_dir` 限制在用户工作目录或项目目录内（`safe_path + check_sandbox`）
2. 禁止路径穿越 `../`、绝对系统路径
3. `template_path` 和 `images[].path` 均经过相同安全校验
4. 不读取远程 URL（仅本地文件路径）
5. `overwrite=true` 仅覆盖用户目录内文件，不能覆盖项目核心文件

---

## 表格 & 图片数据结构

### table_data（原生数组）

```json
[
  {
    "caption": "成绩表",
    "headers": ["姓名", "成绩", "备注"],
    "rows": [
      ["张三", "90", "优秀"],
      ["李四", "85", "良好"]
    ]
  }
]
```

### images（原生数组）

```json
[
  {
    "path": "images/chart.png",
    "width": 400,
    "height": 260,
    "alignment": "center",
    "caption": "图1 销售趋势"
  }
]
```

---

## content Markdown 标记

```
# 一级标题        ← TOC 目录项
## 二级标题       ← TOC 目录项
### 三级标题      ← TOC 目录项

**加粗**
*斜体*

- 无序列表
1. 有序列表

---              ← 水平分隔线
```

---

## 前置条件

```bash
pip install python-docx
# PDF 导出:
apt install libreoffice-core
```

## 参考

- python-docx: https://python-docx.readthedocs.io/
