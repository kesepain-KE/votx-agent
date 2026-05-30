# PDF 读取与分析

> ⚠️ **使用本文档前请注意**：本文档应在实际处理 PDF 文件之前完整阅读，以选择最合适的工具和方法。不要在未阅读本文档的情况下盲目尝试处理 PDF。

用于从 PDF 文件中提取文本、表格和元数据的方法。

## votx-agent 首选方法：convert_to_markdown

votx-agent 内置了 `convert_to_markdown` 工具，可以直接将 PDF 转换为 Markdown 文本：

```
convert_to_markdown(input_path="path/to/file.pdf")
```

这会自动提取 PDF 的文本内容并转为 Markdown 格式，方便后续用 grep 检索。

## 快速决策表

| 场景 | 推荐工具 | 原因 | 命令/代码示例 |
|------|----------|------|--------------|
| PDF 转文本（最常用） | convert_to_markdown | 一键转换，输出 Markdown | `convert_to_markdown(input_path="doc.pdf")` |
| 纯文本提取 | pdftotext 命令 | 最快最简单 | `pdftotext input.pdf output.txt` |
| 需要保留布局 | pdftotext -layout | 保持原始排版 | `pdftotext -layout input.pdf output.txt` |
| 需要提取表格 | pdfplumber | 表格识别能力强 | `page.extract_tables()` |
| 需要元数据 | pypdf | 轻量级 | `reader.metadata` |
| 扫描PDF（图片） | OCR (pytesseract) | 无其他选择 | 先转图片再OCR |

## 文本提取优先级

**推荐优先级（从高到低）**：
1. **convert_to_markdown**（votx-agent 内置，一键转换）
2. **pdftotext 命令行工具**（最快，适合大多数 PDF）
3. pdfplumber（适合需要保留布局或提取表格）
4. pypdf（轻量级，适合简单提取）
5. OCR（仅用于扫描PDF或无法直接提取文本的情况）

## 快速开始：使用 pdftotext

> ⚠️ **重要**：必须将输出保存到文件，不要直接输出到终端（stdout），否则会占用大量 token！

```bash
# ✅ 正确：提取文本到文件（最快最简单）
pdftotext input.pdf output.txt

# ✅ 正确：保留布局并输出到文件
pdftotext -layout input.pdf output.txt

# ✅ 正确：提取特定页面到文件
pdftotext -f 1 -l 5 input.pdf output.txt  # 第1-5页

# ❌ 错误：不要使用 stdout（会占用大量 token）
# pdftotext input.pdf -
```

**使用流程**：
1. 优先使用 convert_to_markdown 转换 PDF
2. 或使用 pdftotext 提取文本到临时文件
3. 使用 grep 对生成的文本文件进行检索
4. 只读取匹配部分的上下文，而非全文

如果需要在 Python 中处理：

```python
from pypdf import PdfReader

# 读取 PDF
reader = PdfReader("document.pdf")
print(f"Pages: {len(reader.pages)}")

# 提取文本
text = ""
for page in reader.pages:
    text += page.extract_text()
```

## Python 库

### pypdf - 基本文本提取

```python
from pypdf import PdfReader

reader = PdfReader("document.pdf")

# 提取全部文本
for page in reader.pages:
    text = page.extract_text()
    print(text)

# 提取元数据
meta = reader.metadata
print(f"Title: {meta.title}")
print(f"Author: {meta.author}")
print(f"Subject: {meta.subject}")
print(f"Creator: {meta.creator}")
```

### pdfplumber - 带布局的文本和表格提取

#### 提取文本（保留布局）

```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        print(text)
```

#### 提取表格

```python
with pdfplumber.open("document.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        for j, table in enumerate(tables):
            print(f"Table {j+1} on page {i+1}:")
            for row in table:
                print(row)
```

#### 高级表格提取（转为 DataFrame）

```python
import pandas as pd

with pdfplumber.open("document.pdf") as pdf:
    all_tables = []
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            if table:  # 检查表格非空
                df = pd.DataFrame(table[1:], columns=table[0])
                all_tables.append(df)

# 合并所有表格
if all_tables:
    combined_df = pd.concat(all_tables, ignore_index=True)
    combined_df.to_excel("extracted_tables.xlsx", index=False)
```

## 命令行工具

### pdftotext (poppler-utils)

> ⚠️ **性能优化**：始终输出到文件，避免占用 token

```bash
# ✅ 提取文本到文件
pdftotext input.pdf output.txt

# ✅ 保留布局提取到文件
pdftotext -layout input.pdf output.txt

# ✅ 提取特定页面到文件
pdftotext -f 1 -l 5 input.pdf output.txt  # 第1-5页

# ✅ 提取带坐标的文本到 XML 文件（用于结构化数据）
pdftotext -bbox-layout document.pdf output.xml

# ❌ 避免：不要省略输出文件名（会输出到 stdout）
# pdftotext input.pdf
```

## 批量处理

```python
import os
import glob
from pypdf import PdfReader
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def batch_extract_text(input_dir):
    """批量提取文本"""
    pdf_files = glob.glob(os.path.join(input_dir, "*.pdf"))
    
    for pdf_file in pdf_files:
        try:
            reader = PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            
            output_file = pdf_file.replace('.pdf', '.txt')
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(text)
            logger.info(f"Extracted text from: {pdf_file}")
            
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_file}: {e}")
            continue
```

## 性能优化

1. **convert_to_markdown 优先**：votx-agent 内置工具，最方便
2. **文件输出优先**：始终将 pdftotext 输出保存到文件，然后用 grep 检索
3. **大型PDF**：使用流式方式逐页处理，避免一次性加载整个文件
4. **文本提取**：`pdftotext` 最快；pdfplumber 适合结构化数据和表格

## 快速参考

| 任务 | 最佳工具 | 命令/代码 |
|------|----------|-----------|
| PDF 转文本 | convert_to_markdown | `convert_to_markdown(input_path="doc.pdf")` |
| 提取文本 | pdfplumber | `page.extract_text()` |
| 提取表格 | pdfplumber | `page.extract_tables()` |
| 命令行提取 | pdftotext | `pdftotext -layout input.pdf output.txt` |
| 提取元数据 | pypdf | `reader.metadata` |
