"""文件操作工具 — 读/写/列/删/编辑"""
import os
import shutil
from pathlib import Path
from run.tool import register_tool
from plugins._common import err, truncate, safe_path, check_sandbox, get_current_user_dir

def _read_outside_sandbox_enabled() -> bool:
    """检查是否允许 read_file 读取工作区外的任意路径。"""
    return os.environ.get("VOTX_FILE_READ_OUTSIDE_SANDBOX", "").strip() in ("1", "true", "yes")


def read_file(path: str, encoding: str = "utf-8") -> str:
    """读取文件内容，默认受沙箱保护。

    设置 VOTX_FILE_READ_OUTSIDE_SANDBOX=1 后，若路径不在项目/用户目录下，
    仍允许读取（保留 20MB 限制、目录检查、编码回退等安全措施）。
    write_file / delete_file / list_dir 不受此开关影响。
    """
    p = safe_path(path)
    if p is None:
        return err(f"无效路径: {path}")

    resolved = check_sandbox(p)
    if not resolved:
        if _read_outside_sandbox_enabled():
            resolved = p
        else:
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

def _edit_outside_sandbox_enabled() -> bool:
    """检查是否允许 edit_file 在工作区外编辑。默认关闭，需显式设置。"""
    return os.environ.get("VOTX_FILE_EDIT_OUTSIDE_SANDBOX", "").strip() in ("1", "true", "yes")


def _clamp_column(line_content: str, col: int) -> tuple[int, str, bool]:
    """将 1-based 列号 clamp 到行内容有效范围。返回 (clamped_col, stripped_content, has_newline)。

    col=1 表示首字符前，col=len+1 表示末尾追加。换行符不计入列范围。
    """
    has_nl = line_content.endswith("\n")
    content = line_content.rstrip("\n")
    max_col = len(content) + 1
    clamped = max(1, min(col, max_col))
    return clamped, content, has_nl


