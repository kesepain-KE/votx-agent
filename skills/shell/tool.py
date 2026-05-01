"""系统命令执行工具 — shell=False + shlex 解析，参数黑名单拦截"""
import os
import shlex
import subprocess
from run.tool import register_tool
from skills._common import err, truncate, safe_path

# 仅拦截真正危险的参数模式
_PARAM_BLOCK = [
    "rm -rf /",
    "rm -rf ~",
    "chmod 777 /",
    "shutdown",
    "mkfs.",
    "dd if=",
    "/dev/sda",
    ":(){ :|:& };:",
    "> /dev/sda",
    "format c:",
]


def run_command(command: str, working_dir: str = "") -> str:
    """安全执行系统命令"""
    if not command.strip():
        return err("命令为空")

    cmd_lower = command.lower()
    for pattern in _PARAM_BLOCK:
        if pattern in cmd_lower:
            return err(f"危险命令被拦截 (匹配: {pattern})")

    try:
        args = shlex.split(command)
    except ValueError as e:
        return err(f"命令解析失败: {e}")

    if working_dir.strip():
        sp = safe_path(working_dir.strip())
        if sp is None:
            return err(f"工作目录越权或无效: {working_dir}")
        cwd = str(sp)
    else:
        cwd = os.environ.get("KESEPAIN_USER_DIR") or None

    try:
        r = subprocess.run(
            args,
            shell=False,
            capture_output=True,
            timeout=120,
            encoding="utf-8",
            errors="replace",
            text=True,
            cwd=cwd,
        )
        output = r.stdout.strip() or r.stderr.strip() or f"(exit={r.returncode})"
        return truncate(output)
    except FileNotFoundError:
        return err(f"命令未找到: {args[0]}")
    except subprocess.TimeoutExpired:
        return err("命令超时 (120s)")
    except Exception as e:
        return err(f"执行失败: {e}")


SCHEMA = {
    "type": "function",
    "function": {
        "name": "run_command",
        "description": (
            "执行系统命令。shell=False 安全模式，仅拦截 rm -rf / 等极端危险操作。"
            "支持任意命令，超时 120 秒。Windows 下自动处理编码。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令（shlex 解析）"},
                "working_dir": {"type": "string", "description": "工作目录（可选，默认用户目录）"},
            },
            "required": ["command"],
        },
    },
}


def register():
    register_tool(SCHEMA, run_command)
