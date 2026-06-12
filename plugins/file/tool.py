"""文件操作工具 — 读/写/列/删/编辑/搜索/移动。"""
from collections import deque
from datetime import datetime
import fnmatch
import os
from pathlib import Path
import re
import shutil
import subprocess

from run.tool import register_tool
from run.io_utils import (
    decode_subprocess_output,
    read_text_fallback,
    text_encoding_candidates,
    utf8_subprocess_env,
)
from plugins._common import (
    err,
    truncate,
    safe_path,
    check_sandbox,
    get_current_user_dir,
    get_effective_tool_timeout,
)

_READ_LIMIT_BYTES = 20 * 1024 * 1024
_SEARCH_FILE_LIMIT_BYTES = 2 * 1024 * 1024
_TREE_MAX_ENTRIES = 1000
_SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _env_enabled(name: str) -> bool:
    """判断环境变量是否开启。"""
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _outside_sandbox_enabled(action: str) -> bool:
    """按操作类型判断是否允许越过默认沙箱。"""
    if _env_enabled("VOTX_FILE_OUTSIDE_SANDBOX"):
        return True
    if action in ("read", "list", "stat", "tree", "search"):
        return _env_enabled("VOTX_FILE_READ_OUTSIDE_SANDBOX")
    if action in ("write", "append", "edit", "copy", "move", "mkdir"):
        return (
            _env_enabled("VOTX_FILE_EDIT_OUTSIDE_SANDBOX")
            or _env_enabled("VOTX_FILE_WRITE_OUTSIDE_SANDBOX")
        )
    if action == "delete":
        return _env_enabled("VOTX_FILE_DELETE_OUTSIDE_SANDBOX")
    return False


def _resolve_path(path: str, action: str) -> Path | None:
    """解析路径并按 action 做沙箱检查。"""
    p = safe_path(path)
    if p is None:
        return None

    resolved = check_sandbox(p)
    if resolved:
        return resolved
    if _outside_sandbox_enabled(action):
        return p
    return None


def _path_error(path: str, action: str) -> str:
    """生成路径越权错误。"""
    return err(
        f"路径越权: {path}。默认只能操作项目根或用户目录；"
        f"如需放开，设置 VOTX_FILE_OUTSIDE_SANDBOX=1，"
        f"或为 {action} 操作设置对应的细粒度环境变量。")


def _read_text_with_fallback(path: Path, encoding: str = "utf-8") -> tuple[str, str]:
    """读取文本，按指定编码、UTF-8 BOM、GBK 顺序回退。"""
    return read_text_fallback(path, encoding)


def _encoding_candidates(encoding: str = "utf-8") -> list[str]:
    """返回去重后的编码候选列表。"""
    return text_encoding_candidates(encoding)


def _fmt_size(n: int) -> str:
    """格式化文件大小。"""
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def _ensure_file(path: Path) -> str | None:
    """检查路径存在且是文件。"""
    if not path.exists():
        return err(f"文件不存在: {path}")
    if path.is_dir():
        return err(f"路径是目录而非文件: {path}")
    return None


def _ensure_dir(path: Path) -> str | None:
    """检查路径存在且是目录。"""
    if not path.exists():
        return err(f"目录不存在: {path}")
    if not path.is_dir():
        return err(f"不是目录: {path}")
    return None


def _clamp_int(value, default: int, min_value: int, max_value: int) -> int:
    """安全限制整数范围。"""
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = default
    return max(min_value, min(n, max_value))


def read_file(path: str, encoding: str = "utf-8") -> str:
    """读取整个文件内容。"""
    resolved = _resolve_path(path, "read")
    if not resolved:
        return _path_error(path, "read")

    file_err = _ensure_file(resolved)
    if file_err:
        return file_err

    try:
        if resolved.stat().st_size > _READ_LIMIT_BYTES:
            return err(f"文件过大，无法读取（超过20MB）: {resolved}")
        content, _ = _read_text_with_fallback(resolved, encoding)
        return truncate(content)
    except UnicodeDecodeError as e:
        return err(f"读取失败（编码错误）: {e}")
    except Exception as e:
        return err(f"读取失败: {e}")


