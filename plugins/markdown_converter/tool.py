"""Markdown 转换工具 — 将各类文件转为 Markdown"""
import os
import tempfile
import subprocess
from pathlib import Path

from run.tool import register_tool
from run.io_utils import decode_subprocess_output, read_text_fallback, utf8_subprocess_env
from plugins._common import (
    err,
    safe_path,
    check_sandbox,
    check_dangerous_command,
    get_effective_tool_timeout,
)


def _read_markdown_file(path: str) -> str:
    """读取 markitdown 输出文件，兼容 UTF-8 BOM。"""
    text, _ = read_text_fallback(Path(path), "utf-8")
    return text


def convert_to_markdown(
    input_path: str,
    output_path: str = "",
    extension: str = "",
    mime_type: str = "",
    charset: str = "",
    use_docintel: bool = False,
    endpoint: str = "",
    use_plugins: bool = False,
) -> str:
    """将文档/文件转换为 Markdown 格式。

    支持: PDF, .docx, .pptx, .xlsx, .xls, HTML, CSV, JSON, XML,
          图片(EXIF+OCR), 音频(转录), ZIP, YouTube URL, EPub

    参数:
        input_path: 输入文件路径
        output_path: 输出 Markdown 文件路径（可选，默认返回内容到 stdout）
        extension: 文件类型提示（stdin 时用，如 .pdf）
        mime_type: MIME 类型提示
        charset: 字符集提示（如 UTF-8）
        use_docintel: 使用 Azure Document Intelligence
        endpoint: Document Intelligence 端点 URL
        use_plugins: 启用第三方插件
    """
    p = safe_path(input_path)
    if p is None:
        return err(f"无效路径: {input_path}")

    resolved = check_sandbox(p)
    if not resolved:
        return err(f"路径越权: {input_path}")

    cmd = ["markitdown", str(resolved)]
    temp_output = ""

    if output_path:
        out = safe_path(output_path)
        if out is None:
            return err(f"无效输出路径: {output_path}")
        out_resolved = check_sandbox(out)
        if not out_resolved:
            return err(f"输出路径越权: {output_path}")
        cmd.extend(["-o", str(out_resolved)])
    else:
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".md",
            prefix="markitdown_",
            delete=False,
        )
        temp_output = tmp.name
        tmp.close()
        cmd.extend(["-o", temp_output])

    if extension:
        cmd.extend(["-x", extension])
    if mime_type:
        cmd.extend(["-m", mime_type])
    if charset:
        cmd.extend(["-c", charset])
    if use_docintel:
        cmd.append("-d")
    if endpoint:
        cmd.extend(["-e", endpoint])
    if use_plugins:
        cmd.append("-p")

    danger = check_dangerous_command(" ".join(cmd))
    if danger:
        return err(danger)

    timeout = get_effective_tool_timeout(120)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            env=utf8_subprocess_env(),
        )
        stderr = decode_subprocess_output(result.stderr).strip()
        stdout = decode_subprocess_output(result.stdout).strip()
        if result.returncode != 0:
            detail = stderr or stdout
            return err(f"markitdown 失败 (code={result.returncode}): {detail}")

        if output_path:
            return f"OK: 已转换并保存到 {output_path}"

        output = _read_markdown_file(temp_output).strip()
        if not output:
            output = stdout
        if not output:
            return "OK: 转换完成，但无内容输出"
        return output
    except subprocess.TimeoutExpired:
        return err(f"markitdown 执行超时（{timeout}秒）")
    except FileNotFoundError:
        return err("未找到 markitdown 命令，请先 pip install markitdown")
    except Exception as e:
        return err(f"转换失败: {e}")
    finally:
        if temp_output:
            try:
                os.unlink(temp_output)
            except OSError:
                pass


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "convert_to_markdown",
            "description": "将文档/文件转换为 Markdown。支持 PDF、Word、PowerPoint、Excel、HTML、CSV、JSON、XML、图片、音频、ZIP、YouTube URL、EPub 等格式。",
            "parameters": {
                "type": "object",
                "properties": {
                    "input_path": {
                        "type": "string",
                        "description": "输入文件路径",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "输出 Markdown 文件路径（可选，不指定则返回内容到 stdout）",
                    },
                    "extension": {
                        "type": "string",
                        "description": "文件扩展名提示，如 .pdf .docx（可选）",
                    },
                    "mime_type": {
                        "type": "string",
                        "description": "MIME 类型提示（可选）",
                    },
                    "charset": {
                        "type": "string",
                        "description": "字符集提示，如 UTF-8（可选）",
                    },
                    "use_docintel": {
                        "type": "boolean",
                        "description": "是否使用 Azure Document Intelligence（可选）",
                    },
                    "endpoint": {
                        "type": "string",
                        "description": "Document Intelligence 端点 URL（可选）",
                    },
                    "use_plugins": {
                        "type": "boolean",
                        "description": "是否启用第三方插件（可选）",
                    },
                },
                "required": ["input_path"],
            },
        },
    },
]

HANDLERS = {
    "convert_to_markdown": convert_to_markdown,
}


def register():
    """注册 markdown-converter 工具"""
    for s in SCHEMAS:
        name = s["function"]["name"]
        register_tool(s, HANDLERS[name])
