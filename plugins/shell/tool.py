"""系统命令执行工具 — subprocess 安全模式"""
import os
import re
import time
import subprocess
import threading
from pathlib import Path
from run.tool import register_tool
from run.io_utils import atomic_write_json, decode_subprocess_output, read_json_safe, utf8_subprocess_env
from plugins._common import (
    err,
    truncate,
    check_dangerous_command,
    check_sandbox,
    safe_path,
    sanitize_env,
    get_current_user_dir,
    get_effective_tool_timeout,
)

_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SENSITIVE_ENV_MARKERS = ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH", "CREDENTIAL")
_SESSION_ID_RE = re.compile(r"^[^\x00-\x1f\x7f]+$")
_SESSION_STATE_VERSION = 2
_SESSION_HISTORY_LIMIT = 200
_SESSION_MAX_COUNT = 50
_SESSION_LOCK = threading.RLock()
_SESSION_CACHE: dict[str, dict] = {}


def _utc_timestamp() -> float:
    """返回 UTC 时间戳。"""
    return time.time()


def _normalize_timestamp(value) -> float:
    """归一化时间戳；非法值回退到当前时间。"""
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return _utc_timestamp()
    if timestamp <= 0:
        return _utc_timestamp()
    return timestamp


def _normalize_timeout(value) -> int:
    """把超时参数归一化为正整数；无效值返回 0。"""
    try:
        timeout = int(value)
    except (TypeError, ValueError):
        return 0
    return timeout if timeout > 0 else 0


def _normalize_session_id(session_id: str | None) -> str:
    """归一化 session_id；空值返回空串。"""
    sid = str(session_id or "").strip()
    if not sid:
        return ""
    if len(sid) > 128:
        raise ValueError("session_id 过长")
    if not _SESSION_ID_RE.match(sid):
        raise ValueError("session_id 含有非法字符")
    return sid


def _session_scope_key(user_dir: str | None) -> str:
    """生成会话缓存键。"""
    if not user_dir:
        return "__global__"
    try:
        return str(Path(user_dir).resolve())
    except Exception:
        return str(user_dir)


def _session_store_path(user_dir: str | None) -> Path | None:
    """返回会话持久化文件路径。"""
    if not user_dir:
        return None
    return Path(user_dir) / "history" / "shell_sessions.json"


def _normalize_env_updates(values: dict | None) -> dict[str, str]:
    """验证并归一化要写入会话或子进程的环境变量。"""
    if not values:
        return {}
    if not isinstance(values, dict):
        raise ValueError("env 必须是 JSON object")

    env: dict[str, str] = {}
    for key, value in values.items():
        if not isinstance(key, str) or not _ENV_KEY_RE.fullmatch(key):
            raise ValueError(f"无效环境变量名: {key}")
        key_upper = key.upper()
        if any(marker in key_upper for marker in _SENSITIVE_ENV_MARKERS):
            raise ValueError(f"不允许设置敏感环境变量: {key}")
        env[key] = "" if value is None else str(value)
    return env


def _merge_environment(session_env: dict | None = None, call_env: dict | None = None) -> dict[str, str]:
    """构造子进程环境，并合并会话级环境与调用级环境。"""
    env = utf8_subprocess_env(sanitize_env())
    env.update(_normalize_env_updates(session_env))
    env.update(_normalize_env_updates(call_env))
    return env


def _resolve_call_working_dir(working_dir: str = "") -> tuple[str | None, str | None]:
    """解析调用级工作目录。"""
    text = (working_dir or "").strip()
    if not text:
        current = get_current_user_dir()
        if current:
            try:
                p = Path(current).resolve()
                if p.exists() and p.is_dir() and check_sandbox(p) is not None:
                    return str(p), None
            except Exception:
                pass
        return None, None

    p = safe_path(text)
    if p is None:
        return None, f"无效工作目录: {working_dir}"
    if not p.exists():
        return None, f"工作目录不存在: {p}"
    if not p.is_dir():
        return None, f"工作目录不是目录: {p}"
    if check_sandbox(p) is None:
        return None, f"工作目录越权: {p}"
    return str(p), None


