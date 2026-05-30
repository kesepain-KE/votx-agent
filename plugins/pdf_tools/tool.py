"""PDF 工具 — 读取信息 / 提取文本 / 拆分 / 合并 / 旋转 / 编辑"""
import os
from pathlib import Path
from io import BytesIO

from run.tool import register_tool
from plugins._common import err, truncate, safe_path, check_sandbox, get_current_user_dir

# ---- 依赖检测 ----

try:
    from pypdf import PdfReader, PdfWriter
    HAS_PYPDF = True
except ImportError:
    PdfReader = None
    PdfWriter = None
    HAS_PYPDF = False

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    HAS_REPORTLAB = True
except ImportError:
    canvas = None
    letter = None
    HAS_REPORTLAB = False

_MISSING_DEPS_MSG = "pypdf 未安装，请执行: pip install pypdf"
_MISSING_REPORTLAB_MSG = "reportlab 未安装，请执行: pip install reportlab"


# ---- 工具函数 ----

def pdf_info(file_path: str) -> str:
    """获取 PDF 元数据（页数、尺寸、作者等）

    Args:
        file_path: PDF 文件路径
    """
    if not HAS_PYPDF:
        return err(_MISSING_DEPS_MSG)

    p = safe_path(file_path)
    if p is None:
        return err(f"无效路径: {file_path}")
    resolved = check_sandbox(p)
    if not resolved:
        return err(f"路径越权（仅允许项目目录和用户目录）: {file_path}")
    if not resolved.exists():
        return err(f"文件不存在: {resolved}")
    if not resolved.suffix.lower() == ".pdf":
        return err(f"不是 PDF 文件: {resolved}")

    try:
        reader = PdfReader(str(resolved))
        info = reader.metadata or {}

        lines = [f"文件: {resolved.name}"]
        lines.append(f"路径: {resolved}")
        lines.append(f"页数: {len(reader.pages)}")

        if info:
            lines.append("\n元数据:")
            for key in ("/Title", "/Author", "/Subject", "/Creator", "/Producer", "/CreationDate", "/ModDate"):
                val = info.get(key)
                if val:
                    lines.append(f"  {key.lstrip('/')}: {val}")

        lines.append("\n页面尺寸:")
        for i, page in enumerate(reader.pages, 1):
            mb = page.mediabox
            if mb:
                w = float(mb.width)
                h = float(mb.height)
                lines.append(f"  第 {i} 页: {w:.1f} x {h:.1f} pt")

        return truncate("\n".join(lines))
    except Exception as e:
        return err(f"读取 PDF 信息失败: {e}")


def pdf_extract_text(file_path: str, start_page: int = 1, end_page: int = -1) -> str:
    """从 PDF 提取文本内容

    Args:
        file_path: PDF 文件路径
        start_page: 起始页码（1-indexed，默认 1）
        end_page: 结束页码（1-indexed，-1 表示到最后一页）
    """
    if not HAS_PYPDF:
        return err(_MISSING_DEPS_MSG)

    p = safe_path(file_path)
    if p is None:
        return err(f"无效路径: {file_path}")
    resolved = check_sandbox(p)
    if not resolved:
        return err(f"路径越权（仅允许项目目录和用户目录）: {file_path}")
    if not resolved.exists():
        return err(f"文件不存在: {resolved}")
    if not resolved.suffix.lower() == ".pdf":
        return err(f"不是 PDF 文件: {resolved}")

    try:
        reader = PdfReader(str(resolved))
        total = len(reader.pages)

        if start_page < 1:
            start_page = 1
        if end_page < 1 or end_page > total:
            end_page = total

        if start_page > total:
            return err(f"起始页 {start_page} 超出总页数 {total}")
        if start_page > end_page:
            return err(f"起始页 {start_page} 大于结束页 {end_page}")

        result_parts = []
        for i in range(start_page - 1, end_page):
            page = reader.pages[i]
            text = page.extract_text()
            if text and text.strip():
                result_parts.append(f"=== 第 {i + 1} 页 ===\n{text.strip()}")

        if not result_parts:
            return f"(PDF 共 {total} 页，指定范围内无可提取文本)"

        return truncate("\n\n".join(result_parts))
    except Exception as e:
        return err(f"提取文本失败: {e}")


