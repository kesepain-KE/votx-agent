"""文件操作工具 — 读/写/列/删"""
import os
from pathlib import Path
from run.tool import register_tool
from plugins._common import err, truncate, safe_path, check_sandbox, get_current_user_dir

def read_file(path: str, encoding: str = "utf-8") -> str:
    """读取文件内容，受沙箱保护"""
    p = safe_path(path)
    if p is None:
        return err(f"无效路径: {path}")
    
    resolved = check_sandbox(p)
    if not resolved:
        return err(f"路径越权，只能在当前项目或用户目录下读取: {path}")
        
    if not resolved.exists():
        return err(f"文件不存在: {resolved}")
    if resolved.is_dir():
        return err(f"路径是目录而非文件: {resolved}")
        
    try:
        if resolved.stat().st_size > 20 * 1024 * 1024:
            return err(f"文件过大，无法读取（超过20MB）: {resolved}")
    except OSError:
        pass
        
    try:
        content = resolved.read_text(encoding=encoding)
        return truncate(content)
    except UnicodeDecodeError:
        try:
            content = resolved.read_text(encoding="gbk")
            return truncate(content)
        except Exception as e:
            return err(f"读取失败（编码错误）: {e}")
    except Exception as e:
        return err(f"读取失败: {e}")

def write_file(path: str, content: str, encoding: str = "utf-8") -> str:
    """将内容写入文件。路径越权时自动回退到用户目录下的 basename"""
    p = safe_path(path)
    if p is None:
        return err(f"无效路径: {path}")
        
    resolved = check_sandbox(p)
    
    if not resolved:
        user_dir = get_current_user_dir()
        if not user_dir:
            return err(f"路径越权且无用户目录配置: {path}")
        resolved = Path(user_dir).resolve() / p.name

    try:
        if resolved.exists() and resolved.is_dir():
            return err(f"路径已存在且是目录，无法覆盖: {resolved}")
            
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding=encoding)
        return f"OK: 已写入 {resolved} ({len(content)} 字符)"
    except Exception as e:
        return err(f"写入失败: {e}")

def list_dir(path: str) -> str:
    """列出目录内容"""
    p = safe_path(path)
    if p is None:
        return err(f"无效路径: {path}")
        
    resolved = check_sandbox(p)
    if not resolved:
        return err(f"路径越权，只能在当前项目或用户目录下进行操作: {path}")
        
    if not resolved.exists():
        return err(f"目录不存在: {resolved}")
    if not resolved.is_dir():
        return err(f"不是目录: {resolved}")
        
    try:
        items = []
        for entry in sorted(resolved.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            tag = "📁" if entry.is_dir() else "📄"
            try:
                size = entry.stat().st_size
            except OSError:
                size = 0
            size_str = "-" if entry.is_dir() else _fmt_size(size)
            items.append(f"{tag} {entry.name}  ({size_str})")
            
        header = f"📂 {resolved}  ({len(items)} 项)\n"
        return header + "\n".join(items) if items else header + "(空目录)"
    except Exception as e:
        return err(f"列目录失败: {e}")

def delete_file(path: str) -> str:
    """删除文件（禁止删目录）"""
    p = safe_path(path)
    if p is None:
        return err(f"无效路径: {path}")
        
    resolved = check_sandbox(p)
    if not resolved:
        return err(f"路径越权，只能删除当前项目或用户目录下的文件: {path}")
        
    if not resolved.exists():
        return err(f"文件不存在: {resolved}")
    if resolved.is_dir():
        return err(f"禁止通过此工具删除目录: {resolved}")
        
    try:
        resolved.unlink()
        return f"OK: 已删除 {resolved}"
    except Exception as e:
        return err(f"删除失败: {e}")

def _fmt_size(n: int) -> str:
    """执行 fmt_size 内部辅助逻辑。"""
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
            "description": "读取文件内容。严格受沙箱保护（只能处于当前项目或用户目录）。支持 UTF-8 和 GBK 编码自动回退，附带20MB大小限制保护内存。相对路径以项目根目录为基准。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径，可以使用相对或绝对路径"},
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
            "description": "将内容写入文件。自动创建父目录。受沙箱保护，若路径越权则自动回退并写入到用户目录下的同名文件中。相对路径以项目根目录为基准。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径，可以使用相对或绝对路径"},
                    "content": {"type": "string", "description": "要写入的内容（完整内容覆盖，非追加）"},
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
            "description": "列出目录内容。受沙箱限制，文件夹将置前排序以更加清晰。相对路径以项目根目录为基准。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径，可以使用相对或绝对路径"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "删除文件。为了数据安全，本工具严格禁止删除目录操作。受沙箱保护。相对路径以项目根目录为基准。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "要删除的文件路径，可以使用相对或绝对路径"},
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
    """注册所有的文件操作函数"""
    for s in SCHEMAS:
        name = s["function"]["name"]
        register_tool(s, HANDLERS[name])
