"""视频下载工具 — yt-dlp 封装"""
import os
import subprocess
from pathlib import Path
from run.tool import register_tool
from plugins._common import err, truncate, safe_path, check_sandbox


def download_video(url: str, output_dir: str = "", filename: str = "", format_spec: str = "") -> str:
    """使用 yt-dlp 下载视频，返回命令输出"""
    if not url.strip():
        return err("URL 为空")

    # 校验输出目录（沙箱保护，可选择性放开）
    out_dir = output_dir.strip()
    if out_dir:
        sp = safe_path(out_dir)
        if sp is None:
            return err(f"输出目录无效: {out_dir}")
        sandboxed = check_sandbox(sp)
        if sandboxed is None:
            if os.environ.get("VOTX_VIDEO_DOWNLOAD_OUTSIDE_SANDBOX", "").strip() in ("1", "true", "yes"):
                # 跳过沙箱：直接展开 ~ 并创建目录
                sp = Path(out_dir).expanduser().resolve()
            else:
                return err(f"输出目录越权（仅允许项目目录和用户目录）。设置 VOTX_VIDEO_DOWNLOAD_OUTSIDE_SANDBOX=1 可解除限制。当前路径: {out_dir}")
        else:
            sp = sandboxed
        sp.mkdir(parents=True, exist_ok=True)
        if not sp.is_dir():
            return err(f"输出路径不是目录: {sp}")
        out_dir = str(sp)

    # 组装 yt-dlp 参数
    args = ["yt-dlp"]

    # 格式
    if format_spec.strip():
        args.extend(["-f", format_spec.strip()])
    else:
        args.extend(["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"])

    # 输出路径
    if filename.strip():
        # 强制只取 basename，防止 ../ 或绝对路径样式绕过沙箱
        safe_name = os.path.basename(filename.strip())
        out = os.path.join(out_dir, safe_name) if out_dir else safe_name
    elif out_dir:
        out = os.path.join(out_dir, "%(title)s.%(ext)s")
    else:
        out = "%(title)s.%(ext)s"
    args.extend(["-o", out])

    args.append(url.strip())

    try:
        r = subprocess.run(
            args,
            shell=False,
            capture_output=True,
            timeout=300,
            encoding="utf-8",
            errors="replace",
            text=True,
        )
        # yt-dlp 进度条在 stderr，最后几行才是结果
        stderr = r.stderr.strip() if r.stderr else ""
        stdout = r.stdout.strip() if r.stdout else ""

        # 提取关键行（最后 5 行 stderr 通常包含结果）
        lines = []
        if stdout:
            lines.append(stdout)
        if stderr:
            stderr_lines = stderr.splitlines()
            # 合并目标文件
            merged = [l for l in stderr_lines if "has already been downloaded" in l or "Destination" in l or "Merging" in l]
            key_lines = merged + stderr_lines[-5:]
            lines.append("\n".join(key_lines))
        if not lines:
            lines.append(f"(exit={r.returncode})")
        return truncate("\n".join(lines))
    except FileNotFoundError:
        return err("yt-dlp 未安装。请运行: pip install yt-dlp")
    except subprocess.TimeoutExpired:
        return err("下载超时 (300s)")
    except Exception as e:
        return err(f"下载失败: {e}")


SCHEMA = {
    "type": "function",
    "function": {
        "name": "download_video",
        "description": (
            "使用 yt-dlp 下载视频。支持 B站/YouTube/抖音等平台。"
            "output_dir 默认受沙箱限制，设置 VOTX_VIDEO_DOWNLOAD_OUTSIDE_SANDBOX=1 后可输出到任意目录（如桌面/下载文件夹）。"
            "filename: 输出文件名（不含扩展名）。"
            "format_spec: 格式选择器（可选，默认最佳 mp4）。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "视频 URL"},
                "output_dir": {"type": "string", "description": "输出目录路径"},
                "filename": {"type": "string", "description": "输出文件名（不含扩展名）"},
                "format_spec": {"type": "string", "description": "yt-dlp 格式选择器，如 bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"},
            },
            "required": ["url"],
        },
    },
}


def register():
    """处理 register 相关逻辑。"""
    register_tool(SCHEMA, download_video)