def pdf_split(file_path: str, output_dir: str = "", pages_per_chunk: int = 1) -> str:
    """将 PDF 拆分为多个文件

    Args:
        file_path: PDF 文件路径
        output_dir: 输出目录（留空则使用源文件所在目录）
        pages_per_chunk: 每个分片的页数（默认 1，即每页一个文件）
    """
    if not HAS_PYPDF:
        return err(_MISSING_DEPS_MSG)

    p = safe_path(file_path)
    if p is None:
        return err(f"无效路径: {file_path}")
    resolved = check_sandbox(p)
    if not resolved:
        return err(f"路径越权（仅允许项目目录和用户目录）: {file_path}")
    if not resolved.exists():
        return err(f"文件不存在: {resolved}")
    if not resolved.suffix.lower() == ".pdf":
        return err(f"不是 PDF 文件: {resolved}")

    # 确定输出目录
    if output_dir:
        out_p = safe_path(output_dir)
        if out_p is None:
            return err(f"无效输出目录: {output_dir}")
        out_dir = check_sandbox(out_p)
        if not out_dir:
            return err(f"输出目录越权（仅允许项目目录和用户目录）: {output_dir}")
    else:
        out_dir = resolved.parent

    try:
        out_dir.mkdir(parents=True, exist_ok=True)

        reader = PdfReader(str(resolved))
        total = len(reader.pages)
        base_name = resolved.stem
        created = []

        if pages_per_chunk < 1:
            pages_per_chunk = 1

        chunk_idx = 0
        for i in range(0, total, pages_per_chunk):
            writer = PdfWriter()
            chunk_pages = []
            for j in range(i, min(i + pages_per_chunk, total)):
                writer.add_page(reader.pages[j])
                chunk_pages.append(j + 1)

            chunk_idx += 1
            if pages_per_chunk == 1:
                out_path = out_dir / f"{base_name}_第{chunk_pages[0]}页.pdf"
            else:
                out_path = out_dir / f"{base_name}_第{chunk_idx}部分_页{chunk_pages[0]}-{chunk_pages[-1]}.pdf"

            with open(out_path, "wb") as f:
                writer.write(f)
            created.append(str(out_path))

        return f"OK: 已将 PDF 拆分为 {len(created)} 个文件，保存到 {out_dir}\n" + "\n".join(f"  - {c}" for c in created)
    except Exception as e:
        return err(f"拆分 PDF 失败: {e}")


def pdf_merge(file_paths: list, output_path: str) -> str:
    """合并多个 PDF 文件为一个

    Args:
        file_paths: 要合并的 PDF 文件路径列表
        output_path: 输出 PDF 文件路径
    """
    if not HAS_PYPDF:
        return err(_MISSING_DEPS_MSG)

    if not file_paths:
        return err("file_paths 不能为空")
    if len(file_paths) < 2:
        return err("至少需要 2 个 PDF 文件才能合并")

    # 验证输出路径
    out_p = safe_path(output_path)
    if out_p is None:
        return err(f"无效输出路径: {output_path}")
    out_resolved = check_sandbox(out_p)
    if not out_resolved:
        return err(f"输出路径越权（仅允许项目目录和用户目录）: {output_path}")

    try:
        out_resolved.parent.mkdir(parents=True, exist_ok=True)

        writer = PdfWriter()
        added = []
        skipped = []

        for fp in file_paths:
            fp_str = str(fp)
            fp_p = safe_path(fp_str)
            if fp_p is None:
                skipped.append(f"{fp_str} (无效路径)")
                continue
            fp_resolved = check_sandbox(fp_p)
            if not fp_resolved:
                skipped.append(f"{fp_str} (越权)")
                continue
            if not fp_resolved.exists():
                skipped.append(f"{fp_str} (不存在)")
                continue
            if not fp_resolved.suffix.lower() == ".pdf":
                skipped.append(f"{fp_str} (非 PDF)")
                continue

            try:
                reader = PdfReader(str(fp_resolved))
                for page in reader.pages:
                    writer.add_page(page)
                added.append(fp_resolved.name)
            except Exception as e:
                skipped.append(f"{fp_resolved.name} (读取失败: {e})")

        if not added:
            return err("没有成功添加任何 PDF 文件")

        with open(out_resolved, "wb") as f:
            writer.write(f)

        lines = [f"OK: 已合并 {len(added)} 个 PDF 文件到 {out_resolved}"]
        lines.append(f"成功: {', '.join(added)}")
        if skipped:
            lines.append(f"跳过: {', '.join(skipped)}")
        return "\n".join(lines)
    except Exception as e:
        return err(f"合并 PDF 失败: {e}")