def read_file_range(
    path: str,
    start_line: int = 1,
    end_line: int = 0,
    tail: int = 0,
    max_lines: int = 500,
    encoding: str = "utf-8",
) -> str:
    """按行读取文件片段；tail>0 时返回末尾 N 行。"""
    resolved = _resolve_path(path, "read")
    if not resolved:
        return _path_error(path, "read")

    file_err = _ensure_file(resolved)
    if file_err:
        return file_err

    max_lines = _clamp_int(max_lines, 500, 1, 5000)
    tail = _clamp_int(tail, 0, 0, 5000)
    start_line = _clamp_int(start_line, 1, 1, 10**9)
    end_line = _clamp_int(end_line, 0, 0, 10**9)

    last_error = None
    selected = []
    total = 0
    used_encoding = encoding
    for enc in _encoding_candidates(encoding):
        try:
            selected = []
            total = 0
            used_encoding = enc
            with resolved.open("r", encoding=enc) as f:
                if tail > 0:
                    tail_lines = deque(maxlen=tail)
                    for total, line in enumerate(f, 1):
                        tail_lines.append((total, line.rstrip("\n\r")))
                    selected = list(tail_lines)
                else:
                    if end_line <= 0:
                        target_end = start_line + max_lines - 1
                    else:
                        if end_line < start_line:
                            return err(f"结束行 {end_line} 不能小于起始行 {start_line}")
                        target_end = min(end_line, start_line + max_lines - 1)
                    for total, line in enumerate(f, 1):
                        if total < start_line:
                            continue
                        if total > target_end:
                            break
                        selected.append((total, line.rstrip("\n\r")))
                    if total < start_line:
                        return err(f"起始行越界: {start_line}，文件共 {total} 行")
            break
        except UnicodeDecodeError as e:
            last_error = e
            continue
        except Exception as e:
            return err(f"读取失败: {e}")
    else:
        return err(f"读取失败（编码错误）: {last_error}")

    body = "\n".join(f"{line_no}: {line}" for line_no, line in selected)
    header = f"File: {resolved}\nEncoding: {used_encoding}\nLines: {total}\n\n"
    return header + body


def write_file(path: str, content: str, encoding: str = "utf-8") -> str:
    """完整覆盖写入文件。越权时不回退，直接按环境变量决定是否允许。"""
    resolved = _resolve_path(path, "write")
    if not resolved:
        return _path_error(path, "write")

    try:
        if resolved.exists() and resolved.is_dir():
            return err(f"路径已存在且是目录，无法覆盖: {resolved}")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding=encoding)
        return f"OK: 已写入 {resolved} ({len(content)} 字符)"
    except Exception as e:
        return err(f"写入失败: {e}")


def append_file(path: str, content: str, encoding: str = "utf-8") -> str:
    """追加写入文件，不存在则创建。"""
    resolved = _resolve_path(path, "append")
    if not resolved:
        return _path_error(path, "append")

    try:
        if resolved.exists() and resolved.is_dir():
            return err(f"路径已存在且是目录，无法写入: {resolved}")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with resolved.open("a", encoding=encoding) as f:
            f.write(content)
        return f"OK: 已追加 {resolved} ({len(content)} 字符)"
    except Exception as e:
        return err(f"追加失败: {e}")