def edit_file(
    path: str,
    mode: str,
    text: str,
    line: int = 1,
    column: int = 1,
    end_line: int = 0,
    end_column: int = 0,
    create_backup: bool = True,
    encoding: str = "utf-8",
) -> str:
    """精确编辑文件内容，支持三种模式。

    - insert:        在 line:column 位置插入 text
    - replace_line:  替换整行 line 为 text
    - replace_range: 替换从 line:column 到 end_line:end_column 的范围为 text

    默认受沙箱保护。设置 VOTX_FILE_EDIT_OUTSIDE_SANDBOX=1 后允许编辑任意路径。
    默认自动创建 .bak 备份。
    """
    if mode not in ("insert", "replace_line", "replace_range"):
        return err(f"无效模式: {mode}，可选 insert / replace_line / replace_range")

    p = safe_path(path)
    if p is None:
        return err(f"无效路径: {path}")

    resolved = check_sandbox(p)
    if not resolved:
        if _edit_outside_sandbox_enabled():
            resolved = p
        else:
            return err(f"路径越权，只能在当前项目或用户目录下编辑: {path}")

    if not resolved.exists():
        return err(f"文件不存在: {resolved}")
    if resolved.is_dir():
        return err(f"路径是目录而非文件: {resolved}")

    # 读取所有行
    try:
        lines = resolved.read_text(encoding=encoding).splitlines(keepends=True)
    except UnicodeDecodeError:
        try:
            lines = resolved.read_text(encoding="gbk").splitlines(keepends=True)
        except Exception as e:
            return err(f"读取失败（编码错误）: {e}")
    except Exception as e:
        return err(f"读取失败: {e}")

    if not lines:
        return err("文件为空，无法编辑。请用 write_file 创建内容。")

    # 行号校验（1-based）—— 先校验，再备份
    if line < 1 or line > len(lines):
        return err(f"行号越界: {line}，文件共 {len(lines)} 行")
    if mode == "replace_range":
        if end_line < 1 or end_line > len(lines):
            return err(f"结束行号越界: {end_line}，文件共 {len(lines)} 行")
        if end_line < line:
            return err(f"结束行 {end_line} 不能小于起始行 {line}")

    li = line - 1  # 0-based index

    try:
        if mode == "replace_line":
            old = lines[li]
            lines[li] = text + ("\n" if old.endswith("\n") else "")

        elif mode == "insert":
            col, content, has_nl = _clamp_column(lines[li], column)
            prefix = content[:col - 1]
            suffix = content[col - 1:] + ("\n" if has_nl else "")
            lines[li] = prefix + text + suffix

        elif mode == "replace_range":
            eli = end_line - 1
            # clamp 列号到各自行内容范围
            col_start, first_content, first_nl = _clamp_column(lines[li], column)
            col_end, last_content, last_nl = _clamp_column(lines[eli], end_column)
            # 同行的 end_column 不能早于 column（clamp 后重新判断）
            if line == end_line and col_end < col_start:
                return err(f"结束列 ({col_end}) 不能早于起始列 ({col_start})，行内容长度={len(first_content)}")

            if line == end_line:
                # 单行范围替换
                prefix = first_content[:col_start - 1]
                suffix = first_content[col_end - 1:] + ("\n" if first_nl else "")
                lines[li] = prefix + text + suffix
            else:
                # 跨行范围替换
                prefix = first_content[:col_start - 1]
                suffix = last_content[col_end - 1:] + ("\n" if last_nl else "")
                replacement = prefix + text + suffix
                lines[li:eli + 1] = [replacement + ("\n" if not replacement.endswith("\n") and last_nl else "")]

        # 所有校验通过后才创建备份
        if create_backup:
            bak = resolved.with_suffix(resolved.suffix + ".bak")
            try:
                shutil.copy2(resolved, bak)
            except Exception as e:
                return err(f"创建备份失败: {e}")

        resolved.write_text("".join(lines), encoding=encoding)
        return f"OK: 已编辑 {resolved} (mode={mode}, line={line})"
    except Exception as e:
        return err(f"编辑失败: {e}")


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
            "description": "读取文件内容。默认受沙箱保护（仅项目/用户目录），设置环境变量 VOTX_FILE_READ_OUTSIDE_SANDBOX=1 后允许读取任意路径。支持 UTF-8 和 GBK 编码自动回退，20MB 大小限制。相对路径以项目根目录为基准。",
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
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "精确编辑文件内容。支持三种模式: insert(在指定行列插入), replace_line(替换整行), replace_range(替换行列范围)。默认受沙箱保护，设置 VOTX_FILE_EDIT_OUTSIDE_SANDBOX=1 允许编辑任意路径。自动创建 .bak 备份。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径，可以使用相对或绝对路径"},
                    "mode": {"type": "string", "description": "编辑模式: insert / replace_line / replace_range"},
                    "text": {"type": "string", "description": "要插入或替换的文本"},
                    "line": {"type": "integer", "description": "起始行号 (1-based)，默认 1"},
                    "column": {"type": "integer", "description": "起始列号 (1-based)，默认 1"},
                    "end_line": {"type": "integer", "description": "结束行号 (replace_range 用)"},
                    "end_column": {"type": "integer", "description": "结束列号 (replace_range 用)"},
                    "create_backup": {"type": "boolean", "description": "是否创建 .bak 备份，默认 true"},
                    "encoding": {"type": "string", "description": "文件编码，默认 utf-8"},
                },
                "required": ["path", "mode", "text"],
            },
        },
    },
]

HANDLERS = {
    "read_file": read_file,
    "write_file": write_file,
    "list_dir": list_dir,
    "delete_file": delete_file,
    "edit_file": edit_file,
}

def register():
    """注册所有的文件操作函数"""
    for s in SCHEMAS:
        name = s["function"]["name"]
        register_tool(s, HANDLERS[name])