def _resolve_cd_target(
    path_text: str,
    current_dir: str | None,
    allow_empty: bool = True,
) -> tuple[str | None, str | None]:
    """把 cd 目标解析为受限的绝对目录。"""
    target = _strip_matching_quotes(path_text.strip())
    if not target:
        if not allow_empty:
            return None, "目录为空"
        home = get_current_user_dir() or current_dir or os.getcwd()
        p = Path(home).resolve()
        if p.exists() and p.is_dir() and check_sandbox(p) is not None:
            return str(p), None
        return None, "默认目录不可用"

    base = Path(current_dir or get_current_user_dir() or os.getcwd())
    candidate = Path(target)
    if not candidate.is_absolute():
        candidate = base / candidate

    try:
        resolved = candidate.resolve()
    except Exception as e:
        return None, f"无效工作目录: {e}"

    if not resolved.exists():
        return None, f"工作目录不存在: {resolved}"
    if not resolved.is_dir():
        return None, f"工作目录不是目录: {resolved}"
    if check_sandbox(resolved) is None:
        return None, f"工作目录越权: {resolved}"
    return str(resolved), None


def _format_output(stdout: str, stderr: str, returncode: int) -> str:
    """统一格式化命令输出。"""
    if stdout and stderr:
        output = f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
    else:
        output = stdout or stderr or ""

    if output:
        if returncode != 0:
            output = f"{output}\n(exit={returncode})"
    else:
        output = f"(exit={returncode})"
    return output


def _normalize_session_state(data: dict | None, cwd_hint: str | None = None) -> dict:
    """Normalize persisted session state."""
    state = data if isinstance(data, dict) else {}
    cwd = str(state.get("cwd") or cwd_hint or get_current_user_dir() or os.getcwd())
    previous_cwd = state.get("previous_cwd")
    env = _normalize_env_updates(state.get("env") if isinstance(state.get("env"), dict) else {})
    history = state.get("history")
    if not isinstance(history, list):
        history = []
    history = [str(item) for item in history if str(item).strip()]
    if len(history) > _SESSION_HISTORY_LIMIT:
        history = history[-_SESSION_HISTORY_LIMIT:]
    return {
        "version": _SESSION_STATE_VERSION,
        "cwd": cwd,
        "previous_cwd": str(previous_cwd) if previous_cwd else "",
        "env": env,
        "history": history,
        "last_access": _normalize_timestamp(state.get("last_access")),
    }


def _load_session_store(user_dir: str | None) -> dict:
    """Load the current user's session store."""
    key = _session_scope_key(user_dir)
    with _SESSION_LOCK:
        if key in _SESSION_CACHE:
            return _SESSION_CACHE[key]

        path = _session_store_path(user_dir)
        raw = read_json_safe(path, default=None) if path else None
        sessions: dict[str, dict] = {}
        if isinstance(raw, dict):
            raw_sessions = raw.get("sessions", {})
            if isinstance(raw_sessions, dict):
                for sid, data in raw_sessions.items():
                    sid_text = str(sid).strip() or str(sid)
                    if not sid_text:
                        continue
                    sessions[sid_text] = _normalize_session_state(data)

        store = {"version": _SESSION_STATE_VERSION, "sessions": sessions}
        _SESSION_CACHE[key] = store
        return store


def _save_session_store(user_dir: str | None, store: dict):
    """Persist the session store."""
    path = _session_store_path(user_dir)
    if not path:
        return
    try:
        atomic_write_json(path, store, indent=2)
    except Exception:
        pass


def _prune_session_store(store: dict, keep_session_id: str | None = None) -> list[str]:
    """Trim the session store to the configured limit."""
    sessions = store.setdefault("sessions", {})
    if not isinstance(sessions, dict):
        store["sessions"] = {}
        return []

    if len(sessions) <= _SESSION_MAX_COUNT:
        return []

    keep_key = str(keep_session_id or "").strip()
    candidates: list[tuple[float, str]] = []
    for sid, data in list(sessions.items()):
        sid_text = str(sid).strip() or str(sid)
        if keep_key and sid_text == keep_key:
            continue
        normalized = _normalize_session_state(data)
        sessions[sid_text] = normalized
        candidates.append((normalized["last_access"], sid_text))

    overflow = len(sessions) - _SESSION_MAX_COUNT
    if overflow <= 0:
        return []

    candidates.sort(key=lambda item: (item[0], item[1]))
    removed: list[str] = []
    for _, sid_text in candidates[:overflow]:
        if sessions.pop(sid_text, None) is not None:
            removed.append(sid_text)
    return removed