def list_dir(path: str) -> str:
    """列出目录内容。"""
    resolved = _resolve_path(path, "list")
    if not resolved:
        return _path_error(path, "list")

    dir_err = _ensure_dir(resolved)
    if dir_err:
        return dir_err

    try:
        items = []
        for entry in sorted(resolved.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            tag = "[D]" if entry.is_dir() else "[F]"
            try:
                size = entry.stat().st_size
            except OSError:
                size = 0
            size_str = "-" if entry.is_dir() else _fmt_size(size)
            items.append(f"{tag} {entry.name}  ({size_str})")

        header = f"Directory: {resolved}  ({len(items)} items)\n"
        return header + "\n".join(items) if items else header + "(empty)"
    except Exception as e:
        return err(f"列目录失败: {e}")


def tree_dir(
    path: str,
    max_depth: int = 2,
    max_entries: int = 200,
    include_hidden: bool = False,
) -> str:
    """输出目录树。"""
    resolved = _resolve_path(path, "tree")
    if not resolved:
        return _path_error(path, "tree")

    dir_err = _ensure_dir(resolved)
    if dir_err:
        return dir_err

    max_depth = _clamp_int(max_depth, 2, 0, 10)
    max_entries = _clamp_int(max_entries, 200, 1, _TREE_MAX_ENTRIES)
    lines = [str(resolved)]
    count = 0

    def walk(root: Path, prefix: str, depth: int):
        nonlocal count
        if depth >= max_depth or count >= max_entries:
            return
        try:
            entries = sorted(root.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except OSError:
            return
        if not include_hidden:
            entries = [e for e in entries if not e.name.startswith(".")]
        for idx, entry in enumerate(entries):
            if count >= max_entries:
                return
            count += 1
            connector = "`-- " if idx == len(entries) - 1 else "|-- "
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{prefix}{connector}{entry.name}{suffix}")
            if entry.is_dir() and entry.name not in _SKIP_DIRS:
                next_prefix = prefix + ("    " if idx == len(entries) - 1 else "|   ")
                walk(entry, next_prefix, depth + 1)

    walk(resolved, "", 0)
    if count >= max_entries:
        lines.append(f"... (truncated at {max_entries} entries)")
    return "\n".join(lines)


def stat_file(path: str) -> str:
    """查看文件或目录信息。"""
    resolved = _resolve_path(path, "stat")
    if not resolved:
        return _path_error(path, "stat")

    if not resolved.exists():
        return err(f"路径不存在: {resolved}")

    try:
        st = resolved.stat()
        kind = "directory" if resolved.is_dir() else "file"
        modified = datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
        created = datetime.fromtimestamp(st.st_ctime).isoformat(timespec="seconds")
        return (
            f"Path: {resolved}\n"
            f"Type: {kind}\n"
            f"Size: {st.st_size} bytes ({_fmt_size(st.st_size)})\n"
            f"Modified: {modified}\n"
            f"Created: {created}\n"
            f"Exists: true"
        )
    except Exception as e:
        return err(f"读取文件信息失败: {e}")


def delete_file(path: str) -> str:
    """删除文件，禁止删除目录。"""
    resolved = _resolve_path(path, "delete")
    if not resolved:
        return _path_error(path, "delete")

    file_err = _ensure_file(resolved)
    if file_err:
        return file_err

    try:
        resolved.unlink()
        return f"OK: 已删除 {resolved}"
    except Exception as e:
        return err(f"删除失败: {e}")


def _clamp_column(line_content: str, col: int) -> tuple[int, str, bool]:
    """将 1-based 列号 clamp 到行内容有效范围。"""
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
    old_text: str = "",
    expected_count: int = 1,
    create_backup: bool = True,
    encoding: str = "utf-8",
) -> str:
    """精确编辑文件内容。"""
    if mode not in ("insert", "replace_line", "replace_range", "replace_text"):
        return err("无效模式，可选 insert / replace_line / replace_range / replace_text")

    resolved = _resolve_path(path, "edit")
    if not resolved:
        return _path_error(path, "edit")

    file_err = _ensure_file(resolved)
    if file_err:
        return file_err

    try:
        content, used_encoding = _read_text_with_fallback(resolved, encoding)
        lines = content.splitlines(keepends=True)
    except UnicodeDecodeError as e:
        return err(f"读取失败（编码错误）: {e}")
    except Exception as e:
        return err(f"读取失败: {e}")

    if mode == "replace_text":
        if not old_text:
            return err("replace_text 模式需要 old_text")
        count = content.count(old_text)
        if expected_count >= 0 and count != expected_count:
            return err(f"old_text 匹配次数为 {count}，不等于 expected_count={expected_count}")
        new_content = content.replace(old_text, text)
    else:
        if not lines:
            return err("文件为空，无法编辑。请用 write_file 创建内容。")

        if line < 1 or line > len(lines):
            return err(f"行号越界: {line}，文件共 {len(lines)} 行")
        if mode == "replace_range":
            if end_line < 1 or end_line > len(lines):
                return err(f"结束行号越界: {end_line}，文件共 {len(lines)} 行")
            if end_line < line:
                return err(f"结束行 {end_line} 不能小于起始行 {line}")

        li = line - 1
        try:
            if mode == "replace_line":
                old = lines[li]
                lines[li] = text + ("\n" if old.endswith("\n") else "")

            elif mode == "insert":
                col, line_content, has_nl = _clamp_column(lines[li], column)
                prefix = line_content[:col - 1]
                suffix = line_content[col - 1:] + ("\n" if has_nl else "")
                lines[li] = prefix + text + suffix

            elif mode == "replace_range":
                eli = end_line - 1
                col_start, first_content, first_nl = _clamp_column(lines[li], column)
                col_end, last_content, last_nl = _clamp_column(lines[eli], end_column)
                if line == end_line and col_end < col_start:
                    return err(f"结束列 ({col_end}) 不能早于起始列 ({col_start})")

                if line == end_line:
                    prefix = first_content[:col_start - 1]
                    suffix = first_content[col_end - 1:] + ("\n" if first_nl else "")
                    lines[li] = prefix + text + suffix
                else:
                    prefix = first_content[:col_start - 1]
                    suffix = last_content[col_end - 1:] + ("\n" if last_nl else "")
                    replacement = prefix + text + suffix
                    lines[li:eli + 1] = [
                        replacement + ("\n" if not replacement.endswith("\n") and last_nl else "")
                    ]
        except Exception as e:
            return err(f"编辑失败: {e}")
        new_content = "".join(lines)

    try:
        if create_backup:
            bak = resolved.with_suffix(resolved.suffix + ".bak")
            shutil.copy2(resolved, bak)
        resolved.write_text(new_content, encoding=used_encoding or encoding)
        return f"OK: 已编辑 {resolved} (mode={mode})"
    except Exception as e:
        return err(f"写入失败: {e}")


def make_dir(path: str, parents: bool = True, exist_ok: bool = True) -> str:
    """创建目录。"""
    resolved = _resolve_path(path, "mkdir")
    if not resolved:
        return _path_error(path, "mkdir")

    try:
        if resolved.exists() and not resolved.is_dir():
            return err(f"路径已存在且不是目录: {resolved}")
        resolved.mkdir(parents=parents, exist_ok=exist_ok)
        return f"OK: 已创建目录 {resolved}"
    except Exception as e:
        return err(f"创建目录失败: {e}")


def copy_file(src_path: str, dst_path: str, overwrite: bool = False) -> str:
    """复制文件。dst_path 必须是目标文件路径，不能是目录。"""
    src = _resolve_path(src_path, "read")
    if not src:
        return _path_error(src_path, "read")
    dst = _resolve_path(dst_path, "copy")
    if not dst:
        return _path_error(dst_path, "copy")

    file_err = _ensure_file(src)
    if file_err:
        return file_err
    if dst.exists() and dst.is_dir():
        return err(f"目标路径是目录，请提供完整目标文件路径: {dst}")
    if dst.exists() and not overwrite:
        return err(f"目标文件已存在，设置 overwrite=true 才能覆盖: {dst}")

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return f"OK: 已复制 {src} -> {dst}"
    except Exception as e:
        return err(f"复制失败: {e}")


def move_file(src_path: str, dst_path: str, overwrite: bool = False) -> str:
    """移动或重命名文件。dst_path 必须是目标文件路径，不能是目录。"""
    src = _resolve_path(src_path, "move")
    if not src:
        return _path_error(src_path, "move")
    dst = _resolve_path(dst_path, "move")
    if not dst:
        return _path_error(dst_path, "move")

    file_err = _ensure_file(src)
    if file_err:
        return file_err
    if dst.exists() and dst.is_dir():
        return err(f"目标路径是目录，请提供完整目标文件路径: {dst}")
    if dst.exists() and not overwrite:
        return err(f"目标文件已存在，设置 overwrite=true 才能覆盖: {dst}")

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and overwrite:
            dst.unlink()
        shutil.move(str(src), str(dst))
        return f"OK: 已移动 {src} -> {dst}"
    except Exception as e:
        return err(f"移动失败: {e}")


def _iter_search_files(root: Path, include_hidden: bool, file_glob: str):
    """遍历搜索文件。"""
    for dirpath, dirnames, filenames in os.walk(str(root), onerror=lambda _e: None):
        if not include_hidden:
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in _SKIP_DIRS]
            filenames = [f for f in filenames if not f.startswith(".")]
        else:
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fname in filenames:
            if file_glob and not fnmatch.fnmatch(fname, file_glob):
                continue
            yield Path(dirpath) / fname


