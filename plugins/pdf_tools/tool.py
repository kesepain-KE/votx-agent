"""PDF 工具 — 信息 / 提取 / 拆分 / 合并 / 旋转 / 盖字 / 水印 / 预览 / 压缩 / OCR / 选页 / 删页 / 脱敏。



错误码: INVALID_PATH / FILE_NOT_FOUND / NOT_PDF / DEPENDENCY / SAVE_FAILED /

        PDF_ENCRYPTED / NO_TEXT_LAYER / OCR_FAILED / PAGE_OUT_OF_RANGE

"""

from __future__ import annotations



import json

import os

import re

import subprocess

from io import BytesIO

from pathlib import Path



from run.tool import register_tool

from plugins._common import err, truncate, safe_path, check_sandbox, get_current_user_dir

from plugins._common.artifacts import make_file_artifact, make_image_artifact, make_tool_result



# ──────── 依赖检测 ────────



try:

    from pypdf import PdfReader, PdfWriter

    HAS_PYPDF = True

except ImportError:

    PdfReader = PdfWriter = None

    HAS_PYPDF = False



try:

    from reportlab.pdfgen import canvas as rl_canvas

    from reportlab.lib.pagesizes import A4, letter

    from reportlab.lib.units import mm, inch

    from reportlab.lib.colors import HexColor, black, white, red

    HAS_REPORTLAB = True

except ImportError:

    rl_canvas = None

    A4 = letter = None

    mm = inch = None

    HexColor = black = white = red = None

    HAS_REPORTLAB = False



try:

    from PIL import Image

    HAS_PIL = True

except ImportError:

    Image = None

    HAS_PIL = False



_HAS_PDF2IMAGE = False

convert_from_path = None

try:

    from pdf2image import convert_from_path as _cfp  # noqa: F401

    convert_from_path = _cfp

    _HAS_PDF2IMAGE = True

except ImportError:

    pass



_HAS_TESSERACT = False

try:

    import pytesseract

    _HAS_TESSERACT = True

except ImportError:

    pytesseract = None



_HAS_NUMPY = False

try:

    import numpy as np

    _HAS_NUMPY = True

except ImportError:

    np = None  # type: ignore



_HAS_FITZ = False

try:

    import fitz  # PyMuPDF

    _HAS_FITZ = True

except ImportError:

    fitz = None  # type: ignore



# ──────── 错误码 ────────



def _ec(code: str, msg: str) -> str:

    return f"ERROR: [{code}] {msg}"





def _ok(message: str, artifacts: list[dict] | None = None, **extra) -> str:

    return make_tool_result(True, message, artifacts, **extra)



# ──────── 通用安全校验 ────────



def _resolve_input(path: str) -> Path | str:

    """校验输入路径：safe_path → check_sandbox → 是否存在 → 是否 .pdf。返回 Path 或错误字符串。"""

    if not HAS_PYPDF:

        return _ec("DEPENDENCY", "pypdf 未安装: pip install pypdf")

    pp = safe_path(path)

    if pp is None:

        return _ec("INVALID_PATH", f"路径无效: {path}")

    resolved = check_sandbox(pp)

    if not resolved:

        return _ec("INVALID_PATH", f"路径越权（仅允许项目目录和用户目录）: {path}")

    if not resolved.exists():

        return _ec("FILE_NOT_FOUND", f"文件不存在: {resolved}")

    if not resolved.suffix.lower() == ".pdf":

        return _ec("NOT_PDF", f"不是 PDF 文件: {resolved}")

    return resolved





def _resolve_output(output: str, default_dir: Path, default_stem: str,

                    overwrite: bool = False, auto_rename: bool = True,

                    suffix: str = ".pdf") -> Path | str:

    """校验/生成输出路径。返回 Path 或错误字符串。"""

    if output:

        op = safe_path(output)

        if op is None:

            return _ec("INVALID_PATH", f"输出路径无效: {output}")

        out = check_sandbox(op)

        if not out:

            return _ec("INVALID_PATH", f"输出路径越权: {output}")

    else:

        out = default_dir / f"{default_stem}{suffix}"



    out.parent.mkdir(parents=True, exist_ok=True)



    if out.exists():

        if overwrite:

            pass

        elif auto_rename:

            stem = out.stem

            ext = out.suffix

            for i in range(1, 1000):

                candidate = out.parent / f"{stem}_{i}{ext}"

                if not candidate.exists():

                    return candidate

            return _ec("SAVE_FAILED", f"无法生成不冲突文件名: {out}")

        else:

            return _ec("SAVE_FAILED", f"文件已存在: {out}（设置 overwrite=true 或 auto_rename=true）")



    return out





def _parse_pages(pages: str, total: int) -> set | str:

    """解析页码范围字符串，返回 set 或错误字符串。'all' → None 表示全部。"""

    if not pages or pages.strip().lower() == "all":

        return set()  # 空集表示全部

    try:

        result = set()

        for part in pages.split(","):

            part = part.strip()

            if not part:

                continue

            if "-" in part:

                a, b = part.split("-", 1)

                start, end = int(a), int(b)

                if start > end:

                    return _ec("INVALID_PATH", f"无效页码范围: {part}")

                for p in range(start, end + 1):

                    if p < 1 or p > total:

                        return _ec("PAGE_OUT_OF_RANGE", f"页码 {p} 超出范围（共 {total} 页）")

                    result.add(p)

            else:

                p = int(part)

                if p < 1 or p > total:

                    return _ec("PAGE_OUT_OF_RANGE", f"页码 {p} 超出范围（共 {total} 页）")

                result.add(p)

        return result if result else set()

    except (ValueError, TypeError):

        return _ec("INVALID_PATH", f"无效页码范围: {pages}，格式如 'all' 或 '1,3,5' 或 '1-3,5-7'")





def _add_page_break_markers(text: str, pages_text: list[str]) -> str:

    """为每页文本加分页标记。"""

    result: list[str] = []

    for i, t in enumerate(pages_text):

        if t and t.strip():

            result.append(f"=== 第 {i + 1} 页 ===\n{t.strip()}")

    return "\n\n".join(result)





_RESULT_TRUNCATE = int(os.environ.get("PDF_RESULT_TRUNCATE", "8000"))



# ──────── dry_run 辅助 ────────



def _dry_run_msg(tool: str, input_path: str, output_path: str = "",

                 pages: int = 0, **details) -> str:

    """统一 dry_run 返回格式。"""

    lines = [f"[DRY_RUN] {tool}", f"  input: {input_path}"]

    if output_path:

        lines.append(f"  output: {output_path}")

    if pages:

        lines.append(f"  pages: {pages}")

    for k, v in details.items():

        lines.append(f"  {k}: {v}")

    lines.append("  result: (未真正执行，dry_run=true)")

    return "\n".join(lines)



def _check_dry(dry_run: bool, tool: str, input_path: str,

               output_path: str = "", pages: int = 0, **details) -> str | None:

    """如果 dry_run=true，返回预览消息；否则返回 None 继续执行。"""

    if dry_run:

        return _dry_run_msg(tool, input_path, output_path, pages, **details)

    return None





# ──────── 1. pdf_info ────────



