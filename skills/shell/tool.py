"""系统命令执行工具 — shell=False + shlex 解析"""
import os
import shlex
import subprocess
from run.tool import register_tool
from skills._common import err, truncate, check_dangerous_command, safe_working_dir, sanitize_env, get_current_user_dir


def run_command(command: str, working_dir: str = "") -> str:
    """执行系统命令"""
    if not command.strip():
        return err("命令为空")

    # 安全检查：危险命令拦截
    danger_err = check_dangerous_command(command)
    if danger_err:
        return err(danger_err)

    # 安全检查：工作目录校验
    wd_err = safe_working_dir(working_dir)
    if wd_err:
        return err(wd_err)

    # cmd.exe /c 时注入 UTF-8 代码页，防止中文路径乱码
    cmd = command.strip()
    if cmd[:4].lower() == "cmd " or cmd[:8].lower() == "cmd.exe ":
        import re
        m = re.match(r'(cmd(\.exe)?)\s+(/[ck])\s+', cmd, re.IGNORECASE)
        if m:
            rest = cmd[m.end():].strip()
            # 去掉已有的外层引号
            if rest.startswith('"') and rest.endswith('"'):
                rest = rest[1:-1]
            # 转义内部双引号防止命令注入
            rest_escaped = rest.replace('"', '\\"')
            cmd = f'{m.group(1)} {m.group(3)} "chcp 65001 > nul & {rest_escaped}"'

    try:
        args = shlex.split(cmd)
    except ValueError as e:
        return err(f"命令解析失败: {e}")

    cwd = working_dir.strip() or get_current_user_dir() or None

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
            env=sanitize_env(),
        )
        output = r.stdout.strip() or r.stderr.strip() or f"(exit={r.returncode})"
        return truncate(output, max_len=100000)
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
            "执行系统命令。shell=False 安全模式。支持任意命令，超时 120 秒。Windows 下自动处理编码。"
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
    """处理 register 相关逻辑。"""
    register_tool(SCHEMA, run_command)