def _has_bin(name: str) -> bool:
    """检查命令行工具是否可用。"""
    return shutil.which(name) is not None


def _search_roots(scope: str, root: str) -> tuple[list[Path], str | None]:
    """根据 scope/root 获取搜索根目录。"""
    roots: list[Path] = []
    if root:
        resolved = _resolve_path(root, "search")
        if not resolved:
            return [], _path_error(root, "search")
        if not resolved.exists() or not resolved.is_dir():
            return [], err(f"搜索根目录不存在或不是目录: {resolved}")
        return [resolved], None

    if scope in ("workspace", "both"):
        resolved = _resolve_path(str(_PROJECT_ROOT), "search")
        if resolved:
            roots.append(resolved)
    if scope in ("user", "both"):
        user_dir = get_current_user_dir()
        if user_dir:
            resolved = _resolve_path(user_dir, "search")
            if resolved:
                roots.append(resolved)
    if not roots:
        return [], err("没有可用的搜索根目录")
    deduped = []
    seen = set()
    for item in roots:
        key = str(item)
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped, None


def _run_search_command(cmd: list[str]) -> tuple[int, str, str]:
    """运行搜索命令并按 UTF-8 优先解码输出。"""
    r = subprocess.run(
        cmd,
        capture_output=True,
        timeout=get_effective_tool_timeout(30),
        env=utf8_subprocess_env(),
    )
    return (
        r.returncode,
        decode_subprocess_output(r.stdout),
        decode_subprocess_output(r.stderr),
    )