def pdf_rotate(file_path: str, rotation: int = 90, pages: str = "all") -> str:
    """旋转 PDF 页面

    Args:
        file_path: PDF 文件路径
        rotation: 旋转角度（90, 180, 270, -90）
        pages: 要旋转的页码，"all" 表示所有页，也可用逗号分隔如 "1,3,5"
    """
    if not HAS_PYPDF:
        return err(_MISSING_DEPS_MSG)

    if rotation not in (90, 180, 270, -90):
        return err(f"无效旋转角度: {rotation}，支持 90, 180, 270, -90")

    p = safe_path(file_path)
    if p is None:
        return err(f"无效路径: {file_path}")
    resolved = check_sandbox(p)
    if not resolved:
        return err(f"路径越权（仅允许项目目录和用户目录）: {file_path}")
    if not resolved.exists():
        return err(f"文件不存在: {resolved}")
    if not resolved.suffix.lower() == ".pdf":
        return err(f"不是 PDF 文件: {resolved}")

    # 解析页码范围
    try:
        if pages.strip().lower() == "all":
            page_set = None  # None = 全部
        else:
            page_set = set()
            for part in pages.split(","):
                part = part.strip()
                if "-" in part:
                    a, b = part.split("-", 1)
                    page_set.update(range(int(a), int(b) + 1))
                else:
                    page_set.add(int(part))
    except (ValueError, TypeError):
        return err(f"无效的页码范围: {pages}，格式如 'all' 或 '1,3,5' 或 '1-3,5-7'")

    try:
        reader = PdfReader(str(resolved))
        writer = PdfWriter()
        total = len(reader.pages)
        rotated = []

        for i in range(total):
            page = reader.pages[i]
            page_num = i + 1

            if page_set is None or page_num in page_set:
                page.rotate(rotation)
                rotated.append(page_num)

            writer.add_page(page)

        # 生成输出路径：在原文件名后加 _rotated
        out_path = resolved.parent / f"{resolved.stem}_rotated{rotation}.pdf"
        with open(out_path, "wb") as f:
            writer.write(f)

        if page_set is None:
            return f"OK: 已将全部 {total} 页旋转 {rotation}°，保存到 {out_path}"
        else:
            return f"OK: 已将第 {sorted(rotated)} 页旋转 {rotation}°，保存到 {out_path}"
    except Exception as e:
        return err(f"旋转 PDF 失败: {e}")


def pdf_edit_text(
    file_path: str,
    page: int,
    x: float,
    y: float,
    text: str,
    output_path: str = "",
    font_size: int = 12,
) -> str:
    """在 PDF 页面上叠加文本

    Args:
        file_path: PDF 文件路径
        page: 目标页码（1-indexed）
        x: X 坐标（从左起，单位 pt）
        y: Y 坐标（从下起，单位 pt）
        text: 要添加的文本
        output_path: 输出文件路径（留空则自动生成 _edited.pdf）
        font_size: 字体大小（默认 12）
    """
    if not HAS_PYPDF:
        return err(_MISSING_DEPS_MSG)
    if not HAS_REPORTLAB:
        return err(_MISSING_REPORTLAB_MSG)

    p = safe_path(file_path)
    if p is None:
        return err(f"无效路径: {file_path}")
    resolved = check_sandbox(p)
    if not resolved:
        return err(f"路径越权（仅允许项目目录和用户目录）: {file_path}")
    if not resolved.exists():
        return err(f"文件不存在: {resolved}")
    if not resolved.suffix.lower() == ".pdf":
        return err(f"不是 PDF 文件: {resolved}")

    # 确定输出路径
    if output_path:
        out_p = safe_path(output_path)
        if out_p is None:
            return err(f"无效输出路径: {output_path}")
        out_resolved = check_sandbox(out_p)
        if not out_resolved:
            return err(f"输出路径越权（仅允许项目目录和用户目录）: {output_path}")
    else:
        out_resolved = resolved.parent / f"{resolved.stem}_edited.pdf"

    try:
        out_resolved.parent.mkdir(parents=True, exist_ok=True)

        reader = PdfReader(str(resolved))
        total = len(reader.pages)

        if page < 1 or page > total:
            return err(f"页码 {page} 超出范围（共 {total} 页）")

        # 用 reportlab 创建文本 overlay
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        can.setFont("Helvetica", font_size)
        can.drawString(x, y, text)
        can.save()

        packet.seek(0)
        overlay_reader = PdfReader(packet)
        overlay_page = overlay_reader.pages[0]

        writer = PdfWriter()
        for i in range(total):
            p_page = reader.pages[i]
            if i == page - 1:
                p_page.merge_page(overlay_page)
            writer.add_page(p_page)

        with open(out_resolved, "wb") as f:
            writer.write(f)

        return f"OK: 已在第 {page} 页 ({x}, {y}) 处添加文本「{text}」，保存到 {out_resolved}"
    except Exception as e:
        return err(f"编辑 PDF 文本失败: {e}")


