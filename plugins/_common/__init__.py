"""skills 公共模块 — err / safe_path / check_sandbox / SSRF 防护 / 命令安全 / log_tool_call"""
import ipaddress
import json
import os
import re as _re
import socket
import uuid
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse as _urlparse

from run.io_utils import append_jsonl

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# skills/_common/__init__.py → skills/_common → skills → 项目根
_CURRENT_USER_DIR: ContextVar[str | None] = ContextVar("votx_current_user_dir", default=None)

# 多模态上下文 — session 级 provider 注入（所有 multimodal plugin 共用）
_MULTIMODAL_CTX: ContextVar = ContextVar("multimodal_ctx", default=None)


def set_multimodal_context(provider, chat=None, user_name: str = ""):
    """注入当前会话的 provider 上下文。供所有 multimodal plugin 使用。
    由 web/session.py、main.py、start.py、cron/scheduler.py 在会话初始化时调用。
    """
    _MULTIMODAL_CTX.set({"provider": provider, "chat": chat, "user_name": user_name})


def get_multimodal_context() -> dict | None:
    """获取当前会话的 multimodal 上下文（provider/chat/user_name）。"""
    return _MULTIMODAL_CTX.get()


def err(msg: str) -> str:
    """处理 err 相关逻辑。"""
    return f"ERROR: {msg}"


def truncate(text: str, max_len: int = 0) -> str:
    """截断文本到指定长度。max_len=0 表示不限制（兼容旧调用方）。"""
    if max_len > 0 and len(text) > max_len:
        return text[:max_len] + f"\n... (截断，共 {len(text)} 字符)"
    return text


def set_current_user_dir(user_dir: str | None) -> Token:
    """绑定当前工具执行上下文的用户目录，避免多用户 Web 会话互相串日志。"""
    return _CURRENT_USER_DIR.set(user_dir)


def reset_current_user_dir(token: Token):
    """处理 reset_current_user_dir 相关逻辑。"""
    _CURRENT_USER_DIR.reset(token)


def get_current_user_dir() -> str:
    """优先返回当前工具上下文中的用户目录，兼容旧的 VOTX_USER_DIR 环境变量。"""
    return _CURRENT_USER_DIR.get() or os.environ.get("VOTX_USER_DIR", "")


def _positive_int(value) -> int | None:
    """将配置值解析为正整数；无效值返回 None。"""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _read_tool_timeout_config(path: Path) -> int | None:
    """从配置文件读取 tool.tool_timeout。"""
    try:
        if not path.exists():
            return None
        config = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            return None
        tool_cfg = config.get("tool", {})
        if not isinstance(tool_cfg, dict):
            return None
        return _positive_int(tool_cfg.get("tool_timeout"))
    except Exception:
        return None


def get_effective_tool_timeout(default: int = 120) -> int:
    """获取工具内部超时。

    优先级：当前用户配置 users/<name>/config.json 的 tool.tool_timeout >
    全局配置 config/config_core.json 的 tool.tool_timeout > 工具传入的内置默认值。
    """
    fallback = _positive_int(default) or 120

    user_dir = get_current_user_dir()
    if user_dir:
        timeout = _read_tool_timeout_config(Path(user_dir) / "config.json")
        if timeout is not None:
            return timeout

    timeout = _read_tool_timeout_config(_PROJECT_ROOT / "config" / "config_core.json")
    if timeout is not None:
        return timeout

    return fallback


# ---- 路径安全 ----

def safe_path(raw_path: str) -> Path | None:
    """解析路径。相对路径以项目根为基准，避免依赖不确定的 cwd。"""
    try:
        p = Path(raw_path)
        if not p.is_absolute():
            p = _PROJECT_ROOT / p
        return p.resolve()
    except Exception:
        return None


def check_sandbox(p: Path, allowed_roots: list | None = None) -> Path | None:
    """检查路径是否在允许的根目录内。返回 resolved Path 或 None。

    默认允许项目根目录和当前用户目录。使用 realpath/resolve 后再判断，
    防止通过符号链接或 .. 跳出沙箱。
    """
    try:
        resolved = p.resolve()
    except Exception:
        return None
    roots = [Path(x) for x in (allowed_roots or []) if x]
    if not roots:
        roots.append(_PROJECT_ROOT)
        user_dir = get_current_user_dir()
        if user_dir:
            roots.append(Path(user_dir))
    for root in roots:
        try:
            resolved_root = root.resolve()
        except Exception:
            continue
        if resolved == resolved_root or resolved.is_relative_to(resolved_root):
            return resolved
    return None


# ---- SSRF 防护 ----

_LOCAL_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("0.0.0.0/32"),
    ipaddress.ip_network("::/128"),
]

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

_CLOUD_METADATA_IPS = {
    "169.254.169.254",
    "fd00:ec2::254",
}