def _search_files_fd(query: str, roots: list[Path], max_results: int,
                     file_glob: str, regex: bool, include_hidden: bool) -> str:
    """使用 fd 搜索文件名。"""
    results = []
    try:
        for root in roots:
            cmd = ["fd", "--max-results", str(max_results)]
            if include_hidden:
                cmd.append("--hidden")
            if file_glob:
                cmd.extend(["--glob", file_glob])
            elif not regex:
                cmd.append(query)
            else:
                cmd.append(query)
            cmd.append(str(root))
            code, stdout, stderr = _run_search_command(cmd)
            if code == 0:
                results.extend([line for line in stdout.splitlines() if line])
            elif code == 1:
                continue
            else:
                return err(f"fd 错误: {stderr.strip()}")
            if len(results) >= max_results:
                break
        return "\n".join(results[:max_results]) if results else "未找到匹配结果"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "__FALLBACK__"
    except Exception:
        return "__FALLBACK__"


def _search_text_rg(query: str, roots: list[Path], max_results: int,
                    context_lines: int, file_glob: str, regex: bool,
                    include_hidden: bool) -> str:
    """使用 rg 搜索文本内容。"""
    results = []
    try:
        for root in roots:
            cmd = ["rg", "--line-number", "--max-count", str(max_results)]
            if not regex:
                cmd.append("--fixed-strings")
            if include_hidden:
                cmd.append("--hidden")
            if context_lines > 0:
                cmd.extend(["-C", str(context_lines)])
            if file_glob:
                cmd.extend(["--glob", file_glob])
            cmd.extend([query, str(root)])
            code, stdout, stderr = _run_search_command(cmd)
            if code == 0:
                results.append(stdout.strip())
            elif code == 1:
                continue
            else:
                return err(f"rg 错误: {stderr.strip()}")
        output = "\n--\n".join([r for r in results if r]) if results else "未找到匹配结果"
        return truncate(output, max_len=50000)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "__FALLBACK__"
    except Exception:
        return "__FALLBACK__"