def _get_session_state(
    user_dir: str | None,
    session_id: str,
    cwd_hint: str | None = None,
    reset_session: bool = False,
) -> dict:
    """Get or create a session state."""
    store = _load_session_store(user_dir)
    with _SESSION_LOCK:
        sessions = store.setdefault("sessions", {})
        state = {} if reset_session else sessions.get(session_id, {})
        normalized = _normalize_session_state(state, cwd_hint=cwd_hint)
        if cwd_hint:
            normalized["cwd"] = cwd_hint
        normalized["last_access"] = _utc_timestamp()
        sessions[session_id] = normalized
        removed = _prune_session_store(store, keep_session_id=session_id)
        _SESSION_CACHE[_session_scope_key(user_dir)] = store
        if removed:
            _save_session_store(user_dir, store)
        return normalized


def _persist_session_state(user_dir: str | None, session_id: str, state: dict):
    """Write back session state and keep the store trimmed."""
    store = _load_session_store(user_dir)
    with _SESSION_LOCK:
        sessions = store.setdefault("sessions", {})
        normalized = _normalize_session_state(state)
        normalized["last_access"] = _utc_timestamp()
        sessions[session_id] = normalized
        _prune_session_store(store, keep_session_id=session_id)
        _SESSION_CACHE[_session_scope_key(user_dir)] = store
        _save_session_store(user_dir, store)


def _session_history_text(history: list[str], limit: int | None = None) -> str:
    """格式化会话历史。"""
    items = history if limit is None or limit <= 0 else history[-limit:]
    if not items:
        return "(empty)"
    start = len(history) - len(items) + 1
    return "\n".join(f"{i}. {cmd}" for i, cmd in enumerate(items, start))


def _split_shell_words(text: str) -> list[str]:
    """Split a shell-like segment into words without POSIX backslash rules."""
    words: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    token_started = False
    i = 0

    while i < len(text):
        ch = text[i]
        if in_single:
            token_started = True
            if ch == "'":
                in_single = False
            else:
                buf.append(ch)
            i += 1
            continue

        if in_double:
            token_started = True
            if ch == "\\" and i + 1 < len(text) and text[i + 1] in {'"', "\\"}:
                buf.append(text[i + 1])
                i += 2
                continue
            if ch == '"' and i + 1 < len(text) and text[i + 1] == '"':
                buf.append('"')
                i += 2
                continue
            if ch == '"':
                in_double = False
                i += 1
                continue
            buf.append(ch)
            i += 1
            continue

        if ch.isspace():
            if token_started:
                words.append("".join(buf))
                buf = []
                token_started = False
            i += 1
            continue

        if ch == "'":
            in_single = True
            token_started = True
            i += 1
            continue

        if ch == '"':
            in_double = True
            token_started = True
            i += 1
            continue

        buf.append(ch)
        token_started = True
        i += 1

    if in_single or in_double:
        raise ValueError("引号未闭合")
    if token_started:
        words.append("".join(buf))
    return words


def _split_command_chain(command: str) -> list[tuple[str | None, str]]:
    """Split a command chain on top-level &&, || and ; separators."""
    parts: list[tuple[str | None, str]] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    current_op: str | None = None
    token_started = False
    i = 0

    while i < len(command):
        ch = command[i]
        if in_single:
            buf.append(ch)
            if ch == "'":
                in_single = False
            i += 1
            continue

        if in_double:
            token_started = True
            if ch == "\\" and i + 1 < len(command) and command[i + 1] in {'"', "\\"}:
                buf.append(ch)
                buf.append(command[i + 1])
                i += 2
                continue
            if ch == '"' and i + 1 < len(command) and command[i + 1] == '"':
                buf.append('"')
                buf.append('"')
                i += 2
                continue
            buf.append(ch)
            if ch == '"':
                in_double = False
            i += 1
            continue

        if command.startswith("&&", i) or command.startswith("||", i):
            segment = "".join(buf).strip()
            if segment or token_started:
                parts.append((current_op, segment))
            buf = []
            token_started = False
            current_op = command[i : i + 2]
            i += 2
            continue

        if ch == ";":
            segment = "".join(buf).strip()
            if segment or token_started:
                parts.append((current_op, segment))
            buf = []
            token_started = False
            current_op = ";"
            i += 1
            continue

        buf.append(ch)
        token_started = True
        if ch == "'":
            in_single = True
        elif ch == '"':
            in_double = True
        i += 1

    if in_single or in_double:
        raise ValueError("引号未闭合")

    segment = "".join(buf).strip()
    if segment or token_started or not parts:
        parts.append((current_op, segment))
    return parts