_NETWORK_SCOPES = {"public", "local", "private", "all"}

MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB


def _normalize_network_scope(network_scope: str | None) -> str:
    """标准化网络访问范围。未知值按 public 处理。"""
    scope = (network_scope or "public").strip().lower()
    if scope not in _NETWORK_SCOPES:
        return "public"
    return scope


def classify_ip_scope(addr_str: str) -> str:
    """返回 IP 所属网络范围: public/local/private/metadata。"""
    addr_str = str(addr_str).split("%", 1)[0]
    try:
        addr = ipaddress.ip_address(addr_str)
    except ValueError:
        return "public"

    if str(addr) in _CLOUD_METADATA_IPS:
        return "metadata"
    for net in _LOCAL_NETWORKS:
        if addr in net:
            return "local"
    for net in _PRIVATE_NETWORKS:
        if addr in net:
            return "private"
    return "public"


def _scope_allows(address_scope: str, network_scope: str) -> bool:
    """判断 network_scope 是否允许访问某类地址。"""
    if address_scope == "metadata":
        return False
    if network_scope == "all":
        return address_scope in {"public", "local", "private"}
    return address_scope == network_scope


def inspect_url(url: str, network_scope: str | None = "public") -> dict:
    """解析并校验 URL，返回错误、地址范围和解析出的 IP 信息。"""
    effective_scope = _normalize_network_scope(network_scope)
    result = {
        "error": None,
        "url": url,
        "host": "",
        "network_scope": effective_scope,
        "address_scope": "",
        "resolved_ips": [],
    }
    try:
        parsed = _urlparse(url)
    except Exception:
        result["error"] = "无效的 URL 格式"
        return result

    if parsed.scheme not in ("http", "https"):
        result["error"] = f"不支持的协议: {parsed.scheme}，仅允许 http/https"
        return result

    host = parsed.hostname
    if not host:
        result["error"] = "URL 缺少主机名"
        return result
    result["host"] = host

    host_lower = host.lower().rstrip(".")
    if host_lower == "localhost":
        result["resolved_ips"] = ["127.0.0.1", "::1"]
        result["address_scope"] = "local"
        if not _scope_allows("local", effective_scope):
            result["error"] = f"当前 network_scope={effective_scope} 不允许访问本地地址: {host}"
        return result

    resolved_ips: list[str] = []
    try:
        for info in socket.getaddrinfo(host, None, 0, socket.SOCK_STREAM):
            addr_str = info[4][0]
            if addr_str not in resolved_ips:
                resolved_ips.append(addr_str)
    except socket.gaierror:
        result["error"] = f"无法解析域名: {host}"
        return result

    result["resolved_ips"] = resolved_ips
    scopes = [classify_ip_scope(addr) for addr in resolved_ips]

    if "metadata" in scopes:
        result["address_scope"] = "metadata"
        result["error"] = f"禁止访问云元数据端点: {host}"
        return result

    if "local" in scopes:
        address_scope = "local"
    elif "private" in scopes:
        address_scope = "private"
    else:
        address_scope = "public"
    result["address_scope"] = address_scope

    blocked_scopes = sorted({s for s in scopes if not _scope_allows(s, effective_scope)})
    if blocked_scopes:
        resolved = ", ".join(resolved_ips)
        result["error"] = (
            f"当前 network_scope={effective_scope} 不允许访问 "
            f"{'/'.join(blocked_scopes)} 地址: {host} ({resolved})")
        return result

    return result


def validate_url(url: str, network_scope: str | None = "public") -> str | None:
    """SSRF 防护：按 network_scope 校验 URL。返回错误字符串或 None。"""
    return inspect_url(url, network_scope).get("error")


# ---- 命令安全 ----

_DANGEROUS_COMMANDS: set[str] = {
    "rmdir", "del", "deltree",
    "shutdown", "format",
    "cacls", "icacls", "netsh",
}

_DANGEROUS_PATTERNS: list[tuple[_re.Pattern, str]] = [
    (_re.compile(r'\bformat\s+[a-zA-Z]:'), "禁止 Windows 格式化磁盘"),
    (_re.compile(r'\bdel\s+/[fq].*[A-Z]:\\'), "禁止 Windows 强制删除系统文件"),
]

_ENV_ALLOWLIST: set[str] = {
    "PATH", "HOME", "USER", "USERNAME", "USERPROFILE",
    "TEMP", "TMP", "TMPDIR",
    "SYSTEMROOT", "SystemRoot", "WINDIR", "windir",
    "ProgramFiles", "ProgramFiles(x86)",
    "CommonProgramFiles", "CommonProgramFiles(x86)",
    "ProgramData", "ALLUSERSPROFILE", "PUBLIC",
    "COMSPEC", "PATHEXT", "OS",
    "CUDA_VISIBLE_DEVICES", "CUDA_PATH",
    "VIRTUAL_ENV", "CONDA_PREFIX", "CONDA_DEFAULT_ENV",
    "VOTX_USER_DIR",
}