def _code_patterns(query: str) -> list[re.Pattern]:
    """生成代码定义搜索模式。"""
    q = re.escape(query)
    raw_patterns = [
        r"^\s*(def|class|async def)\s+\w*" + q + r"\w*",
        r"^\s*(fn|function|func)\s+\w*" + q + r"\w*",
        r"^\s*(public|private|protected)\s+(static\s+)?(function|class)\s+\w*" + q + r"\w*",
        r"^\s*(const|let|var)\s+\w*" + q + r"\w*\s*=",
        r"^\s*(export\s+)?(default\s+)?(function|class)\s+\w*" + q + r"\w*",
    ]
    return [re.compile(p, re.IGNORECASE) for p in raw_patterns]


def _search_code_rg(query: str, roots: list[Path], max_results: int,
                    context_lines: int, include_hidden: bool) -> str:
    """使用 rg 搜索代码定义。"""
    q = re.escape(query)
    pattern = "|".join([
        r"^\s*(def|class|async def)\s+\w*" + q + r"\w*",
        r"^\s*(fn|function|func)\s+\w*" + q + r"\w*",
        r"^\s*(public|private|protected)\s+(static\s+)?(function|class)\s+\w*" + q + r"\w*",
        r"^\s*(const|let|var)\s+\w*" + q + r"\w*\s*=",
        r"^\s*(export\s+)?(default\s+)?(function|class)\s+\w*" + q + r"\w*",
    ])
    results = []
    try:
        for root in roots:
            cmd = ["rg", "--line-number", "--max-count", str(max_results)]
            if include_hidden:
                cmd.append("--hidden")
            if context_lines > 0:
                cmd.extend(["-C", str(context_lines)])
            cmd.extend([pattern, str(root)])
            code, stdout, stderr = _run_search_command(cmd)
            if code == 0:
                results.append(stdout.strip())
            elif code == 1:
                continue
            else:
                return err(f"rg 错误: {stderr.strip()}")
        output = "\n--\n".join([r for r in results if r]) if results else "未找到匹配结果"
        return truncate(output, max_len=50000)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "__FALLBACK__"
    except Exception:
        return "__FALLBACK__"


def _format_context(file_path: Path, lines: list[str], index: int, context_lines: int) -> str:
    """格式化命中行上下文。"""
    start = max(0, index - context_lines)
    end = min(len(lines), index + context_lines + 1)
    return "".join(f"{file_path}:{j + 1}:{lines[j]}" for j in range(start, end)).strip()