def _strip_matching_quotes(text: str) -> str:
    """去掉首尾成对引号。"""
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        return text[1:-1]
    return text


def _parse_cd_segment(segment: str, current_dir: str | None) -> tuple[str | None, bool, str | None]:
    """解析 cd/chdir/pwd 片段。"""
    try:
        tokens = _split_shell_words(segment)
    except ValueError as e:
        return None, False, f"命令解析失败: {e}"

    if not tokens:
        return None, False, "命令为空"

    head = tokens[0].lower()
    if head == "pwd":
        return current_dir or get_current_user_dir() or os.getcwd(), True, None
    if head not in {"cd", "chdir"}:
        return None, False, None

    args = tokens[1:]
    if args and args[0].lower() in {"/d", "-d"}:
        args = args[1:]
    target, err_msg = _resolve_cd_target(" ".join(args), current_dir, allow_empty=False)
    if err_msg:
        return None, False, err_msg
    return target, False, None


def _run_command_segment(
    segment: str,
    cwd: str | None,
    timeout: int,
    stdin_text: str,
    env: dict[str, str],
) -> tuple[str, bool]:
    """执行单个非链式命令片段。"""
    try:
        args = _split_shell_words(segment)
    except ValueError as e:
        return err(f"命令解析失败: {e}"), False

    if not args:
        return err("命令为空"), False

    try:
        r = subprocess.run(
            args,
            shell=False,
            capture_output=True,
            input=stdin_text.encode("utf-8") if stdin_text else None,
            timeout=timeout,
            cwd=cwd,
            env=env,
        )
        stdout = decode_subprocess_output(r.stdout).strip()
        stderr = decode_subprocess_output(r.stderr).strip()
        return _format_output(stdout, stderr, r.returncode), r.returncode == 0
    except FileNotFoundError:
        return err(f"命令未找到: {args[0]}"), False
    except subprocess.TimeoutExpired:
        return err(f"命令超时 ({timeout}s)"), False
    except Exception as e:
        return err(f"执行失败: {e}"), False


def _format_session_env(env: dict[str, str]) -> str:
    """格式化会话环境变量。"""
    if not env:
        return "(empty)"
    lines = [f"{k}={v}" for k, v in sorted(env.items(), key=lambda item: item[0].lower())]
    return "\n".join(lines)


def _parse_env_assignments(tokens: list[str]) -> tuple[dict[str, str] | None, str | None]:
    """解析 export/set/env 的赋值参数。"""
    updates: dict[str, str] = {}
    for token in tokens:
        if "=" not in token:
            return None, f"无效环境变量赋值: {token}"
        key, value = token.split("=", 1)
        updates[key] = _strip_matching_quotes(value)
    try:
        return _normalize_env_updates(updates), None
    except ValueError as e:
        return None, str(e)