def pdf_info(file_path: str) -> str:

    """获取 PDF 详细信息：页数、尺寸、加密状态、文本层、图片数、书签、元数据。"""

    resolved = _resolve_input(file_path)

    if isinstance(resolved, str):

        return resolved



    try:

        reader = PdfReader(str(resolved))

        meta = reader.metadata or {}

        total = len(reader.pages)

        lines = [

            f"[PDF INFO] {resolved.name}",

            f"  path: {resolved}",

            f"  pages: {total}",

            f"  size: {resolved.stat().st_size:,} bytes ({resolved.stat().st_size / 1024:.1f} KB)",

            f"  encrypted: {reader.is_encrypted}",

        ]



        # 文本层 / 图片数

        has_text = False

        total_images = 0

        for page in reader.pages:

            if page.extract_text() and page.extract_text().strip():

                has_text = True

            try:

                if "/XObject" in page["/Resources"]:

                    for obj in page["/Resources"]["/XObject"].values():

                        if obj["/Subtype"] == "/Image":

                            total_images += 1

            except Exception:

                pass

        lines.append(f"  has_text_layer: {has_text}")

        lines.append(f"  total_images: {total_images}")



        # 是否有表单

        has_form = False

        try:

            if reader.get_fields():

                has_form = True

        except Exception:

            pass

        lines.append(f"  has_form: {has_form}")



        # 书签

        try:

            outlines = reader.outline

            if outlines:

                lines.append(f"  bookmarks: {len(outlines)} items")

        except Exception:

            lines.append("  bookmarks: unknown")



        # 元数据

        if meta:

            lines.append("  metadata:")

            for k in ("/Title", "/Author", "/Subject", "/Creator", "/Producer", "/CreationDate", "/ModDate"):

                v = meta.get(k)

                if v:

                    lines.append(f"    {k.lstrip('/').lower()}: {v}")



        # 页面尺寸（唯一尺寸汇总，不全列）

        sizes: dict[str, int] = {}

        for page in reader.pages:

            mb = page.mediabox

            if mb:

                key = f"{float(mb.width):.0f}x{float(mb.height):.0f}"

                sizes[key] = sizes.get(key, 0) + 1

        lines.append("  page_sizes:")

        for sz, cnt in sizes.items():

            w, h = sz.split("x")

            mm_w, mm_h = float(w) * 0.3528, float(h) * 0.3528

            lines.append(f"    {sz} pt ({mm_w:.0f}x{mm_h:.0f} mm) x {cnt} pages")



        return "\n".join(lines)

    except Exception as e:

        if "encrypted" in str(e).lower():

            return _ec("PDF_ENCRYPTED", f"PDF 已加密，无法读取: {e}")

        return _ec("SAVE_FAILED", f"读取 PDF 信息失败: {e}")





# ──────── 2. pdf_extract_text ────────



def pdf_extract_text(

    file_path: str,

    start_page: int = 1,

    end_page: int = -1,

    mode: str = "plain",

    include_page_breaks: bool = True,

    ocr_fallback: bool = False,

    language: str = "",

) -> str:

    """从 PDF 提取文本。mode=layout 尝试保留排版，ocr_fallback 在无文本层时自动 OCR。"""

    resolved = _resolve_input(file_path)

    if isinstance(resolved, str):

        return resolved



    try:

        reader = PdfReader(str(resolved))

        total = len(reader.pages)

        if start_page < 1: start_page = 1

        if end_page < 1 or end_page > total: end_page = total

        if start_page > total:

            return _ec("PAGE_OUT_OF_RANGE", f"起始页 {start_page} 超出总页数 {total}")

        if start_page > end_page:

            return _ec("PAGE_OUT_OF_RANGE", f"起始页 {start_page} > 结束页 {end_page}")



        result_parts: list[str] = []

        needs_ocr: list[int] = []



        for i in range(start_page - 1, end_page):

            page = reader.pages[i]

            text = ""

            if mode == "layout":

                try:

                    text = page.extract_text(extraction_mode="layout")

                except Exception:

                    text = page.extract_text()

            else:

                text = page.extract_text()



            if text and text.strip():

                if include_page_breaks:

                    result_parts.append(f"=== 第 {i + 1} 页 ===\n{text.strip()}")

                else:

                    result_parts.append(text.strip())

            elif ocr_fallback:

                needs_ocr.append(i + 1)



        # OCR fallback

        if needs_ocr and ocr_fallback:

            if not _HAS_PDF2IMAGE or not _HAS_TESSERACT:

                result_parts.insert(0, f"[!] {len(needs_ocr)} 页无文本层，需安装 pdf2image + pytesseract 进行 OCR")

            else:

                lang = language or "chi_sim+eng"

                for pg in needs_ocr:

                    try:

                        images = convert_from_path(str(resolved), first_page=pg, last_page=pg, dpi=200)

                        if images:

                            text = pytesseract.image_to_string(images[0], lang=lang)

                            if text.strip():

                                if include_page_breaks:

                                    result_parts.append(f"=== 第 {pg} 页 (OCR) ===\n{text.strip()}")

                                else:

                                    result_parts.append(text.strip())

                    except Exception as e:

                        result_parts.append(f"[!] 第 {pg} 页 OCR 失败: {e}")



        if not result_parts:

            return _ec("NO_MATCH", f"PDF 共 {total} 页，指定范围内无可提取文本。{'可开启 ocr_fallback=true 尝试 OCR' if not ocr_fallback else '文件可能是扫描版，建议用 pdf_ocr'}")



        return truncate("\n\n".join(result_parts), _RESULT_TRUNCATE)

    except Exception as e:

        return _ec("SAVE_FAILED", f"提取文本失败: {e}")





# ──────── 3. pdf_split ────────



def pdf_split(

    file_path: str,

    output_dir: str = "",

    pages_per_chunk: int = 1,

    page_ranges: str = "",

    name_pattern: str = "",

) -> str:

    """拆分 PDF。pages_per_chunk 按固定页数拆分，page_ranges 按指定范围拆分（如 1-3,5,8-10）。"""

    resolved = _resolve_input(file_path)

    if isinstance(resolved, str):

        return resolved



    od = output_dir or str(resolved.parent)

    out_d = safe_path(od)

    if out_d is None or check_sandbox(out_d) is None:

        return _ec("INVALID_PATH", f"输出目录越权: {od}")

    out_d.mkdir(parents=True, exist_ok=True)



    try:

        reader = PdfReader(str(resolved))

        total = len(reader.pages)

        base = resolved.stem

        created: list[str] = []



        # page_ranges 优先

        if page_ranges.strip():

            ranges_list = [x.strip() for x in page_ranges.split(",") if x.strip()]

            for idx, rng in enumerate(ranges_list):

                writer = PdfWriter()

                if "-" in rng:

                    a, b = rng.split("-", 1)

                    pgs = list(range(int(a), int(b) + 1))

                else:

                    pgs = [int(rng)]

                for pg in pgs:

                    if 1 <= pg <= total:

                        writer.add_page(reader.pages[pg - 1])

                nm = name_pattern or f"{base}_part{idx + 1}"

                out_path = out_d / f"{nm}.pdf"

                with open(out_path, "wb") as f:

                    writer.write(f)

                created.append(str(out_path))



        else:

            if pages_per_chunk < 1: pages_per_chunk = 1

            for i in range(0, total, pages_per_chunk):

                writer = PdfWriter()

                chunk_pgs = list(range(i + 1, min(i + pages_per_chunk, total) + 1))

                for j in range(i, min(i + pages_per_chunk, total)):

                    writer.add_page(reader.pages[j])

                nm = name_pattern or base

                if pages_per_chunk == 1:

                    out_path = out_d / f"{nm}_p{chunk_pgs[0]}.pdf"

                else:

                    out_path = out_d / f"{nm}_p{chunk_pgs[0]}-{chunk_pgs[-1]}.pdf"

                with open(out_path, "wb") as f:

                    writer.write(f)

                created.append(str(out_path))



        return _ok(

            "PDF 拆分完成",

            [make_file_artifact(p) for p in created],

            count=len(created),

            output_dir=str(out_d),

        )


    except Exception as e:

        return _ec("SAVE_FAILED", f"拆分失败: {e}")





# ──────── 4. pdf_merge ────────