def search_files(
    query: str,
    root: str = "",
    mode: str = "text",
    scope: str = "workspace",
    file_glob: str = "",
    max_results: int = 50,
    context_lines: int = 0,
    include_hidden: bool = False,
    regex: bool = False,
    encoding: str = "utf-8",
) -> str:
    """搜索文件名、文件内容或代码定义。"""
    if not query or not query.strip():
        return err("query 参数不能为空")
    query = query.strip()

    mode = (mode or "text").strip().lower()
    if mode not in ("file", "name", "text", "content", "code"):
        return err("mode 可选 file/name/text/content/code")

    scope = (scope or "workspace").strip().lower()
    if scope not in ("workspace", "user", "both"):
        return err("scope 可选 workspace/user/both")

    max_results = _clamp_int(max_results, 50, 1, 500)
    context_lines = _clamp_int(context_lines, 0, 0, 20)

    roots, root_err = _search_roots(scope, root)
    if root_err:
        return root_err

    try:
        pattern = re.compile(query, re.IGNORECASE) if regex else None
    except re.error as e:
        return err(f"正则表达式无效: {e}")

    def matches(value: str) -> bool:
        return bool(pattern.search(value)) if pattern else query.lower() in value.lower()

    if mode in ("file", "name") and _has_bin("fd"):
        result = _search_files_fd(query, roots, max_results, file_glob, regex, include_hidden)
        if result != "__FALLBACK__":
            return result

    if mode in ("text", "content") and _has_bin("rg"):
        result = _search_text_rg(query, roots, max_results, context_lines, file_glob, regex, include_hidden)
        if result != "__FALLBACK__":
            return result

    if mode == "code" and _has_bin("rg"):
        result = _search_code_rg(query, roots, max_results, context_lines, include_hidden)
        if result != "__FALLBACK__":
            return result

    results = []
    code_patterns = _code_patterns(query) if mode == "code" else []
    for search_root in roots:
        for file_path in _iter_search_files(search_root, include_hidden, file_glob):
            if len(results) >= max_results:
                break
            if mode in ("file", "name"):
                if matches(file_path.name) or matches(str(file_path)):
                    results.append(str(file_path))
                continue

            try:
                if file_path.stat().st_size > _SEARCH_FILE_LIMIT_BYTES:
                    continue
                text, _ = _read_text_with_fallback(file_path, encoding)
            except Exception:
                continue
            lines = text.splitlines(keepends=True)
            for i, line in enumerate(lines):
                if mode == "code":
                    hit = any(p.search(line) for p in code_patterns)
                else:
                    hit = matches(line)
                if hit:
                    if context_lines > 0:
                        results.append(_format_context(file_path, lines, i, context_lines))
                    else:
                        results.append(f"{file_path}:{i + 1}:{line}".rstrip())
                    if len(results) >= max_results:
                        break
        if len(results) >= max_results:
            break

    return "\n".join(results) if results else "未找到匹配结果"


SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取整个文件内容。默认受沙箱保护；VOTX_FILE_OUTSIDE_SANDBOX=1 或 VOTX_FILE_READ_OUTSIDE_SANDBOX=1 可读取沙箱外路径。支持 UTF-8/UTF-8 BOM/GBK 回退，20MB 限制。",
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
            "name": "read_file_range",
            "description": "按行读取文件片段，支持 start_line/end_line 或 tail 读取日志尾部。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "start_line": {"type": "integer", "description": "起始行号，1-based"},
                    "end_line": {"type": "integer", "description": "结束行号；0 表示按 max_lines 自动截断"},
                    "tail": {"type": "integer", "description": "读取末尾 N 行；大于 0 时优先于 start_line/end_line"},
                    "max_lines": {"type": "integer", "description": "最大返回行数，默认 500，上限 5000"},
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
            "description": "完整覆盖写入文件。不会在越权时回退路径；越权是否允许完全由环境变量控制。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "要写入的完整内容"},
                    "encoding": {"type": "string", "description": "编码，默认 utf-8"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_file",
            "description": "追加写入文件，不存在则创建。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "要追加的内容"},
                    "encoding": {"type": "string", "description": "编码，默认 utf-8"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "精确编辑文件内容。支持 insert、replace_line、replace_range、replace_text。默认创建 .bak 备份。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "mode": {"type": "string", "enum": ["insert", "replace_line", "replace_range", "replace_text"], "description": "编辑模式"},
                    "text": {"type": "string", "description": "插入内容、新行内容或替换后的文本"},
                    "line": {"type": "integer", "description": "起始行号"},
                    "column": {"type": "integer", "description": "起始列号"},
                    "end_line": {"type": "integer", "description": "结束行号"},
                    "end_column": {"type": "integer", "description": "结束列号"},
                    "old_text": {"type": "string", "description": "replace_text 模式下要替换的原文"},
                    "expected_count": {"type": "integer", "description": "replace_text 期望匹配次数，默认 1；设为 -1 跳过检查"},
                    "create_backup": {"type": "boolean", "description": "是否创建 .bak 备份，默认 true"},
                    "encoding": {"type": "string", "description": "编码，默认 utf-8"},
                },
                "required": ["path", "mode", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "列出目录内容，文件夹置前排序。",
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
            "name": "tree_dir",
            "description": "显示目录树，默认跳过常见大目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径"},
                    "max_depth": {"type": "integer", "description": "最大深度，默认 2"},
                    "max_entries": {"type": "integer", "description": "最大条目数，默认 200，上限 1000"},
                    "include_hidden": {"type": "boolean", "description": "是否包含隐藏文件"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stat_file",
            "description": "查看文件或目录的类型、大小、创建时间和修改时间。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "路径"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "搜索文件名、文件内容或代码定义。支持 mode=file/text/code、scope=workspace/user/both、上下文行和 fd/rg 加速。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词或正则"},
                    "root": {"type": "string", "description": "搜索根目录，默认项目根"},
                    "mode": {"type": "string", "enum": ["file", "name", "text", "content", "code"], "description": "搜索模式"},
                    "scope": {"type": "string", "enum": ["workspace", "user", "both"], "description": "搜索范围，默认 workspace；root 非空时优先使用 root"},
                    "file_glob": {"type": "string", "description": "文件名 glob 过滤，如 *.py"},
                    "max_results": {"type": "integer", "description": "最大结果数，默认 50，上限 500"},
                    "context_lines": {"type": "integer", "description": "匹配行上下文行数，默认 0，上限 20"},
                    "include_hidden": {"type": "boolean", "description": "是否搜索隐藏文件"},
                    "regex": {"type": "boolean", "description": "query 是否按正则处理"},
                    "encoding": {"type": "string", "description": "编码，默认 utf-8"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "copy_file",
            "description": "复制文件。目标必须是完整文件路径；默认不覆盖。",
            "parameters": {
                "type": "object",
                "properties": {
                    "src_path": {"type": "string", "description": "源文件路径"},
                    "dst_path": {"type": "string", "description": "目标文件路径"},
                    "overwrite": {"type": "boolean", "description": "是否覆盖已存在目标"},
                },
                "required": ["src_path", "dst_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": "移动或重命名文件。目标必须是完整文件路径；默认不覆盖。",
            "parameters": {
                "type": "object",
                "properties": {
                    "src_path": {"type": "string", "description": "源文件路径"},
                    "dst_path": {"type": "string", "description": "目标文件路径"},
                    "overwrite": {"type": "boolean", "description": "是否覆盖已存在目标"},
                },
                "required": ["src_path", "dst_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "make_dir",
            "description": "创建目录，默认递归创建父目录且目录已存在时不报错。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径"},
                    "parents": {"type": "boolean", "description": "是否递归创建父目录，默认 true"},
                    "exist_ok": {"type": "boolean", "description": "目录已存在时是否视为成功，默认 true"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "删除文件，严格禁止删除目录。沙箱外删除需要 VOTX_FILE_OUTSIDE_SANDBOX=1 或 VOTX_FILE_DELETE_OUTSIDE_SANDBOX=1。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "要删除的文件路径"},
                },
                "required": ["path"],
            },
        },
    },
]

HANDLERS = {
    "read_file": read_file,
    "read_file_range": read_file_range,
    "write_file": write_file,
    "append_file": append_file,
    "edit_file": edit_file,
    "list_dir": list_dir,
    "tree_dir": tree_dir,
    "stat_file": stat_file,
    "search_files": search_files,
    "copy_file": copy_file,
    "move_file": move_file,
    "make_dir": make_dir,
    "delete_file": delete_file,
}


def register():
    """注册所有文件操作函数。"""
    for s in SCHEMAS:
        name = s["function"]["name"]
        register_tool(s, HANDLERS[name])