def _handle_shell_builtin(
    segment: str,
    state: dict,
    *,
    allow_history: bool = False,
) -> tuple[bool, str, bool]:
    """处理 shell 内建命令。"""
    try:
        tokens = _split_shell_words(segment)
    except ValueError as e:
        return True, err(f"命令解析失败: {e}"), False

    if not tokens:
        return True, err("命令为空"), False

    head = tokens[0].lower()
    args = tokens[1:]
    cwd = str(state.get("cwd") or get_current_user_dir() or os.getcwd())

    if head == "pwd":
        return True, cwd, True

    if head in {"cd", "chdir"}:
        if args and args[0].lower() in {"/d", "-d"}:
            args = args[1:]
        if args and args[0] == "-":
            previous = str(state.get("previous_cwd") or "").strip()
            if not previous:
                return True, err("没有可切换的上一个目录"), False
            target = previous
        else:
            target_text = " ".join(args)
            target, cd_err = _resolve_cd_target(target_text, cwd, allow_empty=True)
            if cd_err:
                return True, err(cd_err), False
        state["previous_cwd"] = cwd
        state["cwd"] = target
        return True, "", True

    if head in {"export", "set", "env"}:
        if not args:
            return True, _format_session_env(state.get("env", {})), True
        updates, env_err = _parse_env_assignments(args)
        if env_err:
            return True, err(env_err), False
        env_state = state.setdefault("env", {})
        env_state.update(updates or {})
        return True, f"OK: {', '.join(sorted((updates or {}).keys()))}", True

    if head in {"unset", "unsetenv"}:
        if not args:
            return True, err("unset 需要至少一个变量名"), False
        env_state = state.setdefault("env", {})
        removed = []
        for name in args:
            key = _strip_matching_quotes(name)
            if not _ENV_KEY_RE.fullmatch(key):
                return True, err(f"无效环境变量名: {key}"), False
            if key in env_state:
                env_state.pop(key, None)
                removed.append(key)
        if not removed:
            return True, "(empty)", True
        return True, f"OK: {', '.join(removed)}", True

    if head == "history":
        if not allow_history:
            return False, "", True
        history = list(state.get("history", []))
        if args and args[0] in {"-c", "clear"}:
            state["history"] = []
            return True, "OK: history cleared", True
        if args:
            first = args[0]
            try:
                limit = int(first)
            except ValueError:
                limit = 0
            if limit > 0:
                return True, _session_history_text(history, limit), True
        return True, _session_history_text(history), True

    return False, "", True


def _run_shell_chain(
    command: str,
    state: dict,
    timeout: int,
    stdin_text: str,
    call_env: dict | None = None,
    *,
    allow_history: bool = False,
) -> str:
    """执行一条 shell 风格命令链。"""
    try:
        parts = _split_command_chain(command)
    except ValueError as e:
        return err(f"命令解析失败: {e}")

    current_dir = str(state.get("cwd") or get_current_user_dir() or os.getcwd())
    pending_stdin = stdin_text
    outputs: list[str] = []
    last_ok = True

    for op, segment in parts:
        segment = segment.strip()
        if not segment:
            continue

        danger_err = check_dangerous_command(segment)
        if danger_err:
            return err(danger_err)

        if op == "&&" and not last_ok:
            continue
        if op == "||" and last_ok:
            continue

        recognized, builtin_output, builtin_ok = _handle_shell_builtin(
            segment,
            state,
            allow_history=allow_history,
        )
        current_dir = str(state.get("cwd") or current_dir)
        if recognized:
            if builtin_output:
                outputs.append(builtin_output)
            last_ok = builtin_ok
            continue

        env = _merge_environment(state.get("env"), call_env)
        output, ok = _run_command_segment(
            segment,
            current_dir,
            timeout,
            pending_stdin,
            env,
        )
        pending_stdin = ""
        if output:
            outputs.append(output)
        last_ok = ok

    result = "\n".join(item for item in outputs if item)
    if not result:
        result = current_dir
    return truncate(result, max_len=100000)


def _run_cd_chain(
    segments: list[str],
    cwd: str | None,
    timeout: int,
    stdin_text: str,
    env: dict[str, str],
) -> str:
    """执行以 cd/chdir 开头的受限命令链。"""
    current_dir = cwd or get_current_user_dir() or os.getcwd()
    outputs: list[str] = []
    pending_stdin = stdin_text
    consumed_command = False

    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue

        danger_err = check_dangerous_command(segment)
        if danger_err:
            return err(danger_err)

        target_dir, cd_only, cd_err = _parse_cd_segment(segment, current_dir)
        if cd_err:
            return err(cd_err)
        if target_dir is not None:
            current_dir = target_dir
            continue

        output, success = _run_command_segment(segment, current_dir, timeout, pending_stdin, env)
        consumed_command = True
        pending_stdin = ""
        if output:
            outputs.append(output)
        if not success:
            return truncate("\n".join(outputs), max_len=100000)

    if not consumed_command:
        return current_dir
    return truncate("\n".join(outputs), max_len=100000)