def pdf_merge(
    file_paths: list,
    output_path: str,
    overwrite: bool = False,
    auto_rename: bool = True,
    remove_blank_pages: bool = False,
) -> str:
    """合并 PDF 文件，可选择跳过空白页。"""
    if not HAS_PYPDF:
        return _ec("DEPENDENCY", "pypdf 未安装")
    if not file_paths or len(file_paths) < 2:
        return _ec("INVALID_PATH", "至少需要 2 个 PDF 文件")

    out = _resolve_output(output_path, Path("."), "", overwrite, auto_rename)
    if isinstance(out, str):
        return out

    writer = PdfWriter()
    added: list[str] = []
    skipped: list[str] = []

    for fp in file_paths:
        r = _resolve_input(str(fp))
        if isinstance(r, str):
            skipped.append(f"{fp}: {r}")
            continue
        try:
            sub_reader = PdfReader(str(r))
            for page in sub_reader.pages:
                if remove_blank_pages and not (page.extract_text() or "").strip():
                    continue
                writer.add_page(page)
            added.append(r.name)
        except Exception as e:
            skipped.append(f"{r.name}: {e}")

    if not added:
        return _ec("SAVE_FAILED", "没有可合并的 PDF 文件")

    try:
        with open(out, "wb") as f:
            writer.write(f)
    except Exception as e:
        return _ec("SAVE_FAILED", f"合并失败: {e}")

    extra = {
        "merged": len(added),
        "pages": len(writer.pages),
        "skipped_count": len(skipped),
    }
    if skipped:
        extra["warnings"] = skipped[:5]
    return _ok("PDF 合并完成", [make_file_artifact(out)], **extra)


def pdf_rotate(

    file_path: str,

    rotation: int = 90,

    pages: str = "all",

    output_path: str = "",

    overwrite: bool = False,

    auto_rename: bool = True,

    dry_run: bool = False,

) -> str:

    """旋转 PDF 页面。支持 90/180/270/-90，可选择全部或指定页面。"""

    resolved = _resolve_input(file_path)

    if isinstance(resolved, str):

        return resolved



    if rotation not in (90, 180, 270, -90):

        return _ec("INVALID_PATH", f"无效旋转角度: {rotation}，支持 90, 180, 270, -90")



    out = _resolve_output(output_path, resolved.parent,

                          f"{resolved.stem}_rot{rotation}", overwrite, auto_rename)

    if isinstance(out, str):

        return out



    try:

        reader = PdfReader(str(resolved))

        writer = PdfWriter()

        total = len(reader.pages)

        page_set = _parse_pages(pages, total)

        if isinstance(page_set, str):

            return page_set

        select_all = not page_set  # 空集 = 全部



        selected_pages = total if select_all else len(page_set)

        dr = _check_dry(dry_run, "pdf_rotate", file_path, str(out), pages=selected_pages,

                        rotation=rotation, pages_selected=(pages if pages != "all" else "all"))

        if dr:

            return dr



        rotated: list[int] = []



        for i in range(total):

            page = reader.pages[i]

            pn = i + 1

            if select_all or pn in page_set:

                page.rotate(rotation)

                rotated.append(pn)

            writer.add_page(page)



        with open(out, "wb") as f:

            writer.write(f)
        return _ok("PDF 旋转完成", [make_file_artifact(out)], rotated=len(rotated), total=total, rotation=rotation)

    except Exception as e:

        return _ec("SAVE_FAILED", f"旋转失败: {e}")





# ──────── 6. pdf_stamp_text (原 pdf_edit_text) ────────



def pdf_stamp_text(

    file_path: str,

    page: int,

    x: float,

    y: float,

    text: str,

    output_path: str = "",

    overwrite: bool = False,

    auto_rename: bool = True,

    font_size: int = 12,

    font_color: str = "",

    opacity: float = 1.0,

    rotation: float = 0.0,

    max_width: float = 0.0,

    dry_run: bool = False,

) -> str:

    """在 PDF 页面上叠加文本（盖字/标注）。使用 reportlab 生成 overlay。



    坐标原点为左下角(bottom-left)，单位为 pt (1pt ≈ 0.3528mm)。

    """

    if not HAS_PYPDF:

        return _ec("DEPENDENCY", "pypdf 未安装")

    if not HAS_REPORTLAB:

        return _ec("DEPENDENCY", "reportlab 未安装: pip install reportlab")



    resolved = _resolve_input(file_path)

    if isinstance(resolved, str):

        return resolved



    out = _resolve_output(output_path, resolved.parent,

                          f"{resolved.stem}_stamped", overwrite, auto_rename)

    if isinstance(out, str):

        return out



    dr = _check_dry(dry_run, "pdf_stamp_text", file_path, str(out),

                    page=page, text=text[:30], x=x, y=y)

    if dr: return dr



    try:

        reader = PdfReader(str(resolved))

        total = len(reader.pages)

        if page < 1 or page > total:

            return _ec("PAGE_OUT_OF_RANGE", f"页码 {page} 超出范围（共 {total} 页）")



        # 获取目标页尺寸

        target_page = reader.pages[page - 1]

        pw = float(target_page.mediabox.width)

        ph = float(target_page.mediabox.height)



        packet = BytesIO()

        can = rl_canvas.Canvas(packet, pagesize=(pw, ph))



        # 颜色

        color = black

        if font_color:

            try:

                if font_color.startswith("#"):

                    color = HexColor(font_color)

                elif "," in font_color:

                    parts = [float(x.strip()) / 255 for x in font_color.split(",")]

                    color = HexColor("#" + "".join(f"{int(p * 255):02x}" for p in parts))

                else:

                    color = HexColor(font_color)

            except Exception:

                color = black



        # 透明度

        if opacity < 1.0:

            can.setFillColor(color.clone(alpha=opacity))

        else:

            can.setFillColor(color)



        can.setFont("Helvetica", font_size)



        # 旋转

        if rotation:

            can.rotate(rotation)



        # 绘制文本（支持自动换行）

        if max_width > 0 and len(text) * font_size * 0.5 > max_width:

            # 简单换行

            words = text

            can.drawString(x, y, text[:80])

        else:

            can.drawString(x, y, text)



        can.save()

        packet.seek(0)



        overlay_reader = PdfReader(packet)

        overlay_page = overlay_reader.pages[0]



        writer = PdfWriter()

        for i in range(total):

            pg = reader.pages[i]

            if i == page - 1:

                pg.merge_page(overlay_page)

            writer.add_page(pg)



        with open(out, "wb") as f:

            writer.write(f)
        return _ok("PDF 盖章完成", [make_file_artifact(out)], page=page, x=x, y=y, text=text[:30])

    except Exception as e:

        return _ec("SAVE_FAILED", f"盖字失败: {e}")





# ──────── 7. pdf_select_pages ────────



def pdf_select_pages(

    file_path: str,

    pages: str,

    output_path: str = "",

    overwrite: bool = False,

    auto_rename: bool = True,

    dry_run: bool = False,

) -> str:

    """抽取指定页面。pages='1,3,5-7'。"""

    resolved = _resolve_input(file_path)

    if isinstance(resolved, str):

        return resolved



    reader = PdfReader(str(resolved))

    total = len(reader.pages)

    page_set = _parse_pages(pages, total)

    if isinstance(page_set, str):

        return page_set

    if not page_set:

        return _ec("INVALID_PATH", "pages 不能为空或 'all'")



    out = _resolve_output(output_path, resolved.parent,

                          f"{resolved.stem}_selected", overwrite, auto_rename)

    if isinstance(out, str):

        return out



    selected = sorted(page_set)

    dr = _check_dry(dry_run, "pdf_select_pages", file_path, str(out),

                    pages=len(selected), selected=str(selected[:10]))

    if dr: return dr



    try:

        writer = PdfWriter()

        selected = sorted(page_set)

        for pn in selected:

            writer.add_page(reader.pages[pn - 1])



        with open(out, "wb") as f:

            writer.write(f)
        return _ok("PDF 选页完成", [make_file_artifact(out)], selected=len(selected), total=total, pages=selected[:20])

    except Exception as e:

        return _ec("SAVE_FAILED", f"抽取页面失败: {e}")





# ──────── 8. pdf_delete_pages ────────



