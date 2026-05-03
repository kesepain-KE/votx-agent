"""文件操作工具 — 读/写/列/删"""
import os
from pathlib import Path
from run.tool import register_tool
from skills._common import err, truncate, safe_path


def read_file(path: str, encoding: str = "utf-8") -> str:
    """读取文件内容"""
    try:
        p = safe_path(path)
        if p is None:
            return err(f"路径越权或无效: {path}")
        if not p.exists():
            return err(f"文件不存在: {p}")
        if p.is_dir():
            return err(f"路径是目录而非文件: {p}")
        content = p.read_text(encoding=encoding)
        return truncate(content)
    except UnicodeDecodeError:
        # 回退到常见编码
        try:
            content = p.read_text(encoding="gbk")
            return truncate(content)
        except Exception as e:
            return err(f"读取失败（编码错误）: {e}")
    except Exception as e:
        return err(f"读取失败: {e}")


def write_file(path: str, content: str, encoding: str = "utf-8") -> str:
    """将内容写入文件。路径越权时自动回退到用户目录下的 basename"""
    try:
        p = safe_path(path)
        if p is None:
            # 回退：使用文件名的 basename 放到用户目录
            user_dir = os.environ.get("VOTX_USER_DIR", "")
            if user_dir:
                p = Path(user_dir) / Path(path).name
            else:
                return err(f"路径越权且无用户目录: {path}")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
        return f"OK: 已写入 {p} ({len(content)} 字符)"
    except Exception as e:
        return err(f"写入失败: {e}")


def list_dir(path: str) -> str:
    """列出目录内容"""
    try:
        p = safe_path(path)
        if p is None:
            return err(f"路径越权或无效: {path}")
        if not p.exists():
            return err(f"目录不存在: {p}")
        if not p.is_dir():
            return err(f"不是目录: {p}")
        items = []
        for entry in sorted(p.iterdir()):
            tag = "📁" if entry.is_dir() else "📄"
            try:
                size = entry.stat().st_size
            except OSError:
                size = 0
            items.append(f"{tag} {entry.name}  ({_fmt_size(size)})")
        header = f"📂 {p}  ({len(items)} 项)\n"
        return header + "\n".join(items) if items else header + "(空目录)"
    except Exception as e:
        return err(f"列目录失败: {e}")


def delete_file(path: str) -> str:
    """删除文件（禁止删目录）"""
    try:
        p = safe_path(path)
        if p is None:
            return err(f"路径越权或无效: {path}")
        if not p.exists():
            return err(f"文件不存在: {p}")
        if p.is_dir():
            return err(f"禁止通过此工具删除目录: {p}")
        p.unlink()
        return f"OK: 已删除 {p}"
    except Exception as e:
        return err(f"删除失败: {e}")


def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    else:
        return f"{n / 1024 / 1024:.1f} MB"


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文件内容。支持 UTF-8 和 GBK 编码自动回退。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "encoding": {"type": "string", "description": "编码，默认 utf-8"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "将内容写入文件。自动创建父目录。越权路径自动回退到用户目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "要写入的内容"},
                    "encoding": {"type": "string", "description": "编码，默认 utf-8"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "列出目录内容，显示文件和子目录（含大小）",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "删除文件（禁止删除目录）",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                },
                "required": ["path"],
            },
        },
    },
]

HANDLERS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_dir": list_dir,
    "delete_file": delete_file,
}


def register():
    for s in SCHEMAS:
        name = s["function"]["name"]
        register_tool(s, HANDLERS[name])