def run_command(
    command: str,
    working_dir: str = "",
    timeout: int = 0,
    stdin: str = "",
    env: dict | None = None,
    session_id: str = "",
    reset_session: bool = False,
) -> str:
    """执行系统命令"""
    if not command.strip():
        return err("命令为空")

    # 安全检查：危险命令拦截
    danger_err = check_dangerous_command(command)
    if danger_err:
        return err(danger_err)

    # cmd.exe /c 时注入 UTF-8 代码页，防止中文路径乱码
    cmd = command.strip()
    if cmd[:4].lower() == "cmd " or cmd[:8].lower() == "cmd.exe ":
        m = re.match(r'(cmd(\.exe)?)\s+(/[ck])\s+', cmd, re.IGNORECASE)
        if m:
            rest = cmd[m.end():].strip()
            # 去掉已有的外层引号
            if rest.startswith('"') and rest.endswith('"'):
                rest = rest[1:-1]
            # 转义内部双引号防止命令注入
            rest_escaped = rest.replace('"', '""')
            cmd = f'{m.group(1)} {m.group(3)} "chcp 65001 > nul & {rest_escaped}"'

    try:
        timeout_value = _normalize_timeout(timeout) or get_effective_tool_timeout(120)
        stdin_text = "" if stdin is None else str(stdin)
        call_env = _normalize_env_updates(env)
        resolved_cwd, cwd_err = _resolve_call_working_dir(working_dir)
        if cwd_err:
            return err(cwd_err)
        session_key = _normalize_session_id(session_id)
    except ValueError as e:
        return err(str(e))

    if session_key:
        user_dir = get_current_user_dir()
        state = _get_session_state(user_dir, session_key, cwd_hint=resolved_cwd, reset_session=reset_session)
        if resolved_cwd:
            state["cwd"] = resolved_cwd
        result = _run_shell_chain(
            cmd,
            state,
            timeout_value,
            stdin_text,
            call_env,
            allow_history=True,
        )
        history = state.setdefault("history", [])
        history.append(cmd)
        if len(history) > _SESSION_HISTORY_LIMIT:
            state["history"] = history[-_SESSION_HISTORY_LIMIT:]
        _persist_session_state(user_dir, session_key, state)
        return result

    state = {
        "version": _SESSION_STATE_VERSION,
        "cwd": resolved_cwd or get_current_user_dir() or os.getcwd(),
        "previous_cwd": "",
        "env": {},
        "history": [],
    }
    result = _run_shell_chain(
        cmd,
        state,
        timeout_value,
        stdin_text,
        call_env,
        allow_history=False,
    )
    return result


SCHEMA = {
    "type": "function",
    "function": {
        "name": "run_command",
        "description": (
            "执行系统命令。subprocess 安全模式。支持 working_dir、stdin、env、timeout 和 session_id。"
            "会话模式下 cwd/env/history 跨调用保留，可用 cd/chdir/pwd/export/unset/history，并支持 &&/||/; 命令链。"
            "超时遵循 tool.tool_timeout（用户配置 > 全局配置 > 内置默认）。Windows 下自动处理编码。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令（自定义 shell-like 解析）"},
                "working_dir": {"type": "string", "description": "工作目录（可选，默认用户目录）"},
                "timeout": {
                    "type": "integer",
                    "description": "单次命令超时（秒），0 表示使用配置值",
                },
                "stdin": {"type": "string", "description": "传给命令的标准输入文本"},
                "env": {
                    "type": "object",
                    "description": "附加环境变量；敏感键会被拒绝",
                },
                "session_id": {
                    "type": "string",
                    "description": "会话标识；相同 session_id 共享 cwd/env/history",
                },
                "reset_session": {
                    "type": "boolean",
                    "description": "是否重置指定 session_id 的状态",
                },
            },
            "required": ["command"],
        },
    },
}


def register():
    """处理 register 相关逻辑。"""
    register_tool(SCHEMA, run_command)