def pdf_delete_pages(

    file_path: str,

    pages: str,

    output_path: str = "",

    overwrite: bool = False,

    auto_rename: bool = True,

    dry_run: bool = False,

) -> str:

    """删除指定页面。pages='1,3,5-7'。"""

    resolved = _resolve_input(file_path)

    if isinstance(resolved, str):

        return resolved



    reader = PdfReader(str(resolved))

    total = len(reader.pages)

    page_set = _parse_pages(pages, total)

    if isinstance(page_set, str):

        return page_set

    if not page_set:

        return _ec("INVALID_PATH", "pages 不能为空或 'all'")



    out = _resolve_output(output_path, resolved.parent,

                          f"{resolved.stem}_deleted", overwrite, auto_rename)

    if isinstance(out, str):

        return out



    dr = _check_dry(dry_run, "pdf_delete_pages", file_path, str(out),

                    delete_count=len(page_set), delete_pages=str(sorted(page_set)[:10]))

    if dr: return dr



    try:

        writer = PdfWriter()

        kept = []

        for i in range(total):

            pn = i + 1

            if pn not in page_set:

                writer.add_page(reader.pages[i])

                kept.append(pn)



        if not kept:

            return _ec("INVALID_PATH", "删除后没有剩余页面")



        with open(out, "wb") as f:

            writer.write(f)
        return _ok("PDF 删除页完成", [make_file_artifact(out)], deleted=len(page_set), kept=len(kept))

    except Exception as e:

        return _ec("SAVE_FAILED", f"删除页面失败: {e}")





# ──────── 9. pdf_compress ────────



def pdf_compress(

    file_path: str,

    output_path: str = "",

    overwrite: bool = False,

    auto_rename: bool = True,

    quality: str = "ebook",

    dry_run: bool = False,

) -> str:

    """压缩 PDF。quality 等级: screen(最小) / ebook(默认) / printer / prepress(最大)。"""

    resolved = _resolve_input(file_path)

    if isinstance(resolved, str):

        return resolved



    out = _resolve_output(output_path, resolved.parent,

                          f"{resolved.stem}_compressed", overwrite, auto_rename)

    if isinstance(out, str):

        return out



    dr = _check_dry(dry_run, "pdf_compress", file_path, str(out),

                    quality=quality, orig_size=resolved.stat().st_size)

    if dr: return dr



    # quality 等级 → ghostscript PDFSETTINGS

    _QUALITY_GS: dict[str, str] = {"screen": "/screen", "ebook": "/ebook", "printer": "/printer", "prepress": "/prepress"}

    pdf_settings = _QUALITY_GS.get(quality, "/ebook")



    # 优先使用 ghostscript

    if shutil_which("gs"):

        try:

            r = subprocess.run([

                "gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",

                f"-dPDFSETTINGS={pdf_settings}", "-dNOPAUSE", "-dQUIET", "-dBATCH",

                f"-sOutputFile={out}", str(resolved),

            ], capture_output=True, timeout=120)

            if r.returncode == 0:

                orig_size = resolved.stat().st_size

                new_size = out.stat().st_size

                ratio = (1 - new_size / orig_size) * 100 if orig_size > 0 else 0
                return _ok("PDF 压缩完成", [make_file_artifact(out)], method="ghostscript", orig_size=orig_size, new_size=new_size, ratio=ratio)

        except Exception:

            pass  # fallback to pypdf



    # pypdf 轻量压缩

    try:

        reader = PdfReader(str(resolved))

        writer = PdfWriter()

        for page in reader.pages:

            page.compress_content_streams()

            writer.add_page(page)



        with open(out, "wb") as f:

            writer.write(f)



        orig_size = resolved.stat().st_size

        new_size = out.stat().st_size

        ratio = (1 - new_size / orig_size) * 100 if orig_size > 0 else 0
        return _ok("PDF 压缩完成", [make_file_artifact(out)], method="pypdf", orig_size=orig_size, new_size=new_size, ratio=ratio)

    except Exception as e:

        return _ec("SAVE_FAILED", f"压缩失败: {e}")





# ──────── 10. pdf_watermark ────────



def pdf_watermark(

    file_path: str,

    text: str,

    output_path: str = "",

    overwrite: bool = False,

    auto_rename: bool = True,

    pages: str = "all",

    font_size: int = 40,

    opacity: float = 0.15,

    rotation: float = 45.0,

    dry_run: bool = False,

) -> str:

    """添加文字水印（斜铺半透明）。使用 reportlab 生成 overlay。"""

    if not HAS_PYPDF:

        return _ec("DEPENDENCY", "pypdf 未安装")

    if not HAS_REPORTLAB:

        return _ec("DEPENDENCY", "reportlab 未安装: pip install reportlab")



    resolved = _resolve_input(file_path)

    if isinstance(resolved, str):

        return resolved



    out = _resolve_output(output_path, resolved.parent,

                          f"{resolved.stem}_watermarked", overwrite, auto_rename)

    if isinstance(out, str):

        return out



    dr = _check_dry(dry_run, "pdf_watermark", file_path, str(out),

                    text=text, pages=pages)

    if dr: return dr



    try:

        reader = PdfReader(str(resolved))

        total = len(reader.pages)

        page_set = _parse_pages(pages, total)

        if isinstance(page_set, str):

            return page_set

        apply_all = not page_set



        writer = PdfWriter()

        for i in range(total):

            page = reader.pages[i]

            pn = i + 1

            if apply_all or pn in page_set:

                w = float(page.mediabox.width)

                h = float(page.mediabox.height)



                packet = BytesIO()

                can = rl_canvas.Canvas(packet, pagesize=(w, h))

                can.setFillColor(black)

                if opacity < 1.0:

                    can.setFillAlpha(opacity)

                can.setFont("Helvetica", font_size)

                can.rotate(rotation)

                # 铺满页面

                step_x, step_y = w * 0.4, h * 0.4

                for cx in range(-3, int(w / step_x) + 4):

                    for cy in range(-3, int(h / step_y) + 4):

                        can.drawString(cx * step_x, cy * step_y, text)

                can.save()

                packet.seek(0)



                ov_reader = PdfReader(packet)

                page.merge_page(ov_reader.pages[0])



            writer.add_page(page)



        with open(out, "wb") as f:

            writer.write(f)



        return _ok(

            "PDF 水印完成",

            [make_file_artifact(out)],

            text=text,

            pages=total,

        )

    except Exception as e:

        return _ec("SAVE_FAILED", f"水印失败: {e}")





# ──────── 11. pdf_render_preview ────────



def pdf_render_preview(

    file_path: str,

    output_dir: str = "",

    pages: str = "1",

    dpi: int = 150,

    image_format: str = "png",

) -> str:

    """渲染 PDF 页面为图片。需 pdf2image (poppler) + Pillow。"""

    resolved = _resolve_input(file_path)

    if isinstance(resolved, str):

        return resolved



    if not _HAS_PDF2IMAGE:

        return _ec("DEPENDENCY", "pdf2image 未安装: pip install pdf2image。还需系统安装 poppler-utils")

    if not HAS_PIL:

        return _ec("DEPENDENCY", "Pillow 未安装: pip install Pillow")



    reader = PdfReader(str(resolved))

    total = len(reader.pages)

    page_set = _parse_pages(pages, total)

    if isinstance(page_set, str):

        return page_set

    selected = sorted(page_set) if page_set else [1]

    if len(selected) > 10:

        return _ec("INVALID_PATH", f"预览最多 10 页，请求了 {len(selected)} 页")



    od = output_dir or str(resolved.parent)

    out_d = safe_path(od)

    if out_d is None or check_sandbox(out_d) is None:

        return _ec("INVALID_PATH", f"输出目录越权: {od}")

    out_d.mkdir(parents=True, exist_ok=True)



    fmt = image_format if image_format in ("png", "jpg", "jpeg") else "png"

    created: list[str] = []



    try:

        for pg in selected:

            images = convert_from_path(str(resolved), dpi=dpi, first_page=pg, last_page=pg)

            if not images:

                return _ec("SAVE_FAILED", f"页面 {pg} 渲染为空")

            img = images[0]

            out_path = out_d / f"{resolved.stem}_p{pg}.{fmt}"

            img.save(str(out_path), fmt.upper() if fmt != "jpg" else "JPEG")

            created.append(str(out_path))
        return _ok("PDF 预览完成", [make_image_artifact(p) for p in created], pages=len(created), dpi=dpi, output_dir=str(out_d))

    except Exception as e:

        return _ec("SAVE_FAILED", f"渲染预览失败: {e}")





# ──────── 12. pdf_ocr ────────