def check_dangerous_command(command: str) -> str | None:
    """检查命令是否包含危险操作。返回错误字符串或 None（通过）。"""
    import shlex

    cmd_stripped = command.strip()

    try:
        tokens = shlex.split(cmd_stripped)
        if tokens:
            base_cmd = os.path.basename(tokens[0]).lower()
            if base_cmd in _DANGEROUS_COMMANDS:
                return f"禁止执行危险命令: {base_cmd}"
    except ValueError:
        pass

    for pattern, msg in _DANGEROUS_PATTERNS:
        if pattern.search(command):
            return msg

    return None


def safe_working_dir(working_dir: str) -> str | None:
    """校验 working_dir 在允许范围内。返回错误字符串或 None。"""
    if not working_dir or not working_dir.strip():
        return None
    p = safe_path(working_dir)
    if p is None:
        return f"无效的工作目录: {working_dir}"
    if not p.exists():
        return f"工作目录不存在: {p}"
    if not p.is_dir():
        return f"工作目录不是目录: {p}"
    if check_sandbox(p) is None:
        return f"工作目录越权: {p}"
    return None


def sanitize_env() -> dict[str, str]:
    """返回清理后的环境变量字典，剥离 API keys/tokens/passwords 等敏感信息。"""
    env: dict[str, str] = {}
    for key, val in os.environ.items():
        upper = key.upper()
        if any(s in upper for s in ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH", "CREDENTIAL")):
            continue
        if key in _ENV_ALLOWLIST:
            env[key] = val
        elif key.startswith(("VOTX_", "CONDA_", "VIRTUAL_")):
            env[key] = val
        elif key in ("CC", "CXX", "MAKEFLAGS", "PKG_CONFIG_PATH"):
            env[key] = val
    return env


# ---- 工具日志 ----

def _log_path(user_dir: str | None = None) -> str | None:
    """执行 log_path 内部辅助逻辑。"""
    user_dir = user_dir or get_current_user_dir()
    if not user_dir:
        return None
    log_dir = os.path.join(user_dir, "history", "log")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "tool_log.jsonl")


_TOOL_LOG_MAX_CACHE = None


def _get_tool_log_max() -> int:
    """执行 get_tool_log_max 内部辅助逻辑。"""
    global _TOOL_LOG_MAX_CACHE
    if _TOOL_LOG_MAX_CACHE is not None:
        return _TOOL_LOG_MAX_CACHE
    try:
        config_path = _PROJECT_ROOT / "config" / "config_core.json"
        if config_path.exists():
            config = json.loads(config_path.read_text(encoding="utf-8"))
            _TOOL_LOG_MAX_CACHE = config.get("tool", {}).get("tool_log_max", 1000)
        else:
            _TOOL_LOG_MAX_CACHE = 1000
    except Exception:
        _TOOL_LOG_MAX_CACHE = 1000
    return _TOOL_LOG_MAX_CACHE


def log_tool_call(name: str, args: dict, result: str, success: bool, elapsed: float, user_dir: str | None = None, tool_call_id: str = ""):
    """处理 log_tool_call 相关逻辑。返回生成的 log_id。"""
    path = _log_path(user_dir)
    if not path:
        return ""
    _sensitive_keys = {"api_key", "key", "token", "secret", "password", "authorization", "auth"}
    safe_args = {}
    for k, v in args.items():
        kl = k.lower()
        if any(s in kl for s in _sensitive_keys):
            safe_args[k] = "***"
        elif isinstance(v, str) and len(v) > 200:
            safe_args[k] = v[:200] + "..."
        else:
            safe_args[k] = v
    safe_result = result
    for s in _sensitive_keys:
        if s in result.lower():
            safe_result = result[:2000]
            break
    else:
        safe_result = result[:2000]
    log_id = uuid.uuid4().hex[:8]
    entry = {
        "id": log_id,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": name,
        "args": safe_args,
        "result": safe_result,
        "success": success,
        "elapsed": round(elapsed, 3),
    }
    if tool_call_id:
        entry["tool_call_id"] = tool_call_id
    try:
        append_jsonl(path, entry)
    except Exception:
        pass

    # Enforce tool_log_max: 超过上限则只保留最新 N 条
    max_lines = _get_tool_log_max()
    try:
        with open(path, "r+", encoding="utf-8") as f:
            lines = f.readlines()
            if len(lines) > max_lines:
                f.seek(0)
                f.truncate()
                f.writelines(lines[-max_lines:])
    except Exception:
        pass

    return log_id