# ---- Schema 定义 ----

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "pdf_info",
            "description": "获取 PDF 元数据：页数、页面尺寸、作者、标题等信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "PDF 文件路径",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pdf_extract_text",
            "description": "从 PDF 提取文本内容，支持指定页码范围。1-indexed，end_page=-1 表示到最后一页",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "PDF 文件路径",
                    },
                    "start_page": {
                        "type": "integer",
                        "description": "起始页码（1-indexed，默认 1）",
                    },
                    "end_page": {
                        "type": "integer",
                        "description": "结束页码（1-indexed，-1 表示到最后一页，默认 -1）",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pdf_split",
            "description": "将 PDF 拆分为多个文件。默认每页一个文件，可通过 pages_per_chunk 调整每份页数",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "PDF 文件路径",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "输出目录（留空则使用源文件所在目录）",
                    },
                    "pages_per_chunk": {
                        "type": "integer",
                        "description": "每个分片的页数（默认 1）",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pdf_merge",
            "description": "合并多个 PDF 文件为一个。至少需要 2 个 PDF 文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要合并的 PDF 文件路径列表",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "输出 PDF 文件路径",
                    },
                },
                "required": ["file_paths", "output_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pdf_rotate",
            "description": "旋转 PDF 页面。支持旋转全部或指定页面，旋转后保存为新文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "PDF 文件路径",
                    },
                    "rotation": {
                        "type": "integer",
                        "description": "旋转角度：90, 180, 270, -90（默认 90）",
                    },
                    "pages": {
                        "type": "string",
                        "description": "要旋转的页码。'all' 表示全部，也可用逗号分隔如 '1,3,5' 或范围 '1-3,5-7'",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pdf_edit_text",
            "description": "在 PDF 页面上叠加文本（使用 reportlab 生成 overlay）。适合添加水印、标注等",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "PDF 文件路径",
                    },
                    "page": {
                        "type": "integer",
                        "description": "目标页码（1-indexed）",
                    },
                    "x": {
                        "type": "number",
                        "description": "X 坐标（从左起，单位 pt）",
                    },
                    "y": {
                        "type": "number",
                        "description": "Y 坐标（从下起，单位 pt）",
                    },
                    "text": {
                        "type": "string",
                        "description": "要添加的文本内容",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "输出文件路径（留空则自动生成 _edited.pdf）",
                    },
                    "font_size": {
                        "type": "integer",
                        "description": "字体大小（默认 12）",
                    },
                },
                "required": ["file_path", "page", "x", "y", "text"],
            },
        },
    },
]

HANDLERS = {
    "pdf_info": pdf_info,
    "pdf_extract_text": pdf_extract_text,
    "pdf_split": pdf_split,
    "pdf_merge": pdf_merge,
    "pdf_rotate": pdf_rotate,
    "pdf_edit_text": pdf_edit_text,
}


def register():
    """注册所有 PDF 工具函数到全局工具表"""
    for s in SCHEMAS:
        name = s["function"]["name"]
        register_tool(s, HANDLERS[name])