def pdf_ocr(

    file_path: str,

    output_path: str = "",

    overwrite: bool = False,

    auto_rename: bool = True,

    language: str = "chi_sim+eng",

    pages: str = "all",

    dpi: int = 200,

    force_ocr: bool = False,

    skip_text: bool = True,

    deskew: bool = False,

    dry_run: bool = False,

) -> str:

    """对扫描版 PDF 进行 OCR，输出含文本层的新 PDF。需 pdf2image + pytesseract。



    force_ocr: 即使有文本层也重新 OCR。skip_text: 有文本层则跳过该页。deskew: 自动纠偏。"""

    resolved = _resolve_input(file_path)

    if isinstance(resolved, str):

        return resolved



    if not _HAS_PDF2IMAGE:

        return _ec("DEPENDENCY", "pdf2image 未安装: pip install pdf2image")

    if not _HAS_TESSERACT:

        return _ec("DEPENDENCY", "pytesseract 未安装: pip install pytesseract")

    if not HAS_PIL:

        return _ec("DEPENDENCY", "Pillow 未安装: pip install Pillow")



    out = _resolve_output(output_path, resolved.parent,

                          f"{resolved.stem}_ocr", overwrite, auto_rename)

    if isinstance(out, str):

        return out



    dr = _check_dry(dry_run, "pdf_ocr", file_path, str(out),

                    language=language, pages=pages, force_ocr=force_ocr)

    if dr: return dr



    try:

        reader = PdfReader(str(resolved))

        total = len(reader.pages)

        page_set = _parse_pages(pages, total)

        if isinstance(page_set, str):

            return page_set

        apply_all = not page_set



        # 渲染需要处理的页面为图片 → OCR → 按原页码叠加文本层。

        from reportlab.pdfgen import canvas as ocr_canvas



        ocr_overlays: dict[int, object] = {}

        ocr_pages_processed = 0



        for i in range(total):

            pn = i + 1

            if not apply_all and pn not in page_set:

                continue



            # skip_text: 检查是否已有文本层

            if skip_text and not force_ocr:

                existing = reader.pages[i].extract_text()

                if existing and existing.strip():

                    continue



            images = convert_from_path(str(resolved), first_page=pn, last_page=pn, dpi=dpi)

            if not images:

                continue



            img = images[0]

            text = pytesseract.image_to_string(img, lang=language)



            # 创建含 OCR 文本的页面

            w_pt = float(reader.pages[i].mediabox.width)

            h_pt = float(reader.pages[i].mediabox.height)



            page_packet = BytesIO()

            c = ocr_canvas.Canvas(page_packet, pagesize=(w_pt, h_pt))

            c.setFont("Helvetica", 8)

            y_pos = h_pt - 20

            for line in text.split("\n"):

                if y_pos < 20:

                    c.showPage()

                    c.setFont("Helvetica", 8)

                    y_pos = h_pt - 20

                c.drawString(20, y_pos, line[:120])

                y_pos -= 10

            c.save()



            page_packet.seek(0)

            overlay_reader = PdfReader(page_packet)

            if overlay_reader.pages:

                ocr_overlays[pn] = overlay_reader.pages[0]

            ocr_pages_processed += 1



        if ocr_pages_processed == 0:

            return _ec("SAVE_FAILED", "没有页面被 OCR 处理")



        writer = PdfWriter()

        for i in range(total):

            pg = reader.pages[i]

            pn = i + 1

            overlay = ocr_overlays.get(pn)

            if overlay is not None:

                pg.merge_page(overlay)

            writer.add_page(pg)



        with open(out, "wb") as f:

            writer.write(f)



        return _ok(

            "PDF OCR 完成",

            [make_file_artifact(out)],

            ocr_pages=ocr_pages_processed,

            language=language,

        )

    except Exception as e:

        return _ec("OCR_FAILED", f"OCR 失败: {e}")





# ──────── 13. pdf_redact ────────



def pdf_redact(

    file_path: str,

    output_path: str = "",

    keywords: str = "",

    rectangles: str = "",

    regex: bool = False,

    case_sensitive: bool = True,

    overwrite: bool = False,

    auto_rename: bool = True,

    dry_run: bool = False,

) -> str:

    """真实脱敏：用 PyMuPDF 添加并应用 redaction annotation。



    keywords: 逗号分隔的关键词或原生数组。当前仅支持字面量搜索，不支持正则。

    rectangles: JSON 数组坐标，如 [{"x0":100,"y0":100,"x1":300,"y1":120,"page":1}]。

    坐标原点为左下角(bottom-left)，单位 pt。

    """

    if not HAS_PYPDF:

        return _ec("DEPENDENCY", "pypdf 未安装")



    resolved = _resolve_input(file_path)

    if isinstance(resolved, str):

        return resolved



    out = _resolve_output(output_path, resolved.parent,

                          f"{resolved.stem}_redacted", overwrite, auto_rename)

    if isinstance(out, str):

        return out



    # keywords: 原生数组 [str, ...] 或兼容旧逗号字符串

    if isinstance(keywords, list):

        kw_list = [str(k).strip() for k in keywords if str(k).strip()]

    elif isinstance(keywords, str):

        kw_list = [k.strip() for k in keywords.split(",") if k.strip()]

    else:

        kw_list = []



    # rectangles: 原生数组 [{page,x0,y0,x1,y1}, ...] 或兼容旧 JSON 字符串

    rect_list = []

    if isinstance(rectangles, list):

        rect_list = rectangles

    elif isinstance(rectangles, str) and rectangles.strip():

        try:

            rect_list = json.loads(rectangles)

        except json.JSONDecodeError:

            return _ec("INVALID_PATH", f"rectangles 不是合法 JSON: {rectangles}")

    if isinstance(rect_list, dict):

        rect_list = [rect_list]



    if not kw_list and not rect_list:

        return _ec("NO_MATCH", "keywords 或 rectangles 至少提供一个，且不能为空")

    if regex:

        return _ec("INVALID_PATH", "PyMuPDF 关键词脱敏当前不支持 regex=true，请使用字面关键词或坐标 rectangles")

    if kw_list and not case_sensitive:

        return _ec("INVALID_PATH", "case_sensitive=false 暂不支持可靠关键词坐标定位，请使用精确大小写关键词或 rectangles")

    if not _HAS_FITZ:

        return _ec("DEPENDENCY", "PyMuPDF 未安装: pip install PyMuPDF")



    dr = _check_dry(dry_run, "pdf_redact", file_path, str(out),

                    keywords_count=len(kw_list), rectangles_count=len(rect_list),

                    regex=regex, case_sensitive=case_sensitive)

    if dr: return dr



    if out == resolved:

        return _ec("INVALID_PATH", "pdf_redact 不支持原地覆盖，请指定不同的 output_path")



    try:

        doc = fitz.open(str(resolved))

        redacted_count = 0



        for page_index in range(len(doc)):

            page = doc[page_index]

            page_changed = False



            for kw in kw_list:

                flags = 0

                if hasattr(fitz, "TEXT_DEHYPHENATE"):

                    flags |= fitz.TEXT_DEHYPHENATE

                matches = page.search_for(kw, flags=flags)

                for rect in matches:

                    page.add_redact_annot(rect, fill=(0, 0, 0))

                    redacted_count += 1

                    page_changed = True



            # 坐标涂黑

            for rect in rect_list:

                r_page = rect.get("page", 1)

                if r_page != page_index + 1:

                    continue

                try:

                    x0, y0 = float(rect.get("x0", 0)), float(rect.get("y0", 0))

                    x1, y1 = float(rect.get("x1", 100)), float(rect.get("y1", 100))

                    if x1 <= x0 or y1 <= y0:

                        return _ec("INVALID_PATH", f"无效矩形坐标: {rect}")

                    height = float(page.rect.height)

                    page_rect = fitz.Rect(x0, height - y1, x1, height - y0)

                    page.add_redact_annot(page_rect, fill=(0, 0, 0))

                    redacted_count += 1

                    page_changed = True

                except (TypeError, ValueError):

                    return _ec("INVALID_PATH", f"无效矩形坐标: {rect}")



            if page_changed:

                page.apply_redactions()



        if redacted_count == 0:

            doc.close()

            return _ec("NO_MATCH", "未找到可脱敏的关键词或坐标区域")



        doc.save(str(out), garbage=4, deflate=True, clean=True)

        doc.close()



        details = [f"keywords: {len(kw_list)}", f"rectangles: {len(rect_list)}",

                   f"regex: {regex}", f"case_sensitive: {case_sensitive}"]



        return _ok(

            "PDF 脱敏完成",

            [make_file_artifact(out)],

            redacted=redacted_count,

            keywords=len(kw_list),

            rectangles=len(rect_list),

            regex=regex,

            case_sensitive=case_sensitive,

        )

    except Exception as e:

        return _ec("SAVE_FAILED", f"涂黑失败: {e}")





