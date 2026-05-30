"""文件搜索工具 — 使用 fd/rg 快速搜索文件名和内容，无 fd/rg 时回退到 Python 实现"""
import os
import re
import subprocess
from pathlib import Path

from run.tool import register_tool
from plugins._common import err, truncate, safe_path, check_sandbox, get_current_user_dir, log_tool_call

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _has_bin(name: str) -> bool:
    """检查命令行工具是否可用"""
    try:
        r = subprocess.run(
            ["which", name] if os.name != "nt" else ["where", name],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


def _get_search_roots(scope: str, root: str) -> list[Path]:
    """根据 scope 和 root 参数返回搜索根目录列表"""
    roots: list[Path] = []
    if scope in ("workspace", "both"):
        p = safe_path(root) if root else _PROJECT_ROOT
        if p and check_sandbox(p):
            roots.append(p)
    if scope in ("user", "both"):
        user_dir = get_current_user_dir()
        if user_dir:
            p = safe_path(user_dir)
            if p and check_sandbox(p):
                roots.append(p)
    if not roots:
        roots.append(_PROJECT_ROOT)
    return roots


def _search_files_fd(pattern: str, roots: list[Path], max_results: int) -> str:
    """使用 fd 搜索文件名"""
    results = []
    try:
        cmd = ["fd", "--max-results", str(max_results)]
        if pattern:
            cmd.extend(["--glob", pattern])
        for root in roots:
            r = subprocess.run(
                cmd + [str(root)], capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                for line in r.stdout.strip().split("\n"):
                    if line:
                        results.append(line)
            elif r.returncode == 1:
                continue  # no matches
            else:
                return err(f"fd 错误: {r.stderr.strip()}")
        return "\n".join(results) if results else "未找到匹配的文件"
    except FileNotFoundError:
        return "__FALLBACK__"
    except subprocess.TimeoutExpired:
        return "__FALLBACK__"
    except Exception:
        return "__FALLBACK__"


def _search_files_python(pattern: str, roots: list[Path], max_results: int, file_glob: str) -> str:
    """使用 Python os.walk + re 搜索文件名（fd 回退方案）"""
    results = []
    try:
        glob_re = None
        if file_glob:
            glob_re = re.compile(file_glob.replace("*", ".*").replace("?", "."))
        pat_re = re.compile(pattern, re.IGNORECASE) if pattern else None
    except re.error as e:
        return err(f"正则/glob 表达式无效: {e}")

    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(str(root), onerror=lambda e: None):
            # 跳过隐藏目录
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fname in filenames:
                if len(results) >= max_results:
                    break
                full_path = os.path.join(dirpath, fname)
                # 跳过隐藏文件
                if fname.startswith("."):
                    continue
                # glob 过滤
                if glob_re and not glob_re.search(fname):
                    continue
                # 模式过滤
                if pat_re and not pat_re.search(fname):
                    continue
                results.append(full_path)
            if len(results) >= max_results:
                break
        if len(results) >= max_results:
            break

    return "\n".join(results) if results else "未找到匹配的文件"


def _search_text_rg(query: str, roots: list[Path], max_results: int, context_lines: int, file_glob: str) -> str:
    """使用 rg 搜索文件内容"""
    results = []
    try:
        cmd = ["rg", "--line-number", "--max-count", str(max_results)]
        if context_lines > 0:
            cmd.extend(["-C", str(context_lines)])
        if file_glob:
            cmd.extend(["--glob", file_glob])
        cmd.append(query)
        for root in roots:
            r = subprocess.run(
                cmd + [str(root)], capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                results.append(r.stdout.strip())
            elif r.returncode == 1:
                continue  # no matches in this root
            else:
                return err(f"rg 错误: {r.stderr.strip()}")
        output = "\n--\n".join(results) if results else "未找到匹配的内容"
        return truncate(output, max_len=50000)
    except FileNotFoundError:
        return "__FALLBACK__"
    except subprocess.TimeoutExpired:
        return "__FALLBACK__"
    except Exception:
        return "__FALLBACK__"


def _search_text_python(query: str, roots: list[Path], max_results: int, context_lines: int, file_glob: str) -> str:
    """使用 Python 逐行搜索文件内容（rg 回退方案）"""
    results: list[str] = []
    try:
        pat = re.compile(query, re.IGNORECASE)
    except re.error as e:
        return err(f"正则表达式无效: {e}")

    try:
        glob_re = None
        if file_glob:
            glob_re = re.compile(file_glob.replace("*", ".*").replace("?", "."))
    except re.error as e:
        return err(f"glob 表达式无效: {e}")

    match_count = 0
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(str(root), onerror=lambda e: None):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fname in filenames:
                if match_count >= max_results:
                    break
                if fname.startswith("."):
                    continue
                if glob_re and not glob_re.search(fname):
                    continue
                full_path = os.path.join(dirpath, fname)
                if os.path.getsize(full_path) > 2 * 1024 * 1024:
                    continue  # 跳过大于 2MB 的文件
                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                except Exception:
                    continue
                for i, line in enumerate(lines):
                    if match_count >= max_results:
                        break
                    if pat.search(line):
                        start = max(0, i - context_lines)
                        end = min(len(lines), i + context_lines + 1)
                        ctx = "".join(
                            f"{full_path}:{j+1}:{lines[j]}" for j in range(start, end)
                        )
                        results.append(ctx.strip())
                        match_count += 1
            if match_count >= max_results:
                break
        if match_count >= max_results:
            break

    output = "\n--\n".join(results) if results else "未找到匹配的内容"
    return truncate(output, max_len=50000)


def _search_code_rg(query: str, roots: list[Path], max_results: int, context_lines: int) -> str:
    """使用 rg 搜索代码定义（函数/类等）"""
    results = []
    code_patterns = [
        r"^\s*(def|class|async def)\s+\w*" + re.escape(query) + r"\w*",
        r"^\s*(fn|function|func)\s+\w*" + re.escape(query) + r"\w*",
        r"^\s*(public|private|protected)\s+(static\s+)?(function|class)\s+\w*" + re.escape(query) + r"\w*",
        r"^\s*(const|let|var)\s+\w*" + re.escape(query) + r"\w*\s*=",
        r"^\s*(export\s+)?(default\s+)?(function|class)\s+\w*" + re.escape(query) + r"\w*",
    ]
    pattern_str = "|".join(code_patterns)
    try:
        cmd = ["rg", "--line-number", "--max-count", str(max_results)]
        if context_lines > 0:
            cmd.extend(["-C", str(context_lines)])
        cmd.append(pattern_str)
        for root in roots:
            r = subprocess.run(
                cmd + [str(root)], capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                results.append(r.stdout.strip())
            elif r.returncode == 1:
                continue
            else:
                return err(f"rg 错误: {r.stderr.strip()}")
        output = "\n--\n".join(results) if results else "未找到匹配的代码定义"
        return truncate(output, max_len=50000)
    except FileNotFoundError:
        return "__FALLBACK__"
    except subprocess.TimeoutExpired:
        return "__FALLBACK__"
    except Exception:
        return "__FALLBACK__"


def _search_code_python(query: str, roots: list[Path], max_results: int, context_lines: int) -> str:
    """使用 Python 搜索代码定义（rg 回退方案）"""
    code_patterns = [
        re.compile(r"^\s*(def|class|async def)\s+\w*" + re.escape(query) + r"\w*", re.IGNORECASE),
        re.compile(r"^\s*(fn|function|func)\s+\w*" + re.escape(query) + r"\w*", re.IGNORECASE),
        re.compile(r"^\s*(public|private|protected)\s+(static\s+)?(function|class)\s+\w*" + re.escape(query) + r"\w*", re.IGNORECASE),
        re.compile(r"^\s*(const|let|var)\s+\w*" + re.escape(query) + r"\w*\s*=", re.IGNORECASE),
        re.compile(r"^\s*(export\s+)?(default\s+)?(function|class)\s+\w*" + re.escape(query) + r"\w*", re.IGNORECASE),
    ]

    results: list[str] = []
    match_count = 0
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(str(root), onerror=lambda e: None):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fname in filenames:
                if match_count >= max_results:
                    break
                if fname.startswith("."):
                    continue
                full_path = os.path.join(dirpath, fname)
                if os.path.getsize(full_path) > 2 * 1024 * 1024:
                    continue
                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                except Exception:
                    continue
                for i, line in enumerate(lines):
                    if match_count >= max_results:
                        break
                    if any(pat.search(line) for pat in code_patterns):
                        start = max(0, i - context_lines)
                        end = min(len(lines), i + context_lines + 1)
                        ctx = "".join(
                            f"{full_path}:{j+1}:{lines[j]}" for j in range(start, end)
                        )
                        results.append(ctx.strip())
                        match_count += 1
            if match_count >= max_results:
                break
        if match_count >= max_results:
            break

    output = "\n--\n".join(results) if results else "未找到匹配的代码定义"
    return truncate(output, max_len=50000)


def search_model(
    query: str,
    mode: str = "text",
    scope: str = "workspace",
    root: str = "",
    file_glob: str = "",
    max_results: int = 50,
    context_lines: int = 3,
) -> str:
    """搜索文件系统中名称/内容/代码定义。

    参数:
        query:        搜索关键词/正则表达式（必填）
        mode:         搜索模式 — "file"(文件名) | "text"(文件内容) | "code"(代码定义)
        scope:        搜索范围 — "workspace"(工作区) | "user"(用户目录) | "both"(两者)
        root:         自定义根目录（空串 = 默认工作区根目录）
        file_glob:    文件名 glob 过滤（如 "*.py"）
        max_results:  最大结果数（默认 50）
        context_lines:匹配行的上下文行数（默认 3）
    """
    # 参数校验
    if not query or not query.strip():
        return err("query 参数不能为空")
    query = query.strip()

    if mode not in ("file", "text", "code"):
        return err(f"无效的 mode: {mode}，可选值: file, text, code")

    if scope not in ("workspace", "user", "both"):
        return err(f"无效的 scope: {scope}，可选值: workspace, user, both")

    if max_results < 1 or max_results > 500:
        return err("max_results 需在 1-500 之间")

    if context_lines < 0 or context_lines > 20:
        return err("context_lines 需在 0-20 之间")

    # 获取搜索根目录
    roots = _get_search_roots(scope, root)

    # 根据 mode 选择搜索策略
    if mode == "file":
        if _has_bin("fd"):
            result = _search_files_fd(query if not file_glob else file_glob, roots, max_results)
            if result != "__FALLBACK__":
                return result
        return _search_files_python(query, roots, max_results, file_glob)

    elif mode == "text":
        if _has_bin("rg"):
            result = _search_text_rg(query, roots, max_results, context_lines, file_glob)
            if result != "__FALLBACK__":
                return result
        return _search_text_python(query, roots, max_results, context_lines, file_glob)

    elif mode == "code":
        if _has_bin("rg"):
            result = _search_code_rg(query, roots, max_results, context_lines)
            if result != "__FALLBACK__":
                return result
        return _search_code_python(query, roots, max_results, context_lines)

    return err(f"未知的 mode: {mode}")


SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_model",
        "description": (
            "搜索文件系统中的文件名称、文件内容或代码定义。"
            "支持 fd/rg 加速，自动回退到 Python 实现。"
            "mode=file 搜索文件名，mode=text 搜索文件内容，mode=code 搜索函数/类定义。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或正则表达式（必填）",
                },
                "mode": {
                    "type": "string",
                    "description": "搜索模式: file(文件名), text(文件内容), code(代码定义)",
                    "enum": ["file", "text", "code"],
                    "default": "text",
                },
                "scope": {
                    "type": "string",
                    "description": "搜索范围: workspace(工作区), user(用户目录), both(两者)",
                    "enum": ["workspace", "user", "both"],
                    "default": "workspace",
                },
                "root": {
                    "type": "string",
                    "description": "自定义根目录路径（空串使用默认工作区根目录）",
                    "default": "",
                },
                "file_glob": {
                    "type": "string",
                    "description": "文件名 glob 过滤，如 *.py、*.js",
                    "default": "",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大结果数 (1-500，默认 50)",
                    "default": 50,
                },
                "context_lines": {
                    "type": "integer",
                    "description": "匹配行的上下文行数 (0-20，默认 3)",
                    "default": 3,
                },
            },
            "required": ["query"],
        },
    },
}


def register():
    """注册 search_model 工具到全局工具表"""
    register_tool(SCHEMA, search_model)
