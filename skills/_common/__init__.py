"""skills 公共模块 — err / safe_path / check_sandbox / SSRF 防护 / 命令安全 / log_tool_call"""
import ipaddress
import json
import os
import re as _re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse as _urlparse

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# skills/_common/__init__.py → skills/_common → skills → 项目根


def err(msg: str) -> str:
    return f"ERROR: {msg}"


def truncate(text: str, max_len: int = 0) -> str:
    """截断文本到指定长度。max_len=0 表示不限制（兼容旧调用方）。"""
    if max_len > 0 and len(text) > max_len:
        return text[:max_len] + f"\n... (截断，共 {len(text)} 字符)"
    return text


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

    沙箱已关闭：允许访问任意路径。
    如需重新启用，取消下方注释即可。
    """
    try:
        return p.resolve()
    except Exception:
        return None


# ---- SSRF 防护 ----

_SSRF_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

_CLOUD_METADATA_IPS = {"169.254.169.254"}

MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB


def _is_ip_blocked(host: str) -> bool:
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    for net in _SSRF_BLOCKED_NETWORKS:
        if addr in net:
            return True
    return False


def validate_url(url: str) -> str | None:
    """SSRF 防护：校验 URL 安全性。返回错误字符串或 None（通过）。"""
    try:
        parsed = _urlparse(url)
    except Exception:
        return "无效的 URL 格式"

    if parsed.scheme not in ("http", "https"):
        return f"不支持的协议: {parsed.scheme}，仅允许 http/https"

    host = parsed.hostname
    if not host:
        return "URL 缺少主机名"

    if host.lower() in ("localhost", "0.0.0.0", "0", "[::]", "::", "127.0.0.1"):
        return f"禁止访问本地地址: {host}"

    if host in _CLOUD_METADATA_IPS:
        return f"禁止访问云元数据端点: {host}"

    if _is_ip_blocked(host):
        return f"禁止访问内网/回环地址: {host}"

    return None


# ---- 命令安全 ----

_DANGEROUS_COMMANDS: set[str] = {
    "rm", "rmdir", "del", "deltree",
    "shutdown", "reboot", "halt", "poweroff", "init", "systemctl",
    "sudo", "su", "pkexec", "doas",
    "chmod", "chown", "chgrp", "chattr", "cacls", "icacls",
    "mkfs", "mkfs.ext4", "mkfs.ntfs", "mkfs.vfat",
    "dd", "fdisk", "parted", "format",
    "iptables", "nftables", "ufw", "firewall-cmd", "netsh",
    "killall", "pkill",
}

_DANGEROUS_PATTERNS: list[tuple[_re.Pattern, str]] = [
    (_re.compile(r'\brm\s+.*-rf\b'), "禁止 rm -rf (递归强制删除)"),
    (_re.compile(r'\brm\s+.*-r\s+/'), "禁止递归删除根目录"),
    (_re.compile(r'\bdd\s+if='), "禁止 dd 磁盘操作"),
    (_re.compile(r'>\s*/dev/sd'), "禁止重定向写入块设备"),
    (_re.compile(r'mkfs\.'), "禁止格式化文件系统"),
    (_re.compile(r':\(\)\s*\{'), "禁止 fork 炸弹模式"),
    (_re.compile(r'\bformat\s+[a-zA-Z]:'), "禁止 Windows 格式化磁盘"),
    (_re.compile(r'\bdel\s+/[fq].*[A-Z]:\\'), "禁止 Windows 强制删除系统文件"),
]

_ENV_ALLOWLIST: set[str] = {
    "PATH", "HOME", "USER", "USERNAME", "USERPROFILE",
    "TEMP", "TMP", "TMPDIR",
    "LANG", "LC_ALL", "LC_CTYPE", "LANGUAGE",
    "TERM", "COLORTERM", "DISPLAY", "WAYLAND_DISPLAY",
    "SHELL", "PWD", "OLDPWD",
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

def _log_path() -> str | None:
    user_dir = os.environ.get("VOTX_USER_DIR")
    if not user_dir:
        return None
    log_dir = os.path.join(user_dir, "history", "log")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "tool_log.json")


def log_tool_call(name: str, args: dict, result: str, success: bool, elapsed: float):
    path = _log_path()
    if not path:
        return
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
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": name,
        "args": safe_args,
        "result": safe_result,
        "success": success,
        "elapsed": round(elapsed, 3),
    }
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