# ──────── 辅助 ────────



def shutil_which(cmd: str) -> bool:

    """检查命令是否存在。"""

    import shutil

    return shutil.which(cmd) is not None





# ──────── 14. pdf_compare ────────



def pdf_compare(

    before_path: str,

    after_path: str,

    output_dir: str = "",

    pages: str = "all",

    dpi: int = 150,

    threshold: float = 0.05,

) -> str:

    """视觉对比两个 PDF，生成差异图片。需 pdf2image + Pillow。



    逐页渲染为图片，计算像素级差异，差异区域红色高亮。

    threshold 为差异判定阈值（0-1，默认 0.05 即 5% 像素变化视为差异）。

    """

    if not _HAS_PDF2IMAGE:

        return _ec("DEPENDENCY", "pdf2image 未安装: pip install pdf2image")

    if not HAS_PIL:

        return _ec("DEPENDENCY", "Pillow 未安装: pip install Pillow")



    before_r = _resolve_input(before_path)

    if isinstance(before_r, str):

        return before_r

    after_r = _resolve_input(after_path)

    if isinstance(after_r, str):

        return after_r



    od = output_dir or str(before_r.parent)

    out_d = safe_path(od)

    if out_d is None or check_sandbox(out_d) is None:

        return _ec("INVALID_PATH", f"输出目录越权: {od}")

    out_d.mkdir(parents=True, exist_ok=True)



    try:

        reader_b = PdfReader(str(before_r))

        reader_a = PdfReader(str(after_r))

        total_b = len(reader_b.pages)

        total_a = len(reader_a.pages)



        page_set_b = _parse_pages(pages, total_b)

        if isinstance(page_set_b, str):

            return page_set_b



        lines = [f"[PDF COMPARE]",

                 f"  before: {before_r.name} ({total_b} pages)",

                 f"  after:  {after_r.name} ({total_a} pages)"]



        if total_b != total_a:

            lines.append(f"  warning: 页数不同 ({total_b} vs {total_a})")



        # 取两文件中页数较小的

        max_pages = min(total_b, total_a)

        compare_pages = sorted(page_set_b) if page_set_b else list(range(1, max_pages + 1))

        if len(compare_pages) > 20:

            return _ec("INVALID_PATH", f"对比最多 20 页，请求了 {len(compare_pages)} 页")



        diff_files: list[str] = []

        total_diff_pixels = 0

        for pn in compare_pages:

            if pn > max_pages:

                continue



            imgs_b = convert_from_path(str(before_r), first_page=pn, last_page=pn, dpi=dpi)

            imgs_a = convert_from_path(str(after_r), first_page=pn, last_page=pn, dpi=dpi)

            if not imgs_b or not imgs_a:

                continue



            img_b = imgs_b[0].convert("RGB")

            img_a = imgs_a[0].convert("RGB")



            # 统一尺寸

            if img_b.size != img_a.size:

                img_a = img_a.resize(img_b.size, Image.LANCZOS)



            # 像素级差异

            import numpy as np

            arr_b = np.array(img_b, dtype=np.float32)

            arr_a = np.array(img_a, dtype=np.float32)

            diff = np.abs(arr_b - arr_a)

            diff_mask = np.max(diff, axis=2) > (threshold * 255)

            diff_pixels = int(np.sum(diff_mask))

            total_diff_pixels += diff_pixels



            # 生成差异图：差异区域红色

            diff_img = img_b.copy()

            if diff_pixels > 0:

                red_overlay = Image.new("RGBA", img_b.size, (255, 0, 0, 100))

                mask_img = Image.fromarray((diff_mask * 255).astype(np.uint8))

                diff_img.paste(red_overlay, mask=mask_img)



            total_pixels = img_b.size[0] * img_b.size[1]

            ratio = diff_pixels / total_pixels * 100 if total_pixels > 0 else 0



            out_path = out_d / f"diff_p{pn}.png"

            diff_img.save(str(out_path))

            diff_files.append(str(out_path))

            lines.append(f"  page {pn}: {diff_pixels} diff pixels ({ratio:.1f}%)")



        lines.append(f"  total_diff: {total_diff_pixels} pixels")

        lines.append(f"  output: {len(diff_files)} diff images → {out_d}")



        return _ok(

            "PDF 对比完成",

            [make_image_artifact(p) for p in diff_files],

            pages=len(diff_files),

            total_diff_pixels=total_diff_pixels,

            output_dir=str(out_d),

        )

        return "\n".join(lines)



    except ImportError:

        return _ec("DEPENDENCY", "numpy 未安装: pip install numpy")

    except Exception as e:

        return _ec("SAVE_FAILED", f"对比失败: {e}")





# ──────── 15. check_pdf_dependencies ────────



def check_pdf_dependencies() -> str:

    """检测 PDF 工具链依赖状态。返回各组件可用性报告。"""

    lines = ["[PDF DEPENDENCIES]"]



    checks = [

        ("pypdf", HAS_PYPDF, "pip install pypdf"),

        ("PyMuPDF", _HAS_FITZ, "pip install PyMuPDF"),

        ("reportlab", HAS_REPORTLAB, "pip install reportlab"),

        ("Pillow", HAS_PIL, "pip install Pillow"),

        ("pdf2image", _HAS_PDF2IMAGE, "pip install pdf2image and add Poppler to PATH"),

        ("pytesseract", _HAS_TESSERACT, "pip install pytesseract and add Tesseract to PATH"),

        ("numpy", _HAS_NUMPY, "pip install numpy"),

    ]



    for name, ok, hint in checks:

        status = "ok" if ok else f"missing ({hint})"

        lines.append(f"  {name}: {status}")



    # 检查系统级依赖

    import shutil

    lines.append("")

    lines.append("[SYSTEM DEPENDENCIES]")



    sys_checks = [

        ("ghostscript", shutil.which("gs") or shutil.which("gswin64c") or shutil.which("gswin32c")),

        ("tesseract", shutil.which("tesseract")),

        ("poppler (pdftoppm)", shutil.which("pdftoppm")),

        ("libreoffice", shutil.which("libreoffice") or shutil.which("soffice")),

    ]

    for name, path in sys_checks:

        status = f"ok ({path})" if path else "missing"

        lines.append(f"  {name}: {status}")



    # 能力总结

    lines.append("")

    lines.append("[CAPABILITIES]")

    caps = [

        ("basic (info/extract/split/merge/rotate/select/delete)", HAS_PYPDF),

        ("stamp/watermark", HAS_PYPDF and HAS_REPORTLAB),

        ("compress (ghostscript)", HAS_PYPDF and bool(shutil.which("gs") or shutil.which("gswin64c"))),

        ("compress (pypdf fallback)", HAS_PYPDF),

        ("preview", HAS_PYPDF and _HAS_PDF2IMAGE and HAS_PIL),

        ("OCR", HAS_PYPDF and _HAS_PDF2IMAGE and _HAS_TESSERACT and HAS_PIL and bool(shutil.which("tesseract"))),

        ("compare (visual diff)", HAS_PYPDF and _HAS_PDF2IMAGE and HAS_PIL and _HAS_NUMPY),

        ("redact (true removal)", HAS_PYPDF and _HAS_FITZ),

    ]

    for name, ok in caps:

        lines.append(f"  {name}: {'ok' if ok else 'missing deps'}")



    return "\n".join(lines)





# ──────── 注册 ────────



