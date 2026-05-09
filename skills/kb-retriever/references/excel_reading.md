# Excel 文件读取

> ⚠️ **使用本文档前请注意**：本文档应在实际处理 Excel 文件之前阅读，以了解正确的读取方法。请配合 excel_analysis.md 一起使用。

## votx-agent 首选方法：convert_to_markdown

votx-agent 内置了 `convert_to_markdown` 工具，可以直接将 Excel 转换为 Markdown 表格：

```
convert_to_markdown(input_path="path/to/file.xlsx")
```

这会自动将 Excel 工作表转为 Markdown 表格格式，方便快速预览数据结构和内容。

## 使用 pandas 读取

```python
import pandas as pd

# 读取第一个工作表（或指定工作表）
df = pd.read_excel("data.xlsx", sheet_name="Sheet1")

# 只读取前几行查看结构
df_preview = pd.read_excel("data.xlsx", nrows=10)

# 只读取需要的列（提高性能）
df = pd.read_excel("data.xlsx", usecols=["列1", "列2", "列3"])
```

## 读取单个工作表

```python
import pandas as pd

# 读取指定工作表
df = pd.read_excel("data.xlsx", sheet_name="Sheet1")

# 查看前几行
print(df.head())

# 基本统计信息
print(df.describe())
```

## 读取整个工作簿的所有工作表

```python
import pandas as pd

# 读取所有工作表
excel_file = pd.ExcelFile("workbook.xlsx")

for sheet_name in excel_file.sheet_names:
    df = pd.read_excel(excel_file, sheet_name=sheet_name)
    print(f"\n{sheet_name}:")
    print(df.head())
```

## 读取特定列

```python
import pandas as pd

# 只读取指定列（提高性能）
df = pd.read_excel("data.xlsx", usecols=["column1", "column2", "column3"])
```

## 性能优化选项

- 使用 `usecols` 只读取需要的列
- 使用 `dtype` 参数指定列类型以加快读取速度
- 根据文件类型选择合适的引擎：`engine='openpyxl'` 或 `engine='xlrd'`

## 处理大文件

对于非常大的 Excel 文件，避免一次性读取整个文件：
- 优先使用 convert_to_markdown 预览结构
- 使用 `nrows` 参数限制读取的行数
- 先读取前若干行了解数据结构
- 按需分批处理数据