SCHEMAS = [

    # 1

    {

        "type": "function", "function": {

            "name": "pdf_info",

            "description": "获取 PDF 详细信息：页数、尺寸、加密状态、文本层、图片数、书签、元数据、是否有表单",

            "parameters": {

                "type": "object",

                "properties": {"file_path": {"type": "string", "description": "PDF 文件路径（必填）"}},

                "required": ["file_path"],

            },

        },

    },

    # 2

    {

        "type": "function", "function": {

            "name": "pdf_extract_text",

            "description": "从 PDF 提取文本。支持 layout 模式保留排版、ocr_fallback 自动 OCR 扫描件",

            "parameters": {

                "type": "object",

                "properties": {

                    "file_path": {"type": "string", "description": "PDF 文件路径（必填）"},

                    "start_page": {"type": "integer", "description": "起始页码（1-indexed，默认 1）"},

                    "end_page": {"type": "integer", "description": "结束页码（-1=最后一页，默认 -1）"},

                    "mode": {"type": "string", "enum": ["plain", "layout"], "description": "提取模式：plain 纯文本 / layout 保留排版"},

                    "include_page_breaks": {"type": "boolean", "description": "是否在每页间插入分页标记，默认 true"},

                    "ocr_fallback": {"type": "boolean", "description": "无文本层时是否自动 OCR（需 pdf2image+pytesseract）"},

                    "language": {"type": "string", "description": "OCR 语言，如 chi_sim+eng。默认 chi_sim+eng"},

                },

                "required": ["file_path"],

            },

        },

    },

    # 3

    {

        "type": "function", "function": {

            "name": "pdf_split",

            "description": "拆分 PDF。按固定页数(pages_per_chunk)或指定范围(page_ranges='1-3,5,8-10')",

            "parameters": {

                "type": "object",

                "properties": {

                    "file_path": {"type": "string", "description": "PDF 文件路径（必填）"},

                    "output_dir": {"type": "string", "description": "输出目录（留空用源文件目录）"},

                    "pages_per_chunk": {"type": "integer", "description": "每份页数（默认 1）"},

                    "page_ranges": {"type": "string", "description": "按范围拆分，如 1-3,5,8-10（优先于 pages_per_chunk）"},

                    "name_pattern": {"type": "string", "description": "输出文件命名前缀"},

                },

                "required": ["file_path"],

            },

        },

    },

    # 4

    {

        "type": "function", "function": {

            "name": "pdf_merge",

            "description": "合并多个 PDF。自动跳过无效文件，支持去除空白页",

            "parameters": {

                "type": "object",

                "properties": {

                    "file_paths": {"type": "array", "items": {"type": "string"}, "description": "PDF 文件路径列表（至少 2 个）"},

                    "output_path": {"type": "string", "description": "输出文件路径（必填）"},

                    "overwrite": {"type": "boolean", "description": "是否覆盖已有文件，默认 false"},

                    "auto_rename": {"type": "boolean", "description": "重名时自动追加序号，默认 true"},

                    "remove_blank_pages": {"type": "boolean", "description": "是否移除空白页，默认 false"},

                },

                "required": ["file_paths", "output_path"],

            },

        },

    },

    # 5

    {

        "type": "function", "function": {

            "name": "pdf_rotate",

            "description": "旋转 PDF 页面（90/180/270/-90 度），支持全部或指定页面",

            "parameters": {

                "type": "object",

                "properties": {

                    "file_path": {"type": "string", "description": "PDF 文件路径（必填）"},

                    "rotation": {"type": "integer", "description": "旋转角度：90, 180, 270, -90（默认 90）"},

                    "pages": {"type": "string", "description": "页码范围：'all'(全部) 或 '1,3,5' 或 '1-3,5-7'"},

                    "output_path": {"type": "string", "description": "输出路径（留空自动生成 *_rot90.pdf）"},

                    "overwrite": {"type": "boolean", "description": "是否覆盖"},

                    "auto_rename": {"type": "boolean", "description": "重名时自动追加序号，默认 true"},

                    "dry_run": {"type": "boolean", "description": "只预览不执行"},

                },

                "required": ["file_path"],

            },

        },

    },

    # 6

    {

        "type": "function", "function": {

            "name": "pdf_stamp_text",

            "description": "在 PDF 页面上叠加文本（盖字/标注）。支持颜色、透明度、旋转角度。坐标原点为左下角，单位 pt",

            "parameters": {

                "type": "object",

                "properties": {

                    "file_path": {"type": "string", "description": "PDF 文件路径（必填）"},

                    "page": {"type": "integer", "description": "目标页码，1-indexed（必填）"},

                    "x": {"type": "number", "description": "X 坐标（从左起，pt）。72pt≈1英寸≈2.54cm（必填）"},

                    "y": {"type": "number", "description": "Y 坐标（从下起，pt）（必填）"},

                    "text": {"type": "string", "description": "要添加的文本（必填）"},

                    "output_path": {"type": "string", "description": "输出路径（留空自动生成 *_stamped.pdf）"},

                    "overwrite": {"type": "boolean", "description": "是否覆盖"},

                    "auto_rename": {"type": "boolean", "description": "重名时自动追加序号，默认 true"},

                    "font_size": {"type": "integer", "description": "字号（pt），默认 12"},

                    "font_color": {"type": "string", "description": "颜色：#RRGGBB / r,g,b(0-255)格式。默认黑色"},

                    "opacity": {"type": "number", "description": "透明度 0-1。默认 1.0（不透明）"},

                    "rotation": {"type": "number", "description": "文字旋转角度（度）。默认 0"},

                    "max_width": {"type": "number", "description": "最大宽度（pt），超出自动换行。0=不换行"},

                    "dry_run": {"type": "boolean", "description": "只预览不执行"},

                },

                "required": ["file_path", "page", "x", "y", "text"],

            },

        },

    },

    # 7

    {

        "type": "function", "function": {

            "name": "pdf_select_pages",

            "description": "抽取指定页面生成新 PDF。pages='1,3,5-7'",

            "parameters": {

                "type": "object",

                "properties": {

                    "file_path": {"type": "string", "description": "PDF 文件路径（必填）"},

                    "pages": {"type": "string", "description": "页码范围：'1,3,5' 或 '1-3,5-7'（必填）"},

                    "output_path": {"type": "string", "description": "输出路径（留空自动生成 *_selected.pdf）"},

                    "overwrite": {"type": "boolean", "description": "是否覆盖"},

                    "auto_rename": {"type": "boolean", "description": "重名时自动追加序号，默认 true"},

                    "dry_run": {"type": "boolean", "description": "只预览不执行"},

                },

                "required": ["file_path", "pages"],

            },

        },

    },

    # 8

    {

        "type": "function", "function": {

            "name": "pdf_delete_pages",

            "description": "删除指定页面。pages='1,3,5-7'",

            "parameters": {

                "type": "object",

                "properties": {

                    "file_path": {"type": "string", "description": "PDF 文件路径（必填）"},

                    "pages": {"type": "string", "description": "要删除的页码范围：'1,3,5' 或 '1-3,5-7'（必填）"},

                    "output_path": {"type": "string", "description": "输出路径（留空自动生成 *_deleted.pdf）"},

                    "overwrite": {"type": "boolean", "description": "是否覆盖"},

                    "auto_rename": {"type": "boolean", "description": "重名时自动追加序号，默认 true"},

                    "dry_run": {"type": "boolean", "description": "只预览不执行"},

                },

                "required": ["file_path", "pages"],

            },

        },

    },

    # 9

    {

        "type": "function", "function": {

            "name": "pdf_compress",

            "description": "压缩 PDF。优先 ghostscript，回退 pypdf。quality 等级: screen(最小)/ebook(默认)/printer/prepress(最大)",

            "parameters": {

                "type": "object",

                "properties": {

                    "file_path": {"type": "string", "description": "PDF 文件路径（必填）"},

                    "output_path": {"type": "string", "description": "输出路径（留空自动生成 *_compressed.pdf）"},

                    "overwrite": {"type": "boolean", "description": "是否覆盖"},

                    "auto_rename": {"type": "boolean", "description": "重名时自动追加序号，默认 true"},

                    "quality": {"type": "string", "enum": ["screen", "ebook", "printer", "prepress"], "description": "压缩等级：screen 最小 / ebook 默认 / printer / prepress 最大"},

                    "dry_run": {"type": "boolean", "description": "只预览不执行"},

                },

                "required": ["file_path"],

            },

        },

    },

    # 10

    {

        "type": "function", "function": {

            "name": "pdf_watermark",

            "description": "添加文字水印（斜铺半透明）。适合添加「草稿」「机密」「仅供学习」等",

            "parameters": {

                "type": "object",

                "properties": {

                    "file_path": {"type": "string", "description": "PDF 文件路径（必填）"},

                    "text": {"type": "string", "description": "水印文字（必填），如 草稿、机密"},

                    "output_path": {"type": "string", "description": "输出路径（留空自动生成 *_watermarked.pdf）"},

                    "overwrite": {"type": "boolean", "description": "是否覆盖"},

                    "auto_rename": {"type": "boolean", "description": "重名时自动追加序号，默认 true"},

                    "pages": {"type": "string", "description": "页码范围，'all' 或 '1,3,5-7'。默认 all"},

                    "font_size": {"type": "integer", "description": "水印字号，默认 40"},

                    "opacity": {"type": "number", "description": "透明度 0-1。默认 0.15（半透明）"},

                    "rotation": {"type": "number", "description": "水印倾斜角度（度），默认 45"},

                    "dry_run": {"type": "boolean", "description": "只预览不执行"},

                },

                "required": ["file_path", "text"],

            },

        },

    },

    # 11

    {

        "type": "function", "function": {

            "name": "pdf_render_preview",

            "description": "渲染 PDF 页面为图片（PNG/JPG）。需 pdf2image(poppler)+Pillow。最多 10 页",

            "parameters": {

                "type": "object",

                "properties": {

                    "file_path": {"type": "string", "description": "PDF 文件路径（必填）"},

                    "output_dir": {"type": "string", "description": "输出目录（留空用源文件目录）"},

                    "pages": {"type": "string", "description": "页码范围，默认 '1'（第一页）。最多 10 页"},

                    "dpi": {"type": "integer", "description": "渲染 DPI，默认 150"},

                    "image_format": {"type": "string", "enum": ["png", "jpg"], "description": "图片格式，默认 png"},

                },

                "required": ["file_path"],

            },

        },

    },

    # 12

    {

        "type": "function", "function": {

            "name": "pdf_ocr",

            "description": "对扫描版 PDF 进行 OCR，输出含文本层的新 PDF。需 pdf2image+pytesseract。支持跳过有文本层的页面",

            "parameters": {

                "type": "object",

                "properties": {

                    "file_path": {"type": "string", "description": "PDF 文件路径（必填）"},

                    "output_path": {"type": "string", "description": "输出路径（留空自动生成 *_ocr.pdf）"},

                    "overwrite": {"type": "boolean", "description": "是否覆盖"},

                    "auto_rename": {"type": "boolean", "description": "重名时自动追加序号，默认 true"},

                    "language": {"type": "string", "description": "OCR 语言，默认 chi_sim+eng"},

                    "pages": {"type": "string", "description": "页码范围，默认 all"},

                    "dpi": {"type": "integer", "description": "渲染 DPI，默认 200"},

                    "force_ocr": {"type": "boolean", "description": "即使有文本层也重新 OCR。默认 false"},

                    "skip_text": {"type": "boolean", "description": "有文本层则跳过该页。默认 true"},

                    "deskew": {"type": "boolean", "description": "自动纠偏。默认 false"},

                    "dry_run": {"type": "boolean", "description": "只预览不执行"},

                },

                "required": ["file_path"],

            },

        },

    },

    # 13

    {

        "type": "function", "function": {

            "name": "pdf_redact",

            "description": "真实脱敏：用 PyMuPDF 删除关键词或坐标区域并覆盖黑块。用于删除姓名/手机号/身份证号/地址/API key",

            "parameters": {

                "type": "object",

                "properties": {

                    "file_path": {"type": "string", "description": "PDF 文件路径（必填）"},

                    "output_path": {"type": "string", "description": "输出路径（留空自动生成 *_redacted.pdf）"},

                    "keywords": {"type": "array", "items": {"type": "string"}, "description": "关键词列表。如 [\"张三\",\"13800138000\"]。当前按字面量搜索"},

                    "rectangles": {"type": "array", "items": {"type": "object", "properties": {"page": {"type": "integer", "description": "页码 1-indexed"}, "x0": {"type": "number", "description": "左下角 X (pt)"}, "y0": {"type": "number", "description": "左下角 Y (pt)"}, "x1": {"type": "number", "description": "右上角 X (pt)"}, "y1": {"type": "number", "description": "右上角 Y (pt)"}}}, "description": "坐标区域列表。原点为左下角(bottom-left)，单位 pt"},

                    "regex": {"type": "boolean", "description": "保留参数；当前 true 会返回错误，避免不可靠脱敏"},

                    "case_sensitive": {"type": "boolean", "description": "是否大小写敏感。当前关键词脱敏仅支持 true"},

                    "overwrite": {"type": "boolean", "description": "是否覆盖"},

                    "auto_rename": {"type": "boolean", "description": "重名时自动追加序号，默认 true"},

                    "dry_run": {"type": "boolean", "description": "只预览不执行"},

                },

                "required": ["file_path"],

            },

        },

    },

    # 14

    {

        "type": "function", "function": {

            "name": "pdf_compare",

            "description": "视觉对比两个 PDF，逐页渲染为图片后计算像素差异，差异区域红色高亮。需 pdf2image+Pillow+numpy",

            "parameters": {

                "type": "object",

                "properties": {

                    "before_path": {"type": "string", "description": "修改前 PDF 路径（必填）"},

                    "after_path": {"type": "string", "description": "修改后 PDF 路径（必填）"},

                    "output_dir": {"type": "string", "description": "差异图片输出目录（留空用 before 所在目录）"},

                    "pages": {"type": "string", "description": "对比页码范围，默认 all。最多 20 页"},

                    "dpi": {"type": "integer", "description": "渲染分辨率，默认 150"},

                    "threshold": {"type": "number", "description": "差异阈值 0-1，默认 0.05（5%像素变化视为差异）"},

                },

                "required": ["before_path", "after_path"],

            },

        },

    },

    # 15

    {

        "type": "function", "function": {

            "name": "check_pdf_dependencies",

            "description": "检测 PDF 工具链依赖：pypdf/reportlab/Pillow/pdf2image/pytesseract/numpy + 系统级 gs/tesseract/poppler。返回各组件可用性和能力矩阵",

            "parameters": {"type": "object", "properties": {}, "required": []},

        },

    },

]



HANDLERS = {

    "pdf_info": pdf_info,

    "pdf_extract_text": pdf_extract_text,

    "pdf_split": pdf_split,

    "pdf_merge": pdf_merge,

    "pdf_rotate": pdf_rotate,

    "pdf_stamp_text": pdf_stamp_text,

    "pdf_edit_text": pdf_stamp_text,

    "pdf_select_pages": pdf_select_pages,

    "pdf_delete_pages": pdf_delete_pages,

    "pdf_compress": pdf_compress,

    "pdf_watermark": pdf_watermark,

    "pdf_render_preview": pdf_render_preview,

    "pdf_ocr": pdf_ocr,

    "pdf_redact": pdf_redact,

    "pdf_compare": pdf_compare,

    "check_pdf_dependencies": check_pdf_dependencies,

}





def register():

    """注册所有 PDF 工具。"""

    for s in SCHEMAS:

        name = s["function"]["name"]

        register_tool(s, HANDLERS[name])

    stamp_schema = next(s for s in SCHEMAS if s["function"]["name"] == "pdf_stamp_text")

    alias_schema = json.loads(json.dumps(stamp_schema, ensure_ascii=False))

    alias_schema["function"]["name"] = "pdf_edit_text"

    alias_schema["function"]["description"] = "兼容旧名：同 pdf_stamp_text，在 PDF 页面上叠加文本。"

    register_tool(alias_schema, pdf_stamp_text)

